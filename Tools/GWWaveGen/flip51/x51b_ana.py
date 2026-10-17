# -*- coding: utf-8 -*-
"""FLIP51 X2B': reading of the X2B' 0.5 m run under the X2B frozen plan, with the user's rule Q83 (2026-10-17): every evaluation shows and judges,
CO-EQUALLY, (1) the Unity PRINT-VIEW render at the most print-like instant, (2) the centre section vs the print outline with the print ruler,
(3) the convergence metrics. Progress = convergence better AND print match not worse. (py -3.10 -B; numpy, scipy, PIL.)
2026-10-17 written new (Claude). Read only on every existing tool: x51_ana (judge05 = the frozen plan-E reading: per-period scan / g50-event
instants, e51 metrics, N1, gates G1-G6), x51_video (compare mp4), e51_metrics, g50_table; pv53's output json (written by
Tools/GWWaveGen/flip53/pv53.py, unchanged). In-memory adaptations only (never a file): x51_common.CASES gets the X2B record, x51_common.X_F =
275.25 (the D smoke report and the video's focus marker), x51_ana.GATES G4_side_x_max = 210.25 (the generating side band now ends there),
x51_table.dirfield answers 'X2B' with the X2B field. Writes only under the run folder (e51/, video/, x2b/) or, for --test, Unity/Build/FLIP51/_scratch.

What it adds to x51_ana judge05 (rules frozen in plan_X2B_frozen.json; the numbers below are the single source the plan copies):
  G2_X2B   inlet amplitude: median over the 15 gauges with linear A >= 0.4 m of (FLIP crest median / linear A), t 30-75 s, in [0.90, 1.12].
           The single plan-E gauge (110, 0.5) is reported: its linear A is 0.68 m in X2B (1.05 in X2), near a partial node, and X2's gauges with
           A 0.41-0.64 m read 0.99-1.18 [measured] (X2 all-gauge median 1.007, X1 1.021 [measured]).
  G7       side band generation on the slope (new): first-harmonic amplitude of hf - eta0 (t 42-74 s, every 2nd frame) at x 185 / 195 / 205 m,
           y 100 / 110 / 120 m divided by the table's linear |A|; median in [0.75, 1.15]. X2's generating side band (x 60-175 m, same y) read
           0.78-1.09, median ~0.95 [measured 2026-10-17]. Reference points x 130 / 150 / 165 m reported.
  G7b      (report) the VEX target in the new band: run records info.dir_check, x 200 m, lateral 100 / 120 m, target factor g and the grid
           velocity against the numpy target (slope of u_grid on u_tgt) after t 20 s.
  break    per period the first g50 centre overturning onset (on_x, on_t, on_eta) and its still depth; prediction x_b 282 [273-290] m.
  validity pipeline items: run_complete, G1_table, G2_X2B, G4_no_band_breaking (x <= 210.25 m in the side band), G5_volume, G7_side_band,
           periods_valid (>= 4). G3_recurrence and G6_focus_where_designed are PHYSICS FLAGS (reported; X2, the convergence reference, failed
           both, so they cannot block a comparison with it).
Co-equal verdict (coequal): see COEQ and verdict(); print ruler numbers come from pv53 (per period: the most print-like instant on the
  summit's own track in [t_max - 1.5, t_max + 3.0] s, crest floor 0.6 Hc), convergence numbers from judge05 at its own instants.
usage:
  py -3.10 -B x51b_ana.py judge <run_dir> [--test --out=<scratch dir>]   -> <run>/e51/{screen_E05,judge_E05}.json + <run>/x2b/judge_X2B.json
  py -3.10 -B x51b_ana.py video <run_dir>                                 -> <run>/video/<run>_E_compare.mp4 (x51_video, focus marker 275.25)
  py -3.10 -B x51b_ana.py coequal <run_dir> [--pv53=<json>] [--out=<dir>]   -> <run>/x2b/coequal_X2B.json + report_X2B.png
  py -3.10 -B x51b_ana.py selftest                                        the X2B additions and the verdict on X2 / DM1A (scratch only)
Tags: [measured] [computed] [literature] [guess] [chosen].
"""
import os, sys, json, math, time, glob, shutil, copy, warnings

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
import x51b_common as XB              # noqa: E402
import x51_common as XC               # noqa: E402  read only
import x51_ana as XA                  # noqa: E402  read only (frozen plan-E reading)
import e51_metrics as EM              # noqa: E402  read only (frozen ruler)
import g50_table as TB                # noqa: E402  read only

TOOL = "Tools/GWWaveGen/flip51/x51b_ana.py"
FPS = 24.0
SCRATCH = XC.SCRATCH_PREFIX + "x2b_test"

# ------------------------------------------------------------------ X2B additions to the frozen reading [chosen; reasons in the docstring]
G2B = dict(A_min=0.4, range=[0.90, 1.12], t=[30.0, 75.0],
           calib=dict(X2_median=1.007, X2_range_A_ge_0p4=[0.869, 1.184], X1_median=1.021, tag="measured 2026-10-17 (r6 gauges, t 30-75 s)"))
G7 = dict(new=[[x, y] for x in (185.0, 195.0, 205.0) for y in (100.0, 110.0, 120.0)],
          ref=[[x, y] for x in (130.0, 150.0, 165.0) for y in (100.0, 110.0, 120.0)], t=[42.0, 74.0], every=2, range=[0.75, 1.15],
          calib=dict(X2_generating_x60_175=[0.78, 1.09], X2_median=0.95, tag="measured 2026-10-17 (X2 hf, same rule)"))
G7B = dict(x=200.0, zl_min=100.0, t_min=20.0)
PIPELINE = ("run_complete", "G1_table", "G2_X2B", "G4_no_band_breaking", "G5_volume", "G7_side_band", "periods_valid")
PHYSICS_FLAGS = ("G3_recurrence", "G6_focus_where_designed")

