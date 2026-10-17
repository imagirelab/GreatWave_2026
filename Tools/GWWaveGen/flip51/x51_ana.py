# -*- coding: utf-8 -*-
"""FLIP51 plan E: reading of the T 7 crossing screens (1.0 m) and of a promoted 0.5 m run under the FROZEN plan E rules (py -3.10 -B; numpy,
scipy). 2026-10-17 written new (Claude). Read only on every run folder; writes only under Unity/Build/FLIP51 (or, for a test on a FLIP50 run,
under the session scratchpad given with --out).

What it measures (definitions frozen in Unity/Build/FLIP51/plan/plan_E_frozen.json; the numbers below are the single source the plan copies):
  still level eta0     the run's online still offset (run record info.still_offset_online: median top-surface height over x 110-340 m,
                       t 0.5-1.5 s). At dp 1.0 the top surface reads still water +0.48 m high (SMOKE50DA, frames 2-49) [measured], so
                       eta0 = 0 would add 0.48 m to every height.
  per-period scan      periods n = 6-10, windows [7n - 3.5, 7n + 3.5) s; per window the 'max' frame = largest Hc of the 3x3-median hf - eta0
                       over x 150-300 m and the interior |y| <= 95 m (the side band y >= 95 m generates/absorbs and is never the judged wave);
                       e51_metrics.hf_metrics (frozen ruler, unchanged) on that frame with the rows y > 95 m set to NaN and xwin (150, 300).
                       Edge guard: if >= 2 window maxima lie within 0.25 s of a window edge, all windows shift by +3.5 s (reported).
  N1 isolation         highest local maximum (15 m x 15 m max filter: half width floor(7.5 m / grid) cells) of the mirrored 3x3-median
                       hf - eta0 inside x 110-340 m, |y| <= 90 m, r <= 100 m from the summit, outside r < 4 Hc of the summit and of its mirror
                       image (x_pk, -y_pk), divided by Hc (0 if none).
  gates G2-G6, eligibility E1-E3, the 0.5 m outcomes and the promotion rule: see GATES / ELIG / BARS / OUT05 and decide().
  report only: W(f), taper, S1, ring, Lx50, A50, section face/concavity/overhang/back (r2, y 0.5 m), tbest (optimistic), and the D smoke
                       analysis where it applies (g50_ana smoke_gauge_gates / smoke_focus_gates with the plan-D smoke gate numbers, read only).
usage:
  py -3.10 -B x51_ana.py screen <run_dir> [--case=U7|X2|X1] [--out=<dir>] [--T=7]   -> <run>/e51/screen_E.json (last stdout line: summary json)
  py -3.10 -B x51_ana.py judge05 <run_dir> [--case=..] [--out=<dir>]                -> <run>/e51/judge_E05.json
  py -3.10 -B x51_ana.py decide [--U7=<screen_E.json>] [--X2=..] [--X1=..] [--out=<file>]   the frozen promotion rule -> decision json
  py -3.10 -B x51_ana.py calib [--out=<file>]       pre-freeze calibration on measured runs (1.0/0.5 bias with the online eta0; N1)
Tags: [measured] [computed] [literature] [guess] [chosen].
"""
import os, sys, json, math, glob, time, warnings

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
from scipy import ndimage as ndi      # noqa: E402
import x51_common as XC               # noqa: E402
import e51_metrics as EM              # noqa: E402  frozen ruler (read only)

FPS = 24.0
SCAN = dict(T=7.0, periods=[6, 7, 8, 9, 10], half_s=3.5, xr=[150.0, 300.0], ymax=95.0, edge_s=0.25, edge_n=2, edge_shift_s=3.5,
            min_valid=4, t_pass=[30.0, 75.0])
N1DEF = dict(win_m=15.0, x=[110.0, 340.0], ymax=90.0, rmax=100.0, rex_Hc=4.0)
GATES = dict(G2_ratio_1p0=[0.78, 1.15], G2_ratio_0p5=[0.90, 1.12], G2_t=[30.0, 75.0], G2_gauge=[110.0, 0.5],
             G3_T=7.0, G3_tol=0.5, G3_min_consec_summits=4, G3_xspread_max=20.0,
             G4_kA_max=0.40, G4_inlet_x=100.0, G4_side_y=95.0, G4_side_x_max=180.25, G4_lip_z_min=0.5, G4_t=[30.0, 75.0],
             G5_volume_max=0.02, G6_x=[160.0, 300.0], G6_Hc_frac=0.68)
ELIG = dict(N1_max=0.65, Hc_vs_U7=0.85, U7_Hc_fallback_1p0=6.5 * 0.94, Hc_0p5_min=5.0, gain_min=1.8)
BARS = dict(abs_miss_1p0=2.75, rel_miss_vs_U7=-0.50, tie=0.30, jet_probe_rel=-0.80)
OUT05 = dict(new_best_miss=2.8, target_band_miss=0.5, jet_ratio=1.30, no_gain_ratio=1.10, no_gain_W50=3.3)
REPORT_KEYS = ["Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "ring_p90", "ring_mean", "Lx50", "Lx70",
               "A50", "FWHM_excess", "c_side_6Hc", "W50_tr", "H_front_row", "Hs", "face_deg", "concavity", "overhang", "back_deg", "miss", "N1",
               "c_in110", "Hc_raw"]


# ====================================================================== records
def recs(rd):
    return [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]


def still_offset(rd, rr=None):
    for r in (rr if rr is not None else recs(rd)):
        o = (r.get("info") or {}).get("still_offset_online")
        if o and o.get("value") is not None:
            return float(o["value"]), "online (run_c%05d info.still_offset_online)" % int(r.get("f_start") or 0)
    p = os.path.join(rd, "run.json")
    if os.path.exists(p):
        v = (json.load(open(p, encoding="utf8")).get("still_offset") or {}).get("value")
        if v is not None:
            return float(v), "run.json still_offset"
    return EM.still_offset(rd), "pana/events.json (or 0)"


