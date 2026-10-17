# -*- coding: utf-8 -*-
"""FLIP52S2 plan DFG-S-E140: reading of the optional 0.5 m pipeline check (pipeline gates only) and of the 0.5 m run under the FROZEN plan
rules, per group of the period P = 28 s (the D-style judge: plan E D rule for the 'max' instant), and the CO-EQUAL verdict (print view + print
ruler + convergence at the judge's instant AND at the most print-like instant) after pv53 (py -3.10 -B; numpy, scipy). 2026-10-18 written new
(Claude) by adapting flip52s/g52s_ana.py (DFG-S, frozen, not edited). Read only on every run folder; writes only <run>/g52s2/ and the pv53 alias
<run>/g52/judge_DFG.json (or the session scratchpad given with --out, for tests on runs of other campaigns). Imports READ ONLY: flip51/e51_metrics
(frozen ruler), flip52/g52_ana (generic readers: Blocks, records, still offset, r6, harmonic fit, the r2 / r4 lip detector of AM-DFG1, G5),
flip53/pv53 (only for the fallback when pv53's own json is missing).

Definitions (plan_DFGS2_frozen.json; numbers in GROUP / GATES / ELIG / DEC / COEQ / COEQ_PL below, compared with the plan by `selftest`);
everything as DFG-S except the items marked NEW:
  eta0      the run's online still offset (run record info.still_offset_online: median top-surface height over x 60-205 m, t 0.5-1.5 s)
  groups    n = 1, 2, 3 with t_fn = 48 + 28 (n - 1) s; window [t_fn - 8, t_fn + 6] s.
            'conv'  = the converged crest: the largest Hc of the 3x3-median hf - eta0 over x 90-200 m, |y| <= 65 m in [t_fn - 8, t_fn + 2] s
            'onset' = the first overturning lip on the centre section r2 (AM-DFG1 lip test) at x 90-205 m in the window
            'max'   = (plan E D rule) if an onset: argmax Hc in [on_f - 3 s, on_f + 1.5 s], summit in x [on_x - 60, on_x + 35] m; else 'conv'
            convergence metrics = e51 hf_metrics (rows y > 65 m NaN) at 'max'; core miss = score_vs_target; N1, Nt, c_in60, plunge flags as DFG-S.
  gates A   G1 table + build + precheck; G2f harmonic fit per frequency at x 60 m, y 0.5/15/30/45/60 m over t 32-88 s (fit referenced to t_f
            48 s), ranges RELATIVE to DFG-2's measured 0.5 m realisation (DFG-S rule); G3P recurrence of the 'conv' summits (28 +- 1.5 s, x
            spread <= 20 m, Hc max/min <= 1.25); G4 kp x crest <= 0.40 from t 30 s in the inlet band (x <= 50 m, all y 0-140 m) and the
            generating side-band CORE (sd0 110 <= y <= W - 7.5 = 132.5 m, x <= 180 m; the DFG-S text with this tank's sd0 and W), no r2 lip at
            x < 60 m; reported beside it: the outer-wall strip y > 132.5 m, the full band y >= 110 m and (NEW, report) the free lateral strip
            y 65-110 m, x <= 180 m (the off-axis secondary focus moves there at W 140); G5 volume <= 2 %; G6 (NEW window) 'conv' at x 95-175 m,
            |y| <= 10 m, t in [t_fn - 5, t_fn + 2] s, Hc >= 5.87 m (= 0.68 x the linear design crest 8.635 m at x_f, the plan E / DFG-S rule;
            design (a): FLIP's first break x 108-128 m at t_rel -2.9 .. -1.5 s [calibrated]); run complete, 3 groups.
  eligibility E1 N1 <= 0.65, E1t Nt <= 0.75, E2 Hc('max') >= 5.0 m, E3 Hc / c_in60 >= 1.8 (medians over the groups) (= DFG-S)
  decision  (convergence) bar = min(2.8, best valid 0.5 m median core miss - 0.5) over DF1A 3.3 and the valid plan E X2 / X1, DFG-2, DFG-2B,
            X2B', DFG-S (NEW in the list; its 1.27 makes the bar 0.77) and DFG-2B-E 0.5 m runs (read at analysis time); NEW_BEST_SHAPE (valid,
            eligible, miss <= bar), TARGET_BAND (miss <= 0.5), JET_REGIME_SEEN, NO_GAIN / NOT_ELIGIBLE; physics flags as DFG-S.
  co-equal  (after pv53) PROGRESS iff ALL of
              (1) the Unity print view was rendered at the most print-like instant (pv53),
              (2) the print match is ok by the AM-DFG2 rule (median best-instant score3 <= 0.9485 and median best-instant lip >= 0.20),
              (3a) the convergence decision at the judge's 'max' instants is NEW_BEST_SHAPE or TARGET_BAND,
              (3b) NEW co-requirement: convergence measured AT THE MOST PRINT-LIKE INSTANT of each group (pv53's best frame per group; e51
                   hf_metrics + score_vs_target, xwin [x_c - 60, x_c + 35] m, rows y > 65 m NaN, the judge's eta0; >= 2 groups): the median
                   'print-like miss' <= bar_pl = min(2.8, best valid earlier print-like median miss - 0.5) (the convergence bar rule applied to
                   the print-like instant; earlier values read from the pv53 jsons at analysis time; at freeze [measured]: X2B' 2.75 (valid
                   by its plan) -> bar_pl 2.25; DFG-S 4.36; DFG-2 2.24, X2 2.47, X1 2.80 are invalid by their own plans and not used).
            Reported beside it: SAME_INSTANT_NEW_BEST (print-like miss <= the convergence bar), PRINT_BETTER_THAN_DM1A (median best score3 < 0.6485,
            lip >= 0.20). A run without the print-view package is INCOMPLETE, never progress. Every judge / verdict carries the Q84 energy
            statement ('equal spectral energy (Q84)' and the in-tank ratios).
usage:
  py -3.10 -B g52s2_ana.py pcheck <run_dir> [--out=<dir>]         -> <run>/g52s2/pcheck_DFGS2.json (pipeline only)
  py -3.10 -B g52s2_ana.py judge <run_dir> [--out=<dir>]          -> <run>/g52s2/judge_DFGS2.json (+ <run>/g52/judge_DFG.json for pv53)
  py -3.10 -B g52s2_ana.py coequal <run_dir> [--pv=<pv53 json>] [--out=<dir> --judge=<json> (tests)]  -> <run>/g52s2/coequal_DFGS2.json
  py -3.10 -B g52s2_ana.py plrefs                                 the print-like-instant references and bar_pl (read only; json to stdout)
  py -3.10 -B g52s2_ana.py dfgbe [<run_dir>]                      the pre-launch read of DFG-2B-E (read only; json to stdout)
  py -3.10 -B g52s2_ana.py g4split <run_dir>                      G4 per region of any DFG-tank run (read only; json to stdout)
  py -3.10 -B g52s2_ana.py selftest                               frozen numbers vs the plan, synthetic checks (writes nothing)
Tags: [measured] [computed] [guess] [chosen].
"""
import os, sys, json, math, glob, time, warnings

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
from scipy import ndimage as ndi      # noqa: E402
import g52s2_common as GC              # noqa: E402
for _p in (GC.TOOLS51, GC.TOOLS52):
    if _p not in sys.path:
        sys.path.append(_p)
import e51_metrics as EM              # noqa: E402  frozen ruler (read only)
import g52_ana as GA52                # noqa: E402  generic readers (read only)

FPS = 24.0
E51_SHA = "91a2f0417f6f979cd1649e5bd0fc007d558722b005ac92142454c87be658e8ff"
PV53 = GC.REPO + "/Tools/GWWaveGen/flip53/pv53.py"
PV53_OUT = GC.REPO + "/Unity/Build/FLIP53/pv53"
GROUP = dict(win=GC.GROUP_WIN, conv_end=2.0, scan_x=GC.SCAN_X, ymask=GC.INTERIOR_Y, onset_x=GC.ONSET_X, onset_back_s=3.0, onset_fwd_s=1.5,
             onset_xwin=(-60.0, 35.0), Nt_half=14.0, Nt_excl=3.5, Nt_x=GC.INTERIOR_X, Nt_x_report=(60.0, 160.0), plunge_dt=(-1.0, 4.0),
             plunge_dx=30.0, face_edge_x=GC.X_EDGE + 10.0, prebreak_dt_s=0.5)
N1DEF = dict(win_m=15.0, x=list(GC.INTERIOR_X), ymax=GC.INTERIOR_Y, rmax=100.0, rex_Hc=4.0)
GATES = dict(G2f_x=60.0, G2f_y=list(GC.GAUGE_Y), G2f_nuisance=(6, 10), G2f_t_main=(32.0, 88.0),
             G2f_phase_0p5=0.35, G2f_floor_0p5=0.60, G2f_margin_0p5=0.10, G2f_hi_0p5=1.12,
             G2f_fallback_0p5={3: (0.85, 1.12), 4: (0.85, 1.12), 5: (0.80, 1.12)},
             G3P_P=GC.P_S, G3P_tol=1.5, G3P_xspread=20.0, G3P_Hc_ratio=1.25,
             G4_kA=0.40, G4_t0=30.0, G4_inlet_x=GC.IN_X1, G4_side_y=GC.SD0, G4_side_y1=GC.SD_CORE_Y1, G4_side_x=GC.SD_GEN, G4_lip_x=60.0,
             G5_max=0.02, G6_x=(95.0, 175.0), G6_y=10.0, G6_t=(-5.0, 2.0), G6_Hc=5.87,
             pc_still_t=(0.5, 1.5), pc_still_flat_x=(60.0, 100.0), pc_still_shelf_x=(155.0, 205.0), pc_still_diff_max=0.05, pc_still_abs_max=0.15,
             pc_wave_t=(6.0, 10.0), pc_wave_ratio=(0.33, 3.0), pc_wave_delay_s=1.5, pc_eta0_abs_max=0.25)
G2F_RULE = ("per frequency n: R_n = sum|A_fit| / sum|A_lin| at the five gauges (x 60 m, t 32-88 s, fit referenced to t_f 48 s); pass if "
            "max(0.60, R_n(DFG-2 0.5 m measured) - 0.10) <= R_n <= 1.12 and |phase| <= 0.35 rad. DFG-2 reference: "
            "Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/judge_DFG.json G2f (n3 1.048, n4 0.973, n5 0.788; same gauges, window, table "
            "convention, VEX and dp). If the reference is missing: the DFG-2 frozen ranges. The step's face reflection (<= 5 % per frequency, "
            "screen) is inside the margin. (= DFG-S; DFG-S measured n3 1.031, n4 0.949, n5 0.791)")
