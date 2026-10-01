# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：原画視点の輪郭を、なめらかな低次元の場（3 次 B スプライン）で合わせる（py -3.10）。

faceswap_edgefit（縁の頂点を動かして周りへ広げる）は細い帯を動かすので、クレイの描画で細い折れ（しわ）になった。ここでは
  変位 = φ(c, j) · n（n は行の面の中の断面の外向きの法線）、φ(c, j) = Σ_k Σ_l B_k(c) B_l(j) θ_kl
の係数 θ（行の向き n_c 個 × 列の向き n_j 個、端の関数は 0 に固定）を、原画の線の各点の符号付きの差（px、faceswap_edgefit.errors）を
最小にするように、ガウス・ニュートン（数値のヤコビアン）で解く。場そのものがなめらかなので、しわや折れを作らない。
正則化：Σθ² と、隣り合う係数の差（行の向き・列の向き）。"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
KC = F.KC


def bspline_basis(x, lo, hi, n, deg=3):
    """[lo, hi] に等間隔の節の n 個の B スプラインの基底（x の外は 0）。端の関数（最初と最後の 1 個ずつ）は後で除く。"""
    from scipy.interpolate import BSpline
    inner = np.linspace(lo, hi, n - deg + 1)
    t = np.r_[[lo] * deg, inner, [hi] * deg]
    B = np.zeros((len(x), n))
    xin = (x >= lo) & (x <= hi)
    for k in range(n):
        cc = np.zeros(n); cc[k] = 1
        B[xin, k] = BSpline(t, cc, deg, extrapolate=False)(x[xin])
    return np.nan_to_num(B)


def profile_normals(A, Y):
    """行の断面の外向きの法線（行の面の中、(a, y)）。列の増える向きの接線を反時計回りに 90° 回したもの。"""
    ta = np.gradient(A, axis=1); ty = np.gradient(Y, axis=1)
    L = np.maximum(np.hypot(ta, ty), 1e-12)
    return -ty / L, ta / L


class BSFit:
    def __init__(self, ef, c, A, Y, rows_c, cols, n_c, n_j, segs, weights=None, trim=1):
        self.ef, self.c, self.A0, self.Y0 = ef, c, A.copy(), Y.copy()
        self.segs = segs
        self.w = weights or {}
        Bc = bspline_basis(c, rows_c[0], rows_c[1], n_c)
        j = np.arange(A.shape[1], dtype=float)
        Bj = bspline_basis(j, cols[0], cols[1], n_j)
        # 端の関数を除く（境で 0、値と傾きが続く）
        self.Bc = Bc[:, trim:n_c - trim]
        self.Bj = Bj[:, trim:n_j - trim]
        self.na, self.ny = profile_normals(A, Y)
        self.shape = (self.Bc.shape[1], self.Bj.shape[1])

    def apply(self, th):
        phi = self.Bc @ th.reshape(self.shape) @ self.Bj.T
        return self.A0 + phi * self.na, self.Y0 + phi * self.ny

    def residual(self, th, reach=40.0):
        A, Y = self.apply(th)
        _, _, f = self.ef.render(self.c, A, Y)
        E = self.ef.errors(f, self.segs, reach=reach)
        out = []
        for k in self.segs:
            e = E[k].copy()
            e[~np.isfinite(e)] = reach
            out.append(e * self.w.get(k, 1.0))
        return np.concatenate(out)

    def solve(self, iters=5, lam=2.0, smooth=4.0, step=0.04, log=print, max_step_m=0.8):
        n = self.shape[0] * self.shape[1]
        th = np.zeros(n)
        # 正則化：θ² と隣の差
        D = []
        for i in range(self.shape[0]):
            for jj in range(self.shape[1] - 1):
                v = np.zeros(n); v[i * self.shape[1] + jj] = 1; v[i * self.shape[1] + jj + 1] = -1; D.append(v)
        for i in range(self.shape[0] - 1):
            for jj in range(self.shape[1]):
                v = np.zeros(n); v[i * self.shape[1] + jj] = 1; v[(i + 1) * self.shape[1] + jj] = -1; D.append(v)
        D = np.array(D) if D else np.zeros((0, n))
        hist = []
        for it in range(iters):
            t0 = time.time()
            r0 = self.residual(th)
            J = np.zeros((len(r0), n))
            for k in range(n):
                th2 = th.copy(); th2[k] += step
                J[:, k] = (self.residual(th2) - r0) / step
            H = J.T @ J + lam * np.eye(n) + smooth * D.T @ D
            g = J.T @ r0 + lam * th + smooth * D.T @ (D @ th)
            dth = -np.linalg.solve(H, g)
            if np.abs(dth).max() > max_step_m:
                dth *= max_step_m / np.abs(dth).max()
            # 直線探索（半分ずつ）
            best = (float(np.sum(r0 ** 2)), 0.0)
            for s in (1.0, 0.5, 0.25):
                r1 = self.residual(th + s * dth)
                v = float(np.sum(r1 ** 2))
                if v < best[0]:
                    best = (v, s)
                    break
            th = th + best[1] * dth
            hist.append({"it": it, "sse_before": float(np.sum(r0 ** 2)), "sse_after": best[0], "step": best[1],
                         "max_abs_px_before": float(np.abs(r0).max()), "theta_max_m": float(np.abs(th).max()), "sec": round(time.time() - t0, 1)})
            log("  bsfit it %d: sse %.1f -> %.1f (step %.2f), max|e| %.2f px, max|theta| %.3f m, %.0fs" % (
                it, hist[-1]["sse_before"], best[0], best[1], hist[-1]["max_abs_px_before"], hist[-1]["theta_max_m"], hist[-1]["sec"]))
            if best[1] == 0.0:
                break
        A, Y = self.apply(th)
        return A, Y, th, hist
