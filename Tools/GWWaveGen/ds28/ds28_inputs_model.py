# -*- coding: utf-8 -*-
"""設計28：入力条件の変更と較正の掃引のための生成器（設計27 の生成器 ds27_model.Generator を読むだけで継承する）。

README
======
設計27 の生成器（Tools/GWWaveGen/ds27/ds27_model.py、コミット c2b6839）は変えない。ここでは継承して、次の値を外から与えられる
ようにしただけである（既定の値では設計27 の art_on・art_off と頂点まで同じ。ds28_inputs_run.py の selftest で確かめる）：

  物理の入力（設計26 §1.3 の「物理の入力」。設計28 の「入力条件の変更」）
    dtheta_deg  交差角 Δθ（0／60／120°）。搬送波・背景のうねり・切った版の背面（交差波群の断面）・峰の模様の速さに効く。
    lam_p       代表の波長 λp（195／250 m）。同じところに効く。
    c0 は入力から決める：c0 = 20.0 m/s ×（c(λp)/c(195 m)）×（cos30°/cos(Δθ/2)）。既定（60°・195 m）で設計27 と同じ 20.0 m/s。
    jet_cos2    切った版の唇の打ち出しの水平の速さ（設計26 E4c の中央値 u/c0、60° で較正）を、峰の水の速さと模様の速さの比
                cos²(Δθ/2) に比例させる（設計26 §1.1 の自前の導出。60° で 1 倍、0° で 4/3 倍、120° で 1/3 倍）。
  物理の頂の高さ（設計27 の引き継ぎの 4。切った版が K* の行ごとの頂の高さ＝塔を受け継がないようにする）
    crest="phys"  行ごとの t* の頂の高さを、搬送波の分散集中（NewWave、±Δθ/2 の 2 系）の波峰線に沿った包絡 E(c) と、狭帯域の
                  2 次の急峻化 H = A_L·E + ½·k̄·(A_L·E)²（設計26 E2 と同じ式）から決める。焦点（c = 0、主断面）で H* = 20.80 m
                  （K* の大きさは美術の選択として変えない。設計26 §1.3）。K* の頂が 3 m 以上の行だけに当てる（それより低い行と
                  本体のない行は、シートに本体の手本がないので K* のまま。限界として記録）。K* の断面は行ごとに縦だけ
                  s_r = H_phys/H_K* 倍した「縦に伸ばした K*」を手本にし、唇・rim・錨の列は元の K* のものを使う。
    growth="phys" t* までの頂の高さの育ち方も、焦点へ集まる主役の峰（模様の速さで進む峰）の線形の高さの時系列から決める
                  （既定 "table" は設計27 の較正の表）。噴流の始まりから t* までは頂の上昇を割線（一定の速さ）にする。
  較正（設計26 §1.3 の「較正」。設計28 の「較正の掃引」）
    onset_s       噴流の始まり（峰の行、t* の何秒前か。2.0／2.4／2.8）。段階の表（σ）は、始まりの前を始まりに合わせて平行に
                  ずらし、始まりから t* までを縮め・伸ばす（σ' = σ + (τ0 − 2.4)、始まりの後は σ' = σ·2.4/τ0）。
    peel          波峰線に沿った砕波の広がり（20／30 m/s）。
    c0            峰の模様の速さを直接与える（16 m/s の見え方）。
    decel_lead_s  減速を噴流の始まりより前から始める（既定 0。1.8 s で峰の行は段階 a（τ −4.2 s）から 0.8 c0 へ減速）。
    beta          t* の峰の速さ / c0（0.8）。
  錨（設計28 のレビュー対応で足した）
    anchor_to_kstar  True（既定、設計27 と同じ）：設計27 の内壁の錨の ease-in（anchor.to_kstar_sigma。τ −2.0 s から t* の K* の錨の
                  位置 q* = (a*_ja − a*_頂)/H へ寄せる）を掛ける。設計27 ではこれが切り替えの外にあり、切った版にも掛かっていた。
                  False：ease-in を掛けない（錨は設計27 の表の D(σ) のまま。切った版では頂の真下の 0.02H で止まる）。
                  「物理だけ」（ds28_inputs_run.PHYS）は False。K* を目標にした動きが t* の差を K* へ寄せないように。

使い方：
    from ds28_inputs_model import InputGen
    g = InputGen(dict(base="art_off", crest="phys", dtheta_deg=120.0))
    A, Y = g.sections(-2.0)       # 波の枠の局所の断面（海の前）
    X = g.world(0.0)              # t* のワールド（海を含む）
numpy だけ。K* と設計26 の値の JSON は設計27 の生成器と同じく SHA-256 を照合して読む。利用者の Houdini 解算のファイルは読まない。
"""
import copy
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, DS27)
import ds27_model as M27  # noqa: E402
from ds27_model import G, Generator, KStar, angle_dir, integ_S, jonswap, load_json, sha256_file, smoothstep  # noqa: E402

