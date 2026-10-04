# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：主役波 K*′ AS05A の t* の、材質（AS04F Flat Smooth、約束は Build/Polish/sample04/mat/README.md）が読む
頂点の属性つきの静止のメッシュを作る。見本04 の fx1_mesh.py（変えない）と同じ手順に、白の区域の作り直しを足した。
  1. 白の印は見本03 の v2 を頂点の番号で引き継ぎ、fx1 と同じ歯の列のならし・湾の床の白を当てる（① は見本04 と同じ見え方）。
  2. 形を作り直した行の白（README 3 節「形を作り直す時に白の区域も作り直すこと」）：
     ② の段（shapeA_hero の step2 の窓の重み ≥ W2）：列 104〜JW2 を白（背の頂の前の壁・溝・② の頂・唇の前の縁と唇の下の少し）、
       列 JW2+1〜300 を藍（唇の下の引っ込みの面・垂れの面＝ ② の藍の面）。
     左の肩（c < C23、唇を引っ込めた行）：列 104〜JWL を白（短い肩と鼻）、列 JWL+1〜379 を藍（鼻の下の巻きの面と前の面。③ の後ろ）。
  3. 境からの距離を新しい面の上で測り直し（shape_mesh.resigned_distance）、低い行は白にしない（shape_mesh の LOW_H0）。
  4. 見本03 の surf_relief.py（変えない）を --flat で呼ぶ（入力のパスだけ替える）。
直しの回 fix1（fx5_A_mesh.py）：shapeA_mesh.py（変えない）の写し。白の区域の決め方の 2. だけを次に替えた（批評の「① と ② が一枚の白い翼に
  つながる」「③ の白が左の白い翼に触れる」を直すため。B の段の行の決め方と同じ考え）。
     ② の段の芯（step2 の窓の重み ≥ W2_CORE）：列 104〜JW2 を白、JW2+1〜300 を藍（元と同じ）。
     作り直したほかの行（c −23.5〜−8.4 の、② の芯でない行：左の肩・② と ③ の間・② と ① の間）：背の頂の白（列 ≤ NOSE_WHITE、既定 124）だけ白、
     その前（列 NOSE_WHITE+1〜379）は藍。① の行（c > −8.4）は見本04 のまま。
  使い方：fx5_A_run.py から呼ぶ（置き場は shapeA_common の OUT を fix1/A へ替えてから読む）。
使い方（元）：py -3.10 -B Tools/GWWaveGen/as05/shapeA_mesh.py
出力（Git 対象外）：Unity/Build/Polish/sample05/shapeA/mesh/hero_smooth_as05a.bin・.json・_report.json、white_mask_as05a_f32.bin
"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as05", "Tools/GWWaveGen/as04", "Tools/GWWaveGen/as03"):
    sys.path.insert(0, REPO + "/" + _p)
import shapeA_common as C  # noqa: E402
import shapeA_hero as H  # noqa: E402
import shape_mesh as M  # noqa: E402
import fx1_mesh as FX  # noqa: E402
import surf_common as SC  # noqa: E402
import surf_relief as R  # noqa: E402

SH = C.OUT
NAME = "hero_smooth_as05a"
W2, JW2 = 0.05, 214    # ② の白は唇の下へ少し回す（列 214 まで。唇の下の白の縁に水色の帯が出る）
C23, JWL = -13.5, 204
W2_CORE, NOSE_WHITE = float(os.environ.get("FX5_W2_CORE", "0.6")), int(os.environ.get("FX5_A_NOSE_WHITE", "124"))      # 直しの回 fix1（124：背の頂の白を 118 より少し前まで。118 では原画視点で wave4 と layer3 の間に背の頂の白が 4 画素の島として覗いた）


