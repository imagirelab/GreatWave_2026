# -*- coding: utf-8 -*-
"""Q20 cand A, step 2: the SECONDARY DESIGN of K* (pre-warp shape), generated from numbers only.

The generator never reads the reference model.  Its section family is our own construction (a clamped cubic B-spline
per row, 26 control points), and its parameters are functions of c given as knot tables (candA_params.json).
The knot values were set from the reference model's measured large-form numbers (candA_measure_model.py:
back width, shell thickness, tube size / depth, lip overhang, the barrel that continues past the main section,
three lobes on the near-shoulder face) and then changed on purpose (secondary design; see the difference record):
smoother back (one inflection, superellipse-like), round top, thin hooked lip, a front trough on the open sea instead of
the sculpture's bowl/base, a far end that tapers into a thin curl hidden from the painting camera, no claws / fingers.

Rows: 240 constant-c planes of the K* 26修正01 section frame, row 159 = c 0 (main section).  Columns: 400, landmarks
j_B 18 (back foot), j_top 90 (crest), j_tip 200 (lip nose = most forward point), j_corner 314 (back-most point of the
tube wall), j_facebot 379 (trough bottom), j_E 394 (front sea).
usage: py -3.10 candA_design.py <params.json> <out_rows.npz>
"""
import sys, os, json, math
import numpy as np
from scipy.interpolate import BSpline, PchipInterpolator
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

NCP = 26
# control-point index of each landmark (the curve point nearest to the control point's parameter is used)
CP_LM = {"j_B": "foot", "j_top": "crest", "j_tip": "nose", "j_corner": "wall", "j_facebot": "trough", "j_E": "front"}


def c_rows(prm):
    """row c values: 159 rows from c_near to 0 (fine near the body), 80 rows from 0 to c_far."""
    g = prm["grid"]
    fine, c_fine = g["near_fine_step"], g["near_fine_extent"]
    n_fine = int(round(c_fine / fine))
    n_rest = 159 - n_fine
    L = -g["c_near"] - c_fine
    # geometric growth from `fine` so that n_rest steps cover L
    lo, hi = 1.0, 1.3
    for _ in range(80):
        q = 0.5 * (lo + hi)
        s = fine * q * (q ** n_rest - 1) / (q - 1)
        lo, hi = (q, hi) if s < L else (lo, q)
    steps = np.r_[np.full(n_fine, fine), fine * q ** np.arange(1, n_rest + 1)]
    steps *= (c_fine + L) / steps.sum()
    near = -np.r_[0.0, np.cumsum(steps)][::-1]           # 160 values, last = 0
    # far side: fine rows where the lip retracts along the painting's under-lip outline (0..8 m), coarser to the end
    # smoothly graded far rows: ~0.1 m where the lip retracts (0..5.5 m), then growing smoothly to the far end
    nfine = g.get("far_fine_rows", 52)
    t = np.arange(80)
    sp = np.where(t < nfine, 1.0, 1.0 + (t - nfine) / (80 - nfine) * 4.0)
    sp = np.convolve(np.pad(sp, 4, mode="edge"), np.ones(9) / 9, "valid")
    far = np.cumsum(sp); far *= g["c_far"] / far[-1]
    c = np.r_[near, far]
    assert len(c) == 240 and abs(c[159]) < 1e-9
    return c


def knots(tab, c):
    """PCHIP through a knot table [[c, v], ...] (flat beyond the ends)."""
    k = np.array(tab, float)
    f = PchipInterpolator(k[:, 0], k[:, 1], extrapolate=False)
    v = f(np.clip(c, k[0, 0], k[-1, 0]))
    return v


