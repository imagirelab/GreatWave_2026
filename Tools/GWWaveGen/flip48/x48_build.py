# -*- coding: utf-8 -*-
"""FLIP48：場面 Houdini/FLIP48/g48_tank.hiplc を作る起動役（py -3.10）。2026-10-15 新しく書いた。
ほかの hython（FLIP46 の計算を含む）が終わるまで待ってから、hython g48_build_tank.py を起動し、出力を Build/FLIP48/_logs/build.log に書く。
hython の中から wait_no_hython を呼ばない（自分を見て待ち続けるため）。
起動の前に、既定の孤立波の npz（g48_cfg.py ready が書く）があるかを確かめる（なければ始めない）。
2026-10-15 R3：確かめ（build_check.json）に R3 の spur_channel・G0c の段の板を足したので、その行も記録に書く。
使い方：py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48/x48_build.py
"""
import os, sys, subprocess, time, json

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g48_common as GC   # noqa: E402


def main():
    logd = GC.B48 + "/_logs"
    os.makedirs(logd, exist_ok=True)
    lp = logd + "/build.log"
    if not os.path.exists(GC.SOL_DEFAULT):
        raise SystemExit("既定の孤立波の npz がない：%s（先に py -3.10 g48_cfg.py ready）" % GC.SOL_DEFAULT)

    def log(*a):
        msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
        print(msg, flush=True)
        with open(lp, "a", encoding="utf8") as fh:
            fh.write(msg + "\n")
    log("build start; waiting for other hython")
    w = GC.wait_no_hython(log=log)
    log("waited %.0f s; launching hython" % w)
    env = dict(os.environ, HOUDINI_TEMP_DIR=GC.B48 + "/tmp_houdini", PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(GC.B48 + "/tmp_houdini", exist_ok=True)
    t0 = time.time()
    with open(lp, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, GC.TOOLS + "/g48_build_tank.py"], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    log("hython exit", r.returncode, "%.0f s" % (time.time() - t0))
    ck = GC.B48 + "/_logs/build_check.json"
    if os.path.exists(ck):
        c = json.load(open(ck, encoding="utf8"))
        log("build_check all_ok", c.get("all_ok"), "R0", {k: (c.get("default_R0") or {}).get(k) for k in ("bed_max_abs_dz_m", "sdf_max_abs_diff_near_m", "particles", "n_below_bed")},
            "R1", {k: (c.get("R1") or {}).get(k) for k in ("bed_max_abs_dz_m", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac")})
        for nm in ("R3_spur_channel", "R3_spur_channel_particles_dp1", "G0c_ledge_strip"):
            log("build_check", nm, {k: (c.get(nm) or {}).get(k) for k in ("bed_max_abs_dz_m", "sdf_max_abs_diff_near_m", "sdf_sign_mismatch_frac",
                                                                  "sdf_covers_box_floor", "particles", "particles_model", "n_below_bed", "gap_min_m")})
        if c.get("error"):
            log("build_check error", c.get("error"))
    log("hip exists", os.path.exists(GC.HIP), GC.HIP)


if __name__ == "__main__":
    main()
