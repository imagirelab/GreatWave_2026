# -*- coding: utf-8 -*-
"""番号26修正01：K* メッシュの検査と、参照モデル（Q5）との並べ図（Blender 5.2.2 ヘッドレス）。

使い方（リポジトリ根で）:
    blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26r01_blender.py -- \
        <kstar_new_dir> <kstar_old_dir> <out_dir> <views_json> <eye_x> <eye_y> <eye_z> <look_x> <look_y> <look_z> [<ref_obj> <align_json> <ref_selected_world.npy>]

1. 検査（26修正01 の K* a45）：番号26 の af26_blender_qa.py と同じ数え方。非多様体の辺、縁の辺（格子の外周と一致するか）、面の反転、面積 0 の面、
   BVH の重なりによる自己交差の組、座席 v1 の目から半球へ 5 万本の射線（開いた背面・切断端・穴）。
2. 参照モデルとの比較（引数があるときだけ。記録のみ）：参照モデルの選んだ頂点から K*（CP1 と 26修正01）の面までの最短距離の統計と、
   参照モデル（解B）・CP1 の K* 45°・26修正01 の K* を、座席 v1・側面・背面の同じ機位から Workbench で描いた図。
   参照モデルの OBJ は読むだけで保存しない（.blend も書かない）。座標は Unity (x, y, z) → Blender (x, z, y) で描く。
"""
import sys
import os
import json
import math
import shutil
import tempfile

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
KNEW, KOLD, OUT, VIEWS = argv[:4]
EYE = np.array([float(v) for v in argv[4:7]])
LOOK = np.array([float(v) for v in argv[7:10]])
REF = argv[10] if len(argv) > 12 else None
ALIGN = argv[11] if len(argv) > 12 else None
SELNPY = argv[12] if len(argv) > 12 else None
os.makedirs(OUT, exist_ok=True)
TMPR = tempfile.mkdtemp(prefix="af26r01_cmp_")
SEA_Y = -0.07
N_RAYS = 50000
res = {"blender": bpy.app.version_string, "eye": EYE.tolist(), "look_at": LOOK.tolist(), "rays": N_RAYS, "sea_y": SEA_Y, "meshes": {}}


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


def qa(kdir, key):
    meta = json.load(open(os.path.join(kdir, "kstar_%s_meta.json" % key), encoding="utf-8"))
    nu, nv = meta["nu"], meta["nv"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=os.path.join(kdir, "kstar_%s.obj" % key), forward_axis='Y', up_axis='Z')
    obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
    obj.matrix_world.identity()
    me = obj.data
    V = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
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
    fnz = np.array([f.normal[1] for f in bm.faces])
    fz = np.array([max(abs(v.co[1]) for v in f.verts) < 1e-6 for f in bm.faces])
    flat_down = int(np.count_nonzero(fz & (fnz < 0)))
    bverts = set()
    for e in bm.edges:
        if len(e.link_faces) == 1:
            bverts.update(v.index for v in e.verts)
    bverts = np.array(sorted(bverts))
    b_high = bverts[V[bverts, 1] > SEA_Y + 0.05 + 0.07]
    bm.verts.ensure_lookup_table()
    edge_faces = set()
    for vi in b_high:
        for f in bm.verts[int(vi)].link_faces:
            edge_faces.add(f.index)
    grid = V.reshape(nv, nu, 3)
    ring = np.vstack([grid[0, :, :], grid[1:, -1, :], grid[-1, ::-1, :][1:], grid[::-1, 0, :][1:]])
    foot = ring[:, [0, 2]]
    fwd = LOOK - EYE
    dirs = fibonacci_hemisphere(N_RAYS, fwd)
    cls = {"wave_front": 0, "wave_back_open": 0, "cut_end": 0, "hole": 0, "sea_outside_footprint": 0, "sky": 0}
    back_samples, cut_samples, hole_samples = [], [], []
    eye_v = Vector(EYE.tolist())
    sea_pts = []
    up_hits, up_total = 0, 0
    for k in range(N_RAYS):
        d = dirs[k]
        loc, nrm, idx, dist = bvh.ray_cast(eye_v, Vector(d.tolist()))
        elev = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
        if elev >= 60.0:
            up_total += 1
        if idx is not None:
            if elev >= 60.0:
                up_hits += 1
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
    out = {"obj": "kstar_%s.obj" % key, "vertices": len(V), "faces": len(bm.faces), "vertex_order_ok": bool(order_ok),
           "nonmanifold_edges_gt2_faces": int(nonman), "boundary_edges": int(boundary), "boundary_edges_expected_grid_perimeter": int(expected_boundary),
           "wire_edges": int(wire), "flipped_inconsistent_winding_edges": int(flipped), "degenerate_faces_area_lt_1e-8": int(degenerate),
           "self_intersecting_face_pairs": len(inter), "self_intersection_samples": inter[:10],
           "flat_sea_faces_facing_down": flat_down, "boundary_vertices": int(len(bverts)), "boundary_vertices_above_sea_5cm": int(len(b_high)),
           "rays": cls, "rays_elevation_ge_60deg": {"total": up_total, "hit_wave": up_hits},
           "open_back_face_samples": back_samples, "cut_end_samples": cut_samples, "hole_samples": hole_samples}
    bm.free()
    print("QA", key, json.dumps({k: v for k, v in out.items() if not k.endswith("samples")}))
    return out


