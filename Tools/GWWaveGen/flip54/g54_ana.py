# -*- coding: utf-8 -*-
"""FLIP54 K54: read the K54 2D strips with the pv53 ruler, calibrate K0's H once, and judge the concave-bed arms against K0 by the bar
frozen in Unity/Build/FLIP54/k54/plan/plan_K54_frozen.json (py -3.10 -B; numpy, scipy, scikit-image, PIL, ffmpeg).
2026-10-18 written new (Claude, FLIP54 builder K). Read only (imported, never edited): flip49/g49_periodic_ana.py (Ctx49 = the records,
the bed, the still offset; find_breakers = the FLIP49 event rule and its k numbering; r6 readers, zero-down waves, Goda & Suzuki), flip46
g46_analyze.r2_mask + STUDY52 s52_shape.measure_mask + d_shape_measure.pick (= the pv53 ruler), flip47 g47_video.score3 / print_phys.
In memory only: g49_common.B49 := Unity/Build/FLIP54 before g49_periodic_ana is imported (its guards then point into FLIP54, as
g50_common.redirect_gc49 does for FLIP50); nothing of FLIP49 is written.

Per strip (`measure`): breakers by the FLIP49 event rule (front face first vertical, k numbered in time order); judged = k2, k3, k4. For each
judged breaker, the centre section r2 (y 0.25 m) is measured with the pv53 ruler at EVERY frame in [t_on - 2.0 s, t_on + 3.5 s] along the
pv53 crest track (top of the centre hf row, 3-point median; -1.0 .. +2.5 m per frame forward, -2.5 .. +1.0 m backward), plus:
  eligible frames   eta_c >= 0.6 x the largest eta_c in the window (pv53 crest floor without a judge Hc), no ruler error
  first lip         first eligible frame with lip_thick_mid > 0 (the design workflow's hoodchord.py rule)
  pre-touchdown     eligible frames before the first frame AFTER the first lip whose face chord exceeds 120 deg (the jet has landed: the
                    0.1-0.5 eta_c chord then runs under the jet, DFG-2B f1484 70 deg -> f1486 141 deg [measured]); frames before the first
                    lip with chord > 120 deg are dropped one by one
  hood78            max hood_area over pre-touchdown frames with chord <= 78 deg (0 if none)                         -> bar (i)
  hood14 frame      first pre-touchdown frame with hood_area >= 0.14: its eta_c (m) and front foot (front_x01_rel)   -> bars (ii), (iii)
  onset076          first frame on the hf crest track in [t_on - 6 s, landing] with crest / still depth under it >= 0.76 (also 0.70,
                    0.65: the ladder below)
  onset -> lip      (first lip - onset) / 24 s (negative if the lip comes first)                                     -> bar (iv)
                    threshold ladder (registered): 0.76; if K0 does not reach 0.76 at or before its first lip on >= 2 judged breakers,
                    0.70, then 0.65, then 0.60 - the same threshold for every arm, chosen on K0 alone (2D periodic crests are lower relative to depth
                    than the 3D focused crest of DFG-2B: FLIP49 BS0 2D, h0 17 m, T 12 s, 1:10, reached Hc/h 0.57-0.74 at its first lip
                    [measured with this code 2026-10-18])
  max hood frame    max hood_area over the pre-touchdown frames: its chord and its front-trough depth                 -> bar (v)
  front trough      centre hf row, lowest point in (x_c, x_c + 45 m]; depth = still depth there + eta there; / eta_c
  cavity air        sum over columns x_c - 0.5 eta_c .. x_c + 1.5 eta_c with >= 2 water runs whose top run starts above 0.2 eta_c of the
                    air between the top run and the run below, x dx / eta_c^2 (numerics_resolution/series_check.py rule; print 0.23)
  hollow instant    (R0 rule, report) eligible frame with the largest cavity air with chord 50-100 deg and lip >= 0.30
  hood bands        max hood (hood > 0) at chord 50-80 and at chord 80-100 over all eligible frames (incoming_sea/hoodchord.py rule;
                    the A12 validity)
  h_b               still depth at the FLIP49 onset (campaign B's h_b; the K0 calibration)
Medians over the judged breakers (values that exist; >= 2 needed).

usage:
  py -3.10 -B g54_ana.py measure <run_dir> [--out=<dir under FLIP54>]          -> <out | run>/k54/k54_ana.json (prints a summary JSON line)
  py -3.10 -B g54_ana.py calib <K0p run_dir> [--out=<file under FLIP54>] [--ana=<k54_ana.json>] [--force]
                                                                                once-only K0 calibration -> k54/plan/calibration_K0.json
  py -3.10 -B g54_ana.py verdict --map=<json file {arm: run_dir}> [--out=<dir under FLIP54>] [--no-video]
                                                                                -> k54/verdict/verdict_K54.json, K54_sheet.png, K54_sections.mp4
"""
import os, sys, json, math, glob, time, io, contextlib, subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                     # noqa: E402
import g54_common as C                 # noqa: E402
C.GC49.B49 = C.B54                     # in memory only (see the docstring); before g49_periodic_ana is imported
import g49_periodic_ana as PA          # noqa: E402
A46 = PA.A46
import g47_video as GV                 # noqa: E402
from scipy import ndimage as ndi       # noqa: E402

FPS = 24.0
WIN = (-2.0, 3.5)                      # ruler window around the FLIP49 onset (s) [chosen, registered]
BACK_S = 6.0                           # onset076 search back from the onset (s) [chosen, registered]
FWD_STEP = (-1.0, 2.5)                 # pv53 crest track steps (m per frame)
BACK_STEP = (-2.5, 1.0)
CREST_FLOOR = 0.6
CHORD_LANDED = 120.0
TROUGH_AHEAD_M = 45.0
ONSET_RATIO = 0.76
ONSET_LADDER = (0.76, 0.70, 0.65, 0.60)   # registered: 0.76 (task); the lower rungs only if K0 never reaches 0.76 before its first lip
HOOD14 = 0.14
FONT = "C:/Windows/Fonts/meiryo.ttc"
ANA_NAME = "k54_ana.json"


def t_of(f):
    return (int(f) - 1) / FPS


