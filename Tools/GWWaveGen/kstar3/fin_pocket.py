# -*- coding: utf-8 -*-
"""Q20 final K*': the painting's sky pocket under the lip (inside outline 72) and the lip band, in "main-equivalent"
coordinates, and the camera-ray mapping between a row plane c and the main plane c = 0.

Main-equivalent coordinates: a point (a, y) on the row plane c is carried along its PaintingCam v1 ray to the main plane
c = 0, where it lands at (a', y') = cam + lam(c) * ((a, y) - cam),  lam(c) = (0 - c_cam) / (c - c_cam).
Every row therefore sees the same pocket / band in main-equivalent coordinates; a far row (c > 0) is hidden in the
painting view as long as its main-equivalent image stays out of the pocket and under the band top.

Only the painting (PaintingTruth sky envelope) is read here.  No reference-model data.
"""
import os, sys, json, math
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

HORIZON = 787.7
_CACHE = {}


def cam_sec():
    V1, tgt, fr = C.painting_frame()
    S = C.sec(fr.cam.pos[None, :])[0]
    return float(S[0]), float(S[1]), float(S[2])


def lam(c, c_cam=None):
    if c_cam is None:
        c_cam = cam_sec()[2]
    return (0.0 - c_cam) / (np.asarray(c, float) - c_cam)


def to_real(P, c, cs=None):
    """main-equivalent (n, 2) -> row plane c (n, 2)."""
    a_c, y_c, c_c = cs or cam_sec()
    L = (0.0 - c_c) / (c - c_c)
    P = np.asarray(P, float)
    return np.stack([a_c + (P[..., 0] - a_c) / L, y_c + (P[..., 1] - y_c) / L], -1)


def to_eq(P, c, cs=None):
    a_c, y_c, c_c = cs or cam_sec()
    L = (0.0 - c_c) / (c - c_c)
    P = np.asarray(P, float)
    return np.stack([a_c + (P[..., 0] - a_c) * L, y_c + (P[..., 1] - y_c) * L], -1)


