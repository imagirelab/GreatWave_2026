# -*- coding: utf-8 -*-
"""設計28修正01 試行E：試行D（Q15〜Q17 の動きの直し）の上に、D の評審で残った E1〜E6 を直す生成器。K* はフォルダーで受け取る。

README
======
試行D の Generator（Tools/GWWaveGen/ds28r01d/ds28r01d_model.py）を import して継承する。試行A〜D・設計26〜29 のファイルは変えない
（読み込む時に SHA-256 を記録する）。値はすべて ds28r01e_params.json（名前の付いた値。どれも切れる）。K* は D と同じくフォルダーで渡す
（--kstar。K*′ ができたらそのフォルダーを渡して同じコマンドで作り直す。コードは変えない）。

足したもの（E1〜E6 は依頼の番号）：
  E1 ds_lean_with_height（美術の誘導。D の ds_lean_pace の時計と錨の時刻の組み直し）：
     D は段階 b/c の表を最大 2 s 先の時計で読み、内壁の錨を σ −6.6 → −3.0 の最小躍度で頂の下へ寄せたので、前面が 0.54〜0.56 Hf で鉛直になり、
     約 2 s 半分の高さの塊（上の角 ≤ 110°）として立っていた（Q17 で利用者が嫌った形）。E では
       ・錨の進み P(σ) を節点の表（5 次の Hermite、節点で二階微分 0、C2、単調）にし、前面が高さとともに立つ（90° は H ≈ 0.74 Hf）。
       ・表の時計の先回り δ(σ) を小さく（最大 1 s）、前の足 F・背 Lb・wall_s だけに掛ける（帯の角・頂の帽子・ψ_b は読まない）。
       ・設計28 の段階 b の尖った塔（ds_tower_peak：帯の上面 46°・頂の帽子の谷）を切り、帯の下面の角と頂の帽子の表を差し替えて
         唇ができる前の頂を丸く保つ（頂の角 ≥ 125°）。唇の運びは σ −3.85 から 0.8 s で立ち上げる（試行B の値の上書き）。
     噴流の始まり（σ −2.4）より後の本体は D のまま。
  E2 ds_curl_lead（美術の誘導。試行C の巻き下がりの形 Φc の選び直し）：kind = delayed_extension のとき、C1 の伸びに比例の形の始まりを
     運びの始まりから σ_c（−3.2）へ遅らせ、一定の速さ（γ_c = 0）にする（唇が見える前は頂とともに上がり、見え始めから下がる）。
     頂に対する下がりは上へ加速しない形だけ（ブレーキなし）なので、最後の重力の分を減らすため、放出（自由な飛行の始まり）を
     0.15·T_row → 0.07·T_row、その前の下向きの加速度の立ち上げを 0.45 → 0.28 s にする（c1_overrides。放出の後は重力だけ）。
     kind = c1_overrides だけのときは試行C の変種 C1 の値の上書き（例：crest_lag の μ。試して採らなかった）。
  E6 ds_back_hold_water（美術の誘導。D の ds_back_hold に足す）：水の釣り合いの山（ds_approach_kstar の ΔL1·B1 + ΔL2·B2。背を横に
     広げて巻きの間の水を保つ）の分を、背の下の部分（K* の背の高さの割合 η ≤ 0.5 で全部、0.85 以上で 0）だけに掛ける（mode lower_back）。
     頂のまわりの背は表の Lb のまま（D の背の保持で σ −1.0 に t* の値へ着いて止まる）。D では背の表を止めてもこの山が t* まで頂のまわりの背を
     広げていて、最後の 1 s に頂が 9〜11° 尖った（山を 0 にした試しで τ −0.75 → 0 の尖りは 2〜3°）。山の当てはめ（60 Hz の格子、最小二乗）は
     同じ式で解き直す。mode end_early（山の終わりを σ_hold へ早める）も残す（試して採らなかった：背の足の加速度が増えた）。
  E3 keypose の精度（数値の条件）：節点の τ −3〜0 の間隔（keypose.fine_step_s）はここで、書式（後方互換の精度の層の追加）は
     ds28r01e_generate.py。E4・E5 の時間曲線は ds28r01e_timewarp.py。
  進行役の判断（Q24）の記録は ds28r01e_params.json の decisions_ja。

使い方（numpy だけ）：
    from ds28r01e_model import Generator
    g = Generator(kstar_dir="Unity/Build/Design/28R01D/kstar_foot")
    g = Generator(e_overrides={"curl_lead": {"start_sigma": -3.4}}, off=["back_hold_water"])
    X = g.local(-2.0)
"""
import copy
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DSD = os.path.abspath(os.path.join(HERE, "..", "ds28r01d"))
if DSD not in sys.path:
    sys.path.insert(0, DSD)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds28r01d_model as MDD  # noqa: E402

