# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3: reading of the 0.5 m run under the FROZEN plan rules, per group of the period P = 28 s (the DFG-2B judge with the
round-2 registrations), and the CO-EQUAL verdict (print view + print ruler + convergence at the judge's instant AND at the most print-like
instant + Hc not lower) after pv53 (py -3.10 -B; numpy, scipy). 2026-10-18 written new (Claude) by adapting flip52b/g52b_ana.py (DFG-2B /
DFG-2B-E, FROZEN, not edited) and the 3b rule of flip52s2/g52s2_ana.py (DFG-S-E140, not edited). Read only on every run folder; writes only
<run>/g52b2/ and the pv53 alias <run>/g52/judge_DFG.json (or Unity/Build/FLIP52B2/_scratch given with --out, for tests). Imports READ ONLY:
flip51/e51_metrics (frozen ruler), flip52/g52_ana (generic readers: Blocks, records, still offset, r6, harmonic fit, the r2 / r4 lip detector of
AM-DFG1, G5), flip53/pv53 (only for the fallback when pv53's own json is missing).

Definitions (plan_DFGB3_frozen.json; numbers in GROUP / GATES / ELIG / DEC / COEQ / COEQ_PL / COEQ_HC below, compared with the plan by
`selftest`); everything as DFG-2B except the items marked R2 (round-2 registrations, frozen before any FLIP52B2 run):
  eta0      the run's online still offset (run record info.still_offset_online: median top-surface height over x 110-340 m, t 0.5-1.5 s)
  groups    n = 1, 2, 3 with t_fn = 63 + 28 (n - 1) s; window [t_fn - 8, t_fn + 6] s.
            'onset' = the first overturning lip on the centre section r2 (AM-DFG1 lip test) at x 200-335 m in the window (= DFG-2B)
            'conv'  (R2) = the converged crest BEFORE the curl: the largest Hc of the 3x3-median hf - eta0 over x 150-300 m, |y| <= 95 m in
                    [t_fn - 8, min(t_fn + 2, t_lip1)) s, t_lip1 = the first r2 lip (same test, x 200-335 m) at t >= t_fn - 6.9 s (the G6 window
                    start: an earlier lip cannot be the converged crest's); no such lip -> [t_fn - 8, t_fn + 2] (= DFG-2B). So the plunge's
                    splash-up on the face is never taken for the converged crest. The DFG-2B 'conv' is reported beside it (conv_frozen_rule).
            'max'   = (plan E D rule, = DFG-2B) if an onset: argmax Hc in [on_f - 3 s, on_f + 1.5 s], summit in x [on_x - 60, on_x + 35] m; else 'conv'
            convergence metrics = e51 hf_metrics (rows y > 95 m NaN) at 'max'; core miss = score_vs_target; N1, Nt, c_in110, plunge flags as DFG-2B;
            reported (R2): dt_conv_to_lip = t_lip1 - t_conv, the onset on the face (x 230.25-261.75 m) / on the shelf.
  gates A   G1 table (DFGB3 G1 incl. design = DFG-2B-E's table and the intended phase offsets) + build + precheck; G2f harmonic fit per frequency
            at x 110 m, y 0.5/20/40/60/80 m over t 49-105 s, R2: against the DESIGN target (= DFG-2B-E's table at the gauges; the generator
            carries the phase calibration), ranges RELATIVE to DFG-2's measured 0.5 m realisation (= DFG-2B); G3P recurrence of the 'conv'
            summits (28 +- 1.5 s, x spread <= 20 m, Hc max/min <= 1.25); G4 kp x crest <= 0.40 from t 30 s in the inlet band (x <= 100 m) and the
            generating side band (y >= 95 m, x <= 180.25 m), no r2 lip at x < 100 m; G5 volume <= 2 %; G6 (R2 window) 'conv' at x 215-260 m,
            |y| <= 10 m, t in [t_fn - 6.9, t_fn - 0.9] s, Hc >= 5.67 m (CS1 screen prediction t_fn - 3.9 s +- 3 s, the half-width of the DFG-2B
            window; Hc floor = 0.68 x the CS1 converged crest 8.34 m, the plan E rule); run complete, 3 groups.
  eligibility E1 N1 <= 0.65, E1t Nt <= 0.75, E2 Hc('max') >= 5.0 m, E3 Hc / c_in110 >= 1.8 (medians over the groups) (= DFG-2B)
  decision  (convergence) bar = min(2.8, best valid 0.5 m median core miss - 0.5) over DF1A 3.3 and the runs valid by their own plans among X2,
            X1, DFG-2, DFG-2B, X2B', DFG-S, DFG-2B-E, DFG-S-E140 (read at analysis time); NEW_BEST_SHAPE / TARGET_BAND / JET_REGIME_SEEN /
            NO_GAIN / NOT_ELIGIBLE; physics flags PLUNGE_AT_CONVERGED / BREAKS_LATER / NO_BREAK_IN_WINDOW / ONSET_ON_FACE (>= 2 of 3 groups).
  co-equal  (after pv53) PROGRESS iff ALL of
              (1) the Unity print view was rendered at the most print-like instant (pv53),
              (2) the print match is ok by the AM-DFG2 rule (median best-instant score3 <= 0.9485 and median best-instant lip >= 0.20),
              (3a) the convergence decision at the judge's 'max' instants is NEW_BEST_SHAPE or TARGET_BAND (valid),
              (3b) convergence AT THE MOST PRINT-LIKE INSTANT: the median over the groups of pv53's periods[].conv_print.miss (e51 core miss at
                   pv53's best frame, xwin [x_c - 60, x_c + 35] m, rows y > 65 m NaN: the measure that gave DFG-2B-E 2.16 / 2.27 / 2.37) <=
                   bar_pl = min(2.8, DFG-2B-E's median 2.27 - 0.5 = 1.77 ('clearly below DFG-2B-E'), best valid earlier print-like median - 0.5),
              (3c) Hc not lower than DFG-2B-E: median 'conv' Hc >= 8.37 - 0.18 m and median print-like Hc (pv53 conv_print.Hc) >= 6.81 - 0.18 m
                   (0.18 m = half DFG-2B-E's group-to-group range of the converged Hc [measured]).
            Reported: PL_CLEARLY_BETTER_THAN_DFGB2E (3b miss <= 1.77), SAME_INSTANT_NEW_BEST (3b miss <= the convergence bar), PRINT_BETTER_THAN_DM1A,
            the recomputed print-like miss with the judge's eta0. A run without the print-view package or its Unity render is INCOMPLETE,
            never progress. Every judge / verdict carries the Q84 energy statement (equal spectral energy; in-tank power ratio).
usage:
  py -3.10 -B g52b2_ana.py judge <run_dir> [--out=<dir>]          -> <run>/g52b2/judge_DFGB3.json (+ <run>/g52/judge_DFG.json for pv53)
                                   [--test-any-set --out=<_scratch dir>]  tests: another set's run (e.g. DFG-2B-E) read with the DFGB3 rules
  py -3.10 -B g52b2_ana.py coequal <run_dir> [--pv=<pv53 json>] [--out=<dir> --judge=<json> (tests)]  -> <run>/g52b2/coequal_DFGB3.json
  py -3.10 -B g52b2_ana.py plrefs                                 the print-like-instant references and bar_pl (read only; json to stdout)
  py -3.10 -B g52b2_ana.py selftest                               frozen numbers vs the plan, synthetic checks (writes nothing)
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, math, glob, time, warnings

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
from scipy import ndimage as ndi      # noqa: E402
import g52b2_common as GC             # noqa: E402
for _p in (GC.TOOLS51, GC.TOOLS52):
    if _p not in sys.path:
        sys.path.append(_p)
import e51_metrics as EM              # noqa: E402  frozen ruler (read only)
import g52_ana as GA52                # noqa: E402  generic readers (read only)

FPS = 24.0
E51_SHA = "91a2f0417f6f979cd1649e5bd0fc007d558722b005ac92142454c87be658e8ff"
PV53 = GC.REPO + "/Tools/GWWaveGen/flip53/pv53.py"
PV53_OUT = GC.REPO + "/Unity/Build/FLIP53/pv53"
GROUP = dict(win=GC.GROUP_WIN, conv_end=2.0, scan_x=GC.SCAN_X, ymask=GC.INTERIOR_Y, onset_x=(200.0, 335.0), onset_back_s=3.0, onset_fwd_s=1.5,
             onset_xwin=(-60.0, 35.0), Nt_half=14.0, Nt_excl=3.5, Nt_x=(150.0, 275.0), plunge_dt=(-1.0, 4.0), plunge_dx=30.0,
             conv_lip_from_rel=-6.9, face_x=(GC.X_FOOT - 5.0, GC.X_EDGE + 10.0))
N1DEF = dict(win_m=15.0, x=[110.0, 340.0], ymax=90.0, rmax=100.0, rex_Hc=4.0)
GATES = dict(G2f_x=110.0, G2f_y=list(GC.GAUGE_Y), G2f_nuisance=(6, 10), G2f_t_main=(GC.T_F - 14.0, GC.T_F + 42.0),
             G2f_phase_0p5=0.35, G2f_floor_0p5=0.60, G2f_margin_0p5=0.10, G2f_hi_0p5=1.12,
             G2f_fallback_0p5={3: (0.85, 1.12), 4: (0.85, 1.12), 5: (0.80, 1.12)},
             G3P_P=GC.P_S, G3P_tol=1.5, G3P_xspread=20.0, G3P_Hc_ratio=1.25,
             G4_kA=0.40, G4_t0=30.0, G4_inlet_x=GC.IN_X1, G4_side_y=GC.SD0, G4_side_x=GC.SD_GEN, G4_lip_x=100.0,
             G5_max=0.02, G6_x=(215.0, 260.0), G6_y=10.0, G6_t=(-6.9, -0.9), G6_Hc=5.67)
G2F_RULE = ("per frequency n: R_n = sum|A_fit| / sum|A_lin| at the five gauges (x 110 m, t 49-105 s, fit referenced to t_f 63 s), A_lin = the DESIGN "
            "target (= DFG-2B-E's table at the gauges; the generator table carries the phase calibration exp(-i phi_n)); pass if max(0.60, R_n(DFG-2 "
            "0.5 m measured) - 0.10) <= R_n <= 1.12 and |phase| <= 0.35 rad. DFG-2 reference: Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/"
            "judge_DFG.json G2f (n3 1.048, n4 0.973, n5 0.788). If the reference is missing: the DFG-2 frozen ranges. (= DFG-2B's rule; DFG-2B-E "
            "measured n3 0.995 / -0.061 rad, n4 0.899 / +0.279 rad, n5 0.799 / +0.514 rad)")
DFG_REF = GC.REPO + "/Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/judge_DFG.json"
ELIG = dict(N1_max=0.65, Nt_max=0.75, Hc_min=5.0, gain_min=1.8)
DEC = dict(bar_cap=2.8, bar_margin=0.5, DF1A_miss=3.3, target_band=0.5, jet_ratio=1.30, jet_groups=2, linear_crest=GC.A_SUM, plunge_groups=2)
DFGS2_RUN = GC.REPO + "/Unity/Build/FLIP52S2/runs/DFGS2E_step3h6_xf145_W140_dp0p5"
BEST_RUNS = {"X2": dict(judge=GC.REPO + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/e51/judge_E05.json"),
             "X1": dict(judge=GC.REPO + "/Unity/Build/FLIP51/runs/S51X1_D19B_T7_l60d15_dp0p5/e51/judge_E05.json"),
             "DFG2": dict(judge=GC.REPO + "/Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/judge_DFG.json"),
             "DFG2B": dict(judge=GC.REPO + "/Unity/Build/FLIP52B/runs/DFG2B_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json"),
             "X2B": dict(judge=GC.REPO + "/Unity/Build/FLIP51/runs/S51X2B_D19B_T7_g60s28_xf275_dp0p5/e51/judge_E05.json",
                         valid_file=GC.REPO + "/Unity/Build/FLIP51/runs/S51X2B_D19B_T7_g60s28_xf275_dp0p5/x2b/judge_X2B.json", valid_key="valid_x2b"),
             "DFGS": dict(judge=GC.REPO + "/Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/g52s/judge_DFGS.json"),
             "DFGB2E": dict(judge=GC.DFGBE_JUDGE),
             "DFGS2E": dict(judge=DFGS2_RUN + "/g52s2/judge_DFGS2.json")}
COEQ = dict(score3_bar=0.9485, score3_DM1A_median=0.6485, tol=0.30, lip_min=0.20, conv_outcomes=["NEW_BEST_SHAPE", "TARGET_BAND"],
            print_ref=dict(back_deg_07_09=31.3, back_band=[29.0, 38.0], width07=1.32, width07_band=[1.02, 1.42], lip=0.35, chord_deg=64.3, hood=0.186),
            source="AM-DFG2 / AM-DFG2a (Unity/Build/FLIP52/plan/amendments.jsonl) applied unchanged (as DFG-2B / DFG-S-E140); pv53 rule")
PL_REFS = {"DFGS": dict(pv53=PV53_OUT + "/DFGS_step3h6_xf145_dp0p5/pv53_DFGS_step3h6_xf145_dp0p5.json", judge=BEST_RUNS["DFGS"]["judge"]),
           "DFGB2E": dict(pv53=GC.DFGBE_PV53, judge=GC.DFGBE_JUDGE),
           "DFG2": dict(pv53=PV53_OUT + "/DFG2_flat20_P28_dp0p5/pv53_DFG2_flat20_P28_dp0p5.json", judge=BEST_RUNS["DFG2"]["judge"]),
           "X2": dict(pv53=PV53_OUT + "/S51X2_D19B_T7_g60s28_dp0p5/pv53_S51X2_D19B_T7_g60s28_dp0p5.json", judge=BEST_RUNS["X2"]["judge"]),
           "X1": dict(pv53=PV53_OUT + "/S51X1_D19B_T7_l60d15_dp0p5/pv53_S51X1_D19B_T7_l60d15_dp0p5.json", judge=BEST_RUNS["X1"]["judge"]),
           "X2B": dict(pv53=PV53_OUT + "/S51X2B_D19B_T7_g60s28_xf275_dp0p5/pv53_S51X2B_D19B_T7_g60s28_xf275_dp0p5.json",
                       judge=BEST_RUNS["X2B"]["judge"], valid_file=BEST_RUNS["X2B"]["valid_file"], valid_key="valid_x2b"),
           "DFGS2E": dict(pv53=PV53_OUT + "/DFGS2E_step3h6_xf145_W140_dp0p5/pv53_DFGS2E_step3h6_xf145_W140_dp0p5.json", judge=BEST_RUNS["DFGS2E"]["judge"])}
# R2 co-requirement 3b (frozen before any FLIP52B2 run): DFG-2B-E converged at t_fn - 4.0 .. -3.4 s (miss 0.04) but curled ~2.2-2.4 s later at
# x 259-267 m where its crest had dropped / widened: print-like miss 2.16 / 2.27 / 2.37 (median 2.271672) [measured, pv53 conv_print]
COEQ_PL = dict(cap=2.8, margin=0.5, min_groups=2, xwin_rel=(-60.0, 35.0), ymax_pv53=65.0, round2_ref="DFGB2E",
               DFGB2E_measured=[2.158116, 2.271672, 2.373844], DFGB2E_median=2.271672, DM1A_best_report=6.4673,
               rule="median over the groups of pv53's periods[].conv_print.miss (e51 core miss at pv53's most print-like frame of each group, xwin [x_c - 60, "
                    "x_c + 35] m, rows y > 65 m NaN; >= 2 groups) <= bar_pl = min(2.8, DFG-2B-E's print-like median 2.27 - 0.5 (the round-2 reference: "
                    "'clearly below DFG-2B-E', its validity notwithstanding), best print-like median of the earlier runs valid by their own plans - 0.5); "
                    "earlier values from the pv53 jsons read at analysis time (DFG-2B-E: the frozen 2.271672 if its json is unreadable)")
COEQ_HC = dict(tol_m=0.18, DFGB2E_conv_Hc_median=8.366235, DFGB2E_pl_Hc_median=6.81371, DFGB2E_conv_Hc=[8.099553, 8.453778, 8.366235],
               rule="median 'conv' Hc >= DFG-2B-E's 8.366 m - 0.18 and median print-like Hc (pv53 conv_print.Hc) >= DFG-2B-E's 6.814 m - 0.18; 0.18 m = half "
                    "DFG-2B-E's group-to-group range of the converged Hc (8.10-8.45 m) [measured / chosen]")
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


def foci(cfg):
    a = cfg.get("analysis") or {}
    return [float(v) for v in (a.get("foci_s") or GC.FOCI)]


# ====================================================================== the per-frame pass (= DFG-2B)
def pass_frames(H, eta0, t_lo, t_hi, kp):
    fr = [f for f in H.frames() if t_lo - 1e-9 <= (f - 1) / FPS <= t_hi + 1e-9]
    out = dict(f=[], t=[], Hc=[], x=[], y=[], Hn=[], xn=[], c110=[], kA_in=[], kA_sd=[], g2=[], xc0=[], ec0=[])
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
            inl = np.zeros(e.shape, bool); inl[:, xs <= GATES["G4_inlet_x"] + 1e-9] = True
            sd = np.zeros(e.shape, bool); sd[np.ix_(yh >= GATES["G4_side_y"] - 1e-9, xs <= GATES["G4_side_x"] + 1e-9)] = True
            i0 = int(np.clip(np.searchsorted(xs, 110.0) - 1, 0, len(xs) - 2)); w110 = (110.0 - xs[i0]) / (xs[i0 + 1] - xs[i0])
            cx = (xs >= 150.0) & (xs <= 335.0)
        for msk, kk in ((scan, ("Hc", "x", "y")), (ntr, ("Hn", "xn", None))):
            v = np.where(msk, e, np.nan)
            if np.isfinite(v).any():
                j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
                out[kk[0]].append(float(v[iy, ix])); out[kk[1]].append(float(xs[ix]))
                if kk[2]:
                    out[kk[2]].append(float(yh[iy]))
            else:
                out[kk[0]].append(np.nan); out[kk[1]].append(np.nan)
                if kk[2]:
                    out[kk[2]].append(np.nan)
        line = (1 - w110) * e[:, i0] + w110 * e[:, i0 + 1]
        out["c110"].append(float(np.nanmax(np.where(rowin, line, np.nan))) if np.isfinite(line[rowin]).any() else np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            out["kA_in"].append(float(kp * np.nanmax(np.where(inl, e, np.nan))))
            out["kA_sd"].append(float(kp * np.nanmax(np.where(sd, e, np.nan))))
        r0 = np.where(cx, e[0], np.nan)
        if np.isfinite(r0).any():
            j0 = int(np.nanargmax(r0)); out["xc0"].append(float(xs[j0])); out["ec0"].append(float(r0[j0]))
        else:
            out["xc0"].append(np.nan); out["ec0"].append(np.nan)
        out["g2"].append([interp2(e, xs, yh, GATES["G2f_x"], y) for y in GATES["G2f_y"]])
        out["f"].append(int(f)); out["t"].append((f - 1) / FPS)
    o = {k: np.asarray(v, float) for k, v in out.items()}
    o["f"] = o["f"].astype(int)
    return o


# ====================================================================== metrics of one frame (= DFG-2B)
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


# ====================================================================== R2: the converged crest before the curl
def pick_conv(t, Hc, tfn, lips_t):
    """index into (t, Hc) of 'conv': the largest Hc in [t_fn - 8, min(t_fn + 2, t_lip1)), t_lip1 = the first lip time >= t_fn - 6.9 s; no such
    lip (or no frame before it) -> the DFG-2B window [t_fn - 8, t_fn + 2]. Returns (index, rule text, t_lip1)."""
    a = tfn + GROUP["win"][0]
    lip1 = next((tl for tl in sorted(lips_t) if tl >= tfn + GROUP["conv_lip_from_rel"] - 1e-9), None)
    end = tfn + GROUP["conv_end"]
    rule = "DFG-2B window [t_fn - 8, t_fn + 2] (no r2 lip at t >= t_fn - 6.9 s)"
    if lip1 is not None and lip1 < end + 1e-9:
        sel = (t >= a - 1e-9) & (t < lip1 - 1e-9) & np.isfinite(Hc)
        if sel.any():
            idx = np.where(sel)[0]
            return int(idx[np.argmax(Hc[idx])]), "pre-lip window [t_fn - 8, t_lip1 = %.3f s)" % lip1, lip1
        rule = "DFG-2B window (no frame before the first lip at %.3f s)" % lip1
    sel = (t >= a - 1e-9) & (t <= end + 1e-9) & np.isfinite(Hc)
    if not sel.any():
        return None, "no hf frames in the window", lip1
    idx = np.where(sel)[0]
    return int(idx[np.argmax(Hc[idx])]), rule, lip1


# ====================================================================== groups
def group_rows(rd, H, R2, R4, PF, eta0, t_end, fo):
    rows = []
    avail = set(H.frames())
    for n, tfn in enumerate(fo, 1):
        a, b = tfn + GROUP["win"][0], tfn + GROUP["win"][1]
        row = dict(n=n, t_fn=tfn, window=[a, b])
        if b > t_end + 1e-9:
            row.update(complete=False, why="window beyond the record end %.2f s" % t_end); rows.append(row); continue
        selw = (PF["t"] >= a - 1e-9) & (PF["t"] <= b + 1e-9)
        fw = [int(f) for f in PF["f"][selw]]
        lips = r2_lips(R2, eta0, fw, GROUP["onset_x"][0], GROUP["onset_x"][1])
        lips_t = [(f_ - 1) / FPS for f_, _ in lips]
        i, rule, lip1 = pick_conv(PF["t"], PF["Hc"], tfn, lips_t)
        if i is None:
            row.update(complete=False, why="no hf frames in the window"); rows.append(row); continue
        conv = dict(f=int(PF["f"][i]), t=float(PF["t"][i]), Hc=float(PF["Hc"][i]), x=float(PF["x"][i]), y=float(PF["y"][i]), rule=rule)
        sel0 = (PF["t"] >= a - 1e-9) & (PF["t"] <= tfn + GROUP["conv_end"] + 1e-9) & np.isfinite(PF["Hc"])
        if sel0.any():
            i0 = int(np.where(sel0)[0][np.argmax(PF["Hc"][sel0])])
            row["conv_frozen_rule"] = dict(f=int(PF["f"][i0]), t=float(PF["t"][i0]), Hc=float(PF["Hc"][i0]), x=float(PF["x"][i0]), y=float(PF["y"][i0]),
                                           rule="DFG-2B: largest Hc in [t_fn - 8, t_fn + 2] (report)")
        row.update(complete=True, conv=conv)
        row["lip1"] = dict(t=lip1, x=next((x_ for (f_, x_) in lips if abs((f_ - 1) / FPS - lip1) < 1e-9), None)) if lip1 is not None else None
        row["lips_first5"] = [dict(f=f_, t=(f_ - 1) / FPS, x=x_) for f_, x_ in lips[:5]]
        row["onset"] = dict(frame=lips[0][0], t=(lips[0][0] - 1) / FPS, x=lips[0][1]) if lips else None
        l4 = r4_lips(R4, eta0, [f for f in fw if f in set(R4.frames())], GROUP["onset_x"][0], GROUP["onset_x"][1], ymax=GC.INTERIOR_Y) if R4.frames() else []
        row["onset_r4"] = dict(frame=l4[0][0], t=(l4[0][0] - 1) / FPS, x=l4[0][1], y=l4[0][2]) if l4 else None
        f_use = conv["f"]; xwin = tuple(GROUP["scan_x"]); inst = "conv (no r2 onset in the window): scan max x 150-300 m, |y| <= 95 m"
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
        sw = (PF["t"] >= tfn - GROUP["Nt_half"] - 1e-9) & (PF["t"] < tfn + GROUP["Nt_half"] - 1e-9) & np.isfinite(PF["Hn"])
        far = sw & (np.abs(PF["t"] - conv["t"]) >= GROUP["Nt_excl"] - 1e-9)
        if far.any() and conv["Hc"] > 0.5:
            j = int(np.where(far)[0][np.argmax(PF["Hn"][far])])
            row["Nt"] = float(PF["Hn"][j] / conv["Hc"])
            row["Nt_at"] = dict(t=float(PF["t"][j]), x=float(PF["xn"][j]), H=float(PF["Hn"][j]), Hc_conv=conv["Hc"])
        else:
            row["Nt"] = None
        row["Nt_coverage_s"] = float(PF["t"][sw].max() - PF["t"][sw].min()) if sw.any() else 0.0
        row["c_in110"] = float(np.nanmax(PF["c110"][sw])) if (sw.any() and np.isfinite(PF["c110"][sw]).any()) else None
        row["gain_over_c_in110"] = (row["Hc"] / row["c_in110"]) if (row.get("c_in110") and row.get("Hc")) else None
        row["jet_ratio"] = row["Hc"] / DEC["linear_crest"] if row.get("Hc") else None
        on = row["onset"]
        row["plunge_at_converged"] = bool(on is not None and conv["t"] + GROUP["plunge_dt"][0] - 1e-9 <= on["t"] <= conv["t"] + GROUP["plunge_dt"][1] + 1e-9
                                          and on["x"] <= conv["x"] + GROUP["plunge_dx"] + 1e-9)
        row["breaks_later"] = bool(on is not None and not row["plunge_at_converged"])
        row["dt_conv_to_lip1_s"] = (lip1 - conv["t"]) if lip1 is not None else None
        row["onset_on_face"] = bool(on is not None and GROUP["face_x"][0] <= on["x"] <= GROUP["face_x"][1])
        row["onset_on_shelf"] = bool(on is not None and on["x"] > GROUP["face_x"][1])
        rows.append(row)
    return rows


# ====================================================================== gates
def gate_G1(rd, cfg):
    dr = cfg.get("dir") or {}
    tc = GC.TABLE_CHECK
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    bc = GC.jload(GC.BUILD_CHECK) if os.path.exists(GC.BUILD_CHECK) else {}
    run_hips = sorted(set(r.get("hip_sha256") for r in recs(rd) if r.get("hip_sha256")))
    ok_tab = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256") and dr.get("npz") and os.path.exists(dr["npz"])
                  and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    ok_build = bool(bc.get("all_ok") and run_hips and all(h == bc.get("hip_sha256") for h in run_hips))
    ok_pre = bool((cfg.get("precheck") or {}).get("ok"))
    return dict(ok=bool(ok_tab and ok_build and ok_pre), table_check=ok_tab, build_check52b2=ok_build, cfg_precheck=ok_pre,
                hip_sha_runs=[h[:16] for h in run_hips], hip_sha_build=str(bc.get("hip_sha256"))[:16])


def g2f_ranges():
    """the frozen relative rule: DFG-2's measured R_n at 0.5 m (if present) -> ranges; else the DFG-2 frozen ranges."""
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


def g2f(PF, lin, lin_table=None):
    t = PF["t"]
    tw = GATES["G2f_t_main"]
    sel = (t >= tw[0] - 1e-9) & (t <= tw[1] + 1e-9)
    rng, phmax, src, ref = g2f_ranges()
    out = dict(window=list(tw), n_frames=int(sel.sum()), per_n={}, ranges={str(k): list(v) for k, v in rng.items()}, phase_max_rad=phmax, range_source=src,
               span_s=float(t[sel].max() - t[sel].min()) if sel.any() else 0.0, rule=G2F_RULE, reference="DESIGN target (cfg dir.linear_refs.G2f_gauges)")
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
        row = dict(R=R, phase_err_rad=ph, range=list(rng[n]), ok=okn, R_DFG2_ref=(ref or {}).get(n), phi_comp_rad=GC.PHI_COMP[n])
        if lin_table:
            Alt = [complex(*lin_table["y%g" % y]["n%d" % n]) for y in GATES["G2f_y"]]
            row["phase_vs_generator_table_rad_report"] = float(np.angle(sum(a * np.conj(b) for a, b in zip(Af, Alt))))
        out["per_n"]["n%d" % n] = row
        ok = ok and okn
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


def gate_G4(PF, R2, eta0, t_end):
    t = PF["t"]
    sel = t >= GATES["G4_t0"] - 1e-9
    kin = float(np.nanmax(PF["kA_in"][sel])) if sel.any() else None
    ksd = float(np.nanmax(PF["kA_sd"][sel])) if sel.any() else None
    lips = r2_lips(R2, eta0, [int(f) for f in PF["f"][sel]], 3.0, GATES["G4_lip_x"])
    out = dict(ok=bool(kin is not None and ksd is not None and kin <= GATES["G4_kA"] and ksd <= GATES["G4_kA"] and not lips),
               kA_inlet_max=kin, kA_side_max=ksd, kA_max=GATES["G4_kA"], kp=GC.kp(), r2_lips_x_lt_100=lips[:20], n_lip_frames=len(lips),
               rule="kp x (3x3-median hf - eta0) <= 0.40 from t 30 s in the inlet band (x <= 100 m) and the generating side band (y >= 95 m, "
                    "x <= 180.25 m); no overturning lip on r2 at x < 100 m (= DFG-2B)")
    if sel.any() and np.isfinite(PF["kA_sd"][sel]).any():
        j = int(np.where(sel)[0][np.nanargmax(PF["kA_sd"][sel])])
        out["kA_side_max_at_t"] = float(PF["t"][j])
    return out


def gate_G6(rows):
    bad = []
    for r in rows:
        if not r.get("complete"):
            bad.append(dict(n=r["n"], why=r.get("why"))); continue
        c = r["conv"]
        ok = (GATES["G6_x"][0] <= c["x"] <= GATES["G6_x"][1] and abs(c["y"]) <= GATES["G6_y"] + 1e-9
              and r["t_fn"] + GATES["G6_t"][0] - 1e-9 <= c["t"] <= r["t_fn"] + GATES["G6_t"][1] + 1e-9 and c["Hc"] >= GATES["G6_Hc"])
        if not ok:
            bad.append(dict(n=r["n"], x=c["x"], y=c["y"], t=c["t"], t_fn=r["t_fn"], t_rel=c["t"] - r["t_fn"], Hc=c["Hc"]))
    return dict(ok=bool(not bad and len(rows) == 3), failing=bad,
                rule="each group's converged summit ('conv', the R2 pre-lip rule) at x 215-260 m, |y| <= 10 m, t in [t_fn - 6.9, t_fn - 0.9] s, "
                     "Hc >= 5.67 m (R2 window, registered before the run)")


# ====================================================================== judge
def common(rd, any_set=False):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = load_cfg(rd)
    cset = (cfg.get("dir") or {}).get("set")
    if cset != GC.SET and not any_set:
        raise SystemExit("run %s has set %s, not %s (not a DFGB3 run)" % (os.path.basename(rd), cset, GC.SET))
    rr = recs(rd)
    eta0, eta0_src = still_offset(rd, rr)
    H = Blocks(rd, "hf", "eta"); R2 = Blocks(rd, "r2", "sdf"); R4 = Blocks(rd, "r4", "sdf")
    frames = H.frames()
    t_end = (max(frames) - 1) / FPS if frames else 0.0
    done = max([int(r.get("f_end_done") or 0) for r in rr] or [0])
    res = dict(run_id=os.path.basename(rd), run_dir=rd, kind="0p5", plan=GC.PLAN_REL, plan_sha_ok=GC.plan_sha_ok(), tool="Tools/GWWaveGen/flip52b2/g52b2_ana.py",
               tool_sha256=GC.sha256_file(os.path.abspath(__file__)), e51_sha256=GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py"),
               e51_frozen_ok=GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py") == E51_SHA, amendments=[a.get("id") for a in GC.amendments()],
               date=time.strftime("%Y-%m-%d %H:%M:%S"), eta0=eta0, eta0_source=eta0_src, t_record_end=t_end, frames_n=len(frames),
               dp=float((cfg.get("parms") or {}).get("dp", 0.0)), set=cset)
    res["run_complete"] = dict(ok=bool(cfg and done >= int(cfg.get("f_end", 10 ** 9))), frames_done=done, f_end=cfg.get("f_end"))
    res["launches"] = [dict(f_start=r.get("f_start"), f_end_done=r.get("f_end_done"), stopped=r.get("stopped"), wall_s=r.get("wall_total_s"),
                            particles_max=r.get("particles_max"), rss_gb=r.get("rss_peak_gb")) for r in rr]
    res["wall_h"] = sum([float(r.get("wall_total_s") or 0.0) for r in rr]) / 3600.0
    PF = pass_frames(H, eta0, 25.0, t_end, GC.kp())
    lin = ((cfg.get("dir") or {}).get("linear_refs") or {})
    res["G1"] = gate_G1(rd, cfg)
    An = (lin.get("G2f_gauges") or {}).get("A_n")
    Ant = (lin.get("G2f_gauges_table") or {}).get("A_n")
    res["G2f"] = g2f(PF, An, Ant) if (An and "y%g" % GATES["G2f_y"][0] in An) else dict(ok=False, why="cfg dir.linear_refs.G2f_gauges missing")
    res["G4"] = gate_G4(PF, R2, eta0, t_end)
    res["G5"] = gate_G5(load_r6(rd))
    res["per_frame"] = dict(t=PF["t"][::4], Hc_scan=PF["Hc"][::4], x_scan=PF["x"][::4], centre_crest=PF["ec0"][::4], centre_x=PF["xc0"][::4], c110=PF["c110"][::4])
    return res, cfg, H, R2, R4, PF, eta0, t_end


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


def best_valid():
    rows = dict(DF1A=dict(miss=DEC["DF1A_miss"], valid=True, source="DF1A 0.5 m e51 'max' median core miss 3.3 [measured]"))
    for k, d in BEST_RUNS.items():
        p = d["judge"]
        if not os.path.exists(p):
            rows[k] = dict(missing=True, source=p); continue
        try:
            j = GC.jload(p)
            rows[k] = dict(miss=j.get("core_miss_median"), valid=_valid_by_own_plan(d), source=p)
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
    n_face = sum(1 for r in ok_rows if r.get("onset_on_face"))
    flags = (["PLUNGE_AT_CONVERGED"] if n_plunge >= k else []) + (["BREAKS_LATER"] if n_later >= k else []) + \
            (["NO_BREAK_IN_WINDOW"] if (len(ok_rows) - n_plunge - n_later) >= k else []) + (["ONSET_ON_FACE"] if n_face >= k else [])
    out = dict(bar=bar, best_valid_0p5=best, best_rows=rows, physics_flags=flags, n_groups_plunge_at_converged=n_plunge, n_groups_break_later=n_later,
               n_groups_onset_on_face=n_face,
               rule="plan_DFGB3_frozen decision (convergence part = the DFG-2 / DFG-2B frozen rule over the runs valid by their own plans; physics flags "
                    "report the breaker)")
    if failed:
        cls = "pipeline" if any(q in pipe for q in failed) else "physics"
        out.update(valid=False, failure_class=cls, outcomes=["INVALID"],
                   next=("PIPELINE_FAIL: the main session fixes the pipeline cause and reruns once (same setup name)" if cls == "pipeline" else
                         "PHYSICS_FAIL: report the numbers, the print view and the print ruler to the user; DFGB3 stops"))
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


def judge(rd, out_dir=None, any_set=False):
    """any_set (tests only, with out_dir in Unity/Build/FLIP52B2/_scratch): read a run of another set (e.g. DFG-2B-E) with the DFGB3 rules."""
    t0 = time.time()
    if any_set and not out_dir:
        raise SystemExit("--test-any-set needs --out=<Unity/Build/FLIP52B2/_scratch/...>")
    res, cfg, H, R2, R4, PF, eta0, t_end = common(rd, any_set=any_set)
    rows = group_rows(res["run_dir"], H, R2, R4, PF, eta0, t_end, foci(cfg))
    res["groups"] = rows
    ok_rows = [r for r in rows if r.get("complete")]
    summ = {k: med(ok_rows, k) for k in REPORT_KEYS}
    for k in ("Nt", "c_in110", "gain_over_c_in110", "jet_ratio", "h_at_pk", "dt_conv_to_lip1_s"):
        summ[k] = med(ok_rows, k)
    summ["conv_Hc"] = med([dict(v=r["conv"]["Hc"]) for r in ok_rows], "v")
    summ["conv_x"] = med([dict(v=r["conv"]["x"]) for r in ok_rows], "v")
    summ["conv_t_rel"] = med([dict(v=r["conv"]["t"] - r["t_fn"]) for r in ok_rows], "v")
    summ["conv_Hc_over_h"] = med([dict(v=r["conv"]["Hc_over_h"]) for r in ok_rows], "v")
    summ["conv_miss"] = med([dict(v=(r.get("conv_metrics") or {}).get("miss")) for r in ok_rows], "v")
    summ["onset_x"] = med([dict(v=r["onset"]["x"]) for r in ok_rows if r.get("onset")], "v")
    summ["onset_t_rel"] = med([dict(v=r["onset"]["t"] - r["t_fn"]) for r in ok_rows if r.get("onset")], "v")
    summ["W_curve"] = {fk: med([dict(v=(r.get("W_curve") or {}).get(fk)) for r in ok_rows], "v") for fk in ("%.2f" % f for f in EM.FRACS)}
    res["median"] = summ
    g = dict(run_complete=res["run_complete"], G1=res["G1"], G2f=res["G2f"], G3P=gate_G3P(rows), G4=res["G4"], G5=res["G5"], G6=gate_G6(rows),
             groups3=dict(ok=bool(len(ok_rows) == 3), n=len(ok_rows)))
    res["gates"] = g
    keys = ["run_complete", "G1", "G2f", "G3P", "G4", "G5", "G6", "groups3"]
    res["failed_gates"] = [k for k in keys if not (g.get(k) or {}).get("ok")]
    res["valid"] = not res["failed_gates"]
    Hc = summ.get("Hc"); cin = summ.get("c_in110")
    gain = (Hc / cin) if (Hc and cin) else None
    res["eligibility"] = dict(
        E1=dict(N1_median=summ.get("N1"), max=ELIG["N1_max"], ok=bool(summ.get("N1") is not None and summ["N1"] <= ELIG["N1_max"])),
        E1t=dict(Nt_median=summ.get("Nt"), max=ELIG["Nt_max"], ok=bool(summ.get("Nt") is not None and summ["Nt"] <= ELIG["Nt_max"])),
        E2=dict(Hc_median=Hc, min=ELIG["Hc_min"], ok=bool(Hc is not None and Hc >= ELIG["Hc_min"])),
        E3=dict(gain=gain, Hc_median=Hc, c_in110_median=cin, min=ELIG["gain_min"], ok=bool(gain is not None and gain >= ELIG["gain_min"])))
    tab = cfg.get("dir") or {}
    res["gains_report"] = dict(Hc_over_linear_design_crest_xf=(Hc / ((tab.get("linear_refs") or {}).get("design_crest_xf_m") or np.nan)) if Hc else None,
                               Hc_over_a_sum=(Hc / DEC["linear_crest"]) if Hc else None,
                               Hc_over_max_component=(Hc / tab["a_max_component"]) if (Hc and tab.get("a_max_component")) else None,
                               Hc_over_c_in110=gain)
    res["core_miss_median"] = summ.get("miss")
    res["energy_statement"] = (cfg.get("wave") or {}).get("energy")
    res["decision"] = decide(res)
    best = min(ok_rows, key=lambda r: r["miss"]) if ok_rows else None
    res["red_instant"] = dict(n=best["n"], frame=best["f"], t=best["t"], miss=best["miss"], Hc=best["Hc"], x=best["x_pk"], y=best["y_pk"]) if best else None
    res["elapsed_s"] = round(time.time() - t0, 1)
    od = GC.guard_out(out_dir or os.path.join(res["run_dir"], "g52b2"), allow_scratch=True)
    p = os.path.join(od, "judge_DFGB3.json")
    GC.jdump(res, p)
    res["_path"] = p.replace("\\", "/")
    # pv53 alias: pv53 treats a run whose cfg dir.set starts with 'DFG' as FLIP52 family and reads <run>/g52/judge_DFG.json (groups f, x_pk, y_pk,
    # Hc ...; decision.outcomes; median; core_miss_median; red_instant). The same content under that name; written only for a real run folder.
    if not out_dir:
        GC.jdump(dict(res, alias_of="g52b2/judge_DFGB3.json (plan DFGB3)"), GC.guard_out(os.path.join(res["run_dir"], "g52")) + "/judge_DFG.json")
    return res


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


def pl_median_of_pv53(pj):
    vals = [((p.get("conv_print") or {}).get("miss")) for p in (pj or {}).get("periods") or []]
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    return (float(np.median(vals)) if len(vals) >= COEQ_PL["min_groups"] else None), vals


def pl_refs():
    """[measured, read at analysis time] the earlier runs' median e51 miss at their most print-like instants (pv53 periods[].conv_print) and their
    validity by their own plans; bar_pl = min(cap, DFG-2B-E's median - margin, best valid earlier median - margin)."""
    rows = {}
    for k, d in PL_REFS.items():
        if not os.path.exists(d["pv53"]):
            rows[k] = dict(missing=True, source=d["pv53"]); continue
        try:
            m, vals = pl_median_of_pv53(GC.jload(d["pv53"]))
        except Exception as ex:
            rows[k] = dict(error=repr(ex)[:200], source=d["pv53"]); continue
        rows[k] = dict(pl_miss_median=m, per_group=vals, valid=_valid_by_own_plan(d), source=d["pv53"])
    r2 = rows.get(COEQ_PL["round2_ref"]) or {}
    dfgbe = r2.get("pl_miss_median") if isinstance(r2.get("pl_miss_median"), (int, float)) else COEQ_PL["DFGB2E_median"]
    vals = [r["pl_miss_median"] for r in rows.values() if r.get("valid") and isinstance(r.get("pl_miss_median"), (int, float))]
    best = min(vals) if vals else None
    bar_r2 = dfgbe - COEQ_PL["margin"]
    bar = min(COEQ_PL["cap"], bar_r2, (best - COEQ_PL["margin"]) if best is not None else COEQ_PL["cap"])
    return dict(bar_pl=bar, bar_round2=bar_r2, DFGB2E_pl_median=dfgbe, DFGB2E_pl_median_frozen=COEQ_PL["DFGB2E_median"],
                DFGB2E_read_equals_frozen=bool(abs(dfgbe - COEQ_PL["DFGB2E_median"]) < 1e-5), best_valid_pl=best, rows=rows, rule=COEQ_PL["rule"])


def conv_at_print_like(rd, P, eta0):
    """3b: pv53's own conv_print per group (primary: the measure of DFG-2B-E's 2.27); beside it a recomputation with the judge's eta0 and the
    same window / ymax 65 m (report; used only where pv53's value is missing)."""
    H = Blocks(rd, "hf", "eta")
    avail = set(H.frames())
    rows = []
    for p_ in (P or {}).get("periods") or []:
        b = p_.get("best") or {}
        cp = p_.get("conv_print") or {}
        f = b.get("frame"); xc = b.get("x_c")
        r = dict(n=p_.get("n"), frame=f, t=b.get("t"), x_c=xc, score3=b.get("score3"), lip=b.get("lip"),
                 miss=cp.get("miss") if isinstance(cp.get("miss"), (int, float)) else None, Hc=cp.get("Hc"),
                 **{k: cp.get(k) for k in ("W50", "W80", "W95", "K", "S2", "x_pk", "y_pk")}, src="pv53 conv_print")
        if f is not None and xc is not None and int(f) in avail:
            try:
                a, meta = H.get(int(f))
                bb = masked(a, meta, COEQ_PL["ymax_pv53"])
                xw = (float(xc) + COEQ_PL["xwin_rel"][0], float(xc) + COEQ_PL["xwin_rel"][1])
                m = EM.hf_metrics(bb, meta, eta0, xwin=xw)
                if m and "W50" in m:
                    miss, _ = EM.score_vs_target(m)
                    r["recomputed_judge_eta0"] = dict(miss=miss, Hc=m.get("Hc"), W50=m.get("W50"), xwin=list(xw))
            except Exception as ex:
                r["recompute_error"] = repr(ex)[:200]
        if r.get("miss") is None and (r.get("recomputed_judge_eta0") or {}).get("miss") is not None:
            r["miss"] = float(r["recomputed_judge_eta0"]["miss"]); r["Hc"] = r["recomputed_judge_eta0"]["Hc"]
            r["src"] = "recomputed (pv53 conv_print missing)"
        rows.append(r)
    vals = [q["miss"] for q in rows if isinstance(q.get("miss"), (int, float))]
    med_ = float(np.median(vals)) if len(vals) >= COEQ_PL["min_groups"] else None
    medians = {k: med([q for q in rows if q.get(k) is not None], k) for k in ("Hc", "W50", "W80", "W95", "K", "S2")}
    return dict(per_group=rows, pl_miss_median=med_, n_groups=len(vals), medians=medians)


def verdict_text(J, P, src, conv_ok, conv_oc, pm_ok, s3, lip, unity_ok, unity_why, pl_ok, plm, bar_pl, hc_ok, hc_txt, same_inst):
    """the co-equal verdict sentence (pure; tested in selftest)."""
    plt = "print-like miss %s %s bar_pl %.2f" % (("%.2f" % plm) if plm is not None else "not measured", "<=" if pl_ok else ">", bar_pl)
    if not J:
        return "INCOMPLETE (no judge)"
    if P is None:
        return "INCOMPLETE (no print-view package: pv53 %s); never progress without the print view" % src
    allc = bool(conv_ok and pm_ok and pl_ok and hc_ok)
    if allc and not unity_ok:
        return ("convergence %s, print ruler ok (score3 %.3f, lip %.2f), %s and Hc not lower, but the Unity print view is missing (%s): INCOMPLETE, "
                "not shown as progress until the render exists" % (conv_oc, s3, lip, plt, unity_why))
    if allc:
        return ("PROGRESS: convergence %s AND print match ok (median best score3 %.3f <= %.4f, lip %.2f >= %.2f) AND converged at the most print-like "
                "instant (%s) AND Hc not lower (%s)%s" % (conv_oc, s3, COEQ["score3_bar"], lip, COEQ["lip_min"], plt, hc_txt,
                                                         "; SAME_INSTANT_NEW_BEST" if same_inst else ""))
    if conv_ok and pm_ok and not pl_ok:
        return ("NOT progress: convergence %s and print match ok (score3 %.3f, lip %.2f) but the most print-like instant is not converged clearly "
                "better than DFG-2B-E (%s): the curl still comes after the converged instant" % (conv_oc, s3, lip, plt))
    if conv_ok and pm_ok and pl_ok and not hc_ok:
        return "NOT progress: convergence, print match and %s hold but Hc is lower than DFG-2B-E's (%s)" % (plt, hc_txt)
    if conv_ok:
        return "converged, print match worse than DM1A (score3 %s, lip %s; %s): NOT a new shape reference, not shown as progress" % (s3, lip, plt)
    if pm_ok:
        return "print match ok (score3 %.3f, lip %.2f) but the convergence decision does not improve (%s; %s): reported side by side" % (s3, lip, conv_oc, plt)
    return "neither: convergence %s, print match %s (score3 %s, lip %s; %s)" % (conv_oc, "worse than DM1A" if s3 is not None else "not measured", s3, lip, plt)


def coequal(rd, pv=None, out_dir=None, judge_path=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    jp = judge_path or os.path.join(rd, "g52b2", "judge_DFGB3.json")       # judge_path: tests only (with out_dir in the _scratch)
    J = GC.jload(jp) if os.path.exists(jp) else None
    P, ppath, src = pv53_result(rd, pv)
    out = dict(run_id=os.path.basename(rd), date=time.strftime("%Y-%m-%d %H:%M:%S"), plan=GC.PLAN_REL, rule=COEQ, rule_pl=COEQ_PL, rule_hc=COEQ_HC,
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
    refs = pl_refs()
    plc = conv_at_print_like(rd, P, float((J or {}).get("eta0") or 0.0)) if (P and J) else dict(per_group=[], pl_miss_median=None, n_groups=0, medians={})
    plm = plc.get("pl_miss_median")
    pl_ok = bool(plm is not None and plm <= refs["bar_pl"] + 1e-9)
    conv_bar = ((J or {}).get("decision") or {}).get("bar")
    same_inst = bool(plm is not None and conv_bar is not None and plm <= conv_bar + 1e-9)
    hc_c = ((J or {}).get("median") or {}).get("conv_Hc")
    hc_p = (plc.get("medians") or {}).get("Hc")
    hc_ok = bool(hc_c is not None and hc_p is not None and hc_c >= COEQ_HC["DFGB2E_conv_Hc_median"] - COEQ_HC["tol_m"] - 1e-9
                 and hc_p >= COEQ_HC["DFGB2E_pl_Hc_median"] - COEQ_HC["tol_m"] - 1e-9)
    hc_txt = "conv Hc %s vs >= %.2f, print-like Hc %s vs >= %.2f" % (("%.2f" % hc_c) if hc_c is not None else "-", COEQ_HC["DFGB2E_conv_Hc_median"] - COEQ_HC["tol_m"],
                                                                      ("%.2f" % hc_p) if hc_p is not None else "-", COEQ_HC["DFGB2E_pl_Hc_median"] - COEQ_HC["tol_m"])
    out.update(
        criterion_1_print_view=dict(ok=bool(unity.get("ok")), why=unity.get("why"), stills={k: v for k, v in (unity.get("print_like") or {}).items()
                                                                                             if isinstance(v, str) and (v.endswith(".png") or v.endswith(".mp4") or v.endswith(".jpg"))},
                                    report_png=(P or {}).get("report_png"), most_print_like=(P or {}).get("most_print_like")),
        criterion_2_print_ruler=dict(print_match=("ok" if pm_ok else ("worse than DM1A" if s3 is not None else "not measured")), median_best_score3=s3,
                                     median_best_lip=lip, bar_score3=COEQ["score3_bar"], lip_min=COEQ["lip_min"], per_group=per, medians=ruler,
                                     print_ref=COEQ["print_ref"], DFGB2E_report=dict(score3=[0.557, 0.770, 0.752], lip_range=[0.25, 0.31], back_deg=[17, 18], w07=[1.53, 1.57]),
                                     better_than_DM1A=bool(s3 is not None and lip is not None and s3 < COEQ["score3_DM1A_median"] and lip >= COEQ["lip_min"])),
        criterion_3_convergence=dict(valid=(J or {}).get("valid"), failed=(J or {}).get("failed_gates"), outcomes=conv_oc, improves=conv_ok,
                                     core_miss_median=(J or {}).get("core_miss_median"), bar=conv_bar,
                                     median={k: ((J or {}).get("median") or {}).get(k) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "N1", "Nt", "conv_Hc",
                                                                                                 "conv_x", "conv_t_rel", "conv_Hc_over_h", "conv_miss",
                                                                                                 "onset_x", "onset_t_rel", "dt_conv_to_lip1_s")},
                                     physics_flags=((J or {}).get("decision") or {}).get("physics_flags")),
        criterion_3b_convergence_at_print_like=dict(ok=pl_ok, pl_miss_median=plm, bar_pl=refs["bar_pl"], bar_round2=refs["bar_round2"],
                                                    DFGB2E_pl_median=refs["DFGB2E_pl_median"], best_valid_earlier_pl=refs["best_valid_pl"],
                                                    pl_clearly_better_than_DFGB2E=bool(plm is not None and plm <= refs["bar_round2"] + 1e-9),
                                                    n_groups=plc.get("n_groups"), per_group=plc.get("per_group"), medians=plc.get("medians"),
                                                    same_instant_new_best=same_inst, conv_bar=conv_bar, refs=refs["rows"], rule=COEQ_PL["rule"]),
        criterion_3c_hc_not_lower=dict(ok=hc_ok, conv_Hc_median=hc_c, print_like_Hc_median=hc_p, text=hc_txt, rule=COEQ_HC["rule"]))
    prog = bool(conv_ok and pm_ok and pl_ok and hc_ok and P is not None and bool(unity.get("ok")))
    verdict = verdict_text(J, P, src, conv_ok, conv_oc, pm_ok, s3, lip, bool(unity.get("ok")), unity.get("why"), pl_ok, plm, refs["bar_pl"], hc_ok, hc_txt,
                           same_inst)
    en = out.get("energy_statement") or {}
    if en.get("statement"):
        it = en.get("in_tank") or {}
        verdict += (" | equal spectral energy (Q84): sum a^2 %.6f m^2 = DM1A's; in-tank inlet variance %s x DM1A, interior power %s x DM1A"
                    % (float(en.get("sum_a2_m2") or float("nan")), _r2(it.get("inlet_variance_over_DM1A")), _r2(it.get("interior_power_over_DM1A"))))
    out["progress"] = prog
    out["verdict"] = verdict
    od = GC.guard_out(out_dir or os.path.join(rd, "g52b2"), allow_scratch=True)
    GC.jdump(out, os.path.join(od, "coequal_DFGB3.json"))
    out["_path"] = os.path.join(od, "coequal_DFGB3.json").replace("\\", "/")
    return out


def _r2(v):
    return ("%.3f" % v) if isinstance(v, (int, float)) else "-"


def summary_line(res):
    s = res.get("median") or {}
    d = res.get("decision") or {}
    G2 = res.get("G2f") or {}
    return dict(run=res.get("run_id"), kind=res.get("kind"), valid=res.get("valid"), failed=res.get("failed_gates"),
                miss=s.get("miss"), Hc=s.get("Hc"), conv_Hc=s.get("conv_Hc"), conv_x=s.get("conv_x"), conv_t_rel=s.get("conv_t_rel"), onset_x=s.get("onset_x"),
                dt_lip=s.get("dt_conv_to_lip1_s"), W50=s.get("W50"), W80=s.get("W80"), W95=s.get("W95"), K=s.get("K"), S2=s.get("S2"), N1=s.get("N1"),
                Nt=s.get("Nt"), gain=(res.get("eligibility") or {}).get("E3", {}).get("gain"), outcomes=d.get("outcomes"), flags=d.get("physics_flags"),
                bar=d.get("bar"), G2f={k: [round(v["R"], 3), round(v["phase_err_rad"], 3)] for k, v in (G2.get("per_n") or {}).items()},
                G4=dict(inlet=(res.get("G4") or {}).get("kA_inlet_max"), side=(res.get("G4") or {}).get("kA_side_max")),
                G6=((res.get("gates") or {}).get("G6") or {}).get("failing"), red_instant=res.get("red_instant"),
                energy=((res.get("energy_statement") or {}).get("in_tank") or {}).get("interior_power_over_DM1A"), path=res.get("_path"))


def selftest():
    pl = GC.plan()
    cr = pl["criteria"]
    ck = {}
    ck["coequal"] = bool(cr["coequal"]["score3_bar"] == COEQ["score3_bar"] and cr["coequal"]["lip_min"] == COEQ["lip_min"]
                         and cr["coequal"]["conv_outcomes"] == COEQ["conv_outcomes"])
    PLp = cr["coequal"]["print_like_instant"]
    ck["coequal_3b"] = bool(PLp["cap"] == COEQ_PL["cap"] and PLp["margin"] == COEQ_PL["margin"] and PLp["min_groups"] == COEQ_PL["min_groups"]
                            and PLp["DFGB2E_median"] == COEQ_PL["DFGB2E_median"] and PLp["ymax_pv53_m"] == COEQ_PL["ymax_pv53"])
    HCp = cr["coequal"]["hc_not_lower"]
    ck["coequal_3c"] = bool(HCp["tol_m"] == COEQ_HC["tol_m"] and HCp["DFGB2E_conv_Hc_median"] == COEQ_HC["DFGB2E_conv_Hc_median"]
                            and HCp["DFGB2E_pl_Hc_median"] == COEQ_HC["DFGB2E_pl_Hc_median"])
    ck["eligibility"] = bool(cr["B_eligibility"] == ELIG)
    G6p = cr["A_validity"]["G6"]
    ck["gates"] = bool(G6p["x"] == list(GATES["G6_x"]) and G6p["t_rel"] == list(GATES["G6_t"]) and G6p["Hc_min"] == GATES["G6_Hc"]
                       and G6p["y_abs_max"] == GATES["G6_y"] and cr["A_validity"]["G4"]["kA_max"] == GATES["G4_kA"]
                       and cr["A_validity"]["G5"]["max"] == GATES["G5_max"] and cr["A_validity"]["G3P"]["tol_s"] == GATES["G3P_tol"]
                       and cr["A_validity"]["G2f"]["window_main_s"] == list(GATES["G2f_t_main"]) and cr["A_validity"]["G2f"]["phase_0p5"] == GATES["G2f_phase_0p5"])
    ck["decision"] = bool(cr["decision"]["bar_cap"] == DEC["bar_cap"] and cr["decision"]["bar_margin"] == DEC["bar_margin"]
                          and sorted(cr["decision"]["best_valid_runs"]) == sorted(BEST_RUNS))
    ck["group"] = bool(pl["records"]["group_window_s"] == list(GC.GROUP_WIN) and cr["groups"]["Nt_x"] == list(GROUP["Nt_x"])
                       and cr["groups"]["conv_lip_from_rel_s"] == GROUP["conv_lip_from_rel"])
    ck["e51_frozen"] = GC.sha256_file(GC.TOOLS51 + "/e51_metrics.py") == E51_SHA
    # synthetic: the R2 'conv' rule
    t = np.arange(50.0, 70.0, 1.0 / 24.0)
    Hc = 8.0 - 0.3 * (t - 59.0) ** 2
    Hc = np.where((t > 61.5) & (t < 62.5), 9.5, Hc)                 # a splash-up after the lip
    i1, r1, l1 = pick_conv(t, Hc, 63.0, [60.0, 61.0])               # first lip 60.0 >= 63 - 6.9 = 56.1
    i2, r2_, l2 = pick_conv(t, Hc, 63.0, [])                        # no lip: the DFG-2B window takes the splash-up
    i3, r3, l3 = pick_conv(t, Hc, 63.0, [55.0, 60.5])               # a lip before t_fn - 6.9 is ignored
    ck["synthetic_conv_rule"] = bool(abs(t[i1] - 59.0) < 1e-9 and Hc[i2] == 9.5 and abs(t[i3] - 59.0) < 1e-9 and l3 == 60.5 and l1 == 60.0)
    # synthetic: the verdict ladder
    vt = verdict_text({"valid": True}, {"p": 1}, "pv53 json", True, ["NEW_BEST_SHAPE"], True, 0.7, 0.3, True, None, True, 1.5, 1.77, True, "x", False)
    vn = verdict_text({"valid": True}, {"p": 1}, "pv53 json", True, ["NEW_BEST_SHAPE"], True, 0.7, 0.3, True, None, False, 2.2, 1.77, True, "x", False)
    vu = verdict_text({"valid": True}, {"p": 1}, "pv53 json", True, ["NEW_BEST_SHAPE"], True, 0.7, 0.3, False, "no render", True, 1.5, 1.77, True, "x", False)
    vh = verdict_text({"valid": True}, {"p": 1}, "pv53 json", True, ["NEW_BEST_SHAPE"], True, 0.7, 0.3, True, None, True, 1.5, 1.77, False, "x", False)
    ck["synthetic_verdicts"] = bool(vt.startswith("PROGRESS") and vn.startswith("NOT progress") and "INCOMPLETE" in vu and vh.startswith("NOT progress"))
    refs = pl_refs()
    ck["pl_refs_DFGB2E_frozen"] = bool(refs["DFGB2E_read_equals_frozen"] and abs(refs["bar_round2"] - (COEQ_PL["DFGB2E_median"] - 0.5)) < 1e-5)
    try:
        J = GC.jload(GC.DFGBE_JUDGE)
        ck["DFGB2E_numbers_as_frozen"] = bool(abs(J["median"]["conv_Hc"] - COEQ_HC["DFGB2E_conv_Hc_median"]) < 1e-5
                                              and [round(g["conv"]["Hc"], 6) for g in J["groups"]] == COEQ_HC["DFGB2E_conv_Hc"])
    except Exception:
        ck["DFGB2E_numbers_as_frozen"] = False
    print(json.dumps(dict(ok=all(ck.values()), checks=ck, bar_pl_now=refs["bar_pl"], pl_rows={k: (v.get("pl_miss_median"), v.get("valid")) for k, v in refs["rows"].items()})))
    return all(ck.values())


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
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    if a[0] == "judge":
        r = judge(a[1], opt.get("out"), any_set=("test-any-set" in opt))
        print(json.dumps(GC.clean(summary_line(r)), ensure_ascii=False))
    elif a[0] == "coequal":
        r = coequal(a[1], opt.get("pv"), out_dir=opt.get("out"), judge_path=opt.get("judge"))
        c3b = r["criterion_3b_convergence_at_print_like"]
        print(json.dumps(GC.clean(dict(run=r["run_id"], progress=r["progress"], verdict=r["verdict"], print_view_ok=r["criterion_1_print_view"]["ok"],
                                       print_match=r["criterion_2_print_ruler"]["print_match"], score3=r["criterion_2_print_ruler"]["median_best_score3"],
                                       lip=r["criterion_2_print_ruler"]["median_best_lip"], convergence=r["criterion_3_convergence"]["outcomes"],
                                       miss=r["criterion_3_convergence"]["core_miss_median"], pl_ok=c3b["ok"], pl_miss=c3b["pl_miss_median"],
                                       bar_pl=c3b["bar_pl"], pl_clearly_better_than_DFGB2E=c3b["pl_clearly_better_than_DFGB2E"],
                                       same_instant=c3b["same_instant_new_best"], hc_ok=r["criterion_3c_hc_not_lower"]["ok"],
                                       hc=r["criterion_3c_hc_not_lower"]["text"], path=r["_path"])), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
