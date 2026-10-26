"""Pengaturan aplikasi: simpan/muat JSON dan opsi 'mulai bersama Windows'."""
import json
import os
import sys

APP_NAME = "NotchIsland"
VERSION = "1.1.0"

CITIES = {
    "Jakarta": (-6.2088, 106.8456),
    "Tangerang": (-6.1783, 106.6319),
    "Bekasi": (-6.2383, 106.9756),
    "Bandung": (-6.9175, 107.6191),
    "Semarang": (-6.9667, 110.4167),
    "Yogyakarta": (-7.7956, 110.3695),
    "Surabaya": (-7.2575, 112.7521),
    "Denpasar": (-8.6705, 115.2126),
    "Medan": (3.5952, 98.6722),
    "Batam": (1.0456, 104.0305),
    "Palembang": (-2.9761, 104.7754),
    "Pontianak": (-0.0263, 109.3425),
    "Balikpapan": (-1.2379, 116.8529),
    "Makassar": (-5.1477, 119.4327),
}

DEFAULTS = {
    # tampilan
    "name": "",
    "mascot": True,
    "sleep_minutes": 5,
    "music_popup": True,
    "pill_icon": "cover",
    "hover_distance": 30,
    "split_mode": "mini",
    "pill_eq": True,
    "lyrics": True,
    "lyric_view": False,
    "wa": True,
    "hide_fullscreen": True,
    # pengingat
    "greeting": True,
    "remind_drink": True,
    "drink_every": 60,
    "remind_rest": True,
    "rest_every": 120,
    "remind_eat": True,
    "eat_times": "07:00, 12:00, 18:30",
    "work_start": "07:00",
    "work_end": "18:00",
    "custom": "08:00 Cek APD sebelum mulai bongkar\n16:30 Rekap barang masuk dan keluar hari ini",
    # sholat
    "prayer": True,
    "prayer_city": "Jakarta",
    "prayer_lat": -6.2088,
    "prayer_lon": 106.8456,
    "prayer_pre": 10,
    # sistem
    "startup": False,
}

LIMITS = {
    "sleep_minutes": (1, 120),
    "drink_every": (5, 240),
    "rest_every": (10, 480),
    "prayer_pre": (0, 60),
    "hover_distance": (0, 120),
    "prayer_lat": (-90.0, 90.0),
    "prayer_lon": (-180.0, 180.0),
}


def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path():
    return os.path.join(config_dir(), "config.json")


def sanitize(cfg):
    """Pastikan semua kunci ada, tipenya benar, dan angkanya wajar."""
    out = {}
    for key, default in DEFAULTS.items():
        value = cfg.get(key, default)
        try:
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, int):
                value = int(float(value))
            elif isinstance(default, float):
                value = float(value)
            else:
                value = str(value)
        except Exception:
            value = default
        if key in LIMITS:
            lo, hi = LIMITS[key]
            value = max(lo, min(hi, value))
        out[key] = value
    if out["pill_icon"] not in ("cover", "mascot", "none"):
        out["pill_icon"] = DEFAULTS["pill_icon"]
    if out["split_mode"] not in ("mini", "hide", "off"):
        out["split_mode"] = DEFAULTS["split_mode"]
    return out


def load():
    data = {}
    try:
        with open(config_path(), encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
    return sanitize(data)


def save(cfg):
    path = config_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sanitize(cfg), f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------- Mulai bersama Windows ----------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    return f'"{exe}" "{os.path.abspath(sys.argv[0])}"'


def startup_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except Exception:
        return False


def set_startup(enable):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