# ------------------------------------------------------------------ references [measured; files read at freeze time and again at verdict time]
REF = dict(
    X2=dict(run="S51X2_D19B_T7_g60s28_dp0p5", miss=1.882398, W50=4.334095, W80=2.639993, W95=0.995923, N1=0.563296, Hc=5.456841, gain=2.53007,
            score3_median=2.367, lip_median=0.0, chord=[20.0, 29.1], back=[9.4, 15.2], width07=[2.96, 4.54], red_n=6, red_miss=0.922692,
            src="Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/e51/judge_E05.json + Unity/Build/FLIP53/pv53/S51X2_D19B_T7_g60s28_dp0p5/pv53_*.json"),
    DM1A=dict(run="DM1A_D19B_T12_th80_dp0p5", miss=4.8555, W50=9.3069, W80=5.6498, W95=2.6772, N1_range=[0.171297, 0.396627], Hc=7.8334,
              score3_median=0.6485, score3=[0.414, 0.721, 0.576, 1.0], lip_median=0.3397, chord=[86.0, 99.0], back=13.8,
              src="Unity/Build/FLIP51/target/baseline.json (e51 'max') + pv53 REF (DM1A pana/best_frames.json) + plan_E calib_E.json N1"),
    PRINT=dict(chord=64.3, foot=0.254, hood=0.186, lip=0.35, back=31.3, width07=1.32, src="g47_video.print_ref (STUDY52 cn)"),
    TARGET=dict(W50=[1.5, 2.6], W80=[0.8, 1.25], W95=[0.4, 0.85], K=[2.0, 4.5], S2=[0.05, 0.35], src="e51_metrics TARGET (user's screenshot read values)"))

COEQ = dict(
    tie_miss=0.30,            # plan E BARS.tie: median core-miss differences below 0.30 are ties [chosen in plan E]
    W50_hold_factor=1.15,     # X2's converged periods n6 / n7 / n10 read W50 3.56-4.33 Hc (spread 18 %) [measured] -> +15 % is 'held' [chosen]
    N1_max=0.65,              # plan E E1 isolation bound [chosen in plan E]
    Hc_min=5.0,               # plan E E2 at 0.5 m [chosen in plan E]
    gain_min=1.8,             # plan E E3 focusing gain [chosen in plan E]
    score3_bar=0.9485,        # pv53 / AM-E2: DM1A median best score3 0.6485 + 0.30 (its own breaker-to-breaker scatter) [measured + chosen]
    lip_min=0.20,             # pv53 / AM-E2: 0.57 x the print's lip 0.35; a plunging lip exists [chosen]
    score3_gain_vs_X2=0.30,   # 'print gain over X2': median best score3 at least 0.30 (DM1A's scatter) below X2's 2.367 [chosen]
)


def levels_text():
    X2, DM = REF["X2"], REF["DM1A"]
    return dict(
        C_BETTER="median core miss <= %.3f (X2 %.3f - tie %.2f), W50 <= %.3f Hc (X2), N1 <= %.2f, Hc >= %.1f m, gain >= %.1f" % (
            X2["miss"] - COEQ["tie_miss"], X2["miss"], COEQ["tie_miss"], X2["W50"], COEQ["N1_max"], COEQ["Hc_min"], COEQ["gain_min"]),
        C_HELD="median core miss <= %.3f (X2 + tie), W50 <= %.3f Hc (X2 x %.2f), N1 <= %.2f, Hc >= %.1f m, gain >= %.1f" % (
            X2["miss"] + COEQ["tie_miss"], X2["W50"] * COEQ["W50_hold_factor"], COEQ["W50_hold_factor"], COEQ["N1_max"], COEQ["Hc_min"],
            COEQ["gain_min"]),
        C_DM1A="median core miss <= %.3f (DM1A e51 'max' %.4f - tie) and W50 < %.3f Hc (DM1A), Hc >= %.1f m" % (
            DM["miss"] - COEQ["tie_miss"], DM["miss"], DM["W50"], COEQ["Hc_min"]),
        C_NONE="none of the above",
        P_OK="(a) median over the periods of the best-instant score3 <= %.4f AND median best lip >= %.2f, AND (b) the same two bars at the "
             "converged summit (the period of the judge's red instant = most converged)" % (COEQ["score3_bar"], COEQ["lip_min"]),
        P_RUN_ONLY="(a) holds but (b) not: the print-like wave is not the converged one",
        P_GAIN="median best score3 <= %.3f (X2 %.3f - %.2f) or median best lip >= %.2f (X2 0.000)" % (
            X2["score3_median"] - COEQ["score3_gain_vs_X2"], X2["score3_median"], COEQ["score3_gain_vs_X2"], COEQ["lip_min"]),
        P_NONE="none of the above",
        verdict=dict(
            INVALID="a pipeline item failed (items: %s): the run does not test X2B'; numbers and views are still shown" % "/".join(
                k.split("_")[0] for k in PIPELINE),
            INCOMPLETE="no Unity print-view render at the most print-like instant: the rule requires it to be SHOWN, so no claim is made",
            PROGRESS_STRICT="P_OK and C_BETTER: convergence better than X2 AND print match not worse than DM1A",
            PROGRESS="P_OK and C_HELD: vs DM1A (the print reference) convergence better and print match not worse; vs X2 (the convergence "
                     "reference) print match better and convergence not worse within the frozen tie band",
            TRADE_OFF="P_OK but convergence below C_HELD: print match reached, X2's convergence lost (not progress)",
            NO_PROGRESS_PRINT="C_HELD or better but not P_OK: as converged as X2, not print-like (flag P_GAIN if it moved toward the print)",
            NO_PROGRESS="neither"))


PRED = dict(x_b=[273.0, 290.0, 282.0], h_b=[6.0, 7.7, 6.9], Hc=[5.2, 5.95, 5.6], W50=[3.6, 4.8, 4.4], W80=[1.9, 3.0, 2.7], miss=[1.0, 2.7, 1.9],
            N1=[0.51, 0.70, 0.62], S2=[0.43, 0.72, 0.56], chord=[40.0, 80.0, None], lip_ge_0p20_chance=0.35, back=[11.0, 16.0, None],
            width07=[2.5, 3.5, None], score3=[0.8, 2.0, None], tags="computed (x51b_screen.py detail) and guess (ruler items); registered before the run")


# ====================================================================== in-memory adaptation of the frozen plan-E reading
_ADAPTED = {}


