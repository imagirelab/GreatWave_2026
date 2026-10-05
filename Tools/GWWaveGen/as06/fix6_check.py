# -*- coding: utf-8 -*-
"""美術の見本06 の直しの回（段の行 R8 → R9）：asm6_check.py（変えない）を読み込み、比べる作りを 前 B10・直す前 R8（組み立ての描画 R8A）・直した R9 にして同じ確かめ
（主役波と wave4 の食い込み・帯の座標 w の伸び・原画視点の爪の隠れ・一艘目の船の画素）を出す。
使い方：py -3.10 -B Tools/GWWaveGen/as06/fix6_check.py <出力.json>
"""
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as06")
import asm6_check as C  # noqa: E402

P = REPO + "/Unity/Build/Polish"
C.BUILDS = {
    "B10": C.BUILDS["B10"],
    "R8": {"union": P + "/sample06/rows/mesh/union_AS06R_d_f1.json", "hero": P + "/sample06/rows/final_d/mesh/hero_smooth_as06r.json",
           "render": P + "/sample06/assemble/render/R8A"},
    "R9": {"union": P + "/sample06/fix/mesh/union_AS06R9_f1.json", "hero": P + "/sample06/fix/final/mesh/hero_smooth_as06r.json",
           "render": P + "/sample06/fix/render/R9"},
}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import os
    os.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)
    C.main()
