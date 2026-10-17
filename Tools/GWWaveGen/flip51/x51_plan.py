# -*- coding: utf-8 -*-
"""FLIP51 plan E: the frozen plan (setups, metrics, criteria, promotion rule, honesty) -> Unity/Build/FLIP51/plan/plan_E_frozen.json + .sha256
(py -3.10 -B). 2026-10-17 written new (Claude). Every number of the rules is read from the code that applies it (x51_ana: SCAN, N1DEF, GATES,
ELIG, BARS, OUT05; e51_metrics: FROZEN, TARGET; x51_common: CASES), so the plan and the code cannot disagree; the code files are registered
with their sha256 and the automation (G:/research/Wave Simulation/_tools/auto_E.py) refuses to run if any of them changed after freezing.
usage:
  py -3.10 -B x51_plan.py calib                      the pre-freeze calibration (x51_ana.calib) -> Unity/Build/FLIP51/plan/calib_E.json
  py -3.10 -B x51_plan.py freeze [--force=1 --reason=...]   write the frozen plan (refused once a plan E run has records)
  py -3.10 -B x51_plan.py verify                     the registered shas against the files now (json; exit 1 on a mismatch)
"""
import os, sys, json, time, glob

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import x51_common as XC              # noqa: E402
import x51_ana as XA                 # noqa: E402
import e51_metrics as EM             # noqa: E402
import g50_common as GC              # noqa: E402  read only

AUTO = "G:/research/Wave Simulation/_tools/auto_E.py"
CALIB = XC.PLAN_DIR + "/calib_E.json"
USER_WORDS = ("这种你以后能自己确认的就自己确认 ，我感觉造型上大浪还是不够收束...，是不是应该继续调整造型为目标，我想要的收束是截图这种感觉的收束，"
              "可能纯物理确实很难做到，但还是去尽力接近这类效果")


def rel(p):
    return p.replace("\\", "/").replace(XC.REPO + "/", "")


def registered_files():
    fs = dict(XC.code_files())
    fs["_tools/auto_E.py (G:/research/Wave Simulation)"] = AUTO
    return fs


def e_runs_with_records():
    out = []
    for root in (XC.SMOKE_ROOT, XC.RUNS_ROOT):
        out += [p for p in glob.glob(root + "/S51*/run.json")]
    return out


