# -*- coding: utf-8 -*-
"""Q20 final K*' (refinement of candidate A, loop 1): the pre-warp SECONDARY DESIGN, generated from numbers only.

The generator never reads the reference model.  Every row is a clamped cubic B-spline over a fixed list of named
control points (so the landmark columns mean the same thing on every row); the control points come from
  * knot tables over c (fin_params.json, PCHIP) for the back, the crest and the near-side lip / tube, and
  * the painting's sky pocket under the lip (fin_pocket.py, outline 72 envelope) for the far side (c > 0):
    the far rows are designed in "main-equivalent" coordinates (carried along the PaintingCam rays to c = 0) where
    the pocket is the same for every row, so they wrap the pocket as a thin round hood (the open far barrel, grafted
    from candidate B's idea) and are hidden from the painting camera by construction; then the barrel closes as a
    small curl behind the pocket and fades into the sea (no truncation, no planar fin).

Frame: K* 26修正01 section frame; rows are 240 constant-c planes, row 159 = c 0 (main section).  Columns: 400, landmarks
j_B 18 (back foot), j_top 90 (crest), j_tip 200 (lip nose), j_corner 314 (tube back-most point), j_facebot 379
(trough bottom), j_E 394 (front flat sea).
usage: py -3.10 fin_design.py fin_params.json out_pre_rows.npz
"""
import sys, os, json, math
import numpy as np
from scipy.interpolate import BSpline, PchipInterpolator
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import fin_pocket as PK

NAMES = ["sea0", "sea1", "sea2", "foot", "back1", "back2", "back3", "back4", "crest",
         "liptop1", "liptop2", "liptop3", "lipfront", "nose", "hooktip", "hookin", "under1", "under2", "under3", "ceil",
         "wall0", "wall1", "wall2", "wall3", "wall4", "floor", "face", "trough", "rise", "front", "sea3", "sea4"]
IX = {n: i for i, n in enumerate(NAMES)}
CP_LM = {"j_B": "foot", "j_top": "crest", "j_tip": "nose", "j_corner": "wall1", "j_facebot": "trough", "j_E": "front"}
LIP_TUBE = ["liptop1", "liptop2", "liptop3", "lipfront", "nose", "hooktip", "hookin", "under1", "under2", "under3", "ceil",
            "wall0", "wall1", "wall2", "wall3", "wall4", "floor", "face", "trough", "rise"]


# ------------------------------------------------------------------ rows and knot tables
def c_rows(prm):
    g = prm["grid"]
    fine, c_fine = g["near_fine_step"], g["near_fine_extent"]
    n_fine = int(round(c_fine / fine)); n_rest = 159 - n_fine
    L = -g["c_near"] - c_fine
    lo, hi = 1.0, 1.3
    for _ in range(80):
        q = 0.5 * (lo + hi)
        s = fine * q * (q ** n_rest - 1) / (q - 1)
        lo, hi = (q, hi) if s < L else (lo, q)
    steps = np.r_[np.full(n_fine, fine), fine * q ** np.arange(1, n_rest + 1)]
    steps *= (c_fine + L) / steps.sum()
    near = -np.r_[0.0, np.cumsum(steps)][::-1]
    nfine = g.get("far_fine_rows", 64)
    t = np.arange(80)
    sp = np.where(t < nfine, 1.0, 1.0 + (t - nfine) / (80 - nfine) * g.get("far_growth", 4.0))
    sp = np.convolve(np.pad(sp, 4, mode="edge"), np.ones(9) / 9, "valid")
    far = np.cumsum(sp); far *= g["c_far"] / far[-1]
    c = np.r_[near, far]
    assert len(c) == 240 and abs(c[159]) < 1e-9
    return c


def knots(tab, c):
    k = np.array(tab, float)
    f = PchipInterpolator(k[:, 0], k[:, 1], extrapolate=False)
    return f(np.clip(c, k[0, 0], k[-1, 0]))


