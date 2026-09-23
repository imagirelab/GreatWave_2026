"""Method B (outline-based) base-contour pipeline.  See docs/records/step1_contour_b.md.

Stages
------
A  ink mask (blueness + luma black top-hat)  ->  gap-closed sky region  (boundaries, not fills:
   the sky region is only the vehicle that gives the ORDER of the outline's outer edge)
B  raw silhouette WITH claws: ordered inter-pixel boundary of the sky region
C  rolling ball from the body side (opening, radius R): claws = protrusions narrower than 2R;
   opened boundary vertices are 'traced' (on the raw outline) or bridges across claw bases;
   bridges are replaced by chords between the claw-root points
D  sub-pixel refinement of traced points: outer edge of the ink outline along the local normal
E  smoothing (traced: sigma 3 px, bridges: sigma 10 px), landmarks, inner-arc end, completion to
   Z = 0, segmentation, uniform 2 px resampling
"""
import math

import numpy as np

from . import method_b_lib as L

TRACED, BRIDGE, COMPLETED_OCCLUDED, COMPLETED_OTHER = 0, 1, 2, 3
SOURCE_NAMES = {TRACED: "traced", BRIDGE: "claw_root_bridge",
                COMPLETED_OCCLUDED: "completed_occluded", COMPLETED_OTHER: "completed_other"}


def P(cfg, name):
    return cfg[name]["value"]


# ------------------------------------------------------------------ stage A
def build_masks(rgb_roi, cfg, log=None):
    """rgb_roi: uint8 (h, w, 3) of the work area.  Returns dict with D, Lm (3x3 blurred feature
    maps), ink, sky (gap-closed connected sky region), W (= ~sky), d_sky (distance of W pixels to
    the sky, capped)."""
    r = int(P(cfg, "pre_blur_r"))
    D = L.box_blur(L.blueness(rgb_roi), r)
    Lm = L.box_blur(L.luma(rgb_roi), r)
    bth = L.black_tophat(Lm, int(P(cfg, "ink_tophat_k")))
    bg = L.box_blur(Lm, int(P(cfg, "ink_tophat_bg_blur_r")))
    ink = (D > P(cfg, "ink_blueness_thr")) | ((bth > P(cfg, "ink_tophat_thr")) & (bg > P(cfg, "ink_tophat_bg_min")))
    cand = ~ink
    g = int(P(cfg, "gap_close_px"))
    dist = L.edt_capped(cand, g + 2)
    seed = tuple(int(v) for v in P(cfg, "sky_seed_xy"))
    core, n_it = L.flood_fill(dist > g, [seed])
    sky = L.geodesic_dilate(core, cand, g + 2)
    if log:
        log("stage A: flood iterations %d, sky px %d" % (n_it, int(sky.sum())))
    a = rgb_roi.astype(np.float32)
    GR = L.box_blur(a[:, :, 1] - a[:, :, 0], r)      # G - R: light cyan stripes are +22, foam -4, sky -13
    return {"D": D, "Lm": Lm, "GR": GR, "ink": ink, "sky": sky, "W": ~sky}


def left_edge_start(region_sky):
    """Start crack for a trace that keeps the sky on the left: the vertex below the lowest sky pixel
    of column 0 that is connected to the top of the column."""
    col = region_sky[:, 0]
    if not col[0]:
        raise RuntimeError("column 0 does not start in the sky")
    yb = int(np.argmin(col)) - 1 if not col.all() else len(col) - 1
    return (0, yb + 1)


def cut_at_stop(path, stop_xy):
    idx = np.nonzero((path[:, 0] > stop_xy[0]) & (path[:, 1] > stop_xy[1]))[0]
    if len(idx) == 0:
        raise RuntimeError("trace never reached the stop box %r" % (stop_xy,))
    return path[:idx[0] + 1]


def raw_silhouette(masks, cfg):
    sky = masks["sky"]
    loop = L.trace_cracks(sky, left_edge_start(sky), 0)
    return cut_at_stop(loop, P(cfg, "raw_trace_stop_xy"))


# ------------------------------------------------------------------ stage C
def opened_boundary(masks, radius, cfg):
    """Rolling ball of `radius` from the body side.  Returns (path (N, 2) int crack vertices,
    dev (N-1,) distance of the sky-side pixel of every step to the real sky)."""
    W = masks["W"]
    pad = int(math.ceil(radius)) + 3
    # edge-replicated padding: the frame edge must not act as a boundary of the wave
    Wo = L.opening(np.pad(W, pad, mode="edge"), radius)[pad:-pad, pad:-pad]
    so = ~Wo
    loop = L.trace_cracks(so, left_edge_start(so), 0)
    path = cut_at_stop(loop, P(cfg, "raw_trace_stop_xy"))
    d_sky = L.edt_capped(W, int(math.ceil(radius)) + 2)        # 0 on sky pixels
    left = L.crack_left_pixels(path)
    h, w = W.shape
    lx = np.clip(left[:, 0], 0, w - 1)
    ly = np.clip(left[:, 1], 0, h - 1)
    return path, d_sky[ly, lx]


