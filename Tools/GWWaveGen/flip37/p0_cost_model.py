# -*- coding: utf-8 -*-
"""P0 の計算の重さの見積もり（cost model）を runs.jsonl から作る（py -3.10）。
1 コマの時間 ≈ a × 粒子数（百万）+ b × 格子数（百万） を、成功した計算（水が落ちなかったもの）で最小二乗に合わせる。
メモリーは 粒子 1 個あたりと格子 1 個あたりで同じく合わせる。
使い方: py -3.10 p0_cost_model.py <runs.jsonl> <run_id,...> <out.json>
"""
import json, sys
import numpy as np

rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf8") if l.strip()]
ids = sys.argv[2].split(",")
last = {}
for r in rows:  # 同じ run_id が 2 回ある時は後の行（やり直し）を使う
    if r["run_id"] in ids and "info" in r:
        last[r["run_id"]] = r
use = [last[i] for i in ids if i in last]
X, yw, ym, tab = [], [], [], []
for r in use:
    res = r["info"].get("res_last") or r["info"].get("res_first")
    cells = res[0] * res[1] * res[2] / 1e6
    # 粒子数は最初のコマ（帯だけ）ではなく、計算中の代表値（最後のコマ）を使う
    parts = r["particles_last"] / 1e6
    X.append([parts, cells]); yw.append(r["wall_per_frame_median_s"]); ym.append(r["rss_peak_gb"])
    tab.append({"run_id": r["run_id"], "particles_M": round(parts, 3), "cells_M": round(cells, 3),
                "wall_per_frame_s": r["wall_per_frame_median_s"], "rss_peak_gb": r["rss_peak_gb"],
                "frames": r["f_end_done"] - r["f_start"] + 1, "wall_total_s": r["wall_total_s"],
                "us_per_particle_frame": round(r["wall_per_frame_median_s"] / max(parts, 1e-9), 3)})
X = np.array(X); yw = np.array(yw); ym = np.array(ym)
out = {"runs": tab}
if len(X) >= 2:
    cw, *_ = np.linalg.lstsq(X, yw, rcond=None)
    cm, *_ = np.linalg.lstsq(np.c_[X, np.ones(len(X))], ym, rcond=None)
    out["wall_s_per_frame"] = {"per_M_particles": float(cw[0]), "per_M_cells": float(cw[1]),
                               "fit_resid_s": [float(v) for v in (X @ cw - yw)]}
    out["rss_gb"] = {"per_M_particles": float(cm[0]), "per_M_cells": float(cm[1]), "base": float(cm[2])}
print(json.dumps(out, indent=1, ensure_ascii=False))
json.dump(out, open(sys.argv[3], "w", encoding="utf8"), indent=1, ensure_ascii=False)
