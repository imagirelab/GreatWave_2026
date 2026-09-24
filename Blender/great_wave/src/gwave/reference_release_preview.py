"""参照初期水体の実FLIPと、独立計算した白波を同じ時刻で表示する。"""

import json
from pathlib import Path

import bpy
from mathutils import Vector

from gwave import fluid_preview, fluid_ukiyoe


def build(main_cache, output, end_frame=96, whitewater_cache=None,
          whitewater_end=None, whitewater_first_visible=3, stylized=False):
    """読込み時に形状と時間を変更しない。白波の計算範囲を超えて表示しない。"""
    if whitewater_cache is not None:
        if whitewater_end is None or end_frame > whitewater_end:
            raise ValueError("白波の最終時刻を指定し、表示をその範囲内にしてください")
        if not Path(whitewater_cache).is_file():
            raise FileNotFoundError(whitewater_cache)
    fluid_preview.OUTPUT = Path(output).resolve()
    scene = fluid_preview.build(main_cache, end_frame, fps=24,
                                name="参照初期値の実流体と独立白波の比較")
    settings = [
        ("CAM_側面確認", (2, -22, 2.3), (2, 0, 2.3), 13),
        ("CAM_斜め確認", (10, -15, 8), (2, 0, 1.5), 11),
        ("CAM_斜面付近の側面", (0, -15, 2.3), (0, 0, 2.3), 7),
    ]
    for label, position, target, scale in settings:
        camera = fluid_preview.select_camera(scene, label)
        camera.location = position
        camera.rotation_euler = (Vector(target)-camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
    fluid_preview._camera(scene, "CAM_波冠の斜視", (6, -11, 5), (0, 0, 2.1), 8)
    if stylized:
        fluid_ukiyoe.apply(scene)
    white_objects = []
    if whitewater_cache is not None:
        previous = set(bpy.data.objects)
        bpy.ops.wm.alembic_import(filepath=str(Path(whitewater_cache).resolve()),
                                 set_frame_range=False, always_add_cache_reader=True,
                                 as_background_job=False)
        white_objects = [obj for obj in bpy.data.objects if obj not in previous and obj.type == "MESH"]
        if not white_objects:
            raise ValueError("白波キャッシュにメッシュがありません")
        if stylized:
            material = fluid_ukiyoe.material("別計算した白波の色面", foam=True)
        else:
            material = bpy.data.materials.new("別計算した白波の確認用白色")
            material.use_nodes = True
            shader = material.node_tree.nodes.get("Principled BSDF")
            shader.inputs["Base Color"].default_value = (.87, .88, .79, 1)
            shader.inputs["Roughness"].default_value = .8
        for index, obj in enumerate(white_objects):
            obj.name = f"独立した白波の実計算メッシュ_{index+1}"
            obj.data.materials.clear()
            obj.data.materials.append(material)
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
            obj["出典"] = Path(whitewater_cache).name
            obj["表示方法"] = "独立Whitewater Solverの粒子から表面化。主波面の白塗りではない"
            # Alembicの先頭の空形状は読込み時に最初の非空形状へ丸められる。
            # 計算で実際に粒子が生まれた時刻まで表示を止め、出生を前倒ししない。
            obj.driver_add("hide_render").driver.expression = f"frame < {int(whitewater_first_visible)}"
            obj.driver_add("hide_viewport").driver.expression = f"frame < {int(whitewater_first_visible)}"
        scene["白波キャッシュ"] = str(Path(whitewater_cache).resolve())
    scene["検証段階"] = "初期造形の崩壊を調べる試作。目標の形成・持続・浮世絵表現は未達"
    scene.camera = fluid_preview.select_camera(scene, "CAM_波冠の斜視")
    scene.frame_set(1)
    manifest = {
        "説明": "主FLIPと独立白波の実キャッシュ表示。時刻の引延ばし、姿勢の保持、ループを追加しない。",
        "主流体": str(Path(main_cache).resolve()),
        "白波": str(Path(whitewater_cache).resolve()) if whitewater_cache else None,
        "表示範囲": [1, end_frame], "FPS": 24, "色面の試験": stylized,
        "白波の初回表示フレーム": whitewater_first_visible if whitewater_cache else None,
        "先頭の空白": "最初の非空形状より前は非表示。読込メッシュの座標が存在しても表示しない。",
        "白波の読込検査": fluid_preview.sample_geometry(white_objects, [1, min(6, end_frame), end_frame]),
        "制限": "小規模な確認用。北斎の造形・運動の合格、Unity再生、HMD性能を示すものではない。",
    }
    (fluid_preview.OUTPUT / "表示条件.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    scene.frame_set(1)
    bpy.data.libraries.write(str(fluid_preview.OUTPUT / "実流体と白波の比較.blend"), {scene}, compress=True)
    return scene
