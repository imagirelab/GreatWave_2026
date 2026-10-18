# -*- coding: utf-8 -*-
"""FLIP54 K54: the FROZEN PLAN of the 2D concave-bed strip screen (py -3.10 -B; numpy only). 2026-10-18 written new (Claude, FLIP54
builder K) by adapting flip49/g49_planB.py (plan_B2 / freeze_B2: queue, frozen criteria, gate, honesty, refuse-once-a-run-exists; FROZEN,
read only). Writes Unity/Build/FLIP54/k54/plan/plan_K54_frozen.json + .sha256 BEFORE any K54 run; g54_chain.py starts a strip only when
the plan's sha256 holds, and g54_pcfg.py names it in every cfg.

usage:
  py -3.10 -B g54_plan.py show                         print the plan that would be frozen (json; writes nothing)
  py -3.10 -B g54_plan.py freeze [--force=1 --reason=...]   write the plan + .sha256; refuses when it exists, and always once a K54 run exists
"""
import os, sys, json, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np            # noqa: E402
import g54_common as C        # noqa: E402

DESIGN_FILES = ("Unity/Build/FLIP54/ideas/bed_angle/bed_candidates_big_hollow.json", "Unity/Build/FLIP54/ideas/bed_angle/bedscreen2.json",
                "Unity/Build/FLIP54/ideas/incoming_sea/candidates_incoming_sea.json", "Unity/Build/FLIP54/ideas/incoming_sea/out_hood_vs_chord.txt",
                "Unity/Build/FLIP54/ideas/incoming_sea/out_front_trough_DM1A_vs_DFGB2E.txt",
                "Unity/Build/FLIP54/ideas/numerics_resolution/series_DFGB2E_p1_y0p5.jsonl")


