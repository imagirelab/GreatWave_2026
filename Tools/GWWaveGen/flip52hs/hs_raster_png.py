# -*- coding: utf-8 -*-
"""FLIP52B hires surfacing test: pictures of hs_surface_test.py's raster (py -3.10 -B, numpy + PIL; < 1 min). 2026-10-18 written new (Claude).
Reads Unity/Build/FLIP52B/hires/test_fFFFF/raster_fFFFF.npz (top-surface raster 0.1 m of each variant's mesh: height h and the interpolated
vertex normal hn at the hit = what the water shader shades with) and writes, next to it:
  shade_fFFFF.png    one panel per variant: shading of hn with a low sun + a glossy highlight (the grid shows up here as it does in the video)
  section_fFFFF.png  centre-section (symmetry-plane seam) points of every variant over the baseline, x 202-298 m
usage: py -3.10 -B hs_raster_png.py [frame=2112] [tag]
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 2112
TAG = ("_" + sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else ""
OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B/hires/test_f%04d" % FRAME
Z = np.load(OUT + "/raster_f%04d%s.npz" % (FRAME, TAG))
names = [str(n) for n in Z["names"]]
rec = json.load(open(OUT + "/hs_surface_test_f%04d%s.json" % (FRAME, TAG), encoding="utf8"))
L = np.array([-0.55, 0.45, 0.70]); L /= np.linalg.norm(L)            # low sun from upstream / side
V = np.array([0.25, 0.60, -0.76]); V /= np.linalg.norm(V)            # viewer roughly where a seat would look from
H = (L + V); H /= np.linalg.norm(H)
try:
    FONT = ImageFont.truetype("arial.ttf", 18)
except Exception:
    FONT = ImageFont.load_default()
panels = []
for nm in names:
    hn = Z["hn_" + nm].astype(np.float32)                      # (nx, nz, 3) x along tank, z lateral
    h = Z["h_" + nm]
    ok = h > -900
    ndl = np.clip((hn * L).sum(-1), 0, 1)
    spec = np.clip((hn * H).sum(-1), 0, 1) ** 120
    img = 0.15 + 0.55 * ndl + 0.9 * spec
    img = np.where(ok, img, 0.0)
    a = (np.clip(img, 0, 1) * 255).astype(np.uint8).T[::-1]   # rows = lateral (far at top), cols = x
    im = Image.fromarray(a, "L").convert("RGB")
    d = ImageDraw.Draw(im)
    v = rec["variants"].get(nm, {})
    lab = "%s  %s" % (nm, ("%.3f m vox" % v["pfs_voxel_m"]) if "pfs_voxel_m" in v else "recorded hero")
    d.rectangle([0, 0, im.width, 24], fill=(0, 0, 0))
    d.text((6, 3), lab, fill=(255, 255, 0), font=FONT)
    panels.append(im)
W = panels[0].width; Hh = panels[0].height
cols = 2
rows = (len(panels) + cols - 1) // cols
sheet = Image.new("RGB", (cols * W + (cols - 1) * 6, rows * Hh + (rows - 1) * 6), (40, 40, 40))
for i, im in enumerate(panels):
    sheet.paste(im, ((i % cols) * (W + 6), (i // cols) * (Hh + 6)))
sheet.save(OUT + "/shade_f%04d%s.png" % (FRAME, TAG))

# centre section
sx, sy = 12.0, 24.0                     # px per m (x), px per m (y, exaggerated x2)
x0, x1 = 202.0, 298.0
ys = [Z["seam_" + n][:, 1] for n in names]
ymin = min(float(a.min()) for a in ys if len(a)) - 0.5; ymax = max(float(a.max()) for a in ys if len(a)) + 0.5
im = Image.new("RGB", (int((x1 - x0) * sx) + 20, int((ymax - ymin) * sy) + 20), (255, 255, 255))
d = ImageDraw.Draw(im)
colors = [(0, 0, 0), (200, 0, 0), (0, 120, 0), (0, 0, 220), (200, 120, 0), (150, 0, 150), (0, 150, 150), (120, 120, 120)]
for i, n in enumerate(names):
    s = Z["seam_" + n]
    for x, y in s:
        px = 10 + (x - x0) * sx; py = 10 + (ymax - y) * sy
        d.point((px, py), fill=colors[i % len(colors)])
    d.text((14, 12 + 20 * i), n, fill=colors[i % len(colors)], font=FONT)
im.save(OUT + "/section_f%04d%s.png" % (FRAME, TAG))
print("wrote", OUT + "/shade_f%04d%s.png" % (FRAME, TAG), OUT + "/section_f%04d%s.png" % (FRAME, TAG), names)
