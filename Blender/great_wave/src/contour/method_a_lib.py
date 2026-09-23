"""Method A (region based) helpers for the base contour: numpy-only image morphology,
connected components, crack-following boundary tracing and polyline tools.

All masks are bool arrays (rows top-to-bottom).  All point coordinates are CONTINUOUS
pixel coordinates of gw.frame (pixel (i, j) covers [i, i+1] x [j, j+1]); a boundary
traced by `trace_cracks` runs on the integer corner lattice of that system.

No scipy / cv2 here: the Euclidean distance transform is an exact 'capped' EDT
(1-D row distance + a min-plus pass over +-cap rows), good for radii up to ~100 px.
"""
import math

import numpy as np


# ------------------------------------------------------------------ distance / morphology
def edt_capped(mask, cap, pad_mode="edge"):
    """Exact Euclidean distance (pixel-centre to pixel-centre) from every True pixel to
    the nearest False pixel, capped: values > cap are returned as cap + 1.
    False pixels get 0.  The image is padded by replicating its border (pad_mode='edge')
    so that a region touching the frame is treated as continuing beyond the frame."""
    m = np.asarray(mask, dtype=bool)
    cap = int(cap)
    big = cap + 1
    p = cap + 2
    mp = np.pad(m, p, mode=pad_mode) if pad_mode == "edge" else np.pad(m, p, mode="constant", constant_values=False)
    h, w = mp.shape
    idx = np.arange(w, dtype=np.int32)[None, :]
    far = np.int32(10 ** 7)
    left = np.where(mp, -far, idx)
    np.maximum.accumulate(left, axis=1, out=left)
    right = np.where(mp, far, idx)
    right = np.minimum.accumulate(right[:, ::-1], axis=1)[:, ::-1]
    g = np.minimum(idx - left, right - idx)
    np.minimum(g, big, out=g)
    g2 = (g.astype(np.float32)) ** 2
    d2 = g2.copy()
    lim = float(big * big)
    for dy in range(1, big + 1):
        c = float(dy * dy)
        if c >= lim:
            break
        np.minimum(d2[dy:], g2[:-dy] + c, out=d2[dy:])
        np.minimum(d2[:-dy], g2[dy:] + c, out=d2[:-dy])
    np.minimum(d2, lim, out=d2)
    d = np.sqrt(d2)
    return d[p:-p, p:-p]


def erode_disc(mask, r):
    """Erosion by a disc of radius r (pixels whose distance to the background is > r)."""
    if r <= 0:
        return np.asarray(mask, dtype=bool).copy()
    return edt_capped(mask, int(math.ceil(r)) + 1) > r


def dilate_disc(mask, r):
    """Dilation by a disc of radius r (pixels within distance <= r of the mask)."""
    if r <= 0:
        return np.asarray(mask, dtype=bool).copy()
    return ~(edt_capped(~np.asarray(mask, dtype=bool), int(math.ceil(r)) + 1) > r)


def open_disc(mask, r):
    return dilate_disc(erode_disc(mask, r), r)


def close_disc(mask, r):
    return erode_disc(dilate_disc(mask, r), r)


# ------------------------------------------------------------------ connected components
def label_components(mask):
    """4-connected components of a bool mask.  Returns (labels int32 (0 = background), n).
    Run based: row runs are the graph nodes, vertical overlaps the edges; components by
    min-label hooking + pointer jumping (all vectorised)."""
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    start = m.copy()
    start[:, 1:] &= ~m[:, :-1]
    rid = np.cumsum(start.ravel(), dtype=np.int64).reshape(h, w)
    rid[~m] = 0
    n = int(rid.max())
    if n == 0:
        return np.zeros((h, w), np.int32), 0
    sel = m[:-1] & m[1:] & (start[:-1] | start[1:])
    a = rid[:-1][sel]
    b = rid[1:][sel]
    parent = np.arange(n + 1, dtype=np.int64)
    for _ in range(10000):
        pa = parent[a]
        pb = parent[b]
        diff = pa != pb
        if not diff.any():
            break
        pa, pb = pa[diff], pb[diff]
        mn = np.minimum(pa, pb)
        np.minimum.at(parent, pa, mn)
        np.minimum.at(parent, pb, mn)
        while True:
            pp = parent[parent]
            if np.array_equal(pp, parent):
                break
            parent = pp
    roots, inv = np.unique(parent, return_inverse=True)
    # root 0 is the background (rid 0 -> parent 0)
    lab_of_run = inv.astype(np.int32)
    if roots[0] != 0:
        lab_of_run = lab_of_run + 1
    labels = lab_of_run[rid]
    return labels, int(labels.max())


def components_touching(mask, seeds_xy):
    """Union of the 4-connected components of `mask` that contain one of the seed pixels
    (x, y).  Seeds that fall on False pixels are reported in the second return value."""
    labels, _ = label_components(mask)
    keep, missed = set(), []
    for (x, y) in seeds_xy:
        l = int(labels[int(y), int(x)])
        if l == 0:
            missed.append((int(x), int(y)))
        else:
            keep.add(l)
    if not keep:
        return np.zeros_like(mask, dtype=bool), missed
    lut = np.zeros(int(labels.max()) + 1, bool)
    lut[list(keep)] = True
    return lut[labels], missed


