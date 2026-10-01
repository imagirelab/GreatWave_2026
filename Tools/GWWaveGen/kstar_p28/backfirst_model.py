# -*- coding: utf-8 -*-
"""仕上げ28 第1回：背から先に作る案（back-first）の K*′ の生成器（numpy、py -3.10 と hython の両方で読める）。

考え方（Polish_28 の第1回、計画 §5.3 仕上げ28 の最初の項目、利用者 Q21）
  1 背と頂の大きな形を先に決める：背（列 18〜約 84）は、1 本の正規化した背の断面 (u(s), g(s)) を、行ごとの
    頂 (a_top(c), H(c)) と背の幅 W(c) = ρ(c)·H(c) で置いた「掃引（sweep）」にする。ρ(c) は少ない鍵の 3 次の
    スプラインで、行ごとの勝手な凹凸を持たない（内側をなめらかさで凍らせる）。
  2 原画には輪郭を作る縁だけで合わせる：肩の行（c −17.8〜+3）の頂と唇（列 84 より前）は、原画の 78/130/131/132/72 を
    作っている R3 の形をそのまま使う（輪郭を作る縁）。背の掃引は列 70〜88 で R3 へなめらかに移す。
  3 奥の端（c > +3）は、1 つの型の断面（R3 の c +8 の行の唇・管・前面）に、掃引の背をつけた「相似の族」
    X(c) = a0(c)·T + s(c)·(型の断面) にする。s(c)（大きさ）と a0(c)（射線の方向へ下がる量）は少ない鍵の
    スプラインで、72 の壁（奥の行の唇先が作る）には最適化（backfirst_opt.py）で合わせる。c +3〜+7 で R3 の行から
    この族へなめらかに移す。
  4 手前の尾（c < −17.8、原画の枠の外）は、c −17.2 の行を相似に縮めた族にする（頂を弧にする）。
入力：R3 の行の npz（Unity/Build/Q20H/final/_R3/kstarR3_a45_rows.npz、読むだけ）と、R4 の主断面（背の型だけ）。
参照モデルは読まない（F13-1）。座標は kh_common と同じ断面の座標（a = 進行 T、y、c = 波峰 E）。
"""
import os
import json
import math

import numpy as np

REPO = r"G:\Unity\GreatWave_2026_Fresh"
BASE_R3 = os.path.join(REPO, "Unity", "Build", "Q20H", "final", "_R3", "kstarR3_a45_rows.npz")
BACK_TPL_R4 = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz")
NU, NV = 400, 240
J_B, J_TOP, J_TIP, J_COR, J_FB, J_E = 18, 90, 200, 314, 379, 394

_CACHE = {}


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def spline(kc, kv, c, kind="cubic"):
    """natural cubic spline through the keys (clamped to the end values outside the keys)."""
    from scipy.interpolate import CubicSpline, PchipInterpolator
    kc = np.asarray(kc, float); kv = np.asarray(kv, float)
    cc = np.clip(c, kc[0], kc[-1])
    if kind == "pchip":
        return PchipInterpolator(kc, kv)(cc)
    return CubicSpline(kc, kv, bc_type="natural")(cc)


def load_base():
    if "base" not in _CACHE:
        z = np.load(BASE_R3)
        _CACHE["base"] = (z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float))
    return _CACHE["base"]


def back_template(n=73):
    """正規化した背の断面：R4 の主断面（c ≈ 0、R4 の整えの層で背の R6 が小さい行）の列 18〜90 を、
    u = (a − a_foot)/(a_top − a_foot)、g = y/H にし、弧長で等分した n 点に取り直して軽くならす。
    戻り値 (u, g)：u, g とも 0 → 1（足 → 頂）。"""
    if "btpl" in _CACHE:
        return _CACHE["btpl"]
    z = np.load(BACK_TPL_R4)
    c, A, Y = z["c"], z["A"], z["Y"]
    r = int(np.argmin(np.abs(c)))
    a = A[r, J_B:J_TOP + 1].astype(float); y = Y[r, J_B:J_TOP + 1].astype(float)
    u = (a - a[0]) / (a[-1] - a[0]); g = (y - y[0]) / (y[-1] - y[0])
    s = np.r_[0, np.cumsum(np.hypot(np.diff(u), np.diff(g)))]; s /= s[-1]
    t = np.linspace(0, 1, 400)
    uu = np.interp(t, s, u); gg = np.interp(t, s, g)
    # light smoothing (keeps the ends)
    k = np.exp(-0.5 * (np.arange(-12, 13) / 4.0) ** 2); k /= k.sum()
    pad = 12
    uu_s = np.convolve(np.r_[2 * uu[0] - uu[1:pad + 1][::-1], uu, 2 * uu[-1] - uu[-pad - 1:-1][::-1]], k, "valid")
    gg_s = np.convolve(np.r_[2 * gg[0] - gg[1:pad + 1][::-1], gg, 2 * gg[-1] - gg[-pad - 1:-1][::-1]], k, "valid")
    uu_s[0], gg_s[0], uu_s[-1], gg_s[-1] = 0.0, 0.0, 1.0, 1.0
    s2 = np.r_[0, np.cumsum(np.hypot(np.diff(uu_s), np.diff(gg_s)))]; s2 /= s2[-1]
    tt = np.linspace(0, 1, n)
    out = (np.interp(tt, s2, uu_s), np.interp(tt, s2, gg_s))
    _CACHE["btpl"] = out
    return out


def back_template_cos(q=0.85, n=400):
    """解析の背の断面：g(u) = (1 − cos(π u^q)) / 2（足と頂で水平、変曲点は 1 つ）。q < 1 で急な所を足の側へ寄せ、頂の側の凸を長くする。"""
    u = np.linspace(0.0, 1.0, n)
    g = 0.5 * (1.0 - np.cos(np.pi * u ** q))
    return u, g


def row_crest(A, Y, j0=60, j1=130):
    j = j0 + int(np.argmax(Y[j0:j1]))
    return j, A[j], Y[j]


def sweep_back(a_top, H, W, n_cols):
    """背の掃引：足（a_top − W, 0）から頂（a_top, H）まで、型の断面を n_cols 点で（弧長の等分）。"""
    u, g = back_template(200)
    a = a_top - W + W * u; y = H * g
    s = np.r_[0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]
    t = np.linspace(0, s[-1], n_cols)
    return np.interp(t, s, a), np.interp(t, s, y)


