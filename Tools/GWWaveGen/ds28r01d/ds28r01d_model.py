# -*- coding: utf-8 -*-
"""設計28修正01 試行D：利用者が選んだ試行C の C1（Q15）の上に、Q16・Q17 の動きの直しを足す生成器。K* はフォルダーで受け取る。

README
======
試行C の Generator（Tools/GWWaveGen/ds28r01c/ds28r01c_model.py、変種 C1）を import して継承する。試行A〜C・設計26〜29 の
ファイルは変えない。値はすべて ds28r01d_params.json（名前の付いた値。どれも切れる）。

K*（t* の姿）：Generator(kstar_dir=...) のフォルダー（*.gwb・*_rows.npz・*_meta.json。ds28r01d_kstar.py）。目印の列 j_B・j_corner・j_E は
meta から。平らな縁の y < 0（前の谷・背後の谷）は split_trough で分け、生成器は土台（縁は y = 0）を K* として動かし、谷は near_trough で足す。
K*′（別の作業が作る最後の一コマ）ができたら、そのフォルダーを渡せばよい（コードは変えない）。

足したもの（名前の付いた値。M1〜M4 は依頼の番号）：
  M1 ds_lean_pace（美術の誘導、Q17 の原型 P10）：段階 b/c の表を間合いの時計 g(σ) で読み、内壁の錨を σ −6.6 → −3.0 で寄せ、唇の運びを
     σ −3.7 から 1.0 s で立ち上げる（試行B の値の上書き）。噴流の始まり（σ −2.4）より後は変えない。
     ds_timewarp_lean_slow（時間曲線 F2）は ds28r01d_timewarp.py。
  M2 num_no_rebound_after_apex（数値の条件）：唇・管の天井の点の高さを、頂点（最高点）の後は上へ加速しない（ブレーキ・再上昇しない）
     ように直す。120 Hz の格子で高さ y(τ) を作り、頂点の前は下がって戻るくぼみを埋め、頂点の 0.15 s 前から t* までの傾きを単調に減る列へ
     当てはめ（和を保つ＝t* は同じ）、ならした差 δ(τ) を補間して足す。
  M3 near_trough（物理。深さの時刻の係数だけ）：K* の谷 T* を s_r(τ) = (y_c,r(τ)/y_c,r(0))^p で掛けて縁の頂点に足す（足と一緒に動き、
     頂が高くなるほど深く、t* で最も深い）。海の釣り合い（搬送波の振幅の式）に本体と一緒に入る。周りの海の静めは掛けない。
  M4 num_row_timing_smooth（数値の条件）：行ごとの時刻 T_row の V 字の折れをなめらかに。
     num_row_smooth（数値の条件）：爪の細部を除いた断面を行の方向にガウス（σ 0.5 m）でならし、t* に近づくと（τ −1.5 s から）K* の
     行ごとの細部を戻す。t* は K* のまま。
     ds_back_hold（美術の誘導）：背の表（Lb・頂の帽子 ω）を σ −1.0 で t* の値に着けて止める（最後の 1 秒に頂を尖らせない）。
（行ごとの目印の列を小数にする作り直しは、Q16 の計画の順のとおり、num_row_smooth で J1〜J3 が通らない時にだけ行う。）

使い方（numpy だけ）：
    from ds28r01d_model import Generator
    g = Generator(kstar_dir="Unity/Build/Design/28R01D/kstar_foot")      # 既定（試し）
    g = Generator(kstar_dir="<K*′ のフォルダー>", d_overrides={"row_smooth": {"sigma_m": 0.75}})
    g = Generator(off=["near_trough"])                                    # 1 つずつ切る（P20）
    X = g.local(-2.0)
"""
import copy
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DSC = os.path.abspath(os.path.join(HERE, "..", "ds28r01c"))
if DSC not in sys.path:
    sys.path.insert(0, DSC)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds28r01c_model as MC  # noqa: E402
import ds28r01d_kstar as KS  # noqa: E402

MB, M8, MD = MC.MB, MC.M8, MC.MD
REPO = MD.REPO
PARAMS_D = os.path.join(HERE, "ds28r01d_params.json")
NAMES = ("lean_pace", "row_timing", "near_trough", "row_smooth", "back_hold", "no_rebound")


