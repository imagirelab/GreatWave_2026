# -*- coding: utf-8 -*-
"""Q20 loop 3, candidate A2 (push loop-2 K*' for drama): shared helpers.  No reference-model data is read here.

Frame = K* 26修正01 section frame (a along travel, y up, c along the crest; row 159 = c 0).  Grid 400 x 240 as K*.
  painting-view helpers: projection, ID-buffer visibility (painter's order), coverage mask, allowed test per row plane.
"""
import os, sys, math, json
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

REPO = C.REPO
Q20 = os.path.join(REPO, "Unity", "Build", "Q20")
L3 = os.path.join(REPO, "Unity", "Build", "Q20L3")
OUT = os.path.join(L3, "candA2")
WORK = os.path.join(OUT, "_work")
FINAL_ROWS = os.path.join(Q20, "final", "kstarF_a45_rows.npz")
LOOP1_ROWS = os.path.join(Q20, "final", "_loop1", "kstarF_a45_rows.npz")
HORIZON = 787.7
LM = C.LM
_PF = {}


def pframe():
    if "f" not in _PF:
        _PF["f"] = C.painting_frame()
    return _PF["f"]


def load_rows(p=FINAL_ROWS):
    z = np.load(p)
    return z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)


def project(X):
    V1, tgt, fr = pframe()
    return fr.cam.project(np.asarray(X).reshape(-1, 3))


def tris():
    V1, tgt, fr = pframe()
    return V1.triangles(C.NU, C.NV)


def coverage(c, A, Y, ss=2):
    """painting-view coverage (display px, 0..1) of the sheet"""
    V1, tgt, fr = pframe()
    return V1.rasterize(fr.cam, C.world(c, A, Y), tris(), ss)