def back_template_mode(mode, q, n=800):
    if mode == "r4":
        u, g = back_template(n)
        return u, g
    return back_template_cos(q, n)


def replace_back_v3(a_row, y_row, a_top, H, W, q=0.85, j_end=78, j_bl0=64, tpl="cos"):
    """背の掃引（v3）：解析の断面を足 (a_top − W, 0) → 仮の頂 (a_top, H) で作り、元の行の列 j_end の高さで切って
    列 18..j_end に弧長で配り、列 j_end で元の行の点にちょうど合わせ（上半分へ広げた移動）、列 j_bl0..j_end で元の行へ移す。
    列 j_end より頂の側（輪郭 78/130/131 を作る列 83〜112 を含む）は元の行のまま。"""
    a_new = a_row.copy(); y_new = y_row.copy()
    u, g = back_template_mode(tpl, q, 800)
    aa = a_top - W + W * u; yy = H * g
    ye = y_row[j_end]
    k = int(np.searchsorted(yy, min(ye, yy[-1] - 1e-9)))
    k = int(np.clip(k, 8, len(yy) - 1))
    aa, yy = aa[:k + 1], yy[:k + 1]
    s = np.r_[0, np.cumsum(np.hypot(np.diff(aa), np.diff(yy)))]
    t = np.linspace(0, s[-1], j_end - J_B + 1)
    sa, sy = np.interp(t, s, aa), np.interp(t, s, yy)
    wv = smoothstep((np.arange(len(sa)) - len(sa) * 0.3) / (len(sa) * 0.7))
    sa = sa + (a_row[j_end] - sa[-1]) * wv; sy = sy + (y_row[j_end] - sy[-1]) * wv
    a_new[J_B:j_end + 1] = sa; y_new[J_B:j_end + 1] = sy
    w = smoothstep((np.arange(j_bl0, j_end + 1) - j_bl0) / float(j_end - j_bl0))
    a_new[j_bl0:j_end + 1] = sa[j_bl0 - J_B:] * (1 - w) + a_row[j_bl0:j_end + 1] * w
    y_new[j_bl0:j_end + 1] = sy[j_bl0 - J_B:] * (1 - w) + y_row[j_bl0:j_end + 1] * w
    a_new[:J_B + 1] = np.linspace(a_row[0], a_new[J_B], J_B + 1); y_new[:J_B + 1] = 0.0
    return a_new, y_new


def replace_back_v2(a_row, y_row, a_top, H, W, q=0.85, j_top=J_TOP, j_bl0=76):
    """背の掃引（v2）：足 (a_top − W, 0) から頂 (a_top, H) まで解析の断面 g(u) を列 18..j_top に弧長で配り、
    列 j_bl0..j_top で元の行へなめらかに移す（頂の近くは元の形）。(a_top, H) は行の列 j_top の点をならした値。"""
    a_new = a_row.copy(); y_new = y_row.copy()
    u, g = back_template_cos(q)
    aa = a_top - W + W * u; yy = H * g
    s = np.r_[0, np.cumsum(np.hypot(np.diff(aa), np.diff(yy)))]
    t = np.linspace(0, s[-1], j_top - J_B + 1)
    sa, sy = np.interp(t, s, aa), np.interp(t, s, yy)
    # move the sweep so its top lands exactly on the row's own col j_top point (tiny shift, spread over the upper half)
    wv = smoothstep((np.arange(len(sa)) - len(sa) * 0.4) / (len(sa) * 0.6))
    sa = sa + (a_row[j_top] - sa[-1]) * wv; sy = sy + (y_row[j_top] - sy[-1]) * wv
    a_new[J_B:j_top + 1] = sa; y_new[J_B:j_top + 1] = sy
    w = smoothstep((np.arange(j_bl0, j_top + 1) - j_bl0) / float(j_top - j_bl0))
    a_new[j_bl0:j_top + 1] = sa[j_bl0 - J_B:] * (1 - w) + a_row[j_bl0:j_top + 1] * w
    y_new[j_bl0:j_top + 1] = sy[j_bl0 - J_B:] * (1 - w) + y_row[j_bl0:j_top + 1] * w
    a_new[:J_B + 1] = np.linspace(a_row[0], a_new[J_B], J_B + 1); y_new[:J_B + 1] = 0.0
    return a_new, y_new


def replace_back(a_row, y_row, a_top, H, W, j_end=84, j_bl0=66):
    """行の列 18..j_end を掃引の背で置き換え、列 j_bl0..j_end で元の行へなめらかに移す。
    掃引は足から『元の行の列 j_end の高さ』までを 18..j_end に配る（頂の近くの列は元の行の形のまま）。"""
    a_new = a_row.copy(); y_new = y_row.copy()
    yj = y_row[j_end]
    # sweep from the foot up to the height yj on the template (then the crest part stays as the base row)
    u, g = back_template(400)
    aa = a_top - W + W * u; yy = H * g
    k = int(np.searchsorted(yy, min(yj, yy[-1] - 1e-6)))
    k = max(k, 3)
    aa, yy = aa[:k + 1].copy(), yy[:k + 1].copy()
    # make the sweep end exactly at the base row's column j_end (shift the top part smoothly)
    da = a_row[j_end] - aa[-1]; dy = y_row[j_end] - yy[-1]
    wv = smoothstep(np.linspace(0, 1, len(aa)) / 1.0) ** 2
    aa = aa + da * wv; yy = yy + dy * wv
    s = np.r_[0, np.cumsum(np.hypot(np.diff(aa), np.diff(yy)))]
    t = np.linspace(0, s[-1], j_end - J_B + 1)
    sa, sy = np.interp(t, s, aa), np.interp(t, s, yy)
    a_new[J_B:j_end + 1] = sa; y_new[J_B:j_end + 1] = sy
    # blend j_bl0..j_end towards the base (the base keeps its column spacing near the crest)
    w = smoothstep((np.arange(j_bl0, j_end + 1) - j_bl0) / float(j_end - j_bl0))
    a_new[j_bl0:j_end + 1] = sa[j_bl0 - J_B:] * (1 - w) + a_row[j_bl0:j_end + 1] * w
    y_new[j_bl0:j_end + 1] = sy[j_bl0 - J_B:] * (1 - w) + y_row[j_bl0:j_end + 1] * w
    # the flat back sea 0..18: straight from the base's col 0 to the new foot
    a_new[:J_B + 1] = np.linspace(a_row[0], a_new[J_B], J_B + 1); y_new[:J_B + 1] = 0.0
    return a_new, y_new


