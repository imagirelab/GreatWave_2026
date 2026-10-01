# -*- coding: utf-8 -*-
"""仕上げ28：関門 P13 の (2)（地面の二階差分、30 Hz、物理の時刻 τ = −m/30、巻きの行の全点、上限 0.0218 m = 2g）を越えた点の分布を数える。
関門の検査器（ds27_gates.py の acc30）と同じ量を、包み（pl28_f71_geom.Pkg：16 bit ＋ 精度の層、再生器と同じ Hermite、地面 = 局所 ＋ O(τ)）
から全部の点について作り、列の帯・行・時刻ごとの越えた数と最大を書く（関門の値は最大の 1 点だけなので、どこを直すかを決めるため）。
巻きの行は関門の検査器の K*′（ds28r01d_gates の写し）から読む代わりに、--rows で渡すか、既定では全部の行を数える。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_acc30_map.py --package <包み> --out <json> [--fine 0|1] [--rows 14,236]
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl28_f71_geom as GM  # noqa: E402

LIM = 2 * 9.81 / 900.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fine", type=int, default=0, help="0：関門の既定と同じ 16 bit の読み、1：精度の層つき")
    ap.add_argument("--rows", default="", help="数える行の範囲 a,b（両端を含む）")
    a = ap.parse_args()
    pk = GM.Pkg(a.package)
    nv, nu = pk.nv, pk.nu
    r0, r1 = (0, nv - 1) if not a.rows else [int(x) for x in a.rows.split(",")]
    K = int(np.floor(-pk.knots[0] * 30 + 1e-6))
    taus = -np.arange(K, -1, -1) / 30.0
    prev = []
    cnt = np.zeros((nv, nu), np.int32)
    mx = np.zeros((nv, nu))
    by_tau = []
    for tau in taus:
        X = pk.world(float(tau), fine=bool(a.fine)).reshape(nv, nu, 3)
        prev.append(X)
        if len(prev) == 3:
            d2 = np.linalg.norm(prev[2] - 2 * prev[1] + prev[0], axis=-1)
            d2[:r0] = 0
            d2[r1 + 1:] = 0
            over = d2 > LIM
            cnt += over
            mx = np.maximum(mx, d2)
            by_tau.append((round(float(tau) - 1 / 30.0, 4), int(over.sum()), float(d2.max())))
            prev.pop(0)
    bands = {"back_foot_cols_0_30": (0, 30), "back_31_89": (31, 89), "crest_lip_90_200": (90, 200), "tube_201_313": (201, 313),
             "front_314_378": (314, 378), "front_foot_379_399": (379, 399)}
    res = dict(package=os.path.relpath(pk.dir, GM.REPO).replace("\\", "/"), fine=bool(a.fine), limit_m=LIM, rows=[r0, r1], frames=len(taus),
               max_m=float(mx.max()), at=[int(x) for x in np.unravel_index(int(mx.argmax()), mx.shape)],
               vertex_frames_over=int(cnt.sum()), vertices_over=int((cnt > 0).sum()),
               bands={k: dict(vertex_frames_over=int(cnt[:, c0:c1 + 1].sum()), max_m=round(float(mx[:, c0:c1 + 1].max()), 5),
                              at=[int(x) for x in np.unravel_index(int(mx[:, c0:c1 + 1].argmax()), mx[:, c0:c1 + 1].shape)])
                      for k, (c0, c1) in bands.items()},
               top_cols=[(int(c), int(cnt[:, c].sum()), round(float(mx[:, c].max()), 4)) for c in np.argsort(-cnt.sum(0))[:15]],
               top_rows=[(int(r), int(cnt[r].sum()), round(float(mx[r].max()), 4)) for r in np.argsort(-cnt.sum(1))[:15]],
               top_tau=sorted(by_tau, key=lambda x: -x[1])[:15], tau_with_over=[x[0] for x in by_tau if x[1] > 0])
    res["tau_range_over"] = [min(res["tau_with_over"]), max(res["tau_with_over"])] if res["tau_with_over"] else None
    res["frames_over"] = len(res["tau_with_over"])
    del res["tau_with_over"]
    os.makedirs(os.path.dirname(GM.absrepo(a.out)), exist_ok=True)
    np.savez_compressed(GM.absrepo(a.out).replace(".json", ".npz"), cnt=cnt, mx=mx)
    with open(GM.absrepo(a.out), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("top_tau",)}, ensure_ascii=False, indent=0)[:2500])
    print("top_tau", res["top_tau"][:10])


if __name__ == "__main__":
    main()
