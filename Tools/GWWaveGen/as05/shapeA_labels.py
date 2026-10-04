# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：層の印（主役波の行の格子の int の npy）と、s5_targets.py measure の候補の json を書く。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_labels.py [render_dir]

層の印（形で分けた層。原画の区域から写したものではない）：
  1 ① 主の頂と唇：行 c ≥ C12（② の窓の右）、列 J_TOP（90）〜前の面の下、高さ ≥ 0.25 H0
  2 ② b区域：行 c C23〜C12（shapeA_hero の step2 の窓）、列 104（背の頂の前、溝から）〜 300、高さ ≥ 0.25 H0（溝・縁の頂・唇・垂れの面）
  3 ③：別のメッシュ layer3 の全部の頂点（shapeA_l3.py の layer3_labels.npy）
  0 ほか（主役波の左の肩・背など。s5_targets は前を 4、背を 8 にする）
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402

C12, C23 = -8.3, -13.5
LAB = C.OUT + "/hero/row_labels_AS05A.npy"
CAND = C.OUT + "/measure/cand_AS05A.json"


def labels(rows=C.ROWS05A):
    c, A, Y = C.SC.load_rows(rows)
    RL = np.zeros(A.shape, np.int16)
    J = np.arange(A.shape[1])[None, :]
    cc = c[:, None]
    hi = Y >= 0.25 * C.H0
    RL[(cc >= C12) & (J >= 90) & (J <= 379) & hi] = 1
    # ② は step2 の窓の重みが 0.5 以上の行の、溝の底（列 J_G）から前（溝・縁の頂・唇・垂れの面）
    import shapeA_hero as H
    p = H.DESIGN["step2"]
    w = C.wwin(c, p["full"], p["blend"])
    jg = np.argmin(np.where((J >= 104) & (J <= 200), Y, 1e9), axis=1)        # 行ごとの溝の底の列（列 104〜200 の最も低い所）
    RL[(w[:, None] >= 0.5) & (J >= 104) & (J <= 300) & hi] = 2      # 溝の後ろの壁（背の頂の前、列 104 から）も ② の段に入れる
    return RL


def main():
    rd = sys.argv[1] if len(sys.argv) > 1 else None
    RL = labels()
    os.makedirs(os.path.dirname(LAB), exist_ok=True)
    np.save(LAB, RL)
    cand = {"name": "AS05A", "rows": C.ROWS05A, "row_labels": LAB,
            "meshes": [{"path": C.WAVE4_F1, "role": "wave4", "layer": 0},
                       {"path": C.L3_JSON, "role": "layer3", "layer": 3, "vertex_labels": C.OUT + "/l3/layer3_labels.npy"}]}
    if rd:
        cand["render_dir"] = rd
    C.jdump(CAND, cand)
    print("labels", {k: int((RL == k).sum()) for k in (0, 1, 2)}, CAND)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