DFG_REF = GC.REPO + "/Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/judge_DFG.json"
ELIG = dict(N1_max=0.65, Nt_max=0.75, Hc_min=5.0, gain_min=1.8)
DEC = dict(bar_cap=2.8, bar_margin=0.5, DF1A_miss=3.3, target_band=0.5, jet_ratio=1.30, jet_groups=2, linear_crest=GC.A_SUM, plunge_groups=2)
BEST_RUNS = {"X2": dict(judge=GC.REPO + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/e51/judge_E05.json"),
             "X1": dict(judge=GC.REPO + "/Unity/Build/FLIP51/runs/S51X1_D19B_T7_l60d15_dp0p5/e51/judge_E05.json"),
             "DFG2": dict(judge=GC.REPO + "/Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/judge_DFG.json"),
             "DFG2B": dict(judge=GC.REPO + "/Unity/Build/FLIP52B/runs/DFG2B_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json"),
             "X2B": dict(judge=GC.REPO + "/Unity/Build/FLIP51/runs/S51X2B_D19B_T7_g60s28_xf275_dp0p5/e51/judge_E05.json",
                         valid_file=GC.REPO + "/Unity/Build/FLIP51/runs/S51X2B_D19B_T7_g60s28_xf275_dp0p5/x2b/judge_X2B.json", valid_key="valid_x2b"),
             "DFGS": dict(judge=GC.DFGS_RUN + "/g52s/judge_DFGS.json"),
             "DFGB2E": dict(judge=GC.REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json")}
COEQ = dict(score3_bar=0.9485, score3_DM1A_median=0.6485, tol=0.30, lip_min=0.20, conv_outcomes=["NEW_BEST_SHAPE", "TARGET_BAND"],
            print_ref=dict(back_deg_07_09=31.3, back_band=[29.0, 38.0], width07=1.32, width07_band=[1.02, 1.42], lip=0.35, chord_deg=64.3, hood=0.186),
            source="AM-DFG2 / AM-DFG2a (Unity/Build/FLIP52/plan/amendments.jsonl) applied unchanged (as DFG-S); pv53 rule (Tools/GWWaveGen/flip53/pv53.py)")
# NEW co-requirement (plan DFG-S-E140, frozen before any FLIP52S2 run): convergence also AT THE MOST PRINT-LIKE INSTANT (DFG-S lesson: converged
# instant miss 1.27, but at its most print-like instant (the curl, ~2 s later) the crest had spread: miss 4.55 / 4.36 / 4.28 [measured, pv53])
PL_REFS = {"DFGS": dict(pv53=PV53_OUT + "/DFGS_step3h6_xf145_dp0p5/pv53_DFGS_step3h6_xf145_dp0p5.json", judge=GC.DFGS_RUN + "/g52s/judge_DFGS.json"),
           "DFGB2E": dict(pv53=PV53_OUT + "/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json",
                          judge=GC.REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json"),
           "DFG2": dict(pv53=PV53_OUT + "/DFG2_flat20_P28_dp0p5/pv53_DFG2_flat20_P28_dp0p5.json", judge=BEST_RUNS["DFG2"]["judge"]),
           "X2": dict(pv53=PV53_OUT + "/S51X2_D19B_T7_g60s28_dp0p5/pv53_S51X2_D19B_T7_g60s28_dp0p5.json", judge=BEST_RUNS["X2"]["judge"]),
           "X1": dict(pv53=PV53_OUT + "/S51X1_D19B_T7_l60d15_dp0p5/pv53_S51X1_D19B_T7_l60d15_dp0p5.json", judge=BEST_RUNS["X1"]["judge"]),
           "X2B": dict(pv53=PV53_OUT + "/S51X2B_D19B_T7_g60s28_xf275_dp0p5/pv53_S51X2B_D19B_T7_g60s28_xf275_dp0p5.json",
                       judge=BEST_RUNS["X2B"]["judge"], valid_file=BEST_RUNS["X2B"]["valid_file"], valid_key="valid_x2b")}
COEQ_PL = dict(cap=2.8, margin=0.5, min_groups=2, xwin_rel=(-60.0, 35.0), ymax=GC.INTERIOR_Y, DFGS_measured=[4.5498, 4.3594, 4.2794],
               DFGS_median=4.3594, DM1A_best_report=6.4673,
               rule="median over the groups of the e51 core miss at pv53's most print-like frame of each group (xwin [x_c - 60, x_c + 35] m, rows "
                    "y > 65 m NaN, the judge's eta0; >= 2 groups) <= bar_pl = min(2.8, best valid earlier print-like median miss - 0.5); earlier "
                    "values from the pv53 jsons (periods[].conv_print.miss) of the runs valid by their own plans, read at analysis time")
REPORT_KEYS = ["Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "ring_p90", "ring_mean", "Lx50", "Lx70",
               "A50", "FWHM_excess", "c_side_6Hc", "W50_tr", "H_front_row", "Hs", "face_deg", "concavity", "overhang", "back_deg", "miss", "N1", "Hc_raw"]
Blocks = GA52.Blocks
recs = GA52.recs
load_cfg = GA52.load_cfg
still_offset = GA52.still_offset
load_r6 = GA52.load_r6
axes = GA52.axes
interp2 = GA52.interp2
masked = GA52.masked
harmonic_fit = GA52.harmonic_fit
r2_lips = GA52.r2_lips
r4_lips = GA52.r4_lips
med = GA52.med
gate_G5 = GA52.gate_G5
REP_PTS = ((190.0, 0.5), (200.0, 0.5), (190.0, 30.0), (200.0, 30.0))


def foci(cfg):
    a = cfg.get("analysis") or {}
    return [float(v) for v in (a.get("foci_s") or GC.FOCI)]


# ====================================================================== the per-frame pass
def pass_frames(H, eta0, t_lo, t_hi, kp, depth=None):
    """per hf frame: scan / interior crests, c60, band steepness per region, gauges, centre crest, levels. depth(x) = the run's still depth
    (default: the DFG-S step) for the local-k report."""
    depth = depth or GC.step_depth
    fr = [f for f in H.frames() if t_lo - 1e-9 <= (f - 1) / FPS <= t_hi + 1e-9]
    out = dict(f=[], t=[], Hc=[], x=[], y=[], Hn=[], xn=[], yn=[], Hr=[], c60=[], kA_in=[], kA_core=[], kA_wall=[], kA_full=[], kA_core_loc=[],
               full_at=[], kA_free=[], free_at=[], g2=[], rep=[], xc0=[], ec0=[], lvl_flat=[], lvl_shelf=[], lvl_exit=[])
    key = None
    for f in fr:
        a, meta = H.get(f)
        e = EM.median3(a) - eta0
        xs, yh = axes(meta, e.shape)
        if key != (e.shape, float(meta["x0"]), float(meta["z0"])):
            key = (e.shape, float(meta["x0"]), float(meta["z0"]))
            rowin = yh <= GC.INTERIOR_Y + 1e-9
            scan = rowin[:, None] & ((xs >= GROUP["scan_x"][0]) & (xs <= GROUP["scan_x"][1]))[None, :]
            ntr = rowin[:, None] & ((xs >= GROUP["Nt_x"][0]) & (xs <= GROUP["Nt_x"][1]))[None, :]
            ntr2 = rowin[:, None] & ((xs >= GROUP["Nt_x_report"][0]) & (xs <= GROUP["Nt_x_report"][1]))[None, :]
            inl = np.zeros(e.shape, bool); inl[:, xs <= GATES["G4_inlet_x"] + 1e-9] = True
            xsd = xs <= GATES["G4_side_x"] + 1e-9
            core = np.zeros(e.shape, bool); core[np.ix_((yh >= GATES["G4_side_y"] - 1e-9) & (yh <= GATES["G4_side_y1"] + 1e-9), xsd)] = True
            wall = np.zeros(e.shape, bool); wall[np.ix_(yh > GATES["G4_side_y1"] + 1e-9, xsd)] = True
            full = np.zeros(e.shape, bool); full[np.ix_(yh >= GATES["G4_side_y"] - 1e-9, xsd)] = True
            free = np.zeros(e.shape, bool); free[np.ix_((yh > GC.INTERIOR_Y + 1e-9) & (yh < GATES["G4_side_y"] - 1e-9), xsd)] = True
            kloc = GC.kdisp(2 * math.pi / GC.TP, np.maximum(depth(xs), 0.05))[None, :] * np.ones((len(yh), 1))
            i0 = int(np.clip(np.searchsorted(xs, 60.0) - 1, 0, len(xs) - 2)); w60 = (60.0 - xs[i0]) / (xs[i0 + 1] - xs[i0])
            cx = (xs >= GC.ONSET_X[0]) & (xs <= GC.ONSET_X[1])
            fl = rowin[:, None] & ((xs >= 60.0) & (xs <= 100.0))[None, :]
            sh = rowin[:, None] & ((xs >= 155.0) & (xs <= 205.0))[None, :]
            ex = rowin[:, None] & ((xs >= 190.0) & (xs <= 200.0))[None, :]
        for msk, kk in ((scan, ("Hc", "x", "y")), (ntr, ("Hn", "xn", "yn")), (ntr2, ("Hr", None, None))):
            v = np.where(msk, e, np.nan)
            if np.isfinite(v).any():
                j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
                out[kk[0]].append(float(v[iy, ix]))
                if kk[1]:
                    out[kk[1]].append(float(xs[ix])); out[kk[2]].append(float(yh[iy]))
            else:
                out[kk[0]].append(np.nan)
                if kk[1]:
                    out[kk[1]].append(np.nan); out[kk[2]].append(np.nan)
        line = (1 - w60) * e[:, i0] + w60 * e[:, i0 + 1]
        out["c60"].append(float(np.nanmax(np.where(rowin, line, np.nan))) if np.isfinite(line[rowin]).any() else np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            out["kA_in"].append(float(kp * np.nanmax(np.where(inl, e, np.nan))))
            out["kA_core"].append(float(kp * np.nanmax(np.where(core, e, np.nan))))
            out["kA_wall"].append(float(kp * np.nanmax(np.where(wall, e, np.nan))) if wall.any() else np.nan)
            vf = np.where(full, e, np.nan)
            if np.isfinite(vf).any():
                jf = int(np.nanargmax(vf)); iyf, ixf = np.unravel_index(jf, vf.shape)
                out["kA_full"].append(float(kp * vf[iyf, ixf])); out["full_at"].append([float(xs[ixf]), float(yh[iyf])])
            else:                                # (a record narrower than this layout: tests on other runs only)
                out["kA_full"].append(np.nan); out["full_at"].append([np.nan, np.nan])
            if free.any() and np.isfinite(np.where(free, e, np.nan)).any():
                vr_ = np.where(free, e, np.nan)
                jr = int(np.nanargmax(vr_)); iyr, ixr = np.unravel_index(jr, vr_.shape)
                out["kA_free"].append(float(kp * vr_[iyr, ixr])); out["free_at"].append([float(xs[ixr]), float(yh[iyr])])
            else:
                out["kA_free"].append(np.nan); out["free_at"].append([np.nan, np.nan])
            out["kA_core_loc"].append(float(np.nanmax(np.where(core, e * kloc, np.nan))))
            out["lvl_flat"].append(float(np.nanmean(np.where(fl, e, np.nan))))
            out["lvl_shelf"].append(float(np.nanmean(np.where(sh, e, np.nan))))
            out["lvl_exit"].append(float(np.nanmean(np.where(ex, e, np.nan))))
        r0 = np.where(cx, e[0], np.nan)
        if np.isfinite(r0).any():
            j0 = int(np.nanargmax(r0)); out["xc0"].append(float(xs[j0])); out["ec0"].append(float(r0[j0]))
        else:
            out["xc0"].append(np.nan); out["ec0"].append(np.nan)
        out["g2"].append([interp2(e, xs, yh, GATES["G2f_x"], y) for y in GATES["G2f_y"]])
        out["rep"].append([interp2(e, xs, yh, x, y) for x, y in REP_PTS])
        out["f"].append(int(f)); out["t"].append((f - 1) / FPS)
    o = {k: np.asarray(v, float) for k, v in out.items()}
    o["f"] = o["f"].astype(int)
    return o


# ====================================================================== metrics of one frame
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
        return dict(N1=0.0, at=None, n_candidates=0)
    i = int(np.argmax(np.where(pk, e, -99.0)))
    return dict(N1=float(e.flat[i] / Hc), at=[float(XX.flat[i]), float(YY.flat[i])], dist_m=float(r.flat[i]), n_candidates=int(pk.sum()))


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


def centre_shape(row, xs, i_pk):
    """centre-row shape around the crest at index i_pk (= flip52s/dfgs_screen.centre_shape, the screen's pre-break ruler): width at 0.7 eta_c
    (/eta_c), back angle between 0.7 and 0.9 eta_c (rear face, deg), face chord 0.1-0.5 eta_c (front, deg), front foot 0.1 eta_c (/eta_c).
    Pre-breaking surface only (the hf top surface cannot show an overhang): REPORT, never a gate."""
    ec = float(row[i_pk])
    if not np.isfinite(ec) or ec <= 0.3:
        return None

    def cross(level, direction):
        i = i_pk
        while 0 < i < len(row) - 1 and row[i] >= level:
            i += direction
        if row[i] >= level:
            return None
        a, b = row[i], row[i - direction]
        f = (level - a) / (b - a) if b != a else 0.0
        return float(xs[i] + f * (xs[i - direction] - xs[i]))

    out = dict(eta_c=ec, x_c=float(xs[i_pk]))
    f07 = cross(0.7 * ec, +1); b07 = cross(0.7 * ec, -1); b09 = cross(0.9 * ec, -1)
    f01 = cross(0.1 * ec, +1); f05 = cross(0.5 * ec, +1)
    if f07 is not None and b07 is not None:
        out["w07"] = (f07 - b07) / ec
    if b07 is not None and b09 is not None and b09 > b07:
        out["back_deg"] = math.degrees(math.atan2(0.2 * ec, b09 - b07))
    if f01 is not None and f05 is not None and f01 > f05:
        out["chord_deg"] = math.degrees(math.atan2(0.4 * ec, f01 - f05))
    if f01 is not None:
        out["foot"] = (f01 - float(xs[i_pk])) / ec
    return out


def centre_shape_at(H, f, eta0, x_hint=None):
    """centre-row shape (median of hf rows y 0.5-2.5 m, 1-D 3-point median) of frame f around the centre crest in x 90-205 m."""
    a, meta = H.get(f)
    if a is None:
        return None
    xs, yh = axes(meta, a.shape)
    row = np.median(np.asarray(a[0:3, :], float), axis=0) - eta0
    row = ndi.median_filter(row, size=3, mode="nearest")
    m = (xs >= GC.ONSET_X[0]) & (xs <= GC.ONSET_X[1])
    if x_hint is not None:
        m &= np.abs(xs - x_hint) <= 30.0
    if not m.any():
        return None
    i = int(np.argmax(np.where(m, row, -9.0)))
    return centre_shape(row, xs, i)


def iribarren(Hb, T, slope):
    L0 = GC.G * T * T / (2 * math.pi)
    return slope / math.sqrt(max(Hb, 1e-6) / L0)


# ====================================================================== groups
def group_rows(rd, H, R2, R4, PF, eta0, t_end, fo):
    rows = []
    avail = set(H.frames())
    for n, tfn in enumerate(fo, 1):
        a, b = tfn + GROUP["win"][0], tfn + GROUP["win"][1]
        row = dict(n=n, t_fn=tfn, window=[a, b])
        if b > t_end + 1e-9:
            row.update(complete=False, why="window beyond the record end %.2f s" % t_end); rows.append(row); continue
        sel = (PF["t"] >= a - 1e-9) & (PF["t"] <= tfn + GROUP["conv_end"] + 1e-9) & np.isfinite(PF["Hc"])
        if not sel.any():
            row.update(complete=False, why="no hf frames in the window"); rows.append(row); continue
        idx = np.where(sel)[0]
        i = int(idx[np.argmax(PF["Hc"][idx])])
        conv = dict(f=int(PF["f"][i]), t=float(PF["t"][i]), Hc=float(PF["Hc"][i]), x=float(PF["x"][i]), y=float(PF["y"][i]))
        row.update(complete=True, conv=conv)
        selw = (PF["t"] >= a - 1e-9) & (PF["t"] <= b + 1e-9)
        fw = [int(f) for f in PF["f"][selw]]
        lips = r2_lips(R2, eta0, fw, GROUP["onset_x"][0], GROUP["onset_x"][1])
        row["onset"] = dict(frame=lips[0][0], t=(lips[0][0] - 1) / FPS, x=lips[0][1], h=GC.h_of(lips[0][1])) if lips else None
        r4f = set(R4.frames())
        l4 = r4_lips(R4, eta0, [f for f in fw if f in r4f], GROUP["onset_x"][0], GROUP["onset_x"][1], ymax=GC.INTERIOR_Y) if r4f else []
        row["onset_r4"] = dict(frame=l4[0][0], t=(l4[0][0] - 1) / FPS, x=l4[0][1], y=l4[0][2]) if l4 else None
        f_use = conv["f"]; xwin = tuple(GROUP["scan_x"]); inst = "conv (no r2 onset in the window): scan max x 90-200 m, |y| <= 65 m in [t_fn - 8, t_fn + 2]"
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
                f_use = best[1]; xwin = xw
                inst = "onset rule: r2 lip at t %.2f s, x %.1f m -> e51 max in [on - 3 s, on + 1.5 s], x [on_x - 60, on_x + 35]" % ((on_f - 1) / FPS, on_x)
        m = frame_full(rd, H, f_use, eta0, xwin)
        if not m or "W50" not in m:
            row.update(complete=False, why="no crest metrics at frame %d" % f_use); rows.append(row); continue
        row.update({k: m.get(k) for k in REPORT_KEYS if k in m})
        row.update(f=int(f_use), t=(f_use - 1) / FPS, instant=inst, xwin=list(xwin), W_curve=m.get("W_curve"), W_censored=m.get("W_censored"),
                   miss_per=m.get("miss_per"), N1_detail=m.get("N1_detail"), h_at_pk=GC.h_of(m["x_pk"]))
        mc = frame_full(rd, H, conv["f"], eta0, tuple(GROUP["scan_x"])) if conv["f"] != f_use else m
        row["conv_metrics"] = {k: (mc or {}).get(k) for k in ("Hc", "x_pk", "y_pk", "W50", "W80", "W95", "K", "S2", "miss", "N1")}
        row["conv"]["h"] = GC.h_of(conv["x"]); row["conv"]["Hc_over_h"] = conv["Hc"] / max(GC.h_of(conv["x"]), 0.1)
        # Nt: DFG-2 rule (interior x 60-205 m) relative to Hc('max'); report: x 60-160 m
        sw = (PF["t"] >= tfn - GROUP["Nt_half"] - 1e-9) & (PF["t"] < tfn + GROUP["Nt_half"] - 1e-9) & np.isfinite(PF["Hn"])
        far = sw & (np.abs(PF["t"] - row["t"]) >= GROUP["Nt_excl"] - 1e-9)
        if far.any() and row.get("Hc"):
            j = int(np.where(far)[0][np.argmax(PF["Hn"][far])])
            row["Nt"] = float(PF["Hn"][j] / row["Hc"])
            row["Nt_at"] = dict(t=float(PF["t"][j]), x=float(PF["xn"][j]), y=float(PF["yn"][j]), H=float(PF["Hn"][j]))
            far2 = far & np.isfinite(PF["Hr"])
            row["Nt_x60_160_report"] = float(np.nanmax(PF["Hr"][far2]) / row["Hc"]) if far2.any() else None
        else:
            row["Nt"] = None
        row["Nt_coverage_s"] = float(PF["t"][sw].max() - PF["t"][sw].min()) if sw.any() else 0.0
        row["c_in60"] = float(np.nanmax(PF["c60"][sw])) if (sw.any() and np.isfinite(PF["c60"][sw]).any()) else None
        row["gain_over_c_in60"] = (row["Hc"] / row["c_in60"]) if (row.get("c_in60") and row.get("Hc")) else None
        row["jet_ratio"] = row["Hc"] / DEC["linear_crest"] if row.get("Hc") else None
        on = row["onset"]
        row["plunge_at_converged"] = bool(on is not None and conv["t"] + GROUP["plunge_dt"][0] - 1e-9 <= on["t"] <= conv["t"] + GROUP["plunge_dt"][1] + 1e-9
                                          and on["x"] <= conv["x"] + GROUP["plunge_dx"] + 1e-9)
        row["breaks_later"] = bool(on is not None and not row["plunge_at_converged"])
        row["onset_on_face_or_edge"] = bool(on is not None and on["x"] <= GROUP["face_edge_x"] + 1e-9)
        row["onset_on_shelf"] = bool(on is not None and on["x"] > GROUP["face_edge_x"] + 1e-9)
        # report: pre-break centre-row shape (the screen's ruler; the print: back 31.3 deg, width07 1.32) and the breaker parameter
        pre_f = (on["frame"] - int(round(GROUP["prebreak_dt_s"] * FPS))) if on else conv["f"]
        row["prebreak_shape"] = dict(frame=int(pre_f), t=(pre_f - 1) / FPS, rule=("onset - 0.5 s" if on else "conv instant (no onset)"),
                                     shape=centre_shape_at(H, pre_f, eta0, x_hint=(on["x"] if on else conv["x"])) if pre_f in avail else None)
        row["conv_shape"] = centre_shape_at(H, conv["f"], eta0, x_hint=conv["x"])
        if on is not None:
            slope = (1.0 / GC.SLOPE_S) if (GC.X_TOE < on["x"] < GC.X_EDGE + 1e-9) else 0.0
            row["onset"]["Hc_max_over_h_on"] = row["Hc"] / max(on["h"], 0.1)
            row["onset"]["iribarren_b_T7_Hmax"] = iribarren(row["Hc"], 7.0, slope) if slope > 0 else None
            row["onset"]["on_face"] = bool(slope > 0)
        rows.append(row)
    return rows


# ====================================================================== gates
def gate_G1(rd, cfg):
    dr = cfg.get("dir") or {}
    tc = GC.PLAN_DIR + "/table_check_DFGS2.json"
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    bc = GC.jload(GC.BUILD_CHECK) if os.path.exists(GC.BUILD_CHECK) else {}
    run_hips = sorted(set(r.get("hip_sha256") for r in recs(rd) if r.get("hip_sha256")))
    ok_tab = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256") and dr.get("npz") and os.path.exists(dr["npz"])
                  and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    ok_build = bool(bc.get("all_ok") and run_hips and all(h == bc.get("hip_sha256") for h in run_hips))
    ok_pre = bool((cfg.get("precheck") or {}).get("ok"))
    return dict(ok=bool(ok_tab and ok_build and ok_pre), table_check=ok_tab, build_check52s2=ok_build, cfg_precheck=ok_pre,
                hip_sha_runs=[h[:16] for h in run_hips], hip_sha_build=str(bc.get("hip_sha256"))[:16])


def g2f_ranges():
    """the frozen relative rule: DFG-2's measured 0.5 m R_n (if present) -> ranges; else the DFG-2 frozen ranges."""
    ref = None
    try:
        if os.path.exists(DFG_REF):
            j = GC.jload(DFG_REF)
            g = (j.get("G2f") or (j.get("gates") or {}).get("G2f") or {})
            ref = {int(k[1:]): float(v["R"]) for k, v in (g.get("per_n") or {}).items()}
    except Exception:
        ref = None
    if ref and len(ref) == 3:
        rng = {n: (max(GATES["G2f_floor_0p5"], ref[n] - GATES["G2f_margin_0p5"]), GATES["G2f_hi_0p5"]) for n in GC.HARMONICS}
        src = "relative to DFG-2 0.5 m measured R %s [measured]" % {n: round(v, 3) for n, v in ref.items()}
    else:
        rng = dict(GATES["G2f_fallback_0p5"]); src = "DFG-2 frozen 0.5 m ranges (DFG-2 0.5 m G2f not available)"
    return rng, GATES["G2f_phase_0p5"], src, ref


def g2f(PF, lin):
    t = PF["t"]
    tw = GATES["G2f_t_main"]
    sel = (t >= tw[0] - 1e-9) & (t <= tw[1] + 1e-9)
    rng, phmax, src, ref = g2f_ranges()
    out = dict(window=list(tw), n_frames=int(sel.sum()), per_n={}, ranges={str(k): list(v) for k, v in rng.items()}, phase_max_rad=phmax, range_source=src,
               span_s=float(t[sel].max() - t[sel].min()) if sel.any() else 0.0, rule=G2F_RULE)
    if sel.sum() < 100:
        out["ok"] = False; out["why"] = "too few frames in the G2f window"
        return out
    fits = [harmonic_fit(t[sel], PF["g2"][sel, i], P=GC.P_S, ns=GC.HARMONICS, nuisance=GATES["G2f_nuisance"], tf=GC.T_F) for i in range(len(GATES["G2f_y"]))]
    ok = out["span_s"] >= (tw[1] - tw[0]) - 1.0
    for n in GC.HARMONICS:
        Af = [f_["A"][n] for f_ in fits]
        Al = [complex(*lin["y%g" % y]["n%d" % n]) for y in GATES["G2f_y"]]
        R = sum(abs(a) for a in Af) / sum(abs(a) for a in Al)
        ph = float(np.angle(sum(a * np.conj(b) for a, b in zip(Af, Al))))
        okn = bool(rng[n][0] <= R <= rng[n][1] and abs(ph) <= phmax)
        out["per_n"]["n%d" % n] = dict(R=R, phase_err_rad=ph, range=list(rng[n]), ok=okn, R_DFG2_ref=(ref or {}).get(n),
                                       per_gauge=[dict(y=y, fit_abs=abs(a), lin_abs=abs(b), phase_err=float(np.angle(a * np.conj(b))))
                                                  for y, a, b in zip(GATES["G2f_y"], Af, Al)])
        ok = ok and okn
    out["nuisance_abs_max_m"] = float(max(max(f_["nuisance"].values()) for f_ in fits))
    out["ok"] = bool(ok)
    return out


def gate_G3P(rows):
    ok_rows = [r for r in rows if r.get("complete")]
    ts = [r["conv"]["t"] for r in ok_rows]
    sp = [b - a for a, b in zip(ts[:-1], ts[1:])]
    xs = [r["conv"]["x"] for r in ok_rows]
    Hs = [r["conv"]["Hc"] for r in ok_rows]
    ok = bool(len(ok_rows) == 3 and all(abs(v - GATES["G3P_P"]) <= GATES["G3P_tol"] + 1e-9 for v in sp)
              and (max(xs) - min(xs)) <= GATES["G3P_xspread"] + 1e-9 and max(Hs) / max(min(Hs), 1e-9) <= GATES["G3P_Hc_ratio"] + 1e-9)
    return dict(ok=ok, conv_t=ts, spacings_s=sp, x_spread_m=(max(xs) - min(xs)) if xs else None, Hc_max_over_min=(max(Hs) / min(Hs)) if Hs else None,
                rule="three converged summits spaced 28.0 +- 1.5 s, x spread <= 20 m, Hc max/min <= 1.25")


def g4_numbers(PF, t0=30.0):
    t = PF["t"]
    sel = t >= t0 - 1e-9
    if not sel.any():
        return None
    def mx(k):
        v = PF[k][sel]
        return (float(np.nanmax(v)), float(t[sel][int(np.nanargmax(v))])) if np.isfinite(v).any() else (None, None)
    kin, tin = mx("kA_in"); kco, tco = mx("kA_core"); kwa, twa = mx("kA_wall"); kfu, tfu = mx("kA_full"); klo, tlo = mx("kA_core_loc")
    jf = int(np.nanargmax(PF["kA_full"][sel])) if np.isfinite(PF["kA_full"][sel]).any() else 0
    at = PF["full_at"][sel][jf]
    kfr, tfr = mx("kA_free") if "kA_free" in PF else (None, None)
    fr_at = None
    if kfr is not None and np.isfinite(PF["kA_free"][sel]).any():
        jr = int(np.nanargmax(PF["kA_free"][sel])); fr_at = [float(v) for v in PF["free_at"][sel][jr]]
    return dict(kA_inlet_max=kin, t_inlet_max=tin, kA_side_core_max=kco, t_side_core_max=tco, kA_wall_strip_max=kwa, t_wall_strip_max=twa,
                kA_side_full_max_DFG2_rule=kfu, t_side_full_max=tfu, side_full_max_at_xy=[float(at[0]), float(at[1])],
                klocal_side_core_max=klo, t_klocal_max=tlo, kA_free_lateral_max_report=kfr, t_free_lateral_max=tfr, free_lateral_max_at_xy=fr_at)


def gate_G4(PF, R2, eta0, t_end):
    t = PF["t"]
    sel = t >= GATES["G4_t0"] - 1e-9
    g = g4_numbers(PF, GATES["G4_t0"]) or {}
    lips = r2_lips(R2, eta0, [int(f) for f in PF["f"][sel]], 3.0, GATES["G4_lip_x"])
    kin = g.get("kA_inlet_max"); kco = g.get("kA_side_core_max")
    return dict(ok=bool(kin is not None and kco is not None and kin <= GATES["G4_kA"] and kco <= GATES["G4_kA"] and not lips),
                kA_max=GATES["G4_kA"], kp=GC.kp(), r2_lips_x_lt_60=lips[:20], n_lip_frames=len(lips), **g,
                DFG2_rule_full_band_pass_report=bool(g.get("kA_side_full_max_DFG2_rule") is not None and g["kA_side_full_max_DFG2_rule"] <= GATES["G4_kA"]
                                                     and kin is not None and kin <= GATES["G4_kA"]),
                rule="kp x (3x3-median hf - eta0) <= 0.40 from t 30 s in the inlet band (x <= 50 m, all y 0-140 m) and the generating side-band "
                     "CORE (110 <= y <= 132.5 m, x <= 180 m); no overturning lip on r2 at x < 60 m. Reported, not gated: the outer-wall strip "
                     "y > 132.5 m (target tapered to 0 there, the wall reflects), the full band (y >= 110 m), k(h(x)) x crest in the core, and the "
                     "free lateral strip y 65-110 m, x <= 180 m (the off-axis secondary focus at W 140)")


def gate_G6(rows):
    bad = []
    for r in rows:
        if not r.get("complete"):
            bad.append(dict(n=r["n"], why=r.get("why"))); continue
        c = r["conv"]
        ok = (GATES["G6_x"][0] <= c["x"] <= GATES["G6_x"][1] and abs(c["y"]) <= GATES["G6_y"] + 1e-9
              and r["t_fn"] + GATES["G6_t"][0] - 1e-9 <= c["t"] <= r["t_fn"] + GATES["G6_t"][1] + 1e-9 and c["Hc"] >= GATES["G6_Hc"])
        if not ok:
            bad.append(dict(n=r["n"], x=c["x"], y=c["y"], t=c["t"], t_fn=r["t_fn"], Hc=c["Hc"]))
    return dict(ok=bool(not bad and len(rows) == 3), failing=bad,
                rule="each group's converged summit at x 95-175 m, |y| <= 10 m, t in [t_fn - 5, t_fn + 2] s, Hc >= 5.87 m")


def leak_report(rr):
    nb = [int(q.get("n_below_bed") or 0) for r in rr for q in ((r.get("info") or {}).get("leak") or [])]
    gm = [float(q.get("gap_min")) for r in rr for q in ((r.get("info") or {}).get("leak") or []) if q.get("gap_min") is not None]
    return dict(n_samples=len(nb), n_below_bed_max=(max(nb) if nb else None), gap_min_m=(min(gm) if gm else None),
                ok=bool(nb and max(nb) == 0))


def setup_report(PF):
    """report only: mean level over the shelf (x 155-205 m) and the flat (x 60-100 m) per period (breaking set-up held by the exit sponge)."""
    t = PF["t"]
    out = {}
    for a, b in ((30.0, 62.0), (62.0, 90.0), (90.0, 110.0)):
        s = (t >= a) & (t < b)
        if s.any():
            out["t%g_%g" % (a, b)] = dict(shelf=float(np.nanmean(PF["lvl_shelf"][s])), flat=float(np.nanmean(PF["lvl_flat"][s])),
                                          exit_190_200=float(np.nanmean(PF["lvl_exit"][s])))
    return dict(per_period=out, rule="report only: mean (hf - eta0) over x 155-205 m (shelf), 60-100 m (flat), 190-200 m, |y| <= 65 m")


def sponge_report(PF, lin_rep):
    t = PF["t"]
    rows = {}
    for k, (x, y) in enumerate(REP_PTS):
        key = "x%g_y%g" % (x, y)
        r_ = {}
        for nm, a, b in (("t32_60", 32.0, 60.0), ("t60_88", 60.0, 88.0)):
            sl = (t >= a) & (t < b)
            if sl.sum() > 50 and key in (lin_rep or {}):
                fit = harmonic_fit(t[sl], PF["rep"][sl, k], P=GC.P_S, ns=GC.HARMONICS, tf=GC.T_F)
                r_[nm] = {"n%d" % n: dict(abs=abs(fit["A"][n]), ratio_to_linear=abs(fit["A"][n]) / max(abs(complex(*lin_rep[key]["n%d" % n])), 1e-9))
                          for n in GC.HARMONICS}
        rows[key] = r_
    out = dict(per_frequency=rows, rule="report only: harmonic fit on the shelf before the exit sponge, two halves of t 32-88 s")
    try:
        g = [rows[k]["t60_88"]["n%d" % n]["abs"] / max(rows[k]["t32_60"]["n%d" % n]["abs"], 1e-9) for k in rows for n in GC.HARMONICS]
        out["second_over_first_half_max"] = float(max(g)); out["growing_pattern_flag"] = bool(max(g) > 1.2)
    except Exception:
        pass
    return out


# ====================================================================== pipeline check and judge
def common(rd, kind):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = load_cfg(rd)
    rr = recs(rd)
    eta0, eta0_src = still_offset(rd, rr)
    H = Blocks(rd, "hf", "eta"); R2 = Blocks(rd, "r2", "sdf"); R4 = Blocks(rd, "r4", "sdf")
    frames = H.frames()
    t_end = (max(frames) - 1) / FPS if frames else 0.0
    done = max([int(r.get("f_end_done") or 0) for r in rr] or [0])
    res = dict(run_id=os.path.basename(rd), run_dir=rd, kind=kind, plan=GC.PLAN_REL, plan_sha_ok=GC.plan_sha_ok(), tool="Tools/GWWaveGen/flip52s2/g52s2_ana.py",
               tool_sha256=GC.sha256_file(os.path.abspath(__file__)), e51_sha256=GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py"),
               e51_frozen_ok=GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py") == E51_SHA, amendments=[a.get("id") for a in GC.amendments()],
               date=time.strftime("%Y-%m-%d %H:%M:%S"), eta0=eta0, eta0_source=eta0_src, t_record_end=t_end, frames_n=len(frames),
               dp=float((cfg.get("parms") or {}).get("dp", 0.0)), set=(cfg.get("dir") or {}).get("set"),
               bed=dict(x_toe=(cfg.get("parms") or {}).get("ridge_x0"), s=(cfg.get("parms") or {}).get("ridge_s"), shelf_h=(cfg.get("parms") or {}).get("shelf_h")))
    res["run_complete"] = dict(ok=bool(cfg and done >= int(cfg.get("f_end", 10 ** 9))), frames_done=done, f_end=cfg.get("f_end"))
    res["launches"] = [dict(f_start=r.get("f_start"), f_end_done=r.get("f_end_done"), stopped=r.get("stopped"), wall_s=r.get("wall_total_s"),
                            particles_max=r.get("particles_max"), rss_gb=r.get("rss_peak_gb"), substeps=r.get("substeps_min_max")) for r in rr]
    res["wall_h"] = sum([float(r.get("wall_total_s") or 0.0) for r in rr]) / 3600.0
    res["particles_max"] = max([int(r.get("particles_max") or 0) for r in rr] or [0])
    res["leak"] = leak_report(rr)
    res["G1"] = gate_G1(rd, cfg)
    res["G5"] = gate_G5(load_r6(rd))
    return res, cfg, rr, H, R2, R4, eta0, t_end


def pcheck(rd, out_dir=None):
    """PIPELINE CHECK ONLY (0.5 m, 0-10 s; never shape-judged)."""
    res, cfg, rr, H, R2, R4, eta0, t_end = common(rd, "pcheck")
    ck = {}
    ck["run_complete"] = res["run_complete"]["ok"]
    ck["G1"] = res["G1"]["ok"]
    ck["G5"] = res["G5"].get("ok")
    ck["no_guard_stop"] = bool(rr and all((r.get("stopped") in (None, "")) or str(r.get("stopped")).startswith("wall_limit") for r in rr))
    ck["no_particle_below_bed"] = res["leak"]["ok"]
    ck["eta0_small"] = bool(abs(eta0) <= GATES["pc_eta0_abs_max"])
    # still water over the step at the start (seeding fills the face and the shelf to the still level)
    fr = [f for f in H.frames() if GATES["pc_still_t"][0] - 1e-9 <= (f - 1) / FPS <= GATES["pc_still_t"][1] + 1e-9]
    df, mxa = [], []
    for f in fr:
        a, meta = H.get(f)
        e = EM.median3(a) - eta0
        xs, yh = axes(meta, e.shape)
        rows = yh <= GC.INTERIOR_Y + 1e-9
        flm = (xs >= GATES["pc_still_flat_x"][0]) & (xs <= GATES["pc_still_flat_x"][1])
        shm = (xs >= GATES["pc_still_shelf_x"][0]) & (xs <= GATES["pc_still_shelf_x"][1])
        df.append(float(np.nanmean(e[np.ix_(rows, shm)]) - np.nanmean(e[np.ix_(rows, flm)])))
        mxa.append(float(np.nanmax(np.abs(e[np.ix_(rows, (xs >= 60.0) & (xs <= 205.0))]))))
    res["still_start"] = dict(frames=len(fr), shelf_minus_flat_m=(max(df, key=abs) if df else None), max_abs_eta_m=(max(mxa) if mxa else None))
    ck["still_water_over_step"] = bool(df and abs(max(df, key=abs)) <= GATES["pc_still_diff_max"] and max(mxa) <= GATES["pc_still_abs_max"])
    # the waves arrive at x 60 m with the order of magnitude of the ramped linear target
    PF = pass_frames(H, eta0, GATES["pc_wave_t"][0], GATES["pc_wave_t"][1], GC.kp())
    meas = float(np.nanmax(np.abs(PF["c60"]))) if len(PF["t"]) else 0.0
    exp_ = None
    try:
        import g52s2_table as TBS
        tab = TBS.load((cfg.get("dir") or {}).get("npz"))
        yl = np.arange(0.5, GC.INTERIOR_Y + 1e-9, 1.0)
        best = 0.0
        for tq in np.arange(GATES["pc_wave_t"][0], GATES["pc_wave_t"][1] + 1e-9, 0.25):
            e1, _, _ = TBS.dirwave_np(tab, 60.0 + 0 * yl, 50.0, yl, tq, 1.0, ret_on=0.0)
            tr = max(0.0, min(1.0, (tq - GATES["pc_wave_delay_s"]) / GC.RAMP_S))
            best = max(best, float(np.max(e1)) * 0.5 * (1.0 - math.cos(math.pi * tr)))
        exp_ = best
    except Exception as ex:
        res["wave_expect_error"] = repr(ex)[:200]
    ratio = (meas / exp_) if exp_ else None
    res["waves_arrive"] = dict(x=60.0, t=list(GATES["pc_wave_t"]), crest_max_measured_m=meas, crest_max_ramped_linear_m=exp_, ratio=ratio,
                               rule="largest crest on x 60 m (|y| <= 65 m) in t 6-10 s / the linear target there x the half-cosine ramp delayed 1.5 s; "
                                    "pass if 0.33-3.0 (order of magnitude: pipeline only)")
    ck["waves_arrive"] = bool(ratio is not None and GATES["pc_wave_ratio"][0] <= ratio <= GATES["pc_wave_ratio"][1])
    surf = sorted(glob.glob(os.path.join(res["run_dir"], "surf", "s_*.gw45s")))
    r4n = len(R4.frames())
    res["records"] = dict(hf_frames=len(H.frames()), r2_frames=len(R2.frames()), r4_frames=r4n, r5_files=len(surf))
    ck["records_written"] = bool(len(H.frames()) >= int(cfg.get("f_end", 10 ** 9)) and len(R2.frames()) >= int(cfg.get("f_end", 10 ** 9))
                                 and r4n > 0 and len(surf) > 0)
    res["checks"] = ck
    failed = [k for k, v in ck.items() if not v]
    res["failed"] = failed
    res["pcheck_pass"] = not failed
    res["verdict"] = "PCHECK_PASS (pipeline only, never shape-judged)" if not failed else "PCHECK_FAIL (%s)" % ", ".join(failed)
    res["rate_s_per_frame"] = dict(wall=res["launches"][0].get("wall_s") if res["launches"] else None, frames=res["run_complete"]["frames_done"])
    od = GC.guard_out(out_dir or os.path.join(res["run_dir"], "g52s2"), allow_scratch=True)
    p = os.path.join(od, "pcheck_DFGS2.json")
    GC.jdump(res, p)
    res["_path"] = p.replace("\\", "/")
    return res


def best_valid():
    rows = dict(DF1A=dict(miss=DEC["DF1A_miss"], valid=True, source="DF1A 0.5 m e51 'max' median core miss 3.3 [measured]"))
    for k, d in BEST_RUNS.items():
        p = d["judge"]
        if not os.path.exists(p):
            rows[k] = dict(missing=True, source=p); continue
        try:
            j = GC.jload(p)
            v = bool(j.get("valid"))
            if d.get("valid_file"):
                vf = GC.jload(d["valid_file"]) if os.path.exists(d["valid_file"]) else {}
                v = bool(vf.get(d["valid_key"]))
            rows[k] = dict(miss=j.get("core_miss_median"), valid=v, source=p)
        except Exception as ex:
            rows[k] = dict(error=repr(ex)[:200], source=p)
    vals = [r["miss"] for r in rows.values() if r.get("valid") and isinstance(r.get("miss"), (int, float))]
    return min(vals), rows


def decide(res):
    failed = res["failed_gates"]
    pipe = {"run_complete", "G1", "G2f"}
    best, rows = best_valid()
    bar = min(DEC["bar_cap"], best - DEC["bar_margin"])
    ok_rows = [r for r in res["groups"] if r.get("complete")]
    k = DEC["plunge_groups"]
    n_plunge = sum(1 for r in ok_rows if r.get("plunge_at_converged"))
    n_later = sum(1 for r in ok_rows if r.get("breaks_later"))
    n_face = sum(1 for r in ok_rows if r.get("onset_on_face_or_edge"))
    n_shelf = sum(1 for r in ok_rows if r.get("onset_on_shelf"))
    flags = (["PLUNGE_AT_CONVERGED"] if n_plunge >= k else []) + (["BREAKS_LATER"] if n_later >= k else []) + \
            (["NO_BREAK_IN_WINDOW"] if (len(ok_rows) - n_plunge - n_later) >= k else []) + \
            (["ONSET_ON_FACE_OR_EDGE"] if n_face >= k else []) + (["BREAKS_ON_SHELF"] if n_shelf >= k else [])
    out = dict(bar=bar, best_valid_0p5=best, best_rows=rows, physics_flags=flags, n_groups_plunge_at_converged=n_plunge, n_groups_break_later=n_later,
               n_groups_onset_face_or_edge=n_face, n_groups_onset_shelf=n_shelf,
               rule="plan_DFGS2_frozen decision (convergence part = the DFG-2 / DFG-S frozen rule, DFG-S and DFG-2B-E added to the best-valid list; "
                    "physics flags report the breaker)")
    if failed:
        cls = "pipeline" if any(q in pipe for q in failed) else "physics"
        out.update(valid=False, failure_class=cls, outcomes=["INVALID"],
                   next=("PIPELINE_FAIL: the main session fixes the pipeline cause and reruns once (same setup name)" if cls == "pipeline" else
                         "PHYSICS_FAIL: report the numbers, the print view and the print ruler to the user; DFG-S-E140 stops"))
        return out
    el = res["eligibility"]
    eligible = bool(all((el.get(q) or {}).get("ok") for q in ("E1", "E1t", "E2", "E3")))
    miss = res["median"].get("miss")
    oc = []
    if eligible:
        if miss is not None and miss <= bar:
            oc.append("NEW_BEST_SHAPE")
        if miss is not None and miss <= DEC["target_band"]:
            oc.append("TARGET_BAND")
        if sum(1 for r in ok_rows if (r.get("jet_ratio") or 0) >= DEC["jet_ratio"]) >= DEC["jet_groups"]:
            oc.append("JET_REGIME_SEEN")
    if not any(o in oc for o in ("NEW_BEST_SHAPE", "TARGET_BAND")):
        oc.append("NO_GAIN" if eligible else "NOT_ELIGIBLE")
    out.update(valid=True, eligible=eligible, outcomes=oc, next="co-equal verdict after pv53 (convergence %s; physics %s)" % (oc, flags))
    return out


def judge(rd, out_dir=None):
    t0 = time.time()
    res, cfg, rr, H, R2, R4, eta0, t_end = common(rd, "0p5")
    sp = GC.bed_spec(cfg if cfg.get("bed") else None, parms=(cfg.get("parms") or {}))
    PF = pass_frames(H, eta0, 25.0, t_end, GC.kp(), depth=lambda x: -GC.bed_z(np.asarray(x, float), 0.0, **sp))
    lin = ((cfg.get("dir") or {}).get("linear_refs") or {})
    An = (lin.get("G2f_gauges") or {}).get("A_n")
    res["G2f"] = g2f(PF, An) if (An and "y%g" % GATES["G2f_y"][0] in An) else dict(ok=False, why="cfg dir.linear_refs.G2f_gauges missing")
    res["G4"] = gate_G4(PF, R2, eta0, t_end)
    rows = group_rows(res["run_dir"], H, R2, R4, PF, eta0, t_end, foci(cfg))
    res["groups"] = rows
    ok_rows = [r for r in rows if r.get("complete")]
    summ = {k: med(ok_rows, k) for k in REPORT_KEYS}
    for k in ("Nt", "Nt_x60_160_report", "c_in60", "gain_over_c_in60", "jet_ratio", "h_at_pk"):
        summ[k] = med(ok_rows, k)
    summ["conv_Hc"] = med([dict(v=r["conv"]["Hc"]) for r in ok_rows], "v")
    summ["conv_x"] = med([dict(v=r["conv"]["x"]) for r in ok_rows], "v")
    summ["conv_Hc_over_h"] = med([dict(v=r["conv"]["Hc_over_h"]) for r in ok_rows], "v")
    summ["onset_x"] = med([dict(v=r["onset"]["x"]) for r in ok_rows if r.get("onset")], "v")
    summ["onset_h"] = med([dict(v=r["onset"]["h"]) for r in ok_rows if r.get("onset")], "v")
    summ["prebreak_back_deg"] = med([dict(v=((r.get("prebreak_shape") or {}).get("shape") or {}).get("back_deg")) for r in ok_rows], "v")
    summ["prebreak_w07"] = med([dict(v=((r.get("prebreak_shape") or {}).get("shape") or {}).get("w07")) for r in ok_rows], "v")
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
    res["eligibility"] = dict(
        E1=dict(N1_median=summ.get("N1"), max=ELIG["N1_max"], ok=bool(summ.get("N1") is not None and summ["N1"] <= ELIG["N1_max"])),
        E1t=dict(Nt_median=summ.get("Nt"), max=ELIG["Nt_max"], ok=bool(summ.get("Nt") is not None and summ["Nt"] <= ELIG["Nt_max"]),
                 Nt_x60_160_report=summ.get("Nt_x60_160_report")),
        E2=dict(Hc_median=Hc, min=ELIG["Hc_min"], ok=bool(Hc is not None and Hc >= ELIG["Hc_min"])),
        E3=dict(gain=gain, Hc_median=Hc, c_in60_median=cin, min=ELIG["gain_min"], ok=bool(gain is not None and gain >= ELIG["gain_min"])))
    tab = cfg.get("dir") or {}
    res["gains_report"] = dict(Hc_over_linear_design_crest_xf=(Hc / ((tab.get("linear_refs") or {}).get("design_crest_xf_m") or np.nan)) if Hc else None,
                               Hc_over_a_sum=(Hc / DEC["linear_crest"]) if Hc else None,
                               Hc_over_max_component=(Hc / tab["a_max_component"]) if (Hc and tab.get("a_max_component")) else None,
                               Hc_over_c_in60=gain)
    res["setup_report"] = setup_report(PF)
    res["sponge_report"] = sponge_report(PF, lin.get("report_gauges"))
    res["core_miss_median"] = summ.get("miss")
    res["energy_statement"] = (cfg.get("wave") or {}).get("energy")
    res["decision"] = decide(res)
    best = min(ok_rows, key=lambda r: r["miss"]) if ok_rows else None
    res["red_instant"] = dict(n=best["n"], frame=best["f"], t=best["t"], miss=best["miss"], Hc=best["Hc"], x=best["x_pk"], y=best["y_pk"]) if best else None
    res["per_frame"] = dict(t=PF["t"][::4], Hc_scan=PF["Hc"][::4], x_scan=PF["x"][::4], centre_crest=PF["ec0"][::4], centre_x=PF["xc0"][::4], c60=PF["c60"][::4])
    res["elapsed_s"] = round(time.time() - t0, 1)
    od = GC.guard_out(out_dir or os.path.join(res["run_dir"], "g52s2"), allow_scratch=True)
    p = os.path.join(od, "judge_DFGS2.json")
    GC.jdump(res, p)
    res["_path"] = p.replace("\\", "/")
    # pv53 alias: pv53 treats a run whose cfg dir.set starts with 'DFG' as FLIP52 family and reads <run>/g52/judge_DFG.json (groups f, x_pk, y_pk,
    # Hc ...; decision.outcomes; median; core_miss_median; red_instant). The same content under that name; written only for a real run folder.
    if not out_dir:
        GC.jdump(dict(res, alias_of="g52s2/judge_DFGS2.json (plan DFG-S-E140)"), GC.guard_out(os.path.join(res["run_dir"], "g52")) + "/judge_DFG.json")
    return res


def g4split(rd):
    """read only: G4 numbers per region (inlet, side core, outer-wall strip, full band, free lateral strip) of a run in this plan's layout
    (W 140 m, side band 110-140 m; GATES)."""
    rd = os.path.abspath(rd).replace("\\", "/")
    rr = recs(rd)
    eta0, src = still_offset(rd, rr)
    H = Blocks(rd, "hf", "eta")
    fr = H.frames()
    t_end = (max(fr) - 1) / FPS if fr else 0.0
    cfg = load_cfg(rd)
    sp = GC.bed_spec(cfg if cfg.get("bed") else None, parms=(cfg.get("parms") or {}))
    PF = pass_frames(H, eta0, GATES["G4_t0"], t_end, GC.kp(), depth=lambda x: -GC.bed_z(np.asarray(x, float), 0.0, **sp))
    g = g4_numbers(PF, GATES["G4_t0"]) or {}
    return dict(run=os.path.basename(rd), bed_kind=GC.bed_kind(sp), bed_x_toe=float(sp["x_toe"]), eta0=eta0, eta0_source=src, t=[GATES["G4_t0"], t_end], frames=len(PF["t"]), kp=GC.kp(), **g,
                regions=dict(inlet="x <= 50 m, all y", side_core="%g <= y <= %g m, x <= 180 m" % (GATES["G4_side_y"], GATES["G4_side_y1"]),
                             wall_strip="y > %g m, x <= 180 m" % GATES["G4_side_y1"], full_band="y >= %g m, x <= 180 m" % GATES["G4_side_y"],
                             free_lateral="65 < y < %g m, x <= 180 m (report)" % GATES["G4_side_y"]), tag="measured (3x3-median hf - eta0, kp = k(T 7 s, 20 m))")


# ====================================================================== the co-equal verdict (after pv53)
def pv53_result(rd, pv=None):
    rid = os.path.basename(os.path.abspath(rd).rstrip("/\\"))
    p = pv or (PV53_OUT + "/%s/pv53_%s.json" % (rid, rid))
    if os.path.exists(p):
        return GC.jload(p), p, "pv53 json"
    if os.path.exists(PV53):
        try:
            import importlib.util as ilu
            spec = ilu.spec_from_file_location("pv53_ro", PV53)
            M = ilu.module_from_spec(spec); spec.loader.exec_module(M)
            R, per, best_p, ref, V = M.analyse(rd, log=lambda *a: None)
            return dict(verdict=V, periods=[dict((k, v) for k, v in p_.items() if k != "series") for p_ in per],
                        most_print_like=(dict(n=best_p["n"], frame=best_p["best"]["frame"], t=best_p["best"]["t"], score3=best_p["best"]["score3"],
                                              lip=best_p["best"].get("lip")) if best_p else None), unity=dict(ok=False, why="pv53 run json missing: no render")), \
                None, "pv53.analyse (no Unity view)"
        except Exception as ex:
            return None, None, "pv53 fallback failed: %s" % repr(ex)[:200]
    return None, None, "pv53 missing"


def _valid_by_own_plan(d):
    try:
        if not os.path.exists(d["judge"]):
            return None
        j = GC.jload(d["judge"])
        v = bool(j.get("valid"))
        if d.get("valid_file"):
            vf = GC.jload(d["valid_file"]) if os.path.exists(d["valid_file"]) else {}
            v = bool(vf.get(d["valid_key"]))
        return v
    except Exception:
        return None


def pl_median_of_pv53(pj):
    vals = [((p.get("conv_print") or {}).get("miss")) for p in (pj or {}).get("periods") or []]
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    return (float(np.median(vals)) if len(vals) >= COEQ_PL["min_groups"] else None), vals


def pl_refs():
    """[measured, read at analysis time] the earlier runs' median e51 miss at their most print-like instants (pv53 periods[].conv_print), only
    for runs valid by their own plans; bar_pl = min(cap, best - margin)."""
    rows = {}
    for k, d in PL_REFS.items():
        if not os.path.exists(d["pv53"]):
            rows[k] = dict(missing=True, source=d["pv53"]); continue
        try:
            m, vals = pl_median_of_pv53(GC.jload(d["pv53"]))
        except Exception as ex:
            rows[k] = dict(error=repr(ex)[:200], source=d["pv53"]); continue
        rows[k] = dict(pl_miss_median=m, per_group=vals, valid=_valid_by_own_plan(d), source=d["pv53"])
    vals = [r["pl_miss_median"] for r in rows.values() if r.get("valid") and isinstance(r.get("pl_miss_median"), (int, float))]
    best = min(vals) if vals else None
    bar = min(COEQ_PL["cap"], best - COEQ_PL["margin"]) if best is not None else COEQ_PL["cap"]
    return dict(bar_pl=bar, best_valid_pl=best, rows=rows, rule=COEQ_PL["rule"])


def conv_at_print_like(rd, P, eta0):
    """NEW co-requirement 3b: e51 at pv53's most print-like frame of each group (recomputed here with the judge's eta0; pv53's own conv_print
    value is reported beside it and used only if the recomputation fails for a group)."""
    H = Blocks(rd, "hf", "eta")
    avail = set(H.frames())
    rows = []
    for p_ in (P or {}).get("periods") or []:
        b = p_.get("best") or {}
        f = b.get("frame"); xc = b.get("x_c")
        r = dict(n=p_.get("n"), frame=f, t=b.get("t"), x_c=xc, score3=b.get("score3"), lip=b.get("lip"),
                 pv53_miss=(p_.get("conv_print") or {}).get("miss"), pv53_Hc=(p_.get("conv_print") or {}).get("Hc"))
        if f is None or xc is None:
            r["why"] = "no print-like instant"; rows.append(r); continue
        m = None
        if int(f) in avail:
            try:
                a, meta = H.get(int(f))
                bb = masked(a, meta, GC.INTERIOR_Y)
                xw = (float(xc) + COEQ_PL["xwin_rel"][0], float(xc) + COEQ_PL["xwin_rel"][1])
                m = EM.hf_metrics(bb, meta, eta0, xwin=xw)
                if m and "W50" in m:
                    miss, per = EM.score_vs_target(m)
                    r.update(miss=miss, miss_per=per, xwin=list(xw), src="recomputed (judge eta0)",
                             **{k: m.get(k) for k in ("Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "K", "S2")})
            except Exception as ex:
                r["error"] = repr(ex)[:200]
        if r.get("miss") is None and isinstance(r.get("pv53_miss"), (int, float)):
            r["miss"] = float(r["pv53_miss"]); r["src"] = "pv53 conv_print (recomputation failed)"
        rows.append(r)
    vals = [q["miss"] for q in rows if isinstance(q.get("miss"), (int, float))]
    med_ = float(np.median(vals)) if len(vals) >= COEQ_PL["min_groups"] else None
    keys = ("Hc", "W50", "W80", "W95", "K", "S2")
    medians = {k: med([q for q in rows if q.get(k) is not None], k) for k in keys}
    return dict(per_group=rows, pl_miss_median=med_, n_groups=len(vals), medians=medians)


def coequal(rd, pv=None, out_dir=None, judge_path=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    jp = judge_path or os.path.join(rd, "g52s2", "judge_DFGS2.json")       # judge_path: tests only (with out_dir in the scratchpad)
    J = GC.jload(jp) if os.path.exists(jp) else None
    P, ppath, src = pv53_result(rd, pv)
    out = dict(run_id=os.path.basename(rd), date=time.strftime("%Y-%m-%d %H:%M:%S"), plan=GC.PLAN_REL, rule=COEQ, rule_pl=COEQ_PL,
               judge=jp if J else None, pv53=ppath, pv53_source=src, energy_statement=(J or {}).get("energy_statement"))
    conv_oc = ((J or {}).get("decision") or {}).get("outcomes") or []
    conv_ok = bool(J and J.get("valid") and any(o in COEQ["conv_outcomes"] for o in conv_oc))
    V = (P or {}).get("verdict") or {}
    s3 = V.get("median_best_score3"); lip = V.get("median_best_lip")
    pm_ok = bool(s3 is not None and lip is not None and s3 <= COEQ["score3_bar"] + 1e-9 and lip >= COEQ["lip_min"] - 1e-9)
    unity = (P or {}).get("unity") or {}
    per = []
    for p_ in (P or {}).get("periods") or []:
        b = p_.get("best") or {}
        per.append(dict(n=p_.get("n"), frame=b.get("frame"), t=b.get("t"), score3=b.get("score3"), lip=b.get("lip"), chord=b.get("chord"), foot=b.get("foot"),
                        hood=b.get("hood"), hollow=b.get("hollow"), back=b.get("back"), w07=b.get("w07"), eta_c=b.get("eta_c"), x_c=b.get("x_c"),
                        below_crest_floor=b.get("below_crest_floor")))
    med_ = lambda k: med([q for q in per if q.get(k) is not None], k)
    ruler = {k: med_(k) for k in ("score3", "lip", "chord", "foot", "hood", "hollow", "back", "w07", "eta_c")}
    pre = {k: ((J or {}).get("median") or {}).get(k) for k in ("prebreak_back_deg", "prebreak_w07", "onset_x", "onset_h")}
    pr = COEQ["print_ref"]
    pre["prebreak_back_in_print_band"] = bool(pre.get("prebreak_back_deg") is not None and pr["back_band"][0] <= pre["prebreak_back_deg"] <= pr["back_band"][1])
    pre["prebreak_w07_in_print_band"] = bool(pre.get("prebreak_w07") is not None and pr["width07_band"][0] <= pre["prebreak_w07"] <= pr["width07_band"][1])
    # 3b: convergence at the most print-like instant (NEW co-requirement)
    refs = pl_refs()
    plc = conv_at_print_like(rd, P, float((J or {}).get("eta0") or 0.0)) if (P and J) else dict(per_group=[], pl_miss_median=None, n_groups=0)
    plm = plc.get("pl_miss_median")
    pl_ok = bool(plm is not None and plm <= refs["bar_pl"] + 1e-9)
    conv_bar = ((J or {}).get("decision") or {}).get("bar")
    same_inst = bool(plm is not None and conv_bar is not None and plm <= conv_bar + 1e-9)
    out.update(
        criterion_1_print_view=dict(ok=bool(unity.get("ok")), why=unity.get("why"), stills={k: v for k, v in (unity.get("print_like") or {}).items()
                                                                                             if isinstance(v, str) and (v.endswith(".png") or v.endswith(".mp4") or v.endswith(".jpg"))},
                                    report_png=(P or {}).get("report_png"), most_print_like=(P or {}).get("most_print_like")),
        criterion_2_print_ruler=dict(print_match=("ok" if pm_ok else ("worse than DM1A" if s3 is not None else "not measured")), median_best_score3=s3,
                                     median_best_lip=lip, bar_score3=COEQ["score3_bar"], lip_min=COEQ["lip_min"], per_group=per, medians=ruler,
                                     print_ref=COEQ["print_ref"], prebreak_report=pre,
                                     better_than_DM1A=bool(s3 is not None and lip is not None and s3 < COEQ["score3_DM1A_median"] and lip >= COEQ["lip_min"])),
        criterion_3_convergence=dict(valid=(J or {}).get("valid"), failed=(J or {}).get("failed_gates"), outcomes=conv_oc, improves=conv_ok,
                                     core_miss_median=(J or {}).get("core_miss_median"), bar=conv_bar,
                                     median={k: ((J or {}).get("median") or {}).get(k) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "N1", "Nt",
                                                                                                 "conv_Hc", "conv_x", "conv_Hc_over_h", "onset_x")},
                                     physics_flags=((J or {}).get("decision") or {}).get("physics_flags")),
        criterion_3b_convergence_at_print_like=dict(ok=pl_ok, pl_miss_median=plm, bar_pl=refs["bar_pl"], best_valid_earlier_pl=refs["best_valid_pl"],
                                                    n_groups=plc.get("n_groups"), per_group=plc.get("per_group"), medians=plc.get("medians"),
                                                    same_instant_new_best=same_inst, conv_bar=conv_bar, refs=refs["rows"],
                                                    DFGS_measured_median=COEQ_PL["DFGS_median"], DM1A_best_report=COEQ_PL["DM1A_best_report"],
                                                    rule=COEQ_PL["rule"]))
    prog = bool(conv_ok and pm_ok and pl_ok and P is not None and bool(unity.get("ok")))
    plt = ("print-like miss %s %s bar_pl %.2f" % (("%.2f" % plm) if plm is not None else "not measured", "<=" if pl_ok else ">", refs["bar_pl"]))
    if not J:
        verdict = "INCOMPLETE (no judge)"
    elif P is None:
        verdict = "INCOMPLETE (no print-view package: pv53 %s); never progress without the print view" % src
    elif conv_ok and pm_ok and pl_ok and not unity.get("ok"):
        verdict = ("convergence %s, print ruler ok (score3 %.3f, lip %.2f) and %s but the Unity print view is missing (%s): INCOMPLETE, not shown "
                   "as progress until the render exists" % (conv_oc, s3, lip, plt, unity.get("why")))
    elif prog:
        verdict = ("PROGRESS: convergence %s AND print match ok (median best score3 %.3f <= %.4f, lip %.2f >= %.2f) AND converged at the most "
                   "print-like instant (%s)%s" % (conv_oc, s3, COEQ["score3_bar"], lip, COEQ["lip_min"], plt,
                                                  "; SAME_INSTANT_NEW_BEST" if same_inst else ""))
    elif conv_ok and pm_ok:
        verdict = ("NOT progress: convergence %s and print match ok (score3 %.3f, lip %.2f) but the most print-like instant is not converged "
                   "(%s): the converged and the print-like instants are different waves" % (conv_oc, s3, lip, plt))
    elif conv_ok:
        verdict = "converged, print match worse than DM1A (score3 %s, lip %s; %s): NOT a new shape reference, not shown as progress" % (s3, lip, plt)
    elif pm_ok:
        verdict = "print match ok (score3 %.3f, lip %.2f) but convergence does not improve (%s; %s): reported side by side" % (s3, lip, conv_oc, plt)
    else:
        verdict = "neither: convergence %s, print match %s (score3 %s, lip %s; %s)" % (conv_oc, "worse than DM1A" if s3 is not None else "not measured",
                                                                                       s3, lip, plt)
    en = out.get("energy_statement") or {}
    if en.get("statement"):
        verdict += " | " + en["statement"].split(";")[0] + "; in-tank inlet variance %s x DM1A, interior power %s x DM1A" % (
            _r2((en.get("in_tank") or {}).get("inlet_variance_over_DM1A")), _r2((en.get("in_tank") or {}).get("interior_power_over_DM1A")))
    out["progress"] = prog
    out["verdict"] = verdict
    od = GC.guard_out(out_dir or os.path.join(rd, "g52s2"), allow_scratch=True)
    GC.jdump(out, os.path.join(od, "coequal_DFGS2.json"))
    out["_path"] = os.path.join(od, "coequal_DFGS2.json").replace("\\", "/")
    return out


def _r2(v):
    return ("%.2f" % v) if isinstance(v, (int, float)) else "-"


# ====================================================================== the pre-launch read of DFG-2B-E (plan pre_launch_check; read only)
PRE = dict(win_s=1.5, x_back=30.0, x_fwd=5.0, k7eta_max=0.50, lip_min=0.20, min_onset_groups=2, T=7.0,
           run=GC.REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5",
           rule="for each group with an r2 onset: crit = max over the hf frames in [on - 1.5 s, on] of k(T 7 s, h(x_c)) x eta_c, eta_c = the centre-row "
                "crest (median of hf rows y 0.5-2.5 m, 3-point median, minus eta0) in x [on_x - 30, on_x + 5] m, h from the run's cfg bed; trigger 1 "
                "if the median crit over >= 2 groups <= 0.50 (FLIP breaks at a lower steepness than the design's C 0.55-0.70); trigger 2 if >= 2 "
                "groups have an r2 onset and pv53's median best-instant lip < 0.20 (breaks without a forward lip: jet / spill)")


def dfgbe_read(rd=None):
    """[measured, read only] the design's pre-launch condition on DFG-2B-E (same sea x 1.680585 on the D19B 1:10 beach): returns the two
    indicators and whether either trigger fires. Missing judge -> readable False (no trigger: no evidence)."""
    rd = os.path.abspath(rd or PRE["run"]).replace("\\", "/")
    rid = os.path.basename(rd)
    jp = next((q for q in (rd + "/g52b/judge_DFGB.json", rd + "/g52s/judge_DFGS.json", rd + "/g52s2/judge_DFGS2.json") if os.path.exists(q)), None)
    out = dict(run=rid, run_dir=rd, judge=jp, rule=PRE["rule"], readable=False, trigger_k7eta=False, trigger_no_lip=False)
    if not jp:
        out["why"] = "no judge file (DFG-2B-E did not finish its judge): no evidence, no trigger"
        return out
    J = GC.jload(jp)
    cfg = load_cfg(rd)
    eta0 = float(J.get("eta0") or 0.0)
    sp = GC.bed_spec(cfg if cfg.get("bed") else None, parms=(cfg.get("parms") or {}))
    H = Blocks(rd, "hf", "eta")
    avail = set(H.frames())
    rows = []
    for g in J.get("groups") or []:
        on = g.get("onset")
        if not on:
            rows.append(dict(n=g.get("n"), onset=None)); continue
        f1 = int(on["frame"]); f0 = f1 - int(round(PRE["win_s"] * FPS))
        best = None
        for f in range(f0, f1 + 1):
            if f not in avail:
                continue
            a, meta = H.get(f)
            xs, yh = axes(meta, a.shape)
            row = np.median(np.asarray(a[0:3, :], float), axis=0) - eta0
            row = ndi.median_filter(row, size=3, mode="nearest")
            m = (xs >= float(on["x"]) - PRE["x_back"]) & (xs <= float(on["x"]) + PRE["x_fwd"])
            if not m.any():
                continue
            i = int(np.argmax(np.where(m, row, -9.0)))
            xc = float(xs[i]); ec = float(row[i])
            h = max(float(-GC.bed_z(np.asarray(xc, float), 0.0, **sp)), 0.05)
            k = float(GC.kdisp(2 * math.pi / PRE["T"], h))
            if best is None or k * ec > best["k7eta"]:
                best = dict(frame=f, t=(f - 1) / FPS, x_c=xc, eta_c=ec, h=h, k7eta=k * ec)
        rows.append(dict(n=g.get("n"), onset=dict(frame=f1, t=on.get("t"), x=on.get("x")), crit=best))
    crits = [r["crit"]["k7eta"] for r in rows if r.get("crit")]
    n_on = sum(1 for r in rows if r.get("onset"))
    pvp = PV53_OUT + "/%s/pv53_%s.json" % (rid, rid)
    lipm = None
    if os.path.exists(pvp):
        try:
            lipm = (GC.jload(pvp).get("verdict") or {}).get("median_best_lip")
        except Exception:
            lipm = None
    med_c = float(np.median(crits)) if len(crits) >= PRE["min_onset_groups"] else None
    out.update(readable=True, eta0=eta0, groups=rows, n_onset_groups=n_on, k7eta_crit_median=med_c, pv53=pvp if os.path.exists(pvp) else None,
               pv53_median_best_lip=lipm, judge_valid=J.get("valid"), judge_outcomes=(J.get("decision") or {}).get("outcomes"),
               trigger_k7eta=bool(med_c is not None and med_c <= PRE["k7eta_max"] + 1e-12),
               trigger_no_lip=bool(n_on >= PRE["min_onset_groups"] and lipm is not None and lipm < PRE["lip_min"] - 1e-12))
    out["fallback"] = ("design fallback A_s130 (scale 1.30, 0.60 x DM1A energy, W 100, no new tank): NOT energy-matched, needs the user's OK"
                       if (out["trigger_k7eta"] or out["trigger_no_lip"]) else None)
    return out


def summary_line(res):
    s = res.get("median") or {}
    d = res.get("decision") or {}
    return dict(run=res.get("run_id"), kind=res.get("kind"), valid=res.get("valid", res.get("pcheck_pass")), failed=res.get("failed_gates", res.get("failed")),
                verdict=res.get("verdict"), miss=s.get("miss"), Hc=s.get("Hc"), conv_Hc=s.get("conv_Hc"), conv_x=s.get("conv_x"), onset_x=s.get("onset_x"),
                W50=s.get("W50"), W80=s.get("W80"), W95=s.get("W95"), K=s.get("K"), S2=s.get("S2"), N1=s.get("N1"), Nt=s.get("Nt"),
                gain=(res.get("eligibility") or {}).get("E3", {}).get("gain"), outcomes=d.get("outcomes"), flags=d.get("physics_flags"), bar=d.get("bar"),
                G2f={k: round(v["R"], 3) for k, v in ((res.get("G2f") or {}).get("per_n") or {}).items()},
                G4=dict(core=(res.get("G4") or {}).get("kA_side_core_max"), wall=(res.get("G4") or {}).get("kA_wall_strip_max"),
                        full=(res.get("G4") or {}).get("kA_side_full_max_DFG2_rule"), inlet=(res.get("G4") or {}).get("kA_inlet_max")) if res.get("G4") else None,
                prebreak=dict(back=s.get("prebreak_back_deg"), w07=s.get("prebreak_w07")), red_instant=res.get("red_instant"),
                checks=res.get("checks"), wall_h=res.get("wall_h"), particles_max=res.get("particles_max"), path=res.get("_path"))


def selftest():
    ck = {}
    pl = GC.plan() if os.path.exists(GC.PLAN) else None
    if pl:
        cr = pl["criteria"]
        ck["plan_sha"] = GC.plan_sha_ok()
        ck["coequal"] = bool(cr["coequal"]["score3_bar"] == COEQ["score3_bar"] and cr["coequal"]["lip_min"] == COEQ["lip_min"]
                             and cr["coequal"]["conv_outcomes"] == COEQ["conv_outcomes"] and cr["coequal"]["print_ref"] == COEQ["print_ref"])
        ck["eligibility"] = bool(cr["B_eligibility"] == ELIG)
        A = cr["A_validity"]
        ck["gates"] = bool(A["G6"]["x"] == list(GATES["G6_x"]) and A["G6"]["Hc_min"] == GATES["G6_Hc"] and A["G6"]["t_rel"] == list(GATES["G6_t"])
                           and A["G4"]["kA_max"] == GATES["G4_kA"] and A["G4"]["side_core_y"] == [GATES["G4_side_y"], GATES["G4_side_y1"]]
                           and A["G4"]["side_x_max"] == GATES["G4_side_x"] and A["G4"]["inlet_x_max"] == GATES["G4_inlet_x"]
                           and A["G4"]["lip_x_max"] == GATES["G4_lip_x"] and A["G5"]["max"] == GATES["G5_max"]
                           and A["G3P"]["tol_s"] == GATES["G3P_tol"] and A["G2f"]["x"] == GATES["G2f_x"] and A["G2f"]["window_s"] == list(GATES["G2f_t_main"])
                           and A["G2f"]["floor"] == GATES["G2f_floor_0p5"] and A["G2f"]["margin"] == GATES["G2f_margin_0p5"]
                           and A["G2f"]["hi"] == GATES["G2f_hi_0p5"] and A["G2f"]["phase"] == GATES["G2f_phase_0p5"])
        ck["decision"] = bool(cr["decision"]["bar_cap"] == DEC["bar_cap"] and cr["decision"]["bar_margin"] == DEC["bar_margin"]
                              and cr["decision"]["target_band"] == DEC["target_band"] and cr["decision"]["plunge_groups"] == DEC["plunge_groups"])
        G = cr["groups"]
        ck["group"] = bool(pl["records"]["group_window_s"] == list(GC.GROUP_WIN) and G["scan_x"] == list(GROUP["scan_x"])
                           and G["onset_x"] == list(GROUP["onset_x"]) and G["Nt_x"] == list(GROUP["Nt_x"]) and G["face_edge_x"] == GROUP["face_edge_x"])
        pc = cr["pcheck"]
        ck["pcheck_rule"] = bool(pc["still_diff_max_m"] == GATES["pc_still_diff_max"] and pc["wave_ratio"] == list(GATES["pc_wave_ratio"]))
        q = cr["coequal"]["print_like_instant"]
        ck["coequal_pl"] = bool(q["cap"] == COEQ_PL["cap"] and q["margin"] == COEQ_PL["margin"] and q["min_groups"] == COEQ_PL["min_groups"]
                                and q["xwin_rel_m"] == list(COEQ_PL["xwin_rel"]) and q["ymax_m"] == COEQ_PL["ymax"]
                                and sorted(q["references"]) == sorted(PL_REFS) and "3b" in cr["coequal"]["progress_rule"])
        ck["best_runs_listed"] = bool(sorted(cr["decision"]["best_valid_runs"]) == sorted(BEST_RUNS))
    else:
        ck["plan_present"] = False
    ck["e51_frozen"] = GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py") == E51_SHA
    # synthetic: harmonic fit referenced to t_f 48 s returns the table convention; the centre-row ruler on a known profile
    t = np.arange(32.0, 88.0, 1.0 / 24.0)
    A3 = 0.7 - 0.2j; A5 = -0.1 + 0.3j
    e = np.real(A3 * np.exp(-1j * 2 * math.pi * 3 / GC.P_S * (t - GC.T_F))) + np.real(A5 * np.exp(-1j * 2 * math.pi * 5 / GC.P_S * (t - GC.T_F))) + 0.05
    f = harmonic_fit(t, e, P=GC.P_S, ns=GC.HARMONICS, nuisance=(6, 10), tf=GC.T_F)
    ck["harmonic_fit_tf48"] = bool(abs(f["A"][3] - A3) < 1e-9 and abs(f["A"][5] - A5) < 1e-9 and abs(f["A"][4]) < 1e-9 and abs(f["mean"] - 0.05) < 1e-9)
    xs = np.arange(0.0, 300.0, 0.5)
    row = 6.0 * np.exp(-0.5 * ((xs - 145.0) / 3.0) ** 2)
    cs = centre_shape(row, xs, int(np.argmax(row)))
    w07_exact = 2 * 3.0 * math.sqrt(2 * math.log(1 / 0.7)) / 6.0
    ck["centre_shape"] = bool(cs and abs(cs["w07"] - w07_exact) < 0.02 and cs["back_deg"] > 0)
    ck["kp"] = bool(abs(GC.kp() - 0.087313) < 1e-5)
    ck["G6_Hc_rule"] = bool(abs(GATES["G6_Hc"] - round(0.68 * 8.635368, 2)) < 1e-9)
    ck["G4_core_is_sd0_to_W_minus_taper"] = bool(GATES["G4_side_y"] == 110.0 and GATES["G4_side_y1"] == 132.5)
    # synthetic: the print-like median / bar rule (DFG-S's own pv53 values give 4.36; bar_pl = min(2.8, 4.36 - 0.5) = 2.8)
    m_, _v = pl_median_of_pv53(dict(periods=[dict(conv_print=dict(miss=v)) for v in COEQ_PL["DFGS_measured"]]))
    ck["pl_median_rule"] = bool(abs(m_ - COEQ_PL["DFGS_median"]) < 1e-9 and min(COEQ_PL["cap"], m_ - COEQ_PL["margin"]) == 2.8
                                and pl_median_of_pv53(dict(periods=[dict(conv_print=dict(miss=1.0))]))[0] is None)
    out = dict(ok=all(v for v in ck.values() if isinstance(v, bool)), checks=ck)
    print(json.dumps(out))
    return out["ok"]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "selftest":
        sys.exit(0 if selftest() else 1)
    if a[0] == "plrefs":
        print(json.dumps(GC.clean(pl_refs()), ensure_ascii=False)); return
    if a[0] == "dfgbe":
        print(json.dumps(GC.clean(dfgbe_read(a[1] if len(a) > 1 else None)), ensure_ascii=False)); return
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    if a[0] == "pcheck":
        r = pcheck(a[1], opt.get("out"))
        print(json.dumps(GC.clean(summary_line(r)), ensure_ascii=False))
    elif a[0] == "judge":
        r = judge(a[1], opt.get("out"))
        print(json.dumps(GC.clean(summary_line(r)), ensure_ascii=False))
    elif a[0] == "g4split":
        print(json.dumps(GC.clean(g4split(a[1])), ensure_ascii=False))
    elif a[0] == "coequal":
        r = coequal(a[1], opt.get("pv"), opt.get("out"), opt.get("judge"))
        print(json.dumps(GC.clean(dict(run=r["run_id"], progress=r["progress"], verdict=r["verdict"], print_view_ok=r["criterion_1_print_view"]["ok"],
                                       print_match=r["criterion_2_print_ruler"]["print_match"], score3=r["criterion_2_print_ruler"]["median_best_score3"],
                                       lip=r["criterion_2_print_ruler"]["median_best_lip"], convergence=r["criterion_3_convergence"]["outcomes"],
                                       miss=r["criterion_3_convergence"]["core_miss_median"],
                                       pl_ok=r["criterion_3b_convergence_at_print_like"]["ok"],
                                       pl_miss=r["criterion_3b_convergence_at_print_like"]["pl_miss_median"],
                                       bar_pl=r["criterion_3b_convergence_at_print_like"]["bar_pl"],
                                       same_instant=r["criterion_3b_convergence_at_print_like"]["same_instant_new_best"],
                                       prebreak=r["criterion_2_print_ruler"]["prebreak_report"], path=r["_path"])), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
