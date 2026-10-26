import os
import random
import sys
import tempfile
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["APPDATA"] = tempfile.mkdtemp()

import appconfig  # noqa: E402
import services  # noqa: E402
from prayer import prayer_times  # noqa: E402
from reminders import (Scheduler, fmt_hm, next_prayer, parse_custom,  # noqa: E402
                       parse_hhmm, parse_times, period_of)


def cfg(**kw):
    c = appconfig.sanitize({})
    c.update(kw)
    return c


class PrayerTests(unittest.TestCase):
    def test_jakarta_order_and_range(self):
        t = prayer_times(date(2026, 10, 25), -6.2088, 106.8456, 7)
        order = [t[k] for k in ("Subuh", "Terbit", "Dzuhur", "Ashar", "Maghrib", "Isya")]
        self.assertEqual(order, sorted(order))
        self.assertTrue(11.4 < t["Dzuhur"] < 12.0, fmt_hm(t["Dzuhur"]))
        self.assertTrue(17.5 < t["Maghrib"] < 18.2, fmt_hm(t["Maghrib"]))
        self.assertTrue(3.9 < t["Subuh"] < 4.6, fmt_hm(t["Subuh"]))

    def test_next_prayer_wraps_to_tomorrow(self):
        t = prayer_times(date(2026, 10, 25), -6.2088, 106.8456, 7)
        name, mins = next_prayer(t, 23 * 60)
        self.assertEqual(name, "Subuh")
        self.assertTrue(0 < mins < 8 * 60)


class ParseTests(unittest.TestCase):
    def test_hhmm(self):
        self.assertEqual(parse_hhmm("07:30"), 450)
        self.assertEqual(parse_hhmm("7.05"), 425)
        self.assertIsNone(parse_hhmm("25:00"))
        self.assertIsNone(parse_hhmm("abc"))

    def test_times_and_custom(self):
        self.assertEqual(parse_times("07:00, 12:00; 18:30 bad"), [420, 720, 1110])
        self.assertEqual(parse_custom("08:00 Cek APD\nasal\n16:30 Rekap"), [(480, "Cek APD"), (990, "Rekap")])

    def test_period(self):
        self.assertEqual([period_of(h) for h in (5, 12, 16, 20, 2)], ["pagi", "siang", "sore", "malam", "malam"])

    def test_lrc(self):
        r = services.parse_lrc("[00:01.50] satu\n[00:05.00]\n[01:02.25] tiga\nbukan lrc")
        self.assertEqual(r, [(1.5, "satu"), (5.0, ""), (62.25, "tiga")])


class SplitTests(unittest.TestCase):
    def test_side_by_side(self):
        import winutil
        self.assertTrue(winutil.side_by_side([(0, 960), (960, 1920)]))
        self.assertTrue(winutil.side_by_side([(0, 640), (640, 1280), (1280, 1920)]))
        self.assertFalse(winutil.side_by_side([(0, 960), (100, 1000)]))   # saling menumpuk
        self.assertFalse(winutil.side_by_side([(0, 960)]))
        self.assertFalse(winutil.side_by_side([]))


class ConfigTests(unittest.TestCase):
    def test_enums_and_hover_limits(self):
        c = appconfig.sanitize({"pill_icon": "aneh", "split_mode": "x", "hover_distance": 999})
        self.assertEqual(c["pill_icon"], "cover")
        self.assertEqual(c["split_mode"], "mini")
        self.assertEqual(c["hover_distance"], 120)
        c2 = appconfig.sanitize({"pill_icon": "mascot", "split_mode": "hide", "hover_distance": 0})
        self.assertEqual((c2["pill_icon"], c2["split_mode"], c2["hover_distance"]), ("mascot", "hide", 0))

    def test_sanitize_clamps_and_types(self):
        c = appconfig.sanitize({"drink_every": "9999", "prayer_lat": "abc", "mascot": 0, "name": 5})
        self.assertEqual(c["drink_every"], 240)
        self.assertEqual(c["prayer_lat"], appconfig.DEFAULTS["prayer_lat"])
        self.assertIs(c["mascot"], False)
        self.assertEqual(c["name"], "5")

    def test_save_load_roundtrip(self):
        c = cfg(name="Budi", mascot=False)
        appconfig.save(c)
        self.assertEqual(appconfig.load()["name"], "Budi")
        self.assertIs(appconfig.load()["mascot"], False)


