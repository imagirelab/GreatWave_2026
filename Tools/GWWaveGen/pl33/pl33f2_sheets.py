# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 2：前後の図と動画を、後＝修正の回 2（Build/Polish/33/fix02/r_fix02）で描き直す（pl33_sheets.py の関数をそのまま使い、後の説明だけ替える）。
修正の回 1 の同じ名前の図・動画は Git 対象外の Unity/Build/Polish/33/record/archive_fix01/ に写して残した（archive_index.json に SHA-256）。

使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_sheets.py [--skip-video]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pl33_sheets as S  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
S.HEAD_A = ("後＝仕上げ33 修正の回 2：修正の回 1（原画の爪の低い浮き彫り、鉤の内の水色の膜、b区域の房の添え指、稜の房の冠の爪 18 房 79 本）に、"
            "⑤ pl33f2_white_clip：膜と添え指を t 10 s〜t* のどのコマでも白の範囲の内（3D の白の範囲、原画視点の空と藍の上に出ない）に縮め、"
            "pl33f2_grow_schedule で時刻とともに増えるだけの倍率にした（b区域の頂から藍へ垂れる水色の細片 WC223・SC223m・WC224 をなくした。"
            "膜 38 本・添え指 22 本を縮め、添え指 12 本は根元へ潰した）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=REPO + "/Unity/Build/Polish/32/fix01/r_fix01")
    ap.add_argument("--after", default=REPO + "/Unity/Build/Polish/33/fix02/r_fix02")
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
