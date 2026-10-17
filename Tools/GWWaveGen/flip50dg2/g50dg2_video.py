# -*- coding: utf-8 -*-
"""FLIP50 DG2 (AM-D22): the compare and whole-run videos of a DG2 calculation (py -3.10 -B). 2026-10-17 written new (Claude).
It imports flip50g/g50g_video.py as a module (its in-memory groove patch and label tolerance run at import; the file is unchanged), replaces
its bed wording with the DG2 variant's and runs the same g49_video2 main.
usage: py -3.10 -B g50dg2_video.py all|compare|whole <DG2 run> [g49_video2 options] [--plain]
"""
import os, sys, json

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g50dg2_common as D          # noqa: E402

D.install(D.GG)
import g50g_video as GV            # noqa: E402  flip50g (unchanged); patches at import

if __name__ == "__main__":
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(pos) < 2:
        print(__doc__); sys.exit(1)
    cfg = json.load(open(os.path.join(pos[1], "cfg.json"), encoding="utf8"))
    v, kind = D.variant_of(cfg.get("run_id"))
    if v is None:
        raise SystemExit("not a DG2 run: %s" % cfg.get("run_id"))
    g = D.params(v)
    cf = D.closed_form(g)
    GV.BED_NEW = ("海底 D19B に選んだ浅い溝 2 本 DG2-%s（軸の両側、|y| %.0f m で最も深く %.1f m、x %g〜%g m。離岸流の溝の類比で測った所ではない【選び】）"
                  % (v, cf["y_dz_max_m"], cf["dz_max_m"], g["x1"], g["x4"]))
    GV.V2.TOOL = "Tools/GWWaveGen/flip50dg2/g50dg2_video.py (g50_video / g49_video2 with the DG2-%s groove bed)" % v
    GV.GG.frozen()
    D.frozen_dg2()
    GV.V2.main()
