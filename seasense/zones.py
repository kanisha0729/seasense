"""Preset fishing zones along the Tamil Nadu coast.

Each point is a little offshore, because the marine API returns
empty wave data for points on land.
"""

ZONES = {
    "chennai": {
        "lat": 13.08, "lon": 80.35,
        "names": {"en": "Chennai coast", "ta": "சென்னை கடற்கரை", "hi": "चेन्नई तट"},
    },
    "nagapattinam": {
        "lat": 10.77, "lon": 79.90,
        "names": {"en": "Nagapattinam", "ta": "நாகப்பட்டினம்", "hi": "नागपट्टिनम"},
    },
    "rameswaram": {
        "lat": 9.25, "lon": 79.40,
        "names": {"en": "Rameswaram", "ta": "ராமேஸ்வரம்", "hi": "रामेश्वरम"},
    },
    "thoothukudi": {
        "lat": 8.75, "lon": 78.25,
        "names": {"en": "Thoothukudi", "ta": "தூத்துக்குடி", "hi": "थूथुकुडी"},
    },
    "kanyakumari": {
        "lat": 7.95, "lon": 77.55,
        "names": {"en": "Kanyakumari", "ta": "கன்னியாகுமரி", "hi": "कन्याकुमारी"},
    },
}


def find_zone_key(text: str) -> str | None:
    """Match what the user said, in any supported language, to a zone key."""
    said = (text or "").strip().lower()
    if not said:
        return None
    for key, zone in ZONES.items():
        names = [key] + [n.lower() for n in zone["names"].values()]
        if any(n in said or said in n for n in names):
            return key
    return None


def zone_name(key: str, lang: str = "en") -> str:
    return ZONES[key]["names"].get(lang, ZONES[key]["names"]["en"])


def zone_list(lang: str = "en") -> str:
    return ", ".join(zone_name(k, lang) for k in ZONES)
