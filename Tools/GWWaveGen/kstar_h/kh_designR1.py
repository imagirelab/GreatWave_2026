# -*- coding: utf-8 -*-
"""設計28修正01 K*′（最後の一コマ）を Houdini で作るための断面の生成器（候補 H1A の精修 R1）。numpy だけ（hython と py -3.10 の両方）。

R1 で H1A（kh_designA.py）から変えた所（評審の must-fix に対して、形の手続きの側で直す）：
  * 側の縁の移動は、海面（y < 0.3 m）と低い行では 0（H1A では平らな海も視線をかすめるので縁の ramp で動き、c −60 の行に −0.74 m の谷、
    c +15 の行に 2.8 m の段ができていた）。
  * 列 314（j_corner）= 管の中の最も後ろの点（lean で回した後の a の最小。H1A は回す前の φ = 180° で、2〜3 m ずれていた）。
  * b 区域の谷は、その所の唇の厚みの 40% より深く押さない（H1A は薄い唇を谷が突き抜け、151 行で唇の上面と下面が交差していた）。
  * 検査の関数：lip_clearance（唇の上面と下面の符号つきの間隔）、section_selfx（断面の折れ線の自己交差）、top_excess（頂より高い点）。
以下は H1A の説明（そのまま）。


Houdini のネットワーク（kh_design_scene.py が作る /obj/kstar_h_design）の Python SOP がこの関数を呼び、
最適化（kh_fit.py）は同じ関数を Houdini の外で呼ぶ（同じ式なので同じ形。最後に Houdini で cook し橋で格子へ移して確かめる）。

断面（c 一定の行、a = 進行方向、y = 高さ）は「樽（管）の中心 B のまわりの同心の殻」:
  内の面（管）   r_in(φ)  = R (1 + e2 cos 2φ) − 鉤の引き込み h (1 − (φ − φtip)/span)²       φ ∈ [φtip, φend]
  外の面（背）   r_out(φ) = r_in(φ) + τ(φ)          τ = 殻の厚み（単調な 3 次、先 → 唇 → 頂 → 背 → 背の下）
  唇先           外と内を丸い先（3 次 Bezier）でつなぐ
  足             背の下（φbl）から凹の丸みで後ろの海へ（台座なし）
  前             管（φend）から前の谷の底 D へ、D から前の海 E へ（台座なし、谷あり）
頂（列 90）は外の面の最も高い点。形は H で割った比で作り、頂を (aT, H) に置く（H と aT が原画の側の縁を動かす）。
行の母数は c の関数（CTRL の ramp、数個の鍵、単調 3 次で補間）。
その後の 2 つの段（どちらも別の節点）:
  b 区域（左肩の第二の波頭）: 肩の行の唇の上面を法線の向きへ「谷 → 稜」に押す（3 つの房は c 方向のなだらかな山）
  側の縁の合わせ（edge）: 原画視点で輪郭を作る縁の列の帯だけを、法線の向きへ c のなめらかな ramp で動かす（中は動かさない）
列の目印（K* と同じ）: j_B 18 背の足 / j_top 90 頂 / j_tip 200 唇先 / j_corner 314 管の最も後ろ（φ = 180°）/
j_facebot 379 前の谷の底 / j_E 394 前の海の始まり。
"""
import math
import json
import numpy as np

NU, NV = 400, 240
SEGCOLS = [0, 18, 90, 200, 314, 379, 394, 399]
LM = {"j_B": 18, "j_top": 90, "j_tip": 200, "j_corner": 314, "j_facebot": 379, "j_E": 394}
C_LO, C_HI = -60.0, 18.0          # ramp の 0..1 に当てる c の範囲（R1：鍵が c +17 まであるので 18 に広げた。曲線は c の単位で同じ）
C_DENSE0, C_DENSE1, DC = -19.0, 15.0, 0.2

