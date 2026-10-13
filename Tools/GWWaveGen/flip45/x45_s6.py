# -*- coding: utf-8 -*-
"""FLIP45 煙の試し S6：計算の中の面（記録 R5）（hython で実行、数分。計画 plan_ja.md §10.2）。
煙の試しの途中保存の 1 コマ（S2a の粒子 0.5 m と、S6b の粒子 0.25 m の小さな箱）を読み、G45_SURF の道で面を作る：
  (1) 水面の近くの薄い層の粒子（surf_layer_m = L）から作った面と、(2) 水の全体の粒子（surf_layer_m = 0）から作った面。
判定（走らせる前に決めた）：薄い層の面の点から全体の面までの距離の p99 ≤ 0.05 m。y = 0 で切って写した面の継ぎ目の隙間 ≤ 0.01 m。面を作る秒を記録。
使い方：hython x45_s6.py <run_id> <コマ> <薄い層の厚さ L（m）> [<run_id> <コマ> <L> ...]
出力：Unity/Build/FLIP45/smoke/S6/s6_<run_id>.json
"""
import hou, sys, os, json, time
import numpy as np

TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45"
sys.path.insert(0, TOOLS)
import g45_common as GC

PRIO = GC.unthrottle_self()
OUT = GC.B45 + "/smoke/S6"
os.makedirs(OUT, exist_ok=True)
args = sys.argv[1:]
for k in range(0, len(args), 3):
    rid, frame, L = args[k], int(args[k + 1]), float(args[k + 2])
    rd = GC.B45 + "/smoke/" + rid
    cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
    hou.hipFile.load(GC.HIP, suppress_save_prompt=True, ignore_load_warnings=True)
    ctrl = hou.node("/obj/G45_SETUP/CTRL")
    for kk, v in cfg["parms"].items():
        ctrl.parm(kk).set(v)
    bg = sorted([p for p in os.listdir(rd) if p.startswith("table_") and p.endswith(".bgeo.sc")])
    if bg:
        ctrl.parm("table_file").set(rd + "/" + bg[-1])
    ctrl.parm("ckpt").set(rd + "/ckpt"); ctrl.parm("ckpt_on").set(1); ctrl.parm("ckpt_every").set(100000)
    fs = hou.node("/obj/G45_SIM/flipsolver"); fs.parm("donarrowband").set(0)
    hou.setSimulationEnabled(True)
    t0 = time.time(); hou.setFrame(frame); _ = hou.node("/obj/G45_READ/surface_field").geometry(); t_load = time.time() - t0
    O = np.array([cfg["parms"]["ox"], cfg["parms"]["oy"], cfg["parms"]["oz"]])
    res = dict(run=rid, frame=frame, t=cfg["parms"]["t_off"] + (frame - 1) / 24.0, layer_m=L, load_s=round(t_load, 2), priority=PRIO)
    geos = {}
    for nm, lm in (("whole", 0.0), ("layer", L)):
        ctrl.parm("surf_layer_m").set(lm)
        node = hou.node("/obj/G45_SURF/OUT_SURF")
        t1 = time.time(); g = node.geometry(); ts = time.time() - t1
        npart = hou.node("/obj/G45_SURF/layer_and_mirror").geometry().intrinsicValue("pointcount")
        P = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O
        res[nm] = dict(surface_s=round(ts, 2), particles_used=int(npart), points=int(g.intrinsicValue("pointcount")),
                       triangles=int(g.intrinsicValue("primitivecount")), z_min=float(P[:, 2].min()) if len(P) else None)
        # 継ぎ目：三角形 1 個だけに使われる辺（面の縁）のうち、対称の面（z = 0）の近く（|z| < 0.05 m）の辺の点の |z| の最大
        tri = np.stack([np.frombuffer(g.primIntAttribValuesAsString(k), dtype=np.int32) for k in ("a", "b", "c")], 1)
        e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
        uq, cnt = np.unique(e, axis=0, return_counts=True)
        bd = uq[cnt == 1]
        near = bd[(np.abs(P[bd[:, 0], 2]) < 0.05) & (np.abs(P[bd[:, 1], 2]) < 0.05)]
        zz = np.abs(P[np.unique(near.ravel()), 2]) if len(near) else np.array([])
        res[nm]["seam"] = dict(boundary_edges_on_plane=int(len(near)), max_abs_z=float(zz.max()) if len(zz) else None,
                               gap_m=float(2 * zz.max()) if len(zz) else None)
        geos[nm] = (g.freeze(), P)
    gw, Pw = geos["whole"]; gl, Pl = geos["layer"]
    rng = np.random.default_rng(1)
    idx = rng.choice(len(Pl), size=min(4000, len(Pl)), replace=False)
    d = []
    for i in idx:
        pos = hou.Vector3(*(Pl[i] + O))
        r = gw.nearestPrim(pos)
        if r and r[0] is not None:
            d.append(r[3])
    d = np.array(d)
    res["dist_layer_to_whole"] = dict(n=int(len(d)), p50=float(np.percentile(d, 50)), p99=float(np.percentile(d, 99)), max=float(d.max()))
    res["seam"] = res["layer"]["seam"]
    res["pass"] = bool(res["dist_layer_to_whole"]["p99"] <= 0.05 and res["seam"]["gap_m"] is not None and res["seam"]["gap_m"] <= 0.01)
    res["note_ja"] = ("薄い層の面の点から全体の面までの距離（hou.Geometry.nearestPrim）の p99 ≤ 0.05 m、継ぎ目の隙間（面の縁の辺のうち z = 0 の近くの辺の点の "
                      "|z| の最大の 2 倍。読み方 R20）≤ 0.01 m")
    json.dump(res, open(OUT + "/s6_%s.json" % rid, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
