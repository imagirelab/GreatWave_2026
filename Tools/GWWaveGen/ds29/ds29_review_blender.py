# -*- coding: utf-8 -*-
"""設計29 のレビュー対応：BVH の 3 次元の自己交差を 30 Hz の全コマ（τ −12〜0 s、361 コマ）で数える（ds29_review_checks.py の blender から呼ぶ）。

使い方：blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/ds29/ds29_review_blender.py -- <入力.npz> <出力.json>
入力の npz：V[コマ, 頂点, 3]（ワールド、float32）、F[面, 3]、taus、res_alt（5 mm）。
数え方は ds29_blender_qa.py の 1. と同じ：BVHTree.overlap の組から、頂点を 1 つでも共有する組を除き、両方の面の最小の高さ ≥ res_alt の組を数える
（除いた頂点を共有する組の貫通は ds29_review_checks.py の mesh で測る）。
"""
import json
import sys
import time

import numpy as np
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
NPZ, OUT = argv[0], argv[1]
z = np.load(NPZ)
V = z["V"]
F = z["F"].astype(np.int64)
taus = z["taus"]
RES_ALT = float(z["res_alt"])
polys = F.tolist()
res = dict(frames_n=int(V.shape[0]), tau_range=[float(taus[0]), float(taus[-1])], res_alt_m=RES_ALT, frames=[])
t0 = time.time()
for k in range(V.shape[0]):
    X = V[k].astype(np.float64)
    bvh = BVHTree.FromPolygons(X.tolist(), polys, all_triangles=True, epsilon=0.0)
    a, b, c = X[F[:, 0]], X[F[:, 1]], X[F[:, 2]]
    nl = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    emax = np.maximum.reduce([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)])
    resolv = nl / np.maximum(emax, 1e-15) >= RES_ALT
    pairs = bvh.overlap(bvh)
    if pairs:
        P = np.array(pairs, dtype=np.int64)
        P = P[P[:, 0] < P[:, 1]]
        Fa, Fb = F[P[:, 0]], F[P[:, 1]]
        share = np.zeros(len(P), bool)
        for i in range(3):
            for j in range(3):
                share |= Fa[:, i] == Fb[:, j]
        Qp = P[~share]
    else:
        Qp = np.zeros((0, 2), np.int64)
    Qr = Qp[resolv[Qp[:, 0]] & resolv[Qp[:, 1]]] if len(Qp) else Qp
    res["frames"].append(dict(tau=round(float(taus[k]), 4), self_intersections_all=int(len(Qp)), self_intersections=int(len(Qr)),
                              samples=[[int(p), int(q), [round(float(v), 3) for v in X[F[p]].mean(0)]] for p, q in Qr[:6]]))
    if k % 30 == 0:
        print("DS29RB frame %d/%d %.0fs" % (k, V.shape[0], time.time() - t0), flush=True)
res["frames_with_selfx"] = int(sum(1 for f in res["frames"] if f["self_intersections"]))
res["pairs_total"] = int(sum(f["self_intersections"] for f in res["frames"]))
res["frames_with_selfx_incl_slivers"] = int(sum(1 for f in res["frames"] if f["self_intersections_all"]))
res["blender_runtime_s"] = round(time.time() - t0, 1)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("DS29RB done", res["frames_with_selfx"], res["pairs_total"], flush=True)
