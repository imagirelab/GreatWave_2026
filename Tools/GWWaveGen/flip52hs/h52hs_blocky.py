# -*- coding: utf-8 -*-
"""Blockiness of captured frames (JPEG capture vs H.264 mp4 frame), read only. 2026-10-18 written new (Claude).
For each pixel phase p = 0..15 (absolute image coordinates), mean |luma step| between column/row with x % 16 == p and the next one,
over the water (rows 600..1079). A block codec shows peaks at p = 7 and 15 (8-px blocks) or 15 (16-px macroblocks).
py -3.10 -B h52hs_blocky.py img1 img2 ..."""
import sys
import numpy as np
from PIL import Image
for p in sys.argv[1:]:
    a = np.asarray(Image.open(p).convert("L"), np.float64)
    y0 = 600
    dh = np.abs(np.diff(a[y0:, :], axis=1))           # step between x and x+1
    dv = np.abs(np.diff(a, axis=0))[y0:, :]            # step between y and y+1 (absolute y = y0 + i)
    ph = [dh[:, np.arange(dh.shape[1]) % 16 == k].mean() for k in range(16)]
    pv = [dv[(np.arange(y0, y0 + dv.shape[0]) % 16) == k, :].mean() for k in range(16)]
    med_h, med_v = np.median(ph), np.median(pv)
    print("%-22s mean_step=%.3f  h-steps/median at x%%16=7,15: %.2f %.2f   v-steps/median at y%%16=7,15: %.2f %.2f  max other h %.2f v %.2f" % (
        p.replace("\\", "/").split("/")[-1], np.mean(ph), ph[7] / med_h, ph[15] / med_h, pv[7] / med_v, pv[15] / med_v,
        max(ph[k] for k in range(16) if k not in (7, 15)) / med_h, max(pv[k] for k in range(16) if k not in (7, 15)) / med_v))