def load_d(path=PARAMS_D):
    R = MD.load_json(path)
    shas = {}
    for k in ("trial_c_model", "trial_c_params"):
        p = os.path.join(REPO, R["base"][k])
        if not os.path.isfile(p):
            raise SystemExit("[ds28r01d] base のファイルがありません：%s" % R["base"][k])
        shas[R["base"][k]] = MD.sha256_file(p)
    return R, shas


def s5(x):
    x = np.clip(x, 0.0, 1.0)
    return x ** 3 * (x * (6 * x - 15) + 10)


class Remap:
    """表 f を時計 m(σ) で読む（f(m(σ))）。表の属性はそのまま見せる。"""

    def __init__(self, f, m):
        self.f = f
        self.m = m

    def __call__(self, s, *a, **k):
        return self.f(self.m(s), *a, **k)

    def __getattr__(self, n):
        return getattr(self.f, n)


def antitonic(s):
    """単調に減る列への最小二乗の当てはめ（PAVA）。和を保つ。"""
    vals, cnts = [], []
    for v in s.tolist():
        vals.append(v)
        cnts.append(1)
        while len(vals) > 1 and vals[-2] < vals[-1]:
            c2 = cnts.pop()
            v2 = vals.pop()
            c1 = cnts[-1]
            vals[-1] = (vals[-1] * c1 + v2 * c2) / (c1 + c2)
            cnts[-1] = c1 + c2
    return np.repeat(np.array(vals), np.array(cnts))


def gauss_nearest(x, sig):
    if sig < 0.5:
        return x
    r = int(math.ceil(3 * sig))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
    k /= k.sum()
    xp = np.concatenate([np.full(r, x[0]), x, np.full(r, x[-1])])
    return np.convolve(xp, k, mode="valid")


class _KStarAt:
    """MD.KStar の代わり（生成器の準備の間だけ差し替える）。フォルダーの K* を読み、縁の谷を分けた土台を行の断面にする。"""
    kdir = None

    def __init__(self, P):
        K = KS.load(self.kdir)
        self.src = K
        self.dir = os.path.join(REPO, K["dir"])
        self.sha = {"gwb": K["sha"]["gwb"], "rows": K["sha"]["rows"], "meta": K["sha"]["meta"]}
        g = KS.read_gwb(K["paths"]["gwb"])
        self.tris = g["tris"]
        self.Xgwb = g["X"][0].astype(np.float64)
        self.nu, self.nv = g["nu"], g["nv"]
        lm = K["landmarks"]
        # 目印の列を K* の meta から（生成器の P の profile_columns を書き換える。記録に残る）
        P["profile_columns"] = dict(P["profile_columns"], j_B=int(lm["j_B"]), j_corner=int(lm["j_corner"]), j_E=int(lm["j_E"]))
        P["inputs"] = dict(P["inputs"], kstar_dir=K["dir"], kstar_gwb_sha256=K["sha"]["gwb"], kstar_rows_sha256=K["sha"]["rows"],
                           kstar_meta_sha256=K["sha"]["meta"])
        self.landmarks = lm
        self.A = K["A"]
        Ybase, T = KS.split_trough(K["A"], K["Y"], int(lm["j_B"]), int(lm["j_E"]))
        self.Y = Ybase
        self.Y_full = K["Y"]
        self.T_trough = T
        self.c = K["c"]
        fr = K["meta"]["frame"]
        self.e = np.array(fr["e_crest"], np.float64)
        self.t = np.array(fr["t_travel"], np.float64)
        self.O = np.array(fr["section_origin_world"], np.float64)
        self.up = np.array([0.0, 1.0, 0.0])
        self.main_row = int(K["meta"]["rows"]["main_row"])
        self.X = self.world_from_section(self.A, self.Y_full)          # K* のワールド（谷を含む。t* の比べはこれ）
        self.recon_max_m = float(np.abs(self.X - self.Xgwb).max())

    def world_from_section(self, A, Y, O=None):
        O = self.O if O is None else O
        return (O[None, None, :] + self.c[:, None, None] * self.e[None, None, :]
                + A[..., None] * self.t[None, None, :] + Y[..., None] * self.up[None, None, :])


