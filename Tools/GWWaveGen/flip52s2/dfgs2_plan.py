# -*- coding: utf-8 -*-
"""FLIP52S2 plan DFG-S-E140: write and FREEZE Unity/Build/FLIP52S2/plan/plan_DFGS2_frozen.json (+ .sha256) BEFORE any FLIP52S2 run exists
(py -3.10 -B). 2026-10-18 written new (Claude) by adapting flip52s/dfgs_plan.py (DFG-S, frozen, not edited). Reads (read only): the DFG-S
results (judge, co-equal verdict, pv53 json), the design screen files copied to Unity/Build/FLIP52S2/screens/design_20261018/ (the design step
of 2026-10-18 03:2x-03:38, scratchpad scripts on flip52s/dfgs_screen.py), the G1 table check (plan/table_check_DFGS2.json), the written table npz,
the constants of g52s2_common / g52s2_ana / g52s2_pcfg (embedded so that g52s2_pcfg.plan_consistency and g52s2_ana.selftest compare them back),
the FLIP52B amendments (AM-DFGB1 sea, AM-DFGB1b caveat), flip52s/dfgs_screen.StepSea (the arrival rule on the W 140 layout, ~1 s CPU) and the
input tables for the in-tank energy (g52s2_table.energy_in_tank).
Refuses to (re)freeze if any FLIP52S2 run folder exists (pcheck/<id> or runs/<id> with records); a frozen plan is changed only by appending
amendments to Unity/Build/FLIP52S2/plan/amendments.jsonl.
usage: py -3.10 -B dfgs2_plan.py freeze [--refreeze-before-runs] | show
"""
import os, sys, json, math, time, glob

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52s2_common as GC          # noqa: E402
import g52s2_ana as AN             # noqa: E402
import g52s2_pcfg as PC            # noqa: E402
import g52s2_table as TB           # noqa: E402

DESIGN_DIR = GC.SCREEN_DIR + "/design_20261018"
DFGS_JUDGE = GC.DFGS_RUN + "/g52s/judge_DFGS.json"
DFGS_COEQ = GC.DFGS_RUN + "/g52s/coequal_DFGS.json"
DFGS_PV53 = GC.REPO + "/Unity/Build/FLIP53/pv53/DFGS_step3h6_xf145_dp0p5/pv53_DFGS_step3h6_xf145_dp0p5.json"
AUTO = "G:/research/Wave Simulation/_tools/auto_DFGS2.py"


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


def arrival_W140():
    """[computed] the DFG-S ray arrival rule (flip52s/dfgs_screen.StepSea.arrival, read only) on the W 140 layout (side band inner edge 110 m):
    t_f = ceil(t_full + 3.9 s). The rule is amplitude-free."""
    sys.path.insert(0, GC.TOOLS52S)
    import dfgs_screen as S
    sys.path.remove(GC.TOOLS52S)
    bed = S.bed_spec(GC.X_TOE, GC.SLOPE_S, GC.H_TOP)
    sea = S.StepSea(bed, GC.X_F, 0.0, "design", "gen180")
    lay = dict(S.side_lay(bed, "gen180")); lay["W"] = GC.W_MAIN; lay["sd0"] = GC.SD0
    sea.lay = lay
    arr = sea.arrival()
    sea0 = S.StepSea(bed, GC.X_F, 0.0, "design", "gen180")
    return dict(t_full_s=arr["t_full_s"], t_f_s=float(math.ceil(arr["t_full_s"] + 3.9)), aperture=arr["aperture"], n_side=arr["n_side"],
                frac_of_focal_sum_from_side_over_step=arr["frac_of_focal_sum_from_side_over_step"],
                W100_for_comparison=dict(t_full_s=sea0.arr["t_full_s"], frac_of_focal_sum_from_side_over_step=sea0.arr["frac_of_focal_sum_from_side_over_step"]),
                layout=lay, rule="ray traced back from the focus (Snell over the step) to the inlet band end x 50 m or the side band inner edge y 110 m; "
                                 "travel = sum dx / (cos th c_g); t_full = ramp 14 s + the slowest significant ray; t_f = ceil(t_full + 3.9 s) "
                                 "(the DFG-2 / DFG-S rule) [computed]")


def design_summary():
    """the design step's numbers (DFG-S follow-up, 2026-10-18 03:2x-03:38; files in screens/design_20261018) as tagged plan text; the linear
    W 140 screen re-read from its json."""
    L = GC.jload(DESIGN_DIR + "/dfgs2_A_E_W140.json")
    e51 = L["e51"]
    mx = max(e51, key=lambda q: q["Hc"])
    pred = GC.jload(DESIGN_DIR + "/dfgs2_predict.json")
    return dict(
        tag="[computed] linear WKB screen (flip52s/dfgs_screen StepSea) per candidate; [calibrated] FLIP / linear ratios measured on DFG-S (3 groups) "
            "against the S7 linear screen at matched t_rel; [guess] where marked",
        chosen="(a) DFG-S-E140: energy-matched amplitudes (x 1.680585) + W 140 (side band 110-140 m) + t_f by the arrival rule; DFG-S otherwise unchanged",
        why=["in the calibrated screen it is the only candidate where convergence at the curl clearly improves",
             "it closes most of the height gap at equal energy (Q84)",
             "(b) moving the focus / edge and (c) bed changes give no convergence gain at the curl in the model: the linear crest persists on the 6 m "
             "shelf (W50 ~6.1, W50_m ~31 m from t_f - 0.5 to t_f + 2 s for every focus or bed variant); the FLIP decay between edge and onset "
             "(Hc x0.80, W95_m x1.46, the crossing X opening into two branches) is nonlinear and happens on any shelf"],
        why_W140="validity, not physics: at W 100 the side-band core sits on an off-axis secondary focus at x ~85-90, y ~74 (linear kp x eta 0.447, "
                 "~0.436 in FLIP terms at this energy) -> G4 fails; W 120 passes the core but the inlet wall corner reads 0.43; W 140: side core "
                 "0.35-0.38, inlet core 0.345-0.37, wall corner 0.34 (FLIP-equivalent) [computed / calibrated]; at W 140 the side-band share of the "
                 "focal sum entering over the step drops from 0.137 to 0.024",
        linear_W140=dict(converged_crest_m=r(mx["Hc"], 3), at_x_m=mx["x_pk"], at_t_rel_s=mx["t_rel"], miss_lin=r(mx["miss"], 3),
                         bands_lin=L["bands_lin"], energy_vs_DM1A=r(L["energy_vs_DM1A"], 4), aperture=L["aperture"], tag="[computed] (linear)"),
        ratios_DFGS=pred["ratios"],
        onset_rule="critical when 0.96 eta / h >= 0.78 or k7 x 0.96 eta >= C, C 0.55-0.70 (anchors: DFG-2 flat 0.54 unbroken; DFG-S 0.60-0.62 at the "
                   "edge, overturning ~1.1 s later [measured, g52s2_ana dfgbe on DFG-S: 0.605 / 0.619 / 0.619]); lip 0.5-1.1 s after the critical point [calibrated]",
        candidates={
            "a_E_W140": dict(first_break_x_m=[108, 128], h_m=[13, 20], t_rel_s=[-2.9, -1.5], Hc_curl_m=[6.1, 7.7], miss_curl_face_onset=[[0.2, 1.0], [1.8, 2.6]],
                             miss_max_instant=[0.3, 1.0], back_deg=[[13, 17], [9, 11]], w07=[[2.3, 2.9], [2.5, 3.1]],
                             if_survives_to_upper_face=dict(P=[0.10, 0.15], lip_x_m=[140, 147], h_m=[7, 9], back_deg=[14, 24], w07=[1.7, 2.0]),
                             iribarren_1to3_T7=[0.9, 1.0], Nt_cap_model=[0.72, 0.80], cost_h=[2.4, 3.0]),
            "b_timing": dict(variants="focus x 150 / 155 / 160 / 165 / 170 (t_f 43-47) or edge x 135", miss_curl_onset=[4.24, 4.33], Hc_m=4.1,
                             note="no gain: with face ratios 2.1-2.4 but S7 itself gives 2.16 under the same assumption", P_progress=0.05),
            "c_bed": dict(variants="5 m shelf (C_h5), 1:2 face (C_s2)", miss_curl=[4.29, 4.37], note="Hc capped ~3.9 m, bore risk; new hip", P_progress=0.05),
            "fallback_A_s130": dict(scale=1.30, energy_vs_DM1A=0.60, W_m=100, G4_side_core=[0.34, 0.36], lip_x_m=[115, 152], miss_curl=[[1.0, 2.2], [3.1, 3.4]],
                                    Hc_m=[5.3, 6.1], P_progress=0.15, note="NOT energy-matched: needs the user's OK")},
        files=sorted(os.path.basename(p) for p in glob.glob(DESIGN_DIR + "/*")),
        source="Unity/Build/FLIP52S2/screens/design_20261018/ (copies of the session scratchpad files; dfgs2_screen.py / dfgs2_predict.py import "
               "flip52s/dfgs_screen.py read only)")


