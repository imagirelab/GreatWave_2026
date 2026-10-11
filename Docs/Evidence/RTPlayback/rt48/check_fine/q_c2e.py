# -*- coding: utf-8 -*-
"""C2 (e) sensitivity: lip reach/thickness on the fine surface at 3740-3744 read (A) on raw contour vertices, (B) on the face resampled
at 0.25 m (spacing used by the FLIP42 reading), (C) resampled at 0.125 m."""
import json, numpy as np
import q_lib as Q
OFF = Q.still_offset_fine(); LC = 135.46329754326246
SEC_LO, SEC_HI = 457.0 - Q.XP, 998.5 - Q.XP
cm = json.load(open(Q.DATA + "/coarse/manifest.json", encoding="utf8"))
crest = {r["frame"]: r["crest_x"] for r in cm["frames"]}
def cross(seg, x):
    ys = []
    for a, b in zip(seg[:-1], seg[1:]):
        if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
            ys.append(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
    return ys
def lip(face, vox=0.5):
    xx = face[:, 0]
    for i in range(1, len(xx) - 1):
        if xx[i] >= xx[i - 1] and xx[i] > xx[i + 1]:
            j = i + 1
            while j < len(xx) and xx[j] <= xx[i]: j += 1
            seg = face[i:j]; iw = i + int(np.argmin(seg[:, 0]))
            if xx[i] - face[iw, 0] >= vox:
                xt, xw = xx[i], face[iw, 0]; xm = 0.5 * (xt + xw)
                up = cross(face[:i + 1], xm); lo = cross(face[i:iw + 1], xm)
                return dict(reach=float(xt - xw), thick=float(max(up) - max(lo)) if up and lo else None, x_tip=float(xt))
    return None
res = {}
for kind in ("fine", "solver"):
    for f in range(3738, 3745):
        if kind == "fine":
            phi, xs, ys = Q.load_phi(f); sel = (xs >= SEC_LO - 1e-6) & (xs <= SEC_HI + 1e-6)
            P = Q.main_curve(phi[:, sel], xs[sel], ys - OFF)
        else:
            S, sx, sy = Q.load_sec(f); sy = sy - Q.OFF_R3; j0 = int(np.searchsorted(sy, -25)); P = Q.main_curve(S[j0:], sx, sy[j0:])
        m = np.abs(P[:, 0] - crest[f]) <= 40; ic = np.where(m)[0][int(np.argmax(P[m, 1]))]; xc = P[ic, 0]
        fwd = P[ic:]; end = len(fwd)
        for j in range(1, len(fwd)):
            if fwd[j, 1] <= 0 or abs(fwd[j, 0] - xc) > LC: end = j + 1; break
        row = {}
        for nm, face in (("raw", fwd[:end]), ("rs0.25", Q.resample_step(fwd[:end], 0.25)), ("rs0.125", Q.resample_step(fwd[:end], 0.125))):
            row[nm] = lip(face)
        res["%s_%d" % (kind, f)] = row
        print(kind, f, {k: (None if v is None else (round(v["reach"], 3), v["thick"] and round(v["thick"], 3))) for k, v in row.items()})
json.dump(res, open(Q.OUT + "/q_c2e.json", "w"), indent=1)
