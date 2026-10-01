# -*- coding: utf-8 -*-
# 仕上げ28：粘土の確認用の描画（Blender Workbench、ヘッドレス）。設計28修正01 の試行F の最終の評審で使った描画の台本（作業場所の clay_render_f.py、
# SHA-256 は pl28 の run.json に記録）を、中身を変えずにリポジトリへ写したもの。E・F_final の粘土のこまと同じ設定で G_final のこまを描き、
# 同じ視点・同じ画面の時刻で並べる（pl28_clay_compose.py）。形と速さを見るためのもので、作品の色・線・白ではない。
# 使い方：blender --background --factory-startup --python-exit-code 1 --python pl28_clay_render.py -- --mode frames --kstar <K*′> --pkg <包み> --warp <時間曲線> --fine auto --out <出力> --views side_follow,seat_up30 --w 960 --h 540

"""(28R01F copy of the 28R01E renderer: adds view back34_follow = three-quarter view from behind the wave, follows O(tau))
(28R01E copy of the 28R01D clay renderer: adds --fine (reads the pos_lo_rgba8/1 precision layer when the package lists it) and --mode tstills --times (stills at screen times through the warp))
(28R01 copy: adds --stages) Clay review renders of the DS27-format keypose packages (Blender Workbench, background).
Review only; reads the repo read-only.

Usage:
  blender --background --factory-startup --python-exit-code 1 --python clay_render.py -- \
      --mode frames|stills|kstar --pkg <package dir> --warp <timewarp json> --out <dir> --views a,b,c [--step 1] [--fps 30]
Unity world (left-handed, Y up) -> Blender (right-handed, Z up): B = (x_u, z_u, y_u); winding flipped.
"""
import bpy
import sys
import os
import json
import math
import time
import numpy as np
from mathutils import Vector

REPO = r"G:\Unity\GreatWave_2026_Fresh"
KSTAR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45.gwb")
_ka = sys.argv[sys.argv.index("--kstar") + 1] if "--kstar" in sys.argv else None
if _ka:
    import glob as _glob
    _d = _ka if os.path.isabs(_ka) else os.path.join(REPO, _ka)
    KSTAR = sorted(_glob.glob(os.path.join(_d, "*.gwb")))[0]

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in argv:
        return argv[argv.index(name) + 1]
    return default


MODE = arg("--mode", "kstar")
PKG = arg("--pkg")
WARP = arg("--warp")
OUT = arg("--out")
VIEWS = arg("--views", "seat_toward_wave,seat_up30,side_fixed,side_follow,painting").split(",")
STEP = int(arg("--step", "1"))
FPS = float(arg("--fps", "30"))
TEND = 14.0
RES = (int(arg("--w", "1280")), int(arg("--h", "720")))
FSTART = int(arg("--fstart", "0"))
FEND = int(arg("--fend", "-1"))
STAGES = [("a", -4.433), ("b", -3.500), ("c", -2.933), ("d", -2.250), ("apex", -1.333), ("tstar", 0.0)]
if arg("--stages"):   # 28R01: e.g. a=-4.367,b=-3.517,...
    STAGES = [(kv.split("=")[0], float(kv.split("=")[1])) for kv in arg("--stages").split(",")]

# ---------------------------------------------------------------- package (same maths as ds27_player_ref.py)


def hermite_weights(knots, tau):
    n = len(knots)
    if tau <= knots[0]:
        return (0, 0, 0, 0), (0.0, 1.0, 0.0, 0.0)
    if tau >= knots[-1]:
        return (n - 1, n - 1, n - 1, n - 1), (0.0, 1.0, 0.0, 0.0)
    i1 = int(np.searchsorted(knots, tau, side="right") - 1)
    i1 = min(i1, n - 2)
    i2 = i1 + 1
    i0 = max(i1 - 1, 0)
    i3 = min(i2 + 1, n - 1)
    t1, t2 = knots[i1], knots[i2]
    D = t2 - t1
    s = (tau - t1) / D
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1
    h10 = s ** 3 - 2 * s ** 2 + s
    h01 = -2 * s ** 3 + 3 * s ** 2
    h11 = s ** 3 - s ** 2
    w = [0.0, h00, h01, 0.0]
    if i0 == i1:
        w[2] += h10
        w[1] -= h10
    else:
        f = h10 * D / (t2 - knots[i0])
        w[2] += f
        w[0] -= f
    if i3 == i2:
        w[2] += h11
        w[1] -= h11
    else:
        f = h11 * D / (knots[i3] - t1)
        w[3] += f
        w[1] -= f
    return (i0, i1, i2, i3), tuple(float(x) for x in w)


