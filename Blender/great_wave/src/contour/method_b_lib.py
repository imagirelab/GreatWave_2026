"""Method B (outline-based) base-contour extraction -- numpy-only building blocks.

Everything here is deterministic and works in continuous pixel coordinates of the painting
(origin top-left, x right, y down, pixel (i, j) has its centre at (i + 0.5, j + 0.5)).

Contents
--------
* feature maps            : luma, blueness D = B - R
* flood_fill              : 4-connected flood fill by vectorised run sweeps
* trace_cracks            : ordered inter-pixel boundary of a region (region on the LEFT of travel)
* edt_capped              : exact Euclidean distance transform, capped at a maximum radius
* opening                 : morphological opening with a disc (rolling ball from the body side)
* bilinear                : sub-pixel sampling
* refine_edge             : sub-pixel half-level edge localisation along the local normal
* arclength helpers, gaussian smoothing along arclength, uniform resampling, tangent angles
"""
import math

import numpy as np


# ------------------------------------------------------------------ feature maps
def luma(rgb):
    a = rgb.astype(np.float32)
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


def blueness(rgb):
    """D = B - R (float32).  sky: -50 .. -3, foam white: about -22, ink outline: +25 .. +45,
    dark blue fill: about +65 (values measured on the painting, see the record)."""
    a = rgb.astype(np.float32)
    return a[:, :, 2] - a[:, :, 0]


def box_blur(a, r):
    """(2r+1)^2 box mean with edge replication; r = 0 returns a."""
    if r <= 0:
        return a
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge").astype(np.float64)
    c = np.cumsum(p, axis=0)
    c = np.concatenate([np.zeros((1, c.shape[1])), c], axis=0)
    v = c[k:] - c[:-k]
    c = np.cumsum(v, axis=1)
    c = np.concatenate([np.zeros((c.shape[0], 1)), c], axis=1)
    h = c[:, k:] - c[:, :-k]
    return (h / float(k * k)).astype(np.float32)


def _running_extreme(a, k, axis, fn):
    """Running max / min over a centred window of k (odd) samples along `axis` (edge replicated)."""
    r = k // 2
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode="edge")
    n = a.shape[axis]
    out = None
    for s in range(k):
        sl = [slice(None), slice(None)]
        sl[axis] = slice(s, s + n)
        v = p[tuple(sl)]
        out = v.copy() if out is None else fn(out, v, out=out)
    return out


def grey_dilate(a, k):
    """Grey-scale dilation (running maximum) with a k x k square, k odd."""
    return _running_extreme(_running_extreme(a, k, 0, np.maximum), k, 1, np.maximum)


def grey_erode(a, k):
    """Grey-scale erosion (running minimum) with a k x k square, k odd."""
    return _running_extreme(_running_extreme(a, k, 0, np.minimum), k, 1, np.minimum)


def black_tophat(a, k):
    """closing(a) - a with a k x k square: response of DARK structures narrower than k px."""
    return grey_erode(grey_dilate(a, k), k) - a


# ------------------------------------------------------------------ flood fill
def _run_ids(mask):
    """Row-wise run ids of a boolean mask (h, w): pixels of the same horizontal run share an id.
    Returns (ids int64 (h, w) valid where mask, n_runs)."""
    h, w = mask.shape
    start = mask.copy()
    start[:, 1:] &= ~mask[:, :-1]
    ids = np.cumsum(start.ravel()).reshape(h, w) - 1
    return ids, int(start.sum())


