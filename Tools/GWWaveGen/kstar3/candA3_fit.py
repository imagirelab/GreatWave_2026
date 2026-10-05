# -*- coding: utf-8 -*-
"""Q20 loop 3, candidate A3, step 2: fit our 400 x 240 sheet to the SMOOTHED large form of the reference model.

Input: the temporary smoothed volume (candA3_vol.Vol; built outside the repo by _model_side/candA3_refsmooth.py) and a
design parameter json.  Rows are the constant-c planes of the loop-2 K*' grid (same 240 c values, row 159 = c 0).

Per row (c inside the model's body range):
  1. the 0.5 level set of the plane (the sea / base below floor_y filled) -> the main contour from the back sea over the
     wave to the front sea (the tube cavity is open to the front, so the contour runs into the barrel and out again);
  2. landmarks on it: back foot (last up-crossing of y = 0 before the crest), top (highest point), lip tip (most
     forward point above 0.3 H in front of the crest), RIM (first point after the top where the heading has turned
     180 deg, i.e. the curl's lower edge running back into the tube), tube corner (back-most point of the tube wall,
     0.15..0.8 H), and the design's own trough / front foot;
  3. SECONDARY DESIGN on the curve (numbers in the params, all recorded):
       * back: arc-length smoothing much stronger than the model (sigma_back), then a concave open-sea foot (cubic
         Hermite from the flat sea into the back tangent at foot_join*H) -> one curvature sign change (D1, D2);
       * front: the model's inner wall is kept down to wall_cut*H, then our own trough (depth trough_D*H, bottom
         trough_ahead*R_tube in front of the tube corner, rise to the sea over trough_rise*H) -> no plinth (D2, F08);
       * lip: optional thinning of the curl near the tip toward the medial line (lip_thin) (F06);
  4. far rows beyond the body (the model's curl is a detached island there): the island's outline + a thin stem
     (the continued back shell, thickness stem_t) down to the sea, so the far end closes as a thin curl (D5);
  5. per-row resampling to 400 columns with the landmark columns (j_B 18, j_top 90, j_tip 200, j_rim 232 (internal),
     j_corner 314, j_facebot 379, j_E 394), landmark arc fractions smoothed along the crest;
  6. rows outside [c_lo, c_hi] (near shoulder / far sea) come from the loop-2 K*' rows (painting-locked), blended over
     blend_w metres with the fitted rows (both grids share the landmark meanings column by column).
usage: py -3.10 candA3_fit.py vol.npz params.json out_rows.npz
"""
import sys, os, json, math
import numpy as np
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3_vol as CV

KF_ROWS = os.path.join(C.REPO, "Unity", "Build", "Q20", "final", "kstarF_a45_rows.npz")
LM3 = {"j_B": 18, "j_top": 90, "j_tip": 200, "j_rim": 232, "j_corner": 314, "j_facebot": 379, "j_E": 394}
ORDER = ["j_B", "j_top", "j_tip", "j_rim", "j_corner", "j_facebot", "j_E"]


def tab(prm, key, c):
    k = np.array(prm[key], float)
    if k.ndim == 0:
        return np.full_like(np.atleast_1d(c), float(k), dtype=float)
    return np.interp(c, k[:, 0], k[:, 1])


# ------------------------------------------------------------------ curve helpers
def resample(P, step):
    s = C.arclen(P[:, 0], P[:, 1])
    n = max(int(round(s[-1] / step)) + 1, 2)
    ss = np.linspace(0, s[-1], n)
    return np.stack([np.interp(ss, s, P[:, 0]), np.interp(ss, s, P[:, 1])], -1)


def heading(P):
    d = np.gradient(P, axis=0)
    return np.degrees(np.unwrap(np.arctan2(d[:, 1], d[:, 0])))


def smooth_var(P, sig_pts):
    """arc-length Gaussian smoothing with a per-point sigma (in samples), ends fixed."""
    n = len(P)
    out = P.copy()
    idx = np.arange(n)
    for i in range(1, n - 1):
        s = sig_pts[i]
        if s < 0.3:
            continue
        w = int(min(3 * s, i, n - 1 - i))
        if w < 1:
            continue
        j = idx[i - w:i + w + 1]
        g = np.exp(-0.5 * ((j - i) / s) ** 2)
        out[i] = (g[:, None] * P[j]).sum(0) / g.sum()
    return out


def hermite(p0, t0, p1, t1, n=40):
    """cubic Hermite from p0 (tangent t0) to p1 (tangent t1); tangent lengths scaled by the chord."""
    L = np.linalg.norm(p1 - p0)
    t0 = t0 / max(np.linalg.norm(t0), 1e-9) * L; t1 = t1 / max(np.linalg.norm(t1), 1e-9) * L
    s = np.linspace(0, 1, n)[:, None]
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1; h10 = s ** 3 - 2 * s ** 2 + s; h01 = -2 * s ** 3 + 3 * s ** 2; h11 = s ** 3 - s ** 2
    return h00 * p0 + h10 * t0 + h01 * p1 + h11 * t1


def main_contour(cons, vol, floor):
    """the open contour from the left border to the right border (through the filled floor), oriented left -> right."""
    best = None
    amin = vol.a0 + vol.res * 1.5; amax = vol.a0 + vol.res * (vol.na - 2.5)
    for q in cons:
        if len(q) < 10:
            continue
        ends = (q[0, 0] <= amin or q[-1, 0] <= amin) and (q[0, 0] >= amax or q[-1, 0] >= amax)
        if ends and (best is None or len(q) > len(best)):
            best = q
    if best is None:
        return None
    if best[0, 0] > best[-1, 0]:
        best = best[::-1]
    return best


