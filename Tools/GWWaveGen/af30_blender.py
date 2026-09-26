# -*- coding: utf-8 -*-
"""番号30：形成の途中のフレームのメッシュの検査（Blender 5.2.2 ヘッドレス）。

使い方（リポジトリの根で）:
    blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af30_blender.py -- \
        <frames_dir> <out_json> <eye_x> <eye_y> <eye_z> <look_x> <look_y> <look_z>

frames_dir の X_<t>.npy（af30_formation.py --stage frames、Unity のワールド座標、行 × 400 + 列の順）と tris.npy から、
各フレームのメッシュを作り、番号26修正01（af26r01_blender.py）と同じ数え方で検査する：
非多様体の辺、縁の辺（格子の外周と一致するか）、巻き方向の食い違う辺（面の反転）、面積 0 の面、BVH の重なりによる自己交差の組、
座席 v1 の目から半球へ 5 万本の射線（開いた背面・切断端・穴、仰角 60° 以上で波に当たる本数）。.blend は書かない。
"""
import sys
import os
import json
import math
import glob

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
FDIR, OUTJ = argv[:2]
EYE = np.array([float(v) for v in argv[2:5]])
LOOK = np.array([float(v) for v in argv[5:8]])
NU, NV = 400, 240
N_RAYS = 50000
SEA_Y = -0.07


def fibonacci_hemisphere(n, axis):
    i = np.arange(n) + 0.5
    z = 1.0 - i / n
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


tris = np.load(os.path.join(FDIR, "tris.npy")).astype(np.int64)
dirs = fibonacci_hemisphere(N_RAYS, LOOK - EYE)
res = {"blender": bpy.app.version_string, "eye": EYE.tolist(), "look_at": LOOK.tolist(), "rays": N_RAYS, "frames": {}}
for path in sorted(glob.glob(os.path.join(FDIR, "X_*.npy"))):
    t = float(os.path.basename(path)[2:-4])
    V = np.load(path).astype(np.float64)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new("af30")
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.ravel())
    me.loops.add(len(tris) * 3)
    me.loops.foreach_set("vertex_index", tris.ravel())
    me.polygons.add(len(tris))
    me.polygons.foreach_set("loop_start", np.arange(0, len(tris) * 3, 3))
    me.polygons.foreach_set("loop_total", np.full(len(tris), 3))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    flipped = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    bvh = BVHTree.FromBMesh(bm, epsilon=0.0)
    pairs = bvh.overlap(bvh)
    fv = [set(v.index for v in f.verts) for f in bm.faces]
    inter = [(a, b) for a, b in pairs if a < b and not (fv[a] & fv[b])]
    fnz = np.array([f.normal[1] for f in bm.faces])
    fz = np.array([max(abs(v.co[1]) for v in f.verts) < 1e-6 for f in bm.faces])
    flat_down = int(np.count_nonzero(fz & (fnz < 0)))
    bverts = set()
    for e in bm.edges:
        if len(e.link_faces) == 1:
            bverts.update(v.index for v in e.verts)
    bverts = np.array(sorted(bverts))
    b_high = bverts[V[bverts, 1] > SEA_Y + 0.05 + 0.07]
    edge_faces = set()
    for vi in b_high:
        for f in bm.verts[int(vi)].link_faces:
            edge_faces.add(f.index)
    grid = V.reshape(NV, NU, 3)
    ring = np.vstack([grid[0, :, :], grid[1:, -1, :], grid[-1, ::-1, :][1:], grid[::-1, 0, :][1:]])
    foot = ring[:, [0, 2]]
    cls = {"wave_front": 0, "wave_back_open": 0, "cut_end": 0, "hole": 0, "sea_outside_footprint": 0, "sky": 0}
    up_hits, up_total = 0, 0
    elev_max_hit = -90.0
    sea_pts = []
    eye_v = Vector(EYE.tolist())
    for k in range(N_RAYS):
        d = dirs[k]
        loc, nrm, idx, dist = bvh.ray_cast(eye_v, Vector(d.tolist()))
        elev = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
        if elev >= 60.0:
            up_total += 1
        if idx is not None:
            if elev >= 60.0:
                up_hits += 1
            elev_max_hit = max(elev_max_hit, elev)
            if nrm.dot(Vector(d.tolist())) > 0:
                cls["wave_back_open"] += 1
            elif idx in edge_faces:
                cls["cut_end"] += 1
            else:
                cls["wave_front"] += 1
            continue
        if d[1] < 0:
            tt = (0.0 - EYE[1]) / d[1]
            sea_pts.append(EYE + tt * d)
        else:
            cls["sky"] += 1
    if sea_pts:
        sp = np.array(sea_pts)
        ins = point_in_poly(sp[:, [0, 2]], foot)
        cls["hole"] = int(ins.sum())
        cls["sea_outside_footprint"] = int((~ins).sum())
    out = {"t": t, "vertices": len(V), "faces": len(bm.faces), "nonmanifold_edges_gt2_faces": int(nonman), "boundary_edges": int(boundary),
           "boundary_edges_expected_grid_perimeter": 2 * (NU - 1) + 2 * (NV - 1), "flipped_inconsistent_winding_edges": int(flipped),
           "degenerate_faces_area_lt_1e-8": int(degenerate), "self_intersecting_face_pairs": len(inter), "self_intersection_samples": inter[:10],
           "flat_sea_faces_facing_down": flat_down, "boundary_vertices_above_sea_5cm": int(len(b_high)),
           "rays": cls, "rays_elevation_ge_60deg": {"total": up_total, "hit_wave": up_hits}, "ray_hit_elevation_max_deg": elev_max_hit}
    bm.free()
    res["frames"]["%.3f" % t] = out
    print("QA", json.dumps({k: v for k, v in out.items() if not k.endswith("samples")}), flush=True)
with open(OUTJ, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
