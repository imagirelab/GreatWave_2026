# -*- coding: utf-8 -*-
"""仕上げ28（焼き直しと Unity の描画）：PL28Render（または DS29Render）が書いた t* の画像の組を、設計30・40 の回帰の評価器と同じ 3 つの読みで測る。
設計30 の ds30b_tstar_regress.py の手順を写し、K*′ の幾何の値・焼き込みの置き場所を引数にして、72 の大きな輪郭の σ12 の読みを足した（評価器のファイルは変えない）。

組（<scene>/<組>/t28/render/af28r01_*.png）ごとに：
  1) 評価器の定義のままの読み：pl28u_tstar_eval.py（= ds29r01_tstar_eval.py の固定値を引数にした写し。美術優先28修正01 の評価器）。
     色区の境界 73・77・79・118・120・133・134・175・263・270 と 265〜267（28修正01 の値と比べる）、輪郭 78／130／131（K*′ の幾何の値と比べる）、
     細部込みの 132 最大・72 p95（ID 画像の主役波の輪郭）。
  2) 大きな輪郭：132・72 を σ12（kh_gate_lf.LFGate。28修正01 の 1 回目の緩め。閉じる目安の「σ24 の緩めなし」）と σ24（kh_gate_lfR4.LFGate。
     28修正01 の 2 回目の緩め。段階5〜9 の関門の読み、記録）で。入力は af28r01_class_ids.png（3840×2160）の空の被覆を 2×2 で平均した 1920×1080。
  3) 輪郭の両側を除く読み（ds29r01_tstar_sym.py。設計29修正01 が採り、段階5〜9 が関門に使った読み。記録）。
組：t28_white（爪なし。仕上げ28 の関門の読み）、t28_claws（爪あり。爪は仕上げ32・33 まで合わせ直さないので、そのまま記録）。

使い方（リポジトリの根で。重い numpy の処理と同時に回さない）:
    py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/28/unity/scene_p28 --kstar p28 [--sets t28_white,t28_claws] [--no-sym]
出力：<scene>/pl28u_regress.json
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


_LF = {}


def lfgates(run):
    for p in ("Tools/PaintingTruth", "Tools/GWWaveGen", "Tools/GWWaveGen/kstar3", "Tools/GWWaveGen/kstar_h"):
        q = os.path.join(REPO, p)
        if q not in sys.path:
            sys.path.insert(0, q)
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        import cv2
        if not _LF:
            import kh_gate_lf as L12
            import kh_gate_lfR4 as L24
            _LF["s12"] = L12.LFGate()
            _LF["s24"] = L24.LFGate()
        pth = os.path.join(run, "t28", "render", "af28r01_class_ids.png")
        im = cv2.imdecode(np.fromfile(pth, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]
        H, W = im.shape[:2]
        sky = np.all(im == 255, axis=-1).astype(np.float64).reshape(H // 2, 2, W // 2, 2).mean((1, 3))
        out = {"ids": os.path.relpath(pth, REPO).replace("\\", "/"), "ids_sha256": sha256(pth)}
        for k, g in _LF.items():
            r = g.measure(1.0 - sky, np.zeros_like(sky))
            out[k] = {"132_max_px": round(r["132"]["max_px"], 4), "132_p95_px": round(r["132"]["p95_px"], 4),
                      "72_p95_px": round(r["72"]["p95_px"], 4), "72_max_px": round(r["72"]["max_px"], 4),
                      "132_worst_xy": r["132"]["worst_xy"], "72_worst_xy": r["72"]["worst_xy"]}
        return out
    finally:
        os.chdir(cwd)


def sym(run, out):
    sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds29r01"))
    import ds29r01_tstar_sym as S
    S.KP_T28 = os.path.join(run, "t28")
    S.OUT = out
    os.makedirs(out, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        S.main()
    finally:
        os.chdir(cwd)
    return load(os.path.join(out, "tstar_sym.json"))


def strict_summary(run, verdict_name):
    v = load(os.path.join(run, verdict_name))
    R = load(os.path.join(run, "ds27_tstar_remeasure.json"))
    items = {k: {"max_now_px": e.get("max_now_px", e.get("now_max_px")), "worst_measure": e["worst_measure"], "now_at_worst_px": e["now_max_px"],
                 "r28r01_at_worst_px": e["r28r01_max_px"], "worst_abs_diff_vs_28r01_px": round(e["worst_abs_diff_px"], 4), "verdict": e["verdict_now"],
                 "verdict_28r01": e["verdict_28r01"]}
             for k, e in v["colour_boundaries"]["items"].items()}
    c = R["colour_265_266_267"]
    col = {"265_dE00": c["265"]["ds27"].get("dE00"), "265": c["265"]["ds27_verdict"], "266": c["266"]["ds27_verdict"], "267": c["267"]["ds27_verdict"],
           "267_bands_ge_20px": {vw: c["267"]["ds27"]["views"]["white"][vw]["bands_ge_20px"] for vw in ("painting_view", "seat_view", "seat_low_view")}}
    sil = {s["item"]: {"max_px": s["ds27_max_px"], "p95_px": s["ds27_p95_px"]} for s in R["silhouettes_vs_26r01_28r01"]}
    return {"colour_items": items, "colour_265_267": col, "items_over_0p5_vs_28r01": v["colour_boundaries"]["items_over_0p5"],
            "verdict_changes_vs_28r01": v["verdict_changes_vs_28r01"], "silhouettes_definition_reading": sil,
            "silhouettes_vs_kstar_prime_geometry": v["silhouettes_vs_kstar_prime"], "pass_colour": v["pass_colour"], "pass_silhouette": v["pass_silhouette"],
            "summary_verdicts": R.get("summary_verdicts_ds27")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--kstar", required=True, choices=["p28", "r4", "rec"])
    ap.add_argument("--sets", default="t28_white,t28_claws")
    ap.add_argument("--no-sym", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="評価器の定義のままの読みの出力があれば回し直さない")
    a = ap.parse_args()
    scene = os.path.join(REPO, a.scene)
    res = {"schema": "GreatWave.Polish28.tstar_regress/1", "number": "仕上げ28（焼き直しと Unity の描画）", "scene": a.scene, "kstar": a.kstar,
           "method_ja": __doc__.strip(), "sets": {}}
    for s in a.sets.split(","):
        run = os.path.join(scene, s) if s != "." else scene
        if not os.path.isdir(os.path.join(run, "t28", "render")):
            print("skip", s)
            continue
        rel = os.path.relpath(run, REPO).replace("\\", "/")
        if not (a.reuse and os.path.exists(os.path.join(run, "pl28u_tstar_verdict.json"))):
            subprocess.run([sys.executable, "-B", os.path.join(HERE, "pl28u_tstar_eval.py"), "--run", rel, "--kstar", a.kstar], check=True, cwd=REPO)
        e = {"strict": strict_summary(run, "pl28u_tstar_verdict.json"), "large_form": lfgates(run),
             "t28_sha256": {f: sha256(os.path.join(run, "t28", "render", f)) for f in sorted(os.listdir(os.path.join(run, "t28", "render")))
                            if f.startswith("af28r01_") and f.endswith(".png") and "rule28" not in f and "side" not in f and "back" not in f}}
        if not a.no_sym:
            sy = sym(run, os.path.join(scene, "tstar_sym_" + (s if s != "." else "run")))
            e["sym"] = {"worst_abs_diff_px": sy["worst_abs_diff_px"], "pass": sy["pass"],
                        "rows": [{"item": r["item"], "measure": r["measure"], "kp_sym_max_px": r["kp_sym_max_px"], "diff_px": r["diff_px"]} for r in sy["rows"]],
                        "flat_painting_view_266_267": {k: (sy["flat_painting_view_266_267"]["kp"][k]["sym"] or {}).get("bands_ge_20px")
                                                       for k in ("white", "mizuiro", "ai_mid", "ai_dark")}}
        res["sets"][s] = e
        print(s, json.dumps({"lf": {k: e["large_form"][k] for k in ("s12", "s24")},
                             "sil": e["strict"]["silhouettes_definition_reading"]}, ensure_ascii=False)[:900], flush=True)
    with open(os.path.join(scene, "pl28u_regress.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")
    print("PL28U_REGRESS_DONE", a.scene)


if __name__ == "__main__":
    main()