def islands(cons, main, min_area=1.0):
    out = []
    for q in cons:
        if q is main or len(q) < 10:
            continue
        if np.linalg.norm(q[0] - q[-1]) > 1e-6:
            continue
        area = 0.5 * abs(np.sum(q[:-1, 0] * q[1:, 1] - q[1:, 0] * q[:-1, 1]))
        if area >= min_area and q[:, 1].max() > 2.0:
            out.append(q)
    return out


def orient_cw(q):
    """closed contour oriented clockwise in (a, y) (a right, y up): over the top from back (-a) to front (+a)."""
    area2 = np.sum(q[:-1, 0] * q[1:, 1] - q[1:, 0] * q[:-1, 1])
    return q if area2 < 0 else q[::-1]


# ------------------------------------------------------------------ one row
def landmarks_on(P, H):
    a, y = P[:, 0], P[:, 1]
    iT = int(np.argmax(y))
    up = np.nonzero((y[:iT] < 0.0) & (y[1:iT + 1] >= 0.0))[0]
    iB = int(up[-1] + 1) if len(up) else 0
    fr = np.arange(iT, len(a)); hi = fr[y[fr] > 0.3 * H]
    iP = int(hi[np.argmax(a[hi])]) if len(hi) else iT
    hd = heading(P)
    aft = np.arange(iP, len(a))
    tw = aft[(y[aft] > 0.15 * H) & (y[aft] < 0.8 * H)]
    iK = int(tw[np.argmin(a[tw])]) if len(tw) else min(iP + 5, len(a) - 1)
    turned = np.nonzero(hd[iT:iK + 1] <= hd[iT] - 180.0)[0]
    iR = int(iT + turned[0]) if len(turned) else int(iP + np.argmin(hd[iP:iK + 1]))
    iR = min(max(iR, iP + 1), iK - 1)
    return dict(B=iB, T=iT, P=iP, R=iR, K=iK)



def rot(v, ang_deg):
    t = np.radians(ang_deg); c_, s_ = np.cos(t), np.sin(t)
    return np.stack([c_ * v[..., 0] - s_ * v[..., 1], s_ * v[..., 0] + c_ * v[..., 1]], -1)


def painting_lip_target(c0, H, a_top, y_lo_f=0.5, margin=0.4):
    """most forward point of the painted big-wave region (PaintingCam v1, raw sky sdf < 0) on the plane c0 inside the
    lip band (y > y_lo_f * H, a > a_top), connected to the crest; the lip may reach it without touching the sky."""
    import fin_allowed as FA
    global _PT
    try:
        _PT
    except NameError:
        _PT = C.painting_frame()
    V1, tgt, fr = _PT
    aa, yy, ok, s = FA.allowed_grid(fr, tgt, c0, a_rng=(a_top - 2.0, a_top + 16.0), y_rng=(y_lo_f * H, H + 2.0), res=0.1)
    from scipy.ndimage import label
    lab, n = label(ok)
    i0 = int(np.argmin(np.abs(aa - a_top))); j0 = int(np.argmin(np.abs(yy - (H - 0.5))))
    k = lab[j0, i0]
    if k == 0:
        return None
    m = lab == k
    cols = np.nonzero(m.any(0))[0]
    amax = aa[cols.max()]
    jj = np.nonzero(m[:, cols.max()])[0]
    return float(amax - margin), float(yy[jj].mean())


_PLANES = {}


def painting_plane(c0, a_rng=(-30.0, 25.0), y_rng=(-4.0, 26.0), res=0.1):
    """allowed mask of the plane c0: True where surface does not touch the painting's sky (PaintingCam v1, raw sdf)."""
    key = round(float(c0), 4)
    if key not in _PLANES:
        import fin_allowed as FA
        global _PT
        try:
            _PT
        except NameError:
            _PT = C.painting_frame()
        V1, tgt, fr = _PT
        # like fin_allowed.allowed_grid, but with the half-width compensated sky (the gate's envelope)
        aa = np.arange(a_rng[0], a_rng[1] + 1e-9, res); yy = np.arange(y_rng[0], y_rng[1] + 1e-9, res)
        Ag, Yg = np.meshgrid(aa, yy)
        X = C.world(np.full(Ag.shape[0], c0), Ag, Yg).reshape(-1, 3)
        P = fr.cam.project(X)
        sd = tgt.sample(P[:, :2], comp=True)
        ok = (sd < 0) | (P[:, 1] > FA.HORIZON) | (P[:, 0] < tgt.x0) | (P[:, 0] > tgt.x1) | (P[:, 2] <= 0.5)
        _PLANES[key] = (aa, yy, ok.reshape(Ag.shape))
    return _PLANES[key]


def top_run(plane, a, y_max):
    """(lo, hi) of the topmost allowed vertical run at column a that starts below y_max."""
    aa, yy, ok = plane
    i = int(np.clip(np.round((a - aa[0]) / (aa[1] - aa[0])), 0, len(aa) - 1))
    col = ok[:, i] & (yy <= y_max)
    if not col.any():
        return None
    j1 = int(np.nonzero(col)[0].max()); j0 = j1
    while j0 > 0 and col[j0 - 1]:
        j0 -= 1
    return float(yy[j0]), float(yy[j1])


