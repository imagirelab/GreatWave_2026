# -*- coding: utf-8 -*-
"""FLIP42：R4 の設定で 2 コマ動かし、場面の全部のノードの誤りと警告、海底の体積の大きさを出す（hython、読むだけ）。"""
import hou, json, sys
cfg = json.load(open(sys.argv[1], encoding="utf8"))
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G_SETUP/CTRL")
for k, v in cfg["parms"].items():
    ctrl.parm(k).set(v)
hou.node("/obj/G_SIM/flipsolver").parm("donarrowband").set(0)
ctrl.parm("ckpt_on").set(0)
hou.setSimulationEnabled(True)
for f in (1, 2, 3):
    hou.setFrame(f)
    print("frame", f)
    for n in hou.node("/obj").allSubChildren():
        try:
            e = n.errors(); w = n.warnings()
        except Exception:
            continue
        if e or w:
            print("  ", n.path(), "E:", [x[:150] for x in e], "W:", [x[:150] for x in w])
    for n in hou.node("/obj/G_SETUP").children():
        try:
            g = n.geometry()
        except Exception:
            g = None
        if g is not None and f == 1:
            vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
            if vols:
                print("   vol", n.path(), [v.resolution() for v in vols[:2]], g.boundingBox())
            else:
                print("   geo", n.path(), "pts", len(g.points()) if len(g.points()) < 10**8 else "many", g.boundingBox())
    sys.stdout.flush()