def med(v):
    v = [float(x) for x in v if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))]
    return float(np.median(v)) if len(v) >= 2 else None


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ====================================================================== the run
class Run:
    def __init__(self, rd):
        self.rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
        self.id = os.path.basename(self.rd)
        self.cfg = PA.load_cfg(self.rd)
        with contextlib.redirect_stdout(io.StringIO()):
            self.cx = PA.Ctx49(self.rd, {})
        self.off = float(self.cx.off)
        self.r2set = set(int(f) for f in self.cx.R2.frames)
        self.hfset = set(int(f) for f in self.cx.R1.frames)
        sf = self.cfg.get("sf") or {}
        self.T = float(sf.get("T", C.T_MAIN))
        self.H = float(sf.get("H", float("nan")))

    def depth(self, x):
        return -np.asarray(self.cx.bed_z(np.asarray(x, float), 0.0), float)

    def centre_row(self, f):
        e, m, t = self.cx.R1.get(f)
        xs = float(m["x0"]) + float(m["dx"]) * np.arange(int(m["res"][0]))
        row = np.asarray(e[0], float) - self.off
        row = ndi.median_filter(np.where(np.isfinite(row), row, -99.0), size=3, mode="nearest")
        return xs, row

    def track(self, f0, x0, f_lo, f_hi):
        """pv53 PVRun.track (copied): the crest of the centre hf row followed forward and backward from (f0, x0)."""
        out = {}
        for rng, step in ((range(f0, f_hi + 1), FWD_STEP), (range(f0, f_lo - 1, -1), BACK_STEP)):
            xg = x0
            for i, f in enumerate(rng):
                if f not in self.hfset:
                    break
                xs, row = self.centre_row(f)
                lo, hi = (-3.0, 3.0) if i == 0 else step
                sel = np.where((xs >= xg + lo) & (xs <= xg + hi))[0]
                if not len(sel):
                    break
                xg = float(xs[sel[int(np.argmax(row[sel]))]])
                out[f] = xg
        return out

    def ruler(self, f, xg, keep=False):
        """pv53 PVRun.measure (copied) + cavity air + front trough."""
        try:
            M, X, Z, t = A46.r2_mask(self.cx, f, xg)
            mm = A46.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=self.cx.Lc))
            row = A46.DS.pick(mm)
            s3, parts = GV.score3(row)
        except Exception as ex:
            return dict(frame=int(f), t=t_of(f), xg=xg, error=repr(ex)[:200])
        g = lambda k: (float(row[k]) if isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool) and math.isfinite(float(row[k])) else None)
        r = dict(frame=int(f), t=float(t), xg=float(xg), score3=s3, chord=g("face_chord_deg_01_05"), foot=g("front_x01_rel"), hood=g("hood_area"),
                 hollow=g("hood_wall_x_rel"), lip=g("lip_thick_mid"), gap=g("gap_max"), back=g("back_angle_07_09_deg"), w07=g("width07_silhouette"),
                 eta_c=g("eta_c"), x_c=g("x_c"), hood_height_m=(float(mm["hood_height_m"]) if mm.get("hood_height_m") is not None else None))
        if r["eta_c"] and r["x_c"] is not None:
            r["air"] = cavity_air(M, X, Z, r["eta_c"], r["x_c"])
            r.update(self.front_trough(f, r["x_c"], r["eta_c"]))
        if keep:
            r["_mask"] = (M, X, Z)
        return r

    def front_trough(self, f, xc, eta_c):
        try:
            xs, row = self.centre_row(f)
        except Exception:
            return dict(trough_d=None, trough_x=None, trough_eta=None, trough_d_over_eta=None)
        sel = np.where((xs > xc) & (xs <= xc + TROUGH_AHEAD_M) & (row > -90.0))[0]
        if not len(sel):
            return dict(trough_d=None, trough_x=None, trough_eta=None, trough_d_over_eta=None)
        i = int(sel[int(np.argmin(row[sel]))])
        d = float(self.depth(xs[i])) + float(row[i])
        return dict(trough_x=float(xs[i]), trough_eta=float(row[i]), trough_d=d, trough_d_over_eta=d / eta_c)


def cavity_air(M, X, Z, eta, xc):
    """numerics_resolution/series_check.py 'air_all' (copied): air under overturned columns / eta_c^2."""
    S52 = A46.S52
    dx = float(X[1] - X[0]); dz = float(Z[1] - Z[0])
    j_lo = int(np.searchsorted(Z, 0.2 * eta))
    air = 0.0
    for i in np.where((X >= xc - 0.5 * eta) & (X <= xc + 1.5 * eta))[0]:
        rr = S52.runs(M[:, i])
        if len(rr) >= 2:
            top = rr[-1]; below = rr[-2]
            if top[0] > j_lo:
                air += (Z[top[0]] - Z[below[1]] - dz)
    return float(air * dx / eta ** 2)


