# -*- coding: utf-8 -*-
"""仕上げ28修正01 の変種 RIDGE（稜）の生成器。OPENBLAS_NUM_THREADS=1 py -3.10 r01_ridge_build.py build|probe <out> [ridge_design.json]
（BLAS を 1 本にするとバイトまで決定的。並びでは 1e-14 m の丸めの差が出る）

土台は採った K*′ P28R2rec（Unity/Build/Polish/28/kstar_p28rec/）。動かすのは、原画の左の輪郭を作る行（c ≤ c_pin = −2.4）より
奥の行の頂のまわりだけ。
なぜ：仕上げ28 の第1回の RAYS の A5（crest_ramp）だけが後ろから見た形を変えた（頂を原画の頂の奥で c ≈ +5.4 まで上げ続け、
ドーム → 奥へ上る稜）。ただし A5 は (1) 頂の上げを c −1.2 から 1.8 m で始めて行ごとの余裕で頭打ちに切ったので c ≈ −0.5 に縦の溝、
(2) 頂を後ろへずらす量（back_k 2·ΔH）を c 3〜7 で切り替えたので頂の線が平面で折れ、(3) 最高点が c 5.4、F10 の段 0.43 を足した。
26修正01 の K*（CP1）は、頂を c −0.4 から c 1 m あたり約 1.2 m 後ろへ流しながら傾き約 0.42 で c +5.4 まで上げていて、
後ろから見てドームにならない（頂は直角だった）。RIDGE は、頂の線（背骨：各行の列 90 の点 (a, H)）を 3 次元でなめらかな、
曲がりの限られた 1 本の曲線として 2 段で解き直す：
  U 行ごとの「動かしの形」W_r(j)：頂の列 90 の点を 1 だけ動かす時の各列の割合。背の側（列 ≤ 90）は高さに応じて（y/H が b0 より
    下の背の足は動かない）、前の側は列 90 から列 j_end(c) へなめらかに 0 へ（132 を作る行 c ≤ +1.4 は唇の頭 列 ≥ 101、奥の行は
    唇先の手前 列 ≥ 185 を動かさない。間は c 方向に smoothstep）。
  P 平面の背骨 a(c)：頂の点を後ろ（−a）へだけ動かし、目標の線 min(土台, a(c_s) − s_a·(c − c_s)) に近く、2 階・3 階の差分が小さい
    曲線を、箱つきの最小二乗（scipy の lsq_linear）で解く（c ≤ c_pin と c ≥ c_end_a は土台のまま）。後ろへ動かすと、原画の
    カメラから見た頂の仰ぎの角が下がり（射線は 1 m 後ろで約 0.34 m 上る）、上げの余裕が増える。A5 の back_k と違い、ずらしの量は
    c の関数として一度に解くので、頂の線は平面で折れない。
  K 行ごとの上げの上限 cap(c)：P の後の形で、上げ k·W_r が原画の空の射線の禁止域（3 px 広げたもの）と段階9 の船・手前の海の
    射線の禁止域に新しくかからず、断面が自己交差しない最大の k（二分探索）。c −2.4〜+3.2 の行は頂の円の半径（評価基準 F02 の Rmin）を
    R_min 以上・1 頂点の折れを fold_max 以下に保つ（Rmin_guard）。奥の行は頂の ±2 m の弦の角を、土台と deg の小さい方より下げない
    （chord_guard。奥の小さな巻きの行は上げると尖り、Q17 の弧を割った）。
  S 立面の背骨 H(c)：c ≤ c_pin と c ≥ c_end は土台のまま、間を「目標の稜」（c_pin の高さから傾き s で c_pk まで上り、c_pk から
    奥の端の土台へ 3 次で下りる）に近く、2 階・3 階の差分が小さく、土台 ≤ H ≤ 上限 U = 土台 + cap − margin の箱の中の曲線として解く。
    上り（c ≤ c_pk）は単調にしたいので、上限を U の右からの累積の最小（単調に上る曲線が U の下にいられる最大）に tol を足した値にする
    （A5 の溝は、余裕の小さい行で頭打ちに切った上げが c 方向に凹んだこと）。固定の行を c_pin の手前 pin_extra_m だけ差分に入れるので、
    止められた行から上る稜へ曲がりの跳びなしにつながる。
  A 当てる：A += Δa_r·W_r、Y += ΔH_r·W_r。
  B 背の縦の襞をならす（back_smooth）：奥の行（c +1〜+11.5）の背（列 18〜72、86 で 0 へ）を、頂（列 90）の点に対する相対の形のまま
    c 方向に σ 1.5 m でならす。背の足（y/H 0.12〜0.35 より下）は動かさない（動かすと海の上に小山ができた）。
  J 背の行ごとの揺れをならす（back_dejitter）：c −12〜+4 の背（列 18〜58、70 で 0 へ）を、同じ列のまま c 方向に σ 0.5 m でならす
    （仕上げ28 の第2回の背の作り直しと回復の殻の見張りの行ごとの切り替わりが、後ろから見た細い縦の筋の元）。列 70 より上へ広げると
    肩の行（c −11〜−9）の列 79〜81 が原画視点で見えて動いたので、列 58〜70 で止めた。
  F 背のへこみを埋める（back_fill、2 回）：各高さの背の等高線で、c −7〜0 のいちばん後ろの行から奥へ、後ろへの出を累積の最大にして
    へこみ（P28R2rec で c ≈ +0.4 に深さ 1.7 m。後ろから見た縦の溝）だけを後ろへ平らに埋める。
  G 確かめ：全部の行で空・船の禁止域に新しくかかる数と、断面の自己交差を数える（0 のはず）。頂の線の 3 次元の曲がりを記録する。
試して採らなかった段：頂の丸め（弧長のガウスで頂をならす。F02 の Rmin がかえって下がった。代わりに K で頂の円の半径の見張りを入れた）、
前の側の減りを頂の後ろから始める場（back_m_132。頂の折れが 13° を超えた）、唇の頭の止めを c +1.4〜+2.4 で早く外す（空の余裕が減った）。
原画の輪郭を作る点（78・130・131 は c ≤ −2.4 の行、132 は c −3〜+1.4 の列 101〜193、72 は唇先 列 195〜208 と c ≈ 6 の列 342）は
動かさない（重みが 0）。格子 400×240、目印の列、UV、行の c は変えない。参照モデルは読まない（F13-1）。
"""
import os
import sys
import json
import time
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_ridge_common as RR  # noqa: E402
R2, RCm = RR.redirect_caches()
import r2_build as B2  # noqa: E402
import rec_build as RB  # noqa: E402