# 名前、既定値、単位・意味、下限、上限（CTRL の ramp の名前 = 名前）
PARAMS = [
    ("crest_height", 20.5, "H 頂の高さ [m]（原画の側の縁）", 0.0, 24.0),
    ("crest_a", 0.0, "aT 頂の a 位置 [m]（波峰線の平面、原画の側の縁）", -16.0, 8.0),
    ("tube_radius", 0.40, "R/H 管の半径", 0.15, 0.60),
    ("tube_oval", -0.10, "e2 管の楕円（+ = 横長、- = 縦長）", -0.30, 0.30),
    ("lean", 18.0, "殻全体の傾き [deg]（B のまわりの回転、+ = 頂が後ろ・唇先が上）", -20.0, 50.0),
    ("shell_top", 0.20, "τ/H 頂の殻の厚み（φ = 90°）", 0.03, 0.45),
    ("shell_back", 0.27, "τ/H 背の殻の厚み（φ = 180°）", 0.03, 0.55),
    ("shell_base", 0.48, "τ/H 背の下の殻（φbl、胴の裾）", 0.05, 0.90),
    ("back_low", 212.0, "φbl 背の丸みが足の凹へ移る角 [deg]", 185.0, 240.0),
    ("foot_spread", 0.18, "足の凹の長さ /H", 0.04, 0.60),
    ("tip_angle", 28.0, "φtip 唇先の角（B から、deg。負 = 唇先が管の中心より下へ垂れる鉤）", -75.0, 80.0),
    ("hook_depth", 0.07, "鉤の引き込み h/H（唇先が管の中へ下がる）", 0.0, 0.25),
    ("hook_span", 55.0, "鉤の引き込みが効く角の幅 [deg]", 10.0, 120.0),
    ("lip_len", 26.0, "唇の刃の長さ（φtip からの角、deg）", 5.0, 60.0),
    ("lip_thick", 0.055, "唇の刃の厚み τ/H（φtip + lip_len）", 0.01, 0.20),
    ("tip_round", 0.22, "唇先の頭の丸み [m]（先の厚みの半分。刃 lip_thick より厚くすると、細い首の先の丸い頭になる）", 0.05, 2.20),
    ("tube_end", 246.0, "φend 管から前の面へ移る角 [deg]", 205.0, 275.0),
    ("trough_depth", 0.20, "前の谷の深さ /H", 0.02, 0.40),
    ("trough_reach", 0.20, "管の端から谷の底までの a /H", 0.03, 0.80),
    ("trough_len", 0.32, "谷の底から前の海までの a /H", 0.08, 1.20),
    ("ledge_amp", 0.0, "b 区域：第二の波頭の強さ [m]（肩の行）", 0.0, 3.5),
    ("ledge_pos", 0.62, "b 区域：稜の位置（頂 0 → 唇先 1 の列の比）", 0.30, 0.92),
    ("ledge_width", 0.16, "b 区域：稜と谷の幅（列の比）", 0.05, 0.40),
    ("ledge_lobe", 0.0, "b 区域：房（稜の張り出しの足し分、m）。c 方向の山が房になる（3 つ）", -1.0, 2.5),
    ("lipprof_1", 0.0, "唇の上面の断面の形 1：頂から唇先へ 10% の所のまわり（列の幅 ±11）を法線の向きへ [m]（R1、大きな形の線）", -0.8, 0.8),
    ("lipprof_2", 0.0, "唇の上面の断面の形 2：30% の所 [m]", -0.8, 0.8),
    ("lipprof_3", 0.0, "唇の上面の断面の形 3：50% の所 [m]", -0.8, 0.8),
    ("lipprof_4", 0.0, "唇の上面の断面の形 4：70% の所 [m]", -0.8, 0.8),
    ("lipprof_5", 0.0, "唇の上面の断面の形 5：88% の所（唇の頭）[m]", -0.8, 0.8),
    ("edge_tip", 0.0, "側の縁：唇先の縁（列 200 のまわり σ 6 列。唇の下の輪郭 72 を作る縁そのもの）を法線の向きへ [m]（R1）", -0.4, 0.4),
    ("edge_1", 0.0, "側の縁 1：列 70 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_2", 0.0, "側の縁 2：列 100 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_3", 0.0, "側の縁 3：列 130 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_4", 0.0, "側の縁 4：列 160 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_5", 0.0, "側の縁 5：列 188 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_6", 0.0, "側の縁 6：列 210 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_7", 0.0, "側の縁 7：列 240 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_8", 0.0, "側の縁 8：列 280 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_9", 0.0, "側の縁 9：列 320 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
]
PNAMES = [p[0] for p in PARAMS]
PDEF = {p[0]: p[1] for p in PARAMS}
PBOUNDS = {p[0]: (p[3], p[4]) for p in PARAMS}
PDESC = {p[0]: p[2] for p in PARAMS}
EDGE_CENTERS = (70, 100, 130, 160, 188, 210, 240, 280, 320)       # R1: 9 column bands (Gaussian, partition of unity)
EDGE_SIG = 14.0
EDGE_NAMES = ["edge_%d" % (k + 1) for k in range(len(EDGE_CENTERS))] + ["edge_tip"]
TIP_SIG = 6.0


# ------------------------------------------------------------------ rows
def c_rows():
    n_dense = int(round((C_DENSE1 - C_DENSE0) / DC))
    dense = C_DENSE0 + DC * np.arange(n_dense + 1)
    n_left = NV - len(dense)
    L = C_DENSE0 - C_LO
    lo, hi = 1.0, 1.3
    for _ in range(100):
        g = 0.5 * (lo + hi)
        s = DC * (g ** np.arange(1, n_left + 1))
        if s.sum() > L:
            hi = g
        else:
            lo = g
    s = DC * (g ** np.arange(1, n_left + 1)); s *= L / s.sum()
    left = C_DENSE0 - np.cumsum(s)
    c = np.r_[left[::-1], dense]
    c[0] = C_LO
    return c


# ------------------------------------------------------------------ monotone cubic (Fritsch-Carlson), the ramp basis
def pchip(xk, yk, x):
    xk = np.asarray(xk, float); yk = np.asarray(yk, float); x = np.asarray(x, float)
    if len(xk) == 1:
        return np.full_like(x, yk[0])
    o = np.argsort(xk); xk, yk = xk[o], yk[o]
    h = np.diff(xk); d = np.diff(yk) / h
    m = np.zeros_like(yk)
    if len(xk) == 2:
        m[:] = d[0]
    else:
        for i in range(1, len(xk) - 1):
            if d[i - 1] * d[i] <= 0:
                m[i] = 0.0
            else:
                w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]
                m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        # end slopes: flat (a ramp holds its end value; also keeps the rows constant outside the keys)
        m[0] = 0.0; m[-1] = 0.0
    xc = np.clip(x, xk[0], xk[-1])
    i = np.clip(np.searchsorted(xk, xc) - 1, 0, len(xk) - 2)
    t = (xc - xk[i]) / h[i]
    h00 = (1 + 2 * t) * (1 - t) ** 2; h10 = t * (1 - t) ** 2; h01 = t * t * (3 - 2 * t); h11 = t * t * (t - 1)
    return h00 * yk[i] + h10 * h[i] * m[i] + h01 * yk[i + 1] + h11 * h[i] * m[i + 1]


