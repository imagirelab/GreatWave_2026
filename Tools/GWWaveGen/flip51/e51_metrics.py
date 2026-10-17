# -*- coding: utf-8 -*-
"""FLIP51 target: 'convergence' (収束) metrics of one big wave, read from FLIP49 / FLIP50 records (numpy only; py -3.10 -B).
2026-10-17 written new (Claude). Read only on every run folder; writes only under Unity/Build/FLIP51/target.

Why: the user (2026-10-17 ~17:10) judged the big wave 'not converged enough' and showed a target picture
(Unity/Build/FLIP50/_scratch/target/user_target_20261017.jpg, git-ignored, never copied or committed): one tall wave whose crest
narrows upward into a short summit with the curl and a spray plume at the very top, a steep concave face whose streaks converge
toward the top, the surrounding sea much lower.

Records (writer: flip49/g49_run.py, same for FLIP50):
  hf_c*_b*.npz  eta[t, y, x]: top-most water height of any water voxel (an overturning lip counts), half tank y >= 0 (mirrored at
                y = 0 here), absolute height; the still level eta0 = <run>/pana/events.json still_offset_m. Grid 1 m.
  r2_c*_b*.npz  sdf[t, z, x] on the centre section y = 0.5 m (float16, clipped +-8 m), grid 1 m.
  Overlapping blocks of a restarted chain: the later launch wins (same rule as g50_ana.load_sec).
Coordinates here: x along the tank (waves travel +x), y lateral (Houdini z), z up (Houdini y). t = (frame - 1) / 24 s.

The six metrics (frozen in FROZEN / TARGET below before this code measured any run):
  M1 dominance            S1 = c(y_pk +- 1 Hc) / Hc and S2 = c(y_pk +- 2 Hc) / Hc (crest-line height one and two crest heights to
                          the side of the summit, mean of both sides); ring = (eta - eta0) / Hc over the plan ring 2-5 Hc around the
                          summit, seaward of x_pk + 10 m (max = the highest neighbour, p90, mean).
  M2 lateral width        W50 / Hc, W80 / Hc: full width of the contiguous run of the crest line c(y) around the summit with
                          c >= f Hc above the still level (censored at the tank side -> flagged '>=').
  M3 summit sharpness     W95 / Hc (width of the top 5 %: a plateau is wide, a peak is narrow) and taper = W80 / W50
                          (flat top -> 1, Gaussian 0.57, triangle 0.40, cusp < 0.4).
  M4 upward convergence   K = W20 / W80 and the whole curve W(f) / Hc for f = 0.2 ... 0.95 (does the crest narrow with height).
  M5 longitudinal         Lx50 / Hc and Lx70 / Hc: along-x run through the summit on the summit row of eta >= f Hc;
     compactness          plan aspect A50 = W50 / Lx50 (a ridge wall >> 1, a mountain ~ 1-2).
  M6 face (centre r2)     face chord angle from the body toe at 0.1 Hs to the front-most water at 0.8 Hs (deg; > 90 = the upper
                          face overhangs the toe); concavity = max distance of the face behind that chord / Hs (> 0 = concave);
                          overhang = (front-most water above 0.5 Hs) - (body toe at 0.1 Hs), / Hs; back angle 0.7 -> 0.9 Hs
                          (same levels as the D ruler back_best).  Hs = crest height of the section above still.
  c(y) = max over x in [x_pk - 30 m, x_pk + 10 m] of the 3x3-median height field (the crest at the sides lags behind the summit;
  ahead of the summit there is only the lip, the front trough and the swash).

Instants per judged breaker (pana/events.json, judged = True):
  onset   the event onset frame on_f;
  max     the frame of the largest Hc in [on_f - 3 s, on_f + 1.5 s], summit searched in x [on_x - 60 m, on_x + 35 m];
  best    the D/A 'most print-like' frame of pana/best_frames.json (score3 on the centre section, the old 2D print ruler);
  tbest   the frame of the smallest target miss (score_vs_target) in [on_f - 3 s, end of the best_frames window]
          (the best this breaker ever gets under the new target).

usage:
  py -3.10 -B e51_metrics.py freeze                 writes Unity/Build/FLIP51/target/target_frozen.json (definitions + target)
  py -3.10 -B e51_metrics.py baseline               DA3, DM1A, DF1A, DG1 -> Unity/Build/FLIP51/target/baseline.json (+ gap)
  py -3.10 -B e51_metrics.py gap                    (re)writes the 'gap' section of baseline.json (value / target read value)
  py -3.10 -B e51_metrics.py frame <run_dir> <frame> [x_lo x_hi]   metrics of one frame (json to stdout)
  library: frame_metrics(rd, frame, xwin=None), breaker_instants(rd, ev, best), score_vs_target(m), run_metrics(rd)
"""
import os, sys, json, glob, math, time, hashlib, warnings

