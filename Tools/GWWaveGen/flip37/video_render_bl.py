# -*- coding: utf-8 -*-
"""動画の粘土の図（Blender 5.2.2、画面なし）。一つの Blender の中で多くのコマを順に描く（コマごとに Blender を起こさない）。

使い方: blender -b --factory-startup -P video_render_bl.py -- <job.json>
job.json:
  {"res": [960, 540], "near_clip": 3.0,
   "items": [{"mesh": ".../mesh_0301.npz",            # 計算の網目（P・tri、計算の座標）
              "xf": {"T": [..], "E": [..], "O": [..], "s": 1.0, "anchor": [xa, ya, za]},   # 計算 → Unity（p2_common.place と同じ式）
              "cams": [{"name": "painting", "pos": [..], "fwd": [..], "up": [0,1,0], "vfov": 26}, ...],
              "crop": {"x": [-160, 90], "z": [-70, 70]},        # 任意：頂からの計算の座標の箱の外の三角形を捨てる
              "out": {"painting": ".../painting/f0301.png", ...}},
             {"static": ".../union_AS06R9_f1.json", "xf": null, ...}]}   # Unity の座標の網目（見本06 の形式）
材質は粘土の 1 色（Workbench の studio の光、くぼみの陰）。p2_clay_bl.py と同じ設定。出力が全部あるものは描かない（続きから）。
面の向き：item の "flip"（既定 "auto"）。"auto" は静かな水面より上の、上下を向いた面の法線の向きで判定して、下向きが多ければ三角形の向きを
反転する。Workbench は面の両側を同じに照らすので、今の見た目は反転しても変わらない（2026-10-06 に R05・P1・R9 で確かめた）。
面の向きを使う描き方に替えたときのための備え。
"""
import sys, os, json, time
import numpy as np
import bpy
from mathutils import Matrix, Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf8"))
res = job.get("res", [960, 540])
near_clip = float(job.get("near_clip", 3.0))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
LIGHT = job.get("light", "MATCAP")
if LIGHT == "MATCAP":
    # P2・P3 の粘土の図と同じ（Blender 付属の clay_studio の MatCap）。STUDIO の光は暗くて読みにくかった（2026-10-07）
    sh.light = "MATCAP"
    sh.studio_light = "clay_studio.exr"
else:
    sh.light = "STUDIO"
sh.color_type = "SINGLE"
sh.single_color = (0.78, 0.74, 0.66)   # CLAY と同じ
sh.show_cavity = True
sh.cavity_type = "WORLD"
sh.show_object_outline = False
sh.background_type = "VIEWPORT"
sh.background_color = (0.93, 0.92, 0.88)
sh.show_backface_culling = False
sc.render.resolution_x, sc.render.resolution_y = res
sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"

ob = bpy.data.objects.new("water", bpy.data.meshes.new("empty"))
sc.collection.objects.link(ob)
cams = {}


def sw(v):
    return Vector((v[0], v[2], v[1]))   # Unity (x, y, z) → Blender (x, z, y)


def get_cam(c):
    key = json.dumps(c, sort_keys=True)
    if key in cams:
        return cams[key]
    cd = bpy.data.cameras.new(c["name"])
    cd.sensor_fit = "VERTICAL"
    cd.angle_y = np.radians(c["vfov"])
    cd.clip_start = float(c.get("clip_start", near_clip if c["name"] == "painting" else 0.5))
    cd.clip_end = 3000
    co = bpy.data.objects.new(c["name"], cd)
    sc.collection.objects.link(co)
    pos = np.array(c["pos"], float); f = np.array(c["fwd"], float); f /= np.linalg.norm(f)
    up = np.array(c["up"], float)
    r = np.cross(up, f); r /= np.linalg.norm(r); u = np.cross(f, r)
    X, Y, Z = sw(r), sw(u), -sw(f)
    M = Matrix(((X[0], Y[0], Z[0]), (X[1], Y[1], Z[1]), (X[2], Y[2], Z[2]))).to_4x4()
    M.translation = sw(pos)
    co.matrix_world = M
    cams[key] = co
    return co


