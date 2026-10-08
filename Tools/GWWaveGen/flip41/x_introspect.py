# -*- coding: utf-8 -*-
"""FLIP41：Houdini の FLIP Solver の中で surfacepressure がどこで作られ使われるか、Static Object の動く衝突の項目を調べる（読むだけ）。"""
import hou
dop = hou.node("/obj").createNode("dopnet", "X")
fs = dop.createNode("flipsolver::2.0", "fs")
print("inputs", fs.inputLabels())
names = [p.name() for p in fs.parms()]
print("surf parms", [n for n in names if "surf" in n.lower() or "tension" in n.lower() or "press" in n.lower()])
print("coll parms", [n for n in names if "coll" in n.lower()])
print("vel parms", [n for n in names if "vel" in n.lower()][:60])
try:
    fs.allowEditingOfContents()
except Exception as e:
    print("allowEditing", e)
for n in fs.allSubChildren():
    ps = []
    for p in n.parms():
        try:
            v = p.unexpandedString() if p.parmTemplate().type() == hou.parmTemplateType.String else None
        except Exception:
            v = None
        if v and ("surfacepressure" in v or "surfacetension" in v.lower()):
            ps.append((p.name(), v[:120]))
    if ps or "surfacepress" in n.name().lower() or "tension" in n.name().lower():
        print("NODE", n.path(), n.type().name(), ps[:8])
so = dop.createNode("staticobject", "so")
print("static parms", [p.name() for p in so.parms()][:120])
proj = [n for n in fs.allSubChildren() if n.type().name().startswith("gasprojectnondivergentvariational")]
for n in proj:
    print("PROJ", n.path(), n.type().name())
    for p in n.parms():
        if any(s in p.name().lower() for s in ("surf", "press", "coll", "solid", "weight", "stress")):
            try:
                print("   ", p.name(), repr(p.eval())[:80], p.unexpandedString()[:80] if p.parmTemplate().type() == hou.parmTemplateType.String else "")
            except Exception as e:
                print("   ", p.name(), "?")
