# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: launcher of the scene build Houdini/FLIP52/g52_tank.hiplc (py -3.10). 2026-10-17 written new (adapted from x50_build.py).
1. writes (py -3.10, numpy) the inputs the hython build checks need: the N-layer tables of DFG2 (and of the frozen branches B2, B1)
   (g52_table.write) -> Unity/Build/FLIP52/_logs/build_inputs52.json, and refuses to go on if the G1 numpy table check of DFG2 fails
   (g52_table.checks -> Unity/Build/FLIP52/plan/table_check_DFG2.json).
2. waits until no other hython runs (one heavy computation at a time: round E2 first), then runs hython g52_build_tank.py -> _logs/build52.log
3. prints the main lines of _logs/build_check52.json. If all_ok is false, g52_chain.py will not start any run.
Options: --no-wait   do not wait for other hython (only when the caller has already checked; auto_DFG.py waits itself)
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52/x52_build.py
"""
import os, sys, subprocess, time, json

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g52_common as GC    # noqa: E402
import g52_table as TB     # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.makedirs(GC.LOG_DIR, exist_ok=True)
    lp = GC.LOG_DIR + "/build52.log"

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
    tabs = {}
    for s in GC.SETS:
        p, sha, ch, info = TB.write(s)
        tabs[s] = dict(npz=p, sha256=sha, content_sha256=ch, n_layers=info["n_layers"], a_sum=info["a_sum"])
        log("table", s, p, "sha", sha[:16], "content", ch[:16])
    for s in GC.SETS:                         # G1 for the run (DFG2) and for the two frozen follow-up branches (their cfg prechecks need it)
        o = TB.checks(s)
        GC.jdump(o, GC.PLAN_DIR + "/table_check_%s.json" % s)
        log("G1 numpy table check", s, o["ok"], "all_ok", o["all_ok"], "%.1f s" % o["cpu_s"])
        if s == "DFG2" and (not o["all_ok"] or o["content_sha256"] != tabs["DFG2"]["content_sha256"]):
            log("STOP the DFG2 table fails its numpy check (or differs from the written file); no build"); return 3
    inputs = dict(dir_npz=tabs["DFG2"]["npz"], dir_sha256=tabs["DFG2"]["sha256"], tables=tabs, plan=GC.PLAN_REL, plan_sha256=GC.sha256_file(GC.PLAN),
                  made=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(inputs, open(GC.BUILD_INPUTS, "w", encoding="utf8"), indent=1)
    if "--no-wait" not in sys.argv:
        log("build start; waiting for other hython")
        w = GC.wait_no_hython(log=log)
        log("waited %.0f s; launching hython" % w)
    elif GC.hython_running():
        log("STOP --no-wait given but another hython runs; no build"); return 4
    env = dict(os.environ, HOUDINI_TEMP_DIR=GC.B52 + "/tmp_houdini", PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(GC.B52 + "/tmp_houdini", exist_ok=True)
    t0 = time.time()
    with open(lp, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, GC.TOOLS52 + "/g52_build_tank.py"], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    log("hython exit", r.returncode, "%.0f s" % (time.time() - t0))
    ck = GC.BUILD_CHECK
    ok = False
    if os.path.exists(ck) and os.path.getmtime(ck) >= t0 - 1:
        c = json.load(open(ck, encoding="utf8"))
        ok = bool(c.get("all_ok"))
        log("build_check52 all_ok", c.get("all_ok"))
        for nm in ("flat_strip", "flat_3d", "flat_3d_particles_dp1", "flat_numpy"):
            log("  ", nm, {k: (c.get(nm) or {}).get(k) for k in ("bed_max_abs_dz_m", "bed_flat_20m", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac",
                                                              "sdf_ok", "particles", "particles_model", "n_below_bed", "equals_minus_h0_bit", "g48_plain_path")})
        for nm in ("dir_probe", "relax_probe_DFG"):
            log("  ", nm, {k: v for k, v in (c.get(nm) or {}).items() if not isinstance(v, (dict, list))})
            for r_ in ("ret0", "ret1"):
                if (c.get(nm) or {}).get(r_):
                    log("     ", r_, c[nm][r_])
        log("   restored", c.get("restored_ctrl_equal_default"), "still/bands off", c.get("saved_scene_still_water_bands_off"), "dop_errors", c.get("dop_errors"))
        if c.get("error"):
            log("build_check52 error", c.get("error"), c.get("traceback", "")[-800:])
    else:
        log("no fresh build_check52.json (see %s)" % lp)
    log("hip exists", os.path.exists(GC.HIP), GC.HIP)
    print(json.dumps(dict(build_ok=ok, hip=GC.HIP, hip_exists=os.path.exists(GC.HIP), build_check=ck)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
