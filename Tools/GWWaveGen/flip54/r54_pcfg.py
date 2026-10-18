# -*- coding: utf-8 -*-
"""FLIP54 R54: write the cfg of one R54 strip (K0 or K4 of K54 at dp 0.25 m) and its pre-run checks (py -3.10 -B; numpy; < 1 min).
2026-10-18 written new (Claude, FLIP54 builder R). The cfg is g54_pcfg.make(arm) - the UNCHANGED K54 cfg builder, with the K54 calibrated
H (k54/plan/calibration_K0.json, read only) - run while g54_common.DP is 0.25 in this process (r54_common.patched_dp), then renamed for R54:
run id R54_*_dp0p25, out_root r54/strips, case / analysis plan_frozen = the R54 plan, max_hours 5 h (a dp-0.25 strip is ~1.2-1.6 h; K54's
0.75 h was for 5.5-6.6 min strips). The grid follows the unchanged gridscale 2.0 (0.5 m); bed, wave (Fenton table, H, T, ramp, inlet band),
sponge, drift stage A, records, gauges, level regions, 90 s, checkpoints and launch limit stay the K54 values.

Precheck = every K54 precheck item evaluated at dp 0.25, except four that name K54 or assume a one-launch strip, which R54 replaces:
  run_id_named        -> the R54 name rule        plan_named / plan_frozen_sha_ok -> the R54 plan
  one_launch_est      -> chain_est_le_0p8_max_hours (the chain splits a strip into <= 1740 s launches from checkpoints)
plus: dp_0p25_grid_0p5, identical_to_K54_cfg_except_dp_tied (field-by-field against the K54 ready cfg of the same arm; the only allowed
differences are listed in DP_TIED / R54_NAMES), H_T_equal_K54, K54_reference_complete, particles_x8 (7.6-8.4 x the K54 model count).

usage:
  py -3.10 -B r54_pcfg.py cfg <K0|K4>                         write Unity/Build/FLIP54/r54/strips/ready/<run_id>.json (refuses if not ok)
  py -3.10 -B r54_pcfg.py dry [--out=<dir under FLIP54>]      both arms into Unity/Build/FLIP54/_scratch/dry_r54 (no plan sha needed)
Prints one JSON line last.
"""
import os, sys, json, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import r54_common as RC       # noqa: E402
import g54_common as C        # noqa: E402
import g54_pcfg as P54        # noqa: E402  (read only, never edited)

# fields allowed to differ from the K54 cfg of the same arm
DP_TIED = ("parms.dp", "parms.ox", "parms.oy", "parms.oz",                    # particle size and the grid-face offsets (box48: 0.5 vox)
           "box.dp", "box.vox", "box.cells", "box.z_floor", "box.ox", "box.oy", "box.oz",
           "sf_check.zl")                                                     # the inlet probe height 0.5 vox
R54_NAMES = ("run_id", "out_root", "note", "precheck", "max_hours", "wave.H_rule", "analysis.plan_frozen",
             "case.name", "case.campaign", "case.plan_frozen", "case.plan", "case.dry_build", "case.dp", "case.dp_ref", "case.ref_run",
             "case.ref_campaign", "case.question")


def flat(o, pre=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flat(v, (pre + "." if pre else "") + str(k)))
    else:
        out[pre] = o
    return out


def allowed(path):
    for a in DP_TIED + R54_NAMES:
        if path == a or path.startswith(a + "."):
            return True
    return False


def diff_vs_k54(c, refc):
    fa, fb = flat(refc), flat(c)
    keys = sorted(set(fa) | set(fb))
    unexpected, tied = [], []
    for k in keys:
        same = (k in fa and k in fb and json.dumps(fa[k], sort_keys=True) == json.dumps(fb[k], sort_keys=True))
        if same:
            continue
        (tied if allowed(k) else unexpected).append(k)
    return unexpected, tied


