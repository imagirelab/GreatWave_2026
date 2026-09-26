# -*- coding: utf-8 -*-
"""番号30：t*（12.0 s）の keypose の描画を、番号28修正01 と同じ評価の手順で測り直す（t* の再測定が 26修正01／28修正01 と ±0.5 px 以内か）。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/af30_tstar_eval.py
入力：
    Unity/Build/ArtFirst/30/t28/render/af28r01_*.png   AF30Formation.Render が keypose の頂点補間（AF30 NPR Keypose）で t* に描いた画像
                                                    （番号28修正01 の AF28R01NprScene.Render と同じ名前・同じ採取の設定）
    Unity/Build/ArtFirst/28修正01/                      番号28修正01 の焼き込みと集計（読むだけ。同じ内容をハードリンクで t28/ へ並べる）
処理：番号28修正01 の af28r01_evaluate.py を読み込み、params の build_dir と evidence_dir だけを t28/ へ向けた一時の params で main() を走らせる
（評価の関数・真値・閾値は同じ）。番号30 が描かなかった比較用の画像（rule28 の画像・側面・背面など）は 28修正01 のものを並べるだけで、
番号30 の比較には使わない。出力：Unity/Build/ArtFirst/30/af30_tstar_remeasure.json（項目ごとに 30 の値・28修正01／26修正01 の値・差）。
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PT = os.path.join(REPO, "Tools", "PaintingTruth")
sys.path.insert(0, os.path.join(PT, "colour"))
sys.path.insert(0, PT)
import truthlib as T  # noqa: E402

B28 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01")
OUT = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30")
T28 = os.path.join(OUT, "t28")
MINE = ["af28r01_painting.png", "af28r01_seat.png", "af28r01_seat_low.png", "af28r01_painting_kstar.png", "af28r01_seat_kstar.png",
        "af28r01_seat_low_kstar.png", "af28r01_class_ids.png", "af28r01_seat_class_ids.png", "af28r01_seat_low_class_ids.png", "af28r01_line_ids.png"]


def link_tree(src, dst, skip=()):
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src):
        s, d = os.path.join(src, f), os.path.join(dst, f)
        if os.path.isdir(s) or f in skip:
            continue
        if os.path.exists(d):
            os.remove(d)
        try:
            os.link(s, d)
        except OSError:
            shutil.copy2(s, d)


def flatten(v, path=""):
    out = {}
    if isinstance(v, dict):
        if "max_px" in v and isinstance(v["max_px"], (int, float)):
            out[path or "."] = {"max_px": v["max_px"], "p95_px": v.get("p95_px")}
        for k, x in v.items():
            if isinstance(x, dict):
                out.update(flatten(x, (path + "/" if path else "") + k))
    return out


def main():
    for f in MINE:
        if not os.path.exists(os.path.join(T28, "render", f)):
            raise SystemExit("番号30 の t* の画像がありません: " + f)
    link_tree(os.path.join(B28, "render"), os.path.join(T28, "render"), skip=set(MINE) | {"idmap.json"})
    shutil.copy2(os.path.join(B28, "render", "idmap.json"), os.path.join(T28, "render", "idmap.json"))
    link_tree(os.path.join(B28, "bake"), os.path.join(T28, "bake"))
    link_tree(os.path.join(B28, "bake_input"), os.path.join(T28, "bake_input"))
    for f in ("af28r01_render_report.json", "af28r01_build_report.json"):
        shutil.copy2(os.path.join(B28, f), os.path.join(T28, f))
    P = T.load_json(os.path.join(REPO, "Tools", "PaintingTruth", "colour", "af28r01_params.json"))
    P["build_dir"] = "Unity/Build/ArtFirst/30/t28"
    P["evidence_dir"] = "Unity/Build/ArtFirst/30/t28/evidence"
    P["note_ja"] = "番号30 の t* の再測定の一時の params（af28r01_params.json の build_dir と evidence_dir だけを変えた。Git 対象外）"
    pp = os.path.join(T28, "af30_t28_params.json")
    T.save_json(pp, P)
    import af28r01_evaluate as E28
    E28.PARAMS_REL = "Unity/Build/ArtFirst/30/t28/af30_t28_params.json"
    rc = E28.main()
    mine = T.load_json(os.path.join(T28, "evidence", "metrics.json"))
    ref28 = T.load_json(os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "28R01", "metrics.json"))
    ref26 = T.load_json(os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "26R01", "metrics.json"))
    rows = []
    worst = 0.0
    for k in ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]:
        a = flatten(mine["items"][k]["value"])
        b = flatten(ref28["items"][k]["value"])
        for p in sorted(set(a) & set(b)):
            d = a[p]["max_px"] - b[p]["max_px"]
            worst = max(worst, abs(d))
            rows.append({"item": k, "measure": p, "af30_max_px": round(a[p]["max_px"], 4), "r28r01_max_px": round(b[p]["max_px"], 4), "diff_px": round(d, 4),
                         "af30_verdict": mine["items"][k]["verdict"], "r28r01_verdict": ref28["items"][k]["verdict"]})
    sil = mine["silhouette_crosscheck_evaluator23"]["class_ids"]
    sil26 = {e["item"]: e for e in ref26.get("evaluator_compare", []) if isinstance(e, dict)}
    sil28 = ref28["silhouette_crosscheck_evaluator23"]["class_ids"]
    srows = []
    for k in ["78", "130", "131", "132", "72", "71"]:
        a = sil.get(k, {})
        e = sil26.get(k, {})
        c = sil28.get(k, {})
        d26 = None if a.get("max_px") is None or e.get("r01") is None else a["max_px"] - e["r01"]
        d28 = None if a.get("max_px") is None or c.get("max_px") is None else a["max_px"] - c["max_px"]
        dp = None if a.get("p95_px") is None or e.get("r01_p95") is None else a["p95_px"] - e["r01_p95"]
        if k != "71":
            for v in (d26, d28, dp):
                if v is not None:
                    worst = max(worst, abs(v))
        srows.append({"item": k, "af30_max_px": a.get("max_px"), "af30_p95_px": a.get("p95_px"), "r26r01_max_px": e.get("r01"), "r26r01_p95_px": e.get("r01_p95"),
                      "r28r01_max_px": c.get("max_px"), "diff_vs_26r01_max_px": d26, "diff_vs_26r01_p95_px": dp, "diff_vs_28r01_max_px": d28})
    col = {k: {"af30": mine["items"][k]["value"], "r28r01": ref28["items"][k]["value"], "af30_verdict": mine["items"][k]["verdict"],
               "r28r01_verdict": ref28["items"][k]["verdict"]} for k in ("265", "266", "267")}
    res = {"schema": "GreatWave.AF30.tstar_remeasure/1", "number": "30",
           "method_ja": __doc__.strip(),
           "boundaries_vs_28r01": rows, "silhouettes_vs_26r01_28r01": srows, "colour_265_266_267": col,
           "worst_abs_diff_px": round(worst, 4), "criterion_px": 0.5, "pass": worst <= 0.5,
           "summary_verdicts_af30": mine["summary_verdicts"], "summary_verdicts_28r01": ref28["summary_verdicts"],
           "outline_interior_px": {"af30": mine["items"]["outline_interior_record"]["value"], "r28r01": ref28["items"]["outline_interior_record"]["value"]},
           "evaluate_rc": rc}
    T.save_json(os.path.join(OUT, "af30_tstar_remeasure.json"), res)
    print("AF30_TSTAR worst_abs_diff_px=%.4f pass=%s" % (worst, worst <= 0.5))


if __name__ == "__main__":
    main()