MC, MB, M8, MD = MDD.MC, MDD.MB, MDD.M8, MDD.MD
REPO = MDD.REPO
PARAMS_E = os.path.join(HERE, "ds28r01e_params.json")
E_NAMES = ("lean_with_height", "curl_lead", "back_hold_water")


def load_e(path=PARAMS_E):
    R = MD.load_json(path)
    shas = {}
    for k in ("trial_d_model", "trial_d_params"):
        p = os.path.join(REPO, R["base"][k])
        if not os.path.isfile(p):
            raise SystemExit("[ds28r01e] base のファイルがありません：%s" % R["base"][k])
        shas[R["base"][k]] = MD.sha256_file(p)
    return R, shas


class Quintic:
    """節点 (x_i, y_i) を通る 5 次の Hermite（節点の傾きは隣の割線の調和平均（Fritsch–Carlson。符号が変わる所と端は 0）、
    節点の二階微分は 0）。C2 で、節点の間は単調（作る時に 1 ms で確かめる）。範囲の前は最初の値、後ろは最後の値。"""

    def __init__(self, pts, check_monotone=True):
        xs, ys = np.asarray(pts, np.float64).T
        self.x, self.y = xs, ys
        h = np.diff(xs)
        assert np.all(h > 0)
        d = np.diff(ys) / h
        m = np.zeros_like(ys)
        for i in range(1, len(xs) - 1):
            if d[i - 1] * d[i] > 0:
                m[i] = 2.0 / (1.0 / d[i - 1] + 1.0 / d[i])
        self.h, self.m = h, m
        if check_monotone and len(xs) > 1:
            g = np.linspace(xs[0], xs[-1], int((xs[-1] - xs[0]) * 1000) + 2)
            v = self(g)
            dv = np.diff(v)
            sgn = np.sign(ys[-1] - ys[0])
            assert np.all(sgn * dv >= -1e-12), "節点の表が単調でない：%s" % (pts,)

    def __call__(self, s, deriv=0):
        s = np.asarray(s, np.float64)
        xs, ys, h, m = self.x, self.y, self.h, self.m
        sc = np.clip(s, xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, sc, side="right") - 1, 0, len(xs) - 2)
        t = (sc - xs[i]) / h[i]
        if deriv == 0:
            H0 = 1 - 10 * t ** 3 + 15 * t ** 4 - 6 * t ** 5
            H1 = t - 6 * t ** 3 + 8 * t ** 4 - 3 * t ** 5
            H4 = -4 * t ** 3 + 7 * t ** 4 - 3 * t ** 5
            H5 = 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5
            return H0 * ys[i] + H1 * h[i] * m[i] + H4 * h[i] * m[i + 1] + H5 * ys[i + 1]
        dH0 = -30 * t ** 2 + 60 * t ** 3 - 30 * t ** 4
        dH1 = 1 - 18 * t ** 2 + 32 * t ** 3 - 15 * t ** 4
        dH4 = -12 * t ** 2 + 28 * t ** 3 - 15 * t ** 4
        dH5 = 30 * t ** 2 - 60 * t ** 3 + 30 * t ** 4
        v = (dH0 * ys[i] + dH1 * h[i] * m[i] + dH4 * h[i] * m[i + 1] + dH5 * ys[i + 1]) / h[i]
        return np.where((s < xs[0]) | (s > xs[-1]), 0.0, v)