def load_cfg(rd):
    p = os.path.join(rd, "cfg.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}


class HF:
    """hf frames; overlapping blocks of a restarted chain: the later launch wins (file names sort by launch, as e51_metrics)."""

    def __init__(self, rd):
        self.where = {}
        for p in sorted(glob.glob(os.path.join(rd, "hf_c*_b*.npz"))):
            with np.load(p) as d:
                fr = np.array(d["frames"], dtype=np.int64)
            for i, f in enumerate(fr):
                self.where[int(f)] = (p, i)
        self._c = {}

    def frames(self):
        return sorted(self.where)

    def get(self, f):
        p, i = self.where[int(f)]
        if p not in self._c:
            if len(self._c) >= 2:
                self._c.pop(next(iter(self._c)))
            with np.load(p) as d:
                self._c[p] = (np.array(d["eta"]), json.loads(str(d["meta"])))
        a, meta = self._c[p]
        return a[i].astype(np.float64), meta


def load_r6(rd):
    """copy of g49_periodic_ana.load_r6 (gauges and volume; the later launch wins)."""
    best = {}
    gxy = vnames = None
    for p in sorted(glob.glob(os.path.join(rd, "r6_c*.npz")), key=lambda q: int(os.path.basename(q)[4:9])):
        d = np.load(p)
        if "gauge" not in d.files:
            continue
        gxy = d["gauge_xy"]; vnames = [str(v) for v in d["vol_names"]]
        for i, f in enumerate(d["frames"]):
            best[int(f)] = (float(d["t"][i]), d["gauge"][i], d["vol"][i], int(d["npts"][i]))
    fr = np.array(sorted(best))
    return dict(frames=fr, t=np.array([best[f][0] for f in fr]), gauge=np.array([best[f][1] for f in fr]), vol=np.array([best[f][2] for f in fr]),
                npts=np.array([best[f][3] for f in fr]), gxy=gxy, vnames=vnames)


def waves_zero_down(t, e):
    """zero-down waves (copy of g49_periodic_ana.waves_zero_down, mean removed): crest per wave."""
    m = float(np.nanmean(e)); q = e - m
    ok = np.isfinite(q)
    dn = np.where(ok[:-1] & ok[1:] & (q[:-1] >= 0) & (q[1:] < 0))[0]
    out = []
    for a, b in zip(dn[:-1], dn[1:]):
        ee = e[a + 1:b + 1]; tt = t[a + 1:b + 1]
        if len(ee) < 5 or not np.isfinite(ee).all():
            continue
        ic = int(np.argmax(ee))
        out.append(dict(t_crest=float(tt[ic]), crest=float(ee[ic]), trough=float(np.min(ee)), H=float(ee[ic] - np.min(ee))))
    return out


# ====================================================================== geometry helpers
def axes(meta, shape):
    nz, nx = shape
    xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
    yh = float(meta["z0"]) + float(meta["dz"]) * np.arange(nz)
    return xs, yh


def k_of_x(xs, T):
    om = 2 * math.pi / T
    h = XC.bed_h(xs)
    k = np.where(h > 0.3, XC.kdisp(om, np.maximum(h, 0.3)), np.nan)
    return np.asarray(k, float)


def masked_interior(a, meta, ymax=None):
    ymax = SCAN["ymax"] if ymax is None else ymax
    _, yh = axes(meta, a.shape)
    b = a.copy()
    b[yh > ymax + 1e-9, :] = np.nan
    return b


def n1_isolation(e_half, meta, m):
    """N1 (frozen): e_half = 3x3-median hf - eta0 (half tank, rows y > 95 m may be NaN); m = hf_metrics of the frame."""
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


def frame_full(rd, H, f, eta0, xwin, ymask=True):
    """the frozen metrics at one frame: hf_metrics (interior rows only), miss, N1, r2 section metrics (report)."""
    a, meta = H.get(f)
    b = masked_interior(a, meta) if ymask else a
    m = EM.hf_metrics(b, meta, eta0, xwin=xwin)
    if not m or "W50" not in m:
        return m
    m["frame"] = int(f); m["t"] = (int(f) - 1) / FPS
    miss, per = EM.score_vs_target(m)
    m["miss"] = miss; m["miss_per"] = per
    e_half = EM.median3(b) - eta0
    iso = n1_isolation(e_half, meta, m)
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


# ====================================================================== pass over the records (t 30-75 s)
def pass_frames(rd, H, eta0, T, t_lo, t_hi):
    """per frame: Hc_scan (interior, x 150-300), c110 (max over |y| <= 95 of the crest line x 110 m), band steepness (G4)."""
    fr = [f for f in H.frames() if t_lo - 1e-9 <= (f - 1) / FPS <= t_hi + 1e-9]
    out = dict(f=[], t=[], Hc=[], x=[], y=[], c110=[], kA_in=[], kA_sd=[])
    key = None
    for f in fr:
        a, meta = H.get(f)
        e = EM.median3(a) - eta0
        xs, yh = axes(meta, e.shape)
        if key != (e.shape, float(meta["x0"]), float(meta["z0"])):      # the grid can change between launches (run record res_changes)
            key = (e.shape, float(meta["x0"]), float(meta["z0"]))
            kx = k_of_x(xs, T)
            inter = yh <= SCAN["ymax"] + 1e-9
            sreg = inter[:, None] & ((xs >= SCAN["xr"][0]) & (xs <= SCAN["xr"][1]))[None, :]
            inl = np.zeros(e.shape, bool); inl[:, xs < GATES["G4_inlet_x"]] = True
            sd = np.zeros(e.shape, bool); sd[np.ix_(yh >= GATES["G4_side_y"], xs <= GATES["G4_side_x_max"])] = True
            i0 = int(np.searchsorted(xs, 110.0)) - 1; w110 = (110.0 - xs[i0]) / (xs[i0 + 1] - xs[i0])
        v = np.where(sreg, e, np.nan)
        if np.isfinite(v).any():
            j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            out["Hc"].append(float(v[iy, ix])); out["x"].append(float(xs[ix])); out["y"].append(float(yh[iy]))
        else:
            out["Hc"].append(np.nan); out["x"].append(np.nan); out["y"].append(np.nan)
        line = (1 - w110) * e[:, i0] + w110 * e[:, i0 + 1]
        out["c110"].append(float(np.nanmax(np.where(inter, line, np.nan))))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ke = kx[None, :] * e
            out["kA_in"].append(float(np.nanmax(np.where(inl, ke, np.nan))))
            out["kA_sd"].append(float(np.nanmax(np.where(sd, ke, np.nan))))
        out["f"].append(int(f)); out["t"].append((f - 1) / FPS)
    return {k: np.asarray(v) for k, v in out.items()}


def r2_lip(rd, eta0, f_lo, f_hi, x_max):
    """G4 overturning lip on the centre section (r2, y 0.5 m) at x < x_max: a column whose water has an air gap below a higher water run,
    the gap bottom above eta0 + 0.5 m, in >= 2 adjacent columns. -> list of (frame, x)."""
    hits = []
    for f in range(f_lo, f_hi + 1):
        s, meta = EM.load_frame(rd, "r2", f, "sdf")
        if s is None:
            continue
        nz, nx = s.shape
        xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
        zs = float(meta["y0"]) + float(meta["dy"]) * np.arange(nz) - eta0
        cols = np.where((xs < x_max) & (xs > 3.0))[0]
        flag = []
        for c in cols:
            a = s[:, c] < 0
            starts = np.where(a & ~np.concatenate([[False], a[:-1]]))[0]
            if len(starts) < 2:
                flag.append(False); continue
            top = starts[-1]
            gap = top - 1
            flag.append(bool(gap >= 0 and not a[gap] and zs[gap] > GATES["G4_lip_z_min"]))
        flag = np.array(flag, bool)
        if len(flag) >= 2 and np.any(flag[1:] & flag[:-1]):
            k = int(np.where(flag[1:] & flag[:-1])[0][0])
            hits.append((int(f), float(xs[cols[k]])))
    return hits


# ====================================================================== the per-period scan
def period_windows(T, shift=0.0):
    """[nT - T/2, nT + T/2) (= [7n - 3.5, 7n + 3.5) at T 7, the frozen windows; T/2 so a test on a T 12 run uses whole periods)."""
    h = 0.5 * T
    return [(n, n * T - h + shift, n * T + h + shift) for n in SCAN["periods"]]


def scan_periods(P, T, t_end, shift=0.0):
    rows = []
    for n, a, b in period_windows(T, shift):
        if b > t_end + 1e-9:
            rows.append(dict(n=n, window=[a, b], complete=False)); continue
        m = (P["t"] >= a - 1e-9) & (P["t"] < b - 1e-9) & np.isfinite(P["Hc"])
        if not m.any():
            rows.append(dict(n=n, window=[a, b], complete=False)); continue
        idx = np.where(m)[0]
        i = int(idx[np.argmax(P["Hc"][idx])])
        rows.append(dict(n=n, window=[a, b], complete=True, f=int(P["f"][i]), t=float(P["t"][i]), Hc_scan=float(P["Hc"][i]),
                         x_scan=float(P["x"][i]), y_scan=float(P["y"][i]), c_in110=float(np.nanmax(P["c110"][idx])),
                         edge=bool(min(P["t"][i] - a, b - P["t"][i]) <= SCAN["edge_s"] + 1e-9)))
    return rows


def g3_recurrence(rows, T):
    ts = [r["t"] for r in rows if r.get("complete")]
    sp = [b - a for a, b in zip(ts[:-1], ts[1:])]
    best = run = 0
    for v in sp:
        run = run + 1 if abs(v - T) <= GATES["G3_tol"] * T / 7.0 + 1e-9 else 0      # 7.0 +- 0.5 s at T 7 (+-7 %)
        best = max(best, run)
    xs = [r["x_pk"] for r in rows if r.get("complete") and r.get("x_pk") is not None]
    spread = (max(xs) - min(xs)) if xs else None
    ok = bool(best + 1 >= GATES["G3_min_consec_summits"] and spread is not None and spread <= GATES["G3_xspread_max"] + 1e-9)
    return dict(summit_t=ts, spacings_s=sp, longest_consecutive_summits=best + 1 if ts else 0, x_spread_m=spread, ok=ok,
                rule="period summits spaced 7.0 +- 0.5 s for >= 4 consecutive summits (>= 3 consecutive spacings) and summit x spread "
                     "(max - min over the complete periods) <= 20 m")


def med(rows, key):
    v = [r[key] for r in rows if r.get(key) is not None and isinstance(r.get(key), (int, float)) and np.isfinite(r[key])]
    return float(np.median(v)) if v else None


# ====================================================================== D smoke analysis (report only, where it applies)
def d_report(rd, cfg, case, P_hf, eta0, T, R):
    """P_hf = (xs, ys, tt, eta) with eta already minus eta0 (mirrored); eta0 is used for the gauges."""
    out = {}
    try:
        sys.path.insert(0, XC.TOOLS50)
        import g50_ana as AN                      # in-memory adaptations of flip49 tools only (no file edited)
        sg = json.load(open(XC.PLAN_D_FROZEN, encoding="utf8"))["smoke_gates"]
        gl = (cfg.get("dir") or {}).get("gauges_lin") or {}
        out["generation_gauges"] = AN.smoke_gauge_gates(R["gxy"], R["gauge"], R["t"], eta0, gl, T, sg)
        xs, ys, tt, eta = P_hf
        import x51_table as XT
        xg = np.union1d(np.arange(140.0, 300.0 + 1e-9, 1.0), [XC.X_F])
        df = XT.dirfield(case, x=np.union1d(np.arange(0.0, 300.0 + 1e-9, 1.0), [XC.X_F]))
        Aall = np.abs(df.complex_amp(np.abs(np.asarray(ys, float))))
        keep = np.isin(df.x, xg)
        A = Aall[keep]
        side = (np.abs(ys) >= sg["contrast_side_y"][0]) & (np.abs(ys) <= sg["contrast_side_y"][1])
        j0 = int(np.argmin(np.abs(ys)))
        C_lin = dict(x=df.x[keep], C=A[:, j0] / np.maximum(A[:, side].mean(axis=1), 1e-9))
        A_lin = dict(x=df.x[keep], A=A[:, j0])
        fo = AN.smoke_focus_gates(xs, ys, tt, eta, XC.X_F, T, A_lin, C_lin, sg)
        fo.pop("contrast_profile", None)
        out["focus_D_smoke_gates"] = fo
        out["thresholds_from"] = "plan_D_frozen.json smoke_gates (read only; report only for plan E)"
    except Exception as ex:
        out["error"] = repr(ex)[:400]
    return out


# ====================================================================== screen
def guess_case(rd, cfg):
    c = ((cfg.get("case") or {}).get("e_case")) or ""
    if c in XC.CASES:
        return c
    for k in XC.CASES:
        if os.path.basename(rd).startswith("S51%s_" % k):
            return k
    return None


def screen(rd, case=None, out_dir=None, T=None, kind=None):
    t_start = time.time()
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = load_cfg(rd)
    case = case or guess_case(rd, cfg)
    T = float(T or (cfg.get("dir") or {}).get("T") or XC.T7)
    dp = float((cfg.get("parms") or {}).get("dp", 1.0))
    kind = kind or ("0p5" if dp == 0.5 else "1p0")
    rr = recs(rd)
    eta0, eta0_src = still_offset(rd, rr)
    H = HF(rd)
    frames = H.frames()
    t_end = (max(frames) - 1) / FPS if frames else 0.0
    res = dict(run_id=os.path.basename(rd), run_dir=rd, case=case, dp=dp, T=T, plan=XC.PLAN_E_REL, tool="Tools/GWWaveGen/flip51/x51_ana.py",
               tool_sha256=XC.sha256_file(os.path.abspath(__file__)), e51_sha256=XC.sha256_file(XC.TOOLS51 + "/e51_metrics.py"),
               date=time.strftime("%Y-%m-%d %H:%M:%S"), eta0=eta0, eta0_source=eta0_src, t_record_end=t_end, frames_n=len(frames))
    done = max([int(r.get("f_end_done") or 0) for r in rr] or [0])
    res["run_complete"] = bool(cfg and done >= int(cfg.get("f_end", 10 ** 9)))
    res["launches"] = [dict(f_start=r.get("f_start"), f_end_done=r.get("f_end_done"), stopped=r.get("stopped"), wall_s=r.get("wall_total_s"),
                            particles_max=r.get("particles_max"), rss_gb=r.get("rss_peak_gb"), substeps=r.get("substeps_min_max")) for r in rr]
    # ---- pass over t 30-75
    t_lo, t_hi = SCAN["t_pass"][0], min(SCAN["t_pass"][1], t_end)
    P = pass_frames(rd, H, eta0, T, t_lo, t_hi)
    rows = scan_periods(P, T, t_end)
    n_edge = sum(1 for r in rows if r.get("edge"))
    shift = 0.0
    if n_edge >= SCAN["edge_n"]:
        shift = SCAN["edge_shift_s"] * T / 7.0          # = 3.5 s at T 7 (half a period)
        rows = scan_periods(P, T, t_end, shift)
    res["scan"] = dict(rule=SCAN, edge_maxima_first_pass=n_edge, shift_s=shift)
    xr = tuple(SCAN["xr"])
    for r in rows:
        if not r.get("complete"):
            continue
        m = frame_full(rd, H, r["f"], eta0, xr)
        if not m or "W50" not in m:
            r["metrics_error"] = "no crest metrics"; r["complete"] = False; continue
        r.update({k: m.get(k) for k in REPORT_KEYS if k in m and k != "c_in110"})
        r["W_curve"] = m.get("W_curve"); r["W_censored"] = m.get("W_censored"); r["miss_per"] = m.get("miss_per"); r["N1_detail"] = m.get("N1_detail")
        # tbest (report only, optimistic): smallest miss among every 2nd frame of the window with Hc_scan >= 0.8 x the window maximum
        a, b = r["window"]
        cand = [(f, h) for f, t, h in zip(P["f"], P["t"], P["Hc"]) if a - 1e-9 <= t < b - 1e-9 and np.isfinite(h) and h >= 0.8 * r["Hc_scan"]]
        tb = None
        for f, _ in cand[::2]:
            a_, meta_ = H.get(f)
            mm = EM.hf_metrics(masked_interior(a_, meta_), meta_, eta0, xwin=xr)
            if mm and "W50" in mm:
                s_, _ = EM.score_vs_target(mm)
                if tb is None or s_ < tb[0]:
                    tb = (s_, f, mm.get("Hc"), mm.get("W50"))
        r["tbest_report_only"] = dict(miss=tb[0], frame=tb[1], Hc=tb[2], W50=tb[3]) if tb else None
    valid = [r for r in rows if r.get("complete")]
    res["periods"] = rows
    res["n_valid_periods"] = len(valid)
    summ = {k: med(valid, k) for k in REPORT_KEYS}
    summ["c_in110"] = med(valid, "c_in110")
    summ["W_curve"] = {fk: med([dict(v=(r.get("W_curve") or {}).get(fk)) for r in valid], "v") for fk in ("%.2f" % f for f in EM.FRACS)}
    summ["censored_any"] = {k: any(bool(r.get("W_censored", {}).get(f_)) for r in valid) for k, f_ in (("W20", "0.20"), ("W50", "0.50"), ("W80", "0.80"))}
    summ["tbest_miss_report_only"] = med([dict(v=(r.get("tbest_report_only") or {}).get("miss")) for r in valid], "v")
    res["median"] = summ
    # ---- gates
    g = {}
    tab = cfg.get("dir") or {}
    lr = tab.get("linear_refs") or {}
    g["G1_table"] = dict(ok=None, note="checked before launch (x51_table check; cfg precheck table sha) -> see plan / table_check_<case>.json")
    tc = XC.PLAN_DIR + "/table_check_%s.json" % case if case else None
    if tc and os.path.exists(tc):
        g["G1_table"]["ok"] = bool(json.load(open(tc, encoding="utf8")).get("all_ok")) and bool(
            tab.get("npz") and os.path.exists(tab["npz"]) and XC.sha256_file(tab["npz"]) == tab.get("npz_sha256"))
    # G2
    R = load_r6(rd)
    j = [i for i, (x_, y_) in enumerate(R["gxy"]) if abs(x_ - GATES["G2_gauge"][0]) < 1e-6 and abs(y_ - GATES["G2_gauge"][1]) < 1e-6]
    g2 = dict(ok=False)
    if j:
        tt = R["t"]; e = R["gauge"][:, j[0]] - eta0
        sel = (tt >= GATES["G2_t"][0] - 1e-9) & (tt <= GATES["G2_t"][1] + 1e-9) & np.isfinite(e)
        wv = [w_ for w_ in waves_zero_down(tt[sel], e[sel])]
        cr = [w_["crest"] for w_ in wv]
        A_lin = lr.get("A_lin_x110_y0p5")
        rng = GATES["G2_ratio_0p5"] if kind == "0p5" else GATES["G2_ratio_1p0"]
        if cr and A_lin:
            c_med = float(np.median(cr))
            g2 = dict(crest_median_m=c_med, n_waves=len(cr), A_lin=A_lin, ratio=c_med / A_lin, range=rng,
                      ok=bool(rng[0] <= c_med / A_lin <= rng[1]),
                      first_harmonic_ratio_report=float(2.0 * abs(np.mean((e[sel] - np.mean(e[sel])) * np.exp(1j * 2 * math.pi / T * tt[sel]))) / A_lin))
    g["G2_inlet_amplitude"] = g2
    # G3
    g["G3_recurrence"] = g3_recurrence(valid, T)
    # G4
    in_max = float(np.nanmax(P["kA_in"])) if len(P["kA_in"]) else None
    sd_max = float(np.nanmax(P["kA_sd"])) if len(P["kA_sd"]) else None
    f_lo = int(round(GATES["G4_t"][0] * FPS)) + 1; f_hi = min(int(round(GATES["G4_t"][1] * FPS)) + 1, max(frames) if frames else 0)
    lips = r2_lip(rd, eta0, f_lo, f_hi, GATES["G4_inlet_x"])
    g["G4_no_band_breaking"] = dict(kA_inlet_max=in_max, kA_side_max=sd_max, kA_max=GATES["G4_kA_max"], r2_lip_frames_x_lt_100=lips[:20],
                                    n_lip_frames=len(lips),
                                    ok=bool(in_max is not None and sd_max is not None and in_max <= GATES["G4_kA_max"] and sd_max <= GATES["G4_kA_max"]
                                            and not lips),
                                    rule="k(h(x)) x (3x3-median hf - eta0) max over t 30-75 s in the inlet band (x < 100 m, all y) and the generating "
                                         "side band (y >= 95 m, x <= 180.25 m) <= 0.40; no overturning lip on r2 (y 0.5 m) at x < 100 m. The side band "
                                         "has no section record, so only the steepness reads it")
    # G5
    vi = {nm: i for i, nm in enumerate(R["vnames"] or [])}
    g5 = dict(ok=False)
    if "V_m3" in vi:
        V = R["vol"][:, vi["V_m3"]]; tt = R["t"]
        ref = (tt >= 1.0 - 1e-9) & (tt <= 1.5 + 1e-9); later = tt > 1.5
        if ref.any() and later.any():
            V0 = float(np.nanmean(V[ref]))
            vmax = float(np.nanmax(np.abs(V[later] / V0 - 1.0)))
            g5 = dict(corrected_max_rel=vmax, max=GATES["G5_volume_max"], ok=bool(vmax <= GATES["G5_volume_max"]),
                      end_rel=float(V[-1] / V0 - 1.0), rule="the D hard health item for drift stage A (AM-D18): max |V/V0 - 1| of the measured "
                                                             "whole-tank column volume after 1.5 s (as g49_periodic_ana.health)")
            if "Vwin_m3" in vi:
                Vw = R["vol"][:, vi["Vwin_m3"]]; Vw0 = float(np.nanmean(Vw[ref]))
                g5["window_max_rel_report"] = float(np.nanmax(np.abs(Vw[later] / Vw0 - 1.0)))
    leaks = [l_ for r in rr for l_ in ((r.get("info") or {}).get("leak") or [])]
    pmax = max([r.get("particles_max") or 0 for r in rr] or [1])
    g5["bed_leak_frac_report"] = (max([l_.get("n_below_bed") or 0 for l_ in leaks] or [0]) / max(pmax, 1))
    g["G5_volume"] = g5
    # G6
    pred = XC.CASES.get(case, {}).get("Hc_pred_central") if case else None
    fl = GATES["G6_Hc_frac"] * pred if pred else None
    bad6 = [dict(n=r["n"], x_pk=r.get("x_pk"), Hc=r.get("Hc")) for r in valid
            if not (GATES["G6_x"][0] <= (r.get("x_pk") or -1) <= GATES["G6_x"][1]) or (fl is not None and (r.get("Hc") or 0) < fl)]
    g["G6_focus_where_designed"] = dict(Hc_floor=fl, x_range=GATES["G6_x"], failing=bad6, ok=bool(valid and not bad6 and fl is not None))
    g["periods_valid"] = dict(n=len(valid), min=SCAN["min_valid"], ok=bool(len(valid) >= SCAN["min_valid"]))
    g["run_complete"] = dict(ok=res["run_complete"], frames_done=done, f_end=cfg.get("f_end"))
    res["gates"] = g
    keys = ["run_complete", "G1_table", "G2_inlet_amplitude", "G3_recurrence", "G4_no_band_breaking", "G5_volume", "G6_focus_where_designed", "periods_valid"]
    failed = [k for k in keys if not (g.get(k) or {}).get("ok")]
    res["valid"] = not failed
    res["failed_gates"] = failed
    pipe = {"run_complete", "G1_table", "G2_inlet_amplitude", "periods_valid"}
    res["failure_class"] = (None if not failed else ("pipeline" if any(k in pipe for k in failed) else "physics"))
    # ---- eligibility (E2 needs U7: in decide)
    Hc = summ.get("Hc"); cin = summ.get("c_in110")
    res["eligibility"] = dict(
        E1_isolation=dict(N1_median=summ.get("N1"), max=ELIG["N1_max"], ok=bool(summ.get("N1") is not None and summ["N1"] <= ELIG["N1_max"])),
        E2_height=dict(Hc_median=Hc, rule="X: Hc >= 0.85 x Hc(U7) at 1.0 m (decide); 0.5 m: Hc >= 5.0 m"),
        E3_focusing_gain=dict(Hc_over_incoming=(Hc / cin) if (Hc and cin) else None, c_in110_median=cin, min=ELIG["gain_min"],
                              ok=bool(Hc and cin and Hc / cin >= ELIG["gain_min"]),
                              rule="median Hc / median over the periods of the largest incoming crest on the line x 110 m (|y| <= 95 m) in the window "
                                   "(the strictest incoming crest: the cross-screen definition c_in_x110)"),
        gains_report=dict(Hc_over_a_j_max=(Hc / tab["a_j_max"]) if (Hc and tab.get("a_j_max")) else None,
                          Hc_over_linear_design_crest=(Hc / lr["design_crest_xf"]) if (Hc and lr.get("design_crest_xf")) else None,
                          Hc_over_axis_gauge_crest=(Hc / g2["crest_median_m"]) if (Hc and g2.get("crest_median_m")) else None,
                          a_j_max=tab.get("a_j_max"), design_crest_xf=lr.get("design_crest_xf")))
    res["core_miss_median"] = summ.get("miss")
    # ---- D smoke analysis (report only)
    try:
        fr2 = [f for f in frames if 18.0 - 1e-9 <= (f - 1) / FPS <= t_end + 1e-9][:: (2 if dp == 0.5 else 1)]
        stack = []; xs_ = ys_ = None
        for f in fr2:
            a, meta = H.get(f)
            e, y_ = EM.mirror_y(a - eta0, meta)
            if xs_ is None:
                xs_ = EM.xs_of(meta, e.shape[1]); ys_ = y_
            stack.append(e.astype(np.float32))
        res["D_smoke_report"] = d_report(rd, cfg, case, (xs_, ys_, np.array([(f - 1) / FPS for f in fr2]), np.array(stack)), eta0, T, R) \
            if (case and stack) else dict(error="no case or frames")
    except Exception as ex:
        res["D_smoke_report"] = dict(error=repr(ex)[:300])
    res["per_frame"] = dict(t=P["t"][::2], Hc_scan=P["Hc"][::2], x_scan=P["x"][::2], c110=P["c110"][::2])
    # ---- the most converged instant (video red frame): the valid period instant with the smallest core miss
    best = min(valid, key=lambda r: r["miss"]) if valid else None
    res["red_instant"] = dict(n=best["n"], frame=best["f"], t=best["t"], miss=best["miss"], Hc=best["Hc"]) if best else None
    res["elapsed_s"] = round(time.time() - t_start, 1)
    od = XC.guard_out(out_dir or os.path.join(rd, "e51"), allow_scratch=True)
    p = os.path.join(od, "screen_E%s.json" % ("05" if kind == "0p5" else ""))
    XC.jdump(res, p)
    res["_path"] = p.replace("\\", "/")
    return res


def summary_line(res):
    s = res.get("median") or {}
    return dict(run=res.get("run_id"), case=res.get("case"), valid=res.get("valid"), failed=res.get("failed_gates"), cls=res.get("failure_class"),
                miss=s.get("miss"), Hc=s.get("Hc"), W50=s.get("W50"), W80=s.get("W80"), W95=s.get("W95"), K=s.get("K"), S2=s.get("S2"), N1=s.get("N1"),
                gain=(res.get("eligibility") or {}).get("E3_focusing_gain", {}).get("Hc_over_incoming"), periods=res.get("n_valid_periods"),
                path=res.get("_path"))


# ====================================================================== the frozen promotion rule
def decide(scr):
    """scr: {case: screen_E.json dict or None}. The plan E promote_rule (frozen). Returns the decision dict."""
    out = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), rule="plan_E_frozen.json promote_rule (Steps 1-5)", bars=BARS, elig=ELIG, per_case={})
    U = scr.get("U7")
    U_valid = bool(U and U.get("valid"))
    U_miss = (U or {}).get("core_miss_median") if U_valid else None
    U_Hc = ((U or {}).get("median") or {}).get("Hc") if U_valid else None
    Hc_ref = U_Hc if U_Hc else ELIG["U7_Hc_fallback_1p0"]
    out["U7"] = dict(valid=U_valid, miss=U_miss, Hc=U_Hc, Hc_ref_for_E2=Hc_ref, Hc_ref_source="U7 1.0 m median" if U_Hc else
                     "U7 not valid: central prediction 6.5 m x 0.94 (measured 1.0/0.5 Hc ratio, online eta0) [chosen in the plan]")
    prom = []
    for c in XC.ORDER:
        s = scr.get(c)
        row = dict(ran=bool(s))
        if not s:
            out["per_case"][c] = row; continue
        miss = s.get("core_miss_median"); el = s.get("eligibility") or {}
        Hc = (s.get("median") or {}).get("Hc")
        row.update(valid=bool(s.get("valid")), failed=s.get("failed_gates"), failure_class=s.get("failure_class"), miss=miss, Hc=Hc,
                   N1=(el.get("E1_isolation") or {}).get("N1_median"), gain=(el.get("E3_focusing_gain") or {}).get("Hc_over_incoming"))
        e1 = bool((el.get("E1_isolation") or {}).get("ok"))
        e3 = bool((el.get("E3_focusing_gain") or {}).get("ok"))
        e2 = True if c == "U7" else bool(Hc is not None and Hc >= ELIG["Hc_vs_U7"] * Hc_ref)
        row.update(E1=e1, E2=e2, E3=e3, eligible=bool(row["valid"] and e1 and e2 and e3))
        absb = bool(miss is not None and miss <= BARS["abs_miss_1p0"])
        rel = (miss - U_miss) if (c != "U7" and miss is not None and U_miss is not None) else None
        relb = bool(rel is not None and rel <= BARS["rel_miss_vs_U7"])
        row.update(abs_bar=absb, rel_vs_U7=rel, rel_bar=relb)
        row["promotable"] = bool(row["eligible"] and (absb or (c != "U7" and relb)))
        if row["promotable"]:
            prom.append(c)
        out["per_case"][c] = row
    out["promotable"] = prom
    choice = None; why = None; label = None
    if prom:
        mmin = min(out["per_case"][c]["miss"] for c in prom)
        near = [c for c in prom if out["per_case"][c]["miss"] <= mmin + BARS["tie"] + 1e-12]
        choice = next(c for c in XC.TIE_ORDER if c in near)
        why = "lowest median core miss %.2f among promotable %s; within the tie band %.2f: %s -> order X2, X1, U7 picks %s" % (
            mmin, prom, BARS["tie"], near, choice)
        label = "deliverable candidate (0.5 m)"
    else:
        x1 = out["per_case"].get("X1") or {}
        if (x1.get("valid") and x1.get("rel_vs_U7") is not None and x1["rel_vs_U7"] <= BARS["jet_probe_rel"] and x1.get("E2") and x1.get("E3")
                and not x1.get("E1")):
            choice = "X1"; label = "mechanism probe, not a deliverable"
            why = "jet-probe exception: X1 valid, miss(X1) - miss(U7) = %.2f <= %.2f, fails only the isolation guard (N1 %.2f > %.2f)" % (
                x1["rel_vs_U7"], BARS["jet_probe_rel"], x1.get("N1") or float("nan"), ELIG["N1_max"])
        else:
            why = "nothing promotable: no 0.5 m run tonight; report that the direction set does not narrow the crest in FLIP at T 7 (numbers " \
                  "per case), DFG-2 multi-frequency engineering next day"
    out["choice"] = choice
    out["label"] = label
    out["why"] = why
    runner = None
    if choice and label and label.startswith("deliverable"):
        rest = [c for c in XC.TIE_ORDER if c in prom and c != choice]
        rest.sort(key=lambda c: out["per_case"][c]["miss"])
        runner = rest[0] if rest else None
    out["runner_up_promotable"] = runner
    return out