# ====================================================================== one breaker
def measure_breaker(R, ev, keep_rows=True):
    f_on = int(ev["on_f"]); x_on = float(ev["on_x"])
    f_lo = f_on + int(round(WIN[0] * FPS)); f_hi = f_on + int(round(WIN[1] * FPS))
    f_back = f_on - int(round(BACK_S * FPS))
    trk = R.track(f_on, x_on, f_back, f_hi)
    rows = []
    for f in range(f_lo, f_hi + 1):
        if f in R.r2set and f in trk:
            rows.append(R.ruler(f, trk[f]))
    ok = [r for r in rows if "error" not in r and r.get("eta_c")]
    hc_ref = max([r["eta_c"] for r in ok] or [0.0])
    floor = CREST_FLOOR * hc_ref
    el = [r for r in ok if r["eta_c"] >= floor - 1e-9]
    lip = [r for r in el if (r.get("lip") or 0.0) > 0.0]
    f_lip = lip[0]["frame"] if lip else None
    # pre-touchdown frames
    pre = []
    for r in el:
        ch = r.get("chord")
        if f_lip is not None and r["frame"] > f_lip and ch is not None and ch > CHORD_LANDED:
            break
        if ch is not None and ch > CHORD_LANDED:
            continue
        pre.append(r)
    hv = lambda r: (r.get("hood") or 0.0)
    c78 = [r for r in pre if r.get("chord") is not None and r["chord"] <= 78.0]
    r78 = max(c78, key=hv) if c78 else None
    rmx = max(pre, key=hv) if pre else None
    h14 = [r for r in pre if hv(r) >= HOOD14 - 1e-12]
    r14 = h14[0] if h14 else None
    # onset on the hf crest track: crest / still depth under it, from t_on - 6 s to the landing (or the window end); first crossing of
    # each ladder threshold (0.76 = the task's; 0.70 / 0.65 only if K0 never reaches 0.76 before its first lip, see decide())
    landed = next((r["frame"] for r in el if f_lip is not None and r["frame"] > f_lip and (r.get("chord") or 0) > CHORD_LANDED), None)
    ser76 = []
    cross = {}
    for f in range(f_back, (landed if landed is not None else f_hi) + 1):
        if f not in trk or f not in R.hfset:
            continue
        xs, row = R.centre_row(f)
        i = int(np.argmin(np.abs(xs - trk[f])))
        Hc = float(row[i]); h = float(R.depth(xs[i]))
        ratio = Hc / h if h > 0.05 else float("inf")
        ser76.append((f, float(xs[i]), Hc, h, ratio))
        for thr in ONSET_LADDER:
            if thr not in cross and ratio >= thr:
                cross[thr] = dict(frame=f, t=t_of(f), x=float(xs[i]), Hc=Hc, h=h, ratio=ratio, before_first_lip=bool(f_lip is None or f <= f_lip))
    on76 = cross.get(ONSET_RATIO)
    o2l_l = {("%.2f" % thr): (((f_lip - cross[thr]["frame"]) / FPS) if (thr in cross and f_lip is not None) else None) for thr in ONSET_LADDER}
    o2l = o2l_l["%.2f" % ONSET_RATIO]
    pre_lip = [q for (f, x, hc, h, q) in ser76 if f_lip is not None and f <= f_lip and math.isfinite(q)]
    # hollow instant (R0 rule) and hood bands (hoodchord rule)
    hol = [r for r in el if r.get("chord") is not None and 50.0 <= r["chord"] <= 100.0 and (r.get("lip") or 0.0) >= 0.30 and r.get("air") is not None]
    rhol = max(hol, key=lambda r: r["air"]) if hol else None
    b1 = [hv(r) for r in el if r.get("chord") is not None and 50.0 <= r["chord"] <= 80.0 and hv(r) > 0]
    b2 = [hv(r) for r in el if r.get("chord") is not None and 80.0 < r["chord"] <= 100.0 and hv(r) > 0]
    best3 = min([r for r in el if r.get("score3") is not None], key=lambda r: (r["score3"], r["frame"]), default=None)
    pick = lambda r, ks: ({k: r.get(k) for k in ks} if r else None)
    KS = ("frame", "t", "x_c", "eta_c", "chord", "foot", "hood", "lip", "air", "trough_d_over_eta", "trough_d", "score3", "xg")
    out = dict(k=int(ev["k"]), on_f=f_on, on_t=float(ev["on_t"]), on_x=x_on, h_b=float(ev.get("depth_on")), on_eta=float(ev.get("on_eta")),
               window_frames=[f_lo, f_hi], n_frames=len(rows), n_eligible=len(el), n_pre_touchdown=len(pre), n_errors=sum(1 for r in rows if "error" in r),
               crest_ref_m=hc_ref, crest_floor_m=floor,
               first_lip=pick(lip[0], KS) if lip else None,
               landed_frame=landed,
               hood78=(hv(r78) if r78 else 0.0), hood78_at=pick(r78, KS),
               hood_max=(hv(rmx) if rmx else 0.0), hood_max_at=pick(rmx, KS),
               chord_at_hood_max=(rmx.get("chord") if rmx else None), trough_at_hood_max=(rmx.get("trough_d_over_eta") if rmx else None),
               eta_at_hood_max=(rmx.get("eta_c") if rmx else None), foot_at_hood_max=(rmx.get("foot") if rmx else None),
               hood14_at=pick(r14, KS), eta_at_hood14=(r14.get("eta_c") if r14 else None), foot_at_hood14=(r14.get("foot") if r14 else None),
               onset076=on76, onset_to_lip_s=o2l, onset_cross={("%.2f" % k): v for k, v in cross.items()}, onset_to_lip_ladder_s=o2l_l,
               ratio_max_before_lip=(max(pre_lip) if pre_lip else None),
               hollow_instant=pick(rhol, KS),
               hood_chord50_80=max(b1 or [0.0]), hood_chord80_100=max(b2 or [0.0]), n_chord50_80=len(b1), n_chord80_100=len(b2),
               best_score3=pick(best3, KS),
               air_max_pre=max([r.get("air") or 0.0 for r in pre] or [0.0]))
    if keep_rows:
        out["series"] = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if not k.startswith("_")} for r in rows]
        out["onset076_series"] = [[f, round(x, 2), round(hc, 3), round(h, 3), round(q, 4) if math.isfinite(q) else None] for f, x, hc, h, q in ser76]
    return out


