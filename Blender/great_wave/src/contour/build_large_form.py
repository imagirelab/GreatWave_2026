"""LARGE-FORM base contour: curvature-limited regularisation of the finger-scale base contour.

Run (headless, one command regenerates everything):
    & "G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1" src/contour/build_large_form.py
Options (after '--', via -ScriptArgs):
    --params <json>   other parameter file (default: large_form_params.json next to this file)
    --tag <name>      trial run: everything goes to results/step1_prepare/contour_large_form/trial_<name>/,
                      nothing under target/ is touched
    --no-images       numbers and json only (also works without bpy, e.g. with Blender's python.exe)
    --radii a,b,c     trial runs only: other ball radii (e.g. the stability test 165,180,200)
    --official-order-only   trial runs only: skip the other morphological order

Input  : target/base_contour_finger_scale.json (the judged finger-scale contour of build_base_contour.py), the
         painting (pictures only), results/step1_prepare/contour_final/base_contour_alt_sky_silhouette.json.
Outputs: target/base_contour.json (OFFICIAL large-form contour, schema gw.base_contour.v1),
         target/base_contour_overlay.png, target/large_form_variants/*.json,
         results/step1_prepare/contour_large_form/ (pictures, plots, metrics.json, comparison contours).
Same parameter file + same finger-scale file -> byte-identical json.

Definition (no hand tuning, see large_form_params.json for every number):
  1. The finger-scale contour is closed to a region (body inside): both ends are extended along their end tangents,
     the region is closed far below the picture, and rasterised at full resolution (pixel centre inside the polygon).
  2. Morphological CLOSING then OPENING with a disc of radius r (exact Euclidean distance transforms).  The other
     order is computed too and reported: it is unstable, the notches between the lobes act as constrictions and the
     opening removes the tip lobe for every r >= 100 px and the whole lower block of the head at r = 150 px (see
     morph_order in the parameter file).
  3. The boundary is re-extracted: crack following, every vertex moved onto the level set 'distance = r' of the last
     distance field (sub-pixel), 1 px resampling, light arclength Gaussian.
  4. The ORIGINAL line is kept wherever the regularised one is closer than keep_tol (0.15 % of image height) AND the
     original line itself turns no faster than the ball (spacing / r per S8 sample); smooth cross-fades in between.
  5. Flags: finger-scale flag where the point still lies on the finger-scale line ('traced', or
     'offset_from_visible_edge' = the CONSTRUCTED left end of the back, see build_base_contour.py), 'large_form_bridge'
     where the regularisation moved it ('large_form_bridge' always wins over an inherited flag), completed_* always
     carried over (in_S7 = false).  Landmarks, 3 segments, 2 px spacing.
     The flags are decided on the 1 px polyline (distance <= label_tol); the 2 px resampling and the rounding to
     0.001 px come afterwards, so a flagged point of the json may exceed label_tol by a small epsilon (the measured
     maximum is written into the json, key source_flags).
  6. 'pending_user_confirmation' / 'pending_stretches' are inherited from the finger-scale file: the x-range of the back
     that depends on the pending left-end reading (index range and flag counts are recomputed for this file).
"""
import math
import os
import sys

import numpy as np

_SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gw import bootstrap, paths, frame, draw, plot                  # noqa: E402
from gw import profile_metrics as PM                                # noqa: E402
from contour import method_a_lib as LA                              # noqa: E402
from contour import build_base_contour as BB                        # noqa: E402  (helpers only; its main() is not run)

log = bootstrap.log
HERE = os.path.dirname(os.path.abspath(__file__))
SEG_NAMES = BB.SEG_NAMES
SEG_JP = BB.SEG_JP
COMPLETED = BB.COMPLETED
P = BB.P
NOTE_KEY = "note_large_form_decision"
NOTE_TEXT = ("FINGER-SCALE reference contour (single hook claws removed, foam lobes kept). Until 2026-09-20 this was "
             "target/base_contour.json. Since the orchestrator's large-form decision (to be confirmed by the user) the "
             "OFFICIAL S5/S7/S8 target is target/base_contour.json = the LARGE-FORM contour derived from this file by "
             "src/contour/build_large_form.py; this file stays the reference for later claw / foam placement. The key "
             "'official' below is the judge's original flag and is kept unchanged; geometry and all other keys are "
             "unchanged. Rebuilt by src/contour/build_base_contour.py (which writes this path now).")


# ====================================================================== input
def is_large_form(j):
    return isinstance(j, dict) and ("r_px" in j or "derived_from" in j)


def ensure_finger_scale_file(cfg, official):
    """Path of the finger-scale file.  Official run: make sure it exists under its new name and carries the note."""
    fpath = os.path.join(paths.PROJECT_ROOT, P(cfg, "finger_scale_file"))
    if not os.path.isfile(fpath):
        old = paths.BASE_CONTOUR_JSON
        j = paths.read_json(paths.require_file(old))
        if is_large_form(j):
            raise FileNotFoundError("%s is missing and %s already holds a large-form contour; rebuild the finger-scale "
                                    "file with src/contour/build_base_contour.py" % (fpath, old))
        if not official:
            log("INPUT trial run: using the finger-scale contour still stored in", paths.norm(old))
            return old
        log("INPUT moving the finger-scale contour", paths.norm(old), "->", paths.norm(fpath))
        paths.write_json(fpath, with_note(j))
        return fpath
    if official:
        j = paths.read_json(fpath)
        if is_large_form(j):
            raise ValueError("%s is not a finger-scale contour" % fpath)
        if j.get(NOTE_KEY) != NOTE_TEXT:
            log("INPUT adding the note key to", paths.norm(fpath))
            paths.write_json(fpath, with_note(j))
    return fpath


def with_note(j):
    out = {}
    for k, v in j.items():
        if k == NOTE_KEY:
            continue
        out[k] = v
        if k == "built_by":
            out[NOTE_KEY] = NOTE_TEXT
    if NOTE_KEY not in out:
        out[NOTE_KEY] = NOTE_TEXT
    return out


def load_contour(path):
    j = paths.read_json(path)
    by = {s["name"]: s for s in j["segments"]}
    pts, lab, seg = [], [], []
    for k, nm in enumerate(SEG_NAMES):
        p = np.asarray(by[nm]["points_px"], np.float64)
        l_ = list(by[nm]["source"])
        if k:
            p, l_ = p[1:], l_[1:]
        pts.append(p)
        lab += l_
        seg += [nm] * len(p)
    n_back, n_head = len(by["back"]["points_px"]), len(by["head"]["points_px"])
    return {"json": j, "pts": np.vstack(pts), "lab": np.array(lab, dtype=object), "seg": np.array(seg, dtype=object),
            "i_crest": n_back - 1, "i_tip": n_back + n_head - 2, "path": paths.norm(path)}


# ====================================================================== region + morphology
def build_region(O, r_max, cfg):
    """Closed region (body = True) on a canvas that contains the contour plus a margin.  -> (mask, (ox, oy), info)"""
    k = P(cfg, "end_tangent_len_px")
    s = LA.arclength(O)
    a = LA.interp_at(O, s, np.array([k]))[0]
    b = LA.interp_at(O, s, np.array([s[-1] - k]))[0]
    t0 = (O[0] - a) / np.hypot(*(O[0] - a))
    t1 = (O[-1] - b) / np.hypot(*(O[-1] - b))
    ext = 6.0 * r_max
    A = O[0] + ext * t0
    B = O[-1] + ext * t1
    pad_x, pad_top, pad_bot = 2 * r_max + 60, r_max + 40, 2 * r_max + 60
    x0, x1 = int(math.floor(O[:, 0].min() - pad_x)), int(math.ceil(O[:, 0].max() + pad_x))
    y0, y1 = int(math.floor(O[:, 1].min() - pad_top)), int(math.ceil(O[:, 1].max() + pad_bot))
    far = 1.0e5
    poly = np.vstack([A, O, B, [B[0], far], [A[0], far]])
    M = draw.polygon_mask((y1 - y0, x1 - x0), poly - np.array([x0, y0], np.float64))
    info = {"canvas_px": [x0, y0, x1, y1], "start_tangent_deg": float(np.degrees(np.arctan2(-t0[1], t0[0]))),
            "end_tangent_deg": float(np.degrees(np.arctan2(-t1[1], t1[0]))), "extension_px": ext}
    if A[0] > x0 or B[0] < x1:
        raise RuntimeError("tangent extensions do not leave the canvas sideways: %s %s" % (A, B))
    return M, (x0, y0), info


def morph(M, r, order):
    """open_close / close_open with a disc of radius r.  -> (result mask, last distance field)
    The boundary of the result is the level set D = r of the returned field (sub-pixel)."""
    cap = int(math.ceil(r)) + 3
    if order == "open_close":
        E = LA.edt_capped(M, cap) > r                       # erosion
        Op = ~(LA.edt_capped(~E, cap) > r)                  # dilation  -> opening
        Dl = ~(LA.edt_capped(~Op, cap) > r)                 # dilation
        D = LA.edt_capped(Dl, cap)                          # erosion   -> closing
        return D > r, D
    if order == "close_open":
        Dl = ~(LA.edt_capped(~M, cap) > r)
        C = LA.edt_capped(Dl, cap) > r
        E = LA.edt_capped(C, cap) > r
        D = LA.edt_capped(~E, cap)
        return ~(D > r), D
    raise ValueError("unknown morph order %r" % order)


def extract_boundary(mask, D, r, origin, sigma_px):
    """Left canvas edge -> right canvas edge boundary (body on the right hand side), sub-pixel on the level set
    D = r, resampled at 1 px and lightly smoothed.  Image px coordinates."""
    h, w = mask.shape
    col = mask[:, 0]
    if col[0] or not col.any():
        raise RuntimeError("the body does not cross the left canvas edge as expected")
    yb = int(np.argmax(col))

    def outside(x, y):
        return bool(mask[min(max(y, 0), h - 1), min(max(x, 0), w - 1)])
    v = LA.trace_cracks(mask, (0, yb), 0, lambda x, y, n: x >= w or y >= h or y <= 0, max_steps=200000, outside=outside)
    if v[-1, 0] < w:
        raise RuntimeError("boundary trace ended at %s instead of the right canvas edge" % (v[-1],))
    p = v.astype(np.float64)
    ok = (p[:, 0] > 3) & (p[:, 0] < w - 3) & (p[:, 1] > 3) & (p[:, 1] < h - 3)
    p = p[ok]
    Df = D.astype(np.float32)
    for _ in range(3):                                      # Newton steps onto the level set D = r (|grad D| ~ 1)
        d0 = BB.bilinear(Df, p[:, 0], p[:, 1])
        gx = 0.5 * (BB.bilinear(Df, p[:, 0] + 1, p[:, 1]) - BB.bilinear(Df, p[:, 0] - 1, p[:, 1]))
        gy = 0.5 * (BB.bilinear(Df, p[:, 0], p[:, 1] + 1) - BB.bilinear(Df, p[:, 0], p[:, 1] - 1))
        g2 = np.maximum(gx * gx + gy * gy, 0.25)
        step = ((r - d0) / g2)[:, None] * np.stack([gx, gy], axis=1)
        ln = np.hypot(step[:, 0], step[:, 1])
        step *= np.minimum(1.0, 1.5 / np.maximum(ln, 1e-9))[:, None]
        p = p + step
    resid = np.abs(BB.bilinear(Df, p[:, 0], p[:, 1]) - r)
    seg = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
    p = p[np.concatenate([[True], seg > 1e-6])]
    p1 = BB.resample_1px(p)
    sm = LA.gaussian_smooth(p1, sigma_px, 1.0)
    sm = BB.resample_1px(sm)
    return sm + np.array(origin, np.float64), {"n_crack_vertices": int(len(v)), "level_residual_px_p95": float(np.percentile(resid, 95)),
                                                "level_residual_px_max": float(resid.max())}


