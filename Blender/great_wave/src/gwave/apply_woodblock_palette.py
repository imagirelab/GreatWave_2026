"""北斎風の少数色パレットをアニメーションする3D波の固定された面に割り当てる。

これは版画用カメラからの正確な投影実験に対応する、意図的に粗い視点非依存の試作である。
各面の色は最終形状で原画から一度選び、以後は PC2 の頂点とともに動く。
奥行きに応じて参照位置を少しずらし、波頭に画像がそのまま伸びる状態を避ける。
独立して動く泡と爪状の形状は別途必要である。

    tools/run_blender.ps1 src/gwave/apply_woodblock_palette.py -Blend blend/great_wave.blend -NoFactoryStartup
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import numpy as np

from gw import bootstrap, frame as gw_frame, paths
from gwave import profile_motion as wm
from gwave.apply_ukiyoe_style import _make_background


PALETTE = (
    ("paper_foam", "#f3f0e1"),
    ("warm_foam", "#e4d8c0"),
    ("sea_mist", "#bfd6d6"),
    ("light_ice", "#9fb3c1"),
    ("wave_blue", "#34678f"),
    ("prussian_blue", "#1b395a"),
    ("deep_ink", "#142b4c"),
    ("distant_gray", "#565e60"),
    ("boat_ochre", "#bb907b"),
)


def _hex_linear(code):
    rgb = np.array([int(code[k:k + 2], 16) / 255.0 for k in (1, 3, 5)])
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _hex_srgb(code):
    return np.array([int(code[k:k + 2], 16) / 255.0 for k in (1, 3, 5)])


def _flat_material(name, linear_rgb):
    import bpy

    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*[float(c) for c in linear_rgb], 1.0)
    mat.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def _final_face_centres(scene, obj, final_frame):
    import bpy

    scene.frame_set(final_frame)
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    xyz = np.empty(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", xyz)
    xyz = xyz.reshape(-1, 3)
    faces = wm.grid_faces(int(obj["gw_n_u"]), int(obj["gw_n_v"]))
    if len(faces) != len(obj.data.polygons):
        raise RuntimeError("波のトポロジーが想定した規則格子と異なります")
    return xyz[faces].mean(axis=1)


def _sample_image(image, frame, centres):
    pixels = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(pixels)
    width, height = int(image.size[0]), int(image.size[1])
    rgba = pixels.reshape(height, width, 4)
    # 奥行き方向の参照位置を控えめにずらす。版画の大きな色面を保ちながら、
    # 厚みを持たせた表面には峰に沿った変化を与える。
    X, Y, Z = (centres[:, k] / frame.H for k in range(3))
    Xs = X + 0.045 * np.sin(3.0 * Y + 1.5 * X)
    Zs = Z + 0.018 * np.sin(4.5 * Y - 2.0 * Z)
    x = np.clip(np.rint((Xs - frame.x_left) / frame.frame_w * (width - 1)), 0, width - 1).astype(np.int32)
    y = np.clip(np.rint((Zs - frame.z_bottom) / frame.frame_h * (height - 1)), 0, height - 1).astype(np.int32)
    return rgba[y, x, :3]


def apply():
    import bpy

    scene = bpy.context.scene
    obj = bpy.data.objects["GreatWave"]
    final_frame = int(wm.load_wave_params()["n_frames"])
    frame = gw_frame.Frame.from_params()
    centres = _final_face_centres(scene, obj, final_frame)
    image = bpy.data.images.load(paths.painting_path(), check_existing=True)
    colours = _sample_image(image, frame, centres)
    palette_srgb = np.stack([_hex_srgb(hex_colour) for _, hex_colour in PALETTE])
    palette_linear = np.stack([_hex_linear(hex_colour) for _, hex_colour in PALETTE])
    # 紙色付近の差を少し圧縮し、濃紺の面積を確保する。
    distances = ((colours[:, None, :] - palette_srgb[None, :, :]) ** 2).sum(axis=2)
    indices = distances.argmin(axis=1).astype(np.int32)
    obj.data.materials.clear()
    for name, _ in PALETTE:
        obj.data.materials.append(_flat_material("GW_" + name, palette_linear[len(obj.data.materials)]))
    obj.data.polygons.foreach_set("material_index", indices)
    obj["visual_method"] = "最終形状で参照した絵画の色を、固定された面ごとに9種類の木版画風マテリアルへ量子化"
    obj["visual_limit"] = "配色の参照用。計測済みの泡モデルや検証済みの HMD シェーダーではない"
    _make_background(frame)
    sea = bpy.data.objects.get("Sea_ref")
    if sea:
        sea.hide_render = True
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.camera = bpy.data.objects["CAM_print"]
    scene.render.resolution_x, scene.render.resolution_y = 1286, 864
    scene.render.resolution_percentage = 100
    scene.frame_set(final_frame)
    return np.bincount(indices, minlength=len(PALETTE)).tolist()


def main():
    import bpy

    bootstrap.set_log_prefix("GW_PALETTE")
    counts = apply()
    out = os.path.join(wm.PROJECT, "blend", "great_wave_woodblock.blend")
    paths.ensure_parent(out)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    bootstrap.log("パレット別の面数: " + ", ".join("%s=%d" % (PALETTE[i][0], n) for i, n in enumerate(counts)))
    bootstrap.log("シーン: %s" % out)
    bootstrap.finish(True, "apply_woodblock_palette")


if __name__ == "__main__":
    main()
