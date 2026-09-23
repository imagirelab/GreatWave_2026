"""Exact, deterministic numpy rasteriser + binary-mask utilities (numpy only, no bpy).

Rasteriser
----------
`rasterize_triangles` fills the UNION ('any coverage') of 2-D triangles given in
continuous pixel coordinates (same convention as gw.frame / gw.draw: origin top-left,
x right, y down, pixel (i, j) has its centre at (i + 0.5, j + 0.5)).

Coverage rule: a pixel is set when its CENTRE lies inside or exactly on the border of
at least one triangle (closed triangles).  Shared edges therefore never leave cracks.
The implementation is a vectorised scan-conversion:

  * every triangle is expanded into one 'span' per pixel row whose centre line
    y = j + 0.5 crosses it;
  * the span [xl, xr] is the min / max of the intersections of that line with the
    (non-horizontal) edges.  The intersection is always evaluated from the lower-y
    end point of the edge (canonical order), so two triangles that share an edge get
    bit-identical x values for it -> no cracks from rounding, independent of winding;
  * spans are accumulated in a (h, w+1) difference image, one cumsum gives the mask.

The cost is O(number of spans) = O(sum of triangle heights in px), NOT O(bbox area),
so thin slivers and huge triangles are both cheap.  Triangles are processed in chunks
to bound memory.  Degenerate / edge-on triangles (zero projected area) cover no pixel
centre and are skipped without warnings; with thin='line' they (and slivers thinner
than `thin_px`) are additionally drawn as 1-px lines so that an exactly edge-on sheet
becomes visible (this DILATES the silhouette by up to ~0.5 px, so it is off by default).

Mask utilities
--------------
Run-length based connected-component labelling (vectorised union-find), largest
component, hole filling / hole report.  Foreground uses 8-connectivity, background
4-connectivity (the usual dual pair), everywhere in this project.
"""
import numpy as np

__all__ = [
    "rasterize_triangles", "rasterize_exact", "EdgeData", "fill_below", "Components", "label_components",
    "largest_component", "fill_holes", "hole_report", "brute_force_mask",
]


# ====================================================================== rasteriser
def _as_tri_px(tri_px):
    t = np.asarray(tri_px, dtype=np.float64)
    if t.ndim != 3 or t.shape[1:] != (3, 2):
        raise ValueError("tri_px must have shape (N, 3, 2), got %r" % (t.shape,))
    return t


