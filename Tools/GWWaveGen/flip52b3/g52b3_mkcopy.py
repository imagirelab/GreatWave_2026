# -*- coding: utf-8 -*-
"""FLIP52B3 plan DFGB4 (DFG-2B-V): make g52b3_run.py and g52b3_chain.py as exact copies of flip52/g52_run.py and flip52/g52_chain.py, and
g52b3_video.py as an exact copy of flip52b/g52b_video.py, with counted string replacements only (py -3.10 -B). 2026-10-18 written new (Claude)
by adapting flip52b2/g52b2_mkcopy.py (DFGB3, frozen, not edited). The sources are READ ONLY: their sha256 must equal the values below (flip52:
the versions that ran DFG-2 / DFG-2B-E / DFG-S-E140 / DFGB3, the same values flip52b / flip52b2 / flip52s2 recorded; flip52b/g52b_video.py: the
version that made DFG-2B-E's compare video), otherwise nothing is written. Every replacement must match its expected count exactly, so the
copies are the FLIP52 run loop and chain and the DFG-2B video except for:
  g52b3_run.py    constants / paths of FLIP52B3 (g52b3_common: Build/FLIP52B3, Houdini/FLIP52B3/g52b3_tank.hiplc = a byte copy of DFG-2B-E's scene,
                  DFG-2B-E's level regions); the N-layer numpy mirror stays flip52/g52_table.py (generic); record stage "FLIP52B3".
  g52b3_chain.py  paths of FLIP52B3 (Build/FLIP52B3, flip52b3/g52b3_run.py, _logs/build_check52b3.json); messages name x52b3_build.py /
                  g52b3_pcfg.py.
  g52b3_video.py  reads <run>/g52b3/judge_DFGB4.json and coequal_DFGB4.json (g52b3_ana), writes <run>/video/<run>_DFGB4_compare.mp4; the
                  header states the DFG-2B-V setup; the table panel adds the (3b) / (3c) / keeps-the-curl co-equal lines.
No scene builder is generated: the bed and the box are DFG-2B-E's, so x52b3_build.py copies DFG-2B-E's scene byte for byte.
usage: py -3.10 -B g52b3_mkcopy.py [--check]     (--check: build in memory and compare with the files on disk; writes nothing)
"""
import os, sys, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"
SRC_B = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b"
SHA = {"g52_run.py": "282b21e393e3ecfabb4c3774c29b60b40bccd16491519bb7e996abd51db6e17b",
       "g52_chain.py": "adc668759bf65cddf411c31e1fe8fa4861d2b8ee709a46f81e13894eb495d728",
       "g52b_video.py": "4594f5b5d8c61d04dbfe891cf2ea18061b28eca5bd83b21202783599e66131e4"}

RUN_DOC = '''"""FLIP52B3 plan DFGB4 (DFG-2B-V): run one launch of a FLIP52B3 calculation and write its records (hython; started by g52b3_chain.py).
GENERATED 2026-10-18 by flip52b3/g52b3_mkcopy.py from flip52/g52_run.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52b3/g52b3_common.py (Build/FLIP52B3, Houdini/FLIP52B3/g52b3_tank.hiplc = a byte copy of DFG-2B-E's scene,
    DFG-2B-E's level regions); the N-layer numpy mirror is flip52/g52_table.py (generic); record stage "FLIP52B3"; message 'x52b3_build.py'.
Everything else is the FLIP52 run loop (= the FLIP50 one with the N-layer OUT_DIRTAB check) that ran DFG-2 / DFG-2B-E / DFG-S-E140 / DFGB3.
usage: hython g52b3_run.py <cfg.json>  (normally py -3.10 g52b3_chain.py <cfg.json>)
output: Unity/Build/FLIP52B3/<out_root>/<run_id>/  (cfg out_root is an absolute FLIP52B3 folder)
"""'''

