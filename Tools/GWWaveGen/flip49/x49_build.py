# -*- coding: utf-8 -*-
"""FLIP49：場面 Houdini/FLIP49/g49_tank.hiplc を作る起動役（py -3.10）。2026-10-15 新しく書いた（x48_build.py の写し）。
ほかの hython（ほかの役の計算を含む）が終わるまで待ってから、hython g49_build_tank.py を起動し、出力を Build/FLIP49/_logs/build.log に書く。
作った後の確かめ（_logs/build_check.json）の主な行を書く。all_ok が偽なら、計算（g49_chain.py）は始めない。
2026-10-15 方案 A（SC37）の海底・粒子・帯の確かめ（A_3d・A_3d_particles_dp1・relax_probe_A）の行も書く。
使い方：py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49/x49_build.py
"""
import os, sys, subprocess, time, json

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g49_common as GC   # noqa: E402


def main():
    logd = GC.B49 + "/_logs"
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
    _, tb = GC.sf_solve()                     # hython には scipy が無いので、流れ関数の表はここ（py -3.10）で解いて渡す
    json.dump(tb, open(GC.sf_table_file(), "w", encoding="utf8"), indent=1)
    log("sf table", GC.sf_table_file(), "L %.3f c %.4f crest %.4f" % (tb["L"], tb["c"], tb["eta_crest"]))
    log("build start; waiting for other hython")
    w = GC.wait_no_hython(log=log)
    log("waited %.0f s; launching hython" % w)
    env = dict(os.environ, HOUDINI_TEMP_DIR=GC.B49 + "/tmp_houdini", PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(GC.B49 + "/tmp_houdini", exist_ok=True)
    t0 = time.time()
    with open(lp, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, GC.TOOLS + "/g49_build_tank.py"], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    log("hython exit", r.returncode, "%.0f s" % (time.time() - t0))
    ck = GC.B49 + "/_logs/build_check.json"
    if os.path.exists(ck):
        c = json.load(open(ck, encoding="utf8"))
        log("build_check all_ok", c.get("all_ok"))
        for nm in ("axis_strip_PG12s", "flat_strip", "PG12s_3d", "PG12s_3d_particles_dp1", "R4_g48_path", "A_3d", "A_3d_particles_dp1"):
            log("  ", nm, {k: (c.get(nm) or {}).get(k) for k in ("bed_max_abs_dz_m", "bed_vex_numpy_lt_1mm", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac",
                                                              "sdf_ok", "particles", "particles_model", "n_below_bed", "numpy_equals_g48_bit")})
        for nm in ("sf_probe", "relax_probe", "relax_probe_A"):
            log("  ", nm, {k: v for k, v in (c.get(nm) or {}).items() if not isinstance(v, (dict, list))})
        log("   restored", c.get("restored_ctrl_equal_default"), "still/bands off", c.get("saved_scene_still_water_bands_off"), "dop_errors", c.get("dop_errors"))
        if c.get("error"):
            log("build_check error", c.get("error"), c.get("traceback", "")[-800:])
    log("hip exists", os.path.exists(GC.HIP), GC.HIP)


if __name__ == "__main__":
    main()
