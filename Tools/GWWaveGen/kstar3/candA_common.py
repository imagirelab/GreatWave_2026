# -*- coding: utf-8 -*-
"""Q20 candidate A (K*' secondary design from the reference model's large forms): shared frame, IO and geometry helpers.

Frame = K* 26修正01 section frame (Unity world, left-handed, Y up, still water y = 0):
  a = along travel t (+ = lip side), y = height, c = along the crest e (- = camera-side near shoulder).
Nothing here reads the reference-model OBJ; the model enters only through the TEMP cache (candA_refcache.py).
"""
import os, sys, json, math
import numpy as np

REPO = r"G:\Unity\GreatWave_2026_Fresh"
KSTAR_DIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar")
KSTAR_GWB = os.path.join(KSTAR_DIR, "kstar_a45.gwb")
KSTAR_ROWS = os.path.join(KSTAR_DIR, "kstar_a45_rows.npz")
KSTAR_META = os.path.join(KSTAR_DIR, "kstar_a45_meta.json")
OUT_DIR = os.path.join(REPO, "Unity", "Build", "Q20", "candA")
TMP_DIR = os.path.join(OUT_DIR, "_tmp")
REF_CACHE = os.path.join(TMP_DIR, "ref_cache.npz")
RUBRIC_TOOLS = os.path.join(REPO, "Unity", "Build", "Q20", "rubric", "tools")

E = np.array([0.6798348938056157, 0.0, 0.733365200404483])
T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
UP = np.array([0.0, 1.0, 0.0])
H0_KSTAR = 20.752853190871733
SEAT = np.array([3.9544, 1.8323, -15.0308])
CAM_POS = np.array([0.0, 3.0, -62.0])
NU, NV = 400, 240
LM = {"j_B": 18, "j_top": 90, "j_tip": 200, "j_corner": 314, "j_facebot": 379, "j_E": 394}
MAIN_ROW = 159


def sec(P):
    """world -> (a, y, c)"""
    Q = np.atleast_2d(P) - O
    return np.c_[Q @ T, Q[:, 1], Q @ E]


def world(c, A, Y):
    """rows (nv,), A/Y (nv, nu) -> (nv, nu, 3) world"""
    return O[None, None, :] + A[..., None] * T + Y[..., None] * UP + np.asarray(c)[:, None, None] * E


def load_kstar_rows():
    z = np.load(KSTAR_ROWS)
    return z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)


def read_gwb(path):
    b = open(path, "rb").read()
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4")
    ntri = int(np.frombuffer(b[28:32], "<i4")[0]); n = int(nu) * int(nv)
    o = 32
    uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy(); o += n * 8
    uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy(); o += n * 8
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    hdr = b[:32]
    return dict(nu=int(nu), nv=int(nv), uv=uv, uv2=uv2, tris=tris, X=X, header=hdr)


def write_gwb(path, nu, nv, uv, uv2, tris, X):
    import struct
    with open(path, "wb") as fo:
        fo.write(b"GWW0" + struct.pack("<iiiifii", 1, nu, nv, 1, 30.0, 0, len(tris)))
        for arr in (uv.astype(np.float32), uv2.astype(np.float32), tris.astype(np.int32), X.reshape(-1, 3).astype(np.float32)):
            fo.write(np.ascontiguousarray(arr).tobytes())


def load_ref_cache(path=REF_CACHE):
    z = np.load(path)
    return z["V"].astype(np.float64), z["tris"]


# ---------------------------------------------------------------- mesh slicing on c planes
def slice_mesh(S, tris, c0, tri_sel=None):
    """segments (k, 2, 2) in (a, y) where the plane c = c0 cuts the triangles.  S = section coords of vertices."""
    tt = tris if tri_sel is None else tris[tri_sel]
    d = S[:, 2] - c0
    dt = d[tt]
    s = np.sign(dt); s[s == 0] = 1
    cut = ~((s[:, 0] == s[:, 1]) & (s[:, 1] == s[:, 2]))
    tr = tt[cut]; dt = dt[cut]
    P = S[tr][:, :, :2]
    pts = []; ms = []
    for (i, j) in ((0, 1), (1, 2), (2, 0)):
        si, sj = np.sign(dt[:, i]), np.sign(dt[:, j])
        si[si == 0] = 1; sj[sj == 0] = 1
        m = si != sj
        t = dt[:, i] / np.where(m, dt[:, i] - dt[:, j], 1.0)
        pts.append(P[:, i] + t[:, None] * (P[:, j] - P[:, i])); ms.append(m)
    ms = np.stack(ms, 1); pts = np.stack(pts, 1)       # (k, 3), (k, 3, 2)
    two = ms.sum(1) >= 2
    first = np.argmax(ms, 1)
    ms2 = ms.copy(); ms2[np.arange(len(ms)), first] = False
    second = np.argmax(ms2, 1)
    k = np.arange(len(ms))
    seg = np.stack([pts[k, first], pts[k, second]], 1)[two]
    return seg


def rasterize_segments(segs, a0, a1, y0, y1, res):
    """even-odd fill of the closed section loops on a grid (rows = y ascending, cols = a ascending)."""
    na = int(round((a1 - a0) / res)) + 1; ny = int(round((y1 - y0) / res)) + 1
    img = np.zeros((ny, na), np.uint8)
    ya = segs[:, 0, 1]; yb = segs[:, 1, 1]; xa = segs[:, 0, 0]; xb = segs[:, 1, 0]
    lo = np.minimum(ya, yb); hi = np.maximum(ya, yb)
    order = np.argsort(lo)
    for iy in range(ny):
        yv = y0 + iy * res + 1e-7
        m = (lo <= yv) & (hi > yv)
        if not m.any():
            continue
        t = (yv - ya[m]) / (yb[m] - ya[m])
        xs = np.sort(xa[m] + t * (xb[m] - xa[m]))
        for k in range(0, len(xs) - 1, 2):
            i0 = int(math.ceil((xs[k] - a0) / res)); i1 = int(math.floor((xs[k + 1] - a0) / res))
            if i1 >= i0:
                img[iy, max(i0, 0):min(i1 + 1, na)] = 1
    return img


def arclen(a, y):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]


def resample_poly(P, n=None, step=None):
    s = arclen(P[:, 0], P[:, 1])
    if n is None:
        n = max(int(round(s[-1] / step)) + 1, 2)
    ss = np.linspace(0, s[-1], n)
    return np.stack([np.interp(ss, s, P[:, 0]), np.interp(ss, s, P[:, 1])], -1)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def gauss1d_nonuniform(v, x, sigma):
    """Gaussian smoothing of samples v at (possibly non-uniform) positions x, sigma in the units of x."""
    W = np.exp(-0.5 * ((x[:, None] - x[None, :]) / sigma) ** 2)
    W /= W.sum(1, keepdims=True)
    return W @ v


def painting_frame():
    """V1.Target / V1.Frame of 26修正01 (for projections and the gate)."""
    sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth")); sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen"))
    import truthlib as TL
    import gw_wavegen_v1 as V1
    params = TL.load_json(os.path.join(REPO, "Tools", "GWWaveGen", "params_v2_af26r01.json"))
    tgt = V1.Target(); fr = V1.Frame(tgt.spec, float(params["alpha_deg"]), params["anchor"], tgt)
    return V1, tgt, fr
