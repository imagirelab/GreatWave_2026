# -*- coding: utf-8 -*-
"""FLIP50 (option D): write the frozen-plan DRAFT Unity/Build/FLIP50/plan/plan_D_draft.json (py -3.10 -B). 2026-10-15 written new (Claude).
Source: the design step's draft Tools/GWWaveGen/flip50/plan_D_draft.json (read only; criteria were copied there unchanged from
Unity/Build/FLIP49/plan/plan_A_frozen.json). This tool keeps design, criteria, decision rules, registered predictions and honesty, and adds:
  - implementation (files with sha256-16, scene, build check, tables with sha256, cfg ids, commands, numpy check summary)
  - amendments_vs_design_draft (implementation choices made while coding, each with its reason and tag; no threshold is changed)
  - the updated cost (DA1 launch 2 measured 3.79 s/frame) and record windows.
  - review_pre_freeze (2026-10-15 adversarial review): the open decisions RV-D1..D4 (end-wall run-up, H_volume under stage C, H_wall,
    rule precedence) with their evidence, and the computed physics numbers (focal zone, widths, reflection). Nothing is decided here.
2026-10-16 freeze step (campaign B findings, the main session's brief): freeze_step() adds the campaign-B criteria (targets_D, q73_vs_DA3,
  DA3_reference), the q-profile design check (design_review_B: design numbers kept), the frozen smoke gates, the pass/partial/fail decision
  rules with the partial mapping, the RV-D1..D4 resolutions, honesty and registered expectations (AM-D9..AM-D15, AM-D17).
The orchestrator freezes it (sha256) with `py -3.10 -B g50_pcfg.py freezeD` (the hython build check x50_build.py stays a launch gate of
g50_chain.py). Nothing here runs Houdini.
usage: py -3.10 -B g50_planD.py   (needs `g50_pcfg.py check` first: reads plan/precheck_D.json)
"""
import os, sys, json, copy, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g50_common as GC     # noqa: E402
import g50_pcfg as PC       # noqa: E402


# ====================================================================== 2026-10-16 freeze step (campaign B findings; the main session's brief)
PLAN_B2 = GC.REPO + "/Unity/Build/FLIP49/plan/plan_B2_frozen.json"
DA3_PANA = GC.REPO + "/Unity/Build/FLIP49/runs/DA3_SC37y30_T12H7p5_dp0p5/pana/periodic_ana.json"
VAL_DA3 = GC.PLAN_DIR + "/validation_DA3/planD_ana.json"


def _da3_periodic():
    """DA3 narrow/periodic medians over k2-k9 (FLIP49 periodic_ana.json, read only) [measured]."""
    import numpy as np
    pa = json.load(open(DA3_PANA, encoding="utf8"))
    ws = [w for w in pa["waves"] if w.get("t_on") is not None and w["t_on"] >= 45.0]

    def med(k):
        v = [w[k] for w in ws if w.get(k) is not None]
        return float(np.median(v)) if v else None

    def rng(k):
        v = [w[k] for w in ws if w.get(k) is not None]
        return [float(min(v)), float(max(v))] if v else None
    x = np.array([w["x_on"] for w in ws], float); hc = np.array([w["Hc"] for w in ws], float)
    return dict(source="Unity/Build/FLIP49/runs/DA3_SC37y30_T12H7p5_dp0p5/pana/periodic_ana.json", sha256_16=GC.sha256_file(DA3_PANA)[:16],
                ks=[w["k"] for w in ws], c0_over_c_side=med("ratio_side"), c0_over_c_side_range=rng("ratio_side"), c0_over_c4Hc=med("ratio_4Hc"),
                curl_w_maxov_over_Hc=med("w_maxov_over_Hc"), curl_w_maxov_range=rng("w_maxov_over_Hc"), curl_w_td_over_Hc=med("w_td_over_Hc"),
                curl_w_td_range=rng("w_td_over_Hc"), onset_x_range=rng("x_on"), onset_x_max_dev_m=float(np.max(np.abs(x - np.median(x)))),
                Hc_cv=float(hc.std() / hc.mean()), n=len(ws), PERIODIC_k=(pa.get("periodic_A") or {}).get("PERIODIC_k"), tag="measured (FLIP DA3)")


