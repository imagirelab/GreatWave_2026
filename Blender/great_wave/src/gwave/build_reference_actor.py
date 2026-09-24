"""利用者提供の参照模型を底稿にした、分離白波と前進運動の比較シーン。

参照模型の造形を自作したと扱わない。模型を簡略化し、姿勢の変化を
シェイプキーへ保存する。流体シミュレーションの代替検証ではない。
"""

import hashlib
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

from gwave.build_localized_scene import mesh_object, animate_mesh, camera, rgba, linear_keys
from gwave.profile_motion import grid_faces
from gwave.traveling_sequence import TravelingSequence, BreakingConfig
from gwave.woodblock_material import make_material
from gwave.mesh_refinement import refine_reference

PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT / "results" / "reference_actor"
H = 11.0
SOURCE_NAME = "wave_repair_zbrush2.obj"


def set_attributes(obj, positions, foam_weight=None):
    """変形前の座標で色面を固定し、アニメーション中の模様の滑りを防ぐ。"""
    attribute = obj.data.attributes.new("rest_position", "FLOAT_VECTOR", "POINT")
    attribute.data.foreach_set("vector", np.asarray(positions, dtype=np.float32).ravel())
    if foam_weight is not None:
        attribute = obj.data.attributes.new("foam_weight", "FLOAT", "POINT")
        attribute.data.foreach_set("value", np.asarray(foam_weight, dtype=np.float32))


def foam_weights(xyz):
    """上方包絡面からの距離で、波冠と立体的な爪を連続して色分けする。"""
    cell = .045*H
    ij = np.floor((xyz[:, :2]-xyz[:, :2].min(0))/cell).astype(int)
    shape = ij.max(0)+1
    top = np.full(shape, -100.0)
    np.maximum.at(top, (ij[:, 0], ij[:, 1]), xyz[:, 2])
    padded = np.pad(top, 2, constant_values=-100)
    upper = np.maximum.reduce([padded[a:a+shape[0], b:b+shape[1]]
                               for a in range(5) for b in range(5)])
    weight = np.clip(1-(upper[ij[:, 0], ij[:, 1]]-xyz[:, 2])/(.70*H), 0, 1)
    weight *= np.clip((xyz[:, 2]/H-.12)/.15, 0, 1)
    return weight


