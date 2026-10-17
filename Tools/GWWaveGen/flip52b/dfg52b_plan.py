# -*- coding: utf-8 -*-
"""FLIP52B plan DFG-2B: write and FREEZE Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json (+ .sha256) BEFORE any FLIP52B run exists
(py -3.10 -B). 2026-10-17 written new (Claude). Reads: the screen outputs (Unity/Build/FLIP52B/screens/calib_52b.json, dfg52b_xf*.json,
dfg52b_screen_summary.json), the G1 table check (plan/table_check_DFGB.json), the constants of g52b_common / g52b_ana (embedded so that
g52b_pcfg.plan_consistency and g52b_ana.selftest compare them back), the DFG-2 frozen plan and its amendments (read only).
Refuses to (re)freeze if any FLIP52B run folder exists (smoke/<id> or runs/<id> with records) unless --force-before-runs is impossible:
a frozen plan is changed only by appending amendments to Unity/Build/FLIP52B/plan/amendments.jsonl.
usage: py -3.10 -B dfg52b_plan.py freeze | show
"""
import os, sys, json, math, time, glob, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52b_common as GC           # noqa: E402
import g52b_ana as AN              # noqa: E402
import g52b_pcfg as PC             # noqa: E402

SCREEN = GC.SCREEN_DIR
DFG_PLAN = GC.REPO + "/Unity/Build/FLIP52/plan/plan_DFG_frozen.json"
DFG_AMEND = GC.REPO + "/Unity/Build/FLIP52/plan/amendments.jsonl"
ALT = (220.25, 230.25, 240.25, 250.25, 255.25, 260.25, 265.25, 270.25, 272.25, 275.25)


def r(v, n=3):
    return None if v is None else round(float(v), n)


def runs_exist():
    out = []
    for d in glob.glob(GC.SMOKE_ROOT + "/*") + glob.glob(GC.RUNS_ROOT + "/*"):
        if os.path.basename(d) == "ready":
            continue
        if glob.glob(d + "/run_c*.json") or glob.glob(d + "/hf_c*.npz"):
            out.append(d)
    return out


