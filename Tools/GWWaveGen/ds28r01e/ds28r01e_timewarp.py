# -*- coding: utf-8 -*-
"""設計28修正01 試行E：時間曲線 τ(t)（E4 の止めの長さ・E5 の選び）。

形は試行D（ds28r01d_timewarp.py）と同じ：速さ ρ(τ) = dτ/dt を τ の節点の間の smootherstep でつなぎ、t* の前 tf 秒で止め
（τ = τ_f + r0·tf·(x − (x³ − x⁴/2))、x = (t − (t* − tf))/tf、τ_f = −r0·tf/2。速さは r0·(1 − smoothstep(x)) で 0 へ）、t* から 2 s 保持。
E で変えたのは tf（止めの長さ。Q16 の計画の J7 で ≥ 0.8 s）と、候補の節点の組（ds28r01e_params.json の timewarp.candidates）。
出力の schema は設計27 と同じ GreatWave.DS27.timewarp/1（Unity の再生器は -WarpFile で読む）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01e/ds28r01e_timewarp.py [--candidate <名前>] [--out <json>] [--package <パッケージ>]
  既定の候補は ds28r01e_params.json の timewarp.default、出力の既定は Tools/GWWaveGen/ds28r01e/timewarp_default_E.json。
"""
import argparse
import hashlib
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HZ = 240


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


def build(knots, t_star=12.0, tf=0.8, t_end=14.0, hz=HZ):
    """(t, τ, 情報)。knots = [(τ, 速さ), ...]（τ の順）。最後の速さ r0 のまま t* − tf まで進み、tf で止める。"""
    knots = [tuple(map(float, k)) for k in knots]
    r0 = knots[-1][1]
    tau_f = -r0 * tf / 2.0
    tg = np.linspace(-16.0, tau_f, 240001)
    inv = 1.0 / rho_of(knots, tg)
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(tg))])
    t_of = (t_star - tf) - (cum[-1] - cum)
    t = np.round(np.arange(0, int(round(t_end * hz)) + 1) / hz, 9)
    tau = np.interp(t, t_of, tg)
    m = (t >= t_star - tf) & (t < t_star)
    x = (t[m] - (t_star - tf)) / tf
    tau[m] = tau_f + r0 * tf * (x - (x ** 3 - x ** 4 / 2))
    tau[t >= t_star] = 0.0
    return t, tau, dict(r0=r0, tau_f=tau_f, tau_at_t0=float(tau[0]), t_star=t_star, tf=tf)


def params_of(R, name):
    C = R["candidates"][name]
    return [tuple(map(float, k)) for k in C["rate_knots_tau"]], float(C.get("t_star", R["t_star"])), float(C.get("tf", R["tf"]))


def describe(t, tau, info, knots):
    rate = np.gradient(tau, t)
    t_star, tf = info["t_star"], info["tf"]
    k_pre = t < t_star - tf - 0.1
    return dict(rate_knots_tau=[list(k) for k in knots], tf=tf, t_star=t_star, tau_at_t0=round(info["tau_at_t0"], 6), r0=info["r0"],
                apparent_g_mps2_final=round(9.81 * info["r0"] ** 2, 4), stop_start_t=round(t_star - tf, 4), stop_tau_f=round(info["tau_f"], 4),
                t_at_tau={("%.2f" % v): round(float(np.interp(v, tau[k_pre], t[k_pre])), 4) for v in (-5.4, -4.2, -3.1, -2.4, -1.0)
                          if tau[k_pre][0] <= v <= tau[k_pre][-1]},
                tau_at_t={("%.1f" % v): round(float(np.interp(v, t, tau)), 4) for v in (0.0, 3.0, 6.0, 8.0, 10.0, 11.0)},
                rate_max_step_per_s=round(float(np.max(np.abs(np.gradient(rate, t)[k_pre]))), 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--params", default=os.path.join(HERE, "ds28r01e_params.json"))
    ap.add_argument("--package", default=None, help="記録のためのパッケージ（pos の SHA-256 を書く）")
    a = ap.parse_args()
    R = json.load(open(a.params, encoding="utf-8"))["timewarp"]
    name = a.candidate or R["default"]
    knots, t_star, tf = params_of(R, name)
    t, tau, info = build(knots, t_star, tf)
    assert abs(float(np.interp(t_star, t, tau))) < 1e-9 and np.all(np.diff(tau) >= -1e-12)
    params = dict(name=R["name"], candidate=name, hold_s=round(14.0 - t_star, 4), **describe(t, tau, info, knots))
    if a.package:
        p = os.path.join(a.package if os.path.isabs(a.package) else os.path.join(REPO, a.package), "ds27_pos_rgba16.bin")
        if os.path.isfile(p):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
            params["package_pos_sha256"] = h.hexdigest()
    J = {"schema": "GreatWave.DS27.timewarp/1", "id": "ds28r01e_%s" % name,
         "note_ja": "設計28修正01 試行E（%s、候補 %s）：%s。t* = %.1f s の前の %.2f s で止め（E4）、t* から保持" % (R["name"], name, R["candidates"][name]["note_ja"], t_star, tf),
         "t_star_s": t_star, "hz": HZ, "params": params,
         "t": [round(float(v), 9) for v in t], "tau": [round(float(v), 9) for v in tau]}
    out = a.out or os.path.join(HERE, "timewarp_default_E.json" if name == R["default"] else "timewarp_%s.json" % name)
    out = out if os.path.isabs(out) else os.path.join(REPO, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(J, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(json.dumps(dict(file=out, params=params), ensure_ascii=False))


if __name__ == "__main__":
    main()
