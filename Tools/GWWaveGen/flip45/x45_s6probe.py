# -*- coding: utf-8 -*-
"""FLIP45：煙の試し S6 の調べ（hython、1〜2 分）。面の道（G45_SURF）の各段の点と三角形の数・範囲を、水の全体の粒子と薄い層の粒子で書き出す。
S6 の 1 回目（2026-10-12 10:05）で、水の全体から作った面の点が薄い層の面の 1/6 しかなかったため、どの段で減ったかを見る。流体の計算はしない。
使い方：hython x45_s6probe.py <run_id> <コマ> <L>
出力：Unity/Build/FLIP45/smoke/S6/probe_<run_id>.json
"""
import hou, sys, os, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45")
import g45_common as GC

GC.unthrottle_self()
rid, frame, L = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
rd = GC.B45 + "/smoke/" + rid
cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
hou.hipFile.load(GC.HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G45_SETUP/CTRL")
for k, v in cfg["parms"].items():
    if ctrl.parm(k) is not None:
        ctrl.parm(k).set(v)
bg = sorted([p for p in os.listdir(rd) if p.startswith("table_") and p.endswith(".bgeo.sc")])
if bg:
    ctrl.parm("table_file").set(rd + "/" + bg[-1])
ctrl.parm("ckpt").set(rd + "/ckpt"); ctrl.parm("ckpt_on").set(1); ctrl.parm("ckpt_every").set(100000)
hou.node("/obj/G45_SIM/flipsolver").parm("donarrowband").set(0)
hou.setSimulationEnabled(True)
hou.setFrame(frame)
sf = hou.node("/obj/G45_READ/surface_field").geometry()
v = [p for p in sf.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)][0]
a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32)
out = dict(run=rid, frame=frame, L=L, surface_field=dict(min=float(a.min()), max=float(a.max()), p01=float(np.percentile(a, 1)), res=list(v.resolution())))
O = np.array([cfg["parms"]["ox"], cfg["parms"]["oy"], cfg["parms"]["oz"]])
names = ["particles", "layer_and_mirror", "fluid_surface", "cut_symmetry", "triangles", "crop", "OUT_SURF"]
for lm in (0.0, L):
    ctrl.parm("surf_layer_m").set(lm)
    rec = {}
    for nm in names:
        g = hou.node("/obj/G45_SURF/" + nm).geometry()
        P = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3) - O if g.intrinsicValue("pointcount") else np.zeros((0, 3))
        rec[nm] = dict(points=int(g.intrinsicValue("pointcount")), prims=int(g.intrinsicValue("primitivecount")),
                       ymin=float(P[:, 1].min()) if len(P) else None, ymax=float(P[:, 1].max()) if len(P) else None,
                       y_hist=np.histogram(P[:, 1], bins=[-25, -15, -10, -5, -2, 0, 2, 5, 10])[0].tolist() if len(P) else None,
                       errors=[str(e)[:200] for e in hou.node("/obj/G45_SURF/" + nm).errors()])
    out["layer_%g" % lm] = rec
pfs = hou.node("/obj/G45_SURF/fluid_surface")
out["pfs_parms"] = {p.name(): p.eval() for p in pfs.parms() if p.name() in ("surfmethod", "particlesep", "voxelsize", "influenceradius", "surfacedistance",
                                                                                "conversion", "adaptivity", "docontainer", "closedcontainer", "dobbox",
                                                                                "dosurfunion", "surferosion", "minvoxelradius")}
os.makedirs(GC.B45 + "/smoke/S6", exist_ok=True)
json.dump(out, open(GC.B45 + "/smoke/S6/probe_%s.json" % rid, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:3000])
