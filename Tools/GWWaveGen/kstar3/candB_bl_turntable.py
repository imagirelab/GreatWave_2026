# -*- coding: utf-8 -*-
"""Q20 candidate B: clay turntable of a GWW0 K*' (Blender Workbench, cavity on, same light/material as the rubric's
standard views).  72 frames, 5 deg apart, orbit around the main crest at 70 m, elevation 15 deg.
usage: blender --background --factory-startup --python-exit-code 1 --python candB_bl_turntable.py -- <out_dir> <gwb> [n]
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, GWB = argv[0], argv[1]
N = int(argv[2]) if len(argv) > 2 else 72
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
    me = bpy.data.meshes.new(name); vb = u2b(V_u).astype(np.float32); FF = F[:, [0, 2, 1]]
    me.vertices.add(len(vb)); me.vertices.foreach_set("co", vb.ravel())
    me.loops.add(FF.size); me.loops.foreach_set("vertex_index", FF.astype(np.int32).ravel())
    me.polygons.add(len(FF)); me.polygons.foreach_set("loop_start", np.arange(0, FF.size, 3, dtype=np.int32))
    me.update(); me.validate(); me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    mat = bpy.data.materials.new(name + "_m"); mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1); mat.roughness = 0.55
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); return ob


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"; sc.render.image_settings.file_format = "PNG"; sc.display.render_aa = "8"
sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_cavity = True; sh.cavity_type = "WORLD"
sh.show_shadows = False; sh.show_specular_highlight = True; sh.show_backface_culling = False
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("sky"); w.color = (0.62, 0.72, 0.84); sc.world = w
tris, X = read_gwb(GWB)
mesh_obj(sc, "wave", X, tris, (0.74, 0.69, 0.62))
s = 350.0
cs = np.array([[O[0] - s, -0.03, O[2] - s], [O[0] + s, -0.03, O[2] - s], [O[0] + s, -0.03, O[2] + s], [O[0] - s, -0.03, O[2] + s]])
mesh_obj(sc, "water", cs, np.array([[0, 1, 2], [0, 2, 3]]), (0.30, 0.31, 0.33))
cd = bpy.data.cameras.new("cam"); cd.sensor_fit = "VERTICAL"; cd.sensor_height = 24.0; cd.lens = 12.0 / math.tan(math.radians(36) / 2)
cd.clip_start = 0.2; cd.clip_end = 3000
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 960, 540
C0 = O + np.array([0, 8.0, 0]); R = 70.0; el = math.radians(15)
os.makedirs(OUT, exist_ok=True)
for k in range(N):
    az = math.radians(360.0 * k / N)
    # azimuth 0 = in front of the wave (+t), increasing toward the far side (+e)
    d = math.cos(el) * (math.cos(az) * T + math.sin(az) * E) + math.sin(el) * UP
    p = C0 + R * d
    pb = Vector(u2b(p).tolist()); tb = Vector(u2b(C0).tolist())
    cam.location = pb; cam.rotation_mode = "QUATERNION"; cam.rotation_quaternion = (tb - pb).to_track_quat("-Z", "Y")
    sc.render.filepath = os.path.join(OUT, "tt_%03d.png" % k)
    bpy.ops.render.render(write_still=True)
print("turntable done", N)
