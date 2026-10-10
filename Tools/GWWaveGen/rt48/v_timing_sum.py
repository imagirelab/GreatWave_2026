# -*- coding: utf-8 -*-
"""RT48 つなぎ・確かめの段：C7 の記録（v_timing.ps1 の出力）をまとめ、record_ja.md の V7・V8 で判定する（py -3.10）。
使い方:  py -3.10 v_timing_sum.py <Unity/Build/RT48/verify/timing/<tag>>
出力：<tag>/summary.json と標準出力の表。"""
import sys, os, json
import numpy as np

GATE = 8.9


def summ(v):
    v = np.asarray(v, dtype=np.float64)
    if len(v) == 0:
        return None
    return dict(n=int(len(v)), p50=float(np.percentile(v, 50)), p95=float(np.percentile(v, 95)), p99=float(np.percentile(v, 99)),
                max=float(v.max()), mean=float(v.mean()), over8_9=float((v > 8.9).mean()), over11_1=float((v > 11.1).mean()))


def mock_check(png):
    """V8：左右の眼の絵（横に並んだ 1 枚）。どちらも一色でなく、右を −40〜+40 px ずらして最も合う所の差の平均 ≤ 3/255"""
    if not os.path.exists(png):
        return dict(found=False, pass_=None, note="両眼の絵が書かれていない")
    from PIL import Image
    im = np.asarray(Image.open(png).convert("RGB")).astype(np.float64) / 255.0
    h, w, _ = im.shape
    L, R = im[:, : w // 2], im[:, w // 2: w // 2 * 2]
    lum = lambda a: 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    l, r = lum(L), lum(R)
    best = None
    for s in range(-40, 41):
        if s >= 0:
            d = np.abs(l[:, s:] - r[:, :r.shape[1] - s]).mean()
        else:
            d = np.abs(l[:, :s] - r[:, -s:]).mean()
        if best is None or d < best[1]:
            best = (s, float(d))
    res = dict(found=True, size=[w, h], left_mean=float(l.mean()), left_std=float(l.std()), right_mean=float(r.mean()), right_std=float(r.std()),
               raw_mean_abs_diff=float(np.abs(l - r).mean()), best_shift_px=best[0], best_mean_abs_diff=best[1])
    res["pass_"] = bool(l.std() > 0.01 and r.std() > 0.01 and best[1] <= 3 / 255)
    # 04:33 に足した参考（判定の決め方を変えた所。record_ja.md）：Mock の眼の画角は左右で非対称なので、ずらす幅を半分の幅の ±1/2 まで広げる
    wide = None
    for s in range(-(w // 4), w // 4 + 1):
        d = np.abs(l[:, s:] - r[:, :r.shape[1] - s]).mean() if s >= 0 else np.abs(l[:, :s] - r[:, -s:]).mean()
        if wide is None or d < wide[1]:
            wide = (s, float(d))
    res.update(wide_search_px=w // 4, wide_best_shift_px=wide[0], wide_best_mean_abs_diff=wide[1],
               pass_wide=bool(l.std() > 0.01 and r.std() > 0.01 and wide[1] <= 3 / 255))
    return res


def main(d):
    mach = json.load(open(os.path.join(d, "machine.json"), encoding="utf-8-sig"))
    out = dict(dir=d, gate_ms=GATE, conds={})
    for c in mach["conds"]:
        name = c["name"]
        row = dict(window=c["window"], proxy=c["proxy"], exit=c["exitCode"], cpuTotalPctMean=c.get("cpuTotalPctMean"), cpuTotalPctMax=c.get("cpuTotalPctMax"),
                   hython_samples=c.get("hythonSamples"), n_samples=c.get("nSamples"))
        if c.get("mock"):
            row["mock"] = mock_check(os.path.join(d, "mock_botheyes.png"))
            log = c["log"]
            if os.path.exists(log):
                row["log_lines"] = [ln.strip() for ln in open(log, encoding="utf-8", errors="replace") if "RT48_XR" in ln or "Exception" in ln][:10]
        elif os.path.exists(c["json"]):
            j = json.load(open(c["json"], encoding="utf-8-sig"))
            cpu_all = np.concatenate([r["cpuMs"] for r in j["runs"]]) if j["runs"] else np.zeros(0)
            gpu_all = np.concatenate([r["gpuMs"] for r in j["runs"]]) if j["runs"] else np.zeros(0)
            # 測れなかったフレーム（0 以下）と時刻の読み違い（1,000 ms 超）は除き、数を書く（04:33 に足した読み方。record_ja.md）
            okc = (cpu_all > 0) & (cpu_all < 1000); okg = (gpu_all > 0) & (gpu_all < 1000)
            cpu, gpu = cpu_all[okc], gpu_all[okg]
            row_ex = dict(cpu_n_all=int(len(cpu_all)), cpu_excluded_le0=int((cpu_all <= 0).sum()), cpu_excluded_ge1000=int((cpu_all >= 1000).sum()),
                          gpu_n_all=int(len(gpu_all)), gpu_excluded_le0=int((gpu_all <= 0).sum()), gpu_excluded_ge1000=int((gpu_all >= 1000).sum()),
                          gpu_with_zeros=summ(gpu_all[gpu_all < 1000]))
            dt = np.concatenate([r["dtMs"] for r in j["runs"]]) if j["runs"] else []
            row.update(runs=len(j["runs"]), frames=[r["unityFrames"] for r in j["runs"]], sim=[[r["simStart"], r["simEnd"]] for r in j["runs"]],
                       frameTimingAvailable=j["frameTimingAvailable"], isDebugBuild=j["isDebugBuild"], vSync=j["vSyncCount"],
                       screen=[j["screenWidth"], j["screenHeight"]], eye=[j["eyeWidth"], j["eyeHeight"], j["eyeMsaa"]], graphicsApi=j["graphicsApi"],
                       cpu=summ(cpu), gpu=summ(gpu), dt=summ(dt), excluded=row_ex,
                       per_run=[dict(cpu_p95=r["cpu"]["p95"], gpu_p95=r["gpu"]["p95"], frames=r["unityFrames"]) for r in j["runs"]])
            if c["proxy"]:
                row["pass_"] = bool(row["cpu"] and row["gpu"] and row["cpu"]["p95"] <= GATE and row["gpu"]["p95"] <= GATE)
        out["conds"][name] = row
    prox = [v for k, v in out["conds"].items() if k.startswith("proxy")]
    out["C7_pass"] = bool(len(prox) == 3 and all(v.get("pass_") for v in prox))
    json.dump(out, open(os.path.join(d, "summary.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    for k, v in out["conds"].items():
        if "cpu" in v and v["cpu"]:
            print("%-10s CPU p50 %.2f p95 %.2f p99 %.2f max %.1f >8.9 %.4f >11.1 %.4f | GPU p50 %.2f p95 %.2f p99 %.2f max %.1f >8.9 %.4f >11.1 %.4f | frames %s | cpuLoad %s%% hython %s/%s | pass %s" % (
                k, v["cpu"]["p50"], v["cpu"]["p95"], v["cpu"]["p99"], v["cpu"]["max"], v["cpu"]["over8_9"], v["cpu"]["over11_1"],
                v["gpu"]["p50"], v["gpu"]["p95"], v["gpu"]["p99"], v["gpu"]["max"], v["gpu"]["over8_9"], v["gpu"]["over11_1"], v["frames"],
                v["cpuTotalPctMean"], v["hython_samples"], v["n_samples"], v.get("pass_")))
            print("           excluded:", json.dumps({q: w for q, w in v["excluded"].items() if q != "gpu_with_zeros"}),
                  "| GPU p95 with zeros %.2f" % v["excluded"]["gpu_with_zeros"]["p95"], "| dt p50 %.2f p95 %.2f p99 %.2f" % (v["dt"]["p50"], v["dt"]["p95"], v["dt"]["p99"]))
        else:
            print(k, json.dumps(v, ensure_ascii=False)[:1500])
    print("C7_pass", out["C7_pass"])


if __name__ == "__main__":
    main(sys.argv[1])
