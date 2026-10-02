# -*- coding: utf-8 -*-
"""仕上げ35：負荷の計測器（PL35PerfProbe）の出力 pl35perf_<tag>.json を条件ごとに数える（記録）。

数え方は設計35（DS35PerfRunner・ds35_record.py）と同じ：FrameTimingManager のフレームの開始時刻の差を間隔とし、先頭 8 件を除く。
平均 fps＝1000／間隔の平均、間隔の p95・最大、33.3 ms・11.1 ms（90 Hz）を超えた割合。CPU 主スレッド・GPU は 0 より大きく 1 s 未満の値の中央値・p95。
段の時間（PL35PerfProbe の Stopwatch）はフレームごとの中央値・p95。HMD の実機ではない（PS VR2 は未導入）。RTX 3080 の PC の代理。
使い方：py -3.10 -B Tools/GWWaveGen/pl35/pl35_perf_summary.py --runs <dir> --tags f0_perf1,f0_perf2 --out <json>
"""
import argparse
import json
import os

import numpy as np


def cond_stats(c, freq=None):
    st = np.array(c.get("ftStart") or [], dtype=np.float64)
    out = {"name": c["name"], "view": c.get("view"), "stereoProxy": c.get("stereoProxy"), "frames": c.get("unityFrames"),
           "measureSeconds": c.get("measureSeconds")}
    if len(st) > 10:
        st = st[8:]
        # 開始時刻は CPU の計時の刻み（FrameTimingManager.GetCpuTimerFrequency。Windows は 10 MHz）
        iv = np.diff(st) / (freq or 1e7) * 1000.0
        iv = iv[iv > 0]
        out.update({"interval_mean_ms": round(float(iv.mean()), 3), "fps_mean": round(1000.0 / float(iv.mean()), 1),
                    "interval_p50_ms": round(float(np.percentile(iv, 50)), 3), "interval_p95_ms": round(float(np.percentile(iv, 95)), 3),
                    "interval_p99_ms": round(float(np.percentile(iv, 99)), 3), "interval_max_ms": round(float(iv.max()), 3),
                    "over_33_3ms": int((iv > 33.3).sum()), "over_11_1ms_frac": round(float((iv > 11.1).mean()), 4), "n_intervals": int(len(iv))})
    else:
        dt = np.array(c.get("dt") or [], dtype=np.float64) * 1000.0
        if len(dt) > 10:
            dt = dt[8:]
            out.update({"interval_mean_ms": round(float(dt.mean()), 3), "fps_mean": round(1000.0 / float(dt.mean()), 1),
                        "interval_p95_ms": round(float(np.percentile(dt, 95)), 3), "interval_max_ms": round(float(dt.max()), 3), "from": "unscaledDeltaTime"})
    for k, key in (("cpuMain", "ftCpuMain"), ("cpuRender", "ftCpuRender"), ("gpu", "ftGpu")):
        v = np.array(c.get(key) or [], dtype=np.float64)
        v = v[8:] if len(v) > 8 else v
        v = v[(v > 0) & (v < 1000)]
        if len(v):
            out[k + "_p50_ms"] = round(float(np.median(v)), 3)
            out[k + "_p95_ms"] = round(float(np.percentile(v, 95)), 3)
            out[k + "_zero_or_bad_frac"] = round(1 - len(v) / max(1, len(c.get(key) or [])), 3)
    for k in ("msSeek", "msWater", "msBoatWater", "msWhite", "msClaws", "msSpray"):
        v = np.array(c.get(k) or [], dtype=np.float64)
        if len(v) > 8:
            v = v[8:]
            out[k + "_p50"] = round(float(np.median(v)), 3)
            out[k + "_p95"] = round(float(np.percentile(v, 95)), 3)
    out["gc_gen0"] = c.get("gcGen0Collections")
    out["gc_gen2"] = c.get("gcGen2Collections")
    fr = max(1, c.get("unityFrames") or 1)
    out["alloc_MB_per_frame"] = round(((c.get("totalAllocatedEnd") or 0) - (c.get("totalAllocatedStart") or 0)) / fr / 1e6, 4)
    out["mono_used_delta_MB"] = round(((c.get("monoUsedEnd") or 0) - (c.get("monoUsedStart") or 0)) / 1e6, 2)
    if c.get("boatWaterRebuilds"):
        out["boatWater_rebuild_ms_mean"] = round(c["boatWaterRebuildMs"] / c["boatWaterRebuilds"], 3)
    tp = np.array(c.get("tPlayed") or [])
    if len(tp):
        out["t_played_min"] = round(float(tp.min()), 3)
        out["t_played_max"] = round(float(tp.max()), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--tags", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"rule_ja": __doc__.strip().split("\n\n")[1], "runs": {}}
    for t in a.tags.split(","):
        p = os.path.join(a.runs, t, "pl35perf_" + t + ".json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8-sig"))
        r = {k: d.get(k) for k in ("device", "graphicsApi", "cpu", "qualityName", "isDebugBuild", "frameTimingFeatureEnabled", "xrActive", "screenWidth", "screenHeight",
                                    "clawVertices", "clawTriangles", "clawItems", "sprayCount0", "sprayCount1", "windowStart", "windowEnd", "reachRealS", "takeoverWave",
                                    "stagesBefore", "stagesAfter", "errorJa", "hmdCamera", "paintingCamera", "seatCamera")}
        r["conditions"] = {c["name"]: cond_stats(c) for c in d.get("conditions") or []}
        res["runs"][t] = r
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for t, r in res["runs"].items():
        print("==", t, r["device"], r["screenWidth"], r["screenHeight"], "claws", r["clawVertices"], "spray", r["sprayCount0"], r["sprayCount1"], "err", r["errorJa"])
        for n, c in r["conditions"].items():
            print("%-22s fps %7s int p95 %6s max %6s >33 %3s >11.1 %5s | main p50 %6s p95 %6s gpu p95 %6s | seek %6s water %5s boat %6s white %5s claws %6s spray %5s | gc0 %s alloc/f %s MB" % (
                n, c.get("fps_mean"), c.get("interval_p95_ms"), c.get("interval_max_ms"), c.get("over_33_3ms"), c.get("over_11_1ms_frac"),
                c.get("cpuMain_p50_ms"), c.get("cpuMain_p95_ms"), c.get("gpu_p95_ms"), c.get("msSeek_p50"), c.get("msWater_p50"), c.get("msBoatWater_p50"),
                c.get("msWhite_p50"), c.get("msClaws_p50"), c.get("msSpray_p50"), c.get("gc_gen0"), c.get("alloc_MB_per_frame")))


if __name__ == "__main__":
    main()
