# -*- coding: utf-8 -*-
"""P3 の粘土のコマ（Blender 5.2.2、画面なし）。p2_clay_seq_bl.py を元に、1 コマに網目を何枚か（色を変えて）重ねられるようにした。
使い方: blender -b --factory-startup -P p3_clay_seq_bl.py -- <seq_job.json>
seq_job.json: {"frames": [[{"path": ".../mesh_XXXX.npz", "color": [r, g, b]}, ...], ...], "T", "E", "O", "s", "anchor",
               "cams": [...], "out_dir": "...", "res": [w, h]}
（"meshes": [...] だけなら P2 と同じく 1 枚・粘土の色）
出力：<out_dir>/<cam>_<0000>.png（コマの順の番号）
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
sh.color_type = "MATERIAL"
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
CLAY = [0.78, 0.74, 0.66]
frames = job.get("frames") or [[{"path": mp, "color": CLAY}] for mp in job["meshes"]]
mats = {}


def mat_for(col):
    k = tuple(round(c, 3) for c in col)
    if k not in mats:
        m = bpy.data.materials.new("m%d" % len(mats))
        m.diffuse_color = (col[0], col[1], col[2], 1.0)
        mats[k] = m
    return mats[k]


obs = []
for i, layers in enumerate(frames):
    for ob in obs:
        me_old = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me_old)
    obs = []
    for L in layers:
        d = np.load(L["path"])
        P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
        if len(tri) == 0:
            continue
        Q = P - np.array([a[0], 0.0, a[2]])
        U = O + s * (Q[:, 0:1] * T + Q[:, 1:2] * np.array([0.0, 1.0, 0.0]) + Q[:, 2:3] * E)
        B = np.stack([U[:, 0], U[:, 2], U[:, 1]], 1)
        me = bpy.data.meshes.new("water")
        me.vertices.add(len(B)); me.vertices.foreach_set("co", B.astype(np.float32).ravel())
        order = [0, 1, 2] if L.get("flip") else [0, 2, 1]   # P3 の網目は P2 と三角形の向きが逆（"flip": true）
        me.loops.add(tri.size); me.loops.foreach_set("vertex_index", tri[:, order].astype(np.int32).ravel())
        me.polygons.add(len(tri)); me.polygons.foreach_set("loop_start", (np.arange(len(tri)) * 3).astype(np.int32))
        me.update(calc_edges=True); me.validate()
        me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
        me.materials.append(mat_for(L.get("color", CLAY)))
        ob = bpy.data.objects.new("water", me)
        sc.collection.objects.link(ob)
        obs.append(ob)
    for name, co in cams:
        sc.camera = co
        sc.render.filepath = os.path.join(job["out_dir"], "%s_%04d.png" % (name, i))
        bpy.ops.render.render(write_still=True)
print("SEQ DONE", len(frames))
