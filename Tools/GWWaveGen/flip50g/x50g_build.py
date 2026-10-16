# -*- coding: utf-8 -*-
"""FLIP50 DG1 (AM-D20): T0G = build and check the SEPARATE groove hip Houdini/FLIP50/g50_tank_g.hiplc (py -3.10 -B). 2026-10-17 written new.
1. refuses to start unless (dg1_frozen.json implementation.order 1) the DF1A chain has ended and been analysed (auto_D_status.txt), DF1A is
   neither PASS nor a hard health item, DM1A's median onset is within 256.5 +- 10 m, and every 'untouched' file still has its frozen sha.
   --order-ok="<the user's answer, e.g. Q81 ...>" skips ONLY the order items (DF1A / DM1A conditions), for a case the user decided; it is
   written into build_check_g.json. The sha checks are never skipped.
2. writes Unity/Build/FLIP50/_logs/build_inputs_g.json = build_inputs.json (DM1 table, S2D Fenton table) after checking the table sha256
   (no table is rewritten: g50_table.write is not called).
3. waits until no other hython runs (one heavy computation at a time), runs hython g50g_build_tank.py -> _logs/build_g.log, then prints the
   main lines of _logs/build_check_g.json and checks again that g50_tank.hiplc, build_check.json and the other untouched files did not change.
A failed check is a code fault: fix the code and rebuild (not a round). Any fix that would change a number of dg1_frozen.json -> stop and ask.
usage: py -3.10 -B G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50g/x50g_build.py [--order-ok="..."] [--check-only]
  --check-only   print the start condition and the untouched check, build nothing
"""
import os, sys, subprocess, time, json

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g50g_common as GG    # noqa: E402

GC = GG.patch_modules()


def main(argv):
    opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    os.makedirs(GG.LOGS, exist_ok=True)

    def log(*a):
        msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            print(msg.encode("ascii", "replace").decode(), flush=True)
        if "check-only" not in opt:
            with open(GG.BUILD_LOG_G, "a", encoding="utf8") as fh:
                fh.write(msg + "\n")
    fz = GG.frozen()
    u0 = GG.check_untouched(fz)
    st = GG.order_state()
    log("DG1 T0G: untouched", u0, "| order ok", st["ok"], st["why"])
    if not u0["ok"]:
        log("STOP: files the DM1A / DF1A runs depend on changed:", u0["bad"]); return 2
    if not st["ok"] and not opt.get("order-ok"):
        log("STOP: the start condition of dg1_frozen.json implementation.order 1 does not hold (Houdini steps wait):", st["why"]); return 3
    if "check-only" in opt:
        return 0
    bi = json.load(open(GG.LOGS + "/build_inputs.json", encoding="utf8"))
    for case, t in bi["tables"].items():
        if GG.sha256_file(t["npz"]) != t["sha256"]:
            log("STOP: table", case, t["npz"], "sha256 differs from build_inputs.json"); return 4
    bi_g = dict(bi, made_g=time.strftime("%Y-%m-%d %H:%M:%S"), source="copy of Unity/Build/FLIP50/_logs/build_inputs.json (tables checked, none rewritten)",
                dg1=GG.frozen_ref(), order_ok=opt.get("order-ok"), order_state=st)
    json.dump(bi_g, open(GG.BUILD_INPUTS_G, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    log("build start (groove hip %s); waiting for other hython" % GG.HIP_G)
    w = GC.wait_no_hython(log=log)
    log("waited %.0f s; launching hython" % w)
    tmp = GG.B50 + "/tmp_houdini"
    env = dict(os.environ, HOUDINI_TEMP_DIR=tmp, PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(tmp, exist_ok=True)
    t0 = time.time()
    with open(GG.BUILD_LOG_G, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, HERE + "/g50g_build_tank.py"], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    log("hython exit", r.returncode, "%.0f s" % (time.time() - t0))
    u1 = GG.check_untouched(fz)
    log("untouched after the build", u1)
    if os.path.exists(GG.BUILD_CHECK_G):
        c = json.load(open(GG.BUILD_CHECK_G, encoding="utf8"))
        c["untouched_after_build"] = u1
        c["order_ok_override"] = opt.get("order-ok")
        if not u1["ok"]:
            c["all_ok"] = False
        json.dump(c, open(GG.BUILD_CHECK_G, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
        log("build_check_g all_ok", c.get("all_ok"), "hip_sha256", str(c.get("hip_sha256"))[:16], "DG1 items", c.get("DG1_items"))
        for nm in ("D19B_strip", "D19B_3d", "D19B_3d_particles_dp1", "D19B_numpy", "DG1_strip", "DG1_3d", "DG1_3d_groove_box", "DG1_3d_particles_dp1",
                   "DG1_switch"):
            log("  ", nm, {k: (c.get(nm) or {}).get(k) for k in ("bed_max_abs_dz_m", "bed_vex_numpy_lt_1mm", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac",
                                                              "sdf_ok", "particles", "particles_model", "n_below_bed", "x_max_m", "equals_analytic_bit",
                                                              "houdini_groove_dz_max_m", "numpy_groove_dz_max_m", "ok")})
        log("   DG1_numpy ok", (c.get("DG1_numpy") or {}).get("ok"), "failed", (c.get("DG1_numpy") or {}).get("failed"))
        for nm in ("sf_probe_h19", "dir_probe", "relax_probe_D", "relax_probe_S"):
            log("  ", nm, {k: v for k, v in (c.get(nm) or {}).items() if not isinstance(v, (dict, list))})
        log("   restored", c.get("restored_ctrl_equal_default"), "still/bands off", c.get("saved_scene_still_water_bands_off"), "dop_errors", c.get("dop_errors"))
        if c.get("error"):
            log("build_check_g error", c.get("error"), c.get("traceback", "")[-800:])
    log("groove hip exists", os.path.exists(GG.HIP_G), GG.HIP_G)
    return 0 if r.returncode == 0 else 5


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
