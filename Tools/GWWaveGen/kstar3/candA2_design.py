# -*- coding: utf-8 -*-
"""Q20 loop 3, candidate A2: push loop-2 K*' for drama by reshaping ONLY what the painting camera does not see.

Rule (checked, not assumed): a vertex is PINNED if it belongs to a triangle that is the first hit of any pixel of the
PaintingCam v1 view (exact perspective-correct z-buffer at 2x display resolution, OR the painter's-order ID buffer,
dilated by one column).  Pinned vertices keep their loop-2 position exactly, so every surface the painting camera
sees -- and therefore every outline 78/130/131/132/72 -- is unchanged.  Free vertices are redesigned; they must stay
inside the painting's allowed region (painted wave / below the horizon / outside the scored frame) and behind the
loop-2 visible surface (checked with the loop-2 z-buffer), so the painting view does not change at all.

Design of the free parts (per row, K* section frame a / y, row plane c):
  * lip: a thin blade -- the free side of the lip is the pinned side offset by t(d) (0.32 m at the tip, growing to the
    shell thickness at the lip root); where both sides are free the loop-2 top is kept and the underside follows it;
  * tube: the cavity wall is a round arc; where the painting pins the wall (near / main rows) the pinned wall is kept
    and only the ceiling is rounded into it; where the wall is free (c > +0.7) a circle arc bulges back below the pinned
    tube corner into a deep round bottom and a front trough;
  * back: a round shell concentric with the tube: the back is the tube wall offset outwards by the shell thickness,
    capped by a round crest (slope-limited) and ending in one concave foot;
  * far rows: the same construction with the loop-2 pinned lip pieces (the far hood's contour pieces along 72).
No reference-model data is read; the reference model only informed the rubric numbers (proportions).
usage: py -3.10 candA2_design.py params.json out_rows.npz
"""
import sys, os, json, math
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import PchipInterpolator
import scipy.sparse as sp
import scipy.sparse.linalg as spla
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA2_common as K

NU = 400


# ------------------------------------------------------------------ polyline helpers
def arclen(P):
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]


def at_s(P, s, q):
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], -1)


def resample_fracs(P, fr):
    """points on polyline P at arc-length fractions fr (0..1)"""
    s = arclen(P)
    return at_s(P, s, np.asarray(fr) * s[-1])


def col_fracs(Pold, j0, j1):
    """arc-length fractions of columns j0..j1 along the old row (keeps the old column density)"""
    s = arclen(Pold[j0:j1 + 1])
    return s / max(s[-1], 1e-9)


def normals(P):
    d = np.gradient(P, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
    return np.stack([d[:, 1], -d[:, 0]], -1)     # right-hand normal of the travel direction


def offset(P, t):
    """offset polyline P by t (array or scalar) along its right-hand normal, with a light smoothing"""
    n = normals(gaussian_filter1d(P, 2.0, axis=0, mode="nearest"))
    return P + np.asarray(t)[..., None] * n


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ design pieces
def back_curve(aT, H, a_ref, y_ref, prm):
    """back from the crest (aT, H) to the sea: a round cap (radius cap_R x H) until the heading reaches th1, then a
    flank whose heading grows with depth to th_max (solved so the back passes (a_ref, y_ref)), then one concave
    foot (heading falls to 0 at the sea).  Returns the polyline crest -> sea (a decreasing)."""
    ds = 0.05
    Rc = prm["cap_R"] * H
    th1 = math.radians(prm.get("cap_th1", 55.0))
    y_ft = prm.get("foot_y", 0.28) * H
    y_c1 = H - Rc * (1 - math.cos(th1))

    def build(thm):
        P = [np.array([aT, H])]; th = 0.0
        thm = math.radians(thm)
        while P[-1][1] > 0.0 and len(P) < 40000:
            yv = P[-1][1]
            if th < th1 and yv > y_ft and yv > y_c1 - 1e-9:
                th = min(th + ds / Rc, th1)
            elif yv > y_ft:
                f = (y_c1 - yv) / max(y_c1 - y_ft, 1e-6)
                th = th1 + (thm - th1) * min(max(f, 0.0), 1.0) ** prm.get("flank_p", 0.8)
            else:
                th = max(thm * (yv / y_ft) ** prm.get("foot_p", 0.7), math.radians(1.5))
            P.append(P[-1] + ds * np.array([-math.cos(th), -math.sin(th)]))
        P = np.array(P); P[-1, 1] = 0.0
        return P
    lo, hi = math.degrees(th1) + 0.5, 89.5
    for _ in range(26):
        m = 0.5 * (lo + hi)
        P = build(m)
        a_at = np.interp(y_ref, P[::-1, 1], P[::-1, 0])
        if a_at < a_ref:
            lo = m
        else:
            hi = m
    thm = 0.5 * (lo + hi)
    P = build(thm)
    tail = np.stack([P[-1, 0] - np.linspace(0.3, 40.0, 30), np.zeros(30)], -1)
    return np.vstack([P, tail]), thm


def circle_arc(cen, R, t0, t1, n=200):
    t = np.radians(np.linspace(t0, t1, n))
    return np.stack([cen[0] + R * np.cos(t), cen[1] + R * np.sin(t)], -1)


def fit_circle(P, w=None):
    w = np.ones(len(P)) if w is None else w
    M = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))] * w[:, None]
    s, *_ = np.linalg.lstsq(M, (P ** 2).sum(1) * w, rcond=None)
    return s[:2], float(np.sqrt(s[2] + s[0] ** 2 + s[1] ** 2))