class Package:
    def __init__(self, d):
        with open(os.path.join(d, "ds27_keypose.json"), encoding="utf-8") as f:
            m = json.load(f)
        self.L, self.R, self.C = int(m["layers"]), int(m["rows"]), int(m["cols"])
        self.N = self.R * self.C
        raw = np.fromfile(os.path.join(d, "ds27_pos_rgba16.bin"), "<u2")
        assert raw.size == self.L * self.N * 4
        self.q = raw.reshape(self.L, self.N, 4)
        self.lo8 = None
        fine = arg("--fine", "auto")
        if m.get("pos_lo_file") and fine in ("auto", "1"):
            r8 = np.fromfile(os.path.join(d, m["pos_lo_file"]), np.uint8)
            assert r8.size == self.L * self.N * 4
            self.lo8 = r8.reshape(self.L, self.N, 4)
        print("PACKAGE", d, "layers", self.L, "fine" if self.lo8 is not None else "16-bit only", flush=True)
        self.lo = np.asarray(m["bbox_min"], np.float64)
        self.size = np.asarray(m["bbox_size"], np.float64)
        self.knots = np.asarray(m["knot_tau"], np.float64)
        self.ftau = np.asarray(m["frame"]["tau"], np.float64)
        self.forg = np.asarray(m["frame"]["origin"], np.float64).reshape(-1, 3)

    def layer_local(self, k):
        u = self.q[k, :, :3].astype(np.float64)
        if self.lo8 is not None:   # pos_lo_rgba8/1: p = bbox_min + (q16 + lo/255 - 0.5)/65535*bbox_size
            u = u + self.lo8[k, :, :3].astype(np.float64) / 255.0 - 0.5
        return self.lo[None, :] + u / 65535.0 * self.size[None, :]

    def local(self, tau):
        idx, w = hermite_weights(self.knots, tau)
        P = np.zeros((self.N, 3))
        for q in range(4):
            if w[q] != 0.0:
                P += w[q] * self.layer_local(idx[q])
        return P

    def origin(self, tau):
        return np.array([np.interp(tau, self.ftau, self.forg[:, a]) for a in range(3)])

    def world(self, tau):
        return self.local(tau) + self.origin(tau)[None, :]


def read_kstar():
    b = open(KSTAR, "rb").read()
    assert b[:4] == b"GWW0"
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4")
    ntri = int(np.frombuffer(b[28:32], "<i4")[0])
    n = int(nu) * int(nv)
    o = 32 + n * 16
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy()
    o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    return int(nu), int(nv), tris, X


def u2b(P):
    """Unity world -> Blender world."""
    P = np.asarray(P, np.float64)
    return np.stack([P[..., 0], P[..., 2], P[..., 1]], -1)


# ---------------------------------------------------------------- scene
T_U = np.array([0.7334, 0.0, -0.6798]); T_U /= np.linalg.norm(T_U)
N_U = np.array([-T_U[2], 0.0, T_U[0]])          # horizontal, perpendicular to t (+n side: lip profile unoccluded)
SEAT_EYE_U = np.array([3.954, 1.832, -15.031])
PAINT_POS_U = np.array([0.0, 3.0, -62.0])
PAINT_TGT_U = np.array([-2.5, 9.7, 4.0])
O_FOCUS_U = np.array([-7.2276859, 0.0, -2.7131699])   # O(0) (same in all three packages)
SIDE_DIST = 120.0
SIDE_H = 10.0
SIDE_SIGN = float(arg("--side_sign", "1"))


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.compression = 15
    sc.render.film_transparent = False
    sc.display.render_aa = "8"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor = 1.0
    sh.cavity_valley_factor = 1.0
    sh.curvature_ridge_factor = 0.6
    sh.curvature_valley_factor = 0.8
    sh.show_shadows = arg("--shadow", "0") == "1"
    sh.shadow_intensity = 0.35
    sc.display.light_direction = (0.45, -0.35, 0.82)   # set in Blender world axes
    sc.display.shadow_shift = 0.05
    sh.show_specular_highlight = True
    sh.use_world_space_lighting = arg("--wslight", "0") == "1"
    sl = arg("--studio", "")
    if sl:
        sh.studio_light = sl
    sh.studiolight_rotate_z = math.radians(float(arg("--lrot", "0")))
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    w = bpy.data.worlds.new("sky")
    w.color = (0.62, 0.72, 0.84)
    sc.world = w
    try:
        bpy.context.preferences.system.anisotropic_filter = "FILTER_16"
    except Exception:
        pass
    return sc


