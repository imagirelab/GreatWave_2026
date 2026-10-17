# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: reading of the 1.0 m smoke (pipeline gates only) and of a 0.5 m run under the FROZEN plan rules, per group of the
period P = 28 s (py -3.10 -B; numpy, scipy). 2026-10-17 written new (Claude). Read only on every run folder; writes only <run>/g52/ (or the
session scratchpad given with --out, for tests on runs of other campaigns). The frozen ruler flip51/e51_metrics.py (sha 91a2f041..) is
imported READ ONLY (hf_metrics, score_vs_target, median3, mirror_y, section_metrics, load_frame).

Definitions (plan_DFG_frozen.json gates / analysis; numbers in GATES / ELIG / DEC below, checked against the plan by `selftest`):
  eta0        the run's online still offset (run record info.still_offset_online: median top-surface height over x 60-205 m, t 0.5-1.5 s)
  groups      n = 1, 2, 3 with t_fn = 44, 72, 100 s. 'max' instant = the largest Hc of the 3x3-median hf - eta0 over x 90-190 m, |y| <= 60 m in
              [t_fn - 6, t_fn + 4] s; if an overturning onset falls in that window, the e51 'max' of that onset instead: argmax Hc in
              [on_f - 3 s, on_f + 1.5 s], summit searched in x [on_x - 60, on_x + 35] m (plan E D rule). Onset detector: see amendment AM-DFG1
              (the centre-section lip of g52_ana.lip_cols, because the g50 centre-track detector is hard-wired to layout D).
  metrics     e51 hf_metrics with rows y > 65 m set to NaN, xwin 90-190 m (or the onset window), core miss = score_vs_target; medians over
              the groups. N1 (plan E definition): 15 m max filter at the 'max' instant, x 60-205 m, |y| <= 65 m, r <= 100 m, outside
              r < 4 Hc of the summit and of its mirror, / Hc. Nt: largest interior Hc_scan (x 60-205 m, |y| <= 65 m) in [t_fn - 14, t_fn + 14)
              at |t - t_max| >= 3.5 s, / Hc. c_in: largest crest on the line x 60 m (|y| <= 65 m) in [t_fn - 14, t_fn + 14).
  gates A     G1 table + build + precheck; G2f harmonic fit per frequency at x 60 m, y 0.5/15/30/45/60 m over t 32-88 s (mean + n 3, 4, 5 +
              nuisance n 6-10); G3P recurrence; G4 band steepness kp x crest <= 0.40 (t 30-105 s, inlet band x <= 50 m all y, generating side
              band y >= 70 m, x <= 180 m) and no r2 lip at x < 60 m; G5 volume <= 2 %; G6 focus where / when designed; run complete, 3 groups.
  eligibility E1 N1 <= 0.65, E1t Nt <= 0.75, E2 Hc >= 5.0 m, E3 median Hc / median c_in >= 1.8 (medians over the groups)
  decision    the frozen decision_after_first_0p5 (bar = min(2.8, best valid 0.5 m miss - 0.5) with best = min(DF1A 3.3, valid E2 X2 / X1)).
usage:
  py -3.10 -B g52_ana.py smoke <run_dir> [--out=<dir>]       -> <run>/g52/smoke_DFG.json (last stdout line: summary json)
  py -3.10 -B g52_ana.py judge <run_dir> [--out=<dir>]       -> <run>/g52/judge_DFG.json (0.5 m: gates, eligibility, decision)
  py -3.10 -B g52_ana.py selftest                            frozen numbers vs the plan, harmonic fit and lip detector on synthetic data
