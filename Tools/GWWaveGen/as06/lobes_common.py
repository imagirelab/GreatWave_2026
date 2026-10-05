# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES の共通部（Q34：② b区域・③ 最左側の小区域を、① から左下へ下りる「体のある段」にする）。py -3.10（numpy・scipy・skimage・cv2）。

やり方（見本05 の行の道具と違う所）：
  見本05 の形 B は、行ごとの断面の制御点を作り直した（段の窓が狭く、② ③ に体がなかった）。見本06 は、② と ③ を
  3D の丸い塊（lobe）として、断面の座標 (a, y, c) の陰関数（符号つき距離）で作り、主役波の体と大きな丸み（滑らかな和）でつなぐ。
  その後、行 c ごとに陰関数の 0 の等値線を取り出し、見本05 と同じ 240 行 × 400 列の格子へ戻す（列の並び・境の輪・
  材質の属性の約束 sample04/mat/README.md はそのまま使える）。
  - 主役波の体の距離：各行の断面の折れ線（列 0..399）を海の下で閉じた多角形の、点ごとの距離（内が −）。
  - 塊の距離：塊ごとの「縁の頂の線」（原画の層の頂の線 READ_CREST の射線の上、原画のカメラから dist m）に沿って、
    行 c ごとに縁の頂 R(c) と断面の形（踏み面・溝・縁の頂・唇・唇の下の凹み・前へ出る下の面・裾）を置いた閉じた曲線の距離。
    塊の両端では形を体の中の点 Q(c) へ縮める（楕円の重み）ので、端は丸く体へ消える。
  - 合わせ方：多項式の滑らかな最小（smin、丸みの半径 k m）。溝（縁の後ろの鞍）は塊の形そのものに入れる。
座標：a = 進行方向（+ が前・原画のカメラの側）、y = 高さ、c = 波峰線（+ が原画視点の右奥）。H0 = 20.75 m。
原画のカメラは縁の頂の置き場と測りにだけ使う（色は写さない。G1）。参照モデルの OBJ・写真は読まない。
"""
import hashlib
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as05", "Tools/GWWaveGen/as04", "Tools/GWWaveGen/kstar_p28", "Tools/GWWaveGen/kstar_h"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import shapeB_common as B  # noqa: E402

P = REPO + "/Unity/Build/Polish"
OUT = P + "/sample06/lobes"
ROWS04F = B.ROWS04F                                                     # 見本04 の主役波（行 c ≥ −8 は見本05 B10 と同じ）
ROWS05B = P + "/sample05/fix1/B/final/cand/kstarAS05B_a45_rows.npz"     # 見本05 形 B の最後（B10）
WAVE4_F1 = B.WAVE4_F1
H0 = B.H0
C_KTOP = -8.0
J_B, J_TOP, J_TIP, J_CORNER, J_FACEBOT = 18, 90, 200, 314, 379


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


def rnd(v, k=3):
    return B.rnd(v, k)


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def smin(a, b, k):
    """多項式の滑らかな最小（Inigo Quilez）。k = 丸みの幅（m）。"""
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)
