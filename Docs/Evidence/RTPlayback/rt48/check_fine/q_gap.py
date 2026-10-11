# -*- coding: utf-8 -*-
"""C6 side number: gap between the time-interpolated boat pose and the pose from the shown (held) water, at 90 Hz, fine source."""
import json, math, numpy as np
import q_lib as Q
man = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
pairs = np.fromfile(Q.DATA + "/fine/pairs.bin", dtype="<f4").reshape(570, 2, 8192, 2).astype(np.float64)
interp = [p["interp"] for p in man["pairs"]]
HULL = np.array([-6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0])
def top_at(C, xq):
    X = C[:, 0]; Y = C[:, 1]; out = np.full(len(xq), np.nan)
    for n, x in enumerate(xq):
        s = ((X[:-1] - x) * (X[1:] - x) <= 0) & (X[:-1] != X[1:]); i = np.where(s)[0]
        if len(i): out[n] = (Y[i] + (Y[i + 1] - Y[i]) * (x - X[i]) / (X[i + 1] - X[i])).max()
    return out
res = {}
for seat in (556.0, 574.0):
    end_t = man["boat"][str(int(seat))]["clip_end_t"]; end_f = man["boat"][str(int(seat))]["clip_end_frame"]
    tb = []
    for f in range(3319, end_f + 2):
        C = pairs[f - 3319, 0].copy(); C[:, 0] += Q.X0B
        h = top_at(C, seat + HULL); tb.append((h.mean(), math.degrees(math.atan(np.polyfit(HULL, h, 1)[0]))))
    tb = np.array(tb)
    g = {"after_K": [0, 0], "held_before_K": [0, 0]}
    for t in 138.25 + np.arange(int(round((end_t - 138.25) * 90)) + 1) / 90:
        fr = (t - 138.25) * 24; p = int(math.floor(fr + 1e-9)); u = fr - p
        if p < 570 and interp[p]: continue
        key = "after_K" if 3319 + p >= 3745 else "held_before_K"
        lh = (1 - u) * tb[p, 0] + u * tb[min(p + 1, len(tb) - 1), 0]; lp = (1 - u) * tb[p, 1] + u * tb[min(p + 1, len(tb) - 1), 1]
        g[key][0] = max(g[key][0], abs(lh - tb[p, 0])); g[key][1] = max(g[key][1], abs(lp - tb[p, 1]))
    res[str(int(seat))] = g
    print(seat, g)
json.dump(res, open(Q.OUT + "/q_gap.json", "w"), indent=1)