# ====================================================================== polyline helpers
def project(q, pts, chunk=1024):
    """Nearest point of the polyline pts for every query point.
    -> dist, arclength position on pts, projected point, signed distance (+ = query on the LEFT of the travel
       direction = sky side of the contour)."""
    q = np.atleast_2d(np.asarray(q, np.float64))
    a, b = pts[:-1], pts[1:]
    ab = b - a
    l2 = np.maximum((ab ** 2).sum(1), 1e-12)
    s = LA.arclength(pts)
    seg_len = np.sqrt(l2)
    dist = np.empty(len(q))
    spos = np.empty(len(q))
    proj = np.empty((len(q), 2))
    sign = np.empty(len(q))
    for i in range(0, len(q), chunk):
        qq = q[i:i + chunk]
        t = np.clip(((qq[:, None, :] - a[None]) * ab[None]).sum(2) / l2[None], 0.0, 1.0)
        c = a[None] + t[:, :, None] * ab[None]
        d2 = ((qq[:, None, :] - c) ** 2).sum(2)
        k = d2.argmin(1)
        ar = np.arange(len(qq))
        dist[i:i + chunk] = np.sqrt(d2[ar, k])
        spos[i:i + chunk] = s[k] + t[ar, k] * seg_len[k]
        proj[i:i + chunk] = c[ar, k]
        nl = np.stack([ab[k, 1], -ab[k, 0]], axis=1) / seg_len[k][:, None]       # left normal (px coords, y down)
        sign[i:i + chunk] = np.sign(((qq - c[ar, k]) * nl).sum(1))
    return dist, spos, proj, dist * sign


def sliding_turn(pts, delta):
    """|turn| between the chords [s - delta, s] and [s, s + delta] at every vertex (deg); 0 near the ends."""
    s = LA.arclength(pts)
    ok = (s >= delta) & (s <= s[-1] - delta)
    a = LA.interp_at(pts, s, np.clip(s - delta, 0, s[-1]))
    b = LA.interp_at(pts, s, np.clip(s + delta, 0, s[-1]))
    d0 = np.degrees(np.arctan2(-(pts[:, 1] - a[:, 1]), pts[:, 0] - a[:, 0]))
    d1 = np.degrees(np.arctan2(-(b[:, 1] - pts[:, 1]), b[:, 0] - pts[:, 0]))
    t = LA.angle_diff_deg(d1, d0)
    return np.where(ok, t, 0.0), s


def s8_profile(pts, spacing, n_phase):
    """Spec S8 on the WHOLE polyline (continuous across the joints and the head tip): for every phase, samples every
    `spacing` of arclength, tangent_j = chord j -> j+1, junction value = tangent_j - tangent_j-1 (deg, signed, + = turning
    towards +Z / counter-clockwise).  -> (s of the junctions, signed turn, phase index), sorted by s."""
    s = LA.arclength(pts)
    ss, tt, pp = [], [], []
    for ph in range(n_phase):
        t = np.arange(spacing * ph / n_phase, s[-1] + 1e-9, spacing)
        if len(t) < 3:
            continue
        q = LA.interp_at(pts, s, t)
        ang = np.degrees(np.arctan2(-np.diff(q[:, 1]), np.diff(q[:, 0])))
        ss.append(t[1:-1])
        tt.append(LA.angle_diff_deg(ang[1:], ang[:-1]))
        pp.append(np.full(len(t) - 2, ph))
    ss, tt, pp = np.concatenate(ss), np.concatenate(tt), np.concatenate(pp)
    o = np.argsort(ss, kind="stable")
    return ss[o], tt[o], pp[o]


def dilate_1d(mask, n):
    if n <= 0:
        return mask.copy()
    c = np.concatenate([[0], np.cumsum(mask.astype(np.int64))])
    i = np.arange(len(mask))
    lo, hi = np.clip(i - n, 0, len(mask)), np.clip(i + n + 1, 0, len(mask))
    return (c[hi] - c[lo]) > 0


def moving_mean(v, n):
    c = np.concatenate([[0.0], np.cumsum(v)])
    i = np.arange(len(v))
    lo, hi = np.clip(i - n, 0, len(v)), np.clip(i + n + 1, 0, len(v))
    return (c[hi] - c[lo]) / (hi - lo)


def dist_to_true(mask):
    """distance (in samples) of every index to the nearest True index (inf if none)."""
    n = len(mask)
    idx = np.arange(n)
    big = 10 ** 9
    left = np.where(mask, idx, -big)
    left = np.maximum.accumulate(left)
    right = np.where(mask, idx, big)
    right = np.minimum.accumulate(right[::-1])[::-1]
    return np.minimum(idx - left, right - idx).astype(np.float64)


# ====================================================================== composition of one variant
def compose(R_full, O, F, cfg, r):
    """Blend the regularised line R with the original line O.  -> dict (1 px polyline P + per-point data)."""
    h1 = float(F.pct_h_to_px(1.0))
    # trim R to the extent of O: from its crossing of the left frame edge x = 0 to the foot of O's last point
    sR = LA.arclength(R_full)
    k0 = int(np.nonzero((R_full[:-1, 0] < 0.0) & (R_full[1:, 0] >= 0.0))[0][0])
    f0 = (0.0 - R_full[k0, 0]) / (R_full[k0 + 1, 0] - R_full[k0, 0])
    s0 = sR[k0] + f0 * (sR[k0 + 1] - sR[k0])
    _, s1, _, _ = project(O[-1:], R_full)
    t = np.linspace(s0, s1[0], max(2, int(round(s1[0] - s0)) + 1))
    R = LA.interp_at(R_full, sR, t)
    R[0, 0] = 0.0
    d, sO, Oproj, dsig = project(R, O)
    sO = np.maximum.accumulate(sO)                          # monotone parameter on O (guards against back-jumps)
    # --- where must the regularised line be used?
    keep_tol = float(F.pct_h_to_px(P(cfg, "keep_tol_pct_h")))
    far = d > keep_tol
    delta = float(F.pct_h_to_px(P(cfg, "s8_spacing_pct_h")))
    turn_O, s_O = sliding_turn(O, delta)
    limit = math.degrees(delta / r)
    if P(cfg, "keep_turn_rule") == "ball":
        rough_O = np.abs(turn_O) > limit
        rough = np.interp(sO, s_O, rough_O.astype(np.float64)) > 0.0
        rough = dilate_1d(rough, int(round(delta)))
    else:
        rough = np.zeros(len(R), bool)
    core = far | rough
    # --- hysteresis: extend every changed stretch until both lines coincide within the raster noise
    seam_tol = float(F.pct_h_to_px(P(cfg, "seam_tol_pct_h")))
    max_exp = int(round(float(F.pct_h_to_px(P(cfg, "seam_max_expand_pct_h")))))
    dm = moving_mean(d, int(round(0.5 * h1)))
    changed = core.copy()
    for (i, j) in BB.runs_of(core):
        k = i
        while k > 0 and i - k < max_exp and dm[k - 1] > seam_tol:
            k -= 1
        changed[k:i] = True
        k = j
        while k < len(core) - 1 and k - j < max_exp and dm[k + 1] > seam_tol:
            k += 1
        changed[j:k + 1] = True
    L = float(F.pct_h_to_px(P(cfg, "seam_blend_len_pct_h")))
    u = np.clip(dist_to_true(changed) / L, 0.0, 1.0) if changed.any() else np.ones(len(R))
    w = u * u * (3.0 - 2.0 * u)
    Pp = R + w[:, None] * (Oproj - R)
    if w[0] == 1.0:
        Pp[0] = O[0]
    Pp[0, 0] = 0.0                                          # the contour starts ON the left frame edge
    if w[-1] == 1.0:
        Pp[-1] = O[-1]
    # --- flags
    lab_O_at = lambda sv: np.clip(np.searchsorted(s_O, sv), 0, len(s_O) - 1)
    return {"R": R, "P": Pp, "w": w, "d_R_to_O": d, "dsig_R_to_O": dsig, "sO": sO, "core_far": far, "core_rough": rough,
            "changed": changed, "turn_limit_deg": limit, "turn_O": turn_O, "s_O": s_O, "lab_index": lab_O_at(sO)}


def finalise(comp, Oc, F, cfg):
    """Flags, landmarks, segments (2 px) of a composed polyline."""
    O, labO = Oc["pts"], Oc["lab"]
    Pp = comp["P"]
    p1 = BB.resample_1px(Pp)
    d, sO, _, dsig = project(p1, O)
    s_O = LA.arclength(O)
    idx = np.clip(np.searchsorted(s_O, sO), 0, len(s_O) - 1)
    prev = np.clip(idx - 1, 0, len(s_O) - 1)
    idx = np.where(np.abs(s_O[prev] - sO) < np.abs(s_O[idx] - sO), prev, idx)
    l_near = labO[idx]
    label_tol = float(F.pct_h_to_px(P(cfg, "label_tol_pct_h")))
    on_line = d <= label_tol
    # a stretch counts as 'still on the finger-scale line' only if it is at least label_min_run long; shorter runs are places
    # where the regularised line merely CROSSES the finger-scale line
    min_run = float(F.pct_h_to_px(P(cfg, "label_min_run_pct_h")))
    for (i, j) in BB.runs_of(on_line):
        if j - i + 1 < min_run:
            on_line[i:j + 1] = False
    lab = np.where(np.isin(l_near, COMPLETED), l_near, np.where(on_line, l_near, "large_form_bridge")).astype(object)
    # completed flags must form ONE run at the end (a bridge point whose nearest original point is completed stays completed)
    comp_idx = np.nonzero(np.isin(lab, COMPLETED))[0]
    if comp_idx.size and not np.all(np.diff(comp_idx) == 1):
        first = comp_idx[0]
        for k in range(first, len(lab)):
            if lab[k] not in COMPLETED:
                lab[k] = "completed_occluded"
    s1 = LA.arclength(p1)
    vis = ~np.isin(lab, COMPLETED)
    i_vis_end = int(np.nonzero(vis)[0][-1])
    sig = float(F.pct_h_to_px(P(cfg, "landmark_sigma_pct_h")))
    sm = LA.gaussian_smooth(p1, sig, 1.0)
    i_c = int(np.argmin(sm[:i_vis_end + 1, 1]))
    i_top = int(np.argmin(p1[:i_vis_end + 1, 1]))
    # head tip: vertex of a parabola through x(s) over the run within tip_tol of the maximum
    i_t0 = i_c + int(np.argmax(p1[i_c:i_vis_end + 1, 0]))
    tol_t = float(F.pct_h_to_px(P(cfg, "tip_tol_pct_h")))
    a = i_t0
    while a > i_c and p1[a - 1, 0] >= p1[i_t0, 0] - tol_t:
        a -= 1
    b = i_t0
    while b < i_vis_end and p1[b + 1, 0] >= p1[i_t0, 0] - tol_t:
        b += 1
    s_t = float(s1[i_t0])
    fit = {"run_s_px": [float(s1[a]), float(s1[b])], "run_y_px": [float(p1[a, 1]), float(p1[b, 1])], "used_parabola": False}
    if b - a >= 6:
        ss = s1[a:b + 1] - s1[i_t0]
        c2, c1, _c0 = np.polyfit(ss, p1[a:b + 1, 0], 2)
        if c2 < 0:
            sv = -c1 / (2 * c2)
            if ss[0] <= sv <= ss[-1]:
                s_t = float(s1[i_t0] + sv)
                fit["used_parabola"] = True
    tip = LA.interp_at(p1, s1, np.array([s_t]))[0]
    i_t = int(np.searchsorted(s1, s_t))
    i_d = i_t + int(np.argmin(sm[i_t:i_vis_end + 1, 0]))
    i_dstrict = i_t + int(np.argmin(p1[i_t:i_vis_end + 1, 0]))
    tol = P(cfg, "plateau_tol_px")
    top_run = np.nonzero(p1[:i_t, 1] <= p1[i_top, 1] + tol)[0]
    deep_run = i_t + np.nonzero(p1[i_t:i_vis_end + 1, 0] <= p1[i_dstrict, 0] + tol)[0]
    # segments: back [0, i_c], head [i_c, tip], inner_arc [tip, end]
    head_p = np.vstack([p1[i_c:i_t], tip]) if s1[i_t] > s_t else np.vstack([p1[i_c:i_t + 1], tip])
    head_l = np.concatenate([lab[i_c:i_t], lab[i_t:i_t + 1]]) if s1[i_t] > s_t else np.concatenate([lab[i_c:i_t + 1], lab[i_t:i_t + 1]])
    k_in = i_t if s1[i_t] > s_t else i_t + 1
    inner_p = np.vstack([tip, p1[k_in:]])
    inner_l = np.concatenate([lab[k_in:k_in + 1], lab[k_in:]])
    sp = P(cfg, "sample_spacing_px")
    segs = {}
    for nm, (q, ql) in (("back", (p1[:i_c + 1], lab[:i_c + 1])), ("head", (head_p, head_l)), ("inner_arc", (inner_p, inner_l))):
        keep = np.concatenate([[True], np.hypot(np.diff(q[:, 0]), np.diff(q[:, 1])) > 1e-9])
        q, ql = q[keep], ql[keep]
        rp, rl, actual = BB.resample_exact(q, ql, sp)
        rp = np.round(rp, 3)
        segs[nm] = {"pts": rp, "lab": rl, "actual_spacing_px": float(actual), "length_px": float(LA.arclength(q)[-1])}
    segs["head"]["pts"][0] = segs["back"]["pts"][-1]
    segs["inner_arc"]["pts"][0] = segs["head"]["pts"][-1]
    # completed labels after resampling must still be a single final run starting at a completed point
    full = np.vstack([segs["back"]["pts"], segs["head"]["pts"][1:], segs["inner_arc"]["pts"][1:]])
    labf = np.concatenate([segs["back"]["lab"], segs["head"]["lab"][1:], segs["inner_arc"]["lab"][1:]])
    segf = np.array(["back"] * len(segs["back"]["pts"]) + ["head"] * (len(segs["head"]["pts"]) - 1)
                    + ["inner_arc"] * (len(segs["inner_arc"]["pts"]) - 1), dtype=object)
    n_back, n_head = len(segs["back"]["pts"]), len(segs["head"]["pts"])
    dev, _, _, devs = project(full, O)
    for nm in SEG_NAMES:
        m = segf == nm
        dd = dev[m]
        if nm != "back":
            first = int(np.nonzero(m)[0][0]) - 1
            dd = np.concatenate([[dev[first]], dd])
        segs[nm]["dev_px"] = np.round(dd, 2)
    return {"segs": segs, "full": full, "lab": labf, "seg": segf, "i_c": n_back - 1, "i_t": n_back + n_head - 2,
            "crest_px": segs["back"]["pts"][-1].copy(), "tip_px": segs["head"]["pts"][-1].copy(), "deep_px": np.round(p1[i_d], 3),
            "dev_px": dev, "dev_signed_px": devs,
            "lm": {"crest_strict_px": p1[i_top].tolist(), "crest_plateau_x_px": [float(p1[top_run, 0].min()), float(p1[top_run, 0].max())],
                   "deep_strict_px": p1[i_dstrict].tolist(), "deep_run_y_px": [float(p1[deep_run, 1].min()), float(p1[deep_run, 1].max())],
                   "tip_fit": fit, "vis_end_px": p1[i_vis_end].tolist()}}


