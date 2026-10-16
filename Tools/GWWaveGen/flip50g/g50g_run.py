# -*- coding: utf-8 -*-
"""FLIP50 DG1 (AM-D20): one launch of a DG1 calculation (hython; started by g50g_chain.py). 2026-10-17 written new (Claude).
It patches the bed in memory (g50g_common.patch_modules(hip=True): g50_common.HIP = Houdini/FLIP50/g50_tank_g.hiplc, bed_spec / bed_z with
the groove) and then runs the UNCHANGED flip50/g50_run.py (sha256_16 checked against dg1_frozen.json untouched) as __main__. So the run loop,
the records, the stage-A volume hold and the checkpoints are DM1A's; the bed consumers inside g50_run (leak check against the GROOVE bed,
stage-A column volume, still offset) see the groove; the run record's 'hip' / 'hip_sha256' name the groove hip and 'bed_spec_ctrl' carries
the CTRL gr_* values; 'module_shas' adds the flip50g files.
Smoke only (cfg kind 'smoke', first launch): before the run, the frame-1 seeding (OUT_PARTICLES of the groove hip with the cfg parms; the FLIP
object imports exactly this at frame 1) is compared with the numpy groove bed -> <run>/groove_seed_check.json (smoke gate b numbers).
usage: hython g50g_run.py <cfg.json>  (normally py -3.10 g50g_chain.py <cfg.json>)
"""
import hou, sys, os, json, time, runpy
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g50g_common as GG      # noqa: E402

GC = GG.patch_modules(hip=True)
RUN = GG.TOOLS50 + "/g50_run.py"


def seed_check(args):
    """frame-1 particles of the groove hip (OUT_PARTICLES, cfg parms) against the numpy groove bed (smoke gate b) and the particle model."""
    t0 = time.time()
    out_dir = os.path.join(GC.B50, args.get("out_root", "runs"), args["run_id"])
    os.makedirs(out_dir, exist_ok=True)
    rec = dict(run_id=args["run_id"], date=time.strftime("%Y-%m-%d %H:%M:%S"), hip=GG.HIP_G, hip_sha256=GC.sha256_file(GG.HIP_G), tool="flip50g/g50g_run.py seed_check")
    try:
        hou.hipFile.load(GG.HIP_G, suppress_save_prompt=True, ignore_load_warnings=True)
        ctrl = hou.node("/obj/G50_SETUP/CTRL")
        for k, v in (args.get("parms") or {}).items():
            if ctrl.parm(k) is not None:
                ctrl.parm(k).set(v)
        P = {p.name(): p.eval() for p in ctrl.parms()}
        o = np.array([float(P["ox"]), float(P["oy"]), float(P["oz"])])
        g = hou.node("/obj/G50_SETUP/OUT_PARTICLES").geometry()
        Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
        spec = GC.bed_spec(parms=P)
        dp = float(P["dp"]); vox = dp * float(P["gridscale"])
        n_model = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), dp, zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))[0]
        D19 = {k: v for k, v in spec.items() if not k.startswith("gr_")}
        n_d19 = GC.count_particles(D19, float(P["Lx"]), float(P["W"]), dp, zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))[0]
        gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **spec)
        rec.update(spec_gr={k: v for k, v in spec.items() if k.startswith("gr_")}, dp=dp, vox=vox, particles=int(len(Pp)), particles_model_groove=int(n_model),
                   particles_model_D19B=int(n_d19), ratio_houdini_over_model=float(len(Pp)) / max(n_model, 1),
                   n_below_groove_bed_quarter_vox=int((gap < -0.25 * vox).sum()), gap_min_m=float(gap.min()), x_max_m=float(Pp[:, 0].max()),
                   core=GG.seed_core_stats(Pp, dp, spec, zb=float(P["zb"]), bed_gap=float(P["bed_gap"])))
        rec["a_count_ok"] = bool(abs(rec["ratio_houdini_over_model"] - 1.0) < 0.002)
        rec["c_none_below_ok"] = bool(rec["n_below_groove_bed_quarter_vox"] == 0)
        rec["b_core_ok"] = bool(rec["core"].get("ok"))
        hou.hipFile.clear(suppress_save_prompt=True)
    except Exception as e:
        import traceback
        rec["error"] = repr(e)[:400]; rec["traceback"] = traceback.format_exc()[-2000:]
    rec["wall_s"] = round(time.time() - t0, 1)
    json.dump(rec, open(os.path.join(out_dir, "groove_seed_check.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    print("DG1 seed check", json.dumps({k: rec.get(k) for k in ("particles", "particles_model_groove", "a_count_ok", "b_core_ok", "c_none_below_ok",
                                                                "wall_s", "error")}, default=str))
    sys.stdout.flush()


if __name__ == "__main__":
    args = json.load(open(sys.argv[1], encoding="utf8"))
    bad = GG.cfg_groove_ok(args)
    if bad:
        raise SystemExit("DG1 run refused (cfg is not the frozen DG1 cfg): %s" % bad)
    if args.get("kind") == "smoke" and int(args.get("f_start", 1)) == int(args.get("f_first", 1)):
        seed_check(args)
    GG.read_source(RUN, "flip50/g50_run.py")         # sha256_16 check only (the file itself is run unchanged)
    runpy.run_path(RUN, run_name="__main__")