def smooth_poly(P, sig_m):
    """Gaussian smoothing along the arc (sigma in metres), resampled at 0.05 m"""
    s = arclen(P)
    if s[-1] < 0.2:
        return P.copy()
    q = np.arange(0, s[-1] + 1e-9, 0.05)
    Q = at_s(P, s, q)
    return gaussian_filter1d(Q, max(sig_m / 0.05, 0.5), axis=0, mode="nearest")


def wall_builder(S, thS, yb, R_t, prm, H):
    """cavity wall from S (heading thS, degrees, travel direction ceiling -> bottom, CCW) : turn left with radius R_t to
    straight down (270 - lean), [or, if already past it, turn right with radius R_s = the S-bend], go down, then a round
    bottom of radius R_bot to horizontal at y = yb.  Returns the polyline (0.05 m steps)."""
    ds = 0.05
    tgt = 270.0 - prm.get("wall_lean_back", 0.0)
    R_s = prm.get("wall_R_s", 0.25) * H
    R_bot = min(R_t, max((S[1] - yb) * 0.9, 0.5))
    pts = [np.array(S, float)]; th = float(thS)
    phase = 0
    for _ in range(20000):
        p = pts[-1]
        if phase == 0:
            if th < tgt - 1e-6:
                th = min(th + math.degrees(ds / R_t), tgt)
            elif th > tgt + 1e-6 and prm.get("allow_S", True):
                th = max(th - math.degrees(ds / R_s), tgt)
            else:
                phase = 1
            if p[1] <= yb + R_bot:
                phase = 2
        elif phase == 1:
            if p[1] <= yb + R_bot:
                phase = 2
        if phase == 2:
            th = min(th + math.degrees(ds / R_bot), 360.0)
            if th >= 360.0 - 1e-6 or p[1] <= yb + 1e-3:
                break
        pts.append(p + ds * np.array([math.cos(math.radians(th)), math.sin(math.radians(th))]))
    return np.array(pts)


def heading_deg(P, i, k=3):
    i0 = max(i - k, 0); i1 = min(i + k, len(P) - 1)
    d = P[i1] - P[i0]
    return math.degrees(math.atan2(d[1], d[0])) % 360.0


def turtle(S, th, segs, ds=0.05, max_steps=40000):
    """polyline from S with heading th (deg, unwrapped).  segs: list of dicts
       {"turn": +1 (left, CCW) / -1 (right) / 0, "R": radius, "until": ("heading", deg) | ("y_below", y) | ("len", m)}"""
    pts = [np.array(S, float)]; th = float(th)
    for sg in segs:
        kind, val = sg["until"]
        turn = sg.get("turn", 0); R = max(sg.get("R", 1.0), 1e-3)
        L = 0.0
        for _ in range(max_steps):
            p = pts[-1]
            if kind == "heading" and ((turn > 0 and th >= val - 1e-9) or (turn < 0 and th <= val + 1e-9) or turn == 0):
                break
            if kind == "y_below" and p[1] <= val:
                break
            if kind == "len" and L >= val:
                break
            if turn != 0:
                th += turn * math.degrees(ds / R)
                if kind == "heading":
                    th = min(th, val) if turn > 0 else max(th, val)
            pts.append(p + ds * np.array([math.cos(math.radians(th)), math.sin(math.radians(th))]))
            L += ds
    return np.array(pts), th


