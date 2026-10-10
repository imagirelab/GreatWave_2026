# -*- coding: utf-8 -*-
"""RT48：焼いたデータ（pairs.bin・loops.bin）を、縦横同じ縮尺の横からの線で描いて確かめる（py -3.10、Pillow）。見た目の判定ではなく、焼きの読み書きの確かめ。
使い方: py -3.10 r_plot_check.py <data/元 のフォルダー> <出力 png> <コマ:x0:x1>[,...]
A（コマ k の線）を濃い青、B（コマ k+1 の線）を橙、閉じた水を緑、囲んだ空気を白（黒の縁）、座席 556・574 m を灰の点線で描く。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw

d, outp, spec = sys.argv[1], sys.argv[2], sys.argv[3]
m = json.load(open(os.path.join(d, "manifest.json"), encoding="utf8"))
P = np.fromfile(os.path.join(d, "pairs.bin"), "<f4").reshape(m["files"]["pairs"]["shape"])
Lp = np.fromfile(os.path.join(d, "loops.bin"), "<f4").reshape(-1, 2)
li = {r["frame"]: r["loops"] for r in m["loops_index"]}
X0 = m["coords"]["origin_x_rel"]; F0 = m["time"]["first_frame"]
panels = [tuple(float(v) for v in s.split(":")) for s in spec.split(",")]
W, PH, Y0, Y1 = 1400, 260, -5.0, 12.0
img = Image.new("RGB", (W, PH * len(panels)), "white")
dr = ImageDraw.Draw(img)
for k, (f, xa, xb) in enumerate(panels):
    f = int(f); p = min(f - F0, P.shape[0] - 1); use_b = f - F0 > P.shape[0] - 1
    s = min((W - 20) / (xb - xa), (PH - 30) / (Y1 - Y0))
    oy = PH * k + 25

    def tp(x, y):
        return (10 + (x - xa) * s, oy + (Y1 - y) * s)
    dr.line([tp(xa, 0), tp(xb, 0)], fill=(200, 200, 200))
    for xs in (556.0, 574.0):
        for yy in np.arange(Y0, Y1, 0.6):
            dr.line([tp(xs, yy), tp(xs, yy + 0.3)], fill=(150, 150, 150))
    A = P[p, 1 if use_b else 0].astype(float); B = P[p, 1].astype(float)
    for C, col, wdt in ((B, (230, 140, 30), 1), (A, (20, 40, 160), 2)):
        pts = [tp(x + X0, y) for x, y in C if xa - 5 <= x + X0 <= xb + 5]
        if len(pts) > 1:
            dr.line(pts, fill=col, width=wdt)
    for (o, n, ph, ar) in li.get(f, []):
        q = Lp[o:o + n].astype(float)
        if q[:, 0].max() + X0 < xa or q[:, 0].min() + X0 > xb:
            continue
        dr.polygon([tp(x + X0, y) for x, y in q], fill=(255, 255, 255) if ph == 1 else (40, 170, 90), outline=(0, 0, 0))
    r = m["pairs"][p]
    dr.text((12, PH * k + 4), "%s  frame %d  t=%.3f s  pair interp=%s (%s)  marks=%s  x %g-%g m  (1 m = %.1f px)" % (
        m["source"], f, (f - 1) / 24.0, r["interp"], r["reason"], r["marks"], xa, xb, s), fill=(0, 0, 0))
img.save(outp)
print("saved", outp)
