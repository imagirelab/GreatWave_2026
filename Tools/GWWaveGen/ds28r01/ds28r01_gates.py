# -*- coding: utf-8 -*-
"""設計28修正01：関門の検査の包み。設計27 の ds27_gates.py（P1〜P16・原画の前提）と設計28 の ds28_gates_extra.py（P17〜P19）を
変えずに import して走らせる。変えるのは P15 の段階の表だけ（T4：ds28r01_params.json の stage_table_q13。この包みの中で
ds27_gates.STAGE の H/H* の帯と load_conditions の段階の時刻を差し替える＝P15'）。P15' には「d の頂は c の頂より高い」を足す。

使い方（リポジトリの根で。1 回 約 6〜9 分）：
  py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_gates.py --package Unity/Build/Design/28R01/art_on \\
      --timewarp Tools/GWWaveGen/ds28r01/timewarp_default.json --sea Unity/Build/Design/28R01/art_on/ds27_sea.npz \\
      --out Unity/Build/Design/28R01/gates/art_on_default.json [--table design26]
  （--table design26：設計26 の表のままで P15 を測る。比べるため）
出力：<出力>.json（ds27 の報告に gates_ds28（P17〜P19）と gates_ds28r01（P15' の d > c）を足したもの）、<出力>_ds27.json、<出力>_extra.json。
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
DS28 = os.path.abspath(os.path.join(HERE, "..", "ds28"))
for p in (DS28, DS27):
    if p not in sys.path:
        sys.path.insert(0, p)
import ds27_gates as DG  # noqa: E402
import ds28_gates_extra as GX  # noqa: E402

fnum = DG.fnum
rel = DG.rel
PARAMS = os.path.join(HERE, "ds28r01_params.json")


def patch_table(kind):
    """ds27_gates の段階の表を差し替える（この包みのプロセスの中だけ。ds27_gates.py のファイルは変えない）。"""
    R = json.load(open(PARAMS, encoding="utf-8"))["stage_table_q13"]
    if kind == "design26":
        return dict(kind="design26", note_ja="設計26 §3.1 の表のまま（比べるため）")
    b = R["H_bands"]
    DG.STAGE["a"]["H"] = tuple(b["a"])
    DG.STAGE["b"]["H"] = tuple(b["b"])
    DG.STAGE["c"]["H"] = tuple(b["c"])
    DG.STAGE["d"]["H_min"] = float(b["d_min"])
    orig = DG.load_conditions

    def load_conditions():
        cond, src = orig()
        if cond is not None:
            cond["stage_tau"] = {k: float(R["stage_tau_peak_row_s"][k]) for k in "abcd"}
            cond["main_lag"] = float(R["main_row_lag_s"])
        if src is not None:
            src = dict(src, stage_table_ds28r01=dict(path=rel(PARAMS), stage_tau_peak_row_s=R["stage_tau_peak_row_s"], H_bands=b))
        return cond, src
    DG.load_conditions = load_conditions
    GX.DG.load_conditions = load_conditions
    return dict(kind="q13", stage_tau_peak_row_s=R["stage_tau_peak_row_s"], main_row_lag_s=R["main_row_lag_s"], H_bands=b,
                design26_table=R["design26_table"], note_ja=R["note_ja"])


def d_taller_than_c(pk, ks, p15):
    """P15' の足し：主断面と峰の行で、P15 の d の時刻の頂 H が c の時刻の頂より高いこと（写真 Fig. 4：d は c より高い）。"""
    out = {}
    ok = True
    named = {ks.main_row: "主断面", ks.peak_row: "峰で最も高い巻きの行"}
    for r, nm in named.items():
        d = p15["detail"].get(nm, {})
        tt = d.get("tau") or {}
        res = {}
        for k in ("c", "d"):
            if tt.get(k) is None:
                res[k] = None
                continue
            Xl = pk.local(float(tt[k])) + ks.O
            A, Y, _ = ks.section(Xl)
            rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
            Hf = None
            res[k] = dict(tau=tt[k], H_m=fnum(float(rm["H"][r]), 3))
        Xl = pk.local(0.0) + ks.O
        A, Y, _ = ks.section(Xl)
        Hf = float(DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)["H"][r])
        for k in ("c", "d"):
            if res[k]:
                res[k]["H_over_Hf"] = fnum(res[k]["H_m"] / Hf, 3)
        okr = bool(res["c"] and res["d"] and res["d"]["H_m"] > res["c"]["H_m"])
        res["pass"] = okr
        ok &= okr
        out[nm] = res
    return dict(name_ja="P15' の足し：d の頂は c の頂より高い（主断面と峰の行）", pass_=ok, detail=out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--timewarp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sea", default=None)
    ap.add_argument("--table", default="q13", choices=["q13", "design26"])
    a = ap.parse_args()
    t0 = time.time()
    tab = patch_table(a.table)
    base = os.path.splitext(a.out)[0]
    out27 = base + "_ds27.json"
    rep, M, ks, pk = DG.run(a.package, a.timewarp, out27, a.sea)
    ext = GX.run(a.package, out27, base + "_extra.json")
    add = {}
    if a.table == "q13":
        dc = d_taller_than_c(pk, ks, rep["gates"]["P15"])
        dc["pass"] = dc.pop("pass_")
        add["P15_d_taller_than_c"] = dc
        p15 = rep["gates"]["P15"]
        add["P15_prime"] = dict(name_ja="P15'：a→b→c→d の順（T4 の表、各 ±0.3 s、最初の白は c）かつ d の頂 > c の頂",
                                pass_=None, value=p15["value"])
        add["P15_prime"]["pass"] = bool(p15["pass"]) and bool(dc["pass"])
        add["P15_prime"].pop("pass_")
    rep["schema"] = "GreatWave.DS28R01.gates/1"
    rep["number"] = "設計28修正01"
    rep["tool_ds28r01"] = rel(os.path.abspath(__file__))
    rep["stage_table"] = tab
    rep["gates_ds28"] = ext["gates"]
    rep["readings_ds28_ja"] = GX.READINGS_JA
    rep["thresholds_ds28"] = GX.TH
    rep["gates_ds28r01"] = add
    fails = [k for k, g in list(rep["gates"].items()) + list(ext["gates"].items()) + list(add.items()) if g.get("pass") is False]
    rep["summary_all"] = dict(failed=fails, n_fail=len(fails))
    rep["runtime_total_s"] = round(time.time() - t0, 1)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=lambda o: fnum(o) if hasattr(o, "dtype") else str(o))
    print("[ds28r01_gates] 表 %s、不合格 %s（%.0f s）→ %s" % (a.table, ",".join(fails) or "なし", rep["runtime_total_s"], a.out))


if __name__ == "__main__":
    main()
