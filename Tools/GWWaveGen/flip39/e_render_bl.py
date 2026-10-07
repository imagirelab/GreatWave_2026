# -*- coding: utf-8 -*-
"""FLIP39 E：粘土の図（Blender 5.2.2、画面なし、Workbench の MatCap clay_studio。FLIP37 の video_render_bl.py と同じ見た目の設定）。
使い方: blender -b --factory-startup -P e_render_bl.py -- <job.json>
job.json: {"res": [960, 540], "items": [{"mesh": ".../mesh_0301.npz", "mode": "slab"|"mirror", "Lz": 12, "zw": -120,
            "crop_x": [300, 706], "boat": [x, z] or null, "cams": [{"pos": [x,y,z], "look": [x,y,z], "vfov": 60, "out": ".../a.png"}]}]}
座標：計算の (x, y, z)（y が上）→ Blender (x, −z, y)（右手系のまま）。
板（slab）：z に一様な波なので、板の網目を z 方向に並べて ±tile_m まで広げる（壁の面は捨てる）。
3D（mirror）：z = zw の壁（対称の面）で網目を鏡に映して足す（壁の面は捨てる）。
船（boat）：座席の位置に長さ 11.33 m・幅 3.6 m・高さ 1.2 m の箱（大きさの目安。波には乗せない。灰色）。
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf8"))
res = job.get("res", [960, 540])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "MATCAP"
sh.studio_light = "clay_studio.exr"
sh.color_type = "OBJECT"
sh.show_cavity = True
sh.cavity_type = "WORLD"
sh.show_object_outline = False
sh.background_type = "VIEWPORT"
sh.background_color = (0.80, 0.86, 0.92)
sh.show_backface_culling = False
sc.render.resolution_x, sc.render.resolution_y = res
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"

water = bpy.data.objects.new("water", bpy.data.meshes.new("w0"))
water.color = (0.78, 0.74, 0.66, 1.0)
sc.collection.objects.link(water)
boat = None
camobj = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(camobj)
sc.camera = camobj


def b(v):
    return Vector((v[0], -v[2], v[1]))


def drop_walls(P, tri, zwalls, tol=0.6):
    """z の壁の上にある三角形（3 点とも壁から tol 以内）を捨てる。"""
    keep = np.ones(len(tri), bool)
    for zw in zwalls:
        on = np.abs(P[tri][:, :, 2] - zw) < tol
        keep &= ~on.all(axis=1)
    return tri[keep]


def build(item):
    d = np.load(item["mesh"])
    P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
    P[:, 1] += float(item.get("yoff", 0.0))   # 粒子から水面を作る時のずれ（静かな水で +0.43〜0.46 m）を引く
    cx = item.get("crop_x")
    if cx:
        c = P[tri].mean(axis=1)[:, 0]
        tri = tri[(c >= cx[0]) & (c <= cx[1])]
    Lz = float(item["Lz"])
    if item["mode"] == "slab":
        # 板：z に一様な波なので、網目を z = 0.013 の面で切った断面（張り出しも含む線分の集まり）を z 方向に ±tile_m 押し出す
        # （板の網目をそのまま並べると、壁ぎわの水面の乱れが 12 m ごとの継ぎ目になったため）
        z0 = 0.013
        A = P[tri]                                    # (n, 3, 3)
        sgn = np.sign(A[:, :, 2] - z0)
        segs = []
        for (i, j) in ((0, 1), (1, 2), (2, 0)):
            pass
        cross = []
        for (i, j) in ((0, 1), (1, 2), (2, 0)):
            m = sgn[:, i] * sgn[:, j] < 0
            f = (z0 - A[:, i, 2]) / np.where(m, A[:, j, 2] - A[:, i, 2], 1.0)
            pt = A[:, i, :] + f[:, None] * (A[:, j, :] - A[:, i, :])
            cross.append((m, pt))
        nt = np.cross(A[:, 1] - A[:, 0], A[:, 2] - A[:, 0])     # 網目の三角形の外向きの法線（向きをそろえる手がかり）
        pts = []
        for k in range(len(tri)):
            q = [c[1][k] for c in cross if c[0][k]]
            if len(q) == 2:
                a_, b_ = q
                d_ = b_ - a_
                nq = np.array([-d_[1], d_[0], 0.0])               # 線分を +z へ押し出した面の法線（の向き）
                if nq[0] * nt[k, 0] + nq[1] * nt[k, 1] < 0:
                    a_, b_ = b_, a_
                pts.append((a_, b_))
        tile = float(item.get("tile_m", 160.0))
        nzs = 40
        zz = np.linspace(-tile, tile, nzs + 1)
        V = []; T = []
        for a_, b_ in pts:
            n0 = len(V)
            for zq in zz:
                V += [[a_[0], a_[1], zq], [b_[0], b_[1], zq]]
            for j in range(nzs):
                i0 = n0 + 2 * j
                T += [[i0, i0 + 2, i0 + 3], [i0, i0 + 3, i0 + 1]]
        P = np.array(V, float); tri = np.array(T, np.int64)
    else:
        zw = float(item.get("zw", -0.5 * Lz))
        tri = drop_walls(P, tri, [zw, zw + Lz])
        Q = P.copy(); Q[:, 2] = 2 * zw - Q[:, 2]
        P = np.concatenate([P, Q]); tri = np.concatenate([tri, tri[:, ::-1] + len(Q)])
    B = np.c_[P[:, 0], -P[:, 2], P[:, 1]]
    me = bpy.data.meshes.new("w")
    me.vertices.add(len(B)); me.vertices.foreach_set("co", B.astype(np.float32).ravel())
    me.loops.add(tri.size); me.loops.foreach_set("vertex_index", tri.astype(np.int32).ravel())
    me.polygons.add(len(tri)); me.polygons.foreach_set("loop_start", (np.arange(len(tri)) * 3).astype(np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(tri), 3, np.int32))
    me.update(); me.validate()
    old = water.data
    water.data = me
    bpy.data.meshes.remove(old)


def set_boat(bz):
    global boat
    if bz is None:
        if boat:
            boat.hide_render = True
        return
    if boat is None:
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        boat = bpy.context.active_object
        boat.scale = (11.33, 3.6, 1.2)
        boat.color = (0.35, 0.35, 0.38, 1.0)
    boat.hide_render = False
    by = bz[2] if len(bz) > 2 else 0.0
    boat.location = b([bz[0] - 1.0, by + 0.03, bz[1]])


for it in job["items"]:
    outs = [c["out"] for c in it["cams"]]
    if all(os.path.exists(o) for o in outs):
        continue
    build(it)
    set_boat(it.get("boat"))
    for c in it["cams"]:
        if os.path.exists(c["out"]):
            continue
        camobj.location = b(c["pos"])
        dvec = b(c["look"]) - b(c["pos"])
        camobj.rotation_mode = "QUATERNION"
        camobj.rotation_quaternion = dvec.to_track_quat("-Z", "Y")
        camobj.data.sensor_fit = "VERTICAL"
        camobj.data.angle_y = np.radians(float(c.get("vfov", 50)))
        camobj.data.clip_start = float(c.get("near", 0.3))
        camobj.data.clip_end = 5000.0
        sc.render.filepath = c["out"]
        os.makedirs(os.path.dirname(c["out"]), exist_ok=True)
        bpy.ops.render.render(write_still=True)
print("render done", len(job["items"]))
