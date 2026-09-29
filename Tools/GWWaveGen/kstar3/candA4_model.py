# -*- coding: utf-8 -*-
"""Q20 loop 3, candidate A4: low-DOF parametric sculpt of the final frame K*' (no reference-model data is read here).

Every row (a constant-c section plane of the K* 26修正01 frame) is ONE smooth curve built from a handful of
tangent-continuous primitives, and every primitive parameter is a smooth cubic B-spline of c with a few control values,
so bulges or dents inside the surface cannot appear by construction:

  back sea -> foot fillet (concave) -> straight -> round back arc (convex) -> crest top T (horizontal tangent)
  -> lip chain: crest front arc (convex) -> descent -> neck/valley arc (concave) -> ridge/hook arc (convex)
     -> hook arc (convex) -> round tip cap
  -> underside (cubic Bezier, G1) -> barrel (polar curve around its centre: radius R with 2nd/3rd harmonics, i.e. a
     round tube whose deviation from a circle is a smooth low-order term) -> trough ramp (cubic Bezier) -> front sea

On the near shoulder (c < -4) the neck/valley and the ridge of the lip chain ARE the b region (the second crest): the
ridge is the band's top edge seen from the painting camera and the tip cap is its claw edge; toward the main section
the valley closes into the lip's small concave neck (the painting's くびれ in 132).

Lengths are proportions of the row height H (so the rows shrink smoothly into the flat sea at both ends); a few
tip-scale lengths are absolute metres.  Columns follow the K* landmarks: j_B 18 = back foot, j_top 90 = crest top,
j_tip 200 = tip apex, j_corner 314 = rearmost point of the barrel, j_facebot 379 = lowest point in front, j_E 394 =
front sea start.
"""
import os, sys, json, math
import numpy as np
from scipy.interpolate import BSpline
from scipy.ndimage import gaussian_filter1d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

NU, NV = 400, 240
TURN_MAX = 150.0        # max total clockwise turn of the lip chain (crest top -> tip)
TC_MAX = 165.0          # max turn of the tip cap
SEGCOLS = [0, 18, 90, 200, 314, 379, 394, 399]      # column boundaries of the 7 segments
PARAMS = ["H", "aT",                                # crest top
          "ea", "eb", "thb", "rf",                  # back: ellipse semi-axes /H (horizontal, vertical), end slope (deg), foot fillet radius/H
          "r1", "t1", "r2", "t2", "r3", "t3", "r4", "t4", "r5", "t5",   # lip chain (radius/H, turn deg; arc 3 concave)
          "rt", "tc",                               # tip cap radius (m) and turn (deg)
          "k0", "k1",                               # underside Bezier handle factors
          "bx", "by", "rR", "e2c", "e2s", "e3c", "e3s",          # barrel centre (/H, rel. to T), radius/H, harmonics
          "phj", "phe",                             # barrel join angle (deg) and end angle past 270 (deg)
          "lr", "dt", "dsea",                       # trough ramp length/H, trough depth/H; sea level of the far back (m, <=0)
          "fb"]                                     # height (m) below which the row fades into a flat, curl-free swell


# ------------------------------------------------------------------ rows and parameter splines
def c_rows(c0=-60.0, c_dense0=-18.0, c1=14.0, dc=0.2, nv=NV):
    n_dense = int(round((c1 - c_dense0) / dc))
    dense = c_dense0 + dc * np.arange(n_dense + 1)
    n_left = nv - len(dense)
    L = c_dense0 - c0
    lo, hi = 1.0, 1.2
    for _ in range(80):
        g = 0.5 * (lo + hi)
        s = dc * (g ** np.arange(1, n_left + 1))
        if s.sum() > L:
            hi = g
        else:
            lo = g
    s = dc * (g ** np.arange(1, n_left + 1)); s *= L / s.sum()
    left = c_dense0 - np.cumsum(s)
    c = np.r_[left[::-1], dense]
    c[0] = c0
    return c


class Spline1:
    """natural cubic spline of c through the control values at the knot sites (C2; values at the sites = row values),
    held constant outside the sites."""

    def __init__(self, sites):
        self.sites = np.asarray(sites, float)

    def __call__(self, v, c):
        from scipy.interpolate import CubicSpline
        cs = CubicSpline(self.sites, np.asarray(v, float), bc_type="natural")
        return cs(np.clip(c, self.sites[0], self.sites[-1]))


