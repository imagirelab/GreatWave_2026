# -*- coding: utf-8 -*-
"""P0 の診断：静かな水で数コマ進め、格子の場（surface・collision・vel・pressure）と粒子の高さを列ごとに見る（hython）。
使い方: hython p0_diag_fields.py '<JSON>'  JSON: {"parms": {...}, "frames": [1,2,6], "hip": "..."}
"""
import hou, sys, json
args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
HIP = args.get("hip", r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p0_tank.hiplc")
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/P0_SETUP/CTRL")
for k, v in args.get("parms", {"H": 0.0}).items():
    ctrl.parm(k).set(v)
for k, v in args.get("node_parms", {}).items():
    path, pn = k.rsplit("/", 1)
    hou.node(path).parm(pn).set(v)
for path in args.get("bypass", []):
    hou.node(path).bypass(True)
print("hipsave", hou.text.expandString("$_HIP_SAVEVERSION"), "running", hou.applicationVersionString())
hou.setSimulationEnabled(True)
fi = hou.node("/obj/P0_READ/surface_field")
names = args.get("fields", ["surface", "collision", "vel", "pressure"])
fi.parm("fields").set(len(names))
for i, nm in enumerate(names):
    fi.parm("objname%d" % (i + 1)).set("water"); fi.parm("fieldname%d" % (i + 1)).set(nm)
cols = args.get("cols", [70, 300, 500, 650])
ys = args.get("ys", [-61, -50, -30, -20, -10, -3, -1, 0.3])
for f in args.get("frames", [1, 2, 6, 12]):
    hou.setFrame(f)
    g = fi.geometry()
    print("== frame", f, "prims", len(g.prims()), [p.resolution() for p in g.prims()][:6])
    pn = [p.attribValue("name") if g.findPrimAttrib("name") else "?" for p in g.prims()]
    for p, nm in zip(g.prims(), pn):
        for x in cols:
            print("  %-12s x=%4d" % (nm, x), [round(p.sample(hou.Vector3(x, y, 0)), 3) for y in ys])
    sim = hou.node("/obj/P0_SIM").simulation()
    o = sim.findObject("water")
    geo = o.geometry()
    import numpy as np
    P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    for x in cols:
        m = np.abs(P[:, 0] - x) < 5
        if m.sum():
            print("  particles near x=%d: n=%d ymin=%.2f ymax=%.2f" % (x, m.sum(), P[m, 1].min(), P[m, 1].max()))
    print("  total particles", len(P))
    if f == args.get("frames", [1])[0]:
        print("  water subdata", sorted(o.subData().keys()))
        for dn in sorted(o.subData().keys()):
            pass
    for n in hou.node("/obj/P0_SIM").children():
        e = n.errors(); w = n.warnings()
        if e or w: print("  node", n.name(), e, w)
