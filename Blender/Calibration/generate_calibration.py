"""Blender と Unity の長さ・軸・鏡映を確かめる最小校正データを新規作成する。

使用例:
blender --background --factory-startup --python generate_calibration.py

既存作品や試作は一切読み込まない。出力先は本ファイルと同じフォルダー。
生成した blend の再読込と FBX の空シーンへの再読込を数値で検証する。
Unity での検証は別工程であり、本スクリプトの合格には含めない。
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector


OUTPUT_DIR = Path(__file__).resolve().parent
TOLERANCE_M = 1e-5
SPECIFICATIONS = [
    # 名前、Blender 右手座標系での中心 [m]、寸法 [m]、表示色。
    ('Calibration_Cube_1m', (0.0, 0.0, 0.5), (1.0, 1.0, 1.0), (0.65, 0.65, 0.65, 1.0)),
    ('Axis_PosX_2m', (2.0, 0.0, 0.0), (0.20, 0.10, 0.10), (0.85, 0.04, 0.04, 1.0)),
    ('Axis_PosY_3m', (0.0, 3.0, 0.0), (0.10, 0.30, 0.10), (0.04, 0.65, 0.06, 1.0)),
    ('Axis_PosZ_4m', (0.0, 0.0, 4.0), (0.10, 0.10, 0.40), (0.04, 0.16, 0.90, 1.0)),
    ('Axis_NegX_1p5m', (-1.5, 0.0, 0.0), (0.15, 0.15, 0.15), (0.95, 0.45, 0.04, 1.0)),
    ('Handedness_P123', (1.0, 2.0, 3.0), (0.12, 0.20, 0.28), (0.72, 0.04, 0.78, 1.0)),
]

EXPORT_FLAGS = {
    'check_existing': False,
    'use_selection': True,
    'global_scale': 1.0,
    'apply_unit_scale': True,
    'apply_scale_options': 'FBX_SCALE_UNITS',
    'axis_forward': '-Z',
    'axis_up': 'Y',
    'use_space_transform': True,
    'bake_space_transform': False,
    'object_types': {'MESH'},
    'use_mesh_modifiers': True,
    'use_triangles': False,
    'mesh_smooth_type': 'OFF',
    'use_custom_props': True,
    'bake_anim': False,
    'add_leaf_bones': False,
    'path_mode': 'STRIP',
    'embed_textures': False,
}

IMPORT_FLAGS = {
    'global_scale': 1.0,
    'use_manual_orientation': False,
    'bake_space_transform': False,
    'use_anim': False,
    'use_image_search': False,
    'use_custom_props': True,
}


def clear_scene():
    """元データや直前のシーンが検証へ混入しないよう空の初期状態にする。"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'


def create_objects():
    for name, center, dimensions, rgba in SPECIFICATIONS:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
        obj = bpy.context.object
        obj.name = name
        obj.data.name = name + '_Mesh'
        obj.scale = dimensions
        # 位置も含めて適用する。各オブジェクトの変換は単位行列となる。
        # したがって位置検証では Transform.position でなく形状の中心を使う。
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj['calibration_role'] = name
        obj['unit'] = 'metre'
        mat = bpy.data.materials.new(name + '_Material')
        mat.diffuse_color = rgba
        if mat.node_tree:
            mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = rgba
        obj.data.materials.append(mat)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='SELECT')


def record_geometry():
    """ワールド頂点から寸法と中心を求める。Transform 値だけの検証にしない。"""
    result = {}
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        if obj.type != 'MESH':
            continue
        points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        low = [min(p[axis] for p in points) for axis in range(3)]
        high = [max(p[axis] for p in points) for axis in range(3)]
        result[obj.name] = {
            'bounds_min_m': low,
            'bounds_max_m': high,
            'center_m': [(a + b) / 2 for a, b in zip(low, high)],
            'dimensions_m': [b - a for a, b in zip(low, high)],
            'vertex_count': len(points),
            'polygon_count': len(obj.data.polygons),
            'world_vertices_m': sorted([list(p) for p in points]),
            'object_location': list(obj.location),
            'object_rotation_euler_rad': list(obj.rotation_euler),
            'object_scale': list(obj.scale),
        }
    return result


