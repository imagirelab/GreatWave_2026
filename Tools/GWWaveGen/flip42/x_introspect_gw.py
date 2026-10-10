# -*- coding: utf-8 -*-
"""FLIP42：Geometry Wrangle（DOP）の bindclass の選び方を調べる（読むだけ）。"""
import hou
dop = hou.node("/obj").createNode("dopnet", "X")
gw = dop.createNode("geometrywrangle", "gw")
p = gw.parm("bindclass")
print("bindclass", p.eval(), p.menuItems(), p.menuLabels())
for nm in ("bindgeo", "usetimestep", "vex_precision"):
    q = gw.parm(nm)
    try:
        print(nm, q.eval(), q.menuItems())
    except Exception:
        print(nm, q.eval())
gf = dop.createNode("gasfieldwrangle", "gf")
q = gf.parm("vex_precision")
print("gf precision", q.eval() if q else None, q.menuItems() if q else None)
