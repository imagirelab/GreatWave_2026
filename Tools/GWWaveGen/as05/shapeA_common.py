# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A（Q33：三つの層を形で分ける）の共通部。py -3.10（numpy・scipy・OpenCV）。

- 地にする形：見本04 の最後（主役波 K*′ AS04F の t* の行 240 × 列 400 ＋ wave4 fix1）。その写しを作り直す（見本04 のファイルは変えない）。
- 断面の座標（kh_common）：a = 進行方向 T（+ が前・原画のカメラの側）、y = 高さ、c = 波峰線 E（+ が原画視点の右・奥）。
- 原画のカメラは、層の頂を置く射線と測りにだけ使う。色は面へ写さない（Q28・G1）。参照モデルの OBJ・写真は読まない。
出力はすべて Git 対象外の Unity/Build/Polish/sample05/shapeA/ の下。
"""
import hashlib
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as05", "Tools/GWWaveGen/as04", "Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h", "Tools/GWWaveGen/as02",
           "Tools/GWWaveGen/as03"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import shape_common as SC  # noqa: E402
import s4_common as S4  # noqa: E402

K = SC.K
CC = SC.CC
H0 = SC.H0
P = REPO + "/Unity/Build/Polish"
P4 = P + "/sample04"
OUT = P + "/sample05/shapeA"
ROWS04F = P4 + "/fix1/shape/final/cand/kstarAS04F_a45_rows.npz"
GWB04F = P4 + "/fix1/shape/final/cand/kstarAS04F_a45.gwb"
WAVE4_F1 = P4 + "/wave4/mesh_fix1/wave4.json"
NAME = "kstarAS05A_a45"
CAND = OUT + "/hero/cand/" + NAME
ROWS05A = CAND + "_rows.npz"
GWB05A = CAND + ".gwb"
L3_JSON = OUT + "/l3/layer3.json"
CAM_SEC = K.sec(K.CAM_POS_U[None])[0]
# 一艘目の船（boat_left）：Unity の根の位置（AF27 の配置、見本05 の調べの K-boat）
BOAT_U = np.array([-15.29, 4.82, -12.53])


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jdump(p, o):
    SC.jdump(p, o)


def rnd(v, k=3):
    return SC.rnd(v, k)


def ss(x):
    return SC.ss(x)


def wwin(c, full, blend):
    """c の窓の重み：full の中で 1、blend の外で 0、間は smoothstep。"""
    (f0, f1), (b0, b1) = full, blend
    return ss((c - b0) / max(f0 - b0, 1e-9)) * ss((b1 - c) / max(b1 - f1, 1e-9))


def painting_cam():
    return CC.painting_cam()


def ray_point(x_ref, y_ref, dist):
    """原画の画素（3859×2594）の射線の、原画のカメラから dist m の点（断面の座標 a, y, c）。"""
    cam = painting_cam()
    xd, yd = S4.ref_to_disp(np.array([x_ref, y_ref], float))
    d = cam.ray(np.array([xd]), np.array([yd]))[0]
    return K.sec((cam.pos + dist * d)[None])[0]


def sec_to_world(Q):
    Q = np.atleast_2d(np.asarray(Q, float))
    return K.O[None, :] + Q[:, 0:1] * K.T[None, :] + Q[:, 1:2] * K.UP[None, :] + Q[:, 2:3] * K.E[None, :]