def build():
    cal = json.load(open(CALIB, encoding="utf8"))
    cases = {}
    for c in XC.ORDER:
        th, w = XC.components(c)
        tcp = XC.PLAN_DIR + "/table_check_%s.json" % c
        tc = json.load(open(tcp, encoding="utf8"))
        rows = {}
        for dp in (1.0, 0.5):
            p = XC.cfg_path(c, dp)
            cfg = json.load(open(p, encoding="utf8"))
            rows["dp%s" % ("%.1f" % dp).replace(".", "p")] = dict(run_id=cfg["run_id"], cfg=rel(p), cfg_sha256=XC.sha256_file(p),
                                                                  run_dir=rel(XC.run_dir(c, dp)), precheck_ok=cfg["precheck"]["ok"],
                                                                  precheck_time=cfg["precheck"].get("time"), max_hours=cfg["max_hours"],
                                                                  parms_diff_vs_reference=cfg["precheck"]["diff_vs_reference"]["parms_diff"],
                                                                  reference_cfg=cfg["case"]["reference_cfg"])
        dr = json.load(open(XC.cfg_path(c, 1.0), encoding="utf8"))["dir"]
        cases[c] = dict(XC.CASES[c], theta_deg=[float(v) for v in th], w=[float(v) for v in w], n=len(th), a_j_m=[float(XC.A_SUM * v) for v in w],
                        table=dict(npz=rel(dr["npz"]), npz_sha256=dr["npz_sha256"], content_sha256=dr["content_sha256"]),
                        table_check=dict(path=rel(tcp), sha256=XC.sha256_file(tcp), all_ok=tc["all_ok"], focus_rel_err=tc["focus"]["rel_err_vs_theory"],
                                         band_linear_steepness=tc["band_linear_steepness"]),
                        linear_refs=dr["linear_refs"], runs=rows)
    hip_sha = GC.sha256_file(GC.HIP)
    bc = json.load(open(GC.B50 + "/_logs/build_check.json", encoding="utf8"))
    doc = dict(
        status="FROZEN", plan="E", campaign="FLIP51-E",
        title="FLIP51 plan E: T 7 s crossing screens (U7, X2, X1) at dp 1.0 and one promoted 0.5 m run, toward the user's converged-peak picture",
        tool="Tools/GWWaveGen/flip51/x51_plan.py",
        trigger=dict(
            user_2026_10_17_1710=USER_WORDS,
            reading=("the user wants the big wave's SHAPE to converge like the screenshot (one tall wave narrowing upward into a sharp peak), "
                     "accepts that pure physics may not get all the way, and asks to get as close as possible; self-checkable steps are to be "
                     "confirmed without asking"),
            target_image="Unity/Build/FLIP50/_scratch/target/user_target_20261017.jpg (git-ignored; read only; never copied, uploaded or committed)",
            target_seen=("ONE tall wave converging upward into a sharp peak: steep concave face with streaks converging toward the top, a spray plume at "
                         "the summit, height large against its base width, the surrounding sea much lower; the curl is at the very top")),
        physics_rules=dict(
            forces="gravity, the seabed and the incoming waves only; no force toward a shape; currents or wind only with a real cause (none here)",
            Q39="height must come from physical focusing / shoaling, not from input enlargement: a_sum is the DM1A input sum (not enlarged); gains "
                "are reported over each component and over the incoming crest",
            Q52="periodic recurrence: a monochromatic directional sea puts one focused crest on the hot spot every T = 7 s (fixed hot spot)",
            Q54_honesty="chosen at the inlet: period, directions and weights, a_sum, focus point and time; computed: shoaling, refraction, "
                        "focusing, breaking and any jet"),
        ranking_summary=("1 X2 isolated hybrid crossing (deliverable candidate), 2 X1 pure crossing (bracket, jet chance; lattice risk), "
                         "3 DFG-2 multi-frequency crossing (best on paper, 5-9 h engineering: the follow-up), 4 U7 (one-change control, T 7 pipeline "
                         "check), 5 DFG-1 (dominated by X), 6 seabed lenses (dropped: cannot beat DF1A; 0.5 m infeasible)"),
        mechanism_screens=dict(
            dfg="Tools/GWWaveGen/flip51/dfg51_screen.py, dfg51_v1cal.py -> Unity/Build/FLIP51/screens/dfg51 (numpy; 2nd order; FLIP45 V1 calibration)",
            crossing="Tools/GWWaveGen/flip51/cross/* -> Unity/Build/FLIP51/cross (screen_A-E, predict, predict_X2, jet_requirement, v1_e51)",
            lens="Tools/GWWaveGen/flip51/lens/* -> Unity/Build/FLIP51/lens (mild-slope solver; verdict: no 0.5 m run for this family)"),
        setups=dict(
            common=dict(
                tank="D19B half tank (mirror y = 0): Lx 412 m, W 140 m, h0 19 m flat, toe 160.25 m, straight 1:10 beach (shoreline 350.25 m)",
                solver="dp 1.0 screens / 0.5 promoted; gridscale 2, cfl 1, pcfl 0.75, minsub 1, maxsub 8",
                bands="inlet x 0-100 m (relax_g 1, wall taper 20 m, in_gain 1); side band y 95-140 m (sd_gen 180.25, sd_sw 210.25, sigma 1.41, pow 2, "
                      "taper 11.25, gain 1); ret_on 1; dir_on 1, dir_tf 0; drift stage A (AM-D18) vol_x 110-400 m; no absorber; gravity only",
                sea=dict(T_s=XC.T7, ramp_s=XC.RAMP7, a_sum_m=XC.A_SUM, a_sum_rule="= DM1A input sum [chosen]; not enlarged",
                         focus=[XC.X_F, 0.0], focus_time="t = 7n s (phases 0 at the focus)"),
                t_end_s=XC.T_END, frames=GC.frames_for(0.0, XC.T_END),
                records="hf, r2, r3 every frame; r4 every 3rd frame in 35-75 s; r5 (surface meshes) only at dp 0.5 (35-75 s every 3rd frame)",
                hip=dict(path="Houdini/FLIP50/g50_tank.hiplc", sha256=hip_sha, build_check="Unity/Build/FLIP50/_logs/build_check.json",
                         build_check_sha256=GC.sha256_file(GC.B50 + "/_logs/build_check.json"), build_check_all_ok=bc.get("all_ok"),
                         new_hip="NOT needed: the FLIP50 option-D hip is used unchanged (read only): its band VEX reads the table fields, omega and "
                                 "T from the npz (CTRL dir_npz) and the ramp from CTRL ramp_s, so a T 7 table with any direction set runs through it. "
                                 "No build step; g50_chain's start gate checks this build_check and hip sha."),
                pipeline="Tools/GWWaveGen/flip50/g50_chain.py + g50_run.py unchanged (read only), cfg out_root = absolute FLIP51 folder",
                one_change="each cfg differs from DM1A (dp 0.5) / SMOKE50DA (dp 1.0) only by the table (T 7, direction set), ramp_s 24 -> 14, t_end, "
                           "records (x51_pcfg diff, in each cfg precheck)"),
            cases=cases,
            order=list(XC.ORDER)),
        metrics=dict(
            ruler="Tools/GWWaveGen/flip51/e51_metrics.py (frozen target metrics; unchanged)", ruler_sha256=XC.sha256_file(XC.TOOLS51 + "/e51_metrics.py"),
            ruler_note="Unity/Build/FLIP51/target/baseline.json records tool sha 68e7372c... (written before the amendment texts of the same file); "
                       "the core ruler used here is the file with sha 91a2f041...",
            target_frozen="Unity/Build/FLIP51/target/target_frozen.json", target_frozen_sha256=XC.sha256_file(XC.B51 + "/target/target_frozen.json"),
            baseline="Unity/Build/FLIP51/target/baseline.json", baseline_sha256=XC.sha256_file(XC.B51 + "/target/baseline.json"),
            e51_frozen=EM.FROZEN, target=EM.TARGET, core=EM.FROZEN["core"],
            still_level=("eta0 = the run's online still offset (run record info.still_offset_online: median top-surface height over x 110-340 m at "
                         "t 0.5-1.5 s); every height is above it"),
            per_period_scan=dict(XA.SCAN, rule=("periods n = 6-10, windows [7n - 3.5, 7n + 3.5) s; 'max' frame = largest Hc of the 3x3-median hf - eta0 "
                                                "over x 150-300 m and the interior |y| <= 95 m; e51 hf_metrics on that frame with rows y > 95 m set to "
                                                "NaN and xwin (150, 300); medians over the complete periods (>= 4); edge guard: if >= 2 window maxima "
                                                "lie within 0.25 s of an edge, all windows shift by +3.5 s (reported)")),
            N1=dict(XA.N1DEF, rule=("highest local maximum (15 m x 15 m max filter, half width floor(7.5 m / grid) cells) of the mirrored 3x3-median "
                                    "hf - eta0 in x 110-340 m, |y| <= 90 m, r <= 100 m from the summit, outside r < 4 Hc of the summit and of its "
                                    "mirror (x_pk, -y_pk), / Hc; 0 if none; median over the periods")),
            score="core target miss (e51 score_vs_target over W50, W80, W95, K, S2) at the 'max' instant, median over the periods"),
        criteria=dict(
            A_validity=dict(
                G1=dict(rule="table numpy check before launch: focus vs theory < 1 %, symmetry, continuity, interpolation, vertical profile, "
                             "return current, symmetric set (x51_table check)", status={c: cases[c]["table_check"]["all_ok"] for c in XC.ORDER}),
                G2=dict(rule="median zero-down crest (above eta0) of the gauge x 110 m, y 0.5 m over t 30-75 s / the table's linear |A| there",
                        range_1p0=XA.GATES["G2_ratio_1p0"], range_0p5=XA.GATES["G2_ratio_0p5"],
                        reason="FLIP45 S10b at 1.0 m, T 7: 0.80-0.88 [measured, as reported]; upper bound allows the 2nd-order crest excess "
                               "(computed at this gauge: U7 1.10, X2 1.03, X1 1.07 of linear)"),
                G3=dict(rule="period summits spaced 7.0 +- 0.5 s for >= 4 consecutive summits (>= 3 consecutive spacings), summit x spread "
                             "(max - min over the complete periods) <= 20 m", reason="D runs held 11.3-12.6 s at T 12 (~+-7 %); accepted D spreads "
                                                                                     "12 m (DM1A), 18 m (DF1A) [measured]"),
                G4=dict(rule="no band breaking: k(h(x)) x (3x3-median hf - eta0) <= 0.40 over t 30-75 s in the inlet band (x < 100 m, all y) and "
                             "the generating side band (y >= 95 m, x <= 180.25 m); no overturning lip on r2 (y 0.5 m) at x < 100 m (a water run "
                             "above an air gap whose bottom is > 0.5 m above still, in >= 2 adjacent columns). The side band has no section "
                             "record: only the steepness reads it", kA_max=XA.GATES["G4_kA_max"],
                        reason="X1 side band linear kA 0.33 [computed]; 2D Stokes limit ~0.42-0.44 at kh 1.2-1.75"),
                G5=dict(rule="the D hard health item for stage A (AM-D18): max |V/V0 - 1| of the measured whole-tank column volume after 1.5 s "
                             "<= 2 %", max=XA.GATES["G5_volume_max"]),
                G6=dict(rule="every period summit x in 160-300 m and Hc >= 0.68 x the central prediction (U7 6.5, X2 6.0, X1 6.1 m)",
                        floors_m={c: round(XA.GATES["G6_Hc_frac"] * XC.CASES[c]["Hc_pred_central"], 3) for c in XC.ORDER},
                        reason="fH low end 0.77 x the 1.0 m crest ratio 0.88"),
                also="run complete (f_end reached) and >= 4 complete periods",
                failure_class="pipeline = run incomplete, G1, G2, fewer than 4 periods (may be fixed and rerun once, same setup name, by the main "
                              "session); physics = G3, G4, G5, G6 (ends that screen)"),
            B_eligibility=dict(
                E1=dict(rule="N1 median <= 0.65", max=XA.ELIG["N1_max"],
                        calibration={k: v["range"] for k, v in cal["N1"].items()},
                        reason="above every measured single focus by >= 0.14 (max 0.51, DA3); below the X1 lattice prediction 0.69-0.92 and the "
                               "picture's highest neighbour ~0.7"),
                E2=dict(rule="X: median Hc >= 0.85 x median Hc(U7), both 1.0 m (if U7 is not valid: 0.85 x 6.5 x 0.94 m); 0.5 m: Hc >= 5.0 m",
                        Hc_vs_U7=XA.ELIG["Hc_vs_U7"], U7_fallback_m=XA.ELIG["U7_Hc_fallback_1p0"], Hc_0p5_min=XA.ELIG["Hc_0p5_min"]),
                E3=dict(rule="focusing gain: median Hc / median over the periods of the LARGEST incoming crest on the line x 110 m (|y| <= 95 m) "
                             "in the window >= 1.8", min=XA.ELIG["gain_min"],
                        reason="at least DM1A's c0/c_in 1.97 minus the noise (the per-period scan reads DM1A at 1.95 [measured, test on DM1A]); "
                               "the strictest incoming crest (the cross screen's c_in_x110), so the height must come from focusing"),
                reports="Hc / a_j max and Hc / the linear design crest |A(x_f, 0)| (U7 5.714, X2 5.406, X1 5.478 m), ungated"),
            C_ranking=dict(score="median core miss", bars=XA.BARS,
                           bar_derivation="absolute = DF1A 0.5 m 'max' median 3.3 - 0.5 (~2 SE of a 4-5 period median difference) - 0.05 (the measured "
                                          "1.0 m reading bias at T 12 with the online eta0) = 2.75; relative <= -0.50 vs U7 (cancels the unknown T 7 "
                                          "resolution bias); tie band 0.30 (~1.2 SE)",
                           report_only="W(f), taper, S1, ring, Lx50, A50, face/concavity/overhang/back (r2), tbest (optimistic), the D smoke analysis"),
            D_judgement_0p5=dict(
                instants="g50 events (g49 find_breakers, centre overturning onsets) where they fall in a period window: the e51 'max' instant of "
                         "that onset (argmax Hc in [on_f - 3 s, on_f + 1.5 s], summit in x on_x - 60 .. + 35 m); otherwise the per-period scan",
                valid="G2 (0.90-1.12), G3, G4, G5, G6 and E2 (Hc >= 5.0 m)",
                outcomes=dict(NEW_BEST_SHAPE="median core miss <= 2.8 AND N1 <= 0.65 AND E3 >= 1.8 -> replaces DF1A as the shape reference; mp4; "
                                             "shown to the user with gains over every component",
                              TARGET_BAND="median miss <= 0.5",
                              JET_REGIME_SEEN="Hc / linear design crest >= 1.30 -> refine within crossing (angle, sigma) and start DFG-2",
                              NO_GAIN="miss > 2.8, or ratio < 1.10 with W50/Hc >= 3.3 -> report honestly; next DFG-2 or the Froude-scaled tank "
                                      "(the user's choice)"),
                numbers=XA.OUT05),
            watch_items="face regression (crossing fronts 30-60 deg vs 95-110 in D; the top may become a vertical spout); back angle (20-30 deg "
                        "predicted); absolute height Hc ~6 m (shape first, 10/13; size later by Froude scaling the whole sea)"),
        promote_rule=dict(
            frozen_before_any_screen=True, automatic=True,
            step1_validity="a screen counts only if it passes G1-G6 (+ run complete, >= 4 periods); a pipeline failure may be fixed and rerun once "
                           "(same setup name) by the main session; a physics failure ends that screen; if U7 fails a physics gate X2 and X1 still "
                           "run and only the absolute bar applies",
            step2_eligibility="E1 (N1 <= 0.65), E2 (X: Hc >= 0.85 Hc(U7)) and E3 (gain >= 1.8)",
            step3_promotable="eligible AND (median miss <= 2.75 at 1.0 m OR miss(screen) - miss(U7) <= -0.50); U7 only by the absolute bar",
            step4_choice="the promotable screen with the lowest median miss; ties within 0.30 -> order X2, X1, U7. The promoted run = the same setup "
                         "at dp 0.5 m, t 0-75 s, r5 from 35 s every 3rd frame; launched at once (one simulation at a time)",
            step5_nothing="jet-probe exception: X1 valid, miss(X1) - miss(U7) <= -0.80, fails only E1 -> X1 at 0.5 m labelled 'mechanism probe, not "
                          "a deliverable' (N1 re-judged at 0.5 m). Otherwise no 0.5 m run tonight; report that the direction set does not narrow "
                          "the crest in FLIP at T 7 (numbers), DFG-2 next day",
            second_slot="the runner-up follows at 0.5 m only if it is also promotable",
            numbers=dict(BARS=XA.BARS, ELIG=XA.ELIG)),
        pre_freeze_corrections=[
            dict(item="still level at dp 1.0", what=("the plan draft's 1.0/0.5 bias (miss -0.14, Hc 1.005) was measured with eta0 = 0 for the 1.0 m "
                                                     "run; the 1.0 m top surface reads still water +0.483 m (SMOKE50DA frames 2-49; frame 1 is the "
                                                     "initial state) [measured]. With each run's online offset: miss -0.05 (IQR -0.38..+0.14), Hc 0.94, "
                                                     "W50 1.04, W80 0.94, W95 0.94, K 1.11, S2 0.99, ring 0.97 (n 44) [measured]"),
                 consequence="eta0 = online offset everywhere; absolute bar by the draft's own formula 3.3 - 0.5 - 0.05 = 2.75 (draft 2.65)"),
            dict(item="incoming crest for E3", what=("at x 110 m the axis point is a cold spot of the crossing pattern (linear |A(110, 0)|: X2 1.05 m "
                                                     "against 2.01 m at the line maximum; U7 2.23, X1 2.28) [computed]; 'Hc / incoming axis crest' at "
                                                     "the gauge would inflate X2's gain ~2x"),
                 consequence="E3 uses the largest incoming crest on the whole line x 110 m (|y| <= 95 m) per period = the cross screen's c_in_x110, "
                             "which the registered gain predictions (X2 2.2-2.8, X1 1.9-2.3) used; the axis-gauge ratio is reported"),
            dict(item="eligibility list", what="promote_rule step 2 named E1 and E2; criteria B lists E1-E3",
                 consequence="the union (E1, E2, E3) is required (stricter; the 0.5 m NEW BEST SHAPE also needs E3)"),
            dict(item="summit region", what="the side band y 95-140 m generates/absorbs waves and is not the judged wave",
                 consequence="summit search and hf_metrics use the interior |y| <= 95 m (rows beyond are NaN); widths are unaffected unless a "
                             "crest run reaches |y| = 95 m (W >= 190 m)"),
            dict(item="G3 wording", what="'7.0 +- 0.5 s for at least 4 consecutive periods'",
                 consequence=">= 4 consecutive period summits (>= 3 consecutive spacings) within 7.0 +- 0.5 s"),
            dict(item="window edges", what="a period maximum at a window edge could flip to the next window",
                 consequence="edge guard (>= 2 maxima within 0.25 s of an edge -> all windows +3.5 s), reported")],
        calibration=dict(path=rel(CALIB), sha256=XC.sha256_file(CALIB), bias_T12=cal["bias_T12"], N1={k: v["range"] for k, v in cal["N1"].items()},
                         analysis_test=("the per-period scan on DM1A (T 12 test windows n 3-7, scratchpad only) gave miss 4.69, Hc 7.79 m, W50 9.08, "
                                        "N1 0.19, gain 1.95 (D measure c0/c_in 1.97) [measured]")),
        honesty=dict(
            chosen_at_inlet="period T 7 s, the direction set and weights, a_sum 6.331240 m (= DM1A input sum), focus point (220.25, 0) and "
                            "time t = 7n s; the D19B bed",
            computed_by_FLIP="shoaling, refraction, focusing, the crest's growth, breaking, any jet / plume",
            gains_reported="Hc / largest incoming crest at x 110 m (E3), Hc / largest a_j, Hc / linear design crest, Hc / axis gauge crest",
            not_done="no input enlargement, no force toward a shape, no wind or current; the target picture is used only through the frozen "
                     "e51 read values; nothing committed; README / Docs not edited"),
        registered_predictions=dict(
            pre_jet_0p5={c: dict(Hc=XC.CASES[c]["Hc_pred_range"], miss=XC.CASES[c]["miss_pred_range"], miss_central=XC.CASES[c]["miss_pred_central"],
                                 W50=XC.CASES[c]["W50_pred"]) for c in XC.ORDER},
            expected_1p0="1.0 m reads miss ~0.05 lower than 0.5 m at T 12 (online eta0) [measured]; unverified at T 7 (FLIP45 S10b: 1.0 m crest "
                         "0.83-0.88 of 0.5 m)",
            gains="Hc / incoming crest: U7 ~2.65, X2 2.5 (2.2-2.8), X1 2.1 (1.9-2.3); Hc / a_j max ~21-31 [computed]",
            with_jet="J 1.4: X1 miss 0.10, X2 0.24 [guess, geometric jet model]; J <= 1.1 stays near the pre-jet values"),
        compute=dict(
            screens="dp 1.0, 1801 frames, ~13-16 min wall each (SMOKE50DA 1201 frames in 582 s, substeps 1) [measured rate]; RSS ~5.4-5.7 GB",
            promoted="dp 0.5, 1801 frames, 1.7-2.2 h estimated (x51_pcfg precheck), DM1A measured 3.58 h for 92 s; RSS 6.5-8.1 GB; max_hours 3.0 "
                     "with up to 2 resumes from the checkpoint",
            one_at_a_time="g50_chain waits for every other hython before each launch; auto_E waits for the hero re-record (DM1Ar ... c1152_t138_long) "
                          "to complete and for no hython"),
        automation=dict(script=AUTO, status="Unity/Build/FLIP51/_logs/auto_E_status.txt (lines '<date> <time> E <msg>')",
                        flow="wait hero complete + no hython -> verify plan/code/cfg shas and the dry chain gate -> U7, X2, X1 at 1.0 m (chain, "
                             "x51_ana screen, x51_video) -> x51_ana decide (this rule) -> promoted 0.5 m chain -> x51_ana judge05 + video -> "
                             "runner-up only if promotable",
                        stop_file="Unity/Build/FLIP51/_logs/auto_E_STOP (checked before every launch)"),
        risks=["the jet is the only path into the target band and its height (J) is unknown; at 1.0 m (Hc ~ 3 cells of 2 m) no jet can show",
               "X1 is a lattice by construction (6 neighbours 0.69-0.92 Hc at 50-90 m): E1 will probably fail it",
               "T 7 at 1.0 m is under-resolved (crest 12-17 % low at T 7 in FLIP45 S10b); the relative bar vs U7 cancels part of it",
               "crossing fronts are gentle (30-60 deg): the top may become a vertical spout, not a forward curl",
               "the side band reaches linear kA 0.33 for X1 (G4 watches it)",
               "the 1.0/0.5 bias is measured at T 12 only"],
        implementation=dict(code_sha256={k: XC.sha256_file(v) for k, v in registered_files().items()}),
    )
    return doc


