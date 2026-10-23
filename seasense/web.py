"""SeaSense web app: sign-in, then a visual, spoken dashboard on the live backend.

Run:   python web.py
Open:  http://127.0.0.1:8080

Pages:
  /login   sign in or create an account (name + 4-6 digit PIN)
  /        dashboard (needs sign-in)

API (all JSON; requests that change data must send Content-Type: application/json):
  POST   /api/signup   {name, pin, zone, lang}
  POST   /api/login    {name, pin}            5 wrong PINs -> name locked 10 min (429)
  POST   /api/logout
  GET    /api/me                              -> {name, zone, lang}
  PATCH  /api/me       {zone?, lang?}         save zone / language
  POST   /api/me/pin   {pin, new_pin}         change PIN
  DELETE /api/me       {pin}                  delete account and all sessions
  GET    /api/zones
  GET    /api/report?zone=rameswaram&lang=ta  live report (needs sign-in)
  GET    /api/best?zone=...&lang=...          safest time to go in the next 24 h
  GET    /api/trip                            my current trip (or null)
  POST   /api/trip     {zone?, back_by, lang} start a trip ("2 PM", "14:00", "8 hours")
  POST   /api/trip/end                        I'm back
  GET    /trip/<token>                        family page for a shared trip link (no sign-in)
  GET    /api/family/<token>?lang=ta          that trip's status as JSON
  GET    /board?lang=ta                       harbour board: every zone on one screen (Fire TV)
  GET    /api/board?lang=ta
  GET    /healthz

The account is the same profile the voice tools use, so a zone saved here is
what Alexa+ uses when the same person asks by name.

Settings (environment variables, all optional):
  SEASENSE_HOST  default 127.0.0.1
  SEASENSE_PORT  default 8080
  SEASENSE_HTTPS set to 1 when served over HTTPS, so the session cookie is Secure
"""

import json
import logging
import os
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

import seasense_core as core
from i18n import LANGS, normalize_lang, t
from zones import ZONES, find_zone_key, zone_list, zone_name

logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("seasense")
STATIC = Path(__file__).parent / "static"
COOKIE = "seasense_session"
HTTPS = os.environ.get("SEASENSE_HTTPS") == "1"

CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; "
       "img-src 'self' data:; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


class JsonOnlyWrites(BaseHTTPMiddleware):
    """Requests that change data must be JSON. A plain HTML form on another site
    can't send JSON without the browser asking permission first, so this blocks
    cross-site request forgery (on top of the SameSite cookie)."""
    async def dispatch(self, request, call_next):
        if request.method in ("POST", "PATCH", "DELETE") and request.url.path.startswith("/api/") \
                and request.url.path != "/api/logout":
            if not request.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse({"error": "json_required"}, status_code=415)
        return await call_next(request)


async def read_json(request: Request) -> dict:
    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def current_user(request: Request) -> dict | None:
    name = core.session_user(request.cookies.get(COOKIE))
    return core.get_user(name) if name else None


def signed_in(response: JSONResponse, name: str) -> JSONResponse:
    response.set_cookie(COOKIE, core.new_session(name), max_age=core.SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", secure=HTTPS)
    return response


def pin_ok(pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 6


# ---------- pages ----------

async def home(request: Request):
    if not current_user(request):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(STATIC / "index.html")


async def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=302)
    return FileResponse(STATIC / "login.html")


async def favicon(request: Request):
    return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")


async def healthz(request: Request):
    return JSONResponse({"ok": True})


# ---------- account API ----------

async def signup(request: Request):
    body = await read_json(request)
    name, pin = " ".join(str(body.get("name", "")).split()), str(body.get("pin", "")).strip()
    zone_key = find_zone_key(str(body.get("zone", "")))
    lang = normalize_lang(body.get("lang"))
    error = core.validate_new_account(name, pin) or (None if zone_key else "bad_zone")
    if error:
        return JSONResponse({"error": error}, status_code=400)
    if not core.create_account(name, pin, zone_key, lang):
        return JSONResponse({"error": "name_taken"}, status_code=400)
    return signed_in(JSONResponse(core.get_user(name)), name)


async def login(request: Request):
    body = await read_json(request)
    name, pin = str(body.get("name", "")).strip(), str(body.get("pin", "")).strip()
    wait = core.login_locked_for(name)
    if wait:
        return JSONResponse({"error": "too_many", "retry_after": wait}, status_code=429,
                            headers={"Retry-After": str(wait)})
    if not core.check_login(name, pin):
        core.record_failure(name)
        return JSONResponse({"error": "bad_login"}, status_code=401)
    core.clear_failures(name)
    return signed_in(JSONResponse(core.get_user(name)), name)


async def logout(request: Request):
    core.end_session(request.cookies.get(COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE)
    return response


async def me(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "signed_out"}, status_code=401)

    if request.method == "PATCH":
        body = await read_json(request)
        zone_key = find_zone_key(str(body.get("zone", ""))) or user["zone"]
        lang = normalize_lang(body.get("lang")) if body.get("lang") else user["lang"]
        core.save_user(user["name"], zone_key, lang)
        return JSONResponse(core.get_user(user["name"]))

    if request.method == "DELETE":
        body = await read_json(request)
        if not core.check_login(user["name"], str(body.get("pin", ""))):
            return JSONResponse({"error": "wrong_pin"}, status_code=403)
        core.delete_account(user["name"])
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE)
        return response

    return JSONResponse(user)


