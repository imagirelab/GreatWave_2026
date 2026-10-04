# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照モデルの一時キャッシュ（PLY、断面の座標）を Blender の Workbench で描き、目で数を読むための一時の図にする。
形の画像なので、出力はキャッシュのフォルダー（Git 対象外）だけに置き、s1_obj.py delete で消す。リポジトリ・成果物へは入れない。
座標：Blender (x, y, z) = (a, c, y)（Unity の左手系から Blender の右手系へ、y と z を入れ替える慣例と同じ向き）。
使い方：blender --background --factory-startup --python s1_bl_views.py -- <ply> <outdir> <views.json>
"""
import bpy
import json
import math
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
ply, outdir, vj = argv[0], argv[1], argv[2]
views = json.load(open(vj, encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.ply_import(filepath=ply)
ob = bpy.context.selected_objects[0]
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "SINGLE"
sh.single_color = (0.8, 0.8, 0.8)
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.curvature_ridge_factor = 1.0
sh.curvature_valley_factor = 1.0
sh.show_specular_highlight = True
sc.render.resolution_x = 1600
sc.render.resolution_y = 1200
sc.render.film_transparent = False
world = bpy.data.worlds.new("w")
sc.world = world
cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
for v in views:
    name = v["name"]
    look = Vector(v["dir"])          # 視線（Blender の座標）
    look.normalize()
    ctr = Vector(v["center"])
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = v["width"]
    cam.location = ctr - look * 80.0
    if abs(look.z) > 0.99:
        # 真上から：画面の上を Blender の -x（参照の後ろ、a の負の側）にする
        cam.rotation_mode = "XYZ"
        cam.rotation_euler = (0.0, 0.0, math.pi / 2)
    else:
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = look.to_track_quat("-Z", "Y")
    cam_d.clip_start = 1.0
    cam_d.clip_end = 300.0
    sc.render.filepath = outdir + "/tmp_bl_" + name + ".png"
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath)
