# -*- coding: utf-8 -*-
"""設計28：関門の検査の包み。設計27 の関門の検査器 ds27_gates.py（P1〜P16 と原画の前提。変えずに import）を走らせ、
設計28 で足した関門 P17〜P19（ds28_gates_extra.py）を同じパッケージで測り、P20（ds28_p20.py の出力、記録）を添えて、1 つの JSON と日本語の表にする。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28/ds28_gates.py --package Unity/Build/Design/28/art_on --timewarp Tools/GWWaveGen/ds27/timewarp_default.json \\
      --sea Unity/Build/Design/28/art_on/ds27_sea.npz --out Unity/Build/Design/28/gates/art_on_default.json [--p20 Unity/Build/Design/28/p20/ds28_p20.json]
出力：<出力>.json（ds27 の報告に gates_ds28 と p20 を足したもの）と <出力>.md。<出力>_ds27.json（ds27_gates.py の出力そのもの）も残す。
1 回 約 6〜8 分（ds27_gates 約 5〜6 分＋P17〜P19 約 1 分）。
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, HERE)
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402
import ds28_gates_extra as GX  # noqa: E402

fnum = DG.fnum
rel = DG.rel


def p20_summary(path):
    if not path or not os.path.isfile(path):
        return None
    J = json.load(open(path, encoding="utf-8"))
    rows = {}
    for nm, e in J["guidance"].items():
        if e.get("colour_only"):
            rows[nm] = dict(kind_ja=e["kind_ja"], colour_only=True, twhite_changed_vertices=e["twhite_changed_vertices"],
                            twhite_max_abs_diff_s=e["twhite_max_abs_diff_s"], shape_max_diff_m=e.get("shape_max_diff_m"))
        else:
            pt = e["per_tau"]
            k = max(pt, key=lambda r: r["max_m"])
            rows[nm] = dict(kind_ja=e["kind_ja"], max_m=k["max_m"], max_tau=k["tau"], max_at=k["max_at"], rms_max_m=e["rms_max_over_tau_m"],
                            at_tstar=dict(rms_m=pt[-1]["rms_m"], max_m=pt[-1]["max_m"]),
                            at_minus1s=next((dict(rms_m=r["rms_m"], max_m=r["max_m"]) for r in pt if abs(r["tau"] + 1.0) < 1e-6), None))
    return dict(source=rel(path), rows=rows, all_off_max_m=max(r["max_m"] for r in J["all_off"]["per_tau"]))


def write_md(path, rep):
    L = ["# 設計28 の関門の検査（ds28_gates.py：ds27_gates.py の P1〜P16 ＋ 設計28 の P17〜P19、P20 は記録）", ""]
    pk = rep["package"]
    L.append("- 包み：`%s`（版 %s、%d 層）、時間曲線 `%s`" % (pk["dir"], pk["version"], pk["layers"], rep["timewarp"]["path"]))
    L.append("")
    L.append("| 関門 | 内容 | 値 | しきい値 | 判定 |")
    L.append("| --- | --- | --- | --- | --- |")
    for k, g in list(rep["gates"].items()) + list(rep["gates_ds28"].items()):
        v = g["value"]
        if isinstance(v, dict):
            v = "；".join("%s %s" % (kk, (" ".join("%s %s" % (a, b) for a, b in vv.items()) if isinstance(vv, dict) else vv)) for kk, vv in v.items())
        ok = g["pass"]
        L.append("| %s | %s | %s | %s | %s |" % (k, g["name_ja"], v, g["threshold"], "合格" if ok is True else ("不合格" if ok is False else "判定なし")))
    if rep.get("p20"):
        L += ["", "P20（美術の誘導の大きさ、記録。入れた版とその誘導だけを切った版の頂点の差の最大）：", "",
              "| 誘導 | 中身 | 最大（m） | τ | 最大の場所 | RMS の最大（m） |", "| --- | --- | --- | --- | --- | --- |"]
        for nm, e in rep["p20"]["rows"].items():
            if e.get("colour_only"):
                L.append("| %s | %s | 形 0（色だけ：T_white が変わる頂点 %d、最大 %s s） | — | — | — |" % (nm, e["kind_ja"], e["twhite_changed_vertices"], e["twhite_max_abs_diff_s"]))
            else:
                L.append("| %s | %s | %s | %s | 行 %d 列 %d（c %s m） | %s |" % (nm, e["kind_ja"], e["max_m"], e["max_tau"], e["max_at"]["row"], e["max_at"]["col"], e["max_at"]["c_m"], e["rms_max_m"]))
    L += ["", "設計28 の関門の読み方：", ""] + ["- " + x for x in GX.READINGS_JA]
    L += ["", "- P1〜P16 と原画の前提は設計27 の検査器そのもの（読み方は同じ名前の _ds27.md）。"]
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--timewarp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sea", default=None)
    ap.add_argument("--p20", default=None)
    a = ap.parse_args()
    t0 = time.time()
    base = os.path.splitext(a.out)[0]
    out27 = base + "_ds27.json"
    rep, M, ks, pk = DG.run(a.package, a.timewarp, out27, a.sea)
    ext = GX.run(a.package, out27, base + "_extra.json")
    rep["schema"] = "GreatWave.DS28.gates/1"
    rep["number"] = "設計28"
    rep["tool_ds28"] = rel(os.path.abspath(__file__))
    rep["gates_ds28"] = ext["gates"]
    rep["readings_ds28_ja"] = GX.READINGS_JA
    rep["thresholds_ds28"] = GX.TH
    rep["p20"] = p20_summary(a.p20)
    fails = [k for k, g in list(rep["gates"].items()) + list(ext["gates"].items()) if g["pass"] is False]
    rep["summary_all"] = dict(failed=fails, n_fail=len(fails))
    rep["runtime_total_s"] = round(time.time() - t0, 1)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=lambda o: fnum(o) if hasattr(o, "dtype") else str(o))
    write_md(base + ".md", rep)
    print("[ds28_gates] 不合格 %s（%.0f s）→ %s" % (",".join(fails) or "なし", rep["runtime_total_s"], a.out))


if __name__ == "__main__":
    main()
