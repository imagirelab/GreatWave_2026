# -*- coding: utf-8 -*-
"""FLIP54 K54: write g54_run.py and g54_chain.py as BYTE COPIES of flip49/g49_run.py and flip49/g49_chain.py (FROZEN, read only) with named,
counted edits only (py -3.10 -B; no hython). 2026-10-18 written new (Claude, FLIP54 builder K), the flip52b g52b_mkcopy pattern.

Why copies: g49_run.py stops when the Fenton depth is not the fixed 17 m of FLIP49 (the K54 strips generate at h0 19 m = D19B) and writes
under Unity/Build/FLIP49; g49_chain.py starts g49_run.py and reads Unity/Build/FLIP49/_logs/build_check.json. Everything else (records, drift
stages, guards, checkpoints, launch splitting) is kept bit for bit.

usage:  py -3.10 -B g54_mkcopy.py write     (re-)write g54_run.py / g54_chain.py; refuses if the sources changed since the copy was designed
        py -3.10 -B g54_mkcopy.py check     verify that the written copies equal source + edits (exit 1 if not)
"""
import os, sys, hashlib, json

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
T49 = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49"
SRC_SHA = {"g49_run.py": None, "g49_chain.py": None}     # filled below from the files at design time (printed by `write`)

NOTE_RUN = ('"""FLIP54 K54 copy (2026-10-18, g54_mkcopy.py): g49_run.py BYTE FOR BYTE except the named edits E1-E6 (import g54_common, outputs\n'
            'Unity/Build/FLIP54/<out_root>, the Fenton depth check sf.h == h0 (the K54 strips generate at h0 19 m), stage label FLIP54).\n'
            'The original docstring follows unchanged (its FLIP49 wording describes the copied behaviour).\n"""\n')
NOTE_CHAIN = ('"""FLIP54 K54 copy (2026-10-18, g54_mkcopy.py): g49_chain.py BYTE FOR BYTE except the named edits C1-C5 (import g54_common, run\n'
              'g54_run.py, Unity/Build/FLIP54 paths, the scene check Unity/Build/FLIP54/_logs/build_check54.json written by x54_check.py).\n'
              'The original docstring follows unchanged (its FLIP49 wording describes the copied behaviour).\n"""\n')

EDITS_RUN = [
    ("E1", 'TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49"', 'TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip54"', 1),
    ("E2", "import g49_common as GC", "import g54_common as GC", 1),
    ("E3", 'ROOT = os.path.join(GC.B49, args.get("out_root", "runs"))', 'ROOT = os.path.join(GC.B54, args.get("out_root", "runs"))', 1),
    ("E4", '    if SF_ON and (abs(float(SF["h"]) - float(ctrl.parm("h0").eval())) > 1e-9 or abs(float(SF["h"]) - 17.0) > 1e-9):\n'
           '        stop_early("error: 流れ関数の波の水深 sf.h %r が h0 %r（= 17 m）と違う" % (SF["h"], ctrl.parm("h0").eval()))',
     '    if SF_ON and abs(float(SF["h"]) - float(ctrl.parm("h0").eval())) > 1e-9:\n'
     '        stop_early("error: Fenton depth sf.h %r differs from h0 %r (K54: both 19 m)" % (SF["h"], ctrl.parm("h0").eval()))', 1),
    ("E5", 'rec = dict(stage="FLIP49", run_id=rid,', 'rec = dict(stage="FLIP54", run_id=rid,', 1),
    ("E6", '"stage": "FLIP49", "run_id": rid,', '"stage": "FLIP54", "run_id": rid,', 1),
]
EDITS_CHAIN = [
    ("C1", "import g49_common as GC", "import g54_common as GC", 1),
    ("C2", 'RUN = GC.TOOLS + "/g49_run.py"', 'RUN = GC.TOOLS + "/g54_run.py"', 1),
    ("C3", 'TMP = GC.B49 + "/tmp_houdini"', 'TMP = GC.B54 + "/tmp_houdini"', 1),
    ("C4", 'R = os.path.join(GC.B49, cfg.get("out_root", "runs"))', 'R = os.path.join(GC.B54, cfg.get("out_root", "runs"))', 1),
    ("C5", '    ckp = GC.B49 + "/_logs/build_check.json"', '    ckp = GC.BUILD_CHECK', 1),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def build(src_name, edits, note):
    b = open(T49 + "/" + src_name, "rb").read()
    t = b.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"                 # g49_run.py has CRLF line ends, g49_chain.py LF: edits follow the source
    note = note.replace("\n", nl)
    log = []
    for eid, old, new, n in edits:
        old = old.replace("\n", nl); new = new.replace("\n", nl)
        c = t.count(old)
        if c != n:
            raise SystemExit("%s: edit %s expects %d occurrence(s) of %r, found %d (the source changed)" % (src_name, eid, n, old[:80], c))
        t = t.replace(old, new)
        log.append(dict(id=eid, count=c, old=old, new=new))
    head, sep, rest = t.partition('"""')          # keep the coding line, put the note before the original docstring
    if not sep:
        raise SystemExit("%s: no docstring" % src_name)
    out = head + note + sep + rest
    return out.encode("utf-8"), sha(b), log


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    res = {}
    ok = True
    for src, dst, ed, note in (("g49_run.py", "g54_run.py", EDITS_RUN, NOTE_RUN), ("g49_chain.py", "g54_chain.py", EDITS_CHAIN, NOTE_CHAIN)):
        data, s_sha, log = build(src, ed, note)
        p = HERE + "/" + dst
        if cmd == "write":
            open(p, "wb").write(data)
        same = os.path.exists(p) and open(p, "rb").read() == data
        ok = ok and same
        res[dst] = dict(source="Tools/GWWaveGen/flip49/" + src, source_sha256=s_sha, copy_sha256=sha(data), equal_to_source_plus_edits=same,
                        edits=[dict(id=e["id"], count=e["count"]) for e in log])
    res["ok"] = ok
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