def bspline_ramp(xk, yk, x, per_span=48):
    """ramp の B-spline 基底（Houdini の ramp の「B-Spline」と同じ考え方）：鍵 (c_k, v_k) を制御点とする
    開いた一様 3 次 B-spline（両端の鍵を通る）。曲線は鍵の多角形の中に収まり（波打たない）、2 階まで連続。
    鍵の外では端の値のまま。"""
    xk = np.asarray(xk, float); yk = np.asarray(yk, float); x = np.asarray(x, float)
    o = np.argsort(xk, kind="stable"); xk, yk = xk[o], yk[o]
    n = len(xk)
    if n == 1:
        return np.full_like(x, yk[0])
    if n < 4:
        return np.interp(x, xk, yk)
    m = n - 3
    kn = np.r_[[0.0] * 3, np.arange(m + 1, dtype=float), [float(m)] * 3]
    t = np.linspace(0.0, m, m * per_span + 1)
    t[-1] = m - 1e-12
    # de Boor basis (vectorised Cox-de Boor)
    B = np.zeros((len(t), len(kn) - 1))
    for i in range(len(kn) - 1):
        B[:, i] = (kn[i] <= t) & (t < kn[i + 1])
    for d in range(1, 4):
        Bn = np.zeros((len(t), len(kn) - 1 - d))
        for i in range(len(kn) - 1 - d):
            a = (t - kn[i]) / (kn[i + d] - kn[i]) if kn[i + d] > kn[i] else 0.0
            b = (kn[i + d + 1] - t) / (kn[i + d + 1] - kn[i + 1]) if kn[i + d + 1] > kn[i + 1] else 0.0
            Bn[:, i] = a * B[:, i] + b * B[:, i + 1]
        B = Bn
    cx = B @ xk; cy = B @ yk
    cx[-1] = xk[-1]; cy[-1] = yk[-1]
    return np.interp(x, cx, cy)


RAMP_BASIS = "bspline"


class Design:
    """母数ごとの鍵（c [m] と値）。Houdini の ramp（位置 u = (c − C_LO)/(C_HI − C_LO)、基底 B-Spline）と同じ中身。"""

    def __init__(self, keys=None):
        self.keys = {}
        for n in PNAMES:
            k = (keys or {}).get(n)
            self.keys[n] = ([float(x) for x in k[0]], [float(v) for v in k[1]]) if k else ([0.0], [PDEF[n]])

    def eval(self, c):
        f = bspline_ramp if RAMP_BASIS == "bspline" else pchip
        return {n: f(self.keys[n][0], self.keys[n][1], c) for n in PNAMES}

    def to_json(self):
        return {"schema": "GreatWave.kstar_h.design/1", "c_range_for_ramps": [C_LO, C_HI],
                "keys": {n: {"c": self.keys[n][0], "v": self.keys[n][1]} for n in PNAMES}}

    @staticmethod
    def from_json(d):
        return Design({n: (v["c"], v["v"]) for n, v in d["keys"].items()})

    @staticmethod
    def load(path):
        return Design.from_json(json.load(open(path, encoding="utf-8")))

    def save(self, path):
        json.dump(self.to_json(), open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ curve helpers
def arclen(P):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1])))]


def resample(P, n):
    s = arclen(P)
    if s[-1] < 1e-12:
        return np.repeat(P[:1], n + 1, 0)
    q = np.linspace(0, s[-1], n + 1)
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], -1)


def resample_at(P, q):
    s = arclen(P)
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], -1)


def bezier(P0, P1, P2, P3, n):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3


def hermite(P0, T0, P1, T1, k0, k1, n=None):
    d = float(np.linalg.norm(P1 - P0))
    if n is None:
        n = max(int(math.ceil(1.6 * d / 0.004)), 8)
    return bezier(P0, P0 + k0 * d * T0, P1 - k1 * d * T1, P1, n)


def cat(parts):
    out = [parts[0]]
    for p in parts[1:]:
        out.append(p[1:] if np.linalg.norm(p[0] - out[-1][-1]) < 1e-9 else p)
    return np.vstack(out)


def unit(v):
    return v / max(float(np.linalg.norm(v)), 1e-12)


def smooth_poly(P, sig, step):
    """弧長で取り直してガウスでならす（端は固定）。sig・step は同じ単位。"""
    if sig <= 0 or len(P) < 5:
        return P
    s = arclen(P)
    q = np.arange(0.0, s[-1] + 1e-12, step)
    if len(q) < 7:
        return P
    X = resample_at(P, q)
    r = int(math.ceil(3 * sig / step))
    ker = np.exp(-0.5 * (np.arange(-r, r + 1) * step / sig) ** 2); ker /= ker.sum()
    Xp = np.pad(X, ((r, r), (0, 0)), mode="edge")
    Xs = np.stack([np.convolve(Xp[:, k], ker, "valid") for k in range(2)], -1)
    w = np.clip(np.minimum(np.arange(len(q)), np.arange(len(q))[::-1]) / max(r, 1), 0, 1)
    return X + w[:, None] * (Xs - X)


# ------------------------------------------------------------------ one section (unit height, barrel centre at the origin)
def _polar(r, phi):
    return np.stack([r * np.cos(phi), r * np.sin(phi)], -1)


