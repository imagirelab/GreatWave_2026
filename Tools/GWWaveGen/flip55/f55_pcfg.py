# -*- coding: utf-8 -*-
"""FLIP55: the run configurations (cfg.json) derived from DFG-2B-V's LAUNCHED cfg, the printed diff, the precheck and a dry copy of the chain's
start gate (py -3.10 -B; numpy only, no Houdini). 2026-10-19 written new (Claude).
Reads only: DFG-2B-V's launched cfg Unity/Build/FLIP52B3/runs/ready/DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5.json (every key not listed as tied /
execution / name below must stay EQUAL to it), its table, its scene build check, its run folder (checkpoint v.1056 for the nest), the frozen
FLIP55 plan (when it exists). Writes only Unity/Build/FLIP55/runs/ready/<run_id>__<stage>.json and Unity/Build/FLIP55/plan/precheck_F55.json.

Options / stages (f55_common.OPTIONS; frozen in plan_F55_frozen.json):
  A375 g1    dp 0.375 m, the whole DFG-2B-V tank, frames 1-1657 (t 0-69 s: group 1 with its window [55, 69] s)   runnable (frozen g52b3_run.py)
  A375 full  the same run folder continued to frame 3001 (t 125 s, three windows) from its last checkpoint          runnable
  C2 g1      dp 0.25 m one-way nest x 180-356, y 0-60 m, frames 1057-1657 from the parent's v.1056                   DESIGN cfg (needs the nest tools)
  C2ID g1    the same nest at dp 0.5 m (gate GN1 and the baseline of C2)                                              DESIGN cfg (needs the nest tools)
usage:
  py -3.10 -B f55_pcfg.py diff [A375|C2|C2ID] [g1|full]   print the classified diff against DFG-2B-V's launched cfg
  py -3.10 -B f55_pcfg.py check [--dry]                   precheck of every option / stage (writes plan/precheck_F55.json; --dry: nothing)
  py -3.10 -B f55_pcfg.py cfg <A375|C2|C2ID> [g1|full]    write runs/ready/<run_id>__<stage>.json (precheck inside; not written if it fails)
  py -3.10 -B f55_pcfg.py gate <cfg.json>                 the f55_chain start gate, dry (reads only) -> json
  py -3.10 -B f55_pcfg.py show <A375|C2|C2ID> [g1|full]   print the cfg (not written)
Tags: [measured] [computed] [chosen] [guess].
"""
import os, sys, json, math, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import f55_common as C               # noqa: E402

PART_CAP_M = {"A375": 16.0, "C2": 7.5, "C2ID": 1.0}           # model peak cap per option [chosen: ~1.1 x the computed peak]
MAX_H = {"A375": 6.0, "C2": 3.0, "C2ID": 1.0}                 # per chain (execution only)
CAP_RESUMES = 2


# ====================================================================== diff helpers
def flat(o, pre=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flat(v, pre + str(k) + "."))
    else:
        out[pre[:-1]] = o
    return out


def diff_paths(a, b):
    fa, fb = flat(a), flat(b)
    keys = sorted(set(fa) | set(fb))
    return [k for k in keys if json.dumps(fa.get(k, "<absent>"), sort_keys=True, default=str) != json.dumps(fb.get(k, "<absent>"), sort_keys=True, default=str)]


def classify(paths, tied, execu, names):
    out = dict(tied=[], execution=[], names=[], unexpected=[])
    for p in paths:
        if any(p == t or p.startswith(t + ".") for t in names):
            out["names"].append(p)
        elif any(p == t or p.startswith(t + ".") for t in tied):
            out["tied"].append(p)
        elif any(p == t or p.startswith(t + ".") for t in execu):
            out["execution"].append(p)
        else:
            out["unexpected"].append(p)
    return out


def ref_cfg():
    return C.jload(C.DFGBV_READY)


# ====================================================================== A375 (runnable)
A_TIED = ("parms.dp", "parms.zb", "parms.Hz", "parms.Lx", "parms.W", "parms.ox", "parms.oy", "parms.oz", "parms.crop_x1", "level_box", "box")
A_EXEC = ("max_hours", "f_end", "t_end_s", "records.windows", "pstats_frames")


