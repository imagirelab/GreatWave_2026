# -*- coding: utf-8 -*-
"""Q20 candidate B, step 5: near-row lips thinned to a hooked shell and tubes rounded (hidden parts only).

For a near row (c < -0.3 m, its lip hidden in the painting view) the cavity under the lip is rebuilt as a circle of
radius R = r_rel * H_r that passes through the painting-kept lip tip at the angle theta_tip (the lip curls down onto the
tube), goes over the roof, down the inner wall, through the trough bottom and back up into the front sea.  The lip
upper surface (crest -> tip) is kept; so the lip becomes a thin hook (thickness = upper surface - roof arc)."""
import numpy as np
from candB_common import *
from candB_geom import resample_w, resample


def tube_section(a, y, Hr, r_rel=0.41, th_tip=55.0, t_min=0.35, th_corner=165.0, th_face=240.0, th_out=300.0):
    """returns new (a, y) for columns 200..399 (tip -> tube -> trough -> front sea) or None."""
    Pt = np.array([a[200], y[200]])
    R = r_rel * Hr
    up = np.stack([a[90:201], y[90:201]], -1)          # upper surface crest -> tip
    for it in range(40):
        C = Pt - R * np.array([np.cos(np.radians(th_tip)), np.sin(np.radians(th_tip))])
        # roof arc (th_tip..180) must stay t_min below the upper surface
        th = np.radians(np.linspace(th_tip + 3, 150, 60))
        ra = C[0] + R * np.cos(th); ry = C[1] + R * np.sin(th)
        m = (ra >= up[:, 0].min()) & (ra <= up[:, 0].max())
        uy = np.interp(ra[m], up[::-1, 0] if up[0, 0] > up[-1, 0] else up[:, 0], up[::-1, 1] if up[0, 0] > up[-1, 0] else up[:, 1])
        if not m.any() or (uy - ry[m]).min() >= t_min:
            break
        th_tip += 2.0            # rotate the tip further down the circle (the lip hangs more) and shrink a little
        R *= 0.985
    thc = np.radians(np.r_[np.linspace(th_tip, 360.0 * 0 + th_out, 400)])
    arc = np.stack([C[0] + R * np.cos(thc), C[1] + R * np.sin(thc)], -1)
    # leave the circle tangentially at th_out and ease into the front sea (y = 0, level tangent)
    p0 = arc[-1]; t0 = np.array([-np.sin(np.radians(th_out)), np.cos(np.radians(th_out))])
    a_f = p0[0] + max(4.0, 2.5 * abs(p0[1]) + 3.0)
    L = np.hypot(a_f - p0[0], p0[1])
    s = np.linspace(0, 1, 60)[:, None]
    h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s; h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
    P2 = h00 * p0 + h10 * t0 * L + h01 * np.array([a_f, 0.0]) + h11 * np.array([1.0, 0.0]) * L
    a_end = max(a[-1], a_f + 10.0)
    P3 = np.stack([np.linspace(a_f, a_end, 12)[1:], np.zeros(11)], -1)
    # columns: 200..314 tip -> corner(th_corner); 314..379 corner -> face(th_face); 379..399 face -> out -> sea
    def arc_between(t0_, t1_, n):
        tt = np.radians(np.linspace(t0_, t1_, n))
        return np.stack([C[0] + R * np.cos(tt), C[1] + R * np.sin(tt)], -1)
    S1 = arc_between(th_tip, th_corner, 115)
    S2 = arc_between(th_corner, th_face, 66)
    rest = np.vstack([arc_between(th_face, th_out, 40)[1:], P2[1:], P3])
    w = np.ones(len(rest) + 1); w[-len(P3):] = 0.3
    S3 = resample_w(np.vstack([S2[-1:], rest]), 21, w)
    Q = np.vstack([S1, S2[1:], S3[1:]])
    return Q[:, 0], Q[:, 1], {"R": float(R), "C": C.tolist(), "th_tip": float(th_tip)}


