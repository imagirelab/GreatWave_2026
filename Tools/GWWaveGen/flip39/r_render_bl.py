# -*- coding: utf-8 -*-
"""FLIP39 R：粘土の図（Blender 5.2.2、画面なし、Workbench の MatCap clay_studio。E の e_render_bl.py と同じ見た目の設定）。
使い方: blender -b --factory-startup -P r_render_bl.py -- <job.json>
job.json: {"res": [W, H],
           "coarse": {"npz": ".../coarse_eta.npz", "hole": [x0, x1, z0, z1]},   E3 の一番上の水面（2 m、毎コマ）。hole の中（細かい計算の範囲）は描かない
           "items": [{"frame": F, "fine": ".../mesh_FFFF.npz" or null, "fine_off": 0.6, "boat": [x, y, z] or null,
                      "cams": [{"pos": [x,y,z], "look": [x,y,z], "vfov": 60, "near": 0.3, "out": ".../a.png"}]}]}
- 細かい計算の網目（粘土色）：z = −120 m の壁（E3 の対称の面）で鏡に映して足す。壁の上の面は捨て、壁から 0.4 m の点は壁の上へ寄せる。
- 粗い計算の水面（青みの灰色）：E3 の一番上の水面（張り出しは描けない）。z = −120 m の壁で鏡に映す。細かい計算の範囲は穴にする。
- 水槽の外：高さ 0 の平らな面（青みの灰色）。
- 船：座席の位置に長さ 11.33 m・幅 3.6 m・高さ 0.6 m の箱（灰色。目と同じく上下だけ水面に乗せる。大きさの目安）。
座標：計算の (x, y, z)（y が上）→ Blender (x, −z, y)。水面のずれ（粒子から水面を作る時のずれ）は引いてから描く。
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
ZW = -120.0
CLAY = (0.78, 0.74, 0.66, 1.0)
COARSE = (0.62, 0.66, 0.70, 1.0)


def new_obj(name, color):
    o = bpy.data.objects.new(name, bpy.data.meshes.new(name + "0"))
    o.color = color
    sc.collection.objects.link(o)
    return o


def set_mesh(obj, P, tri):
    B = np.c_[P[:, 0], -P[:, 2], P[:, 1]]
    me = bpy.data.meshes.new("m")
    me.vertices.add(len(B)); me.vertices.foreach_set("co", B.astype(np.float32).ravel())
    me.loops.add(tri.size); me.loops.foreach_set("vertex_index", tri.astype(np.int32).ravel())
    me.polygons.add(len(tri)); me.polygons.foreach_set("loop_start", (np.arange(len(tri)) * 3).astype(np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(tri), 3, np.int32))
    me.update(); me.validate()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)


fine = new_obj("fine", CLAY)
coarse = new_obj("coarse", COARSE)
outer = new_obj("outer", COARSE)
camobj = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(camobj)
sc.camera = camobj
boat = None

# ---- 粗い計算の水面（topology は一度だけ作り、コマごとに高さだけ入れ替える）
CO = job.get("coarse")
cdat = None
if CO:
    d = np.load(CO["npz"])
    cdat = dict(eta=d["eta"], frames=d["frames"], x=d["x"], z=d["z"], off=float(d["off"]))
    xs, zs = cdat["x"], cdat["z"]
    nx, nz = len(xs), len(zs)
    X, Z = np.meshgrid(xs, zs)
    hx0, hx1, hz0, hz1 = CO.get("hole") or [0, 0, 0, 0]
    cx = 0.5 * (X[:-1, :-1] + X[1:, 1:]); cz = 0.5 * (Z[:-1, :-1] + Z[1:, 1:])
    keep = ~((cx > hx0) & (cx < hx1) & (cz > hz0) & (cz < hz1))
    j, i = np.nonzero(keep)
    v00 = j * nx + i; v10 = j * nx + i + 1; v01 = (j + 1) * nx + i; v11 = (j + 1) * nx + i + 1
    T = np.concatenate([np.c_[v00, v11, v10], np.c_[v00, v01, v11]])   # 上向きの法線（裏の面は MatCap で暗くなるため）
    N = nx * nz
    cdat["tri"] = np.concatenate([T, T[:, ::-1] + N])
    cdat["X"] = np.concatenate([X.ravel(), X.ravel()]); cdat["Z"] = np.concatenate([Z.ravel(), 2 * ZW - Z.ravel()])
    cdat["fidx"] = {int(f): k for k, f in enumerate(cdat["frames"])}
    set_mesh(coarse, np.c_[cdat["X"], np.zeros(2 * N), cdat["Z"]], cdat["tri"])
    # 水槽の外の平らな面（x 0〜806、z −360〜120 の外）
    L = 6000.0
    xa, xb_, za, zb_ = float(xs[0]), float(xs[-1]), float(2 * ZW - zs[-1]), float(zs[-1])
    quads = [((-L, -L), (xa, -L), (xa, L), (-L, L)), ((xb_, -L), (L, -L), (L, L), (xb_, L)),
             ((xa, -L), (xb_, -L), (xb_, za), (xa, za)), ((xa, zb_), (xb_, zb_), (xb_, L), (xa, L))]
    PP = []; TT = []
    for q in quads:
        n0 = len(PP)
        PP += [[p[0], 0.0, p[1]] for p in q]
        TT += [[n0, n0 + 2, n0 + 1], [n0, n0 + 3, n0 + 2]]   # 上向きの法線
    set_mesh(outer, np.array(PP, float), np.array(TT, np.int64))


PH = job.get("plane_hole")
if PH and not CO:
    # 粗い水面がない時（FLIP37 P3 の「前」の図）：細かい計算の箱の外を高さ 0 の平らな面にする
    L = 6000.0
    xa, xb_, za, zb_ = PH
    quads = [((-L, -L), (xa, -L), (xa, L), (-L, L)), ((xb_, -L), (L, -L), (L, L), (xb_, L)),
             ((xa, -L), (xb_, -L), (xb_, za), (xa, za)), ((xa, zb_), (xb_, zb_), (xb_, L), (xa, L))]
    PP = []; TT = []
    for q in quads:
        n0 = len(PP)
        PP += [[p[0], 0.0, p[1]] for p in q]
        TT += [[n0, n0 + 2, n0 + 1], [n0, n0 + 3, n0 + 2]]
    set_mesh(outer, np.array(PP, float), np.array(TT, np.int64))


def set_coarse(frame):
    if cdat is None:
        return
    k = cdat["fidx"].get(int(frame))
    if k is None:
        k = int(np.argmin(np.abs(cdat["frames"] - frame)))
    e = cdat["eta"][k].astype(np.float64).ravel() - cdat["off"]
    e = np.where(np.isfinite(e), e, 0.0)
    Y = np.concatenate([e, e])
    B = np.c_[cdat["X"], -cdat["Z"], Y].astype(np.float32)
    coarse.data.vertices.foreach_set("co", B.ravel())
    coarse.data.update()


def set_fine(path, off, mirror=True, flip=False):
    if not path:
        fine.hide_render = True
        return
    fine.hide_render = False
    d = np.load(path)
    P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
    P[:, 1] -= off
    # Particle Fluid Surface の網目（FLIP37 P3・この R）は、そのままでは Workbench の MatCap で表の面が暗い茶色に描かれた（10/8 02:35 の試し）。
    # 三角形の向きを裏返すと粘土色になる（E の Convert Volume の網目は裏返さない）。flip で選ぶ
    if flip:
        tri = tri[:, ::-1]
    if not mirror:
        set_mesh(fine, P, tri)
        return
    # 壁（対称の面）の継ぎ目：壁から 1.2 m の点を壁の上へ寄せ、3 点とも壁の上の三角形（壁に沿う面）を捨てる。
    # 粒子の面は壁ぎわで丸く下がるので、寄せないと鏡に映した網目との間にすき間（暗い破線）が出た（10/8 02:50 の試し）
    near = P[:, 2] < ZW + 1.2
    P[near, 2] = ZW
    onw = (P[tri][:, :, 2] <= ZW + 1e-6).all(axis=1)
    tri = tri[~onw]
    Q = P.copy(); Q[:, 2] = 2 * ZW - Q[:, 2]
    P2 = np.concatenate([P, Q]); T2 = np.concatenate([tri, tri[:, ::-1] + len(P)])
    set_mesh(fine, P2, T2)


def set_boat(bz):
    global boat
    if bz is None:
        if boat:
            boat.hide_render = True
        return
    if boat is None:
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        boat = bpy.context.active_object
        boat.scale = (11.33, 3.6, 0.6)
        boat.color = (0.35, 0.35, 0.38, 1.0)
    boat.hide_render = False
    boat.location = Vector((bz[0], -bz[2], bz[1] + 0.03))


def b(v):
    return Vector((v[0], -v[2], v[1]))


for it in job["items"]:
    outs = [c["out"] for c in it["cams"]]
    if all(os.path.exists(o) for o in outs):
        continue
    set_coarse(it["frame"])
    set_fine(it.get("fine"), float(it.get("fine_off", 0.0)), bool(it.get("mirror", True)), bool(it.get("flip", False)))
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
        camobj.data.clip_end = 8000.0
        sc.render.filepath = c["out"]
        os.makedirs(os.path.dirname(c["out"]), exist_ok=True)
        bpy.ops.render.render(write_still=True)
    print("frame", it["frame"], flush=True)
print("render done", len(job["items"]))
