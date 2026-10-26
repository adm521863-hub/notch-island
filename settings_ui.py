"""Jendela Pengaturan: pilih fitur apa saja yang aktif di notch."""
import os
import tkinter as tk
from tkinter import ttk

import appconfig


def open_settings(root, cfg, on_save, on_test):
    win = tk.Toplevel(root)
    win.title("Pengaturan Notch Island")
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass

    v = {}
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))

    def tab(title):
        f = ttk.Frame(nb, padding=14)
        nb.add(f, text=title)
        return f

    def chk(f, row, key, text, init=None):
        var = tk.BooleanVar(value=bool(cfg[key] if init is None else init))
        v[key] = var
        ttk.Checkbutton(f, text=text, variable=var).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=3)

    def ent(f, row, key, label, width=26):
        ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 10))
        var = tk.StringVar(value=str(cfg[key]))
        v[key] = var
        ttk.Entry(f, textvariable=var, width=width).grid(row=row, column=1, columnspan=2, sticky="w")

    maps = {}

    def choice(f, row, key, label, options):
        """options: [(teks, nilai)]"""
        ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 10))
        by_val = {val: txt for txt, val in options}
        var = tk.StringVar(value=by_val.get(cfg[key], options[0][0]))
        v[key] = var
        maps[key] = {txt: val for txt, val in options}
        ttk.Combobox(f, textvariable=var, values=[t for t, _ in options], state="readonly",
                     width=24).grid(row=row, column=1, columnspan=2, sticky="w")

    def spin(f, row, key, label, lo, hi, col=0):
        ttk.Label(f, text=label).grid(row=row, column=col, sticky="w", pady=3, padx=(0, 10))
        var = tk.StringVar(value=str(cfg[key]))
        v[key] = var
        ttk.Spinbox(f, from_=lo, to=hi, textvariable=var, width=6).grid(row=row, column=col + 1, sticky="w")

    # --- Tampilan ---
    t1 = tab("Tampilan")
    ent(t1, 0, "name", "Nama panggilan (untuk ucapan)")
    chk(t1, 1, "mascot", "Tampilkan maskot")
    spin(t1, 2, "sleep_minutes", "Maskot tidur setelah (menit)", 1, 120)
    chk(t1, 3, "music_popup", "Kartu musik muncul saat ganti lagu")
    chk(t1, 4, "lyrics", "Lirik tersinkron dan mode lirik")
    choice(t1, 5, "pill_icon", "Ikon di pill musik",
           [("Cover album", "cover"), ("Maskot menari", "mascot"), ("Tidak ada", "none")])
    chk(t1, 6, "pill_eq", "Equalizer di pill kecil")
    chk(t1, 7, "wa", "Notifikasi WhatsApp (app atau WA Web di Chrome)")
    spin(t1, 8, "hover_distance", "Jarak kursor membuka notch (px)", 0, 120)
    choice(t1, 9, "split_mode", "Saat layar dibagi 2 atau 3 jendela",
           [("Perkecil otomatis", "mini"), ("Sembunyikan", "hide"), ("Tidak ada aksi", "off")])
    chk(t1, 10, "hide_fullscreen", "Sembunyikan notch saat aplikasi layar penuh")

    # --- Pengingat ---
    t2 = tab("Pengingat")
    chk(t2, 0, "greeting", "Ucapan selamat pagi / siang / sore / malam")
    chk(t2, 1, "remind_drink", "Ingatkan minum")
    spin(t2, 1, "drink_every", "tiap (menit)", 5, 240, col=3)
    chk(t2, 2, "remind_rest", "Ingatkan istirahat dan regangkan badan")
    spin(t2, 2, "rest_every", "tiap (menit)", 10, 480, col=3)
    chk(t2, 3, "remind_eat", "Ingatkan makan")
    ent(t2, 4, "eat_times", "Jam makan (pisahkan koma)")
    ent(t2, 5, "work_start", "Jam kerja mulai")
    ent(t2, 6, "work_end", "Jam kerja selesai")
    ttk.Label(t2, text="Pengingat kerja (satu per baris: 08:00 Cek APD)").grid(
        row=7, column=0, columnspan=4, sticky="w", pady=(10, 2))
    txt = tk.Text(t2, width=52, height=4, wrap="word")
    txt.insert("1.0", cfg["custom"])
    txt.grid(row=8, column=0, columnspan=4, sticky="w")
    ttk.Label(t2, text="Minum dan istirahat hanya muncul di dalam jam kerja.",
              foreground="#6e6e73").grid(row=9, column=0, columnspan=4, sticky="w", pady=(6, 0))

    # --- Sholat ---
    t3 = tab("Jadwal sholat")
    chk(t3, 0, "prayer", "Tampilkan jadwal sholat dan pengingat adzan")
    ttk.Label(t3, text="Kota").grid(row=1, column=0, sticky="w", pady=3, padx=(0, 10))
    city = tk.StringVar(value=cfg["prayer_city"])
    v["prayer_city"] = city
    box = ttk.Combobox(t3, textvariable=city, values=list(appconfig.CITIES) + ["Manual"],
                       state="readonly", width=24)
    box.grid(row=1, column=1, sticky="w")
    ent(t3, 2, "prayer_lat", "Lintang (latitude)", width=14)
    ent(t3, 3, "prayer_lon", "Bujur (longitude)", width=14)
    spin(t3, 4, "prayer_pre", "Ingatkan sebelum adzan (menit, 0 = mati)", 0, 60)

    def on_city(_=None):
        name = city.get()
        if name in appconfig.CITIES:
            lat, lon = appconfig.CITIES[name]
            v["prayer_lat"].set(str(lat))
            v["prayer_lon"].set(str(lon))
    box.bind("<<ComboboxSelected>>", on_city)
    ttk.Label(t3, text="Metode Kemenag RI (Subuh 20, Isya 18, ihtiyat 2 menit).\n"
                       "Waktu berupa perkiraan, cocokkan dengan jadwal resmi setempat.",
              foreground="#6e6e73").grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))

    # --- Sistem ---
    t4 = tab("Sistem")
    chk(t4, 0, "startup", "Jalankan Notch Island saat Windows menyala",
        init=appconfig.startup_enabled())
    ttk.Label(t4, text=f"Notch Island versi {appconfig.VERSION}").grid(
        row=1, column=0, sticky="w", pady=(10, 2))

    def open_folder():
        try:
            os.startfile(appconfig.config_dir())
        except Exception:
            pass
    ttk.Button(t4, text="Buka folder pengaturan", command=open_folder).grid(
        row=2, column=0, sticky="w", pady=4)

    def collect():
        new = dict(cfg)
        for key, var in v.items():
            val = var.get()
            new[key] = maps[key].get(val, cfg[key]) if key in maps else val
        new["custom"] = txt.get("1.0", "end").strip()
        return appconfig.sanitize(new)

    def save():
        on_save(collect())
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=10, pady=(4, 10))
    ttk.Button(bar, text="Tes maskot", command=on_test).pack(side="left")
    ttk.Button(bar, text="Batal", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Simpan", command=save).pack(side="right", padx=6)

    win.update_idletasks()
    try:
        x = (win.winfo_screenwidth() - win.winfo_width()) // 2
        win.geometry(f"+{max(0, x)}+120")
        win.lift()
        win.focus_force()
    except Exception:
        pass
    return win
