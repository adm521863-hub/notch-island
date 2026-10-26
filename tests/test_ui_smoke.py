"""Uji asap UI tanpa layar: tkinter diganti stub, semua mode digambar berulang."""
import ctypes
import os
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["APPDATA"] = tempfile.mkdtemp()


def install_stubs():
    if not hasattr(ctypes, "windll"):
        ctypes.windll = MagicMock()
        ctypes.WINFUNCTYPE = lambda *a, **k: (lambda f: f)
    root = MagicMock()
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    root.winfo_pointerxy.return_value = (10, 600)
    root.winfo_rootx.return_value = 800
    root.winfo_rooty.return_value = 0
    root.winfo_id.return_value = 1
    tk = types.ModuleType("tkinter")
    tk.Tk = lambda: root
    tk.Canvas = lambda *a, **k: MagicMock()
    tk.Menu = lambda *a, **k: MagicMock()
    tkf = types.ModuleType("tkinter.font")

    class Font:
        def __init__(self, *a, **k):
            pass

        def measure(self, s):
            return 7 * len(s)
    tkf.Font = Font
    tk.font = tkf
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.font"] = tkf
    return root


ROOT = install_stubs()
import notch_island as ni  # noqa: E402


def make():
    n = ni.Notch(selftest=True)
    n.track = {"title": "Judul lagu contoh yang sangat panjang sekali untuk uji", "artist": "Artis contoh", "dur": 200.0}
    n.playing, n.pos_ref, n.ref_t = True, 10.0, time.time()
    n.lyrics = ni._sample_lyrics()
    n.lyric_times = [t for t, _ in n.lyrics]
    return n


