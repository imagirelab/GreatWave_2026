# -*- coding: utf-8 -*-
"""美術の見本02 BACK の生成器：K*′ P28R2rec の見えない背を、後ろから見て一つの山（中ほどがいちばん盛り上がり、両側へなだらかに下がる）にする。
py -3.10 back_build.py <out_prefix> [design.json]

なぜ（利用者の Q30-2、要求書 S4）：P28R2rec の背は、高さごとの背の位置（平面の等高線の背の側）が c ≈ −4 の縦の肋と、奥の端（c ≈ +8〜+12。
頂の線が後ろへ流れる所）の二つで後ろへ出て、その間の c ≈ +0.4〜+2（原画の頂のすぐ奥）が 1.0〜1.7 m 引っ込む（back_measure.py の測り）。
後ろ 65°・真後ろで暗い縦の帯に見え、「两边凸起中间凹陷」に読める。

作り方（数値だけ。参照モデルは読まない、F13-1）：
  1. 高さ y ごと（0.25 m おき）に、背の等高線 d(c) = −a_back(c, y)（背の列 18..頂が y を最初に越える所の a）を読む。
  2. 窓 c ∈ [window_c0, 等高線の奥の端] で、両端を結ぶ弦を引き、弦からの出っ張り g(c) = d − 弦 を求める。
  3. 目標の出っ張りを、c_m（原画の頂の最も高い行）で最大になる一つの山 G·φ(c)、φ = (1 − u²)^p（左右で幅の違う u）にする。
     G は g と同じ面積になるように決める（高さごとの背の量を保つ。押し出す所と引っ込める所が釣り合う）。
  4. 差 dl = Gφ − g（正 ＝ 後ろへ出す）を (c, y) でならし（σ_c、σ_y）、各頂点を同じ高さのまま a 方向に −dl だけずらす。
     頂のまわり（頂から弧長 top_m）では 0 へ戻す。列 0..17 の海の帯は足までの間に比例で並べ直す（r01_shoulder_build と同じ）。
  5. 制約は r01_shoulder_build.Build と同じ：原画視点で見えている四角形の頂点とその隣は動かさない（厳密な z バッファー）、
     原画の空の射線の禁止域（3 px）と段階9 の船・手前の海の射線の禁止域に新しくかからない、断面が新しく自己交差しない。
     動かせる割合を c 方向・列の方向にならし、禁止域で押さえる（3 次元でなめらか）。
格子 400×240、目印の列、UV、行の c、境の輪は変えない。出力は Unity/Build/Polish/sample02/back/ の下（Git 対象外）。
"""
import os
import sys
import json
import time

import numpy as np
from scipy.ndimage import gaussian_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import back_common as BC  # noqa: E402
sys.path.insert(0, os.path.join(BC.REPO, "Tools", "GWWaveGen", "kstar_p28"))
import r01_shoulder_common as S  # noqa: E402
S.OUT = BC.OUT                         # 見えている四角形のキャッシュ（土台と同じ P28R2rec から作ったもの）はこの見本の場所から読む
import r01_shoulder_build as SB  # noqa: E402

R = S.R
KC = S.KC

J_TOP_MAX = 110

BACK_DEFAULT = {
    "back": {
        "c_m": -0.8,            # 一つの山の頂（原画の頂の最も高い行）
        "window_c0": -14.0,     # これより −c 側（b区域と手前の尾）は変えない
        "p": 0.75,              # φ = (1 − u²)^p（p ≤ 1 で上に凸）
        "gain": 1.0,            # G の倍率（1 ＝ 面積を保つ）
        "level_step": 0.25,
        "y_min": 0.05,
        "sigma_c_m": 1.0,
        "sigma_y_m": 1.0,
        "top_m": 1.2,           # 頂から弧長 top_m で 0 へ戻す
        "push_max_m": 4.0,      # 後ろへ出す量の上限
        "pull_max_m": 4.5,      # 引っ込める量の上限
        "edge_fade_m": 2.0,     # 窓の −c 端のなめらかな戻し
    },
    "free_cap": 190,
    "end_fade_m": 1.5,
    "anchor_margin_cols": 3,
    "anchor_cap": 92,
    "anchor_minwin_rows": 2,
    "sea_cols": 18,
    "sigma_c_m": 0.6,
    "sigma_cols": 2.0,
    "clear_margin_m": 0.3,
    "desired_sigma_c_m": 0.0,
    "desired_sigma_cols": 1.5,
}


def tube_inner_a(A, Y, jt, i, y):
    """行 i の頂より前の列（唇・管・前面）が高さ y を横切る所の a の最小（背と管の間の壁の内側）。なければ nan。"""
    a = A[i, jt[i]:]; yy = Y[i, jt[i]:]
    s = np.sign(yy - y)
    k = np.nonzero(s[:-1] * s[1:] < 0)[0]
    if not len(k):
        return np.nan
    t = (y - yy[k]) / (yy[k + 1] - yy[k])
    return float((a[k] + t * (a[k + 1] - a[k])).min())


