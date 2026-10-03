# -*- coding: utf-8 -*-
"""美術の見本01 爪の部：numpy の下見の描画（作る間の確かめ。Unity の描画ではない）。

claws_build.py の出力（as01_entries.npy）と t* の主役波を、見直しの視点で z バッファに描き、一覧の図にする。
使い方：py -3.10 -B Tools/GWWaveGen/as01/claws_preview.py [--mesh …] [--out 図.png] [--views painting,seat,…] [--scale 0.5]
"""
import argparse
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
import claws_common as CC  # noqa: E402

DEF_VIEWS = "painting,seat,seat_toward_wave,side_left,side_right,back65,top,tt0,tt60,tt120,tt180,tt240,tt300"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default=CC.OUTD + "/mesh")
    ap.add_argument("--out", default=CC.OUTD + "/preview/preview_sheet.png")
    ap.add_argument("--views", default=DEF_VIEWS)
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--zones", default="")
    ap.add_argument("--crop", default="")
    a = ap.parse_args()
    ents = list(np.load(os.path.join(a.mesh, "as01_entries.npy"), allow_pickle=True))
    if a.zones:
        zs = set(a.zones.split(","))
        ents = [e for e in ents if e["zone"] in zs]
    hero = CC.Hero(CC.load_hero())
    W, H = int(1920 * a.scale), int(1080 * a.scale)
    tiles = []
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    for v in a.views.split(","):
        if v == "painting":
            c = CC.painting_cam()
            cam = CC.Cam(c.pos, c.f, c.u, 26.0, W, H)
        else:
            cam = CC.cam_view(v, W, H)
        img = CC.preview(cam, hero, ents)
        CC.label(img, v, s=0.6)
        cv2.imwrite(os.path.join(os.path.dirname(a.out), "pv_%s.png" % v), img)
        tiles.append(img)
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.full((rows * H, cols * W, 3), 230, np.uint8)
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        sheet[r * H:(r + 1) * H, c * W:(c + 1) * W] = t
    cv2.imwrite(a.out, sheet)
    print("PREVIEW_DONE", a.out)


if __name__ == "__main__":
    main()