def main():
    nr, nc = 240, 400
    import ds33_common as U  # noqa: F401
    SC.HERO_PKG = SH + "/hero_pkg_AS05A"
    Pb = SC.load_hero_world()
    sd_old = np.fromfile(M.WM_OLD, np.float32).astype(np.float64).reshape(nr, nc)
    rows = np.load(C.ROWS05A)
    c = rows["c"].astype(np.float64)
    from scipy.ndimage import gaussian_filter1d
    sd_src = sd_old.copy()
    jj = np.arange(nc)
    T = FX.TEETH
    wcol = np.clip((jj - T["col0"]) / max(T["col1"] - T["col0"], 1), 0, 1)
    wcol = wcol * wcol * (3 - 2 * wcol)
    sd_sm = gaussian_filter1d(sd_src, T["sigma_rows"], axis=0, mode="nearest")
    sd_src = sd_src + wcol[None, :] * (sd_sm - sd_src)
    for (c0, c1), (j0, j1) in FX.WHITE_WINDOWS:
        m = (c >= c0) & (c <= c1)
        sd_src[m, j0:j1] = np.maximum(np.abs(sd_src[m, j0:j1]), 0.01)
    # 形を作り直した行の白
    p2 = H.DESIGN["step2"]
    w2 = C.wwin(c, p2["full"], p2["blend"])
    rows2 = np.nonzero(w2 >= W2_CORE)[0]
    rowsL = np.nonzero((c >= -23.5) & (c <= -8.4) & (w2 < W2_CORE))[0]       # 直しの回 fix1：② の芯でない作り直しの行は背の頂の白だけ
    for rr, jw, jend in ((rows2, JW2, 300), (rowsL, NOSE_WHITE, 379)):
        blk = sd_src[rr, 104:jw + 1]
        sd_src[rr, 104:jw + 1] = np.maximum(np.abs(blk), 0.01)
        blk = sd_src[rr, jw + 1:jend + 1]
        sd_src[rr, jw + 1:jend + 1] = -np.maximum(np.abs(blk), 0.01)
    sd_new = M.resigned_distance(Pb, sd_src)
    Hrow = Pb[:, 18:201, 1].max(1)
    cap = (Hrow - M.LOW_H0 * M.H0) * M.LOW_K
    sd_new = np.minimum(sd_new, cap[:, None])
    os.makedirs(SH + "/mesh", exist_ok=True)
    wm = SH + "/mesh/white_mask_as05a_f32.bin"
    sd_new.astype(np.float32).tofile(wm)
    wrep = {"source_mask": M.WM_OLD, "source_sha256": SC.sha(M.WM_OLD), "out": wm, "out_sha256": SC.sha(wm),
            "fx1_teeth_and_white_windows": {"teeth": T, "white_windows": [[list(w), list(j)] for w, j in FX.WHITE_WINDOWS]},
            "step2_rows": [int(rows2.min()), int(rows2.max())] if len(rows2) else None, "step2_white_cols": [104, JW2], "step2_indigo_cols": [JW2 + 1, 300],
            "fix1_rule": {"step2_core_w_min": W2_CORE, "other_reshaped_rows_c": [-23.5, -8.4], "other_white_cols": [104, NOSE_WHITE], "other_indigo_cols": [NOSE_WHITE + 1, 379]},
            "white_vertices_source_new": [int((sd_old > 0).sum()), int((sd_new > 0).sum())],
            "note_ja": "白・藍の区域は見本03 の白の印 v2 を頂点の番号で引き継ぎ（fx1 の歯の列のならし・湾の床の白）、形を作り直した ② の段と左の肩の行だけ列の範囲で決め直し、境からの距離を AS05A の面の上で測り直した。"}
    cand = C.CAND
    SC.GWB = cand + ".gwb"
    SC.META = cand + "_meta.json"
    SC.ROWS = cand + "_rows.npz"
    SC.ATTR = SH + "/attr/a/s01a_hero_attr_v2_f32.bin"
    SC.OUT = SH
    R.S = SC
    sys.argv = ["surf_relief.py", "--name", NAME, "--flat", "--white-mask", wm]
    R.main()
    rp = SH + "/mesh/" + NAME + "_report.json"
    rep = json.load(open(rp, encoding="utf-8"))
    rep["as05a_white_mask"] = wrep
    rep["as05a_inputs"] = {"hero_pkg": SC.HERO_PKG, "gwb": SC.GWB, "meta": SC.META, "rows": SC.ROWS, "attr": SC.ATTR}
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(wrep, ensure_ascii=False))


if __name__ == "__main__":
    main()