def load_static(js):
    meta = json.load(open(js, encoding="utf-8"))
    n = meta["vertices"]
    raw = np.fromfile(os.path.join(os.path.dirname(js), meta["bin"]), np.float32)
    off = 0
    pos = None
    for nm, k in meta["channels"]:
        if nm == "position":
            pos = raw[off:off + n * k].reshape(n, k).astype(np.float64)
        off += n * k
    tri = raw[off:].view(np.uint32).reshape(-1, 3).astype(np.int64)
    return pos, tri


CLAY = (0.78, 0.74, 0.66)
OUTER_TINT = job.get("outer_tint", [0.66, 0.68, 0.70])   # 外の海（P2）の色。少し灰青にして主役の範囲（P3）と見分ける。None で同じ色


def set_mesh(B, tri, vcol=None):
    old = ob.data
    me = bpy.data.meshes.new("water")
    me.vertices.add(len(B))
    me.vertices.foreach_set("co", B.astype(np.float32).ravel())
    me.loops.add(tri.size)
    me.loops.foreach_set("vertex_index", tri.astype(np.int32).ravel())
    me.polygons.add(len(tri))
    me.polygons.foreach_set("loop_start", (np.arange(len(tri)) * 3).astype(np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.ones(len(tri), bool))
    if vcol is not None:
        ca = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
        ca.data.foreach_set("color", np.concatenate([vcol, np.ones((len(vcol), 1))], 1).astype(np.float32).ravel())
    ob.data = me
    bpy.data.meshes.remove(old)


static_cache = {}
t_all = time.time(); n_img = 0
for i, it in enumerate(job["items"]):
    outs = it["out"]
    if all(os.path.isfile(p) for p in outs.values()) and not job.get("force"):
        continue
    t0 = time.time()
    if "static" in it:
        if it["static"] not in static_cache:
            static_cache[it["static"]] = load_static(it["static"])
        U, tri = static_cache[it["static"]]
        tri = tri.copy()   # 向きを直すときに、写しを書き換える（読み込んだ物はそのまま）
        part = np.zeros(len(tri), np.int64)
    else:
        d = np.load(it["mesh"])
        P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
        U = P
        n_in = len(P)
        part = np.zeros(len(tri), np.int64)
        # 外の海（P3 の主役の範囲の外を P2 の網目で描く）。video_common.load_frame と同じ決め方：
        # 抜く範囲 hole（"auto" は内の網目の x・z の外枠）の外に頂点が一つでもある三角形を残す（境目は少し重ねる）
        for ex in it.get("extra") or []:
            de = np.load(ex["mesh"])
            Po = de["P"].astype(np.float64); to = de["tri"].astype(np.int64)
            h = ex.get("hole", "auto")
            if h == "auto" or h is None:
                h = [P[:, 0].min(), P[:, 0].max(), P[:, 2].min(), P[:, 2].max()]
            inside = (Po[:, 0] > h[0]) & (Po[:, 0] < h[1]) & (Po[:, 2] > h[2]) & (Po[:, 2] < h[3])
            to = to[~inside[to].all(1)]
            part = np.concatenate([part, np.full(len(to), part.max() + 1 if len(part) else 1, np.int64)])
            tri = np.concatenate([tri, to + len(U)])
            U = np.concatenate([U, Po])
    db = it.get("drop_below_y")
    if db is not None and "static" not in it:
        # 深い所の面（網目を切った高さの底の蓋・主役の範囲の縁の壁の下の方）を捨てる（回り台で箱を切ったときに厚い板に見えないように）
        keep = ~(U[:, 1] < db)[tri].all(1)
        tri = tri[keep]; part = part[keep]
    xf = it.get("xf")
    crop = it.get("crop")
    if crop and xf:
        # 頂（anchor）からの計算の座標の箱で切る：{"x": [lo, hi], "z": [lo, hi]}。箱の外に頂点がある三角形を捨てる
        a = xf["anchor"]
        ok = np.ones(len(U), bool)
        if "x" in crop:
            ok &= (U[:, 0] >= a[0] + crop["x"][0]) & (U[:, 0] <= a[0] + crop["x"][1])
        if "z" in crop:
            ok &= (U[:, 2] >= a[2] + crop["z"][0]) & (U[:, 2] <= a[2] + crop["z"][1])
        keep = ok[tri].all(1)
        tri = tri[keep]; part = part[keep]
    if xf:
        T = np.array(xf["T"]); E = np.array(xf["E"]); O = np.array(xf["O"]); s = float(xf["s"]); a = xf["anchor"]
        Q = U - np.array([a[0], 0.0, a[2]])
        U = O + s * (Q[:, 0:1] * T + Q[:, 1:2] * np.array([0.0, 1.0, 0.0]) + Q[:, 2:3] * E)
    B = np.stack([U[:, 0], U[:, 2], U[:, 1]], 1)
    flip = it.get("flip", job.get("flip", "auto"))
    # 面の向きをそろえる（部分ごと：主役の範囲 P3 と外の海 P2 は網目の作り方が違い、三角形の向きが逆のことがある）。
    # 静かな水面より上の、上か下を向いた三角形の面積で重みをつけた法線の z（Blender の上）の符号。下向きが多ければその部分を反転する。
    flips = []
    for k in np.unique(part):
        sel_k = part == k
        if flip == "auto":
            q = B[tri[sel_k]]
            n = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])
            sel = (q[:, :, 2].mean(1) > 0.5) & (np.abs(n[:, 2]) > 0.5 * np.linalg.norm(n, axis=1))
            fk = bool(sel.any() and n[sel, 2].sum() < 0)
        else:
            fk = bool(flip)
        if fk:
            tri[sel_k] = tri[sel_k][:, ::-1]
        flips.append(fk)
    print("VIDEO_BL orient %s flip=%s" % (it.get("mesh", it.get("static", ""))[-30:], flips))
    vcol = None
    if it.get("extra") and OUTER_TINT is not None:
        vcol = np.tile(np.array(CLAY, float), (len(B), 1))
        vcol[n_in:] = OUTER_TINT
    if job.get("two_sided") and "static" not in it and len(tri):
        # 裏の面も粘土に見せる：向きを逆にした写しを、点の法線に沿って少し内側（two_sided_offset m）に置く。
        # 網目は水面の一枚の膜（薄い唇・切り口の所で裏が見える）なので、MatCap の裏の色（暗い茶）が出ないようにする。形は変えない
        q = B[tri]
        fn = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])
        vn = np.zeros_like(B)
        for k in range(3):
            for c in range(3):
                vn[:, c] += np.bincount(tri[:, k], weights=fn[:, c], minlength=len(B))
        vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
        off = float(job.get("two_sided_offset", 0.05))
        tri = np.concatenate([tri, tri[:, ::-1] + len(B)])
        B = np.concatenate([B, B - off * vn])
        if vcol is not None:
            vcol = np.concatenate([vcol, vcol])
    sh.color_type = "VERTEX" if vcol is not None else "SINGLE"
    set_mesh(B, tri, vcol)
    for c in it["cams"]:
        if c["name"] not in outs:
            continue
        sc.camera = get_cam(c)
        os.makedirs(os.path.dirname(outs[c["name"]]), exist_ok=True)
        sc.render.filepath = outs[c["name"]]
        bpy.ops.render.render(write_still=True)
        n_img += 1
    print("VIDEO_BL item %d/%d %.2f s" % (i + 1, len(job["items"]), time.time() - t0)); sys.stdout.flush()
print("VIDEO_BL DONE images=%d wall=%.1f s" % (n_img, time.time() - t_all))