def solid_material(name, rgb):
    """Material with a tiny 1x1 image so TEXTURE colour mode shows a flat colour."""
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    mat.use_nodes = True
    nt = mat.node_tree
    img = bpy.data.images.new(name + "_px", 4, 4, alpha=False)
    img.pixels.foreach_set(np.tile(np.array([rgb[0], rgb[1], rgb[2], 1.0], np.float32), 16))
    img.pack()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is not None:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.nodes.active = tex
    return mat


def make_water(sc):
    size = 640.0
    cx_u, cz_u = -70.0, 60.0
    y_u = -0.03   # 3 cm below still water so the wave's flat edges (y = 0) never z-fight with the plane
    corners_u = np.array([[cx_u - size / 2, y_u, cz_u - size / 2], [cx_u + size / 2, y_u, cz_u - size / 2],
                          [cx_u + size / 2, y_u, cz_u + size / 2], [cx_u - size / 2, y_u, cz_u + size / 2]])
    vb = u2b(corners_u)
    me = bpy.data.meshes.new("water")
    me.from_pydata([tuple(v) for v in vb], [], [(0, 1, 2, 3)])
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    # UV: u along Unity x, v along Unity z
    for li, loop in enumerate(me.loops):
        c = corners_u[loop.vertex_index]
        uv.data[li].uv = ((c[0] - (cx_u - size / 2)) / size, (c[2] - (cz_u - size / 2)) / size)
    npx = 2048   # 0.3125 m per pixel, 10 m = 32 px
    base = WATER_RGB
    line = WATER_RGB + 0.09
    major = WATER_RGB + 0.16
    img = np.empty((npx, npx, 4), np.float32)
    img[..., :3] = base
    img[..., 3] = 1.0
    idx = np.arange(npx)
    minor = (idx % 32) == 0
    maj = (idx % 160) == 0
    maj2 = ((idx % 160) == 1)
    for sel, col in ((minor, line), (maj, major), (maj2, major)):
        img[sel, :, :3] = col
        img[:, sel, :3] = col
    im = bpy.data.images.new("grid", npx, npx, alpha=False)
    im.pixels.foreach_set(img.ravel())
    im.pack()
    mat = bpy.data.materials.new("water")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = im
    tex.interpolation = "Linear"
    bsdf = nt.nodes.get("Principled BSDF")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    try:
        bsdf.inputs["Roughness"].default_value = 1.0
    except Exception:
        pass
    nt.nodes.active = tex
    mat.roughness = 1.0
    mat.metallic = 0.0
    me.materials.append(mat)
    ob = bpy.data.objects.new("water", me)
    sc.collection.objects.link(ob)
    return ob


SKIRT_R = 320.0


def boundary_loop(nu, nv):
    top = [0 * nu + c for c in range(nu)]
    right = [r * nu + (nu - 1) for r in range(1, nv)]
    bot = [(nv - 1) * nu + c for c in range(nu - 2, -1, -1)]
    left = [r * nu + 0 for r in range(nv - 2, 0, -1)]
    return np.array(top + right + bot + left, np.int64)


def skirt_verts(V_u, loop):
    """inner ring = the sheet's own boundary vertices; outer ring = pushed out radially (horizontal) by SKIRT_R, y = -0.03."""
    B = np.asarray(V_u)[loop]
    cxz = B[:, [0, 2]].mean(0)
    d = B[:, [0, 2]] - cxz
    n = d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    Ou = np.stack([B[:, 0] + n[:, 0] * SKIRT_R, np.full(len(B), -0.03), B[:, 2] + n[:, 1] * SKIRT_R], 1)
    return np.concatenate([B, Ou], 0)