# ====================================================================== inlet and health (no file written)
def inlet_numbers(rd, cfg):
    try:
        R6 = PA.load_r6(rd)
    except SystemExit as e:
        return dict(error=str(e))
    off = PA.still_off(PA.run_recs(rd))
    sf = cfg.get("sf") or {}
    T = float(sf.get("T", C.T_MAIN)); c_t = float(sf.get("c", 12.0)); k_sf = float(sf.get("k", 2 * math.pi / 110.0))
    P = cfg.get("parms") or {}
    t = R6["t"]
    gxy = R6["gxy"]
    ta = float(P.get("ramp_s", 2 * T)) + (float(max(gxy[:, 0])) - float(P.get("x_p", C.X_P))) / c_t
    nper = int(math.floor((float(t[-1]) - ta) / T + 1e-9))
    tb = ta + nper * T
    sel = (t >= ta - 1e-9) & (t <= tb + 1e-9)
    out = dict(window_s=[ta, tb], periods=nper, H_target_m=float(sf.get("H", 0.0)), still_offset_m=off, gauges={})
    for j, (xg, yg) in enumerate(gxy):
        e = R6["gauge"][:, j] - off
        ws, mean = PA.waves_zero_down(t[sel], e[sel])
        ws = [w for w in ws if w["t_down0"] >= ta and w["t_down1"] <= tb]
        Hs = [w["H"] for w in ws]
        out["gauges"]["x%g_y%g" % (xg, yg)] = dict(x=float(xg), y=float(yg), n=len(ws), H_mean=float(np.mean(Hs)) if Hs else None,
                                         crest_mean=float(np.mean([w["crest"] for w in ws])) if ws else None, mean_level=mean)
    y0 = float(np.min(np.abs(gxy[:, 1])))
    row0 = [j for j in range(len(gxy)) if abs(abs(float(gxy[j, 1])) - y0) < 1e-6]          # the centre gauge row
    gx = sorted(set(float(gxy[j, 0]) for j in row0))
    if len(gx) >= 2 and sel.sum() > 10:
        ja = next(j for j in row0 if abs(float(gxy[j, 0]) - gx[0]) < 1e-6); jb = next(j for j in row0 if abs(float(gxy[j, 0]) - gx[1]) < 1e-6)
        try:
            aI, aR, K, sk = PA.goda_suzuki(t[sel], R6["gauge"][sel, ja], R6["gauge"][sel, jb], gx[0], gx[1], k_sf, T)
            out["Kr"] = dict(pair=[gx[0], gx[1]], a_I=aI, a_R=aR, Kr=K, sin_kdl=sk, tag="computed from measured (Goda & Suzuki 1976, first harmonic)")
        except Exception as ex:
            out["Kr"] = dict(pair=[gx[0], gx[1]], Kr=None, error=repr(ex)[:120])
    gk = lambda j: "x%g_y%g" % (float(gxy[j, 0]), float(gxy[j, 1]))
    hs = [out["gauges"][gk(j)]["H_mean"] for j in row0 if out["gauges"][gk(j)]["H_mean"] is not None]
    out["H_realized_m"] = float(np.mean(hs)) if hs else None
    # volume (stage A: corrected whole-tank V / V0 - 1 after 1.5 s) and the mean level over the shelf front per period
    try:
        vi = {nm: i for i, nm in enumerate(R6["vnames"])}
        V = R6["vol"][:, vi["V_m3"]]
        ref = (t >= 1.0 - 1e-9) & (t <= 1.5 + 1e-9)
        V0 = float(np.nanmean(V[ref]))
        aft = t > 1.5
        out["volume_max_rel"] = float(np.nanmax(np.abs(V[aft] / V0 - 1.0))) if aft.any() else None
    except Exception as ex:
        out["volume_error"] = repr(ex)[:120]
    try:
        names = R6["names"]
        if "shelf_front" in names:
            i = names.index("shelf_front")
            out["shelf_front_level_period_means_m"] = PA.period_means(t, R6["lvl"][:, i] - off, float(P.get("ramp_s", 2 * T)), T,
                                                                      int((float(t[-1]) - float(P.get("ramp_s", 2 * T))) // T))
    except Exception:
        pass
    return out


# ====================================================================== measure one strip
def measure(rd, out_dir=None):
    t0 = time.time()
    R = Run(rd)
    with contextlib.redirect_stdout(io.StringIO()):
        res, _ = PA.find_breakers(R.rd, R.cfg)
    evs = res["events"]
    judged = [e for e in evs if e["k"] in C.JUDGED_K]
    rows = []
    for e in judged:
        log("  %s k%d onset t %.2f x %.1f h_b %.2f" % (R.id, e["k"], e["on_t"], e["on_x"], e["depth_on"]))
        rows.append(measure_breaker(R, e))
    keys = ("h_b", "on_x", "on_t", "hood78", "eta_at_hood14", "foot_at_hood14", "onset_to_lip_s", "chord_at_hood_max", "trough_at_hood_max",
            "hood_max", "eta_at_hood_max", "foot_at_hood_max", "hood_chord50_80", "hood_chord80_100", "air_max_pre")
    meds = {k: med([r.get(k) for r in rows]) for k in keys}
    meds["first_lip_lip"] = med([(r.get("first_lip") or {}).get("lip") for r in rows])
    meds["hollow_air"] = med([(r.get("hollow_instant") or {}).get("air") for r in rows])
    meds["best_score3"] = med([(r.get("best_score3") or {}).get("score3") for r in rows])
    meds["onset076_x"] = med([(r.get("onset076") or {}).get("x") for r in rows])
    meds["onset076_Hc"] = med([(r.get("onset076") or {}).get("Hc") for r in rows])
    meds["hood14_reached_n"] = sum(1 for r in rows if r.get("hood14_at"))
    for thr in ONSET_LADDER:
        kk = "%.2f" % thr
        meds["onset_to_lip_s@" + kk] = med([(r.get("onset_to_lip_ladder_s") or {}).get(kk) for r in rows])
        meds["onset_reached_before_lip_n@" + kk] = sum(1 for r in rows if ((r.get("onset_cross") or {}).get(kk) or {}).get("before_first_lip")
                                                      and r.get("first_lip"))
    meds["ratio_max_before_lip"] = med([r.get("ratio_max_before_lip") for r in rows])
    inl = inlet_numbers(R.rd, R.cfg)
    case = R.cfg.get("case") or {}
    health = dict(n_judged=len(rows), n_judged_ok=bool(len(rows) >= 2),
                  Kr=(inl.get("Kr") or {}).get("Kr"), Kr_ok=bool((inl.get("Kr") or {}).get("Kr") is not None and inl["Kr"]["Kr"] <= 0.10),
                  volume_max_rel=inl.get("volume_max_rel"), volume_ok=bool(inl.get("volume_max_rel") is not None and inl["volume_max_rel"] <= 0.01),
                  breaks_on_slope=bool(all(r["on_x"] >= C.X_TOE for r in rows)) if rows else False,
                  rule="report: Kr <= 0.10 (task), stage-A volume <= 1 % (FLIP49), >= 2 judged breakers, judged onsets at x >= 160.25 m")
    out = dict(run_id=R.id, run_dir=R.rd.replace(C.REPO + "/", ""), arm=case.get("arm"), role=case.get("role"), label=case.get("label"),
               T=R.T, H=R.H, still_offset_m=R.off, Lc=R.cx.Lc, date=time.strftime("%Y-%m-%d %H:%M:%S"),
               events=[{k: e.get(k) for k in ("k", "on_f", "on_t", "on_x", "on_eta", "depth_on", "why")} for e in evs],
               judged_k=[r["k"] for r in rows], breakers=rows, medians=meds, inlet=inl, health=health,
               rules=dict(window_s=list(WIN), back_s=BACK_S, crest_floor=CREST_FLOOR, chord_landed=CHORD_LANDED, trough_ahead_m=TROUGH_AHEAD_M,
                          onset_ratio=ONSET_RATIO, hood14=HOOD14, ruler="pv53 (g46 r2_mask -> STUDY52 measure_mask -> d_shape_measure.pick, g47_video.score3)"),
               module_shas=C.module_shas(), wall_s=time.time() - t0,
               tags=dict(all="measured (FLIP records + the pv53 ruler)", medians="measured (median over judged breakers with a value; >= 2 needed)"))
    od = C.guard_out(out_dir or (R.rd + "/k54"))
    C.jdump(out, od + "/" + ANA_NAME)
    return out, od + "/" + ANA_NAME


def load_or_measure(rd, out_dir=None):
    p = (out_dir or (os.path.abspath(rd).replace("\\", "/").rstrip("/") + "/k54")) + "/" + ANA_NAME
    if os.path.exists(p):
        return C.jload(p), p
    return measure(rd, out_dir)


# ====================================================================== calibration (once)
def calib(rd, out_file=None, force=False, ana=None):
    if ana:                                      # an analysis file written elsewhere under FLIP54 (the launcher's --simulate stand-ins)
        a, p = C.jload(ana), ana
        if not a:
            raise SystemExit("no analysis %s" % ana)
    else:
        a, p = load_or_measure(rd)
    hb = [r["h_b"] for r in a["breakers"]]
    src = "judged k2-k4"
    if len(hb) < 2:
        hb = [e["depth_on"] for e in a["events"] if e["k"] >= 2]
        src = "all breakers k >= 2 (fewer than 2 judged)"
    hb_med = float(np.median(hb)) if hb else None
    H_K0, why = C.h_calibrated(a["H"], hb_med)
    o = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), pilot_run=a["run_id"], pilot_ana=p.replace(C.REPO + "/", ""), H_pilot=a["H"], T=a["T"],
             h_b_each=hb, h_b_source=src, h_b_median=hb_med, band=list(C.H_BAND_HB), target=C.H_TARGET_HB, exponent=C.H_EXP, clamp=list(C.H_CLAMP),
             H_K0=H_K0, why=why, pilot_is_K0=bool(H_K0 is not None and abs(H_K0 - round(a["H"], 2)) < 1e-9),
             H_A12=(C.h_a12(H_K0) if H_K0 is not None else None), goda_ratio=C.goda_ratio(C.T_MAIN, C.T_A12),
             plan_sha256=(C.sha256_file(C.PLAN) if os.path.exists(C.PLAN) else None),
             rule="plan K54 wave.H_calibration (registered before any run): once only; then frozen for K0, K1-K5 (and A12 through the Goda ratio)",
             tags=dict(h_b="measured", H_K0="calibrated", H_A12="computed"))
    target = out_file or C.CALIB
    if os.path.exists(target) and not force and out_file is None:
        raise SystemExit("calibration %s exists (once only); --force only to repeat an identical calibration" % target)
    C.jdump(o, target)
    return o, target


