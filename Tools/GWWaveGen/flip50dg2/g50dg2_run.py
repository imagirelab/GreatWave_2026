# -*- coding: utf-8 -*-
"""FLIP50 DG2 (AM-D22): one launch of a DG2 calculation (hython; started by g50dg2_chain.py). 2026-10-17 written new (Claude).
It installs the DG2 acceptance in memory (g50dg2_common.install: g50g_common.cfg_groove_ok accepts the DG2 ids with their own gr_*), sets
g50g_common.CORE_BOX to the variant's groove core box (smoke gate b, read by g50g_run.seed_check) and then runs the UNCHANGED
flip50g/g50g_run.py as __main__ (which patches the groove bed in memory and runs the unchanged flip50/g50_run.py; the CTRL gr_* come from the
cfg parms, the VEX reads them through chf).
usage: hython g50dg2_run.py <cfg.json>
"""
import os, sys, json, runpy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
T50G = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50g"
for _p in (HERE, T50G):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import g50dg2_common as D          # noqa: E402

D.install(D.GG)
_v, _kind = D.variant_of(json.load(open(sys.argv[1], encoding="utf8")).get("run_id"))
if _v is None:
    raise SystemExit("g50dg2_run.py: not a DG2 cfg")
D.set_core_box(_v)
runpy.run_path(T50G + "/g50g_run.py", run_name="__main__")