def rasterize_triangles(tri_px, width, height, thin="skip", thin_px=1.0, eps=1e-9,
                        max_spans=2_000_000, out=None, return_info=False, _edge_store=None):
    """Union of triangles -> bool mask (height, width).

    tri_px   : (N, 3, 2) float array, continuous px coords (x right, y down).
    thin     : 'skip' (default) -> exact pixel-centre coverage only.
               'line' -> triangles whose height over their longest edge is < thin_px
               (this includes exactly degenerate / edge-on ones) are ALSO drawn as a
               1-px line along their longest edge.
    eps      : tolerance in px for 'centre exactly on the border' (inclusive rule).
    out      : optional existing bool mask (height, width) that is OR-ed into.
    Non-finite triangles are ignored (counted in info['n_nonfinite']).
    (_edge_store is internal: see rasterize_exact.)
    """
    w, h = int(width), int(height)
    if w <= 0 or h <= 0:
        raise ValueError("width and height must be positive")
    tri = _as_tri_px(tri_px)
    info = {"n_triangles": int(tri.shape[0]), "n_spans": 0, "n_chunks": 0,
            "n_nonfinite": 0, "n_thin_lines": 0, "n_zero_area": 0}
    finite = np.isfinite(tri).all(axis=(1, 2))
    info["n_nonfinite"] = int((~finite).sum())
    if not finite.all():
        tri = tri[finite]

    diff = np.zeros(h * (w + 1), dtype=np.int32)
    if _edge_store is not None:
        _edge_store["hi"] = np.full(h * w, -np.inf, np.float32)
        _edge_store["lo"] = np.full(h * w, np.inf, np.float32)
        _edge_store["sliver"] = []
    if tri.shape[0]:
        x = tri[:, :, 0]
        y = tri[:, :, 1]
        ymin = y.min(axis=1)
        ymax = y.max(axis=1)
        xmin = x.min(axis=1)
        xmax = x.max(axis=1)
        area2 = np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
        info["n_zero_area"] = int((area2 == 0).sum())
        # rows whose centre line crosses the triangle: j + 0.5 in [ymin, ymax]
        j0 = np.ceil(ymin - 0.5 - eps)
        j1 = np.floor(ymax - 0.5 + eps)
        j0 = np.clip(j0, 0, h).astype(np.int64)
        j1 = np.clip(j1, -1, h - 1).astype(np.int64)
        cnt = j1 - j0 + 1
        cnt[(cnt < 0) | (xmax < 0.5 - eps) | (xmin > w - 0.5 + eps)] = 0
        keep = np.nonzero(cnt > 0)[0]
        if keep.size:
            cnt_k = cnt[keep]
            csum = np.cumsum(cnt_k)
            total = int(csum[-1])
            info["n_spans"] = total
            # chunk boundaries so that each chunk has about max_spans spans
            n_chunks = max(1, int(np.ceil(total / float(max_spans))))
            bounds = np.searchsorted(csum, np.arange(1, n_chunks) * (total / float(n_chunks)), side="left")
            bounds = np.unique(np.concatenate([[0], bounds + 1, [keep.size]]))
            info["n_chunks"] = int(len(bounds) - 1)
            for a, b in zip(bounds[:-1], bounds[1:]):
                _accumulate_spans(diff, x[keep[a:b]], y[keep[a:b]], j0[keep[a:b]], cnt_k[a:b], w, h, eps,
                                  _edge_store)
    mask = np.cumsum(diff.reshape(h, w + 1)[:, :w], axis=1, dtype=np.int32) > 0
    del diff
    if _edge_store is not None:
        _edge_store["hi"] = _edge_store["hi"].reshape(h, w)
        _edge_store["lo"] = _edge_store["lo"].reshape(h, w)
        sl = _edge_store["sliver"]
        if sl:
            key = np.concatenate([s[0] for s in sl])
            lo = np.concatenate([s[1] for s in sl])
            hi = np.concatenate([s[2] for s in sl])
            order = np.lexsort((lo, key))
            _edge_store["sliver"] = (key[order], lo[order], hi[order])
        else:
            _edge_store["sliver"] = (np.zeros(0, np.int64), np.zeros(0, np.float32), np.zeros(0, np.float32))

    if thin == "line" and tri.shape[0]:
        n_lines = _draw_thin_lines(mask, tri, float(thin_px))
        info["n_thin_lines"] = int(n_lines)
    elif thin not in ("skip", "line"):
        raise ValueError("thin must be 'skip' or 'line'")

    if out is not None:
        if out.shape != mask.shape:
            raise ValueError("out has shape %r, expected %r" % (out.shape, mask.shape))
        np.logical_or(out, mask, out=out)
        mask = out
    return (mask, info) if return_info else mask