def plan():
    arms = {}
    for a, (hL, s2, sh, T, role, lab) in C.ARMS.items():
        arms[a] = dict(role=role, label=lab, T_s=T, pg_hL=hL, pg_s2=s2, shelf_h=sh, landmarks=C.landmarks(a), spec=C.spec_for(a),
                       sponge_Kr_1D=C.sponge_kr(T, sh), iribarren_report=C.iribarren(a),
                       H_rule={"K0p": "H_GUESS", "A12": "H_K0 x goda_ratio(T 9.33 -> 12 s, h_b 8.7 m)"}.get(a, "H_K0 (calibrated once, frozen)"))
    sc = {a: dict(ok=C.bed_selfcheck(a)["ok"]) for a in C.ARMS}
    design = {}
    for p in DESIGN_FILES:
        q = C.REPO + "/" + p
        design[p] = C.sha256_file(q)[:16] if os.path.exists(q) else None
    return dict(
        name="K54: 2D concave-bed strip screen for the big hollow (FLIP54 builder K)",
        why=("user 2026-10-18 evening: 最关键的问题我觉得还是卷不出大空洞 (the big hollow does not curl). The FLIP54 design workflow (records in "
             "Unity/Build/FLIP54/ideas) found that DFG-2B's centre section already curls a near print-sized hollow 0.33-0.58 s after the pv53 "
             "frame (f1480-1483 y 0.5 m: hood 0.14-0.19, lip 0.29-0.30, cavity air 0.22-0.28 eta_c^2; print 0.23) [measured], but late (foot "
             "0.54-0.65 vs print 0.25) and narrow; root cause on 1:10: xi_b 0.30/0.40 (spilling-plunging border), the crest is depth-limited "
             "and travels 26-32 m before the lip [computed]. Best lever: a CONCAVE bed - 1:10 down to h 12.5-14 m, then 1:6-1:8 onto a 7-7.5 m "
             "terrace (front trough 0.59-0.82 eta_c, xi_b 0.43-0.58, curl ~1 s earlier on a taller crest) [computed]; predicted hood 0.10-0.20, "
             "lip 0.30-0.36 [guess]; P ~0.3. Screen first in 2D strips (this plan)."),
        design_inputs=design,
        rules_kept=("gravity, the bed and the incoming waves only (no shaping force, Q39); numbers with reasons and tags; the user judges the "
                    "look; nothing here is shown as the 3D wave"),
        tank=dict(scene=C.HIP_REL, scene_sha256=C.HIP_SHA256, scene_note="FLIP49's g49_tank.hiplc unchanged and never saved; its CTRL carries h0, "
                  "the FLIP49 two-slope bed (pg_hL / pg_s2 / shelf_h), the Fenton inlet band and the exit sponge (abs_on, xa0, abs_sigma, abs_pow)",
                  box=dict(Lx=C.LX, zb=C.ZB, W=C.W_STRIP, dp=C.DP, grid_m=2 * C.DP, floor_pad_cells=2), h0=C.H0, x_toe=C.X_TOE, slope="1:10",
                  inlet_band_m=[0.0, C.IN_X1], wall_taper_m=C.WALL_TAPER, x_p=C.X_P, ramp="2 T (half cosine)",
                  exit_sponge=dict(x_m=[C.XA0, C.LX], sigma=C.EX_SIGMA, pow=C.EX_POW, Kr_1D_max=0.10,
                                   Kr_1D={"T9p33": {("h%s" % C.tag(h)): C.sponge_kr(C.T_MAIN, h) for h in (6.0, 7.0, 7.5)},
                                          "T12": {("h%s" % C.tag(h)): C.sponge_kr(C.T_A12, h) for h in (6.0, 7.0, 7.5)}},
                                   tag="computed (Peric & Abdel-Maksoud 2018 1D, flip45 r45_gen_numbers.reflection)"),
                  drift=dict(stage="A", window_m=list(C.VOL_X), note="as DFG-2B and DM1A (whole-tank volume held)"),
                  records="hf + centre section r2 every frame, r6 gauges x 110 / 128 / 160 m and levels; no r4 / r5",
                  t_end_s=C.T_END, judged_k=list(C.JUDGED_K),
                  bed_selfcheck=sc),
        arms=arms, launch_order=list(C.ARM_ORDER), test_arms=list(C.TEST_ARMS),
        wave=dict(kind="periodic Fenton stream-function wave (N 40, zero mean mass flux) generated at h0 19 m", T_main_s=C.T_MAIN, T_A12_s=C.T_A12,
                  H_guess_m=C.H_GUESS, H_guess_note=C.h_guess_note(),
                  H_calibration=dict(
                      rule=("ONCE ONLY: run K0p (= K0's bed) at H_GUESS; h_b = median still depth at the FLIP49 onset over judged k2-k4 (fewer than 2 "
                            "judged: all breakers k >= 2). If 8.4 <= h_b <= 9.0 m the pilot IS K0 (no rerun). Else H_K0 = H_GUESS x (8.7 / h_b)^(1/0.69), "
                            "clamped to [0.85, 1.15] x H_GUESS, rounded to 0.01 m, and K0 is run once at H_K0 - frozen whatever its h_b. H_K0 is then used "
                            "for K1-K5; A12 uses H_K0 x goda_ratio(9.33 -> 12 s, h_b 8.7 m)"),
                      exponent=C.H_EXP, exponent_source="campaign-B strips BS0 / BS1: realized H 7.15 / 9.43 m -> h_b 8.07 / 9.78 m [measured]",
                      band_m=list(C.H_BAND_HB), target_m=C.H_TARGET_HB, clamp=list(C.H_CLAMP), q_max=C.Q_MAX,
                      goda_ratio_9p33_to_12=C.goda_ratio(C.T_MAIN, C.T_A12)),
                  in_gain="1.0 (the calibration absorbs the inlet loss; the gauges report the realized H)"),
        metrics=dict(
            ruler="pv53: g46 r2_mask -> STUDY52 s52_shape.measure_mask -> d_shape_measure.pick, g47_video.score3 (Lc of Ctx49), every frame",
            breakers="FLIP49 event rule (g49_periodic_ana.find_breakers: front face first vertical, k numbered in time order); judged k2, k3, k4",
            window="[t_on - 2.0 s, t_on + 3.5 s] along the pv53 crest track (top of the centre hf row, 3-point median; -1.0..+2.5 m / frame "
                   "forward, -2.5..+1.0 m backward)",
            eligible="eta_c >= 0.6 x the largest eta_c in the window, no ruler error",
            first_lip="first eligible frame with lip_thick_mid > 0",
            pre_touchdown="eligible frames before the first frame after the first lip with chord > 120 deg; earlier frames with chord > 120 deg dropped",
            hood78="max hood_area over pre-touchdown frames with chord <= 78 deg (0 if none)",
            hood14="first pre-touchdown frame with hood_area >= 0.14: eta_c (m) and front foot (front_x01_rel)",
            onset=("first frame on the hf crest track in [t_on - 6 s, landing] with crest / still depth >= r; r = 0.76 (task), or the first of "
                   "0.70 / 0.65 / 0.60 that K0 reaches at or before its first lip on >= 2 judged breakers when K0 never does at 0.76 (the same r "
                   "for every arm, chosen on K0 alone); FLIP49 BS0 (2D, h0 17 m, T 12 s, 1:10) reached only 0.57-0.74 at its first lip [measured "
                   "with this code 2026-10-18]"),
            onset_to_lip="(first lip - onset) / 24 s (negative when the lip comes first)",
            max_hood="max hood_area over the pre-touchdown frames: its chord and its front-trough depth",
            front_trough="centre hf row, lowest point in (x_c, x_c + 45 m]: (still depth there + eta there) / eta_c",
            cavity_air="air under overturned columns x_c - 0.5..+1.5 eta_c, top run above 0.2 eta_c, / eta_c^2 (series_check.py; print 0.23)",
            hollow_instant="report (R0 rule): eligible frame with the largest cavity air with chord 50-100 deg and lip >= 0.30",
            hood_bands="max hood (> 0) at chord 50-80 and 80-100 over all eligible frames (hoodchord.py rule) - the A12 validity",
            medians="median over the judged breakers that have a value; >= 2 values needed (else None)",
            tool="Tools/GWWaveGen/flip54/g54_ana.py measure"),
        criteria=dict(
            reference="K0 (the calibrated control; if the pilot is K0, the pilot run)",
            pass_bar=dict(
                i="median hood78 >= K0's",
                ii="median eta_c at the first hood >= 0.14 frame >= 1.08 x K0's (K0 with < 2 such breakers: its median eta_c at the max-hood frame)",
                iii="median front foot at that frame <= K0's - 0.10 (same K0 fallback: its foot at the max-hood frame)",
                iv="median onset -> first lip <= K0's - 0.5 s (onset rung r chosen on K0; K0 reaching no rung: untestable, dropped)",
                v="no wall: median chord at max hood <= 100 deg AND median front-trough depth there >= 0.55 eta_c (absolute)"),
            arm_passes="every testable item (i)-(v) true; an arm whose median is missing for a testable item fails it; < 2 judged breakers: fails",
            report_only=["(v) against K0's chord (2D plungers overturn on a steep face)", "cavity air max, hollow instant, best score3, h_b, H realized, Kr"],
            validity_A12=("A12 must reproduce DM1A's ordering: median hood at chord 50-80 < median hood at chord 80-100, AND the ordering on >= 2 "
                          "judged breakers (DM1A n2-n5: 0.080<0.174, 0.159<0.236, 0.132<0.249, 0.161<0.179 [measured, ideas/incoming_sea/"
                          "out_hood_vs_chord.txt])"),
            decision=dict(
                STRIPS_UNTRUSTED="A12 invalid -> the strips are untrusted; recommend K4 straight to 3D (task rule), report only",
                PASS="valid and >= 1 of K1-K4 passes -> the passing arm with the largest median hood78 (ties: shorter onset->lip, then higher "
                     "eta_c at hood14) is the 3D candidate with the DFG-2B-V sea (one change: the bed); report only - the user decides",
                NONE_PASS="valid and none of K1-K4 passes -> no 3D bed recommended from the strips; numbers shown; the user decides",
                K0_INCOMPLETE="K0 with < 2 judged breakers -> no decision; diagnose the strip",
                K5="wall-side bracket: measured and reported (does it fail (v)?), never recommended"),
            health_report=("Kr (Goda & Suzuki at x 110 / 128 m) <= 0.10; stage-A volume max |V/V0 - 1| <= 1 %; >= 2 judged breakers; judged onsets "
                           "at x >= 160.25 m - reported with the verdict, a flag does not change the bar")),
        predictions=dict(K1_K4=dict(hood="0.10-0.20 [guess]", lip="0.30-0.36 [guess]", P_any_arm_passes=0.3, source="FLIP54 ideas synthesis (task)"),
                         K5="expected to fail (v) (wall side: steep 1:3 face onto 6 m gave front trough 0.38-0.49 eta_c in 3D) [guess]",
                         K0_v_risk=("2D plungers on 1:10 reached their max hood at chord 114-118 deg just before touchdown (FLIP49 BS0 strip measured "
                                    "with this code 2026-10-18) [measured]: item (v) is absolute (task), so K0 itself may fail it and NONE_PASS can "
                                    "follow from (v) alone")),
        honesty=["2D strips (half width 6 m) are not the 3D focused wave: they screen the bed's effect on one breaker shape; the 3D DFG-2B centre "
                 "curl is narrower and later than a 2D strip's", "the periodic Fenton wave is not DFG-2's focused group (the task chose it); "
                 "T 9.33 s is DFG-2's longest layer", "the bar is the task's, written before any run; its operational definitions (window, "
                 "touchdown, onset ladder) are this plan's and are frozen with it", "AI self-assessment: the user judges the look"],
        outputs=dict(strips=C.RUNS_ROOT.replace(C.REPO + "/", ""), calibration=C.CALIB.replace(C.REPO + "/", ""),
                     verdict=C.VERDICT_DIR.replace(C.REPO + "/", "") + "/verdict_K54.json, K54_sheet.png, K54_sections.mp4",
                     status="Unity/Build/FLIP54/_logs/auto_K54_status.txt ('K54 ...', last 'K54 FINISHED ...')",
                     launcher="G:/research/Wave Simulation/_tools/auto_K54.py (not started by its author)"),
        module_shas=C.module_shas(),
        tags="[measured] FLIP records, [computed] formulas, [literature], [guess], [chosen], [calibrated]")


