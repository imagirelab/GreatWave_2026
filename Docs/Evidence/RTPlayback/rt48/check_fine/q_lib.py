# -*- coding: utf-8 -*-
"""Shared helpers for the independent check of the RT48 fine source (written from scratch; does not import project tools).
Coordinates: x_rel = x_scene - XP (distance from the wave paddle); X_bake = x_rel - 527; heights above each source's own still level."""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import json
import numpy as np
from skimage import measure
from scipy.spatial import cKDTree

ROOT = "G:/Unity/GreatWave_2026_Fresh"
R3 = ROOT + "/Unity/Build/FLIP42/runs/R3"
RE = ROOT + "/Unity/Build/RT48/rerun/R3e"
FINE = RE + "/fine"
DATA = ROOT + "/Unity/Build/RT48/data"
XP = 135.46329754326246     # paddle x in the scene (R3 cfg x_p)
OFF_R3 = 0.116838239133358  # R3 still-level offset (FLIP42 R3 shape.json)
X0B = 527.0
FPS = 24.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def t_of(f):
    return (f - 1) / FPS


def still_offset_fine():
    m = json.load(open(FINE + "/meta.json", encoding="utf8"))
    return float(m["still_offset_m"])


def load_phi(f):
    z = np.load(FINE + "/phi_%04d.npz" % f)
    phi = z["phi"].astype(np.float64)
    xs = float(z["x0_rel"]) + float(z["dx"]) * np.arange(phi.shape[1])
    ys_abs = float(z["y0_abs"]) + float(z["dy"]) * np.arange(phi.shape[0])
    return phi, xs, ys_abs


_sec_cache = {}


def _sec_files():
    if "idx" not in _sec_cache:
        import glob
        idx = {}
        for fn in sorted(glob.glob(R3 + "/sec_c*_b*.npz")):
            z = np.load(fn)
            for i, f in enumerate(z["frames"]):
                idx[int(f)] = (fn, i)   # any record is fine: C1(a)/(b) show they are byte-identical
        _sec_cache["idx"] = idx
    return _sec_cache["idx"]


def load_sec(f):
    fn, i = _sec_files()[f]
    if _sec_cache.get("fn") != fn:
        z = np.load(fn)
        _sec_cache["fn"] = fn
        _sec_cache["arr"] = z["sdf"]
        _sec_cache["meta"] = json.loads(str(z["meta"]))
    m = _sec_cache["meta"]
    S = _sec_cache["arr"][i].astype(np.float64)
    xs = m["x0"] + m["dx"] * np.arange(m["nx"]) - XP
    ys_abs = m["y0"] + m["dy"] * np.arange(m["ny"])
    return S, xs, ys_abs


_hf_cache = {}


def load_hf(f):
    import glob
    if "idx" not in _hf_cache:
        idx = {}
        for fn in sorted(glob.glob(R3 + "/hf_c*.npz")):
            z = np.load(fn)
            for i, ff in enumerate(z["frames"]):
                idx[int(ff)] = (fn, i)
        _hf_cache["idx"] = idx
    fn, i = _hf_cache["idx"][f]
    if _hf_cache.get("fn") != fn:
        z = np.load(fn)
        _hf_cache["fn"] = fn
        _hf_cache["eta"] = z["eta"]
        _hf_cache["x"] = z["x"]
        _hf_cache["z"] = z["z"]
    iz = int(np.argmin(np.abs(_hf_cache["z"])))
    return _hf_cache["eta"][i, iz].astype(np.float64), _hf_cache["x"] - XP


def contours(F, xs, ys):
    """0-level contours of field F (rows=y, cols=x) in physical coords; returns list of (N,2) arrays and closed flags."""
    out = []
    for c in measure.find_contours(F, 0.0):
        P = np.stack([xs[0] + c[:, 1] * (xs[1] - xs[0]), ys[0] + c[:, 0] * (ys[1] - ys[0])], 1)
        closed = bool(np.allclose(c[0], c[-1]))
        out.append((P, closed))
    return out


def main_curve(F, xs, ys):
    """the open contour with the largest x extent, oriented so x increases from start to end overall."""
    cs = [P for P, cl in contours(F, xs, ys) if not cl]
    ext = [P[:, 0].max() - P[:, 0].min() for P in cs]
    P = cs[int(np.argmax(ext))]
    if P[0, 0] > P[-1, 0]:
        P = P[::-1]
    return P


def closed_loops(F, xs, ys):
    """closed contours: list of (P, phase, area); phase -1 water blob, +1 enclosed air, 0 undecided."""
    res = []
    for P, cl in contours(F, xs, ys):
        if not cl:
            continue
        ph, _ = loop_phase(P, F, xs, ys)
        res.append((P, ph, poly_area(P)))
    return res


def poly_area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def point_in_poly(px, py, P):
    """even-odd test, vectorised over points (px,py) for polygon P (closed or not)."""
    x = P[:, 0]; y = P[:, 1]
    x2 = np.roll(x, -1); y2 = np.roll(y, -1)
    inside = np.zeros(len(px), bool)
    for i in range(len(x)):
        c = ((y[i] > py) != (y2[i] > py))
        if not c.any():
            continue
        xint = x[i] + (py - y[i]) * (x2[i] - x[i]) / (y2[i] - y[i] + 1e-300)
        inside ^= c & (px < xint)
    return inside


