# -*- coding: utf-8 -*-
"""仕上げ28（焼き直しと Unity の描画）：t* の画像の組 1 つを、設計29修正01 の ds29r01_tstar_eval.py と同じ手順（美術優先28修正01 の評価器）で測る。

ds29r01_tstar_eval.py の main() の中の固定値（K*′ の幾何の値 KP_GEOM、焼き込みの置き場所、K*′ の SHA-256）を引数にしただけの写しで、
評価の関数・真値・閾値・書式は同じ（ds27_tstar_eval.py を同じプロセスの中で読み込み、B28 と af28r01_params.json の kstar_dir だけを差し替える）。
  --kstar p28 ：仕上げ28 の K*′ P28R2（幾何の値 78／130／131 = 2.439／3.2299／3.3546 px。Unity/Build/Polish/28/r2/metrics.json の
                values.P28R2.outline_78_130_131_max_px_definition_reading）と、その焼き直し（Unity/Build/Polish/28/unity/bake_kp）
  --kstar r4  ：設計28修正01 の K*′ R4（2.741／3.8308／2.9243 px、設計29修正01 の焼き込み Unity/Build/Design/29R01/bake_kp）。段階9 の状態を同じ読みで測る時
色区の境界は 28修正01 の値（Docs/Evidence/ArtFirst/28R01/metrics.json）と比べる（「評価器の定義のままの読み」）。輪郭 78／130／131 は K*′ の幾何の値と比べる。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl28/pl28u_tstar_eval.py --run Unity/Build/Polish/28/unity/scene_p28/t28_white --kstar p28
出力：<run>/ds27_tstar_remeasure.json（ds27_tstar_eval.py と同じ書式）と <run>/pl28u_tstar_verdict.json（ds29r01_tstar_verdict.json と同じ書式）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds27"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds29r01"))
import ds27_tstar_eval as E27  # noqa: E402
import ds29r01_tstar_eval as V29  # noqa: E402  （stage() を借りる。V29 の import で E27.B28 は元のまま）
T = E27.T

KSTAR = {
    "p28": {"bake_kp": "Unity/Build/Polish/28/unity/bake_kp", "geom": {"78": 2.439, "130": 3.2299, "131": 3.3546},
            "gwb_sha256": "79ff9fde8ea8ebf9b04897915d19717108fe826f0626b72384e891a6d53c6992", "name": "K*′ P28R2（仕上げ28）"},
    # 仕上げ28 の回復（rec）：K*′ P28R2rec（Unity/Build/Polish/28/kstar_p28rec。幾何の値は kh_eval の rec/try/eval_P4 と同じ行の値）
    "rec": {"bake_kp": "Unity/Build/Polish/28/unity/bake_rec", "geom": {"78": 2.439, "130": 3.2299, "131": 3.3546},
            "gwb_sha256": "a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94", "name": "K*′ P28R2rec（仕上げ28 の回復）"},
    "r4": {"bake_kp": "Unity/Build/Design/29R01/bake_kp", "geom": {"78": 2.741, "130": 3.8308, "131": 2.9243},
           "gwb_sha256": "38a9b11ab63cccb45cf2cb7776ae3a59485d58102e96cabaf828fb36d14cf19a", "name": "K*′ R4（設計28修正01）"},
}
COLOUR_ITEMS = V29.COLOUR_ITEMS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--kstar", choices=sorted(KSTAR), required=True)
    a = ap.parse_args()
    K = KSTAR[a.kstar]
    bake_kp = os.path.join(REPO, K["bake_kp"])
    E27.B28 = V29.stage(bake_kp)
    kdir_rel = K["bake_kp"] + "/kstar"
    orig_load = T.load_json

    def load_json(p, *k, **kw):
        v = orig_load(p, *k, **kw)
        if str(p).replace("\\", "/").endswith("Tools/PaintingTruth/colour/af28r01_params.json") and isinstance(v, dict):
            v = dict(v)
            v["kstar_dir"] = kdir_rel
            v["kstar_gwb_sha256_expected"] = {"a45": K["gwb_sha256"]}
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
        e = per_item.setdefault(r["item"], {"measures": 0, "worst_abs_diff_px": 0.0, "verdict_now": r["ds27_verdict"], "verdict_28r01": r["r28r01_verdict"],
                                            "max_now_px": 0.0})
        e["measures"] += 1
        e["max_now_px"] = max(e["max_now_px"], r["ds27_max_px"] if r["ds27_max_px"] is not None else 0.0)
        if abs(r["diff_px"]) >= e["worst_abs_diff_px"]:
            e["worst_abs_diff_px"] = abs(r["diff_px"])
            e["worst_measure"] = r["measure"]
            e["now_max_px"] = r["ds27_max_px"]
            e["r28r01_max_px"] = r["r28r01_max_px"]
    sil = {s["item"]: s for s in R["silhouettes_vs_26r01_28r01"]}
    sil_rows = {}
    worst_sil = 0.0
    for k, g in K["geom"].items():
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
        "schema": "GreatWave.Polish28.tstar_verdict/1", "number": "仕上げ28（焼き直しと Unity の描画）", "run": os.path.relpath(run, REPO).replace("\\", "/"),
        "kstar": K["name"], "kstar_geometry_px": K["geom"], "bake_kp": K["bake_kp"],
        "method_ja": "ds29r01_tstar_eval.py と同じ：ds27_tstar_eval.py の結果（ds27_tstar_remeasure.json）から、色区の境界は 28修正01 の値との差（±0.5 px）、"
                     "輪郭 78／130／131 は K*′ の幾何の値との差（±0.5 px）で判定する。265〜267 は判定の一致を見る。評価器の定義のままの読み。",
        "colour_boundaries": {"worst_abs_diff_px": round(worst_colour, 4), "worst": worst_row, "items": per_item, "items_over_0p5": sorted(colour_regress, key=int)},
        "colour_265_267": col,
        "silhouettes_vs_kstar_prime": {"rows": sil_rows, "worst_abs_diff_px": round(worst_sil, 4)},
        "verdict_changes_vs_28r01": verdict_flip,
        "pass_colour": worst_colour <= 0.5 and not [k for k in verdict_flip if k in ("265", "266", "267")],
        "pass_silhouette": worst_sil <= 0.5,
    }
    T.save_json(os.path.join(run, "pl28u_tstar_verdict.json"), out)
    print("PL28U_TSTAR colour_worst=%.4f over0.5=%s sil_worst=%.4f flips=%s pass_colour=%s pass_sil=%s" % (
        worst_colour, colour_regress, worst_sil, verdict_flip, out["pass_colour"], out["pass_silhouette"]))


if __name__ == "__main__":
    main()
