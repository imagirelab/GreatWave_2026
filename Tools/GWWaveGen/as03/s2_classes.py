# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S2：原画 DP130155 の左の範囲（x 0..2450、y 0..2594 の画素）を、番号23 の 5 色の Lloyd 中心
（白＝紙の地・水色・墨版の縁 mix・藍中・藍濃）と空（番号23 の sky_claws の被覆）に分ける（原画の画素の細かさ）。
測るためだけ（Q28：面へは写さない）。出力（Git 対象外）：Unity/Build/Polish/sample03/study/tmp/s2_classes.npz と下見の図。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s2_classes.py
"""
import json

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
PAL = REPO + "/Tools/PaintingTruth/targets/palette.json"
SKY = REPO + "/Tools/PaintingTruth/targets/masks/sky_claws_cov.png"
OUT = REPO + "/Unity/Build/Polish/sample03/study/tmp/s2_classes.npz"
QW, QH = 2450, 2594
A = 0.4163454124903624
OFFX = 156.66152659984573
NAMES = ["sky", "white", "mizuiro", "mix", "ai_mid", "ai_dark"]


def main():
    im = cv2.imdecode(np.fromfile(PAINT, np.uint8), cv2.IMREAD_COLOR)[:QH, :QW]
    lab = cv2.cvtColor(im.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)
    pal = json.load(open(PAL, encoding="utf-8"))["classes_lloyd_centers_lab"]
    cen = np.array([pal[k] for k in ["white", "mizuiro", "mix", "ai_mid", "ai_dark"]], np.float32)
    best = np.full((QH, QW), np.inf, np.float32)
    lab_cls = np.zeros((QH, QW), np.uint8)
    for k in range(len(cen)):                                   # 1..5（メモリを抑えるため 1 色ずつ）
        dk = ((lab - cen[k]) ** 2).sum(-1)
        m = dk < best
        best[m] = dk[m]
        lab_cls[m] = k + 1
    del best
    # 空：表示の被覆（16bit）を原画の画素へ（表示の画素 x_d = A(x+0.5) − 0.5 + OFFX）
    cov = cv2.imread(SKY, cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0
    xs = A * (np.arange(QW) + 0.5) - 0.5 + OFFX
    ys = A * (np.arange(QH) + 0.5) - 0.5
    mx, my = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32))
    skyc = cv2.remap(cov, mx, my, cv2.INTER_LINEAR)
    sky = skyc > 0.5
    cls = lab_cls.copy()
    # 空の被覆の中でも、はっきり藍・水色の画素（爪の縁の線など）は波の色のまま。紙の地の色だけ空にする
    cls[sky & (lab_cls == 1)] = 0
    cls[sky & (lab[..., 0] > 70) & (lab[..., 2] > 12)] = 0
    np.savez_compressed(OUT, cls=cls, sky=sky, L=lab[..., 0].astype(np.float16))
    vis = np.zeros((QH, QW, 3), np.uint8)
    col = {0: (200, 225, 245), 1: (255, 255, 255), 2: (205, 215, 190), 3: (90, 70, 60), 4: (150, 100, 40), 5: (90, 50, 25)}
    for k, c in col.items():
        vis[cls == k] = c
    cv2.imwrite(REPO + "/Unity/Build/Polish/sample03/study/tmp/s2_classes_preview.png", cv2.resize(vis, (QW // 2, QH // 2), interpolation=cv2.INTER_NEAREST))
    cnt = {NAMES[k]: int((cls == k).sum()) for k in range(6)}
    print(cnt)


if __name__ == "__main__":
    main()
