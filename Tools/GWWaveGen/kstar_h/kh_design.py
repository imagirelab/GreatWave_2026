# -*- coding: utf-8 -*-
"""設計28修正01 K*′（最後の一コマ）を Houdini で作るための断面の生成器（候補 H1）。numpy だけ（hython と py -3.10 の両方）。

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
C_LO, C_HI = -60.0, 21.0          # ramp の 0..1 に当てる c の範囲
C_DENSE0, C_DENSE1, DC = -18.0, 20.0, 0.2      # 奥の端（c +12〜+20）で細い巻きへ閉じるまでの行

# 名前、既定値、単位・意味、下限、上限（CTRL の ramp の名前 = 名前）
PARAMS = [
    ("crest_height", 20.5, "H 頂の高さ [m]（原画の側の縁）", 0.0, 24.0),
    ("crest_a", 0.0, "aT 頂の a 位置 [m]（波峰線の平面、原画の側の縁）", -16.0, 8.0),
    ("tube_radius", 0.40, "R/H 管の半径", 0.15, 0.52),
    ("tube_oval", -0.10, "e2 管の楕円（+ = 横長、- = 縦長）", -0.30, 0.30),
    ("lean", 18.0, "殻全体の傾き [deg]（B のまわりの回転、+ = 頂が後ろ・唇先が上）", -10.0, 42.0),
    ("shell_top", 0.20, "τ/H 頂の殻の厚み（φ = 90°）", 0.03, 0.45),
    ("shell_back", 0.27, "τ/H 背の殻の厚み（φ = 180°）", 0.03, 0.55),
    ("shell_base", 0.48, "τ/H 背の下の殻（φbl、胴の裾）", 0.05, 0.90),
    ("back_low", 212.0, "φbl 背の丸みが足の凹へ移る角 [deg]", 185.0, 240.0),
    ("foot_spread", 0.18, "足の凹の長さ /H", 0.04, 0.60),
    ("tip_angle", 28.0, "φtip 唇先の角（B から、deg。負 = 唇先が管の中心より下へ垂れる鉤）", -50.0, 40.0),
    ("hook_depth", 0.07, "鉤の引き込み h/H（唇先が管の中へ下がる）", 0.0, 0.25),
    ("hook_span", 55.0, "鉤の引き込みが効く角の幅 [deg]", 10.0, 120.0),
    ("lip_len", 26.0, "唇の刃の長さ（φtip からの角、deg）", 5.0, 60.0),
    ("lip_thick", 0.055, "唇の刃の厚み τ/H（φtip + lip_len）", 0.01, 0.20),
    ("tip_round", 0.22, "唇先の頭の丸み [m]（先の厚みの半分。刃 lip_thick より厚くすると、細い首の先の丸い頭になる）", 0.12, 2.20),
    ("tube_end", 246.0, "φend 管から前の面へ移る角 [deg]", 205.0, 275.0),
    ("trough_depth", 0.20, "前の谷の深さ /H", 0.02, 0.40),
    ("trough_reach", 0.20, "管の端から谷の底までの a /H", 0.03, 0.80),
    ("trough_len", 0.32, "谷の底から前の海までの a /H", 0.08, 1.20),
    ("ledge_amp", 0.0, "b 区域：第二の波頭の強さ [m]（肩の行）", 0.0, 2.0),
    ("ledge_pos", 0.62, "b 区域：稜の位置（頂 0 → 唇先 1 の列の比）", 0.30, 0.92),
    ("ledge_width", 0.16, "b 区域：稜と谷の幅（列の比）", 0.05, 0.40),
    ("edge_top", 0.0, "側の縁：頂の帯（列 40〜160）で視線がかすめる縁の法線の移動 [m]", -1.5, 1.5),
    ("edge_lip", 0.0, "側の縁：唇の上の帯（列 120〜215）で視線がかすめる縁の法線の移動 [m]", -1.5, 1.5),
    ("edge_hook", 0.0, "側の縁：唇の下と管の帯（列 190〜340）で視線がかすめる縁の法線の移動 [m]", -1.5, 1.5),
]
PNAMES = [p[0] for p in PARAMS]
PDEF = {p[0]: p[1] for p in PARAMS}
PBOUNDS = {p[0]: (p[3], p[4]) for p in PARAMS}
PDESC = {p[0]: p[2] for p in PARAMS}
EDGE_BANDS = {"edge_top": (40, 160, 12), "edge_lip": (120, 215, 10), "edge_hook": (190, 340, 12)}   # 列の帯（端はなだらかに 0 へ）


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
    pend = D(float(p["tube_end"])); pbl = D(float(p["back_low"]))
    rt = max(float(p["tip_round"]), 0.03) / Hm
    tau_tip = 2.0 * rt
    llen = D(max(float(p["lip_len"]), 2.0))
    tk_phi = [ptip, ptip + llen, 0.5 * math.pi, math.pi, pbl]
    tk_val = [tau_tip, max(float(p["lip_thick"]), 0.01), float(p["shell_top"]), float(p["shell_back"]), float(p["shell_base"])]
    # keep the knots ordered (the lip knot may not pass the top): smooth minimum (3 deg), so the shape stays
    # differentiable in the parameters (no kink when the lip knot reaches the limit)
    lim = max(0.5 * math.pi - D(8), ptip + D(4))
    s_ = D(3.0)
    a_, b_ = tk_phi[1], lim
    m_ = min(a_, b_)
    tk_phi[1] = m_ - s_ * math.log(math.exp(-(a_ - m_) / s_) + math.exp(-(b_ - m_) / s_))
    tk_phi[1] = max(tk_phi[1], ptip + D(2))
    # the thickness never shrinks from the lip blade toward the back; the tip head may be thicker than the blade
    # (a round head on a thinner neck: the painting's drooping lip head, its concave くびれ on the lip top)
    for i in range(2, len(tk_val)):
        tk_val[i] = max(tk_val[i], tk_val[i - 1] + 1e-4)

    def hook(phi):
        # the hook pull toward the barrel centre near the tip: smoothstep in the angle, zero slope at the tip, so the
        # underside leaves the tip along the barrel (no zigzag or loop at the tip)
        t = np.clip((phi - ptip) / span, 0.0, 1.0)
        return hk * (1.0 - t * t * (3.0 - 2.0 * t))

    def r_in(phi):
        return R * (1.0 + e2 * np.cos(2.0 * phi)) - hook(phi)

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
    kt = int(np.clip(np.argmax(outer[:, 1]), 1, len(outer) - 2))
    y0, y1, y2 = outer[kt - 1, 1], outer[kt, 1], outer[kt + 1, 1]
    den = y0 - 2 * y1 + y2
    ft = float(np.clip(0.5 * (y0 - y2) / den, -0.5, 0.5)) if den < -1e-15 else 0.0
    # corner = inner at exactly phi = 180 deg (before the lean) -> fractional index
    fc = float(np.interp(math.pi, phi_i, np.arange(len(phi_i))))
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


def _first_cross(P, Q):
    """first crossing of polyline P (searched from its end backwards) with polyline Q (from its start): (i, k, point)."""
    a0, a1 = P[:-1], P[1:]; b0, b1 = Q[:-1], Q[1:]
    r = a1 - a0; s = b1 - b0
    for i in range(len(r) - 1, -1, -1):
        den = r[i, 0] * s[:, 1] - r[i, 1] * s[:, 0]
        ok = np.abs(den) > 1e-14
        dq = b0 - a0[i]
        t = (dq[:, 0] * s[:, 1] - dq[:, 1] * s[:, 0]) / np.where(ok, den, 1.0)
        u = (dq[:, 0] * r[i, 1] - dq[:, 1] * r[i, 0]) / np.where(ok, den, 1.0)
        m = ok & (t > 1e-9) & (t < 1 - 1e-9) & (u > 1e-9) & (u < 1 - 1e-9)
        if m.any():
            k = int(np.nonzero(m)[0][0])
            return i, k, a0[i] + t[k] * r[i]
    return None


def untie_tip(upper, cap_lo, inner, span=0.25):
    """upper ends at the apex, cap_lo starts there and runs into the underside (inner).  If the last `span` (unit
    lengths) of upper crosses the first `span` of (cap_lo + inner), the loop between is cut and the crossing becomes
    the apex."""
    lower = cat([cap_lo, inner])
    su = arclen(upper); sl = arclen(lower)
    iu = int(np.searchsorted(su, su[-1] - span)); il = int(np.searchsorted(sl, span))
    P = upper[iu:]; Q = lower[:il + 1]
    if len(P) < 3 or len(Q) < 3:
        return upper, cap_lo
    hit = _first_cross(P[:-1], Q[1:])
    if hit is None:
        return upper, cap_lo
    i, k, X = hit
    up = np.vstack([upper[:iu + i + 1], X[None]])
    k_abs = 1 + k + 1                        # index in lower after the crossing
    nlo = len(cap_lo)
    if k_abs >= nlo - 1:                     # the loop reaches into the barrel: keep a 2-point cap
        return up, np.vstack([X[None], lower[k_abs:k_abs + 1]]) if k_abs < len(lower) else np.vstack([X[None], X[None] + 1e-6])
    return up, np.vstack([X[None], cap_lo[k_abs:]])


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
        back_round = back_all[-2:]
    elif above[0] == 0:
        back_round = back_all
    else:
        k = int(above[0]); f = (k - 1) + float(-yy[k - 1] / (yy[k] - yy[k - 1]))
        back_round = split_frac(back_all, f)[1]
    Pb = back_round[0]
    hb = unit(back_round[min(3, len(back_round) - 1)] - back_round[0])
    if hb[1] < 0.2:                        # never let the back start by heading down (undercut): tilt up
        hb = unit(np.array([hb[0], 0.2]))
    F = np.array([Pb[0] - float(p["foot_spread"]) - 0.35 * (Pb[1] - ysea), ysea])
    fillet = hermite(F, np.array([1.0, 0.0]), Pb, hb, 0.45, 0.45)
    back = cat([fillet, back_round])
    # ---- upper lip: top -> tip apex (arc-length middle of the cap)
    cap_up, cap_lo = split_arc(cap, 0.5)
    upper = cat([lip_top, cap_up])
    # a thin tip can leave a small loop where the upper surface and the underside cross next to the apex: cut it
    upper, cap_lo = untie_tip(upper, cap_lo, inner)
    # ---- inner: cap second half -> tube to 180 deg (corner) -> tube end
    tube_a, tube_b = split_frac(inner, U["corner_f"])
    lower = cat([cap_lo, tube_a])
    face_tube = tube_b
    Qe = face_tube[-1]
    he = U["d_inner"](U["pend"])
    yD = ysea - float(p["trough_depth"])
    Dp = np.array([Qe[0] + float(p["trough_reach"]) + 0.6 * max(Qe[1] - yD, 0.0) * max(he[0], 0.0), yD])
    if Dp[1] > Qe[1] - 0.02:
        Dp[1] = Qe[1] - 0.02
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
        fb, f0 = 4.5, 2.0
        if h >= fb:
            continue
        w = float(np.clip((h - f0) / (fb - f0), 0.0, 1.0)); w = w * w * (3 - 2 * w)
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


def apply_ledge(c, A, Y, P):
    """b 区域：肩の行の唇の上面（列 90〜200）を法線の向きへ、谷（頂の側）→ 稜（唇先の側）の形に押す。
    強さ ledge_amp(c)、稜の位置 ledge_pos、幅 ledge_width（列の比）。唇先そのもの（列 190〜）は動かさない。"""
    A = A.copy(); Y = Y.copy()
    j = np.arange(NU, dtype=float)
    u = (j - 90.0) / 110.0
    for r in range(len(c)):
        amp = float(P["ledge_amp"][r])
        if abs(amp) < 1e-6:
            continue
        pos = float(P["ledge_pos"][r]); wd = max(float(P["ledge_width"][r]), 0.03)
        prof = np.exp(-0.5 * ((u - pos) / wd) ** 2) - 0.85 * np.exp(-0.5 * ((u - (pos - 1.6 * wd)) / (0.9 * wd)) ** 2)
        prof *= band_weight(92, 196, 6)
        n = row_normals(A[r], Y[r])
        A[r] += amp * prof * n[:, 0]; Y[r] += amp * prof * n[:, 1]
    return A, Y


# PaintingCam v1（Unity、kh_common と同じ値）と K* の断面の枠
CAM_POS_U = np.array([0.0, 3.0, -62.0])
FRAME_E = np.array([0.6798348938056157, 0.0, 0.733365200404483])
FRAME_T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
FRAME_O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
GRAZE = 0.35          # |cos(視線, 面の法線)| の目安（約 20°）。輪郭の縁から面に沿って 1〜2 m でなめらかに 0 へ（細い稜を作らない）


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


def row_normals_smooth(a, y, sigma=0.8, step=0.05):
    """断面の法線を、弧長 σ（m）でならした曲線から求める。細い唇先では上面と下面の法線が平均されて前を向くので、
    側の縁の移動が唇先で上面と下面を交差させない。"""
    s = np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]
    q = np.arange(0.0, s[-1] + step, step)
    X = np.stack([np.interp(q, s, a), np.interp(q, s, y)], -1)
    r = int(math.ceil(3 * sigma / step))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) * step / sigma) ** 2); k /= k.sum()
    Xp = np.pad(X, ((r, r), (0, 0)), mode="edge")
    Xs = np.stack([np.convolve(Xp[:, i], k, "valid") for i in range(2)], -1)
    T = np.gradient(Xs, axis=0)
    ta = np.interp(s, q, T[:, 0]); ty = np.interp(s, q, T[:, 1])
    L = np.maximum(np.hypot(ta, ty), 1e-12)
    return np.stack([-ty / L, ta / L], -1)


def apply_edges(c, A, Y, P):
    """側の縁の合わせ：原画視点で輪郭を作る縁（視線が面をかすめる所、なめらかな重み）だけを、各帯の ramp の量だけ
    断面の法線の向きへ動かす。帯：頂（列 40〜160）・唇の上（120〜215）・唇の下と管（190〜340）。中の面は動かない。"""
    A = A.copy(); Y = Y.copy()
    if not any(np.any(np.abs(P[k]) > 1e-7) for k in EDGE_BANDS):
        return A, Y
    G = graze_weight(c, A, Y)
    W = {k: band_weight(*v) for k, v in EDGE_BANDS.items()}
    for r in range(len(c)):
        hf = float(np.clip((Y[r].max() - 4.5) / 2.0, 0.0, 1.0))      # not on the low rows fading into the sea
        d = sum(float(P[k][r]) * W[k] for k in EDGE_BANDS) * G[r] * hf
        if not np.any(np.abs(d) > 1e-7):
            continue
        # near the lip tip the move is capped by a quarter of the local lip thickness (distance to the mirrored column
        # across the apex j_tip = 200), so the upper surface and the underside cannot cross
        for k in range(0, 13):
            sep = math.hypot(A[r, 200 - k] - A[r, 200 + k], Y[r, 200 - k] - Y[r, 200 + k]) if k else                 math.hypot(A[r, 199] - A[r, 201], Y[r, 199] - Y[r, 201])
            lim = 0.25 * sep
            for j in {200 - k, 200 + k}:
                d[j] = float(np.clip(d[j], -lim, lim))
        n = row_normals_smooth(A[r], Y[r])
        A[r] += d * n[:, 0]; Y[r] += d * n[:, 1]
    return A, Y


def build(design, c=None):
    c, A, Y, P = build_base(design, c)
    A, Y = apply_ledge(c, A, Y, P)
    A, Y = apply_edges(c, A, Y, P)
    return c, A, Y, P
