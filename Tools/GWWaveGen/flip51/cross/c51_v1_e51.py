# -*- coding: utf-8 -*-
"""FLIP51 crossing (2026-10-17, Claude): the frozen e51 target metrics on FLIP45 V1 (Fochesato 2007 flat-bed focused breaker, T 7.004 s,
h 20 m, +-45 deg fan, dp 0.5 m) as the measured anchor of a steepness-limited 3D breaker at T 7 s (read only on FLIP45 records).
Instants: onset = ana.json onset frame 1330; max = largest Hc in [onset - 3 s, onset + 1.5 s]; tbest = smallest miss there with Hc >= 0.6 x 6.19 m."""
import sys, json
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip51")
import numpy as np
import e51_metrics as EM
rd = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP45/runs/V1"
a = json.load(open(rd + "/ana.json", encoding="utf8")); eta0 = float(a["still_level_offset_m"])
xwin = (242.5 - 60, 242.5 + 35); avail = EM.frames_available(rd); rows = []
for f in range(1330 - 72, 1330 + 37):
    if f not in avail: continue
    m = EM.frame_metrics(rd, f, xwin, eta0, with_section=True)
    if not m or "W50" not in m: continue
    m["target_miss"], m["target_miss_per"] = EM.score_vs_target(m); rows.append(m)
on = [r for r in rows if r["frame"] == 1330][0]; mx = max(rows, key=lambda r: r["Hc"])
tb = min([r for r in rows if r["Hc"] >= 0.6 * 6.19], key=lambda r: r["target_miss"])
K = ["frame", "Hc", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "Lx50", "A50", "face_deg", "concavity", "back_deg", "target_miss"]
out = dict(doc=__doc__, eta0=eta0, onset={k: on.get(k) for k in K}, max={k: mx.get(k) for k in K}, tbest={k: tb.get(k) for k in K})
json.dump(out, open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP51/cross/v1_e51.json", "w", encoding="utf8"), indent=1, default=float)
for nm in ("onset", "max", "tbest"):
    print(nm, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out[nm].items()})