def control_polygon(p):
    """control points (a, y) for one row (fixed count, so landmark indices are the same for every row).
    outer: back sea -> concave foot -> convex back (one inflection) -> round crest -> lip top (S: waist) -> nose -> hook;
    inner: hook -> thin lip underside -> tube ceiling -> tube back wall (elliptic tube) -> [second-crest ledge:
           lobe + pocket] -> tube bottom = trough bottom (y_bot) -> gentle rise -> front sea."""
    H, aT, Wb = p["H"], p["aT"], p["Wb"]
    an, yn, hk, tl = p["a_nose"], p["y_nose"], p["hook_drop"], p["lip_t"]
    aw, yc, yb = p["a_wall"], p["y_ceil"], p["y_bot"]
    afr = p["a_front"]
    fl = p["foot_len"]
    lf = p["lip_full"]
    Ra = p["tube_Ra"]                       # horizontal semi-axis of the elliptic tube (back wall -> centre)
    # the tube's widest point (vertical wall) sits at y_eq; the upper and lower halves have their own vertical
    # semi-axes, so below ~4 m the wall already leans (no vertical step into the trough, F08)
    yeq = float(np.clip(p.get("tube_eq", 0.5), 0.2, 0.8))
    ytc = yb + yeq * (yc - yb)
    Ry_up, Ry_lo = yc - ytc, ytc - yb
    Ry = 0.5 * (yc - yb)
    atc = aw + Ra
    def ell(deg):
        t = np.radians(deg)
        ry = Ry_up if np.sin(t) >= 0 else Ry_lo
        return (atc + Ra * np.cos(t), ytc + ry * np.sin(t))
    Pt = {}
    L = []
    def add(name, xy):
        Pt[name] = len(L); L.append(tuple(float(v) for v in xy))
    add("sea0", (aT - Wb - 40.0, 0.0))
    add("sea1", (aT - Wb - 12.0 - fl, 0.0))
    add("sea2", (aT - Wb - 1.0 - fl, 0.0))
    add("foot", (aT - Wb - 0.30 * fl, 0.04 * H))
    add("back1", (aT - 1.02 * Wb, 0.26 * H))
    add("back2", (aT - 0.93 * Wb, 0.55 * H))
    add("back3", (aT - 0.70 * Wb, 0.83 * H))
    add("back4", (aT - 0.36 * Wb, 0.975 * H))
    add("crest", (aT, 1.02 * H))
    add("liptop1", (aT + 0.30 * (an - aT), H - (0.03 + 0.10 * lf) * (H - yn)))
    add("liptop2", (an - 0.32 * (an - aT), yn + (0.18 + 0.06 * lf) * (H - yn)))
    add("lipfront", (an - 0.05, yn + 0.15 + 0.02 * (H - yn)))
    add("nose", (an + 0.30, yn - 0.25 * hk))
    add("hooktip", (an - 0.05, yn - 1.0 * hk))
    add("hookin", (an + 0.05 - 0.6 * tl, yn - 0.55 * hk))
    add("under1", (an - 1.0 - tl, yn + 0.42))
    c105 = ell(100.0)
    add("under2", (0.5 * (an - 1.0 - tl) + 0.5 * c105[0], 0.5 * (yn + 0.42) + 0.5 * c105[1] - p["under_sag"] * Ry))
    add("ceil", ell(118.0))
    # second-crest ledge (lobes A/B/C) on the back wall: collapses onto the ellipse when lobe = 0; it also fades
    # where the tube ceiling comes down to the ridge (no room for the ledge under the lip)
    lob = p.get("lobe", 0.0) * float(np.clip((yc - p.get("y_ridge", yc) - 1.6) / 1.2, 0.0, 1.0))
    yr, ye = p.get("y_ridge", ytc + 0.5 * Ry), p.get("y_edge", ytc + 0.2 * Ry)
    # ellipse angle of the ridge (the wall point sits above it, so the polygon runs ceiling -> wall -> ledge -> down)
    def ang_at(y):
        ry = Ry_up if y >= ytc else Ry_lo
        return 180.0 - np.degrees(np.arcsin(np.clip((y - ytc) / ry, -0.999, 0.999)))
    th_w = np.clip(ang_at(yr + 1.2), 125.0, 170.0) if lob > 0 else 150.0
    th_w = (1 - lob) * 150.0 + lob * th_w
    add("wall", ell(th_w))
    aw_r = ell(ang_at(yr))[0]                       # the wall's a at the ridge height
    ae = aw_r + p.get("lobe_L", 0.0)
    led = [(aw_r + 0.1, yr + 0.35), (aw_r + 0.5 * (ae - aw_r), yr + 0.05), (ae - 0.35, yr - 0.30 * (yr - ye)),
           (ae + 0.25, ye + 0.40 * (yr - ye)), (ae - 0.15, ye - 0.05), (ae - 0.95, ye + 0.35), (aw_r + 0.5, ye - 0.35)]
    th_b = max(ang_at(ye - 0.9), th_w + 8.0)
    for k, q in enumerate(led):
        base = np.array(ell(th_w + (max(th_b, 195.0) - th_w) * (k + 1) / (len(led) + 1)))
        add("ledge%d" % k, (1 - lob) * base + lob * np.array(q))
    add("wall2", ell(max(th_b, 195.0) + 0.5 * (228.0 - max(th_b, 195.0)) * lob if lob > 0 else 195.0))
    add("floor", ell(228.0))
    add("face", ell(255.0))
    add("trough", ell(272.0))
    add("rise", (atc + 0.45 * (afr - atc) , 0.55 * yb))
    add("front", (afr, 0.0))
    add("sea3", (afr + 12.0, 0.0))
    add("sea4", (afr + 40.0, 0.0))
    P = np.array(L, float)
    # tiny rows (the two ends of the crest): the curl fades into a plain rounded bump (no folded micro-curl)
    tiny = max(float(np.clip((2.8 - H) / 1.8, 0.0, 1.0)), p.get("force_tiny", 0.0))
    if tiny > 0:
        names = ["liptop1", "liptop2", "lipfront", "nose", "hooktip", "hookin", "under1", "under2", "ceil", "wall"] +                 ["ledge%d" % k for k in range(7)] + ["wall2", "floor", "face", "trough", "rise"]
        a_end = max(afr, aT + 3.0 * max(H, 0.3) + 2.0)
        for k, nm in enumerate(names):
            t = (k + 1) / (len(names) + 1)
            q = (aT + t * (a_end - aT) * 0.6 + (a_end - aT) * 0.4 * t * t, H * (1 - t) ** 2 * (1 + 2 * t) * 1.0)
            P[Pt[nm]] = (1 - tiny) * P[Pt[nm]] + tiny * np.array(q)
    sh = p.get("shoulder", 0.0)
    if sh > 0:
        # near shoulder (outside the barrel), a TWO-TIER front: the round crest rolls into a small curl (only where the
        # step down to the second crest is large enough), the face below steps onto the second-crest lobe (bulge +
        # pocket), and the lower face slopes forward into a shallow trough (no vertical wall, no long lip)
        S = P.copy()
        step = max(H - yr, 0.5)
        s1 = float(np.clip((step - 1.4) * 1.1, 0.0, 2.6))          # curl reach (0 when the lobe is right under the crest)
        cr = 1.0 + 0.35 * step                                      # horizontal reach of the rounded crest front
        a0 = aT + cr                                                # face line near the crest
        yf = yr + 0.8                                               # face just above the ridge
        af_ = a0 + 0.25 * (H - yf) * 0.45                           # the face leans forward going down (~65 deg)
        S[Pt["liptop1"]] = (aT + 0.45 * cr, H - 0.12)
        S[Pt["liptop2"]] = (aT + 0.85 * cr, H - 0.10 * step - 0.35)
        S[Pt["lipfront"]] = (a0 + 0.45 * s1, H - 0.22 * step - 0.35)
        S[Pt["nose"]] = (a0 + 0.75 * s1 + 0.05, H - 0.30 * step - 0.4)
        S[Pt["hooktip"]] = (a0 + 0.55 * s1, H - 0.40 * step - 0.45)
        S[Pt["hookin"]] = (a0 + 0.25 * s1, H - 0.40 * step - 0.35)
        S[Pt["under1"]] = (a0 + 0.05 * s1, H - 0.46 * step - 0.3)
        S[Pt["under2"]] = (0.5 * (a0 + af_) + 0.1, 0.5 * (H - 0.46 * step - 0.3) + 0.5 * (yf + 0.5))
        S[Pt["ceil"]] = (af_ + 0.05, yf + 0.45)
        S[Pt["wall"]] = (af_, yf)
        ae2 = af_ + p.get("lobe_L", 0.0)
        led_s = [(af_ + 0.25, yr + 0.35), (af_ + 0.55 * (ae2 - af_), yr + 0.05), (ae2 - 0.30, yr - 0.30 * (yr - ye)),
                 (ae2 + 0.20, ye + 0.42 * (yr - ye)), (ae2 - 0.15, ye + 0.02), (ae2 - 0.85, ye + 0.30), (af_ + 0.45, ye - 0.30)]
        lob2 = p.get("lobe", 0.0)
        for k_, q in enumerate(led_s):
            t = (k_ + 1) / (len(led_s) + 1)
            base = np.array((af_ + 1.0 * t, (1 - t) * (yf) + t * (0.62 * ye)))
            S[Pt["ledge%d" % k_]] = (1 - lob2) * base + lob2 * np.array(q)
        # lower face: slopes forward-down from under the pocket into the trough
        S[Pt["wall2"]] = (af_ + 1.0, 0.62 * ye)
        S[Pt["floor"]] = (af_ + 2.8, 0.28 * ye)
        S[Pt["face"]] = (af_ + 4.6, 0.35 * yb)
        S[Pt["trough"]] = (af_ + 7.0, yb)
        S[Pt["rise"]] = (0.5 * (af_ + 7.0) + 0.5 * afr, 0.5 * yb)
        P = (1 - sh) * P + sh * S
    f72 = p.get("face72", 0.0)
    if f72 > 0 and p.get("line") is not None:
        # barrel end (far side): the tube's lower back wall leans forward along the camera-ray plane through the
        # painting's inner-wall outline (72, lower part), closing the tube floor at ~4 m (the barrel closes out here)
        ly, la = p["line"]
        dl = p.get("face72_off", 0.15)
        def aline(y):
            return np.interp(y, ly, la) - dl
        G = P.copy()
        G[Pt["wall2"]] = (aline(8.4), 8.4)
        w0 = np.array(P[Pt["wall"]]); w1 = np.array(G[Pt["wall2"]])
        for k_ in range(7):
            t = (k_ + 1) / 8.0
            G[Pt["ledge%d" % k_]] = (1 - t) * w0 + t * w1 + np.array([-0.35 * np.sin(np.pi * t), 0.0])
        G[Pt["floor"]] = (aline(6.3), 6.3)
        G[Pt["face"]] = (aline(2.6), 2.6)                      # the leaning inner face continues into the trough
        G[Pt["trough"]] = (aline(2.6) + 4.5, yb)
        G[Pt["rise"]] = (0.5 * (aline(2.6) + 4.5) + 0.5 * afr, 0.5 * yb)
        P = (1 - f72) * P + f72 * G
    fm = p.get("farmix", 0.0)
    if fm > 0 and p.get("line") is not None:
        # far end (hidden from the painting camera): a spilling curl whose lower face is a convex curve tangent to the
        # camera-ray plane through the painting's inner-wall outline (72, lower part) at height y_t
        ly, la = p["line"]
        yt = p["y_t"]
        def aface(y):
            return np.interp(y, ly, la) - (0.12 + 0.10 * (y - yt) ** 2)
        F = P.copy()
        F[Pt["under1"]] = (an - 0.5 - 1.2 * tl, yn - 0.2 * hk)
        F[Pt["under2"]] = (an - 1.0 - tl, yn - 0.7 * hk - 0.4)
        F[Pt["ceil"]] = (an - 0.8, yn - 1.3 * hk - 1.0)
        y17 = min(yn - 1.5 * hk - 1.6, yt + 2.2)
        F[Pt["wall"]] = (min(aface(y17), an - 0.6), y17)
        ya = yt + 0.9; yb2 = yt - 0.6
        for k in range(7):
            yy = ya + (yb2 - ya) * (k + 1) / 8.0
            F[Pt["ledge%d" % k]] = (aface(yy), yy)
        F[Pt["wall2"]] = (aface(yt - 0.6), yt - 0.6)
        y20 = max(yt - 2.4, 0.6)
        F[Pt["floor"]] = (aface(0.5 * (yt - 0.6) + 0.5 * y20), 0.5 * (yt - 0.6) + 0.5 * y20)
        F[Pt["face"]] = (aface(y20), y20)
        F[Pt["trough"]] = (F[Pt["face"]][0] + 2.5, yb)
        F[Pt["rise"]] = (0.55 * F[Pt["trough"]][0] + 0.45 * afr, 0.45 * yb)
        P = (1 - fm) * P + fm * F
    return P, Pt