def flood_fill(mask, seeds, max_iter=10000):
    """4-connected flood fill inside `mask` (bool) from `seeds` (list of (x, y) integer pixels).
    Vectorised: alternates row-run and column-run propagation until nothing changes.
    Returns (reached bool array, n_iterations)."""
    m = np.ascontiguousarray(mask.astype(bool))
    mt = np.ascontiguousarray(m.T)
    ids_r, n_r = _run_ids(m)
    ids_c, n_c = _run_ids(mt)
    reached = np.zeros_like(m)
    for (x, y) in seeds:
        if not m[y, x]:
            raise ValueError("flood_fill seed (%d, %d) is outside the mask" % (x, y))
        reached[y, x] = True
    count = int(reached.sum())
    it = 0
    while it < max_iter:
        it += 1
        hit = np.bincount(ids_r[m], weights=reached[m], minlength=n_r) > 0
        reached = m & hit[np.clip(ids_r, 0, max(n_r - 1, 0))]
        rt = np.ascontiguousarray(reached.T)
        hit = np.bincount(ids_c[mt], weights=rt[mt], minlength=n_c) > 0
        rt = mt & hit[np.clip(ids_c, 0, max(n_c - 1, 0))]
        reached = np.ascontiguousarray(rt.T)
        new_count = int(reached.sum())
        if new_count == count:
            break
        count = new_count
    return reached, it


def geodesic_dilate(seed, within, steps):
    """Grow `seed` inside `within` by `steps` pixel steps (alternating 4- and 8-neighbourhoods, an
    octagonal approximation of the Euclidean metric).  The growth never crosses pixels outside
    `within`, so thin ink lines are respected."""
    cur = seed & within
    for i in range(int(steps)):
        p = np.pad(cur, 1, mode="constant", constant_values=False)
        g = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
        if i % 2 == 1:
            g |= p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:]
        cur = g & within
    return cur


# ------------------------------------------------------------------ crack tracing
_DX = (1, 0, -1, 0)      # 0 = E, 1 = S, 2 = W, 3 = N   (image coords, y down)
_DY = (0, 1, 0, -1)


#: offset of the pixel on the LEFT of a crack step that starts at vertex (x, y) heading 0=E,1=S,2=W,3=N
LEFT_PIXEL = ((0, -1), (0, 0), (-1, 0), (-1, -1))


def crack_left_pixels(path):
    """For an (N, 2) crack path (unit steps) return the (N-1, 2) integer pixel coordinates of the
    pixel on the left of every step (the region side for a trace_cracks path)."""
    d = np.diff(path, axis=0)
    direction = np.where(d[:, 0] == 1, 0, np.where(d[:, 1] == 1, 1, np.where(d[:, 0] == -1, 2, 3)))
    off = np.asarray(LEFT_PIXEL, dtype=np.int64)[direction]
    return path[:-1] + off


def trace_cracks_open(region, start_vertex, start_dir, n_vertices):
    """Like trace_cracks but returns after n_vertices vertices (open path, no closing test)."""
    return trace_cracks(region, start_vertex, start_dir, max_steps=int(n_vertices), allow_open=True)


def trace_cracks(region, start_vertex, start_dir, max_steps=5_000_000, allow_open=False):
    """Follow the inter-pixel boundary (cracks) of `region` (bool (h, w)) keeping the region on the
    LEFT of the travel direction; the region is treated as 4-connected (diagonal contacts do not
    connect it).  Vertices are integer lattice points: vertex (x, y) is the top-left corner of
    pixel (x, y).  start_vertex / start_dir (0=E, 1=S, 2=W, 3=N) must describe a valid crack: the
    pixel on the left of the first step belongs to the region and the pixel on the right does not.
    Pixels outside the array count as NOT region.  Returns an (N, 2) int array of vertices of the
    closed loop (first vertex not repeated)."""
    h, w = region.shape
    reg = region

    def inside(px, py):
        return 0 <= px < w and 0 <= py < h and bool(reg[py, px])

    # pixels ahead-left / ahead-right of vertex (x, y) when heading in direction d
    # E: AL = (x, y-1), AR = (x, y);  S: AL = (x, y), AR = (x-1, y)
    # W: AL = (x-1, y), AR = (x-1, y-1);  N: AL = (x-1, y-1), AR = (x, y-1)
    AL = ((0, -1), (0, 0), (-1, 0), (-1, -1))
    AR = ((0, 0), (-1, 0), (-1, -1), (0, -1))
    x, y = int(start_vertex[0]), int(start_vertex[1])
    d = int(start_dir)
    if not (inside(x + AL[d][0], y + AL[d][1]) and not inside(x + AR[d][0], y + AR[d][1])):
        raise ValueError("trace_cracks: invalid start crack")
    out = []
    x0, y0, d0 = x, y, d
    for _ in range(max_steps):
        out.append((x, y))
        x += _DX[d]
        y += _DY[d]
        # choose the next direction at the new vertex
        al = inside(x + AL[d][0], y + AL[d][1])
        ar = inside(x + AR[d][0], y + AR[d][1])
        if not al:
            d = (d + 3) % 4          # turn left
        elif ar:
            d = (d + 1) % 4          # turn right
        if x == x0 and y == y0 and d == d0:
            break
    else:
        if not allow_open:
            raise RuntimeError("trace_cracks: boundary did not close within max_steps")
    return np.asarray(out, dtype=np.int64)