class SchedulerTests(unittest.TestCase):
    def sched(self):
        return Scheduler(prayer_fn=lambda d: prayer_times(d, -6.2088, 106.8456, 7), rng=random.Random(1))

    def test_greeting_once_per_period(self):
        s, c = self.sched(), cfg(prayer=False, remind_eat=False, custom="")
        e1 = s.poll(datetime(2026, 10, 25, 8, 0, 0), c)
        e2 = s.poll(datetime(2026, 10, 25, 8, 0, 1), c)
        self.assertEqual([e["title"] for e in e1], ["Selamat pagi"])
        self.assertEqual(e2, [])
        e3 = s.poll(datetime(2026, 10, 25, 12, 0, 0), cfg(prayer=False, remind_eat=False, custom=""))
        self.assertEqual(e3[0]["title"], "Selamat siang")

    def test_greeting_uses_name_and_can_be_disabled(self):
        s = self.sched()
        e = s.poll(datetime(2026, 10, 25, 20, 0, 0), cfg(name="Budi", prayer=False, remind_eat=False, custom=""))
        self.assertEqual(e[0]["title"], "Selamat malam, Budi")
        s2 = self.sched()
        self.assertEqual(s2.poll(datetime(2026, 10, 25, 20, 0, 0), cfg(greeting=False, prayer=False,
                                                                       remind_eat=False, custom="")), [])

    def test_eat_fires_once(self):
        s, c = self.sched(), cfg(greeting=False, prayer=False, custom="", remind_drink=False, remind_rest=False)
        a = s.poll(datetime(2026, 10, 25, 12, 0, 5), c)
        b = s.poll(datetime(2026, 10, 25, 12, 1, 5), c)
        self.assertEqual([e["title"] for e in a], ["Waktunya makan siang"])
        self.assertEqual(b, [])

    def test_drink_interval_and_work_hours(self):
        c = cfg(greeting=False, prayer=False, remind_eat=False, custom="", remind_rest=False, drink_every=60)
        s = self.sched()
        self.assertEqual(s.poll(datetime(2026, 10, 25, 9, 0, 0), c), [])
        self.assertEqual(s.poll(datetime(2026, 10, 25, 9, 30, 0), c), [])
        e = s.poll(datetime(2026, 10, 25, 10, 0, 1), c)
        self.assertEqual(e[0]["title"], "Waktunya minum")
        self.assertEqual(s.poll(datetime(2026, 10, 25, 10, 30, 0), c), [])
        s2 = self.sched()
        s2.poll(datetime(2026, 10, 25, 20, 0, 0), c)
        self.assertEqual(s2.poll(datetime(2026, 10, 25, 21, 0, 1), c), [])  # di luar jam kerja

    def test_custom_and_prayer(self):
        c = cfg(greeting=False, remind_eat=False, remind_drink=False, remind_rest=False, prayer_pre=10)
        s = self.sched()
        e = s.poll(datetime(2026, 10, 25, 8, 0, 3), c)
        self.assertEqual([x["kind"] for x in e], ["remind"])
        t = prayer_times(date(2026, 10, 25), -6.2088, 106.8456, 7)
        m = int(t["Dzuhur"] * 60 + 0.5)
        pre = s.poll(datetime(2026, 10, 25, (m - 10) // 60, (m - 10) % 60, 2), c)
        now = s.poll(datetime(2026, 10, 25, m // 60, m % 60, 2), c)
        again = s.poll(datetime(2026, 10, 25, m // 60, m % 60, 40), c)
        self.assertEqual(pre[0]["title"], "10 menit lagi Dzuhur")
        self.assertEqual(now[0]["title"], "Waktu Dzuhur")
        self.assertEqual(again, [])


if __name__ == "__main__":
    unittest.main()
