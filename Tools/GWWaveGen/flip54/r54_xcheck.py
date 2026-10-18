# -*- coding: utf-8 -*-
"""FLIP54 R54: the SCENE CHECK at dp 0.25 m (run with hython; auto_R54.py runs it once before the first R54 strip).
2026-10-18 written new (Claude, FLIP54 builder R). It runs the UNCHANGED K54 scene check x54_check.py (never builds or saves a scene; loads
Houdini/FLIP49/g49_tank.hiplc read only) with three values of g54_common changed in memory of this hython only:
  DP           0.5 -> 0.25 m   (x54_check.set_box -> box48 at dp 0.25: grid 0.5 m, offsets 0.25 m; the bed / SDF / initial-particle checks
                               then run on the R54 box: Houdini's particle count within 0.2 % of g54_common.count_particles at dp 0.25)
  BUILD_CHECK  -> Unity/Build/FLIP54/r54/_check/build_check_r54.json  (K54's Unity/Build/FLIP54/_logs/build_check54.json is not touched)
  LOG_DIR      -> Unity/Build/FLIP54/r54/_check                       (the relax probe's divergence test file goes to r54/_check/vdtest54)
The bed tags inside the record still read "dp 0.5 m" (x54_check's text); the field "dp" of every bed and the "r54" block below give the
real particle size. After x54_check finishes, this wrapper adds the "r54" block and sets all_ok to x54_check's all_ok AND every checked
bed at dp 0.25 (r54_chain.py's gate reads all_ok and hip_sha256).
usage: hython r54_xcheck.py [<sf table T9.33 json> [<sf table T12 json>]]   (auto_R54.py passes the R54 wave's table, T 9.33 s H 7.0 m)
"""
import sys, os, json, runpy, time

sys.dont_write_bytecode = True
HERE = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip54"
sys.path.insert(0, HERE)
import r54_common as RC       # noqa: E402
import g54_common as C        # noqa: E402

C.DP = RC.DP
C.BUILD_CHECK = RC.BUILD_CHECK
C.LOG_DIR = RC.CHECK_DIR
os.makedirs(RC.CHECK_DIR, exist_ok=True)
X54 = HERE + "/x54_check.py"
t0 = time.time()
sys.argv = [X54] + sys.argv[1:]
try:
    runpy.run_path(X54, run_name="__main__")
finally:
    chk = RC.jload(RC.BUILD_CHECK) or {}
    beds = chk.get("beds") or {}
    dp_ok = bool(beds and all(abs(float(v.get("dp", -1)) - RC.DP) < 1e-12 for v in beds.values()))
    chk["r54"] = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), dp=RC.DP, grid_m=RC.DP * RC.GRIDSCALE, wrapper="Tools/GWWaveGen/flip54/r54_xcheck.py",
                      wrapper_sha256=C.sha256_file(os.path.abspath(__file__)), x54_check_sha256=C.sha256_file(X54),
                      patched_in_memory=dict(DP=RC.DP, BUILD_CHECK=RC.BUILD_CHECK, LOG_DIR=RC.CHECK_DIR), beds_at_dp0p25=dp_ok,
                      all_ok_x54=chk.get("all_ok"), tables=sys.argv[1:], wall_s=round(time.time() - t0, 1),
                      note="x54_check.py unchanged; its bed tags say 'dp 0.5 m' (text) - the bed field dp is the real particle size")
    chk["all_ok"] = bool(chk.get("all_ok") and dp_ok)
    if chk:
        json.dump(chk, open(RC.BUILD_CHECK, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    print("BUILD_CHECK_R54", json.dumps(dict(all_ok=chk.get("all_ok"), beds_at_dp0p25=dp_ok, hip_unchanged=chk.get("hip_unchanged"),
                                             error=chk.get("error")), ensure_ascii=False))
    sys.stdout.flush()
