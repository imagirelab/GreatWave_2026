# -*- coding: utf-8 -*-
"""番号26：参照モデル（Q5）と K* の比較の Blender 側（記録のみ）。Blender 5.2.2 ヘッドレス。

使い方:
    blender --background --factory-startup --python Tools/GWWaveGen/af26_blender_ref.py -- <ref_obj> <align_json> <kstar_dir> <ref_selected_world.npy> <out_dir>

1. 偏差の統計：af26_reference.py が選んだ参照モデルの頂点（Unity ワールド座標）から、各 K* の面までの最短距離（BVH の find_nearest）。
2. 並べ図：参照モデル（解B の 4×4 で世界座標へ）と K* 3 案を、船上座席・側面・背面・真上の同じ機位から Workbench で描く。
参照モデルの OBJ は読むだけで保存しない（.blend も書かない）。座標は Unity (x, y, z) → Blender (x, z, y) で描く。
"""
import sys
import os
import json
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
REF, ALIGN, KDIR, SELNPY, OUT = argv[:5]
os.makedirs(OUT, exist_ok=True)
KEYS = ["a30", "a45", "a60"]
res = {"blender": bpy.app.version_string, "deviation": {}}
sel = np.load(SELNPY).astype(np.float64)

# ---- 1. 偏差（K* の座標は Unity のまま BVH にする）
for k in KEYS:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=os.path.join(KDIR, "kstar_%s.obj" % k), forward_axis='Y', up_axis='Z')
    o = [x for x in bpy.context.scene.objects if x.type == 'MESH'][0]
    o.matrix_world.identity()
    me = o.data
    verts = [v.co.copy() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    d = np.empty(len(sel))
    for i, p in enumerate(sel):
        loc, nrm, idx, dist = bvh.find_nearest(Vector(p))
        d[i] = dist if dist is not None else np.nan
    meta = json.load(open(os.path.join(KDIR, "kstar_%s_meta.json" % k), encoding="utf-8"))
    H = meta["reference_ratios_self_check_record_only"]["main_row"]["H_m"]
    res["deviation"][k] = {"n": int(np.isfinite(d).sum()), "mean_m": float(np.nanmean(d)), "p50_m": float(np.nanpercentile(d, 50)),
                           "p95_m": float(np.nanpercentile(d, 95)), "max_m": float(np.nanmax(d)), "H_kstar_m": H,
                           "mean_over_H": float(np.nanmean(d) / H), "p50_over_H": float(np.nanpercentile(d, 50) / H),
                           "p95_over_H": float(np.nanpercentile(d, 95) / H), "max_over_H": float(np.nanmax(d) / H)}
    print("DEV", k, json.dumps(res["deviation"][k]))

# ---- 2. 並べ図
al = json.load(open(ALIGN))
M4 = Matrix(al["obj_to_unity_4x4"])
S = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # Unity → Blender
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# 軸の変換をしない指定（forward=Y, up=Z）で読み、生の OBJ 座標に解B の 4×4 と Unity→Blender の入れ替えをかける
bpy.ops.wm.obj_import(filepath=REF, forward_axis='Y', up_axis='Z')
ref = [o for o in sc.objects if o.type == 'MESH'][0]
ref.matrix_world = Matrix.Identity(4)
ref.data.transform(S @ M4)
if np.linalg.det(np.array(S @ M4)[:3, :3]) < 0:
    ref.data.flip_normals()
ref.data.update()
objs = {"ref": ref}
for k in KEYS:
    bpy.ops.wm.obj_import(filepath=os.path.join(KDIR, "kstar_%s.obj" % k), forward_axis='Y', up_axis='Z')
    o = [x for x in sc.objects if x.type == 'MESH' and x.name not in [v.name for v in objs.values()]][0]
    o.matrix_world.identity()
    o.data.transform(S)
    o.data.flip_normals()
    o.data.update()
    objs[k] = o
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


views = {"boat": ((-0.7069781422615051, 1.514340877532959, -33.40697479248047), (-7, 5, 3), 80),
         "side": ((53, 22, -2), (-1, 7, 0), 60), "back": ((-45, 30, 60), (-5, 8, -3), 50), "top": ((-5, 120, -10), (-5, 0, -9.9), 60),
         "painting": ((0, 3, -62), (-2.5, 9.7, 4), 26)}
sc.render.resolution_x, sc.render.resolution_y = 960, 540
bb = {}
for name, o in objs.items():
    co = np.zeros(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)[::50]
    bb[name] = {"blender_min": co.min(0).round(2).tolist(), "blender_max": co.max(0).round(2).tolist()}
res["bounds_blender_xyz_every50th_vertex"] = bb
for name, o in objs.items():
    for x in objs.values():
        x.hide_render = x is not o
    o.color = (0.80, 0.80, 0.78, 1) if name == "ref" else (0.62, 0.72, 0.80, 1)
    for vk, (e, t, f) in views.items():
        cam.location = U(e)
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = (U(t) - U(e)).normalized().to_track_quat('-Z', 'Y')
        cd.angle_y = math.radians(f)
        sc.render.filepath = os.path.join(OUT, "cmp_%s_%s.png" % (name, vk))
        bpy.ops.render.render(write_still=True)
with open(os.path.join(OUT, "af26_blender_ref.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("REF_BLENDER_DONE")
