# -*- coding: utf-8 -*-
"""設計28修正01 試行B（Q13）：唇（爪を含む）の伸び出しを、頂の上昇の後半へ早める生成器。

README
======
設計28 の生成器（Tools/GWWaveGen/ds28/ds28_physoff.py の Generator＝ds28_model.Generator に ds_crest_tower・ds_undercut_kstar を
足したもの）を import し、唇（層4）の放出の前の動きと放出の時刻だけを上書きする。設計26〜28 のファイルは変えない
（ds28r01b_params.json の base の SHA-256 を照合する代わりに、読み込む時に SHA-256 を記録し、ds28_params.json の SHA-256 は
設計28 の記録の値と照合する）。試行A（Tools/GWWaveGen/ds28r01/）の生成器は使わない。

Q13（利用者、2026-09-27）：原画の手前の爪の形の大きな部分（唇と爪）が、波が最も高くなった後に伸び出すのがおかしい。唇（爪を含む）は、
平らな海から最高点へ育つ過程の後半に、もう伸び始めているべき。

変えないもの（物理の入力と設計28 の見え方）：頂の高さの時刻（設計28 の S 字の上昇）、段階 a・b の塔、進み方（c0・β・波の枠）、
較正の噴流の始まり（頂の減速・段階の時計 σ・錨・管の形の始まり）、t* = K*、白の時刻。

足した美術の誘導（名前の付いた値。ds28r01b_params.json）：
  ds_lip_carry（唇の運び）：唇の点を、放出の前に頂に付いたまま前へ運ぶ。点 i（行 r）の放出の前の位置（地面）＝
      設計28 の放出の前の位置 B_i(τ)（κ = 1 の行は帯、κ < 1 の行は帯と本体の前面の混ぜ）＋ (Aξ_i·Φξ_r(τ), Aη_i·Φη_r(τ))。
      Φξ：運びの始まり τ_b,r（段階の時計 σ_b、変種ごと）から、頂に対する前への速さ ψξ = S((τ − τ_b)/t_up)·(1 + γ·(τ − τ_b))。
      Φη：頂の上昇が止まる区間（σ −2.9〜−2.4）で、頂に対する上下の速さ ψη = S((σ + 2.9)/0.5)（その後 1）。
      放出（自由な飛行の始まり）T_i = f·T_row·(1 − s_i)^p（κ < 1 の行はさらに κ 倍）。振幅は、放出の時に打ち出しの補間が速さを
      変えない（v2 = V0）ように点ごとに一次式で解く：
        Aξ_i·(Φξ_r + ψξ_r·Tc + ψξ'_r·E) = (K_i − δn_i)_x − (B_i + B_i'·Tc + B_i''·E)_x
        Aη_i·(Φη_r + ψη_r·Tc + ψη'_r·E) = (K_i − δn_i)_y − (B_i + B_i'·Tc + B_i''·E)_y + g·ISg(Tc)
      （E = Tc²/2 − ISg、ISg は設計26 の放出の補間の重力の積分）。放出の後は設計28 の式（重力だけ）。
  ds_claws_follow_lip（爪は唇とともに育つ）：K* の唇の爪・鉤の細部 δn_i（列の方向のガウス σ 8 列でならした線からの法線の差。
      上面と下面を分けてならす）を、運びの進み P_r(τ) = Φξ_r(τ)/Φξ_r(0) に比例させ、放出の前から持たせる。振幅 a_i は
      a_i·(P_r + P_r'·Tc + P_r''·E) = 1（放出の後も細部は重力だけの一次の動きで t* に δn_i へ着く）。
      切ると細部は設計28 と同じく打ち出しの速さへ入り（v2 = V0 + δn_i/IS）、放出の後に育つ。

使い方（numpy だけ）：
    from ds28r01b_model import Generator
    g = Generator("art_on", carry_variant="V75")                 # 試行B の変種（誘導 16 個をすべて入れる）
    g = Generator("art_on", carry_variant="V75", claws_follow=False)   # ds_claws_follow_lip だけ切る（P20）
    g = Generator("art_on", carry_variant="V75", lip_carry=False)       # 運びを切る（＝設計28 の入れた版）
    X = g.local(-2.0); T = g.twhite()
"""
import copy
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS28 = os.path.abspath(os.path.join(HERE, "..", "ds28"))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
for p in (DS27, DS28):
    if p not in sys.path:
        sys.path.insert(0, p)
