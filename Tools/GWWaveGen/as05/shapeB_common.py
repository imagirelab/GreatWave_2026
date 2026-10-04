# -*- coding: utf-8 -*-
"""美術の見本05 の形づくり・やり方 B（Q33、要求書 S11）の共通部：②・③ を主役波の行の中の「段（棚）」にする。py -3.10（numpy・scipy・OpenCV）。

- 土台：見本04 の最後の主役波 K*′ AS04F の t*（行 240 × 列 400）。行 c ≥ −8 m（いちばん高い峰、K-top）は変えない。
- 断面の座標（kh_common）：a = 進行方向（+ が前・原画のカメラの側）、y = 高さ、c = 波峰線（+ が原画視点の右・奥）。
- 原画のカメラは、段の縁の頂の置き場（原画の ②・③ の爪の群れの上の縁の射線の上）と測りにだけ使う。色は面へ写さない（Q28・G1）。
- 参照モデルの OBJ・写真は読まない。数は調べ（Unity/Build/Polish/sample05/study/targets.json）から取る。
出力はすべて Git 対象外の Unity/Build/Polish/sample05/shapeB/ の下。やり方 A の置き場（sample05/shapeA）には触れない。
"""
import hashlib
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as05", "Tools/GWWaveGen/as04", "Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h", "Tools/GWWaveGen/kstar_p28",
           "Tools/GWWaveGen/as02"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import s5_common as S5  # noqa: E402
import shape_common as SC  # noqa: E402

K = S5.K
H0 = S5.H0
P = REPO + "/Unity/Build/Polish"
OUT = P + "/sample05/shapeB"
ROWS04F = S5.ROWS04F
WAVE4_F1 = S5.WAVE4_F1
J_B, J_TOP, J_TIP, J_CORNER, J_FACEBOT = 18, 90, 200, 314, 379
C_KTOP = -8.0        # 行 c ≥ −8 m は見本04 のまま（K-top）
# 進行役が読んだ層の頂（爪の群れの上の縁）の線（原画の画素。調べ s5_diag.READ_CREST と同じ点）
READ_CREST = {"r2": [(650, 1010), (780, 950), (930, 930), (1060, 935), (1180, 930), (1300, 960), (1400, 1010)],
              "r3": [(20, 1270), (100, 1120), (230, 1080), (380, 1090), (500, 1110), (600, 1150)]}


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


_CAM = {}


def ray_dir(x_ref, y_ref):
    """原画の画素 (x, y) の射線の向き（Unity のワールド、単位）。"""
    if "cam" not in _CAM:
        _CAM["cam"] = S5.painting_cam()
    cam = _CAM["cam"]
    d = S5.S4.ref_to_disp(np.array([x_ref, y_ref], float))
    D = np.asarray(cam.ray(np.array(d[0]), np.array(d[1])), float).reshape(-1)[-3:]
    return D / np.linalg.norm(D)


def ray_point(x_ref, y_ref, dist):
    """原画の画素の射線の上で、原画のカメラから dist m の点（断面の座標 a, y, c）。"""
    q = K.sec((K.CAM_POS_U + dist * ray_dir(x_ref, y_ref))[None])[0]
    return q


def crest_curve(key, dist, n=200, dy_px=0.0):
    """原画の層の頂の線（READ_CREST[key]、原画の画素）を細かくし、各点の射線の上で dist m の点（a, y, c）を返す。
    dist はスカラーか、x の関数（callable）。dy_px は原画の画素で下へずらす量（＋ で下＝低く）。"""
    pts = np.array(READ_CREST[key], float)
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    t = np.linspace(0, s[-1], n)
    xs = np.interp(t, s, pts[:, 0]); ys = np.interp(t, s, pts[:, 1]) + dy_px
    out = []
    for x, y in zip(xs, ys):
        d = dist(x) if callable(dist) else dist
        out.append(ray_point(x, y, d))
    return np.array(out), xs, ys


def load_rows(p=ROWS04F):
    return SC.load_rows(p)


def ss(x):
    return SC.ss(x)
