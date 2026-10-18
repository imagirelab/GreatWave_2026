# -*- coding: utf-8 -*-
"""FLIP55: make f55_chain.py as an exact copy of flip52b3/g52b3_chain.py (the chain that ran DFG-2B-V) with counted string replacements only
(py -3.10 -B). 2026-10-19 written new (Claude) after flip52b3/g52b3_mkcopy.py. The source is READ ONLY: its sha256 must equal SHA below,
otherwise nothing is written; every replacement must match its expected count exactly. The copy differs from the DFG-2B-V chain ONLY in:
  - its import path names flip52b3 explicitly (the copy lives in flip55), so it still imports g52b3_common and launches the FROZEN
    flip52b3/g52b3_run.py (the runner is not copied: the A375 run uses DFG-2B-V's run loop unchanged);
  - its Houdini temp folder is Unity/Build/FLIP55/tmp_houdini (not FLIP52B3's);
  - the docstring.
The run folder follows the cfg's absolute out_root (Unity/Build/FLIP55/runs), exactly as in g52b3_chain.py. The start gate is unchanged: cfg
precheck ok, Unity/Build/FLIP52B3/_logs/build_check52b3.json all_ok + the scene sha (A375 loads DFG-2B-V's scene unchanged), the table sha, the
frozen plan named in the cfg (the FLIP55 plan) against its .sha256.
usage: py -3.10 -B f55_mkcopy.py [--check]     (--check: build in memory and compare with the file on disk; writes nothing)
"""
import os, sys, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b3/g52b3_chain.py"
SHA = "2ccf005200a28f024a74ec14750e8c4dc171d491a732fc97eb0bb7195daed444"      # = plan_DFGB4_frozen.json code_sha256 (the chain that ran DFG-2B-V)
OUT = os.path.join(HERE, "f55_chain.py")

DOC_OLD_FIRST = '"""FLIP52B3 plan DFGB4 (DFG-2B-V): run one calculation to the end as chained launches of <= 29 min (py -3.10).\n'
DOC_NEW_FIRST = ('"""FLIP55 (3D resolution of DFG-2B-V, option A375): run one calculation to the end as chained launches of <= 29 min (py -3.10).\n'
                 'GENERATED 2026-10-19 by flip55/f55_mkcopy.py from flip52b3/g52b3_chain.py (sha256 %s, not edited) by exact, counted string\n'
                 'replacements: the import path names flip52b3 (so the FROZEN flip52b3/g52b3_run.py is launched) and the Houdini temp folder is\n'
                 'Unity/Build/FLIP55/tmp_houdini. The text below is the source docstring.\n' % SHA)
REPL = [
    (DOC_OLD_FIRST, DOC_NEW_FIRST, 1),
    ("sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))",
     'sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b3")', 1),
    ('TMP = GC.B52B3 + "/tmp_houdini"', 'TMP = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP55/tmp_houdini"', 1),
]


def build():
    raw = open(SRC, "rb").read()
    h = hashlib.sha256(raw).hexdigest()
    if h != SHA:
        raise SystemExit("source %s sha256 %s differs from the frozen %s: nothing written" % (SRC, h, SHA))
    s = raw.decode("utf-8")
    for old, new, n in REPL:
        k = s.count(old)
        if k != n:
            raise SystemExit("replacement %r: %d matches, expected %d: nothing written" % (old[:60], k, n))
        s = s.replace(old, new)
    return s


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    s = build()
    if "--check" in sys.argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
        same = cur == s
        print("f55_chain.py %s" % ("same as on disk" if same else "DIFFERS from the recipe (or missing)"))
        sys.exit(0 if same else 1)
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write(s)
    print("wrote %s (sha256 %s)" % (OUT, hashlib.sha256(s.encode("utf-8")).hexdigest()))


if __name__ == "__main__":
    main()
