# -*- coding: utf-8 -*-
"""Q20 candidate B: section-level geometry tools (numpy/scipy/cv2 only).

- painting lock: which K* vertices define the PaintingCam silhouette (their image lies within LOCK_PX of the K* sky
  boundary); those vertices are kept; everything else may move while its image stays inside the K* silhouette
  (eroded by a margin), so the painting gate does not move.
- back / crest / lip / tube / foot curve builders (heading-angle integration, arc-length resampling).
"""
import math
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter1d
from candB_common import *

LOCK_PX = 2.5

_M = {}


def silhouette_masks():
    if "M0" not in _M:
        cov = np.load(os.path.join(WORK, "cov_kstar.npy")) if os.path.isfile(os.path.join(WORK, "cov_kstar.npy")) else coverage(*load_kstar())
        yh = horizon_y()
        M = (cov > 0.5)
        M[int(math.ceil(yh)):] = True
        _M["M0"] = M.astype(np.uint8)
        _M["yh"] = yh
        _M["din"] = cv2.distanceTransform(_M["M0"], cv2.DIST_L2, 5)
    return _M


def inside_px(P):
    """P: world (...,3). Return the inside distance (px) of the image point in the K* silhouette (0 = outside)."""
    m = silhouette_masks()
    Q = project(P)
    x = np.round(Q[..., 0]).astype(int); y = np.round(Q[..., 1]).astype(int)
    ok = (x >= 0) & (x < 1920) & (y >= 0) & (y < 1080)
    d = np.zeros(x.shape, np.float32)
    d[ok] = m["din"][y[ok], x[ok]]
    # off-frame (outside the display) counts as free: the painting does not see it
    d[~ok] = 1e3
    return d


def row_inside(a, y, c, margin=2.0):
    P = O[None, :] + a[:, None] * T + y[:, None] * UP + c * E
    return inside_px(P) >= margin


def kstar_lock(A, Y, c):
    m = silhouette_masks()
    d = inside_px(world(A, Y, c))
    return (d <= LOCK_PX) & (Y > 0.5)


def clamp_row(a, y, a_ref, y_ref, c, margin=2.0, n=24):
    """move every vertex whose image leaves the (eroded) silhouette back toward its reference position (assumed inside)."""
    a = a.copy(); y = y.copy()
    bad = ~row_inside(a, y, c, margin)
    if not bad.any():
        return a, y, 0
    idx = np.nonzero(bad)[0]
    ts = np.linspace(1.0, 0.0, n + 1)
    best = np.zeros(len(idx))
    for k, t in enumerate(ts):
        aa = a_ref[idx] + t * (a[idx] - a_ref[idx]); yy = y_ref[idx] + t * (y[idx] - y_ref[idx])
        ok = row_inside(aa, yy, c, margin)
        upd = ok & (best == 0)
        best[upd] = t if t > 0 else 1e-9
    best[best == 0] = 0.0
    a[idx] = a_ref[idx] + best * (a[idx] - a_ref[idx]); y[idx] = y_ref[idx] + best * (y[idx] - y_ref[idx])
    return a, y, len(idx)


# ------------------------------------------------------------------ polyline tools
def resample(P, n):
    s = arclen(P[:, 0], P[:, 1])
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], -1)


def resample_w(P, n, w=None):
    """arc-length resampling with an optional density weight (per input vertex, >0)."""
    s = arclen(P[:, 0], P[:, 1])
    if w is None:
        u = s
    else:
        ds = np.diff(s) * 0.5 * (w[1:] + w[:-1]); u = np.r_[0, np.cumsum(ds)]
    t = np.linspace(0, u[-1], n)
    return np.stack([np.interp(t, u, P[:, 0]), np.interp(t, u, P[:, 1])], -1)


def heading_curve(p0, th_deg, ds):
    """integrate a curve from p0 with headings th_deg (deg, measured from +a, CCW) sampled at arc steps ds."""
    th = np.radians(th_deg)
    d = np.stack([np.cos(th), np.sin(th)], -1) * ds
    return p0[None, :] + np.r_[np.zeros((1, 2)), np.cumsum(0.5 * (d[1:] + d[:-1]), 0)]


def fair(a, y, fixed, iters=200, lam_=0.5):
    """Laplacian fairing with fixed vertices (keeps end points)."""
    a = a.copy(); y = y.copy()
    fx = fixed.copy(); fx[0] = fx[-1] = True
    for _ in range(iters):
        la = 0.5 * (a[:-2] + a[2:]) - a[1:-1]; ly = 0.5 * (y[:-2] + y[2:]) - y[1:-1]
        m = ~fx[1:-1]
        a[1:-1][m] += lam_ * la[m]; y[1:-1][m] += lam_ * ly[m]
    return a, y


def fair2(a, y, fixed, iters=300, lam_=0.25):
    """bi-Laplacian (curvature-smoothing) fairing with fixed vertices: removes kinks while keeping G2 near locks."""
    a = a.copy(); y = y.copy()
    fx = fixed.copy(); fx[:2] = True; fx[-2:] = True
    for _ in range(iters):
        for v in (a, y):
            L = np.zeros_like(v); L[1:-1] = 0.5 * (v[:-2] + v[2:]) - v[1:-1]
            LL = np.zeros_like(v); LL[1:-1] = 0.5 * (L[:-2] + L[2:]) - L[1:-1]
            v[~fx] -= lam_ * LL[~fx]
    return a, y


