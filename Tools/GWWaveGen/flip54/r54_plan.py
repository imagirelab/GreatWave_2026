# -*- coding: utf-8 -*-
"""FLIP54 R54: the FROZEN PLAN of the 2D resolution check (py -3.10 -B). 2026-10-18 written new (Claude, FLIP54 builder R) after
g54_plan.py's pattern (show / freeze, refuse once a run exists). Writes Unity/Build/FLIP54/r54/plan/plan_R54_frozen.json + .sha256 BEFORE
any R54 run: the arms, what stays identical and what is tied to dp, the K54 dp-0.5 references (their analyses' sha256 and baseline numbers),
the quantities, the reading rule, the execution policy and the time / memory / disk estimate. r54_chain.py starts a strip only when the plan's
sha256 holds (g54_chain's gate on case.plan_frozen); r54_ana.py reads its thresholds from it.

usage:
  py -3.10 -B r54_plan.py show [--out=<file under FLIP54>]     print (or write) the plan that would be frozen
  py -3.10 -B r54_plan.py freeze [--force=1 --reason=...]      write plan + .sha256; refuses when it exists, and always once an R54 run exists
"""
import os, sys, json, time, glob

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import r54_common as RC       # noqa: E402
import g54_common as C        # noqa: E402
import r54_pcfg as RP         # noqa: E402
import r54_ana as RA          # noqa: E402

REL = lambda p: (p or "").replace(C.REPO + "/", "")


def ckpt_bytes(rd):
    fs = glob.glob(rd + "/ckpt/*.sim")
    return sum(os.path.getsize(f) for f in fs), len(fs)