def lessons():
    """[measured] what DFG-S (same step, same code, 0.5 m, 0.354 x DM1A energy) taught this plan."""
    J = GC.jload(DFGS_JUDGE)
    P = GC.jload(DFGS_PV53)
    Co = GC.jload(DFGS_COEQ)
    g4 = J["G4"]
    per = [dict(n=q["n"], frame=q["best"]["frame"], t=r(q["best"]["t"], 3), score3=q["best"]["score3"], lip=r(q["best"]["lip"], 3), back=r(q["best"].get("back"), 1),
                w07=r(q["best"].get("w07"), 2), eta_c=r(q["best"]["eta_c"], 2), x_c=r(q["best"]["x_c"], 1), pl_miss=r((q.get("conv_print") or {}).get("miss"), 3),
                pl_Hc=r((q.get("conv_print") or {}).get("Hc"), 2), pl_W50=r((q.get("conv_print") or {}).get("W50"), 2)) for q in P["periods"]]
    grp = [dict(n=g["n"], conv=dict(t=r(g["conv"]["t"], 3), x=g["conv"]["x"], Hc=r(g["conv"]["Hc"], 3)), onset=dict(t=r(g["onset"]["t"], 3), x=g["onset"]["x"])
                if g.get("onset") else None, max_miss=r(g["miss"], 3), Nt=r(g.get("Nt"), 3)) for g in J["groups"]]
    pre = AN.dfgbe_read(GC.DFGS_RUN)
    return dict(
        DFGS_result=dict(valid=J["valid"], outcomes=J["decision"]["outcomes"], flags=J["decision"]["physics_flags"], core_miss_median=r(J["core_miss_median"], 4),
                         median={k: r(J["median"].get(k), 3) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "N1", "Nt", "conv_Hc", "conv_x", "onset_x")},
                         groups=grp, print_like=per, print_match=Co["criterion_2_print_ruler"]["print_match"],
                         median_best_score3=Co["criterion_2_print_ruler"]["median_best_score3"], median_best_lip=r(Co["criterion_2_print_ruler"]["median_best_lip"], 3),
                         coequal_progress=Co["progress"], pl_miss_median=r(float(np.median([q["pl_miss"] for q in per])), 4),
                         source="Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/g52s + Unity/Build/FLIP53/pv53/DFGS_step3h6_xf145_dp0p5 [measured]"),
        gaps=["(1) the curl (most print-like instant) comes ~2 s after the converged instant; the crest spreads meanwhile (e51 miss 1.27 at the "
              "'max' instants, 4.28-4.55 at the print-like instants; W50 6.46-7.04, eta_c 3.9-4.0 m)",
              "(2) height 4-5 m (DM1A 7.8 m)", "(3) the back is too gentle (11.5-16.9 deg; print 31.3) and width07 2.5-2.85 (print 1.32)",
              "(the screen had predicted back ~30 deg, w07 ~1.1: missed)"],
        G4_DFGS_W100=dict(inlet=r(g4["kA_inlet_max"], 4), side_core_70_92p5=r(g4["kA_side_core_max"], 4), wall_strip=r(g4["kA_wall_strip_max"], 4),
                          full_band=r(g4["kA_side_full_max_DFG2_rule"], 4), full_at_xy=g4["side_full_max_at_xy"],
                          reading="at DFG-S's 0.354 x DM1A energy the core read 0.26 (= linear x 0.975); x 1.6806 would put it at ~0.44 on the W 100 layout "
                                  "-> W 140 [measured + computed]"),
        G2f_DFGS={k: r(v["R"], 3) for k, v in J["G2f"]["per_n"].items()},
        k7eta_critical_DFGS=dict(median=r(pre.get("k7eta_crit_median"), 3), per_group=[r((q.get("crit") or {}).get("k7eta"), 3) for q in pre.get("groups") or []],
                                 rule=AN.PRE["rule"], tag="[measured] (g52s2_ana dfgbe applied to DFG-S)"),
        new_co_requirement_why="DFG-S was PROGRESS by its frozen rule (converged instant + print match), but the converged instant and the print-like "
                               "instant were different waves ~2 s apart: the print-like crest had spread (miss 4.36). From this plan on, convergence "
                               "must also hold AT the most print-like instant (criterion 3b) [chosen by the main session's task 2026-10-18]")