def row_params(prm, c):
    out = {}
    for k, tab in prm["knots"].items():
        v = knots(tab, c)
        sm = prm.get("smooth_c", {}).get(k)
        if sm:
            # extra smoothing along c (metres), on the non-uniform rows
            W = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sm) ** 2); W /= W.sum(1, keepdims=True)
            v = W @ v
        out[k] = v
    return out


# ------------------------------------------------------------------ one row: the control polygon
def lam_of(c, cs):
    return (0.0 - cs[2]) / (c - cs[2])


def edge_real(c, cs, yv):
    """a of the painting's pocket left boundary (outline 72, main-eq) mapped into the row plane c at height yv."""
    L = lam_of(c, cs)
    yq = cs[1] + (yv - cs[1]) * L
    la = float(PK.left_a_eq(yq))
    return cs[0] + (la - cs[0]) / L if np.isfinite(la) else np.inf


def tip_u(c, cs, a_target):
    """pocket-path fraction u (0 = painted lip tip ... 0.5 = tube top-left corner) whose image in plane c lies at
    the real a_target (the lip tip retreats at a steady rate along the crest, F05 lip-tip line)."""
    uu = np.linspace(0.0, 0.52, 261)
    Pq, _ = PK.path_at(uu)
    ar = PK.to_real(Pq, c, cs)[:, 0]
    ar = np.minimum.accumulate(ar)          # monotone (the claw head bump)
    if a_target >= ar[0]:
        return 0.0
    if a_target <= ar[-1]:
        return 0.52
    return float(np.interp(-a_target, -ar, uu))


def back_target(p, n_pts=120):
    """target back curve from the crest top down to the foot on the back sea: superellipse quadrant
    |x/Wb|^n + |(y - ys)/(H - ys)|^n = 1 above ys, then a concave flare (quarter of a cosine) to the sea."""
    H, aT, Wb = p["H"], p["aT"], p["Wb"]
    n = p.get("back_n", 2.5); ys = p.get("back_ys", 0.37) * H; Bv = H - ys
    t = np.linspace(0, 1, n_pts)
    x = -Wb * np.sin(0.5 * np.pi * t) ** (2.0 / n)
    y = ys + Bv * np.cos(0.5 * np.pi * t) ** (2.0 / n)
    top = np.stack([aT + x, y], -1)
    L = p.get("back_flare", 0.30) * H + 0.2 * Wb
    u = np.linspace(0, 1, n_pts)[1:]
    fl = np.stack([aT - Wb - L * (1 - np.cos(0.5 * np.pi * u)) ** 1.0, ys * np.cos(0.5 * np.pi * u) ** 1.6], -1)
    return np.vstack([top, fl])


def fit_back(P, p, iters=6):
    """move the back control points so that the B-spline lies on the back target (fixed-point, nearest target point)."""
    bt = back_target(p)
    idx = [IX[n] for n in ("crest", "back4", "back3", "back2", "back1", "foot")]
    for _ in range(iters):
        u, Qc, gre = eval_bspline(P, 1500)
        for k, i in enumerate(idx):
            j = int(np.argmin(np.abs(u - gre[i])))
            d = np.linalg.norm(bt - Qc[j], axis=1); m = int(np.argmin(d))
            err = bt[m] - Qc[j]
            if k == 0:
                err[0] = 0.0          # the crest keeps its a
            P[i] += 0.9 * err
    return P


def lip_target(p, a):
    """the painting's lip-top shape (131 right part + 132, main-eq) stretched between this row's crest and nose:
    the height of the lip top at a (thin blade on the painted outline; the warp then hardly moves it)."""
    L = PK.lip_top_eq()
    a0, y0 = L[0]; a1, y1 = L[-1]
    aT, H = p["aT"], p["H"]; an, yn = p["a_nose"] + 0.3, p["y_nose"] - 0.12 * p["hook_drop"]
    u = (a - aT) / max(an - aT, 1e-3)
    ae = a0 + u * (a1 - a0)
    ye = np.interp(ae, L[:, 0], L[:, 1])
    v = (ye - y1) / max(y0 - y1, 1e-3)                # 1 at the crest, 0 at the tip
    return np.array([a, yn + v * (H - yn) + p.get("lip_lift", 0.0) * np.sin(np.pi * np.clip(u, 0, 1))])


