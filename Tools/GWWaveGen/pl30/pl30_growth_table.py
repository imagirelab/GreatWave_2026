# -*- coding: utf-8 -*-
"""仕上げ30 修正02：海の材質 PL30 Ukiyoe Sea Keypose の「系の今の育ち」の表（_GrowR0〜6・_GrowS0〜6）を、海のパッケージの生成記録から作り、
材質の値のファイル（pl30_sea_params.txt）の該当の行を書き換える。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_growth_table.py --sea Unity/Build/Polish/30/sea [--params-txt Tools/GWWaveGen/pl30/pl30_sea_params.txt]
表：s_k = k/27（k = 0〜27）、τ_k = −12·s_k²（τ = 0 の近くが密）。値は生成器の growth_right_knots（右の高い波・肩の稜。_GrowR）と
growth_knots（手前の小波。_GrowS）を節点の τ で線形に補ったもの（生成器の Features.g・g_r と同じ補い方）。材質は s = √(−τ/12) で表を線形に読む。
原画カメラは読まない（Q28）。参照モデルは読まない。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl30_sea as S  # noqa: E402

REPO = S.REPO
N = 28


def tables(sea_dir):
    log = S.load_json(os.path.join(sea_dir, "pl30_generate_log.json"))
    kj = S.load_json(os.path.join(sea_dir, "near", "ds27_keypose.json"))
    kn = np.array(kj["knot_tau"], np.float64)
    gR = np.array(log["growth_right_knots"], np.float64)
    gS = np.array(log["growth_knots"], np.float64)
    s = np.arange(N) / (N - 1.0)
    tau = -12.0 * s * s
    tR = np.interp(tau, kn, gR)
    tS = np.interp(tau, kn, gS)
    # 表を線形に読んだ時の、節点の値からのずれの最大（記録用）
    s_kn = np.sqrt(np.clip(-kn / 12.0, 0, 1)) * (N - 1)
    errR = float(np.abs(np.interp(s_kn, np.arange(N), tR) - gR).max())
    errS = float(np.abs(np.interp(s_kn, np.arange(N), tS) - gS).max())
    return tau, tR, tS, errR, errS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sea", default="Unity/Build/Polish/30/sea")
    ap.add_argument("--params-txt", default=os.path.relpath(os.path.join(HERE, "pl30_sea_params.txt"), REPO))
    args = ap.parse_args()
    sd = os.path.join(REPO, args.sea)
    tau, tR, tS, errR, errS = tables(sd)
    lines = ["# 修正02：系の今の育ちの表（pl30_growth_table.py が %s の pl30_generate_log.json（SHA-256 %s）から書く。"
             "s = k/27、τ = −12·s²。_GrowR は稜の系 g_r、_GrowS は小波 g。表を線形に読んだ時の節点の値からのずれの最大 g_r %.4f・g %.4f）"
             % (args.sea.replace("\\", "/"), S.sha256_file(os.path.join(sd, "pl30_generate_log.json"))[:16], errR, errS)]
    for nm, t in (("_GrowR", tR), ("_GrowS", tS)):
        for k in range(7):
            v = t[4 * k:4 * k + 4]
            lines.append("%s%d=%s" % (nm, k, ",".join("%.5f" % x for x in v)))
    p = os.path.join(REPO, args.params_txt)
    src = open(p, encoding="utf-8").read().splitlines()
    keep = [ln for ln in src if not (ln.startswith("_GrowR") or ln.startswith("_GrowS") or ln.startswith("# 修正02：系の今の育ちの表"))]
    out = keep + lines
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("written", p, "maxerr", errR, errS)
    for x, a, b in zip(tau, tR, tS):
        print("tau %8.3f gR %.4f gS %.4f" % (x, a, b))


if __name__ == "__main__":
    main()