async def change_pin(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "signed_out"}, status_code=401)
    body = await read_json(request)
    old, new = str(body.get("pin", "")), str(body.get("new_pin", ""))
    if not core.check_login(user["name"], old):
        return JSONResponse({"error": "wrong_pin"}, status_code=403)
    if not pin_ok(new):
        return JSONResponse({"error": "bad_pin"}, status_code=400)
    core.change_pin(user["name"], new)
    return JSONResponse({"ok": True})


# ---------- data API ----------

async def zones(request: Request):
    return JSONResponse({
        "languages": LANGS,
        "zones": [{"key": k, "names": z["names"], "lat": z["lat"], "lon": z["lon"]} for k, z in ZONES.items()],
    })


async def report(request: Request):
    if not current_user(request):
        return JSONResponse({"error": "signed_out"}, status_code=401)
    lang = normalize_lang(request.query_params.get("lang"))
    said = request.query_params.get("zone", "")
    key = find_zone_key(said)
    if not key:
        return JSONResponse({"error": t(lang, "unknown_zone", zone=said[:40], zones=zone_list(lang))},
                            status_code=400)
    try:
        return JSONResponse(await core.get_report(key, lang))
    except core.ForecastError as exc:
        log.warning("forecast failed for %s: %s", key, exc)
        return JSONResponse({"error": t(lang, "fetch_failed", zone=zone_name(key, lang))}, status_code=502)


# ---------- feature: best time to go ----------

async def best(request: Request):
    if not current_user(request):
        return JSONResponse({"error": "signed_out"}, status_code=401)
    lang = normalize_lang(request.query_params.get("lang"))
    key = find_zone_key(request.query_params.get("zone", ""))
    if not key:
        return JSONResponse({"error": "bad_zone"}, status_code=400)
    try:
        return JSONResponse(await core.best_window(key, lang))
    except core.ForecastError:
        return JSONResponse({"error": t(lang, "fetch_failed", zone=zone_name(key, lang))}, status_code=502)


# ---------- feature: trip check-in ----------

async def trip(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "signed_out"}, status_code=401)

    if request.method == "POST":
        body = await read_json(request)
        lang = normalize_lang(body.get("lang"))
        key = find_zone_key(str(body.get("zone", ""))) or user["zone"]
        when = core.parse_back_by(str(body.get("back_by", "")))
        if not when:
            return JSONResponse({"error": t(lang, "bad_back_by")}, status_code=400)
        try:
            await core.start_trip(user["name"], key, when)
        except core.ForecastError:
            return JSONResponse({"error": t(lang, "fetch_failed", zone=zone_name(key, lang))}, status_code=502)

    lang = normalize_lang(request.query_params.get("lang") or user["lang"])
    current = core.get_trip(user["name"])
    if not current:
        return JSONResponse({"trip": None})
    return JSONResponse({"trip": await core.trip_status(current, lang)})


async def trip_end(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "signed_out"}, status_code=401)
    core.end_trip(user["name"])
    current = core.get_trip(user["name"])
    lang = normalize_lang(request.query_params.get("lang") or user["lang"])
    return JSONResponse({"trip": await core.trip_status(current, lang) if current else None})


async def family_page(request: Request):
    if not core.trip_by_token(request.path_params["token"]):
        return await not_found(request, HTTPException(404))
    return FileResponse(STATIC / "family.html")


async def family_api(request: Request):
    """Public, but only for whoever holds the unguessable link the fisherman shared."""
    found = core.trip_by_token(request.path_params["token"])
    if not found:
        return JSONResponse({"error": "not_found"}, status_code=404)
    status = await core.trip_status(found, normalize_lang(request.query_params.get("lang")))
    status.pop("token", None)
    return JSONResponse(status)


# ---------- feature: harbour board (Fire TV / any big screen) ----------

async def board_page(request: Request):
    return FileResponse(STATIC / "board.html")


async def board_api(request: Request):
    lang = normalize_lang(request.query_params.get("lang"))
    return JSONResponse({"zones": await core.board(lang), "lang": lang})


# ---------- errors ----------

async def not_found(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "not_found"}, status_code=404)
    return HTMLResponse((STATIC / "404.html").read_text(encoding="utf-8"), status_code=404)


async def method_not_allowed(request: Request, exc: HTTPException):
    return JSONResponse({"error": "method_not_allowed"}, status_code=405)


async def server_error(request: Request, exc: Exception):
    log.exception("unexpected error on %s", request.url.path)
    return JSONResponse({"error": "server_error"}, status_code=500)


app = Starlette(
    routes=[
        Route("/", home),
        Route("/login", login_page),
        Route("/favicon.svg", favicon),
        Route("/favicon.ico", favicon),
        Route("/healthz", healthz),
        Route("/api/signup", signup, methods=["POST"]),
        Route("/api/login", login, methods=["POST"]),
        Route("/api/logout", logout, methods=["POST"]),
        Route("/api/me", me, methods=["GET", "PATCH", "DELETE"]),
        Route("/api/me/pin", change_pin, methods=["POST"]),
        Route("/api/zones", zones),
        Route("/api/report", report),
        Route("/api/best", best),
        Route("/api/trip", trip, methods=["GET", "POST"]),
        Route("/api/trip/end", trip_end, methods=["POST"]),
        Route("/trip/{token}", family_page),
        Route("/api/family/{token}", family_api),
        Route("/board", board_page),
        Route("/api/board", board_api),
    ],
    middleware=[Middleware(SecurityHeaders), Middleware(JsonOnlyWrites)],
    exception_handlers={404: not_found, 405: method_not_allowed, 500: server_error},
)

if __name__ == "__main__":
    host = os.environ.get("SEASENSE_HOST", "127.0.0.1")
    port = int(os.environ.get("SEASENSE_PORT", "8080"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"SeaSense is running at http://{host}:{port}  (press Ctrl+C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
