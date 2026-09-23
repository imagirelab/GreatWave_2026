"""Base contour candidate A (REGION BASED) -- one command regenerates everything:

    & "<project>/tools/run_blender.ps1" src/contour/method_a_run.py

Pipeline (all parameters in method_a_params.json, nothing else is tuned by hand):
  1. masks      : ink/blue barrier + paper-white barrier -> gap-tolerant flood fill of the SKY from seeds
                  -> body = the non-sky component that contains the belly seed.
  2. claws      : pattern spectrum (area removed by openings of growing radius) + finger widths,
                  opening with a disc of open_radius_px -> claws and attached spray disappear, the
                  boundary of the opened region runs through the claw roots.
  3. trace      : crack following from the left frame edge (body on the right, sky on the left).
  4. classify   : 'traced' (on the raw sky/body boundary) vs 'claw_root_bridge' (opening arcs).
  5. smooth     : Gaussian along arclength (small sigma on traced, larger on bridges).
  6. junction   : end of the visible inner arc (the near wave takes over), completion down to Z = 0.
  7. split      : back / head / inner_arc at the crest and the head tip, 2 px resampling.
  8. measure    : S1..S6 re-measure, own S8, head thickness; json + overlays + crops + record data.

Outputs:
  target/candidates/a/base_contour.json            (schema gw.base_contour.v1)
  results/step1_prepare/contour_a/*.png, metrics.json
"""
import math
import os
import sys
import time

_SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import numpy as np

from gw import bootstrap, paths, frame, imgio, draw, plot
from contour import method_a_lib as L
from contour import method_a_report as R

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_JSON = os.path.join(HERE, "method_a_params.json")
OUT_JSON = os.path.join(paths.CANDIDATES_DIR, "a", "base_contour.json")
log = bootstrap.log


def load_params():
    raw = paths.read_json(PARAMS_JSON)
    return {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in raw.items()
            if not k.startswith("_")}


# ----------------------------------------------------------------------------- 1. masks
def build_masks(img, P):
    x0, y0, x1, y1 = P["roi_px"]
    assert x0 == 0 and y0 == 0, "the ROI must start at the top-left corner (pixel coords are used unshifted)"
    roi = img[:y1, :x1]
    f = roi.astype(np.float32)
    rb = f[:, :, 0] - f[:, :, 2]
    luma = imgio.to_gray(roi)
    bg = L.box_mean(luma, P["ink_bg_box_halfwidth"])
    ink = (rb < P["ink_rb_max"]) | (luma < P["ink_luma_ratio"] * bg)
    k = P["white_box_halfwidth"]
    rb_box = L.box_mean(rb, k)
    white = (rb_box < P["white_rb_max"]) & (L.box_mean(luma, k) > P["white_luma_min"]) & ~ink
    # paper white is a barrier only inside the claw zone: elsewhere the closed ink outline is enough, and
    # pale cloud patches that touch the outline of the back from the sky side must stay sky
    wx0, wy0, wx1, wy1 = P["white_barrier_zone_px"]
    wz = np.zeros_like(white)
    wz[wy0:wy1, wx0:wx1] = True
    white &= wz
    passable = ~(ink | white)
    sky = flood_sky(passable, P["sky_gap_radius_px"], P["sky_seeds_px"])
    body, missed = L.components_touching(~sky, [P["body_seed_px"]])
    if missed:
        raise RuntimeError("the body seed is sky: %s" % missed)
    leaks = {name: bool(sky[y, x]) for name, (x, y) in P["leak_check_points_px"].items()}
    return {"roi": roi, "rb": rb, "rb_box": rb_box, "luma": luma, "ink": ink, "white": white,
            "passable": passable, "sky": sky, "body": body, "leaks": leaks}


def flood_sky(passable, r, seeds):
    """Gap tolerant flood fill: flood inside the passable area eroded by r, dilate back by r."""
    core = L.erode_disc(passable, r) if r > 0 else passable
    sky_core, missed = L.components_touching(core, seeds)
    if missed:
        raise RuntimeError("sky seeds fall on barrier pixels (gap radius %s): %s" % (r, missed))
    return (L.dilate_disc(sky_core, r) & passable) if r > 0 else sky_core


def gap_radius_sweep(M, P):
    """Robustness evidence: leak check and sky area for other gap radii."""
    rows = []
    for r in P["sky_gap_radius_sweep_px"]:
        sky = flood_sky(M["passable"], r, P["sky_seeds_px"])
        leaked = [name for name, (x, y) in P["leak_check_points_px"].items() if sky[y, x]]
        rows.append({"gap_radius_px": r, "sky_px": int(sky.sum()), "leaked_check_points": leaked,
                     "sky_px_minus_chosen": int(sky.sum()) - int(M["sky"].sum())})
    return rows


# ----------------------------------------------------------------------------- 2. claws
def granulometry(body, P):
    """Pattern spectrum inside the claw zone + finger widths for the chosen radius."""
    zx0, zy0, zx1, zy1 = P["claw_zone_px"]
    radii = list(P["granulometry_radii_px"])
    m = max(radii) + 4
    cx0, cy0 = max(zx0 - 2 * m, 0), max(zy0 - 2 * m, 0)
    cx1, cy1 = min(zx1 + 2 * m, body.shape[1]), min(zy1 + 2 * m, body.shape[0])
    sub = body[cy0:cy1, cx0:cx1]
    d = L.edt_capped(sub, max(radii) + 2)
    zs = (slice(zy0 - cy0, zy1 - cy0), slice(zx0 - cx0, zx1 - cx0))
    rows = []
    for rad in radii:
        opened = L.dilate_disc(d > rad, rad)
        rows.append({"R_px": rad, "removed_px2": int((sub & ~opened)[zs].sum())})
    for i, row in enumerate(rows):
        if i == 0:
            row["d_removed_per_px_of_R"] = None
        else:
            row["d_removed_per_px_of_R"] = (row["removed_px2"] - rows[i - 1]["removed_px2"]) / float(
                row["R_px"] - rows[i - 1]["R_px"])
    # finger widths: components removed by the chosen opening, widest inscribed disc in each
    rad = P["open_radius_px"]
    opened = L.dilate_disc(d > rad, rad)
    removed = sub & ~opened
    zone = np.zeros_like(removed)
    zone[zs] = True
    lab, n = L.label_components(removed & zone)
    widths = []
    if n:
        area = np.bincount(lab.ravel(), minlength=n + 1)
        dmax = np.zeros(n + 1, np.float32)
        np.maximum.at(dmax, lab.ravel(), d.ravel())
        for l in range(1, n + 1):
            if area[l] >= 150:
                # d is the centre-to-centre distance to the nearest sky pixel: width ~ 2*d - 1
                widths.append(2.0 * float(dmax[l]) - 1.0)
    widths = np.array(sorted(widths))
    fingers = {"n_components_area_ge_150px2": int(len(widths))}
    if len(widths):
        fingers.update({"width_px_median": float(np.median(widths)), "width_px_p90": float(np.percentile(widths, 90)),
                        "width_px_max": float(widths.max()), "width_px_min": float(widths.min()),
                        "widths_px": [round(float(w), 1) for w in widths]})
    return rows, fingers


