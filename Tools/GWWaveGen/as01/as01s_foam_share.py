# -*- coding: utf-8 -*-
"""美術の見本01（Q29）改善の回 2：原画視点の爪の画素（爪あり − 爪なしの差、閾値 40）が、原画の「明るい所（紙の地の白と水色の版、空を除く）」に
載る割合と、原画の明るい所（主役波の頂と唇の帯の枠の内）を覆う割合（記録だけ。新しい関門ではない）。
原画の明るい所：原画の表示の画素の明るさ（Rec.601 の Y）> 150、かつ Tools/PaintingTruth/targets/masks/sky_claws_cov.png の空でない所。
枠：原画視点の頂と唇の帯（表示の画素 x 260〜1220、y 60〜620。as01s_sheets.py の ZOOM の全体と同じ x、下を船の手前まで）。
使い方：py -3.10 -B Tools/GWWaveGen/as01/as01s_foam_share.py <出力 json> <名前=描画のフォルダー> …
"""
import json
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
BOX = (260, 60, 1220, 620)


def main():
    out = sys.argv[1]
    P = cv2.imread(REPO + "/Tools/PaintingTruth/build/painting_display.png").astype(np.float64)
    Y = 0.299 * P[..., 2] + 0.587 * P[..., 1] + 0.114 * P[..., 0]
    sky = cv2.imread(REPO + "/Tools/PaintingTruth/targets/masks/sky_claws_cov.png", cv2.IMREAD_UNCHANGED).astype(np.float64) / 65535.0 > 0.5
    box = np.zeros(Y.shape, bool)
    x0, y0, x1, y1 = BOX
    box[y0:y1, x0:x1] = True
    light = (Y > 150) & ~sky & box
    res = dict(tool="Tools/GWWaveGen/as01/as01s_foam_share.py", box=BOX, painting_light_px=int(light.sum()), runs={})
    for kv in sys.argv[2:]:
        name, d = kv.split("=", 1)
        a = cv2.imread(d + "/views/painting_t120_claws.png").astype(int)
        b = cv2.imread(d + "/views/painting_t120_clawfree.png").astype(int)
        cl = (np.abs(a - b).sum(2) > 40) & box
        res["runs"][name] = dict(claw_px=int(cl.sum()), on_painting_light=round(float((cl & light).sum() / max(cl.sum(), 1)), 4),
                                 painting_light_cov=round(float((cl & light).sum() / max(light.sum(), 1)), 4))
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("FOAM_SHARE", json.dumps(res["runs"], ensure_ascii=False))


if __name__ == "__main__":
    main()