def eval_bspline(Pc, n=4000):
    k = 3
    m = len(Pc)
    t = np.r_[np.zeros(k), np.linspace(0, 1, m - k + 1), np.ones(k)]
    u = np.linspace(0, 1, n)
    sp = BSpline(t, Pc, k)
    # parameter of each control point (Greville abscissae)
    gre = np.array([t[i + 1:i + k + 1].mean() for i in range(m)])
    return u, sp(u), gre


def row_curve(p, n=4000):
    Pc, Pt = control_polygon(p)
    u, Q, gre = eval_bspline(Pc, n)
    # landmark indices on the dense curve
    lm = {}
    for key, nm in CP_LM.items():
        lm[key] = int(np.argmin(np.abs(u - gre[Pt[nm]])))
    # j_top: the true crest (highest point); j_tip: most forward point between crest and corner (above 0.3 H)
    it = int(np.argmax(Q[:lm["j_tip"], 1]))
    lm["j_top"] = it
    seg = np.arange(it, lm["j_corner"])
    hi = seg[Q[seg, 1] > 0.3 * Q[it, 1]]
    if len(hi):
        lm["j_tip"] = int(hi[np.argmax(Q[hi, 0])])
    seg = np.arange(lm["j_tip"] + 5, lm["j_facebot"])
    ok = seg[(Q[seg, 1] > 0.12 * Q[it, 1])]
    if len(ok):
        lm["j_corner"] = int(ok[np.argmin(Q[ok, 0])])
    seg = np.arange(lm["j_corner"], lm["j_E"])
    lm["j_facebot"] = int(seg[np.argmin(Q[seg, 1])])
    # back foot: last point behind the crest that is below 1 % of H
    b = np.nonzero(Q[:it, 1] < 0.01 * Q[it, 1] + 0.01)[0]
    if len(b):
        lm["j_B"] = int(b[-1])
    e = np.nonzero((Q[lm["j_facebot"]:, 1] > -0.01) )[0]
    if len(e):
        lm["j_E"] = max(lm["j_facebot"] + int(e[0]), lm["j_facebot"] + 5)
    return Q, lm