def unit_section(p, Hm):
    """p: scalars of one row (ratios of H).  Hm = the row height in metres (for the absolute tip radius).
    returns dict of polylines in unit coordinates (B at the origin) and landmarks."""
    D = math.radians
    R = float(p["tube_radius"]); e2 = float(p["tube_oval"])
    ptip = D(float(p["tip_angle"])); span = D(max(float(p["hook_span"]), 1.0)); hk = float(p["hook_depth"])
    pbl = D(float(p["back_low"]))
    # R1: the tube hands over to the front face before its lowest point (after the lean), so the face runs down into the
    # trough without first rising (H1A's vertical S-fold on the tube face): soft minimum with 262 deg - lean
    te, tl = float(p["tube_end"]), 262.0 - float(p.get("lean", 0.0))
    kq = 3.0
    pend = D(-kq * math.log(math.exp(-te / kq) + math.exp(-tl / kq)))
    # R1: the round head of the lip never exceeds 3.5 % of the row height (soft minimum): in the low closing rows a head of
    #     fixed metres dominated the tiny curl and creased the sheet across the rows
    tr, tl_ = max(float(p["tip_round"]), 0.03), 0.035 * Hm
    kr = 0.02
    rt = max(-kr * math.log(math.exp(-tr / kr) + math.exp(-tl_ / kr)), 0.02) / Hm
    tau_tip = 2.0 * rt
    llen = D(max(float(p["lip_len"]), 2.0))
    tk_phi = [ptip, ptip + llen, 0.5 * math.pi, math.pi, pbl]
    tk_val = [tau_tip, max(float(p["lip_thick"]), 0.01), float(p["shell_top"]), float(p["shell_back"]), float(p["shell_base"])]
    # keep the knots ordered (the lip knot may not pass the top)
    # soft clamp (no crease across the rows when the lip knot meets its limit)
    kk = D(3.0)
    lim = 0.5 * math.pi - D(8)
    tk_phi[1] = -kk * math.log(math.exp(-tk_phi[1] / kk) + math.exp(-lim / kk))
    tk_phi[1] = kk * math.log(math.exp(tk_phi[1] / kk) + math.exp((ptip + D(2)) / kk))
    # the thickness never shrinks from the lip blade toward the back; the tip head may be thicker than the blade
    # (a round head on a thinner neck: the painting's drooping lip head, its concave くびれ on the lip top)
    for i in range(2, len(tk_val)):
        tk_val[i] = max(tk_val[i], tk_val[i - 1] + 1e-4)

    def r_in(phi):
        u = np.clip(1.0 - (phi - ptip) / span, 0.0, 1.0)
        return R * (1.0 + e2 * np.cos(2.0 * phi)) - hk * u * u

    def dr_in(phi):
        u = np.clip(1.0 - (phi - ptip) / span, 0.0, 1.0)
        return -2.0 * R * e2 * np.sin(2.0 * phi) + 2.0 * hk * u / span * ((phi - ptip) < span)

    def tau(phi):
        return pchip(tk_phi, tk_val, phi)

    step = D(0.25)
    # outer: from the back-low angle down to the tip
    pho = np.linspace(pbl, ptip, 1000)
    ro = r_in(pho) + tau(pho)
    outer = _polar(ro, pho)
    # inner: from the tip up to the tube end
    phi_i = np.linspace(ptip, pend, 1000)
    inner = _polar(r_in(phi_i), phi_i)
    # headings
    eps = 1e-4

    def d_outer(phi):          # traversal toward the tip = decreasing phi
        P1 = _polar(r_in(phi + eps) + tau(phi + eps), phi + eps); P0 = _polar(r_in(phi - eps) + tau(phi - eps), phi - eps)
        return unit(P0 - P1)

    def d_inner(phi):          # traversal away from the tip = increasing phi
        return unit(_polar(r_in(phi + eps), phi + eps) - _polar(r_in(phi - eps), phi - eps))
    # tip cap (rounded, bulging along the outer heading)
    Po, Pi = outer[-1], inner[0]
    ho, hi = d_outer(ptip), d_inner(ptip)
    k = 0.95 * float(np.linalg.norm(Po - Pi))
    cap = bezier(Po, Po + k * ho, Pi - k * hi, Pi, 81)
    # lean: rotate the whole shell about B (CCW = crest back, tip up)
    lw = D(float(p.get("lean", 0.0)))
    Rm = np.array([[math.cos(lw), -math.sin(lw)], [math.sin(lw), math.cos(lw)]])
    outer = outer @ Rm.T; inner = inner @ Rm.T; cap = cap @ Rm.T
    d_o0, d_i0 = d_outer, d_inner
    d_outer = lambda phi: Rm @ d_o0(phi)
    d_inner = lambda phi: Rm @ d_i0(phi)
    # top = highest point of the outer, located continuously (parabola through the 3 samples around the maximum)
    # soft argmax (continuous when the top is flat or has two near-equal humps; a hard argmax would jump and
    # crease the sheet across the rows)
    yo = outer[:, 1]
    wts = np.exp((yo - yo.max()) / 0.004)
    kt_soft = float(np.sum(wts * np.arange(len(yo))) / np.sum(wts))
    kt = int(np.clip(np.floor(kt_soft), 1, len(outer) - 2)); ft = kt_soft - kt
    # corner (R1) = the rearmost point of the tube (minimum a after the lean), located continuously (soft argmin over the
    # inner curve from phi = 90 deg to the tube end); kept at least 60 samples before the tube end
    lo = int(np.searchsorted(phi_i, 0.5 * math.pi))
    xi = inner[lo:, 0]
    wts_c = np.exp(-(xi - xi.min()) / 0.004)
    fc = lo + float(np.sum(wts_c * np.arange(len(xi))) / np.sum(wts_c))
    fc = float(np.clip(fc, lo, len(phi_i) - 61))
    return dict(outer=outer, inner=inner, cap=cap, kt=kt + ft, corner_f=fc,
                pbl=pbl, pend=pend, lean=lw, d_outer=d_outer, d_inner=d_inner, r_in=r_in, tau=tau, R=R)


def split_frac(P, f):
    """split polyline P at the fractional index f -> (P[..f], P[f..]) sharing the interpolated point."""
    f = float(np.clip(f, 0.0, len(P) - 1.0))
    k = int(math.floor(f)); t = f - k
    if k >= len(P) - 1:
        return P.copy(), P[-1:].copy()
    Q = P[k] + t * (P[k + 1] - P[k])
    first = np.vstack([P[:k + 1], Q[None]]) if t > 1e-9 else P[:k + 1].copy()
    second = np.vstack([Q[None], P[k + 1:]]) if t > 1e-9 else P[k:].copy()
    return first, second