def box_mean(a, k):
    """Mean over a (2k+1) x (2k+1) box, edge replicated.  a: 2-D float array."""
    a = np.asarray(a, dtype=np.float32)
    if k <= 0:
        return a.copy()
    n = 2 * k + 1
    p = np.pad(a, k, mode="edge").astype(np.float64)
    c = np.cumsum(p, axis=0)
    c = np.concatenate([np.zeros((1, c.shape[1])), c], axis=0)
    r = c[n:] - c[:-n]
    c = np.cumsum(r, axis=1)
    c = np.concatenate([np.zeros((c.shape[0], 1)), c], axis=1)
    r = c[:, n:] - c[:, :-n]
    return (r / float(n * n)).astype(np.float32)


# ------------------------------------------------------------------ boundary tracing
_DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))     # E, S, W, N in image coords (y down); +1 = right turn


def _pix(mask, x, y, outside):
    h, w = mask.shape
    if x < 0 or y < 0 or x >= w or y >= h:
        return outside(x, y)
    return bool(mask[y, x])


def trace_cracks(mask, start_vertex, start_dir, stop_fn, max_steps=2000000, outside=None):
    """Follow the crack (pixel edge) boundary of `mask` with the mask (body) on the RIGHT
    hand side and the background on the LEFT (image coords, y down), body 8-connected.
    start_vertex: integer corner (x, y); start_dir: index into E,S,W,N.
    stop_fn(x, y, n) -> True stops.  outside(x, y) gives the mask value outside the array
    (default: False).  Returns an (N, 2) int array of corner vertices."""
    if outside is None:
        outside = lambda x, y: False
    x, y = int(start_vertex[0]), int(start_vertex[1])
    d = int(start_dir)
    pts = [(x, y)]
    for n in range(max_steps):
        dx, dy = _DIRS[d]
        # pixels ahead of the vertex: front-left and front-right w.r.t. the direction
        if d == 0:      # E: front pixels have x, rows y-1 (left = north) and y (right = south)
            fl, fr = (x, y - 1), (x, y)
        elif d == 1:    # S: left = east
            fl, fr = (x, y), (x - 1, y)
        elif d == 2:    # W: left = south
            fl, fr = (x - 1, y), (x - 1, y - 1)
        else:           # N: left = west
            fl, fr = (x - 1, y - 1), (x, y - 1)
        bl = _pix(mask, fl[0], fl[1], outside)
        br = _pix(mask, fr[0], fr[1], outside)
        if bl:
            d = (d + 3) % 4          # turn left
        elif br:
            pass                      # straight
        else:
            d = (d + 1) % 4          # turn right
        dx, dy = _DIRS[d]
        x, y = x + dx, y + dy
        pts.append((x, y))
        if stop_fn(x, y, n):
            break
    return np.array(pts, dtype=np.int64)


# ------------------------------------------------------------------ polylines
def arclength(pts):
    p = np.asarray(pts, dtype=np.float64)
    seg = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
    return np.concatenate([[0.0], np.cumsum(seg)])


def resample(pts, spacing, s=None, return_s=False):
    """Uniform arclength resampling (linear interpolation); always keeps both end points.
    The spacing is adjusted slightly so that the samples are exactly uniform."""
    p = np.asarray(pts, dtype=np.float64)
    s = arclength(p) if s is None else s
    total = s[-1]
    n = max(1, int(round(total / spacing)))
    t = np.linspace(0.0, total, n + 1)
    out = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    return (out, t) if return_s else out


def interp_at(pts, s, t):
    p = np.asarray(pts, dtype=np.float64)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)


def gaussian_smooth(values, sigma, step=1.0):
    """Gaussian smoothing of an (N, k) or (N,) sequence sampled at uniform `step`.
    End handling: the sequence is extended by point reflection about its end points
    (keeps end positions and end tangents, no shrinkage at the ends)."""
    v = np.asarray(values, dtype=np.float64)
    one_d = v.ndim == 1
    if one_d:
        v = v[:, None]
    if sigma <= 0:
        return v[:, 0].copy() if one_d else v.copy()
    sg = sigma / float(step)
    r = int(math.ceil(4.0 * sg))
    r = min(r, len(v) - 1)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2)
    k /= k.sum()
    head = 2.0 * v[0] - v[1:r + 1][::-1]
    tail = 2.0 * v[-1] - v[-r - 1:-1][::-1]
    ext = np.concatenate([head, v, tail], axis=0)
    out = np.stack([np.convolve(ext[:, c], k, mode="valid") for c in range(v.shape[1])], axis=1)
    return out[:, 0] if one_d else out


def tangent_angles(pts):
    """Direction (deg, gw.frame convention: 0 = +X right, +90 = up) of the central-difference
    tangent at every point of a polyline given in pixel coords."""
    p = np.asarray(pts, dtype=np.float64)
    d = np.gradient(p, axis=0)
    return np.degrees(np.arctan2(-d[:, 1], d[:, 0]))


def angle_diff_deg(a, b):
    """Smallest signed difference a - b in degrees."""
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def point_to_polyline_dist(q, pts):
    """Distance from each query point (M, 2) to the polyline pts (N, 2) (segment exact).
    Chunked, O(M * N)."""
    q = np.atleast_2d(np.asarray(q, dtype=np.float64))
    p = np.asarray(pts, dtype=np.float64)
    a, b = p[:-1], p[1:]
    ab = b - a
    l2 = np.maximum((ab ** 2).sum(1), 1e-12)
    out = np.empty(len(q))
    step = max(1, int(4000000 // max(1, len(a))))
    for i in range(0, len(q), step):
        qq = q[i:i + step]
        t = ((qq[:, None, :] - a[None]) * ab[None]).sum(2) / l2[None]
        t = np.clip(t, 0.0, 1.0)
        c = a[None] + t[:, :, None] * ab[None]
        out[i:i + step] = np.sqrt(((qq[:, None, :] - c) ** 2).sum(2)).min(1)
    return out
