"""M1 の構図検討用に船と富士山を新規作成する。

Blender 5.2.2 LTS のバックグラウンドで実行する。
長さの値は制作上の仮寸法であり、歴史的実測値・浮力模型ではない。
既存の試作・制作物は読み込まない。外部画像もメッシュへ転用しない。
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
TOLERANCE = 1e-5
EXPORT_FLAGS = {
    'check_existing': False, 'use_selection': True, 'global_scale': 1.0,
    'apply_unit_scale': True, 'apply_scale_options': 'FBX_SCALE_UNITS',
    'axis_forward': '-Z', 'axis_up': 'Y', 'use_space_transform': True,
    'bake_space_transform': False, 'object_types': {'MESH'},
    'use_mesh_modifiers': True, 'use_triangles': True,
    'mesh_smooth_type': 'OFF', 'use_custom_props': True,
    'bake_anim': False, 'add_leaf_bones': False,
    'path_mode': 'STRIP', 'embed_textures': False,
}
IMPORT_FLAGS = {
    'global_scale': 1.0, 'use_manual_orientation': False,
    'bake_space_transform': False, 'use_anim': False,
    'use_image_search': False, 'use_custom_props': True,
}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    bpy.context.preferences.filepaths.save_version = 0


def material(name, rgba):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = rgba
    bsdf.inputs['Roughness'].default_value = 1.0
    return mat


def mesh_object(name, vertices, faces, materials, face_materials=None):
    mesh = bpy.data.meshes.new(name + '_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for mat in materials:
        mesh.materials.append(mat)
    if face_materials:
        for polygon, index in zip(mesh.polygons, face_materials):
            polygon.material_index = index
    # 各閉じた部品の法線を外向きにそろえる。描画で裏面を隠して検査する。
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = False
    obj['purpose_ja'] = 'M1 構図と材質の静的検討。歴史的実測・物理検証なし。'
    obj['unit'] = 'metre'
    return obj


def add_box(vertices, faces, center, size):
    start = len(vertices)
    for x, y, z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                    (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]:
        vertices.append(tuple(c + s*q/2 for c,s,q in zip(center,size,(x,y,z))))
    faces.extend(tuple(start+i for i in face) for face in
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])


# 船首は -Y。細長い平面形、上がった両端、開いた船内を構図の基礎とする。
STATIONS = [(-5.0,.04,.74,1.74),(-4.6,.23,.40,1.43),(-3.8,.48,.16,1.19),
            (-2.8,.69,.04,1.04),(-1.5,.85,.00,.98),(0.0,.90,.00,.96),
            (1.5,.86,.00,.98),(2.8,.71,.04,1.05),(3.8,.50,.18,1.22),
            (4.6,.25,.39,1.43),(5.0,.10,.64,1.65)]


def beam_at(y):
    for left, right in zip(STATIONS, STATIONS[1:]):
        if left[0] <= y <= right[0]:
            u = (y-left[0])/(right[0]-left[0])
            return left[1]*(1-u) + right[1]*u
    raise ValueError(y)


def inside_width_at(y, z):
    for left, right in zip(STATIONS, STATIONS[1:]):
        if left[0] <= y <= right[0]:
            u=(y-left[0])/(right[0]-left[0])
            width,bottom,top=[left[j]*(1-u)+right[j]*u for j in (1,2,3)]
            half=max(.018,width-.075)
            floor=bottom+.085
            t=max(0.0,(z-floor)/(top-floor))
            return half*(.46+.42*t/.40 if t<.40 else .88+.12*(t-.40)/.60)
    raise ValueError(y)


def make_boat():
    wood = material('GW_Boat_Wood', (.63,.38,.18,1))
    edge = material('GW_Boat_Edge', (.16,.20,.24,1))
    plank = material('GW_Boat_Plank', (.76,.58,.32,1))
    vertices, faces = [], []
    # 外側と内側を接続した厚みのある船殻。上面をふさがない。
    section = [(-1,1),(-.88,.40),(-.46,0),(.46,0),(.88,.40),(1,1)]
    count = len(section)
    for inner in (False, True):
        for y, width, bottom, top in STATIONS:
            half = max(.018,width-.075) if inner else width
            floor = bottom + (.085 if inner else 0)
            for x, t in section:
                vertices.append((x*half,y,floor+(top-floor)*t))
    n = len(STATIONS)
    sheet = n*count
    for side in (0,1):
        for station in range(n-1):
            for j in range(count-1):
                a = side*sheet+station*count+j
                faces.append((a,a+1,a+count+1,a+count))
    for station in range(n-1):
        for j in (0,count-1):
            a = station*count+j
            faces.append((a,a+count,a+count+sheet,a+sheet))
    for station in (0,n-1):
        for j in range(count-1):
            a=station*count+j
            faces.append((a,a+sheet,a+sheet+1,a+1))
    hull = mesh_object('Boat_Hull_OpenThick',vertices,faces,[wood])
    hull['forward_axis_blender'] = '-Y'
    hull['nominal_side_inset_m'] = .075
    hull['nominal_floor_thickness_m'] = .085

    # 両舷の縁材も厚さを持つ閉じた形状にする。
    for sign,label in [(-1,'Left'),(1,'Right')]:
        vertices,faces = [],[]
        for y,width,bottom,top in STATIONS:
            x0=sign*width
            x1=sign*max(.012,width-.09)
            vertices.extend([(x0,y,top-.045),(x1,y,top-.045),
                             (x1,y,top+.035),(x0,y,top+.035)])
        for i in range(n-1):
            for j in range(4):
                a=i*4+j
                faces.append((a,i*4+(j+1)%4,(i+1)*4+(j+1)%4,a+4))
        faces.extend([(3,2,1,0),tuple((n-1)*4+j for j in range(4))])
        mesh_object('Boat_Gunwale_'+label,vertices,faces,[edge])

    vertices,faces=[],[]
    # 中央の乗船用床。隙間を小さく残し、板割りを形状として読めるようにする。
    for index in range(25):
        y=-3.36+index*.28
        z=.25 + .12*(abs(y)/3.36)**2
        # 上反りのある船底でも床板が船殻を突き抜けない寸法にする。
        width=1.92*min(inside_width_at(y-.134,z-.0325),inside_width_at(y+.134,z-.0325))
        add_box(vertices,faces,(0,y,z),(width,.268,.065))
    deck = mesh_object('Boat_Deck_Planks',vertices,faces,[plank])
    deck['central_deck_top_m']=.2825

    vertices,faces=[],[]
    for y in (-2.75,-1.45,0,1.45,2.75):
        add_box(vertices,faces,(0,y,.82),(beam_at(y)*2-.17,.135,.10))
    mesh_object('Boat_Crossbeams',vertices,faces,[edge])
    bpy.context.view_layer.update()


def make_fuji():
    blue=material('GW_Fuji_Blue',(.055,.17,.29,1))
    snow=material('GW_Fuji_Snow',(.96,.91,.75,1))
    n=48
    vertices=[]
    # 低い裾野から頂へ絞る四周のある山。雪線は頂点列を共有し、面の重なりを作らない。
    for ring in range(5):
        for i in range(n):
            a=2*math.pi*i/n
            if ring==0:
                radius,z=12.0,0.0
            elif ring==1:
                z=1.8+.18*math.sin(3*a)
                radius=12*(1-z/8)**1.35
            elif ring==2:
                z=4.35+.48*math.sin(7*a+.4)+.24*math.sin(13*a)
                radius=12*(1-z/8)**1.35
            elif ring==3:
                z=7.5+.10*math.sin(3*a)
                radius=.54+.07*math.cos(5*a)
            else:
                radius,z=.12,8.0
            vertices.append((radius*math.cos(a),radius*math.sin(a),z))
    faces=[]
    mats=[]
    faces.append(tuple(reversed(range(n))))
    mats.append(0)
    for ring in range(4):
        for i in range(n):
            j=(i+1)%n
            a,b,c,d=ring*n+i,ring*n+j,(ring+1)*n+j,(ring+1)*n+i
            faces.extend([(a,b,c),(a,c,d)])
            mats.extend([1 if ring>=2 else 0]*2)
    faces.append(tuple(4*n+i for i in range(n)))
    mats.append(1)
    obj=mesh_object('Fuji_Mountain',vertices,faces,[blue,snow],mats)
    obj['base_radius_m']=12.0
    obj['height_m']=8.0
    obj['shape_ja']='構図検討用の仮寸法。地理的縮尺の再現ではない。'
    bpy.context.view_layer.update()


def measure():
    result={}
    for obj in sorted(bpy.context.scene.objects,key=lambda item:item.name):
        if obj.type!='MESH':
            continue
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        low=[min(p[a] for p in points) for a in range(3)]
        high=[max(p[a] for p in points) for a in range(3)]
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        volume=bm.calc_volume(signed=True)
        nonmanifold=sum(not edge.is_manifold for edge in bm.edges)
        degenerate=sum(face.calc_area()<1e-10 for face in bm.faces)
        bm.free()
        obj.data.calc_loop_triangles()
        normal_errors=sum(not all(math.isfinite(c) for c in p.normal) or abs(p.normal.length-1)>1e-4
                          for p in obj.data.polygons)
        result[obj.name]={
            'bounds_min_m':low,'bounds_max_m':high,
            'dimensions_m':[b-a for a,b in zip(low,high)],
            'vertex_count':len(points),'triangle_count':len(obj.data.loop_triangles),
            'material_names':[m.name for m in obj.data.materials],
            'signed_volume_m3':volume,'nonmanifold_edges':nonmanifold,
            'degenerate_faces':degenerate,'invalid_or_nonunit_normals':normal_errors,
            'object_location':list(obj.location),'object_rotation_euler_rad':list(obj.rotation_euler),
            'object_scale':list(obj.scale),
        }
        assert volume>0 and nonmanifold==0 and degenerate==0 and normal_errors==0,obj.name
    return result


def compare(source,other):
    assert set(source)==set(other)
    error=0.0
    for name in source:
        for key in ('bounds_min_m','bounds_max_m'):
            error=max(error,max(abs(a-b) for a,b in zip(source[name][key],other[name][key])))
        assert source[name]['triangle_count']==other[name]['triangle_count'],name
        assert source[name]['material_names']==other[name]['material_names'],name
    assert error<TOLERANCE,error
    return {'passed':True,'maximum_bounds_error_m':error,
            'triangle_counts_and_material_slots_match':True,
            'closed_manifold_positive_volume_and_unit_normals':True}


def overall_bounds(geometry):
    low=[min(obj['bounds_min_m'][a] for obj in geometry.values()) for a in range(3)]
    high=[max(obj['bounds_max_m'][a] for obj in geometry.values()) for a in range(3)]
    return {'bounds_min_m':low,'bounds_max_m':high,
            'dimensions_m':[b-a for a,b in zip(low,high)],
            'triangles':sum(o['triangle_count'] for o in geometry.values())}


def render_preview(name,target,camera_location,ortho):
    # 実際の Blender 描画を保存する。Unity/HMD の証跡には数えない。
    scene=bpy.context.scene
    camera_data=bpy.data.cameras.new('QA_Camera')
    camera=bpy.data.objects.new('QA_Camera',camera_data)
    scene.collection.objects.link(camera)
    camera.location=camera_location
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.type='ORTHO'
    camera_data.ortho_scale=ortho
    scene.camera=camera
    scene.render.engine='BLENDER_WORKBENCH'
    shading=scene.display.shading
    shading.light='STUDIO'
    shading.color_type='MATERIAL'
    shading.show_shadows=True
    shading.show_cavity=True
    shading.cavity_type='BOTH'
    shading.show_object_outline=True
    shading.show_backface_culling=True
    shading.background_type='WORLD'
    scene.world=bpy.data.worlds.new('QA_World')
    scene.world.color=(.73,.71,.65)
    scene.render.resolution_x=1100
    scene.render.resolution_y=800
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.filepath=str(ROOT/(name+'_blender_preview.png'))
    bpy.ops.render.render(write_still=True)


def generate_asset(name,maker,preview):
    reset()
    maker()
    source=measure()
    for obj in source.values():
        assert max(abs(x) for x in obj['object_location'])<1e-9
        assert max(abs(x) for x in obj['object_rotation_euler_rad'])<1e-9
        assert max(abs(x-1) for x in obj['object_scale'])<1e-9
    blend=ROOT/(name+'.blend')
    fbx=ROOT/(name+'.fbx')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    assert 'FINISHED' in bpy.ops.export_scene.fbx(filepath=str(fbx),**EXPORT_FLAGS)
    render_preview(name,*preview)
    reset()
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    saved=measure()
    saved_check=compare(source,saved)
    reset()
    assert 'FINISHED' in bpy.ops.import_scene.fbx(filepath=str(fbx),**IMPORT_FLAGS)
    bpy.context.view_layer.update()
    imported=measure()
    imported_check=compare(source,imported)
    return {'source_objects':source,'source_bounds':overall_bounds(source),
            'fbx_roundtrip_bounds':overall_bounds(imported),
            'saved_blend_reopen':saved_check,'fbx_roundtrip':imported_check}


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    report={
        'schema_version':1,'created_utc':datetime.now(timezone.utc).isoformat(),
        'software':{'name':'Blender','version':bpy.app.version_string,
                    'build_hash':bpy.app.build_hash.decode('ascii')},
        'description_ja':'M1 向け新規の船・富士山ブロックアウト。構図検討用の仮寸法。',
        'reference_ja':'所蔵館資料 Met JP1847 の細長い船・青と白の富士の構成を視覚的に観察。画像の形状抽出は行わない。',
        'coordinates':{'unit':'metre','handedness':'right','up':'+Z','boat_forward':'-Y'},
        'export_flags':{k:sorted(v) if isinstance(v,set) else v for k,v in EXPORT_FLAGS.items()},
        'reimport_flags':IMPORT_FLAGS,'tolerance_m':TOLERANCE,
        'assets':{},'unity_validation':'NOT_RUN','hmd_validation':'NOT_RUN',
    }
    report['assets']['boat_blockout']=generate_asset('boat_blockout',make_boat,
                                                   ((0,0,.7),(10,-14,13),12.5))
    report['assets']['fuji_blockout']=generate_asset('fuji_blockout',make_fuji,
                                                   ((0,0,3),(26,-35,19),29))
    boat=report['assets']['boat_blockout']['source_bounds']
    fuji=report['assets']['fuji_blockout']['source_bounds']
    assert abs(boat['dimensions_m'][0]-1.8)<TOLERANCE
    assert abs(boat['dimensions_m'][1]-10.0)<TOLERANCE
    assert max(abs(a-b) for a,b in zip(fuji['dimensions_m'],(24,24,8)))<TOLERANCE
    report['checks']={'passed':True,'boat_width_and_length_m':[1.8,10.0],
                      'fuji_dimensions_m':[24,24,8],
                      'all_source_transforms_identity':True,
                      'geometry_and_normals_checked_after_fbx_reimport':True}
    paths=[Path(__file__).resolve()]+sorted(ROOT.glob('*.blend'))+sorted(ROOT.glob('*.fbx'))
    paths+=sorted(ROOT.glob('*_blender_preview.png'))
    report['files']={p.name:{'bytes':p.stat().st_size,
                           'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}
    (ROOT/'validation_blender.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('M1_BLENDER_ASSETS_PASS '+json.dumps(report['checks'],ensure_ascii=False))


if __name__=='__main__':
    main()