# ====================================================================== the promoted 0.5 m run
def g50_events(rd, cfg):
    """g50/g49 breaker events (centre r2 overturning onsets; the D detector), read in memory; None if the tools fail."""
    try:
        sys.path.insert(0, XC.TOOLS50)
        import g50_ana as AN
        evr, _ = AN.PA.find_breakers(rd, cfg)
        return [dict(on_f=int(e["on_f"]), on_t=float(e["on_t"]), on_x=float(e["on_x"]), on_eta=float(e["on_eta"])) for e in evr["events"]]
    except Exception as ex:
        return dict(error=repr(ex)[:300])


def judge05(rd, case=None, out_dir=None):
    res = screen(rd, case=case, out_dir=out_dir, kind="0p5")
    rd = res["run_dir"]; cfg = load_cfg(rd)
    eta0 = res["eta0"]
    ev = g50_events(rd, cfg)
    res["g50_events"] = ev
    H = HF(rd)
    avail = set(H.frames())
    rows = res["periods"]
    used = []
    if isinstance(ev, list) and ev:
        for r in rows:
            if not r.get("complete"):
                continue
            a, b = r["window"]
            e_in = [e for e in ev if a - 1e-9 <= e["on_t"] < b - 1e-9]
            if not e_in:
                used.append(dict(n=r["n"], instant="scan")); continue
            e = e_in[0]
            xwin = (e["on_x"] + EM.FROZEN["peak_xwin_rel_onset_m"][0], e["on_x"] + EM.FROZEN["peak_xwin_rel_onset_m"][1])
            best = (-1e9, None)
            for f in range(e["on_f"] - int(round(3.0 * FPS)), e["on_f"] + int(round(1.5 * FPS)) + 1):
                if f not in avail:
                    continue
                a_, meta_ = H.get(f)
                ee = EM.median3(masked_interior(a_, meta_)) - eta0
                xs = EM.xs_of(meta_, ee.shape[1])
                sel = (xs >= xwin[0]) & (xs <= xwin[1])
                h = float(np.nanmax(ee[:, sel]))
                if h > best[0]:
                    best = (h, f)
            if best[1] is None:
                used.append(dict(n=r["n"], instant="scan (no frames)")); continue
            m = frame_full(rd, H, best[1], eta0, xwin)
            if m and "W50" in m:
                for k in REPORT_KEYS:
                    if k in m and k != "c_in110":
                        r[k] = m[k]
                r["f"] = int(best[1]); r["t"] = (best[1] - 1) / FPS; r["instant"] = "g50 event k on_t %.2f -> e51 max" % e["on_t"]
                used.append(dict(n=r["n"], instant="g50 event", on_t=e["on_t"], frame=best[1]))
    else:
        used = [dict(n=r["n"], instant="scan") for r in rows if r.get("complete")]
    valid = [r for r in rows if r.get("complete")]
    for k in REPORT_KEYS:
        if k != "c_in110":
            res["median"][k] = med(valid, k)
    res["core_miss_median"] = res["median"].get("miss")
    res["instants_used"] = used
    g = res["gates"]
    g["G3_recurrence"] = g3_recurrence(valid, res["T"])
    pred = XC.CASES.get(res.get("case"), {}).get("Hc_pred_central")
    fl = GATES["G6_Hc_frac"] * pred if pred else None
    bad6 = [dict(n=r["n"], x_pk=r.get("x_pk"), Hc=r.get("Hc")) for r in valid
            if not (GATES["G6_x"][0] <= (r.get("x_pk") or -1) <= GATES["G6_x"][1]) or (fl is not None and (r.get("Hc") or 0) < fl)]
    g["G6_focus_where_designed"] = dict(Hc_floor=fl, x_range=GATES["G6_x"], failing=bad6, ok=bool(valid and not bad6 and fl is not None),
                                        note="recomputed on the instants used (g50 events where present)")
    best = min(valid, key=lambda r: r["miss"]) if valid else None
    res["red_instant"] = dict(n=best["n"], frame=best["f"], t=best["t"], miss=best["miss"], Hc=best["Hc"]) if best else None
    tab = cfg.get("dir") or {}
    lr = tab.get("linear_refs") or {}
    Hc = res["median"].get("Hc"); cin = res["median"].get("c_in110")
    ratio = (Hc / lr["design_crest_xf"]) if (Hc and lr.get("design_crest_xf")) else None
    W50 = res["median"].get("W50"); miss = res["core_miss_median"]; N1 = res["median"].get("N1")
    gain = (Hc / cin) if (Hc and cin) else None
    el = res["eligibility"]                     # recomputed on the instants used
    el["E1_isolation"].update(N1_median=N1, ok=bool(N1 is not None and N1 <= ELIG["N1_max"]))
    el["E2_height"].update(Hc_median=Hc, ok=bool(Hc is not None and Hc >= ELIG["Hc_0p5_min"]))
    el["E3_focusing_gain"].update(Hc_over_incoming=gain, ok=bool(gain is not None and gain >= ELIG["gain_min"]))
    gr = el.get("gains_report") or {}
    if Hc and gr.get("a_j_max"):
        gr["Hc_over_a_j_max"] = Hc / gr["a_j_max"]
    if Hc and gr.get("design_crest_xf"):
        gr["Hc_over_linear_design_crest"] = Hc / gr["design_crest_xf"]
    keys = ["run_complete", "G2_inlet_amplitude", "G3_recurrence", "G4_no_band_breaking", "G5_volume", "G6_focus_where_designed", "periods_valid"]
    failed = [k for k in keys if not (g.get(k) or {}).get("ok")]
    res["valid"] = not failed; res["failed_gates"] = failed
    e2 = bool(Hc is not None and Hc >= ELIG["Hc_0p5_min"])
    oc = []
    if res["valid"] and e2:
        if miss is not None and miss <= OUT05["new_best_miss"] and N1 is not None and N1 <= ELIG["N1_max"] and gain is not None and gain >= ELIG["gain_min"]:
            oc.append("NEW BEST SHAPE")
        if miss is not None and miss <= OUT05["target_band_miss"]:
            oc.append("TARGET BAND")
        if ratio is not None and ratio >= OUT05["jet_ratio"]:
            oc.append("JET REGIME SEEN")
        if (miss is not None and miss > OUT05["new_best_miss"]) or (ratio is not None and ratio < OUT05["no_gain_ratio"] and W50 is not None
                                                                     and W50 >= OUT05["no_gain_W50"]):
            oc.append("NO GAIN")
    res["judgement_05"] = dict(outcomes=oc or (["INVALID"] if not (res["valid"] and e2) else ["NONE OF THE FROZEN OUTCOMES"]),
                               valid=res["valid"], E2_Hc_ge_5m=e2, miss=miss, N1=N1, gain_over_incoming=gain, Hc_over_linear_design=ratio,
                               W50=W50, rules=OUT05)
    od = XC.guard_out(out_dir or os.path.join(rd, "e51"), allow_scratch=True)
    p = os.path.join(od, "judge_E05.json")
    XC.jdump(res, p)
    res["_path"] = p.replace("\\", "/")
    return res