def close_override(p, c, cs):
    """closing curls (far side, after the lip has retracted): the nose sits just behind the painting's pocket (its
    left boundary at the nose height, main-eq clearance `gap`), the curl's tube undercuts back below the nose (a lip on
    every big row, F05), the crest is a broad round top ~r behind the nose (F02)."""
    k = float(np.clip(p.get("close", 0.0), 0.0, 1.0))
    if k <= 0 or c <= 0:
        return p
    q = dict(p)
    L = lam_of(c, cs)
    yn = p["y_nose"]
    yq = cs[1] + (yn - cs[1]) * L
    la = float(PK.left_a_eq(yq))
    if np.isfinite(la):
        an_c = cs[0] + (la - p["gap"] - cs[0]) / L - 0.30
        q["a_nose"] = (1 - k) * p["a_nose"] + k * min(p["a_nose"], an_c)
    an = q["a_nose"]; H = p["H"]
    # the curl size follows from the crest line (knot table aT, which retreats smoothly behind the pocket)
    r = float(np.clip((an - p["aT"]) / 1.05, p.get("curl_rmin", 1.6), 0.2 * H + 0.8))
    q["aT"] = (1 - k) * p["aT"] + k * (an - 1.05 * r)
    q["a_ceil"] = (1 - k) * p["a_ceil"] + k * (an - 0.85 * r)
    q["y_ceil"] = (1 - k) * p["y_ceil"] + k * (yn - 0.05 * r)
    q["a_wall"] = (1 - k) * p["a_wall"] + k * (an - 1.9 * r)
    q["y_wm"] = (1 - k) * p["y_wm"] + k * max(0.30 * H, yn - 1.9 * r)
    q["lean"] = (1 - k) * p["lean"] + k * (1.6 * r)
    q["a_trough"] = (1 - k) * p["a_trough"] + k * (an - 1.9 * r + 1.6 * r + 2.5)
    q["Wb"] = (1 - k) * p["Wb"] + k * min(p["Wb"] + p.get("close_wb_add", 0.0), 0.9 * r + p.get("close_wb_cap", 1.6))
    q["hook_drop"] = (1 - k) * p["hook_drop"] + k * min(p["hook_drop"], 0.35 * r)
    q["edge_hug"] = 0.0
    return q