def validate_expected(objects, stage):
    expected_names = {item[0] for item in SPECIFICATIONS}
    if set(objects) != expected_names:
        raise AssertionError(f'{stage}: 名前の集合が一致しない: {list(objects)}')
    maximum_error = 0.0
    for name, center, dimensions, _rgba in SPECIFICATIONS:
        actual = objects[name]
        for key, expected in [('center_m', center), ('dimensions_m', dimensions)]:
            error = max(abs(a - b) for a, b in zip(actual[key], expected))
            maximum_error = max(maximum_error, error)
            if error > TOLERANCE_M:
                raise AssertionError(f'{stage}: {name} {key}: 誤差 {error} m')
        if actual['vertex_count'] != 8 or actual['polygon_count'] != 6:
            raise AssertionError(f'{stage}: {name}: 頂点または面数が不正')
    # 軸マーカーの順序付き三重積。鏡映または軸順序の逆転を検出する。
    x = Vector(objects['Axis_PosX_2m']['center_m'])
    y = Vector(objects['Axis_PosY_3m']['center_m'])
    z = Vector(objects['Axis_PosZ_4m']['center_m'])
    triple_product = x.dot(y.cross(z))
    if abs(triple_product - 24.0) > 10 * TOLERANCE_M:
        raise AssertionError(f'{stage}: 三重積が 24 m^3 と一致しない')
    return {'passed': True, 'maximum_dimension_or_center_error_m': maximum_error,
            'ordered_axis_triple_product_m3': triple_product}


def compare_vertices(source, imported):
    maximum_error = 0.0
    for name in source:
        # 再読込の頂点番号は保持される保証がないため、最近接の全単射を確認する。
        remaining = [Vector(p) for p in imported[name]['world_vertices_m']]
        for position in source[name]['world_vertices_m']:
            point = Vector(position)
            index = min(range(len(remaining)), key=lambda i: (remaining[i] - point).length)
            error = (remaining.pop(index) - point).length
            maximum_error = max(maximum_error, error)
            if error > TOLERANCE_M:
                raise AssertionError(f'{name}: FBX の頂点が元形状と一致しない: {error} m')
    return maximum_error


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    blend_path = OUTPUT_DIR / 'Calibration.blend'
    fbx_path = OUTPUT_DIR / 'calibration.fbx'
    clear_scene()
    create_objects()
    source = record_geometry()
    source_check = validate_expected(source, '生成直後')
    for name, geometry in source.items():
        assert max(abs(v) for v in geometry['object_location']) < 1e-9, name
        assert max(abs(v) for v in geometry['object_rotation_euler_rad']) < 1e-9, name
        assert max(abs(v - 1.0) for v in geometry['object_scale']) < 1e-9, name

    # 保存は source の状態で行う。FBX 検証用シーンを blend に上書きしない。
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    export_result = bpy.ops.export_scene.fbx(filepath=str(fbx_path), **EXPORT_FLAGS)
    if 'FINISHED' not in export_result:
        raise RuntimeError('FBX 書き出し未完了')

    clear_scene()
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    saved = record_geometry()
    blend_check = validate_expected(saved, 'blend 再読込')
    blend_check['maximum_world_vertex_error_m'] = compare_vertices(source, saved)

    clear_scene()
    import_result = bpy.ops.import_scene.fbx(filepath=str(fbx_path), **IMPORT_FLAGS)
    if 'FINISHED' not in import_result:
        raise RuntimeError('FBX 再読込未完了')
    bpy.context.view_layer.update()
    reimported = record_geometry()
    fbx_check = validate_expected(reimported, 'FBX 再読込')
    fbx_check['maximum_world_vertex_error_m'] = compare_vertices(source, reimported)

    report = {
        'schema_version': 1,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'description_ja': '新規生成した長さ・軸・鏡映の校正データ。Unity 側は別途実測する。',
        'software': {'name': 'Blender', 'version': bpy.app.version_string,
                     'build_hash': bpy.app.build_hash.decode('ascii')},
        'source_coordinate_system': {'handedness': 'right', 'up_axis': '+Z',
                                     'unit_system': 'METRIC', 'scale_length': 1.0,
                                     'length_unit': 'METERS'},
        'all_source_object_transforms_applied': True,
        'measurement_note_ja': '中心・寸法は変換済みワールド頂点から測定。全オブジェクトの原点は (0,0,0)。',
        'tolerance_m': TOLERANCE_M,
        'export_flags': {k: sorted(v) if isinstance(v, set) else v for k, v in EXPORT_FLAGS.items()},
        'reimport_flags': IMPORT_FLAGS,
        'source_geometry': source,
        'fbx_reimport_geometry': reimported,
        'checks': {'source_geometry': source_check, 'saved_blend_reopen': blend_check,
                   'fbx_reimport': fbx_check},
        'files': {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size}
                  for p in [blend_path, fbx_path, Path(__file__).resolve()]},
        'unity_validation': {'status': 'NOT_RUN',
                             'note_ja': 'Unity の実インポート後にスケール・軸変換・法線を検証する。Blender の往復検証を Unity の合格と扱わない。'},
        'hmd_validation': {'status': 'NOT_RUN', 'note_ja': 'ユーザーは現在 HMD を所持していない。'},
    }
    (OUTPUT_DIR / 'validation_blender.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('CALIBRATION_BLENDER_PASS ' + json.dumps(report['checks'], ensure_ascii=False))


if __name__ == '__main__':
    main()
