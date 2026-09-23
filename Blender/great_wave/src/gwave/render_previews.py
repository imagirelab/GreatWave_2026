"""保存済みの great_wave.blend の確認画像を Workbench で画面なしで出力する。
    tools/run_blender.ps1 src/gwave/render_previews.py -Blend blend/great_wave.blend [-ScriptArgs '--video']
results/wave_build/preview/ に主要フレームの CAM_view34 / CAM_print / CAM_front 画像、
一覧画像、原画と重ねた CAM_print の最終画像、および任意の CAM_view34 動画を出力する。"""
import argparse
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import numpy as np

from gw import bootstrap, draw, imgio, paths
from gwave import profile_motion as wm

KEY_FRAMES = [1, 60, 110, 140, 152, 170, 190, 210, 250, 285]


def render_still(scene, cam_name, frame, path, res, percentage=100):
    import bpy
    scene.camera = bpy.data.objects[cam_name]
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = percentage
    scene.frame_set(frame)
    scene.render.filepath = path
    try:
        scene.render.image_settings.media_type = "IMAGE"
    except Exception:
        pass
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)


def main():
    import bpy
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--frames", default=None)
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("GW")
    scene = bpy.context.scene
    out = paths.ensure_dir(os.path.join(wm.PROJECT, "results", "wave_build", "preview"))
    frames = [int(v) for v in args.frames.split(",")] if args.frames else KEY_FRAMES
    # 確認画像用の近めの斜め構図。保存済みの .blend のカメラは維持する。
    try:
        from mathutils import Vector
        H = float(paths.param("WAVE_HEIGHT_M"))
        c = bpy.data.objects["CAM_view34"]
        c.location = (2.3 * H, -3.4 * H, 1.15 * H)
        c.data.lens = 38.0
        v = Vector((-0.35 * H, 0.0, 0.38 * H)) - c.location
        c.rotation_mode = "QUATERNION"
        c.rotation_quaternion = v.to_track_quat("-Z", "Y")
    except Exception as ex:
        bootstrap.log("カメラ構図の上書きに失敗しました: %r" % (ex,))
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.render_aa = "8"
    scene.render.film_transparent = False
    scene.render.dither_intensity = 0.0

    sheets = {}
    for cam, res in (("CAM_view34", (1280, 720)), ("CAM_print", (1286, 864)), ("CAM_front", (1280, 720))):
        if cam not in bpy.data.objects:
            continue
        imgs = []
        for f in frames:
            p = os.path.join(out, "%s_f%03d.png" % (cam, f))
            render_still(scene, cam, f, p, res)
            imgs.append(imgio.load_image_rgb(p))
        sheets[cam] = imgs
        sheet = draw.grid(imgs, ncols=5, gap=6, labels=["f%d" % f for f in frames], label_scale=2, cell_size=(640, 430))
        imgio.save_png(os.path.join(out, "contact_%s.png" % cam), sheet)
        bootstrap.log("一覧画像", cam)

    # CAM_print の最終フレームを原画に重ねる。
    if "CAM_print" in sheets:
        last = sheets["CAM_print"][-1].astype(np.float32)
        pa = draw.resize(imgio.load_image_rgb(paths.painting_path()), new_w=last.shape[1], new_h=last.shape[0]).astype(np.float32)
        mix = (0.5 * last + 0.5 * pa).clip(0, 255).astype(np.uint8)
        imgio.save_png(os.path.join(out, "final_CAM_print_over_painting.png"), mix)

    if args.video:
        scene.camera = bpy.data.objects["CAM_view34"]
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        scene.render.resolution_percentage = 100
        ok = False
        try:
            scene.render.image_settings.media_type = "VIDEO"
        except Exception:
            pass
        try:
            scene.render.image_settings.file_format = "FFMPEG"
            scene.render.ffmpeg.format = "MPEG4"
            scene.render.ffmpeg.codec = "H264"
            scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
            scene.render.filepath = os.path.join(out, "great_wave_view34_")
            bpy.ops.render.render(animation=True)
            ok = True
        except Exception as ex:
            bootstrap.log("動画のレンダリングに失敗しました: %r" % (ex,))
        bootstrap.log("動画を出力しました" if ok else "動画は出力されていません")
    bootstrap.log("出力先", out)
    bootstrap.finish(True, "render_previews")


if __name__ == "__main__":
    main()
