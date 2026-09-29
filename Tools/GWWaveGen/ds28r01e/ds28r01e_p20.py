# -*- coding: utf-8 -*-
"""設計28修正01 試行E：名前の付いた値ごとの大きさ（P20：その値だけを切った生成器との、頂点の差の最大）を測る。

試行D の ds28r01d_p20.py と同じ測り方（τ −9.5〜−3 の 0.25 s おきと −3〜0 の 0.05 s おきの局所座標の差の最大と場所）を、試行E の生成器で行う。
名前：lean_with_height（E1）・tower_peak_off（E1 の塔を切る部分）・curl_lead（E2）・back_hold_water（E6）、時間曲線 timewarp（D との τ(t) の差）。
使い方（リポジトリの根で。名前ごとに別のプロセスで並べてよい）：
  py -3.10 -B Tools/GWWaveGen/ds28r01e/ds28r01e_p20.py --name curl_lead --out Unity/Build/Design/28R01E/p20/curl_lead.json
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DSD = os.path.abspath(os.path.join(HERE, "..", "ds28r01d"))
for p in (DSD, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import ds28r01d_p20 as PD  # noqa: E402

REPO = PD.REPO


def gen_diff(name, kstar):
    import ds28r01e_model as ME
    t0 = time.time()
    g1 = ME.Generator("art_on", kstar_dir=kstar)
    g0 = ME.Generator("art_on", kstar_dir=kstar, off=[name])
    worst = dict(m=0.0)
    per_tau = {}
    for tau in PD.taus():
        d = np.linalg.norm(g1.local(float(tau)) - g0.local(float(tau)), axis=-1)
        k = int(np.argmax(d))
        r, c = divmod(k, d.shape[1])
        per_tau["%+.2f" % tau] = round(float(d.max()), 4)
        if d.max() > worst["m"]:
            worst = dict(m=float(d.max()), row=int(r), col=int(c), tau=float(tau), c_m=float(g1.K.c[r]))
    return dict(name=name, max_vertex_diff_m=round(worst["m"], 4), at=worst, per_tau=per_tau, seconds=round(time.time() - t0, 1),
                variant_on=g1.variant, variant_off=g0.variant)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kstar", default="Unity/Build/Design/28R01D/kstar_foot")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.name == "timewarp":
        res = PD.warp_diff("Tools/GWWaveGen/ds28r01e/timewarp_default_E.json", "Tools/GWWaveGen/ds28r01d/timewarp_default_D.json")
        res["name"] = "ds_timewarp_e"
        res["note_ja"] = "τ(t) の差（同じ画面の時刻で、E − D）と速さの範囲（止める区間の前。rate_range_C1 の欄は D の値）"
    else:
        res = gen_diff(a.name, a.kstar)
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "per_tau"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
