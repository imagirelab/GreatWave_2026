# -*- coding: utf-8 -*-
"""P0 の再開の確かめ：途中保存から続けた計算（B）と、続けずに計算した計算（A）の、重なるコマの水面 η(x) と粒子数を比べる。
使い方: py -3.10 p0_analyze_resume.py <A_dir> <B_dir> [out.json]"""
import numpy as np, json, sys, os
A = np.load(os.path.join(sys.argv[1], "eta.npz")); B = np.load(os.path.join(sys.argv[2], "eta.npz"))
fa, fb = list(A["frames"]), list(B["frames"])
common = [f for f in fb if f in fa]
res = {"frames_B": [int(fb[0]), int(fb[-1])], "frames_A": [int(fa[0]), int(fa[-1])], "common": [int(f) for f in common], "per_frame": []}
for f in common:
    ea = A["eta"][fa.index(f)]; eb = B["eta"][fb.index(f)]
    m = ~(np.isnan(ea) | np.isnan(eb))
    d = np.abs(ea[m] - eb[m])
    res["per_frame"].append({"frame": int(f), "max_abs_diff_m": float(d.max()), "mean_abs_diff_m": float(d.mean()),
                             "npts_A": int(A["npts"][fa.index(f)]), "npts_B": int(B["npts"][fb.index(f)]),
                             "eta_std_A": float(np.nanstd(ea))})
# B の最初のコマの前後のなめらかさ：B の最初の 2 コマの差と、A の同じ所の差
if len(fb) > 2:
    d1 = np.nanmax(np.abs(B["eta"][1] - B["eta"][0]))
    res["B_first_step_max_change_m"] = float(d1)
    if fb[1] in fa and fb[0] in fa:
        res["A_same_step_max_change_m"] = float(np.nanmax(np.abs(A["eta"][fa.index(fb[1])] - A["eta"][fa.index(fb[0])])))
res["B_first_frame_wall_s"] = float(B["wall"][0])
print(json.dumps(res, indent=1))
if len(sys.argv) > 3:
    json.dump(res, open(sys.argv[3], "w"), indent=1)
