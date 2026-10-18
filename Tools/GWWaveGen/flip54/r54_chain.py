# -*- coding: utf-8 -*-
"""FLIP54 R54: run one R54 strip to the end in <= 1740-s hython launches from checkpoints (py -3.10 -B).
2026-10-18 written new (Claude, FLIP54 builder R). It runs the UNCHANGED K54 chain g54_chain.py (a byte copy of flip49/g49_chain.py with
named edits; it launches the unchanged g54_run.py) with ONE value of g54_common changed in memory of this process: BUILD_CHECK ->
Unity/Build/FLIP54/r54/_check/build_check_r54.json (written by r54_xcheck.py at dp 0.25), so the chain's gate (precheck ok, scene check
all_ok with the current hip sha256, frozen plan sha256 = the R54 plan named in the cfg) checks the R54 scene check instead of K54's.
Resume: rerunning it with the same cfg continues from the last checkpoint (g54_chain behaviour); <run>/STOP stops it before its next launch.
usage: py -3.10 -B r54_chain.py <Unity/Build/FLIP54/r54/strips/ready/<run_id>.json>
"""
import os, sys, runpy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import r54_common as RC       # noqa: E402
import g54_common as GC       # noqa: E402

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(2)
GC.BUILD_CHECK = RC.BUILD_CHECK
CHAIN = HERE + "/g54_chain.py"
print("r54_chain: g54_chain.py with the scene-check gate on %s" % GC.BUILD_CHECK, flush=True)
sys.argv = [CHAIN] + sys.argv[1:]
runpy.run_path(CHAIN, run_name="__main__")