def visibility(c, A, Y, ss=1):
    """painter's-order triangle ID buffer in the painting view -> (vis_vertex (nv, nu) bool, id image)."""
    V1, tgt, fr = pframe()
    X = C.world(c, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    T = tris()
    W, H = fr.cam.W * ss, fr.cam.H * ss
    xy = (P[:, :2] + 0.5) * ss - 0.5
    ok = (P[:, 2] > 0.5)
    tv = ok[T].all(1)
    z = P[T, 2].mean(1)
    order = np.nonzero(tv)[0]
    order = order[np.argsort(-z[order])]
    img = np.zeros((H, W, 3), np.uint8)
    ip = np.round(xy * 16).astype(np.int32)
    for k in order:
        i = int(k) + 1
        cv2.fillConvexPoly(img, ip[T[k]], (i & 255, (i >> 8) & 255, (i >> 16) & 255), lineType=cv2.LINE_8, shift=4)
    ids = img[..., 0].astype(np.int64) + (img[..., 1].astype(np.int64) << 8) + (img[..., 2].astype(np.int64) << 16)
    seen = np.unique(ids[ids > 0]) - 1
    vv = np.zeros(C.NU * C.NV, bool)
    vv[T[seen].ravel()] = True
    return vv.reshape(C.NV, C.NU), ids


def allowed_pts(c_rows, A, Y, margin=0.0, comp=False):
    """True where a point (row plane c, a, y) may hold surface without touching the painted sky: its painting-view image
    is inside the painted big wave (sky sdf < -margin), below the horizon, or outside the scored frame."""
    V1, tgt, fr = pframe()
    X = C.world(c_rows, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    s = tgt.sample(P[:, :2], comp=comp)
    ok = (s < -margin) | (P[:, 1] > HORIZON) | (P[:, 0] < tgt.x0) | (P[:, 0] > tgt.x1) | (P[:, 2] <= 0.5)
    return ok.reshape(np.shape(A)), s.reshape(np.shape(A))


def allowed_grid(c0, a_rng=(-30.0, 22.0), y_rng=(-6.0, 26.0), res=0.1, margin=0.0):
    aa = np.arange(a_rng[0], a_rng[1] + 1e-9, res); yy = np.arange(y_rng[0], y_rng[1] + 1e-9, res)
    Ag, Yg = np.meshgrid(aa, yy)
    ok, s = allowed_pts(np.full(Ag.shape[0], c0), Ag, Yg, margin)
    return aa, yy, ok, s


def gate(c, A, Y, png, title="A2 gate"):
    V1, tgt, fr = pframe()
    g = V1.preview_metrics(fr, tgt, fr.world(c, A, Y), V1.triangles(A.shape[1], A.shape[0]), png, title)
    return g


GATE_LIM = {"78": 1.87, "130": 2.30, "131": 1.97, "132": 1.90}


def gate_ok(g, margin=0.0):
    return all(g[k]["max_px"] <= GATE_LIM[k] - margin for k in GATE_LIM) and g["72"]["p95_px"] <= 4.0 - margin


def self_x(c, A, Y, win=12):
    V1, tgt, fr = pframe()
    return V1.local_self_intersections(fr.world(c, A, Y), win)


def flips(c, A, Y):
    """triangles whose normal points against the local sheet orientation (grid fold-overs), counted like the tech judge:
    the sign of the in-plane cross product of the two edge directions of each quad in (column, row)."""
    X = np.stack([A, Y, np.broadcast_to(c[:, None], A.shape)], -1)
    du = X[:, 1:] - X[:, :-1]; dv = X[1:] - X[:-1]
    n = np.cross(du[:-1], dv[:, :-1])
    # reference orientation: the in-plane normal of the row polyline, rotated; a flip = the quad normal reverses vs its
    # neighbours along the row (dot < 0)
    nn = n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12)
    d = (nn[:, 1:] * nn[:, :-1]).sum(-1)
    return int((d < -0.2).sum())


# ---------------------------------------------------------------- exact z-buffer (perspective-correct) in the painting view
def zbuffer(c, A, Y, ss=2, want_ids=True, max_px=128):
    """true depth buffer of the sheet in the painting view at ss x display resolution.
    Returns (zbuf (H*ss, W*ss) camera depth, inf = empty; ids (triangle index + 1, 0 = empty) or None)."""
    V1, tgt, fr = pframe()
    X = C.world(c, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    T = tris()
    W, H = fr.cam.W * ss, fr.cam.H * ss
    xy = (P[:, :2] + 0.5) * ss - 0.5
    iz = 1.0 / np.maximum(P[:, 2], 1e-6)
    ok = (P[T, 2] > 0.5).all(1)
    t0, t1, t2 = xy[T[:, 0]], xy[T[:, 1]], xy[T[:, 2]]
    x0 = np.floor(np.minimum.reduce([t0[:, 0], t1[:, 0], t2[:, 0]])).astype(int)
    x1 = np.ceil(np.maximum.reduce([t0[:, 0], t1[:, 0], t2[:, 0]])).astype(int)
    y0 = np.floor(np.minimum.reduce([t0[:, 1], t1[:, 1], t2[:, 1]])).astype(int)
    y1 = np.ceil(np.maximum.reduce([t0[:, 1], t1[:, 1], t2[:, 1]])).astype(int)
    ok &= (x1 >= 0) & (x0 < W) & (y1 >= 0) & (y0 < H)
    x0 = np.clip(x0, 0, W - 1); x1 = np.clip(x1, 0, W - 1); y0 = np.clip(y0, 0, H - 1); y1 = np.clip(y1, 0, H - 1)
    bw = x1 - x0 + 1; bh = y1 - y0 + 1; bs = np.maximum(bw, bh)
    z = np.full(W * H, np.inf)
    recs = []
    # triangles larger than max_px (after clipping) are the flat sea next to the camera: skipped as occluders, which
    # can only mark more vertices visible (conservative for pinning)
    for lo, hi in ((0, 4), (4, 8), (8, 16), (16, 32), (32, 64), (64, 128), (128, 256)):
        if lo >= max_px:
            break
        sel = np.nonzero(ok & (bs > lo) & (bs <= hi))[0]
        if not len(sel):
            continue
        n = hi
        chunk = max(1, int(2e6 // (n * n)))
        g = np.arange(n)
        for k in range(0, len(sel), chunk):
            s = sel[k:k + chunk]
            px = x0[s, None, None] + g[None, None, :]
            py = y0[s, None, None] + g[None, :, None]
            px = np.broadcast_to(px, (len(s), n, n)); py = np.broadcast_to(py, (len(s), n, n))
            inb = (px <= x1[s, None, None]) & (py <= y1[s, None, None])
            a_, b_, c_ = t0[s], t1[s], t2[s]
            den = (b_[:, 1] - c_[:, 1]) * (a_[:, 0] - c_[:, 0]) + (c_[:, 0] - b_[:, 0]) * (a_[:, 1] - c_[:, 1])
            good = np.abs(den) > 1e-12
            den = np.where(good, den, 1.0)[:, None, None]
            l0 = ((b_[:, 1] - c_[:, 1])[:, None, None] * (px - c_[:, 0, None, None]) + (c_[:, 0] - b_[:, 0])[:, None, None] * (py - c_[:, 1, None, None])) / den
            l1 = ((c_[:, 1] - a_[:, 1])[:, None, None] * (px - c_[:, 0, None, None]) + (a_[:, 0] - c_[:, 0])[:, None, None] * (py - c_[:, 1, None, None])) / den
            l2 = 1 - l0 - l1
            e = -1e-9
            inside = inb & good[:, None, None] & (l0 >= e) & (l1 >= e) & (l2 >= e)
            izs = l0 * iz[T[s, 0]][:, None, None] + l1 * iz[T[s, 1]][:, None, None] + l2 * iz[T[s, 2]][:, None, None]
            dep = 1.0 / np.maximum(izs, 1e-12)
            ti, yy_, xx_ = np.nonzero(inside)
            pix = py[ti, yy_, xx_] * W + px[ti, yy_, xx_]
            d = dep[ti, yy_, xx_]
            np.minimum.at(z, pix, d)
            if want_ids:
                recs.append((pix, d, s[ti]))
    ids = None
    if want_ids:
        ids = np.zeros(W * H, np.int64)
        for pix, d, tri in recs:
            m = d <= z[pix] + 1e-9
            ids[pix[m]] = tri[m] + 1
        ids = ids.reshape(H, W)
    return z.reshape(H, W), ids


def pinned_mask(c, A, Y, ss=2, dil_cols=1):
    """vertices of every triangle that is the first hit of at least one pixel (ss x display res), dilated along rows."""
    z, ids = zbuffer(c, A, Y, ss)
    T = tris()
    seen = np.unique(ids[ids > 0]) - 1
    vv = np.zeros(C.NU * C.NV, bool)
    vv[T[seen].ravel()] = True
    vv = vv.reshape(C.NV, C.NU)
    if dil_cols:
        v2 = vv.copy()
        for d in range(1, dil_cols + 1):
            v2[:, d:] |= vv[:, :-d]; v2[:, :-d] |= vv[:, d:]
        vv = v2
    return vv, z, ids
