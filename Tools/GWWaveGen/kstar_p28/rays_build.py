# -*- coding: utf-8 -*-
"""仕上げ28 第1回（射線の案 RAYS）：左の輪郭 78・130・131 を作る稜を原画カメラの射線の上で配り直し、
稜の背骨（各行の頂の点の列 (a_s(c), H_s(c))）を 1 本のなめらかな単調な空間曲線として解き、
体の断面をその背骨から作り直す（py -3.10、numpy と scipy だけ。参照モデルは読まない：F13-1）。

作り方（R4 の格子 400×240・目印の列・UV・行の c は変えない）
  1. 断面の正規化：R4 の各行の断面を頂の列 j_top=90 の点で正規化する
       An = (A − a_top)/H、Yn = Y/H（H = Y[:, 90]、a_top = A[:, 90]）
     行の方向（c）にガウス σ_c でならす（縦の襞と行ごとのこぶを消す。後ろから見た「布をかぶせた」見え方の元）。
  2. 背骨：a_s(c) は設計の変数（c の節の値を 3 次でつなぐ）。H_s(c) は、原画の外輪郭（78・130・131）の射線に
     頂の近くの稜が接するように解く（上側の包絡の像の差を、行ごとの高さの修正へ戻す反復）。
     輪郭を作らない行（左の尾・b区域より左）は、単調でなめらかな上り坂で埋める（ドームの前の棚とくぼみを作らない）。
  3. 置き直し：A = a_s + H_s·An、Y = H_s·Yn。平らな海の列（0..18、394..399）は、R4 の格子の端と新しい
     接する点の間に等分して置く（格子の外周は R4 のまま）。c ∈ [C_R0, C_R1] の外は R4 へなめらかに戻す
     （132・72 を作る行 c ≥ −2.4 と、左の尾 c ≤ −36 は R4 のまま）。
  4. 目的（背骨の選び方）：後ろ 65° の視点に写した背骨の曲がり、上から見た背骨の曲がり、3 次元の曲がり、
     H_s の単調さ（くぼみ）、ドームの測り（評審の R6 の局所 2 次の残差の速い近似）、輪郭の残差。
usage:
  py -3.10 rays_build.py build <out_prefix> [design.json]   設計の json（a_s の節、σ_c など）で候補を作る
  py -3.10 rays_build.py search <out_dir>                     a_s の節を探す（Nelder–Mead）→ best_design.json
"""
import os
import sys
import json
import time
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rays_common as RC  # noqa: E402
KC = RC.KC

J_TOP = 90
C_R0, C_R1 = -34.0, -2.4          # 作り直す行の範囲（外は R4）
BLEND_L = (-40.0, -34.0)           # 左の戻し（R4 → 作り直し）
BLEND_R = (-4.0, -2.4)             # 右の戻し（作り直し → R4）
OUTLINE_IDS = ("78", "130", "131")
X_FIT = (150, 766)                 # 上側の包絡を合わせる x の範囲（表示 px）

DEFAULT = {
    "a_knots_c": [-34.0, -26.0, -20.0, -16.0, -12.0, -8.0, -4.0, -2.4],
    "a_knots_v": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "sigma_c_m": 2.0,               # 正規化した断面を c 方向にならす σ
    "sigma_c_lip_m": 1.2,           # 唇の先の側（列 150 以上）の σ（b区域の房を残すため小さく）
    "H_monotone_from_c": -34.0,     # この c から背骨の頂まで H_s を単調に上げる
    "H_monotone_to_c": -2.6,
    "H_monotone_weight": 400.0,     # 単調さの罰の重み（px² 相当）
    "H_monotone_min_slope": 0.03,
    "H_fit_smooth": 3000.0,
    "H_knot_step_m": 2.0,
    "fit_iters": 12,
    "fit_gain": 0.7,
    "H_smooth_sigma_m": 0.6,
}


# ---------------------------------------------------------------- truth outline
def truth_outline():
    d = json.load(open(os.path.join(RC.REPO, "Tools", "PaintingTruth", "targets", "main_wave_outline_envelope.json"), encoding="utf-8"))
    seg = {s["id"]: np.array(s["points_display"], float) for s in d["segments"]}
    P = np.vstack([seg["78"], seg["130"][1:], seg["131"][1:]])
    xs = np.arange(int(math.ceil(P[0, 0])), int(math.floor(P[-1, 0])) + 1)
    ys = np.interp(xs, P[:, 0], P[:, 1])
    return xs.astype(float), ys


def rays_through(px):
    """表示 px (n,2) → 原画カメラの射線の単位方向（Unity）。"""
    pos, r, u, f = KC.cam_basis_unity()
    t = math.tan(math.radians(KC.CAM_VFOV) / 2.0); asp = KC.CAM_W / float(KC.CAM_H)
    vx = (px[:, 0] + 0.5) / KC.CAM_W; vy = 1.0 - (px[:, 1] + 0.5) / KC.CAM_H
    D = ((2 * vx - 1) * t * asp)[:, None] * r + ((2 * vy - 1) * t)[:, None] * u + f[None, :]
    return D / np.linalg.norm(D, axis=1, keepdims=True)


# ---------------------------------------------------------------- envelope of a rows grid
def upper_envelope(c, A, Y, x0, x1, rows=None, sub=3):
    """原画視点で x の 1 px ごとの最も上の像の y と、その点の行（小数）と断面座標。rows を限れば速い。"""
    nv, nu = A.shape
    X = RC.world(c, A, Y)
    rr = np.arange(nv) if rows is None else np.asarray(rows)
    rr = rr[(rr >= 0) & (rr < nv - 1)]
    t = np.linspace(0, 1, sub, endpoint=False)
    # 行の方向に sub 倍、列の方向に sub 倍の双線形の点
    Xa = X[rr][:, None, :, :] * (1 - t)[None, :, None, None] + X[rr + 1][:, None, :, :] * t[None, :, None, None]
    Xa = Xa.reshape(-1, nu, 3)
    Xb = Xa[:, :-1, None, :] * (1 - t)[None, None, :, None] + Xa[:, 1:, None, :] * t[None, None, :, None]
    Xb = Xb.reshape(-1, 3)
    rowf = (rr[:, None] + t[None, :]).reshape(-1)
    rowf = np.repeat(rowf, (nu - 1) * sub)
    q = RC.project(Xb)
    xi = np.round(q[:, 0]).astype(int)
    m = (xi >= x0) & (xi <= x1) & (q[:, 2] > 0)
    xi, yv, rowf, Xb = xi[m], q[m, 1], rowf[m], Xb[m]
    order = np.lexsort((yv, xi))
    xi, yv, rowf, Xb = xi[order], yv[order], rowf[order], Xb[order]
    first = np.r_[True, xi[1:] != xi[:-1]]
    ex = xi[first]; ey = yv[first]; er = rowf[first]; eX = Xb[first]
    out_y = np.full(x1 - x0 + 1, np.nan); out_r = np.full(x1 - x0 + 1, np.nan); out_X = np.full((x1 - x0 + 1, 3), np.nan)
    out_y[ex - x0] = ey; out_r[ex - x0] = er; out_X[ex - x0] = eX
    return out_y, out_r, out_X