CHAIN_DOC = '''"""FLIP52B3 plan DFGB4 (DFG-2B-V): run one calculation to the end as chained launches of <= 29 min (py -3.10).
GENERATED 2026-10-18 by flip52b3/g52b3_mkcopy.py from flip52/g52_chain.py (sha256 %s, not edited) by exact, counted string replacements:
  - constants and paths from flip52b3/g52b3_common.py (Build/FLIP52B3, Houdini/FLIP52B3/g52b3_tank.hiplc) and flip52b3/g52b3_run.py; the start
    gate reads Unity/Build/FLIP52B3/_logs/build_check52b3.json; messages name x52b3_build.py and g52b3_pcfg.py.
Everything else is the FLIP52 / FLIP50 chain (flip46/g46_ckpt ledger; start gate: cfg precheck.ok, build check, frozen plan .sha256, table
sha256; resume from the last checkpoint; waits for every other hython before each launch; waiting time is not counted against max_hours,
which counts from this chain's own start: a new chain on a max_hours stop resumes from the last checkpoint with a fresh budget).
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b3/g52b3_chain.py <cfg.json>
"""'''

VIDEO_DOC = '''"""FLIP52B3 plan DFGB4 (DFG-2B-V): the compare video of one run (py -3.10 -B; numpy, PIL, ffmpeg). GENERATED 2026-10-18 by
flip52b3/g52b3_mkcopy.py from flip52b/g52b_video.py (sha256 %s, not edited) by exact, counted string replacements: reads
<run>/g52b3/judge_DFGB4.json and coequal_DFGB4.json (flip52b3/g52b3_ana.py) and pv53's json; writes only <run>/video (FLIP52B3) or --out
(Unity/Build/FLIP52B3/_scratch, tests). The panels are DFG-2B's (print pose hf proxy, front 3D, centre section with the print outline, crest
line, table); the header states the DFG-2B-V setup and the table adds the co-equal (3b) convergence at the most print-like instant, (3c) Hc not
lower and (4) keeps the curl. The Unity print view itself is pv53's. RED thick frame + 3 s hold = the most PRINT-LIKE instant (pv53's, else
the judge's most converged instant); ORANGE = the groups' 'max'.
usage: py -3.10 -B g52b3_video.py <run_dir> [--out=<dir>] [--t0=<s>] [--t1=<s>] [--res=<judge json> (tests)]
"""'''

