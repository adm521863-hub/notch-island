"""Penjadwal pengingat: ucapan waktu, makan, minum, istirahat, kerja, sholat.

Murni logika (tanpa UI) supaya mudah diuji. Scheduler.poll() dipanggil tiap
detik dan mengembalikan daftar event yang harus ditampilkan maskot.
"""
import random
import re

PRAYERS = ("Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya")

DRINK = ["Jangan lupa minum air putih ya.",
         "Waktunya minum, jaga tubuh tetap segar.",
         "Minum dulu sebentar, kerjaan masih panjang."]
REST = ["Istirahat sebentar, regangkan badan.",
        "Luruskan punggung dan rilekskan bahu.",
        "Berdiri dan jalan sebentar biar tetap fokus."]
EAT = {"sarapan": ("Waktunya sarapan", "Isi tenaga dulu sebelum mulai kerja."),
       "siang": ("Waktunya makan siang", "Jangan telat makan, istirahat dulu."),
       "malam": ("Waktunya makan malam", "Makan dulu, tubuhmu butuh tenaga.")}
GREET = {"pagi": ("Selamat pagi", "Semoga harimu lancar."),
         "siang": ("Selamat siang", "Jangan lupa makan siang ya."),
         "sore": ("Selamat sore", "Sedikit lagi, tetap semangat."),
         "malam": ("Selamat malam", "Istirahat yang cukup ya.")}


def parse_hhmm(text):
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*", text or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return h * 60 + mi if h < 24 and mi < 60 else None


def parse_times(text):
    out = []
    for part in re.split(r"[,;\s]+", text or ""):
        v = parse_hhmm(part)
        if v is not None and v not in out:
            out.append(v)
    return out


def parse_custom(text):
    """Setiap baris 'HH:MM pesan' -> [(menit, pesan)]."""
    out = []
    for line in (text or "").splitlines():
        m = re.match(r"\s*(\d{1,2}[:.]\d{2})\s+(.+?)\s*$", line)
        if m:
            v = parse_hhmm(m.group(1))
            if v is not None:
                out.append((v, m.group(2)))
    return out


def period_of(hour):
    if 4 <= hour < 11:
        return "pagi"
    if 11 <= hour < 15:
        return "siang"
    if 15 <= hour < 18:
        return "sore"
    return "malam"


def fmt_hm(hours):
    total = int(hours * 60 + 0.5) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


def fmt_remain(minutes):
    minutes = max(0, int(minutes))
    if minutes >= 60:
        return f"{minutes // 60} j {minutes % 60} m"
    return f"{minutes} m"


def next_prayer(times, now_minutes):
    """(nama, menit_lagi) untuk sholat berikutnya (Subuh besok jika sudah lewat Isya)."""
    for name in PRAYERS:
        m = times[name] * 60
        if m > now_minutes:
            return name, m - now_minutes
    return "Subuh", times["Subuh"] * 60 + 1440 - now_minutes


class Scheduler:
    def __init__(self, prayer_fn=None, rng=None):
        self.prayer_fn = prayer_fn
        self.rng = rng or random.Random()
        self.period = None
        self.reset()

    def reset(self, keep_period=False):
        self.day = None
        self.fired = set()
        self.next_drink = None
        self.next_rest = None
        if not keep_period:
            self.period = None

    def _work_range(self, cfg):
        a = parse_hhmm(cfg.get("work_start"))
        b = parse_hhmm(cfg.get("work_end"))
        return (7 * 60 if a is None else a), (18 * 60 if b is None else b)

    def poll(self, now, cfg):
        events = []
        ts = now.timestamp()
        mins = now.hour * 60 + now.minute
        day = now.date().isoformat()
        if day != self.day:
            self.day = day
            self.fired = set()
        start, end = self._work_range(cfg)
        in_work = start <= mins < end

        # ucapan
        p = period_of(now.hour)
        if p != self.period:
            self.period = p
            if cfg.get("greeting"):
                title, body = GREET[p]
                name = (cfg.get("name") or "").strip()
                if name:
                    title += ", " + name
                events.append({"kind": "greet", "title": title, "body": body,
                               "mascot": "happy", "secs": 6})

        # minum dan istirahat (interval, hanya jam kerja)
        for key, flag, every, msgs, title in (
                ("next_drink", "remind_drink", "drink_every", DRINK, "Waktunya minum"),
                ("next_rest", "remind_rest", "rest_every", REST, "Waktunya istirahat")):
            if not cfg.get(flag):
                setattr(self, key, None)
                continue
            nxt = getattr(self, key)
            step = max(1, int(cfg.get(every, 60))) * 60
            if nxt is None:
                setattr(self, key, ts + step)
            elif ts >= nxt:
                setattr(self, key, ts + step)
                if in_work:
                    events.append({"kind": "remind", "title": title,
                                   "body": self.rng.choice(msgs), "mascot": "happy", "secs": 8})

        # makan
        if cfg.get("remind_eat"):
            for t in parse_times(cfg.get("eat_times")):
                k = f"eat{t}"
                if t <= mins < t + 2 and k not in self.fired:
                    self.fired.add(k)
                    label = "sarapan" if t < 10 * 60 else ("siang" if t < 16 * 60 else "malam")
                    title, body = EAT[label]
                    events.append({"kind": "remind", "title": title, "body": body,
                                   "mascot": "happy", "secs": 8})

        # pengingat kerja khusus
        for t, msg in parse_custom(cfg.get("custom")):
            k = f"custom{t}{msg}"
            if t <= mins < t + 2 and k not in self.fired:
                self.fired.add(k)
                events.append({"kind": "remind", "title": "Pengingat kerja", "body": msg,
                               "mascot": "alert", "secs": 10})

        # sholat
        if cfg.get("prayer") and self.prayer_fn:
            times = self.prayer_fn(now.date())
            pre = int(cfg.get("prayer_pre", 0))
            for name in PRAYERS:
                m = int(times[name] * 60 + 0.5)
                hm = fmt_hm(times[name])
                k_pre, k_now = f"pre{name}", f"now{name}"
                if pre > 0 and m - pre <= mins < min(m, m - pre + 2) and k_pre not in self.fired:
                    self.fired.add(k_pre)
                    events.append({"kind": "prayer", "title": f"{pre} menit lagi {name}",
                                   "body": f"Pukul {hm}, bersiap ya.", "mascot": "idle", "secs": 8})
                if m <= mins < m + 2 and k_now not in self.fired:
                    self.fired.add(k_now)
                    events.append({"kind": "prayer", "title": f"Waktu {name}",
                                   "body": f"Pukul {hm}, saatnya sholat.", "mascot": "idle", "secs": 12})
        return events
