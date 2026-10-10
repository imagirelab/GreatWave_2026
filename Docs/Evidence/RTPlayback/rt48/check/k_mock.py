# -*- coding: utf-8 -*-
"""9. Mock Runtime の両眼の絵（verify/timing/c7_1/mock_botheyes.png）を自分で比べる：左右の輝度の標準偏差と、
右の絵を横にずらして最も合う所の差の平均（重なる所だけ、0〜255）。出力：out/k_mock.json"""
import numpy as np
from PIL import Image
from k_lib import *

a = np.asarray(Image.open(RT + "/verify/timing/c7_1/mock_botheyes.png").convert("RGB")).astype(float)
h, w, _ = a.shape
L, R = a[:, : w // 2], a[:, w // 2:]
lum = lambda x: (0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2])
res = dict(size=(w, h), std_left=float(lum(L).std() / 255), std_right=float(lum(R).std() / 255))
best = {}
for lim in (40, 320):
    sc = []
    for s in range(-lim, lim + 1):
        if s >= 0:
            d = np.abs(L[:, s:] - R[:, : R.shape[1] - s])
        else:
            d = np.abs(L[:, : L.shape[1] + s] - R[:, -s:])
        sc.append((float(d.mean()), s))
    best[str(lim)] = min(sc)
res["best_shift"] = best
print(res)
jsave(OUT + "/k_mock.json", res)