def adapt():
    """X2B in x51_common.CASES, X_F 275.25, G4 side band x <= 210.25, x51_table.dirfield('X2B'). In memory only; idempotent."""
    if _ADAPTED:
        return _ADAPTED
    XB.register_case()
    _ADAPTED["X_F_before"] = XC.X_F
    XC.X_F = XB.X_F
    _ADAPTED["G4_side_x_max_before"] = XA.GATES["G4_side_x_max"]
    XA.GATES["G4_side_x_max"] = XB.SD_GEN
    import x51_table as XT
    import x51b_table as XBT
    orig = XT.dirfield

    def dirfield(case, x=None):
        if case == XB.CASE:
            return XBT.dirfield(x=x)
        return orig(case, x)
    XT.dirfield = dirfield
    comp_orig = XC.components

    def components(case):
        return comp_orig(XB.BASE_CASE if case == XB.CASE else case)       # X2B uses the X2 set exactly
    XC.components = components
    _ADAPTED.update(X_F_now=XC.X_F, G4_side_x_max_now=XA.GATES["G4_side_x_max"], cases="X2B registered in memory",
                    note="in-memory only (x51_common / x51_ana / x51_table files unchanged)")
    return _ADAPTED


# ====================================================================== X2B additions
def g2_all_gauges(rd, eta0, cfg):
    R = XA.load_r6(rd)
    gl = (cfg.get("dir") or {}).get("gauges_lin") or {}
    tt = R["t"]
    rows = []
    for i, (x, y) in enumerate(R["gxy"]):
        k = "x%g_y%g" % (x, y)
        if k not in gl:
            continue
        A = 0.5 * float(gl[k]["H_lin"])
        e = R["gauge"][:, i] - eta0
        sel = (tt >= G2B["t"][0] - 1e-9) & (tt <= G2B["t"][1] + 1e-9) & np.isfinite(e)
        cr = [w["crest"] for w in XA.waves_zero_down(tt[sel], e[sel])]
        rows.append(dict(x=float(x), y=float(y), A_lin=A, crest_median=float(np.median(cr)) if cr else None,
                         ratio=(float(np.median(cr)) / A) if (cr and A > 0) else None))
    use = [r["ratio"] for r in rows if r["ratio"] is not None and r["A_lin"] >= G2B["A_min"]]
    med = float(np.median(use)) if use else None
    return dict(rows=rows, n_used=len(use), median_ratio=med, range=G2B["range"], A_min=G2B["A_min"], calib=G2B["calib"],
                ok=bool(med is not None and G2B["range"][0] <= med <= G2B["range"][1]),
                rule="median over the gauges with linear A >= %.1f m of (zero-down crest median of hf gauge - eta0, t 30-75 s) / linear A" % G2B["A_min"])


def side_band_check(rd, eta0, cfg):
    H = XA.HF(rd)
    tab = TB.load(cfg["dir"]["npz"])
    fr = [f for f in H.frames() if G7["t"][0] - 1e-9 <= (f - 1) / FPS <= G7["t"][1] + 1e-9][::G7["every"]]
    if len(fr) < 20:
        return dict(ok=False, why="too few hf frames in t %s (%d)" % (G7["t"], len(fr)))
    a, meta = H.get(fr[0])
    xs, yh = XA.axes(meta, a.shape)
    pts = G7["new"] + G7["ref"]
    idx = [(int(np.argmin(np.abs(xs - x))), int(np.argmin(np.abs(yh - y)))) for x, y in pts]
    S = np.full((len(fr), len(pts)), np.nan)
    for k, f in enumerate(fr):
        a, _ = H.get(f)
        for j, (ix, iy) in enumerate(idx):
            S[k, j] = a[iy, ix] - eta0
    t = np.array([(f - 1) / FPS for f in fr]); om = 2 * math.pi / XC.T7
    rows = []
    for j, (x, y) in enumerate(pts):
        e = S[:, j]
        ok = np.isfinite(e)
        e = e[ok] - np.mean(e[ok]) if ok.any() else e
        A1 = float(2 * abs(np.mean(e * np.exp(1j * om * t[ok])))) if ok.sum() > 10 else None
        Al = abs(complex(TB._bilinear(tab, "er", x, y), TB._bilinear(tab, "ei", x, y)))
        rows.append(dict(x=x, y=y, part="new" if [x, y] in G7["new"] else "ref", A1=A1, A_lin=Al, ratio=(A1 / Al) if (A1 is not None and Al > 0) else None,
                         crest_max=float(np.nanmax(S[:, j])) if np.isfinite(S[:, j]).any() else None))
    rn = [r["ratio"] for r in rows if r["part"] == "new" and r["ratio"] is not None]
    rr = [r["ratio"] for r in rows if r["part"] == "ref" and r["ratio"] is not None]
    med = float(np.median(rn)) if rn else None
    return dict(rows=rows, median_new=med, median_ref=float(np.median(rr)) if rr else None, range=G7["range"], calib=G7["calib"],
                ok=bool(med is not None and G7["range"][0] <= med <= G7["range"][1]), frames=[fr[0], fr[-1], len(fr)],
                rule="first-harmonic amplitude (T 7 s) of hf - eta0 at the new generating part of the side band (x 185-205 m, y 100-120 m) / the "
                     "table's linear |A|; median in [0.75, 1.15]")


def vex_band_reading(rd):
    rr = XA.recs(rd)
    xs = []
    for r in rr:
        for d in ((r.get("info") or {}).get("dir_check") or []):
            if float(d.get("t", 0)) < G7B["t_min"]:
                continue
            for q in d.get("rows") or []:
                if abs(float(q["x"]) - G7B["x"]) < 1e-6 and float(q["zl"]) >= G7B["zl_min"] and q.get("u_grid") is not None:
                    xs.append(q)
    if not xs:
        return dict(n=0, note="no dir_check rows at x 200 m, lateral >= 100 m after 20 s")
    ut = np.array([q["u_tgt"] for q in xs]); ug = np.array([q["u_grid"] for q in xs])
    vt = np.array([q["v_tgt"] for q in xs]); vg = np.array([q["v_grid"] for q in xs])
    sl = lambda a, b: float(np.dot(a, b) / max(np.dot(a, a), 1e-12))
    g = np.array([q["g"] for q in xs])
    raw_u = np.where(np.abs(g) > 1e-9, ut / np.where(np.abs(g) > 1e-9, g, 1.0), 0.0)
    return dict(n=len(xs), g_target_factor=[float(g.min()), float(g.max())], in_side=[int(q["in_side"]) for q in xs][:4],
                slope_u=sl(ut, ug), slope_v=sl(vt, vg), slope_u_on_unscaled_target=sl(raw_u, ug),
                corr_u=float(np.corrcoef(ut, ug)[0, 1]) if len(xs) > 2 else None,
                calib=dict(X2=dict(g=0.270, slope_u=3.387, slope_u_on_unscaled_target=0.915, corr_u=0.940), tag="measured 2026-10-17 (X2, x 200 m "
                           "in its blend); X2B expects g = 1 at x 200 m (generating) [computed from the cfg parms]"),
                rule="report: dir_check (g50_run) at x 200 m, lateral 100 / 120 m, t >= 20 s: g = the band target factor from the cfg parms "
                     "(numpy mirror; 1 = generating, X2 0.27 = blend), slope of the FLIP grid velocity on the numpy target and on the unscaled "
                     "linear target")


