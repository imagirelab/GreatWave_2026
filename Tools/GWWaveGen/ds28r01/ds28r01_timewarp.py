# -*- coding: utf-8 -*-
"""設計28修正01（T5）：既定の時間曲線 τ(t) を作り直す（設計27 の ds27_timewarp.py の式をそのまま使い、0.5 倍へ落とす時刻だけを変える）。

D31 の (a) の形（実時間 → S で d1 = 1 s かけて 0.5 倍 → 0.5 倍の一定 → 0.4 s の S で止め、t* = 12.0 s で 2 s 保持）はそのまま。
設計26 §3.2 の既定は 0.5 倍へ着くのが τ −1.432 s（唇先が最初に頂点に着く時刻）で、上昇の後半（実時間）と唇の伸び出し（0.5 倍）が
別の速さに見えた。この表は、峰の行の前面が鉛直を過ぎる前（τ −3.0 s。ds28r01_params.json の timewarp.slow_reached_tau_s）に
0.5 倍へ着く：t1 = 12 − tf − (−tf·r0/2 − τ_a)/r0 − d1。
代案（実時間のまま t* で瞬間に止める）は設計27 の Tools/GWWaveGen/ds27/timewarp_alt.json をそのまま使う（同じ表なので書かない）。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_timewarp.py
出力：Tools/GWWaveGen/ds28r01/timewarp_default.json（schema は設計27 と同じ GreatWave.DS27.timewarp/1。Unity の再生器は -WarpFile で読む）。
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, DS27)
import ds27_timewarp as TW  # noqa: E402


def params():
    R = json.load(open(os.path.join(HERE, "ds28r01_params.json"), encoding="utf-8"))["timewarp"]
    d1, r0, tf = float(R["d1"]), float(R["r0"]), float(R["tf"])
    tau_a = float(R["slow_reached_tau_s"])
    tau_b = -r0 * tf / 2.0
    ta = (TW.T_STAR - tf) - (tau_b - tau_a) / r0
    t1 = ta - d1
    return dict(t1=round(t1, 6), d1=d1, r0=r0, tf=tf), float(R["hold_s"]), tau_a


def main():
    kw, hold, tau_a = params()
    t = np.round(np.arange(0, int(round(TW.T_END * TW.HZ)) + 1) / TW.HZ, 9)
    tau = TW.tau_default(t, **kw)
    info = dict(t1=kw["t1"], d1=kw["d1"], r0=kw["r0"], tf=kw["tf"], hold_s=hold, tau_at_t0_default=round(float(tau[0]), 6),
                slow_reached_t=round(kw["t1"] + kw["d1"], 6), slow_reached_tau=tau_a, freeze_start_t=TW.T_STAR - kw["tf"],
                apparent_g_mps2=9.81 * kw["r0"] ** 2, design26_default=dict(t1=7.936, tau_at_t0=-10.118, slow_reached_tau=-1.432))
    J = {"schema": "GreatWave.DS27.timewarp/1", "id": "default_ds28r01",
         "note_ja": "設計28修正01（Q13・T5）の既定：実時間 → 1 s で 0.5 倍（τ −3.0 s に着く）→ 0.5 倍 → 0.4 s で止め、t* = 12 s で 2 s 保持。上昇の後半と唇の伸び出しを同じ 0.5 倍で見せる",
         "t_star_s": TW.T_STAR, "hz": TW.HZ, "params": info,
         "t": [round(float(v), 9) for v in t], "tau": [round(float(v), 9) for v in tau]}
    p = os.path.join(HERE, "timewarp_default.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(J, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    # 検査：t* = 12.0 s で τ = 0、τ(t) は単調
    assert abs(float(np.interp(TW.T_STAR, t, tau))) < 1e-9 and np.all(np.diff(tau) >= -1e-12)
    print(json.dumps(dict(file=p, info=info), ensure_ascii=False))


if __name__ == "__main__":
    main()
