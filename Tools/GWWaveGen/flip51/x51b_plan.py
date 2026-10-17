# -*- coding: utf-8 -*-
"""FLIP51 X2B': the frozen plan (design, the two changes, registered predictions, CO-EQUAL criteria, gates, verdict rule, automation, risks)
-> Unity/Build/FLIP51/plan/plan_X2B_frozen.json + .sha256 (py -3.10 -B). 2026-10-17 written new (Claude).
Every threshold is read from the code that applies it (x51b_ana: COEQ, REF, G2B, G7, PIPELINE, PHYSICS_FLAGS, PRED, levels_text; x51_ana: the frozen
plan-E reading; x51b_common: the two changes), so the plan and the code cannot disagree. The code files are registered with their sha256 and
the automation (G:/research/Wave Simulation/_tools/auto_X2B.py) refuses to launch if any of them changed after freezing. pv53 (maintained by
another workflow) is registered as NON-blocking: a change is reported, the print bars are copied here (x51b_ana.COEQ).
usage:
  py -3.10 -B x51b_plan.py freeze [--force=1 --reason=...]   write the frozen plan (refused once the X2B run has records)
  py -3.10 -B x51b_plan.py verify                            registered shas against the files now (json; exit 1 on a mismatch)
  py -3.10 -B x51b_plan.py amend                             append AM-X2B1 to Unity/Build/FLIP51/plan/amendments.jsonl (once)
"""
import os, sys, json, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import x51b_common as XB             # noqa: E402
import x51b_ana as XBA               # noqa: E402
import x51_common as XC              # noqa: E402  read only
import x51_ana as XA                 # noqa: E402  read only
import e51_metrics as EM             # noqa: E402  read only
import g50_common as GC              # noqa: E402  read only

AM_ID = "AM-X2B1"


def sha(p):
    return XB.sha256_file(p) if os.path.exists(p) else None


