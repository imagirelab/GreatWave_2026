"""Houdini の実計算サーフェスを読み、固定カメラで比較する。

Alembic の形状と時刻を変更しない。白波の物理計算や展示用の色面は
まだ付けず、巻込み・着水・飛散を確認するための単色表示とする。
"""

import json
from pathlib import Path

import bpy
from mathutils import Vector

from gwave.build_localized_scene import rgba


OUTPUT = Path(__file__).resolve().parents[2] / "results" / "fluid_preview"


def _camera(scene, name, position, target, scale):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z", "Y").to_euler()
    data.type = "ORTHO"
    data.ortho_scale = scale
    obj["比較視点"] = name
    return obj


def select_camera(scene, label):
    """別場面の同名カメラに左右されず、この場面の比較視点を選ぶ。"""
    return next(obj for obj in scene.objects if obj.type == "CAMERA" and obj.get("比較視点") == label)


def _material():
    material = bpy.data.materials.new("流体形状確認用の藍色")
    material.diffuse_color = rgba("#39758d")
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba("#39758d")
    shader.inputs["Roughness"].default_value = .42
    shader.inputs["Metallic"].default_value = .0
    return material


def build(cache_path, end_frame, fps=24, name="浅化する単波のFLIP確認"):
    """新しい場面へ実キャッシュまたは初期表面を読み込む。"""
    cache_path = Path(cache_path).resolve()
    if not cache_path.is_file():
        raise FileNotFoundError(cache_path)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 960, 600
    scene.render.resolution_percentage = 100
    scene.render.fps, scene.render.fps_base = fps, 1.0
    scene.frame_start, scene.frame_end = 1, int(end_frame)
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("形状確認用の明るい背景")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = rgba("#d8d0ba")
    bg.inputs["Strength"].default_value = .65
    previous = set(bpy.data.objects)
    if cache_path.suffix.lower() == ".obj":
        if end_frame != 1:
            raise ValueError("静止OBJの確認は1フレームに限定します")
        bpy.ops.wm.obj_import(filepath=str(cache_path), forward_axis="NEGATIVE_Z", up_axis="Y")
    else:
        bpy.ops.wm.alembic_import(filepath=str(cache_path), set_frame_range=False,
                                 always_add_cache_reader=True, as_background_job=False)
    imported = [obj for obj in bpy.data.objects if obj not in previous]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise ValueError("入力ファイルにサーフェスメッシュがありません")
    material = _material()
    for index, obj in enumerate(meshes):
        obj.name = f"FLIPの実計算サーフェス_{index+1}"
        obj.data.materials.clear()
        obj.data.materials.append(material)
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        obj["出典"] = cache_path.name
        obj["表示方法"] = "実キャッシュをそのまま再生。別の形状キーや強制変形は使わない"
    light_data = bpy.data.lights.new("形状を示す面光源", "AREA")
    light = bpy.data.objects.new(light_data.name, light_data)
    scene.collection.objects.link(light)
    light.location = (-4, -8, 12)
    light.rotation_euler = (Vector((0, 0, 0))-light.location).to_track_quat("-Z", "Y").to_euler()
    light_data.energy, light_data.size = 2300, 8
    _camera(scene, "CAM_側面確認", (0, -22, 1.2), (0, 0, 1.2), 14)
    _camera(scene, "CAM_斜面付近の側面", (2, -22, 1.3), (2, 0, 1.3), 8)
    scene.camera = _camera(scene, "CAM_斜め確認", (11, -17, 9), (0, 0, 1.0), 15)
    scene["検証段階"] = "低解像度の流体計算。北斎の造形・白波・体験の完成品質は未達"
    scene["キャッシュ"] = str(cache_path)
    scene.frame_set(1)
    manifest = {"説明": "入力サーフェスを変形せず表示する比較場面。", "cache": str(cache_path),
                "入力形式": cache_path.suffix.lower(),
                "frame_start": 1, "frame_end": end_frame, "fps": fps,
                "meshes": [obj.name for obj in meshes], "samples": sample_geometry(meshes, [1, end_frame])}
    (OUTPUT / "import_check.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    scene.frame_set(1)
    bpy.data.libraries.write(str(OUTPUT / "fluid_preview.blend"), {scene}, compress=True)
    return scene


def sample_geometry(objects, frames):
    """頂点の時間変化と読込後の軸を調べる。物理精度の検査とは区別する。"""
    rows = []
    for frame in frames:
        bpy.context.scene.frame_set(int(frame))
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
            rows.append({"frame": int(frame), "object": obj.name,
                         "vertices": len(points), "faces": len(mesh.polygons),
                         "min": [min(p[axis] for p in points) for axis in range(3)] if points else None,
                         "max": [max(p[axis] for p in points) for axis in range(3)] if points else None})
            evaluated.to_mesh_clear()
    return rows


def render_still(frame, camera="CAM_斜め確認", suffix="oblique"):
    scene = bpy.context.scene
    scene.camera = select_camera(scene, camera)
    scene.frame_set(frame)
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT / f"fluid_{suffix}_{frame:03d}.png")
    bpy.ops.render.render(write_still=True)
    return scene.render.filepath


def render_movie(camera="CAM_斜め確認", suffix="oblique"):
    """元のフレームレートで一度だけ再生し、待機やループを足さない。"""
    scene = bpy.context.scene
    scene.camera = select_camera(scene, camera)
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    stem = OUTPUT / f"fluid_{suffix}_"
    scene.render.filepath = str(stem)
    bpy.ops.render.render(animation=True)
    # 別視点の末尾名や過去のフレーム範囲を同じ動画と取り違えない。
    rendered = OUTPUT / f"{stem.name}{scene.frame_start:04d}-{scene.frame_end:04d}.mp4"
    if not rendered.is_file():
        raise RuntimeError(f"指定した範囲の動画がありません: {rendered.name}")
    target = OUTPUT / f"fluid_{suffix}.mp4"
    rendered.replace(target)
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    return str(target)