def freeze_step(P, pre):
    """apply the freeze-step changes (AM-D9..AM-D17) to the plan P. Nothing loosens a threshold that a run has been judged against: no
    FLIP50 0.5 m run exists. Reasons and tags inline."""
    b2 = json.load(open(PLAN_B2, encoding="utf8"))
    fc2 = b2["frozen_criteria"]
    qp = pre["q_profile"]
    q1 = qp["DM1"]

    def qrow(h):
        r = min(q1["rows"], key=lambda r: abs(r["h"] - h))
        return dict(x=round(r["x"], 2), h=round(r["h"], 2), A=round(r["A"], 3), H_lin=round(r["H_lin"], 2), Hmax=round(r["Hmax"], 2),
                    q_linear=round(r["q"]["linear"], 3), q_flip49=round(r["q"]["flip49_damping"], 3), q_v1=round(r["q"]["v1_calibrated"], 3))
    P["status"] = ("DRAFT for freezing (2026-10-16 freeze step): campaign-B criteria, smoke gates and pass/partial/fail rules added; design numbers "
                   "unchanged after the q-profile check; numpy checks pass (plan/precheck_D.json). The hython build check (x50_build.py -> "
                   "_logs/build_check.json all_ok) is still pending (no Houdini may run in the freeze step); g50_chain.py refuses every launch "
                   "until it passes")
    P["freeze_step"] = dict(
        date="2026-10-16", by="Claude (freeze subagent of the main session); no Houdini run, nothing committed",
        brief="computed task text from the main session's workflow: the USER chose option D on 2026-10-16 after campaign B rounds 1-2 failed "
              "to steepen the back (as relayed in that brief; the user's own words are recorded by the main session in Docs/Workflow, not here)",
        changed=["AM-D9 criteria (campaign B targets, Q77 height, Q73 vs DA3, DA3 reference)", "AM-D10 smoke 0-50 s + frozen smoke gates",
                 "AM-D11 health (onset h_b > 14 m no longer 'diagnose first'; hard/soft; volume soft band; H_wall 3.0 h)",
                 "AM-D12 decision rules pass/partial/fail with precedence and the frozen next-change mapping",
                 "AM-D13 analysis: campaign-B per-breaker numbers, q track, focusing gain, end-wall report, D verdict in g50_ana",
                 "AM-D14 design kept after the q-profile check (x_f, a_sum, T, theta, bed, Lx unchanged)", "AM-D15 S2D strips out of the queue",
                 "AM-D17 freezeD refuses a stale draft"])
    P["user_and_supervisor_rules"] = dict(
        Q39="the wave becomes tall by real physics (focusing, shoaling), never by enlarging the input; numbers come with reasons",
        Q41_Q54="only gravity, the bed and the incoming waves act; the bands relax horizontal velocity only; no force toward a shape",
        Q52=P.get("supervisor_Q52", "") + "（大波が定期的に現れる状態 → PERIODIC）",
        Q73="rounds by frozen rules, video + numbers each round, continue without waiting; stop and ask when the same direction does not improve "
            "for 2 consecutive rounds",
        Q76="the user's two biggest gaps: the body is too long and gentle (back 0.7-0.9 eta_c, width07) and the wave is not tall enough",
        Q77="height is compared crest-to-trough like Cartwright & Nakamura (2009) 10-12 m: criterion crest-to-front-trough >= 10 m; Hc reported only",
        option_D="user decision 2026-10-16 (as relayed by the main session's brief): directional focusing on a straight 1:10 slope")
    P["campaignB_findings"] = [
        dict(what="the back angle (0.7-0.9 eta_c) of the DA breakers is ~8-10 deg and is inherited from the low q = H/Hmax (0.59-0.64) of the "
                  "incoming swell; DA3 focuses only in the last 2 s (h 11 -> 8.2 m), so the crest gets higher, not sharper", tag="measured / computed"),
        dict(what="steady waves: back and width07 depend almost only on q: q 0.6 -> 10.5 deg / 4.6; 0.9 -> 23 deg / 1.9; 0.975 -> 31.3 deg / 1.34 "
                  "(the print's two numbers); back 25 deg <-> q 0.922", tag="computed (Fenton)"),
        dict(what="3D side-feeding over the DA3 spur-channel bed halves the 2D back (S0 2D onset 15.9 deg vs DA3 8.2 deg)", tag="measured; cause read"),
        dict(what="raising the incoming crest (S1, realized q 0.80) did not steepen the onset back (15.3 vs 15.9 deg); best-frame width07 2.07 vs 2.56",
             tag="measured"),
        dict(what="a steep ledge made it worse: an early low wide breaker (S2 best back 4.3 deg, width07 4.03, crest-to-front-trough 3.45 m)", tag="measured"),
        dict(what="the steepest backs measured so far are focus-limited breakers on a flat bed (FLIP45 V1, FLIP42, Fochesato BEM): back 20-25 deg, "
                  "width07 ~1.1, but their front chord only 17-26 deg; the print has both a sharp crest and a steep front", tag="measured / literature"),
        dict(what="the 1:10 slope steepens the front in 2D (P1c chord 62.9-68 deg) while its onset back stays 13-20 deg", tag="measured")]
    # ---- the q-profile design check (AM-D14) -----------------------------------------------------------------------------------------------------
    P["design_review_B"] = dict(
        question="is the focused crest near-limiting (q >= ~0.9) while still in ~13-15 m, before the 1:10 slope triggers the break (brief, campaign B)?",
        method="linear axis amplitude |A(x, 0)| of the DM1 table code (WKB), steady limit Hmax(h, 12 s) of the Fenton fit (campaign B's q), "
               "q = f 2|A| / Hmax with three realization factors f (g50_pcfg.axis_q_profile; numbers in plan/precheck_D.json q_profile)",
        factors=qp["DM1"]["factors"],
        factor_sources=dict(linear="1.0", flip49_damping="FLIP49 dp 0.5 propagation loss -4.8 % per 50 m [measured] over ~140 m from the bands",
                            v1_calibrated="FLIP45 V1 (dp 0.5, directional focus): crest-to-rear-trough 9.45 m / linear 2|A| 12.58 m = 0.75 [measured]"),
        rows_DM1=[qrow(h) for h in (19.0, 18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0)],
        crossings_DM1=q1["crossings"], crossings_DF1=qp["DF1"]["crossings"],
        axis_gain=dict(flat_x100_to_toe=q1["axis_gain_flat_x100_to_toe"], toe_to_focus=q1["axis_gain_toe_to_focus"],
                       plateau_99pct_x=q1["plateau_99pct_x"],
                       note="most of the convergence happens on the flat; beyond x_f the axis |A| stays within 1 % to x ~280 m because shoaling and "
                            "refraction balance the defocusing: the focus is a phase-lock point and the axis 'hot zone' is a plateau (the lateral contrast "
                            "|A(x,0)| / |A(x, |y| 70-84)| does peak at x 220-230 m, 5.1)"),
        focus_shift_check="moving x_f by +-20 m (same a_sum) changes the axis |A| at h 13-15 m by <= 3 % but at the toe by -9..+9 % (q_lin at the "
                          "toe 0.76-0.91): x_f mainly sets the risk of breaking on the flat, not the q at 13-15 m [computed, freeze step]",
        result=("q >= 0.9 is first reached at h %.1f / %.1f / %.1f m and q >= 1.0 at h %.1f / %.1f / %.1f m (linear / FLIP49-damped / V1-calibrated); "
                "the linear depth-limited break target stays h 11.03 m (x 240.25, gamma_b 1.081)") % (
                   q1["crossings"]["linear"]["h_q0.9"], q1["crossings"]["flip49_damping"]["h_q0.9"], q1["crossings"]["v1_calibrated"]["h_q0.9"],
                   q1["crossings"]["linear"]["h_q1.0"], q1["crossings"]["flip49_damping"]["h_q1.0"], q1["crossings"]["v1_calibrated"]["h_q1.0"]),
        decision="keep x_f 220.25 m, a_sum 6.331 m (DM1), T 12 s, +-80 deg, h0 19 m, 1:10, Lx 412 m [chosen]: the crest becomes near-limiting "
                 "(q 0.9 -> 1.0) between h 16.3 and 14.8 m by the middle (FLIP49-damped) estimate (18.2 -> 16.8 m linear, 14.2 -> 12.6 m V1-calibrated), "
                 "i.e. in the 13-15 m band the brief asks for within the estimates' spread, and the linear depth-limited trigger follows on the slope "
                 "(h 11 m, ~1.6 s after the focus instant); a +-20 m focus shift barely moves q at 13-15 m, and raising a_sum would enlarge the "
                 "input (excluded, Q39)",
        consequences=["health: an onset on the slope at h_b > 14 m is the focus-limited regime campaign B points to -> no longer 'diagnose first' (AM-D11); "
                      "only an onset on the flat (x < 160.25 m) in >= 2 judged periods stays a hard health failure",
                      "analysis: the per-breaker q track (H_rear / Hmax(h)) measures whether the crest really was near-limiting at 13-15 m (AM-D13)"],
        caveats=["Hmax is the 2D steady limit: a short-crested focused crest and a shoaling crest can exceed q = 1 (P1c onsets at q_loc 1.5-1.7) [measured]",
                 "the realization factors come from other runs (FLIP49 swell, FLIP45 V1 at T 7 s) [measured elsewhere -> guess here]",
                 "campaign B also found that the 1:10 slope brings the 2D onset back to ~15-16 deg whatever the incoming q (S0/S1): D may still give a "
                 "2D-slope-like back unless the break is focus-limited [measured -> guess for D]"],
        tags=dict(numbers="computed", decision="chosen"))
    # ---- criteria (AM-D9, AM-D11) ---------------------------------------------------------------------------------------------------------------------
    C = P["criteria"]
    C["source"] = ("P1-P5 and PERIODIC thresholds copied unchanged from plan_A_frozen.json (via the 2026-10-15 draft; P1/P4a x limit 330 m and the crest "
                   "window wavelength move with the D layout). Added at the freeze step (2026-10-16): targets_D (campaign B: back >= 25 deg, width07 <= 1.6, "
                   "lip >= 0.2; Q77: crest-to-front-trough >= 10 m, Hc reported), q73_vs_DA3 with the DA3 reference, the campaign-B definitions, verdict_D. "
                   "Health: H_wall 3.0 h, volume hard/soft band, diagnose-first list revised (AM-D11). Nothing is loosened after a result: no FLIP50 0.5 m run exists")
    C["targets_D"] = dict(H_front_min_m=10.0, back_best_deg_min=25.0, width07_best_max=1.6, lip_min=0.2, Hc="reported only (Q77)",
                          rule="medians over the judged breakers (centre onset t >= 45 s), never best frames alone",
                          why=dict(H_front="Q77: crest-to-trough 10-12 m (Cartwright & Nakamura 2009); DA3 10.5-11.4 m",
                                   back_best="campaign B: back 25 deg <-> steady q 0.922; print 31.3 deg (29-38)",
                                   width07_best="campaign B: print 1.32 (1.02-1.42); 1.6 = steady q ~0.93",
                                   lip="P5 lip (plunging, not spilling); print 0.35"),
                          tag="chosen (frozen before any D run)")
    C["q73_vs_DA3"] = dict(improvement_any=dict(back_best_deg=3.0, width07_best=-0.3), nothing_worse=dict(back_deg=-2.0, width07=0.2, H_front_m=-0.5),
                           rule="medians over judged breakers vs the DA3 medians (k2-k9): improvement = best-frame back >= +3 deg OR best-frame width07 "
                                "<= -0.3, AND nothing worse than back -2 deg, width07 +0.2, crest-to-front-trough -0.5 m (ruler noise at 0.5 m particles)",
                           height_only="a height gain alone is not an improvement in this direction (Q77: DA3 already reaches 10.5-11.4 m)",
                           tag="chosen (the campaign-B2 Q73 test, unchanged)")
    ref = dict(fc2["DA3_reference"])
    ref["copied_from"] = dict(path="Unity/Build/FLIP49/plan/plan_B2_frozen.json frozen_criteria.DA3_reference", sha256=GC.sha256_file(PLAN_B2))
    ref["periodic_narrow"] = _da3_periodic()
    if os.path.exists(VAL_DA3):
        # the D analysis code run on the DA3 records at the freeze step (validation, read only): the campaign-B medians must come back unchanged
        v = json.load(open(VAL_DA3, encoding="utf8"))
        vm = v["medians_judged"]
        pairs = dict(back_on=("back_on", "back_on_deg"), back_best=("back_best", "back_best_deg"), w07_on=("w07_on", "width07_on"),
                     w07_best=("w07_best", "width07_best"), H_front=("H_front", "H_front_m"), Hc=("Hc", "Hc_m"), h_b=("h_b", "h_b_m"))
        diffs = {k: (vm[a] - ref[b]) if (vm.get(a) is not None and ref.get(b) is not None) else None for k, (a, b) in pairs.items()}
        ref["q_track_same_code"] = dict(source="Unity/Build/FLIP50/plan/validation_DA3/planD_ana.json", sha256_16=GC.sha256_file(VAL_DA3)[:16],
                                        q_x160=vm.get("q_toe"), q_h15=vm.get("q_h15"), q_h13=vm.get("q_h13"), h_first_q0_9=vm.get("h_q0.9"),
                                        q_pre_max=vm.get("q_pre_max"), q_on=vm.get("q_on"),
                                        note="DA3 records read by g50_ana.plan_d_numbers at the freeze step; x 160.25 m lies on DA3's 17 m flat; q > 1 at "
                                             "onset on a slope is normal (shoaling crest; campaign B q_loc 1.33-1.64)", tag="measured")
        P["freeze_step"]["validation_DA3"] = dict(
            what="g50_ana.plan_d_numbers on the FLIP49 DA3 records (no new simulation; script plan/validation_DA3/test_planD_DA3.py)",
            medians_minus_frozen_reference=diffs, max_abs_diff=max([abs(d) for d in diffs.values() if d is not None] or [None]),
            reproduced=bool(all(d is not None and abs(d) < 1e-6 for d in diffs.values())),
            q_track_DA3=dict(h_first_q0_9=vm.get("h_q0.9"), q_h15=vm.get("q_h15"), q_h13=vm.get("q_h13")),
            reading="the reused campaign-B measure reproduces the DA3 reference medians; DA3's crest first reaches q 0.9 only at h ~10.8 m (q 0.73 at "
                    "15 m, 0.81 at 13 m), the D design estimate is h 14-18 m: DM1's h_first_q0.9 is the direct test of the campaign-B idea",
            tag="measured")
    C["DA3_reference"] = ref
    C["print_reference"] = dict(fc2["print_reference"], source="STUDY52 cn ruler (as plan_B2_frozen.json)")
    C["definitions"].update(
        judged_breaker="centre (y 0.5 m row) onset t >= 45 s (unchanged)",
        back_angle=fc2["definitions"]["back_angle"].replace("depth >= 16.5 m", "depth >= 16.5 m (D: x <= 185.25 m, the flat 19 m and the lower slope)"),
        width07=fc2["definitions"]["width07"], lip=fc2["definitions"]["lip"], h_b=fc2["definitions"]["h_b"],
        crest_to_trough=fc2["definitions"]["crest_to_trough"],
        measure_code="the campaign-B code itself: flip49 g49_planB_ana.measure (read only, called by g50_ana.plan_d_numbers), so D and DA3/S0-S3 share "
                     "the ruler, the track and the windows",
        q_track="q = H_rear / Hmax(h, T) along the centre-crest track (every 3rd frame; h = still depth under the crest; Hmax = Fenton fit): at the toe "
                "crossing (x 160.25 +- 3 m), at h 15 and 13 m (+- 0.75 m), the first depth with q >= 0.9 / 1.0 (from x 140.25 m on), the maximum over "
                "onset - 3 s .. onset, and q_on = H_rear(onset) / Hmax(h_b)",
        focusing_gain="per breaker: Hc, H_front, H_rear over the component amplitude a_j (0.211 m DM1) and over the linear focal design: |A(x_on, 0)| "
                      "(Hc), 2|A(x_on, 0)| (H_front, H_rear), |A(x_f, 0)|; plus c0/c_in (D: lateral mean over |y| <= 95 m of the incident crest at x 128 m) "
                      "and plan A's c0/c_in (x 160 m gauge)",
        periodic_narrow="c0/c_side (P4a ratio, |y| 70-84 m), c0/c(4 Hc) (P4b ratio), curl width / Hc at onset, max overturn and touchdown (P2/P3), "
                        "onset x scatter (max |x - median|) and Hc CV over the judged breakers and over the PERIODIC window",
        end_wall="report only: per period, the highest top surface over x >= 400 m and the fraction of frames with water at x >= 405 m (RV-D1)")
    C["periodic_D"]["open_item"] = ("the D verdict (pass/partial/fail) uses PERIODIC + targets_D + q73_vs_DA3; P1-P5 per breaker stay reported "
                                    "(P5 chord/hood and P2/P4b are not part of the D verdict)")
    C["verdict_D"] = dict(
        pass_="PERIODIC (>= 3 consecutive judged breakers, each P4a c0/c_side >= 1.5 and curl width <= 2.5 Hc at max overturn; onset x within +-10 m of "
              "their median; Hc CV <= 10 %) AND targets_D on the judged medians (crest-to-front-trough >= 10 m, best-frame back >= 25 deg, best-frame "
              "width07 <= 1.6, lip >= 0.2)",
        partial="not pass, but the Q73 improvement vs DA3 holds",
        fail="no Q73 improvement vs DA3, or fewer than 3 judged breakers with an onset at x <= 330 m",
        never="'steady state'", self_assessment="every shape number is AI self-assessment through the STUDY52 ruler; the user judges print-likeness")
    H = C["health"]
    H.update(volume_hard_max=0.02, wall_max_h_per_coarse_3d_run=3.0,
             wall_rule="<= 3.0 h per coarse 3D run (RV-D3: = cfg max_hours, decided before freezing), launched in chunks of <= 29 min (wall_limit 1740 s)",
             volume_rule="stage C: period-mean window volume over x 110-400 m (beach included; full half width) from the ramp end: < 1 % pass; 1-2 % "
                         "soft (verdict printed with the flag; diagnose before the next round: the beach set-up fed by stage C is the registered suspect, "
                         "RV-D2); > 2 % hard",
             still_offset_note="reported (FLIP surface ~0.1 m high at rest, depth dependent; measured at the run start)",
             diagnose_first=["run incomplete or stopped (max_hours, guard, crash)", "bed leak >= 1e-4", "centre onset on the flat (x < 160.25 m) in >= 2 judged periods",
                             "generation at x 160 m, |y| <= 40 m outside 0.80-1.20 of the linear target (first harmonic, last 3 periods)",
                             "swash set-up > 3 m (period mean of the swash region)", "stage-C window volume > 2 %"],
             hard_soft_rule="hard = diagnose_first (not a round: fix and rerun, or stop and ask); soft = volume 1-2 %, H_wall > 3.0 h, still offset >= 0.1 m "
                            "(printed beside the verdict)",
             removed_at_freeze="'onset at h_b > 14 m' (2026-10-15 draft): an onset on the slope deeper than 14 m is the focus-limited regime (AM-D11)")
    # ---- smoke gates (AM-D10) ----------------------------------------------------------------------------------------------------------------------------
    P["smoke_gates"] = dict(
        text=("SMOKE_D (dp 1.0, 0-50 s, one launch <= 29 min) decides whether DM1 (dp 0.5) is launched: band amplitude 0.85-1.15 of the linear target "
              "at the gauges (inlet and side band), focal hot spot (first-harmonic lateral contrast peak) within +-15 m of x_f with contrast >= 1.5, "
              "recurrence T +- 1 s, no breaking on the flat (x < 160.25 m), no leak, stage-C volume < 1 %, pattern correlation at x 160 m >= 0.9, "
              "finished in one launch"),
        run="SMOKE50D_D19B_T12_dp1p0: 3D dp 1.0, W 140, DM1 sea, 0-50 s, ONE launch of <= 29 min (max_hours 0.49 h), never judged on shape",
        why_50s="the phases put a crest on the focus at t = nT (24, 36, 48 s; the 24 s crest still carries the 24 s band ramp, ~0.3-0.5 of full "
                "[computed: travel 10-17 s from the bands]); 50 s keeps the 48 s passage 2 s inside the record, so two strong passages (36, 48 s) "
                "give one recurrence interval and the last full period (38-50 s) is past the ramp. The brief's example 0-40 s leaves one strong "
                "passage only and part of the ramp in its last period; 0-62 s would reach ~29 min [chosen]",
        band_ratio=[0.85, 1.15], inlet_gauges_x=[110.0], side_gauges_x=[128.0, 160.0], side_gauges_y=[60.0, 80.0],
        hot_x_range=[150.0, 300.0], hot_smooth_m=5.0, focus_dx_max_m=15.0, contrast_side_y=[70.0, 84.0], contrast_min=1.5,
        focus_t_min_s=30.0, focus_t_margin_s=1.0,
        recur_t_min_s=18.0, recur_rel_min=0.5, recur_tol_s=1.0, recur_min_intervals=1,
        leak_frac_max=1e-4, volume_max=0.01, pattern_corr_min=0.9,
        gates=dict(
            inlet_band_amplitude="mean first-harmonic H1 / H_lin (H_lin = 2|A| of the table) over the 5 gauges at x 110 m (y 0.5/20/40/60/80) in the last full "
                                 "period: 0.85-1.15",
            side_band_amplitude="the same over the gauges at x 128 and 160 m, y 60 and 80 m (fed by the side band): 0.85-1.15",
            focal_hot_spot_at_x_f="the first-harmonic lateral contrast C(x) = |A1(x, 0)| / mean |A1(x, |y| 70-84 m)| (+-5 m running mean) peaks at x_hot over "
                                  "x 150-300 m with |x_hot - x_f| <= 15 m (the designed linear field peaks at x_f + ~5 m; |A(x, 0)| itself is a plateau, "
                                  "so the contrast marks the focus)",
            focal_lateral_contrast="C(x_hot) >= 1.5 (linear design 5.1)",
            recurrence_T="strong maxima (>= 0.5 x the largest) of eta(x_hot, 0, t) after 18 s are spaced T +- 1.0 s (>= 1 interval; expected passages ~36 "
                         "and ~48 s, ~24 s if strong enough)",
            no_breaking_on_flat="no centre onset (g46 centre_events on r2: thmax >= 90 deg, crest >= 1 m) at x 5-160.25 m over the whole run (the flat is "
                                "highest on the axis: off-axis H_lin at 19 m is <= 6.4 m, q <= 0.5)",
            no_leak="particles below the bed < 1e-4 of the maximum count",
            volume_stage_C="stage-C window volume period means (from 24 s) < 1 %",
            pattern_corr_x160="complex correlation of the first harmonic at x 160 m with the linear target over |y| <= 95 m >= 0.9 (kept from the draft)",
            finished_in_one_launch="the smoke ends at f_end within one launch (cost: smoke <= 30 min)",
            table_loaded="the directional table (10 fields) loaded by the run", no_errors="no error entries in the run records"),
        reported_not_gated=["the centre crest position at t = 36 and 48 s (dx from x_f; nonlinear crests may run ahead)",
                            "realized first-harmonic axis amplitude / linear |A(x, 0)| at x 160, x_f, 240 m (dp 1.0 damps more than dp 0.5)",
                            "dir_check (grid velocity vs target in the bands)", "launch wall time (re-check of the DM1 time estimate)"],
        decision="all gates pass -> launch DM1 (dp 0.5). Any gate fails -> diagnose and fix (code or preset) and re-smoke; this is not a round. A fix "
                 "that changes a frozen design number needs a dated amendment (plan_D_amendment_*.json) before DM1. Not diagnosable -> stop and ask",
        deliverable="video/<run_id>_smoke.mp4 (top view + centre section 1:1, red frame and hold at t = nT) and pana/smoke_D.json",
        tags=dict(thresholds="chosen (frozen)", numbers="measured (FLIP) vs computed (linear table)"))
    # ---- decision rules (AM-D12, RV-D4) -------------------------------------------------------------------------------------------------------------------
    P["decision_rules"] = dict(
        order="T0D hython build check -> SMOKE_D gates -> DM1 (dp 0.5, 92 s, chained launches <= 29 min) -> g50_ana.py all + g50_video.py all -> after_DM1",
        before_DM1=["T0D: x50_build.py (hython) all_ok: bed/SDF = numpy, particle count, dir_probe VEX = numpy mirror, relax_probe D (pending: no Houdini "
                    "in the freeze step). Failure -> fix code (no design change: no amendment needed; a design change needs one)",
                    "SMOKE_D: every smoke gate passes (smoke_gates) -> DM1. Otherwise smoke_gates.decision",
                    "S2D strips: not in the queue (optional, report only; they never gate DM1) [AM-D15]"],
        min_judged_breakers=3, max_rounds_in_D=3,
        after_DM1=["0 HEALTH: any hard item of criteria.health.diagnose_first -> 'diagnose first' (not a round; fix and rerun, or stop and ask)",
                   "1 COUNT: fewer than 3 judged breakers (onset t >= 45 s) with an onset at x <= 330 m -> FAIL: stop and ask",
                   "2 PASS: criteria.verdict_D.pass_ -> DD3: +48 s continuation of the same run (same settings) and a seamless 12 s loop; then show the user",
                   "3 PARTIAL: not pass but the Q73 improvement vs DA3 holds -> name the single next change by partial_mapping (first match); it is frozen "
                   "as a dated amendment before it runs; Q73 lets it run without waiting for the user",
                   "4 FAIL: no Q73 improvement vs DA3 -> stop and ask (Q73)"],
        precedence="list order, first match wins (RV-D4); implemented in g50_ana.decide_D; soft health items are printed beside any verdict",
        partial_mapping=[
            dict(id="band_gain", threshold=0.90,
                 what="re-run the same design with in_gain = sd_gain = 1 / r, r = the median first-harmonic H1/H_lin of the gauges at x 128 and 160 m, "
                      "|y| <= 40 m (realizes the designed field; a_sum, x_f, T, bed unchanged)",
                 why="the bands are uncalibrated at T 12 s / h0 19 m (in_gain 1.0); when they under-deliver, every shape number is read on a lower q than "
                     "designed; this restores the design, it does not enlarge it", tag="chosen"),
            dict(id="DD3_continuation",
                 what="+48 s continuation of the same run, nothing changed, to read >= 4 more breakers (only when PERIODIC fails on recurrence alone: every "
                      "judged breaker meets P4a >= 1.5 and curl <= 2.5 Hc, and targets_D pass)",
                 why="onset x scatter or Hc CV can come from the first breakers after the ramp and the developing rip cell (U3: x_b spread 10 m); more "
                     "breakers decide it without a change", tag="chosen"),
            dict(id="DF1",
                 what="DF1 = T 10 s (a_sum 6.503 m by the same linear rule h_b 11 m, ramp 20 s, t_end 86 s; table, presets and screens already built)",
                 why="one change (period). At the same focal-height rule T 10 s raises q = H/Hmax(h, T) on the slope by ~6 % (h 13-15 m: linear 1.21-1.38 "
                     "vs 1.13-1.30) - campaign B's lever for back and width07 [computed] - and its linear curl widths are narrower (1.2/2.3/3.2 vs "
                     "1.6/3.0/4.3 Hc) [computed]. Risk: q at the toe is similar (0.83 vs 0.84) and the slope may still set a 2D-like back [guess]",
                 tag="chosen")],
        after_next_round=["the same order (health, count, pass, partial, fail) with Q73 vs DA3 for fail and Q73 vs the previous D round reported "
                          "(g50_ana.py report <run> --prev=<previous D run>)",
                          "two consecutive D rounds without improvement on their previous round -> stop and ask (Q73)",
                          "round 3 (DM1 + 2 follow-ups) -> stop and show the user whatever the verdict (except pass -> DD3 first)",
                          "a mapping item is never used twice; DF1 partial with nothing left -> stop and ask"],
        limits=["one change per run", "at most 3 D rounds before showing the user", "never loosen a frozen threshold after seeing a result",
                "one Houdini simulation at a time; each launch <= 29 min (wall_limit 1740 s, g50_chain)", "no a_sum increase in any listed change (Q39)",
                "every run ships an mp4 (g50_video.py compare/whole, red frame at the most print-like instant with the print outline; the smoke: "
                "g50_ana.py smoke video) plus the tagged numbers"])
    # ---- registered expectations for DM1 (before the run) ------------------------------------------------------------------------------------------------
    P["registered_expectations_DM1"] = dict(
        onset_h_b_m=[10.5, 15.0], Hc_m=[7.5, 10.0], H_front_m=[10.0, 13.5], back_best_deg=[12.0, 22.0], width07_best=[1.4, 2.4], lip=[0.25, 0.5],
        curl_w_maxov_over_Hc=[1.9, 4.2], c0_over_c_side=">> 1.5 (shadowed |y| 70-84 m band)", P_back_best_ge_25=0.2,
        most_likely_verdict="partial (Q73 back +3 deg very likely; back >= 25 deg and curl <= 2.5 Hc doubtful) -> DF1",
        reasons=["U3 screen onsets h_b 10.7-11.7 m, c0 9.5-10.4 m [computed]; q-profile near-limiting at h 13-16 m [computed]",
                 "campaign B: 2D 1:10 onset back 15-16 deg whatever q; focus-limited flat-bed breakers 20-25 deg [measured]",
                 "U3 width proxies 1.9-4.2 Hc at +0.75 s [computed, uncalibrated]"],
        tag="guess (registered before any D run; never used to judge)")
    # ---- RV-D1..D4 resolutions ---------------------------------------------------------------------------------------------------------------------------
    P["review_pre_freeze"]["resolutions"] = dict(
        RV_D1=dict(decision="keep Lx 412 m (beach top +6.175 m at the closed wall) [chosen]",
                   why="minimal change: the break target is 170 m seaward of the wall; the U3 run-up stays 0.3 m below the top; Lx 472 m would add 15-17 % "
                       "grid cells and move the layout away from the registered screens. Wall contact is measured and reported per period (end_wall)",
                   risk="FLIP run-up exceeds the depth-averaged screen (P1c reached its wall): wall reflection and stored swash water are possible"),
        RV_D2=dict(decision="H_volume judged as written (< 1 %) with a soft band 1-2 % that prints the verdict with a flag; > 2 % is hard [chosen]",
                   why="stage C holds the probe level, so the physical beach set-up (+0.5..+1.1 % of the window, estimate) is fed from the inlet; a "
                       "borderline 1 % failure should not discard a 2.5 h run, while > 2 % means the drift fix itself misbehaves"),
        RV_D3=dict(decision="H_wall = 3.0 h (= cfg max_hours) [chosen]", why="DM1 bound 2.73 h by the FLIP48 coefficients, 1.9-2.1 h by the DA1 two-phase "
                                                                              "rule; plan B raised its cap before launch as well"),
        RV_D4=dict(decision="decision_rules.after_DM1 list order, first match wins (health, count, pass, partial, fail) [chosen]",
                   why="the draft's rules mixed 'D negative' and DF1 triggers; the brief's pass/partial/fail replaces them"))
    # ---- honesty -------------------------------------------------------------------------------------------------------------------------------------------
    Ho = P["honesty"]
    Ho["chosen"] = list(Ho["chosen"]) + [
        "keeping x_f, a_sum, T, theta_max, h0, the slope and Lx after the q-profile check (AM-D14)", "the smoke duration 0-50 s and every smoke-gate threshold",
        "targets_D, the Q73 thresholds, the volume soft band 1-2 %, H_wall 3.0 h", "the partial mapping (band gain, DD3 continuation, DF1) and its order"]
    Ho["computed_by_FLIP"] = ("shoaling, refraction, nonlinear focusing, where/when/at what depth each crest breaks, its height, the section shape (back, "
                              "width07, chord, lip, hood), the curl width, the recurrence, set-up and rip currents")
    Ho["computed_numpy"] = ["the band target table (linear WKB) and its mean mass flux", "the axis q profile and the linear focal design |A(x, 0)|",
                            "the focusing gain ratios (measured heights over linear design numbers)"]
    Ho["focus_is_chosen"] = ("the converging directional field, its focus point (220.25 m, 0) and its focus time (t = nT) are CHOSEN at the inlet and side "
                             "bands (all 30 component phases set to 0 there); FLIP computes everything that happens to that field")
    Ho["height_source"] = ("the crest height is set mainly by the CHOSEN coherent sum (a_sum 6.33 m of 30 components of 0.211 m each, all in phase at the "
                           "focus) and by shoaling on the slope. The gain over one component (Hc / a_j, expected ~35-45) is a property of that choice, not "
                           "evidence that the wave grew by itself; the meaningful gains are c0/c_in (vs the incident sea at x 128 m) and Hc vs the linear "
                           "focal design. No listed change raises a_sum (Q39)")
    Ho["q_caveat"] = "q uses the 2D steady limit; focused (short-crested) and shoaling crests can exceed q = 1; the realization factors are borrowed"
    Ho["site"] = "the D19B beach and the focusing field are chosen shapes, not a measured place (Q63: shape first, no site)"
    P["risks"] = [(r + " [resolved at the freeze step: H_wall 3.0 h, RV-D3]") if "H_wall health item (2.5 h)" in r else r for r in P["risks"]] + [
        "focusing completes near the toe and the slope may reshape the crest like a 2D shoaling wave: back 13-17 deg (campaign B's S0/S1/P1c) rather than "
        "the focus-limited 20-25 deg [guess]",
        "the smoke at dp 1.0 cannot test the dp 0.5 losses that set the realized q; DM1's q track measures it",
        "the most likely verdict is partial -> DF1 (registered_expectations_DM1)"]
    # ---- queue ---------------------------------------------------------------------------------------------------------------------------------------------
    for r in P["runs"]:
        if r["id"] == "S2D":
            r["status"] = "not in the queue (optional, report only; AM-D15)"
        if r["id"] == "SMOKE_D":
            r["what"] = "3D smoke dp 1.0, 0-50 s, one launch of <= 29 min, never judged; frozen smoke_gates decide DM1"
        if r["id"] == "T0D":
            r["status"] = "numpy part done (plan/precheck_D.json all_ok); hython build check pending (no Houdini in the freeze step)"
        if r["id"] == "FREEZE_D":
            r["status"] = "this file (2026-10-16 freeze step)"
        if r["id"] == "DF1":
            r["status"] = "conditional: partial_mapping item 3"
        if r["id"] == "DD3":
            r["status"] = "conditional: pass, or partial_mapping item 2"
        if r["id"] == "ANA_D":
            r["what"] = ("g50_ana.py all <run>: g49_periodic_ana (P1-P5, PERIODIC) + report_D + plan_d_numbers (campaign-B numbers, q track, focusing gain, "
                         "targets, Q73 vs DA3, D verdict) -> pana/planD_ana.json, planD_table.txt")
    P["design"]["time_and_records"]["smoke"] = dict(t_end_s=50.0, frames=1201, windows=[[38.0, 50.0]], heavy_every=2, max_hours=0.49)
    I = P["implementation"]
    I["status"] = "implemented; numpy checks pass (plan/precheck_D.json, freeze step 2026-10-16); hython build check pending"
    I.pop("commands_after_DA1", None)
    I["commands_after_freeze"] = [
        "py -3.10 Tools/GWWaveGen/flip50/x50_build.py   (hython build check -> Unity/Build/FLIP50/_logs/build_check.json all_ok; nothing else may run)",
        "py -3.10 -B Tools/GWWaveGen/flip50/g50_pcfg.py cfg SMOKE_D DM1 DF1",
        "py -3.10 Tools/GWWaveGen/flip50/g50_chain.py Unity/Build/FLIP50/smoke/ready/SMOKE50D_D19B_T12_dp1p0.json",
        "py -3.10 -B Tools/GWWaveGen/flip50/g50_ana.py smoke Unity/Build/FLIP50/smoke/SMOKE50D_D19B_T12_dp1p0   (smoke gates + smoke mp4)",
        "py -3.10 Tools/GWWaveGen/flip50/g50_chain.py Unity/Build/FLIP50/runs/ready/DM1_D19B_T12_th80_dp0p5.json   (only if every smoke gate passes)",
        "py -3.10 -B Tools/GWWaveGen/flip50/g50_ana.py all Unity/Build/FLIP50/runs/DM1_D19B_T12_th80_dp0p5   (D verdict: pana/planD_ana.json)",
        "py -3.10 -B Tools/GWWaveGen/flip50/g50_video.py all Unity/Build/FLIP50/runs/DM1_D19B_T12_th80_dp0p5",
        "then decision_rules.after_DM1 (pass -> g50_pcfg.py cfg DD3 --run=<run>; partial -> amendment for the named change; fail -> stop and ask)"]
    I["analysis_note"] = ("g50_ana passes criteria.periodic_D to g49_periodic_ana as periodic_A (identical PERIODIC rule); the D verdict and the next step "
                          "are decided by g50_ana.plan_d_numbers / decide_D from decision_rules.after_DM1 (campaign-B numbers through g49_planB_ana.measure)")
    P["amendments_vs_design_draft"] = list(P["amendments_vs_design_draft"]) + [
        dict(id="AM-D9", what="criteria: targets_D, q73_vs_DA3, DA3_reference, print_reference, campaign-B definitions, verdict_D",
             why="campaign B (back/width07 targets) and Q77 (crest-to-front-trough >= 10 m); the brief's criteria list", tag="chosen"),
        dict(id="AM-D10", what="SMOKE_D 0-48 s -> 0-50 s, max_hours 0.75 -> 0.49 h, frozen smoke_gates", why="smoke_gates.why_50s; one launch <= 29 min",
             tag="chosen", cost="est. %s h" % [round(v, 3) for v in pre["presets"]["SMOKE_D"]["time"]["est_h"]]),
        dict(id="AM-D11", what="health: 'onset at h_b > 14 m' removed from diagnose-first; hard/soft split; volume soft band 1-2 %; H_wall 3.0 h",
             why="design_review_B.consequences; RV-D2; RV-D3", tag="chosen"),
        dict(id="AM-D12", what="decision rules replaced (pass / partial / fail, precedence, partial mapping)", why="the brief; RV-D4", tag="chosen"),
        dict(id="AM-D13", what="g50_ana: plan_d_numbers / decide_D / health_D / end_wall / smoke gates + smoke video", why="the brief's analysis list",
             tag="code"),
        dict(id="AM-D14", what="design numbers kept after the q-profile check", why="design_review_B", tag="chosen (computed reasons)"),
        dict(id="AM-D15", what="S2D strips out of the queue", why="campaign B already measured the 2D 1:10 back (15-16 deg); the strips cannot test focusing",
             tag="chosen"),
        dict(id="AM-D17", what="g50_pcfg.py freezeD refuses a stale draft (module sha16 or precheck sha differ)", why="the frozen plan must describe the code that runs",
             tag="code")]
    return P


