# -*- coding: utf-8 -*-
"""FLIP55: write the FROZEN plan Unity/Build/FLIP55/plan/plan_F55_frozen.json (+ .sha256) BEFORE any FLIP55 run (py -3.10 -B; no Houdini).
2026-10-19 written new (Claude). Refuses once a FLIP55 run folder holds a chain / run record (f55_common.runs_exist), and refuses when a
precheck fails, the chain copy differs from its recipe or the DFG-2B-V hollow baseline does not reproduce R0's series.
What it freezes: the options (A375 runnable now; C2 / C2ID design cfgs) with each stage's cfg sha16, cost and slot needs; DFGB4's gates and
co-equal criteria verbatim (the validity rules of the full A375 run; inherited by the C2 parent) plus the nest gates GN1-GN3; the hollow
quantities, the DFG-2B-V baseline (numbers + file sha256) and the pre-registered reading; the execution (launcher, approval file, slot, watchdog,
resumes, analysis per stage); the machine snapshot and the user's levers; the sha256 of every flip55 tool, of auto_F55.py and of every frozen
tool used unchanged; the risks.
usage: py -3.10 -B f55_plan.py freeze [--force-refreeze-no-runs]    (writes plan_F55_frozen.json + .sha256)
       py -3.10 -B f55_plan.py show                                 (prints the plan that would be written; writes nothing)
"""
import os, sys, json, time, hashlib, subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import f55_common as C               # noqa: E402
import f55_pcfg as PC                # noqa: E402


def r54_summary():
    v = C.jload(C.R54_VERDICT)
    t = v["table"]
    pick = {k: {arm: dict(dp0p5=t[k][arm]["dp0p5"], dp0p25=t[k][arm]["dp0p25"], rel=t[k][arm]["rel"]) for arm in ("K0", "K4")}
            for k in ("air_max_pre", "hood_max", "hood78") if k in t}
    return dict(file=C.rel(C.R54_VERDICT), sha256=C.sha(C.R54_VERDICT), verdict=v["verdict"], gain_quantities=v["reading"]["gain_quantities"],
                flips=v["reading"]["flips"], table=pick, per_breaker=v.get("per_breaker"), run_records=v.get("run_records"), report=v.get("report"),
                setting="2D strips, half width 6 m, T 9.33 s, H 7 m; K0 straight 1:10 onto a 7 m shelf, K4 1:10 to 12.5 m then 1:7; dp 0.5 vs 0.25 m, "
                        "everything else identical [measured]")


def scaled_expectation():
    """[computed] R54's 2x gains log-scaled to the A375 1.33x step: g(r) = (1 + g2)^(log2 r) - 1."""
    import math
    v = C.jload(C.R54_VERDICT)["table"]
    r = math.log2(0.5 / 0.375)
    out = {}
    for k in ("air_max_pre", "hood_max"):
        out[k] = {arm: (1.0 + v[k][arm]["rel"]) ** r - 1.0 for arm in ("K0", "K4")}
    return dict(rule="(1 + R54 gain at 2x)^(log2 1.333) - 1 [computed; assumes the gain is a power of the refinement]", log2_refinement=r, gains=out)