def near_polygon(p, c=0.0, cs=None):
    """near side / main section / closing curls (real coordinates of the row plane)."""
    H, aT, Wb, fl = p["H"], p["aT"], p["Wb"], p["foot_len"]
    an, yn, hk, tl = p["a_nose"], p["y_nose"], p["hook_drop"], p["lip_t"]
    Q = {}
    # back: a superellipse dome (broad round top, steep side at y_s) that rolls into a concave foot: one inflection,
    # no straight board, a thin shell around the deep tube (F03).  The B-spline is fitted onto this target below.
    Q["_back_target"] = back_target(p)
    bt = Q["_back_target"]
    def at_frac(f):
        s_ = C.arclen(bt[:, 0], bt[:, 1]); q = f * s_[-1]
        return np.array([np.interp(q, s_, bt[:, 0]), np.interp(q, s_, bt[:, 1])])
    Q["crest"] = tuple(at_frac(0.0) + np.array([0.0, 0.02 * H]))
    Q["back4"] = tuple(at_frac(0.12))
    Q["back3"] = tuple(at_frac(0.30))
    Q["back2"] = tuple(at_frac(0.50))
    Q["back1"] = tuple(at_frac(0.72))
    fp = bt[-1]
    Q["foot"] = tuple(at_frac(0.92))
    Q["sea2"] = (fp[0] - 1.0 - 0.5 * fl, 0.0)
    Q["sea1"] = (fp[0] - 12.0 - fl, 0.0)
    Q["sea0"] = (fp[0] - 40.0, 0.0)
    # lip top: crest -> nose.  S: a convex shoulder, a small concave waist, then the convex hook (painting order)
    d = an - aT; hh = H - yn
    Q["liptop1"] = (aT + 0.32 * d, H - 0.08 * hh)
    Q["liptop2"] = (an - 0.34 * d, yn + (0.26 + 0.04 * p["lip_full"]) * hh)
    Q["lipfront"] = (an - 0.20, yn + 0.10 + 0.03 * hh)
    Q["liptop3"] = (0.5 * (Q["liptop2"][0] + Q["lipfront"][0]), 0.5 * (Q["liptop2"][1] + Q["lipfront"][1]) + 0.1 * hh)
    wl = float(np.clip(p.get("lip_paint", 0.0), 0.0, 1.0))
    if wl > 0:
        for nm, f in (("liptop1", 0.25), ("liptop2", 0.50), ("liptop3", 0.74), ("lipfront", 0.88)):
            q = lip_target(p, f * (an + 0.3 - aT) + aT)
            Q[nm] = ((1 - wl) * Q[nm][0] + wl * q[0], (1 - wl) * Q[nm][1] + wl * q[1])
    # the hook: a thin blade whose edge curls over and hangs as a narrow claw right at the tip (within ~0.6 m), then
    # the blade's underside runs back just under its top (F06: thin lip, not a wedge)
    Q["nose"] = (an + 0.30, yn - 0.12 * hk)
    Q["hooktip"] = (an + 0.14, yn - 1.00 * hk)
    Q["hookin"] = (an - 0.10, yn - 0.62 * hk)
    top_a = [Q["crest"][0], Q["liptop1"][0], Q["liptop2"][0], Q["liptop3"][0], Q["lipfront"][0]]
    top_y = [Q["crest"][1], Q["liptop1"][1], Q["liptop2"][1], Q["liptop3"][1], Q["lipfront"][1]]
    yt1 = np.interp(an - 0.50, top_a, top_y)
    Q["under1"] = (an - 0.50, yt1 - tl - 0.10)
    ac, yc = p["a_ceil"], p["y_ceil"]
    a2 = 0.55 * (an - 0.55) + 0.45 * ac
    yt2 = np.interp(a2, top_a, top_y)
    Q["under2"] = (a2, max(yt2 - 2.2 * tl - 0.3, yc + 0.25))
    Q["under3"] = (0.3 * a2 + 0.7 * ac + 0.4, yc + 0.12)
    Q["ceil"] = (ac, yc)
    # tube back wall: round top-left corner, back-most point at y_wm, then the lower wall leans forward into the
    # trough along a concave curve (the painted inner wall 72 steepens upwards; no vertical plinth, F08)
    aw, ywm, ln = p["a_wall"], p["y_wm"], p["lean"]
    yb, atr = p["y_bot"], p["a_trough"]
    Q["wall0"] = (aw + 0.22 * (ac - aw), ywm + 0.70 * (yc - ywm))
    Q["wall1"] = (aw, ywm)
    Q["wall2"] = (aw + 0.10 * ln, 0.66 * ywm)
    Q["wall3"] = (aw + 0.36 * ln, 0.36 * ywm)
    Q["wall4"] = (aw + 0.72 * ln, 0.10 * ywm)
    Q["floor"] = (aw + 1.0 * ln + 0.25 * max(atr - aw - ln, 0.5), 0.40 * yb)
    Q["trough"] = (atr, yb)
    af = p["a_front"]
    Q["rise"] = (atr + 0.45 * (af - atr), 0.55 * yb)
    Q["front"] = (af, 0.0)
    Q["sea3"] = (af + 12.0, 0.0)
    Q["sea4"] = (af + 40.0, 0.0)
    eh = float(np.clip(p.get("edge_hug", 0.0), 0.0, 1.0))
    if eh > 0 and cs is not None:
        # the main-section rows form the lower end of outline 72 (the painted inner wall down to the horizon)
        for nm, u, off in (("wall2", 0.80, 0.05), ("wall3", 0.88, 0.05), ("wall4", 0.95, 0.05)):
            q, o = PK.path_at(u)
            R = PK.to_real(q + off * o, c, cs)
            Q[nm] = tuple((1 - eh) * np.array(Q[nm]) + eh * R)
        q, o = PK.path_at(1.0)
        R = PK.to_real(q + np.array([0.6, -0.9]), c, cs)
        Q["floor"] = tuple((1 - eh) * np.array(Q["floor"]) + eh * R)
    fa = Q["floor"][0]
    Q["face"] = (fa + 0.45 * max(atr - fa, 1.0), 0.80 * yb)
    Q["trough"] = (max(atr, fa + 2.0), yb)
    return Q


