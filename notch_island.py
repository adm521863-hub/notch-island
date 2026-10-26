"""
Notch Island untuk Windows

- Bentuk      : menempel di tepi atas layar, bahu melengkung keluar
- Istirahat   : maskot (berkedip, tidur) + jam
- Musik       : pill kecil = lirik bergulir vertikal. Hover / ganti lagu = kartu
                musik. Tombol lirik = mode lirik dua panel
- Maskot      : ucapan pagi/siang/sore/malam, pengingat makan/minum/istirahat/kerja,
                jadwal sholat
- Notif WA    : aplikasi WhatsApp atau WhatsApp Web di Chrome
- Pengaturan  : klik kanan notch -> Pengaturan (pilih fitur yang aktif)
"""
import bisect
import math
import os
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkfont
from collections import deque
from datetime import datetime

import appconfig
import services
import winutil
from prayer import prayer_times, tz_hours
from reminders import Scheduler, fmt_hm, fmt_remain, next_prayer

# ---------- Ukuran (lebar, tinggi) ----------
IDLE = (210, 34)
MINI = (64, 12)       # ukuran terkecil saat layar dibagi
PILL_MUSIC = (300, 34)
HOVER = (440, 152)
CARD = (520, 172)
LYRICS = (640, 194)
ALERT = (470, 112)
SHOULDER = 12        # radius bahu cekung di tepi atas layar
RADIUS = 22          # radius sudut bawah
ART_SMALL, ART_CARD, ART_LYR = 24, 84, 76
POPUP_SECONDS = 5
DWELL = 0.15         # tahan kursor sebentar sebelum notch melebar
HOVER_HOLD = 0.30    # tetap terbuka sebentar setelah kursor pergi

BG = "#000000"
KEY = "#010101"      # warna transparan (jangan dipakai konten)
GREEN, WA_GREEN, MUSIC_GREEN = "#30d158", "#25d366", "#1ed760"
TEAL, TEAL_D, CHEEK, PUPIL = "#5DCAA5", "#085041", "#F0997B", "#04342C"
GRAY = "#a1a1a6"

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
HARI_S = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def shade(rgb, f):
    f = max(0.0, min(1.0, f))
    return "#%02x%02x%02x" % tuple(int(v * f) for v in rgb)


def fmt(sec):
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def rrect(x1, y1, x2, y2, r):
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


