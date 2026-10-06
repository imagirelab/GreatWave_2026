# -*- coding: utf-8 -*-
"""P3 診断（直しではない）：主役の範囲の計算の初めの数コマで、深い所の流速が粗い計算 R18 と合っているかを見る（hython）。
使い方: hython p3_diag_vel.py '<JSON parms>' f_last
出力は標準出力のみ。"""
import hou, sys, json
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip37")
HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p3_window.hiplc"
parms = json.loads(sys.argv[1]); flast = int(sys.argv[2])
nodeparms = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/P3_SETUP/CTRL")
for k, v in parms.items():
    ctrl.parm(k).set(v)
ctrl.parm("ckpt_on").set(0)
for k, v in nodeparms.items():
    hou.parm(k).set(v); print("set", k, v)
hou.setSimulationEnabled(True)
rd = hou.node("/obj/P3_READ")
fv = rd.createNode("dopimportfield::2.0", "diag_vel")
fv.parm("doppath").set("/obj/P3_SIM"); fv.parm("fields").set(4)
fv.parm("objname1").set("water"); fv.parm("fieldname1").set("vel")
fv.parm("objname2").set("water"); fv.parm("fieldname2").set("surface")
fv.parm("objname3").set("water"); fv.parm("fieldname3").set("collision")
fv.parm("objname4").set("water"); fv.parm("fieldname4").set("collisionvel")
fs_ = hou.node("/obj/P3_SIM/flipsolver")
print("solver inputs", list(fs_.inputLabels()), [c.name() if c else None for c in fs_.inputs()])
c0 = hou.node("/obj/P3_SETUP/OUT_COARSE_F0")
cl = hou.node("/obj/P3_SETUP/coarse_lerp")
YS = [-50, -35, -20, -10, -3, 3, 8]
PTS = json.loads(sys.argv[4]) if len(sys.argv) > 4 else [(360, 0), (420, 0), (450, 0), (420, -50), (420, 50)]
F0 = int(ctrl.parm("F0").eval())


def samp(geo, name, p):
    for pr in geo.prims():
        nm = pr.attribValue("name") if geo.findPrimAttrib("name") else ""
        if nm == name:
            return pr.sample(hou.Vector3(*p)) if pr.type() == hou.primType.Volume else pr.sample(hou.Vector3(*p))
    return None


def vsamp(geo, p):
    out = []
    for c in ("vel.x", "vel.y", "vel.z"):
        v = samp(geo, c, p)
        out.append(v)
    if out[0] is None:
        for pr in geo.prims():
            if pr.type() == hou.primType.VDB and "vel" in pr.attribValue("name"):
                return list(pr.voxelAtPos(hou.Vector3(*p))) if hasattr(pr, "voxelAtPos") else list(pr.sample(hou.Vector3(*p)))
    return out


for f in range(F0, flast + 1):
    hou.setFrame(f)
    g = fv.geometry()
    if f <= F0 + 1:
        print("dop field prims", [(p.type().name(), p.attribValue("name") if g.findPrimAttrib("name") else "", p.resolution()) for p in g.prims()])
    gc = cl.geometry()
    if g.findPrimAttrib("name"):
        for (x, y, z) in [(301, -40, 0), (303, -40, 0), (305, -40, 0), (307, -40, 0), (420, -40, -69), (420, -40, -65), (639, -40, 0), (420, -40, 0)]:
            cv = samp(g, "collision", (x, y, z)); vx = samp(g, "collisionvel.x", (x, y, z)); vz = samp(g, "collisionvel.z", (x, y, z))
            print("  coll@(%d,%d,%d) sdf %s cvel.x %s cvel.z %s" % (x, y, z, cv, vx, vz))
    for (x, z) in PTS:
        row = []
        for y in YS:
            vw = vsamp(g, (x, y, z)); vc = vsamp(gc, (x, y, z))
            sw = samp(g, "surface", (x, y, z)); sc = samp(gc, "surface", (x, y, z))
            row.append("y%+d: win u,w %s / R18 %s  sdf %s/%s" % (y, "%.2f,%.2f" % (vw[0], vw[2]) if vw and vw[0] is not None else "-", "%.2f,%.2f" % (vc[0], vc[2]) if vc and vc[0] is not None else "-",
                                                         "%.1f" % sw if sw is not None else "-", "%.1f" % sc if sc is not None else "-"))
        print("f=%d x=%d z=%d | " % (f, x, z) + " | ".join(row))
    sys.stdout.flush()
