# -*- coding: utf-8 -*-
"""6d. 船からの動画の時刻のずれ：測った輪郭の行を、計算の時刻を −2/24〜+2/24 s ずらした予想と比べ、どのずれが最も合うか（150 s から）。
出力：out/k_video_boat_timing.json"""
import numpy as np
from k_lib import *
import k_video as kv

rows = jload(OUT + "/k_r3.json")["rows"]
res = {}
for tag, seat in (("boat556", "556"), ("boat574", "574")):
    V = jload(OUT + f"/k_video_{tag}.json")["rows"]
    hm = np.array([r["heave" + seat] for r in rows]); pm = np.array([r["pitch" + seat] for r in rows])
    S = float(seat); f_px = 540 / np.tan(np.radians(30))
    tend = V[-1]["t"]
    err = {dk: [] for dk in (-2, -1, 0, 1, 2)}
    for o in V:
        if o["t"] < 150.0:
            continue
        for dk in err:
            t = min(max(o["t"] + dk / 24.0, T0), tend)
            k, w, ip = kv.state(t)
            C, loops, f, ub = kv.displayed_curves(t)
            if k >= 570:
                h, p = hm[-1], pm[-1]
            elif ip:
                h, p, _ = boat_pose(C, S)
            else:
                h = hm[k] + (hm[k + 1] - hm[k]) * w; p = pm[k] + (pm[k + 1] - pm[k]) * w
            th = np.radians(p); camX = S - 1.2 * np.sin(th); camY = h + 1.2 * np.cos(th)
            Pa = np.vstack([C] + [L["pts"] for L in loops if L["phase"] == -1])
            a = Pa[:, 0] < camX - 0.5
            e = np.arctan2(Pa[a, 1] * taper_w(Pa[a, 0]) - camY, camX - Pa[a, 0]).max()
            err[dk].append(o["v_meas"] - (540 - f_px * np.tan(e + th)))
    rms = {str(dk): float(np.sqrt(np.mean(np.square(v)))) for dk, v in err.items()}
    res[tag] = dict(n=len(err[0]), rms_px=rms)
    print(tag, res[tag])
jsave(OUT + "/k_video_boat_timing.json", res)