def make(arm, dry=False):
    if arm not in RC.ARMS:
        raise SystemExit("R54 arms: %s" % ", ".join(RC.ARMS))
    ref = RC.k54_ref(arm)
    refc = RC.jload(ref.get("ready_cfg") or "") or {}
    with RC.patched_dp(RC.DP):
        c = P54.make(arm)                              # K54 builder, calibrated H, precheck at dp 0.25
        k54pc = c["precheck"]
    H, T = float(c["wave"]["H_m"]), float(c["wave"]["T_s"])
    rid = RC.run_id(arm, H, T)
    c["run_id"] = rid
    c["out_root"] = RC.OUT_ROOT
    c["max_hours"] = RC.MAX_HOURS
    case = c["case"]
    case.update(name="FLIP54_R54_%s" % arm, campaign="R54", plan_frozen=RC.PLAN_REL, dry_build=bool(dry), dp=RC.DP, dp_ref=RC.DP_REF,
                ref_run=ref.get("run_id"), ref_campaign="K54",
                plan="Unity/Build/FLIP54/r54/plan/plan_R54_frozen.json (quantities, reading rule, K54 references with sha256)",
                question="does the 2D hollow depend on the particle size? (K54 %s rerun at dp 0.25 m, everything else identical)" % arm)
    c["analysis"]["plan_frozen"] = RC.PLAN_REL
    c["wave"]["H_rule"] = ("frozen = the K54 %s strip's H %.2f m (K54 calibration k54/plan/calibration_K0.json, not recalibrated: the resolution check "
                           "keeps the dp-0.5 input wave) [calibrated in K54]" % (arm, H))
    c["note"] = ("FLIP54 R54 %s: the K54 strip %s rerun at dp %.2f m (grid %.2f m; gridscale 2.0 unchanged); bed, Fenton inlet T %.4g s H %.2f m, exit "
                 "sponge, drift stage A, records, gauges, 90 s identical to K54; judged k2-k4 with the unchanged g54_ana ruler." % (
                     arm, ref.get("run_id"), RC.DP, RC.DP * RC.GRIDSCALE, T, H))
    # ---- precheck
    items = dict(k54pc["checks"])
    replaced = {k: items.pop(k, None) for k in ("one_launch_est", "plan_named", "plan_frozen_sha_ok", "run_id_named")}
    ck = dict(items)
    P = c["parms"]
    ck["dp_0p25_grid_0p5"] = bool(float(P["dp"]) == RC.DP and float(P["gridscale"]) == RC.GRIDSCALE and float(c["box"]["vox"]) == RC.DP * RC.GRIDSCALE)
    unexpected, tied = diff_vs_k54(c, refc) if refc else (["(no K54 ready cfg)"], [])
    ck["identical_to_K54_cfg_except_dp_tied"] = bool(refc and not unexpected)
    ck["dp_tied_keys_changed"] = bool("parms.dp" in tied and "box.vox" in tied)
    sf, sfr = c.get("sf") or {}, refc.get("sf") or {}
    ck["H_T_equal_K54"] = bool(sfr and abs(float(sf["H"]) - float(sfr["H"])) < 1e-12 and abs(float(sf["T"]) - float(sfr["T"])) < 1e-12
                               and json.dumps(sf, sort_keys=True) == json.dumps(sfr, sort_keys=True))
    ck["K54_reference_complete"] = bool(ref.get("ok"))
    n = int(k54pc["particles_model"])
    ratio = n / max(1, int(ref.get("particles_model") or 0))
    ck["particles_x8"] = bool(7.6 <= ratio <= 8.4)
    ck["run_id_named"] = bool(c["run_id"] == RC.run_id(arm, float(sf.get("H", -1)), T) and c["run_id"].endswith("_dp0p25"))
    ck["plan_named"] = bool(case.get("plan_frozen") == RC.PLAN_REL and c["analysis"].get("plan_frozen") == RC.PLAN_REL)
    if not dry:
        ck["plan_frozen_sha_ok"] = bool(RC.plan_sha_ok())
    wm = RC.wall_model(arm, n, int(c["f_end"]))
    ck["chain_est_le_0p8_max_hours"] = bool(wm.get("wall_est_s") is not None and wm["wall_est_s"] <= 0.8 * RC.MAX_HOURS * 3600.0)
    ck["chain_hi_le_max_hours"] = bool(wm.get("wall_hi_s") is not None and wm["wall_hi_s"] <= RC.MAX_HOURS * 3600.0)
    pc = dict(checks=ck, k54_items_replaced={k: v for k, v in replaced.items()}, particles_model=n, particles_ratio_vs_K54=ratio,
              water_m3=k54pc.get("water_m3"), frames=int(c["f_end"]), wall_est_s=wm.get("wall_est_s"), wall_hi_s=wm.get("wall_hi_s"),
              launches_est=wm.get("launches"), wall_model=wm, k54_wall_est_rule_unused=k54pc.get("wall_est_rule"),
              diff_vs_K54=dict(k54_cfg=(ref.get("ready_cfg") or "").replace(C.REPO + "/", ""), changed_dp_tied=tied, unexpected=unexpected,
                               allowed_dp_tied=list(DP_TIED), allowed_names=list(R54_NAMES)),
              bed_selfcheck_ok=k54pc.get("bed_selfcheck", {}).get("ok"), sponge=k54pc.get("sponge"), dry_build=bool(dry),
              tags=dict(particles="computed (numpy, the scene's seeding rule at dp 0.25)", wall="computed from measured records (r54_common.wall_model)"))
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "fails: " + ", ".join(k for k, v in ck.items() if not v)
    c["precheck"] = pc
    return c