def _runs(flags):
    """[(start, end_exclusive, value)] runs of a 1-D bool array."""
    out = []
    n = len(flags)
    i = 0
    while i < n:
        j = i
        while j < n and flags[j] == flags[i]:
            j += 1
        out.append((i, j, bool(flags[i])))
        i = j
    return out


def label_and_bridge(path, dev, cfg):
    """Vertex labels (TRACED / BRIDGE) of the opened boundary and the polyline in which every
    bridge is replaced by the chord between its two end (claw-root) points.
    Returns (pts float (M, 2), labels (M,), bridges list of dict)."""
    tol = P(cfg, "traced_tol_px")
    minor = P(cfg, "minor_bridge_max_dev_px")
    step_traced = dev <= tol
    n = len(path)
    vt = np.zeros(n, bool)
    vt[:-1] |= step_traced
    vt[1:] |= step_traced
    # relabel minor bridges
    for a, b, val in _runs(vt):
        if not val:
            lo, hi = max(a - 1, 0), min(b, len(dev))
            if dev[lo:hi].max() <= minor:
                vt[a:b] = True
    pts, labels, bridges = [], [], []
    runs = _runs(vt)
    for k, (a, b, val) in enumerate(runs):
        if val:
            pts.append(path[a:b].astype(np.float64))
            labels.append(np.full(b - a, TRACED, np.int8))
        else:
            if a == 0 or b == n:
                # bridge at a path end: keep the opened boundary itself
                pts.append(path[a:b].astype(np.float64))
                labels.append(np.full(b - a, BRIDGE, np.int8))
                continue
            p0 = path[a - 1].astype(np.float64)
            p1 = path[b].astype(np.float64)
            length = float(np.hypot(*(p1 - p0)))
            m = max(int(round(length)) - 1, 0)
            if m > 0:
                t = (np.arange(1, m + 1) / float(m + 1))[:, None]
                pts.append(p0[None] * (1 - t) + p1[None] * t)
                labels.append(np.full(m, BRIDGE, np.int8))
            lo, hi = max(a - 1, 0), min(b, len(dev))
            bridges.append({"root_a_px": [float(p0[0]), float(p0[1])], "root_b_px": [float(p1[0]), float(p1[1])],
                            "chord_px": length, "opened_arc_px": int(b - a),
                            "max_depth_px": float(dev[lo:hi].max())})
    return np.vstack(pts), np.concatenate(labels), bridges


def resample_labelled(p, lab, spacing):
    """Uniform arclength resampling that carries labels: a new sample is TRACED only if both
    bracketing input points are TRACED; otherwise it takes the larger label code of the two."""
    s = L.arclength(p)
    keep = np.concatenate([[True], np.diff(s) > 1e-9])
    p, lab, s = p[keep], lab[keep], s[keep]
    total = s[-1]
    n = int(math.floor(total / spacing + 1e-9))
    t = np.arange(n + 1) * spacing
    if total - t[-1] > 1e-6:
        t = np.concatenate([t, [total]])
    q = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    j = np.clip(np.searchsorted(s, t, side="right") - 1, 0, len(s) - 2)
    on_node = np.abs(s[j] - t) < 1e-9
    lab_new = np.where(on_node, lab[j], np.maximum(lab[j], lab[j + 1]))
    lab_new[-1] = lab[-1]
    return q, lab_new.astype(np.int8)


# ------------------------------------------------------------------ stage D
def running_median(a, win):
    win = int(win) | 1
    r = win // 2
    p = np.pad(a, r, mode="edge")
    idx = np.arange(len(a))[:, None] + np.arange(win)[None, :]
    return np.median(p[idx], axis=1)


