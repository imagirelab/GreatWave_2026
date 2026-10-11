# -*- coding: utf-8 -*-
"""C2 (c) reverse direction: frames where solver water lies >= 0.49 m from fine water, and where."""
import json, numpy as np
from scipy import ndimage
import q_lib as Q
OFF = Q.still_offset_fine(); H = 0.125
cm = json.load(open(Q.DATA + "/coarse/manifest.json", encoding="utf8"))
crest = {r["frame"]: r["crest_x"] for r in cm["frames"]}
def drop(M):
    lab, n = ndimage.label(M); keep = set(np.unique(lab[0])) - {0}
    sz = ndimage.sum(M, lab, np.arange(1, n + 1)) * H * H
    d = [i + 1 for i in range(n) if (i + 1) not in keep and sz[i] < 0.25]
    return M & ~np.isin(lab, d) if d else M
rows = []
for f in range(3319, 3797):
    phi, xs, ys = Q.load_phi(f)
    m = (xs >= crest[f] - 20) & (xs <= crest[f] + 20)
    Fw = drop(phi[:, m] < 0)
    X = np.broadcast_to(xs[m][None, :], Fw.shape); Yh = np.broadcast_to((ys - OFF)[:, None], Fw.shape)
    S, sx, sy = Q.load_sec(f); eta, xh = Q.load_hf(f)
    Ya = Yh + Q.OFF_R3
    ins = (X >= sx[0]) & (X <= sx[-1])
    Sw = np.zeros(X.shape, bool)
    Sw[ins] = Q.bilinear(S, sx, sy, X[ins], Ya[ins]) < 0
    Sw[~ins] = Ya[~ins] < np.interp(X[~ins], xh, eta)
    Sw = drop(Sw)
    dF = ndimage.distance_transform_edt(~Fw) * H
    dd = np.where(Sw, dF, 0)
    if dd.max() >= 0.49:
        j, i = np.unravel_index(np.argmax(dd), dd.shape)
        rows.append([f, float(dd.max()), float(X[j, i]), float(Yh[j, i]), float(X[j, i] - crest[f])])
print(len(rows), rows[:20])
json.dump(rows, open(Q.OUT + "/q_c2c_rev.json", "w"))