def _accumulate_spans(diff, x, y, j0, cnt, w, h, eps, edge_store=None):
    """Add the spans of the triangles (x, y: (n, 3)) to the flat difference image.
    edge_store (optional): also record, per (row, pixel), the largest right end of the spans
    whose last covered pixel it is ('hi'), the smallest left end of the spans whose first
    covered pixel it is ('lo'), and the 'sliver' spans that cover no pixel centre."""
    n = x.shape[0]
    total = int(cnt.sum())
    t = np.repeat(np.arange(n, dtype=np.int64), cnt)
    first = np.cumsum(cnt) - cnt
    rows = j0[t] + (np.arange(total, dtype=np.int64) - first[t])
    yc = rows.astype(np.float64) + 0.5
    xl = np.full(total, np.inf)
    xr = np.full(total, -np.inf)
    for ia, ib in ((0, 1), (1, 2), (2, 0)):
        xa, ya, xb, yb = x[:, ia], y[:, ia], x[:, ib], y[:, ib]
        swap = ya > yb                      # canonical order: lower y first
        xa, xb = np.where(swap, xb, xa), np.where(swap, xa, xb)
        ya, yb = np.where(swap, yb, ya), np.where(swap, ya, yb)
        dy = yb - ya
        inv = np.zeros_like(dy)
        np.divide(1.0, dy, out=inv, where=dy > 0)
        ya_t = ya[t]
        valid = (dy[t] > 0) & (yc >= ya_t - eps) & (yc <= yb[t] + eps)
        tt = np.clip((yc - ya_t) * inv[t], 0.0, 1.0)
        xa_t = xa[t]
        xe = xa_t + tt * (xb[t] - xa_t)
        xl = np.where(valid & (xe < xl), xe, xl)
        xr = np.where(valid & (xe > xr), xe, xr)
    fin = np.isfinite(xl) & np.isfinite(xr)
    # pixel centres i + 0.5 in [xl, xr]
    i0r = np.ceil(np.where(fin, xl, 0.0) - 0.5 - eps)
    i1r = np.floor(np.where(fin, xr, -1.0) - 0.5 + eps)
    i0 = np.clip(i0r, 0, w).astype(np.int64)
    i1 = np.clip(i1r, -1, w - 1).astype(np.int64)
    ok = fin & (i0 <= i1)
    if edge_store is not None:
        # spans that cover no centre but lie inside the frame, in the gap right of pixel g
        sl = fin & (i0r > i1r) & (xr > xl) & (i1r >= -1) & (i1r <= w - 1)
        if sl.any():
            g = i1r[sl].astype(np.int64)
            edge_store["sliver"].append((rows[sl] * (w + 2) + (g + 1), xl[sl].astype(np.float32),
                                         xr[sl].astype(np.float32)))
    if not ok.any():
        return
    rows = rows[ok]
    i0, i1 = i0[ok], i1[ok]
    base = rows * (w + 1)
    diff += np.bincount(base + i0, minlength=diff.size).astype(np.int32)
    diff -= np.bincount(base + i1 + 1, minlength=diff.size).astype(np.int32)
    if edge_store is not None:
        b2 = rows * w
        np.maximum.at(edge_store["hi"], b2 + i1, xr[ok].astype(np.float32))
        np.minimum.at(edge_store["lo"], b2 + i0, xl[ok].astype(np.float32))


def _draw_thin_lines(mask, tri, thin_px):
    """Mark the longest edge of thin / degenerate triangles as a 1-px line (in place)."""
    h, w = mask.shape
    x = tri[:, :, 0]
    y = tri[:, :, 1]
    area2 = np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
    e = np.stack([np.hypot(x[:, 1] - x[:, 0], y[:, 1] - y[:, 0]),
                  np.hypot(x[:, 2] - x[:, 1], y[:, 2] - y[:, 1]),
                  np.hypot(x[:, 0] - x[:, 2], y[:, 0] - y[:, 2])], axis=1)
    longest = e.max(axis=1)
    height_over_longest = np.where(longest > 0, area2 / np.where(longest > 0, longest, 1.0), 0.0)
    sel = np.nonzero(height_over_longest < thin_px)[0]
    if sel.size == 0:
        return 0
    k = e[sel].argmax(axis=1)
    ia = k
    ib = (k + 1) % 3
    ax, ay = x[sel, ia], y[sel, ia]
    bx, by = x[sel, ib], y[sel, ib]
    # cull lines completely outside the frame
    vis = ~((np.maximum(ax, bx) < 0) | (np.minimum(ax, bx) > w) | (np.maximum(ay, by) < 0) | (np.minimum(ay, by) > h))
    ax, ay, bx, by = ax[vis], ay[vis], bx[vis], by[vis]
    if ax.size == 0:
        return 0
    L = np.hypot(bx - ax, by - ay)
    ns = np.maximum(1, np.ceil(L / 0.5).astype(np.int64)) + 1      # samples every <= 0.5 px
    chunk = 200_000
    for s in range(0, ax.size, chunk):
        sl = slice(s, s + chunk)
        n_s = ns[sl]
        tot = int(n_s.sum())
        t = np.repeat(np.arange(n_s.size), n_s)
        first = np.cumsum(n_s) - n_s
        f = (np.arange(tot) - first[t]) / np.maximum(n_s[t] - 1, 1)
        px = ax[sl][t] + f * (bx[sl][t] - ax[sl][t])
        py = ay[sl][t] + f * (by[sl][t] - ay[sl][t])
        ix = np.floor(px).astype(np.int64)
        iy = np.floor(py).astype(np.int64)
        ok = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
        mask[iy[ok], ix[ok]] = True
    return int(ax.size)