# ====================================================================== measurements
def stats_pct(d_px, F, pts=None):
    d = np.asarray(d_px, np.float64)
    if d.size == 0:
        return {"n": 0, "mean": None, "p95": None, "max": None}
    v = F.px_to_pct_h(d)
    out = {"n": int(d.size), "mean": round(float(v.mean()), 4), "p95": round(float(np.percentile(v, 95)), 4), "max": round(float(v.max()), 4)}
    if pts is not None:
        k = int(np.argmax(d))
        out["max_at_px"] = [round(float(pts[k, 0]), 1), round(float(pts[k, 1]), 1)]
    return out


def inscribed_diameter_at(pts, i_tip, skip_px=6.0):
    """Diameter of the largest circle that touches the contour at the tip from the body side and stays inside the
    contour (the definition tests/test_mesh.py uses for the G3 rim thickness, applied to the 2-D section)."""
    s = LA.arclength(pts)
    p = pts[i_tip]
    a = LA.interp_at(pts, s, np.array([max(0.0, s[i_tip] - 4.0), min(s[-1], s[i_tip] + 4.0)]))
    t = a[1] - a[0]
    t /= np.hypot(*t)
    n_in = np.array([-t[1], t[0]])                          # right of the travel direction = body side (px, y down)
    q = pts[np.abs(s - s[i_tip]) > skip_px] - p
    along = q @ n_in
    ok = along > 1e-9
    rho = (q[ok] ** 2).sum(1) / (2.0 * along[ok])
    k = int(np.argmin(rho))
    return 2.0 * float(rho[k]), (pts[np.abs(s - s[i_tip]) > skip_px][ok][k]).tolist(), (p + rho[k] * n_in).tolist()


def level_crossings(pts, y):
    out = []
    for k in range(len(pts) - 1):
        y0, y1 = pts[k, 1], pts[k + 1, 1]
        if (y0 - y) * (y1 - y) < 0 or y0 == y:
            t = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
            out.append((k, float(pts[k, 0] + t * (pts[k + 1, 0] - pts[k, 0]))))
    return out


