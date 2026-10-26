"""Fungsi khusus Windows (ctypes). Semua aman dipanggil; gagal = nilai netral."""
import ctypes
import re
from ctypes import wintypes

_user32 = None


def user32():
    global _user32
    if _user32 is None:
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetForegroundWindow.argtypes = []
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetAncestor.restype = wintypes.HWND
        u.IsIconic.argtypes = [wintypes.HWND]
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        _user32 = u
    return _user32


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def single_instance(name="NotchIslandSingleton"):
    """(boleh_jalan, handle). Handle harus disimpan agar mutex tidak dilepas."""
    try:
        k = ctypes.windll.kernel32
        handle = k.CreateMutexW(None, False, name)
        return k.GetLastError() != 183, handle
    except Exception:
        return True, None


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte),
                ("percent", ctypes.c_ubyte), ("sys", ctypes.c_ubyte),
                ("life", wintypes.DWORD), ("full", wintypes.DWORD)]


class _MemStatus(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                ("tpage", ctypes.c_ulonglong), ("apage", ctypes.c_ulonglong),
                ("tvirt", ctypes.c_ulonglong), ("avirt", ctypes.c_ulonglong),
                ("ext", ctypes.c_ulonglong)]


def battery():
    """(persen atau None, sedang_mengisi)."""
    try:
        s = _PowerStatus()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
        return (None if s.percent > 100 else int(s.percent)), s.ac == 1
    except Exception:
        return None, False


def ram_percent():
    try:
        m = _MemStatus()
        m.length = ctypes.sizeof(_MemStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return int(m.load)
    except Exception:
        return 0


def whatsapp_unread_from_titles():
    """Cadangan notifikasi WA: baca '(N) WhatsApp' dari judul jendela."""
    try:
        u = user32()
        best = 0
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _):
            nonlocal best
            if u.IsWindowVisible(hwnd):
                n = u.GetWindowTextLengthW(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(hwnd, buf, n + 1)
                    m = re.match(r"^\((\d+)\)\s*WhatsApp", buf.value)
                    if m:
                        best = max(best, int(m.group(1)))
            return True

        u.EnumWindows(proc_type(cb), 0)
        return best
    except Exception:
        return 0


def root_hwnd(widget_id):
    try:
        return user32().GetAncestor(widget_id, 2)
    except Exception:
        return None


def fullscreen_foreground(sw, sh, own_hwnd=None):
    """True bila jendela aktif menutupi seluruh layar (video/game layar penuh)."""
    try:
        u = user32()
        hwnd = u.GetForegroundWindow()
        if not hwnd or (own_hwnd and hwnd == own_hwnd):
            return False
        if not u.IsWindowVisible(hwnd):
            return False
        rect = wintypes.RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        if not (rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh):
            return False
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hwnd, cls, 64)
        return cls.value not in ("Progman", "WorkerW", "Shell_TrayWnd", "")
    except Exception:
        return False


_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                  "Windows.UI.Core.CoreWindow", "NotifyIconOverflowWindow", ""}


def side_by_side(spans, max_overlap=0.3):
    """True bila ada dua jendela yang berdampingan (hampir tidak tumpang tindih horizontal)."""
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            (l1, r1), (l2, r2) = spans[i], spans[j]
            overlap = min(r1, r2) - max(l1, l2)
            if overlap < max_overlap * min(r1 - l1, r2 - l2):
                return True
    return False


def split_screen_active(sw, sh, own_hwnd=None):
    """True bila layar sedang dibagi (snap 2 atau 3 jendela berdampingan).

    Jendela diperiksa dari yang paling atas; jendela maksimal/layar penuh
    menutupi semua yang ada di belakangnya, jadi pemeriksaan berhenti di situ.
    """
    try:
        u = user32()
        dwm = ctypes.windll.dwmapi
        dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        spans = []
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _):
            if own_hwnd and hwnd == own_hwnd:
                return True
            if not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
                return True
            cloaked = wintypes.DWORD(0)
            if dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4) == 0 and cloaked.value:
                return True
            ex = u.GetWindowLongW(hwnd, -20)
            if ex & 0x80 or ex & 0x08000000:      # tool window / tidak bisa diaktifkan
                return True
            if u.GetWindowTextLengthW(hwnd) == 0:
                return True
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, cls, 64)
            if cls.value in _SHELL_CLASSES:
                return True
            r = wintypes.RECT()
            if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
                u.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w <= 0 or h <= 0:
                return True
            if w >= 0.9 * sw and h >= 0.8 * sh:
                return False                       # maksimal/penuh: yang di belakang tidak terlihat
            if r.top <= 8 and h >= 0.5 * sh and 0.2 * sw <= w < 0.9 * sw:
                spans.append((r.left, r.right))
            return True

        u.EnumWindows(proc_type(cb), 0)
        return side_by_side(spans)
    except Exception:
        return False
