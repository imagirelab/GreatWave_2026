# -*- coding: utf-8 -*-
"""P2 の粘土の図（Blender 5.2.2、画面なし）。網目（計算の座標）を p2_common.place と同じ変換で Unity の座標へ置き、
Unity → Blender（x, z, y）に直して、原画カメラ（PaintingCam v1）と左前の斜め（見本06 の回り台 315°）から描く。

使い方: blender -b -P p2_clay_bl.py -- <job.json>
job.json: {"mesh": ".../mesh_XXXX.npz", "T": [..], "E": [..], "O": [..], "s": 1.0, "anchor": [xa, ya, za],
           "cams": [{"name": "painting", "pos": [...], "fwd": [...], "up": [...], "vfov": 26}, ...],
           "out_prefix": ".../clay", "res": [1920, 1080]}
材質は粘土の 1 色（Workbench の MATCAP clay_studio）。海の外（計算の箱の外）は描かない。
"""
import sys, json
import numpy as np
import bpy
from mathutils import Matrix, Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf8"))
d = np.load(job["mesh"])
P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
T = np.array(job["T"]); E = np.array(job["E"]); O = np.array(job["O"]); s = float(job["s"]); a = job["anchor"]
Q = P - np.array([a[0], 0.0, a[2]])
U = O + s * (Q[:, 0:1] * T + Q[:, 1:2] * np.array([0.0, 1.0, 0.0]) + Q[:, 2:3] * E)
B = np.stack([U[:, 0], U[:, 2], U[:, 1]], 1)   # Unity (x, y, z) → Blender (x, z, y)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
me = bpy.data.meshes.new("water")
me.vertices.add(len(B))
me.vertices.foreach_set("co", B.astype(np.float32).ravel())
me.loops.add(tri.size)
me.loops.foreach_set("vertex_index", tri[:, [0, 2, 1]].astype(np.int32).ravel())   # 19:20 から裏返す（MATCAP で確かめると、元の向きでは水の外へ向く面が裏になっていた）
me.polygons.add(len(tri))
me.polygons.foreach_set("loop_start", (np.arange(len(tri)) * 3).astype(np.int32))
me.update(calc_edges=True)
me.validate()
for p in me.polygons:
    p.use_smooth = True
ob = bpy.data.objects.new("water", me)
sc.collection.objects.link(ob)

sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "MATCAP"   # 18:50 STUDIO から変えた（STUDIO では下から見上げる面が暗くつぶれた）
sh.studio_light = "clay_studio.exr"
sh.color_type = "SINGLE"
sh.single_color = (0.78, 0.74, 0.66)
sh.show_cavity = True
sh.cavity_type = "WORLD"
sh.show_object_outline = False
sh.background_type = "VIEWPORT"
sh.background_color = (0.93, 0.92, 0.88)
sc.display.shading.show_backface_culling = False
sc.render.resolution_x, sc.render.resolution_y = job.get("res", [1920, 1080])
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"

for c in job["cams"]:
    cd = bpy.data.cameras.new(c["name"])
    cd.sensor_fit = "VERTICAL"
    cd.angle_y = np.radians(c["vfov"])
    cd.clip_start = 0.5; cd.clip_end = 3000
    co = bpy.data.objects.new(c["name"], cd)
    sc.collection.objects.link(co)
    pos = np.array(c["pos"]); f = np.array(c["fwd"], float); f /= np.linalg.norm(f)
    up = np.array(c["up"], float)
    r = np.cross(up, f); r /= np.linalg.norm(r); u = np.cross(f, r)
    sw = lambda v: Vector((v[0], v[2], v[1]))
    X, Y, Z = sw(r), sw(u), -sw(f)
    M = Matrix(((X[0], Y[0], Z[0]), (X[1], Y[1], Z[1]), (X[2], Y[2], Z[2]))).to_4x4()
    M.translation = sw(pos)
    co.matrix_world = M
    sc.camera = co
    sc.render.filepath = job["out_prefix"] + "_" + c["name"] + ".png"
    bpy.ops.render.render(write_still=True)
print("CLAY DONE")
