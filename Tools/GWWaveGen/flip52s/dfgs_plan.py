# -*- coding: utf-8 -*-
"""FLIP52S plan DFG-S: write and FREEZE Unity/Build/FLIP52S/plan/plan_DFGS_frozen.json (+ .sha256) BEFORE any FLIP52S run exists
(py -3.10 -B). 2026-10-18 written new (Claude) by adapting flip52b/dfg52b_plan.py (not edited). Reads: the DFG-S screen outputs
(Unity/Build/FLIP52S/screens/calib_52s.json, shapecal_52s.json, dfgs_S7_s3_h6_xf145.json, dfgs_screen_summary.json), the G1 table check
(plan/table_check_DFGS.json), the constants of g52s_common / g52s_ana / g52s_pcfg (embedded so that g52s_pcfg.plan_consistency and
g52s_ana.selftest compare them back), the DFG-2 frozen plan, its amendments and its 0.5 m judge (read only), and DFG-2's hf records (read only:
the measured G4 lesson, g52s_ana.g4split, ~1 min CPU).
Refuses to (re)freeze if any FLIP52S run folder exists (pcheck/<id> or runs/<id> with records); a frozen plan is changed only by appending
amendments to Unity/Build/FLIP52S/plan/amendments.jsonl.
usage: py -3.10 -B dfgs_plan.py freeze [--refreeze-before-runs] | show
"""
import os, sys, json, math, time, glob

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52s_common as GC           # noqa: E402
import g52s_ana as AN              # noqa: E402
import g52s_pcfg as PC             # noqa: E402

SCREEN = GC.SCREEN_DIR
DFG_PLAN = GC.REPO + "/Unity/Build/FLIP52/plan/plan_DFG_frozen.json"
DFG_AMEND = GC.REPO + "/Unity/Build/FLIP52/plan/amendments.jsonl"
DFG_RUN = GC.REPO + "/Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5"
AUTO = "G:/research/Wave Simulation/_tools/auto_DFGS.py"
S7 = "S7_s3_h6_xf145"


def r(v, n=3):
    return None if v is None else round(float(v), n)


def runs_exist():
    out = []
    for d in glob.glob(GC.PCHECK_ROOT + "/*") + glob.glob(GC.RUNS_ROOT + "/*"):
        if os.path.basename(d) == "ready":
            continue
        if glob.glob(d + "/run_c*.json") or glob.glob(d + "/hf_c*.npz") or os.path.exists(d + "/chain.log"):
            out.append(d)
    return out


def lessons():
    """[measured] what DFG-2 (same sea, same tank, same code, 0.5 m) taught the gates: G2f per frequency, G4 per region."""
    J = GC.jload(DFG_RUN + "/g52/judge_DFG.json")
    g2 = {k: dict(R=r(v["R"], 6), phase=r(v["phase_err_rad"], 4), frozen_range=v["range"], ok=v["ok"]) for k, v in J["gates"]["G2f"]["per_n"].items()}
    g4 = AN.g4split(DFG_RUN)
    pvj = GC.jload(GC.REPO + "/Unity/Build/FLIP53/pv53/DFG2_flat20_P28_dp0p5/pv53_DFG2_flat20_P28_dp0p5.json")
    return dict(
        G2f_DFG2_0p5=dict(per_n=g2, reading="DFG-2 failed its absolute G2f only by n5 0.788 < 0.80 (the 5.6 s layer, ~0.1 m components, realised "
                                            "at 0.5 m slightly below the linear target) [measured]; same table convention / VEX / gauges / window "
                                            "here, so DFG-S is judged RELATIVE to DFG-2's realisation (the DFG-2B rule): a broken table / VEX / "
                                            "band would fall below it, resolution damping would not"),
        G4_DFG2_split=dict(kp=r(g4["kp"], 6), inlet=r(g4["kA_inlet_max"], 6), side_core_70_92p5=r(g4["kA_side_core_max"], 6),
                           outer_wall_strip_gt_92p5=r(g4["kA_wall_strip_max"], 6), full_band_DFG2_rule=r(g4["kA_side_full_max_DFG2_rule"], 6),
                           full_band_max_at_xy=g4["side_full_max_at_xy"], t_full_max=r(g4["t_side_full_max"], 3),
                           reading="DFG-2's G4 failure (0.41 > 0.40) sits entirely in the outer-wall strip (the last hf row y 99.5 m, x 179.5 m = "
                                   "the end of the generating part), where the band target is tapered to 0 over 7.5 m and the reflecting side wall "
                                   "doubles the arriving crest; the generating band core reached 0.265 = its linear target (table check 0.266) "
                                   "[measured]. The band's own generation was not steep. DFG-S gates the core (70-92.5 m) and the inlet band at "
                                   "0.40 and REPORTS the wall strip and the DFG-2 full-band number beside them",
                           tool="Tools/GWWaveGen/flip52s/g52s_ana.py g4split (read only)"),
        DFG2_shape=dict(conv_back_deg=r(J["median"].get("back_deg"), 2), pv53_best_back=[r(q["best"]["back"], 1) for q in pvj["periods"]],
                        pv53_best_w07=[r(q["best"]["w07"], 2) for q in pvj["periods"]],
                        score3_median=2.484, lip=0.0, note="DFG-2: smooth non-breaking dome at the focus (flat 20 m) [measured]"))