sys.dont_write_bytecode = True
import numpy as np  # noqa: E402

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
OUT_DIR = os.path.join(ROOT, "Unity/Build/FLIP51/target")
FPS = 24.0
FRACS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)

FROZEN = dict(
    frozen_at="2026-10-17 (before any run was measured with this code; two c(y) rows, DM1A f1211 and DA3 f1517, were printed while "
              "reading the record format, after the target ranges had been read from the picture)",
    median_filter="3x3 nan-median of hf before every height-field metric (removes single-voxel droplets; a lip >= 2 cells wide stays)",
    crest_window_m=dict(back=30.0, front=10.0),
    peak_xwin_rel_onset_m=[-60.0, 35.0],
    ring_Hc=[2.0, 5.0],
    ring_front_m=10.0,
    base="still level eta0 = pana/events.json still_offset_m (primary). Auxiliary: W50_tr = width at 50 % between the front trough "
         "(min of the summit row in [x_pk, x_pk + 30 m]) and the summit, because the picture's foot may be the front trough",
    instants=dict(onset="on_f", max="argmax Hc in [on_f - 3 s, on_f + 1.5 s]", best="pana/best_frames.json per_breaker frame",
                  tbest="argmin target miss in [on_f - 3 s, best window end]"),
    section=dict(record="r2 (y = 0.5 m)", window_back_m=40.0, window_front_m=15.0, toe=0.1, top=0.8, back_levels=[0.7, 0.9]),
    score="target miss = sum over the core metrics of |ln(m / hi)| above the range or |ln(lo / m)| below it (0 inside); "
          "censored widths enter with their lower bound (the miss is then a lower bound too)",
    core=["W50", "W80", "W95", "K", "S2"],
    tbest_min_Hc_over_on_eta=0.6,
    amendment_1=("2026-10-17, after the first baseline call crashed (no run number had been produced): W50_tr only when the front "
                 "trough is > 0.5 m below the summit (division by zero), and tbest candidates need Hc >= 0.6 x the event onset height "
                 "(a frame with a collapsed crest has zero widths and would score as 'converged')"),
    amendment_2=("2026-10-17, code fixed to the frozen definition: face_deg was computed as 180 deg minus the defined angle (sign of the "
                 "horizontal run); the definition (> 90 = the upper face overhangs the toe) is unchanged; the first baseline was rerun"),
)