def plan():
    refs, arms, cfgs = {}, {}, {}
    for arm in RC.ARMS:
        r = RC.k54_ref(arm)
        a = C.jload(r["analysis"]) or {}
        q, per, h = RA.quantities(a)
        cb, cn = ckpt_bytes(r["run_dir"])
        refs[arm] = dict(run_id=r["run_id"], run_dir=REL(r["run_dir"]), complete=r["ok"], f_end_done=r["f_end_done"], wall_total_s=r["wall_total_s"],
                         particles_model=r["particles_model"], particles_max=r["particles_max"], rss_peak_gb=r["rss_peak_gb"], H_m=r["H"], T_s=r["T"],
                         analysis=REL(r["analysis"]), analysis_sha256=r["analysis_sha256"], ready_cfg=REL(r["ready_cfg"]), ready_cfg_sha256=r["ready_cfg_sha256"],
                         g54_ana_sha16_in_analysis=(a.get("module_shas") or {}).get("flip54/g54_ana.py"), judged_k=a.get("judged_k"),
                         baseline=q, per_breaker=per, health=h, ckpt_bytes=cb, ckpt_files=cn, tag="measured (K54, dp 0.5 m)")
        c = RP.make(arm, dry=True)
        pc = c["precheck"]
        cfgs[arm] = dict(run_id=c["run_id"], cfg_dry_ok=pc["ok"], reason=pc["reason"], particles_model=pc["particles_model"],
                         particles_ratio_vs_K54=pc["particles_ratio_vs_K54"], frames=pc["frames"], wall_model=pc["wall_model"],
                         changed_dp_tied=pc["diff_vs_K54"]["changed_dp_tied"], unexpected_diffs=pc["diff_vs_K54"]["unexpected"],
                         box=c["box"], parms_dp=c["parms"]["dp"], gridscale=c["parms"]["gridscale"], max_hours=c["max_hours"],
                         ckpt_bytes_est=(cb / max(1, r["particles_max"])) * pc["wall_model"].get("particles_max_model", 0.0) if cb else None)
        hL, s2, sh, T, role, lab = C.ARMS[arm]
        arms[arm] = dict(label=lab, K54_role=role, pg_hL=hL, pg_s2=s2, shelf_h=sh, T_s=T, H_m=c["wave"]["H_m"], spec=C.spec_for(arm),
                         landmarks=C.landmarks(arm), R54_run_id=c["run_id"], K54_run_id=r["run_id"])
    b0 = refs["K0"]["baseline"]; b4 = refs["K4"]["baseline"]
    orders = {k: dict(K0=b0.get(k), K4=b4.get(k), order_dp0p5=RC.order(b4.get(k), b0.get(k)),
                      rel_diff=(None if (b0.get(k) is None or b4.get(k) is None or max(abs(b0[k]), abs(b4[k])) == 0)
                                else (b4[k] - b0[k]) / max(abs(b0[k]), abs(b4[k])))) for k in RC.ORDER_KEYS}
    est = {a: cfgs[a]["wall_model"] for a in RC.ARMS}
    tot = sum(e["wall_est_s"] for e in est.values()); tot_hi = sum(e["wall_hi_s"] for e in est.values())
    tools = {t: (C.sha256_file(HERE + "/" + t) if os.path.exists(HERE + "/" + t) else None) for t in RC.K54_TOOLS + RC.R54_TOOLS}
    return dict(
        name="R54: 2D resolution check of the K54 strips (K0 and K4 at dp 0.25 m; everything else identical) (FLIP54 builder R)",
        why=("user priority: the wave does not curl a BIG hollow. K54 (2D concave-bed screen, dp 0.5 m) finished NONE_PASS 2026-10-18 21:44: concave "
             "beds shorten the foot and thicken the lip, but the hood forms only after the face passes vertical (chord at max hood 108-119 deg; hood at "
             "chord <= 78 deg ~0); report only: K4 had the best score3 0.252 vs K0 0.479. Ranked #3 by the FLIP54 design workflow, this check informs "
             "the supervisor's 0.25 m particle decision: does the 2D hollow depend on the particle size? Earlier 2D evidence: halving the grid gave "
             "+37 % cavity with Hb unchanged (FLIP47 E1a, Unity/Build/FLIP47/runs/E1a_compare) [measured]."),
        question="Do cavity air and the max hood (and the K4-vs-K0 ordering) of K54's K0 and K4 change when dp goes 0.5 -> 0.25 m?",
        arms=arms, order=list(RC.ARM_ORDER),
        identical=("bed (spec, landmarks), Fenton inlet wave (the same table: h0 19 m, T 9.333 s, H 7.0 m = K54's calibrated H_K0, not recalibrated), "
                   "inlet band 0-100 m with ramp 2 T, x_p 80 m, wall taper 20 m, exit sponge 332-412 m sigma 1.41 chi^2, drift stage A (window "
                   "110-327 m), records (hf + centre section r2 every frame, r6 gauges / levels), gauges, level regions, 90 s (2161 frames), solver "
                   "(FLIP, no narrow band, cfl 1, substeps 1-8), checkpoints, 1740-s launch limit, the analysis code g54_ana.py and its ruler"),
        dp=dict(dp_m=RC.DP, dp_ref_m=RC.DP_REF, gridscale=RC.GRIDSCALE, grid_m=RC.DP * RC.GRIDSCALE, half_width_m=C.W_STRIP,
                dp_tied=list(RP.DP_TIED), names_changed=list(RP.R54_NAMES),
                why_tied="g46 box(): voxel = 2 dp; the grid-face offsets ox / oy / oz = 0.5 voxel; the box floor 2 voxels under zb; the inlet probe "
                         "height 0.5 voxel. bed_gap (0.5 dp), surf_vox_scale / surf_keep_vox / surf_bed_vox are in particle / voxel units and follow "
                         "dp by themselves; surf_layer_m / mirror_m are metres and stay"),
        cfg_dry=cfgs,
        references=dict(arms=refs, runmap=REL(RC.K54_RUNMAP), runmap_sha256=RC.sha(RC.K54_RUNMAP), verdict_K54=REL(RC.K54_VERDICT),
                        verdict_K54_sha256=RC.sha(RC.K54_VERDICT), calibration_K0=REL(RC.K54_CALIB), calibration_K0_sha256=RC.sha(RC.K54_CALIB),
                        plan_K54=REL(RC.K54_PLAN), plan_K54_sha256=RC.sha(RC.K54_PLAN),
                        rule="the dp-0.5 numbers are the K54 analyses themselves (never re-measured by R54); r54_ana refuses a reading if their sha256 "
                             "differs from the values registered here"),
        quantities=dict(
            keys=list(RA.QK), labels=RA.QLAB,
            definition=("medians over the judged breakers k2-k4 (FLIP49 event rule; >= 2 values needed) of g54_ana.measure: hood_max = max hood_area "
                        "over the pre-touchdown frames; hood78 = max hood_area at chord <= 78 deg; air_max_pre = max cavity air (air under "
                        "overturned columns / eta_c^2, x_c - 0.5 .. + 1.5 eta_c) over the pre-touchdown frames; hollow_air = the R0 hollow-instant "
                        "air (report); lip = lip_thick_mid (/ eta_c) at the first lip and at the max-hood frame, and in metres = lip x eta_c of that "
                        "frame; chord_at_hood_max (deg); foot_at_hood_max and foot_at_hood14 (front_x01_rel); best_score3 (lower = closer to the "
                        "print); h_b = still depth at the onset; eta_at_hood_max (m). Health (report): realized H at the gauges, Kr (Goda & Suzuki), "
                        "stage-A volume, judged count"),
            tag="measured (FLIP records + the pv53 ruler)"),
        reading_rule=dict(
            gain=RC.GAIN, tie=RC.TIE, gain_keys=list(RC.GAIN_KEYS), order_keys=list(RC.ORDER_KEYS),
            rule=("RESOLUTION_MATTERS ('resolution matters for the hollow') if (a) the SAME quantity among cavity air (air_max_pre) and hood_max grows "
                  "by >= +25 %% at dp 0.25 relative to dp 0.5 in BOTH arms (K0 and K4), i.e. (v_0.25 - v_0.5) / |v_0.5| >= 0.25, or (b) the K4-vs-K0 "
                  "order of any of %s flips: order = sign(K4 - K0) when |K4 - K0| / max(|K4|, |K0|) >= 0.10, else a tie; a flip needs a non-tie "
                  "order at both dp with opposite signs. Otherwise NOT_SHOWN (report only). INCOMPLETE if an arm at either dp has fewer than 2 "
                  "judged breakers (no reading). PLAN_SHA_FAILED / REFERENCE_CHANGED / RULER_CHANGED: no reading (the frozen plan, a K54 analysis "
                  "or g54_ana.py changed)." % ", ".join(RC.ORDER_KEYS)),
            baseline_orders_dp0p5=orders,
            flippable=[k for k, v in orders.items() if v["order_dp0p5"] != 0],
            report_only=("reading (a) per arm with ANY quantity (an arm counts if air OR hood_max grows >= +25 %%), decreases <= -25 %%, an order that "
                         "emerges from a tie or vanishes into one, the h_b shift (> 1 m: the wave breaks elsewhere, so the change mixes resolution "
                         "and breaking position), the realized-H shift, the per-breaker scatter, lip / chord / foot / score3 / h_b changes"),
            consequence=("RESOLUTION_MATTERS: evidence that the dp-0.5 strips under-resolve the hollow (supports the supervisor's 0.25 m decision); "
                         "NOT_SHOWN: no evidence that 0.25 m changes the 2D hollow by the registered amount. Either way report only - the supervisor / "
                         "user decides; 2D strips, not the 3D wave"),
            tag="registered before any R54 run"),
        execution=dict(
            launcher="G:/research/Wave Simulation/_tools/auto_R54.py",
            steps=["verify (tools, K54 tool sha16 = the ones recorded in the K54 analyses, g54_mkcopy check, plan sha, hip sha, K54 references)",
                   "wait: no hython, no pipeline process, no Unity -batchmode on 3 consecutive polls (60 s)",
                   "free commit >= %.0f GB (GlobalMemoryStatusEx) before every chain launch / resume" % RC.COMMIT_MIN_GB,
                   "g54_pcfg.py selfcheck; hython r54_xcheck.py (x54_check at dp 0.25 -> r54/_check/build_check_r54.json, all_ok needed)",
                   "per arm (K0 then K4): r54_pcfg.py cfg -> r54_chain.py (<= 1740-s launches from checkpoints, max_hours %.1f) -> complete? "
                   "else resume (<= %d) -> g54_ana.py measure" % (RC.MAX_HOURS, RC.RESUMES),
                   "r54_ana.py verdict -> r54/verdict/verdict_R54.json, R54_sheet.png, R54_sections.mp4"],
            resume_rule=("resume only for: the watchdog's low-commit stop, a chain that returned incomplete without a STOPPED_* note, or "
                         "STOPPED_MAX_HOURS when (frames left) x (measured s per frame) <= max_hours; never after STOPPED_CRASH / GUARD / NO_CKPT / "
                         "PRECHECK / DISK (logged, the arm is skipped; a failed K0 still lets K4 run, the reading is then INCOMPLETE)"),
            watchdog="free commit < %.0f GB on 2 polls, or the launcher's brake file -> <run>/STOP (the chain stops before its next launch; nothing is killed)" % RC.COMMIT_LOW_GB),
        estimate=dict(per_arm=est, total_hython_s=tot, total_hython_hi_s=tot_hi,
                      total_text="%.0f min (high %.0f min) of hython for both strips + scene check ~5 min + measure ~2 x 2 min + verdict ~3 min" % (tot / 60, tot_hi / 60),
                      memory=RC.RSS_NOTE, disk_text="checkpoints ~%.1f GB + records ~0.5 GB per strip (all checkpoints kept, as K54); G: stop line 25 GB" % (
                          (cfgs["K0"]["ckpt_bytes_est"] or 0) / 1e9),
                      tag="computed from measured records"),
        tools_sha256_at_freeze=tools,
        k54_tools_must_match_k54_analyses=True,
        what_it_is_not="not a 3D run, not a bed screen (no pass bar for beds), not a recalibration of H",
        tags=dict(baseline="measured (K54)", estimate="computed", rule="registered"))