def make_A(stage="g1"):
    ref = ref_cfg()
    c = copy.deepcopy(ref)
    o = C.OPTIONS["A375"]
    b = C.box(o["dp"], o["x0"], o["Lx"], o["W"], o["zb"])
    rid = C.RID["A375"]
    P = c["parms"]
    P.update(dp=b["dp"], zb=b["z_bottom"], Hz=b["Hz"], Lx=b["Lx"], W=b["W"], ox=b["ox"], oy=b["oy"], oz=b["oz"], crop_x1=b["Lx"])
    c["box"] = b
    c["level_box"] = [0.0, b["Lx"], 0.0, b["W"]]
    f_end = C.F_END_G1 if stage == "g1" else C.F_END_FULL
    t_end = (f_end - 1) / float(C.FPS)
    c.update(run_id=rid, out_root=C.RUNS_ROOT, stage="FLIP55", f_end=int(f_end), t_end_s=float(t_end), max_hours=MAX_H["A375"],
             pstats_frames=[1, 2, int(f_end)])
    c["records"]["windows"] = [[t + C.GROUP_WIN[0], t + C.GROUP_WIN[1]] for t in C.FOCI if t + C.GROUP_WIN[1] <= t_end + 1e-9]
    c["case"] = dict(name="FLIP55_A375_%s_D19B_dp0p375" % stage, plan_frozen=C.PLAN_REL,
                     plan="Unity/Build/FLIP55/plan/plan_F55_frozen.json (options, resolution-tied keys, gates = DFGB4's, hollow quantities and reading)",
                     campaign="FLIP55 (3D resolution of DFG-2B-V)", option="A375", stage=stage, judged=True,
                     role="fallback: DFG-2B-V at dp 0.375 m (x1.33 refinement), everything else DFG-2B-V's launched cfg",
                     reference_cfg=C.rel(C.DFGBV_READY), reference_cfg_sha256=C.sha(C.DFGBV_READY), dir_case="DFGB4", P1_x_max_m=330.0)
    c["analysis"]["plan_frozen"] = C.PLAN_REL
    c["analysis"]["tool"] = "Tools/GWWaveGen/flip55/f55_ana.py (g52b3_ana.py unchanged, outputs inside FLIP55)"
    c["note"] = ("FLIP55 A375 (%s): DFG-2B-V's launched cfg at dp 0.375 m: box %g x %g m (whole 0.75 m voxels), zb %g m (layers tile the still "
                 "water exactly), frames 1-%d; the same scene, table, bands, sea, energy, solver, records and stage-A drift" % (stage, b["Lx"], b["W"],
                                                                                                                     b["z_bottom"], f_end))
    c["f55"] = dict(option="A375", stage=stage, tied=C.A375_TIED, execution=C.A375_EXEC, cost=C.cost("A375", stage),
                    runner="Tools/GWWaveGen/flip52b3/g52b3_run.py (frozen, unchanged)", chain="Tools/GWWaveGen/flip55/f55_chain.py",
                    cap_resumes=CAP_RESUMES)
    c.pop("precheck", None)
    c["precheck"] = precheck_A(c, ref)
    return c