class Design:
    """sites + control values per parameter (dict name -> list).  Parameters may have their own sites."""

    def __init__(self, d):
        self.d = d
        self.sites = {k: np.asarray(d["sites"].get(k, d["sites"]["default"]), float) for k in PARAMS}
        self.vals = {k: np.asarray(d["values"][k], float) for k in PARAMS}
        self.spl = {}
        for k in PARAMS:
            key = tuple(self.sites[k])
            if key not in self.spl:
                self.spl[key] = Spline1(self.sites[k])

    def eval(self, c):
        return {k: self.spl[tuple(self.sites[k])](self.vals[k], c) for k in PARAMS}

    def to_json(self):
        return {"sites": {k: list(map(float, v)) for k, v in self.d["sites"].items()},
                "values": {k: list(map(float, self.vals[k])) for k in PARAMS}}


# ------------------------------------------------------------------ curve primitives (dense polylines)
def arc(P, psi, R, turn_deg, step=0.02):
    """circular arc from P with heading psi (rad), radius R, signed turn (deg, + = CCW/left).  returns pts (n,2), psi."""
    tr = math.radians(turn_deg)
    L = abs(tr) * R
    n = max(int(math.ceil(L / step)), 2)
    if abs(tr) < 1e-9 or R <= 0:
        s = np.linspace(0, max(L, 0), n)
        return P[None, :] + s[:, None] * np.array([math.cos(psi), math.sin(psi)]), psi
    sg = 1.0 if tr > 0 else -1.0
    cen = P + sg * R * np.array([-math.sin(psi), math.cos(psi)])
    a0 = math.atan2(P[1] - cen[1], P[0] - cen[0])
    a = a0 + np.linspace(0, tr, n)
    pts = cen[None, :] + R * np.stack([np.cos(a), np.sin(a)], -1)
    pts[0] = P
    return pts, psi + tr


def line(P, psi, L, step=0.02):
    n = max(int(math.ceil(max(L, 0) / step)), 2)
    s = np.linspace(0, max(L, 0), n)
    return P[None, :] + s[:, None] * np.array([math.cos(psi), math.sin(psi)]), psi


def bezier(P0, T0, P1, T1, k0, k1, n=None, step=0.02):
    d = np.linalg.norm(P1 - P0)
    Q0 = P0; Q1 = P0 + k0 * d * T0; Q2 = P1 - k1 * d * T1; Q3 = P1
    if n is None:
        n = max(int(math.ceil(1.5 * d / step)), 4)
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * Q0 + 3 * (1 - t) ** 2 * t * Q1 + 3 * (1 - t) * t * t * Q2 + t ** 3 * Q3


def cat(parts):
    out = [parts[0]]
    for p in parts[1:]:
        out.append(p[1:] if len(p) > 1 and np.linalg.norm(p[0] - out[-1][-1]) < 1e-6 else p)
    return np.vstack(out)


def resample(P, n):
    """n+1 points uniformly by arc length (endpoints kept)."""
    s = C.arclen(P[:, 0], P[:, 1])
    if s[-1] < 1e-9:
        return np.repeat(P[:1], n + 1, 0)
    q = np.linspace(0, s[-1], n + 1)
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], -1)


def _seg_cross(P, Q):
    """first crossing (i, k, point) of polyline P (searched from its end backwards) with polyline Q (from its start)."""
    a0, a1 = P[:-1], P[1:]; b0, b1 = Q[:-1], Q[1:]
    r = a1 - a0; s = b1 - b0
    for i in range(len(r) - 1, -1, -1):
        den = r[i, 0] * s[:, 1] - r[i, 1] * s[:, 0]
        ok = np.abs(den) > 1e-12
        dq = b0 - a0[i]
        t = (dq[:, 0] * s[:, 1] - dq[:, 1] * s[:, 0]) / np.where(ok, den, 1.0)
        u = (dq[:, 0] * r[i, 1] - dq[:, 1] * r[i, 0]) / np.where(ok, den, 1.0)
        m = ok & (t > 1e-9) & (t < 1 - 1e-9) & (u > 1e-9) & (u < 1 - 1e-9)
        if m.any():
            k = int(np.nonzero(m)[0][0])
            return i, k, a0[i] + t[k] * r[i]
    return None


def untie_tip(upper, lower, span=4.0):
    """if the upper lip surface and the underside cross near the tip (a small loop left by the cap when the hook
    arrives steeply), cut the loop at the crossing: the tip becomes that point (continuous in the parameters)."""
    su = C.arclen(upper[:, 0], upper[:, 1]); sl = C.arclen(lower[:, 0], lower[:, 1])
    iu = int(np.searchsorted(su, su[-1] - span)); il = int(np.searchsorted(sl, span))
    P = upper[iu:]; Q = lower[:il + 1]
    if len(P) < 3 or len(Q) < 3:
        return upper, lower
    # ignore the shared tip point itself
    hit = _seg_cross(P[:-1], Q[1:])
    if hit is None:
        return upper, lower
    i, k, X = hit
    up = np.vstack([upper[:iu + i + 1], X[None]])
    lo = np.vstack([X[None], lower[1 + k + 1:]])
    return up, lo


