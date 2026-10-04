# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照モデルの側で、主役波と同じ定義の大きさ（H・縁の長さ L・幅 W）を測る（数だけ）。
s1_crown.py（開く半径 0.42 m）の一時の結果の胴の頂の線を使う。出力：study/s1_ref_dims.json。
定義（s1_hero_dims.py と同じ）：L = 頂の線（高さは 1 m、平面は 3 m の窓でならす）の 3 次元の長さ（頂の高さ ≥ 0.4 H の最も長い区間）、
W(f) = 頂の高さ ≥ f H の最も長い区間の c の幅。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_obj as SO  # noqa: E402
from s1_hero_dims import smooth_on_c, arclen  # noqa: E402

SEA_Y = 1.1982310754126466


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "_v06"
    R = json.load(open(SO.CACHE_DIR + "/tmp_crown_raw%s.json" % tag))
    c = np.array(R["c"])
    ty = np.array(R["body_top_y"], float) - SEA_Y
    ta = np.array(R["body_top_a"], float)
    oy = np.array(R["occ_top_y"], float) - SEA_Y
    ok = np.isfinite(ty)
    c, ty, ta, oy = c[ok], ty[ok], ta[ok], oy[ok]
    H = float(ty.max())
    res = {"tag": tag, "r_open_m": R["r_open_m"], "H_ref_body_m": H, "H_ref_incl_fingers_m": float(np.nanmax(oy)),
           "c_at_H": float(c[int(np.argmax(ty))]), "sea_y": SEA_Y}
    for frac in (0.25, 0.4, 0.5, 0.75):
        s = ty >= frac * H
        idx = np.nonzero(s)[0]
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        r = max(runs, key=len)
        cc = c[r]
        ys = smooth_on_c(cc, ty[r], 1.0)
        as_ = smooth_on_c(cc, ta[r], 3.0)
        P = np.stack([as_, ys, cc], 1)
        res["H_ge_%.2f" % frac] = {"c_range": [float(cc.min()), float(cc.max())], "dc_m": float(cc.max() - cc.min()),
                                    "rim_len_3d_m": arclen(P), "rim_len_cy_m": arclen(P[:, 1:])}
    # 前への張り出し：手の大きさ（半径 0.85 m）で開いた胴の、各 c の最も前の点（高さ 10〜22 m）と、頂の a（3 m の窓）の差
    R2 = json.load(open(SO.CACHE_DIR + "/tmp_crown2_raw_m05b.json"))
    c2 = np.array(R2["c"])
    ta2 = np.array(R2["body_top_a"], float)
    ty2 = np.array(R2["body_top_y"], float) - SEA_Y
    am = np.array([R2["body_amax_at_y"][k] for k in sorted(R2["body_amax_at_y"])], float)
    amax = np.full(len(c2), np.nan)
    for i in range(len(c2)):
        col = am[:, i]
        if np.isfinite(col).any():
            amax[i] = np.nanmax(col)
    okc = np.isfinite(ta2)
    tas2 = smooth_on_c(c2[okc], ta2[okc], 3.0)
    ov = amax[okc] - tas2
    sel = np.isfinite(ov) & (ty2[okc] >= 0.4 * H)
    res["front_overhang_m"] = {"def": "胴（半径 0.85 m で開いた体）の各 c の最も前の点の a − 頂の a（3 m の窓）。頂の高さ ≥ 0.4 H の c",
                               "p10": float(np.percentile(ov[sel], 10)), "p50": float(np.percentile(ov[sel], 50)), "p90": float(np.percentile(ov[sel], 90))}
    json.dump(res, open(SO.STUDY + "/s1_ref_dims.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
