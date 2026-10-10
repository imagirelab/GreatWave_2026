# -*- coding: utf-8 -*-
"""FLIP42：R4 で圧力が効かない原因を調べる。DOP の水の場（surface・collision・pressure・vel）の大きさと値を数コマ出す（hython、読むだけ）。"""
import hou, json, sys
import numpy as np
cfg = json.load(open(sys.argv[1], encoding="utf8"))
over = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
NF = int(sys.argv[3]) if len(sys.argv) > 3 else 3
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G_SETUP/CTRL")
for k, v in cfg["parms"].items():
    ctrl.parm(k).set(v)
fs = hou.node("/obj/G_SIM/flipsolver")
fs.parm("donarrowband").set(0)
for k, v in over.items():
    fs.parm(k).set(v)
ctrl.parm("ckpt_on").set(0)
hou.setSimulationEnabled(True)
Lx = cfg["parms"]["Lx"]
for f in range(1, NF + 1):
    if f == 1:
        pass
    hou.setFrame(f)
    obj = hou.node("/obj/G_SIM").simulation().findObject("water")
    print("frame", f)
    for name in ("surface", "collision", "pressure", "vel", "divergence", "collisionweights", "surfaceweights"):
        d = obj.findSubData(name)
        if d is None:
            print("  ", name, "none"); continue
        try:
            o = d.options()
            fn = o.fieldNames()
            print("  ", name, {k: o.field(k) for k in fn if k in ("div", "divsize", "size", "center", "uniformdiv", "voxelsize", "twod", "border", "totalvoxels", "voxelplane", "usefp16", "position")})
        except Exception as e:
            print("  ", name, "err", str(e)[:120])
    sys.stdout.flush()