def build():
    cal = GC.jload(SCREEN + "/calib_52b.json")
    ch = GC.jload(SCREEN + "/dfg52b_xf%s.json" % GC.tag(GC.X_F))
    summ = GC.jload(SCREEN + "/dfg52b_screen_summary.json")
    tc = GC.jload(GC.PLAN_DIR + "/table_check_DFGB.json")
    C = GC.components()
    fp = ch["flip_pred"]; on = fp["onset"]; cv = fp["converged"]; om = ch["onset_metrics"] or {}
    pe = ch["print_expectation"]
    lin_on = fp["linear_mode"]["onset"]; lin_cv = fp["linear_mode"]["converged"]
    # cost (the g52b_pcfg rule on the cfgs that will be written)
    cs = PC.make("smoke", dry=True); cm = PC.make("main", dry=True)
    te_s = PC.time_estimate(cs); te_m = PC.time_estimate(cm)
    asum_energy = float(C["a_sum"] * math.sqrt(1.336153 / float(np.sum(C["a"] ** 2))))
    alts = {k: v for k, v in summ.items() if any(abs(v["x_f"] - a) < 1e-6 for a in ALT)}
    plan = dict(
        status="FROZEN", plan="DFG-2B", campaign="FLIP52B-DFG2B",
        title=("FLIP52B plan DFG-2B: the DFG-2 periodic three-frequency directional group (P 28 s; T 9.33 / 7 / 5.6 s; plan E X2 directions; a_sum = "
               "DM1A) generated in the D19B tank (h0 19 m, 1:10 beach from x 160.25 m, option-D bands) with the design focus on the slope at "
               "x_f %.2f m (h %.2f m) so that the converged crest starts to shoal where the D19B plunging breakers broke; a 1.0 m smoke (pipeline "
               "only) and one 0.5 m run of three groups; judged by THREE CO-EQUAL criteria (print view, print ruler, convergence)" % (GC.X_F, GC.h_of(GC.X_F))),
        trigger=dict(
            user_2026_10_17_2150="the user asked why the analysis figures from the screenshot metrics (front, top, centre section) were checked without "
                                 "checking the most important thing, whether the ORIGINAL PRINT's view matches. From now on every run's evaluation shows, "
                                 "side by side and as co-equal criteria: (1) the Unity print-view render at the most print-like instant, (2) the centre "
                                 "section vs the Hokusai print outline with the print ruler, (3) the convergence metrics; new goals are constraints on top of "
                                 "the print match, never replacements",
            physics_concern="on the flat DFG-2 bed focus-limited crests tend to jet / spill upward; the print's plunging lip with a steep front came "
                            "from shoaling on the 1:10 slope (FLIP47 P1c, option D): DFG-2B places the same group on the D19B slope",
            parent="plan DFG-2 (Unity/Build/FLIP52/plan/plan_DFG_frozen.json sha %s; AM-DFG1..3, AM-DFG2a) running at 0.5 m" % GC.sha256_file(DFG_PLAN)[:16]),
        physics_rules=dict(
            forces="gravity, the D19B bed and the incoming waves only; no force toward a shape; no wind, no current (the return current only cancels "
                   "the target's own mean mass flux)",
            Q39="a_sum = 6.331240 m = the DM1A input sum, NOT enlarged (input variance 0.354 x DM1A's)",
            Q54_honesty="chosen at the inlet: P, the three frequencies and equal weights, the 34 X2 directions and weights, a_sum, the focus "
                        "(x_f, 0) at t = t_f + 28 m s, the D19B tank and its bands; computed by FLIP: propagation, dispersion, refraction, shoaling, "
                        "focusing, the crest's growth, breaking, any jet / plume"),
        sea=dict(P_s=GC.P_S, harmonics_n=list(GC.HARMONICS), T_s=[round(GC.P_S / n, 6) for n in GC.HARMONICS],
                 freq_weights=[round(float(v), 6) for v in C["wf"]], directions_deg=[round(float(v), 6) for v in C["th"]],
                 dir_weights=[round(float(v), 6) for v in C["wd"]], dspec=list(GC.DSPEC), n_components=int(C["a"].size),
                 a_sum_m=round(C["a_sum"], 9), a_max_component_m=round(float(C["a"].max()), 6), amp_per_freq_m=[round(float(C["a_sum"] * v), 6) for v in C["wf"]],
                 sum_a2_m2=round(float(np.sum(C["a"] ** 2)), 6), generation_depth_m=GC.H0, ramp_s=GC.RAMP_S,
                 same_as_DFG2="frequencies, P, weights, direction set and a_sum bit for bit = plan DFG-2 sea (g52b_pcfg checks against flip52 g52_common)",
                 focus=dict(x_m=GC.X_F, y_m=0.0, h_m=round(GC.h_of(GC.X_F), 6), t_f_s=GC.T_F, times_s=list(GC.FOCI),
                            rule=("x_f = the median centre onset x of the D19B plunging breakers DM1A / DF1A / DG1 (256.5 m, h_b 9.4 m) [measured] minus the "
                                  "X2 0.5 m focus shift dX = %.1f m [measured: FLIP's converged crest occurs %.1f m upstream of the WKB design focus] -> 272.0 m, "
                                  "on the D quarter-metre grid 272.25 m [chosen]. t_f1 = ceil(t_full + 3.9 s) = %.0f s (t_full %.1f s = ramp 14 s + the "
                                  "longest refracted-ray travel time of the components with a >= 5 %% of the largest, 5.6 s components from the side band; "
                                  "+3.9 s = the DFG-2 margin) [computed]" % (cal["rule"]["dX_m"], -cal["rule"]["dX_m"], GC.T_F, ch["arrival"]["t_full_s"])),
                            aperture=r(ch["arrival"]["aperture"]),
                            aperture_note="%.0f %% of the focal linear sum has rays that start in the absorbing part of the D side band (x > 210.25 m): "
                                          "not generated (the side band is kept as option D) [computed]" % (100 * (1 - ch["arrival"]["aperture"])),
                            design_crest_linear_WKB_m=r(tc["focus"]["total_design_crest_m"]))),
        tank=dict(kind="half tank, symmetry plane y = 0, the D19B bed of FLIP50 / plan E (the X2 0.5 m parms, see g52b_pcfg PARMS_DIFFER_FROM_X2)",
                  h0_m=GC.H0, Lx_m=GC.LX, W_m=GC.W_MAIN, z_bed_m=GC.ZB, z_top_m=GC.Z_TOP, x_toe_m=GC.X_TOE, slope_1_in=GC.SLOPE_S, x_shore_m=GC.X_SHORE,
                  solver=dict(dp=[1.0, 0.5], gridscale=2.0, cfl=1.0, pcfl=0.75, minsub=1, maxsub=8, veltransfer="flip"),
                  bands=dict(inlet=dict(x_m=[0.0, GC.IN_X1], xg_end=GC.IN_X1, wall_taper_m=GC.WALL_TAPER, relax_g=1.0, in_gain=1.0),
                             side=dict(y_m=[GC.SD0, GC.W_MAIN], sd0=GC.SD0, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW, sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW,
                                       sd_taper_m=GC.SD_TAPER, sd_gain=1.0),
                             exit_sponge=dict(abs_on=0, note="none: the beach (as option D / plan E)"), ret_on=1, dir_on=1,
                             volume=dict(stage="A (AM-D18)", vol_x_m=list(GC.VOL_X))),
                  sea_into_tank="N-layer table (g52b_table: WKB DirField per harmonic over D19B, 1 m, x 0-214 m, y 0-140 m) read by the unchanged "
                                "N-layer VEX of flip52/g52_tanklib.py in a new scene Houdini/FLIP52B/g52b_tank.hiplc",
                  interior=dict(scan_x_m=list(GC.SCAN_X), y_abs_max_m=GC.INTERIOR_Y, N1_x_m=list(AN.N1DEF["x"]), Nt_x_m=list(AN.GROUP["Nt_x"]))),
        records=dict(hf="top-surface height field (1 m) every frame", r2="centre section y 0.5 m every frame (print ruler, lips)",
                     r3="section y 77 m every frame (report)", r4="per-y sections x 190-335 m, y 0-95 m, every 3rd frame in the group windows",
                     r5="surface meshes every 3rd frame in the group windows, 0.5 m only (Unity print view, mp4)",
                     gauges="x 110 / 128 / 160 m, y 0.5 / 20 / 40 / 60 / 80 m (G2f at x 110 m)", checkpoints="every 48 frames (resume after the 1740 s launch limit)",
                     group_window_s=list(GC.GROUP_WIN), t_end_s={"dp0p5": PC.T_END[0.5], "dp1p0": PC.T_END[1.0]}),
        criteria=dict(
            coequal=dict(COEQ_note="THREE CO-EQUAL CRITERIA, shown side by side for every judged run (user 2026-10-17 ~21:50)",
                         criterion_1="the Unity PRINT-VIEW render (option-D composition) at the run's most print-like instant + a front view + the print "
                                     "(Tools/GWWaveGen/flip53/pv53.py run <run dir>, unchanged; its stills and mp4 are shown to the user)",
                         criterion_2="the centre section vs the Hokusai print outline with the print ruler (STUDY52 cn outline; score3 = chord 0.1-0.5 eta_c + "
                                     "front foot + hood band misses; plus hollow, lip, back 0.7-0.9 eta_c, width07) at the most print-like instant of each "
                                     "group (pv53 rule: frames [t_max - 1.5, t_max + 3.0] s of the judge's 'max' instant, crest floor 0.6 Hc (AM-DFG2a))",
                         criterion_3="the convergence metrics (flip51/e51_metrics.py frozen ruler, target read from the user's screenshot through its frozen "
                                     "read values only) at the judge's 'max' instants, medians over the groups, and the frozen decision",
                         score3_bar=AN.COEQ["score3_bar"], score3_DM1A_median=AN.COEQ["score3_DM1A_median"], tol=AN.COEQ["tol"], lip_min=AN.COEQ["lip_min"],
                         conv_outcomes=AN.COEQ["conv_outcomes"], print_ref=AN.COEQ["print_ref"],
                         progress_rule="PROGRESS iff the convergence decision gives NEW_BEST_SHAPE or TARGET_BAND AND the print match is ok (median best-instant "
                                       "score3 <= 0.9485 = DM1A 0.6485 + 0.30, median best-instant lip >= 0.20) at the instant rendered in the Unity print "
                                       "view; 'converged, print match worse than DM1A' is NOT a new shape reference and is not shown as progress; "
                                       "PRINT_BETTER_THAN_DM1A (report) if median best score3 < 0.6485 and lip >= 0.20. = AM-DFG2 / AM-DFG2a of DFG-2, "
                                       "unchanged",
                         no_print_view_no_progress="a run without the print-view package (pv53 failed) is INCOMPLETE, never progress"),
            groups=dict(window_s=list(GC.GROUP_WIN), conv="largest Hc over x 150-300 m, |y| <= 95 m in [t_fn - 8, t_fn + 2] s",
                        onset="first r2 lip (AM-DFG1 test) at x 200-335 m in the window", max_instant="plan E D rule: onset -> e51 max in [on - 3, on + 1.5] s, "
                        "x [on_x - 60, on_x + 35] m; else conv", Nt_x=list(AN.GROUP["Nt_x"]), Nt_rule="largest Hc in x 150-275 m in [t_fn - 14, t_fn + 14) at "
                        "|t - t_conv| >= 3.5 s / Hc(conv) (the shoaling zone x > 275 m, h < 7.5 m, excluded from the other crests: every crest grows there)",
                        c_in="largest crest on x 110 m, |y| <= 95 m in [t_fn - 14, t_fn + 14)", plunge_at_converged="r2 onset within [t_conv - 1, t_conv + 4] s "
                        "and x_on <= x_conv + 30 m"),
            A_validity=dict(G1=dict(rule="numpy table check table_check_DFGB.json all_ok (focus vs independent WKB sums, symmetry, continuity flat < 5e-3, "
                                         "interpolation < 2 %, vertical profile < 1e-4, zero mass flux, P-periodicity) + build_check52b all_ok with the hip the "
                                         "launches used + cfg precheck ok"),
                            G2f=dict(rule=AN.G2F_RULE, x=AN.GATES["G2f_x"], y=AN.GATES["G2f_y"], window_main_s=list(AN.GATES["G2f_t_main"]),
                                     window_smoke_s=list(AN.GATES["G2f_t_smoke"]), floor_0p5=AN.GATES["G2f_floor_0p5"], margin_0p5=AN.GATES["G2f_margin_0p5"],
                                     hi_0p5=AN.GATES["G2f_hi_0p5"], margin_1p0=AN.GATES["G2f_margin_1p0"], phase_0p5=AN.GATES["G2f_phase_0p5"],
                                     phase_1p0=AN.GATES["G2f_phase_1p0"],
                                     why="the DFG-2 1.0 m smoke failed its frozen G2f by resolution damping (n4 0.775, n5 0.434 at x 60 m; AM-DFG3): the "
                                         "DFG-2B gate asks that the same code realises each frequency about as well as in DFG-2 at the same dp (a broken "
                                         "table / VEX / band would not), not an absolute level the resolution cannot give [chosen]"),
                            G3P=dict(P_s=GC.P_S, tol_s=AN.GATES["G3P_tol"], x_spread_m=AN.GATES["G3P_xspread"], Hc_ratio=AN.GATES["G3P_Hc_ratio"]),
                            G4=dict(kA_max=AN.GATES["G4_kA"], inlet_x_max=GC.IN_X1, side_y_min=GC.SD0, side_x_max=GC.SD_GEN, lip_x_max=AN.GATES["G4_lip_x"]),
                            G5=dict(max=AN.GATES["G5_max"]),
                            G6=dict(x=list(AN.GATES["G6_x"]), y_abs_max=AN.GATES["G6_y"], t_rel=list(AN.GATES["G6_t"]), Hc_min=AN.GATES["G6_Hc"],
                                    why="screen: converged crest at x %.1f m, t_fn %+.2f s, Hc %.2f m (central) / %.2f m (linear) [computed]; the crest keeps "
                                        "growing by shoaling until it breaks (central onset x %.1f m, t_fn %+.2f s), so 'conv' (the largest crest up to t_fn + 2 s) "
                                        "may be that later crest: x up to 295 m and t up to t_fn + 2 s are inside G6 [chosen]; Hc floor = 0.68 x the central "
                                        "converged crest (plan E rule)" % (cv["x"], cv["t"] - GC.T_F, cv["Hc"], lin_cv["Hc"], (on or {}).get("x", float("nan")),
                                                                          (on or {}).get("t", float("nan")) - GC.T_F)),
                            also="run complete (f_end reached), 3 groups",
                            failure_class="pipeline = run incomplete, G1, G2f (fix and rerun once, same setup name); physics = G3P, G4, G5, G6"),
            B_eligibility=dict(AN.ELIG),
            decision=dict(bar_cap=AN.DEC["bar_cap"], bar_margin=AN.DEC["bar_margin"], DF1A_miss=AN.DEC["DF1A_miss"], target_band=AN.DEC["target_band"],
                          jet_ratio=AN.DEC["jet_ratio"], plunge_groups=AN.DEC["plunge_groups"],
                          best_valid_from="DF1A 3.3 [measured] and, if valid by their own plans, plan E X2 / X1 0.5 m and DFG-2 0.5 m (read at analysis time)",
                          outcomes="INVALID / NOT_ELIGIBLE / NEW_BEST_SHAPE (miss <= bar) / TARGET_BAND (miss <= 0.5) / JET_REGIME_SEEN / NO_GAIN; physics "
                                   "flags PLUNGE_AT_CONVERGED / BREAKS_LATER / NO_BREAK_IN_WINDOW (>= 2 of 3 groups)",
                          after="no automatic follow-up run: the co-equal verdict, the print-view stills and the numbers go to the user / main session"),
            smoke_1p0=dict(role="PIPELINE CHECK ONLY (never shape-judged): new scene (D19B + N-layer VEX) and new table",
                           pass_rule="run complete; G1; G2f at the 1.0 m relative ranges; G4; G5; a group-1 crest: the largest Hc over x 150-300 m "
                                     "(|y| <= 95 m) in [t_f1 - 8, t_f1 + 6] s is >= 1.5 m and within |y| <= 20 m of the axis (x reported, not gated: on "
                                     "the beach every crest grows shoreward)",
                           on_fail="the 0.5 m run does not start; the main session reads the smoke and decides (as DFG-2's AM-DFG3)")),
        screen=dict(tool="Tools/GWWaveGen/flip52b/dfg52b_screen.py (WKB DirField per component on D19B + column-wise local Sharma-Dean 2nd order; frozen e51 "
                         "ruler; calibrated on X2 0.5 m and the D19B plunging breakers)",
                    calibration=dict(rule=cal["rule"], X2=dict(R=r(cal["X2"]["R"]), R_lin=r(cal["X2"]["R_lin"]), dX_m=cal["X2"]["dX_m"], dT_s=r(cal["X2"]["dT_s"]),
                                                               W_ratio={k: r(v) for k, v in cal["X2"]["W_ratio"].items()}, screen_focus_Hc=cal["X2"]["screen_focus"]["Hc"],
                                                               screen_focus_x=cal["X2"]["screen_focus"]["x_pk"], screen_miss=cal["X2"]["screen_focus"].get("miss"),
                                                               measured=dict((k, cal["X2"]["measured"][k]) for k in ("Hc", "x_pk", "W50", "W80", "W95", "K", "S2", "miss", "N1"))),
                                     D_breakers=dict((k, dict(gamma=r(cal[k]["gamma_meas"]), screen_crest_at_onset=r((cal[k]["screen_at_onset_x"] or {}).get("eta")),
                                                              R_breaking_limited=r(cal[k]["R"]))) for k in ("DM1A", "DF1A")),
                                     T7_shore_onsets=cal.get("T7_shore_onsets")),
                    candidates=alts,
                    chosen=dict(x_f=GC.X_F, t_f1=GC.T_F, why="the rule in sea.focus.rule; among the candidates it has the highest converged Hc / h (%.2f) "
                                "and the shortest converged -> onset delay (%.1f s) of the central model, at the price of aperture %.2f" % (
                                    cv["ratio"], fp["onset_after_converged_s"] or float("nan"), ch["arrival"]["aperture"])),
                    finding=("with a_sum = DM1A's (6.33 m over 102 components) the FLIP-calibrated converged crest is %.1f m (central) / %.1f m (linear) at "
                             "h %.1f m: Hc / h %.2f-%.2f, far below the D19B onset ratio %.2f (%.2f-%.2f) [computed]; so the group does NOT reach near-limiting "
                             "height at the converged instant on this slope; the central model breaks it %.1f s later at x %.1f m (h %.1f m, Hc %.1f m), "
                             "the linear model only in h < 5 m (x > 300 m, as X2 / X1's shore breakers). With the DM1A input variance (a_sum %.2f m, "
                             "energy matched, NOT used: Q39) the linear scaling gives Hc %.1f m and Hc / h %.2f at the converged crest, i.e. at the D onset "
                             "ratio [computed, linear scaling]" % (cv["Hc"], lin_cv["Hc"], cv["h"], lin_cv["Hc"] / cv["h"], cv["ratio"], cal["rule"]["gamma"],
                                                                    cal["rule"]["gamma_range"][0], cal["rule"]["gamma_range"][1],
                                                                    fp["onset_after_converged_s"] or float("nan"), (on or {}).get("x", float("nan")),
                                                                    (on or {}).get("h", float("nan")), (on or {}).get("Hc", float("nan")), asum_energy,
                                                                    cv["Hc"] * asum_energy / C["a_sum"], cv["Hc"] * asum_energy / C["a_sum"] / cv["h"]))),
        expected=dict(
            tag="[computed] screen, [calibrated] X2 / D19B, [guess] where marked",
            converged=dict(x_m=cv["x"], h_m=r(cv["h"]), t_rel_tfn_s=r(cv["t"] - GC.T_F), Hc_m=dict(central=r(cv["Hc"], 2), linear=r(lin_cv["Hc"], 2), range=[3.6, 5.2]),
                           Hc_over_h=dict(central=r(cv["ratio"]), linear=r(lin_cv["Hc"] / cv["h"]))),
            onset=dict(central=(dict(x_m=on["x"], h_m=r(on["h"], 2), t_rel_tfn_s=r(on["t"] - GC.T_F, 2), Hc_m=r(on["Hc"], 2)) if on else None),
                       linear="no onset with h >= 5 m (x <= 300 m): near-shore breaking as X2 / X1 (x 308-323 m, eta 2.1-3.2 m) [computed + measured analogue]",
                       gamma_hi=fp.get("onset_gamma_hi"), gamma_lo=fp.get("onset_gamma_lo"),
                       P_plunge_at_converged=0.15, P_break_in_window=0.6, tag="probabilities [guess]"),
            convergence=dict(screen_at_onset=dict((k, om.get(k)) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "miss")),
                             X2_width_calibrated=om.get("X2_width_calibrated"),
                             central_core_miss=1.0, range=[0.2, 2.5],
                             note="the screen's onset field is the 2nd-order field near the h 5 m edge (its 2nd-order part is large there); X2 measured "
                                  "1.88 median vs its screen 1.41: the central 1.0 adds that bias to the X2-calibrated 0.23 [guess]",
                             N1=[0.2, 0.6], Nt=dict(screen_x275_conv=r(ch["screen"]["Nt"].get("Nt_lin_x275_conv")), central=0.85, range=[0.6, 1.0],
                                                    note="the 7 s / 9.33 s crests 7-9 s before / after also shoal; E1t (<= 0.75) likely fails [guess]"),
                             E2_Hc_ge_5=dict(P=0.5, why="the 'max' instant is the onset's (Hc ~5.7 central) if it breaks in the window, else the converged crest (4.5)"),
                             c_in110_lin_m=r(ch["screen"]["c_in110_lin"]), P_NEW_BEST_SHAPE=0.2, P_valid=0.6),
            print_ruler=dict(breaker_type=pe.get("breaker_type"), iribarren_b=r(pe.get("iribarren_b")), iribarren_DM1A=r(pe.get("iribarren_DM1A")),
                             iribarren_DF1A=r(pe.get("iribarren_DF1A")), expected=pe.get("expected"), score3=dict(central=1.0, range=[0.5, 2.4]),
                             lip=dict(central=0.2, range=[0.0, 0.4]), print=AN.COEQ["print_ref"], DM1A_median_best_score3=AN.COEQ["score3_DM1A_median"],
                             X2_at_its_max=dict(score3=2.449, back=11.9, width07=3.45, lip=0.0, hood=0.0, chord=16.8, note="measured 2026-10-17 22:20 on "
                                                "S51X2 frame 983 (non-breaking focused crest) with the same ruler"),
                             P_print_match_ok=0.3, tag="[guess]: 5 breakers of 3 D19B runs (T 10-12 s) + the period trend; no T 7 plunging breaker measured"),
            P_progress=0.1),
        cost=dict(smoke=te_s, main=te_m, max_hours=dict(smoke=PC.MAX_H[1.0], main=PC.MAX_H[0.5]), particles_main_M=r(cm["precheck"]["particles_model"] / 1e6, 2),
                  build_min=[3, 8], analysis_min=dict(judge=2, pv53_unity=[5, 12], video=[2, 5]),
                  total_h=[r(te_s["est_h"][0] + te_m["est_h"][0] + 0.15, 2), r(te_s["est_h"][1] + te_m["est_h"][1] + 0.35, 2)]),
        order=["freeze this plan (no FLIP52B run exists)", "wait for DFG-2's final status line and no hython (auto_DFGB.py)", "build (x52b_build.py)",
               "1.0 m smoke (pipeline only)", "0.5 m run", "g52b_ana judge -> pv53 run (Unity print view) -> g52b_ana coequal -> g52b_video"],
        automation=dict(script="G:/research/Wave Simulation/_tools/auto_DFGB.py", start="py -3.10 -B \"G:/research/Wave Simulation/_tools/auto_DFGB.py\"",
                        status="Unity/Build/FLIP52B/_logs/auto_DFGB_status.txt (prefix 'DFGB ')",
                        sha256=(GC.sha256_file("G:/research/Wave Simulation/_tools/auto_DFGB.py") if os.path.exists("G:/research/Wave Simulation/_tools/auto_DFGB.py") else None),
                        wait_rule="starts only after the LAST 'DFG ' line of Unity/Build/FLIP52/_logs/auto_DFG_status.txt matches exactly "
                                  "^<date> <time> DFG FINISHED( <msg>)?$, no auto_DFG*.py / g52_chain.py / g52_run.py process and no hython, on 3 "
                                  "consecutive polls with the same last line"),
        honesty=dict(chosen_at_inlet=plan_chosen(), computed_by_FLIP="propagation, dispersion, refraction, shoaling, focusing, the crest's growth, breaking, "
                                                                     "any jet / plume",
                     input_energy="the DFG-2B input variance is 0.354 x DM1A's (same as DFG-2): the height comes from focusing 102 small components "
                                  "(max 0.095 m), not from a bigger sea",
                     not_done="no input enlargement, no force toward a shape, no wind or current; the target picture only through e51; nothing committed; "
                              "README / Docs not edited; no Houdini started while DFG-2 runs; no file of the running DFG-2 touched"),
        risks=["with a_sum = DM1A the converged crest stays at Hc / h ~0.4-0.47 (screen): the group may not break at the converged instant; "
               "breaking 2-4 s later in h ~7 m or only near the shore",
               "Iribarren ~0.32 at the predicted onset (DM1A 0.47, DF1A 0.42): spilling / weak plunging is likely, so the print ruler (lip, hood) may "
               "be worse than DM1A",
               "aperture 0.72: 28 % of the focal linear sum would need side-band generation beyond x 210.25 m (the option-D band absorbs there)",
               "the 2nd-order screen is a local approximation on a 1:10 slope and grows strongly in h < 8 m; the conservative linear model is "
               "reported beside it",
               "G2f n5 may be low (resolution damping of the 5.6 s wave): the gate is relative to DFG-2's measured realisation",
               "Nt (temporal isolation) on a beach: the 7 / 9.33 s crests before / after also shoal; E1t may fail",
               "the 1.0 m smoke damps the 5.6 s component strongly (DFG-2 smoke n5 0.43): it is a pipeline check only"],
        metrics_ruler=dict(e51="Tools/GWWaveGen/flip51/e51_metrics.py", e51_sha256=AN.E51_SHA,
                           print_view="Tools/GWWaveGen/flip53/pv53.py (sha at freeze %s)" % (GC.sha256_file(AN.PV53)[:16] if os.path.exists(AN.PV53) else None)),
        table_check=dict(all_ok=tc["all_ok"], content_sha256=tc["content_sha256"], ok=tc["ok"]),
        code_sha256={("Tools/GWWaveGen/flip52b/" + nm): GC.sha256_file(os.path.join(HERE, nm)) for nm in GC.CODE_FILES if os.path.exists(os.path.join(HERE, nm))},
        inputs_sha256={rel: GC.sha256_file(GC.REPO + "/" + rel) for rel in ("Unity/Build/FLIP52B/screens/calib_52b.json",
                                                                           "Unity/Build/FLIP52B/screens/dfg52b_xf%s.json" % GC.tag(GC.X_F),
                                                                           "Unity/Build/FLIP52B/plan/table_check_DFGB.json",
                                                                           "Unity/Build/FLIP52/plan/plan_DFG_frozen.json")},
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        frozen_before_any_FLIP52B_run=True)
    return plan


def plan_chosen():
    return ("P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and Gaussian weights, a_sum 6.331240 m (= DM1A), the D19B tank and "
            "its option-D bands, the focus (%.2f, 0) at t = %.0f + 28 m s (rule in sea.focus)" % (GC.X_F, GC.T_F))


def freeze():
    ex = runs_exist()
    if ex:
        raise SystemExit("FLIP52B run folders exist (%s): the plan is frozen; change it only by an amendment" % ex[:3])
    if os.path.exists(GC.PLAN) and "--refreeze-before-runs" not in sys.argv:
        raise SystemExit("%s exists; --refreeze-before-runs (allowed only while no FLIP52B run exists)" % GC.PLAN)
    p = build()
    GC.jdump(p, GC.PLAN)
    h = GC.sha256_file(GC.PLAN)
    open(GC.PLAN + ".sha256", "w", encoding="utf8").write("%s  plan_DFGB_frozen.json\n" % h)
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
        print(json.dumps(GC.clean(build()), ensure_ascii=False, indent=1)[:20000])
    elif a[0] == "freeze":
        p, h = freeze()
        print("frozen", GC.PLAN, h)
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
