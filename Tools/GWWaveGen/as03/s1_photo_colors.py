# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：彫刻の写真（一時の縮めた写し）から色を数で取る（sRGB の値だけ。画像は書かない）。
類（白・淡い水色・藍・金・台の水色）を HSV のしきいで分け、類ごとに明るい所（明るさの上位 15%）・中（中央値の帯）・陰（下位 15%）の
sRGB の中央値と L*（CIE）を出す。鏡のような光の点（明るさ ≥ 245 かつ彩度 ≤ 35）は除き、その点の大きさ（つながりの等価の径の画素）を数える。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_photo_colors.py <画像> <x0,y0,x1,y1> [<類,...>]
"""
import json
import sys

import cv2
import numpy as np


def srgb_to_lab(rgb):
    a = np.asarray(rgb, np.float32).reshape(-1, 1, 3) / 255.0
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).reshape(-1, 3)
    return lab


def stats(pix):
    if len(pix) < 50:
        return None
    rgb = pix[:, ::-1].astype(np.float32)            # BGR -> RGB
    lab = srgb_to_lab(rgb)
    L = lab[:, 0]
    o = np.argsort(L)
    n = len(o)
    lo_, mid_, hi_ = o[:max(int(n * 0.15), 1)], o[int(n * 0.4):int(n * 0.6)], o[int(n * 0.85):]
    f = lambda idx: [int(round(float(np.median(rgb[idx, k])))) for k in range(3)]
    return {"n_px": int(n), "lit_srgb": f(hi_), "mid_srgb": f(mid_), "shadow_srgb": f(lo_),
            "L_lit": round(float(np.median(L[hi_])), 1), "L_mid": round(float(np.median(L[mid_])), 1), "L_shadow": round(float(np.median(L[lo_])), 1)}


def main():
    img = cv2.imread(sys.argv[1])
    x0, y0, x1, y1 = [int(v) for v in sys.argv[2].split(",")]
    img = img[y0:y1, x0:x1]
    want = sys.argv[3].split(",") if len(sys.argv) > 3 else ["white", "lightblue", "indigo", "gold", "base"]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    spec = (v >= 245) & (s <= 35)
    cls = {
        "white": (s <= 70) & (v >= 110) & ~spec,
        "lightblue": (h >= 98) & (h <= 122) & (s >= 110) & (v >= 85) & ~spec,
        "indigo": (h >= 100) & (h <= 135) & (s >= 70) & (v <= 80) & (v >= 8) & ~spec,
        "gold": (h >= 8) & (h <= 28) & (s >= 70) & (v >= 120) & ~spec,
        "base": (h >= 70) & (h <= 100) & (s >= 25) & (v >= 120) & ~spec,
    }
    out = {"image": sys.argv[1].split("/")[-1], "region": [x0, y0, x1, y1]}
    for k in want:
        m = cls[k]
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
        out[k] = stats(img[m])
        out[k + "_area_frac"] = round(float(m.mean()), 4)
    n, lab, st, cen = cv2.connectedComponentsWithStats(spec.astype(np.uint8))
    areas = st[1:, cv2.CC_STAT_AREA]
    areas = areas[areas >= 2]
    out["specular_spots"] = {"n": int(len(areas)), "eq_diam_px_p50": round(float(np.median(2 * np.sqrt(areas / np.pi))), 1) if len(areas) else None,
                             "eq_diam_px_p90": round(float(np.percentile(2 * np.sqrt(areas / np.pi), 90)), 1) if len(areas) else None,
                             "area_frac": round(float(spec.mean()), 5)}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
