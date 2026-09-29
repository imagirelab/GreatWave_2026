# -*- coding: utf-8 -*-
"""設計28修正01（kstar_h）：候補の粘土の描画（Blender 5.2 Workbench、cavity）。第 3 回と同じ粘土・光・海・視点。
Tools/GWWaveGen/kstar3/fin2_bl.py と candA3b_bl.py（第 3 回）を写して、入力に OBJ を加えたもの：
  * GWW0（.gwb）か OBJ（Unity 座標。coords=houdini なら Houdini 座標の OBJ を z 反転して読む）
  * 400×240 の格子（頂点 96,000）なら第 2・3 回と同じ「格子の縁につないだ海の輪＋海に掛けた 5 m の格子」、
    格子でない形（参照モデルの大きな形など）は y = 0 の平らな海の円盤の上に置く
  * 視点 = 9 つの標準（v1〜v9）＋ 利用者の Q21 の失敗の視点 u10〜u13（kh_views.json）
usage:
  blender --background --factory-startup --python-exit-code 1 --python kh_bl.py -- views <out_dir>
          <label=path>[,<label=path>...] [views=all|std|user|v1_painting,...] [scale=1.0] [coords=unity|houdini]
  blender ... -- turntable <path> <out.mp4|none> <stills_dir> [n_frames=240] [radius=72] [elev=16] [w=1280] [h=720] [coords=unity]
"""
import bpy
import sys
import os
import json
import math
import time
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
MODE = argv[0]
HERE = os.path.dirname(os.path.abspath(__file__))
KROWS = r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\ArtFirst\26修正01\kstar\kstar_a45_rows.npz"
VIEWS = os.path.join(HERE, "kh_views.json")
E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187]); UP = np.array([0, 1.0, 0])
SEAT = np.array([3.954, 1.832, -15.031])
CLAY = np.array([0.74, 0.69, 0.62]); SEA = np.array([0.50, 0.53, 0.56]); GRID = np.array([0.36, 0.38, 0.41])
t0 = time.time()
OPTS = {k: v for k, v in (a.split("=", 1) for a in argv if "=" in a and a.split("=", 1)[0] in ("views", "scale", "coords"))}
COORDS = OPTS.get("coords", "unity")


def u2b(P):
    P = np.asarray(P, np.float64); return np.stack([P[..., 0], P[..., 2], P[..., 1]], -1)


def read_gwb(path):
    b = open(path, "rb").read()
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4"); ntri = int(np.frombuffer(b[28:32], "<i4")[0]); n = int(nu) * int(nv)
    o = 32 + n * 16
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    return int(nu), int(nv), tris, X


def read_obj(path, coords):
    V, F = [], []
    with open(path, "rb") as f:
        for line in f:
            if line.startswith(b"v "):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith(b"f "):
                idx = [int(t.split(b"/")[0]) for t in line.split()[1:]]
                idx = [i - 1 if i > 0 else len(V) + i for i in idx]
                for k in range(1, len(idx) - 1):
                    F.append([idx[0], idx[k], idx[k + 1]])
    V = np.array(V, np.float64); F = np.array(F, np.int64)
    if coords == "houdini":
        V = V * np.array([1.0, 1.0, -1.0])       # Houdini -> Unity (kh_common の約束)
    return V, F


def mesh_obj(sc, name, V_u, F, cols):
    me = bpy.data.meshes.new(name)
    vb = u2b(V_u).astype(np.float32)
    FF = np.asarray(F)[:, [0, 2, 1]]
    me.vertices.add(len(vb)); me.vertices.foreach_set("co", vb.ravel())
    me.loops.add(FF.size); me.loops.foreach_set("vertex_index", FF.astype(np.int32).ravel())
    me.polygons.add(len(FF)); me.polygons.foreach_set("loop_start", np.arange(0, FF.size, 3, dtype=np.int32))
    me.update(); me.validate()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    ca = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    cc = np.c_[np.asarray(cols, np.float32), np.ones(len(vb), np.float32)]
    ca.data.foreach_set("color", cc.ravel())
    me.color_attributes.active_color = ca
    try:
        me.color_attributes.render_color_index = 0
    except Exception:
        pass
    mat = bpy.data.materials.new(name + "_m"); mat.diffuse_color = (0.74, 0.69, 0.62, 1); mat.roughness = 0.55
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); return ob


