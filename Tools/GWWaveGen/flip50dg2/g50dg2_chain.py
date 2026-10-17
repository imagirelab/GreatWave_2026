# -*- coding: utf-8 -*-
"""FLIP50 DG2 (AM-D22): run a DG2 calculation (SMOKE50DG2<v>, DG2<v>, a DD3 of DG2<v> or a DG2<v> re-record) to the end as chained launches
(py -3.10). 2026-10-17 written new (Claude).
It runs flip50g/g50g_chain.py's main() in memory (which runs the unchanged flip50/g50_chain.py text, sha-checked) with two changes:
  - g50dg2_common.install(): g50g_common.cfg_groove_ok accepts the DG2 ids of dg2_frozen.json with their own gr_* values, and
    chain_gate_extra adds the DG2 gate items (dg2_frozen + AM-D22, DG1 finished with Q80 not met, the user's opt-in, the hython bed check,
    the numpy self-checks, the DG2 smoke gates for the main run); every DG1 gate item stays (build_check_g, untouched, order, ...)
  - each launch is hython flip50dg2/g50dg2_run.py (the same install + the variant's smoke core box, then the unchanged flip50g/g50g_run.py)
DG1 and DG1 re-records are refused here (flip50g/g50g_chain.py, flip50g2/g50g2_cont.py chain).
usage: py -3.10 g50dg2_chain.py <cfg.json> [--dry]    (--dry: evaluate the gate only; no run folder, nothing launched)
"""
import os, sys, json

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g50dg2_common as D          # noqa: E402


def main(argv):
    pos = [a for a in argv if not a.startswith("--")]
    dry = "--dry" in argv
    unknown = [a for a in argv if a.startswith("--") and a != "--dry"]
    if not pos or unknown:
        print(__doc__); return 1
    cfg = json.load(open(pos[0], encoding="utf8"))
    v, kind = D.variant_of(cfg.get("run_id"))
    if v is None:
        raise SystemExit("%s is not a DG2 run id (DG1: flip50g/g50g_chain.py; DG1 re-records: flip50g2/g50g2_cont.py chain)" % cfg.get("run_id"))
    D.install(D.GG)
    D.set_core_box(v)
    import g50g_chain as GCH
    i = [j for j, r in enumerate(GCH.REPL) if r[0] == 'RUN = GC.TOOLS + "/g50_run.py"']
    if len(i) != 1:
        raise SystemExit("g50g_chain.REPL has no unique RUN replacement")
    GCH.REPL[i[0]] = ('RUN = GC.TOOLS + "/g50_run.py"', 'RUN = %r' % (HERE + "/g50dg2_run.py"), 1)
    sys.argv = [GCH.__file__, pos[0]] + (["--dry"] if dry else [])
    GCH.main()
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