def refine_traced(pts, labels, masks, cfg, field_sign=+1.0):
    """Sub-pixel refinement of TRACED points (outer edge of the outline).  field_sign = -1 is used
    by the white-body variant (edge from blue on the left to white on the right).
    Returns (refined pts, info dict)."""
    sig = P(cfg, "stair_sigma_px")
    q = L.gaussian_smooth_open(pts, sig, 1.0)
    normals, _ = L.local_normals(q, int(P(cfg, "normal_half_window_px")))
    kw = dict(search=P(cfg, "refine_search_px"), step=P(cfg, "refine_step_px"),
              outer=tuple(P(cfg, "refine_outer_px")), inner_max=P(cfg, "refine_inner_max_px"),
              level=P(cfg, "refine_level"), min_contrast=P(cfg, "refine_min_contrast"))
    Lm, D = masks["Lm"], masks["D"]
    if field_sign > 0:
        # local sky luma decides which field is used
        o0, o1 = P(cfg, "refine_outer_px")
        offs = np.arange(o0, o1 + 1e-9, 1.0)
        xs = q[:, 0][:, None] - normals[:, 0][:, None] * offs[None]
        ys = q[:, 1][:, None] - normals[:, 1][:, None] * offs[None]
        sky_l = np.median(L.bilinear(Lm, xs, ys), axis=1)
        use_l = sky_l >= P(cfg, "refine_luma_sky_min")
        rl, okl, shl, cl = L.refine_edge(255.0 - Lm, q, normals, **kw)
        rd, okd, shd, cd = L.refine_edge(D, q, normals, **kw)
        ok = np.where(use_l, okl, okd)
        shift = np.where(use_l, shl, shd)
    else:
        rd, ok, shift, cd = L.refine_edge(-D, q, normals, **kw)
        use_l = np.zeros(len(q), bool)
    traced = labels == TRACED
    good = ok & traced
    shift_f = np.zeros(len(q))
    if good.sum() >= 2:
        idx = np.arange(len(q))
        shift_i = np.interp(idx, idx[good], shift[good])
        shift_i = running_median(shift_i, P(cfg, "refine_shift_median_win"))
        shift_f = np.where(traced, shift_i, 0.0)
    out = q + normals * shift_f[:, None]
    # bridges: straight chord between the refined neighbours
    for a, b, val in _runs(labels != TRACED):
        if val and a > 0 and b < len(out):
            p0, p1 = out[a - 1], out[b]
            t = (np.arange(1, b - a + 1) / float(b - a + 1))[:, None]
            out[a:b] = p0[None] * (1 - t) + p1[None] * t
    info = {"n_traced": int(traced.sum()), "n_refined_ok": int(good.sum()),
            "frac_luma_field": float(use_l[traced].mean()) if traced.any() else 0.0,
            "shift_mean_px": float(shift_f[traced].mean()) if traced.any() else 0.0,
            "shift_abs_mean_px": float(np.abs(shift_f[traced]).mean()) if traced.any() else 0.0,
            "shift_abs_max_px": float(np.abs(shift_f[traced]).max()) if traced.any() else 0.0}
    return out, info, normals


# ------------------------------------------------------------------ stage E
def final_smooth(pts, labels, cfg):
    """pts sampled at 1 px.  Blend of a light (traced) and a heavier (bridge) Gaussian."""
    st, sb, sl = P(cfg, "sigma_traced_px"), P(cfg, "sigma_bridge_px"), P(cfg, "sigma_label_blend_px")
    a = L.gaussian_smooth_open(pts, st, 1.0)
    b = L.gaussian_smooth_open(pts, sb, 1.0)
    ind = (labels == BRIDGE).astype(np.float64)
    w = L.gaussian_smooth_open(np.stack([ind, ind], axis=1), sl, 1.0, fix_ends=False)[:, 0]
    w = np.clip(w, 0.0, 1.0)[:, None]
    out = a * (1 - w) + b * w
    out[0], out[-1] = pts[0], pts[-1]
    return out


def plateau_midpoint(pts, values, i_ext, tol, sign):
    """Contiguous stretch around index i_ext where sign*(values - values[i_ext]) <= tol.
    Returns (i_mid (arclength midpoint), i_a, i_b)."""
    n = len(values)
    ref = values[i_ext]
    a = i_ext
    while a > 0 and sign * (values[a - 1] - ref) <= tol:
        a -= 1
    b = i_ext
    while b < n - 1 and sign * (values[b + 1] - ref) <= tol:
        b += 1
    s = L.arclength(pts[a:b + 1])
    i_mid = a + int(np.argmin(np.abs(s - 0.5 * s[-1])))
    return i_mid, a, b


def inner_arc_end(pts, normals_in, i_from, masks, cfg):
    """First index >= i_from from which the wave side of the boundary is not blue for
    inner_end_min_run_px consecutive samples."""
    offs = np.asarray(P(cfg, "inner_end_inside_offsets_px"), dtype=np.float64)
    xs = pts[:, 0][:, None] + normals_in[:, 0][:, None] * offs[None]
    ys = pts[:, 1][:, None] + normals_in[:, 1][:, None] * offs[None]
    blue = np.median(L.bilinear(masks["D"], xs, ys), axis=1) > P(cfg, "ink_blueness_thr")
    run = int(P(cfg, "inner_end_min_run_px"))
    n = len(pts)
    i = i_from
    while i < n - run:
        if not blue[i:i + run].any():
            return i, blue
        i += 1
    return n - 1, blue