def precheck_A(c, ref=None):
    ref = ref or ref_cfg()
    out = dict(checks={}, tags=dict(particles="computed (numpy, the scene's seeding rule)", memory="computed (measured anchors)", time="computed"))
    ck = out["checks"]
    cmp_c = {k: v for k, v in c.items() if k not in ("precheck",)}
    cmp_r = {k: v for k, v in ref.items() if k not in ("precheck",)}
    dl = diff_paths(cmp_r, cmp_c)
    cl = classify(dl, A_TIED, A_EXEC, C.A375_NAMES)
    out["diff_vs_DFGBV"] = cl
    ck["diff_only_registered"] = bool(not cl["unexpected"])
    o = C.OPTIONS["A375"]
    b = C.box(o["dp"], o["x0"], o["Lx"], o["W"], o["zb"])
    P = c["parms"]
    ck["box_rule"] = bool(c["box"] == b and all(float(P[k]) == float(v) for k, v in dict(dp=b["dp"], zb=b["z_bottom"], Hz=b["Hz"], Lx=b["Lx"], W=b["W"],
                                                                                          ox=b["ox"], oy=b["oy"], oz=b["oz"], crop_x1=b["Lx"]).items())
                          and float(P["gridscale"]) == 2.0 and float(P["x0"]) == 0.0)
    ck["still_level_tiles"] = bool(abs(C.seeded_still_level(b["dp"], b["z_bottom"])) < 1e-12)
    ck["sides_cover_DFGBV_tank"] = bool(b["Lx"] >= 412.0 and b["W"] >= 140.0 and b["W"] - 140.0 < b["vox"] and b["Lx"] - 412.0 < b["vox"])
    ck["band_parms_equal"] = bool(all(float(P[k]) == float(ref["parms"][k]) for k in ("sd0", "sd_gen", "sd_sw", "xg_end", "x_p", "wall_taper_m", "h0",
                                                                                       "relax_g", "in_gain", "sd_gain", "ramp_s", "dir_tf", "vol_x0", "vol_x1")))
    dr = c.get("dir") or {}
    ck["table_same_file"] = bool(dr == ref.get("dir") and os.path.exists(dr.get("npz") or "") and C.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    bc = C.jtry(C.DFGB4_BUILD_CHECK) or {}
    ck["scene_frozen"] = bool(bc.get("all_ok") and os.path.exists(C.DFGB4_HIP) and bc.get("hip_sha256") == C.DFGB4_HIP_SHA256
                              and C.sha256_file(C.DFGB4_HIP) == C.DFGB4_HIP_SHA256)
    cs = C.cost("A375", c["f55"]["stage"])
    out["cost"] = cs
    ck["particles_le_cap"] = bool(cs["particles_peak"][1] / 1e6 <= PART_CAP_M["A375"])
    ck["time_within_resumes"] = bool(cs["time_h"][1] <= float(c["max_hours"]) * (CAP_RESUMES + 1))
    ck["records_windows"] = bool(c["records"]["windows"] == [[t - 8.0, t + 6.0] for t in C.FOCI if t + 6.0 <= c["t_end_s"] + 1e-9])
    ck["frames"] = bool(c["f_end"] in (C.F_END_G1, C.F_END_FULL) and c["f_start"] == 1 and c["f_first"] == 1)
    ck["checkpoints_equal"] = bool(c["ckpt_every"] == ref["ckpt_every"] and c["ckpt_list"] == ref["ckpt_list"] and c["wall_limit_s"] == ref["wall_limit_s"]
                                   and c["disk_stop_free_gb"] == ref["disk_stop_free_gb"])
    ck["out_root_FLIP55"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(C.B55 + "/"))
    ck["plan_named"] = bool(c["case"]["plan_frozen"] == C.PLAN_REL and c["analysis"]["plan_frozen"] == C.PLAN_REL)
    ck["no_temp_paths"] = C.no_temp_paths(c)
    pc = plan_consistency("A375", c)
    out["plan_consistency"] = pc
    ck["plan_consistency"] = bool(pc["ok"])
    out["ok"] = bool(all(ck.values()))
    out["reason"] = None if out["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    return out


# ====================================================================== C2 / C2ID (design cfgs; the nest tools come after approval)
N_TIED = ("parms.dp", "parms.ox", "parms.oy", "parms.oz", "box")
N_NEST = ("parms.x0", "parms.Lx", "parms.W", "parms.crop_x0", "parms.crop_x1", "parms.crop_z1", "parms.xg_end", "parms.x_p", "parms.wall_taper_m",
          "parms.sd0", "parms.sd_gen", "parms.sd_sw", "parms.sd_taper_m", "parms.dir_on", "parms.ret_on", "parms.volcorr_on", "parms.vol_x0", "parms.vol_x1",
          "parms.ramp_s", "level_box", "level_regions", "gauges", "dir_check", "f_start", "f_first", "f_end", "t_end_s", "records", "pstats_frames",
          "fieldbox_frames", "n1_x", "n1_window", "drift", "nest", "kind", "max_hours", "dir", "wave.ramp_s", "ckpt_list")
N_NAMES = ("run_id", "out_root", "stage", "case", "note", "precheck", "analysis.plan_frozen", "analysis.tool", "analysis.dir_case", "f55")


def make_N(option="C2", stage="g1"):
    ref = ref_cfg()
    c = copy.deepcopy(ref)
    o = C.OPTIONS[option]
    b = C.box(o["dp"], o["x0"], o["Lx"], o["W"], o["zb"])
    x1 = b["x0"] + b["Lx"]
    f0 = o["f_start"]
    f_end = o["f_end"] if stage == "g1" else C.F_END_FULL
    t_end = (f_end - 1) / float(C.FPS)
    P = c["parms"]
    P.update(dp=b["dp"], x0=b["x0"], Lx=b["Lx"], W=b["W"], ox=b["ox"], oy=b["oy"], oz=b["oz"], crop_x0=b["x0"], crop_x1=x1, crop_z1=o["relax_y"][0],
             xg_end=o["relax_x"][1], x_p=o["relax_x"][1] - 3.0, wall_taper_m=o["relax_x"][1] - o["relax_x"][0],
             sd0=o["relax_y"][0], sd_gen=x1 + 1.0, sd_sw=x1 + 2.0, sd_taper_m=0.0, dir_on=0.0, ret_on=0.0, ramp_s=0.0,
             volcorr_on=0.0, vol_x0=o["relax_x"][1], vol_x1=min(x1, 400.0))
    c["box"] = b
    c.update(run_id=C.RID[option], out_root=C.RUNS_ROOT, stage="FLIP55", kind="3d_nest", f_start=int(f0), f_first=int(f0), f_end=int(f_end),
             t_end_s=float(t_end), max_hours=MAX_H[option], pstats_frames=[int(f0), int(f0) + 1, int(f_end)], fieldbox_frames=[int(f0) + 1],
             level_box=[b["x0"], x1, 0.0, b["W"]], n1_x=[], n1_window=[])
    c["dir"] = dict(set="DFGB4", parent_only=True, note="no generator table inside the nest: both bands relax toward the PARENT's fields (nest.bands)")
    c["wave"]["ramp_s"] = 0.0
    c["ckpt_list"] = [48, 24, 12]
    c["gauges"] = dict(x=[200.0, 240.0, 270.0], y=[0.5, 20.0, 40.0])
    c["dir_check"] = dict(every=0)
    c["level_regions"] = [list(r) for r in ref["level_regions"] if r[1] >= b["x0"] and r[2] <= x1 and r[4] <= b["W"]]
    c["records"] = dict(r2=True, r3_z=None, block=120, r4_block=24, preg_every=24,
                        r4=dict(x=[max(190.0, b["x0"] + 15.0), 335.0], z1=o["relax_y"][0], y0=-10.0, y1=16.0, clip_vox=6.0, t0=0.0, every=3),
                        r5=dict(t0=0.0, every=3), windows=[[t + C.GROUP_WIN[0], t + C.GROUP_WIN[1]] for t in C.FOCI if t + C.GROUP_WIN[1] <= t_end + 1e-9])
    c["drift"] = dict(stage="replay", source="the parent's volcorr/state.jsonl d(t) (stage A, x 110-400 m) applied to the nest's x %g-%g m" % (
        o["relax_x"][1], min(x1, 400.0)), rule="no own controller: the nest's volume follows the parent's measured correction [chosen]")
    c["nest"] = dict(
        parent=dict(run=C.rel(C.DFGBV_RUN), ready_cfg=C.rel(C.DFGBV_READY), checkpoint="ckpt/v.%04d.sim" % C.NEST_CKPT, t0_s=(C.NEST_CKPT - 1) / 24.0,
                    export_run=C.RID["C2P"], export="vel x/y/z + surface SDF of the parent on its 1 m grid in x %g-%g m (all y) and y %g-%g m (x %g-%g), "
                                                    "every frame %d-%d (a rerun of DFG-2B-V from its own v.%04d: restarts are bit-identical, hf eta diff 0.0 on "
                                                    "frames 865-891 [measured])" % (o["relax_x"][0] - 2.0, o["relax_x"][1] + 4.0, o["relax_y"][0] - 4.0,
                                                                                    min(o["relax_y"][1] + 2.0, 140.0), b["x0"], x1, f0, f_end, C.NEST_CKPT)),
        box=dict(x=[b["x0"], x1], y=[0.0, b["W"]], z=[b["z_bottom"], b["z_top"]], symmetry="y = 0 plane kept (= the parent's)",
                 outflow="none: the box ends at x %g m, beyond the still shoreline 350.25 m (dry beach)" % x1),
        bands=dict(x=list(o["relax_x"]), y=list(o["relax_y"]), corner="both weights, max()", weight="g50_tanklib relaxw (smooth01) over the band width, "
                   "relax_g 1 (= the parent's inlet band)", target="the parent's fields, trilinear in space, linear in time between parent frames"),
        init="reseeded at the parent's checkpoint v.%04d (t %.3f s): particles at dp on the scene's seeding rule below the parent's surface SDF, "
             "velocity sampled from the parent's vel field" % (C.NEST_CKPT, (C.NEST_CKPT - 1) / 24.0),
        records="hf / r2 every frame, r4 / r5 every 3rd frame in the window [55, 69] s; gauges x 200 / 240 / 270 m, y 0.5 / 20 / 40 m",
        lateral_margin_m=o["relax_y"][0] - 6.5, hood_region_y_m=6.5)
    c["case"] = dict(name="FLIP55_%s_%s_nest_x180y60_dp%s" % (option, stage, C.tag(o["dp"])), plan_frozen=C.PLAN_REL, campaign="FLIP55 (3D resolution of DFG-2B-V)",
                     option=option, stage=stage, judged=(option == "C2"), role=o["role"], reference_cfg=C.rel(C.DFGBV_READY),
                     reference_cfg_sha256=C.sha(C.DFGBV_READY), design_cfg=True,
                     runnable=False, needs=list(C.NEST_TOOLS) + ["amendment AM-F55-NEST (code sha256)", C.rel(C.NEST_BUILD_CHECK) + " all_ok"])
    c["analysis"]["plan_frozen"] = C.PLAN_REL
    c["analysis"]["tool"] = "Tools/GWWaveGen/flip55/f55_hollow.py (R0 ruler on the nest's centre section)"
    c["note"] = ("FLIP55 %s (%s): DESIGN cfg of the one-way nest at dp %g m inside DFG-2B-V, box x %g-%g, y 0-%g m, frames %d-%d; NOT runnable until the "
                 "nest tools exist (post-approval engineering)" % (option, stage, o["dp"], b["x0"], x1, b["W"], f0, f_end))
    c["f55"] = dict(option=option, stage=stage, cost=C.cost(option, stage), nest_tools=C.nest_tools_state())
    c.pop("precheck", None)
    c["precheck"] = precheck_N(c, ref)
    return c


def precheck_N(c, ref=None):
    ref = ref or ref_cfg()
    option = c["f55"]["option"]
    o = C.OPTIONS[option]
    out = dict(checks={}, tags=dict(particles="computed", memory="computed", time="computed"), design_cfg=True)
    ck = out["checks"]
    dl = diff_paths({k: v for k, v in ref.items() if k != "precheck"}, {k: v for k, v in c.items() if k != "precheck"})
    cl = classify(dl, N_TIED, N_NEST, N_NAMES)
    cl["nest"] = cl.pop("execution")
    out["diff_vs_DFGBV"] = cl
    ck["diff_only_registered"] = bool(not cl["unexpected"])
    b = c["box"]
    ck["box_rule"] = bool(b == C.box(o["dp"], o["x0"], o["Lx"], o["W"], o["zb"]))
    ck["inside_parent_tank"] = bool(b["x0"] >= 0.0 and b["x0"] + b["Lx"] <= 412.0 and b["W"] <= 95.0)
    ck["outflow_face_dry"] = bool(b["x0"] + b["Lx"] > 350.25 + 2.0)
    ck["inflow_face_upstream_of_hollow"] = bool(o["relax_x"][1] <= 200.0)       # group 1 converges at x ~228-238 m, lips at x >= 200 m [measured DFG-2B-E/V]
    ck["lateral_margin_ge_30m"] = bool(o["relax_y"][0] - 6.5 >= 30.0)
    ck["still_level_tiles"] = bool(abs(C.seeded_still_level(o["dp"], o["zb"])) < 1e-12)
    ck["sea_bed_energy_equal"] = bool(all(json.dumps(ref.get(k), sort_keys=True) == json.dumps(c.get(k), sort_keys=True) for k in ("bed", "sf", "solver"))
                                      and all(float(c["parms"][k]) == float(ref["parms"][k]) for k in ("h0", "gridscale", "cfl", "pcfl", "maxsub", "minsub",
                                                                                                        "bed_gap", "zb", "relax_g")))
    ck["parent_checkpoint"] = bool(os.path.exists(C.DFGBV_RUN + "/ckpt/v.%04d.sim" % C.NEST_CKPT))
    ck["parent_complete"] = bool(os.path.exists(C.DFGBV_RUN + "/chain.log") and " chain end " in open(C.DFGBV_RUN + "/chain.log", encoding="utf-8").read())
    cs = C.cost(option, c["f55"]["stage"])
    out["cost"] = cs
    ck["particles_le_cap"] = bool(cs["particles_peak"][1] / 1e6 <= PART_CAP_M[option])
    ck["out_root_FLIP55"] = bool(c["out_root"].replace("\\", "/").startswith(C.B55 + "/"))
    ck["plan_named"] = bool(c["case"]["plan_frozen"] == C.PLAN_REL)
    ck["no_temp_paths"] = C.no_temp_paths(c)
    pc = plan_consistency(option, c)
    out["plan_consistency"] = pc
    ck["plan_consistency"] = bool(pc["ok"])
    out["nest_tools"] = C.nest_tools_state()
    out["ok"] = bool(all(ck.values()))
    out["runnable"] = bool(out["ok"] and out["nest_tools"]["ok"])
    out["reason"] = None if out["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    return out


# ====================================================================== plan consistency (after the freeze)
def plan_consistency(option, c):
    if not os.path.exists(C.PLAN):
        return dict(ok=True, plan_exists=False, note="no frozen plan yet (pre-freeze check: the freeze stores this precheck)")
    pl = C.jload(C.PLAN)
    ck = dict(plan_sha256=C.plan_sha_ok())
    po = (pl.get("options") or {}).get(option) or {}
    st = c["f55"]["stage"]
    ck["option_frozen"] = bool(po)
    ck["dp"] = bool(po.get("dp") == c["parms"]["dp"])
    ck["box"] = bool(json.dumps(po.get("box"), sort_keys=True) == json.dumps(c["box"], sort_keys=True))
    ck["reference_cfg_sha"] = bool((pl.get("reference") or {}).get("ready_cfg_sha256") == C.sha(C.DFGBV_READY))
    frozen_cfg_sha = ((po.get("stages") or {}).get(st) or {}).get("cfg_sha16")
    cc = {k: v for k, v in c.items() if k not in ("precheck", "f55")}
    ck["cfg_as_frozen"] = bool(frozen_cfg_sha == sha16(cc))
    return dict(ok=bool(all(ck.values())), plan_exists=True, checks=ck)


def sha16(o):
    import hashlib
    return hashlib.sha256(json.dumps(C.clean(o), sort_keys=True, ensure_ascii=False, default=float).encode("utf8")).hexdigest()[:16]


# ====================================================================== io
def make(option, stage="g1"):
    if option == "A375":
        return make_A(stage)
    if option in ("C2", "C2ID"):
        return make_N(option, stage)
    raise SystemExit("unknown option %s" % option)


def cfg_path(option, stage):
    return "%s/%s__%s.json" % (C.READY, C.RID[option], stage)


def write(c):
    p = cfg_path(c["f55"]["option"], c["f55"]["stage"])
    C.guard_out(os.path.dirname(p))
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(c, fh, indent=1, ensure_ascii=False, default=float)
    return p


def gate(cfgp):
    """dry copy of the f55_chain (= g52b3_chain) start gate + the FLIP55 extras (reads only)."""
    cfg = C.jload(cfgp)
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict) or pc.get("ok") is not True:
        bad.append("precheck not ok: %s" % (pc or {}).get("reason"))
    if (cfg.get("case") or {}).get("design_cfg"):
        bad.append("design cfg (nest): not runnable by f55_chain / g52b3_run")
    bc = C.jtry(C.DFGB4_BUILD_CHECK) or {}
    if not bc.get("all_ok"):
        bad.append("build_check52b3 all_ok false / missing")
    if not os.path.exists(C.DFGB4_HIP) or bc.get("hip_sha256") != C.sha256_file(C.DFGB4_HIP):
        bad.append("hip missing or sha differs from build_check52b3")
    dr = cfg.get("dir") or {}
    if not os.path.exists(dr.get("npz") or "") or C.sha256_file(dr["npz"]) != dr.get("npz_sha256"):
        bad.append("table missing or sha differs")
    pf = (cfg.get("case") or {}).get("plan_frozen")
    p = pf if os.path.isabs(pf or "") else os.path.join(C.REPO, pf or "")
    if not (os.path.exists(p) and os.path.exists(p + ".sha256")):
        bad.append("frozen plan or .sha256 missing: %s" % p)
    elif open(p + ".sha256", encoding="utf-8").read().split()[0] != C.sha256_file(p):
        bad.append("frozen plan sha differs from .sha256")
    rd = os.path.join(C.B52B3, cfg.get("out_root", "runs"), cfg["run_id"]).replace("\\", "/")
    return dict(gate_ok=not bad, reasons=bad, run_dir=rd, run_dir_in_FLIP55=rd.startswith(C.B55 + "/"))


def check_all(dry=False):
    out = dict(plan=C.PLAN_REL, options={})
    for opt, stages in (("A375", ("g1", "full")), ("C2", ("g1",)), ("C2ID", ("g1",))):
        for st in stages:
            c = make(opt, st)
            out["options"]["%s_%s" % (opt, st)] = dict(run_id=c["run_id"], precheck=c["precheck"], cfg_sha16=sha16({k: v for k, v in c.items()
                                                                                                                   if k not in ("precheck", "f55")}))
    out["ok"] = bool(all(v["precheck"]["ok"] for v in out["options"].values()))
    if not dry:
        C.jdump(out, C.PRECHECK)
    return out


def print_diff(option, stage):
    ref = ref_cfg()
    c = make(option, stage)
    fr, fc = flat({k: v for k, v in ref.items() if k != "precheck"}), flat({k: v for k, v in c.items() if k != "precheck"})
    cl = c["precheck"]["diff_vs_DFGBV"]
    print("== %s %s vs DFG-2B-V launched cfg (%s)" % (option, stage, C.rel(C.DFGBV_READY)))
    for grp in [g for g in ("tied", "execution", "nest", "unexpected", "names") if g in cl]:
        print("-- %s (%d)" % (grp, len(cl[grp])))
        for p in cl[grp]:
            if grp == "names" and (p.startswith("precheck") or p.startswith("f55.") or p.startswith("case.") or p == "note"):
                continue
            a = json.dumps(fr.get(p, "<absent>"), default=str); b = json.dumps(fc.get(p, "<absent>"), default=str)
            print("   %-28s %s -> %s" % (p, a[:70], b[:70]))
    return cl


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "diff":
        sel = [(a[1], a[2] if len(a) > 2 else "g1")] if len(a) > 1 else [("A375", "g1"), ("A375", "full"), ("C2", "g1"), ("C2ID", "g1")]
        res = {}
        for opt, st in sel:
            cl = print_diff(opt, st)
            res["%s_%s" % (opt, st)] = dict(tied=len(cl["tied"]), execution=len(cl.get("execution", [])), nest=len(cl.get("nest", [])),
                                            unexpected=cl["unexpected"])
        print(json.dumps(res, ensure_ascii=False))
    elif a[0] == "check":
        o = check_all(dry="--dry" in sys.argv)
        print(json.dumps(C.clean(dict(ok=o["ok"], options={k: dict(run_id=v["run_id"], ok=v["precheck"]["ok"], reason=v["precheck"]["reason"],
                                                                   runnable=v["precheck"].get("runnable", True),
                                                                   particles=v["precheck"]["cost"]["particles_model"],
                                                                   peak=v["precheck"]["cost"]["particles_peak"], ws_fit=v["precheck"]["cost"]["ws_fit_gb"],
                                                                   commit_need=v["precheck"]["cost"]["commit_need_gb"], time_h=v["precheck"]["cost"]["time_h"],
                                                                   disk_gb=v["precheck"]["cost"]["disk_gb"], unexpected=v["precheck"]["diff_vs_DFGBV"]["unexpected"],
                                                                   cfg_sha16=v["cfg_sha16"])
                                                           for k, v in o["options"].items()})), ensure_ascii=False))
    elif a[0] in ("cfg", "show") and len(a) >= 2:
        opt = a[1]; st = a[2] if len(a) > 2 else "g1"
        c = make(opt, st)
        if a[0] == "show":
            print(json.dumps(C.clean(c), ensure_ascii=False, indent=1)); return
        if not c["precheck"]["ok"]:
            print(json.dumps(dict(option=opt, stage=st, written=None, precheck_ok=False, reason=c["precheck"]["reason"]), ensure_ascii=False)); return
        p = write(c)
        print(json.dumps(C.clean(dict(option=opt, stage=st, run_id=c["run_id"], written=p, sha256=C.sha256_file(p), precheck_ok=True,
                                      runnable=c["precheck"].get("runnable", True), particles=c["precheck"]["cost"]["particles_model"],
                                      time_h=c["precheck"]["cost"]["time_h"])), ensure_ascii=False))
    elif a[0] == "gate" and len(a) >= 2:
        print(json.dumps(gate(a[1]), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