def loop_phase(P, F, xs, ys):
    """+1 air enclosed (field > 0 inside), -1 water blob (field < 0 inside), 0 undecided; by majority of grid nodes inside."""
    x0, x1 = P[:, 0].min(), P[:, 0].max(); y0, y1 = P[:, 1].min(), P[:, 1].max()
    i0 = max(int(np.ceil((x0 - xs[0]) / (xs[1] - xs[0]))), 0); i1 = min(int(np.floor((x1 - xs[0]) / (xs[1] - xs[0]))), len(xs) - 1)
    j0 = max(int(np.ceil((y0 - ys[0]) / (ys[1] - ys[0]))), 0); j1 = min(int(np.floor((y1 - ys[0]) / (ys[1] - ys[0]))), len(ys) - 1)
    if i1 < i0 or j1 < j0:
        # no node inside: use the mean of the values at the corner nodes of the edges (sign of field at centroid by bilinear)
        cx, cy = P[:, 0].mean(), P[:, 1].mean()
        v = bilinear(F, xs, ys, np.array([cx]), np.array([cy]))[0]
        return (1 if v > 0 else -1 if v < 0 else 0), 0
    II, JJ = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
    px = xs[II.ravel()]; py = ys[JJ.ravel()]
    ins = point_in_poly(px, py, P)
    if not ins.any():
        cx, cy = P[:, 0].mean(), P[:, 1].mean()
        v = bilinear(F, xs, ys, np.array([cx]), np.array([cy]))[0]
        return (1 if v > 0 else -1 if v < 0 else 0), 0
    vals = F[JJ.ravel()[ins], II.ravel()[ins]]
    npos = int((vals > 0).sum()); nneg = int((vals < 0).sum())
    return (1 if npos > nneg else -1 if nneg > npos else 0), int(ins.sum())


def bilinear(F, xs, ys, X, Y):
    fx = (X - xs[0]) / (xs[1] - xs[0]); fy = (Y - ys[0]) / (ys[1] - ys[0])
    i = np.clip(np.floor(fx).astype(int), 0, len(xs) - 2); j = np.clip(np.floor(fy).astype(int), 0, len(ys) - 2)
    u = fx - i; v = fy - j
    return (F[j, i] * (1 - u) * (1 - v) + F[j, i + 1] * u * (1 - v) + F[j + 1, i] * (1 - u) * v + F[j + 1, i + 1] * u * v)


def arclen(P):
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])


def resample_n(P, n):
    s = arclen(P)
    q = np.linspace(0, s[-1], n)
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], 1)


def resample_step(P, h):
    s = arclen(P)
    n = max(int(np.ceil(s[-1] / h)) + 1, 2)
    return resample_n(P, n)


def densify(P, h):
    """insert points so no segment is longer than h (keeps original vertices)."""
    d = P[1:] - P[:-1]
    L = np.hypot(d[:, 0], d[:, 1])
    m = np.maximum(np.ceil(L / h).astype(int), 1)
    seg = np.repeat(np.arange(len(d)), m)
    start = np.concatenate([[0], np.cumsum(m)[:-1]])
    k = np.arange(m.sum()) - np.repeat(start, m) + 1
    t = (k / m[seg])[:, None]
    return np.concatenate([P[:1], P[seg] + d[seg] * t])


def seg_dist(Pts, Q, tree=None, k=8):
    """distance from each point in Pts to polyline Q (exact point-to-segment, candidate segments from k nearest vertices)."""
    if tree is None:
        tree = cKDTree(Q)
    kk = min(k, len(Q))
    _, idx = tree.query(Pts, k=kk)
    if kk == 1:
        idx = idx[:, None]
    best = np.full(len(Pts), np.inf)
    for c in range(kk):
        for off in (-1, 0):
            i0 = np.clip(idx[:, c] + off, 0, len(Q) - 2)
            a = Q[i0]; b = Q[i0 + 1]
            ab = b - a
            L2 = (ab ** 2).sum(1)
            t = np.where(L2 > 0, ((Pts - a) * ab).sum(1) / np.where(L2 > 0, L2, 1), 0.0)
            t = np.clip(t, 0, 1)
            d = np.hypot(*(Pts - (a + ab * t[:, None])).T)
            best = np.minimum(best, d)
    return best


def top_height(F, ys):
    """per column: height of the topmost water->air crossing (linear), and number of sign changes."""
    neg = F < 0
    ny = F.shape[0]
    # highest water node index per column
    rev = neg[::-1]
    has = neg.any(0)
    jtop = ny - 1 - np.argmax(rev, 0)
    h = np.full(F.shape[1], np.nan)
    ok = has & (jtop < ny - 1)
    c = np.where(ok)[0]
    j = jtop[c]
    a = F[j, c]; b = F[j + 1, c]
    h[c] = ys[j] + (ys[1] - ys[0]) * a / (a - b)
    nchg = (np.diff(np.sign(np.where(F == 0, 1e-12, F)), axis=0) != 0).sum(0)
    return h, nchg


def track_crest(get_main, frames, start_x, search=40.0):
    """crest = highest point of the main curve within +-search of the previous crest."""
    out = {}
    xc = start_x
    for f in frames:
        P = get_main(f)
        m = np.abs(P[:, 0] - xc) <= search
        i = np.where(m)[0][int(np.argmax(P[m, 1]))]
        xc = float(P[i, 0])
        out[f] = (xc, float(P[i, 1]))
    return out
