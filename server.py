"""SeaSense: spoken sea-safety briefings for coastal fishermen.

An MCP server with three tools:
  get_sea_briefing  - waves, wind and rain for a zone, as a short spoken briefing
  check_trip_risk   - Safe / Caution / Don't go for the next 12 hours
  save_my_zone      - remembers a user's usual zone

Data: Open-Meteo Marine and Forecast APIs (free, no API key).
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from risk import assess
from zones import find_zone, zone_names

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TRIP_HOURS = 12  # how far ahead a fishing trip looks
IST = timezone(timedelta(hours=5, minutes=30))
USERS_FILE = Path(__file__).parent / "data" / "users.json"

logging.getLogger("httpx").setLevel(logging.WARNING)  # hide per-request log lines

server = MCPServer(
    "SeaSense",
    instructions=(
        "Sea-safety briefings for coastal fishermen in Tamil Nadu. "
        "Read the tool output aloud as it is; it is written to be spoken."
    ),
)


# ---------- saved zones ----------

def load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}


def save_users(users: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def resolve_zone(zone: str, user: str) -> dict | None:
    """Use the zone the user named, or fall back to their saved zone."""
    if zone:
        return find_zone(zone)
    if user:
        saved = load_users().get(user.strip().lower())
        if saved:
            return find_zone(saved)
    return None


def unknown_zone_message(zone: str, user: str) -> str:
    if not zone and user:
        return (f"I don't have a saved zone for {user} yet. "
                f"Tell me your usual zone first. I know: {zone_names()}.")
    return f"I don't know the zone '{zone}'. I know: {zone_names()}."


# ---------- weather data ----------

async def fetch_conditions(zone: dict) -> dict:
    """Get the next TRIP_HOURS of waves, wind and rain for a zone."""
    common = {"latitude": zone["lat"], "longitude": zone["lon"],
              "timezone": "GMT", "forecast_days": 2}
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
    m, w = marine.json()["hourly"], weather.json()["hourly"]

    # keep only the hours from now until the end of the trip window
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = now + timedelta(hours=TRIP_HOURS)

    def window(times, values):
        out = []
        for t, v in zip(times, values):
            ts = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
            if now <= ts < end and v is not None:
                out.append((ts, v))
        return out

    waves = window(m["time"], m["wave_height"])
    winds = window(w["time"], w["wind_speed_10m"])
    gusts = window(w["time"], w["wind_gusts_10m"])
    rain = window(w["time"], w["precipitation_probability"])
    if not waves or not gusts:
        raise ValueError("no forecast data for this zone right now")

    peak_gust_time, peak_gust = max(gusts, key=lambda p: p[1])
    return {
        "wave_now": waves[0][1],
        "wave_max": max(v for _, v in waves),
        "wind_now": winds[0][1] if winds else 0,
        "gust_max": peak_gust,
        "gust_peak_at": peak_gust_time.astimezone(IST).strftime("%I %p").lstrip("0"),
        "rain_max": max((v for _, v in rain), default=0),
    }


# ---------- tools ----------

@server.tool()
async def get_sea_briefing(zone: str = "", user: str = "") -> str:
    """Spoken sea-safety briefing for a fishing zone: waves, wind, rain and a
    trip-risk verdict for the next 12 hours. Give a zone name, or a user name
    whose zone was saved with save_my_zone."""
    z = resolve_zone(zone, user)
    if not z:
        return unknown_zone_message(zone, user)
    try:
        c = await fetch_conditions(z)
    except Exception:
        return f"Sorry, I couldn't get the sea forecast for {z['name']} right now. Please try again in a minute."

    level, reason = assess(c["wave_max"], c["gust_max"])
    rain = (f"Rain chance up to {c['rain_max']:.0f} percent."
            if c["rain_max"] >= 30 else "Little chance of rain.")
    return (
        f"Sea briefing for {z['name']}. "
        f"Waves are {c['wave_now']:.1f} metres now, up to {c['wave_max']:.1f} metres in the next {TRIP_HOURS} hours. "
        f"Wind is {c['wind_now']:.0f} km/h, with gusts up to {c['gust_max']:.0f} km/h around {c['gust_peak_at']}. "
        f"{rain} "
        f"Trip risk: {level}, because of {reason}."
    )


@server.tool()
async def check_trip_risk(zone: str = "", user: str = "") -> str:
    """Quick go / no-go check for a fishing trip in the next 12 hours.
    Returns Safe, Caution or Don't go, with the one reason that decided it."""
    z = resolve_zone(zone, user)
    if not z:
        return unknown_zone_message(zone, user)
    try:
        c = await fetch_conditions(z)
    except Exception:
        return f"Sorry, I couldn't check conditions for {z['name']} right now. Please try again in a minute."

    level, reason = assess(c["wave_max"], c["gust_max"])
    advice = {
        "Safe": "Conditions look fine for a trip.",
        "Caution": "Go only if you must, stay close to shore, and keep checking.",
        "Don't go": "Please stay ashore today.",
    }[level]
    return f"{level} for {z['name']}: {reason} expected in the next {TRIP_HOURS} hours. {advice}"


@server.tool()
async def save_my_zone(user: str, zone: str) -> str:
    """Remember a user's usual fishing zone, so later briefings need no zone."""
    z = find_zone(zone)
    if not z:
        return f"I don't know the zone '{zone}'. I know: {zone_names()}."
    users = load_users()
    users[user.strip().lower()] = z["name"]
    save_users(users)
    return f"Got it, {user}. Your usual zone is {z['name']}. Ask me for your sea briefing any time."


if __name__ == "__main__":
    server.run()
