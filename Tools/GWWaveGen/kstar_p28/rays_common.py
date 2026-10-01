# -*- coding: utf-8 -*-
"""仕上げ28 第1回（射線の案 RAYS）の共通部。py -3.10（numpy だけ。hython からも読める部分は numpy だけ）。

射線の案：原画視点の左の輪郭（78・130・131）を作る稜の点を、原画カメラの射線の上で奥行きだけ配り直し、
後ろから見て 1 本のなめらかな単調な曲線（稜の背骨）にする。体の断面はその背骨から作り直す。
格子 400×240 の並び・目印の列・UV は K*′ R4 と同じに保つ（動き・焼き込み・爪・色の当て直しのため）。

座標は kh_common と同じ（Unity ワールド、断面座標 a = 進行方向 T、y = 高さ、c = 波峰線 E）。
出力はすべて Unity/Build/Polish/28/r1_rays/ の下（Git 対象外）。参照モデルは生成器では読まない（F13-1）。
"""
import os
import sys
import json
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
KH = os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h")
if KH not in sys.path:
    sys.path.insert(0, KH)
import kh_common as KC  # noqa: E402

OUT = os.path.join(REPO, "Unity", "Build", "Polish", "28", "r1_rays")
R4_DIR = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final")
R4_ROWS = os.path.join(R4_DIR, "kstarR4_a45_rows.npz")
R4_GWB = os.path.join(R4_DIR, "kstarR4_a45.gwb")
R4_META = os.path.join(R4_DIR, "kstarR4_a45_meta.json")
R4_SHA = {"gwb": "38a9b11ab63cccb45cf2cb7776ae3a59485d58102e96cabaf828fb36d14cf19a",
          "rows": "a0c256d221f5a3e026f3ff0135481e5a7075daaa57832d2ab4884772b8e79e46",
          "meta": "b8d6752bdf1a4df8106ffe7e3a96addfa9b04d2c9cab1cb71f4cf7df0ad7f943"}
CAM = KC.CAM_POS_U.copy()


def load_r4():
    z = np.load(R4_ROWS)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def world(c, A, Y):
    return KC.world(c, A, Y)


def sec(P):
    return KC.sec(P)


def project(P):
    """Unity world (..., 3) -> display px (x, y) and depth cz."""
    P = np.asarray(P, float)
    sh = P.shape[:-1]
    q = KC.project_unity(P.reshape(-1, 3))
    return q.reshape(sh + (3,))


def ray_dir_sec(P):
    """原画カメラから点 P（Unity）への単位方向を断面座標 (da, dy, dc) で返す。"""
    d = np.asarray(P, float) - CAM
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    return np.stack([d @ KC.T, d[..., 1], d @ KC.E], -1)


def slide_on_ray(P, dc):
    """点 P（Unity）を原画カメラの射線の上で、c が dc だけ変わるまで動かす（像は変わらない）。"""
    P = np.asarray(P, float)
    d = P - CAM
    de = d @ KC.E
    t = 1.0 + dc / de
    return CAM + t[..., None] * d


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