def hood_polygon(p, c, Qn, cs):
    """far side: the lip / tube control points of a hood that wraps the painting's sky pocket (main-equivalent
    coordinates), mapped to the row plane.  The back and crest come from the knot tables (Qn).  The lip tip retreats
    at a steady real rate along the underside; the tube's lower back wall undercuts (a round far tube with a lip)."""
    un = p["u_nose"]; dl = p["clear"]; tn = p["hood_t"]
    ub = PK.u_of_point("back")
    def P(u, off):
        q, o = PK.path_at(u)
        return q + off * o
    blunt = float(np.clip((un - 0.30) / 0.15, 0.0, 1.0)) * p.get("blunt", 1.0)
    eq = {}
    uc = 0.47
    eq["nose"] = P(un, dl + (0.40 + 2.2 * blunt) * tn)
    eq["hooktip"] = P(un + 0.008, dl)
    eq["hookin"] = P(un + 0.020, dl)
    uu = np.linspace(un + 0.035, max(uc, un + 0.06), 4)
    eq["under1"] = P(uu[0], dl); eq["under2"] = P(uu[1], dl); eq["under3"] = P(uu[2], dl)
    eq["ceil"] = P(max(0.505, un + 0.075), dl)
    eq["wall0"] = P(max(0.56, un + 0.10), dl)
    eq["wall1"] = P(max(ub, un + 0.12), dl)
    # undercut lower back wall (main-eq): nearly vertical below the back-most point, then forward into the floor
    b = P(max(ub, un + 0.12), dl)
    uw = float(np.clip(p.get("undercut", 1.0), 0.0, 1.0))
    hug2, hug3, hug4 = P(0.70, dl), P(0.80, dl), P(0.90, dl)
    # the hood forms the painted inner wall (72 lower) down to ~5.5 m (main-eq), then undercuts below it (the far
    # tube's rounded bottom; the main-section rows form the last metres of 72 above the horizon)
    deep = 1.6 + 2.6 * float(np.clip((un - 0.30) / 0.18, 0.0, 1.0))      # the undercut deepens as the lip retracts
    und4 = np.array([P(0.82, dl)[0] - deep, 3.9])
    eq["wall2"] = hug2
    eq["wall3"] = uw * P(0.82, dl) + (1 - uw) * hug3
    eq["wall4"] = uw * und4 + (1 - uw) * hug4
    eq["floor"] = uw * np.array([und4[0] + 2.2, 1.3]) + (1 - uw) * (P(1.0, dl) + np.array([-0.2, -0.35]))
    R = {k: PK.to_real(v, c, cs) for k, v in eq.items()}
    # lip top: from the crest (knot table) down to the nose, a thin blade near the nose (hood_t), thicker at the root
    cr = np.array(Qn["crest"])
    for k, f, t in (("lipfront", 0.86, 0.9), ("liptop3", 0.72, 1.15), ("liptop2", 0.55, 1.6), ("liptop1", 0.22, 3.6)):
        uq = un + (1 - f) * (uc - un)
        q = PK.to_real(P(uq, dl + (t + 1.4 * blunt) * tn), c, cs)
        lin = cr + f * (R["nose"] - cr)
        w = 0.92 if k != "liptop1" else 0.6
        R[k] = w * q + (1 - w) * lin
    # below the horizon (free in the painting view): the floor continues into the trough and the front sea
    fl = R["floor"]
    yb, af = p["y_bot"], p["a_front"]
    atr = max(p["a_trough"], fl[0] + 2.5)
    R["face"] = np.array([0.5 * (fl[0] + atr), 0.8 * yb])
    R["trough"] = np.array([atr, yb])
    R["rise"] = np.array([atr + 0.45 * (af - atr), 0.55 * yb])
    return R


