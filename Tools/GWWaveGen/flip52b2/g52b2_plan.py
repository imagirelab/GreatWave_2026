# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3 (DFG-2B round 2): write and FREEZE Unity/Build/FLIP52B2/plan/plan_DFGB3_frozen.json (+ .sha256) BEFORE any FLIP52B2 run
(py -3.10 -B; numpy). 2026-10-18 written new (Claude). Reads (read only): DFG-2B-E's run results (judge, co-equal, pv53 json, cfg, table, G1),
the FLIP52B frozen plan and amendments, DM1A's cfg and table, the round-2 design screen outputs (Unity/Build/FLIP52B2/diag/*.json), the flip52b2
code. Writes: the DFGB3 generator table (Unity/Build/FLIP52B2/tables/), its G1 check (plan/table_check_DFGB3.json) and the frozen plan + .sha256.
It refuses to (re)freeze once a FLIP52B2 run folder exists (Unity/Build/FLIP52B2/runs/<run_id>).
usage: py -3.10 -B g52b2_plan.py draft     print the plan (nothing written except the table npz and its G1 check)
       py -3.10 -B g52b2_plan.py freeze    write plan_DFGB3_frozen.json + .sha256 (no FLIP52B2 run may exist)
       py -3.10 -B g52b2_plan.py verify    plan sha, code sha as frozen, automation sha (json to stdout; reads only)
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, time, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52b2_common as GC            # noqa: E402
import g52b2_table as TB             # noqa: E402
import g52b2_mkcopy as MK            # noqa: E402

AUTO = "G:/research/Wave Simulation/_tools/auto_DFGB3.py"
INPUTS = ["Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json",
          "Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/coequal_DFGB.json",
          "Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json",
          "Unity/Build/FLIP52B/runs/ready/DFGB2E_D19B_xf272p25_dp0p5.json",
          "Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz",
          "Unity/Build/FLIP52B/plan/table_check_DFGBE.json",
          "Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json",
          "Unity/Build/FLIP52B/plan/amendments.jsonl",
          "Unity/Build/FLIP50/tables/D_DM1_T12_W140_c5c22196af32.npz",
          "Unity/Build/FLIP50/runs/ready/DM1A_D19B_T12_th80_dp0p5.json",
          "Unity/Build/FLIP52S2/plan/plan_DFGS2_frozen.json",
          "Unity/Build/FLIP52B2/diag/cs1_G2fcomp.json",
          "Unity/Build/FLIP52B2/diag/cs1_model.json",
          "Unity/Build/FLIP52B2/diag/screen2_bfmodel.json",
          "Unity/Build/FLIP52B2/diag/screen2_g4lin.json",
          "Unity/Build/FLIP52B2/diag/screen2_g4ts.json",
          "Unity/Build/FLIP52B2/diag/screen2_refl.json",
          "Unity/Build/FLIP52B2/diag/screen2_g4refl_c2_1to3_hL11p5_shelf6.json",
          "Unity/Build/FLIP52B2/diag/screen2_g4refl_c2_1to3_hL11p5_shelf5.json",
          "Unity/Build/FLIP52B2/diag/screen2_g4refl_c3_1to5_hL11p5_shelf6.json",
          "Tools/GWWaveGen/flip53/pv53.py",
          "Tools/GWWaveGen/flip51/e51_metrics.py",
          "Tools/GWWaveGen/flip52b/g52b_ana.py",
          "Tools/GWWaveGen/flip52b/g52b_video.py"]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run_exists():
    return [p for p in (GC.RUNS_ROOT + "/" + GC.RID["main"],) if os.path.exists(p)]


