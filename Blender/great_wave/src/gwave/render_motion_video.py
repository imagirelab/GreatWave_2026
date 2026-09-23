"""Render a short review MP4 from the reproducible animated Blender scene.

The point caches are evaluated at their original 30-fps frame numbers. Rendering
every second source frame at 15 fps keeps the 9.5-second motion and two-second
final hold while making a compact video for GitHub review.
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
    ap.add_argument("--last-frame", type=int, default=None, help="short smoke render when set")
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("GW_VIDEO")
    if args.step < 1 or 30 % args.step:
        raise ValueError("--step must divide the original 30 fps")
    if args.width < 128 or args.width % 2:
        raise ValueError("--width must be even and at least 128 for H.264")

    scene = bpy.context.scene
    if "GreatWave" not in bpy.data.objects or args.camera not in bpy.data.objects:
        raise RuntimeError("Load a generated animated wave scene with the requested camera")
    wave = bpy.data.objects["GreatWave"]
    if not any(mod.type == "MESH_CACHE" for mod in wave.modifiers):
        raise RuntimeError("The wave scene has no animated point cache")
    out_path = paths.project_path(args.out)
    paths.ensure_parent(out_path)
    stem, ext = os.path.splitext(out_path)
    if ext.lower() != ".mp4":
        raise ValueError("--out must end with .mp4")
    scene.camera = bpy.data.objects[args.camera]
    paper = bpy.data.objects.get("Hokusai_paper_guide")
    if paper is not None:
        paper.hide_render = args.camera != "CAM_print"
    scene.frame_start = 1
    wp = wm.load_wave_params()
    scene.frame_end = int(args.last_frame or (int(wp["n_frames"]) + int(wp["hold_frames"])))
    if scene.frame_end < 1 or scene.frame_end > int(wp["n_frames"]) + int(wp["hold_frames"]):
        raise ValueError("--last-frame outside the configured animation")
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
        raise RuntimeError("Expected one MP4 at %s_*.mp4, found %s" % (stem, candidates))
    os.replace(candidates[0], out_path)
    if os.path.getsize(out_path) < 1000:
        raise RuntimeError("Rendered MP4 is unexpectedly small")
    bootstrap.log("video %s (%0.1f MB); camera=%s, %d source frames, %d fps, step=%d" %
                  (out_path, os.path.getsize(out_path) / 1e6, args.camera,
                   scene.frame_end, scene.render.fps, args.step))
    bootstrap.finish(True, "render_motion_video")


if __name__ == "__main__":
    main()
