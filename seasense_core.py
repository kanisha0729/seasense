"""SeaSense backend logic, shared by the MCP server and the web app.

Fetches the live forecast from Open-Meteo (Marine + Forecast APIs, free,
no API key), works out the trip risk, and writes the spoken text.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from i18n import TEXT, spoken_hour, t
from risk import assess
from zones import ZONES, zone_name

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TRIP_HOURS = 12           # how far ahead a fishing trip looks
CACHE_SECONDS = 600       # reuse a forecast for 10 minutes
IST = timezone(timedelta(hours=5, minutes=30))
USERS_FILE = Path(__file__).parent / "data" / "users.json"

_cache: dict[str, tuple[float, dict]] = {}


class ForecastError(Exception):
    pass


# ---------- live data ----------

async def _download(zone_key: str) -> dict:
    zone = ZONES[zone_key]
    common = {"latitude": zone["lat"], "longitude": zone["lon"],
              "timezone": "GMT", "forecast_days": 3}
    async with httpx.AsyncClient(timeout=15) as client:
        marine, weather = await asyncio.gather(
            client.get(MARINE_URL, params={**common, "hourly": "wave_height,wave_period"}),
            client.get(FORECAST_URL, params={
                **common,
                "hourly": "wind_speed_10m,wind_gusts_10m,precipitation_probability",
            }),
        )
    marine.raise_for_status()
    weather.raise_for_status()
    return {"marine": marine.json()["hourly"], "weather": weather.json()["hourly"]}


async def get_hours(zone_key: str, count: int = TRIP_HOURS) -> tuple[list[dict], datetime]:
    """The next `count` hours (from this hour) of waves, wind, gusts and rain for a zone."""
    cached = _cache.get(zone_key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        raw, fetched = cached[1]["raw"], cached[1]["fetched"]
    else:
        try:
            raw = await _download(zone_key)
        except Exception as exc:
            log.warning("Open-Meteo request failed for %s: %s", zone_key, exc)
            raise ForecastError(str(exc)) from exc
        fetched = datetime.now(IST)
        _cache[zone_key] = (time.time(), {"raw": raw, "fetched": fetched})

    m, w = raw["marine"], raw["weather"]
    wave_at = dict(zip(m["time"], m["wave_height"]))
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = now + timedelta(hours=count)

    hours = []
    for i, stamp in enumerate(w["time"]):
        ts = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
        if not (now <= ts < end):
            continue
        hours.append({
            "time": ts.astimezone(IST).isoformat(),
            "hour": ts.astimezone(IST).hour,
            "minute": ts.astimezone(IST).minute,
            "wave": wave_at.get(stamp),
            "wind": w["wind_speed_10m"][i],
            "gust": w["wind_gusts_10m"][i],
            "rain": w["precipitation_probability"][i],
        })
    if not any(h["wave"] is not None for h in hours) or not any(h["gust"] is not None for h in hours):
        raise ForecastError("no forecast data for this zone right now")
    return hours, fetched


# ---------- the report ----------

def _num(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}"


async def get_report(zone_key: str, lang: str = "en") -> dict:
    """Everything the UI and the voice tools need, in one dictionary."""
    hours, fetched = await get_hours(zone_key)
    waves = [h["wave"] for h in hours if h["wave"] is not None]
    gust_hours = [h for h in hours if h["gust"] is not None]
    peak = max(gust_hours, key=lambda h: h["gust"])
    rain_max = max((h["rain"] or 0 for h in hours), default=0)
    wind_now = next((h["wind"] for h in hours if h["wind"] is not None), 0)

    level, cause, value = assess(max(waves), peak["gust"])
    value_text = _num(value, 1 if cause == "wave" else 0)
    zone = zone_name(zone_key, lang)
    texts = TEXT[lang]
    level_word = texts["level"][level]
    reason = texts["cause"][cause].format(value=value_text)
    rain = (texts["rain_high"].format(rain=_num(rain_max, 0)) if rain_max >= 30 else texts["rain_low"])

    briefing = t(lang, "briefing", zone=zone, wave_now=_num(waves[0]), wave_max=_num(max(waves)),
                 hours=TRIP_HOURS, wind=_num(wind_now, 0), gust=_num(peak["gust"], 0),
                 gust_time=spoken_hour(peak["hour"], lang, peak["minute"]), rain=rain, level=level_word, reason=reason)
    risk = t(lang, "risk", level=level_word, zone=zone, reason=reason, hours=TRIP_HOURS,
             advice=texts["advice"][level])

    return {
        "zone_key": zone_key,
        "zone": zone,
        "lang": lang,
        "level": level,
        "level_word": level_word,
        "reason": reason,
        "advice": texts["advice"][level],
        "briefing": briefing,
        "risk": risk,
        "metrics": {
            "wave_now": round(waves[0], 2),
            "wave_max": round(max(waves), 2),
            "wind_now": round(wind_now),
            "gust_max": round(peak["gust"]),
            "gust_peak_time": peak["time"],
            "rain_max": round(rain_max),
        },
        "hours": hours,
        "fetched_at": fetched.isoformat(),
        "source": "Open-Meteo Marine + Forecast API (live)",
    }


# ---------- feature: best time to go (next 24 hours) ----------

LEVEL_RANK = {"safe": 0, "caution": 1, "danger": 2}
BEST_HORIZON = 24     # hours to search
MIN_WINDOW = 3        # a window must last at least this many hours to be useful


def _hour_level(h: dict) -> str | None:
    if h["wave"] is None or h["gust"] is None:
        return None
    return assess(h["wave"], h["gust"])[0]


def _first_run(levels: list[str | None], worst_allowed: int) -> tuple[int, int] | None:
    """Earliest run of >= MIN_WINDOW hours whose level is no worse than worst_allowed.
    Returns (start index, end index exclusive), stretched to the run's full length."""
    i = 0
    while i < len(levels):
        if levels[i] is not None and LEVEL_RANK[levels[i]] <= worst_allowed:
            j = i
            while j < len(levels) and levels[j] is not None and LEVEL_RANK[levels[j]] <= worst_allowed:
                j += 1
            if j - i >= MIN_WINDOW:
                return i, j
            i = j
        else:
            i += 1
    return None