def turn_deg(a, y):
    v = np.stack([np.diff(a), np.diff(y)], -1)
    h = np.unwrap(np.arctan2(v[:, 1], v[:, 0]))
    return np.degrees(np.diff(h))


def ahead_rows(c, cfrom, cto, lo, hi):
    return [r for r in range(len(c)) if cfrom <= c[r] <= cto]


def capped_fair(a, y, a0, y0, cap, iters=400, lam_=0.2, keep=None):
    """bi-Laplacian fairing; every vertex stays within cap[j] (m) of its reference (a0, y0)[j]; keep[j] = fixed."""
    a = a.copy(); y = y.copy()
    fx = np.zeros(len(a), bool) if keep is None else keep.copy()
    fx[:2] = True; fx[-2:] = True
    for _ in range(iters):
        for v in (a, y):
            L = np.zeros_like(v); L[1:-1] = 0.5 * (v[:-2] + v[2:]) - v[1:-1]
            LL = np.zeros_like(v); LL[1:-1] = 0.5 * (L[:-2] + L[2:]) - L[1:-1]
            v[~fx] -= lam_ * LL[~fx]
        da = a - a0; dy = y - y0; dd = np.hypot(da, dy)
        s = np.where(dd > cap, cap / np.maximum(dd, 1e-12), 1.0)
        a = a0 + da * s; y = y0 + dy * s
    return a, y


def clamp_row_dir(a, y, c, free, margin=1.0, direction=(0.0, -1.0), step=0.01, maxd=8.0):
    """move free vertices whose image is outside the silhouette along `direction` (per-vertex (n,2) or one vector)
    until inside. Returns a, y, number moved."""
    a = a.copy(); y = y.copy()
    bad = free & ~row_inside(a, y, c, margin)
    idx = np.nonzero(bad)[0]
    if len(idx) == 0:
        return a, y, 0
    d = np.asarray(direction, float)
    d = np.broadcast_to(d, (len(a), 2))[idx]
    done = np.zeros(len(idx), bool)
    for k in range(1, int(maxd / step) + 1):
        aa = a[idx] + d[:, 0] * k * step; yy = y[idx] + d[:, 1] * k * step
        ok = row_inside(aa, yy, c, margin) & ~done
        a[idx[ok]] = aa[ok]; y[idx[ok]] = yy[ok]; done |= ok
        if done.all():
            break
    return a, y, int(len(idx))


def sanitize(a, y, keep=None, iters=50, cos_min=-0.2):
    """remove U-turns / reversals along a row polyline: a free vertex whose incoming and outgoing segments point in
    opposite directions (cos < cos_min) is moved to the midpoint of its neighbours."""
    a = a.copy(); y = y.copy()
    kp = np.zeros(len(a), bool) if keep is None else keep
    for _ in range(iters):
        d1 = np.stack([a[1:-1] - a[:-2], y[1:-1] - y[:-2]], -1); d2 = np.stack([a[2:] - a[1:-1], y[2:] - y[1:-1]], -1)
        n1 = np.linalg.norm(d1, axis=1); n2 = np.linalg.norm(d2, axis=1)
        cs = (d1 * d2).sum(1) / np.maximum(n1 * n2, 1e-12)
        bad = np.nonzero((cs < cos_min) & ~kp[1:-1])[0] + 1
        if len(bad) == 0:
            break
        a[bad] = 0.5 * (a[bad - 1] + a[bad + 1]); y[bad] = 0.5 * (y[bad - 1] + y[bad + 1])
    return a, y


def remove_tip_loops(a, y, j0=170, j1=240, keep=None, iters=10):
    """a small loop where the lip top and the underside cross near the tip: the vertices inside the loop are put
    on a short straight path through the crossing point (the tip becomes that point)."""
    a = a.copy(); y = y.copy()
    kp = np.zeros(len(a), bool) if keep is None else keep
    for _ in range(iters):
        P = np.stack([a, y], -1); hit = None
        for i in range(j0, j1):
            p, r = P[i], P[i + 1] - P[i]
            for j in range(i + 2, j1):
                q, s_ = P[j], P[j + 1] - P[j]
                den = r[0] * s_[1] - r[1] * s_[0]
                if abs(den) < 1e-14:
                    continue
                t = ((q - p)[0] * s_[1] - (q - p)[1] * s_[0]) / den; u = ((q - p)[0] * r[1] - (q - p)[1] * r[0]) / den
                if 0 < t < 1 and 0 < u < 1:
                    hit = (i, j, p + t * r); break
            if hit:
                break
        if not hit:
            break
        i, j, X = hit
        n = j - i
        Pa, Pb = P[i], P[j + 1]
        for k in range(1, n + 1):
            idx = i + k
            if kp[idx]:
                continue
            w = k / (n + 1)
            # the loop is cut: its vertices go onto the straight path P[i] -> X -> P[j+1]
            if w <= 0.5:
                q = Pa + (w / 0.5) * (X - Pa)
            else:
                q = X + ((w - 0.5) / 0.5) * (Pb - X)
            a[idx], y[idx] = q
    return a, y