def freeze(force=False, reason=None):
    os.makedirs(XC.PLAN_DIR, exist_ok=True)
    recs = e_runs_with_records()
    if os.path.exists(XC.PLAN_E):
        if recs:
            raise SystemExit("plan_E_frozen.json exists and plan E runs have records (%s): never re-frozen" % recs[:3])
        if not force or not reason:
            raise SystemExit("plan_E_frozen.json exists; re-freeze only with --force=1 --reason=... before any plan E run")
    doc = build()
    doc["frozen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if os.path.exists(XC.PLAN_E):
        old = json.load(open(XC.PLAN_E, encoding="utf8"))
        doc["refrozen"] = (old.get("refrozen") or []) + [dict(at=doc["frozen_at"], reason=reason, previous_sha256=XC.sha256_file(XC.PLAN_E))]
    XC.jdump(doc, XC.PLAN_E)
    sha = XC.sha256_file(XC.PLAN_E)
    with open(XC.PLAN_E + ".sha256", "w", encoding="utf8") as fh:
        fh.write("%s  plan_E_frozen.json\n" % sha)
    return dict(frozen=XC.PLAN_E, sha256=sha)


def verify():
    out = dict(plan=XC.PLAN_E, ok=False, bad=[])
    if not (os.path.exists(XC.PLAN_E) and os.path.exists(XC.PLAN_E + ".sha256")):
        out["bad"].append("plan or .sha256 missing"); return out
    if open(XC.PLAN_E + ".sha256", encoding="utf8").read().split()[0] != XC.sha256_file(XC.PLAN_E):
        out["bad"].append("plan sha256 differs from .sha256")
    d = json.load(open(XC.PLAN_E, encoding="utf8"))
    files = registered_files()
    for k, sh in (d.get("implementation") or {}).get("code_sha256", {}).items():
        p = files.get(k)
        if p is None or not os.path.exists(p) or XC.sha256_file(p) != sh:
            out["bad"].append("code changed: %s" % k)
    for c, cs in ((d.get("setups") or {}).get("cases") or {}).items():
        for dpk, r in cs["runs"].items():
            p = os.path.join(XC.REPO, r["cfg"])
            if not os.path.exists(p) or XC.sha256_file(p) != r["cfg_sha256"]:
                out["bad"].append("cfg changed or missing: %s" % r["cfg"])
        tp = os.path.join(XC.REPO, cs["table"]["npz"])
        if not os.path.exists(tp) or XC.sha256_file(tp) != cs["table"]["npz_sha256"]:
            out["bad"].append("table changed or missing: %s" % cs["table"]["npz"])
    h = (d.get("setups") or {}).get("common", {}).get("hip") or {}
    if h.get("sha256") != GC.sha256_file(GC.HIP):
        out["bad"].append("hip sha differs from the plan")
    out["ok"] = not out["bad"]
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
    if a[0] == "calib":
        d = XA.calib()
        XC.jdump(d, CALIB)
        print(json.dumps(XC.clean(dict(written=CALIB, miss_bias=d["bias_T12"]["miss_diff_1p0_minus_0p5"], N1={k: v["range"] for k, v in d["N1"].items()})),
                         ensure_ascii=False))
    elif a[0] == "freeze":
        print(json.dumps(freeze(bool(opt.get("force")), opt.get("reason")), ensure_ascii=False))
    elif a[0] == "verify":
        v = verify()
        print(json.dumps(v, ensure_ascii=False))
        sys.exit(0 if v["ok"] else 1)
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
