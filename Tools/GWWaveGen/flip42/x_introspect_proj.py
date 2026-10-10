# -*- coding: utf-8 -*-
"""FLIP42：FLIP Solver の圧力の解き方のパラメーターを一覧にする（hython、読むだけ）。"""
import hou
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
pn = hou.node("/obj/G_SIM/flipsolver/projectnondivergent")
print(pn.type().name())
for p in pn.parms():
    try:
        v = p.eval()
    except Exception as e:
        v = "?"
    rv = p.rawValue() if hasattr(p, "rawValue") else ""
    print(p.name(), "|", p.description(), "|", v, "|", str(rv)[:80])
