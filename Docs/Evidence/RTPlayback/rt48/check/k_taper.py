# -*- coding: utf-8 -*-
"""8. x の両端の下ろし（x 100〜200 m・825〜925 m で高さに 1→0 の重み）が、座席 556・574 m の目から見える所にあるか。
各コマで、目（船の上下 + 1.2 m）から前（−x）と後ろ（+x）を見て、手前の水より高い角に出る（隠れない）点のうち、下ろしの帯の点の数と、
そこで見せている高さと計算の高さの差の最大。出力：out/k_taper.json"""
import numpy as np
from k_lib import *

my = MyFrames(); rows = jload(OUT + "/k_r3.json")["rows"]
res = {}
for seat in (556.0, 574.0):
    out = dict(front_visible_frames=0, back_visible_frames=0, back_max_dy=0.0, front_max_dy=0.0, back_true_absmax=0.0, front_frames=[], clip_end=None)
    fend = 3771 if seat == 556.0 else 3796      # 船からのクリップの終わり（焼きの表。k_r3 の overturn_on_hull の 1 コマ前と同じ）
    out["clip_end"] = fend
    for f in range(F0, fend + 1):
        P = densify(my.main_of(f), 0.25)
        h = rows[f - F0]["heave%d" % seat]
        eye = h + 1.2
        Yd = P[:, 1] * taper_w(P[:, 0])
        for side in ("front", "back"):
            sel = P[:, 0] < seat - 0.5 if side == "front" else P[:, 0] > seat + 0.5
            x = P[sel, 0]; yd = Yd[sel]; yt = P[sel, 1]
            order = np.argsort(np.abs(x - seat))
            x, yd, yt = x[order], yd[order], yt[order]
            el = np.arctan2(yd - eye, np.abs(x - seat))
            vis = el > np.maximum.accumulate(np.r_[-np.inf, el[:-1]])
            tz = (x < 200.0) | (x > 825.0)
            v = vis & tz
            if v.any():
                out[side + "_visible_frames"] += 1
                if side == "front":
                    out["front_frames"].append(f)
                out[side + "_max_dy"] = max(out[side + "_max_dy"], float(np.abs(yd[v] - yt[v]).max()))
            if side == "back":
                out["back_true_absmax"] = max(out["back_true_absmax"], float(np.abs(yt[tz]).max()) if tz.any() else 0.0)
    res[str(int(seat))] = out
    print(seat, out)
jsave(OUT + "/k_taper.json", res)
