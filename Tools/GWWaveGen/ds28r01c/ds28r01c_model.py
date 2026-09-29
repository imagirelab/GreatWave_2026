# -*- coding: utf-8 -*-
"""設計28修正01 試行C（Q15）：唇の巻き下がり（唇先が頂に対して下がって爪の鉤になる動き）を、唇の伸び出しと同時に進める生成器。

README
======
試行B の V80（Tools/GWWaveGen/ds28r01b/ds28r01b_model.py の Generator、変種 V80）を import して継承し、唇（層4）の放出の前の
上下の運びと、放出の時刻だけを替える。試行B・設計26〜29 のファイルは変えない（読み込む時に SHA-256 を記録する）。

Q15（利用者、2026-09-28）：V80・V70 はどちらでもよい。唇が伸び出す区間は良い。問題は、最高点に達した後の「押し下げ」（唇先が頂に対して
約 8 m 下がって爪へ巻き込む動き）が最後の慢動作の中に集中していて違和感が強いこと。この巻き下がりを明らかに前倒しし、唇が伸び出した
瞬間から始めたい。目的は変わらない（大波の動きに違和感がなく、観客が納得できること）。

V80 で押し下げが後ろに寄る理由（生成器の式から）：
  (1) 上下の運び Φη（頂の上昇が止まる区間から、唇の水が頂に対して上向きの勢い Aη を保つ。主断面の唇先で Aη = +0.85 m/s）で、
      唇先は伸び出しの間に頂に対して −1.44 m → −0.30 m へ上がる。
  (2) 放出（T_free = 0.58·T_row、主断面 1.28 s 前）の後は重力だけなので、頂に対する下がりは g·T²/2 で t* の直前に寄る（8 m）。

試行C で替えるもの（名前の付いた美術の誘導 ds_lip_curl_with_extension。ds28r01c_params.json。物理の入力は変えない）：
  上下の運びの形 Φη を巻き下がりの形 Φc に替える。点 i の放出の前の位置（地面）＝試行B と同じ B_i(τ) ＋ (Aξ_i·Φξ_r(τ), Aη_i·Φc_i(τ))
  − 放出の前の下向きの加速度の立ち上げ ＋ 爪の細部。振幅 Aη_i は試行B と同じ一次式（放出の時に v2 = V0、押しなし）で解く（負＝下向き）。
    P̃（lin_progress）：運びの始まり τ_b から t_up 0.35 s で立ち上がり、その後 (1 + γ_c·経過) で増える速さの形を t* で 1 にしたもの。
    C1（curl_shape = extension）：Φc = P̃（γ_c 0.15/s）。頂に対する唇の下がりは伸び出しの進みにほぼ比例する。
    C2（curl_shape = crest_lag）：Φc_i = (1 − μ_i)·P̃ + μ_i·Q。Q = ∫ S((t − τ_q)/T_q)·y_c'(t) dt（τ_q から、t* で 1）＝唇が頂の上昇に
        付いて上がらない分（頂は伸び出しの前半に大きく上がるので、巻き下がりが伸び出しより先に進む）。μ_i は下がる点だけ μ·w_r（上がる点は 0）、
        λ_i = μ_i·|Aη_i|/span_r ≤ lag_cap（λ > 1 だと頂の上昇が止まる区間で点が上向きに加速する）。
    lead_quadratic（記録用、パッケージは作らない）：Φc = 1 − (1 − P̃)²（頂の上昇が 1 m/s に落ちた後も頂に対する下がりが減速するので、
        唇先が上向きに加速する）。
  放出（自由な飛行の始まり）を T_free = f·T_row（f = 0.15、主断面 0.33 s 前）に遅らせ、その前の 0.45 s で唇先の支えを消す（下向きの加速度を
  (1 − s)²·9.81 m/s² まで立ち上げる）。放出の後は重力だけ（P4）。
  管の天井の移しの上書き（tube_blend_s・tube_blend_shape・tube_follows_curl_linearly・tube_capture）と lag_row_weight_power は試したが、
  既定では切り（設計28 のまま。ds28r01c_params.json の tube_options_ja と C2 の note_ja）。

使い方（numpy だけ）：
    from ds28r01c_model import Generator
    g = Generator("art_on", curl_variant="C1")
    g = Generator("art_on", curl_variant="C2", c_overrides={"variants": {"C2": {"crest_lag_mu": 0.6}}})   # 記録に残る上書き
    X = g.local(-2.0)
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DSB = os.path.abspath(os.path.join(HERE, "..", "ds28r01b"))
if DSB not in sys.path:
    sys.path.insert(0, DSB)
import ds28r01b_model as MB  # noqa: E402

MD = MB.MD
M8 = MB.M8
REPO = MB.REPO
PARAMS_C = os.path.join(HERE, "ds28r01c_params.json")
VARIANTS = ("C1", "C2")
SHAPES = ("extension", "crest_lag", "lead_quadratic")


def load_c(path=PARAMS_C):
    R = MD.load_json(path)
    shas = {}
    for k in ("trial_b_params", "trial_b_model"):
        p = os.path.join(REPO, R["base"][k])
        if not os.path.isfile(p):
            raise SystemExit("[ds28r01c] base のファイルがありません：%s" % R["base"][k])
        shas[R["base"][k]] = MD.sha256_file(p)
    return R, shas


def ramp3(t, tu):
    """smoothstep S(t/tu) と、t の一階・二階微分（t ≤ 0 で 0、t ≥ tu で 1）。"""
    if t <= 0.0:
        return 0.0, 0.0, 0.0
    if t >= tu:
        return 1.0, 0.0, 0.0
    x = t / tu
    return x * x * (3 - 2 * x), 6 * x * (1 - x) / tu, 6 * (1 - 2 * x) / (tu * tu)


class Generator(MB.Generator):
    """試行B の V80 ＋ ds_lip_curl_with_extension（試行C）。"""

    def __init__(self, version="art_on", curl_variant="C1", log=None, switches=None, curl=None, c_path=PARAMS_C, c_overrides=None,
                 claws_follow=None):
        self.RC, self.c_base_shas = load_c(c_path)
        if c_overrides:
            M8.deep_merge(self.RC, c_overrides)
        self.c_path = c_path
        self.c_sha = MD.sha256_file(c_path)
        if curl_variant not in self.RC["variants"]:
            raise ValueError("変種は %s のどれか" % ",".join(self.RC["variants"]))
        self.curl_variant = curl_variant
        self.VC = self.RC["variants"][curl_variant]
        self.curl_kind = str(self.VC["curl_shape"])
        if self.curl_kind not in SHAPES:
            raise ValueError("curl_shape は %s のどれか" % ",".join(SHAPES))
        self.curl_mu = float(self.VC.get("crest_lag_mu", 0.0))
        self.curl_on = (version == "art_on") if curl is None else bool(curl)
        MB.Generator.__init__(self, version, carry_variant=self.RC["base"]["base_variant"], log=log, switches=switches,
                              claws_follow=claws_follow)
        if self.curl_on:
            self.variant = self.variant + "+ds_lip_curl_with_extension=%s" % curl_variant

    # ------------------------------------------------------------ 管の天井の移し（設計28 の tube_blend_s の上書き）
    def _approach_setup(self):
        MB.Generator._approach_setup(self)
        self.tube_bl_28 = self.tube_bl
        if self.curl_on:
            tb = self.VC.get("tube_blend_s", self.RC["lip_curl_with_extension"].get("tube_blend_s"))
            if tb is not None:
                # 管の天井を始まりの Hermite から形の移しへ替える smoothstep の長さ。巻き下がりで rim が始まりの後すぐ下がり始めると、
                # 0.3 s の移しの終わり（二階微分 ±6/T²）で rim のそばの管の天井の点が頂点の後に上向きに加速する（試行C 初回：主断面の
                # 列 224 で +2.5 m/s²、τ −1.92）。移しを長くして抑える
                self.tube_bl = float(tb)
            self.tube_quintic = str(self.VC.get("tube_blend_shape", self.RC["lip_curl_with_extension"].get("tube_blend_shape", "smoothstep"))) == "quintic"
            self.tube_curl_linear = bool(self.VC.get("tube_follows_curl_linearly", self.RC["lip_curl_with_extension"].get("tube_follows_curl_linearly", False)))
            self.tube_capture = str(self.VC.get("tube_capture", self.RC["lip_curl_with_extension"].get("tube_capture", "onset")))
        else:
            self.tube_quintic = False
            self.tube_curl_linear = False
            self.tube_capture = "onset"

    def _tube_t_capture(self, r):
        """管の天井の Hermite から形の移しへ替え始める τ。既定（設計28）は噴流の始まり −T_row。tube_capture = carry_start の時、運ぶ行は
        運びの始まり τ_b（巻き下がりで rim が下がり始める前。形の移しの間は管の天井が両端の動きを列の割合で線形に受ける）。"""
        L = self.lip.get(r)
        if getattr(self, "tube_capture", "onset") == "carry_start" and L is not None and L.get("carry"):
            return float(self.tau_b[r])
        return -float(self.T_row[r])

    def _rim_curl_dy(self, r, tau):
        """rim の点（唇の最後の点）の巻き下がりの上下の足し分 Aη·Φc（C2 は A_P·P + A_Q·Q）。運ぶ行だけ（ほかは 0）。"""
        L = self.lip.get(r)
        if L is None or not L.get("carry"):
            return 0.0
        i = len(L["cols"]) - 1
        if self.curl_kind == "crest_lag":
            return float(L["A_P"][i] * self.lin_progress(r, tau)[0] + L["A_Q"][i] * self.crest_progress(r, tau, deriv=False)[0])
        return float(L["Aeta"][i] * self.curl_shape(r, tau)[0])

    def _tube_hermite(self, r, tau, X_rim, D_rim, X_ja, D_ja):
        """管の天井の Hermite（rim〜錨）。tube_follows_curl_linearly のとき、rim の巻き下がりの上下の足し分 dy を除いた rim から Hermite を
        引き、dy を列の割合で線形に足す（始まりの後の形の移し TM と同じ足し方。巻き下がりで rim が下がっても管の天井の形そのものは
        膨らまない。試行C 初回では、下がった rim から引いた Hermite が 0.5H の高さで前へ膨らみ、始まりの後の移しで 0.7 m 戻った（関門 P18））。"""
        st = self.seam_tube[r]
        if not getattr(self, "tube_curl_linear", False):
            return st.hermite(X_rim, D_rim, X_ja, D_ja, self.herm_scale)
        dy = self._rim_curl_dy(r, tau)
        Ht = st.hermite(X_rim - np.array([0.0, dy]), D_rim, X_ja, D_ja, self.herm_scale)
        uu = np.linspace(0.0, 1.0, len(Ht))
        Ht = Ht.copy()
        Ht[:, 1] += (1.0 - uu) * dy
        return Ht

    def _onset_setup(self):
        MB.Generator._onset_setup(self)
        if not (getattr(self, "tube_curl_linear", False) or getattr(self, "tube_capture", "onset") != "onset"):
            return
        # 管の天井の形 O を、形の移しを始める τ（_tube_t_capture）の Hermite にする（その τ で Hermite と形の移しが一致するように）
        for r in sorted(self.lip.keys()):
            L = self.lip[r]
            if not L.get("carry"):
                continue
            t_on = self._tube_t_capture(r)
            S = self._shared(t_on)
            Arow = self.K.A[r].copy()
            Yrow = self.K.Y[r].copy()
            Bu, X_ja, D_ja, P_top, _ = self._front_body(r, t_on, S, Arow, Yrow, 0.0)
            Xl, rel = self._lip_local(r, t_on, S, Bu)
            X_rim, D_rim = self._rim_tangent(r, t_on, S, Xl)
            L["tube_O"] = self._tube_hermite(r, t_on, X_rim, D_rim, X_ja, D_ja)

    def _tube(self, r, tau, S, Xl, X_ja, D_ja, M):
        """設計28 の _tube と同じ。試行C で tube_blend_shape = quintic の時は Hermite → 形の移しの重みを 5 次の smootherstep
        （両端で一階・二階微分 0）にし、tube_follows_curl_linearly の時は Hermite を _tube_hermite（巻き下がりを線形に足す）にする。"""
        if not (getattr(self, "tube_quintic", False) or getattr(self, "tube_curl_linear", False) or getattr(self, "tube_capture", "onset") != "onset"):
            return M8.Generator._tube(self, r, tau, S, Xl, X_ja, D_ja, M)
        L = self.lip[r]
        st = self.seam_tube[r]
        X_rim, D_rim = self._rim_tangent(r, tau, S, Xl)
        Ht = self._tube_hermite(r, tau, X_rim, D_rim, X_ja, D_ja)
        x = min(max((tau - self._tube_t_capture(r)) / self.tube_bl, 0.0), 1.0)
        bt = x ** 3 * (x * (6 * x - 15) + 10) if self.tube_quintic else x * x * (3 - 2 * x)
        if bt <= 0.0 or "tube_O" not in L:
            return Ht
        Ms = M if self.sw["ds_tube_shape"] else 0.0
        B = (1.0 - Ms) * L["tube_O"] + Ms * st.K
        uu = np.linspace(0.0, 1.0, len(B))[:, None]
        TM = B + (1.0 - uu) * (X_rim - B[0])[None] + uu * (X_ja - B[-1])[None]
        return (1.0 - bt) * Ht + bt * TM

    # ------------------------------------------------------------ 形
    def _carry_params(self):
        MB.Generator._carry_params(self)
        if not self.curl_on:
            return
        C = self.RC["lip_curl_with_extension"]
        V = self.VC
        self.f_free = float(V.get("free_release_fraction_of_T_row", C["free_release_fraction_of_T_row"]))
        self.T_free = self.f_free * self.T_row
        self.dec_a = float(V.get("prerelease_decel_mps2", C["prerelease_decel_mps2"]))
        self.dec_T = float(V.get("prerelease_decel_ramp_s", C["prerelease_decel_ramp_s"]))
        self.curl_gam = float(V.get("gamma_c_per_s", 0.0))
        # C2：頂の上昇に付いて上がらない分（頂の上昇の速さ y_c' に S((τ − τ_q)/T_q) を掛けて積分し、t* で 1 にする）。
        # 行ごとの τ_q = σ_q + lag_r。1 ms の格子で積分し、値は 3 次 Hermite（格子の点の傾き＝被積分関数）で補間する
        self.q_sig = float(V.get("lag_start_sigma", self.sig_b))
        self.q_ramp = float(V.get("lag_ramp_s", self.c_tup))
        self.tau_q = self.q_sig + self.lag
        self._qg = None
        if self.curl_kind == "crest_lag":
            rows = np.array(sorted(int(r) for r in self.lip_rows), int)
            dt = 1e-3
            t0 = float(np.min(self.tau_q[rows])) - 0.01
            tg = np.round(np.arange(t0, 0.02 + 1e-12, dt), 9)
            Yc = np.stack([self.crest(float(t))[1][rows] for t in tg], 0)
            v = np.gradient(Yc, tg, axis=0)
            acc = np.gradient(v, tg, axis=0)
            x = (tg[:, None] - self.tau_q[rows][None, :]) / self.q_ramp
            xc = np.clip(x, 0.0, 1.0)
            S = xc * xc * (3 - 2 * xc)
            dS = np.where((x > 0) & (x < 1), 6 * xc * (1 - xc) / self.q_ramp, 0.0)
            psi = S * v
            dpsi = dS * v + S * acc
            Phi = np.concatenate([np.zeros((1, len(rows))), np.cumsum(0.5 * (psi[1:] + psi[:-1]) * dt, 0)], 0)
            k0 = int(np.argmin(np.abs(tg)))
            norm = Phi[k0]
            self._qg = dict(t=tg, dt=dt, rows={int(r): j for j, r in enumerate(rows)}, Phi=Phi / norm, psi=psi / norm, dpsi=dpsi / norm,
                            span_m=norm)

    def crest_progress(self, r, tau, deriv=True):
        """Q = ∫ S((t − τ_q)/T_q)·y_c'(t) dt（τ_q から τ まで）を t* で 1 にしたもの。戻り (Q, Q', Q'')。"""
        if float(tau) <= float(self.tau_q[r]):
            return 0.0, 0.0, 0.0
        G_ = self._qg
        j = G_["rows"][int(r)]
        tg = G_["t"]
        u = (float(tau) - tg[0]) / G_["dt"]
        k = int(min(max(math.floor(u), 0), len(tg) - 2))
        s = u - k
        h = G_["dt"]
        p0, p1 = G_["Phi"][k, j], G_["Phi"][k + 1, j]
        m0, m1 = G_["psi"][k, j], G_["psi"][k + 1, j]
        h00 = 2 * s ** 3 - 3 * s ** 2 + 1
        h10 = s ** 3 - 2 * s ** 2 + s
        h01 = -2 * s ** 3 + 3 * s ** 2
        h11 = s ** 3 - s ** 2
        Q = h00 * p0 + h10 * h * m0 + h01 * p1 + h11 * h * m1
        if not deriv:
            return float(Q), 0.0, 0.0
        dQ = (1 - s) * m0 + s * m1
        d2Q = (1 - s) * G_["dpsi"][k, j] + s * G_["dpsi"][k + 1, j]
        return float(Q), float(dQ), float(d2Q)

    def lin_progress(self, r, tau):
        """伸び出しの進みの形（運びの始まりから t_up で立ち上がり、その後 (1 + γ_c·経過) で増える速さ）を t* で 1 にしたもの。γ_c = 0 で P そのもの。"""
        Phi, psi, dpsi = MB.carry_shape(float(tau) - float(self.tau_b[r]), self.c_tup, self.curl_gam)
        P1 = MB.carry_shape(-float(self.tau_b[r]), self.c_tup, self.curl_gam)[0]
        return Phi / P1, psi / P1, dpsi / P1

    def curl_shape(self, r, tau, deriv=True):
        """巻き下がりの形 (Φc, Φc', Φc'')。t* で 1。"""
        k = self.curl_kind
        P, dP, d2P = self.lin_progress(r, tau)
        if k == "extension":
            return P, dP, d2P
        if k == "lead_quadratic":
            q = 1.0 - P
            return 1.0 - q * q, 2 * q * dP, 2 * q * d2P - 2 * dP * dP
        mu = self.curl_mu
        Q, dQ, d2Q = self.crest_progress(r, tau, deriv)
        return (1 - mu) * P + mu * Q, (1 - mu) * dP + mu * dQ, (1 - mu) * d2P + mu * d2Q

    def eta_shape(self, r, tau):
        if not self.curl_on:
            return MB.Generator.eta_shape(self, r, tau)
        return self.curl_shape(r, tau)

    def _lip_setup(self):
        MB.Generator._lip_setup(self)
        if not (self.curl_on and self.curl_kind == "crest_lag"):
            return
        # C2：点ごとの μ_i。頂に付いて上がらない割合 λ_i = μ_i·|Aη_i|/span_r（span_r = ∫S·y_c' dt、m）が lag_cap を超える点
        # （K* で頂から遠くへ下がる下面・rim の点）は、μ_i を下げる。λ_i > 1 だと、頂の上昇が止まる区間（y_c'' < 0）で
        # 点の上下の加速度 y_c''·(1 − λ_i·S) が上向きになる（頂点の後のブレーキ）。t* の位置の条件（v2 = V0）は保つ：
        # 振幅は Aη_i·D_i（D = Φ + Φ'·Tc + Φ''·E、放出の時の形）が変わらないように解き直す
        cap = float(self.VC.get("lag_cap", 0.9))
        wpow = float(self.VC.get("lag_row_weight_power", 1.0))
        mu0 = self.curl_mu
        jr = self._qg["rows"]
        for r in self.lip_carry_rows:
            L = self.lip[r]
            n = len(L["cols"])
            Tc, Tr = L["Tc"], L["Tr"]
            IS, ISg = MB.integ_S(Tc, Tr)
            E = Tc ** 2 / 2 - ISg
            sp = float(self._qg["span_m"][jr[int(r)]])
            mu_i = np.full(n, mu0)
            AP = np.zeros(n)
            AQ = np.zeros(n)
            Aeta_new = L["Aeta"].copy()
            P0, V0, A0v = L["P0"].copy(), L["V0"].copy(), L["A0"].copy()
            for i in range(n):
                t0 = -float(Tc[i])
                fP, pP, dP = self.lin_progress(r, t0)
                fQ, pQ, dQ = self.crest_progress(r, t0)
                DP = fP + pP * Tc[i] + dP * E[i]
                DQ = fQ + pQ * Tc[i] + dQ * E[i]
                D0 = (1 - mu0) * DP + mu0 * DQ
                R = float(L["Aeta"][i]) * D0
                # μ_i：下がる点（R < 0）だけ頂の上昇に遅れさせる（上がる点に遅れは意味がなく、κ < 1 の端の行で上がる点と下がる点が隣り合って
                # 途中で開き、面が裏返った（試行C 初回：行 196・197、τ −2.63〜−1.2、111 個））。行の重み w_r も掛ける
                mu = mu0 * float(L.get("carry_w", 1.0)) ** wpow if R < 0.0 else 0.0
                if R < 0.0 and mu * abs(R) / (((1 - mu) * DP + mu * DQ) * sp) > cap:
                    den = abs(R) - cap * sp * (DQ - DP)
                    if den > 0.0:
                        mu = min(mu, max(0.0, cap * sp * DP / den))
                D1 = (1 - mu) * DP + mu * DQ
                a1 = R / D1
                f0 = (1 - mu0) * fP + mu0 * fQ
                p0_ = (1 - mu0) * pP + mu0 * pQ
                d0 = (1 - mu0) * dP + mu0 * dQ
                f1 = (1 - mu) * fP + mu * fQ
                p1_ = (1 - mu) * pP + mu * pQ
                d1 = (1 - mu) * dP + mu * dQ
                a0 = float(L["Aeta"][i])
                P0[i, 1] += a1 * f1 - a0 * f0
                V0[i, 1] += a1 * p1_ - a0 * p0_
                A0v[i, 1] += a1 * d1 - a0 * d0
                mu_i[i] = mu
                Aeta_new[i] = a1
                AP[i] = a1 * (1 - mu)
                AQ[i] = a1 * mu
            Kt = L["Kt"]
            v2 = (Kt - P0 - V0 * (Tc - IS)[:, None] - A0v * (Tc ** 2 / 2 - ISg)[:, None] + np.stack([np.zeros(n), MD.G * ISg], 1)) / IS[:, None]
            # 放出の時の速さと打ち出しの速さの差（押し）は変わらない（v2 = V0 の行は 0 のまま）
            assert float(np.abs((v2 - V0) - L["kick"]).max()) < 1e-6, "C2 の μ_i の解き直しで打ち出しの押しが変わった（行 %d）" % r
            L.update(P0=P0, V0=V0, A0=A0v, v2=v2, kick=v2 - V0, Aeta=Aeta_new, A_P=AP, A_Q=AQ, mu_i=mu_i, lag_span_m=sp,
                     lag_lambda=mu_i * np.maximum(-Aeta_new, 0.0) / sp)

    def _carry_offset(self, r, tau):
        if not self.curl_on or self.curl_kind != "crest_lag":
            return MB.Generator._carry_offset(self, r, tau)
        L = self.lip[r]
        Pxi = self.xi_shape(r, tau)[0]
        P = self.lin_progress(r, tau)[0]
        Q = self.crest_progress(r, tau, deriv=False)[0]
        off = np.stack([L["Axi"] * Pxi, L["A_P"] * P + L["A_Q"] * Q], 1)
        if self.dec_a > 0.0:
            off[:, 1] -= L["wdec"] * self._dec_shape(tau, L["t_dec0"])[0]
        if self.claws_follow:
            off = off + (L["a_claw"] * self.claw_progress(r, tau)[0])[:, None] * L["dn"]
        return off

    # ------------------------------------------------------------ 記録
    def launch_table(self, rows=None):
        out = MB.Generator.launch_table(self, rows)
        if not self.curl_on:
            return out
        for k, ent in out.items():
            r = int(k)
            L = self.lip.get(r)
            if L is None or not L.get("carry"):
                continue
            it = int(L["tip"]) - int(L["root"]) - 1
            Tc = float(L["Tc"][it])
            if self.curl_kind == "crest_lag":
                P = self.lin_progress(r, -Tc)
                Q = self.crest_progress(r, -Tc)
                aP, aQ = float(L["A_P"][it]), float(L["A_Q"][it])
                f0, f1, f2 = (aP * P[k] + aQ * Q[k] for k in range(3))
                ent.update(curl_mu_tip=float(L["mu_i"][it]), curl_lambda_tip=float(L["lag_lambda"][it]),
                           curl_mu_min_row=float(np.min(L["mu_i"])), curl_lambda_max_row=float(np.max(L["lag_lambda"])))
            else:
                a_ = float(L["Aeta"][it])
                f0, f1, f2 = (a_ * v for v in self.curl_shape(r, -Tc))
            ent.update(curl_shape=self.curl_kind, curl_Aeta_m=float(L["Aeta"][it]),
                       curl_offset_at_release_m=float(f0), curl_relative_down_speed_at_release_mps=float(-f1),
                       curl_offset_accel_at_release_mps2=float(f2))
            ent.pop("carry_Aeta_mps", None)
        return out

    def summary(self):
        s = MB.Generator.summary(self)
        s.update(number="設計28修正01 試行C", ds_lip_curl_with_extension=bool(self.curl_on), curl_variant=self.curl_variant if self.curl_on else None,
                 curl_shape=self.curl_kind if self.curl_on else None, crest_lag_mu=self.curl_mu if self.curl_on and self.curl_kind == "crest_lag" else None,
                 r01c_params_sha256=self.c_sha, r01c_base_sha256=self.c_base_shas)
        if self.curl_on:
            s.update(free_release_fraction=self.f_free, prerelease_decel_mps2=self.dec_a, prerelease_decel_ramp_s=self.dec_T,
                     curl_gamma_per_s=self.curl_gam, lag_start_sigma=self.q_sig if self.curl_kind == "crest_lag" else None,
                     lag_ramp_s=self.q_ramp if self.curl_kind == "crest_lag" else None,
                     free_release_tip_tau={str(r): round(-float(self.T_free[r]), 4) for r in (int(self.K.main_row), 192)})
            am = [float(np.min(self.lip[r]["Aeta"])) for r in self.lip_carry_rows]
            aM = [float(np.max(self.lip[r]["Aeta"])) for r in self.lip_carry_rows]
            s.update(curl_Aeta_min=min(am) if am else None, curl_Aeta_max=max(aM) if aM else None)
        return s
