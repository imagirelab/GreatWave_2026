# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：主役波 K*′ AS02C（見本02 の t* の形）の上で、参照の彫刻の比を当てはめるための大きさを測る（数だけ）。
H0（主の頂の高さ）・冠の縁の長さ L（頂の線の 3 次元の長さ。頂の高さ ≥ 0.4 H の行）・唇の線の長さ・面の幅 W（頂の高さ ≥ 0.5 H の c の幅）。
入力：Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz（Git 対象外）。出力：study/s1_hero_dims.json。
参照モデルの側の同じ定義の値は s1_crown2_numbers*.json（rim）から読む。
"""
import hashlib
import json
import os

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
ROWS = REPO + "/Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz"
OUT = REPO + "/Unity/Build/Polish/sample03/study/s1_hero_dims.json"
H0 = 20.752853190871733
J_TOP, J_TIP, J_FACEBOT = 90, 200, 379


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def smooth_on_c(c, x, win):
    out = np.empty_like(x)
    for i in range(len(c)):
        s = np.abs(c - c[i]) <= win / 2
        out[i] = x[s].mean()
    return out


def arclen(P):
    return float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)))


def main():
    z = np.load(ROWS)
    c, A, Y = z["c"], z["A"], z["Y"]
    jt = np.argmax(Y[:, :J_TIP], 1)
    Hc = Y[np.arange(len(Y)), jt]
    at = A[np.arange(len(A)), jt]
    res = {"source": os.path.relpath(ROWS, REPO).replace("\\", "/"), "source_sha256": sha(ROWS), "H0_m": H0,
           "H_max_m": float(Hc.max()), "c_at_H_max": float(c[int(np.argmax(Hc))]), "sea_y": 0.0}
    for frac in (0.4, 0.5):
        s = Hc >= frac * H0
        idx = np.nonzero(s)[0]
        # 最も長いつながった区間
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        r = max(runs, key=len)
        cc = c[r]
        ys = smooth_on_c(cc, Hc[r], 1.0)
        as_ = smooth_on_c(cc, at[r], 3.0)
        P = np.stack([as_, ys, cc], 1)
        tipA = smooth_on_c(cc, A[r, J_TIP], 1.0)
        tipY = smooth_on_c(cc, Y[r, J_TIP], 1.0)
        Pl = np.stack([tipA, tipY, cc], 1)
        res["rim_H_ge_%.1f" % frac] = {"c_range": [float(cc.min()), float(cc.max())], "dc_m": float(cc.max() - cc.min()),
                                      "rim_len_3d_m": arclen(P), "rim_len_cy_m": arclen(P[:, 1:]),
                                      "lip_tip_line_len_3d_m": arclen(Pl)}
    # 面（唇の先から面の底まで）の高さの範囲と、面がある行の c の幅（面が 0.25・0.5・0.75 H の高さを通る行）
    for frac in (0.25, 0.5, 0.75):
        y = frac * H0
        rows = []
        for i in range(len(c)):
            yy = Y[i, J_TIP:J_FACEBOT + 1]
            if yy.min() <= y <= yy.max():
                rows.append(c[i])
        if rows:
            res["face_rows_crossing_%.2fH" % frac] = {"c_min": float(min(rows)), "c_max": float(max(rows)), "W_m": float(max(rows) - min(rows))}
    # 唇の先の高さの分布
    s = Hc >= 0.4 * H0
    res["lip_tip_height_over_H0"] = {"p10": float(np.percentile(Y[s, J_TIP] / H0, 10)), "p50": float(np.percentile(Y[s, J_TIP] / H0, 50)),
                                     "p90": float(np.percentile(Y[s, J_TIP] / H0, 90))}
    res["lip_overhang_a_tip_minus_crest_m"] = {"p10": float(np.percentile(A[s, J_TIP] - at[s], 10)), "p50": float(np.percentile(A[s, J_TIP] - at[s], 50)),
                                               "p90": float(np.percentile(A[s, J_TIP] - at[s], 90))}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