# ---------------------------------------------------------------- profile model
class Model:
    def __init__(self, design=None):
        self.d = dict(DEFAULT)
        if design:
            self.d.update(design)
        self.c, self.A0, self.Y0 = RC.load_r4()
        c, A, Y = self.c, self.A0, self.Y0
        self.nv, self.nu = A.shape
        self.H0 = Y[:, J_TOP].copy()
        self.a0 = A[:, J_TOP].copy()
        # 行の重み（作り直し 1 → R4 0）
        w = np.ones(self.nv)
        w[c <= BLEND_L[0]] = 0.0
        m = (c > BLEND_L[0]) & (c < BLEND_L[1]); w[m] = self._ss((c[m] - BLEND_L[0]) / (BLEND_L[1] - BLEND_L[0]))
        w[c >= BLEND_R[1]] = 0.0
        m = (c > BLEND_R[0]) & (c < BLEND_R[1]); w[m] = self._ss((BLEND_R[1] - c[m]) / (BLEND_R[1] - BLEND_R[0]))
        self.w = w
        # 正規化は、頂の点 (a0, H0) を c 方向にならした値 (ã0, H̃0) で行う。R4 の頂の点は行ごとに少し揺れているので、
        # 生の値で正規化して、ならした背骨の上に置き直すと、その揺れが断面全体の拡大・移動の揺れになり、
        # 管の中や前の面に縦の縞が出る（第1回の途中の版で見えた）。ならした値で正規化すれば、背骨が ã0・H̃0 のままの行は R4 に戻る。
        self.a0s = self.smooth_c(self.a0, self.d.get("a_init_sigma_m", 1.0))
        self.H0s = self.smooth_c(self.H0, self.d.get("H_init_sigma_m", 1.0))
        Hs = np.maximum(self.H0s, 0.05)
        self.An = (A - self.a0s[:, None]) / Hs[:, None]
        self.Yn = Y / Hs[:, None]
        self.band = np.nonzero((c >= BLEND_L[0]) & (c <= BLEND_R[1]))[0]
        self.xs, self.ys = truth_outline()
        self._smooth_profiles()

    @staticmethod
    def _ss(t):
        t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)

    def _smooth_profiles(self):
        """正規化した断面を c 方向にならす。列ごとに σ を変える（唇の先の側は小さく）。"""
        c = self.c
        sig_col = np.full(self.nu, self.d["sigma_c_m"])
        jl = np.arange(self.nu)
        t = self._ss((jl - 130) / 40.0)
        sig_col = self.d["sigma_c_m"] * (1 - t) + self.d["sigma_c_lip_m"] * t
        # ならすのは背と頂（列 ≤ smooth_cols[0]）だけ。唇（b区域の稜と爪の縁、72・132）は R4 の正規化した形のまま
        sc0, sc1 = self.d.get("smooth_cols", [96, 112])
        self._wsm = 1.0 - self._ss((jl - sc0) / float(sc1 - sc0))
        rows = self.band
        An, Yn = self.An.copy(), self.Yn.copy()
        cr = c[rows]
        # ならす元にする行（作り直す範囲と、その外 6 m まで。R4 の形の続き）
        src = np.nonzero((c >= BLEND_L[0] - 6) & (c <= BLEND_R[1] + 3))[0]
        cs = c[src]
        for k, s in enumerate(np.unique(np.round(sig_col, 3))):
            cols = np.nonzero(np.abs(sig_col - s) < 1e-3)[0]
            W = np.exp(-0.5 * ((cr[:, None] - cs[None, :]) / max(s, 1e-3)) ** 2)
            # 行の間隔が不均一なので、間隔で重みを掛ける（連続の積分に近づける）
            dc = np.gradient(cs)
            W = W * dc[None, :]
            W /= W.sum(1, keepdims=True)
            An[np.ix_(rows, cols)] = W @ self.An[np.ix_(src, cols)]
            Yn[np.ix_(rows, cols)] = W @ self.Yn[np.ix_(src, cols)]
        An = self._wsm[None, :] * An + (1 - self._wsm[None, :]) * self.An
        Yn = self._wsm[None, :] * Yn + (1 - self._wsm[None, :]) * self.Yn
        # 72・132 を作る唇（c > −9 の行の列 130 以上）は、ならさずに R4 の正規化した形へ戻す（仕上げ28 の関門 72 を守る）
        lc0, lc1 = self.d.get("lip_keep_c", [-10.0, -8.0])
        wc = np.clip((c - lc0) / (lc1 - lc0), 0, 1); wc = wc * wc * (3 - 2 * wc)
        wj = np.clip((np.arange(self.nu) - 120) / 20.0, 0, 1); wj = wj * wj * (3 - 2 * wj)
        Wk = wc[:, None] * wj[None, :]
        An = Wk * self.An + (1 - Wk) * An
        Yn = Wk * self.Yn + (1 - Wk) * Yn
        # 頂の列を (0, 1) に固定はしない：正規化は c 方向にならした頂 (ã0, H̃0) で行っているので、R4 の頂の点の揺れは
        # 正規化した値に残る。そこだけ (0, 1) に置くと、列 90 の点だけが隣の列から離れて頂に折れ目ができる（F02 の折れ 21〜66°）。
        self.Ans, self.Yns = An, Yn

    def a_spine(self):
        from scipy.interpolate import PchipInterpolator
        kc = np.array(self.d["a_knots_c"], float); kv = np.array(self.d["a_knots_v"], float)
        f = PchipInterpolator(kc, kv, extrapolate=True)
        a = self.a0s.copy()
        m = (self.c >= kc[0]) & (self.c <= kc[-1])
        a[m] = a[m] + f(self.c[m]) * self.w[m]     # R4 の頂の a（ならした値）からのずれとして与える
        return a

    def place(self, a_s, H_s):
        c = self.c
        A = self.A0.copy(); Y = self.Y0.copy()
        rows = self.band
        An, Yn = self.Ans[rows], self.Yns[rows]
        Anew = a_s[rows, None] + H_s[rows, None] * An
        Ynew = H_s[rows, None] * Yn
        # 平らな海の列：格子の端（R4）と新しい接点の間を等分
        for j0, j1 in ((0, 18), (394, self.nu - 1)):
            if j0 == 0:
                a_end, a_in = self.A0[rows, 0], Anew[:, 18]
                t = np.linspace(0, 1, 19)
                Anew[:, 0:19] = a_end[:, None] + (a_in - a_end)[:, None] * t[None, :]
                Ynew[:, 0:19] = Ynew[:, 0:19] * 0 + Ynew[:, 18:19] * (t[None, :] >= 1)
            else:
                a_in, a_end = Anew[:, 394], self.A0[rows, -1]
                t = np.linspace(0, 1, self.nu - 394)
                Anew[:, 394:] = a_in[:, None] + (a_end - a_in)[:, None] * t[None, :]
                Ynew[:, 394:] = Ynew[:, 394:395] * (t[None, :] <= 0)
        w = self.w[rows, None]
        A[rows] = w * Anew + (1 - w) * self.A0[rows]
        Y[rows] = w * Ynew + (1 - w) * self.Y0[rows]
        if self.d.get("far_ridge"):
            A, Y = self.far_ridge(A, Y)
        if self.d.get("far_back_smooth"):
            A, Y = self.far_back_smooth(A, Y)
        if self.d.get("crest_ramp"):
            A, Y = self.crest_ramp(A, Y)
        if self.d.get("crest_sharpen"):
            A, Y = self.crest_sharpen(A, Y)
        if self.d.get("back_ramp", False):
            A, Y = self.back_ramp(A, Y)
        if self.d.get("lip_graft_R3"):
            A, Y = self.lip_graft(A, Y)
        if self.d.get("tail_round"):
            A, Y = self.tail_round(A, Y)
        return A, Y

    def tail_round(self, A, Y):
        """手前の尾の行（c ≤ c_max。頂は原画の画面の外 x < 0 に写る）の頂を弧にする：断面の頂のまわり（弧長 ±win）を
        弧長のガウス σ でならす（頂の ±2 m の弦の角が 67〜106° と尖っていた。仕上げ28 の閉じる目安「手前の尾の行が弧」）。"""
        g = self.d["tail_round"]
        c = self.c
        cmax = g.get("c_max", -24.5); sig = g.get("sigma_m", 1.5); win = g.get("win_m", 3.5); its = int(g.get("iters", 3))
        A = A.copy(); Y = Y.copy()
        for r in np.nonzero(c <= cmax + 1.5)[0]:
            wr = float(np.clip((cmax + 1.5 - c[r]) / 1.5, 0, 1)); wr = wr * wr * (3 - 2 * wr)
            if wr <= 0 or Y[r].max() < 0.5:
                continue
            a, y = A[r].copy(), Y[r].copy()
            for _ in range(its):
                sL = np.r_[0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]
                j = int(np.argmax(y)); s0 = sL[j]
                m = np.abs(sL - s0) <= win + 3 * sig
                idx = np.nonzero(m)[0]
                K = np.exp(-0.5 * ((sL[idx][:, None] - sL[idx][None, :]) / sig) ** 2)
                K /= K.sum(1, keepdims=True)
                a_s, y_s = K @ a[idx], K @ y[idx]
                w = np.exp(-0.5 * ((sL[idx] - s0) / win) ** 2) * wr
                a[idx] = w * a_s + (1 - w) * a[idx]; y[idx] = w * y_s + (1 - w) * y[idx]
            A[r], Y[r] = a, y
        return A, Y

    def lip_graft(self, A, Y):
        """72（唇の下と管の輪郭）を作る奥の行の唇の先（列 140〜270）を、K*′ R3 の同じ行・列の値へ戻す。
        R4 は R3 の唇をならして 72 の σ12 の読みが 3.68 → 6.71 px に悪くなった（設計28修正01 §4.1）。R3 と R4 の差は
        この範囲で最大 0.29 m。行の範囲 g["c"]、列の範囲 g["cols"]（両端 10 列でなめらかに戻す）。"""
        g = self.d["lip_graft_R3"]
        z = np.load(os.path.join(RC.REPO, "Unity", "Build", "Q20H", "final", "_R3", "kstarR3_a45_rows.npz"))
        A3, Y3 = z["A"].astype(float), z["Y"].astype(float)
        c = self.c
        c0, c1 = g.get("c", [-1.0, 15.0])
        wc = np.clip((c - c0) / 1.0, 0, 1) * np.clip((c1 - c) / 0.5, 0, 1)
        j0, j1 = g.get("cols", [140, 270])
        jj = np.arange(self.nu)
        wj = np.clip((jj - j0) / 10.0, 0, 1) * np.clip((j1 - jj) / 10.0, 0, 1)
        W = (wc[:, None] * wj[None, :])
        W = W * W * (3 - 2 * W)
        # 差分として足す（この候補の行は c > −2.4 で R4 と同じなので、R3 − R4 の差を足すのと同じ）
        return A + W * (A3 - self.A0), Y + W * (Y3 - self.Y0)

    def far_ridge(self, A, Y):
        """奥の側（132 を作る行より奥、c ≥ c0）の頂を、頂の点から奥の端の手前までなだらかにつなぐ稜にする
        （R4 は c +2〜+10 で頂が 19.4 → 15.2 m と丸く下がり、後ろから見ると真ん中の丸いふくらみ（ドーム）の右半分になる）。
        頂の高さ H(c) を目標の稜 R(c)（c0 の高さから c1 まで傾き slope でゆるく下がる）まで上げ、c1 から c2 で R4 へ戻す。
        断面は唇の先の高さより上だけを伸ばす：y' = y + ΔH·((y − y_b)/(H − y_b))²（y > y_b、y_b = 唇の先の高さ − 0.5 m）。
        唇の先と管（72 を作る）と背の下は動かない。原画視点では、この高さの頂は唇の陰で見えない（余裕 3〜8 m、rays_analyze の測り）。"""
        g = self.d["far_ridge"]
        c = self.c
        c0, c1, c2 = g.get("c0", 1.6), g.get("c1", 8.0), g.get("c2", 11.0)
        slope = g.get("slope", -0.08)
        A = A.copy(); Y = Y.copy()
        H = Y[:, :J_TOP + 40].max(1)
        h0 = float(g["h0"]) if "h0" in g else float(np.interp(c0, c, H))
        tgt = h0 + slope * (c - c0)
        w = np.clip((c - c0) / float(g.get("ramp_in_m", 0.8)), 0, 1) * np.clip((c2 - c) / (c2 - c1), 0, 1)
        w = w * w * (3 - 2 * w)
        dHs = np.where(w > 0, (tgt - H) * w, 0.0)
        if g.get("smooth_m"):
            # 目標の高さの上げ幅を c 方向にならす（上げ幅の折れが奥の頂の小さなこぶになるのを防ぐ）
            sg = float(g["smooth_m"]); dcc = np.gradient(c)
            Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sg) ** 2) * dcc[None, :]
            Wm /= Wm.sum(1, keepdims=True)
            dHs = np.where((c > c0 - 0.2) & (c < c2 + 0.5), Wm @ np.maximum(dHs, 0), 0.0)
        for r in np.nonzero(dHs > 0)[0]:
            dH = dHs[r]
            if dH <= 0:
                continue
            yt = Y[r, 200]
            yb = yt - 0.5
            cols = np.arange(18, 216)
            yy = Y[r, cols]
            t = np.clip((yy - yb) / max(H[r] - yb, 0.3), 0, None)
            Y[r, cols] = yy + dH * t ** 2
        return A, Y

    def far_back_smooth(self, A, Y):
        """奥の行（c ≥ −3。原画視点では唇と頂の陰で見えない背）の背（列 18〜88）を、頂（列 90）の点で正規化した形のまま
        c 方向にならす（評審の R6 の「奥の背」のこぶと縦の襞を消す）。頂の点（列 90）と唇（列 ≥ 90）は変えない。"""
        g = self.d["far_back_smooth"]
        c = self.c
        c0, c1 = g.get("c", [-3.0, 14.8]); sig = g.get("sigma_m", 2.0)
        rows = np.nonzero((c >= c0 - 1.0) & (c <= c1))[0]
        at, Ht = A[:, J_TOP], np.maximum(Y[:, J_TOP], 0.3)
        An = (A - at[:, None]) / Ht[:, None]; Yn = Y / Ht[:, None]
        src = np.nonzero((c >= c0 - 6) & (c <= 15.0))[0]
        cs = c[src]; dc = np.gradient(cs)
        W = np.exp(-0.5 * ((c[rows][:, None] - cs[None, :]) / sig) ** 2) * dc[None, :]
        W /= W.sum(1, keepdims=True)
        cols = np.arange(18, J_TOP)
        Ans = W @ An[np.ix_(src, cols)]; Yns = W @ Yn[np.ix_(src, cols)]
        wc = np.clip((c[rows] - c0) / 1.0, 0, 1) * np.clip((c1 - c[rows]) / 0.5, 0, 1)
        wj = np.clip((88 - cols) / 8.0, 0, 1)
        Wm = wc[:, None] * wj[None, :]; Wm = Wm * Wm * (3 - 2 * Wm)
        A = A.copy(); Y = Y.copy()
        A[np.ix_(rows, cols)] = Wm * (at[rows, None] + Ht[rows, None] * Ans) + (1 - Wm) * A[np.ix_(rows, cols)]
        Y[np.ix_(rows, cols)] = Wm * (Ht[rows, None] * Yns) + (1 - Wm) * Y[np.ix_(rows, cols)]
        return A, Y

    def crest_ramp(self, A, Y):
        """背骨を奥（c > −1）でも単調に上げ続ける（後ろから見て 1 本の単調な上り坂 → 奥の端で落ちる）。
        R4 は頂の最高点を c ≈ −0.8 に置き（評価基準 F04 の「最高点 c −1〜+3」）、奥で 20.3 → 15.2 m（c +10）と丸く下げるので、
        原画の射線で決まる左の横の上り（傾き 1 前後）と合わせて、後ろから見ると真ん中の丸い山（ドーム）になる。
        26修正01 の K* は頂が c +5.5 まで上がり続け、後ろから見てドームにならない（ただし頂は直角）。
        原画視点では、奥の頂は唇の頭の陰にあり、空に出るまでの余裕は c 0 で 0.6 m、c +2 で 1.8 m、c +6 で 4.8 m（rays_analyze の測り）。
        上げ幅 ΔH(c) = 目標の坂 − R4 の頂の高さ（負は 0）。目標の坂は c = c_start の R4 の高さから傾き slope で上がり、c_f0〜c_f1 で
        R4 の奥の端へなめらかに戻る。上げ幅は各行で空に出る余裕 − margin で頭打ちにする。
        断面は、列 90 の頂の点を ΔH 上げ、背の側は高さに応じて（背の足は動かさない）、前の側は列 j_end(c) で 0 になるように動かす
        （132 を作る行 c ≤ 1.6 は唇の頭（列 ≥ 101）を動かさないよう j_end = 102、奥の行は唇の先の手前 j_end = 185）。"""
        g = self.d["crest_ramp"]
        c = self.c
        cs, slope = float(g.get("c_start", -1.0)), float(g.get("slope", 0.15))
        cf0, cf1 = float(g.get("c_f0", 7.5)), float(g.get("c_f1", 11.5))
        margin = float(g.get("margin_m", 0.35))
        A = A.copy(); Y = Y.copy()
        H0 = Y[:, J_TOP].copy()
        h_s = float(np.interp(cs, c, H0))
        L = h_s + slope * (c - cs)
        k = 3.0
        T = np.where(c >= cs, np.logaddexp(k * H0, k * L) / k, H0)
        f = np.clip((cf1 - c) / (cf1 - cf0), 0, 1); f = f * f * (3 - 2 * f)
        dH = np.maximum(T - H0, 0.0) * f
        dH[c < cs] = 0.0
        # 空に出る余裕で頭打ち（列 90 の点を上げた時の像が原画の空に入らない）
        sky = getattr(self, "_sky", None)
        if sky is None:
            p = os.path.join(RC.OUT, "analysis", "sky_envelope.npy")
            if not os.path.isfile(p):
                sys.path.insert(0, os.path.join(RC.REPO, "Tools", "PaintingTruth"))
                import evaluate as EV
                os.makedirs(os.path.dirname(p), exist_ok=True)
                np.save(p, EV.Truth().cov["sky_envelope"].astype(np.float32))
            self._sky = sky = np.load(p)
        head = np.full(self.nv, np.inf)
        for r in np.nonzero(dH > 0)[0]:
            ys = Y[r, J_TOP] + np.linspace(0, 6.0, 121)
            P = KC.O + A[r, J_TOP] * KC.T + ys[:, None] * KC.UP + c[r] * KC.E
            q = RC.project(P)
            xi = np.clip(np.round(q[:, 0]).astype(int), 0, 1919); yi = np.clip(np.round(q[:, 1]).astype(int), 0, 1079)
            bad = sky[yi, xi] > 0.5
            head[r] = (ys[np.argmax(bad)] - Y[r, J_TOP]) if bad.any() else 6.0
        dH = np.minimum(dH, np.maximum(head - margin, 0.0))
        # c 方向にならして、頭打ちの折れを消す（ならした値も頭打ちを超えない）
        dcc = np.gradient(c)
        Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / float(g.get("smooth_m", 0.8))) ** 2) * dcc[None, :]
        Wm /= Wm.sum(1, keepdims=True)
        dH = np.minimum(Wm @ dH, np.where(np.isfinite(head), np.maximum(head - margin, 0.0), dH))
        # 始まりは c_start から ramp_in m かけてなめらかに（段の折れ目を作らない）
        ri = np.clip((c - cs) / float(g.get("ramp_in_m", 1.5)), 0, 1); ri = ri * ri * (3 - 2 * ri)
        dH = dH * ri
        self._crest_ramp_dH = dH
        je_lo, je_hi = float(g.get("j_end_132", 102)), float(g.get("j_end_far", 185))
        te = np.clip((c - 1.6) / float(g.get("j_end_width_c", 1.9)), 0, 1); te = te * te * (3 - 2 * te)
        j_end = je_lo + (je_hi - je_lo) * te
        jj = np.arange(self.nu)
        # 頂を上げる行のうち 132 の近く（c ≤ back_c1）では、頂を後ろへもずらす（δa = back_k·ΔH）。唇の頭（列 ≥ j_end）は
        # 動かせないので、上げるだけだと列 90〜102 の間で頂が尖る（F02 の Rmin・折れ）。後ろへずらすと唇の上の面が長くなる。
        bk = float(g.get("back_k", 0.0)); bc0, bc1 = g.get("back_c", [3.0, 6.0])
        wbk = np.clip((bc1 - c) / max(bc1 - bc0, 1e-6), 0, 1); wbk = wbk * wbk * (3 - 2 * wbk)
        daa = -bk * dH * wbk
        if g.get("back_smooth_m"):
            sgb = float(g["back_smooth_m"])
            Wb = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sgb) ** 2) * dcc[None, :]
            Wb /= Wb.sum(1, keepdims=True)
            daa = (Wb @ daa) * ri
        for r in np.nonzero(dH > 1e-4)[0]:
            Hr = max(H0[r], 0.3)
            da = daa[r]
            # 背の側（列 ≤ 90）：高さに応じて（足は動かさない）
            yb = Y[r, :J_TOP + 1]
            b0 = float(g.get("back_from_h", 0.25))
            t = np.clip((yb / Hr - b0) / (1.0 - b0), 0, 1); gb = t * t * (3 - 2 * t)
            Y[r, :J_TOP + 1] = yb + dH[r] * gb
            A[r, :J_TOP + 1] = A[r, :J_TOP + 1] + da * gb
            # 前の側（列 90..j_end）：列 90 で 1、j_end で 0
            jf = jj[(jj > J_TOP) & (jj < j_end[r])]
            u = (jf - J_TOP) / max(j_end[r] - J_TOP, 1.0); wf = 1 - u * u * (3 - 2 * u)
            Y[r, jf] = Y[r, jf] + dH[r] * wf
            A[r, jf] = A[r, jf] + da * wf
        return A, Y

    def crest_sharpen(self, A, Y):
        """頂の背の側（列 30..89）を頂へ寄せ、頂の丸い「頭巾」（頂から 0.4H 後ろでも 0.84H の高さ。頂の丸みの半径が約 7 m）を
        細くする。各点の頂からの後ろの距離 u = (a_top − a)/H を、高さ Yn = y/H に応じて u' = u·(1 − k·S((Yn − y_lo)/(1 − y_lo)))
        に縮める（S は smoothstep。高さが y_lo より低い背は動かない）。点は同じ高さのまま頂の側へ動くだけなので、
        原画視点の左の輪郭の射線に接する点も頂の側へ動く（輪郭の差は H の当てはめで戻す）。唇の側（列 ≥ 90）は変えない。"""
        g = self.d["crest_sharpen"]
        c = self.c
        k, ylo = float(g.get("k", 0.4)), float(g.get("y_lo", 0.6))
        c0, c1 = g.get("c", [-34.0, 12.0])
        wr = np.clip((c - c0) / 3.0, 0, 1) * np.clip((c1 - c) / 2.0, 0, 1); wr = wr * wr * (3 - 2 * wr)
        A = A.copy()
        at, H = A[:, J_TOP], np.maximum(Y[:, J_TOP], 0.3)
        cols = np.arange(30, J_TOP)
        Yn = Y[:, cols] / H[:, None]
        t = np.clip((Yn - ylo) / (1 - ylo), 0, 1); S = t * t * (3 - 2 * t)
        u = (at[:, None] - A[:, cols])
        un = u * (1 - k * wr[:, None] * S)
        A[:, cols] = at[:, None] - un
        return A, Y

    def back_ramp(self, A, Y):
        """背の下の部分（列 18..J_K）を、なだらかな背の坂（海から S 字に立ち上がる 3 次のベジエ）に作り直す。
        R4 の背は高さ 2〜12 m がほぼ鉛直の壁で、後ろから見ると布をかぶせた丸い塊（ドーム）に見える元になっている。
        列 J_K より上（頂の近くの稜。原画の左の輪郭の射線に接する点は列 75 以上）は変えない。坂は古い背より後ろ・低い側に
        しか出ないので、原画視点の輪郭の内側に残る。
        行ごとの背の長さ L（列 J_K から海の接点まで）は、max(古い長さ, y_k / tan θ) を c 方向に σ 2 m でならしてから使う
        （行ごとに max が切り替わると、背に斜めの折れ目ができる）。作り直しの重みは c の両端で 6 m かけて 0 にする。"""
        c = self.c
        jk = int(self.d.get("back_ramp_col", 70))
        th = math.radians(float(self.d.get("back_ramp_slope_deg", 40.0)))
        al, be = float(self.d.get("back_ramp_alpha", 0.45)), float(self.d.get("back_ramp_beta", 0.35))
        lo, hi = self.d.get("back_ramp_c", [-40.0, 11.5])
        fin, fout = float(self.d.get("back_ramp_fade_lo_m", 6.0)), float(self.d.get("back_ramp_fade_hi_m", 6.0))
        wb = np.clip((c - lo) / fin, 0, 1) * np.clip((hi - c) / fout, 0, 1)
        wb = wb * wb * (3 - 2 * wb)
        A = A.copy(); Y = Y.copy()
        yk = Y[:, jk]; ak = A[:, jk]
        L_old = ak - A[:, 18]
        L_new = np.maximum(yk, 0.0) / math.tan(th)
        L_raw = np.maximum(L_old, L_new)
        sig = float(self.d.get("back_ramp_L_sigma_m", 2.0))
        dcc = np.gradient(c)
        Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sig) ** 2) * dcc[None, :]
        Wm /= Wm.sum(1, keepdims=True)
        L_s = Wm @ L_raw
        if self.d.get("back_ramp_base_line"):
            # 背の足（海との接点）の平面の線 a_B(c) を、R4 の足と「頂の側の点から y_k/tan θ 後ろ」の後ろの方をとってから
            # c 方向に大きくならした 1 本のなめらかな線にする（頂の線の奥での後ろへの曲がりを背の足へ写さない：くびれ対策）
            sgB = float(self.d["back_ramp_base_line"].get("sigma_m", 6.0))
            aB_raw = np.minimum(A[:, 18], ak - L_new)
            Wb = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sgB) ** 2) * dcc[None, :]
            Wb /= Wb.sum(1, keepdims=True)
            aB_s = Wb @ aB_raw
            L_f = np.maximum(ak - aB_s, 0.3 * np.maximum(yk, 0.0))
        elif self.d.get("back_ramp_floor_old", True):
            L_f = L_s + np.logaddexp(0.0, 4.0 * (L_old - L_s)) / 4.0      # なめらかな max(L_s, L_old)
        else:
            L_f = L_s          # 古い背の長さを下限にしない（行ごとの長さの凸凹が上から見たくびれになるのを防ぐ）
        tt = np.linspace(0, 1, 400)
        for r in np.nonzero(wb > 0)[0]:
            if yk[r] < 1.0:
                continue
            tk = np.array([A[r, jk + 1] - A[r, jk - 1], Y[r, jk + 1] - Y[r, jk - 1]]); tk /= max(np.linalg.norm(tk), 1e-9)
            if tk[0] <= 0.05:
                tk = np.array([0.05, 1.0]); tk /= np.linalg.norm(tk)
            L = L_f[r]
            aB = ak[r] - L
            P0 = np.array([aB, 0.0]); P1 = np.array([aB + al * L, 0.0]); P3 = np.array([ak[r], yk[r]]); P2 = P3 - be * L * tk
            Bz = ((1 - tt)[:, None] ** 3 * P0 + 3 * ((1 - tt) ** 2 * tt)[:, None] * P1 + 3 * ((1 - tt) * tt ** 2)[:, None] * P2 + (tt ** 3)[:, None] * P3)
            if np.any(np.diff(Bz[:, 0]) < -1e-9):
                continue
            sB = np.r_[0, np.cumsum(np.hypot(*np.diff(Bz, axis=0).T))]
            su = np.linspace(0, sB[-1], jk - 18 + 1)
            an = np.interp(su, sB, Bz[:, 0]); yn = np.interp(su, sB, Bz[:, 1])
            w = wb[r]
            A[r, 18:jk + 1] = w * an + (1 - w) * A[r, 18:jk + 1]
            Y[r, 18:jk + 1] = w * yn + (1 - w) * Y[r, 18:jk + 1]
            a_end = self.A0[r, 0]
            A[r, 0:19] = a_end + (A[r, 18] - a_end) * np.linspace(0, 1, 19)
            Y[r, 0:18] = 0.0
        return A, Y

    # ------------------------------------------------------------ H_s
    def smooth_c(self, v, sigma):
        """行の値を c 方向にならす（行の間隔が不均一なので c の距離のガウス × 間隔の重み）。作り直す行だけ置き換える。"""
        c = self.c
        dc = np.gradient(c)
        W = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sigma) ** 2) * dc[None, :]
        W /= W.sum(1, keepdims=True)
        sm = W @ v
        w = self.w
        return w * sm + (1 - w) * v

    def H_initial(self, a_s):
        """R4 の頂の高さ（列 90）を c 方向に σ 1 m でならして始める（R4 の頂の高さの行ごとの揺れが、
        正規化した断面を置き直す時に断面全体の拡大の揺れ＝縦の筋になるのを防ぐ）。"""
        H = self.H0s.copy()
        tr = self.d.get("tail_ramp")
        if tr:
            # 左の尾（原画の画面の外。c ≤ −21 の行の頂は表示の x < 0 に写る）を、b区域の前の段（c −24〜−21 の傾き ≈ 1）の
            # ないなだらかな上り坂にする：c0 の値と傾きから c1 の値と傾きへの 3 次エルミート。後ろから見た背骨の単調さのため。
            c0, c1, s1 = tr["c0"], tr["c1"], tr.get("slope1", 0.45)
            c = self.c
            h0 = float(np.interp(c0, c, H)); h1 = float(np.interp(c1, c, H))
            g0 = float((np.interp(c0 + 0.5, c, H) - np.interp(c0 - 0.5, c, H)))
            L = c1 - c0
            t = np.clip((c - c0) / L, 0, 1)
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
            Ht = h00 * h0 + h10 * L * g0 + h01 * h1 + h11 * L * s1
            m = (c > c0) & (c < c1)
            H = H.copy(); H[m] = np.maximum(H[m], Ht[m]) if tr.get("raise_only", True) else Ht[m]
        return H

    def monotone_fill(self, H, c_from, c_to):
        """c_from..c_to の行で H を単調（非減少）にする：右から見た最小の包み（上から切る）ではなく、
        左から見た最大の包みを使うと高くなるので、右の値を上限にした「下から持ち上げない」単調化：
        H_mono(c) = min_{c' ≥ c, c' ≤ c_to} H(c')（くぼみの左の棚を切り下げる）。"""
        c = self.c
        idx = np.nonzero((c >= c_from) & (c <= c_to))[0]
        h = H[idx]
        hm = np.minimum.accumulate(h[::-1])[::-1]
        out = H.copy(); out[idx] = hm
        return out

    def basis(self, step=None):
        """H の直しの基底：c の 3 次 B スプライン（節の間隔 step m、作り直す範囲）。行 × 基底の行列。"""
        from scipy.interpolate import BSpline
        step = step or self.d.get("H_knot_step_m", 1.2)
        lo, hi = BLEND_L[0], C_R1
        n_in = max(int(round((hi - lo) / step)), 2)
        inner = np.linspace(lo, hi, n_in + 1)
        t = np.r_[[lo] * 3, inner, [hi] * 3]
        nb = len(t) - 4
        B = np.zeros((self.nv, nb))
        m = (self.c >= lo) & (self.c <= hi)
        for k in range(nb):
            cc = np.zeros(nb); cc[k] = 1
            B[m, k] = BSpline(t, cc, 3, extrapolate=False)(self.c[m])
        return np.nan_to_num(B)

    def fit_H(self, a_s, H, iters=None, gain=None, log=None, allow_lower=True):
        """原画の外輪郭（x 150..766）の上側の包絡に合うように H_s を直す（なめらかな基底の Gauss–Newton）。
        各 x の輪郭の点は、その像を作る行の頂の近くの稜の点（射線に接する点）。H を変えると断面は頂の a_s を中心に
        拡大・縮小するので、その点は像の上で動く。戻り値：H、最後の像の差（px）、その行、経過。"""
        iters = iters or self.d["fit_iters"]; gain = gain or self.d["fit_gain"]
        c = self.c
        x0, x1 = X_FIT
        ty = np.interp(np.arange(x0, x1 + 1), self.xs, self.ys)
        ty[np.arange(x0, x1 + 1) < self.xs[0]] = np.nan   # 78 の左端より左は測らない（空へのはみ出しは別に見る）
        # 縦の差を輪郭の法線の距離へ（傾きのある所で縦の差は大きく出る）
        sl = np.gradient(np.interp(np.arange(x0, x1 + 1), self.xs, self.ys))
        self.cosn = 1.0 / np.sqrt(1.0 + sl * sl)
        rows_env = np.nonzero((c >= -45) & (c <= 3))[0]
        B = self.basis() * self.w[:, None]
        nb = B.shape[1]
        D2 = np.diff(np.eye(nb), 2, axis=0)
        lam = self.d.get("H_fit_smooth", 30.0)
        hist = []
        for it in range(iters):
            A, Y = self.place(a_s, H)
            ey, er, eX = upper_envelope(c, A, Y, x0, x1, rows_env)
            err = (ey - ty) * self.cosn           # + = 描いた輪郭が原画より下（低すぎる）。法線の距離（px）
            ok = np.isfinite(err) & np.isfinite(er)
            if not ok.any():
                break
            r_i = er[ok]; Xp = eX[ok]
            ri = np.clip(np.round(r_i).astype(int), 0, self.nv - 1)
            S = RC.sec(Xp)
            Hr = np.maximum(H[ri], 0.5)
            dH = 0.05
            S2 = S.copy(); S2[:, 0] = a_s[ri] + (S[:, 0] - a_s[ri]) * (1 + dH / Hr); S2[:, 1] = S[:, 1] * (1 + dH / Hr)
            P2 = KC.O + S2[:, 0:1] * KC.T + S2[:, 1:2] * KC.UP + S2[:, 2:3] * KC.E
            J = (RC.project(P2)[:, 1] - RC.project(Xp)[:, 1]) / dH * self.cosn[ok]      # px / m（負）
            # 行の小数の位置で基底を補間
            r0 = np.clip(np.floor(r_i).astype(int), 0, self.nv - 2); f = r_i - r0
            Bx = B[r0] * (1 - f)[:, None] + B[r0 + 1] * f[:, None]
            Jm = J[:, None] * Bx
            e = err[ok]
            # 大きい差ほど重く（最大 ≤ 4 px を狙う）
            wgt = 1.0 + (np.abs(e) / 3.0) ** 2
            JtJ = (Jm * wgt[:, None]).T @ Jm + lam * D2.T @ D2 + 1e-3 * np.eye(nb)
            g = (Jm * wgt[:, None]).T @ e
            # 単調さ（左の尾から背骨の頂まで H が下らない）：傾きが s_min を下回る所に罰
            mz = np.nonzero((c >= self.d["H_monotone_from_c"]) & (c <= self.d.get("H_monotone_to_c", -2.6)))[0]
            if len(mz) > 2 and self.d.get("H_monotone_weight", 0) > 0:
                i0, i1 = mz[:-1], mz[1:]
                dcc = c[i1] - c[i0]
                slope = (H[i1] - H[i0]) / dcc
                Ds = (B[i1] - B[i0]) / dcc[:, None]
                smin = self.d.get("H_monotone_min_slope", 0.03)
                act = slope < smin
                mu = self.d["H_monotone_weight"]
                if act.any():
                    JtJ += mu * Ds[act].T @ Ds[act]
                    g += mu * Ds[act].T @ (slope[act] - smin)
            dcoef = -np.linalg.solve(JtJ, g)
            upd = B @ dcoef
            if not allow_lower:
                upd = np.maximum(upd, 0)
            H = H + gain * upd
            hist.append({"it": it, "err_abs_max_px": float(np.nanmax(np.abs(err))), "err_abs_p95_px": float(np.nanpercentile(np.abs(err), 95))})
            if log:
                log("   fit it %d  |err| max %.2f p95 %.2f px" % (it, hist[-1]["err_abs_max_px"], hist[-1]["err_abs_p95_px"]))
        A, Y = self.place(a_s, H)
        ey, er, eX = upper_envelope(c, A, Y, x0, x1, rows_env)
        err = (ey - ty) * self.cosn
        return H, err, er, hist