_WALL = {}


def wall_line(y_lo=470.0, corner_mode="wall"):
    """72 の大きな輪郭（σ 12 px、kh_gate_lf）の下の部分（壁）：表示 px の y ≥ y_lo の点列（y の順）。"""
    if "w" not in _WALL:
        import sys as _s
        for p_ in (os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"), os.path.join(REPO, "Tools", "PaintingTruth"),
                   os.path.join(REPO, "Tools", "GWWaveGen"), os.path.join(REPO, "Tools", "GWWaveGen", "kstar3")):
            if p_ not in _s.path:
                _s.path.insert(0, p_)
        import kh_gate_lf as KG
        g = KG.LFGate()
        P = g.lf["72"]
        _WALL["w"] = P
    P = _WALL["w"]
    # the wall = the part of 72 after the tube's upper-left corner (the top-most point among the points left of x = 870)
    # walk up the wall from the bottom end while the image y keeps decreasing (tolerance 0.5 px): the stop is the corner
    if corner_mode == "ceiling860":
        left = np.nonzero(P[:, 0] < 870.0)[0]
        k = int(left[np.argmin(P[left, 1])])  # the ceiling's high point left of x = 870 (~(860, 383)), then the corner, then the wall
        return P[k:]
    if corner_mode == "ceiling":
        # from the ceiling's last part (the first point left of x = 935 above y = 420, walking from the lip tip) to the wall bottom
        k = int(np.nonzero((P[:, 0] < 935.0) & (P[:, 1] < 420.0))[0][0])
        return P[k:]
    top = np.nonzero(P[:, 1] < 430.0)[0]
    k = int(top[np.argmin(P[top, 0])])       # the left-most point of the upper part = the corner of the tube's mouth
    Q = P[k:]
    Q = Q[Q[:, 1] >= y_lo]
    o = np.argsort(Q[:, 1])
    return Q[o]


def _proj(c, a, y):
    import kh_common as KC
    return KC.project_unity(KC.world(np.atleast_1d(c), np.atleast_2d(a), np.atleast_2d(y)).reshape(-1, 3))


def lip_reach(c, A, Y, lr):
    """奥の行 c ∈ [c0, c1] の唇先を原画の 72 の壁（y ≥ y_lo の部分）へ T の向きに動かす。動かす量 Δa は列 j_lo..j_hi に
    山形の重み（列 200 で 1）で配る。唇先の像が壁の y の範囲の外の行は動かさない（c で滑らかに 0 へ）。"""
    import sys as _s
    kh = os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h")
    if kh not in _s.path:
        _s.path.insert(0, kh)
    Wl = wall_line(lr.get("y_lo", 470.0), lr.get("corner_mode", "wall"))
    from scipy.spatial import cKDTree
    kdW = cKDTree(Wl)
    A = A.copy()
    j_lo, j_hi, jt = lr.get("j_lo", 120), lr.get("j_hi", 300), 200
    jp = lr.get("j_plateau", jt)          # weight 1 on [jp, 200]: the crest moves with the tip (no squeezing of the lip-top)
    jj = np.arange(NU)
    wj = np.where(jj <= jp, smoothstep((jj - j_lo) / float(max(jp - j_lo, 1))), np.where(jj <= jt, 1.0, 1 - smoothstep((jj - jt) / float(j_hi - jt))))
    # vertical moves fade to 0 at the back foot (the back stretches; the flat sea stays at y = 0)
    wjy = wj * np.where(jj < J_TOP, smoothstep((jj - J_B) / float(J_TOP - J_B)), 1.0)
    rows = np.nonzero((c >= lr["c0"] - 1.0) & (c <= lr["c1"]))[0]
    dA = np.zeros(len(c))
    Lr = lr.get("reach_len_m", 0.0)
    for it in range(lr.get("passes", 4)):
        for r in rows:
            if Lr > 0:
                # weight by the section arc length from the tip (same falloff on the lip's upper and lower surfaces), 0 behind the crest
                sa = np.r_[0, np.cumsum(np.hypot(np.diff(A[r]), np.diff(Y[r])))]
                dsx = np.abs(sa - sa[jt]) / Lr
                wj = np.exp(-dsx ** 2) * smoothstep((jj - J_TOP) / 20.0) * (1 - smoothstep((jj - 330) / 30.0))
            p = _proj(c[r], A[r, jt:jt + 1], Y[r, jt:jt + 1])[0]
            if p[0] > lr.get("x_max", 900.0):
                continue
            if lr.get("snap2d"):
                dist, iq = kdW.query(p[:2])
                if dist > lr.get("snap_max_px", 60.0):
                    continue
                q = Wl[iq]
                pa = _proj(c[r], A[r, jt:jt + 1] + 0.1, Y[r, jt:jt + 1])[0]
                py_ = _proj(c[r], A[r, jt:jt + 1], Y[r, jt:jt + 1] + 0.1)[0]
                Jm = np.array([[(pa[0] - p[0]) / 0.1, (py_[0] - p[0]) / 0.1], [(pa[1] - p[1]) / 0.1, (py_[1] - p[1]) / 0.1]])
                try:
                    da, dy = np.linalg.solve(Jm, q - p[:2]) * lr.get("gain", 1.0)
                except np.linalg.LinAlgError:
                    continue
                ms = lr.get("max_step", 3.0)
                da = float(np.clip(da, -ms, ms)); dy = float(np.clip(dy, -ms, ms))
                wc = smoothstep((c[r] - (lr["c0"] - lr.get("fade", 1.0))) / lr.get("fade", 1.0))
                A[r] += wc * da * wj
                Y[r] += wc * dy * wjy * (Y[r] > 0.05)
                dA[r] += wc * da
                continue
            if not (Wl[0, 1] - 5 <= p[1] <= Wl[-1, 1] + 5):
                continue
            xw = np.interp(p[1], Wl[:, 1], Wl[:, 0])
            # dx/da by finite difference
            p2 = _proj(c[r], A[r, jt:jt + 1] + 0.1, Y[r, jt:jt + 1])[0]
            dxda = (p2[0] - p[0]) / 0.1
            if abs(dxda) < 1e-3:
                continue
            da = (xw - p[0]) / dxda * lr.get("gain", 1.0)
            da = float(np.clip(da, -lr.get("max_step", 3.0), lr.get("max_step", 3.0)))
            wc = smoothstep((c[r] - (lr["c0"] - lr.get("fade", 1.0))) / lr.get("fade", 1.0))
            A[r] += wc * da * wj
            dA[r] += wc * da
    return A, Y, {"dA_tip": dA.tolist()}


