"""スタイルを適用した Blender シーンから確認用フレームを出力する。

    tools/run_blender.ps1 src/gwave/render_ukiyoe_preview.py -Blend blend/great_wave_styled.blend -NoFactoryStartup

版画用カメラの一覧画像で動きと最終形状へのテクスチャー位置合わせを確認する。
斜め視点では投影マテリアルの単一視点という制約が分かる。
どちらの画像も泡や HMD での検証を代替しない。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from gw import bootstrap, draw, imgio, paths
from gwave import profile_motion as wm


def render_frame(scene, camera_name, frame, out_file, width, height):
    import bpy

    scene.camera = bpy.data.objects[camera_name]
    paper = bpy.data.objects.get("Hokusai_paper_guide")
    if paper is not None:
        paper.hide_render = camera_name != "CAM_print"
    scene.frame_set(frame)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = out_file
    bpy.ops.render.render(write_still=True)


def main():
    import bpy

    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="1,110,170,210,250,285")
    ap.add_argument("--view34", action="store_true")
    ap.add_argument("--variant", default="projection", help="results/ukiyoe_preview の下に作る出力フォルダー名")
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("GW_PREVIEW")
    scene = bpy.context.scene
    if "GreatWave" not in bpy.data.objects:
        raise RuntimeError("レンダリングの前に生成済みの GreatWave .blend を読み込んでください")
    out_dir = paths.ensure_dir(os.path.join(wm.PROJECT, "results", "ukiyoe_preview", args.variant))
    frames = [int(x) for x in args.frames.split(",")]
    cameras = [("CAM_print", 1286, 864)]
    if args.view34:
        cameras.append(("CAM_view34", 1280, 720))
    for camera, width, height in cameras:
        images = []
        for frame in frames:
            out_file = os.path.join(out_dir, "%s_f%03d.png" % (camera, frame))
            render_frame(scene, camera, frame, out_file, width, height)
            images.append(imgio.load_image_rgb(out_file))
            bootstrap.log("レンダリング完了: %s、フレーム %d" % (camera, frame))
        sheet = draw.grid(images, ncols=3, gap=8, labels=["f%d" % f for f in frames],
                          label_scale=2, cell_size=(643, 432))
        imgio.save_png(os.path.join(out_dir, "contact_%s.png" % camera), sheet)
    bootstrap.finish(True, "render_ukiyoe_preview")


if __name__ == "__main__":
    main()