# 設計27 のコミット c2b6839 の中身（読むだけ。別の担当が生成器を変えても、ここで気づく）
FROZEN27 = {
    "ds27_model.py": "916e8f4201e013a455666998c6819d4aa1292d67ed9e8ca653bda17acdb0826a",
    "ds27_params.json": "03e3b6346a58517511e1c6ad1afaee0217147d0f18a1c1cb4fe7ff81df5b47c4",
    "ds27_gates.py": "4cc4031542f0411b5ea33178a71b0373497ddaeb3295789a8eea5b77127d6f46",
}


def check_frozen():
    out = {}
    for fn, want in FROZEN27.items():
        got = sha256_file(os.path.join(DS27, fn))
        if got != want:
            raise SystemExit("[ds28_inputs] 設計27 のファイルがコミット c2b6839 と違います：%s" % fn)
        out[fn] = got
    return out


DEFAULT_CFG = dict(
    base="art_off",          # 切り替えの既定（art_on：9 つを入れる、art_off：9 つを切る）
    switches=None,           # {名前: bool} で個別に上書き
    dtheta_deg=60.0,
    lam_p=195.0,
    c0=None,                 # None：入力から決める
    onset_s=2.4,
    peel=20.0,
    beta=0.8,
    decel_lead_s=0.0,
    crest="kstar",           # "kstar"（設計27 と同じ）／"phys"
    growth="table",          # "table"（設計27 の較正の表）／"phys"
    jet_cos2=False,
    crest_min_H_m=3.0,       # crest="phys" を当てる K* の頂の高さの下限
    anchor_to_kstar=True,    # 設計27 の錨の ease-in（τ −2.0 s から t* の K* の錨へ）。False で掛けない（設計28 のレビュー対応）
)

C_PHASE_195 = math.sqrt(G * 195.0 / (2 * math.pi))


def c_phase(lam):
    return math.sqrt(G * lam / (2 * math.pi))


def c0_from_inputs(dtheta_deg, lam_p):
    """峰の模様の速さ（t 方向）。設計27 は 60°・195 m で 20.0 m/s（17.4/cos30° ≈ 20.1 を丸めた値）なので、その比で換算する。"""
    return 20.0 * (c_phase(lam_p) / C_PHASE_195) * (math.cos(math.radians(30.0)) / math.cos(math.radians(0.5 * dtheta_deg)))