def plateau_check(rows, rad):
    """Is the chosen radius inside the flat part of the pattern spectrum?  The flat part = radii whose
    removal rate is below 40 % of the peak rate found at smaller radii."""
    rates = [(r["R_px"], r["d_removed_per_px_of_R"]) for r in rows if r["d_removed_per_px_of_R"] is not None]
    peak = max(v for _, v in rates)
    flat = [rr for rr, v in rates if v < 0.4 * peak and rr > rates[int(np.argmax([v for _, v in rates]))][0]]
    # contiguous flat range that starts right after the finger peak
    rng = []
    for rr, v in rates:
        if rr in flat:
            rng.append(rr)
        elif rng:
            break
    return {"peak_rate_px2_per_px": peak, "flat_range_px": [min(rng), max(rng)] if rng else None,
            "chosen_inside_flat_range": bool(rng and min(rng) <= rad <= max(rng))}


# ----------------------------------------------------------------------------- 3./4. trace + classify
def trace_from_left_edge(mask, y_stop):
    col = mask[:, 0]
    if col[0]:
        raise RuntimeError("the body touches the top-left corner: no sky at the left frame edge")
    ys = int(np.argmax(col))
    h, w = mask.shape

    def stop(x, y, n):
        return y >= y_stop or x >= w - 1 or (x <= 0 and n > 5)

    return L.trace_cracks(mask, (0, ys), 0, stop)


def classify_vertices(V, body_raw, tol):
    """traced (True) if the vertex is within tol of the raw sky/body boundary."""
    d = L.edt_capped(body_raw, int(math.ceil(tol)) + 3)
    h, w = body_raw.shape
    out = np.full(len(V), np.inf)
    for dx, dy in ((-1, -1), (0, -1), (-1, 0), (0, 0)):
        x = np.clip(V[:, 0] + dx, 0, w - 1)
        y = np.clip(V[:, 1] + dy, 0, h - 1)
        out = np.minimum(out, d[y, x])
    # d counts centre-to-centre distances: a body pixel that touches the sky has d = 1
    return out <= tol


def relabel_short_runs(flag, min_run):
    """True runs shorter than min_run that lie between two False runs become False."""
    f = flag.copy()
    n = len(f)
    i = 0
    while i < n:
        if f[i]:
            j = i
            while j < n and f[j]:
                j += 1
            if i > 0 and j < n and (j - i) < min_run:
                f[i:j] = False
            i = j
        else:
            i += 1
    return f


def runs_of(flag):
    out, i, n = [], 0, len(flag)
    while i < n:
        if flag[i]:
            j = i
            while j < n and flag[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


# ----------------------------------------------------------------------------- 5. smoothing
def smooth_contour(V, traced, P):
    pts = V.astype(np.float64)
    a = L.gaussian_smooth(pts, P["sigma_traced_px"])
    b = L.gaussian_smooth(pts, P["sigma_bridge_px"])
    ind = L.gaussian_smooth((~traced).astype(np.float64), P["label_blend_sigma_px"])
    w = np.clip(2.0 * (ind - 0.5), 0.0, 1.0)
    w[traced] = 0.0
    w = L.gaussian_smooth(w, 2.0)
    w[traced] = 0.0
    return a * (1.0 - w[:, None]) + b * w[:, None], w


def unit_tangents(pts, half=3):
    p = np.asarray(pts, dtype=np.float64)
    n = len(p)
    i0 = np.clip(np.arange(n) - half, 0, n - 1)
    i1 = np.clip(np.arange(n) + half, 0, n - 1)
    d = p[i1] - p[i0]
    ln = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)
    return d / ln[:, None]


# ----------------------------------------------------------------------------- 6. junction + completion
def find_junction(pts, rb_box, i_from, P):
    J = P["junction"]
    T = unit_tangents(pts, 4)
    N = np.stack([-T[:, 1], T[:, 0]], axis=1)          # right-hand side of the travel direction = body
    q = pts + J["inside_offset_px"] * N
    h, w = rb_box.shape
    xi = np.clip(np.floor(q[:, 0]).astype(int), 0, w - 1)
    yi = np.clip(np.floor(q[:, 1]).astype(int), 0, h - 1)
    inside_rb = rb_box[yi, xi]
    blue = inside_rb < J["blue_rb_max"]
    start = None
    for i in range(i_from, len(pts)):
        if pts[i, 1] >= J["search_from_y_px"]:
            start = i
            break
    if start is None:
        raise RuntimeError("the contour never reaches search_from_y_px")
    run = 0
    for i in range(start, len(pts)):
        if not blue[i]:
            run += 1
            if run >= J["min_run_px"]:
                return i - run + 1, inside_rb
        else:
            run = 0
    raise RuntimeError("no junction found: the inside of the inner arc stays blue down to the end of the trace")


def completion_arc(Jpt, tdir, y_trough, step=1.0):
    tx, ty = tdir
    alpha = math.atan2(ty, tx)                       # image coords, y down; expected 0 < alpha < pi/2
    if not (0.02 < alpha < math.pi / 2):
        raise RuntimeError("unexpected tangent at the junction: %.1f deg" % math.degrees(alpha))
    rho = (y_trough - Jpt[1]) / (1.0 - math.cos(alpha))
    n = max(2, int(math.ceil(rho * alpha / step)))
    phi = alpha - np.linspace(0.0, alpha, n + 1)
    x = Jpt[0] + rho * (math.sin(alpha) - np.sin(phi))
    y = Jpt[1] + rho * (np.cos(phi) - math.cos(alpha))
    return np.stack([x, y], axis=1), rho, math.degrees(alpha)


# ----------------------------------------------------------------------------- 7. split + resample
def refine_extremum(pts, idx, axis, sign):
    """Sub-sample position (arclength index, float) of the extremum of sign * pts[:, axis] near idx
    (parabola through 3 samples)."""
    i = int(np.clip(idx, 1, len(pts) - 2))
    y0, y1, y2 = (sign * pts[i - 1, axis], sign * pts[i, axis], sign * pts[i + 1, axis])
    den = y0 - 2 * y1 + y2
    off = 0.0 if abs(den) < 1e-12 else 0.5 * (y0 - y2) / den
    return i + float(np.clip(off, -0.5, 0.5))


def point_at(pts, fi):
    i = int(math.floor(fi))
    i = min(max(i, 0), len(pts) - 2)
    t = fi - i
    return pts[i] * (1 - t) + pts[i + 1] * t


def cut(pts, labels, fa, fb):
    """Sub-polyline between float indices fa < fb, with labels (nearest)."""
    ia, ib = int(math.ceil(fa)), int(math.floor(fb))
    mid = pts[ia:ib + 1]
    lab = list(labels[ia:ib + 1])
    pa, pb = point_at(pts, fa), point_at(pts, fb)
    if ia - fa > 1e-9:
        mid = np.vstack([pa[None], mid])
        lab = [labels[min(int(round(fa)), len(labels) - 1)]] + lab
    if fb - ib > 1e-9:
        mid = np.vstack([mid, pb[None]])
        lab = lab + [labels[min(int(round(fb)), len(labels) - 1)]]
    return mid, np.array(lab, dtype=object)


def resample_with_labels(pts, labels, spacing):
    s = L.arclength(pts)
    out, t = L.resample(pts, spacing, s=s, return_s=True)
    j = np.clip(np.searchsorted(s, t), 0, len(s) - 1)
    j0 = np.clip(j - 1, 0, len(s) - 1)
    near = np.where(np.abs(s[j0] - t) <= np.abs(s[j] - t), j0, j)
    return out, labels[near]