def build_plan():
    import g52b2_pcfg as PC
    import g52b2_ana as GA
    C = GC.components()
    tp, tsha, tch, tinfo = TB.write()
    tc = TB.checks()
    GC.jdump(tc, GC.TABLE_CHECK)
    if not tc["all_ok"]:
        raise SystemExit("the G1 table check fails: %s" % tc["ok"])
    bs = GC.bed_selfcheck()
    if not bs["ok"]:
        raise SystemExit("the bed self-check fails")
    gen = MK.build_all()
    badc = [nm for nm, s in gen.items() if open(os.path.join(HERE, nm), encoding="utf8").read() != s]
    if badc:
        raise SystemExit("generated copies differ from g52b2_mkcopy output: %s" % badc)
    E = TB.energy_in_tank()
    c = PC.make("main")
    pre = c["precheck"]
    te = pre["time"]
    J = GC.jload(GC.DFGBE_JUDGE)
    PV = GC.jload(GC.DFGBE_PV53)
    pl_vals = [p["conv_print"]["miss"] for p in PV["periods"]]
    pl_hc = [p["conv_print"]["Hc"] for p in PV["periods"]]
    refs = GA.pl_refs()
    best, rows = GA.best_valid()
    lin = tc["linear_refs"]
    plan = {
        "status": "FROZEN",
        "plan": "DFGB3",
        "campaign": "FLIP52B2-DFGB3 (DFG-2B round 2)",
        "tags_legend": {"[measured]": "【測定】", "[computed]": "【計算】", "[literature]": "【文献】", "[guess]": "【推測】", "[chosen]": "【選び】",
                        "[calibrated]": "【計算】 (a screen number scaled by a measured FLIP / screen ratio)"},
        "title": ("FLIP52B2 plan DFGB3 (DFG-2B round 2): DFG-2B-E's energy-matched DFG-2 group sea (P 28 s; T 9.33 / 7 / 5.6 s; the 34 X2 directions; "
                  "spectral energy = DM1A) with a generator PHASE CALIBRATION (layer n x exp(-i phi_n), phi = DFG-2B-E's measured G2f phases) on a "
                  "TWO-SLOPE bed: the D19B 1:10 beach to depth 11.5 m at x 235.25 m (DFG-2B-E's measured converged x), then 1:3 to a 6 m shelf at "
                  "x 251.75 m, so that the crest curls on the face right after it converges"),
        "trigger": {
            "goal_round2": ("the crest should curl (print-like plunge) at or very near the converged instant: convergence measured AT the most "
                            "print-like instant must improve clearly over DFG-2B-E's 2.16 / 2.27 / 2.37, with the print match not worse (bars) and "
                            "Hc not lower; and the gates (G2f, G6 included) pass so the run is valid"),
            "user_rules": {"Q83": "progress = convergence AND print match (co-equal)", "Q84": "incoming sea at equal total (spectral) wave energy to "
                           "DM1A (sum a^2 = 1.336153 m^2 at the generation depth); the report states it incl. the in-tank power ratio",
                           "Q81_Q82": "decide self-checkable things yourself; work never stops"},
            "parent": "DFG-2B-E = Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5 (plan_DFGB_frozen.json + AM-DFGB1/1a/1b/2), the best run so far, "
                      "formally INVALID (G2f n5 phase 0.514 rad > 0.35; G6 group 1 converged at t_fn - 4.04 s, window from t_fn - 4)"},
        "physics_rules": {
            "forces": "gravity, the bed and the incoming waves only; no force toward a shape; no wind, no current (the return current only cancels the "
                      "target's own mean mass flux)",
            "Q84": "the incoming sea has the same SPECTRAL energy as DM1A (sum a^2 = 1.336153 m^2 at h0 19 m) = DFG-2B-E's (AM-DFGB1); the phase "
                   "calibration has |factor| = 1 and changes neither the spectral energy nor the period-mean in-tank power [computed]",
            "calibration_not_a_force": "the phase pre-compensation only advances each frequency layer of the inlet / side-band TARGET in time "
                                       "(n3 -0.090 s, n4 +0.311 s, n5 +0.458 s; a negative value = a delay) so that the realised wave at the G2f gauges equals the design; it acts "
                                       "only inside the generation bands (x <= 100 m, side band x <= 210.25 m), never on the crest",
            "Q54_honesty": "chosen at the inlet: P, the three frequencies and equal weights, the 34 X2 directions and weights, the energy-matched a_sum, "
                           "the design phase reference (272.25, 0) at t = 63 + 28 m s, the calibration phi (measured on DFG-2B-E), the D19B tank and bands, "
                           "the bed (foot depth 11.5 m, 1:3, shelf 6 m), the exit sponge; computed by FLIP: propagation, dispersion, refraction, "
                           "shoaling, reflection at the face, focusing, the crest's growth, breaking, any jet / plume / bore"},
        "sea": {
            "P_s": GC.P_S, "harmonics_n": list(GC.HARMONICS), "T_s": [round(GC.P_S / n, 6) for n in GC.HARMONICS],
            "freq_weights": [round(float(v), 6) for v in C["wf"]], "directions_deg": [round(float(v), 6) for v in C["th"]],
            "dir_weights": [round(float(v), 6) for v in C["wd"]], "dspec": list(GC.DSPEC), "n_components": int(C["a"].size),
            "a_sum_m": round(float(C["a_sum"]), 6), "a_max_component_m": round(float(C["a"].max()), 6),
            "amp_per_freq_m": [round(float(C["a_sum"] * v), 6) for v in C["wf"]], "generation_depth_m": GC.H0, "ramp_s": GC.RAMP_S,
            "same_as_DFGB2E": "frequencies, P, weights, the 34 directions, a_sum (AM-DFGB1 x 1.680585), the design phase reference and t_f bit for bit; the "
                              "DESIGN table equals DFG-2B-E's table float32 field by field (G1 'design_equals_DFGB_E')",
            "focus": {"x_m": GC.X_F, "y_m": 0.0, "t_f_s": GC.T_F, "times_s": list(GC.FOCI), "h_on_design_bed_m": round(GC.H0 - (GC.X_F - GC.X_TOE) / GC.SLOPE_S, 6),
                      "h_on_DFGB3_bed_m": GC.h_of(GC.X_F),
                      "meaning": "the GENERATOR's phase reference (= DFG-2B-E's design focus on the 1:10 beach, DirField over D19B); on the DFGB3 bed x 272.25 m "
                                 "lies on the 6 m shelf. The converged crest is expected where DFG-2B-E's formed, x 228-238 m [measured], upstream of the "
                                 "foot: the bed is unchanged there (x <= 235.25 m) [chosen]"},
            "energy": {
                "basis": "equal spectral energy (Q84): the energy density 0.5 rho g sum a^2 of the incoming components at the generation depth h0 19 m "
                         "(= DM1A's generation depth), as in an open sea of unbounded width",
                "statement": GC.sea_text(), "sum_a2_m2": round(E["spectral"]["sum_a2_m2"], 6), "DM1A_sum_a2_m2": round(GC.DM1A_SUM_A2, 6),
                "ratio": round(E["spectral"]["ratio"], 9), "E_Jm2": round(E["spectral"]["E_Jm2"], 1), "Hm0_spectral_m": round(E["spectral"]["Hm0_spectral_m"], 4),
                "in_tank": dict(inlet_variance_over_DM1A=round(E["DFGB3"]["inlet_variance_over_DM1A"], 6),
                                interior_power_over_DM1A=round(E["DFGB3"]["interior_power_over_DM1A"], 6),
                                power_into_interior_MW=round(E["DFGB3"]["power_into_interior_MW"], 4),
                                DM1A_power_into_interior_MW=round(E["DM1A"]["power_into_interior_MW"], 4),
                                inlet_Hm0_equiv_m=round(E["DFGB3"]["inlet_band_Hm0_equiv_m"], 4), DM1A_inlet_Hm0_equiv_m=round(E["DM1A"]["inlet_band_Hm0_equiv_m"], 4),
                                equals_DFGB_E=E["DFGB3_equals_DFGB_E_power"], reproduces_AM_DFGB1b=E["reproduces_AM_DFGB1b"]["ok"],
                                tag="[computed] g52b2_table.energy_in_tank: numpy on the linear input tables (the AM-DFGB1b rule on the D19B layout)"),
                "statement_in_tank": E["statement_en"],
                "report_rule": "every judge, co-equal verdict and status line states 'equal spectral energy (Q84)' AND the in-tank ratios (inlet variance "
                               "0.128 x, interior power 0.234 x DM1A's)"}},
        "calibration": {
            "what": "(b) generator phase pre-compensation: every table layer n (er/ei, ur/ui, vr/vi) x exp(-i phi_n); kk, hh, mx, my unchanged",
            "phi_rad": {str(k): v for k, v in GC.PHI_COMP.items()},
            "source": "Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json G2f per_n phase_err_rad [measured]",
            "rule": GC.PHI_RULE,
            "time_advance_s": {str(n): round(GC.PHI_COMP[n] / (2 * np.pi * n / GC.P_S), 4) for n in GC.HARMONICS},
            "G2f_reference": "the DESIGN target (= DFG-2B-E's table at the gauges, cfg dir.linear_refs.G2f_gauges); the generator content is recorded as "
                             "G2f_gauges_table (report): G2f measures whether the realised wave equals the design",
            "screen": "linear: G2f phase about 0 after (b); G4 side band 0.381 (base 0.382), FLIP-equivalent 0.396 [computed, diag/screen2_g4lin.json]; CS1: "
                      "converged t_f - 3.88 s at x 235.5 m, Hc 8.34 m [calibrated, diag/cs1_G2fcomp.json]",
            "tag": "[calibrated]"},
        "tank": {
            "kind": "half tank, symmetry plane y = 0, the D19B tank of DFG-2B-E with the DFGB3 bed and an exit sponge on the shelf",
            "h0_m": GC.H0, "Lx_m": GC.LX, "W_m": GC.W_MAIN, "z_bed_m": GC.ZB, "z_top_m": GC.Z_TOP,
            "bed": {"x_toe_m": GC.X_TOE, "slope1_1_in": GC.SLOPE_S, "h_foot_m": GC.H_L, "x_foot_m": GC.X_FOOT, "slope2_1_in": GC.S2,
                    "shelf_h_m": GC.H_TOP, "x_edge_m": GC.X_EDGE, "shelf_to_x_m": GC.LX,
                    "formula": GC.bed_formula(GC.SPEC_BED), "vex_path": "FLIP49 two-slope branch (pgon / rise2 / bedy_pg / bedgrad_pg), no new VEX",
                    "ctrl": {k: v for k, v in GC.bed_parms(GC.SPEC_BED).items()},
                    "selfcheck": {k: bs[k] for k in ("ok", "equals_analytic_bit", "laterally_uniform", "grad_ok", "sdf_ok", "two_slope_path",
                                                     "design_dirfield_bed_equal_upstream_of_foot", "x_foot_m", "x_edge_rule_m", "depth_min_max_m")},
                    "why": "at the converged instant DFG-2B-E's crest is already depth-limited (Hc/h 0.73-0.76) and on 1:10 it rides 0.5-1.0 s at the limit "
                           "before breaking starts, which costs about 0.8 of miss; a 1:3 face at the converged point (Iribarren ~1.0-1.3: plunging; 1:10 "
                           "0.3-0.4) removes the ride [calibrated / guess, design]",
                    "reflection": "linear eigenfunction matching: R T 9.33 s 0.08-0.10, T 7 s 0.05-0.06, T 5.6 s 0.026 (1:10 over the same depths 0.01-0.04); "
                                  "reflected power <= ~1 % of incident; effect (linear upper bound, no band damping): G4 side -0.006, G2f n3 gauge amplitude "
                                  "x 0.951, centre crest +2.4 % [computed, diag/screen2_refl.json, screen2_g4refl_*.json]",
                    "tag": "[chosen] round-2 design (c)"},
            "solver": {"dp": [0.5], "gridscale": 2.0, "cfl": 1.0, "pcfl": 0.75, "minsub": 1, "maxsub": 8, "veltransfer": "flip"},
            "bands": {"inlet": {"x_m": [0.0, 100.0], "xg_end": GC.IN_X1, "wall_taper_m": GC.WALL_TAPER, "relax_g": 1.0, "in_gain": 1.0},
                      "side": {"y_m": [GC.SD0, GC.W_MAIN], "sd0": GC.SD0, "sd_gen": GC.SD_GEN, "sd_sw": GC.SD_SW, "sd_sigma": GC.SD_SIGMA, "sd_pow": GC.SD_POW,
                               "sd_taper_m": GC.SD_TAPER, "sd_gain": 1.0},
                      "exit_sponge": {"abs_on": 1, "xa0_m": GC.XA0, "x_m": [GC.XA0, GC.LX], "abs_sigma": GC.ABS_SIGMA, "abs_pow": GC.ABS_POW,
                                      "why": "the shelf keeps 6 m of water to the end wall x 412 m: without a sponge the bores reflected at the wall return about "
                                             "40 s later and contaminate groups 2-3; DFG-S's values (80 m, sigma 1.0, pow 2) [chosen; infrastructure, not shaping]"},
                      "ret_on": 1, "dir_on": 1,
                      "volume": {"stage": "A", "vol_x_m": list(GC.VOL_X), "DFGB2E_vol_x_m": list(GC.VOL_X_DFGBE),
                                 "why": "the stage A window must lie outside the bands (layout A rule: 5 m before the exit sponge) [chosen]"}},
            "parms_differ_from_DFGB2E": dict(PC.PARMS_DIFFER_FROM_DFGBE),
            "named_differences": "bed (shelf_h, pg_hL, pg_s2), exit sponge (abs_on, xa0, abs_sigma), stage A window end (vol_x1); every other parm = DFG-2B-E's "
                                 "launched cfg (g52b2_pcfg precheck 'parms_equal_DFGBE_except_named'); the generator table differs only by the phase factor",
            "sea_into_tank": "N-layer table (g52b2_table: DFG-2B-E's WKB DirField per harmonic over D19B x exp(-i phi_n), 1 m, x 0-214 m, y 0-140 m) read by "
                             "the unchanged N-layer VEX of flip52/g52_tanklib.py in a new scene Houdini/FLIP52B2/g52b2_tank.hiplc",
            "interior": {"scan_x_m": list(GC.SCAN_X), "y_abs_max_m": GC.INTERIOR_Y, "N1_x_m": list(GC.INTERIOR_X), "Nt_x_m": [150.0, 275.0]}},
        "records": {
            "hf": "top-surface height field (1 m) every frame", "r2": "centre section y 0.5 m every frame (print ruler, lips)",
            "r3": "section y 77 m every frame (report)", "r4": "per-y sections x 190-335 m, y 0-95 m, every 3rd frame in the group windows",
            "r5": "surface meshes every 3rd frame in the group windows (Unity print view, mp4)",
            "gauges": "x 110 / 128 / 160 m, y 0.5 / 20 / 40 / 60 / 80 m (G2f at x 110 m)",
            "checkpoints": "every 48 frames (resume after the 1740 s launch limit)", "group_window_s": list(GC.GROUP_WIN), "t_end_s": PC.T_END[0.5],
            "windows_main_s": c["records"]["windows"], "no_1m_smoke": "no 1.0 m smoke: the code path, sea and records are DFG-2B-E's (which ran); the new "
                                                                     "bed / sponge are covered by the hython build check (VEX = numpy, particles, band probe)"},
        "criteria": {
            "coequal": {
                "COEQ_note": "CO-EQUAL CRITERIA, shown side by side for every judged run (user Q83); ALL are needed for progress",
                "criterion_1": "the Unity PRINT-VIEW render (option-D composition) at the run's most print-like instant + a front view + the print "
                               "(Tools/GWWaveGen/flip53/pv53.py run <run dir>, unchanged; its stills and mp4 are shown to the user)",
                "criterion_2": "the centre section vs the Hokusai print outline with the print ruler (score3, hollow, lip, back 0.7-0.9 eta_c, width07) at "
                               "the most print-like instant of each group (pv53 rule: frames [t_max - 1.5, t_max + 3.0] s of the judge's 'max' instant, "
                               "crest floor 0.6 Hc (AM-DFG2a))",
                "criterion_3": "the convergence metrics (flip51/e51_metrics.py frozen ruler, target read from the user's screenshot through its frozen read "
                               "values only) at the judge's 'max' instants, medians over the groups, and the frozen decision",
                "criterion_3b": "convergence AT THE MOST PRINT-LIKE INSTANT (pv53 periods[].conv_print.miss, median over the groups) <= bar_pl",
                "criterion_3c": "Hc not lower than DFG-2B-E's (converged and print-like)",
                "score3_bar": GA.COEQ["score3_bar"], "score3_DM1A_median": GA.COEQ["score3_DM1A_median"], "tol": GA.COEQ["tol"], "lip_min": GA.COEQ["lip_min"],
                "conv_outcomes": GA.COEQ["conv_outcomes"], "print_ref": GA.COEQ["print_ref"],
                "print_like_instant": {"cap": GA.COEQ_PL["cap"], "margin": GA.COEQ_PL["margin"], "min_groups": GA.COEQ_PL["min_groups"],
                                       "xwin_rel_m": list(GA.COEQ_PL["xwin_rel"]), "ymax_pv53_m": GA.COEQ_PL["ymax_pv53"],
                                       "measure": "pv53 periods[].conv_print.miss (primary; the measure of DFG-2B-E's 2.16 / 2.27 / 2.37); a recomputation "
                                                  "with the judge's eta0 is reported beside it and used only where pv53's value is missing",
                                       "DFGB2E_measured": [round(v, 6) for v in pl_vals], "DFGB2E_median": GA.COEQ_PL["DFGB2E_median"],
                                       "DFGB2E_median_read_at_freeze": round(float(np.median(pl_vals)), 6),
                                       "bar_round2": round(GA.COEQ_PL["DFGB2E_median"] - GA.COEQ_PL["margin"], 6),
                                       "rule": GA.COEQ_PL["rule"], "references": sorted(GA.PL_REFS),
                                       "at_freeze": {"bar_pl": round(refs["bar_pl"], 6), "best_valid_pl": refs["best_valid_pl"],
                                                     "rows": {k: dict(pl_miss_median=v.get("pl_miss_median"), valid=v.get("valid"), missing=v.get("missing"))
                                                              for k, v in refs["rows"].items()}},
                                       "why_DFGB2E_counts": "the round-2 goal is defined against DFG-2B-E (the user's / main session's task: 'clearly below "
                                                            "DFG-2B-E's median 2.27'), although DFG-2B-E is INVALID by its own plan; the valid-runs rule "
                                                            "(as DFG-S-E140) applies on top",
                                       "same_instant_report": "SAME_INSTANT_NEW_BEST if the print-like median miss <= the convergence bar",
                                       "clearly_better_report": "PL_CLEARLY_BETTER_THAN_DFGB2E if the print-like median miss <= 1.77"},
                "hc_not_lower": {"tol_m": GA.COEQ_HC["tol_m"], "DFGB2E_conv_Hc_median": GA.COEQ_HC["DFGB2E_conv_Hc_median"],
                                 "DFGB2E_pl_Hc_median": GA.COEQ_HC["DFGB2E_pl_Hc_median"], "DFGB2E_conv_Hc": GA.COEQ_HC["DFGB2E_conv_Hc"],
                                 "DFGB2E_pl_Hc_read_at_freeze": [round(v, 6) for v in pl_hc], "rule": GA.COEQ_HC["rule"]},
                "progress_rule": ("PROGRESS iff ALL of: (1) the Unity print view rendered at the most print-like instant (pv53); (2) the print match ok "
                                  "(median best-instant score3 <= 0.9485 = DM1A 0.6485 + 0.30, median best-instant lip >= 0.20); (3a) the convergence "
                                  "decision at the judge's 'max' instants NEW_BEST_SHAPE or TARGET_BAND (valid run); (3b) the median pv53 conv_print miss "
                                  "<= bar_pl = min(2.8, DFG-2B-E's 2.27 - 0.5 = 1.77, best valid earlier print-like median - 0.5); (3c) Hc not lower "
                                  "(median conv Hc >= 8.19 m, median print-like Hc >= 6.63 m). 'converged, print match worse than DM1A', 'converged and "
                                  "print-like at different instants' and 'lower crest' are NOT progress. Reported: PL_CLEARLY_BETTER_THAN_DFGB2E, "
                                  "SAME_INSTANT_NEW_BEST, PRINT_BETTER_THAN_DM1A"),
                "no_print_view_no_progress": "a run without the print-view package or without its Unity render is INCOMPLETE, never progress",
                "energy_report": "every verdict carries the Q84 energy statement (equal spectral energy; in-tank inlet variance and interior power ratios)"},
            "groups": {"window_s": list(GC.GROUP_WIN), "scan_x": list(GC.SCAN_X), "onset_x": [200.0, 335.0], "Nt_x": [150.0, 275.0],
                       "conv": "R2: the largest Hc over x 150-300 m, |y| <= 95 m in [t_fn - 8, min(t_fn + 2, t_lip1)) s, t_lip1 = the first r2 lip "
                               "(AM-DFG1 test, x 200-335 m) at t >= t_fn - 6.9 s; no such lip -> [t_fn - 8, t_fn + 2] (= DFG-2B); the DFG-2B 'conv' is "
                               "reported beside it",
                       "conv_lip_from_rel_s": GA.GROUP["conv_lip_from_rel"],
                       "why_conv": "on the 1:3 face the plunge (lip ~0.6-1.2 s after convergence) throws splash-up inside [t_fn - 8, t_fn + 2]; the frozen "
                                   "'largest Hc' could take it for the converged crest and distort G3P / G6 and the metrics [design risk]",
                       "onset": "first r2 lip (AM-DFG1 test) at x 200-335 m in the window (= DFG-2B)",
                       "max_instant": "plan E D rule (= DFG-2B): onset -> e51 max in [on - 3, on + 1.5] s, x [on_x - 60, on_x + 35] m; else conv",
                       "Nt_rule": "= DFG-2B: largest Hc in x 150-275 m in [t_fn - 14, t_fn + 14) at |t - t_conv| >= 3.5 s / Hc(conv)",
                       "c_in": "largest crest on x 110 m, |y| <= 95 m in [t_fn - 14, t_fn + 14)",
                       "plunge_at_converged": "r2 onset within [t_conv - 1, t_conv + 4] s and x_on <= x_conv + 30 m",
                       "reported": "dt_conv_to_lip1 = t_lip1 - t_conv (the round-2 quantity; DFG-2B-E 2.08 s median [measured, the DFGB3 judge run on "
                                   "DFG-2B-E's records]); onset on the face x %.2f-%.2f m / on the shelf" % GA.GROUP["face_x"]},
            "A_validity": {
                "G1": {"rule": "numpy table check table_check_DFGB3.json all_ok (the design = DFG-2B-E's table float32 field by field; the generator = design "
                               "x exp(-i phi_n) with the intended phase offsets; focus vs independent WKB sums; symmetry; continuity flat < 5e-3; "
                               "interpolation < 2 %; vertical profile < 1e-4; zero mass flux per layer and in total < 1e-6; P-periodicity; energy = DM1A) + "
                               "build_check52b2 all_ok with the hip the launches used + cfg precheck ok"},
                "G2f": {"rule": GA.G2F_RULE, "x": 110.0, "y": list(GC.GAUGE_Y), "window_main_s": list(GA.GATES["G2f_t_main"]),
                        "floor_0p5": GA.GATES["G2f_floor_0p5"], "margin_0p5": GA.GATES["G2f_margin_0p5"], "hi_0p5": GA.GATES["G2f_hi_0p5"],
                        "phase_0p5": GA.GATES["G2f_phase_0p5"], "reference_ranges": "DFG-2 0.5 m measured R (n3 1.048, n4 0.973, n5 0.788) - 0.10, floor 0.60",
                        "calibration_stated": "the comparison target is the DESIGN (= DFG-2B-E's G2f reference bit for bit); the generator carries exp(-i phi_n)",
                        "risk": "the face reflection lowers the n3 gauge amplitude by up to x 0.951 (linear, steady) against measured 0.995 and floor 0.948 [computed]"},
                "G3P": {"P_s": GC.P_S, "tol_s": GA.GATES["G3P_tol"], "x_spread_m": GA.GATES["G3P_xspread"], "Hc_ratio": GA.GATES["G3P_Hc_ratio"], "on": "the 'conv' summits"},
                "G4": {"kA_max": GA.GATES["G4_kA"], "t0_s": GA.GATES["G4_t0"], "inlet_x_max": GA.GATES["G4_inlet_x"], "side_y_min": GA.GATES["G4_side_y"],
                       "side_x_max": GA.GATES["G4_side_x"], "lip_x_max": GA.GATES["G4_lip_x"], "rule": "= DFG-2B (unchanged)",
                       "margin_note": "DFG-2B-E measured 0.397 (side band, at t_fn + 4.1 s, x 166-168, y 108: the next group's generation) [measured]; linear "
                                      "generator 0.387 (design 0.386) [computed G1]; FLIP-equivalent 0.396 [calibrated]: a validity coin-flip for any rerun of this sea"},
                "G5": {"max": GA.GATES["G5_max"]},
                "G6": {"x": list(GA.GATES["G6_x"]), "y_abs_max": GA.GATES["G6_y"], "t_rel": list(GA.GATES["G6_t"]), "Hc_min": GA.GATES["G6_Hc"],
                       "why": "R2 (registered before the run): the CS1 screen with (b) predicts the converged crest at t_fn - 3.88 s (range -3.6 .. -4.3), x "
                              "235.5 m, Hc 8.34 m [calibrated]; window = prediction +- 3 s (the half-width the frozen DFG-2B window had around its own screen "
                              "value), x 215-260 m around the measured 228-238 m; Hc floor = 0.68 x 8.34 m (the plan E rule) = 5.67 m. The DFG-2B window "
                              "(t_fn - 4 .. + 2, x 225-295, Hc 3.0) was centred on a screen value that was wrong by 3 s [measured]; read with this window, "
                              "DFG-2B-E's G6 passes (judge run on its records) [measured]"},
                "also": "run complete (f_end reached), 3 groups",
                "failure_class": "pipeline = run incomplete, G1, G2f (the main session looks for a pipeline cause and reruns once, same setup name, only if "
                                 "one is found; a calibration that does not reproduce is reported, not iterated); physics = G3P, G4, G5, G6"},
            "B_eligibility": dict(GA.ELIG),
            "decision": {"bar_cap": GA.DEC["bar_cap"], "bar_margin": GA.DEC["bar_margin"], "DF1A_miss": GA.DEC["DF1A_miss"], "target_band": GA.DEC["target_band"],
                         "jet_ratio": GA.DEC["jet_ratio"], "plunge_groups": GA.DEC["plunge_groups"], "best_valid_runs": sorted(GA.BEST_RUNS),
                         "best_valid_from": "DF1A 3.3 [measured] and the 0.5 m runs valid by their own plans among %s (read at analysis time)" % sorted(GA.BEST_RUNS),
                         "bar_at_freeze": round(min(GA.DEC["bar_cap"], best - GA.DEC["bar_margin"]), 6), "best_valid_at_freeze": round(best, 6),
                         "best_rows_at_freeze": {k: dict(miss=v.get("miss"), valid=v.get("valid"), missing=v.get("missing")) for k, v in rows.items()},
                         "jet_note": "jet_ratio = Hc / a_sum 10.64 m (JET_REGIME_SEEN needs Hc >= 13.8 m: a report outcome only)",
                         "outcomes": "INVALID / NOT_ELIGIBLE / NEW_BEST_SHAPE (miss <= bar) / TARGET_BAND (miss <= 0.5) / JET_REGIME_SEEN / NO_GAIN; physics "
                                     "flags PLUNGE_AT_CONVERGED / BREAKS_LATER / NO_BREAK_IN_WINDOW / ONSET_ON_FACE (>= 2 of 3 groups)",
                         "after": ("no automatic follow-up run: the co-equal verdict, the print-view stills, the compare video and the numbers go to the user / "
                                   "main session. Valid + PROGRESS -> DFGB3 is the new reference. Valid, not progress -> report side by side with the "
                                   "structural finding below (no round 3 without the user / main session). INVALID by a physics gate -> report, DFGB3 "
                                   "stops. Pipeline failure -> fix the cause and rerun once.")}},
        "lessons_measured": {
            "DFGB2E": {"converged": "t 58.96 / 87.58 / 115.38 s (t_fn -4.04 / -3.42 / -3.62) at x 228.5 / 238.5 / 235.5 m, Hc 8.10 / 8.45 / 8.37 m, miss "
                                    "0.08 / 0.00 / 0.04; medians W50 2.25, W80 1.04, W95 0.49, S2 0.25, N1 0.23 [measured]",
                       "print_like": "~2.2 s later at x 259.5-266.5 m: score3 0.557 / 0.770 / 0.752, lip 0.25-0.31, back 17-18 deg (print 31), w07 1.53-1.57 "
                                     "(print 1.32), eta_c ~6.5 m; convergence there: Hc 6.8 m, W50 3.7-3.8, miss 2.16 / 2.27 / 2.37 [measured]",
                       "gates": "INVALID: G2f n5 phase 0.514 rad > 0.35 (amplitude 0.80 in range), G6 group 1 at t_fn - 4.04 s (window from t_fn - 4); G4 "
                                "side 0.397 <= 0.40 [measured]", "energy": "in-tank interior power 0.234 x DM1A (AM-DFGB1b) [computed]",
                       "conv_to_lip_s": "2.08 (median) [measured: the DFGB3 judge's dt_conv_to_lip1 on DFG-2B-E's records]"},
            "X2B": "monochromatic T 7 s crossing focused AT the break point curled only late and low: focusing into breaking depth can pre-empt the focus [measured]",
            "DFGS": "1:3 step to a 6 m shelf also curled ~2 s after convergence (print-like miss 4.36); its round-2 linear screen found no gain from moving the focus "
                    "/ edge ON A SHELF [measured / computed]; on the sloping beach (this plan) the design's BF model gives the face the lever (below)"},
        "design": {
            "choice": "(c) a two-slope bed (the one physical change) + (b) a phase-only generator calibration + the R2 registrations (G6 window, pre-lip "
                      "'conv', 3b, 3c); chosen 2026-10-18 by the round-2 design step from the numpy screens (Tools/GWWaveGen/flip52b2/b2_*.py, "
                      "Unity/Build/FLIP52B2/diag/)",
            "bf_model": "shape at the lip = shape at breaking start x the measured growth factors (6 groups over 2 beds: W50 x 1.35-1.50, W80 x 1.78-2.15, "
                        "W95 x 2.5-3.5, S2 x 1.35-1.9); self-check on DFG-2B-E as run: 2.39 (p10-p90 2.11-2.58) vs measured 2.27 (bias +0.1) [calibrated]",
            "candidates": {"b_alone": "miss at curl 2.18, physically neutral, G6 still fails without re-registration; P(progress) ~0.02 [calibrated / guess]",
                           "a_focus": "shoreward x_f 280-310: miss 2.35-2.57, Hc 8.1 -> 7.1, rejected; seaward x_f 260.25: miss 1.96, Hc 8.83, G4 0.399 "
                                      "(FLIP-equivalent); x_f 250.25: miss 1.85, Hc 9.23, conv x 225.5 at the G6 edge, G4 0.397; both keep the 0.5-1.0 s ride; "
                                      "P(progress) ~0.05 [calibrated / guess]",
                           "side_band": "generating to 210.25 / 240.25 m: miss 1.88, Hc 8.63, G4 0.386; P ~0.04 [calibrated / guess]",
                           "c_face_1to3": "BF miss at curl 1.49 (breaking at the converged instant), 1.69 (+0.25 s), 1.85 (+0.5 s); after the -0.1 bias ~1.4 / 1.6 "
                                          "/ 1.75; P(progress) 0.12-0.18 [calibrated / guess]",
                           "variants": "shelf 5 m: higher R, n3 x 0.937 (G2f risk); 1:5 face: R 0.01-0.05, breaking later, P ~0.10; 1:2 face: R 0.05-0.12 and a "
                                       "collapsing-breaker risk [computed / guess]",
                           "d_other": "no other single change has a lever: below the BF floor (miss >= ~1.1-1.8 even when breaking at the converged instant) only "
                                      "a narrower converged top (W80, W95) helps, i.e. a directional-spectrum redesign that would raise G4: not round-2 material"},
            "structural_finding_to_report": "with depth-limited breaking of this crest, the target band (miss <= 0.5) at the curl is not reachable by any of "
                                            "(a)-(d): the floor is about 1.1-1.8 [calibrated]"},
        "expected": {
            "tag": "[calibrated] CS1 / BF model, [computed] linear reflection, [guess] where marked",
            "converged": "t_fn - 3.9 s (-3.6 .. -4.3), x 228-238 m, Hc 8.3-8.6 m (CS1 8.34 m + 1-2.4 % face shoaling and reflection), converged miss ~0.05 "
                         "(convergence happens upstream of the foot, unchanged) [calibrated / computed]",
            "curl": "0.6-1.2 s after the converged instant, on the face x 240-250 m (h 8-11 m); Hc at the curl 7.0-7.4 m (DFG-2B-E 6.8) [guess]",
            "convergence_at_curl": "e51 miss median ~1.5-1.6 (1.1-1.9) vs DFG-2B-E 2.27 [calibrated, BF model]",
            "print_ruler": "score3 0.6-0.95 (bar 0.9485), lip 0.30-0.45 (bar 0.20), back 15-22 deg (print 31), w07 1.3-1.7 (print 1.32) [guess]",
            "gates": "G2f phase ~0 [calibrated], n3 amplitude 0.95-0.98 vs floor 0.948 [computed]; G4 0.391-0.397 + FLIP noise; G6 passes with the registered "
                     "window; G3P / G5 unchanged; Nt (limit 0.75; DFG-2B-E 0.70): shelf bores 0.4-0.7 [guess]",
            "energy": "spectral sum a^2 = 1.336153 m^2 = DM1A's exactly; in-tank interior power 0.234 x DM1A (computed: unchanged by the phase-only factor); "
                      "reflected power <= ~1 % of incident [computed]",
            "probabilities": {"P_valid": 0.4, "P_G2f": 0.75, "P_G4": 0.7, "P_G6": 0.9, "P_rest": 0.93, "P_forward_plunge_on_face_lip_ge_0p20": 0.85,
                              "P_miss_curl_le_1p77_given_plunge": 0.55, "P_miss_curl_le_2p0": 0.75, "P_print_bars": 0.75, "P_Hc_not_lower": 0.8,
                              "P_progress": [0.12, 0.18], "P_progress_given_valid": [0.35, 0.4], "best_alternative": "(a) x_f 250, ~0.05", "tag": "[guess]"}},
        "cost": {"main": dict(te, particles_model_M=round(pre["particles_model"] / 1e6, 6), particles_ratio_vs_DFGBE=round(pre["particles_ratio_vs_DFGBE"], 6),
                              water_m3=round(pre["water_m3"], 1)),
                 "max_hours": {"main": PC.MAX_H[0.5]}, "build_min": [3, 10], "analysis_min": {"judge": [1, 3], "pv53_unity": [5, 12], "video": [2, 5]},
                 "note": "one 0.5 m run at a time (pagefile); auto_DFGB3 resumes a max_hours stop from the last checkpoint (up to --cap-resumes, default 2)"},
        "order": ["freeze this plan (no FLIP52B2 run exists)",
                  "auto_DFGB3.py: wait for the FINAL '<date> <time> DFGS2 FINISHED' line of Unity/Build/FLIP52S2/_logs/auto_DFGS2_status.txt, no hython and "
                  "no other pipeline process on 3 consecutive polls",
                  "DFGS2_READ (report only)", "build (x52b2_build.py: table, G1, hython scene build + check)", "cfg main + dry chain gate",
                  "0.5 m run (resume on crash / stale; max_hours stops resumed up to 2 times)",
                  "g52b2_ana judge -> pv53 run (Unity print view) -> g52b2_ana coequal (3b, 3c) -> g52b2_video"],
        "automation": {"script": AUTO, "start": "py -3.10 -B \"%s\"" % AUTO, "status": "Unity/Build/FLIP52B2/_logs/auto_DFGB3_status.txt (prefix 'DFGB3 ', final "
                       "'<date> <time> DFGB3 FINISHED ...', also on exceptions)", "sha256": sha(AUTO), "started_by_author": False,
                       "wait_rule": "starts only after the LAST line starting '<date> <time> DFGS2 ' of Unity/Build/FLIP52S2/_logs/auto_DFGS2_status.txt matches "
                                    "exactly ^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} DFGS2 FINISHED( .*)?$, no hython and no other pipeline process "
                                    "(auto_*.py other than itself, *_chain.py, *_run.py, x5*_build.py, pv53.py) on 3 consecutive polls with the same last line; "
                                    "yields (launches nothing) if a restarted auto_DFGS2.py sits in 'WAIT DFG-2B-E' on 3 polls",
                       "simulate": "py -3.10 -B auto_DFGB3.py --simulate[=scenario.json]: no wait, no launch, nothing written"},
        "honesty": {
            "chosen_at_inlet": "P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and Gaussian weights, a_sum 10.640186 m (spectral "
                               "energy = DM1A, AM-DFGB1), the design phase reference (272.25, 0) at t = 63 + 28 m s, the phase calibration phi (measured on "
                               "DFG-2B-E), the D19B tank and its bands",
            "chosen_in_the_tank": "the bed (1:10 to h 11.5 m at x 235.25 m, 1:3 to a 6 m shelf at x 251.75 m) - placed at DFG-2B-E's measured converged x; "
                                  "the exit sponge and the stage A window end (infrastructure)",
            "computed_by_FLIP": "propagation, dispersion, refraction, shoaling, reflection at the face, focusing, the crest's growth, breaking, any jet / plume / bore",
            "input_energy": "equal SPECTRAL energy with DM1A (sum a^2 1.336153 m^2); in the tank the incoming linear waves carry less: inlet-band variance "
                            "0.128 x, interior power 0.234 x DM1A's [computed] (= DFG-2B-E's)",
            "changes_vs_DFGB2E": "(1) bed (physics), (2) generator phase calibration (a calibration of the inlet, not a force), (3) exit sponge + stage A window "
                                 "end (infrastructure), (4) judge registrations R2: G6 window, pre-lip 'conv', co-equal 3b and 3c (rules, not physics); "
                                 "nothing else",
            "registrations_before_run": "G6 window / Hc floor, the pre-lip 'conv', 3b bar_pl with DFG-2B-E as the round-2 reference, 3c tolerance, G2f against "
                                        "the design target: all frozen here before any FLIP52B2 run",
            "not_done": "no force toward a shape, no wind or current; the target picture only through e51; nothing committed; README / Docs not edited; no "
                        "Houdini started; no file of the running DFG-S-E140 (flip52s2, flip52s, flip50 chain code, Houdini/FLIP52S2, FLIP52S2 cfgs / plans) or "
                        "of the frozen DFG-2B (flip52b, flip52, FLIP52B plan / cfgs / runs) touched; auto_DFGB3.py not started"},
        "risks": [
            "G4 is a validity coin-flip for ANY rerun of this sea on the W 140 layout: measured 0.397 vs 0.40 (side band, t_fn + 4.1 s, x 166-168, y 108: the "
            "next group's generation); the face changes it by -0.002 .. -0.006 (linear, no band damping) but the sign depends on phase and the reflected "
            "field alone reaches 0.010-0.018; P(fail) ~0.3 [computed / guess]",
            "G2f n3 amplitude: measured 0.995 vs floor 0.948; the face reflection lowers the x 110 m gauge amplitude to x 0.951 (shelf 6 m, linear steady); with "
            "reflection present ~60 % of the 49-105 s window the expected value is 0.955-0.975; P(fail) ~0.25 [computed / guess]",
            "breaking may not start right at the converged instant: B >= 0.75 0.5 s late -> BF miss ~1.75-1.85 (gain only 0.4-0.5); the BF factors come from 6 "
            "groups on 2 beds, none a plunge on a sloping 1:3 face [calibrated / guess]",
            "collapsing / jet breaker without a forward lip (lip < 0.20): Iribarren 1.0-1.3 is plunging but the 3D crest steepness (k7 Hc ~0.85) has no 2D "
            "analogue; P ~0.1-0.15 [guess]",
            "pre-emption: group 2 converged at x 238.5 m, 3 m up the face: a crest 0.2-0.4 s earlier and 0.1-0.4 m lower is possible (X2B' lesson); P(Hc lower) "
            "~0.2 [guess]",
            "the pre-lip 'conv' rule could be cut short by an earlier lip of a precursor crest of the same group on the face / shelf (t >= t_fn - 6.9 s): conv "
            "would then be an earlier, lower crest and G6 / G3P could fail; the DFG-2B 'conv' and the first 5 lips are reported per group [guess]",
            "the print ruler is not modelled: DFG-S (also 1:3) had a worse back (11.5-16.9 deg) and w07 (2.5-2.85) than DFG-2B-E; score3 could rise toward the "
            "0.9485 bar; P(print bars fail) ~0.2-0.25 [guess]",
            "bores and splash on the shelf could raise Nt (limit 0.75; DFG-2B-E 0.70): NOT_ELIGIBLE; P ~0.15 [guess]",
            "the exit sponge (abs_on 1, xa0 332 m) and the stage A window end 327 m are parameters beyond the bed (infrastructure); without the sponge bores "
            "reflected at the end wall return ~40 s later and contaminate groups 2-3",
            "pipeline: the two-slope bed path was never built in the DFG-2B scene; the build check covers it (VEX vs numpy, particles, band probe with the "
            "sponge) and it was checked in FLIP49 (PG12s); P(pipeline problem) ~0.05 [guess]",
            "DFG-S-E140 (1:3 step at matched energy, running at freeze) may revise these probabilities (G4 margin, G2f margins, 1:3 reflection); its numbers "
            "are logged by auto_DFGB3 (DFGS2_READ, report only) and do not change this plan",
            "CS1 and BF are single-design calibrations: every number past the foot is an extrapolation; the attempted measured reflection split on DFG-2B-E "
            "was ill-conditioned and is not used",
            "the run takes ~%.1f-%.1f h (9 %% more water: the shelf to x 412 m); max_hours 3.5 per chain with up to 2 resumes" % tuple(te["est_h"])],
        "metrics_ruler": {"e51": "Tools/GWWaveGen/flip51/e51_metrics.py", "e51_sha256": sha(GC.TOOLS51 + "/e51_metrics.py"),
                          "print_view": "Tools/GWWaveGen/flip53/pv53.py (sha at freeze %s)" % sha(GC.REPO + "/Tools/GWWaveGen/flip53/pv53.py")[:16]},
        "table_check": {"all_ok": tc["all_ok"], "content_sha256": tc["content_sha256"], "ok": tc["ok"],
                        "file": GC.TABLE_CHECK.replace(GC.REPO + "/", ""), "file_sha256": sha(GC.TABLE_CHECK)},
        "table_npz": {"file": tp.replace(GC.REPO + "/", ""), "file_sha256": tsha, "content_sha256": tch,
                      "design_table": GC.DFGBE_TABLE.replace(GC.REPO + "/", ""), "design_content_sha256": GC.DFGBE_TABLE_CONTENT},
        "precheck_at_freeze": {"particles_model": pre["particles_model"], "time": te, "parms_diff_vs_DFGBE": pre.get("parms_diff_vs_DFGBE"),
                               "parms_named_differences": pre.get("parms_named_differences"),
                               "checks_other_than_plan": {k: v for k, v in pre["checks"].items() if k not in ("plan_consistency", "table_is_plan_set")},
                               "note": "plan_consistency and table_is_plan_set need this frozen file; auto_DFGB3 verify runs the full precheck after the freeze"},
        "code_sha256": {("Tools/GWWaveGen/flip52b2/" + nm): sha(os.path.join(HERE, nm)) for nm in GC.CODE_FILES},
        "inputs_sha256": {p: sha(GC.REPO + "/" + p) for p in INPUTS if os.path.exists(GC.REPO + "/" + p)},
        "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "frozen_before_any_FLIP52B2_run": not run_exists()}
    return plan


def verify():
    out = dict(plan=GC.PLAN_REL, plan_sha_ok=GC.plan_sha_ok())
    pl = GC.plan()
    cs = pl.get("code_sha256") or {}
    out["code_changed"] = [k for k, v in cs.items() if not os.path.exists(GC.REPO + "/" + k) or sha(GC.REPO + "/" + k) != v]
    out["auto_sha_ok"] = bool((pl.get("automation") or {}).get("sha256") == sha(AUTO))
    out["table_ok"] = bool(sha(GC.REPO + "/" + pl["table_npz"]["file"]) == pl["table_npz"]["file_sha256"])
    out["ok"] = bool(out["plan_sha_ok"] and not out["code_changed"] and out["auto_sha_ok"] and out["table_ok"])
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if not a or a[0] not in ("draft", "freeze", "verify"):
        print(__doc__); sys.exit(1)
    if a[0] == "verify":
        print(json.dumps(verify(), ensure_ascii=False)); return
    if run_exists():
        raise SystemExit("a FLIP52B2 run folder exists (%s): the plan is not (re)frozen; register an amendment instead" % run_exists())
    pl = build_plan()
    if a[0] == "draft":
        print(json.dumps(GC.clean(pl), ensure_ascii=False, indent=1)); return
    os.makedirs(GC.PLAN_DIR, exist_ok=True)
    with open(GC.PLAN, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(GC.clean(pl), fh, ensure_ascii=False, indent=1)
    h = sha(GC.PLAN)
    with open(GC.PLAN + ".sha256", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("%s  plan_DFGB3_frozen.json\n" % h)
    print(json.dumps(dict(written=GC.PLAN, sha256=h, frozen_at=pl["frozen_at"], table=pl["table_npz"], code=len(pl["code_sha256"]),
                          automation_sha256=pl["automation"]["sha256"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