def build():
    cal = GC.jload(SCREEN + "/calib_52s.json")
    sc = GC.jload(SCREEN + "/shapecal_52s.json")
    ch = GC.jload(SCREEN + "/dfgs_%s.json" % S7)
    summ = GC.jload(SCREEN + "/dfgs_screen_summary.json")
    tc = GC.jload(GC.PLAN_DIR + "/table_check_DFGS.json")
    C = GC.components()
    fp = ch["flip_pred"]; om = ch["onset_metrics"] or {}
    cp = PC.make("pcheck", dry=True); cm = PC.make("main", dry=True)
    te_p = cp["precheck"]["time"]; te_m = cm["precheck"]["time"]
    sum_a2 = float(np.sum(C["a"] ** 2))
    dm1a_sum_a2 = 30 * (C["a_sum"] / 30.0) ** 2       # DM1A: 30 equal components of a_sum / 30 (g50_common CASES DM1, uniform)
    asum_energy = float(C["a_sum"] * math.sqrt(dm1a_sum_a2 / sum_a2))
    L = lessons()
    stepctrl = {k: GC.bed_parms(GC.SPEC_STEP)[k] for k in ("ridge_on", "ridge_x0", "ridge_k", "ridge_s", "shelf_h")}
    plan = dict(
        status="FROZEN", plan="DFG-S", campaign="FLIP52S-DFGS",
        tags_legend={"[measured]": "【測定】", "[computed]": "【計算】", "[literature]": "【文献】", "[guess]": "【推測】", "[chosen]": "【選び】",
                     "[calibrated]": "【計算】 (a screen number scaled by a DFG-2 measured ratio)"},
        title=("FLIP52S plan DFG-S: the DFG-2 periodic three-frequency directional group (P 28 s; T 9.33 / 7 / 5.6 s; plan E X2 directions; a_sum = "
               "DM1A) in DFG-2's tank (flat 20 m, half width 100 m, exit sponge) with a laterally uniform 1:3 STEP (toe x 108 m, edge x 150 m, 6 m "
               "shelf), the table re-phased by WKB so the group focuses at (145, 0) on the upper face at t = 43 + 28 m s: the converged crest meets "
               "near-limiting depth on a steep face while still converged; a 0.5 m 10 s pipeline check and one 0.5 m run of three groups; judged by "
               "THREE CO-EQUAL criteria (print view, print ruler, convergence)"),
        trigger=dict(
            user_Q83="every run is judged on (1) the Unity print-view render at the most print-like instant, (2) the centre section vs the print "
                     "outline with the print ruler, (3) the convergence metrics; progress = both convergence and the print match",
            DFG2_result="DFG-2 (flat 20 m, this sea, 0.5 m): best convergence of all runs (miss 0.71, W50 3.40, W80 1.69, W95 0.82, S2 0.40, N1 0.09, "
                        "Hc 6.15 m, gain 3.05) but a smooth non-breaking dome (score3 2.48, lip 0); INVALID by G2f (n5 0.79 < 0.80) and G4 (0.41 at "
                        "the outer-wall corner) [measured]",
            physics="convergence needs short waves focused before depth-limited breaking; a print-like plunge needs the crest near its breaking limit "
                    "hitting a steep bed (Iribarren >~ 0.4-0.5); on 1:10 the T 7 s waves give xi 0.31-0.33 (spilling); on 1:3 with the converged "
                    "crest xi_b ~1.0-1.1 (plunging class) [computed]",
            design="flip52s/dfgs_screen.py candidate S7 (main session's design task 2026-10-18); DFG-2B (1:10 beach) screen predicted Hc/h 0.40-0.47 "
                   "at the converged crest with a_sum = DM1A (no plunge); its energy-matched variant awaits the user's decision",
            parents=dict(DFG2_plan="Unity/Build/FLIP52/plan/plan_DFG_frozen.json sha %s" % GC.sha256_file(DFG_PLAN)[:16],
                         DFG2_amendments=[a.get("id") for a in (json.loads(l) for l in open(DFG_AMEND, encoding="utf8") if l.strip())])),
        physics_rules=dict(
            forces="gravity, the bed (flat + step) and the incoming waves only; no force toward a shape; no wind, no current (the return current "
                   "only cancels the target's own mean mass flux)",
            Q39="a_sum = 6.331240 m = the DM1A input sum, NOT enlarged",
            Q54_honesty="chosen at the inlet: P, the three frequencies and equal weights, the 34 X2 directions and weights, a_sum, the focus (145, 0) "
                        "at t = 43 + 28 m s, DFG-2's tank and bands, and the step (toe, slope, shelf depth); computed by FLIP: propagation, "
                        "dispersion, refraction, shoaling, reflection, focusing, the crest's growth, breaking, any jet / plume / bore"),
        sea=dict(P_s=GC.P_S, harmonics_n=list(GC.HARMONICS), T_s=[round(GC.P_S / n, 6) for n in GC.HARMONICS],
                 freq_weights=[round(float(v), 6) for v in C["wf"]], directions_deg=[round(float(v), 6) for v in C["th"]],
                 dir_weights=[round(float(v), 6) for v in C["wd"]], dspec=list(GC.DSPEC), n_components=int(C["a"].size),
                 a_sum_m=round(C["a_sum"], 9), a_max_component_m=round(float(C["a"].max()), 6), amp_per_freq_m=[round(float(C["a_sum"] * v), 6) for v in C["wf"]],
                 sum_a2_m2=round(sum_a2, 6), generation_depth_m=GC.H0, ramp_s=GC.RAMP_S,
                 same_as_DFG2="frequencies, P, weights, direction set and a_sum bit for bit = plan DFG-2 sea (g52s_pcfg checks against flip52 g52_common)",
                 focus=dict(x_m=GC.X_F, y_m=0.0, h_m=r(GC.h_of(GC.X_F), 4), t_f_s=GC.T_F, times_s=list(GC.FOCI),
                            rule="x_f 145 m = screen candidate S7 (focus on the upper face 5 m before the edge) [chosen]; t_f = ceil(t_full + 3.9 s) "
                                 "= ceil(%.2f + 3.9) = 43 s, the DFG-2 arrival rule with the WKB ray travel times over the step [computed]"
                                 % ch["arrival"]["t_full_s"],
                            design_linear_crest_m=r(tc["focus"]["total_design_crest_m"], 4), per_layer_shoal_refr_gain=[r(p["shoal_refr_gain"], 4)
                                                                                                                       for p in tc["focus"]["per_layer"]]),
                 energy=dict(input_variance_vs_DM1A=r(sum_a2 / dm1a_sum_a2, 4), a_sum_for_DM1A_variance_m=r(asum_energy, 3),
                             statement="a_sum 6.331 m = DM1A's input SUM, but the input variance (sum a^2) is only 0.354 x DM1A's (as DFG-2 / "
                                       "DFG-2B): any extra height comes from focusing 102 small components (max 0.095 m), step shoaling and "
                                       "nonlinearity, not from a bigger sea; DFG-2B's energy-matched variant would need a_sum ~10.6 m [computed]")),
        tank=dict(kind="DFG-2's half tank (symmetry plane y = 0, outer side wall y = 100 m) with a laterally uniform step; the DFG-2 0.5 m parms "
                       "(Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/cfg.json) except parms_differ_from_DFG2",
                  h0_m=GC.H0, Lx_m=GC.LX, W_m=GC.W_MAIN, z_bed_m=GC.ZB, z_top_m=GC.Z_TOP,
                  step=dict(x_toe_m=GC.X_TOE, slope_1_in=GC.SLOPE_S, h_top_m=GC.H_TOP, x_edge_m=GC.X_EDGE, ctrl=stepctrl,
                            formula="depth = max(6, 20 - max(x - 108, 0)/3), all y (flat 20 m to x 108 m, 1:3 face to x 150 m, 6 m shelf to x 290 m, "
                                    "under the exit sponge)",
                            vex="NO new VEX term: the FLIP48 plain branch of bedy / bedgrad / bedsdf_out (flip49/g49_tanklib.py VEX head through "
                                "flip50 / flip52 tanklib, unchanged) with ridge_on 1, ridge_k 0, ridge_x0 108, ridge_s 3, shelf_h 6",
                            numpy="g49_common / g48_common bed_z / bed_grad / bed_sdf (plain path) = the analytic step bit for bit; "
                                  "g52s_common.bed_selfcheck (also a transliteration of the VEX text and g50_dirfield.bed_h)",
                            selfcheck_at_freeze={k: v for k, v in GC.bed_selfcheck().items() if k in ("ok", "equals_analytic_bit", "grad_ok", "sdf_ok",
                                                                                                     "dirfield_bed_h_ok", "plain_path",
                                                                                                     "vex_transliteration_max_abs_dz_m")},
                            hython_check="build_check52s.json: OUT_BED heights and the collision SDF vs numpy on the step strip (W 6 m) and 3D box "
                                         "(W 100 m) at dp 0.5, depth range exactly 6-20 m, particle seeding vs count_particles, no particle below "
                                         "the bed",
                            why=dict(choice="screen S7 [chosen]: breaks at the converged crest for every gamma 0.77-0.95 (2nd-order model calibrated on "
                                            "DFG-2: onset x 144.5-147.5 m, h 6.8-7.8 m, Hc 6.4-6.9 m, 1.5-1.75 s after the converged instant); the "
                                            "conservative linear-calibrated model breaks at the edge (x 149.5 m, Hc 5.0 m) if gamma <= 0.81; "
                                            "calibrated miss at the onset 0.12; pre-break back ~30 deg, w07 ~1.1 (print 31.3 / 1.32); Iribarren_b "
                                            "0.98-1.13 at T 7 s; face reflection <= 5 %; only 14 % of the focal sum depends on the WKB side-band "
                                            "target over the face (1:4 faces 24-29 %); the shelf is not too shallow (h_top / Hc 0.9; campaign B "
                                            "S2's low wide breaker came from a 1.7 m shelf, 0.4) [computed / guess]",
                                     refraction="Snell over the step turns the crossing lobes from +-60 deg to +-33-42 deg (k_y conserved, the lateral "
                                                "width kept) and slows the crossing-crest pattern from 15 m/s (measured on DFG-2) to ~9 m/s "
                                                "[measured + computed]")),
                  solver=dict(dp=[0.5], gridscale=2.0, cfl=1.0, pcfl=0.75, minsub=1, maxsub=8, veltransfer="flip"),
                  bands=dict(inlet=dict(x_m=[0.0, GC.IN_X1], xg_end=GC.IN_X1, wall_taper_m=GC.WALL_TAPER, relax_g=1.0, in_gain=1.0),
                             side=dict(y_m=[GC.SD0, GC.W_MAIN], sd0=GC.SD0, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW, sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW,
                                       sd_taper_m=GC.SD_TAPER, sd_gain=1.0, note="generates for x <= 180 m, i.e. also over the face and the shelf "
                                                                                  "with the WKB target (14 % of the focal linear sum enters there)"),
                             exit_sponge=dict(abs_on=1, xa0=GC.XA0, abs_sigma=GC.ABS_SIGMA, abs_pow=GC.ABS_POW, length_m=GC.LX - GC.XA0, over="the 6 m shelf"),
                             ret_on=1, dir_on=1, volume=dict(stage="A (AM-D18, = DFG-2)", vol_x_m=list(GC.VOL_X))),
                  interior=dict(x_m=list(GC.INTERIOR_X), y_abs_max_m=GC.INTERIOR_Y, scan_x_m=list(GC.SCAN_X), onset_x_m=list(GC.ONSET_X)),
                  parms_differ_from_DFG2=list(PC.PARMS_DIFFER_FROM_DFG2), named_differences=cm["precheck"].get("named_differences"),
                  sea_into_tank="N-layer table (g52s_table: WKB DirField kind 'shelf' per harmonic, 1 m, x 0-214 m, y 0-100 m) read by the unchanged "
                                "N-layer VEX of flip52/g52_tanklib.py in a new scene Houdini/FLIP52S/g52s_tank.hiplc"),
        records=dict(hf="top-surface height field (1 m) every frame", r2="centre section y 0.5 m every frame (print ruler, lips)",
                     r3="section y 40 m every frame (report)", r4="per-y sections x 90-200 m, y 0-65 m, every 3rd frame in the group windows",
                     r5="surface meshes (crop x 90-200 m) every 3rd frame in the group windows (Unity print view, mp4)",
                     gauges="x 60 / 100 / 145 / 190 m, y 0.5 / 15 / 30 / 45 / 60 m (G2f at x 60 m)",
                     checkpoints="every 48 frames (resume after the 1740 s launch limit); none in the pipeline check",
                     group_window_s=list(GC.GROUP_WIN), t_end_s=dict(main=PC.T_END["main"], pcheck=PC.T_END["pcheck"]), r4_x_m=list(GC.R4_X),
                     pcheck_window_s=list(PC.PCHECK_WIN), no_1m_smoke="dp 1.0 damps the 5.6 s layer (DFG-2 smoke n5 0.43, AM-DFG3): replaced by the "
                                                                      "0.5 m 10 s pipeline check"),
        criteria=dict(
            coequal=dict(COEQ_note="THREE CO-EQUAL CRITERIA, shown side by side for every judged run (user Q83)",
                         criterion_1="the Unity PRINT-VIEW render (option-D composition) at the run's most print-like instant + a front view + the print "
                                     "(Tools/GWWaveGen/flip53/pv53.py run <run dir>, unchanged; its stills and mp4 are shown to the user)",
                         criterion_2="the centre section vs the Hokusai print outline with the print ruler (STUDY52 cn outline; score3 = chord 0.1-0.5 "
                                     "eta_c + front foot + hood band misses; plus hollow, lip, back 0.7-0.9 eta_c, width07) at the most print-like "
                                     "instant of each group (pv53 rule: frames [t_max - 1.5, t_max + 3.0] s of the judge's 'max' instant, crest floor "
                                     "0.6 Hc (AM-DFG2a))",
                         criterion_3="the convergence metrics (flip51/e51_metrics.py frozen ruler, target read from the user's screenshot through its "
                                     "frozen read values only) at the judge's 'max' instants, medians over the groups, and the frozen decision",
                         score3_bar=AN.COEQ["score3_bar"], score3_DM1A_median=AN.COEQ["score3_DM1A_median"], tol=AN.COEQ["tol"],
                         lip_min=AN.COEQ["lip_min"], conv_outcomes=AN.COEQ["conv_outcomes"], print_ref=AN.COEQ["print_ref"],
                         progress_rule="PROGRESS iff the convergence decision gives NEW_BEST_SHAPE or TARGET_BAND AND the print match is ok (median "
                                       "best-instant score3 <= 0.9485 = DM1A 0.6485 + 0.30, median best-instant lip >= 0.20) AND the Unity print view "
                                       "was rendered at that instant; 'converged, print match worse than DM1A' is NOT a new shape reference and is not "
                                       "shown as progress; PRINT_BETTER_THAN_DM1A (report) if median best score3 < 0.6485 and lip >= 0.20. = AM-DFG2 / "
                                       "AM-DFG2a of DFG-2, unchanged",
                         no_print_view_no_progress="a run without the print-view package or without its Unity render is INCOMPLETE, never progress",
                         prebreak_report="the judge also reports the centre-row pre-break shape (onset - 0.5 s; the screen's ruler: back 0.7-0.9 "
                                         "eta_c, width at 0.7 eta_c) against the print's back 31.3 deg (29-38) and width07 1.32 (1.02-1.42): report only"),
            groups=dict(window_s=list(GC.GROUP_WIN), scan_x=list(AN.GROUP["scan_x"]), onset_x=list(AN.GROUP["onset_x"]), Nt_x=list(AN.GROUP["Nt_x"]),
                        face_edge_x=AN.GROUP["face_edge_x"],
                        conv="largest Hc over x 90-200 m, |y| <= 65 m in [t_fn - 8, t_fn + 2] s",
                        onset="first r2 lip (AM-DFG1 test) at x 90-205 m in the window",
                        max_instant="plan E D rule: onset -> e51 max in [on - 3, on + 1.5] s, x [on_x - 60, on_x + 35] m; else conv",
                        Nt_rule="DFG-2 rule: largest interior Hc (x 60-205 m, |y| <= 65 m) in [t_fn - 14, t_fn + 14) at |t - t_max| >= 3.5 s / "
                                "Hc('max'); reported beside it: the same in x 60-160 m (the screen: on the shelf the focused crest persists, linear "
                                "Nt 0.93-0.97; only breaking dissipation brings Nt below 0.75)",
                        c_in="largest crest on x 60 m, |y| <= 65 m in [t_fn - 14, t_fn + 14)",
                        plunge_at_converged="r2 onset within [t_conv - 1, t_conv + 4] s and x_on <= x_conv + 30 m",
                        onset_on_face_or_edge="r2 onset x <= x_edge + 10 = 160 m"),
            A_validity=dict(
                G1=dict(rule="numpy table check table_check_DFGS.json all_ok (focus vs independent WKB sums, flat part = DFG-2 amplitudes, shelf "
                             "constant, symmetry, continuity flat + shelf < 5e-3 (face reported), interpolation < 2 %, vertical profile < 1e-4, zero "
                             "mass flux, P-periodicity) + build_check52s all_ok with the hip the launches used + cfg precheck ok"),
                G2f=dict(rule=AN.G2F_RULE, x=AN.GATES["G2f_x"], y=list(AN.GATES["G2f_y"]), window_s=list(AN.GATES["G2f_t_main"]),
                         floor=AN.GATES["G2f_floor_0p5"], margin=AN.GATES["G2f_margin_0p5"], hi=AN.GATES["G2f_hi_0p5"], phase=AN.GATES["G2f_phase_0p5"],
                         reference=AN.DFG_REF.replace(GC.REPO + "/", ""), fallback={str(k): list(v) for k, v in AN.GATES["G2f_fallback_0p5"].items()},
                         lesson="see lessons_measured.G2f_DFG2_0p5"),
                G3P=dict(P_s=GC.P_S, tol_s=AN.GATES["G3P_tol"], x_spread_m=AN.GATES["G3P_xspread"], Hc_ratio=AN.GATES["G3P_Hc_ratio"], on="the 'conv' summits"),
                G4=dict(kA_max=AN.GATES["G4_kA"], t0_s=AN.GATES["G4_t0"], inlet_x_max=AN.GATES["G4_inlet_x"],
                        side_core_y=[AN.GATES["G4_side_y"], AN.GATES["G4_side_y1"]], side_x_max=AN.GATES["G4_side_x"], lip_x_max=AN.GATES["G4_lip_x"],
                        rule="kp x (3x3-median hf - eta0) <= 0.40 from t 30 s in the inlet band (x <= 50 m, all y) and the generating side-band CORE "
                             "(70 <= y <= 92.5 m, x <= 180 m); no overturning r2 lip at x < 60 m",
                        reported_not_gated="the outer-wall strip y > 92.5 m (the band target tapers to 0 there and the wall reflects), DFG-2's full-band "
                                           "number (y >= 70 m) and k(h(x)) x crest in the core over the step",
                        lesson="see lessons_measured.G4_DFG2_split: chosen before any DFG-S run; the core rule is the band's purpose (the band must "
                               "not generate a near-breaking sea), the wall row is a wall-reflection reading [chosen]"),
                G5=dict(max=AN.GATES["G5_max"]),
                G6=dict(x=list(AN.GATES["G6_x"]), y_abs_max=AN.GATES["G6_y"], t_rel=list(AN.GATES["G6_t"]), Hc_min=AN.GATES["G6_Hc"],
                        why="screen: converged crest x 127.5 m at t_fn - 1.5 s (Hc 5.1-5.2 m linear), onset x 144.5-149.5 m at t_fn + 0 .. 0.75 s, an "
                            "unbroken crest on the shelf by t_fn + 2 s at x <~ 170 m; Hc floor = 0.68 x the converged linear crest 5.14 m (plan E "
                            "rule) [computed / chosen]"),
                also="run complete (f_end reached), 3 groups",
                failure_class="pipeline = run incomplete, G1, G2f (the main session fixes the cause and reruns once, same setup name); physics = "
                              "G3P, G4, G5, G6"),
            B_eligibility=dict(AN.ELIG),
            decision=dict(bar_cap=AN.DEC["bar_cap"], bar_margin=AN.DEC["bar_margin"], DF1A_miss=AN.DEC["DF1A_miss"], target_band=AN.DEC["target_band"],
                          jet_ratio=AN.DEC["jet_ratio"], plunge_groups=AN.DEC["plunge_groups"],
                          best_valid_from="DF1A 3.3 [measured] and, if valid by their own plans, plan E X2 / X1, DFG-2, DFG-2B and X2B' 0.5 m (read at "
                                          "analysis time; X2B' validity = its x2b/judge_X2B.json valid_x2b)",
                          outcomes="INVALID / NOT_ELIGIBLE / NEW_BEST_SHAPE (miss <= bar) / TARGET_BAND (miss <= 0.5) / JET_REGIME_SEEN / NO_GAIN; "
                                   "physics flags PLUNGE_AT_CONVERGED / BREAKS_LATER / NO_BREAK_IN_WINDOW / ONSET_ON_FACE_OR_EDGE / BREAKS_ON_SHELF "
                                   "(>= 2 of 3 groups)",
                          after="no automatic follow-up run: the co-equal verdict, the print-view stills and the numbers go to the user / main session "
                                "(fallback design S4: 1:4, 6.0 m, equally robust in the screen)"),
            pcheck=dict(role="PIPELINE CHECK ONLY (0.5 m, 0-10 s; never shape-judged): the new scene (step bed SDF, seeding) and the new table under "
                             "the real solver",
                        pass_rule="run complete; G1; G5; no guard stop; no particle below the bed (run 'leak' samples); |eta0| <= 0.25 m; still water "
                                  "over the step at t 0.5-1.5 s (mean level shelf x 155-205 m minus flat x 60-100 m within +-0.05 m, max |eta| <= 0.15 m "
                                  "in x 60-205 m); waves arrive at x 60 m in t 6-10 s with 0.33-3.0 x the ramped linear target; hf / r2 every frame, "
                                  "r4 and r5 written",
                        still_diff_max_m=AN.GATES["pc_still_diff_max"], still_abs_max_m=AN.GATES["pc_still_abs_max"], wave_ratio=list(AN.GATES["pc_wave_ratio"]),
                        on_fail="the 0.5 m run does not start; the main session reads g52s/pcheck_DFGS.json and decides",
                        checked_on_DFG2="the same checks on DFG-2's 0.5 m record (code path, flat bed): still-water difference 0.001 m, waves ratio "
                                        "1.14 [measured 2026-10-18]")),
        lessons_measured=L,
        screen=dict(tool="Tools/GWWaveGen/flip52s/dfgs_screen.py (WKB DirField over the step + column-wise local Sharma-Dean 2nd order; frozen e51 "
                         "ruler; calibrated on DFG-2 0.5 m itself)",
                    calibration=dict(rule=cal["rule"], shape_ratios=dict(at_summit=sc["at_summit"], range=sc["range_dt_-1.5_0"]),
                                     gamma=dict(central=0.84, lo=0.77, hi=0.95,
                                                src="Hc / h_b at the centre onset: DM1A 0.837, DF1A 0.774, DG1 0.832 on 1:10 [measured]; a steeper face "
                                                    "raises the breaking index (Weggel 1972) [literature] -> band 0.77-0.95, central 0.84 [chosen]")),
                    chosen=S7, S7=dict(arrival=ch["arrival"], flip_pred={k: {kk: fp[k].get(kk) for kk in ("onset", "converged", "peak", "gamma", "mode",
                                                                                                            "onset_after_converged_s",
                                                                                                            "breaks_at_converged_crest",
                                                                                                            "onset_on_face_or_edge")} for k in fp},
                                       onset_metrics_calibrated=om.get("DFG2_calibrated"), onset_centre_shape_screen=om.get("centre_shape"),
                                       iribarren_b=ch["iribarren_b"], reflection=ch["reflection"]),
                    candidates=summ),
        expected=dict(
            tag="all ranges [guess] unless tagged; per group (3 groups at 43 / 71 / 99 s)",
            converged=dict(x_m=127.5, h_m=13.5, t_rel_tfn_s=-1.5, Hc_m=[5.1, 5.2], tag="linear [computed]"),
            onset=dict(x_m=145.5, x_range=[144.5, 149.5], h_m=7.5, h_range=[6.2, 7.8], t_rel_tfn_s=0.1, t_range=[0.0, 0.75], Hc_m=6.6,
                       Hc_range=[5.0, 6.9], Hc_over_h=[0.82, 1.0]),
            convergence_at_onset_max=dict(Hc=[6.6, 5.0, 7.5], W50=[2.7, 2.4, 3.4], W80=[1.36, 1.2, 1.8], W95=[0.61, 0.5, 0.9], K=2.7, S2=[0.08, 0.05, 0.4],
                                          miss=dict(central=0.12, range=[0.1, 1.2], note="DFG-2's screen said 0.51 and FLIP measured 0.71"),
                                          N1=[0.16, 0.1, 0.5], gain_over_c_in60=[3.0, 3.8], E2_Hc_ge_5_P=0.75, Nt=[0.5, 0.95], E1t_P=0.5),
            print_ruler=dict(prebreak_back_deg=[30.0, 23.0, 37.0], prebreak_w07=[1.1, 1.0, 1.2], print=dict(back=31.3, back_band=[29, 38], w07=1.32,
                                                                                                          w07_band=[1.02, 1.42]),
                             earlier_beds="FLIP47 back 3-14 deg; DM1A 14 deg / w07 2.2 [measured]",
                             if_plunges=dict(chord_deg=[60, 110], foot=[0.2, 0.6], hood=[0.1, 0.3], lip=[0.2, 0.45], score3=[0.8, 0.4, 1.0]),
                             if_spills_or_bore=dict(score3=[1.5, 2.5], lip=0.0)),
            probabilities=dict(breaks_at_converged_crest_face_or_edge_ge2groups=0.6, plunging_lip_ge_0p20_median=0.45, print_match_ok=0.35,
                               valid_with_DFG2_type_G4_absolute=0.45, valid_with_this_plan_G4_core=0.7, NEW_BEST_SHAPE_given_valid=0.75,
                               TARGET_BAND_given_valid=0.35, PROGRESS_both=[0.2, 0.25], DFG2B_frozen_estimate=0.1, tag="[guess]")),
        cost=dict(pcheck=te_p, main=te_m, max_hours=dict(PC.MAX_H), particles_main_M=dict(model=r(cm["precheck"]["particles_model"] / 1e6, 3),
                                                                                           peak=[r(v, 3) for v in cm["precheck"]["particles_peak_M"]],
                                                                                           DFG2_measured=5.114992),
                  build_min=[5, 10], analysis_min=dict(judge=[2, 4], pv53_unity=[5, 12], video=[2, 5]),
                  total_h=[r(te_p["est_h"][0] + te_m["est_h"][0] + 0.2, 2), r(te_p["est_h"][1] + te_m["est_h"][1] + 0.5, 2)],
                  disk_GB=[4, 6], note="Houdini occupied ~1.0-1.5 h after X2B' (and after DFG-2B if that keeps its slot); the max_hours cap is per "
                                       "chain; auto_DFGS resumes a max_hours stop from the last checkpoint (up to --cap-resumes, default 2)"),
        order=["freeze this plan (no FLIP52S run exists)", "wait for X2B's final status line, no hython and no other pipeline (auto_DFGS.py)",
               "build (x52s_build.py)", "0.5 m 10 s pipeline check (pipeline only)", "0.5 m run",
               "g52s_ana judge -> pv53 run (Unity print view) -> g52s_ana coequal -> g52s_video"],
        automation=dict(script=AUTO, start="py -3.10 -B \"%s\"" % AUTO, status="Unity/Build/FLIP52S/_logs/auto_DFGS_status.txt (prefix 'DFGS ')",
                        sha256=(GC.sha256_file(AUTO) if os.path.exists(AUTO) else None), started_by_author=False,
                        wait_rule="starts only after the LAST 'X2B ' line of Unity/Build/FLIP51/_logs/auto_X2B_status.txt matches exactly "
                                  "^<date> <time> X2B FINISHED( <msg>)?$, no hython and no other pipeline process (auto_*.py, *_chain.py, *_run.py, "
                                  "x5*_build.py, pv53.py) on 3 consecutive polls with the same last line",
                        simulate="py -3.10 -B auto_DFGS.py --simulate[=scenario.json]: no wait, no launch, nothing written"),
        honesty=dict(chosen_at_inlet="P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and Gaussian weights, a_sum 6.331240 m "
                                     "(= DM1A), DFG-2's tank and bands, the step (toe 108 m, 1:3, 6 m shelf), the focus (145, 0) at t = 43 + 28 m s",
                     computed_by_FLIP="propagation, dispersion, refraction, shoaling, reflection, focusing, the crest's growth, breaking, any jet / "
                                      "plume / bore",
                     input_energy="input variance 0.354 x DM1A's (same as DFG-2): the height comes from focusing small components, step shoaling and "
                                  "nonlinearity, not from a bigger sea",
                     gates="G2f relative to DFG-2's measured realisation and G4 on the band core are lessons of DFG-2 chosen BEFORE any DFG-S run; "
                           "the DFG-2-type absolute numbers are reported beside them in every judge",
                     not_done="no input enlargement, no force toward a shape, no wind or current; the target picture only through e51; nothing "
                              "committed; README / Docs not edited; no Houdini started while X2B' runs; no file of a running or queued pipeline "
                              "(flip50*, flip51, flip52, flip52b, their hips, build checks, cfgs, plans) touched; auto_DFGS.py not started"),
        risks=[
            "Nonlinearity is the main uncertainty: the linear crest does not grow on the step (Ks 0.92-1.0, Kr < 1); breaking relies on the 2nd-order "
            "growth, and in h 6-8 m the Ursell number is ~55-90, outside 2nd-order validity. If FLIP follows the linear-calibrated model and gamma > "
            "0.81, the crest crosses the edge unbroken (Hc/h_top 0.83) and breaks later on the shelf as a spiller or bore (BREAKS_LATER). P ~0.3",
            "Campaign B S2 analogue: a 1:3 face is abrupt for T 9.33 s (face length ~0.4 L); the transmitted crest can split into free harmonics on the "
            "shelf instead of plunging on the face. Fallback: S4 (1:4, 6.0 m), equally robust in the screen",
            "A 3D crossing peak may form an upward spout / jet rather than a forward lip (DFG-2's watch item); the step reduces the crossing "
            "half-angle to 33-42 deg, not proven in FLIP",
            "Gates inherited from DFG-2: G4's DFG-2-type full-band number (wall row) likely ~0.42 again (linear side crest x DFG-2's FLIP/linear "
            "1.57); this plan gates the band core (DFG-2 core 0.265 [measured]) and reports the wall row. G2f n5 is relative to DFG-2's 0.788. Face "
            "reflection adds <= 5 % at the x 60 m gauges",
            "E1t temporal isolation: on the shelf the focused crest persists (linear Nt 0.93-0.97); only breaking dissipation brings Nt below 0.75. "
            "P(pass) ~0.5",
            "The WKB side-band target on the 1:3 face is approximate (non-mild slope, no reflection); 14 % of the focal linear sum enters that way; "
            "errors there can seed spurious waves (fallback sd_gen 150 / sd_sw 180 keeps aperture 1.00 [computed])",
            "Calibration transfer: R, dX, dT, W ratios and shape ratios come from DFG-2 on the flat bed and are assumed to hold on the step; the "
            "pre-break back (23-37 deg) and w07 (1.0-1.2) can drift (the screen over-sharpens more in shallow water)",
            "The bound long wave released at the step (P 28 s, long-wave R ~0.29) can set up a weak tank seiche: +-0.1-0.3 m on the mean level and the "
            "onset depth across groups, a small G3P risk",
            "Shelf set-up from breaking held by the exit sponge over the 6 m shelf: expected small (the breaker is laterally narrow); reported, not "
            "gated",
            "The bed collision SDF uses the FLIP48 approximation (z - bed)/sqrt(1 + |grad|^2): it is exact on the flat and the shelf, 5 % smaller "
            "on the 1:3 face and has a small step at the edge x 150 m (VEX = numpy there; the particles see the true bed height) [computed]",
            "DFG-S competes with DFG-2B (auto_DFGB.py, not running at freeze) and the pending energy-matched DFG-2B decision for the Houdini slot; "
            "the order is the main session's or the user's call"],
        metrics_ruler=dict(e51="Tools/GWWaveGen/flip51/e51_metrics.py", e51_sha256=AN.E51_SHA,
                           print_view="Tools/GWWaveGen/flip53/pv53.py (sha at freeze %s)" % (GC.sha256_file(AN.PV53)[:16] if os.path.exists(AN.PV53) else None)),
        table_check=dict(all_ok=tc["all_ok"], content_sha256=tc["content_sha256"], ok=tc["ok"], continuity_face=tc["continuity"]["per_layer"],
                         band_linear_steepness=tc["band_linear_steepness"]),
        code_sha256={("Tools/GWWaveGen/flip52s/" + nm): GC.sha256_file(os.path.join(HERE, nm)) for nm in GC.CODE_FILES if os.path.exists(os.path.join(HERE, nm))},
        inputs_sha256={rel: GC.sha256_file(GC.REPO + "/" + rel) for rel in ("Unity/Build/FLIP52S/screens/calib_52s.json",
                                                                           "Unity/Build/FLIP52S/screens/shapecal_52s.json",
                                                                           "Unity/Build/FLIP52S/screens/dfgs_%s.json" % S7,
                                                                           "Unity/Build/FLIP52S/screens/dfgs_screen_summary.json",
                                                                           "Unity/Build/FLIP52S/plan/table_check_DFGS.json",
                                                                           "Unity/Build/FLIP52/plan/plan_DFG_frozen.json",
                                                                           "Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/cfg.json",
                                                                           "Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/judge_DFG.json")},
        table_npz=dict(path=cm["dir"]["npz"].replace(GC.REPO + "/", ""), sha256=cm["dir"]["npz_sha256"], content_sha256=cm["dir"]["content_sha256"]),
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        frozen_before_any_FLIP52S_run=True)
    return plan


def freeze():
    ex = runs_exist()
    if ex:
        raise SystemExit("FLIP52S run folders exist (%s): the plan is frozen; change it only by an amendment" % ex[:3])
    if os.path.exists(GC.PLAN) and "--refreeze-before-runs" not in sys.argv:
        raise SystemExit("%s exists; --refreeze-before-runs (allowed only while no FLIP52S run exists)" % GC.PLAN)
    p = build()
    GC.jdump(p, GC.PLAN)
    h = GC.sha256_file(GC.PLAN)
    open(GC.PLAN + ".sha256", "w", encoding="utf8").write("%s  plan_DFGS_frozen.json\n" % h)
    return p, h


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "show":
        print(json.dumps(GC.clean(build()), ensure_ascii=False, indent=1)[:30000])
    elif a[0] == "freeze":
        p, h = freeze()
        print("frozen", GC.PLAN, h)
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
