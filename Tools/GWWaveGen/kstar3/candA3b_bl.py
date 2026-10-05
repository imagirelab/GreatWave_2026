# -*- coding: utf-8 -*-
"""Q21 candidate A3b (copy of fin2_bl.py + the user's Q21 failure viewpoints U10..U13 from
Unity/Build/Q20L3/candA3b/views_q21_user.json, rendered with the same clay / light / sea).
Q20 final K*' (loop 2): clay renders of GWW0 sheets on an open clay sea (Blender Workbench, cavity on).

Differences from fin_bl_views.py (loop 1): the separate water plane at y = -0.03 hid the new front trough (it showed as
dark holes) and made the sheet's rectangle visible.  Here the sea outside the sheet is a flat ring joined to the sheet's
boundary (no gap, no plane over the trough), the sheet is coloured by height (sea tone below ~0.2 m -> clay above
~1.4 m), and the 5 m grid is draped on the sea surface (so the trough reads as a dip in the grid).  Cameras, light and
clay are those of the rubric views (Unity/Build/Q20/rubric/tools/bl_rubric_views.py).  Model-free: renders only .gwb.

usage: blender --background --factory-startup --python-exit-code 1 --python fin2_bl.py -- views <out_dir>
          <label=sheet.gwb>[,<label=sheet.gwb>...] [views=all|v1_painting,...] [scale=1.0]
       blender ... -- turntable <sheet.gwb> <out.mp4> <stills_dir> [n_frames=240] [radius=72] [elev=16] [w=1280] [h=720]
"""
import bpy, sys, os, json, math, time
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
MODE = argv[0]
KROWS = r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\ArtFirst\26修正01\kstar\kstar_a45_rows.npz"
VIEWS_USER = r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\Q20\rubric\tools\views_user.json"
E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187]); UP = np.array([0, 1.0, 0])
SEAT = np.array([3.954, 1.832, -15.031])
CLAY = np.array([0.74, 0.69, 0.62]); SEA = np.array([0.50, 0.53, 0.56]); GRID = np.array([0.36, 0.38, 0.41])
t0 = time.time()


def u2b(P):
    P = np.asarray(P, np.float64); return np.stack([P[..., 0], P[..., 2], P[..., 1]], -1)


def read_gwb(path):
    b = open(path, "rb").read()
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4"); ntri = int(np.frombuffer(b[28:32], "<i4")[0]); n = int(nu) * int(nv)
    o = 32 + n * 16
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    return int(nu), int(nv), tris, X


