# -*- coding: utf-8 -*-
"""FLIP52B plan DFG-2B: make g52b_run.py, g52b_chain.py and g52b_build_tank.py as exact copies of flip52/g52_run.py, flip52/g52_chain.py and
flip52/g52_build_tank.py with counted string replacements only (py -3.10 -B). 2026-10-17 written new (Claude). The flip52 sources are READ ONLY:
their sha256 must equal the values below (the versions that built Houdini/FLIP52/g52_tank.hiplc and run DFG-2), otherwise nothing is written.
Every replacement must match its expected count exactly, so the copies are the FLIP52 run loop, chain and builder (which are the FLIP50 ones with
the N-layer table) except for these named changes:
  g52b_run.py        constants / paths of FLIP52B (g52b_common: Build/FLIP52B, Houdini/FLIP52B/g52b_tank.hiplc, the D19B level regions);
                     the N-layer numpy mirror stays flip52/g52_table.py (generic: it reads hh and kk<n> per node); record stage "FLIP52B".
  g52b_chain.py      paths of FLIP52B (Build/FLIP52B, flip52b/g52b_run.py, _logs/build_check52b.json); messages name x52b_build.py / g52b_pcfg.py.
  g52b_build_tank.py the D19B tank of FLIP50 / plan E with the N-layer VEX of flip52/g52_tanklib.py (unchanged, node names G52_*):
                     g52b_common constants (box48 D19B, Lx 412 m, W 140 m, zb -19 m, bands as option D, no exit sponge, dir_tf = DFG-2B t_f);
                     the bed / particle checks are the FLIP50 D19B ones (strip W 6 m and 3D W 140 m, the analytic D19B bed bit for bit);
                     the band probe is the FLIP50 D-layout probe (inlet 0-100 m, side band 95-140 m) with dir_on = the N-layer table; the probe
                     rule 'exit sponge damps' applies only when abs_on (the D tank has no exit sponge: the beach); writes Houdini/FLIP52B and
                     Unity/Build/FLIP52B/_logs/build_check52b.json.
usage: py -3.10 -B g52b_mkcopy.py [--check]     (--check: build in memory and compare with the files on disk; writes nothing)
"""
import os, sys, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"
F52 = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"
F52B = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b"
SHA = {"g52_run.py": "282b21e393e3ecfabb4c3774c29b60b40bccd16491519bb7e996abd51db6e17b",
       "g52_chain.py": "adc668759bf65cddf411c31e1fe8fa4861d2b8ee709a46f81e13894eb495d728",
       "g52_build_tank.py": "d4747657dcd50a8fc548af2f40fcc5d578202b94ef89b81da1cf70f51f05f2f7"}

RUN_DOC = '''"""FLIP52B plan DFG-2B: run one launch of a FLIP52B calculation and write its records (hython; started by g52b_chain.py).
GENERATED 2026-10-17 by flip52b/g52b_mkcopy.py from flip52/g52_run.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52b/g52b_common.py (Build/FLIP52B, Houdini/FLIP52B/g52b_tank.hiplc, the D19B level regions, gauges);
    the N-layer numpy mirror is flip52/g52_table.py (generic); record stage "FLIP52B"; message 'x52b_build.py'.
Everything else is the FLIP52 run loop (= the FLIP50 one that ran DM1A / DF1A / plan E, with the N-layer OUT_DIRTAB check).
usage: hython g52b_run.py <cfg.json>  (normally py -3.10 g52b_chain.py <cfg.json>)
output: Unity/Build/FLIP52B/<out_root>/<run_id>/  (cfg out_root is an absolute FLIP52B folder)
"""'''

CHAIN_DOC = '''"""FLIP52B plan DFG-2B: run one calculation to the end as chained launches of <= 29 min (py -3.10).
GENERATED 2026-10-17 by flip52b/g52b_mkcopy.py from flip52/g52_chain.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52b/g52b_common.py (Build/FLIP52B, Houdini/FLIP52B/g52b_tank.hiplc) and flip52b/g52b_run.py; the start
    gate reads Unity/Build/FLIP52B/_logs/build_check52b.json; messages name x52b_build.py and g52b_pcfg.py.
Everything else is the FLIP52 / FLIP50 chain (flip46/g46_ckpt ledger; start gate: cfg precheck.ok, build check, frozen plan .sha256, table
sha256; resume from the last checkpoint; waits for every other hython before each launch; waiting time is not counted against max_hours).
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b/g52b_chain.py <cfg.json>
"""'''