def measure_variant(V, Oc, F, cfg, J):
    """All numbers asked for one variant.  V = finalise() result, J = its json dict (for the test library)."""
    full, lab, seg, i_c, i_t = V["full"], V["lab"], V["seg"], V["i_c"], V["i_t"]
    out = {}
    h1 = float(F.pct_h_to_px(1.0))
    Hpx = float(F.px_per_H)
    s = LA.arclength(full)
    vis = ~np.isin(lab, COMPLETED)
    i_end = int(np.nonzero(vis)[0][-1])
    # ---- own S8, whole contour, across the tip
    sp = float(F.pct_h_to_px(P(cfg, "s8_spacing_pct_h")))
    js, jt, jp = s8_profile(full, sp, P(cfg, "s8_n_phases"))
    q = LA.interp_at(full, s, js)
    seg_of = np.where(js <= s[i_c], "back", np.where(js <= s[i_t], "head", np.where(js <= s[i_end], "inner_arc", "completed")))
    tipw = float(F.pct_h_to_px(P(cfg, "tip_window_pct_h")))
    s8 = {"spacing_px": sp, "n_phases": P(cfg, "s8_n_phases"), "per_segment": {}}
    for nm in ("back", "head", "inner_arc", "completed"):
        m = seg_of == nm
        if not m.any():
            continue
        k = int(np.argmax(np.abs(jt[m])))
        s8["per_segment"][nm] = {"max_deg": round(float(np.abs(jt[m]).max()), 2), "n_junctions": int(m.sum()),
                                 "n_ge_15": int((np.abs(jt[m]) >= 15.0).sum()), "n_ge_target": int((np.abs(jt[m]) > P(cfg, "s8_target_deg")).sum()),
                                 "max_at_px": [round(float(v), 1) for v in q[m][k]], "p95_deg": round(float(np.percentile(np.abs(jt[m]), 95)), 2)}
    mv = seg_of != "completed"
    s8["max_visible_deg"] = round(float(np.abs(jt[mv]).max()), 2)
    s8["max_whole_deg"] = round(float(np.abs(jt).max()), 2)
    k = int(np.argmax(np.abs(jt)))
    s8["max_whole_at_px"] = [round(float(v), 1) for v in q[k]]
    mt = np.abs(js - s[i_t]) <= tipw
    s8["tip_window_pm_pct_h"] = P(cfg, "tip_window_pct_h")
    s8["tip_window_max_deg"] = round(float(np.abs(jt[mt]).max()), 2) if mt.any() else None
    s8["tip_window_sum_signed_deg_phase0"] = round(float(jt[mt & (jp == 0)].sum()), 2) if mt.any() else None
    st, _ = sliding_turn(full, sp)
    s8["sliding_all_phases_max_deg"] = round(float(np.abs(st).max()), 2)
    s8["design_turn_of_ball_deg"] = None
    out["own_S8"] = s8
    out["_s8_curve"] = (js, jt, jp, seg_of)
    # ---- same-definition re-measurement as the finger-scale report (S1 S2 S4 S5 thickness)
    sig_px = float(F.pct_h_to_px(P(cfg, "landmark_sigma_pct_h")))
    mc = BB.measure_contour(full, lab, seg, i_c, i_t, F, cfg, sig_px)
    out["judge_definitions"] = {"S1": mc["S1"], "S2": mc["S2"],
                                "S4": {k2: v for k2, v in mc["S4"].items() if not k2.startswith("_") and not k2.startswith("slope_table")},
                                "S5": {k2: v for k2, v in mc["S5"].items() if not k2.startswith("_")},
                                "head_thickness": mc["head_thickness"], "tip_turn_clockwise_deg": mc["tip_turn_clockwise_deg"],
                                "segments": mc["segments"]}
    dia, touch, centre = inscribed_diameter_at(full, i_t)
    out["rim_like_thickness_at_tip"] = {"largest_inscribed_circle_diameter_px": round(dia, 1), "pct_H": round(dia / Hpx * 100, 2),
                                        "second_contact_px": [round(v, 1) for v in touch], "centre_px": [round(v, 1) for v in centre],
                                        "spec_G3_limit_pct_H": P(cfg, "rim_limit_pct_H"),
                                        "definition": "diameter of the largest circle tangent to the contour at the head tip from the body side that stays inside the contour (2-D version of the G3 definition in tests/test_mesh.py)"}
    # ---- tip vs the spec S6 claw point and vs the finger-scale tip
    tip = V["tip_px"]
    s6 = np.array(F.pct_to_px(59.2, 33.0), np.float64)
    ft = Oc["pts"][Oc["i_tip"]]
    out["tip"] = {"px": tip.tolist(), "pct": [round(float(v), 3) for v in F.px_to_pct(tip[0], tip[1])],
                  "H": [round(float(v), 5) for v in F.px_to_H(tip[0], tip[1])],
                  "vs_spec_S6_claw_point_pct_h": {"dx": round(float(F.px_to_pct_h(tip[0] - s6[0])), 3), "dy_down_positive": round(float(F.px_to_pct_h(tip[1] - s6[1])), 3),
                                                  "dist": round(float(F.px_to_pct_h(np.hypot(*(tip - s6)))), 3),
                                                  "tip_is_left_of_claw_point": bool(tip[0] < s6[0]), "tip_is_above_claw_point": bool(tip[1] < s6[1])},
                  "vs_finger_scale_tip_pct_h": {"dx": round(float(F.px_to_pct_h(tip[0] - ft[0])), 3), "dy_down_positive": round(float(F.px_to_pct_h(tip[1] - ft[1])), 3),
                                                "dist": round(float(F.px_to_pct_h(np.hypot(*(tip - ft)))), 3)},
                  "fit": V["lm"]["tip_fit"]}
    # ---- distance to the finger-scale contour, both directions, in_S7 points only
    O, labO, segO = Oc["pts"], Oc["lab"], Oc["seg"]
    visO = ~np.isin(labO, COMPLETED)
    dev, devs = V["dev_px"], V["dev_signed_px"]
    dO, _, _, dOs = project(O, full)
    dist = {"large_form_to_finger_scale": {}, "finger_scale_to_large_form": {}, "signed_large_form_minus_finger_scale": {}}
    for nm in SEG_NAMES:
        m = (seg == nm) & vis
        dist["large_form_to_finger_scale"][nm] = stats_pct(dev[m], F, full[m])
        mo = (segO == nm) & visO
        dist["finger_scale_to_large_form"][nm] = stats_pct(dO[mo], F, O[mo])
        v = F.px_to_pct_h(devs[m])
        dist["signed_large_form_minus_finger_scale"][nm] = {
            "mean": round(float(v.mean()), 4), "max_outside_painted_body": round(float(v.max()), 4), "max_inside_painted_body": round(float(-v.min()), 4),
            "share_outside_gt_0p15": round(float((v > 0.15).mean()), 4), "share_inside_gt_0p15": round(float((v < -0.15).mean()), 4)}
    cm = ~vis
    dist["completed_part_px"] = {"n": int(cm.sum()), "max_dev_px": round(float(dev[cm].max()), 3) if cm.any() else None,
                                 "n_moved_more_than_0p05_px": int((dev[cm] > 0.05).sum()) if cm.any() else 0,
                                 "note": "the completed part keeps its flags; its geometry is the finger-scale completion except for the cross-fade next to the junction with the visible inner arc"}
    dist["note"] = "% of image height; segments of the contour the points belong to; completed_* points excluded; signed: + = the large form lies on the sky side of the finger-scale line (body grown), - = inside the painted body (body cut)"
    out["distance_to_finger_scale_pct_h"] = dist
    cnt = {nm: {k2: int(((seg == nm) & (lab == k2)).sum()) for k2 in sorted(set(lab.tolist()))} for nm in SEG_NAMES}
    out["flag_counts"] = cnt
    out["share_of_visible_points_on_the_finger_scale_line"] = {nm: round(float(((lab != "large_form_bridge") & vis & (seg == nm)).sum() / max(1, ((seg == nm) & vis).sum())), 4) for nm in SEG_NAMES}
    # ---- widths
    z0 = float(F.pct_to_px(0, 74.7)[1])
    t0 = full[0] - LA.interp_at(full, s, np.array([5.0 * h1]))[0]          # left-end chord over 5 % (same window as S4 'left end')
    wd = {}
    for lv in P(cfg, "width_levels_pct_H"):
        y = z0 - lv / 100.0 * Hpx
        cr = level_crossings(full, y)
        xb = [x for k2, x in cr if k2 < i_c]
        xf = [(x, k2) for k2, x in cr if k2 >= i_c]
        e = {"y_px": round(y, 1), "x_back_px": round(xb[-1], 1) if xb else None, "back_inside_frame": bool(xb),
             "x_front_px": None, "x_outermost_px": None}
        if xf:
            xfr, kf = min(xf)
            e["x_front_px"] = round(xfr, 1)
            e["x_outermost_px"] = round(max(xf)[0], 1)
            tf_ = full[min(kf + 1, len(full) - 1)] - full[kf]
            e["front_slope_deg_from_horizontal"] = round(float(np.degrees(np.arctan2(abs(tf_[1]), abs(tf_[0])))), 1)
            e["x_front_shift_px_per_pct_h_of_level"] = round(float(h1 * abs(tf_[0]) / max(abs(tf_[1]), 1e-9)), 1)
            e["width_from_frame_edge_to_front_H"] = round(xfr / Hpx, 4)
            if xb:
                e["width_back_to_front_H"] = round((xfr - xb[-1]) / Hpx, 4)
                e["width_back_to_outermost_H"] = round((max(xf)[0] - xb[-1]) / Hpx, 4)
            elif t0[1] > 0 and t0[0] < 0:                    # the back descends towards the left frame edge (spec 7b makes sense)
                xe = float(full[0, 0] + (y - full[0, 1]) * t0[0] / t0[1])
                ln = float(F.px_to_pct_h(np.hypot(xe - full[0, 0], y - full[0, 1])))
                e["x_back_extrapolated_px"] = round(xe, 1)
                e["extrapolation_length_pct_h"] = round(ln, 2)
                if ln <= 10.0:
                    e["width_back_to_front_H_EXTRAPOLATED"] = round((xfr - xe) / Hpx, 4)
                else:
                    e["width_back_to_front_H_EXTRAPOLATED"] = None
                    e["why_no_width"] = "the back would have to be extrapolated over more than 10 % of image height outside the frame"
            else:
                e["why_no_width"] = "the back has left the frame and its left end does not descend towards the frame edge (sky_silhouette reading): no extrapolation"
        wd["%d_pct_H" % lv] = e
    wd["note"] = ("x_front = left-most crossing after the crest (body / cavity boundary, or the top of the head where the level passes above the cavity). The back leaves the frame at "
                  "about 51 % H: below that its x is a straight extrapolation along the chord of the first 5 % of the back (spec 7b) and the width is NOT a measurement. "
                  "x_front_shift_px_per_pct_h_of_level tells how ill-conditioned x_front is (a level that grazes a nearly horizontal stretch).")
    out["widths"] = wd
    # ---- test library on the json: json joints vs detection, S4, phi windows
    lib = {}
    try:
        m_js = PM.measure_base_contour(J)
        m_dt = PM.measure_base_contour(J, use_json_segmentation=False)
        lib["json_joints"] = lib_summary(m_js, F)
        lib["detection"] = lib_summary(m_dt, F)
        agree = {}
        for k2 in ("crest", "head_tip", "inner_deepest"):
            a, b = m_js["landmarks"].get(k2), m_dt["landmarks"].get(k2)
            if a is None or b is None:
                agree[k2] = None
                continue
            pa, pb = np.array(F.H_to_px(*a["H"]), np.float64), np.array(F.H_to_px(*b["H"]), np.float64)
            agree[k2] = {"json_px": [round(float(v), 2) for v in pa], "detected_px": [round(float(v), 2) for v in pb],
                         "dx_pct_h": round(float(F.px_to_pct_h(pb[0] - pa[0])), 4), "dy_pct_h": round(float(F.px_to_pct_h(pb[1] - pa[1])), 4),
                         "dist_pct_h": round(float(F.px_to_pct_h(np.hypot(*(pb - pa)))), 4), "arclength_diff_pct_h": round(float(PM.H_to_pct_h(b["s"] - a["s"])), 4)}
        lib["json_vs_detection"] = agree
        lib["json_vs_detection_max_dist_pct_h"] = max([v["dist_pct_h"] for v in agree.values() if v] or [float("nan")])
        lib["phi_windows"] = {}
        for a_, b_ in P(cfg, "phi_windows_pct_H"):
            ov = {"phi_skip_H": a_ / 100.0, "phi_len_H": (b_ - a_) / 100.0}
            lib["phi_windows"]["%g_to_%g_pct_H" % (a_, b_)] = {"json_joints_deg": PM.measure_base_contour(J, ov)["phi_deg"],
                                                               "detection_deg": PM.measure_base_contour(J, ov, use_json_segmentation=False)["phi_deg"]}
        ct, tp = np.array(m_dt["landmarks"]["crest"]["H"]), (np.array(m_dt["landmarks"]["head_tip"]["H"]) if m_dt["landmarks"]["head_tip"] else None)
        if tp is not None:
            lib["crest_to_tip_direction_deg"] = round(float(np.degrees(np.arctan2(tp[1] - ct[1], tp[0] - ct[0]))), 2)
        lib["ok"] = True
    except Exception as ex:                                  # shared code of another agent (being edited in parallel)
        lib["ok"] = False
        lib["error"] = repr(ex)
    out["test_library"] = lib
    return out


def json_measurements(mm):
    """compact copy of the numbers of one variant for its json file."""
    lib = mm["test_library"]
    jd = mm["judge_definitions"]
    jj = lib.get("json_joints") or {}
    return strip({
        "own_S8": {k: v for k, v in mm["own_S8"].items()},
        "distance_to_finger_scale_pct_h": mm["distance_to_finger_scale_pct_h"],
        "head_tip": mm["tip"],
        "head_thickness_behind_tip": jd["head_thickness"],
        "rim_like_thickness_at_tip": mm["rim_like_thickness_at_tip"],
        "S1_S2_same_definitions_as_finger_scale_report": {"S1": jd["S1"], "S2": jd["S2"]},
        "S5_direction_overhang_area_principal_axis_deg": jd["S5"].get("direction_deg"),
        "S5_direction_alternatives_deg": jd["S5"].get("direction_alternatives_deg"),
        "widths": mm["widths"],
        "flag_counts": mm["flag_counts"],
        "test_library": {"ok": lib.get("ok"), "json_vs_detection": lib.get("json_vs_detection"), "phi_windows": lib.get("phi_windows"),
                         "S4_json_joints": jj.get("S4"), "o_H": jj.get("o_H"), "cavity_depth_H": jj.get("cavity_depth_H"), "theta_deg": jj.get("theta_deg"),
                         "crest_to_tip_direction_deg": lib.get("crest_to_tip_direction_deg"), "S8_library": jj.get("S8")},
    })


def lib_summary(m, F):
    lm = m["landmarks"]
    s4 = {k: v for k, v in m["S4"].items() if k != "slope_curve"}
    return {"overhanging": m["overhanging"], "h_H": m["h"], "x_c_H": m["x_c"], "o_H": m["o"], "cavity_depth_H": m["cavity_depth"],
            "theta_deg": m["theta"], "phi_deg": m["phi_deg"], "S4": s4,
            "S8": {k: m["S8"].get(k) for k in ("max_tangent_diff_deg", "per_segment", "max_unexcluded_deg", "tip_turn_deg", "max_at")},
            "landmarks_px": {k: ([round(float(v), 2) for v in F.H_to_px(*lm[k]["H"])] if lm.get(k) else None)
                             for k in ("crest", "head_tip", "inner_deepest", "trough_end", "body_rightmost")},
            "crest_plateau": lm.get("crest_plateau"), "notes": m.get("notes")}


# ====================================================================== json
def strip(d):
    if isinstance(d, dict):
        return {k: strip(v) for k, v in d.items() if not str(k).startswith("_")}
    if isinstance(d, (list, tuple)):
        return [strip(v) for v in d]
    if isinstance(d, np.ndarray):
        return d.tolist()
    if isinstance(d, (np.floating, np.integer, np.bool_)):
        return d.item()
    return d


