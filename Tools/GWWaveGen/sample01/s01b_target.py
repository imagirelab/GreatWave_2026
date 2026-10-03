# -*- coding: utf-8 -*-
"""美術の見本01 B：原画の主役波の面の「舌」の並び（藍濃の舌と藍中の線）を、原画の色区（表示の画素 1920×1080）から読む。
読むのは画像の上の形の並び（線の中心の点列・面の範囲）だけで、色は面へ写さない。見本の設計（面の座標の上の位相の場）の目的関数の比べる相手にする。
出力（work/）：target_face.png（面の範囲）、target_mid.png（藍中）、target_skel.npz（藍中の線の中心の成分ごとの画素）、target_view.png（点検の図）"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image
from skimage.morphology import skeletonize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s01b_common as S

WORK = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/work/"


def main():
    lab = np.array(Image.open(S.LABELS))
    dark = lab == 4
    mid = lab == 3
    ind = dark | mid
    # 面の範囲：藍（濃・中）を閉じて穴（白い点・線）を埋める
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    face = cv2.morphologyEx(ind.astype(np.uint8), cv2.MORPH_CLOSE, k) > 0
    ff = face.astype(np.uint8).copy()
    h, w = ff.shape
    mask = np.zeros((h + 2, w + 2), np.uint8)
    inv = (1 - ff).astype(np.uint8)
    cv2.floodFill(inv, mask, (0, 0), 0)
    face = face | (inv > 0)
    # 小さな島を除く
    n, cc, st, _ = cv2.connectedComponentsWithStats(face.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] > 3000
    face = keep[cc]
    # 藍中の線：面の中の藍中を少し閉じてから細線化
    m2 = cv2.morphologyEx((mid & face).astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))) > 0
    # 藍中の中の小さな穴（白い点・線）を埋める（細線化の輪を避ける）
    from scipy.ndimage import binary_fill_holes
    holes = binary_fill_holes(m2) & ~m2
    nh, ch, sh, _ = cv2.connectedComponentsWithStats(holes.astype(np.uint8), 8)
    small = np.zeros(nh, bool)
    small[1:] = sh[1:, cv2.CC_STAT_AREA] < 400
    m2 = m2 | small[ch]
    sk = skeletonize(m2)
    # 短い枝を刈る（端点から 12 画素以内で分岐に届く枝）
    for _ in range(12):
        nb = cv2.filter2D(sk.astype(np.uint8), -1, np.ones((3, 3), np.float32)) - sk
        ends = sk & (nb == 1)
        if not ends.any():
            break
        sk = sk & ~ends
    # 線の太さ（距離変換の 2 倍）
    dt = cv2.distanceTransform(m2.astype(np.uint8), cv2.DIST_L2, 5)
    n2, cc2, st2, _ = cv2.connectedComponentsWithStats(sk.astype(np.uint8), 8)
    comps = []
    for i in range(1, n2):
        if st2[i, cv2.CC_STAT_AREA] < 25:
            continue
        ys, xs = np.nonzero(cc2 == i)
        comps.append(dict(x=xs.astype(np.int32), y=ys.astype(np.int32), width=(2 * dt[ys, xs]).astype(np.float32)))
    np.savez_compressed(WORK + "target_skel.npz", n=len(comps),
                        **{f"x{i}": c["x"] for i, c in enumerate(comps)},
                        **{f"y{i}": c["y"] for i, c in enumerate(comps)},
                        **{f"w{i}": c["width"] for i, c in enumerate(comps)})
    Image.fromarray((face * 255).astype(np.uint8)).save(WORK + "target_face.png")
    Image.fromarray((m2 * 255).astype(np.uint8)).save(WORK + "target_mid.png")
    Image.fromarray((dark & face).astype(np.uint8) * 255).save(WORK + "target_dark.png")
    img = np.zeros((h, w, 3), np.uint8) + 235
    img[face] = (34, 63, 96)
    img[m2] = (41, 105, 148)
    rng = np.random.default_rng(3)
    for c in comps:
        col = rng.integers(120, 255, 3)
        img[c["y"], c["x"]] = col
    Image.fromarray(img).save(WORK + "target_view.png")
    stats = dict(face_px=int(face.sum()), mid_px=int(m2.sum()), dark_px=int((dark & face).sum()), skeleton_components=len(comps),
                 mid_width_px_median=float(np.median(np.concatenate([c["width"] for c in comps]))))
    json.dump(stats, open(WORK + "target_stats.json", "w"), indent=1)
    print(stats)


if __name__ == "__main__":
    main()