def split_arc(P, frac):
    s = arclen(P)
    f = float(np.interp(frac * s[-1], s, np.arange(len(P))))
    return split_frac(P, f)


def section(p):
    """p: scalars of one row.  returns (400, 2) (a, y) in metres and info."""
    H_true = max(float(p["crest_height"]), 0.0)
    Hm = max(H_true, 1.5)
    squash = H_true / Hm
    aT = float(p["crest_a"])
    U = unit_section(p, Hm)
    outer, inner, cap = U["outer"], U["inner"], U["cap"]
    back_all, lip_top = split_frac(outer, U["kt"])
    top = lip_top[0].copy()
    ysea = top[1] - 1.0                  # still water in unit coordinates
    # ---- back: the outer from the back-low angle, starting where it is at the foot height (interpolated crossing)
    foot_h = 0.06
    yy = back_all[:, 1] - (ysea + foot_h)
    above = np.nonzero(yy >= 0)[0]
    if len(above) == 0:
        f_foot = float(len(back_all) - 2)
    elif above[0] == 0:
        f_foot = 0.0
    else:
        k = int(above[0]); f_foot = (k - 1) + float(-yy[k - 1] / (yy[k] - yy[k - 1]))
    # R1: the round back never runs under itself: it starts at the rearmost point of the outer curve (minimum a, soft) when
    # that is higher than the foot height; below it the concave foot flows back into the sea (no undercut kick at the foot)
    xb = back_all[:, 0]
    wr = np.exp(-(xb - xb.min()) / REAR_T)
    f_rear = float(np.sum(wr * np.arange(len(xb))) / np.sum(wr))
    kk2 = 2.0
    f = kk2 * math.log(math.exp(f_foot / kk2) + math.exp(f_rear / kk2))        # smooth max of the two sample indices
    f = float(np.clip(f, 0.0, len(back_all) - 2.0))
    back_round = split_frac(back_all, f)[1] if f > 1e-9 else back_all
    Pb = back_round[0]
    hb = unit(back_round[min(3, len(back_round) - 1)] - back_round[0])
    # never let the back start by heading down (undercut): soft floor of the upward component at 0.2
    kk = 0.05
    hy = 0.2 + kk * math.log1p(math.exp((hb[1] - 0.2) / kk)) if (hb[1] - 0.2) / kk < 30 else hb[1]
    hb = unit(np.array([hb[0], hy]))
    F = np.array([Pb[0] - float(p["foot_spread"]) - 0.35 * (Pb[1] - ysea), ysea])
    fillet = hermite(F, np.array([1.0, 0.0]), Pb, hb, 0.45, 0.45)
    back = cat([fillet, back_round])
    # ---- upper lip: top -> tip apex (arc-length middle of the cap)
    cap_up, cap_lo = split_arc(cap, 0.5)
    upper = cat([lip_top, cap_up])
    # ---- inner: cap second half -> tube to 180 deg (corner) -> tube end
    tube_a, tube_b = split_frac(inner, U["corner_f"])
    lower = cat([cap_lo, tube_a])
    face_tube = tube_b
    Qe = face_tube[-1]
    he = U["d_inner"](U["pend"])
    yD = ysea - float(p["trough_depth"])
    Dp = np.array([Qe[0] + float(p["trough_reach"]) + 0.6 * max(Qe[1] - yD, 0.0) * max(he[0], 0.0), yD])
    # the trough bottom stays below the tube end (soft minimum, no crease across the rows)
    kk = 0.02
    lim = Qe[1] - 0.02
    Dp[1] = -kk * math.log(math.exp(-Dp[1] / kk - (-lim / kk)) + 1.0) + (-kk * (-lim / kk)) if False else         min(Dp[1], lim) - kk * math.log1p(math.exp(-abs(Dp[1] - lim) / kk))
    face = cat([face_tube, hermite(Qe, he, Dp, np.array([1.0, 0.0]), 0.40, 0.45)])
    E = np.array([Dp[0] + float(p["trough_len"]), ysea])
    ramp = hermite(Dp, np.array([1.0, 0.0]), E, np.array([1.0, 0.0]), 0.45, 0.45)
    # ---- to metres (top at (aT, H)); the geometry is built at >= 1.5 m and squashed below
    def m(P):
        Q = np.empty_like(P)
        Q[:, 0] = aT + Hm * (P[:, 0] - top[0])
        Q[:, 1] = Hm * (P[:, 1] - ysea) * squash
        return Q
    back, upper, lower, face, ramp = m(back), m(upper), m(lower), m(face), m(ramp)
    # light smoothing of the G1 joints (curvature), keeping the landmark points
    sg = 0.20 * min(1.0, Hm / 8.0)
    back = smooth_poly(back, sg, 0.02); face = smooth_poly(face, sg, 0.02); ramp = smooth_poly(ramp, sg, 0.02)
    Fm, Em = back[0], ramp[-1]
    backsea = np.array([[Fm[0] - 40.0, 0.0], [Fm[0], 0.0]])
    frontsea = np.array([[Em[0], 0.0], [Em[0] + 30.0, 0.0]])
    segs = [backsea, back, upper, lower, face, ramp, frontsea]
    out = [resample(segs[0], SEGCOLS[1])]
    TIPC, TIPL = 12, 0.9
    for k in range(1, 7):
        n = SEGCOLS[k + 1] - SEGCOLS[k]
        P = segs[k]
        if k in (2, 3):
            s_ = arclen(P); L = s_[-1]; Lt = min(TIPL, 0.3 * L)
            if k == 2:
                q = np.r_[np.linspace(0, L - Lt, n - TIPC + 1)[:-1], np.linspace(L - Lt, L, TIPC + 1)]
            else:
                q = np.r_[np.linspace(0, Lt, TIPC + 1)[:-1], np.linspace(Lt, L, n - TIPC + 1)]
            Q = resample_at(P, q)
        else:
            Q = resample(P, n)
        out.append(Q[1:])
    S = np.vstack(out)
    assert S.shape == (NU, 2), S.shape
    info = {"H": H_true, "tip": S[200].copy(), "top": S[90].copy(), "B": np.array([aT + Hm * (0 - top[0]), Hm * (0 - ysea) * squash]),
            "R_m": U["R"] * Hm}
    return S, info


