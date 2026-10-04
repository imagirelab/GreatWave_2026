# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：一艘目の船（boat_left）を原画のカメラを中心とする相似で動かす倍率 s を決める（K-boat、名前の付いた美術の誘導）。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_boat.py
- 船の画素：見本04 の Unity の原画視点の ID の画（assemble/render/FX1/full/ids_noline_noclaws.png、3840×2160、boat_left の色 (34,0,0)）。
- 船の奥行き：AF27 の配置（Tools/GWContext/context_layout.json）の向きで、船の長い軸（ローカル z）は原画のカメラの向きとほぼ直角（奥行きの成分 0.00）、
  幅の軸（ローカル x）が奥行きの向き（0.98）。船の点の前向きの深さは根の深さ ± HALF_BEAM m とみなす。
- s = （③ の面が船の画素で最初に当たる前向きの深さの最小 − MARGIN）÷（根の前向きの深さ + HALF_BEAM）。原画視点の船の画は画素まで同じ（相似）。
出力：Unity/Build/Polish/sample05/shapeA/l3/boat_scale.json
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402
import s5_targets as T5  # noqa: E402
import w4_common as W  # noqa: E402

A = T5.A
IDS = C.P4 + "/assemble/render/FX1/full/ids_noline_noclaws.png"
HALF_BEAM, MARGIN = 1.6, 0.6


def main():
    im = cv2.imread(IDS)[..., ::-1]
    m = (im[..., 0] == 34) & (im[..., 1] == 0) & (im[..., 2] == 0)
    ch, tri, _ = W.read_static(C.L3_JSON)
    P = ch["position"].astype(np.float64)
    cam = A.painting_cam(2)
    _, D, _ = A.raster(cam, P[tri.astype(np.int64)], np.full(len(tri), 3, np.int16))
    z = D[m]
    hit = np.isfinite(z)
    zpiv = float((C.BOAT_U - cam.pos) @ cam.f)
    zmin = float(z[hit].min()) if hit.any() else np.inf
    s = (zmin - MARGIN) / (zpiv + HALF_BEAM)
    s = float(min(s, 1.0))
    newpos = cam.pos + s * (C.BOAT_U - cam.pos)
    rep = {"ids_image": IDS, "ids_sha256": C.sha(IDS), "boat_left_px_2x": int(m.sum()), "boat_px_covered_by_layer3": int(hit.sum()),
           "layer3_min_forward_depth_over_boat_px_m": C.rnd(zmin), "boat_pivot_forward_depth_m": C.rnd(zpiv), "half_beam_m": HALF_BEAM, "margin_m": MARGIN,
           "scale": round(s, 4), "pivot_unity_before": C.BOAT_U.tolist(), "pivot_unity_after": C.rnd(newpos.tolist(), 4),
           "pivot_sec_after": C.rnd(C.K.sec(newpos[None])[0].tolist(), 3),
           "dist_to_painting_cam_before_after_m": [C.rnd(float(np.linalg.norm(C.BOAT_U - cam.pos))), C.rnd(float(np.linalg.norm(newpos - cam.pos)))],
           "note_ja": "名前の付いた美術の誘導：一艘目の船を ③ の面の手前に置く（原画で舳先が ③ の藍の面の手前に描かれる）。原画のカメラを中心とする相似なので原画視点の画は同じ、ほかの視点では s 倍の大きさ"}
    C.jdump(C.OUT + "/l3/boat_scale.json", rep)
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