def write(c, folder=None):
    folder = folder or RC.READY
    RC.guard_out(folder)
    p = folder + "/" + c["run_id"] + ".json"
    RC.jdump(c, p)
    return p


def summary(c, p):
    pc = c["precheck"]
    return dict(cfg=p, run_id=c["run_id"], precheck_ok=pc["ok"], reason=pc["reason"], H=c["wave"]["H_m"], T=c["wave"]["T_s"], dp=c["parms"]["dp"],
                particles_model=pc["particles_model"], wall_est_s=round(pc["wall_est_s"], 1) if pc.get("wall_est_s") else None,
                wall_hi_s=round(pc["wall_hi_s"], 1) if pc.get("wall_hi_s") else None, launches_est=pc.get("launches_est"),
                unexpected_diffs=pc["diff_vs_K54"]["unexpected"], dp_tied_changed=pc["diff_vs_K54"]["changed_dp_tied"])


def main(argv):
    pos, opt = P54.parse(argv[1:])
    if not pos:
        print(__doc__); return 2
    if pos[0] == "cfg":
        c = make(pos[1])
        if not c["precheck"]["ok"]:
            print(json.dumps(C.clean(dict(summary(c, None), cfg=None)), ensure_ascii=False))
            return 1
        p = write(c)
        print(json.dumps(C.clean(summary(c, p)), ensure_ascii=False))
        return 0
    if pos[0] == "dry":
        od = RC.guard_out(opt.get("out") or (RC.SCRATCH + "/dry_r54"))
        rows, ok = [], True
        for arm in RC.ARM_ORDER:
            c = make(arm, dry=True)
            p = write(c, od)
            s = summary(c, p)
            rows.append(s)
            ok = ok and bool(c["precheck"]["ok"])
            print("%-3s %-40s dp %.2f H %.2f T %.2f particles %d est %.0f s (hi %.0f s, launches %s) ok %s %s" % (
                arm, s["run_id"], s["dp"], s["H"], s["T"], s["particles_model"], s["wall_est_s"] or -1, s["wall_hi_s"] or -1, s["launches_est"],
                s["precheck_ok"], s["reason"] or ""))
        RC.jdump(dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), rows=rows, ok=ok, note="DRY BUILD of the R54 cfgs (no plan sha needed); the real cfgs "
                      "are written at launch by `r54_pcfg.py cfg <arm>`"), od + "/dry_summary.json")
        print(json.dumps(C.clean(dict(dry=od + "/dry_summary.json", ok=ok)), ensure_ascii=False))
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