def mesh_obj(sc, name, V_u, F, cols):
    """triangle mesh (Unity coords), per-vertex colours (n, 3) -> object with a point colour attribute."""
    me = bpy.data.meshes.new(name)
    vb = u2b(V_u).astype(np.float32)
    FF = F[:, [0, 2, 1]]
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
    """flat ribbon along a polyline (world), width w, lying roughly on the surface (horizontal side vector)."""
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
    """flat sea ring around the sheet boundary + a 5 m grid draped on the sheet's sea parts and on the ring."""
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
    # draped grid on the sheet's sea parts (columns from each end up to where the surface rises above 0.6 m)
    GV, GF = [], []
    A, Y, C = S[..., 0], S[..., 1], S[..., 2]
    lift = 0.035
    back_end = np.array([int(np.argmax(Y[r] > 0.6)) if (Y[r] > 0.6).any() else nu // 2 for r in range(nv)])
    front_beg = np.array([nu - 1 - int(np.argmax(Y[r, ::-1] > 0.6)) if (Y[r] > 0.6).any() else nu // 2 for r in range(nv)])
    for g in range(-60, 61, 5):
        w = 0.10 if g % 10 else 0.22
        # constant a lines (along the crest)
        for part in ("back", "front"):
            pts = []
            for r in range(nv):
                if part == "back":
                    js = np.arange(0, max(back_end[r], 1))
                else:
                    js = np.arange(min(front_beg[r] + 1, nu - 1), nu)
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
        # constant c lines (across the crest)
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
    # grid on the ring (outside the sheet's footprint rectangle in a / c)
    a_lo, a_hi = A[:, 0].max(), A[:, -1].min(); c_lo, c_hi = C[0, 0], C[-1, 0]
    L = 150.0
    for g in range(-150, 151, 5):
        w = 0.10 if g % 10 else 0.22
        # constant a: c from -L..L outside [c_lo, c_hi] if a inside the sheet's a range
        segs = [(-L, L)] if not (a_lo <= g <= a_hi) else [(-L, c_lo), (c_hi, L)]
        for s0, s1 in segs:
            cc = np.linspace(s0, s1, 40); ribbon(GV, GF, O[None] + g * T + lift * UP + cc[:, None] * E, w)
        segs = [(-L, L)] if not (c_lo <= g <= c_hi) else [(-L, a_lo), (a_hi, L)]
        for s0, s1 in segs:
            aa = np.linspace(s0, s1, 40); ribbon(GV, GF, O[None] + aa[:, None] * T + lift * UP + g * E, w)
    if GV:
        mesh_obj(sc, name + "_grid", np.array(GV), np.array(GF), np.tile(GRID, (len(GV), 1)))


def add_sheet(sc, name, gwb):
    nu, nv, tris, X = read_gwb(gwb)
    ob = mesh_obj(sc, name, X, tris, height_colour(X[:, 1]))
    build_sea(sc, name, nu, nv, X)
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


def views_mode():
    OUT = argv[1]
    items = [x.split("=", 1) for x in argv[2].split(",")]
    VSEL = argv[3].split(",") if len(argv) > 3 and argv[3] not in ("", "all") else None
    SCALE = float(argv[4]) if len(argv) > 4 else 1.0
    sc = scene()
    groups = {lab: add_sheet(sc, lab, p) for lab, p in items}
    z = np.load(KROWS); a_tip, y_tip = float(z["A"][159, 200]), float(z["Y"][159, 200])
    LIP = O + a_tip * T + y_tip * UP
    C0 = O + np.array([0, 9.0, 0])
    TV = json.load(open(VIEWS_USER, encoding="utf-8"))
    views = {
        "v1_painting": (look_cam(sc, "v1", np.array([0, 3.0, -62.0]), np.array([-2.5, 9.7, 4.0]), 26), (1280, 720)),
        "v2_seat": (look_cam(sc, "v2", SEAT, LIP, 80), (1280, 720)),
        "v3_side_along_crest_cam_side": (look_cam(sc, "v3", O - 130 * E + [0, 10, 0], O + [0, 10, 0], 24), (1280, 720)),
        "v4_true_side_perp_crest_front": (look_cam(sc, "v4", O + 130 * T + [0, 10, 0], O + [0, 10, 0], 30), (1280, 720)),
        "v5_back_three_quarter": (look_cam(sc, "v5", C0 + 75 * (-0.62 * T + 0.78 * E) + [0, 22, 0], C0, 40), (1280, 720)),
        "v6_top_down": (look_cam(sc, "v6", O + [0, 200, 0], O, 0, ortho=80), (1100, 1000)),
    }
    for v in TV:
        views[v["name"]] = (look_cam(sc, v["name"], np.array(v["eye"]), np.array(v["tgt"]), v["vfov"]), (1100, 1000))
    VQ = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20L3/candA3b/views_q21_user.json"
    if os.path.isfile(VQ):
        for v in json.load(open(VQ, encoding="utf-8")):
            views[v["name"]] = (look_cam(sc, v["name"], np.array(v["eye"]), np.array(v["tgt"]), v["vfov"]), (v["w"], v["h"]))
    cam = views["v6_top_down"][0]
    xv = Vector(u2b(T).tolist()); yv = Vector(u2b(E).tolist()); zv = xv.cross(yv)
    cam.rotation_mode = "QUATERNION"; cam.rotation_quaternion = Matrix((xv, yv, zv)).transposed().to_quaternion()
    os.makedirs(OUT, exist_ok=True)
    for lab, obs in groups.items():
        for l2, o2 in groups.items():
            for o in o2:
                o.hide_render = (l2 != lab)
        for vn, (cam, res) in views.items():
            if VSEL and vn not in VSEL:
                continue
            sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = int(res[0] * SCALE), int(res[1] * SCALE)
            sc.render.filepath = os.path.join(OUT, "%s__%s.png" % (lab, vn))
            bpy.ops.render.render(write_still=True)
            print("R", lab, vn, round(time.time() - t0, 1), flush=True)
        json.dump({"lip_tip_world": LIP.tolist(), "seat": SEAT.tolist(), "views": list(views.keys()), "gwb": dict(items)[lab],
                   "sea": "flat clay sea ring joined to the sheet boundary; grid draped on the sea (loop 2)"},
                  open(os.path.join(OUT, "views_meta_%s.json" % lab), "w", encoding="utf-8"), indent=1)
    print("done", time.time() - t0)


def turntable_mode():
    GWB, MP4, STILLS = argv[1], argv[2], argv[3]
    NF = int(argv[4]) if len(argv) > 4 else 240
    RAD = float(argv[5]) if len(argv) > 5 else 72.0
    EL = float(argv[6]) if len(argv) > 6 else 16.0
    W = int(argv[7]) if len(argv) > 7 else 1280
    H = int(argv[8]) if len(argv) > 8 else 720
    sc = scene()
    add_sheet(sc, "cand", GWB)
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
    print("done", NF)


if MODE == "views":
    views_mode()
elif MODE == "turntable":
    turntable_mode()
else:
    raise SystemExit("mode?")