# ------------------------------------------------------------------ one section
def section(p, return_parts=False, smooth_sigma=0.25):
    """p: dict of scalars.  returns (400, 2) array of (a, y) and a dict with landmark info."""
    H_true = max(float(p["H"]), 0.0)
    H = max(H_true, 1.2)            # geometry is built at >= 1.2 m and squashed vertically below that
    squash = H_true / H
    aT = float(p["aT"])
    T = np.array([aT, H])
    # ---- back (built from T backwards, then reversed): quarter-ellipse (round mass) -> straight -> foot fillet
    thb = math.radians(float(np.clip(p["thb"], 20.0, 89.5)))
    ea, eb = float(p["ea"]) * H, min(float(p["eb"]) * H, 0.98 * H)
    u_end = math.atan((ea / eb) * math.tan(thb))
    u = np.linspace(0.0, u_end, max(int(0.5 * (ea + eb) * u_end / 0.02), 20))
    b1 = np.stack([aT - ea * np.sin(u), H - eb + eb * np.cos(u)], -1)
    ye = b1[-1, 1]
    Rf = float(p["rf"]) * H
    if Rf * (1 - math.cos(thb)) > ye:
        Rf = ye / (1 - math.cos(thb))
    s_line = max((ye - Rf * (1 - math.cos(thb))) / math.sin(thb), 0.0)
    ps = math.pi + thb
    b2, ps = line(b1[-1], ps, s_line)
    b3, ps = arc(b2[-1], ps, Rf, -math.degrees(thb))
    back = cat([b1, b2, b3])[::-1]
    F = back[0].copy()
    # ---- lip chain from T forward
    parts = []
    P = T.copy(); psi = 0.0
    # the hook may point down or down-back but never curl past 150 deg in total (a spiral would make the underside
    # cross the hook): the excess is taken off t5, then t4 (continuous in the parameters)
    tt = {k: float(p[k]) for k in ("t1", "t2", "t3", "t4", "t5")}
    excess = tt["t1"] + tt["t2"] - tt["t3"] + tt["t4"] + tt["t5"] - TURN_MAX
    if excess > 0:
        d5 = min(excess, tt["t5"]); tt["t5"] -= d5; excess -= d5
        tt["t4"] -= min(max(excess, 0.0), tt["t4"])
    for (r, t) in (("r1", "t1"), ("r2", "t2"), ("r3", "t3"), ("r4", "t4"), ("r5", "t5")):
        sgn = +1.0 if r == "r3" else -1.0
        q, psi = arc(P, psi, max(float(p[r]), 1e-3) * H, sgn * tt[t])
        parts.append(q); P = q[-1]
    lip = cat(parts)
    rt = max(float(p["rt"]), 0.3) * min(1.0, H / 8.0)
    # ---- barrel (polar around the centre)
    cen = np.array([aT + float(p["bx"]) * H, float(p["by"]) * H])
    R0 = float(p["rR"]) * H

    def rho(ph):
        return R0 * (1 + p["e2c"] * np.cos(2 * ph) + p["e2s"] * np.sin(2 * ph) + p["e3c"] * np.cos(3 * ph) + p["e3s"] * np.sin(3 * ph))

    def drho(ph):
        return R0 * (-2 * p["e2c"] * np.sin(2 * ph) + 2 * p["e2s"] * np.cos(2 * ph) - 3 * p["e3c"] * np.sin(3 * ph) + 3 * p["e3s"] * np.cos(3 * ph))
    phj = math.radians(float(p["phj"]))
    # where the barrel bottom stays above the trough, the barrel ends earlier (heading down-forward, up to 45 deg
    # before its bottom) so that the face runs on into the trough without a step; smooth in the parameters
    ytb0 = -float(p["dt"]) * H
    y270 = cen[1] - rho(1.5 * math.pi)
    sblend = float(np.clip((y270 - ytb0) / (0.15 * H), 0.0, 1.0)); sblend = sblend * sblend * (3 - 2 * sblend)
    phe = 1.5 * math.pi + math.radians(float(p["phe"])) - math.radians(45.0) * sblend
    n_ph = max(int((phe - phj) * R0 / 0.02), 50)
    ph = np.linspace(phj, phe, n_ph)
    rr = rho(ph)
    tube = cen[None, :] + rr[:, None] * np.stack([np.cos(ph), np.sin(ph)], -1)
    dt = drho(ph)[:, None] * np.stack([np.cos(ph), np.sin(ph)], -1) + rr[:, None] * np.stack([-np.sin(ph), np.cos(ph)], -1)
    tj = dt[0] / np.linalg.norm(dt[0]); te = dt[-1] / np.linalg.norm(dt[-1])
    # ---- tip cap: its turn is set by the geometry so that the underside leaves the tip heading for the barrel join
    # (a fixed turn made the underside cusp back across the hook where the hook arrives steeply); continuous
    dir_j = math.atan2(tube[0][1] - P[1], tube[0][0] - P[0])
    tc = math.degrees((psi - dir_j) % (2 * math.pi))
    tc = float(np.clip(tc, 70.0, TC_MAX))
    cap1, psi_mid = arc(P, psi, rt, -0.5 * tc, step=0.005)
    tip = cap1[-1].copy()
    cap2, psi_u = arc(tip, psi_mid, rt, -0.5 * tc, step=0.005)
    U0 = cap2[-1]
    Tu = np.array([math.cos(psi_u), math.sin(psi_u)])
    # the underside first runs a short way straight on from the tip cap (so it cannot curl back across the cap),
    # then a G1 cubic Bezier into the barrel
    L0 = min(0.8, 0.12 * np.linalg.norm(tube[0] - U0)) * min(1.0, H / 8.0)
    u0, _ = line(U0, psi_u, L0, step=0.01)
    under = cat([u0, bezier(u0[-1], Tu, tube[0], tj, max(float(p["k0"]), 0.3), float(p["k1"]))])
    # ---- trough (every row has a front trough with a well-defined bottom) and the ramp up to the front sea
    Qe = tube[-1]
    Lr = max(float(p["lr"]) * H, 0.8)
    ytb = min(-float(p["dt"]) * H, Qe[1] - 0.02 * H)
    Btr = np.array([Qe[0] + max(0.35 * Lr, 1.3 * (Qe[1] - ytb)), ytb])     # the drop into the trough is never steeper than ~38 deg
    E = np.array([Btr[0] + 0.65 * Lr, 0.0])
    ramp1 = bezier(Qe, te, Btr, np.array([1.0, 0.0]), 0.35, 0.35)
    ramp2 = bezier(Btr, np.array([1.0, 0.0]), E, np.array([1.0, 0.0]), 0.4, 0.4)
    ramp = cat([ramp1, ramp2])
    dsea = float(p.get("dsea", 0.0))
    backsea = np.array([[F[0] - 40.0, dsea], F])
    frontsea = np.array([E, [E[0] + 30.0, 0.0]])
    # ---- smoothing of the G1 joins (curvature continuity), not near the tip or the sea contacts
    def smooth(Pp, sig, keep_end=False, keep_start=False):
        if len(Pp) < 8 or sig <= 0:
            return Pp
        s = C.arclen(Pp[:, 0], Pp[:, 1]); step = 0.02
        q = np.arange(0, s[-1] + 1e-9, step)
        if len(q) < 8:
            return Pp
        X = np.stack([np.interp(q, s, Pp[:, 0]), np.interp(q, s, Pp[:, 1])], -1)
        Xs = np.stack([gaussian_filter1d(X[:, k], sig / step, mode="nearest") for k in range(2)], -1)
        w = np.ones(len(q))
        ramp_n = int(3 * sig / step)
        if keep_start:
            w[:ramp_n] = np.linspace(0, 1, ramp_n) if ramp_n > 0 else 1
        if keep_end:
            w[-ramp_n:] = np.minimum(w[-ramp_n:], np.linspace(1, 0, ramp_n)) if ramp_n > 0 else 1
        return X + w[:, None] * (Xs - X)
    sg = smooth_sigma * min(1.0, H / 10.0)
    backlip = cat([back, lip])
    jT = len(back) - 1
    sB = C.arclen(backlip[:, 0], backlip[:, 1]); sT = sB[jT]
    backlip_s = smooth(backlip, sg, keep_end=True, keep_start=True)
    # re-locate T on the smoothed curve by arc length
    sBs = C.arclen(backlip_s[:, 0], backlip_s[:, 1])
    kT = int(np.argmin(np.abs(sBs - sT * sBs[-1] / sB[-1])))
    back_s, lip_s = backlip_s[:kT + 1], backlip_s[kT:]
    inner = cat([under, tube])
    inner_s = smooth(inner, sg, keep_start=True, keep_end=True)
    # landmarks on the inner curve: rearmost point of the barrel part and lowest point (tube end + ramp)
    nU = len(under)
    # j_corner = the barrel point at polar angle 180 deg (continuous in the parameters; an argmin of a could jump
    # between two near-equal minima of the harmonic barrel and shuffle the columns from row to row)
    k_ph = int(np.clip(np.searchsorted(ph, math.pi), 1, len(ph) - 2)) if ph[0] < math.pi < ph[-1] else (1 if ph[0] >= math.pi else len(ph) - 2)
    k_corner = int(np.argmin(np.linalg.norm(inner_s - tube[k_ph][None, :], axis=1)))
    k_corner = int(np.clip(k_corner, 2, len(inner_s) - 3))
    front = cat([inner_s[k_corner:], ramp1])
    k_bot = len(front) - 1
    front = cat([front, ramp2])
    upper = cat([lip_s, cap1]); lower = cat([cap2, inner_s[:k_corner + 1]])
    segs = [backsea, back_s, upper, lower,
            front[:k_bot + 1], front[k_bot:], frontsea]
    out = [resample(segs[0], 18)]
    TIPC, TIPL = 12, 0.9          # the last / first 0.9 m around the tip apex get 12 columns each (a well-resolved cap)
    for k in range(1, 7):
        n = SEGCOLS[k + 1] - SEGCOLS[k]
        if k in (2, 3):
            P = segs[k]; s_ = C.arclen(P[:, 0], P[:, 1]); L = s_[-1]; Lt = min(TIPL, 0.3 * L)
            if k == 2:
                q = np.r_[np.linspace(0, L - Lt, n - TIPC + 1)[:-1], np.linspace(L - Lt, L, TIPC + 1)]
            else:
                q = np.r_[np.linspace(0, Lt, TIPC + 1)[:-1], np.linspace(Lt, L, n - TIPC + 1)]
            q = np.stack([np.interp(q, s_, P[:, 0]), np.interp(q, s_, P[:, 1])], -1)
        else:
            q = resample(segs[k], n)
        out.append(q[1:])
    S = np.vstack(out)
    assert S.shape == (NU, 2), S.shape
    S[:, 1] *= squash
    # rows fading into the sea (H < 3.5 m; flat below 1 m): the curl is blended into a monotone flat parametrisation, so the vanishing
    # ends never fold over in plan (no flipped or self-intersecting quads)
    fb = max(float(p.get("fb", 3.5)), 1.5)
    if H_true < fb:
        w = float(np.clip((H_true - 1.0) / (fb - 1.0), 0.0, 1.0)); w = w * w * (3 - 2 * w)
        s = C.arclen(S[:, 0], S[:, 1] / max(squash, 1e-9) if squash > 0 else S[:, 1])
        seg = np.searchsorted(np.arange(NU), [SEGCOLS[1], SEGCOLS[6]])
        a0, a1 = S[SEGCOLS[1], 0], S[SEGCOLS[6], 0]
        f = (s[SEGCOLS[1]:SEGCOLS[6] + 1] - s[SEGCOLS[1]]) / max(s[SEGCOLS[6]] - s[SEGCOLS[1]], 1e-9)
        flat = a0 + f * (a1 - a0)
        S[SEGCOLS[1]:SEGCOLS[6] + 1, 0] = w * S[SEGCOLS[1]:SEGCOLS[6] + 1, 0] + (1 - w) * flat
    info = {"T": T * [1, squash], "tip": tip * [1, squash], "F": F, "E": E, "cen": cen * [1, squash], "R": R0 * squash}
    if return_parts:
        info["parts"] = {"back": back, "lip": lip, "cap": cat([cap1, cap2]), "under": under, "tube": tube, "ramp": ramp}
    return S, info


def build(design, c):
    P = design.eval(c)
    A = np.zeros((len(c), NU)); Y = np.zeros((len(c), NU))
    infos = []
    for r in range(len(c)):
        p = {k: float(P[k][r]) for k in PARAMS}
        S, inf = section(p)
        A[r], Y[r] = S[:, 0], S[:, 1]
        infos.append(inf)
    return A, Y, infos


def load_design(path):
    return Design(json.load(open(path, encoding="utf-8")))


if __name__ == "__main__":
    import time
    d = load_design(sys.argv[1])
    c = c_rows()
    t = time.time(); A, Y, inf = build(d, c); print("build %.2fs" % (time.time() - t), A.shape)