def lip_curl(core, jT, jP, H, prm, c, ext_override=None, target=None):
    """SECONDARY DESIGN of the lip: the model's (smoothed, claw-free) lip is a blunt stub.  Its medial axis (pairs of
    upper / lower surface points by relative arc length from the root to the nose) is re-embedded as a longer curl:
    length + lip_ext, heading turning by lip_turn (deg, clockwise) with the turn growing toward the tip (power
    lip_pow), half-thickness tapering from the root to lip_tip_t (the thin edge).  Returns the new core or None."""
    ext = float(tab(prm, "lip_ext", c)) if ext_override is None else ext_override
    turn = float(tab(prm, "lip_turn", c))
    if ext <= 0.02 and turn <= 0.5:
        return None, {}
    a, y = core[:, 0], core[:, 1]
    aT, aP = a[jT], a[jP]
    f_root = float(tab(prm, "lip_root_f", c))
    up = np.arange(jT, jP + 1)
    ju0 = int(up[np.argmax(a[up] >= aT + f_root * (aP - aT))]) if (a[up] >= aT + f_root * (aP - aT)).any() else jT
    aft = np.arange(jP + 1, len(core))
    back = aft[(a[aft] <= a[ju0]) & (y[aft] > 0.35 * H)]
    if len(back) == 0 or jP - ju0 < 6:
        return None, {}
    jl0 = int(back[0])
    U = core[ju0:jP + 1]; Lo = core[jP:jl0 + 1][::-1]
    N = 160
    def at(P, u):
        s = C.arclen(P[:, 0], P[:, 1]); s = s / max(s[-1], 1e-9)
        return np.stack([np.interp(u, s, P[:, 0]), np.interp(u, s, P[:, 1])], -1)
    u = np.linspace(0, 1, N)
    Uu, Lu = at(U, u), at(Lo, u)
    m = 0.5 * (Uu + Lu); hv = 0.5 * (Uu - Lu)
    t0 = float(np.linalg.norm(hv[0]))
    dm = np.gradient(m, axis=0)
    phi = np.degrees(np.unwrap(np.arctan2(dm[:, 1], dm[:, 0])))
    Lm = float(C.arclen(m[:, 0], m[:, 1])[-1])
    phi0 = float(np.mean(phi[:6]))
    if target is None:
        # clothoid-like curl of length Lm + ext turning by lip_turn (no painting target)
        L2 = Lm + ext
        pw = float(tab(prm, "lip_pow", c))
        phi_new = phi0 - turn * u ** pw
        d = np.stack([np.cos(np.radians(phi_new)), np.sin(np.radians(phi_new))], -1)
        m2 = m[0] + np.r_[np.zeros((1, 2)), np.cumsum(0.5 * (d[1:] + d[:-1]) * (L2 / (N - 1)), 0)]
    else:
        # the curl: a Bezier from the root (root heading) to the top of a round hook, then a circular arc of radius
        # lip_hook_R turning clockwise from lip_hook_start to lip_hook_end deg; the hook's most forward point is the
        # painting target (the front of the painted lip head on this plane), capped at root + lip_ext_max
        Tt = np.asarray(target["tip"], float)
        plane = target["plane"]
        Rmax = float(tab(prm, "lip_hook_R", c)); mv = float(tab(prm, "lip_band_margin", c))
        ph_s, ph_e = float(tab(prm, "lip_hook_start", c)), float(tab(prm, "lip_hook_end", c))
        a_max = m[0][0] + float(tab(prm, "lip_ext_max", c)) + Lm
        Fa = min(Tt[0], a_max)
        tt_hook = 0.5 * float(tab(prm, "lip_hook_thick", c))
        Rh, Fy = None, None
        if target.get("fixed") is not None:
            Fa, Fy, Rh = target["fixed"]
        for R_ in (np.arange(Rmax, 0.79, -0.1) if Rh is None else []):
            Fa_ = max(Fa, m[0][0] + R_ + 1.0)
            band = top_run(plane, Fa_ - R_, H + 1.5)
            band_f = top_run(plane, Fa_ - 0.15, H + 1.5)
            if band is None or band_f is None:
                continue
            lo, hi = band
            hi = min(hi, float(target["y_crest"]) - float(tab(prm, "lip_below_crest", c)))
            if hi - lo >= 2 * (R_ + tt_hook + mv):
                Rh = R_; Fy = hi - mv - tt_hook - R_; Fa = Fa_
                break
        if Rh is None:
            Rh = 0.8; Fa = max(Fa, m[0][0] + Rh + 1.0)
            band = top_run(plane, Fa - Rh, H + 1.5)
            Fy = 0.5 * (band[0] + band[1]) if band else Tt[1]
        cen = np.array([Fa - Rh, Fy])
        def arcp(ph):
            ph = np.radians(ph); return cen + Rh * np.stack([-np.sin(ph), np.cos(ph)], -1)
        S = arcp(ph_s)
        d0 = np.array([np.cos(np.radians(phi0)), np.sin(np.radians(phi0))]); ds = np.array([np.cos(np.radians(ph_s)), np.sin(np.radians(ph_s))])
        Lc = float(np.linalg.norm(S - m[0]))
        k0, k1 = float(tab(prm, "lip_k0", c)), float(tab(prm, "lip_k1", c))
        tb = np.linspace(0, 1, 300)[:, None]
        P0, P1, P2, P3 = m[0], m[0] + k0 * Lc * d0, S - k1 * Lc * ds, S
        Bz = (1 - tb) ** 3 * P0 + 3 * (1 - tb) ** 2 * tb * P1 + 3 * (1 - tb) * tb ** 2 * P2 + tb ** 3 * P3
        Ar = arcp(np.linspace(ph_s, ph_e, 200))
        B = np.vstack([Bz, Ar[1:]])
        m2 = at(B, u)
        L2 = float(C.arclen(m2[:, 0], m2[:, 1])[-1])
        dm2 = np.gradient(m2, axis=0)
        phi_new = np.degrees(np.unwrap(np.arctan2(dm2[:, 1], dm2[:, 0])))
        phi_new = phi_new - (phi_new[0] - phi0)
        d = np.stack([np.cos(np.radians(phi_new)), np.sin(np.radians(phi_new))], -1)
    t_tip = float(tab(prm, "lip_tip_t", c)); q = float(tab(prm, "lip_thin_pow", c))
    tt = t_tip + (t0 - t_tip) * (1 - u) ** q
    ang = np.radians(phi_new - phi0)
    hv0 = hv[0] / max(t0, 1e-9)
    hv2 = np.stack([np.cos(ang) * hv0[0] - np.sin(ang) * hv0[1], np.sin(ang) * hv0[0] + np.cos(ang) * hv0[1]], -1) * tt[:, None]
    U2 = m2 + hv2; L2p = m2 - hv2
    # tip cap: half turn around m2[-1], clockwise from the upper to the lower surface through the forward direction
    r_ = hv2[-1]; th = np.linspace(0, -180, 25)[1:-1]
    cap = m2[-1] + np.stack([np.cos(np.radians(th)) * r_[0] - np.sin(np.radians(th)) * r_[1],
                             np.sin(np.radians(th)) * r_[0] + np.cos(np.radians(th)) * r_[1]], -1)
    # check that the cap goes through the forward side (else mirror the turn)
    if (cap[len(cap) // 2] - m2[-1]) @ d[-1] < 0:
        th = -th
        cap = m2[-1] + np.stack([np.cos(np.radians(th)) * r_[0] - np.sin(np.radians(th)) * r_[1],
                                 np.sin(np.radians(th)) * r_[0] + np.cos(np.radians(th)) * r_[1]], -1)
    new = np.vstack([core[:ju0], U2, cap, L2p[::-1], core[jl0 + 1:]])
    new = resample(new, 0.05)
    # soften the two joints
    k0 = int(np.argmin(np.linalg.norm(new - core[ju0], axis=1))); k1 = int(np.argmin(np.linalg.norm(new - core[jl0], axis=1)))
    sg = np.zeros(len(new))
    for k in (k0, k1):
        sg += 6.0 * np.exp(-0.5 * ((np.arange(len(new)) - k) / 12.0) ** 2)
    new = smooth_var(new, sg)
    info = dict(lip_root_a=float(core[ju0, 0]), lip_len_old=Lm, lip_len_new=L2, lip_root_half_t=t0, lip_tip=m2[-1].tolist(),
                hook_R=float(Rh) if target is not None else None,
                hook=[float(Fa), float(Fy), float(Rh)] if target is not None else None)
    return new, info

def design_row(P, prm, c, log=None, hook_fixed=None):
    """P: dense (a, y) contour from the back (below the sea) over the wave, through the tube and out to the front.
    Returns the designed curve Q (back flat sea -> front flat sea) and landmark indices on Q."""
    P = resample(P, 0.05)
    H = float(P[:, 1].max())
    lm = landmarks_on(P, H)
    iB, iT, iP, iR, iK = lm["B"], lm["T"], lm["P"], lm["R"], lm["K"]
    # ---- inner wall kept down to wall_cut * H (after the tube corner)
    wall_cut = float(tab(prm, "wall_cut", c))
    aft = np.arange(iK, len(P))
    low = aft[P[aft, 1] <= wall_cut * H]
    iW = int(low[0]) if len(low) else len(P) - 1
    core = P[iB:iW + 1].copy()
    tcw = float(tab(prm, "top_close_w", c)) if "top_close_w" in prm else 0.0
    if tcw > 0.05:
        from scipy.ndimage import grey_closing
        jT0 = iT - iB; jP0 = iP - iB
        seg = np.arange(0, jP0 + 1)
        up = seg[core[seg, 1] > 0.55 * H]
        if len(up) > 10:
            a_ = core[up, 0]; y_ = core[up, 1]
            bins = np.arange(a_.min() - 0.5, a_.max() + 0.5, 0.05)
            env = np.full(len(bins), -1e9)
            ib = np.clip(np.round((a_ - bins[0]) / 0.05).astype(int), 0, len(bins) - 1)
            np.maximum.at(env, ib, y_)
            okb = env > -1e8
            env = np.interp(bins, bins[okb], env[okb])
            envc = grey_closing(env, size=max(int(tcw / 0.05), 3))
            ynew = np.maximum(y_, np.interp(a_, bins, envc))
            core[up, 1] = ynew
    # ---- back smoothing (strong low on the back, fading to sig_top at the crest and 0 after the tip)
    n = len(core); jT = iT - iB; jP = iP - iB
    sb = float(tab(prm, "sigma_back", c)) / 0.05; st = float(tab(prm, "sigma_top", c)) / 0.05
    sl = float(tab(prm, "sigma_lip", c)) / 0.05; sw = float(tab(prm, "sigma_tube", c)) / 0.05
    sig = np.empty(n)
    ramp = np.clip(np.arange(n) / max(jT, 1), 0, 1)
    sig[:jT + 1] = sb + (st - sb) * ramp[:jT + 1] ** 2
    k2 = np.arange(jT + 1, n)
    sig[jT + 1:] = np.where(k2 <= jP, st + (sl - st) * (k2 - jT) / max(jP - jT, 1), sw)
    if lm["R"] - iB < n:
        rr = lm["R"] - iB
        sig[jP:rr + 1] = sl
    core = smooth_var(core, sig)
    # ---- back rounding (D1): blend the back (back_round_from * H .. crest top) toward a round Bezier quarter
    lam = float(tab(prm, "back_round", c)) if "back_round" in prm else 0.0
    if lam > 0.01:
        jT = int(np.argmax(core[:, 1]))
        jj0 = np.nonzero(core[:jT, 1] >= float(tab(prm, "back_round_from", c)) * H)[0]
        if len(jj0) and jT - jj0[0] > 20:
            j0b = int(jj0[0])
            p0 = core[j0b]; t0 = core[min(j0b + 5, n - 1)] - core[max(j0b - 5, 0)]; t0 /= np.linalg.norm(t0)
            p3 = core[jT]; t3 = np.array([1.0, 0.0])
            ch = float(np.linalg.norm(p3 - p0)); kk = float(tab(prm, "back_round_k", c)) * ch
            tb = np.linspace(0, 1, 400)[:, None]
            Bz = (1 - tb) ** 3 * p0 + 3 * (1 - tb) ** 2 * tb * (p0 + kk * t0) + 3 * (1 - tb) * tb ** 2 * (p3 - kk * t3) + tb ** 3 * p3
            seg = core[j0b:jT + 1]
            sb_ = C.arclen(seg[:, 0], seg[:, 1]); sb_ /= sb_[-1]
            sz = C.arclen(Bz[:, 0], Bz[:, 1]); sz /= sz[-1]
            Bm = np.stack([np.interp(sb_, sz, Bz[:, 0]), np.interp(sb_, sz, Bz[:, 1])], -1)
            wl = lam * np.sin(np.pi * np.clip(sb_, 0, 1)) ** 0.5            # 0 at both ends (tangent-continuous joins)
            core[j0b:jT + 1] = (1 - wl[:, None]) * seg + wl[:, None] * Bm
    lipinfo = {}
    if "lip_ext" in prm:
        ext_o = None; tgt_pt = None
        if prm.get("lip_to_painting"):
            tg = painting_lip_target(c, H, float(core[jT, 0]), y_lo_f=float(tab(prm, "lip_target_ylo", c)), margin=float(tab(prm, "lip_target_margin", c)))
            if tg is not None:
                tgt_pt = {"tip": (tg[0], tg[1]), "plane": painting_plane(c), "y_crest": float(core[:, 1].max()), "fixed": hook_fixed}
        nc_, li = lip_curl(core, jT, jP, H, prm, c, ext_override=ext_o, target=tgt_pt)
        if nc_ is not None:
            core = nc_; lipinfo = li
            n = len(core)
            jT = int(np.argmax(core[:, 1]))
    # ---- open-sea back foot: flat sea -> Hermite into the back tangent at foot_join * H
    fj = float(tab(prm, "foot_join", c)) * H
    jj = np.nonzero(core[:jT, 1] >= fj)[0]
    j0 = int(jj[0]) if len(jj) else 0
    pj = core[j0]; tj = core[min(j0 + 4, n - 1)] - core[max(j0 - 4, 0)]
    Lf = float(tab(prm, "foot_len", c)) * H
    p0 = np.array([pj[0] - Lf, 0.0])
    foot = hermite(p0, np.array([1.0, 0.0]), pj, tj, 60)
    back_sea = np.stack([np.linspace(p0[0] - 60.0, p0[0], 120)[:-1], np.zeros(119)], -1)
    # ---- front: our trough (from the kept wall point down to -D, then up to the sea)
    pw = core[-1]; tw_ = core[-1] - core[-6]
    D = float(tab(prm, "trough_D", c)) * H
    a_corner = P[iK, 0]
    R_t = max(P[iP, 0] - a_corner, 2.0)
    a_fb = max(a_corner + float(tab(prm, "trough_ahead", c)) * R_t, pw[0] + float(tab(prm, "trough_min_run", c)) * max(D, 0.5))
    pfb = np.array([a_fb, -D])
    seg1 = hermite(pw, tw_, pfb, np.array([1.0, 0.0]), 60)
    Lr = float(tab(prm, "trough_rise", c)) * H
    pe = np.array([a_fb + Lr, 0.0])
    seg2 = hermite(pfb, np.array([1.0, 0.0]), pe, np.array([1.0, 0.0]), 60)
    front_sea = np.stack([np.linspace(pe[0], pe[0] + 60.0, 120)[1:], np.zeros(119)], -1)
    Q = np.vstack([back_sea, foot, core[j0 + 1:], seg1[1:], seg2[1:], front_sea])
    Q = resample(Q, 0.05)
    # landmark indices on Q (nearest points)
    def near(p):
        return int(np.argmin(np.linalg.norm(Q - p, axis=1)))
    iTq = near(core[jT]); iEq = near(pe); iFq = near(pfb); iBq = near(p0 + np.array([0.02, 0.0]))
    Hq = float(Q[:, 1].max())
    frq = np.arange(iTq, iFq); hiq = frq[Q[frq, 1] > 0.3 * Hq]
    iPq = int(hiq[np.argmax(Q[hiq, 0])])
    hdq = heading(Q)
    iKq = near(P[iK])
    if iKq <= iPq + 2:
        seg = np.arange(iPq, iFq); tw2 = seg[(Q[seg, 1] > 0.15 * Hq) & (Q[seg, 1] < 0.8 * Hq)]
        iKq = int(tw2[np.argmin(Q[tw2, 0])])
    turned = np.nonzero(hdq[iTq:iKq + 1] <= hdq[iTq] - 180.0)[0]
    iRq = int(iTq + turned[0]) if len(turned) else int(iPq + np.argmin(hdq[iPq:iKq + 1]))
    iRq = min(max(iRq, iPq + 2), iKq - 2)
    L = {"j_B": iBq, "j_top": iTq, "j_tip": iPq, "j_rim": iRq, "j_corner": iKq, "j_facebot": iFq, "j_E": iEq}
    info = dict(H=Hq, a_top=float(Q[iTq, 0]), a_tip=float(Q[iPq, 0]), y_tip=float(Q[iPq, 1]),
                a_corner=float(Q[iKq, 0]), D=D, a_fb=a_fb, wall_cut_y=float(pw[1]), **lipinfo)
    return Q, L, info


def far_row(isl, prm, c, prev):
    """a far row: the model's detached curl (island) + a thin stem (the continued back shell) to the sea."""
    q = orient_cw(isl)
    q = resample(q[:-1] if np.allclose(q[0], q[-1]) else q, 0.05)
    H = float(q[:, 1].max())
    t = float(tab(prm, "stem_t", c))
    # stem foot: below the island's back-bottom, leaning like the previous row's back
    ib = int(np.argmin(q[:, 1] + 0.35 * q[:, 0]))         # lowest-back point of the island
    pb = q[ib]
    lean = prev.get("lean", 0.25) if prev else 0.25
    s0 = np.array([pb[0] - lean * pb[1], 0.0])            # outer stem foot
    # inner point: the island point nearest to pb + t (along +a)
    target = pb + np.array([t, 0.0])
    cand = np.arange(len(q))
    ii = int(cand[np.argmin(np.linalg.norm(q - target, axis=1))])
    # walk: outer stem (s0 -> pb), island clockwise from ib to ii (over the top, around the tip, underside), inner stem
    if ii > ib:
        path = np.vstack([q[ib:], q[:ii + 1]])
    else:
        path = np.vstack([q[ib:], q[:ii + 1]]) if ii < ib else q[ib:ii + 1]
    s1 = np.array([q[ii][0] - lean * q[ii][1], 0.0])
    outer = hermite(s0, np.array([lean, 1.0]), pb, q[min(ib + 3, len(q) - 1)] - q[max(ib - 3, 0)], 40)
    inner = hermite(q[ii], q[min(ii + 3, len(q) - 1)] - q[max(ii - 3, 0)], s1, np.array([-lean, -1.0]), 40)
    core = np.vstack([outer, path[1:], inner[1:]])
    return core, H


def build(vol, prm, log=print):
    z = np.load(KF_ROWS)
    c = z["c"].astype(float); AF, YF = z["A"].astype(float), z["Y"].astype(float)
    nv = len(c)
    da, dc = float(prm.get("da", 0.0)), float(prm.get("dc", 0.0))
    floor = float(prm.get("floor_y", -3.0))
    c_lo, c_hi = float(prm["c_lo"]), float(prm["c_hi"])
    curves = [None] * nv; lms = [None] * nv; infos = [None] * nv; mcache = {}
    for r in range(nv):
        if not (c_lo - float(prm.get("blend_w", 3.0)) - 0.3 <= c[r] <= c_hi + 0.5):
            continue
        sc = float(prm.get("model_scale", 1.0))
        cons, _ = vol.contours((c[r] - dc) / sc, floor_y=floor / sc)
        M = main_contour(cons, vol, floor)
        if M is None:
            continue
        M = M.copy() * sc; M[:, 0] += da
        if M[:, 1].max() < 3.0:
            continue
        try:
            Q, L, info = design_row(M, prm, c[r])
        except Exception as e:  # noqa
            log("row %d c %.2f design failed: %s" % (r, c[r], e)); continue
        # the main contour must hold the curl (the model's body); otherwise the row is a far row (island)
        isl = islands(cons, M)
        info["islands"] = len(isl)
        curves[r] = Q; lms[r] = L; infos[r] = info; mcache[r] = M
    got = [r for r in range(nv) if curves[r] is not None]
    log("fitted rows %d  c %.2f .. %.2f" % (len(got), c[got[0]], c[got[-1]]))
    # pass 2: the painting-driven hook (front a, centre y, radius) smoothed along the crest, rows redesigned with it
    hk = [r for r in got if infos[r].get("hook")]
    if hk and float(prm.get("hook_smooth_c", 0.0)) > 0:
        Hk = np.array([infos[r]["hook"] for r in hk]); ch = c[hk]
        sg = float(prm["hook_smooth_c"])
        Wm = np.exp(-0.5 * ((ch[:, None] - ch[None, :]) / sg) ** 2); Wm /= Wm.sum(1, keepdims=True)
        Hs = Wm @ Hk
        for k, r in enumerate(hk):
            M = mcache[r]
            try:
                Q, L, info = design_row(M, prm, c[r], hook_fixed=tuple(Hs[k]))
                curves[r] = Q; lms[r] = L; infos[r] = info
            except Exception as e:  # noqa
                log("row %d pass 2 failed: %s" % (r, e))
    # landmark arc fractions, smoothed along the crest
    fr = {k: np.full(nv, np.nan) for k in ORDER}
    for r in got:
        s = C.arclen(curves[r][:, 0], curves[r][:, 1])
        for k in ORDER:
            fr[k][r] = s[lms[r][k]]
    A = AF.copy(); Y = YF.copy()
    A_fit = np.full_like(AF, np.nan); Y_fit = np.full_like(YF, np.nan)
    sig = float(prm.get("landmark_smooth_rows", 2.0))
    okr = np.array(got)
    for k in ORDER:
        v = fr[k][okr]
        fr[k][okr] = gaussian_filter1d(v, sig, mode="nearest")
    for r in got:
        Q = curves[r]
        Ls = {k: fr[k][r] for k in ORDER}
        for a_, b_ in zip(ORDER[:-1], ORDER[1:]):
            Ls[b_] = max(Ls[b_], Ls[a_] + 0.05)
        A_fit[r], Y_fit[r] = resample400(Q, Ls)
    # blend with the loop-2 rows outside [c_lo, c_hi]; beyond c_hi the last fitted row at c <= c_hi is the template
    bw = float(prm.get("blend_w", 3.0)); bwf = max(float(prm.get("blend_w_far", 0.5)), 1e-3)
    w = C.smoothstep((c - (c_lo - bw)) / bw) * C.smoothstep(((c_hi + bwf) - c) / bwf)
    tpl = max([r for r in got if c[r] <= c_hi])
    for r in range(nv):
        if c[r] > c[tpl] and w[r] > 0:
            A_fit[r], Y_fit[r] = A_fit[tpl], Y_fit[tpl]
    has = np.isfinite(A_fit[:, 0])
    w = np.where(has, w, 0.0)
    A = w[:, None] * np.nan_to_num(A_fit) + (1 - w[:, None]) * AF
    Y = w[:, None] * np.nan_to_num(Y_fit) + (1 - w[:, None]) * YF
    far = {}
    if prm.get("far_design"):
        # far template: the model's own section at the template row with a modest curl (no painting lip: the far
        # rows are hidden behind the painted lip head, and the long painted lip would hang in the window)
        pf = dict(prm); pf["lip_to_painting"] = False
        for k in ("lip_ext", "lip_turn", "lip_pow"):
            if "far_" + k in prm:
                pf[k] = prm["far_" + k]
        sc = float(prm.get("model_scale", 1.0))
        cons, _ = vol.contours((c[tpl] - dc) / sc, floor_y=floor / sc)
        M = main_contour(cons, vol, floor) * sc; M[:, 0] += da
        Qf, Lf, _ = design_row(M, pf, c[tpl])
        sf = C.arclen(Qf[:, 0], Qf[:, 1])
        Ls = {k: sf[Lf[k]] for k in ORDER}
        for a_, b_ in zip(ORDER[:-1], ORDER[1:]):
            Ls[b_] = max(Ls[b_], Ls[a_] + 0.05)
        Aft, Yft = resample400(Qf, Ls)
        if not prm.get("far_template", True):
            Aft, Yft = None, None
        A, Y, far = far_rows(c, A, Y, AF, YF, A_fit[tpl], Y_fit[tpl], c[tpl], prm, log, At2=Aft, Yt2=Yft)
        w = np.where(c > c[tpl], 1.0, w)
    dr = prm.get("design_relax_sigma_c")
    if dr:
        import fin2_relax as RX
        sgc = np.interp(c, [t[0] for t in dr], [t[1] for t in dr])
        ww = np.clip((np.abs(Y) - 0.02) / 0.3, 0.0, 1.0)
        ww = np.maximum(ww, np.roll(ww, 1, 1)); ww = np.maximum(ww, np.roll(ww, -1, 1))
        for _ in range(int(prm.get("design_relax_iters", 1))):
            A, Y = RX.cross_rows(A, Y, c, sgc, weight=ww)
    return c, A, Y, dict(weight=w, A_fit=A_fit, Y_fit=Y_fit, infos=infos, lm_arc=fr, far=far)


def far_rows(c, A, Y, AF, YF, At0, Yt0, ct, prm, log=print, At2=None, Yt2=None):
    """SECONDARY DESIGN of the far end (c > template row): the last body row's C (lip curl, round tube, shell) is carried
    along the crest by an affine map a' = a_B + fa(c) (a - a_B) - da(c), y' = fy(c) y (the C keeps its curl and never
    folds), sinking into the sea by c_end.  da(c) is the smallest retreat that keeps the row out of the painting's sky
    (the window under the lip, back-projected on the plane), smoothed and monotone along the crest."""
    c_end = float(prm["far_c_end"]); fa_min = float(prm.get("far_fa_min", 0.55)); pw = float(prm.get("far_pow", 1.0))
    if At2 is None:
        At2, Yt2 = At0, Yt0
    fbc = float(prm.get("far_blend_c", 1.0))

    def tmpl(cc):
        b = C.smoothstep((cc - ct) / fbc)
        return (1 - b) * At0 + b * At2, (1 - b) * Yt0 + b * Yt2
    aB = float(At0[LM3["j_B"]])
    rows = [r for r in range(len(c)) if c[r] > ct]
    lip_rows = [r for r in range(len(c)) if prm.get("far_lip_to_loop2") and prm["far_lip_to_loop2"][0] < c[r] <= ct]
    da = np.zeros(len(c)); fy = np.ones(len(c)); fa = np.ones(len(c))
    for r in rows:
        t = np.clip((c[r] - ct) / (c_end - ct), 0, 1)
        fy[r] = 1.0 - C.smoothstep(t) ** pw if t < 1 else 0.0
        fa[r] = fa_min + (1.0 - fa_min) * fy[r] ** float(prm.get("far_fa_pow", 0.7))
    k0, k1 = prm.get("far_to_loop2", [1e9, 1e9 + 1])
    b2b = np.array([C.smoothstep((cc - k0) / (k1 - k0)) for cc in c])
    # the lip / hook columns hand over earlier (the loop-2 lip is window-safe; a blend of two lips hangs in the window)
    l0, l1 = prm.get("far_lip_to_loop2", [k0, k1])
    b2l = np.array([C.smoothstep((cc - l0) / (l1 - l0)) for cc in c])
    jj = np.arange(400)
    wcol = C.smoothstep((jj - 150) / 25.0) * C.smoothstep((310 - jj) / 25.0)
    b2 = b2b[:, None] + (b2l - b2b)[:, None] * wcol[None, :]

    def row_at(r, d):
        At, Yt = tmpl(c[r])
        a = aB + fa[r] * (At - aB) - d; y = fy[r] * Yt
        g = C.smoothstep((float(prm.get("far_flat_fy", 0.1)) - fy[r]) / float(prm.get("far_flat_fy", 0.1)))
        if g > 0:
            # the sinking curl unfolds into the flat sea: columns become monotone in a (no fold of the flat end)
            Am = np.maximum.accumulate(a) + np.arange(len(a)) * 1e-3
            a = (1 - g) * a + g * Am; y = (1 - g) * y
        # the flat sea columns spread out on both sides (the sheet stays a rectangle in a)
        a[:LM3["j_B"] + 1] = np.linspace(min(-49.2, a[LM3["j_B"]] - 5), a[LM3["j_B"]], LM3["j_B"] + 1)
        a[LM3["j_E"]:] = np.linspace(a[LM3["j_E"]], max(33.0, a[LM3["j_E"]] + 5), 400 - LM3["j_E"])
        # hand the far end over to the loop-2 far rows (they hug the painting's window: its left boundary
        # back-projected on the far planes is the painted inner face near the water, which only far rows can cover)
        return (1 - b2[r]) * a + b2[r] * AF[r], (1 - b2[r]) * y + b2[r] * YF[r]
    for r in rows:
        if b2[r].min() >= 0.999:
            continue
        aa, yy, ok = painting_plane(c[r])
        best = None
        for d in np.arange(0.0, float(prm.get("far_da_max", 14.0)) + 0.01, 0.2):
            a0, y0 = row_at(r, d)
            m = (y0 > 0.3) & (np.arange(len(y0)) >= int(prm.get("far_check_j0", 240)))
            ia = np.clip(np.round((a0[m] - aa[0]) / (aa[1] - aa[0])).astype(int), 0, len(aa) - 1)
            iy = np.clip(np.round((y0[m] - yy[0]) / (yy[1] - yy[0])).astype(int), 0, len(yy) - 1)
            if ok[iy, ia].all():
                best = d; break
        da[r] = best if best is not None else float(prm.get("far_da_max", 14.0))
    dd = np.where(c > ct, da, 0.0)
    sig = float(prm.get("far_da_sigma", 0.6))
    Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sig) ** 2); Wm /= Wm.sum(1, keepdims=True)
    dd_s = np.maximum(Wm @ dd, dd - float(prm.get("far_da_tol", 0.3)))
    A2, Y2 = A.copy(), Y.copy()
    for r in rows:
        A2[r], Y2[r] = row_at(r, dd_s[r])
    for r in lip_rows:
        # body rows before the template: their own lip hands over to the loop-2 lip
        A2[r] = (1 - b2[r]) * A[r] + b2[r] * AF[r]; Y2[r] = (1 - b2[r]) * Y[r] + b2[r] * YF[r]
    log("far rows: c_t %.2f c_end %.2f retreat at c=6/8/10: %s" % (ct, c_end, [round(float(np.interp(x, c, dd_s)), 2) for x in (6, 8, 10)]))
    return A2, Y2, dict(da=dd_s, fy=fy, fa=fa)