class Smoke(unittest.TestCase):
    def run_mode(self, n, mode, size, frames=30, mutate=None):
        n.force = (mode, size)
        for i in range(frames):
            if i == 5:  # loop uji berjalan sangat cepat; paksa ukuran selesai agar cabang "settled" ikut diuji
                n.w, n.h = map(float, n.cap(size))
            if mutate:
                mutate(i)
            delay = n.step()
            self.assertIn(delay, (16, 33, 50, 100, 250))

    def test_all_modes(self):
        n = make()
        saved = n.track
        n.track = None
        self.run_mode(n, "idle", ni.IDLE)
        n.sleeping = True
        self.run_mode(n, "idle", ni.IDLE, 5)
        n.track = saved
        self.run_mode(n, "idle", ni.PILL_MUSIC, 50, lambda i: setattr(n, "pos_ref", 10 + i * 0.5))
        self.run_mode(n, "card", ni.CARD)
        n.lyric_view = True
        self.run_mode(n, "card", ni.LYRICS, 80, lambda i: setattr(n, "pos_ref", 10 + i * 0.7))
        n.lyric_view = False
        n.track = None
        self.run_mode(n, "hover", ni.HOVER)
        n.track = saved
        for kind in ("wa", "greet", "remind", "prayer"):
            n.alert = {"kind": kind, "title": "Judul", "body": "Isi pesan contoh " * 5, "mascot": "alert", "secs": 99}
            n.alert_until = time.time() + 99
            self.run_mode(n, "alert", ni.ALERT, 20)
        for state in ("idle", "sleep", "happy", "alert", "dance"):
            n.draw_mascot(n.canvas, 30, 30, 40, state)

    def test_no_lyrics_and_no_art(self):
        n = make()
        n.lyrics, n.lyric_times = [], []
        for mode, size in (("idle", ni.PILL_MUSIC), ("card", ni.CARD), ("card", ni.LYRICS)):
            n.lyric_view = size == ni.LYRICS
            self.run_mode(n, mode, size, 10)

    def test_settings_variants(self):
        n = make()
        for patch in ({"mascot": False}, {"pill_icon": "none", "pill_eq": False}, {"pill_icon": "mascot"}, {"pill_icon": "cover"}, {"lyrics": False}, {"prayer": False}):
            n.cfg.update(patch)
            for mode, size in (("idle", ni.IDLE), ("idle", ni.PILL_MUSIC), ("card", ni.CARD), ("hover", ni.HOVER)):
                self.run_mode(n, mode, size, 6)

    def test_click_buttons(self):
        n = make()
        n.force = ("card", ni.CARD)
        n.w, n.h = map(float, n.cap(ni.CARD))
        for _ in range(10):
            n.step()
        n.alert = None  # pengingat ucapan otomatis bisa muncul saat step(); tutup dulu
        n.pending.clear()
        toggle = next(h for h in n.hit if h[0] == "circle" and h[1] == "toggle")
        was = n.playing
        n.on_click(types.SimpleNamespace(x=int(toggle[2]) + ni.SHOULDER, y=int(toggle[3])))
        self.assertNotEqual(was, n.playing)
        self.assertEqual(n.cmd_q.get_nowait(), "toggle")
        bar = next(h for h in n.hit if h[0] == "bar")
        n.on_click(types.SimpleNamespace(x=int((bar[1] + bar[2]) / 2) + ni.SHOULDER, y=int(bar[3])))
        cmd = n.cmd_q.get_nowait()
        self.assertEqual(cmd[0], "seek")
        self.assertTrue(80 < cmd[1] < 120)

    def test_text_helpers(self):
        n = make()
        self.assertTrue(n.fit("x" * 200, "body", 100).endswith("…"))
        self.assertEqual(n.fit("pendek", "body", 100), "pendek")
        lines = n.wrap("kata " * 60, 150, "ly", 3)
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(n.tw("ly", ln) <= 150 for ln in lines))

    def test_mini_mode_and_split(self):
        n = make()
        n.mini = True
        n.force = None
        n.track = None
        n.playing = False
        for _ in range(40):
            n.w, n.h = float(ni.MINI[0]), float(ni.MINI[1])
            n.alert = None            # ucapan otomatis dari penjadwal tidak relevan di uji ini
            n.pending.clear()
            n.step()
        self.assertEqual(n.mode, "mini")
        self.assertEqual(n.target, ni.MINI)
        n.alert = None
        n.pending.clear()
        self.assertEqual(n.step(), 100)
        pts = ni.Notch.notch_points(*ni.MINI)
        ys = pts[1::2]
        self.assertTrue(min(ys) >= -0.01 and max(ys) <= ni.MINI[1] + 0.01)

    def test_hover_distance(self):
        n = make()
        n.track = None
        n.playing = False
        n.w, n.h = float(ni.IDLE[0]), float(ni.IDLE[1])
        left = 800 + ni.SHOULDER
        ROOT.winfo_pointerxy.return_value = (left + int(n.w) + 25, 10)
        n.cfg["hover_distance"] = 30
        self.assertTrue(n.hovering())
        n.cfg["hover_distance"] = 10
        self.assertFalse(n.hovering())
        ROOT.winfo_pointerxy.return_value = (10, 600)

    def test_wa_alert_uses_mascot_or_icon(self):
        n = make()
        n.alert = {"kind": "wa", "title": "Nama", "body": "Pesan", "secs": 99}
        n.alert_until = time.time() + 99
        for mascot in (True, False):
            n.cfg["mascot"] = mascot
            self.run_mode(n, "alert", ni.ALERT, 8)

    def test_hidden_blocks_pending(self):
        n = make()
        n.hidden = True
        n.alert = None
        n.pending.append({"kind": "remind", "title": "x", "body": "y", "secs": 3})
        n.poll(time.time())
        self.assertIsNone(n.alert)
        n.hidden = False
        n.poll(time.time())
        self.assertIsNotNone(n.alert)

    def test_notch_shape(self):
        for w, h in ((210, 34), (300, 34), (520, 172), (640, 194)):
            pts = ni.Notch.notch_points(w, h)
            xs, ys = pts[0::2], pts[1::2]
            self.assertEqual((round(min(xs)), round(max(xs))), (0, w + 2 * ni.SHOULDER))
            self.assertEqual((round(pts[1]), round(pts[-1])), (0, 0))
            self.assertLessEqual(max(ys), h + 0.01)


if __name__ == "__main__":
    unittest.main()