# Target ranges read from the picture (【推測】). How they were read (all in image pixels of the 1652 x 814 picture):
#  - near-frontal view, camera eye about at the summit (horizon y ~ 148 px, the summit's solid-water top y ~ 155 px);
#  - summit solid-water top y_c = 155 px (145-165; the lip top at x ~ 940 px, the left lobe hidden by spray, its face streaks meet
#    at y ~ 150-160 px); foot of the face y_f = 520 px (480-570; where the streaked face meets foam / the front trough);
#    H = y_f - y_c = 365 px (315-425);
#  - widths read where the streaked face (smooth sheet) ends against the choppy sea or the dark far sea, at the levels
#    y_f - f H: f 0.95 -> x 720-945 px (225 px), f 0.8 -> x 605(535 with the left shoulder hill)-945 (340-410 px),
#    f 0.5 -> x 330-1050 (720 px; 550-850), f 0.2 -> about 1100 px (900-1200);
#  - aspect ratios in the picture are treated as true ratios (object ~ fronto-parallel at one depth); depth spread of the face, an
#    oblique view (the lip curls to the right, so the view may be 20-40 deg off the travel direction) and the unknown foot level
#    widen every range by about +-25 %;
#  - S1 / S2 at +-1 H / +-2 H from the summit centre x ~ 830 px: left shoulder top y ~ 265 px (0.70 if at the wave's depth, less if
#    farther), right shoulder ~ 0.3; at +-2 H the sea / small far hills: 0.05-0.35;
#  - not readable (frontal view): the along-x size, the back, the face slope (seen head-on). Weak ranges are given only so the code
#    can print a direction; they are flagged 'weak' and are never in the core score.
TARGET = {
    "S1": dict(lo=0.30, hi=0.75, read=0.50, tag="【推測】", weak=False, note="crest height at +-1 Hc / Hc"),
    "S2": dict(lo=0.05, hi=0.35, read=0.20, tag="【推測】", weak=False, note="crest height at +-2 Hc / Hc"),
    "ring_max": dict(lo=0.15, hi=0.45, read=0.25, tag="【推測】", weak=False, note="highest neighbour 2-5 Hc / Hc"),
    "W20": dict(lo=2.3, hi=3.6, read=3.0, tag="【推測】", weak=False, note="full width at 20 % / Hc"),
    "W50": dict(lo=1.5, hi=2.6, read=2.0, tag="【推測】", weak=False, note="full width at 50 % / Hc"),
    "W80": dict(lo=0.8, hi=1.25, read=1.0, tag="【推測】", weak=False, note="full width at 80 % / Hc"),
    "W95": dict(lo=0.4, hi=0.85, read=0.6, tag="【推測】", weak=False, note="full width at 95 % / Hc (summit plateau)"),
    "taper": dict(lo=0.35, hi=0.70, read=0.50, tag="【推測】", weak=False, note="W80 / W50"),
    "K": dict(lo=2.0, hi=4.5, read=3.0, tag="【推測】", weak=False, note="W20 / W80 (upward convergence)"),
    "Lx50": dict(lo=0.8, hi=2.0, read=None, tag="【推測】", weak=True,
                 note="along-x width at 50 % / Hc; not visible in the frontal view; 'mountain' footprint assumed (A50 ~ 1-2.5)"),
    "A50": dict(lo=0.8, hi=2.5, read=None, tag="【推測】", weak=True, note="W50 / Lx50 plan aspect; same assumption"),
    "face_deg": dict(lo=65.0, hi=110.0, read=None, tag="【推測】", weak=True,
                     note="face chord 0.1 -> 0.8 Hs; the face is seen head-on; the lip's side end drops vertically ~0.35 H below the "
                          "summit, so the upper face is about vertical or overhanging"),
    "concavity": dict(lo=0.02, hi=0.40, read=None, tag="【推測】", weak=True, note="face behind its chord / Hs; streaks show a concave sheet"),
    "back_deg": dict(lo=25.0, hi=None, read=None, tag="【選び】", weak=True,
                     note="not visible; the frozen D ruler threshold back_best >= 25 deg (plan_D_frozen.json) is kept as the reference"),
}
INFO_NOT_MEASURABLE = {
    "spray_plume": "solid summit to plume top ~150 px of H 365 px (0.35-0.5 H), plume width ~380 px (~1 H); hf / r2 are the water "
                   "surface only, so the plume is not measured",
    "streak_convergence": "face streaks converge toward the summit (lateral inflow toward the peak); no 3D velocity is recorded "
                          "(r3 velocity only at y = 77 m), so this is not measured",
    "absolute_height": "no scale in the picture; only ratios are read",
}


# ====================================================================== records
_IDX = {}


def _index(rd, kind):
    key = (os.path.normpath(rd), kind)
    if key not in _IDX:
        rows = []
        for p in sorted(glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind))):
            with np.load(p) as d:
                fr = np.array(d["frames"], dtype=np.int64)
            rows.append((p, fr))
        _IDX[key] = rows
    return _IDX[key]


_CACHE = {}


def _block(p, key):
    ck = (p, key)
    if ck not in _CACHE:
        if len(_CACHE) > 6:
            _CACHE.pop(next(iter(_CACHE)))
        with np.load(p) as d:
            _CACHE[ck] = (np.array(d[key]), json.loads(str(d["meta"])), np.array(d["frames"], dtype=np.int64))
    return _CACHE[ck]


def load_frame(rd, kind, frame, key):
    """one frame of hf (key 'eta') or r2 (key 'sdf'); the later launch wins. -> (array float64, meta) or (None, None)."""
    hit = None
    for p, fr in _index(rd, kind):
        if int(frame) in fr:
            hit = p
    if hit is None:
        return None, None
    a, meta, fr = _block(hit, key)
    i = int(np.where(fr == int(frame))[0][0])
    return a[i].astype(np.float64), meta


def frames_available(rd, kind="hf"):
    s = set()
    for _, fr in _index(rd, kind):
        s.update(int(v) for v in fr)
    return s


