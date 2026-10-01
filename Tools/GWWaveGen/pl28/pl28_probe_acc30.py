# -*- coding: utf-8 -*-
"""仕上げ28：関門 P13 の (2)（地面の二階差分 30 Hz、上限 0.0218 m = 2g）の原因の切り分け（仕上げ27 の引き継ぎの 1：名前の付いた値を
1 つずつ切った生成器で 30 Hz の二階差分を測る）。包みは作らない（生成器を 1 つのプロセスで作り、τ = −m/30 の地面の位置を直接測る）。

生成器は ds28p（仕上げ28 の値は切る = G_final と同じ式）。num_no_rebound_after_apex の格子はどの版でも切る（格子は動きごとに作り直しが
要るので、比べをそろえるため。基準の「base」も切った版）。値を 1 つずつ切った版と base の、列の帯ごとの越えた頂点×こまの数と最大を比べる。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_probe_acc30.py --kstar Unity/Build/Polish/28/kstar_p28 --variants base,back_width_retarget,... --out <json>
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for sub in ("ds27", "ds28", "ds28r01b", "ds28r01c", "ds28r01d", "ds28r01e", "ds28r01f", "ds28p"):
    sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", sub))

LIM = 2 * 9.81 / 900.0
BANDS = {"back_foot_0_30": (0, 30), "back_31_89": (31, 89), "crest_lip_90_200": (90, 200), "tube_201_313": (201, 313),
         "front_314_378": (314, 378), "front_foot_379_399": (379, 399)}


def run(kstar, name, t0, t1, rows):
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    import ds28p_model as MP
    off = ["upper_back_aspect", "far_hook_earlier", "no_rebound"]
    if name != "base":
        off.append(name)
    g = MP.Generator(kstar_dir=kstar, off=tuple(off), defer_no_rebound=True)
    g.set_layers(**{k: (v and k != name) for k, v in g.f_on.items()})
    taus = -np.arange(int(round(-t0 * 30)), int(round(-t1 * 30)) - 1, -1) / 30.0
    prev = []
    cnt = {k: 0 for k in BANDS}
    mx = {k: 0.0 for k in BANDS}
    worst = (0.0, None)
    for tau in taus:
        X = g.world(float(tau))[rows[0]:rows[1] + 1]
        prev.append(X)
        if len(prev) == 3:
            d2 = np.linalg.norm(prev[2] - 2 * prev[1] + prev[0], axis=-1)
            for k, (c0, c1) in BANDS.items():
                s = d2[:, c0:c1 + 1]
                cnt[k] += int((s > LIM).sum())
                mx[k] = max(mx[k], float(s.max()))
            i = np.unravel_index(int(d2.argmax()), d2.shape)
            if d2[i] > worst[0]:
                worst = (float(d2[i]), dict(row=int(i[0] + rows[0]), col=int(i[1]), tau=round(float(tau) - 1 / 30, 4)))
            prev.pop(0)
    return dict(name=name, off=off, frames=len(taus), vertex_frames_over=cnt, max_m={k: round(v, 5) for k, v in mx.items()},
                max_all_m=round(worst[0], 5), at=worst[1], vertex_frames_over_all=int(sum(cnt.values())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--variants", required=True)
    ap.add_argument("--t0", type=float, default=-7.0)
    ap.add_argument("--t1", type=float, default=0.0)
    ap.add_argument("--rows", default="48,198")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [int(x) for x in a.rows.split(",")]
    res = dict(limit_m=LIM, rows=rows, tau=[a.t0, a.t1], variants={})
    for nm in a.variants.split(","):
        t = time.time()
        r = run(a.kstar, nm, a.t0, a.t1, rows)
        r["seconds"] = round(time.time() - t, 1)
        res["variants"][nm] = r
        print(nm, r["vertex_frames_over_all"], r["max_all_m"], r["at"], r["vertex_frames_over"], flush=True)
        out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
