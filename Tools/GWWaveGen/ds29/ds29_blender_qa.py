# -*- coding: utf-8 -*-
"""設計29：表示用サーフェスの Blender 5.2.2 ヘッドレスの検査（ds29_qa.py の --blender から呼ぶ。単独でも回せる）。

使い方：
    blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/ds29/ds29_blender_qa.py -- <入力.npz> <出力.json>

入力の npz（ds29_qa.py が書く）：V[コマ, 頂点, 3]（ワールド、Unity の座標のまま。軸の変換はしない＝美術優先26 の OBJ の読み方と同じ）、
F[面, 3]（面の表は Unity と同じく cross(b − a, c − a)）、taus・names、outer（外周の縁の輪の頂点の順）、inner_cat・inner_off（外周のほかの縁の輪）、
eye・look（座席 v1 の目と、射線の半球の中心）、sea_y（平らな参照海面、既定 −0.07 m）、cut_tol（0.12 m）、n_rays（5 万）、selfx（1 で自己交差を測る）。

1 コマごとに数えるもの
  1. 自己交差：BVH の重なり（BVHTree.overlap）で、頂点を共有しない面どうしの交差の組（美術優先26 と同じ）。判定に使う数は、
     両方の面の最小の高さが res_alt（5 mm）以上の組（包みの 16 ビットの量子化でつぶれた細い面どうしの交差は _all に記録だけ）。
  2. 座席 v1 の目から、美術優先26 と同じ半球の向き（黄金角の螺旋）の射線 5 万本。当たる順に、網・カーテン（外周の縁から平らな海までの鉛直の幕）・
     ふた（外周のほかの縁の輪をふさぐ扇）・平らな海 y = sea_y のうち最初のものを見て分ける：
       網：裏面（水の側）＝ wave_back_open（開いた背面）、継ぎ目の縁の頂点に触れる面＝ seam_cut（117）、
           外周の縁の頂点が海 + cut_tol より高い面＝ cut_end（切断端、美術優先26 と同じ）、ほか wave_front。
       カーテン：その所の縁の高さ − 海 ≤ cut_tol なら sea_outside_footprint（美術優先26 で縁の下の 7 cm のすき間を穴にしないのと同じ）、
           超えれば under_edge（持ち上がった外周の縁の下をくぐる＝縁の下のすき間）。
       ふた：hole（網の中の輪を通り抜ける＝穴）。
       海：外周の足跡（平面図）の内なら sea_over_sheet（網が平らな海より低く、海に隠れる所。周りの海の範囲の記録）、外なら sea_outside_footprint。
       何にも当たらず上向き：sky。
  3. 面の向き：単位法線の上向きの成分 < −0.1 の面の重心の 1 mm 上から真上へ射線を出し、網に当たらない面＝ down_facing_open_sky
     （上に網のない下向きの面＝裏返った面）。判定に使う数は最小の高さ ≥ res_alt の面（_all に全部）。
  5. 基準の包み（RVall・RF・RV＝基準の唇・管の頂点、subj_idx＝網の唇・管の頂点）があれば、基準の点から網への最短の 3 次元の距離
     （波頭・唇の欠落）と、網の点から基準の網への距離（はみ出し）の最大と 99%。
  4. 最初のコマで bmesh の位相（非多様体の辺、縁の辺、線だけの辺、巻き方向の食い違い、面積 0 の面）も数え、numpy の位相と照合できるようにする。
"""
import json
import math
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
NPZ, OUT = argv[0], argv[1]
z = np.load(NPZ)
V = z["V"]
F = z["F"].astype(np.int64)
taus = z["taus"]
names = [str(s) for s in z["names"]]
outer = z["outer"].astype(np.int64)
inner_cat, inner_off = z["inner_cat"].astype(np.int64), z["inner_off"].astype(np.int64)
EYE = z["eye"].astype(float)
LOOK = z["look"].astype(float)
SEA_Y = float(z["sea_y"])
CUT_TOL = float(z["cut_tol"])
N_RAYS = int(z["n_rays"])
SELFX = int(z["selfx"])
RES_ALT = float(z["res_alt"]) if "res_alt" in z.files else 0.005
HAS_REF = "RV" in z.files
if HAS_REF:
    RPOLYS = z["RF"].astype(np.int64).tolist()
    REF_IDX = z["ref_idx"].astype(np.int64)
    SUBJ_IDX = z["subj_idx"].astype(np.int64)
nv = V.shape[1]
polys = F.tolist()
inner = [inner_cat[inner_off[k]:inner_off[k + 1]] for k in range(len(inner_off) - 1)]