def still_offset(rd):
    p = os.path.join(rd, "pana", "events.json")
    try:
        with open(p, encoding="utf-8") as fh:
            return float(json.load(fh)["still_offset_m"])
    except Exception:
        return 0.0


def t_of(frame):
    return (int(frame) - 1) / FPS


# ====================================================================== helpers
def median3(a):
    """3x3 nan-median (edges padded by replication)."""
    p = np.pad(a, 1, mode="edge")
    n0, n1 = a.shape
    st = np.stack([p[i:i + n0, j:j + n1] for i in range(3) for j in range(3)], 0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(st, axis=0)


def mirror_y(eta_half, meta):
    """half tank (y >= 0, rows at z0 + k dz) -> full lateral field y in [-W, W]."""
    ny = eta_half.shape[0]
    yh = float(meta["z0"]) + float(meta["dz"]) * np.arange(ny)
    eta = np.concatenate([eta_half[::-1], eta_half], 0)
    y = np.concatenate([-yh[::-1], yh])
    return eta, y


def xs_of(meta, nx):
    return float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)


def run_width(prof, coord, i0, level):
    """contiguous run of prof >= level around index i0 with linear interpolation of the two crossings.
    -> (width, censored, lo, hi). censored = the run reaches the end of the array (width is then a lower bound)."""
    n = len(prof)
    if not np.isfinite(prof[i0]) or prof[i0] < level:
        return 0.0, False, float(coord[i0]), float(coord[i0])
    cens = False
    j = i0
    while j + 1 < n and np.isfinite(prof[j + 1]) and prof[j + 1] >= level:
        j += 1
    if j + 1 >= n:
        hi = float(coord[j]); cens = True
    elif not np.isfinite(prof[j + 1]):
        hi = float(coord[j])
    else:
        a, b = prof[j], prof[j + 1]
        hi = float(coord[j] + (coord[j + 1] - coord[j]) * (a - level) / max(a - b, 1e-12))
    j = i0
    while j - 1 >= 0 and np.isfinite(prof[j - 1]) and prof[j - 1] >= level:
        j -= 1
    if j - 1 < 0:
        lo = float(coord[j]); cens = True
    elif not np.isfinite(prof[j - 1]):
        lo = float(coord[j])
    else:
        a, b = prof[j], prof[j - 1]
        lo = float(coord[j] - (coord[j] - coord[j - 1]) * (a - level) / max(a - b, 1e-12))
    return hi - lo, cens, lo, hi


def _interp(prof, coord, v):
    if v < coord[0] or v > coord[-1]:
        return float("nan")
    return float(np.interp(v, coord, prof))