def end_tangent(pts, fit_len):
    """Unit tangent at the END of a polyline sampled at about 1 px: derivative at s = 0 of quadratic
    least-squares fits x(s), y(s) over the last fit_len px."""
    s = L.arclength(pts)
    sel = s >= s[-1] - fit_len
    ss = s[sel] - s[-1]
    cx = np.polyfit(ss, pts[sel, 0], 2)
    cy = np.polyfit(ss, pts[sel, 1], 2)
    t = np.array([cx[1], cy[1]])
    return t / np.hypot(*t)


def parabola_to_level(p0, t0, y_level, spacing=1.0, run_frac=1.0):
    """Quadratic Bezier P0 - C - P1: C = intersection of the tangent line through P0 with
    y = y_level, P1 = C + (run_frac * |C - P0|, 0).  Tangent t0 at P0, horizontal at P1.
    run_frac = 1 is the symmetric parabola; smaller values keep the curve closer to the tangent
    line (later, tighter turn into the trough level)."""
    if t0[1] <= 0.05 or p0[1] >= y_level:
        raise RuntimeError("parabola_to_level: end tangent does not descend towards the level")
    lam = (y_level - p0[1]) / t0[1]
    c = p0 + lam * t0
    p1 = np.array([c[0] + run_frac * lam, y_level])
    n = max(8, int(4 * lam / spacing))
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    curve = (1 - t) ** 2 * p0[None] + 2 * (1 - t) * t * c[None] + t ** 2 * p1[None]
    q, _ = L.resample_uniform(curve, spacing)
    return q, c, p1


def hidden_completion(p0, t0, y_level, sky, fracs, skip_px=8.0):
    """Largest run_frac (from `fracs`, descending) for which the completed curve stays out of the
    visible sky (it is supposed to be HIDDEN by the near wave / lie in the trough water).
    Returns (curve, c, p1, run_frac, n_sky_samples_of_the_chosen_curve)."""
    h, w = sky.shape
    best = None
    for f in fracs:
        curve, c, p1 = parabola_to_level(p0, t0, y_level, 1.0, f)
        s = L.arclength(curve)
        q = curve[s >= skip_px]
        xi = np.clip(np.floor(q[:, 0]).astype(np.int64), 0, w - 1)
        yi = np.clip(np.floor(q[:, 1]).astype(np.int64), 0, h - 1)
        n_sky = int(sky[yi, xi].sum())
        if best is None or n_sky < best[4]:
            best = (curve, c, p1, float(f), n_sky)
        if n_sky == 0:
            break
    return best


def overhang_axis(contour, i_deep, i_tip, shape_hw, polygon_mask_fn):
    """Principal axis of the overhanging part of the wave: the area enclosed by the base contour
    to the right of (and above) the inner-arc deepest point, closed by the vertical through that
    point.  Returns (direction deg: 0 = +X, negative = pointing below the horizontal, centroid px,
    polygon, elongation = sqrt(l1 / l2))."""
    xd = contour[i_deep, 0]
    top = contour[:i_tip + 1, 0]
    cross = np.nonzero((top[:-1] < xd) & (top[1:] >= xd))[0]
    if len(cross) == 0:
        raise RuntimeError("overhang_axis: the top side never crosses the plumb line of the deepest point")
    i0 = int(cross[-1])
    a, b = contour[i0], contour[i0 + 1]
    t = (xd - a[0]) / (b[0] - a[0])
    start = a + t * (b - a)
    poly = np.vstack([start[None], contour[i0 + 1:i_deep + 1]])
    mask = polygon_mask_fn(shape_hw, poly)
    ys, xs = np.nonzero(mask)
    pts = np.stack([xs + 0.5, ys + 0.5], axis=1)
    c = pts.mean(axis=0)
    cov = np.cov((pts - c).T)
    evals, evecs = np.linalg.eigh(cov)
    v = evecs[:, 1]
    if v[0] < 0:
        v = -v
    ang = float(np.degrees(np.arctan2(-v[1], v[0])))
    return ang, c, poly, float(np.sqrt(evals[1] / max(evals[0], 1e-9))), int(mask.sum())


def slope_profile(back_pts, sigma_px):
    """Slope angle (deg, + = rising towards the crest) along the back, measured on a smoothed copy.
    back_pts sampled at about 1 px.  Returns (arclength s, angle deg at segment midpoints)."""
    q = L.gaussian_smooth_open(back_pts, sigma_px, 1.0)
    s = L.arclength(q)
    ang = L.tangent_angles_deg(q)
    return 0.5 * (s[1:] + s[:-1]), ang, q


def signed_turn_deg(pts, i0, i1, stride):
    """Accumulated signed tangent turning (deg) between sample i0 and i1 (chords of `stride`)."""
    idx = np.arange(i0, i1 + 1, stride)
    if len(idx) < 3:
        return 0.0
    ang = L.tangent_angles_deg(pts[idx])
    return float(L.wrap_deg(np.diff(ang)).sum())
