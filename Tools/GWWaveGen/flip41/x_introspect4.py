import hou
dop = hou.node("/obj").createNode("dopnet", "X")
for t in ("gasmatchfield", "gasanalysis", "enablesolver", "merge", "gasfieldwrangle"):
    n = dop.createNode(t, "n_" + t)
    out = []
    for p in n.parms():
        pt = p.parmTemplate()
        items = None
        if pt.type() == hou.parmTemplateType.Menu:
            items = list(pt.menuItems())
        elif hasattr(pt, "menuItems") and pt.menuItems():
            items = list(pt.menuItems())
        out.append((p.name(), p.eval(), items[:12] if items else None))
    print(t, out[:40])
fs = dop.createNode("flipsolver::2.0", "fs")
pt = fs.parm("veltransfer").parmTemplate(); print("veltransfer", pt.menuItems())
w = dop.node("n_gasfieldwrangle"); print("bindinputmenu1", w.parm("bindinputmenu1").parmTemplate().menuItems())