# ====================================================================== height-field metrics (M1-M5)
def hf_metrics(eta_abs_half, meta, eta0, xwin=None, cw_back=None, cw_front=None):
    """eta_abs_half: hf frame (half tank, absolute heights). -> dict of the M1-M5 numbers (widths / Hc)."""
    cw_back = FROZEN["crest_window_m"]["back"] if cw_back is None else cw_back
    cw_front = FROZEN["crest_window_m"]["front"] if cw_front is None else cw_front
    eta_half = median3(eta_abs_half) - eta0
    eta, y = mirror_y(eta_half, meta)
    x = xs_of(meta, eta.shape[1])
    sel = np.ones_like(x, bool) if xwin is None else (x >= xwin[0]) & (x <= xwin[1])
    sub = np.where(sel[None, :], eta, np.nan)
    if not np.isfinite(sub).any():
        return None
    iy, ix = np.unravel_index(np.nanargmax(sub), sub.shape)
    Hc = float(eta[iy, ix]); x_pk = float(x[ix]); y_pk = float(y[iy])
    out = dict(Hc=Hc, x_pk=x_pk, y_pk=abs(y_pk), Hc_raw=float(np.nanmax(np.where(sel[None, :], np.concatenate(
        [eta_abs_half[::-1], eta_abs_half], 0), np.nan)) - eta0))
    if Hc <= 0.5:
        return out
    # crest line c(y)
    cwin = (x >= x_pk - cw_back) & (x <= x_pk + cw_front)
    c = np.nanmax(np.where(cwin[None, :], eta, -np.inf), axis=1)
    c[~np.isfinite(c)] = np.nan
    out["y_extent"] = [float(y[0]), float(y[-1])]
    W = {}
    cens = {}
    for f in FRACS:
        w, ce, lo, hi = run_width(c, y, iy, f * Hc)
        W["%.2f" % f] = w / Hc
        cens["%.2f" % f] = bool(ce)
    out["W_curve"] = W
    out["W_censored"] = cens
    for nm, f in (("W20", 0.2), ("W50", 0.5), ("W80", 0.8), ("W95", 0.95)):
        out[nm] = W["%.2f" % f]
        out[nm + "_cens"] = cens["%.2f" % f]
    out["taper"] = out["W80"] / out["W50"] if out["W50"] > 0 else float("nan")
    out["taper_cens"] = bool(out["W50_cens"])            # W50 censored -> taper is an upper bound
    out["K"] = out["W20"] / out["W80"] if out["W80"] > 0 else float("nan")
    out["K_cens"] = bool(out["W20_cens"])                # W20 censored -> K is a lower bound
    # M1 dominance
    for nm, k in (("S1", 1.0), ("S2", 2.0)):
        v = [_interp(c, y, y_pk - k * Hc), _interp(c, y, y_pk + k * Hc)]
        v = [a for a in v if np.isfinite(a)]
        out[nm] = float(np.mean(v)) / Hc if v else float("nan")
    XX, YY = np.meshgrid(x, y)
    r = np.hypot(XX - x_pk, YY - y_pk)
    ring = (r >= FROZEN["ring_Hc"][0] * Hc) & (r <= FROZEN["ring_Hc"][1] * Hc) & (XX <= x_pk + FROZEN["ring_front_m"]) & np.isfinite(eta)
    if ring.any():
        v = eta[ring] / Hc
        out["ring_max"] = float(np.max(v)); out["ring_p90"] = float(np.percentile(v, 90)); out["ring_mean"] = float(np.mean(v))
        out["H_over_ring_mean"] = (Hc - float(np.mean(eta[ring]))) / Hc
    # excess FWHM over the side level (continuity with the old 'crest c(y) excess FWHM'): side = median c(y) for |y - y_pk| >= 6 Hc
    far = np.abs(y - y_pk) >= 6.0 * Hc
    if far.any() and np.isfinite(c[far]).any():
        cs = float(np.nanmedian(c[far]))
        w, ce, _, _ = run_width(c, y, iy, cs + 0.5 * (Hc - cs))
        out["c_side_6Hc"] = cs / Hc
        out["FWHM_excess"] = w / Hc
        out["FWHM_excess_m"] = w
        out["FWHM_excess_cens"] = bool(ce)
    # M5 longitudinal (summit row)
    row = eta[iy]
    for nm, f in (("Lx50", 0.5), ("Lx70", 0.7)):
        w, ce, lo, hi = run_width(row, x, ix, f * Hc)
        out[nm] = w / Hc
    out["A50"] = out["W50"] / out["Lx50"] if out["Lx50"] > 0 else float("nan")
    # auxiliary: base = front trough of the summit row
    fr = (x >= x_pk) & (x <= x_pk + 30.0)
    if np.isfinite(row[fr]).any():
        tr = float(np.nanmin(row[fr]))
        Hf = Hc - tr
        out["trough_front"] = tr
        out["H_front_row"] = Hf
        if Hf > 0.5:
            w, ce, _, _ = run_width(c, y, iy, tr + 0.5 * Hf)
            out["W50_tr"] = w / Hf
            out["W50_tr_cens"] = bool(ce)
    return out


# ====================================================================== section metrics (M6)
def _level_row(sdf, zs, z):
    """sdf sampled at height z (linear between rows)."""
    if z <= zs[0] or z >= zs[-1]:
        return None
    k = int(np.searchsorted(zs, z)) - 1
    w = (z - zs[k]) / (zs[k + 1] - zs[k])
    return (1.0 - w) * sdf[k] + w * sdf[k + 1]


def _runs(neg):
    """index runs [a, b] of True."""
    out = []
    n = len(neg); i = 0
    while i < n:
        if neg[i]:
            j = i
            while j + 1 < n and neg[j + 1]:
                j += 1
            out.append((i, j)); i = j + 1
        else:
            i += 1
    return out


def _cross(s, x, i_in, i_out):
    """x of the zero crossing between a water index i_in (s < 0) and its air neighbour i_out."""
    a, b = s[i_in], s[i_out]
    return float(x[i_in] + (x[i_out] - x[i_in]) * (-a) / max(b - a, 1e-12))


