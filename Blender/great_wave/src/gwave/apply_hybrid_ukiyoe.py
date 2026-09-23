"""最終形状への絵画投影と3Dシェーダーを視点に応じて混合する実験。

絵画は UV の V 軸で版画用カメラに近い波の側面だけに適用し、視点が CAM_print
から離れるにつれて薄くする。この方法は HMD 用途では不採用の実験である。
版画用カメラから15度傾けると投影された細部が長い水平線になった。
正面と34度の終点の画像が良好でも、この中間視点の問題は残る。
角度の適用範囲を狭めると、線状の乱れが急激な見た目の変化に置き換わる。

アニメーションする泡のオブジェクトを作成したシーンで実行する例::

    tools/run_blender.ps1 src/gwave/apply_hybrid_ukiyoe.py \
        -Blend blend/great_wave_foam.blend -NoFactoryStartup
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from gw import bootstrap, frame as gw_frame, paths
from gwave import profile_motion as wm
from gwave.add_animated_foam import BAND_NAME, CLAW_INK_NAME, CLAW_WHITE_NAME
from gwave.apply_procedural_ukiyoe import apply as apply_procedural
from gwave.apply_ukiyoe_style import _set_final_projection_uv


def _scalar_ramp(nodes, links, source, stops):
    """[0, 1] の値で指定したグレースケールのランプ出力を返す。"""
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    cr = ramp.color_ramp
    cr.elements.remove(cr.elements[1])
    for i, (position, value) in enumerate(stops):
        e = cr.elements[0] if i == 0 else cr.elements.new(float(position))
        e.position = float(position)
        e.color = (float(value), float(value), float(value), 1.0)
    links.new(source, ramp.inputs["Fac"])
    return ramp.outputs["Color"]


def apply():
    import bpy

    scene = bpy.context.scene
    wave = bpy.data.objects.get("GreatWave")
    if wave is None:
        raise RuntimeError("生成済みの GreatWave シーンを先に読み込んでください")
    # 泡の独立した輪郭がない状態で版画との混合結果を比較すると誤解を招くため、
    # 泡の工程を完了したシーンを入力として要求する。
    available = {ob.name for ob in scene.objects}
    missing = {BAND_NAME, CLAW_INK_NAME, CLAW_WHITE_NAME} - available
    if missing:
        raise RuntimeError("別途アニメーションさせた泡のシーンを読み込んでください。不足: %s" % ", ".join(sorted(missing)))

    apply_procedural()
    final_frame = int(wm.load_wave_params()["n_frames"])
    _set_final_projection_uv(scene, wave, final_frame, gw_frame.Frame.from_params())

    image = bpy.data.images.load(paths.painting_path(), check_existing=True)
    image.pack()
    mat = wave.active_material
    if mat is None or not mat.use_nodes:
        raise RuntimeError("プロシージャルマテリアルを作成できませんでした")
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    emission = next((node for node in nodes if node.type == "EMISSION"), None)
    if emission is None or not emission.inputs["Color"].is_linked:
        raise RuntimeError("プロシージャルマテリアルの発光色が接続されていません")
    procedural_colour = emission.inputs["Color"].links[0].from_socket

    projection_uv = nodes.new("ShaderNodeUVMap")
    projection_uv.uv_map = "Hokusai_final_projection"
    painting = nodes.new("ShaderNodeTexImage")
    painting.image = image
    painting.extension = "EXTEND"
    painting.interpolation = "Linear"
    links.new(projection_uv.outputs["UV"], painting.inputs["Vector"])

    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    uv_sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], uv_sep.inputs["Vector"])
    # 版画用カメラは +Y 方向を見る。V が小さい側はカメラに近い側面。
    # 中央と遠い側面には斜め視点の縞を避けるため3Dシェーダーを維持し、
    # マテリアルの連続性を保つため遷移を広く取る。
    near_flank = _scalar_ramp(nodes, links, uv_sep.outputs["Y"],
                              [(0.0, 1.0), (0.40, 1.0), (0.60, 0.0), (1.0, 0.0)])

    geometry = nodes.new("ShaderNodeNewGeometry")
    incoming_unit = nodes.new("ShaderNodeVectorMath")
    incoming_unit.operation = "NORMALIZE"
    links.new(geometry.outputs["Incoming"], incoming_unit.inputs[0])
    incoming_sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(incoming_unit.outputs["Vector"], incoming_sep.inputs["Vector"])
    abs_y = nodes.new("ShaderNodeMath")
    abs_y.operation = "ABSOLUTE"
    links.new(incoming_sep.outputs["Y"], abs_y.inputs[0])
    side_view = _scalar_ramp(nodes, links, abs_y.outputs[0],
                             [(0.0, 0.0), (0.90, 0.0), (0.985, 1.0), (1.0, 1.0)])
    projection_weight = nodes.new("ShaderNodeMath")
    projection_weight.operation = "MULTIPLY"
    links.new(near_flank, projection_weight.inputs[0])
    links.new(side_view, projection_weight.inputs[1])

    hybrid = nodes.new("ShaderNodeMixRGB")
    hybrid.blend_type = "MIX"
    links.new(projection_weight.outputs[0], hybrid.inputs[0])
    links.new(procedural_colour, hybrid.inputs[1])
    links.new(painting.outputs["Color"], hybrid.inputs[2])
    links.new(hybrid.outputs["Color"], emission.inputs["Color"])
    wave["visual_method"] = "実験: UV 側面と視点角による最終絵画投影／プロシージャル3Dシェーダーの混合"
    wave["visual_limit"] = "HMD 用途では不採用: 15度で投影の線状乱れが生じる。UV は最終形状の1組のみ"
    scene.frame_set(final_frame)


def main():
    import bpy

    bootstrap.set_log_prefix("GW_HYBRID")
    apply()
    out = os.path.join(wm.PROJECT, "blend", "great_wave_hybrid_foam.blend")
    paths.ensure_parent(out)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    bootstrap.log("保存しました: %s" % out)
    bootstrap.finish(True, "apply_hybrid_ukiyoe")


if __name__ == "__main__":
    main()
