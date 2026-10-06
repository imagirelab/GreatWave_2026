# -*- coding: utf-8 -*-
"""P0 T1 の解析：静かな水の水面の揺れ（区域ごと）と粒子の分布（py -3.10、numpy）。
使い方: py -3.10 p0_analyze_still.py <run_dir>"""
import numpy as np, glob, os, sys, json
rd = sys.argv[1]
d = np.load(os.path.join(rd, "eta.npz"))
x, eta, t, npts = d["x"], d["eta"], d["t"], d["npts"]
zones = {"gen_0_140": (0, 140), "flat_140_420": (140, 420), "slope_420_556": (420, 556), "reef_556_706": (556, 706), "abs_706_806": (706, 806)}
out = {"zones": {}}
for k, (lo, hi) in zones.items():
    m = (x >= lo) & (x < hi)
    e = eta[:, m]
    e1 = e[24:]  # 1 秒以後
    out["zones"][k] = {
        "nan_frac": float(np.isnan(e).mean()),
        "max_abs_all": float(np.nanmax(np.abs(e))),
        "max_abs_after1s": float(np.nanmax(np.abs(e1))),
        "mean_last": float(np.nanmean(e[-1])),
        "std_space_last": float(np.nanstd(e[-1])),
        "max_abs_dev_from_mean_after1s": float(np.nanmax(np.abs(e1 - np.nanmean(e1, axis=1, keepdims=True)))),
    }
out["mean_level_series"] = [[float(t[i]), float(np.nanmean(eta[i, (x > 140) & (x < 706)]))] for i in range(0, len(t), 24)]
out["npts_series"] = [[float(t[i]), int(npts[i])] for i in range(0, len(t), 24)]
snaps = []
for f in sorted(glob.glob(os.path.join(rd, "snap_*.npz"))):
    s = np.load(f)
    y = s["y"]
    snaps.append({"file": os.path.basename(f), "n": int(s["n"]), "ymin": float(s["ymin"]),
                  "slice_n": int(len(y)), "slice_y_pct": [float(v) for v in np.percentile(y, [0, 5, 50, 95, 100])],
                  "frac_deeper_than_3m": float((y < -3.0).mean()), "frac_deeper_than_6m": float((y < -6.0).mean())})
out["snaps"] = snaps
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(rd, "analysis_still.json"), "w"), indent=1)
