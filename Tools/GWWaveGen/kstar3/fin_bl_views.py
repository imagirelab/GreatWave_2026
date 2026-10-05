# -*- coding: utf-8 -*-
"""Q20 final K*': clay renders of a GWW0 sheet from the 9 standard review views of the Q20 rubric
(identical cameras, light and water plane to Unity/Build/Q20/rubric/tools/bl_rubric_views.py; Blender Workbench,
cavity on).  Model-free: it renders only the given .gwb files (the reference-model column of the comparison sheet
reuses the rubric's existing renders).
usage: blender --background --factory-startup --python-exit-code 1 --python fin_bl_views.py -- <out_dir> <label>
       <sheet.gwb> [views=all|v1_painting,...] [scale=1.0]
"""
import bpy, sys, os, json, math, time
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, LABEL, GWB = argv[0], argv[1], argv[2]
VSEL = argv[3].split(",") if len(argv) > 3 and argv[3] not in ("", "all") else None
SCALE = float(argv[4]) if len(argv) > 4 else 1.0
KROWS = r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\ArtFirst\26修正01\kstar\kstar_a45_rows.npz"
VIEWS_USER = r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\Q20\rubric\tools\views_user.json"
E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187]); UP = np.array([0, 1.0, 0])
SEAT = np.array([3.954, 1.832, -15.031])
t0 = time.time()


def u2b(P):
    P = np.asarray(P, np.float64); return np.stack([P[..., 0], P[..., 2], P[..., 1]], -1)


def read_gwb(path):
    b = open(path, "rb").read()
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4"); ntri = int(np.frombuffer(b[28:32], "<i4")[0]); n = int(nu) * int(nv)
    o = 32 + n * 16
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    return tris, X


def mesh_obj(sc, name, V_u, F, rgb, flip=True):
    me = bpy.data.meshes.new(name)
    vb = u2b(V_u).astype(np.float32)
    FF = F[:, [0, 2, 1]] if flip else F
    me.vertices.add(len(vb)); me.vertices.foreach_set("co", vb.ravel())
    me.loops.add(FF.size); me.loops.foreach_set("vertex_index", FF.astype(np.int32).ravel())
    me.polygons.add(len(FF)); me.polygons.foreach_set("loop_start", np.arange(0, FF.size, 3, dtype=np.int32))
    me.update(); me.validate()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    mat = bpy.data.materials.new(name + "_m"); mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1); mat.roughness = 0.55
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); return ob


def plane(sc, name, y_u, rgb, size=700.0):
    c = O
    cs = np.array([[c[0] - size / 2, y_u, c[2] - size / 2], [c[0] + size / 2, y_u, c[2] - size / 2],
                   [c[0] + size / 2, y_u, c[2] + size / 2], [c[0] - size / 2, y_u, c[2] + size / 2]])
    return mesh_obj(sc, name, cs, np.array([[0, 1, 2], [0, 2, 3]]), rgb)


def grid_lines(sc, name, y_u):
    V = []; F = []
    def quad(p0, p1, w):
        d = p1 - p0; d /= np.linalg.norm(d); n = np.cross(d, UP) * w / 2
        k = len(V); V.extend([p0 - n, p1 - n, p1 + n, p0 + n]); F.extend([[k, k + 1, k + 2], [k, k + 2, k + 3]])
    for g in range(-60, 61, 5):
        w = 0.10 if g % 10 else 0.22
        quad(O + g * T - 60 * E + [0, y_u, 0], O + g * T + 60 * E + [0, y_u, 0], w)
        quad(O + g * E - 60 * T + [0, y_u, 0], O + g * E + 60 * T + [0, y_u, 0], w)
    return mesh_obj(sc, name, np.array(V), np.array(F), (0.36, 0.37, 0.39))


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


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.image_settings.file_format = "PNG"; sc.display.render_aa = "8"
sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_cavity = True; sh.cavity_type = "WORLD"
sh.show_shadows = False; sh.show_specular_highlight = True; sh.show_backface_culling = False
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("sky"); w.color = (0.62, 0.72, 0.84); sc.world = w
tris, X = read_gwb(GWB)
mesh_obj(sc, "sheet", X, tris, (0.74, 0.69, 0.62)); plane(sc, "water_k", -0.03, (0.30, 0.31, 0.33)); grid_lines(sc, "grid_k", -0.01)
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
cam = views["v6_top_down"][0]
xv = Vector(u2b(T).tolist()); yv = Vector(u2b(E).tolist()); zv = xv.cross(yv)
cam.rotation_mode = "QUATERNION"; cam.rotation_quaternion = Matrix((xv, yv, zv)).transposed().to_quaternion()
os.makedirs(OUT, exist_ok=True)
for vn, (cam, res) in views.items():
    if VSEL and vn not in VSEL:
        continue
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = int(res[0] * SCALE), int(res[1] * SCALE)
    sc.render.filepath = os.path.join(OUT, "%s__%s.png" % (LABEL, vn))
    bpy.ops.render.render(write_still=True)
    print("R", vn, round(time.time() - t0, 1), flush=True)
json.dump({"lip_tip_world": LIP.tolist(), "seat": SEAT.tolist(), "views": list(views.keys()), "gwb": GWB},
          open(os.path.join(OUT, "views_meta_%s.json" % LABEL), "w", encoding="utf-8"), indent=1)
print("done", time.time() - t0)
