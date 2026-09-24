"""11: 空シーンから厚みを持つ静止の巻き波を生成する。流体計算ではない。"""
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1.0

def material(name, color):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    return result

materials = [material('M1_Indigo', (.018, .10, .20)),
             material('M1_Blue', (.065, .27, .39)),
             material('M1_LightBlue', (.23, .46, .53)),
             material('M1_DeepBlue', (.012, .053, .12))]

def bezier(a, b, c, d, t):
    return (1-t)**3 * Vector(a) + 3*(1-t)**2*t*Vector(b) + 3*(1-t)*t*t*Vector(c) + t**3*Vector(d)

def profile(u):
    if u < .62:
        return bezier((-22, -.3), (-20, 6), (-15, 15.7), (-8, 17.5), u/.62)
    return bezier((-8, 17.5), (-1, 21), (5.8, 17), (3.2, 11.7), (u-.62)/.38)

def point(u, v, w):
    # z方向で高さ・張り出し・幅を変え、同一断面の押し出しを避ける。
    p = profile(u)
    tangent = (profile(min(1, u+.001)) - profile(max(0, u-.001))).normalized()
    normal = Vector((-tangent.y, tangent.x))
    thickness = 6.0*(1-u)**1.15 + 1.10
    z = -7.5 + 20*v
    crest_factor = math.sin(math.pi*u/2)**2
    bulge = math.sin(math.pi*v)
    x = p.x + normal.x*thickness*w + crest_factor*(2.5*bulge - 2.0*v)
    y = (p.y + normal.y*thickness*w)*(0.86 + .14*math.sin(math.pi*(.10+.85*v)))
    z += 1.5*math.sin(math.pi*u)*math.sin(math.pi*v)
    # M0で実測した受け渡しの逆変換。Unityの(x,y,z)を制作時に明示する。
    return (-x, -z, y)

U, V, W = 88, 16, 6
vertices, faces, material_ids, lookup = [], [], [], {}
def vertex(i, j, k):
    key = (i, j, k)
    if key not in lookup:
        lookup[key] = len(vertices)
        vertices.append(point(i/U, j/V, k/W))
    return lookup[key]
def quad(keys, mat):
    faces.append(tuple(vertex(*key) for key in keys))
    material_ids.append(mat)

for i in range(U):
    for j in range(V):
        for k in (0, W):
            quad(((i,j,k),(i+1,j,k),(i+1,j+1,k),(i,j+1,k)), 1 if k == 0 else 0)
for i in range(U):
    for k in range(W):
        for j in (0, V):
            quad(((i,j,k),(i+1,j,k),(i+1,j,k+1),(i,j,k+1)), (0,0,1,0,2,0)[k])
for j in range(V):
    for k in range(W):
        for i in (0,U):
            quad(((i,j,k),(i,j+1,k),(i,j+1,k+1),(i,j,k+1)), 3 if i == 0 else 1)

mesh = bpy.data.meshes.new('M1_WaveVolumeMesh')
mesh.from_pydata(vertices, [], faces)
mesh.update()
wave = bpy.data.objects.new('M1_MainWave_Static', mesh)
bpy.context.collection.objects.link(wave)
for mat in materials:
    mesh.materials.append(mat)
for poly, mat in zip(mesh.polygons, material_ids):
    poly.material_index = mat
    poly.use_smooth = True
bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
non_manifold = sum(not e.is_manifold for e in bm.edges)
volume = abs(bm.calc_volume())
bm.to_mesh(mesh)
bm.free()
if non_manifold or volume <= 0:
    raise RuntimeError('閉じた厚みのある形状の検証に失敗')
bpy.context.view_layer.objects.active = wave
wave.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'M1_Wave_Static.blend'))
flags = dict(use_selection=True, global_scale=1.0, apply_unit_scale=True,
             apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y',
             use_space_transform=True, bake_space_transform=False, bake_anim=False,
             object_types={'MESH'}, add_leaf_bones=False, path_mode='STRIP')
bpy.ops.export_scene.fbx(filepath=str(OUT/'wave_static.fbx'), **flags)
unity_vertices = [(-p[0], p[2], -p[1]) for p in vertices]
minimum = [min(p[a] for p in unity_vertices) for a in range(3)]
maximum = [max(p[a] for p in unity_vertices) for a in range(3)]
report = dict(software=bpy.app.version_string, static_not_fluid=True,
              vertices=len(vertices), faces=len(faces), non_manifold_edges=non_manifold,
              enclosed_volume_m3=volume, expected_unity_min_m=minimum, expected_unity_max_m=maximum,
              path_samples=U, depth_samples=V, thickness_layers=W,
              minimum_designed_thickness_m=1.1, depth_variation='高さ・張り出し・位置をz方向で変化',
              physical_accuracy='未検証。原画を観察した静止の形状習作',
              passed=non_manifold == 0 and volume > 0)
(OUT/'11_blender_geometry.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('M1_STEP11_BLENDER_PASS', json.dumps(report, ensure_ascii=False))