# ---------------------------------------------------------------- objectives
def back65_cam():
    """clay_render_f の back34_follow（B34_ANG −65°、距離 90、高さ 18、注視 8 m、縦 26°）を t* の O で。"""
    a = math.radians(-65.0)
    dvec = math.cos(a) * KC.E + math.sin(a) * KC.T
    pos = KC.O + 90.0 * dvec + np.array([0, 18.0, 0])
    tgt = KC.O + np.array([0, 8.0, 0])
    return pos, tgt, 26.0


def project_cam(P, pos, tgt, vfov, w=1920, h=1080):
    f = tgt - pos; f /= np.linalg.norm(f)
    r = np.cross(KC.UP, f); r /= np.linalg.norm(r)
    u = np.cross(f, r)
    d = np.asarray(P, float) - pos
    cx, cy, cz = d @ r, d @ u, d @ f
    t = math.tan(math.radians(vfov) / 2); asp = w / float(h)
    return np.stack([(0.5 + 0.5 * cx / cz / (t * asp)) * w, (1 - (0.5 + 0.5 * cy / cz / t)) * h], -1)


def spine_terms(c, a_s, H_s, lo=-34.0, hi=-2.4):
    m = (c >= lo) & (c <= hi)
    cc, aa, hh = c[m], a_s[m], H_s[m]
    # 一様な c へ取り直す
    g = np.arange(lo, hi + 1e-9, 1.0)
    a_g = np.interp(g, cc, aa); h_g = np.interp(g, cc, hh)
    P = KC.O + a_g[:, None] * KC.T + h_g[:, None] * KC.UP + g[:, None] * KC.E
    # 3 次元の曲がり（弧長あたりの角の変化）
    d1 = np.diff(P, axis=0); L = np.linalg.norm(d1, axis=1); t1 = d1 / L[:, None]
    ang = np.arccos(np.clip((t1[1:] * t1[:-1]).sum(1), -1, 1)) / (0.5 * (L[1:] + L[:-1]))
    # 後ろ 65° の像の曲がり
    pos, tgt, vf = back65_cam()
    q = project_cam(P, pos, tgt, vf)
    dq = np.diff(q, axis=0); Lq = np.linalg.norm(dq, axis=1); tq = dq / np.maximum(Lq[:, None], 1e-9)
    angq = np.arccos(np.clip((tq[1:] * tq[:-1]).sum(1), -1, 1))
    # 上から見た曲がり（a の 2 階差分、m/m²）
    a2 = np.diff(a_g, 2) / 1.0 ** 2
    # 単調さ：H の下り（くぼみ）の合計
    dh = np.diff(h_g)
    dip = float(-dh[dh < 0].sum())
    # 後ろ 65° の像の曲がりの符号の変わり（こぶ・くぼみの数）
    sgn = np.sign(np.cross(tq[:-1], tq[1:]))
    sgn = sgn[np.abs(np.degrees(angq)) > 0.5]
    flips = int((np.diff(sgn) != 0).sum()) if len(sgn) > 1 else 0
    # 傾き dH/dc が一つの山か（二つの山の間の谷 = ドームの前の棚とくぼみ）
    sl = np.diff(h_g) / 1.0
    slm = np.convolve(np.pad(sl, 1, mode="edge"), np.ones(3) / 3, "valid")
    tv = float(np.abs(np.diff(slm)).sum())
    multimodal = tv - (2 * float(slm.max()) - float(slm[0]) - float(slm[-1]))
    return {"slope_multimodality": multimodal, "slope_max": float(slm.max()),
            "curv3d_p95_rad_per_m": float(np.percentile(ang, 95)), "curv3d_max_rad_per_m": float(ang.max()),
            "back65_turn_total_deg": float(np.degrees(angq.sum())), "back65_turn_max_deg_per_1m": float(np.degrees(angq.max())),
            "back65_inflections": flips,
            "top_a2_p95": float(np.percentile(np.abs(a2), 95)), "top_a2_max": float(np.abs(a2).max()),
            "H_dip_total_m": dip, "H_min_slope": float(dh.min() / 1.0)}


