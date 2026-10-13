# -*- coding: utf-8 -*-
"""FLIP45：場面を作る前の確かめ（hython、数秒）。節の引数の名前と hou.Volume の関数の名前を書き出すだけ。流体の計算はしない。
出力：Unity/Build/FLIP45/smoke/probe/probe_nodes.txt"""
import hou, sys
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP45/smoke/probe/probe_nodes.txt"
lines = ["houdini " + hou.applicationVersionString()]
lines.append("hou.Volume methods: " + ", ".join(m for m in dir(hou.Volume) if not m.startswith("_")))
lines.append("hou.Geometry create*: " + ", ".join(m for m in dir(hou.Geometry) if "olume" in m or m.startswith("create")))
geo = hou.node("/obj").createNode("geo", "probe")
for t in ["dopimport", "dopimportfield::2.0", "clip", "divide", "normal", "particlefluidsurface", "attribtransfer", "file", "volume", "volumewrangle", "convertvdb", "vdbfrompolygons"]:
    try:
        n = geo.createNode(t)
        lines.append("== %s (%s)" % (t, n.type().nameWithCategory()))
        for p in n.parms():
            try:
                tpl = p.parmTemplate()
                menu = ""
                if tpl.type() == hou.parmTemplateType.Menu:
                    menu = " menu: " + "; ".join("%s=%s" % (a, b) for a, b in zip(tpl.menuItems(), tpl.menuLabels()))
                lines.append("  %s [%s] = %r%s" % (p.name(), tpl.label(), p.eval(), menu))
            except Exception as e:
                lines.append("  %s err %s" % (p.name(), e))
    except Exception as e:
        lines.append("== %s FAILED %s" % (t, e))
dop = hou.node("/obj").createNode("dopnet", "pdop")
for t in ["flipobject", "flipsolver::2.0", "gasfieldwrangle", "geometrywrangle"]:
    n = dop.createNode(t)
    lines.append("== %s (%s)" % (t, n.type().nameWithCategory()))
    for p in n.parms():
        nm = p.name()
        if any(s in nm for s in ("close", "limit", "kill", "collide", "waterline", "boundary", "reseed", "particlesep", "gridscale", "dynamicresize", "bindclass", "export", "vex_precision", "field", "surface", "narrow", "explicit", "cache")):
            lines.append("  %s [%s] = %r" % (nm, p.parmTemplate().label(), p.eval()))
lines.append("dopnet parms: " + ", ".join(p.name() for p in dop.parms() if "cache" in p.name() or "start" in p.name() or "time" in p.name().lower()))
open(OUT, "w", encoding="utf8").write("\n".join(lines))
print("wrote", OUT, len(lines))
