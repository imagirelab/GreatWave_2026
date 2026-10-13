# -*- coding: utf-8 -*-
"""FLIP45：面を作る SOP の引数の表示名と選びの中身を読む（hython、数秒）。u_probe_nodes.py の続き。
使い方: hython u_probe_menus.py <出力 txt>
2026-10-12 進行役が書いた。"""
import sys
import hou

out = sys.argv[1]
geo = hou.node("/obj").createNode("geo", "probe")
want = {
    "particlefluidsurface": ["surfmethod", "model", "particlesep", "voxelsize", "influenceradius", "surfacedistance", "conversion",
                             "adaptivity", "dosurfunion", "surferosion", "flattengeo", "flattenplane", "flattenshape", "waterlevel",
                             "docontainer", "closedcontainer", "dobbox", "regionvoxelsize", "minvoxelradius", "resamplingiterations",
                             "dosmooth", "dofinalsmooth", "dodilate", "doerode"],
    "convertvdb": ["conversion", "adaptivity"],
    "polyreduce::2.0": ["reductiontarget", "target", "percentage", "finalcount"],
}
lines = []
for t, names in want.items():
    n = geo.createNode(t)
    lines.append("== %s" % n.type().nameWithCategory())
    for nm in names:
        p = n.parm(nm)
        if p is None:
            lines.append("  %s : (なし)" % nm)
            continue
        pt = p.parmTemplate()
        s = "  %s [%s] = %r" % (nm, pt.label(), p.eval())
        try:
            items = pt.menuItems()
            labels = pt.menuLabels()
            if items:
                s += "  menu: " + "; ".join("%s=%s" % (a, b) for a, b in zip(items, labels))
        except Exception:  # noqa
            pass
        try:
            h = pt.help()
            if h:
                s += "  help: " + h.replace("\n", " ")[:300]
        except Exception:  # noqa
            pass
        lines.append(s)
open(out, "w", encoding="utf8").write("\n".join(lines))
print("wrote", out)
