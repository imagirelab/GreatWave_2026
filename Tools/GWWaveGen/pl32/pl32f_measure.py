# -*- coding: utf-8 -*-
"""仕上げ32 修正の回 1：審査の指摘の所を、描いた画像（Unity の PC オフスクリーン描画）で数える（numpy・OpenCV）。

1. b区域の帯の中の白い地の上の暗い線（作る部の pl32_bregion_lines.json と同じ読み：b区域の候補の範囲（pl32_bregion_candidates.json の zone_ref を
   表示の px へ）の中で、灰の明るさ < 110 かつ 31 px の中央値 > 170 の画素と、6 px 以上の連結成分）。原画・前（仕上げ31）・作る部・修正の回 1。
2. b区域の帯の中の水色の版の割合（白い地の上の水色：表示の色が (203, 215, 206) から ΔRGB 30 以内）。原画の房の付け根の水色の雲の量の目安（記録のみ）。
3. 藍の上の爪（座席・座席から波の方向・左右の側面・後ろ 65°・真上・原画視点の t 6・9・10.5・12 s）：作品のままの画像と爪なしの画像で
   20 より色が違う画素のうち、爪なしの画像で藍（明るさ < 110）の所（藍の上に出た爪の画素）。審査で「藍の上の白い棒・くねった白」とされた
   座席の左端と座席から波の方向の左上は、その矩形の中も数える。
4. 原画視点 t 10.5 s の b区域の「閉じた輪」：作品のままと爪なしの差の画素の連結成分のうち、穴（中の白）を囲む輪の数（記録のみ）。
出力：Unity/Build/Polish/32/fix01/measure/pl32f_measure.json
"""
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/32"
RUNS = dict(before=B + "/r_before", build=B + "/r_after", fix01=B + "/fix01/r_fix01")
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
A_DISP, X_OFF = 0.416345, 156.66153
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TS = ["t060", "t090", "t105", "t120"]
SPOTS = {"seat": (0, 520, 700, 1080), "seat_toward_wave": (0, 0, 800, 400)}


def r2d(q):
    q = np.asarray(q, np.float64)
    return np.stack([A_DISP * (q[..., 0] + 0.5) - 0.5 + X_OFF, A_DISP * (q[..., 1] + 0.5) - 0.5], -1)


def paint_disp():
    """原画を表示の px へ（pl32_figs.paint_disp と同じ写し方）。"""
    P = cv2.imread(PAINT)
    M = np.float32([[A_DISP, 0, 0.5 * A_DISP - 0.5 + X_OFF], [0, A_DISP, 0.5 * A_DISP - 0.5]])
    return cv2.warpAffine(P, M, (1920, 1080), flags=cv2.INTER_AREA, borderValue=(200, 200, 200))


def zone_mask():
    bc = json.load(open(B + "/list/pl32_bregion_candidates.json", encoding="utf-8"))
    M = np.zeros((1080, 1920), np.uint8)
    cv2.fillPoly(M, [np.round(r2d(np.asarray(bc["zone_ref"]))).astype(np.int32)], 1)
    return M.astype(bool)


def dark_lines(img, Z):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    med = cv2.medianBlur(g, 31)
    m = (g < 110) & (med > 170) & Z
    n, cc, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    keep = st[1:, 4] >= 6
    return dict(dark_line_px=int(st[1:, 4][keep].sum()), components=int(keep.sum()))


def mizuiro_frac(img, Z):
    c = np.array([206, 215, 203], np.float64)   # BGR
    d = np.abs(img.astype(np.float64) - c).max(2)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    light = Z & (g > 170)
    return round(float(((d < 30) & light).sum() / max(1, light.sum())), 4)


def claws_over_indigo(asis, free, box=None):
    diff = np.abs(asis.astype(int) - free.astype(int)).sum(2) > 20
    indigo = cv2.cvtColor(free, cv2.COLOR_BGR2GRAY) < 110
    m = diff & indigo
    if box:
        x0, y0, x1, y1 = box
        sub = np.zeros_like(m); sub[y0:y1, x0:x1] = True
        m = m & sub
    n, cc, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    big = st[1:, 4]
    return dict(px=int(m.sum()), components_ge20=int((big >= 20).sum()), largest=int(big.max()) if len(big) else 0)


def closed_rings(asis, free, Z):
    diff = (np.abs(asis.astype(int) - free.astype(int)).sum(2) > 20) & Z
    g = cv2.cvtColor(asis, cv2.COLOR_BGR2GRAY)
    dark = diff & (g < 130)
    n, cc, st, _ = cv2.connectedComponentsWithStats(dark.astype(np.uint8), connectivity=8)
    rings = 0
    for k in range(1, n):
        if st[k, 4] < 15:
            continue
        x, y, w, h = st[k, :4]
        sub = (cc[y:y + h, x:x + w] == k).astype(np.uint8)
        inv = 1 - sub
        n2, cc2, st2, _ = cv2.connectedComponentsWithStats(np.pad(inv, 1, constant_values=1), connectivity=4)
        if n2 > 2:   # 外の背景のほかに、輪の中の閉じた所がある
            rings += 1
    return rings


def main():
    Z = zone_mask()
    out = dict(rule_ja=__doc__)
    P = paint_disp()
    bl = dict(painting=dark_lines(P, Z))
    miz = dict(painting=mizuiro_frac(P, Z))
    for k, d in RUNS.items():
        a = cv2.imread(d + "/views/painting_t120_asis.png")
        bl[k] = dark_lines(a, Z)
        miz[k] = mizuiro_frac(a, Z)
        f = cv2.imread(d + "/views/painting_t120_clawfree.png")
        bl[k + "_clawfree"] = dark_lines(f, Z)
    out["bregion_lines_tstar"] = bl
    out["bregion_mizuiro_fraction_tstar"] = miz
    ov = {}
    for k, d in RUNS.items():
        ov[k] = {}
        for v in VIEWS:
            for t in TS:
                a = cv2.imread(d + "/views/%s_%s_asis.png" % (v, t)); f = cv2.imread(d + "/views/%s_%s_clawfree.png" % (v, t))
                if a is None or f is None:
                    continue
                ov[k]["%s_%s" % (v, t)] = claws_over_indigo(a, f)
                if v in SPOTS and t == "t120":
                    ov[k]["%s_%s_spot" % (v, t)] = claws_over_indigo(a, f, SPOTS[v])
    out["claws_over_indigo"] = ov
    rings = {}
    for k, d in RUNS.items():
        for t in ("t105", "t120"):
            a = cv2.imread(d + "/views/painting_%s_asis.png" % t); f = cv2.imread(d + "/views/painting_%s_clawfree.png" % t)
            rings["%s_%s" % (k, t)] = closed_rings(a, f, Z)
    out["bregion_closed_rings"] = rings
    os.makedirs(B + "/fix01/measure", exist_ok=True)
    json.dump(out, open(B + "/fix01/measure/pl32f_measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "rule_ja" and k != "claws_over_indigo"}, ensure_ascii=False))
    for k in RUNS:
        tot = sum(v["px"] for kk, v in ov[k].items() if not kk.endswith("_spot") and not kk.startswith("painting"))
        print(k, "over-indigo px (non-painting views)", tot, {kk: v for kk, v in ov[k].items() if kk.endswith("_spot")})


if __name__ == "__main__":
    main()
