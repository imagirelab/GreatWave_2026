# -*- coding: utf-8 -*-
"""美術の見本01 B：面の座標（頂点ごとの U・V、m）を読む。
- 部 A の面の座標（Build/Polish/sample01/param、README.txt の約束）があればそれを使う（load_param_a）。
- 無い間の開発の仮：仕上げ29 の弧長 (sa, ca)（pl29_hero_attr.py --param arc の B.x・C.w）。管の中で斜めにずれる（異方性 p95 17.6）ので、見本には使わない。"""
import json
import os

import numpy as np

import s01b_common as S

PARAM_DIR = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/param"


def load_provisional():
    A = S.load_attr29()
    return np.stack([A[:, 4], A[:, 11]], 1), dict(source="provisional pl29 (sa, ca)", sha256=S.sha256(S.ATTR29))


def load(kind="auto"):
    if kind in ("auto", "a"):
        f = os.path.join(PARAM_DIR, "s01_param_f32.bin")
        if os.path.exists(f):
            import s01b_param_a
            return s01b_param_a.load()
        if kind == "a":
            raise FileNotFoundError(f)
    return load_provisional()