# ====================================================================== pre-freeze calibration
def calib():
    t0 = time.time()
    R50 = XC.REPO + "/Unity/Build/FLIP50/"
    lo, hi = R50 + "smoke/SMOKE50DA_D19B_T12_dp1p0", R50 + "runs/DM1A_D19B_T12_th80_dp0p5"
    e_lo, src_lo = still_offset(lo); e_hi, src_hi = still_offset(hi)
    Hlo, Hhi = HF(lo), HF(hi)
    K = ["Hc", "W50", "W80", "W95", "K", "S2", "ring_max"]
    rows = []
    for f in range(26 * 24, 50 * 24 + 1, 3):
        if f not in Hlo.where or f not in Hhi.where:
            continue
        a, ma = Hlo.get(f); b, mb = Hhi.get(f)
        A = EM.hf_metrics(a, ma, e_lo, xwin=(170, 300)); B = EM.hf_metrics(b, mb, e_hi, xwin=(170, 300))
        if not A or not B or "W50" not in A or "W50" not in B:
            continue
        if A["Hc"] >= 6.0 and B["Hc"] >= 6.0 and abs(A["x_pk"] - B["x_pk"]) <= 4.0:
            rows.append((f, A, B))
    bias = dict(n_matched=len(rows), eta0_1p0=e_lo, eta0_0p5=e_hi, eta0_sources=[src_lo, src_hi],
                rule="DM1A (0.5 m) vs SMOKE50DA (1.0 m, same sea), frames 26-50 s every 3rd, both Hc >= 6 m and x_pk within 4 m; e51 hf_metrics "
                     "xwin (170, 300); eta0 = each run's online still offset")
    for k in K:
        q = [A[k] / B[k] for _, A, B in rows if B.get(k) and A.get(k) is not None and np.isfinite(A[k]) and np.isfinite(B[k])]
        bias[k] = dict(median=float(np.median(q)), p25=float(np.percentile(q, 25)), p75=float(np.percentile(q, 75))) if q else None
    d = [EM.score_vs_target(A)[0] - EM.score_vs_target(B)[0] for _, A, B in rows]
    bias["miss_diff_1p0_minus_0p5"] = dict(median=float(np.median(d)), p25=float(np.percentile(d, 25)), p75=float(np.percentile(d, 75))) if d else None
    # N1 on the measured single-focus runs at their e51 'max' frames (baseline.json), plus the 1.0 m twin at its period maxima
    base = json.load(open(XC.B51 + "/target/baseline.json", encoding="utf8"))
    n1 = {}
    for lab, Rr in base["runs"].items():
        rd = Rr["run_dir"]; eta0 = float(Rr["still_offset_m"]); Hh = HF(rd); vals = []
        for p in Rr["per_breaker"]:
            mx = p.get("max")
            if not mx:
                continue
            f = int(mx["frame"])
            on_x = float(p["on_x"])
            a, meta = Hh.get(f)
            m = EM.hf_metrics(a, meta, eta0, xwin=(on_x - 60.0, on_x + 35.0))
            iso = n1_isolation(EM.median3(a) - eta0, meta, m)
            vals.append(dict(k=p["k"], frame=f, N1=iso.get("N1"), at=iso.get("at")))
        n1[lab] = dict(values=vals, range=[min(v["N1"] for v in vals), max(v["N1"] for v in vals)] if vals else None)
    tw = []
    for f in (818, 1154):
        a, meta = Hlo.get(f)
        m = EM.hf_metrics(a, meta, e_lo, xwin=(150, 330))
        iso = n1_isolation(EM.median3(a) - e_lo, meta, m)
        tw.append(dict(frame=f, Hc=m.get("Hc"), N1=iso.get("N1"), at=iso.get("at")))
    n1["DM1A_1p0_twin_SMOKE50DA"] = dict(values=tw, range=[min(v["N1"] for v in tw), max(v["N1"] for v in tw)])
    return dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip51/x51_ana.py calib", bias_T12=bias, N1=n1,
                N1_definition=N1DEF, cpu_s=round(time.time() - t0, 1),
                still_reading_1p0=dict(note="SMOKE50DA hf median over x 110-150 m: frame 1 0.000 m (the initial state), frames 2-49 0.483 m; DM1A frame 1 "
                                            "0.000, frames 2-49 0.073-0.082 m [measured 2026-10-17 before freezing]"))