class Generator(MC.Generator):
    """試行C の C1 ＋ ds_lean_pace・num_row_timing_smooth・near_trough・num_row_smooth・ds_back_hold・num_no_rebound_after_apex。"""

    def __init__(self, version="art_on", kstar_dir=None, curl_variant=None, log=None, d_path=PARAMS_D, d_overrides=None, off=(),
                 no_rebound_cache=None):
        self.RD, self.d_base_shas = load_d(d_path)
        if d_overrides:
            M8.deep_merge(self.RD, d_overrides)
        self.d_path = d_path
        self.d_sha = MD.sha256_file(d_path)
        self.d_off = tuple(off)
        for n in self.d_off:
            if n not in NAMES:
                raise ValueError("切れる名前は %s" % ",".join(NAMES))
        on = version == "art_on"
        self.d_on = {n: bool(on and self.RD[n].get("on", True) and n not in self.d_off) for n in NAMES}
        self.kstar_dir = kstar_dir or self.RD["kstar"]["dir_default"]
        self._rs_ready = False
        self._nr_ready = False
        # 間合いの時計と背の保持（表を読む前に決める）
        LP = self.RD["lean_pace"]
        self.pace_s0, self.pace_dl = float(LP["clock_s0"]), float(LP["clock_delta"])
        BH = self.RD["back_hold"]
        self.hold_s0, self.hold_s1 = float(BH["sigma_start"]), float(BH["sigma_hold"])
        _KStarAt.kdir = self.kstar_dir
        orig_ks, orig_lb = MD.KStar, MB.load_b
        b_over = copy.deepcopy(LP["trial_b_overrides"]) if self.d_on["lean_pace"] else None

        def load_b(path=MB.PARAMS_B):
            R, s = orig_lb(path)
            if b_over:
                M8.deep_merge(R, copy.deepcopy(b_over))
            return R, s
        MD.KStar = _KStarAt
        MB.load_b = load_b
        try:
            MC.Generator.__init__(self, version, curl_variant=curl_variant or self.RD["base"]["curl_variant"], log=log)
        finally:
            MD.KStar = orig_ks
            MB.load_b = orig_lb
        tags = [n for n in NAMES if self.d_on[n]]
        self.variant = self.variant + "+ds28r01d[%s]" % ",".join(tags) + ("" if not self.d_off else "-off[%s]" % ",".join(self.d_off))
        # num_row_smooth：t* の断面（ならしも δ も無しで）と、行の方向のガウスの重み、爪の細部の基準
        if self.d_on["row_smooth"]:
            A0, Y0, _ = MC.Generator.section_y(self, 0.0)
            self._A0t, self._Y0t = A0.copy(), Y0.copy()
            CA0, CY0 = self._claw_part(None)
            self._N0A, self._N0Y = A0 - CA0, Y0 - CY0
            sg = float(self.RD["row_smooth"]["sigma_m"])
            cc = self.K.c
            W = np.exp(-0.5 * ((cc[:, None] - cc[None, :]) / sg) ** 2)
            self._Grs = W / W.sum(1, keepdims=True)
            # 列の割り付けが行の間で違う所（K* の行の方向の細部 |N0 − G·N0| が大きい所。唇・管の rim の跳びなど）は、同じ列の番号を
            # 行の間でならすと別の部分どうしを混ぜることになるので、ならしの強さ λ を下げる（h0 以下で 1、h1 以上で 0、3×3 でならす）。
            # （1 回目の繰り返しで試したが、λ が列ごとに変わる所で断面が折り返したので既定は切り：adaptive_detail_m = null → λ = 1）
            h0, h1 = [float(v) for v in (self.RD["row_smooth"].get("adaptive_detail_m") or [1e9, 2e9])]
            HP = np.hypot(self._N0A - self._Grs @ self._N0A, self._N0Y - self._Grs @ self._N0Y)
            lam = 1.0 - MD.smoothstep((HP - h0) / (h1 - h0))
            # 本体の列（j_B〜j_E）と本体のある行だけ（平らな縁は海の層と谷がのり、列の割り付けは足とシートの端の間の割合なので、行の間で
            # ならすと頂点が縁の上を横へすべり、海の高さと合わなくなる。修正2 の試し：縁も含めた初回は行 239 の列 394 が 13.6 m 横へ動いた）
            cols = np.arange(lam.shape[1])
            lam = lam * ((cols >= self.jB) & (cols <= self.jE))[None, :] * np.asarray(self.has_body, float)[:, None]
            ht = self.RD["row_smooth"].get("row_H_taper_m")
            if ht:
                lam = lam * MD.smoothstep((self.H - float(ht[0])) / (float(ht[1]) - float(ht[0])))[:, None]
            lp = np.pad(lam, 1, mode="edge")
            lam = sum(lp[1 + i:1 + i + lam.shape[0], 1 + j:1 + j + lam.shape[1]] for i in (-1, 0, 1) for j in (-1, 0, 1)) / 9.0
            self._lam = lam
            self._lam_stats = dict(mean=float(lam.mean()), frac_lt_0p5=float((lam < 0.5).mean()), h0=h0, h1=h1)
            self._rs_ready = True
        if self.d_on["no_rebound"]:
            self._no_rebound_setup(no_rebound_cache)

    # ------------------------------------------------------------ K* の目印と行ごとの時刻（num_row_timing_smooth）
    def _rows(self):
        MC.Generator._rows(self)
        if not self.d_on["row_timing"]:
            return
        RT = self.RD["row_timing"]
        eps = float(RT["eps_m"])
        w = float(RT["floor_softness_s"])
        x = self.K.c - self.c_pk
        T = self.tau0 - (np.sqrt(x * x + eps * eps) - eps) / self.vpeel
        # 下限の滑らかな max（softplus）
        T = self.floor + w * np.log1p(np.exp(np.clip((T - self.floor) / w, -60.0, 60.0)))
        self.T_row_hard = self.T_row.copy()
        self.T_row = T
        self.lag = self.tau0 - self.T_row

    # ------------------------------------------------------------ ds_lean_pace・ds_back_hold：表の時計
    def pace_g(self, s):
        s = np.asarray(s, np.float64)
        if not self.d_on["lean_pace"]:
            return s
        s0, dl = self.pace_s0, self.pace_dl
        x = np.clip((s - s0) / (-2.4 - s0), 0.0, 1.0)
        return np.where(s < -2.4, s + dl * (1.0 - s5(x)), s)

    def hold_h(self, s):
        """背の保持の時計：σ ≤ s0 は σ、s0 → s1 で 0 へ（始まりで傾き 1、終わりで傾き 0・二階微分 0 の 5 次）、s1 より後は 0。"""
        s = np.asarray(s, np.float64)
        if not self.d_on["back_hold"]:
            return s
        s0, s1 = self.hold_s0, self.hold_s1
        L = s1 - s0
        u = np.clip((s - s0) / L, 0.0, 1.0)
        # B(u)：B(0) = 0、B'(0) = L/(0 − s0)（σ の傾き 1）、B''(0) = 0、B(1) = 1、B'(1) = 0、B''(1) = 0
        m0 = L / (0.0 - s0)
        h10 = u ** 5 * (-3) + u ** 4 * 8 - u ** 3 * 6 + u        # 5 次 Hermite の基底（一階の端の傾き）
        h01 = u ** 5 * 6 - u ** 4 * 15 + u ** 3 * 10
        B = m0 * h10 + h01
        v = s0 + (0.0 - s0) * B
        return np.where(s <= s0, s, np.where(s >= s1, 0.0, v))

    def _tables28(self):
        MC.Generator._tables28(self)
        LP = self.RD["lean_pace"]
        pace_tabs = set(LP["tables"]) if self.d_on["lean_pace"] else set()
        hold_tabs = set(self.RD["back_hold"]["tables"]) if self.d_on["back_hold"] else set()
        for nm in sorted(pace_tabs | hold_tabs):
            if not hasattr(self, nm):
                continue
            p_ = nm in pace_tabs
            h_ = nm in hold_tabs
            if p_ and h_:
                setattr(self, nm, Remap(getattr(self, nm), lambda s: self.hold_h(self.pace_g(s))))
            elif p_:
                setattr(self, nm, Remap(getattr(self, nm), self.pace_g))
            else:
                setattr(self, nm, Remap(getattr(self, nm), self.hold_h))

    def _shared(self, tau):
        S = MC.Generator._shared(self, tau)
        if self.d_on["lean_pace"] and self.sw["ds_tube_shape"] and self.RD["lean_pace"].get("psi_b", True):
            sg = self.pace_g(S["sig"])
            S["psi_b"] = MD.ease_in((sg - self.psi_b_rng[0]) / (self.psi_b_rng[1] - self.psi_b_rng[0]))
        return S

    def anchor_q(self, r, tau, sig_r, M):
        if self.d_on["lean_pace"] and sig_r < -2.4:
            a0, a1 = self.RD["lean_pace"]["anchor_min_jerk_sigma"]
            x = min(max((sig_r - float(a0)) / (float(a1) - float(a0)), 0.0), 1.0)
            q_on = self.q_on[r]
            return q_on + (self.anc["D_s"] - q_on) * (1.0 - x * x * x * (10.0 - 15.0 * x + 6.0 * x * x))
        return MC.Generator.anchor_q(self, r, tau, sig_r, M)

    # ------------------------------------------------------------ near_trough：K* の谷を時刻の係数で
    def trough_scale(self, tau):
        """s_r(τ) = clip((y_c,r(τ)/y_c,r(0))^p, 0, 1)（(nv,)）。"""
        if not self.d_on["near_trough"]:
            return np.zeros(self.K.nv)
        yc = self.crest(float(tau))[1]
        if not hasattr(self, "_yc0"):
            self._yc0 = np.maximum(self.crest(0.0)[1], 1e-6)
        p = float(self.RD["near_trough"]["exponent"])
        return np.clip(np.maximum(yc, 0.0) / self._yc0, 0.0, 1.0) ** p

    def sections(self, tau, diag=False, rows=None, water=True):
        out = MC.Generator.sections(self, tau, diag=diag, rows=rows, water=water)
        if not self.d_on["near_trough"]:
            return out
        A, Y = out[0], out[1]
        s = self.trough_scale(tau)
        T = self.K.T_trough
        if rows is None:
            Y += s[:, None] * T
        else:
            rr = np.array([int(r) for r in rows], int)
            Y[rr] += s[rr, None] * T[rr]
        return out

    # ------------------------------------------------------------ num_row_smooth と num_no_rebound_after_apex
    def _claw_part(self, tau):
        """爪の細部（ds_claws_follow_lip の δn を運びの進みで掛けたもの）の断面の成分 (CA, CY)。t* では δn そのもの。"""
        CA = np.zeros((self.K.nv, self.K.nu))
        CY = np.zeros((self.K.nv, self.K.nu))
        if not getattr(self, "claws_follow", False):
            return CA, CY
        for r in self.lip_carry_rows:
            L = self.lip[r]
            if "dn" not in L:
                continue
            P = 1.0 if tau is None else min(max(float(self.claw_progress(r, tau)[0]), 0.0), 1.0)
            cols = L["cols"]
            CA[r, cols] = P * L["dn"][:, 0]
            CY[r, cols] = P * L["dn"][:, 1]
        return CA, CY

    def detail_weight(self, tau):
        """ω(τ)：t* の行ごとの細部（K* の行の間の違い）を戻す重み。τ_a まで 0、t* で 1（smootherstep）。"""
        ta = -float(self.RD["row_smooth"]["detail_return_s"])
        return float(s5((float(tau) - ta) / (0.0 - ta)))

    def _row_smooth(self, tau, A, Y):
        """爪を除いた部分 N を行の方向にならす：N′ = ω·N0 + G·(N − ω·N0)（N0 は t* の爪を除いた部分）。早い時刻（ω = 0）は N そのものを
        ならし、t* に近づくと K* の行ごとの細部（N0 − G·N0）を ω の分だけ戻す。t* は N = N0、ω = 1 で K* のまま。
        修正1（開発の試し）：t* からの変位だけをならす形（ω = 1 のまま）では、早い時刻に K* の管の天井の行ごとの違いが変位の側に乗って、
        前面に 9 cm のこぶができた（τ −8、行 159、列 306〜309。前面の角 Θ が最初から 81°）。"""
        CA, CY = self._claw_part(tau)
        w = self.detail_weight(tau)
        G = self._Grs
        NA, NY = A - CA, Y - CY
        MA, MY = NA - w * self._N0A, NY - w * self._N0Y
        lam = self._lam
        return CA + NA - lam * (MA - G @ MA), CY + NY - lam * (MY - G @ MY)

    def section_y(self, tau, diag=False):
        A, Y, d = MC.Generator.section_y(self, tau, diag=diag)
        if self._rs_ready and float(tau) < 0.0:
            A, Y = self._row_smooth(float(tau), A, Y)
        if self._nr_ready:
            Y = Y + self._nr_delta(float(tau))
        return A, Y, d

    def _nr_region(self):
        rows = sorted(int(r) for r in self.lip)
        j0 = int(min(self.root[rows])) + 1
        j1 = int(max(self.ja[rows])) - 1
        return rows, j0, j1

    def _no_rebound_setup(self, cache=None):
        NR = self.RD["no_rebound"]
        hz = float(NR["grid_hz"])
        t0 = float(NR["tau_start"])
        n = int(round(-t0 * hz))
        taus = np.round(-np.arange(n, -1, -1) / hz, 9)
        rows, j0, j1 = self._nr_region()
        rr = np.array(rows, int)
        if cache and os.path.isfile(cache):
            z = np.load(cache)
            Yg = z["Y"].astype(np.float64)
            assert Yg.shape == (len(taus), len(rows), j1 - j0 + 1)
        else:
            Yg = np.zeros((len(taus), len(rows), j1 - j0 + 1))
            for k, tau in enumerate(taus):
                A, Y, _ = self.section_y(float(tau))
                Yg[k] = Y[rr, j0:j1 + 1]
            if cache:
                np.savez(cache, Y=Yg.astype(np.float64), taus=taus)
        V = Yg.reshape(len(taus), -1)
        pre = int(round(float(NR["pre_apex_s"]) * hz))
        sg = float(NR["slope_smooth_s"]) * hz
        D = np.zeros_like(V)
        nfix = 0
        worst = 0.0
        for v in range(V.shape[1]):
            y = V[:, v]
            ka = int(np.argmax(y))
            y1 = y.copy()
            changed = False
            # 頂点の前：くぼみ（下がって戻る）を埋める（上へ単調。始まりと頂点の高さは同じ、傾きは σ でならして非負のまま和をそろえる）。
            # 頂点の後だけを直すと、頂点が噴流の始まりにある点（直す）と後ろにある隣の点（直さない）の間で δ が列ごとに 12 cm 跳んだ
            if ka > 2:
                rm = np.maximum.accumulate(y[:ka + 1])
                if np.any(rm - y[:ka + 1] > 1e-9):
                    s = gauss_nearest(np.diff(rm), sg)
                    s = np.maximum(s, 0.0)
                    if s.sum() > 0:
                        s *= (rm[-1] - rm[0]) / s.sum()
                    y1[:ka + 1] = np.concatenate([[rm[0]], rm[0] + np.cumsum(s)])
                    changed = True
            # 頂点の後：傾きを単調に減る列へ（上へ加速しない）
            if ka < len(y) - 3:
                k0 = max(ka - pre, 0)
                s = np.diff(y1[k0:])
                if not np.all(np.diff(s) <= 1e-9):
                    sh = antitonic(s)
                    sh = gauss_nearest(sh, sg)
                    sh = sh + (s.sum() - sh.sum()) / len(sh)
                    y1[k0:] = np.concatenate([[y1[k0]], y1[k0] + np.cumsum(sh)])
                    changed = True
            if not changed:
                continue
            D[:, v] = y1 - y
            nfix += 1
            worst = max(worst, float(np.abs(D[:, v]).max()))
        D[-1] = 0.0
        self._nr_taus = taus
        self._nr_hz = hz
        self._nr_rows = rr
        self._nr_j = (j0, j1)
        self._nr_D = D.reshape(len(taus), len(rows), j1 - j0 + 1)
        self._nr_stats = dict(vertices=int(V.shape[1]), corrected=int(nfix), max_abs_delta_m=worst, grid_hz=hz, tau_start=t0,
                              rows=[int(rows[0]), int(rows[-1])], cols=[j0, j1])
        self._nr_ready = True

    def _nr_delta(self, tau):
        out = np.zeros((self.K.nv, self.K.nu))
        taus = self._nr_taus
        if tau <= taus[0] or tau >= 0.0:
            return out
        u = (tau - taus[0]) * self._nr_hz
        k = int(min(max(math.floor(u), 0), len(taus) - 2))
        s = u - k
        D = self._nr_D
        p0 = D[max(k - 1, 0)]
        p1 = D[k]
        p2 = D[k + 1]
        p3 = D[min(k + 2, len(taus) - 1)]
        v = 0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3)
        j0, j1 = self._nr_j
        out[self._nr_rows, j0:j1 + 1] = v
        return out

    # ------------------------------------------------------------ 記録
    def summary(self):
        s = MC.Generator.summary(self)
        s.update(number="設計28修正01 試行D", ds28r01d=dict(on=self.d_on, off=list(self.d_off), params_sha256=self.d_sha, base_sha256=self.d_base_shas,
                                                         kstar_dir=self.K.src["dir"], kstar_sha256=self.K.sha, landmarks=self.K.landmarks,
                                                         landmarks_source=self.K.src["landmarks_source"],
                                                         trough_min_m=float(self.K.T_trough.min()),
                                                         T_row_range=[float(self.T_row.min()), float(self.T_row.max())],
                                                         no_rebound=getattr(self, "_nr_stats", None), row_smooth_lambda=getattr(self, "_lam_stats", None)))
        return s
