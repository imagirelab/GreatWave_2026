# -*- coding: utf-8 -*-
"""設計28修正01（Q13）：唇の伸び出しを、頂の上昇の後半に重ねる生成器。

README
======
設計28 の生成器（Tools/GWWaveGen/ds28/ds28_physoff.py の Generator＝ds28_model.Generator に ds_crest_tower・ds_undercut_kstar を足したもの）を
import し、Q13 で変える所だけを上書きする。設計26〜28 のファイルは変えない（ds28r01_params.json が ds28_params.json の SHA-256 を照合する）。

Q13（利用者）：原画の手前の爪の形の大きな部分（唇と爪）が、波が最も高くなった後に伸び出しているのがおかしい。唇は、平らな海から
最高点へ育つ過程の後半に、もう伸び始めているようにする。

設計28 の動き（峰の行）：頂は段階 a（τ −4.2 s、0.5H*）から噴流の始まり（τ −2.4 s）まで 1.8 s で 0.5 → 0.89 と急に上がり、そこから
t* までは 1 m/s（0.044 H*/s）でほとんど止まる。唇は始まりから放出され、伸び出しの半分は最後の約 0.7 s（頂 ≥ 0.93H*）。既定の時間曲線は
τ −2.18〜−1.43 s に 0.5 倍へ落ちるので、画面では上昇が実時間、唇の伸び出しが 0.5 倍になり、さらに離れて見えた。

この生成器で足した美術の誘導（名前の付いた値。切ると設計28 と同じ動き）：
  ds_rise_overlap：頂の高さの時刻の表（ds28r01_params.json の rise_overlap.rate_table）。段階 a までの育ちはほぼ同じにし、その後の上昇を
      t* まで続ける：噴流の始まり（σ −2.4）で約 0.73H*（設計28 は 0.894）、σ −1.2 で約 0.87、t* で 1.0（上昇の速さは t* まで 0.11 H*/s）。
      行ごとに y_c = y_頂(K*)·ĥ(σ_r(τ))（始まりの前と後で同じ表）。
作り方の変更（切り替えではなく ds_rise_overlap を入れた版の作り方）：
  唇（κ = 1 の行も）：頂の上昇が一定でないので、放出の前の点（帯の置き場）の地面の位置・速さ・加速度を数値微分で取り、放出の補間を経て
      重力だけで K* へ着くよう打ち出しを解く（設計28 の κ < 1 の行と同じ書き方。放出の時刻は設計28 と同じ）。
  ds_undercut_kstar の始まりの張り出しの高さの係数 h_on を ĥ(−2.4) に替える。
修正1・2（設計28 の名前の付いた誘導の値の変更。ds_rise_overlap を入れた版だけ。ds28r01_params.json）：
  ds_tower_peak の時刻を 0.1 s 早める（tower_overrides。修正1）。
  唇（κ = 1）の放出の前の速さ・加速度を、頂の動きの解析的な微分（噴流の始まり以後の側）にした（修正1。初回は帯の点の中心差分で、唇先が折れた）。
  ds_approach_kstar の水の釣り合いは設計28 の値のまま（修正1 で band_frac 0.06 → 0.15 にしたが P17 が 15% を超えたので修正2 で戻した。
  approach.water_overrides の仕組みは残す）。

使い方（numpy だけ）：
    from ds28r01_model import Generator
    g = Generator("art_on")                          # 設計28修正01 の既定（15 個の誘導をすべて入れる）
    g = Generator("art_off")                         # 15 個すべて切る（設計28 の切った版＝物理だけと同じ動き）
    g = Generator("art_on", rise_overlap=False)      # ds_rise_overlap だけ切る（＝設計28 の入れた版の動き）
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
PARAMS_R01 = os.path.join(HERE, "ds28r01_params.json")
G = MD.G
integ_S = MD.integ_S
smoothstep = MD.smoothstep


def load_r01(path=PARAMS_R01):
    R = MD.load_json(path)
    for key, fn in (("sha256", R["base"]["path"]), ("generator_sha256", R["base"]["generator"])):
        p = os.path.join(REPO, fn)
        if MD.sha256_file(p) != R["base"][key]:
            raise SystemExit("[ds28r01] base のファイルの SHA-256 が記録と違います：%s" % fn)
    if MD.sha256_file(os.path.join(DS28, "ds28_model.py")) != R["base"]["model_sha256"]:
        raise SystemExit("[ds28r01] ds28_model.py の SHA-256 が記録と違います")
    return R


class Generator(PO.Generator):
    """設計28 の生成器（ds28_physoff.Generator）＋ ds_rise_overlap（Q13）。既定は版に従う（art_on で入り、art_off で切り）。"""

    def __init__(self, version="art_on", params_path=M8.PARAMS_JSON, log=None, switches=None, crest_tower=None, undercut_kstar=None,
                 rise_overlap=None, r01_path=PARAMS_R01):
        self.R = load_r01(r01_path)
        self.r01_path = r01_path
        self.r01_sha = MD.sha256_file(r01_path)
        self.rise_overlap = (version == "art_on") if rise_overlap is None else bool(rise_overlap)
        PO.Generator.__init__(self, version, params_path=params_path, log=log, switches=switches, crest_tower=crest_tower,
                              undercut_kstar=undercut_kstar)
        if self.rise_overlap != (version == "art_on"):
            self.variant = self.variant + "+ds_rise_overlap=%d" % int(self.rise_overlap)

    # ------------------------------------------------------------ 表（ds_rise_overlap）
    def _tables28(self):
        if self.rise_overlap:
            # 修正1：ds_tower_peak の時刻を 0.1 s 早める（ds28r01_params.json の tower_overrides。ds28_model._tables28 が読む前に置き換える）
            to = self.R.get("tower_overrides") or {}
            tw = self.P["ds28"]["tower"]
            if to.get("strip_angles_deg_table_upper"):
                tw["strip_angles_deg_table"]["upper"] = copy.deepcopy(to["strip_angles_deg_table_upper"])
            if to.get("crest_cap_omega_table"):
                tw["crest_cap_omega_table"] = copy.deepcopy(to["crest_cap_omega_table"])
        M8.Generator._tables28(self)
        self.h_on_design28 = float(self.P["crest_height"]["H_over_Hstar_at_onset"])
        if not self.rise_overlap:
            return
        ro = self.R["rise_overlap"]
        self.tab_rise = MD.RateTab(ro["rate_table"], float(ro["h_end"]))
        self.h_on_rise = float(self.tab_rise(-2.4))
        # ds_undercut_kstar の始まりの張り出し Lo_on·h_on·H の h_on を、始まりの時の頂の高さの割合にする（ds28_model._approach_setup が読む）
        self.P["crest_height"]["H_over_Hstar_at_onset"] = self.h_on_rise
        # 修正1：ds_approach_kstar の水の釣り合いの値を上書き（ds28r01_params.json の approach.water_overrides。self.ap は同じ辞書）
        for k, v in (self.R.get("approach", {}).get("water_overrides") or {}).items():
            self.P["ds28"]["approach"]["water"][k] = copy.deepcopy(v)
        # 修正1：ds_body_narrow の背面の横の倍率 Lb の表の上書き（ds28r01_params.json の back_overrides.Lb_table。段階 b の塔の縦横比を保つ）
        bo = self.R.get("back_overrides") or {}
        if bo.get("Lb_table"):
            self.tab_Lb = MD.Tab(bo["Lb_table"], float(bo.get("Lb_end_slope", self.P["back"]["Lb_end_slope"])))
            assert abs(self.tab_Lb(0.0) - 1.0) < 1e-12

    def crest(self, tau):
        if not self.rise_overlap:
            return PO.Generator.crest(self, tau)
        T = -tau
        sig = self.sigma(tau)
        shear = (self.D(T, self.tau0) - self.D(T, self.T_row)) * self.w_body
        a_c = self.a_root + shear
        y_c = self.y_root * self.tab_rise(sig)
        return a_c, y_c, sig, shear

    # ------------------------------------------------------------ 唇（層4）：κ = 1 の行も放出の前の動きから打ち出しを解く
    def _strip_ground(self, r, tau):
        """行 r の放出の前の帯の点（地面の断面座標）。_strip_local から波の枠の足し分を引いたものと同じ。"""
        L = self.lip[r]
        sig = float(self.sigma(tau)[r])
        off = self._strip_off(L, float(self.tab_th1(sig)), float(self.tab_th2(sig)))
        y = float(self.crest(tau)[1][r]) if not self.rise_overlap else self.y_root[r] * float(self.tab_rise(sig))
        return np.array([self.a_root[r] - float(self.D(-tau, self.T_row[r])), y])[None, :] + off

    def _crest_kin(self, r, T):
        """行 r の頂の地面の速さと加速度（放出 T 秒前の時刻 τ = −T、噴流の始まり以後の側の値）。解析的な微分。
        水平：a = a_頂 − D(T, T_row)。T ≤ T_row で da/dτ = β c0 + (1 − β) c0 T/T_row、d²a/dτ² = −(1 − β) c0/T_row。
        縦：y = y_頂·ĥ(σ)、dy/dτ = y_頂·ĥ'(σ)·σ'、d²y/dτ² = y_頂·(ĥ''(σ)·σ'² + ĥ'(σ)·σ'')。ĥ' は速さの折れ線、ĥ'' はその区間の傾き（右側）。"""
        Tr_ = float(self.T_row[r])
        b, c0 = self.beta, self.c0
        if T <= Tr_:
            vx = b * c0 + (1 - b) * c0 * T / Tr_
            ax = -(1 - b) * c0 / Tr_
        else:
            vx, ax = c0, 0.0
        tau = -T
        lag = float(self.lag[r])
        hq = self.h_on
        x = tau + Tr_
        Kq = 1.0 / (Tr_ - hq / 2)
        if x <= 0:
            dQ, d2Q = 0.0, 0.0
        elif x < hq:
            xh = x / hq
            dQ = Kq * (3 * xh ** 2 - 2 * xh ** 3)
            d2Q = Kq * (6 * xh - 6 * xh ** 2) / hq
        else:
            dQ, d2Q = Kq, 0.0
        s1 = 1.0 + lag * dQ
        s2 = lag * d2Q
        sig = float(self.sigma(tau)[r])
        tb = self.tab_rise
        xs, rs = tb.x, tb.r
        sc = min(max(sig, xs[0]), xs[-1])
        i = int(min(max(np.searchsorted(xs, sc, side="right") - 1, 0), len(xs) - 2))
        sl = (rs[i + 1] - rs[i]) / (xs[i + 1] - xs[i])
        rate = rs[i] + sl * (sc - xs[i])
        yr = float(self.y_root[r])
        return np.array([vx, yr * rate * s1]), np.array([ax, yr * (sl * s1 * s1 + rate * s2)])

    def _lip_setup(self):
        M8.Generator._lip_setup(self)
        self.lip_thrown_rows = []
        if not self.rise_overlap:
            return
        h = float(self.kl["derivative_h_s"])
        for r in sorted(self.lip.keys()):
            L = self.lip[r]
            if L.get("mode") != "strip":
                continue          # κ < 1 の行は設計28 の打ち出しの弱め（放出の前の点は crest() を通るので新しい頂の高さに従う）
            Tc = L["Tc"]
            Tr = L["Tr"]
            n = len(L["cols"])
            P0 = np.zeros((n, 2))
            V0 = np.zeros((n, 2))
            A0v = np.zeros((n, 2))
            cache = {}
            cc = {}
            for i in range(n):
                t0 = -float(Tc[i])
                if t0 not in cache:
                    cache[t0] = self._strip_ground(r, round(min(t0, 0.0), 12))
                P0[i] = cache[t0][i]
                # 修正1：放出の前の速さ・加速度は、頂の動き（地面の頂 a_頂 − D(T, T_row)、y_頂·ĥ(σ_r(τ))）の解析的な微分で、噴流の始まりの
                # 後ろ側の値（放出はどの点も始まり以後）。水平は設計27・28 の帯の行の式と同じ（ci・−kdec）。帯の置き場の角（表は σ −2.4 で
                # 傾き 0 で終わり、その後は一定）の動きは入れない。初回（r00）は帯の点そのものを中心差分し、ちょうど噴流の始まりに放出される
                # 唇先だけが表の終わりの二階微分の跳び（縦に約 −8 m/s²）の半分を拾って、隣より 0.1〜0.15 m 下を飛び、唇先で折れた
                # （P13(5a)(5f)(5g)(6)）。後ろ向きの差分でも、始まりをまたぐ唇先だけ波の枠の減速（−kdec）を拾わず横にずれる
                if t0 not in cc:
                    cc[t0] = self._crest_kin(r, float(Tc[i]))
                V0[i], A0v[i] = cc[t0]
            IS, ISg = integ_S(Tc, Tr)
            if self.sw["ds_lip_target_kstar"]:
                Kt = L["Kt"]
                v2 = (Kt - P0 - V0 * (Tc - IS)[:, None] - A0v * (Tc ** 2 / 2 - ISg)[:, None] + np.stack([np.zeros(n), G * ISg], 1)) / IS[:, None]
            else:
                v2 = np.stack([L["u2"], L["w2"]], 1)
            L.update(mode="damped", thrown=True, P0=P0, V0=V0, A0=A0v, v2=v2, release_power=1.0)
            self.lip_thrown_rows.append(int(r))

    def progress(self, r, tau, S):
        L = self.lip.get(r)
        if L is not None and L.get("thrown"):
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
            if L.get("thrown"):
                t_on = -float(self.T_row[r])
                S = self._shared(t_on)
                L["rim_a_on"] = self._rim_local_a(r, t_on, S)
                L["rim_span"] = float(self.K.A[r, int(L["rim"])] - L["rim_a_on"])
        M8.Generator._onset_setup(self)

    # ------------------------------------------------------------ 記録
    def launch_table(self, rows=None):
        """行ごとの唇先の放出・打ち出しの記録（放出の時刻、放出の高さと頂、打ち出しの速さ、飛ぶ時間、頂点の高さと頂の高さ）。"""
        out = {}
        rows = rows if rows is not None else [int(self.K.main_row), 192]
        for r in rows:
            L = self.lip.get(r)
            if L is None:
                continue
            it = int(L["tip"]) - int(L["root"]) - 1
            Tc = float(L["Tc"][it])
            H = float(self.H[r])
            _, yc_rel, _, _ = self.crest(-Tc)
            if L.get("mode") == "damped":
                v = L["v2"][it]
                P0 = L["P0"][it]
                V0 = L["V0"][it]
            else:
                v = np.array([L["u2"][it], L["w2"][it]])
                P0 = L["Pg"][it]
                V0 = np.array([L["ci"][it], L["vH"]])
            # 頂点：放出の後を 240 Hz でたどる
            taus = np.linspace(-Tc, 0.0, int(Tc * 240) + 1)
            ys = []
            ycs = []
            for tv in taus:
                Xg, rel, _ = self.lip_state(r, float(tv), float(self.sigma(float(tv))[r]))
                ys.append(float(Xg[it, 1]) if rel[it] else float(P0[1]))
                ycs.append(float(self.crest(float(tv))[1][r]))
            ys = np.array(ys)
            ycs = np.array(ycs)
            k = int(np.argmax(ys))
            out[str(r)] = dict(c_m=float(self.K.c[r]), H_kstar_m=H, release_tau=-Tc, ramp_s=float(L["Tr"][it]), flight_s=Tc,
                               release_y_m=float(P0[1]), crest_at_release_over_H=float(yc_rel[r] / H),
                               prerelease_vel=[float(V0[0]), float(V0[1])], launch_u_over_c0=float(v[0] / self.c0),
                               launch_w_mps=float(v[1]), launch_w_over_sqrt_gH=float(v[1] / math.sqrt(G * H)),
                               apex_y_m=float(ys[k]), apex_tau=float(taus[k]), crest_at_apex_m=float(ycs[k]),
                               apex_minus_crest_m=float(ys[k] - ycs[k]), max_tip_minus_crest_m=float(np.max(ys - ycs)),
                               kstar_tip=[float(L["Kt"][it][0]), float(L["Kt"][it][1])], mode=L.get("mode"), thrown=bool(L.get("thrown", False)))
        return out

    def summary(self):
        s = PO.Generator.summary(self)
        s.update(number="設計28修正01", ds_rise_overlap=bool(self.rise_overlap), r01_params_sha256=self.r01_sha,
                 lip_thrown_rows=len(getattr(self, "lip_thrown_rows", [])))
        if self.rise_overlap:
            s.update(h_on_rise=round(self.h_on_rise, 4), h_on_design28=round(self.h_on_design28, 4),
                     rise_profile_peak_row={("%.2f" % sg): round(float(self.tab_rise(sg)), 4) for sg in (-10.12, -8.1, -6.0, -4.4, -4.2, -3.5, -3.4, -2.8, -2.4, -2.0, -1.2, -0.5, 0.0)})
        return s
