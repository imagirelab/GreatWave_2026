# -*- coding: utf-8 -*-
"""仕上げ33：132・72 の細部込み（評価器の定義のままの読み、包絡の真値）の「爪のこぶ」がどこで 4 px を超えるかを調べる（記録・診断。numpy）。

評価器 23（Tools/PaintingTruth/evaluate.py）の Truth・labelled_hausdorff と同じ真値・同じ点の割り当てで、t* の ID 画像（af28r01_class_ids.png、
3840×2160 を 2×2 で平均）の空の境界の点ごとに、132・72 に割り当てられた描画の点 → 真値の距離と、真値 → 描画の距離を出し、4 px を超える所を
塊に分けて、描画の点が真値の空の中にある（＝描画が包絡より外へ出たこぶ）か外にある（＝描画が包絡に届かないへこみ）かを書く。
使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33_bumps.py <t28 の組のフォルダー（…/t28_claws）> <出力の json>
"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/PaintingTruth")
os.chdir(REPO)
import truthlib as T  # noqa: E402
import evaluate as EV  # noqa: E402


def main():
    run, out = sys.argv[1], sys.argv[2]
    truth = EV.Truth()
    ids = T.imread_rgb(os.path.join(run, "t28", "render", "af28r01_class_ids.png"))
    reg = EV.render_regions_ids(truth, ids, {"classes": {"sky": [255, 255, 255]}})
    sky = reg["sky"]
    rp = T.boundary_points(sky, truth.spec, truth.fmap)
    F = truth.fam["sky_envelope"]
    res = {"run": os.path.relpath(run, REPO).replace("\\", "/"), "items": {}}
    tsky = truth.cov["sky_envelope"]
    for tid in ("132", "72"):
        r, (d_all, assigned), worst = T.labelled_hausdorff(F["pts"], F["sel"][tid], rp)
        P = rp[assigned]
        d = d_all[assigned]
        bad = d > 4.0
        xi = np.clip(np.round(P[:, 0]).astype(int), 0, 1919)
        yi = np.clip(np.round(P[:, 1]).astype(int), 0, 1079)
        outside_env = tsky[yi, xi] > 0.5     # 描画の境界の点が真値の空の中 → 描画が包絡より外へ出ている
        Tt = F["pts"][F["sel"][tid]]
        d_tr, _ = T.nearest(Tt, rp)
        clusters = []
        idx = np.nonzero(bad)[0]
        if len(idx):
            Pb = P[idx]
            used = np.zeros(len(idx), bool)
            for k in range(len(idx)):
                if used[k]:
                    continue
                m = (np.hypot(Pb[:, 0] - Pb[k, 0], Pb[:, 1] - Pb[k, 1]) < 12) & ~used
                used |= m
                sel = idx[m]
                clusters.append({"x": round(float(P[sel, 0].mean()), 1), "y": round(float(P[sel, 1].mean()), 1), "n": int(len(sel)),
                                 "max_px": round(float(d[sel].max()), 3), "bump_out_of_envelope": bool(outside_env[sel].mean() > 0.5)})
        res["items"][tid] = {"max_px": round(r["max_px"], 4), "p95_px": round(r["p95_px"], 4), "max_render_to_truth": round(r["max_render_to_truth"], 4),
                             "max_truth_to_render": round(r["max_truth_to_render"], 4), "render_points_gt4": int(bad.sum()),
                             "render_points": int(len(d)), "truth_points_gt4": int((d_tr > 4).sum()), "truth_points": int(len(d_tr)),
                             "clusters_gt4": sorted(clusters, key=lambda c: -c["max_px"])}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for tid, e in res["items"].items():
        print(tid, e["max_px"], e["p95_px"], "r>4", e["render_points_gt4"], "/", e["render_points"], "t>4", e["truth_points_gt4"], "/", e["truth_points"])
        for c in e["clusters_gt4"][:12]:
            print("   ", c)


if __name__ == "__main__":
    main()
