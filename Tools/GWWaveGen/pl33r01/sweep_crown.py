# -*- coding: utf-8 -*-
"""仕上げ33修正01 変種 SWEEP：頂の裏の冠の爪（仕上げ33 の pl33f_crown）を、掃引の指と同じ断面で、長く太い立つ指にして作り直す（numpy）。

名前の付いた美術の誘導：
  - pl33r01s_crown_big：仕上げ33 修正の回 1 の pl33f_crown.py の手順（稜の上の房、原画のカメラと座席の目から隠れる検査、形成の途中の隠れの検査、
    房の最小の本数）をそのまま使い、指の寸法と巻きだけを変える：房の長さ LT_MIN〜LT_MAX、幅 W_REL × 長さ（W_MIN〜W_MAX）、
    厚み TH_REL × 幅、立ち上がり THETA0 から先の巻き THETA1 まで。断面の輪の頂点の角度は sweep_build.py の Q_ANG（白が約 8 割）。
  - 原画のカメラからは、仕上げ33 と同じく生まれてから t* まで隠れる（原画視点の投影の色・形は変えない）。
入力：--relief（sweep_build.py の --no-crown の出力。既定 Unity/Build/Polish/33r01/sweep/fingers）
出力：--out（既定 Unity/Build/Polish/33r01/sweep/claws）。ds33_claw_layout.json の書式（指 C… ＋ 冠の爪 K…）。
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_crown.py [--relief …] [--out …]
"""
import argparse
import json
import os
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r01")
import pl33f_crown as KC  # noqa: E402
import sweep_build as SB  # noqa: E402

BIG = dict(LT_MIN=3.6, LT_MAX=5.2, W_REL=0.20, W_MIN=0.50, W_MAX=0.95, TH_REL=0.70, THETA0=78.0, THETA1=-20.0, CURL_POW=1.6,
           TUFT_SP=2.6, FING_SP=0.85, N_MIN=3, N_MAX=5, TIP_W=0.08, FAN_DEG=16.0, Y_MIN=9.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relief", default=REPO + "/Unity/Build/Polish/33r01/sweep/fingers")
    ap.add_argument("--out", default=REPO + "/Unity/Build/Polish/33r01/sweep/claws")
    ap.add_argument("--scale", type=float, default=1.0, help="房の長さと幅に掛ける倍率（試し用）")
    ap.add_argument("--seat-free", action="store_true", help="pl33f_crown_seat（座席の目から主役波の面の前に見える冠の爪を作らない）を外す")
    ap.add_argument("--tuft-sp", type=float, default=None, help="房の中心の間隔（m）")
    ap.add_argument("--n-min", type=int, default=None)
    ap.add_argument("--n-max", type=int, default=None)
    ap.add_argument("--fing-sp", type=float, default=None)
    a = ap.parse_args()
    big = dict(BIG)
    if a.seat_free:
        big["SEAT_HID_M"] = -1000.0
    for k, v in (("TUFT_SP", a.tuft_sp), ("N_MIN", a.n_min), ("N_MAX", a.n_max), ("FING_SP", a.fing_sp)):
        if v is not None:
            big[k] = v
    for k in ("LT_MIN", "LT_MAX", "W_MIN", "W_MAX"):
        big[k] = big[k] * a.scale
    KC.P.update(big)
    KC.PHI = SB.Q_ANG.copy()
    sys.argv = [sys.argv[0], "--relief", a.relief, "--out", a.out]
    KC.main()
    p = os.path.join(a.out, "ds33_claw_layout.json")
    lay = json.load(open(p, encoding="utf-8"))
    lay["pl33r01_sweep_crown"] = {"note_ja": __doc__.strip().split("\n\n")[0], "tool": "Tools/GWWaveGen/pl33r01/sweep_crown.py",
                                  "params_changed": big, "ring_angles_deg": [round(float(x) * 180 / 3.141592653589793, 3) for x in SB.Q_ANG]}
    json.dump(lay, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SWEEP_CROWN_DONE", lay["vertices"], lay["triangles"])


if __name__ == "__main__":
    main()
