"""アニメーションする GreatWave メッシュに視点非依存の青と泡のシェーダーを適用する。

色帯には波の弧長 U と峰方向の V 座標を用いるため、PC2 キャッシュで変形しても
3D 表面に追従する。これは美術表現のためのマテリアル試作である。
独立して動く白波は別の生成処理で追加する。この色を流体物理として検証したものではない。

    tools/run_blender.ps1 src/gwave/apply_procedural_ukiyoe.py -Blend blend/great_wave.blend -NoFactoryStartup
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import numpy as np

from gw import bootstrap, frame as gw_frame, paths
from gwave import profile_motion as wm
from gwave.apply_ukiyoe_style import _make_background, _emission_material


def _linear_rgb(code):
    srgb = np.array([int(code[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def _rgba(code):
    return (*[float(v) for v in _linear_rgb(code)], 1.0)


def _set_ramp(ramp, stops, interpolation="EASE"):
    cr = ramp.color_ramp
    cr.interpolation = interpolation
    cr.elements.remove(cr.elements[1])
    for i, (position, colour) in enumerate(stops):
        e = cr.elements[0] if i == 0 else cr.elements.new(position)
        e.position = float(position)
        e.color = _rgba(colour)


def _math(nodes, links, operation, first, second=None):
    """ソケットまたは数値定数からスカラー演算ノードを作る。"""
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    for index, value in enumerate((first, second)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = float(value)
        else:
            links.new(value, node.inputs[index])
    return node.outputs[0]


def make_wave_material():
    import bpy

    mat = bpy.data.materials.get("GW_Ukiyoe_procedural") or bpy.data.materials.new("GW_Ukiyoe_procedural")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    mat.node_tree.animation_data_clear()
    links = mat.node_tree.links

    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], sep.inputs["Vector"])

    u, v = sep.outputs["X"], sep.outputs["Y"]

    # 原画では波の背の上部が淡く、その下は濃青である。U のみで色を分けると、
    # 側面の多くの列が投影上で近い U を持つため、CAM_print では色境界が
    # X 一定の縦線になった。境界の U を高さ、峰方向の V、UV に追従する細部で変化させる。
    position = nodes.new("ShaderNodeNewGeometry")
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"], xyz.inputs["Vector"])
    z_h = _math(nodes, links, "MULTIPLY", xyz.outputs["Z"], 1.0 / gw_frame.Frame.from_params().H)
    z_h.node.use_clamp = True

    broad_noise = nodes.new("ShaderNodeTexNoise")
    broad_noise.inputs["Scale"].default_value = 11.0
    broad_noise.inputs["Detail"].default_value = 2.5
    broad_noise.inputs["Roughness"].default_value = 0.65
    links.new(uv.outputs["UV"], broad_noise.inputs["Vector"])
    fine_noise = nodes.new("ShaderNodeTexNoise")
    fine_noise.inputs["Scale"].default_value = 37.0
    fine_noise.inputs["Detail"].default_value = 2.0
    links.new(uv.outputs["UV"], fine_noise.inputs["Vector"])
    broad_shift = _math(nodes, links, "MULTIPLY", _math(nodes, links, "SUBTRACT", broad_noise.outputs["Fac"], 0.5), 0.065)
    fine_shift = _math(nodes, links, "MULTIPLY", _math(nodes, links, "SUBTRACT", fine_noise.outputs["Fac"], 0.5), 0.022)
    bend_phase = _math(nodes, links, "ADD", _math(nodes, links, "MULTIPLY", v, 40.0),
                       _math(nodes, links, "MULTIPLY", u, 12.0))
    bend_shift = _math(nodes, links, "MULTIPLY", _math(nodes, links, "SINE", bend_phase), 0.012)
    shift = _math(nodes, links, "ADD", broad_shift, _math(nodes, links, "ADD", fine_shift, bend_shift))
    boundary = _math(nodes, links, "ADD", _math(nodes, links, "ADD", 0.515,
                                                 _math(nodes, links, "MULTIPLY", z_h, 0.07)), shift)
    edge_coordinate = _math(nodes, links, "ADD", _math(nodes, links, "SUBTRACT", u, boundary), 0.5)
    dark_side = nodes.new("ShaderNodeValToRGB")
    _set_ramp(dark_side, [(0.0, "#000000"), (0.473, "#000000"),
                          (0.527, "#ffffff"), (1.0, "#ffffff")], "EASE")
    links.new(edge_coordinate, dark_side.inputs["Fac"])

    low_back = nodes.new("ShaderNodeValToRGB")
    _set_ramp(low_back, [(0.0, "#b0b0b0"), (0.14, "#777777"),
                         (0.38, "#000000"), (1.0, "#000000")], "EASE")
    links.new(z_h, low_back.inputs["Fac"])
    blue_coverage = _math(nodes, links, "MAXIMUM", dark_side.outputs["Color"], low_back.outputs["Color"])

    # CAM_print では複数の波頭の列が同じ X=0 に投影されるが、U 座標は大きく異なる場合がある。
    # 重なりに継ぎ目が見えないよう、ワールド空間の狭い帯で色を合わせる。
    x_h = _math(nodes, links, "MULTIPLY", xyz.outputs["X"], 1.0 / gw_frame.Frame.from_params().H)
    crest_x_h = nodes.new("ShaderNodeValue")
    crest_x_h.name = "GW_animated_crest_x_H"
    crest_x_h.label = "動く波頭の X / H"
    motion = wm.WaveMotion(wm.load_wave_params())
    for f in range(1, motion.n_frames + 1):
        crest_x_h.outputs[0].default_value = motion.x_c_of_frame(f)
        crest_x_h.outputs[0].keyframe_insert(data_path="default_value", frame=f)
    relative_x_h = _math(nodes, links, "SUBTRACT", x_h, crest_x_h.outputs[0])
    seam_weight = nodes.new("ShaderNodeValToRGB")
    _set_ramp(seam_weight, [(0.0, "#ffffff"), (0.025, "#ffffff"),
                            (0.21, "#000000"), (1.0, "#000000")], "EASE")
    links.new(_math(nodes, links, "ABSOLUTE", relative_x_h), seam_weight.inputs["Fac"])
    seam_blue_coverage = nodes.new("ShaderNodeValToRGB")
    _set_ramp(seam_blue_coverage, [(0.0, "#ffffff"), (0.60, "#ffffff"),
                                   (0.92, "#000000"), (1.0, "#000000")], "EASE")
    links.new(z_h, seam_blue_coverage.inputs["Fac"])
    coverage_mix = nodes.new("ShaderNodeMixRGB")
    coverage_mix.blend_type = "MIX"
    links.new(seam_weight.outputs["Color"], coverage_mix.inputs[0])
    links.new(blue_coverage, coverage_mix.inputs[1])
    links.new(seam_blue_coverage.outputs["Color"], coverage_mix.inputs[2])

    paper_foam = nodes.new("ShaderNodeValToRGB")
    _set_ramp(paper_foam, [(0.0, "#b6d0cf"), (0.30, "#e0e9df"),
                           (0.56, "#f1ecdd"), (1.0, "#eee9da")])
    links.new(z_h, paper_foam.inputs["Fac"])
    body_blue = nodes.new("ShaderNodeValToRGB")
    _set_ramp(body_blue, [(0.0, "#507e9d"), (0.48, "#2b638a"),
                          (0.58, "#123d66"), (0.66, "#143a63"),
                          (0.73, "#326b91"), (0.84, "#78a1af"),
                          (1.0, "#a9c9ca")], "CONSTANT")
    links.new(u, body_blue.inputs["Fac"])

    # 藍色の帯は変形中も表面に追従する。V で帯を選び、U で流れる水面に沿って緩やかに曲げる。
    bands = nodes.new("ShaderNodeTexWave")
    bands.wave_type = "BANDS"
    bands.bands_direction = "Y"
    bands.wave_profile = "SIN"
    bands.inputs["Scale"].default_value = 8.0
    bands.inputs["Distortion"].default_value = 2.2
    bands.inputs["Detail Scale"].default_value = 2.0
    links.new(uv.outputs["UV"], bands.inputs["Vector"])
    band_ramp = nodes.new("ShaderNodeValToRGB")
    _set_ramp(band_ramp, [(0.0, "#749cb2"), (0.47, "#3b7298"),
                          (0.53, "#173a63"), (1.0, "#0d2b50")], "CONSTANT")
    links.new(bands.outputs["Fac"], band_ramp.inputs["Fac"])
    band_mix = nodes.new("ShaderNodeMixRGB")
    band_mix.blend_type = "MULTIPLY"
    band_mix.inputs[0].default_value = 0.42
    links.new(body_blue.outputs["Color"], band_mix.inputs[1])
    links.new(band_ramp.outputs["Color"], band_mix.inputs[2])

    seam_blue_mix = nodes.new("ShaderNodeMixRGB")
    seam_blue_mix.blend_type = "MIX"
    links.new(seam_weight.outputs["Color"], seam_blue_mix.inputs[0])
    links.new(band_mix.outputs["Color"], seam_blue_mix.inputs[1])
    seam_blue_mix.inputs[2].default_value = _rgba("#1b4770")

    body_mix = nodes.new("ShaderNodeMixRGB")
    body_mix.blend_type = "MIX"
    links.new(coverage_mix.outputs["Color"], body_mix.inputs[0])
    links.new(paper_foam.outputs["Color"], body_mix.inputs[1])
    links.new(seam_blue_mix.outputs["Color"], body_mix.inputs[2])

    # 巻き込む部分に点在する明るい斑点で木版画の泡を示唆する。
    fleck_noise = nodes.new("ShaderNodeTexNoise")
    fleck_noise.inputs["Scale"].default_value = 72.0
    fleck_noise.inputs["Detail"].default_value = 2.0
    links.new(uv.outputs["UV"], fleck_noise.inputs["Vector"])
    fleck_gate = nodes.new("ShaderNodeValToRGB")
    _set_ramp(fleck_gate, [(0.0, "#000000"), (0.69, "#000000"), (0.77, "#ffffff"), (1.0, "#ffffff")], "LINEAR")
    links.new(fleck_noise.outputs["Fac"], fleck_gate.inputs["Fac"])
    head_gate = nodes.new("ShaderNodeValToRGB")
    _set_ramp(head_gate, [(0.0, "#000000"), (0.52, "#000000"), (0.59, "#ffffff"),
                          (0.75, "#ffffff"), (0.88, "#000000"), (1.0, "#000000")])
    links.new(u, head_gate.inputs["Fac"])
    fleck_mul = nodes.new("ShaderNodeMath")
    fleck_mul.operation = "MULTIPLY"
    links.new(fleck_gate.outputs["Color"], fleck_mul.inputs[0])
    links.new(head_gate.outputs["Color"], fleck_mul.inputs[1])
    fleck_mix = nodes.new("ShaderNodeMixRGB")
    fleck_mix.blend_type = "MIX"
    links.new(fleck_mul.outputs[0], fleck_mix.inputs[0])
    links.new(body_mix.outputs["Color"], fleck_mix.inputs[1])
    fleck_mix.inputs[2].default_value = _rgba("#f3f0e1")

    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(fleck_mix.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def apply():
    import bpy

    scene = bpy.context.scene
    obj = bpy.data.objects["GreatWave"]
    mat = make_wave_material()
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    obj["visual_method"] = "3D UV に基づくプロシージャルな青い帯と泡の斑点"
    obj["visual_limit"] = "図案用シェーダーの試作。原画の領域や船上・HMD の照明に合わせた調整は未完了"
    fr = gw_frame.Frame.from_params()
    _make_background(fr)
    sea = bpy.data.objects.get("Sea_ref")
    if sea:
        sea.hide_render = False
        sea.data.materials.clear()
        sea.data.materials.append(_emission_material("GW_sea_flat", _rgba("#8eacb9")))
    world = scene.world or bpy.data.worlds.new("GW_world")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = _rgba("#e4d8c0")
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.camera = bpy.data.objects["CAM_print"]
    scene.render.resolution_x, scene.render.resolution_y = 1286, 864
    scene.render.resolution_percentage = 100
    scene.frame_set(int(wm.load_wave_params()["n_frames"]))


def main():
    import bpy

    bootstrap.set_log_prefix("GW_PROC")
    apply()
    out = os.path.join(wm.PROJECT, "blend", "great_wave_procedural.blend")
    paths.ensure_parent(out)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    bootstrap.log("シーン: %s" % out)
    bootstrap.finish(True, "apply_procedural_ukiyoe")


if __name__ == "__main__":
    main()
