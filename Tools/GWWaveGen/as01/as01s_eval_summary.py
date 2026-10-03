# -*- coding: utf-8 -*-
"""美術の見本01（Q29）組み立て：評価器 23 の 4 組と形の関門を、前（採用の仕上げ33修正01）・見本 A・見本 B・CP1・26修正01 で並べる（記録。新しい計算はしない）。

読むもの：
  前   Unity/Build/Polish/33r01/fix01/r_fix01/eval23/off_<組>/metrics.json
  A・B Unity/Build/Polish/sample01/assemble/<A|B>/eval23/off_<組>/metrics.json（as01s_run_eval.sh）
  形の関門 Unity/Build/Polish/sample01/assemble/logs/gates_B_vs_33r01.txt（sweep_gates.py。前 = r_fix01。A と B は空の被覆が画素で同じなので B の値が A の値）
出力：Unity/Build/Polish/sample01/assemble/measure/as01s_eval_summary.json
"""
import argparse
import json
import os

REPO = "G:/Unity/GreatWave_2026_Fresh"
AS = REPO + "/Unity/Build/Polish/sample01/assemble"
RUNS = {"before_33r01": REPO + "/Unity/Build/Polish/33r01/fix01/r_fix01", "A": AS + "/A", "B": AS + "/B"}
COMBOS = ("line", "line_noclaws", "noline", "noline_noclaws")


def items(run, c):
    d = json.load(open(os.path.join(run, "eval23", "off_" + c, "metrics.json"), encoding="utf-8"))
    out = {}
    for k, it in d["items"].items():
        vals = {}
        for m in it.get("measures", []):
            if isinstance(m, dict):
                vals[m.get("target", m.get("metric", "?"))] = m.get("value_max_px", m.get("value"))
        out[k] = dict(verdict=it.get("verdict"), values=vals)
    return out


def main():
    # 改善の回 1（2026-10-03）：--round r1 で、前（33修正01）・回 0 の A・B・回 1 の A1・B1 を並べ、形の関門は B1 の値（A1 と空の被覆が同じ）
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="r0")
    a = ap.parse_args()
    global RUNS
    gates_file, out_name = AS + "/logs/gates_B_vs_33r01.txt", "as01s_eval_summary.json"
    if a.round == "r1":
        RUNS = dict(RUNS, A1=AS + "/A1", B1=AS + "/B1")
        gates_file, out_name = AS + "/logs/gates_B1_vs_33r01.txt", "as01s_eval_summary_r1.json"
    if a.round == "r2":
        # 改善の回 2（2026-10-03）：回 1 の A1・B1 と回 2 の A2・B2 を足す。形の関門は B2 の値（A2 と空の被覆が画素で同じ）
        RUNS = dict(RUNS, A1=AS + "/A1", B1=AS + "/B1", A2=AS + "/A2", B2=AS + "/B2")
        gates_file, out_name = AS + "/logs/gates_B2_vs_33r01.txt", "as01s_eval_summary_r2.json"
    res = dict(tool="Tools/GWWaveGen/as01/as01s_eval_summary.py", round=a.round, runs=RUNS, eval23={}, changed={})
    for c in COMBOS:
        res["eval23"][c] = {}
        per = {n: items(r, c) for n, r in RUNS.items()}
        for n, it in per.items():
            cnt = {"pass": 0, "fail": 0, "other": 0}
            for v in it.values():
                cnt[v["verdict"] if v["verdict"] in ("pass", "fail") else "other"] += 1
            res["eval23"][c][n] = cnt
        ch = {}
        for k in per["before_33r01"]:
            row = {n: per[n].get(k, {}) for n in RUNS}
            if len({json.dumps(v, sort_keys=True) for v in row.values()}) > 1:
                ch[k] = row
        res["changed"][c] = ch
    g = json.load(open(gates_file, encoding="utf-8"))
    res["gates"] = g["gates"]
    res["gates_raw"] = g["raw"]
    res["gates_note_ja"] = "A と B は爪あり・爪なしとも空の被覆（class_ids の空）が画素で同じ（xor 0）なので、形の関門の値は共通（B の pl28u_regress で測った。A の pl28u_regress は色区 267 の読みで止まった）"
    os.makedirs(AS + "/measure", exist_ok=True)
    json.dump(res, open(AS + "/measure/" + out_name, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for c in COMBOS:
        print(c, json.dumps(res["eval23"][c], ensure_ascii=False))
        for k, row in res["changed"][c].items():
            print("   ", k, {n: (v.get("verdict"), {t: (round(x, 3) if isinstance(x, float) else x) for t, x in v.get("values", {}).items()}) for n, v in row.items()})
    for k, v in res["gates"].items():
        print("gate", k, {kk: vv for kk, vv in v.items()})


if __name__ == "__main__":
    main()
