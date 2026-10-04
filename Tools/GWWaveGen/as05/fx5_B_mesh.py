# -*- coding: utf-8 -*-
"""美術の見本05 やり方 B：主役波 K*′ AS05B の t* の、材質（AS04F Flat Smooth、値の表は as05 の AS05 版）が読む頂点の属性つきの静止のメッシュを作る。
約束は Unity/Build/Polish/sample04/mat/README.md（surf_relief --flat の出力。q・gq・Lq・λ・whiteOn もここで出る）。

白の印 whiteSD（m、+ が白）の作り（形を作り直したので、白の区域も作り直す。mat/README.md の 3 節）：
  土台は見本04 AS04F の白の印（fix1/shape/mesh/white_mask_as04f_f32.bin）の符号（白・藍の区域）。次を替えてから、境からの距離を新しい面の上で測り直す。
  1. 段の行（作り直した行 c < −8.4 m）：層ごとの白は自分の頂の帯だけ（strategies.md の 3 節「層ごとの白は自分の頂の帯だけ」・Q33 の三つの層を分ける）。
     背の頂の白（列 ≤ col_back_white）は見本04 のまま。踏み面・溝（列 col_back_white+1 .. 縁の頂の手前）は藍。
     段の縁の頂の帯（溝の底の列 〜 唇の先を回って唇の下の始まりの列 under_white_col）は白。その先の唇の下・内の面は藍。
     （第 1 版は縁の頂の 10 列前から唇の先までの細い白にしたが、白の前の縁の水色（幅 0.25〜1.1 m・境から 0.3 m 奥）が細い白のほとんどを水色にし、
     原画視点で水色の帯に白い縁と藍の穴が並ぶ乱れた模様に見えたので、白の帯を面の上で約 6 m に広げた）
     段のない行（② と ③ の間の湾・③ の左）は、背の頂の白（列 ≤ nose_white_col）だけで、鼻と唇の下は藍（第 2 版。鼻を白にした版は、② と ③ の白が湾の鼻の白でつながり、
     原画視点で白の輪に囲まれた藍の穴が並んだ）。
  2. T6（Q33 の切り出し、原画視点の唇の下の内の縁）：主の唇の右の端の行（c 3.5〜9.5 m、両端 1 m でなめらかに）の、唇の先より下（列 > 201）の白を藍にする。
     切り出しの白い帯は、この行・列（唇の下の面を縁から見た所）だった（見本04 の描画と numpy の id の画像で確かめた。行 c 5.4〜8.0、列 206〜230）。
     第 2 版：切り出しの下の半分（表示の y 390〜695）の白い帯は、主の唇の右の端の行 c 9〜13.5 m の唇の先の手前（列 190〜225）だった
     （見本05 B の描画 B2 と静止のメッシュの行・列で確かめた）。その行は列 186 より先を藍にした。
     行・列の範囲（格子の場所）で決めるので、原画のカメラの投影は使わない（G1）。
  3. 低い行（頂 < 0.22 H0）は白にしない（見本04 と同じ）。
使い方：py -3.10 -B Tools/GWWaveGen/as05/fx5_B_mesh.py <根> <候補の名前（例 kstarAS05B_a45）>
直しの回 fix1：shapeB_mesh.py（変えない）の写し。段の白の帯を付ける行の段の重みの下限を 0.3 から STEP_S（既定 0.75、環境変数 FX5_STEP_S）にした。
段の窓の外の出入りを広げた（fx5_B_build.py）ので、0.3 のままでは ② と ③ の白の帯が湾の行まで広がり、原画視点で ② ③ の白がつながったため。
"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as04")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as03")
import shape_mesh as M  # noqa: E402
import surf_common as SC  # noqa: E402
import surf_relief as R  # noqa: E402

STEP_S = float(os.environ.get("FX5_STEP_S", "0.75"))   # 直しの回 fix1：段の白の帯を付ける行の段の重みの下限（元は 0.3）
RIM3 = int(os.environ.get("FX5_RIM3", "-1"))   # 直しの回 fix1：③ の段の白の始まりを縁の頂の何列後ろにするか（−1 = 元のとおり溝の底から）
STEP_S3 = float(os.environ.get("FX5_STEP_S3", str(STEP_S)))   # 直しの回 fix1：③ の段だけ別の下限（③ の唇の左の端の白の切れ端をなくすため）
WM_04F = REPO + "/Unity/Build/Polish/sample04/fix1/shape/mesh/white_mask_as04f_f32.bin"
ROWS_04F = REPO + "/Unity/Build/Polish/sample04/fix1/shape/final/cand/kstarAS04F_a45_rows.npz"
RULE = {"col_back_white": 112, "rim_back": 10, "tip_col": 205, "nose_white_col": int(os.environ.get("FX5_NOSE_WHITE", "118")), "under_white_col": int(os.environ.get("S5B_UNDER_WHITE", "232")),
        "bay_c": [-16.6, -13.2], "bay_white_col": int(os.environ.get("S5B_BAY_WHITE", "118")), "t6_windows": [[[3.5, 9.5], 201], [[8.5, 13.5], 186]], "t6_blend_m": 1.0}


def main():
    SH = sys.argv[1] if os.path.isabs(sys.argv[1]) else REPO + "/" + sys.argv[1]
    CAND = SH + "/final/cand/" + sys.argv[2]
    NAME = "hero_smooth_as05b"
    nr, nc = 240, 400
    import ds33_common as U  # noqa: F401
    SC.HERO_PKG = SH + "/hero_pkg_AS05B"
    Pb = SC.load_hero_world()
    sd_src = np.fromfile(WM_04F, np.float32).astype(np.float64).reshape(nr, nc)
    z = np.load(CAND + "_rows.npz"); c = z["c"].astype(np.float64); A = z["A"].astype(np.float64); Y = z["Y"].astype(np.float64)
    z0 = np.load(ROWS_04F); A0 = z0["A"]; Y0 = z0["Y"]
    log = json.load(open(CAND + "_build_log.json", encoding="utf-8"))["log"]
    s_row = np.array(log["s"]); lay = np.array(log["layer"])
    white = sd_src > 0
    changed = (np.abs(A - A0).max(1) + np.abs(Y - Y0).max(1)) > 1e-4
    J = np.arange(nc)
    per_row = []
    for i in np.nonzero(changed)[0]:
        jt = RULE["tip_col"]
        w = white[i].copy()
        w[RULE["col_back_white"] + 1:] = False
        if lay[i] in (2, 3) and s_row[i] >= (STEP_S3 if lay[i] == 3 else STEP_S):
            jr = 130 + int(np.argmax(Y[i, 130:201]))
            jg = RULE["col_back_white"] + 1 + int(np.argmin(Y[i, RULE["col_back_white"] + 1:jr + 1]))   # 溝の底の列
            j0w = max(jg, RULE["col_back_white"] + 1)
            if lay[i] == 3 and RIM3 >= 0:
                j0w = max(j0w, jr - RIM3)          # 直しの回 fix1：③ の段の白は縁の頂の RIM3 列後ろから（溝の床の白が原画視点で縁の線の後ろに島として残った）
            w[j0w:RULE["under_white_col"] + 1] = True
            per_row.append([round(float(c[i]), 2), int(lay[i]), int(jg), int(jr)])
        else:
            bay = RULE["bay_c"][0] <= c[i] <= RULE["bay_c"][1]
            w[RULE["col_back_white"] + 1:(RULE["bay_white_col"] if bay else RULE["nose_white_col"]) + 1] = True
            per_row.append([round(float(c[i]), 2), 0, None])
        white[i] = w
    # T6：主の唇の右の端の行の唇の下（と、c 8.5〜13.5 m では唇の先の手前から）を藍に
    t6_rows = []
    for (t0, t1), col in RULE["t6_windows"]:
        bl = RULE["t6_blend_m"]
        wt = np.clip(np.minimum((c - (t0 - bl)) / bl, ((t1 + bl) - c) / bl), 0, 1)
        for i in np.nonzero(wt > 0)[0]:
            jcut = int(round(col + (1 - wt[i]) * 40))      # 端では切る列を後ろへ（なめらかに元へ）
            n = int(white[i, jcut + 1:].sum())
            white[i, jcut + 1:] = False
            t6_rows.append([round(float(c[i]), 2), jcut, n])
    sd_sign = np.where(white, np.maximum(np.abs(sd_src), 0.01), -np.maximum(np.abs(sd_src), 0.01))
    sd_new = M.resigned_distance(Pb, sd_sign)
    Hrow = Pb[:, 18:201, 1].max(1)
    cap = (Hrow - M.LOW_H0 * M.H0) * M.LOW_K
    sd_new = np.minimum(sd_new, cap[:, None])
    MO = os.environ.get("S5B_MESH_OUT", SH)          # 材質の試し（白の範囲の変種）を別の置き場へ書く時
    os.makedirs(MO + "/mesh", exist_ok=True)
    wm = MO + "/mesh/white_mask_as05b_f32.bin"
    sd_new.astype(np.float32).tofile(wm)
    wrep = {"source_mask": WM_04F, "source_sha256": SC.sha(WM_04F), "out": wm, "out_sha256": SC.sha(wm), "rule": RULE, "step_s_min_fix1": STEP_S, "step3_s_min_fix1": STEP_S3, "step3_white_from_rim_cols_fix1": RIM3,
            "changed_rows": int(changed.sum()), "step_rows_rim_col": per_row, "t6_rows_cut": t6_rows,
            "white_vertices_source_new": [int((sd_src > 0).sum()), int((sd_new > 0).sum())],
            "note_ja": "段の行は層ごとに自分の頂の帯だけ白、T6 の行は唇の下を藍。境からの距離を AS05B の面の上で測り直した。"}
    SC.GWB = CAND + ".gwb"
    SC.META = CAND + "_meta.json"
    SC.ROWS = CAND + "_rows.npz"
    SC.ATTR = SH + "/attr/a/s01a_hero_attr_v2_f32.bin"
    SC.OUT = MO
    R.S = SC
    sys.argv = ["surf_relief.py", "--name", NAME, "--flat", "--white-mask", wm]
    R.main()
    rp = MO + "/mesh/" + NAME + "_report.json"
    rep = json.load(open(rp, encoding="utf-8"))
    rep["as05b_white_mask"] = wrep
    rep["as05b_inputs"] = {"hero_pkg": SC.HERO_PKG, "gwb": SC.GWB, "meta": SC.META, "rows": SC.ROWS, "attr": SC.ATTR}
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps({k: v for k, v in wrep.items() if k not in ("step_rows_rim_col", "t6_rows_cut")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