def fill_below(mask, y_px):
    """Set every pixel whose centre is at or below the horizontal line y = y_px
    (continuous px, y down), in place.  Used for the 'water slab'.  Returns the mask."""
    h = mask.shape[0]
    j = int(np.clip(np.ceil(float(y_px) - 0.5 - 1e-9), 0, h))
    mask[j:, :] = True
    return mask


class EdgeData:
    """Exact positions where the silhouette boundary crosses the grid lines through the pixel
    centres (result of rasterize_exact).  With them the boundary between an inside and an
    outside pixel is known to float precision instead of +-0.5 px.

      x_hi[j, i] : largest right end (x) of the row-j spans whose last covered centre is pixel i
      x_lo[j, i] : smallest left end of the row-j spans whose first covered centre is pixel i
      y_hi[j, i] : largest bottom end (y) of the column-i spans whose last covered centre is row j
      y_lo[j, i] : smallest top end of the column-i spans whose first covered centre is row j
    'Sliver' spans that cover no centre are kept separately and chained on when they touch.
    """

    def __init__(self, shape, row_store, col_store):
        self.shape = shape
        h, w = shape
        self.x_hi, self.x_lo = row_store["hi"], row_store["lo"]
        self.y_hi, self.y_lo = col_store["hi"].T, col_store["lo"].T
        self._sl_row = row_store["sliver"]           # key = row * (w + 2) + (gap + 1)
        self._sl_col = col_store["sliver"]           # key = col * (h + 2) + (gap + 1)

    @staticmethod
    def _chain(sl, key, start, grow_up, tol=1e-4):
        keys, lo, hi = sl
        a = np.searchsorted(keys, key, side="left")
        b = np.searchsorted(keys, key, side="right")
        if b <= a:
            return start
        reach = float(start)
        if grow_up:                                   # extend a right / bottom end upwards
            for k in range(a, b):                     # sorted by lo
                if lo[k] <= reach + tol and hi[k] > reach:
                    reach = float(hi[k])
        else:                                         # extend a left / top end downwards
            for k in sorted(range(a, b), key=lambda q: -hi[q]):
                if hi[k] >= reach - tol and lo[k] < reach:
                    reach = float(lo[k])
        return reach

    def crossing(self, kind, j, i):
        """Exact boundary coordinate next to inside pixel (row j, column i).
        kind: 'right' (x of the boundary right of the pixel), 'left', 'bottom' (y below), 'top'.
        Returns NaN when nothing was recorded (pixel was not covered by a triangle)."""
        h, w = self.shape
        if kind == "right":
            v = float(self.x_hi[j, i])
            return self._chain(self._sl_row, j * (w + 2) + (i + 1), v, True) if np.isfinite(v) else np.nan
        if kind == "left":
            v = float(self.x_lo[j, i])
            return self._chain(self._sl_row, j * (w + 2) + i, v, False) if np.isfinite(v) else np.nan
        if kind == "bottom":
            v = float(self.y_hi[j, i])
            return self._chain(self._sl_col, i * (h + 2) + (j + 1), v, True) if np.isfinite(v) else np.nan
        if kind == "top":
            v = float(self.y_lo[j, i])
            return self._chain(self._sl_col, i * (h + 2) + j, v, False) if np.isfinite(v) else np.nan
        raise ValueError(kind)


