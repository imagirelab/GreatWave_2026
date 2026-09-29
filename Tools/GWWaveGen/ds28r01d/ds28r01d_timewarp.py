# -*- coding: utf-8 -*-
"""設計28修正01 試行D：時間曲線 τ(t)（名前の付いた値 ds_timewarp_lean_slow。Q17 の F2）。

速さ ρ(τ) = dτ/dt を τ の節点の間の smootherstep でつなぐ（ds28r01d_params.json の timewarp.rate_knots_tau。既定は
τ −5.4 まで 1 倍 → −4.2 で 0.65 倍 → −3.1 まで 0.65 倍 → −2.4 で 0.5 倍 → その後 0.5 倍）。t = 12 − 0.4 s から t* = 12 s までは
設計27 と同じ止め方（τ = τ_f + r0·tf·(x − (x³ − x⁴/2))、x = (t − 11.6)/0.4）で止め、12〜14 s は τ = 0 で保持。
作業場所の q17/pace/proto_eval.py の build と同じ式（表の数値も同じになる）。出力の schema は設計27 と同じ GreatWave.DS27.timewarp/1
（Unity の再生器は -WarpFile で読む）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_timewarp.py [--out <json>] [--package <パッケージ>]
"""
import argparse
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HZ = 240
T_END = 14.0


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x ** 3 * (x * (6 * x - 15) + 10)


def rho_of(knots, tau):
    tau = np.asarray(tau, float)
    r = np.full_like(tau, knots[0][1])
    for (a, ra), (b, rb) in zip(knots[:-1], knots[1:]):
        m = tau >= a
        r = np.where(m, ra + (rb - ra) * ss((tau - a) / (b - a)), r)
    return r


def build(knots, t_star=12.0, tf=0.4):
    r0 = knots[-1][1]
    tau_f = -r0 * tf / 2.0
    tg = np.linspace(-14.0, tau_f, 200001)
    inv = 1.0 / rho_of(knots, tg)
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(tg))])
    t_of = (t_star - tf) - (cum[-1] - cum)
    t = np.round(np.arange(0, int(round(T_END * HZ)) + 1) / HZ, 9)
    tau = np.interp(t, t_of, tg)
    m = (t >= t_star - tf) & (t < t_star)
    x = (t[m] - (t_star - tf)) / tf
    tau[m] = tau_f + r0 * tf * (x - (x ** 3 - x ** 4 / 2))
    tau[t >= t_star] = 0.0
    return t, tau, dict(r0=r0, tau_f=tau_f, tau_at_t0=float(tau[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "timewarp_default_D.json"))
    ap.add_argument("--params", default=os.path.join(HERE, "ds28r01d_params.json"))
    ap.add_argument("--package", default=None, help="記録のためのパッケージ（pos の SHA-256 を書く）")
    a = ap.parse_args()
    R = json.load(open(a.params, encoding="utf-8"))["timewarp"]
    knots = [tuple(map(float, k)) for k in R["rate_knots_tau"]]
    t, tau, info = build(knots, float(R["t_star"]), float(R["tf"]))
    assert abs(float(np.interp(float(R["t_star"]), t, tau))) < 1e-9 and np.all(np.diff(tau) >= -1e-12)
    rate = np.gradient(tau, t)
    params = dict(name=R["name"], rate_knots_tau=[list(k) for k in knots], tf=float(R["tf"]), hold_s=float(R["hold_s"]), t_star=float(R["t_star"]),
                  tau_at_t0=round(info["tau_at_t0"], 6), r0=info["r0"], apparent_g_mps2_final=round(9.81 * info["r0"] ** 2, 4),
                  t_at_tau={("%.1f" % v): round(float(np.interp(v, tau[:int(11.6 * HZ)], t[:int(11.6 * HZ)])), 4) for v in (-5.4, -4.2, -3.1, -2.4, -1.0)},
                  rate_max_step_per_s=round(float(np.max(np.abs(np.gradient(rate, t)[: int(11.5 * HZ)]))), 4),
                  freeze_start_t=float(R["t_star"]) - float(R["tf"]))
    if a.package:
        import hashlib
        p = os.path.join(a.package if os.path.isabs(a.package) else os.path.join(REPO, a.package), "ds27_pos_rgba16.bin")
        if os.path.isfile(p):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
            params["package_pos_sha256"] = h.hexdigest()
    J = {"schema": "GreatWave.DS27.timewarp/1", "id": "default_ds28r01d_F2",
         "note_ja": "設計28修正01 試行D（ds_timewarp_lean_slow、Q17 の F2）：τ −5.4 まで 1 倍 → −4.2 で 0.65 倍 → −3.1 まで 0.65 倍 → −2.4 で 0.5 倍 → "
                    "t* = 12 s の前の 0.4 s で止め、2 s 保持",
         "t_star_s": float(R["t_star"]), "hz": HZ, "params": params,
         "t": [round(float(v), 9) for v in t], "tau": [round(float(v), 9) for v in tau]}
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(J, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(json.dumps(dict(file=out, params=params), ensure_ascii=False))


if __name__ == "__main__":
    main()
