# -*- coding: utf-8 -*-
"""FLIP52S2 plan DFG-S-E140: make g52s2_run.py, g52s2_chain.py and g52s2_build_tank.py as exact copies of flip52/g52_run.py,
flip52/g52_chain.py and flip52/g52_build_tank.py with counted string replacements only (py -3.10 -B). 2026-10-18 written new (Claude) by
adapting flip52s/g52s_mkcopy.py (DFG-S, frozen, not edited). The flip52 sources are READ ONLY: their sha256 must equal the values below (the
versions that built Houdini/FLIP52/g52_tank.hiplc and ran DFG-2; the same values flip52s / flip52b recorded), otherwise nothing is written.
Every replacement must match its expected count exactly, so the copies are the FLIP52 run loop, chain and builder except for these named changes:
  g52s2_run.py        constants / paths of FLIP52S2 (g52s2_common: Build/FLIP52S2, Houdini/FLIP52S2/g52s2_tank.hiplc, the level regions);
                      the N-layer numpy mirror stays flip52/g52_table.py (generic); record stage "FLIP52S2".
  g52s2_chain.py      paths of FLIP52S2 (Build/FLIP52S2, flip52s2/g52s2_run.py, _logs/build_check52s2.json); messages name x52s2_build.py /
                      g52s2_pcfg.py.
  g52s2_build_tank.py the DFG-2 tank (box, bands, exit sponge, N-layer VEX of flip52/g52_tanklib.py unchanged, node names G52_*) with the DFG-S
                      step as the default bed (g52s2_common.SPEC_STEP through the FLIP48 plain path: no new VEX term, = DFG-S); the bed /
                      particle checks are on the step (strip W 6 m and 3D W 140 m on the dp 0.5 grid: VEX heights and SDF vs numpy, depth range
                      exactly 6-20 m, particles vs the numpy seeding rule at W 140; plus the numpy-only g52s2_common.bed_selfcheck); the band
                      probe is on the W 140 layout (inlet 0-50 m, side band 110-140 m generating to 180 m / absorbing from 210 m, exit sponge),
                      probes across the side band (y 105-139.5 m) and on the face (108, 125, 145 m); writes Houdini/FLIP52S2 and
                      Unity/Build/FLIP52S2/_logs/build_check52s2.json.
usage: py -3.10 -B g52s2_mkcopy.py [--check]     (--check: build in memory and compare with the files on disk; writes nothing)
"""
import os, sys, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"
SHA = {"g52_run.py": "282b21e393e3ecfabb4c3774c29b60b40bccd16491519bb7e996abd51db6e17b",
       "g52_chain.py": "adc668759bf65cddf411c31e1fe8fa4861d2b8ee709a46f81e13894eb495d728",
       "g52_build_tank.py": "d4747657dcd50a8fc548af2f40fcc5d578202b94ef89b81da1cf70f51f05f2f7"}

RUN_DOC = '''"""FLIP52S2 plan DFG-S-E140: run one launch of a FLIP52S2 calculation and write its records (hython; started by g52s2_chain.py).
GENERATED 2026-10-18 by flip52s2/g52s2_mkcopy.py from flip52/g52_run.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52s2/g52s2_common.py (Build/FLIP52S2, Houdini/FLIP52S2/g52s2_tank.hiplc, the level regions);
    the N-layer numpy mirror is flip52/g52_table.py (generic); record stage "FLIP52S2"; message 'x52s2_build.py'.
Everything else is the FLIP52 run loop (= the FLIP50 one that ran DM1A / DF1A / plan E, with the N-layer OUT_DIRTAB check) that ran DFG-2 / DFG-S.
usage: hython g52s2_run.py <cfg.json>  (normally py -3.10 g52s2_chain.py <cfg.json>)
output: Unity/Build/FLIP52S2/<out_root>/<run_id>/  (cfg out_root is an absolute FLIP52S2 folder)
"""'''

