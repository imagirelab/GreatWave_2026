# -*- coding: utf-8 -*-
"""5b. 24 コマ/秒の切り替わり（見せるコマが変わる Unity のフレーム）で、CPU・GPU の時間が長くなっていないか。
各回の計算の時刻を simStart ＋ dt の累積で近似し、コマの番号が変わったフレームとそれ以外を分けて数える。
出力：out/k_timing_switch.json"""
import numpy as np
from k_lib import *

D = RT + "/verify/timing/c7_1"
res = {}
for name in ("proxy2000", "proxy2064", "proxy2800", "desk1080"):
    d = jload(D + f"/{name}.json")
    sw_c, ot_c, sw_g, ot_g, long_sw, long_all = [], [], [], [], 0, 0
    for r in d["runs"]:
        dt = np.array(r["dtMs"]) / 1000.0
        t = r["simStart"] + np.cumsum(dt) - dt[0]
        k = np.floor((t - T0) * FPS + 1e-9).astype(int)
        sw = np.r_[False, np.diff(k) != 0]
        c = np.array(r["cpuMs"]); g = np.array(r["gpuMs"])
        sw_c += list(c[sw]); ot_c += list(c[~sw])
        gs = g[sw]; go = g[~sw]
        sw_g += list(gs[(gs > 0) & (gs < 1000)]); ot_g += list(go[(go > 0) & (go < 1000)])
        long_all += int((c > 11.1).sum()); long_sw += int(((c > 11.1) & sw).sum())
    q = lambda a: dict(n=len(a), p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), p99=float(np.percentile(a, 99)), max=float(np.max(a)))
    res[name] = dict(cpu_switch=q(sw_c), cpu_other=q(ot_c), gpu_switch=q(sw_g), gpu_other=q(ot_g), cpu_over_11_1_all=long_all, cpu_over_11_1_at_switch=long_sw)
    print(name, {k: ({kk: round(vv, 3) for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in res[name].items()})
jsave(OUT + "/k_timing_switch.json", res)
