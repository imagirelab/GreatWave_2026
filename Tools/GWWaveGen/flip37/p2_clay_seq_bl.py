# -*- coding: utf-8 -*-
"""P2 の粘土の動画のコマ（Blender 5.2.2、画面なし）。p2_clay_bl.py と同じ置き方・同じ材質で、網目の列を 1 回の Blender で順に描く。
使い方: blender -b --factory-startup -P p2_clay_seq_bl.py -- <seq_job.json>
seq_job.json: {"meshes": [".../mesh_XXXX.npz", ...], "T", "E", "O", "s", "anchor", "cams": [...], "out_dir": "...", "res": [w, h]}
出力：<out_dir>/<cam>_<0000>.png（網目の順の番号）
"""
import sys, json, os
import numpy as np
import bpy
from mathutils import Matrix, Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf8"))
T = np.array(job["T"]); E = np.array(job["E"]); O = np.array(job["O"]); s = float(job["s"]); a = job["anchor"]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "MATCAP"
sh.studio_light = "clay_studio.exr"
sh.color_type = "SINGLE"
sh.single_color = (0.78, 0.74, 0.66)
sh.show_cavity = True
sh.cavity_type = "WORLD"
sh.show_object_outline = False
sh.background_type = "VIEWPORT"
sh.background_color = (0.93, 0.92, 0.88)
sh.show_backface_culling = False
sc.render.resolution_x, sc.render.resolution_y = job.get("res", [1280, 720])
sc.view_settings.view_transform = "Standard"
cams = []
for c in job["cams"]:
    cd = bpy.data.cameras.new(c["name"])
    cd.sensor_fit = "VERTICAL"; cd.angle_y = np.radians(c["vfov"]); cd.clip_start = 0.5; cd.clip_end = 3000
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
    cams.append((c["name"], co))
os.makedirs(job["out_dir"], exist_ok=True)
ob = None
for i, mp in enumerate(job["meshes"]):
    d = np.load(mp)
    P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
    Q = P - np.array([a[0], 0.0, a[2]])
    U = O + s * (Q[:, 0:1] * T + Q[:, 1:2] * np.array([0.0, 1.0, 0.0]) + Q[:, 2:3] * E)
    B = np.stack([U[:, 0], U[:, 2], U[:, 1]], 1)
    if ob is not None:
        me_old = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me_old)
    me = bpy.data.meshes.new("water")
    me.vertices.add(len(B)); me.vertices.foreach_set("co", B.astype(np.float32).ravel())
    me.loops.add(tri.size); me.loops.foreach_set("vertex_index", tri[:, [0, 2, 1]].astype(np.int32).ravel())
    me.polygons.add(len(tri)); me.polygons.foreach_set("loop_start", (np.arange(len(tri)) * 3).astype(np.int32))
    me.update(calc_edges=True); me.validate()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("water", me)
    sc.collection.objects.link(ob)
    for name, co in cams:
        sc.camera = co
        sc.render.filepath = os.path.join(job["out_dir"], "%s_%04d.png" % (name, i))
        bpy.ops.render.render(write_still=True)
print("SEQ DONE", len(job["meshes"]))
