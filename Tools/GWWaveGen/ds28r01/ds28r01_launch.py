# -*- coding: utf-8 -*-
"""設計28修正01：唇先の放出・打ち出し・頂点の表（設計28 の入れた版と設計28修正01 の入れた版を、同じ生成器の ds_rise_overlap の入り切りで比べる）。

行ごとに：唇先の放出の時刻と飛ぶ時間、放出の時の頂の高さ（/H）、放出の高さ、放出の前の速さ、打ち出しの速さ（u/c0、w、w/√(gH)）、
唇先の頂点の高さ・時刻とその時の頂の高さ（頂点 − 頂）、放出の後の唇先 − 頂の最大。生成器を直接呼ぶ（パッケージではない）。
使い方（リポジトリの根で。約 4 分）：py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_launch.py [--out Unity/Build/Design/28R01/launch/ds28r01_launch.json]
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds28r01_model as MR  # noqa: E402

ROWS_C = [-25.0, -15.0, -8.0, 0.0, 2.0, 3.85]


def plausible(g):
    """設計26 E1 の目安の範囲（u/c0 0.6〜1.3、w/√(gH) −0.2〜0.8。t* の 0.15 s 前より後に放出される点は評価しない）の割合を、
    実際の放出の点（κ < 1 の行と ds_rise_overlap の行は放出の前の動きから取った P0、ほかは設計27 の Pg）で数え直す。"""
    n_ev = n_ok = 0
    for r, L in g.lip.items():
        Kt = L["Kt"]
        Tc = L["Tc"]
        P0 = L["P0"] if L.get("mode") == "damped" else L["Pg"]
        ub = (Kt[:, 0] - P0[:, 0]) / Tc
        wb = (Kt[:, 1] - P0[:, 1] + 0.5 * MR.G * Tc ** 2) / Tc
        sg = np.sqrt(MR.G * g.H[r])
        ev = L["Ti"] >= 0.15
        ok = (ub / g.c0 >= 0.6) & (ub / g.c0 <= 1.3) & (wb / sg >= -0.2) & (wb / sg <= 0.8)
        n_ev += int(ev.sum())
        n_ok += int((ev & ok).sum())
    return dict(fraction=n_ok / max(n_ev, 1), n_eval=n_ev, n_ok=n_ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(MR.REPO, "Unity", "Build", "Design", "28R01", "launch", "ds28r01_launch.json"))
    a = ap.parse_args()
    out = {}
    for tag, ro in (("ds28_art_on", False), ("ds28r01_art_on", True)):
        g = MR.Generator("art_on", rise_overlap=ro)
        rows = sorted(set(int(np.argmin(np.abs(g.K.c - c))) for c in ROWS_C) & set(g.lip.keys()))
        out[tag] = dict(variant=g.variant, rows=g.launch_table(rows),
                        E1_plausible_recounted=plausible(g), E1_plausible_fraction_summary=g.summary().get("lip_plausible_fraction"),
                        onset_crest_over_H_peak=float(g.crest(-2.4)[1][192] / g.H[192]))
        print(tag, "done", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print(a.out)


if __name__ == "__main__":
    main()
