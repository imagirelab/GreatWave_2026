# -*- coding: utf-8 -*-
"""設計28：単発砕波の生成器（設計27 の ds27_model.py の上に、美術の誘導の作り直しを重ねたもの）。

README
======
設計27 の生成器（Tools/GWWaveGen/ds27/ds27_model.py、方式 H の層 1〜7）を import し、設計28 で変える所だけを上書きする。
設計27 のファイルは変えない（ds27_params.json は ds28_params.json の base として SHA-256 を照合して読む）。

設計27 から引き継いだ課題（Docs/Progress/Design_27_ja.md 第6.1節）と、この生成器での扱い：
  1 K* への引き戻し：設計27 は内壁の錨を τ −2.0 s から t* の K* へ ease-in で寄せ（anchor.to_kstar_sigma）、錨が巻きの間に頂の真下より
    後ろへ下がってから押し戻された（本体の水 −37% → +33%）。→ 名前の付いた美術の誘導 ds_approach_kstar に置き換える：
    錨は噴流の始まりの前に前面が立つ分だけ頂へ近づき（始まりの位置 q_on、段階 c の Lo < 0.05H を保つ最も頂に近い所）、
    始まりの後は後ろへ戻らず、K* の位置へ単調に進む（切ると q_on のまま）。巻きの間の本体の断面積は、始まりの前から t* の K* の値へ
    一次式でつなぎ、背面を縦にふくらませて合わせる（水を保つ）。
  2 段階 b の見え方：名前の付いた美術の誘導 ds_tower_peak（頂の帽子の時刻と、放出の前の帯の上面の角の表）で、b で尖った塔、
    c へ向けて頂の先が前へ出る形にする。最初の白を c で読めるようにする色だけの誘導 ds_tip_white_line（T_white だけを変える）。
  3 峰の行の外側（κ < 1）の唇：位置の混ぜ合わせをやめ、放出の時刻を κ で遅らせて打ち出しを弱める（放出の後はどの点も重力だけ）。
層・約束（パッケージの書式、局所座標、T_white の意味）は設計27 と同じ。Unity の再生器（Design27 の DS27KeyposePlayer）はそのまま読む。

使い方（numpy だけ）：
    from ds28_model import Generator
    g = Generator("art_on")                 # 既定（12 個の誘導をすべて入れる）。"art_off" はすべて切る
    g = Generator("art_on", switches={"ds_approach_kstar": False})   # 1 つだけ切った版（P20 の測定）
    X = g.local(-2.0); W = g.world(-2.0); T = g.twhite()
"""
import copy
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
if DS27 not in sys.path:
    sys.path.insert(0, DS27)
import ds27_model as MD  # noqa: E402

REPO = MD.REPO
PARAMS_JSON = os.path.join(HERE, "ds28_params.json")
G = MD.G
smoothstep = MD.smoothstep
ease_in = MD.ease_in
integ_S = MD.integ_S
angle_dir = MD.angle_dir
unit = MD.unit
Tab = MD.Tab


def trapezoid_s(x, up, down):
    """0→1 の単調な曲線（速さが台形：初めの up の割合で 0 から最大へ、終わりの down の割合で最大から 0 へ、どちらも余弦で滑らかに）。
    加速度の最大は smoothstep より小さい（同じ時間なら約 0.6〜0.8 倍）。x < 0 で 0、x > 1 で 1。"""
    x = min(max(float(x), 0.0), 1.0)
    area = 1.0 - 0.5 * up - 0.5 * down

    def integ(t):
        if t <= up:
            return 0.5 * t - up / (2 * math.pi) * math.sin(math.pi * t / up) if up > 0 else 0.0
        v = (0.5 * up if up > 0 else 0.0)
        if t <= 1.0 - down:
            return v + (t - up)
        v += 1.0 - down - up
        u = t - (1.0 - down)
        return v + 0.5 * u + down / (2 * math.pi) * math.sin(math.pi * u / down) if down > 0 else v
    return integ(x) / area


def deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = copy.deepcopy(v)
    return dst


def load_params(path=PARAMS_JSON):
    """ds28_params.json を読み、base（設計27 の ds27_params.json、SHA-256 を照合）に overrides を重ねた辞書と、ds28 の値を返す。"""
    P28 = MD.load_json(path)
    bp = os.path.join(REPO, P28["base"]["path"])
    sha = MD.sha256_file(bp)
    if sha != P28["base"]["sha256"]:
        raise SystemExit("[ds28] base の ds27_params.json の SHA-256 が記録と違います")
    P = MD.load_json(bp)
    deep_merge(P, P28["overrides"])
    P["ds28"] = copy.deepcopy(P28["ds28"])
    return P, P28, sha


