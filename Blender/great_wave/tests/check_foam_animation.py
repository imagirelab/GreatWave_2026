"""白波アニメーションの .blend を開き直した後、独立した白波キャッシュを検査する。

    tools/run_blender.ps1 tests/check_foam_animation.py -Blend blend/great_wave_foam.blend -NoFactoryStartup

主波のみを判定する正式な S/M/G 試験を補完する検査である。
"""

import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")))

import numpy as np

from gw import bootstrap, frame as gw_frame, paths
from gwave.add_animated_foam import BAND_NAME, CLAW_INK_NAME, CLAW_WHITE_NAME, CLAWS
from gwave import profile_motion as wm


def _coords(obj):
    import bpy

    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    flat = np.empty(len(evaluated.data.vertices) * 3, np.float32)
    evaluated.data.vertices.foreach_get("co", flat)
    return flat.reshape(-1, 3)


def main():
    import bpy

    bootstrap.set_log_prefix("GW_FOAM_CHECK")
    scene = bpy.context.scene
    names = ("GreatWave", BAND_NAME, CLAW_INK_NAME, CLAW_WHITE_NAME)
    frames = (1, 210, int(wm.load_wave_params()["n_frames"]))
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise AssertionError("網目が見つからない: %s" % name)
        md = next((m for m in obj.modifiers if m.type == "MESH_CACHE"), None)
        if md is None:
            raise AssertionError("独立した点キャッシュがない: %s" % name)
        path = bpy.path.abspath(md.filepath)
        with open(path, "rb") as fh:
            sig, version, count, start, step, samples = struct.unpack("<12siiffi", fh.read(32))
        if sig.rstrip(b"\0") != b"POINTCACHE2" or count != len(obj.data.vertices) or samples != frames[-1]:
            raise AssertionError("PC2 のヘッダーまたはトポロジーが一致しない: %s" % name)
        if os.path.getsize(path) != 32 + 12 * count * samples:
            raise AssertionError("PC2 のファイルサイズが一致しない: %s" % name)

    samples = {}
    for f in frames:
        scene.frame_set(f)
        samples[f] = {name: _coords(bpy.data.objects[name]) for name in names}
        for name, xyz in samples[f].items():
            if not np.isfinite(xyz).all():
                raise AssertionError("フレーム %d の %s に有限でない頂点がある" % (f, name))

    H = gw_frame.Frame.from_params().H
    changes = {}
    for name in names[1:]:
        now = samples[frames[-1]][name]
        start = samples[frames[0]][name]
        mid = samples[frames[1]][name]
        total = float(np.max(np.linalg.norm(now - start, axis=1)) / H)
        late = float(np.max(np.linalg.norm(now - mid, axis=1)) / H)
        if total <= 0.01 or late <= 0.005:
            raise AssertionError("白波オブジェクト %s が後半で十分に動いていない" % name)
        changes[name] = {"first_to_final_max_H": total, "mid_to_final_max_H": late}

    ink = samples[frames[-1]][CLAW_INK_NAME].reshape(len(CLAWS), 23, 8, 3)
    tip = ink[0, -1].mean(axis=0)
    fr = gw_frame.Frame.from_params()
    x_px, y_px = [float(v) for v in fr.m_to_px(tip[0], tip[2])]
    expected = CLAWS[0][1]
    tip_error_px = math.hypot(x_px - expected[0], y_px - expected[1])
    if tip_error_px > 1.0:
        raise AssertionError("最外側の爪先が原画上の目標から %.3f px 離れている" % tip_error_px)

    report = {"frames": frames, "objects": {name: len(bpy.data.objects[name].data.vertices) for name in names},
              "motion": changes, "farthest_claw_target_px": expected,
              "farthest_claw_center_px": [x_px, y_px], "tip_error_px": tip_error_px}
    out = paths.project_path("results/foam_check/metrics.json")
    paths.ensure_parent(out)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    bootstrap.log("独立した白波の検査に合格。フレーム %s、先端誤差 %.4f px、報告 %s" %
                  (frames, tip_error_px, out))
    bootstrap.finish(True, "check_foam_animation")


if __name__ == "__main__":
    main()
