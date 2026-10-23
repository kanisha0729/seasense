# SeaSense

**Spoken sea-safety briefings for coastal fishermen, as an MCP server for Alexa+.**

Fishermen on the Tamil Nadu coast often leave harbour before dawn, and sea conditions can change within hours. SeaSense turns free wave and weather forecasts into short briefings meant to be read aloud, plus a plain go / no-go answer for the next 12 hours.

> ⚠️ **Not official guidance.** The risk levels use starter thresholds we chose for this hackathon demo. They are not IMD or INCOIS guidance and must not be used as the only basis for a decision to go to sea.

## Tools

| Tool | What it does |
| --- | --- |
| `get_sea_briefing(zone, user)` | Waves now and the max over the next 12 hours, wind, peak gust and when it hits, rain chance, and a trip-risk verdict. |
| `check_trip_risk(zone, user)` | Quick verdict for the next 12 hours: **Safe**, **Caution** or **Don't go**, with the reason that decided it. |
| `save_my_zone(user, zone)` | Remembers a user's usual zone, so later they can just ask for "my briefing". |

For the first two tools, pass either a `zone` or a `user` whose zone was saved. Read-only tools are marked `read_only_hint` so a client can call them without asking for confirmation.

Example output:

```
Sea briefing for Rameswaram. Waves are 0.8 metres now, up to 1.1 metres in the next 12 hours.
Wind is 14 km/h, with gusts up to 26 km/h around 3 PM. Little chance of rain.
Trip risk: Safe, because of waves under 1.5 metres and gusts under 30 km/h.
```
*(Illustrative format. Live numbers come from the current forecast.)*

## Zones

Chennai coast, Nagapattinam, Rameswaram, Thoothukudi, Kanyakumari.

Each zone is a fixed point a little offshore, because the marine API returns no wave data for points on land. Partial names work too (`rames` matches Rameswaram).

## Risk rules

The verdict uses the **worst** wave height and gust in the next 12 hours:

| Level | Rule |
| --- | --- |
| Safe | waves under 1.5 m **and** gusts under 30 km/h |
| Caution | waves 1.5–2.5 m **or** gusts 30–45 km/h |
| Don't go | waves over 2.5 m **or** gusts over 45 km/h |

The thresholds live in `risk.py` so they're easy to replace with validated values.

## Setup

Requires Python 3.10+.

**Windows (PowerShell)**
```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # only if activation is blocked
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No API keys are needed.

## Run

**Streamable HTTP** (the transport Alexa+ uses):
```bash
python server.py --http                 # serves http://127.0.0.1:8000/mcp
python server.py --http --port 9000     # pick another port
```

**stdio, with MCP Inspector** (how we tested):
```bash
npx @modelcontextprotocol/inspector .venv/Scripts/python.exe server.py   # Windows
npx @modelcontextprotocol/inspector .venv/bin/python server.py           # macOS / Linux
```
Or point the Inspector at the HTTP URL above using its "Streamable HTTP" option.

**Claude Desktop** — add this to `claude_desktop_config.json` (use your own absolute paths):
```json
{
  "mcpServers": {
    "seasense": {
      "command": "C:\\path\\to\\seasense\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\seasense\\server.py"]
    }
  }
}
```

## Tests

```bash
pip install pytest
python -m pytest tests
```
The tests cover the risk rules (including the exact boundaries) and zone matching. They don't need the network.

## How it works

```
Alexa+ / MCP client ──► server.py (MCP, 3 tools)
                           ├─ zones.py   zone name → offshore lat/lon
                           ├─ Open-Meteo Marine API     wave height
                           ├─ Open-Meteo Forecast API   wind, gusts, rain chance
                           └─ risk.py    worst 12 h → Safe / Caution / Don't go
```
The two API calls run in parallel with `httpx`. If either fails, the tool returns a short spoken apology instead of an error, and the failure is logged to stderr. Saved zones are kept in `data/users.json` (local to the machine, not committed).

## Why we demo outside Alexa+

Alexa+ isn't available to us in India, so we tested with MCP Inspector and Claude Desktop. The server speaks standard MCP over Streamable HTTP, the protocol Alexa+ integrations use.

## What's next

- Tamil-language briefings
- SMS alerts for fishermen without smart speakers
- More zones along the Tamil Nadu and Kerala coasts
- Replace the starter thresholds with values checked against IMD / INCOIS ocean-state warnings and feedback from fishermen

## Data and license

Weather and marine data from [Open-Meteo](https://open-meteo.com/) (free, no key; see their terms for attribution). Code under the MIT License, see `LICENSE`.
