# -*- coding: utf-8 -*-
"""番号26：K* メッシュの検査（Blender 5.2.2 ヘッドレス）。

使い方（リポジトリ根で）:
    blender --background --factory-startup --python Tools/GWWaveGen/af26_blender_qa.py -- <kstar_dir> <out_json> <eye_x> <eye_y> <eye_z> <look_x> <look_y> <look_z>

K* の OBJ（gw_wavegen_v1 の出力、Unity のワールド座標のまま）を軸の変換なしで読み、次を数える。
  1. 位相：2 面より多くの面が接する辺（非多様体）、1 面だけの辺（シートの縁。格子の外周の数と一致するか）、面のない辺、
     巻き方向が隣の面と食い違う辺（面の反転）、面積がほぼ 0 の面。
  2. 自己交差：BVH の重なり検査で、頂点を共有しない面どうしの交差の組。
  3. 座席からの射線 5 万本：座席の目の位置から、座席カメラの前方を中心とする半球へ一様に射線を出し、K* と海面（y = −0.07、M1 の参照海面の上面）
     に当てる。K* の裏面（水の側）に当たった射線＝開いた背面、K* の縁の面で縁の頂点が海面より 5 cm 以上高い所に当たった射線＝切断端、
     K* に当たらず下へ向かう射線のうち、シートの平らな海の高さ y = 0 を通る点が K* の平面図の足跡（格子の外周）の内側にある射線＝穴、
     として数える（シートの縁は海面より 7 cm 高いので、縁のすぐ外から縁の下の海面に当たる射線は穴ではない）。83/115/116 の事前検査で、合否は番号41。
面の表は Unity と同じく、各三角形の cross(b − a, c − a) の向き（平らな海で +Y）。Blender の面法線は同じ式なので、そのまま表になる。
"""
import sys
import json
import math

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
KDIR, OUT = argv[0], argv[1]
EYE = np.array([float(v) for v in argv[2:5]])
LOOK = np.array([float(v) for v in argv[5:8]])
SEA_Y = -0.07
N_RAYS = 50000
res = {"blender": bpy.app.version_string, "eye": EYE.tolist(), "look_at": LOOK.tolist(), "rays": N_RAYS, "sea_y": SEA_Y, "meshes": {}}


