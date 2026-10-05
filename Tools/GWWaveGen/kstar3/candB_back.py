# -*- coding: utf-8 -*-
"""Q20 candidate B: the rounded back (Q17 A1 idea, re-designed): the back of a row is rebuilt from the painting-locked
junction near the crest down to the back sea as a heading-angle curve: a round cap (R ~ 0.21 H) that turns the surface
to ~50 deg at 0.9 H, a neck, a steep wall that keeps turning (no straight run), and a concave foot into the flat sea."""
import numpy as np
from scipy.interpolate import PchipInterpolator
from candB_common import *
from candB_geom import resample

# default heading program (deg of descent going backward) against arc length s (in units of H/20.75 m)
BACK_S = [0.0, 3.1, 4.6, 5.9, 9.0, 13.0, 18.0]
BACK_PHI = [None, 40.0, 50.0, 71.0, 78.0, 84.0, 89.0]


def back_curve(PL, phiL, H, s_knots=BACK_S, phi_knots=BACK_PHI, yfoot_frac=0.12, ds=0.02, scale=None):
    """curve from the junction PL going backward/down to y = 0; returns points ordered junction -> foot."""
    sc = (H / 20.75) if scale is None else scale
    sk = np.array(s_knots) * sc
    pk = np.array([phiL if v is None else v for v in phi_knots], float)
    pk[0] = phiL
    # keep monotone increase at the start
    for i in range(1, len(pk)):
        pk[i] = max(pk[i], pk[i - 1] + 0.5)
    f = PchipInterpolator(sk, pk, extrapolate=False)
    pts = [np.array(PL, float)]; s = 0.0
    yf = yfoot_frac * H
    phi = phiL
    while pts[-1][1] > yf and s < 5 * H:
        phi = float(f(min(s, sk[-1])))
        th = np.radians(phi)
        pts.append(pts[-1] + ds * np.array([-np.cos(th), -np.sin(th)])); s += ds
    phiB = np.radians(max(phi, 20.0)); y1 = pts[-1][1]
    if y1 > 1e-3:
        Lf = y1 * phiB / (1 - np.cos(phiB)); nf = max(int(Lf / ds), 4)
        for k in range(1, nf + 1):
            th = phiB * (1 - (k - 0.5) / nf)
            pts.append(pts[-1] + (Lf / nf) * np.array([-np.cos(th), -np.sin(th)]))
    P = np.array(pts)
    # exact landing on y = 0 (vertical rescale of the foot part only)
    if P[-1, 1] != 0:
        m = P[:, 1] < y1 + 1e-9
        if m.any() and y1 > 1e-6:
            P[m, 1] = P[m, 1] * (y1 / max(y1 - P[-1, 1], 1e-9)) - P[-1, 1] * (y1 / max(y1 - P[-1, 1], 1e-9))
            P[m, 1] = np.clip(P[m, 1], 0, None)
    P[-1, 1] = 0.0
    return P


def junction_heading(a, y, jL, side=+1):
    """heading (deg) of the locked side at the junction column jL (side=+1: toward higher columns)."""
    k = 2
    t = np.array([a[jL + side * k] - a[jL], y[jL + side * k] - y[jL]]) * side
    return float(np.degrees(np.arctan2(t[1], t[0])))


def rebuild_back(a, y, jL, H=None, n_flat=18, **kw):
    """replace columns 0..jL-1 of a row (flat back sea + back) with a designed back ending at column jL."""
    H = y[jL] if H is None else H
    hf = junction_heading(a, y, jL, +1)          # front heading at the junction (deg, + = rising toward +a)
    phiL = max(hf, -15.0)                        # going backward along the front tangent (G1): descent angle = front heading
    P = back_curve(np.array([a[jL], y[jL]]), phiL, H, **kw)[::-1]   # foot -> junction
    Pb = resample(P, jL - n_flat + 1)
    a2 = a.copy(); y2 = y.copy()
    a2[n_flat:jL + 1] = Pb[:, 0]; y2[n_flat:jL + 1] = Pb[:, 1]
    a0 = min(a[0], Pb[0, 0] - 30.0)
    a2[:n_flat + 1] = np.linspace(a0, Pb[0, 0], n_flat + 1); y2[:n_flat + 1] = 0.0
    return a2, y2


def back_curve2(PL, phiL, H, s_knots, phi_knots, ds=0.02, conc_shape=1.0):
    """convex part: heading knots (deg) against arc s (m, already scaled) up to the inflection (last knot), then a
    concave foot whose heading falls from the inflection heading to 0 exactly when the curve reaches y = 0."""
    sk = np.array(s_knots, float); pk = np.array(phi_knots, float); pk[0] = phiL
    for i in range(1, len(pk)):
        pk[i] = max(pk[i], pk[i - 1] + 0.5)
    f = PchipInterpolator(sk, pk)
    n1 = int(sk[-1] / ds) + 1
    ss = np.linspace(0, sk[-1], n1); th = np.radians(f(ss))
    d = np.stack([-np.cos(th), -np.sin(th)], -1)
    P1 = PL[None, :] + np.r_[np.zeros((1, 2)), np.cumsum(0.5 * (d[1:] + d[:-1]) * (ss[1] - ss[0]), 0)]
    yk = P1[-1, 1]; phk = th[-1]
    if yk <= 0.05:
        cut = np.nonzero(P1[:, 1] <= 0)[0]
        P1 = P1[:cut[0] + 1] if len(cut) else P1
        P1[-1, 1] = 0.0
        return P1
    x = np.linspace(0, 1, 400)
    g = 1 - (x * x * (3 - 2 * x)) ** conc_shape if conc_shape != 1.0 else 1 - x * x * (3 - 2 * x)
    ph = phk * g
    I = np.trapz(np.sin(ph), x)
    Lc = yk / max(I, 1e-6)
    d2 = np.stack([-np.cos(ph), -np.sin(ph)], -1) * Lc
    P2 = P1[-1][None, :] + np.r_[np.zeros((1, 2)), np.cumsum(0.5 * (d2[1:] + d2[:-1]) * (x[1] - x[0]), 0)]
    P2[:, 1] = np.maximum(P2[:, 1], 0.0); P2[-1, 1] = 0.0
    return np.vstack([P1, P2[1:]])


def rebuild_back2(a, y, jL, s_knots, phi_knots, H=None, n_flat=18, conc_shape=1.0, scale_s=True):
    H = y[jL] if H is None else H
    hf = junction_heading(a, y, jL, +1)
    phiL = max(hf, -15.0)
    sk = np.array(s_knots, float) * ((H / 20.75) if scale_s else 1.0)
    P = back_curve2(np.array([a[jL], y[jL]]), phiL, H, sk, phi_knots, conc_shape=conc_shape)[::-1]
    Pb = resample(P, jL - n_flat + 1)
    a2 = a.copy(); y2 = y.copy()
    a2[n_flat:jL + 1] = Pb[:, 0]; y2[n_flat:jL + 1] = Pb[:, 1]
    a0 = min(a[0], Pb[0, 0] - 30.0)
    a2[:n_flat + 1] = np.linspace(a0, Pb[0, 0], n_flat + 1); y2[:n_flat + 1] = 0.0
    return a2, y2
