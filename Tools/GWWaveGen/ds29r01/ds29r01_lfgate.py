# -*- coding: utf-8 -*-
"""設計29修正01（手渡し (d)）：原画の大きな輪郭の関門（132 σ12 最大・72 σ24 p95。設計28修正01 で採った読み）を Unity の画像から測る。

Unity の t* の色区 ID 画像（af28r01_class_ids.png、3840×2160、空 = (255, 255, 255)）の空の画素を 2×2 で平均して 1920×1080 の被覆にし、
設計28修正01 の関門 Tools/GWWaveGen/kstar_h/kh_gate_lfR4.LFGate にそのまま渡す（海の被覆は 0。ID 画像では海も空ではない）。
K*′ の幾何の値（設計28修正01 §4.1）：132 σ12 3.905 px、72 σ24 p95 3.746 px。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_lfgate.py [--run Unity/Build/Design/29R01/unity/f_final_kp ...]
出力：Unity/Build/Design/29R01/unity/lfgate_unity.json
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in ("Tools/PaintingTruth", "Tools/GWWaveGen", "Tools/GWWaveGen/kstar3", "Tools/GWWaveGen/kstar_h"):
    sys.path.insert(0, os.path.join(REPO, p))
os.chdir(REPO)
import kh_gate_lfR4 as LF  # noqa: E402
import cv2  # noqa: E402

KP_GEOM = {"132_sigma12_max": 3.905, "72_sigma24_p95": 3.746}
DEFAULT_RUNS = ["Unity/Build/Design/29R01/unity/f_final_kp", "Unity/Build/Design/29R01/unity/f_final", "Unity/Build/Design/28R01F/unity/F_final"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="*", default=DEFAULT_RUNS)
    a = ap.parse_args()
    gate = LF.LFGate()
    res = {"schema": "GreatWave.DS29R01.lfgate_unity/1", "method_ja": __doc__.strip(), "kstar_prime_geometry": KP_GEOM, "runs": {}}
    for run in a.run:
        pth = os.path.join(REPO, run, "t28", "render", "af28r01_class_ids.png")
        im = cv2.imdecode(np.fromfile(pth, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]
        H, W = im.shape[:2]
        sky = np.all(im == 255, axis=-1).astype(np.float64).reshape(H // 2, 2, W // 2, 2).mean((1, 3))
        lf = gate.measure(1.0 - sky, np.zeros_like(sky))
        r = {"132_sigma12_max": lf["132"]["max_px"], "132_worst_xy": lf["132"]["worst_xy"], "72_sigma24_p95": lf["72"]["p95_px"],
             "72_worst_xy": lf["72"]["worst_xy"], "ids": run + "/t28/render/af28r01_class_ids.png", "ids_sha256": sha256(pth)}
        r["diff_vs_kstar_prime_px"] = {k: round(r[k] - v, 4) for k, v in KP_GEOM.items()}
        r["gate_4px"] = {"132": r["132_sigma12_max"] <= 4.0, "72": r["72_sigma24_p95"] <= 4.0}
        res["runs"][run] = r
        print(run, {k: r[k] for k in ("132_sigma12_max", "72_sigma24_p95", "diff_vs_kstar_prime_px", "gate_4px")}, flush=True)
    out = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "unity", "lfgate_unity.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")


if __name__ == "__main__":
    main()