def make_skirt(sc, nu, nv, X):
    global SK_LOOP
    SK_LOOP = boundary_loop(nu, nv)
    n = len(SK_LOOP)
    V = skirt_verts(X, SK_LOOP)
    faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    me = bpy.data.meshes.new("water")
    me.from_pydata(u2b(V).tolist(), [], faces)
    me.update()
    me.uv_layers.new(name="UVMap")
    ob_tmp = make_water(sc)            # the original plane, only to build the grid material; then removed
    mat = ob_tmp.data.materials[0]
    bpy.data.objects.remove(ob_tmp, do_unlink=True)
    me.materials.append(mat)
    global SK_LVI
    SK_LVI = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", SK_LVI)
    set_skirt(me, V)
    ob = bpy.data.objects.new("water", me)
    sc.collection.objects.link(ob)
    return me


def set_skirt(me, V):
    size = 640.0
    cx_u, cz_u = -70.0, 60.0
    me.vertices.foreach_set("co", u2b(V).astype(np.float32).ravel())
    uv = np.stack([(V[SK_LVI, 0] - (cx_u - size / 2)) / size, (V[SK_LVI, 2] - (cz_u - size / 2)) / size], 1).astype(np.float32)
    me.uv_layers[0].data.foreach_set("uv", uv.ravel())
    me.update()


SK_LOOP = None
SK_LVI = None


def make_wave(sc, tris, V_u):
    me = bpy.data.meshes.new("wave")
    vb = u2b(V_u)
    faces = tris[:, [0, 2, 1]]   # flip winding for the handedness mirror
    me.from_pydata(vb.tolist(), [], faces.tolist())
    me.update()
    try:
        me.shade_smooth()
    except Exception:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    mat = bpy.data.materials.new("clay")
    mat.use_nodes = True
    nt = mat.node_tree
    ng = 64
    g = np.zeros((ng, 2, 4), np.float32)
    ramp = np.linspace(0, 1, ng)[:, None]
    g[:, :, :3] = (WATER_RGB[None, :] * (1 - ramp) + CLAY_RGB[None, :] * ramp)[:, None, :]
    g[..., 3] = 1
    im = bpy.data.images.new("clayramp", 2, ng, alpha=False)
    im.pixels.foreach_set(g.ravel())
    im.pack()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = im
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"
    bsdf = nt.nodes.get("Principled BSDF")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.nodes.active = tex
    mat.roughness = 0.55
    mat.metallic = 0.0
    me.materials.append(mat)
    me.uv_layers.new(name="UVMap")
    global LOOP_VI
    LOOP_VI = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", LOOP_VI)
    set_uv(me, V_u)
    ob = bpy.data.objects.new("wave", me)
    sc.collection.objects.link(ob)
    return ob, me


LOOP_VI = None
SK_ME = None


def set_uv(me, V_u):
    y = np.asarray(V_u)[:, 1]
    v = np.clip((y - H0) / (H1 - H0), 0.0, 1.0)
    ng = 64
    v = (0.5 + v * (ng - 1)) / ng   # texel centres
    uv = np.empty((LOOP_VI.size, 2), np.float32)
    uv[:, 0] = 0.5
    uv[:, 1] = v[LOOP_VI]
    me.uv_layers[0].data.foreach_set("uv", uv.ravel())


def set_wave(me, V_u):
    if SK_ME is not None:
        set_skirt(SK_ME, skirt_verts(V_u, SK_LOOP))
    vb = u2b(V_u).astype(np.float32)
    me.vertices.foreach_set("co", vb.ravel())
    set_uv(me, V_u)
    me.update()


def look_cam(sc, name, pos_u, tgt_u, vfov_deg, clip_start=0.3):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 24.0
    cd.lens = 12.0 / math.tan(math.radians(vfov_deg) / 2.0)
    cd.clip_start = clip_start
    cd.clip_end = 2000.0
    ob = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(ob)
    place_cam(ob, pos_u, tgt_u)
    return ob