def build():
    cfg = json.load(open(XB.CFG, encoding="utf8"))
    tc = json.load(open(XB.TABLE_CHECK, encoding="utf8"))
    bc = XB.jload(GC.B50 + "/_logs/build_check.json") or {}
    pc = cfg["precheck"]
    reg = {k: sha(v) for k, v in XB.code_files().items()}
    view = {k: sha(v) for k, v in XB.view_files().items()}
    refs = {XB.rel(p): sha(p) for p in (XB.X2_JUDGE, XB.X2_PV53, XB.DM1A_PV53, XB.BASELINE, XB.X2_CFG, XC.PLAN_E)}
    P = dict(
        status="frozen", plan="X2B'", campaign="FLIP51-X2B", tool="Tools/GWWaveGen/flip51/x51b_plan.py",
        title="X2B': the X2 converged sea focused on the 1:10 slope at x_f 275.25 m (h 7.5 m) with the side band generating to 210.25 m, so that the "
              "converged crest breaks (Hc ~0.82 h) just past the focus - a plunging, print-like front while still converged",
        rule_Q83=dict(date="2026-10-17", text="every evaluation must show and judge, co-equally, (1) the Unity PRINT-VIEW render at the most print-like "
                                              "instant, (2) the centre section vs the print outline with the print ruler (STUDY52 cn; score3 chord / foot "
                                              "/ hood / hollow; back, width07, lip), (3) convergence metrics (e51_metrics.py; target = the user's "
                                              "screenshot read values). Progress = convergence better AND print match not worse.",
                      how_applied="the verdict below needs BOTH a convergence level and a print-match level; the print-view render must exist or "
                                  "no claim is made (INCOMPLETE)"),
        trigger=dict(finding_X2="X2 (S51X2_D19B_T7_g60s28_dp0p5) converges best (median core miss 1.88, best 0.92; W50 4.33 Hc; N1 0.56) but its "
                                "summit (x ~200 m, still depth 14.9 m, Hc 5.6 m, Hc/h 0.38) is a smooth non-breaking hump: median best score3 2.37, "
                                "chord 17-29 deg, no lip / hood; lips only at x 317-355 m (depth <= 3.3 m, eta_c <= 2.6 m) [measured]",
                     finding_DM1A="DM1A (T 12 s, +-80 deg, focus 220.25) broke at x 253-260 m (h_b 9-9.7 m) with plunging lips, score3 0.41-1.0, back "
                                  "13.8 deg, but a wide crest (W50 9.3 Hc, miss 4.86) [measured]",
                     idea="X2B: same direction set and a_sum as X2, the focus moved shoreward so the converged crest reaches breaking at the focus"),
        design=dict(
            choice="x_f 275.25 m (h_f 7.5 m), t_f 0 (crest at x_f at t = 7n s: the judge windows n 6-10 stay); side band sd_gen 180.25 -> 210.25 m, "
                   "sd_sw 210.25 -> 240.25 m (cfg / CTRL parms) and a table over x 0-244 m; hip, a_sum 6.331 m, the 34-component X2 set unchanged",
            literal_X2B_rejected="x_f alone (X2 bands) is predicted to fail for every x_f 240-300 m: the 65-85 deg rays to a shoreward focus leave "
                                 "the side band where it absorbs; supply 0.99 / 0.92 / 0.80 / 0.67 at x_f 220 / 240 / 260 / 280, Hc/h_f only 0.42 -> "
                                 "0.53 (0.82 needed), break stays at x 308-316 m (h ~4 m, Hc ~3 m) [computed; the supply rule matches X2's FLIP "
                                 "envelope 0.98-1.02 at x 255-285 m, measured]",
            why_275="with the band extended the supply returns (0.985) and the converged crest reaches ~0.82 h at x ~282 m for x_f 260-280; 275.25 "
                    "puts the break ~7 m (0.1 L) past the focus; 280.25 would allow breaking before full convergence within the -9 m band; 270.25 "
                    "breaks 12 m past [computed]",
            second_change_status="X2B' needs this second change beyond the idea's one-change rule; a_sum and the direction set are unchanged (no "
                                 "input enlargement). Registered here and in AM-X2B1 before any X2B' record exists.",
            screen="Tools/GWWaveGen/flip51/x51b_screen.py (cal, calap, screen2, supplyfix, detail) -> Unity/Build/FLIP51/_scratch/x2b/*.json",
            tags="computed (x51b_screen), measured (X2 / DM1A records), chosen (x_f, bands)"),
        setup=dict(run_id=XB.RUN_ID, run_dir=XB.rel(XB.RUN_DIR), cfg=XB.rel(XB.CFG), cfg_sha256=sha(XB.CFG), precheck_ok=pc.get("ok"),
                   precheck_checks=pc.get("checks"), time_estimate=pc.get("time"), diff_vs_X2=pc.get("diff_vs_X2"),
                   table=dict(npz=XB.rel(cfg["dir"]["npz"]), npz_sha256=cfg["dir"]["npz_sha256"], content_sha256=cfg["dir"]["content_sha256"],
                              grid=cfg["dir"]["grid"], x_f=cfg["dir"]["x_f"], t_f=cfg["dir"]["t_f"], linear_refs=cfg["dir"]["linear_refs"]),
                   table_check=dict(path=XB.rel(XB.TABLE_CHECK), sha256=sha(XB.TABLE_CHECK), all_ok=tc.get("all_ok"), ok=tc.get("ok"),
                                    focus=tc.get("focus"), supply=dict(X2B_bands=(tc.get("supply") or {}).get("frac_X2B_bands"),
                                                                       X2_bands=(tc.get("supply") or {}).get("frac_X2_bands")),
                                    band_linear_steepness=tc.get("band_linear_steepness")),
                   hip=dict(path=XB.rel(GC.HIP), sha256=sha(GC.HIP), build_check_hip_sha256=bc.get("hip_sha256"), build_check_all_ok=bc.get("all_ok"),
                            note="Houdini/FLIP50/g50_tank.hiplc unchanged; its VEX reads sd_gen / sd_sw from CTRL (g50_tanklib.bands50) and clamps x to "
                                 "the table's d_x0..d_x1 (dtab_pos); g50_run.py sets every cfg parm on CTRL"),
                   records=cfg["records"], max_hours=cfg["max_hours"], f_end=cfg["f_end"], t_end_s=cfg["t_end_s"],
                   wall_expected_h=[1.6, 2.0], wall_rule="X2 at dp 0.5 took 1.27 h with 321 surface records at 2.8 s each [measured]; every-frame "
                                                         "surfaces add ~640 x 2.8 s = 0.5 h [computed]; the precheck bound is %.2f h" % ((pc.get("time") or {}).get("bound_h") or 0)),
        registered_predictions=dict(XBA.PRED, expected_text="summit = break at x 282 [273-290] m, h_b 6.9 [6.0-7.7], Hc 5.6 [5.2-5.95]; convergence "
                                    "about X2's (W50 4.4 [3.6-4.8] Hc, miss 1.9 [1.0-2.7], N1 0.62 [0.51-0.70], marginal vs 0.65); print ruler: "
                                    "chord 40-80 deg, lip 0-0.35 (P(lip >= 0.20) ~35 %: Iribarren 0.31-0.33 = spilling range), back 11-16, "
                                    "width07 2.5-3.5, score3 0.8-2.0 [computed / guess]"),
        criteria=dict(
            co_equal="the verdict combines a CONVERGENCE level and a PRINT-MATCH level; neither replaces the other; the print-view render must be shown",
            convergence=dict(reader="x51_ana.judge05 (frozen plan-E reading, unchanged code) run by x51b_ana.judge with in-memory adaptations: "
                                    "X2B case record (G6 floor 0.68 x 5.6 m), G4 side band read to x 210.25 m, D smoke report focus 275.25",
                             metrics=dict(SCAN=XA.SCAN, N1DEF=XA.N1DEF, e51_FROZEN=EM.FROZEN, e51_TARGET=EM.TARGET),
                             refs=dict(X2=XBA.REF["X2"], DM1A=XBA.REF["DM1A"]), thresholds=XBA.COEQ,
                             levels={k: v for k, v in XBA.levels_text().items() if k.startswith("C_")},
                             reasons=dict(tie="0.30 = plan E BARS.tie (median core-miss differences below it are ties)",
                                          W50_hold="X2's converged periods read W50 3.56-4.33 Hc (spread 18 %) [measured] -> 'held' up to +15 %",
                                          N1_Hc_gain="plan E E1 (N1 <= 0.65), E2 0.5 m (Hc >= 5.0 m), E3 (gain >= 1.8)",
                                          DM1A_level="better than DM1A only when the miss is below DM1A's by more than the tie band")),
            print_match=dict(reader="Tools/GWWaveGen/flip53/pv53.py run (unchanged; sha at freeze %s, non-blocking): per period the most print-like "
                                    "instant on the summit's own track [t_max - 1.5, t_max + 3.0] s, crest floor 0.6 Hc (AM-E2a), D ruler (g46 r2_mask "
                                    "-> STUDY52 measure_mask -> d_shape_measure.pick -> g47_video.score3)" % (sha(XB.PV53) or "")[:16],
                             bars=dict(score3=XBA.COEQ["score3_bar"], lip=XBA.COEQ["lip_min"], gain_vs_X2=XBA.COEQ["score3_gain_vs_X2"]),
                             levels={k: v for k, v in XBA.levels_text().items() if k.startswith("P_")},
                             at_converged_summit="the period of the judge's red instant (smallest core miss) must itself pass the bars for P_OK",
                             reasons=dict(score3="DM1A median best score3 0.6485 + 0.30 (DM1A's own breaker-to-breaker scatter: IQR 0.255, max - median "
                                                 "0.35) = 0.9485 [measured + chosen, AM-E2]",
                                          lip="0.20 = 0.57 x the print's lip 0.35 (band 0.318-0.389); DM1A 0.335-0.346: a plunging lip exists [chosen]",
                                          converged="the user wants the converged wave itself to look like the print, not another period")),
            print_view=dict(renders=["pv53: the option-D print pose scaled by Hc at the most print-like instant and at the converged period (Unity "
                                     "stills + short mp4, front view too)",
                                     "x51b_view: the X2 camera rules (cam_x2.py, DM1A metres per pixel) transferred to X2B's converged summit; "
                                     "35-75 s real-time print and front mp4 + stills at every period summit (f3d51_export_e51 + FLIP3DBatch)"],
                            required="pv53's print-view still at the most print-like instant exists, else verdict INCOMPLETE"),
            validity=dict(pipeline=list(XBA.PIPELINE), physics_flags=list(XBA.PHYSICS_FLAGS), G2_X2B=XBA.G2B, G7=XBA.G7, G7b=XBA.G7B,
                          G4_side_x_max=XB.SD_GEN, G4_kA_max=XA.GATES["G4_kA_max"], G5_volume_max=XA.GATES["G5_volume_max"],
                          periods_min=XA.SCAN["min_valid"],
                          reasons=dict(G2_X2B="the plan-E gauge (110, 0.5) has linear A 0.68 m in X2B (near a partial node); X2's gauges with A "
                                              "0.41-0.64 m read 0.99-1.18 [measured] -> the all-gauge median decides (X2 1.007, X1 1.021 [measured])",
                                       G7="the band now generates on the slope (x 180-210 m, h 14-17 m), untested; X2's generating part reads "
                                          "0.78-1.09 (median 0.95) [measured]",
                                       flags="X2, the convergence reference, failed G3 and G6 (its n8 / n9 instants were pulled to the surf break), "
                                             "so they cannot block a comparison with it; they are reported")),
            verdict=XBA.levels_text()["verdict"],
            order="INVALID (pipeline) > INCOMPLETE (no print-view render) > PROGRESS_STRICT > PROGRESS > TRADE_OFF > NO_PROGRESS_PRINT > NO_PROGRESS"),
        automation=dict(script=XB.AUTO, status=XB.rel(XB.STATUS), prefix="X2B ", final_line="<date> <time> X2B FINISHED <verdict>",
                        flow=["verify (this plan's sha, registered code, cfg, table + G1, x51b_pcfg gate = the dry g50_chain start gate)",
                              "wait: the LAST 'DFG ' line of Unity/Build/FLIP52/_logs/auto_DFG_status.txt matches ^<date> <time> DFG FINISHED( .*)?$ "
                              "and comes after the last 'DFG MAIN_ONLY' line, no auto_DFG*.py / g52_chain / g52_run process, no hython, 3 polls in a "
                              "row with the same last line; then yield while an auto_DFGB.py process lives (unless --no-yield) and while any other "
                              "chain (g50 / g52 / g52b) or hython runs",
                              "chain: g50_chain.py <cfg> (launch or adopt; up to 2 resumes after a max_hours stop, a crash or a stale chain)",
                              "x51b_ana judge -> x51b_ana video -> pv53 run (--judge e51/judge_E05.json; on failure pv53 --no-unity) -> x51b_view all "
                              "-> x51b_ana coequal (verdict + report_X2B.png)"],
                        brake=XB.rel(XB.LOGS + "/auto_X2B_STOP"), lock=XB.rel(XB.LOGS + "/auto_X2B.lock"),
                        not_started_by_author=True),
        registered_files=reg, view_tools=view, non_blocking=dict(pv53=dict(path=XB.rel(XB.PV53), sha256=sha(XB.PV53))),
        references=refs, amendments=dict(file=XB.rel(XB.AMENDMENTS), id=AM_ID),
        risks=[
            "Spilling instead of plunging: Iribarren 0.31-0.33 at the break (DM1A plunged at 0.46-0.49); P(lip >= 0.20) ~35 %; breaker type is set "
            "by T and the slope, not by x_f [guess]",
            "Convergence predicted equal to X2, not better (W50 4.4 [3.6-4.8], miss 1.9 [1.0-2.7]); N1 0.62 marginal vs 0.65 (lattice spot ~(243, "
            "+-44) m); progress rests on the print match",
            "Break position 273-290 m (gamma 0.76-0.88, r +-0.07); gamma calibrated at kh ~0.52, X2B' breaks at kh ~0.8 (extrapolated)",
            "Generating side band on the slope (x 180-210 m, h 14-17 m) is untested: WKB target without slope reflection; G7 and G4 watch it",
            "G2 nodal gauge: (110, 0.5) has linear A 0.68 m; the all-gauge median decides (G2_X2B)",
            "Transient: the field develops by ~35-37 s; n6 (t 42 s) has ~5 s margin",
            "Off-axis breaking and curl widening (half-width 5.5 / 8.5 / 13.5 m at x_b + 5 / 10 / 20 m) [computed]",
            "Periodic drift: surf zone ~70 m from x 282 m; successive breaks may move +-3-6 m; G3 is a flag",
            "Calibration on two runs only (X2 T 7, DM1A T 12); FLIP/screen W50 ratio 0.54-0.96",
            "Every-frame surface records add ~0.5 h wall and ~1.8 GB disk (G: had 208 GB free at freezing)",
            "Queue: plan DFG-2 runs until ~01:20; auto_DFGB.py (FLIP52B) also waits for DFG-2 to end; auto_X2B yields to a live auto_DFGB.py by "
            "default (the main session decides the order: --no-yield)"],
        honesty=dict(chosen_at_inlet="T 7 s, the X2 direction set and weights, a_sum 6.331240 m (= DM1A input sum), x_f 275.25 m, t_f 0, the side "
                                     "band generating end 210.25 m",
                     computed_by_FLIP="shoaling, refraction, focusing, the crest's growth, breaking, any lip / jet",
                     not_done="no input enlargement, no force toward a shape, no wind or current; the target picture is used only through the frozen "
                              "e51 read values; nothing committed; README / Docs not edited",
                     judged_by_user="the look in the print view; the ruler numbers are an AI reading"),
        frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    return P


def freeze(force=False, reason=None):
    if os.path.exists(XB.RUN_DIR + "/run.json") and not force:
        raise SystemExit("the X2B run already has records (%s/run.json): not re-frozen (use --force=1 --reason=...)" % XB.RUN_DIR)
    P = build()
    if force:
        P["refrozen"] = dict(reason=reason or "(none given)", date=time.strftime("%Y-%m-%d %H:%M:%S"))
    if not P["setup"]["precheck_ok"] or not P["setup"]["table_check"]["all_ok"]:
        raise SystemExit("precheck or table check not ok: not frozen")
    XB.jdump(P, XB.PLAN)
    h = sha(XB.PLAN)
    open(XB.PLAN + ".sha256", "w", encoding="utf8").write("%s  plan_X2B_frozen.json\n" % h)
    return dict(plan=XB.PLAN, sha256=h, registered=len(P["registered_files"]))


def verify():
    bad, warn = [], []
    if not (os.path.exists(XB.PLAN) and os.path.exists(XB.PLAN + ".sha256")):
        return dict(ok=False, bad=["plan or .sha256 missing"], warn=warn)
    h = sha(XB.PLAN)
    if open(XB.PLAN + ".sha256", encoding="utf8").read().split()[0] != h:
        bad.append("plan sha differs from .sha256")
    P = json.load(open(XB.PLAN, encoding="utf8"))
    for k, v in (P.get("registered_files") or {}).items():
        p = XB.code_files().get(k)
        if p is None or sha(p) != v:
            bad.append("code %s changed (%s -> %s)" % (k, str(v)[:12], str(sha(p) if p else None)[:12]))
    for k, v in (P.get("view_tools") or {}).items():
        p = XB.view_files().get(k)
        if p is None or sha(p) != v:
            bad.append("view tool %s changed" % k)
    s = P.get("setup") or {}
    if sha(XB.CFG) != s.get("cfg_sha256"):
        bad.append("cfg sha differs")
    t = s.get("table") or {}
    if sha(XB.REPO + "/" + t.get("npz", "")) != t.get("npz_sha256"):
        bad.append("table sha differs")
    tc = XB.jload(XB.TABLE_CHECK) or {}
    if not tc.get("all_ok") or sha(XB.TABLE_CHECK) != (s.get("table_check") or {}).get("sha256"):
        bad.append("table check not all_ok or changed")
    bc = XB.jload(GC.B50 + "/_logs/build_check.json") or {}
    if sha(GC.HIP) != bc.get("hip_sha256") or not bc.get("all_ok"):
        bad.append("FLIP50 hip / build_check mismatch")
    pv = (P.get("non_blocking") or {}).get("pv53") or {}
    if sha(XB.PV53) != pv.get("sha256"):
        warn.append("pv53.py changed after freezing (%s -> %s): non-blocking, reported" % (str(pv.get("sha256"))[:12], str(sha(XB.PV53))[:12]))
    for k, v in (P.get("references") or {}).items():
        if sha(XB.REPO + "/" + k) != v:
            warn.append("reference %s changed after freezing" % k)
    return dict(ok=not bad, bad=bad, warn=warn, plan_sha256=h)


def amend():
    lines = open(XB.AMENDMENTS, encoding="utf8").read().splitlines() if os.path.exists(XB.AMENDMENTS) else []
    for ln in lines:
        try:
            if json.loads(ln).get("id") == AM_ID:
                return dict(appended=False, why="%s already registered" % AM_ID)
        except ValueError:
            continue
    if not os.path.exists(XB.PLAN):
        raise SystemExit("freeze the X2B plan first")
    if os.path.exists(XB.RUN_DIR + "/run.json"):
        raise SystemExit("the X2B run already has records: an amendment now would be post hoc")
    P = json.load(open(XB.PLAN, encoding="utf8"))
    rec = dict(id=AM_ID, date=time.strftime("%Y-%m-%d %H:%M:%S"), plan="Unity/Build/FLIP51/plan/plan_E_frozen.json",
               plan_sha256=sha(XC.PLAN_E), new_plan=XB.PLAN_REL, new_plan_sha256=sha(XB.PLAN), by="X2B workflow (Claude)", post_hoc=False,
               what="New run X2B' (%s) under its own frozen plan: X2 with x_f 220.25 -> 275.25 m (table x 0-244 m) AND the side band generating to "
                    "210.25 m (sd_gen 180.25 -> 210.25, sd_sw 210.25 -> 240.25). a_sum, direction set, T, hip unchanged." % XB.RUN_ID,
               why="X2 converges best but its summit (x ~200 m, h 14.9 m, Hc/h 0.38) never breaks (score3 2.37, no lip); X2B moves the converged "
                   "crest onto the slope so it breaks (Hc ~0.82 h) just past the focus. The literal one-change X2B (x_f only) is predicted to fail "
                   "(ray supply 0.99 -> 0.67, break stays at 308-316 m) [computed, x51b_screen.py], hence the second change.",
               registered_prediction=P["registered_predictions"]["expected_text"],
               criteria="co-equal (Q83): convergence level (C_BETTER / C_HELD vs X2, tie 0.30) AND print match (P_OK: median best score3 <= 0.9485 "
                        "and lip >= 0.20, also at the converged summit) with the print-view render shown; verdict rule in the new plan",
               effect="plan E itself unchanged (no threshold or criterion of plan E changes; X2 / X1 stay as judged)", thresholds_changed=False,
               criteria_changed=False, plan_file_changed=False)
    with open(XB.AMENDMENTS, "a", encoding="utf8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return dict(appended=True, id=AM_ID, file=XB.AMENDMENTS)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "freeze":
        print(json.dumps(freeze(force=opt.get("force") == "1", reason=opt.get("reason")), ensure_ascii=False))
    elif a[0] == "verify":
        r = verify()
        print(json.dumps(r, ensure_ascii=False))
        sys.exit(0 if r["ok"] else 1)
    elif a[0] == "amend":
        print(json.dumps(amend(), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
