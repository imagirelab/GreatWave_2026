# -*- coding: utf-8 -*-
"""部 A の面の座標（Build/Polish/sample01/param/s01_param_f32.bin、README.md の約束：頂点ごとの float32 × 8 = u, w, gu, gw, X.xyz, q）を読む。
U = u（巻きの向きの弧長 m、頂の列で 0、唇・前面の側が正）、V = w（頂に並ぶ向き m、|∇w| ≈ 1）。"""
import os

import numpy as np

import s01b_common as S

PARAM_DIR = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/param"
BIN = os.path.join(PARAM_DIR, "s01_param_f32.bin")


def load_full():
    return np.fromfile(BIN, np.float32).reshape(-1, 8).astype(np.float64)


def load():
    a = load_full()
    return np.stack([a[:, 0], a[:, 1]], 1), dict(source="part A s01_param_f32.bin (u, w)", path=BIN, sha256=S.sha256(BIN))