# ------------------------------------------------------------------ in-plane normals of a row, normal displacement bands
def row_normals(a, y):
    """単位の法線（進む向きの左 = 断面の外側。背では後ろ上、唇の上では上、管の中では管の中心の向き）"""
    ta = np.gradient(a); ty = np.gradient(y)
    L = np.maximum(np.hypot(ta, ty), 1e-12)
    return np.stack([-ty / L, ta / L], -1)


def band_weight(j0, j1, ramp, nu=NU):
    j = np.arange(nu, dtype=float)
    w = np.clip((j - j0) / max(ramp, 1), 0, 1) * np.clip((j1 - j) / max(ramp, 1), 0, 1)
    return w * w * (3 - 2 * w)


def fade_small(A, Y, H):
    """低い行（波の両端）: 巻きを単調な膨らみへなだらかに移す（平面で折り返さない）。"""
    for r in range(len(A)):
        h = H[r]
        # R1: the curl fades out between 3.5 m and 2.0 m (H1A: 3.0 -> 0.6 m); lower rows are a pure swell, so the tiny
        #     squashed curls of the end rows never cross themselves
        fb, lo = 3.5, 2.0
        if h >= fb:
            continue
        w = float(np.clip((h - lo) / (fb - lo), 0.0, 1.0)); w = w * w * (3 - 2 * w)
        a, y = A[r], Y[r]
        j0, j1 = SEGCOLS[1], SEGCOLS[6]
        s = np.r_[0.0, np.cumsum(np.hypot(np.diff(a[j0:j1 + 1]), np.diff(y[j0:j1 + 1])))]
        f = s / max(s[-1], 1e-9)
        flat_a = a[j0] + f * (a[j1] - a[j0])
        # a monotone swell of the same height centred at the crest top
        at = a[90]
        sw = 0.5 * (a[j1] - a[j0])
        flat_y = h * np.exp(-0.5 * ((flat_a - at) / max(0.35 * sw, 0.3)) ** 2)
        A[r, j0:j1 + 1] = w * a[j0:j1 + 1] + (1 - w) * flat_a
        Y[r, j0:j1 + 1] = w * y[j0:j1 + 1] + (1 - w) * flat_y
    return A, Y


# ------------------------------------------------------------------ the three stages
def build_base(design, c=None):
    if c is None:
        c = c_rows()
    P = design.eval(c)
    A = np.zeros((len(c), NU)); Y = np.zeros((len(c), NU))
    for r in range(len(c)):
        p = {k: float(P[k][r]) for k in PNAMES}
        S, _ = section(p)
        A[r], Y[r] = S[:, 0], S[:, 1]
    A, Y = fade_small(A, Y, P["crest_height"])
    return c, A, Y, P


LIPPROF_U = (0.10, 0.30, 0.50, 0.70, 0.88)
LIPPROF_SIG = 0.10


def apply_lipprof(c, A, Y, P):
    """R1 唇の上面の断面の形：頂（列 90）→ 唇先（列 200）の外の面を、5 つのなめらかな山（列の比 0.1/0.3/0.5/0.7/0.88、幅 σ 0.1）の
    和の量だけ法線の向きへ動かす。量は c の ramp（鍵 2.5 m おき）。原画視点で唇の上の輪郭（132）を作るのは主断面のまわりの行の
    この断面の線そのものなので、その線の形（凸の頂 → くびれ → 凸の鉤）を断面の側で決める（行ごとに振らない）。"""
    names = ["lipprof_%d" % (k + 1) for k in range(len(LIPPROF_U))]
    if not any(n in P and np.any(np.abs(P[n]) > 1e-7) for n in names):
        return A, Y
    A = A.copy(); Y = Y.copy()
    j = np.arange(NU, dtype=float)
    u = (j - 90.0) / 110.0
    # the band rises slowly from the crest top (22 columns ~ 2 m, C1 smoothstep) so the top stays one round arc (Q17: no kink at
    # the top; a 5-column ramp made a 12-17 deg single-vertex fold at column 92)
    x0 = np.clip((j - 90.0) / 22.0, 0.0, 1.0); x1 = np.clip((199.0 - j) / 6.0, 0.0, 1.0)
    wband = (x0 * x0 * (3 - 2 * x0)) * (x1 * x1 * (3 - 2 * x1))
    basis = [np.exp(-0.5 * ((u - uk) / LIPPROF_SIG) ** 2) * wband for uk in LIPPROF_U]
    for r in range(len(c)):
        prof = sum(float(P[n][r]) * b for n, b in zip(names, basis))
        if not np.any(np.abs(prof) > 1e-7):
            continue
        prof = prof * body_mask(Y[r])
        n = row_normals(A[r], Y[r])
        A[r] += prof * n[:, 0]; Y[r] += prof * n[:, 1]
    return A, Y