def control_polygon(p, c, cs):
    p = dict(p)
    if c > 0 and p.get("tip_rate", 0) > 0 and p.get("hood", 0) > 0:
        p["u_nose"] = tip_u(c, cs, p["tip_a0"] - p["tip_rate"] * c)
    p = close_override(p, c, cs)
    Q = near_polygon(p, c, cs)
    hm = float(np.clip(p["hood"], 0.0, 1.0))
    if hm > 0 and c > 0:
        R = hood_polygon(p, c, Q, cs)
        for k, v in R.items():
            Q[k] = tuple((1 - hm) * np.array(Q[k]) + hm * np.asarray(v))
    P = np.array([Q[n] for n in NAMES], float)
    if p.get("back_fit", 1.0) > 0:
        P = fit_back(P, p)
    wl = float(np.clip(p.get("lip_paint", 0.0), 0.0, 1.0)) * (1.0 - (float(np.clip(p["hood"], 0, 1)) if c > 0 else 0.0))
    if wl > 0.01:
        # the B-spline sits inside its control polygon: lift the lip-top control points until the curve itself lies on
        # the painted lip-top shape
        idx = [IX[n] for n in ("liptop1", "liptop2", "liptop3", "lipfront")]
        for _ in range(8):
            u, Qc, gre = eval_bspline(P, 1500)
            for i in idx:
                j = int(np.argmin(np.abs(u - gre[i])))
                tgt_y = lip_target(p, Qc[j, 0])[1]
                P[i, 1] += 1.0 * wl * (tgt_y - Qc[j, 1])
            # the thin blade: its underside follows the lifted top at the lip thickness
            yt1 = lip_target(p, P[IX["under1"], 0])[1]
            P[IX["under1"], 1] = (1 - wl) * P[IX["under1"], 1] + wl * (yt1 - p["lip_t"] - 0.20)
    kc = float(np.clip(p.get("close", 0.0), 0.0, 1.0)) if c > 0 else 0.0
    if kc > 0 and p.get("close_shear", 0.0) > 0:
        # the closing curl leans forward like a curling ribbon: its foot sits further back than its crest
        ytop = max(p["H"], 0.1)
        sh = kc * p["close_shear"] * np.clip(ytop - np.maximum(P[:, 1], 0.0), 0.0, ytop)
        inner = [IX[n] for n in ("wall1", "wall2", "wall3", "wall4", "floor", "face", "trough", "rise", "front", "sea3", "sea4")]
        sh[inner] *= 0.45            # the curl's inner wall still leans forward into the sea (no vertical step, F08)
        P[:, 0] -= sh
    # tiny rows (the ends of the crest): the curl fades into a plain rounded bump (no folded micro-curl)
    th = p.get("tiny_h", 5.5); tw = p.get("tiny_w", 3.5)
    tiny = max(float(np.clip((th - p["H"]) / tw, 0.0, 1.0)), p.get("force_tiny", 0.0))
    tiny = tiny * tiny * (3 - 2 * tiny)
    if tiny > 0:
        H, aT = p["H"], p["aT"]
        a_end = max(p["a_front"], aT + 3.0 * max(H, 0.3) + 2.0)
        names = LIP_TUBE
        for k, nm in enumerate(names):
            t = (k + 1) / (len(names) + 1)
            q = (aT + t * (a_end - aT) * 0.6 + (a_end - aT) * 0.4 * t * t, H * (1 - t) ** 2 * (1 + 2 * t))
            P[IX[nm]] = (1 - tiny) * P[IX[nm]] + tiny * np.array(q)
    return P


def eval_bspline(Pc, n=4000):
    k = 3; m = len(Pc)
    t = np.r_[np.zeros(k), np.linspace(0, 1, m - k + 1), np.ones(k)]
    u = np.linspace(0, 1, n)
    sp = BSpline(t, Pc, k)
    gre = np.array([t[i + 1:i + k + 1].mean() for i in range(m)])
    return u, sp(u), gre


