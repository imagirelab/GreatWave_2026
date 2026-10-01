# -*- coding: utf-8 -*-
"""仕上げ31：仕上げ29 の主役波の材質（PL29 Ukiyoe Keypose）が t* で白にする範囲（白の範囲 zZone）を、頂点ごとの面の座標から numpy で作る。

シェーダー `Unity/Assets/GreatWave/Polish29/Shaders/PL29_Ukiyoe_Hero.shader` の frag の「白の範囲」と同じ式（背の境 b(c)・前の白の終わり F_end(c)・
爪の指の房・縁の泡の小さな舌・唇の先・背の足・低い行）。値は `Tools/GWWaveGen/pl29/pl29_material_params.txt`（PL29Render と同じ写し）。
違うところ（記録する）：
  - 画面の画素で舌・切れ込みを消す所（_FeaturePx）は、視点で変わるので入れない（k = 1。どの視点でも近い所の形）。
  - 房の不揃いの Hash1 = frac(sin(x·127.1 + 311.7)·43758.5453) は float32 で計算するが、GPU の sin の近似と同じ値にはならない。
    房の並び（周期・長さ・幅の範囲）は同じで、どの房が長いかの割り当てだけが違う。白の割合の時間の変化を数えるのに使う。
原画カメラの投影は使わない（Q28）。白の時刻 T_white は別（pl31_white.py）。
"""
import os

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
PARAMS = REPO + "/Tools/GWWaveGen/pl29/pl29_material_params.txt"
ATTR = REPO + "/Unity/Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin"


def load_params(path=PARAMS):
    p = {}
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        k, v = line.split("=", 1)
        vals = [float(x) for x in v.split(",")]
        p[k.strip()] = np.array(vals + [0.0] * (4 - len(vals)) if len(vals) > 1 else vals, dtype=np.float64)
    return p


def load_attr(path=ATTR, n=96000):
    a = np.fromfile(path, dtype="<f4").reshape(n, 12).astype(np.float64)
    return dict(F=a[:, 0], hrel=a[:, 1], kc=a[:, 2], hrow=a[:, 3], s=a[:, 4], c=a[:, 5], dtip=a[:, 6], dtop=a[:, 7],
                n=a[:, 8:11], ca=a[:, 11])


def hash1(x):
    x = np.asarray(x, dtype=np.float32)
    v = np.sin(x * np.float32(127.1) + np.float32(311.7)).astype(np.float32) * np.float32(43758.5453)
    return (v - np.floor(v)).astype(np.float64)


def lobe_profile(u, w):
    x = (u - 0.5) / np.maximum(0.5 * np.clip(w, 0, 1), 1e-3)
    return np.sqrt(np.clip(1.0 - x * x, 0, 1))


def back_b(c, p):
    k, b = p["_BackC"], p["_BackB"]
    r = np.full_like(c, b[3])
    r = np.where(c <= k[3], b[2] + (b[3] - b[2]) * (c - k[2]) / max(k[3] - k[2], 1e-3), r)
    r = np.where(c <= k[2], b[1] + (b[2] - b[1]) * (c - k[1]) / max(k[2] - k[1], 1e-3), r)
    r = np.where(c <= k[1], b[0] + (b[1] - b[0]) * (c - k[0]) / max(k[1] - k[0], 1e-3), r)
    r = np.where(c <= k[0], b[0], r)
    return r


