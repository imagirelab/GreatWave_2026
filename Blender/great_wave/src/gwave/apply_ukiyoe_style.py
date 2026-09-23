"""北斎の参照画像をカメラ投影し、アニメーションするメッシュに貼る。

UV 座標は評価済みの最終形状から固定する。そのためアニメーションする頂点に
追従し、285 フレーム目には版画用カメラから原画の対応する座標を参照する。
これは大波の見た目を比較する基準である。別途モデル化する泡や、
視点非依存の浮世絵シェーダーの代わりにはならない。

build_great_wave.py の後に実行する::

    tools/run_blender.ps1 src/gwave/apply_ukiyoe_style.py -Blend blend/great_wave.blend

生成したスタイル付きシーンは Git の対象外である blend/ に置く。
このスクリプトと参照画像からマテリアルを再現できる。
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import numpy as np

from gw import bootstrap, frame as gw_frame, paths
from gwave import profile_motion as wm


def _emission_material(name, color):
    import bpy

    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def _projected_material(image_path):
    import bpy

    image = bpy.data.images.load(image_path, check_existing=True)
    image.pack()
    mat = bpy.data.materials.get("Hokusai_projected_wave") or bpy.data.materials.new("Hokusai_projected_wave")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "Hokusai_final_projection"
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.extension = "EXTEND"
    tex.interpolation = "Linear"
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links = mat.node_tree.links
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def _set_final_projection_uv(scene, obj, final_frame, frame):
    """元のメッシュは最初のフレームなので、評価済みの形状を使う。"""
    import bpy

    scene.frame_set(final_frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    xyz = np.empty(len(evaluated.data.vertices) * 3, np.float32)
    evaluated.data.vertices.foreach_get("co", xyz)
    xyz = xyz.reshape(-1, 3)
    if not np.isfinite(xyz).all() or float(xyz[:, 2].max()) < 0.7 * frame.H:
        raise RuntimeError("最終フレームの点キャッシュがないか、まだ評価されていません")
    if len(xyz) != len(obj.data.vertices):
        raise RuntimeError("トポロジーを変えるモディファイアーにより投影 UV を固定できません")
    uv = obj.data.uv_layers.get("Hokusai_final_projection") or obj.data.uv_layers.new(name="Hokusai_final_projection")
    loop_ids = np.empty(len(obj.data.loops), dtype=np.int32)
    obj.data.loops.foreach_get("vertex_index", loop_ids)
    X = xyz[loop_ids, 0] / frame.H
    Z = xyz[loop_ids, 2] / frame.H
    u = (X - frame.x_left) / frame.frame_w
    v = (Z - frame.z_bottom) / frame.frame_h
    uv.data.foreach_set("uv", np.stack([u, v], axis=1).astype(np.float32).ravel())
    return float(xyz[:, 2].max()), len(xyz)


def _make_background(frame):
    """大波の静止コピーを含まない、紙と遠景の海の参照面。"""
    import bpy

    obj = bpy.data.objects.get("Hokusai_paper_guide")
    if obj is None:
        x0, x1 = frame.x_left * frame.H, frame.x_right * frame.H
        z0, z1 = frame.z_bottom * frame.H, frame.z_top * frame.H
        y = 4.5 * frame.H
        mesh = bpy.data.meshes.new("Hokusai_paper_guide")
        mesh.from_pydata([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [], [(0, 1, 2, 3)])
        uv = mesh.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
        obj = bpy.data.objects.new("Hokusai_paper_guide", mesh)
        bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.get("Hokusai_paper_and_sea") or bpy.data.materials.new("Hokusai_paper_and_sea")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    uv = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    cr = ramp.color_ramp
    cr.elements.remove(cr.elements[1])
    for pos, color in ((0.0, (0.24, 0.32, 0.36, 1)),
                       (0.29, (0.58, 0.59, 0.55, 1)),
                       (0.38, (0.83, 0.78, 0.66, 1)),
                       (1.0, (0.89, 0.84, 0.73, 1))):
        e = cr.elements[0] if pos == 0.0 else cr.elements.new(pos)
        e.position, e.color = pos, color
    em = nodes.new("ShaderNodeEmission")
    out = nodes.new("ShaderNodeOutputMaterial")
    links = mat.node_tree.links
    links.new(uv.outputs["UV"], sep.inputs["Vector"])
    links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], em.inputs["Color"])
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def apply():
    import bpy

    scene = bpy.context.scene
    WP = wm.load_wave_params()
    final_frame = int(WP["n_frames"])
    obj = bpy.data.objects["GreatWave"]
    fr = gw_frame.Frame.from_params()
    crest_m, vertex_count = _set_final_projection_uv(scene, obj, final_frame, fr)
    mat = _projected_material(paths.painting_path())
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    _make_background(fr)

    # 古い Workbench 用の海の参照面は CAM_print では側面から見えるが、
    # Eevee を有効にすると別視点で波を隠す場合がある。
    sea = bpy.data.objects.get("Sea_ref")
    if sea:
        sea.hide_render = True
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.camera = bpy.data.objects["CAM_print"]
    scene.render.resolution_x = 1286
    scene.render.resolution_y = 864
    scene.render.resolution_percentage = 100
    obj["visual_method"] = "最終フレームの版画用カメラによる UV 投影。元の PC2 波メッシュで動かす"
    obj["visual_limit"] = "単一視点のテクスチャー参照。泡の形状と HMD 対応の視点非依存シェーディングは別工程"
    scene.frame_set(final_frame)
    return {"crest_m": crest_m, "vertices": vertex_count}


def main():
    import bpy

    bootstrap.set_log_prefix("GW_STYLE")
    stats = apply()
    out = os.path.join(wm.PROJECT, "blend", "great_wave_styled.blend")
    paths.ensure_parent(out)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    bootstrap.log("スタイル付きシーン %s、波頭 %.3f m、頂点数 %d" % (out, stats["crest_m"], stats["vertices"]))
    bootstrap.finish(True, "apply_ukiyoe_style")


if __name__ == "__main__":
    import bpy
    main()