class Generator(MDD.Generator):
    """試行D ＋ ds_lean_with_height（E1）・ds_curl_lead（E2）・ds_back_hold_water（E6）。"""

    def __init__(self, version="art_on", kstar_dir=None, log=None, e_path=PARAMS_E, e_overrides=None, off=(), no_rebound_cache=None):
        self.RE, self.e_base_shas = load_e(e_path)
        if e_overrides:
            M8.deep_merge(self.RE, copy.deepcopy(e_overrides))
        self.e_path = e_path
        self.e_sha = MD.sha256_file(e_path)
        off = tuple(off)
        for n in off:
            if n not in E_NAMES and n not in MDD.NAMES and n != "tower_peak_off":
                raise ValueError("切れる名前は %s" % ",".join(E_NAMES + MDD.NAMES + ("tower_peak_off",)))
        self.e_off = off
        on = version == "art_on"
        self.e_on = {n: bool(on and self.RE[n].get("on", True) and n not in off) for n in E_NAMES}
        LW = self.RE["lean_with_height"]
        # --- E1：錨の進みの表と、表の時計の先回りの表（D の初期化の中で使うので先に作る）
        if self.e_on["lean_with_height"]:
            self._anc_P = Quintic(LW["anchor_progress_knots"])
            ck = LW["clock_offset_knots"]
            self._clk_D = Quintic(ck) if len(ck) > 1 else None
            self._clk_end = float(ck[-1][0])
            self._clk_d0 = float(ck[0][1])
            # 時計が進む向きだけ（g' = 1 + δ' > 0）
            gg = np.linspace(-12.0, -2.4, 9601)
            gv = self.pace_g(gg)
            assert np.all(np.diff(gv) > 0), "表の時計が逆に進む"
        # --- 設計28 の段階 b の尖った塔（ds_tower_peak）を切る（E1 の一部。切れる名前 tower_peak_off）
        tower_off = self.e_on["lean_with_height"] and bool(LW.get("tower_peak_off", True)) and "tower_peak_off" not in off
        self.e_tower_off = tower_off
        # --- E2：巻き下がりの形（kind = delayed_extension：C1 の伸びに比例の形の始まりを σ_c へ遅らせる。c1_overrides は試行C の C1 の値の上書き）
        c_ov = None
        CL = self.RE["curl_lead"]
        self.e_curl_kind = str(CL.get("kind", "c1_overrides")) if self.e_on["curl_lead"] else None
        if self.e_on["curl_lead"] and CL.get("c1_overrides"):
            c_ov = {"variants": {"C1": {k: v for k, v in CL["c1_overrides"].items()}}}
        if self.e_curl_kind == "delayed_extension":
            self.e_curl_s0 = float(CL["start_sigma"])
            self.e_curl_tup = float(CL["ramp_s"])
            self.e_curl_gam = float(CL["gamma_c_per_s"])
        # --- D の値の上書き（E の値として記録に残る）
        d_ov = copy.deepcopy(self.RE.get("d_overrides") or {})
        if self.e_on["lean_with_height"]:
            M8.deep_merge(d_ov, {"lean_pace": {"tables": list(LW["clock_tables"]), "psi_b": bool(LW.get("clock_psi_b", True))}})
            if LW.get("trial_b_overrides"):
                M8.deep_merge(d_ov, {"lean_pace": {"trial_b_overrides": copy.deepcopy(LW["trial_b_overrides"])}})
        BW = self.RE["back_hold_water"]
        if self.e_on["back_hold_water"] and BW.get("sigma_hold") is not None:
            M8.deep_merge(d_ov, {"back_hold": {"sigma_hold": float(BW["sigma_hold"])}})
        self._bw_end = None
        d_off = [n for n in off if n in MDD.NAMES]
        orig_init = MC.Generator.__init__
        sw = {"ds_tower_peak": False} if tower_off else None

        def init_wrap(gself, version_, curl_variant="C1", log=None, **kw):
            if sw:
                kw["switches"] = dict(kw.get("switches") or {}, **sw)
            if c_ov:
                kw["c_overrides"] = M8.deep_merge(copy.deepcopy(kw.get("c_overrides") or {}), copy.deepcopy(c_ov))
            return orig_init(gself, version_, curl_variant=curl_variant, log=log, **kw)
        MC.Generator.__init__ = init_wrap
        try:
            MDD.Generator.__init__(self, version, kstar_dir=kstar_dir, log=log, d_overrides=d_ov, off=d_off, no_rebound_cache=no_rebound_cache)
        finally:
            MC.Generator.__init__ = orig_init
        # E3：keypose の節点の細かい区間（τ −3〜0）の間隔（数値の条件。節点の Hermite の二階微分の段を小さくして、節点のこまの法線のちらつきを抑える）
        kp = self.RE.get("keypose") or {}
        if kp.get("fine_step_s"):
            self.P["knots"] = dict(self.P["knots"], fine_step_s=float(kp["fine_step_s"]))
        tags = [n for n in E_NAMES if self.e_on[n]]
        self.variant = self.variant + "+ds28r01e[%s]" % ",".join(tags) + ("" if not off else "-offE[%s]" % ",".join(off))

    # ------------------------------------------------------------ E1：表の時計と錨の進み
    def pace_g(self, s):
        s = np.asarray(s, np.float64)
        if not getattr(self, "e_on", {}).get("lean_with_height", False):
            return MDD.Generator.pace_g(self, s)
        if self._clk_D is None:
            return np.where(s < self._clk_end, s + self._clk_d0, s)
        return np.where(s < self._clk_end, s + self._clk_D(s), s)

    def anchor_q(self, r, tau, sig_r, M):
        if self.e_on["lean_with_height"] and sig_r < -2.4:
            q_on = self.q_on[r]
            p = float(self._anc_P(sig_r))
            return q_on + (self.anc["D_s"] - q_on) * (1.0 - p)
        return MDD.Generator.anchor_q(self, r, tau, sig_r, M)

    def _tables28(self):
        """試行D の _tables28（表の時計と背の保持）の前に、E1 の帯の上面の角と頂の帽子の表を差し替える（塔を切った時だけ）。"""
        MC.Generator._tables28(self)
        LW = self.RE["lean_with_height"]
        if self.e_on["lean_with_height"] and self.e_tower_off:
            if LW.get("strip_upper_knots"):
                self.tab_th1 = MD.Tab(LW["strip_upper_knots"], 0.0)
                assert abs(float(self.tab_th1(-2.4)) - self.th1f) < 1e-9, "帯の上面の角は噴流の始まりで %.1f°" % self.th1f
            if LW.get("strip_under_knots"):
                self.tab_th2 = MD.Tab(LW["strip_under_knots"], 0.0)
                assert abs(float(self.tab_th2(-2.4)) - self.th2f) < 1e-9, "帯の下面の角は噴流の始まりで %.1f°" % self.th2f
            if LW.get("cap_knots") and self.cap_on:
                self.tab_cap = MD.Tab(LW["cap_knots"], self.P["back"]["crest_cap"].get("omega_end_slope", 0.0))
                assert abs(float(self.tab_cap(0.0))) < 1e-12, "頂の帽子は t* で 0"
        # 以下は試行D の _tables28 と同じ（表の時計・背の保持の時計で読む）
        LP = self.RD["lean_pace"]
        pace_tabs = set(LP["tables"]) if self.d_on["lean_pace"] else set()
        hold_tabs = set(self.RD["back_hold"]["tables"]) if self.d_on["back_hold"] else set()
        for nm in sorted(pace_tabs | hold_tabs):
            if not hasattr(self, nm):
                continue
            p_ = nm in pace_tabs
            h_ = nm in hold_tabs
            if p_ and h_:
                setattr(self, nm, MDD.Remap(getattr(self, nm), lambda s_: self.hold_h(self.pace_g(s_))))
            elif p_:
                setattr(self, nm, MDD.Remap(getattr(self, nm), self.pace_g))
            else:
                setattr(self, nm, MDD.Remap(getattr(self, nm), self.hold_h))

    # ------------------------------------------------------------ E2：巻き下がりの始まりを唇が見える頃へ（delayed_extension）
    def curl_shape(self, r, tau, deriv=True):
        if getattr(self, "e_curl_kind", None) != "delayed_extension" or not self.curl_on:
            return MC.Generator.curl_shape(self, r, tau, deriv)
        tc = self.e_curl_s0 + float(self.lag[r])
        Phi, psi, dpsi = MB.carry_shape(float(tau) - tc, self.e_curl_tup, self.e_curl_gam)
        P1 = MB.carry_shape(-tc, self.e_curl_tup, self.e_curl_gam)[0]
        return Phi / P1, psi / P1, dpsi / P1

    # ------------------------------------------------------------ E6：水の釣り合いの山を σ_hold で終える
    def _bw_setup(self):
        """行ごとに、σ_r(τ) = σ_hold となる τ（噴流の始まりの後）。1 ms の格子で求める。"""
        BW = self.RE["back_hold_water"]
        sh = float(BW.get("bump_end_sigma") or BW.get("sigma_hold") or self.hold_s1)
        tg = np.round(np.arange(-2.6, 1e-9, 1e-3), 9)
        S = np.stack([self.sigma(float(t)) for t in tg], 0)         # (n, nv)
        end = np.zeros(self.K.nv)
        for r in range(self.K.nv):
            s = S[:, r]
            k = np.nonzero(s >= sh)[0]
            k = int(k[0]) if len(k) else len(tg) - 1
            if k == 0:
                end[r] = float(tg[0])
            else:
                f = (sh - s[k - 1]) / max(s[k] - s[k - 1], 1e-12)
                end[r] = float(tg[k - 1] + f * (tg[k] - tg[k - 1]))
        self._bw_end = np.minimum(end, -1e-3)
        self._bw_sigma_hold = sh

    def _bw_mode(self):
        return str(self.RE["back_hold_water"].get("mode", "end_early")) if self.e_on["back_hold_water"] else None

    def _back(self, r, S, Lb_r, Arow, Yrow):
        """E6（mode = lower_back）：水の釣り合いの山の分 δ = Lb − Lb_表 を、背の下の部分だけに掛ける（頂の近くの背は表の Lb のまま）。
        K* の背の高さの割合 η = Y*/y_頂 で、重み w = 1 − smoothstep((η − η0)/(η1 − η0))（η ≤ η0 で 1、η ≥ η1 で 0）。
        背の列の横の位置 A = a_頂 + (Lb_表 + w·δ)·(A* − a*_頂)。δ ≥ 0 なら列の順は保たれる。足の位置の上限（シートの後ろの端）は D と同じ。"""
        if self._bw_mode() != "lower_back":
            return M8.Generator._back(self, r, S, Lb_r, Arow, Yrow)
        Lt = float(S["Lb"][r])
        d = float(Lb_r) - Lt
        capped = M8.Generator._back(self, r, S, Lt, Arow, Yrow)
        if abs(d) < 1e-12 or not (self.sw["ds_body_narrow"] or self.sw["ds_back_steep"]):
            return capped
        A0, Y0 = self.K.A, self.K.Y
        jB = self.jB
        root = int(self.root[r])
        ac = S["a_c"][r]
        ar = self.a_root[r]
        bw = max(ar - A0[r, jB], 1e-6)
        cap_ = max((ac - (A0[r, 0] + float(self.P["back"]["back_foot_margin_m"]))) / bw, 1.0)
        BW = self.RE["back_hold_water"]
        e0, e1 = [float(v) for v in BW.get("lower_back_eta", [0.5, 0.85])]
        eta = Y0[r, jB:root + 1] / max(float(self.y_root[r]), 1e-9)
        w = 1.0 - MD.smoothstep((eta - e0) / (e1 - e0))
        L = np.minimum(Lt + w * d, cap_)
        Anew = ac + L * (A0[r, jB:root + 1] - ar)
        if self.cap_on:
            # 頂の帽子（D の _back と同じ式）を新しい横の位置で掛け直す
            om_ = float(self.tab_cap(S["sig"][r])) * S["wbd"][r]
            if om_ > 0.0:
                H = self.H[r]
                yc = S["y_c"][r]
                sy = yc / max(self.y_root[r], 1e-9)
                Yb = sy * Y0[r, jB:root + 1]
                dd = np.maximum(ac - Anew, 0.0)
                fcap = 1.0 - om_ * (1.0 - MD.smoothstep(dd / max(self.cap_D_over_H * H, 1e-6)))
                Yrow[jB:root + 1] = yc - (yc - Yb) * fcap
        Arow[jB:root + 1] = Anew
        Arow[:jB + 1] = A0[r, 0] + self.fb[r] * (Arow[jB] - A0[r, 0])
        return int(bool(np.any(Lt + w * d > cap_ + 1e-12)))

    def _bump(self, r, tau):
        if self._bw_mode() == "lower_back":
            return M8.Generator._bump(self, r, tau)
        if not self.e_on["back_hold_water"]:
            return M8.Generator._bump(self, r, tau)
        if self._bw_end is None:
            self._bw_setup()
        Tr = float(self.T_row[r])
        te = float(self._bw_end[r])
        if tau <= -Tr - self.water_rise or tau >= te:
            return 0.0
        if tau < -Tr:
            x = (tau + Tr + self.water_rise) / self.water_rise
        else:
            x = 1.0 - (tau + Tr) / (te + Tr)
        x = min(max(x, 0.0), 1.0)
        return x * x * x * (10.0 - 15.0 * x + 6.0 * x * x)

    def _bump2(self, r, tau):
        if self._bw_mode() == "lower_back":
            return M8.Generator._bump2(self, r, tau)
        if not self.e_on["back_hold_water"]:
            return M8.Generator._bump2(self, r, tau)
        if self._bw_end is None:
            self._bw_setup()
        Tr = float(self.T_row[r])
        te = float(self._bw_end[r])
        if -Tr < tau < te:
            u = (tau + Tr) / (te + Tr)
            if str(self.RE["back_hold_water"].get("bump2_shape", "sin2")) == "poly3":
                # (4u(1 − u))³：両端で値・傾き・二階微分 0（sin² は端で二階微分 ≠ 0。t* の前で止めると加速度が跳ぶ）
                b2 = (4.0 * u * (1.0 - u)) ** 3
            else:
                b2 = math.sin(math.pi * u) ** 2
        else:
            b2 = 0.0
        return np.array([self._bump(r, tau), b2])

    # ------------------------------------------------------------ 記録
    def summary(self):
        s = MDD.Generator.summary(self)
        LW = self.RE["lean_with_height"]
        s.update(number="設計28修正01 試行E",
                 ds28r01e=dict(on=self.e_on, off=list(self.e_off), params_sha256=self.e_sha, base_sha256=self.e_base_shas,
                               tower_peak_off=bool(self.e_tower_off),
                               anchor_progress_knots=LW["anchor_progress_knots"] if self.e_on["lean_with_height"] else None,
                               clock_offset_knots=LW["clock_offset_knots"] if self.e_on["lean_with_height"] else None,
                               clock_tables=LW["clock_tables"] if self.e_on["lean_with_height"] else None,
                               strip_upper_knots=LW.get("strip_upper_knots") if self.e_on["lean_with_height"] else None,
                               strip_under_knots=LW.get("strip_under_knots") if self.e_on["lean_with_height"] else None,
                               cap_knots=LW.get("cap_knots") if self.e_on["lean_with_height"] else None,
                               curl_lead={k: v for k, v in self.RE["curl_lead"].items() if not k.startswith(("note", "kind_ja", "name"))}
                               if self.e_on["curl_lead"] else None,
                               curl_kind=getattr(self, "curl_kind", None), free_release_fraction=getattr(self, "f_free", None),
                               prerelease_decel_ramp_s=getattr(self, "dec_T", None),
                               back_hold_water_sigma=getattr(self, "_bw_sigma_hold", None),
                               back_hold_water_end_tau={str(r): round(float(self._bw_end[r]), 4) for r in (159, 192)} if self._bw_end is not None else None,
                               d_overrides=self.RE.get("d_overrides")))
        return s
