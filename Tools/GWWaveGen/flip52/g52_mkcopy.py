# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: make g52_run.py and g52_chain.py as exact copies of flip50/g50_run.py and flip50/g50_chain.py with counted string
replacements only (py -3.10 -B). 2026-10-17 written new (Claude). The two flip50 sources are READ ONLY: their sha256 must equal the values
below (the versions that ran SMOKE50DA, DM1A, DF1A and plan E), otherwise nothing is written. Every replacement must match its expected count
exactly, so the copies are the FLIP50 run loop and chain (as they ran) except for these named changes:
  g52_run.py   (hython) paths / node names / stage label of FLIP52; the OUT_DIRTAB check is the N-layer one (fields of the table, d_nlayer,
               d_P, harmonics, t_f, content hash); the default level regions are FLIP52's; the descriptor period is read from cfg sf.T only.
  g52_chain.py (py -3.10) paths of FLIP52 (Build/FLIP52, Houdini/FLIP52/g52_tank.hiplc through g52_common, flip52/g52_run.py,
               _logs/build_check52.json); messages name x52_build.py / g52_pcfg.py.
usage: py -3.10 -B g52_mkcopy.py [--check]     (--check: build in memory and compare with the files on disk; writes nothing)
"""
import os, sys, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50"
SHA = {"g50_run.py": "78bae5b081b7ee2c76ac88229611e5ae3ceed14ace14cee3dbdd6097031cb540",
       "g50_chain.py": "258c32bc3d52a4ad1a0c8fe7e8905194cdafa539a4d6923620f8f7d7498dc5f7"}

RUN_DOC = '''"""FLIP52 plan DFG-2: run one launch of a FLIP52 calculation and write its records (hython; started by g52_chain.py).
GENERATED 2026-10-17 by flip52/g52_mkcopy.py from flip50/g50_run.py (sha256 %s, not edited) by exact, counted string replacements:
  - tools g52_common (Build/FLIP52, Houdini/FLIP52/g52_tank.hiplc), g52_table (numpy mirror of the N-layer band VEX); node names G52_*;
    record stage "FLIP52"; default level regions = g52_common.LEVEL_REGIONS_52; message 'x52_build.py'.
  - cfg dir (N-layer table of g52_table.py): the npz must exist with the sha256 written in the cfg; it is loaded into OUT_DIRTAB through the
    CTRL string dir_npz; the run stops unless OUT_DIRTAB has the table's fields, d_nlayer = cfg n_layers, d_P = cfg P, the cfg harmonics,
    d_tf = the table t_f = CTRL dir_tf, and the cfg content hash. Recorded in info.dir_table.
  - the descriptor period T_WAVE is cfg sf.T (the dir block holds lists per layer).
Everything else is the FLIP50 run loop as it ran SMOKE50DA, DM1A, DF1A and the plan E screens (records hf, r2, r3, r4, r5, r6, volcorr,
checkpoints, guards, dir_check recorded only).
usage: hython g52_run.py <cfg.json>  (normally py -3.10 g52_chain.py <cfg.json>)
output: Unity/Build/FLIP52/<out_root>/<run_id>/  (cfg out_root is an absolute FLIP52 folder)
"""'''

CHAIN_DOC = '''"""FLIP52 plan DFG-2: run one calculation to the end as chained launches of <= 29 min (py -3.10).
GENERATED 2026-10-17 by flip52/g52_mkcopy.py from flip50/g50_chain.py (sha256 %s, not edited) by exact, counted string replacements:
  - tools g52_common (Build/FLIP52, Houdini/FLIP52/g52_tank.hiplc) and flip52/g52_run.py; hython temp folder Build/FLIP52/tmp_houdini;
    the start gate reads Unity/Build/FLIP52/_logs/build_check52.json (all_ok and hip_sha256 = the current scene); messages name x52_build.py
    and g52_pcfg.py.