def resample400(Q, L, a_back=-49.2, a_front=33.0):
    s = C.arclen(Q[:, 0], Q[:, 1])
    A = np.zeros(400); Y = np.zeros(400)
    jB, jE = LM3["j_B"], LM3["j_E"]
    aB = np.interp(L["j_B"], s, Q[:, 0]); aE = np.interp(L["j_E"], s, Q[:, 0])
    A[:jB + 1] = np.linspace(min(a_back, aB - 5), aB, jB + 1); Y[:jB + 1] = 0.0
    A[jE:] = np.linspace(aE, max(a_front, aE + 5), 400 - jE); Y[jE:] = 0.0
    segs = list(zip(ORDER[:-1], ORDER[1:]))
    u = [(L[k1] - L[k0]) / (LM3[k1] - LM3[k0]) for k0, k1 in segs]
    joint = [u[0]] + [float(np.sqrt(u[i] * u[i + 1])) for i in range(len(u) - 1)] + [u[-1]]
    for i, (k0, k1) in enumerate(segs):
        j0, j1 = LM3[k0], LM3[k1]
        nn = j1 - j0
        h = np.linspace(joint[i], joint[i + 1], nn)
        h = np.maximum(h, 1e-6); h *= (L[k1] - L[k0]) / h.sum()
        ss = L[k0] + np.r_[0.0, np.cumsum(h)]
        A[j0:j1 + 1] = np.interp(ss, s, Q[:, 0]); Y[j0:j1 + 1] = np.interp(ss, s, Q[:, 1])
    return A, Y


def main(vol_path, prm_path, out):
    prm = json.load(open(prm_path, encoding="utf-8"))
    vol = CV.Vol(vol_path)
    c, A, Y, info = build(vol, prm)
    np.savez_compressed(out, A=A, Y=Y, c=c, weight=info["weight"], A_fit=info["A_fit"], Y_fit=info["Y_fit"])
    H = Y.max(1)
    print("ok", out, "H0 %.2f Hmax %.2f at c %.2f" % (Y[159].max(), H.max(), c[np.argmax(H)]))
    return info


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
