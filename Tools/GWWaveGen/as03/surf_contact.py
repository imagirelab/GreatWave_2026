# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：描画の一覧（内部の確かめ用。Git 対象外の surface/tmp へ）。
使い方：py -3.10 -B surf_contact.py <描画のフォルダー> <出力の png> [crest|views|both] [w]"""
import os
import sys

import cv2
import numpy as np

d, out = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "both"
W = int(sys.argv[4]) if len(sys.argv) > 4 else 640
views = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
tiles = []
if mode in ("views", "both"):
    for v in views:
        p = os.path.join(d, "views", v + "_t120_clawfree.png")
        if not os.path.exists(p):
            p = os.path.join(d, "views", v + "_t120_claws.png")
        if os.path.exists(p):
            tiles.append((v, cv2.imread(p)))
if mode in ("crest", "both"):
    for az in range(0, 360, 45):
        p = os.path.join(d, "crest", "t120_az%03d_clawfree.png" % az)
        if os.path.exists(p):
            tiles.append(("az%03d" % az, cv2.imread(p)))
h = W * 9 // 16
cols = 4 if len(tiles) > 6 else 3
rows = (len(tiles) + cols - 1) // cols
sheet = np.full((rows * h, cols * W, 3), 255, np.uint8)
for k, (lab, im) in enumerate(tiles):
    r, c = divmod(k, cols)
    sm = cv2.resize(im, (W, h), interpolation=cv2.INTER_AREA)
    cv2.putText(sm, lab, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    sheet[r * h:(r + 1) * h, c * W:(c + 1) * W] = sm
os.makedirs(os.path.dirname(out), exist_ok=True)
cv2.imwrite(out, sheet)
print(out, sheet.shape)
