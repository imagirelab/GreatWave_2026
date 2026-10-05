# -*- coding: utf-8 -*-
"""原画を PaintingCam v1 の表示フレーム（1920×1080、原画は縦いっぱい・左右に黒帯）へ置いた背景板を作る。
評価器（Tools/PaintingTruth/evaluate.py の Truth.disp_rgb）と同じ写像・同じ画素なので、Houdini のカメラ背景に使うと
評価器の座標と 1 画素単位で重なる。出力は Git 対象外の Unity/Build/Q20H/plate/。
usage: py -3.10 kh_plate.py [out.png]
       py -3.10 kh_plate.py blend <houdini_painting_view.png> <out.png> [alpha=0.5]"""
import os
import sys
import json

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kh_common as KC  # noqa: E402
sys.path.insert(0, os.path.join(KC.REPO, "Tools", "PaintingTruth"))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
import truthlib as T  # noqa: E402


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else KC.PLATE
    os.makedirs(os.path.dirname(out), exist_ok=True)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    ref_rgb, disp_rgb = T.painting_display(spec, fm)
    img = np.asarray(disp_rgb, np.uint8).copy()
    img[:, :int(fm.x0)] = 0; img[:, int(fm.x1) + 1:] = 0          # 採点しない左右の帯は黒（仕様の「左右の黒帯」）
    Image.fromarray(img).save(out)
    info = {"plate": out, "sha256": KC.sha256(out), "size": [int(disp_rgb.shape[1]), int(disp_rgb.shape[0])],
            "painting": KC.PAINTING, "painting_sha256": KC.sha256(KC.PAINTING),
            "mapping": spec["display_frame"]["ref_to_display_ja"], "scale": fm.s, "offset_x": fm.ox,
            "black_bars_outside_scored_columns": [int(fm.x0), int(fm.x1)]}
    json.dump(info, open(os.path.splitext(out)[0] + ".json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(info, ensure_ascii=False))


def blend(render_png, out_png, alpha=0.5):
    """Houdini の原画視点の描画と背景板を半々に重ねる（輪郭の見比べ用）。"""
    a = np.asarray(Image.open(KC.PLATE).convert("RGB"), np.float32)
    b = np.asarray(Image.open(render_png).convert("RGB").resize((a.shape[1], a.shape[0])), np.float32)
    Image.fromarray(np.clip(a * (1 - alpha) + b * alpha, 0, 255).astype(np.uint8)).save(out_png)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "blend":
        blend(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.5)
    else:
        main()
