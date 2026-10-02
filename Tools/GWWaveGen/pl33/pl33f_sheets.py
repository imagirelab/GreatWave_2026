# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1：前後の図と動画を、後＝修正の回 1（Build/Polish/33/fix01/r_fix01）で描き直す（pl33_sheets.py の関数をそのまま使い、後の説明だけ替える）。
作る部の同じ名前の図・動画は Git 対象外の Unity/Build/Polish/33/record/archive_build/ に写して残した（archive_index.json に SHA-256）。

使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33f_sheets.py [--skip-video]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pl33_sheets as S  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
S.HEAD_A = ("後＝仕上げ33 修正の回 1：① pl33f_low_relief：原画の爪の立ち上げを帯の弧長 × 0.12（上限 0.22 m、先は面の近くへ戻る）にし、t 10.3 s から t* へ"
            "ゆっくり浮かせる（作る部は × 0.35・0.8 m）。断面の裏返りを 180° 回して続け、急な折れの縁の折れ返りの幅を縮めた、② 鉤の内の水色の版の膜（b区域は帯の幅 × 3.0）が面に入らないよう"
            "縮めた、③ pl33f_tuft_fingers：b区域の爪 57 本の両側に短い添え指（外の縁だけに線）を置き房にした、④ pl33f_crown：冠の爪を稜（後ろ 65°・回り台の上の縁）"
            "に沿う 3 本以上の指の房 18 房 79 本にし、生まれてから t* まで原画のカメラから隠れ、座席の目から主役波の面の上に見えないことを確かめた")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=REPO + "/Unity/Build/Polish/32/fix01/r_fix01")
    ap.add_argument("--after", default=REPO + "/Unity/Build/Polish/33/fix01/r_fix01")
    ap.add_argument("--out", default=REPO + "/Docs/Evidence/Polish/33")
    ap.add_argument("--skip-video", action="store_true")
    a = ap.parse_args()
    fs = S.view_sheets(a, a.out) + S.turntable(a, a.out)
    if not a.skip_video:
        fs += S.videos(a, a.out)
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
