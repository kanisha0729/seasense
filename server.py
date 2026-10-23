"""SeaSense MCP server: what Alexa+ (or any MCP client) talks to.

Tools:
  get_sea_briefing  - waves, wind and rain for a zone, as a short spoken briefing
  check_trip_risk   - Safe / Caution / Don't go for the next 12 hours
  find_best_time    - the safest time to set out in the next 24 hours
  save_my_zone      - remembers a user's usual zone and language
  start_trip        - "I'm going to sea, back by 2 PM" (records conditions at departure)
  end_trip          - "I'm back"
  check_on_trip     - for family: at sea / overdue (+ Coast Guard 1554) / back,
                      and a warning if the sea has got worse since departure

Languages: English (en), Tamil (ta), Hindi (hi).
Live data: Open-Meteo Marine + Forecast APIs. Logic lives in seasense_core.py.
"""

import argparse
import logging

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

import seasense_core as core
from i18n import TEXT, normalize_lang, t
from zones import find_zone_key, zone_list, zone_name

logging.getLogger("httpx").setLevel(logging.WARNING)  # hide per-request log lines
log = logging.getLogger("seasense")  # logs go to stderr, never into the MCP stdio stream

# Hints for the client (Alexa+): read-only tools can run without asking the user to confirm.
READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(read_only_hint=False, idempotent_hint=True)
WRITE_NEW = ToolAnnotations(read_only_hint=False, idempotent_hint=False, open_world_hint=True)

server = MCPServer(
    "SeaSense",
    instructions=(
        "Sea-safety briefings for coastal fishermen in Tamil Nadu, in English, Tamil or Hindi. "
        "Pass language='ta' for Tamil or 'hi' for Hindi when the user speaks that language. "
        "When someone says they are going fishing, call start_trip; when they are back, end_trip. "
        "When a family member asks whether someone is back, call check_on_trip. "
        "Read the tool output aloud exactly as it is; it is written to be spoken."
    ),
)


def _resolve(zone: str, user: str, language: str) -> tuple[str | None, str, str | None]:
    """Work out (zone_key, lang, error_message) from what the user gave."""
    saved = core.get_user(user) if user else None
    lang = normalize_lang(language) if language else (saved or {}).get("lang", "en")
    if zone:
        key = find_zone_key(zone)
        if not key:
            return None, lang, t(lang, "unknown_zone", zone=zone, zones=zone_list(lang))
        return key, lang, None
    if saved:
        return saved["zone"], lang, None
    if user:
        return None, lang, t(lang, "no_saved_zone", user=user, zones=zone_list(lang))
    return None, lang, t(lang, "unknown_zone", zone="", zones=zone_list(lang))


@server.tool(annotations=READ)
async def get_sea_briefing(zone: str = "", user: str = "", language: str = "") -> str:
    """Spoken sea-safety briefing for a fishing zone: waves, wind, rain and a
    trip-risk verdict for the next 12 hours, from the live forecast.
    zone: Chennai, Nagapattinam, Rameswaram, Thoothukudi or Kanyakumari (any language).
    user: a name saved with save_my_zone, used when no zone is given.
    language: 'en', 'ta' (Tamil) or 'hi' (Hindi); defaults to the user's saved language."""
    key, lang, error = _resolve(zone, user, language)
    if error:
        return error
    try:
        return await _with_trip_warning(user, lang, (await core.get_report(key, lang))["briefing"])
    except core.ForecastError:
        log.exception("forecast fetch failed for %s", key)
        return t(lang, "fetch_failed", zone=zone_name(key, lang))


async def _with_trip_warning(user: str, lang: str, text: str) -> str:
    """If this user is at sea and the sea got worse since they left, say that first."""
    trip = core.get_trip(user) if user else None
    if trip and trip["status"] == "at_sea":
        status = await core.trip_status(trip, lang)
        if status["worsened"]:
            return f"{status['warning']} {text}"
    return text


