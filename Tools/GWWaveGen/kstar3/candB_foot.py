# -*- coding: utf-8 -*-
"""Q20 candidate B, step 3: the 3 m vertical plinth at the foot becomes a face that flows into a front trough.
Only the part below the painting's horizon changes (free in the painting view); the depth grows with the row height
(D = 0.22 H_r); at the seat boat (c ~ -1.4, bow waterline -1.37 m at a 14.4) the trough is shaped to meet the bow."""
import numpy as np
from candB_common import *
from candB_geom import resample_w

SEAT_C = -1.4
BOW_A, BOW_Y = 14.4, -1.37


def trough_profile(a, a_b, a_e, D):
    """0 -> -D (at a_b) -> 0 (at a_e): cosine rise behind a_b; returns y(a) for a >= a_b."""
    u = np.clip((a - a_b) / max(a_e - a_b, 1e-6), 0, 1)
    return -D * 0.5 * (1 + np.cos(np.pi * u))


def rebuild_foot(a, y, cc, jf=379, Hr=None, depth_rel=0.22, seat_w=0.0, a_end_min=None):
    """replace columns jf+1..399: from the face point (col jf) along its tangent into the trough and the front sea."""
    Hr = y[:200].max() if Hr is None else Hr
    Pf = np.array([a[jf], y[jf]])
    t = np.array([a[jf] - a[jf - 3], y[jf] - y[jf - 3]]); t /= max(np.linalg.norm(t), 1e-9)
    if t[1] > -0.2:                      # make sure the face keeps going down
        t = np.array([0.6, -0.8])
    # no plinth: the face leaves the painted part at most 65 deg steep and flows into the trough
    ang = np.degrees(np.arctan2(-t[1], t[0]))
    if ang > 65.0:
        t = np.array([np.cos(np.radians(65.0)), -np.sin(np.radians(65.0))])
    D = depth_rel * Hr
    a_b = Pf[0] + max(4.0, 0.95 * (Pf[1] + D))
    a_e = a_b + 10.0
    if seat_w > 0:
        a_bs = Pf[0] + max(4.0, 0.95 * (Pf[1] + 2.0)); a_es = a_bs + 9.0
        g = 0.5 * (1 + np.cos(np.pi * np.clip((BOW_A - a_bs) / (a_es - a_bs), 0, 1)))
        Ds = -BOW_Y / max(g, 0.2)
        D = (1 - seat_w) * D + seat_w * Ds; a_b = (1 - seat_w) * a_b + seat_w * a_bs; a_e = (1 - seat_w) * a_e + seat_w * a_es
    # face -> bottom: cubic Hermite with the face tangent at the start and a level tangent at the bottom
    L = np.hypot(a_b - Pf[0], Pf[1] + D)
    s = np.linspace(0, 1, 120)[:, None]
    h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s; h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
    P1 = h00 * Pf + h10 * (t * L) + h01 * np.array([a_b, -D]) + h11 * (np.array([1.0, 0.0]) * L)
    aa = np.linspace(a_b, a_e, 80)[1:]
    P2 = np.stack([aa, trough_profile(aa, a_b, a_e, D)], -1)
    a_end = max(a[-1], a_e + 8.0) if a_end_min is None else max(a_end_min, a_e + 8.0)
    P3 = np.stack([np.linspace(a_e, a_end, 20)[1:], np.zeros(19)], -1)
    P = np.vstack([P1, P2, P3])
    w = np.ones(len(P)); w[len(P1) + len(P2):] = 0.25          # fewer columns on the flat sea
    Q = resample_w(P, NU - jf, w)
    a2 = a.copy(); y2 = y.copy(); a2[jf:] = Q[:, 0]; y2[jf:] = Q[:, 1]
    return a2, y2, {"D": float(D), "a_b": float(a_b), "a_e": float(a_e)}


def seat_weight(cc):
    d = abs(cc - SEAT_C)
    return float(1 - smoothstep((d - 2.0) / 1.5))
