"""再現可能な Blender アニメーションシーンから確認用の短い MP4 を出力する。

点キャッシュは元の 30 fps のフレーム番号で評価する。1 フレームおきに 15 fps で
レンダリングし、9.5 秒の動きと最終形状での 2 秒の静止を保ったまま、
GitHub で確認しやすい小さな動画にする。
"""

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from gw import bootstrap, paths
from gwave import profile_motion as wm


def main():
    import bpy

    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", choices=("CAM_print", "CAM_view34"), default="CAM_print")
    ap.add_argument("--out", default="results/video/great_wave_motion_print.mp4")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--last-frame", type=int, default=None, help="指定すると短い動作確認用レンダリングになる")
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("GW_VIDEO")
    if args.step < 1 or 30 % args.step:
        raise ValueError("--step は元の 30 fps を割り切れる値にしてください")
    if args.width < 128 or args.width % 2:
        raise ValueError("H.264 用の --width は 128 以上の偶数にしてください")

    scene = bpy.context.scene
    if "GreatWave" not in bpy.data.objects or args.camera not in bpy.data.objects:
        raise RuntimeError("指定したカメラを含む生成済みの波アニメーションシーンを読み込んでください")
    wave = bpy.data.objects["GreatWave"]
    if not any(mod.type == "MESH_CACHE" for mod in wave.modifiers):
        raise RuntimeError("波のシーンにアニメーション用の点キャッシュがありません")
    out_path = paths.project_path(args.out)
    paths.ensure_parent(out_path)
    stem, ext = os.path.splitext(out_path)
    if ext.lower() != ".mp4":
        raise ValueError("--out の末尾を .mp4 にしてください")
    scene.camera = bpy.data.objects[args.camera]
    paper = bpy.data.objects.get("Hokusai_paper_guide")
    if paper is not None:
        paper.hide_render = args.camera != "CAM_print"
    scene.frame_start = 1
    wp = wm.load_wave_params()
    scene.frame_end = int(args.last_frame or (int(wp["n_frames"]) + int(wp["hold_frames"])))
    if scene.frame_end < 1 or scene.frame_end > int(wp["n_frames"]) + int(wp["hold_frames"]):
        raise ValueError("--last-frame が設定されたアニメーションの範囲外です")
    scene.frame_step = args.step
    scene.render.fps = int(wp["fps"]) // args.step
    scene.render.resolution_x = args.width
    scene.render.resolution_y = 2 * round(args.width * (2594 / 3859 if args.camera == "CAM_print" else 9 / 16) / 2)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.filepath = stem + "_"
    bpy.ops.render.render(animation=True)
    candidates = glob.glob(stem + "_*.mp4")
    if len(candidates) != 1:
        raise RuntimeError("%s_*.mp4 に MP4 が1件あるはずですが、検出結果は %s です" % (stem, candidates))
    os.replace(candidates[0], out_path)
    if os.path.getsize(out_path) < 1000:
        raise RuntimeError("出力した MP4 の容量が想定より小さすぎます")
    bootstrap.log("動画 %s (%0.1f MB)、カメラ=%s、元フレーム数=%d、%d fps、間引き間隔=%d" %
                  (out_path, os.path.getsize(out_path) / 1e6, args.camera,
                   scene.frame_end, scene.render.fps, args.step))
    bootstrap.finish(True, "render_motion_video")


if __name__ == "__main__":
    main()
