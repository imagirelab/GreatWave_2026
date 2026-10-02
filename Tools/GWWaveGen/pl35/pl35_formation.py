# -*- coding: utf-8 -*-
"""仕上げ35：体験の通し（設計50 の自動の試し --ds50auto main）の形成の全区間のフレームの時間を数える（199 の代理。記録）。

設計50 の frames.csv（コマごとの udt＝実時間の間隔、FrameTimingManager の ftCpuMain・ftGpu、相 phase、時計の動き clockRunning、止め flowPaused、大波の時刻 wave）から、
相が Formation で時計が動いている（clockRunning = 1、flowPaused = 0）コマだけを取る。自動の試しは形成の中で停止の試し（P で止めて再開）を 1 回するので、
止めている間のコマ（時計が進まず段を呼ばない。速い）は除く（仕上げ33 までの sweep_perf.py の相の中央値はこのコマを含んでいた）。
間隔＝udt（秒→ms）。平均 fps＝1000／間隔の平均、p95・p99・最大、33.3 ms・11.1 ms を超えた割合。大波の時刻 1 s ごとの平均と CPU 主スレッドの中央値も出す。
HMD の実機ではない（PS VR2 は未導入）。RTX 3080・i7-12700K の PC の代理、1920×1080 の窓、単眼、垂直同期なし。
使い方：py -3.10 -B Tools/GWWaveGen/pl35/pl35_formation.py --run <dir>[,<dir>...] --out <json>
"""
import argparse
import csv
import json
import math
import os

import numpy as np


def fnum(x):
    try:
        v = float(x)
        return v if not math.isnan(v) else np.nan
    except ValueError:
        return np.nan


def one(d):
    rows = list(csv.DictReader(open(os.path.join(d, "frames.csv"), encoding="utf-8")))
    allf = [r for r in rows if r["phase"] == "Formation"]
    f = [r for r in allf if r["clockRunning"] == "1" and r["flowPaused"] == "0"]
    udt = np.array([fnum(r["udt"]) for r in f]) * 1000.0
    cm = np.array([fnum(r["ftCpuMain"]) for r in f]); g = np.array([fnum(r["ftGpu"]) for r in f])
    w = np.array([fnum(r["wave"]) for r in f])
    out = {"run": os.path.basename(d), "formation_rows_all": len(allf), "formation_rows_running": len(f),
           "interval_mean_ms": round(float(np.nanmean(udt)), 3), "fps_mean": round(1000.0 / float(np.nanmean(udt)), 1),
           "interval_p50_ms": round(float(np.nanpercentile(udt, 50)), 3), "interval_p95_ms": round(float(np.nanpercentile(udt, 95)), 3),
           "interval_p99_ms": round(float(np.nanpercentile(udt, 99)), 3), "interval_max_ms": round(float(np.nanmax(udt)), 3),
           "over_33_3ms_frac": round(float((udt > 33.3).mean()), 4), "over_11_1ms_frac": round(float((udt > 11.1).mean()), 4),
           "cpuMain_p50_ms": round(float(np.nanmedian(cm)), 3), "cpuMain_p95_ms": round(float(np.nanpercentile(cm, 95)), 3),
           "gpu_p95_ms": round(float(np.nanpercentile(g[g > 0], 95)), 3) if np.any(g > 0) else None,
           "wave_min": round(float(np.nanmin(w)), 3), "wave_max": round(float(np.nanmax(w)), 3), "by_wave_s": {}}
    for a in range(0, 12):
        s = (w >= a) & (w < a + 1)
        if s.sum():
            out["by_wave_s"]["%02d" % a] = {"n": int(s.sum()), "interval_mean_ms": round(float(np.nanmean(udt[s])), 2),
                                           "interval_p95_ms": round(float(np.nanpercentile(udt[s], 95)), 2), "cpuMain_p50_ms": round(float(np.nanmedian(cm[s])), 2)}
    rep = os.path.join(d, "report.json")
    if os.path.exists(rep):
        r = json.load(open(rep, encoding="utf-8-sig"))
        out.update({"pass": r.get("pass"), "errors": r.get("errors"), "exceptions": r.get("exceptions"), "frames": r.get("frames")})
    lj = os.path.join(d, "launch.json")
    if os.path.exists(lj):
        l = json.load(open(lj, encoding="utf-8-sig"))
        out.update({"exe": l.get("exe"), "exeSha256": l.get("exeSha256"), "args": l.get("args")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"rule_ja": __doc__.strip().split("\n\n")[1], "runs": [one(d) for d in a.run.split(",")]}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in res["runs"]:
        print(r["run"], "rows", r["formation_rows_running"], "/", r["formation_rows_all"], "fps", r["fps_mean"], "p95", r["interval_p95_ms"], "p99", r["interval_p99_ms"],
              ">33.3", r["over_33_3ms_frac"], "cpuMain p50", r["cpuMain_p50_ms"], "gpu p95", r["gpu_p95_ms"], "pass", r.get("pass"))
        print("   ", " ".join("%s:%.1f" % (k, v["interval_mean_ms"]) for k, v in r["by_wave_s"].items()))


if __name__ == "__main__":
    main()
