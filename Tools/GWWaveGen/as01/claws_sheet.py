# -*- coding: utf-8 -*-
"""美術の見本01 爪の部：Unity の描画（claws_run_render.sh の出力）から、見直しの視点ごとに頂と唇の所を切り出して並べる図（OpenCV）。

切り出しの枠は、t* の主役波の頂と唇の帯（行 40〜235、列 c_tip − 110 〜 c_tip + 35）を各視点へ投影した範囲（1〜99 パーセンタイル、余白 8 割の 1 割、16:9）。
使い方：py -3.10 -B Tools/GWWaveGen/as01/claws_sheet.py 出力.png 描画のフォルダー [描画のフォルダー 2 …] [--views …] [--w 640] [--kind claws]
  フォルダーを 2 つ以上渡すと、視点ごとに横へ並べる（前後の図）。
"""
import argparse
import os

import cv2
import numpy as np

BOX = {"painting": [0, 4, 1560, 882], "seat": [0, 314, 1361, 1080], "seat_toward_wave": [0, 0, 1515, 852], "side_left": [634, 310, 1380, 730], "side_right": [630, 336, 1380, 758], "back65": [522, 167, 1685, 821], "top": [581, 363, 1192, 707], "tt0": [146, 207, 1332, 874], "tt30": [154, 157, 1277, 789], "tt60": [276, 130, 1421, 774], "tt90": [462, 199, 1495, 780], "tt120": [434, 208, 1593, 860], "tt150": [345, 218, 1592, 920], "tt180": [437, 218, 1705, 931], "tt210": [449, 193, 1710, 902], "tt240": [416, 122, 1777, 887], "tt270": [442, 180, 1695, 885], "tt300": [316, 217, 1640, 962], "tt330": [308, 223, 1618, 960]}
ALL = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"] + ["tt%d" % a for a in range(0, 360, 30)]


def path_of(d, v, kind):
    if v.startswith("tt"):
        return os.path.join(d, "tt", "t120_az%03d_%s.png" % (int(v[2:]), kind))
    return os.path.join(d, "views", "%s_t120_%s.png" % (v, kind))


def tile(p, v, w, lab):
    im = cv2.imread(p)
    h = int(round(w * 9 / 16))
    if im is None:
        return np.full((h, w, 3), 40, np.uint8)
    x0, y0, x1, y1 = BOX[v]
    c = cv2.resize(im[y0:y1, x0:x1], (w, h), interpolation=cv2.INTER_AREA)
    for col, th in (((0, 0, 0), 3), ((255, 255, 255), 1)):
        cv2.putText(c, lab, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, th, cv2.LINE_AA)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--views", default=",".join(ALL))
    ap.add_argument("--w", type=int, default=640)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--kind", default="claws")
    ap.add_argument("--labels", default="")
    a = ap.parse_args()
    views = a.views.split(",")
    labs = a.labels.split(",") if a.labels else [os.path.basename(os.path.normpath(d)) for d in a.dirs]
    tiles = []
    for v in views:
        row = [tile(path_of(d, v, a.kind), v, a.w, "%s  %s" % (v, lb)) for d, lb in zip(a.dirs, labs)]
        tiles.append(np.hstack(row))
    cols = a.cols if len(a.dirs) == 1 else 1
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)])
    cv2.imwrite(a.out, sheet)
    print("SHEET", a.out, sheet.shape)


if __name__ == "__main__":
    main()
