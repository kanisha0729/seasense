# SeaSense

**Spoken sea-safety briefings for coastal fishermen, in English, Tamil and Hindi.**

SeaSense tells a fisherman the waves, wind and rain for his usual fishing zone over the next 12 hours, and says plainly whether it's **Safe**, **Caution** or **Don't go**. It uses the live forecast, remembers each user's zone and language, and speaks the answer aloud.

Built for the Build, Ship, Shape: Amazon Developer Hackathon (Alexa+ track).

## How it works

```
 Alexa+ / any MCP client ──► server.py (MCP server, 3 tools) ─┐
                                                              ├──► seasense_core.py ──► Open-Meteo Marine + Forecast APIs (live)
 Web browser ─────────────► web.py (web app + JSON API) ──────┘        │
                                                                       ├── risk.py   Safe / Caution / Don't go rules
                                                                       ├── i18n.py   English, Tamil, Hindi text
                                                                       └── zones.py  5 Tamil Nadu fishing zones
```

- **Backend:** `seasense_core.py` fetches the live forecast for the next 12 hours, works out the trip risk and writes the spoken text. Both front ends use it, so they always agree.
- **Voice front end:** `server.py` is an MCP server. Alexa+ (or Claude Desktop, or MCP Inspector) calls its tools.
- **Visual front end:** `web.py` serves a web app with a risk card, live metrics, 12-hour charts and a **Listen** button that reads the briefing aloud in the chosen language.
- **One account, two front ends:** users sign in with their name and a 4 to 6 digit PIN (stored as a salted PBKDF2 hash). Their zone and language are one profile: set it on the web, and Alexa+ uses it when the same person asks by name, and the reverse.

## What makes SeaSense different

| Feature | What it does | Where |
| --- | --- | --- |
| **Best time to go** | Searches the next 24 hours for the earliest window of at least 3 safe hours: "Don't go now, but 4:30 to 9:30 AM tomorrow should be safe." If there's no safe window, it names the calmest Caution stretch or says to stay ashore. | Voice + dashboard (24-hour colour strip) |
| **Trip check-in for family** | "I'm going to Rameswaram, back by 2 PM." Family can ask Alexa "Is Murugan back?" or open a private link. Once the trip is overdue, they're told to call first, then the **Coast Guard on 1554** (toll-free search and rescue). | Voice + dashboard + family page `/trip/<link>` |
| **Worse-weather warning** | Records the sea at departure. If waves rise 0.5 m or more, gusts rise 10 km/h or more, or the risk level goes up, every later check warns: "Conditions have worsened since you left." | Voice + dashboard + family page |
| **Harbour board** | Every zone on one TV screen with verdict, waves, gusts and best time. Rotates English, Tamil and Hindi every 20 s and refreshes every 10 min. Built for a harbour office or fishing co-op TV, in any TV or desktop browser, with no remote needed. | `/board` (`/board?lang=ta` pins one language) |

## MCP tools

| Tool | What it does |
| --- | --- |
| `get_sea_briefing(zone, user, language)` | Full spoken briefing: waves, wind, gusts, rain, and the trip-risk verdict |
| `check_trip_risk(zone, user, language)` | Quick go / no-go with the one reason that decided it |
| `find_best_time(zone, user, language)` | The safest time to set out in the next 24 hours |
| `save_my_zone(user, zone, language)` | Remembers a user's usual zone and language |
| `start_trip(user, back_by, zone, language)` | Logs a trip ("2 PM", "14:00", "8 hours") and records the sea at departure |
| `end_trip(user, language)` | "I'm back" |
| `check_on_trip(user, language)` | For family: at sea / overdue (with Coast Guard 1554) / back, plus a worse-weather warning |

`language` accepts `en`, `ta` (Tamil) or `hi` (Hindi). Zone names work in any of the three languages, for example `Rameswaram`, `ராமேஸ்வரம்` or `रामेश्वरम`.

## Run it (Windows PowerShell)

```powershell
cd seasense
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
pip install "mcp[cli]" httpx
```

**Web app:**
```powershell
python web.py
```
Then open http://127.0.0.1:8080, create an account, and you're on the dashboard. For Tamil and Hindi voices, use Microsoft Edge, which includes natural Indian-language voices.

Accounts and sessions are stored in `data/`, which is git-ignored.

**MCP server for Alexa+ (MCP spec 2025-11-25, Streamable HTTP):**
```powershell
python server.py
```
It serves MCP at **http://127.0.0.1:8000/mcp**. To test it, open MCP Inspector in a second window:
```powershell
npx @modelcontextprotocol/inspector
```
In the Inspector, choose transport **Streamable HTTP**, enter `http://127.0.0.1:8000/mcp`, and click **Connect**. Use `python server.py --stdio` for stdio clients such as Claude Desktop.

Run `web.py` and `server.py` at the same time: they share the same accounts, saved zones and trips.

## Tests

```powershell
python -m unittest discover tests -v
```

25 automated tests, no internet needed (the forecast is replaced with fixed sample data). They cover the risk rules, reports in all 3 languages, voice tools sharing the web profile, sign-up validation, the full account flow, best-time windows, trip check-in and overdue alerts, the worse-weather warning, family links, the harbour board, PIN brute-force lockout, change PIN, delete account, damaged-file recovery, forecast failure, security headers and cookies, and 404s.

## Security

- PINs are stored only as salted PBKDF2-SHA256 hashes (200,000 rounds), never as plain text.
- 5 wrong PINs within 10 minutes lock that name for 10 minutes (HTTP 429).
- Session cookie is `HttpOnly` and `SameSite=Lax`. Set `SEASENSE_HTTPS=1` when serving over HTTPS to make it `Secure`.
- Requests that change data must be JSON, which blocks cross-site form attacks.
- Headers: Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy.
- Account files are written atomically. A damaged file is set aside and never silently overwritten.

**Known limits:** lockout is per name, so someone could deliberately lock out another user for 10 minutes. Accounts live in JSON files, which suits a demo but not thousands of users (move to SQLite or Postgres). There's no PIN reset, because there's no email or SMS channel yet. Run behind HTTPS before putting it on the internet.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SEASENSE_HOST` | `127.0.0.1` | Address to listen on |
| `SEASENSE_PORT` | `8080` | Port |
| `SEASENSE_HTTPS` | unset | Set to `1` behind HTTPS so the session cookie is `Secure` |

No API keys or secrets are needed, because Open-Meteo is free and keyless.

## Risk rules

| Level | Waves (next 12 h) | Wind gusts (next 12 h) |
| --- | --- | --- |
| Safe | under 1.5 m | and under 30 km/h |
| Caution | 1.5 to 2.5 m | or 30 to 45 km/h |
| Don't go | over 2.5 m | or over 45 km/h |

> These are starter thresholds for a hackathon demo, **not official IMD guidance**. Always follow IMD and INCOIS warnings before going to sea.

## Zones

Chennai coast, Nagapattinam, Rameswaram, Thoothukudi, Kanyakumari: points a little offshore, because the marine model has no wave data on land.

## Data

Live hourly forecast from [Open-Meteo](https://open-meteo.com/) (Marine API for wave height, Forecast API for wind, gusts and rain chance). It's free and needs no API key. Each forecast is cached for 10 minutes.

## What's next

- Alexa+ skill listing, so fishermen can just ask out loud
- SMS alerts before dawn for phones without data
- Malayalam and Telugu, and more zones along the whole Indian coast
- Official IMD and INCOIS warnings layered on top of the forecast

## License

MIT