def back_target_hull(c, A, Y, g):
    """方式 hull（2 回目）：高さごとに、背の等高線 d(c) を「上に凸な包絡（入り江を埋める）＋丸み ε·φ」へ置き換える。
    c ≈ −4 の縦の肋は先に少し引っ込め（rib_pull_m）、奥の端は管との壁（wall_min_m）より前へは引かない。
    目標は c 方向にならした（σ target_sigma_c_m）なめらかな曲線なので、行ごとの細い縦の襞も一緒に消える。"""
    H, jt, at = BC.crest(A, Y)
    ys = np.arange(g["y_min"], H.max() - 0.05, g["level_step"])
    nv = len(c)
    DL = np.zeros((nv, len(ys)))
    M = np.zeros((nv, len(ys)))
    lev = []
    for k, y in enumerate(ys):
        ab = BC.back_level_a(A, Y, jt, y)
        ok = np.isfinite(ab) & (H > y + 0.02)
        im = int(np.argmin(np.abs(c - g["c_m"])))
        if not ok[im]:
            continue
        i0 = im
        while i0 - 1 >= 0 and ok[i0 - 1]:
            i0 -= 1
        i1 = im
        while i1 + 1 < nv and ok[i1 + 1]:
            i1 += 1
        idx = np.arange(i0, i1 + 1)
        idx = idx[c[idx] >= g["window_c0"]]
        if len(idx) < 8:
            continue
        cc = c[idx]; dd = -ab[idx]
        lo, hi = cc[0], cc[-1]
        fy = y / BC.H0
        rib = g["rib_pull_m"] * np.exp(-0.5 * ((cc - g["rib_c"]) / g["rib_w_m"]) ** 2) * R.ss((fy - g["rib_f"][0]) / 0.1) * (1 - R.ss((fy - g["rib_f"][1]) / 0.1))
        dmod = dd - rib
        env = dmod + BC.concave_hull_gap(cc, dmod)
        cm = min(max(g["c_m"], lo + 0.5), hi - 0.5)
        u = np.where(cc < cm, (cc - cm) / (cm - lo), (cc - cm) / (hi - cm))
        phi = (1.0 - np.clip(u * u, 0, 1)) ** g["p"]
        tgt = env + g["round_m"] * phi
        # 壁の下限（奥の端）
        floor = np.array([(-tube_inner_a(A, Y, jt, int(i), y) + g["wall_min_m"]) if np.isfinite(tube_inner_a(A, Y, jt, int(i), y)) else -np.inf
                          for i in idx])
        floor = np.minimum(floor, dd)            # 今より前へは壁の分しか引かない（今が壁より薄い所は今のまま）
        tgt = np.maximum(tgt, floor)
        # c 方向にならす（上に凸は保たれる）
        xs = np.arange(lo, hi + 1e-9, 0.1)
        from scipy.ndimage import gaussian_filter1d as gf
        ts = gf(np.interp(xs, cc, tgt), g["target_sigma_c_m"] / 0.1, mode="nearest")
        tgt = np.maximum(np.interp(cc, xs, ts), floor)
        dl = tgt - dd
        if c[i0] < g["window_c0"]:
            dl *= R.ss((cc - g["window_c0"]) / g["edge_fade_m"])
        dl = np.clip(dl, -g["pull_max_m"], g["push_max_m"])
        DL[idx, k] = dl
        M[idx, k] = 1.0
        lev.append({"y": round(float(y), 2), "c_lo": round(float(lo), 2), "c_hi": round(float(hi), 2),
                    "push_max": round(float(dl.max()), 3), "pull_max": round(float(-dl.min()), 3)})
    sy = g["sigma_y_m"] / g["level_step"]
    num = gaussian_filter1d(R.csmooth(c, DL * M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else DL * M, sy, axis=1, mode="nearest")
    den = gaussian_filter1d(R.csmooth(c, M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else M, sy, axis=1, mode="nearest")
    DLs = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    DLs *= R.ss(den / 0.5)
    return ys, DLs, lev


def concave_lsq(x, f, w, fix_lo=True, fix_hi=True, floor=None, iters=6):
    """重み付き最小二乗で f に最も近い上に凸な（入り江のない）折れ線を求める。
    f(x_k) = f0 + s0 (x_k − x_0) − Σ_j w_j (x_k − x_j)_+ 、w_j ≥ 0（傾きは減るだけ）。両端は大きな重みで今の値に留める。
    floor（下限）を下回る所は、その下限へ大きな重みで引き寄せて解き直す。"""
    from scipy.optimize import lsq_linear
    x = np.asarray(x, float); f = np.asarray(f, float); n = len(x)
    knots = x[1:-1]
    Bm = np.c_[np.ones(n), x - x[0], -np.maximum(x[:, None] - knots[None, :], 0.0)]
    lb = np.r_[-np.inf, -np.inf, np.zeros(len(knots))]
    ub = np.full(Bm.shape[1], np.inf)
    ww = np.asarray(w, float).copy()
    tgt = f.copy()
    if fix_lo:
        ww[0] = 1e3
    if fix_hi:
        ww[-1] = 1e3
    sol = None
    for _ in range(iters):
        sw = np.sqrt(ww)
        r = lsq_linear(Bm * sw[:, None], tgt * sw, bounds=(lb, ub), method="bvls", lsmr_tol="auto", max_iter=2000)
        sol = Bm @ r.x
        if floor is None:
            break
        bad = sol < floor - 1e-3
        if not bad.any():
            break
        tgt = np.where(bad, floor + 0.02, tgt)
        ww = np.where(bad, np.maximum(ww, 50.0), ww)
    return sol


def concave_lsq_bounded(x, f, w, lb, ub, iters=12):
    """concave_lsq に、点ごとの下限 lb・上限 ub を足したもの（はみ出した点をその境へ大きな重みで引き寄せて解き直す）。
    両立しない時は、境を守った形（最後に [lb, ub] へ切る）を返す。"""
    from scipy.optimize import lsq_linear
    x = np.asarray(x, float); f = np.asarray(f, float); n = len(x)
    knots = x[1:-1]
    Bm = np.c_[np.ones(n), x - x[0], -np.maximum(x[:, None] - knots[None, :], 0.0)]
    lbt = np.r_[-np.inf, -np.inf, np.zeros(len(knots))]
    ubt = np.full(Bm.shape[1], np.inf)
    ww = np.asarray(w, float).copy(); ww[0] = ww[-1] = 1e3
    tgt = f.copy()
    sol = f.copy()
    for _ in range(iters):
        sw = np.sqrt(ww)
        r = lsq_linear(Bm * sw[:, None], tgt * sw, bounds=(lbt, ubt), method="bvls", max_iter=2000)
        sol = Bm @ r.x
        lo_bad = sol < lb - 1e-3; hi_bad = sol > ub + 1e-3
        if not (lo_bad.any() or hi_bad.any()):
            break
        tgt = np.where(lo_bad, lb, np.where(hi_bad, ub, tgt))
        ww = np.where(lo_bad | hi_bad, ww * 4.0 + 5.0, ww)
    return np.clip(sol, lb, ub)


def row_wall_at(A, Y, jt, i, y, ab):
    """行 i、高さ y の、背（a = ab）から最初の内側の面（頂より前の列の交わり）までの水平の厚み。内側の面がなければ nan。"""
    ai = tube_inner_a(A, Y, jt, i, y)
    return ai - ab if np.isfinite(ai) else np.nan


def back_target_lsq(c, A, Y, g):
    """方式 lsq（3 回目）：高さごとに、背の等高線 d(c) を、それに最も近い上に凸な曲線（重み付き最小二乗）へ置き換える。
    出っ張った縦の肋は引っ込み、入り江（溝）は埋まり、量はほぼ保たれる。奥の端は管との壁（wall_min_m）より前へは引かない。
    その上に、c_m で最大の小さな丸み round_m·φ を足し、c 方向にならす（行ごとの細い縦の襞も消える）。"""
    H, jt, at = BC.crest(A, Y)
    ys = np.arange(g["y_min"], H.max() - 0.05, g["level_step"])
    nv = len(c)
    DL = np.zeros((nv, len(ys)))
    M = np.zeros((nv, len(ys)))
    lev = []
    from scipy.ndimage import gaussian_filter1d as gf
    for k, y in enumerate(ys):
        ab = BC.back_level_a(A, Y, jt, y)
        ok = np.isfinite(ab) & (H > y + 0.02)
        im = int(np.argmin(np.abs(c - g["c_m"])))
        if not ok[im]:
            continue
        i0 = im
        while i0 - 1 >= 0 and ok[i0 - 1]:
            i0 -= 1
        i1 = im
        while i1 + 1 < nv and ok[i1 + 1]:
            i1 += 1
        idx = np.arange(i0, i1 + 1)
        idx = idx[c[idx] >= g["window_c0"]]
        if len(idx) < 8:
            continue
        cc = c[idx]; dd = -ab[idx]
        lo, hi = cc[0], cc[-1]
        fl = np.array([tube_inner_a(A, Y, jt, int(i), y) for i in idx])
        floor = np.where(np.isfinite(fl), -fl + g["wall_min_m"], -np.inf)
        floor = np.minimum(floor, dd)
        wts = np.gradient(cc)                          # 1 m あたりの重みをそろえる
        if g.get("bounded"):
            # 上限：この高さの今の最も後ろ（側面の影の幅を広げない）。本体の行（評価基準 F03 の行に余白）では壁を [shell_min, wall_max]·H(c) に保つ
            dmax_level = float(np.nanmax(-ab))
            ub = np.full(len(cc), dmax_level)
            lb = floor.copy()
            wall = -ab[idx] - (-fl)                    # = fl − ab（背から内側の面まで、水平）
            wall = fl - ab[idx]
            Hc = H[idx]
            bwin = g.get("body_c", [-6.0, 5.0])
            body = (Hc >= 0.70 * BC.H0) & (cc >= bwin[0]) & (cc <= bwin[1]) & np.isfinite(wall)
            ub = np.where(body, np.minimum(ub, dd + np.maximum(g["wall_max_H"] * Hc - wall, 0.0)), ub)
            lb = np.where(body, np.maximum(lb, dd - np.maximum(wall - g["shell_min_H"] * Hc, 0.0)), lb)
            ub = np.maximum(ub, dd) if g.get("never_below_now_ub", True) else ub
            fit = concave_lsq_bounded(cc, dd, wts, lb, ub)
        else:
            fit = concave_lsq(cc, dd, wts, floor=floor)
            lb = floor; ub = np.full(len(cc), np.inf)
        cm = min(max(g["c_m"], lo + 0.5), hi - 0.5)
        u = np.where(cc < cm, (cc - cm) / (cm - lo), (cc - cm) / (hi - cm))
        phi = (1.0 - np.clip(u * u, 0, 1)) ** g["p"]
        tgt = fit + g["round_m"] * phi
        xs = np.arange(lo, hi + 1e-9, 0.1)
        ts = gf(np.interp(xs, cc, tgt), g["target_sigma_c_m"] / 0.1, mode="nearest")
        tgt = np.clip(np.interp(cc, xs, ts), lb, ub)
        dl = tgt - dd
        if c[i0] < g["window_c0"]:
            dl *= R.ss((cc - g["window_c0"]) / g["edge_fade_m"])
        # 等高線の両端（頂の下で輪が閉じる所）へ向けてなめらかに 0 へ（足元の段・針を作らない）
        et = g.get("end_taper_m", 0.0)
        if et > 0:
            dl *= R.ss((cc - lo) / et) * R.ss((hi - cc) / et)
        dl = np.clip(dl, -g["pull_max_m"], g["push_max_m"])
        DL[idx, k] = dl
        M[idx, k] = 1.0
        lev.append({"y": round(float(y), 2), "c_lo": round(float(lo), 2), "c_hi": round(float(hi), 2),
                    "push_max": round(float(dl.max()), 3), "pull_max": round(float(-dl.min()), 3),
                    "area_change_m2": round(float(np.trapezoid(dl, cc)), 3)})
    sy = g["sigma_y_m"] / g["level_step"]
    num = gaussian_filter1d(R.csmooth(c, DL * M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else DL * M, sy, axis=1, mode="nearest")
    den = gaussian_filter1d(R.csmooth(c, M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else M, sy, axis=1, mode="nearest")
    DLs = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    DLs *= R.ss(den / 0.5)
    return ys, DLs, lev


def back_target_fill(c, A, Y, g):
    """方式 fill（5 回目）：高さごとに、背の等高線 d(c) の入り江（溝）だけを、上に凸な包絡まで後ろへ出して埋める（引っ込めない）。
    ・縦の肋（c ≈ −4）は引っ込めない（評価基準 F03 の殻の下限 0.20H に当たるため。管が原画に見えていて動かせない）。
    ・奥の端（c ≳ 9）は管との壁が薄く引っ込められないので、包絡の端として残る。
    ・奥の端の低い裾（skirt：c ≥ skirt_c0、y < skirt_t·H(c)）だけは、壁が厚いので前へ引き、奥の体積の増えを打ち消す。
    ・どの高さでも、今の最も後ろ（側面の影の幅、評価基準 F04）より後ろへは出さない。
    ・目標は c 方向にならし（σ target_sigma_c_m）、等高線の両端へ end_taper_m で 0 へ戻す。"""
    H, jt, at = BC.crest(A, Y)
    ys = np.arange(g["y_min"], H.max() - 0.05, g["level_step"])
    nv = len(c)
    DL = np.zeros((nv, len(ys)))
    M = np.zeros((nv, len(ys)))
    lev = []
    from scipy.ndimage import gaussian_filter1d as gf
    sk = g.get("skirt")
    for k, y in enumerate(ys):
        ab = BC.back_level_a(A, Y, jt, y)
        ok = np.isfinite(ab) & (H > y + 0.02)
        im = int(np.argmin(np.abs(c - g["c_m"])))
        if not ok[im]:
            continue
        i0 = im
        while i0 - 1 >= 0 and ok[i0 - 1]:
            i0 -= 1
        i1 = im
        while i1 + 1 < nv and ok[i1 + 1]:
            i1 += 1
        idx = np.arange(i0, i1 + 1)
        idx = idx[c[idx] >= g["window_c0"]]
        if len(idx) < 8:
            continue
        cc = c[idx]; dd = -ab[idx]
        lo, hi = cc[0], cc[-1]
        fl = np.array([tube_inner_a(A, Y, jt, int(i), y) for i in idx])
        floor = np.where(np.isfinite(fl), -fl + g["wall_min_m"], -np.inf)
        floor = np.minimum(floor, dd)
        dmax_level = float(np.nanmax(-ab))
        d1 = dd.copy()
        if sk:
            t = y / np.maximum(H[idx], 1e-6)
            wsk = R.ss((cc - sk["c0"]) / sk["ramp_m"]) * np.clip(1.0 - t / sk["t_max"], 0, 1) ** 2
            fls = np.where(np.isfinite(fl), -fl + sk["wall_min_m"], -np.inf)
            d1 = np.maximum(dd - sk["pull_m"] * wsk, np.minimum(fls, dd))
        env = d1 + BC.concave_hull_gap(cc, d1)
        cm = min(max(g["c_m"], lo + 0.5), hi - 0.5)
        u = np.where(cc < cm, (cc - cm) / (cm - lo), (cc - cm) / (hi - cm))
        phi = (1.0 - np.clip(u * u, 0, 1)) ** g["p"]
        tgt = env + g["round_m"] * phi
        xs = np.arange(lo, hi + 1e-9, 0.1)
        ts = gf(np.interp(xs, cc, tgt), g["target_sigma_c_m"] / 0.1, mode="nearest")
        tgt = np.interp(cc, xs, ts)
        tgt = np.minimum(tgt, np.maximum(dmax_level, dd))
        tgt = np.maximum(tgt, np.minimum(floor, d1))
        dl = tgt - dd
        if c[i0] < g["window_c0"]:
            dl *= R.ss((cc - g["window_c0"]) / g["edge_fade_m"])
        et = g.get("end_taper_m", 0.0)
        if et > 0:
            dl *= R.ss((cc - lo) / et) * R.ss((hi - cc) / et)
        dl = np.clip(dl, -g["pull_max_m"], g["push_max_m"])
        DL[idx, k] = dl
        M[idx, k] = 1.0
        lev.append({"y": round(float(y), 2), "c_lo": round(float(lo), 2), "c_hi": round(float(hi), 2),
                    "push_max": round(float(dl.max()), 3), "pull_max": round(float(-dl.min()), 3),
                    "area_change_m2": round(float(np.trapezoid(dl, cc)), 3),
                    "area_change_c_gt_0_m2": round(float(np.trapezoid(np.where(cc > 0, dl, 0.0), cc)), 3)})
    sy = g["sigma_y_m"] / g["level_step"]
    num = gaussian_filter1d(R.csmooth(c, DL * M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else DL * M, sy, axis=1, mode="nearest")
    den = gaussian_filter1d(R.csmooth(c, M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else M, sy, axis=1, mode="nearest")
    DLs = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    DLs *= R.ss(den / 0.5)
    return ys, DLs, lev


def back_target_fill2(c, A, Y, g):
    """方式 fill2（6 回目）：高さごとの背の等高線 d(c) を、
      1. c 方向に σ smooth_c_m でならす（行ごとの細い縦の襞と、肩との境の折れ目をやわらげる。等高線の両端と、
         窓の −c 端の手前は元の値へ戻す）、
      2. c ≥ fill_c0（縦の肋のあたり）から奥の端までで、入り江（溝）を上に凸な包絡まで λ だけ後ろへ出して埋める（引っ込めない）、
      3. 奥の端の低い裾（skirt）は管との壁が厚いので前へ引き、奥の体積の増えを減らす、
    の順で目標にする。どの高さでも今の最も後ろより後ろへは出さない（側面の影の幅）。"""
    H, jt, at = BC.crest(A, Y)
    ys = np.arange(g["y_min"], H.max() - 0.05, g["level_step"])
    nv = len(c)
    DL = np.zeros((nv, len(ys)))
    M = np.zeros((nv, len(ys)))
    lev = []
    from scipy.ndimage import gaussian_filter1d as gf
    sk = g.get("skirt")
    lam = float(g.get("fill_frac", 1.0))
    for k, y in enumerate(ys):
        ab = BC.back_level_a(A, Y, jt, y)
        ok = np.isfinite(ab) & (H > y + 0.02)
        im = int(np.argmin(np.abs(c - g["c_m"])))
        if not ok[im]:
            continue
        i0 = im
        while i0 - 1 >= 0 and ok[i0 - 1]:
            i0 -= 1
        i1 = im
        while i1 + 1 < nv and ok[i1 + 1]:
            i1 += 1
        idx = np.arange(i0, i1 + 1)
        idx = idx[c[idx] >= g["window_c0"]]
        if len(idx) < 8:
            continue
        cc = c[idx]; dd = -ab[idx]
        lo, hi = cc[0], cc[-1]
        fl = np.array([tube_inner_a(A, Y, jt, int(i), y) for i in idx])
        floor = np.where(np.isfinite(fl), -fl + g["wall_min_m"], -np.inf)
        dmax_level = float(np.nanmax(-ab))
        # 1. ならす（等間隔へ置き直して）
        xs = np.arange(lo, hi + 1e-9, 0.1)
        dx = np.interp(xs, cc, dd)
        ds = np.interp(cc, xs, gf(dx, g["smooth_c_m"] / 0.1, mode="nearest"))
        wend = R.ss((cc - lo) / g["smooth_end_m"]) * R.ss((hi - cc) / g["smooth_end_m"])
        if c[i0] < g["window_c0"]:
            wend = wend * R.ss((cc - g["window_c0"]) / g["edge_fade_m"])
        d1 = dd + wend * (ds - dd)
        # 3. 奥の裾
        for skk in ("skirt", "skirt2"):                 # 裾の引き（埋める前。埋める段が入り江を作らないように直す）
            sk = g.get(skk)
            if not sk:
                continue
            t = y / np.maximum(H[idx], 1e-6)
            wsk = R.ss((cc - sk["c0"]) / sk["ramp_m"]) * np.clip(1.0 - t / sk["t_max"], 0, 1) ** 2
            fls = np.where(np.isfinite(fl), -fl + sk["wall_min_m"], -np.inf)
            d1 = np.maximum(d1 - sk["pull_m"] * wsk, np.minimum(fls, d1))
        # 2. 入り江を埋める（fill_c0 から奥の端まで）
        sel = cc >= g["fill_c0"]
        fill = np.zeros(len(cc))
        if sel.sum() >= 4:
            fill[sel] = BC.concave_hull_gap(cc[sel], d1[sel])
            if g.get("fill_smooth_mode", "fill") == "target":
                # 包絡そのもの（上に凸）をならす：ならしても上に凸のまま、入り江の底が残らない
                ex = np.interp(xs, cc, d1 + fill)
                es = np.interp(cc, xs, gf(ex, g["fill_sigma_c_m"] / 0.1, mode="nearest"))
                wf = R.ss((cc - g["fill_c0"]) / 2.0)
                fill = np.maximum(wf * (es - d1), 0.0) * (fill > 0) + np.maximum(wf * (es - d1), 0.0) * (fill <= 0) * 0.0 + fill * (1 - wf)
                fill = np.maximum(fill, 0.0)
            else:
                fx = np.interp(xs, cc, fill)
                fill = np.interp(cc, xs, gf(fx, g["fill_sigma_c_m"] / 0.1, mode="nearest"))
        # 丸みの中心：round_c（美術の見本02 の修正の回 1、as02_fix01_back_round。無ければ今までどおり c_m）
        cm = min(max(g.get("round_c", g["c_m"]), lo + 0.5), hi - 0.5)
        u = np.where(cc < cm, (cc - cm) / (cm - lo), (cc - cm) / (hi - cm))
        phi = (1.0 - np.clip(u * u, 0, 1)) ** g["p"]
        rf = g.get("round_f_max")                       # 丸みは高さ round_f_max·H0 より下だけ（頂の弧 Q17 に触れない）
        rw = (1.0 - R.ss((y - (rf - 0.1) * BC.H0) / (0.1 * BC.H0))) if rf else 1.0
        rfm = g.get("round_fade_mode")
        if rf and rfm == "cos":
            # 美術の見本02 の修正の回 1（as02_fix01_back_round）：丸みを高さ 0 から round_f_max·H0 まで余弦でなめらかに 0 へ
            # （0.1 H0 の幅で急に消すと背の断面に S 字ができる）
            rw = 0.5 * (1.0 + np.cos(np.pi * min(y / (rf * BC.H0), 1.0)))
        elif rf and rfm == "lin":
            rw = max(1.0 - y / (rf * BC.H0), 0.0)
        tgt = d1 + lam * fill + g["round_m"] * rw * phi * R.ss((cc - g["fill_c0"]) / 3.0)
        dl = tgt - dd
        et = g.get("end_taper_m", 0.0)
        if et > 0:                                     # 埋める分だけ、等高線の両端へ 0 に戻す（裾の引きは戻さない）
            dl *= R.ss((cc - lo) / et) * R.ss((hi - cc) / et)
        tgt = dd + dl
        ska = g.get("skirt_after")
        if ska:                                        # 埋めた後で低い裾を前へ引く（c 方向にゆっくり増える重みで、溝を作らない）
            t = y / np.maximum(H[idx], 1e-6)
            pw = ska.get("power", 2.0)
            q = np.clip(1.0 - t / ska["t_max"], 0, 1)
            wsk = R.ss((cc - ska["c0"]) / ska["ramp_m"]) * (R.ss(q) if pw == "ss" else q ** pw)
            fls = np.where(np.isfinite(fl), -fl + ska["wall_min_m"], -np.inf)
            tgt = np.maximum(tgt - ska["pull_m"] * wsk, np.minimum(fls, tgt))
        tgt = np.minimum(tgt, np.maximum(dmax_level, dd))
        tgt = np.maximum(tgt, np.minimum(floor, dd))
        dl = tgt - dd
        dl = np.clip(dl, -g["pull_max_m"], g["push_max_m"])
        DL[idx, k] = dl
        M[idx, k] = 1.0
        lev.append({"y": round(float(y), 2), "c_lo": round(float(lo), 2), "c_hi": round(float(hi), 2),
                    "push_max": round(float(dl.max()), 3), "pull_max": round(float(-dl.min()), 3),
                    "area_change_m2": round(float(np.trapezoid(dl, cc)), 3),
                    "area_change_c_gt_0_m2": round(float(np.trapezoid(np.where(cc > 0, dl, 0.0), cc)), 3)})
    sy = g["sigma_y_m"] / g["level_step"]
    num = gaussian_filter1d(R.csmooth(c, DL * M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else DL * M, sy, axis=1, mode="nearest")
    den = gaussian_filter1d(R.csmooth(c, M, g["sigma_c_m"]) if g["sigma_c_m"] > 0 else M, sy, axis=1, mode="nearest")
    DLs = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    DLs *= R.ss(den / 0.5)
    return ys, DLs, lev


def back_target(c, A, Y, g):
    """高さごとの dl(c, y)（正 ＝ 後ろへ出す、m）を (nv, nlev) で返す。"""
    if g.get("mode") == "hull":
        return back_target_hull(c, A, Y, g)
    if g.get("mode") == "lsq":
        return back_target_lsq(c, A, Y, g)
    if g.get("mode") == "fill":
        return back_target_fill(c, A, Y, g)
    if g.get("mode") == "fill2":
        return back_target_fill2(c, A, Y, g)
    H, jt, at = BC.crest(A, Y)
    ys = np.arange(g["y_min"], H.max() - 0.05, g["level_step"])
    nv = len(c)
    DL = np.zeros((nv, len(ys)))
    M = np.zeros((nv, len(ys)))
    lev = []
    for k, y in enumerate(ys):
        ab = BC.back_level_a(A, Y, jt, y)
        ok = np.isfinite(ab) & (H > y + 0.02)
        # c_m を含む連続した行の区間
        im = int(np.argmin(np.abs(c - g["c_m"])))
        if not ok[im]:
            continue
        i0 = im
        while i0 - 1 >= 0 and ok[i0 - 1]:
            i0 -= 1
        i1 = im
        while i1 + 1 < nv and ok[i1 + 1]:
            i1 += 1
        idx = np.arange(i0, i1 + 1)
        idx = idx[c[idx] >= g["window_c0"]]
        if len(idx) < 8:
            continue
        cc = c[idx]; dd = -ab[idx]
        lo, hi = cc[0], cc[-1]
        cm = min(max(g["c_m"], lo + 0.5), hi - 0.5)
        chord = dd[0] + (dd[-1] - dd[0]) * (cc - lo) / (hi - lo)
        gg = dd - chord
        u = np.where(cc < cm, (cc - cm) / (cm - lo), (cc - cm) / (hi - cm))
        phi = (1.0 - np.clip(u * u, 0, 1)) ** g["p"]
        G = g["gain"] * np.trapezoid(gg, cc) / np.trapezoid(phi, cc)
        dl = G * phi - gg
        # 窓の −c 端（window_c0 で切った時）はなめらかに 0 へ
        if c[i0] < g["window_c0"]:
            dl *= R.ss((cc - g["window_c0"]) / g["edge_fade_m"])
        dl = np.clip(dl, -g["pull_max_m"], g["push_max_m"])
        DL[idx, k] = dl
        M[idx, k] = 1.0
        lev.append({"y": round(float(y), 2), "c_lo": round(float(lo), 2), "c_hi": round(float(hi), 2), "G": round(float(G), 3),
                    "push_max": round(float(dl.max()), 3), "pull_max": round(float(-dl.min()), 3)})
    # (c, y) でならす（正規化した畳み込み。値のない所は 0 として重みを持たない）
    sy = g["sigma_y_m"] / g["level_step"]
    num = gaussian_filter1d(R.csmooth(c, DL * M, g["sigma_c_m"]), sy, axis=1, mode="nearest")
    den = gaussian_filter1d(R.csmooth(c, M, g["sigma_c_m"]), sy, axis=1, mode="nearest")
    DLs = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    # 値のあった所の外へは滑らかに消す（den の大きさで）
    DLs *= R.ss(den / 0.5)
    return ys, DLs, lev


class BackBuild(SB.Build):
    def __init__(self, design=None, base=None):
        super().__init__(design, base)
        # 原画視点で見えている四角形を 2 倍の解像度（ss=2）でも求めて合わせる（1 倍では漏れる縁の 1 画素未満の四角形も止める）
        if self.d.get("vis_ss2", True):
            cache = os.path.join(BC.OUT, "cache", "vis_quads_base_ss2.npy")
            if os.path.isfile(cache):
                q2 = np.load(cache)
            else:
                zb, ids = SB.RC.zbuf(self.c, self.A0, self.Y0, 2)
                iv, iu = SB.RC.tri_quad(ids)
                q2 = np.zeros_like(self.visq)
                ok = iv >= 0
                q2[iv[ok], iu[ok]] = True
                os.makedirs(os.path.dirname(cache), exist_ok=True)
                np.save(cache, q2)
            q = self.visq | q2
            v = np.zeros(self.A0.shape, bool)
            v[:, :-1] |= q; v[:, 1:] |= q
            v[1:] |= v[:-1].copy(); v[:-1] |= v[1:].copy()
            self.visq, self.visv = q, v
        pc = int(self.d.get("pin_dilate_cols", 0))
        if pc > 0:
            v = self.visv.copy()
            for k in range(1, pc + 1):
                v[:, :-k] |= self.visv[:, k:]          # 見えている頂点から背の側（列の小さい側）へ pc 列
            pr = int(self.d.get("pin_dilate_rows", 0))
            for k in range(1, pr + 1):
                v[k:] |= v[:-k].copy(); v[:-k] |= v[k:].copy()
            self.visv = v

    def desired(self):
        d = self.d
        g = d["back"]
        js = int(d["sea_cols"])
        A0, c = self.A0, self.c
        Ybase = self.Y0
        # 段 A：原画が止めない行（c ≈ +1〜+9.6）で、頂の高さ H(c) を原画の頂（c −0.8）から奥の端の止まる所（c 9.6）へ
        # なだらかに下がる上に凸な曲線まで下げる（中ほどがいちばん高く、+c 側へ徐々に下がる。要求書 S4）。
        # 見えている唇より上（y > y_keep）の見えない頂点だけを、y_keep で傾き 0 のなめらかな重みで下げる。
        dYA = np.zeros_like(Ybase)
        cl = d.get("crest_lower")
        self.crest_lower_info = None
        if cl:
            H0r, jt0, _ = BC.crest(A0, Ybase)
            ia = int(np.argmin(np.abs(c - cl["c_a"]))); ib = int(np.argmin(np.abs(c - cl["c_b"])))
            Ha, Hb = H0r[ia], H0r[ib]
            u = np.clip((c - c[ia]) / (c[ib] - c[ia]), 0, 1)
            Ht = Ha - (Ha - Hb) * u ** cl["q"]
            wc = R.ss((c - cl["w_c0"]) / cl["w_ramp"]) * R.ss((cl["w_end"] - c) / cl["w_end_ramp"])
            drop = np.clip(H0r - Ht, 0, cl["drop_max"]) * wc
            drop = R.csmooth(c, drop, cl.get("sigma_c_m", 0.6))
            info = []
            for i in range(self.nv):
                if drop[i] <= 1e-4:
                    continue
                vy = Ybase[i][self.visv[i]]
                vis_max = float(vy.max()) if len(vy) else 0.0
                y_keep = vis_max + cl["keep_margin"]
                span = H0r[i] - y_keep
                dmax = span / 1.6
                dd_ = min(drop[i], max(dmax, 0.0))
                if dd_ <= 1e-4:
                    continue
                jj = np.arange(int(d["sea_cols"]), min(int(cl.get("col_max", 200)), self.nu))
                wy = R.ss((Ybase[i, jj] - y_keep) / span)
                dYA[i, jj] = -dd_ * wy
                info.append({"c": round(float(c[i]), 2), "H": round(float(H0r[i]), 3), "drop_m": round(float(dd_), 3), "y_keep": round(y_keep, 2)})
            dYA[self.visv] = 0.0
            self.crest_lower_info = info
        Y0 = Ybase + dYA
        ys, DL, lev = back_target(c, A0, Y0, g)
        self.levels = lev
        self.DL = DL
        self.ys = ys
        H, jt, at = BC.crest(A0, Y0)
        dA = np.zeros_like(A0); dY = dYA.copy()
        for i in range(self.nv):
            if not np.any(DL[i] != 0):
                continue
            j1 = int(jt[i])
            jj = np.arange(js, j1 + 1)
            s = R.arclen(A0[i], Y0[i])
            hidden_top = (not self.visv[i, j1]) and ("top_m_hidden" in g)
            w = R.ss((s[j1] - s[jj]) / (g["top_m_hidden"] if hidden_top else g["top_m"]))
            tdy = float(g.get("top_dy_hidden_m", 0.0) if hidden_top else g.get("top_dy_m", 0.0))
            if tdy > 0:                                 # 頂の下 tdy の高さで 0 へ（頂のまわりの水平に近い面を横へずらして折らない）
                w = w * R.ss((H[i] - Y0[i, jj]) / tdy)
            dl = np.interp(Y0[i, jj], ys, DL[i], left=DL[i, 0], right=0.0)
            dA[i, jj] = -dl * w
        sdj = float(d.get("desired_sigma_cols", 0.0))
        if sdj > 0:
            dA[:, js:] = gaussian_filter1d(dA[:, js:], sdj, axis=1, mode="nearest")
            for i in range(self.nv):
                dA[i, int(jt[i]) + 1:] = 0.0
        dA[:, :js] = 0.0
        # 側面の影の幅（評価基準 F04）を広げない：どの高さでも、土台の背の最も後ろ（全部の行）より後ろへは出さない
        if g.get("cap_side_shadow", True):
            yl = np.arange(0.05, H.max(), 0.1)
            Hb_, jtb_, _ = BC.crest(A0, Ybase)
            amin = np.array([np.nanmin(BC.back_level_a(A0, Ybase, jtb_, yv)) if np.isfinite(BC.back_level_a(A0, Ybase, jtb_, yv)).any() else np.nan
                             for yv in yl])
            fin = np.isfinite(amin)
            for i in range(self.nv):
                jj = np.arange(js, int(jt[i]) + 1)
                lim = np.interp(Y0[i, jj], yl[fin], amin[fin]) + float(g.get("cap_margin_m", 0.1)) - A0[i, jj]
                dA[i, jj] = np.maximum(dA[i, jj], np.minimum(lim, 0.0))
        # 止めた頂点（原画視点で見える所とその近く）へ向けて、列の方向に pin_fade_cols 列かけてなめらかに 0 へ（頂の近くの折れを作らない）
        pf = int(d.get("pin_fade_cols", 0))
        if pf > 0:
            dist = np.full(self.visv.shape, 1e9)
            for i in range(self.nv):
                pj = np.nonzero(self.visv[i])[0]
                if len(pj):
                    jj = np.arange(self.nu)
                    dist[i] = np.min(np.abs(jj[:, None] - pj[None, :]), 1)
            wpin = R.ss(dist / float(pf))
            wpin = R.csmooth(self.c, wpin, 0.4)
            dA *= wpin; dY *= wpin
        dA[self.visv] = 0.0; dY[self.visv] = 0.0
        dA[0] = dA[-1] = 0.0
        info = {"levels": len(lev), "dA_min": round(float(dA.min()), 3), "dA_max": round(float(dA.max()), 3)}
        return dA, dY, info


def main():
    pre = sys.argv[1]
    design = json.loads(json.dumps(BACK_DEFAULT))
    if len(sys.argv) > 2:
        user = json.load(open(sys.argv[2], encoding="utf-8"))
        if "back" in user:
            design["back"].update(user.pop("back"))
        design.update(user)
    t0 = time.time()
    b = BackBuild(design)
    A, Y = b.run()
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    prov = {"route": "美術の見本02 BACK Tools/GWWaveGen/as02/back_build.py（r01_shoulder_build.Build の制約を使う）",
            "base": "K*′ P28R2rec (Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_rows.npz, sha256 %s)" % BC.BASE_SHA["rows"],
            "design": b.d, "reference_model_read_by_generator": False}
    KC.write_candidate(pre, b.c, A, Y, prov)
    mv = np.hypot(A - b.A0, Y - b.Y0)
    rep = {"design": b.d, "log": b.log, "levels": b.levels, "crest_lower": getattr(b, "crest_lower_info", None),
           "moved_vertices_gt_1cm": int((mv > 0.01).sum()), "max_move_m": round(float(mv.max()), 3),
           "visible_vertices_moved": int((mv[b.visv] > 1e-9).sum()), "seconds": round(time.time() - t0, 1)}
    BC.jdump(rep, pre + "_build_report.json")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("levels", "design")}, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
