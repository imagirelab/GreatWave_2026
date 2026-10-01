# -*- coding: utf-8 -*-
"""仕上げ28：側面 t 4〜6.5 s の「平らな頂の塊」（M10。28修正01 の最終の評審が粘土の正側面で見た形）を数で読む。

正側面の見え方（波峰線の向き c に沿って見る）は、全部の行の断面を進む向き a に重ねた上の包絡 env(a) = max_y（波の枠の局所座標）。
  plateau_95_m：env ≥ 0.95·max の a の長さ（平らな頂の長さ）。plateau_95_over_H はそれを最高の高さ H で割った値。
  front_run_80_m：最高点から前（a の大きい側）へ、env が 0.8·max に下がるまでの a の距離（小さい＝前の上の角が小さな半径で急に落ちる）
  back_run_80_m：同じく後ろへ 0.8·max まで（大きい＝背の上が長く平ら）
  loaf_index = back_run_80_m / max(front_run_80_m, 0.5)（大きいほど「前が切り立ち、背の上が長く平ら」な塊）
  crest_radius_m：最高点の前後 ±0.25H の包絡に当てはめた円の半径（頂の丸さ。大きい＝平ら）
使い方（包み）：py -3.10 -B Tools/GWWaveGen/pl28/pl28_loaf.py --tag F_final=<包み>|<時間曲線> ... --kstar-meta <meta.json> --out <json>
関数 loaf_metrics(X_local, t_travel) は生成器の試し（pl28_probe.py）からも使う。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl28_f71_geom as GM  # noqa: E402

TIMES = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]


def envelope(A, Y, da=0.1):
    a = A.ravel()
    y = Y.ravel()
    m = y > 0.05
    a, y = a[m], y[m]
    b = np.floor((a - a.min()) / da).astype(np.int64)
    env = np.full(b.max() + 1, -np.inf)
    np.maximum.at(env, b, y)
    xs = a.min() + (np.arange(len(env)) + 0.5) * da
    ok = np.isfinite(env)
    return xs[ok], env[ok]


def loaf_metrics(X, t_travel, sign=1.0):
    A = (X @ np.asarray(t_travel, float)) * sign
    Y = X[..., 1]
    xs, env = envelope(A, Y)
    k = int(np.argmax(env))
    H = float(env[k])
    pl = xs[env >= 0.95 * H]
    fr = xs[k:][env[k:] < 0.8 * H]
    bk = xs[:k][env[:k] < 0.8 * H]
    front = float(fr[0] - xs[k]) if fr.size else float("nan")
    back = float(xs[k] - bk[-1]) if bk.size else float("nan")
    sel = np.abs(xs - xs[k]) <= 0.25 * H
    x, y = xs[sel], env[sel]
    # 円の当てはめ（代数）
    Am = np.stack([x, y, np.ones_like(x)], 1)
    bb = -(x ** 2 + y ** 2)
    try:
        c = np.linalg.lstsq(Am, bb, rcond=None)[0]
        R = float(np.sqrt(max(c[0] ** 2 / 4 + c[1] ** 2 / 4 - c[2], 0.0)))
    except Exception:
        R = float("nan")
    return dict(H_m=round(H, 3), plateau_95_m=round(float(pl.max() - pl.min()), 3), plateau_95_over_H=round(float(pl.max() - pl.min()) / H, 4),
                front_run_80_m=round(front, 3), back_run_80_m=round(back, 3), loaf_index=round(back / max(front, 0.5), 3),
                crest_radius_m=round(R, 2), crest_radius_over_H=round(R / H, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", action="append", required=True, help="名前=包み|時間曲線")
    ap.add_argument("--kstar-meta", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    meta = json.load(open(GM.absrepo(a.kstar_meta), encoding="utf-8"))
    T = np.asarray(meta["frame"]["t_travel"], float)
    res = dict(schema="GreatWave.Polish28.loaf/1", times=TIMES, t_travel=T.tolist(), tags={})
    for s in a.tag:
        name, v = s.split("=", 1)
        pkd, wp = v.split("|")
        pk = GM.Pkg(pkd)
        W = json.load(open(GM.absrepo(wp), encoding="utf-8"))
        wt, wtau = np.asarray(W["t"], float), np.asarray(W["tau"], float)
        # 前 = 唇の側（a の大きい側）。t* の主断面で唇先が頂より前にあることを確かめて符号を決める
        X0 = pk.world(0.0) - np.array([np.interp(0.0, pk.ftau, pk.forg[:, k]) for k in range(3)])
        X0 = X0.reshape(pk.nv, pk.nu, 3)
        a0 = X0[164] @ T
        sign = 1.0 if a0[200] > a0[int(np.argmax(X0[164, 18:394, 1])) + 18] else -1.0
        rows = {}
        for t in TIMES:
            tau = float(np.interp(t, wt, wtau))
            X = (pk.world(tau) - np.array([np.interp(tau, pk.ftau, pk.forg[:, k]) for k in range(3)])).reshape(pk.nv, pk.nu, 3)
            rows["%.1f" % t] = dict(tau=round(tau, 4), **loaf_metrics(X, T, sign))
        res["tags"][name] = dict(package=pkd, warp=wp, sign=sign, by_t=rows)
        del pk
    os.makedirs(os.path.dirname(GM.absrepo(a.out)), exist_ok=True)
    with open(GM.absrepo(a.out), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for n, d in res["tags"].items():
        for t, m in d["by_t"].items():
            print(n, t, m)


if __name__ == "__main__":
    main()
