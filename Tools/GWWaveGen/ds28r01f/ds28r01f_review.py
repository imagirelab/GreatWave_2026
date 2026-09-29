# -*- coding: utf-8 -*-
"""設計28修正01 試行F：試行E の目標の検査器（ds28r01e_review.py）を、K*′ の行で走らせる包み（ファイルは変えない）。

E の検査器は主断面と峰の行を行の番号（159・192、唇先の列 199・223）で持つ。これは古い K*（kstar_foot、行の c の並びが違う）の番号で、
K*′（R1・R2、行 164 が c = 0）では c = −1.0 m・+5.6 m の行を測ってしまう。この包みは、同じプロセスの中だけで、行の番号を
K*′ の c で選び直す（主断面 = meta の main_row、峰の行 = c が +3.85 m に最も近い行、唇先の列 = 関門の検査器の KStar.tip_col）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_review.py --kstar <K*′> --tags F_R2 --tag-spec 'F_R2=<pkg>|<warp>|<kstar>|-3.85' --out <json>
  （--kstar の後は ds28r01e_review.py の引数そのまま）
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))
for sub in ("ds27", "ds28", "ds28r01", "ds28r01d", "ds28r01e"):
    p = os.path.join(GW, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import ds28r01d_gates as DGW  # noqa: E402
import ds28r01e_review as RE  # noqa: E402

RV = RE.RV


def main():
    argv = sys.argv[1:]
    k = argv.index("--kstar")
    kdir = argv[k + 1]
    del argv[k:k + 2]
    d = DGW.patch_kstar(kdir)
    ks = DGW.DG.KStar(d)
    main_row = int(ks.main_row)
    peak = int(np.argmin(np.abs(ks.c - 3.85)))
    rows = (main_row, peak)
    tip = {r: int(ks.tip_col[r]) if int(ks.tip_col[r]) >= 0 else 200 for r in rows}
    RV.ROWS = rows
    RV.TIP = tip
    RE.ROWS = rows
    RE.TIP = tip
    # 前の谷の行（E の検査器は古い K* の行 100・130・159・192・214）も c で選び直す（古い K* の c は E の K* のフォルダーの rows から）
    old = os.path.join(DGW.KS.REPO, "Unity", "Build", "Design", "28R01D", "kstar_foot", "kstar_a45_rows.npz")
    if os.path.isfile(old):
        c_old = np.load(old)["c"]
        RV.TROUGH_ROWS = tuple(int(np.argmin(np.abs(ks.c - c_old[r]))) for r in (100, 130, 159, 192, 214))
    RV.CC.ROWS = {"main": rows[0], "peak": rows[1]}
    print("[ds28r01f_review] 行 %s（c %.2f・%.2f m）、唇先の列 %s、谷の行 %s" % (rows, ks.c[rows[0]], ks.c[rows[1]], tip, RV.TROUGH_ROWS), flush=True)
    sys.argv = [RE.__file__] + argv
    RE.main()


if __name__ == "__main__":
    main()