DEFAULT = {
    "schema": "GreatWave.kstar_p28.backfirst_design/2",
    "note_ja": "既定値（最適化の初期値）。各鍵は c [m] の 3 次スプライン。far は R3 の奥の行を唇先のまわりに相似に動かす（s・da）。"
               "back は掃引の背の幅 ρ = W/H（肩から奥の端まで 1 本のスプライン）。tail は手前の尾（原画の枠の外）。",
    "tail": {"c_lo": -60.0, "c_hi": -17.8, "c_tpl": -17.2, "blend": [-21.5, -17.8], "power": 1.25},
    "back": {"on": True, "knots_c": [-17.8, -12.0, -6.0, 0.0, 4.0, 8.0, 12.0, 15.0], "rho": None, "j_end": 84, "j_bl0": 66, "q": 0.85, "j_bl0v2": 76, "crest_sigma_c": 0.6, "mode": "v3", "j_end_v3": 78, "blend_cols": 14,
             "c_lo": -17.8, "c_hi": 15.0},
    "far": {"on": True, "blend": [0.5, 2.0], "knots_c": [1.0, 3.5, 6.0, 8.5, 10.5, 12.5, 14.0, 15.0], "s": None, "da": None, "pivot_col": 200},
    "far2": {"on": False, "c_a": 6.0, "c_b": 10.0, "blend": [3.0, 6.0], "knots_c": [3.0, 6.0, 8.0, 10.0, 12.0, 13.5, 14.5, 15.0],
             "H": None, "atop": None, "H_kind": "pchip"},
    "far_lip_reach": {"on": False, "c0": 6.0, "c1": 15.0, "y_lo": 470.0, "j_lo": 120, "j_hi": 300, "passes": 4, "gain": 1.0, "max_step": 3.0},
    "reach_adjust": {"on": False, "knots_c": [5.0, 6.0, 7.0, 8.0, 9.0, 10.0], "da": [0.0] * 6, "dy": [0.0] * 6, "j_lo": 120, "j_hi": 300},
    "back_smooth_c": {"on": False, "sigma_c": 0.0, "c_rng": [-16.0, 14.0], "cols": [18, 74]},
    "crest_smooth_c": {"on": False, "sigma_c": 0.0, "c_rng": [0.5, 6.0], "cols": [40, 160]},
    "tail_smooth_c": {"on": False, "sigma_c": 0.0, "c_hi": -18.0, "ramp": 3.0},
    "far_crest_smooth": {"on": False, "c0": 6.0, "sigma_c": 0.0, "ramp": 2.0, "strength": 1.0, "keep_end": True, "lift_max": 3.0},
    "shoulder_knob": {"on": False, "sigma_j": 0.0, "strength": 1.0, "c_rng": [-17.5, -5.5], "cols": [112, 196]},
    "shoulder_smooth": {"on": False, "sigma_c": 0.0, "c_rng": [-17.0, -6.0], "cols": [100, 192]},
}


def init_design(rho_far=0.9):
    """R3 を土台にした初期値：far の s = 1、da = 0（R3 の奥の行そのもの）。背の ρ は R3 の行の値（奥の端は rho_far まで広げる）。"""
    d = json.loads(json.dumps(DEFAULT))
    c, A, Y = load_base()
    rho = []
    for kc in d["back"]["knots_c"]:
        r = int(np.argmin(np.abs(c - kc)))
        at, H = A[r, J_TOP], Y[r, J_TOP]
        v = float((at - A[r, J_B]) / max(H, 0.5)) if H > 1.0 else rho_far
        if kc >= 6.0:
            v = max(v, rho_far)
        rho.append(v)
    d["back"]["rho"] = rho
    n = len(d["far"]["knots_c"])
    d["far"]["s"] = [1.0] * n
    d["far"]["da"] = [0.0] * n
    return d


def base_rows(d):
    """土台：R3 の行。base.mode = "r4back" なら、c ≤ c_max の行の背（列 < j_max）を R4 の背（R4 の整えの層でならした背）にする
    （c ≤ −2 の行では R4 と R3 の差は背の列 3〜75 だけ。唇は R3 のまま＝72 の σ12 の関門を保つ）。"""
    c, A0, Y0 = load_base()
    bm = d.get("base", {})
    if bm.get("mode") != "r4back":
        return c, A0, Y0
    z = np.load(BACK_TPL_R4)
    A4, Y4 = z["A"].astype(float), z["Y"].astype(float)
    wc = 1 - smoothstep((c - bm.get("c_max", 3.0)) / bm.get("c_fade", 1.5))
    jj = np.arange(NU)
    wj = 1 - smoothstep((jj - (bm.get("j_max", 78) - bm.get("blend_cols", 10))) / float(bm.get("blend_cols", 10)))
    W = wc[:, None] * wj[None, :]
    return c, A0 * (1 - W) + A4 * W, Y0 * (1 - W) + Y4 * W