def allowed_main(res=0.04, a_rng=(-4.0, 13.0), y_rng=(2.0, 24.0)):
    V1, tgt, fr = C.painting_frame()
    aa = np.arange(a_rng[0], a_rng[1] + 1e-9, res); yy = np.arange(y_rng[0], y_rng[1] + 1e-9, res)
    A, Y = np.meshgrid(aa, yy)
    X = C.world(np.zeros(A.shape[0]), A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    s = tgt.sample(P[:, :2], comp=True)          # half-width compensated target (as the gate)
    ok = (s < 0.0) | (P[:, 1] > HORIZON)
    return aa, yy, ok.reshape(A.shape)


def pocket(res=0.04, smooth_m=0.35):
    """pocket boundary path (main-eq), from the lip tip along the lip underside to the tube corner and down the inner
    wall (72 lower) to the horizon; smoothed along its arc length and pushed out of the pocket where smoothing cut in.
    Returns dict(path (n,2), s (n,), i_corner, band_top (a', y'_top) arrays)."""
    if "pk" in _CACHE:
        return _CACHE["pk"]
    aa, yy, ok = allowed_main(res)
    sky = (~ok).astype(np.uint8)
    lab = cv2.connectedComponents(sky)[1]
    ia = int((5.0 - aa[0]) / res); iy = int((8.0 - yy[0]) / res)
    pk = lab == lab[iy, ia]
    # restrict to the pocket proper: below 13.3 m, left of the tip (11.75), above the horizon line (y' 2.9)
    A, Y = np.meshgrid(aa, yy)
    pk &= (Y < 13.3) & (A < 11.75) & (Y > 2.9)
    m = pk.astype(np.uint8)
    cn, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cn = max(cn, key=len)[:, 0, :]
    P = np.stack([aa[cn[:, 0]], yy[cn[:, 1]]], -1)
    # keep the boundary points that touch the painted wave (not the artificial clip lines)
    ii = np.clip(cn[:, 1], 1, len(yy) - 2); jj = np.clip(cn[:, 0], 1, len(aa) - 2)
    touch = np.zeros(len(cn), bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            touch |= ok[ii + dy, jj + dx]
    touch &= (P[:, 0] < 11.7) & (P[:, 1] > 2.95)
    # rotate so that the run of touching points is contiguous; take the longest run
    idx = np.nonzero(~touch)[0]
    if len(idx):
        P = np.roll(P, -idx[0], 0); touch = np.roll(touch, -idx[0])
    runs = []; cur = []
    for i, t in enumerate(touch):
        if t:
            cur.append(i)
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    run = max(runs, key=len)
    Q = P[run].astype(float)
    # orient: start at the lip tip (large a', high), end at the horizon (low y')
    if Q[0, 1] < Q[-1, 1]:
        Q = Q[::-1]
    # start at the lip tip: the most forward wave-side point at y' 11.5..12.9
    tipc = np.nonzero((Q[:, 1] > 11.5) & (Q[:, 1] < 12.9))[0]
    it = int(tipc[np.argmax(Q[tipc, 0])])
    Q = Q[it:]
    Q = C.resample_poly(Q, step=0.05)
    s = C.arclen(Q[:, 0], Q[:, 1])
    k = smooth_m / 0.05
    Qs = np.stack([gaussian_filter1d(Q[:, 0], k, mode="nearest"), gaussian_filter1d(Q[:, 1], k, mode="nearest")], -1)
    # push smoothed points out of the pocket (towards the wave) where they cut in
    inside = lambda q: pk[np.clip(((q[:, 1] - yy[0]) / res).round().astype(int), 0, len(yy) - 1),
                          np.clip(((q[:, 0] - aa[0]) / res).round().astype(int), 0, len(aa) - 1)]
    d = np.gradient(Qs, axis=0); d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    nrm = np.stack([-d[:, 1], d[:, 0]], -1)          # left normal
    # the wave side = the side that is not the pocket: test with a small step
    t1 = inside(Qs + 0.3 * nrm).mean(); t2 = inside(Qs - 0.3 * nrm).mean()
    out = nrm if t1 < t2 else -nrm
    push = np.zeros(len(Qs))
    for _ in range(40):
        bad = inside(Qs + push[:, None] * out)
        if not bad.any():
            break
        push[bad] += 0.02
    push = gaussian_filter1d(np.maximum.accumulate(push * 0) + push, 3)
    Qs = Qs + push[:, None] * out
    s = C.arclen(Qs[:, 0], Qs[:, 1])
    # corner: the back-most point above y' 9 (the tube's top-left)
    up = np.nonzero(Qs[:, 1] > 9.0)[0]
    i_back = int(up[np.argmin(Qs[up, 0])])
    # band top (upper boundary of the painted region) per a'
    top = np.full(len(aa), np.nan)
    for j in range(len(aa)):
        col = np.nonzero(ok[:, j])[0]
        if len(col):
            top[j] = yy[col.max()]
    res_ = {"path": Qs, "s": s, "out": out, "i_back": i_back, "band_a": aa, "band_top": top, "pocket_mask": pk,
            "grid": (aa, yy)}
    _CACHE["pk"] = res_
    return res_


def path_at(u):
    """point on the pocket path at arc fraction u (0 = lip tip, 1 = horizon end) and its outward normal."""
    pk = pocket(); s = pk["s"]; Q = pk["path"]; o = pk["out"]
    q = np.clip(u, 0, 1) * s[-1]
    return (np.stack([np.interp(q, s, Q[:, 0]), np.interp(q, s, Q[:, 1])], -1),
            np.stack([np.interp(q, s, o[:, 0]), np.interp(q, s, o[:, 1])], -1))


def u_of_point(name):
    pk = pocket(); s = pk["s"]; Q = pk["path"]
    if name == "back":
        return s[pk["i_back"]] / s[-1]
    if name == "hookbot":
        top = np.nonzero(Q[:, 0] > 8.0)[0]
        return s[top[np.argmin(Q[top, 1])]] / s[-1]
    raise KeyError(name)


def u_at_y_edge(yv):
    """arc fraction of the inner-wall (72 lower) point at height y' (below the back-most point)."""
    pk = pocket(); s = pk["s"]; Q = pk["path"]; ib = pk["i_back"]
    seg = np.arange(ib, len(Q))
    yq = Q[seg, 1]
    o = np.argsort(yq)
    return float(np.interp(yv, yq[o], s[seg][o]) / s[-1])


def left_a_eq(yv):
    """the pocket's left boundary a' at height y' (main-eq); +inf where the pocket has no pixel at that height."""
    pk = pocket()
    if "left" not in pk:
        aa, yy = pk["grid"]; m = pk["pocket_mask"]
        L = np.full(len(yy), np.inf)
        for i in range(len(yy)):
            xs = np.nonzero(m[i])[0]
            if len(xs):
                L[i] = aa[xs.min()]
        fin = np.isfinite(L)
        Ls = L.copy()
        Ls[fin] = gaussian_filter1d(L[fin], 6)
        Ls[fin] = np.minimum(Ls[fin], L[fin])
        pk["left"] = (yy, Ls)
    yy, Ls = pk["left"]
    i = np.clip(np.round((np.asarray(yv, float) - yy[0]) / (yy[1] - yy[0])).astype(int), 0, len(yy) - 1)
    return Ls[i]


def lip_top_eq():
    """the painting's lip-top outline (gate target: 131 from the crest top, then 132 to the lip tip, half-width
    compensated) carried along the camera rays to the main plane: (a', y') from the crest top to the tip."""
    if "lip" not in _CACHE:
        import candA_warp as W
        pt = W.Painting()
        T = pt.T[pt.lm["top"]:pt.lm["tip"] + 1]
        Xn = W.backproject_to_plane(pt, T, np.zeros(len(T)))
        S = C.sec(Xn)[:, :2]
        S = C.resample_poly(S, step=0.05)
        S = np.stack([gaussian_filter1d(S[:, 0], 4, mode="nearest"), gaussian_filter1d(S[:, 1], 4, mode="nearest")], -1)
        _CACHE["lip"] = S
    return _CACHE["lip"]


def band_top_eq(a):
    pk = pocket()
    return np.interp(a, pk["band_a"], pk["band_top"])


if __name__ == "__main__":
    pk = pocket()
    Q = pk["path"]
    print("path points", len(Q), "length %.2f m" % pk["s"][-1], "back-most", Q[pk["i_back"]], "u_back %.3f" % u_of_point("back"),
          "u_hookbot %.3f" % u_of_point("hookbot"))
    for u in np.linspace(0, 1, 21):
        p, n = path_at(u)
        print("u %.2f  a' %.2f y' %.2f  out (%.2f, %.2f)" % (u, p[0], p[1], n[0], n[1]))