def freeze(force=False, reason=None):
    runs = C.runs_exist()
    if runs:
        raise SystemExit("K54 runs exist (%s): the plan is never re-frozen after a run" % ", ".join(runs[:4]))
    if os.path.exists(C.PLAN) and not force:
        raise SystemExit("%s exists; --force=1 --reason=... only before any run" % C.PLAN)
    p = plan()
    p["frozen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if force:
        old = C.jload(C.PLAN) or {}
        p["refrozen"] = dict(reason=reason or "(none given)", previous_frozen_at=old.get("frozen_at"),
                             previous_sha256=(C.sha256_file(C.PLAN) if os.path.exists(C.PLAN) else None))
    C.jdump(p, C.PLAN)
    sha = C.sha256_file(C.PLAN)
    with open(C.PLAN + ".sha256", "w", encoding="utf8") as fh:
        fh.write(sha + "  plan_K54_frozen.json\n")
    return p, sha


def main(argv):
    opt = {}
    pos = []
    for a in argv[1:]:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opt[k] = v or "1"
        else:
            pos.append(a)
    cmd = pos[0] if pos else "show"
    if cmd == "show":
        print(json.dumps(C.clean(plan()), ensure_ascii=False, indent=1))
        return 0
    if cmd == "freeze":
        p, sha = freeze(force=bool(opt.get("force")), reason=opt.get("reason"))
        print(json.dumps(dict(plan=C.PLAN, sha256=sha, frozen_at=p["frozen_at"]), ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
