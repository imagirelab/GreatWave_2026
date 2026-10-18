# -*- coding: utf-8 -*-
"""FLIP52B3 plan DFGB4 = DFG-2B-V (DFG-2B round 3, a validation rerun of DFG-2B-E): write and FREEZE
Unity/Build/FLIP52B3/plan/plan_DFGB4_frozen.json (+ .sha256) BEFORE any FLIP52B3 run (py -3.10 -B; numpy). 2026-10-18 written new (Claude) by
adapting flip52b2/g52b2_plan.py (DFGB3, frozen, not edited). Reads (read only): DFG-2B-E's and DFGB3's results (judge, co-equal, pv53 json,
cfg, table, G1), the FLIP52B frozen plan and amendments, DM1A's cfg and table, the round-3 design-step screens (Unity/Build/FLIP52B3/diag/*.json,
_scratch/g4map.npz), the flip52b3 code and the automation script. Writes: the DFGB4 generator table (Unity/Build/FLIP52B3/tables/), its G1
check (plan/table_check_DFGB4.json) and the frozen plan + .sha256. It refuses to (re)freeze once a FLIP52B3 run folder exists.
usage: py -3.10 -B g52b3_plan.py draft     print the plan (nothing written except the table npz and its G1 check)
       py -3.10 -B g52b3_plan.py freeze    write plan_DFGB4_frozen.json + .sha256 (no FLIP52B3 run may exist)
       py -3.10 -B g52b3_plan.py verify    plan sha, code sha as frozen, automation sha (json to stdout; reads only)
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, time, hashlib, math

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52b3_common as GC            # noqa: E402
import g52b3_table as TB             # noqa: E402
import g52b3_mkcopy as MK            # noqa: E402

AUTO = "G:/research/Wave Simulation/_tools/auto_DFGB4.py"
INPUTS = ["Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json",
          "Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/coequal_DFGB.json",
          "Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json",
          "Unity/Build/FLIP52B/runs/ready/DFGB2E_D19B_xf272p25_dp0p5.json",
          "Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz",
          "Unity/Build/FLIP52B/plan/table_check_DFGBE.json",
          "Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json",
          "Unity/Build/FLIP52B/plan/amendments.jsonl",
          "Unity/Build/FLIP52B/_logs/build_check52b.json",
          "Houdini/FLIP52B/g52b_tank.hiplc",
          "Unity/Build/FLIP52B2/plan/plan_DFGB3_frozen.json",
          "Unity/Build/FLIP52B2/runs/DFGB3_D19Bs3h6_xf272p25_dp0p5/g52b2/judge_DFGB3.json",
          "Unity/Build/FLIP52B2/runs/DFGB3_D19Bs3h6_xf272p25_dp0p5/g52b2/coequal_DFGB3.json",
          "Unity/Build/FLIP53/pv53/DFGB3_D19Bs3h6_xf272p25_dp0p5/pv53_DFGB3_D19Bs3h6_xf272p25_dp0p5.json",
          "Unity/Build/FLIP52S2/plan/plan_DFGS2_frozen.json",
          "Unity/Build/FLIP52S2/runs/DFGS2E_step3h6_xf145_W140_dp0p5/g52s2/judge_DFGS2.json",
          "Unity/Build/FLIP50/tables/D_DM1_T12_W140_c5c22196af32.npz",
          "Unity/Build/FLIP50/runs/ready/DM1A_D19B_T12_th80_dp0p5.json",
          "Unity/Build/FLIP52B2/diag/cs1_model.json",
          "Unity/Build/FLIP52B2/diag/screen2_bfmodel.json",
          "Unity/Build/FLIP52B3/diag/cs1band.json",
          "Unity/Build/FLIP52B3/diag/cs1band_scan.json",
          "Unity/Build/FLIP52B3/diag/cs1band_scan2.json",
          "Unity/Build/FLIP52B3/diag/cs1_with_measured_Q.json",
          "Unity/Build/FLIP52B3/diag/g4map.json",
          "Unity/Build/FLIP52B3/diag/g4_3runs.json",
          "Unity/Build/FLIP52B3/diag/harm_B3_vs_B2E.json",
          "Unity/Build/FLIP52B3/diag/track3_B2E.json",
          "Unity/Build/FLIP52B3/diag/track3_B3.json",
          "Unity/Build/FLIP52B3/diag/track3_S2E.json",
          "Unity/Build/FLIP52B3/diag/trough_toe_3runs.json",
          "Unity/Build/FLIP52B3/_scratch/g4map.npz",
          "Tools/GWWaveGen/flip52b3/b3_common.py",
          "Tools/GWWaveGen/flip52b3/b3_cs1band.py",
          "Tools/GWWaveGen/flip52b3/b3_g4.py",
          "Tools/GWWaveGen/flip52b3/b3_g4map.py",
          "Tools/GWWaveGen/flip52b3/b3_harm.py",
          "Tools/GWWaveGen/flip52b3/b3_track3.py",
          "Tools/GWWaveGen/flip53/pv53.py",
          "Tools/GWWaveGen/flip51/e51_metrics.py",
          "Tools/GWWaveGen/flip52b/g52b_ana.py",
          "Tools/GWWaveGen/flip52b/g52b_video.py"]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run_exists():
    return [p for p in (GC.RUNS_ROOT + "/" + GC.RID["main"],) if os.path.exists(p)]


def _cs1_row(scale5):
    """the design step's CS1 band scan row for s = (0, 0, scale5) (Unity/Build/FLIP52B3/diag/cs1band_scan2.json) [calibrated]."""
    try:
        for r in GC.jload(GC.DIAG_DIR + "/cs1band_scan2.json"):
            if [float(v) for v in r["s"]] == [0.0, 0.0, float(scale5)]:
                return r
    except Exception:
        return None
    return None


