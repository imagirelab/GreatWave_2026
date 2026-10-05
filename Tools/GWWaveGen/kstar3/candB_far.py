# -*- coding: utf-8 -*-
"""Q20 candidate B, step 1: far-side re-close (Q16 M5 idea, extended to a thin curl).

Every far row (c > 0) is designed in "main-equivalent" coordinates (its section mapped along PaintingCam rays onto
the main plane c = 0) as a member of a family between the main section (q = 0) and a thin hood S_min (q = 1) that
wraps the painted tube hole at a small clearance.  Mapped back to its own plane with the camera-centre scale
lambda(c) = (c - c_cam)/(0 - c_cam), each far row is hidden behind the main section in the painting view, so the
painting gate does not move (checked).  The far end is a thin open curl (the tube mouth open), the crest line stays
nearly straight in plan, the height falls from the main crest to ~0.73 H0 by c ~ 3.3 m.
"""
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter1d
from candB_common import *
from candB_geom import resample, capped_fair, turn_deg, inside_px, row_inside

GRID = 0.02


def hole_polygon(aM, yM, j0=200, j1=384):
    """painted tube hole in the main plane: main underside + inner wall (cols j0..j1) closed below the horizon."""
    P = np.stack([aM[j0:j1 + 1], yM[j0:j1 + 1]], -1)
    tip = P[0]
    bot = P[-1]
    ext = np.array([[bot[0], -4.0], [45.0, -4.0], [45.0, tip[1]], [tip[0] + 0.05, tip[1]]])
    return np.vstack([P, ext])