Everything else is the FLIP50 chain (flip46/g46_ckpt ledger, nothing pruned without the user's permission; the start gate: cfg precheck.ok,
build check, frozen plan .sha256, table sha256; resume from the last checkpoint; waits for every other hython before each launch; waiting
time is not counted against cfg max_hours).
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52/g52_chain.py <cfg.json>
"""'''

OLD_DIR = '''    _dg = hou.node("/obj/G50_SETUP/OUT_DIRTAB").geometry()
    DIRINFO = {nm: _dg.attribValue(nm) for nm in ("d_omega", "d_T", "d_x0", "d_x1", "d_y0", "d_y1", "d_nfield", "d_content", "d_src")}
    _om = 2.0 * math.pi / float(DIR["T"])
    # 2026-10-16 build step: d_omega is a float32 detail attribute (hou addAttrib has no 64-bit option): rel. error <= 2^-24, so the
    # tolerance is 2^-23 (was 1e-9, which every launch would have failed on the rounding alone; phase error < 2e-6 rad at 140 s)
    if int(DIRINFO["d_nfield"]) != len(GC.TABLE_FIELDS) or abs(float(DIRINFO["d_omega"]) - _om) > 2.0 ** -23 * _om or DIRINFO["d_content"] != DIR.get("content_sha256"):
        stop_early("error: OUT_DIRTAB does not match the cfg table: %s" % DIRINFO)
    DIRINFO.update(npz=_np, npz_sha256=_sha, T=float(DIR["T"]), case=DIR.get("case"))
    DTAB = TB.load(_np)
'''
NEW_DIR = '''    _dg = hou.node("/obj/G52_SETUP/OUT_DIRTAB").geometry()
    DIRINFO = {nm: _dg.attribValue(nm) for nm in ("d_P", "d_nlayer", "d_n0", "d_n1", "d_n2", "d_n3", "d_om0", "d_om1", "d_om2", "d_om3",
                                                  "d_x0", "d_x1", "d_y0", "d_y1", "d_tf", "d_nfield", "d_content", "d_src")}
    DTAB = TB.load(_np)
    # FLIP52: the N-layer table (d_nlayer, d_P, d_n<n>, d_tf are exact float32 detail attributes; see g52_tanklib.PYSOP_DIRTAB52)
    _I = DTAB["info"]
    _nl = int(_I["n_layers"])
    _bad = []
    if int(DIRINFO["d_nfield"]) != len(_I["fields"]):
        _bad.append("d_nfield")
    if int(round(float(DIRINFO["d_nlayer"]))) != _nl or _nl != int(DIR.get("n_layers", -1)):
        _bad.append("d_nlayer")
    if float(DIRINFO["d_P"]) != float(DIR["P"]) or float(_I["P"]) != float(DIR["P"]):
        _bad.append("d_P")
    if any(float(DIRINFO["d_n%d" % _n]) != float(DIR["harmonics"][_n]) for _n in range(_nl)):
        _bad.append("d_n")
    if float(DIRINFO["d_tf"]) != float(_I["t_f"]) or abs(float(ctrl.parm("dir_tf").eval()) - float(DIR["t_f"])) > 1e-12:
        _bad.append("t_f")
    if DIRINFO["d_content"] != DIR.get("content_sha256"):
        _bad.append("content")
    if _bad:
        stop_early("error: OUT_DIRTAB does not match the cfg table (%s): %s" % (",".join(_bad), DIRINFO))
    DIRINFO.update(npz=_np, npz_sha256=_sha, P=float(DIR["P"]), harmonics=DIR.get("harmonics"), set=DIR.get("set"))
'''

RUN_REPL = [
    ('TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50"', 'TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"', 1),
    ("import g50_common as GC", "import g52_common as GC", 1),
    ("import g50_table as TB", "import g52_table as TB", 1),
    (OLD_DIR, NEW_DIR, 1),
    ("GC.B50", "GC.B52", 1),
    ('"FLIP50"', '"FLIP52"', 2),
    ("/obj/G50_", "/obj/G52_", 8),
    ('"G50_FIELDS"', '"G52_FIELDS"', 1),
    ("GC.LEVEL_REGIONS_D", "GC.LEVEL_REGIONS_52", 1),
    ("x49_build.py", "x52_build.py", 1),
    ('T_WAVE = float((SF or {}).get("T", (args.get("dir") or {}).get("T", GC.T_WAVE)))', 'T_WAVE = float((SF or {}).get("T", GC.T_WAVE))', 1),
]
CHAIN_REPL = [
    ("import g50_common as GC", "import g52_common as GC", 1),
    ('RUN = GC.TOOLS + "/g50_run.py"', 'RUN = GC.TOOLS52 + "/g52_run.py"', 1),
    ('ckp = GC.B50 + "/_logs/build_check.json"', "ckp = GC.BUILD_CHECK", 1),
    ("GC.B50", "GC.B52", 2),
    ("g50_pcfg.py", "g52_pcfg.py", 2),
    ("x50_build.py", "x52_build.py", 2),
    ("場面の確かめ build_check.json の all_ok が偽", "場面の確かめ build_check52.json の all_ok が偽", 1),
]


def make(name, doc, repl):
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
    for bad in ("G50_", "import g50_common", "import g50_table", "GC.B50", "flip50\"", "GC.TOOLS +", "build_check.json\""):
        if bad in s:
            raise SystemExit("%s: %r is still in the copy" % (name, bad))
    return s


def main():
    out = {"g52_run.py": make("g50_run.py", RUN_DOC, RUN_REPL), "g52_chain.py": make("g50_chain.py", CHAIN_DOC, CHAIN_REPL)}
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