def contour_json(V, Oc, F, cfg, r, order, name, finger_rel, finger_sha, official, left_variant, comparison_only=None):
    fj = Oc["json"]

    def lm_json(p):
        h = F.px_to_H(p[0], p[1])
        pc = F.px_to_pct(p[0], p[1])
        return {"px": [float(p[0]), float(p[1])], "H": [round(float(h[0]), 6), round(float(h[1]), 6)],
                "pct": [round(float(pc[0]), 3), round(float(pc[1]), 3)]}

    def seg_json(nm):
        sg = V["segs"][nm]
        ptsH = np.round(F.pts_px_to_H(sg["pts"]), 6)
        return {"name": nm, "jp": SEG_JP[nm], "points_px": [[float(a), float(b)] for a, b in sg["pts"]],
                "points_H": [[float(a), float(b)] for a, b in ptsH], "source": [str(v) for v in sg["lab"]],
                "in_S7": [bool(v not in COMPLETED) for v in sg["lab"]], "actual_spacing_px": round(sg["actual_spacing_px"], 6),
                "dev_from_finger_scale_px": [float(v) for v in sg["dev_px"]]}
    z0 = float(F.pct_to_px(0, 74.7)[1])
    fl = fj.get("landmarks", {})
    # ---- flag descriptions: only flags that occur in THIS file; measured epsilon of the label tolerance (labels / meta data only)
    lab_all = np.asarray(V["lab"], dtype=object)
    flags_present = sorted(set(str(v) for v in lab_all.tolist()))
    inherited = ~np.isin(lab_all, COMPLETED) & (lab_all != "large_form_bridge")
    tol_px = float(F.pct_h_to_px(P(cfg, "label_tol_pct_h")))
    dev_inh = np.asarray(V["dev_px"], np.float64)[inherited]
    on_line_text = ("flags are decided on the 1 px polyline BEFORE the final 2 px resampling: distance to the finger-scale line <= label_tol = %g %% "
                    "of image height (%.3f px) in runs of at least %g %%; after the resampling and the rounding to 0.001 px a flagged point "
                    "of this file may exceed label_tol by a small epsilon (measured in this file over all %d points that carry an inherited "
                    "flag: max distance %.3f px, %d of them > label_tol)" % (P(cfg, "label_tol_pct_h"), tol_px, P(cfg, "label_min_run_pct_h"), int(dev_inh.size),
                                                                             float(dev_inh.max()) if dev_inh.size else 0.0, int((dev_inh > tol_px).sum())))
    flag_text = {
        "traced": "point lies on a TRACED stretch of the finger-scale line; " + on_line_text,
        BB.OFFSET_FLAG: "point lies on the CONSTRUCTED left end of the back of the finger-scale line (white_body_outline reading: no ink line is "
                        "drawn there, visible white-body edge shifted outwards by the measured ink-line width; inherited flag, same tolerance rule "
                        "as 'traced'); in_S7 = true, but the stretch depends on the pending decision 'back_left_variant' (see pending_stretches)",
        "claw_root_bridge": "point lies on a ball-smoothed chord of the finger-scale line (" + BB.SOURCE_FLAG_TEXT["claw_root_bridge"].split(".")[0]
                            + "); inherited flag, same tolerance rule as 'traced'",
        "large_form_bridge": "point moved by the large-form regularisation (in_S7 = true); wins over every inherited flag",
        "completed_occluded": "hidden behind the near wave, completed (in_S7 = false)",
        "completed_other": "visible sea patch without a drawn wave face, completed (in_S7 = false)"}
    # ---- stretch that depends on the pending left-end reading: x-range inherited from the finger-scale file
    pend_keys = list(fj.get(BB.PENDING_KEY) or [])
    pend = {}
    f_blk = (fj.get(BB.PENDING_STRETCHES_KEY) or {}).get(BB.PENDING_LEFT_END)
    if f_blk and f_blk.get("x_range_px"):
        bk = V["segs"]["back"]
        xr = [float(f_blk["x_range_px"][0]), float(f_blk["x_range_px"][1])]
        m_off = np.asarray(bk["lab"], dtype=object) == BB.OFFSET_FLAG
        if m_off.any():                                      # the 2 px samples of this file are phase-shifted against the finger-scale
            xr[1] = max(xr[1], float(bk["pts"][m_off, 0].max()))    # samples: the last flagged point may lie up to one sample further
        blk = BB.pending_left_end(bk["pts"], bk["lab"], xr, F,
                                  "%s key %s (x-range of the finger-scale flag %s), extended to the last point of THIS file that carries "
                                  "the flag; every large-form point in this x-range is derived from that constructed stretch, whether it "
                                  "kept the flag or became large_form_bridge" % (finger_rel, BB.PENDING_STRETCHES_KEY, BB.OFFSET_FLAG))
        blk["x_range_px_of_finger_scale_file"] = [float(v) for v in f_blk["x_range_px"]]
        pend[BB.PENDING_LEFT_END] = blk
    if comparison_only:
        definition = comparison_only
    else:
        definition = ("LARGE FORM of the great wave: the finger-scale base contour (%s) closed to a region (body inside), morphological %s with a disc of radius r = %g px "
                      "(exact Euclidean distance transforms at full resolution), boundary re-extracted on the sub-pixel level set and smoothed along arclength with sigma = %g %% of "
                      "image height; the ORIGINAL finger-scale line is kept wherever the regularised line is closer than %g %% of image height and the original line itself turns "
                      "no faster than the ball (%.2f deg per %g %% sample); smoothstep cross-fades of %g %% in between. r follows from spec S8: %g deg per %g %% of image height = "
                      "radius of curvature >= %.1f px." % (finger_rel, "OPENING then CLOSING" if order == "open_close" else "CLOSING then OPENING", r, P(cfg, "post_sigma_pct_h"),
                                                         P(cfg, "keep_tol_pct_h"), math.degrees(F.pct_h_to_px(P(cfg, "s8_spacing_pct_h")) / r), P(cfg, "s8_spacing_pct_h"),
                                                         P(cfg, "seam_blend_len_pct_h"), P(cfg, "s8_limit_deg"), P(cfg, "s8_spacing_pct_h"),
                                                         F.pct_h_to_px(P(cfg, "s8_spacing_pct_h")) / math.radians(P(cfg, "s8_limit_deg"))))
    J = {
        "schema": "gw.base_contour.v1",
        "official": bool(official),
        "built_by": "src/contour/build_large_form.py",
        "variant": name,
        "r_px": r,
        "morph_order": order,
        "left_end_variant": left_variant,
        "derived_from": {"path": finger_rel, "sha256": finger_sha},
        "needs_user_confirmation": ["large-form scale r", "left-end reading (%s)" % left_variant],
        BB.PENDING_KEY: pend_keys,
        BB.PENDING_STRETCHES_KEY: pend,
        "image": fj.get("image"),
        "frame": fj.get("frame"),
        "order": "left frame edge -> crest -> head tip -> inner arc -> trough",
        "sample_spacing_px": P(cfg, "sample_spacing_px"),
        "contour_definition": definition,
        "source_flags": {k: flag_text.get(k, "inherited from the finger-scale file (no description)")
                         for k in [f for f in flag_text if f in flags_present] + [f for f in flags_present if f not in flag_text]},
        "segments": [seg_json(nm) for nm in SEG_NAMES],
        "landmarks": {
            "crest": dict(lm_json(V["crest_px"]), definition="argmin(y) of a copy smoothed with sigma = %g %% of image height (same robust rule as the finger-scale file)" % P(cfg, "landmark_sigma_pct_h"),
                          strict_highest_px=V["lm"]["crest_strict_px"], plateau_x_px=V["lm"]["crest_plateau_x_px"]),
            "head_tip": dict(lm_json(V["tip_px"]), definition="right-most point of the large-form head (vertex of a parabola fitted to x(s) within %g %% of image height of the maximum)" % P(cfg, "tip_tol_pct_h"),
                             fit=V["lm"]["tip_fit"]),
            "inner_deepest": dict(lm_json(V["deep_px"]), definition="argmin(x) of the smoothed copy of the visible inner arc (same rule as the finger-scale file)",
                                  strict_leftmost_px=V["lm"]["deep_strict_px"], run_y_px=V["lm"]["deep_run_y_px"]),
            "trough_level": fl.get("trough_level", {"y_px": round(z0, 3), "top_pct": 74.7}),
            "claw_rightmost": fl.get("claw_rightmost"),
            "inner_arc_visible_end": lm_json(V["lm"]["vis_end_px"]),
            "completion_end": lm_json(V["segs"]["inner_arc"]["pts"][-1]),
            "finger_scale_head_tip": fl.get("head_tip", {}).get("px"),
        },
    }
    return J


# ====================================================================== drawing
COL = {"back": "red", "head": "magenta", "inner_arc": "lime", "large_form_bridge": "orange", "claw_root_bridge": "orange",
       "completed_occluded": "cyan", "completed_other": "blue"}
VAR_COL = {100: "red", 120: (0, 170, 0), 135: "purple", 150: "blue"}


def draw_variant(img, tf, V, width=3.0):
    for nm in SEG_NAMES:
        sg = V["segs"][nm]
        pts, lab = sg["pts"], sg["lab"]
        i = 0
        while i < len(pts):
            j = i
            while j + 1 < len(pts) and lab[j + 1] == lab[i]:
                j += 1
            k = min(j + 1, len(pts) - 1)
            l_ = lab[i]
            if l_ in COMPLETED:
                draw.polyline(img, tf(pts[i:k + 1]), COL[l_], width, dash=(10, 6))
            elif l_ == "large_form_bridge":
                draw.polyline(img, tf(pts[i:k + 1]), COL[l_], width)
            elif l_ == BB.OFFSET_FLAG:                               # constructed left end of the back: segment colour, short dashes
                draw.polyline(img, tf(pts[i:k + 1]), COL[nm], width, dash=BB.offset_dash(width))
            else:
                draw.polyline(img, tf(pts[i:k + 1]), COL[nm], width)
            i = j + 1


def draw_marks(img, tf, V, F, Oc, scale=2, labels=True):
    for name, pct in (("S1 spec", (38.2, 8.7)), ("S2 spec", (39.5, 46.3)), ("S6 spec", (59.2, 33.0))):
        p = tf(np.array(F.pct_to_px(*pct), np.float64))
        if labels:
            draw.label_point(img, p, name, "navy", scale=scale, offset=(10, 10), kind="x", size=5 + 2 * scale)
        else:
            draw.marker(img, p, "x", 5 + 2 * scale, "navy", 2, outline="white")
    ft = tf(Oc["pts"][Oc["i_tip"]])
    if labels:
        draw.label_point(img, ft, "finger-scale tip", "darkgray", scale=scale, offset=(10, -14), kind="s", size=3 + scale)
    else:
        draw.marker(img, ft, "s", 3 + scale, "darkgray", 2, outline="white")
    for name, p in (("crest", V["crest_px"]), ("head tip", V["tip_px"]), ("inner deepest", V["deep_px"])):
        q = tf(np.asarray(p, np.float64))
        if labels:
            draw.label_point(img, q, name, "black", scale=scale, offset=(10, -14) if name != "head tip" else (-10, 12), kind="O", size=4 + 2 * scale)
        else:
            draw.marker(img, q, "O", 4 + 2 * scale, "black", 2, outline="white")


def legend_box(img, x, y, items, scale=2):
    w = max(draw.text_size(t, scale)[0] for t, _, _ in items) + 60
    h = 11 * scale * len(items) + 10
    draw.rect(img, x, y, x + w, y + h, "white", fill=True, alpha=0.88)
    for k, (t, c, dash) in enumerate(items):
        yy = y + 6 + k * 11 * scale
        if c is not None:
            draw.line(img, (x + 6, yy + 4 * scale), (x + 40, yy + 4 * scale), c, 3, dash=dash)
        draw.text(img, x + 48, yy, t, "black", scale=scale)
    return (x, y, x + w, y + h)


STD_ITEMS = [("finger-scale contour (thin, visible where the two differ)", "black", None), ("large form: on the finger-scale line, back", "red", None),
             ("same, but that line is CONSTRUCTED (offset_from_visible_edge)", "red", BB.offset_dash(3.0)),
             ("large form: on the finger-scale line, head", "magenta", None), ("large form: on the finger-scale line, inner arc", "lime", None),
             ("large form: moved by the regularisation (large_form_bridge)", "orange", None),
             ("completed, in_S7 = false (dashed)", "cyan", (10, 6))]


def view_official(rgb, box, scale, V, Oc, F, title, labels=True, width=3.0, extra=None, legend_at=None, z0_line=True):
    v = draw.View(rgb, box[0], box[1], box[2], box[3], scale=scale, method="bilinear" if scale > 1 else "auto")
    for pts, colr, wd, dash in (extra or []):
        draw.polyline(v.img, v.to_view(pts), colr, wd, dash=dash)
    draw.polyline(v.img, v.to_view(Oc["pts"]), "black", 1.3)
    draw_variant(v.img, v.to_view, V, width=width)
    draw_marks(v.img, v.to_view, V, F, Oc, scale=2 if labels else 1, labels=labels)
    if z0_line:
        zz = v.to_view(np.array([0.0, float(F.pct_to_px(0, 74.7)[1])]))[1]
        if 0 <= zz < v.img.shape[0]:
            draw.hline(v.img, zz, "orange", 1.5, dash=(10, 6))
            draw.text(v.img, 6, zz + 4, "Z = 0 (74.7 %)", "orange", scale=1, bg="white")
    if legend_at is not None:
        legend_box(v.img, legend_at[0], legend_at[1], STD_ITEMS, scale=legend_at[2] if len(legend_at) > 2 else 2)
    draw.text(v.img, 4, 4, "%s   x %d..%d  y %d..%d  zoom %.2f" % (title, box[0], box[2], box[1], box[3], scale), "black", scale=2, bg="white")
    return v.img


