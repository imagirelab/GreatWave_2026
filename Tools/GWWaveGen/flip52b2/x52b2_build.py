# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3: launcher of the scene build Houdini/FLIP52B2/g52b2_tank.hiplc (py -3.10). 2026-10-18 written new (Claude) by adapting
flip52b/x52b_build.py (DFG-2B, frozen, not edited). It never touches Houdini/FLIP52B, Houdini/FLIP52S2 or their Build folders.
1. checks the frozen plan's .sha256, that the generated copies (g52b2_run.py, g52b2_chain.py, g52b2_build_tank.py, g52b2_video.py) still equal
   g52b2_mkcopy.py's output (no hand edit) and the numpy bed self-check (g52b2_common.bed_selfcheck); writes (numpy) the DFGB3 generator table
   (g52b2_table.write) -> Unity/Build/FLIP52B2/_logs/build_inputs52b2.json, and refuses to go on if the G1 numpy table check fails
   (g52b2_table.checks -> Unity/Build/FLIP52B2/plan/table_check_DFGB3.json) or the table differs from the plan's frozen content sha.
2. waits until no other hython runs (one heavy computation at a time), then runs hython g52b2_build_tank.py -> _logs/build52b2.log
3. prints the main lines of _logs/build_check52b2.json. If all_ok is false, g52b2_chain.py will not start any run.
Options: --no-wait   do not wait for other hython (only when the caller has already checked; auto_DFGB3.py waits itself)
usage: py -3.10 -B G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b2/x52b2_build.py
"""
import os, sys, subprocess, time, json

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g52b2_common as GC    # noqa: E402
import g52b2_table as TB     # noqa: E402
import g52b2_mkcopy as MK    # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.makedirs(GC.LOG_DIR, exist_ok=True)
    lp = GC.LOG_DIR + "/build52b2.log"

    def log(*a):
        msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            print(msg.encode("ascii", "replace").decode(), flush=True)
        with open(lp, "a", encoding="utf8") as fh:
            fh.write(msg + "\n")
    if not GC.plan_sha_ok():
        log("STOP the frozen plan %s does not match its .sha256" % GC.PLAN); return 2
    try:
        gen = MK.build_all()
    except SystemExit as e:
        log("STOP g52b2_mkcopy cannot regenerate the copies (a source changed?): %s" % e); return 5
    bad = [nm for nm, s in gen.items() if not (os.path.exists(os.path.join(GC.TOOLS52B2, nm)) and open(os.path.join(GC.TOOLS52B2, nm), encoding="utf8").read() == s)]
    if bad:
        log("STOP the generated copies differ from g52b2_mkcopy.py output: %s (run py -3.10 -B g52b2_mkcopy.py, then re-freeze)" % bad); return 5
    bs = GC.bed_selfcheck()
    log("bed self-check (numpy) ok", bs["ok"], "foot x %.2f, edge x %.2f, depth %s" % (bs["x_foot_m"], GC.X_EDGE, bs["depth_min_max_m"]))
    if not bs["ok"]:
        log("STOP the numpy bed self-check failed: %s" % json.dumps(GC.clean(bs))[:800]); return 3
    p, sha, ch, info = TB.write()
    log("sea", GC.SET, "(DFG-2B-E's energy-matched sea x exp(-i phi_n), phi %s)" % GC.PHI_COMP, "a_sum %.6f m" % GC.A_SUM)
    log("table", p, "sha", sha[:16], "content", ch[:16])
    o = TB.checks()
    GC.jdump(o, GC.TABLE_CHECK)
    log("G1 numpy table check all_ok", o["all_ok"], o["ok"], "%.1f s" % o["cpu_s"])
    if not o["all_ok"] or o["content_sha256"] != ch:
        log("STOP the DFGB3 table fails its numpy check (or differs from the written file); no build"); return 3
    pc = (GC.plan().get("table_npz") or {}).get("content_sha256")
    if pc != ch:
        log("STOP the table content %s differs from the frozen plan's %s; no build" % (ch[:16], str(pc)[:16])); return 3
    inputs = dict(dir_npz=p, dir_sha256=sha, content_sha256=ch, n_layers=info["n_layers"], a_sum=info["a_sum"], x_f=info["x_f"], t_f=info["t_f"],
                  phase_comp_rad=info["phase_comp_rad"], plan=GC.PLAN_REL, plan_sha256=GC.sha256_file(GC.PLAN), made=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(inputs, open(GC.BUILD_INPUTS, "w", encoding="utf8"), indent=1)
    if "--no-wait" not in sys.argv:
        log("build start; waiting for other hython")
        w = GC.wait_no_hython(log=log)
        log("waited %.0f s; launching hython" % w)
    elif GC.hython_running():
        log("STOP --no-wait given but another hython runs; no build"); return 4
    env = dict(os.environ, HOUDINI_TEMP_DIR=GC.B52B2 + "/tmp_houdini", PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(GC.B52B2 + "/tmp_houdini", exist_ok=True)
    os.makedirs(os.path.dirname(GC.HIP), exist_ok=True)
    t0 = time.time()
    with open(lp, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, GC.TOOLS52B2 + "/g52b2_build_tank.py"], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    log("hython exit", r.returncode, "%.0f s" % (time.time() - t0))
    ck = GC.BUILD_CHECK
    ok = False
    if os.path.exists(ck) and os.path.getmtime(ck) >= t0 - 1:
        c = json.load(open(ck, encoding="utf8"))
        ok = bool(c.get("all_ok"))
        log("build_check52b2 all_ok", c.get("all_ok"), "W", (c.get("bed_3d") or {}).get("W"))
        for nm in ("bed_strip", "bed_3d", "bed_3d_particles_dp1"):
            log("  ", nm, {k: (c.get(nm) or {}).get(k) for k in ("bed_max_abs_dz_m", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac", "sdf_ok",
                                                              "bed_min_depth_m", "bed_max_depth_m", "depth_range_is_bed", "spec_is_bed",
                                                              "particles", "particles_model", "n_below_bed", "particles_ok")})
        log("   bed_numpy ok", (c.get("bed_numpy") or {}).get("ok"))
        for nm in ("dir_probe", "relax_probe_DFGB3"):
            log("  ", nm, {k: v for k, v in (c.get(nm) or {}).items() if not isinstance(v, (dict, list))})
            for r_ in ("ret0", "ret1"):
                if (c.get(nm) or {}).get(r_):
                    log("     ", r_, c[nm][r_])
        log("   restored", c.get("restored_ctrl_equal_default"), "default bed DFGB3", c.get("default_bed_is_DFGB3"), "sponge parms",
            c.get("default_sponge_parms"), "still/bands off", c.get("saved_scene_still_water_bands_off"), "dop_errors", c.get("dop_errors"))
        if c.get("error"):
            log("build_check52b2 error", c.get("error"), c.get("traceback", "")[-800:])
    else:
        log("no fresh build_check52b2.json (see %s)" % lp)
    log("hip exists", os.path.exists(GC.HIP), GC.HIP)
    print(json.dumps(dict(build_ok=ok, hip=GC.HIP, hip_exists=os.path.exists(GC.HIP), build_check=ck)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
