"""Offline tests for the risk rules and zone matching (no network).

Written by Deva; adapted to the current risk/zones API so they run with
`python -m unittest discover tests` (pytest works too).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from risk import assess  # noqa: E402
from zones import find_zone_key  # noqa: E402


class RiskThresholds(unittest.TestCase):
    def test_safe(self):
        self.assertEqual(assess(1.0, 20)[0], "safe")

    def test_caution_from_waves(self):
        self.assertEqual(assess(1.5, 20)[0], "caution")

    def test_caution_from_gusts(self):
        self.assertEqual(assess(1.0, 30)[0], "caution")

    def test_dont_go_from_waves(self):
        self.assertEqual(assess(2.6, 20)[0], "danger")

    def test_dont_go_from_gusts(self):
        self.assertEqual(assess(1.0, 46)[0], "danger")

    def test_boundaries_stay_caution(self):
        self.assertEqual(assess(2.5, 45)[0], "caution")


class ZoneMatching(unittest.TestCase):
    def test_zone_matching(self):
        self.assertEqual(find_zone_key("Rameswaram"), "rameswaram")
        self.assertEqual(find_zone_key("chennai coast"), "chennai")
        self.assertEqual(find_zone_key("  KANYAKUMARI "), "kanyakumari")
        self.assertEqual(find_zone_key("rames"), "rameswaram")
        self.assertEqual(find_zone_key("ராமேஸ்வரம்"), "rameswaram")      # Tamil
        self.assertEqual(find_zone_key("कन्याकुमारी"), "kanyakumari")     # Hindi

    def test_unknown_zones(self):
        self.assertIsNone(find_zone_key(""))
        self.assertIsNone(find_zone_key("a"))
        self.assertIsNone(find_zone_key("Mumbai"))


if __name__ == "__main__":
    unittest.main()