def row_curve(p, c, cs, n=4000):
    Pc = control_polygon(p, c, cs)
    u, Q, gre = eval_bspline(Pc, n)
    lm = {key: int(np.argmin(np.abs(u - gre[IX[nm]]))) for key, nm in CP_LM.items()}
    it = int(np.argmax(Q[:lm["j_tip"], 1])); lm["j_top"] = it
    seg = np.arange(it, lm["j_corner"])
    hi = seg[Q[seg, 1] > 0.3 * Q[it, 1]]
    if len(hi):
        lm["j_tip"] = int(hi[np.argmax(Q[hi, 0])])
    seg = np.arange(lm["j_tip"] + 5, lm["j_facebot"])
    ok = seg[Q[seg, 1] > 0.12 * Q[it, 1]]
    if len(ok):
        lm["j_corner"] = int(ok[np.argmin(Q[ok, 0])])
    seg = np.arange(lm["j_corner"], lm["j_E"])
    lm["j_facebot"] = int(seg[np.argmin(Q[seg, 1])])
    b = np.nonzero(Q[:it, 1] < 0.01 * Q[it, 1] + 0.01)[0]
    if len(b):
        lm["j_B"] = int(b[-1])
    e = np.nonzero(Q[lm["j_facebot"]:, 1] > -0.01)[0]
    if len(e):
        lm["j_E"] = max(lm["j_facebot"] + int(e[0]), lm["j_facebot"] + 5)
    return Q, lm


def resample400(Q, L, a_back=-49.2, a_front=33.0):
    s = C.arclen(Q[:, 0], Q[:, 1])
    order = ["j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"]
    A = np.zeros(400); Y = np.zeros(400)
    jB, jE = C.LM["j_B"], C.LM["j_E"]
    sB, sE = L["j_B"], L["j_E"]
    aB = np.interp(sB, s, Q[:, 0]); aE = np.interp(sE, s, Q[:, 0])
    A[:jB + 1] = np.linspace(min(a_back, aB - 5), aB, jB + 1); Y[:jB + 1] = np.interp(sB, s, Q[:, 1]) * np.linspace(0, 1, jB + 1) ** 3
    A[jE:] = np.linspace(aE, max(a_front, aE + 5), 400 - jE); Y[jE:] = np.interp(sE, s, Q[:, 1]) * np.linspace(1, 0, 400 - jE) ** 3
    segs = list(zip(order[:-1], order[1:]))
    u = [(L[k1] - L[k0]) / (C.LM[k1] - C.LM[k0]) for k0, k1 in segs]
    joint = [u[0]] + [float(np.sqrt(u[i] * u[i + 1])) for i in range(len(u) - 1)] + [u[-1]]
    for i, (k0, k1) in enumerate(segs):
        j0, j1 = C.LM[k0], C.LM[k1]
        n = j1 - j0
        h = np.linspace(joint[i], joint[i + 1], n)
        h = np.maximum(h, 1e-6); h *= (L[k1] - L[k0]) / h.sum()
        ss = L[k0] + np.r_[0.0, np.cumsum(h)]
        A[j0:j1 + 1] = np.interp(ss, s, Q[:, 0]); Y[j0:j1 + 1] = np.interp(ss, s, Q[:, 1])
    return A, Y


