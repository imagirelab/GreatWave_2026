# -*- coding: utf-8 -*-
"""FLIP42：FLIP Solver 2.0 の小刻み・CFL のパラメーターの名前と入口の名前を調べる（読むだけ。場面は作らない）。"""
import hou
dop = hou.node("/obj").createNode("dopnet", "X")
fs = dop.createNode("flipsolver::2.0", "fs")
print("inputs", fs.inputLabels())
for p in fs.parms():
    n = p.name().lower()
    lab = p.parmTemplate().label()
    if any(s in n for s in ("cfl", "substep", "timescale", "step")) or "CFL" in lab:
        try:
            print("PARM", p.name(), "|", lab, "|", p.eval())
        except Exception:
            print("PARM", p.name(), "|", lab)
gw = dop.createNode("geometrywrangle", "gw")
print("geowrangle parms", [p.name() for p in gw.parms()][:60])
print("class menu", gw.parm("class").menuItems() if gw.parm("class") else None)