SHEAR = 0.45     # the tube leans: a' = a - SHEAR (y - y_c)  (roof back, lower inner wall slanting forward like 72)


def circ(C, R, th_deg, k=None):
    k = SHEAR if k is None else k
    th = np.radians(np.asarray(th_deg, float))
    return np.stack([C[0] + R * np.cos(th) - k * R * np.sin(th), C[1] + R * np.sin(th)], -1)


def centre_from_tip(Pt, R, th_tip, k=None):
    k = SHEAR if k is None else k
    t = np.radians(th_tip)
    return Pt - np.array([R * np.cos(t) - k * R * np.sin(t), R * np.sin(t)])


def roof_clearance(a, y, C, R, th_tip):
    """min vertical gap between the lip upper surface (cols 90..200) and the tube roof arc (th_tip+3 .. 150 deg)."""
    up = np.stack([a[90:201], y[90:201]], -1)
    o = np.argsort(up[:, 0])
    Pr = circ(C, R, np.linspace(th_tip + 3, 150, 60))
    ra = Pr[:, 0]; ry = Pr[:, 1]
    m = (ra >= up[:, 0].min()) & (ra <= up[:, 0].max())
    if not m.any():
        return 9.0
    uy = np.interp(ra[m], up[o, 0], up[o, 1])
    return float((uy - ry[m]).min())


def solve_th_tip(a, y, R, th0, t_min=0.35, th_max=85.0):
    """smallest tip angle >= th0 for which the roof keeps t_min below the lip top (continuous bisection)."""
    Pt = np.array([a[200], y[200]])
    def clr(th):
        C = centre_from_tip(Pt, R, th)
        return roof_clearance(a, y, C, R, th)
    if clr(th0) >= t_min:
        return th0
    lo, hi = th0, th_max
    if clr(hi) < t_min:
        return hi
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        if clr(mid) >= t_min:
            hi = mid
        else:
            lo = mid
    return hi


def tube_section_fixed(a, y, R, th_tip, th_corner=165.0, th_face=240.0, th_out=300.0):
    """the tube circle (sheared, see SHEAR) given (R, tip angle) through the kept lip tip; returns cols 200..399."""
    Pt = np.array([a[200], y[200]])
    C = centre_from_tip(Pt, R, th_tip)
    def arc_between(t0_, t1_, n):
        return circ(C, R, np.linspace(t0_, t1_, n))
    p0 = circ(C, R, [th_out])[0]
    d = circ(C, R, [th_out + 0.5])[0] - p0; t0 = d / np.linalg.norm(d)
    a_f = p0[0] + max(4.0, 2.5 * abs(p0[1]) + 3.0)
    L = np.hypot(a_f - p0[0], p0[1])
    s_ = np.linspace(0, 1, 60)[:, None]
    h00 = 2 * s_**3 - 3 * s_**2 + 1; h10 = s_**3 - 2 * s_**2 + s_; h01 = -2 * s_**3 + 3 * s_**2; h11 = s_**3 - s_**2
    P2 = h00 * p0 + h10 * t0 * L + h01 * np.array([a_f, 0.0]) + h11 * np.array([1.0, 0.0]) * L
    a_end = max(a[-1], a_f + 10.0)
    P3 = np.stack([np.linspace(a_f, a_end, 12)[1:], np.zeros(11)], -1)
    S1 = arc_between(th_tip, th_corner, 115)
    S2 = arc_between(th_corner, th_face, 66)
    rest = np.vstack([arc_between(th_face, th_out, 40)[1:], P2[1:], P3])
    w = np.ones(len(rest) + 1); w[-len(P3):] = 0.3
    S3 = resample_w(np.vstack([S2[-1:], rest]), 21, w)
    Q = np.vstack([S1, S2[1:], S3[1:]])
    return Q[:, 0], Q[:, 1], C
