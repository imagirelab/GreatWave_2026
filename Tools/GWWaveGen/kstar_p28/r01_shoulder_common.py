# -*- coding: utf-8 -*-
"""仕上げ28修正01 の案 SHOULDER（肩）の共通部。py -3.10（numpy・OpenCV・PIL）。

なぜ（Polish_28 第 9 節の限界 1、進行役の決定 2026-10-01）：後ろから見たドーム（頭巾）は、原画の頂（行 c ≲ +1.4 の列 79〜107）を
動かさずには消えない、と仕上げ28 で記録した。ただ、原画のカメラから見て輪郭の縁（rim）より奥の殻（背の列 0..〜80 と、奥の行の頂・唇の上）は
原画視点で見えず、空の射線の禁止域の下なら自由に形を変えられる。案 SHOULDER は、原画の頂をそのままにして、その見えない背の殻を
c 方向に少しずつ外・後ろへずらし（3 次元でなめらかに）、後ろから見て丸い頭巾でなく、奥の端へ長く下る肩に読ませる。
座標は kh_common と同じ（a = 進行方向 T、y = 高さ、c = 波峰線 E）。土台は採用中の K*′ P28R2rec（変えない）。
出力はすべて Unity/Build/Polish/28r01/shoulder/ の下（Git 対象外）。参照モデルは生成器では読まない（F13-1）。
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for _p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import r2_common as R  # noqa: E402

KC = R.KC
OUT = os.path.join(REPO, "Unity", "Build", "Polish", "28r01", "shoulder")
P28 = os.path.join(REPO, "Unity", "Build", "Polish", "28")
BASE_DIR = os.path.join(P28, "kstar_p28rec")
BASE_ROWS = os.path.join(BASE_DIR, "kstarP28R2rec_a45_rows.npz")
BASE_GWB = os.path.join(BASE_DIR, "kstarP28R2rec_a45.gwb")
BASE_SHA = {"gwb": "a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94",
            "rows": "c55e048d388e41e30289d075089066c481bf2f3b99d84727c655eea9e1a437a3"}
R4_ROWS = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz")
KEEPOUT_CACHE = os.path.join(P28, "r2", "cache", "keepout_d3.npz")       # 空の射線の禁止域（第2回と同じ、読むだけ）
KEEPOUT0_CACHE = os.path.join(P28, "r2", "cache", "keepout_d0.npz")
PROTECT_CACHE = os.path.join(P28, "rec", "cache", "protect_grids.npz")   # 船・手前の海の射線の禁止域（回復と同じ、読むだけ）


def load_rows(p=BASE_ROWS):
    z = np.load(p)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def sha256(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