def rasterize_exact(tri_px, width, height, thin="skip", thin_px=1.0, eps=1e-9, max_spans=2_000_000):
    """rasterize_triangles + EdgeData (two scan passes: rows, then columns).
    -> (mask, EdgeData, info).  Costs about twice the time and 4 float32 images of memory."""
    tri = _as_tri_px(tri_px)
    row_store, col_store = {}, {}
    mask, info = rasterize_triangles(tri, width, height, thin, thin_px, eps, max_spans,
                                     return_info=True, _edge_store=row_store)
    mask_t, info_t = rasterize_triangles(tri[:, :, ::-1], height, width, "skip", thin_px, eps, max_spans,
                                         return_info=True, _edge_store=col_store)
    info["n_spans_columns"] = info_t["n_spans"]
    if thin == "skip":
        info["row_col_mask_disagree_px"] = int((mask != mask_t.T).sum())
    return mask, EdgeData((int(height), int(width)), row_store, col_store), info


def brute_force_mask(tri_px, width, height, eps=1e-9):
    """Reference implementation (slow, O(N * w * h)): closed-triangle pixel-centre test
    with edge functions.  Only for tests with few triangles / small images."""
    tri = _as_tri_px(tri_px)
    w, h = int(width), int(height)
    xs = (np.arange(w) + 0.5)[None, :]
    ys = (np.arange(h) + 0.5)[:, None]
    mask = np.zeros((h, w), bool)
    for a, b, c in tri:
        if not np.isfinite([a, b, c]).all():
            continue
        area = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if area == 0:
            continue
        s = 1.0 if area > 0 else -1.0
        scale = max(abs(area), 1e-300) ** 0.5
        tol = eps * scale
        e0 = s * ((b[0] - a[0]) * (ys - a[1]) - (b[1] - a[1]) * (xs - a[0]))
        e1 = s * ((c[0] - b[0]) * (ys - b[1]) - (c[1] - b[1]) * (xs - b[0]))
        e2 = s * ((a[0] - c[0]) * (ys - c[1]) - (a[1] - c[1]) * (xs - c[0]))
        mask |= (e0 >= -tol) & (e1 >= -tol) & (e2 >= -tol)
    return mask


# ====================================================================== components
class Components:
    """Result of label_components(): run-length representation of a labelled mask.

    Attributes (numpy arrays over runs; a run is [start, end) in one row):
      row, start, end, label      label is 0 .. n-1 (components sorted by first run)
    Per component (length n): area, touches_border, bbox (n, 4) = x0, y0, x1, y1 (exclusive)
    """

    def __init__(self, shape, row, start, end, label, n):
        self.shape = (int(shape[0]), int(shape[1]))
        self.row, self.start, self.end, self.label = row, start, end, label
        self.n = int(n)
        h, w = self.shape
        ln = (end - start).astype(np.int64)
        self.area = np.bincount(label, weights=ln, minlength=n).astype(np.int64) if n else np.zeros(0, np.int64)
        tb = (row == 0) | (row == h - 1) | (start == 0) | (end == w)
        self.touches_border = np.bincount(label, weights=tb, minlength=n) > 0 if n else np.zeros(0, bool)
        bbox = np.zeros((n, 4), np.int64)
        if n:
            bbox[:, 0] = w
            bbox[:, 1] = h
            np.minimum.at(bbox[:, 0], label, start)
            np.minimum.at(bbox[:, 1], label, row)
            np.maximum.at(bbox[:, 2], label, end)
            np.maximum.at(bbox[:, 3], label, row + 1)
        self.bbox = bbox

    def mask_of(self, labels):
        """bool mask of the union of the given component labels (int or iterable)."""
        h, w = self.shape
        sel = np.isin(self.label, np.atleast_1d(labels))
        diff = np.zeros(h * (w + 1), np.int32)
        base = self.row[sel] * (w + 1)
        np.add.at(diff, base + self.start[sel], 1)
        np.add.at(diff, base + self.end[sel], -1)
        return np.cumsum(diff.reshape(h, w + 1)[:, :w], axis=1, dtype=np.int32) > 0

    def label_image(self):
        """int32 image: 0 = not in mask, k + 1 = component k."""
        h, w = self.shape
        diff = np.zeros(h * (w + 1), np.int64)
        base = self.row * (w + 1)
        np.add.at(diff, base + self.start, self.label + 1)
        np.add.at(diff, base + self.end, -(self.label + 1))
        return np.cumsum(diff.reshape(h, w + 1)[:, :w], axis=1).astype(np.int32)


