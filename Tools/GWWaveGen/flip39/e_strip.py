# -*- coding: utf-8 -*-
"""FLIP39 E：焦点の列の断面の粒子を並べた図（崩れ方を目で確かめる）。py -3.10 e_strip.py <run_dir> <t0> <t1> <n> [x0 x1]"""
import sys, os, glob, json
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_plot import font
rd = sys.argv[1]; t0, t1, n = float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
_a = [q for q in sys.argv if not q.startswith("--")]
x0, x1 = (float(_a[5]), float(_a[6])) if len(_a) > 6 else (None, None)
rj = json.load(open(os.path.join(rd, "run.json"), encoding="utf8")); toff = float(rj["parms"].get("t_off", 0.0))
sd = sorted(glob.glob(os.path.join(rd, "sec", "z*")))
zpick = None
for a in sys.argv:
    if a.startswith("--z="):
        zpick = int(a.split("=")[1])
sdir = sd[0] if len(sd) == 1 else (min(sd, key=lambda q: abs(int(os.path.basename(q)[1:]) - zpick)) if zpick is not None else [s for s in sd if s.endswith("z-118")][0])
fs = {int(os.path.basename(f)[5:9]): f for f in glob.glob(os.path.join(sdir, "snap_*.npz"))}
frs = np.array(sorted(fs))
W, H = 520, 300
im = Image.new("RGB", (W * min(n, 4), H * ((n + 3) // 4)), (255, 255, 255)); d = ImageDraw.Draw(im)
off = 0.43 if float(rj["parms"]["Lz"]) <= 20 else 0.46
for i, tt in enumerate(np.linspace(t0, t1, n)):
    f = int(frs[np.argmin(np.abs((frs - 1) / 24.0 + toff - tt))])
    q = np.load(fs[f]); x, y = q["x"], q["y"] - off
    if x0 is None:
        k = np.argmax(y); xa, xb = x[k] - 60, x[k] + 40
    else:
        xa, xb = x0, x1
    ya, yb = -12.0, 24.0
    s = min((W - 20) / (xb - xa), (H - 30) / (yb - ya))
    ox, oy = (i % 4) * W + 10, (i // 4) * H + 25
    m = (x >= xa) & (x <= xb) & (y >= ya) & (y <= yb)
    for X, Y in zip(x[m], y[m]):
        px = ox + (X - xa) * s; py = oy + (yb - Y) * s
        d.point((px, py), fill=(40, 80, 160))
    d.line([(ox, oy + (yb - 0) * s), (ox + (xb - xa) * s, oy + (yb - 0) * s)], fill=(200, 120, 120))
    d.line([(ox, oy + (yb - 1.83) * s), (ox + (xb - xa) * s, oy + (yb - 1.83) * s)], fill=(230, 200, 120))
    d.text((ox, oy - 22), "t=%.2f s  x %.0f〜%.0f m（縦横同じ縮尺）" % ((f - 1) / 24.0 + toff, xa, xb), fill=(0, 0, 0), font=font(13))
out = os.path.join(rd, "strip_%s%s.png" % (os.path.basename(rd.rstrip("/\\")), ("_z%+04d" % zpick) if zpick is not None else ""))
im.save(out); print(out)
