# -*- coding: utf-8 -*-
"""美術の見本04 の直しの回 1（fix1）：直した主役波 K*′ AS04F の t* の、材質が読む頂点の属性つきの静止のメッシュを作る。
shape_mesh.py（変えない）と同じ手順（白の印を見本03 の v2 から頂点の番号で引き継ぎ、境からの距離を新しい面で測り直し、surf_relief --flat）。
次だけを足した。
  白い刃の直し（批評の 2 番、S8 の黄色の線の左上）：①–② の湾の右の壁（主の唇 ① の左の端の壁と、その唇の下）は、原画視点で
  黄色の線のすぐ左上に白・水色の刃（Z の形の楔）として見えた。原画ではそこは巻きの内の藍の面なので、白の印をそこだけ藍にする：
    c −6.8〜−5.6 m の列 150 以上（湾の壁と唇の下）、c −5.6〜−3.8 m の列 200 以上（唇の下だけ）。第 1 版の c −6.8〜−4.6 は、c −5.5〜−4.6 の列 153〜181 で帯の座標 w が縮み（|∇w| 0.22 倍、1,076 三角形）G1 を落としたので狭めた。頂の白（列 < 150）と主の唇 ①（c > −3.8）の白は変えない。
使い方：py -3.10 -B Tools/GWWaveGen/as04/fx1_mesh.py <fix の根（例 Unity/Build/Polish/sample04/fix1/shape）> <候補の名前（例 kstarAS04F_a45）>
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

BLUE_WINDOWS = [w for w in (((-6.8, -5.6), 150), ((-5.6, -3.8), 200)) if os.environ.get("FX1_BLADE", "white") == "blue"]
# 第 3 版（既定、FX1_BLADE=white）：湾の床と壁の上（c −8.6〜−5.6 m、列 150〜199）を白にして、頂の白と一つの塊にする（囲まれた白い刃を作らない）。
# 藍にする案（FX1_BLADE=blue、第 1・2 版）は、湾の壁（c −5.5〜−4.6、列 153〜181）で帯の座標 w が縮んで（|∇w| 0.22 倍）模様の面に入り、G1 が落ちた。
WHITE_WINDOWS = [((-8.6, -5.6), (150, 200))] if os.environ.get("FX1_BLADE", "white") == "white" else []
# 歯の列の直し（批評の 7 番）：唇の先と唇の下（列 185 から）の白の境は、見本03 の白の印 v2（白い舌の先）を引き継いだので、
# 行ごとに白の届く列が 2〜6 行おきに 20〜40 列揺れ（爪の舌の形）、冠の爪を外した今は座席から同じ形の歯が並ぶように見えた。
# その区域だけ、白の印を行の向きにならす（σ 行）。四角い切り欠き（座席、c −2.4〜−1.4 m の唇の下）も同じ所で丸くなる。
TEETH = {"col0": 180, "col1": 192, "sigma_rows": 4.0}


def main():
    SH = sys.argv[1] if os.path.isabs(sys.argv[1]) else REPO + "/" + sys.argv[1]
    CAND = SH + "/final/cand/" + sys.argv[2]
    NAME = "hero_smooth_as04f"
    nr, nc = 240, 400
    import ds33_common as U  # noqa: F401
    SC.HERO_PKG = SH + "/hero_pkg_AS04F"
    Pb = SC.load_hero_world()
    sd_old = np.fromfile(M.WM_OLD, np.float32).astype(np.float64).reshape(nr, nc)
    rows = np.load(CAND + "_rows.npz")
    c = rows["c"].astype(np.float64)
    from scipy.ndimage import gaussian_filter1d
    sd_src = sd_old.copy()
    jj = np.arange(nc)
    wcol = np.clip((jj - TEETH["col0"]) / max(TEETH["col1"] - TEETH["col0"], 1), 0, 1)
    wcol = wcol * wcol * (3 - 2 * wcol)
    sd_sm = gaussian_filter1d(sd_src, TEETH["sigma_rows"], axis=0, mode="nearest")
    sd_teeth = sd_src + wcol[None, :] * (sd_sm - sd_src)
    teeth_flipped = int(((sd_teeth > 0) != (sd_src > 0)).sum())
    sd_src = sd_teeth
    changed = 0
    for (c0, c1), j0 in BLUE_WINDOWS:
        m = (c >= c0) & (c <= c1)
        blk = sd_src[m, j0:]
        changed += int((blk > 0).sum())
        sd_src[m, j0:] = -np.maximum(np.abs(blk), 0.01)
    made_white = 0
    for (c0, c1), (j0, j1) in WHITE_WINDOWS:
        m = (c >= c0) & (c <= c1)
        blk = sd_src[m, j0:j1]
        made_white += int((blk <= 0).sum())
        sd_src[m, j0:j1] = np.maximum(np.abs(blk), 0.01)
    sd_new = M.resigned_distance(Pb, sd_src)
    Hrow = Pb[:, 18:201, 1].max(1)
    cap = (Hrow - M.LOW_H0 * M.H0) * M.LOW_K
    sd_new = np.minimum(sd_new, cap[:, None])
    os.makedirs(SH + "/mesh", exist_ok=True)
    wm = SH + "/mesh/white_mask_as04f_f32.bin"
    sd_new.astype(np.float32).tofile(wm)
    wrep = {"source_mask": M.WM_OLD, "source_sha256": SC.sha(M.WM_OLD), "out": wm, "out_sha256": SC.sha(wm),
            "blue_windows_ja": "白い刃の直し：c の窓と列の始まり（その窓の列より先の白の頂点を藍にした）", "blue_windows": [[list(w), j] for w, j in BLUE_WINDOWS],
            "white_vertices_turned_blue": changed,
            "white_windows": [[list(w), list(j)] for w, j in WHITE_WINDOWS], "blue_vertices_turned_white": made_white,
            "blade_mode": os.environ.get("FX1_BLADE", "white"),
            "teeth_smoothing": dict(TEETH, vertices_flipped=teeth_flipped,
                                    note_ja="唇の先と唇の下（列 180〜192 から先）の白の印を行の向きに σ 4 行でならした（歯の列・四角い切り欠きを消す）"),
            "white_vertices_source_new": [int((sd_old > 0).sum()), int((sd_new > 0).sum())],
            "low_rows_rule": {"LOW_H0": M.LOW_H0, "LOW_K": M.LOW_K},
            "note_ja": "白・藍の区域は見本03 の白の印 v2 を頂点の番号で引き継ぎ（白い刃の窓だけ藍）、境からの距離を AS04F の面の上で測り直した。"}
    SC.GWB = CAND + ".gwb"
    SC.META = CAND + "_meta.json"
    SC.ROWS = CAND + "_rows.npz"
    SC.ATTR = SH + "/attr/a/s01a_hero_attr_v2_f32.bin"
    SC.OUT = SH
    R.S = SC
    sys.argv = ["surf_relief.py", "--name", NAME, "--flat", "--white-mask", wm]
    R.main()
    rp = SH + "/mesh/" + NAME + "_report.json"
    rep = json.load(open(rp, encoding="utf-8"))
    rep["as04f_white_mask"] = wrep
    rep["as04f_inputs"] = {"hero_pkg": SC.HERO_PKG, "gwb": SC.GWB, "meta": SC.META, "rows": SC.ROWS, "attr": SC.ATTR}
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(wrep, ensure_ascii=False))


if __name__ == "__main__":
    main()
