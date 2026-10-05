# -*- coding: utf-8 -*-
"""explicit crest arc for rows whose back near the crest is painting-locked: from the last locked crest vertex a
circle of radius R continues the back tangent over the top and eases into the free front (G1), then the free
vertices are clamped under the painting silhouette."""
import numpy as np
from candB_common import *
from candB_geom import resample, clamp_row_dir, row_inside, sanitize, capped_fair


def crest_arc(a, y, cc, lk, R=1.1, j2_off=18, margin=0.5):
    a = a.copy(); y = y.copy()
    jt = int(np.argmax(y[:200]))
    # last locked vertex at/after the crest on the back side run
    # the crest vertex (or the last locked back vertex before it) is the start; everything after it is re-shaped
    jl = jt
    while jl > jt - 6 and not lk[jl]:
        jl -= 1
    if not lk[jl]:
        jl = jt
    hb = np.degrees(np.arctan2(y[jl] - y[jl - 1], a[jl] - a[jl - 1]))
    j2 = min(jl + j2_off, 199)
    hf = np.degrees(np.arctan2(y[j2 + 1] - y[j2], a[j2 + 1] - a[j2]))
    if hb - hf < 5:
        return a, y
    # circle from P(jl) with heading hb, turning clockwise until heading hf
    ds = 0.01; P = [np.array([a[jl], y[jl]])]; h = hb
    while h > hf and len(P) < 5000:
        h -= np.degrees(ds / R)
        th = np.radians(h); P.append(P[-1] + ds * np.array([np.cos(th), np.sin(th)]))
    P = np.array(P)
    # then a straight/eased connection to P(j2) keeping G1 approximately (Hermite)
    p0 = P[-1]; p1 = np.array([a[j2], y[j2]])
    L = np.linalg.norm(p1 - p0)
    t0 = np.array([np.cos(np.radians(hf)), np.sin(np.radians(hf))]); t1 = t0
    s = np.linspace(0, 1, 40)[:, None]
    h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s; h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
    Q = h00 * p0 + h10 * t0 * L + h01 * p1 + h11 * t1 * L
    curve = np.vstack([P, Q[1:]])
    # the circle may overshoot past P(j2) horizontally: keep only if monotone-ish
    new = resample(curve, j2 - jl + 1)
    a2 = a.copy(); y2 = y.copy()
    a2[jl:j2 + 1] = new[:, 0]; y2[jl:j2 + 1] = new[:, 1]
    free = np.zeros(NU, bool); free[jl + 1:j2] = True
    a2, y2, _ = clamp_row_dir(a2, y2, cc, free, margin=margin, step=0.005)
    a2, y2 = sanitize(a2, y2, keep=~free)
    return a2, y2


def crest_best(a, y, cc, lk, Rs=(0.8, 1.1, 1.4), offs=(18, 26), margin=0.3):
    import rubric_check as RC
    jt = int(np.argmax(y[:200]))
    if lk[jt:200].sum() >= 15:           # the lip top itself is the painted outline (132/131): leave it
        return a, y
    q0 = RC.corner_q17(a, y, 200)
    best = (max(0, q0["fold_deg"] - 11) + 5 * max(0, 1.2 - q0["Rmin_m"]), a, y)
    for R in Rs:
        for off in offs:
            a2, y2 = crest_arc(a, y, cc, lk, R=R, j2_off=off, margin=margin)
            q = RC.corner_q17(a2, y2, 200)
            sc = max(0, q["fold_deg"] - 11) + 5 * max(0, 1.2 - q["Rmin_m"])
            if sc < best[0] - 1e-6:
                best = (sc, a2, y2)
    return best[1], best[2]