def section_metrics(sdf, meta, eta0, x_hint, back_m=None, front_m=None):
    """centre section r2: sdf[z, x] (Houdini y up). -> dict face / concavity / overhang / back (Hs = section crest over still)."""
    S = FROZEN["section"]
    back_m = S["window_back_m"] if back_m is None else back_m
    front_m = S["window_front_m"] if front_m is None else front_m
    nz, nx = sdf.shape
    x = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
    zs = float(meta["y0"]) + float(meta["dy"]) * np.arange(nz) - eta0
    win = (x >= x_hint - back_m) & (x <= x_hint + front_m)
    xi = np.where(win)[0]
    if len(xi) < 5:
        return None
    sw = sdf[:, xi].astype(np.float64); xw = x[xi]
    neg = sw < 0
    has = neg.any(0)
    jtop = nz - 1 - np.argmax(neg[::-1], axis=0)
    jtop = np.clip(jtop, 0, nz - 2)
    cols = np.arange(len(xi))
    vj = sw[jtop, cols]; vj1 = sw[jtop + 1, cols]
    frac = np.where(vj1 - vj > 1e-9, -vj / np.maximum(vj1 - vj, 1e-9), 0.0)
    top = np.where(has, zs[jtop] + (zs[1] - zs[0]) * np.clip(frac, 0, 1), np.nan)
    if not np.isfinite(top).any():
        return None
    ic = int(np.nanargmax(top)); Hs = float(top[ic]); xc = float(xw[ic])
    out = dict(Hs=Hs, x_c_sec=xc)
    if Hs < 1.0:
        return out

    def level(fz):
        s = _level_row(sw, zs, fz * Hs)
        if s is None:
            return None
        rr = _runs(s < 0)
        if not rr:
            return None
        main = max(rr, key=lambda ab: ab[1] - ab[0])        # the wave body at this level = the longest run
        a, b = main
        xf = _cross(s, xw, b, b + 1) if b + 1 < len(s) else float(xw[b])
        xb = _cross(s, xw, a, a - 1) if a - 1 >= 0 else float(xw[a])
        last = rr[-1][1]
        xany = _cross(s, xw, last, last + 1) if last + 1 < len(s) else float(xw[last])
        return dict(xf=xf, xb=xb, xany=xany)

    z1, z2 = S["toe"], S["top"]
    L1 = level(z1); L2 = level(z2)
    if L1 and L2:
        dx = L1["xf"] - L2["xany"]                           # toe minus upper front: > 0 for a face leaning back, < 0 overhanging
        out["face_deg"] = math.degrees(math.atan2((z2 - z1) * Hs, dx))
        # concavity: the body front behind the chord, between the two levels
        dmax = 0.0
        for fz in np.linspace(z1, z2, 15)[1:-1]:
            L = level(fz)
            if not L:
                continue
            xch = L1["xf"] + (L2["xany"] - L1["xf"]) * (fz - z1) / (z2 - z1)
            dmax = max(dmax, xch - L["xf"])
        out["concavity"] = dmax / Hs
        ov = -1e9
        for fz in np.linspace(0.5, 0.98, 13):
            L = level(fz)
            if L:
                ov = max(ov, L["xany"] - L1["xf"])
        out["overhang"] = ov / Hs if ov > -1e8 else float("nan")
    b1, b2 = S["back_levels"]
    B1 = level(b1); B2 = level(b2)
    if B1 and B2:
        out["back_deg"] = math.degrees(math.atan2((b2 - b1) * Hs, max(B2["xb"] - B1["xb"], 1e-6)))
    return out


# ====================================================================== frame / breaker / run
def frame_metrics(rd, frame, xwin=None, eta0=None, with_section=True):
    eta0 = still_offset(rd) if eta0 is None else eta0
    a, meta = load_frame(rd, "hf", frame, "eta")
    if a is None:
        return None
    m = hf_metrics(a, meta, eta0, xwin=xwin)
    if m is None:
        return None
    m["frame"] = int(frame); m["t"] = t_of(frame)
    if with_section and "W50" in m:
        s, smeta = load_frame(rd, "r2", frame, "sdf")
        if s is not None:
            sm = section_metrics(s, smeta, eta0, m["x_pk"])
            if sm:
                m.update(sm)
    return m


def score_vs_target(m, core=None):
    """target miss (0 = inside every core range). -> (miss, per-metric dict)."""
    core = FROZEN["core"] if core is None else core
    tot = 0.0; per = {}
    for k in core:
        v = m.get(k)
        T = TARGET[k]
        if v is None or not np.isfinite(v) or v <= 0:
            per[k] = None; continue
        lo, hi = T["lo"], T["hi"]
        d = 0.0
        if hi is not None and v > hi:
            d = math.log(v / hi)
        elif lo is not None and v < lo:
            d = math.log(lo / v)
        per[k] = d; tot += d
    return tot, per


