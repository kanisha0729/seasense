"""SeaSense automated tests. No internet needed: the forecast download is replaced
with fixed sample data, and accounts go to a temporary folder.

Run from the project folder:
    python -m unittest discover tests -v
"""

import asyncio
import logging
import math
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import seasense_core as core  # noqa: E402
from risk import assess  # noqa: E402

logging.disable(logging.CRITICAL)   # keep test output readable

# Wave / gust levels per zone chosen to hit every risk level
PROFILE = {"chennai": (0.7, 18), "nagapattinam": (1.1, 26), "rameswaram": (1.4, 33),
           "thoothukudi": (1.9, 41), "kanyakumari": (2.6, 52)}


async def fake_download(zone_key):
    base_w, base_g = PROFILE[zone_key]
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(72)]
    gust = [round(base_g + 5 * math.sin(i / 4), 1) for i in range(72)]
    return {"marine": {"time": times, "wave_height": [base_w] * 72, "wave_period": [7] * 72},
            "weather": {"time": times, "wind_speed_10m": [g * 0.6 for g in gust], "wind_gusts_10m": gust,
                        "precipitation_probability": [20] * 72}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        core.USERS_FILE = Path(self.tmp.name) / "users.json"
        core.SESSIONS_FILE = Path(self.tmp.name) / "sessions.json"
        core.TRIPS_FILE = Path(self.tmp.name) / "trips.json"
        core._download = fake_download
        core._cache.clear()
        core._failures.clear()

    def tearDown(self):
        self.tmp.cleanup()


class RiskRules(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(assess(1.0, 20)[0], "safe")
        self.assertEqual(assess(1.5, 20)[0], "caution")     # 1.5 m is the caution line
        self.assertEqual(assess(1.0, 30)[0], "caution")
        self.assertEqual(assess(2.6, 20)[0], "danger")
        self.assertEqual(assess(1.0, 46)[0], "danger")
        self.assertEqual(assess(2.6, 46)[1], "wave")         # waves are checked first


class Reports(Base):
    def test_report_in_three_languages(self):
        for lang, word in [("en", "Caution"), ("ta", "எச்சரிக்கை"), ("hi", "सावधान")]:
            r = asyncio.run(core.get_report("rameswaram", lang))
            self.assertEqual(r["level"], "caution")
            self.assertIn(word, r["briefing"])
            self.assertEqual(len(r["hours"]), core.TRIP_HOURS)

    def test_failed_download_raises(self):
        async def broken(_):
            raise OSError("network down")
        core._download = broken
        with self.assertRaises(core.ForecastError):
            asyncio.run(core.get_report("chennai", "en"))


class VoiceTools(Base):
    def test_tools_share_profile_with_web_account(self):
        import server
        core.create_account("Murugan", "4321", "kanyakumari", "hi")
        reply = asyncio.run(server.check_trip_risk(user="Murugan"))
        self.assertIn("कन्याकुमारी", reply)                   # web profile used by voice
        asyncio.run(server.save_my_zone("Murugan", "chennai", "en"))
        self.assertTrue(core.check_login("Murugan", "4321"))  # voice update keeps the PIN
        self.assertEqual(core.get_user("murugan")["zone"], "chennai")

    def test_unknown_zone_message(self):
        import server
        self.assertIn("xyz", asyncio.run(server.get_sea_briefing(zone="xyz")))


class Storage(Base):
    def test_damaged_file_is_set_aside_not_crashing(self):
        core.USERS_FILE.write_text("{broken", encoding="utf-8")
        self.assertFalse(core.check_login("anyone", "1234"))
        self.assertTrue(any(p.name.startswith("users.corrupt-") for p in Path(self.tmp.name).iterdir()))

    def test_pin_is_never_stored_plain(self):
        core.create_account("Selvi", "9876", "chennai", "ta")
        self.assertNotIn("9876", core.USERS_FILE.read_text(encoding="utf-8"))


class WebApp(Base):
    def setUp(self):
        super().setUp()
        from starlette.testclient import TestClient
        import web
        self.c = TestClient(web.app)

    def signup(self, name="Murugan", pin="4321", zone="rameswaram", lang="ta"):
        return self.c.post("/api/signup", json={"name": name, "pin": pin, "zone": zone, "lang": lang})

    def test_signed_out_is_sent_to_login(self):
        r = self.c.get("/", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (302, "/login"))
        self.assertEqual(self.c.get("/api/report?zone=chennai").status_code, 401)
        self.assertEqual(self.c.get("/api/me").status_code, 401)

    def test_signup_validation(self):
        self.assertEqual(self.signup(pin="12").json()["error"], "bad_pin")
        self.assertEqual(self.signup(pin="12ab").json()["error"], "bad_pin")
        self.assertEqual(self.signup(name="x").json()["error"], "bad_name")
        self.assertEqual(self.signup(name="<script>").json()["error"], "bad_name")
        self.assertEqual(self.signup(zone="mars").json()["error"], "bad_zone")
        self.assertEqual(self.signup(name="முருகன்").status_code, 200)   # Tamil names allowed

    def test_full_account_flow(self):
        self.assertEqual(self.signup().status_code, 200)
        self.assertEqual(self.c.get("/api/me").json()["zone"], "rameswaram")
        r = self.c.get("/api/report?zone=rameswaram&lang=ta")
        self.assertEqual(r.json()["level"], "caution")
        self.assertEqual(self.c.patch("/api/me", json={"zone": "kanyakumari", "lang": "hi"}).json()["lang"], "hi")
        self.assertEqual(self.signup(name="murugan").json()["error"], "name_taken")   # case-insensitive
        self.c.post("/api/logout")
        self.assertEqual(self.c.get("/api/me").status_code, 401)
        self.assertEqual(self.c.post("/api/login", json={"name": " MURUGAN ", "pin": "4321"}).status_code, 200)

    def test_pin_brute_force_is_locked_out(self):
        self.signup()
        self.c.post("/api/logout")
        codes = [self.c.post("/api/login", json={"name": "Murugan", "pin": f"{i:04d}"}).status_code
                 for i in range(7)]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5:], [429, 429])
        locked = self.c.post("/api/login", json={"name": "Murugan", "pin": "4321"})  # even the right PIN
        self.assertEqual(locked.status_code, 429)
        self.assertIn("Retry-After", locked.headers)

    def test_change_pin(self):
        self.signup()
        self.assertEqual(self.c.post("/api/me/pin", json={"pin": "0000", "new_pin": "5555"}).status_code, 403)
        self.assertEqual(self.c.post("/api/me/pin", json={"pin": "4321", "new_pin": "55"}).status_code, 400)
        self.assertEqual(self.c.post("/api/me/pin", json={"pin": "4321", "new_pin": "5555"}).status_code, 200)
        self.assertTrue(core.check_login("Murugan", "5555"))
        self.assertFalse(core.check_login("Murugan", "4321"))

    def test_delete_account(self):
        self.signup()
        self.assertEqual(self.c.request("DELETE", "/api/me", json={"pin": "0000"}).status_code, 403)
        self.assertEqual(self.c.request("DELETE", "/api/me", json={"pin": "4321"}).status_code, 200)
        self.assertIsNone(core.get_user("Murugan"))
        self.assertEqual(self.c.get("/api/me").status_code, 401)            # session gone too

    def test_forecast_failure_is_a_clean_error(self):
        self.signup()
        async def broken(_):
            raise OSError("network down")
        core._download = broken
        r = self.c.get("/api/report?zone=chennai&lang=en")
        self.assertEqual(r.status_code, 502)
        self.assertIn("try again", r.json()["error"])

    def test_security_headers_and_cookie(self):
        r = self.signup()
        cookie = r.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        h = self.c.get("/login").headers
        self.assertIn("frame-ancestors 'none'", h["content-security-policy"])
        self.assertEqual(h["x-content-type-options"], "nosniff")

    def test_non_json_writes_rejected(self):
        self.assertEqual(self.c.post("/api/login", data={"name": "a", "pin": "1"}).status_code, 415)
        self.assertEqual(self.c.post("/api/login", content="{bad", headers={"content-type": "application/json"}).status_code, 401)

    def test_404(self):
        self.assertEqual(self.c.get("/api/nope").json()["error"], "not_found")
        r = self.c.get("/nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("Lost at sea", r.text)


class BestTime(Base):
    def test_status_per_zone(self):
        self.assertEqual(asyncio.run(core.best_window("chennai", "en"))["status"], "now")       # calm all day
        self.assertEqual(asyncio.run(core.best_window("thoothukudi", "en"))["status"], "caution")
        b = asyncio.run(core.best_window("kanyakumari", "ta"))
        self.assertIn(b["status"], ("caution", "none"))
        self.assertIn("கன்னியாகுமரி", b["text"])
        self.assertEqual(len(b["strip"]), core.BEST_HORIZON)

    def test_finds_a_later_window(self):
        levels = ["danger"] * 5 + ["safe"] * 2 + ["caution"] + ["safe"] * 4 + ["danger"] * 12
        self.assertEqual(core._first_run(levels, 0), (8, 12))        # 2-hour gap is too short, 4-hour run wins
        self.assertEqual(core._first_run(["danger"] * 24, 1), None)


class Trips(Base):
    def test_parse_back_by(self):
        from datetime import datetime
        now = datetime(2026, 10, 23, 17, 0, tzinfo=core.IST)
        self.assertEqual(core.parse_back_by("14:00", now).day, 24)       # already past today -> tomorrow
        self.assertEqual(core.parse_back_by("9 pm", now).hour, 21)
        self.assertEqual(core.parse_back_by("2:30PM", now).minute, 30)
        self.assertEqual(core.parse_back_by("8 hours", now).hour, 1)
        for bad in ["25:00", "13 pm", "soon", "", "99 hours"]:
            self.assertIsNone(core.parse_back_by(bad, now), bad)

    def test_trip_lifecycle_and_overdue(self):
        import server
        from datetime import datetime, timedelta
        core.save_user("Murugan", "rameswaram", "en")
        self.assertIn("Trip logged", asyncio.run(server.start_trip("Murugan", "6 hours")))
        self.assertIn("expected back", asyncio.run(server.check_on_trip("Murugan")))
        trips = core._read(core.TRIPS_FILE)
        trips["murugan"]["back_by"] = (datetime.now(core.IST) - timedelta(minutes=50)).isoformat()
        core._write(core.TRIPS_FILE, trips)
        overdue = asyncio.run(server.check_on_trip("Murugan"))
        self.assertIn("overdue", overdue)
        self.assertIn("1554", overdue)
        self.assertIn("Welcome back", asyncio.run(server.end_trip("Murugan")))
        self.assertIn("is back", asyncio.run(server.check_on_trip("Murugan")))
        self.assertIn("no trip", asyncio.run(server.end_trip("Murugan")))

    def test_worse_weather_warning(self):
        import server
        core.save_user("Murugan", "rameswaram", "en")
        asyncio.run(server.start_trip("Murugan", "6 hours"))
        self.assertNotIn("Warning", asyncio.run(server.check_on_trip("Murugan")))     # same sea as at departure
        trips = core._read(core.TRIPS_FILE)                                           # pretend it was calm when he left
        trips["murugan"]["at_start"] = {"level": "safe", "cause": "calm", "value": 0, "wave_max": 0.5, "gust_max": 12}
        core._write(core.TRIPS_FILE, trips)
        self.assertIn("worsened", asyncio.run(server.check_on_trip("Murugan")))
        self.assertTrue(asyncio.run(server.check_trip_risk(user="Murugan")).startswith("Warning"))

    def test_family_link(self):
        from starlette.testclient import TestClient
        import web
        c = TestClient(web.app)
        c.post("/api/signup", json={"name": "Murugan", "pin": "4321", "zone": "rameswaram", "lang": "en"})
        r = c.post("/api/trip", json={"back_by": "nonsense"})
        self.assertEqual(r.status_code, 400)
        token = c.post("/api/trip", json={"back_by": "8 hours", "lang": "ta"}).json()["trip"]["token"]
        family = TestClient(web.app)                                    # a different browser, not signed in
        self.assertEqual(family.get(f"/trip/{token}").status_code, 200)
        data = family.get(f"/api/family/{token}?lang=ta").json()
        self.assertEqual(data["status"], "at_sea")
        self.assertNotIn("token", data)
        self.assertEqual(family.get("/api/family/guess123").status_code, 404)
        self.assertEqual(family.get("/api/trip").status_code, 401)       # can't see trips without the link
        self.assertEqual(c.post("/api/trip/end").status_code, 415)       # non-JSON write blocked (CSRF guard)
        self.assertEqual(c.post("/api/trip/end", json={}).status_code, 200)
        self.assertEqual(family.get(f"/api/family/{token}").json()["status"], "returned")


class Board(Base):
    def test_board_lists_every_zone(self):
        from starlette.testclient import TestClient
        import web
        c = TestClient(web.app)
        self.assertEqual(c.get("/board").status_code, 200)              # no sign-in needed for a harbour TV
        zones = c.get("/api/board?lang=hi").json()["zones"]
        self.assertEqual(len(zones), 5)
        self.assertEqual({z["level"] for z in zones}, {"safe", "caution", "danger"})
        self.assertTrue(all(z["best"] for z in zones))

    def test_board_survives_one_zone_failing(self):
        real = core._download
        async def flaky(key):
            if key == "chennai":
                raise OSError("down")
            return await real(key)
        core._download = flaky
        zones = asyncio.run(core.board("en"))
        self.assertIn("error", zones[0])
        self.assertEqual(sum("error" in z for z in zones), 1)


if __name__ == "__main__":
    unittest.main()
