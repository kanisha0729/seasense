"""Offline tests for the risk rules and zone matching (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from risk import assess  # noqa: E402
from zones import find_zone  # noqa: E402


def test_safe():
    assert assess(1.0, 20)[0] == "Safe"


def test_caution_from_waves():
    assert assess(1.5, 20)[0] == "Caution"


def test_caution_from_gusts():
    assert assess(1.0, 30)[0] == "Caution"


def test_dont_go_from_waves():
    assert assess(2.6, 20)[0] == "Don't go"


def test_dont_go_from_gusts():
    assert assess(1.0, 46)[0] == "Don't go"


def test_boundaries_stay_caution():
    assert assess(2.5, 45)[0] == "Caution"


def test_zone_matching():
    assert find_zone("Rameswaram")["name"] == "Rameswaram"
    assert find_zone("chennai coast")["name"] == "Chennai coast"
    assert find_zone("  KANYAKUMARI ")["name"] == "Kanyakumari"
    assert find_zone("rames")["name"] == "Rameswaram"


def test_unknown_zones():
    assert find_zone("") is None
    assert find_zone("a") is None
    assert find_zone("Mumbai") is None
