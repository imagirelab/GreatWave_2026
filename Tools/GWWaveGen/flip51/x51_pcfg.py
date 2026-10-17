# -*- coding: utf-8 -*-
"""FLIP51 plan E: run configurations of the T 7 crossing screens (dp 1.0) and of the promoted run (dp 0.5), with the precheck and a dry
copy of the g50_chain start gate (py -3.10 -B). 2026-10-17 written new (Claude). flip50 modules are imported READ ONLY (g50_common,
g50_pcfg: parms_D, drift_stage_A, precheck, time_estimate, analysis_block). No flip50 file, hip, build_check or FLIP50 run is written.

The cfg is the DM1A / SMOKE50DA cfg (D19B tank, bands, stage-A drift AM-D18, gravity only, no absorber) with ONLY these differences:
  dir      the plan E table of the case (x51_table: T 7 s, explicit direction set, a_sum 6.331240 m = DM1A, focus (220.25, 0) at t = 7n s)
  sf       the linear descriptor at T 7 s (period for the drift reading; not a forcing table)
  parms    ramp_s 14 s (2T, the D rule) instead of 24 s
  time     t_end 75 s (frames 1-1801); records hf, r2, r3 every frame, r4 every 3rd frame in 35-75 s; r5 (surface meshes) only at dp 0.5
           (35-75 s every 3rd frame, for the video)
  paths    out_root = the ABSOLUTE folder Unity/Build/FLIP51/smoke (dp 1.0) or Unity/Build/FLIP51/runs (dp 0.5): g50_chain.py and g50_run.py
           join it onto Build/FLIP50 with os.path.join, and an absolute second part wins, so every record lands in FLIP51.
  plan     case.plan_frozen = Unity/Build/FLIP51/plan/plan_E_frozen.json (g50_chain checks its .sha256 before the first launch)
  budget   dp 1.0: max_hours 0.75 (one launch of <= 29 min expected: SMOKE50DA 1201 frames in 582 s [measured]); dp 0.5: 3.0 h (D value)
The hip is Houdini/FLIP50/g50_tank.hiplc UNCHANGED (its VEX reads the table, omega and ramp from the npz and CTRL): no new hip, no build.
usage:
  py -3.10 -B x51_pcfg.py cfg U7|X2|X1|all [--dp=1.0|0.5]     write <root>/ready/<run_id>.json (precheck inside; not written if it fails)
  py -3.10 -B x51_pcfg.py gate <cfg.json>                      the g50_chain start gate, dry (reads only) -> json
  py -3.10 -B x51_pcfg.py diff <cfg.json>                      parms/records difference against the DM1A (dp 0.5) or SMOKE50DA (dp 1.0) cfg
"""
import os, sys, json, math, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import x51_common as XC              # noqa: E402
import x51_table as XT               # noqa: E402
import g50_common as GC              # noqa: E402  read only
import g50_pcfg as PC                # noqa: E402  read only

REF_CFG = {1.0: GC.B50 + "/smoke/ready/SMOKE50DA_D19B_T12_dp1p0.json", 0.5: GC.B50 + "/runs/ready/DM1A_D19B_T12_th80_dp0p5.json"}
ALLOWED_PARM_DIFF = ("ramp_s",)       # the only parms that may differ from the reference cfg [chosen in the plan: period only]
SCREEN_MAX_H = 0.75
MAIN_MAX_H = 3.0
SMOKE_RATE = 581.8 / 1201 / 0.853673  # s per frame per million particles: SMOKE50DA launch (substeps 1, r5 every 2nd frame 38-50 s) [measured]