# ====================================================================== verdict
def ref_value(k0, key, fb=None):
    v = k0["medians"].get(key)
    if v is None and fb:
        return k0["medians"].get(fb), "fallback %s" % fb
    return v, key


def onset_threshold(k0):
    """the ladder rung used for bar (iv): the first of 0.76 / 0.70 / 0.65 that K0 reaches at or before its first lip on >= 2 judged breakers."""
    for thr in ONSET_LADDER:
        if (k0["medians"].get("onset_reached_before_lip_n@%.2f" % thr) or 0) >= 2:
            return "%.2f" % thr
    return None


def criteria(a, k0):
    m, r = a["medians"], k0["medians"]
    out = {}
    thr = onset_threshold(k0)
    o2l_a = m.get("onset_to_lip_s@" + thr) if thr else None
    o2l_r = r.get("onset_to_lip_s@" + thr) if thr else None

    def item(name, val, ref, ok, rule):
        out[name] = dict(value=val, ref=ref, pass_=None if ok is None else bool(ok), rule=rule)
    # (i)
    item("i_hood78", m.get("hood78"), r.get("hood78"),
         None if r.get("hood78") is None else (m.get("hood78") is not None and m["hood78"] >= r["hood78"] - 1e-12),
         "median max hood at chord <= 78 deg >= K0's")
    # (ii) / (iii): K0 reference at its first hood >= 0.14 frame, fallback its max-hood frame
    e_ref, e_src = ref_value(k0, "eta_at_hood14", "eta_at_hood_max")
    f_ref, f_src = ref_value(k0, "foot_at_hood14", "foot_at_hood_max")
    item("ii_eta_at_hood14", m.get("eta_at_hood14"), None if e_ref is None else 1.08 * e_ref,
         None if e_ref is None else (m.get("eta_at_hood14") is not None and m["eta_at_hood14"] >= 1.08 * e_ref),
         "median eta_c at the first frame with hood >= 0.14 >= 1.08 x K0's (%s)" % e_src)
    item("iii_foot_at_hood14", m.get("foot_at_hood14"), None if f_ref is None else f_ref - 0.10,
         None if f_ref is None else (m.get("foot_at_hood14") is not None and m["foot_at_hood14"] <= f_ref - 0.10),
         "median front foot there <= K0's - 0.10 (%s)" % f_src)
    item("iv_onset_to_lip", o2l_a, None if o2l_r is None else o2l_r - 0.5,
         None if o2l_r is None else (o2l_a is not None and o2l_a <= o2l_r - 0.5),
         "median onset (Hc/h %s, ladder rung chosen on K0) to first lip <= K0's - 0.5 s" % (thr or "none reached by K0: untestable"))
    ch, tr = m.get("chord_at_hood_max"), m.get("trough_at_hood_max")
    item("v_no_wall", dict(chord=ch, trough=tr), dict(chord_max=100.0, trough_min=0.55),
         (ch is not None and tr is not None and ch <= 100.0 and tr >= 0.55), "median chord at max hood <= 100 deg and front-trough depth >= 0.55 eta_c")
    # report only (never part of the pass): (v) against K0 instead of the absolute 100 deg
    ch_r = r.get("chord_at_hood_max")
    out["v_report_chord_vs_K0"] = dict(value=ch, ref=ch_r, pass_=None, report_only=True,
                                       below_K0=(None if (ch is None or ch_r is None) else bool(ch <= ch_r)),
                                       rule="REPORT ONLY: median chord at max hood <= K0's (2D plungers overturn on a steep face)")
    tested = [v["pass_"] for k, v in out.items() if v["pass_"] is not None and not v.get("report_only")]
    untest = [k for k, v in out.items() if v["pass_"] is None and not v.get("report_only")]
    return out, bool(tested and all(tested)), untest


def validity_A12(a):
    if a is None:
        return dict(valid=None, why="A12 not measured")
    m = a["medians"]
    per = [(r["k"], r["hood_chord50_80"], r["hood_chord80_100"], r["hood_chord50_80"] < r["hood_chord80_100"]) for r in a["breakers"]]
    n_ok = sum(1 for p in per if p[3])
    med_ok = (m.get("hood_chord50_80") is not None and m.get("hood_chord80_100") is not None and m["hood_chord50_80"] < m["hood_chord80_100"])
    return dict(valid=bool(med_ok and n_ok >= 2), median_50_80=m.get("hood_chord50_80"), median_80_100=m.get("hood_chord80_100"), per_breaker=per,
                n_breakers_ordered=n_ok, rule="DM1A's ordering (hood at chord 50-80 < hood at chord 80-100) on the median AND on >= 2 judged breakers "
                                              "(DM1A n2-n5: 0.080<0.174, 0.159<0.236, 0.132<0.249, 0.161<0.179 [measured])")