def depth(x):
    return None if x is None else float(19.0 - max(float(x) - 160.25, 0.0) / 10.0)


def breaks(res):
    ev = res.get("g50_events")
    out = []
    if not isinstance(ev, list):
        return dict(error=str(ev)[:200] if ev else "no g50 events", per_period=[])
    for p in res.get("periods") or []:
        if not p.get("window"):
            continue
        a, b = p["window"]
        e_in = [e for e in ev if a - 1e-9 <= e["on_t"] < b - 1e-9]
        if e_in:
            e = e_in[0]
            out.append(dict(n=p["n"], on_t=e["on_t"], on_x=e["on_x"], on_eta=e["on_eta"], h_b=depth(e["on_x"]),
                            on_eta_over_h=(e["on_eta"] / depth(e["on_x"])) if depth(e["on_x"]) else None, rel_xf=e["on_x"] - XB.X_F))
    xb = [r["on_x"] for r in out]
    return dict(per_period=out, x_b_median=float(np.median(xb)) if xb else None, h_b_median=depth(float(np.median(xb))) if xb else None,
                all_events_x=[float(e["on_x"]) for e in ev][:40], pred=dict(x_b=PRED["x_b"], h_b=PRED["h_b"]))


def conv_level(med, gain):
    X2, DM = REF["X2"], REF["DM1A"]
    miss, W50, N1, Hc = med.get("miss"), med.get("W50"), med.get("N1"), med.get("Hc")
    f = lambda v: v is not None and np.isfinite(v)
    base = bool(f(Hc) and Hc >= COEQ["Hc_min"] and f(N1) and N1 <= COEQ["N1_max"] and gain is not None and gain >= COEQ["gain_min"])
    if base and f(miss) and f(W50) and miss <= X2["miss"] - COEQ["tie_miss"] + 1e-12 and W50 <= X2["W50"] + 1e-12:
        return "C_BETTER"
    if base and f(miss) and f(W50) and miss <= X2["miss"] + COEQ["tie_miss"] + 1e-12 and W50 <= X2["W50"] * COEQ["W50_hold_factor"] + 1e-12:
        return "C_HELD"
    if f(miss) and f(W50) and f(Hc) and miss <= DM["miss"] - COEQ["tie_miss"] + 1e-12 and W50 < DM["W50"] and Hc >= COEQ["Hc_min"]:
        return "C_DM1A"
    return "C_NONE"


# ====================================================================== judge
def judge(rd, out_dir=None, test=False):
    t0 = time.time()
    rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
    adapt()
    case = XB.CASE if not test else (XA.guess_case(rd, XA.load_cfg(rd)) or XB.CASE)
    e51_dir = out_dir + "/e51" if out_dir else None
    res = XA.judge05(rd, case=case, out_dir=e51_dir)
    cfg = XA.load_cfg(rd)
    eta0 = res["eta0"]
    g = res["gates"]
    g["G2_X2B"] = g2_all_gauges(rd, eta0, cfg)
    g["G2_X2B"]["single_gauge_plan_E"] = {k: (g.get("G2_inlet_amplitude") or {}).get(k) for k in ("ratio", "A_lin", "crest_median_m", "ok", "range")}
    try:
        g["G7_side_band"] = side_band_check(rd, eta0, cfg)
    except Exception as ex:
        g["G7_side_band"] = dict(ok=False, error=repr(ex)[:300])
    try:
        g["G7b_vex_band_report"] = vex_band_reading(rd)
    except Exception as ex:
        g["G7b_vex_band_report"] = dict(error=repr(ex)[:300])
    g["G4_no_band_breaking"]["x2b_note"] = "side band read for x <= %.2f m (the X2B generating end; plan E read 180.25 m)" % XA.GATES["G4_side_x_max"]
    failed_pipe = [k for k in PIPELINE if not (g.get(k) or {}).get("ok")]
    flags = [k for k in PHYSICS_FLAGS if not (g.get(k) or {}).get("ok")]
    med = res.get("median") or {}
    el = res.get("eligibility") or {}
    gain = (el.get("E3_focusing_gain") or {}).get("Hc_over_incoming")
    br = breaks(res)
    lev = conv_level(med, gain)
    out = dict(run_id=res["run_id"], run_dir=rd, tool=TOOL, tool_sha256=XB.sha256_file(os.path.abspath(__file__)), date=time.strftime("%Y-%m-%d %H:%M:%S"),
               plan=XB.PLAN_REL, adapted=adapt(), judge_E05=res.get("_path"), eta0=eta0, case=case,
               valid_x2b=not failed_pipe, failed_pipeline=failed_pipe, physics_flags=flags, plan_E_valid=res.get("valid"),
               plan_E_failed=res.get("failed_gates"), judgement_05_plan_E=res.get("judgement_05"),
               convergence=dict(level=lev, miss=med.get("miss"), W50=med.get("W50"), W80=med.get("W80"), W95=med.get("W95"), K=med.get("K"),
                                S2=med.get("S2"), N1=med.get("N1"), Hc=med.get("Hc"), gain=gain, x_pk=med.get("x_pk"), red_instant=res.get("red_instant"),
                                instants_used=res.get("instants_used"), levels=levels_text(), refs=dict(X2=REF["X2"], DM1A=REF["DM1A"])),
               periods=[{k: p.get(k) for k in ("n", "complete", "f", "t", "x_pk", "y_pk", "Hc", "W50", "W80", "W95", "K", "S2", "N1", "miss", "instant",
                                                  "face_deg", "overhang", "back_deg")} for p in res.get("periods") or []],
               breaks=br, gates={k: g.get(k) for k in ("run_complete", "G1_table", "G2_inlet_amplitude", "G2_X2B", "G3_recurrence", "G4_no_band_breaking",
                                                        "G5_volume", "G6_focus_where_designed", "G7_side_band", "G7b_vex_band_report", "periods_valid")},
               seconds=round(time.time() - t0, 1))
    # the judge file that pv53 / f3d51_export read gets the X2B markers too (same content otherwise)
    try:
        jp = res["_path"]
        J = json.load(open(jp, encoding="utf8"))
        J["x2b"] = dict(note="X2B': read by x51b_ana.py with the in-memory adaptations listed in adapted; X2B validity / convergence level in x2b/judge_X2B.json",
                        adapted=adapt(), valid_x2b=out["valid_x2b"], failed_pipeline=failed_pipe, physics_flags=flags, convergence_level=lev,
                        G2_X2B_ok=g["G2_X2B"].get("ok"), G7_ok=(g.get("G7_side_band") or {}).get("ok"))
        XC.jdump(J, jp)
    except Exception as ex:
        out["judge_mark_error"] = repr(ex)[:200]
    od = out_dir or (rd + "/x2b")
    os.makedirs(od, exist_ok=True)
    p = od + "/judge_X2B.json"
    XB.jdump(out, p)
    out["_path"] = p
    return out