def build_plan():
    import g52b3_pcfg as PC
    import g52b3_ana as GA
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
        raise SystemExit("generated copies differ from g52b3_mkcopy output: %s" % badc)
    if not os.path.exists(AUTO):
        raise SystemExit("the automation script %s is missing (write it before freezing: its sha256 is frozen here)" % AUTO)
    E = TB.energy_in_tank()
    c = PC.make("main")
    pre = c["precheck"]
    te = pre["time"]
    PV = GC.jload(GC.DFGBE_PV53)
    pl_vals = [p["conv_print"]["miss"] for p in PV["periods"]]
    pl_hc = [p["conv_print"]["Hc"] for p in PV["periods"]]
    refs = GA.pl_refs()
    best, rows = GA.best_valid()
    cs1 = _cs1_row(GC.CAL_SCALE5) or {}
    g4s = tc["g4_screen"]
    E4 = E["DFGB4"]; EE = E["DFGB_E"]
    cont = tc["continuity"]["per_layer"]
    seam5 = [r for r in cont if r["n"] == 5][0]
    import x52b3_build as XB
    src = XB.source_ok()
    plan = {
        "status": "FROZEN",
        "plan": "DFGB4",
        "name": GC.NAME,
        "campaign": "FLIP52B3-DFGB4 (DFG-2B round 3: DFG-2B-V, a validation rerun of DFG-2B-E)",
        "tags_legend": {"[measured]": "【測定】", "[computed]": "【計算】", "[literature]": "【文献】", "[guess]": "【推測】", "[chosen]": "【選び】",
                        "[calibrated]": "【計算】 (a screen number scaled by a measured FLIP / screen ratio)"},
        "title": ("FLIP52B3 plan DFGB4 = DFG-2B-V: DFG-2B-E bit for bit (energy-matched DFG-2 group sea P 28 s, T 9.33 / 7 / 5.6 s, the 34 X2 "
                  "directions, spectral energy = DM1A; the D19B 1:10 beach; x_f 272.25 m, t_f 63 s; W 140, bands, solver, judged records) with two "
                  "generator-table differences - an INLET-ONLY n5 phase calibration (0.6 x the measured G2f n5 phase = 0.3084 rad) and a 3 % SIDE-BAND "
                  "amplitude taper at the G4 hot spot - and the judge registrations (R2 G6 window, pre-lip 'conv', 3b / 3c vs DFG-2B-E, keeps the curl): "
                  "the run most likely to give a VALID DFG-2B-like hero"),
        "trigger": {
            "goal_round3": ("a VALID run with DFG-2B-E's look (forward plunging curl on the 1:10 beach, score3 ~0.75, lip ~0.3, crest ~8.4 m at "
                            "convergence): user Q85 made DFG-2B the Unity hero, but DFG-2B-E is formally INVALID (G2f n5 phase 0.514 rad > 0.35; G6 0.04 s "
                            "early in the old window) and its G4 0.397 sits at the 0.40 limit; DFGB3 (1:3 face to a 6 m shelf) fixed G2f / G6 but lost the "
                            "curl (lip 0-0.20, score3 1.56-1.77) and failed G4 (0.419)"),
            "user_rules": {"Q83": "progress = convergence AND print match (co-equal)",
                           "Q84": "incoming sea at equal total (spectral) wave energy to DM1A (sum a^2 = 1.336153 m^2 at the generation depth); every report "
                                  "states it incl. the in-tank power ratio",
                           "Q85": "the user judged DFG-2B's look the best (\"DFG-2B 的效果更好\"): keep the forward curl; a variant that loses the curl is a "
                                  "failure even if it converges",
                           "Q81_Q82": "decide self-checkable things yourself; work never stops"},
            "parent": "DFG-2B-E = Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5 (plan_DFGB_frozen.json + AM-DFGB1/1a/1b/2), the Unity hero (Q85), "
                      "formally INVALID",
            "honest_expectation": ("NOT progress by the frozen co-equal rule: miss at the curl ~2.25 against the 1.77 bar (P(progress) 0.02 [guess]); "
                                   "the aim is a VALID DFG-2B-like hero candidate (P(valid) ~0.6, P(valid and keeps the curl) ~0.5 [guess])")},
        "physics_rules": {
            "forces": "gravity, the bed and the incoming waves only; no force toward a shape; no wind, no current (the return current only cancels the "
                      "target's own mean mass flux)",
            "Q84": "the incoming sea has the same SPECTRAL energy as DM1A (sum a^2 = 1.336153 m^2 at h0 19 m) = DFG-2B-E's (AM-DFGB1); the n5 phase "
                   "calibration has |factor| 1; the 3 %% taper lowers the generator target only in the side band y 95-125 m, x >= 140 m (full from "
                   "x 160 m through the generating band to x 180.25 m and on its fade-out to x 210.25 m) (not the spectrum) and so lowers the in-tank interior power by x %.4f [computed]" % E["DFGB4_vs_DFGB_E"]["interior_power_ratio"],
            "calibration_not_a_force": "the inlet-only phase factor only advances the n5 (T 5.6 s) layer of the inlet-band TARGET by 0.2749 s so that the "
                                       "realised wave at the G2f gauges matches the design; it acts only at x <= 100 m (the generation band), never on the crest",
            "taper_not_a_force": "the side-band taper lowers the generator target amplitude by <= 3 % in the side band at y 95-125 m, x >= 140 m (full "
                                 "from x 160 m through the generating band to x 180.25 m and on its fade-out to x 210.25 m; the G4 hot spot is at "
                                 "(168.5, 108.5)); it acts only inside the generating side band (y >= 95 m), never on the crest",
            "Q54_honesty": "chosen at the inlet: P, the three frequencies and equal weights, the 34 X2 directions and weights, the energy-matched a_sum, "
                           "the design phase reference (272.25, 0) at t = 63 + 28 m s, the D19B tank and bands (all = DFG-2B-E); calibrated: the n5 inlet "
                           "phase 0.3084 rad, the 3 % taper; computed by FLIP: propagation, dispersion, refraction, shoaling, focusing, the crest's growth, "
                           "breaking, any jet / plume / bore"},
        "sea": {
            "P_s": GC.P_S, "harmonics_n": list(GC.HARMONICS), "T_s": [round(GC.P_S / n, 6) for n in GC.HARMONICS],
            "freq_weights": [round(float(v), 6) for v in C["wf"]], "directions_deg": [round(float(v), 6) for v in C["th"]],
            "dir_weights": [round(float(v), 6) for v in C["wd"]], "dspec": list(GC.DSPEC), "n_components": int(C["a"].size),
            "a_sum_m": round(float(C["a_sum"]), 6), "a_max_component_m": round(float(C["a"].max()), 6),
            "amp_per_freq_m": [round(float(C["a_sum"] * v), 6) for v in C["wf"]], "generation_depth_m": GC.H0, "ramp_s": GC.RAMP_S,
            "same_as_DFGB2E": "frequencies, P, weights, the 34 directions, a_sum (AM-DFGB1 x 1.680585), the design phase reference and t_f bit for bit; the "
                              "DESIGN table equals DFG-2B-E's table float32 field by field (G1 'design_equals_DFGB_E')",
            "focus": {"x_m": GC.X_F, "y_m": 0.0, "t_f_s": GC.T_F, "times_s": list(GC.FOCI), "h_m": round(GC.h_of(GC.X_F), 6),
                      "meaning": "the generator's phase reference (= DFG-2B-E's design focus on the 1:10 beach); DFG-2B-E converged at x 228-238 m [measured]"},
            "energy": {
                "basis": "equal spectral energy (Q84): the energy density 0.5 rho g sum a^2 of the incoming components at the generation depth h0 19 m "
                         "(= DM1A's generation depth), as in an open sea of unbounded width",
                "statement": GC.sea_text(), "sum_a2_m2": round(E["spectral"]["sum_a2_m2"], 6), "DM1A_sum_a2_m2": round(GC.DM1A_SUM_A2, 6),
                "ratio": round(E["spectral"]["ratio"], 9), "E_Jm2": round(E["spectral"]["E_Jm2"], 1), "Hm0_spectral_m": round(E["spectral"]["Hm0_spectral_m"], 4),
                "in_tank": dict(inlet_variance_over_DM1A=round(E4["inlet_variance_over_DM1A"], 6), interior_power_over_DM1A=round(E4["interior_power_over_DM1A"], 6),
                                power_into_interior_MW=round(E4["power_into_interior_MW"], 4), DM1A_power_into_interior_MW=round(E["DM1A"]["power_into_interior_MW"], 4),
                                inlet_Hm0_equiv_m=round(E4["inlet_band_Hm0_equiv_m"], 4), DM1A_inlet_Hm0_equiv_m=round(E["DM1A"]["inlet_band_Hm0_equiv_m"], 4),
                                DFGB_E_interior_power_over_DM1A=round(EE["interior_power_over_DM1A"], 6),
                                interior_power_vs_DFGB_E=round(E["DFGB4_vs_DFGB_E"]["interior_power_ratio"], 6),
                                side_edge_power_vs_DFGB_E=round(E["DFGB4_vs_DFGB_E"]["side_edge_power_ratio"], 6),
                                reproduces_AM_DFGB1b=E["reproduces_AM_DFGB1b"]["ok"],
                                tag="[computed] g52b3_table.energy_in_tank: numpy on the linear input tables (the AM-DFGB1b rule on the D19B layout)",
                                design_guess_was="0.231-0.234 x DM1A [guess, design]; computed 0.228 (the taper removes 3.2 % of the power through the side "
                                                 "edge y 95 m, which carries most of the interior power)"),
                "statement_in_tank": E["statement_en"],
                "report_rule": "every judge, co-equal verdict and status line states 'equal spectral energy (Q84)' AND the in-tank ratios (inlet variance "
                               "%.3f x, interior power %.3f x DM1A's; DFG-2B-E 0.234 x)" % (E4["inlet_variance_over_DM1A"], E4["interior_power_over_DM1A"])}},
        "calibration": {
            "what": "named difference 1: an INLET-ONLY calibration of table layer n5 (T 5.6 s): er5/ei5, ur5/ui5, vr5/vi5 x exp(-i PHI5 b(x)); n3, n4 "
                    "untouched; kk, hh unchanged; mx, my unchanged by the phase (a per-layer period mean)",
            "n": GC.CAL_N, "phi5_rad": round(GC.PHI5, 7), "phi5_measured_rad": GC.PHI5_MEAS, "scale": GC.CAL_SCALE5,
            "time_advance_s": round(GC.PHI5 / (2 * math.pi * GC.CAL_N / GC.P_S), 4), "x_full_m": GC.CAL_X_FULL, "x_zero_m": GC.CAL_X_ZERO,
            "b_of_x": "b(x) = 1 - smooth01((x - 80)/20): 1 for x <= 80 m (all y), 0 for x >= 100 m",
            "rule": GC.CAL_RULE,
            "source": "Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5/g52b/judge_DFGB.json G2f per_n n5 phase_err_rad 0.513994 [measured]",
            "why_0p6": ("CS1 band scan (diag/cs1band_scan2.json, s = (0, 0, 0.6)) [calibrated]: G2f phases %s rad, R %s, conv Hc %s m at x %s m, t_fn %s s; "
                        "s5 = 1.0 leaves the n5 R margin 0.002 (CS1 lowers R as the phase is advanced), 0.5-0.75 keep the margins; 0.6 = the design's pick"
                        % (cs1.get("ph_corr"), cs1.get("R_corr"), cs1.get("Hc"), cs1.get("x"), cs1.get("t"))),
            "why_inlet_only": "DFGB3's whole-table factor (all three layers, inlet AND side band) fixed G2f / G6 but pushed the side band, already on time "
                              "(the realised side band at the G4 hot spot lagged its target by only n3 -0.17, n4 -0.01, n5 -0.05 rad [calibrated, diag/"
                              "cs1band.json]), off the design: G4 0.419 [measured]; the per-cell G4 screen puts 0.412 on that table and 0.406 on half of it "
                              "[calibrated, diag/g4map.json]",
            "why_this_seam": ("the factor is a function of x only: the WHOLE inlet band (x <= 80 m, all y, incl. the corner y 95-140 m where the inlet and "
                              "the side band relax toward the same target; the inlet weight dominates there for x < ~50 m and y < ~117 m) is advanced, blended over the "
                              "band's last 20 m (x 80-100 m: inlet relaxation weight <= 0.002; smooth01 over 20 m = the shape and length of the inlet band's "
                              "20 m wall taper), and the table is the design for x >= 100 m. This matches CS1's partition: its 'inlet source' = every wave "
                              "crossing x 100 m at |y| < 95 m, generated across the whole inlet band width (oblique rays from the corner included); its "
                              "'side source' = waves entering the interior across y 95 m at x > 100 m (kept at the design). The side-band target is then "
                              "continuous at the x 100 m / y >= 95 m corner [chosen]"),
            "screens": {"G2f_CS1": dict(phase_rad=cs1.get("ph_corr"), R=cs1.get("R_corr"), ph_margin=cs1.get("ph_margin"), R_margin=cs1.get("R_margin"),
                                        tag="[calibrated] CS1 with measured offsets (validated within 0.03 in R on two runs; n5 phase offset +0.19 / +0.235)"),
                        "converged_CS1": dict(Hc_m=cs1.get("Hc"), x_m=cs1.get("x"), t_rel_fn_s=cs1.get("t"), tag="[calibrated]"),
                        "seam_continuity": dict(n5_raw_max=round(seam5["generator_max_rel_flat_seam_taper"], 6),
                                                n5_weighted_added=round(seam5["seam_added_weighted_max"], 6),
                                                n5_over_frozen_tapers=round(seam5["seam_over_frozen_tapers"], 6), tag="[computed] G1")},
            "G2f_reference": "the DESIGN target (= DFG-2B-E's table at the gauges, cfg dir.linear_refs.G2f_gauges); at x 110 m the generator equals the "
                             "design (b(110) = 0, g(110, y) = 1)",
            "dropped": "DFGB3's whole-table phase factor (n3 -0.061, n4 +0.279, n5 +0.514 rad on all bands)",
            "tag": "[calibrated]"},
        "taper": {
            "what": "named difference 2: every table layer x g(x, y) (amplitude only); mx, my x g^2; kk, hh unchanged",
            "d": GC.TAPER_D, "x": list(GC.TAPER_X), "y": list(GC.TAPER_Y), "y_in": list(GC.TAPER_YIN), "rule": GC.TAPER_RULE,
            "g_at_hot_spot_168p5_108p5": round(float(GC.gain(168.5, 108.5)), 6),
            "why": "G4 is the binding gate: DFG-2B-E measured 0.397 (side band, x 166-168, y 108, t_fn + 4.1 s: the next group's generation) vs the 0.40 "
                   "limit; the per-cell G4 screen (r = FLIP / linear per side-band cell, measured on DFG-2B-E) puts 0.387 on this table [calibrated]",
            "screens": {"G4_side_exact_table": dict(value=round(g4s.get("predicted_G4_side", float("nan")), 6), at=g4s.get("at"),
                                                    linear_max=round(g4s.get("linear_max", float("nan")), 6), tag="[calibrated] g52b3_table.g4_screen"),
                        "G4_side_g4map_candidate": (g4s.get("g4map_candidate_taper3") or {}),
                        "G4_5pc_fallback": "0.381 [calibrated, diag/g4map.json 'design + taper 5 %']",
                        "screen_residual": "DFGB3: screen 0.412 vs measured 0.419 (+0.007); so 0.387 means up to ~0.394 [calibrated]"},
            "cost_on_crest": ("the taper removes %.1f %% of the power through the side edge y 95 m (x 100-180 m) and %.1f %% of the interior power [computed]; "
                              "Hc at convergence -0.03 .. -0.08 m [guess]; hard upper bound 3 %% (~0.25 m) if the whole crest came through the tapered "
                              "segment [computed]" % (100 * (1 - E["DFGB4_vs_DFGB_E"]["side_edge_power_ratio"]),
                                                       100 * (1 - E["DFGB4_vs_DFGB_E"]["interior_power_ratio"]))),
            "tag": "[calibrated]"},
        "tank": {
            "kind": "half tank, symmetry plane y = 0, the D19B tank of DFG-2B-E unchanged",
            "h0_m": GC.H0, "Lx_m": GC.LX, "W_m": GC.W_MAIN, "z_bed_m": GC.ZB, "z_top_m": GC.Z_TOP,
            "bed": {"spec": "g50_common.SPEC_D19B", "x_toe_m": GC.X_TOE, "slope_1_in": GC.SLOPE_S, "x_shore_m": GC.X_SHORE,
                    "formula": GC.bed_formula(GC.SPEC_BED), "selfcheck": bs, "same_as_DFGB2E": True, "tag": "[chosen] = DFG-2B-E"},
            "solver": {"dp": [0.5], "gridscale": 2.0, "cfl": 1.0, "pcfl": 0.75, "minsub": 1, "maxsub": 8, "veltransfer": "flip"},
            "bands": {"inlet": {"x_m": [0.0, 100.0], "xg_end": GC.IN_X1, "wall_taper_m": GC.WALL_TAPER, "relax_g": 1.0, "in_gain": 1.0},
                      "side": {"y_m": [GC.SD0, GC.W_MAIN], "sd0": GC.SD0, "sd_gen": GC.SD_GEN, "sd_sw": GC.SD_SW, "sd_sigma": GC.SD_SIGMA, "sd_pow": GC.SD_POW,
                               "sd_taper_m": GC.SD_TAPER, "sd_gain": 1.0},
                      "exit_sponge": {"abs_on": 0, "why": "none (= DFG-2B-E: the 1:10 beach absorbs)"},
                      "ret_on": 1, "dir_on": 1, "volume": {"stage": "A", "vol_x_m": list(GC.VOL_X)}},
            "parms_differ_from_DFGB2E": dict(PC.PARMS_DIFFER_FROM_DFGBE),
            "named_differences": "none in the cfg parms (g52b3_pcfg precheck 'parms_equal_DFGBE', 'blocks_equal_DFGBE'); the generator TABLE differs by the "
                                 "two registered maps (calibration, taper)",
            "scene": {"hip": GC.HIP_REL, "kind": "a BYTE COPY of DFG-2B-E's scene (x52b3_build.py; no hython build)", "source": "Houdini/FLIP52B/g52b_tank.hiplc",
                      "source_sha256": GC.HIP_SRC_SHA256, "source_check": {k: src[k] for k in ("source_sha_as_registered", "source_build_check_ok",
                                                                                                 "dfgbe_launches_used_source", "ok")},
                      "why": "the bed and box are DFG-2B-E's, so the validated scene is reused bit for bit; a separate file keeps the hero's files untouched"},
            "sea_into_tank": "N-layer table (g52b3_table: DFG-2B-E's WKB DirField per harmonic over D19B x the DFGB4 maps, 1 m, x 0-214 m, y 0-140 m) read "
                             "by the unchanged N-layer VEX of flip52/g52_tanklib.py",
            "interior": {"scan_x_m": list(GC.SCAN_X), "y_abs_max_m": GC.INTERIOR_Y, "N1_x_m": list(GC.INTERIOR_X), "Nt_x_m": [150.0, 275.0]}},
        "records": {
            "hf": "top-surface height field (1 m) every frame", "r2": "centre section y 0.5 m every frame (print ruler, lips)",
            "r3": "section y 77 m every frame (report)", "r4": "per-y sections x 190-335 m, y 0-95 m, every 3rd frame in the group windows",
            "r5": "surface meshes every 3rd frame in the group windows (Unity print view, mp4)",
            "gauges": "x 110 / 128 / 160 m, y 0.5 / 20 / 40 / 60 / 80 m (G2f at x 110 m)",
            "checkpoints": "every 48 frames (resume after the 1740 s launch limit)", "group_window_s": list(GC.GROUP_WIN), "t_end_s": PC.T_END[0.5],
            "windows_main_s": c["records"]["windows"],
            "layout_choice": "the judged layout of DFG-2B-E (r4 / r5 every 3rd frame) so the run is directly comparable and the verdict comes ~1.35 h "
                             "earlier; if valid and kept, its every-frame re-record from checkpoint 1152 (+2.94 h) is a separate step after the user's yes",
            "no_1m_smoke": "no 1.0 m smoke: the code path, the scene (byte copy), the sea and the records are DFG-2B-E's (which ran)"},
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
                "criterion_4": "KEEPS THE CURL (Q85): median best lip >= 0.20 AND median best score3 <= 0.9485 AND >= 2 of 3 groups with best lip >= 0.20",
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
                                       "why_DFGB2E_counts": "the goal is defined against DFG-2B-E (the hero), although it is INVALID by its own plan; the "
                                                            "valid-runs rule applies on top (= DFGB3's rule, unchanged)",
                                       "same_instant_report": "SAME_INSTANT_NEW_BEST if the print-like median miss <= the convergence bar",
                                       "clearly_better_report": "PL_CLEARLY_BETTER_THAN_DFGB2E if the print-like median miss <= 1.77"},
                "hc_not_lower": {"tol_m": GA.COEQ_HC["tol_m"], "DFGB2E_conv_Hc_median": GA.COEQ_HC["DFGB2E_conv_Hc_median"],
                                 "DFGB2E_pl_Hc_median": GA.COEQ_HC["DFGB2E_pl_Hc_median"], "DFGB2E_conv_Hc": GA.COEQ_HC["DFGB2E_conv_Hc"],
                                 "DFGB2E_pl_Hc_read_at_freeze": [round(v, 6) for v in pl_hc], "rule": GA.COEQ_HC["rule"]},
                "keeps_curl": {"lip_min": GA.COEQ_CURL["lip_min"], "score3_max": GA.COEQ_CURL["score3_max"], "min_groups_lip": GA.COEQ_CURL["min_groups_lip"],
                               "DFGB2E_report": GA.COEQ_CURL["DFGB2E_report"], "rule": GA.COEQ_CURL["rule"],
                               "DFGB2E_reads": "keeps the curl (3 of 3 groups lip >= 0.20, median score3 0.752, lip 0.31) [measured, the DFGB4 coequal on "
                                               "DFG-2B-E's records]"},
                "progress_rule": ("PROGRESS iff ALL of: (1) the Unity print view rendered at the most print-like instant (pv53); (2) the print match ok "
                                  "(median best-instant score3 <= 0.9485 = DM1A 0.6485 + 0.30, median best-instant lip >= 0.20); (3a) the convergence "
                                  "decision at the judge's 'max' instants NEW_BEST_SHAPE or TARGET_BAND (valid run); (3b) the median pv53 conv_print miss "
                                  "<= bar_pl = min(2.8, DFG-2B-E's 2.27 - 0.5 = 1.77, best valid earlier print-like median - 0.5); (3c) Hc not lower "
                                  "(median conv Hc >= 8.19 m, median print-like Hc >= 6.63 m); (4) keeps the curl. 'converged, print match worse than "
                                  "DM1A', 'converged and print-like at different instants', 'lower crest' and 'lost the curl' are NOT progress. Reported: "
                                  "PL_CLEARLY_BETTER_THAN_DFGB2E, SAME_INSTANT_NEW_BEST, PRINT_BETTER_THAN_DM1A"),
                "hero_rule": GA.HERO["rule"],
                "no_print_view_no_progress": "a run without the print-view package or without its Unity render is INCOMPLETE, never progress",
                "energy_report": "every verdict carries the Q84 energy statement (equal spectral energy; in-tank inlet variance and interior power ratios)"},
            "groups": {"window_s": list(GC.GROUP_WIN), "scan_x": list(GC.SCAN_X), "onset_x": [200.0, 335.0], "Nt_x": [150.0, 275.0],
                       "conv": "R2 (= DFGB3, unchanged): the largest Hc over x 150-300 m, |y| <= 95 m in [t_fn - 8, min(t_fn + 2, t_lip1)) s, t_lip1 = the "
                               "first r2 lip (AM-DFG1 test, x 200-335 m) at t >= t_fn - 6.9 s; no such lip -> [t_fn - 8, t_fn + 2] (= DFG-2B); the DFG-2B "
                               "'conv' is reported beside it",
                       "conv_lip_from_rel_s": GA.GROUP["conv_lip_from_rel"],
                       "conv_on_DFGB2E": "with this rule DFG-2B-E reads conv median Hc 8.37 m at x 235.5 m, t_fn - 3.63 s, miss 0.04 (as before) [measured, "
                                         "the DFGB4 judge on DFG-2B-E's records]",
                       "onset": "first r2 lip (AM-DFG1 test) at x 200-335 m in the window (= DFG-2B)",
                       "max_instant": "plan E D rule (= DFG-2B): onset -> e51 max in [on - 3, on + 1.5] s, x [on_x - 60, on_x + 35] m; else conv",
                       "Nt_rule": "= DFG-2B: largest Hc in x 150-275 m in [t_fn - 14, t_fn + 14) at |t - t_conv| >= 3.5 s / Hc(conv)",
                       "c_in": "largest crest on x 110 m, |y| <= 95 m in [t_fn - 14, t_fn + 14)",
                       "plunge_at_converged": "r2 onset within [t_conv - 1, t_conv + 4] s and x_on <= x_conv + 30 m",
                       "reported": "dt_conv_to_lip1 = t_lip1 - t_conv (DFG-2B-E 2.08 s median [measured]); the depth at the onset"},
            "A_validity": {
                "G1": {"rule": "numpy table check table_check_DFGB4.json all_ok (the design = DFG-2B-E's table float32 field by field; the generator = design "
                               "x F_n g exactly with the registered maps; focus vs independent WKB sums; symmetry; CONTINUITY (registered for DFGB4): design "
                               "flat < 5e-3, generator flat < 5e-3 where the maps are constant, in the seam / taper strips raw <= 0.10 and the seam's added "
                               "residual weighted by the band weight x target factor <= 0.10 x the frozen wall / side-wall tapers' weighted residual; "
                               "interpolation < 2 %; vertical profile < 1e-4; zero mass flux per layer and in total < 1e-6 (mx, my x g^2); P-periodicity; "
                               "energy = DM1A) + build_check52b3 all_ok (the byte copy of DFG-2B-E's validated scene) with the hip the launches used + cfg "
                               "precheck ok",
                       "continuity_at_freeze": [{k: r[k] for k in ("n", "design_max_rel_flat", "generator_max_rel_flat_const_maps",
                                                                     "generator_max_rel_flat_seam_taper", "seam_added_weighted_max", "frozen_tapers_weighted_max",
                                                                     "seam_over_frozen_tapers", "generator_seam_max_at_xy")} for r in cont],
                       "why_continuity_restated": "a band-specific calibration in one table cannot be an exact linear solution where its factor varies; "
                                                  "the seam must not drive spurious waves: its added residual is bounded against what the frozen D19B "
                                                  "band tapers already accept (8 % of it for n5 at freeze) [computed]"},
                "G2f": {"rule": GA.G2F_RULE, "x": 110.0, "y": list(GC.GAUGE_Y), "window_main_s": list(GA.GATES["G2f_t_main"]),
                        "floor_0p5": GA.GATES["G2f_floor_0p5"], "margin_0p5": GA.GATES["G2f_margin_0p5"], "hi_0p5": GA.GATES["G2f_hi_0p5"],
                        "phase_0p5": GA.GATES["G2f_phase_0p5"], "reference_ranges": "DFG-2 0.5 m measured R (n3 1.048, n4 0.973, n5 0.788) - 0.10, floor 0.60",
                        "calibration_stated": "the comparison target is the DESIGN (= DFG-2B-E's G2f reference bit for bit); the generator carries the "
                                              "inlet-only n5 factor (1 at the gauges)",
                        "prediction": "[calibrated] CS1: R n3 0.995 / n4 0.899 / n5 0.73 (floors 0.948 / 0.873 / 0.688), phase -0.07 / +0.26..0.28 / +0.18 rad"},
                "G3P": {"P_s": GC.P_S, "tol_s": GA.GATES["G3P_tol"], "x_spread_m": GA.GATES["G3P_xspread"], "Hc_ratio": GA.GATES["G3P_Hc_ratio"], "on": "the 'conv' summits"},
                "G4": {"kA_max": GA.GATES["G4_kA"], "t0_s": GA.GATES["G4_t0"], "inlet_x_max": GA.GATES["G4_inlet_x"], "side_y_min": GA.GATES["G4_side_y"],
                       "side_x_max": GA.GATES["G4_side_x"], "lip_x_max": GA.GATES["G4_lip_x"], "rule": "= DFG-2B (unchanged)",
                       "margin_note": "DFG-2B-E measured 0.397 (side band, t_fn + 4.1 s, x 166-168, y 108) [measured]; DFGB3 0.419 [measured]; this table: "
                                      "%.3f [calibrated, per-cell screen] (up to ~0.394 with DFGB3's +0.007 screen residual)" % g4s.get("predicted_G4_side", float("nan"))},
                "G5": {"max": GA.GATES["G5_max"]},
                "G6": {"x": list(GA.GATES["G6_x"]), "y_abs_max": GA.GATES["G6_y"], "t_rel": list(GA.GATES["G6_t"]), "Hc_min": GA.GATES["G6_Hc"],
                       "registration": "a RE-REGISTRATION (R2), frozen before DFGB3 and unchanged here: the DFG-2B window (t_fn - 4 .. + 2, x 225-295, Hc "
                                       "3.0) was centred on a screen value that was wrong by 3 s [measured]; R2 = the CS1 prediction t_fn - 3.88 s +- 3 s, "
                                       "x 215-260 m, Hc >= 0.68 x 8.34 m = 5.67 m. Every report states it as a re-registration with this reason, not as a "
                                       "new finding",
                       "on_DFGB2E": "passes on DFG-2B-E's own records (groups at t_fn -4.04 / -3.42 / -3.62) [measured, DFGB4 judge test]"},
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
                                     "flags PLUNGE_AT_CONVERGED / BREAKS_LATER / NO_BREAK_IN_WINDOW (>= 2 of 3 groups)",
                         "hero_classes": "VALID_DFGB2_LIKE_HERO_CANDIDATE / LOST_CURL / INCOMPLETE_NO_PRINT_VIEW / INVALID_<class>",
                         "after": {
                             "VALID_DFGB2_LIKE_HERO_CANDIDATE": "report 'valid DFG-2B-like hero candidate, NOT progress' (unless the co-equal rule says PROGRESS) "
                                                                "with the print-view stills, the compare video and DFG-2B-E side by side; propose to the user "
                                                                "(i) replacing the invalid DFG-2B-E hero after an every-frame re-record of DFG-2B-V from its "
                                                                "checkpoint 1152 (+2.94 h; the user judges the look) and (ii) the remaining physics options "
                                                                "for convergence at the curl: a 1:7 face from x 235.25 m (P(progress) ~0.06 [guess]) or x_f "
                                                                "250.25 for a taller curl; nothing is started automatically",
                             "LOST_CURL": "a failure by Q85 even if it converges: report side by side; no follow-up without the user / main session",
                             "PROGRESS": "DFG-2B-V becomes the new reference (unexpected: P 0.02); report to the user with the print view",
                             "INVALID_physics_G4": "registered fallback (not automatic): the 5 % taper (screen 0.381, ~0.06-0.1 m more crest loss), no change "
                                                   "to the G2f or G6 rules",
                             "INVALID_pipeline_G2f": "registered fallback (not automatic): n4 is the fragile layer; next an inlet-only n4 at 0.25 (CS1 phase "
                                                     "margin 0.164, R margin 0.017) together with this n5",
                             "INVALID_other": "report the numbers; DFGB4 stops; a pipeline cause is fixed and rerun once (same setup name)"}}},
        "lessons_measured": {
            "DFGB2E": {"converged": "t 58.96 / 87.58 / 115.38 s (t_fn -4.04 / -3.42 / -3.62) at x 228.5 / 238.5 / 235.5 m, Hc 8.10 / 8.45 / 8.37 m (Hc/h "
                                    "0.73-0.76: already depth-limited), miss 0.08 / 0.00 / 0.04; medians W50 2.25, W80 1.04, W95 0.49, S2 0.25 [measured]",
                       "print_like": "+1.9-2.25 s at x 260-267 m: score3 0.557 / 0.770 / 0.752, lip 0.25-0.31, back 17-18 deg (print 31), w07 1.53-1.57 "
                                     "(print 1.32), chord 50-56 deg (print 64), Hc 6.8 m, W50 3.7, miss 2.16 / 2.27 / 2.37 [measured]",
                       "gates": "INVALID: G2f n5 phase 0.514 rad > 0.35, G6 group 1 0.042 s early in the old window; G4 side 0.397 [measured]"},
            "DFGB3": "1:3 face from the converged x 235.25 m (h 11.5) to a 6 m shelf + whole-table phase calibration: G2f / G6 passed (phases 0.03-0.05 rad), "
                     "converged miss 0.06 but Hc 7.7-7.8 m (lower); only group 1 curled a little (lip 0.20, chord 102 deg), groups 2-3 lip 0; score3 "
                     "1.56-1.77; G4 side 0.419 FAILED; NO_BREAK_IN_WINDOW: the steep face pushed the crest up without a plunge [measured]",
            "DFGS2E": "flat 20 m, 1:3 step to a 6 m shelf, W 140: converged at the print-like instant (miss 0.30-0.54) but a wall overturn (chord 115-125 deg vs "
                      "print 64), score3 1.15-1.76; G4 failed (wall 0.437, inlet 0.431) [measured]",
            "breaker_type": "front-trough water depth / eta_c: the print-like plunge at 0.74-0.82 (1:10), the wall overturn at 0.38-0.49 (1:3) [measured, "
                            "diag/trough_toe_3runs.json]",
            "structural": "on the 1:10 beach the miss at the curl is ~2.2 for structural reasons (the crest rides the depth cap and its top flattens "
                          "sideways; measured on 3 groups); a 1:3 face to a shelf keeps convergence but gives a wall overturn instead of the print-like "
                          "plunge [measured]"},
        "design": {
            "choice": "(d) with a minimal (c): DFG-2B-E unchanged + inlet-only n5 calibration + 3 % side-band taper + the R2 registrations; chosen "
                      "2026-10-18 by the round-3 design step from the measured three-run evidence and the calibrated screens (Tools/GWWaveGen/flip52b3/"
                      "b3_*.py, Unity/Build/FLIP52B3/diag/)",
            "candidates": {
                "a_seaward_focus_1to10": "x_f 250.25 + calibration: CS1 conv Hc 9.23 m at x 225.5; BF miss at the curl ~1.75-1.85 (spread +-0.25) but the "
                                         "mechanism does not depend on x_f (1.8-2.3 [guess]); the G4 hot spot unscreened; P(valid) 0.40, P(curl) 0.70, "
                                         "P(progress) 0.07 [calibrated / guess]",
                "b_face_1to7": "front-trough ratio 0.66-0.70 between the plunge (0.74-0.82) and the wall (0.38-0.49), no data there; miss at the curl "
                               "1.4-2.1; P(valid) 0.50-0.55, P(curl) 0.45, P(progress) 0.06; 1:5: P(curl) 0.2, P(progress) 0.03 [computed / guess]",
                "c_wider_tank": "full relayout: P(valid) 0.55-0.65, P(curl) 0.6, P(progress) 0.02, +10-15 % particles and a new build; the minimal form "
                                "(the 3 % taper) is folded into (d) [guess]",
                "d_pick": "P(valid) 0.60 (0.5-0.7), P(curl) 0.85, P(progress) 0.02; without the taper P(valid) 0.40 [guess]",
                "ranking_P_valid_and_curl": "(d) 0.51 > (c) 0.36 > (a) 0.28 > (b 1:7) 0.23 > (b 1:5) 0.1 [guess]"},
            "honest_verdict": "no candidate is expected to beat DFG-2B-E on the co-equal rule; the best P(progress) is ~0.06-0.07 for (a) x_f 250.25 or (b) "
                              "a 1:7 face; DFGB4 is the variant most likely to make a VALID DFG-2B-like run so that the hero can be a valid run"},
        "expected": {
            "tag": "[measured] = DFG-2B-E's own value carried over (same physics), [calibrated] = a screen, [guess] = judgement",
            "converged": "t_fn -3.4 .. -4.1 s, x 228-238 m, h 11.2-12.2 m; Hc 8.15-8.35 m (median ~8.25; CS1 8.26 with the n5 calibration [calibrated], the "
                         "taper -0.03 .. -0.08 m [guess]); miss 0.0-0.1, W50 2.2-2.5, W80 1.0-1.1, W95 0.47-0.50, S2 0.25-0.32 [measured + perturbation]; "
                         "decision NEW_BEST_SHAPE if valid (bar %.2f)" % min(GA.DEC["bar_cap"], best - GA.DEC["bar_margin"]),
            "curl": "+1.9 .. +2.25 s after convergence at x 260-267 m, h 8.4-9.0 m: score3 0.55-0.80 (median ~0.75; bar 0.9485), lip 0.25-0.31 (bar 0.20), "
                    "back 17-18 deg, w07 1.53-1.57, chord 50-56 deg, hood 0.05-0.09; Hc at the curl 6.75-6.85 m (3c floor 6.63) [measured + small perturbation]",
            "convergence_at_curl": "miss 2.1-2.4, median ~2.25: NOT better than DFG-2B-E by 0.5, so not progress [measured / guess]",
            "gates": "G1 pass (checked at freeze); G2f R 0.995 / 0.899 / 0.73, phases -0.07 / +0.26..0.28 / +0.18 rad [calibrated] (P 0.9); G4 side %.3f "
                     "(up to 0.394), inlet 0.21 [calibrated] (P 0.8-0.85); G6 with the R2 window P 0.95; G3P, G5 and run complete P 0.93 together; Nt ~0.62-0.70 "
                     "(limit 0.75)" % g4s.get("predicted_G4_side", float("nan")),
            "energy": "spectral sum a^2 1.336153 m^2 = DM1A's exactly; in-tank inlet variance %.3f x DM1A, interior power %.3f x DM1A (DFG-2B-E 0.234 x; the "
                      "taper x %.4f) [computed]" % (E4["inlet_variance_over_DM1A"], E4["interior_power_over_DM1A"], E["DFGB4_vs_DFGB_E"]["interior_power_ratio"]),
            "probabilities": {"P_valid": 0.6, "P_valid_range": [0.5, 0.7], "P_G2f": 0.9, "P_G4": [0.8, 0.85], "P_G6": 0.95, "P_rest": 0.93,
                              "P_keeps_curl": 0.85, "P_valid_and_keeps_curl": 0.5, "P_miss_curl_le_1p77": 0.03, "P_progress": 0.02,
                              "P_hc_not_lower_3c": 0.6, "tag": "[guess]"}},
        "cost": {"main": dict(te, particles_model_M=round(pre["particles_model"] / 1e6, 6), particles_ratio_vs_DFGBE=round(pre["particles_ratio_vs_DFGBE"], 6),
                              water_m3=round(pre["water_m3"], 1), measured="DFG-2B-E 2.375 h, DFGB3 2.406 h on the same code path"),
                 "max_hours": {"main": PC.MAX_H[0.5]}, "build_min": [0, 1], "analysis_min": {"judge": [1, 3], "pv53_unity": [5, 12], "video": [2, 5]},
                 "timeline": "the hero (sim, compare, export, Unity captures) ends ~13:45; DFG-2B-V sim ~2.4 h, then judge / pv53 / video ~20-30 min: verdict "
                             "~16:45 if started right after the hero [computed / guess]",
                 "note": "one 0.5 m run at a time (pagefile); auto_DFGB4 resumes a max_hours stop from the last checkpoint (up to --cap-resumes, default 2)"},
        "order": ["freeze this plan (no FLIP52B3 run exists)",
                  "auto_DFGB4.py: wait for the FINAL '<date> <time> HERO2B FINISHED' line of Unity/Build/FLIP52B/_logs/auto_hero2b_status.txt, no hython, "
                  "no other pipeline process and no Unity batch on 3 consecutive polls",
                  "HERO2B_READ (report only)", "build (x52b3_build.py: table, G1, byte copy of DFG-2B-E's scene + copy check)", "cfg main + dry chain gate",
                  "0.5 m run (resume on crash / stale; max_hours stops resumed up to 2 times)",
                  "g52b3_ana judge -> pv53 run (Unity print view) -> g52b3_ana coequal (3b, 3c, 4, hero class) -> g52b3_video"],
        "automation": {"script": AUTO, "start": "py -3.10 -B \"%s\"" % AUTO, "status": "Unity/Build/FLIP52B3/_logs/auto_DFGB4_status.txt (prefix 'DFGB4 ', "
                       "final '<date> <time> DFGB4 FINISHED ...', also on exceptions)", "sha256": sha(AUTO), "started_by_author": False,
                       "wait_rule": "starts only after the LAST line starting '<date> <time> HERO2B ' of Unity/Build/FLIP52B/_logs/auto_hero2b_status.txt "
                                    "matches exactly ^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} HERO2B FINISHED( .*)?$, no hython, no other pipeline "
                                    "process (auto_*.py other than itself, *_chain.py, *_run.py, x5*_build.py, pv53.py, h52b_*.py) and no Unity "
                                    "-batchmode process on 3 consecutive polls with the same last line; yields (launches nothing) if a restarted "
                                    "auto_hero2b.py sits in its 'WAIT DFGB3' phase on 3 polls (the hero comes first)",
                       "brake": "Unity/Build/FLIP52B3/_logs/auto_DFGB4_STOP", "simulate": "py -3.10 -B auto_DFGB4.py --simulate[=scenario.json]: no wait, "
                       "no launch, nothing written", "test_regex": "py -3.10 -B auto_DFGB4.py --test-regex"},
        "honesty": {
            "chosen_at_inlet": "P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and Gaussian weights, a_sum 10.640186 m (spectral "
                               "energy = DM1A, AM-DFGB1), the design phase reference (272.25, 0) at t = 63 + 28 m s, the D19B tank and its bands (= DFG-2B-E)",
            "calibrated": "the inlet-only n5 phase 0.3084 rad (0.6 x DFG-2B-E's measured 0.514; CS1), the 3 % side-band taper (DFG-2B-E's per-cell G4 map)",
            "computed_by_FLIP": "propagation, dispersion, refraction, shoaling, focusing, the crest's growth, breaking, any jet / plume / bore",
            "input_energy": "equal SPECTRAL energy with DM1A (sum a^2 1.336153 m^2); in the tank the incoming linear waves carry less: inlet-band variance "
                            "%.3f x, interior power %.3f x DM1A's [computed] (DFG-2B-E 0.234 x: the taper lowers it by %.1f %%)"
                            % (E4["inlet_variance_over_DM1A"], E4["interior_power_over_DM1A"], 100 * (1 - E["DFGB4_vs_DFGB_E"]["interior_power_ratio"])),
            "changes_vs_DFGB2E": "(1) the inlet-only n5 phase calibration (a calibration of the inlet, not a force), (2) the 3 % side-band taper (a "
                                 "generator-target gain in the side band, not a force), (3) judge registrations: G6 R2 window, pre-lip 'conv', co-equal 3b, "
                                 "3c and 4 (keeps the curl) (rules, not physics); nothing else (cfg parms equal; the scene a byte copy)",
            "registrations_before_run": "G6 window / Hc floor (R2, a re-registration), the pre-lip 'conv', 3b bar_pl with DFG-2B-E as the reference, 3c "
                                        "tolerance, 4 keeps the curl, the G1 continuity rule for the calibration seam, G2f against the design target: all "
                                        "frozen here before any FLIP52B3 run",
            "not_progress_expected": "this run is NOT expected to be progress by the frozen co-equal rule (miss at the curl ~2.25 vs the 1.77 bar); the "
                                     "verdict text must read 'valid DFG-2B-like hero candidate, not progress' with the structural finding (1:10: miss at the "
                                     "curl ~2.2; 1:3 face to a shelf: wall overturn)",
            "not_done": "no force toward a shape, no wind or current; the target picture only through e51; nothing committed; README / Docs not edited; no "
                        "Houdini started; no file of the running hero (flip52bh, flip52b, flip52, flip50 chain code, Houdini/FLIP52B, Unity/Build/FLIP52B "
                        "hero / runs) or of the frozen DFGB3 / DFG-S-E140 (flip52b2, flip52s2 plans / cfgs / runs) touched; auto_DFGB4.py not started"},
        "risks": [
            "G4 is still the binding gate: the 0.387 prediction scales the FLIP crest with the local target using the r-map measured on DFG-2B-E itself (hot "
            "spot (168.5, 108.5), band weight ~0.008, gain 0.975); 13 m inside the band the relaxation is partial and FLIP may follow a lower target by less than "
            "2.5 %; the inlet n5 advance also changes the inlet waves reaching the hot spot (not modelled); DFGB3's +0.007 screen residual bounds it only "
            "roughly: plausible 0.385-0.395, P(fail) ~0.15-0.2 [guess]; 3 % registered before the run, no mid-run change",
            "REVIEW 2026-10-18 (physics/honesty review, before the run): the 0.387 screen is optimistic. The r-map was validated only on DFGB3's "
            "spatially UNIFORM phase change; the taper is non-uniform in y. At the hot spot (y 108.5) the side-band relaxation is weak (relaxw 0.0087 "
            "per 1/24 s, time constant ~4.8 s), and the crest there is set by waves from the deeper band (y 115-135, taper <= 1.5 %, none above "
            "y 125) and by inlet-born waves (no taper). A ray-relaxation estimate puts the REALISED taper at the hot spot at 0.5-1.6 % (not 2.5 %) "
            "[computed, simple model]. A harmonic synthesis of DFG-2B-E's measured hot-spot harmonics (it reproduces DFGB3's measured rise, ratio "
            "1.060 vs 1.055) puts the inlet n5 advance at +0.001 to +0.0025 [computed]. Together: G4 side ~0.392-0.398 (central ~0.395), i.e. about "
            "DFG-2B-E's own 0.397 (which passed); P(G4 pass) ~0.7-0.8, P(valid) ~0.5-0.55, P(valid and keeps the curl) ~0.45 [guess]. The same "
            "argument makes the taper's cost on the crest and on the interior power smaller than the target-based numbers (0.228 x DM1A is the "
            "generator-target value, the AM-DFGB1b rule, as for DFG-2B-E's 0.234). The 5 % fallback (screen 0.381) would realise ~0.8-2.7 %.",
            "the calibration seam: a phase ramp of 0.308 rad over x 80-100 m (all y); the inlet weight there is <= 0.002 but the side band near the outer "
            "wall relaxes strongly toward it; G1 bounds it (n5 raw %.3f <= 0.10, weighted %.4f = %.1f %% of the frozen tapers' weighted residual) "
            "[computed]; P(problem) ~0.05 [guess]" % (seam5["generator_max_rel_flat_seam_taper"], seam5["seam_added_weighted_max"],
                                                      100 * seam5["seam_over_frozen_tapers"]),
            "the corner side band (x <= 80 m, y >= 95 m) carries the advanced n5 target (consistent with CS1's inlet source); waves generated there travel "
            "inside the side band and are re-relaxed toward the design at x >= 100 m; their residual effect on the G4 hot spot is not screened (+-0.004 "
            "[guess])",
            "G2f margins are small: n4 R 0.899 vs floor 0.873 and phase 0.279 vs 0.35 are DFG-2B-E's own values (n4 not calibrated); n5 R 0.73 vs 0.688 "
            "depends on CS1's inlet / side interference at the x 110 m gauges, validated within 0.03 on two runs; CS1's n5 phase offset was +0.19 on one "
            "validation run and +0.235 on the other [calibrated]",
            "the G6 R2 window ([t_fn - 6.9, t_fn - 0.9] s, x 215-260 m) was set after DFG-2B-E missed the old window by 0.042 s; frozen before DFGB3; "
            "DFG-2B-E passes it on its own records: every report states it as a re-registration with its reason",
            "3c 'Hc not lower' (converged floor 8.19 m) is borderline: CS1 puts -0.11 m on the n5 calibration and the taper costs -0.03 .. -0.08 m "
            "[guess]: prediction 8.15-8.3 m, P(pass) ~0.6; not a validity gate, but a crest 0.1-0.2 m lower is shown beside DFG-2B-E",
            "this run cannot be progress by the frozen co-equal rule (miss at the curl ~2.25 vs 1.77, P(progress) 0.02)",
            "the look needs the user's confirmation: the group-to-group spread on DFG-2B-E was already score3 0.56-0.77 and lip 0.25-0.31; the user judges "
            "the art (multi-view); a valid run with a slightly different curl replaces the hero only after the user says so",
            "compute and locks: one 0.5 m sim slot; the hero (sim, compare, export, Unity captures, unity.lock) comes first; pv53 needs Unity (lockwait "
            "120 min) and is serialised after the hero; if the hero runs late, everything shifts; a hero re-record of DFG-2B-V needs another 2.94 h",
            "eligibility: Nt was 0.70 (old 'conv') / 0.62 (R2 'conv') on DFG-2B-E against the 0.75 limit: low risk, NOT_ELIGIBLE does not invalidate",
            "honest alternatives NOT chosen: (b) a 1:7 continuing face from x 235.25 m (front-trough ratio 0.66-0.70, no calibration data; P(curl) ~0.45, "
            "P(progress) ~0.06) and (a) x_f 250.25 (taller curl; G4 hot spot unscreened, P(valid) ~0.4, the look changes): each after a valid hero exists "
            "and only with the user's go-ahead",
            "fallbacks (registered, not automatic): G4 fails -> the 5 % taper (screen 0.381); G2f fails -> an inlet-only n4 at 0.25 with this n5",
            "the run takes ~%.1f-%.1f h; max_hours %.1f per chain with up to 2 resumes" % (te["est_h"][0], te["est_h"][1], PC.MAX_H[0.5])],
        "metrics_ruler": {"e51": "Tools/GWWaveGen/flip51/e51_metrics.py", "e51_sha256": sha(GC.TOOLS51 + "/e51_metrics.py"),
                          "print_view": "Tools/GWWaveGen/flip53/pv53.py (sha at freeze %s)" % sha(GC.REPO + "/Tools/GWWaveGen/flip53/pv53.py")[:16]},
        "table_check": {"all_ok": tc["all_ok"], "content_sha256": tc["content_sha256"], "ok": tc["ok"],
                        "file": GC.TABLE_CHECK.replace(GC.REPO + "/", ""), "file_sha256": sha(GC.TABLE_CHECK)},
        "table_npz": {"file": tp.replace(GC.REPO + "/", ""), "file_sha256": tsha, "content_sha256": tch,
                      "design_table": GC.DFGBE_TABLE.replace(GC.REPO + "/", ""), "design_content_sha256": GC.DFGBE_TABLE_CONTENT},
        "precheck_at_freeze": {"particles_model": pre["particles_model"], "time": te, "parms_diff_vs_DFGBE": pre.get("parms_diff_vs_DFGBE"),
                               "blocks_diff_vs_DFGBE": pre.get("blocks_diff_vs_DFGBE"),
                               "checks_other_than_plan": {k: v for k, v in pre["checks"].items() if k not in ("plan_consistency", "table_is_plan_set")},
                               "note": "plan_consistency and table_is_plan_set need this frozen file; auto_DFGB4 verify runs the full precheck after the freeze"},
        "code_sha256": {("Tools/GWWaveGen/flip52b3/" + nm): sha(os.path.join(HERE, nm)) for nm in GC.CODE_FILES},
        "inputs_sha256": {p: sha(GC.REPO + "/" + p) for p in INPUTS if os.path.exists(GC.REPO + "/" + p)},
        "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "frozen_before_any_FLIP52B3_run": not run_exists()}
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
        raise SystemExit("a FLIP52B3 run folder exists (%s): the plan is not (re)frozen; register an amendment instead" % run_exists())
    pl = build_plan()
    if a[0] == "draft":
        print(json.dumps(GC.clean(pl), ensure_ascii=False, indent=1)); return
    os.makedirs(GC.PLAN_DIR, exist_ok=True)
    with open(GC.PLAN, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(GC.clean(pl), fh, ensure_ascii=False, indent=1)
    h = sha(GC.PLAN)
    with open(GC.PLAN + ".sha256", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("%s  plan_DFGB4_frozen.json\n" % h)
    print(json.dumps(dict(written=GC.PLAN, sha256=h, frozen_at=pl["frozen_at"], table=pl["table_npz"], code=len(pl["code_sha256"]),
                          automation_sha256=pl["automation"]["sha256"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
