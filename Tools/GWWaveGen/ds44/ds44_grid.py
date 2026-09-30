# -*- coding: utf-8 -*-
"""設計44：固定の軌道（numpy 版 ds44_model.Trajectory。C# の DS44Trajectory と同じ手順）を、引き継ぎの状態の格子で試す。

格子：範囲の中の位置 5 × 5（u は範囲の前後の縁から 2 m 内側まで、v ±23 m）× 船首の向き（原画の向き ±0・30・60・90・135・180°）× 速さ（0・1.2・2.4 m/s）= 750。
数える量：所要 T、首振りの速さの最大、原画の位置より前（u > 2 m）へ出る件数と最大の u、着いた時の向きのずれ。
範囲の前の縁を −10 m（設計15 の箱の前の縁）にした時と、ds44_steer.json の値（−25 m）の時を比べる（D44-1 の根拠）。
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds44_model as M  # noqa: E402


def run(P, u_front):
    fr = M.Frame(P)
    rows = []
    for u in np.linspace(P["range"]["uMin"] + 2, u_front - 2, 5):
        for v in np.linspace(-23, 23, 5):
            for dh in [0, 30, -30, 60, -60, 90, -90, 135, -135, 180]:
                for sp in [0.0, 1.2, 2.4]:
                    yaw = fr.yaw + dh
                    r = math.radians(yaw)
                    vel = sp * np.array([math.sin(r), math.cos(r)])
                    tr = M.Trajectory(P, fr.to_world(u, v), vel, yaw, 0.0, 0.0, fr)
                    ts = np.linspace(0, tr.T, 600)
                    ev = [tr.eval(t) for t in ts]
                    yr = np.abs([e[3] for e in ev]).max()
                    umax = max(fr.to_uv(e[0])[0] for e in ev)
                    rows.append([u, v, dh, sp, tr.T, tr.L, yr, max(e[5] for e in ev), abs(M.wrap_deg(ev[-1][2] - fr.yaw)), tr.arc_deg, umax])
    A = np.array(rows)
    return dict(u_front=u_front, cases=len(A), T_p50=float(np.percentile(A[:, 4], 50)), T_p95=float(np.percentile(A[:, 4], 95)), T_max=float(A[:, 4].max()),
                yawrate_p50=float(np.percentile(A[:, 6], 50)), yawrate_p95=float(np.percentile(A[:, 6], 95)), yawrate_max=float(A[:, 6].max()),
                yawrate_over_15=int((A[:, 6] > 15).sum()), speed_max=float(A[:, 7].max()), end_yaw_err_max_deg=float(A[:, 8].max()),
                ahead_of_painting_over_2m=int((A[:, 10] > 2).sum()), u_max=float(A[:, 10].max()), with_arc=int((A[:, 9] != 0).sum()))


if __name__ == "__main__":
    P = M.load_params()
    out = dict(note_ja=__doc__.strip(), params=os.path.relpath(M.PARAMS, M.REPO).replace("\\", "/"))
    out["range_front_minus25"] = run(P, P["range"]["uMax"])
    P2 = json.loads(json.dumps(P))
    P2["range"]["uMax"] = -10.0
    out["range_front_minus10"] = run(P2, -10.0)
    os.makedirs(M.OUT, exist_ok=True)
    with open(os.path.join(M.OUT, "ds44_trajectory_grid.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k.startswith("range")}, indent=1))