def far_cavity(U, P, jn, c, H, yb, prm, info):
    """far rows: the lip's underside U (tip -> back) curls into a small round tube of radius R_f (tangent to U), the
    tube floor turns down into an undercut face (the curl overhangs it), then a round trough bottom at yb.
    Returns the cavity polyline from the tip to the trough bottom."""
    R_f = float(np.interp(c, *zip(*prm["far_R_tab"]))) * H
    R_f = max(R_f, 0.8)
    sU = arclen(U)
    k = int(np.argmin(np.abs(sU - prm.get("far_tan_s", 1.0) * R_f)))
    k = int(np.clip(k, 3, len(U) - 4))
    d = U[min(k + 3, len(U) - 1)] - U[max(k - 3, 0)]
    th0 = math.degrees(math.atan2(d[1], d[0]))          # travel heading of the underside (backwards: ~180)
    th0 = th0 % 360.0
    if th0 < 90:
        th0 += 360.0
    lean = prm.get("far_face_lean", 12.0)
    R_face = prm.get("far_R_face", 0.10) * H
    R_bot = prm.get("far_R_bot", 0.12) * H
    segs = [{"turn": +1, "R": R_f, "until": ("heading", 360.0)},
            {"turn": -1, "R": R_face, "until": ("heading", 270.0 - lean)},
            {"turn": 0, "until": ("y_below", yb + R_bot * (1 - math.cos(math.radians(90 + lean))) + 0.05)},
            {"turn": +1, "R": R_bot, "until": ("heading", 360.0)}]
    W, _ = turtle(U[k], th0, segs)
    info.update(far_R=R_f, far_tan_k=k)
    return np.vstack([U[:k], W])


