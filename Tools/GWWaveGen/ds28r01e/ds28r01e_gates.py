# -*- coding: utf-8 -*-
"""設計28修正01 試行E：関門の検査器を、精度の層（ds27_pos_lo_rgba8.bin）を足した位置（新しい再生器の読み）で走らせる包み（記録用）。

既定の関門（古い再生器と同じ 16 bit の読み）は試行D の包み ds28r01d_gates.py のまま走らせる。この包みは、同じプロセスの中だけで
ds27_gates.Package を ds28r01e_review.FinePackage（16 bit ＋ 精度の層）に差し替えてから ds28r01d_gates.main を呼ぶ（ファイルは変えない）。
P16 のように h = 1/30 s の二階差分で 0.05 m/s² を測る関門は、16 bit の刻み 1.7 mm の雑音（最大 約 2 m/s²）が支配するので、精度の層の読みも記録する。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01e/ds28r01e_gates.py [--stop-max 1.3] --kstar <K* のフォルダー> --tool gates -- <ds28r01_gates.py の引数>
  --stop-max：P16 の止めるための区間の上限（既定 0.5 s）を変えた読み（記録）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "ds28r01d")))
sys.path.insert(0, HERE)
import ds28r01d_gates as DGW  # noqa: E402
import ds28r01e_review as RE  # noqa: E402

if __name__ == "__main__":
    # --stop-max <s>（包みの引数、-- の前）：P16 の「止めるための区間」の上限（検査器の既定 0.5 s）を変えた読み（記録。E4 の止めは 1.2 s）
    if "--stop-max" in sys.argv:
        k = sys.argv.index("--stop-max")
        DGW.DG.TH["P16_stop_ramp_max_s"] = float(sys.argv[k + 1])
        del sys.argv[k:k + 2]
    DGW.DG.Package = RE.FinePackage
    DGW.main()