def build(d, return_parts=False):
    """設計 d → (c, A, Y)。"""
    c, A0, Y0 = base_rows(d)
    A = A0.copy(); Y = Y0.copy()
    nv = len(c)
    info = {}
    # ---------------- 1a far crest-line smoothing: rows c >= c0 are scaled about their lip tip (col 200, y = 0) and shifted along T so
    #   that their crest (col 90) lands on the crest line smoothed along c (Gaussian sigma_c) -> the hook / crash of the far end is eased.
    fs = d.get("far_crest_smooth", {})
    if fs.get("on") and fs.get("sigma_c", 0) > 0.05:
        from scipy.ndimage import gaussian_filter1d
        sel = np.nonzero(c >= fs["c0"] - 4.0)[0]
        dcm = float(np.median(np.diff(c[sel])))
        a90 = A[sel, J_TOP].copy(); h90 = Y[sel, J_TOP].copy()
        # pad the end (c = 15) with the zero-height continuation so the smoothing does not lift the last rows
        a_s = gaussian_filter1d(a90, fs["sigma_c"] / dcm, mode="nearest")
        # heights beyond the last row are zero (the end of the wave): pad with zeros, not with the last value
        h_s = gaussian_filter1d(h90, fs["sigma_c"] / dcm, mode="constant", cval=0.0) if fs.get("end_zero", False) else             gaussian_filter1d(h90, fs["sigma_c"] / dcm, mode="nearest")
        if fs.get("keep_end", True):
            h_s = np.minimum(h_s, np.maximum(h90, 0.0) + fs.get("lift_max", 3.0))
        if fs.get("end_slope", 0) > 0:
            # the wave ends at the last row: soft-cap the smoothed height by a ramp of end_slope m per m of c down to the end
            cap = np.maximum(fs["end_slope"] * (c[sel].max() - c[sel]), 1e-4)
            pw = 4.0
            h_s = h_s * cap / (h_s ** pw + cap ** pw) ** (1.0 / pw)
        for i, r in enumerate(sel):
            if c[r] < fs["c0"] or h90[i] < 0.05:
                continue
            w = smoothstep((c[r] - fs["c0"]) / fs.get("ramp", 2.0)) * fs.get("strength", 1.0)
            if fs.get("end_fade"):
                e0, e1 = fs["end_fade"]          # the last tiny rows keep their own (R3) shape
                w *= 1 - smoothstep((c[r] - e0) / (e1 - e0))
            ht = h90[i] + (h_s[i] - h90[i]) * w; at_ = a90[i] + (a_s[i] - a90[i]) * w
            sr = max(ht, 0.02) / max(h90[i], 0.02)
            piv = A[r, 200]
            a_new = piv + sr * (A[r] - piv); y_new = sr * Y[r]
            a_new += at_ - a_new[J_TOP]
            a_new[:J_B + 1] = np.linspace(min(A0[r, 0], a_new[J_B] - 1.0), a_new[J_B], J_B + 1)
            a_new[J_E:] = np.linspace(a_new[J_E], max(A0[r, -1], a_new[J_E] + 1.0), NU - J_E)
            y_new[:J_B + 1] = 0.0; y_new[J_E:] = 0.0
            A[r] = a_new; Y[r] = y_new
    # ---------------- 1c far lip reach: move each far row's lip tip (col 200) along T onto the painted 72 wall at the tip's own height
    #   (the crest line and the back stay on the smoothed large form; only the lip reach changes). Newton on the projected x, a few passes.
    lr = d.get("far_lip_reach", {})
    if lr.get("on"):
        if lr.get("split_sigma_c", 0) > 0.05:
            # split the wall fit: the smooth part (along c) of the needed tip move is applied to the whole row (the crest moves with the
            # lip, no squeezing of the lip-top); the remainder is the lip reach below.
            from scipy.ndimage import gaussian_filter1d
            _, _, inf0 = lip_reach(c, A.copy(), Y.copy(), lr)
            dtip = np.array(inf0["dA_tip"])
            rr = np.nonzero(c >= lr["c0"] - lr.get("fade", 1.0) - 3.0)[0]
            dcm = float(np.median(np.diff(c[rr])))
            sh = np.zeros(len(c))
            sh[rr] = gaussian_filter1d(dtip[rr], lr["split_sigma_c"] / dcm, mode="nearest") * lr.get("split_gain", 1.0)
            jjs = np.arange(NU)
            wsh = smoothstep((jjs - J_B) / 12.0)
            A = A + sh[:, None] * wsh[None, :]
            A[:, :J_B + 1] = np.minimum(A[:, :J_B + 1], A[:, J_B:J_B + 1])
            info["rigid_shift"] = sh.tolist()
        A_b, Y_b = A.copy(), Y.copy()
        A, Y, info["lip_reach"] = lip_reach(c, A, Y, lr)
        if lr.get("smooth_sigma_c", 0) > 0.05:
            # smooth the reach displacement field along c (per-row Newton steps are independent -> small row-to-row lumps)
            from scipy.ndimage import gaussian_filter1d
            rr = np.nonzero(c >= lr["c0"] - 3.0)[0]
            dcm = float(np.median(np.diff(c[rr])))
            dAf = gaussian_filter1d(A[rr] - A_b[rr], lr["smooth_sigma_c"] / dcm, axis=0, mode="nearest")
            dYf = gaussian_filter1d(Y[rr] - Y_b[rr], lr["smooth_sigma_c"] / dcm, axis=0, mode="nearest")
            wr = smoothstep((c[rr] - (lr["c0"] - 1.0)) / 1.0) * (1 - smoothstep((c[rr] - lr["c1"]) / 0.8))
            A[rr] = A_b[rr] + dAf * wr[:, None]; Y[rr] = Y_b[rr] + dYf * wr[:, None]
    ra = d.get("reach_adjust", {})
    if ra.get("on"):
        dA_ = spline(ra["knots_c"], ra["da"], c); dY_ = spline(ra["knots_c"], ra["dy"], c)
        fdr = ra.get("fade", 1.0)
        wc_ = smoothstep((c - (ra["knots_c"][0] - fdr + 1.0)) / fdr) * (1 - smoothstep((c - ra["knots_c"][-1]) / fdr))
        jj_ = np.arange(NU); j_lo_, j_hi_, jt_ = ra.get("j_lo", 120), ra.get("j_hi", 300), 200
        jp_ = ra.get("j_plateau", jt_)
        wj_ = np.where(jj_ <= jp_, smoothstep((jj_ - j_lo_) / float(max(jp_ - j_lo_, 1))), np.where(jj_ <= jt_, 1.0, 1 - smoothstep((jj_ - jt_) / float(j_hi_ - jt_))))
        A = A + (wc_ * dA_)[:, None] * wj_[None, :]
        wjy_ = wj_ * np.where(jj_ < J_TOP, smoothstep((jj_ - J_B) / float(J_TOP - J_B)), 1.0)
        Y = Y + (wc_ * dY_)[:, None] * wjy_[None, :] * (Y > 0.05)
    ft = d.get("far_top_round", {})
    if ft.get("on") and ft.get("sigma_j", 0) > 0.5:
        # round the crest of the small far curls: smooth the section along its columns around the crest (cols j0..j1, ends pinned)
        from scipy.ndimage import gaussian_filter1d
        j0, j1 = ft.get("cols", [50, 185])
        jj = np.arange(j0, j1 + 1)
        wj = smoothstep((jj - j0) / 25.0) * (1 - smoothstep((jj - (j1 - 25)) / 25.0))
        for r in range(nv):
            wc = smoothstep((c[r] - (ft["c_rng"][0] - 1.5)) / 1.5) * (1 - smoothstep((c[r] - ft["c_rng"][1]) / 1.5))
            if wc <= 0 or Y[r, J_TOP] < 0.5:
                continue
            As = gaussian_filter1d(A[r, j0 - 30:j1 + 31], ft["sigma_j"], mode="nearest")[30:-30]
            Ys = gaussian_filter1d(Y[r, j0 - 30:j1 + 31], ft["sigma_j"], mode="nearest")[30:-30]
            w = wc * wj * ft.get("strength", 1.0)
            A[r, j0:j1 + 1] = A[r, j0:j1 + 1] * (1 - w) + As * w
            Y[r, j0:j1 + 1] = Y[r, j0:j1 + 1] * (1 - w) + Ys * w
    ls_ = d.get("lip_smooth_c", {})
    if ls_.get("on") and ls_.get("sigma_c", 0) > 0.05:
        # the lip underside / tube top smoothed along c (the along-c 4th difference, bump4) on rows c_rng, cols [j0, j1]
        from scipy.ndimage import gaussian_filter1d
        rr = np.nonzero((c >= ls_["c_rng"][0] - 3) & (c <= ls_["c_rng"][1] + 3))[0]
        j0, j1 = ls_["cols"]
        dcm = float(np.median(np.diff(c[rr])))
        As = gaussian_filter1d(A[rr, j0:j1 + 1], ls_["sigma_c"] / dcm, axis=0, mode="nearest")
        Ys = gaussian_filter1d(Y[rr, j0:j1 + 1], ls_["sigma_c"] / dcm, axis=0, mode="nearest")
        fd = ls_.get("fade", 2.0)
        wc = smoothstep((c[rr] - ls_["c_rng"][0] + fd) / fd) * (1 - smoothstep((c[rr] - ls_["c_rng"][1]) / fd))
        jj = np.arange(j0, j1 + 1)
        wj = smoothstep((jj - j0) / 15.0) * (1 - smoothstep((jj - (j1 - 15)) / 15.0))
        Wm = wc[:, None] * wj[None, :]
        A[rr, j0:j1 + 1] = A[rr, j0:j1 + 1] * (1 - Wm) + As * Wm
        Y[rr, j0:j1 + 1] = Y[rr, j0:j1 + 1] * (1 - Wm) + Ys * Wm
    # ---------------- 1 far rows (after 1a): the rows moved as a whole about the lip tip (similarity), smooth in c — the silhouette fit of the far end
    f = d["far"]
    if f.get("on", True):
        s = np.maximum(spline(f["knots_c"], f["s"], c), 0.05)
        da = spline(f["knots_c"], f["da"], c)
        jp = int(f.get("pivot_col", 200))
        for r in range(nv):
            if c[r] < f["blend"][0]:
                continue
            w = smoothstep((c[r] - f["blend"][0]) / (f["blend"][1] - f["blend"][0]))
            sr = 1.0 + (s[r] - 1.0) * w; dr = da[r] * w
            piv = A[r, jp]
            a_new = piv + sr * (A[r] - piv) + dr
            y_new = sr * Y[r]
            a_new[:J_B + 1] = np.linspace(min(A0[r, 0], a_new[J_B] - 1.0), a_new[J_B], J_B + 1)
            a_new[J_E:] = np.linspace(a_new[J_E], max(A0[r, -1], a_new[J_E] + 1.0), NU - J_E)
            A[r] = a_new; Y[r] = y_new
        info["far_s"] = s; info["far_da"] = da
    # ---------------- 1b far rows v2: a morph family of R3's own normalized far sections, placed on a smooth crest line
    #   N(c) = lerp(N(c_a), N(c_b), m(c)) with N_r = ((A_r - a90_r)/H_r, Y_r/H_r); row = (a_top(c) + H(c) N_a, H(c) N_y).
    #   H(c) and a_top(c) are smooth splines (keys "H", "atop"); blended in from R3 over "blend".
    f2 = d.get("far2", {})
    if f2.get("on"):
        ra = int(np.argmin(np.abs(c - f2["c_a"]))); rb = int(np.argmin(np.abs(c - f2["c_b"])))
        def norm(r):
            H = A0[r, J_TOP] * 0 + Y0[r, J_TOP]
            return (A0[r] - A0[r, J_TOP]) / H, Y0[r] / H
        Na = norm(ra); Nb = norm(rb)
        Hc = np.maximum(spline(f2["knots_c"], f2["H"], c, kind=f2.get("H_kind", "pchip")), 0.0)
        at = spline(f2["knots_c"], f2["atop"], c)
        for r in range(nv):
            if c[r] < f2["blend"][0]:
                continue
            m = smoothstep((c[r] - f2["c_a"]) / (f2["c_b"] - f2["c_a"]))
            na = Na[0] * (1 - m) + Nb[0] * m; ny = Na[1] * (1 - m) + Nb[1] * m
            hh = max(Hc[r], 0.01)
            a_new = at[r] + hh * na; y_new = hh * ny
            a_new[:J_B + 1] = np.linspace(min(A0[r, 0], a_new[J_B] - 1.0), a_new[J_B], J_B + 1)
            a_new[J_E:] = np.linspace(a_new[J_E], max(A0[r, -1], a_new[J_E] + 1.0), NU - J_E)
            y_new[:J_B + 1] = 0.0; y_new[J_E:] = 0.0
            w = smoothstep((c[r] - f2["blend"][0]) / (f2["blend"][1] - f2["blend"][0]))
            A[r] = A[r] * (1 - w) + a_new * w
            Y[r] = Y[r] * (1 - w) + y_new * w
    if d["tail"].get("first"):
        # ---------------- 4 near tail (outside the painting frame): similarity of the c_tpl row (before the back sweep when tail.first)
        t = d["tail"]
        rt = int(np.argmin(np.abs(c - t["c_tpl"])))
        jt, att, Ht = row_crest(A[rt], Y[rt])
        for r in range(nv):
            if c[r] >= t["blend"][1]:
                continue
            x = (c[r] - t["c_lo"]) / (t["c_hi"] - t["c_lo"])
            if t.get("mode", "power") == "cos":
                # rounded near end: height k_y = (1 - cos(pi x)) / 2 (flat at both ends), width k_a = k_y ** aniso (wider, lower rows)
                ky = 0.5 - 0.5 * math.cos(math.pi * min(max(x, 0.0), 1.0))
                ky = max(ky, 1e-3)
                ka = ky ** t.get("aniso", 0.5)
            else:
                ky = ka = max(x, 0.0) ** t["power"]
            ta = A[rt] - att; ty = Y[rt]
            a_new = att + ka * ta
            y_new = ky * ty
            a_new[:J_B + 1] = np.linspace(A0[r, 0], a_new[J_B], J_B + 1); y_new[:J_B + 1] = 0.0
            a_new[J_E:] = np.linspace(a_new[J_E], A0[r, -1], NU - J_E); y_new[J_E:] = 0.0
            w = 1 - smoothstep((c[r] - t["blend"][0]) / (t["blend"][1] - t["blend"][0]))
            A[r] = A[r] * (1 - w) + a_new * w
            Y[r] = Y[r] * (1 - w) + y_new * w
    # ---------------- 2 back sweep (shoulder .. far end): one normalized back profile, width W = rho(c) * H(c)
    b = d["back"]
    if b.get("on", True):
        rho = spline(b["knots_c"], b["rho"], c)
        A1, Y1 = A.copy(), Y.copy()
        # the crest line (col 90) smoothed along c (the sweep must not copy row-to-row wiggles of the crest)
        from scipy.ndimage import gaussian_filter1d
        sel = np.nonzero((c >= b["c_lo"] - 4.5) & (c <= b["c_hi"] + 0.01))[0]
        dcm = float(np.median(np.diff(c[sel])))
        sig = b.get("crest_sigma_c", 0.6) / dcm
        a90 = A1[:, J_TOP].copy(); y90 = Y1[:, J_TOP].copy()
        a90[sel] = gaussian_filter1d(A1[sel, J_TOP], sig, mode="nearest"); y90[sel] = gaussian_filter1d(Y1[sel, J_TOP], sig, mode="nearest")
        q = b.get("q", 0.85)
        for r in range(nv):
            if not (b["c_lo"] - 4.0 <= c[r] <= b["c_hi"] + 1e-6):
                continue
            H = y90[r]
            if H < 0.6:
                continue
            if b.get("mode", "v3") == "v3":
                # rows that draw 78/130/131 (c < +3) keep their own shape from col j_end on; the hidden far rows attach at the crest
                je = int(round(np.interp(c[r], [3.0, 6.0], [b.get("j_end_v3", 78), b.get("j_end_far", J_TOP)])))
                jb0 = je - b.get("blend_cols", 14)
                a_new, y_new = replace_back_v3(A1[r], Y1[r], a90[r], H, rho[r] * H, q, je, jb0, b.get("tpl", "cos"))
            else:
                a_new, y_new = replace_back_v2(A1[r], Y1[r], a90[r], H, rho[r] * H, q, J_TOP, b.get("j_bl0v2", 76))
            w = smoothstep((c[r] - (b["c_lo"] - 4.0)) / 4.0)
            if b.get("c_skip"):
                s0, s1 = b["c_skip"]; fd = b.get("skip_fade", 1.5)
                w *= 1 - smoothstep((c[r] - s0) / fd) * (1 - smoothstep((c[r] - (s1 - fd)) / fd))
            A[r] = A1[r] * (1 - w) + a_new * w
            Y[r] = Y1[r] * (1 - w) + y_new * w
        info["rho"] = rho
    # ---------------- 3 shoulder lip-top smoothing along c (optional)
    ss = d.get("shoulder_smooth", {})
    if ss.get("on") and ss.get("sigma_c", 0) > 0.05:
        from scipy.ndimage import gaussian_filter1d
        rr = np.nonzero((c >= ss["c_rng"][0] - 3) & (c <= ss["c_rng"][1] + 3))[0]
        j0, j1 = ss["cols"]
        dc = float(np.median(np.diff(c[rr])))
        As = gaussian_filter1d(A[rr, j0:j1 + 1], ss["sigma_c"] / dc, axis=0, mode="nearest")
        Ys = gaussian_filter1d(Y[rr, j0:j1 + 1], ss["sigma_c"] / dc, axis=0, mode="nearest")
        wc = smoothstep((c[rr] - ss["c_rng"][0] + 3) / 3.0) * (1 - smoothstep((c[rr] - ss["c_rng"][1]) / 3.0))
        wj = smoothstep((np.arange(j0, j1 + 1) - j0) / 8.0) * (1 - smoothstep((np.arange(j0, j1 + 1) - (j1 - 8)) / 8.0))
        Wm = wc[:, None] * wj[None, :]
        A[rr, j0:j1 + 1] = A[rr, j0:j1 + 1] * (1 - Wm) + As * Wm
        Y[rr, j0:j1 + 1] = Y[rr, j0:j1 + 1] * (1 - Wm) + Ys * Wm
    # ---------------- 3b shoulder lip knob softening along the section (b region; rows c_rng, cols [j0, j1], pinned ends)
    kn = d.get("shoulder_knob", {})
    if kn.get("on") and kn.get("sigma_j", 0) > 0.5:
        from scipy.ndimage import gaussian_filter1d
        j0, j1 = kn["cols"]
        jj = np.arange(j0, j1 + 1)
        wj = smoothstep((jj - j0) / 10.0) * (1 - smoothstep((jj - (j1 - 10)) / 10.0))
        for r in range(nv):
            wc = smoothstep((c[r] - (kn["c_rng"][0] - 2.0)) / 2.0) * (1 - smoothstep((c[r] - kn["c_rng"][1]) / 2.5))
            if wc <= 0:
                continue
            As = gaussian_filter1d(A[r, j0 - 30:j1 + 31], kn["sigma_j"], mode="nearest")[30:-30]
            Ys = gaussian_filter1d(Y[r, j0 - 30:j1 + 31], kn["sigma_j"], mode="nearest")[30:-30]
            w = wc * wj * kn.get("strength", 1.0)
            A[r, j0:j1 + 1] = A[r, j0:j1 + 1] * (1 - w) + As * w
            Y[r, j0:j1 + 1] = Y[r, j0:j1 + 1] * (1 - w) + Ys * w
    if not d["tail"].get("first"):
        # ---------------- 4 near tail (outside the painting frame): similarity of the c_tpl row
        t = d["tail"]
        rt = int(np.argmin(np.abs(c - t["c_tpl"])))
        jt, att, Ht = row_crest(A[rt], Y[rt])
        for r in range(nv):
            if c[r] >= t["blend"][1]:
                continue
            x = (c[r] - t["c_lo"]) / (t["c_hi"] - t["c_lo"])
            if t.get("mode", "power") == "cos":
                # rounded near end: height k_y = (1 - cos(pi x)) / 2 (flat at both ends), width k_a = k_y ** aniso (wider, lower rows)
                ky = 0.5 - 0.5 * math.cos(math.pi * min(max(x, 0.0), 1.0))
                ky = max(ky, 1e-3)
                ka = ky ** t.get("aniso", 0.5)
            else:
                ky = ka = max(x, 0.0) ** t["power"]
            ta = A[rt] - att; ty = Y[rt]
            a_new = att + ka * ta
            y_new = ky * ty
            a_new[:J_B + 1] = np.linspace(A0[r, 0], a_new[J_B], J_B + 1); y_new[:J_B + 1] = 0.0
            a_new[J_E:] = np.linspace(a_new[J_E], A0[r, -1], NU - J_E); y_new[J_E:] = 0.0
            w = 1 - smoothstep((c[r] - t["blend"][0]) / (t["blend"][1] - t["blend"][0]))
            A[r] = A[r] * (1 - w) + a_new * w
            Y[r] = Y[r] * (1 - w) + y_new * w
    # ---------------- 5 interior smoothness prior along c (the back cols 18..j1 and the tail rows outside the painting frame)
    from scipy.ndimage import gaussian_filter1d
    bs = d.get("back_smooth_c", {})
    if bs.get("on") and bs.get("sigma_c", 0) > 0.05:
        rr = np.nonzero((c >= bs["c_rng"][0] - 3) & (c <= bs["c_rng"][1] + 3))[0]
        j0, j1 = bs.get("cols", [18, 74])
        dcm = float(np.median(np.diff(c[rr])))
        As = gaussian_filter1d(A[rr, j0:j1 + 1], bs["sigma_c"] / dcm, axis=0, mode="nearest")
        Ys = gaussian_filter1d(Y[rr, j0:j1 + 1], bs["sigma_c"] / dcm, axis=0, mode="nearest")
        wc = smoothstep((c[rr] - bs["c_rng"][0] + 3) / 3.0) * (1 - smoothstep((c[rr] - bs["c_rng"][1]) / 3.0))
        wc = wc * smoothstep((Y[rr, J_TOP] - 0.3) / 1.0)      # the flat end rows (c = 15) are not lifted by their neighbours
        jj = np.arange(j0, j1 + 1)
        wj = 1 - smoothstep((jj - (j1 - 12)) / 12.0)
        Wm = wc[:, None] * wj[None, :]
        A[rr, j0:j1 + 1] = A[rr, j0:j1 + 1] * (1 - Wm) + As * Wm
        Y[rr, j0:j1 + 1] = Y[rr, j0:j1 + 1] * (1 - Wm) + Ys * Wm
        A[rr, :J_B + 1] = np.linspace(0, 1, J_B + 1)[None, :] * (A[rr, J_B:J_B + 1] - A[rr, :1]) + A[rr, :1]
    cs = d.get("crest_smooth_c", {})
    if cs.get("on") and cs.get("sigma_c", 0) > 0.05:
        rr = np.nonzero((c >= cs["c_rng"][0] - 3) & (c <= cs["c_rng"][1] + 3))[0]
        j0, j1 = cs.get("cols", [40, 160])
        dcm = float(np.median(np.diff(c[rr])))
        As = gaussian_filter1d(A[rr, j0:j1 + 1], cs["sigma_c"] / dcm, axis=0, mode="nearest")
        Ys = gaussian_filter1d(Y[rr, j0:j1 + 1], cs["sigma_c"] / dcm, axis=0, mode="nearest")
        wc = smoothstep((c[rr] - cs["c_rng"][0] + 2) / 2.0) * (1 - smoothstep((c[rr] - cs["c_rng"][1]) / 2.0))
        jj = np.arange(j0, j1 + 1)
        wj = smoothstep((jj - j0) / 25.0) * (1 - smoothstep((jj - (j1 - 30)) / 30.0))
        Wm = wc[:, None] * wj[None, :]
        A[rr, j0:j1 + 1] = A[rr, j0:j1 + 1] * (1 - Wm) + As * Wm
        Y[rr, j0:j1 + 1] = Y[rr, j0:j1 + 1] * (1 - Wm) + Ys * Wm
    ts = d.get("tail_smooth_c", {})
    if ts.get("on") and ts.get("sigma_c", 0) > 0.05:
        rr = np.nonzero(c <= ts["c_hi"] + 4.0)[0]
        # the rows are unevenly spaced in the tail: smooth on a uniform resampling of c, then map back
        cu = np.linspace(c[rr].min(), c[rr].max(), 400)
        du = cu[1] - cu[0]
        Au = np.stack([np.interp(cu, c[rr], A[rr, j]) for j in range(NU)], 1)
        Yu = np.stack([np.interp(cu, c[rr], Y[rr, j]) for j in range(NU)], 1)
        Au = gaussian_filter1d(Au, ts["sigma_c"] / du, axis=0, mode="nearest"); Yu = gaussian_filter1d(Yu, ts["sigma_c"] / du, axis=0, mode="nearest")
        As = np.stack([np.interp(c[rr], cu, Au[:, j]) for j in range(NU)], 1); Ys = np.stack([np.interp(c[rr], cu, Yu[:, j]) for j in range(NU)], 1)
        w = 1 - smoothstep((c[rr] - (ts["c_hi"] - ts.get("ramp", 3.0))) / ts.get("ramp", 3.0))
        A[rr] = A[rr] * (1 - w[:, None]) + As * w[:, None]
        Y[rr] = Y[rr] * (1 - w[:, None]) + Ys * w[:, None]
    if return_parts:
        return c, A, Y, info
    return c, A, Y


if __name__ == "__main__":
    import sys
    d = init_design()
    print(json.dumps(d, indent=1)[:2000])
    c, A, Y = build(d)
    c0, A0, Y0 = load_base()
    print("max |dA| %.3f |dY| %.3f" % (np.abs(A - A0).max(), np.abs(Y - Y0).max()))
    if len(sys.argv) > 1:
        np.savez_compressed(sys.argv[1], A=A, Y=Y, c=c)