def apply_ledge(c, A, Y, P):
    """b 区域：肩の行の唇の上面（列 90〜200）を法線の向きへ、谷（頂の側）→ 稜（唇先の側）の形に押す。
    強さ ledge_amp(c)、稜の位置 ledge_pos、幅 ledge_width（列の比）。唇先そのもの（列 190〜）は動かさない。"""
    A = A.copy(); Y = Y.copy()
    j = np.arange(NU, dtype=float)
    u = (j - 90.0) / 110.0
    for r in range(len(c)):
        amp = float(P["ledge_amp"][r]); lobe = float(P["ledge_lobe"][r]) if "ledge_lobe" in P else 0.0
        if abs(amp) < 1e-6 and abs(lobe) < 1e-6:
            continue
        pos = float(P["ledge_pos"][r]); wd = max(float(P["ledge_width"][r]), 0.03)
        ridge = np.exp(-0.5 * ((u - pos) / wd) ** 2)
        prof = amp * (ridge - 0.85 * np.exp(-0.5 * ((u - (pos - 1.6 * wd)) / (0.9 * wd)) ** 2)) + lobe * ridge
        prof *= band_weight(92, 196, 6)
        # R1: the valley (inward push) never goes deeper than 40 % of the local lip thickness (smooth cap)
        th = lip_thickness(A[r], Y[r])
        cap = np.maximum(0.40 * th, 0.02)
        prof = np.where(prof < 0.0, -cap * np.tanh(-prof / cap), prof)
        prof = prof * body_mask(Y[r])          # R1: never on the sea
        n = row_normals(A[r], Y[r])
        A[r] += prof * n[:, 0]; Y[r] += prof * n[:, 1]
    return A, Y


# PaintingCam v1（Unity、kh_common と同じ値）と K* の断面の枠
CAM_POS_U = np.array([0.0, 3.0, -62.0])
FRAME_E = np.array([0.6798348938056157, 0.0, 0.733365200404483])
FRAME_T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
FRAME_O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
REAR_T = 0.004        # R1: softness of the rearmost-point search of the back (unit section coordinates)
GRAZE = 0.12          # |cos(視線, 面の法線)| がこの程度までを「輪郭の縁」とみなす（なめらかな重み）


def world_u(c, A, Y):
    return FRAME_O[None, None, :] + A[..., None] * FRAME_T + Y[..., None] * np.array([0.0, 1.0, 0.0]) + np.asarray(c)[:, None, None] * FRAME_E


def graze_weight(c, A, Y):
    """原画カメラから見て面が視線に沿う（輪郭を作る）所ほど 1 になる重み exp(-(cosθ/GRAZE)²)。"""
    X = world_u(c, A, Y)
    du = np.gradient(X, axis=1); dv = np.gradient(X, axis=0)
    n = np.cross(du, dv)
    v = X - CAM_POS_U
    cos = np.sum(n * v, -1) / np.maximum(np.linalg.norm(n, axis=-1) * np.linalg.norm(v, axis=-1), 1e-12)
    return np.exp(-(cos / GRAZE) ** 2)


def edge_band_weights(nu=NU):
    """R1: the 9 column bands of the side-edge strips: Gaussians (sigma 14 columns) normalised to a partition of unity over
    columns 60..330, fading to 0 outside (the sea margins and the far back never move)."""
    j = np.arange(nu, dtype=float)
    g = np.stack([np.exp(-0.5 * ((j - cc) / EDGE_SIG) ** 2) for cc in EDGE_CENTERS])
    g = g / np.maximum(g.sum(0, keepdims=True), 1e-12)
    return g * band_weight(40, 350, 20)[None, :]


def edge_modes(c, A, Y):
    """R1: per band b the field M_b(r, j) = smooth_cols(W_b * G) * body: the displacement (m, along the section normal) per
    metre of the band's ramp value.  The side-edge displacement is sum_b ramp_b(c_r) * M_b(r, j)."""
    G = graze_weight(c, A, Y)
    # copy A: the grazing weight is smoothed over the sheet (4 columns, 3 rows) and the displacement again along the
    # section (3 columns), so the side-edge strips never kink a section or crease across the rows
    G = _smooth2(G, 4.0, 3.0)
    W = edge_band_weights(A.shape[1])
    body = body_mask(Y)
    modes = [_smooth2(W[b][None, :] * G, 3.0, 0.0) * body for b in range(len(W))]
    # the lip-tip edge (the underside outline 72 is drawn by the tips of the rows): a narrow band around column 200,
    # not weighted by the grazing (the tip cap is the edge itself)
    j = np.arange(A.shape[1], dtype=float)
    modes.append(np.exp(-0.5 * ((j - 200.0) / TIP_SIG) ** 2)[None, :] * body)
    return np.stack(modes)


def apply_edges(c, A, Y, P, modes=None):
    """側の縁の合わせ（R1）：原画視点で輪郭を作る縁（視線が面をかすめる所、なめらかな重み）だけを、9 本の列の帯の ramp の量だけ
    断面の法線の向きへ動かす。中の面・海・低い行は動かない。"""
    A = A.copy(); Y = Y.copy()
    if not any(np.any(np.abs(P[k]) > 1e-7) for k in EDGE_NAMES):
        return A, Y
    M = edge_modes(c, A, Y) if modes is None else modes
    Dm = sum(np.asarray(P[k])[:, None] * M[b] for b, k in enumerate(EDGE_NAMES))
    for r in range(len(c)):
        d = Dm[r]
        if not np.any(np.abs(d) > 1e-7):
            continue
        n = row_normals(A[r], Y[r])
        A[r] += d * n[:, 0]; Y[r] += d * n[:, 1]
    return A, Y


def _gk(sig):
    if sig <= 0:
        return np.array([1.0])
    r = int(np.ceil(3 * sig)); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
    return k / k.sum()