def _runs(mask):
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    p = np.zeros((h, w + 2), np.int8)
    p[:, 1:-1] = m
    d = np.diff(p, axis=1)                       # (h, w+1): +1 at run start, -1 at run end
    rs, cs = np.nonzero(d == 1)
    re, ce = np.nonzero(d == -1)
    return rs.astype(np.int64), cs.astype(np.int64), ce.astype(np.int64)


def label_components(mask, connectivity=8):
    """Connected components of a bool mask (connectivity 4 or 8) -> Components."""
    if connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8")
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    row, start, end = _runs(m)
    n_runs = row.size
    if n_runs == 0:
        return Components((h, w), row, start, end, np.zeros(0, np.int64), 0)
    K = w + 2
    key_s = row * K + start
    key_e = row * K + end
    prev = (row - 1) * K
    if connectivity == 4:      # overlap: s_a < e_b  and  e_a > s_b
        first = np.searchsorted(key_e, prev + start, side="right")
        last = np.searchsorted(key_s, prev + end, side="left") - 1
    else:                      # 8: s_a <= e_b  and  e_a >= s_b
        first = np.searchsorted(key_e, prev + start, side="left")
        last = np.searchsorted(key_s, prev + end, side="right") - 1
    cnt = np.maximum(last - first + 1, 0)
    cnt[row == 0] = 0
    # a candidate must really be in the previous row (guards the row-0 / key edge cases)
    b = np.repeat(np.arange(n_runs, dtype=np.int64), cnt)
    off = np.arange(int(cnt.sum()), dtype=np.int64) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    a = first[b] + off
    good = row[a] == row[b] - 1
    a, b = a[good], b[good]

    parent = np.arange(n_runs, dtype=np.int64)
    while True:
        pa, pb = parent[a], parent[b]
        lo = np.minimum(pa, pb)
        hi = np.maximum(pa, pb)
        ch = lo != hi
        if not ch.any():
            break
        np.minimum.at(parent, hi[ch], lo[ch])
        while True:                              # pointer jumping
            pp = parent[parent]
            if np.array_equal(pp, parent):
                break
            parent = pp
    roots, label = np.unique(parent, return_inverse=True)
    return Components((h, w), row, start, end, label.astype(np.int64), roots.size)