# ------------------------------------------------------------------ distance transform / opening
def edt_capped(mask, rmax):
    """Exact Euclidean distance (float32) from every True pixel of `mask` to the nearest False
    pixel (pixel-centre to pixel-centre), capped at rmax (values > rmax are returned as rmax + 1).
    False pixels get 0.  Pixels outside the array are treated as True (no border effect).
    Cost: (2*rmax + 1) vectorised passes."""
    m = mask.astype(bool)
    h, w = m.shape
    rmax = int(rmax)
    big = rmax + 1
    # 1-D distance along columns (vertical), capped
    g = np.full((h, w), big, np.int32)
    run = np.full(w, big, np.int32)
    for yy in range(h):                       # top -> bottom
        run = np.where(m[yy], np.minimum(run + 1, big), 0)
        g[yy] = run
    run = np.full(w, big, np.int32)
    for yy in range(h - 1, -1, -1):           # bottom -> top
        run = np.where(m[yy], np.minimum(run + 1, big), 0)
        g[yy] = np.minimum(g[yy], run)
    g2 = g.astype(np.float32) ** 2
    g2[g >= big] = np.float32(1e12)
    best = g2.copy()
    for dx in range(1, rmax + 1):
        add = np.float32(dx * dx)
        best[:, dx:] = np.minimum(best[:, dx:], g2[:, :-dx] + add)
        best[:, :-dx] = np.minimum(best[:, :-dx], g2[:, dx:] + add)
    d = np.sqrt(np.minimum(best, np.float32(big * big)))
    d[d > rmax] = big
    return d.astype(np.float32)


def opening(mask, radius):
    """Morphological opening of `mask` with a disc of the given radius (exact EDT based):
    union of all discs of that radius (centre-to-centre metric) that fit inside the mask."""
    r = float(radius)
    rcap = int(math.ceil(r)) + 1
    core = edt_capped(mask, rcap) > r            # erosion: centres whose disc fits
    back = edt_capped(~core, rcap) <= r          # dilation of the core
    return back & mask


# ------------------------------------------------------------------ sampling
def bilinear(a, x, y):
    """Sample array a (h, w) at continuous px coords (x, y) (pixel centres at +0.5)."""
    h, w = a.shape
    fx = np.clip(np.asarray(x, np.float64) - 0.5, 0, w - 1.000001)
    fy = np.clip(np.asarray(y, np.float64) - 0.5, 0, h - 1.000001)
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    tx = fx - x0
    ty = fy - y0
    v00 = a[y0, x0]
    v01 = a[y0, x0 + 1]
    v10 = a[y0 + 1, x0]
    v11 = a[y0 + 1, x0 + 1]
    return (v00 * (1 - tx) + v01 * tx) * (1 - ty) + (v10 * (1 - tx) + v11 * tx) * ty


