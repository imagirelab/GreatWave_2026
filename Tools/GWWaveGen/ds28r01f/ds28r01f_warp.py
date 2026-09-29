# -*- coding: utf-8 -*-
"""設計28修正01 試行F：時間曲線 τ(t) を K*′ の形成の時刻へ合わせる（ds_timewarp_f。E の ds_timewarp_e（P10H）の平行移動）。

E の時間曲線（ds28r01e_params.json の timewarp、候補 P10H）は、τ −4.2 → −3.0 で速さ 1 → 0.5 倍へ下げ、t* の前 1.2 s で止める。
この下げの区間は、E の古い K* で主断面の前面が鉛直になる時刻（Θ 90°、τ −3.038 s）の直前に置かれていた（小山 → C 字を画面で ≥ 3 s に
するため。Q17）。K*′（R1・R2）では同じ動きでも前面が鉛直になるのが早い（F_R1 の主断面で τ −4.01 s）ので、E の時間曲線のままでは
小山 → C 字が画面で 2.3 s に縮む。そこで、パッケージの主断面の Θ 90° の時刻 τ90 を測り（ds28r01d_review の sec_metrics、60 Hz の物理の時刻）、
E の速さの節点を Δ = τ90 − τ90_E だけずらす（形・止め・t* = 12 s は E と同じ。Δ > 0 にはしない）。E の K* を渡せば Δ ≈ 0。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_warp.py --package <パッケージ> --kstar <K* のフォルダー> --out <json>
出力：設計27 と同じ schema（GreatWave.DS27.timewarp/1、Unity の再生器は -WarpFile で読む）。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(GW, "..", ".."))
for sub in ("ds27", "ds28", "ds28r01", "ds28r01d", "ds28r01e"):
    p = os.path.join(GW, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

TAU90_E_MAIN = -3.038      # E の既定の検査（review_E.json の pace 159 の Theta90）


def absrepo(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import ds28r01d_gates as DGW
    import ds28r01d_review as RV
    import ds28r01e_review as RE
    import ds28r01e_timewarp as TW
    d = DGW.patch_kstar(a.kstar)
    ks = DGW.DG.KStar(d)
    pk = RE.FinePackage(absrepo(a.package), ks, fine=True)
    r = int(ks.main_row)
    taus = np.arange(-7.0, 0.0 + 1e-9, 1 / 60.0)
    A, Y = RV.sections_at(pk, ks, taus, (r,))
    jB, jE = 18, int(ks.j_E)
    tip = int(ks.tip_col[r]) if int(ks.tip_col[r]) >= 0 else 200
    Th = np.array([RV.sec_metrics(A[n, 0], Y[n, 0], jB, jE, tip)["Theta"] for n in range(len(taus))])
    t90 = RV.cross(taus, Th, 90.0)
    if t90 is None:
        raise SystemExit("[ds28r01f_warp] 主断面の前面が鉛直にならない（Θ 90°）")
    delta = min(float(t90) - TAU90_E_MAIN, 0.0)
    R = json.load(open(os.path.join(GW, "ds28r01e", "ds28r01e_params.json"), encoding="utf-8"))["timewarp"]
    name = R["default"]
    knots, t_star, tf = TW.params_of(R, name)
    knots_f = [(round(k + delta, 6), v) for k, v in knots]
    t, tau, info = TW.build(knots_f, t_star, tf)
    assert abs(float(np.interp(t_star, t, tau))) < 1e-9 and np.all(np.diff(tau) >= -1e-12)
    params = dict(name="ds_timewarp_f", base=R["name"], candidate=name, shift_s=round(delta, 4), tau90_main=round(float(t90), 4),
                  tau90_main_E=TAU90_E_MAIN, main_row=r, hold_s=round(14.0 - t_star, 4), package_pos_sha256=pk.pos_sha,
                  **TW.describe(t, tau, info, knots_f))
    J = {"schema": "GreatWave.DS27.timewarp/1", "id": "ds28r01f_%s" % os.path.basename(os.path.dirname(absrepo(a.package).rstrip("/\\"))),
         "note_ja": ("設計28修正01 試行F（ds_timewarp_f）：E の %s（%s）の速さの節点を %.3f s ずらした（主断面の前面が鉛直になる τ %.3f s を E の %.3f s に合わせる）。"
                     "t* = %.1f s の前の %.2f s で止め、t* から保持" % (name, R["name"], delta, t90, TAU90_E_MAIN, t_star, tf)),
         "t_star_s": t_star, "hz": TW.HZ, "params": params,
         "t": [round(float(v), 9) for v in t], "tau": [round(float(v), 9) for v in tau]}
    out = absrepo(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(J, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(json.dumps(dict(file=out, params=params), ensure_ascii=False))


if __name__ == "__main__":
    main()
