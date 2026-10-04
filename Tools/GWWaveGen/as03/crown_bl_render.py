# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1-5：冠の粘土の描画（Blender 5.2 の Workbench、headless）。
入力はこの道具の呼び手（crown_render.py）が書いた一式：meshes.json（メッシュごとに .npy の頂点（Blender の座標）・三角形・頂点の色）と views.json。
座標：Blender (x, y, z) = (x_u, z_u, y_u)（Unity の左手系の y と z を入れ替える。場面とカメラの両方に同じ入れ替えをするので、画は左右に反転しない）。
使い方：blender --background --factory-startup --python crown_bl_render.py -- <meshes.json> <views.json> <outdir>
"""
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
mj, vj, outdir = argv[0], argv[1], argv[2]
meshes = json.load(open(mj, encoding="utf-8"))
views = json.load(open(vj, encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
for m in meshes:
    V = np.load(m["V"]).astype(np.float32)
    F = np.load(m["F"]).astype(np.int32)
    C = np.load(m["C"]).astype(np.float32)
    me = bpy.data.meshes.new(m["name"])
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.ravel())
    me.loops.add(len(F) * 3)
    me.loops.foreach_set("vertex_index", F.ravel())
    me.polygons.add(len(F))
    me.polygons.foreach_set("loop_start", np.arange(0, len(F) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(F), 3, np.int32))
    me.update(calc_edges=True)
    me.validate()
    if m.get("smooth", True):
        me.polygons.foreach_set("use_smooth", np.ones(len(F), bool))
    att = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    att.data.foreach_set("color", C.ravel())
    me.color_attributes.active_color = att
    ob = bpy.data.objects.new(m["name"], me)
    sc.collection.objects.link(ob)
sc.render.engine = "BLENDER_WORKBENCH"
try:
    sc.view_settings.view_transform = "Standard"
except Exception:
    pass
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "VERTEX"
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.cavity_ridge_factor = 0.6
sh.cavity_valley_factor = 1.0
sh.curvature_ridge_factor = 0.5
sh.curvature_valley_factor = 0.8
sh.show_specular_highlight = True
sh.show_shadows = True
sh.shadow_intensity = 0.45
sh.show_backface_culling = False
sc.display.shadow_focus = 0.2
try:
    sc.display.light_direction = (-0.45, -0.5, 0.75)      # Blender の座標の光の向き（Unity の固定の光と同じ向き）
except Exception:
    pass
sc.display.render_aa = "16"
world = bpy.data.worlds.new("w")
world.color = (0.62, 0.66, 0.72)
sc.world = world
sh.background_type = "WORLD"
cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam_d.sensor_fit = "VERTICAL"
cam_d.clip_start = 0.3
cam_d.clip_end = 2000.0


def bl(v):
    return Vector((v[0], v[2], v[1]))


for v in views:
    W, H = v.get("W", 1920), v.get("H", 1080)
    sc.render.resolution_x = W
    sc.render.resolution_y = H
    sc.render.resolution_percentage = 100
    f = bl(v["fwd"]).normalized()
    u = bl(v["up"])
    u = (u - f * u.dot(f)).normalized()
    r = f.cross(u)                 # Blender（右手系）のカメラの右 = 前 × 上
    M = Matrix(((r.x, u.x, -f.x), (r.y, u.y, -f.y), (r.z, u.z, -f.z)))
    cam.matrix_world = Matrix.Translation(bl(v["pos"])) @ M.to_4x4()
    cam_d.angle_y = math.radians(v["fov"])
    sc.render.filepath = outdir + "/" + v["name"] + ".png"
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath, flush=True)