BUILD_DOC = '''"""FLIP52B plan DFG-2B: build the tank scene Houdini/FLIP52B/g52b_tank.hiplc (hython, a few min; launched by x52b_build.py, which waits for
every other hython first). GENERATED 2026-10-17 by flip52b/g52b_mkcopy.py from flip52/g52_build_tank.py (sha256 %s, not edited) by exact,
counted string replacements. The scene = the FLIP52 scene (same particle seeding, surface VDB, FLIP Solver 2.0, bed SDF, read / surface paths,
stage A/B/C nodes, node names G52_*, the N-layer VEX of flip52/g52_tanklib.py unchanged) on the D19B tank of FLIP50 / plan E:
  - constants from flip52b/g52b_common.py: box48 D19B (x 0-412 m, y 0-140 m, z -19 .. +17 m, floor pad 2 cells), the D19B bed (1:10 from
    x 160.25 m) through the FLIP48 plain path, bands as option D (inlet 0-100 m, taper 20 m, side band 95-140 m generating to x 180.25 m,
    absorbing from 210.25 m, taper 11.25 m), no exit sponge (the beach), ramp 14 s, dir_tf = the DFG-2B first focus time. Every band default is
    OFF (still water); g52b_run.py switches them on from the cfg parms.
Checks (Unity/Build/FLIP52B/_logs/build_check52b.json; all_ok false -> g52b_chain.py never starts):
  1. bed: OUT_BED heights and the bed SDF against numpy on the D19B strip (W 6 m) and the D19B 3D box (W 140 m) on the dp 0.5 grid; numpy
     D19B = the analytic -(19 - max(x - 160.25, 0)/10) bit for bit (the FLIP50 check).
  2. particles: Houdini seeding against count_particles: strip at dp 0.5, 3D at dp 1.0 (W 140 m); none below the bed.
  3. N-layer directional table: OUT_DIRTAB detail and dir_probe (VEX dirwave, g = 1) against the numpy mirror flip52/g52_table.dirwave_np
     (within 1e-5 of the scale).
  4. bands: relax_probe (VEX relax_apply + vc_divergence) against g52_table.relax_np on the D layout (the FLIP50 probe points; dir_on 1 with
     the N-layer table, ret_on 1, stage-C test file, in_gain 1.03 / sd_gain 0.97); vertical velocity unchanged, interior untouched, the side
     absorber damps; 'exit sponge damps' only when abs_on.
  5. the saved scene's CTRL equals the build defaults (still water, every band off).
usage: py -3.10 x52b_build.py  (writes the table, waits for other hython, runs hython g52b_build_tank.py)
"""'''

RUN_REPL = [
    ('TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"',
     'TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b"\nsys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")', 1),
    ("import g52_common as GC", "import g52b_common as GC", 1),
    ("GC.B52", "GC.B52B", 1),
    ('"FLIP52"', '"FLIP52B"', 2),
    ("GC.LEVEL_REGIONS_52", "GC.LEVEL_REGIONS_52B", 1),
    ("x52_build.py", "x52b_build.py", 1),
]
CHAIN_REPL = [
    ("import g52_common as GC", "import g52b_common as GC", 1),
    ('RUN = GC.TOOLS52 + "/g52_run.py"', 'RUN = GC.TOOLS52B + "/g52b_run.py"', 1),
    ("GC.B52", "GC.B52B", 2),
    ("g52_pcfg.py", "g52b_pcfg.py", 2),
    ("x52_build.py", "x52b_build.py", 2),
    ("build_check52.json", "build_check52b.json", 1),
]
OLD_CHECKS_HEAD = '''try:
    SP = dict(GC.SPEC_FLAT20)'''