# ------------------------------------------------------------------ one row
def design_row(P, pin, c, H0, prm, info):
    """goal positions (400, 2) for a row.  P = loop-2 row (400, 2), pin = pinned mask."""
    G = P.copy()
    a, y = P[:, 0], P[:, 1]
    jt = int(np.argmax(y[:200]))              # crest column (loop 2)
    H = float(y[jt]); aT = float(a[jt])
    jn = 200; jc = 314; jb = 379
    t_tip = prm["lip_t_tip"]
    ts = prm["shell_t"] * H
    # ---------------- lip blade: the underside is the (smoothed) top offset inwards by t(d), d from the tip
    top = P[jt:jn + 1]
    rev = smooth_poly(top[::-1], prm.get("top_smooth_m", 0.6))     # tip -> crest, 0.05 m steps
    rev[0] = P[jn]
    s_top = arclen(rev)
    L_lip = s_top[-1]
    d0 = prm["lip_thin_len"]; d1 = max(prm["lip_ramp_frac"] * L_lip, d0 + 1.0)
    t_root = min(ts * prm.get("root_frac", 0.85), 0.45 * H)
    tt = t_tip + (t_root - t_tip) * smoothstep((s_top - d0) / (d1 - d0))
    n_rev = normals(gaussian_filter1d(rev, 4.0, axis=0, mode="nearest"))
    sgn = -1.0 if n_rev[-1, 1] > 0 else 1.0
    U = rev + sgn * tt[:, None] * n_rev          # underside tip -> root (0.05 m steps)
    keep = np.r_[True, np.diff(np.minimum.accumulate(U[:, 0])) < 0]
    U = U[keep | (np.arange(len(U)) < 5)]
    # ---------------- cavity
    wall_pin = np.nonzero(pin[250:380])[0] + 250
    corner_pin = np.nonzero(pin[230:345])[0] + 230
    j_fp = next((j for j in range(jb + 1, NU) if pin[j]), NU - 1)      # first pinned front-sea column
    yb = -prm["trough_D"] * H
    # wall pins behind the lip (columns 250..359); the lowest contiguous group decides where the free wall starts
    wp = np.nonzero(pin[250:360])[0] + 250
    groups = []
    for j in wp:
        if groups and j == groups[-1][-1] + 1:
            groups[-1].append(j)
        else:
            groups.append([j])
    groups = [g for g in groups if len(g) >= 6 and P[g[-1], 0] < P[jn, 0] - 2.0]
    if len(wall_pin) > 40 and wall_pin.max() >= 360:
        mode = "pinned_wall"
    elif groups:
        mode = "pinned_corner"
        corner_pin = np.arange(groups[0][0], groups[-1][-1] + 1)
    else:
        mode = "free"
    info["mode"] = mode

    def put(j0, j1, curve):
        """columns j0..j1 (inclusive) along curve by the old column arc fractions; free sub-spans that sit between
        pinned columns are mapped onto the part of the curve between the projections of their pinned anchors"""
        if not (j1 > j0 and len(curve) >= 2):
            return
        curve = np.asarray(curve, float)
        sc = arclen(curve)
        fr = col_fracs(P, j0, j1)
        sdef = fr * sc[-1]
        G[j0:j1 + 1] = at_s(curve, sc, sdef)
        dense = at_s(curve, sc, np.linspace(0, sc[-1], max(int(sc[-1] / 0.05), 20)))
        sd = np.linspace(0, sc[-1], len(dense))
        def proj(pt, s0):
            win = np.abs(sd - s0) < max(0.35 * sc[-1], 3.0)
            dd = np.where(win, np.hypot(dense[:, 0] - pt[0], dense[:, 1] - pt[1]), np.inf)
            return float(sd[int(np.argmin(dd))])
        j = j0
        while j <= j1:
            if pin[j]:
                j += 1; continue
            f0 = j
            while j + 1 <= j1 and not pin[j + 1]:
                j += 1
            f1 = j; j += 1
            left_anchor = f0 - 1 >= j0 and pin[f0 - 1]
            right_anchor = f1 + 1 <= j1 and pin[f1 + 1]
            if not (left_anchor or right_anchor):
                continue
            s_lo = proj(P[f0 - 1], sdef[f0 - 1 - j0]) if left_anchor else sdef[f0 - j0]
            s_hi = proj(P[f1 + 1], sdef[f1 + 1 - j0]) if right_anchor else sdef[f1 - j0]
            if s_hi <= s_lo + 0.05:
                continue
            e0 = f0 - 1 if left_anchor else f0
            e1 = f1 + 1 if right_anchor else f1
            ff = col_fracs(P, e0, e1)
            q = s_lo + (s_hi - s_lo) * ff
            G[e0:e1 + 1] = np.where(pin[e0:e1 + 1, None], G[e0:e1 + 1], at_s(curve, sc, q))
    R_t = (prm["tube_R_far"] if c > prm.get("far_c", 3.0) else prm["tube_R"]) * H
    if mode == "pinned_wall":
        jW = int(wall_pin.min())
        Wpt = P[jW]
        k = int(np.argmin(np.abs(U[:, 0] - (Wpt[0] + prm.get("ceil_join", 1.5)))))
        put(jn, jW, np.vstack([U[:max(k, 3)], Wpt[None]]))
        wall_ref = P[jW:jb + 1]
    else:
        if mode == "pinned_corner":
            jf = int(corner_pin.min()); jk = int(corner_pin.max())
            k = int(np.argmin(np.abs(U[:, 0] - (P[jf, 0] + prm.get("ceil_join", 1.5)))))
            put(jn, jf, np.vstack([U[:max(k, 3)], P[jf][None]]))
            S = P[jk]; thS = heading_deg(P, jk)
            Wc = wall_builder(S, thS, yb, R_t, prm, H)
            j_start = jk
        else:
            # free rows: the underside curls into a round tube (radius from far_R_tab), floor -> undercut face -> trough
            Wc = far_cavity(U, P, jn, c, H, yb, prm, info)
            S = Wc[0]; thS = 0.0
            j_start = jn
        # landmark: back-most point of the wall (middle of the flat minimum), searched before the tube floor
        lim = len(Wc)
        if mode == "free":
            yy_ = Wc[:, 1]; iymin = int(np.argmin(yy_[: max(len(Wc) - 5, 5)]))
            lim = max(iymin, 5)
        am = Wc[:lim, 0].min()
        near_min = np.nonzero(Wc[:lim, 0] <= am + 0.03)[0]
        ib = int(near_min[len(near_min) // 2])
        ib = int(np.clip(ib, 2, len(Wc) - 3))
        if j_start < jc:
            put(j_start, jc, Wc[:ib + 1]); put(jc, jb, Wc[ib:])
        else:
            put(j_start, jb, Wc)
        info.update(wall_start=[float(S[0]), float(S[1])], wall_start_heading=float(thS), R_t=float(R_t))
        wall_ref = Wc
        # trough bottom -> front rise -> first pinned front-sea column
        Bt = Wc[-1]; Fp = P[j_fp]
        span = max(Fp[0] - Bt[0], 2.0)
        fr = np.array([Bt, Bt + np.array([0.25 * span, 0.02 * H]), [Bt[0] + 0.6 * span, 0.5 * (yb * 0.4 + Fp[1])], Fp])
        sF = arclen(fr); fine = at_s(fr, sF, np.linspace(0, sF[-1], 300))
        fine = gaussian_filter1d(fine, 10, axis=0, mode="nearest"); fine[0] = Bt; fine[-1] = Fp
        put(jb, j_fp, fine)
    # ---------------- back: round cap + flank + one concave foot, passing the shell offset of the wall at 0.5 H
    wr = wall_ref[(wall_ref[:, 1] > 0.35 * H) & (wall_ref[:, 1] < 0.65 * H)]
    a_old5 = float(np.interp(0.5 * H, y[:jt + 1], a[:jt + 1]))
    if len(wr) > 3 and prm.get("back_from_wall", True):
        i = int(np.argmin(np.abs(wr[:, 1] - 0.5 * H)))
        a_ref = float(wr[i, 0]) - ts
    else:
        a_ref = a_old5
    a_ref = float(np.clip(a_ref, aT - prm.get("back_w5_max", 0.40) * H, aT - prm.get("back_w5_min", 0.28) * H))
    B, thm = back_curve(aT, H, a_ref, 0.5 * H, prm)
    info["back_th_max"] = thm; info["back_a_ref"] = a_ref
    Bf = B[::-1]
    ifoot = int(np.argmax(Bf[:, 1] > 0.02 * H))
    foot = Bf[max(ifoot - 1, 0):]
    put(18, jt, foot)
    if c < prm.get("back_keep_c", -0.8):
        # rows whose crest forms the painting's top outline: keep the loop-2 cap, blend into the new back below it
        y0k = prm.get("back_keep_y", 0.72) * H; dk = prm.get("back_keep_dy", 0.12) * H
        w = smoothstep((y[18:jt + 1] - y0k) / dk)[:, None]
        G[18:jt + 1] = w * P[18:jt + 1] + (1 - w) * G[18:jt + 1]
    G[0:18] = np.stack([np.linspace(min(P[0, 0], foot[0, 0] - 25.0), foot[0, 0] - 1.0, 18), np.zeros(18)], -1)
    # ---------------- where the underside next to the tip is pinned and the top is free: thin the hidden top
    und = np.arange(jn + 1, jn + 45)
    run = 0; best = 0
    for j in und:
        run = run + 1 if pin[j] else 0; best = max(best, run)
    hc = prm.get("hook_clear", 0.7)
    if best >= 10:
        uj = und[pin[und]]
        uj = uj[(P[uj, 0] < P[jn, 0] - hc) & (P[uj, 1] > P[jn, 1])]        # the underside proper, not the hook
        if len(uj) >= 5:
            Up = P[uj]
            nU = normals(gaussian_filter1d(Up, 1.5, axis=0, mode="nearest"))
            sg = 1.0 if nU[len(nU) // 2, 1] > 0 else -1.0
            Uo = Up + sg * (t_tip + 0.2) * nU
            o = np.argsort(Uo[:, 0])
            Lb = max(prm.get("top_lower_blend", 0.6) * (P[jn, 0] - aT), 1.0)
            for j in range(jt + 1, jn):
                if pin[j] or not (Uo[o[0], 0] <= G[j, 0] <= min(Uo[o[-1], 0], P[jn, 0] - hc)):
                    continue
                yo = float(np.interp(G[j, 0], Uo[o, 0], Uo[o, 1]))
                w = 1.0 - smoothstep((P[jn, 0] - hc - G[j, 0]) / Lb)
                w *= smoothstep((P[jn, 0] - G[j, 0] - hc) / 0.5)
                if yo < G[j, 1]:
                    G[j, 1] = G[j, 1] + w * (yo - G[j, 1])
            info["top_lowered"] = True
    # ---------------- no thickening of the lip: the new underside / ceiling never goes below the loop-2 one (carve only)
    if prm.get("no_thicken", True):
        seg = np.arange(jn + 5, jc + 1)
        Uo_ = P[seg]
        # the old underside as a function of a over its backward-running part (after the hook, before the wall turns down)
        am = np.minimum.accumulate(Uo_[:, 0])
        mono = np.r_[True, np.diff(am) < -1e-6]
        Um = Uo_[mono]
        if len(Um) > 5:
            o = np.argsort(Um[:, 0])
            ahi = Um[o[-1], 0]; alo = Um[o[0], 0]
            for j in range(jn + 5, jc + 1):
                if pin[j] or not (alo <= G[j, 0] <= ahi):
                    continue
                if G[j, 1] > 0.5 * H:
                    yo = float(np.interp(G[j, 0], Um[o, 0], Um[o, 1]))
                    if G[j, 1] < yo:
                        G[j, 1] = yo
    # ---------------- keep the redesigned cavity out of the painting's sky pocket in this row plane
    if prm.get("pocket_clamp", True):
        aa, yy, ok, _ = K.allowed_grid(c, (aT - 2.0, 30.0), (0.0, H + 1.0), 0.1)
        amax = np.full(len(yy), np.inf)
        for iy in range(len(yy)):
            bad = np.nonzero(~ok[iy])[0]
            if len(bad):
                amax[iy] = aa[bad[0]]
        m = prm.get("pocket_margin", 0.35)
        js = np.arange(jn + prm.get("pocket_from", 12), NU)
        js = js[~pin[js]]
        iy = np.clip(np.round((G[js, 1] - yy[0]) / 0.1).astype(int), 0, len(yy) - 1)
        lim = amax[iy] - m
        over = G[js, 0] > lim
        G[js[over], 0] = lim[over]
        info["pocket_clamped"] = int(over.sum())
    G[pin] = P[pin]                          # pinned columns: the fairing starts from their exact position
    dG = G - P
    dn = np.linalg.norm(dG, axis=1)
    cap = prm.get("max_disp_H", 0.5) * H
    G = P + dG * np.minimum(1.0, cap / np.maximum(dn, 1e-9))[:, None]
    return G


# ------------------------------------------------------------------ constrained fairing of one row
def fair_row(P, G, pin, w_goal=2e-3, lock_ends=True, soft=None):
    """x = argmin sum |D2 (x - G)|^2 + w |x - G|^2 over free vertices; pinned vertices = P.
    soft: optional per-vertex extra goal weight (pull toward G strongly, used for constraint violators)."""
    n = len(P)
    fixed = pin.copy()
    if lock_ends:
        fixed[0] = fixed[-1] = True
    D2 = sp.diags([np.ones(n - 2), -2 * np.ones(n - 2), np.ones(n - 2)], [0, 1, 2], shape=(n - 2, n))
    wv = np.full(n, w_goal) if soft is None else w_goal + soft
    M = (D2.T @ D2 + sp.diags(wv)).tocsr()
    free = np.nonzero(~fixed)[0]; fx = np.nonzero(fixed)[0]
    X = P.copy()
    E = np.zeros_like(P)
    E[fx] = P[fx] - G[fx]
    Mff = M[free][:, free].tocsc(); Mfx = M[free][:, fx]
    for k in range(2):
        E[free, k] = spla.spsolve(Mff, -(Mfx @ E[fx, k]))
    X[free] = G[free] + E[free]
    return X


def _viol_raw(c, A, Y, zold, margin_px, ss, z_tol):
    V1, tgt, fr = K.pframe()
    X = C.world(c, A, Y).reshape(-1, 3)
    Pp = fr.cam.project(X)
    ok, sdf = K.allowed_pts(c, A, Y, margin=margin_px)
    H_, W_ = zold.shape
    xs = np.clip(np.round((Pp[:, 0] + 0.5) * ss - 0.5).astype(int), 0, W_ - 1)
    ys = np.clip(np.round((Pp[:, 1] + 0.5) * ss - 0.5).astype(int), 0, H_ - 1)
    inimg = (Pp[:, 0] >= 0) & (Pp[:, 0] < W_ / ss) & (Pp[:, 1] >= 0) & (Pp[:, 1] < H_ / ss)
    zo = zold[ys, xs]
    zmin = zo.copy()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            zmin = np.minimum(zmin, zold[np.clip(ys + dy, 0, H_ - 1), np.clip(xs + dx, 0, W_ - 1)])
    front = inimg & np.isfinite(zmin) & (Pp[:, 2] < zmin - z_tol)
    above_h = Pp[:, 1] < K.HORIZON
    newcov = inimg & ~np.isfinite(zo) & above_h & (Pp[:, 0] >= tgt.x0) & (Pp[:, 0] <= tgt.x1)
    return ~ok, (front | newcov).reshape(A.shape)


def violations_zb(c, A, Y, A0, Y0, pin, margin_px=0.5, zold=None, z_tol=0.02):
    """end-to-end check: render the new sheet in the painting view (exact z-buffer, 2x) and flag the moved free vertices
    of every triangle that is now the first hit of a pixel where it lies in front of the loop-2 first hit by more than
    z_tol (or covers a pixel above the horizon that loop 2 left empty) -- i.e. where the painting view would change --
    plus moved free vertices that newly leave the allowed region (sub-pixel slivers).  Sea-level vertices below the
    horizon are exempt (they only change the painting's foreground sea, which is not scored; counted separately)."""
    z, ids = K.zbuffer(c, A, Y, 2)
    moved = (np.hypot(A - A0, Y - Y0) > 1e-4) & ~pin
    V1, tgt, fr = K.pframe()
    Pp = fr.cam.project(C.world(c, A, Y).reshape(-1, 3)).reshape(A.shape + (3,))
    sea_ok = (Pp[..., 1] > K.HORIZON + 3.0) & (Y <= 0.3) & (Y0 <= 0.3)
    moved &= ~sea_ok
    if zold is None:
        zold = np.load(os.path.join(K.WORK, "pin_F.npz"))["z"].astype(np.float64)
    Hh = z.shape[0]
    rows_img = (np.arange(Hh)[:, None] + 0.5) / 2 - 0.5
    changed = (np.isfinite(z) & ((z < zold - z_tol) | (~np.isfinite(zold) & (rows_img < K.HORIZON))))
    T = K.tris()
    seen = np.unique(ids[changed & (ids > 0)]) - 1
    vv = np.zeros(A.size, bool); vv[T[seen].ravel()] = True
    na, _ = _viol_raw(c, A, Y, np.full((2, 2), np.inf), margin_px, 2, 0.05)
    oa, _ = _viol_raw(c, A0, Y0, np.full((2, 2), np.inf), margin_px, 2, 0.05)
    return moved & na & ~oa, moved & vv.reshape(A.shape)


def violations(c, A, Y, A0, Y0, pin, zold, margin_px=1.5, ss=2, z_tol=0.05):
    """free vertices that newly (vs their loop-2 position) (a) leave the allowed region or (b) come in front of the
    loop-2 visible surface / onto pixels the loop-2 sheet did not cover above the horizon."""
    moved = (np.hypot(A - A0, Y - Y0) > 1e-4) & ~pin
    na, nf = _viol_raw(c, A, Y, zold, margin_px, ss, z_tol)
    oa, of = _viol_raw(c, A0, Y0, zold, margin_px, ss, z_tol)
    return moved & na & ~oa, moved & nf & ~of


def free_spans(pin):
    sp_ = []; j = 0; n = len(pin)
    while j < n:
        if not pin[j]:
            k = j
            while k + 1 < n and not pin[k + 1]:
                k += 1
            sp_.append((j, k)); j = k + 1
        else:
            j += 1
    return sp_


def run(prm_path, out, log=print):
    prm = json.load(open(prm_path, encoding="utf-8"))
    A0, Y0, c = K.load_rows(prm.get("base_rows", K.FINAL_ROWS))
    pin_npz = prm.get("pin_cache", os.path.join(K.WORK, "pin_F.npz"))
    zp = np.load(pin_npz)
    pin = zp["pinned"].copy(); zold = zp["z"].astype(np.float64)
    v1, _ = K.visibility(c, A0, Y0, 1)
    pin |= v1
    for _ in range(prm.get("pin_dil_rows", 1)):
        p2 = pin.copy(); p2[1:] |= pin[:-1]; p2[:-1] |= pin[1:]; pin = p2
    for _ in range(prm.get("pin_dil_cols", 1)):
        p2 = pin.copy(); p2[:, 1:] |= pin[:, :-1]; p2[:, :-1] |= pin[:, 1:]; pin = p2
    # the painting's foreground sea (sea-level vertices whose image is below the horizon) is not scored: free
    V1, tgt, fr = K.pframe()
    Pp0 = fr.cam.project(C.world(c, A0, Y0).reshape(-1, 3)).reshape(A0.shape + (3,))
    sea0 = (Pp0[..., 1] > K.HORIZON + 3.0) & (Y0 <= 0.3)
    if prm.get("free_sea", True):
        pin &= ~sea0
    H0 = float(Y0[159].max())
    A, Y = A0.copy(), Y0.copy()
    c_lo, c_hi = prm["zone"]
    infos = {}; goals = {}
    rows = [r for r in range(len(c)) if (c_lo <= c[r] <= c_hi) and Y0[r].max() >= prm.get("min_H", 2.0)]
    wz = {}
    for r in rows:
        P = np.stack([A0[r], Y0[r]], -1)
        info = {}
        try:
            G = design_row(P, pin[r], float(c[r]), H0, prm, info)
        except Exception as e:
            import traceback; traceback.print_exc()
            info["error"] = repr(e); infos[int(r)] = info; log("row %d error %r" % (r, e)); continue
        goals[r] = G; infos[int(r)] = info
        wz[r] = float(np.clip((c[r] - c_lo) / max(prm.get("zone_blend", 3.0), 1e-6), 0.0, 1.0))
    if prm.get("goal_sigma_c", 0) > 0 and goals:
        rr = sorted(goals); cc = c[rr]
        Gs = np.stack([goals[r] for r in rr]); P0 = np.stack([np.stack([A0[r], Y0[r]], -1) for r in rr])
        pm = np.stack([pin[r] for r in rr])
        sg = prm["goal_sigma_c"]
        Wm = np.exp(-0.5 * ((cc[:, None] - cc[None, :]) / sg) ** 2); Wm /= Wm.sum(1, keepdims=True)
        D = Gs - P0                                   # smooth the design displacement, not the positions
        Dm = np.einsum("ij,jkl->ikl", Wm, D)
        for i, r in enumerate(rr):
            goals[r] = np.where(pm[i][:, None], Gs[i], P0[i] + Dm[i])
    # span amplitude: a free span whose goal causes a violation is blended toward loop 2 as a whole (keeps its shape)
    amp = {r: np.ones(NU) for r in goals}
    spans = {r: free_spans(pin[r]) for r in goals}
    for it in range(prm.get("viol_iters", 6) + 1):
        for r in goals:
            P = np.stack([A0[r], Y0[r]], -1)
            Gr = P + amp[r][:, None] * (goals[r] - P)
            X = fair_row(P, Gr, pin[r], prm.get("w_goal", 2e-3))
            A[r] = A0[r] + wz[r] * (X[:, 0] - A0[r]); Y[r] = Y0[r] + wz[r] * (X[:, 1] - Y0[r])
        ba, bf = violations_zb(c, A, Y, A0, Y0, pin, prm.get("margin_px", 0.5), zold)
        nb = int((ba | bf).sum())
        log("iter %d: violations allowed %d front/newcov %d" % (it, int(ba.sum()), int(bf.sum())))
        if it == 0:
            rr_, jj_ = np.nonzero(ba | bf)
            np.savez_compressed(os.path.splitext(out)[0] + "_viol0.npz", r=rr_, j=jj_, ba=ba, bf=bf, A=A, Y=Y)
        if nb == 0 or it == prm.get("viol_iters", 6):
            break
        if it >= prm.get("viol_iters", 6) - 2:
            # last rounds: hard revert around the remaining violators
            badh = ba | bf
            for r in goals:
                for jv in np.nonzero(badh[r])[0]:
                    lo_, hi_ = max(jv - 12, 0), min(jv + 12, NU - 1)
                    for rr_ in (r - 1, r, r + 1):
                        if rr_ in amp:
                            amp[rr_][lo_:hi_ + 1] = 0.0
        bad = ba | bf
        for r in goals:
            if not bad[r].any():
                continue
            for (j0, j1) in spans[r]:
                jj = np.nonzero(bad[r, j0:j1 + 1])[0] + j0
                if not len(jj):
                    continue
                # local amplitude cut around the violators (+-25 columns, smooth), within the span
                lo_, hi_ = max(j0, jj.min() - 8), min(j1, jj.max() + 8)
                x = np.arange(j0, j1 + 1)
                wv = np.clip(1.0 - np.maximum(np.maximum(lo_ - x, x - hi_), 0) / 10.0, 0.0, 1.0)
                amp[r][j0:j1 + 1] *= 1.0 - prm.get("viol_cut", 0.4) * wv
        for r in goals:
            a_ = amp[r]
            for _ in range(3):
                a2 = a_.copy(); a2[1:] = np.minimum(a2[1:], a_[:-1]); a2[:-1] = np.minimum(a2[:-1], a_[1:])
                a_ = np.where(pin[r], a2, a_)
            amp[r] = a_
        # spread the cuts across neighbouring rows (a cut in one row alone shears the triangles between rows)
        rr = sorted(amp); M = np.stack([amp[r] for r in rr])
        Ms = M.copy()
        Ms[1:] = np.minimum(Ms[1:], 0.5 * (1 + M[:-1])); Ms[:-1] = np.minimum(Ms[:-1], 0.5 * (1 + M[1:]))
        for i, r in enumerate(rr):
            amp[r] = Ms[i]
    np.savez_compressed(out, A=A, Y=Y, c=c, A_pre=A0, Y_pre=Y0, pinned=pin)
    ampmin = {int(r): float(amp[r].min()) for r in amp if amp[r].min() < 0.999}
    json.dump({"rows": infos, "prm": prm, "violations_final": {"allowed": int(ba.sum()), "front_or_newcov": int(bf.sum())},
               "span_amplitude_min_by_row": ampmin},
              open(os.path.splitext(out)[0] + "_design.json", "w"), indent=1, default=float)
    log("saved %s" % out)
    return out


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