def view_variants(rgb, box, scale, variants, Oc, F, title, radii, width=2.2, extra=None, legend_at=(8, 34), with_tips=True):
    v = draw.View(rgb, box[0], box[1], box[2], box[3], scale=scale, method="bilinear" if scale > 1 else "auto")
    for e in (extra or []):
        draw.polyline(v.img, v.to_view(e[0]), e[1], e[2], dash=e[3])
    items = [("finger-scale contour", "black", None)]
    for r in radii:
        V = variants[r]
        draw.polyline(v.img, v.to_view(V["full"]), VAR_COL.get(r, "orange"), width)
        items.append(("large form r = %d px" % r, VAR_COL.get(r, "orange"), None))
    draw.polyline(v.img, v.to_view(Oc["pts"]), "black", 1.2)
    if with_tips:
        for r in radii:
            draw.marker(v.img, v.to_view(variants[r]["tip_px"]), "O", 7, VAR_COL.get(r, "orange"), 2, outline="white")
        draw.marker(v.img, v.to_view(Oc["pts"][Oc["i_tip"]]), "s", 5, "black", 2, outline="white")
        s6 = np.array(F.pct_to_px(59.2, 33.0), np.float64)
        draw.label_point(v.img, v.to_view(s6), "S6 spec", "navy", scale=2, offset=(-10, 12), kind="x", size=9)
        items += [("ring = head tip of that variant, square = finger-scale tip", None, None)]
    for t, c, dsh in [(e[4], e[1], e[3]) for e in (extra or []) if len(e) > 4]:
        items.append((t, c, dsh))
    if legend_at is not None:
        legend_box(v.img, legend_at[0], legend_at[1], items, scale=2)
    draw.text(v.img, 4, 4, "%s   x %d..%d  y %d..%d  zoom %.2f" % (title, box[0], box[2], box[1], box[3], scale), "black", scale=2, bg="white")
    return v.img


