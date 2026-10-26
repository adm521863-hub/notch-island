"""Jadwal sholat offline (algoritma posisi matahari, metode Kemenag RI).

Subuh 20 derajat, Isya 18 derajat, Ashar standar (bayangan 1x), ihtiyat +2 menit.
Hasilnya perkiraan; cocokkan dengan jadwal resmi setempat bila perlu.
"""
import math
from datetime import datetime


def _sin(d):
    return math.sin(math.radians(d))


def _cos(d):
    return math.cos(math.radians(d))


def _fix_angle(a):
    return a - 360.0 * math.floor(a / 360.0)


def _fix_hour(a):
    return a - 24.0 * math.floor(a / 24.0)


def _julian(y, m, d):
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100.0)
    b = 2 - a + math.floor(a / 4.0)
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def _sun_position(jd):
    d = jd - 2451545.0
    g = _fix_angle(357.529 + 0.98560028 * d)
    q = _fix_angle(280.459 + 0.98564736 * d)
    lon = _fix_angle(q + 1.915 * _sin(g) + 0.020 * _sin(2 * g))
    e = 23.439 - 0.00000036 * d
    ra = math.degrees(math.atan2(_cos(e) * _sin(lon), _cos(lon))) / 15.0
    eqt = q / 15.0 - _fix_hour(ra)
    decl = math.degrees(math.asin(_sin(e) * _sin(lon)))
    return decl, eqt


def tz_hours():
    off = datetime.now().astimezone().utcoffset()
    return off.total_seconds() / 3600.0 if off else 7.0


def prayer_times(day, lat, lon, tz, fajr_angle=20.0, isha_angle=18.0,
                 asr_factor=1.0, ihtiyat=2.0):
    """Mengembalikan dict nama -> jam desimal waktu lokal."""
    jd = _julian(day.year, day.month, day.day) - lon / (15.0 * 24.0)

    def mid_day(t):
        _, eqt = _sun_position(jd + t)
        return _fix_hour(12.0 - eqt)

    def sun_angle_time(angle, t, ccw=False):
        decl, _ = _sun_position(jd + t)
        noon = mid_day(t)
        x = (-_sin(angle) - _sin(decl) * _sin(lat)) / (_cos(decl) * _cos(lat))
        x = max(-1.0, min(1.0, x))
        delta = math.degrees(math.acos(x)) / 15.0
        return noon + (-delta if ccw else delta)

    def asr_time(factor, t):
        decl, _ = _sun_position(jd + t)
        angle = -math.degrees(math.atan(1.0 / (factor + math.tan(math.radians(abs(lat - decl))))))
        return sun_angle_time(angle, t)

    t = {"fajr": 5 / 24, "sunrise": 6 / 24, "dhuhr": 12 / 24, "asr": 13 / 24,
         "sunset": 18 / 24, "isha": 18 / 24}
    res = {}
    for _ in range(2):
        res = {
            "fajr": sun_angle_time(fajr_angle, t["fajr"], ccw=True),
            "sunrise": sun_angle_time(0.833, t["sunrise"], ccw=True),
            "dhuhr": mid_day(t["dhuhr"]),
            "asr": asr_time(asr_factor, t["asr"]),
            "sunset": sun_angle_time(0.833, t["sunset"]),
            "isha": sun_angle_time(isha_angle, t["isha"]),
        }
        t = {k: v / 24.0 for k, v in res.items()}

    shift = tz - lon / 15.0
    ih = ihtiyat / 60.0
    return {
        "Subuh": res["fajr"] + shift + ih,
        "Terbit": res["sunrise"] + shift - ih,
        "Dzuhur": res["dhuhr"] + shift + ih,
        "Ashar": res["asr"] + shift + ih,
        "Maghrib": res["sunset"] + shift + ih,
        "Isya": res["isha"] + shift + ih,
    }
