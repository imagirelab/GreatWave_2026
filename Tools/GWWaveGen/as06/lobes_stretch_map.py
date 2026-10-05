# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：帯の座標 w の伸びの三角形（G1）の場所を、Unity の描画の上に点で描く道具（隠れは見ない。場所を探すだけ）。
py -3.10 -B Tools/GWWaveGen/as06/lobes_stretch_map.py <主役波の静止のメッシュ.json> <描画のフォルダー> <出力.png>
"""
import json
import os
import sys

import cv2
import numpy as np

os.environ["AS04_FIX"] = "fix1"
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04")
import asm4_common as A  # noqa: E402
import asm4_rules as R  # noqa: E402


def main():
    p, rd, out = sys.argv[1:4]
    A.N_HERO = json.load(open(p, encoding="utf-8"))["vertices"]
    m = R.stretch_masks(p, "hero")
    bad = m["sel"] & m["pat"] & ((m["gw"] < 1 / 3) | (m["gw"] > 3))
    C = m["pos"][m["tri"][bad]].mean(1)
    tiles = []
    for v, f in (("painting", "views/painting_t120_clawfree.png"), ("tt0", "tt/t120_az000_noclaws.png"), ("tt330", "tt/t120_az330_noclaws.png"), ("seat_toward_wave", "views/seat_toward_wave_t120_clawfree.png")):
        im = cv2.imread(rd + "/" + f)
        cam = A.painting_cam(1) if v == "painting" else A.view_cam(v, im.shape[1], im.shape[0])
        xy, cz = cam.project(C)
        xy = np.asarray(xy); ok = np.asarray(cz) > 0
        sx = im.shape[1] / cam.W; sy = im.shape[0] / cam.H
        for (x, y), o in zip(xy, ok):
            if o:
                cv2.circle(im, (int(x * sx), int(y * sy)), 3, (0, 0, 255), -1)
        cv2.putText(im, v, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        tiles.append(cv2.resize(im, (960, 540)))
    cv2.imwrite(out, np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])]))
    print("bad", int(bad.sum()), out)


if __name__ == "__main__":
    main()
