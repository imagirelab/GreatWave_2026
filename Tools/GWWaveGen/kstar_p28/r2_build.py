# -*- coding: utf-8 -*-
"""仕上げ28 第2回（r2）の生成器：第1回の最良の候補 P28R1（RAYS）を土台に、原画視点で見えない所の断面を読み直す。py -3.10

なぜ（第1回の3案の共通の原因）：各行の断面では、管の奥（列 314 の角）が頂の 5〜8 m 後ろまで入り込み、背がその管を
半径 8 m ほどの円で包む（断面が「頭巾」）。頂の線 H(c) も原画で決まるので、背の足や頂をどう配っても、後ろからは丸い頭巾の
連なり＝ドームに見えた。第2回は、原画の空を通る射線（r2_common.keepout_grids：行ごとの「空の射線の禁止域」）に触れない
範囲で、見えない所の断面を作り直す。採った設計（cand/r2_design.json）で働く段（run の順）：
  T 管を前へ（tube）：禁止域に新しくかからない最大の量（行ごと）で、管の奥（列 228〜378）を頂の a + 0.8 m まで前へずらす。
    管の口の空（72 の内側）が通る行 c ≳ −1.2 はずらせない（fig_keepout_rows）。c −31〜−1.2（端は 2 m・4.5 m でなめらかに）。
  B 背を波の背に（back）：背（列 18..JK=78）を、海から凹んで立ち上がり列 JK へ接する 3 次のベジエ（S 字）で作り直す。
    平均の傾き θ_b = 52°（既定の長さ L = y_JK/tan θ_b）。管の内側から壁 1.8 m（元が薄い行は元の 0.9 倍）を保つ最小の長さで下を押さえ、
    奥の行（c 2〜6 で）は元の背の長さへ戻す。背は c 方向に σ 0.9 m でならし、断面が自己交差する行は元の背へ戻す。
  N 手前の尾（stretch_tail・tail_cols）：原画の画面の外の尾の行（c ≲ −24.5）の上の部分（y/H > 0.25）を頂のまわりに横へ広げ（最大 2.7 倍）、
    頂のまわりを列の方向にならす（頂の ±2 m の弦の角を 110° 以上に）。足元の幅は変えない。
  F 奥の頂の線（far_wall・crest_line_smooth・far_wall_height・col_smooth）：奥の行（c 3〜12.9）の頂の線（列 90）を c 方向に
    σ 1.5 m でならし、その動きを断面の上の部分へ同じ量だけ移す（評審の R6 の奥の頂のこぶ）。壁が 0.1 m 以下の奥の行は、
    先に背を 0.7 m（列 ≤ 62）後ろへ出し、後で管の角の高さのまわり（σ_y 2 m）だけ 0.6 m 出す（角が背に写る折れ目を消す）。
  L b区域の 3 つの房（b_lobes）：肩の唇の稜（評価器 candA4_fit.band_curves と同じ読み）の像の y を、原画の帯の上の縁
    （candA4_band_targets.json の top_raw）へ近づける：差（px）を稜のまわりの列の高さの修正（m）へ戻し、c 方向に σ 0.35 m でならして 6 回。
  D 変位のならし（disp_smooth）：土台からの変位を c 方向に σ 0.5 m でならす（奥の 0.2 m 間隔の行の、行をまたぐ折れを消す）。
試して採らなかった段（設計に書けば働く）：ramp（頂の線を原画の頂の奥で上げる → 後ろから見て二つの山と谷）、sharpen＋refit_outline
（頂を締めて原画の左の輪郭を当て直す → R6 と頂の弦が悪化）、graft_far・graft_patches（第1回の BACK-FIRST の行を継ぐ）、widen_tail、tail_round。
輪郭を作る点（78・130・131 は列 79〜107、132 は c −3〜+1.4 の列 101〜193、72 は唇先 列 195〜208 と c≈6 の列 342）は動かさない。
格子 400×240、目印の列、UV、行の c は変えない。参照モデルは読まない（F13-1）。
usage: py -3.10 r2_build.py <out_prefix> [design.json]
"""
import os
import sys
import json
import time
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_common as R  # noqa: E402
for _p in (os.path.join(R.REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(R.REPO, "Tools", "PaintingTruth"), os.path.join(R.REPO, "Tools", "GWWaveGen")):
    if _p not in sys.path:
        sys.path.append(_p)
KC = R.KC

DEFAULT = {
    "JK": 78,                      # 背の作り直しの上端の列（この列から上の頂・唇は変えない）
    "back_c": [-44.0, 13.6],       # 背を作り直す行の範囲
    "back_theta_deg": 56.0,        # 背の平均の傾き（足から列 JK まで）
    "back_alpha": 0.40,            # 足の側の水平の接線の長さ（L の割合）：凹みの強さ
    "back_beta": 0.30,             # 列 JK の側の接線の長さ（L の割合）
    "wall_min_m": 1.8,             # 背と管の内側の水平の壁の厚さの下限
    "L_sigma_m": 2.5,              # 背の長さを c 方向にならす σ
    "tube": True,
    "tube_c": [-42.0, -2.8],       # 管を前へずらす行の範囲（右端は tube_fade_m で 0 へ）
    "tube_fade_m": 1.8,
    "tube_a_off": 0.8,             # 目標：管の角（列 314）を頂の a + tube_a_off まで
    "tube_cols": [228, 300, 324, 378],   # ずらしの重み φ(j)：228 で 0 → 300 で 1 … 324 で 1 → 378 で 0
    "tube_sigma_m": 1.5,
    "tail_round": {"c_max": -22.0, "sigma_m": 0.9, "win_m": 3.0, "iters": 3},
}


def phi_cols(nu, cols):
    j = np.arange(nu, dtype=float)
    j0, j1, j2, j3 = cols
    return R.ss((j - j0) / (j1 - j0)) * (1 - R.ss((j - j2) / (j3 - j2)))


def seg_selfx(a, y, j0=0, j1=None, skip=2):
    """断面の折れ線の自己交差の数（全ての線分の組）。"""
    P = np.c_[a, y][j0:j1]
    p = P[:-1]; q = P[1:]
    A1 = p[:, None, :]; A2 = q[:, None, :]; B1 = p[None, :, :]; B2 = q[None, :, :]

    def cross(o, a_, b_):
        return (a_[..., 0] - o[..., 0]) * (b_[..., 1] - o[..., 1]) - (a_[..., 1] - o[..., 1]) * (b_[..., 0] - o[..., 0])
    d1 = cross(A1, A2, B1); d2 = cross(A1, A2, B2); d3 = cross(B1, B2, A1); d4 = cross(B1, B2, A2)
    X = (d1 * d2 < 0) & (d3 * d4 < 0)
    ii, kk = np.nonzero(X)
    m = np.abs(ii - kk) > skip
    return int(m.sum() // 2)


class Build:
    def __init__(self, design=None, base=None):
        self.d = json.loads(json.dumps(DEFAULT))
        if design:
            self.d.update(design)
        self.c, self.A0, self.Y0 = R.load_rows(base or R.BASE_ROWS)
        self.nv, self.nu = self.A0.shape
        self.G = R.keepout_grids(self.c, 3, 2, cache=os.path.join(R.OUT, "cache", "keepout_d3.npz"))
        self.base_fill = [R.section_fill(self.A0[i], self.Y0[i]) & self.G[i] for i in range(self.nv)]
        self.log = []
        self.L = {}

    def new_spill(self, i, a, y, exact=False):
        if exact:
            if not hasattr(self, "G0"):
                self.G0 = R.keepout_grids(self.c, 0, 2, cache=os.path.join(R.OUT, "cache", "keepout_d0.npz"))
                self.base_fill0 = [R.section_fill(self.A0[k], self.Y0[k]) & self.G0[k] for k in range(self.nv)]
            f = R.section_fill(a, y) & self.G0[i]
            return int((f & ~self.base_fill0[i]).sum())
        f = R.section_fill(a, y) & self.G[i]
        return int((f & ~self.base_fill[i]).sum())

    # ------------------------------------------------------------ T
    def tube(self, A, Y):
        d = self.d
        c = self.c
        ph = phi_cols(self.nu, d["tube_cols"])
        c0, c1 = d["tube_c"]
        wr = R.ss((c - c0) / 2.0) * R.ss((c1 - c) / d["tube_fade_m"])
        jt = Y.argmax(1)
        atop = A[np.arange(self.nv), jt]
        dtar = np.maximum(0.0, atop + d["tube_a_off"] - A[:, 314])
        dok = np.zeros(self.nv)
        for i in np.nonzero(wr > 1e-3)[0]:
            if Y[i].max() < 1.0 or dtar[i] <= 0.05:
                continue
            lo, hi = 0.0, dtar[i]
            sp_ref = self.new_spill(i, A[i], Y[i])
            for _ in range(10):
                mid = 0.5 * (lo + hi)
                a2 = A[i] + mid * ph
                ok = self.new_spill(i, a2, Y[i]) <= sp_ref and seg_selfx(a2, Y[i], 150, 395) == 0
                if ok:
                    lo = mid
                else:
                    hi = mid
            dok[i] = lo
        ds = dok.copy()
        for _ in range(4):
            ds = np.minimum(R.csmooth(c, ds, d["tube_sigma_m"]), dok)
        ds = R.csmooth(c, ds, 0.6)
        ds = np.minimum(ds, dok)
        ds *= wr
        A = A + ds[:, None] * ph[None, :]
        self.tube_shift = ds
        self.log.append({"tube_shift_m": {"%.1f" % c[i]: round(float(ds[i]), 2) for i in range(0, self.nv, 6) if ds[i] > 0.01},
                         "tube_target_max": round(float(dtar[wr > 0.5].max()), 2)})
        return A, Y

    # ------------------------------------------------------------ B
    def bez_back(self, a_f, pk, tk, L, al, be, n):
        tt = np.linspace(0, 1, 600)
        P0 = np.array([a_f, 0.0]); P1 = np.array([a_f + al * L, 0.0]); P3 = pk; P2 = pk - be * L * tk
        B = ((1 - tt)[:, None] ** 3 * P0 + 3 * ((1 - tt) ** 2 * tt)[:, None] * P1 + 3 * ((1 - tt) * tt ** 2)[:, None] * P2
             + (tt ** 3)[:, None] * P3)
        s = R.arclen(B[:, 0], B[:, 1])
        su = np.linspace(0, s[-1], n)
        return np.interp(su, s, B[:, 0]), np.interp(su, s, B[:, 1]), B

    @staticmethod
    def wall_ok(B, a_in, y_in, wmin):
        """背の曲線 B が、管の内側の点 (a_in, y_in) より、同じ高さで wmin 以上後ろにあるか。"""
        if len(a_in) == 0:
            return True
        by = B[:, 1]; ba = B[:, 0]
        # B は a について単調（呼び出し側で確かめる）なので、高さ → a は、y が単調でない所も含めて全交点の最も前をとる
        for a0, y0 in zip(a_in, y_in):
            if y0 <= 0.3 or y0 >= by.max():
                continue
            k = np.nonzero((by[:-1] - y0) * (by[1:] - y0) <= 0)[0]
            if len(k) == 0:
                continue
            den = by[k + 1] - by[k]
            den = np.where(np.abs(den) < 1e-9, 1e-9, den)
            t = (y0 - by[k]) / den
            ab = ba[k] + t * (ba[k + 1] - ba[k])
            if ab.max() > a0 - wmin:
                return False
        return True

    @staticmethod
    def wall_min_of(B, a_in, y_in):
        by = B[:, 1]; ba = B[:, 0]; w = np.inf
        for a0, y0 in zip(a_in, y_in):
            if y0 <= 0.3 or y0 >= by.max():
                continue
            k = np.nonzero((by[:-1] - y0) * (by[1:] - y0) <= 0)[0]
            if len(k) == 0:
                continue
            den = by[k + 1] - by[k]
            den = np.where(np.abs(den) < 1e-9, 1e-9, den)
            t = (y0 - by[k]) / den
            ab = ba[k] + t * (ba[k + 1] - ba[k])
            w = min(w, a0 - ab.max())
        return float(w)

    def back(self, A, Y):
        d = self.d
        self.row_wall = {}
        c = self.c
        JK = int(d["JK"])
        c0, c1 = d["back_c"]
        wr = R.ss((c - c0) / 2.0) * R.ss((c1 - c) / float(d.get("back_fade_hi_m", 1.0)))
        th = math.radians(d["back_theta_deg"])
        al, be = d["back_alpha"], d["back_beta"]
        L_rule = np.maximum(Y[:, JK], 0.0) / math.tan(th)
        L_req = np.zeros(self.nv)
        tks = np.zeros((self.nv, 2))
        for i in range(self.nv):
            if Y[i, JK] < 0.8:
                continue
            tk = np.array([A[i, JK + 1] - A[i, JK - 1], Y[i, JK + 1] - Y[i, JK - 1]])
            tk /= max(np.linalg.norm(tk), 1e-9)
            if tk[0] < 0.05:
                tk = np.array([0.05, 1.0]) / math.hypot(0.05, 1.0)
            tks[i] = tk
            pk = np.array([A[i, JK], Y[i, JK]])
            jj = np.arange(JK + 60, 379)
            a_in, y_in = A[i, jj], Y[i, jj]
            m = y_in < Y[i, JK] - 0.2
            a_in, y_in = a_in[m], y_in[m]
            # 元の背の壁の厚さ（背の点と同じ高さの内側の点との水平の距離の最小）。元が薄い行は元の厚さの 0.9 倍までを許す
            B0 = np.c_[A[i, 18:JK + 1], Y[i, 18:JK + 1]]
            wmin = d["wall_min_m"]
            w0 = self.wall_min_of(B0, a_in, y_in)
            if w0 < wmin:
                wmin = max(0.9 * w0, 0.3)
            L = 0.3 * max(Y[i, JK], 0.5)
            found = False
            for _ in range(80):
                _, _, B = self.bez_back(pk[0] - L, pk, tk, L, al, be, JK - 18 + 1)
                if np.all(np.diff(B[:, 0]) > -1e-9) and self.wall_ok(B, a_in, y_in, wmin):
                    found = True
                    break
                L += 0.3
            L_req[i] = L if found else np.nan
            self.row_wall[i] = [w0, wmin]
        L_old = A[:, JK] - A[:, 18]
        fail = ~np.isfinite(L_req) & (Y[:, JK] >= 0.8)
        self.back_fail = fail
        L_req = np.where(np.isfinite(L_req), L_req, L_old)
        # 奥の行（c > far_c0）は元の背より長くしない（奥の後ろへ引かれた部分を太らせない）
        f0, f1 = d.get("far_thin_c", [-1.0, 3.0])
        wf = R.ss((c - f0) / (f1 - f0))
        far_mode = d.get("far_L", "min")
        L_far = np.minimum(L_rule, L_old) if far_mode == "min" else L_old
        L_tgt = (1 - wf) * L_rule + wf * L_far
        Lt = np.maximum(L_tgt, L_req)
        Lt = np.where(fail, L_old, Lt)
        Ls = Lt.copy()
        for _ in range(3):
            Ls = R.csmooth(c, Ls, d["L_sigma_m"])
            Ls = Ls + np.logaddexp(0.0, 3.0 * (L_req - Ls)) / 3.0     # なめらかな max(Ls, L_req)
        A = A.copy(); Y = Y.copy()
        for i in np.nonzero(wr > 1e-3)[0]:
            if Y[i, JK] < 0.8 or fail[i]:
                continue
            pk = np.array([A[i, JK], Y[i, JK]])
            an, yn, B = self.bez_back(pk[0] - Ls[i], pk, tks[i], Ls[i], al, be, JK - 18 + 1)
            w = wr[i]
            A[i, 18:JK + 1] = w * an + (1 - w) * A[i, 18:JK + 1]
            Y[i, 18:JK + 1] = w * yn + (1 - w) * Y[i, 18:JK + 1]
            a_end = self.A0[i, 0]
            A[i, 0:19] = a_end + (A[i, 18] - a_end) * np.linspace(0, 1, 19)
            Y[i, 0:18] = 0.0
        # 作り直した背（列 18..JK）を行の方向にならす（行ごとの接線の揺れ・壁の下限の切り替わりが行をまたぐ折れになるのを防ぐ）
        sgb = float(d.get("back_row_sigma_m", 0.9))
        if sgb > 0:
            rows = np.nonzero(wr > 1e-3)[0]
            dcc = np.gradient(c)
            Wb = np.exp(-0.5 * ((c[rows][:, None] - c[rows][None, :]) / sgb) ** 2) * dcc[rows][None, :]
            Wb /= Wb.sum(1, keepdims=True)
            cols = np.arange(18, JK + 1)
            jw = 1 - R.ss((cols - (JK - 8)) / 8.0)      # 列 JK の近く（頂の側）は元のまま
            for arr in (A, Y):
                sm = Wb @ arr[np.ix_(rows, cols)]
                arr[np.ix_(rows, cols)] = jw[None, :] * sm + (1 - jw[None, :]) * arr[np.ix_(rows, cols)]
            for i in rows:
                a_end = self.A0[i, 0]
                A[i, 0:19] = a_end + (A[i, 18] - a_end) * np.linspace(0, 1, 19)
                Y[i, 0:19] = 0.0
        # 行ごとの確かめ：背と管が交わる行は、交わらなくなるまで元の背（列 0..JK）へ戻す（割合を c 方向にならす）
        fb = np.zeros(self.nv)
        for i in np.nonzero(wr > 1e-3)[0]:
            if seg_selfx(A[i], Y[i], 0, None) == 0:
                continue
            for f in (0.25, 0.5, 0.75, 1.0):
                a1 = A[i].copy(); y1 = Y[i].copy()
                a1[:JK + 1] = (1 - f) * A[i, :JK + 1] + f * self.A0[i, :JK + 1]
                y1[:JK + 1] = (1 - f) * Y[i, :JK + 1] + f * self.Y0[i, :JK + 1]
                if seg_selfx(a1, y1, 0, None) == 0:
                    break
            fb[i] = f
        if fb.any():
            fbs = np.maximum(R.csmooth(c, fb, 0.5), fb)
            for i in np.nonzero(fbs > 1e-3)[0]:
                A[i, :JK + 1] = (1 - fbs[i]) * A[i, :JK + 1] + fbs[i] * self.A0[i, :JK + 1]
                Y[i, :JK + 1] = (1 - fbs[i]) * Y[i, :JK + 1] + fbs[i] * self.Y0[i, :JK + 1]
            self.log.append({"back_revert_rows": {"%.1f" % c[i]: round(float(fbs[i]), 2) for i in np.nonzero(fbs > 1e-3)[0]}})
        self.L = {"L_old": L_old, "L_rule": L_rule, "L_req": L_req, "L_final": Ls}
        self.log.append({"back_fail_rows": [round(float(x), 1) for x in c[fail]]})
        self.log.append({"back_L_old_req_final": {"%.1f" % c[i]: [round(float(L_old[i]), 1), round(float(L_req[i]), 1), round(float(Ls[i]), 1)]
                                                  for i in range(0, self.nv, 8) if Y[i, JK] > 0.8}})
        return A, Y

    # ------------------------------------------------------------ N
    def tail_round(self, A, Y):
        g = self.d["tail_round"]
        c = self.c
        cmax = g["c_max"]; sig = g["sigma_m"]; win = g["win_m"]; its = int(g["iters"])
        A = A.copy(); Y = Y.copy()
        for r in np.nonzero(c <= cmax + 2.0)[0]:
            wr = float(R.ss((cmax + 2.0 - c[r]) / 2.0))
            if wr <= 0 or Y[r].max() < 0.5:
                continue
            a, y = A[r].copy(), Y[r].copy()
            for _ in range(its):
                sL = R.arclen(a, y)
                j = int(np.argmax(y)); s0 = sL[j]
                idx = np.nonzero(np.abs(sL - s0) <= win + 3 * sig)[0]
                K = np.exp(-0.5 * ((sL[idx][:, None] - sL[idx][None, :]) / sig) ** 2)
                K /= K.sum(1, keepdims=True)
                a_s, y_s = K @ a[idx], K @ y[idx]
                w = np.exp(-0.5 * ((sL[idx] - s0) / win) ** 2) * wr
                a[idx] = w * a_s + (1 - w) * a[idx]; y[idx] = w * y_s + (1 - w) * y[idx]
            A[r], Y[r] = a, y
        return A, Y

    # ------------------------------------------------------------ R
    def ok_point(self, i, a, y):
        ia = int(round((a - R.GA0) / R.GRES)); iy = int(round((y - R.GY0) / R.GRES))
        if ia < 0 or ia >= R.NA or iy < 0 or iy >= R.NY:
            return True
        return not self.G[i][iy, ia]

    def ramp(self, A, Y):
        """頂の線を原画の頂（c ≈ −1.6）の奥で上げ続ける（後ろから見て、奥へ上る稜 → 奥の端で落ちる）。
        目標の頂 (a_t(c), H_t(c)) は節の値を PCHIP でつなぐ。上げ幅は、行ごとに頂の点が空の射線の禁止域に入らない高さまで。
        断面は、頂の点を (Δa, ΔH) 動かし、背の側は高さに応じて（下の背は後で作り直す）、唇の側は列 j_end で 0 になるように動かす
        （132 を作る行 c ≤ 1.4 は唇（列 ≥ 101）を動かさない。奥の行は唇先（列 ≥ 190）を動かさない）。"""
        from scipy.interpolate import PchipInterpolator
        g = self.d["ramp"]
        c = self.c
        kc = np.array(g["c"], float)
        jt = Y.argmax(1); rr = np.arange(self.nv)
        ao, Ho = A[rr, jt].copy(), Y[rr, jt].copy()
        lo, hi = kc[0], kc[-1]
        kH = np.array([np.interp(x, c, Ho) if v is None else v for x, v in zip(kc, g["H"])], float)
        ka = np.array([np.interp(x, c, ao) if v is None else v for x, v in zip(kc, g["a"])], float)
        Ht = PchipInterpolator(kc, kH)(np.clip(c, lo, hi)); at = PchipInterpolator(kc, ka)(np.clip(c, lo, hi))
        wr = R.ss((c - lo) / 0.8) * R.ss((hi - c) / 1.0)
        dH = (Ht - Ho) * wr; da = (at - ao) * wr
        # 頭打ち：新しい頂の点とその上 margin が禁止域に入らない
        mg = float(g.get("margin_m", 0.3))
        for i in np.nonzero(wr > 1e-3)[0]:
            if dH[i] <= 0:
                continue
            k = 1.0
            for _ in range(30):
                a1 = ao[i] + da[i]; y1 = Ho[i] + k * dH[i]
                if self.ok_point(i, a1, y1 + mg) and self.ok_point(i, a1 + 0.5, y1 + mg) and self.ok_point(i, a1 - 0.5, y1 + mg):
                    break
                k -= 0.04
            dH[i] = max(k, 0.0) * dH[i]
        dH0 = dH.copy()
        for _ in range(3):
            dH = np.minimum(R.csmooth(c, dH, float(g.get("sigma_m", 0.8))), np.where(dH0 > 0, dH0, dH))
        # 列の重み
        j = np.arange(self.nu, dtype=float)
        je_lo, je_hi = float(g.get("j_end_132", 101)), float(g.get("j_end_far", 185))
        c132 = float(g.get("c132", 1.4))
        te = R.ss((c - c132) / 1.0)
        if g.get("j_end_knots"):
            kk_c = np.array(g["j_end_knots"][0], float); kk_j = np.array(g["j_end_knots"][1], float)
            je_row = np.interp(c, kk_c, kk_j)
        else:
            je_row = je_lo + (je_hi - je_lo) * te
        W = np.zeros((self.nv, self.nu))
        for i in np.nonzero(wr > 1e-3)[0]:
            je = je_row[i]
            Hr = max(Ho[i], 0.5)
            wb = R.ss((Y[i] / Hr - 0.3) / 0.7) * (j <= jt[i])
            u = (j - jt[i]) / max(je - jt[i], 1.0)
            wl = (1 - R.ss(u)) * (j > jt[i])
            W[i] = wb + wl
        # 行ごとに、空の禁止域に新しくかからない最大の割合 k（二分探索）→ c 方向のなめらかな下限
        kk = np.ones(self.nv)
        ex = bool(g.get("exact_keepout", True))
        for i in np.nonzero(wr > 1e-3)[0]:
            if self.new_spill(i, A[i] + da[i] * W[i], Y[i] + dH[i] * W[i], ex) == 0:
                continue
            lo_, hi_ = 0.0, 1.0
            for _ in range(9):
                m_ = 0.5 * (lo_ + hi_)
                if self.new_spill(i, A[i] + m_ * da[i] * W[i], Y[i] + m_ * dH[i] * W[i], ex) == 0:
                    lo_ = m_
                else:
                    hi_ = m_
            kk[i] = lo_
        k0 = kk.copy()
        for _ in range(4):
            kk = np.minimum(R.csmooth(c, kk, 0.6), k0)
        dH = dH * kk; da = da * kk
        A = A + da[:, None] * W; Y = Y + dH[:, None] * W
        self.ramp_d = {"dH": dH, "da": da, "Ht": Ht, "at": at}
        self.log.append({"ramp_dH": {"%.1f" % c[i]: [round(float(dH[i]), 2), round(float(da[i]), 2)] for i in range(0, self.nv, 4) if abs(dH[i]) > 0.01 or abs(da[i]) > 0.01}})
        return A, Y

    # ------------------------------------------------------------ S（頂を締める）＋ 原画の左の輪郭の当て直し
    def sharpen(self, A, Y):
        """頂のまわりを締める：頂の点（各行の最高点）からの水平の距離を、高さ Yn = y/H に応じて縮める
        u' = u·(1 − k·S((Yn − y_lo)/(1 − y_lo)))。背の側（列 40..頂）は k_back、唇の側（頂..列 j_lip_end）は k_lip
        （唇の側は列 j_lip_end へ向かって 0 に戻す。132 を作る行 c −3.5〜+1.9 は唇の側を動かさない）。"""
        g = self.d["sharpen"]
        c = self.c
        kb, kl, ylo = float(g.get("k_back", 0.45)), float(g.get("k_lip", 0.35)), float(g.get("y_lo", 0.62))
        c0, c1 = g.get("c", [-40.0, 13.2])
        wr = R.ss((c - c0) / 2.0) * R.ss((c1 - c) / 1.5)
        n0, n1 = g.get("no_lip_c", [-3.5, 1.9])
        wl_r = 1 - R.ss((c - (n0 - 1.0)) / 1.0) * (1 - R.ss((c - n1) / 1.0))
        jle = float(g.get("j_lip_end", 125))
        A = A.copy(); Y = Y.copy()
        j = np.arange(self.nu, dtype=float)
        for i in np.nonzero(wr > 1e-3)[0]:
            jt = int(np.argmax(Y[i])); H = max(Y[i, jt], 0.5); a0 = A[i, jt]
            if H < 1.0:
                continue
            Yn = Y[i] / H
            S = R.ss((Yn - ylo) / (1 - ylo))
            mb = (j >= 30) & (j < jt)
            A[i, mb] = a0 - (a0 - A[i, mb]) * (1 - kb * wr[i] * S[mb])
            ml = (j > jt) & (j < jle)
            fade = 1 - R.ss((j[ml] - jt) / max(jle - jt, 1.0))
            A[i, ml] = a0 + (A[i, ml] - a0) * (1 - kl * wr[i] * wl_r[i] * S[ml] * fade)
        return A, Y

    def refit_outline(self, A, Y, iters=8, gain=0.8):
        """原画視点の左の輪郭（x 157〜766 の上側の包絡）を、土台 P28R1 の包絡へ戻す（78・130・131 は P28R1 で合格）。
        包絡の差（px）を、その x の包絡を作る行の高さの修正（m）へ戻し、c 方向にならして、頂のまわりの列（40〜130）だけ上下する。"""
        import rays_build as RB
        c = self.c
        rows = np.nonzero((c >= -24) & (c <= 3.0))[0]
        y_tgt, _, _ = RB.upper_envelope(c, self.A0, self.Y0, 157, 766, rows=rows)
        j = np.arange(self.nu, dtype=float)
        wj = R.ss((j - 40) / 25.0) * (1 - R.ss((j - 112) / 22.0))
        hist = []
        for it in range(iters):
            ey, er, eX = RB.upper_envelope(c, A, Y, 157, 766, rows=rows)
            m = np.isfinite(ey) & np.isfinite(y_tgt) & np.isfinite(er)
            err = ey - y_tgt          # > 0：像が下（低い）→ 上げる
            hist.append([round(float(np.nanmax(np.abs(err[m]))), 2), round(float(np.nanpercentile(np.abs(err[m]), 95)), 2)])
            # px → m（その点の奥行き）
            q = R.KC.project_unity(eX[m])
            z = q[:, 2]
            pxpm = (KC.CAM_H / 2.0) / math.tan(math.radians(KC.CAM_VFOV) / 2.0) / np.maximum(z, 1.0)
            dy_pt = err[m] / pxpm
            rr = np.round(er[m]).astype(int)
            acc = np.zeros(self.nv); cnt = np.zeros(self.nv)
            np.add.at(acc, rr, dy_pt); np.add.at(cnt, rr, 1.0)
            has = cnt > 0
            dy = np.zeros(self.nv); dy[has] = acc[has] / cnt[has]
            # 行の間を埋めて、ならす
            dyi = np.interp(c, c[has], dy[has]) if has.sum() > 2 else dy
            band = (c >= c[has].min() - 1.0) & (c <= c[has].max() + 1.0) if has.any() else np.zeros(self.nv, bool)
            dyi = np.where(band, dyi, 0.0)
            dyi = R.csmooth(c, dyi, 0.5)
            Y = Y + gain * dyi[:, None] * wj[None, :] * (Y > 0.05)
        ey, er, eX = RB.upper_envelope(c, A, Y, 157, 766, rows=rows)
        m = np.isfinite(ey) & np.isfinite(y_tgt)
        err = ey - y_tgt
        hist.append([round(float(np.nanmax(np.abs(err[m]))), 2), round(float(np.nanpercentile(np.abs(err[m]), 95)), 2)])
        self.log.append({"refit_outline_err_max_p95_px": hist})
        return A, Y

    # ------------------------------------------------------------ M（見えない所のならし：評審の R6 のこぶ）
    def smooth_patch(self, A, Y, spec):
        """行 c ∈ [c0, c1]、列 [j0, j1] の断面の点 (A, Y) を、c 方向 σ_c（m）と列の方向 σ_j（列）のガウスでならし、
        端は重みで元へ戻す。空の射線の禁止域（3 px 広げたもの）に新しくかかる行は、その行だけならしの割合を下げる。"""
        c = self.c
        c0, c1 = spec["c"]; j0, j1 = spec["cols"]
        sc, sj = float(spec.get("sigma_c_m", 1.5)), float(spec.get("sigma_j", 4.0))
        fc, fj = float(spec.get("fade_c_m", 1.5)), float(spec.get("fade_j", 12.0))
        rows = np.nonzero((c >= c0 - 3 * sc) & (c <= c1 + 3 * sc))[0]
        dc = np.gradient(c)
        Wc = np.exp(-0.5 * ((c[rows][:, None] - c[rows][None, :]) / sc) ** 2) * dc[rows][None, :]
        Wc /= Wc.sum(1, keepdims=True)
        jj = np.arange(self.nu)
        r = int(math.ceil(3 * sj)); kj = np.exp(-0.5 * (np.arange(-r, r + 1) / sj) ** 2); kj /= kj.sum()

        def conv_j(M):
            P = np.pad(M, ((0, 0), (r, r)), mode="edge")
            out = np.zeros_like(M)
            for k, w in enumerate(kj):
                out += w * P[:, k:k + M.shape[1]]
            return out
        if spec.get("relative"):
            # 頂（列 jr）の点に対する相対の形をならし、頂の点は元の位置に戻す（奥の行は頂が c とともに後ろへ流れるので、
            # 絶対の座標でならすと、ならした列とならさない列の境に折れができる）
            jr = int(spec.get("j_ref", 90))
            ar, yr = A[rows, jr][:, None], Y[rows, jr][:, None]
            As = conv_j(Wc @ (A[rows] - ar)) + ar; Ys = conv_j(Wc @ (Y[rows] - yr)) + yr
        else:
            As = conv_j(Wc @ A[rows]); Ys = conv_j(Wc @ Y[rows])
        wr = R.ss((c[rows] - c0) / fc) * R.ss((c1 - c[rows]) / fc)
        wj = R.ss((jj - j0) / fj) * R.ss((j1 - jj) / fj)
        Wm = wr[:, None] * wj[None, :]
        A2 = A.copy(); Y2 = Y.copy()
        fk = np.zeros(len(rows))
        for k, i in enumerate(rows):
            if wr[k] <= 0:
                continue
            sp0 = self.new_spill(i, A[i], Y[i])
            for f in (1.0, 0.8, 0.6, 0.4, 0.2, 0.0):
                a1 = A[i] + f * Wm[k] * (As[k] - A[i]); y1 = Y[i] + f * Wm[k] * (Ys[k] - Y[i])
                if self.new_spill(i, a1, y1) <= sp0 and seg_selfx(a1, y1, 0, None) == 0:
                    break
            fk[k] = f
        # 行ごとの割合を c 方向のなめらかな下限にする（行ごとの跳びが行をまたぐ折れにならないように）
        f0 = fk.copy(); cr = c[rows]
        for _ in range(4):
            fk = np.minimum(R.csmooth(cr, fk, 0.8), f0)
        for k, i in enumerate(rows):
            A2[i] = A[i] + fk[k] * Wm[k] * (As[k] - A[i]); Y2[i] = Y[i] + fk[k] * Wm[k] * (Ys[k] - Y[i])
        self.log.append({"smooth_patch_%s" % spec["c"]: {"%.1f" % cr[k]: round(float(fk[k]), 2) for k in range(0, len(rows), 3) if wr[k] > 0}})
        return A2, Y2

    def widen_tail(self, A, Y):
        """手前の尾の行（原画の画面の外）の断面の上の部分を、頂の a のまわりに横へ広げる：
        a' = a_top + (a − a_top)·(1 + k·S((y/H − y0)/(1 − y0)))。頂の ±2 m の弦の角を広げる（尖った尾 → 弧）。"""
        g = self.d["widen_tail"]
        c = self.c
        k, y0, cmax, fade = float(g.get("k", 1.0)), float(g.get("y0", 0.35)), float(g.get("c_max", -25.0)), float(g.get("fade_m", 3.0))
        wr = 1 - R.ss((c - cmax) / fade)
        A = A.copy()
        for i in np.nonzero(wr > 1e-3)[0]:
            jt = int(np.argmax(Y[i])); H = Y[i, jt]
            if H < 0.4:
                continue
            S = R.ss((Y[i] / H - y0) / (1 - y0))
            A[i] = A[i, jt] + (A[i] - A[i, jt]) * (1 + k * wr[i] * S)
        return A, Y

    def tail_cols(self, A, Y):
        """手前の尾の行（c ≤ c_max）の頂のまわり（列 j0..j1）を、列の方向のガウス σ_j で数回ならす（列で決めた窓なので、
        行ごとに窓が跳ばず、行をまたぐ折れを作らない）。重みは c で c_max から fade_m かけて 0 → 1。"""
        g = self.d["tail_cols"]
        c = self.c
        j0, j1 = g.get("cols", [96, 236]); sj = float(g.get("sigma_j", 6.0)); its = int(g.get("iters", 3))
        cmax, fade = float(g.get("c_max", -24.0)), float(g.get("fade_m", 4.0))
        wr = 1 - R.ss((c - (cmax - fade)) / fade)
        r = int(math.ceil(3 * sj)); kj = np.exp(-0.5 * (np.arange(-r, r + 1) / sj) ** 2); kj /= kj.sum()
        jj = np.arange(self.nu)
        wj = R.ss((jj - j0) / 15.0) * R.ss((j1 - jj) / 15.0)
        A = A.copy(); Y = Y.copy()
        for i in np.nonzero(wr > 1e-3)[0]:
            if Y[i].max() < 0.4:
                continue
            a, y = A[i].copy(), Y[i].copy()
            for _ in range(its):
                a = a + wj * wr[i] * (np.convolve(np.pad(a, r, mode="edge"), kj, "valid") - a)
                y = y + wj * wr[i] * (np.convolve(np.pad(y, r, mode="edge"), kj, "valid") - y)
            A[i], Y[i] = a, y
        return A, Y

    def stretch_tail(self, A, Y):
        """手前の尾の行（原画の画面の外、c ≤ c0）の断面全体を、頂の a のまわりに横へ k(c) 倍に広げる（高さは変えない）。
        k(c) = 1 + k_max·S((c0 − c)/L)（c が c0 から L m で満ちる）。小さな尾の断面は幅 4 m ほどの尖った山で、頂の ±2 m の弦が
        110° を割っていた（仕上げ28 の閉じる目安「手前の尾の行が弧」）。行ごとに一様な倍率なので、格子の並びは崩れない。"""
        g = self.d["stretch_tail"]
        c = self.c
        c0, L, kmax = float(g.get("c0", -24.0)), float(g.get("L_m", 6.0)), float(g.get("k_max", 1.2))
        k = 1 + kmax * R.ss((c0 - c) / L)
        H = Y.max(1)
        k = 1 + (k - 1) * R.ss(H / 1.0)
        # 伸ばしの中心：頂の a を c 方向にならした値（最高点の列が行ごとに唇の鉤と背の側で入れ替わっても中心が跳ばない）
        jt = Y.argmax(1)
        a_top = A[np.arange(self.nv), jt]
        a0s = R.csmooth(c, a_top, 2.0)
        A = A.copy()
        y0 = g.get("y0")
        for i in np.nonzero(k > 1 + 1e-4)[0]:
            a0 = a0s[i]
            if y0 is None:
                A[i, 18:395] = a0 + (A[i, 18:395] - a0) * k[i]
            else:
                # 上の部分だけ広げる（足元の幅は変えない）：倍率 1 + (k − 1)·S((y/H − y0)/(1 − y0))
                Hh = max(float(Y[i].max()), 0.3)
                S = R.ss((Y[i, 18:395] / Hh - float(y0)) / (1 - float(y0)))
                A[i, 18:395] = a0 + (A[i, 18:395] - a0) * (1 + (k[i] - 1) * S)
            # 平らな海の列（0..18、394..399）は、格子の外周（元のまま）と新しい足の間に等分し直す
            A[i, 0:19] = A[i, 0] + (A[i, 18] - A[i, 0]) * np.linspace(0, 1, 19)
            A[i, 394:] = A[i, 394] + (A[i, -1] - A[i, 394]) * np.linspace(0, 1, self.nu - 394)
        return A, Y

    def graft(self, A, Y):
        """奥の行（c ≥ c1）を第1回の BACK-FIRST 候補 P28bf の行に置き換え、c0〜c1 でなめらかにつなぐ
        （P28bf は奥の端の頂の線を c 方向にならし、唇先だけで原画の 72 に合わせ直していて、奥の頂の R6 のこぶが小さい）。"""
        g = self.d["graft_far"]
        z = np.load(g["rows"])
        assert np.allclose(z["c"], self.c)
        Ab, Yb = z["A"].astype(float), z["Y"].astype(float)
        w = R.ss((self.c - g["c"][0]) / (g["c"][1] - g["c"][0]))
        self.graft_sha = KC.sha256(g["rows"])
        return A + w[:, None] * (Ab - A), Y + w[:, None] * (Yb - Y)

    def crest_line_smooth(self, A, Y):
        """奥の頂の線（列 jr の点の列）を c 方向にならし、その動き Δ(c) を断面の上の部分（列 j0..j3）へ同じ量だけ移す
        （列の重み：j0→j1 で 0→1、j2→j3 で 1→0。唇先の帯（列 ≥ 190）と下の背は動かない）。頂の線だけをならすので、
        ならした列とならさない列の境に折れができない。空の禁止域・断面の自己交差で行ごとに割合を下げ、c 方向になめらかにする。"""
        g = self.d["crest_line_smooth"]
        c = self.c
        c0, c1 = g["c"]; sc = float(g.get("sigma_c_m", 1.5)); fc = float(g.get("fade_c_m", 1.5))
        jr = int(g.get("j_ref", 90)); j0, j1, j2, j3 = g.get("cols", [40, 70, 150, 188])
        rows = np.nonzero((c >= c0 - 3 * sc) & (c <= c1 + 3 * sc))[0]
        dcc = np.gradient(c)
        Wc = np.exp(-0.5 * ((c[rows][:, None] - c[rows][None, :]) / sc) ** 2) * dcc[rows][None, :]
        Wc /= Wc.sum(1, keepdims=True)
        ar, yr = A[rows, jr], Y[rows, jr]
        da = (Wc @ ar - ar) * float(g.get("da_scale", 1.0)); dy = (Wc @ yr - yr) * float(g.get("dy_scale", 1.0))
        wr = R.ss((c[rows] - c0) / fc) * R.ss((c1 - c[rows]) / fc)
        jj = np.arange(self.nu, dtype=float)
        wj = R.ss((jj - j0) / max(j1 - j0, 1)) * (1 - R.ss((jj - j2) / max(j3 - j2, 1)))
        fk = np.zeros(len(rows))
        for k, i in enumerate(rows):
            if wr[k] <= 0:
                continue
            sp0 = self.new_spill(i, A[i], Y[i])
            for f in (1.0, 0.8, 0.6, 0.4, 0.2, 0.0):
                a1 = A[i] + f * wr[k] * da[k] * wj; y1 = Y[i] + f * wr[k] * dy[k] * wj
                if self.new_spill(i, a1, y1) <= sp0 and seg_selfx(a1, y1, 0, None) == 0:
                    break
            fk[k] = f
        f0 = fk.copy(); cr = c[rows]
        for _ in range(4):
            fk = np.minimum(R.csmooth(cr, fk, 0.8), f0)
        A = A.copy(); Y = Y.copy()
        for k, i in enumerate(rows):
            A[i] = A[i] + fk[k] * wr[k] * da[k] * wj; Y[i] = Y[i] + fk[k] * wr[k] * dy[k] * wj
        self.log.append({"crest_line_smooth": {"%.1f" % cr[k]: [round(float(fk[k] * wr[k] * da[k]), 2), round(float(fk[k] * wr[k] * dy[k]), 2)]
                                               for k in range(0, len(rows), 3) if wr[k] > 0}})
        return A, Y

    def graft_patch(self, A, Y, g):
        """行 c ∈ [c0, c1]・列 [j0, j1] を別の候補の行の値へ置き換える（端は fade でなめらかに）。"""
        z = np.load(g["rows"])
        assert np.allclose(z["c"], self.c)
        Ab, Yb = z["A"].astype(float), z["Y"].astype(float)
        c = self.c; jj = np.arange(self.nu)
        c0, c1 = g["c"]; j0, j1 = g["cols"]; fc, fj = float(g.get("fade_c_m", 1.5)), float(g.get("fade_j", 10))
        W = (R.ss((c - c0) / fc) * R.ss((c1 - c) / fc))[:, None] * (R.ss((jj - j0) / fj) * R.ss((j1 - jj) / fj))[None, :]
        return A + W * (Ab - A), Y + W * (Yb - Y)

    def far_wall(self, A, Y):
        """奥の端の行（c ∈ [c0, c1]）の背（列 18..j1）を δ m 後ろへ出す（管の角と背がほぼ接していて（壁 ≈ 0 m）、
        頂の線をならすと断面が自己交差する行。壁を δ だけ厚くして、ならしを通す）。"""
        g = self.d["far_wall"]
        c = self.c
        c0, c1 = g["c"]; dl = float(g.get("delta_m", 0.6)); j1 = int(g.get("j1", 76)); fc = float(g.get("fade_c_m", 1.0))
        wr = R.ss((c - c0) / fc) * R.ss((c1 - c) / fc)
        jj = np.arange(self.nu, dtype=float)
        wj = (1 - R.ss((jj - (j1 - 18)) / 18.0)) * (jj <= j1)
        A = A.copy()
        for i in np.nonzero(wr > 1e-3)[0]:
            A[i] = A[i] - dl * wr[i] * wj
            a_end = self.A0[i, 0]
            A[i, 0:19] = a_end + (A[i, 18] - a_end) * np.linspace(0, 1, 19)
        return A, Y

    def col_smooth(self, A, Y, g):
        """行 c ∈ [c0, c1]（端は fade_c）の列 [j0, j1]（端 15 列で 0 へ）を、列の方向のガウス σ_j で iters 回ならす
        （頂のまわりを弧にする。行ごとの窓が跳ばないよう、列で決めた窓を使う）。禁止域・自己交差の行は割合を下げる。"""
        c = self.c
        c0, c1 = g["c"]; j0, j1 = g["cols"]; sj = float(g.get("sigma_j", 5.0)); its = int(g.get("iters", 2)); fc = float(g.get("fade_c_m", 1.0))
        wr = R.ss((c - c0) / fc) * R.ss((c1 - c) / fc)
        r = int(math.ceil(3 * sj)); kj = np.exp(-0.5 * (np.arange(-r, r + 1) / sj) ** 2); kj /= kj.sum()
        jj = np.arange(self.nu)
        wj = R.ss((jj - j0) / 15.0) * R.ss((j1 - jj) / 15.0)
        A = A.copy(); Y = Y.copy()
        for i in np.nonzero(wr > 1e-3)[0]:
            a, y = A[i].copy(), Y[i].copy()
            for _ in range(its):
                a = a + wj * (np.convolve(np.pad(a, r, mode="edge"), kj, "valid") - a)
                y = y + wj * (np.convolve(np.pad(y, r, mode="edge"), kj, "valid") - y)
            sp0 = self.new_spill(i, A[i], Y[i])
            for f in (1.0, 0.7, 0.4, 0.0):
                a1 = A[i] + f * wr[i] * (a - A[i]); y1 = Y[i] + f * wr[i] * (y - Y[i])
                if self.new_spill(i, a1, y1) <= sp0 and seg_selfx(a1, y1, 0, None) == 0:
                    break
            A[i], Y[i] = a1, y1
        return A, Y

    def b_lobes(self, A, Y):
        """b区域（左肩の第二の波頭）の帯の上の縁を、原画の帯の上の縁（candA4_band_targets.json の top_raw：3 つの房と
        2 つの切れ込み）へ近づける。各肩の行について、評価器と同じ読み（candA4_fit.band_curves：唇の鎖の谷の後の像の最も上の点
        ＝稜）の点の像の y と、その x の目標の y の差（px）を、その行の稜のまわりの列（列の方向のガウス σ_j）の高さの修正（m）へ
        戻し、c 方向に σ_c でならして、数回くり返す。唇先（列 ≥ 200 − 4）と頂（列 ≤ j_min）は動かさない。"""
        import candA_common as CC
        import candA4_fit as F4
        g = self.d["b_lobes"]
        c = self.c
        V1, tgt, fr = CC.painting_frame()

        class _Ctx:
            pass
        cx = _Ctx(); cx.fr = fr
        bt = json.load(open(os.path.join(R.REPO, "Tools", "GWWaveGen", "kstar3", "candA4_band_targets.json"), encoding="utf-8"))
        T = np.array(bt[g.get("target", "top_raw")], float)
        rows = np.nonzero((c > -18.5) & (c < -3.5))[0]
        jmin, jmax = int(g.get("j_min", 120)), int(g.get("j_max", 196))
        sj, sc, gain = float(g.get("sigma_j", 9.0)), float(g.get("sigma_c_m", 0.35)), float(g.get("gain", 0.7))
        cap = float(g.get("cap_m", 1.2))
        jj = np.arange(self.nu, dtype=float)
        hist = []
        A = A.copy(); Y = Y.copy()
        total = np.zeros(self.nv)
        for it in range(int(g.get("iters", 6))):
            X = fr.world(c, A, Y)
            top, _ = F4.band_curves(cx, c, A, Y, X, rows)
            err = np.full(len(rows), np.nan); kcol = np.full(len(rows), -1)
            for k, r in enumerate(rows):
                if not np.isfinite(top[k, 0]):
                    continue
                if top[k, 0] < T[0, 0] - 3 or top[k, 0] > T[-1, 0] + 3:
                    continue
                yt = np.interp(top[k, 0], T[:, 0], T[:, 1])
                err[k] = top[k, 1] - yt          # > 0：稜の像が目標より下 → 上げる
                P = fr.cam.project(X[r, 88:216].reshape(-1, 3))[:, :2]
                kcol[k] = 88 + int(np.argmin(np.hypot(P[:, 0] - top[k, 0], P[:, 1] - top[k, 1])))
            m = np.isfinite(err)
            hist.append([round(float(np.nanmedian(np.abs(err))), 1), round(float(np.nanpercentile(np.abs(err), 90)), 1), round(float(np.nanmax(np.abs(err))), 1), int(m.sum())])
            if m.sum() < 3:
                break
            z = np.array([fr.cam.project(X[rows[k], kcol[k]][None])[0, 2] if m[k] else 60.0 for k in range(len(rows))])
            pxpm = (KC.CAM_H / 2.0) / math.tan(math.radians(KC.CAM_VFOV) / 2.0) / np.maximum(z, 1.0)
            dyr = np.where(m, err / pxpm, 0.0)
            full = np.zeros(self.nv); full[rows] = dyr
            has = np.zeros(self.nv, bool); has[rows[m]] = True
            fi = np.interp(c, c[has], full[has]) if has.sum() > 2 else full
            band = (c >= c[has].min() - 0.8) & (c <= c[has].max() + 0.8)
            fi = np.where(band, fi, 0.0)
            fi = R.csmooth(c, fi, sc) * gain
            kc = np.interp(c, c[rows[m]], kcol[m].astype(float))
            for i in np.nonzero(np.abs(fi) > 1e-4)[0]:
                d_ = float(np.clip(fi[i], -cap - total[i], cap - total[i]))
                w = np.exp(-0.5 * ((jj - kc[i]) / sj) ** 2) * R.ss((jj - jmin) / 10.0) * R.ss((jmax - jj) / 6.0)
                y1 = Y[i] + d_ * w
                if seg_selfx(A[i], y1, 0, None) == 0:
                    Y[i] = y1; total[i] += d_
        X = fr.world(c, A, Y)
        top, _ = F4.band_curves(cx, c, A, Y, X, rows)
        r_ = F4.curve_vs_target(top, T, big=np.nan); v = np.abs(r_[np.isfinite(r_)])
        hist.append([round(float(np.median(v)), 1), round(float(np.percentile(v, 90)), 1), round(float(v.max()), 1), int(len(v))])
        self.log.append({"b_lobes_err_med_p90_max_n": hist, "b_lobes_dy_m": {"%.1f" % c[i]: round(float(total[i]), 2) for i in rows[::3]}})
        return A, Y

    def disp_smooth(self, A, Y):
        """最後に、土台（P28R1）からの変位 (ΔA, ΔY) を c 方向に σ_c でならす（行ごとの割合の跳びが、奥の 0.2 m 間隔の行で
        行をまたぐ折れ（F11）になるのを消す）。変位 0 の所（原画の輪郭を作る点など）は 0 のまま。ならした後に空の禁止域へ
        新しくかかる行・自己交差する行は、ならす前の値へ戻す。"""
        g = self.d["disp_smooth"]
        c = self.c
        sc = float(g.get("sigma_c_m", 0.5))
        dA = A - self.A0; dY = Y - self.Y0
        sA = R.csmooth(c, dA, sc); sY = R.csmooth(c, dY, sc)
        # 変位が 0 の列・行はそのまま（ならしで 0 の所へ変位をにじませない）：元の変位の大きさの重み
        mag = np.hypot(dA, dY)
        keep0 = mag < 1e-9
        A2 = self.A0 + np.where(keep0, 0.0, sA); Y2 = self.Y0 + np.where(keep0, 0.0, sY)
        back = 0
        for i in range(self.nv):
            if np.array_equal(A2[i], A[i]) and np.array_equal(Y2[i], Y[i]):
                continue
            if self.new_spill(i, A2[i], Y2[i]) > self.new_spill(i, A[i], Y[i]) or (seg_selfx(A2[i], Y2[i], 0, None) > 0 and seg_selfx(A[i], Y[i], 0, None) == 0):
                A2[i], Y2[i] = A[i], Y[i]; back += 1
        self.log.append({"disp_smooth_rows_reverted": back})
        return A2, Y2

    def far_wall_height(self, A, Y):
        """奥の端の行で、背の点のうち管の角（列 314）の高さの近く（ガウス σ_y）だけを δ m 後ろへ出す（頂の近くは動かさない）。
        奥の行では管の角と背の間の壁が 0.1 m 以下で、後ろから見ると角の形が背に写って斜めの小さな折れ目になる。"""
        g = self.d["far_wall_height"]
        c = self.c
        c0, c1 = g["c"]; dl = float(g.get("delta_m", 0.6)); sy = float(g.get("sigma_y_m", 2.0)); fc = float(g.get("fade_c_m", 1.0))
        wr = R.ss((c - c0) / fc) * R.ss((c1 - c) / fc)
        A = A.copy()
        for i in np.nonzero(wr > 1e-3)[0]:
            jt = int(np.argmax(Y[i, :200]))
            yc = float(Y[i, 314])
            jj = np.arange(18, jt + 1)
            w = np.exp(-0.5 * ((Y[i, jj] - yc) / sy) ** 2)
            A[i, jj] = A[i, jj] - dl * wr[i] * w
        return A, Y

    def run(self):
        A, Y = self.A0.copy(), self.Y0.copy()
        for g in self.d.get("graft_patches", []):
            A, Y = self.graft_patch(A, Y, g)
            self.A0, self.Y0 = A.copy(), Y.copy()
            self.base_fill = [R.section_fill(A[i], Y[i]) & self.G[i] for i in range(self.nv)]
        if self.d.get("graft_far"):
            A, Y = self.graft(A, Y)
            # 継いだ形を以後の「元」とする（禁止域の増分・背の戻し先・平らな海の外周）
            self.A0, self.Y0 = A.copy(), Y.copy()
            self.base_fill = [R.section_fill(A[i], Y[i]) & self.G[i] for i in range(self.nv)]
            if hasattr(self, "G0"):
                del self.G0
        if self.d.get("ramp"):
            A, Y = self.ramp(A, Y)
        if self.d.get("sharpen"):
            A, Y = self.sharpen(A, Y)
            A, Y = self.refit_outline(A, Y)
        if self.d.get("tube"):
            A, Y = self.tube(A, Y)
        A, Y = self.back(A, Y)
        if self.d.get("widen_tail"):
            A, Y = self.widen_tail(A, Y)
        if self.d.get("tail_round"):
            A, Y = self.tail_round(A, Y)
        if self.d.get("tail_cols"):
            A, Y = self.tail_cols(A, Y)
        if self.d.get("stretch_tail"):
            A, Y = self.stretch_tail(A, Y)
        if self.d.get("far_wall"):
            A, Y = self.far_wall(A, Y)
        if self.d.get("crest_line_smooth"):
            A, Y = self.crest_line_smooth(A, Y)
        for spec in self.d.get("smooth_patches", []):
            A, Y = self.smooth_patch(A, Y, spec)
        if self.d.get("far_wall_height"):
            A, Y = self.far_wall_height(A, Y)
        for g in self.d.get("col_smooth_patches", []):
            A, Y = self.col_smooth(A, Y, g)
        if self.d.get("b_lobes"):
            A, Y = self.b_lobes(A, Y)
        if self.d.get("disp_smooth"):
            A, Y = self.disp_smooth(A, Y)
        self.A, self.Y = A, Y
        sp = np.array([self.new_spill(i, A[i], Y[i]) for i in range(self.nv)])
        sx = np.array([seg_selfx(A[i], Y[i], 0, None) if Y[i].max() > 0.5 else 0 for i in range(self.nv)])
        self.log.append({"new_spill_cells_total": int(sp.sum()),
                         "new_spill_rows": {"%.1f" % self.c[i]: int(sp[i]) for i in np.nonzero(sp)[0]},
                         "section_selfx_rows": {"%.1f" % self.c[i]: int(sx[i]) for i in np.nonzero(sx)[0]}})
        return A, Y


def main():
    pre = sys.argv[1]
    design = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else {}
    t0 = time.time()
    b = Build(design)
    A, Y = b.run()
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    prov = {"route": "仕上げ28 第2回（r2）Tools/GWWaveGen/kstar_p28/r2_build.py", "base": "P28R1 (r1_rays/cand/kstarP28R1_a45_rows.npz)",
            "design": b.d, "reference_model_read_by_generator": False}
    KC.write_candidate(pre, b.c, A, Y, prov)
    rep = {"design": b.d, "log": b.log, "seconds": round(time.time() - t0, 1)}
    R.jdump(rep, pre + "_build_report.json")
    np.savez_compressed(pre + "_build_aux.npz", tube_shift=getattr(b, "tube_shift", np.zeros(b.nv)), **b.L)
    print(json.dumps(b.log, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