def make(case, dp):
    dp = float(dp)
    smoke = dp == 1.0
    p, b = PC.parms_D(dp, GC.W_MAIN, XC.RAMP7, smoke=smoke)
    p["ret_on"] = 1.0
    pc, dr = PC.drift_stage_A()
    p.update(pc)
    vox = b["vox"]
    f_end = GC.frames_for(0.0, XC.T_END)
    rec = dict(r2=True, r3_z=GC.R3_Y, block=120, r4_block=24, preg_every=24,
               r4=dict(x=list(GC.R4_X), z1=GC.R4_Y1, y0=-10.0, y1=16.0, clip_vox=6.0, t0=0.0, every=3),
               r5=(None if smoke else dict(t0=0.0, every=3)), windows=[list(XC.REC_WINDOW)])
    tb = XT.table_record(case)
    H_ref = tb["gauges_lin"]["x110_y0.5"]["H_lin"]
    sf = GC.sf_descriptor(XC.T7, H_ref, note="plan E: the inflow is the directional table cfg dir (T 7 s); this descriptor is for T, L, c, k only")
    C = XC.CASES[case]
    rid = XC.run_id(case, dp)
    th, w = XC.components(case)
    root = XC.SMOKE_ROOT if smoke else XC.RUNS_ROOT
    an = PC.analysis_block("E_" + case)
    an["plan_frozen"] = XC.PLAN_E_REL
    an["c_in_rule"] = "plan E: c_in110 = largest crest on the line x 110 m (|y| <= 95 m) per period window (x51_ana)"
    c = dict(
        run_id=rid, out_root=root, stage="FLIP51", kind=("smoke" if smoke else "3d"),
        case=dict(name="FLIP51_E_%s_D19B_T7_dp%s" % (case, GC.tag(dp)), plan_frozen=XC.PLAN_E_REL,
                  plan="Unity/Build/FLIP51/plan/plan_E_frozen.json (setups, frozen e51 metrics, gates G1-G6, eligibility E1-E3, promote rule, honesty)",
                  campaign="FLIP51-E", queue_id="E_%s_dp%s" % (case, GC.tag(dp)), judged=(not smoke), P1_x_max_m=GC.X_P1_MAX, dir_case="E_" + case,
                  e_case=case, role=C["role"], label=C["label"],
                  reference_cfg=REF_CFG[dp].replace(GC.REPO + "/", ""),
                  one_change="vs DM1A / SMOKE50DA: the directional table (T 12 -> 7 s and, for X1 / X2, the direction set), ramp 24 -> 14 s (2T), "
                             "t_end 75 s, records; everything else equal (x51_pcfg.py diff)"),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(XC.T_END), parms=p, box=b, bed=GC.bed_record(GC.SPEC_D19B, b),
        sf=sf, dir=dict(tb, ret_on=1.0),
        wave=dict(kind="linear directional monochromatic sea, explicit direction set (%s), phases 0 at (x_f, 0) at t = t_f + nT" % C["label"],
                  T_s=XC.T7, H_m=None, theta_deg=[float(v) for v in th], weights=[float(v) for v in w], n_components=int(len(th)),
                  theta_max_deg=float(np.abs(th).max()), a_sum_m=XC.A_SUM, a_component_max_m=float(XC.A_SUM * np.max(w)),
                  x_f_m=XC.X_F, t_f_s=XC.T_F, focal_crest_linear_m=tb["linear_refs"]["design_crest_xf"], in_gain=1.0, sd_gain=1.0, ramp_s=XC.RAMP7,
                  chosen_at_inlet="period T 7 s, directions and weights, a_sum 6.331240 m (= DM1A input sum, not enlarged), focus point (220.25, 0) "
                                  "and time t = 7n s [chosen]; computed by FLIP: shoaling, refraction, focusing, breaking, any jet",
                  tags=dict(T="chosen", directions="chosen", a_sum="chosen (= DM1A)", x_f="chosen", table="computed (x51_table)")),
        drift=dr, solver=dict(veltransfer="flip", donarrowband=0), records=rec,
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in GC.LEVEL_REGIONS_D],
        dir_check=dict(every=(48 if smoke else 120), x=[10.0, 40.0, 70.0, 95.0, 150.0, 200.0], y=[-15.0, -8.0, -2.0], zl=[0.5 * vox, 50.0, 100.0, 120.0]),
        ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0,
        max_hours=(SCREEN_MAX_H if smoke else MAIN_MAX_H), level_box=[0.0, b["Lx"], 0.0, b["W"]],
        n1_x=list(GC.N1_X), n1_window=[0.5, 1.5], shore_x=GC.X_SHORE, fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)],
        note=("FLIP51 plan E %s %s: 3D dp %g, half tank W 140 (45 m side band), D19B (h0 19 m, 1:10 beach, toe 160.25 m), directional sea T 7 s, %s, "
              "a_sum %.6f m (= DM1A), focus (220.25, 0) at t = 7n s, ramp 14 s, stage A (AM-D18), 0-75 s. %s. Hip Houdini/FLIP50/g50_tank.hiplc unchanged."
              % ("screen" if smoke else "promoted run", case, dp, C["label"], XC.A_SUM,
                 "Records hf/r2/r3 every frame, r4 every 3rd frame in 35-75 s, no r5" if smoke else
                 "Records hf/r2/r3 every frame, r4 and r5 every 3rd frame in 35-75 s")),
        layout="D", analysis=an)
    c["precheck"] = precheck_E(c)
    return c


