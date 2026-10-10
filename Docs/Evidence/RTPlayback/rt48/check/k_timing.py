# -*- coding: utf-8 -*-
"""5. 1 フレームの時間（計画 C7）を、プレイヤーが書いた生の記録（verify/timing/c7_1/*.json の毎フレームの値）から数え直す。
出力：out/k_timing.json"""
import numpy as np
from k_lib import *

D = RT + "/verify/timing/c7_1"
summ = jload(D + "/summary.json")
mach = jload(D + "/machine.json")
res = {}


def st(a):
    a = np.asarray(a, float)
    if len(a) == 0:
        return {}
    return dict(n=len(a), p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), p99=float(np.percentile(a, 99)), max=float(a.max()),
                n_over_8_9=int((a > 8.9).sum()), n_over_11_1=int((a > 11.1).sum()))


for name in ("proxy2000", "proxy2064", "proxy2800", "desk1080"):
    d = jload(D + f"/{name}.json")
    cpu = np.concatenate([r["cpuMs"] for r in d["runs"]]); gpu = np.concatenate([r["gpuMs"] for r in d["runs"]])
    dt = np.concatenate([r["dtMs"] for r in d["runs"]])
    g_ok = gpu[(gpu > 0) & (gpu < 1000)]
    runs = [dict(frames=r["unityFrames"], n_cpu=len(r["cpuMs"]), realSeconds=r["realSeconds"], sim=(r["simStart"], r["simEnd"]),
                 cpu_p95=float(np.percentile(r["cpuMs"], 95))) for r in d["runs"]]
    s_rep = summ["conds"][name]
    res[name] = dict(eye=(d.get("eyeWidth"), d.get("eyeHeight"), d.get("eyeMsaa")), proxy=d.get("proxy"), xrActive=d.get("xrActive"),
                     isDebugBuild=d.get("isDebugBuild"), vSync=d.get("vSyncCount"), api=d.get("graphicsApi"), warm=d.get("warmSeconds"),
                     runs=runs, cpu=st(cpu), cpu_le0=int((cpu <= 0).sum()),
                     gpu_excl=st(g_ok), gpu_all=st(gpu[gpu < 1000]), gpu_le0=int((gpu <= 0).sum()), gpu_ge1000=int((gpu >= 1000).sum()),
                     gpu_ge1000_values=[float(v) for v in gpu[gpu >= 1000]][:3], dt=st(dt),
                     reported=dict(cpu=s_rep["cpu"], gpu=s_rep["gpu"], excluded=s_rep["excluded"]),
                     p95_with_zeros_minus_without=float(np.percentile(gpu[gpu < 1000], 95) - np.percentile(g_ok, 95)))
    r = res[name]
    r["match_cpu"] = all(abs(r["cpu"][k] - s_rep["cpu"][k]) < 1e-6 for k in ("p50", "p95", "p99", "max"))
    r["match_gpu"] = all(abs(r["gpu_excl"][k] - s_rep["gpu"][k]) < 1e-6 for k in ("p50", "p95", "p99", "max"))
    r["gate_8_9_pass"] = (r["cpu"]["p95"] <= 8.9 and r["gpu_excl"]["p95"] <= 8.9)
    print(name, r["eye"], "cpu", {k: round(v, 3) for k, v in r["cpu"].items()}, "gpu", {k: round(v, 3) for k, v in r["gpu_excl"].items()},
          "le0", r["gpu_le0"], "ge1000", r["gpu_ge1000"], r["gpu_ge1000_values"], "dp95(with0-without)", round(r["p95_with_zeros_minus_without"], 4),
          "match", r["match_cpu"], r["match_gpu"], [(x["frames"], round(x["realSeconds"], 2)) for x in runs])

# 機械の様子
for c in mach["conds"]:
    s = c.get("samples", [])
    cpu = [x["cpuTotalPct"] for x in s]
    res.setdefault("machine", {})[c["name"]] = dict(n=len(s), cpu_mean=float(np.mean(cpu)) if cpu else None, cpu_max=max(cpu) if cpu else None,
                                                    hython=sum(1 for x in s if x.get("hython")), gpu_util_mean=float(np.mean([x["gpuUtilPct"] for x in s])) if s else None,
                                                    exit=c.get("exitCode"), killed=c.get("killed"))
print(res["machine"])
jsave(OUT + "/k_timing.json", res)