def resample400(Q, lm, a_back=-49.2, a_front=33.0, lmf=None):
    """400 columns: flat sea 0..18 and 394..399, arc-length uniform between landmarks (lmf = smoothed fractional
    landmark positions along the dense curve, to keep the column layout consistent between rows)."""
    s = C.arclen(Q[:, 0], Q[:, 1])
    L = lmf if lmf is not None else {k: s[v] for k, v in lm.items()}
    order = ["j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"]
    A = np.zeros(400); Y = np.zeros(400)
    jB, jE = C.LM["j_B"], C.LM["j_E"]
    sB, sE = L["j_B"], L["j_E"]
    aB = np.interp(sB, s, Q[:, 0]); aE = np.interp(sE, s, Q[:, 0])
    A[:jB + 1] = np.linspace(min(a_back, aB - 5), aB, jB + 1); Y[:jB + 1] = np.interp(sB, s, Q[:, 1]) * np.linspace(0, 1, jB + 1) ** 3
    A[jE:] = np.linspace(aE, max(a_front, aE + 5), 400 - jE); Y[jE:] = np.interp(sE, s, Q[:, 1]) * np.linspace(1, 0, 400 - jE) ** 3
    # graded spacing: inside each landmark segment the column spacing changes linearly from the joint spacing at its
    # start to the joint spacing at its end (joint = geometric mean of the two segments' mean spacings), so there is
    # no spacing jump at a landmark (e.g. coarse back -> fine lip at the crest)
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