def r6_fast(c, A, Y, Rm=6.0, row_step=4, col_step=6, pt_step=3):
    """評審の j_bulge6 の R6 と同じ定義の速い近似（中心の間引きを粗く）。p99・最大・領域別。"""
    nv, nu = A.shape
    X = RC.world(c, A, Y)
    s = np.concatenate([np.zeros((nv, 1)), np.cumsum(np.linalg.norm(np.diff(X, axis=1), axis=-1), 1)], 1)
    tip = np.full(nv, 200)
    rows = [r for r in range(nv) if abs(c[r]) <= 16][::row_step]
    vals = []
    for r0 in rows:
        rs = np.nonzero(np.abs(c - c[r0]) <= Rm)[0][::2]
        for j0 in range(18, 201, col_step):
            if Y[r0, j0] < 0.5 or j0 > tip[r0] - 12:
                continue
            pts = []
            for r in rs:
                jj = np.nonzero((np.abs(s[r] - s[r, j0]) <= Rm) & (np.arange(nu) <= tip[r] - 8))[0][::pt_step]
                pts.append(X[r, jj])
            P = np.concatenate(pts)
            P = P[np.linalg.norm(P - X[r0, j0], axis=1) <= Rm]
            if len(P) < 30:
                continue
            mu = P.mean(0); _, _, Vt = np.linalg.svd(P - mu, full_matrices=False)
            Q = P - X[r0, j0]; u = Q @ Vt[0]; v = Q @ Vt[1]; w = Q @ Vt[2]
            Mx = np.c_[np.ones_like(u), u, v, u * u, u * v, v * v]
            co, *_ = np.linalg.lstsq(Mx, w, rcond=None)
            vals.append((c[r0], j0, abs(co[0])))
    v = np.array(vals)
    reg = {}
    for nm, (ja, jb) in (("back", (18, 90)), ("crest_liptop", (90, 201))):
        for cn, (ca, cb) in (("shoulder", (-16, -6)), ("main", (-6, 3)), ("far", (3, 16))):
            mm = (v[:, 1] >= ja) & (v[:, 1] < jb) & (v[:, 0] >= ca) & (v[:, 0] < cb)
            if mm.sum() > 3:
                reg[nm + "/" + cn] = [round(float(np.percentile(v[mm, 2], 99)), 3), round(float(v[mm, 2].max()), 3)]
    return {"p99": float(np.percentile(v[:, 2], 99)), "max": float(v[:, 2].max()), "regions": reg, "n": int(len(v))}