class CarrierCrest:
    """搬送波の分散集中の、主役の峰の高さ（線形＋狭帯域の 2 次）。成分は設計27 の搬送波と同じ（JONSWAP γ 3.3、f 0.5〜2.5 fp、
    64 成分、NewWave の重み S(f)Δf、±Δθ/2 の対称・同振幅・一方向の 2 系、焦点 = 断面の原点 c = 0・a = 0・τ = 0）。
    2 系の和は η(x, c, τ) = Σ a_f·cos(k_f sin(Δθ/2)·c)·cos(k_f cos(Δθ/2)·x − ω_f τ)（x は断面の a と同じ向きの地面の座標）。"""

    def __init__(self, dtheta_deg, lam_p, gamma=3.3, H_ref=20.80, n=64):
        fp = math.sqrt(G / (2 * math.pi * lam_p))
        fq = np.linspace(0.5 * fp, 2.5 * fp, n)
        S = jonswap(fq, fp, gamma)
        self.amp = S / S.sum()
        self.k = (2 * math.pi * fq) ** 2 / G
        self.om = 2 * math.pi * fq
        h = math.radians(0.5 * dtheta_deg)
        self.ks = self.k * math.sin(h)
        self.kx = self.k * math.cos(h)
        self.kbar = float((self.amp * self.k).sum())
        self.H_ref = float(H_ref)
        # 焦点（線形の単位の高さ 1）で H_ref になる線形の振幅 A_L（設計26 E2 と同じ：A_L + ½ k̄ A_L² = H）
        self.AL = (-1.0 + math.sqrt(1.0 + 2.0 * self.kbar * self.H_ref)) / self.kbar
        self.c_pat = float(self.om[np.argmax(self.amp)] / self.kx[np.argmax(self.amp)])   # 模様の速さ（ピーク成分）
        self.lam_x = lam_p / math.cos(h)

    def height(self, zeta):
        z = np.maximum(zeta, 0.0)
        return self.AL * z + 0.5 * self.kbar * (self.AL * z) ** 2

    def envelope_c(self, c):
        """t* の波峰線に沿った線形の包絡 E(c)（焦点で 1）。"""
        c = np.asarray(c, np.float64)
        return np.cos(np.outer(c, self.ks)) @ self.amp

    def hero_zeta(self, c, taus, x_speed):
        """主役の峰（τ = 0 に焦点で最大になる峰、地面の x ≈ x_speed·τ）の線形の高さ ζ(c, τ)（(nc, nt)）。
        その近く（±0.3 波長）の最大を取る。"""
        c = np.asarray(c, np.float64)
        W = np.cos(np.outer(c, self.ks)) * self.amp[None, :]          # (nc, nf)
        out = np.zeros((len(c), len(taus)))
        half = 0.3 * self.lam_x
        xs0 = np.linspace(-half, half, 481)
        for i, tau in enumerate(taus):
            x = x_speed * tau + xs0
            Mx = np.cos(np.outer(self.kx, x) - (self.om * tau)[:, None])   # (nf, nx)
            out[:, i] = (W @ Mx).max(1)
        return out


def scaled_kstar(K, s):
    """K* の断面を行ごとに縦だけ s_r 倍したもの（a はそのまま）。列の意味と行の位置は同じ。"""
    Ks = copy.copy(K)
    Ks.Y = K.Y * np.asarray(s, np.float64)[:, None]
    Ks.X = Ks.world_from_section(Ks.A, Ks.Y)
    return Ks


