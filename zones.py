"""Preset fishing zones along the Tamil Nadu coast.

Each point is a little offshore, because the marine API returns
empty wave data for points on land.
"""

ZONES = {
    "chennai": {"name": "Chennai coast", "lat": 13.08, "lon": 80.35},
    "nagapattinam": {"name": "Nagapattinam", "lat": 10.77, "lon": 79.90},
    "rameswaram": {"name": "Rameswaram", "lat": 9.25, "lon": 79.40},
    "thoothukudi": {"name": "Thoothukudi", "lat": 8.75, "lon": 78.25},
    "kanyakumari": {"name": "Kanyakumari", "lat": 7.95, "lon": 77.55},
}


def find_zone(text: str) -> dict | None:
    """Match what the user said ("rameswaram", "Chennai coast") to a zone."""
    key = text.strip().lower()
    if not key:
        return None
    for zone_key, zone in ZONES.items():
        if zone_key in key or key in zone_key:
            return zone
    return None


def zone_names() -> str:
    return ", ".join(z["name"] for z in ZONES.values())
