# -*- coding: utf-8 -*-
"""見本 B の点検用の並べ図（views の 7 視点を 3×3、または tt の 12 方位を 4×3）。使い方：py -3.10 s01b_grid.py <出力名> [views|tt] [ts]"""
import os
import sys

from PIL import Image

B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/"
name = sys.argv[1]
kind = sys.argv[2] if len(sys.argv) > 2 else "views"
ts = sys.argv[3] if len(sys.argv) > 3 else "t120"
if kind == "views":
    V = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
    files = [B + f"{name}/views/{v}_{ts}_clawfree.png" for v in V]
    nc, tw, th = 3, 640, 360
else:
    files = [B + f"{name}/tt/{ts}_az{a:03d}_noclaws.png" for a in range(0, 360, 30)]
    nc, tw, th = 4, 480, 270
nr = (len(files) + nc - 1) // nc
g = Image.new("RGB", (nc * tw, nr * th), (30, 30, 30))
for k, f in enumerate(files):
    if os.path.exists(f):
        g.paste(Image.open(f).convert("RGB").resize((tw, th), Image.LANCZOS), ((k % nc) * tw, (k // nc) * th))
out = B + f"{name}/grid_{kind}_{ts}.png"
g.save(out)
print(out)