def place_cam(ob, pos_u, tgt_u):
    p = Vector(u2b(pos_u).tolist())
    t = Vector(u2b(tgt_u).tolist())
    ob.location = p
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (t - p).to_track_quat("-Z", "Y")


def seat_target(pitch_deg):
    f = -T_U * math.cos(math.radians(pitch_deg)) + np.array([0, 1.0, 0]) * math.sin(math.radians(pitch_deg))
    return SEAT_EYE_U + 10.0 * f


WATER_RGB = np.array([float(x) for x in arg("--water", "0.50,0.505,0.515").split(",")])
CLAY_RGB = np.array([0.74, 0.69, 0.62])
H0, H1 = 0.05, 0.8   # wave colour: water grey at y <= H0 -> clay at y >= H1 (so the mesh's own flat sea apron reads as water)
SIDE_FIXED_VFOV = float(arg("--side_fixed_vfov", "50"))
SIDE_FOLLOW_VFOV = float(arg("--side_follow_vfov", "30"))


def side_pos(o_u):
    return o_u + SIDE_SIGN * SIDE_DIST * N_U + np.array([0.0, SIDE_H, 0.0])


F34_DIST = float(arg("--f34_dist", "95"))
F34_ANG = float(arg("--f34_ang", "50"))      # degrees from the side direction toward the travel direction (+T_U = the front)
F34_H = float(arg("--f34_h", "12"))
F34_TGT_H = float(arg("--f34_tgt_h", "9"))
F34_VFOV = float(arg("--f34_vfov", "24"))


def front34_pos(o_u):
    a = math.radians(F34_ANG)
    dvec = math.cos(a) * SIDE_SIGN * N_U + math.sin(a) * T_U
    return o_u + F34_DIST * dvec + np.array([0.0, F34_H, 0.0])


B34_DIST = float(arg("--b34_dist", "90"))
B34_ANG = float(arg("--b34_ang", "-65"))      # degrees from the side direction toward the travel direction (negative = behind the wave)
B34_H = float(arg("--b34_h", "18"))
B34_TGT_H = float(arg("--b34_tgt_h", "8"))
B34_VFOV = float(arg("--b34_vfov", "26"))


def back34_pos(o_u):
    a = math.radians(B34_ANG)
    dvec = math.cos(a) * SIDE_SIGN * N_U + math.sin(a) * T_U
    return o_u + B34_DIST * dvec + np.array([0.0, B34_H, 0.0])


def make_cams(sc, views):
    cams = {}
    for v in views:
        if v == "seat_toward_wave":
            cams[v] = look_cam(sc, v, SEAT_EYE_U, seat_target(0.0), 70.0, 0.3)
        elif v == "seat_up30":
            cams[v] = look_cam(sc, v, SEAT_EYE_U, seat_target(30.0), 70.0, 0.3)
        elif v == "side_fixed":
            cams[v] = look_cam(sc, v, side_pos(O_FOCUS_U), O_FOCUS_U, SIDE_FIXED_VFOV, 1.0)
        elif v == "side_follow":
            cams[v] = look_cam(sc, v, side_pos(O_FOCUS_U), O_FOCUS_U, SIDE_FOLLOW_VFOV, 1.0)
        elif v == "front34_follow":   # 28R01E close-ups: 3/4 view from ahead of the wave (front face), follows O(tau)
            cams[v] = look_cam(sc, v, front34_pos(O_FOCUS_U), O_FOCUS_U + np.array([0.0, F34_TGT_H, 0.0]), F34_VFOV, 1.0)
        elif v == "back34_follow":   # 28R01F: 3/4 view from behind the wave (the back), follows O(tau)
            cams[v] = look_cam(sc, v, back34_pos(O_FOCUS_U), O_FOCUS_U + np.array([0.0, B34_TGT_H, 0.0]), B34_VFOV, 1.0)
        elif v == "painting":
            cams[v] = look_cam(sc, v, PAINT_POS_U, PAINT_TGT_U, 26.0, 1.0)
        else:
            raise SystemExit("unknown view " + v)
    return cams


