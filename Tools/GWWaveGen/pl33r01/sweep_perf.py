# -*- coding: utf-8 -*-
"""仕上げ33修正01 変種 SWEEP：Release のプレイヤー（設計50 の自動の試し、PC の 1920×1080 の窓）の負荷を、前（仕上げ33 の exe）と後（SWEEP の exe）で並べる（記録）。

読むもの：<runs>/<tag>/report.json（pass・frames・errors・exceptions）と frames.csv（コマごとの FrameTimingManager の ftCpuMain・ftGpu、段 phase）。
段ごとに ftCpuMain・ftGpu・ftCpu の中央値（ms。NaN を除く）を出す。HMD の実機ではない（PS VR2 は未導入）。90 Hz の予算は 11.1 ms。
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_perf.py --runs Unity/Build/Polish/33r01/sweep/release/runs --tags pl33_1,sweep_1,pl33_2,sweep_2 --out …
"""
import argparse
import csv
import json
import math
import os
import statistics

REPO = "G:/Unity/GreatWave_2026_Fresh"


def summarize(d):
    rep = json.load(open(os.path.join(d, "report.json"), encoding="utf-8-sig"))
    by = {}
    with open(os.path.join(d, "frames.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ph = r["phase"]
            for k in ("ftCpuMain", "ftGpu", "ftCpu"):
                try:
                    v = float(r[k])
                except ValueError:
                    continue
                if math.isnan(v):
                    continue
                by.setdefault(ph, {}).setdefault(k, []).append(v)
    out = {"frames": rep.get("frames"), "seconds": rep.get("realSeconds"), "pass": rep.get("pass"), "errors": rep.get("errors"),
           "exceptions": rep.get("exceptions"), "gpu": rep.get("gpu"), "graphicsApi": rep.get("graphicsApi")}
    if out["frames"] and out["seconds"]:
        out["fps"] = round(out["frames"] / out["seconds"], 1)
    for ph, kv in by.items():
        out[ph] = {k: round(statistics.median(v), 4) for k, v in kv.items()}
        out[ph]["n"] = len(kv.get("ftGpu", []))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--tags", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"rule_ja": __doc__.strip().split("\n\n")[1]}
    for t in a.tags.split(","):
        d = os.path.join(a.runs, t)
        if os.path.exists(os.path.join(d, "report.json")):
            res[t] = summarize(d)
            lj = os.path.join(d, "launch.json")
            if os.path.exists(lj):
                res[t]["exe"] = json.load(open(lj, encoding="utf-8-sig")).get("exe")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for t, v in res.items():
        if t == "rule_ja":
            continue
        print(t, v.get("frames"), v.get("pass"), "Formation", v.get("Formation"), "Hold", v.get("Hold"))


if __name__ == "__main__":
    main()