def precheck_E(c):
    """g50_pcfg.precheck (read only) with the D-specific items replaced by their plan E versions:
    layout_D_named -> plan_E_named (case/analysis plan_frozen = plan_E); table_is_case -> table_is_E_case (the table info = the case's set,
    T 7, a_sum, x_f, ramp); smoke_one_launch -> screen_within_budget (SMOKE50DA rate x 1.0-1.6 <= max_hours); wall_le_limit (dp 0.5) kept.
    Added: parms_equal_reference (only ramp_s differs from DM1A / SMOKE50DA), records as designed."""
    pc = PC.precheck(c)
    ck = dict(pc["checks"])
    ck.pop("layout_D_named", None)
    ck.pop("table_is_case", None)
    ck.pop("smoke_one_launch", None)
    an = c.get("analysis") or {}
    ck["plan_E_named"] = bool(c.get("layout") == "D" and an.get("plan_frozen") == XC.PLAN_E_REL and (c.get("case") or {}).get("plan_frozen") == XC.PLAN_E_REL
                              and abs(float(an.get("p1_x_max_m", -1)) - GC.X_P1_MAX) < 1e-9)
    dr = c.get("dir") or {}
    case = (c.get("case") or {}).get("e_case")
    th, w = XC.components(case)
    ok_t = False
    try:
        info = json.loads(str(np.load(dr["npz"], allow_pickle=False)["info"]))
        ok_t = bool(info.get("case") == "E_" + case and abs(info["T"] - XC.T7) < 1e-12 and abs(info["a_sum"] - XC.A_SUM) < 1e-12
                    and abs(info["x_f"] - XC.X_F) < 1e-12 and np.allclose(info["theta_deg"], th, atol=0, rtol=0) and np.allclose(info["w"], w, atol=0, rtol=0)
                    and float(c["parms"]["ramp_s"]) == XC.RAMP7 and abs(float(c["sf"]["T"]) - XC.T7) < 1e-12)
    except Exception:
        ok_t = False
    ck["table_is_E_case"] = ok_t
    tc = XC.PLAN_DIR + "/table_check_%s.json" % case
    ck["table_G1_checked"] = bool(os.path.exists(tc) and json.load(open(tc, encoding="utf8")).get("all_ok")
                                  and json.load(open(tc, encoding="utf8"))["info"].get("content_sha256", dr.get("content_sha256")) in (dr.get("content_sha256"), None))
    d = diff_vs_ref(c)
    ck["parms_equal_reference"] = bool(d["parms_ok"])
    rec = c["records"]
    smoke = c["kind"] == "smoke"
    ck["records_as_designed"] = bool(rec.get("r2") and rec.get("r3_z") == GC.R3_Y and (rec.get("r4") or {}).get("every") == 3
                                     and rec.get("windows") == [list(XC.REC_WINDOW)] and ((rec.get("r5") is None) == smoke))
    ck["out_root_absolute_FLIP51"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(XC.B51 + "/")
                                          and os.path.join(GC.B50, c["out_root"]).replace("\\", "/") == c["out_root"].replace("\\", "/"))
    if smoke:
        n = int(pc.get("particles_model") or 0)
        nf = int(c["f_end"]) - int(c.get("f_start", 1)) + 1
        est = [SMOKE_RATE * n * 1.1 / 1e6 * nf / 3600.0, SMOKE_RATE * n * 1.3 / 1e6 * nf / 3600.0 * 1.6]
        pc["time"] = dict(frames=nf, est_h=est, rule="SMOKE50DA measured %.3f s per Mp per frame x growth 1.1-1.3 x substeps up to 1.6 [measured rate, "
                                                       "guessed growth/substeps]" % SMOKE_RATE)
        ck["screen_within_budget"] = bool(est[1] <= float(c["max_hours"]))
    pc["checks"] = ck
    pc["diff_vs_reference"] = d
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    pc["replaced_D_items"] = "layout_D_named -> plan_E_named; table_is_case -> table_is_E_case; smoke_one_launch -> screen_within_budget"
    return pc