def evaluate_design(design, log=None, want_r6=True):
    M = Model(design)
    a_s = M.a_spine()
    H = M.H_initial(a_s)
    # 左の尾から輪郭の始まりまで単調に（くぼみの左の棚を切り下げる）
    H, err, er, hist = M.fit_H(a_s, H, log=log)
    A, Y = M.place(a_s, H)
    sp = spine_terms(M.c, a_s, H)
    ok = np.isfinite(err)
    res = {"outline_err_abs_max_px": float(np.nanmax(np.abs(err))), "outline_err_abs_p95_px": float(np.nanpercentile(np.abs(err), 95)),
           "spine": sp, "fit_hist": hist[-3:]}
    if want_r6:
        res["r6_fast"] = r6_fast(M.c, A, Y)
    return M, a_s, H, A, Y, res


def objective(res, w=None):
    """背骨の選び方の目的（小さいほどよい）。輪郭の最大 3.5 px を超える分を強く罰し、ドームの測り（R6 の近似）、
    後ろから見た背骨の単調さ（くぼみ・傾きの二つの山）、3 次元の曲がり、上から見た曲がりを足す。"""
    w = w or {"outline": 2.0, "r6": 10.0, "dip": 8.0, "multi": 3.0, "a2": 10.0, "c3d": 5.0}
    sp = res["spine"]
    o = (w["outline"] * max(res["outline_err_abs_max_px"] - 3.5, 0) ** 2 + 0.3 * res["outline_err_abs_p95_px"]
         + w["r6"] * res["r6_fast"]["p99"] + w["dip"] * sp["H_dip_total_m"] + w["multi"] * sp["slope_multimodality"]
         + w["a2"] * sp["top_a2_p95"] + w["c3d"] * sp["curv3d_p95_rad_per_m"])
    return float(o)