def breaker_instants(rd, ev, best, eta0, avail):
    """ev = events.json event; best = best_frames per_breaker row (or None)."""
    xwin = (ev["on_x"] + FROZEN["peak_xwin_rel_onset_m"][0], ev["on_x"] + FROZEN["peak_xwin_rel_onset_m"][1])
    on_f = int(ev["on_f"])
    res = dict(k=ev["k"], on_f=on_f, on_t=ev["on_t"], on_x=ev["on_x"])
    # onset
    res["onset"] = frame_metrics(rd, on_f, xwin, eta0)
    # max (Hc only on the scan, then the full metrics on the arg max)
    f0 = on_f - int(round(3.0 * FPS)); f1 = on_f + int(round(1.5 * FPS))
    bestH = (-1e9, None)
    for f in range(f0, f1 + 1):
        if f not in avail:
            continue
        a, meta = load_frame(rd, "hf", f, "eta")
        e = median3(a) - eta0
        x = xs_of(meta, e.shape[1])
        sel = (x >= xwin[0]) & (x <= xwin[1])
        h = float(np.nanmax(e[:, sel]))
        if h > bestH[0]:
            bestH = (h, f)
    res["max"] = frame_metrics(rd, bestH[1], xwin, eta0) if bestH[1] is not None else None
    # best (print-like, old ruler)
    if best is not None:
        bx = (best["xc"] - 45.0, best["xc"] + 20.0)
        res["best"] = frame_metrics(rd, int(best["frame"]), bx, eta0)
        res["best_score3"] = best.get("score3")
        f_end = int(best["window_frames"][1])
    else:
        res["best"] = None
        f_end = on_f + int(round(2.5 * FPS))
    # tbest: smallest target miss
    tb = (1e9, None)
    for f in range(f0, f_end + 1):
        if f not in avail:
            continue
        m = frame_metrics(rd, f, xwin, eta0, with_section=False)
        if not m or "W50" not in m or m["Hc"] < FROZEN["tbest_min_Hc_over_on_eta"] * float(ev["on_eta"]):
            continue
        s, _ = score_vs_target(m)
        if s < tb[0]:
            tb = (s, f)
    res["tbest"] = frame_metrics(rd, tb[1], xwin, eta0) if tb[1] is not None else None
    for nm in ("onset", "max", "best", "tbest"):
        if res.get(nm):
            s, per = score_vs_target(res[nm])
            res[nm]["target_miss"] = s
            res[nm]["target_miss_per"] = per
    return res


KEYS_SUMMARY = ["Hc", "S1", "S2", "ring_max", "ring_mean", "W20", "W50", "W80", "W95", "taper", "K", "Lx50", "Lx70", "A50",
                "FWHM_excess", "c_side_6Hc", "W50_tr", "Hs", "face_deg", "concavity", "overhang", "back_deg", "target_miss"]


def _med(rows, inst, key):
    v = [r[inst][key] for r in rows if r.get(inst) and key in r[inst] and r[inst][key] is not None and np.isfinite(r[inst][key])]
    return float(np.median(v)) if v else None


def _anycens(rows, inst, key):
    return any(bool(r[inst].get(key + "_cens")) for r in rows if r.get(inst))


def run_metrics(rd, label=None):
    with open(os.path.join(rd, "pana", "events.json"), encoding="utf-8") as fh:
        E = json.load(fh)
    with open(os.path.join(rd, "pana", "best_frames.json"), encoding="utf-8") as fh:
        B = json.load(fh)
    eta0 = float(E["still_offset_m"])
    avail = frames_available(rd, "hf")
    bk = {int(p["k"]): p for p in B["per_breaker"]}
    rows = []
    for ev in E["events"]:
        if not ev.get("judged"):
            continue
        rows.append(breaker_instants(rd, ev, bk.get(int(ev["k"])), eta0, avail))
    summ = {}
    for inst in ("onset", "max", "best", "tbest"):
        summ[inst] = {k: _med(rows, inst, k) for k in KEYS_SUMMARY}
        summ[inst]["censored_any"] = {k: _anycens(rows, inst, k) for k in ("W20", "W50", "W80", "W95", "taper", "K")}
    ob = B.get("overall_best") or {}
    ob_row = next((r for r in rows if int(r["k"]) == int(ob.get("k", -1))), None)
    return dict(run=label or os.path.basename(rd), run_dir=rd.replace("\\", "/"), still_offset_m=eta0, n_judged=len(rows),
                overall_best=dict(k=ob.get("k"), frame=ob.get("frame"), metrics=(ob_row or {}).get("best")),
                median_judged=summ, per_breaker=rows)


