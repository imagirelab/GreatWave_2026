# -*- coding: utf-8 -*-
"""P0 の診断 3：いちばん小さい DOP の FLIP（箱の水が閉じた箱の底に座る）で、水が落ちずに止まるかを見る（hython）。
引数の JSON: {"nb": 0|1, "frames": [..]}"""
import hou, sys, json
import numpy as np
args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
src = obj.createNode("geo", "SRC")
bx = src.createNode("box"); bx.parm("sizex").set(20); bx.parm("sizey").set(10); bx.parm("sizez").set(4); bx.parm("ty").set(-5)
fs_ = src.createNode("flipsource"); fs_.setInput(0, bx)
for nm, v in (("particlesep", 0.25),):
    if fs_.parm(nm) is not None: fs_.parm(nm).set(v)
out = src.createNode("null", "OUT"); out.setInput(0, fs_)
dop = obj.createNode("dopnet", "SIM")
fo = dop.createNode("flipobject", "water"); fo.parm("objname").set("water")
fo.parm("particlesep").set(0.25); fo.parm("soppath").set(out.path()); fo.parm("closedends").set(1); fo.parm("closeypos").set(0)
sol = dop.createNode("flipsolver::2.0", "flipsolver"); sol.setInput(0, fo)
sol.parm("dynamicresize").set(0)
sol.parm("limit_sizex").set(20); sol.parm("limit_sizey").set(14); sol.parm("limit_sizez").set(4); sol.parm("limit_ty").set(-3)
if args.get("nb"): sol.parm("donarrowband").set(1)
gr = dop.createNode("gravity"); gr.setInput(0, sol)
o = dop.createNode("output"); o.setInput(0, gr); o.setDisplayFlag(True)
rd = obj.createNode("geo", "RD")
fi = rd.createNode("dopimportfield::2.0"); fi.parm("doppath").set(dop.path()); fi.parm("fields").set(3)
for i, nm in enumerate(["collision", "pressure", "vel"]):
    fi.parm("objname%d" % (i + 1)).set("water"); fi.parm("fieldname%d" % (i + 1)).set(nm)
print("flipsource parms:", [p.name() for p in fs_.parms()][:30])
hou.setSimulationEnabled(True)
for f in args.get("frames", [2, 6, 24]):
    hou.setFrame(f)
    g = fi.geometry()
    for p in g.prims():
        nm = p.attribValue("name") if g.findPrimAttrib("name") else "?"
        a = np.frombuffer(p.allVoxelsAsString(), dtype=np.float32)
        print(f, nm, p.resolution(), "min %.3f max %.3f" % (a.min(), a.max()))
    geo = dop.simulation().findObject("water").geometry()
    P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    print(f, "particles", len(P), "ymin %.2f ymax %.2f" % (P[:, 1].min(), P[:, 1].max()), [str(e) for e in sol.errors()], [str(w) for w in sol.warnings()][:2])
