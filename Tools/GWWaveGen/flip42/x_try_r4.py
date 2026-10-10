# -*- coding: utf-8 -*-
"""FLIP42：R4（粒子 0.177 m）で圧力が解けるかを、数十コマだけ走らせて確かめる（hython、途中保存なし）。
hython x_try_r4.py <cfg.json> <solver の上書き JSON> <コマ数>
各コマの水面の平均（水槽の 0.2〜0.6 の範囲、一番上の水面の高さ）と、FLIP Solver の失敗を出す。"""
import hou, json, sys, time
import numpy as np
cfg = json.load(open(sys.argv[1], encoding="utf8"))
over = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
NF = int(sys.argv[3]) if len(sys.argv) > 3 else 15
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G_SETUP/CTRL")
for k, v in cfg["parms"].items():
    ctrl.parm(k).set(v)
fs = hou.node("/obj/G_SIM/flipsolver")
fs.parm("donarrowband").set(0)
for k, v in over.items():
    fs.parm(k).set(v)
ctrl.parm("ckpt_on").set(0)
import os
if os.environ.get("DOPCACHE"):
    hou.node("/obj/G_SIM").parm("cachemaxsize").set(int(os.environ["DOPCACHE"])); print("cachemaxsize", os.environ["DOPCACHE"])
print("cache", hou.node("/obj/G_SIM").parm("cacheenabled").eval() if hou.node("/obj/G_SIM").parm("cacheenabled") else None, hou.node("/obj/G_SIM").parm("cachemaxsize").eval())
hou.setSimulationEnabled(True)
fi = hou.node("/obj/G_READ/surface_field")
Lx = cfg["parms"]["Lx"]
lv0 = None
for f in range(1, NF + 1):
    t0 = time.time()
    hou.setFrame(f)
    g = fi.geometry()
    dt = time.time() - t0
    if g is None:
        print("frame", f, "NO GEOMETRY", [str(e)[:120] for e in fs.errors()]); sys.stdout.flush(); break
    vol = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)][0]
    nx, ny, nz = vol.resolution()
    a = np.frombuffer(vol.allVoxelsAsString(), dtype=np.float32).reshape(nz, ny, nx)
    p0 = vol.indexToPos((0, 0, 0)); p1 = vol.indexToPos((1, 1, 1))
    ys = p0[1] + (p1[1] - p0[1]) * np.arange(ny); xs = p0[0] + (p1[0] - p0[0]) * np.arange(nx)
    neg = a[nz // 2] < 0
    top = np.where(neg.any(0), ys[ny - 1 - np.argmax(neg[::-1, :], axis=0)], np.nan)
    m = (xs > 0.2 * Lx) & (xs < 0.6 * Lx)
    lv = float(np.nanmean(top[m]))
    lv0 = lv if lv0 is None else lv0
    wg = hou.node("/obj/G_SIM").simulation().findObject("water").geometry()
    npt = wg.intrinsicValue("pointcount")
    P = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    mid = (P[:, 0] > 0.2 * Lx) & (P[:, 0] < 0.6 * Lx)
    print("frame %d dt %.1f level %.3f (change %.3f) res %s pts %d  mid: n %d ymax %.2f ymin %.2f vy_mean %.3f vy_min %.3f err %s" % (f, dt, lv, lv - lv0, (nx, ny, nz), npt,
          mid.sum(), P[mid, 1].max(), P[mid, 1].min(), V[mid, 1].mean(), V[mid, 1].min(), [str(e)[:80] for e in fs.errors()]))
    sys.stdout.flush()
    if lv - lv0 < -0.5:
        print("FREE FALL"); break