# ------------------------------------------------------------------ polyline helpers
def arclength(p):
    d = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
    return np.concatenate([[0.0], np.cumsum(d)])


def resample_uniform(p, spacing, keep_end=True):
    """Resample polyline p (N, 2) at uniform arclength spacing (first point kept; the last point is
    appended when keep_end and it is not already hit).  Returns (M, 2) and the arclength of each
    output sample measured on the input polyline."""
    s = arclength(p)
    total = s[-1]
    n = int(math.floor(total / spacing + 1e-9))
    t = np.arange(n + 1) * spacing
    if keep_end and total - t[-1] > 1e-6:
        t = np.concatenate([t, [total]])
    out = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    return out, t


def resample_uniform_exact(p, spacing):
    """Resample so that the spacing is uniform AND both end points are kept exactly: the number of
    intervals is round(length / spacing), the actual spacing is length / n (within a fraction of
    a percent of the nominal spacing)."""
    s = arclength(p)
    total = s[-1]
    n = max(1, int(round(total / spacing)))
    t = np.linspace(0.0, total, n + 1)
    out = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    return out, t


def gaussian_smooth_open(p, sigma, spacing, fix_ends=True):
    """Gaussian smoothing of an OPEN polyline sampled at uniform `spacing` (sigma in px of
    arclength).  Ends are handled by point reflection (keeps end position and end tangent);
    with fix_ends the first / last point are restored exactly."""
    if sigma <= 0:
        return p.copy()
    sg = sigma / float(spacing)
    r = int(math.ceil(4 * sg))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2)
    k /= k.sum()
    n = len(p)
    r_eff = min(r, n - 1)
    head = 2 * p[0] - p[1:r_eff + 1][::-1]
    tail = 2 * p[-1] - p[-r_eff - 1:-1][::-1]
    ext = np.vstack([head, p, tail])
    if r_eff < r:
        k = k[r - r_eff:r + r_eff + 1]
        k /= k.sum()
    out = np.stack([np.convolve(ext[:, 0], k, mode="valid"),
                    np.convolve(ext[:, 1], k, mode="valid")], axis=1)
    if fix_ends:
        out[0] = p[0]
        out[-1] = p[-1]
    return out


def tangent_angles_deg(p):
    """Direction of each polyline segment, degrees, 0 = +x (right), +90 = up (y is down in px)."""
    d = np.diff(p, axis=0)
    return np.degrees(np.arctan2(-d[:, 1], d[:, 0]))


def wrap_deg(a):
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def s8_profile(p, spacing_px):
    """S8-style smoothness of a polyline: resample at `spacing_px`, tangent direction of each chord,
    absolute direction change between neighbouring chords.  Returns dict with the sample points,
    the per-vertex turn (deg, signed: + = turning left / counter-clockwise in X-Z) and the maximum."""
    q, _ = resample_uniform(p, spacing_px, keep_end=False)
    if len(q) < 3:
        return {"points": q, "turn_deg": np.zeros(0), "max_abs_deg": 0.0, "argmax_px": None}
    ang = tangent_angles_deg(q)
    turn = wrap_deg(np.diff(ang))
    i = int(np.argmax(np.abs(turn)))
    return {"points": q, "turn_deg": turn, "max_abs_deg": float(np.abs(turn).max()),
            "argmax_px": [float(q[i + 1, 0]), float(q[i + 1, 1])]}