# ====================================================================== CLI
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    if "periods" in opt or "tpass" in opt:          # TEST ONLY (e.g. a T 12 FLIP50 run, output to the scratchpad); recorded in the output
        if opt.get("out") is None or not os.path.abspath(opt["out"]).replace("\\", "/").lower().startswith(XC.SCRATCH_PREFIX.lower()):
            raise SystemExit("--periods / --tpass are test overrides: give --out=<scratchpad dir>")
        if "periods" in opt:
            SCAN["periods"] = [int(v) for v in opt["periods"].split(",")]
        if "tpass" in opt:
            SCAN["t_pass"] = [float(v) for v in opt["tpass"].split(",")]
        SCAN["TEST_OVERRIDE"] = True
    if a[0] == "screen":
        r = screen(a[1], case=opt.get("case"), out_dir=opt.get("out"), T=opt.get("T"))
        print(json.dumps(XC.clean(summary_line(r)), ensure_ascii=False))
    elif a[0] == "judge05":
        r = judge05(a[1], case=opt.get("case"), out_dir=opt.get("out"))
        s = summary_line(r); s["judgement_05"] = r.get("judgement_05")
        print(json.dumps(XC.clean(s), ensure_ascii=False))
    elif a[0] == "decide":
        scr = {}
        for c in XC.ORDER:
            p = opt.get(c)
            scr[c] = json.load(open(p, encoding="utf8")) if p and os.path.exists(p) else None
        d = decide(scr)
        p = opt.get("out")
        if p:
            XC.guard_out(os.path.dirname(p), allow_scratch=True)
            XC.jdump(d, p)
        print(json.dumps(XC.clean(d), ensure_ascii=False))
    elif a[0] == "calib":
        d = calib()
        p = opt.get("out") or (XC.PLAN_DIR + "/calib_E.json")
        XC.guard_out(os.path.dirname(p), allow_scratch=True)
        XC.jdump(d, p)
        print(json.dumps(XC.clean({k: d[k] for k in ("bias_T12", "cpu_s")}), ensure_ascii=False))
        print(json.dumps(XC.clean({k: v["range"] for k, v in d["N1"].items()}), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
