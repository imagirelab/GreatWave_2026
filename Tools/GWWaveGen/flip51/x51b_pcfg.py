# -*- coding: utf-8 -*-
"""FLIP51 X2B': the run configuration (dp 0.5) with its precheck and the dry copy of the g50_chain start gate (py -3.10 -B).
2026-10-17 written new (Claude). Read only: the registered X2 0.5 m cfg (Unity/Build/FLIP51/runs/ready/S51X2_D19B_T7_g60s28_dp0p5.json, its sha
is the one plan E registered), flip50 g50_pcfg (precheck), flip51 x51_pcfg (gate). No flip50 / flip51 file, hip, build_check or run is written.

The cfg is the X2 0.5 m cfg (D19B tank, bands, stage-A drift AM-D18, gravity only, T 7 s, the X2 direction set, a_sum 6.331240 m, ramp 14 s,
0-75 s, hf / r2 / r3 every frame, r4 every 3rd frame in 35-75 s, budget 3.0 h) with ONLY these differences (checked by diff_vs_X2):
  dir      the X2B table (x51b_table: x_f 275.25 m, t_f 0, grid x 0-244 m; same set, T, a_sum)              <- change 1 (focus)
  parms    sd_gen 180.25 -> 210.25 m, sd_sw 210.25 -> 240.25 m (CTRL parms; the unchanged VEX reads them)    <- change 2 (side band)
  sf       the linear descriptor with H = the new table's linear height at the gauge (110, 0.5) (T, L, c, k unchanged; not a forcing table)
  records  r5 (surface meshes) every frame in 35-75 s (X2: every 3rd) so every period can be played at 24/s in Unity; r4 unchanged
  names    run_id, case block, plan_frozen = Unity/Build/FLIP51/plan/plan_X2B_frozen.json, wave / analysis text with the new x_f, note
The hip is Houdini/FLIP50/g50_tank.hiplc UNCHANGED (its CTRL has sd_gen / sd_sw; g50_run.py sets every cfg parm on CTRL).
usage:
  py -3.10 -B x51b_pcfg.py cfg [--r5-every=1|3]     write Unity/Build/FLIP51/runs/ready/<run_id>.json (precheck inside; not written if it fails)
  py -3.10 -B x51b_pcfg.py gate [<cfg.json>]         the g50_chain start gate, dry (reads only) -> json
  py -3.10 -B x51b_pcfg.py diff [<cfg.json>]         differences against the X2 0.5 m cfg
  py -3.10 -B x51b_pcfg.py precheck [<cfg.json>]     recompute the precheck of a written cfg (reads only)
"""
import os, sys, json, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import x51b_common as XB             # noqa: E402
import x51b_table as XBT             # noqa: E402
import x51_common as XC              # noqa: E402  read only
import x51_pcfg as XP                # noqa: E402  read only (gate)
import g50_common as GC              # noqa: E402  read only
import g50_pcfg as PC                # noqa: E402  read only (precheck)

ALLOWED_PARM_DIFF = ("sd_gen", "sd_sw")
SAME_BLOCKS = ("box", "bed", "drift", "solver", "gauges", "level_regions", "n1_x", "n1_window", "shore_x", "level_box", "ckpt_on", "ckpt_every",
               "ckpt_list", "wall_limit_s", "level_guard_m", "disk_stop_free_gb", "layout", "f_start", "f_first", "f_end", "t_end_s", "max_hours",
               "dir_check", "fieldbox_frames", "pstats_frames", "out_root", "stage", "kind")
SAME_DIR_KEYS = ("T", "omega", "theta_max_deg", "n", "weight", "theta_deg", "w", "a_sum", "a_j", "a_j_max", "t_f", "fields", "ret_on")
X2_CFG_SHA_PLAN_E = None              # read from plan_E_frozen.json at run time (registered sha of the X2 0.5 m cfg)


def x2_cfg():
    c = json.load(open(XB.X2_CFG, encoding="utf8"))
    plan = XB.jload(XC.PLAN_E) or {}
    reg = ((((plan.get("setups") or {}).get("cases") or {}).get("X2") or {}).get("runs") or {}).get("dp0p5") or {}
    sha = XB.sha256_file(XB.X2_CFG)
    return c, dict(path=XB.rel(XB.X2_CFG), sha256=sha, plan_E_registered_sha256=reg.get("cfg_sha256"),
                   equals_plan_E_registration=bool(reg.get("cfg_sha256") and reg["cfg_sha256"] == sha))