CHAIN_DOC = '''"""FLIP52S2 plan DFG-S-E140: run one calculation to the end as chained launches of <= 29 min (py -3.10).
GENERATED 2026-10-18 by flip52s2/g52s2_mkcopy.py from flip52/g52_chain.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52s2/g52s2_common.py (Build/FLIP52S2, Houdini/FLIP52S2/g52s2_tank.hiplc) and flip52s2/g52s2_run.py; the start
    gate reads Unity/Build/FLIP52S2/_logs/build_check52s2.json; messages name x52s2_build.py and g52s2_pcfg.py.
Everything else is the FLIP52 / FLIP50 chain (flip46/g46_ckpt ledger; start gate: cfg precheck.ok, build check, frozen plan .sha256, table
sha256; resume from the last checkpoint; waits for every other hython before each launch; waiting time is not counted against max_hours,
which counts from this chain's own start: a new chain on a max_hours stop resumes from the last checkpoint with a fresh budget).
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52s2/g52s2_chain.py <cfg.json>
"""'''

BUILD_DOC = '''"""FLIP52S2 plan DFG-S-E140: build the tank scene Houdini/FLIP52S2/g52s2_tank.hiplc (hython, a few min; launched by x52s2_build.py, which
waits for every other hython first). GENERATED 2026-10-18 by flip52s2/g52s2_mkcopy.py from flip52/g52_build_tank.py (sha256 %s, not edited)
by exact, counted string replacements. The scene = the FLIP52 scene of DFG-2 / DFG-S (same particle seeding, surface VDB, FLIP Solver 2.0, bed
SDF, read / surface paths, stage A/B/C nodes, node names G52_*, the N-layer VEX of flip52/g52_tanklib.py unchanged) with the DFG-S STEP as the
default bed (flat 20 m to x 108 m, 1:3 face to the edge x 150 m, 6 m shelf; g52s2_common.SPEC_STEP through the FLIP48 plain bed path: ridge_on 1,
ridge_k 0, ridge_x0 108, ridge_s 3, shelf_h 6; no new VEX term). The box and bands are CTRL parms set by each run's cfg (W 140 m, inlet 0-50 m,
side band 110-140 m generating to 180 m / absorbing from 210 m, exit sponge 210-290 m); every band default is OFF (still water).
Checks (Unity/Build/FLIP52S2/_logs/build_check52s2.json; all_ok false -> g52s2_chain.py never starts):
  1. bed: OUT_BED heights and the bed SDF (collision) against numpy on the step strip (W 6 m) and the step 3D box (W 140 m) on the dp 0.5 grid
     (< 1 cm and < 2 cm, no SDF sign mismatch), the depth range exactly 6-20 m, + the numpy-only g52s2_common.bed_selfcheck.
  2. particles: Houdini seeding against count_particles: strip at dp 0.5, 3D at dp 1.0 (W 140 m); none below the bed.
  3. N-layer directional table: OUT_DIRTAB detail and dir_probe (VEX dirwave, g = 1) against the numpy mirror flip52/g52_table.dirwave_np
     (within 1e-5 of the scale) on the energy-matched W 140 table.
  4. bands: relax_probe (VEX relax_apply + vc_divergence) against g52_table.relax_np on the W 140 layout with the step bed (dir_on 1, ret_on 1,
     stage-C test file, in_gain 1.03 / sd_gain 0.97, probes across the side band y 105-139.5 m and on the face x 108 / 125 / 145 m): vertical
     velocity unchanged, interior untouched, the side absorber and the exit sponge damp.
  5. the saved scene's CTRL equals the build defaults (still water, every band off).
usage: py -3.10 x52s2_build.py  (writes the table, waits for other hython, runs hython g52s2_build_tank.py)
"""'''

RUN_REPL = [
    ('TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"',
     'TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52s2"\nsys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")', 1),
    ("import g52_common as GC", "import g52s2_common as GC", 1),
    ("GC.B52", "GC.B52S2", 1),
    ('"FLIP52"', '"FLIP52S2"', 2),
    ("GC.LEVEL_REGIONS_52", "GC.LEVEL_REGIONS_52S2", 1),
    ("x52_build.py", "x52s2_build.py", 1),
]
CHAIN_REPL = [
    ("import g52_common as GC", "import g52s2_common as GC", 1),
    ('RUN = GC.TOOLS52 + "/g52_run.py"', 'RUN = GC.TOOLS52S2 + "/g52s2_run.py"', 1),
    ("GC.B52", "GC.B52S2", 2),
    ("g52_pcfg.py", "g52s2_pcfg.py", 2),
    ("x52_build.py", "x52s2_build.py", 2),
    ("build_check52.json", "build_check52s2.json", 1),
]
OLD_CHECKS_HEAD = '''try:
    SP = dict(GC.SPEC_FLAT20)'''
