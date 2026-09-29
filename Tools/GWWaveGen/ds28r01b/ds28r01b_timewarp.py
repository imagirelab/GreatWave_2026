# -*- coding: utf-8 -*-
"""設計28修正01 試行B：既定の時間曲線 τ(t) を変種ごとに作る（設計27 の ds27_timewarp.py の式のまま）。

D31 (a) の形（実時間 → S で d1 = 1 s かけて 0.5 倍 → 0.5 倍の一定 → 0.4 s の S で止め、t* = 12.0 s で 2 s 保持）と、設計26 §3.2 の規則
「0.5 倍へ着くのは唇先が最初に頂点に着く時刻」はそのまま。唇先の頂点は、その変種のパッケージ（ds27_gates.Package の Hermite、240 Hz）で、
巻きの行すべての唇先（K* の唇先の列）の τ ≥ −4 s の最高点の時刻の最も早いものとする（設計26 では生成器から −1.432 s）。
代案（実時間のまま t* で瞬間に止める）は設計27 の Tools/GWWaveGen/ds27/timewarp_alt.json をそのまま使う（同じ表なので書かない）。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01b/ds28r01b_timewarp.py --variant V75 [--package Unity/Build/Design/28R01B/V75/art_on]
出力：Tools/GWWaveGen/ds28r01b/timewarp_default_<変種>.json（schema は設計27 と同じ GreatWave.DS27.timewarp/1。Unity の再生器は -WarpFile で読む）。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402
import ds27_timewarp as TW  # noqa: E402

REPO = DG.REPO


def earliest_apex(pkdir, hz=240, t0=-4.0):
    ks = DG.KStar()
    pk = DG.Package(pkdir, ks)
    rows = np.array(ks.curled_idx, int)
    cols = ks.tip_col[rows]
    taus = np.round(np.arange(t0, 1e-9, 1.0 / hz), 9)
    taus[-1] = 0.0
    Y = np.empty((len(taus), len(rows)))
    for k, tv in enumerate(taus):
        X = pk.local(float(tv))
        Y[k] = X[rows, cols, 1]
    kap = np.argmax(Y, 0)
    tap = taus[kap]
    # t* まで上がり続ける行（頂点が t* の行）は除く
    ok = kap < len(taus) - 2
    i = int(np.argmin(np.where(ok, tap, np.inf)))
    return float(tap[i]), int(rows[i]), dict(rows=int(len(rows)), rows_rising_to_tstar=int((~ok).sum()),
                                              apex_tau_p10=float(np.percentile(tap[ok], 10)), apex_tau_median=float(np.median(tap[ok])),
                                              main_row_apex=float(tap[list(rows).index(ks.main_row)]), peak_row_apex=float(tap[list(rows).index(ks.peak_row)]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--package", default=None)
    a = ap.parse_args()
    R = json.load(open(os.path.join(HERE, "ds28r01b_params.json"), encoding="utf-8"))["timewarp"]
    pkdir = a.package or os.path.join(REPO, "Unity", "Build", "Design", "28R01B", a.variant, "art_on")
    tau_a, row, info = earliest_apex(pkdir)
    d1, r0, tf = float(R["d1"]), float(R["r0"]), float(R["tf"])
    tau_b = -r0 * tf / 2.0
    ta = (TW.T_STAR - tf) - (tau_b - tau_a) / r0
    t1 = ta - d1
    kw = dict(t1=round(t1, 6), d1=d1, r0=r0, tf=tf)
    t = np.round(np.arange(0, int(round(TW.T_END * TW.HZ)) + 1) / TW.HZ, 9)
    tau = TW.tau_default(t, **kw)
    tau_ramp_start = float(np.interp(t1, t, tau))
    info_all = dict(t1=kw["t1"], d1=d1, r0=r0, tf=tf, hold_s=float(R["hold_s"]), tau_at_t0_default=round(float(tau[0]), 6),
                    slow_reached_t=round(ta, 6), slow_reached_tau=round(tau_a, 6), slow_reached_rule_ja="その変種の唇先が最初に頂点に着く τ（巻きの行すべて）",
                    earliest_apex_row=row, apex_stats=info, tau_at_ramp_start=round(tau_ramp_start, 6), freeze_start_t=TW.T_STAR - tf,
                    apparent_g_mps2=9.81 * r0 ** 2, design26_default=dict(t1=7.936, tau_at_t0=-10.118, slow_reached_tau=-1.432),
                    package=os.path.relpath(pkdir, REPO).replace("\\", "/"), package_pos_sha256=DG.sha256_file(os.path.join(pkdir, "ds27_pos_rgba16.bin")))
    J = {"schema": "GreatWave.DS27.timewarp/1", "id": "default_ds28r01b_%s" % a.variant,
         "note_ja": "設計28修正01 試行B（%s）の既定：実時間 → 1 s で 0.5 倍（唇先が最初に頂点に着く τ %.3f s に着く）→ 0.5 倍 → 0.4 s で止め、t* = 12 s で 2 s 保持" % (a.variant, tau_a),
         "t_star_s": TW.T_STAR, "hz": TW.HZ, "params": info_all,
         "t": [round(float(v), 9) for v in t], "tau": [round(float(v), 9) for v in tau]}
    p = os.path.join(HERE, "timewarp_default_%s.json" % a.variant)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(J, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    assert abs(float(np.interp(TW.T_STAR, t, tau))) < 1e-9 and np.all(np.diff(tau) >= -1e-12)
    print(json.dumps(dict(file=p, info=info_all), ensure_ascii=False))


if __name__ == "__main__":
    main()