def _when(iso: str, lang: str, after: str | None = None) -> str:
    """'4:30 AM tomorrow' / 'நாளை காலை 4:30 மணி' / 'कल सुबह 4:30 बजे'.
    With `after` on the same day, the day word is left out ('8 PM today to 11 PM')."""
    dt = datetime.fromisoformat(iso).astimezone(IST)
    clock = spoken_hour(dt.hour, lang, dt.minute)
    if after and datetime.fromisoformat(after).astimezone(IST).date() == dt.date():
        return clock
    tomorrow = dt.date() > datetime.now(IST).date()
    day = TEXT[lang]["tomorrow" if tomorrow else "today"]
    return f"{clock} {day}" if lang == "en" else f"{day} {clock}"


async def best_window(zone_key: str, lang: str = "en") -> dict:
    """Find the safest time to set out in the next 24 hours."""
    hours, _ = await get_hours(zone_key, BEST_HORIZON)
    levels = [_hour_level(h) for h in hours]
    zone = zone_name(zone_key, lang)

    run, status = _first_run(levels, 0), "safe"
    if not run:
        run, status = _first_run(levels, 1), "caution"
    strip = [{"time": h["time"], "level": lv} for h, lv in zip(hours, levels)]
    if not run:
        return {"status": "none", "text": t(lang, "best_none", zone=zone), "strip": strip}

    i, j = run
    start_iso = hours[i]["time"]
    end_iso = (datetime.fromisoformat(hours[j - 1]["time"]) + timedelta(hours=1)).isoformat()
    start, end = _when(start_iso, lang), _when(end_iso, lang, after=start_iso)
    if status == "safe" and i == 0:
        status, text = "now", t(lang, "best_now", zone=zone, end=end)
    elif status == "safe":
        status, text = "later", t(lang, "best_later", zone=zone, start=start, end=end)
    else:
        text = t(lang, "best_caution", zone=zone, start=start, end=end)
    return {"status": status, "start": start_iso, "end": end_iso, "hours": j - i, "text": text, "strip": strip}