def largest_component(mask, connectivity=8, speck_max_area_px=None, max_listed=20):
    """-> (bool mask of the largest component, info dict).

    Everything that is NOT the largest component is REMOVED from the returned mask, and never silently:
      n_components, largest_area_px, largest_bbox, second_largest_area_px   (as before)
      removed_area_px          total area of all removed components
      n_removed                number of removed components (= n_components - 1)
      speck_max_area_px        the limit used below (None = no classification asked for)
      n_removed_specks / removed_specks_area_px     removed components with area <  speck_max_area_px
      n_removed_islands / removed_islands_area_px   removed components with area >= speck_max_area_px
                               (without a limit EVERY removed component counts as an island)
      removed                  list of the `max_listed` largest removed components, largest first:
                               {'area_px', 'bbox_px' [x0, y0, x1, y1) (exclusive), 'kind' 'speck' | 'island'}
      removed_list_truncated   True when there are more removed components than listed
    A 'speck' is rasterisation dust (a few pixels); an 'island' is a real detached piece of geometry (spray, a second
    object, a part of the mesh that is not connected to the wave AS SEEN in the mask).  The caller decides what to do
    with islands; this function only reports them."""
    comp = label_components(mask, connectivity)
    lim = None if speck_max_area_px is None else float(speck_max_area_px)
    if comp.n == 0:
        return np.zeros(comp.shape, bool), {"n_components": 0, "largest_area_px": 0, "removed_area_px": 0,
                                           "second_largest_area_px": 0, "n_removed": 0, "speck_max_area_px": lim,
                                           "n_removed_specks": 0, "removed_specks_area_px": 0, "n_removed_islands": 0,
                                           "removed_islands_area_px": 0, "removed": [], "removed_list_truncated": False}
    k = int(comp.area.argmax())
    areas = np.sort(comp.area)[::-1]
    info = {"n_components": int(comp.n), "largest_area_px": int(areas[0]),
            "second_largest_area_px": int(areas[1]) if comp.n > 1 else 0,
            "removed_area_px": int(areas[1:].sum()), "largest_bbox": [int(v) for v in comp.bbox[k]]}
    others = np.array([i for i in range(comp.n) if i != k], dtype=np.int64)
    a_o = comp.area[others] if others.size else np.zeros(0, np.int64)
    is_speck = (a_o < lim) if lim is not None else np.zeros(a_o.size, bool)
    order = np.argsort(-a_o, kind="stable")
    info.update({"n_removed": int(others.size), "speck_max_area_px": lim,
                 "n_removed_specks": int(is_speck.sum()), "removed_specks_area_px": int(a_o[is_speck].sum()),
                 "n_removed_islands": int((~is_speck).sum()), "removed_islands_area_px": int(a_o[~is_speck].sum()),
                 "removed": [{"area_px": int(a_o[i]), "bbox_px": [int(v) for v in comp.bbox[others[i]]],
                              "kind": "speck" if is_speck[i] else "island"} for i in order[:int(max_listed)]],
                 "removed_list_truncated": bool(others.size > int(max_listed))})
    return comp.mask_of(k), info


def fill_holes(mask, sky="top"):
    """Fill background regions that are not part of the 'sky' (4-connectivity).

    sky = 'top'    : sky = background components that touch the TOP image border (default; right
                     for silhouettes with a water slab: an un-swept region under the surface
                     that happens to touch the left / right frame edge is still a hole).
    sky = 'border' : sky = background components that touch any image border.
    -> (filled mask, holes mask, info).  info: n_holes, hole_area_px, largest_hole_area_px,
    largest_hole_bbox [x0, y0, x1, y1), holes (list of up to 10 largest: area, bbox)."""
    m = np.asarray(mask, dtype=bool)
    comp = label_components(~m, connectivity=4)
    if comp.n == 0:
        hole_ids = np.zeros(0, np.int64)
    elif sky == "top":
        touches_top = np.bincount(comp.label, weights=(comp.row == 0), minlength=comp.n) > 0
        hole_ids = np.nonzero(~touches_top)[0]
    elif sky == "border":
        hole_ids = np.nonzero(~comp.touches_border)[0]
    else:
        raise ValueError("sky must be 'top' or 'border'")
    info = {"n_holes": int(hole_ids.size), "hole_area_px": 0, "largest_hole_area_px": 0,
            "largest_hole_bbox": None, "holes": []}
    if hole_ids.size == 0:
        return m.copy(), np.zeros_like(m), info
    holes = comp.mask_of(hole_ids)
    areas = comp.area[hole_ids]
    order = np.argsort(areas)[::-1]
    info["hole_area_px"] = int(areas.sum())
    info["largest_hole_area_px"] = int(areas[order[0]])
    info["largest_hole_bbox"] = [int(v) for v in comp.bbox[hole_ids[order[0]]]]
    info["holes"] = [{"area_px": int(areas[i]), "bbox": [int(v) for v in comp.bbox[hole_ids[i]]]}
                     for i in order[:10]]
    return m | holes, holes, info


def hole_report(mask, sky="top"):
    """Un-filled interior holes of a silhouette mask (see fill_holes) plus the fraction of
    the filled silhouette they make up.  A solid silhouette has n_holes == 0."""
    filled, _holes, info = fill_holes(mask, sky)
    tot = int(filled.sum())
    info["filled_area_px"] = tot
    info["hole_area_frac"] = float(info["hole_area_px"]) / tot if tot else 0.0
    return info
