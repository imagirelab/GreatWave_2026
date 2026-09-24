"""参照造形を閉じた初期水体にする。形成過程の流体計算ではない。"""

import hashlib
import json
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from gwave.build_localized_scene import mesh_object, rgba
from gwave.fluid_preview import _camera, _material

PROJECT = Path(__file__).resolve().parents[2]
REPOSITORY = PROJECT.parents[1]
OUTPUT = PROJECT / "results" / "reference_fluid_initial"
INPUTS = REPOSITORY / "Houdini" / "reference_release" / "inputs"


def mesh_stats(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    stats = {
        "頂点数": len(bm.verts), "面数": len(bm.faces),
        "境界辺数": sum(edge.is_boundary for edge in bm.edges),
        "非多様体辺数": sum(not edge.is_manifold for edge in bm.edges),
        "表示表面の符号付き体積_m3": bm.calc_volume(signed=True),
    }
    bm.free()
    p = np.asarray([tuple(v.co) for v in obj.data.vertices])
    stats["境界箱最小_Blender_m"] = p.min(0).tolist()
    stats["境界箱最大_Blender_m"] = p.max(0).tolist()
    return stats


def write_obj(obj, path):
    """適用済みの座標をHoudiniのY-upへ正回転して書き出す。"""
    obj.data.calc_loop_triangles()
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("# 利用者の参照模型に基づく初期水体。Houdini Y-up、単位m。\n")
        for vertex in obj.data.vertices:
            x, y, z = obj.matrix_world @ vertex.co
            stream.write(f"v {x:.8f} {z:.8f} {-y:.8f}\n")
        for triangle in obj.data.loop_triangles:
            stream.write("f " + " ".join(str(i+1) for i in triangle.vertices) + "\n")


def build(source_path, height=3.0, waterline=1.4, cut_depth=.30, voxel=.035):
    """参考形状の閉体積を作り、水面下の裁切条件をHoudiniへ渡す。"""
    source_path = Path(source_path)
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    cache = PROJECT / "results" / "reference_actor" / "source_reduced.npz"
    if not cache.exists():
        from gwave.build_reference_actor import prepare
        prepare(source_path)
    data = np.load(cache)
    if str(data["source_sha256"]) != digest:
        raise ValueError("簡略化模型と原OBJのハッシュが一致しません")
    v = data["vertices"].astype(float).copy()
    faces = data["faces"]
    scale = height / v[:, 2].max()
    above = v[v[:, 2] >= 0]
    center = (above[:, :2].min(0) + above[:, :2].max(0))*.5
    v[:, :2] -= center
    v *= scale
    v[:, 2] += waterline
    OUTPUT.mkdir(parents=True, exist_ok=True)
    INPUTS.mkdir(parents=True, exist_ok=True)
    scene = bpy.data.scenes.new("参考造形からの閉じた初期水体")
    bpy.context.window.scene = scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1200, 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("初期水体確認の背景")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = rgba("#ded6c5")
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .65
    raw = mesh_object(scene, "位置と寸法を合わせた参照造形", v, faces)
    raw.data.materials.append(_material())
    raw.hide_render = True
    raw.hide_set(True)
    proxy = mesh_object(scene, "参照の閉体積_水面下は未切断", v, faces)
    bpy.ops.object.select_all(action="DESELECT")
    proxy.select_set(True)
    bpy.context.view_layer.objects.active = proxy
    initial_stats = mesh_stats(proxy)
    bm = bmesh.new()
    bm.from_mesh(proxy.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(proxy.data)
    bm.free()

    proxy.data.remesh_voxel_size = voxel
    bpy.ops.object.voxel_remesh()
    bm = bmesh.new()
    bm.from_mesh(proxy.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(proxy.data)
    bm.free()
    # 水面下の切断はHoudiniの符号付き距離場で行う。
    # 複数の底部輪郭へ重なる蓋を追加せず、全体の閉体積を渡す。
    proxy.data.update()
    final_stats = mesh_stats(proxy)
    if final_stats["非多様体辺数"] or final_stats["表示表面の符号付き体積_m3"] <= 0:
        raise RuntimeError("閉じた正方向の初期水体になっていません")
    if abs(final_stats["境界箱最大_Blender_m"][2] - (waterline+height)) > voxel*2:
        raise RuntimeError("修復中に参照の高峰を失いました")
    proxy.data.materials.append(_material())
    for polygon in proxy.data.polygons:
        polygon.use_smooth = True
    lamp_data = bpy.data.lights.new("初期水体を照らす面光源", "AREA")
    lamp = bpy.data.objects.new(lamp_data.name, lamp_data)
    scene.collection.objects.link(lamp)
    lamp.location = (-4, -7, 10)
    lamp.rotation_euler = (Vector((0, 0, 2.4))-lamp.location).to_track_quat("-Z", "Y").to_euler()
    lamp_data.energy, lamp_data.size = 2000, 7
    _camera(scene, "初期水体_側面", (0, -15, 2.3), (0, 0, 2.3), 7)
    _camera(scene, "初期水体_斜視", (7, -10, 7), (0, 0, 2.3), 8)
    _camera(scene, "初期水体_反対側", (6, 10, 6), (0, 0, 2.3), 8)
    scene.camera = next(o for o in scene.objects if o.get("比較視点") == "初期水体_斜視")
    path = INPUTS / "参照水体.obj"
    write_obj(proxy, path)
    meta = {"説明": "参照模型を体積再構成した美術指定の初期水体。水面下はHoudiniのSDFで切断する。自然な形成過程は未計算。",
            "出典": source_path.name, "原OBJのSHA256": digest,
            "元の水線仮定_Y": 2.5, "水上高さ_m": height, "静水位_m": waterline,
            "Houdiniで指定する水面下の切断深さ_m": cut_depth, "再構成ボクセル_m": voxel,
            "簡略化座標からの倍率": scale, "簡略化座標の水平中心": center.tolist(),
            "修復前": initial_stats, "修復後": final_stats,
            "座標変換": "Blender (x,y,z) → Houdini (x,z,-y)。正回転。",
            "入力模型": path.name, "入力模型SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "制限": "水体の閉鎖性を確認。全表面の幾何誤差、自己交差、物理的成立は別検証。"}
    (INPUTS / "造形の由来.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    bpy.data.libraries.write(str(OUTPUT / "初期水体.blend"), {scene}, compress=True)
    return meta


def render(label="初期水体_斜視", name="proxy_oblique"):
    scene = bpy.context.scene
    scene.camera = next(o for o in scene.objects if o.get("比較視点") == label)
    scene.render.filepath = str(OUTPUT / (name+".png"))
    bpy.ops.render.render(write_still=True)
    return scene.render.filepath