class Generator(MD.Generator):
    def __init__(self, version="art_on", params_path=PARAMS_JSON, log=None, switches=None):
        # 設計27 の Generator.__init__ と同じ手順（パラメータの読み方と切り替えだけが違う）
        if version not in ("art_on", "art_off"):
            raise ValueError("version は art_on か art_off（1 つずつ切るのは switches で）")
        self.version = version
        self.log = log or (lambda *a: None)
        self.params_path = params_path
        self.P, self.P28, self.base_sha = load_params(params_path)
        P = self.P
        cpath = os.path.join(REPO, P["inputs"]["conditions"])
        self.cond_sha = MD.sha256_file(cpath)
        if self.cond_sha != P["inputs"]["conditions_sha256"]:
            raise SystemExit("[ds28] ds26_conditions.json の SHA-256 が記録と違います")
        self.C = MD.load_json(cpath)
        self.params_sha = MD.sha256_file(params_path)
        on = bool(P["switches"]["versions"][version])
        self.sw = {k: on for k in P["switches"]["names"]}
        if switches:
            for k, v in switches.items():
                if k not in self.sw:
                    raise ValueError("知らない切り替え：%s" % k)
                self.sw[k] = bool(v)
        self.variant = version if not switches else version + "+" + ",".join("%s=%d" % (k, int(v)) for k, v in sorted(switches.items()))
        self.K = MD.KStar(P)
        C = self.C
        cal, phys = C["calibration"], C["physical_input"]
        self.c0 = 20.0
        self.tau0 = abs(float(cal["jet_onset_peak_row_tau_s"]["value"]))
        self.c_pk_on = float(cal["jet_onset_peak_row_tau_s"]["row_c_m"])
        self.floor = float(cal["jet_onset_floor_s"]["value"])
        self.vpeel = float(cal["peel_speed_mps"]["value"])
        self.p_rel = float(cal["release_exponent_p"]["value"])
        self.beta = float(cal["crest_decel_beta"]["value"])
        self.vH = float(cal["crest_rise_after_onset_mps"]["value"])
        self.lam_p = float(phys["peak_wavelength_m"]["value"])
        self.half_angle = 0.5 * float(phys["crossing_angle_deg"]["value"])
        self.gamma_j = float(phys["spectrum"]["gamma"])
        self.Hs = float(phys["background_swell_Hs_m"]["value"])
        num = C["numerical"]
        self.strip_delta = float(P["lip"]["strip_spacing_m"])
        self.th1f = float(num["prerelease_rule"]["upper_strip_angle_deg"])
        self.th2f = float(num["prerelease_rule"]["underside_strip_angle_deg"])
        ov_ = P["front"].get("strip_angle_override_deg")
        if ov_:
            self.th1f = float(ov_.get("upper", self.th1f))
            self.th2f = float(ov_.get("under", self.th2f))
        self.Tr_max = float(P["lip"]["release_ramp_max_s"])
        self.tau_min = float(P["range"]["tau_min_s"])
        D8 = P["ds28"]
        self.ap = D8["approach"]
        self.kl = D8["lip_kappa"]
        self._tables()
        self._tables28()
        self._rows()
        self._clock_setup()
        self._approach_setup()
        self._seam_setup_body()
        self._lip_setup()
        self._seam_setup()
        self._onset_setup()
        self._xs_setup()
        self._sea_setup()
        self._water_setup()

    # ------------------------------------------------------------ 表（設計28）
    def _tables28(self):
        tw = self.P["ds28"]["tower"]
        if self.sw["ds_tower_peak"]:
            self.tab_th1 = Tab(tw["strip_angles_deg_table"]["upper"], 0.0)
            self.tab_th2 = Tab(tw["strip_angles_deg_table"]["under"], 0.0)
            if self.cap_on:
                self.tab_cap = Tab(tw["crest_cap_omega_table"], self.P["back"]["crest_cap"].get("omega_end_slope", 0.0))
                assert abs(self.tab_cap(0.0)) < 1e-12
        assert abs(self.tab_th1(-2.4) - self.th1f) < 1e-9 and abs(self.tab_th2(-2.4) - self.th2f) < 1e-9

    # ------------------------------------------------------------ 内壁の錨（ds_approach_kstar）
    def _approach_setup(self):
        ap = self.ap
        nv = self.K.nv
        H = self.H
        self.qst = (self.K_ja[:, 0] - self.a_root) / np.maximum(H, 1e-9)
        self.q_on = np.zeros(nv)
        h_c = float(self.P["crest_height"]["H_over_Hstar_at_onset"])
        # 設計28修正の2回目：噴流の始まりでの張り出し Lo_on/H を行ごとに、K* の張り出し（定義 A）を波峰線方向にならした値から決める
        # （K* の唇が短い行ほど、始まりの前に内壁を頂の下へ寄せる。唇が長い行は唇先の前進で段階 d の Lo ≥ 0.1H に届く）
        lo = ap["lo_at_onset"]
        cc = self.K.c
        ov = np.where(self.H >= 2.0, np.clip(self.overhang, 0.0, None), 0.0)
        Wg = np.exp(-0.5 * ((cc[:, None] - cc[None, :]) / float(lo["row_smooth_m"])) ** 2) * (self.H >= 2.0)[None, :]
        ov_s = (Wg @ ov) / np.maximum(Wg.sum(1), 1e-9)
        self.lo_on = np.clip(float(lo["a"]) - float(lo["b"]) * ov_s, float(lo["min"]), float(lo["max"]))
        d1 = angle_dir(self.th1f)
        d2 = angle_dir(self.th2f)
        for r in range(nv):
            if not self.has_body[r]:
                continue
            dl = self.strip_delta * float(np.clip(H[r] / self.P["lip"]["strip_spacing_scale_H_m"], self.P["lip"]["strip_spacing_min_factor"], 1.0))
            n_up = max(int(self.tip[r]) - int(self.root[r]), 0)
            n_un = max(int(self.rim[r]) - int(self.tip[r]), 0)
            front = max(n_up * dl * d1[0], n_up * dl * d1[0] + n_un * dl * d2[0])    # 放出の前の帯の一番前（頂からの横の距離）
            q = max(float(ap["q_floor"]), front / H[r] - float(self.lo_on[r]) * h_c)
            self.q_on[r] = min(q, self.qst[r])
        self.anc_s0 = float(ap["steepen_sigma_start"])
        self.rim_min = float(ap["rim_progress_min_m"])
        self.tube_bl = float(ap["tube_blend_s"])

    def anchor_q(self, r, tau, sig_r, M):
        """内壁の錨の頂からの横の距離 / H（行 r、物理の時刻 τ、行の時計 σ_r、始まりの後の進み M）。"""
        D_s = self.anc["D_s"]
        q_on = self.q_on[r]
        if sig_r < -2.4:
            x = (sig_r - self.anc_s0) / (-2.4 - self.anc_s0)
            x = min(max(x, 0.0), 1.0)
            return q_on + (D_s - q_on) * (1.0 - x * x * x * (10.0 - 15.0 * x + 6.0 * x * x))    # 最小躍度（加速度が両端で 0）
        if not self.sw["ds_approach_kstar"]:
            return q_on
        return q_on + (self.qst[r] - q_on) * M

    def progress(self, r, tau, S):
        """始まりの後の進み M（0〜1、単調）：唇の rim の局所の a が始まりの時から K* まで進んだ割合。
        κ < 1 の行・rim の進みが小さい行・唇のない行は時間 u = (τ + T_row)/T_row の smoothstep。"""
        Tr = float(self.T_row[r])
        if tau <= -Tr:
            return 0.0
        L = self.lip.get(r)
        if L is not None and L.get("mode") == "strip" and L.get("rim_span", 0.0) >= self.rim_min:
            a = self._rim_local_a(r, tau, S)
            return float(min(max((a - L["rim_a_on"]) / L["rim_span"], 0.0), 1.0))
        u = min(max((tau + Tr) / Tr, 0.0), 1.0)
        return float(smoothstep(u))

    def _rim_local_a(self, r, tau, S):
        L = self.lip[r]
        Xg, rel, off = self.lip_state(r, tau, S["sig"][r])
        i = len(L["cols"]) - 1
        T = S["T"]
        if rel[i]:
            a = Xg[i, 0]
        else:
            a = self.a_root[r] - self.D(T, self.T_row[r]) + off[i, 0]
        return float(a + self._frame_offset(r, T, S["Dpk"]))

    # ------------------------------------------------------------ 本体の前面（頂〜錨）の座標：行ごと
    def _seam_setup_body(self):
        A0, Y0 = self.K.A, self.K.Y
        self.seam_body = {}
        for r in range(self.K.nv):
            if not self.has_body[r] or self.w_cplx[r] <= 0.0:
                continue
            root, ja = int(self.root[r]), int(self.ja[r])
            cols = np.arange(root, ja + 1)
            self.seam_body[r] = MD.Seam(np.stack([A0[r, cols], Y0[r, cols]], 1))

    def _seam_setup(self):
        A0, Y0 = self.K.A, self.K.Y
        self.seam_tube = {}
        for r in self.lip:
            ja = int(self.ja[r])
            tc = np.arange(int(self.lip[r]["rim"]), ja + 1)
            self.seam_tube[r] = MD.Seam(np.stack([A0[r, tc], Y0[r, tc]], 1), by_column=True)

    def _onset_setup(self):
        """行ごとに、始まり（τ = −T_row）の rim の位置と管の天井の形 O（Hermite）を記録する（始まりの後の形の移しの出発点）。"""
        for r in sorted(self.lip.keys()):
            L = self.lip[r]
            t_on = -float(self.T_row[r])
            S = self._shared(t_on)
            if L.get("mode") == "strip":
                L["rim_a_on"] = self._rim_local_a(r, t_on, S)
                L["rim_span"] = float(self.K.A[r, int(L["rim"])] - L["rim_a_on"])
            Arow = self.K.A[r].copy()
            Yrow = self.K.Y[r].copy()
            Bu, X_ja, D_ja, P_top, _ = self._front_body(r, t_on, S, Arow, Yrow, 0.0)
            Xl, rel = self._lip_local(r, t_on, S, Bu)
            X_rim, D_rim = self._rim_tangent(r, t_on, S, Xl)
            L["tube_O"] = self.seam_tube[r].hermite(X_rim, D_rim, X_ja, D_ja, self.herm_scale)

    def _shared(self, tau):
        """sections で行に共通の量（全行の配列）。"""
        T = -tau
        a_c, y_c, sig, shear = self.crest(tau)
        wbd = np.where(self.has_body, self.w_body, 0.0)
        return dict(T=T, tau=tau, a_c=a_c, y_c=y_c, sig=sig, shear=shear, Dpk=float(self.D(T, self.tau0)), wbd=wbd,
                    Lb=1.0 + (self.tab_Lb(sig) - 1.0) * wbd, F=1.0 + (self.tab_F(sig) - 1.0) * wbd, sw_=self.tab_sw(sig),
                    th1=self.tab_th1(sig),
                    psi_b=(ease_in((sig - self.psi_b_rng[0]) / (self.psi_b_rng[1] - self.psi_b_rng[0])) if self.sw["ds_tube_shape"] else np.zeros_like(sig)))

    def _front_body(self, r, tau, S, A0r, Y0r, M):
        """行 r の内壁（ja〜j_E）と本体の上の前面 Bu（頂〜ja）。A0r, Y0r は書き込む行（コピー）。
        戻り (Bu (ja−root+1, 2), X_ja, D_ja, P_top, info)。"""
        A0, Y0 = self.K.A, self.K.Y
        jE = self.jE
        H = self.H[r]
        ac = S["a_c"][r]
        yc = S["y_c"][r]
        sy = yc / max(self.y_root[r], 1e-9)
        ar = self.a_root[r]
        ja = int(self.ja[r])
        y_ja = sy * Y0[r, ja]
        q = self.anchor_q(r, tau, float(S["sig"][r]), M)
        a_ja = ac + H * q
        gam = math.atan2(max(yc - y_ja, 1e-6), a_ja - ac)
        fw = max(A0[r, jE] - ar, 1e-6)
        a_ft = ac + S["F"][r] * fw
        a_ft_max = A0[r, -1] - float(self.P["front"]["front_foot_margin_m"])
        capped = 0
        if a_ft > a_ft_max:
            a_ft = a_ft_max
            capped = 1
        if not self.sw["ds_body_narrow"]:
            gW = fw + (self.grp_Wb - fw) * self.w_grp[r]
            a_ft = min(ac + gW, a_ft_max) - 2.0 * math.log1p(math.exp(-abs(ac + gW - a_ft_max) / 2.0))
        Lw, th, ell = self.wall[r]
        s_w = S["sw_"][r] if self.sw["ds_tube_shape"] else 0.6 * S["sw_"][r]
        wsm = math.radians(8.0)
        g_w = gam - wsm * math.log1p(math.exp((gam - self.wall_start_max) / wsm))
        th0 = -g_w * (1.0 - smoothstep((ell - 0.65) / 0.35))
        thb = s_w * th + (1.0 - s_w) * th0
        x = np.concatenate([[0.0], np.cumsum(Lw * np.cos(thb))])
        z = np.concatenate([[0.0], np.cumsum(Lw * np.sin(thb))])
        bad = 0
        if z[-1] >= -1e-9 or x[-1] <= 1e-6 or a_ft - a_ja <= 0.05 * fw:
            bad = 1
            a_ft = max(a_ft, a_ja + 0.05 * fw)
            if x[-1] <= 1e-6:
                x = np.linspace(0, 1, len(x))
            if z[-1] >= -1e-9:
                z = -np.linspace(0, 1, len(z))
        kz = -y_ja / z[-1]
        kx = (a_ft - a_ja) / x[-1]
        A0r[ja:jE + 1] = a_ja + kx * x
        Y0r[ja:jE + 1] = y_ja + kz * z
        Y0r[jE] = 0.0
        X_ja = np.array([A0r[ja], Y0r[ja]])
        D_ja = unit(np.array([A0r[ja + 1] - A0r[ja], Y0r[ja + 1] - Y0r[ja]]))
        P_top = np.array([ac, yc])
        sb = self.seam_body[r]
        D0 = angle_dir(float(S["th1"][r]))
        Hc = sb.hermite(P_top, D0, X_ja, D_ja, self.herm_scale)
        pb = float(S["psi_b"][r])
        Bu = Hc if pb <= 0.0 else (1 - pb) * Hc + pb * sb.similarity(P_top, X_ja)
        return Bu, X_ja, D_ja, P_top, dict(foot_capped=capped, wall_bad=bad, q=q)

    def _frame_offset(self, r, T, Dpk):
        """行 r の地面の a から局所の a への足し分（設計27 の sections の Xl[:,0] += Dr + w_body·(Dpk − Dr)）。"""
        Dr = float(self.D(T, self.T_row[r]))
        return Dr + self.w_body[r] * (Dpk - Dr)

    def _strip_off(self, L, th1, th2):
        d1 = angle_dir(th1)
        d2 = angle_dir(th2)
        dl = L["dl"]
        return np.where(L["upm"][:, None], L["k_up"][:, None] * dl * d1[None, :],
                        L["n_up"] * dl * d1[None, :] + L["k_un"][:, None] * dl * d2[None, :])

    def _strip_local(self, r, tau, S):
        L = self.lip[r]
        sig_r = float(S["sig"][r])
        off = self._strip_off(L, float(self.tab_th1(sig_r)), float(self.tab_th2(sig_r)))
        T = S["T"]
        crest_g = np.array([self.a_root[r] - self.D(T, self.T_row[r]), S["y_c"][r]])
        strip = crest_g[None, :] + off
        strip[:, 0] += self._frame_offset(r, T, S["Dpk"])
        return strip

    def _prerelease_local(self, r, tau, S=None, Bu=None):
        """κ < 1 の行の、放出の前の唇の点の局所の位置（帯の置き場と本体の前面 Bu を κ で混ぜる）。(n, 2)。"""
        if S is None:
            S = self._shared(tau)
        if Bu is None:
            A0r = self.K.A[r].copy()
            Y0r = self.K.Y[r].copy()
            Bu = self._front_body(r, tau, S, A0r, Y0r, self.progress(r, tau, S))[0]
        strip = self._strip_local(r, tau, S)
        n = len(self.lip[r]["cols"])
        Bl = Bu[1:n + 1]
        return Bl + float(self.kappa[r]) * (strip - Bl)

    def _lip_local(self, r, tau, S, Bu):
        """行 r の唇の点の局所の位置（放出の前は帯（κ < 1 の行は Bu と混ぜる）、放出の後は重力だけ）。戻り (Xl, rel)。"""
        L = self.lip[r]
        Xg, rel, off = self.lip_state(r, tau, S["sig"][r])
        fo = self._frame_offset(r, S["T"], S["Dpk"])
        if L.get("mode") == "damped":
            Xpre = self._prerelease_local(r, tau, S, Bu)
            Xl = np.where(rel[:, None], Xg + np.array([fo, 0.0])[None, :], Xpre)
        else:
            crest_g = np.array([self.a_root[r] - self.D(S["T"], self.T_row[r]), S["y_c"][r]])
            Xl = np.where(rel[:, None], Xg, crest_g[None, :] + off)
            Xl[:, 0] += fo
        return Xl, rel

    def _rim_tangent(self, r, tau, S, Xl):
        L = self.lip[r]
        i_rim = len(L["cols"]) - 1
        kb = min(8, i_rim)
        d2p = angle_dir(float(self.tab_th2(S["sig"][r])))
        lam = float(smoothstep((L["Tc"][i_rim] - S["T"]) / self.rim_tangent_blend_s))
        return Xl[i_rim], unit((1 - lam) * d2p + lam * unit(Xl[i_rim] - Xl[i_rim - kb]))

    def _tube(self, r, tau, S, Xl, X_ja, D_ja, M):
        """管の天井（rim〜錨）。始まりの前は Hermite、始まりの後は始まりの形 O から K* の形への移し（ds_tube_shape）＋両端の動き。"""
        L = self.lip[r]
        st = self.seam_tube[r]
        X_rim, D_rim = self._rim_tangent(r, tau, S, Xl)
        Ht = st.hermite(X_rim, D_rim, X_ja, D_ja, self.herm_scale)
        Tr = float(self.T_row[r])
        bt = float(smoothstep((tau + Tr) / self.tube_bl))
        if bt <= 0.0 or "tube_O" not in L:
            return Ht
        Ms = M if self.sw["ds_tube_shape"] else 0.0
        B = (1.0 - Ms) * L["tube_O"] + Ms * st.K
        uu = np.linspace(0.0, 1.0, len(B))[:, None]
        TM = B + (1.0 - uu) * (X_rim - B[0])[None] + uu * (X_ja - B[-1])[None]
        return (1.0 - bt) * Ht + bt * TM

    # ------------------------------------------------------------ 唇（層4）：κ < 1 の行は打ち出しを弱める
    def _lip_setup(self):
        MD.Generator._lip_setup(self)
        for r in self.lip:
            self.lip[r]["mode"] = "strip"
        self.lip_kappa_rows = []
        if self.kl.get("mode") != "launch_damping":
            return
        gp = float(self.kl["release_power"])
        h = float(self.kl["derivative_h_s"])
        for r in sorted(self.lip.keys()):
            kap = float(self.kappa[r])
            if kap >= 1.0:
                continue
            L = self.lip[r]
            lp = self.P["lip"]
            # 設計28修正の1回目：放出を遅らせるのは κ < kappa_delay_below の行だけ（その間は κ/kappa_delay_below の release_power 乗）。
            # κ がそれ以上の行（峰の行と巻きの行の端）は設計27 と同じ時刻に放す（P16 の窓と噴流の始まりの順を保つ）
            k0 = float(self.kl.get("kappa_delay_below", 0.0))
            fac = min(1.0, kap / k0) ** gp if k0 > 0 else kap ** gp
            Ti = L["Ti"] * fac
            Tc = np.maximum(Ti, float(lp["Tc_min_s"]))
            Tr = np.minimum(self.Tr_max, Tc / 2)
            if self.e4_curled[r] and self.kl.get("curled_ramp_end_by_table", False) and kap < float(self.kl["ramp_limit_below_kappa"]):
                # 設計28修正の2回目：K* で巻く行では、打ち出しの補間を設計26 の表の時刻（行の始まり + min(0.6 s, T_row/2)）までに終える
                # （放出を κ で遅らせても、関門 P16 の窓の始まりで唇先がまだ補間の途中にならないように）
                T_row = float(self.T_row[r])
                lim = Tc - T_row + min(self.Tr_max, T_row / 2)
                Tr = np.where(lim >= float(self.kl["ramp_min_s"]), np.minimum(Tr, lim), Tr)
            n = len(L["cols"])
            P0 = np.zeros((n, 2))
            V0 = np.zeros((n, 2))
            A0v = np.zeros((n, 2))
            L["mode"] = "damped_setup"
            cache = {}
            for i in range(n):
                t0 = -float(Tc[i])
                pts = []
                for dt in (-h, 0.0, h):
                    tt = round(min(t0 + dt, 0.0), 12)
                    if tt not in cache:
                        Sx = self._shared(tt)
                        loc = self._prerelease_local(r, tt, Sx)
                        cache[tt] = (loc, self._frame_offset(r, -tt, Sx["Dpk"]))
                    loc, fo = cache[tt]
                    g_ = loc[i].copy()
                    g_[0] -= fo
                    pts.append(g_)
                P0[i] = pts[1]
                V0[i] = (pts[2] - pts[0]) / (2 * h)
                A0v[i] = (pts[2] - 2 * pts[1] + pts[0]) / (h * h)
            IS, ISg = integ_S(Tc, Tr)
            if self.sw["ds_lip_target_kstar"]:
                # t* に K* へ着くように打ち出しの速さを一次式で解く（放出の時の速さ・加速度から打ち出しの補間を経て重力だけ）
                Kt = L["Kt"]
                v2 = (Kt - P0 - V0 * (Tc - IS)[:, None] - A0v * (Tc ** 2 / 2 - ISg)[:, None] + np.stack([np.zeros(n), G * ISg], 1)) / IS[:, None]
            else:
                # 切った版（K* へ逆算しない）：設計27 の切った版の打ち出しの速さ（E4c の中央値）と放出の時の速さの差を κ 倍にする
                v2 = V0 + kap * (np.stack([L["u2"], L["w2"]], 1) - V0)
            L.update(mode="damped", Ti=Ti, Tc=Tc, Tr=Tr, P0=P0, V0=V0, A0=A0v, v2=v2, release_power=gp)
            self.lip_kappa_rows.append(int(r))

    def lip_state(self, r, tau, sig_r):
        L = self.lip[r]
        if L.get("mode") not in ("damped",):
            return MD.Generator.lip_state(self, r, tau, sig_r)
        T = -tau
        tp = L["Tc"] - T
        rel = tp >= 0
        tpc = np.clip(tp, 0.0, None)
        IS, ISg = integ_S(tpc, L["Tr"])
        X = (L["P0"] + L["V0"] * (tpc - IS)[:, None] + L["A0"] * (tpc ** 2 / 2 - ISg)[:, None] + L["v2"] * IS[:, None]
             - np.stack([np.zeros_like(ISg), G * ISg], 1))
        th1 = float(self.tab_th1(sig_r))
        th2 = float(self.tab_th2(sig_r))
        off = self._strip_off(L, th1, th2)
        return np.where(rel[:, None], X, 0.0), rel, off

    # ------------------------------------------------------------ 水の釣り合い（ds_approach_kstar の一部）
    def _water_setup(self):
        W = self.ap["water"]
        self.water_on = bool(W.get("on")) and self.sw["ds_approach_kstar"] and (self.sw["ds_body_narrow"] or self.sw["ds_back_steep"])
        nv = self.K.nv
        self.Lb_min = float(W["Lb_min"])
        self.water_Tb = float(W["blend_s"])
        self.water_lead = float(W["lead_before_onset_s"])
        self.water_g = float(W["band_frac"])
        self.A_star = self._body_area(self.K.A, self.K.Y)
        self.A_w = np.full(nv, np.nan)
        self.A_w_raw = np.full(nv, np.nan)
        self._water_mode = "off"
        self.Lb_grid = None
        if not self.water_on:
            return
        tws = np.round(-self.T_row - self.water_lead, 9)
        for tw in np.unique(tws):
            rows = np.nonzero(np.abs(tws - tw) < 1e-12)[0]
            A, Y = self.sections(float(tw), rows=rows, water=False)
            self.A_w_raw[rows] = self._body_area(A[rows], Y[rows])
        g = self.water_g
        self.A_w = np.clip(self.A_w_raw, (1 - g) * self.A_star, (1 + g) * self.A_star)
        # 設計28修正の1回目：Lb をコマごとに解くと、前面がえぐれる所で Lb が 0.4 s に ±0.3 揺れ、背面の足の加速度が 2 g を超えた（P13(2)）。
        # 60 Hz の格子で行ごとに解いた Lb と表の Lb の差 d(τ) を、1 つのなめらかな山 ΔL·B(τ)（噴流の始まりの rise_s 前から始まりまで最小躍度で 0 → 1、
        # 始まりから t* まで最小躍度で 1 → 0）へ最小二乗で当てはめ、評価は Lb = 表 + ΔL·B(τ) とする（加速度が形で抑えられる。t* で Lb = 1）。
        W = self.ap["water"]
        hz = float(W["schedule_hz"])
        self.water_rise = float(W["bump_rise_s"])
        t_start = float(np.min(-self.T_row - self.water_rise)) - 0.1
        n = int(np.ceil(-t_start * hz))
        grid = -np.arange(n, -1, -1) / hz
        Ls = np.full((len(grid), nv), np.nan)
        Lt = np.full((len(grid), nv), np.nan)
        self._water_mode = "solve"
        for k, t in enumerate(grid):
            A, Y, d = self.sections(float(t), diag=True)
            Ls[k] = d["Lb_all"]
            Lt[k] = self._shared(float(t))["Lb"]
        self._water_mode = "bump"
        self.dL = np.zeros((nv, 2))
        fit_from = float(W["fit_from_before_onset_s"])
        for r in range(nv):
            v = Ls[:, r] - Lt[:, r]
            if not np.isfinite(v).all():
                continue
            B = np.array([self._bump2(r, float(t)) for t in grid])      # (n, 2)
            m = grid >= -float(self.T_row[r]) - fit_from
            M_ = B[m]
            wt = np.where(grid[m] < -float(self.T_row[r]), float(W["fit_weight_before_onset"]), 1.0)   # 始まりの前（前面が鉛直になる頃）を重く
            AtA = (M_ * wt[:, None]).T @ M_ + 1e-6 * np.eye(2)
            self.dL[r] = np.linalg.solve(AtA, (M_ * wt[:, None]).T @ v[m])
        self.Lb_grid = grid
        self.Lb_solved = Ls
        self.Lb_table_grid = Lt

    def _bump2(self, r, tau):
        """水の釣り合いの 2 つの山：B1（始まりの rise_s 前から始まりまで 0 → 1、始まりから t* まで 1 → 0。最小躍度）、
        B2（始まりから t* まで sin²(πu)、u = (τ + T_row)/T_row。両端で値・傾き 0）。"""
        Tr = float(self.T_row[r])
        b2 = math.sin(math.pi * (tau + Tr) / Tr) ** 2 if -Tr < tau < 0.0 else 0.0
        return np.array([self._bump(r, tau), b2])

    def _bump(self, r, tau):
        Tr = float(self.T_row[r])
        if tau <= -Tr - self.water_rise or tau >= 0.0:
            return 0.0
        if tau < -Tr:
            x = (tau + Tr + self.water_rise) / self.water_rise
        else:
            x = 1.0 - (tau + Tr) / Tr
        x = min(max(x, 0.0), 1.0)
        return x * x * x * (10.0 - 15.0 * x + 6.0 * x * x)

    def _Lb_at(self, r, tau):
        """ならした Lb の表の 3 次補間（Catmull-Rom、格子は等間隔）。"""
        g = self.Lb_grid
        h = g[1] - g[0]
        x = (tau - g[0]) / h
        i = int(min(max(np.floor(x), 0), len(g) - 2))
        t = x - i
        v = self.Lb_sched[:, r]
        p0, p1, p2, p3 = v[max(i - 1, 0)], v[i], v[i + 1], v[min(i + 2, len(g) - 1)]
        return float(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))

    def _body_area(self, A, Y):
        a = A[..., self.jB:self.jE + 1]
        y = Y[..., self.jB:self.jE + 1]
        return -0.5 * (a[..., :-1] * y[..., 1:] - a[..., 1:] * y[..., :-1]).sum(-1)

    def water_target(self, r, tau):
        """(目標の直線の値, 重み b)。τ_w = −T_row − lead から t* まで：A_w → A*（K*）の一次式。その前の blend_s は重み b で移る。"""
        tw = -float(self.T_row[r]) - self.water_lead
        t1 = tw - self.water_Tb
        if tau <= t1 or not np.isfinite(self.A_w[r]):
            return None, 0.0
        b = float(smoothstep((tau - t1) / self.water_Tb))
        line = self.A_w[r] + (self.A_star[r] - self.A_w[r]) * (tau - tw) / (0.0 - tw)
        return line, b

    # ------------------------------------------------------------ 背面（層3）
    def _back(self, r, S, Lb_r, Arow, Yrow):
        """背面（列 0〜頂）を Arow, Yrow に書く。戻り 背面の Lb が抑えられたか。"""
        A0, Y0 = self.K.A, self.K.Y
        jB = self.jB
        root = int(self.root[r])
        H = self.H[r]
        ac = S["a_c"][r]
        yc = S["y_c"][r]
        sy = yc / max(self.y_root[r], 1e-9)
        ar = self.a_root[r]
        bw = max(ar - A0[r, jB], 1e-6)
        margin_b = float(self.P["back"]["back_foot_margin_m"])
        on_back = self.sw["ds_body_narrow"] or self.sw["ds_back_steep"]
        capped = 0
        if on_back:
            cap_ = max((ac - (A0[r, 0] + margin_b)) / bw, 1.0)
            L_ = min(Lb_r, cap_)
            capped = int(L_ < Lb_r - 1e-12)
            Arow[jB:root + 1] = ac + L_ * (A0[r, jB:root + 1] - ar)
            Yrow[jB:root + 1] = sy * Y0[r, jB:root + 1]
        else:
            u = (ar - A0[r, jB:root + 1]) / bw
            Wb = bw + (self.grp_Wb - bw) * self.w_grp[r]
            Wb = min(Wb, max(ac - (A0[r, 0] + margin_b), 1.0))
            xg = -u * Wb
            Arow[jB:root + 1] = ac + xg
            Yrow[jB:root + 1] = yc * np.interp(xg, self.grp_xs * (Wb / self.grp_Wb), self.grp_y)
        if self.cap_on and on_back:
            om_ = float(self.tab_cap(S["sig"][r])) * S["wbd"][r]
            if om_ > 0.0:
                dd = np.maximum(ac - Arow[jB:root + 1], 0.0)
                fcap = 1.0 - om_ * (1.0 - smoothstep(dd / max(self.cap_D_over_H * H, 1e-6)))
                Yrow[jB:root + 1] = yc - (yc - Yrow[jB:root + 1]) * fcap
        Arow[:jB + 1] = A0[r, 0] + self.fb[r] * (Arow[jB] - A0[r, 0])
        Yrow[:jB + 1] = 0.0
        return capped

    def _back_area(self, r, Arow, Yrow):
        root = int(self.root[r])
        a = Arow[self.jB:root + 1]
        y = Yrow[self.jB:root + 1]
        return -0.5 * float((a[:-1] * y[1:] - a[1:] * y[:-1]).sum())

    # ------------------------------------------------------------ 本体（層3）と唇・管の組み立て
    def sections(self, tau, diag=False, rows=None, water=True):
        """全行の断面（局所の a、y）。(nv, nu) の 2 つ。海（層1）の前。設計27 の sections を行ごとに分け、
        錨（anchor_q）・κ < 1 の唇（放出の前の混ぜ合わせ＋打ち出しの弱め）・管の天井（形の移し）・水の釣り合い（背面の Lb）を変えた。"""
        K = self.K
        A0, Y0 = K.A, K.Y
        nv = K.nv
        jE = self.jE
        S = self._shared(tau)
        a_c, y_c, sig = S["a_c"], S["y_c"], S["sig"]
        A = A0.copy()
        Y = Y0.copy()
        F = S["F"]
        margin_f = float(self.P["front"]["front_foot_margin_m"])
        info = dict(lb_capped=0, foot_capped=0, wall_bad=0, Lb={}, anchor_q={}, M={}, Lb_all=np.full(nv, np.nan))
        use_water = self.water_on and water
        row_iter = range(nv) if rows is None else [int(r) for r in rows]
        for r in row_iter:
            if not self.has_body[r]:
                continue
            root = int(self.root[r])
            sy = y_c[r] / max(self.y_root[r], 1e-9)
            ar = self.a_root[r]
            ac = a_c[r]
            Lb_r = float(S["Lb"][r])
            if use_water and self._water_mode == "bump":
                Lb_r = Lb_r + float(self.dL[r] @ self._bump2(r, tau))
            info["lb_capped"] += self._back(r, S, Lb_r, A[r], Y[r])
            # ---- 単純な本体（小さい行）
            if self.w_cplx[r] < 1.0:
                As = A[r].copy()
                Ys = Y[r].copy()
                fw = max(A0[r, jE] - ar, 1e-6)
                Fr = F[r] if self.sw["ds_body_narrow"] else (fw + (self.grp_Wb - fw) * self.w_grp[r]) / fw
                Fr = min(Fr, max((A0[r, -1] - margin_f - ac) / fw, 0.2))
                As[root:jE + 1] = ac + Fr * (A0[r, root:jE + 1] - ar)
                Ys[root:jE + 1] = sy * Y0[r, root:jE + 1]
                As[jE:] = As[jE] + self.ff[r] * (A0[r, -1] - As[jE])
                Ys[jE:] = 0.0
                if self.w_cplx[r] <= 0.0:
                    A[r], Y[r] = As, Ys
                    continue
            ja = int(self.ja[r])
            M = self.progress(r, tau, S)
            Bu, X_ja, D_ja, P_top, fi = self._front_body(r, tau, S, A[r], Y[r], M)
            info["foot_capped"] += fi["foot_capped"]
            info["wall_bad"] += fi["wall_bad"]
            A[r, jE:] = A[r, jE] + self.ff[r] * (A0[r, -1] - A[r, jE])
            Y[r, jE:] = 0.0
            kap = self.kappa[r] if r in self.lip else 0.0
            if kap > 0.0:
                Lp = self.lip[r]
                Xl, rel = self._lip_local(r, tau, S, Bu)
                Tu = self._tube(r, tau, S, Xl, X_ja, D_ja, M)
                cols_l = Lp["cols"]
                Lf = np.zeros((ja - root + 1, 2))
                Lf[0] = P_top
                Lf[1:len(cols_l) + 1] = Xl
                Lf[len(cols_l):] = Tu
                if kap < 1.0 and Lp.get("mode") != "damped":
                    Lf = Bu + kap * (Lf - Bu)
                A[r, root + 1:ja] = Lf[1:-1, 0]
                Y[r, root + 1:ja] = Lf[1:-1, 1]
            else:
                A[r, root + 1:ja] = Bu[1:-1, 0]
                Y[r, root + 1:ja] = Bu[1:-1, 1]
            A[r, root] = ac
            Y[r, root] = y_c[r]
            if self.w_cplx[r] < 1.0:
                wc = self.w_cplx[r]
                A[r] = As + wc * (A[r] - As)
                Y[r] = Ys + wc * (Y[r] - Ys)
            if use_water and self._water_mode == "solve":
                # ---- 水の釣り合い：背面の横の倍率 Lb を割線法で解く（ds_approach_kstar。表を作るときだけ）
                line, b = self.water_target(r, tau)
                if line is not None and b > 0.0:
                    area0 = float(self._body_area(A[r], Y[r]))
                    tgt = (1.0 - b) * area0 + b * line
                    ba0 = self._back_area(r, A[r], Y[r])
                    Ar2 = A[r].copy()
                    Yr2 = Y[r].copy()
                    L1 = Lb_r + 0.1
                    self._back(r, S, L1, Ar2, Yr2)
                    ba1 = self._back_area(r, Ar2, Yr2)
                    Lb_new = Lb_r
                    if abs(ba1 - ba0) > 1e-9:
                        Lb_new = max(Lb_r + 0.1 * (tgt - area0) / (ba1 - ba0), self.Lb_min)
                        self._back(r, S, Lb_new, Ar2, Yr2)
                        ba2 = self._back_area(r, Ar2, Yr2)
                        if abs(ba2 - ba1) > 1e-9 and abs(Lb_new - L1) > 1e-9:
                            Lb_new = max(Lb_new + (Lb_new - L1) * (ba0 + (tgt - area0) - ba2) / (ba2 - ba1), self.Lb_min)
                    info["lb_capped"] += self._back(r, S, Lb_new, A[r], Y[r])
                    Lb_r = Lb_new
            info["Lb_all"][r] = Lb_r
            if r in (K.main_row, 192):
                info["anchor_q"][int(r)] = fi["q"]
                info["M"][int(r)] = M
                info["Lb"][int(r)] = Lb_r
        if self.xs_on:
            lr, j0, j1, Mk, Wn = self.xs_rows, self.xs_j0, self.xs_j1, self.xs_mask, self.xs_W
            dA = (A[lr, j0:j1] - A0[lr, j0:j1]) * Mk
            dY = (Y[lr, j0:j1] - Y0[lr, j0:j1]) * Mk
            den = Wn @ Mk
            ok = Mk > 0
            sA = np.where(ok, (Wn @ dA) / np.maximum(den, 1e-12), 0.0)
            sY = np.where(ok, (Wn @ dY) / np.maximum(den, 1e-12), 0.0)
            A[lr, j0:j1] = np.where(ok, A0[lr, j0:j1] + sA, A[lr, j0:j1])
            Y[lr, j0:j1] = np.where(ok, Y0[lr, j0:j1] + sY, Y[lr, j0:j1])
        if diag:
            return A, Y, dict(info, a_c=a_c, y_c=y_c, sigma=sig, shear=S["shear"])
        return A, Y

    # ------------------------------------------------------------ 白（層6）：ds_tip_white_line
    def twhite(self):
        T = MD.Generator.twhite(self).astype(np.float64)
        if not self.sw["ds_tip_white_line"]:
            return T.astype(np.float32)
        W = self.P["ds28"]["white_tip_line"]
        d0 = float(W["delay_s"])
        spread = float(W["band_spread_s"])
        band = float(W["band_over_H"])
        lead = float(W.get("lead_before_release_s", 0.0))
        for r in self.lip:
            if self.kappa[r] < 0.5:
                continue
            L = self.lip[r]
            cols = L["cols"]
            sa = self.sarc[r]
            tip = int(L["tip"])
            dist = np.abs(sa[cols] - sa[tip])
            m = dist <= band * self.H[r]
            if not m.any():
                continue
            t_tip = -float(np.max(L["Tc"]))          # 行の唇先の放出（最も早い放出）
            tl = t_tip - lead + d0 + spread * np.clip(dist[m] / max(band * self.H[r], 1e-9), 0.0, 1.0)
            T[r, cols[m]] = np.minimum(T[r, cols[m]], tl)
        return T.astype(np.float32)

    # ------------------------------------------------------------ 記録
    def summary(self):
        s = MD.Generator.summary(self)
        s.update(variant=self.variant, lip_kappa_mode=self.kl.get("mode"), lip_damped_rows=len(getattr(self, "lip_kappa_rows", [])),
                 water_on=bool(self.water_on), base_params_sha256=self.base_sha)
        return s
