# -*- coding: utf-8 -*-
"""仕上げ33修正01 変種 SWEEP：原画視点の形の関門と評価器 23 を、前（仕上げ33 修正の回 2）・後（SWEEP）・CP1・26修正01 で並べる（記録。新しい計算はしない）。

読むもの：<描画>/pl28u_regress.json（pl28u_regress.py の出力：t28_white＝爪なし、t28_claws＝爪あり）と <描画>/eval23/off_<組>/metrics.json（評価器 23）。
  - 78・130・131：定義のままの読みの最大（silhouettes_definition_reading）
  - 132・72 σ12：大きな輪郭の読み（large_form.s12 の 132_max_px・72_p95_px）
  - 132 細部込み（raw）の最大・72 細部込みの p95（定義のままの読み。爪がこの細部を描いてよいので記録する）
  - 評価器 23 の 4 組（線あり・線ありの爪なし・線なし・線なしの爪なし）の合格・不合格の数
CP1・26修正01 の値は仕上げ33 の記録（Docs/Progress/Polish_33_ja.md 第 6 節の表）から写した。
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --after-run … --out …
"""
import argparse
import json
import os

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish"
REF = {"CP1": {"78": 2.772, "130": 1.968, "131": 1.814, "132_s12": 1.326, "72_s12_p95": 1.558},
       "26修正01": {"78": 1.641, "130": 1.953, "131": 1.798, "132_s12": 1.574, "72_s12_p95": 1.723}}
GATE = 4.0


def read(run):
    d = json.load(open(os.path.join(run, "pl28u_regress.json"), encoding="utf-8"))
    out = {}
    for s, nm in (("t28_white", "noclaws"), ("t28_claws", "claws")):
        st = d["sets"][s]
        sd = st["strict"]["silhouettes_definition_reading"]
        lf = st["large_form"]["s12"]
        out[nm] = {"78": sd["78"]["max_px"], "130": sd["130"]["max_px"], "131": sd["131"]["max_px"],
                   "132_s12": lf["132_max_px"], "72_s12_p95": lf["72_p95_px"],
                   "132_raw_max": sd["132"]["max_px"], "72_raw_p95": sd["72"]["p95_px"], "72_raw_max": sd["72"]["max_px"],
                   "pass_silhouette": st["strict"]["pass_silhouette"]}
    ev = {}
    for c in ("line", "line_noclaws", "noline", "noline_noclaws"):
        p = os.path.join(run, "eval23", "off_" + c, "metrics.json")
        if not os.path.exists(p):
            continue
        e = json.load(open(p, encoding="utf-8"))
        v = [it.get("verdict") for it in e["items"].values()]
        ev[c] = {"pass": sum(1 for x in v if x == "pass"), "fail": sum(1 for x in v if x == "fail"), "other": sum(1 for x in v if x not in ("pass", "fail"))}
    out["eval23"] = ev
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-run", default=B + "/33/fix02/r_fix02")
    ap.add_argument("--after-run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    b, f = read(a.before_run), read(a.after_run)
    rows = {}
    for k in ("78", "130", "131", "132_s12", "72_s12_p95"):
        rows[k] = {"after_noclaws": f["noclaws"][k], "after_claws": f["claws"][k], "before_noclaws": b["noclaws"][k], "before_claws": b["claws"][k],
                   "CP1": REF["CP1"][k], "26修正01": REF["26修正01"][k], "gate_px": GATE,
                   "pass_after": bool(max(f["noclaws"][k], f["claws"][k]) <= GATE),
                   "regress_vs_before_px": round(max(f["noclaws"][k], f["claws"][k]) - max(b["noclaws"][k], b["claws"][k]), 4)}
    raw = {k: {"after_claws": f["claws"][k], "before_claws": b["claws"][k], "after_noclaws": f["noclaws"][k]} for k in ("132_raw_max", "72_raw_p95", "72_raw_max")}
    res = dict(rule_ja=__doc__.strip().split("\n\n")[1], before_run=os.path.relpath(a.before_run, REPO).replace("\\", "/"),
               after_run=os.path.relpath(a.after_run, REPO).replace("\\", "/"), gates=rows, raw_detail_with_claws=raw,
               eval23=dict(before=b["eval23"], after=f["eval23"]), before=b, after=f)
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "sweep_gates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(dict(gates=rows, raw=raw, eval23=res["eval23"]), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