def freeze(force=False, reason=None):
    runs = RC.runs_exist()
    if runs:
        raise SystemExit("R54 runs exist (%s): the plan is never re-frozen after a run" % ", ".join(runs[:4]))
    if os.path.exists(RC.PLAN) and not force:
        raise SystemExit("%s exists; --force=1 --reason=... only before any run" % RC.PLAN)
    p = plan()
    p["frozen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if force:
        old = C.jload(RC.PLAN) or {}
        p["refrozen"] = dict(reason=reason or "(none given)", previous_frozen_at=old.get("frozen_at"), previous_sha256=RC.sha(RC.PLAN))
    RC.jdump(p, RC.PLAN)
    sha = C.sha256_file(RC.PLAN)
    with open(RC.PLAN + ".sha256", "w", encoding="utf8") as fh:
        fh.write(sha + "  plan_R54_frozen.json\n")
    return p, sha


def main(argv):
    opt, pos = {}, []
    for a in argv[1:]:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opt[k] = v or "1"
        else:
            pos.append(a)
    cmd = pos[0] if pos else "show"
    if cmd == "show":
        p = plan()
        if opt.get("out"):
            RC.jdump(p, opt["out"])
            with open(opt["out"] + ".sha256", "w", encoding="utf8") as fh:      # a test copy (r54_ana --plan=) needs its own sha file
                fh.write(C.sha256_file(opt["out"]) + "  " + os.path.basename(opt["out"]) + "\n")
            print(json.dumps(dict(show=opt["out"]), ensure_ascii=False))
        else:
            print(json.dumps(C.clean(p), ensure_ascii=False, indent=1))
        return 0
    if cmd == "freeze":
        p, sha = freeze(force=bool(opt.get("force")), reason=opt.get("reason"))
        print(json.dumps(dict(plan=RC.PLAN, sha256=sha, frozen_at=p["frozen_at"]), ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