OLD_CHECKS_TAIL = '''                     and not CHK.get("error"))          # dop_errors are recorded only (as FLIP49/50: some DOP nodes report before the first sim step)'''
NEW_CHECKS = '''try:
    SP = dict(GC.SPEC_STEP)
    # 1-2: bed and particles on the DFG-S step (flat 20 m to x 108 m, 1:3 face to x 150 m, 6 m shelf) through the FLIP48 plain VEX path, W 140
    set_box(0.5, GC.W_STRIP, SP)
    CHK["step_strip"] = bed_check("DFG-S step strip (W 6 m, dp 0.5 m)")
    particle_check(CHK["step_strip"], GC.bed_spec(parms=ctrl_floats()))
    set_box(0.5, GC.W_MAIN, SP)
    CHK["step_3d"] = bed_check("DFG-S step 3D (W 140 m, dp 0.5 m grid)")
    set_box(1.0, GC.W_MAIN, SP)
    CHK["step_3d_particles_dp1"] = particle_check(dict(W=float(ctrl.parm("W").eval())), GC.bed_spec(parms=ctrl_floats()))
    for _k in ("step_strip", "step_3d"):
        _c = CHK[_k]
        _c["depth_range_is_step"] = bool(abs(float(_c.get("bed_min_depth_m", -1.0)) - GC.H_TOP) < 1e-6
                                         and abs(float(_c.get("bed_max_depth_m", -1.0)) - GC.H0) < 1e-6)
        _c["spec_is_step"] = bool(float(_c["spec"]["x_toe"]) == GC.X_TOE and float(_c["spec"]["s"]) == GC.SLOPE_S
                                  and float(_c["spec"]["shelf_h"]) == GC.H_TOP and float(_c["spec"]["k"]) == 0.0)
    CHK["step_numpy"] = GC.bed_selfcheck()
    restore_ctrl()
    # 3: the N-layer directional table (the energy-matched WKB table over the step, y 0-140 m, of g52s2_table.py)
    CHK["dir_probe"] = dir_check(INPUTS["dir_npz"])
    # 4: bands on the W 140 layout over the step: dir_on (N-layer), side band 110-140 m, exit sponge, ret_on, stage C test file
    restore_ctrl()
    ctrl.parm("dir_npz").set(INPUTS["dir_npz"])
    tabD = TB.load(INPUTS["dir_npz"])
    onD = dict(relax_on=1.0, sd_on=1.0, dir_on=1.0, ret_on=1.0, sf_on=0.0, abs_on=1.0, in_gain=1.03, sd_gain=0.97, duabs_on=1.0,
               volcorr_on=1.0, hold_on=1.0, ramp_s=GC.RAMP_S, dir_tf=GC.T_F)
    CHK["relax_probe_DFGS2"] = relax_check("W 140 layout over the DFG-S step: inlet 0-50 m + side band 110-140 m + exit sponge 210-290 m, dir_on 1, ret_on 1",
                                          GC.W_MAIN, SP, onD,
                                          (1.0, 5.0, 12.0, 30.0, 49.0, 50.5, 100.0, 108.0, 125.0, 145.0, 150.0, 179.0, 181.0, 195.0, 209.0, 211.0,
                                           235.0, 289.0),
                                          (0.5, 40.0, 69.0, 71.0, 99.5, 105.0, 109.0, 111.0, 125.0, 132.0, 135.0, 139.5), tab=tabD)
    restore_ctrl()
    for n in (sol, sftab, vdp, dtab, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
        n.cook(force=True)
    rlp_pts.parm("pts_json").set("[]"); dpr_pts.parm("pts_json").set("[]")
    CHK["restored_ctrl_equal_default"] = bool(ctrl_floats() == DEFAULT_CTRL and all(ctrl.parm(k).evalAsString() == v for k, v in DEFAULT_STR.items()))
    CHK["default_bed_is_step"] = bool(float(ctrl.parm("ridge_x0").eval()) == GC.X_TOE and float(ctrl.parm("ridge_s").eval()) == GC.SLOPE_S
                                      and float(ctrl.parm("shelf_h").eval()) == GC.H_TOP and float(ctrl.parm("ridge_k").eval()) == 0.0
                                      and float(ctrl.parm("ridge_on").eval()) == 1.0)
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
BEDK = ("step_strip", "step_3d")
CHK["all_ok"] = bool(all((CHK.get(k) or {}).get("bed_ok") and (CHK.get(k) or {}).get("sdf_ok") and (CHK.get(k) or {}).get("depth_range_is_step")
                         and (CHK.get(k) or {}).get("spec_is_step") for k in BEDK)
                     and all((CHK.get(k) or {}).get("particles_ok") for k in ("step_strip", "step_3d_particles_dp1"))
                     and (CHK.get("step_numpy") or {}).get("ok")
                     and (CHK.get("dir_probe") or {}).get("ok") and (CHK.get("relax_probe_DFGS2") or {}).get("ok")
                     and CHK.get("restored_ctrl_equal_default") and CHK.get("default_bed_is_step") and CHK.get("saved_scene_still_water_bands_off")
                     and not CHK.get("error"))          # dop_errors are recorded only (as FLIP49/50/52: some DOP nodes report before the first sim step)'''