def main():
    D = json.load(open(GC.DESIGN_DRAFT, encoding="utf8"))
    pre_p = GC.PLAN_DIR + "/precheck_D.json"
    if not os.path.exists(pre_p):
        raise SystemExit("run `py -3.10 -B g50_pcfg.py check` first (%s missing)" % pre_p)
    pre = json.load(open(pre_p, encoding="utf8"))
    if not pre.get("all_ok"):
        raise SystemExit("precheck_D.json all_ok is false: fix before writing the draft")
    P = copy.deepcopy(D)
    P["status"] = ("DRAFT for freezing: option D implemented in Tools/GWWaveGen/flip50 and all numpy checks pass (plan/precheck_D.json); the hython "
                   "build check (x50_build.py -> _logs/build_check.json all_ok) is pending (DA1 running). Freeze with `py -3.10 -B g50_pcfg.py freezeD` "
                   "after the build check passes; g50_chain.py refuses to start without plan_D_frozen.json + .sha256")
    P["made_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    P["tool"] = "Tools/GWWaveGen/flip50/g50_planD.py"
    P["canonical_path"] = "Unity/Build/FLIP50/plan/plan_D_draft.json (frozen copy: plan_D_frozen.json)"
    P["design_draft"] = dict(path="Tools/GWWaveGen/flip50/plan_D_draft.json", sha256=GC.sha256_file(GC.DESIGN_DRAFT), note="read only")
    pr = pre["presets"]
    tm = pr["DM1"]["time"]; tf = pr["DF1"]["time"]
    t1 = pre["table_DM1"]; t2 = pre["table_DF1"]
    P["amendments_vs_design_draft"] = [
        dict(id="AM-D1", what="zero-mean-mass-flux return current in the band target (ret_on 1): u_r = -M/h with M = Re(A conj(Q))/(2h), applied as g^2 (mx, my)",
             why=("with Wheeler stretching the linear target carries a period-mean mass flux; through x = 100 m it is %.0f m3/s for the half tank (DM1; %.0f m3/s DF1), "
                  "about %.0f m3 in 92 s, i.e. the band would pump water onto the beach. The FLIP49 Fenton inlet has u2 = 0 (zero mean mass flux), so the band "
                  "imposes no net flux there either. Inlet-band return current max %.3f m/s, mean %.3f m/s (FLIP49 Fenton u1 = -0.29 m/s)")
             % (t1["mean_mass_flux"]["per_x"]["x100"]["M_without_return_m3s"], t2["mean_mass_flux"]["per_x"]["x100"]["M_without_return_m3s"],
                t1["mean_mass_flux"]["implied_volume_92s_without_return_m3"], t1["mean_mass_flux"]["inlet_band_return_mps"]["max"],
                t1["mean_mass_flux"]["inlet_band_return_mps"]["mean"]),
             tag="chosen (computed magnitudes)", caveat="the U3 screens had no return current: their set-up/set-down numbers include the pumping; stage C stays as the drift fix"),
        dict(id="AM-D2", what="outer side-wall taper of the band target smooth01((W - y)/11.25 m)", why="FLIP45 wallE rule (taper = band thickness / 4) so the "
             "target does not drive flow into the closed wall y = W; the upstream wall keeps the FLIP49 20 m taper", tag="chosen",
             caveat="the U3 screen had no side taper; generation at |y| 60-80 m may fall a little below the screened 0.85-0.88"),
        dict(id="AM-D3", what="heavy records (r4, r5) continuously from 44 s to the end every 3rd frame; r4 x 190-335 m, lateral 0-95 m; r3 (far section) at y 77 m; "
             "g46 far row y_far 90 m; surface crop y <= 95 m", why="the break time is uncertain by several seconds (onset x +-25 m), so screen windows could miss it "
             "(plan A AM-A2 precedent); r4 must cover the P1 limit 330 m and stay in the interior; y_far must lie inside r4 (the default W - 1 = 139 m is in the side band)",
             tag="chosen", cost="DM1 %d heavy frames (screen windows every 2nd frame: about 340)" % pr["DM1"]["heavy"]),
        dict(id="AM-D4", what="SMOKE_D runs 0-48 s (not 0-36 s)", why="ramp 24 s + travel from the band to x 160 m (~10 s) + one full period for the pattern correlation at x 160 m",
             tag="computed / chosen", cost="estimated %s h, one launch" % [round(v, 2) for v in pr["SMOKE_D"]["time"]["est_h"]]),
        dict(id="AM-D5", what="dp 1.0 half width 140 m (box48 keeps 140 at a 2 m grid): 665,000 particles", why="the design used W 142 (674,500); 140 is a 2 m multiple", tag="computed"),
        dict(id="AM-D6", what="cfg max_hours 3.0 h for DM1/DF1 (task budget 2.5-3 h); criteria.health.wall_max_h_per_coarse_3d_run stays 2.5 h (copied from plan A)",
             why="the FLIP48-coefficient upper estimate is %.2f h (DM1); the DA1 two-phase estimate is %s h" % (tm["total_h_hi"], [round(v, 2) for v in tm.get("da1_two_phase_h", [])]),
             tag="chosen", open_item="the orchestrator decides before freezing whether H_wall should read 3.0 h; as written, a 2.5-3.0 h run would fail H_wall (health) only"),
        dict(id="AM-D7", what="S2D strips: t_end 84 s (T 12) / 70 s (T 10), in_gain 1.0 (uncalibrated at h0 19 m; the gauges report H), stage C, heavy records 40 s..end",
             why="ramp + 5 periods gives 3-4 breakers at t >= 45 s for T 12 s", tag="chosen"),
        dict(id="AM-D8", what="stage C reading region probe_c and the band-core / window levels use the interior y 0-95 m", why="the side band (y 95-140 m) is forced", tag="chosen"),
    ]
    P["design"]["time_and_records"]["main"].update(windows=[[PC.HEAVY_CONT["t0"], 92.0]], heavy_every=PC.HEAVY_CONT["every"], heavy_frames=pr["DM1"]["heavy"],
                                                   windows_screen_alternative="g50_pcfg.py cfg DM1 --heavy=screen")
    P["design"]["time_and_records"]["fallback"].update(windows=[[PC.HEAVY_CONT["t0"], 86.0]], heavy_every=PC.HEAVY_CONT["every"], heavy_frames=pr["DF1"]["heavy"])
    P["design"]["time_and_records"]["heavy"] = ("r4 per-y sections x 190-335 m, lateral 0-95 m, vertical -10..16 m, and r5 surfaces (y <= 95 m), "
                                                "continuously from 44 s every 3rd frame (AM-D3)")
    P["design"]["time_and_records"]["gauges"] = "eta at x 110/128/160 m x y 0.5/20/40/60/80 m every frame"
    P["design"]["cost"].update(
        estimate_DM1=dict(coef_h=[round(tm["total_h_lo"], 2), round(tm["total_h_hi"], 2)], da1_two_phase_h=[round(v, 2) for v in tm.get("da1_two_phase_h", [])],
                          bound_h=round(tm["bound_h"], 2), launches=pr["DM1"]["launches"], heavy_frames=pr["DM1"]["heavy"]),
        estimate_DF1=dict(coef_h=[round(tf["total_h_lo"], 2), round(tf["total_h_hi"], 2)], da1_two_phase_h=[round(v, 2) for v in tf.get("da1_two_phase_h", [])],
                          bound_h=round(tf["bound_h"], 2), launches=pr["DF1"]["launches"]),
        da1_launches_measured=pre["da1_phases"].get("launches"),
        da1_note=("DA1 launches [measured]: " + "; ".join("frames %d-%d %.2f s/frame (%.3f s per Mp per frame, substeps %s)" % (
                      r["f_start"], r["f_end"], r["s_per_frame"], r["s_per_Mp_frame"], r.get("substeps")) for r in pre["da1_phases"].get("launches", []))
                  + ". Launch 1 is before breaking and heavy records; later launches include breaking (more substeps) and r5 surfaces every 3rd frame "
                    "(2.36-2.41 s each). The DA1 two-phase rule uses launch 1 before t 36 s and the later launches after it"),
        limit_h=GC.LIMIT_D_H)
    P["design"]["inflow"]["return_current"] = "ret_on 1 (AM-D1)"
    P["design"]["bands"]["side"]["outer_wall_taper_m"] = GC.SD_TAPER
    P["design"]["domain"]["particles_computed"] = {k: v["model"] for k, v in pre["particles"].items()}
    P["design"]["inflow"]["table_check"] = {c: dict(focus_abs_A_m=pre["table_" + c]["focus"]["abs_A"], focus_theory_m=pre["table_" + c]["focus"]["theory_sum"],
                                                    crest_time_mod_T_s=pre["table_" + c]["focus"]["crest_time_mod_T_s"],
                                                    continuity_flat=pre["table_" + c]["continuity"]["max_rel_residual_flat"],
                                                    interpolation_max_rel=max(pre["table_" + c]["interpolation"]["max_rel_eta"], pre["table_" + c]["interpolation"]["max_rel_U"],
                                                                              pre["table_" + c]["interpolation"]["max_rel_V"]),
                                                    symmetry_V_y0=pre["table_" + c]["symmetry"]["max_abs_V_at_y0"],
                                                    first_lateral_zero_scale_m=pre["table_" + c]["ky_bound"]["first_lateral_zero_scale_m"]) for c in ("DM1", "DF1")}
    tabs = {c: PC.table_for(c) for c in ("DM1", "DF1")}
    P["implementation"] = dict(
        status="implemented; numpy checks pass; hython build check pending",
        files={("flip50/" + k.split("/")[-1]): v for k, v in GC.module_shas().items() if k.startswith("flip50/")},
        read_only=["flip45-flip49 files (g49_tanklib VEX head reused verbatim with renamed node paths and a replaced band block; g49_run/g49_chain "
                   "copied with counted replacements; g49_periodic_ana/g49_video2 run with in-memory adaptations)"],
        reused_sha16={k: v for k, v in GC.module_shas().items() if not k.startswith("flip50/")},
        scene=dict(hip="Houdini/FLIP50/g50_tank.hiplc", nodes="G50_SETUP / G50_SIM / G50_READ / G50_SURF", build_check="Unity/Build/FLIP50/_logs/build_check.json"),
        tables={c: dict(npz=v["npz"].replace(GC.REPO + "/", ""), sha256=v["npz_sha256"], content_sha256=v["content_sha256"]) for c, v in tabs.items()},
        cfgs={nm: v["run_id"] for nm, v in pr.items()},
        numpy_checks=dict(path="Unity/Build/FLIP50/plan/precheck_D.json", sha256=GC.sha256_file(pre_p), ok=pre["ok"]),
        commands_after_DA1=[
            "py -3.10 -B Tools/GWWaveGen/flip50/g50_pcfg.py check",
            "py -3.10 Tools/GWWaveGen/flip50/x50_build.py",
            "py -3.10 -B Tools/GWWaveGen/flip50/g50_planD.py && py -3.10 -B Tools/GWWaveGen/flip50/g50_pcfg.py freezeD",
            "py -3.10 -B Tools/GWWaveGen/flip50/g50_pcfg.py cfg all",
            "(optional S2D) py -3.10 Tools/GWWaveGen/flip50/g50_chain.py Unity/Build/FLIP50/strips/ready/S2D_D19B_axis_T12_H0p83max.json (and T10), then g50_ana.py s2d",
            "py -3.10 Tools/GWWaveGen/flip50/g50_chain.py Unity/Build/FLIP50/smoke/ready/SMOKE50D_D19B_T12_dp1p0.json; py -3.10 -B Tools/GWWaveGen/flip50/g50_ana.py smoke <run>",
            "py -3.10 Tools/GWWaveGen/flip50/g50_chain.py Unity/Build/FLIP50/runs/ready/DM1_D19B_T12_th80_dp0p5.json",
            "py -3.10 -B Tools/GWWaveGen/flip50/g50_ana.py all <run>; py -3.10 -B Tools/GWWaveGen/flip50/g50_video.py all <run>"],
        analysis_note="g50_ana passes criteria.periodic_D to g49_periodic_ana as periodic_A (identical rule) and applies decision_rules.after_DM1/after_DF1 for the next step")
    for r in P["runs"]:
        if r["id"] in ("SMOKE_D", "DM1", "DF1"):
            r["run_id"] = pr[r["id"]]["run_id"]
        if r["id"] == "S2D":
            r["run_id"] = [pr["S2D_T12"]["run_id"], pr["S2D_T10"]["run_id"]]
        if r["id"] == "T0D":
            r["what"] = ("numpy checks (done: plan/precheck_D.json all_ok) + hython build checks (x50_build.py: bed/SDF vs numpy, particles, Fenton probe at h0 19, "
                         "dir_probe VEX = numpy mirror, relax_probe D and strip layouts)")
    P["honesty"]["chosen"] = list(P["honesty"]["chosen"]) + ["the zero-mean-mass-flux return current in the band target (AM-D1)", "the outer side-wall taper 11.25 m (AM-D2)",
                                                             "the heavy-record window 44 s..end every 3rd frame (AM-D3)"]
    P["honesty"]["computed"] = list(P["honesty"]["computed"]) + ["the band target table (linear WKB directional field) and its mean mass flux"]
    P["risks"] = list(P["risks"]) + [
        "the DA1 breaking-phase rate (3.79 s/frame) is twice its pre-break rate: DM1 is estimated at %s h by the DA1 two-phase rule and %.2f h by the FLIP48 "
        "coefficient bound; the H_wall health item (2.5 h) may fail although the cfg allows 3.0 h (AM-D6)" % ([round(v, 2) for v in tm.get("da1_two_phase_h", [])], tm["bound_h"]),
        "first FLIP use of the directional complex-table relaxation and the side band at T 12 s / h0 19 m (FLIP45 tested T 7 s, h 20 m); the hython build check compares "
        "the VEX with the numpy mirror, SMOKE_D checks the generated pattern"]
    # 2026-10-15 adversarial review (numpy only, no hython): decisions the orchestrator takes BEFORE freezing; no threshold is changed here
    P["review_pre_freeze"] = dict(
        date="2026-10-15", by="review subagent (numpy checks; DA1 untouched)",
        code="no blocking code bug found; one robustness fix: g50_chain.py no longer counts time spent waiting for another hython against cfg max_hours",
        decisions=[
            dict(id="RV-D1", item="end wall at x 412 m: the D19B beach top there is only +6.175 m and the box wall is closed",
                 evidence=["U3 screen of DM1 (u50_F12_main, Lx 412): run-up up to +5.88 m at the centre, +5.68 m at |y| 20-40 m, +5.27 m at |y| 60-84 m in t 48-72 s "
                           "(the judged breakers), 0.2-0.3 m below the top [computed, screen]; DF1: +5.27 m",
                           "FLIP 2D analogue P1c (FLIP47, 1:10 beach, T 14 s, H 12 m, beach top +14 m): water above +6.175 m in 62 % of frames, run-up to its end wall "
                           "and up to 2.0 m of water kept there after 62 s [measured, hf records]; FLIP run-up exceeds the depth-averaged screen (Hunt R = xi0 H0 ~ 6 m there)"],
                 consequence="FLIP DM1 is likely to reach the end wall during the judged breakers: wall reflection back through the surf zone and stored water "
                             "(more stage-C inflow); not judged by any criterion",
                 option="Lx 472 m (top +12.2 m) or 482 m (+13.2 m): particles unchanged (5,383,840: the extension is dry beach), grid cells +15-17 % (air); "
                        "needs an amendment (design Lx, constants check against the U3 layout Lx 412, layout text) and a rebuild; alternatively keep Lx 412 and "
                        "read the swash at x 412 in S2D (runs only after freezing; a re-freeze with --force before any 3D record is allowed)",
                 tag="computed / measured; choice open"),
            dict(id="RV-D2", item="H_volume (health, 1 %) under stage C with a beach",
                 evidence=["DA1 (plan A, stage C) window period means +0.92, +0.73, +0.40, +0.78 % over 24-72 s [measured, volcorr/state.jsonl up to launch 3]",
                           "D: stage C holds the probe level, so the beach set-up (U3 swash +0.7..+1.1 m) is fed from the inlet: about +0.5..+1.1 % of the "
                           "x 110-400 m window [estimate]; the judged window volume (vc_step Vwin) spans the full half width 0-140 m, side band included"],
                 consequence="a borderline H_volume failure makes next_D print 'health failure -> diagnose first' before any other rule",
                 option="decide before freezing whether the stage-C set-up volume counts as drift (e.g. report-only for stage C, or judge V minus the "
                        "period-mean set-up of the swash region); never after seeing the result", tag="measured / estimate; choice open"),
            dict(id="RV-D3", item="H_wall 2.5 h vs cfg max_hours 3.0 h (AM-D6)",
                 evidence=["the per-particle time rules ignore that D's grid footprint 412 x 140 m is 1.54 x DA1's 442 x 85 m and that the r5 surface is built over "
                           "the whole width before the y <= 95 m crop: +10-20 % is plausible [guess], i.e. about 2.2-2.6 h by the DA1 rule"],
                 consequence="H_wall may fail (health, reported only; next_D does not stop on it)", option="amend H_wall to 3.0 h before freezing, or accept the report",
                 tag="guess; choice open"),
            dict(id="RV-D4", item="precedence of decision_rules.after_DM1",
                 evidence=["g50_ana.next_D applies the list in order, so a run with P4b < 1.3 on all breakers but P5 on >= 2 and P2/P3 failing on >= 2 goes to DF1, "
                           "not to 'D negative'"],
                 option="state the intended precedence in the frozen text (list order as implemented, or 'D negative' first)", tag="chosen; choice open")],
        physics_numbers=dict(
            focal_zone="linear axis |A| >= 0.9 |A(x_f)| over x 160-300 m (DM1) / 172-300 m (DF1) on the slope, so the break point x 240 m (2|A|/h = 1.081 at h 11.03 m) "
                       "lies inside the focal zone; the crest passes x_f at t = nT and x 240 m at nT + 1.62 s (DM1) [computed]",
            widths="linear lateral FWHM of |A|: DM1 76 m (flat bed) -> 80 m at x_f -> 81 m at x 240 m (refraction lowers the oblique components, Kr down to 0.57); DF1 61 -> 64 "
                   "-> 65 m. A full +-90 deg fan cannot go below 2 x 1.52/k0 = 72 m (T 12) / 58 m (T 10): 1-2.5 Hc (10-24 m) is reachable only as the width of the "
                   "overturning part (threshold effect), never as the linear crest width [computed]",
            reflection="Battjes Kr ~ 0.1 xi0^2: focused centre (H ~12 m, xi0 0.43) 0.02, side rows (H 3-5 m, xi0 0.67-0.87) 0.05-0.08; the returning waves are "
                       "relaxed away in the inlet/side bands (incident-only target) but they enter the x 110-160 m gauges, so inlet.json Kr (Goda-Suzuki on the axis) "
                       "and c are not interpretable for the directional field [computed / literature]"))
    P = freeze_step(P, pre)
    os.makedirs(GC.PLAN_DIR, exist_ok=True)
    json.dump(P, open(GC.PLAN_DRAFT, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print("wrote", GC.PLAN_DRAFT, GC.sha256_file(GC.PLAN_DRAFT))


if __name__ == "__main__":
    main()
