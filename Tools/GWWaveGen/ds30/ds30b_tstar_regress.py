# -*- coding: utf-8 -*-
"""設計30 第B部：t*（t = 12 s）の原画視点の回帰を、設計29修正01 と同じ 3 つの読みで測る（評価器のファイルは変えない）。

DS30Render が <out>/<組>/t28/render/af28r01_*.png に書いた t* の画像の組ごとに：
  1) ds29r01_tstar_eval.py --run <out>/<組>（美術優先28修正01 の評価器。色区の境界は 28修正01 の値、輪郭 78／130／131 は K*′ の幾何の値と比べる）
  2) 大きな輪郭の関門（132 σ12 最大・72 σ24 p95。kh_gate_lfR4.LFGate を ds29r01_lfgate.py と同じ読みで。書き出し先だけ設計30 の出力にする）
  3) 輪郭の両側を除く読み（ds29r01_tstar_sym.py の関数を、入力と出力の置き場所だけ差し替えて呼ぶ）
組：t28（主役波の本体だけ。ID と _kstar は周りの海を隠す）、t28_seaids（ID と _kstar に周りの海と平らな海も入れる）。
t28_ctrl（海なし、29修正01 と同じ場面）は、10 枚の画像が 29修正01 の f_final_kp と画素まで同じことを SHA-256 で確かめる（同じ画像なので評価も同じ）。
設計29修正01 の値（Unity/Build/Design/29R01/unity/f_final_kp/ds29r01_tstar_verdict.json、tstar_sym/tstar_sym.json、lfgate_unity.json）と並べる。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/30/unity/single [--sets t28,t28_seaids]
出力：<out>/ds30_tstar_regress.json
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
R29 = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "unity")
IMAGES = ["af28r01_painting.png", "af28r01_seat.png", "af28r01_seat_low.png", "af28r01_painting_kstar.png", "af28r01_seat_kstar.png",
          "af28r01_seat_low_kstar.png", "af28r01_class_ids.png", "af28r01_seat_class_ids.png", "af28r01_seat_low_class_ids.png", "af28r01_line_ids.png"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def lfgate(run):
    for p in ("Tools/PaintingTruth", "Tools/GWWaveGen", "Tools/GWWaveGen/kstar3", "Tools/GWWaveGen/kstar_h"):
        sys.path.insert(0, os.path.join(REPO, p))
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        import kh_gate_lfR4 as LF
        import cv2
        pth = os.path.join(run, "t28", "render", "af28r01_class_ids.png")
        im = cv2.imdecode(np.fromfile(pth, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]
        H, W = im.shape[:2]
        sky = np.all(im == 255, axis=-1).astype(np.float64).reshape(H // 2, 2, W // 2, 2).mean((1, 3))
        lf = LF.LFGate().measure(1.0 - sky, np.zeros_like(sky))
        return {"132_sigma12_max": float(lf["132"]["max_px"]), "72_sigma24_p95": float(lf["72"]["p95_px"]), "ids_sha256": sha256(pth)}
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sets", default="t28,t28_seaids")
    ap.add_argument("--no-sym", action="store_true")
    a = ap.parse_args()
    out = os.path.join(REPO, a.out)
    res = {"schema": "GreatWave.DS30.tstar_regress/1", "number": "設計30 第B部", "method_ja": __doc__.strip(), "sets": {}}
    # 対照：29修正01 と画素まで同じか
    ctrl = os.path.join(out, "t28_ctrl", "t28", "render")
    if os.path.isdir(ctrl):
        same = {f: sha256(os.path.join(ctrl, f)) == sha256(os.path.join(R29, "f_final_kp", "t28", "render", f)) for f in IMAGES}
        res["ctrl_identical_to_29r01_f_final_kp"] = {"all": all(same.values()), "files": same}
    base = {"verdict": load(os.path.join(R29, "f_final_kp", "ds29r01_tstar_verdict.json")),
            "sym": load(os.path.join(R29, "tstar_sym", "tstar_sym.json")),
            "lfgate": load(os.path.join(R29, "lfgate_unity.json"))["runs"].get("Unity/Build/Design/29R01/unity/f_final_kp")}
    res["base_29r01"] = {"colour_worst_abs_diff_px": base["verdict"]["colour_boundaries"]["worst_abs_diff_px"],
                         "silhouettes_vs_kstar_prime": base["verdict"]["silhouettes_vs_kstar_prime"],
                         "sym_worst_abs_diff_px": base["sym"]["worst_abs_diff_px"], "lfgate": base["lfgate"]}
    for s in a.sets.split(","):
        run = os.path.join(out, s)
        if not os.path.isdir(run):
            continue
        rel = os.path.relpath(run, REPO).replace("\\", "/")
        subprocess.run([sys.executable, "-B", os.path.join(REPO, "Tools", "GWWaveGen", "ds29r01", "ds29r01_tstar_eval.py"), "--run", rel], check=True, cwd=REPO)
        v = load(os.path.join(run, "ds29r01_tstar_verdict.json"))
        e = {"verdict": {"colour_worst_abs_diff_px": v["colour_boundaries"]["worst_abs_diff_px"], "items_over_0p5": v["colour_boundaries"]["items_over_0p5"],
                         "silhouettes_vs_kstar_prime": v["silhouettes_vs_kstar_prime"], "verdict_changes_vs_28r01": v["verdict_changes_vs_28r01"],
                         "pass_colour": v["pass_colour"], "pass_silhouette": v["pass_silhouette"]},
             "lfgate": lfgate(run)}
        # 29修正01 の値との差（輪郭）
        e["silhouette_diff_vs_29r01_px"] = {k: round((r["unity_max_px"] or 0) - (base["verdict"]["silhouettes_vs_kstar_prime"]["rows"][k]["unity_max_px"] or 0), 4)
                                            for k, r in v["silhouettes_vs_kstar_prime"]["rows"].items()}
        e["lfgate_diff_vs_29r01_px"] = {k: round(e["lfgate"][k] - base["lfgate"][k], 4) for k in ("132_sigma12_max", "72_sigma24_p95")}
        if not a.no_sym:
            sy = sym(run, os.path.join(out, "tstar_sym_" + s))
            e["sym"] = {"worst_abs_diff_px": sy["worst_abs_diff_px"], "pass": sy["pass"], "over_0p5": [r for r in sy["rows"] if abs(r["diff_px"]) > 0.5],
                        "flat_painting_view_266_267": {k: {"sym_bands": (sy["flat_painting_view_266_267"]["kp"][k]["sym"] or {}).get("bands_ge_20px")}
                                                       for k in ("white", "mizuiro", "ai_mid", "ai_dark")}}
            # 29修正01 の sym の行と同じ測りの差
            b = {(r["item"], r["measure"]): r["kp_sym_max_px"] for r in base["sym"]["rows"]}
            d = [(r["item"], r["measure"], round(r["kp_sym_max_px"] - b[(r["item"], r["measure"])], 4)) for r in sy["rows"] if (r["item"], r["measure"]) in b]
            e["sym"]["worst_diff_vs_29r01_px"] = max((abs(x[2]) for x in d), default=0.0)
            e["sym"]["diff_vs_29r01_over_0p5"] = [x for x in d if abs(x[2]) > 0.5]
        res["sets"][s] = e
        print(s, json.dumps({k: e[k] for k in ("lfgate", "silhouette_diff_vs_29r01_px", "lfgate_diff_vs_29r01_px")}, ensure_ascii=False), flush=True)
    with open(os.path.join(out, "ds30_tstar_regress.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")


if __name__ == "__main__":
    main()