def render_to(sc, cam, path):
    """Render to a temp file, then rename, so a streaming consumer only ever sees complete PNGs."""
    sc.camera = cam
    tmp = os.path.join(os.path.dirname(path), "_tmp_render.png")
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    os.replace(tmp, path)


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    sc = reset_scene()
    nu, nv, tris, X = read_kstar()
    global SK_ME
    SK_ME = make_skirt(sc, nu, nv, X)
    os.makedirs(OUT, exist_ok=True)
    if MODE == "kstar":
        ob, me = make_wave(sc, tris, X)
        cams = make_cams(sc, VIEWS)
        for v, cam in cams.items():
            t1 = time.time()
            render_to(sc, cam, os.path.join(OUT, "kstar_%s.png" % v))
            print("RENDER", v, "%.2fs" % (time.time() - t1))
        print("DONE kstar %.1fs" % (time.time() - t0))
        return
    pk = Package(PKG)
    ob, me = make_wave(sc, tris, pk.world(0.0))
    cams = make_cams(sc, VIEWS)
    log = {"pkg": PKG, "warp": WARP, "views": VIEWS, "frames": []}
    if MODE == "stills":
        for name, tau in STAGES:
            set_wave(me, pk.world(tau))
            o = pk.origin(tau)
            for v, cam in cams.items():
                if v == "side_follow":
                    place_cam(cam, side_pos(o), o)
                elif v == "front34_follow":
                    place_cam(cam, front34_pos(o), o + np.array([0.0, F34_TGT_H, 0.0]))
                elif v == "back34_follow":
                    place_cam(cam, back34_pos(o), o + np.array([0.0, B34_TGT_H, 0.0]))
                d = os.path.join(OUT, v)
                os.makedirs(d, exist_ok=True)
                render_to(sc, cam, os.path.join(d, "stage_%s.png" % name))
        print("DONE stills %.1fs" % (time.time() - t0))
        return
    with open(WARP, encoding="utf-8") as f:
        w = json.load(f)
    wt, wtau = np.asarray(w["t"]), np.asarray(w["tau"])
    if MODE == "tstills":
        for t in [float(x) for x in arg("--times").split(",")]:
            tau = float(np.interp(t, wt, wtau))
            set_wave(me, pk.world(tau))
            o = pk.origin(tau)
            for v, cam in cams.items():
                if v == "side_follow":
                    place_cam(cam, side_pos(o), o)
                elif v == "front34_follow":
                    place_cam(cam, front34_pos(o), o + np.array([0.0, F34_TGT_H, 0.0]))
                elif v == "back34_follow":
                    place_cam(cam, back34_pos(o), o + np.array([0.0, B34_TGT_H, 0.0]))
                d = os.path.join(OUT, v)
                os.makedirs(d, exist_ok=True)
                render_to(sc, cam, os.path.join(d, "t_%04d.png" % int(round(t * 100))))
            log["frames"].append([t, tau])
        with open(os.path.join(OUT, "tstills.json"), "w", encoding="utf-8") as f:
            json.dump(log, f)
        print("DONE tstills %.1fs" % (time.time() - t0))
        return
    nfr = int(round(TEND * FPS))
    fend = nfr if FEND < 0 else min(FEND, nfr)
    for v in cams:
        os.makedirs(os.path.join(OUT, v), exist_ok=True)
    for i in range(FSTART, fend, STEP):
        t = i / FPS
        tau = float(np.interp(t, wt, wtau))
        set_wave(me, pk.world(tau))
        o = pk.origin(tau)
        for v, cam in cams.items():
            if v == "side_follow":
                place_cam(cam, side_pos(o), o)
            elif v == "front34_follow":
                place_cam(cam, front34_pos(o), o + np.array([0.0, F34_TGT_H, 0.0]))
            elif v == "back34_follow":
                place_cam(cam, back34_pos(o), o + np.array([0.0, B34_TGT_H, 0.0]))
            render_to(sc, cam, os.path.join(OUT, v, "f_%04d.png" % i))
        log["frames"].append([i, t, tau])
        if i % 30 == 0:
            print("FRAME %d t=%.3f tau=%.3f elapsed %.1fs" % (i, t, tau, time.time() - t0), flush=True)
    with open(os.path.join(OUT, "frames_%d_%d.json" % (FSTART, fend)), "w", encoding="utf-8") as f:
        json.dump(log, f)
    print("DONE frames %.1fs" % (time.time() - t0))


main()