def decide(anas, plan=None):
    k0 = anas.get("K0")
    rows = {}
    if k0 is None or not k0["health"]["n_judged_ok"]:
        return dict(verdict="K0_INCOMPLETE", recommendation="none: K0 (the reference) has fewer than 2 judged breakers; diagnose the strip first",
                    arms={}, validity=validity_A12(anas.get("A12")))
    for arm in ("K1", "K2", "K3", "K4", "K5"):
        a = anas.get(arm)
        if a is None:
            rows[arm] = dict(status="not run")
            continue
        if not a["health"]["n_judged_ok"]:
            rows[arm] = dict(status="incomplete (< 2 judged breakers): cannot pass", pass_all=False)
            continue
        cr, ok, untest = criteria(a, k0)
        rows[arm] = dict(status="measured", pass_all=ok, criteria=cr, untestable=untest, health=a["health"], medians=a["medians"])
    val = validity_A12(anas.get("A12"))
    passing = [arm for arm in C.TEST_ARMS if (rows.get(arm) or {}).get("pass_all")]
    if val.get("valid") is False:
        verdict = "STRIPS_UNTRUSTED"
        rec = ("A12 does not reproduce DM1A's ordering (hood at chord 50-80 < at 80-100): the 2D strips are treated as untrusted; registered "
               "recommendation: take K4 (1:7 from h 12.5 m onto the 7.5 m shelf) straight to 3D (DFG-2B-V sea), report only")
        pick = "K4"
    elif passing:
        thr = onset_threshold(k0)
        key = lambda arm: (rows[arm]["medians"]["hood78"] or 0.0, -((rows[arm]["medians"].get("onset_to_lip_s@" + thr) if thr else None) or 99.0),
                           rows[arm]["medians"].get("eta_at_hood14") or 0.0)
        pick = max(passing, key=key)
        verdict = "PASS"
        rec = ("%s passes every registered item against K0 (%s); registered next step: %s in 3D with the DFG-2B-V sea (one change: the bed), "
               "report only - the user decides" % (pick, ", ".join(passing) + " pass" if len(passing) > 1 else "the only one", pick))
    else:
        verdict = "NONE_PASS"
        pick = None
        rec = "no arm among K1-K4 passes every registered item; no 3D bed is recommended from the strips (show the numbers; the user decides)"
    if val.get("valid") is None:
        rec += " | A12 (validity) was not measured: the strips' trust is unknown"
    k5 = rows.get("K5") or {}
    return dict(verdict=verdict, pick=pick, recommendation=rec, passing=passing, arms=rows, validity=val, onset_threshold=onset_threshold(k0),
                K5_bracket=("K5 (wall-side bracket) %s item (v)" % ("PASSES" if ((k5.get("criteria") or {}).get("v_no_wall") or {}).get("pass_") else "fails"))
                if k5.get("criteria") else "K5 not measured")


# ====================================================================== sheet and video (PIL + ffmpeg)
_FC = {}


def fnt(sz, bold=False):
    from PIL import ImageFont
    k = (sz, bold)
    if k not in _FC:
        try:
            _FC[k] = ImageFont.truetype(FONT, sz, index=1 if bold else 0)
        except Exception:
            _FC[k] = ImageFont.load_default()
    return _FC[k]


WATER = (60, 110, 160); SAND = (196, 178, 140); TXT = (20, 20, 20); SUB = (90, 90, 90); RED = (200, 30, 30); GREEN = (25, 130, 55)


def section_rgb(R, f, xg, xc, ec, w, h, XLr=-42.0, XRr=22.0):
    """the centre section of frame f (pv53 draw_section's raster: water blue, bed sand), x_c - 42 .. x_c + 22 m, z -9 .. eta_c + 3.5 m."""
    from PIL import Image
    M, X, Z, t = A46.r2_mask(R.cx, f, xg)
    XL, XR = xc + XLr, xc + XRr
    ZB, ZT = -9.0, max(ec + 3.5, 10.0)
    s = min(w / (XR - XL), h / (ZT - ZB))
    Wp, Hp = int((XR - XL) * s), int((ZT - ZB) * s)
    gx = XL + (np.arange(Wp) + 0.5) / s
    gz = ZT - (np.arange(Hp) + 0.5) / s
    ix = np.clip(np.round((gx - X[0]) / (X[1] - X[0])).astype(int), 0, len(X) - 1)
    iz = np.clip(np.round((gz - Z[0]) / (Z[1] - Z[0])).astype(int), 0, len(Z) - 1)
    inside = ((gx >= X[0]) & (gx <= X[-1]))[None, :] & ((gz >= Z[0]) & (gz <= Z[-1]))[:, None]
    wat = M[iz][:, ix] & inside
    rgb = np.full((Hp, Wp, 3), 255, np.uint8)
    rgb[wat] = WATER
    bz = np.asarray(R.cx.bed_z(gx, 0.0), float) - R.off
    rgb[gz[:, None] <= bz[None, :]] = SAND
    im = Image.fromarray(rgb)
    geo = dict(XL=XL, XR=XR, ZB=ZB, ZT=ZT, s=s, Wp=Wp, Hp=Hp)
    return im, geo


def draw_panel(im, R, a, br, at, box, title, lines, show_print=True):
    from PIL import ImageDraw
    dr = ImageDraw.Draw(im)
    x0, y0, w, h = box
    dr.rectangle([x0, y0, x0 + w, y0 + h], fill=(255, 255, 255), outline=(150, 150, 150))
    dr.text((x0 + 6, y0 + 4), title, fill=TXT, font=fnt(15, True))
    if not at:
        dr.text((x0 + 10, y0 + 40), "no frame to show", fill=RED, font=fnt(14))
        return
    f, xg, xc, ec = int(at["frame"]), float(at.get("xg") or at["x_c"]), float(at["x_c"]), float(at["eta_c"])
    try:
        sim, geo = section_rgb(R, f, xg, xc, ec, w - 50, h - 130)
    except Exception as ex:
        dr.text((x0 + 10, y0 + 40), "section error %s" % repr(ex)[:80], fill=RED, font=fnt(13))
        return
    px0, py0 = x0 + 40, y0 + 28
    im.paste(sim, (px0, py0))
    s, XL, ZT = geo["s"], geo["XL"], geo["ZT"]
    tr = lambda P: [(px0 + (p[0] - XL) * s, py0 + (ZT - p[1]) * s) for p in P]
    dr.line([(px0, py0 + ZT * s), (px0 + geo["Wp"], py0 + ZT * s)], fill=(120, 120, 120), width=1)
    if show_print:
        try:
            for q in GV.print_phys(xc, ec):
                P = [p for p in np.asarray(q) if geo["XL"] <= p[0] <= geo["XR"] and geo["ZB"] <= p[1] <= geo["ZT"]]
                if len(P) > 1:
                    dr.line(tr(P), fill=(0, 0, 0), width=2)
        except Exception:
            pass
    for zz in range(-5, int(ZT) + 1, 5):
        dr.text((px0 - 30, py0 + (ZT - zz) * s - 8), "%d" % zz, fill=SUB, font=fnt(11))
    yy = py0 + geo["Hp"] + 4
    for ln in lines:
        dr.text((x0 + 8, yy), ln, fill=TXT, font=fnt(13))
        yy += 18