def diff_vs_ref(c):
    dp = float(c["parms"]["dp"])
    ref = json.load(open(REF_CFG[dp], encoding="utf8"))
    pa, pb = c["parms"], ref["parms"]
    keys = sorted(set(pa) | set(pb))
    dd = {k: [pb.get(k), pa.get(k)] for k in keys if pa.get(k) != pb.get(k)}
    other = {}
    for k in ("bed", "box", "drift", "solver", "gauges", "level_regions", "n1_x", "n1_window", "shore_x", "level_box", "ckpt_every", "ckpt_list",
              "wall_limit_s", "level_guard_m", "disk_stop_free_gb", "layout"):
        if c.get(k) != ref.get(k):
            other[k] = "differs"
    return dict(reference=REF_CFG[dp], parms_diff=dd, parms_ok=bool(set(dd) <= set(ALLOWED_PARM_DIFF) and not other), other_blocks_diff=other,
                allowed=list(ALLOWED_PARM_DIFF))


def write(c):
    p = os.path.join(c["out_root"], "ready", c["run_id"] + ".json").replace("\\", "/")
    XC.guard_out(os.path.dirname(p))
    with open(p, "w", encoding="utf8") as fh:
        json.dump(c, fh, indent=1, ensure_ascii=False, default=float)
    return p


def gate(cfgp):
    """dry copy of the g50_chain.py start gate (same conditions; reads only)."""
    cfg = json.load(open(cfgp, encoding="utf8"))
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict) or pc.get("ok") is not True:
        bad.append("precheck not ok: %s" % (pc or {}).get("reason"))
    ckp = GC.B50 + "/_logs/build_check.json"
    if not os.path.exists(ckp):
        bad.append("build_check.json missing")
    else:
        bc = json.load(open(ckp, encoding="utf8"))
        if not bc.get("all_ok"):
            bad.append("build_check all_ok false")
        if not os.path.exists(GC.HIP):
            bad.append("hip missing")
        elif bc.get("hip_sha256") != GC.sha256_file(GC.HIP):
            bad.append("hip sha differs from build_check")
    dr = cfg.get("dir") or {}
    if not os.path.exists(dr.get("npz") or ""):
        bad.append("table missing")
    elif GC.sha256_file(dr["npz"]) != dr.get("npz_sha256"):
        bad.append("table sha differs")
    pf = (cfg.get("case") or {}).get("plan_frozen")
    p = pf if os.path.isabs(pf) else os.path.join(GC.REPO, pf)
    if not (os.path.exists(p) and os.path.exists(p + ".sha256")):
        bad.append("frozen plan or .sha256 missing: %s" % p)
    elif open(p + ".sha256", encoding="utf8").read().split()[0] != GC.sha256_file(p):
        bad.append("frozen plan sha differs from .sha256")
    rd = os.path.join(GC.B50, cfg.get("out_root", "runs"), cfg["run_id"]).replace("\\", "/")
    return dict(gate_ok=not bad, reasons=bad, run_dir=rd, run_dir_in_FLIP51=rd.startswith(XC.B51 + "/"),
                hip=GC.HIP, hip_sha256=GC.sha256_file(GC.HIP) if os.path.exists(GC.HIP) else None)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    if a[0] == "cfg":
        dp = float(opt.get("dp", "1.0"))
        cases = list(XC.ORDER) if a[1] == "all" else [a[1]]
        for case in cases:
            c = make(case, dp)
            if not c["precheck"]["ok"]:
                print(json.dumps(dict(case=case, written=None, precheck_ok=False, reason=c["precheck"]["reason"]), ensure_ascii=False))
                continue
            p = write(c)
            print(json.dumps(dict(case=case, run_id=c["run_id"], written=p, sha256=XC.sha256_file(p), precheck_ok=True,
                                  time=c["precheck"].get("time"), particles=c["precheck"].get("particles_model"),
                                  parms_diff=c["precheck"]["diff_vs_reference"]["parms_diff"]), ensure_ascii=False, default=float))
    elif a[0] == "gate":
        print(json.dumps(gate(a[1]), ensure_ascii=False))
    elif a[0] == "diff":
        print(json.dumps(diff_vs_ref(json.load(open(a[1], encoding="utf8"))), ensure_ascii=False, default=float))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