def fibonacci_hemisphere(n, axis):
    """美術優先26 の af26_blender_qa.py と同じ（axis を中心とする半球の一様な向き、黄金角の螺旋）。"""
    i = np.arange(n) + 0.5
    zz = 1.0 - i / n
    r = np.sqrt(np.maximum(0.0, 1.0 - zz * zz))
    phi = i * math.pi * (3.0 - math.sqrt(5.0))
    local = np.stack([r * np.cos(phi), r * np.sin(phi), zz], -1)
    a = axis / np.linalg.norm(axis)
    tmp = np.array([0.0, 1.0, 0.0]) if abs(a[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(tmp, a)
    u /= np.linalg.norm(u)
    v = np.cross(a, u)
    return local[:, 0:1] * u + local[:, 1:2] * v + local[:, 2:3] * a


def point_in_poly(pts, poly):
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), bool)
    n = len(poly)
    for k in range(n):
        x0, y0 = poly[k]
        x1, y1 = poly[(k + 1) % n]
        cond = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / np.where(y1 != y0, y1 - y0, 1e-12) + x0)
        inside ^= cond
    return inside


DIRS = fibonacci_hemisphere(N_RAYS, LOOK - EYE)
ELEV = np.degrees(np.arcsin(np.clip(DIRS[:, 1], -1, 1)))
DIRV = [Vector(d.tolist()) for d in DIRS]
EYEV = Vector(EYE.tolist())
inner_v = np.unique(inner_cat) if len(inner_cat) else np.zeros(0, np.int64)
vm_inner = np.zeros(nv, bool)
vm_inner[inner_v] = True
seam_face = vm_inner[F].any(1)
res = {"blender": bpy.app.version_string, "eye": EYE.tolist(), "look_at": LOOK.tolist(), "rays": N_RAYS, "sea_y": SEA_Y, "cut_tol": CUT_TOL,
       "label": str(z["label"]), "frames": []}

# ---- 位相（bmesh、t* に近い最後のコマ）
t0 = time.time()
me = bpy.data.meshes.new("ds29")
me.from_pydata(V[-1].astype(np.float64).tolist(), [], polys)
me.update()
bm = bmesh.new()
bm.from_mesh(me)
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()
res["topology_bmesh"] = {
    "vertices": len(bm.verts), "faces": len(bm.faces), "edges": len(bm.edges),
    "nonmanifold_edges_gt2_faces": sum(1 for e in bm.edges if len(e.link_faces) > 2),
    "boundary_edges": sum(1 for e in bm.edges if len(e.link_faces) == 1),
    "wire_edges": sum(1 for e in bm.edges if len(e.link_faces) == 0),
    "flipped_inconsistent_winding_edges": sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous),
    "degenerate_faces_area_lt_1e-8": sum(1 for f in bm.faces if f.calc_area() < 1e-8),
    "frame": names[-1], "runtime_s": 0.0}
bm.free()
bpy.data.meshes.remove(me)
res["topology_bmesh"]["runtime_s"] = round(time.time() - t0, 2)
print("DS29BQ topology", json.dumps(res["topology_bmesh"]), flush=True)

# ふた（外周のほかの縁の輪を重心からの扇でふさぐ）があるか
has_cap = any(len(lp) >= 3 for lp in inner)