def fmt(v, f="%.2f"):
    return "-" if v is None or (isinstance(v, float) and not math.isfinite(v)) else (f % v)


def median_breaker(a, key="hood_max"):
    rows = a.get("breakers") or []
    if not rows:
        return None
    vals = [r.get(key) or 0.0 for r in rows]
    m = float(np.median(vals))
    return min(rows, key=lambda r: (abs((r.get(key) or 0.0) - m), r["k"]))


def sheet(anas, runs, D, path):
    from PIL import Image, ImageDraw
    arms = [a for a in ("K0", "K1", "K2", "K3", "K4", "K5", "A12", "K0p") if a in anas and not (a == "K0p" and runs.get("K0p") == runs.get("K0"))]
    cols, pw, ph = 2, 700, 340
    nrow = int(math.ceil(len(arms) / cols))
    W, Hh = cols * pw + 30, 300 + nrow * (ph + 14)
    im = Image.new("RGB", (W, Hh), (247, 247, 244))
    dr = ImageDraw.Draw(im)
    dr.text((14, 10), "K54 concave-bed 2D strip screen: verdict %s%s" % (D["verdict"], (" -> " + D["pick"]) if D.get("pick") else ""), fill=TXT, font=fnt(22, True))
    yy = 44
    import textwrap
    for ln in [w for para in [D["recommendation"]] + [
            "validity (A12 vs DM1A ordering): %s  (median hood chord 50-80 %s < 80-100 %s; ordered on %s breakers)" % (
                D["validity"].get("valid"), fmt(D["validity"].get("median_50_80"), "%.3f"), fmt(D["validity"].get("median_80_100"), "%.3f"),
                D["validity"].get("n_breakers_ordered")),
            "bar vs K0 (medians over judged k2-k4): (i) hood at chord<=78 >= K0  (ii) eta_c at first hood>=0.14 >= 1.08 K0  (iii) foot there <= K0-0.10  "
            "(iv) onset(Hc/h 0.76)->first lip <= K0-0.5 s  (v) chord at max hood <= 100 and front trough >= 0.55 eta_c",
            "panels: centre section r2 of the median breaker at its MAX-HOOD frame before touchdown (pv53 ruler); black = the print outline scaled to "
            "this frame's crest (STUDY52 cn); blue water, sand bed; 2D strips (half width 6 m), not the 3D wave [measured]"] for w in textwrap.wrap(para, 165)]:
        dr.text((14, yy), ln, fill=SUB, font=fnt(14))
        yy += 20
    # medians table
    thr = D.get("onset_threshold")
    hdr = ["arm", "H m", "h_b m", "hood<=78", "eta@h14", "foot@h14", "on%s->lip" % (thr or "?"), "chord@hmax", "trough", "air max", "hollow", "pass"]
    xs = [14, 70, 130, 190, 270, 350, 430, 530, 630, 700, 780, 860]
    for x, t_ in zip(xs, hdr):
        dr.text((x, yy), t_, fill=TXT, font=fnt(13, True))
    yy += 18
    for arm in arms:
        m = anas[arm]["medians"]
        pa = (D["arms"].get(arm) or {}).get("pass_all")
        vals = [arm, fmt(anas[arm]["H"]), fmt(m.get("h_b")), fmt(m.get("hood78"), "%.3f"), fmt(m.get("eta_at_hood14")), fmt(m.get("foot_at_hood14")),
                fmt(m.get("onset_to_lip_s@" + thr) if thr else None), fmt(m.get("chord_at_hood_max"), "%.1f"), fmt(m.get("trough_at_hood_max")), fmt(m.get("air_max_pre"), "%.3f"),
                fmt(m.get("hollow_air"), "%.3f"), "ref" if arm == "K0" else ("-" if pa is None else ("PASS" if pa else "fail"))]
        for x, t_ in zip(xs, vals):
            dr.text((x, yy), t_, fill=(GREEN if t_ == "PASS" else (RED if t_ == "fail" else TXT)), font=fnt(13))
        yy += 18
    y0 = max(yy + 10, 300)
    if y0 + nrow * (ph + 14) > Hh:
        im2 = Image.new("RGB", (W, y0 + nrow * (ph + 14) + 10), (247, 247, 244)); im2.paste(im, (0, 0)); im = im2
    for i, arm in enumerate(arms):
        a = anas[arm]
        br = median_breaker(a)
        at = (br or {}).get("hood_max_at")
        R = Run(runs[arm])
        cr = ((D["arms"].get(arm) or {}).get("criteria") or {})
        mk = lambda k: ("" if k not in cr else (" [%s]" % ("ok" if cr[k]["pass_"] else ("fail" if cr[k]["pass_"] is False else "n/a"))))
        lines = ["k%s  t %s s  x_c %s m  eta_c %s m  h(x_c) %s m" % (br["k"] if br else "-", fmt((at or {}).get("t")), fmt((at or {}).get("x_c"), "%.1f"),
                                                                    fmt((at or {}).get("eta_c")), fmt(float(R.depth((at or {}).get("x_c") or 0.0)) if at else None)),
                 "hood %s  lip %s  chord %s deg%s  foot %s  air %s" % (fmt((at or {}).get("hood"), "%.3f"), fmt((at or {}).get("lip"), "%.3f"),
                                                                       fmt((at or {}).get("chord"), "%.1f"), mk("v_no_wall"), fmt((at or {}).get("foot")),
                                                                       fmt((at or {}).get("air"), "%.3f")),
                 "front trough %s eta_c   on->lip %s s%s   hood<=78 %s%s" % (fmt((at or {}).get("trough_d_over_eta")), fmt(((br or {}).get("onset_to_lip_ladder_s") or {}).get(thr) if thr else None), mk("iv_onset_to_lip"),
                                                                              fmt((br or {}).get("hood78"), "%.3f"), mk("i_hood78")),
                 a.get("label") or ""]
        px, py = 14 + (i % cols) * (pw + 2), y0 + (i // cols) * (ph + 14)
        draw_panel(im, R, a, br, at, (px, py, pw - 14, ph), "%s  (%s)  H %.2f m  T %.2f s" % (arm, a["run_id"], a["H"], a["T"]), lines)
    C.guard_out(os.path.dirname(path))
    im.save(path)
    return path


def video(anas, runs, path, slow=2, size=(480, 190)):
    """centre sections of the median breaker of each arm, aligned at each arm's first lip (-1.5 .. +2.5 s), 2 x 4 grid, 0.5x speed."""
    from PIL import Image, ImageDraw
    arms = [a for a in ("K0", "K1", "K2", "K3", "K4", "K5", "A12", "K0p") if a in anas and not (a == "K0p" and runs.get("K0p") == runs.get("K0"))][:8]
    cols = 4
    nrow = int(math.ceil(len(arms) / cols))
    W, Hh = cols * size[0], nrow * (size[1] + 26) + 40
    W += W % 2; Hh += Hh % 2
    prep = []
    for arm in arms:
        a = anas[arm]
        br = median_breaker(a) or {}
        fl = (br.get("first_lip") or {}).get("frame") or br.get("on_f")
        R = Run(runs[arm])
        trk = R.track(int(br.get("on_f") or fl or 1), float(br.get("on_x") or 250.0), int(fl) - 40, int(fl) + 64) if fl else {}
        ec = (br.get("hood_max_at") or {}).get("eta_c") or (br.get("crest_ref_m") or 6.0)
        prep.append((arm, a, br, fl, R, trk, ec))
    ff = C.FFMPEG
    C.guard_out(os.path.dirname(path))
    cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, Hh), "-r", "24", "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    for d in range(-36, 61):
        im = Image.new("RGB", (W, Hh), (247, 247, 244))
        dr = ImageDraw.Draw(im)
        dr.text((10, 8), "K54 strips: centre sections aligned at each arm's first lip  t_rel %+.2f s  (0.5x speed; 2D strips, not the 3D wave)" % (d / FPS),
                fill=TXT, font=fnt(16, True))
        for i, (arm, a, br, fl, R, trk, ec) in enumerate(prep):
            px, py = (i % cols) * size[0], 40 + (i // cols) * (size[1] + 26)
            dr.text((px + 6, py), "%s  k%s  H %.2f" % (arm, br.get("k", "-"), a["H"]), fill=TXT, font=fnt(14, True))
            if not fl:
                continue
            f = int(fl) + d
            xg = trk.get(f)
            if xg is None or f not in R.r2set:
                continue
            try:
                sim, geo = section_rgb(R, f, xg, xg, float(ec), size[0] - 10, size[1] - 10)
                im.paste(sim, (px + 5, py + 22))
            except Exception:
                pass
        b = im.tobytes()
        for _ in range(slow):
            pr.stdin.write(b)
            n += 1
    pr.stdin.close()
    pr.wait()
    return path, n


def verdict(runmap, out_dir=None, do_video=True):
    anas, paths = {}, {}
    for arm, rd in runmap.items():
        if rd is None:
            continue
        od = None if out_dir is None else (out_dir + "/ana_" + arm)
        a, p = load_or_measure(rd, od)
        anas[arm], paths[arm] = a, p
    D = decide(anas)
    od = C.guard_out(out_dir or C.VERDICT_DIR)
    D.update(date=time.strftime("%Y-%m-%d %H:%M:%S"), runs={k: (v.replace(C.REPO + "/", "") if v else None) for k, v in runmap.items()},
             analyses={k: v.replace(C.REPO + "/", "") for k, v in paths.items()},
             plan=C.PLAN_REL, plan_sha256=(C.sha256_file(C.PLAN) if os.path.exists(C.PLAN) else None), plan_sha_ok=C.plan_sha_ok(),
             medians={k: v["medians"] for k, v in anas.items()}, H={k: v["H"] for k, v in anas.items()},
             health={k: v["health"] for k, v in anas.items()},
             tags=dict(verdict="decided by the frozen rule (plan K54 criteria) from measured medians; AI self-assessment, the user judges the look"))
    try:
        D["sheet"] = sheet(anas, runmap, D, od + "/K54_sheet.png")
    except Exception as ex:
        D["sheet_error"] = repr(ex)[:300]
    if do_video:
        try:
            p, n = video(anas, runmap, od + "/K54_sections.mp4")
            D["video"] = p; D["video_frames"] = n
        except Exception as ex:
            D["video_error"] = repr(ex)[:300]
    C.jdump(D, od + "/verdict_K54.json")
    return D, od + "/verdict_K54.json"


# ====================================================================== cli
def parse(argv):
    pos, opt = [], {}
    for a in argv:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opt[k] = v if v else "1"
        else:
            pos.append(a)
    return pos, opt


def main(argv):
    pos, opt = parse(argv[1:])
    if not pos:
        print(__doc__); return 2
    cmd = pos[0]
    if cmd == "measure":
        o, p = measure(pos[1], opt.get("out"))
        print(json.dumps(C.clean(dict(ana=p, run_id=o["run_id"], judged_k=o["judged_k"], medians=o["medians"], health=o["health"],
                                      H_realized=o["inlet"].get("H_realized_m"), wall_s=round(o["wall_s"], 1))), ensure_ascii=False))
        return 0
    if cmd == "calib":
        o, p = calib(pos[1], opt.get("out"), force=bool(opt.get("force")), ana=opt.get("ana"))
        print(json.dumps(C.clean(dict(calibration=p, H_K0=o["H_K0"], pilot_is_K0=o["pilot_is_K0"], h_b_median=o["h_b_median"], why=o["why"],
                                      H_A12=o["H_A12"])), ensure_ascii=False))
        return 0 if o["H_K0"] is not None else 1
    if cmd == "verdict":
        mp = json.load(open(opt["map"], encoding="utf8"))
        D, p = verdict(mp, opt.get("out"), do_video=not opt.get("no-video"))
        print(json.dumps(C.clean(dict(verdict_json=p, verdict=D["verdict"], pick=D.get("pick"), passing=D.get("passing"), validity=D["validity"].get("valid"),
                                      sheet=D.get("sheet"), video=D.get("video"), errors=[D.get(k) for k in ("sheet_error", "video_error") if D.get(k)])),
                         ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