import ds27_model as MD  # noqa: E402
import ds28_model as M8  # noqa: E402
import ds28_physoff as PO  # noqa: E402

REPO = MD.REPO
PARAMS_B = os.path.join(HERE, "ds28r01b_params.json")
G = MD.G
integ_S = MD.integ_S
smoothstep = MD.smoothstep
VARIANTS = ("V80", "V75", "V70")
# 設計28 の記録（Docs/Progress/Design_28_ja.md・run.json）の ds28_params.json の SHA-256 の頭。合わなければ止まる
DS28_PARAMS_SHA_HEAD = None


def load_b(path=PARAMS_B):
    R = MD.load_json(path)
    shas = {}
    for k, fn in R["base"].items():
        if k.startswith("ds2"):
            p = os.path.join(REPO, fn)
            if not os.path.isfile(p):
                raise SystemExit("[ds28r01b] base のファイルがありません：%s" % fn)
            shas[fn] = MD.sha256_file(p)
    return R, shas


def S_(x):
    x = min(max(float(x), 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def carry_shape(t, t_up, gam):
    """運びの形（経過 t ≥ 0）。戻り (Φ, ψ = Φ', ψ')。ψ = S(t/t_up)·(1 + γ t)、S = smoothstep。"""
    if t <= 0.0:
        return 0.0, 0.0, 0.0
    if t < t_up:
        x = t / t_up
        S = x * x * (3 - 2 * x)
        dS = 6 * x * (1 - x) / t_up
        Phi = t_up * ((x ** 3 - x ** 4 / 2) + gam * t_up * (0.75 * x ** 4 - 0.4 * x ** 5))
        return Phi, S * (1 + gam * t), dS * (1 + gam * t) + S * gam
    Phi0 = t_up * (0.5 + gam * t_up * 0.35)
    return Phi0 + (t - t_up) + gam * (t * t - t_up * t_up) / 2, 1 + gam * t, gam


def stall_shape(x, w):
    """上下の運びの形。x = σ − σ1（σ1 = −2.9）、w = σ2 − σ1。戻り (Φ, ψ, ψ')（σ の時計で。噴流の始まりの前は dσ/dτ = 1）。"""
    if x <= 0.0:
        return 0.0, 0.0, 0.0
    if x < w:
        u = x / w
        return w * (u ** 3 - u ** 4 / 2), u * u * (3 - 2 * u), 6 * u * (1 - u) / w
    return w / 2 + (x - w), 1.0, 0.0


def gauss_smooth_odd(P, sigma):
    """折れ線 P (n, 2) を列の方向にガウス（σ 列、両端は奇の折り返しで端点を固定）でならす。"""
    n = len(P)
    if n < 3:
        return P.copy()
    m = int(min(math.ceil(3 * sigma), n - 1))
    x = np.arange(-m, m + 1, dtype=float)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    head = 2 * P[0] - P[m:0:-1]
    tail = 2 * P[-1] - P[-2:-m - 2:-1]
    Pp = np.concatenate([head, P, tail], 0)
    return np.stack([np.convolve(Pp[:, i], k, mode="valid") for i in range(2)], 1)


def normal_detail(P, sigma):
    """折れ線 P の細部：ならした線 Sm からの差の、Sm の法線の向きの成分（ベクトル）。端点は 0。"""
    Sm = gauss_smooth_odd(P, sigma)
    T = np.gradient(Sm, axis=0)
    tl = np.linalg.norm(T, axis=1)
    nrm = np.stack([-T[:, 1], T[:, 0]], 1) / np.maximum(tl, 1e-12)[:, None]
    dn = ((P - Sm) * nrm).sum(1)
    dn[tl < 1e-9] = 0.0
    out = dn[:, None] * nrm
    out[0] = 0.0
    out[-1] = 0.0
    return out


class Generator(PO.Generator):
    """設計28 の生成器（ds28_physoff.Generator）＋ ds_lip_carry・ds_claws_follow_lip（試行B）。"""

    def __init__(self, version="art_on", carry_variant="V75", params_path=M8.PARAMS_JSON, log=None, switches=None, crest_tower=None,
                 undercut_kstar=None, lip_carry=None, claws_follow=None, b_path=PARAMS_B, overrides=None):
        self.RB, self.base_shas = load_b(b_path)
        if overrides:
            M8.deep_merge(self.RB, overrides)
        self.b_path = b_path
        self.b_sha = MD.sha256_file(b_path)
        if carry_variant not in self.RB["variants"]:
            raise ValueError("変種は %s のどれか" % ",".join(self.RB["variants"]))
        self.carry_variant = carry_variant
        self.VB = self.RB["variants"][carry_variant]
        self.lip_carry = (version == "art_on") if lip_carry is None else bool(lip_carry)
        self.claws_follow = (self.lip_carry and version == "art_on") if claws_follow is None else bool(claws_follow)
        if self.claws_follow and not self.lip_carry:
            raise ValueError("ds_claws_follow_lip は ds_lip_carry を入れた時だけ")
        self.kappa_strip = float(self.RB["lip_carry"].get("kappa_as_strip_from", 1.0)) if self.lip_carry else 1.0
        U = self.RB["lip_carry"]["undercut"]
        self.u_lead = float(self.VB.get("undercut_lead_s", 0.0)) if self.lip_carry else 0.0
        self.u_keep = float(self.VB.get("undercut_keep_until_sigma", U["keep_until_sigma"]))
        self.u_width = float(self.VB.get("undercut_width_s", U["width_s"]))
        PO.Generator.__init__(self, version, params_path=params_path, log=log, switches=switches, crest_tower=crest_tower,
                              undercut_kstar=undercut_kstar)
        tag = []
        if self.lip_carry:
            tag.append("ds_lip_carry=%s" % carry_variant)
        if self.lip_carry and not self.claws_follow:
            tag.append("ds_claws_follow_lip=0")
        if tag:
            self.variant = self.variant + "+" + "+".join(tag)

    # ------------------------------------------------------------ 形（行ごと）
    def _carry_params(self):
        C = self.RB["lip_carry"]
        self.f_free = float(C["free_release_fraction_of_T_row"])
        self.Tr_carry = float(C["release_ramp_max_s"])
        self.dec_a = float(C["vertical"].get("prerelease_decel_mps2", 0.0))
        self.dec_T = float(C["vertical"].get("prerelease_decel_ramp_s", 0.5))
        self.c_tup = float(C["horizontal"]["t_up_s"])
        self.c_gam = float(C["horizontal"]["gamma_per_s"])
        s1, s2 = C["vertical"]["stall_sigma"]
        self.st1, self.st_w = float(s1), float(s2) - float(s1)
        assert abs(float(s2) + 2.4) < 1e-12, "上下の運びは σ −2.4（噴流の始まり）で終わる約束"
        self.sig_b = float(self.VB["carry_start_sigma"])
        assert self.sig_b < -2.4
        self.claw_sigma = float(self.RB["claws_follow_lip"]["sigma_cols"])
        self.kappa_strip = float(self.RB["lip_carry"].get("kappa_as_strip_from", 1.0))
        self.claw_k = float(self.RB["claws_follow_lip"].get("front_load", 1.0))
        assert self.claw_k == 1.0 or self.claw_k >= 2.0, "front_load は 1 か 2 以上（二階微分が t* で有界）"
        # 行ごとの運びの始まり τ_b,r（噴流の始まりの前は σ_r = τ − lag_r）と、唇先の放出 T_free,r
        self.tau_b = self.sig_b + self.lag
        self.T_free = self.f_free * self.T_row

    def carry_weight(self, r):
        """行の運びの重み w_r = S((κ − k0)/(k1 − k0))·S((H − h0)/(h1 − h0))（S = smoothstep）。手前の端の小さい行（H 3〜7 m）と、
        奥の壁の側で κ が小さくなる行で 0 へ（0 の行は設計28 の唇のまま）。"""
        W = self.RB["lip_carry"].get("row_weight")
        if not W:
            return 1.0
        k0, k1 = W["kappa"]
        h0, h1 = W["H_m"]
        return float(S_((float(self.kappa[r]) - k0) / (k1 - k0)) * S_((float(self.H[r]) - h0) / (h1 - h0)))

    def xi_shape(self, r, tau):
        """行 r の前への運びの形（Φξ, ψξ, ψξ'）。"""
        return carry_shape(float(tau) - float(self.tau_b[r]), self.c_tup, self.c_gam)

    def eta_shape(self, r, tau):
        """行 r の上下の運びの形（Φη, ψη, ψη'）。τ の関数（噴流の始まりの後は ψη = 1、Φη は τ に一次）。"""
        Tr_ = float(self.T_row[r])
        if tau <= -Tr_:
            return stall_shape(float(tau) - float(self.lag[r]) - self.st1, self.st_w)
        Phi_on = self.st_w / 2.0
        return Phi_on + (float(tau) + Tr_), 1.0, 0.0

    def _dec_shape(self, tau, t0):
        """放出の前の減速の形（加速度 S((τ − t0)/T_pre)、その 1 回・2 回の積分）。t0 は配列でもよい。戻り (位置, 速さ, 加速度)。"""
        T = self.dec_T
        t = np.maximum(float(tau) - np.asarray(t0, np.float64), 0.0)
        x = np.minimum(t / T, 1.0)
        tl = np.maximum(t - T, 0.0)
        pos = T * T * (x ** 4 / 4 - x ** 5 / 10) + np.where(t > T, T * 0.5 * tl + 0.5 * tl ** 2, 0.0)
        vel = T * (x ** 3 - x ** 4 / 2) + tl
        acc = x * x * (3 - 2 * x)
        return pos, vel, acc

    def claw_progress(self, r, tau):
        """爪の細部の進み P_c = 1 − (1 − P)^k（k = claws_follow_lip.front_load。k = 1 で運びの進み P そのもの）と、τ の一階・二階微分。"""
        P, dP, d2P = self.lip_progress(r, tau)
        k = self.claw_k
        if k == 1.0:
            return P, dP, d2P
        q = max(1.0 - P, 0.0)
        return 1.0 - q ** k, k * q ** (k - 1) * dP, k * q ** (k - 1) * d2P - k * (k - 1) * q ** (k - 2) * dP * dP if q > 0 else 0.0

    def lip_progress(self, r, tau):
        """運びの進み P_r(τ) = Φξ(τ)/Φξ(0)、と τ の一階・二階微分。"""
        Phi, psi, dpsi = self.xi_shape(r, tau)
        P1 = self.xi_shape(r, 0.0)[0]
        return Phi / P1, psi / P1, dpsi / P1

    # ------------------------------------------------------------ 放出の前の位置（地面）
    def _base_prerelease_local(self, r, tau, S, Bu=None):
        """設計28 の放出の前の唇の点の局所の位置（κ = 1 の行は帯、κ < 1 の行は帯と本体の前面の混ぜ）。(n, 2)。"""
        if self.kappa[r] >= self.kappa_strip:
            return M8.Generator._strip_local(self, r, tau, S)
        return M8.Generator._prerelease_local(self, r, tau, S, Bu)

    def _carry_offset(self, r, tau):
        """運びと爪の細部の足し分（地面＝局所で同じ）。(n, 2)。"""
        L = self.lip[r]
        Pxi = self.xi_shape(r, tau)[0]
        Peta = self.eta_shape(r, tau)[0]
        off = np.stack([L["Axi"] * Pxi, L["Aeta"] * Peta], 1)
        if self.dec_a > 0.0:
            off[:, 1] -= L["wdec"] * self._dec_shape(tau, L["t_dec0"])[0]
        if self.claws_follow:
            off = off + (L["a_claw"] * self.claw_progress(r, tau)[0])[:, None] * L["dn"]
        return off

    def _prerelease_local(self, r, tau, S=None, Bu=None):
        L = self.lip[r]
        if not L.get("carry"):
            return M8.Generator._prerelease_local(self, r, tau, S, Bu)
        if S is None:
            S = self._shared(tau)
        return self._base_prerelease_local(r, tau, S, Bu) + self._carry_offset(r, tau)

    # ------------------------------------------------------------ 唇（層4）
    def _lip_setup(self):
        self._cw = {}
        if self.lip_carry:
            # 行の運びの重み（錨の時計の早めにも使うので、設計28 の唇の準備（κ < 1 の行は本体の前面 Bu を読む）より前に決める）
            self._cw = {int(r): self.carry_weight(int(r)) for r in self.lip_rows}
        M8.Generator._lip_setup(self)
        self.lip_carry_rows = []
        if not self.lip_carry:
            return
        self._carry_params()
        lp = self.P["lip"]
        kl = self.kl
        gp = float(kl["release_power"])
        k0 = float(kl.get("kappa_delay_below", 0.0))
        h = float(kl["derivative_h_s"])
        for r in sorted(self.lip.keys()):
            L = self.lip[r]
            kap = float(self.kappa[r])
            n = len(L["cols"])
            L["Ti28"], L["Tc28"], L["Tr28"] = L["Ti"].copy(), L["Tc"].copy(), L["Tr"].copy()
            wr = self._cw[int(r)]
            L["carry_w"] = wr
            if wr <= 1e-6:
                continue                  # 運ばない行（手前の端の小さい行・奥の壁の側の κ の小さい行）：設計28 の唇のまま
            fac = 1.0
            if kap < 1.0 and kl.get("mode") == "launch_damping":
                fac = min(1.0, kap / k0) ** gp if k0 > 0 else kap ** gp
            Tf = float(self.T_free[r])
            Ti = Tf * np.clip(1.0 - L["s"], 0.0, 1.0) ** self.p_rel * fac
            Ti = L["Ti28"] + wr * (Ti - L["Ti28"])        # 重みの途中の行は設計28 の放出の時刻と混ぜる
            Tc = np.maximum(Ti, float(lp["Tc_min_s"]))
            Tr28r = np.minimum(self.Tr_max, Tc / 2)
            if kap < 1.0 and self.e4_curled[r] and kl.get("curled_ramp_end_by_table", False) and kap < float(kl["ramp_limit_below_kappa"]):
                # 設計28 の curled_ramp_end_by_table（K* で巻く κ < 0.9 の行の補間を表の打ち出しの補間の終わりまでに終える）を、混ぜた放出の時刻にも当てる。
                # 修正2 の後の不具合の直し：初回の修正2 ではこの規則を落とし、重み 0.016 の行 60 の補間が関門 P16 の窓の中で続いた（P16 +0.405・+1.707 m/s²）
                T_row = float(self.T_row[r])
                lim = Tc - T_row + min(self.Tr_max, T_row / 2)
                Tr28r = np.where(lim >= float(kl["ramp_min_s"]), np.minimum(Tr28r, lim), Tr28r)
            Tr = (1.0 - wr) * Tr28r + wr * np.minimum(self.Tr_carry, Tc / 2)
            assert float(self.tau_b[r]) < -float(Tc.max()) - 0.05, "運びは放出より前に始まる約束（行 %d）" % r
            # --- 設計28 の放出の前の位置 B と速さ・加速度（地面、放出の時刻で）
            Bp = np.zeros((n, 2))
            Bv = np.zeros((n, 2))
            Ba = np.zeros((n, 2))
            L["carry"] = False            # 下の B は運びなし（_prerelease_local が設計28 の値を返す）
            L["mode"] = "damped_setup"
            cache = {}
            for i in range(n):
                t0 = -float(Tc[i])
                if kap >= self.kappa_strip:
                    # κ = 1 の行（と κ ≥ kappa_strip の行）：帯（頂の地面の位置＋帯の置き場）。放出は噴流の始まりの後なので、頂の地面の動きは解析的
                    T_ = float(Tc[i])
                    Trow = float(self.T_row[r])
                    assert T_ <= Trow + 1e-9
                    if t0 not in cache:
                        Sx = self._shared(t0)
                        loc = M8.Generator._strip_local(self, r, t0, Sx)
                        fo = self._frame_offset(r, T_, Sx["Dpk"])
                        g_ = loc.copy()
                        g_[:, 0] -= fo
                        vx = self.beta * self.c0 + (1 - self.beta) * self.c0 * T_ / Trow
                        ax = -(1 - self.beta) * self.c0 / Trow
                        cache[t0] = (g_, np.array([vx, float(self.vH_r[r])]), np.array([ax, 0.0]))
                    g_, v_, a_ = cache[t0]
                    Bp[i], Bv[i], Ba[i] = g_[i], v_, a_
                else:
                    pts = []
                    for dt in (-h, 0.0, h):
                        tt = round(min(t0 + dt, 0.0), 12)
                        if tt not in cache:
                            Sx = self._shared(tt)
                            loc = M8.Generator._prerelease_local(self, r, tt, Sx)
                            cache[tt] = (loc, self._frame_offset(r, -tt, Sx["Dpk"]))
                        loc, fo = cache[tt]
                        g_ = loc[i].copy()
                        g_[0] -= fo
                        pts.append(g_)
                    Bp[i] = pts[1]
                    Bv[i] = (pts[2] - pts[0]) / (2 * h)
                    Ba[i] = (pts[2] - 2 * pts[1] + pts[0]) / (h * h)
            # --- 放出の前の減速（上下）：点 i の放出の T_pre 前から、上向きの加速度 −a_d·w_i·S(·) を足す（w_i = (1 − s_i)²、唇先で 1、頂で 0）。
            #     唇の水の上がりが放出の前に弱まり、放出の補間で重力へ移る。振幅 Aη はこの項を含めて v2 = V0 に解く
            wdec = self.dec_a * np.clip(1.0 - L["s"], 0.0, 1.0) ** 2
            L["wdec"] = wdec
            L["t_dec0"] = -Tc - self.dec_T
            dq = np.stack([self._dec_shape(float(-Tc[i]), float(L["t_dec0"][i])) for i in range(n)], 0)
            Bp[:, 1] -= wdec * dq[:, 0]
            Bv[:, 1] -= wdec * dq[:, 1]
            Ba[:, 1] -= wdec * dq[:, 2]
            # --- 爪・鉤の細部 δn（K* の唇。ds_claws を切った版は Kt がもうならしてあるので δn はほぼ 0）
            Kt = L["Kt"]
            it = int(L["tip"]) - int(L["root"]) - 1          # 唇先の点の番号（cols は root+1..rim）
            Kfull = np.concatenate([np.array([[self.K.A[r, int(L["root"])], self.K.Y[r, int(L["root"])]]]), Kt], 0)   # 頂＋唇
            up = Kfull[:it + 2]                               # 頂..唇先
            un = Kfull[it + 1:]                               # 唇先..rim
            dn = np.zeros((n + 1, 2))
            dn[:it + 2] = normal_detail(up, self.claw_sigma)
            dn[it + 1:] += normal_detail(un, self.claw_sigma)
            dn = dn[1:]
            # --- 振幅を解く（放出の時に v2 = V0）
            IS, ISg = integ_S(Tc, Tr)
            E = Tc ** 2 / 2 - ISg
            Axi = np.zeros(n)
            Aeta = np.zeros(n)
            acl = np.zeros(n)
            shp = np.zeros((n, 9))
            for i in range(n):
                t0 = -float(Tc[i])
                fx, px, dpx = self.xi_shape(r, t0)
                fe, pe, dpe = self.eta_shape(r, t0)
                fc, pc, dpc = self.claw_progress(r, t0)
                shp[i] = (fx, px, dpx, fe, pe, dpe, fc, pc, dpc)
                tgt = Kt[i] - dn[i]
                rest = tgt - Bp[i] - Bv[i] * Tc[i] - Ba[i] * E[i] + np.array([0.0, G * ISg[i]])
                Axi[i] = rest[0] / (fx + px * Tc[i] + dpx * E[i])
                Aeta[i] = rest[1] / (fe + pe * Tc[i] + dpe * E[i])
                acl[i] = 1.0 / (fc + pc * Tc[i] + dpc * E[i])
            if not self.claws_follow:
                acl[:] = 0.0
            if wr < 1.0:
                # 重みの途中の行：運び・爪・放出の前の減速を重み倍にし、残りは設計28 と同じく打ち出しの速さ（v2 の一次式）で K* へ
                Bp[:, 1] += (1.0 - wr) * wdec * dq[:, 0]
                Bv[:, 1] += (1.0 - wr) * wdec * dq[:, 1]
                Ba[:, 1] += (1.0 - wr) * wdec * dq[:, 2]
                wdec = wdec * wr
                L["wdec"] = wdec
                Axi, Aeta, acl = Axi * wr, Aeta * wr, acl * wr
            P0 = Bp + np.stack([Axi * shp[:, 0], Aeta * shp[:, 3]], 1) + (acl * shp[:, 6])[:, None] * dn
            V0 = Bv + np.stack([Axi * shp[:, 1], Aeta * shp[:, 4]], 1) + (acl * shp[:, 7])[:, None] * dn
            A0v = Ba + np.stack([Axi * shp[:, 2], Aeta * shp[:, 5]], 1) + (acl * shp[:, 8])[:, None] * dn
            # 打ち出しの速さ：設計28 と同じ一次式で K* へ（運びの振幅を上の式で解いたので、v2 = V0。細部を運ばない時は v2 = V0 + δn/IS）
            v2 = (Kt - P0 - V0 * (Tc - IS)[:, None] - A0v * (Tc ** 2 / 2 - ISg)[:, None] + np.stack([np.zeros(n), G * ISg], 1)) / IS[:, None]
            L.update(mode="damped", carry=True, Ti=Ti, Tc=Tc, Tr=Tr, P0=P0, V0=V0, A0=A0v, v2=v2, Axi=Axi, Aeta=Aeta, a_claw=acl, dn=dn,
                     kick=v2 - V0, release_power=gp, tip_index=it, B_release=Bp)
            self.lip_carry_rows.append(int(r))

    # 放出の後の位置は M8.Generator.lip_state（mode "damped"）のまま

    # ------------------------------------------------------------ 唇の下のえぐり（ds_lip_carry の一部）：錨が q_on へ寄る時計を段階 b の後だけ早める
    def anchor_q(self, r, tau, sig_r, M):
        kap = float(self.kappa[r]) * float(getattr(self, "_cw", {}).get(int(r), 0.0))
        if self.lip_carry and sig_r < -2.4 and self.u_lead > 0.0 and kap > 0.0:
            # 唇のある行だけ、κ の重みで（唇のない奥の壁・手前の端の行の前面は設計28 のまま）
            sa = sig_r + kap * self.u_lead * S_((sig_r - self.u_keep) / self.u_width)
            return M8.Generator.anchor_q(self, r, tau, min(sa, -2.4 - 1e-9), M)
        return M8.Generator.anchor_q(self, r, tau, sig_r, M)

    # ------------------------------------------------------------ 始まりの後の進み（錨・管）：κ = 1 の行は設計28 と同じく rim の進み
    def _rim_local_a(self, r, tau, S):
        L = self.lip[r]
        if not L.get("carry"):
            return M8.Generator._rim_local_a(self, r, tau, S)
        Xg, rel, off = self.lip_state(r, tau, S["sig"][r])
        i = len(L["cols"]) - 1
        if rel[i]:
            return float(Xg[i, 0] + self._frame_offset(r, S["T"], S["Dpk"]))
        return float(self._prerelease_local(r, tau, S)[i, 0])

    def progress(self, r, tau, S):
        L = self.lip.get(r)
        if L is not None and L.get("carry") and self.kappa[r] >= self.kappa_strip:
            Tr = float(self.T_row[r])
            if tau <= -Tr:
                return 0.0
            if L.get("rim_span", 0.0) >= self.rim_min:
                a = self._rim_local_a(r, tau, S)
                return float(min(max((a - L["rim_a_on"]) / L["rim_span"], 0.0), 1.0))
            u = min(max((tau + Tr) / Tr, 0.0), 1.0)
            return float(smoothstep(u))
        return M8.Generator.progress(self, r, tau, S)

    def _onset_setup(self):
        for r in sorted(self.lip.keys()):
            L = self.lip[r]
            if L.get("carry") and self.kappa[r] >= self.kappa_strip:
                t_on = -float(self.T_row[r])
                S = self._shared(t_on)
                L["rim_a_on"] = self._rim_local_a(r, t_on, S)
                L["rim_span"] = float(self.K.A[r, int(L["rim"])] - L["rim_a_on"])
        M8.Generator._onset_setup(self)

    # ------------------------------------------------------------ 白（色だけ）：設計28 と同じ時刻
    def twhite(self):
        if not self.lip_carry:
            return PO.Generator.twhite(self)
        keep = {}
        for r, L in self.lip.items():
            if L.get("carry"):
                keep[r] = (L["Ti"], L["Tc"])
                L["Ti"], L["Tc"] = L["Ti28"], L["Tc28"]
        try:
            return PO.Generator.twhite(self)
        finally:
            for r, (a, b) in keep.items():
                self.lip[r]["Ti"], self.lip[r]["Tc"] = a, b

    # ------------------------------------------------------------ 記録
    def tip_track(self, r, taus):
        """行 r の唇先（K* の唇先の列の点）の地面と局所の位置・頂の位置（記録・調整用）。"""
        L = self.lip[r]
        it = int(L["tip"]) - int(L["root"]) - 1
        out = []
        for tv in taus:
            S = self._shared(float(tv))
            Xl, rel = self._lip_local(r, float(tv), S, None if self.kappa[r] >= 1.0 else self._bu(r, float(tv), S))
            out.append((float(Xl[it, 0]), float(Xl[it, 1]), bool(rel[it]), float(S["a_c"][r]), float(S["y_c"][r])))
        return np.array([o[0] for o in out]), np.array([o[1] for o in out]), np.array([o[2] for o in out]), np.array([o[3] for o in out]), np.array([o[4] for o in out])

    def _bu(self, r, tau, S):
        A0r = self.K.A[r].copy()
        Y0r = self.K.Y[r].copy()
        return self._front_body(r, tau, S, A0r, Y0r, self.progress(r, tau, S))[0]

    def launch_table(self, rows=None):
        """行ごとの唇先の運び・放出・打ち出し・頂点の記録。"""
        out = {}
        rows = rows if rows is not None else [int(self.K.main_row), 192]
        for r in rows:
            L = self.lip.get(r)
            if L is None:
                continue
            it = int(L["tip"]) - int(L["root"]) - 1
            Tc = float(L["Tc"][it])
            H = float(self.H[r])
            v = L["v2"][it]
            V0 = L["V0"][it]
            P0 = L["P0"][it]
            taus = np.round(np.linspace(-Tc, 0.0, int(round(Tc * 240)) + 1), 9)
            ys, ycs = [], []
            for tv in taus:
                Xg, rel, _ = self.lip_state(r, float(tv), float(self.sigma(float(tv))[r]))
                ys.append(float(Xg[it, 1]) if rel[it] else float(P0[1]))
                ycs.append(float(self.crest(float(tv))[1][r]))
            ys, ycs = np.array(ys), np.array(ycs)
            k = int(np.argmax(ys))
            ent = dict(c_m=float(self.K.c[r]), H_kstar_m=H, kappa=float(self.kappa[r]), T_row_s=float(self.T_row[r]),
                       release_tau=-Tc, ramp_s=float(L["Tr"][it]), flight_s=Tc, release_y_m=float(P0[1]),
                       crest_at_release_over_H=float(self.crest(-Tc)[1][r] / H),
                       prerelease_vel=[float(V0[0]), float(V0[1])], launch_u_mps=float(v[0]), launch_u_over_c0=float(v[0] / self.c0),
                       launch_w_mps=float(v[1]), launch_w_over_sqrt_gH=float(v[1] / math.sqrt(G * H)),
                       kick_mps=[float(L["kick"][it][0]), float(L["kick"][it][1])] if "kick" in L else None,
                       apex_y_m=float(ys[k]), apex_tau=float(taus[k]), crest_at_apex_m=float(ycs[k]),
                       apex_minus_crest_m=float(ys[k] - ycs[k]), max_tip_minus_crest_after_release_m=float(np.max(ys - ycs)),
                       kstar_tip=[float(L["Kt"][it][0]), float(L["Kt"][it][1])], mode=L.get("mode"), carry=bool(L.get("carry", False)))
            if L.get("carry"):
                ent.update(carry_start_tau=float(self.tau_b[r]), carry_Axi_mps=float(L["Axi"][it]), carry_Aeta_mps=float(L["Aeta"][it]),
                           claw_amp=float(L["a_claw"][it]), design28_release_tau=-float(L["Tc28"][it]),
                           relative_forward_speed_at_release_mps=float(L["Axi"][it] * self.xi_shape(r, -Tc)[1]))
            out[str(r)] = ent
        return out

    def summary(self):
        s = PO.Generator.summary(self)
        s.update(number="設計28修正01 試行B", ds_lip_carry=bool(self.lip_carry), ds_claws_follow_lip=bool(self.claws_follow),
                 carry_variant=self.carry_variant if self.lip_carry else None, r01b_params_sha256=self.b_sha, base_sha256=self.base_shas,
                 lip_carry_rows=len(getattr(self, "lip_carry_rows", [])))
        if self.lip_carry:
            kicks = np.concatenate([np.abs(self.lip[r]["kick"]).max(1) for r in self.lip_carry_rows])
            s.update(carry_start_sigma=self.sig_b, free_release_fraction=self.f_free,
                     carry_start_tau={str(r): round(float(self.tau_b[r]), 4) for r in (int(self.K.main_row), 192)},
                     free_release_tip_tau={str(r): round(-float(self.T_free[r]), 4) for r in (int(self.K.main_row), 192)},
                     max_abs_kick_mps=float(kicks.max()) if len(kicks) else None)
        return s
