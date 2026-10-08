# -*- coding: utf-8 -*-
"""FLIP41：FLIP Solver の中の surfacepressure まわりの並びと式を読む（読むだけ）。"""
import hou
dop = hou.node("/obj").createNode("dopnet", "X")
fs = dop.createNode("flipsolver::2.0", "fs")
names = ["init_surfacepressure", "enable_init_surfacepressure", "match_surfacepressure", "enable_surfacetension",
         "compute_curvature", "scale_curvature", "surfacetension_blur", "projectnondivergent"]
def expr(p):
    try:
        return p.expression()
    except Exception:
        try:
            return p.unexpandedString()
        except Exception:
            return repr(p.eval())
for nm in names:
    n = fs.node(nm)
    print("==", nm, n.type().name(), "inputs:", [i.name() if i else None for i in n.inputs()], "outputs:", [o.name() for o in n.outputs()])
    for p in n.parms():
        if p.isAtDefault() and not p.parmTemplate().type() == hou.parmTemplateType.String:
            continue
        print("   ", p.name(), "=", expr(p)[:160])
# 並びを全部たどる：出力ノードから上流へ（入力 0 の鎖）
out = [n for n in fs.children() if n.isDisplayFlagSet()] if hasattr(fs.children()[0], "isDisplayFlagSet") else []
print("display", [n.name() for n in out])
def chain(n, depth=0, seen=set()):
    if n is None or n.path() in seen or depth > 400:
        return
    seen.add(n.path())
    ins = n.inputs()
    for i in ins:
        chain(i, depth + 1, seen)
    print("CH", n.name(), n.type().name(), [i.name() if i else None for i in ins])
for o in out:
    chain(o)