def _smooth2(M, sig_col, sig_row):
    """separable Gaussian smoothing (edge-padded) along columns (axis 1) and rows (axis 0)."""
    out = M
    for ax, sg in ((1, sig_col), (0, sig_row)):
        if sg <= 0:
            continue
        k = _gk(sg); r = len(k) // 2
        pad = [(0, 0), (0, 0)]; pad[ax] = (r, r)
        Q = np.pad(out, pad, mode="edge")
        out = np.apply_along_axis(lambda v: np.convolve(v, k, "valid"), ax, Q)
    return out


def body_mask(Y, y0=0.3, y1=1.5):
    """1 on the wave body, 0 on the sea (y <= y0), smooth in between (R1)."""
    x = np.clip((np.asarray(Y) - y0) / (y1 - y0), 0.0, 1.0)
    return x * x * (3 - 2 * x)


def lip_thickness(a, y, j0=90, j1=200, jl1=330):
    """R1: per column j0..j1 of the upper lip, the distance to the nearest point of the lower chain (cols j1..jl1); other
    columns get a large value.  (distance to the vertices, densified 4x along the lower chain)"""
    out = np.full(len(a), 99.0)
    L = np.stack([a[j1:jl1 + 1], y[j1:jl1 + 1]], -1)
    t = np.linspace(0, 1, 4, endpoint=False)[None, :, None]
    Ld = (L[:-1, None, :] * (1 - t) + L[1:, None, :] * t).reshape(-1, 2)
    U = np.stack([a[j0:j1 - 3], y[j0:j1 - 3]], -1)
    d = np.sqrt(((U[:, None, :] - Ld[None, :, :]) ** 2).sum(-1)).min(1)
    out[j0:j1 - 3] = d
    return out


def lip_clearance(A, Y, rows=None, j0=95, j1=197, jl0=203, jl1=None):
    """R1: signed clearance (m) of the upper lip (cols j0..j1) above the lower surface (cols jl0..jl1, default up to the
    corner 314 + 30): + = the water body between them, − = the upper surface has passed through the lower one.
    returns (per-row minimum, per-row column of the minimum)."""
    nv = A.shape[0]
    rows = range(nv) if rows is None else rows
    jl1 = jl1 or 344
    mins = np.full(nv, 99.0); cols = np.zeros(nv, int)
    for r in rows:
        if Y[r].max() < 1.0:
            continue
        L = np.stack([A[r, jl0:jl1 + 1], Y[r, jl0:jl1 + 1]], -1)
        tl = np.gradient(L, axis=0)
        tl /= np.maximum(np.linalg.norm(tl, axis=1, keepdims=True), 1e-12)
        nl = np.stack([-tl[:, 1], tl[:, 0]], -1)             # left of the lower chain's traversal = away from the water
        U = np.stack([A[r, j0:j1 + 1], Y[r, j0:j1 + 1]], -1)
        D = U[:, None, :] - L[None, :, :]
        dist = np.sqrt((D ** 2).sum(-1))
        k = np.argmin(dist, 1)
        sgn = -np.sign(np.einsum("ij,ij->i", D[np.arange(len(U)), k], nl[k]))
        sd = sgn * dist[np.arange(len(U)), k]
        i = int(np.argmin(sd))
        mins[r] = float(sd[i]); cols[r] = j0 + i
    return mins, cols


def segx_count(P, i0=0, i1=None):
    """R1: number of crossings between non-adjacent segments of the polyline P[i0:i1] (2-D)."""
    P = P[i0:i1]
    a0 = P[:-1]; a1 = P[1:]
    n = len(a0)
    I, J = np.triu_indices(n, 2)
    mn = np.minimum(a0, a1); mx = np.maximum(a0, a1)
    ok = (mn[J, 0] <= mx[I, 0]) & (mx[J, 0] >= mn[I, 0]) & (mn[J, 1] <= mx[I, 1]) & (mx[J, 1] >= mn[I, 1])
    I, J = I[ok], J[ok]
    if len(I) == 0:
        return 0, []
    p, r = a0[I], a1[I] - a0[I]; q, s_ = a0[J], a1[J] - a0[J]
    rxs = r[:, 0] * s_[:, 1] - r[:, 1] * s_[:, 0]
    qp = q - p
    den = np.where(np.abs(rxs) < 1e-15, 1e-15, rxs)
    t = (qp[:, 0] * s_[:, 1] - qp[:, 1] * s_[:, 0]) / den
    u = (qp[:, 0] * r[:, 1] - qp[:, 1] * r[:, 0]) / den
    m = (np.abs(rxs) > 1e-15) & (t > 1e-9) & (t < 1 - 1e-9) & (u > 1e-9) & (u < 1 - 1e-9)
    return int(m.sum()), list(zip((I[m] + i0).tolist(), (J[m] + i0).tolist()))


def section_selfx(A, Y, j0=0, j1=None):
    """R1: rows whose section polyline (cols j0..j1) crosses itself -> {row: n_crossings}."""
    out = {}
    for r in range(A.shape[0]):
        if Y[r].max() < 0.5 and Y[r].min() > -0.5:
            continue
        n, _ = segx_count(np.stack([A[r], Y[r]], -1), j0, j1)
        if n:
            out[r] = n
    return out


def top_excess(A, Y, j_top=90, j1=200):
    """R1: per row, how much the highest point of cols j_top+1..j1 rises above the top column (m, >0 = the top is not the
    highest point)."""
    return Y[:, j_top + 1:j1].max(1) - Y[:, j_top]


def build(design, c=None):
    c, A, Y, P = build_base(design, c)
    A, Y = apply_lipprof(c, A, Y, P)
    A, Y = apply_ledge(c, A, Y, P)
    A, Y = apply_edges(c, A, Y, P)
    return c, A, Y, P
