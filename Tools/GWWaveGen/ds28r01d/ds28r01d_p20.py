# -*- coding: utf-8 -*-
"""設計28修正01 試行D：名前の付いた値ごとの大きさ（P20：その値だけを切った生成器との、頂点の差の最大）を測る。

生成器を直接 2 つ作り（すべて入り／1 つだけ切り）、τ −9.5〜0 の 0.25 s おき（と τ −3〜0 の 0.05 s おき）の局所座標の差の最大と、
その場所（行・列・τ）を書く。num_no_rebound_after_apex は生成器の記録（δ の最大）を使う。時間曲線（ds_timewarp_lean_slow）は形を変えない
ので、画面の時刻の割り付けの差（τ(t) の差の最大）を書く。K* の足の焼き直し（ds_kstar_foot_rebake）は、同じ a での断面の高さの差の最大。
使い方（リポジトリの根で。名前ごとに別のプロセスで並べてよい）：
  py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_p20.py --name near_trough --out Unity/Build/Design/28R01D/p20/near_trough.json
  py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_p20.py --name kstar_foot_rebake --out ...
  py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_p20.py --name timewarp --out ...
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds28r01d_kstar as KS  # noqa: E402

REPO = KS.REPO


def taus():
    a = np.round(np.arange(-9.5, -3.0, 0.25), 6)
    b = np.round(np.arange(-3.0, 1e-9, 0.05), 6)
    return np.concatenate([a, b])


def gen_diff(name, kstar, cache_dir):
    import ds28r01d_model as MDD
    t0 = time.time()
    g1 = MDD.Generator("art_on", kstar_dir=kstar, no_rebound_cache=os.path.join(cache_dir, "nr_full.npz") if cache_dir else None)
    g0 = MDD.Generator("art_on", kstar_dir=kstar, off=[name], no_rebound_cache=os.path.join(cache_dir, "nr_off_%s.npz" % name) if cache_dir else None)
    worst = dict(m=0.0)
    per_tau = {}
    for tau in taus():
        d = np.linalg.norm(g1.local(float(tau)) - g0.local(float(tau)), axis=-1)
        k = int(np.argmax(d))
        r, c = divmod(k, d.shape[1])
        per_tau["%+.2f" % tau] = round(float(d.max()), 4)
        if d.max() > worst["m"]:
            worst = dict(m=float(d.max()), row=int(r), col=int(c), tau=float(tau), c_m=float(g1.K.c[r]))
    return dict(name=name, max_vertex_diff_m=round(worst["m"], 4), at=worst, per_tau=per_tau, seconds=round(time.time() - t0, 1),
                variant_on=g1.variant, variant_off=g0.variant)


def upper_env(a, y, grid):
    """折れ線 (a, y) の、各 a での一番上の y（その a を横切る線分がなければ nan）。"""
    out = np.full(len(grid), -np.inf)
    for k in range(len(a) - 1):
        a0, a1 = a[k], a[k + 1]
        lo, hi = min(a0, a1), max(a0, a1)
        m = (grid >= lo) & (grid <= hi)
        if not m.any():
            continue
        if hi - lo < 1e-9:
            v = np.full(m.sum(), max(y[k], y[k + 1]))
        else:
            v = y[k] + (grid[m] - a0) / (a1 - a0) * (y[k + 1] - y[k])
        out[m] = np.maximum(out[m], v)
    out[~np.isfinite(out)] = np.nan
    return out


def foot_diff(kstar_new, kstar_old):
    Kn, Ko = KS.load(kstar_new), KS.load(kstar_old)
    out = dict(m=0.0)
    for r in range(Kn["A"].shape[0]):
        an, yn = Kn["A"][r], Kn["Y"][r]
        ao, yo = Ko["A"][r], Ko["Y"][r]
        j0 = 360
        # 前の部分（列 360〜）の断面の上の面を、同じ a で比べる
        grid = np.linspace(max(an[j0], ao[j0]), min(an[-1], ao[-1]), 600)
        d = np.abs(upper_env(an[j0:], yn[j0:], grid) - upper_env(ao[j0:], yo[j0:], grid))
        if np.nanmax(d) > out["m"]:
            out = dict(m=float(np.nanmax(d)), row=r, a=float(grid[int(np.nanargmax(d))]))
    return dict(name="ds_kstar_foot_rebake", max_section_height_diff_m=round(out["m"], 4), at=out,
                note_ja="同じ a での断面の上の面の高さの差の最大（列 360 より前の部分）。台座を取った分と前の谷の深さ")


def warp_diff(wD, wC):
    a = json.load(open(os.path.join(REPO, wD), encoding="utf-8"))
    b = json.load(open(os.path.join(REPO, wC), encoding="utf-8"))
    t = np.asarray(a["t"])
    ta, tb = np.asarray(a["tau"]), np.interp(t, np.asarray(b["t"]), np.asarray(b["tau"]))
    ra, rb = np.gradient(ta, t), np.gradient(tb, t)
    return dict(name="ds_timewarp_lean_slow", max_abs_tau_diff_s=round(float(np.max(np.abs(ta - tb))), 4),
                rate_range=[round(float(ra[: int(11.5 * 240)].min()), 4), round(float(ra.max()), 4)],
                rate_range_C1=[round(float(rb[: int(11.5 * 240)].min()), 4), round(float(rb.max()), 4)],
                tau_at_t0=[round(float(ta[0]), 4), round(float(tb[0]), 4)], note_ja="τ(t) の差（同じ画面の時刻で）と速さの範囲（止める区間の前）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kstar", default="Unity/Build/Design/28R01D/kstar_foot")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", default=None)
    a = ap.parse_args()
    if a.name == "kstar_foot_rebake":
        res = foot_diff(a.kstar, "Unity/Build/ArtFirst/26修正01/kstar")
    elif a.name == "timewarp":
        res = warp_diff("Tools/GWWaveGen/ds28r01d/timewarp_default_D.json", "Tools/GWWaveGen/ds28r01c/timewarp_default_C1.json")
    else:
        res = gen_diff(a.name, a.kstar, a.cache_dir)
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "per_tau"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