OLD_CHECKS_TAIL = '''                     and not CHK.get("error"))          # dop_errors are recorded only (as FLIP49/50: some DOP nodes report before the first sim step)'''
NEW_CHECKS = '''try:
    SP = dict(GC.SPEC_BED)
    # 1-2: bed and particles (the FLIP50 D19B checks)
    set_box(0.5, GC.W_STRIP, SP)
    CHK["D19B_strip"] = bed_check("D19B strip (W 6 m, dp 0.5 m)")
    particle_check(CHK["D19B_strip"], GC.bed_spec(parms=ctrl_floats()))
    set_box(0.5, GC.W_MAIN, SP)
    CHK["D19B_3d"] = bed_check("D19B 3D (W 140 m, dp 0.5 m grid)")
    set_box(1.0, GC.W_MAIN, SP)
    CHK["D19B_3d_particles_dp1"] = particle_check(dict(W=float(ctrl.parm("W").eval())), GC.bed_spec(parms=ctrl_floats()))
    xq = np.arange(0.0, GC.LX, 0.37); yq = np.arange(0.0, GC.W_MAIN, 0.41)
    CHK["D19B_numpy"] = dict(equals_analytic_bit=bool(np.array_equal(GC.bed_z(xq[None, :], yq[:, None], **SP)[0],
                                                                     -(GC.H0 - np.maximum(xq - GC.X_TOE, 0.0) / GC.SLOPE_S))),
                             laterally_uniform=bool(np.all(GC.bed_z(xq[None, :], yq[:, None], **SP) == GC.bed_z(xq[None, :], 0.0 * yq[:, None], **SP))),
                             g48_plain_path=bool(not GC.is_new(SP)), kind=GC.bed_kind(SP), x_toe=float(SP["x_toe"]))
    restore_ctrl()
    # 3: the N-layer directional table (D19B WKB table of g52b_table.py)
    CHK["dir_probe"] = dir_check(INPUTS["dir_npz"])
    # 4: bands on the D layout (W 140): dir_on (N-layer), side band, ret_on, stage C test file; no exit sponge (the beach)
    restore_ctrl()
    ctrl.parm("dir_npz").set(INPUTS["dir_npz"])
    tabD = TB.load(INPUTS["dir_npz"])
    onD = dict(relax_on=1.0, sd_on=1.0, dir_on=1.0, ret_on=1.0, sf_on=0.0, abs_on=0.0, in_gain=1.03, sd_gain=0.97, duabs_on=1.0,
               volcorr_on=1.0, hold_on=1.0, ramp_s=GC.RAMP_S, dir_tf=GC.T_F)
    CHK["relax_probe_D"] = relax_check("D layout: inlet 0-100 m + side band 95-140 m (generating to 180.25 m, absorbing from 210.25 m), no exit "
                                       "sponge, dir_on 1 (N-layer), ret_on 1", GC.W_MAIN, SP, onD,
                                       (1.0, 5.0, 19.0, 60.0, 99.0, 100.5, 150.0, 180.0, 195.0, 209.0, 211.0, 260.0, 400.0),
                                       (0.5, 40.0, 94.0, 96.0, 110.0, 128.0, 135.0, 139.5), tab=tabD)
    restore_ctrl()
    for n in (sol, sftab, vdp, dtab, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
        n.cook(force=True)
    rlp_pts.parm("pts_json").set("[]"); dpr_pts.parm("pts_json").set("[]")
    CHK["restored_ctrl_equal_default"] = bool(ctrl_floats() == DEFAULT_CTRL and all(ctrl.parm(k).evalAsString() == v for k, v in DEFAULT_STR.items()))
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
BEDK = ("D19B_strip", "D19B_3d")
CHK["all_ok"] = bool(all((CHK.get(k) or {}).get("bed_ok") and (CHK.get(k) or {}).get("sdf_ok") for k in BEDK)
                     and all((CHK.get(k) or {}).get("particles_ok") for k in ("D19B_strip", "D19B_3d_particles_dp1"))
                     and all((CHK.get("D19B_numpy") or {}).get(k) for k in ("equals_analytic_bit", "laterally_uniform", "g48_plain_path"))
                     and (CHK.get("dir_probe") or {}).get("ok") and (CHK.get("relax_probe_D") or {}).get("ok")
                     and CHK.get("restored_ctrl_equal_default") and CHK.get("saved_scene_still_water_bands_off")
                     and not CHK.get("error"))          # dop_errors are recorded only (as FLIP49/50/52: some DOP nodes report before the first sim step)'''
BUILD_REPL = [
    ('sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")\nimport importlib, numpy as np, g52_tanklib as L, g52_common as GC, g52_table as TB',
     'sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")\nsys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b")\n'
     'import importlib, numpy as np, g52_tanklib as L, g52b_common as GC, g52_table as TB', 1),
    ("AX = dict(GC.SPEC_FLAT20)", "AX = dict(GC.SPEC_BED)", 1),
    ("    # bed (g48 names; flat 20 m = plain path k 0, toe beyond the box)", "    # bed (g48 names; D19B = plain path k 0, toe 160.25 m, 1:10)", 1),
    ('"slope toe x_toe (m) (beyond the box: flat)"', '"slope toe x_toe (m) (D19B 160.25 m)"', 1),
    ('GC.B52 + "/runs/ckpt_default"', 'GC.B52B + "/runs/ckpt_default"', 1),
    ('                     and out["n_interior"] > 0 and out["n_absorb"] > 0 and out["n_sponge"] > 0)',
     '                     and out["n_interior"] > 0 and out["n_absorb"] > 0 and (out["n_sponge"] > 0 or P_["abs_on"] < 0.5))', 1),
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
    for bad in ("import g52_common", "GC.B52 ", "GC.B52)", "GC.B52,", "GC.B52 +", "SPEC_FLAT20", "GC.LEVEL_REGIONS_52)", "flat_20m\") for k in BEDK"):
        if bad in s:
            raise SystemExit("%s: %r is still in the copy" % (name, bad))
    return s


def build_all():
    return {"g52b_run.py": make("g52_run.py", RUN_DOC, RUN_REPL), "g52b_chain.py": make("g52_chain.py", CHAIN_DOC, CHAIN_REPL),
            "g52b_build_tank.py": make("g52_build_tank.py", BUILD_DOC, BUILD_REPL, block=(OLD_CHECKS_HEAD, OLD_CHECKS_TAIL, NEW_CHECKS))}


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