KC = R2.KC
J_TOP = 90
sys.path.insert(0, os.path.join(RR.REPO, "Tools", "GWWaveGen", "rubric"))
import rubric_check as RCK  # noqa: E402

DEFAULT = {
    "c_pin": -2.4,            # これより手前の行は土台のまま（原画の左の輪郭 78・130・131 を作る行）
    "c_end": 13.6,            # 立面：これより奥の行は土台のまま
    "c_end_a": 9.0,           # 平面：これより奥の行は土台のまま（土台の頂がすでに後ろへ流れている）
    "b0": 0.25,               # 背の側：y/H がこれより下の背は動かない
    "je_132": 101.0,          # 132 を作る行の前の側の重みが 0 になる列（唇の頭）
    "je_far": 185.0,          # 奥の行の前の側の重みが 0 になる列（唇先の手前）
    "je_c": [1.4, 4.4],       # j_end を je_132 → je_far へ移す c の範囲（smoothstep）
    # P（平面）
    "plan": True,
    "c_s": -0.6,              # 頂を後ろへ流し始める c
    "s_a": 1.0,               # 目標の後ろへの流れ（c 1 m あたり m）
    "da_max": 3.0,            # 後ろへのずらしの最大
    "wa_goal": 1.0, "wa_d2": 40.0, "wa_d3": 10.0,
    # K
    "margin_m": 0.2,
    "kmax_m": 8.0,
    # S（立面）
    "slope": 0.35,            # 目標の稜の傾き（c_pin から c_pk まで）
    "c_pk": 6.0,              # 目標の稜の最高点の c
    "mono_tol_m": 0.03,
    "w_goal": 1.0, "w_d2": 30.0, "w_d3": 6.0,
    "pin_extra_m": 3.0,
}