def judge_line(o):
    c = o.get("convergence") or {}
    b = o.get("breaks") or {}
    g = o.get("gates") or {}
    f = lambda v, s="%.2f": (s % v) if isinstance(v, (int, float)) and v is not None else str(v)
    return ("valid_x2b %s failed %s flags %s | convergence %s: miss %s W50 %s W80 %s N1 %s Hc %s gain %s (X2 1.88 / 4.33 / 0.56; DM1A 4.86 / 9.31) | "
            "break x %s h_b %s (pred 282 [273-290], 6.9) | G2_X2B %s (%s) G7 %s (%s) G4 kA side %s" % (
                o.get("valid_x2b"), o.get("failed_pipeline"), o.get("physics_flags"), c.get("level"), f(c.get("miss")), f(c.get("W50")),
                f(c.get("W80")), f(c.get("N1")), f(c.get("Hc")), f(c.get("gain")), f(b.get("x_b_median"), "%.1f"), f(b.get("h_b_median")),
                (g.get("G2_X2B") or {}).get("ok"), f((g.get("G2_X2B") or {}).get("median_ratio"), "%.3f"), (g.get("G7_side_band") or {}).get("ok"),
                f((g.get("G7_side_band") or {}).get("median_new"), "%.3f"), f((g.get("G4_no_band_breaking") or {}).get("kA_side_max"), "%.3f")))


# ====================================================================== video (x51_video, unchanged, with the focus marker at 275.25)
def video(rd, out_dir=None, res_path=None, t0=35.0, t1=75.0):
    adapt()
    import x51_video as XV
    rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
    jp = res_path or (rd + "/e51/judge_E05.json")
    return XV.make(rd, res_path=jp if os.path.exists(jp) else None, out_dir=out_dir, t0=t0, t1=t1)


# ====================================================================== the co-equal verdict
def pv53_path(rd):
    rid = os.path.basename(rd.rstrip("/"))
    return XB.REPO + "/Unity/Build/FLIP53/pv53/%s/pv53_%s.json" % (rid, rid)


def print_levels(pv, red_n):
    per = [p for p in (pv.get("periods") or []) if p.get("best")]
    s3 = [p["best"]["score3"] for p in per if p["best"].get("score3") is not None]
    lp = [(p["best"].get("lip") or 0.0) for p in per]
    med_s3 = float(np.median(s3)) if s3 else None
    med_lip = float(np.median(lp)) if lp else None
    run_ok = bool(med_s3 is not None and med_s3 <= COEQ["score3_bar"] + 1e-12 and med_lip is not None and med_lip >= COEQ["lip_min"] - 1e-12)
    cp = [p for p in per if int(p["n"]) == int(red_n)] if red_n is not None else []
    cb = cp[0]["best"] if cp else None
    conv_ok = bool(cb and cb.get("score3") is not None and cb["score3"] <= COEQ["score3_bar"] + 1e-12 and (cb.get("lip") or 0.0) >= COEQ["lip_min"] - 1e-12)
    gain = bool((med_s3 is not None and med_s3 <= REF["X2"]["score3_median"] - COEQ["score3_gain_vs_X2"] + 1e-12)
                or (med_lip is not None and med_lip >= COEQ["lip_min"] - 1e-12))
    lev = "P_OK" if (run_ok and conv_ok) else ("P_RUN_ONLY" if run_ok else ("P_GAIN" if gain else "P_NONE"))
    rows = []
    for p in per:
        b = p["best"]
        rows.append(dict(n=p["n"], frame=b.get("frame"), t=b.get("t"), x_c=b.get("x_c"), eta_c=b.get("eta_c"), h=depth(b.get("x_c")), score3=b.get("score3"),
                         chord=b.get("chord"), foot=b.get("foot"), hood=b.get("hood"), lip=b.get("lip"), back=b.get("back"), width07=b.get("w07"),
                         below_crest_floor=b.get("below_crest_floor"), conv_print_miss=(p.get("conv_print") or {}).get("miss")))
    return dict(level=lev, median_best_score3=med_s3, median_best_lip=med_lip, run_ok=run_ok, converged_period=red_n,
                converged_best=dict(score3=(cb or {}).get("score3"), lip=(cb or {}).get("lip"), chord=(cb or {}).get("chord"), frame=(cb or {}).get("frame"),
                                    x_c=(cb or {}).get("x_c"), eta_c=(cb or {}).get("eta_c")) if cb else None,
                converged_ok=conv_ok, gain_vs_X2=gain, per_period=rows, pv53_verdict=pv.get("verdict"))


def verdict(J, P, render_ok):
    c = (J.get("convergence") or {}).get("level")
    p = P.get("level")
    if not J.get("valid_x2b"):
        v = "INVALID"
    elif not render_ok:
        v = "INCOMPLETE"
    elif p == "P_OK" and c == "C_BETTER":
        v = "PROGRESS_STRICT"
    elif p == "P_OK" and c == "C_HELD":
        v = "PROGRESS"
    elif p == "P_OK":
        v = "TRADE_OFF"
    elif c in ("C_BETTER", "C_HELD"):
        v = "NO_PROGRESS_PRINT"
    else:
        v = "NO_PROGRESS"
    return v, levels_text()["verdict"][v]