# ====================================================================== main
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(HERE, "large_form_params.json"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--radii", default="", help="trial runs only: comma separated radii instead of radii_px")
    ap.add_argument("--official-order-only", action="store_true", help="trial runs only: skip the other morph order")
    args = bootstrap.parse_args(ap)
    cfg = paths.read_json(args.params)
    if args.tag and args.radii:
        cfg["radii_px"]["value"] = [float(v) for v in args.radii.split(",")]
        cfg["official_candidates_px"]["value"] = [int(float(v)) for v in args.radii.split(",")]
    F = frame.get_frame()
    official_run = not args.tag
    base_out = os.path.join(paths.STEP1_DIR, "contour_large_form")
    out_dir = paths.ensure_dir(base_out if official_run else os.path.join(base_out, "trial_" + args.tag))
    var_dir = paths.ensure_dir(os.path.join(paths.TARGET_DIR, "large_form_variants") if official_run else os.path.join(out_dir, "large_form_variants"))
    json_path = paths.BASE_CONTOUR_JSON if official_run else os.path.join(out_dir, "base_contour.json")
    overlay_path = os.path.join(paths.TARGET_DIR, "base_contour_overlay.png") if official_run else os.path.join(out_dir, "base_contour_overlay.png")
    log("LARGEFORM params =", paths.norm(args.params), "| official run =", official_run)

    finger_path = ensure_finger_scale_file(cfg, official_run)
    finger_rel = os.path.relpath(finger_path, paths.PROJECT_ROOT).replace("\\", "/")
    finger_sha = BB.sha256_of(finger_path)
    Oc = load_contour(finger_path)
    O = Oc["pts"]
    left_variant = (Oc["json"].get("variant") or {}).get("back_left_variant", "unknown")
    log("INPUT finger-scale contour %s sha256 %s... | %d points | left end = %s" % (finger_rel, finger_sha[:16], len(O), left_variant))

    radii = [float(v) for v in P(cfg, "radii_px")]
    order_off = P(cfg, "morph_order")
    order_other = [o for o in cfg["morph_order"]["allowed"] if o != order_off][0]
    h1 = float(F.pct_h_to_px(1.0))
    sig_px = float(F.pct_h_to_px(P(cfg, "post_sigma_pct_h")))
    r_limit = float(F.pct_h_to_px(P(cfg, "s8_spacing_pct_h"))) / math.radians(P(cfg, "s8_limit_deg"))
    log("S8 -> minimum radius of curvature %.1f px (%.2f %% of image height, %.2f %% H); target %.1f deg -> %.1f px" % (
        r_limit, F.px_to_pct_h(r_limit), r_limit / F.px_per_H * 100, P(cfg, "s8_target_deg"), h1 / math.radians(P(cfg, "s8_target_deg"))))

    # ---------------------------------------------------------------- 1. regularisation (all radii, both orders)
    M, origin, reg_info = build_region(O, max(radii), cfg)
    log("REGION canvas %s (%.1f MP), end tangents %.1f / %.1f deg" % (reg_info["canvas_px"], M.size / 1e6, reg_info["start_tangent_deg"], reg_info["end_tangent_deg"]))
    variants, others, metrics, comps = {}, {}, {}, {}
    for r in radii:
        for order in ((order_off,) if (args.tag and args.official_order_only) else (order_off, order_other)):
            with bootstrap.Timer("morphology r = %g %s" % (r, order)):
                mask, D = morph(M, r, order)
                R, ext_info = extract_boundary(mask, D, r, origin, sig_px)
            comp = compose(R, O, F, cfg, r)
            V = finalise(comp, Oc, F, cfg)
            name = "large_form_r%d" % int(round(r)) if order == order_off else "large_form_r%d_%s" % (int(round(r)), order)
            J = contour_json(V, Oc, F, cfg, r, order, name, finger_rel, finger_sha, False, left_variant)
            mm = measure_variant(V, Oc, F, cfg, J)
            mm["own_S8"]["design_turn_of_ball_deg"] = round(math.degrees(h1 / r), 2)
            kept = ~comp["changed"]
            mm["raster_check"] = dict(ext_info, signed_offset_R_minus_O_on_unchanged_stretches_px=BB.q_stats(comp["dsig_R_to_O"][kept]),
                                      abs_offset_p95_px=float(np.percentile(comp["d_R_to_O"][kept], 95)) if kept.any() else None,
                                      share_of_R_changed=float(comp["changed"].mean()), share_far=float(comp["core_far"].mean()),
                                      share_rough_only=float((comp["core_rough"] & ~comp["core_far"]).mean()))
            J["measurements"] = json_measurements(mm)
            V["J"], V["name"], V["comp"] = J, name, comp
            if order == order_off:
                variants[int(round(r))] = V
                metrics[name] = mm
            else:
                others[int(round(r))] = V
                metrics[name] = mm
            s8 = mm["own_S8"]
            log("VARIANT %-28s own S8 max %.2f (back %.2f head %.2f inner %.2f, tip window %.2f; ball %.2f) | tip (%.1f, %.1f) | json-vs-detection max %.3f %%" % (
                name, s8["max_whole_deg"], s8["per_segment"]["back"]["max_deg"], s8["per_segment"]["head"]["max_deg"], s8["per_segment"]["inner_arc"]["max_deg"],
                s8["tip_window_max_deg"], s8["design_turn_of_ball_deg"], V["tip_px"][0], V["tip_px"][1],
                mm["test_library"].get("json_vs_detection_max_dist_pct_h", float("nan"))))
            dd = mm["distance_to_finger_scale_pct_h"]["finger_scale_to_large_form"]
            log("   finger-scale -> large form  " + "  ".join("%s %.2f/%.2f/%.2f" % (nm, dd[nm]["mean"], dd[nm]["p95"], dd[nm]["max"]) for nm in SEG_NAMES)
                + " | raster offset on unchanged stretches median %+.2f px" % mm["raster_check"]["signed_offset_R_minus_O_on_unchanged_stretches_px"].get("median", float("nan")))

    # ---------------------------------------------------------------- 2. official radius
    cand = [int(v) for v in P(cfg, "official_candidates_px")]
    target = P(cfg, "s8_target_deg")
    passing = [r for r in sorted(cand) if metrics["large_form_r%d" % r]["own_S8"]["max_whole_deg"] <= target]
    r_off = passing[0] if passing else max(cand)
    sel = {"rule": "smallest r of official_candidates_px whose own S8 maximum (whole contour, 4 phases, across the tip) is <= s8_target_deg",
           "s8_target_deg": target, "candidates_px": cand,
           "own_S8_max_deg": {str(r): metrics["large_form_r%d" % r]["own_S8"]["max_whole_deg"] for r in sorted(variants)},
           "official_r_px": r_off, "rule_satisfied": bool(passing)}
    log("OFFICIAL r = %d px (%s)" % (r_off, "rule satisfied" if passing else "NO candidate meets the target - largest taken"))

    # ---------------------------------------------------------------- 3. comparison: the judge's Gaussian low-pass
    sg = P(cfg, "lowpass_compare_sigma_pct_h")
    lp = LA.gaussian_smooth(BB.resample_1px(O), float(F.pct_h_to_px(sg)), 1.0)
    comp_lp = {"P": lp}
    V_lp = finalise(comp_lp, Oc, F, cfg)
    J_lp = contour_json(V_lp, Oc, F, cfg, None, "gaussian_lowpass", "compare_lowpass_sigma%gpct" % sg, finger_rel, finger_sha, False, left_variant,
                        comparison_only="COMPARISON ONLY: finger-scale contour low-passed along arclength with a Gaussian of sigma = %g %% of image height (the judge's diagnostic)" % sg)
    metrics["compare_lowpass_sigma%gpct" % sg] = measure_variant(V_lp, Oc, F, cfg, J_lp)
    V_lp["J"] = J_lp

    # ---------------------------------------------------------------- 4. the other left-end reading (official r only)
    alt_V, alt_Oc = None, None
    alt_path = os.path.join(paths.PROJECT_ROOT, P(cfg, "alt_left_end_file"))
    if os.path.isfile(alt_path):
        alt_Oc = load_contour(alt_path)
        alt_variant = (alt_Oc["json"].get("variant") or {}).get("back_left_variant", "other")
        Ma, origin_a, _ = build_region(alt_Oc["pts"], r_off, cfg)
        with bootstrap.Timer("morphology other left-end reading r = %d" % r_off):
            mask, D = morph(Ma, float(r_off), order_off)
            Ra, _ = extract_boundary(mask, D, float(r_off), origin_a, sig_px)
        alt_V = finalise(compose(Ra, alt_Oc["pts"], F, cfg, float(r_off)), alt_Oc, F, cfg)
        alt_rel = os.path.relpath(alt_path, paths.PROJECT_ROOT).replace("\\", "/")
        alt_name = "large_form_r%d_alt_%s" % (r_off, alt_variant)
        alt_V["J"] = contour_json(alt_V, alt_Oc, F, cfg, float(r_off), order_off, alt_name, alt_rel, BB.sha256_of(alt_path), False, alt_variant)
        alt_V["name"] = alt_name
        metrics[alt_name] = measure_variant(alt_V, alt_Oc, F, cfg, alt_V["J"])
        metrics[alt_name]["own_S8"]["design_turn_of_ball_deg"] = round(math.degrees(h1 / r_off), 2)
        alt_V["J"]["measurements"] = json_measurements(metrics[alt_name])
        s8 = metrics[alt_name]["own_S8"]
        log("VARIANT %-28s own S8 max %.2f (back %.2f) at %s" % (alt_name, s8["max_whole_deg"], s8["per_segment"]["back"]["max_deg"], s8["max_whole_at_px"]))
    else:
        log("WARNING other left-end reading not found:", paths.norm(alt_path))

    # ---------------------------------------------------------------- 5. json files
    written = {}
    for r, V in sorted(variants.items()):
        V["J"]["official"] = bool(r == r_off)
        pth = os.path.join(var_dir, V["name"] + ".json")
        paths.write_json(pth, V["J"])
        written[V["name"]] = BB.sha256_of(pth)
    paths.write_json(json_path, variants[r_off]["J"])
    written["base_contour.json"] = BB.sha256_of(json_path)
    if r_off in others:
        Vo = others[r_off]
        paths.write_json(os.path.join(var_dir, Vo["name"] + ".json"), Vo["J"])
    if alt_V is not None:
        paths.write_json(os.path.join(var_dir, alt_V["name"] + ".json"), alt_V["J"])
    paths.write_json(os.path.join(out_dir, "compare_lowpass_sigma%gpct.json" % sg), J_lp)
    log("WROTE", paths.norm(json_path), "sha256", written["base_contour.json"][:16], "| variants in", paths.norm(var_dir))

    # finger-scale own numbers with the same code, for the tables
    Vf = {"full": O, "lab": Oc["lab"], "seg": Oc["seg"], "i_c": Oc["i_crest"], "i_t": Oc["i_tip"], "tip_px": O[Oc["i_tip"]],
          "dev_px": np.zeros(len(O)), "dev_signed_px": np.zeros(len(O)), "lm": {"tip_fit": None}}
    metrics["finger_scale"] = measure_variant(Vf, Oc, F, cfg, Oc["json"])

    # ---------------------------------------------------------------- 6. metrics.json
    curves = {k: m.pop("_s8_curve") for k, m in metrics.items()}
    summary = {
        "params_file": paths.norm(args.params), "finger_scale_file": finger_rel, "finger_scale_sha256": finger_sha, "left_end_variant": left_variant,
        "S8_derivation": {"limit_deg": P(cfg, "s8_limit_deg"), "spacing_pct_h": P(cfg, "s8_spacing_pct_h"), "spacing_px": h1,
                          "min_radius_of_curvature_px": r_limit, "min_radius_pct_of_image_height": float(F.px_to_pct_h(r_limit)), "min_radius_pct_H": r_limit / F.px_per_H * 100,
                          "radius_for_target_px": h1 / math.radians(target)},
        "region": reg_info, "morph_order_official": order_off, "official_selection": sel,
        "variants": strip(metrics), "output_sha256": written,
    }
    paths.write_json(os.path.join(out_dir, "metrics.json"), summary)

    # ---------------------------------------------------------------- 7. pictures
    if not args.no_images:
        from gw import imgio
        rgb = imgio.load_painting_rgb()
        make_pictures(rgb, F, cfg, Oc, variants, others, V_lp, alt_V, alt_Oc, metrics, curves, r_off, order_off, order_other, out_dir, overlay_path, sel, left_variant)

    # ---------------------------------------------------------------- console table
    for name in sorted(metrics):
        m = metrics[name]
        s8, jd, lib = m["own_S8"], m["judge_definitions"], m["test_library"]
        th = jd["head_thickness"]
        log("TABLE %-30s S8 b/h/i %.1f/%.1f/%.1f tip+-2%% %.1f | thick 5/10/20 %%H pair %.1f/%.1f/%.1f short %.1f/%.1f/%.1f inscribed %.1f %%H | tip %.2f/%.2f" % (
            name, s8["per_segment"]["back"]["max_deg"], s8["per_segment"]["head"]["max_deg"], s8["per_segment"]["inner_arc"]["max_deg"], s8["tip_window_max_deg"],
            th["5_pct_H"]["pair_distance_pct_H"], th["10_pct_H"]["pair_distance_pct_H"], th["20_pct_H"]["pair_distance_pct_H"],
            th["5_pct_H"]["shortest_top_to_underside_pct_H"], th["10_pct_H"]["shortest_top_to_underside_pct_H"], th["20_pct_H"]["shortest_top_to_underside_pct_H"],
            m["rim_like_thickness_at_tip"]["pct_H"], m["tip"]["pct"][0], m["tip"]["pct"][1]))
        if lib.get("ok"):
            s4 = lib["json_joints"]["S4"]
            log("      lib S4 left %.1f mid %.1f before-crest %.1f flattens %s round-top %s (crest zone turn %.1f) | phi %s | o %.4f cavity %.4f dir %.1f | json-vs-detection %.3f %%" % (
                s4["left_end_deg"], s4["mid_max_deg"], s4["before_crest_deg"], s4["flattens_towards_crest"], s4["top_is_round_no_corner"], s4["crest_max_turn_deg"],
                {k: (None if v["json_joints_deg"] is None else round(v["json_joints_deg"], 1)) for k, v in lib["phi_windows"].items()},
                lib["json_joints"]["o_H"], lib["json_joints"]["cavity_depth_H"], lib.get("crest_to_tip_direction_deg", float("nan")), lib["json_vs_detection_max_dist_pct_h"]))
        else:
            log("      lib FAILED:", lib.get("error"))
    ok = bool(sel["rule_satisfied"])
    bootstrap.finish(ok, "large-form base contour written (official r = %d px)" % r_off if ok else "no candidate radius meets the S8 target")


# ====================================================================== pictures
def make_pictures(rgb, F, cfg, Oc, variants, others, V_lp, alt_V, alt_Oc, metrics, curves, r_off, order_off, order_other, out_dir, overlay_path, sel, left_variant):
    from gw import imgio
    V = variants[r_off]
    O = Oc["pts"]
    shown = [r for r in (100, 120, 150) if r in variants] or sorted(variants)
    tt = "large form r = %d px (%s), left end = %s" % (r_off, order_off, left_variant)
    alt_back = None
    if alt_Oc is not None:
        ab = alt_Oc["pts"][:alt_Oc["i_crest"] + 1]
        alt_back = ab[ab[:, 0] < 420]
    alt_lf = None
    if alt_V is not None:
        ab = alt_V["segs"]["back"]["pts"]
        alt_lf = ab[ab[:, 0] < 420]

    # (a) full-wave overlays
    sc = 1600.0 / F.width_px
    img = view_official(rgb, (0, 0, F.width_px, F.height_px), sc, V, Oc, F, "OFFICIAL base contour = " + tt, labels=False, width=2.6, legend_at=(1010, 30, 1))
    imgio.save_png(overlay_path, img)
    img_a = view_official(rgb, (0, 0, 2700, 2100), 1600.0 / 2700.0, V, Oc, F, "OFFICIAL base contour = " + tt, labels=True, width=3.0, legend_at=(8, 34))
    imgio.save_png(os.path.join(out_dir, "a_overlay_wave_1600.png"), img_a)
    full = rgb.copy()
    draw.polyline(full, O, "black", 2.0)
    draw_variant(full, lambda q: q, V, width=5.0)
    draw_marks(full, lambda q: q, V, F, Oc, scale=3)
    imgio.save_png(os.path.join(out_dir, "a_overlay_full_res.png"), full)
    # (b) head close-up, three radii
    extra_lp = [(V_lp["full"], "orange", 1.6, (8, 5), "comparison only: Gaussian low-pass sigma %g %%" % P(cfg, "lowpass_compare_sigma_pct_h"))]
    img_b = view_variants(rgb, (1450, 150, 2350, 1150), 1.6, variants, Oc, F, "head: large form for r = %s px (%s) over the finger-scale line" % ("/".join(str(r) for r in shown), order_off), shown, extra=extra_lp)
    imgio.save_png(os.path.join(out_dir, "b_head_radii.png"), img_b)
    img_b2 = view_variants(rgb, (2000, 650, 2330, 1130), 4.5, variants, Oc, F, "head tip and right flank", shown, width=2.0)
    imgio.save_png(os.path.join(out_dir, "b_head_tip_zoom.png"), img_b2)
    # both orders for the official r
    v = draw.View(rgb, 1450, 150, 2350, 1150, scale=1.6, method="bilinear")
    if r_off in others:
        draw.polyline(v.img, v.to_view(others[r_off]["full"]), "cyan", 2.4)
    draw.polyline(v.img, v.to_view(V["full"]), "blue", 2.4)
    draw.polyline(v.img, v.to_view(O), "black", 1.2)
    legend_box(v.img, 8, 34, [("finger-scale contour", "black", None), ("r = %d px, %s (official order)" % (r_off, order_off), "blue", None),
                              ("r = %d px, %s (other order)" % (r_off, order_other), "cyan", None)])
    draw.text(v.img, 4, 4, "order of opening / closing, r = %d px" % r_off, "black", scale=2, bg="white")
    imgio.save_png(os.path.join(out_dir, "b_head_orders.png"), v.img)
    # official with flags, head
    imgio.save_png(os.path.join(out_dir, "b_head_official_flags.png"),
                   view_official(rgb, (1450, 150, 2350, 1150), 1.6, V, Oc, F, "head, official " + tt, legend_at=(8, 34)))
    # (c) crest / step
    imgio.save_png(os.path.join(out_dir, "c_crest_step_radii.png"),
                   view_variants(rgb, (1250, 140, 1950, 520), 2.2, variants, Oc, F, "crest and the step right of the crest", shown, with_tips=False))
    imgio.save_png(os.path.join(out_dir, "c_crest_step_official.png"),
                   view_official(rgb, (1250, 140, 1950, 520), 2.2, V, Oc, F, "crest / step, official", legend_at=None))
    imgio.save_png(os.path.join(out_dir, "c_vertical_face_radii.png"),
                   view_variants(rgb, (1760, 340, 2140, 720), 4.0, variants, Oc, F, "vertical face of the head and the corner under it", shown, with_tips=False))
    # (d) armpit
    imgio.save_png(os.path.join(out_dir, "d_armpit_radii.png"),
                   view_variants(rgb, (1480, 780, 1980, 1180), 3.2, variants, Oc, F, "armpit between the underside of the head and the inner arc", shown, with_tips=False))
    imgio.save_png(os.path.join(out_dir, "d_underside_radii.png"),
                   view_variants(rgb, (1640, 820, 2260, 1160), 2.5, variants, Oc, F, "underside of the head", shown, with_tips=False))
    # (e) left end, both readings
    ex = []
    if alt_back is not None:
        ex.append((alt_back, "purple", 1.5, None, "finger-scale, OTHER reading (sky silhouette), thin"))
    if alt_lf is not None:
        ex.append((alt_lf, "purple", 3.0, (12, 6), "large form of the other reading r = %d px (dashed)" % r_off))
    v = draw.View(rgb, 0, 780, 520, 1120, scale=3.0, method="bilinear")
    for pts, colr, wd, dash, _t in ex:
        draw.polyline(v.img, v.to_view(pts), colr, wd, dash=dash)
    draw.polyline(v.img, v.to_view(O), "black", 1.3)
    draw_variant(v.img, v.to_view, V, width=3.0)
    legend_box(v.img, 560, 34, [("finger-scale, white_body_outline (thin black)", "black", None), ("large form, official (on the finger-scale line)", "red", None),
                                ("same, short dashes: that line is CONSTRUCTED (white edge + ink width)", "red", BB.offset_dash(3.0)),
                                ("large form, moved by the regularisation", "orange", None)] + [(t, c, d_) for _p, c, _w, d_, t in ex])
    draw.text(v.img, 4, 4, "left end of the back: both readings   x 0..520  y 780..1120  zoom 3", "black", scale=2, bg="white")
    img_e = v.img
    imgio.save_png(os.path.join(out_dir, "e_left_end_readings.png"), img_e)
    # inner arc lower end / completion
    imgio.save_png(os.path.join(out_dir, "x_inner_arc_lower_end.png"),
                   view_official(rgb, (1700, 1600, 2300, 2000), 2.6, V, Oc, F, "inner arc lower end and completion, official", legend_at=None))
    imgio.save_png(os.path.join(out_dir, "x_back_mid_official.png"),
                   view_official(rgb, (250, 330, 1350, 960), 1.45, V, Oc, F, "back, official", legend_at=None, z0_line=False))

    # (g) S8 plots
    Hp = float(F.height_px)
    plots = []
    for name in ["finger_scale"] + [variants[r]["name"] for r in sorted(variants)] + ["compare_lowpass_sigma%gpct" % P(cfg, "lowpass_compare_sigma_pct_h")]:
        js, jt, jp, seg_of = curves[name]
        ser = []
        for nm, colr in (("back", "red"), ("head", "magenta"), ("inner_arc", "green"), ("completed", "cyan")):
            m = seg_of == nm
            if m.any():
                ser.append({"label": nm, "x": js[m] / Hp * 100, "y": np.abs(jt[m]), "color": colr, "marker": "o", "marker_size": 2, "width": 1})
        hl = [{"y": 15, "label": "S8 limit 15", "color": "black"}, {"y": P(cfg, "s8_target_deg"), "label": "target %g" % P(cfg, "s8_target_deg"), "color": "darkgray"}]
        rr = metrics[name]["own_S8"].get("design_turn_of_ball_deg")
        if rr:
            hl.append({"y": rr, "label": "ball %.1f" % rr, "color": "blue"})
        ymax = 30 if name != "finger_scale" else 90
        pl = plot.line_plot(ser, title="own S8 of %s: |tangent change| between neighbouring 1 %% samples, 4 phases, across the head tip (max %.1f deg)" % (name, metrics[name]["own_S8"]["max_whole_deg"]),
                            xlabel="arclength from the left frame edge [% of image height]", ylabel="deg", size=(1600, 420), ylim=(0, ymax), hlines=hl)
        imgio.save_png(os.path.join(out_dir, "g_S8_%s.png" % name), pl)
        plots.append(pl)
    imgio.save_png(os.path.join(out_dir, "g_S8_all_variants.png"), draw.fit_width(draw.vstack(plots), 1600))
    # signed curvature of the official variant (sliding turn) + deviation from the finger scale
    st, ss = sliding_turn(V["full"], float(F.pct_h_to_px(1.0)))
    stf, ssf = sliding_turn(O, float(F.pct_h_to_px(1.0)))
    pl1 = plot.line_plot([{"label": "finger scale", "x": ssf / Hp * 100, "y": stf, "color": "lightgray", "width": 1},
                          {"label": "large form r = %d" % r_off, "x": ss / Hp * 100, "y": st, "color": "blue", "width": 2}],
                         title="signed turn per 1 % of arclength (sliding): + = counter-clockwise, - = clockwise (convex body)",
                         xlabel="arclength [% of image height]", ylabel="deg", size=(1600, 420), ylim=(-25, 25),
                         hlines=[{"y": 15, "label": "+15"}, {"y": -15, "label": "-15"}],
                         vlines=[{"x": LA.arclength(V["full"])[V["i_c"]] / Hp * 100, "label": "crest"}, {"x": LA.arclength(V["full"])[V["i_t"]] / Hp * 100, "label": "head tip"}])
    pl2 = plot.line_plot([{"label": "r = %d" % r, "x": LA.arclength(variants[r]["full"]) / Hp * 100, "y": F.px_to_pct_h(variants[r]["dev_signed_px"]), "color": VAR_COL.get(r, "orange"), "width": 2}
                          for r in sorted(variants)],
                         title="signed distance large form - finger-scale line (+ = sky side: body grown, - = body cut)", xlabel="arclength of the large form [% of image height]",
                         ylabel="% of image height", size=(1600, 420), hlines=[{"y": 0.15, "label": "+0.15 keep tol"}, {"y": -0.15, "label": "-0.15"}])
    imgio.save_png(os.path.join(out_dir, "g_turn_signed_and_deviation.png"), draw.vstack([pl1, pl2]))

    # where was the original line kept?  (official variant)
    cp = V["comp"]
    sR = LA.arclength(cp["R"]) / Hp * 100
    lim = cp["turn_limit_deg"]
    tO = np.interp(cp["sO"], cp["s_O"], np.abs(cp["turn_O"]))
    pd1 = plot.line_plot([{"label": "signed distance R - O [px]", "x": sR, "y": np.clip(cp["dsig_R_to_O"], -12, 12), "color": "blue", "width": 1},
                          {"label": "weight of the original line x 10", "x": sR, "y": 10.0 * cp["w"], "color": "red", "width": 2}],
                         title="official variant: regularised line R vs original line O along R (clipped at +-12 px); weight 1 = original line kept",
                         xlabel="arclength [% of image height]", ylabel="px", size=(1600, 420), ylim=(-12.5, 12.5),
                         hlines=[{"y": float(F.pct_h_to_px(P(cfg, "keep_tol_pct_h"))), "label": "keep tol"}, {"y": -float(F.pct_h_to_px(P(cfg, "keep_tol_pct_h")))}])
    pd2 = plot.line_plot([{"label": "own turn of O per 1 % (sliding)", "x": sR, "y": np.clip(tO, 0, 40), "color": "darkgray", "width": 1},
                          {"label": "changed (far) x 30", "x": sR, "y": 30.0 * cp["core_far"], "color": "orange", "width": 1},
                          {"label": "changed (turn rule) x 25", "x": sR, "y": 25.0 * cp["core_rough"], "color": "magenta", "width": 1},
                          {"label": "changed incl. hysteresis x 20", "x": sR, "y": 20.0 * cp["changed"], "color": "blue", "width": 1}],
                         title="why: own turn of the original line vs the turn of the ball (%.1f deg), changed stretches" % lim,
                         xlabel="arclength [% of image height]", ylabel="deg", size=(1600, 420), ylim=(0, 41), hlines=[{"y": lim, "label": "ball %.1f" % lim, "color": "blue"}])
    imgio.save_png(os.path.join(out_dir, "g_where_original_kept.png"), draw.vstack([pd1, pd2]))

    # (f) decision sheet (<= 2400 px wide): A overview, B head with the radii, C left end, short ASCII legend
    a_img = view_official(rgb, (0, 0, 2700, 2100), 1480.0 / 2700.0, V, Oc, F, "A  official large form r = %d px (thick) over the finger-scale contour (thin black)" % r_off,
                          labels=True, width=3.0, legend_at=None)
    b_img = view_variants(rgb, (1450, 150, 2350, 1150), 1.0, variants, Oc, F, "B  head: r = %s px" % " / ".join(str(r) for r in shown), shown, width=2.0, legend_at=(8, 30))
    vc = draw.View(rgb, 0, 780, 520, 1120, scale=900.0 / 520.0, method="bilinear")
    for pts, colr, wd, dash, _t in ex:
        draw.polyline(vc.img, vc.to_view(pts), colr, max(1.2, wd * 0.7), dash=dash)
    draw.polyline(vc.img, vc.to_view(O), "black", 1.2)
    draw_variant(vc.img, vc.to_view, V, width=2.4)
    legend_box(vc.img, 296, 30, [("official reading: white_body_outline", "red", None),
                                 ("short dashes: constructed, no ink line", "red", BB.offset_dash(2.4)),
                                 ("other reading: sky_silhouette (finger scale)", "purple", None),
                                 ("large form of the other reading (dashed)", "purple", (12, 6))], scale=2)
    draw.text(vc.img, 4, 4, "C  left end of the back   x 0..520  y 780..1120", "black", scale=2, bg="white")
    fs = metrics["finger_scale"]
    mo = metrics[V["name"]]
    dh = mo["distance_to_finger_scale_pct_h"]["finger_scale_to_large_form"]
    col_names = {100: "red", 120: "green", 135: "purple", 150: "blue"}
    pblk = (V["J"].get(BB.PENDING_STRETCHES_KEY) or {}).get(BB.PENDING_LEFT_END) or {}
    constructed = bool(pblk.get("flag_counts", {}).get(BB.OFFSET_FLAG))
    c_lines = (["   Red SHORT DASHES (and the orange stretch left of them) = CONSTRUCTED: no ink line is drawn there, the line is the",
                "   visible white-body edge moved outwards by the measured ink-line width (back, x <= %.0f px; still counted in S7)." % pblk["x_range_px"][1]]
               if constructed else [])
    lines = ["GREAT WAVE - LARGE-FORM BASE CONTOUR - decision sheet (step 1; to be confirmed by the user)", "",
             "A  thick = OFFICIAL large form: red / magenta / lime = still ON the finger-scale line, orange = moved by the",
             "   regularisation, cyan dashed = completed (not counted in S7). Thin black = finger-scale contour (foam lobes kept).",
             "B  head for r = %s px; rings = head tips; black square = finger-scale tip;" % " / ".join("%d (%s)" % (r, col_names.get(r, "?")) for r in shown),
             "   navy x = spec S6 point (right-most point INCLUDING claws).",
             "C  left end of the back: red = white_body_outline reading (official), purple = sky_silhouette reading."] + c_lines + ["",
             "WHY  spec S8 (< 15 deg per 1 %% sample) = radius of curvature >= %.0f px. The finger-scale contour has own S8 = %.0f deg," % (
                 float(F.pct_h_to_px(1.0)) / math.radians(15.0), fs["own_S8"]["max_whole_deg"]),
             "      so S7 (follow it within 1 % / 2 %) and S8 cannot both be met against it.",
             "HOW   %s with a ball of radius r; the original line is kept wherever it is not changed." % ("closing then opening" if order_off == "close_open" else "opening then closing"),
             "NOTE  every lobe narrower than 2 r disappears for ANY r that satisfies S8: the lowest lobe of the head (its bottom is",
             "      at (%.0f, %.0f)) is cut by up to %.1f %% of image height (r = %d)." % (dh["inner_arc"]["max_at_px"][0], dh["inner_arc"]["max_at_px"][1], dh["inner_arc"]["max"], r_off), "",
             "Distances finger scale -> large form in % of image height (S7 limits for a mesh: mean 1, p95 2):",
             "    r px | own S8 max (ball) deg | head mean / p95 / max | underside + inner arc mean / p95 / max | tip left / top % | circle at tip % H"]
    for r in sorted(variants):
        m = metrics[variants[r]["name"]]
        dd = m["distance_to_finger_scale_pct_h"]["finger_scale_to_large_form"]
        lines.append(" %s %4d |   %5.1f (%4.1f)        | %5.2f / %4.2f / %4.2f   | %5.2f / %4.2f / %4.2f                    | %5.2f / %5.2f    | %5.1f" % (
            "->" if r == r_off else "  ", r, m["own_S8"]["max_whole_deg"], m["own_S8"]["design_turn_of_ball_deg"], dd["head"]["mean"], dd["head"]["p95"], dd["head"]["max"],
            dd["inner_arc"]["mean"], dd["inner_arc"]["p95"], dd["inner_arc"]["max"], m["tip"]["pct"][0], m["tip"]["pct"][1], m["rim_like_thickness_at_tip"]["pct_H"]))
    lines += [" finger  |   %5.1f               |                       |                                        | %5.2f / %5.2f    | %5.1f" % (
        fs["own_S8"]["max_whole_deg"], fs["tip"]["pct"][0], fs["tip"]["pct"][1], fs["rim_like_thickness_at_tip"]["pct_H"]), "",
              "PLEASE CONFIRM  (1) the large-form scale r (official now: %d px = smallest candidate with own S8 <= %g deg);" % (r_off, P(cfg, "s8_target_deg")),
              "                (2) the reading of the back's left end (picture C);",
              "                (3) spec G3 'rim <= 3 % H': a section that follows the painted head cannot have it (last column =",
              "                    largest circle touching the contour at the tip from inside = the G3 definition of the tests)."]
    tw = max(draw.text_size(l_, 2)[0] for l_ in lines) + 24
    tb = draw.canvas(22 * len(lines) + 20, tw, "white")
    for k, l_ in enumerate(lines):
        draw.text(tb, 12, 10 + 22 * k, l_, "black", scale=2)
    left = draw.vstack([a_img, tb], gap=8)
    right = draw.vstack([b_img, vc.img], gap=8)
    sheet = draw.hstack([left, right], gap=8)
    if sheet.shape[1] > 2400:
        sheet = draw.fit_width(sheet, 2400)
    imgio.save_png(os.path.join(out_dir, "f_decision_sheet.png"), sheet)
    log("PICTURES written to", paths.norm(out_dir))


if __name__ == "__main__":
    main()
