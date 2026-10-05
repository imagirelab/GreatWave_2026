# -*- coding: utf-8 -*-
"""Q20 final K*': clay turntable (Blender Workbench, cavity on, same clay / light / water plane as the rubric views),
written straight to an H.264 mp4 by Blender's FFmpeg output, plus 12 PNG stills for a contact sheet.
usage: blender --background --factory-startup --python-exit-code 1 --python fin_turntable.py -- <sheet.gwb> <out.mp4>
       <stills_dir> [n_frames=240] [radius_m=72] [elev_deg=16] [w=1280] [h=720]
The camera orbits the wave centre (K* section origin O + 9 m up), starting at the painting camera's azimuth."""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GWB, MP4, STILLS = argv[0], argv[1], argv[2]
NF = int(argv[3]) if len(argv) > 3 else 240
RAD = float(argv[4]) if len(argv) > 4 else 72.0
EL = float(argv[5]) if len(argv) > 5 else 16.0
W = int(argv[6]) if len(argv) > 6 else 1280
H = int(argv[7]) if len(argv) > 7 else 720
E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187]); UP = np.array([0, 1.0, 0])


def u2b(P):
    P = np.asarray(P, np.float64); return np.stack([P[..., 0], P[..., 2], P[..., 1]], -1)


def read_gwb(p):
    b = open(p, "rb").read()
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4"); ntri = int(np.frombuffer(b[28:32], "<i4")[0]); n = int(nu) * int(nv)
    o = 32 + n * 16
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    return tris, X


def mesh_obj(sc, name, V_u, F, rgb):
    me = bpy.data.meshes.new(name)
    vb = u2b(V_u).astype(np.float32); FF = F[:, [0, 2, 1]]
    me.vertices.add(len(vb)); me.vertices.foreach_set("co", vb.ravel())
    me.loops.add(FF.size); me.loops.foreach_set("vertex_index", FF.astype(np.int32).ravel())
    me.polygons.add(len(FF)); me.polygons.foreach_set("loop_start", np.arange(0, FF.size, 3, dtype=np.int32))
    me.update(); me.validate()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    mat = bpy.data.materials.new(name + "_m"); mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1); mat.roughness = 0.55
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); return ob


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.render_aa = "8"
sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_cavity = True; sh.cavity_type = "WORLD"
sh.show_shadows = False; sh.show_specular_highlight = True; sh.show_backface_culling = False
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("sky"); w.color = (0.62, 0.72, 0.84); sc.world = w
tris, X = read_gwb(GWB)
mesh_obj(sc, "cand", X, tris, (0.74, 0.69, 0.62))
S = 700.0
cs = np.array([[O[0] - S / 2, -0.03, O[2] - S / 2], [O[0] + S / 2, -0.03, O[2] - S / 2], [O[0] + S / 2, -0.03, O[2] + S / 2], [O[0] - S / 2, -0.03, O[2] + S / 2]])
mesh_obj(sc, "water", cs, np.array([[0, 1, 2], [0, 2, 3]]), (0.30, 0.31, 0.33))
V = []; Fq = []
def quad(p0, p1, wd):
    d = p1 - p0; d /= np.linalg.norm(d); nn = np.cross(d, UP) * wd / 2
    k = len(V); V.extend([p0 - nn, p1 - nn, p1 + nn, p0 + nn]); Fq.extend([[k, k + 1, k + 2], [k, k + 2, k + 3]])
for g in range(-60, 61, 5):
    wd = 0.10 if g % 10 else 0.22
    quad(O + g * T - 60 * E + [0, -0.01, 0], O + g * T + 60 * E + [0, -0.01, 0], wd)
    quad(O + g * E - 60 * T + [0, -0.01, 0], O + g * E + 60 * T + [0, -0.01, 0], wd)
mesh_obj(sc, "grid", np.array(V), np.array(Fq), (0.36, 0.37, 0.39))
cd = bpy.data.cameras.new("cam"); cd.sensor_fit = "VERTICAL"; cd.sensor_height = 24.0
cd.lens = 12.0 / math.tan(math.radians(34) / 2.0); cd.clip_start = 0.2; cd.clip_end = 3000
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = W, H
C0 = O + np.array([0, 9.0, 0])
pc = np.array([0.0, 3.0, -62.0]) - C0; az0 = math.atan2(pc[2], pc[0])
cam.rotation_mode = "QUATERNION"


def place(f):
    az = az0 + 2 * math.pi * f / NF
    eye = C0 + np.array([RAD * math.cos(math.radians(EL)) * math.cos(az), RAD * math.sin(math.radians(EL)), RAD * math.cos(math.radians(EL)) * math.sin(az)])
    p = Vector(u2b(eye).tolist()); t = Vector(u2b(C0).tolist())
    cam.location = p; cam.rotation_quaternion = (t - p).to_track_quat("-Z", "Y")


# stills
os.makedirs(STILLS, exist_ok=True)
sc.render.image_settings.file_format = "PNG"
for f in range(0, NF, NF // 12):
    place(f)
    sc.render.filepath = os.path.join(STILLS, "f_%04d.png" % f)
    bpy.ops.render.render(write_still=True)
# movie: keyframe the orbit and render straight to H.264
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