def ss(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def diff_ops(cw):
    """不均一な c の 2 階・3 階の差分の作用素。"""
    n = len(cw)
    D2 = np.zeros((n - 2, n))
    for k in range(1, n - 1):
        h1, h2 = cw[k] - cw[k - 1], cw[k + 1] - cw[k]
        D2[k - 1, k - 1] = 2.0 / (h1 * (h1 + h2)); D2[k - 1, k] = -2.0 / (h1 * h2); D2[k - 1, k + 1] = 2.0 / (h2 * (h1 + h2))
    D3 = np.zeros((n - 3, n))
    for k in range(n - 3):
        # D2 の行 k は c = cw[k+1] の 2 階の差分。隣の行との差を中心の間隔で割る
        D3[k] = (D2[k + 1] - D2[k]) / max(cw[k + 2] - cw[k + 1], 1e-3)
    return D2, D3


def smooth_lsq(c, v0, goal, lo, hi, free, win, w_goal, w_d2, w_d3):
    """窓 win の行の値を変数（free 以外は v0 に固定）とし、w_d2·Σ(D2 v)² Δc + w_d3·Σ(D3 v)² Δc + w_goal·Σ(v − goal)² Δc を
    lo ≤ v ≤ hi で最小にする（lsq_linear）。"""
    from scipy.optimize import lsq_linear
    cw = c[win]
    D2, D3 = diff_ops(cw)
    wd = np.gradient(cw)
    isfree = np.isin(win, free)
    fi = np.nonzero(isfree)[0]; xi = np.nonzero(~isfree)[0]
    vfix = v0[win][xi]
    rows_, rhs = [], []
    for M, w in ((D2 * np.sqrt(wd[1:-1])[:, None], w_d2), (D3 * np.sqrt(wd[1:-2])[:, None], w_d3)):
        sw = math.sqrt(w)
        rows_.append(sw * M[:, fi]); rhs.append(-sw * M[:, xi] @ vfix)
    sg = math.sqrt(w_goal) * np.sqrt(wd[fi])
    rows_.append(np.diag(sg)); rhs.append(sg * goal[win][fi])
    Am = np.vstack(rows_); b = np.concatenate(rhs)
    l = lo[win][fi]; h = hi[win][fi]
    l = np.minimum(l, h - 1e-9)
    r = lsq_linear(Am, b, bounds=(l, h), method="trf", lsmr_tol="auto", max_iter=3000)
    out = v0.copy()
    out[win[fi]] = r.x
    act_hi = [int(win[fi][k]) for k in range(len(fi)) if r.x[k] >= h[k] - 1e-4]
    act_lo = [int(win[fi][k]) for k in range(len(fi)) if r.x[k] <= l[k] + 1e-4]
    return out, {"status": int(r.status), "cost": float(r.cost), "n_free": int(len(fi)),
                 "active_upper_rows_c": [round(float(c[i]), 2) for i in act_hi], "active_lower_rows_c": [round(float(c[i]), 2) for i in act_lo]}


class RidgeBuild(RB.RecBuild):
    def __init__(self, design=None):
        super().__init__({}, {"protect": RB.REC_DEFAULT["protect"]}, base=RR.BASE_ROWS)
        self.g = dict(DEFAULT)
        if design:
            self.g.update(design)
        self.log = []

    # ------------------------------------------------------------ U
    def j_end(self):
        g = self.g
        c0, c1 = g["je_c"]
        t = ss((self.c - c0) / max(c1 - c0, 1e-6))
        return g["je_132"] + (g["je_far"] - g["je_132"]) * t

    def back_m(self):
        """前の側の減りを頂（列 90）の後ろ何 m（弧長）から始めるか。132 の行（唇の頭が止まる）は back_m_132、奥は 0（c は je_c と同じ移り）。"""
        g = self.g
        c0, c1 = g["je_c"]
        t = ss((self.c - c0) / max(c1 - c0, 1e-6))
        return float(g.get("back_m_132", 0.0)) * (1 - t)

    def field(self, i, A, Y, je, bm=0.0):
        g = self.g
        j = np.arange(self.nu, dtype=float)
        H = max(float(Y[i, J_TOP]), 0.3)
        wb = ss((Y[i] / H - g["b0"]) / (1.0 - g["b0"]))
        if bm > 1e-6:
            # 弧長で、頂の後ろ bm m から列 je まで減らす（頂のまわりの曲がりの足し方を減らす：132 の行は唇の頭が止まるので）
            sL = np.r_[0, np.cumsum(np.hypot(np.diff(A[i]), np.diff(Y[i])))]
            s0 = sL[J_TOP] - bm; s1 = float(np.interp(je, j, sL))
            wf = 1.0 - ss((sL - s0) / max(s1 - s0, 1e-3))
            W = np.where(j <= J_TOP, wb * wf, wf)
        else:
            wf = 1.0 - ss((j - J_TOP) / max(je - J_TOP, 1.0))
            W = np.where(j <= J_TOP, wb, wf)
        W[:18] = 0.0
        return W

    def fields(self, A, Y):
        je = self.j_end(); bm = self.back_m()
        W = np.zeros((self.nv, self.nu))
        for i in range(self.nv):
            if Y[i].max() >= 1.0:
                W[i] = self.field(i, A, Y, je[i], bm[i])
        return W

    # ------------------------------------------------------------ K
    def caps(self, A, Y, W, dirA=None):
        """行ごとの上げ（Y += k·W、dirA があれば A += k·dirA·W も）の上限 k。"""
        g = self.g
        cap = np.zeros(self.nv)
        rows = np.nonzero((self.c > g["c_pin"] - 1.0) & (self.c < g["c_end"] + 0.5))[0]
        for i in rows:
            if Y[i].max() < 1.0:
                continue
            sp0 = self.new_spill(i, A[i], Y[i]); pp0 = self.new_spill_p(i, A[i], Y[i])
            sx0 = B2.seg_selfx(A[i], Y[i], 0, None)
            da = 0.0 if dirA is None else float(dirA[i])

            rq = g.get("Rmin_guard")
            q0 = RCK.corner_q17(A[i], Y[i], 200) if rq else None
            use_rq = bool(rq) and q0["Rmin_m"] >= float(rq["R_min"]) and float(rq["c"][0]) <= self.c[i] <= float(rq["c"][1])

            cg = g.get("chord_guard")
            use_cg = bool(cg) and float(cg["c"][0]) <= self.c[i] <= float(cg["c"][1])
            ch_min = min(float(q0["chord2_deg"]) if q0 else RCK.corner_q17(A[i], Y[i], 200)["chord2_deg"], float(cg["deg"])) if use_cg else None

            def ok(k):
                y1 = Y[i] + k * W[i]; a1 = A[i] + k * da * W[i]
                if use_rq:
                    q = RCK.corner_q17(a1, y1, 200)
                    if q["Rmin_m"] < float(rq["R_min"]) or q["fold_deg"] > float(rq.get("fold_max", 12.0)):
                        return False
                if use_cg and RCK.corner_q17(a1, y1, 200)["chord2_deg"] < ch_min:
                    # 頂の ±2 m の弦の角（Q17 の弧の読み）を、土台と目標の小さい方より下げない（奥の小さな巻きの行は上げると尖る）
                    return False
                return (self.new_spill(i, a1, y1) <= sp0 and self.new_spill_p(i, a1, y1) <= pp0
                        and B2.seg_selfx(a1, y1, 0, None) <= sx0)
            lo, hi = 0.0, float(g["kmax_m"])
            if ok(hi):
                lo = hi
            else:
                for _ in range(14):
                    mid = 0.5 * (lo + hi)
                    if ok(mid):
                        lo = mid
                    else:
                        hi = mid
            cap[i] = lo
        return cap

    # ------------------------------------------------------------ P
    def back_caps(self, A, Y, W):
        """行ごとの、頂を後ろへずらす量（A −= k·W）の上限 k（空・船の禁止域に新しくかからず、断面が自己交差しない）。"""
        g = self.g
        bc = np.zeros(self.nv)
        rows = np.nonzero((self.c > g["c_pin"]) & (self.c < g["c_end_a"] + 0.5))[0]
        for i in rows:
            if Y[i].max() < 1.0:
                continue
            sp0 = self.new_spill(i, A[i], Y[i]); pp0 = self.new_spill_p(i, A[i], Y[i]); sx0 = B2.seg_selfx(A[i], Y[i], 0, None)

            def ok(k):
                a1 = A[i] - k * W[i]
                return self.new_spill(i, a1, Y[i]) <= sp0 and self.new_spill_p(i, a1, Y[i]) <= pp0 and B2.seg_selfx(a1, Y[i], 0, None) <= sx0
            lo, hi = 0.0, float(g["da_max"])
            if ok(hi):
                lo = hi
            else:
                for _ in range(12):
                    mid = 0.5 * (lo + hi)
                    if ok(mid):
                        lo = mid
                    else:
                        hi = mid
            bc[i] = lo
        return bc

    def solve_plan(self, A, Y, W):
        g = self.g
        c = self.c
        a0 = A[:, J_TOP].copy()
        cpin, cend = float(g["c_pin"]), float(g["c_end_a"])
        cs, sa = float(g["c_s"]), float(g["s_a"])
        if g.get("a_knots"):
            # 目標の後ろへのずらしを節で与える：(c, Δa ≤ 0)。PCHIP でつなぎ、土台より前へは出さない
            from scipy.interpolate import PchipInterpolator
            kc = np.array([k[0] for k in g["a_knots"]], float); kv = np.array([k[1] for k in g["a_knots"]], float)
            dag = np.where((c >= kc[0]) & (c <= kc[-1]), PchipInterpolator(kc, kv)(np.clip(c, kc[0], kc[-1])), 0.0)
            goal = a0 + np.minimum(dag, 0.0)
        else:
            line = float(np.interp(cs, c, a0)) - sa * np.maximum(c - cs, 0.0)
            goal = np.where(c > cs, np.minimum(a0, line), a0)
        bc = self.back_caps(A, Y, W) * np.maximum(W[:, J_TOP], 0.05)    # 列 90 の点のずらしの上限
        self.back_cap = bc
        free = np.nonzero((c > cpin) & (c < cend))[0]
        win = np.nonzero((c >= cpin - float(g["pin_extra_m"])) & (c <= cend + 1.5))[0]
        lo = a0 - np.maximum(bc - float(g.get("back_margin_m", 0.05)), 0.0); hi = a0.copy()
        at, info = smooth_lsq(c, a0, goal, lo, hi, free, win, g["wa_goal"], g["wa_d2"], g["wa_d3"])
        da = at - a0
        da[(c <= cpin) | (c >= cend)] = 0.0
        self.goal_a = goal
        self.log.append({"plan_lsq": info, "plan_back_cap_m": {"%.1f" % c[i]: round(float(bc[i]), 2) for i in range(0, self.nv, 3) if c[i] > cpin and c[i] < cend},
                         "plan_da_m": {"%.1f" % c[i]: round(float(da[i]), 2) for i in range(0, self.nv, 3) if abs(da[i]) > 0.01}})
        return da

    # ------------------------------------------------------------ S
    def solve_height(self, H0, cap):
        g = self.g
        c = self.c
        cpin, cend = float(g["c_pin"]), float(g["c_end"])
        hp = float(np.interp(cpin, c, H0)); he = float(np.interp(cend, c, H0))
        cpk = float(g["c_pk"]); s = float(g["slope"])
        hpk = hp + s * (cpk - cpin)
        se = float((np.interp(cend + 0.2, c, H0) - np.interp(cend - 0.2, c, H0)) / 0.4)
        goal = H0.copy()
        if g.get("H_knots"):
            # 目標の稜を節で与える：(c, ΔH)。ΔH は「止められた行の最高 Hpl」からの高さ（None は土台の高さ）。PCHIP（単調な区間）でつなぐ
            from scipy.interpolate import PchipInterpolator
            Hpl = float(H0[(c > cpin - 0.01) & (c < float(g.get("c_plateau_end", 0.2)))].max())
            kc = np.array([k[0] for k in g["H_knots"]], float)
            kv = np.array([float(np.interp(k[0], c, H0)) if k[1] is None else Hpl + k[1] for k in g["H_knots"]], float)
            f = PchipInterpolator(kc, kv)
            m = (c > cpin) & (c < cend) & (c >= kc[0]) & (c <= kc[-1])
            goal[m] = f(c[m])
            m0 = (c > cpin) & (c < kc[0])
            goal[m0] = np.maximum(H0[m0], kv[0])
        else:
            m1 = (c > cpin) & (c <= cpk)
            goal[m1] = hp + s * (c[m1] - cpin)
            m2 = (c > cpk) & (c < cend)
            L = cend - cpk
            t = (c[m2] - cpk) / L
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
            goal[m2] = h00 * hpk + h10 * L * s + h01 * he + h11 * L * se
        U = H0 + np.maximum(cap - float(g["margin_m"]), 0.0)
        # 上り（c_pin〜c_pk）：単調に上る曲線が U の下にいられる最大（右からの累積の最小）＋ tol
        up = np.nonzero((c > cpin) & (c <= cpk))[0]
        M = U.copy()
        if len(up):
            M[up] = np.minimum.accumulate(U[up][::-1])[::-1] + float(g["mono_tol_m"])
        hi = np.minimum(U, M)
        lo = H0.copy()
        hi = np.maximum(hi, lo)
        # 上り：下限も単調に（止められた行の最高 − tol を下回って凹まない。上限が許す所まで）
        if len(up):
            run = np.maximum.accumulate(np.r_[H0[c <= cpin][-1:], lo[up]])[1:] - float(g["mono_tol_m"])
            lo[up] = np.maximum(lo[up], np.minimum(run, hi[up]))
        free = np.nonzero((c > cpin) & (c < cend))[0]
        win = np.nonzero((c >= cpin - float(g["pin_extra_m"])) & (c <= cend + 1.5))[0]
        Ht, info = smooth_lsq(c, H0, goal, lo, hi, free, win, g["w_goal"], g["w_d2"], g["w_d3"])
        self.goal = goal; self.U = U; self.hi = hi
        self.log.append({"height_lsq": info})
        return Ht

    # ------------------------------------------------------------ B（背の縦の襞をならす）
    def back_smooth(self, A, Y):
        """背（列 18..j1、j1 から j2 で 0 へ）を、頂（列 90）の点に対する相対の形のまま c 方向に σ でならす（後ろから見た縦の襞・
        布をかぶせたような見え方を減らす）。背の足の a（列 18）も同じにならす。頂の点と唇は動かさない。背は原画のカメラから見えない
        （頂の陰）が、空・船の禁止域と自己交差で行ごとに割合を下げる。"""
        g = self.g["back_smooth"]
        c = self.c
        c0, c1 = g.get("c", [-6.0, 11.0]); sg = float(g.get("sigma_m", 1.0)); fc = float(g.get("fade_m", 1.5))
        j1, j2 = int(g.get("j1", 76)), int(g.get("j2", 88))
        at, Ht = A[:, J_TOP], np.maximum(Y[:, J_TOP], 0.3)
        dA = A - at[:, None]; dY = Y - Ht[:, None]
        sA = R2.csmooth(c, dA, sg); sY = R2.csmooth(c, dY, sg)
        jj = np.arange(self.nu, dtype=float)
        wj = (1 - ss((jj - j1) / max(j2 - j1, 1))) * (jj >= 18) * (jj <= J_TOP)
        wr = ss((c - c0) / fc) * ss((c1 - c) / fc)
        A2, Y2 = A.copy(), Y.copy()
        red = {}
        for i in np.nonzero(wr > 1e-3)[0]:
            if Y[i].max() < 2.0:
                continue
            # 背の足（y/H が foot_h0〜foot_h1 より下）は動かさない（足を動かすと海の上に小山ができる）
            Hh = max(float(Y[i].max()), 0.3)
            wy = ss((Y[i] / Hh - float(g.get("foot_h0", 0.12))) / max(float(g.get("foot_h1", 0.35)) - float(g.get("foot_h0", 0.12)), 1e-3))
            for f in (1.0, 0.7, 0.4, 0.0):
                w = f * wr[i] * wj * wy
                a1 = A[i] + w * (sA[i] - dA[i]); y1 = Y[i] + w * (sY[i] - dY[i])
                y1 = np.where(w > 0, np.maximum(y1, 0.0), y1)
                a1[0:18] = A[i, 0:18] + (a1[18] - A[i, 18]) * np.linspace(0, 1, 19)[:18]
                if (self.new_spill(i, a1, y1) <= self.new_spill(i, A[i], Y[i]) and self.new_spill_p(i, a1, y1) <= self.new_spill_p(i, A[i], Y[i])
                        and B2.seg_selfx(a1, y1, 0, None) <= B2.seg_selfx(A[i], Y[i], 0, None)):
                    break
            if f < 1.0:
                red["%.1f" % c[i]] = f
            A2[i], Y2[i] = a1, y1
        self.log.append({"back_smooth": {"c": [c0, c1], "sigma_m": sg, "rows_reduced": red}})
        return A2, Y2

    # ------------------------------------------------------------ J（背の行ごとの揺れ＝縦の襞をならす）
    def back_dejitter(self, A, Y):
        """背（列 18..j1、j1 から j2 で 0 へ）の点を、同じ列のまま c 方向に σ（小さい）でならす（行ごとの揺れが、後ろから見た縦の襞・
        布のような見え方になる。仕上げ28 の第2回の背の作り直しと回復の殻の見張りの行ごとの切り替わりが元）。大きな形は変えない。
        ならした点が、その行の頂より y_cap_frac·H より上へ出ないようにし、空・船の禁止域と自己交差で行ごとに割合を下げる。"""
        g = self.g["back_dejitter"]
        c = self.c
        c0, c1 = g.get("c", [-12.0, 4.0]); sg = float(g.get("sigma_m", 0.5)); fc = float(g.get("fade_m", 1.0))
        j1, j2 = int(g.get("j1", 70)), int(g.get("j2", 82))
        sA = R2.csmooth(c, A, sg); sY = R2.csmooth(c, Y, sg)
        jj = np.arange(self.nu, dtype=float)
        wj = (1 - ss((jj - j1) / max(j2 - j1, 1))) * (jj >= 18)
        wr = ss((c - c0) / fc) * ss((c1 - c) / fc)
        A2, Y2 = A.copy(), Y.copy()
        red = {}
        for i in np.nonzero(wr > 1e-3)[0]:
            H = float(Y[i].max())
            if H < 2.0:
                continue
            for f in (1.0, 0.6, 0.3, 0.0):
                w = f * wr[i] * wj
                a1 = A[i] + w * (sA[i] - A[i]); y1 = Y[i] + w * (sY[i] - Y[i])
                y1 = np.where(w > 0, np.minimum(y1, float(g.get("y_cap_frac", 0.97)) * H), y1)
                y1 = np.where(w > 0, np.maximum(y1, 0.0), y1)
                a1[0:18] = A[i, 0:18] + (a1[18] - A[i, 18]) * np.linspace(0, 1, 19)[:18]
                if (self.new_spill(i, a1, y1) <= self.new_spill(i, A[i], Y[i]) and self.new_spill_p(i, a1, y1) <= self.new_spill_p(i, A[i], Y[i])
                        and B2.seg_selfx(a1, y1, 0, None) <= B2.seg_selfx(A[i], Y[i], 0, None)):
                    break
            if f < 1.0:
                red["%.1f" % c[i]] = f
            A2[i], Y2[i] = a1, y1
        self.log.append({"back_dejitter": {"c": [c0, c1], "sigma_m": sg, "cols": [j1, j2], "rows_reduced": red}})
        return A2, Y2

    # ------------------------------------------------------------ F（背のへこみを埋める）
    @staticmethod
    def back_contour(A, Y, y):
        """各行の背の側（列 18..頂）で高さ y を横切る点の a（無ければ nan）。"""
        out = np.full(len(A), np.nan)
        for r in range(len(A)):
            jt = int(np.argmax(Y[r, :200]))
            if Y[r, jt] <= y:
                continue
            a, yy = A[r, 18:jt + 1], Y[r, 18:jt + 1]
            k = np.nonzero((yy[:-1] - y) * (yy[1:] - y) <= 0)[0]
            if len(k) == 0:
                continue
            k = k[-1]
            t = (y - yy[k]) / (yy[k + 1] - yy[k] + 1e-12)
            out[r] = a[k] + t * (a[k + 1] - a[k])
        return out

    def back_fill(self, A, Y):
        """後ろから見た縦の溝（背が c ≈ 0 で前へへこむ）を埋める。各高さ y の背の等高線 a_b(c, y) について、c_f0〜c_ref_max の中で
        いちばん後ろ（a 最小）の行 c_ref から奥へ、後ろへの出 b = −a_b を累積の最大にする（へこみだけを、後ろへ平らに埋める。前へは動かさない）。
        変位 Δa(c, y) ≤ 0 を c 方向に σ_c、高さの方向に σ_y でならし、背の頂点（列 18..頂）へ高さで当てる（頂から top_fade_m の内は 0 へ）。
        背は原画のカメラから見えない（射線は後ろへ行くほど上るので、頂より低い背の点は頂の陰）。最後に禁止域と自己交差で確かめる。"""
        g = self.g["back_fill"]
        c = self.c
        ys = np.arange(float(g.get("y0", 0.5)), float(g.get("y1", 22.0)) + 1e-9, float(g.get("dy", 0.5)))
        c0, cref1, c1 = float(g.get("c_f0", -7.0)), float(g.get("c_ref_max", 0.0)), float(g.get("c_f1", 8.0))
        rows = np.nonzero((c >= c0) & (c <= c1))[0]
        D = np.zeros((self.nv, len(ys)))
        for k, y in enumerate(ys):
            ab = self.back_contour(A, Y, y)
            m = np.isfinite(ab) & (c >= c0) & (c <= c1)
            if m.sum() < 3:
                continue
            rr = np.nonzero(m)[0]
            sel = rr[c[rr] <= cref1]
            if not len(sel):
                continue
            iref = sel[int(np.argmin(ab[sel]))]
            b = -ab
            run = -np.inf
            for i in rr:
                if i < iref:
                    continue
                run = max(run, b[i])
                D[i, k] = -(run - b[i])          # ≤ 0：後ろへ
        # ならす（c 方向・高さの方向）
        Ds = D.copy()
        if float(g.get("sigma_c_m", 0.8)) > 0:
            Ds = R2.csmooth(c, Ds, float(g.get("sigma_c_m", 0.8)))
        sy = float(g.get("sigma_y_m", 1.0)) / float(g.get("dy", 0.5))
        if sy > 0:
            r_ = int(math.ceil(3 * sy)); kk = np.exp(-0.5 * (np.arange(-r_, r_ + 1) / sy) ** 2); kk /= kk.sum()
            Ds = np.array([np.convolve(np.pad(v, r_, mode="edge"), kk, "valid") for v in Ds])
        Ds = np.minimum(Ds, 0.0)
        A2 = A.copy()
        tf = float(g.get("top_fade_m", 1.0))
        moved = 0
        for i in rows:
            jt = int(np.argmax(Y[i, :200])); H = Y[i, jt]
            if H < 2.0:
                continue
            jj = np.arange(18, jt + 1)
            d = np.interp(Y[i, jj], ys, Ds[i])
            w = ss((H - Y[i, jj]) / tf)
            a1 = A[i].copy(); a1[jj] = A[i, jj] + d * w
            a1[0:19] = self.A0[i, 0] + (a1[18] - self.A0[i, 0]) * np.linspace(0, 1, 19)
            if (self.new_spill(i, a1, Y[i]) <= self.new_spill(i, A[i], Y[i]) and self.new_spill_p(i, a1, Y[i]) <= self.new_spill_p(i, A[i], Y[i])
                    and B2.seg_selfx(a1, Y[i], 0, None) <= B2.seg_selfx(A[i], Y[i], 0, None)):
                A2[i] = a1; moved += 1
        self.fill = Ds
        self.log.append({"back_fill": {"rows_moved": moved, "max_push_back_m": round(float(-Ds.min()), 3),
                                       "push_by_c_at_y12_16_18": {"%.1f" % c[i]: [round(float(np.interp(y, ys, Ds[i])), 2) for y in (12.0, 16.0, 18.0)]
                                                                  for i in rows[::4]}}})
        return A2

    # ------------------------------------------------------------ run
    def run(self):
        g = self.g
        A, Y = self.A0.copy(), self.Y0.copy()
        t0 = time.time()
        W = self.fields(A, Y)
        da = np.zeros(self.nv)
        if g.get("plan"):
            da = self.solve_plan(A, Y, W)
            A = A + (da / np.maximum(W[:, J_TOP], 0.05))[:, None] * W
            W = self.fields(A, Y)
        self.da = da
        H0 = Y[:, J_TOP].copy()
        cap = self.caps(A, Y, W)
        w90 = np.maximum(W[:, J_TOP], 0.05)
        self.cap = cap * w90                       # 列 90 の点の上げの上限（場の振幅 × 列 90 の割合）
        self.log.append({"caps_s": round(time.time() - t0, 1)})
        Ht = self.solve_height(H0, self.cap)
        dH = Ht - H0
        dH[(self.c <= g["c_pin"]) | (self.c >= g["c_end"])] = 0.0
        self.dH = dH
        Y = Y + (dH / w90)[:, None] * W
        self.W = W
        if g.get("back_smooth"):
            A, Y = self.back_smooth(A, Y)
        if g.get("back_dejitter"):
            A, Y = self.back_dejitter(A, Y)
        if g.get("back_fill"):
            for _ in range(int(g["back_fill"].get("iters", 1))):
                A = self.back_fill(A, Y)
        self.A, self.Y = A, Y
        sp = np.array([self.new_spill(i, A[i], Y[i]) for i in range(self.nv)])
        pp = np.array([self.new_spill_p(i, A[i], Y[i]) for i in range(self.nv)])
        sx = np.array([B2.seg_selfx(A[i], Y[i], 0, None) if Y[i].max() > 0.5 else 0 for i in range(self.nv)])
        sx0 = np.array([B2.seg_selfx(self.A0[i], self.Y0[i], 0, None) if self.Y0[i].max() > 0.5 else 0 for i in range(self.nv)])
        self.log.append({"final_new_spill_cells_sky_d3": int(sp.sum()), "final_new_spill_cells_protect": int(pp.sum()),
                         "section_selfx_new_rows": [round(float(self.c[i]), 2) for i in np.nonzero(sx > sx0)[0]],
                         "dH_max_m": round(float(dH.max()), 3), "c_of_dH_max": round(float(self.c[int(np.argmax(dH))]), 2),
                         "da_min_m": round(float(da.min()), 3), "spine3d": spine_curvature(self.c, A, Y)})
        return A, Y

    def table(self):
        c = self.c
        rows = np.nonzero((c > self.g["c_pin"] - 1.5) & (c < self.g["c_end"] + 1.0))[0]
        return [{"c": round(float(c[i]), 2), "a0": round(float(self.A0[i, J_TOP]), 3), "da": round(float(self.da[i]), 3),
                 "H0": round(float(self.Y0[i, J_TOP]), 3), "cap": round(float(self.cap[i]), 3), "hi": round(float(self.hi[i]), 3),
                 "goal": round(float(self.goal[i]), 3), "H": round(float(self.Y[i, J_TOP]), 3), "dH": round(float(self.dH[i]), 3),
                 "Hmax_row": round(float(self.Y[i].max()), 3)} for i in rows]


def spine_curvature(c, A, Y, c0=-14.0, c1=12.0):
    """頂の線（列 90 の点、断面座標 (a, y, c)）の 3 次元の曲がり（1/m）と、行をまたぐ向きの変わり（度/m）。"""
    m = (c >= c0) & (c <= c1)
    P = np.stack([A[m, J_TOP], Y[m, J_TOP], c[m]], -1)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    su = np.arange(0, s[-1], 0.25)
    Pu = np.stack([np.interp(su, s, P[:, k]) for k in range(3)], -1)
    d1 = np.gradient(Pu, 0.25, axis=0); d2 = np.gradient(d1, 0.25, axis=0)
    kap = np.linalg.norm(np.cross(d1, d2), axis=1) / np.maximum(np.linalg.norm(d1, axis=1) ** 3, 1e-9)
    cu = Pu[:, 2]
    tang = d1 / np.linalg.norm(d1, axis=1, keepdims=True)
    turn = np.degrees(np.arccos(np.clip((tang[4:] * tang[:-4]).sum(1), -1, 1))) / 1.0   # 4 × 0.25 m = 1 m
    k_main = kap[(cu > -6) & (cu < 9)]
    return {"kappa_max_per_m": round(float(kap.max()), 4), "c_of_kappa_max": round(float(cu[int(np.argmax(kap))]), 2),
            "kappa_p95_per_m": round(float(np.percentile(kap, 95)), 4),
            "kappa_max_c_-6_9": round(float(k_main.max()), 4) if len(k_main) else None,
            "turn_max_deg_per_m": round(float(turn.max()), 2)}


def main():
    mode, pre = sys.argv[1], sys.argv[2]
    design = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
    t0 = time.time()
    b = RidgeBuild(design)
    A, Y = b.run()
    rep = {"design": b.g, "log": b.log, "table": b.table(), "seconds": round(time.time() - t0, 1),
           "base": {"rows": RR.BASE_ROWS, "rows_sha256": RR.sha256(RR.BASE_ROWS)},
           "base_spine3d": spine_curvature(b.c, b.A0, b.Y0)}
    if mode == "probe":
        RR.jdump(rep, pre)
    else:
        os.makedirs(os.path.dirname(pre), exist_ok=True)
        prov = {"route": "仕上げ28修正01 の変種 RIDGE Tools/GWWaveGen/kstar_p28/r01_ridge_build.py（rec_build.RecBuild を継ぐ）",
                "base": "K*′ P28R2rec (Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_rows.npz)", "design": b.g,
                "reference_model_read_by_generator": False}
        KC.write_candidate(pre, b.c, A, Y, prov)
        RR.jdump(rep, pre + "_build_report.json")
        np.savez_compressed(pre + "_build_aux.npz", cap=b.cap, dH=b.dH, da=b.da, goal=b.goal, W=b.W.astype(np.float32))
    for r in rep["table"][::3]:
        print(r)
    print(json.dumps(b.log, ensure_ascii=False)[:3000])
    print("base spine3d", rep["base_spine3d"])
    print("seconds", round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