# ---------- feature: trip check-in + worse-weather warning ----------

TRIPS_FILE = Path(__file__).parent / "data" / "trips.json"
COAST_GUARD = "1554"   # Indian Coast Guard, toll-free search and rescue


def parse_back_by(text: str, now: datetime | None = None) -> datetime | None:
    """'14:00', '2 pm', '2:30pm', '8 hours', '8h' -> the next such time in IST."""
    now = now or datetime.now(IST)
    s = (text or "").strip().lower().replace(".", "")
    m = re.fullmatch(r"(\d{1,2})\s*(h|hr|hrs|hour|hours)", s)
    if m:
        hrs = int(m.group(1))
        return now + timedelta(hours=hrs) if 1 <= hrs <= 48 else None
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if ampm == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return when if when > now else when + timedelta(days=1)


def _duration(minutes: int, lang: str) -> str:
    h, m = divmod(max(0, minutes), 60)
    words = {"en": ("hours" if h != 1 else "hour", "minutes"), "ta": ("மணி", "நிமிடம்"), "hi": ("घंटे", "मिनट")}[lang]
    if h and m:
        return f"{h} {words[0]} {m} {words[1]}"
    return f"{h} {words[0]}" if h else f"{m} {words[1]}"


async def _trip_conditions(zone_key: str, until: datetime) -> dict:
    """Worst waves and gusts between now and the expected return."""
    count = max(3, min(24, math.ceil((until - datetime.now(IST)).total_seconds() / 3600)))
    hours, _ = await get_hours(zone_key, count)
    waves = [h["wave"] for h in hours if h["wave"] is not None]
    gusts = [h["gust"] for h in hours if h["gust"] is not None]
    level, cause, value = assess(max(waves), max(gusts))
    return {"level": level, "cause": cause, "value": value,
            "wave_max": round(max(waves), 2), "gust_max": round(max(gusts))}


def _reason(cond: dict, lang: str) -> str:
    value = _num(cond["value"], 1 if cond["cause"] == "wave" else 0)
    return TEXT[lang]["cause"][cond["cause"]].format(value=value)


def _worsened(start: dict, now: dict) -> bool:
    return (LEVEL_RANK[now["level"]] > LEVEL_RANK[start["level"]]
            or now["wave_max"] >= start["wave_max"] + 0.5
            or now["gust_max"] >= start["gust_max"] + 10)


async def start_trip(user: str, zone_key: str, back_by: datetime) -> dict:
    cond = await _trip_conditions(zone_key, back_by)
    with _lock:
        trips = _read(TRIPS_FILE)
        trip = {"name": " ".join(user.split()), "zone": zone_key, "status": "at_sea",
                "left_at": datetime.now(IST).isoformat(), "back_by": back_by.isoformat(),
                "token": secrets.token_urlsafe(9), "at_start": cond}
        trips[_key(user)] = trip
        _write(TRIPS_FILE, trips)
    return trip


def end_trip(user: str) -> dict | None:
    with _lock:
        trips = _read(TRIPS_FILE)
        trip = trips.get(_key(user))
        if not trip or trip["status"] != "at_sea":
            return None
        trip.update(status="returned", returned_at=datetime.now(IST).isoformat())
        _write(TRIPS_FILE, trips)
        return trip


def get_trip(user: str) -> dict | None:
    return _read(TRIPS_FILE).get(_key(user))


def trip_by_token(token: str) -> dict | None:
    return next((tr for tr in _read(TRIPS_FILE).values() if secrets.compare_digest(tr["token"], token or "")), None)


