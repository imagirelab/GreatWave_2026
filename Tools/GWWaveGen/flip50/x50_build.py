# -*- coding: utf-8 -*-
"""FLIP50 (option D): launcher of the scene build Houdini/FLIP50/g50_tank.hiplc (py -3.10). 2026-10-15 written new (adapted from x49_build.py).
1. writes (py -3.10, numpy/scipy) the inputs the hython build checks need: the DM1 and DF1 directional tables (g50_table.write) and the S2D
   Fenton tables at h0 19 m (g49_common.sf_solve; hython has no scipy) -> Build/FLIP50/_logs/build_inputs.json
2. waits until no other hython runs (one heavy computation at a time; DA1 first), then runs hython g50_build_tank.py -> _logs/build.log
3. prints the main lines of _logs/build_check.json. If all_ok is false, g50_chain.py will not start any run.
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50/x50_build.py
"""
import os, sys, subprocess, time, json

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g50_common as GC    # noqa: E402
import g50_table as TB     # noqa: E402


def s2d_H(T):
    """S2D strip wave height: 0.83 of the 2D highest wave at h0 19 m (the design: the focused crest stays at 0.83-0.85 Hmax2D on the flat)."""
    _, tb1 = GC.sf_solve(GC.H0, T, 1.0, GC.SF_N)
    return round(0.83 * float(tb1["Hmax_fit"]), 3), float(tb1["Hmax_fit"])


def sf_table_h19(T):
    H, Hmax = s2d_H(T)
    p = GC.sf_table_file(T, H)
    if not os.path.exists(p):
        _, tb = GC.sf_solve(GC.H0, T, H, GC.SF_N)
        tb["Hmax2D_fit_m"] = Hmax
        tb["rule"] = "H = 0.83 Hmax2D at h0 19 m [chosen in the plan, S2D]"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(tb, open(p, "w", encoding="utf8"), indent=1)
    return p, H


def main():
    logd = GC.B50 + "/_logs"
    os.makedirs(logd, exist_ok=True)
    lp = logd + "/build.log"

    def log(*a):
        msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            print(msg.encode("ascii", "replace").decode(), flush=True)
        with open(lp, "a", encoding="utf8") as fh:
            fh.write(msg + "\n")
    tabs = {}
    for case in ("DM1", "DF1"):
        p, sha, ch, info = TB.write(case)
        tabs[case] = dict(npz=p, sha256=sha, content_sha256=ch)
        log("table", case, p, "sha", sha[:16])
    sft = {}
    for T in (12.0, 10.0):
        p, H = sf_table_h19(T)
        sft["T%g" % T] = dict(path=p, H=H)
        log("S2D Fenton table h0 19 m T %g H %.3f" % (T, H), p)
    inputs = dict(dir_npz=tabs["DM1"]["npz"], dir_sha256=tabs["DM1"]["sha256"], tables=tabs, sf_table=sft["T12"]["path"], sf_tables=sft,
                  made=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(inputs, open(logd + "/build_inputs.json", "w", encoding="utf8"), indent=1)
    log("build start; waiting for other hython")
    w = GC.wait_no_hython(log=log)
    log("waited %.0f s; launching hython" % w)
    env = dict(os.environ, HOUDINI_TEMP_DIR=GC.B50 + "/tmp_houdini", PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(GC.B50 + "/tmp_houdini", exist_ok=True)
    t0 = time.time()
    with open(lp, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, GC.TOOLS + "/g50_build_tank.py"], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    log("hython exit", r.returncode, "%.0f s" % (time.time() - t0))
    ck = logd + "/build_check.json"
    if os.path.exists(ck):
        c = json.load(open(ck, encoding="utf8"))
        log("build_check all_ok", c.get("all_ok"))
        for nm in ("D19B_strip", "D19B_3d", "D19B_3d_particles_dp1", "D19B_numpy"):
            log("  ", nm, {k: (c.get(nm) or {}).get(k) for k in ("bed_max_abs_dz_m", "bed_vex_numpy_lt_1mm", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac",
                                                              "sdf_ok", "particles", "particles_model", "n_below_bed", "equals_analytic_bit", "g48_plain_path")})
        for nm in ("sf_probe_h19", "dir_probe", "relax_probe_D", "relax_probe_S"):
            log("  ", nm, {k: v for k, v in (c.get(nm) or {}).items() if not isinstance(v, (dict, list))})
        log("   restored", c.get("restored_ctrl_equal_default"), "still/bands off", c.get("saved_scene_still_water_bands_off"), "dop_errors", c.get("dop_errors"))
        if c.get("error"):
            log("build_check error", c.get("error"), c.get("traceback", "")[-800:])
    log("hip exists", os.path.exists(GC.HIP), GC.HIP)


if __name__ == "__main__":
    main()