for k in range(V.shape[0]):
    tf = time.time()
    X = V[k].astype(np.float64)
    fr = {"name": names[k], "tau": float(taus[k])}
    verts = X.tolist()
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=True, epsilon=0.0)
    a, b, c = X[F[:, 0]], X[F[:, 1]], X[F[:, 2]]
    n = np.cross(b - a, c - a)
    nl = np.linalg.norm(n, axis=1)
    un = n / np.maximum(nl, 1e-300)[:, None]
    area = 0.5 * nl
    emax = np.maximum.reduce([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)])
    resolv = 2 * area / np.maximum(emax, 1e-15) >= RES_ALT        # 最小の高さ ≥ 5 mm（16 ビットの量子化 1.2 mm の約 4 倍。numpy の側と同じ）
    fr["degenerate_faces_area_lt_1e-8"] = int((area < 1e-8).sum())
    # 1. 自己交差
    if SELFX:
        ts = time.time()
        pairs = bvh.overlap(bvh)
        if pairs:
            P = np.array(pairs, dtype=np.int64)
            P = P[P[:, 0] < P[:, 1]]
            Fa, Fb = F[P[:, 0]], F[P[:, 1]]
            share = np.zeros(len(P), bool)
            for i in range(3):
                for j in range(3):
                    share |= Fa[:, i] == Fb[:, j]
            Q = P[~share]
        else:
            Q = np.zeros((0, 2), np.int64)
        fr["self_intersections_all"] = int(len(Q))
        Qr = Q[resolv[Q[:, 0]] & resolv[Q[:, 1]]] if len(Q) else Q
        fr["self_intersections"] = int(len(Qr))
        fr["self_intersection_samples"] = [[int(p), int(q), [round(float(v), 3) for v in X[F[p]].mean(0)]] for p, q in Qr[:8]]
        fr["self_intersection_samples_slivers"] = [[int(p), int(q), [round(float(v), 3) for v in X[F[p]].mean(0)]] for p, q in Q[:4]]
        fr["selfx_runtime_s"] = round(time.time() - ts, 2)
    else:
        fr["self_intersections"] = None
    # 2. 座席の射線
    ob = outer
    high = np.zeros(nv, bool)
    high[ob[X[ob, 1] > SEA_Y + CUT_TOL]] = True
    cut_face = high[F].any(1)
    # カーテン：外周の縁のうち海より高い辺から海の 2 cm 下まで
    cv, cp, cedge = [], [], []
    m = len(ob)
    for i in range(m):
        p, q = X[ob[i]], X[ob[(i + 1) % m]]
        if max(p[1], q[1]) <= SEA_Y:
            continue
        base = len(cv)
        cv += [tuple(p), tuple(q), (q[0], SEA_Y - 0.02, q[2]), (p[0], SEA_Y - 0.02, p[2])]
        cp.append((base, base + 1, base + 2, base + 3))
        cedge.append(i)
    cbvh = BVHTree.FromPolygons(cv, cp, all_triangles=False, epsilon=0.0) if cp else None
    # ふた
    pbvh = None
    if has_cap:
        pv = [tuple(v) for v in verts]
        ptri = []
        for lp in inner:
            if len(lp) < 3:
                continue
            cen = X[lp].mean(0)
            ci = len(pv)
            pv.append(tuple(cen))
            for j in range(len(lp)):
                ptri.append((int(lp[j]), int(lp[(j + 1) % len(lp)]), ci))
        pbvh = BVHTree.FromPolygons(pv, ptri, all_triangles=True, epsilon=0.0)
    foot = X[ob][:, [0, 2]]
    cls = {k_: 0 for k_ in ("wave_front", "wave_back_open", "cut_end", "seam_cut", "under_edge", "hole", "sea_over_sheet",
                            "sea_outside_footprint", "sky")}
    under_small = 0
    samples = {k_: [] for k_ in ("wave_back_open", "cut_end", "seam_cut", "under_edge", "hole", "sea_over_sheet")}
    sea_pts, sea_idx = [], []
    up_total = int((ELEV >= 60.0).sum())
    up_hits = 0
    gaps = []
    for r in range(N_RAYS):
        d = DIRS[r]
        dv = DIRV[r]
        best, kind, info = math.inf, None, None
        loc, nrm, idx, dist = bvh.ray_cast(EYEV, dv)
        if idx is not None:
            best, kind, info = dist, "sheet", (loc, nrm, idx)
        if cbvh is not None:
            l2, n2, i2, d2 = cbvh.ray_cast(EYEV, dv)
            if i2 is not None and d2 < best and l2[1] >= SEA_Y:
                best, kind, info = d2, "curtain", (l2, i2)
        if pbvh is not None:
            l3, n3, i3, d3 = pbvh.ray_cast(EYEV, dv)
            if i3 is not None and d3 < best:
                best, kind, info = d3, "cap", (l3,)
        if d[1] < 0:
            dsea = (SEA_Y - EYE[1]) / d[1]
            if dsea < best:
                best, kind, info = dsea, "sea", None
        if ELEV[r] >= 60.0 and kind == "sheet":
            up_hits += 1
        if kind == "sheet":
            loc, nrm, idx = info
            if nrm.dot(dv) > 0:
                c_ = "wave_back_open"
            elif seam_face[idx]:
                c_ = "seam_cut"
            elif cut_face[idx]:
                c_ = "cut_end"
            else:
                c_ = "wave_front"
            cls[c_] += 1
            if c_ in samples and len(samples[c_]) < 12:
                samples[c_].append([round(x, 3) for x in loc] + [int(idx)])
        elif kind == "curtain":
            l2, i2 = info
            e = cedge[i2]
            p, q = X[ob[e]], X[ob[(e + 1) % m]]
            dxz = q[[0, 2]] - p[[0, 2]]
            s = float(np.clip(np.dot(np.array([l2[0], l2[2]]) - p[[0, 2]], dxz) / max(float(np.dot(dxz, dxz)), 1e-18), 0, 1))
            gap = p[1] + s * (q[1] - p[1]) - SEA_Y
            if gap <= CUT_TOL:
                cls["sea_outside_footprint"] += 1
                under_small += 1
            else:
                cls["under_edge"] += 1
                gaps.append(gap)
                if len(samples["under_edge"]) < 12:
                    samples["under_edge"].append([round(x, 3) for x in l2] + [round(float(gap), 3)])
        elif kind == "cap":
            cls["hole"] += 1
            if len(samples["hole"]) < 12:
                samples["hole"].append([round(x, 3) for x in info[0]])
        elif kind == "sea":
            sea_pts.append(EYE + best * d)
            sea_idx.append(r)
        else:
            cls["sky"] += 1
    if sea_pts:
        sp = np.array(sea_pts)
        ins = point_in_poly(sp[:, [0, 2]], foot)
        cls["sea_over_sheet"] = int(ins.sum())
        cls["sea_outside_footprint"] += int((~ins).sum())
        samples["sea_over_sheet"] = sp[ins][:12].round(3).tolist()
    fr["rays"] = cls
    fr["rays_under_edge_within_tol"] = under_small
    fr["under_edge_gap_max_m"] = round(float(max(gaps)), 3) if gaps else None
    fr["rays_elevation_ge_60deg"] = {"total": up_total, "hit_wave": up_hits}
    fr["outer_boundary_vertices_above_sea_tol"] = int(high.sum())
    fr["outer_boundary_y_range_m"] = [round(float(X[ob, 1].min()), 3), round(float(X[ob, 1].max()), 3)]
    fr["samples"] = samples
    # 3. 下を向き、上に網のない面
    dn = np.nonzero((un[:, 1] < -0.1) & (area > 1e-8))[0]
    cen = (a + b + c) / 3.0
    upv = Vector((0.0, 1.0, 0.0))
    bad = []
    for fi in dn:
        o = cen[fi]
        l4, n4, i4, d4 = bvh.ray_cast(Vector((o[0], o[1] + 1e-3, o[2])), upv)
        if i4 is None:
            bad.append(int(fi))
    bad = np.array(bad, dtype=np.int64)
    badr = bad[resolv[bad]] if len(bad) else bad
    fr["down_facing_faces"] = int(len(dn))
    fr["down_facing_open_sky_all"] = int(len(bad))
    fr["down_facing_open_sky"] = int(len(badr))
    fr["down_facing_open_sky_samples"] = [[int(fi)] + [round(float(v), 3) for v in cen[fi]] for fi in badr[:12]]
    # 4. 基準の包みとの 3 次元の距離（波頭の欠落）：基準の唇・管の頂点から網へ、網の唇・管の頂点から基準の網へ
    if HAS_REF:
        RX = z["RVall"][k].astype(np.float64)
        rbvh = BVHTree.FromPolygons(RX.tolist(), RPOLYS, all_triangles=True, epsilon=0.0)
        P = z["RV"][k].astype(np.float64)
        d1 = np.array([bvh.find_nearest(Vector(p))[3] for p in P])
        Q2 = X[SUBJ_IDX]
        d2 = np.array([rbvh.find_nearest(Vector(p))[3] for p in Q2])
        i1, i2 = int(np.argmax(d1)), int(np.argmax(d2))
        fr["ref_dev"] = {"ref_to_subject_max_m": round(float(d1.max()), 5), "ref_to_subject_p99_m": round(float(np.percentile(d1, 99)), 5),
                         "ref_to_subject_max_at_ref_vertex": int(REF_IDX[i1]), "ref_to_subject_max_xyz": [round(float(v), 3) for v in P[i1]],
                         "subject_to_ref_max_m": round(float(d2.max()), 5), "subject_to_ref_p99_m": round(float(np.percentile(d2, 99)), 5),
                         "subject_to_ref_max_at_vertex": int(SUBJ_IDX[i2]), "points": [int(len(P)), int(len(Q2))]}
    fr["runtime_s"] = round(time.time() - tf, 2)
    res["frames"].append(fr)
    print("DS29BQ", names[k], json.dumps({"rays": cls, "selfx": [fr["self_intersections"], fr.get("self_intersections_all")],
                                          "down_open": [fr["down_facing_open_sky"], fr["down_facing_open_sky_all"]], "t": fr["runtime_s"]}), flush=True)

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("DS29BQ_DONE", OUT, flush=True)
