# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3: make g52b2_run.py, g52b2_chain.py, g52b2_build_tank.py as exact copies of flip52/g52_run.py, flip52/g52_chain.py,
flip52/g52_build_tank.py, and g52b2_video.py as an exact copy of flip52b/g52b_video.py, with counted string replacements only (py -3.10 -B).
2026-10-18 written new (Claude) by adapting flip52b/g52b_mkcopy.py (DFG-2B, frozen, not edited). The sources are READ ONLY: their sha256 must
equal the values below (flip52: the versions that built Houdini/FLIP52/g52_tank.hiplc and ran DFG-2 / DFG-2B-E / DFG-S-E140, the same values
flip52b / flip52s2 recorded; flip52b/g52b_video.py: the version that made DFG-2B-E's compare video), otherwise nothing is written. Every
replacement must match its expected count exactly, so the copies are the FLIP52 run loop, chain and builder and the DFG-2B video except for:
  g52b2_run.py        constants / paths of FLIP52B2 (g52b2_common: Build/FLIP52B2, Houdini/FLIP52B2/g52b2_tank.hiplc, the level regions);
                      the N-layer numpy mirror stays flip52/g52_table.py (generic); record stage "FLIP52B2".
  g52b2_chain.py      paths of FLIP52B2 (Build/FLIP52B2, flip52b2/g52b2_run.py, _logs/build_check52b2.json); messages name x52b2_build.py /
                      g52b2_pcfg.py.
  g52b2_build_tank.py the D19B tank of DFG-2B-E (box, bands, N-layer VEX of flip52/g52_tanklib.py unchanged, node names G52_*) with the DFGB3
                      TWO-SLOPE bed as the default bed (g52b2_common.SPEC_BED through the FLIP49 two-slope VEX path pgon / rise2 / bedy_pg:
                      no new VEX term) and the exit sponge defaults xa0 332 m, abs_sigma 1.0, abs_pow 2 (abs_on 0 in the saved scene; the cfg
                      switches it on); the bed / particle checks are on this bed (strip W 6 m and 3D W 140 m on the dp 0.5 grid: VEX heights and
                      SDF vs numpy, depth range exactly 6-19 m, particles vs the numpy seeding rule; plus the numpy-only g52b2_common.bed_selfcheck);
                      the band probe is the D layout (inlet 0-100 m, side band 95-140 m generating to 180.25 m / absorbing from 210.25 m) WITH the
                      exit sponge (abs_on 1), probes on the face and the shelf and inside the sponge; writes Houdini/FLIP52B2 and
                      Unity/Build/FLIP52B2/_logs/build_check52b2.json.
  g52b2_video.py      reads <run>/g52b2/judge_DFGB3.json and coequal_DFGB3.json (g52b2_ana), writes <run>/video/<run>_DFGB3_compare.mp4; the
                      header states the DFGB3 setup; the table panel adds the (3b) / (3c) co-equal lines.
usage: py -3.10 -B g52b2_mkcopy.py [--check]     (--check: build in memory and compare with the files on disk; writes nothing)
"""
import os, sys, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"
SRC_B = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b"
SHA = {"g52_run.py": "282b21e393e3ecfabb4c3774c29b60b40bccd16491519bb7e996abd51db6e17b",
       "g52_chain.py": "adc668759bf65cddf411c31e1fe8fa4861d2b8ee709a46f81e13894eb495d728",
       "g52_build_tank.py": "d4747657dcd50a8fc548af2f40fcc5d578202b94ef89b81da1cf70f51f05f2f7",
       "g52b_video.py": "4594f5b5d8c61d04dbfe891cf2ea18061b28eca5bd83b21202783599e66131e4"}

RUN_DOC = '''"""FLIP52B2 plan DFGB3: run one launch of a FLIP52B2 calculation and write its records (hython; started by g52b2_chain.py).
GENERATED 2026-10-18 by flip52b2/g52b2_mkcopy.py from flip52/g52_run.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52b2/g52b2_common.py (Build/FLIP52B2, Houdini/FLIP52B2/g52b2_tank.hiplc, the level regions);
    the N-layer numpy mirror is flip52/g52_table.py (generic); record stage "FLIP52B2"; message 'x52b2_build.py'.
Everything else is the FLIP52 run loop (= the FLIP50 one with the N-layer OUT_DIRTAB check) that ran DFG-2 / DFG-2B-E / DFG-S-E140.
usage: hython g52b2_run.py <cfg.json>  (normally py -3.10 g52b2_chain.py <cfg.json>)
output: Unity/Build/FLIP52B2/<out_root>/<run_id>/  (cfg out_root is an absolute FLIP52B2 folder)
"""'''

CHAIN_DOC = '''"""FLIP52B2 plan DFGB3: run one calculation to the end as chained launches of <= 29 min (py -3.10).
GENERATED 2026-10-18 by flip52b2/g52b2_mkcopy.py from flip52/g52_chain.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52b2/g52b2_common.py (Build/FLIP52B2, Houdini/FLIP52B2/g52b2_tank.hiplc) and flip52b2/g52b2_run.py; the start
    gate reads Unity/Build/FLIP52B2/_logs/build_check52b2.json; messages name x52b2_build.py and g52b2_pcfg.py.
Everything else is the FLIP52 / FLIP50 chain (flip46/g46_ckpt ledger; start gate: cfg precheck.ok, build check, frozen plan .sha256, table
sha256; resume from the last checkpoint; waits for every other hython before each launch; waiting time is not counted against max_hours,
which counts from this chain's own start: a new chain on a max_hours stop resumes from the last checkpoint with a fresh budget).
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b2/g52b2_chain.py <cfg.json>
"""'''

BUILD_DOC = '''"""FLIP52B2 plan DFGB3: build the tank scene Houdini/FLIP52B2/g52b2_tank.hiplc (hython, a few min; launched by x52b2_build.py, which waits
for every other hython first). GENERATED 2026-10-18 by flip52b2/g52b2_mkcopy.py from flip52/g52_build_tank.py (sha256 %s, not edited) by exact,
counted string replacements. The scene = the FLIP52 scene of DFG-2 / DFG-2B-E (same particle seeding, surface VDB, FLIP Solver 2.0, bed SDF,
read / surface paths, stage A/B/C nodes, node names G52_*, the N-layer VEX of flip52/g52_tanklib.py unchanged) with the DFGB3 TWO-SLOPE bed as
the default bed (1:10 from x 160.25 m to depth 11.5 m at x 235.25 m, then 1:3 to the 6 m shelf at x 251.75 m, shelf to the box end;
g52b2_common.SPEC_BED through the FLIP49 two-slope VEX path: ridge_on 1, ridge_x0 160.25, ridge_s 10, ridge_k 0, pg_hL 11.5, pg_s2 3, shelf_h 6;
no new VEX term) and the exit-sponge defaults xa0 332 m, abs_sigma 1.0, abs_pow 2. The box and bands are CTRL parms set by each run's cfg
(D19B box x 0-412 m, y 0-140 m, z -19 .. +17 m; inlet 0-100 m, side band 95-140 m generating to 180.25 m / absorbing from 210.25 m, exit sponge
332-412 m); every band default is OFF (still water).
Checks (Unity/Build/FLIP52B2/_logs/build_check52b2.json; all_ok false -> g52b2_chain.py never starts):
  1. bed: OUT_BED heights and the bed SDF (collision) against numpy on the strip (W 6 m) and the 3D box (W 140 m) on the dp 0.5 grid (< 1 cm and
     < 2 cm, no SDF sign mismatch), the depth range exactly 6-19 m, + the numpy-only g52b2_common.bed_selfcheck (analytic bed, VEX text).
  2. particles: Houdini seeding against count_particles: strip at dp 0.5, 3D at dp 1.0 (W 140 m); none below the bed.
  3. N-layer directional table: OUT_DIRTAB detail and dir_probe (VEX dirwave, g = 1) against the numpy mirror flip52/g52_table.dirwave_np
     (within 1e-5 of the scale) on the DFGB3 generator table (DFG-2B-E's x exp(-i phi_n)).
  4. bands: relax_probe (VEX relax_apply + vc_divergence) against g52_table.relax_np on the D layout with the two-slope bed and the exit sponge
     (dir_on 1, ret_on 1, abs_on 1, stage-C test file, in_gain 1.03 / sd_gain 0.97; probes on the flat, the face, the shelf and inside the
     sponge): vertical velocity unchanged, interior untouched, the side absorber and the exit sponge damp.
  5. the saved scene's CTRL equals the build defaults (still water, every band off) and its default bed is the DFGB3 bed.
usage: py -3.10 x52b2_build.py  (writes the table, waits for other hython, runs hython g52b2_build_tank.py)
"""'''

VIDEO_DOC = '''"""FLIP52B2 plan DFGB3: the compare video of one run (py -3.10 -B; numpy, PIL, ffmpeg). GENERATED 2026-10-18 by flip52b2/g52b2_mkcopy.py
from flip52b/g52b_video.py (sha256 %s, not edited) by exact, counted string replacements: reads <run>/g52b2/judge_DFGB3.json and
coequal_DFGB3.json (flip52b2/g52b2_ana.py) and pv53's json; writes only <run>/video (FLIP52B2) or --out (Unity/Build/FLIP52B2/_scratch, tests).
The panels are DFG-2B's (print pose hf proxy, front 3D, centre section with the print outline, crest line, table); the header states the DFGB3
setup and the table adds the co-equal (3b) convergence at the most print-like instant and (3c) Hc not lower. The Unity print view itself is
pv53's. RED thick frame + 3 s hold = the most PRINT-LIKE instant (pv53's, else the judge's most converged instant); ORANGE = the groups' 'max'.
usage: py -3.10 -B g52b2_video.py <run_dir> [--out=<dir>] [--t0=<s>] [--t1=<s>] [--res=<judge json> (tests)]
"""'''

RUN_REPL = [
    ('TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"',
     'TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b2"\nsys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")', 1),
    ("import g52_common as GC", "import g52b2_common as GC", 1),
    ("GC.B52", "GC.B52B2", 1),
    ('"FLIP52"', '"FLIP52B2"', 2),
    ("GC.LEVEL_REGIONS_52", "GC.LEVEL_REGIONS_52B2", 1),
    ("x52_build.py", "x52b2_build.py", 1),
]
CHAIN_REPL = [
    ("import g52_common as GC", "import g52b2_common as GC", 1),
    ('RUN = GC.TOOLS52 + "/g52_run.py"', 'RUN = GC.TOOLS52B2 + "/g52b2_run.py"', 1),
    ("GC.B52", "GC.B52B2", 2),
    ("g52_pcfg.py", "g52b2_pcfg.py", 2),
    ("x52_build.py", "x52b2_build.py", 2),
    ("build_check52.json", "build_check52b2.json", 1),
]
OLD_CHECKS_HEAD = '''try:
    SP = dict(GC.SPEC_FLAT20)'''
OLD_CHECKS_TAIL = '''                     and not CHK.get("error"))          # dop_errors are recorded only (as FLIP49/50: some DOP nodes report before the first sim step)'''
NEW_CHECKS = '''try:
    SP = dict(GC.SPEC_BED)
    # 1-2: bed and particles on the DFGB3 two-slope bed (1:10 to h 11.5 m at x 235.25 m, 1:3 to the 6 m shelf at x 251.75 m) through the FLIP49
    #      two-slope VEX path (pgon true), the W 6 m strip and the W 140 m box
    set_box(0.5, GC.W_STRIP, SP)
    CHK["bed_strip"] = bed_check("DFGB3 two-slope bed strip (W 6 m, dp 0.5 m)")
    particle_check(CHK["bed_strip"], GC.bed_spec(parms=ctrl_floats()))
    set_box(0.5, GC.W_MAIN, SP)
    CHK["bed_3d"] = bed_check("DFGB3 two-slope bed 3D (W 140 m, dp 0.5 m grid)")
    set_box(1.0, GC.W_MAIN, SP)
    CHK["bed_3d_particles_dp1"] = particle_check(dict(W=float(ctrl.parm("W").eval())), GC.bed_spec(parms=ctrl_floats()))
    for _k in ("bed_strip", "bed_3d"):
        _c = CHK[_k]
        _c["depth_range_is_bed"] = bool(abs(float(_c.get("bed_min_depth_m", -1.0)) - GC.H_TOP) < 1e-6
                                        and abs(float(_c.get("bed_max_depth_m", -1.0)) - GC.H0) < 1e-6)
        _c["spec_is_bed"] = bool(float(_c["spec"]["x_toe"]) == GC.X_TOE and float(_c["spec"]["s"]) == GC.SLOPE_S
                                 and float(_c["spec"]["shelf_h"]) == GC.H_TOP and float(_c["spec"]["pg_hL"]) == GC.H_L
                                 and float(_c["spec"]["pg_s2"]) == GC.S2 and float(_c["spec"]["k"]) == 0.0 and GC.is_new(_c["spec"]))
    CHK["bed_numpy"] = GC.bed_selfcheck()
    restore_ctrl()
    # 3: the N-layer directional table (the DFGB3 generator table = DFG-2B-E's x exp(-i phi_n), y 0-140 m, of g52b2_table.py)
    CHK["dir_probe"] = dir_check(INPUTS["dir_npz"])
    # 4: bands on the D layout over the two-slope bed WITH the exit sponge: dir_on (N-layer), side band 95-140 m, exit sponge 332-412 m, ret_on,
    #    stage C test file
    restore_ctrl()
    ctrl.parm("dir_npz").set(INPUTS["dir_npz"])
    tabD = TB.load(INPUTS["dir_npz"])
    onD = dict(relax_on=1.0, sd_on=1.0, dir_on=1.0, ret_on=1.0, sf_on=0.0, abs_on=1.0, in_gain=1.03, sd_gain=0.97, duabs_on=1.0,
               volcorr_on=1.0, hold_on=1.0, ramp_s=GC.RAMP_S, dir_tf=GC.T_F)
    CHK["relax_probe_DFGB3"] = relax_check("D layout over the DFGB3 bed: inlet 0-100 m + side band 95-140 m (generating to 180.25 m, absorbing from "
                                           "210.25 m) + exit sponge 332-412 m, dir_on 1 (N-layer), ret_on 1", GC.W_MAIN, SP, onD,
                                           (1.0, 5.0, 19.0, 60.0, 99.0, 100.5, 150.0, 180.0, 195.0, 209.0, 211.0, 236.0, 245.0, 260.0, 326.0, 330.0,
                                            360.0, 395.0, 411.0),
                                           (0.5, 40.0, 94.0, 96.0, 110.0, 128.0, 135.0, 139.5), tab=tabD)
    restore_ctrl()
    for n in (sol, sftab, vdp, dtab, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
        n.cook(force=True)
    rlp_pts.parm("pts_json").set("[]"); dpr_pts.parm("pts_json").set("[]")
    CHK["restored_ctrl_equal_default"] = bool(ctrl_floats() == DEFAULT_CTRL and all(ctrl.parm(k).evalAsString() == v for k, v in DEFAULT_STR.items()))
    CHK["default_bed_is_DFGB3"] = bool(float(ctrl.parm("ridge_x0").eval()) == GC.X_TOE and float(ctrl.parm("ridge_s").eval()) == GC.SLOPE_S
                                       and float(ctrl.parm("shelf_h").eval()) == GC.H_TOP and float(ctrl.parm("pg_hL").eval()) == GC.H_L
                                       and float(ctrl.parm("pg_s2").eval()) == GC.S2 and float(ctrl.parm("ridge_k").eval()) == 0.0
                                       and float(ctrl.parm("ridge_on").eval()) == 1.0 and float(ctrl.parm("b_end").eval()) == 0.0
                                       and float(ctrl.parm("lag_xb").eval()) >= 1e8)
    CHK["default_sponge_parms"] = bool(float(ctrl.parm("xa0").eval()) == GC.XA0 and float(ctrl.parm("abs_sigma").eval()) == GC.ABS_SIGMA
                                       and float(ctrl.parm("abs_pow").eval()) == GC.ABS_POW and float(ctrl.parm("abs_on").eval()) == 0.0)
    CHK["saved_scene_still_water_bands_off"] = bool(all(ctrl.parm(k).eval() == 0.0 for k in ("relax_on", "abs_on", "sf_on", "dir_on", "sd_on", "ret_on",
                                                                                          "volcorr_on", "hold_on", "duabs_on", "wave_on")))
    CHK["dop_errors"] = {n_.path(): [str(e)[:200] for e in n_.errors()] for n_ in (relax, vcd, en_r, en_vc, msv, fo, fs) if n_.errors()}
except Exception as e:
    import traceback
    CHK["error"] = repr(e)[:400]
    CHK["traceback"] = traceback.format_exc()[-3000:]
    try:
        restore_ctrl()
    except Exception:
        pass
BEDK = ("bed_strip", "bed_3d")
CHK["all_ok"] = bool(all((CHK.get(k) or {}).get("bed_ok") and (CHK.get(k) or {}).get("sdf_ok") and (CHK.get(k) or {}).get("depth_range_is_bed")
                         and (CHK.get(k) or {}).get("spec_is_bed") for k in BEDK)
                     and all((CHK.get(k) or {}).get("particles_ok") for k in ("bed_strip", "bed_3d_particles_dp1"))
                     and (CHK.get("bed_numpy") or {}).get("ok")
                     and (CHK.get("dir_probe") or {}).get("ok") and (CHK.get("relax_probe_DFGB3") or {}).get("ok")
                     and (CHK.get("relax_probe_DFGB3") or {}).get("exit_sponge_damps") is True
                     and CHK.get("restored_ctrl_equal_default") and CHK.get("default_bed_is_DFGB3") and CHK.get("default_sponge_parms")
                     and CHK.get("saved_scene_still_water_bands_off")
                     and not CHK.get("error"))          # dop_errors are recorded only (as FLIP49/50/52: some DOP nodes report before the first sim step)'''
BUILD_REPL = [
    ('sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")\nimport importlib, numpy as np, g52_tanklib as L, g52_common as GC, g52_table as TB',
     'sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")\nsys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b2")\n'
     'import importlib, numpy as np, g52_tanklib as L, g52b2_common as GC, g52_table as TB', 1),
    ("AX = dict(GC.SPEC_FLAT20)", "AX = dict(GC.SPEC_BED)", 1),
    ("    # bed (g48 names; flat 20 m = plain path k 0, toe beyond the box)",
     "    # bed (g48 / g49 names; DFGB3 = the FLIP49 two-slope path: k 0, toe 160.25 m, 1:10 to h 11.5 m, then 1:3 to the 6 m shelf)", 1),
    ('"slope toe x_toe (m) (beyond the box: flat)"', '"slope toe x_toe (m) (DFGB3 160.25 m)"', 1),
    ('GC.B52 + "/runs/ckpt_default"', 'GC.B52B2 + "/runs/ckpt_default"', 1),
    ("# x52_build.py: the DFG2 table npz (and the branch tables)", "# x52b2_build.py: the DFGB3 generator table npz", 1),
]
VIDEO_REPL = [
    ("import g52b_common as GC", "import g52b2_common as GC", 1),
    ("import g52b_ana as GA", "import g52b2_ana as GA", 1),
    ('jl(os.path.join(rd, "g52b", "judge_DFGB.json")) or jl(os.path.join(rd, "g52b", "smoke_DFGB.json"))',
     'jl(os.path.join(rd, "g52b2", "judge_DFGB3.json"))', 1),
    ('"no g52b/judge_DFGB.json or smoke_DFGB.json in %s"', '"no g52b2/judge_DFGB3.json in %s"', 1),
    ('jl(os.path.join(rd, "g52b", "coequal_DFGB.json"))', 'jl(os.path.join(rd, "g52b2", "coequal_DFGB3.json"))', 1),
    ('''    if cset in ("DFG2B", "DFG2BE") and cset != GC.SET:      # AM-DFGB1: the label states the sea; it must be the run's sea
        raise SystemExit("run %s has sea %s but this process has %s: set G52B_SEA=%s" % (rid, cset, GC.SET, "E" if cset == "DFG2BE" else ""))''',
     '''    if cset != GC.SET:                                       # the header states the DFGB3 setup: it must be a DFGB3 run
        raise SystemExit("run %s has set %s, not %s (not a DFGB3 run)" % (rid, cset, GC.SET))''', 1),
    ('"%s_DFGB_compare.mp4"', '"%s_DFGB3_compare.mp4"', 1),
    ('"FLIP52B DFG-2B %s　t = %.2f s　粒子 %g m%s"', '"FLIP52B2 DFGB3（DFG-2B 第 2 回）%s　t = %.2f s　粒子 %g m%s"', 1),
    ('''            dr.text((30, 34), ("選んだ物【選び】：DFG-2 と同じ周期・方向の海（P 28 s、T 9.33/7/5.6 s、X2 の方向 34 本）、全エネルギー = DM1A（振幅の和 %.2f m"
                               "＝凍結時の %.3f 倍、AM-DFGB1）を D19B の" % (GC.A_SUM, GC.E_SCALE) if GC.SEA == "E" else
                               "選んだ物【選び】：DFG-2 と同じ海（P 28 s、T 9.33/7/5.6 s、X2 の方向 34 本、振幅の和 6.331 m = DM1A、大きくしていない）を D19B の")
                              + "斜面の水槽で、焦点 (%.2f, 0)（水深 %.1f m）・時刻 %s s" % (GC.X_F, GC.h_of(GC.X_F), " / ".join("%g" % q for q in fo)), fill=SUB, font=XV.fnt(13))''',
     '''            dr.text((30, 34), ("選んだ物【選び】：DFG-2B-E の海（X2 の方向 34 本、スペクトルのエネルギー = DM1A）＋造波の位相の較正。"
                               "海底 1:10 → 水深 11.5 m（x %.2f）→ 1:3 → 6 m の棚（x %.2f〜）。位相の基準 (%.0f, 0)・時刻 %s s"
                               % (GC.X_FOOT, GC.X_EDGE, GC.X_F, " / ".join("%g" % q for q in fo))), fill=SUB, font=XV.fnt(13))''', 1),
    ('''                 "(3) 収束：%s（miss 中央値 %s、bar %s、valid %s）" % (c3.get("outcomes"), _n(c3.get("core_miss_median")), _n(c3.get("bar")), c3.get("valid")),''',
     '''                 "(3) 収束：%s（miss 中央値 %s、bar %s、valid %s）" % (c3.get("outcomes"), _n(c3.get("core_miss_median")), _n(c3.get("bar")), c3.get("valid")),
                 "(3b) 原画に最も近い瞬間の収束：miss 中央値 %s（bar_pl %s、DFG-2B-E 2.27）→ %s　(3c) Hc が下がらない：%s" % (
                     _n((co.get("criterion_3b_convergence_at_print_like") or {}).get("pl_miss_median")),
                     _n((co.get("criterion_3b_convergence_at_print_like") or {}).get("bar_pl")),
                     (co.get("criterion_3b_convergence_at_print_like") or {}).get("ok"), (co.get("criterion_3c_hc_not_lower") or {}).get("ok")),''', 1),
    ("（auto_DFGB が pv53 → coequal の後にこの動画を作る）", "（auto_DFGB3 が pv53 → coequal の後にこの動画を作る）", 1),
]


def make(name, doc, repl, block=None, src=SRC):
    p = os.path.join(src, name)
    b = open(p, "rb").read()
    h = hashlib.sha256(b).hexdigest()
    if h != SHA[name]:
        raise SystemExit("%s sha256 %s differs from the recorded %s: not copied" % (name, h, SHA[name]))
    s = b.decode("utf8")
    i0 = s.find('"""'); i1 = s.find('"""', i0 + 3)
    if not (0 < i0 < i1):
        raise SystemExit("%s: docstring not found" % name)
    s = s[:i0] + (doc % h) + s[i1 + 3:]
    for old, new, n in repl:
        c = s.count(old)
        if c != n:
            raise SystemExit("%s: %r found %d times, expected %d: not copied" % (name, old[:80], c, n))
        s = s.replace(old, new)
    if block is not None:
        head, tail, new = block
        if s.count(head) != 1 or s.count(tail) != 1:
            raise SystemExit("%s: block markers found %d / %d times: not copied" % (name, s.count(head), s.count(tail)))
        a = s.find(head); z = s.find(tail) + len(tail)
        if not a < z:
            raise SystemExit("%s: block markers out of order" % name)
        s = s[:a] + new + s[z:]
    for bad in ("import g52_common", "import g52b_common", "import g52b_ana", "GC.B52 ", "GC.B52)", "GC.B52,", "GC.B52 +", "GC.B52B ", "GC.B52B)",
                "SPEC_FLAT20", "GC.LEVEL_REGIONS_52)", 'flat_20m") for k in BEDK', "GC.SEA", "judge_DFGB.json\"", "G52B_SEA"):
        if bad in s:
            raise SystemExit("%s: %r is still in the copy" % (name, bad))
    return s


def build_all():
    return {"g52b2_run.py": make("g52_run.py", RUN_DOC, RUN_REPL), "g52b2_chain.py": make("g52_chain.py", CHAIN_DOC, CHAIN_REPL),
            "g52b2_build_tank.py": make("g52_build_tank.py", BUILD_DOC, BUILD_REPL, block=(OLD_CHECKS_HEAD, OLD_CHECKS_TAIL, NEW_CHECKS)),
            "g52b2_video.py": make("g52b_video.py", VIDEO_DOC, VIDEO_REPL, src=SRC_B)}


def main():
    out = build_all()
    if "--check" in sys.argv:
        for nm, s in out.items():
            p = os.path.join(HERE, nm)
            same = os.path.exists(p) and open(p, encoding="utf8").read() == s
            print(nm, "same as on disk" if same else "DIFFERS from disk")
        return
    for nm, s in out.items():
        with open(os.path.join(HERE, nm), "w", encoding="utf8", newline="\n") as fh:
            fh.write(s)
        print("wrote", nm, hashlib.sha256(s.encode("utf8")).hexdigest()[:16])


if __name__ == "__main__":
    main()
