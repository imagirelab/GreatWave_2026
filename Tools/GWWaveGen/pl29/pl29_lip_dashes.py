# -*- coding: utf-8 -*-
"""仕上げ29 修正の回：唇の先の「梯子」（細い藍の帯の上の 1〜2 画素の暗い切れ切れの線）を数える（記録用）。

原画視点・爪なし（views/painting_<時刻>_clawfree.png）の唇の先のまわりの枠の中で、暗い画素（相対輝度 < 0.25：縁の線・藍濃）の連結成分（8 近傍）のうち、
大きさ 2〜40 画素の離れた小さな成分を「切れ切れの暗い線」として数える。輪郭の線や藍の面は大きな成分なので数えない。
枠：t 12 s は (880, 300)–(1140, 500)、t 10.5 s は (600, 300)–(860, 480)（1920×1080 の画素。どの版も同じ枠）。
出力：<out>/lip_dashes.json。使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_lip_dashes.py --render name=<dir> [name=<dir> …] --out <dir>
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

BOX = {"t120": (880, 300, 1140, 500), "t105": (600, 300, 860, 480)}
DARK, LO, HI = 0.25, 2, 40


def count(p, box):
    c = np.array(Image.open(p).convert("RGB").crop(box)).astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    lum = 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]
    dark = lum < DARK
    lab, n = ndi.label(dark, structure=np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())[1:] if n else np.array([])
    small = [int(s) for s in sizes if LO <= s <= HI]
    return {"smallDarkPieces": len(small), "smallDarkPx": int(sum(small)), "darkPx": int(dark.sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"schema": "GreatWave.Polish29.lip_dashes/1", "noteJa": __doc__.strip().split("\n")[0], "boxes": BOX, "darkRelLum": DARK, "pieceSizePx": [LO, HI], "renders": {}}
    for item in a.render:
        name, d = item.split("=", 1)
        res["renders"][name] = {"dir": d.replace("\\", "/")}
        for ts, box in BOX.items():
            p = os.path.join(d, "views", "painting_%s_clawfree.png" % ts)
            if os.path.exists(p):
                res["renders"][name][ts] = count(p, box)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "lip_dashes.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for k, v in res["renders"].items():
        print(k, {t: v.get(t) for t in BOX})


if __name__ == "__main__":
    main()
