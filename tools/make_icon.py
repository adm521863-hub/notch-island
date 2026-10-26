"""Buat assets/icon.ico dari maskot orisinal (butuh Pillow). Jalankan: python tools/make_icon.py"""
import os
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=230, fill=(0, 0, 0, 255))      # latar notch
u = S / 24.0 * 0.78
ox = oy = S * 0.11
def P(x, y): return ox + x * u, oy + y * u
teal, dark, cheek, pupil = (93, 202, 165), (8, 80, 65), (240, 153, 123), (4, 52, 44)
d.line([P(12, 4), P(12, 1.6)], fill=teal, width=int(1.4 * u))
x, y = P(12, 1.6); r = 1.5 * u
d.ellipse((x - r, y - r, x + r, y + r), fill=cheek)
d.rounded_rectangle((*P(2, 4), *P(22, 22)), radius=int(9 * u), fill=teal)
for ex in (5.2, 18.8):
    x, y = P(ex, 17)
    d.ellipse((x - 1.6 * u, y - 1 * u, x + 1.6 * u, y + 1 * u), fill=cheek)
for ex in (8.5, 15.5):
    x, y = P(ex, 13)
    d.ellipse((x - 2.7 * u, y - 2.7 * u, x + 2.7 * u, y + 2.7 * u), fill="white")
    d.ellipse((x - 1.2 * u, y - 1.0 * u, x + 1.2 * u, y + 1.4 * u), fill=pupil)
x, y = P(12, 18.4)
d.arc((x - 2 * u, y - 1.6 * u, x + 2 * u, y + 1.6 * u), start=20, end=160, fill=dark, width=int(1.3 * u))
out = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(out, exist_ok=True)
img.resize((256, 256), Image.LANCZOS).save(os.path.join(out, "icon.png"))
img.save(os.path.join(out, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")