def make(r5_every=XB.R5_EVERY_DEFAULT):
    base, prov = x2_cfg()
    if not prov["equals_plan_E_registration"]:
        raise SystemExit("the X2 0.5 m cfg %s is not the one plan E registered (%s): not used as the base" % (prov["path"], prov))
    c = copy.deepcopy(base)
    c.pop("precheck", None)
    c.pop("hip_sha256", None); c.pop("module_shas_at_chain_start", None)
    tb = XBT.table_record()
    H_ref = tb["gauges_lin"]["x110_y0.5"]["H_lin"]
    c["run_id"] = XB.RUN_ID
    c["parms"]["sd_gen"] = float(XB.SD_GEN)
    c["parms"]["sd_sw"] = float(XB.SD_SW)
    c["dir"] = dict(tb, ret_on=1.0)
    c["sf"] = GC.sf_descriptor(XC.T7, H_ref, note="X2B': the inflow is the directional table cfg dir (T 7 s, x_f 275.25 m); this descriptor is "
                                                    "for T, L, c, k only")
    c["records"]["r5"] = dict(t0=0.0, every=int(r5_every))
    cs = c["case"]
    cs.update(name="FLIP51_X2B_D19B_T7_xf275_dp0p5", plan_frozen=XB.PLAN_REL,
              plan="Unity/Build/FLIP51/plan/plan_X2B_frozen.json (design, the two changes, registered predictions, co-equal criteria: convergence "
                   "AND print match, gates, verdict rule)",
              campaign="FLIP51-X2B", queue_id="X2B_dp0p5", judged=True, dir_case="E_X2B", e_case=XB.CASE, role=XB.CASE_REC["role"],
              label=XB.CASE_REC["label"], reference_cfg=XB.rel(XB.X2_CFG), reference_cfg_sha256=prov["sha256"],
              one_change="vs X2 (S51X2_D19B_T7_g60s28_dp0p5): the focus point x_f 220.25 -> 275.25 m and the table built for it",
              second_change="side band generation sd_gen 180.25 -> 210.25 m, sd_sw 210.25 -> 240.25 m (table x 0-244 m): without it no x_f breaks "
                            "at the focus (ray supply 0.99 -> 0.67 for x_f 220 -> 280) [computed, x51b_screen.py supplyfix]",
              unchanged="hip, bed, box, direction set, weights, a_sum 6.331240 m (no input enlargement), T 7 s, ramp 14 s, t_f 0, drift stage A, "
                        "dp 0.5, 0-75 s, gauges, budget",
              r5_rule="surface meshes every %d frame(s) in 35-75 s (X2: every 3rd) [chosen: every period playable at 24/s in Unity]" % int(r5_every))
    w = c["wave"]
    w.update(x_f_m=XB.X_F, t_f_s=XB.T_F, focal_crest_linear_m=tb["linear_refs"]["design_crest_xf"],
             kind="linear directional monochromatic sea, explicit direction set (%s), phases 0 at (x_f, 0) at t = t_f + nT" % XB.CASE_REC["label"],
             chosen_at_inlet="period T 7 s, the X2 directions and weights, a_sum 6.331240 m (= DM1A input sum, not enlarged), focus point "
                             "(275.25, 0) and time t = 7n s, side band generating to x 210.25 m [chosen]; computed by FLIP: shoaling, refraction, "
                             "focusing, breaking, any jet",
             tags=dict(T="chosen", directions="chosen (= X2)", a_sum="chosen (= DM1A)", x_f="chosen (X2B design)", side_band="chosen (X2B design)",
                       table="computed (x51b_table)"))
    an = c["analysis"]
    an["plan_frozen"] = XB.PLAN_REL
    an["x_f_m"] = XB.X_F
    an["x_break_target_m"] = 281.9
    an["x_break_target_note"] = "X2B' predicted break x 281.9 m [273-290] [computed, x51b_screen.py detail]; D's 240.25 m does not apply"
    c["note"] = ("FLIP51 X2B' (dp 0.5): 3D, half tank W 140 (45 m side band generating to x 210.25 m, blend to absorbing by 240.25 m), D19B (h0 19 m, "
                 "1:10 beach, toe 160.25 m), directional sea T 7 s, %s, a_sum %.6f m (= DM1A), focus (275.25, 0) at t = 7n s, ramp 14 s, stage A "
                 "(AM-D18), 0-75 s. Records hf/r2/r3 every frame, r4 every 3rd and r5 every %d frame(s) in 35-75 s. Hip Houdini/FLIP50/g50_tank.hiplc "
                 "unchanged." % (XB.CASE_REC["label"], XC.A_SUM, int(r5_every)))
    c["precheck"] = precheck_X2B(c)
    return c


