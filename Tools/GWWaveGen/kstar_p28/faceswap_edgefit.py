# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：原画視点の輪郭を「側の縁」だけで合わせる道具（Q21 の合わせ方。py -3.10、numpy + cv2）。

やり方（1 回の反復）
  1. 形を原画カメラで描き（評価器と同じ rasterize と参照の海面）、被覆の 0.5 の等値線を得る（評価器と同じ平滑）。
  2. 目標の線（78・130・131 は原画の線そのもの、132・72 は σ12 の大きな輪郭）の各点で、線の法線（空の側が +）に沿って
     描いた縁までの符号付きの差 e（px。+ = 空へはみ出し、− = 穴）を測る。
  3. 縁を描いている頂点（見えていて、面が視線にほぼ沿う頂点）のうち、描いた縁に最も近いものを選び、
     その行の面の中（a, y）で面の法線の向きへ、投影が −e だけ動く量を動かす（1 回の上限つき）。
  4. 動かす量を、網の上のガウス（c の向き σ_c、弧長の向き σ_s）で周りへ広げる（内側の面は動かさない：広げる幅は縁の近くだけ）。
  5. 減衰を掛けて足し、繰り返す。
行は c 一定の面に残る（E の成分は動かさない）。トポロジー・列の並び・UV は変えない。"""
import os
import sys
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
KC = F.KC


def resample(P, step):
    P = np.asarray(P, float)
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    n = max(2, int(math.floor(s[-1] / step)) + 1)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], -1)


class EdgeFit:
    def __init__(self, gate=None, step_px=3.0):
        import cv2
        gate = gate or F.QuickGate()          # kh_gate_lf が kstar3 などを sys.path に足す
        import candA_common as C
        import gw_wavegen as G0
        self.cv2 = cv2
        self.gate = gate or F.QuickGate()
        tr = self.gate.lf.truth
        self.sky = tr.cov["sky_envelope"]
        self.sig = float(tr.spec["scoring"]["contour"]["boundary_smoothing_sigma_px"])
        self.V1, self.tgt, self.fr = C.painting_frame()
        self.seacov, _ = G0.sea_horizon_cover(self.fr.cam, self.tgt.spec)
        seg = F.outline_segments()
        lf = self.gate.lf.lf
        self.targets = {"78": resample(seg["78"], step_px), "130": resample(seg["130"], step_px), "131": resample(seg["131"], step_px),
                        "132": resample(lf["132"], step_px), "72": resample(lf["72"], step_px)}
        self.normals = {}
        for k, P in self.targets.items():
            t = np.gradient(P, axis=0)
            t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
            n = np.stack([t[:, 1], -t[:, 0]], -1)
            # 空の側を + にする（原画の空の被覆で向きを決める）
            q = P + 5 * n
            s_plus = self._sample(self.sky, q)
            s_minus = self._sample(self.sky, P - 5 * n)
            flip = s_plus < s_minus
            n[flip] *= -1
            self.normals[k] = n

    @staticmethod
    def _sample(img, P):
        h, w = img.shape
        x = np.clip(P[:, 0], 0, w - 1.001); y = np.clip(P[:, 1], 0, h - 1.001)
        x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
        fx = x - x0; fy = y - y0
        return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy
                + img[y0 + 1, x0 + 1] * fx * fy)

    def render(self, c, A, Y):
        X = self.fr.world(c, A, Y)
        cov = self.V1.rasterize(self.fr.cam, X, self.V1.triangles(A.shape[1], A.shape[0]))
        other = np.maximum(cov, self.seacov)
        f = self.cv2.GaussianBlur(np.asarray(other, np.float64), (0, 0), self.sig) if self.sig > 0 else other
        return X, cov, f

    def errors(self, f, segs, reach=40.0):
        """各目標点の符号付きの差（px）。見つからない所は nan。"""
        out = {}
        ss = np.arange(-reach, reach + 0.01, 0.5)
        for k in segs:
            P, n = self.targets[k], self.normals[k]
            Q = P[:, None, :] + ss[None, :, None] * n[:, None, :]
            v = self._sample(f, Q.reshape(-1, 2)).reshape(len(P), len(ss)) - 0.5      # >0 = 波（空でない）
            e = np.full(len(P), np.nan)
            for i in range(len(P)):
                sg = np.sign(v[i])
                cross = np.nonzero(sg[:-1] * sg[1:] <= 0)[0]
                if len(cross) == 0:
                    continue
                # 空の側（+s）へ向かって 波 → 空 に変わる交差のうち、0 に最も近いもの
                cand = [k2 for k2 in cross if v[i, k2] > 0 >= v[i, k2 + 1]]
                if not cand:
                    continue
                k2 = min(cand, key=lambda q: abs(ss[q]))
                t = v[i, k2] / (v[i, k2] - v[i, k2 + 1])
                e[i] = ss[k2] + t * (ss[k2 + 1] - ss[k2])
            out[k] = e
        return out

    # 輪郭ごとに、縁を描いてよい頂点の範囲（列・行の c）。背（原画視点で見えない面）へ広げないため。
    SEG_COLS = {"78": (40, 205), "130": (40, 205), "131": (40, 205), "132": (80, 216), "72": (150, 395)}

    def step(self, c, A, Y, segs, sigma_c=0.9, sigma_s=0.9, damp=0.7, max_move=0.4, vis_tol=0.6, tang_max=0.45,
             rows_mask=None, cols_mask=None, weights=None, sigma_j=14.0, seg_cols=None):
        cv2 = self.cv2
        nv, nu = A.shape
        X, cov, f = self.render(c, A, Y)
        E = self.errors(f, segs)
        # 頂点の投影と深さ、面の法線
        P = self.fr.cam.project(X.reshape(-1, 3)).reshape(nv, nu, 3)
        Xu = np.gradient(X, axis=1); Xv = np.gradient(X, axis=0)
        N = np.cross(Xu, Xv)
        N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
        ray = X - KC.CAM_POS_U[None, None, :]
        dist = np.linalg.norm(ray, axis=-1)
        ray = ray / dist[..., None]
        tang = np.abs((N * ray).sum(-1))
        # z-buffer（頂点の点描、半径 1 px）
        zb = np.full((1080, 1920), np.inf)
        xi = np.round(P[..., 0]).astype(int); yi = np.round(P[..., 1]).astype(int)
        ok = (xi >= 1) & (xi < 1919) & (yi >= 1) & (yi < 1079) & (P[..., 2] > 0)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                np.minimum.at(zb, (yi[ok] + dy, xi[ok] + dx), P[..., 2][ok])
        vis = np.zeros((nv, nu), bool)
        vis[ok] = P[..., 2][ok] <= zb[yi[ok], xi[ok]] + vis_tol
        cand0 = vis & (tang <= tang_max) & (Y > 0.2)
        cand = cand0
        if rows_mask is not None:
            cand &= rows_mask[:, None]
        if cols_mask is not None:
            cand &= cols_mask
        from scipy.spatial import cKDTree
        jgrid = np.arange(nu)[None, :]
        imp_r, imp_j, imp_d = [], [], []
        report = {}
        for k in segs:
            lo, hi = (seg_cols or {}).get(k, self.SEG_COLS.get(k, (0, nu - 1)))
            cm = cand & (jgrid >= lo) & (jgrid <= hi)
            ci = np.argwhere(cm)
            cp = P[cm][:, :2]
            kd = cKDTree(cp)
            e = E[k]
            T, n = self.targets[k], self.normals[k]
            w = 1.0 if weights is None else weights.get(k, 1.0)
            used = 0
            for i in range(len(T)):
                if not np.isfinite(e[i]) or abs(e[i]) < 0.25:
                    continue
                b = T[i] + e[i] * n[i]
                dd, ii = kd.query(b, k=3, distance_upper_bound=6.0)
                for d_, i_ in zip(np.atleast_1d(dd), np.atleast_1d(ii)):
                    if not np.isfinite(d_):
                        continue
                    r, j = ci[i_]
                    # 行の面の中の向き：面の法線から E の成分を除く
                    Nd = N[r, j] - (N[r, j] @ KC.E) * KC.E
                    Nd /= max(np.linalg.norm(Nd), 1e-9)
                    p0 = P[r, j, :2]
                    p1 = self.fr.cam.project((X[r, j] + 0.02 * Nd)[None])[0, :2]
                    g = float((p1 - p0) @ n[i]) / 0.02          # px / m
                    if abs(g) < 2.0:
                        continue
                    mv = float(np.clip(-e[i] / g, -max_move, max_move)) * w
                    da = mv * float(Nd @ KC.T); dy = mv * float(Nd[1])
                    imp_r.append(r); imp_j.append(j); imp_d.append((da, dy))
                    used += 1
                    break
            fin = np.isfinite(e)
            report[k] = {"n": int(len(e)), "found": int(fin.sum()), "max_abs": float(np.nanmax(np.abs(e))) if fin.any() else None,
                         "mean": float(np.nanmean(e)) if fin.any() else None, "min": float(np.nanmin(e)) if fin.any() else None,
                         "max": float(np.nanmax(e)) if fin.any() else None,
                         "p95_abs": float(np.nanpercentile(np.abs(e), 95)) if fin.any() else None, "impulses": used}
        if not imp_r:
            return A, Y, report
        imp_r = np.array(imp_r); imp_j = np.array(imp_j); imp_d = np.array(imp_d)
        # 広げる：c の距離と、行の中の弧長の距離（インパルスの行で測る）
        S = np.concatenate([np.zeros((nv, 1)), np.cumsum(np.hypot(np.diff(A, axis=1), np.diff(Y, axis=1)), 1)], 1)
        D = np.zeros((nv, nu, 2)); Wsum = np.zeros((nv, nu))
        rows_near = [np.nonzero(np.abs(c - c[r]) <= 3 * sigma_c)[0] for r in range(nv)]
        for (r, j, d) in zip(imp_r, imp_j, imp_d):
            rr = rows_near[r]
            wc = np.exp(-0.5 * ((c[rr] - c[r]) / sigma_c) ** 2)
            ds = S[rr] - S[rr, j][:, None]
            # 行ごとに同じ列の弧長の位置を基準にする
            ws = np.exp(-0.5 * (ds / sigma_s) ** 2) * np.exp(-0.5 * ((np.arange(nu) - j) / sigma_j) ** 2)[None, :]
            w = wc[:, None] * ws
            D[rr] += w[..., None] * np.array(d)[None, None, :]
            Wsum[rr] += w
        D /= np.maximum(Wsum, 1.0)[..., None]
        if cols_mask is not None:
            D *= cols_mask[..., None]
        if rows_mask is not None:
            D *= rows_mask.astype(float)[:, None, None]      # 範囲の外の行は広がりでも動かさない
        A2 = A + damp * D[..., 0]
        Y2 = Y + damp * D[..., 1]
        return A2, Y2, report

    def run(self, c, A, Y, segs, iters=8, log=print, seg_kw=None, **kw):
        """seg_kw: {輪郭: {sigma_c, sigma_s, sigma_j, ...}} 輪郭ごとに広げ方を変える（左の外輪郭は広く、唇の頭と管は細かく）。"""
        for it in range(iters):
            if seg_kw:
                rep = {}
                for group, kk in seg_kw.items():
                    gs = [s_ for s_ in group.split("+") if s_ in segs]
                    if not gs:
                        continue
                    kw2 = dict(kw); kw2.update(kk)
                    A, Y, r_ = self.step(c, A, Y, gs, **kw2)
                    rep.update(r_)
            else:
                A, Y, rep = self.step(c, A, Y, segs, **kw)
            log("  edgefit it %d: %s" % (it, {k: (round(v["max_abs"], 2) if v["max_abs"] is not None else None,
                                                  round(v["min"], 1) if v.get("min") is not None else None,
                                                  round(v["max"], 1) if v.get("max") is not None else None, v["impulses"]) for k, v in rep.items()}))
        return A, Y
