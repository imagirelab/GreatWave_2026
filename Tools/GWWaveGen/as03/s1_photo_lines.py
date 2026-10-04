# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：彫刻の写真（一時の縮めた写し）から、面の淡い水色の線を数える（数だけ。画像は書かない）。
水色の画素（HSV：色相 95〜125、彩度 ≥ 90、明るさ ≥ 70）を、指定の高さの横の線の上で連なりとして数え、線の幅・間（藍の幅）・周期を画素で出す。
分かれ目（Y 字）は、水色の領域の骨格の 3 本以上の分岐点の数。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_photo_lines.py <画像> <x0> <x1> <y,y,y> [領域 x0,y0,x1,y1]
"""
import json
import sys

import cv2
import numpy as np


def main():
    img = cv2.imread(sys.argv[1])
    x0, x1 = int(sys.argv[2]), int(sys.argv[3])
    ys = [int(v) for v in sys.argv[4].split(",")]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    blue = (h >= 95) & (h <= 125) & (s >= 90) & (v >= 70)
    blue = cv2.morphologyEx(blue.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    out = {"image": sys.argv[1].split("/")[-1], "x_range": [x0, x1], "rows": {}}
    for y in ys:
        band = blue[max(y - 2, 0):y + 3, x0:x1].mean(0) > 0.5
        runs = []
        k = 0
        while k < len(band):
            if band[k]:
                j = k
                while j < len(band) and band[j]:
                    j += 1
                runs.append((k, j))
                k = j
            else:
                k += 1
        runs = [r for r in runs if r[1] - r[0] >= 3]
        w = [r[1] - r[0] for r in runs]
        cen = [(r[0] + r[1]) / 2 for r in runs]
        per = list(np.diff(cen)) if len(cen) > 1 else []
        gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
        out["rows"][str(y)] = {"n_lines": len(runs), "line_width_px_p50": float(np.median(w)) if w else None,
                               "period_px_p50": float(np.median(per)) if per else None,
                               "gap_indigo_px_p50": float(np.median(gaps)) if gaps else None,
                               "line_width_over_period": float(np.median(w) / np.median(per)) if per else None,
                               "span_px": float(cen[-1] - cen[0]) if len(cen) > 1 else None}
    if len(sys.argv) > 5:
        a0, b0, a1, b1 = [int(v) for v in sys.argv[5].split(",")]
        from skimage.morphology import skeletonize
        sk = skeletonize(blue[b0:b1, a0:a1])
        nb = cv2.filter2D(sk.astype(np.uint8), -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - sk
        junc = sk & (nb >= 3)
        n_j, _ = cv2.connectedComponents(cv2.dilate(junc.astype(np.uint8), np.ones((5, 5), np.uint8)))
        ends = sk & (nb == 1)
        n_e, _ = cv2.connectedComponents(cv2.dilate(ends.astype(np.uint8), np.ones((5, 5), np.uint8)))
        out["region"] = [a0, b0, a1, b1]
        out["blue_area_frac"] = float(blue[b0:b1, a0:a1].mean())
        out["skeleton_junctions"] = int(n_j - 1)
        out["skeleton_ends"] = int(n_e - 1)
        out["skeleton_len_px"] = int(sk.sum())
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