def build():
    tc = GC.jload(GC.PLAN_DIR + "/table_check_DFGS2.json")
    C = GC.components()
    cp = PC.make("pcheck", dry=True); cm = PC.make("main", dry=True)
    te_p = cp["precheck"]["time"]; te_m = cm["precheck"]["time"]
    sum_a2 = float(np.sum(C["a"] ** 2))
    stepctrl = {k: GC.bed_parms(GC.SPEC_STEP)[k] for k in ("ridge_on", "ridge_x0", "ridge_k", "ridge_s", "shelf_h")}
    arr = arrival_W140()
    if arr["t_f_s"] != GC.T_F:
        raise SystemExit("the arrival rule gives t_f %s, g52s2_common.T_F is %s: not frozen" % (arr["t_f_s"], GC.T_F))
    E = TB.energy_in_tank()
    en = PC.energy_block()
    am = GC.am_dfgb1_sea()
    refs = AN.pl_refs()
    best, rows = AN.best_valid()
    bar = min(AN.DEC["bar_cap"], best - AN.DEC["bar_margin"])
    L = lessons()
    D = design_summary()
    ptxt = ("PROGRESS iff ALL of: (1) the Unity print view rendered at the most print-like instant (pv53); (2) the print match ok (median "
            "best-instant score3 <= 0.9485 = DM1A 0.6485 + 0.30, median best-instant lip >= 0.20); (3a) the convergence decision at the judge's 'max' "
            "instants NEW_BEST_SHAPE or TARGET_BAND; (3b) NEW co-requirement: the median e51 core miss at the most print-like instants (pv53's best "
            "frame per group, xwin [x_c - 60, x_c + 35] m, rows y > 65 m NaN, the judge's eta0, >= 2 groups) <= bar_pl = min(2.8, best valid "
            "earlier print-like median miss - 0.5). 'converged, print match worse than DM1A' and 'converged and print-like at different instants' "
            "are NOT progress. Reported: SAME_INSTANT_NEW_BEST (print-like miss <= the convergence bar), PRINT_BETTER_THAN_DM1A")
    plan = dict(
        status="FROZEN", plan="DFG-S-E140", campaign="FLIP52S2-DFGS2E",
        tags_legend={"[measured]": "【測定】", "[computed]": "【計算】", "[literature]": "【文献】", "[guess]": "【推測】", "[chosen]": "【選び】",
                     "[calibrated]": "【計算】 (a screen number scaled by a measured FLIP / screen ratio)"},
        title=("FLIP52S2 plan DFG-S-E140: DFG-S (1:3 step toe x 108 m -> edge x 150 m, 6 m shelf, focus (145, 0), WKB table phasing, 0.5 m) with "
               "ENERGY-MATCHED amplitudes (every component x 1.680585, a_sum 10.640186 m, sum a^2 = DM1A's 1.336153 m^2: equal spectral energy, Q84) "
               "in a W 140 m half tank (side band 110-140 m; G4 validity), t_f 48 s by the arrival rule; one 0.5 m run of three groups judged by the "
               "CO-EQUAL criteria with the NEW co-requirement that convergence also holds at the most print-like instant"),
        trigger=dict(
            user_Q83="every run is judged on (1) the Unity print-view render at the most print-like instant, (2) the centre section vs the print "
                     "outline with the print ruler, (3) the convergence metrics; progress = both convergence and the print match",
            user_Q84="compare incoming seas at EQUAL TOTAL WAVE ENERGY to DM1A (energy density 0.5 rho g sum a^2 at the generation depth; DM1A sum a^2 "
                     "= 1.336153 m^2) and say so in reports",
            DFGS_result="DFG-S (0.5 m, valid, all gates pass): converged-instant miss 1.27 (W50 4.19, W80 1.90, W95 0.86, S2 0.52, N1 0.32), Hc 5.18 m at "
                        "x 136.5 m; PLUNGE_AT_CONVERGED but onset / breaking on the shelf x ~164; most print-like instant 72.33 s score3 0.69, lip 0.45, "
                        "chord 90, but at that instant the crest had spread (e51 miss 4.36, W50 6.58) and eta_c 4.0 m; back 11.5-16.9 deg, width07 "
                        "2.5-2.85 (print 31.3 / 1.32) [measured]",
            design="the DFG-S follow-up design step (2026-10-18 ~03:20-03:40): candidate (a) DFG-S-E140 chosen by screen (see design)",
            parents=dict(DFGS_plan="Unity/Build/FLIP52S/plan/plan_DFGS_frozen.json sha %s" % GC.sha256_file(GC.DFGS_PLAN)[:16],
                         DFGB_E_sea="Unity/Build/FLIP52B/plan/amendments.jsonl AM-DFGB1 (sea), AM-DFGB1b (in-tank caveat)")),
        physics_rules=dict(
            forces="gravity, the bed (flat + step) and the incoming waves only; no force toward a shape; no wind, no current (the return current "
                   "only cancels the target's own mean mass flux)",
            Q84="the incoming sea has the same SPECTRAL energy as DM1A (sum a^2 = 1.336153 m^2 at the generation depth); this supersedes DFG-S's 'a_sum "
                "= the DM1A input sum, not enlarged' for this sea by the user's own decision Q84 (as AM-DFGB1 did for DFG-2B); no single component is "
                "larger than DM1A's (0.159 m vs 0.211 m)",
            Q54_honesty="chosen at the inlet: P, the three frequencies and equal weights, the 34 X2 directions and weights, the energy-matched a_sum, "
                        "the focus (145, 0) at t = 48 + 28 m s, the W 140 tank and bands, and the step (toe, slope, shelf depth); computed by FLIP: "
                        "propagation, dispersion, refraction, shoaling, reflection, focusing, the crest's growth, breaking, any jet / plume / bore"),
        sea=dict(P_s=GC.P_S, harmonics_n=list(GC.HARMONICS), T_s=[round(GC.P_S / n, 6) for n in GC.HARMONICS],
                 freq_weights=[round(float(v), 6) for v in C["wf"]], directions_deg=[round(float(v), 6) for v in C["th"]],
                 dir_weights=[round(float(v), 6) for v in C["wd"]], dspec=list(GC.DSPEC), n_components=int(C["a"].size),
                 a_sum_m=round(C["a_sum"], 9), a_max_component_m=round(float(C["a"].max()), 6), amp_per_freq_m=[round(float(C["a_sum"] * v), 6) for v in C["wf"]],
                 sum_a2_m2=round(sum_a2, 6), generation_depth_m=GC.H0, ramp_s=GC.RAMP_S, scale_vs_DFGS=round(GC.E_SCALE, 8),
                 same_as="the DFG-2 / DFG-S frequency and direction set x %.8f = the AM-DFGB1 sea of DFG-2B-E bit for bit (g52s2_pcfg checks both "
                         "against flip52 g52_common and the registered AM-DFGB1 numbers %s)" % (GC.E_SCALE, json.dumps(am and {k: am[k] for k in ("a_sum_m", "sum_a2_m2", "scale")})),
                 focus=dict(x_m=GC.X_F, y_m=0.0, h_m=r(GC.h_of(GC.X_F), 4), t_f_s=GC.T_F, times_s=list(GC.FOCI), arrival=arr,
                            rule="x_f 145 m = DFG-S (screen S7) [chosen]; t_f = ceil(t_full + 3.9 s) = ceil(%.2f + 3.9) = %d s on the W 140 layout (the "
                                 "large-angle rays now start at the side band edge y 110 m: t_full 38.68 -> %.2f s) [computed]"
                                 % (arr["t_full_s"], int(GC.T_F), arr["t_full_s"]),
                            design_linear_crest_m=r(tc["focus"]["total_design_crest_m"], 4),
                            per_layer_shoal_refr_gain=[r(p["shoal_refr_gain"], 4) for p in tc["focus"]["per_layer"]]),
                 energy=dict(basis="equal spectral energy (Q84): the energy density 0.5 rho g sum a^2 of the incoming components at the generation "
                                   "depth (DFG-S-E140 h0 20 m; DM1A h0 19 m), as in an open sea of unbounded width",
                             statement=GC.sea_text(), sum_a2_m2=round(sum_a2, 6), DM1A_sum_a2_m2=round(GC.DM1A_SUM_A2, 6), ratio=r(sum_a2 / GC.DM1A_SUM_A2, 6),
                             E_Jm2=r(0.5 * 1000.0 * GC.G * sum_a2, 1), DM1A_E_Jm2=r(0.5 * 1000.0 * GC.G * GC.DM1A_SUM_A2, 1),
                             in_tank=dict(DFGS2E=E["DFGS2E"], DM1A=E.get("DM1A"), DFGS=E.get("DFGS"), DFGB_E=E.get("DFGB_E"),
                                          reproduces_AM_DFGB1b=E.get("reproduces_AM_DFGB1b"), rule=E["rule"], tag=E["tag"]),
                             statement_in_tank=E["statement_en"],
                             caveat="AM-DFGB1b caveat applies: equal SPECTRAL energy is not equal IN-TANK energy. On this plan's own layout the inlet-band "
                                    "variance is %.3f x DM1A's and the power entering the interior %.3f x DM1A's [computed]; the design step quoted "
                                    "DFG-2B-E's 0.13 / 0.23 (its D19B layout), which is not this tank's number. Reports state both the spectral "
                                    "equality and these in-tank ratios" % (E["DFGS2E"]["inlet_variance_over_DM1A"], E["DFGS2E"]["interior_power_over_DM1A"]),
                             report_rule="every judge, co-equal verdict, status line and video of this plan carries 'equal spectral energy (Q84)' and "
                                         "the in-tank ratios (cfg wave.energy -> judge energy_statement -> coequal verdict)")),
        tank=dict(kind="DFG-S's half tank widened to W 140 m (symmetry plane y = 0, outer side wall y = 140 m) with the laterally uniform step; the "
                       "DFG-S 0.5 m parms (Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/cfg.json) except parms_differ_from_DFGS",
                  h0_m=GC.H0, Lx_m=GC.LX, W_m=GC.W_MAIN, z_bed_m=GC.ZB, z_top_m=GC.Z_TOP, surface_crop_z1_m=GC.CROP_Z1,
                  why_W140=D["why_W140"],
                  step=dict(x_toe_m=GC.X_TOE, slope_1_in=GC.SLOPE_S, h_top_m=GC.H_TOP, x_edge_m=GC.X_EDGE, ctrl=stepctrl,
                            formula="depth = max(6, 20 - max(x - 108, 0)/3), all y (= DFG-S)",
                            vex="NO new VEX term (= DFG-S): the FLIP48 plain branch of bedy / bedgrad / bedsdf_out with ridge_on 1, ridge_k 0, "
                                "ridge_x0 108, ridge_s 3, shelf_h 6",
                            selfcheck_at_freeze={k: v for k, v in GC.bed_selfcheck().items() if k in ("ok", "equals_analytic_bit", "grad_ok", "sdf_ok",
                                                                                                     "dirfield_bed_h_ok", "plain_path",
                                                                                                     "vex_transliteration_max_abs_dz_m")},
                            hython_check="build_check52s2.json: OUT_BED heights and the collision SDF vs numpy on the step strip (W 6 m) and 3D box "
                                         "(W 140 m) at dp 0.5, depth range exactly 6-20 m, particle seeding vs count_particles at W 140, no particle "
                                         "below the bed; dir_probe on the W 140 table; relax_probe on the W 140 layout",
                            hip="Houdini/FLIP52S2/g52s2_tank.hiplc: the bed is unchanged; the scene is rebuilt (by auto_DFGS2.py, ~1 min hython) only "
                                "so that the build check (the chain's start gate) covers THIS layout; Houdini/FLIP52S (frozen DFG-S) is not touched"),
                  solver=dict(dp=[0.5], gridscale=2.0, cfl=1.0, pcfl=0.75, minsub=1, maxsub=8, veltransfer="flip"),
                  bands=dict(inlet=dict(x_m=[0.0, GC.IN_X1], xg_end=GC.IN_X1, wall_taper_m=GC.WALL_TAPER, relax_g=1.0, in_gain=1.0),
                             side=dict(y_m=[GC.SD0, GC.W_MAIN], sd0=GC.SD0, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW, sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW,
                                       sd_taper_m=GC.SD_TAPER, sd_gain=1.0, note="generates for x <= 180 m; at W 140 only %.1f %% of the focal linear "
                                                                                  "sum enters over the step through it (DFG-S W 100: 13.7 %%) [computed]"
                                                                                  % (100 * arr["frac_of_focal_sum_from_side_over_step"])),
                             exit_sponge=dict(abs_on=1, xa0=GC.XA0, abs_sigma=GC.ABS_SIGMA, abs_pow=GC.ABS_POW, length_m=GC.LX - GC.XA0, over="the 6 m shelf"),
                             ret_on=1, dir_on=1, volume=dict(stage="A (AM-D18, = DFG-2 / DFG-S)", vol_x_m=list(GC.VOL_X))),
                  interior=dict(x_m=list(GC.INTERIOR_X), y_abs_max_m=GC.INTERIOR_Y, scan_x_m=list(GC.SCAN_X), onset_x_m=list(GC.ONSET_X),
                                free_lateral_strip="y 65-110 m (new at W 140): not in the metrics (rows y > 65 m NaN, = DFG-S); its crest steepness is "
                                                   "REPORTED by the judge (G4 kA_free_lateral) because the off-axis secondary focus (x 80-90, y 72-75; "
                                                   "FLIP kp x eta ~0.44-0.47 expected) now lies there"),
                  parms_differ_from_DFGS=list(PC.PARMS_DIFFER_FROM_DFGS), named_differences=cm["precheck"].get("named_differences"),
                  sea_into_tank="N-layer table (g52s2_table: WKB DirField kind 'shelf' per harmonic, 1 m, x 0-214 m, y 0-140 m, energy-matched) read "
                                "by the unchanged N-layer VEX of flip52/g52_tanklib.py in the scene Houdini/FLIP52S2/g52s2_tank.hiplc"),
        records=dict(hf="top-surface height field (1 m) every frame (full width 0-140 m)", r2="centre section y 0.5 m every frame (print ruler, lips)",
                     r3="section y 40 m every frame (report)", r4="per-y sections x 90-200 m, y 0-65 m, every 3rd frame in the group windows",
                     r5="surface meshes (crop x 90-200 m, y 0-70 m = DFG-S) every 3rd frame in the group windows (Unity print view, mp4)",
                     gauges="x 60 / 100 / 145 / 190 m, y 0.5 / 15 / 30 / 45 / 60 m (G2f at x 60 m)",
                     checkpoints="every 48 frames (resume after the 1740 s launch limit); none in the optional pipeline check",
                     group_window_s=list(GC.GROUP_WIN), t_end_s=dict(main=PC.T_END["main"], pcheck=PC.T_END["pcheck"]), r4_x_m=list(GC.R4_X),
                     windows_main_s=PC.windows_for("main", PC.T_END["main"]), pcheck_window_s=list(PC.PCHECK_WIN),
                     no_1m_smoke="dp 1.0 damps the 5.6 s layer (DFG-2 smoke n5 0.43, DFG-2B-E smoke n5 0.46 [measured]): none",
                     pcheck_optional="the 0.5 m 10 s pipeline check is NOT run by default (auto_DFGS2.py --pcheck runs it): the bed, VEX, seeding and "
                                     "code path are DFG-S's, whose identical check passed (PCHECK_PASS 2026-10-18 01:56); the new box, bands and table "
                                     "are covered by the hython build check"),
        criteria=dict(
            coequal=dict(COEQ_note="CO-EQUAL CRITERIA, shown side by side for every judged run (user Q83), all needed for progress",
                         criterion_1="the Unity PRINT-VIEW render (option-D composition) at the run's most print-like instant + a front view + the print "
                                     "(Tools/GWWaveGen/flip53/pv53.py run <run dir>, unchanged; its stills and mp4 are shown to the user)",
                         criterion_2="the centre section vs the Hokusai print outline with the print ruler (score3, hollow, lip, back 0.7-0.9 eta_c, "
                                     "width07) at the most print-like instant of each group (pv53 rule: frames [t_max - 1.5, t_max + 3.0] s of the "
                                     "judge's 'max' instant, crest floor 0.6 Hc (AM-DFG2a))",
                         criterion_3="the convergence metrics (flip51/e51_metrics.py frozen ruler, target read from the user's screenshot through its "
                                     "frozen read values only) at the judge's 'max' instants, medians over the groups, and the frozen decision",
                         criterion_3b="NEW (this plan): the same convergence metrics AT THE MOST PRINT-LIKE INSTANT of each group (pv53's best frame), "
                                      "median over the groups; must also pass (bar_pl)",
                         score3_bar=AN.COEQ["score3_bar"], score3_DM1A_median=AN.COEQ["score3_DM1A_median"], tol=AN.COEQ["tol"],
                         lip_min=AN.COEQ["lip_min"], conv_outcomes=AN.COEQ["conv_outcomes"], print_ref=AN.COEQ["print_ref"],
                         print_like_instant=dict(cap=AN.COEQ_PL["cap"], margin=AN.COEQ_PL["margin"], min_groups=AN.COEQ_PL["min_groups"],
                                                 xwin_rel_m=list(AN.COEQ_PL["xwin_rel"]), ymax_m=AN.COEQ_PL["ymax"], references=sorted(AN.PL_REFS),
                                                 rule=AN.COEQ_PL["rule"], at_freeze=dict(bar_pl=r(refs["bar_pl"], 4), best_valid_pl=r(refs["best_valid_pl"], 4),
                                                                                          rows={k: {kk: v.get(kk) for kk in ("pl_miss_median", "valid", "missing")}
                                                                                                for k, v in refs["rows"].items()}),
                                                 DFGS_measured=AN.COEQ_PL["DFGS_measured"], DM1A_best_report=AN.COEQ_PL["DM1A_best_report"],
                                                 why="DFG-S: converged and print-like instants ~2 s apart, the print-like crest spread (miss 4.36) [measured]",
                                                 same_instant_report="SAME_INSTANT_NEW_BEST if the print-like median miss <= the convergence bar"),
                         progress_rule=ptxt,
                         no_print_view_no_progress="a run without the print-view package or without its Unity render is INCOMPLETE, never progress",
                         prebreak_report="the judge also reports the centre-row pre-break shape (onset - 0.5 s; back 0.7-0.9 eta_c, width at 0.7 eta_c) "
                                         "against the print's back 31.3 deg (29-38) and width07 1.32 (1.02-1.42): report only",
                         energy_report="every verdict carries the Q84 energy statement (equal spectral energy; in-tank ratios)"),
            groups=dict(window_s=list(GC.GROUP_WIN), scan_x=list(AN.GROUP["scan_x"]), onset_x=list(AN.GROUP["onset_x"]), Nt_x=list(AN.GROUP["Nt_x"]),
                        face_edge_x=AN.GROUP["face_edge_x"],
                        conv="largest Hc over x 90-200 m, |y| <= 65 m in [t_fn - 8, t_fn + 2] s",
                        onset="first r2 lip (AM-DFG1 test) at x 90-205 m in the window",
                        max_instant="plan E D rule: onset -> e51 max in [on - 3, on + 1.5] s, x [on_x - 60, on_x + 35] m; else conv",
                        Nt_rule="DFG-2 rule: largest interior Hc (x 60-205 m, |y| <= 65 m) in [t_fn - 14, t_fn + 14) at |t - t_max| >= 3.5 s / Hc('max'); "
                                "reported beside it: the same in x 60-160 m",
                        c_in="largest crest on x 60 m, |y| <= 65 m in [t_fn - 14, t_fn + 14)",
                        plunge_at_converged="r2 onset within [t_conv - 1, t_conv + 4] s and x_on <= x_conv + 30 m",
                        onset_on_face_or_edge="r2 onset x <= x_edge + 10 = 160 m"),
            A_validity=dict(
                G1=dict(rule="numpy table check table_check_DFGS2.json all_ok (focus vs independent WKB sums, flat part = DFG-2 amplitudes x scale, "
                             "shelf constant, symmetry, continuity flat + shelf < 5e-3 (face reported), interpolation < 2 %, vertical profile < 1e-4, "
                             "zero mass flux per layer < 1e-6 and the all-layer total < 1e-3, P-periodicity) + build_check52s2 all_ok with the hip the "
                             "launches used + cfg precheck ok",
                        mass_flux_total_note="the all-layer total through x = const carries a higher-order residual of the stretched-depth profile at "
                                             "the energy-matched amplitude (1e-4 at x 190 m, 3e-6 at x 145 m; DFG-S 1e-8) [computed]; per layer it is "
                                             "exact (< 1e-6): tolerance for the total 1e-3 [chosen before any FLIP52S2 run]"),
                G2f=dict(rule=AN.G2F_RULE, x=AN.GATES["G2f_x"], y=list(AN.GATES["G2f_y"]), window_s=list(AN.GATES["G2f_t_main"]),
                         floor=AN.GATES["G2f_floor_0p5"], margin=AN.GATES["G2f_margin_0p5"], hi=AN.GATES["G2f_hi_0p5"], phase=AN.GATES["G2f_phase_0p5"],
                         reference=AN.DFG_REF.replace(GC.REPO + "/", ""), fallback={str(k): list(v) for k, v in AN.GATES["G2f_fallback_0p5"].items()},
                         lesson="DFG-S measured n3 1.031, n4 0.949, n5 0.791 with the same rule [measured]"),
                G3P=dict(P_s=GC.P_S, tol_s=AN.GATES["G3P_tol"], x_spread_m=AN.GATES["G3P_xspread"], Hc_ratio=AN.GATES["G3P_Hc_ratio"], on="the 'conv' summits"),
                G4=dict(kA_max=AN.GATES["G4_kA"], t0_s=AN.GATES["G4_t0"], inlet_x_max=AN.GATES["G4_inlet_x"],
                        side_core_y=[AN.GATES["G4_side_y"], AN.GATES["G4_side_y1"]], side_x_max=AN.GATES["G4_side_x"], lip_x_max=AN.GATES["G4_lip_x"],
                        rule="kp x (3x3-median hf - eta0) <= 0.40 from t 30 s in the inlet band (x <= 50 m, all y 0-140 m) and the generating side-band "
                             "CORE (110 <= y <= 132.5 m, x <= 180 m); no overturning r2 lip at x < 60 m (the DFG-S text, with this tank's sd0 and W)",
                        reported_not_gated="the outer-wall strip y > 132.5 m, the full band (y >= 110 m), k(h(x)) x crest in the core, and the free "
                                           "lateral strip y 65-110 m (the off-axis secondary focus)",
                        expected_linear=dict(inlet=tc["band_linear_steepness"]["kp_crest_inlet_lin"], side_core=tc["band_linear_steepness"]["kp_crest_side_core_lin"],
                                             wall_strip_target=tc["band_linear_steepness"]["kp_crest_wall_strip_lin_target"],
                                             FLIP_over_linear_DFGS=dict(side_core=0.975, inlet_wall_corner=1.255), tag="[computed] linear table; [measured] ratios"),
                        margin_note="the side-core margin is 0.02-0.06 below 0.40 [calibrated]; a Stokes-type crest gain of 5-10 % could reach 0.40"),
                G5=dict(max=AN.GATES["G5_max"]),
                G6=dict(x=list(AN.GATES["G6_x"]), y_abs_max=AN.GATES["G6_y"], t_rel=list(AN.GATES["G6_t"]), Hc_min=AN.GATES["G6_Hc"],
                        why="design (a): the linear converged crest 8.78 m at x 128 m, t_rel -1.5 s (x 103 m at -3.5 s); FLIP's first break at x 108-128 m, "
                            "t_rel -2.9 .. -1.5 s [calibrated]; the DFG-S window (x 110-175, t -4 .. 2) would cut an early steepness break: x from 95 m, "
                            "t from -5 s; Hc floor = 0.68 x the linear design crest 8.635 m at x_f (the plan E / DFG-S rule) = 5.87 m [computed / chosen]"),
                also="run complete (f_end reached), 3 groups",
                failure_class="pipeline = run incomplete, G1, G2f (the main session fixes the cause and reruns once, same setup name); physics = "
                              "G3P, G4, G5, G6"),
            B_eligibility=dict(AN.ELIG),
            decision=dict(bar_cap=AN.DEC["bar_cap"], bar_margin=AN.DEC["bar_margin"], DF1A_miss=AN.DEC["DF1A_miss"], target_band=AN.DEC["target_band"],
                          jet_ratio=AN.DEC["jet_ratio"], plunge_groups=AN.DEC["plunge_groups"], best_valid_runs=sorted(AN.BEST_RUNS),
                          best_valid_from="DF1A 3.3 [measured] and, if valid by their own plans, plan E X2 / X1, DFG-2, DFG-2B, X2B', DFG-S and DFG-2B-E 0.5 m "
                                          "(read at analysis time)",
                          bar_at_freeze=r(bar, 4), best_valid_at_freeze=r(best, 4),
                          best_rows_at_freeze={k: {kk: v.get(kk) for kk in ("miss", "valid", "missing")} for k, v in rows.items()},
                          jet_note="jet_ratio = Hc / a_sum (= DFG-S's definition; a_sum is now 10.64 m, so JET_REGIME_SEEN needs Hc >= 13.8 m: a report "
                                   "outcome only)",
                          outcomes="INVALID / NOT_ELIGIBLE / NEW_BEST_SHAPE (miss <= bar) / TARGET_BAND (miss <= 0.5) / JET_REGIME_SEEN / NO_GAIN; "
                                   "physics flags PLUNGE_AT_CONVERGED / BREAKS_LATER / NO_BREAK_IN_WINDOW / ONSET_ON_FACE_OR_EDGE / BREAKS_ON_SHELF "
                                   "(>= 2 of 3 groups)",
                          after="no automatic follow-up run: the co-equal verdict, the print-view stills and the numbers go to the user / main session"),
            pcheck=dict(role="OPTIONAL PIPELINE CHECK (0.5 m, 0-10 s; never shape-judged; auto_DFGS2.py --pcheck)",
                        pass_rule="as DFG-S: run complete; G1; G5; no guard stop; no particle below the bed; |eta0| <= 0.25 m; still water over the step "
                                  "at t 0.5-1.5 s; waves arrive at x 60 m in t 6-10 s with 0.33-3.0 x the ramped linear target; records written",
                        still_diff_max_m=AN.GATES["pc_still_diff_max"], still_abs_max_m=AN.GATES["pc_still_abs_max"], wave_ratio=list(AN.GATES["pc_wave_ratio"]),
                        on_fail="the 0.5 m run does not start; the main session reads g52s2/pcheck_DFGS2.json and decides")),
        pre_launch_check=dict(
            what="the design's condition 'before launching, read DFG-2B-E (same sea x 1.6806 on its D19B 1:10 beach)': applied automatically by "
                 "auto_DFGS2.py after DFG-2B-E's final FINISHED line and before the build",
            rule=AN.PRE["rule"], k7eta_max=AN.PRE["k7eta_max"], lip_min=AN.PRE["lip_min"], min_onset_groups=AN.PRE["min_onset_groups"],
            window_s=AN.PRE["win_s"], run=AN.PRE["run"].replace(GC.REPO + "/", ""),
            action="either trigger -> STOP before the build (nothing launched), status 'PRECONDITION_FAIL'; the design fallback A_s130 (scale 1.30, "
                   "0.60 x DM1A energy, W 100, no new tank) is NOT energy-matched and needs the user's OK. No DFG-2B-E judge -> no evidence: the run "
                   "proceeds and the status says so. --no-dfgbe-check skips the read (the main session's decision, logged)",
            DFGS_calibration=L["k7eta_critical_DFGS"]),
        lessons_measured=L,
        design=D,
        expected=dict(
            tag="per group (groups at 48 / 76 / 104 s); [computed] / [calibrated] / [guess] as marked",
            first_break=dict(x_m=[108, 128], h_m=[13, 20], t_rel_s=[-2.9, -1.5], Hc_m=[6.1, 7.7], kind="steepness-limited 3D focused crest, lobes at "
                             "+-52-58 deg; ~1 s of later breaking on the face or shelf possible", tag="[calibrated]"),
            convergence=dict(max_instant_miss=[0.3, 1.0], curl_miss=dict(face_ratios=0.7, onset_ratios=2.1), DFGS_measured=dict(max=1.27, curl=4.36),
                             tag="[calibrated]"),
            shape_at_curl=dict(back_deg=[9, 17], w07=[2.3, 3.1], if_upper_face=dict(back_deg=[14, 24], w07=[1.7, 2.0]), print=dict(back=31.3, w07=1.32),
                               score3_lip="not predicted by the screen", tag="[calibrated]"),
            height=dict(Hc_m=[6.0, 7.7], DM1A_m=7.8, basis="equal spectral energy"),
            G4=dict(inlet=[0.34, 0.37], side_core=[0.35, 0.38], wall_strip_report=0.48, tag="[calibrated]"),
            probabilities=dict(curl_better_than_DFGS=0.65, curl_better_if_forward_plunge=0.85, curl_better_if_jet=0.4,
                               print_match_not_worse_than_DFGS=0.30, print_bars_absolute=0.50, valid=0.60, valid_parts=dict(G4=0.8, G2f=0.9, G3P=0.85, G5_G6=0.95),
                               eligible_given_valid=0.70, NEW_BEST_SHAPE_given_valid_eligible=0.45, TARGET_BAND_given_valid_eligible=0.25,
                               print_like_co_requirement_3b_pass=0.45, frozen_rule_PROGRESS_without_3b=[0.10, 0.12],
                               PROGRESS_this_plan_with_3b=[0.06, 0.08], b_or_c_progress=0.05, fallback_A_s130_progress=0.15, tag="[guess]")),
        cost=dict(main=te_m, pcheck_optional=te_p, max_hours=dict(PC.MAX_H),
                  particles_main_M=dict(model=r(cm["precheck"]["particles_model"] / 1e6, 3), peak=[r(v, 3) for v in cm["precheck"]["particles_peak_M"]],
                                        DFGS_measured_peak=3.276925),
                  build_min=[1, 5], analysis_min=dict(judge=[1, 3], pv53_unity=[5, 12], video=[2, 5]),
                  total_h=[r(te_m["est_h"][0] + 0.2, 2), r(te_m["est_h"][1] + 0.5, 2)], disk_GB=[5, 9],
                  note="Houdini after DFG-2B-E's final line (~06:00-06:30 on 2026-10-18 [guess]); max_hours 2.5 per chain; auto_DFGS2 resumes a "
                       "max_hours stop from the last checkpoint (up to --cap-resumes, default 2)"),
        order=["freeze this plan (no FLIP52S2 run exists)",
               "auto_DFGS2.py: wait for the FINAL '<date> <time> DFGB FINISHED' line of Unity/Build/FLIP52B/_logs/auto_DFGB_status.txt, no hython and no "
               "other pipeline process on 3 polls",
               "the pre-launch read of DFG-2B-E (stop on a trigger)", "build (x52s2_build.py: table, G1, hython scene build + check)",
               "[optional --pcheck] 0.5 m 10 s pipeline check", "0.5 m run (resume on crash / max_hours)",
               "g52s2_ana judge -> pv53 run (Unity print view) -> g52s2_ana coequal (with 3b) -> g52s2_video"],
        automation=dict(script=AUTO, start="py -3.10 -B \"%s\"" % AUTO, status="Unity/Build/FLIP52S2/_logs/auto_DFGS2_status.txt (prefix 'DFGS2 ', final "
                                                                                "'<date> <time> DFGS2 FINISHED ...')",
                        sha256=(GC.sha256_file(AUTO) if os.path.exists(AUTO) else None), started_by_author=False,
                        wait_rule="starts only after the LAST 'DFGB ' line of Unity/Build/FLIP52B/_logs/auto_DFGB_status.txt matches exactly "
                                  "^<date> <time> DFGB FINISHED( <msg>)?$, no hython and no other pipeline process (auto_*.py other than itself, "
                                  "*_chain.py, *_run.py, x5*_build.py, pv53.py) on 3 consecutive polls with the same last line",
                        simulate="py -3.10 -B auto_DFGS2.py --simulate[=scenario.json]: no wait, no launch, nothing written"),
        honesty=dict(chosen_at_inlet="P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and Gaussian weights, a_sum 10.640186 m "
                                     "(DFG-S x 1.680585: equal spectral energy with DM1A, Q84), the W 140 tank and bands, the step (toe 108 m, 1:3, 6 m "
                                     "shelf), the focus (145, 0) at t = 48 + 28 m s",
                     computed_by_FLIP="propagation, dispersion, refraction, shoaling, reflection, focusing, the crest's growth, breaking, any jet / "
                                      "plume / bore",
                     input_energy="equal SPECTRAL energy with DM1A (sum a^2 1.336153 m^2); in the tank the incoming linear waves carry less "
                                  "(inlet-band variance %.2f x, interior power %.2f x DM1A's) [computed]"
                                  % (E["DFGS2E"]["inlet_variance_over_DM1A"], E["DFGS2E"]["interior_power_over_DM1A"]),
                     two_changes="amplitude (the physics change) AND width W 140 (a validity change for G4: without it the side band itself would be "
                                 "too steep); t_f follows from the frozen arrival rule; nothing else of DFG-S changes",
                     gates="G4 text unchanged (core = sd0 .. W - 7.5 m); G6 window widened for the predicted early break BEFORE any run; G1 all-layer "
                           "mass-flux tolerance 1e-3 (per layer 1e-6) BEFORE any run",
                     not_done="no force toward a shape, no wind or current; the target picture only through e51; nothing committed; README / Docs not "
                              "edited; no Houdini started; no file of the running DFG-2B-E (flip52b, flip52, FLIP52B hip, cfgs, plans) or of the frozen "
                              "DFG-S (flip52s, FLIP52S plan / hip / runs) touched; auto_DFGS2.py not started"),
        risks=[
            "Early steepness breaking is very likely (P 0.85-0.9): the linear k7 x eta of the energy-matched crest is 0.84-0.89 at x 121-136 m, above "
            "what FLIP has shown (DFG-2 0.54 unbroken, DFG-S 0.60-0.62 at the edge); the crest may break at x 105-128 m in 13-20 m of water, before "
            "the converged plateau and most of the shelf refraction, so the step may be mostly a second breaking site [calibrated / guess]",
            "Jet instead of a forward plunge (P 0.4-0.5) [literature: McAllister et al. 2019 JFM 860, the Draupner recreation: crossings near 120 deg "
            "break as a vertical jet]: at h 15-20 m the lobes cross at 105-115 deg; lip and score3 may get worse and pv53 may pick the later shelf "
            "breaker, where convergence is about DFG-S's",
            "All FLIP / linear ratios were measured at 0.354 x DM1A energy; their amplitude dependence is untested; the breaking threshold C 0.55-0.70 "
            "is a guess between two anchors. The pre-launch read of DFG-2B-E (same sea x 1.6806) is the check before launch",
            "G4 margin is small (0.02-0.06 below 0.40 at W 140), resting on DFG-S's FLIP / linear 0.975 (side core) and 1.255 (inlet wall corner); a "
            "Stokes-type crest gain of ~5-10 % could push the side core to ~0.40",
            "Two changes at once: W 140 needs a new box, a W 140 table, a W 140 build check and ~1.4 x particles (~4.6 M); W 120 would be cheaper but "
            "needs an inlet-gate redefinition",
            "Eligibility on Nt (limit 0.75): the cap model gives 0.72-0.80 before dissipation (DFG-S measured 0.73); G3P may suffer if steepness "
            "breaking varies from group to group",
            "G6 Hc floor 5.87 m: an early steepness break at C 0.55 in h 13-15 m caps the crest near ~5.8-6.3 m before any jet raises the top surface: "
            "a G6 physics failure is possible (P ~0.1) [guess]",
            "The print shape at the curl is not predicted to improve (back 9-17 deg, w07 2.3-3.1 vs the print's 31.3 / 1.32); only if the crest "
            "survives to the upper face (P 0.10-0.15)",
            "The new co-requirement 3b (convergence at the print-like instant <= bar_pl, currently 2.25 from X2B' 2.75) is strict: predicted curl miss "
            "0.7 (face ratios) to 2.1 (onset ratios); P(pass) ~0.45 [guess]",
            "At W 140 the off-axis secondary focus (x 80-90, y 72-75; FLIP kp x eta ~0.44-0.47) is in the free interior: expected not to break; if it "
            "does it is a secondary breaker outside |y| <= 65 m (reported by the judge's free-lateral reading, not in the e51 metrics)",
            "Q84 honesty: spectral energy equal to DM1A's, in-tank energy lower (this layout: inlet variance %.2f x, interior power %.2f x DM1A's); "
            "reports state both" % (E["DFGS2E"]["inlet_variance_over_DM1A"], E["DFGS2E"]["interior_power_over_DM1A"]),
            "The screen has no handle for (b) / (c) beyond the linear field; their predicted no-gain could be wrong in their favour (the linear screen "
            "contradicts that: the linear crest persists on the shelf)",
            "The G1 all-layer zero-mass-flux tolerance was loosened to 1e-3 at this amplitude (per layer unchanged at 1e-6): the return current is "
            "exact per layer, the residual is a higher-order stretched-profile term [computed]"],
        metrics_ruler=dict(e51="Tools/GWWaveGen/flip51/e51_metrics.py", e51_sha256=AN.E51_SHA,
                           print_view="Tools/GWWaveGen/flip53/pv53.py (sha at freeze %s)" % (GC.sha256_file(AN.PV53)[:16] if os.path.exists(AN.PV53) else None)),
        table_check=dict(all_ok=tc["all_ok"], content_sha256=tc["content_sha256"], ok=tc["ok"], continuity_face=tc["continuity"]["per_layer"],
                         band_linear_steepness=tc["band_linear_steepness"], mean_mass_flux_rule=tc["mean_mass_flux"].get("rule")),
        code_sha256={("Tools/GWWaveGen/flip52s2/" + nm): GC.sha256_file(os.path.join(HERE, nm)) for nm in GC.CODE_FILES if os.path.exists(os.path.join(HERE, nm))},
        inputs_sha256=dict({rel: GC.sha256_file(GC.REPO + "/" + rel) for rel in (
            "Unity/Build/FLIP52S/plan/plan_DFGS_frozen.json", "Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/cfg.json",
            "Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/g52s/judge_DFGS.json", "Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/g52s/coequal_DFGS.json",
            "Unity/Build/FLIP53/pv53/DFGS_step3h6_xf145_dp0p5/pv53_DFGS_step3h6_xf145_dp0p5.json",
            "Unity/Build/FLIP52B/plan/amendments.jsonl", "Tools/GWWaveGen/flip52s/dfgs_screen.py", "Unity/Build/FLIP50/tables/D_DM1_T12_W140_c5c22196af32.npz")},
            **{("Unity/Build/FLIP52S2/screens/design_20261018/" + os.path.basename(p)): GC.sha256_file(p) for p in sorted(glob.glob(DESIGN_DIR + "/*"))}),
        table_npz=dict(path=cm["dir"]["npz"].replace(GC.REPO + "/", ""), sha256=cm["dir"]["npz_sha256"], content_sha256=cm["dir"]["content_sha256"]),
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        frozen_before_any_FLIP52S2_run=True)
    if not plan["table_npz"]["sha256"]:
        raise SystemExit("the table npz is not written (py -3.10 -B g52s2_table.write): not frozen")
    return plan


def freeze():
    ex = runs_exist()
    if ex:
        raise SystemExit("FLIP52S2 run folders exist (%s): the plan is frozen; change it only by an amendment" % ex[:3])
    if os.path.exists(GC.PLAN) and "--refreeze-before-runs" not in sys.argv:
        raise SystemExit("%s exists; --refreeze-before-runs (allowed only while no FLIP52S2 run exists)" % GC.PLAN)
    p = build()
    GC.jdump(p, GC.PLAN)
    h = GC.sha256_file(GC.PLAN)
    open(GC.PLAN + ".sha256", "w", encoding="utf8").write("%s  plan_DFGS2_frozen.json\n" % h)
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
        print(json.dumps(GC.clean(build()), ensure_ascii=False, indent=1)[:40000])
    elif a[0] == "freeze":
        p, h = freeze()
        print("frozen", GC.PLAN, h)
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
