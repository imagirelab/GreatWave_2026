# -*- coding: utf-8 -*-
"""FLIP52S plan DFG-S: launcher of the scene build Houdini/FLIP52S/g52s_tank.hiplc (py -3.10). 2026-10-18 written new (adapted from
flip52b/x52b_build.py, not edited).
1. checks the frozen plan against its .sha256, that the generated copies (g52s_run.py, g52s_chain.py, g52s_build_tank.py) still equal
   g52s_mkcopy.py's output (no hand edit) and the numpy bed self-check (g52s_common.bed_selfcheck); writes (numpy) the N-layer step table
   (g52s_table.write) -> Unity/Build/FLIP52S/_logs/build_inputs52s.json, and refuses to go on if the G1 numpy table check fails
   (g52s_table.checks -> Unity/Build/FLIP52S/plan/table_check_DFGS.json).
2. waits until no other hython runs (one heavy computation at a time), then runs hython g52s_build_tank.py -> _logs/build52s.log
3. prints the main lines of _logs/build_check52s.json. If all_ok is false, g52s_chain.py will not start any run.
Options: --no-wait   do not wait for other hython (only when the caller has already checked)
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52s/x52s_build.py
"""
import os, sys, subprocess, time, json

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g52s_common as GC    # noqa: E402
import g52s_table as TB     # noqa: E402
import g52s_mkcopy as MK    # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.makedirs(GC.LOG_DIR, exist_ok=True)
    lp = GC.LOG_DIR + "/build52s.log"

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
        log("STOP g52s_mkcopy cannot regenerate the copies (a flip52 source changed?): %s" % e); return 5
    bad = [nm for nm, s in gen.items() if not (os.path.exists(os.path.join(GC.TOOLS52S, nm)) and open(os.path.join(GC.TOOLS52S, nm), encoding="utf8").read() == s)]
    if bad:
        log("STOP the generated copies differ from g52s_mkcopy.py output: %s (run py -3.10 -B g52s_mkcopy.py, then re-freeze)" % bad); return 5
    bs = GC.bed_selfcheck()
    log("numpy bed self-check ok", bs["ok"], {k: bs[k] for k in ("equals_analytic_bit", "grad_ok", "sdf_ok", "dirfield_bed_h_ok", "plain_path")})
    if not bs["ok"]:
        log("STOP the numpy step bed self-check fails; no build"); return 3
    p, sha, ch, info = TB.write()
    log("table", p, "sha", sha[:16], "content", ch[:16])
    o = TB.checks()
    GC.jdump(o, GC.PLAN_DIR + "/table_check_DFGS.json")
    log("G1 numpy table check all_ok", o["all_ok"], o["ok"], "%.1f s" % o["cpu_s"])
    if not o["all_ok"] or o["content_sha256"] != ch:
        log("STOP the DFG-S table fails its numpy check (or differs from the written file); no build"); return 3
    inputs = dict(dir_npz=p, dir_sha256=sha, content_sha256=ch, n_layers=info["n_layers"], a_sum=info["a_sum"], x_f=info["x_f"], t_f=info["t_f"],
                  plan=GC.PLAN_REL, plan_sha256=GC.sha256_file(GC.PLAN), made=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(inputs, open(GC.BUILD_INPUTS, "w", encoding="utf8"), indent=1)
    if "--no-wait" not in sys.argv:
        log("build start; waiting for other hython")
        w = GC.wait_no_hython(log=log)
        log("waited %.0f s; launching hython" % w)
    elif GC.hython_running():
        log("STOP --no-wait given but another hython runs; no build"); return 4
    env = dict(os.environ, HOUDINI_TEMP_DIR=GC.B52S + "/tmp_houdini", PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(GC.B52S + "/tmp_houdini", exist_ok=True)
    os.makedirs(os.path.dirname(GC.HIP), exist_ok=True)
    t0 = time.time()
    with open(lp, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, GC.TOOLS52S + "/g52s_build_tank.py"], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    log("hython exit", r.returncode, "%.0f s" % (time.time() - t0))
    ck = GC.BUILD_CHECK
    ok = False
    if os.path.exists(ck) and os.path.getmtime(ck) >= t0 - 1:
        c = json.load(open(ck, encoding="utf8"))
        ok = bool(c.get("all_ok"))
        log("build_check52s all_ok", c.get("all_ok"))
        for nm in ("step_strip", "step_3d", "step_3d_particles_dp1"):
            log("  ", nm, {k: (c.get(nm) or {}).get(k) for k in ("bed_max_abs_dz_m", "bed_min_depth_m", "bed_max_depth_m", "depth_range_is_step",
                                                              "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac", "sdf_ok", "particles",
                                                              "particles_model", "n_below_bed", "particles_ok")})
        log("   step_numpy ok", (c.get("step_numpy") or {}).get("ok"), "default_bed_is_step", c.get("default_bed_is_step"))
        for nm in ("dir_probe", "relax_probe_DFGS"):
            log("  ", nm, {k: v for k, v in (c.get(nm) or {}).items() if not isinstance(v, (dict, list))})
            for r_ in ("ret0", "ret1"):
                if (c.get(nm) or {}).get(r_):
                    log("     ", r_, c[nm][r_])
        log("   restored", c.get("restored_ctrl_equal_default"), "still/bands off", c.get("saved_scene_still_water_bands_off"), "dop_errors", c.get("dop_errors"))
        if c.get("error"):
            log("build_check52s error", c.get("error"), c.get("traceback", "")[-800:])
    else:
        log("no fresh build_check52s.json (see %s)" % lp)
    log("hip exists", os.path.exists(GC.HIP), GC.HIP)
    print(json.dumps(dict(build_ok=ok, hip=GC.HIP, hip_exists=os.path.exists(GC.HIP), build_check=ck)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