PKEYS = ["H", "aT", "Wb", "back_sq", "foot_len", "a_nose", "y_nose", "hook_drop", "lip_t", "lip_full",
         "a_wall", "y_ceil", "y_bot", "tube_Ra", "a_front", "farmix", "y_t", "under_sag", "lobe", "y_ridge", "y_edge", "lobe_L", "shoulder", "sh_front", "face72", "face72_off", "tube_eq"]

_LINES = None


def ray_lines(c):
    """for each row plane c: the line where the camera rays through the painting's inner-wall outline (72, lower
    part, display y 520..735) cut the plane, as (y ascending, a) arrays (extrapolated below 4.1 m along the last segment)."""
    V1, tgt, fr = C.painting_frame()
    cam = fr.cam
    seg = np.array(tgt.seg["72"], float)
    low = seg[(seg[:, 1] >= 500) & (seg[:, 0] < 960)]
    low = low[np.argsort(low[:, 1])]
    D = cam.rays(low)
    out = []
    for c0 in c:
        s_ = (c0 - (cam.pos - C.O) @ C.E) / (D @ C.E)
        X = cam.pos[None, :] + s_[:, None] * D
        S = C.sec(X)
        a, y = S[:, 0], S[:, 1]
        o = np.argsort(y); a, y = a[o], y[o]
        # extrapolate down to y = -3 along the lowest 1 m direction
        k = y < y[0] + 1.0
        g = np.polyfit(y[k], a[k], 1)
        ye = np.linspace(-3.0, y[0] - 0.05, 12)
        out.append((np.r_[ye, y], np.r_[np.polyval(g, ye), a]))
    return out


