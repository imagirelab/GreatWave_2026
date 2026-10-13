# -*- coding: utf-8 -*-
"""FLIP46：海底の中へ入った粒子を調べる（hython。煙の試し SB と同じ設定で数十コマだけ回す。記録は smoke/leak_probe_<tag>.json）。
使い方：hython x46_leak_probe.py <cfg.json> <最後のコマ> [tag]
"""
import hou, sys, os, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
import g46_common as GC
GC.unthrottle_self()
cfg = json.load(open(sys.argv[1], encoding="utf8"))
fend = int(sys.argv[2]); tag = sys.argv[3] if len(sys.argv) > 3 else cfg["run_id"]
hou.hipFile.load(GC.HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ct = hou.node("/obj/G46_SETUP/CTRL")
for k, v in cfg["parms"].items():
    ct.parm(k).set(v)
if cfg.get("solitary_npz"):
    ct.parm("sol_npz").set(cfg["solitary_npz"])
fs = hou.node("/obj/G46_SIM/flipsolver")
fs.parm("donarrowband").set(0)
for k, v in cfg.get("solver", {}).items():
    if k not in ("donarrowband",):
        fs.parm(k).set(v)
P = {p.name(): p.eval() for p in ct.parms()}
O = np.array([P["ox"], P["oy"], P["oz"]]); VOX = P["dp"] * P["gridscale"]
hou.setSimulationEnabled(True)
dop = hou.node("/obj/G46_SIM")
col = hou.node("/obj/G46_READ/collision_field")
out = dict(frames={})
for f in range(1, fend + 1):
    hou.setFrame(f)
    if f % 6 and f != fend:
        continue
    wg = dop.simulation().findObject("water").geometry()
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    bed = GC.bed_z(Pp[:, 0], Pp[:, 2], k=P["ridge_k"], x_toe=P["ridge_x0"], s=P["ridge_s"], h0=P["h0"], on=P["ridge_on"] > 0.5)
    gap = Pp[:, 1] - bed
    bad = np.where(gap < -0.25 * VOX)[0]
    cg = col.geometry()
    cv = [p for p in cg.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)] if cg else []
    rows = []
    for i in bad[:40]:
        hp = hou.Vector3(*(Pp[i] + O))
        rows.append(dict(p=[round(float(v), 3) for v in Pp[i]], v=[round(float(v), 3) for v in V[i]], gap=round(float(gap[i]), 3),
                         coll=round(float(cv[0].sample(hp)), 3) if cv else None))
    # 衝突の場と式の SDF の比べ（尾根の上の格子の点）
    chk = []
    if cv:
        for x in (60.0, 100.0, 150.0, 200.0, 250.0, 300.0):
            for zl in (1.0, 34.0, 67.0):
                b = float(GC.bed_z(x, zl, k=P["ridge_k"], x_toe=P["ridge_x0"], s=P["ridge_s"], h0=P["h0"]))
                for dy in (-2.0, -1.0, 0.0, 1.0, 2.0):
                    chk.append(dict(x=x, zl=zl, y=b + dy, sdf_formula=dy, coll=round(float(cv[0].sample(hou.Vector3(x + O[0], b + dy + O[1], zl + O[2]))), 3)))
    out["frames"][str(f)] = dict(n=int(len(Pp)), n_below=int(len(bad)), gap_min=float(gap.min()), below=rows,
                                 hist_x=np.histogram(Pp[bad, 0], bins=[0, 88.825, 120, 160, 200, 250, 330])[0].tolist() if len(bad) else [],
                                 coll_check=chk if f == fend else None)
    print(f, len(Pp), len(bad), float(gap.min())); sys.stdout.flush()
json.dump(out, open(os.path.join(GC.B46, "smoke", "leak_probe_%s.json" % tag), "w", encoding="utf8"), indent=1)
print("done")