async def trip_status(trip: dict, lang: str = "en") -> dict:
    """Where the trip stands now, plus a warning if the sea got worse since departure."""
    now = datetime.now(IST)
    back_by = datetime.fromisoformat(trip["back_by"])
    zone = zone_name(trip["zone"], lang)
    left, back = _when(trip["left_at"], lang), _when(trip["back_by"], lang)
    out = {"name": trip["name"], "zone": zone, "zone_key": trip["zone"], "status": trip["status"],
           "left_at": trip["left_at"], "back_by": trip["back_by"], "token": trip["token"],
           "worsened": False, "warning": "", "coast_guard": COAST_GUARD}

    if trip["status"] == "returned":
        out["text"] = t(lang, "trip_returned", user=trip["name"], time=_when(trip["returned_at"], lang))
        return out

    mins = int((back_by - now).total_seconds() // 60)
    if mins >= 0:
        out["text"] = t(lang, "trip_at_sea", user=trip["name"], zone=zone, left=left, back=back,
                        remaining=_duration(mins, lang))
    else:
        out["status"] = "overdue"
        out["text"] = t(lang, "trip_overdue", user=trip["name"], zone=zone, left=left, back=back,
                        late=_duration(-mins, lang), cg=COAST_GUARD)

    try:
        cond = await _trip_conditions(trip["zone"], max(back_by, now + timedelta(hours=3)))
        out["now"] = cond
        if _worsened(trip["at_start"], cond):
            out["worsened"] = True
            out["warning"] = t(lang, "trip_worse", zone=zone, left=left,
                               level=TEXT[lang]["level"][cond["level"]], reason=_reason(cond, lang))
    except ForecastError:
        pass
    return out


# ---------- feature: harbour board (every zone at once) ----------

async def board(lang: str = "en") -> list[dict]:
    async def one(key: str) -> dict:
        try:
            r = await get_report(key, lang)
            b = await best_window(key, lang)
            return {"zone_key": key, "zone": r["zone"], "level": r["level"], "level_word": r["level_word"],
                    "reason": r["reason"], "wave_max": r["metrics"]["wave_max"], "gust_max": r["metrics"]["gust_max"],
                    "rain_max": r["metrics"]["rain_max"], "best": b["text"], "best_status": b["status"]}
        except ForecastError:
            return {"zone_key": key, "zone": zone_name(key, lang), "level": "none",
                    "error": t(lang, "fetch_failed", zone=zone_name(key, lang))}
    return list(await asyncio.gather(*(one(k) for k in ZONES)))


# ---------- users: one profile shared by the web app and the voice tools ----------

_lock = threading.Lock()
log = logging.getLogger("seasense")


def _read(path: Path) -> dict:
    """Read a JSON store. A damaged file is set aside (never silently overwritten)."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        backup = path.with_suffix(f".corrupt-{int(time.time())}.json")
        path.replace(backup)
        log.error("%s was damaged; moved it to %s and started fresh", path.name, backup.name)
        return {}


def _write(path: Path, data: dict) -> None:
    """Write atomically: a crash mid-write can't leave a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _key(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def load_users() -> dict:
    users = _read(USERS_FILE)
    for k, v in list(users.items()):
        if isinstance(v, str):          # file written by the first version
            users[k] = {"name": k.title(), "zone": v.lower().split()[0], "lang": "en"}
    return users


def save_user(user: str, zone_key: str, lang: str) -> None:
    """Set a user's zone and language (voice tool or web app). Keeps any login."""
    with _lock:
        users = load_users()
        record = users.get(_key(user), {"name": user.strip()})
        record.update(zone=zone_key, lang=lang)
        users[_key(user)] = record
        _write(USERS_FILE, users)


def get_user(user: str) -> dict | None:
    """Public profile: name, zone, lang (never the PIN hash)."""
    record = load_users().get(_key(user))
    if not record:
        return None
    return {"name": record.get("name", user), "zone": record["zone"], "lang": record.get("lang", "en"),
            "has_login": "pin_hash" in record}


# ---------- login (name + PIN) ----------

SESSIONS_FILE = Path(__file__).parent / "data" / "sessions.json"
SESSION_DAYS = 30


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000).hex()


