"""Genera l'icona dell'app (PNG e ICO) in flight_analyzer/resources. Serve Pillow solo qui.

Icona: risposta al gradino (setpoint, risposta con sovraelongazione, fascia di
assestamento) su fondo blu, con il logo del team Zefiro in basso a destra.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[0] / "flight_analyzer" / "resources"
OUT.mkdir(parents=True, exist_ok=True)
S = 1024

BLUE = "#1864ab"
YELLOW = "#ffd43b"
W = "white"

fig = plt.figure(figsize=(S / 100, S / 100), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.set_axis_off()
fig.patch.set_alpha(0)
ax.add_patch(FancyBboxPatch((4, 4), 92, 92, boxstyle="round,pad=0,rounding_size=20", fc=BLUE, ec="none"))

# area del grafico
x0, x1 = 14, 88  # asse dei tempi
y0, y1 = 16, 87  # zero e cima dell'asse verticale
ystep = 70  # livello del setpoint (valore 1)
ts = 21  # istante del gradino

# griglia leggera
for gx in np.linspace(ts, x1, 5)[1:]:
    ax.plot([gx, gx], [y0, y1 - 4], color=W, lw=1.5, alpha=0.18)
for gy in (y0 + (ystep - y0) * 0.5, ystep):
    ax.plot([x0, x1], [gy, gy], color=W, lw=1.5, alpha=0.18)

# fascia di assestamento ±5%
band = 0.05 * (ystep - y0)
ax.add_patch(Rectangle((ts, ystep - band), x1 - ts, 2 * band, fc=W, ec="none", alpha=0.16))

# assi
ax.annotate("", xy=(x1 + 3, y0), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=W, lw=6, mutation_scale=40))
ax.annotate("", xy=(x0, y1 + 3), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=W, lw=6, mutation_scale=40))

# setpoint a gradino (tratteggiato)
ax.plot([x0, ts, ts, x1], [y0, y0, ystep, ystep], color=W, lw=5, ls=(0, (2.2, 1.6)), solid_capstyle="round",
        dash_capstyle="round", alpha=0.95)

# risposta del secondo ordine (smorzamento 0,45)
zeta, wn = 0.45, 1.0
tt = np.linspace(0, 16, 600)
wd = wn * np.sqrt(1 - zeta**2)
resp = 1 - np.exp(-zeta * wn * tt) * (np.cos(wd * tt) + zeta / np.sqrt(1 - zeta**2) * np.sin(wd * tt))
xs = ts + (x1 - ts) * tt / tt[-1]
ys = y0 + (ystep - y0) * resp
ax.plot(xs, ys, color="#0b3d70", lw=19, solid_capstyle="round", alpha=0.55)  # ombra
ax.plot(xs, ys, color=YELLOW, lw=12, solid_capstyle="round")
k = int(np.argmax(resp))
ax.plot([xs[k], xs[k]], [ystep, ys[k]], color=W, lw=2.5, alpha=0.8)  # sovraelongazione
ax.plot(xs[k], ys[k], "o", ms=17, mfc=W, mec=YELLOW, mew=5)

base_png = OUT / "_base.png"
fig.savefig(base_png, transparent=True)
plt.close(fig)
icon = Image.open(base_png).convert("RGBA").resize((S, S), Image.LANCZOS)
base_png.unlink()

# logo Zefiro in un badge bianco in basso a destra
team = Image.open(HERE / "logo_team_originale.png").convert("RGBA")
D = int(S * 0.25)
big = D * 4
b = Image.new("RGBA", (big, big), (0, 0, 0, 0))
d = ImageDraw.Draw(b)
d.ellipse((0, 0, big - 1, big - 1), fill=(255, 255, 255, 255), outline=(206, 212, 218, 255), width=big // 40)
lg = team.copy()
lg.thumbnail((int(big * 0.80), int(big * 0.80)), Image.LANCZOS)
b.alpha_composite(lg, ((big - lg.width) // 2, (big - lg.height) // 2))
b = b.resize((D, D), Image.LANCZOS)
# nello spazio libero sotto la risposta, appena sopra l'asse dei tempi, in basso a destra
right = int(S * 0.905)
bottom = int(S * (1 - 0.205))
icon.alpha_composite(b, (right - D, bottom - D))

icon = icon.resize((512, 512), Image.LANCZOS)
icon.save(OUT / "icona.png")
icon.save(OUT / "icona.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icona creata in", OUT)