def write_candidate(prefix, c, A, Y, design, res):
    prov = {"route": "仕上げ28 第1回（射線の案 RAYS）Tools/GWWaveGen/kstar_p28/rays_build.py", "base": "K*′ R4 (kstar_final, SHA-256 rows %s…)" % RC.R4_SHA["rows"][:8],
            "design": design, "reference_model_read_by_generator": False}
    return KC.write_candidate(prefix, c, A, Y, prov)


def main():
    mode = sys.argv[1]
    if mode == "build":
        pre = sys.argv[2]
        design = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
        t0 = time.time()
        M, a_s, H, A, Y, res = evaluate_design(design, log=print)
        os.makedirs(os.path.dirname(pre), exist_ok=True)
        meta = write_candidate(pre, M.c, A, Y, M.d, res)
        np.savez_compressed(pre + "_spine.npz", c=M.c, a_s=a_s, H_s=H, a0=M.a0, H0=M.H0)
        res["objective"] = objective(res)
        res["seconds"] = round(time.time() - t0, 1)
        res["design"] = M.d
        RC.jdump(res, pre + "_build_report.json")
        print(json.dumps({k: v for k, v in res.items() if k != "design"}, ensure_ascii=False, default=float)[:3000])
    elif mode == "search":
        out = sys.argv[2]
        os.makedirs(out, exist_ok=True)
        from scipy.optimize import minimize
        base = dict(DEFAULT)
        if len(sys.argv) > 3:
            base.update(json.load(open(sys.argv[3], encoding="utf-8")))
        free = [1, 2, 3, 4, 5, 6]      # 節 −26, −20, −16, −12, −8, −4 の a のずれ
        hist = []

        def f(x):
            d = dict(base); v = list(base["a_knots_v"])
            for i, k in enumerate(free):
                v[k] = float(x[i])
            d["a_knots_v"] = v
            _, _, _, _, _, res = evaluate_design(d)
            o = objective(res)
            hist.append({"x": [float(t) for t in x], "obj": o, "outline_max": res["outline_err_abs_max_px"], "r6": res["r6_fast"]["p99"],
                         "spine": res["spine"]})
            print("%3d obj %.3f  x %s  outline %.2f  r6 %.3f  dip %.3f  multi %.3f  a2 %.3f" % (len(hist), o, np.round(x, 2), res["outline_err_abs_max_px"],
                  res["r6_fast"]["p99"], res["spine"]["H_dip_total_m"], res["spine"]["slope_multimodality"], res["spine"]["top_a2_p95"]), flush=True)
            RC.jdump(hist, os.path.join(out, "search_hist.json"))
            return o
        x0 = np.zeros(len(free))
        r = minimize(f, x0, method="Nelder-Mead", options={"maxfev": int(os.environ.get("RAYS_MAXFEV", "60")), "xatol": 0.1, "fatol": 0.01,
                                                              "initial_simplex": np.vstack([x0] + [x0 + 1.5 * np.eye(len(free))[i] for i in range(len(free))])})
        best = dict(base); v = list(base["a_knots_v"])
        for i, k in enumerate(free):
            v[k] = float(r.x[i])
        best["a_knots_v"] = v
        RC.jdump(best, os.path.join(out, "best_design.json"))
        print("best", r.fun, r.x)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