def validate_new_account(name: str, pin: str) -> str | None:
    """Return an error code, or None if the details are fine."""
    if not (2 <= len(name.strip()) <= 30) or not all(
            unicodedata.category(ch)[0] in "LMN" or ch in " .'-" for ch in name):
        return "bad_name"     # letters in any script, digits, spaces and . ' - only
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        return "bad_pin"
    record = load_users().get(_key(name))
    if record and "pin_hash" in record:
        return "name_taken"
    return None


def create_account(name: str, pin: str, zone_key: str, lang: str) -> bool:
    """Make a login. If the voice tools already know this name, keep their profile.
    Returns False if someone else created a login with this name first."""
    with _lock:
        users = load_users()
        record = users.get(_key(name), {})
        if "pin_hash" in record:
            return False
        salt = secrets.token_bytes(16)
        record.update(name=" ".join(name.split()), zone=zone_key, lang=lang,
                      salt=salt.hex(), pin_hash=_hash_pin(pin, salt))
        users[_key(name)] = record
        _write(USERS_FILE, users)
        return True


def change_pin(name: str, new_pin: str) -> None:
    with _lock:
        users = load_users()
        salt = secrets.token_bytes(16)
        users[_key(name)].update(salt=salt.hex(), pin_hash=_hash_pin(new_pin, salt))
        _write(USERS_FILE, users)


def delete_account(name: str) -> None:
    """Remove the profile, the login and every session for this person."""
    with _lock:
        users = load_users()
        users.pop(_key(name), None)
        _write(USERS_FILE, users)
        sessions = {t: s for t, s in _read(SESSIONS_FILE).items() if s["user"] != _key(name)}
        _write(SESSIONS_FILE, sessions)


def check_login(name: str, pin: str) -> bool:
    record = load_users().get(_key(name))
    if not record or "pin_hash" not in record:
        return False
    return hmac.compare_digest(record["pin_hash"], _hash_pin(pin, bytes.fromhex(record["salt"])))


def new_session(name: str) -> str:
    with _lock:
        sessions = _read(SESSIONS_FILE)
        now = time.time()
        sessions = {t: s for t, s in sessions.items() if s["expires"] > now}   # drop expired
        token = secrets.token_urlsafe(32)
        sessions[token] = {"user": _key(name), "expires": now + SESSION_DAYS * 86400}
        _write(SESSIONS_FILE, sessions)
        return token


def session_user(token: str | None) -> str | None:
    if not token:
        return None
    s = _read(SESSIONS_FILE).get(token)
    if not s or s["expires"] < time.time():
        return None
    return s["user"]


def end_session(token: str | None) -> None:
    with _lock:
        sessions = _read(SESSIONS_FILE)
        if token in sessions:
            del sessions[token]
            _write(SESSIONS_FILE, sessions)


# ---------- brute-force protection for PIN sign-in ----------

MAX_FAILURES = 5          # wrong PINs allowed ...
FAILURE_WINDOW = 600      # ... within 10 minutes
LOCKOUT_SECONDS = 600     # then that name is locked for 10 minutes
_failures: dict[str, list[float]] = {}


def login_locked_for(name: str) -> int:
    """Seconds until this name may try again (0 = not locked)."""
    now = time.time()
    recent = [t for t in _failures.get(_key(name), []) if now - t < FAILURE_WINDOW]
    _failures[_key(name)] = recent
    if len(recent) >= MAX_FAILURES:
        return max(1, int(recent[-1] + LOCKOUT_SECONDS - now))
    return 0


def record_failure(name: str) -> None:
    _failures.setdefault(_key(name), []).append(time.time())


def clear_failures(name: str) -> None:
    _failures.pop(_key(name), None)
