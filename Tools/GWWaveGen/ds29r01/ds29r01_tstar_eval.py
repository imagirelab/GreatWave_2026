# -*- coding: utf-8 -*-
"""設計29修正01（手渡し (a)）：K*′ へ焼き直した色面で描いた t* の画像を、美術優先28修正01 と同じ評価の手順で測り直す。

設計27 の ds27_tstar_eval.py をそのまま読み込み、同じプロセスの中だけで次の 2 つを差し替えて走らせる（元のファイルは変えない）：
  1) ds27_tstar_eval.B28（28修正01 の焼き込みと集計の置き場所）を、次を並べた一時のフォルダー <bake_kp>/stage28 にする：
       bake/・bake_input/ … K*′ への焼き直し（DS29R01Bake と ds29r01_bake_input.py の出力）
       render/・af28r01_*_report.json … 28修正01 のもの（評価器が並べるだけの比較用の画像。DS29Render が描いた t* の 10 枚で上書きされる）
  2) af28r01_params.json を読むとき、kstar_dir を K*′ の写し（<bake_kp>/kstar）にする（評価器では記録の欄にだけ使われる）。
比べる値（ds27_tstar_eval.py と同じ）：色区の境界 73・77・79・118・120・133・134・175・263・270 と 265〜267 は 28修正01 の値（Docs/Evidence/ArtFirst/28R01/metrics.json）、
輪郭は 26修正01／28修正01 の値。**輪郭は K*′ の形なので 26修正01 とは違って当然**で、設計29修正01 の判定では輪郭は K*′ の値（幾何）と比べる
（ds29r01_tstar_eval の出力 ds29r01_tstar_verdict.json）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_tstar_eval.py --run Unity/Build/Design/29R01/unity/f_final_kp
出力：<run>/ds27_tstar_remeasure.json（ds27_tstar_eval.py と同じ書式）と <run>/ds29r01_tstar_verdict.json（設計29修正01 の判定）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds27"))
import ds27_tstar_eval as E27  # noqa: E402
T = E27.T

BAKE_KP_REL = "Unity/Build/Design/29R01/bake_kp"
B28_ORIG = E27.B28
# K*′ の幾何から測った原画視点の値（設計28修正01 §4.1、独立の点検 ic_painting.json と同じ）
KP_GEOM = {"78": 2.741, "130": 3.8308, "131": 2.9243}
COLOUR_ITEMS = ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]


def stage(bake_kp):
    st = os.path.join(bake_kp, "stage28")
    E27.link_tree(os.path.join(B28_ORIG, "render"), os.path.join(st, "render"))
    E27.link_tree(os.path.join(bake_kp, "bake"), os.path.join(st, "bake"))
    E27.link_tree(os.path.join(bake_kp, "bake_input"), os.path.join(st, "bake_input"))
    for f in ("af28r01_render_report.json", "af28r01_build_report.json"):
        src = os.path.join(B28_ORIG, f)
        dst = os.path.join(st, f)
        if os.path.exists(dst):
            os.remove(dst)
        with open(src, "rb") as a, open(dst, "wb") as b:
            b.write(a.read())
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--bake-kp", default=BAKE_KP_REL)
    a = ap.parse_args()
    bake_kp = os.path.join(REPO, a.bake_kp)
    E27.B28 = stage(bake_kp)
    kdir_rel = a.bake_kp.replace("\\", "/") + "/kstar"
    orig_load = T.load_json

    def load_json(p, *k, **kw):
        v = orig_load(p, *k, **kw)
        if str(p).replace("\\", "/").endswith("Tools/PaintingTruth/colour/af28r01_params.json") and isinstance(v, dict):
            v = dict(v)
            v["kstar_dir"] = kdir_rel
            v["kstar_gwb_sha256_expected"] = {"a45": "38a9b11ab63cccb45cf2cb7776ae3a59485d58102e96cabaf828fb36d14cf19a"}
        return v
    T.load_json = load_json
    sys.argv = [sys.argv[0], "--run", a.run]
    E27.main()
    T.load_json = orig_load

    run = os.path.abspath(os.path.join(REPO, a.run))
    R = json.load(open(os.path.join(run, "ds27_tstar_remeasure.json"), encoding="utf-8"))
    rows = [r for r in R["boundaries_vs_28r01"] if r["item"] in COLOUR_ITEMS]
    worst_colour = max(abs(r["diff_px"]) for r in rows)
    worst_row = max(rows, key=lambda r: abs(r["diff_px"]))
    per_item = {}
    for r in rows:
        e = per_item.setdefault(r["item"], {"measures": 0, "worst_abs_diff_px": 0.0, "verdict_now": r["ds27_verdict"], "verdict_28r01": r["r28r01_verdict"]})
        e["measures"] += 1
        if abs(r["diff_px"]) >= e["worst_abs_diff_px"]:
            e["worst_abs_diff_px"] = abs(r["diff_px"])
            e["worst_measure"] = r["measure"]
            e["now_max_px"] = r["ds27_max_px"]
            e["r28r01_max_px"] = r["r28r01_max_px"]
    sil = {s["item"]: s for s in R["silhouettes_vs_26r01_28r01"]}
    sil_rows = {}
    worst_sil = 0.0
    for k, g in KP_GEOM.items():
        v = sil.get(k, {}).get("ds27_max_px")
        d = None if v is None else v - g
        if d is not None:
            worst_sil = max(worst_sil, abs(d))
        sil_rows[k] = {"unity_max_px": v, "kstar_prime_geometry_px": g, "diff_px": None if d is None else round(d, 4)}
    col = {}
    for k in ("265", "266", "267"):
        c = R["colour_265_266_267"][k]
        col[k] = {"verdict_now": c["ds27_verdict"], "verdict_28r01": c["r28r01_verdict"], "now": c["ds27"], "r28r01": c["r28r01"]}
    colour_regress = [k for k, e in per_item.items() if e["worst_abs_diff_px"] > 0.5]
    verdict_flip = [k for k, e in per_item.items() if e["verdict_now"] != e["verdict_28r01"]] + [k for k, c in col.items() if c["verdict_now"] != c["verdict_28r01"]]
    out = {
        "schema": "GreatWave.DS29R01.tstar_verdict/1", "number": "設計29修正01", "run": os.path.relpath(run, REPO).replace("\\", "/"),
        "method_ja": "ds27_tstar_eval.py の結果（ds27_tstar_remeasure.json）から、色区の境界は 28修正01 の値との差（±0.5 px）、輪郭 78／130／131 は K*′ の幾何の値との差（±0.5 px）で判定する（計画 §2.0 の回帰の規則）。265〜267 は判定の一致を見る。",
        "colour_boundaries": {"worst_abs_diff_px": round(worst_colour, 4), "worst": worst_row, "items": per_item, "items_over_0p5": sorted(colour_regress, key=int)},
        "colour_265_267": col,
        "silhouettes_vs_kstar_prime": {"rows": sil_rows, "worst_abs_diff_px": round(worst_sil, 4)},
        "verdict_changes_vs_28r01": verdict_flip,
        "pass_colour": worst_colour <= 0.5 and not [k for k in verdict_flip if k in ("265", "266", "267")],
        "pass_silhouette": worst_sil <= 0.5,
    }
    T.save_json(os.path.join(run, "ds29r01_tstar_verdict.json"), out)
    print("DS29R01_TSTAR colour_worst=%.4f over0.5=%s sil_worst=%.4f flips=%s pass_colour=%s pass_sil=%s" % (
        worst_colour, colour_regress, worst_sil, verdict_flip, out["pass_colour"], out["pass_silhouette"]))


if __name__ == "__main__":
    main()