class InputGen(Generator):
    """設計27 の Generator に、設計28 の入力・較正・物理の頂の高さを外から与える。"""

    def __init__(self, cfg=None, log=None):
        cfg = dict(DEFAULT_CFG, **(cfg or {}))
        self.cfg = cfg
        version = cfg["base"]
        if version not in ("art_on", "art_off"):
            raise ValueError("base は art_on か art_off")
        # ---- 以下は ds27_model.Generator.__init__ と同じ手順（値の出どころだけを cfg に替えた）
        self.version = version
        self.log = log or (lambda *a: None)
        self.params_path = M27.PARAMS_JSON
        self.P = load_json(self.params_path)
        P = self.P
        cpath = os.path.join(M27.REPO, P["inputs"]["conditions"])
        self.cond_sha = sha256_file(cpath)
        if self.cond_sha != P["inputs"]["conditions_sha256"]:
            raise SystemExit("[ds28_inputs] ds26_conditions.json の SHA-256 が記録と違います")
        self.C = load_json(cpath)
        self.params_sha = sha256_file(self.params_path)
        on = bool(P["switches"]["versions"][version])
        self.sw = {k: on for k in P["switches"]["names"]}
        if cfg["switches"]:
            for k, v in cfg["switches"].items():
                if k not in self.sw:
                    raise ValueError("切り替えの名前が違います：%s" % k)
                self.sw[k] = bool(v)
        self.K_true = KStar(P)
        self.K = self.K_true
        C = self.C
        cal, phys = C["calibration"], C["physical_input"]
        self.lam_p = float(cfg["lam_p"])
        self.half_angle = 0.5 * float(cfg["dtheta_deg"])
        self.c0_input = c0_from_inputs(float(cfg["dtheta_deg"]), self.lam_p)
        self.c0 = float(cfg["c0"]) if cfg["c0"] is not None else self.c0_input
        self.tau0 = float(cfg["onset_s"])
        self.c_pk_on = float(cal["jet_onset_peak_row_tau_s"]["row_c_m"])
        self.floor = float(cal["jet_onset_floor_s"]["value"])
        self.vpeel = float(cfg["peel"])
        self.p_rel = float(cal["release_exponent_p"]["value"])
        self.beta = float(cfg["beta"])
        self.vH = float(cal["crest_rise_after_onset_mps"]["value"])
        self.gamma_j = float(phys["spectrum"]["gamma"])
        self.Hs = float(phys["background_swell_Hs_m"]["value"])
        self.lead = float(cfg["decel_lead_s"])
        num = C["numerical"]
        self.strip_delta = float(P["lip"]["strip_spacing_m"])
        self.th1f = float(num["prerelease_rule"]["upper_strip_angle_deg"])
        self.th2f = float(num["prerelease_rule"]["underside_strip_angle_deg"])
        ov_ = self.P["front"].get("strip_angle_override_deg")
        if ov_:
            self.th1f = float(ov_.get("upper", self.th1f))
            self.th2f = float(ov_.get("under", self.th2f))
        self.Tr_max = float(P["lip"]["release_ramp_max_s"])
        self.tau_min = float(P["range"]["tau_min_s"])
        self.jet_fac = (math.cos(math.radians(self.half_angle)) ** 2 / math.cos(math.radians(30.0)) ** 2) if cfg["jet_cos2"] else 1.0
        self.carrier_crest = CarrierCrest(float(cfg["dtheta_deg"]), self.lam_p, self.gamma_j, H_ref=float(self.K_true.Y[self.K_true.main_row].max()))
        self._tables()
        self._rows()
        self._clock_setup()
        self._lip_setup()
        self._seam_setup()
        self._xs_setup()
        self._sea_setup()

    # ------------------------------------------------------------ 行ごとの値（物理の頂の高さ）
    def _rows(self):
        cfg = self.cfg
        if cfg["crest"] == "phys":
            # 1) 列の意味（唇先・rim・巻きの行など）は元の K* から
            self.K = self.K_true
            Generator._rows(self)
            keep = dict(tip=self.tip.copy(), rim=self.rim.copy(), e4_curled=self.e4_curled.copy(), overhang=self.overhang.copy(),
                        root=self.root.copy(), ja=self.ja.copy())
            # 2) 行ごとの t* の頂の高さを物理から：K* の頂が crest_min_H_m 以上の行だけ
            Hk = self.K_true.Y.max(1)
            Hp = self.carrier_crest.height(self.carrier_crest.envelope_c(self.K_true.c))
            self.phys_mask = Hk >= float(cfg["crest_min_H_m"])
            s = np.where(self.phys_mask, Hp / np.maximum(Hk, 1e-9), 1.0)
            self.phys_scale = s
            self.phys_H_target = np.where(self.phys_mask, Hp, Hk)
            self.K = scaled_kstar(self.K_true, s)
            Generator._rows(self)
            assert np.array_equal(self.root, keep["root"]) and np.array_equal(self.ja, keep["ja"]), "縦に伸ばしても頂・錨の列は同じはず"
            self.tip, self.rim, self.e4_curled, self.overhang = keep["tip"], keep["rim"], keep["e4_curled"], keep["overhang"]
        else:
            self.phys_mask = np.zeros(self.K_true.nv, bool)
            self.phys_scale = np.ones(self.K_true.nv)
            Generator._rows(self)
        self._fix_Trow()
        if cfg["growth"] == "phys":
            self._phys_growth()

    def _fix_Trow(self):
        """噴流の始まり T_row を cfg の τ0・広がりで。切った版の Froude の抑え（設計27 は主断面の 2.2075 s·√(H/20.8)）は、
        K* の頂なら (τ0 − |c_pk_on|/広がり)·√(H/20.8)（既定で設計27 と同じ値）、物理の頂なら峰（焦点の行）の τ0·√(H/H_峰)。"""
        c = self.K.c
        H = self.H
        if self.cfg["crest"] == "phys" and not (self.version == "art_on" or self.sw["ds_farwall_hold"]):
            # 物理の頂の峰は焦点の行（c = 0）。Δθ 0° では頂が波峰線に沿って一様で argmax が定まらない（初回の実行で c −21.4 m を拾った）
            self.c_pk = 0.0
        T = np.maximum(self.tau0 - np.abs(c - self.c_pk) / self.vpeel, self.floor)
        if not self.sw["ds_lip_target_kstar"]:
            if self.cfg["crest"] == "phys":
                cap = self.tau0 * np.sqrt(np.maximum(H, 0.0) / max(float(H.max()), 1e-9))
            else:
                cap = (self.tau0 - abs(self.c_pk_on) / self.vpeel) * np.sqrt(np.maximum(H, 0.0) / 20.8)
            T = np.maximum(np.minimum(T, cap), self.floor)
        self.T_row = T
        self.lag = self.tau0 - self.T_row

    def _phys_growth(self):
        """主役の峰の物理の育ち方（模様の速さで進む峰の線形の高さ → 2 次）を行ごとに表にする（τ −12〜0 s、0.02 s おき）。"""
        cc = self.carrier_crest
        self.gr_tau = np.linspace(self.tau_min, 0.0, int(round(-self.tau_min / 0.02)) + 1)
        z = cc.hero_zeta(self.K.c, self.gr_tau, self.c0_input)
        Hg = cc.height(z)                               # (nv, nt)
        Hg = Hg / np.maximum(Hg[:, -1:], 1e-9)          # t* で 1
        self.gr_H = Hg
        # 噴流の始まりから t* までは割線（設計27 の post と同じ形 y_root − vH·T）。始まりで物理の高さにつなぐ
        on = np.array([np.interp(-self.T_row[r], self.gr_tau, Hg[r]) for r in range(self.K.nv)])
        vH_phys = self.y_root * (1.0 - on) / np.maximum(self.T_row, 1e-9)
        self.vH_r = np.where(self.phys_mask, np.maximum(vH_phys, 0.0), self.vH_r)
        self.gr_onset_ratio = on

    # ------------------------------------------------------------ 錨（設計28 のレビュー対応：K* への ease-in を切れるようにする）
    def sections(self, tau, diag=False):
        if self.cfg["anchor_to_kstar"]:
            return Generator.sections(self, tau, diag)
        # 設計27 の sections は錨を a_ja = a_c + H·[D_r(1 − E) + q*·E]（E は τ −2.0 s から t* への ease-in、q* は K* の錨の位置）に置く。
        # 設計27 のファイルを変えずに E の項を消すため、この呼び出しの間だけ K* の錨の a を「その τ の D_r の位置」に置き換える
        # （q* = D_r になり a_ja = a_c + H·D_r）。K_ja の a は sections の中で q* にだけ使う（ds27_model.py の 798 行）。
        _a_c, _y_c, sig, _sh = self.crest(tau)
        an = self.anc
        Dtab = an["D_s"] - (an["D_s"] - an["D_e"]) * smoothstep((sig - an["s0"]) / (an["s1"] - an["s0"]))
        Dr = Dtab if self.sw["ds_tube_shape"] else 0.02 + 0.03 * np.log1p(np.exp((Dtab - 0.02) / 0.03))
        keep = self.K_ja
        Kj = keep.copy()
        Kj[:, 0] = self.a_root + self.H * Dr
        self.K_ja = Kj
        try:
            return Generator.sections(self, tau, diag)
        finally:
            self.K_ja = keep

    # ------------------------------------------------------------ 時計（噴流の始まりの掃引）
    def sigma(self, tau):
        s = Generator.sigma(self, tau)
        if abs(self.tau0 - 2.4) < 1e-12:
            return s
        return np.where(s <= -self.tau0, s + (self.tau0 - 2.4), s * 2.4 / self.tau0)

    def D(self, T, T_row):
        """減速を噴流の始まりより lead 秒前から始める（lead = 0 で設計27 と同じ）。"""
        return Generator.D(self, T, np.asarray(T_row, np.float64) + self.lead)

    def crest(self, tau):
        a_c, y_c, sig, shear = Generator.crest(self, tau)
        if self.cfg["growth"] == "phys":
            T = -tau
            pre = self.y_root * np.array([np.interp(tau, self.gr_tau, self.gr_H[r]) for r in range(self.K.nv)])
            post = self.y_root - self.vH_r * T
            yp = np.where(tau >= -self.T_row, post, pre)
            y_c = np.where(self.phys_mask, yp, y_c)
        return a_c, y_c, sig, shear

    # ------------------------------------------------------------ 唇（ds27_model.Generator._lip_setup の写し。変えたのは 3 か所）
    def _lip_setup(self):
        K = self.K
        A, Y = K.A, K.Y
        target = self.sw["ds_lip_target_kstar"]
        claws_on = self.sw["ds_claws"]
        prof = self.P["lip"]["median_launch_profile"]
        pu = np.array(prof["upper"], np.float64)
        d1 = angle_dir(self.th1f)
        d2 = angle_dir(self.th2f)
        lp = self.P["lip"]
        self.lip = {}
        for r in self.lip_rows:
            root, tip, rim = int(self.root[r]), int(self.tip[r]), int(self.rim[r])
            cols = np.arange(root + 1, rim + 1)
            upm = cols <= tip
            sa = self.sarc[r]
            S_up = max(sa[tip] - sa[root], 1e-6)
            s_up = (sa[tip] - sa[cols[upm]]) / S_up
            s_un = np.minimum((sa[cols[~upm]] - sa[tip]) / max(S_up, sa[rim] - sa[tip]), 1.0)
            s = np.concatenate([s_up, s_un])
            if not target:
                nu_ = max(tip - root, 1)
                s = np.concatenate([(tip - cols[upm]) / nu_, np.minimum((cols[~upm] - tip) / nu_, 1.0)]).astype(np.float64)
            T_row = float(self.T_row[r])
            T_dec = T_row + self.lead                     # [設計28] 減速の始まり（lead = 0 で T_row）
            Ti = T_row * np.clip(1 - s, 0, 1) ** self.p_rel
            if not target:
                Ti = np.where(upm, Ti, T_row)
            Tc = np.maximum(Ti, float(lp["Tc_min_s"]))
            dl = self.strip_delta * float(np.clip(self.H[r] / lp["strip_spacing_scale_H_m"], lp["strip_spacing_min_factor"], 1.0))
            k_up = (cols - root).astype(np.float64)
            k_un = (cols - tip).astype(np.float64)
            n_up = float(tip - root)
            off = np.where(upm[:, None], k_up[:, None] * dl * d1[None, :], n_up * dl * d1[None, :] + k_un[:, None] * dl * d2[None, :])
            Kt = np.stack([A[r, cols], Y[r, cols]], 1)
            if target and not claws_on:
                g_ = np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2)
                g_ /= g_.sum()
                sm = np.stack([np.convolve(np.pad(Kt[:, i], 6, mode="edge"), g_, mode="valid") for i in range(2)], 1)
                wgt = smoothstep(np.minimum(np.arange(len(cols)), np.arange(len(cols))[::-1]) / 6.0)[:, None]
                Kt = Kt + wgt * (sm - Kt)
            Tr = np.minimum(self.Tr_max, Tc / 2)
            ci = self.beta * self.c0 + (1 - self.beta) * self.c0 * np.minimum(Tc / T_dec, 1.0)   # [設計28] T_row → T_dec
            kdec = (1 - self.beta) * self.c0 / T_dec                                            # [設計28] T_row → T_dec
            vH = float(self.vH_r[r])
            Pg = np.stack([self.a_root[r] - self.D(Tc, T_row), self.y_root[r] - vH * Tc], 1) + off
            IS, ISg = integ_S(Tc, Tr)
            bx = ci * (Tc - IS) - kdec * (Tc ** 2 / 2 - ISg)
            by = vH * (Tc - IS)
            if target:
                u2 = (Kt[:, 0] - Pg[:, 0] - bx) / IS
                w2 = (Kt[:, 1] - Pg[:, 1] - by + G * ISg) / IS
            else:
                u_t = float(np.interp(0.0, pu[:, 0], pu[:, 1]))
                w_t = float(np.interp(0.0, pu[:, 0], pu[:, 2]))
                u_m = np.where(upm, np.interp(s, pu[:, 0], pu[:, 1]), u_t * (1.0 - 0.05 * s)) * self.c0 * self.jet_fac   # [設計28] jet_fac
                w_m = np.where(upm, np.interp(s, pu[:, 0], pu[:, 2]), w_t * (1.0 - 0.2 * s)) * math.sqrt(G * self.H[r])
                bl = smoothstep(Ti / 0.6)
                u2 = ci + (u_m - ci) * bl
                w2 = vH + (w_m - vH) * bl
            ub = (Kt[:, 0] - Pg[:, 0]) / Tc
            wb = (Kt[:, 1] - Pg[:, 1] + 0.5 * G * Tc ** 2) / Tc
            ev = Ti >= 0.15
            okp = (ub / self.c0 >= 0.6) & (ub / self.c0 <= 1.3) & (wb / math.sqrt(G * self.H[r]) >= -0.2) & (wb / math.sqrt(G * self.H[r]) <= 0.8)
            self.lip[int(r)] = dict(vH=vH, cols=cols, upm=upm, s=s, Ti=Ti, Tc=Tc, Tr=Tr, ci=ci, kdec=kdec, Pg=Pg, u2=u2, w2=w2,
                                    dl=dl, k_up=k_up, k_un=k_un, n_up=n_up, T_row=T_row, root=root, tip=tip, rim=rim,
                                    n_eval=int(ev.sum()), n_ok=int((ev & okp).sum()), Kt=Kt, ub=ub, wb=wb, ev=ev, okp=okp)

    def cfg_record(self):
        c = dict(self.cfg)
        c.update(c0_used_mps=round(self.c0, 4), c0_from_inputs_mps=round(self.c0_input, 4), jet_fac=round(self.jet_fac, 4),
                 c_pk_m=round(float(self.c_pk), 3), T_row_range_s=[round(float(self.T_row.min()), 3), round(float(self.T_row.max()), 3)],
                 carrier_AL_m=round(self.carrier_crest.AL, 3), carrier_kbar=round(self.carrier_crest.kbar, 5),
                 switches_on=[k for k, v in self.sw.items() if v])
        return c