Tags: [measured] [computed] [guess] [chosen].
"""
import os, sys, json, math, glob, time, warnings

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
from scipy import ndimage as ndi      # noqa: E402
import g52_common as GC               # noqa: E402
if GC.TOOLS51 not in sys.path:
    sys.path.append(GC.TOOLS51)
import e51_metrics as EM              # noqa: E402  frozen ruler (read only)

FPS = 24.0
E51_SHA = "91a2f0417f6f979cd1649e5bd0fc007d558722b005ac92142454c87be658e8ff"
GROUP = dict(win=(-6.0, 4.0), focal_x=GC.FOCAL_X, focal_y=GC.FOCAL_Y, ymask=GC.INTERIOR_Y, onset_back_s=3.0, onset_fwd_s=1.5,
             onset_xwin=(-60.0, 35.0), Nt_half=14.0, Nt_excl=3.5)
N1DEF = dict(win_m=15.0, x=list(GC.INTERIOR_X), ymax=GC.INTERIOR_Y, rmax=100.0, rex_Hc=4.0)
GATES = dict(G2f_t=(32.0, 88.0), G2f_x=60.0, G2f_y=list(GC.GAUGE_Y), G2f_nuisance=(6, 10),
             G2f_range_0p5={3: (0.85, 1.12), 4: (0.85, 1.12), 5: (0.80, 1.12)}, G2f_phase_0p5=0.35,
             G2f_range_1p0={3: (0.70, 1.15), 4: (0.70, 1.15), 5: (0.60, 1.15)}, G2f_phase_1p0=0.6,
             G3P_P=GC.P_S, G3P_tol=1.5, G3P_xspread=20.0, G3P_Hc_ratio=1.25,
             G4_kA=0.40, G4_t=(30.0, 105.0), G4_inlet_x=GC.IN_X1, G4_side_y=GC.SD0, G4_side_x=GC.SD_GEN, G4_lip_x=60.0, lip_z_min=0.5,
             G5_max=0.02, G6_x=(110.0, 170.0), G6_y=10.0, G6_t=(-3.0, 2.0), G6_Hc=4.1,
             smoke_summit_dt=4.0, smoke_spacing_tol=2.0, smoke_edge_s=0.25, smoke_edge_x=2.0)
ELIG = dict(N1_max=0.65, Nt_max=0.75, Hc_min=5.0, gain_min=1.8)
DEC = dict(bar_cap=2.8, bar_margin=0.5, DF1A_miss=3.3, target_band=0.5, jet_ratio=1.30, jet_groups=2, linear_crest=6.331, B2_no_overturn_groups=2,
           B1_N1_max=0.40, overturn_win=(-4.0, 3.0), overturn_x=GC.FOCAL_X)
E2_RUNS = {"X2": GC.REPO + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/e51/judge_E05.json",
           "X1": GC.REPO + "/Unity/Build/FLIP51/runs/S51X1_D19B_T7_l60d15_dp0p5/e51/judge_E05.json"}
REPORT_KEYS = ["Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "ring_p90", "ring_mean", "Lx50", "Lx70",
               "A50", "FWHM_excess", "c_side_6Hc", "W50_tr", "H_front_row", "Hs", "face_deg", "concavity", "overhang", "back_deg", "miss", "N1", "Hc_raw"]


# ====================================================================== records
def recs(rd):
    return [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]


def load_cfg(rd):
    p = os.path.join(rd, "cfg.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}


def still_offset(rd, rr=None):
    for r in (rr if rr is not None else recs(rd)):
        o = (r.get("info") or {}).get("still_offset_online")
        if o and o.get("value") is not None:
            return float(o["value"]), "online (run_c%05d info.still_offset_online)" % int(r.get("f_start") or 0)
    return 0.0, "none found (0)"


class Blocks:
    """frames of one record kind (hf: key 'eta', r2 / r4: key 'sdf'); overlapping blocks of a restarted chain: the later launch wins."""

    def __init__(self, rd, kind, key):
        self.key = key
        self.where = {}
        for p in sorted(glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind))):
            with np.load(p) as d:
                fr = np.array(d["frames"], dtype=np.int64)
            for i, f in enumerate(fr):
                self.where[int(f)] = (p, i)
        self._c = {}

    def frames(self):
        return sorted(self.where)

    def get(self, f):
        if int(f) not in self.where:
            return None, None
        p, i = self.where[int(f)]
        if p not in self._c:
            if len(self._c) >= 2:
                self._c.pop(next(iter(self._c)))
            with np.load(p) as d:
                self._c[p] = (np.array(d[self.key]), json.loads(str(d["meta"])))
        a, meta = self._c[p]
        return a[i].astype(np.float64), meta


def load_r6(rd):
    best = {}
    gxy = vnames = None
    for p in sorted(glob.glob(os.path.join(rd, "r6_c*.npz")), key=lambda q: int(os.path.basename(q)[4:9])):
        d = np.load(p)
        if "vol" not in d.files:
            continue
        gxy = d["gauge_xy"] if "gauge_xy" in d.files else None
        vnames = [str(v) for v in d["vol_names"]]
        for i, f in enumerate(d["frames"]):
            best[int(f)] = (float(d["t"][i]), d["vol"][i], int(d["npts"][i]))
    fr = np.array(sorted(best))
    return dict(frames=fr, t=np.array([best[f][0] for f in fr]), vol=np.array([best[f][1] for f in fr]), npts=np.array([best[f][2] for f in fr]),
                gxy=gxy, vnames=vnames)


def axes(meta, shape):
    nz, nx = shape
    return float(meta["x0"]) + float(meta["dx"]) * np.arange(nx), float(meta["z0"]) + float(meta["dz"]) * np.arange(nz)


def interp2(e, xs, ys, x, y):
    """bilinear value of a (y, x) field at (x, y) (clamped)."""
    fx = np.clip((x - xs[0]) / (xs[1] - xs[0]), 0, len(xs) - 1.000001); fy = np.clip((y - ys[0]) / (ys[1] - ys[0]), 0, len(ys) - 1.000001)
    i = int(fx); j = int(fy); wx = fx - i; wy = fy - j
    return float((1 - wx) * (1 - wy) * e[j, i] + wx * (1 - wy) * e[j, i + 1] + (1 - wx) * wy * e[j + 1, i] + wx * wy * e[j + 1, i + 1])


def masked(a, meta, ymax):
    _, yh = axes(meta, a.shape)
    b = a.copy()
    b[yh > ymax + 1e-9, :] = np.nan
    return b


# ====================================================================== the per-frame pass
def pass_frames(H, eta0, t_lo, t_hi, kp):
    """per hf frame in [t_lo, t_hi]: Hc_scan (interior), Hc_focal (focal window), c60 (line x 60 m), band steepness, gauge values."""
    fr = [f for f in H.frames() if t_lo - 1e-9 <= (f - 1) / FPS <= t_hi + 1e-9]
    out = dict(f=[], t=[], Hc=[], x=[], y=[], Hf=[], xf=[], yf=[], c60=[], kA_in=[], kA_sd=[], g2=[], rep=[], lvl_exit=[])
    key = None
    rep_pts = ((GC.X_F, 0.5), (190.0, 0.5), (200.0, 0.5), (190.0, 30.0), (200.0, 30.0))
    for f in fr:
        a, meta = H.get(f)
        e = EM.median3(a) - eta0
        xs, yh = axes(meta, e.shape)
        if key != (e.shape, float(meta["x0"]), float(meta["z0"])):
            key = (e.shape, float(meta["x0"]), float(meta["z0"]))
            inter = ((yh <= GC.INTERIOR_Y + 1e-9)[:, None] & ((xs >= GC.INTERIOR_X[0]) & (xs <= GC.INTERIOR_X[1]))[None, :])
            foc = ((yh <= GC.FOCAL_Y + 1e-9)[:, None] & ((xs >= GC.FOCAL_X[0]) & (xs <= GC.FOCAL_X[1]))[None, :])
            inl = np.zeros(e.shape, bool); inl[:, xs <= GATES["G4_inlet_x"] + 1e-9] = True
            sd = np.zeros(e.shape, bool); sd[np.ix_(yh >= GATES["G4_side_y"] - 1e-9, xs <= GATES["G4_side_x"] + 1e-9)] = True
            i0 = int(np.clip(np.searchsorted(xs, 60.0) - 1, 0, len(xs) - 2)); w60 = (60.0 - xs[i0]) / (xs[i0 + 1] - xs[i0])
            rowin = yh <= GC.INTERIOR_Y + 1e-9
            exit_reg = ((yh <= GC.INTERIOR_Y + 1e-9)[:, None] & ((xs >= 190.0) & (xs <= 200.0))[None, :])
        for msk, kk in ((inter, ("Hc", "x", "y")), (foc, ("Hf", "xf", "yf"))):
            v = np.where(msk, e, np.nan)
            if np.isfinite(v).any():
                j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
                out[kk[0]].append(float(v[iy, ix])); out[kk[1]].append(float(xs[ix])); out[kk[2]].append(float(yh[iy]))
            else:
                out[kk[0]].append(np.nan); out[kk[1]].append(np.nan); out[kk[2]].append(np.nan)
        line = (1 - w60) * e[:, i0] + w60 * e[:, i0 + 1]
        out["c60"].append(float(np.nanmax(np.where(rowin, line, np.nan))) if np.isfinite(line[rowin]).any() else np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            out["kA_in"].append(float(kp * np.nanmax(np.where(inl, e, np.nan))))
            out["kA_sd"].append(float(kp * np.nanmax(np.where(sd, e, np.nan))))
            out["lvl_exit"].append(float(np.nanmean(np.where(exit_reg, e, np.nan))))
        out["g2"].append([interp2(e, xs, yh, GATES["G2f_x"], y) for y in GATES["G2f_y"]])
        out["rep"].append([interp2(e, xs, yh, x, y) for x, y in rep_pts])
        out["f"].append(int(f)); out["t"].append((f - 1) / FPS)
    o = {k: np.asarray(v, float) for k, v in out.items()}
    o["f"] = o["f"].astype(int)
    o["rep_pts"] = rep_pts
    return o


# ====================================================================== harmonic fit (G2f and reports)
def harmonic_fit(t, e, P=GC.P_S, ns=GC.HARMONICS, nuisance=(6, 10), tf=GC.T_F):
    """least-squares fit e(t) = m + sum_n (a_n cos(w_n t') + b_n sin(w_n t')) for n in ns and nuisance harmonics n_lo..n_hi, w_n = 2 pi n/P,
    t' = t - tf. Returns {n: A_n = a_n + i b_n} (the table convention eta_n = Re(A_n e^{-i w_n t'})), the mean and the rms residual."""
    t = np.asarray(t, float); e = np.asarray(e, float)
    ok = np.isfinite(e)
    t = t[ok]; e = e[ok]
    allns = list(ns) + [n for n in range(nuisance[0], nuisance[1] + 1) if n not in ns]
    cols = [np.ones_like(t)]
    for n in allns:
        w = 2 * math.pi * n / P
        cols += [np.cos(w * (t - tf)), np.sin(w * (t - tf))]
    M = np.stack(cols, 1)
    c, *_ = np.linalg.lstsq(M, e, rcond=None)
    A = {n: complex(c[1 + 2 * i], c[2 + 2 * i]) for i, n in enumerate(allns)}
    res = e - M @ c
    return dict(A={n: A[n] for n in ns}, nuisance={n: abs(A[n]) for n in allns if n not in ns}, mean=float(c[0]),
                rms_residual=float(np.sqrt(np.mean(res ** 2))) if len(res) else None, n=int(len(t)))


def g2f(PF, lin, kind):
    """G2f: R_n = sum_gauges |A_n fit| / sum_gauges |A_n linear|, phase error = arg(sum A_n fit conj(A_n linear))."""
    t = PF["t"]
    sel = (t >= GATES["G2f_t"][0] - 1e-9) & (t <= GATES["G2f_t"][1] + 1e-9)
    rng = GATES["G2f_range_0p5"] if kind == "0p5" else GATES["G2f_range_1p0"]
    phmax = GATES["G2f_phase_0p5"] if kind == "0p5" else GATES["G2f_phase_1p0"]
    out = dict(window=list(GATES["G2f_t"]), n_frames=int(sel.sum()), per_n={}, ranges={str(k): v for k, v in rng.items()}, phase_max_rad=phmax,
               span_s=float(t[sel].max() - t[sel].min()) if sel.any() else 0.0)
    if sel.sum() < 100:
        out["ok"] = False; out["why"] = "too few frames in t 32-88 s"
        return out
    fits = [harmonic_fit(t[sel], PF["g2"][sel, i]) for i in range(len(GATES["G2f_y"]))]
    ok = out["span_s"] >= 2 * GC.P_S - 1.0
    for n in GC.HARMONICS:
        Af = [f_["A"][n] for f_ in fits]
        Al = [complex(*lin["y%g" % y]["n%d" % n]) for y in GATES["G2f_y"]]
        R = sum(abs(a) for a in Af) / sum(abs(a) for a in Al)
        ph = float(np.angle(sum(a * np.conj(b) for a, b in zip(Af, Al))))
        okn = bool(rng[n][0] <= R <= rng[n][1] and abs(ph) <= phmax)
        out["per_n"]["n%d" % n] = dict(R=R, phase_err_rad=ph, range=list(rng[n]), ok=okn,
                                       per_gauge=[dict(y=y, fit_abs=abs(a), lin_abs=abs(b), phase_err=float(np.angle(a * np.conj(b))))
                                                  for y, a, b in zip(GATES["G2f_y"], Af, Al)])
        ok = ok and okn
    out["nuisance_abs_max_m"] = float(max(max(f_["nuisance"].values()) for f_ in fits))
    out["rms_residual_m"] = [f_["rms_residual"] for f_ in fits]
    out["ok"] = bool(ok)
    out["rule"] = ("complex harmonic fit (mean + w3, w4, w5 + nuisance n 6-10) of the 3x3-median hf - eta0 at x 60 m, y 0.5/15/30/45/60 m over "
                   "t 32-88 s (2 P); R_n = sum|A_fit| / sum|A_lin|, phase error = arg(sum A_fit conj(A_lin))")
    return out


# ====================================================================== overturning lips (r2 centre section, r4 per-y sections)
def lip_cols(s, zs, x_ok, zmin=GATES["lip_z_min"]):
    """s: section SDF (vertical, x) (< 0 water). A column has a lip when its water has >= 2 runs (rising air->water edges going up) and the
    air cell just below the topmost run lies above eta0 + zmin (zs is already height above eta0). Returns the boolean column flags (x_ok mask)."""
    w = s < 0
    rise = w & ~np.vstack([np.zeros((1, w.shape[1]), bool), w[:-1]])
    nrise = rise.sum(0)
    ktop = np.where(rise.any(0), w.shape[0] - 1 - np.argmax(rise[::-1], axis=0), 0)
    gapz = zs[np.clip(ktop - 1, 0, len(zs) - 1)]
    return (nrise >= 2) & (ktop >= 1) & (gapz > zmin) & x_ok


def lip_hit(flags):
    """first x index where >= 2 adjacent columns are flagged, else None."""
    if len(flags) < 2:
        return None
    both = flags[1:] & flags[:-1]
    return int(np.where(both)[0][0]) if both.any() else None


def r2_lips(R2, eta0, frames, x_lo, x_hi):
    hits = []
    for f in frames:
        s, meta = R2.get(f)
        if s is None:
            continue
        nz, nx = s.shape
        xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
        zs = float(meta["y0"]) + float(meta["dy"]) * np.arange(nz) - eta0
        fl = lip_cols(s, zs, (xs >= x_lo) & (xs <= x_hi))
        k = lip_hit(fl)
        if k is not None:
            hits.append((int(f), float(xs[k])))
    return hits


def r4_lips(R4, eta0, frames, x_lo, x_hi, ymax=GC.INTERIOR_Y):
    """per-y sections of r4 (sdf[lateral, vertical, x]); returns [(frame, x, y)] of the first lip per frame."""
    hits = []
    for f in frames:
        s, meta = R4.get(f)
        if s is None:
            continue
        nzl, nyv, nx = s.shape
        xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
        zv = float(meta["y0"]) + float(meta["dy"]) * np.arange(nyv) - eta0
        yl = float(meta["z0"]) + float(meta["dz"]) * np.arange(nzl)
        xok = (xs >= x_lo) & (xs <= x_hi)
        for j in range(nzl):
            if yl[j] > ymax + 1e-9:
                continue
            k = lip_hit(lip_cols(s[j], zv, xok))
            if k is not None:
                hits.append((int(f), float(xs[k]), float(yl[j])))
                break
    return hits


# ====================================================================== N1 (plan E definition on the DFG interior)
def n1_isolation(e_half, meta, m):
    Hc = float(m["Hc"]); xp = float(m["x_pk"]); yp = abs(float(m["y_pk"]))
    if not np.isfinite(Hc) or Hc <= 0.5:
        return dict(N1=None)
    eta, y = EM.mirror_y(e_half, meta)
    x = EM.xs_of(meta, eta.shape[1])
    e = np.where(np.isfinite(eta), eta, -99.0)
    hx = max(1, int(math.floor(0.5 * N1DEF["win_m"] / float(meta["dx"]))))
    hy = max(1, int(math.floor(0.5 * N1DEF["win_m"] / float(meta["dz"]))))
    mx = ndi.maximum_filter(e, size=(2 * hy + 1, 2 * hx + 1), mode="constant", cval=-99.0)
    XX, YY = np.meshgrid(x, y)
    r = np.hypot(XX - xp, YY - yp); rm = np.hypot(XX - xp, YY + yp)
    rex = N1DEF["rex_Hc"] * Hc
    pk = ((e >= mx - 1e-12) & (e > 0.0) & (XX >= N1DEF["x"][0]) & (XX <= N1DEF["x"][1]) & (np.abs(YY) <= N1DEF["ymax"])
          & (r <= N1DEF["rmax"]) & (r >= rex) & (rm >= rex))
    if not pk.any():
        return dict(N1=0.0, at=None, n_candidates=0, filter_cells=[2 * hy + 1, 2 * hx + 1])
    i = int(np.argmax(np.where(pk, e, -99.0)))
    return dict(N1=float(e.flat[i] / Hc), at=[float(XX.flat[i]), float(YY.flat[i])], dist_m=float(r.flat[i]), n_candidates=int(pk.sum()),
                filter_cells=[2 * hy + 1, 2 * hx + 1])


def frame_full(rd, H, f, eta0, xwin):
    a, meta = H.get(f)
    b = masked(a, meta, GC.INTERIOR_Y)
    m = EM.hf_metrics(b, meta, eta0, xwin=xwin)
    if not m or "W50" not in m:
        return m
    m["frame"] = int(f); m["t"] = (int(f) - 1) / FPS
    miss, per = EM.score_vs_target(m)
    m["miss"] = miss; m["miss_per"] = per
    iso = n1_isolation(EM.median3(b) - eta0, meta, m)
    m["N1"] = iso.get("N1"); m["N1_detail"] = iso
    try:
        s, smeta = EM.load_frame(rd, "r2", f, "sdf")
        if s is not None:
            sm = EM.section_metrics(s, smeta, eta0, m["x_pk"])
            if sm:
                m.update(sm)
    except Exception as ex:
        m["section_error"] = repr(ex)[:200]
    return m


def med(rows, key):
    v = [r[key] for r in rows if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool) and np.isfinite(r[key])]
    return float(np.median(v)) if v else None


# ====================================================================== groups
def group_rows(rd, H, R2, R4, PF, eta0, t_end, kind):
    rows = []
    avail = set(H.frames())
    for n, tfn in enumerate(GC.FOCI, 1):
        a, b = tfn + GROUP["win"][0], tfn + GROUP["win"][1]
        row = dict(n=n, t_fn=tfn, window=[a, b])
        if b > t_end + 1e-9:
            row.update(complete=False, why="window beyond the record end %.2f s" % t_end); rows.append(row); continue
        sel = (PF["t"] >= a - 1e-9) & (PF["t"] <= b + 1e-9) & np.isfinite(PF["Hf"])
        if not sel.any():
            row.update(complete=False, why="no hf frames in the window"); rows.append(row); continue
        idx = np.where(sel)[0]
        i = int(idx[np.argmax(PF["Hf"][idx])])
        row.update(complete=True, scan=dict(f=int(PF["f"][i]), t=float(PF["t"][i]), Hc=float(PF["Hf"][i]), x=float(PF["xf"][i]), y=float(PF["yf"][i])))
        # overturning onset in the window (centre section r2, x 90-190 m): the plan E D rule moves the instant to the onset's e51 'max'
        fw = [int(f) for f in PF["f"][idx]]
        lips = r2_lips(R2, eta0, fw, GC.FOCAL_X[0], GC.FOCAL_X[1])
        row["onset"] = dict(frame=lips[0][0], t=(lips[0][0] - 1) / FPS, x=lips[0][1]) if lips else None
        f_use = row["scan"]["f"]; xwin = tuple(GC.FOCAL_X); inst = "scan max (x 90-190 m, |y| <= 60 m)"
        if lips:
            on_f, on_x = lips[0]
            xw = (on_x + GROUP["onset_xwin"][0], on_x + GROUP["onset_xwin"][1])
            best = (-1e9, None)
            for f in range(on_f - int(round(GROUP["onset_back_s"] * FPS)), on_f + int(round(GROUP["onset_fwd_s"] * FPS)) + 1):
                if f not in avail:
                    continue
                aa, mm = H.get(f)
                ee = EM.median3(masked(aa, mm, GC.INTERIOR_Y)) - eta0
                xs = EM.xs_of(mm, ee.shape[1])
                s_ = (xs >= xw[0]) & (xs <= xw[1])
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    h = float(np.nanmax(ee[:, s_])) if s_.any() else -1e9
                if h > best[0]:
                    best = (h, f)
            if best[1] is not None:
                f_use = best[1]; xwin = xw; inst = "onset rule: lip on r2 at t %.2f s, x %.1f m -> e51 max in [on - 3 s, on + 1.5 s], x [on_x - 60, on_x + 35]" % (
                    (on_f - 1) / FPS, on_x)
        m = frame_full(rd, H, f_use, eta0, xwin)
        if not m or "W50" not in m:
            row.update(complete=False, why="no crest metrics at frame %d" % f_use); rows.append(row); continue
        row.update({k: m.get(k) for k in REPORT_KEYS if k in m})
        row.update(f=int(f_use), t=(f_use - 1) / FPS, instant=inst, xwin=list(xwin), W_curve=m.get("W_curve"), W_censored=m.get("W_censored"),
                   miss_per=m.get("miss_per"), N1_detail=m.get("N1_detail"))
        # Nt: largest interior Hc_scan in [t_fn - 14, t_fn + 14) at |t - t_max| >= 3.5 s
        sw = (PF["t"] >= tfn - GROUP["Nt_half"] - 1e-9) & (PF["t"] < tfn + GROUP["Nt_half"] - 1e-9) & np.isfinite(PF["Hc"])
        far = sw & (np.abs(PF["t"] - row["t"]) >= GROUP["Nt_excl"] - 1e-9)
        cov = float(PF["t"][sw].max() - PF["t"][sw].min()) if sw.any() else 0.0
        if far.any() and row["Hc"]:
            j = int(np.where(far)[0][np.argmax(PF["Hc"][far])])
            row["Nt"] = float(PF["Hc"][j] / row["Hc"])
            row["Nt_at"] = dict(t=float(PF["t"][j]), x=float(PF["x"][j]), y=float(PF["y"][j]), H=float(PF["Hc"][j]))
        else:
            row["Nt"] = None
        row["Nt_coverage_s"] = cov
        row["c_in_coverage_s"] = cov          # the run ends at 105 s: group 3 sees [86, 105) only (reported, not changed)
        row["c_in60"] = float(np.nanmax(PF["c60"][sw])) if (sw.any() and np.isfinite(PF["c60"][sw]).any()) else None
        row["gain_over_c_in60"] = (row["Hc"] / row["c_in60"]) if (row.get("c_in60") and row.get("Hc")) else None
        row["jet_ratio"] = row["Hc"] / DEC["linear_crest"] if row.get("Hc") else None
        # B2 rule: overturning (lip) at the focus in r2 or r4, x 90-190 m, [t_fn - 4, t_fn + 3]
        ow = [int(f) for f in H.frames() if tfn + DEC["overturn_win"][0] - 1e-9 <= (f - 1) / FPS <= tfn + DEC["overturn_win"][1] + 1e-9]
        l2 = r2_lips(R2, eta0, ow, DEC["overturn_x"][0], DEC["overturn_x"][1])
        l4 = r4_lips(R4, eta0, [f for f in ow if f in set(R4.frames())], DEC["overturn_x"][0], DEC["overturn_x"][1]) if R4.frames() else []
        row["overturn"] = dict(any=bool(l2 or l4), r2_first=(dict(frame=l2[0][0], t=(l2[0][0] - 1) / FPS, x=l2[0][1]) if l2 else None),
                               r4_first=(dict(frame=l4[0][0], t=(l4[0][0] - 1) / FPS, x=l4[0][1], y=l4[0][2]) if l4 else None),
                               n_r2_frames=len(l2), n_r4_frames=len(l4), window=[tfn + DEC["overturn_win"][0], tfn + DEC["overturn_win"][1]])
        rows.append(row)
    return rows


# ====================================================================== gates
def gate_G1(rd, cfg):
    dr = cfg.get("dir") or {}
    s = dr.get("set") or "DFG2"
    tc = GC.PLAN_DIR + "/table_check_%s.json" % s
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    bc = GC.jload(GC.BUILD_CHECK) if os.path.exists(GC.BUILD_CHECK) else {}
    run_hips = sorted(set(r.get("hip_sha256") for r in recs(rd) if r.get("hip_sha256")))
    ok_tab = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256") and dr.get("npz") and os.path.exists(dr["npz"])
                  and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    ok_build = bool(bc.get("all_ok") and run_hips and all(h == bc.get("hip_sha256") for h in run_hips))
    ok_pre = bool((cfg.get("precheck") or {}).get("ok"))
    return dict(ok=bool(ok_tab and ok_build and ok_pre), table_check=ok_tab, build_check52=ok_build, cfg_precheck=ok_pre,
                hip_sha_runs=[h[:16] for h in run_hips], hip_sha_build=str(bc.get("hip_sha256"))[:16],
                rule="numpy table check per layer and total (table_check_<set>.json, same content hash as the cfg), build_check52 all_ok with the hip "
                     "the launches used, cfg precheck ok (table = the plan's set bit for bit)")


def gate_G3P(rows):
    ok_rows = [r for r in rows if r.get("complete")]
    ts = [r["t"] for r in ok_rows]
    sp = [b - a for a, b in zip(ts[:-1], ts[1:])]
    xs = [r["x_pk"] for r in ok_rows]
    Hs = [r["Hc"] for r in ok_rows]
    ok = bool(len(ok_rows) == 3 and all(abs(v - GATES["G3P_P"]) <= GATES["G3P_tol"] + 1e-9 for v in sp)
              and (max(xs) - min(xs)) <= GATES["G3P_xspread"] + 1e-9 and max(Hs) / max(min(Hs), 1e-9) <= GATES["G3P_Hc_ratio"] + 1e-9)
    return dict(ok=ok, summit_t=ts, spacings_s=sp, x_spread_m=(max(xs) - min(xs)) if xs else None, Hc_max_over_min=(max(Hs) / min(Hs)) if Hs else None,
                rule="three group summits ('max' instants) spaced 28.0 +- 1.5 s, summit x spread <= 20 m, Hc max/min <= 1.25")


def gate_G4(PF, R2, eta0, t_end):
    t = PF["t"]
    sel = (t >= GATES["G4_t"][0] - 1e-9) & (t <= min(GATES["G4_t"][1], t_end) + 1e-9)
    kin = float(np.nanmax(PF["kA_in"][sel])) if sel.any() else None
    ksd = float(np.nanmax(PF["kA_sd"][sel])) if sel.any() else None
    fr = [int(f) for f in PF["f"][sel]]
    lips = r2_lips(R2, eta0, fr, 3.0, GATES["G4_lip_x"])
    return dict(ok=bool(kin is not None and ksd is not None and kin <= GATES["G4_kA"] and ksd <= GATES["G4_kA"] and not lips),
                kA_inlet_max=kin, kA_side_max=ksd, kA_max=GATES["G4_kA"], kp=GC.kp(), r2_lips_x_lt_60=lips[:20], n_lip_frames=len(lips),
                t_inlet_max=float(t[sel][np.nanargmax(PF["kA_in"][sel])]) if sel.any() else None,
                t_side_max=float(t[sel][np.nanargmax(PF["kA_sd"][sel])]) if sel.any() else None,
                rule="kp x (3x3-median hf - eta0) <= 0.40 over t 30-105 s in the inlet band (x <= 50 m, all y) and the generating side band "
                     "(y >= 70 m, x <= 180 m); no overturning lip on r2 (y 0.5 m) at x < 60 m")


def gate_G5(R):
    vi = {nm: i for i, nm in enumerate(R["vnames"] or [])}
    if "V_m3" not in vi or not len(R["t"]):
        return dict(ok=False, why="no volume record")
    V = R["vol"][:, vi["V_m3"]]; t = R["t"]
    ref = (t >= 1.0 - 1e-9) & (t <= 1.5 + 1e-9); later = t > 1.5
    if not (ref.any() and later.any()):
        return dict(ok=False, why="no frames after 1.5 s")
    V0 = float(np.nanmean(V[ref]))
    vmax = float(np.nanmax(np.abs(V[later] / V0 - 1.0)))
    out = dict(ok=bool(vmax <= GATES["G5_max"]), max_rel=vmax, end_rel=float(V[-1] / V0 - 1.0), max=GATES["G5_max"],
               rule="max |V/V0 - 1| of the whole-tank column volume after 1.5 s (stage A)")
    if "Vwin_m3" in vi:
        Vw = R["vol"][:, vi["Vwin_m3"]]
        out["window_max_rel_report"] = float(np.nanmax(np.abs(Vw[later] / np.nanmean(Vw[ref]) - 1.0)))
    return out


def gate_G6(rows):
    bad = []
    for r in rows:
        if not r.get("complete"):
            bad.append(dict(n=r["n"], why=r.get("why"))); continue
        ok = (GATES["G6_x"][0] <= r["x_pk"] <= GATES["G6_x"][1] and abs(r["y_pk"]) <= GATES["G6_y"] + 1e-9
              and r["t_fn"] + GATES["G6_t"][0] - 1e-9 <= r["t"] <= r["t_fn"] + GATES["G6_t"][1] + 1e-9 and r["Hc"] >= GATES["G6_Hc"])
        if not ok:
            bad.append(dict(n=r["n"], x_pk=r["x_pk"], y_pk=r["y_pk"], t=r["t"], t_fn=r["t_fn"], Hc=r["Hc"]))
    return dict(ok=bool(not bad and len(rows) == 3), failing=bad,
                rule="each group's 'max' summit at x 110-170 m, |y| <= 10 m, t in [t_fn - 3, t_fn + 2] s, Hc >= 4.1 m")


def sponge_report(PF, lin_rep, kind):
    """report only: the mean level at x 190-200 m (|y| <= 65 m) and the per-frequency field at x 190/200 m (y 0.5/30 m), fitted over the two
    halves of t 32-88 s: a growing standing pattern would raise the second half."""
    t = PF["t"]
    out = dict(rule="report only (plan smoke_1p0 pass_rule: sponge behaviour reported, not gated)")
    m = (t >= 32.0) & (t <= 88.0)
    out["mean_level_x190_200_m"] = dict(t32_60=float(np.nanmean(PF["lvl_exit"][(t >= 32) & (t < 60)])) if ((t >= 32) & (t < 60)).any() else None,
                                        t60_88=float(np.nanmean(PF["lvl_exit"][(t >= 60) & (t <= 88)])) if ((t >= 60) & (t <= 88)).any() else None)
    rows = {}
    for k, (x, y) in enumerate(PF["rep_pts"]):
        key = "x%g_y%g" % (x, y)
        h1 = (t >= 32.0) & (t < 60.0); h2 = (t >= 60.0) & (t < 88.0)
        r_ = {}
        for nm, sl in (("t32_60", h1), ("t60_88", h2), ("t32_88", m)):
            if sl.sum() > 50:
                fit = harmonic_fit(t[sl], PF["rep"][sl, k])
                r_[nm] = {"n%d" % n: dict(abs=abs(fit["A"][n]), ratio_to_linear=abs(fit["A"][n]) / max(abs(complex(*lin_rep[key]["n%d" % n])), 1e-9))
                          for n in GC.HARMONICS}
        rows[key] = r_
    out["per_frequency"] = rows
    try:
        g = [rows[k]["t60_88"]["n%d" % n]["abs"] / max(rows[k]["t32_60"]["n%d" % n]["abs"], 1e-9) for k in ("x190_y0.5", "x200_y0.5", "x190_y30", "x200_y30")
             for n in GC.HARMONICS]
        out["second_over_first_half_max"] = float(max(g))
        out["growing_pattern_flag"] = bool(max(g) > 1.2)
    except Exception:
        pass
    return out


# ====================================================================== smoke and judge
def common(rd, kind, out_dir=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = load_cfg(rd)
    rr = recs(rd)
    eta0, eta0_src = still_offset(rd, rr)
    H = Blocks(rd, "hf", "eta"); R2 = Blocks(rd, "r2", "sdf"); R4 = Blocks(rd, "r4", "sdf")
    frames = H.frames()
    t_end = (max(frames) - 1) / FPS if frames else 0.0
    done = max([int(r.get("f_end_done") or 0) for r in rr] or [0])
    res = dict(run_id=os.path.basename(rd), run_dir=rd, kind=kind, plan=GC.PLAN_REL, plan_sha_ok=GC.plan_sha_ok(), tool="Tools/GWWaveGen/flip52/g52_ana.py",
               tool_sha256=GC.sha256_file(os.path.abspath(__file__)), e51_sha256=GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py"),
               e51_frozen_ok=GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py") == E51_SHA, amendments=[a.get("id") for a in GC.amendments()],
               date=time.strftime("%Y-%m-%d %H:%M:%S"), eta0=eta0, eta0_source=eta0_src, t_record_end=t_end, frames_n=len(frames),
               dp=float((cfg.get("parms") or {}).get("dp", 0.0)), set=(cfg.get("dir") or {}).get("set"))
    res["run_complete"] = dict(ok=bool(cfg and done >= int(cfg.get("f_end", 10 ** 9))), frames_done=done, f_end=cfg.get("f_end"))
    res["launches"] = [dict(f_start=r.get("f_start"), f_end_done=r.get("f_end_done"), stopped=r.get("stopped"), wall_s=r.get("wall_total_s"),
                            particles_max=r.get("particles_max"), rss_gb=r.get("rss_peak_gb"), substeps=r.get("substeps_min_max")) for r in rr]
    res["particles_max"] = max([r.get("particles_max") or 0 for r in rr] or [0])
    res["wall_h"] = sum([float(r.get("wall_total_s") or 0.0) for r in rr]) / 3600.0
    kp = GC.kp()
    PF = pass_frames(H, eta0, 25.0, t_end, kp)
    lin = ((cfg.get("dir") or {}).get("linear_refs") or {})
    res["G1"] = gate_G1(rd, cfg)
    res["G2f"] = g2f(PF, (lin.get("G2f_gauges") or {}).get("A_n") or {}, kind) if lin else dict(ok=False, why="cfg dir.linear_refs missing")
    res["G4"] = gate_G4(PF, R2, eta0, t_end)
    R = load_r6(rd)
    res["G5"] = gate_G5(R)
    try:
        res["focus_point_per_frequency_report"] = {"n%d" % n: dict(abs=abs(v), ratio_to_linear=abs(v) / max(abs(complex(*lin["report_gauges"]["x150_y0.5"]["n%d" % n])), 1e-9))
                                                   for n, v in harmonic_fit(PF["t"][(PF["t"] >= 30) & (PF["t"] < 86)],
                                                                            PF["rep"][(PF["t"] >= 30) & (PF["t"] < 86), 0])["A"].items()}
    except Exception as ex:
        res["focus_point_per_frequency_report"] = dict(error=repr(ex)[:200])
    res["sponge_report"] = sponge_report(PF, lin.get("report_gauges") or {}, kind) if lin else None
    res["per_frame"] = dict(t=PF["t"][::4], Hc_scan=PF["Hc"][::4], Hc_focal=PF["Hf"][::4], x_focal=PF["xf"][::4], c60=PF["c60"][::4])
    return res, cfg, H, R2, R4, PF, eta0, t_end


def smoke(rd, out_dir=None):
    t0 = time.time()
    res, cfg, H, R2, R4, PF, eta0, t_end = common(rd, "1p0", out_dir)
    # groups 1-2: a summit (time-local maximum, not at the window edge) at x 90-190 m within +-4 s of t_fn, spaced 28 +- 2 s
    sm = []
    for n, tfn in enumerate(GC.FOCI[:2], 1):
        sel = (PF["t"] >= tfn - GATES["smoke_summit_dt"] - 1e-9) & (PF["t"] <= tfn + GATES["smoke_summit_dt"] + 1e-9) & np.isfinite(PF["Hf"])
        if not sel.any():
            sm.append(dict(n=n, ok=False, why="no frames")); continue
        idx = np.where(sel)[0]
        i = int(idx[np.argmax(PF["Hf"][idx])])
        t_ = float(PF["t"][i]); x_ = float(PF["xf"][i])
        edge_t = min(t_ - (tfn - GATES["smoke_summit_dt"]), tfn + GATES["smoke_summit_dt"] - t_) <= GATES["smoke_edge_s"]
        edge_x = min(x_ - GC.FOCAL_X[0], GC.FOCAL_X[1] - x_) <= GATES["smoke_edge_x"]
        sm.append(dict(n=n, t_fn=tfn, t=t_, x=x_, y=float(PF["yf"][i]), Hc=float(PF["Hf"][i]), edge_t=bool(edge_t), edge_x=bool(edge_x),
                       ok=bool(not edge_t and not edge_x)))
    sp = (sm[1]["t"] - sm[0]["t"]) if (len(sm) == 2 and "t" in sm[0] and "t" in sm[1]) else None
    res["smoke_groups"] = dict(rows=sm, spacing_s=sp, ok=bool(all(r.get("ok") for r in sm) and sp is not None
                                                             and abs(sp - GC.P_S) <= GATES["smoke_spacing_tol"] + 1e-9),
                               rule="groups 1-2: a time-local summit of the 3x3-median hf - eta0 (x 90-190 m, |y| <= 60 m) inside [t_fn - 4, t_fn + 4] s "
                                    "(not within 0.25 s of the window ends, not within 2 m of x 90 / 190 m), spaced 28 +- 2 s")
    keys = ["run_complete", "G1", "G2f", "G4", "G5", "smoke_groups"]
    failed = [k for k in keys if not (res.get(k) or {}).get("ok")]
    res["smoke_pass"] = not failed
    res["failed"] = failed
    res["verdict"] = ("SMOKE_PASS: the 0.5 m run may start" if not failed else
                      "SMOKE_FAIL (%s): pipeline cause -> fix and smoke once more; the 0.5 m run does not start" % ", ".join(failed))
    res["note"] = "PIPELINE CHECK ONLY: the 1.0 m smoke is not shape-judged (plan smoke_1p0.role)"
    res["elapsed_s"] = round(time.time() - t0, 1)
    od = GC.guard_out(out_dir or os.path.join(res["run_dir"], "g52"), allow_scratch=True)
    p = os.path.join(od, "smoke_DFG.json")
    GC.jdump(res, p)
    res["_path"] = p.replace("\\", "/")
    return res


def e2_best():
    """the best valid 0.5 m median core miss among DF1A (3.3, measured) and the round-E2 X2 / X1 runs (judge_E05.json: plan E validity)."""
    rows = dict(DF1A=dict(miss=DEC["DF1A_miss"], valid=True, source="plan expected.core_miss.compare (measured)"))
    for k, p in E2_RUNS.items():
        if os.path.exists(p):
            try:
                j = GC.jload(p)
                rows[k] = dict(miss=j.get("core_miss_median"), valid=bool(j.get("valid")), outcomes=(j.get("judgement_05") or {}).get("outcomes"), source=p)
            except Exception as ex:
                rows[k] = dict(error=repr(ex)[:200], source=p)
        else:
            rows[k] = dict(missing=True, source=p)
    vals = [r["miss"] for r in rows.values() if r.get("valid") and isinstance(r.get("miss"), (int, float))]
    best = min(vals)
    return best, rows


def decide(res):
    """the frozen decision_after_first_0p5 (steps 1-4)."""
    g = res["gates"]
    failed = res["failed_gates"]
    pipe = {"run_complete", "G1", "G2f"}
    best, rows = e2_best()
    bar = min(DEC["bar_cap"], best - DEC["bar_margin"])
    out = dict(bar=bar, best_valid_0p5=best, best_rows=rows, rule="plan decision_after_first_0p5 (frozen)")
    if failed:
        cls = "pipeline" if any(k in pipe for k in failed) else "physics"
        out.update(valid=False, failure_class=cls, outcomes=["INVALID"],
                   next=("PIPELINE_FAIL: fix and rerun once (same setup name)" if cls == "pipeline" else
                         "PHYSICS_FAIL: report the numbers to the user; DFG-2 stops (next = the user's choice)"), follow_up=None)
        return out
    el = res["eligibility"]
    eligible = bool(all((el.get(k) or {}).get("ok") for k in ("E1", "E1t", "E2", "E3")))
    miss = res["median"].get("miss"); N1 = res["median"].get("N1")
    rows_ok = [r for r in res["groups"] if r.get("complete")]
    n_jet = sum(1 for r in rows_ok if (r.get("jet_ratio") or 0) >= DEC["jet_ratio"])
    n_no_ov = sum(1 for r in rows_ok if not (r.get("overturn") or {}).get("any"))
    breaking = (len(rows_ok) - n_no_ov) >= 2
    oc = []
    if eligible:
        if miss is not None and miss <= bar:
            oc.append("NEW_BEST_SHAPE")
        if miss is not None and miss <= DEC["target_band"]:
            oc.append("TARGET_BAND")
        if n_jet >= DEC["jet_groups"]:
            oc.append("JET_REGIME_SEEN")
    if n_no_ov >= DEC["B2_no_overturn_groups"]:
        fu = "B2"; why = "valid and no overturning at the focus in %d of 3 groups -> B2 STEEPER (a_sum 7.10 m, x1.12 the DM1A sum, labelled an enlargement)" % n_no_ov
    elif eligible and breaking and miss is not None and miss > bar and N1 is not None and N1 <= DEC["B1_N1_max"]:
        fu = "B1"; why = "valid, eligible, breaking, miss %.2f > bar %.2f and N1 %.2f <= 0.40 -> B1 NARROWER (lobes 65 deg / sigma 25)" % (miss, bar, N1)
    elif "NEW_BEST_SHAPE" in oc:
        fu = None; why = "NEW_BEST_SHAPE (miss %.2f <= bar %.2f): mp4 shown to the user with the gains; no follow-up needed" % (miss, bar)
    else:
        fu = None; why = "NO_GAIN: stop DFG-2 and report honestly (miss %s, bar %.2f, eligible %s, breaking groups %d, N1 %s)" % (
            ("%.2f" % miss) if miss is not None else None, bar, eligible, len(rows_ok) - n_no_ov, ("%.2f" % N1) if N1 is not None else None)
        oc.append("NO_GAIN")
    out.update(valid=True, eligible=eligible, outcomes=oc or ["NONE"], follow_up=fu, why=why, n_groups_jet=n_jet, n_groups_no_overturn=n_no_ov,
               breaking=breaking, next=("FOLLOW_UP %s (at most one, before reporting)" % fu) if fu else why)
    return out


def judge(rd, out_dir=None):
    t0 = time.time()
    res, cfg, H, R2, R4, PF, eta0, t_end = common(rd, "0p5", out_dir)
    rows = group_rows(res["run_dir"], H, R2, R4, PF, eta0, t_end, "0p5")
    res["groups"] = rows
    ok_rows = [r for r in rows if r.get("complete")]
    summ = {k: med(ok_rows, k) for k in REPORT_KEYS}
    for k in ("Nt", "c_in60", "gain_over_c_in60", "jet_ratio"):
        summ[k] = med(ok_rows, k)
    summ["W_curve"] = {fk: med([dict(v=(r.get("W_curve") or {}).get(fk)) for r in ok_rows], "v") for fk in ("%.2f" % f for f in EM.FRACS)}
    res["median"] = summ
    g = dict(run_complete=res["run_complete"], G1=res["G1"], G2f=res["G2f"], G3P=gate_G3P(rows), G4=res["G4"], G5=res["G5"], G6=gate_G6(rows),
             groups3=dict(ok=bool(len(ok_rows) == 3), n=len(ok_rows)))
    res["gates"] = g
    keys = ["run_complete", "G1", "G2f", "G3P", "G4", "G5", "G6", "groups3"]
    res["failed_gates"] = [k for k in keys if not (g.get(k) or {}).get("ok")]
    res["valid"] = not res["failed_gates"]
    Hc = summ.get("Hc"); cin = summ.get("c_in60")
    gain = (Hc / cin) if (Hc and cin) else None
    tab = cfg.get("dir") or {}
    res["eligibility"] = dict(
        E1=dict(N1_median=summ.get("N1"), max=ELIG["N1_max"], ok=bool(summ.get("N1") is not None and summ["N1"] <= ELIG["N1_max"])),
        E1t=dict(Nt_median=summ.get("Nt"), max=ELIG["Nt_max"], ok=bool(summ.get("Nt") is not None and summ["Nt"] <= ELIG["Nt_max"])),
        E2=dict(Hc_median=Hc, min=ELIG["Hc_min"], ok=bool(Hc is not None and Hc >= ELIG["Hc_min"])),
        E3=dict(gain=gain, Hc_median=Hc, c_in60_median=cin, min=ELIG["gain_min"], ok=bool(gain is not None and gain >= ELIG["gain_min"]),
                rule="median Hc / median largest crest on the line x 60 m (|y| <= 65 m) in [t_fn - 14, t_fn + 14)"))
    res["gains_report"] = dict(Hc_over_linear_design_crest=(Hc / DEC["linear_crest"]) if Hc else None,
                               Hc_over_max_component=(Hc / tab["a_max_component"]) if (Hc and tab.get("a_max_component")) else None,
                               Hc_over_amp_per_freq=(Hc / tab["amp_per_freq"][0]) if (Hc and tab.get("amp_per_freq")) else None,
                               Hc_over_c_in60=gain, a_max_component=tab.get("a_max_component"), amp_per_freq=tab.get("amp_per_freq"),
                               a_sum=tab.get("a_sum"), linear_design_crest=DEC["linear_crest"],
                               per_group=[dict(n=r["n"], Hc=r.get("Hc"), jet_ratio=r.get("jet_ratio"), gain_over_c_in60=r.get("gain_over_c_in60"))
                                          for r in ok_rows])
    res["core_miss_median"] = summ.get("miss")
    res["decision"] = decide(res)
    best = min(ok_rows, key=lambda r: r["miss"]) if ok_rows else None
    res["red_instant"] = dict(n=best["n"], frame=best["f"], t=best["t"], miss=best["miss"], Hc=best["Hc"], x=best["x_pk"], y=best["y_pk"]) if best else None
    res["elapsed_s"] = round(time.time() - t0, 1)
    od = GC.guard_out(out_dir or os.path.join(res["run_dir"], "g52"), allow_scratch=True)
    p = os.path.join(od, "judge_DFG.json")
    GC.jdump(res, p)
    res["_path"] = p.replace("\\", "/")
    return res


def summary_line(res):
    s = res.get("median") or {}
    d = res.get("decision") or {}
    return dict(run=res.get("run_id"), kind=res.get("kind"), valid=res.get("valid", res.get("smoke_pass")), failed=res.get("failed_gates", res.get("failed")),
                verdict=res.get("verdict"), miss=s.get("miss"), Hc=s.get("Hc"), W50=s.get("W50"), W80=s.get("W80"), W95=s.get("W95"), K=s.get("K"),
                S2=s.get("S2"), N1=s.get("N1"), Nt=s.get("Nt"), gain=(res.get("eligibility") or {}).get("E3", {}).get("gain"),
                outcomes=d.get("outcomes"), follow_up=d.get("follow_up"), next=d.get("next"), bar=d.get("bar"),
                G2f={k: round(v["R"], 3) for k, v in ((res.get("G2f") or {}).get("per_n") or {}).items()}, red_instant=res.get("red_instant"),
                path=res.get("_path"))


# ====================================================================== self test (frozen numbers vs the plan; synthetic data)
def selftest():
    pl = GC.plan()
    A = pl["gates"]["A_validity"]; B = pl["gates"]["B_eligibility"]
    ck = {}
    ck["G2f_ranges"] = bool(A["G2f"]["range_0p5"] == {"n%d" % k: list(v) for k, v in GATES["G2f_range_0p5"].items()}
                            and A["G2f"]["range_1p0"] == {"n%d" % k: list(v) for k, v in GATES["G2f_range_1p0"].items()}
                            and A["G2f"]["phase_max_rad_0p5"] == GATES["G2f_phase_0p5"] and A["G2f"]["phase_max_rad_1p0"] == GATES["G2f_phase_1p0"])
    ck["G4"] = bool(A["G4"]["kA_max"] == GATES["G4_kA"])
    ck["G5"] = bool(A["G5"]["max"] == GATES["G5_max"])
    ck["elig"] = bool(B["E1"]["max"] == ELIG["N1_max"] and B["E1t"]["max"] == ELIG["Nt_max"] and B["E2"]["min"] == ELIG["Hc_min"]
                      and B["E3"]["min"] == ELIG["gain_min"])
    ck["e51_frozen"] = bool(GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py") == E51_SHA == pl["metrics_ruler"]["e51_sha256"])
    ck["plan_sha"] = GC.plan_sha_ok()
    # harmonic fit recovers known amplitudes (with nuisance harmonics and noise)
    rng = np.random.default_rng(1)
    t = np.arange(32.0, 88.0 + 1e-9, 1.0 / 24.0)
    true = {3: 0.8 - 0.3j, 4: -0.5 + 0.9j, 5: 0.2 + 0.1j}
    e = 0.07 + sum((v * np.exp(-1j * 2 * math.pi * n / GC.P_S * (t - GC.T_F))).real for n, v in true.items())
    e += 0.15 * np.cos(2 * math.pi * 8 / GC.P_S * t + 0.3) + rng.normal(0, 0.02, len(t))
    fit = harmonic_fit(t, e)
    ck["harmonic_fit"] = bool(max(abs(fit["A"][n] - v) for n, v in true.items()) < 5e-3 and abs(fit["mean"] - 0.07) < 5e-3)
    # lip detector: a column with water, an air gap above 0.5 m and water above it
    zs = np.arange(-5.0, 10.0, 0.5)
    s = np.ones((len(zs), 6))
    s[zs <= 1.0, :] = -1.0
    s[(zs >= 3.0) & (zs <= 4.0), 2:4] = -1.0         # lip over columns 2-3, gap bottom at 1.5 m
    fl = lip_cols(s, zs, np.ones(6, bool))
    ck["lip_detector"] = bool(lip_hit(fl) == 2 and fl.tolist() == [False, False, True, True, False, False])
    s2 = s.copy(); s2[(zs >= 3.0) & (zs <= 4.0), 2:4] = 1.0; s2[(zs >= 3.0) & (zs <= 3.0), 3] = -1.0
    ck["lip_single_column_ignored"] = bool(lip_hit(lip_cols(s2, zs, np.ones(6, bool))) is None)
    return dict(ok=bool(all(ck.values())), checks=ck, fit=dict(A={str(k): [v.real, v.imag] for k, v in fit["A"].items()}, mean=fit["mean"]))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "smoke" and len(a) >= 2:
        r = smoke(a[1], out_dir=opt.get("out"))
        print(json.dumps(GC.clean(summary_line(r)), ensure_ascii=False))
    elif a[0] == "judge" and len(a) >= 2:
        r = judge(a[1], out_dir=opt.get("out"))
        print(json.dumps(GC.clean(summary_line(r)), ensure_ascii=False))
    elif a[0] == "selftest":
        print(json.dumps(GC.clean(selftest()), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