def dist_field(poly, a0=-30, a1=30, y0=-6, y1=26, st=GRID):
    W = int((a1 - a0) / st); H = int((y1 - y0) / st)
    img = np.zeros((H, W), np.uint8)
    pts = np.stack([(poly[:, 0] - a0) / st, (y1 - poly[:, 1]) / st], -1)
    cv2.fillPoly(img, [np.round(pts * 16).astype(np.int32)], 255, lineType=cv2.LINE_8, shift=4)
    d = cv2.distanceTransform((img == 0).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * st
    return d, (a0, a1, y0, y1, st)


def sample_field(d, g, a, y):
    a0, a1, y0, y1, st = g
    x = (a - a0) / st; yy = (y1 - y) / st
    return cv2.remap(d.astype(np.float32), x.astype(np.float32).reshape(1, -1), yy.astype(np.float32).reshape(1, -1),
                     cv2.INTER_LINEAR).ravel()


def level_curve(field, g, level):
    """largest contour of {field <= level} as (a, y) points (closed, CCW in image = ?)."""
    a0, a1, y0, y1, st = g
    m = (field <= level).astype(np.uint8)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cn = max(cnts, key=len)[:, 0, :].astype(float)
    return np.stack([a0 + cn[:, 0] * st, y1 - cn[:, 1] * st], -1)


def smooth_closed(P, sig):
    return np.stack([gaussian_filter1d(P[:, 0], sig, mode="wrap"), gaussian_filter1d(P[:, 1], sig, mode="wrap")], -1)


def build_smin(aM, yM, delta=0.30, t_top=0.55, t_bot=2.2, tip_a=9.3, smooth_m=0.5):
    """S_min in main-equivalent coordinates, 400 columns with the K* landmark semantics.
    inner surface = level set D_hole = delta; outer surface = D_hole = delta + t(y) (thin at the lip, thicker low)."""
    poly = hole_polygon(aM, yM)
    d, g = dist_field(poly)
    a0, a1, y0, y1, st = g
    Ag = a0 + (np.arange(d.shape[1]) + 0.0) * st; Yg = y1 - np.arange(d.shape[0]) * st
    tt = t_top + (t_bot - t_top) * smoothstep((11.5 - Yg) / 8.0)
    F_out = d - tt[:, None]
    inner = level_curve(d, g, delta)
    outer = level_curve(F_out, g, delta)
    sg = smooth_m / st
    inner = smooth_closed(inner, sg); outer = smooth_closed(outer, sg)

    def branch(C, a_tip):
        # keep the part left of / above the hole: points with a < a_tip + 0.5 and y > -2, ordered from the tip
        # region along the underside toward the inner wall bottom; the contour is a loop around the hole polygon
        keep = (C[:, 1] > -2.5) & (C[:, 0] < a_tip + 1.0) & ~((C[:, 0] > aM[384] + 0.5) & (C[:, 1] < 2.0))
        # rotate so that the loop starts at a dropped point, then take the longest kept run
        idx = np.nonzero(~keep)[0]
        if len(idx):
            C = np.roll(C, -idx[0], 0); keep = np.roll(keep, -idx[0])
        runs = []; s0 = None
        for i, k in enumerate(keep):
            if k and s0 is None:
                s0 = i
            if (not k or i == len(keep) - 1) and s0 is not None:
                runs.append((s0, i if not k else i + 1)); s0 = None
        s0, s1 = max(runs, key=lambda r: r[1] - r[0])
        B = C[s0:s1]
        if B[0, 1] < B[-1, 1]:
            B = B[::-1]
        return B      # from the top/tip end down to the bottom end
    Bi = branch(inner, tip_a); Bo = branch(outer, tip_a)
    # inner surface: start at the tip point (the point of Bi nearest to the underside at a = tip_a, lowest there)
    def cut_at_tip(B, a_t):
        # first point (from the tip end) with a <= a_t after the curve has come back from the right
        j = int(np.argmin(np.abs(B[:, 0] - a_t) + 0.3 * np.abs(B[:, 1] - np.interp(a_t, aM[200:260][::-1], yM[200:260][::-1]))))
        return j
    ji = cut_at_tip(Bi, tip_a)
    Bi = Bi[ji:]
    # outer: tip end point just above the inner tip point; take the outer branch point nearest to it
    jo = int(np.argmin(np.hypot(Bo[:, 0] - Bi[0, 0], Bo[:, 1] - Bi[0, 1] - 0.5 * (t_top + 0.0))))
    Bo = Bo[jo:]
    # extend both to y = 0 (then the sea): below the horizon the region is free
    def to_sea(B, back):
        B = B[B[:, 1] > 0.3]
        last = B[-1]
        if back:   # outer: continue down-back to y = 0 with a concave foot
            ext = np.array([[last[0] - 0.4 * k * last[1] / 8, last[1] * (1 - k / 8)] for k in range(1, 9)])
        else:      # inner: continue down to y = 0 slightly forward
            ext = np.array([[last[0] + 0.3 * k * last[1] / 8, last[1] * (1 - k / 8)] for k in range(1, 9)])
        return np.vstack([B, ext])
    Bi = to_sea(Bi, False); Bo = to_sea(Bo, True)
    # tip cap: semicircle from the outer tip end to the inner tip end
    p_o, p_i = Bo[0], Bi[0]
    mid = 0.5 * (p_o + p_i); rad = 0.5 * np.linalg.norm(p_o - p_i)
    v = (p_o - mid) / max(rad, 1e-6); nrm = np.array([v[1], -v[0]])       # toward +a (outward of the tip)
    if nrm[0] < 0:
        nrm = -nrm
    cap = np.array([mid + rad * (np.cos(t) * v + np.sin(t) * nrm) for t in np.linspace(0, np.pi, 12)])
    # assemble with landmark columns: 0-18 flat back, 18-90 back (outer, foot -> crest), 90-200 lip top (crest -> tip),
    # 200-314 underside (tip -> tube corner), 314-379 inner wall (corner -> foot), 379-394 foot/trough, 394-399 flat front
    outer_up = Bo[::-1]                           # from the back foot up to the tip end
    j_crest = int(np.argmax(outer_up[:, 1]))
    back = outer_up[:j_crest + 1]; top = np.vstack([outer_up[j_crest:], cap[1:-1]])
    # inner: from the tip down; the tube corner = the inner-surface point nearest to main's corner (col 314)
    jc = int(np.argmin(np.hypot(Bi[:, 0] - aM[314], Bi[:, 1] - yM[314])))
    under = Bi[:jc + 1]; wall = Bi[jc:]
    S = np.zeros((NU, 2))
    S[18:91] = resample(back, 73)
    S[90:201] = resample(top, 111)
    S[200:315] = resample(under, 115)
    S[314:380] = resample(wall, 66)
    foot_a = S[379, 0]
    S[:19, 0] = np.linspace(S[18, 0] - 40.0, S[18, 0], 19); S[:19, 1] = 0.0
    S[379:395, 0] = np.linspace(foot_a, foot_a + 6.0, 16); S[379:395, 1] = np.linspace(S[379, 1], 0.0, 16)
    S[394:, 0] = np.linspace(foot_a + 6.0, foot_a + 30.0, 6); S[394:, 1] = 0.0
    return S, {"inner": Bi, "outer": Bo, "crest_eq": outer_up[j_crest].tolist()}


def to_plane(a_eq, y_eq, c):
    """main-equivalent -> plane c along PaintingCam rays; below 1 m the height is kept (below the horizon: free)."""
    lm = lam(c, 0.0)
    a = CAM_S[0] + lm * (a_eq - CAM_S[0])
    yc = CAM_S[1] + lm * (y_eq - CAM_S[1])
    w = smoothstep((y_eq - 1.0) / 3.0)
    y = w * yc + (1 - w) * y_eq * np.where(y_eq > 0, 1.0, 1.0)
    return a, np.maximum(y, np.minimum(y_eq, 0.0))


def far_rows(aM, yM, c_new, q_of_c, Smin):
    A = np.zeros((len(c_new), NU)); Yv = np.zeros((len(c_new), NU))
    for i, cc in enumerate(c_new):
        q = q_of_c(cc)
        ae = (1 - q) * aM + q * Smin[:, 0]; ye = (1 - q) * yM + q * Smin[:, 1]
        A[i], Yv[i] = to_plane(ae, ye, cc)
    return A, Yv


def push_out(P, field, g, level, maxd=4.0, step=0.01):
    """move polyline points along their outward (right-hand) normal until field >= level."""
    d = np.gradient(P, axis=0)
    d = np.stack([gaussian_filter1d(d[:, 0], 3), gaussian_filter1d(d[:, 1], 3)], -1)
    n = np.stack([d[:, 1], -d[:, 0]], -1); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    Q = P.copy(); done = sample_field(field, g, Q[:, 0], Q[:, 1]) >= level
    for k in range(int(maxd / step)):
        if done.all():
            break
        Q[~done] += step * n[~done]
        done = done | (sample_field(field, g, Q[:, 0], Q[:, 1]) >= level)
    return Q


def build_smin2(aM, yM, delta=0.30, t_top=0.55, t_bot=2.2, jh=226, smooth_m=0.4):
    """S_min with the underside in correspondence with the main underside (pushed along normals by delta)."""
    poly = hole_polygon(aM, yM)
    d, g = dist_field(poly)
    a0, a1, y0, y1, st = g
    Yg = y1 - np.arange(d.shape[0]) * st
    tt = t_top + (t_bot - t_top) * smoothstep((11.5 - Yg) / 8.0)
    # inner surface: main cols jh..384 pushed out by delta (keeps the column correspondence)
    Pm = np.stack([aM[jh:385], yM[jh:385]], -1)
    Pi = push_out(Pm, d, g, delta)
    Pi = np.stack([gaussian_filter1d(Pi[:, 0], 1.5, mode="nearest"), gaussian_filter1d(Pi[:, 1], 1.5, mode="nearest")], -1)
    Pi = push_out(Pi, d, g, delta * 0.9)
    # outer surface: level set D_hole = delta + t(y), the branch from above the inner tip over the top to the back sea
    outer = smooth_closed(level_curve(d - tt[:, None], g, delta), smooth_m / st)
    keep = (outer[:, 1] > -2.5) & (outer[:, 0] < aM[200] + 1.0) & ~((outer[:, 0] > aM[384] + 0.5) & (outer[:, 1] < 2.0))
    idx = np.nonzero(~keep)[0]
    if len(idx):
        outer = np.roll(outer, -idx[0], 0); keep = np.roll(keep, -idx[0])
    runs = []; s0 = None
    for i, k in enumerate(keep):
        if k and s0 is None:
            s0 = i
        if (not k or i == len(keep) - 1) and s0 is not None:
            runs.append((s0, i if not k else i + 1)); s0 = None
    s0, s1 = max(runs, key=lambda r: r[1] - r[0])
    Bo = outer[s0:s1]
    if Bo[0, 1] < Bo[-1, 1]:
        Bo = Bo[::-1]
    # start the outer branch near the inner tip
    jo = int(np.argmin(np.hypot(Bo[:, 0] - Pi[0, 0], Bo[:, 1] - Pi[0, 1])))
    Bo = Bo[jo:]
    Bo = Bo[Bo[:, 1] > 0.3]
    last = Bo[-1]
    Bo = np.vstack([Bo, np.array([[last[0] - 0.5 * k * last[1] / 8, last[1] * (1 - k / 8)] for k in range(1, 9)])])
    # tip cap between the outer start and the inner start
    p_o, p_i = Bo[0], Pi[0]
    mid = 0.5 * (p_o + p_i); rad = 0.5 * np.linalg.norm(p_o - p_i)
    v = (p_o - mid) / max(rad, 1e-6); nrm = np.array([v[1], -v[0]])
    if nrm[0] < 0:
        nrm = -nrm
    cap = np.array([mid + rad * (np.cos(t) * v + np.sin(t) * nrm) for t in np.linspace(0, np.pi, 10)])
    outer_up = Bo[::-1]
    j_crest = int(np.argmax(outer_up[:, 1]))
    back = outer_up[:j_crest + 1]; top = np.vstack([outer_up[j_crest:], cap[1:-1]])
    S = np.zeros((NU, 2))
    S[18:91] = resample(back, 73)
    S[90:201] = resample(np.vstack([outer_up[j_crest:], cap[:1]]), 111)
    # tip cap on columns 200..jh (compressed), then the pushed main underside/wall 1:1 (jh..384)
    S[200:jh + 1] = resample(np.vstack([cap, Pi[:1]]), jh - 200 + 1)
    S[jh:385] = Pi
    foot_a = S[384, 0]
    S[:19, 0] = np.linspace(S[18, 0] - 40.0, S[18, 0], 19); S[:19, 1] = 0.0
    S[384:395, 0] = np.linspace(foot_a, foot_a + 3.0, 11); S[384:395, 1] = np.linspace(S[384, 1], 0.0, 11)
    S[394:, 0] = np.linspace(foot_a + 3.0, foot_a + 27.0, 6); S[394:, 1] = 0.0
    return S, {"crest_eq": outer_up[j_crest].tolist(), "field": (d, g)}


def build_smin3(aM, yM, delta=0.35, t_top=0.5, t_bot=2.0, jh=214, yhz=2.7):
    """S_min with a ROUND tube: the smallest circle (centre searched on a grid) that contains the painted hole
    (main underside/inner wall above the horizon, from col jh) with clearance delta and whose outer shell (radius
    R + t_top) stays under the main's upper surface.  Underside columns are the RADIAL projections of the main's
    underside columns onto the circle (so every far row between main and S_min stays outside the hole)."""
    Hm = np.stack([aM[jh:385], yM[jh:385]], -1)
    Hm_up = Hm[Hm[:, 1] > yhz]
    up_a = aM[90:201]; up_y = yM[90:201]
    order = np.argsort(up_a)
    def upper(a_):
        return np.interp(a_, up_a[order], up_y[order], left=np.nan, right=np.nan)
    best = None
    for ac in np.arange(2.0, 9.01, 0.1):
        for yc in np.arange(2.0, 9.01, 0.1):
            rho = np.hypot(Hm_up[:, 0] - ac, Hm_up[:, 1] - yc)
            R = rho.max() + delta
            th = np.radians(np.linspace(60, 150, 40))
            xa = ac + (R + t_top) * np.cos(th); ya = yc + (R + t_top) * np.sin(th)
            u = upper(xa)
            ok = np.isfinite(u)
            if ok.sum() < 10 or (u[ok] - ya[ok]).min() < 0.15:
                continue
            if best is None or R < best[0]:
                best = (R, ac, yc)
    if best is None:
        raise RuntimeError("no round tube fits")
    R, ac, yc = best
    C = np.array([ac, yc])
    # tip angle: going clockwise from the top (90 deg), the first angle where the outer shell leaves the main lip
    th_tip = 90.0
    for t in np.arange(90.0, -30.0, -0.5):
        xa = ac + (R + t_top) * np.cos(np.radians(t)); ya = yc + (R + t_top) * np.sin(np.radians(t))
        u = upper(np.array([xa]))[0]
        if not np.isfinite(u) or u - ya < 0.15:
            break
        th_tip = t
    th_tip += 4.0
    # inner surface: radial projection of main cols j >= jh onto the circle; angles in (-180, 180] around C
    ang = np.degrees(np.arctan2(yM[jh:385] - yc, aM[jh:385] - ac))
    ang = np.where(ang < th_tip - 360 + 360, ang, ang)
    ang = np.unwrap(np.radians(ang))
    ang = np.degrees(ang)
    ang = np.minimum(ang, 999)
    inner = np.stack([ac + R * np.cos(np.radians(ang)), yc + R * np.sin(np.radians(ang))], -1)
    # tip cap (cols 200..jh): outer tip point -> inner circle point at th_tip
    pt_o = C + (R + t_top) * np.array([np.cos(np.radians(th_tip)), np.sin(np.radians(th_tip))])
    pt_i = C + R * np.array([np.cos(np.radians(th_tip)), np.sin(np.radians(th_tip))])
    mid = 0.5 * (pt_o + pt_i); rad = 0.5 * t_top
    v = (pt_o - mid) / rad; nrm = np.array([v[1], -v[0]])
    if nrm @ np.array([np.cos(np.radians(th_tip - 90)), np.sin(np.radians(th_tip - 90))]) < 0:
        nrm = -nrm
    cap = np.array([mid + rad * (np.cos(t) * v + np.sin(t) * nrm) for t in np.linspace(0, np.pi, 8)])
    # the underside from the cap to the first projected column: short arc th_tip -> ang[0]
    a0 = ang[0]
    arc0 = np.array([C + R * np.array([np.cos(np.radians(t)), np.sin(np.radians(t))]) for t in np.linspace(th_tip, a0, 6)])
    S = np.zeros((NU, 2))
    S[200:jh + 1] = resample(np.vstack([cap, arc0[1:]]), jh - 200 + 1)
    S[jh:385] = inner
    # outer shell: from the tip over the top and down the back (thickness grows with depth), to y = 0 behind
    ang_back = ang[-1]
    ts = np.linspace(th_tip, max(ang_back, 190.0), 300)
    tt = t_top + (t_bot - t_top) * smoothstep((ts - 110.0) / 90.0)
    outer = np.stack([ac + (R + tt) * np.cos(np.radians(ts)), yc + (R + tt) * np.sin(np.radians(ts))], -1)
    outer = outer[outer[:, 1] > 0.05] if (outer[:, 1] <= 0.05).any() else outer
    last = outer[-1]
    if last[1] > 0.05:
        # continue down along the tangent and ease to the flat back sea
        tg = outer[-1] - outer[-2]; tg /= np.linalg.norm(tg)
        ext = [last + tg * k * 0.3 for k in range(1, 400)]
        ext = np.array([p for p in ext if p[1] > 0.0])
        if len(ext):
            outer = np.vstack([outer, ext])
        outer = np.vstack([outer, [[outer[-1, 0] - 1.0, 0.0]]])
    j_crest = int(np.argmax(outer[:, 1]))
    top = outer[:j_crest + 1][::-1]          # crest -> tip  (reversed below)
    back = outer[j_crest:][::-1]             # foot -> crest
    S[18:91] = resample(back, 73)
    S[90:201] = resample(np.vstack([outer[:j_crest + 1][::-1], ]), 111)[::-1][::-1]
    # S[90:201] must run crest -> tip
    seg = outer[:j_crest + 1]                # tip -> crest
    S[90:201] = resample(seg[::-1], 111)
    foot_a = S[384, 0]
    S[:19, 0] = np.linspace(S[18, 0] - 40.0, S[18, 0], 19); S[:19, 1] = 0.0
    S[384:395, 0] = np.linspace(foot_a, foot_a + 3.0, 11); S[384:395, 1] = np.linspace(S[384, 1], 0.0, 11)
    S[394:, 0] = np.linspace(foot_a + 3.0, foot_a + 27.0, 6); S[394:, 1] = 0.0
    return S, {"crest_eq": outer[j_crest].tolist(), "C": C.tolist(), "R": float(R), "th_tip": float(th_tip)}


def build_smin4(aM, yM, delta=0.35, t_top=0.5, t_bot=2.0, a_tip=9.0, jh0=236, yhz=2.7, th_back=212.0):
    """round-tube S_min, lip tip placed above the painted claw cluster at a = a_tip (main-equivalent)."""
    up_a = aM[90:201]; up_y = yM[90:201]; o = np.argsort(up_a)
    def upper(a_):
        return np.interp(a_, up_a[o], up_y[o], left=np.nan, right=np.nan)
    un_a = aM[200:300]; un_y = yM[200:300]
    # the underside height at a (lowest crossing of the main underside)
    def under(a_):
        ys = []
        for j in range(len(un_a) - 1):
            x0, x1 = un_a[j], un_a[j + 1]
            if (x0 - a_) * (x1 - a_) <= 0 and x0 != x1:
                ys.append(un_y[j] + (a_ - x0) / (x1 - x0) * (un_y[j + 1] - un_y[j]))
        return max(ys) if ys else np.nan
    Hm = np.stack([aM[jh0:385], yM[jh0:385]], -1); Hm = Hm[Hm[:, 1] > yhz]
    yu, yo = under(a_tip), float(upper(np.array([a_tip]))[0])
    best = None
    for ac in np.arange(2.0, 8.01, 0.1):
        for yc in np.arange(3.0, 9.01, 0.1):
            R = np.hypot(Hm[:, 0] - ac, Hm[:, 1] - yc).max() + delta
            if abs(a_tip - ac) >= R:
                continue
            ty = yc + np.sqrt(R * R - (a_tip - ac) ** 2)
            if not (yu + delta < ty < yo - t_top - 0.15):
                continue
            tht = np.degrees(np.arctan2(ty - yc, a_tip - ac))
            th = np.radians(np.linspace(tht, 150, 40))
            xa = ac + (R + t_top) * np.cos(th); ya = yc + (R + t_top) * np.sin(th)
            u = upper(xa); ok = np.isfinite(u)
            if ok.sum() < 10 or (u[ok] - ya[ok]).min() < 0.15:
                continue
            score = R - 0.3 * (ty - yu)
            if best is None or score < best[0]:
                best = (score, R, ac, yc, tht)
    if best is None:
        raise RuntimeError("no round tube fits")
    _, R, ac, yc, th_tip = best
    C = np.array([ac, yc])
    # underside columns: 200..jh0 = tip cap + arc th_tip -> angle of main col jh0; jh0..384 = radial projections
    ang = np.degrees(np.unwrap(np.arctan2(yM[jh0:385] - yc, aM[jh0:385] - ac)))
    ang = np.where(ang < th_tip, ang + 360.0, ang)
    ang = np.maximum.accumulate(ang)
    inner = np.stack([ac + R * np.cos(np.radians(ang)), yc + R * np.sin(np.radians(ang))], -1)
    pt_o = C + (R + t_top) * np.array([np.cos(np.radians(th_tip)), np.sin(np.radians(th_tip))])
    pt_i = C + R * np.array([np.cos(np.radians(th_tip)), np.sin(np.radians(th_tip))])
    mid = 0.5 * (pt_o + pt_i); rad = 0.5 * t_top
    v = (pt_o - mid) / rad
    dirt = np.array([np.sin(np.radians(th_tip)), -np.cos(np.radians(th_tip))])   # clockwise tangent = outward past the tip
    cap = np.array([mid + rad * (np.cos(t) * v + np.sin(t) * dirt) for t in np.linspace(0, np.pi, 8)])
    arc0 = np.array([C + R * np.array([np.cos(np.radians(t)), np.sin(np.radians(t))]) for t in np.linspace(th_tip, ang[0], 8)])
    S = np.zeros((NU, 2))
    S[200:jh0 + 1] = resample(np.vstack([cap, arc0[1:]]), jh0 - 200 + 1)
    S[jh0:385] = inner
    # outer shell: tip -> over the top -> down the back to th_back, then a concave foot to y = 0
    ts = np.linspace(th_tip, th_back, 300)
    tt = t_top + (t_bot - t_top) * smoothstep((ts - 110.0) / 90.0)
    outer = np.stack([ac + (R + tt) * np.cos(np.radians(ts)), yc + (R + tt) * np.sin(np.radians(ts))], -1)
    p0 = outer[-1]; tg = outer[-1] - outer[-2]; tg /= np.linalg.norm(tg)
    if p0[1] > 0.05:
        L = p0[1] * 1.6
        s = np.linspace(0, 1, 40)[:, None]
        h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s; h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
        end = np.array([p0[0] + tg[0] / max(-tg[1], 0.2) * p0[1] - 0.8 * p0[1], 0.0])
        foot = h00 * p0 + h10 * tg * L + h01 * end + h11 * np.array([-1.0, 0.0]) * L
        outer = np.vstack([outer, foot[1:]])
    j_crest = int(np.argmax(outer[:, 1]))
    S[90:201] = resample(outer[:j_crest + 1][::-1], 111)            # crest -> tip
    S[18:91] = resample(outer[j_crest:][::-1], 73)                  # foot -> crest
    foot_a = S[384, 0]
    S[:19, 0] = np.linspace(S[18, 0] - 40.0, S[18, 0], 19); S[:19, 1] = 0.0
    S[384:395, 0] = np.linspace(foot_a, foot_a + 3.0, 11); S[384:395, 1] = np.linspace(S[384, 1], min(S[384, 1], 0.0), 11)
    S[394:, 0] = np.linspace(foot_a + 3.0, foot_a + 27.0, 6); S[394:, 1] = 0.0
    return S, {"crest_eq": outer[j_crest].tolist(), "C": C.tolist(), "R": float(R), "th_tip": float(th_tip)}


def build_smin5(aM, yM, delta=0.3, t_top=0.5, t_bot=2.0, a_tip=9.0, jh0=232, yhz=2.7, th_back=200.0):
    """round (elliptic, axis ratio <= 1.25) tube S_min containing the painted hole (main-equivalent)."""
    up_a = aM[90:201]; up_y = yM[90:201]; o = np.argsort(up_a)
    def upper(a_):
        return np.interp(a_, up_a[o], up_y[o], left=np.nan, right=np.nan)
    Hm = np.stack([aM[jh0:379], yM[jh0:379]], -1); Hm = Hm[Hm[:, 1] > yhz]
    un = np.stack([aM[200:240], yM[200:240]], -1)
    best = None
    for ac in np.arange(3.5, 7.01, 0.1):
        for yc in np.arange(5.0, 9.01, 0.1):
            for Ra in np.arange(4.5, 7.01, 0.1):
                for k in (1.0, 1.08, 1.16, 1.25):
                    Ry = Ra * k
                    rr = np.sqrt(((Hm[:, 0] - ac) / (Ra - delta)) ** 2 + ((Hm[:, 1] - yc) / (Ry - delta)) ** 2)
                    if rr.max() > 1.0:
                        continue
                    if abs(a_tip - ac) >= Ra:
                        continue
                    ty = yc + Ry * np.sqrt(1 - ((a_tip - ac) / Ra) ** 2)
                    # tip must be above the painted underside near a_tip and under the upper surface
                    near = un[np.abs(un[:, 0] - a_tip) < 0.6]
                    if len(near) and ty < near[:, 1].max() + delta:
                        continue
                    if ty > upper(np.array([a_tip]))[0] - t_top - 0.15:
                        continue
                    tht = np.degrees(np.arctan2((ty - yc) / Ry, (a_tip - ac) / Ra))
                    th = np.radians(np.linspace(tht, 150, 40))
                    xa = ac + (Ra + t_top) * np.cos(th); ya = yc + (Ry + t_top) * np.sin(th)
                    u = upper(xa); ok = np.isfinite(u)
                    if ok.sum() < 10 or (u[ok] - ya[ok]).min() < 0.15:
                        continue
                    score = Ra * Ry + 3.0 * (k - 1.0) * Ra * Ra
                    if best is None or score < best[0]:
                        best = (score, ac, yc, Ra, Ry, tht)
    if best is None:
        raise RuntimeError("no round tube fits")
    _, ac, yc, Ra, Ry, th_tip = best
    def E_(t, dr=0.0):
        t = np.radians(np.asarray(t, float))
        return np.stack([ac + (Ra + dr) * np.cos(t), yc + (Ry + dr) * np.sin(t)], -1)
    # parametric angle of main columns (radial from the centre, in normalised coordinates)
    ang = np.degrees(np.arctan2((yM[jh0:385] - yc) / Ry, (aM[jh0:385] - ac) / Ra))
    base = th_tip - 30.0
    ang = (ang - base) % 360.0 + base
    ang = np.maximum(ang, th_tip + 0.5)
    ang = np.maximum.accumulate(ang)
    for k in range(1, len(ang)):                  # strictly increasing (no coincident columns)
        ang[k] = max(ang[k], ang[k - 1] + 0.25)
    inner = E_(ang)
    pt_o = E_(th_tip, t_top); pt_i = E_(th_tip)
    mid = 0.5 * (pt_o + pt_i); rad = 0.5 * np.linalg.norm(pt_o - pt_i)
    v = (pt_o - mid) / rad
    tg = E_(th_tip - 1.0) - E_(th_tip); tg /= np.linalg.norm(tg)
    cap = np.array([mid + rad * (np.cos(t) * v + np.sin(t) * tg) for t in np.linspace(0, np.pi, 8)])
    arc0 = E_(np.linspace(th_tip, ang[0], 8))
    S = np.zeros((NU, 2))
    S[200:jh0 + 1] = resample(np.vstack([cap, arc0[1:]]), jh0 - 200 + 1)
    S[jh0:385] = inner
    ts = np.linspace(th_tip, th_back, 300)
    tt = t_top + (t_bot - t_top) * smoothstep((ts - 110.0) / 90.0)
    outer = np.stack([ac + (Ra + tt) * np.cos(np.radians(ts)), yc + (Ry + tt) * np.sin(np.radians(ts))], -1)
    p0 = outer[-1]; tgb = outer[-1] - outer[-2]; tgb /= np.linalg.norm(tgb)
    if p0[1] > 0.05:
        L = p0[1] * 1.6
        s = np.linspace(0, 1, 40)[:, None]
        h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s; h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
        end = np.array([p0[0] - 0.9 * p0[1], 0.0])
        foot = h00 * p0 + h10 * tgb * L + h01 * end + h11 * np.array([-1.0, 0.0]) * L
        outer = np.vstack([outer, foot[1:]])
    j_crest = int(np.argmax(outer[:, 1]))
    S[90:201] = resample(outer[:j_crest + 1][::-1], 111)
    S[18:91] = resample(outer[j_crest:][::-1], 73)
    foot_a = S[384, 0]
    S[:19, 0] = np.linspace(S[18, 0] - 40.0, S[18, 0], 19); S[:19, 1] = 0.0
    S[384:395, 0] = np.linspace(foot_a, foot_a + 3.0, 11); S[384:395, 1] = np.linspace(S[384, 1], min(S[384, 1], 0.0), 11)
    S[394:, 0] = np.linspace(foot_a + 3.0, foot_a + 27.0, 6); S[394:, 1] = 0.0
    return S, {"crest_eq": outer[j_crest].tolist(), "C": [float(ac), float(yc)], "Ra": float(Ra), "Ry": float(Ry), "th_tip": float(th_tip)}
