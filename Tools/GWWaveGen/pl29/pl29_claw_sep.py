# -*- coding: utf-8 -*-
"""仕上げ29 修正の回：立体の爪が、作品のままの色の画像で後ろの主役波から分かれて見えるかを数える（記録用）。

pl29_after_measure.py の「溶けた爪」は線なしの ID の画像で数えるので、爪の縁の線（設計38）を数えない。ここでは作品のままの色の画像
（views/<視点>_<時刻>_asis.png、回り台は tt/<時刻>_az<方位>_claws.png）で、爪の縁が暗い色（縁の線・藍）で囲まれているかを数える。
  ・爪の画素：主役波の印の画像（diag/*_hero_claws0.png と *_hero_claws1.png。アルファ 128 が主役波）で、爪なしでは主役波、爪ありでは主役波でない画素
    （爪が主役波を隠す画素。pl29_after_measure.py と同じ取り方）。連結成分 ≥ 40 px を爪の片とする。
  ・縁の画素：片の外側 1 画素の輪。縁の画素の 2 画素以内（5×5）に暗い画素（相対輝度 < 0.30：縁の線・藍濃・藍中）があれば「分かれる」。
  ・片の分かれる割合：縁の画素のうち分かれる割合。0.6 以上の片を「読める」とする（進行役が決めた目安。記録のみ）。
出力：<out>/claw_sep.json。使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_claw_sep.py --render <PL29Render の出力> --name <名> --out <dir>
"""
import argparse
import glob
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TIMES = ["t060", "t090", "t105", "t120"]
MINPX, DARK, READ = 40, 0.30, 0.6


def hero(p):
    a = np.array(Image.open(p).convert("RGBA"))[..., 3].astype(int)
    return np.abs(a - 128) <= 2


def lum(p):
    c = np.array(Image.open(p).convert("RGB")).astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def count(colour, h0, h1):
    claw = h0 & ~h1
    lab, n = ndi.label(claw)
    if n == 0:
        return {"pieces": 0, "readable": 0, "clawPx": 0, "sepFracMedian": None}
    sizes = ndi.sum(claw, lab, range(1, n + 1))
    dark = lum(colour) < DARK
    darkN = ndi.maximum_filter(dark.astype(np.uint8), size=5) > 0
    fr = []
    for k in range(1, n + 1):
        if sizes[k - 1] < MINPX:
            continue
        m = lab == k
        ring = ndi.binary_dilation(m) & ~m
        if ring.sum() == 0:
            continue
        fr.append(float(darkN[ring].mean()))
    fr = np.array(fr)
    return {"pieces": int(len(fr)), "readable": int((fr >= READ).sum()), "clawPx": int(claw.sum()),
            "sepFracMedian": round(float(np.median(fr)), 3) if len(fr) else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    R = a.render
    res = {"schema": "GreatWave.Polish29.claw_sep/1", "noteJa": __doc__.strip().split("\n")[0], "render": R.replace("\\", "/"), "name": a.name,
           "thresholds": {"minPiecePx": MINPX, "darkRelLum": DARK, "readableSepFrac": READ}, "views": {}, "turntable": {}}
    for v in VIEWS:
        for t in TIMES:
            c = os.path.join(R, "views", "%s_%s_asis.png" % (v, t))
            h0 = os.path.join(R, "diag", "%s_%s_hero_claws0.png" % (v, t))
            h1 = os.path.join(R, "diag", "%s_%s_hero_claws1.png" % (v, t))
            if os.path.exists(c) and os.path.exists(h0) and os.path.exists(h1):
                res["views"]["%s_%s" % (v, t)] = count(c, hero(h0), hero(h1))
    for c in sorted(glob.glob(os.path.join(R, "tt", "*_claws.png"))):
        b = os.path.basename(c).replace("_claws.png", "")
        h0 = os.path.join(R, "diag", "tt_%s_hero_claws0.png" % b)
        h1 = os.path.join(R, "diag", "tt_%s_hero_claws1.png" % b)
        if os.path.exists(h0) and os.path.exists(h1):
            res["turntable"][b] = count(c, hero(h0), hero(h1))

    def agg(d, keys):
        p = sum(d[k]["pieces"] for k in keys); r = sum(d[k]["readable"] for k in keys)
        return {"pieces": p, "readable": r, "readableFrac": round(r / p, 3) if p else None, "clawPx": sum(d[k]["clawPx"] for k in keys)}
    res["byView"] = {v: agg(res["views"], [k for k in res["views"] if k.startswith(v + "_t")]) for v in VIEWS}
    res["byView"]["turntable"] = agg(res["turntable"], list(res["turntable"].keys()))
    res["t120"] = {v: res["views"].get(v + "_t120") for v in VIEWS}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "claw_sep_%s.json" % a.name), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res["byView"], ensure_ascii=False))


if __name__ == "__main__":
    main()