def diff_vs_X2(c):
    base, prov = x2_cfg()
    pa, pb = c["parms"], base["parms"]
    keys = sorted(set(pa) | set(pb))
    dd = {k: [pb.get(k), pa.get(k)] for k in keys if pa.get(k) != pb.get(k)}
    other = {k: "differs" for k in SAME_BLOCKS if c.get(k) != base.get(k)}
    rb, ra = copy.deepcopy(base["records"]), copy.deepcopy(c["records"])
    r5b, r5a = rb.pop("r5", None), ra.pop("r5", None)
    if ra != rb:
        other["records (except r5)"] = "differs"
    r5_ok = bool(isinstance(r5a, dict) and r5a.get("t0") == (r5b or {}).get("t0") and int(r5a.get("every", 0)) in (1, 3))
    da, db = c.get("dir") or {}, base.get("dir") or {}
    dir_same = {k: bool(da.get(k) == db.get(k)) for k in SAME_DIR_KEYS}
    dir_x = dict(x_f=[db.get("x_f"), da.get("x_f")], grid_x=[(db.get("grid") or {}).get("x"), (da.get("grid") or {}).get("x")])
    ok = bool(set(dd) <= set(ALLOWED_PARM_DIFF) and set(dd) == set(ALLOWED_PARM_DIFF) and not other and r5_ok and all(dir_same.values())
              and abs(float(pa["sd_gen"]) - XB.SD_GEN) < 1e-12 and abs(float(pa["sd_sw"]) - XB.SD_SW) < 1e-12
              and abs(float(da.get("x_f", -1)) - XB.X_F) < 1e-12)
    return dict(reference=prov, parms_diff=dd, allowed_parms=list(ALLOWED_PARM_DIFF), other_blocks_diff=other, r5=[r5b, r5a], r5_ok=r5_ok,
                dir_same_keys=dir_same, dir_changed=dir_x, ok=ok)


def precheck_X2B(c):
    """g50_pcfg.precheck (read only) with the D / plan E items replaced by their X2B versions:
    layout_D_named -> plan_X2B_named; table_is_case -> table_is_X2B; side_band -> side_band_X2B (sd_gen 210.25, sd_sw 240.25);
    table_covers_bands -> table_covers_bands_X2B (grid x end >= sd_sw of THIS cfg). Added: table_G1_checked (table_check_X2B.json all_ok, same
    content), only_planned_diffs_vs_X2, records_as_designed, out_root_absolute_FLIP51. wall_le_limit (dp 0.5, 3.0 h) kept."""
    pc = PC.precheck(c)
    ck = dict(pc["checks"])
    for k in ("layout_D_named", "table_is_case", "side_band", "table_covers_bands"):
        ck.pop(k, None)
    P = c["parms"]
    an = c.get("analysis") or {}
    ck["plan_X2B_named"] = bool(c.get("layout") == "D" and an.get("plan_frozen") == XB.PLAN_REL and (c.get("case") or {}).get("plan_frozen") == XB.PLAN_REL
                                and abs(float(an.get("p1_x_max_m", -1)) - GC.X_P1_MAX) < 1e-9 and c.get("run_id") == XB.RUN_ID)
    dr = c.get("dir") or {}
    th, w = XB.components()
    ok_t = False
    try:
        info = json.loads(str(np.load(dr["npz"], allow_pickle=False)["info"]))
        ok_t = bool(info.get("case") == "E_X2B" and abs(info["T"] - XC.T7) < 1e-12 and abs(info["a_sum"] - XC.A_SUM) < 1e-12
                    and abs(info["x_f"] - XB.X_F) < 1e-12 and abs(info["t_f"] - XB.T_F) < 1e-12
                    and np.allclose(info["theta_deg"], th, atol=0, rtol=0) and np.allclose(info["w"], w, atol=0, rtol=0)
                    and float(P["ramp_s"]) == XC.RAMP7 and abs(float(c["sf"]["T"]) - XC.T7) < 1e-12 and float(P["dir_tf"]) == XB.T_F)
    except Exception:
        ok_t = False
    ck["table_is_X2B"] = ok_t
    ck["side_band_X2B"] = bool(float(P["sd_on"]) == 1.0 and abs(float(P["sd0"]) - (float(P["W"]) - GC.SD_BAND)) < 1e-9
                               and abs(float(P["sd_gen"]) - XB.SD_GEN) < 1e-12 and abs(float(P["sd_sw"]) - XB.SD_SW) < 1e-12
                               and float(P["sd_gen"]) < float(P["sd_sw"]) and GC.SIDE_BAND[1] < float(P["sd0"])
                               and max(float(v) for v in c["gauges"]["y"]) < float(P["sd0"]))
    ck["table_covers_bands_X2B"] = bool((dr.get("grid") or {}).get("x", [0, 0])[1] >= float(P["sd_sw"])
                                        and (dr.get("grid") or {}).get("y", [0, 0])[1] >= float(P["W"]) - 1e-9)
    tc = XB.jload(XB.TABLE_CHECK) or {}
    ck["table_G1_checked"] = bool(tc.get("all_ok") and (tc.get("info") or {}).get("content_sha256") == dr.get("content_sha256")
                                  and tc.get("npz_sha256") == dr.get("npz_sha256"))
    d = diff_vs_X2(c)
    ck["only_planned_diffs_vs_X2"] = bool(d["ok"])
    rec = c["records"]
    ck["records_as_designed"] = bool(rec.get("r2") and rec.get("r3_z") == GC.R3_Y and (rec.get("r4") or {}).get("every") == 3
                                     and rec.get("windows") == [list(XC.REC_WINDOW)] and isinstance(rec.get("r5"), dict)
                                     and int(rec["r5"].get("every", 0)) in (1, 3))
    ck["out_root_absolute_FLIP51"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(XC.B51 + "/")
                                          and os.path.join(GC.B50, c["out_root"]).replace("\\", "/") == c["out_root"].replace("\\", "/"))
    ck["dp_0p5_3d"] = bool(float(P["dp"]) == XB.DP and c.get("kind") == "3d")
    pc["checks"] = ck
    pc["diff_vs_X2"] = d
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    pc["replaced_items"] = ("layout_D_named -> plan_X2B_named; table_is_case -> table_is_X2B; side_band -> side_band_X2B; "
                            "table_covers_bands -> table_covers_bands_X2B; added table_G1_checked, only_planned_diffs_vs_X2, records_as_designed, "
                            "out_root_absolute_FLIP51, dp_0p5_3d")
    return pc


