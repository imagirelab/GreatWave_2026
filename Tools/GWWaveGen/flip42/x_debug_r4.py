# -*- coding: utf-8 -*-
"""FLIP42：R4（粒子 0.177 m）が 2 コマ目で水面の場を返さなかった原因を調べる（hython）。途中保存はしない。"""
import hou, json, sys, time
cfg = json.load(open(sys.argv[1] if len(sys.argv) > 1 else r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R4/cfg.json", encoding="utf8"))
NF = int(sys.argv[2]) if len(sys.argv) > 2 else 3
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G_SETUP/CTRL")
for k, v in cfg["parms"].items():
    ctrl.parm(k).set(v)
fs = hou.node("/obj/G_SIM/flipsolver")
fs.parm("donarrowband").set(0)
for k, v in (json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}).items():
    fs.parm(k).set(v); print("set", k, v)
ctrl.parm("ckpt_on").set(0)
hou.setSimulationEnabled(True)
fi = hou.node("/obj/G_READ/surface_field")
for f in range(1, NF + 1):
    t0 = time.time()
    hou.setFrame(f)
    try:
        g = fi.geometry()
    except Exception as e:
        g = None; print("geometry exception", e)
    print("frame", f, "dt %.1f" % (time.time() - t0), "geo", g is not None, "errors", fi.errors(), "warnings", fi.warnings()[:3])
    for n in hou.node("/obj/G_READ").allSubChildren():
        if n.errors():
            print("  node error", n.path(), n.errors())
    dop = hou.node("/obj/G_SIM")
    for n in dop.allSubChildren():
        if n.errors():
            print("  dop error", n.path(), n.errors())
    if g is not None:
        vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
        print("  vols", len(vols), vols[0].resolution() if vols else None)
    sys.stdout.flush()
