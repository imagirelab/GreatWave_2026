# -*- coding: utf-8 -*-
"""仕上げ28（焼き直しと Unity の描画）：設計30 の周りの海（near）の行 0 と、主役波の本体の境の輪（列 18・394 と行の端）のずれを測る（記録）。

設計30 は near の行 0 を F_final の主役波の境の輪（Unity/Build/Design/30/sea/near/ds30_ring0_index.json の 1230 点）そのものとして作った。
仕上げ28 は主役波の包みを G_p28b に替えたが、near は作り直していない（接続帯の作り直しは仕上げ30 の最初。計画 §5.1）。
この道具は、同じ τ で near の行 0 と、G_p28b（と F_final、対照）の境の輪の点の距離を測り、描画の継ぎ目に隙間・重なりが出るかを数で示す。
位置は精度の層つきの復号（pl28_f71_geom.Pkg、3 次 Hermite）。τ は near の節点の全部（242）。

使い方（リポジトリの根で。重い numpy の処理と同時に回さない。約 3 GB）:
    py -3.10 -B Tools/GWWaveGen/pl28/pl28u_seam.py [--out Unity/Build/Polish/28/unity/seam_near_ring.json]
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import pl28_f71_geom as FG  # noqa: E402

NEAR = "Unity/Build/Design/30/sea/near"
HEROES = {"F_final": "Unity/Build/Design/28R01F/F_final/art_on", "G_p28b": "Unity/Build/Polish/28/G_p28b/art_on",
          "G_p28rec": "Unity/Build/Polish/28/G_p28rec/art_on"}   # G_p28rec：仕上げ28 の回復で採った動き


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Unity/Build/Polish/28/unity/seam_near_ring.json")
    a = ap.parse_args()
    R = json.load(open(os.path.join(REPO, NEAR, "ds30_ring0_index.json"), encoding="utf-8"))
    loop = R["loop"]
    ncol = np.array([e["near_col"] for e in loop])
    hidx = np.array([e["hero_row"] * 400 + e["hero_col"] for e in loop])
    near = FG.Pkg(NEAR)
    taus = near.knots
    nearring = {}
    for t in taus:
        Pn = near.world(float(t)).reshape(near.nv, near.nu, 3)
        nearring[float(t)] = Pn[0, ncol]
    del near
    res = {"schema": "GreatWave.Polish28.seam_near_ring/1", "near": NEAR, "ring_points": int(len(loop)), "taus": int(len(taus)), "heroes": {}}
    for name, d in HEROES.items():
        pk = FG.Pkg(d)
        dist = np.zeros((len(taus), len(loop)))
        for i, t in enumerate(taus):
            P = pk.world(float(t))
            dist[i] = np.linalg.norm(P[hidx] - nearring[float(t)], axis=1)
        per_tau = dist.max(1)
        k = int(per_tau.argmax())
        j = int(dist[k].argmax())
        res["heroes"][name] = {
            "package": d, "pos_sha256": pk.pos_sha,
            "max_m": round(float(dist.max()), 5), "p99_m": round(float(np.percentile(dist, 99)), 5), "median_m": round(float(np.median(dist)), 6),
            "at_tstar_max_m": round(float(dist[-1].max()), 5),
            "worst": {"tau": float(taus[k]), "near_col": int(ncol[j]), "hero_row": int(hidx[j] // 400), "hero_col": int(hidx[j] % 400)},
            "points_over_0p05m_by_tau_max": int((dist > 0.05).sum(1).max()), "taus_with_any_over_0p05m": int(((dist > 0.05).sum(1) > 0).sum()),
            "points_over_0p5m_by_tau_max": int((dist > 0.5).sum(1).max()),
            "max_by_tau_sample": {("%.3f" % taus[i]): round(float(per_tau[i]), 4) for i in range(0, len(taus), max(1, len(taus) // 24))},
        }
        del pk
        print(name, json.dumps({k2: res["heroes"][name][k2] for k2 in ("max_m", "p99_m", "at_tstar_max_m", "worst")}, ensure_ascii=False), flush=True)
    res["note_ja"] = ("F_final は near の行 0 を作った元なので 0 に近いはず（対照）。G_p28b の値が、主役波を差し替えた描画の継ぎ目の隙間・重なりの大きさ"
                      "（周りの海は合わせ直していない。仕上げ30 の最初に作り直す）。")
    with open(os.path.join(REPO, a.out), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("PL28U_SEAM_DONE")


if __name__ == "__main__":
    main()
