# -*- coding: utf-8 -*-
"""仕上げ30 修正02：海の面の GPU の時間（壁時計の見当）を、前（-pl30Old 1：仕上げ29 の海）と後（修正02 の海）の 3 回ずつの描画（PL30Render -pl29Only gpu）から集める。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_gpu_runs.py --dir Unity/Build/Polish/30/fix02 --out Docs/Evidence/Polish/30/gpu_sea_fix02_runs.json
読むもの：<dir>/gpu_before<k>/gpu/pl30_gpu_sea.json・<dir>/gpu_after<k>/gpu/pl30_gpu_sea.json（k = 1〜3）と、修正01 の値 Docs/Evidence/Polish/30/gpu_sea_fix01_runs.json。
"""
import argparse
import json
import os

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="Unity/Build/Polish/30/fix02")
    ap.add_argument("--out", default="Docs/Evidence/Polish/30/gpu_sea_fix02_runs.json")
    a = ap.parse_args()
    d = os.path.join(REPO, a.dir)
    runs = {}
    for side in ("before", "after"):
        for k in (1, 2, 3):
            p = os.path.join(d, "gpu_%s%d" % (side, k), "gpu", "pl30_gpu_sea.json")
            if not os.path.exists(p):
                continue
            g = json.load(open(p, encoding="utf-8"))
            for t in g["timing"]:
                runs.setdefault(t["cond"], {}).setdefault(side, []).append(round(float(t["heroMs"]), 4))
    f1 = json.load(open(os.path.join(REPO, "Docs", "Evidence", "Polish", "30", "gpu_sea_fix01_runs.json"), encoding="utf-8"))
    out = {}
    for c, v in runs.items():
        b, af = v.get("before", []), v.get("after", [])
        out[c] = dict(before_ms=b, after_ms=af, before_median=float(np.median(b)) if b else None, after_median=float(np.median(af)) if af else None,
                      diff_median=(float(np.median(af)) - float(np.median(b))) if b and af else None,
                      fix01_after_median=f1["runs"].get(c, {}).get("after_median"))
    rec = dict(number="仕上げ30 修正02",
               method_ja="PL30Render -pl29Only gpu -pl29Gpu 1 -pl30GpuTarget sea を、前（-pl30Old 1：仕上げ29 の海）と後（修正02 の海）で 3 回ずつ交互に回した（修正01 と同じ方法）。"
                         "各回は周りの海の面だけを残し t 6〜12 s の 120 コマを RT へ描いて毎コマ 1 画素を読み戻す壁時計の平均を 3 回（あり・なし）とり、中央値の差を海の分とした。GPU のタイマーではない。RTX 3080・Direct3D11。HMD 実機ではない。",
               runs=out)
    with open(os.path.join(REPO, a.out), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    for c, v in out.items():
        print(c, v["before_median"], "->", v["after_median"], "(fix01", v["fix01_after_median"], ")")


if __name__ == "__main__":
    main()