def smoothstep01(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def front_end(c, p):
    kc = list(p["_FrontC0"]) + list(p["_FrontC1"])
    ke = list(p["_FrontE0"]) + list(p["_FrontE1"])
    r = np.full_like(c, ke[0])
    for j in range(7):
        t = smoothstep01((c - kc[j]) / max(kc[j + 1] - kc[j], 1e-3))
        r = np.where(c > kc[j], ke[j] + (ke[j + 1] - ke[j]) * t, r)
    return r


def zone(A, p):
    """白の範囲の符号付きの値（面の座標の単位。正が白）。A は面の座標の辞書（頂点の値か、三角形の中で線形に補った値）。"""
    F, hrel, c, ca, dtip, hrow = A["F"], A["hrel"], A["c"], A["ca"], A["dtip"], A["hrow"]
    bw = p["_BackWave"]
    wave = bw[0] * np.sin(2 * np.pi * ca / max(bw[1], 0.1))
    zBack = hrel - (back_b(c, p) + wave)
    fe = front_end(c, p)
    beyond = np.maximum(F - fe, 0.0)
    fg, fg2, fg3, fr = p["_Finger"], p["_Finger2"], p["_Finger3"], p["_Fringe"]
    cl = ca + fg[3] * beyond * beyond
    tongue = np.zeros_like(F)
    if fg2[3] > 0.5:
        P = max(fg[0], 0.1)
        fi = np.floor(cl / P)
        u = cl / P - fi
        ln = fg[1] * (1.0 - fg2[2] * hash1(fi + fg2[1]))
        wj = fg2[0] * (1.0 - fg3[0] * hash1(fi * 2.13 + fg2[1] + 4.7))
        uc = u - fg3[1] * (hash1(fi * 3.71 + fg2[1] + 1.3) - 0.5)
        prof = lobe_profile(uc, wj)
        tongue = ln * prof - fg[2] * (1.0 - prof)
    if fr[3] > 0.5:
        Pf = max(fr[0], 0.05)
        cf = cl + 0.37 * Pf
        ff = np.floor(cf / Pf)
        uf = cf / Pf - ff
        pf = lobe_profile(uf, 0.75)
        lf = fr[1] * (0.6 + 0.8 * hash1(ff * 1.7 + 5.3))
        tongue = tongue + lf * pf - fr[2] * (1.0 - pf)
    edgeF = fe + tongue
    zFront = edgeF - F
    z = np.where(F < 1.0, zBack, zFront)
    z = np.maximum(z, float(p["_TipFoam"][0]) - np.abs(dtip))
    z = np.minimum(z, F + 0.25)
    z = np.minimum(z, hrow - float(p["_MinRowH"][0]))
    return z, edgeF


def zone_robust(A, p):
    """白の範囲の下限（仕上げ31 修正01）：房の不揃いの Hash1 がどの値でも白の範囲に入るか。GPU の sin は numpy と同じ値にならないので、
    放出点は Hash1 によらない所に限る。房の舌 ln·prof − _Finger.z·(1 − prof) は ln ≥ 0 なので −_Finger.z 以上（房の中心と幅が Hash1 で動くので
    prof はどの u でも 0 になりうる）。縁の泡の舌 lf·pf − _Fringe.z·(1 − pf) は pf が Hash1 によらず、lf ≥ 0.6·_Fringe.y。"""
    F, hrel, c, ca, dtip, hrow = A["F"], A["hrel"], A["c"], A["ca"], A["dtip"], A["hrow"]
    bw = p["_BackWave"]
    wave = bw[0] * np.sin(2 * np.pi * ca / max(bw[1], 0.1))
    zBack = hrel - (back_b(c, p) + wave)
    fe = front_end(c, p)
    beyond = np.maximum(F - fe, 0.0)
    fg, fg2, fr = p["_Finger"], p["_Finger2"], p["_Fringe"]
    assert fg2[2] <= 1.0 and fg[1] >= 0.0, "房の長さの下限が負になる値（下限の式の前提が崩れる）"
    cl = ca + fg[3] * beyond * beyond
    tongue = np.zeros_like(F)
    if fg2[3] > 0.5:
        tongue = tongue - fg[2]
    if fr[3] > 0.5:
        Pf = max(fr[0], 0.05)
        cf = cl + 0.37 * Pf
        uf = cf / Pf - np.floor(cf / Pf)
        pf = lobe_profile(uf, 0.75)
        tongue = tongue + 0.6 * fr[1] * pf - fr[2] * (1.0 - pf)
    zFront = fe + tongue - F
    z = np.where(F < 1.0, zBack, zFront)
    z = np.maximum(z, float(p["_TipFoam"][0]) - np.abs(dtip))
    z = np.minimum(z, F + 0.25)
    z = np.minimum(z, hrow - float(p["_MinRowH"][0]))
    return z


def tri_samples(n_sub=3):
    """三角形の中の重心座標の標本（n_sub 分割の小三角形の重心）。戻り値 (m, 3)。"""
    pts = []
    for i in range(n_sub):
        for j in range(n_sub - i):
            pts.append(((i + 1 / 3) / n_sub, (j + 1 / 3) / n_sub))
            if i + j < n_sub - 1:
                pts.append(((i + 2 / 3) / n_sub, (j + 2 / 3) / n_sub))
    b = np.array([(1 - a - b_, a, b_) for a, b_ in pts])
    return b


if __name__ == "__main__":
    p = load_params()
    A = load_attr()
    z, _ = zone(A, p)
    print("zone vertices", int((z > 0).sum()), "of", len(z))
