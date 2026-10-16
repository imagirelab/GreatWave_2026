# -*- coding: utf-8 -*-
"""FLIP50 DG1 (AM-D20): run a DG1 calculation (SMOKE50DG1 or DG1) to the end as chained launches of <= 29 min (py -3.10). 2026-10-17 new.
It runs the unchanged flip50/g50_chain.py text (sha256_16 checked against dg1_frozen.json untouched) after exact, counted replacements:
  - g50_common patched in memory (g50g_common.patch_modules(hip=True)): GC.HIP = Houdini/FLIP50/g50_tank_g.hiplc, so the gate compares
    build_check_g.json's hip_sha256 with the GROOVE hip and the cfg records its sha; module_shas add the flip50g files
  - the scene check is Unity/Build/FLIP50/_logs/build_check_g.json (all_ok, hip sha)
  - each launch is hython flip50g/g50g_run.py (the unchanged g50_run.py after the same in-memory patch)
  - gate items added (dg1_frozen.json run.launch_gate + implementation.order): dg1_frozen.json sha = .sha256 = AM-D20, cfg groove (parms gr_*,
    bed.groove, case.dg1_frozen, hip / build_check keys) = the frozen values, every 'untouched' sha (g50_tank.hiplc, build_check.json,
    plan, tables, the six cfgs, 24 modules), build_check_g built against dg1_frozen and its switch-off check ok, the start condition
    (DF1A chain ended and analysed, DF1A not PASS / no hard health, DM1A median onset 256.5 +- 10 m), and for the DG1 main run the smoke
    gates (smoke/SMOKE50DG1_.../pana/smoke_DG1.json ok)
Waits for every other hython before each launch (one heavy computation at a time).
usage: py -3.10 G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50g/g50g_chain.py <cfg.json> [--order-ok="<the user's answer>"] [--dry]
  --dry       evaluate the gate only (prints the reasons; creates no run folder, launches nothing)
  --order-ok  skips ONLY the start-condition items (a case the user decided, e.g. DF1A never launched); recorded in the run's cfg.json
"""
import os, sys, json, ast

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g50g_common as GG      # noqa: E402

SRC = GG.TOOLS50 + "/g50_chain.py"
REPL = [
    ("import g50_common as GC\nimport g46_ckpt as K\n",
     "import g50_common as GC\nimport g46_ckpt as K\nGC = GG.patch_modules(hip=True)          # DG1: groove hip + groove bed functions (in memory)\n", 1),
    ('RUN = GC.TOOLS + "/g50_run.py"', 'RUN = GG.TOOLS50G + "/g50g_run.py"', 1),
    ('    ckp = GC.B50 + "/_logs/build_check.json"', "    ckp = GG.BUILD_CHECK_G", 1),
    ("    return bad\n\n\n_bad = gate()",
     "    bad += GG.chain_gate_extra(cfg, order_ok=GG_ORDER_OK)\n    return bad\n\n\n_bad = gate()", 1),
    ('cfg["module_shas_at_chain_start"] = GC.module_shas()',
     'cfg["module_shas_at_chain_start"] = GC.module_shas()\n'
     'cfg["dg1_chain"] = dict(tool="flip50g/g50g_chain.py", order_ok=GG_ORDER_OK, order_state=GG.order_state(), untouched=GG.check_untouched())', 1),
]


def main():
    argv = sys.argv[1:]
    flags = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    if not pos:
        print(__doc__); sys.exit(1)
    unknown = set(flags) - {"dry", "order-ok"}
    if unknown:
        raise SystemExit("unknown option(s) %s" % sorted(unknown))
    GG.frozen()
    src = GG.read_source(SRC, "flip50/g50_chain.py")
    src2, info = GG.apply_replacements(src, REPL)
    order_ok = flags.get("order-ok") or None
    if flags.get("dry"):
        cfg = json.load(open(pos[0], encoding="utf8"))
        GC = GG.patch_modules(hip=True)
        tree = ast.parse(src2)
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "gate"]
        ns = dict(cfg=cfg, GC=GC, GG=GG, os=os, json=json, GG_ORDER_OK=order_ok)
        exec(compile(ast.Module(body=fn, type_ignores=[]), SRC + " [gate, DG1 patched]", "exec"), ns)
        bad = ns["gate"]()
        print(json.dumps(dict(run_id=cfg.get("run_id"), gate_ok=not bad, reasons=bad, order_ok=order_ok), ensure_ascii=False, indent=1))
        sys.exit(0 if not bad else 1)
    sys.argv = [SRC, pos[0]]
    code = compile(src2, SRC + " [DG1: patched in memory by flip50g/g50g_chain.py]", "exec")
    exec(code, {"__name__": "__main__", "__file__": SRC, "GG": GG, "GG_ORDER_OK": order_ok})


if __name__ == "__main__":
    main()