def height_colour(y):
    t = np.clip((y - 0.15) / 1.25, 0.0, 1.0); t = t * t * (3 - 2 * t)
    return SEA[None, :] * (1 - t[:, None]) + CLAY[None, :] * t[:, None]


def sec(P):
    Q = np.atleast_2d(P) - O
    return np.c_[Q @ T, Q[:, 1], Q @ E]


def ribbon(V, F, pts, w):
    if len(pts) < 2:
        return
    d = np.gradient(pts, axis=0); d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    s = np.cross(d, UP); s /= np.maximum(np.linalg.norm(s, axis=1, keepdims=True), 1e-9)
    k = len(V)
    for p, q in zip(pts - s * w / 2, pts + s * w / 2):
        V.append(p); V.append(q)
    for i in range(len(pts) - 1):
        a, b, c, e = k + 2 * i, k + 2 * i + 1, k + 2 * i + 3, k + 2 * i + 2
        F.append([a, b, c]); F.append([a, c, e])


def build_sea(sc, name, nu, nv, X):
    """第 2・3 回と同じ：格子の縁につないだ平らな海の輪＋海の部分に掛けた 5 m の格子。"""
    G = X.reshape(nv, nu, 3)
    S = sec(X).reshape(nv, nu, 3)
    loop = np.concatenate([G[0, :], G[1:, -1], G[-1, -2::-1], G[-2:0:-1, 0]])
    cen = np.array([loop[:, 0].mean(), 0.0, loop[:, 2].mean()])
    n = len(loop)
    rings = [loop]
    for k in (1.01, 1.04, 1.1, 1.25, 1.5, 2.0, 3.0, 5.0, 9.0, 16.0, 30.0):
        q = cen + (loop - cen) * np.array([k, 0.0, k]); q[:, 1] = 0.0; rings.append(q)
    V = np.concatenate(rings); F = []
    for m in range(len(rings) - 1):
        o0, o1 = m * n, (m + 1) * n
        for i in range(n):
            j = (i + 1) % n
            F.append([o0 + i, o0 + j, o1 + j]); F.append([o0 + i, o1 + j, o1 + i])
    ob = mesh_obj(sc, name + "_sea", V, np.array(F), np.tile(SEA, (len(V), 1)))
    ob.data.polygons.foreach_set("use_smooth", np.zeros(len(ob.data.polygons), bool))
    GV, GF = [], []
    A, Y, C = S[..., 0], S[..., 1], S[..., 2]
    lift = 0.035
    back_end = np.array([int(np.argmax(Y[r] > 0.6)) if (Y[r] > 0.6).any() else nu // 2 for r in range(nv)])
    front_beg = np.array([nu - 1 - int(np.argmax(Y[r, ::-1] > 0.6)) if (Y[r] > 0.6).any() else nu // 2 for r in range(nv)])
    for g in range(-60, 61, 5):
        w = 0.10 if g % 10 else 0.22
        for part in ("back", "front"):
            pts = []
            for r in range(nv):
                js = np.arange(0, max(back_end[r], 1)) if part == "back" else np.arange(min(front_beg[r] + 1, nu - 1), nu)
                a = A[r, js]
                if len(js) < 2 or not (a.min() <= g <= a.max()) or np.any(np.diff(a) <= 0):
                    if len(pts) > 1:
                        ribbon(GV, GF, np.array(pts), w)
                    pts = []
                    continue
                y = np.interp(g, a, Y[r, js]); cc = C[r, 0]
                pts.append(O + g * T + (y + lift) * UP + cc * E)
            if len(pts) > 1:
                ribbon(GV, GF, np.array(pts), w)
        cr = C[:, 0]
        if cr.min() <= g <= cr.max():
            r1 = int(np.searchsorted(cr, g)); r0 = max(r1 - 1, 0); r1 = min(r1, nv - 1)
            t = 0.0 if r1 == r0 else (g - cr[r0]) / (cr[r1] - cr[r0])
            aa = (1 - t) * A[r0] + t * A[r1]; yy = (1 - t) * Y[r0] + t * Y[r1]
            b = min(back_end[r0], back_end[r1]); f = max(front_beg[r0], front_beg[r1])
            for js in (np.arange(0, max(b, 1)), np.arange(min(f + 1, nu - 1), nu)):
                if len(js) > 1:
                    pts = O[None] + aa[js, None] * T + (yy[js, None] + lift) * UP + g * E
                    ribbon(GV, GF, pts, w)
    a_lo, a_hi = A[:, 0].max(), A[:, -1].min(); c_lo, c_hi = C[0, 0], C[-1, 0]
    L = 150.0
    for g in range(-150, 151, 5):
        w = 0.10 if g % 10 else 0.22
        segs = [(-L, L)] if not (a_lo <= g <= a_hi) else [(-L, c_lo), (c_hi, L)]
        for s0, s1 in segs:
            cc = np.linspace(s0, s1, 40); ribbon(GV, GF, O[None] + g * T + lift * UP + cc[:, None] * E, w)
        segs = [(-L, L)] if not (c_lo <= g <= c_hi) else [(-L, a_lo), (a_hi, L)]
        for s0, s1 in segs:
            aa = np.linspace(s0, s1, 40); ribbon(GV, GF, O[None] + aa[:, None] * T + lift * UP + g * E, w)
    if GV:
        mesh_obj(sc, name + "_grid", np.array(GV), np.array(GF), np.tile(GRID, (len(GV), 1)))


def build_plain_sea(sc, name):
    """格子でない形のための平らな海の円盤（y = 0、半径 300 m）と 5 m の格子。"""
    n = 96
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    V = [O.copy()] + [O + r * (math.cos(t) * T + math.sin(t) * E) for r in (40.0, 120.0, 300.0) for t in ang]
    V = np.array(V); F = []
    for i in range(n):
        F.append([0, 1 + (i + 1) % n, 1 + i])
    for ring in range(2):
        o0, o1 = 1 + ring * n, 1 + (ring + 1) * n
        for i in range(n):
            j = (i + 1) % n
            F.append([o0 + i, o1 + j, o0 + j]); F.append([o0 + i, o1 + i, o1 + j])
    ob = mesh_obj(sc, name + "_sea", V, np.array(F), np.tile(SEA, (len(V), 1)))
    ob.data.polygons.foreach_set("use_smooth", np.zeros(len(ob.data.polygons), bool))
    GV, GF = [], []
    for g in range(-150, 151, 5):
        w = 0.10 if g % 10 else 0.22
        cc = np.linspace(-150, 150, 60)
        ribbon(GV, GF, O[None] + g * T + 0.035 * UP + cc[:, None] * E, w)
        ribbon(GV, GF, O[None] + cc[:, None] * T + 0.035 * UP + g * E, w)
    mesh_obj(sc, name + "_grid", np.array(GV), np.array(GF), np.tile(GRID, (len(GV), 1)))


def add_candidate(sc, name, path):
    if path.lower().endswith(".gwb"):
        nu, nv, tris, X = read_gwb(path)
    else:
        X, tris = read_obj(path, COORDS)
        nu = nv = None
        if len(X) == 400 * 240:
            nu, nv = 400, 240
    mesh_obj(sc, name, X, tris, height_colour(X[:, 1]))
    if nu:
        build_sea(sc, name, nu, nv, X)
    else:
        build_plain_sea(sc, name)
    return [o for o in sc.collection.objects if o.name.startswith(name)]


def look_cam(sc, name, pos_u, tgt_u, vfov, ortho=None):
    cd = bpy.data.cameras.new(name); cd.sensor_fit = "VERTICAL"; cd.sensor_height = 24.0
    if ortho:
        cd.type = "ORTHO"; cd.ortho_scale = ortho
    else:
        cd.lens = 12.0 / math.tan(math.radians(vfov) / 2.0)
    cd.clip_start = 0.2; cd.clip_end = 3000
    ob = bpy.data.objects.new(name, cd); sc.collection.objects.link(ob)
    p = Vector(u2b(pos_u).tolist()); t = Vector(u2b(tgt_u).tolist())
    ob.location = p; ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = (t - p).to_track_quat("-Z", "Y")
    return ob


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.image_settings.file_format = "PNG"; sc.display.render_aa = "8"
    sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "VERTEX"; sh.show_cavity = True; sh.cavity_type = "WORLD"
    sh.show_shadows = False; sh.show_specular_highlight = True; sh.show_backface_culling = False
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("sky"); w.color = (0.62, 0.72, 0.84); sc.world = w
    return sc


def all_views(sc):
    z = np.load(KROWS); a_tip, y_tip = float(z["A"][159, 200]), float(z["Y"][159, 200])
    LIP = O + a_tip * T + y_tip * UP
    C0 = O + np.array([0, 9.0, 0])
    VJ = json.load(open(VIEWS, encoding="utf-8"))
    views = {
        "v1_painting": (look_cam(sc, "v1", np.array([0, 3.0, -62.0]), np.array([-2.5, 9.7, 4.0]), 26), (1280, 720)),
        "v2_seat": (look_cam(sc, "v2", SEAT, LIP, 80), (1280, 720)),
        "v3_side_along_crest_cam_side": (look_cam(sc, "v3", O - 130 * E + [0, 10, 0], O + [0, 10, 0], 24), (1280, 720)),
        "v4_true_side_perp_crest_front": (look_cam(sc, "v4", O + 130 * T + [0, 10, 0], O + [0, 10, 0], 30), (1280, 720)),
        "v5_back_three_quarter": (look_cam(sc, "v5", C0 + 75 * (-0.62 * T + 0.78 * E) + [0, 22, 0], C0, 40), (1280, 720)),
        "v6_top_down": (look_cam(sc, "v6", O + [0, 200, 0], O, 0, ortho=80), (1100, 1000)),
    }
    for v in VJ["standard"]:
        if v["name"] not in views:
            views[v["name"]] = (look_cam(sc, v["name"], np.array(v["eye"]), np.array(v["tgt"]), v["vfov"]), (v["w"], v["h"]))
    for v in VJ["user_failure"]:
        views[v["name"]] = (look_cam(sc, v["name"], np.array(v["eye"]), np.array(v["tgt"]), v["vfov"]), (v["w"], v["h"]))
    cam = views["v6_top_down"][0]
    xv = Vector(u2b(T).tolist()); yv = Vector(u2b(E).tolist()); zv = xv.cross(yv)
    cam.rotation_mode = "QUATERNION"; cam.rotation_quaternion = Matrix((xv, yv, zv)).transposed().to_quaternion()
    std = [v["name"] for v in VJ["standard"]]; usr = [v["name"] for v in VJ["user_failure"]]
    return views, LIP, std, usr


def views_mode():
    OUT = argv[1]
    items = [x.split("=", 1) for x in argv[2].split(",")]
    sel = OPTS.get("views", "all")
    SCALE = float(OPTS.get("scale", "1.0"))
    sc = scene()
    groups = {lab: add_candidate(sc, lab, p) for lab, p in items}
    views, LIP, std, usr = all_views(sc)
    if sel == "all":
        VSEL = std + usr
    elif sel == "std":
        VSEL = std
    elif sel == "user":
        VSEL = usr
    else:
        VSEL = sel.split("+")
    os.makedirs(OUT, exist_ok=True)
    for lab, obs in groups.items():
        for l2, o2 in groups.items():
            for o in o2:
                o.hide_render = (l2 != lab)
        for vn in VSEL:
            cam, res = views[vn]
            sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = int(res[0] * SCALE), int(res[1] * SCALE)
            sc.render.filepath = os.path.join(OUT, "%s__%s.png" % (lab, vn))
            bpy.ops.render.render(write_still=True)
            print("R", lab, vn, round(time.time() - t0, 1), flush=True)
        json.dump({"lip_tip_world_v2_target": LIP.tolist(), "seat": SEAT.tolist(), "views": VSEL, "input": dict(items)[lab], "coords": COORDS,
                   "views_json": VIEWS, "renderer": "Blender Workbench clay (kh_bl.py, copy of fin2_bl.py/candA3b_bl.py + OBJ input)"},
                  open(os.path.join(OUT, "views_meta_%s.json" % lab), "w", encoding="utf-8"), indent=1)
    print("done", time.time() - t0)


def turntable_mode():
    PATH, MP4, STILLS = argv[1], argv[2], argv[3]
    pos = [a for a in argv[4:] if "=" not in a]
    NF = int(pos[0]) if len(pos) > 0 else 240
    RAD = float(pos[1]) if len(pos) > 1 else 72.0
    EL = float(pos[2]) if len(pos) > 2 else 16.0
    W = int(pos[3]) if len(pos) > 3 else 1280
    H = int(pos[4]) if len(pos) > 4 else 720
    sc = scene()
    add_candidate(sc, "cand", PATH)
    cd = bpy.data.cameras.new("cam"); cd.sensor_fit = "VERTICAL"; cd.sensor_height = 24.0
    cd.lens = 12.0 / math.tan(math.radians(34) / 2.0); cd.clip_start = 0.2; cd.clip_end = 3000
    cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = W, H
    C0 = O + np.array([0, 9.0, 0])
    pc = np.array([0.0, 3.0, -62.0]) - C0; az0 = math.atan2(pc[2], pc[0])
    cam.rotation_mode = "QUATERNION"

    def place(f):
        az = az0 + 2 * math.pi * f / NF
        eye = C0 + np.array([RAD * math.cos(math.radians(EL)) * math.cos(az), RAD * math.sin(math.radians(EL)),
                             RAD * math.cos(math.radians(EL)) * math.sin(az)])
        p = Vector(u2b(eye).tolist()); t = Vector(u2b(C0).tolist())
        cam.location = p; cam.rotation_quaternion = (t - p).to_track_quat("-Z", "Y")
    os.makedirs(STILLS, exist_ok=True)
    sc.render.image_settings.file_format = "PNG"
    for f in range(0, NF, NF // 12):
        place(f)
        sc.render.filepath = os.path.join(STILLS, "f_%04d.png" % f)
        bpy.ops.render.render(write_still=True)
    if MP4 in ("", "none"):
        return
    for f in range(NF):
        sc.frame_set(f + 1); place(f)
        cam.keyframe_insert("location", frame=f + 1); cam.keyframe_insert("rotation_quaternion", frame=f + 1)
    sc.frame_start, sc.frame_end = 1, NF
    sc.render.fps = 30
    ims = sc.render.image_settings
    if hasattr(ims, "media_type"):
        ims.media_type = "VIDEO"
    ims.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
    try:
        sc.render.ffmpeg.constant_rate_factor = "MEDIUM"; sc.render.ffmpeg.ffmpeg_preset = "GOOD"
    except Exception as e:
        print("ffmpeg opts", e)
    sc.render.filepath = MP4
    bpy.ops.render.render(animation=True)
    print("done", NF, time.time() - t0)


if MODE == "views":
    views_mode()
elif MODE == "turntable":
    turntable_mode()
else:
    raise SystemExit("mode?")