def prepare(source_path):
    """原模型を変更せず、簡略化した座標と面をローカル検討用に保存する。"""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_path = Path(source_path)
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    cache = OUTPUT / "source_reduced.npz"
    if cache.exists():
        data = np.load(cache)
        if str(data["source_sha256"]) == digest:
            return cache
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(source_path), forward_axis="Y", up_axis="Z")
    imported = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if len(imported) != 1:
        raise ValueError("参照模型は単一メッシュである必要があります")
    obj = imported[0]
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    modifier = obj.modifiers.new("比較用の面数削減", "DECIMATE")
    modifier.ratio = .055
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.calc_loop_triangles()
    vertices = np.empty(len(obj.data.vertices)*3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", vertices)
    vertices = vertices.reshape(-1, 3)[:, [2, 0, 1]].copy()
    # 原模型は Y-up。水線2.5と高さ11mは比較用の仮定で、計測値ではない。
    vertices[:, 2] -= 2.5
    vertices *= H/(15.3-2.5)
    vertices[:, 0] -= 2.8
    triangles = np.array([t.vertices[:] for t in obj.data.loop_triangles], dtype=np.int32)
    np.savez_compressed(cache, vertices=vertices, faces=triangles, source_sha256=digest)
    bpy.data.objects.remove(obj, do_unlink=True)
    return cache


def _piece(scene, name, vertices, faces, selected, weight, sequence, frames, anchor, deformation):
    chosen = faces[selected]
    ids, inverse = np.unique(chosen.ravel(), return_inverse=True)
    points, local_weight = vertices[ids], weight[ids]
    obj = mesh_object(scene, name, points, inverse.reshape(-1, 3))
    set_attributes(obj, points, local_weight)
    obj.data.materials.append(make_material(name+"の色面"))
    def sample(frame):
        p = deformation(points, frame, H=H, anchor_x_H=anchor)
        contact = np.exp(-(np.maximum(p[:,2],0)/(.24*H))**2)
        p[:,2] += ocean_height(p[:,0],p[:,1],frame)*contact
        return p
    animate_mesh(obj, sample, frames, hold_end=450)
    obj["造形の出典"] = "利用者提供の "+SOURCE_NAME+" を簡略化した派生模型"
    obj["未検証事項"] = "流体物理、体積保存、Unityへの移植"
    return obj


def ocean_height(x, y, frame):
    """大きさと方向の異なる周辺波。接続検討のための美術的な水位場。"""
    t = frame/30
    x, y = x/H, y/H
    waves = .055*np.sin(3.4*x+.45*np.sin(y*1.4)-t*1.25)
    waves += .031*np.sin(5.7*x+2.1*y-t*1.95)
    waves += .016*np.sin(8.8*x-1.6*y-t*2.5)
    return H*waves


def _spray(scene, vertices, weight, sequence, anchor, deformation):
    rng = np.random.default_rng(9275)
    n = 420
    candidates = np.where((weight>.62) & (vertices[:, 2]>.42*H))[0]
    chosen = rng.choice(candidates, n, replace=True)
    birth = rng.uniform(75, 340, n)
    lifespan = rng.uniform(.5, 1.35, n)
    radius = rng.uniform(.020, .062, n)
    anchors, velocity = [], []
    for i, f in enumerate(birth):
        p = vertices[chosen[i]:chosen[i]+1]
        anchors.append(deformation(p, f, H=H, anchor_x_H=anchor)[0])
        velocity.append(30*(deformation(p, f+.5, H=H, anchor_x_H=anchor)[0]
                            - deformation(p, f-.5, H=H, anchor_x_H=anchor)[0]))
    anchors, velocity = np.asarray(anchors), np.asarray(velocity)
    velocity += np.column_stack((rng.uniform(.4, 2.3, n), rng.uniform(-1, 1, n), rng.uniform(.5, 3, n)))
    base = np.array(((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)), dtype=float)
    tri = np.array(((0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)))
    faces = (tri[None]+6*np.arange(n)[:,None,None]).reshape(-1,3)
    def sample(frame):
        age = (frame-birth)/30
        live = np.clip(age/.08,0,1)*np.clip((lifespan-age)/.18,0,1)
        age = np.clip(age, 0, lifespan)
        centers = anchors+velocity*age[:, None]
        centers[:,2] -= .5*9.81*age**2
        live *= np.clip((centers[:,2]+.2)/.2,0,1)
        return centers[:,None,:]+base[None]*np.maximum(.00001,radius*live)[:,None,None]
    obj = mesh_object(scene, "波冠から離れる独立した小滴", sample(1), faces)
    set_attributes(obj, sample(1).reshape(-1,3))
    obj.data.materials.append(make_material("小滴の生成り", foam=True))
    animate_mesh(obj, sample, list(range(1,451,3))+[450], hold_end=450)
    obj["運動の方法"] = "造形面の速度を引継ぎ、重力で飛ばす。物理的な粒子放出量は未計算"


def build(source_path=None, step=6, motion_mode="curl"):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cache = prepare(source_path) if source_path else OUTPUT/"source_reduced.npz"
    data = np.load(cache)
    vertices, faces = data["vertices"], data["faces"]
    reduced_counts = (len(vertices),len(faces))
    if motion_mode=="curl":
        if reduced_counts != (62210,124511):
            raise ValueError("局所細分の面番号は今回の参照模型専用です。別の簡略化結果は先に検査してください")
        vertices,faces = refine_reference(vertices,faces)
    weight = foam_weights(vertices)
    scene = bpy.data.scenes.new("参照模型を底稿にした前進波")
    bpy.context.window.scene = scene
    # 同じ生成器の以前の比較シーンだけを置換し、名前の連番化を防ぐ。
    for previous in list(bpy.data.scenes):
        if previous != scene and previous.name.startswith("参照模型を底稿にした前進波"):
            for obj in list(previous.objects):
                bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.scenes.remove(previous)
    scene.name = "参照模型を底稿にした前進波"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, 450
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("生成りの空")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = rgba("#ddd4b8")
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .8
    lamp = bpy.data.objects.new("広い空の光", bpy.data.lights.new("広い空の光", "AREA"))
    scene.collection.objects.link(lamp)
    lamp.location = (-10,-30,40)
    lamp.data.energy, lamp.data.size = 14000, 25
    lamp.rotation_euler = (Vector((0,0,5))-lamp.location).to_track_quat("-Z","Y").to_euler()
    sequence = TravelingSequence()
    if motion_mode not in ("lean","curl"):
        raise ValueError("運動方式は lean または curl で指定してください")
    deformation = sequence.deform_breaking_points if motion_mode=="curl" else sequence.deform_points
    anchor = float(vertices[np.argmax(vertices[:,2]),0]/H)
    frames = sorted(set(list(range(1,451,int(step)))+[180,210,240,285,345,450]))
    # 白波を別メッシュとして分離し、境界の同じ頂点には同じ運動を適用する。
    foam_faces = weight[faces].mean(axis=1)>.48
    water = _piece(scene,"主波_参照模型からの派生",vertices,faces,~foam_faces,weight,sequence,frames,anchor,deformation)
    white = _piece(scene,"白波_独立した波冠と爪",vertices,faces,foam_faces,weight,sequence,frames,anchor,deformation)
    _spray(scene,vertices,weight,sequence,anchor,deformation)
    x,y = np.meshgrid(np.linspace(-9,13,181)*H,np.linspace(-9,15,161)*H)
    sea_rest = np.stack((x,y,np.zeros_like(x)),axis=-1)
    def ocean(frame):
        z = ocean_height(x,y,frame)+sequence.follow_height(x,y,frame,H)
        return np.stack((x,y,z),axis=-1)
    sea = mesh_object(scene,"周辺で進む海面",ocean(1),grid_faces(181,161))
    set_attributes(sea,sea_rest)
    sea.data.materials.append(make_material("周辺海面の藍",sea=True))
    animate_mesh(sea,ocean,list(range(1,451,9))+[450],hold_end=450)
    scene.camera = camera(scene,"CAM_斜めからの全過程",(1.8,-3.1,1.2),(.1,0,.5),lens=46)
    inspection_camera = scene.camera
    camera_x = inspection_camera.location.x
    center_at_reference = sequence.state(210)["center_x_H"]
    for frame in (1,450):
        inspection_camera.location.x = camera_x+H*(sequence.state(frame)["center_x_H"]-center_at_reference)
        inspection_camera.keyframe_insert(data_path="location",frame=frame)
    linear_keys(inspection_camera)
    inspection_camera["視点の目的"] = "大波と同速で前進し、唇の巻き下げを画面内で比較する。固定船上視点ではない"
    camera(scene,"CAM_原画に近い方向",(.0,-4.8,.49),(.0,0,.49),lens=62)
    camera(scene,"CAM_船上の高さ",(1.1,-1.35,.12),(.0,0,.63),lens=26)
    camera(scene,"CAM_固定した全体確認",(2.1,-4.6,1.0),(.5,0,.4),lens=44)
    scene.frame_set(210)
    scene["制作段階"] = "参照模型から派生した美術的な運動試作。参考展示と同等の品質には未達"
    scene["参照模型"] = SOURCE_NAME
    scene["原模型のSHA256"] = str(data["source_sha256"])
    path = OUTPUT/("reference_actor_curl_animated.blend" if motion_mode=="curl" else "reference_actor_animated.blend")
    # 他の比較シーンを混入させず、このシーンと依存データだけを保存する。
    bpy.data.libraries.write(str(path), {scene}, fake_user=True, compress=True)
    manifest = {"説明":"利用者の参照模型を底稿にした動的な比較試作。流体物理は未検証。",
                "source_name":SOURCE_NAME,"source_sha256":str(data["source_sha256"]),
                "source_axes":"原Yが高さ、原Zが進行方向。比較用水線は原Y=2.5。",
                "reduced_vertices":reduced_counts[0],"reduced_triangles":reduced_counts[1],
                "refined_vertices":len(vertices),"refined_triangles":len(faces),
                "water_vertices":len(water.data.vertices),"foam_vertices":len(white.data.vertices),
                "shape_frames":frames,"anchor_x_H":anchor,"motion_mode":motion_mode,
                "breaking_config":vars(BreakingConfig()) if motion_mode=="curl" else None,
                "camera_motion":"斜めの視点は波と同じ速度で前進。固定の全体確認と船上の高さは動かさない。",
                "sequence":sequence.metadata()}
    manifest_name = "curl_scene_manifest.json" if motion_mode=="curl" else "scene_manifest.json"
    (OUTPUT/manifest_name).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"保存先":str(path),"頂点":len(vertices),"面":len(faces)},ensure_ascii=False))
    return scene


def render_still(camera_name="CAM_斜めからの全過程", frame=210, name=None, width=1280):
    scene = bpy.context.scene
    scene.camera = scene.objects[camera_name]
    scene.frame_set(frame)
    scene.render.resolution_x,scene.render.resolution_y = width,int(width*.625)
    scene.render.filepath = str(OUTPUT/(name or f"姿勢_{frame}_{camera_name}.png"))
    bpy.ops.render.render(write_still=True)
    return scene.render.filepath


def render_movie(camera_name="CAM_斜めからの全過程", suffix="volume", width=960):
    scene = bpy.context.scene
    scene.camera = scene.objects[camera_name]
    scene.frame_start,scene.frame_end,scene.frame_step = 1,450,1
    scene.render.resolution_x,scene.render.resolution_y = width,int(width*.625)
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    stem = OUTPUT/f"reference_actor_{suffix}_"
    scene.render.filepath = str(stem)
    bpy.ops.render.render(animation=True)
    movies = list(OUTPUT.glob(stem.name+"*.mp4"))
    if len(movies)!=1:
        raise RuntimeError("出力動画を一つに特定できません")
    target = OUTPUT/f"reference_actor_{suffix}.mp4"
    movies[0].replace(target)
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(210)
    return str(target)
