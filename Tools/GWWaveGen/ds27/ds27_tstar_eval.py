# -*- coding: utf-8 -*-
"""設計27：DS27 の再生で描いた t*（τ = 0）の画像を、美術優先28修正01 と同じ評価の手順で測り直す（計画 §2.0 の回帰の確認、設計26 §4.2）。
美術優先31 の af31_tstar_eval.py と同じ処理で、入出力の場所を引数にした（評価の関数・真値・閾値は同じ）。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/ds27/ds27_tstar_eval.py --run Unity/Build/Design/27/<版>_<時間曲線>
入力：
    <run>/t28/render/af28r01_*.png   DS27Formation.Render が t* に描いた画像（美術優先28修正01 の AF28R01NprScene.Render と同じ名前・同じ採取の設定）
    Unity/Build/ArtFirst/28修正01/      28修正01 の焼き込みと集計（読むだけ。同じ内容をハードリンクで <run>/t28/ へ並べる）
    Unity/Build/ArtFirst/30/t28/render/ 美術優先30 の t* の画像（読むだけ。画素の差を記録する）
処理：28修正01 の af28r01_evaluate.py を読み込み、params の build_dir と evidence_dir だけを <run>/t28 へ向けた一時の params で main() を走らせる。
DS27 が描かなかった比較用の画像（rule28 の画像・側面・背面など）は 28修正01 のものを並べるだけで、比較には使わない。
出力：<run>/ds27_tstar_remeasure.json（項目ごとに DS27 の値・28修正01／26修正01 の値・差、美術優先30 の画像との画素の差）。合格：差の最大 ≤ 0.5 px。
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PT = os.path.join(REPO, "Tools", "PaintingTruth")
sys.path.insert(0, os.path.join(PT, "colour"))
sys.path.insert(0, PT)
import truthlib as T  # noqa: E402

B28 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01")
AF30_T28 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30", "t28", "render")
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


def pixel_diff(a_path, b_path):
    a = T.imread_rgb(a_path).astype(np.int16)
    b = T.imread_rgb(b_path).astype(np.int16)
    if a.shape != b.shape:
        return {"shape_a": list(a.shape), "shape_b": list(b.shape)}
    d = np.abs(a - b).max(2)
    return {"pixels": int(d.size), "differing_pixels": int((d > 0).sum()), "differing_gt8": int((d > 8).sum()),
            "max_channel_diff": int(d.max()), "fraction_differing": float((d > 0).mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="DS27Formation の出力（例 Unity/Build/Design/27/art_on_default）")
    args = ap.parse_args()
    run = os.path.abspath(os.path.join(REPO, args.run)) if not os.path.isabs(args.run) else os.path.abspath(args.run)
    t28 = os.path.join(run, "t28")
    for f in MINE:
        if not os.path.exists(os.path.join(t28, "render", f)):
            raise SystemExit("DS27 の t* の画像がありません: " + f)
    link_tree(os.path.join(B28, "render"), os.path.join(t28, "render"), skip=set(MINE) | {"idmap.json"})
    shutil.copy2(os.path.join(B28, "render", "idmap.json"), os.path.join(t28, "render", "idmap.json"))
    link_tree(os.path.join(B28, "bake"), os.path.join(t28, "bake"))
    link_tree(os.path.join(B28, "bake_input"), os.path.join(t28, "bake_input"))
    for f in ("af28r01_render_report.json", "af28r01_build_report.json"):
        shutil.copy2(os.path.join(B28, f), os.path.join(t28, f))
    rel = os.path.relpath(t28, REPO).replace("\\", "/")
    P = T.load_json(os.path.join(REPO, "Tools", "PaintingTruth", "colour", "af28r01_params.json"))
    P["build_dir"] = rel
    P["evidence_dir"] = rel + "/evidence"
    P["note_ja"] = "設計27 の t* の再測定の一時の params（af28r01_params.json の build_dir と evidence_dir だけを変えた。Git 対象外）"
    pp = os.path.join(t28, "ds27_t28_params.json")
    T.save_json(pp, P)
    import af28r01_evaluate as E28
    E28.PARAMS_REL = rel + "/ds27_t28_params.json"
    rc = E28.main()
    mine = T.load_json(os.path.join(t28, "evidence", "metrics.json"))
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
            rows.append({"item": k, "measure": p, "ds27_max_px": round(a[p]["max_px"], 4), "r28r01_max_px": round(b[p]["max_px"], 4), "diff_px": round(d, 4),
                         "ds27_verdict": mine["items"][k]["verdict"], "r28r01_verdict": ref28["items"][k]["verdict"]})
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
        srows.append({"item": k, "ds27_max_px": a.get("max_px"), "ds27_p95_px": a.get("p95_px"), "r26r01_max_px": e.get("r01"), "r26r01_p95_px": e.get("r01_p95"),
                      "r28r01_max_px": c.get("max_px"), "diff_vs_26r01_max_px": d26, "diff_vs_26r01_p95_px": dp, "diff_vs_28r01_max_px": d28})
    col = {k: {"ds27": mine["items"][k]["value"], "r28r01": ref28["items"][k]["value"], "ds27_verdict": mine["items"][k]["verdict"],
               "r28r01_verdict": ref28["items"][k]["verdict"]} for k in ("265", "266", "267")}
    px = {}
    for f in MINE:
        b = os.path.join(AF30_T28, f)
        if os.path.exists(b):
            px[f] = pixel_diff(os.path.join(t28, "render", f), b)
    res = {"schema": "GreatWave.DS27.tstar_remeasure/1", "number": "設計27",
           "method_ja": __doc__.strip(), "run": run,
           "boundaries_vs_28r01": rows, "silhouettes_vs_26r01_28r01": srows, "colour_265_266_267": col,
           "worst_abs_diff_px": round(worst, 4), "criterion_px": 0.5, "pass": worst <= 0.5,
           "summary_verdicts_ds27": mine["summary_verdicts"], "summary_verdicts_28r01": ref28["summary_verdicts"],
           "outline_interior_px": {"ds27": mine["items"]["outline_interior_record"]["value"], "r28r01": ref28["items"]["outline_interior_record"]["value"]},
           "pixel_diff_vs_af30_t28": px,
           "evaluate_rc": rc}
    T.save_json(os.path.join(run, "ds27_tstar_remeasure.json"), res)
    print("DS27_TSTAR worst_abs_diff_px=%.4f pass=%s -> %s" % (worst, worst <= 0.5, os.path.join(run, "ds27_tstar_remeasure.json")))


if __name__ == "__main__":
    main()
