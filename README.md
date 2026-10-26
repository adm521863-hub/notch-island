# Notch Island

Notch ala Dynamic Island untuk Windows, menempel di tepi atas layar dengan bahu melengkung keluar.

## Fitur (semua bisa dimatikan di Pengaturan)
- **Istirahat:** maskot orisinal berkedip, menoleh, bernapas, dan tidur kalau lama diam, di samping jam. Badge hijau muncul bila ada WA belum dibaca
- **Musik:** pill kecil menampilkan lirik bergulir vertikal, dengan ikon cover album atau maskot yang menari mengikuti lirik. Hover atau ganti lagu membuka kartu musik (cover, judul, artis, progres, prev, play/jeda, next). Tombol lirik membuka mode lirik dua panel
- **Maskot pengingat:** makan, minum, istirahat, dan pengingat kerja buatan sendiri
- **Ucapan:** selamat pagi, siang, sore, malam
- **Jadwal sholat:** pengingat sebelum dan saat adzan (metode Kemenag RI, perkiraan)
- **Notifikasi WhatsApp:** aplikasi atau WhatsApp Web di Chrome; maskot kaget saat pesan masuk
- **Hover tanpa musik:** jam, tanggal, sholat berikutnya, baterai, RAM
- **Kursor mendekat membuka notch:** jarak bisa diatur (0-120 px)
- **Layar dibagi 2 atau 3 jendela (snap):** notch otomatis mengecil jadi garis kecil tanpa isi, atau disembunyikan. Pilih di Pengaturan
- Disembunyikan otomatis saat aplikasi layar penuh

Klik kanan notch untuk **Pengaturan**, **Tes maskot**, atau **Keluar**.

## Instal
Unduh `NotchIslandSetup-x.y.z.exe` dari tab **Releases**, jalankan, lalu pilih:
- Jalankan saat Windows menyala
- Pintasan di desktop

Windows SmartScreen bisa menampilkan "Windows protected your PC" karena aplikasi belum ditandatangani.
Klik **More info** lalu **Run anyway**. Versi tanpa instalasi: `NotchIsland-portable-x.y.z.zip`.

## Rilis lewat GitHub
1. Push ke branch `main`. GitHub Actions menjalankan uji, membangun exe, uji coba exe, dan membuat installer (ada di Actions > Artifacts).
2. Untuk rilis resmi: `git tag v1.0.0` lalu `git push origin v1.0.0`. File installer dan zip otomatis muncul di Releases.

## Lirik dan notifikasi
- Lirik tersinkron diambil dari [LRCLIB](https://lrclib.net) dan hanya disimpan di memori. Jika tidak ada, pill menampilkan judul dan artis.
- Notifikasi WA: Windows > Settings > Privacy & security > Notifications, izinkan akses notifikasi. Chrome: izinkan notifikasi untuk web.whatsapp.com. Jika ditolak, aplikasi memakai cadangan (hitung "(N) WhatsApp" di judul tab Chrome yang aktif).

## Pengembangan
```
pip install -r requirements.txt
python notch_island.py
python -m unittest discover -s tests
```
Pengaturan tersimpan di `%APPDATA%\NotchIsland\config.json`, log galat di `error.log` pada folder yang sama.