res["meshes"]["r01_a45"] = qa(KNEW, "a45")
res["meshes"]["cp1_a45_same_seat"] = qa(KOLD, "a45")

if REF:
    sel = np.load(SELNPY).astype(np.float64)
    res["deviation"] = {}
    for name, kdir in (("cp1_a45", KOLD), ("r01_a45", KNEW)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.obj_import(filepath=os.path.join(kdir, "kstar_a45.obj"), forward_axis='Y', up_axis='Z')
        o = [x for x in bpy.context.scene.objects if x.type == 'MESH'][0]
        o.matrix_world.identity()
        me = o.data
        bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        d = np.empty(len(sel))
        for i, p in enumerate(sel):
            loc, nrm, idx, dist = bvh.find_nearest(Vector(p))
            d[i] = dist if dist is not None else np.nan
        meta = json.load(open(os.path.join(kdir, "kstar_a45_meta.json"), encoding="utf-8"))
        H = meta["reference_ratios_self_check_record_only"]["main_row"]["H_m"]
        res["deviation"][name] = {"n": int(np.isfinite(d).sum()), "mean_m": float(np.nanmean(d)), "p50_m": float(np.nanpercentile(d, 50)),
                                  "p95_m": float(np.nanpercentile(d, 95)), "max_m": float(np.nanmax(d)), "H_kstar_m": H,
                                  "mean_over_H": float(np.nanmean(d) / H), "p50_over_H": float(np.nanpercentile(d, 50) / H),
                                  "p95_over_H": float(np.nanpercentile(d, 95) / H), "max_over_H": float(np.nanmax(d) / H)}
        print("DEV", name, json.dumps(res["deviation"][name]))
    al = json.load(open(ALIGN))
    M4 = Matrix(al["obj_to_unity_4x4"])
    S = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bpy.ops.wm.obj_import(filepath=REF, forward_axis='Y', up_axis='Z')
    ref = [o for o in sc.objects if o.type == 'MESH'][0]
    ref.matrix_world = Matrix.Identity(4)
    ref.data.transform(S @ M4)
    if np.linalg.det(np.array(S @ M4)[:3, :3]) < 0:
        ref.data.flip_normals()
    ref.data.update()
    objs = {"ref": ref}
    for name, kdir in (("cp1", KOLD), ("r01", KNEW)):
        bpy.ops.wm.obj_import(filepath=os.path.join(kdir, "kstar_a45.obj"), forward_axis='Y', up_axis='Z')
        o = [x for x in sc.objects if x.type == 'MESH' and x.name not in [v.name for v in objs.values()]][0]
        o.matrix_world.identity()
        o.data.transform(S)
        o.data.flip_normals()
        o.data.update()
        objs[name] = o
    bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 0, -0.07))
    sea = bpy.context.active_object
    sea.color = (0.13, 0.25, 0.38, 1)
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.view_settings.view_transform = 'Standard'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_cavity = True; sh.cavity_type = 'BOTH'
    sh.show_backface_culling = False; sh.background_type = 'VIEWPORT'; sh.background_color = (0.976, 0.910, 0.769)
    sh.show_shadows = False
    sc.display.render_aa = '8'
    cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
    cd.clip_start = 0.1; cd.clip_end = 3000; cd.sensor_fit = 'VERTICAL'

    def U(p):
        return Vector((p[0], p[2], p[1]))
    vj = json.load(open(VIEWS, encoding="utf-8"))
    vv = {v["key"]: (v["eye"], v["target"], v["fov"]) for v in vj["views"]}
    views = {"seat_lip": vv["seat_lip"], "seat_up": vv["seat_up"], "side": vv["side_left"], "back": vv["back"]}
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    for name, o in objs.items():
        for x in objs.values():
            x.hide_render = x is not o
        o.color = (0.80, 0.80, 0.78, 1) if name == "ref" else (0.62, 0.72, 0.80, 1)
        for vk, (e, t, f) in views.items():
            cam.location = U(e)
            cam.rotation_mode = 'QUATERNION'
            cam.rotation_quaternion = (U(t) - U(e)).normalized().to_track_quat('-Z', 'Y')
            cd.angle_y = math.radians(f)
            # Blender の画像の書き出しは ASCII でないパス（「26修正01」）に書けないことがあるので、一時フォルダーへ書いてから移す
            tmp_png = os.path.join(TMPR, "cmp_%s_%s.png" % (name, vk))
            sc.render.filepath = tmp_png
            bpy.ops.render.render(write_still=True)
            shutil.move(tmp_png, os.path.join(OUT, "cmp_%s_%s.png" % (name, vk)))
    res["compare_views"] = {k: {"eye": v[0], "target": v[1], "fov": v[2]} for k, v in views.items()}

with open(os.path.join(OUT, "af26r01_blender.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("AF26R01_BLENDER_DONE")
