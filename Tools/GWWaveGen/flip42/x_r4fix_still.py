# -*- coding: utf-8 -*-
"""FLIP42 R4fix：静かな水槽（造波なし）を数コマだけ走らせ、水が落ちるかと DOP の場（大きさ・値）を出す（hython、途中保存なし、場面は保存しない）。
hython x_r4fix_still.py '<JSON>'
JSON: {"cfg": cfg.json のパス, "ctrl": {CTRL の上書き}, "solver": {FLIP Solver の上書き}, "fobj": {FLIP Object の上書き},
       "static": {Static Object の上書き}, "nf": コマ数, "fields": 1 なら場の値も出す, "py": 場面を変える Python の文（任意）}
造波は relax_g = 0 で止める（ctrl で上書きしない限り）。"""
import hou, json, sys, time
import numpy as np
A = json.loads(sys.argv[1])
cfg = json.load(open(A["cfg"], encoding="utf8"))
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G_SETUP/CTRL")
P = dict(cfg["parms"]); P["relax_g"] = 0.0
P.update(A.get("ctrl", {}))
for k, v in P.items():
    ctrl.parm(k).set(v)
ctrl.parm("ckpt_on").set(0)
fs = hou.node("/obj/G_SIM/flipsolver")
fs.parm("donarrowband").set(0)
for k, v in A.get("solver", {}).items():
    fs.parm(k).set(v)
fo = hou.node("/obj/G_SIM/water")
for k, v in A.get("fobj", {}).items():
    fo.parm(k).set(v)
so = hou.node("/obj/G_SIM/seabed")
for k, v in A.get("static", {}).items():
    so.parm(k).set(v)
if A.get("py"):
    exec(A["py"])
print("RUN", json.dumps({k: A.get(k) for k in ("ctrl", "solver", "fobj", "static", "py")}, ensure_ascii=True))
hou.setSimulationEnabled(True)
Lx = float(P["Lx"])
NF = int(A.get("nf", 6))


FN = tuple(A.get("fn", ["surface", "collision", "collisionweights", "pressure", "vel", "divergence", "surfaceweights"]))
rdn = hou.node("/obj").createNode("geo", "R4FIX_FIELDS")
for c in rdn.children():
    c.destroy()
FI = {}
for nm in FN:
    q = rdn.createNode("dopimportfield::2.0", "f_" + nm)
    q.parm("doppath").set("/obj/G_SIM")
    q.parm("fields").set(1)
    q.parm("objname1").set("water")
    q.parm("fieldname1").set(nm)
    FI[nm] = q


def finfo(nm, values=True):
    try:
        g = FI[nm].geometry()
    except Exception as e:
        return {"err": str(e)[:100]}
    if g is None:
        return None
    out = {}
    vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
    for i, v in enumerate(vols[:3]):
        r = v.resolution()
        p0 = v.indexToPos((0, 0, 0)); p1 = v.indexToPos((1, 1, 1))
        if A.get("exact"):
            bb = v.boundingBox()
            e = dict(res=list(r), p0=[repr(c) for c in p0], d=[repr(p1[j] - p0[j]) for j in range(3)],
                     bmin=[repr(c) for c in bb.minvec()], bmax=[repr(c) for c in bb.maxvec()])
        else:
            e = dict(res=list(r), p0=[round(c, 4) for c in p0], d=[round(p1[j] - p0[j], 5) for j in range(3)])
        if values and r[0] * r[1] * r[2] < 4e8:
            try:
                a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32)
                e.update(min=round(float(a.min()), 5), max=round(float(a.max()), 5), mean=round(float(a.mean()), 6), nneg=int((a < 0).sum()), npos=int((a > 0).sum()), n=int(a.size))
            except Exception as ex:
                e["verr"] = str(ex)[:80]
        out["c%d" % i] = e
    return out


t_all = time.time()
for f in range(1, NF + 1):
    t0 = time.time()
    hou.setFrame(f)
    sim = hou.node("/obj/G_SIM").simulation()
    obj = sim.findObject("water")
    dt = time.time() - t0
    errs = []
    for n in hou.node("/obj/G_SIM").allSubChildren():
        try:
            if n.errors():
                errs.append((n.path(), [x[:100] for x in n.errors()]))
        except Exception:
            pass
    wg = obj.geometry()
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    mid = (Pp[:, 0] > 0.2 * Lx) & (Pp[:, 0] < 0.8 * Lx)
    sp = np.sqrt((V.astype(np.float64)**2).sum(1)); im = int(np.argmax(sp))
    print("frame %d dt %.1f pts %d mid ymax %.3f ymin %.3f vy_mean %.4f vy_min %.4f vy_max %.4f | all |v|max %.4f at (%.2f, %.2f, %.2f) n|v|>0.1 %d err %s" % (
        f, dt, len(Pp), Pp[mid, 1].max(), Pp[mid, 1].min(), V[mid, 1].mean(), V[mid, 1].min(), V[mid, 1].max(),
        sp[im], Pp[im, 0], Pp[im, 1], Pp[im, 2], int((sp > 0.1).sum()), errs))
    if A.get("fields") and (f <= 2 or f == NF):
        for nm in FN:
            fi = finfo(nm)
            if fi:
                print("   ", nm, json.dumps(fi))
    sys.stdout.flush()
    if V[mid, 1].mean() < -1.0:
        print("FREE FALL"); break
print("TOTAL %.1f s" % (time.time() - t_all))