def section_crossings(P):
    p, q = P[:-1], P[1:]
    dd = q - p
    dx = dd[:, None, :]; ex = dd[None, :, :]
    w = p[None, :, :] - p[:, None, :]
    den = dx[..., 0] * ex[..., 1] - dx[..., 1] * ex[..., 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (w[..., 0] * ex[..., 1] - w[..., 1] * ex[..., 0]) / den
        t = (w[..., 0] * dx[..., 1] - w[..., 1] * dx[..., 0]) / den
    hit = (np.abs(den) > 1e-12) & (s > 1e-9) & (s < 1 - 1e-9) & (t > 1e-9) & (t < 1 - 1e-9)
    return int(np.triu(hit, 2).sum())


def build(prm, log=print):
    c = c_rows(prm)
    P = row_params(prm, c)
    cs = PK.cam_sec()
    PK.pocket()
    nv = len(c)
    keys = list(P.keys())
    curves, lms = [], []
    for r in range(nv):
        p = {k: float(P[k][r]) for k in keys}
        if p["H"] < 0.05:
            curves.append(None); lms.append(None); continue
        Q, lm = row_curve(p, c[r], cs)
        curves.append(Q); lms.append(lm)
    fr = {k: np.full(nv, np.nan) for k in C.LM}
    for r in range(nv):
        if curves[r] is None:
            continue
        s = C.arclen(curves[r][:, 0], curves[r][:, 1])
        for k in C.LM:
            fr[k][r] = s[lms[r][k]] / s[-1]
    ok = np.isfinite(fr["j_B"])
    sig = prm["grid"].get("landmark_smooth_rows", 2.0)
    for k in C.LM:
        v = fr[k].copy()
        if (~ok).any():
            v[~ok] = np.interp(np.nonzero(~ok)[0], np.nonzero(ok)[0], v[ok])
        fr[k] = gaussian_filter1d(v, sig, mode="nearest")
    A = np.zeros((nv, 400)); Y = np.zeros((nv, 400))
    forced = np.zeros(nv)
    order = ["j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"]
    def sample(r, ft):
        p = {k: float(P[k][r]) for k in keys}; p["force_tiny"] = ft
        Q, _ = row_curve(p, c[r], cs)
        s = C.arclen(Q[:, 0], Q[:, 1])
        L = {k: fr[k][r] * s[-1] for k in C.LM}
        for a_, b_ in zip(order[:-1], order[1:]):
            L[b_] = max(L[b_], L[a_] + 0.05)
        return resample400(Q, L)
    # pass 1: which small rows fold onto themselves, and how much flattening they need
    for r in range(nv):
        if curves[r] is None or P["H"][r] > 6.0:
            continue
        for ft in (0.0, 0.25, 0.5, 0.75, 1.0):
            a_, y_ = sample(r, ft)
            if section_crossings(np.stack([a_, y_], -1)) == 0:
                break
        forced[r] = ft
    # the flattening varies smoothly along the crest (no row-to-row switching -> no cross-row creases)
    if forced.any():
        fm = np.maximum.reduce([np.roll(forced, k) for k in range(-3, 4)])
        forced = np.clip(gaussian_filter1d(fm, 2.0), 0.0, 1.0)
    for r in range(nv):
        if curves[r] is None:
            A[r] = np.linspace(-49.2, 33.0, 400); Y[r] = 0.0; continue
        A[r], Y[r] = sample(r, float(forced[r]))
    # design-level relaxation along the crest (the sheet is one smooth surface; rows stay planar)
    sg = prm["grid"].get("design_relax_sigma", 0.0)
    if sg > 0:
        import fin_relax as RX
        w = np.clip((np.abs(Y) - 0.02) / 0.3, 0.0, 1.0)            # the flat sea keeps its own spacing
        w = np.maximum(w, np.roll(w, 1, 1)); w = np.maximum(w, np.roll(w, -1, 1))
        tab = prm["grid"].get("design_relax_sigma_c")
        sgc = np.interp(c, [t[0] for t in tab], [t[1] for t in tab]) if tab else sg
        A, Y = RX.cross_rows(A, Y, c, sgc, weight=w)
    P["force_tiny_used"] = forced
    return c, A, Y, P


def main(prm_path, out):
    prm = json.load(open(prm_path, encoding="utf-8"))
    c, A, Y, P = build(prm)
    np.savez_compressed(out, A=A, Y=Y, c=c, **{"p_" + k: v for k, v in P.items()})
    H = Y.max(1)
    print("ok", out, "H0 %.2f Hmax %.2f at c %.2f" % (Y[159].max(), H.max(), c[np.argmax(H)]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