def predictions_check(J, P):
    c = J.get("convergence") or {}
    b = J.get("breaks") or {}
    rows = []

    def chk(name, val, rng):
        if val is None or rng is None:
            rows.append(dict(item=name, value=val, range=rng, hit=None)); return
        rows.append(dict(item=name, value=val, range=rng[:2], central=rng[2] if len(rng) > 2 else None, hit=bool(rng[0] <= val <= rng[1])))
    chk("x_b (m)", b.get("x_b_median"), PRED["x_b"])
    chk("h_b (m)", b.get("h_b_median"), PRED["h_b"])
    for k in ("Hc", "W50", "W80", "miss", "N1", "S2"):
        chk(k, c.get(k), PRED[k])
    per = P.get("per_period") or []
    mf = lambda k: float(np.median([r[k] for r in per if r.get(k) is not None])) if any(r.get(k) is not None for r in per) else None
    chk("chord (deg)", mf("chord"), PRED["chord"])
    chk("back (deg)", mf("back"), PRED["back"])
    chk("width07", mf("width07"), PRED["width07"])
    chk("score3 (median best)", P.get("median_best_score3"), PRED["score3"])
    rows.append(dict(item="lip >= 0.20 (median best)", value=P.get("median_best_lip"), chance_pred=PRED["lip_ge_0p20_chance"],
                     hit=None if P.get("median_best_lip") is None else bool(P["median_best_lip"] >= 0.20)))
    return rows


def coequal(rd, pv_path=None, out_dir=None):
    rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
    od = out_dir or (rd + "/x2b")
    os.makedirs(od, exist_ok=True)
    J = XB.jload(od + "/judge_X2B.json") or XB.jload(rd + "/x2b/judge_X2B.json")
    if not J:
        raise SystemExit("no x2b/judge_X2B.json (run x51b_ana.py judge first)")
    pvp = pv_path or pv53_path(rd)
    pv = XB.jload(pvp) or {}
    red_n = ((J.get("convergence") or {}).get("red_instant") or {}).get("n")
    P = print_levels(pv, red_n) if pv else dict(level="P_NONE", error="no pv53 json %s" % pvp, per_period=[])
    un = pv.get("unity") or {}
    pl = un.get("print_like") or {}
    render_ok = bool(pl.get("ok") and pl.get("cprint_still") and os.path.exists(pl["cprint_still"]))
    V = XB.jload(od + "/view/view_X2B.json") or {}
    v, why = verdict(J, P, render_ok)
    res = dict(run_id=os.path.basename(rd), tool=TOOL, tool_sha256=XB.sha256_file(os.path.abspath(__file__)), date=time.strftime("%Y-%m-%d %H:%M:%S"),
               plan=XB.PLAN_REL, plan_sha256=XB.sha256_file(XB.PLAN) if os.path.exists(XB.PLAN) else None, rule_Q83="every evaluation shows and judges "
               "co-equally (1) the Unity print-view render at the most print-like instant, (2) the centre section vs the print outline with the print "
               "ruler, (3) the convergence metrics; progress = convergence better AND print match not worse",
               verdict=v, verdict_text=why, convergence=J.get("convergence"), print_match=P, render=dict(ok=render_ok, print_like=pl.get("cprint_still"),
               front=pl.get("cseat_still"), converged=(un.get("converged") or {}).get("cprint_still"), pv53_json=pvp,
               pv53_tool_sha256=pv.get("tool_sha256"), view=V.get("stills")), valid_x2b=J.get("valid_x2b"), failed_pipeline=J.get("failed_pipeline"),
               physics_flags=J.get("physics_flags"), breaks=J.get("breaks"), predictions=predictions_check(J, P), coeq=COEQ, refs=REF,
               tags="convergence and ruler numbers [measured] records -> [computed]; thresholds [chosen] (reasons in COEQ / plan); the user judges the look")
    res["lines"] = verdict_lines(res)
    p = od + "/coequal_X2B.json"
    XB.jdump(res, p)
    try:
        png = report(res, J, P, pv, V, od)
        res["report_png"] = png
        XB.jdump(res, p)
    except Exception as ex:
        res["report_error"] = repr(ex)[:400]
        XB.jdump(res, p)
    res["_path"] = p
    return res