def build():
    pc = PC.check_all(dry=True)
    if not pc["ok"]:
        raise SystemExit("a precheck failed: %s" % json.dumps({k: v["precheck"]["reason"] for k, v in pc["options"].items()}, ensure_ascii=False))
    r = subprocess.run(["py", "-3.10", "-B", HERE + "/f55_mkcopy.py", "--check"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("f55_chain.py differs from its recipe: run f55_mkcopy.py")
    bl = C.jload(C.BASELINE)
    if not bl.get("reproduction_ok"):
        raise SystemExit("the DFG-2B-V hollow baseline does not reproduce r0_hollow.json's series")
    dfgb4 = C.jload(C.DFGB4_PLAN)
    if C.sha(C.DFGB4_PLAN) != C.DFGB4_PLAN_SHA256:
        raise SystemExit("plan_DFGB4_frozen.json changed")
    options = {}
    for opt, stages in (("A375", ("g1", "full")), ("C2", ("g1",)), ("C2ID", ("g1",))):
        o = dict(C.OPTIONS[opt])
        st_out = {}
        box = None
        for st in stages:
            c = PC.make(opt, st)
            box = c["box"]
            cs = c["precheck"]["cost"]
            st_out[st] = dict(run_id=c["run_id"], cfg_file=C.rel(PC.cfg_path(opt, st)), cfg_sha16=PC.sha16({k: v for k, v in c.items() if k not in ("precheck", "f55")}),
                              f_start=c["f_start"], f_end=c["f_end"], t_end_s=c["t_end_s"], max_hours=c["max_hours"],
                              particles_model=cs["particles_model"], particles_peak=cs["particles_peak"], growth=cs["growth"],
                              ws_fit_gb=cs["ws_fit_gb"], ws_prop_gb=cs["ws_prop_gb"], commit_gb=cs["commit_gb"], commit_need_gb=cs["commit_need_gb"],
                              time_h=cs["time_h"], time_rule=cs["time_rule"], ckpt_gb_each=cs["ckpt_gb_each"], n_ckpt=cs["n_ckpt"], disk_gb=cs["disk_gb"],
                              disk_need_gb=cs["disk_need_gb"], parent_export_h=cs.get("parent_export_h"), parent_export_gb=cs.get("parent_export_gb"),
                              seeded_still_level_m=cs["seeded_still_level_m"], water_m3=cs["water_m3"],
                              diff_vs_DFGBV=c["precheck"]["diff_vs_DFGBV"], precheck_checks=c["precheck"]["checks"],
                              runnable=bool(c["precheck"].get("runnable", True)),
                              tags=dict(particles="computed (numpy, the scene's seeding rule)", memory="computed from measured anchors", time="computed",
                                        disk="computed"))
        o.update(dp=o["dp"], box=box, stages=st_out)
        options[opt] = o
    options["A375"]["tied"] = C.A375_TIED
    options["A375"]["execution"] = C.A375_EXEC
    options["A375"]["named_differences"] = ("resolution-tied only: dp 0.375; the box rounded to whole 0.75 m voxels (W 140.25, Lx 412.5, top 17.625 m); "
                                            "zb -19.125 m so the seeded still level is exactly 0 (with -19 m it would be +0.125 m, a level step against the "
                                            "band target); records on the 0.75 m grid (centre section r2 at y 0.375 m instead of 0.5 m). Execution: max_hours "
                                            "6 h per chain; the group-1 stage ends at frame 1657.")
    options["A375"]["expected"] = dict(scaled_from_R54=scaled_expectation(), note=(
        "a 1.33x step: the log-scaled R54 gains are air +37..+52 % and hood +21..+25 % [computed], i.e. air likely above and hood at or below the "
        "+25 % bar; the 3D hollow (hood only over |y| <= ~6.5 m [measured R0]) may gain less than the 2D strips [guess]"))
    options["A375"]["risks"] = ["G4 (kp x crest <= 0.40) had a 0.002 margin in DFG-2B-V (0.398) and a finer run is steeper: G4 may fail at the full stage "
                                "[guess]", "the inlet-only n5 calibration (0.3084 rad) was fitted on the 0.5 m realisation: G2f may drift [guess]",
                                "the side band's chi runs over 45.25 m (W 140.25 m) and the table target is clamped at y 140 m in the outer 0.25 m",
                                "hf / r2 / r4 / r5 at 0.75 m: the R0 / pv53 ruler resamples to 0.05 m (spacing-aware) but was never run on a 0.75 m grid"]
    c2 = PC.make("C2", "g1")["precheck"]["cost"]; cid = PC.make("C2ID", "g1")["precheck"]["cost"]
    options["C2"]["group1_total_h"] = [c2["parent_export_h"] + cid["time_h"][0] + c2["time_h"][0], c2["parent_export_h"] + cid["time_h"][1] + c2["time_h"][1]]
    options["C2"]["engineering"] = dict(estimate_days=[1.5, 2.5], tag="guess", not_written=list(C.NEST_TOOLS), interface=(
        "f55_nest.py export | run C2ID | gates C2ID | run C2 | analyse C2, each printing a final json line with \"ok\"; x55_nest_build.py writes "
        "_logs/build_check55_nest.json (all_ok) after a short 0.5 m smoke; an amendment AM-F55-NEST in plan/amendments.jsonl registers their "
        "sha256 (code_sha256 {path: sha}) BEFORE any nest run; the cfgs, gates and reading below do not change"))
    options["C2"]["gates_nest"] = dict(
        GN1=dict(rule="the 0.5 m identity nest C2ID reproduces the parent DFG-2B-V in x 200-300 m, |y| <= 20 m, group 1: converged Hc within +-2 %, "
                      "crest x_pk within +-1.5 m, t_conv and the first-lip time within +-0.25 s, R0 hood_max and air_max within +-20 %", tag="chosen"),
        GN2=dict(rule="band leakage: rms |eta_nest - eta_parent| along the band inner edges (x 195-197 m, y <= 45 m; y 43-45 m, x >= 195 m) <= 5 % of the "
                      "parent's converged Hc, for t before the first lip", tag="chosen"),
        GN3=dict(rule="volume: the nest's water volume within +-2 % of the parent's over the same box at every recorded frame", tag="chosen"),
        order="GN1-GN3 on C2ID must pass before the 0.25 m nest C2 runs; a failure = no reading (fallback A375)")
    options["C2"]["expected"] = dict(note="the full 2x step R54 tested: R54 gained air +113..+174 %, hood +59..+71 % in 2D [measured]; the 3D nest is "
                                          "expected to gain less (lateral spreading, hood only over |y| <= ~6.5 m) [guess]")
    options["C2"]["risks"] = ["reflection / seam at the relaxation bands (x 180-195, y 45-60): GN1 / GN2 decide",
                              "the nest reproduces only the last ~85 m of shoaling + breaking at 0.25 m; propagation from the generator stays 0.5 m",
                              "group 1 only unless extended (the Unity hero needs groups 1-3: ~2.4-3.4 h more nest + 1.6 h parent export [computed])"]
    options["not_prepared"] = dict(
        B=dict(what="dp 0.25 m full tank", particles_M=[43.0, 49.0], ws_gb=[25.0, 56.0], time_h_group1=[15.0, 20.0], time_h_full=[31.0, 37.0],
               why="memory above the free commit (17 GB) by 8-39 GB even with every app closed in the proportional model; 15-37 h; not feasible "
                   "before 10/29 [computed, FLIP55 design]"),
        D1=dict(what="surface oversampling 1.5 -> 3 at dp 0.5 m (1 m grid)", why="pressure / velocity stay on the 1 m grid; R54's lip at hood max is "
                                                                                  "1.4-1.75 m (~1.5-2 voxels): extra particles smooth the mesh, they do not resolve the jet [guess]"),
        D3=dict(what="narrow band at dp 0.25 m", why="a solver-mode change (DFG-2B-V ran donarrowband 0): a numerical named difference with volume (G5) "
                                                     "and deep-orbital risk; 7-10 h for group 1 [computed / guess]"))
    hollow = dict(
        ruler=("Unity/Build/FLIP54/r0/r0_hollow.py (frozen; rule r0_rule_registered.json sha256 %s) = pv53's ruler on the centre section r2: g46 "
               "r2_mask -> STUDY52 measure_mask -> score3; cavity air = the R0 column rule (= R54 air_max_pre's rule)" % C.sha(C.R0_RULE)),
        tool="Tools/GWWaveGen/flip55/f55_hollow.py",
        window=("PRIMARY = R0's extended window [f_max - 36, f_max + 96] frames (t_max - 1.5 .. + 4.0 s) of each pv53 group; the pv53 window "
                "[f_max - 36, f_max + 72] values are reported with the suffix _pv. Why: DFG-2B-V group 1's R0 hollow instant (f 1483) sits at the "
                "pv53 window end (1484, R0 flag 'edge'): the cavity still grows there [measured]"),
        alive="frames with the section crest eta_c >= 0.6 x Hc_ref (pv53 crest floor; the 3D stand-in for R54's 'before touchdown')",
        quantities=dict(air_max="max cavity air / eta_c^2 over the alive frames (GAIN KEY)", hood_max="max hood_area over the alive frames (GAIN KEY)",
                        hood78="max hood_area with chord <= 78 deg (0 if none)", chord_at_hood_max="deg", lip_at_hood_max="lip_thick_mid / eta_c",
                        lip_at_hood_max_m="m (lip x eta_c)", eta_at_hood_max="m", hi_air="R0 hollow-instant air / eta_c^2", hi_air_m2="m^2",
                        hi_lip_m="m", hi_chord="deg", best_score3="pv53 most print-like instant (lower = closer to the print)", best_lip="pv53"),
        baseline_file=C.rel(C.BASELINE), baseline_file_sha256=C.sha(C.BASELINE), baseline_reproduces_r0_hollow_json=bl["reproduces_r0_hollow_json_DFG2BV"],
        baseline_DFGBV={int(k): {kk: v.get(kk) for kk in ("air_max", "hood_max", "hood78", "chord_at_hood_max", "lip_at_hood_max_m", "eta_at_hood_max",
                                                           "hi_air", "hi_air_m2", "hi_lip_m", "hi_chord", "best_score3", "best_lip", "n_alive",
                                                           "air_max_pv", "hood_max_pv")} for k, v in bl["groups"].items()},
        baseline_r4_note="r2 from the judged DFG-2B-V run (every frame); r4 from the same run (every 3rd frame in the windows = the A375 layout); the "
                         "r4-based side projections are report only")
    reading = dict(
        gain=C.GAIN, gain_keys=list(C.GAIN_KEYS), report_keys=list(C.REPORT_KEYS),
        rule=("RESOLUTION_MATTERS_3D iff for air_max or hood_max: group-1 stage -> group 1's change vs the baseline >= +25 %; full stage -> the median "
              "over groups 1-3 of the change >= +25 % AND at least 2 groups each >= +25 %. Otherwise NOT_SHOWN (report only). INCOMPLETE when a group "
              "has no value on either side. NO_READING_*_CHANGED when the plan sha, the baseline file sha or the ruler sha (r0_hollow.py, pv53.py) "
              "differs from this plan. Baseline: A375 -> DFG-2B-V (this file); C2 -> the 0.5 m identity nest C2ID (same nest; DFG-2B-V beside it)."),
        meaning=dict(
            RESOLUTION_MATTERS_3D="the 3D hollow is resolution-limited as in 2D: the hero needs the finer particles (C2 for groups 1-3 before 10/29, or "
                                  "A375 full) - the look is then the user's call from the renders",
            NOT_SHOWN="no +25 % change at this step: for A375 (x1.33) this does NOT refute R54 (x2); for C2 (x2) the 3D hollow is limited by "
                      "something else (lateral spreading of a crest only ~13 m wide, the 1:10 bed): a negative but useful result",
            INCOMPLETE="no reading (a group without frames on either side)"),
        report_only=("toward the print: chord at hood max and hood78 (R54 0.25 m moved the chord at max hood 113 -> 84 deg in 2D); the lip in metres; "
                     "the R0 hollow instant; pv53 best score3; the Unity print view and the video (the USER judges the look)"),
        group1_gates="REPORT ONLY at the group-1 stage: run_complete / groups3 / G2f (t 49-105 s) cannot pass on a 69 s record; the full stage "
                     "applies DFGB4's gates as frozen")
    pl = dict(
        status="FROZEN", plan="F55", name="FLIP55: the 3D resolution run of the hero DFG-2B-V",
        campaign="FLIP55 (after R54 RESOLUTION_MATTERS)",
        tags_legend={"[measured]": "FLIP / machine records", "[computed]": "formulas from measured anchors", "[guess]": "judgement",
                     "[chosen]": "design choices"},
        trigger=dict(R54=r54_summary(), user="the user's priority: the BIG HOLLOW; the 0.25 m 3D run is reserved for after the SUPERVISOR's approval "
                                             "(user decisions Q57 / Q64): this plan PREPARES only, nothing is started",
                     approval=("the launcher does nothing until %s exists, written only by the main session from the user's own words (OPTION, "
                               "SCOPE, USER_WORDS)" % C.rel(C.APPROVAL))),
        reference=dict(run=C.rel(C.DFGBV_RUN), ready_cfg=C.rel(C.DFGBV_READY), ready_cfg_sha256=C.sha(C.DFGBV_READY),
                       run_json_sha256=C.sha(C.DFGBV_RUN + "/run.json"), chain_log_sha256=C.sha(C.DFGBV_RUN + "/chain.log"),
                       pv53=C.rel(C.DFGBV_PV53), pv53_sha256=C.sha(C.DFGBV_PV53), plan_DFGB4=C.rel(C.DFGB4_PLAN), plan_DFGB4_sha256=C.DFGB4_PLAN_SHA256,
                       judge=C.rel(C.DFGBV_RUN + "/g52b3/judge_DFGB4.json"), judge_sha256=C.sha(C.DFGBV_RUN + "/g52b3/judge_DFGB4.json"),
                       scene=C.rel(C.DFGB4_HIP), scene_sha256=C.DFGB4_HIP_SHA256, anchors=C.ANCHORS_TEXT),
        physics_rules=dict(dfgb4=dfgb4["physics_rules"], this_plan=("same sea, bed, energy, bands, solver and drift as DFG-2B-V; A375 changes only the "
                                                                    "particle size and its tied box keys; C2 changes only the particle size inside a nest "
                                                                    "driven by DFG-2B-V's own fields (no new force, no target shape)")),
        options=options,
        recommendation=("C2 (one-way 0.25 m nest of group 1): the only option that tests R54's full 2x step where the hollow forms, at today's memory "
                        "(working set ~7.0-7.3 GB, need 11.5 GB free commit) and ~1.3-1.6 h for group 1, after 1.5-2.5 days of engineering [guess]; "
                        "fallback A375 (zero new Houdini code, 3.5-4.7 h for group 1, need 15.6 GB free commit) if the engineering slips past ~10/22 "
                        "or GN1 fails; B / D not prepared"),
        gates=dict(dfgb4_criteria=dfgb4["criteria"], source=C.rel(C.DFGB4_PLAN), source_sha256=C.DFGB4_PLAN_SHA256,
                   applicability=dict(A375_g1="REPORT ONLY (69 s record): G1 table / build / precheck, G4, G5 meaningful; G2f (t 49-105 s), G3P "
                                              "(3 groups), G6 per group, run_complete and groups3 are not decided at this stage",
                                      A375_full="DFGB4's gates and co-equal criteria as frozen there (the judge g52b3_ana.py unchanged); the hero class "
                                                "VALID_DFGB2_LIKE_HERO_CANDIDATE replaces nothing automatically (the user decides)",
                                      C2="the parent's gates (DFG-2B-V valid by DFGB4) + GN1-GN3; G6 inside the nest is reported")),
        hollow=hollow, reading=reading,
        execution=dict(
            launcher=C.AUTO, start='py -3.10 -B "%s"' % C.AUTO, started_by_author=False, approval_file=C.rel(C.APPROVAL),
            approval_format="OPTION: A375|C2 (required); SCOPE: group1|full (default group1); USER_WORDS: <the user's own words> (required); DATE / BY",
            status=C.rel(C.STATUS) + " (prefix 'F55 ', final '<date> <time> F55 FINISHED ...', also on exceptions)", brake=C.rel(C.STOPF),
            simulate='py -3.10 -B "%s" --simulate[=scenario.json]' % C.AUTO, test_rules='py -3.10 -B "%s" --test-rules' % C.AUTO,
            slot=("no hython, no pipeline process, no Unity -batchmode, free commit >= the stage's commit_need_gb, G: free >= disk_need_gb, on 3 "
                  "consecutive 60-s polls; gives up after 48 h"),
            watchdog="free commit < 3 GB on 2 polls, or the brake file -> <run>/STOP (the chain stops before its next launch; nothing is killed)",
            resumes="crash / stale / watchdog stop: up to 2; max_hours stops: up to --cap-resumes (default 2), each from the last checkpoint",
            analysis=dict(A375_g1=["f55_ana.py judge (report)", "pv53.py run --lockwait 120 (retry --no-unity)", "f55_ana.py coequal (report)",
                                   "f55_hollow.py measure --groups=1", "f55_hollow.py verdict --stage=g1 (THE reading)", "f55_ana.py video"],
                          A375_full=["f55_ana.py judge (DFGB4 gates)", "pv53.py run", "f55_ana.py coequal (co-equal verdict)",
                                     "f55_hollow.py measure (groups 1-3)", "f55_hollow.py verdict --stage=full", "f55_ana.py video"],
                          C2=["f55_nest.py export", "f55_nest.py run C2ID", "f55_nest.py gates C2ID (GN1-GN3)", "f55_nest.py run C2",
                              "f55_nest.py analyse C2", "f55_hollow.py verdict <C2> --stage=g1 --base=<C2ID>/f55/hollow_F55.json"]),
            chain=("Tools/GWWaveGen/flip55/f55_chain.py = flip52b3/g52b3_chain.py with the import path and the Houdini temp folder (FLIP55) replaced "
                   "(f55_mkcopy.py, counted); it launches the FROZEN flip52b3/g52b3_run.py; the start gate needs this plan's .sha256"),
            no_temp_paths=True),
        machine=dict(snapshot=dict(zip(("free_commit_GiB", "commit_limit_GiB", "free_phys_GiB"), C.commit_gb()), G_free_GB=C.free_disk_gb("G:/"),
                                   C_free_GB=C.free_disk_gb("C:/"), D_free_GB=C.free_disk_gb("D:/"), F_free_GB=C.free_disk_gb("F:/"),
                                   at=time.strftime("%Y-%m-%d %H:%M:%S"), tag="measured"),
                     levers=dict(close_apps=("private commit [measured 2026-10-19, FLIP55 design]: Edge 3.36, ChatGPT 2.86, NVIDIA Overlay 2.86, Discord "
                                             "1.70, QQ 1.32, Steam 1.22, Chrome 1.09, WeChat 1.06, cloudmusic 0.96 GB; total 16.4 GB -> free commit ~31-33 GB; "
                                             "~10 GB of commit is owned by no process"),
                                 pagefile=("the commit limit grows 1:1 with the pagefile (now C:\\pagefile.sys 1 GB); C: has ~16 GB free, so put a 32 GB "
                                           "pagefile on F: or D: (limit ~97 GB); admin rights and a reboot"),
                                 caveat="a pagefile adds commit, not RAM: a working set above free physical memory (~36-40 GB) pages and slows FLIP badly",
                                 who="the USER's action; no script changes them"),
                     needs={"A375": "15.6 GB free commit (today ~16-17 GB: tight; closing Edge / ChatGPT / Discord / QQ / Steam gives ~11 GB margin)",
                            "C2": "11.5 GB (no lever needed)", "C2ID": "8.2 GB"}),
        honesty=dict(prepared_only="nothing started; no Houdini run; the approval file not written; nothing committed",
                     not_written="the C2 nest tools (x55_nest_build.py, f55_nest.py): post-approval engineering; the launcher refuses C2 until they exist "
                                 "and AM-F55-NEST registers them",
                     not_done="no DOP-cache cut (the frozen runner has no parm for it), no commit (PrivateUsage) logging added (the runner is frozen)",
                     verdicts="AI self-assessment by frozen rules; the USER judges the look from the print view and the video"),
        risks=["the memory model is a fit to the measured runs (0.37-8.4 M particles): A375 (14.5 M peak) is a 1.7x extrapolation beyond the largest "
               "3D anchor; commit is not measured (the runner logs PeakWorkingSet only) [computed / guess]",
               "breaking-phase substeps at finer dp may exceed R54's 1-6 in 3D: time +30-50 % over the computed range [guess]",
               "A375 is a 1.33x step: the predicted hood gain sits at the +25 % bar (verdict may be ambiguous); air is predicted above it [computed]",
               "C2's nest boundaries (reflection, seam) are untested until GN1 / GN2; engineering 1.5-2.5 days [guess] is ~1/5 of the time to 10/29",
               "the 3D hollow may stay small at any resolution (crest only ~13 m wide in y): NOT_SHOWN would be a real, useful negative",
               "machine levers are the user's; the launcher only waits for the free commit and logs what is missing"],
        code_sha256=dict({("Tools/GWWaveGen/flip55/" + f): C.sha(HERE + "/" + f) for f in C.CODE_FILES}, **{C.AUTO: C.sha(C.AUTO)}),
        code_sha256_frozen_used={p: C.sha(C.REPO + "/" + p) for p in C.FROZEN_USED},
        inputs_sha256={C.rel(p): C.sha(p) for p in (C.DFGBV_READY, C.DFGBV_RUN + "/run.json", C.DFGBV_RUN + "/chain.log", C.DFGBV_PV53, C.R0_JSON,
                                                       C.R54_VERDICT, C.DFGB4_PLAN, C.DFGB4_BUILD_CHECK, C.BASELINE)},
        frozen_before_any_F55_run=True, frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    missing = [k for k, v in pl["code_sha256"].items() if v is None] + [k for k, v in pl["code_sha256_frozen_used"].items() if v is None]
    if missing:
        raise SystemExit("missing files: %s" % missing)
    return pl


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a or a[0] not in ("freeze", "show"):
        print(__doc__); sys.exit(1)
    ex = C.runs_exist()
    if a[0] == "freeze" and ex:
        raise SystemExit("FLIP55 runs exist (%s): the plan is not refrozen" % ex)
    pl = build()
    if a[0] == "show":
        print(json.dumps(C.clean(pl), ensure_ascii=False, indent=1)[:20000]); return
    if os.path.exists(C.PLAN):
        prev = C.sha(C.PLAN)
        pl["refrozen"] = dict(previous_sha256=prev, reason="re-frozen before any FLIP55 run (tools edited during preparation)")
    C.jdump(pl, C.PLAN)
    h = C.sha256_file(C.PLAN)
    with open(C.PLAN + ".sha256", "w", encoding="utf-8") as fh:
        fh.write("%s  plan_F55_frozen.json\n" % h)
    print(json.dumps(dict(ok=True, plan=C.PLAN, sha256=h, options={k: {st: dict(cfg_sha16=v["cfg_sha16"], commit_need_gb=round(v["commit_need_gb"], 2),
                                                                                  time_h=[round(t, 2) for t in v["time_h"]], runnable=v["runnable"])
                                                                         for st, v in o["stages"].items()} for k, o in pl["options"].items() if "stages" in o}),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