# ====================================================================== CLI
RUNS = [
    ("DA3", ROOT + "/Unity/Build/FLIP49/runs/DA3_SC37y30_T12H7p5_dp0p5"),
    ("DM1A", ROOT + "/Unity/Build/FLIP50/runs/DM1A_D19B_T12_th80_dp0p5"),
    ("DF1A", ROOT + "/Unity/Build/FLIP50/runs/DF1A_D19B_T10_th80_dp0p5"),
    ("DG1", ROOT + "/Unity/Build/FLIP50/runs/DG1_D19Bgr_T12_th80_dp0p5"),
]


def _self_sha():
    with open(os.path.abspath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return None if not np.isfinite(v) else round(v, 4)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def freeze():
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "target_frozen.json")
    doc = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip51/e51_metrics.py", tool_sha256=_self_sha(),
               frozen=FROZEN, target=TARGET, not_measurable=INFO_NOT_MEASURABLE,
               picture="Unity/Build/FLIP50/_scratch/target/user_target_20261017.jpg (git-ignored; read only, never copied)")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(_clean(doc), fh, ensure_ascii=False, indent=1)
    print("wrote", p)


def baseline():
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    res = {}
    for lab, rd in RUNS:
        ts = time.time()
        res[lab] = run_metrics(rd, lab)
        print(lab, "%.1f s" % (time.time() - ts), flush=True)
    table = []
    for lab in res:
        for inst in ("best", "max", "onset", "tbest"):
            s = res[lab]["median_judged"][inst]
            table.append(dict(run=lab, instant=inst, **{k: s.get(k) for k in KEYS_SUMMARY}))
    doc = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip51/e51_metrics.py", tool_sha256=_self_sha(),
               frozen=FROZEN, target=TARGET, not_measurable=INFO_NOT_MEASURABLE,
               note="all run numbers 【測定】 (FLIP records, numpy); target ranges 【推測】 (read from a perspective picture); "
                    "widths and heights are / Hc of the same frame; median over the judged breakers of each run",
               table_median_judged=table, runs=res, elapsed_s=time.time() - t0)
    p = os.path.join(OUT_DIR, "baseline.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(_clean(doc), fh, ensure_ascii=False, indent=1)
    print("wrote", p, "%.1f s" % (time.time() - t0))
    return doc


def gap(doc):
    """per run x instant: value / target read value for the readable metrics (1 = on the read value), and the best case over all."""
    keys = [k for k in ("W50", "W80", "W95", "W20", "S1", "S2", "ring_max", "taper", "K") if TARGET[k]["read"]]
    rows = []
    for r in doc["table_median_judged"]:
        rows.append(dict(run=r["run"], instant=r["instant"],
                         **{k: (None if r.get(k) is None else r[k] / TARGET[k]["read"]) for k in keys}))
    best = {}
    for k in keys:
        cand = [(abs(math.log(x[k])), x[k], x["run"], x["instant"]) for x in rows if x.get(k)]
        if cand:
            c = min(cand)
            best[k] = dict(ratio=c[1], run=c[2], instant=c[3])
    return dict(rule="ratio = median measured value / target read value (【測定】 / 【推測】); widths in Hc of the same frame",
                rows=rows, closest=best)


def add_gap():
    p = os.path.join(OUT_DIR, "baseline.json")
    with open(p, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["gap"] = gap(doc)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(_clean(doc), fh, ensure_ascii=False, indent=1)
    print("gap added to", p)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    if a[0] == "freeze":
        freeze()
    elif a[0] == "baseline":
        baseline()
        add_gap()
    elif a[0] == "gap":
        add_gap()
    elif a[0] == "frame":
        rd, f = a[1], int(a[2])
        xw = (float(a[3]), float(a[4])) if len(a) >= 5 else None
        m = frame_metrics(rd, f, xw)
        s, per = score_vs_target(m)
        m["target_miss"] = s; m["target_miss_per"] = per
        print(json.dumps(_clean(m), ensure_ascii=False, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
