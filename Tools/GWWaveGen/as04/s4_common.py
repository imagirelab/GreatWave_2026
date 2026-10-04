# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S（Q32）の共通部。py -3.10（numpy・scipy・OpenCV）。

- 主役波 K*' AS02C（見本02・03 の t* の形。行 240 × 列 400。行 = c 一定の断面、列 = 背の根元 → 頂 → 唇の先 → 唇の下 → 前の面）。
- 断面の座標（kh_common：a = 進行方向 T、y = 高さ、c = 波峰線 E。+c は原画視点の右・奥）。
- 原画の画素（DP130155、3859×2594）と表示の画素（1920×1080）の写像、利用者の区域の多角形（Q32）。
- 見直しの視点（claws_common の VIEWS：原画・座席・座席から波・左右の側面・後ろ 65°・真上）。
原画の色は面へ写さない（Q28）。原画のカメラは、原画の区域を面の行・列へ結ぶ測りにだけ使う。参照モデルの OBJ は読まない（F13-1）。
出力はすべて Git 対象外の Unity/Build/Polish/sample04/map/ の下。
"""
import hashlib
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import claws_common as CC  # noqa: E402
import kh_common as K  # noqa: E402

U = CC.U
OUT = REPO + "/Unity/Build/Polish/sample04/map"
TMP = OUT + "/tmp"
HERO_PKG = REPO + "/Unity/Build/Polish/sample02/fix01/assemble/hero_pkg_AS02C"
ROWS = REPO + "/Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz"
S2MAP = REPO + "/Unity/Build/Polish/sample03/study/tmp/s2_map.npz"
SEA_NEAR = REPO + "/Unity/Build/Polish/30/sea/near/ds30_tstar.gwb"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
OUTLINE_ENV = REPO + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json"
SCULPT_SPEC = REPO + "/Unity/Build/Polish/sample03/study/sculpture_spec.json"
H0 = 20.752853190871733
J_B, J_TOP, J_TIP, J_CORNER, J_FACEBOT, J_E = 18, 90, 200, 314, 379, 394
A_DISP = 0.4163454124903624
OFFX = 156.66152659984573

# ---------------------------------------------------------------- 利用者の区域（原画の画素。Q32）
# ①②③：進行役が描き、利用者が「对」と答えた多角形（scratchpad q32/annot.py と同じ点）。
REG1 = [(851, 700), (900, 420), (1150, 300), (1450, 250), (1900, 330), (2290, 700), (2297, 1130), (1950, 1134), (1700, 900),
        (1500, 700), (1300, 620), (1100, 760)]
REG2 = [(640, 960), (900, 900), (1180, 930), (1400, 1010), (1400, 1250), (1150, 1420), (850, 1400), (650, 1250)]
REG3 = [(2, 1110), (630, 1110), (630, 1849), (2, 1849)]
# ④：利用者が黄色の線で描き直した所（左端の小さな青い波の上の縁だけ）。
REG4 = [(0, 872), (97, 858), (233, 856), (360, 862), (350, 911), (214, 950), (97, 969), (0, 930)]
# 出っ張り：利用者の 1 枚目の切り出しの黄色の線。見本03 V1 の原画視点の描画（1920×1080 の表示の画素）で描かれた。
BULGE_DISP = [(551, 334), (624, 270), (720, 249), (840, 264), (891, 308), (865, 340), (789, 404), (739, 419), (662, 391), (586, 355)]
REGION_JA = {"r1": "①浪尖（頂と唇）", "r2": "②b区域", "r3": "③最左側の小区域", "r4": "④左端の小さな青い波の上の縁", "bulge": "出っ張り（S8）"}


def disp_to_ref(P):
    P = np.asarray(P, np.float64)
    return np.stack([(P[..., 0] + 0.5 - OFFX) / A_DISP - 0.5, (P[..., 1] + 0.5) / A_DISP - 0.5], -1)


def ref_to_disp(P):
    P = np.asarray(P, np.float64)
    return np.stack([A_DISP * (P[..., 0] + 0.5) - 0.5 + OFFX, A_DISP * (P[..., 1] + 0.5) - 0.5], -1)


def regions_ref():
    return {"r1": np.array(REG1, float), "r2": np.array(REG2, float), "r3": np.array(REG3, float), "r4": np.array(REG4, float),
            "bulge": disp_to_ref(np.array(BULGE_DISP, float))}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=_np)


def _np(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def rnd(v, k=3):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return round(float(v), k)


def load_hero():
    CC.HERO = HERO_PKG
    X0 = CC.load_hero()
    return X0


def rows_c():
    return np.load(ROWS)["c"].astype(np.float64)


def hero_sec(X0):
    """(R, C, 3) の Unity ワールド → (a, y, c)。"""
    return K.sec(X0.reshape(-1, 3)).reshape(X0.shape)


def outline_segments():
    d = json.load(open(OUTLINE_ENV, encoding="utf-8"))
    return {s["id"]: np.array(s["points_ref"], float) for s in d["segments"]}
