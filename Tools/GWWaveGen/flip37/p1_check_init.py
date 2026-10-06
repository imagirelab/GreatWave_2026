# -*- coding: utf-8 -*-
"""P1：hot start の初めの水面と流速を、計算を走らせずに確かめる（SOP だけを cook。hython）。
使い方: hython p1_check_init.py '<parms JSON>'"""
import hou, sys, json, time
import numpy as np
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p1_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/P1_SETUP/CTRL")
for k, v in json.loads(sys.argv[1]).items():
    ctrl.parm(k).set(v)
for nm in ("OUT_PARTICLES", "OUT_SURFACE_VDB", "OUT_VEL_VDB"):
    t0 = time.time(); g = hou.node("/obj/P1_SETUP/" + nm).geometry(); print(nm, "cook %.1fs" % (time.time() - t0), len(g.points()), len(g.prims()))
g = hou.node("/obj/P1_SETUP/water_mesh").geometry()
P = np.array(g.pointFloatAttribValuesAsString("P") and np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32)).reshape(-1, 3)
top = P[(P[:, 2] < 0) & (P[:, 1] > -30)]
o = np.argsort(top[:, 0]); top = top[o]
xs = np.arange(0, 806, 20.0)
print("eta(x):", " ".join("%d:%.1f" % (x, np.interp(x, top[:, 0], top[:, 1])) for x in xs))
gv = hou.node("/obj/P1_SETUP/OUT_VEL_VDB").geometry()
vp = [p for p in gv.prims() if p.attribValue("name") == "vel.x"][0] if gv.findPrimAttrib("name") else gv.prims()[0]
print("u at y=0:", " ".join("%d:%.1f" % (x, vp.sample(hou.Vector3(x, -0.5, 0))) for x in xs[::2]))