def point_polyline_distance(pts, poly):
    """Distance from each point (N, 2) to the polyline poly (M, 2) (segments).  Returns (dist,
    index of the nearest segment, parameter t on it).  Vectorised in chunks."""
    a = poly[:-1]
    b = poly[1:]
    ab = b - a
    l2 = np.maximum((ab ** 2).sum(axis=1), 1e-12)
    dist = np.empty(len(pts))
    idx = np.empty(len(pts), np.int64)
    tt = np.empty(len(pts))
    chunk = max(1, int(4_000_000 // max(len(a), 1)))
    for i0 in range(0, len(pts), chunk):
        q = pts[i0:i0 + chunk]
        ap = q[:, None, :] - a[None, :, :]
        t = np.clip((ap * ab[None]).sum(axis=2) / l2[None], 0.0, 1.0)
        proj = a[None] + t[:, :, None] * ab[None]
        dd = np.hypot(q[:, None, 0] - proj[:, :, 0], q[:, None, 1] - proj[:, :, 1])
        j = dd.argmin(axis=1)
        r = np.arange(len(q))
        dist[i0:i0 + chunk] = dd[r, j]
        idx[i0:i0 + chunk] = j
        tt[i0:i0 + chunk] = t[r, j]
    return dist, idx, tt


# ------------------------------------------------------------------ sub-pixel edge refinement
def local_normals(p, half_window):
    """Unit normals of an ordered polyline (N, 2), from the chord p[i+hw] - p[i-hw].  The normal
    points to the RIGHT of the travel direction (for a sky-on-the-left trace: INTO the wave)."""
    n = len(p)
    i0 = np.clip(np.arange(n) - half_window, 0, n - 1)
    i1 = np.clip(np.arange(n) + half_window, 0, n - 1)
    t = p[i1] - p[i0]
    ln = np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)
    t = t / ln[:, None]
    # travel direction (tx, ty) in image coords (y down); right-hand side = (-ty, tx)
    return np.stack([-t[:, 1], t[:, 0]], axis=1), t


def refine_edge(field, p, normals, search=6.0, step=0.25, outer=(3.0, 7.0), inner_max=7.0,
                level=0.5, min_contrast=12.0):
    """Sub-pixel localisation of the sky -> wave edge on a scalar `field` that is LOW in the sky and
    HIGH on the ink / wave side.

    For every point p[i] the field is sampled along the normal (pointing into the wave) at offsets
    t in [-search - outer[1], +search + inner_max].  sky level  = median of the samples whose offset
    lies in [-outer[1], -outer[0]] relative to the first guess; wave level = maximum of the samples
    in [0, inner_max]; the edge is the first crossing (coming from the sky side) of
    sky + level * (wave - sky), linearly interpolated.  Points with contrast < min_contrast or
    without a crossing inside +-search keep their position and are flagged not-ok.
    Returns (refined (N, 2), ok bool (N,), shift (N,) signed px along the normal, contrast (N,))."""
    t = np.arange(-(search + outer[1]), search + inner_max + 1e-9, step)
    xs = p[:, 0][:, None] + normals[:, 0][:, None] * t[None, :]
    ys = p[:, 1][:, None] + normals[:, 1][:, None] * t[None, :]
    prof = bilinear(field, xs, ys)                                   # (N, T)
    sel_o = (t >= -outer[1]) & (t <= -outer[0])
    sky = np.median(prof[:, sel_o], axis=1)
    sel_i = (t >= 0.0) & (t <= inner_max)
    wave = prof[:, sel_i].max(axis=1)
    contrast = wave - sky
    thr = sky + level * contrast
    above = prof >= thr[:, None]
    sel_s = (t >= -search) & (t <= search)
    # first index inside the search window where the profile is above the threshold while the
    # previous sample is below
    cross = above[:, 1:] & ~above[:, :-1] & sel_s[None, 1:]
    has = cross.any(axis=1)
    j = np.argmax(cross, axis=1) + 1
    r = np.arange(len(p))
    v0 = prof[r, j - 1]
    v1 = prof[r, j]
    frac = np.where(np.abs(v1 - v0) > 1e-9, (thr - v0) / np.where(np.abs(v1 - v0) > 1e-9, v1 - v0, 1.0), 0.5)
    shift = t[j - 1] + frac * step
    ok = has & (contrast >= min_contrast)
    shift = np.where(ok, shift, 0.0)
    out = p + normals * shift[:, None]
    return out, ok, shift, contrast