BUILD_REPL = [
    ('sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")\nimport importlib, numpy as np, g52_tanklib as L, g52_common as GC, g52_table as TB',
     'sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")\nsys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52s2")\n'
     'import importlib, numpy as np, g52_tanklib as L, g52s2_common as GC, g52_table as TB', 1),
    ("AX = dict(GC.SPEC_FLAT20)", "AX = dict(GC.SPEC_STEP)", 1),
    ("    # bed (g48 names; flat 20 m = plain path k 0, toe beyond the box)", "    # bed (g48 names; DFG-S step = plain path k 0, toe 108 m, 1:3 face, shelf 6 m; box W from the run cfg)", 1),
    ('"slope toe x_toe (m) (beyond the box: flat)"', '"slope toe x_toe (m) (DFG-S step 108 m)"', 1),
    ('GC.B52 + "/runs/ckpt_default"', 'GC.B52S2 + "/runs/ckpt_default"', 1),
    ("# x52_build.py: the DFG2 table npz (and the branch tables)", "# x52s2_build.py: the DFG-S-E140 table npz (energy-matched, y 0-140 m)", 1),
]


def make(name, doc, repl, block=None):
    p = os.path.join(SRC, name)
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
    for bad in ("import g52_common", "GC.B52 ", "GC.B52)", "GC.B52,", "GC.B52 +", "SPEC_FLAT20", "GC.LEVEL_REGIONS_52)", "bed_flat_20m\") for k in BEDK",
                "build_check52.json", '"FLIP52"', "x52_build.py", "g52_pcfg.py", "GC.TOOLS52 + ", "g52s_common", "GC.B52S ", "GC.B52S)", "GC.B52S +",
                "GC.LEVEL_REGIONS_52S)", "build_check52s.json", '"FLIP52S"', "x52s_build.py", "g52s_pcfg.py", 'relax_probe_DFGS"'):
        if bad in s:
            raise SystemExit("%s: %r is still in the copy" % (name, bad))
    return s


def build_all():
    return {"g52s2_run.py": make("g52_run.py", RUN_DOC, RUN_REPL), "g52s2_chain.py": make("g52_chain.py", CHAIN_DOC, CHAIN_REPL),
            "g52s2_build_tank.py": make("g52_build_tank.py", BUILD_DOC, BUILD_REPL, block=(OLD_CHECKS_HEAD, OLD_CHECKS_TAIL, NEW_CHECKS))}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
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
