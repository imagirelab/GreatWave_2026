# -*- coding: utf-8 -*-
"""美術の見本06 の直しの回：Unity の描画（爪なし）で、細い白の切れ端（白・水色の塊で、厚さが薄く細長い物）を数える（読むだけ）。
批評の直しの項目 4「横から見た白い棒・旗」の数。回り台 12 方位（爪なし）と 7 視点（爪なし）で、名前ごとに数を並べる。
白 = R ≥ 235・G ≥ 228・B ≥ 205（空のクリーム色 B 192 は入らない）、水色 = R 175〜215・G 198〜222・B 188〜215。8 連結の塊のうち
面積 ≥ 80 画素で、厚さ（塊の中の境からの距離の最大の 2 倍）≤ 8 画素、かつ 面積 / 厚さ² ≥ 6 の物を「細い切れ端」とする（1920×1080 の画素）。
画素の物差しなので、作りどうしの比べにだけ使う（m の幅ではない）。
使い方：py -3.10 -B Tools/GWWaveGen/as06/fix6_slivers.py <出力.json> 名前=描画のフォルダー [名前=描画のフォルダー ...]
"""
import json
import sys

import cv2
import numpy as np

VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
AZ = list(range(0, 360, 30))


def pale(im):
    r, g, b = im[..., 2].astype(int), im[..., 1].astype(int), im[..., 0].astype(int)
    w = (r >= 235) & (g >= 228) & (b >= 205)
    c = (r >= 175) & (r <= 215) & (g >= 198) & (g <= 222) & (b >= 188) & (b <= 215)
    return (w | c).astype(np.uint8)


def thin_pieces(path):
    im = cv2.imread(path)
    m = pale(im)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    out = []
    for i in range(1, n):
        a = int(st[i, 4])
        if a < 80:
            continue
        th = 2.0 * float(dt[lab == i].max())
        if th <= 8.0 and a / max(th * th, 1e-6) >= 6.0:
            out.append({"xy": [int(cen[i][0]), int(cen[i][1])], "area_px": a, "thick_px": round(th, 1)})
    return out


def main():
    outp = sys.argv[1]
    runs = dict(a.split("=", 1) for a in sys.argv[2:])
    res = {"tool": "Tools/GWWaveGen/as06/fix6_slivers.py", "rule_ja": __doc__.strip().split("\n")[3], "runs": {}}
    for nm, rd in runs.items():
        per = {}
        for az in AZ:
            per["tt%03d" % az] = thin_pieces(rd + "/tt/t120_az%03d_noclaws.png" % az)
        for v in VIEWS:
            per[v] = thin_pieces(rd + "/views/%s_t120_clawfree.png" % v)
        res["runs"][nm] = {"render": rd, "total": int(sum(len(v) for v in per.values())), "per_image": {k: len(v) for k, v in per.items()}, "pieces": per}
        print(nm, res["runs"][nm]["total"], res["runs"][nm]["per_image"])
    json.dump(res, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
