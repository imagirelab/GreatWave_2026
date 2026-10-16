# -*- coding: utf-8 -*-
"""FLIP50 (option D): write the frozen-plan DRAFT Unity/Build/FLIP50/plan/plan_D_draft.json (py -3.10 -B). 2026-10-15 written new (Claude).
Source: the design step's draft Tools/GWWaveGen/flip50/plan_D_draft.json (read only; criteria were copied there unchanged from
Unity/Build/FLIP49/plan/plan_A_frozen.json). This tool keeps design, criteria, decision rules, registered predictions and honesty, and adds:
  - implementation (files with sha256-16, scene, build check, tables with sha256, cfg ids, commands, numpy check summary)
  - amendments_vs_design_draft (implementation choices made while coding, each with its reason and tag; no threshold is changed)
  - the updated cost (DA1 launch 2 measured 3.79 s/frame) and record windows.
  - review_pre_freeze (2026-10-15 adversarial review): the open decisions RV-D1..D4 (end-wall run-up, H_volume under stage C, H_wall,
    rule precedence) with their evidence, and the computed physics numbers (focal zone, widths, reflection). Nothing is decided here.
The orchestrator freezes it (sha256) with `py -3.10 -B g50_pcfg.py freezeD` after `x50_build.py` reports all_ok. Nothing here runs Houdini.
usage: py -3.10 -B g50_planD.py   (needs `g50_pcfg.py check` first: reads plan/precheck_D.json)
"""
import os, sys, json, copy, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g50_common as GC     # noqa: E402
import g50_pcfg as PC       # noqa: E402


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
    os.makedirs(GC.PLAN_DIR, exist_ok=True)
    json.dump(P, open(GC.PLAN_DRAFT, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print("wrote", GC.PLAN_DRAFT, GC.sha256_file(GC.PLAN_DRAFT))


if __name__ == "__main__":
    main()