RUN_REPL = [
    ('TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52"',
     'TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b3"\nsys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")', 1),
    ("import g52_common as GC", "import g52b3_common as GC", 1),
    ("GC.B52", "GC.B52B3", 1),
    ('"FLIP52"', '"FLIP52B3"', 2),
    ("GC.LEVEL_REGIONS_52", "GC.LEVEL_REGIONS_52B3", 1),
    ("x52_build.py", "x52b3_build.py", 1),
]
CHAIN_REPL = [
    ("import g52_common as GC", "import g52b3_common as GC", 1),
    ('RUN = GC.TOOLS52 + "/g52_run.py"', 'RUN = GC.TOOLS52B3 + "/g52b3_run.py"', 1),
    ("GC.B52", "GC.B52B3", 2),
    ("g52_pcfg.py", "g52b3_pcfg.py", 2),
    ("x52_build.py", "x52b3_build.py", 2),
    ("build_check52.json", "build_check52b3.json", 1),
]
VIDEO_REPL = [
    ("import g52b_common as GC", "import g52b3_common as GC", 1),
    ("import g52b_ana as GA", "import g52b3_ana as GA", 1),
    ('jl(os.path.join(rd, "g52b", "judge_DFGB.json")) or jl(os.path.join(rd, "g52b", "smoke_DFGB.json"))',
     'jl(os.path.join(rd, "g52b3", "judge_DFGB4.json"))', 1),
    ('"no g52b/judge_DFGB.json or smoke_DFGB.json in %s"', '"no g52b3/judge_DFGB4.json in %s"', 1),
    ('jl(os.path.join(rd, "g52b", "coequal_DFGB.json"))', 'jl(os.path.join(rd, "g52b3", "coequal_DFGB4.json"))', 1),
    ('''    if cset in ("DFG2B", "DFG2BE") and cset != GC.SET:      # AM-DFGB1: the label states the sea; it must be the run's sea
        raise SystemExit("run %s has sea %s but this process has %s: set G52B_SEA=%s" % (rid, cset, GC.SET, "E" if cset == "DFG2BE" else ""))''',
     '''    if cset != GC.SET:                                       # the header states the DFG-2B-V setup: it must be a DFGB4 run
        raise SystemExit("run %s has set %s, not %s (not a DFGB4 run)" % (rid, cset, GC.SET))''', 1),
    ('"%s_DFGB_compare.mp4"', '"%s_DFGB4_compare.mp4"', 1),
    ('"FLIP52B DFG-2B %s　t = %.2f s　粒子 %g m%s"', '"FLIP52B3 DFG-2B-V（DFG-2B の確かめの再計算）%s　t = %.2f s　粒子 %g m%s"', 1),
    ('''            dr.text((30, 34), ("選んだ物【選び】：DFG-2 と同じ周期・方向の海（P 28 s、T 9.33/7/5.6 s、X2 の方向 34 本）、全エネルギー = DM1A（振幅の和 %.2f m"
                               "＝凍結時の %.3f 倍、AM-DFGB1）を D19B の" % (GC.A_SUM, GC.E_SCALE) if GC.SEA == "E" else
                               "選んだ物【選び】：DFG-2 と同じ海（P 28 s、T 9.33/7/5.6 s、X2 の方向 34 本、振幅の和 6.331 m = DM1A、大きくしていない）を D19B の")
                              + "斜面の水槽で、焦点 (%.2f, 0)（水深 %.1f m）・時刻 %s s" % (GC.X_F, GC.h_of(GC.X_F), " / ".join("%g" % q for q in fo)), fill=SUB, font=XV.fnt(13))''',
     '''            dr.text((30, 34), ("選んだ物【選び】：DFG-2B-E と同じ海（X2 の方向 34 本、スペクトルのエネルギー = DM1A）と 1:10 の浜。違いは造波の表だけ："
                               "入口の帯の 5.6 s を %.3f rad 早める較正と、側の帯の 3 %% の弱め。位相の基準 (%.2f, 0)・時刻 %s s"
                               % (GC.PHI5, GC.X_F, " / ".join("%g" % q for q in fo))), fill=SUB, font=XV.fnt(13))''', 1),
    ('''                 "(3) 収束：%s（miss 中央値 %s、bar %s、valid %s）" % (c3.get("outcomes"), _n(c3.get("core_miss_median")), _n(c3.get("bar")), c3.get("valid")),''',
     '''                 "(3) 収束：%s（miss 中央値 %s、bar %s、valid %s）" % (c3.get("outcomes"), _n(c3.get("core_miss_median")), _n(c3.get("bar")), c3.get("valid")),
                 "(3b) 原画に最も近い瞬間の収束：miss 中央値 %s（bar_pl %s、DFG-2B-E 2.27）→ %s　(3c) Hc が下がらない：%s　(4) 巻きを保つ：%s" % (
                     _n((co.get("criterion_3b_convergence_at_print_like") or {}).get("pl_miss_median")),
                     _n((co.get("criterion_3b_convergence_at_print_like") or {}).get("bar_pl")),
                     (co.get("criterion_3b_convergence_at_print_like") or {}).get("ok"), (co.get("criterion_3c_hc_not_lower") or {}).get("ok"),
                     (co.get("criterion_4_keeps_curl") or {}).get("ok")),''', 1),
    ("（auto_DFGB が pv53 → coequal の後にこの動画を作る）", "（auto_DFGB4 が pv53 → coequal の後にこの動画を作る）", 1),
]


def make(name, doc, repl, src=SRC):
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
    for bad in ("import g52_common", "import g52b_common", "import g52b2_common", "import g52b_ana", "import g52b2_ana", "GC.B52 ", "GC.B52)",
                "GC.B52,", "GC.B52 +", "GC.B52B ", "GC.B52B)", "GC.B52B2", "SPEC_FLAT20", "GC.LEVEL_REGIONS_52)", "GC.SEA", "judge_DFGB.json\"",
                "judge_DFGB3", "G52B_SEA", "flip52b2/"):
        if bad in s:
            raise SystemExit("%s: %r is still in the copy" % (name, bad))
    return s


def build_all():
    return {"g52b3_run.py": make("g52_run.py", RUN_DOC, RUN_REPL), "g52b3_chain.py": make("g52_chain.py", CHAIN_DOC, CHAIN_REPL),
            "g52b3_video.py": make("g52b_video.py", VIDEO_DOC, VIDEO_REPL, src=SRC_B)}


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