def row_params(prm, c):
    kt = prm["knots"]
    out = {}
    for k in PKEYS:
        out[k] = knots(kt[k], c)
    # scale-dependent terms for small rows: everything shrinks toward the crest as H -> 0
    return out


def build(prm):
    c = c_rows(prm)
    P = row_params(prm, c)
    nv = len(c)
    lines = ray_lines(c)
    curves, lms = [], []
    for r in range(nv):
        p = {k: float(P[k][r]) for k in PKEYS}
        p["line"] = lines[r] if (p["farmix"] > 0 or p["face72"] > 0) else None
        if p["H"] < 0.05:
            curves.append(None); lms.append(None); continue
        Q, lm = row_curve(p)
        curves.append(Q); lms.append(lm)
    # smoothed fractional landmark arc positions along c (consistent columns between rows)
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
        v = fr[k].copy(); v[~ok] = np.interp(np.nonzero(~ok)[0], np.nonzero(ok)[0], v[ok]) if (~ok).any() else v[~ok]
        fr[k] = gaussian_filter1d(v, sig, mode="nearest")
    A = np.zeros((nv, 400)); Y = np.zeros((nv, 400))
    import candA_warp as Wp
    for r in range(nv):
        if curves[r] is None:
            A[r] = np.linspace(-49.2, 33.0, 400); Y[r] = 0.0; continue
        for ft in (0.0, 0.35, 0.7, 1.0):
            if ft > 0:
                # a small row whose curl folds onto itself: flatten the curl a bit more (recorded as force_tiny)
                p = {k: float(P[k][r]) for k in PKEYS}
                p["line"] = lines[r] if (p["farmix"] > 0 or p["face72"] > 0) else None
                p["force_tiny"] = ft
                curves[r], _ = row_curve(p)
            Q = curves[r]; s = C.arclen(Q[:, 0], Q[:, 1])
            L = {k: fr[k][r] * s[-1] for k in C.LM}
            order = ["j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"]
            for a_, b_ in zip(order[:-1], order[1:]):
                L[b_] = max(L[b_], L[a_] + 0.05)
            A[r], Y[r] = resample400(Q, None, lmf=L)
            if Wp.section_crossings(np.stack([A[r], Y[r]], -1)) == 0 or P["H"][r] > 6.0:
                break
    return c, A, Y, P


def main(prm_path, out):
    prm = json.load(open(prm_path, encoding="utf-8"))
    c, A, Y, P = build(prm)
    np.savez_compressed(out, A=A, Y=Y, c=c, **{"p_" + k: v for k, v in P.items()})
    print("ok", out, "H0", Y[159].max(), "Hmax", Y.max(), "at c", c[np.argmax(Y.max(1))])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