def fibonacci_hemisphere(n, axis):
    """axis を中心とする半球の一様な方向（黄金角の螺旋）。"""
    i = np.arange(n) + 0.5
    z = 1.0 - i / n                      # 0..1（半球）
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    phi = i * math.pi * (3.0 - math.sqrt(5.0))
    local = np.stack([r * np.cos(phi), r * np.sin(phi), z], -1)
    a = axis / np.linalg.norm(axis)
    tmp = np.array([0.0, 1.0, 0.0]) if abs(a[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(tmp, a); u /= np.linalg.norm(u)
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


for key in ("a30", "a45", "a60"):
    meta = json.load(open(KDIR + "/kstar_%s_meta.json" % key, encoding="utf-8"))
    nu, nv = meta["nu"], meta["nv"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=KDIR + "/kstar_%s.obj" % key, forward_axis='Y', up_axis='Z')
    obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
    obj.matrix_world.identity()
    me = obj.data
    V = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    # OBJ の頂点順がそのまま残っていることを確かめる（行×nu + 列）
    order_ok = len(V) == nu * nv
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    wire = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    flipped = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    expected_boundary = 2 * (nu - 1) + 2 * (nv - 1)
    bvh = BVHTree.FromBMesh(bm, epsilon=0.0)
    pairs = bvh.overlap(bvh)
    fv = [set(v.index for v in f.verts) for f in bm.faces]
    inter = [(a, b) for a, b in pairs if a < b and not (fv[a] & fv[b])]
    # 面の表の向き（平らな海の面で +Y か）
    fnz = np.array([f.normal[1] for f in bm.faces])
    fz = np.array([max(abs(v.co[1]) for v in f.verts) < 1e-6 for f in bm.faces])
    flat_down = int(np.count_nonzero(fz & (fnz < 0)))
    # 縁の頂点（格子の外周）と高さ
    bverts = set()
    for e in bm.edges:
        if len(e.link_faces) == 1:
            bverts.update(v.index for v in e.verts)
    bverts = np.array(sorted(bverts))
    b_high = bverts[V[bverts, 1] > SEA_Y + 0.05 + 0.07]      # 海面より 5 cm 以上高い縁の頂点（シートの平らな海は y = 0）
    bm.verts.ensure_lookup_table()
    edge_faces = set()
    for vi in b_high:
        for f in bm.verts[int(vi)].link_faces:
            edge_faces.add(f.index)
    # 平面図の足跡（格子の外周を順にたどった多角形、xz）
    grid = V.reshape(nv, nu, 3)
    ring = np.vstack([grid[0, :, :], grid[1:, -1, :], grid[-1, ::-1, :][1:], grid[::-1, 0, :][1:]])
    foot = ring[:, [0, 2]]
    # 射線
    fwd = LOOK - EYE
    dirs = fibonacci_hemisphere(N_RAYS, fwd)
    cls = {"wave_front": 0, "wave_back_open": 0, "cut_end": 0, "hole": 0, "sea_outside_footprint": 0, "sky": 0}
    back_samples, cut_samples, hole_samples = [], [], []
    eye_v = Vector(EYE.tolist())
    sea_pts = []
    for k in range(N_RAYS):
        d = dirs[k]
        loc, nrm, idx, dist = bvh.ray_cast(eye_v, Vector(d.tolist()))
        if idx is not None:
            if nrm.dot(Vector(d.tolist())) > 0:
                cls["wave_back_open"] += 1
                if len(back_samples) < 20:
                    back_samples.append([round(x, 3) for x in loc])
            elif idx in edge_faces:
                cls["cut_end"] += 1
                if len(cut_samples) < 20:
                    cut_samples.append([round(x, 3) for x in loc])
            else:
                cls["wave_front"] += 1
            continue
        if d[1] < 0:
            # 穴の判定は、射線がシートの平らな海の高さ（y = 0）を通る所で行う（縁の下の 7 cm のすき間から海面に当たる射線は穴に数えない）
            t = (0.0 - EYE[1]) / d[1]
            sea_pts.append(EYE + t * d)
        else:
            cls["sky"] += 1
    if sea_pts:
        sp = np.array(sea_pts)
        ins = point_in_poly(sp[:, [0, 2]], foot)
        cls["hole"] = int(ins.sum())
        cls["sea_outside_footprint"] = int((~ins).sum())
        hole_samples = sp[ins][:20].round(3).tolist()
    res["meshes"][key] = {
        "obj": "kstar_%s.obj" % key, "vertices": len(V), "faces": len(bm.faces), "vertex_order_ok": bool(order_ok),
        "nonmanifold_edges_gt2_faces": int(nonman), "boundary_edges": int(boundary), "boundary_edges_expected_grid_perimeter": int(expected_boundary),
        "wire_edges": int(wire), "flipped_inconsistent_winding_edges": int(flipped), "degenerate_faces_area_lt_1e-8": int(degenerate),
        "self_intersecting_face_pairs": len(inter), "self_intersection_samples": inter[:10],
        "flat_sea_faces_facing_down": flat_down,
        "boundary_vertices": int(len(bverts)), "boundary_vertices_above_sea_5cm": int(len(b_high)),
        "rays": cls, "open_back_face_samples": back_samples, "cut_end_samples": cut_samples, "hole_samples": hole_samples,
    }
    bm.free()
    print("QA", key, json.dumps({k: v for k, v in res["meshes"][key].items() if not k.endswith("samples")}))

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("QA_DONE", OUT)
