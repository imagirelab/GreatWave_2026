# -*- coding: utf-8 -*-
"""美術の見本06 の段の行：粘土の画（rows_clay.py の出力）から、決めた視点だけを大きく並べる下見（候補を上下に）。
py -3.10 -B Tools/GWWaveGen/as06/rows_cmp.py <out.png> <clay_dir> <kind,kind,...> <view,view,...> [clay|tint]"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rows_clay as RC  # noqa: E402

out, d, kinds, views = sys.argv[1], sys.argv[2], sys.argv[3].split(","), sys.argv[4].split(",")
suf = sys.argv[5] if len(sys.argv) > 5 else "clay"
tw, th = 640, 360
img = Image.new("RGB", (tw * len(views), th * len(kinds)), (255, 255, 255))
for ci, v in enumerate(views):
    box = RC.crop_box(d, kinds, v)
    for ri, k in enumerate(kinds):
        p = os.path.join(d, "%s_%s_%s.png" % (k, v, suf))
        if os.path.isfile(p):
            img.paste(Image.open(p).convert("RGB").crop(box).resize((tw, th), Image.LANCZOS), (ci * tw, ri * th))
img.save(out)