def write(c):
    p = XB.CFG
    XB.guard(os.path.dirname(p))
    with open(p, "w", encoding="utf8") as fh:
        json.dump(c, fh, indent=1, ensure_ascii=False, default=float)
    return p


def gate(cfgp=None):
    """the dry g50_chain start gate (x51_pcfg.gate: precheck ok, FLIP50 build_check all_ok and the hip sha, table sha, frozen plan + .sha256)
    plus: the cfg is the X2B run and its out_root lands in FLIP51."""
    cfgp = cfgp or XB.CFG
    g = XP.gate(cfgp)
    cfg = json.load(open(cfgp, encoding="utf8"))
    if cfg.get("run_id") != XB.RUN_ID:
        g["reasons"].append("cfg run_id %s is not %s" % (cfg.get("run_id"), XB.RUN_ID))
    if not g.get("run_dir_in_FLIP51"):
        g["reasons"].append("run dir %s not in FLIP51" % g.get("run_dir"))
    if (cfg.get("case") or {}).get("plan_frozen") != XB.PLAN_REL:
        g["reasons"].append("cfg plan_frozen is not the X2B plan")
    g["gate_ok"] = not g["reasons"]
    return g


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "cfg":
        c = make(int(opt.get("r5-every", XB.R5_EVERY_DEFAULT)))
        if not c["precheck"]["ok"]:
            print(json.dumps(dict(written=None, precheck_ok=False, reason=c["precheck"]["reason"], diff=c["precheck"].get("diff_vs_X2")),
                             ensure_ascii=False, default=float))
            sys.exit(1)
        p = write(c)
        print(json.dumps(dict(run_id=c["run_id"], written=p, sha256=XB.sha256_file(p), precheck_ok=True, time=c["precheck"].get("time"),
                              particles=c["precheck"].get("particles_model"), parms_diff=c["precheck"]["diff_vs_X2"]["parms_diff"],
                              r5=c["records"]["r5"]), ensure_ascii=False, default=float))
    elif a[0] == "gate":
        print(json.dumps(gate(a[1] if len(a) > 1 else None), ensure_ascii=False))
    elif a[0] == "diff":
        print(json.dumps(diff_vs_X2(json.load(open(a[1] if len(a) > 1 else XB.CFG, encoding="utf8"))), ensure_ascii=False, default=float))
    elif a[0] == "precheck":
        c = json.load(open(a[1] if len(a) > 1 else XB.CFG, encoding="utf8"))
        pc = precheck_X2B(c)
        print(json.dumps(dict(ok=pc["ok"], reason=pc["reason"], checks=pc["checks"], same_as_written=bool(pc["checks"] == (c.get("precheck") or {}).get("checks"))),
                         ensure_ascii=False, default=float))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
