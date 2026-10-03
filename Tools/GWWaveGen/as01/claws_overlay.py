# -*- coding: utf-8 -*-
"""美術の見本01 爪の部：原画視点の重ね図と数（OpenCV。Unity の描画を測る。原画カメラからの投影の色は使わない）。

入力：claws_run_render.sh の描画のフォルダー（views/painting_t120_claws.png と _clawfree.png）。爪の画素は「爪あり − 爪なし」の差（RGB の差の和 > THR）。
原画の爪：仕上げ32 の一覧（Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json）の main の爪の領域の多角形（region_polygon_ref_ds32、
無ければ region_polygon_ref）を表示の画素へ写した和。原画の空：Tools/PaintingTruth/targets/masks/sky_claws_cov.png（> 0.5 が空）。
数（記録のみ）：
  claw_px            爪の画素
  in_painting_claw   爪の画素のうち原画の爪の領域に入る割合（精度）
  painting_claw_cov  原画の爪の領域のうち爪の画素で覆われる割合（再現）
  out_to_sky_px      爪の画素のうち原画の空に出る画素（原画の輪郭の外へ出た分。≤ 4 px の関門そのものではない）
図：原画（淡く）＋ 原画の爪の領域の縁（橙）＋ 見本の爪の画素（青緑の半透明）。左に原画、中に見本の原画視点、右に重ね。
使い方：py -3.10 -B Tools/GWWaveGen/as01/claws_overlay.py 出力の名前 描画のフォルダー [描画のフォルダー …]（数は 出力の名前.json）
"""
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
import ds33_common as U  # noqa: E402

THR = 40
CROP = (300, 40, 1200, 640)
INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"
PAINT = REPO + "/Tools/PaintingTruth/build/painting_display.png"
SKY = REPO + "/Tools/PaintingTruth/targets/masks/sky_claws_cov.png"


def painting_claw_mask():
    inv = json.load(open(INV, encoding="utf-8"))
    m = np.zeros((1080, 1920), np.uint8)
    n = 0
    for c in inv["claws"]:
        if c["zone"] != "main":
            continue
        poly = c.get("region_polygon_ref_ds32") or c.get("region_polygon_ref")
        if not poly:
            continue
        q = U.to_disp(np.array(poly, np.float64))
        cv2.fillPoly(m, [np.round(q).astype(np.int32)], 255)
        n += 1
    return m > 0, n


def main():
    out = sys.argv[1]
    dirs = sys.argv[2:]
    pm, npoly = painting_claw_mask()
    sky = cv2.imread(SKY, cv2.IMREAD_UNCHANGED).astype(np.float64) / 65535.0 > 0.5
    paint = cv2.imread(PAINT)
    x0, y0, x1, y1 = CROP
    res = dict(tool="Tools/GWWaveGen/as01/claws_overlay.py", thr=THR, painting_claw_polygons=npoly, painting_claw_px=int(pm.sum()), runs={})
    rows = []
    for d in dirs:
        a = cv2.imread(os.path.join(d, "views", "painting_t120_claws.png")).astype(np.int32)
        b = cv2.imread(os.path.join(d, "views", "painting_t120_clawfree.png")).astype(np.int32)
        cm = np.abs(a - b).sum(-1) > THR
        cm = cv2.morphologyEx(cm.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0
        r = dict(claw_px=int(cm.sum()), in_painting_claw=round(float((cm & pm).sum() / max(cm.sum(), 1)), 4),
                 painting_claw_cov=round(float((cm & pm).sum() / max(pm.sum(), 1)), 4), out_to_sky_px=int((cm & sky).sum()))
        res["runs"][os.path.basename(os.path.normpath(d))] = r
        g = cv2.cvtColor(cv2.cvtColor(paint, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR).astype(np.float64)
        g = 0.55 * g + 0.45 * 255
        ov = g.copy()
        ov[cm] = 0.45 * ov[cm] + 0.55 * np.array([200, 170, 20], np.float64)
        edge = cv2.morphologyEx(pm.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
        ov[edge] = (0, 120, 255)
        sk = cm & sky
        ov[sk] = (60, 60, 230)
        lab = os.path.basename(os.path.normpath(d))
        tiles = [paint[y0:y1, x0:x1].copy(), a[y0:y1, x0:x1].astype(np.uint8).copy(), np.clip(ov, 0, 255).astype(np.uint8)[y0:y1, x0:x1].copy()]
        txt = ["painting", lab, "overlay: cyan=claws, orange=painting claw regions, red=claws in painting sky"]
        for t, s in zip(tiles, txt):
            for col, th in (((0, 0, 0), 3), ((255, 255, 255), 1)):
                cv2.putText(t, s, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, th, cv2.LINE_AA)
        rows.append(np.hstack(tiles))
    sheet = np.vstack(rows)
    cv2.imwrite(out + ".png", sheet)
    json.dump(res, open(out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OVERLAY", out + ".png", json.dumps(res["runs"], ensure_ascii=False))


if __name__ == "__main__":
    main()