# ----------------------------------------------------------------------------- 8. measurements
def bilinear(a, x, y):
    """Sample the 2-D array a at continuous pixel coords (pixel centre = index + 0.5)."""
    h, w = a.shape
    fx = np.clip(np.asarray(x, dtype=np.float64) - 0.5, 0, w - 1.001)
    fy = np.clip(np.asarray(y, dtype=np.float64) - 0.5, 0, h - 1.001)
    x0 = np.floor(fx).astype(int)
    y0 = np.floor(fy).astype(int)
    tx, ty = fx - x0, fy - y0
    return (a[y0, x0] * (1 - tx) * (1 - ty) + a[y0, x0 + 1] * tx * (1 - ty)
            + a[y0 + 1, x0] * (1 - tx) * ty + a[y0 + 1, x0 + 1] * tx * ty)


def edge_offset_check(pts, src, luma, step=5, t_sky=-7.0, t_in=7.0):
    """Independent check of WHERE the contour sits relative to the outline: along the normal of every
    step-th traced point the luma profile is sampled; the 'half level edge' is the first crossing of the
    mean of the sky level and the darkest ink level.  Returns the signed offsets t_edge (px along the inward
    normal; negative = the half-level edge lies on the sky side of the contour, i.e. the contour runs inside
    the ink by that much)."""
    T = unit_tangents(pts, 3)
    N = np.stack([-T[:, 1], T[:, 0]], axis=1)
    ts = np.arange(t_sky, t_in + 1e-9, 0.25)
    out = []
    for i in range(0, len(pts), step):
        if src[i] != "traced":
            continue
        q = pts[i][None, :] + ts[:, None] * N[i][None, :]
        prof = bilinear(luma, q[:, 0], q[:, 1])
        sky_l = float(np.median(prof[ts <= -4.0]))
        ink_l = float(prof[ts >= -1.0].min())
        if sky_l - ink_l < 50.0:
            continue
        half = 0.5 * (sky_l + ink_l)
        below = np.nonzero(prof < half)[0]
        if len(below) == 0 or below[0] == 0:
            continue
        k = int(below[0])
        t = ts[k - 1] + (prof[k - 1] - half) / max(prof[k - 1] - prof[k], 1e-6) * 0.25
        out.append((i, t))
    return np.array(out, dtype=np.float64).reshape(-1, 2)


def chord_angle(pts, s, s0, s1):
    a = L.interp_at(pts, s, np.array([s0, s1]))
    return float(frame.Frame.px_dir_to_deg(a[1, 0] - a[0, 0], a[1, 1] - a[0, 1]))


def s8_profile(pts, spacing_px, tangent_half_px=4.0):
    """Tangent direction differences between samples `spacing_px` apart (within one segment)."""
    s = L.arclength(pts)
    total = s[-1]
    n = int(math.floor(total / spacing_px))
    if n < 2:
        return None
    t = np.arange(n + 1) * spacing_px
    lo = np.clip(t - tangent_half_px, 0, total)
    hi = np.clip(t + tangent_half_px, 0, total)
    a, b = L.interp_at(pts, s, lo), L.interp_at(pts, s, hi)
    ang = frame.Frame.px_dir_to_deg(b[:, 0] - a[:, 0], b[:, 1] - a[:, 1])
    dif = np.abs(L.angle_diff_deg(ang[1:], ang[:-1]))
    smp = L.interp_at(pts, s, t)
    ch = frame.Frame.px_dir_to_deg(np.diff(smp[:, 0]), np.diff(smp[:, 1]))
    cdif = np.abs(L.angle_diff_deg(ch[1:], ch[:-1]))
    return {"t": t, "samples": smp, "tangent_deg": ang, "tangent_diff_deg": dif, "chord_diff_deg": cdif}