@server.tool(annotations=READ)
async def check_trip_risk(zone: str = "", user: str = "", language: str = "") -> str:
    """Quick go / no-go check for a fishing trip in the next 12 hours, from the
    live forecast. Returns Safe, Caution or Don't go with the reason.
    Same arguments as get_sea_briefing."""
    key, lang, error = _resolve(zone, user, language)
    if error:
        return error
    try:
        return await _with_trip_warning(user, lang, (await core.get_report(key, lang))["risk"])
    except core.ForecastError:
        log.exception("forecast fetch failed for %s", key)
        return t(lang, "fetch_failed", zone=zone_name(key, lang))


@server.tool(annotations=READ)
async def find_best_time(zone: str = "", user: str = "", language: str = "") -> str:
    """The safest time to set out in the next 24 hours, e.g. 'Don't go now, but
    4 AM to 9 AM tomorrow should be safe'. Same arguments as get_sea_briefing."""
    key, lang, error = _resolve(zone, user, language)
    if error:
        return error
    try:
        return (await core.best_window(key, lang))["text"]
    except core.ForecastError:
        log.exception("forecast fetch failed for %s", key)
        return t(lang, "fetch_failed", zone=zone_name(key, lang))


@server.tool(annotations=WRITE_NEW)
async def start_trip(user: str, back_by: str, zone: str = "", language: str = "") -> str:
    """Log that a fisherman is going to sea, so family can check on them.
    back_by: when they expect to return, e.g. '2 PM', '14:00' or '8 hours'.
    zone: defaults to the user's saved zone."""
    if not user.strip():
        return t(normalize_lang(language), "need_name")
    key, lang, error = _resolve(zone, user, language)
    if error:
        return error
    when = core.parse_back_by(back_by)
    if not when:
        return t(lang, "bad_back_by")
    try:
        trip = await core.start_trip(user, key, when)
    except core.ForecastError:
        log.exception("forecast fetch failed for %s", key)
        return t(lang, "fetch_failed", zone=zone_name(key, lang))
    return t(lang, "trip_started", user=trip["name"], zone=zone_name(key, lang),
             back=core._when(trip["back_by"], lang), level=TEXT[lang]["level"][trip["at_start"]["level"]])


@server.tool(annotations=WRITE)
async def end_trip(user: str, language: str = "") -> str:
    """Mark that a fisherman is safely back on shore."""
    if not user.strip():
        return t(normalize_lang(language), "need_name")
    lang = normalize_lang(language) if language else (core.get_user(user) or {}).get("lang", "en")
    trip = core.end_trip(user)
    return t(lang, "trip_ended", user=trip["name"]) if trip else t(lang, "no_trip", user=user)


@server.tool(annotations=READ)
async def check_on_trip(user: str, language: str = "") -> str:
    """For family at home: is this fisherman back yet? Says whether they are at sea,
    overdue (with the Coast Guard number) or back, and warns if the sea has got
    worse since they left."""
    if not user.strip():
        return t(normalize_lang(language), "need_name")
    lang = normalize_lang(language) if language else (core.get_user(user) or {}).get("lang", "en")
    trip = core.get_trip(user)
    if not trip:
        return t(lang, "no_trip", user=user)
    status = await core.trip_status(trip, lang)
    return f"{status['text']} {status['warning']}".strip()


@server.tool(annotations=WRITE)
async def save_my_zone(user: str, zone: str, language: str = "en") -> str:
    """Remember a user's usual fishing zone and language, so later briefings
    need only their name."""
    lang = normalize_lang(language)
    if not user.strip():
        return t(lang, "need_name")
    key = find_zone_key(zone)
    if not key:
        return t(lang, "unknown_zone", zone=zone, zones=zone_list(lang))
    core.save_user(user, key, lang)
    return t(lang, "saved", user=user, zone=zone_name(key, lang))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SeaSense MCP server.")
    parser.add_argument("--http", action="store_true",
                        help="serve over Streamable HTTP (for Alexa+ and remote clients) instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.http:
        # Streamable HTTP endpoint (MCP spec 2025-11-25): http://<host>:<port>/mcp
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        print(f"SeaSense MCP server (Streamable HTTP) at http://{args.host}:{args.port}/mcp  (Ctrl+C to stop)")
        server.run("streamable-http", host=args.host, port=args.port)
    else:
        server.run()  # stdio, for MCP Inspector and Claude Desktop