class Notch:
    def __init__(self, selftest=False):
        self.selftest = selftest
        self.cfg = appconfig.load()
        self.root = r = tk.Tk()
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.configure(bg=KEY)
        r.attributes("-transparentcolor", KEY)
        self.sw, self.sh = r.winfo_screenwidth(), r.winfo_screenheight()

        F = tkfont.Font
        self.fonts = {
            "pill": F(family="Segoe UI", size=10),
            "small": F(family="Segoe UI", size=9),
            "body": F(family="Segoe UI", size=10),
            "title": F(family="Segoe UI Semibold", size=12),
            "big": F(family="Segoe UI Semibold", size=14),
            "ly": F(family="Segoe UI Semibold", size=11),
        }
        self.canvas = tk.Canvas(r, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.menu = tk.Menu(r, tearoff=0)
        self.menu.add_command(label="Pengaturan…", command=self.open_settings)
        self.menu.add_command(label="Tes maskot", command=self.test_alerts)
        self.menu.add_separator()
        self.menu.add_command(label="Keluar", command=self.quit)
        self.canvas.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        self.canvas.bind("<Button-1>", self.on_click)

        # tampilan
        self.w, self.h = map(float, IDLE)
        self.target = IDLE
        self.mode = "idle"
        self.force = None
        self.geo = None
        self.hit = []
        self.hidden = False
        self.mini = False
        self.beat = 0.0
        self.settings_win = None
        # waktu
        self.last_t = time.time()
        self.last_stats = self.last_titles = self.last_sched = 0.0
        self.last_fs = self.last_top = 0.0
        self.last_log = 0.0
        self.idle_since = time.time()
        self.hover_since = None
        self.hover_until = 0.0
        self.sleeping = False
        self.stats = (None, False, 0)
        # notifikasi
        self.unread = 0
        self.listener = "starting"
        self.alert = None
        self.alert_until = 0.0
        self.pending = deque(maxlen=8)
        # musik
        self.track = None
        self.playing = False
        self.pos_ref, self.ref_t = 0.0, time.time()
        self.lyrics, self.lyric_times = [], []
        self.lyrics_loading = False
        self.art = self.art_card = self.art_lyr = None
        self.popup_until = 0.0
        self.lyric_view = bool(self.cfg["lyric_view"])
        self.cur_idx, self.cur_text, self.prev_text, self.anim_t = -99, "", "", 0.0
        self.ly_cur, self.ly_shift = None, 0.0
        # cache teks
        self._c = {}
        # pengingat
        self._pt_key = None
        self._pt = None
        self.sched = Scheduler(prayer_fn=self.prayers_for)
        self._np = (0, "")

        self.q = queue.Queue()
        self.cmd_q = queue.Queue()
        if not selftest:
            threading.Thread(target=services.winrt_listener, args=(self.q,), daemon=True).start()
            threading.Thread(target=services.media_listener, args=(self.q, self.cmd_q), daemon=True).start()

    # ---------- umum ----------
    def quit(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def log_error(self):
        now = time.time()
        if now - self.last_log < 5:
            return
        self.last_log = now
        try:
            p = os.path.join(appconfig.config_dir(), "error.log")
            if os.path.exists(p) and os.path.getsize(p) > 200_000:
                os.remove(p)
            with open(p, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
        except Exception:
            pass

    def cap(self, size):
        return (min(size[0], self.sw - 2 * SHOULDER - 24), size[1])

    def card_size(self):
        return LYRICS if (self.lyric_view and self.cfg["lyrics"]) else CARD

    def music_active(self):
        return self.track is not None and self.playing

    def pos_now(self):
        return self.pos_ref + (time.time() - self.ref_t) if self.playing else self.pos_ref

    def prayers_for(self, d):
        lat, lon = self.cfg["prayer_lat"], self.cfg["prayer_lon"]
        key = (d.toordinal(), round(lat, 4), round(lon, 4))
        if key != self._pt_key:
            self._pt = prayer_times(d, lat, lon, tz_hours())
            self._pt_key = key
        return self._pt

    # ---------- pengaturan ----------
    def open_settings(self):
        try:
            if self.settings_win is not None and self.settings_win.winfo_exists():
                self.settings_win.lift()
                return
        except Exception:
            pass
        import settings_ui
        self.settings_win = settings_ui.open_settings(self.root, self.cfg, self.apply_cfg, self.test_alerts)

    def open_settings_for_test(self):
        import settings_ui
        return settings_ui.open_settings(self.root, self.cfg, lambda c: None, lambda: None)

    def apply_cfg(self, new):
        self.cfg = new
        try:
            appconfig.save(new)
        except Exception:
            self.log_error()
        appconfig.set_startup(bool(new.get("startup")))
        self.lyric_view = bool(new["lyric_view"]) and bool(new["lyrics"])
        self._pt_key = None
        self.sched.reset(keep_period=True)
        self._c.clear()

    def test_alerts(self):
        name = (self.cfg.get("name") or "").strip()
        self.pending.extend([
            {"kind": "greet", "title": "Selamat pagi" + (", " + name if name else ""),
             "body": "Contoh ucapan dari maskot.", "mascot": "happy", "secs": 4},
            {"kind": "remind", "title": "Waktunya minum",
             "body": "Jangan lupa minum air putih ya.", "mascot": "happy", "secs": 4},
            {"kind": "prayer", "title": "Waktu Dzuhur",
             "body": "Pukul 11:39, saatnya sholat.", "mascot": "idle", "secs": 4},
            {"kind": "wa", "title": "Nama pengirim",
             "body": "Contoh notifikasi WhatsApp.", "secs": 4},
        ])

    # ---------- cache teks ----------
    def _put(self, key, val):
        if len(self._c) > 900:
            self._c.clear()
        self._c[key] = val
        return val

    def tw(self, fname, text):
        k = ("m", fname, text)
        v = self._c.get(k)
        return v if v is not None else self._put(k, self.fonts[fname].measure(text))

    def cum(self, fname, text):
        k = ("c", fname, text)
        v = self._c.get(k)
        if v is None:
            acc, out = 0, [0]
            for ch in text:
                acc += self.fonts[fname].measure(ch)
                out.append(acc)
            v = self._put(k, out)
        return v

    def fit(self, text, fname, maxw):
        text = " ".join((text or "").split())
        k = ("f", fname, text, int(maxw))
        v = self._c.get(k)
        if v is not None:
            return v
        if self.tw(fname, text) <= maxw:
            return self._put(k, text)
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.tw(fname, text[:mid] + "…") <= maxw:
                lo = mid
            else:
                hi = mid - 1
        return self._put(k, text[:lo] + "…")

    def wrap(self, text, area, fname="ly", maxlines=3):
        k = ("w", fname, text, int(area), maxlines)
        v = self._c.get(k)
        if v is not None:
            return v
        lines, cur = [], ""
        for wd in (text or "").split():
            trial = wd if not cur else cur + " " + wd
            if self.tw(fname, trial) <= area:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = wd if self.tw(fname, wd) <= area else self.fit(wd, fname, area)
        if cur:
            lines.append(cur)
        if not lines:
            lines = [""]
        if len(lines) > maxlines:
            lines = lines[:maxlines]
            lines[-1] = self.fit(lines[-1] + "…", fname, area)
        return self._put(k, lines)

    # ---------- loop ----------
    def run(self):
        self.tick()
        self.root.mainloop()

    def tick(self):
        delay = 50
        try:
            delay = self.step()
        except Exception:
            self.log_error()
        try:
            self.root.after(delay, self.tick)
        except Exception:
            pass

    def poll(self, now):
        try:
            while True:
                m = self.q.get_nowait()
                k = m[0]
                if k == "status":
                    self.listener = m[1]
                elif k == "notif":
                    if self.cfg["wa"]:
                        self.pending.append({"kind": "wa", "title": m[1], "body": m[2], "secs": 6})
                elif k == "track":
                    self.on_track(*m[1:])
                elif k == "play":
                    self.playing, self.pos_ref, self.ref_t = m[1], m[2], m[3]
                elif k == "nomedia":
                    self.track, self.playing = None, False
                    self.lyrics, self.lyric_times = [], []
                    self.art = self.art_card = self.art_lyr = None
                elif k == "lyrics":
                    if self.track and m[1] == (self.track["title"], self.track["artist"]):
                        self.lyrics = m[2]
                        self.lyric_times = [t for t, _ in m[2]]
                        self.lyrics_loading = False
        except queue.Empty:
            pass

        if now - self.last_sched >= 1.0:
            self.last_sched = now
            for ev in self.sched.poll(datetime.now(), self.cfg):
                self.pending.append(ev)

        if self.cfg["wa"] and now - self.last_titles > 2.0:
            self.last_titles = now
            n = winutil.whatsapp_unread_from_titles()
            if n > self.unread and self.listener != "ok":
                self.pending.append({"kind": "wa", "title": "WhatsApp",
                                     "body": f"{n} pesan belum dibaca", "secs": 6})
            self.unread = n

        if self.alert and now > self.alert_until:
            self.alert = None
        if not self.alert and self.pending and not self.hidden:
            self.alert = self.pending.popleft()
            self.alert_until = now + float(self.alert.get("secs", 6))
            self.idle_since = now

    def on_track(self, title, artist, dur, thumb):
        self.track = {"title": title, "artist": artist, "dur": dur}
        self.lyrics, self.lyric_times = [], []
        self.lyrics_loading = bool(self.cfg["lyrics"])
        self.art = services.make_art(thumb, ART_SMALL) if thumb else None
        self.art_card = services.make_art(thumb, ART_CARD) if thumb else None
        self.art_lyr = services.make_art(thumb, ART_LYR) if thumb else None
        self.cur_idx, self.cur_text, self.prev_text = -99, "", ""
        self.ly_cur, self.ly_shift = None, 0.0
        self.idle_since = time.time()
        if self.cfg["music_popup"]:
            self.popup_until = time.time() + POPUP_SECONDS
        if self.cfg["lyrics"]:
            threading.Thread(target=services.fetch_lyrics,
                             args=(artist, title, dur, self.q, (title, artist)),
                             daemon=True).start()

    def hovering(self):
        if self.hidden:
            return False
        px, py = self.root.winfo_pointerxy()
        left = self.root.winfo_rootx() + SHOULDER
        top = self.root.winfo_rooty()
        # saat tertutup, kursor yang mendekat (jarak diatur di Pengaturan) sudah membuka notch
        pad = self.cfg["hover_distance"] if self.mode in ("idle", "mini") else 12
        return left - pad <= px <= left + self.w + pad and top <= py <= top + self.h + pad

    def select_mode(self, now):
        cfg = self.cfg
        if self.force:
            self.mode, size = self.force
            self.target = self.cap(size)
            return
        if self.hovering():
            if self.hover_since is None:
                self.hover_since = now
            dwell = 0.0 if self.mode in ("card", "hover") else DWELL
            if now - self.hover_since >= dwell:
                self.hover_until = now + HOVER_HOLD
                self.idle_since = now
        else:
            self.hover_since = None
        hovered = now < self.hover_until
        if self.alert:
            mode, size = "alert", ALERT
        elif self.track and cfg["music_popup"] and now < self.popup_until:
            mode, size = "card", self.card_size()
        elif hovered:
            mode, size = ("card", self.card_size()) if self.track else ("hover", HOVER)
        else:
            mode, size = "idle", (PILL_MUSIC if self.music_active() else IDLE)
            if self.mini:
                mode, size = "mini", MINI
        self.mode = mode
        self.target = self.cap(size)
        self.sleeping = bool(cfg["mascot"] and mode == "idle" and not self.music_active()
                             and now - self.idle_since > cfg["sleep_minutes"] * 60)

    def check_windows(self, now):
        """Tiap 1,5 detik: deteksi aplikasi layar penuh dan layar terbagi (snap)."""
        if self.selftest or now - self.last_fs < 1.5:
            return
        self.last_fs = now
        own = winutil.root_hwnd(self.root.winfo_id())
        fs = bool(self.cfg["hide_fullscreen"]) and winutil.fullscreen_foreground(self.sw, self.sh, own)
        split_mode = self.cfg["split_mode"]
        split = (not fs) and split_mode != "off" and winutil.split_screen_active(self.sw, self.sh, own)
        self.mini = bool(split and split_mode == "mini")
        want_hidden = bool(fs or (split and split_mode == "hide"))
        if want_hidden != self.hidden:
            self.hidden = want_hidden
            if want_hidden:
                self.root.withdraw()
            else:
                self.root.deiconify()
                self.root.attributes("-topmost", True)
                self.geo = None

    def step(self):
        """Satu frame. Mengembalikan jeda (ms) sampai frame berikutnya."""
        now = time.time()
        dt = min(0.1, max(0.001, now - self.last_t))
        self.last_t = now
        self.poll(now)
        self.check_windows(now)
        if self.hidden:
            return 250
        if not self.selftest and now - self.last_top > 5:
            self.last_top = now
            self.root.attributes("-topmost", True)
        self.select_mode(now)

        tw_, th_ = self.target
        moving = abs(tw_ - self.w) > 0.5 or abs(th_ - self.h) > 0.5
        k = 1 - math.exp(-dt * 16)
        self.w += (tw_ - self.w) * k
        self.h += (th_ - self.h) * k
        if abs(tw_ - self.w) < 0.6:
            self.w = float(tw_)
        if abs(th_ - self.h) < 0.6:
            self.h = float(th_)
        if abs(self.ly_shift) > 0.3:
            self.ly_shift *= math.exp(-dt * 11)
        else:
            self.ly_shift = 0.0

        if now - self.last_stats > 5:
            pct, ac = winutil.battery()
            self.stats = (pct, ac, winutil.ram_percent())
            self.last_stats = now

        wi, hi = int(round(self.w)), int(round(self.h))
        W = wi + 2 * SHOULDER
        X = (self.sw - W) // 2
        if (W, hi, X) != self.geo:
            self.root.geometry(f"{W}x{hi}+{X}+0")
            self.geo = (W, hi, X)
        self.draw(wi, hi)

        if moving or abs(self.ly_shift) > 0.5:
            return 16
        if self.mode == "mini":
            return 100
        if self.mode != "idle" or self.music_active():
            return 33
        return 100 if self.sleeping else 50

    # ---------- klik ----------
    def on_click(self, e):
        now = time.time()
        self.idle_since = now
        if self.alert:
            self.alert = None
            return
        if self.mode != "card":
            return
        lx, ly = e.x - SHOULDER, e.y
        for item in self.hit:
            if item[0] == "circle":
                _, name, bx, by, br = item
                if (lx - bx) ** 2 + (ly - by) ** 2 <= br * br:
                    if name == "lyric":
                        self.lyric_view = not self.lyric_view
                        self.cfg["lyric_view"] = self.lyric_view
                        try:
                            appconfig.save(self.cfg)
                        except Exception:
                            pass
                    else:
                        self.cmd_q.put(name)
                        if name == "toggle":
                            p = self.pos_now()
                            self.playing = not self.playing
                            self.pos_ref, self.ref_t = p, now
                    return
            elif item[0] == "bar":
                _, x1, x2, by = item
                if x1 - 6 <= lx <= x2 + 6 and abs(ly - by) <= 10 and self.track and self.track["dur"] > 0:
                    sec = max(0.0, min(1.0, (lx - x1) / (x2 - x1))) * self.track["dur"]
                    self.cmd_q.put(("seek", sec))
                    self.pos_ref, self.ref_t = sec, now
                    return
        self.popup_until = 0.0

    # ---------- lirik ----------
    def lyric_state(self, pos):
        pos += 0.0
        if self.lyric_times:
            i = bisect.bisect_right(self.lyric_times, pos) - 1
            if i >= 0:
                start = self.lyric_times[i]
                end = self.lyric_times[i + 1] if i + 1 < len(self.lyric_times) else start + 5
                return i, (self.lyrics[i][1] or "♪"), start, end, pos
        t = self.track
        return -1, f"{t['title']} — {t['artist']}", 0.0, 0.0, pos

    @staticmethod
    def marquee_progress(idx, pos, start, end):
        if idx >= 0:
            return max(0.0, min(1.0, (pos - start - 0.6) / max(1.0, (end - start) * 0.7)))
        ph = (time.time() % 10) / 10
        return ph * 2 if ph < 0.5 else 2 - ph * 2

    def put_text(self, c, text, prog, x1, x2, y, color, fname="pill"):
        f = self.fonts[fname]
        area = x2 - x1
        cum = self.cum(fname, text)
        total = cum[-1]
        if total <= area:
            c.create_text((x1 + x2) / 2, y, text=text, fill=color, font=f)
            return
        off = (total - area) * prog
        i = bisect.bisect_left(cum, off)
        j = max(i, bisect.bisect_right(cum, cum[min(i, len(cum) - 1)] + area) - 1)
        c.create_text(x1, y, text=text[i:j], fill=color, font=f, anchor="w")

    # ---------- gambar ----------
    @staticmethod
    def notch_points(w, h):
        pad = SHOULDER                               # lebar bahu = ruang kosong di tiap sisi jendela
        S = min(pad, max(2, h - 6))                  # bahu mengecil bila notch sangat pendek
        R = max(3, min(RADIUS, h - S))
        W = w + 2 * pad
        x0 = pad - S
        n = 10
        pts = []
        for i in range(n + 1):                       # bahu kiri
            t = (math.pi / 2) * i / n
            pts += [x0 + S * math.sin(t), S - S * math.cos(t)]
        cx, cy = pad + R, h - R                      # sudut kiri-bawah
        for i in range(n + 1):
            a = math.pi - (math.pi / 2) * i / n
            pts += [cx + R * math.cos(a), cy + R * math.sin(a)]
        cx = pad + w - R                             # sudut kanan-bawah
        for i in range(n + 1):
            a = (math.pi / 2) - (math.pi / 2) * i / n
            pts += [cx + R * math.cos(a), cy + R * math.sin(a)]
        for i in range(n + 1):                       # bahu kanan
            t = (math.pi / 2) * (1 - i / n)
            pts += [W - x0 - S * math.sin(t), S - S * math.cos(t)]
        return pts

    def draw(self, w, h):
        c = self.canvas
        c.delete("all")
        self.hit = []
        tw_, th_ = self.target
        settled = abs(h - th_) < 12 and abs(w - tw_) < 24
        m = self.mode
        if m == "idle":
            if self.music_active():
                if w >= PILL_MUSIC[0] - 24 and h <= IDLE[1] + 8:
                    self.draw_pill_music(c, w, h)
            elif h <= IDLE[1] + 8 and w <= IDLE[0] + 24:
                self.draw_idle(c, w, h)
        elif m == "card" and settled and self.track:
            if self.lyric_view and self.cfg["lyrics"]:
                self.draw_lyrics_view(c, w, h)
            else:
                self.draw_card(c, w, h)
        elif m == "hover" and settled:
            self.draw_hover(c, w, h)
        elif m == "alert" and settled and self.alert:
            self.draw_alert(c, w, h)
        c.move("all", SHOULDER, 0)
        shape = c.create_polygon(self.notch_points(w, h), fill=BG, outline=BG)
        c.tag_lower(shape)

    # --- maskot (karakter orisinal) ---
    def draw_mascot(self, c, cx, cy, size, state):
        t = time.time()
        u = size / 24.0
        ox, oy = cx - 12 * u, cy - 12 * u
        if state == "dance":
            oy -= (abs(math.sin(t * 7)) * 3 + max(0.0, 1 - (t - self.beat) * 3) * 2) * u
        elif state in ("idle", "sleep"):
            oy += math.sin(t * 1.6) * 0.5 * u

        def P(x, y):
            return ox + x * u, oy + y * u

        ax, ay = P(12, 4)
        bx, by = P(12, 1.6)
        c.create_line(ax, ay, bx, by, fill=TEAL, width=max(1, 1.4 * u))
        c.create_oval(bx - 1.4 * u, by - 1.4 * u, bx + 1.4 * u, by + 1.4 * u, fill=CHEEK, outline="")
        x1, y1 = P(2, 4)
        x2, y2 = P(22, 22)
        c.create_polygon(rrect(x1, y1, x2, y2, 9 * u), smooth=True, splinesteps=12,
                         fill=TEAL, outline=TEAL)
        for ex in (5.2, 18.8):
            px, py = P(ex, 17)
            c.create_oval(px - 1.6 * u, py - 1 * u, px + 1.6 * u, py + 1 * u,
                          fill=CHEEK, outline="", stipple="gray50")
        lw = max(1, 1.3 * u)
        if state == "sleep":
            for ex in (8.5, 15.5):
                px, py = P(ex, 12.2)
                c.create_arc(px - 2.6 * u, py - 2 * u, px + 2.6 * u, py + 2 * u,
                             start=200, extent=140, style="arc", outline=TEAL_D, width=lw)
            mx, my = P(12, 17.5)
            c.create_arc(mx - 1.6 * u, my - 1 * u, mx + 1.6 * u, my + 1 * u,
                         start=200, extent=140, style="arc", outline=TEAL_D, width=lw)
            zy = (t * 9) % 10
            zx, zy0 = P(21, 3)
            c.create_text(zx, zy0 - zy * u * 0.5, text="z", fill=GRAY,
                          font=("Segoe UI", max(7, int(size * 0.4))))
            return
        if state == "happy":
            for ex in (8.5, 15.5):
                px, py = P(ex, 13.6)
                c.create_arc(px - 2.6 * u, py - 2.2 * u, px + 2.6 * u, py + 2.2 * u,
                             start=20, extent=140, style="arc", outline=TEAL_D, width=lw)
            mx, my = P(12, 17.2)
            c.create_arc(mx - 3 * u, my - 2 * u, mx + 3 * u, my + 2 * u,
                         start=200, extent=140, style="arc", outline=TEAL_D, width=lw)
            return
        big = state == "alert"
        er = (3.2 if big else 2.7) * u
        blink = 0.12 if (t % 4.2) < 0.14 else 1.0
        dx = 1.3 * u * math.sin(t * 0.9) if not big else 0.0
        for ex in (8.5, 15.5):
            px, py = P(ex, 13)
            c.create_oval(px - er, py - er * blink, px + er, py + er * blink, fill="white", outline="")
            if blink > 0.5:
                pr = (1.1 if big else 1.2) * u
                c.create_oval(px + dx - pr, py + 0.2 * u - pr, px + dx + pr, py + 0.2 * u + pr,
                              fill=PUPIL, outline="")
        mx, my = P(12, 18.4)
        if big or state == "dance":
            c.create_oval(mx - 1.8 * u, my - 2 * u, mx + 1.8 * u, my + 2 * u, fill=TEAL_D, outline="")
        else:
            c.create_arc(mx - 2 * u, my - 1.6 * u, mx + 2 * u, my + 1.6 * u,
                         start=200, extent=140, style="arc", outline=TEAL_D, width=lw)
        if big:
            qx, qy = P(21, 4)
            c.create_text(qx, qy, text="!", fill=CHEEK, font=("Segoe UI", max(8, int(size * 0.45)), "bold"))

    # --- istirahat ---
    def draw_idle(self, c, w, h):
        t = time.time()
        cy = h / 2
        if self.cfg["mascot"]:
            self.draw_mascot(c, 22, cy, 24, "sleep" if self.sleeping else "idle")
        else:
            ph = (t % 2.0) / 2.0
            c.create_oval(18, cy - 4, 26, cy + 4, fill=GREEN, outline="")
            r = 4 + 8 * ph
            c.create_oval(22 - r, cy - r, 22 + r, cy + r, outline=shade((48, 209, 88), 1 - ph), fill="")
        c.create_text(w / 2 + 6, cy, text=time.strftime("%H:%M"),
                      fill="#8e8e93" if self.sleeping else "white", font=self.fonts["title"])
        if self.unread:
            c.create_oval(w - 38, cy - 9, w - 20, cy + 9, fill=WA_GREEN, outline="")
            c.create_text(w - 29, cy, text=str(min(self.unread, 99)), fill="black",
                          font=("Segoe UI", 8, "bold"))
        elif not self.sleeping:
            for k in range(3):
                wave = max(0.0, math.sin(t * 5 - k * 0.7))
                x, y = w - 38 + k * 9, cy - 4 * wave
                c.create_oval(x - 2, y - 2, x + 2, y + 2,
                              fill=shade((142, 142, 147), 0.45 + 0.55 * wave), outline="")

    # --- pill musik: lirik bergulir vertikal ---
    def draw_pill_music(self, c, w, h):
        cfg = self.cfg
        x1 = 14
        icon = cfg["pill_icon"]
        if icon == "mascot" and not cfg["mascot"]:
            icon = "cover"
        if icon == "mascot":
            self.draw_mascot(c, 22, h / 2, 24, "dance")
            x1 = 42
        elif icon == "cover":
            if self.art:
                c.create_image(10, h / 2, image=self.art, anchor="w")
            else:
                c.create_rectangle(10, h / 2 - 12, 34, h / 2 + 12, fill="#2c2c2e", outline="")
                c.create_text(22, h / 2, text="♪", fill=GRAY, font=("Segoe UI", 11))
            x1 = 42
        x2 = w - 48 if cfg["pill_eq"] else w - 16
        idx, text, start, end, pos = self.lyric_state(self.pos_now())
        now = time.time()
        if idx != self.cur_idx:
            self.prev_text, self.cur_text = self.cur_text, text
            self.cur_idx, self.anim_t = idx, now
            self.beat = now
        p = min(1.0, (now - self.anim_t) / 0.22)
        p = 1 - (1 - p) ** 3
        prog = self.marquee_progress(idx, pos, start, end)
        if p < 1 and self.prev_text:
            self.put_text(c, self.prev_text, 1.0, x1, x2, h / 2 - p * 13, "#6e6e73")
        self.put_text(c, self.cur_text, prog, x1, x2, h / 2 + (1 - p) * 13, "white")
        if cfg["pill_eq"]:
            for k in range(3):
                amp = 0.35 + 0.65 * abs(math.sin(now * 3.1 + k * 1.7))
                bh = 4 + 10 * amp
                x = w - 38 + k * 8
                c.create_rectangle(x, h / 2 - bh / 2, x + 4, h / 2 + bh / 2, fill=MUSIC_GREEN, outline="")

    # --- kartu musik ---
    def draw_art(self, c, x, y, img, size):
        if img:
            c.create_image(x, y, image=img, anchor="nw")
        else:
            c.create_polygon(rrect(x, y, x + size, y + size, size // 6), smooth=True,
                             fill="#2c2c2e", outline="#2c2c2e")
            c.create_text(x + size / 2, y + size / 2, text="♪", fill=GRAY,
                          font=("Segoe UI", max(10, size // 3)))

    def draw_header(self, c, x, y):
        now = datetime.now()
        c.create_oval(x - 6, y - 6, x + 6, y + 6, outline=GREEN, width=2)
        date = f"{HARI_S[now.weekday()]} {now.day} {BULAN[now.month - 1]} {now.year}"
        c.create_text(x + 16, y, text=date, anchor="w", fill="white", font=self.fonts["small"])
        tx = x + 16 + self.tw("small", date) + 10
        c.create_text(tx, y, text=now.strftime("%H:%M"), anchor="w", fill="white", font=self.fonts["title"])

    def draw_progress(self, c, left, right, y):
        t = self.track
        dur = t["dur"]
        pos = self.pos_now()
        if dur > 0:
            pos = min(pos, dur)
        c.create_text(left, y, text=fmt(pos), anchor="w", fill="white", font=self.fonts["small"])
        if dur > 0:
            c.create_text(right, y, text="-" + fmt(dur - pos), anchor="e", fill="white",
                          font=self.fonts["small"])
        x1, x2 = left + 44, right - 52
        c.create_line(x1, y, x2, y, fill="#4d4d4d", width=4, capstyle="round")
        if dur > 0 and pos > 0:
            c.create_line(x1, y, x1 + (x2 - x1) * pos / dur, y, fill="white", width=4, capstyle="round")
        self.hit.append(("bar", x1, x2, y))

    def draw_controls(self, c, cx, cy, lyric_x):
        px, nx = cx - 52, cx + 52
        c.create_rectangle(px - 8, cy - 7, px - 6, cy + 7, fill="white", outline="")
        c.create_polygon(px + 7, cy - 7, px + 7, cy + 7, px - 5, cy, fill="white")
        c.create_rectangle(nx + 6, cy - 7, nx + 8, cy + 7, fill="white", outline="")
        c.create_polygon(nx - 7, cy - 7, nx - 7, cy + 7, nx + 5, cy, fill="white")
        c.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, fill="white", outline="")
        if self.playing:
            c.create_rectangle(cx - 5, cy - 6, cx - 2, cy + 6, fill="black", outline="")
            c.create_rectangle(cx + 2, cy - 6, cx + 5, cy + 6, fill="black", outline="")
        else:
            c.create_polygon(cx - 4, cy - 7, cx - 4, cy + 7, cx + 7, cy, fill="black")
        self.hit += [("circle", "prev", px, cy, 15), ("circle", "toggle", cx, cy, 16),
                     ("circle", "next", nx, cy, 15)]
        if self.cfg["lyrics"]:
            col = "white" if self.lyric_view else GRAY
            c.create_polygon(rrect(lyric_x - 10, cy - 8, lyric_x + 10, cy + 6, 4), smooth=True,
                             outline=col, fill="", width=2)
            c.create_polygon(lyric_x - 4, cy + 5, lyric_x - 7, cy + 11, lyric_x + 2, cy + 5, fill=col, outline=col)
            for dx in (-3, 3):
                c.create_oval(lyric_x + dx - 1.5, cy - 3.5, lyric_x + dx + 1.5, cy - 0.5, fill=col, outline="")
            self.hit.append(("circle", "lyric", lyric_x, cy, 16))

    def draw_card(self, c, w, h):
        t = self.track
        ax, ay = 22, 26
        self.draw_art(c, ax, ay, self.art_card, ART_CARD)
        tx = ax + ART_CARD + 18
        self.draw_header(c, tx + 6, 30)
        c.create_text(tx, 66, text=self.fit(t["title"], "big", w - tx - 26), fill="white",
                      anchor="w", font=self.fonts["big"])
        c.create_text(tx, 88, text=self.fit(t["artist"], "body", w - tx - 26), fill=GRAY,
                      anchor="w", font=self.fonts["body"])
        self.draw_progress(c, 22, w - 22, 128)
        self.draw_controls(c, w / 2, 152, 38)

    # --- mode lirik dua panel ---
    def draw_lyrics_view(self, c, w, h):
        t = self.track
        split = 312
        ax, ay = 22, 28
        self.draw_art(c, ax, ay, self.art_lyr, ART_LYR)
        tx = ax + ART_LYR + 14
        c.create_text(tx, 52, text=self.fit(t["title"], "title", split - tx - 14), fill="white",
                      anchor="w", font=self.fonts["title"])
        c.create_text(tx, 74, text=self.fit(t["artist"], "body", split - tx - 14), fill=GRAY,
                      anchor="w", font=self.fonts["body"])
        self.draw_progress(c, 22, split - 14, 126)
        self.draw_controls(c, 160, 158, 38)
        c.create_line(split + 12, 30, split + 12, h - 24, fill="#3a3a3c")
        self.draw_lyric_panel(c, split + 34, w - 26, 24, h - 20, self.pos_now())

    def draw_lyric_panel(self, c, x1, x2, top, bot, pos):
        area = x2 - x1
        if not self.lyrics:
            msg = "Memuat lirik…" if self.lyrics_loading else "Lirik tidak tersedia"
            c.create_text((x1 + x2) / 2, (top + bot) / 2, text=msg, fill="#6e6e73", font=self.fonts["body"])
            return
        LH, GAP = 18, 10
        n = len(self.lyrics)

        def lines_of(i):
            return self.wrap(self.lyrics[i][1] or "♪", area, "ly", 3)

        def hgt(i):
            return len(lines_of(i)) * LH + GAP

        idx = self.lyric_state(pos)[0]
        cur = min(max(idx, 0), n - 1)
        if self.ly_cur is not None and cur != self.ly_cur:
            if abs(cur - self.ly_cur) <= 3:
                lo, hi = sorted((cur, self.ly_cur))
                dist = sum(hgt(i) for i in range(lo, hi))
                self.ly_shift += dist if cur > self.ly_cur else -dist
            else:
                self.ly_shift = 0.0
        self.ly_cur = cur

        anchor = top + (bot - top) * 0.34
        y0 = anchor + self.ly_shift
        items = [(cur, y0)]
        yy = y0
        for i in range(cur - 1, max(-1, cur - 4), -1):
            yy -= hgt(i)
            items.append((i, yy))
        yy = y0 + hgt(cur)
        for i in range(cur + 1, min(n, cur + 5)):
            items.append((i, yy))
            yy += hgt(i)
        mid = anchor + len(lines_of(cur)) * LH / 2
        for i, ytop in items:
            ls = lines_of(i)
            hh = len(ls) * LH
            if ytop < top - 2 or ytop + hh > bot + 2:
                continue
            d = abs(ytop + hh / 2 - mid)
            f = max(0.0, 1 - d / 120)
            col = shade((255, 255, 255), 0.28 + 0.72 * f ** 1.5)
            for k, ln in enumerate(ls):
                c.create_text(x1, ytop + k * LH + LH / 2, text=ln, anchor="w", fill=col,
                              font=self.fonts["ly"])

    # --- hover tanpa musik ---
    def next_prayer_text(self):
        sec = int(time.time())
        if self._np[0] == sec:
            return self._np[1]
        now = datetime.now()
        times = self.prayers_for(now.date())
        name, mins = next_prayer(times, now.hour * 60 + now.minute + now.second / 60.0)
        text = f"{name} {fmt_hm(times[name])} · {fmt_remain(mins)} lagi"
        self._np = (sec, text)
        return text

    def draw_hover(self, c, w, h):
        now = datetime.now()
        if self.cfg["mascot"]:
            self.draw_mascot(c, 64, 62, 34, "sleep" if self.sleeping else "idle")
        c.create_text(w / 2, 42, text=now.strftime("%H:%M:%S"), fill="white", font=("Segoe UI Light", 30))
        c.create_text(w / 2, 76, text=f"{HARI[now.weekday()]}, {now.day} {BULAN[now.month - 1]} {now.year}",
                      fill=GRAY, font=self.fonts["body"])
        if self.cfg["prayer"]:
            c.create_text(w / 2, 100, text=self.next_prayer_text(), fill=MUSIC_GREEN, font=self.fonts["body"])
        pct, ac, ram = self.stats
        bat = "Baterai —" if pct is None else f"Baterai {pct}%" + (" · mengisi" if ac else "")
        c.create_text(w * 0.27, 130, text=bat, fill=GREEN, font=self.fonts["body"])
        c.create_text(w * 0.73, 130, text=f"RAM {ram}%", fill="#0a84ff", font=self.fonts["body"])

    # --- notifikasi dan maskot ---
    def draw_wa_icon(self, c, cx, cy, r=18):
        s = r / 18.0
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=WA_GREEN, outline="")
        c.create_oval(cx - 9 * s, cy - 8 * s, cx + 9 * s, cy + 6 * s, fill="white", outline="")
        c.create_polygon(cx - 5 * s, cy + 4 * s, cx - 8 * s, cy + 11 * s, cx + 1 * s, cy + 6 * s,
                         fill="white", outline="white")
        for dx in (-4, 0, 4):
            c.create_oval(cx + (dx - 1.4) * s, cy - 2.4 * s, cx + (dx + 1.4) * s, cy + 0.4 * s,
                          fill=WA_GREEN, outline="")

    def draw_alert(self, c, w, h):
        it = self.alert
        cy = h / 2 + 4
        if it.get("kind") == "wa":
            if self.cfg["mascot"]:
                self.draw_mascot(c, 40, cy, 40, "alert")      # maskot kaget + lencana WA
                self.draw_wa_icon(c, 60, cy + 16, 9)
                tx = 76
            else:
                self.draw_wa_icon(c, 38, cy)
                tx = 72
        else:
            if self.cfg["mascot"]:
                self.draw_mascot(c, 40, cy, 40, it.get("mascot", "happy"))
            else:
                c.create_oval(22, cy - 18, 58, cy + 18, fill=TEAL, outline="")
                c.create_text(40, cy, text="!", fill=TEAL_D, font=("Segoe UI", 16, "bold"))
            tx = 76
        maxw = w - tx - 24
        c.create_text(tx, cy - 16, text=self.fit(it.get("title", ""), "title", maxw), fill="white",
                      anchor="w", font=self.fonts["title"])
        for k, ln in enumerate(self.wrap(it.get("body", ""), maxw, "body", 2)):
            c.create_text(tx, cy + 4 + k * 16, text=ln, fill="#d1d1d6", anchor="w", font=self.fonts["body"])


# ---------- selftest (dipakai CI) ----------
def _sample_lyrics():
    # teks contoh buatan sendiri, hanya untuk uji tampilan
    return [(float(i * 4), f"Baris lirik contoh nomor {i + 1} untuk uji tampilan") for i in range(12)]


def selftest():
    winutil.set_dpi_aware()
    log = os.path.join(appconfig.config_dir(), "selftest.log")
    try:
        n = Notch(selftest=True)
        n.track = {"title": "Judul lagu contoh yang cukup panjang", "artist": "Artis contoh", "dur": 200.0}
        n.playing, n.pos_ref, n.ref_t = True, 10.0, time.time()
        n.lyrics = _sample_lyrics()
        n.lyric_times = [t for t, _ in n.lyrics]
        n.cfg["music_popup"] = False

        def frames(count, mutate=None):
            for i in range(count):
                if mutate:
                    mutate(i)
                n.step()
                n.root.update()

        n.force = ("idle", IDLE)
        saved_track = n.track
        n.track = None
        frames(15)
        n.sleeping = True
        frames(5)
        n.track = saved_track
        n.force = ("idle", PILL_MUSIC)
        frames(40, lambda i: setattr(n, "pos_ref", 10.0 + i * 0.5))
        n.cfg["pill_icon"] = "mascot"
        n.force = ("idle", PILL_MUSIC)
        frames(20)
        n.cfg["pill_icon"] = "cover"
        n.force = ("mini", MINI)
        frames(10)
        n.force = ("card", CARD)
        frames(25)
        n.lyric_view = True
        n.force = ("card", LYRICS)
        frames(60, lambda i: setattr(n, "pos_ref", 10.0 + i * 0.6))
        n.lyric_view = False
        n.track = None
        n.force = ("hover", HOVER)
        frames(25)
        n.track = saved_track
        for kind, mascot in (("wa", None), ("greet", "happy"), ("remind", "alert"),
                             ("prayer", "idle"), ("remind", "dance")):
            n.alert = {"kind": kind, "title": "Judul pengingat contoh", "body": "Isi pesan contoh. " * 4,
                       "mascot": mascot or "happy", "secs": 99}
            n.alert_until = time.time() + 99
            n.force = ("alert", ALERT)
            frames(20)
        n.alert = None
        n.force = None
        n.cfg["mascot"] = False
        n.force = ("idle", IDLE)
        n.track = None
        frames(10)
        win = n.open_settings_for_test()
        n.root.update()
        win.destroy()
        n.root.destroy()
        with open(log, "w", encoding="utf-8") as f:
            f.write("SELFTEST OK\n")
        return 0
    except Exception:
        with open(log, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        return 1


def check_winrt():
    log = os.path.join(appconfig.config_dir(), "winrt-check.log")
    missing = []
    for mod in ("winrt.windows.media.control", "winrt.windows.storage.streams",
                "winrt.windows.ui.notifications", "winrt.windows.ui.notifications.management",
                "PIL.ImageTk"):
        try:
            __import__(mod)
        except Exception as e:
            missing.append(f"{mod}: {e}")
    with open(log, "w", encoding="utf-8") as f:
        f.write("OK\n" if not missing else "MISSING\n" + "\n".join(missing) + "\n")
    return 0 if not missing else 2


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--check-winrt" in sys.argv:
        sys.exit(check_winrt())
    winutil.set_dpi_aware()
    ok, _handle = winutil.single_instance()
    if not ok:
        return
    Notch().run()


if __name__ == "__main__":
    main()