def main():
    t_all = time.perf_counter()
    import argparse
    ap = argparse.ArgumentParser(description="base contour candidate A (region based)")
    ap.add_argument("--ball-radius", type=int, default=0,
                    help="OPTIONAL VARIANT, not the candidate: after the claw opening the region is closed and "
                         "opened with a ball of this radius (px) -> smooth 'large shape' contour")
    ap.add_argument("--tag", default="", help="name of the variant (required with --ball-radius); output goes to "
                                              "base_contour_<tag>.json and contour_a/variant_<tag>/")
    args = bootstrap.parse_args(ap)
    variant = bool(args.tag)
    if args.ball_radius and not variant:
        raise SystemExit("--ball-radius needs --tag (the candidate itself is never overwritten by a variant)")
    P = load_params()
    P["post_ball_radius_px"] = int(args.ball_radius)
    if variant:
        R.TITLE = "A VARIANT %s (ball %d px) - not the candidate" % (args.tag, args.ball_radius)
    F = frame.get_frame()
    out_dir = paths.step1_dir("contour_a" if not variant else os.path.join("contour_a", "variant_" + args.tag))
    out_json = OUT_JSON if not variant else os.path.join(os.path.dirname(OUT_JSON), "base_contour_%s.json" % args.tag)
    img = imgio.load_painting_rgb()
    Hh, Ww = img.shape[:2]
    pct = lambda d_px: float(d_px) / Hh * 100.0          # length in % of image height
    px_per_H = F.px_per_H

    # ---- 1
    with bootstrap.Timer("masks"):
        M = build_masks(img, P)
    log("leak check (True = leaked):", M["leaks"])
    if any(M["leaks"].values()):
        R.save_mask_debug(out_dir, M, None, P)
        bootstrap.finish(False, "sky leaked into the body: %s" % M["leaks"])

    with bootstrap.Timer("gap radius sweep"):
        sweep = gap_radius_sweep(M, P)
    for row in sweep:
        log("gap sweep:", row)

    # ---- 2
    with bootstrap.Timer("granulometry"):
        spectrum, fingers = granulometry(M["body"], P)
    for row in spectrum:
        log("spectrum R=%2d px removed=%6d px2 rate=%s" % (row["R_px"], row["removed_px2"],
            "n/a" if row["d_removed_per_px_of_R"] is None else "%.0f px2/px" % row["d_removed_per_px_of_R"]))
    plateau = plateau_check(spectrum, P["open_radius_px"])
    log("plateau check:", plateau)
    log("finger widths:", {k: v for k, v in fingers.items() if k != "widths_px"})
    with bootstrap.Timer("opening R=%d" % P["open_radius_px"]):
        opened = L.open_disc(M["body"], P["open_radius_px"])
    if P["post_ball_radius_px"] > 0:
        with bootstrap.Timer("variant: close + open with a ball of %d px" % P["post_ball_radius_px"]):
            opened = L.open_disc(L.close_disc(opened, P["post_ball_radius_px"]), P["post_ball_radius_px"])
    M["opened"] = opened

    # ---- 3 / 4
    with bootstrap.Timer("trace + classify"):
        V = trace_from_left_edge(opened, y_stop=P["roi_px"][3] - 2)
        traced = classify_vertices(V, M["body"], P["traced_tol_px"])
        traced = relabel_short_runs(traced, int(P["min_traced_run_px"]))
    log("trace: %d vertices, start %s, end %s" % (len(V), V[0].tolist(), V[-1].tolist()))

    # sensitivity to the opening radius (for the record only)
    sens = []
    sens_traces = {}
    with bootstrap.Timer("opening radius sensitivity"):
        for rad in ([] if variant else sorted(set(list(P["open_radius_sensitivity_px"]) + [P["open_radius_px"]]))):
            om = opened if rad == P["open_radius_px"] else L.open_disc(M["body"], rad)
            vv = V if rad == P["open_radius_px"] else trace_from_left_edge(om, y_stop=P["roi_px"][3] - 2)
            ic = int(np.argmin(vv[:, 1]))
            below = np.nonzero(vv[ic:, 1] > P["junction"]["search_from_y_px"])[0]
            ie = ic + (int(below[0]) if len(below) else len(vv) - ic - 1)
            it = ic + int(np.argmax(vv[ic:ie, 0]))
            sens.append({"R_px": rad, "head_tip_px": vv[it].tolist(),
                         "head_tip_pct": [round(float(vv[it, 0]) / Ww * 100, 2), round(float(vv[it, 1]) / Hh * 100, 2)],
                         "crest_y_px": int(vv[ic, 1]), "path_length_crest_to_y%d_px" % P["junction"]["search_from_y_px"]: int(ie - ic)})
            sens_traces[rad] = vv[:ie + 400]
            log("sensitivity R=%d: head tip %s (%s %%), path length crest -> inner arc %d px" % (
                rad, vv[it].tolist(), sens[-1]["head_tip_pct"], ie - ic))

    # ---- 5
    S, w_bridge = smooth_contour(V, traced, P)

    # ---- 6
    i_crest0 = int(np.argmin(S[:, 1]))
    j_idx, inside_rb = find_junction(S, M["rb_box"], i_crest0, P)
    log("crest (first pass) idx %d at (%.1f, %.1f); junction idx %d at (%.1f, %.1f)" % (
        i_crest0, S[i_crest0, 0], S[i_crest0, 1], j_idx, S[j_idx, 0], S[j_idx, 1]))
    vis = S[:j_idx + 1]
    vis_traced = traced[:j_idx + 1]
    vis_raw = V[:j_idx + 1]
    y_trough = float(F.pct_to_px(0.0, frame.SPEC_TROUGH_TOP_PCT)[1])       # Z = 0 of the spec frame
    nfit = int(P["completion"]["tangent_fit_px"])
    seg = vis[-nfit:]
    c = seg - seg.mean(0)
    _, _, vt = np.linalg.svd(c, full_matrices=False)
    tdir = vt[0] if np.dot(vt[0], seg[-1] - seg[0]) > 0 else -vt[0]
    arc, rho, alpha_deg = completion_arc(vis[-1], tdir, y_trough)
    log("completion arc: junction tangent %.1f deg below horizontal, radius %.1f px, ends at x=%.1f" % (
        alpha_deg, rho, arc[-1, 0]))

    # right-most claw point (raw body incl. claws) -- S6 re-measure, also the end of the flat run
    sx0, sy0, sx1, sy1 = P["s6_claw_search_px"]
    # only INK pixels of the body count: a spray dot (paper white, no outline) that touches the claw must
    # not shift the point
    sub = (M["body"] & M["ink"])[sy0:sy1, sx0:sx1]
    cols = np.nonzero(sub.sum(axis=0) >= 3)[0]
    # the body mask in this window must not touch the window's right border
    if cols.max() >= sub.shape[1] - 1:
        raise RuntimeError("claw search window is too small")
    xr = int(cols.max())
    yr = np.nonzero(sub[:, xr])[0]
    claw_px = (sx0 + xr + 1.0, sy0 + float(yr.mean()) + 0.5)            # outer edge of the ink outline
    log("right-most claw point (outer ink edge): (%.1f, %.1f)" % claw_px)

    flat = None
    if P["completion"]["flat_run_to"] == "claw_rightmost_x" and claw_px[0] > arc[-1, 0] + 1.0:
        n = int(math.ceil(claw_px[0] - arc[-1, 0]))
        flat = np.stack([np.linspace(arc[-1, 0], claw_px[0], n + 1), np.full(n + 1, y_trough)], axis=1)

    pts = [vis, arc[1:]]
    labels = [np.where(vis_traced, "traced", "claw_root_bridge").astype(object),
              np.full(len(arc) - 1, "completed_occluded", dtype=object)]
    if flat is not None:
        pts.append(flat[1:])
        labels.append(np.full(len(flat) - 1, "completed_other", dtype=object))
    full = np.vstack(pts)
    full_lab = np.concatenate(labels)

    # ---- 7
    i_crest = int(np.argmin(vis[:, 1]))
    f_crest = refine_extremum(vis, i_crest, 1, -1.0)
    i_tip = i_crest + int(np.argmax(vis[i_crest:, 0]))
    f_tip = refine_extremum(vis, i_tip, 0, +1.0)
    segs = {}
    spacing = float(P["sample_spacing_px"])
    for name, fa, fb in (("back", 0.0, f_crest), ("head", f_crest, f_tip), ("inner_arc", f_tip, float(len(full) - 1))):
        sp, sl = cut(full, full_lab, fa, fb)
        rp, rl = resample_with_labels(sp, sl, spacing)
        segs[name] = {"pts": rp, "src": rl}
    crest_px = segs["back"]["pts"][-1]
    tip_px = segs["head"]["pts"][-1]
    log("crest (%.2f, %.2f)  head tip (%.2f, %.2f)" % (crest_px[0], crest_px[1], tip_px[0], tip_px[1]))

    # ---- 8 measurements -------------------------------------------------------------------
    metrics = {"params": P, "frame": F.summary(), "leak_check": M["leaks"], "gap_radius_sweep": sweep,
               "pattern_spectrum": spectrum,
               "plateau_check": plateau, "finger_widths": fingers,
               "trace": {"n_vertices": int(len(V)), "junction_index": int(j_idx)},
               "open_radius_sensitivity": sens}

    # residual raw traced vertices -> final contour, per segment (only traced vertices)
    allpts = np.vstack([segs[k]["pts"] for k in ("back", "head", "inner_arc")])
    resid = {}
    bounds = {"back": (0, int(round(f_crest))), "head": (int(round(f_crest)), int(round(f_tip))),
              "inner_arc": (int(round(f_tip)), j_idx + 1)}
    for name, (a, b) in bounds.items():
        sel = np.arange(a, b)
        sel = sel[vis_traced[a:b]]
        raw = vis_raw[sel].astype(np.float64)
        d = L.point_to_polyline_dist(raw, segs[name]["pts"]) if len(raw) else np.zeros(0)
        nb = int((~vis_traced[a:b]).sum())
        resid[name] = {"n_traced_raw_vertices": int(len(raw)), "n_bridge_vertices": nb,
                       "mean_px": float(d.mean()) if len(d) else None,
                       "p95_px": float(np.percentile(d, 95)) if len(d) else None,
                       "max_px": float(d.max()) if len(d) else None,
                       "max_pct_h": pct(d.max()) if len(d) else None,
                       "max_at_px": raw[int(np.argmax(d))].tolist() if len(d) else None}
        log("residual raw traced -> smoothed [%s]: mean %.2f p95 %.2f max %.2f px (%.3f %% of image height) at %s; bridge vertices %d"
            % (name, resid[name]["mean_px"], resid[name]["p95_px"], resid[name]["max_px"], resid[name]["max_pct_h"],
               resid[name]["max_at_px"], nb))
    metrics["smoothing_residual"] = resid

    # independent check of the line position against the luma half-level edge of the outline
    edge = {}
    for name in ("back", "head", "inner_arc"):
        e = edge_offset_check(segs[name]["pts"], segs[name]["src"], M["luma"])
        if len(e):
            t = e[:, 1]
            edge[name] = {"n": int(len(t)), "mean_px": float(t.mean()), "median_px": float(np.median(t)),
                          "p05_px": float(np.percentile(t, 5)), "p95_px": float(np.percentile(t, 95)),
                          "abs_max_px": float(np.abs(t).max())}
            log("edge check [%s]: half-level edge of the outline relative to the contour: median %+.2f px, p05 %+.2f, p95 %+.2f (n=%d; negative = contour lies inside the ink)"
                % (name, edge[name]["median_px"], edge[name]["p05_px"], edge[name]["p95_px"], len(t)))
    metrics["edge_position_check"] = dict(edge, definition="signed distance along the inward normal from the contour to the first half-level luma crossing (mean of sky level and darkest ink level); traced points only, every 5th point")

    # bridge runs (where the opening replaced the raw boundary)
    bruns = []
    for a, b in runs_of(~vis_traced):
        p0, p1 = vis[a], vis[b - 1]
        dev = L.point_to_polyline_dist(vis[a:b], vis_raw[[max(a - 1, 0), min(b, len(vis_raw) - 1)]].astype(float))
        bruns.append({"i0": int(a), "i1": int(b), "length_px": int(b - a), "from_px": p0.round(1).tolist(),
                      "to_px": p1.round(1).tolist()})
    metrics["bridge_runs"] = bruns
    log("bridge runs: %d, total %d px of %d px visible contour" % (len(bruns), sum(r["length_px"] for r in bruns), len(vis)))

    # S8 (own smoothness), within each segment
    sp8 = float(F.pct_h_to_px(P["s8_spacing_pct_h"]))
    s8 = {}
    s8_prof = {}
    for name in ("back", "head", "inner_arc"):
        pr = s8_profile(segs[name]["pts"], sp8)
        s8_prof[name] = pr
        dif = pr["tangent_diff_deg"]
        order = np.argsort(dif)[::-1][:6]
        worst = [{"diff_deg": float(dif[i]), "at_px": pr["samples"][i + 1].round(1).tolist(),
                  "chord_diff_deg": float(pr["chord_diff_deg"][min(i, len(pr["chord_diff_deg"]) - 1)])} for i in order]
        # the same restricted to the part that is scored by S7 (not completed) and to traced-only
        s8[name] = {"n_samples": int(len(pr["t"])), "max_tangent_diff_deg": float(dif.max()),
                    "n_over_15deg": int((dif >= 15.0).sum()), "max_chord_diff_deg": float(pr["chord_diff_deg"].max()),
                    "n_chord_over_15deg": int((pr["chord_diff_deg"] >= 15.0).sum()), "worst": worst}
        log("S8 own [%s]: max tangent diff %.1f deg, %d of %d over 15 deg; chord version max %.1f deg (%d over)" % (
            name, s8[name]["max_tangent_diff_deg"], s8[name]["n_over_15deg"], len(dif),
            s8[name]["max_chord_diff_deg"], s8[name]["n_chord_over_15deg"]))
    metrics["S8_own"] = s8

    # diagnostic: how far is an S8-smooth curve from this base contour?  (S7 vs S8 compatibility)
    # S8 allows 15 deg per 1 % of image height, i.e. a radius of curvature >= 25.94 / 0.2618 = 99 px.  Stand-in for
    # a smooth silhouette: the opened region 'rolled' from both sides with a ball of radius r (close, then open).
    compat = []
    compat_curves = {}
    with bootstrap.Timer("S7/S8 compatibility diagnostic"):
        for rb_ in ([] if variant else P["s7_s8_compat_ball_radii_px"]):
            reg = L.open_disc(L.close_disc(opened, rb_), rb_)
            vv = trace_from_left_edge(reg, y_stop=P["roi_px"][3] - 2)
            ic = int(np.argmin(vv[:, 1]))
            below = np.nonzero(vv[ic:, 1] > vis[-1, 1])[0]
            ie = ic + (int(below[0]) if len(below) else len(vv) - ic - 1)
            curve = L.gaussian_smooth(vv[:ie + 1].astype(np.float64), P["sigma_traced_px"])
            it = ic + int(np.argmax(curve[ic:, 0]))
            pr = s8_profile(L.resample(curve, spacing), sp8)
            row = {"ball_radius_px": rb_, "s8_max_tangent_diff_deg": float(pr["tangent_diff_deg"].max()),
                   "s8_n_over_15deg": int((pr["tangent_diff_deg"] >= 15.0).sum()), "s8_n_samples": int(len(pr["t"])),
                   "head_tip_px": curve[it].round(1).tolist(),
                   "head_tip_pct": [round(float(curve[it, 0]) / Ww * 100, 2), round(float(curve[it, 1]) / Hh * 100, 2)]}
            for name in ("back", "head", "inner_arc"):
                base = segs[name]["pts"][[str(s) in ("traced", "claw_root_bridge") for s in segs[name]["src"]]]
                dv = L.point_to_polyline_dist(base, curve)
                row[name] = {"dev_mean_pct_h": pct(dv.mean()), "dev_p95_pct_h": pct(np.percentile(dv, 95)),
                             "dev_max_pct_h": pct(dv.max())}
            compat.append(row)
            compat_curves[rb_] = curve
            log("S7/S8 compatibility ball r=%3d px: S8 max %.0f deg (%d of %d over 15), tip %s; " % (
                rb_, row["s8_max_tangent_diff_deg"], row["s8_n_over_15deg"], row["s8_n_samples"], row["head_tip_pct"])
                + "; ".join("%s dev mean %.2f p95 %.2f max %.2f %%h" % (
                    n, row[n]["dev_mean_pct_h"], row[n]["dev_p95_pct_h"], row[n]["dev_max_pct_h"])
                    for n in ("back", "head", "inner_arc")))
    metrics["s7_s8_compatibility"] = {
        "rows": compat,
        "definition": "diagnostic only. S8 (15 deg per 1 % of image height) means a radius of curvature of at least 99 px. Stand-in for a smooth silhouette: the opened region closed and then opened with a ball of the given radius, traced like the base contour. Reported: its own S8 over the whole path (left frame edge -> junction level), its right-most point, and the distance of the base-contour points (in_S7 only) to it per segment (mean / p95 / max in % of image height; the S7 limits are 1 / 2)."}

    # total turn around the head tip
    hp, ip = segs["head"]["pts"], segs["inner_arc"]["pts"]
    hs, is_ = L.arclength(hp), L.arclength(ip)
    turn = {}
    for q in (5, 10, 20):
        d_px = q / 100.0 * px_per_H
        if d_px + 10 < hs[-1] and d_px + 10 < is_[-1]:
            a_in = chord_angle(hp, hs, hs[-1] - d_px - 8, hs[-1] - d_px + 8)
            a_out = chord_angle(ip, is_, d_px - 8, d_px + 8)
            # unwrapped turning: integrate along the path
            pth = np.vstack([hp[hs >= hs[-1] - d_px], ip[1:][is_[1:] <= d_px]])
            tt = unit_tangents(pth, 4)                                   # chords over +-8 px
            ang = np.unwrap(np.arctan2(-tt[:, 1], tt[:, 0]))
            tot = float(np.degrees(ang[-1] - ang[0]))
            turn["within_%d_pct_H" % q] = {"tangent_in_deg": a_in, "tangent_out_deg": a_out, "net_turn_deg": tot}
    metrics["head_tip_turn"] = turn
    log("turn around the head tip:", turn)

    # head thickness (claws removed)
    thick = {}
    for q in P["head_thickness_at_pct_H"]:
        d_px = q / 100.0 * px_per_H
        if d_px < hs[-1] and d_px < is_[-1]:
            a = L.interp_at(hp, hs, np.array([hs[-1] - d_px]))[0]
            b = L.interp_at(ip, is_, np.array([d_px]))[0]
            t_px = float(np.hypot(*(a - b)))
            # vertical thickness at the x of the mid point between a and b
            thick["at_%d_pct_H" % q] = {"top_px": a.round(1).tolist(), "under_px": b.round(1).tolist(),
                                         "thickness_px": t_px, "thickness_pct_H": t_px / px_per_H * 100.0,
                                         "thickness_pct_h_image": pct(t_px)}
    # vertical thickness of the head at fixed x offsets behind the tip
    vth = {}
    for q in (5, 10, 20):
        xq = tip_px[0] - q / 100.0 * px_per_H
        top = hp[np.argmin(np.abs(hp[:, 0] - xq))]
        under_sel = ip[(ip[:, 1] < 1250)]
        und = under_sel[np.argmin(np.abs(under_sel[:, 0] - xq))]
        vth["x_tip_minus_%d_pct_H" % q] = {"x_px": float(xq), "top_y_px": float(top[1]), "under_y_px": float(und[1]),
                                            "vertical_thickness_pct_H": float(und[1] - top[1]) / px_per_H * 100.0}
    metrics["head_thickness"] = {"by_equal_arclength_behind_tip": thick, "vertical_at_x_behind_tip": vth,
                                 "definition": "equal arclength: point on the top side s behind the head tip (along 'head') and point on the underside s behind it (along 'inner_arc'), straight distance between the two; s in %% of H (H = %.1f px). vertical: y difference between the underside and the top side at x = x_tip - q*H." % px_per_H}
    log("head thickness:", {k: round(v["thickness_pct_H"], 2) for k, v in thick.items()},
        "vertical:", {k: round(v["vertical_thickness_pct_H"], 2) for k, v in vth.items()})

    # ---- landmarks ----------------------------------------------------------------------
    bp = segs["back"]["pts"]
    bs = L.arclength(bp)
    # crest plateau: part of the contour within 2 px of the top
    ally = np.vstack([bp, hp[1:]])
    top_y = float(ally[:, 1].min())
    near = ally[ally[:, 1] <= top_y + 2.0]
    plateau_x = (float(near[:, 0].min()), float(near[:, 0].max()))
    # inner arc deepest point = left-most point of the inner arc below the head underside
    lower = ip[:, 1] > tip_px[1]
    # the left-most point of the visible inner arc (not the completion)
    isrc = segs["inner_arc"]["src"]
    vis_sel = np.array([s in ("traced", "claw_root_bridge") for s in isrc])
    cand = np.nonzero(vis_sel)[0]
    i_deep = cand[int(np.argmin(ip[cand, 0]))]
    deep_px = ip[i_deep]
    near_deep = ip[cand][ip[cand, 0] <= deep_px[0] + 2.0]
    deep_y_range = (float(near_deep[:, 1].min()), float(near_deep[:, 1].max()))

    # head-tip direction
    def mid_behind(q):
        d_px = q / 100.0 * px_per_H
        a = L.interp_at(hp, hs, np.array([hs[-1] - d_px]))[0]
        b = L.interp_at(ip, is_, np.array([d_px]))[0]
        return 0.5 * (a + b)
    dir_alt = {}
    for q in (5, 10, 20, 30):
        mq = mid_behind(q)
        dir_alt["medial_axis_%dpct_H" % q] = round(float(F.px_dir_to_deg(tip_px[0] - mq[0], tip_px[1] - mq[1])), 2)
    for q in (10, 20, 30):
        a = L.interp_at(hp, hs, np.array([hs[-1] - q / 100.0 * px_per_H]))[0]
        dir_alt["top_side_chord_last_%dpct_H" % q] = round(float(F.px_dir_to_deg(tip_px[0] - a[0], tip_px[1] - a[1])), 2)
    dir_alt["crest_to_tip"] = round(float(F.px_dir_to_deg(tip_px[0] - crest_px[0], tip_px[1] - crest_px[1])), 2)
    # principal axis of the overhang region (right of the plumb line through the inner-arc deepest point)
    k0 = int(np.nonzero(hp[:, 0] >= deep_px[0])[0][0])
    poly = np.vstack([hp[k0:], ip[1:i_deep + 1]])
    o = np.floor(poly.min(0)) - 2.0
    wh = np.ceil(poly.max(0) - o).astype(int) + 4
    om = draw.polygon_mask((int(wh[1]), int(wh[0])), poly - o)
    ys_, xs_ = np.nonzero(om)
    cen = np.array([xs_.mean() + 0.5 + o[0], ys_.mean() + 0.5 + o[1]])
    dx_, dy_ = xs_ - xs_.mean(), ys_ - ys_.mean()
    cov = np.array([[np.mean(dx_ * dx_), np.mean(dx_ * dy_)], [np.mean(dx_ * dy_), np.mean(dy_ * dy_)]])
    ev, evec = np.linalg.eigh(cov)
    ax = evec[:, int(np.argmax(ev))]
    ax = ax if ax[0] > 0 else -ax
    dir_axis = float(F.px_dir_to_deg(ax[0], ax[1]))
    dir_alt["centroid_of_overhang_to_tip"] = round(float(F.px_dir_to_deg(tip_px[0] - cen[0], tip_px[1] - cen[1])), 2)
    overhang = {"area_px2": int(om.sum()), "area_H2": float(om.sum()) / px_per_H ** 2, "centroid_px": cen.round(1).tolist(),
                "principal_axis_deg": round(dir_axis, 2),
                "axis_std_px": [round(float(math.sqrt(max(v, 0.0))), 1) for v in sorted(ev, reverse=True)]}
    dir_def = ("principal axis (largest second moment of area) of the OVERHANG region = the part of the base contour's "
               "interior that lies right of the plumb line through the inner-arc deepest point and above that point "
               "(closed polygon: head from that plumb line to the head tip, then underside / inner arc back to the "
               "deepest point); oriented towards +X; 0 deg = +X, negative = pointing downward. Chosen because the "
               "painted head with claws removed is a blunt mass (right side almost vertical), so local tip-direction "
               "definitions are unstable - see direction_alternatives_deg")

    # S3: lowest visible sky pixel in the hollow
    tx0, tx1 = P["s3_trough_search_x_px"]
    sky = M["sky"]
    colmax = np.array([(np.nonzero(sky[:, x])[0].max() if sky[:, x].any() else -1) for x in range(tx0, tx1)])
    # restrict to the sky that is below the head (rows below the head tip)
    ix = int(np.argmax(colmax))
    trough_meas_px = (tx0 + ix + 0.5, float(colmax[ix]) + 1.0)          # lower edge of the lowest sky pixel
    log("lowest visible sky point in the hollow: (%.1f, %.1f)" % trough_meas_px)

    def lm(p):
        X, Z = F.px_to_H(p[0], p[1])
        return {"px": [round(float(p[0]), 2), round(float(p[1]), 2)], "H": [round(float(X), 5), round(float(Z), 5)],
                "pct": [round(float(p[0]) / Ww * 100, 3), round(float(p[1]) / Hh * 100, 3)]}

    landmarks = {
        "crest": dict(lm(crest_px), plateau_x_px=[round(v, 1) for v in plateau_x],
                      plateau_definition="x range of the base contour that is within 2 px of its highest row",
                      plateau_centre_px=[round(0.5 * (plateau_x[0] + plateau_x[1]), 1), round(top_y, 2)]),
        "head_tip": dict(lm(tip_px), direction_deg=round(dir_axis, 2), direction_definition=dir_def,
                         direction_alternatives_deg=dir_alt, overhang_region=overhang),
        "inner_deepest": dict(lm(deep_px), y_range_within_2px_of_leftmost_px=[round(v, 1) for v in deep_y_range]),
        "trough_level": {"y_px": round(y_trough, 2), "top_pct": frame.SPEC_TROUGH_TOP_PCT,
                         "note": "Z = 0 of the spec frame (74.7 %); the completed part of the contour ends on this level. The lowest VISIBLE sky point is reported in remeasure.S3.",
                         "measured_lowest_visible_sky_px": [round(trough_meas_px[0], 1), round(trough_meas_px[1], 1)]},
        "claw_rightmost": lm(claw_px),
        "junction_near_wave": dict(lm(vis[-1]), note="end of the visible inner arc; below it the near wave (temae no nami) hides the great wave"),
    }
    # local dip of the silhouette near the left frame edge
    n_first = int(np.searchsorted(bs, 0.25 * bs[-1]))
    i_dip = int(np.argmax(bp[:n_first, 1]))
    landmarks["back_left_dip"] = dict(lm(bp[i_dip]), note="lowest point of the silhouette near the left frame edge; left of it the outline RISES towards the frame edge (a neighbouring swell), right of it the back of the great wave begins")

    # ---- re-measure S1..S6 -------------------------------------------------------------
    spec = {k: F.pct_to_px(*v) for k, v in frame.SPEC_LANDMARKS_PCT.items()}
    s1s = (float(spec["S1_crest"][0]), float(spec["S1_crest"][1]))
    s2s = (float(spec["S2_inner_arc_deepest"][0]), float(spec["S2_inner_arc_deepest"][1]))
    s6s = (float(spec["S6_claw_rightmost"][0]), float(spec["S6_claw_rightmost"][1]))
    pc = landmarks["crest"]["plateau_centre_px"]
    rem = {}
    rem["S1"] = {"spec_pct": [38.2, 8.7], "measured_pct": landmarks["crest"]["pct"],
                 "diff_pct_h": {"dx": pct(crest_px[0] - s1s[0]), "dz_up_positive": pct(s1s[1] - crest_px[1])},
                 "plateau_x_px": landmarks["crest"]["plateau_x_px"],
                 "plateau_width_pct_h": pct(plateau_x[1] - plateau_x[0]),
                 "plateau_centre_pct": [round(pc[0] / Ww * 100, 3), round(pc[1] / Hh * 100, 3)],
                 "plateau_centre_diff_pct_h": {"dx": pct(pc[0] - s1s[0])},
                 "how": "highest point of the smoothed base contour (outer edge of the ink outline, claws / spray removed by the opening); the top is a flat plateau, so x is ill-conditioned: plateau = contour within 2 px of the top row"}
    rem["S2"] = {"spec_pct": [39.5, 46.3], "measured_pct": landmarks["inner_deepest"]["pct"],
                 "diff_pct_h": {"dx": pct(deep_px[0] - s2s[0]), "dy_down_positive": pct(deep_px[1] - s2s[1]),
                                "dist": pct(math.hypot(deep_px[0] - s2s[0], deep_px[1] - s2s[1]))},
                 "y_range_within_2px_of_leftmost_pct": [round(v / Hh * 100, 3) for v in deep_y_range],
                 "how": "left-most point of the visible inner arc of the base contour (sky / belly boundary, outer edge of the ink line); the boundary is nearly vertical there, so y is ill-conditioned: the y range within 2 px of the left-most x is given"}
    h_meas = pct(trough_meas_px[1] - crest_px[1])
    rem["S3"] = {"spec": {"trough_top_pct": 74.7, "height_pct_h": 66.0},
                 "measured": {"lowest_visible_sky_pct": [round(trough_meas_px[0] / Ww * 100, 3), round(trough_meas_px[1] / Hh * 100, 3)],
                              "height_pct_h": h_meas},
                 "diff_pct_h": {"trough_level": pct(trough_meas_px[1]) - 74.7, "height": h_meas - 66.0},
                 "how": "lowest pixel of the flood-filled sky inside x = %d..%d px (the hollow between the great wave and the right wave): it is the point where the flank of the near wave meets the dark sea band at the foot of Fuji. The real trough under the head is hidden by the near wave, so this is only the lowest VISIBLE water line, not a reliable trough measurement." % (tx0, tx1)}
    # S4
    wpx = float(F.pct_h_to_px(P["s4_tangent_window_pct_h"]))
    sl_s = np.arange(0.0, bs[-1] + 1e-6, 2.0)
    sl = np.array([chord_angle(bp, bs, max(s - wpx, 0.0), min(s + wpx, bs[-1])) for s in sl_s])
    s_dip = bs[i_dip]
    i_max = int(np.argmax(sl))
    def slope_at(s):
        return float(np.interp(s, sl_s, sl))
    pmax = L.interp_at(bp, bs, np.array([sl_s[i_max]]))[0]
    after_max = sl[i_max:]
    incr = np.diff(after_max)
    s4 = {"spec_deg": {"left_end": 25.0, "mid_max": 47.0, "before_crest": 8.0},
          "measured_deg": {
              "at_left_frame_edge": slope_at(0.0),
              "at_dip": slope_at(s_dip),
              "dip_plus_2pct_h": slope_at(s_dip + F.pct_h_to_px(2)),
              "dip_plus_5pct_h": slope_at(s_dip + F.pct_h_to_px(5)),
              "dip_plus_10pct_h": slope_at(s_dip + F.pct_h_to_px(10)),
              "mid_max": float(sl[i_max]),
              "mid_max_at_pct": [round(float(pmax[0]) / Ww * 100, 2), round(float(pmax[1]) / Hh * 100, 2)],
              "crest_minus_10pct_h": slope_at(bs[-1] - F.pct_h_to_px(10)),
              "crest_minus_5pct_h": slope_at(bs[-1] - F.pct_h_to_px(5)),
              "crest_minus_3pct_h": slope_at(bs[-1] - F.pct_h_to_px(3)),
              "crest_minus_2pct_h": slope_at(bs[-1] - F.pct_h_to_px(2))},
          "checks": {"mid_is_steepest": bool(0.2 * bs[-1] < sl_s[i_max] < 0.8 * bs[-1]),
                     "largest_slope_increase_between_max_and_crest_deg": float(np.max(np.maximum.accumulate(after_max[::-1])[::-1] - after_max)) if len(after_max) > 1 else 0.0},
          "how": "slope = direction of the chord over +-%.1f %% of image height of arclength (one-sided at the ends) on the 'back' segment; positions are arclength offsets from the left dip / from the crest" % P["s4_tangent_window_pct_h"]}
    # the same with a wider chord (+-3 % of image height) to show how much the numbers depend on the window
    wpx2 = float(F.pct_h_to_px(3.0))
    sl2 = np.array([chord_angle(bp, bs, max(s - wpx2, 0.0), min(s + wpx2, bs[-1])) for s in sl_s])
    i_max2 = int(np.argmax(sl2))
    s4["measured_deg_window_3pct_h"] = {
        "dip_plus_5pct_h": float(np.interp(s_dip + F.pct_h_to_px(5), sl_s, sl2)),
        "dip_plus_10pct_h": float(np.interp(s_dip + F.pct_h_to_px(10), sl_s, sl2)),
        "mid_max": float(sl2[i_max2]),
        "crest_minus_10pct_h": float(np.interp(bs[-1] - F.pct_h_to_px(10), sl_s, sl2)),
        "crest_minus_5pct_h": float(np.interp(bs[-1] - F.pct_h_to_px(5), sl_s, sl2))}
    # where does the back have the spec slopes?  (first / last arclength position with that slope)
    def first_pos(val, after):
        k = np.nonzero((sl_s > after) & (sl >= val))[0]
        if not len(k):
            return None
        p = L.interp_at(bp, bs, np.array([sl_s[k[0]]]))[0]
        return [round(float(p[0]) / Ww * 100, 2), round(float(p[1]) / Hh * 100, 2)]
    def last_pos(val):
        k = np.nonzero((sl_s > sl_s[i_max]) & (sl >= val))[0]
        if not len(k):
            return None
        p = L.interp_at(bp, bs, np.array([sl_s[k[-1]]]))[0]
        return [round(float(p[0]) / Ww * 100, 2), round(float(p[1]) / Hh * 100, 2)]
    s4["where_pct"] = {"slope_first_reaches_25deg_after_dip": first_pos(25.0, s_dip),
                       "slope_last_above_8deg_before_crest": last_pos(8.0)}
    s4["diff_deg"] = {"mid_max_minus_spec47": float(sl[i_max]) - 47.0,
                      "mid_max_window3pct_minus_spec47": float(sl2[i_max2]) - 47.0}
    rem["S4"] = s4
    rem["S6"] = {"spec_pct": [59.2, 33.0], "measured_pct": landmarks["claw_rightmost"]["pct"],
                 "diff_pct_h": {"dx": pct(claw_px[0] - s6s[0]), "dy_down_positive": pct(claw_px[1] - s6s[1])},
                 "derived": {"overhang_pct_of_H": float((claw_px[0] - crest_px[0]) / px_per_H * 100.0),
                             "direction_from_crest_deg": float(F.px_dir_to_deg(claw_px[0] - crest_px[0], claw_px[1] - crest_px[1]))},
                 "how": "right-most column of the raw body mask (claws included, outer edge of the ink outline) inside the window %s; y = mean row of that column" % (P["s6_claw_search_px"],)}
    rem["S5"] = {"head_tip_pct": landmarks["head_tip"]["pct"], "head_tip_H": landmarks["head_tip"]["H"],
                 "direction_deg": landmarks["head_tip"]["direction_deg"],
                 "direction_alternatives_deg": landmarks["head_tip"]["direction_alternatives_deg"],
                 "relative_to_S6_point_pct_h": {"dx": pct(tip_px[0] - claw_px[0]), "dy_down_positive": pct(tip_px[1] - claw_px[1])},
                 "how": "head tip = right-most point of the base contour between the crest and the junction (claws removed by the opening). " + dir_def}
    metrics["landmarks"] = landmarks
    metrics["remeasure"] = rem
    for k in ("S1", "S2", "S3", "S6"):
        log("remeasure %s: %s" % (k, {kk: vv for kk, vv in rem[k].items() if kk != "how"}))
    log("remeasure S4:", s4["measured_deg"], s4["checks"])
    log("remeasure S5:", {kk: vv for kk, vv in rem["S5"].items() if kk != "how"})

    # ---- JSON -----------------------------------------------------------------------------
    jp = {k: {"px": v["px"], "H": v["H"]} for k, v in landmarks.items() if "px" in v}
    out = {
        "schema": "gw.base_contour.v1",
        "candidate": ("A (region based: sky flood fill + disc opening R=%d px)" % P["open_radius_px"]) if not variant
        else ("OPTIONAL VARIANT '%s' of A (not the candidate): disc opening R=%d px, then close + open with a ball of %d px"
              % (args.tag, P["open_radius_px"], P["post_ball_radius_px"])),
        "image": {"path": paths.painting_path(), "width": Ww, "height": Hh},
        "frame": {"crest_left_pct": F.crest_left_pct, "crest_top_pct": F.crest_top_pct, "height_pct": F.height_pct,
                  "frame_h_H": round(F.frame_h, 6), "frame_w_H": round(F.frame_w, 6),
                  "x_left_H": round(F.x_left, 6), "z_top_H": round(F.z_top, 6)},
        "order": "left frame edge -> crest -> head tip -> inner arc -> trough",
        "sample_spacing_px": spacing,
        "contour_definition": "outer edge (sky side) of the dark outline of the great wave; claws / spray removed by a disc opening (R = %d px) of the non-sky region, so the line bridges every claw at its root with an arc of that radius" % P["open_radius_px"],
        "segments": [],
        "landmarks": {
            "crest": dict(jp["crest"], plateau_x_px=landmarks["crest"]["plateau_x_px"], plateau_centre_px=landmarks["crest"]["plateau_centre_px"]),
            "head_tip": dict(jp["head_tip"], direction_deg=landmarks["head_tip"]["direction_deg"],
                             direction_definition=dir_def,
                             direction_alternatives_deg=landmarks["head_tip"]["direction_alternatives_deg"]),
            "inner_deepest": jp["inner_deepest"],
            "trough_level": landmarks["trough_level"],
            "claw_rightmost": jp["claw_rightmost"],
            "junction_near_wave": jp["junction_near_wave"],
            "back_left_dip": jp["back_left_dip"],
        },
        "remeasure": rem,
    }
    jpn = {"back": "背", "head": "波頭", "inner_arc": "内側の弧"}
    for name in ("back", "head", "inner_arc"):
        p = segs[name]["pts"]
        src = [str(s) for s in segs[name]["src"]]
        out["segments"].append({
            "name": name, "jp": jpn[name],
            "points_px": [[round(float(x), 2) + 0.0, round(float(y), 2) + 0.0] for x, y in p],
            "points_H": [[round(float(X), 6), round(float(Z), 6)] for X, Z in F.pts_px_to_H(p)],
            "source": src,
            "in_S7": [s in ("traced", "claw_root_bridge") for s in src],
        })
        cnt = {s: src.count(s) for s in sorted(set(src))}
        sp_real = float(np.mean(np.hypot(*np.diff(p, axis=0).T)))
        metrics.setdefault("segments", {})[name] = {"n_points": len(p), "length_px": float(L.arclength(p)[-1]),
                                                     "spacing_px": sp_real, "source_counts": cnt}
        log("segment %-9s: %4d points, length %.0f px, spacing %.4f px, sources %s" % (name, len(p), L.arclength(p)[-1], sp_real, cnt))
    paths.write_json(out_json, out)
    log("wrote", out_json)

    # ---- images -----------------------------------------------------------------------------
    with bootstrap.Timer("images"):
        files = R.make_all(out_dir, img, M, P, F, segs, landmarks, spectrum, plateau, vis_raw, vis_traced,
                           s8_prof, sl_s, sl, bp, bs, inside_rb, S, j_idx, sens_traces, compat_curves)
    metrics["images"] = files
    metrics["runtime_s"] = time.perf_counter() - t_all
    paths.write_json(os.path.join(out_dir, "metrics.json"), metrics)
    log("wrote", os.path.join(out_dir, "metrics.json"))
    bootstrap.finish(True, "method A base contour written (%.0f s)" % (time.perf_counter() - t_all))


if __name__ == "__main__":
    main()
