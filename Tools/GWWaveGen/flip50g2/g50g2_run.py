# -*- coding: utf-8 -*-
"""FLIP50 DG1 re-record (flip50g2, 2026-10-17): one launch (hython; started by g50g2_cont.py chain through flip50g/g50g_chain.py in memory).
It only makes g50g_common.cfg_groove_ok also accept a DG1 re-record id (cfg.restart.src_run = the DG1 main run; g50g2_cont.accept_rr) and then
runs the UNCHANGED flip50g/g50g_run.py as __main__ (which patches the groove bed in memory and runs the unchanged flip50/g50_run.py).
usage: hython g50g2_run.py <cfg.json>
"""
import os, sys, runpy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
T50G = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip50g"
for _p in (HERE, T50G):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import g50g_common as GG          # noqa: E402
import g50g2_cont as G2           # noqa: E402

G2.accept_rr(GG)
runpy.run_path(T50G + "/g50g_run.py", run_name="__main__")
