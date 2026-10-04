# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4（Q32、S9）：原画の左端の小さな青い波（④）の色の帯を、原画の画素で測る（numpy・OpenCV）。

原画（DP130155、3859×2594）の列 x 0〜360 ごとに、輪郭（区間 78 の真値）から楔の下の縁までの画素を、palette.json の Lab の中心の
最も近い色（白・水色・藍中・藍濃）に分け、頂の水色の帯・下の淡い筋・白い点の位置（原画の y）を数える。
数は波の頂点の属性（白の印 whiteSD の帯の境）を決める手がかりにだけ使う。原画の色を面へ写さない（Q28）。
出力：Unity/Build/Polish/sample04/wave4/meas/w4_paint_bands.json（Git 対象外）。
"""
import json
import sys

import cv2
import numpy as np

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04")
import s4_common as S  # noqa: E402

OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/meas/w4_paint_bands.json"
PAL = "G:/Unity/GreatWave_2026_Fresh/Tools/PaintingTruth/targets/palette.json"


def main():
    pal = json.load(open(PAL, encoding="utf-8"))
    cen = pal["classes_lloyd_centers_lab"]
    names = ["white", "mizuiro", "ai_mid", "ai_dark"]
    C = np.array([cen[n] for n in names], np.float64)
    im = cv2.imread(S.PAINT, cv2.IMREAD_COLOR)
    crop = im[780:1160, 0:420]
    crop = cv2.GaussianBlur(crop, (5, 5), 1.2)
    lab = cv2.cvtColor(crop.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64)
    d = ((lab[:, None, :] - C[None]) ** 2).sum(-1)
    cls = np.argmin(d, 1).reshape(crop.shape[:2])
    seg = S.outline_segments()["78"]
    M = json.load(open(S.OUT + "/s4_map.json", encoding="utf-8"))
    wl = {e["x_ref"]: e.get("wedge_lower_edge_y_ref_smooth") for e in M["region4"]["columns"]}
    cols = []
    for x in range(0, 364, 4):
        k = int(np.argmin(np.abs(seg[:, 0] - x)))
        yo = float(seg[k, 1]) if abs(seg[k, 0] - x) < 6 else None
        ylo = wl.get(x)
        if yo is None:
            yo = float(np.interp(x, seg[:, 0], seg[:, 1]))
        if ylo is None:
            cols.append({"x_ref": x, "outline_y": round(yo, 1)})
            continue
        y0, y1 = int(round(yo)) + 4, int(round(ylo)) - 2
        col = cls[y0 - 780:y1 - 780, x if x < 420 else 419]
        ys = np.arange(y0, y1)
        runs = []
        if len(col):
            s0 = 0
            for i in range(1, len(col) + 1):
                if i == len(col) or col[i] != col[s0]:
                    runs.append((names[col[s0]], int(ys[s0]), int(ys[i - 1]) + 1))
                    s0 = i
        # 頂の水色の帯：輪郭のすぐ下で最初に続く水色（3 px より短い切れ目は続きとみなす）
        miz = [r for r in runs if r[0] == "mizuiro" and r[2] - r[1] >= 3]
        top = None
        if miz and miz[0][1] - yo < 25:
            a0, a1 = miz[0][1], miz[0][2]
            for r in miz[1:]:
                if r[1] - a1 <= 4:
                    a1 = r[2]
            top = [a0, a1]
        low = None
        rest = [r for r in miz if top is None or r[1] > top[1] + 8]
        if rest:
            low = [rest[0][1], rest[0][2]]
        cols.append({"x_ref": x, "outline_y": round(yo, 1), "wedge_lower_y": ylo, "mizuiro_top": top, "mizuiro_low": low,
                     "white_px": int((col == 0).sum()), "runs": runs[:16]})
    # 楔の藍の中の白い点（白の画素のつながり。輪郭の 20 px 下〜楔の下の縁の 6 px 上、x 0〜360）
    wm = np.zeros(cls.shape, np.uint8)
    for x in range(0, 361):
        yo = float(np.interp(x, seg[:, 0], seg[:, 1]))
        k = min(wl.keys(), key=lambda q: abs(q - x))
        ylo = wl.get(k)
        if ylo is None:
            continue
        y0, y1 = int(yo + 20) - 780, int(ylo - 6) - 780
        if y1 > y0:
            wm[max(y0, 0):y1, x] = (cls[max(y0, 0):y1, x] <= 1).astype(np.uint8)   # 白か水色（ぼかしで点の縁が水色に寄る）
    n, lab, st, cen = cv2.connectedComponentsWithStats(wm, 8)
    chips = []
    for i in range(1, n):
        a = int(st[i, cv2.CC_STAT_AREA])
        bw, bh = int(st[i, cv2.CC_STAT_WIDTH]), int(st[i, cv2.CC_STAT_HEIGHT])
        if 25 <= a <= 600 and max(bw, bh) <= 2.6 * min(bw, bh):   # 細長い物（淡い筋）は点ではない
            chips.append({"x_ref": round(float(cen[i, 0]), 1), "y_ref": round(float(cen[i, 1]) + 780, 1), "area_px": a,
                          "r_px": round(float(np.sqrt(a / np.pi)), 2)})
    print("chips", chips)
    res = {"schema": "GreatWave.AS04.w4_paint_bands/1", "chips": chips, "source": S.PAINT, "source_sha256": S.sha(S.PAINT),
           "note_ja": "原画の左端の青い楔の列ごとの色の帯（原画の画素の y）。白い点は藍の中の白の画素数。原画の色は面へ写さない。", "columns": cols}
    S.jdump(OUT, res)
    for e in cols[::5]:
        print(e["x_ref"], e["outline_y"], e.get("wedge_lower_y"), e.get("mizuiro_top"), e.get("mizuiro_low"), e.get("white_px"))


if __name__ == "__main__":
    main()
