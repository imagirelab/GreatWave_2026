# -*- coding: utf-8 -*-
"""Basilisk の窓のコマを、原画と同じ物差し（Tools/GWWaveGen/ruler の s52_shape.measure_mask）で測る。

- 長さの尺度：h0 = 19 m（本作の FLIP の実験と同じ）。格子は 0.05 m（s52_shape.FINE）。
- 水の 2 値：f の双一次の補間 > 0.5。海底の固体（cs < 0.5）は水として埋める
  （底につながる水を選ぶため。量はどれも静かな水面より上で読むので、固体を水と数えても変わらない）。
- 底につながる水だけを残す（s52_shape.flip_mask と同じ：4 近傍のつながり、いちばん下の行のラベル）。
- score3：前の面の弦の角度・前の足・覆いの面積の 3 つについて、許す帯の外の距離 ÷ 原画の値（1 を上限）の和。
  0 は 3 つとも帯の中。帯は 2026-10-13 の雲の計算の指令の値。
"""
import os, sys, json, math
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ruler"))
import s52_shape as S  # noqa: E402
from skimage import measure  # noqa: E402

H0M = 19.0
FINE = S.FINE

_P = json.load(open(os.path.join(REPO, "Tools", "GWWaveGen", "ruler", "shape_measures.json"), encoding="utf8"))["print"]["cn"]
PRINT = {k: _P[k] for k in ("face_chord_deg_01_05", "front_x01_rel", "hood_area", "gap_max", "lip_thick_mid",
                            "back_angle_07_09_deg", "width07_silhouette")}
# 許す帯（指令の値）。gap_max は下限だけ
BANDS = {"face_chord_deg_01_05": (60.5, 78.0), "front_x01_rel": (0.18, 0.28), "hood_area": (0.143, 0.229),
         "gap_max": (0.49, None), "lip_thick_mid": (0.32, 0.39)}
SCORE_KEYS = ("face_chord_deg_01_05", "front_x01_rel", "hood_area")


def frame_mask(fr, back_m=105.0, front_m=105.0, zlow_m=-12.0, ztop_pad_m=1.5):
    """窓のコマ（gwread.read_frame）から、0.05 m の水の 2 値 M[z, x] と X・Z（m）を作る。"""
    f, cs = fr["f"], fr["cs"]
    dx = fr["dx"] * H0M
    x0 = fr["x0"] * H0M
    y0 = fr["y0"] * H0M
    ny, nx = f.shape
    # 頂のおおよその位置（粗い格子で、水の最も高い行）
    wet = (f > 0.5) & (cs > 0.5)
    lab = measure.label(wet | (cs < 0.5), connectivity=1)
    keep = lab[0][lab[0] > 0]
    if len(keep):
        wet = wet & (lab == np.bincount(keep).argmax())
    rows = np.where(wet.any(1))[0]
    jt = rows.max()
    xc0 = x0 + dx * np.where(wet[jt])[0].mean()
    ztop = y0 + dx * jt
    X = np.arange(max(xc0 - back_m, x0), min(xc0 + front_m, x0 + dx * (nx - 1)), FINE)
    Z = np.arange(max(zlow_m, y0), min(ztop + ztop_pad_m, y0 + dx * (ny - 1)), FINE)
    gi = (X - x0) / dx
    gj = (Z - y0) / dx
    JJ, II = np.meshgrid(gj, gi, indexing="ij")
    F = ndimage.map_coordinates(f, [JJ, II], order=1, mode="nearest")
    CS = ndimage.map_coordinates(cs, [JJ, II], order=1, mode="nearest")
    M = (F > 0.5) | (CS < 0.5)
    lab = measure.label(M, connectivity=1)
    keep = lab[0][lab[0] > 0]
    if len(keep):
        M = lab == np.bincount(keep).argmax()
    return M, X, Z


def score3(m):
    s = 0.0
    parts = {}
    for k in SCORE_KEYS:
        v = m.get(k, float("nan"))
        lo, hi = BANDS[k]
        if v is None or not np.isfinite(v):
            d = 1.0
        else:
            d = 0.0
            if lo is not None and v < lo:
                d = (lo - v) / abs(PRINT[k])
            if hi is not None and v > hi:
                d = (v - hi) / abs(PRINT[k])
            d = min(1.0, d)
        parts[k] = d
        s += d
    return s, parts


KEEP = ("eta_c", "x_c", "face_chord_deg_01_05", "front_x01_rel", "hood_area", "gap_max", "gap_max_is_lower_bound",
        "gap_under_tip", "lip_thick_mid", "back_angle_07_09_deg", "width07_silhouette", "reach", "hood_height", "hood",
        "steep60_frac", "front_x05_rel", "back_x07_rel", "face_concavity_01_05", "tip_z", "hood_low_z")


def measure_frame(fr):
    """1 コマを測る。戻り値：物差しの量（長さは η_c で割った値、η_c と x_c は m）と score3。"""
    M, X, Z = frame_mask(fr)
    try:
        m = S.measure_mask(M, X, Z)
    except Exception as e:  # 形が物差しの前提に合わない（頂の近くに水がない等）
        return dict(t=fr["t"], error=repr(e))
    out = {k: (float(m[k]) if isinstance(m.get(k), (int, float, np.floating)) and not isinstance(m.get(k), bool) else m.get(k))
           for k in KEEP if k in m}
    sc, parts = score3(m)
    out.update(t=fr["t"], score3=sc, score3_parts=parts)
    return out