def _f(v, s="%.2f"):
    return (s % v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v is not None and np.isfinite(v) else "-"


def verdict_lines(res):
    c = res.get("convergence") or {}
    P = res.get("print_match") or {}
    cb = P.get("converged_best") or {}
    return [
        "X2B' co-equal verdict: %s - %s" % (res["verdict"], res["verdict_text"]),
        "convergence %s: median core miss %s (X2 1.88, DM1A 4.86), W50 %s Hc (X2 4.33, DM1A 9.31), N1 %s (<= 0.65), Hc %s m, gain %s" % (
            c.get("level"), _f(c.get("miss")), _f(c.get("W50")), _f(c.get("N1")), _f(c.get("Hc")), _f(c.get("gain"))),
        "print match %s: median best score3 %s (bar 0.9485; X2 2.367, DM1A 0.6485), median lip %s (bar 0.20; DM1A 0.34); at the converged summit n%s: "
        "score3 %s lip %s chord %s deg" % (P.get("level"), _f(P.get("median_best_score3"), "%.3f"), _f(P.get("median_best_lip"), "%.3f"),
                                           P.get("converged_period"), _f(cb.get("score3"), "%.3f"), _f(cb.get("lip"), "%.3f"), _f(cb.get("chord"), "%.0f")),
        "validity: pipeline failed %s; physics flags %s; print-view render %s" % (res.get("failed_pipeline"), res.get("physics_flags"),
                                                                                    "shown" if (res.get("render") or {}).get("ok") else "MISSING")]


# ====================================================================== the combined report image
FONT = "C:/Windows/Fonts/meiryo.ttc"
_FC = {}


def fnt(s):
    from PIL import ImageFont
    if s not in _FC:
        _FC[s] = ImageFont.truetype(FONT, s)
    return _FC[s]


def fit(dr, text, size, width):
    s = size
    while s > 10 and dr.textlength(text, font=fnt(s)) > width:
        s -= 1
    return fnt(s)


def paste(im, path, box, label, sub=None):
    from PIL import Image, ImageDraw
    dr = ImageDraw.Draw(im)
    x0, y0, w, h = box
    dr.text((x0, y0), label, font=fit(dr, label, 17, w), fill=(20, 20, 20))
    y1 = y0 + 26
    if path and os.path.exists(path):
        a = Image.open(path).convert("RGB")
        s = min(w / a.width, (h - 26 - (22 if sub else 0)) / a.height)
        a = a.resize((max(1, int(a.width * s)), max(1, int(a.height * s))), Image.LANCZOS)
        im.paste(a, (x0, y1))
        if sub:
            dr.text((x0, y1 + a.height + 2), sub, font=fit(dr, sub, 13, w), fill=(70, 70, 70))
    else:
        dr.rectangle([x0, y1, x0 + w, y0 + h - 4], outline=(200, 0, 0), width=3)
        dr.text((x0 + 12, y1 + 12), "missing: %s" % (os.path.basename(path) if path else "(not rendered)"), font=fnt(15), fill=(200, 0, 0))


def report(res, J, P, pv, V, od):
    from PIL import Image, ImageDraw
    W = 1920
    im = Image.new("RGB", (W, 1840), (248, 248, 244))
    dr = ImageDraw.Draw(im)
    v = res["verdict"]
    col = (0, 120, 40) if v.startswith("PROGRESS") else ((200, 0, 0) if v in ("INVALID", "INCOMPLETE", "NO_PROGRESS") else (190, 90, 0))
    dr.text((20, 12), "X2B' (%s)  co-equal evaluation (Q83)  %s" % (res["run_id"], res["date"]), font=fnt(30), fill=(20, 20, 20))
    y = 58
    for i, ln in enumerate(res["lines"]):
        dr.text((20, y), ln, font=fit(dr, ln, 21 if i == 0 else 16, W - 40), fill=col if i == 0 else (40, 40, 40))
        y += 32 if i == 0 else 24
    y += 8
    un = (pv.get("unity") or {})
    pl, cv = un.get("print_like") or {}, un.get("converged") or {}
    mp = pv.get("most_print_like") or {}
    st = (V.get("stills") or {})
    # row 1: (1) print view at the most print-like instant | front view same instant | print view at the converged summit
    tw, th = 620, 400
    paste(im, pl.get("cprint_still"), (20, y, tw, th), "(1) print view (Unity), most print-like instant n%s" % mp.get("n"),
          "frame %s, t %s s, crest x %s m, eta_c %s m, score3 %s, lip %s (pv53 camera: option-D pose scaled by Hc)" % (
              mp.get("frame"), _f(mp.get("t")), _f(mp.get("x_c"), "%.1f"), _f(mp.get("eta_c")), _f(mp.get("score3"), "%.3f"), _f(mp.get("lip"), "%.2f")))
    paste(im, pl.get("cseat_still"), (20 + tw + 30, y, tw, th), "front view (Unity), same instant", "shore side on the axis, eye at the crest height")
    conv_img = st.get("print_conv") or cv.get("cprint_still") or (pl.get("cprint_still") if (J.get("convergence") or {}).get("red_instant", {}).get("n") == mp.get("n") else None)
    red = (J.get("convergence") or {}).get("red_instant") or {}
    paste(im, conv_img, (20 + 2 * (tw + 30), y, tw, th), "print view at the converged summit n%s" % red.get("n"),
          "e51 red instant frame %s, miss %s, Hc %s m (%s)" % (red.get("frame"), _f(red.get("miss")), _f(red.get("Hc")),
                                                             "x2view camera, DM1A m/pixel" if st.get("print_conv") else "pv53 camera"))
    y += th + 10
    # row 2: (2) section + print outline at the most print-like instant | at the converged summit
    sw, sh = 940, 470
    paste(im, st.get("section_print_like"), (20, y, sw, sh), "(2) centre section r2 (y 0.5 m, 1:1) + print outline cn, most print-like instant")
    paste(im, st.get("section_converged"), (20 + sw + 20, y, sw, sh), "centre section at the converged summit (e51 red instant)")
    y += sh + 8
    # row 3: (3) table
    c = J.get("convergence") or {}
    rows = [("item", "X2B'", "X2 (conv. ref)", "DM1A (print ref)", "print / target")]
    X2, DM, PR, TG = REF["X2"], REF["DM1A"], REF["PRINT"], REF["TARGET"]
    rows += [("core miss (median)", _f(c.get("miss")), _f(X2["miss"]), _f(DM["miss"]), "0 in band"),
             ("W50 / W80 (Hc)", "%s / %s" % (_f(c.get("W50")), _f(c.get("W80"))), "%s / %s" % (_f(X2["W50"]), _f(X2["W80"])),
              "%s / %s" % (_f(DM["W50"]), _f(DM["W80"])), "%s / %s" % (TG["W50"], TG["W80"])),
             ("N1 / Hc (m) / gain", "%s / %s / %s" % (_f(c.get("N1")), _f(c.get("Hc")), _f(c.get("gain"))), "%s / %s / %s" % (
                 _f(X2["N1"]), _f(X2["Hc"]), _f(X2["gain"])), "%s-%s / %s / -" % (_f(DM["N1_range"][0]), _f(DM["N1_range"][1]), _f(DM["Hc"])),
              "N1 <= 0.65"),
             ("break x / h_b (m)", "%s / %s" % (_f((J.get("breaks") or {}).get("x_b_median"), "%.1f"), _f((J.get("breaks") or {}).get("h_b_median"))),
              "317-322 / <=3.3", "253-260 / 9-9.7", "pred 282 / 6.9"),
             ("score3 median best", _f(P.get("median_best_score3"), "%.3f"), _f(X2["score3_median"], "%.3f"), _f(DM["score3_median"], "%.3f"), "bar 0.9485"),
             ("lip median best", _f(P.get("median_best_lip"), "%.3f"), "0.000", _f(DM["lip_median"], "%.3f"), "%.2f (bar 0.20)" % PR["lip"]),
             ("converged summit score3 / lip", "%s / %s" % (_f((P.get("converged_best") or {}).get("score3"), "%.3f"),
                                                          _f((P.get("converged_best") or {}).get("lip"), "%.2f")), "2.399 / 0.00 (n6)", "-", "bars 0.9485 / 0.20")]
    per = P.get("per_period") or []
    med = lambda k: _f(float(np.median([r[k] for r in per if r.get(k) is not None])), "%.1f") if any(r.get(k) is not None for r in per) else "-"
    rows += [("chord / back (deg)", "%s / %s" % (med("chord"), med("back")), "20-29 / 9-15", "86-99 / 13.8", "%.1f / %.1f" % (PR["chord"], PR["back"])),
             ("width07", med("width07"), "2.96-4.54", "-", "%.2f" % PR["width07"]),
             ("levels", "%s / %s" % (c.get("level"), P.get("level")), "-", "-", "verdict %s" % res["verdict"])]
    widths = [300, 330, 300, 300, 300]
    x0 = 20
    for i, r in enumerate(rows):
        xx = x0
        if i == 0:
            dr.rectangle([x0, y, x0 + sum(widths), y + 26], fill=(228, 228, 222))
        for j, cell in enumerate(r):
            dr.text((xx + 6, y + 3), str(cell), font=fnt(15), fill=(20, 20, 20) if j != 1 else (0, 60, 140))
            xx += widths[j]
        y += 27
    y += 6
    pr = res.get("predictions") or []
    hits = ["%s %s%s" % (q["item"], _f(q.get("value")), "" if q.get("hit") is None else (" ok" if q["hit"] else " OUT")) for q in pr]
    for k in range(0, len(hits), 6):
        dr.text((20, y), ("registered predictions: " if k == 0 else "   ") + "; ".join(hits[k:k + 6]), font=fnt(14), fill=(60, 60, 60)); y += 21
    dr.text((20, y), "levels: C_BETTER / C_HELD / C_DM1A (convergence vs X2 / DM1A, tie 0.30) and P_OK / P_RUN_ONLY / P_GAIN (print ruler vs DM1A bars); "
                     "verdict rule in coequal_X2B.json. AI reading of the ruler; the user judges the look.", font=fnt(14), fill=(60, 60, 60))
    y += 24
    im = im.crop((0, 0, W, min(im.height, y + 10)))
    p = od + "/report_X2B.png"
    im.save(p)
    im.resize((W // 2, im.height // 2)).save(od + "/report_X2B_half.jpg", quality=90)
    return p


# ====================================================================== selftest (X2 / DM1A, scratch only)
def selftest():
    t0 = time.time()
    adapt()
    rd = XB.X2_RUN
    cfg = XA.load_cfg(rd)
    eta0, _ = XA.still_offset(rd)
    out = dict(G2_X2B_on_X2=g2_all_gauges(rd, eta0, cfg), G7_on_X2=side_band_check(rd, eta0, cfg), G7b_on_X2=vex_band_reading(rd))
    J = XB.jload(XB.X2_JUDGE)
    med = J.get("median") or {}
    gain = (J.get("eligibility") or {}).get("E3_focusing_gain", {}).get("Hc_over_incoming")
    out["conv_level_X2"] = conv_level(med, gain)
    pv = XB.jload(XB.X2_PV53) or {}
    P = print_levels(pv, (J.get("red_instant") or {}).get("n"))
    out["print_level_X2"] = {k: P[k] for k in ("level", "median_best_score3", "median_best_lip", "run_ok", "converged_ok", "gain_vs_X2")}
    fake = dict(valid_x2b=True, convergence=dict(level=out["conv_level_X2"]))
    out["verdict_X2_as_if_X2B"] = verdict(fake, P, True)
    pd = XB.jload(XB.DM1A_PV53) or {}
    Pd = print_levels(pd, 2) if pd else None
    out["print_level_DM1A"] = {k: Pd[k] for k in ("level", "median_best_score3", "median_best_lip", "run_ok")} if Pd else None
    base = XB.jload(XB.BASELINE) or {}
    tm = [r for r in (base.get("table_median_judged") or []) if r.get("run") == "DM1A" and r.get("instant") == "max"]
    if tm:
        out["conv_level_DM1A"] = conv_level(dict(miss=tm[0].get("target_miss"), W50=tm[0].get("W50"), N1=0.3, Hc=tm[0].get("Hc")), 2.0)
    out["seconds"] = round(time.time() - t0, 1)
    os.makedirs(SCRATCH, exist_ok=True)
    XB.jdump(out, SCRATCH + "/selftest_x51b_ana.json")
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "judge":
        out_dir = opt.get("out")
        if "test" in opt:
            out_dir = out_dir or (SCRATCH + "/" + os.path.basename(a[1].rstrip("/")))
            if not os.path.abspath(out_dir).replace("\\", "/").lower().startswith(XC.SCRATCH_PREFIX.lower()):
                raise SystemExit("--test writes only under %s" % XC.SCRATCH_PREFIX)
        o = judge(a[1], out_dir=out_dir, test="test" in opt)
        print(judge_line(o))
        print(json.dumps(XC.clean(dict(valid_x2b=o["valid_x2b"], failed=o["failed_pipeline"], flags=o["physics_flags"], level=o["convergence"]["level"],
                                       miss=o["convergence"]["miss"], W50=o["convergence"]["W50"], N1=o["convergence"]["N1"], Hc=o["convergence"]["Hc"],
                                       gain=o["convergence"]["gain"], x_b=o["breaks"].get("x_b_median"), path=o["_path"])), ensure_ascii=False))
    elif a[0] == "video":
        if opt.get("out") and not os.path.abspath(opt["out"]).replace("\\", "/").lower().startswith(XC.SCRATCH_PREFIX.lower()):
            raise SystemExit("--out (tests) must be under %s" % XC.SCRATCH_PREFIX)
        m = video(a[1], out_dir=opt.get("out"), res_path=opt.get("res"), t0=float(opt.get("t0", 35.0)), t1=float(opt.get("t1", 75.0)))
        print(json.dumps(XC.clean(dict(ok=bool(m.get("path") or m.get("mp4")), path=m.get("path") or m.get("mp4"), red_instant=m.get("red_instant"))),
                         ensure_ascii=False, default=str))
    elif a[0] == "coequal":
        r = coequal(a[1], pv_path=opt.get("pv53"), out_dir=opt.get("out"))
        for ln in r["lines"]:
            print(ln)
        print(json.dumps(XC.clean(dict(verdict=r["verdict"], conv=(r.get("convergence") or {}).get("level"), print=(r.get("print_match") or {}).get("level"),
                                       render=(r.get("render") or {}).get("ok"), report=r.get("report_png"), err=r.get("report_error"), path=r["_path"])),
                         ensure_ascii=False))
    elif a[0] == "selftest":
        o = selftest()
        print(json.dumps(XC.clean({k: v for k, v in o.items() if k not in ("G2_X2B_on_X2", "G7_on_X2")}), ensure_ascii=False, default=str))
        print(json.dumps(XC.clean(dict(G2=o["G2_X2B_on_X2"]["median_ratio"], G2_ok=o["G2_X2B_on_X2"]["ok"], G7_new=o["G7_on_X2"]["median_new"],
                                       G7_ref=o["G7_on_X2"]["median_ref"])), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
