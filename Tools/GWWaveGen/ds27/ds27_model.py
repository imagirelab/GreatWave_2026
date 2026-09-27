# -*- coding: utf-8 -*-
"""設計27：単発砕波の生成器（方式 H の層 1〜7。形成から t* まで、崩壊は作らない（Q11））。

README
======
この模块は、設計26 の記録（Docs/Progress/Design_26_ja.md）の §2 の層 1〜7 を numpy の解析式で実装する。
τ（物理の時刻、t* = 0）を与えると、K* と同じ固定トポロジーの格子（240 行 × 400 列 = 96,000 頂点）の
**波の枠の局所座標**（ワールド − O(τ)。O は波の枠の原点で平行移動だけ、軸はワールドの軸）を返す。
パッケージへの書き出し・節点の選び方・検査は ds27_generate.py、パッケージの読み込みと Hermite の再生は ds27_package.py。

層（Design_26_ja.md §2 の表。値はすべて ds27_params.json と ds26_conditions.json）：
  1 海     ：±30° の 2 系の分散集中の搬送波（JONSWAP γ 3.3、λp 195 m、成分の振幅は NewWave の S(f)Δf、焦点 = K* の頂の下の
             海面・τ = 0）と、同じスペクトルのランダムな位相の背景のうねり（Hs 5 m、種で決定的）。行ごと・時刻ごとの搬送波の
             振幅 A_c,r(τ) は、頂を中心に 225 m の窓の符号付きの断面積が 0 になるように一次式で解く（本体が搬送波の山を
             置き換え、外の谷が埋め合わせる。P2・P3）。本体の列は搬送波を持たず、シートの外端の帯（後ろ 15 m・前 10 m）で
             解析式の海へ戻る。うねりは全頂点に縦に足す。ds_swell_calm・ds_sea_calm_painting（入れた版）で t* に 0。
  2 平行移動：波の枠は峰の行（c = +3.85 m）の頂に合わせて c0 = 20 m/s、噴流の始まり（τ −2.4 s）から t* まで 0.8 c0 へ線形に
             減速（O(τ) = O_K − X(τ)·t̂）。行ごとの減速の差（最大 2.4 m のせん断）は局所座標に入る。
  3 本体   ：美術優先30 の仕組み（頂の高さ、背面を頂を中心に横 Lb 倍、前面の回転角補間と閉合、前の足の倍率 F）を、行ごとの
             段階の時計 σ_r(τ)（噴流の始まりで σ = −2.4、t* で 0、dσ/dτ ≥ 1、t* で傾き ≠ 0）で動かす。頂の高さは上昇の速さの
             折れ線の積分（頂の加速度 < 2g）。前面は、頂 →（唇の帯）→ 管の天井 → 内壁の錨 X_ja（0.3H）→ 内壁と谷 → 前の足。
             錨の横の位置は段階 a の寝た前面（0.62H 前）から段階 c のほぼ鉛直の壁（頂の少し後ろ）へ 3.5 s の smoothstep で
             戻り、t* へ K* の位置に寄せる。表の終点は K*（t* で一致）。段階 a→b→c→d の自前の見積もりは各 ±0.3 s の内。
  4 唇     ：前縁の帯（頂から列の順に 2 cm おき、上面 40°・下面 80°。噴流の始まりの前は寝た角から立ち上がる）＋ 放出の補間
             min(0.6 s, T_i/2) ＋ 重力だけの弾道。入れた版は t* に K* へ着くように行ごとに一次式で解く（設計26 e4_common.py の
             ramp_solve と同じ式）。切った版は設計26 E4c の打ち出しの速さの中央値から前へ積分する。管の天井（rim〜錨）は
             3 次 Hermite と K* の管の相似変換の混ぜ合わせ（噴流の始まりで 0 → t* で 1）。唇の境の列は行の間でならす。
  5 美術の誘導：9 つの名前の付いた値（ds_*）。art_on = すべて入れる、art_off = すべて切る（P14）。
  6 白     ：T_white（τ の秒）を物理の時刻で作り直す（最初の白は峰の行の唇先 τ −2.3 s、放出の順と 20 m/s の広がり、背面は
             −0.3 s までに、管の中は ds_tube_white_early で τ −1.0〜−0.2 s）。崩壊の場は作らない（Q11）。
  7 時間   ：ds27_timewarp.py（既定と代案の τ(t) の表）。この模块は τ だけを読む。

使い方（numpy だけ）：
    from ds27_model import Generator
    g = Generator("art_on")          # または "art_off"
    X = g.local(-2.0)                # (240, 400, 3) 波の枠の局所座標（float64）
    O = g.origin(-2.0)               # (3,) 波の枠の原点（ワールド）
    W = g.world(-2.0)                # ワールド = O + 局所
    T = g.twhite()                   # (240, 400) float32、τ の秒（+1e9 = t* まで白にならない）
入力（Git 対象外、SHA-256 を照合）：Unity/Build/ArtFirst/26修正01/kstar/（K*）、Docs/Evidence/Design/26/ds26_conditions.json、
Tools/GWWaveGen/ds27/ds27_params.json。利用者の Houdini 解算のファイルは読まない（数値は設計26 の記録にあるものだけ）。
"""
import hashlib
import json
import math
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARAMS_JSON = os.path.join(HERE, "ds27_params.json")
G = 9.81


# ---------------------------------------------------------------- 小道具
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smin(a, b, k):
    """滑らかな最小（softplus。|a − b| ≫ k で min(a, b)、差 0 で min − k·ln2）。"""
    return b - k * math.log1p(math.exp((b - a) / k)) if (b - a) / k < 30 else a


def ease_in(x):
    """0 で値 0・傾き 0、1 で値 1・傾き 1.5（t* で止まらない）。"""
    x = np.clip(x, 0.0, 1.0)
    return 0.5 * (3.0 * x * x - x ** 3)


def integ_S(tp, Tr):
    """∫0^tp S(t'/Tr) dt' と ∫0^tp ∫0^t'' S dt' dt''（S = smoothstep、Tr 以後は 1）。設計26 e4_common.integ_S と同じ。"""
    s = np.clip(tp / Tr, 0.0, 1.0)
    IS = Tr * (s ** 3 - s ** 4 / 2) + np.maximum(tp - Tr, 0.0)
    ISg = np.where(tp <= Tr, Tr ** 2 * (0.75 * s ** 4 - 0.4 * s ** 5), Tr ** 2 * 0.35 + (tp ** 2 - Tr ** 2) / 2)
    return IS, ISg


class Tab:
    """[x, y] の組を単調な 3 次 Hermite（Fritsch–Carlson）でつなぐ表。始まりの傾き 0、終わりの傾き end_slope
    （行ごとの配列も可。呼び出しで上書き）。範囲の前は始まりの値、後ろは終わりの傾きで直線に延ばす。"""

    def __init__(self, pts, end_slope=0.0):
        xs, ys = np.asarray(pts, np.float64).T
        self.x, self.y = xs, ys
        self.h = np.diff(xs)
        d = np.diff(ys) / self.h
        m = np.zeros_like(ys)
        for i in range(1, len(xs) - 1):
            if d[i - 1] * d[i] > 0:
                w1 = 2 * self.h[i] + self.h[i - 1]
                w2 = self.h[i] + 2 * self.h[i - 1]
                m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        m[-1] = end_slope
        self.m = m

    def __call__(self, s, end_slope=None):
        s = np.asarray(s, np.float64)
        xs, ys, h, m = self.x, self.y, self.h, self.m
        sc = np.clip(s, xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, sc, side="right") - 1, 0, len(xs) - 2)
        t = (sc - xs[i]) / h[i]
        m1 = m[i + 1]
        mend = m[-1] if end_slope is None else np.asarray(end_slope, np.float64)
        if end_slope is not None:
            m1 = np.where(i + 1 == len(xs) - 1, mend, m1)
        v = ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h[i] * m[i]
             + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h[i] * m1)
        return np.where(s > xs[-1], ys[-1] + mend * (s - xs[-1]), v)


class LogisticF:
    """前の足の倍率 F(σ) = 1 + (F0 − 1)·(g(σ) − g(0))/(1 − g(0))、g = 1/(1 + exp((σ − m)/w))。設計27修正の2回目：
    表（単調な 3 次 Hermite）の節点で二階微分が跳び、前の足（列 394）の加速度が 2 g を超えていた（τ −4.1 s、P13(2)）ので、
    滑らかなロジスティックにした（段階 a・b の値は表とほぼ同じ：F(−4.2) ≈ 1.9、F(−3.4) ≈ 1.45）。"""

    def __init__(self, F0, m, w, x0=-11.5):
        self.F0, self.m, self.w = float(F0), float(m), float(w)
        self.g0 = 1.0 / (1.0 + math.exp((0.0 - self.m) / self.w))
        self.x = np.array([x0])

    def __call__(self, s, end_slope=None):
        s = np.asarray(s, np.float64)
        g = 1.0 / (1.0 + np.exp(np.clip((s - self.m) / self.w, -60, 60)))
        return 1.0 + (self.F0 - 1.0) * (g - self.g0) / (1.0 - self.g0)


class RateTab:
    """上昇の速さ r(σ) を折れ線で与え、高さ h(σ) = h_end − ∫_σ^{σ_end} r を解析的に積分する表（加速度 = r の傾きが有界）。
    σ_end で h = h_end。範囲の前は始まりの値。"""

    def __init__(self, rate_pts, h_end):
        xs, rs = np.asarray(rate_pts, np.float64).T
        self.x, self.r = xs, rs
        seg = 0.5 * (rs[1:] + rs[:-1]) * np.diff(xs)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.h_knot = h_end - (cum[-1] - cum)
        self.h_end = h_end
        self.m_end = float(rs[-1])

    def __call__(self, s):
        s = np.asarray(s, np.float64)
        xs, rs = self.x, self.r
        sc = np.clip(s, xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, sc, side="right") - 1, 0, len(xs) - 2)
        dx = sc - xs[i]
        sl = (rs[i + 1] - rs[i]) / (xs[i + 1] - xs[i])
        return self.h_knot[i] + rs[i] * dx + 0.5 * sl * dx * dx


def jonswap(f, fp, gamma=3.3):
    sg = np.where(f <= fp, 0.07, 0.09)
    return f ** -5 * np.exp(-1.25 * (fp / f) ** 4) * gamma ** np.exp(-(f - fp) ** 2 / (2 * sg * sg * fp * fp))


class Seam:
    """K* の点列 Kseg（(n, 2)）の弧長の比に沿って、P0（接線 D0）→ P1（接線 D1）の 3 次 Hermite と、
    Kseg[0]→P0・Kseg[-1]→P1 の相似変換（回転・拡大）を作る。τ によらない部分を先に計算しておく。"""

    def __init__(self, Kseg, by_column=False):
        self.K = np.asarray(Kseg, np.float64)
        if by_column:
            # 列の番号の比（K* の列の割り付けが行の間で変わる所でも、隣の行と同じ比になる）
            t = (np.arange(len(self.K)) / max(len(self.K) - 1, 1))[:, None]
        else:
            s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(self.K, axis=0).T))])
            t = (s / max(s[-1], 1e-12))[:, None]
        self.h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        self.h10 = t ** 3 - 2 * t ** 2 + t
        self.h01 = -2 * t ** 3 + 3 * t ** 2
        self.h11 = t ** 3 - t ** 2
        self.z = self.K[:, 0] + 1j * self.K[:, 1]
        self.dz = self.z[-1] - self.z[0]

    def hermite(self, P0, D0, P1, D1, scale=1.0):
        L = max(float(np.hypot(*(P1 - P0))), 1e-6) * scale
        return self.h00 * P0[None] + self.h10 * (L * D0)[None] + self.h01 * P1[None] + self.h11 * (L * D1)[None]

    def similarity(self, P0, P1):
        w0 = P0[0] + 1j * P0[1]
        M = ((P1[0] + 1j * P1[1]) - w0) / self.dz if abs(self.dz) > 1e-9 else 1.0
        w = w0 + M * (self.z - self.z[0])
        return np.stack([w.real, w.imag], 1)


def arc_fraction(P):
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    return s / max(s[-1], 1e-12), s[-1]


def unit(v):
    n = float(np.hypot(v[0], v[1]))
    return v / n if n > 1e-12 else np.array([1.0, 0.0])


def angle_dir(deg):
    """水平から deg 度だけ下向き（前へ）の単位ベクトル。"""
    r = np.radians(deg)
    return np.stack([np.cos(r), -np.sin(r)], -1)


# ---------------------------------------------------------------- K*
class KStar:
    """26修正01 の K*（kstar_a45.gwb・_rows.npz・_meta.json）。読むだけ。"""

    def __init__(self, P):
        inp = P["inputs"]
        self.dir = os.path.join(REPO, inp["kstar_dir"])
        paths = {"gwb": "kstar_a45.gwb", "rows": "kstar_a45_rows.npz", "meta": "kstar_a45_meta.json"}
        want = {"gwb": inp["kstar_gwb_sha256"], "rows": inp["kstar_rows_sha256"], "meta": inp["kstar_meta_sha256"]}
        self.sha = {}
        for k, fn in paths.items():
            p = os.path.join(self.dir, fn)
            if not os.path.isfile(p):
                raise SystemExit("[ds27] K* がありません：%s" % os.path.relpath(p, REPO))
            self.sha[k] = sha256_file(p)
            if self.sha[k] != want[k]:
                raise SystemExit("[ds27] K* の SHA-256 が記録と違います：%s" % fn)
        b = open(os.path.join(self.dir, paths["gwb"]), "rb").read()
        if b[:4] != b"GWW0":
            raise SystemExit("[ds27] GWW0 ではありません")
        _, nu, nv, _ = struct.unpack("<4i", b[4:20])
        ntri = struct.unpack("<i", b[28:32])[0]
        n = nu * nv
        o = 32 + n * 16
        self.tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy()
        o += ntri * 12
        self.Xgwb = np.frombuffer(b, np.float32, n * 3, o).reshape(nv, nu, 3).astype(np.float64)
        self.nu, self.nv = nu, nv
        z = np.load(os.path.join(self.dir, paths["rows"]))
        self.A = z["A"].astype(np.float64)
        self.Y = z["Y"].astype(np.float64)
        self.c = z["c"].astype(np.float64)
        meta = load_json(os.path.join(self.dir, paths["meta"]))
        fr = meta["frame"]
        self.e = np.array(fr["e_crest"], np.float64)
        self.t = np.array(fr["t_travel"], np.float64)
        self.O = np.array(fr["section_origin_world"], np.float64)
        self.up = np.array([0.0, 1.0, 0.0])
        self.main_row = int(meta["rows"]["main_row"])
        self.X = self.world_from_section(self.A, self.Y)          # K* のワールド（float64、断面から）
        self.recon_max_m = float(np.abs(self.X - self.Xgwb).max())

    def world_from_section(self, A, Y, O=None):
        O = self.O if O is None else O
        return (O[None, None, :] + self.c[:, None, None] * self.e[None, None, :]
                + A[..., None] * self.t[None, None, :] + Y[..., None] * self.up[None, None, :])


# ---------------------------------------------------------------- 生成器
class Generator:
    def __init__(self, version="art_on", params_path=PARAMS_JSON, log=None):
        if version not in ("art_on", "art_off"):
            raise ValueError("version は art_on か art_off")
        self.version = version
        self.log = log or (lambda *a: None)
        self.params_path = params_path
        self.P = load_json(params_path)
        P = self.P
        cpath = os.path.join(REPO, P["inputs"]["conditions"])
        self.cond_sha = sha256_file(cpath)
        if self.cond_sha != P["inputs"]["conditions_sha256"]:
            raise SystemExit("[ds27] ds26_conditions.json の SHA-256 が記録と違います")
        self.C = load_json(cpath)
        self.params_sha = sha256_file(params_path)
        on = bool(P["switches"]["versions"][version])
        self.sw = {k: on for k in P["switches"]["names"]}
        self.K = KStar(P)
        C = self.C
        cal, phys = C["calibration"], C["physical_input"]
        self.c0 = 20.0                                        # 峰の模様の速さ（設計26 §1.3：17.4/cos30° ≈ 20 m/s）
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
        # 設計27修正の1回目：噴流の始まりの帯の上面の角を設計26 の 40° から変えられるようにする（段階 c の頂の角 θc、P15）
        ov_ = self.P["front"].get("strip_angle_override_deg")
        if ov_:
            self.th1f = float(ov_.get("upper", self.th1f))
            self.th2f = float(ov_.get("under", self.th2f))
        self.Tr_max = float(P["lip"]["release_ramp_max_s"])
        self.tau_min = float(P["range"]["tau_min_s"])
        self._tables()
        self._rows()
        self._clock_setup()
        self._lip_setup()
        self._seam_setup()
        self._xs_setup()
        self._sea_setup()

    # ------------------------------------------------------------ 表
    def _tables(self):
        P = self.P
        s0 = float(P["range"]["sigma_table_start_s"])
        ch = P["crest_height"]
        self.h_c = float(ch["H_over_Hstar_at_onset"])
        self.tab_h = RateTab(ch["rise_rate_table"], self.h_c)
        self.h_adj0 = float(ch["onset_slope_adjust_from_sigma"])
        self.tab_Lb = Tab(P["back"]["Lb_table"], P["back"]["Lb_end_slope"])
        fr = P["front"]
        self.tab_th1 = Tab(fr["strip_angles_deg_table"]["upper"], 0.0)
        self.tab_th2 = Tab(fr["strip_angles_deg_table"]["under"], 0.0)
        an = fr["anchor"]
        self.anc = dict(D_s=float(an["offset_start_over_H"]), D_e=float(an["offset_end_over_H"]), s0=float(an["retreat_sigma"][0]),
                        s1=float(an["retreat_sigma"][1]), e0=float(an["to_kstar_sigma"][0]))
        self.tab_sw = Tab(fr["wall_s_table"], fr["wall_s_end_slope"])
        cp = P["back"].get("crest_cap")
        self.cap_on = bool(cp)
        if cp:
            # 設計27修正の1回目：頂の帽子（背面の頂の近くの下がりを縦に縮めて頂を丸める。頂の角 θc を段階 a〜c で設計26 §3.1 の値へ。t* で 0）
            self.tab_cap = Tab(cp["omega_table"], cp.get("omega_end_slope", 0.0))
            self.cap_D_over_H = float(cp["D_over_H"])
            assert abs(self.tab_cap(0.0)) < 1e-12, "頂の帽子は t* で 0"
        self.tab_F = Tab(fr["foot_F_table"], fr["foot_F_end_slope"])
        if fr.get("foot_F_logistic"):
            self.tab_F = LogisticF(**fr["foot_F_logistic"])

        self.wall_start_max = math.radians(fr["wall_start_angle_max_deg"])
        self.psi_b_rng = fr["upper_psi_ramp_s"]
        self.herm_scale = float(fr["hermite_tangent_scale"])
        self.rim_tangent_blend_s = float(fr["rim_tangent_blend_s"])
        assert abs(self.tab_th1(-2.4) - self.th1f) < 1e-9 and abs(self.tab_th2(-2.4) - self.th2f) < 1e-9
        for tb in (self.tab_Lb, self.tab_sw, self.tab_F):
            assert abs(tb(0.0) - 1.0) < 1e-12, "表の t* の値が K* と違う"
            assert tb.x[0] <= s0

    # ------------------------------------------------------------ 行ごとの値
    def _rows(self):
        K, P = self.K, self.P
        A, Y, c = K.A, K.Y, K.c
        nv, nu = K.nv, K.nu
        pc = P["profile_columns"]
        self.jB, self.jK, self.jE = pc["j_B"], pc["j_corner"], pc["j_E"]
        H = Y.max(1)
        self.H = H
        rw = P["rows"]
        self.has_body = H >= float(rw["body_H_min_m"])
        self.w_body = smoothstep((H - rw["body_weight_H_m"][0]) / (rw["body_weight_H_m"][1] - rw["body_weight_H_m"][0]))
        self.w_cplx = smoothstep((H - rw["complex_weight_H_m"][0]) / (rw["complex_weight_H_m"][1] - rw["complex_weight_H_m"][0]))
        self.w_cplx[~self.has_body] = 0.0
        # 頂の列：K* の頂の列（argmax）は平らな頂で 84〜92 と跳ぶので、波峰線方向に平滑して丸める（背面の縮みの中心が隣の行とそろう）
        jt_raw = np.argmax(Y, 1).astype(np.float64)
        sgr = float(rw["root_row_smooth_m"])
        hb = H >= float(rw["body_H_min_m"])
        Wr = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sgr) ** 2) * hb[None, :]
        jt_s = (Wr @ jt_raw) / np.maximum(Wr.sum(1), 1e-12)
        self.root = np.where(hb, np.round(jt_s), jt_raw).astype(int)
        self.root_raw = jt_raw.astype(int)
        self.a_root = A[np.arange(nv), self.root]
        self.y_root = Y[np.arange(nv), self.root]      # 頂の高さ（t* で K* のこの列に着く）
        self.seg = np.hypot(np.diff(A, axis=1), np.diff(Y, axis=1))               # (nv, nu-1)
        self.sarc = np.concatenate([np.zeros((nv, 1)), np.cumsum(self.seg, 1)], 1)  # 列ごとの弧長
        # 内壁の錨（0.3H の交差、列 j_corner〜j_E の最初）：全行
        ja = np.full(nv, self.jK + 30, int)
        for r in range(nv):
            if not self.has_body[r]:
                continue
            w = np.arange(self.jK, self.jE + 1)
            yw = Y[r, w] - 0.3 * H[r]
            k = np.where(yw[:-1] * yw[1:] <= 0)[0]
            if len(k):
                k = k[0]
                f = (0.3 * H[r] - Y[r, w[k]]) / (Y[r, w[k + 1]] - Y[r, w[k]] + 1e-12)
                ja[r] = self.jK + k + (1 if f > 0.5 else 0)
        self.ja = ja
        # 唇（設計26 e4_common と同じ判定）：巻きのある行の唇先・rim・張り出し
        jtip = np.full(nv, -1, int)
        rim = np.full(nv, -1, int)
        ov = np.full(nv, -9.0)
        e4cur = np.zeros(nv, bool)
        for r in range(nv):
            if H[r] < 2.0:
                continue
            y = Y[r]
            a = A[r]
            jt = self.root[r]
            if jt >= 200:
                continue
            sg = np.arange(jt, self.jK + 1)
            jp = int(sg[np.argmax(a[sg])])
            # 唇先：K* の唇に前へ出た山が 2 つある行（鉤）では、頂から見て最初の山が一番前から tip_tie_m 以内ならそれを取る（隣の行と唇先の列がそろう）
            am = a[sg]
            loc = np.nonzero((am[1:-1] >= am[:-2]) & (am[1:-1] >= am[2:]))[0] + 1
            for k in loc:
                if am[k] >= am.max() - self.P["rows"]["tip_tie_m"]:
                    jp = int(sg[k])
                    break
            a03 = A[r, ja[r]]
            ov[r] = (a[jp] - a03) / H[r]
            un = np.arange(jp, self.jK + 1)
            yy = y[un]
            kmin = next((i for i in range(1, len(yy) - 1) if yy[i] <= yy[i - 1] and yy[i] < yy[i + 1]), len(yy) - 1)
            un = un[:max(kmin + 1, 6)]
            jtip[r], rim[r] = jp, int(un[-1])
            e4cur[r] = (ov[r] >= 0.2) and (jp > jt + 5)
        self.overhang = ov
        self.e4_curled = e4cur
        # 唇の重み κ
        lo, hi = rw["curl_weight_overhang_over_H"]
        kap = smoothstep((ov - lo) / (hi - lo))
        kap[H < 2.0] = 0.0
        sgm = float(rw["curl_weight_row_smooth_m"])
        Wc = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sgm) ** 2)
        # 設計27修正の1回目：奥の壁の側（c > 0）では、平滑の前に κ を波峰線方向に dil だけ外へ広げる（最大値のフィルター）。
        # 峰で最も高い巻きの行（c = +3.85 m、巻きの行の最後）で κ = 1 になり、唇が重力だけで動く（P4）。減衰は奥の壁の手前の行へ移る。
        dil = float(rw.get("curl_weight_dilate_far_m", 0.0))
        if dil > 0:
            kd = kap.copy()
            for r in range(nv):
                if c[r] > 0:
                    near = np.abs(c - c[r]) <= dil + 1e-9
                    kd[r] = kap[near].max()
            kap = kd
        kap_s = (Wc * kap[None, :]).sum(1) / Wc.sum(1)
        kap_s[kap_s < 0.02] = 0.0
        kap_s[kap_s > 0.999] = 1.0
        if self.version == "art_on":
            self.kappa = kap_s
        else:
            a0, a1 = rw["artoff_lip_weight_H_m"]
            self.kappa = smoothstep((H - a0) / (a1 - a0))
            self.kappa[self.kappa < 1e-3] = 0.0
        # 唇の境の列：巻きのある行の値を 5 行のメディアンで均し、ほかの行は一番近い巻きのある行
        cur = np.nonzero(e4cur)[0]
        half = int(rw["boundary_median_rows"]) // 2
        tip_s = np.zeros(nv, int)
        rim_s = np.zeros(nv, int)
        for r in range(nv):
            q = cur[np.argmin(np.abs(cur - r))]
            if not e4cur[r]:
                tip_s[r], rim_s[r] = jtip[q], rim[q]
                continue
            win = cur[(cur >= r - half) & (cur <= r + half)]
            tip_s[r] = int(np.median(jtip[win]))
            rim_s[r] = int(np.median(rim[win]))
        # 行の間の跳び（K* の列の割り付けが主断面の付近で変わる：rim 205 → 225）を、波峰線方向のガウスでならして丸める
        sg_b = float(rw["boundary_row_smooth_m"])
        if sg_b > 0:
            Wb = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sg_b) ** 2)
            Wb /= Wb.sum(1, keepdims=True)
            rim_s = np.round(Wb @ rim_s.astype(np.float64)).astype(int)     # 唇先は平滑しない（K* の一番前の列からずらすと唇先で折れる）
        if self.version == "art_off" and sg_b > 0:
            tip_s = np.round(Wb @ tip_s.astype(np.float64)).astype(int)   # 切った版は標的を使わないので唇先の列もならす
        rim_s = np.maximum(rim_s, tip_s + 3)
        rim_s = np.minimum(rim_s, self.ja - 20)
        tip_s = np.minimum(tip_s, rim_s - 3)
        self.tip = tip_s
        self.rim = rim_s
        self.lip_rows = np.nonzero((self.kappa > 0) & self.has_body & (self.w_cplx > 0))[0]
        # 峰の行（入れた版は設計26 の c = +3.85 m、切った版は奥の壁も砕けるので一番高い行）
        if self.version == "art_on" or self.sw["ds_farwall_hold"]:
            self.c_pk = self.c_pk_on
        else:
            self.c_pk = float(c[int(np.argmax(H))])
        self.T_row = np.maximum(self.tau0 - np.abs(c - self.c_pk) / self.vpeel, self.floor)
        if not self.sw["ds_lip_target_kstar"]:
            # 切った版：唇を前へ積分するので、低い行の唇が t* の前に着水しない（崩壊を作らない、Q11）ように、噴流の始まりを
            # 主断面の 2.21 s の Froude 相似（√(H/H*)）で抑える（下限はそのまま）
            self.T_row = np.maximum(np.minimum(self.T_row, 2.2075 * np.sqrt(np.maximum(H, 0.0) / 20.8)), self.floor)
        self.lag = self.tau0 - self.T_row
        # 噴流の後の頂の上昇（設計26：1 m/s）。手前の端の小さい行は高さに比例して弱める（H 12 m 未満）
        self.vH_r = self.vH * np.clip(H / 12.0, 0.0, 1.0)
        self.K_ja = np.stack([A[np.arange(nv), self.ja], Y[np.arange(nv), self.ja]], 1)
        # K* の頂→錨の弦の角 γ*（0〜π）
        dy = self.y_root - self.K_ja[:, 1]
        da = self.K_ja[:, 0] - self.a_root
        self.gamma_star = np.arctan2(np.maximum(dy, 1e-6), da)
        # 平らな余白の間隔の比（外端は固定）
        a0 = A[:, 0]
        a1 = A[:, -1]
        self.fb = (A[:, :self.jB + 1] - a0[:, None]) / np.maximum(A[:, self.jB] - a0, 1e-9)[:, None]
        self.ff = (A[:, self.jE:] - A[:, self.jE][:, None]) / np.maximum(a1 - A[:, self.jE], 1e-9)[:, None]
        self.sheet_a0 = float(A[:, 0].min())
        self.sheet_a1 = float(A[:, -1].max())
        # 内壁の線分の向き（K*、ja〜j_E、行ごとに巻き戻し、最後を 0 付近に）
        self.wall = {}
        for r in range(nv):
            if not self.has_body[r]:
                continue
            j0 = self.ja[r]
            da_ = np.diff(A[r, j0:self.jE + 1])
            dy_ = np.diff(Y[r, j0:self.jE + 1])
            L = np.hypot(da_, dy_)
            raw = np.arctan2(dy_, da_)
            last = raw[0] if L[0] > 1e-9 else -math.pi / 2
            for j in range(len(raw)):
                if L[j] <= 1e-9:
                    raw[j] = last
                last = raw[j]
            th = np.unwrap(raw)
            th -= 2 * math.pi * np.round(th[-1] / (2 * math.pi))
            ell = np.concatenate([[0.0], np.cumsum(L)])
            ell = 0.5 * (ell[:-1] + ell[1:]) / max(ell[-1], 1e-9)
            self.wall[r] = (L, th, ell)
        # 切った版の背面：物理の交差波群の断面（λ 195 m、線形＋狭帯域の 2 次、頂 = 1）
        self._group_back()
        # 切った版の足跡の広がりの重み（本体のある行で 1。波峰線方向に σ artoff_width_row_smooth_m で平滑し、塔の両端で滑らかに K* の幅へ）
        sgw = float(rw["artoff_width_row_smooth_m"])
        Wg = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sgw) ** 2)
        self.w_grp = np.minimum(np.clip((Wg @ self.w_body.astype(np.float64)) / Wg.sum(1), 0.0, 1.0), smoothstep(H / 3.0)) * (H >= float(rw["body_H_min_m"]))

    def _group_back(self):
        lam = self.lam_p
        fp = math.sqrt(G / (2 * math.pi * lam))
        fq = np.linspace(0.5 * fp, 2.5 * fp, 256)
        Sp = jonswap(fq, fp, self.gamma_j)
        amp = np.sqrt(Sp)
        amp /= amp.sum()
        kk = (2 * math.pi * fq) ** 2 / G
        kx = kk * math.cos(math.radians(self.half_angle))
        xs = np.linspace(-80.0, 0.0, 1601)
        e1 = (amp[None, :] * np.cos(np.outer(xs, kx))).sum(1)
        hil = (amp[None, :] * np.sin(np.outer(xs, kx))).sum(1)
        kbar = (amp * kk).sum() / amp.sum()
        Ht = 20.8
        AL = (-1 + math.sqrt(1 + 2 * kbar * Ht)) / kbar
        body = (AL * e1 + 0.5 * kbar * AL ** 2 * (e1 ** 2 - hil ** 2)) / Ht
        k0 = np.where(body <= 0.02)[0]
        k0 = k0[-1] if len(k0) else 0
        self.grp_xs = xs[k0:]                  # 頂の後ろ（負）→ 頂（0）
        self.grp_y = np.clip(body[k0:], 0.0, None)
        self.grp_Wb = float(-self.grp_xs[0])  # 背面の半幅（頂 → 0.02H の点）
        self.grp_y[0] = 0.0

    # ------------------------------------------------------------ 時計と平行移動
    def _clock_setup(self):
        self.h_on = float(self.P["clock"]["onset_smooth_s"])

    def sigma(self, tau):
        """行ごとの段階の時計 σ_r(τ)（(nv,)）。"""
        T, lag, h = self.T_row, self.lag, self.h_on
        x = tau + T
        Kq = 1.0 / (T - h / 2)
        xh = np.clip(x / h, 0.0, 1.0)
        Q = np.where(x <= 0, 0.0, np.where(x < h, Kq * h * (xh ** 3 - xh ** 4 / 2), Kq * (h / 2 + (x - h))))
        return tau - lag + lag * Q

    def D(self, T, T_row):
        """t* の T 秒前から t* までに頂が進む距離（地面）。噴流の始まりの後は c0 → β c0 に線形に減速。"""
        T = np.asarray(T, np.float64)
        b, c0 = self.beta, self.c0
        return np.where(T <= T_row, b * c0 * T + (1 - b) * c0 * T ** 2 / (2 * T_row),
                        b * c0 * T_row + (1 - b) * c0 * T_row / 2 + c0 * (T - T_row))

    def frame_X(self, tau):
        """波の枠の原点が t* までに進む残りの距離 X(τ)（峰の行の頂に合わせる）。"""
        return float(self.D(-min(tau, 0.0), self.tau0))

    def origin(self, tau):
        return self.K.O - self.frame_X(tau) * self.K.t

    def crest(self, tau):
        """行ごとの頂（局所の a、y）と、せん断を含めた行のずれ。"""
        T = -tau
        sig = self.sigma(tau)
        shear = (self.D(T, self.tau0) - self.D(T, self.T_row)) * self.w_body
        a_c = self.a_root + shear
        y_on = self.y_root - self.vH_r * self.T_row
        # 始まりの傾きを行ごとの vH_r にそろえる：[σ_a0, −2.4] で (m_r − m_共通)·h·(t³ − t²) を足す（t = 0 で値・傾き 0、t = 1 で値 0・傾き 1）
        mend = self.vH_r / np.maximum(y_on, 1e-6) * self.h_c
        hw = -2.4 - self.h_adj0
        tt = np.clip((sig - self.h_adj0) / hw, 0.0, 1.0)
        pre = y_on * (self.tab_h(sig) + (mend - self.tab_h.m_end) * hw * (tt ** 3 - tt ** 2)) / self.h_c
        post = self.y_root - self.vH_r * T
        y_c = np.where(tau >= -self.T_row, post, pre)
        return a_c, y_c, sig, shear

    # ------------------------------------------------------------ 唇（層4）
    def _lip_setup(self):
        K = self.K
        A, Y = K.A, K.Y
        target = self.sw["ds_lip_target_kstar"]
        claws_on = self.sw["ds_claws"]
        prof = self.P["lip"]["median_launch_profile"]
        pu = np.array(prof["upper"], np.float64)
        pn = np.array(prof["under"], np.float64)
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
                # 切った版：K* の標的を使わないので、弧長の比の代わりに列の番号の比（行の間で同じ列が同じ比になり、K* の列の
                # 割り付けが変わる主断面の付近でも隣の行と同じ打ち出しになる）
                nu_ = max(tip - root, 1)
                s = np.concatenate([(tip - cols[upm]) / nu_, np.minimum((cols[~upm] - tip) / nu_, 1.0)]).astype(np.float64)
            T_row = float(self.T_row[r])
            Ti = T_row * np.clip(1 - s, 0, 1) ** self.p_rel
            if not target:
                Ti = np.where(upm, Ti, T_row)     # 切った版：下面は唇先と同時に放す（遅れて放すと唇先より上へ出て膜が折れる）
            Tc = np.maximum(Ti, float(lp["Tc_min_s"]))
            dl = self.strip_delta * float(np.clip(self.H[r] / lp["strip_spacing_scale_H_m"], lp["strip_spacing_min_factor"], 1.0))
            k_up = (cols - root).astype(np.float64)
            k_un = (cols - tip).astype(np.float64)
            n_up = float(tip - root)
            off = np.where(upm[:, None], k_up[:, None] * dl * d1[None, :], n_up * dl * d1[None, :] + k_un[:, None] * dl * d2[None, :])
            Kt = np.stack([A[r, cols], Y[r, cols]], 1)
            if target and not claws_on:
                # 鉤・爪を除いた標的：K* の唇を列の方向に 5 列のガウスで平滑（両端は固定）
                g_ = np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2)
                g_ /= g_.sum()
                sm = np.stack([np.convolve(np.pad(Kt[:, i], 6, mode="edge"), g_, mode="valid") for i in range(2)], 1)
                wgt = smoothstep(np.minimum(np.arange(len(cols)), np.arange(len(cols))[::-1]) / 6.0)[:, None]
                Kt = Kt + wgt * (sm - Kt)
            Tr = np.minimum(self.Tr_max, Tc / 2)
            ci = self.beta * self.c0 + (1 - self.beta) * self.c0 * Tc / T_row
            kdec = (1 - self.beta) * self.c0 / T_row
            vH = float(self.vH_r[r])
            Pg = np.stack([self.a_root[r] - self.D(Tc, T_row), self.y_root[r] - vH * Tc], 1) + off   # 放出の点（地面）
            IS, ISg = integ_S(Tc, Tr)
            bx = ci * (Tc - IS) - kdec * (Tc ** 2 / 2 - ISg)
            by = vH * (Tc - IS)
            if target:
                u2 = (Kt[:, 0] - Pg[:, 0] - bx) / IS
                w2 = (Kt[:, 1] - Pg[:, 1] - by + G * ISg) / IS
            else:
                # 切った版：打ち出しの速さは設計26 E4c の中央値（上面は唇先からの弧長の比 s の表）。下面は唇先の値から少し遅く
                # （下面が唇先を追い越して膜が折れないように）。放出が t* に近い点は、峰の速さへ滑らかに寄せる（0.6 s 未満）
                u_t = float(np.interp(0.0, pu[:, 0], pu[:, 1]))
                w_t = float(np.interp(0.0, pu[:, 0], pu[:, 2]))
                u_m = np.where(upm, np.interp(s, pu[:, 0], pu[:, 1]), u_t * (1.0 - 0.05 * s)) * self.c0
                w_m = np.where(upm, np.interp(s, pu[:, 0], pu[:, 2]), w_t * (1.0 - 0.2 * s)) * math.sqrt(G * self.H[r])
                bl = smoothstep(Ti / 0.6)
                u2 = ci + (u_m - ci) * bl
                w2 = vH + (w_m - vH) * bl
            # 目安の範囲（設計26 E1：u/c0 0.6〜1.3、w/√(gH) −0.2〜0.8。t* の 0.15 s 前より後に放出される点は評価しない）
            ub = (Kt[:, 0] - Pg[:, 0]) / Tc
            wb = (Kt[:, 1] - Pg[:, 1] + 0.5 * G * Tc ** 2) / Tc
            ev = Ti >= 0.15
            okp = (ub / self.c0 >= 0.6) & (ub / self.c0 <= 1.3) & (wb / math.sqrt(G * self.H[r]) >= -0.2) & (wb / math.sqrt(G * self.H[r]) <= 0.8)
            self.lip[int(r)] = dict(vH=vH, cols=cols, upm=upm, s=s, Ti=Ti, Tc=Tc, Tr=Tr, ci=ci, kdec=kdec, Pg=Pg, u2=u2, w2=w2,
                               dl=dl, k_up=k_up, k_un=k_un, n_up=n_up, T_row=T_row, root=root, tip=tip, rim=rim,
                               n_eval=int(ev.sum()), n_ok=int((ev & okp).sum()), Kt=Kt)

    def _seam_setup(self):
        A0, Y0 = self.K.A, self.K.Y
        self.seam_body = {}
        self.seam_tube = {}
        for r in range(self.K.nv):
            if not self.has_body[r] or self.w_cplx[r] <= 0.0:
                continue
            root, ja = int(self.root[r]), int(self.ja[r])
            cols = np.arange(root, ja + 1)
            self.seam_body[r] = Seam(np.stack([A0[r, cols], Y0[r, cols]], 1))
            if r in self.lip:
                tc = np.arange(int(self.lip[r]["rim"]), ja + 1)
                self.seam_tube[r] = Seam(np.stack([A0[r, tc], Y0[r, tc]], 1), by_column=True)

    def _xs_setup(self):
        sg = float(self.P["lip"]["cross_row_smooth_m"])
        lr = np.array(sorted(self.lip.keys()), int)
        self.xs_on = sg > 0 and len(lr) > 1
        if not self.xs_on:
            return
        j0 = int(min(self.root[lr])) + 1
        j1 = int(max(self.ja[lr]))
        M = np.zeros((len(lr), j1 - j0))
        for i, r in enumerate(lr):
            M[i, int(self.root[r]) + 1 - j0:int(self.ja[r]) - j0] = 1.0
        cc = self.K.c[lr]
        W = np.exp(-0.5 * ((cc[:, None] - cc[None, :]) / sg) ** 2) * (self.kappa[lr][None, :] > 0)
        self.xs_rows, self.xs_j0, self.xs_j1, self.xs_mask, self.xs_W = lr, j0, j1, M, W

    def lip_state(self, r, tau, sig_r):
        """行 r の唇の頂点の地面の断面座標（a、y）。(n, 2)。"""
        L = self.lip[r]
        T = -tau
        tp = L["Tc"] - T
        rel = tp >= 0
        tpc = np.clip(tp, 0.0, None)
        IS, ISg = integ_S(tpc, L["Tr"])
        xr = L["Pg"][:, 0] + L["ci"] * (tpc - IS) - L["kdec"] * (tpc ** 2 / 2 - ISg) + L["u2"] * IS
        yr = L["Pg"][:, 1] + L["vH"] * (tpc - IS) + L["w2"] * IS - G * ISg
        # 放出の前：頂 + 帯の置き場（噴流の始まりの前は帯の角が表に従う）
        th1 = float(self.tab_th1(sig_r))
        th2 = float(self.tab_th2(sig_r))
        d1 = angle_dir(th1)
        d2 = angle_dir(th2)
        dl = L["dl"]
        off = np.where(L["upm"][:, None], L["k_up"][:, None] * dl * d1[None, :],
                       L["n_up"] * dl * d1[None, :] + L["k_un"][:, None] * dl * d2[None, :])
        return np.stack([np.where(rel, xr, 0.0), np.where(rel, yr, 0.0)], 1), rel, off

    # ------------------------------------------------------------ 本体（層3）と唇・管の組み立て
    def sections(self, tau, diag=False):
        """全行の断面（局所の a、y）。(nv, nu) の 2 つ。海（層1）の前。"""
        K = self.K
        A0, Y0 = K.A, K.Y
        nv, nu = K.nv, K.nu
        jB, jE = self.jB, self.jE
        T = -tau
        a_c, y_c, sig, shear = self.crest(tau)
        Dpk = self.D(T, self.tau0)
        A = A0.copy()
        Y = Y0.copy()
        on_back = self.sw["ds_body_narrow"] or self.sw["ds_back_steep"]
        wbd = np.where(self.has_body, self.w_body, 0.0)
        Lb = 1.0 + (self.tab_Lb(sig) - 1.0) * wbd          # 小さい行（H 0.5〜3 m）は足の広がりを弱め、平らな行へなめらかにつなぐ
        F = 1.0 + (self.tab_F(sig) - 1.0) * wbd
        sw_ = self.tab_sw(sig)
        an = self.anc
        Dtab = an["D_s"] - (an["D_s"] - an["D_e"]) * smoothstep((sig - an["s0"]) / (an["s1"] - an["s0"]))
        Eanc = np.full(len(sig), float(ease_in((tau - an["e0"]) / (0.0 - an["e0"]))))   # 物理の時刻 τ で（行の時計の縮みを受けない）
        th1 = self.tab_th1(sig)
        psi_b = ease_in((sig - self.psi_b_rng[0]) / (self.psi_b_rng[1] - self.psi_b_rng[0]))
        if not self.sw["ds_tube_shape"]:
            psi_b = np.zeros_like(psi_b)
        margin_b = float(self.P["back"]["back_foot_margin_m"])
        margin_f = float(self.P["front"]["front_foot_margin_m"])
        info = dict(lb_capped=0, foot_capped=0, wall_bad=0)
        for r in range(nv):
            if not self.has_body[r]:
                continue
            root = int(self.root[r])
            H = self.H[r]
            sy = y_c[r] / max(self.y_root[r], 1e-9)
            ar = self.a_root[r]
            ac = a_c[r]
            # ---- 背面（j_B〜頂）
            bw = max(ar - A0[r, jB], 1e-6)
            if on_back:
                Lb_r = min(Lb[r], max((ac - (A0[r, 0] + margin_b)) / bw, 1.0))
                if Lb_r < Lb[r] - 1e-12:
                    info["lb_capped"] += 1
                A[r, jB:root + 1] = ac + Lb_r * (A0[r, jB:root + 1] - ar)
                Y[r, jB:root + 1] = sy * Y0[r, jB:root + 1]
            else:
                # 切った版：物理の交差波群の背面（K* の背面の横の比で列を並べる）
                u = (ar - A0[r, jB:root + 1]) / bw                       # 1（足）→ 0（頂）
                Wb = bw + (self.grp_Wb - bw) * self.w_grp[r]   # 塔の両端の小さい行は K* の背面の幅へ滑らかに寄せる
                Wb = min(Wb, max(ac - (A0[r, 0] + margin_b), 1.0))
                xg = -u * Wb
                A[r, jB:root + 1] = ac + xg
                Y[r, jB:root + 1] = y_c[r] * np.interp(xg, self.grp_xs * (Wb / self.grp_Wb), self.grp_y)
            if self.cap_on and on_back:
                # 頂の帽子は美術の本体（K* の狭く急な背面）にだけ掛ける。切った版の物理の背面は頂がもともと丸い
                om_ = float(self.tab_cap(sig[r])) * wbd[r]
                if om_ > 0.0:
                    dd = np.maximum(ac - A[r, jB:root + 1], 0.0)
                    fcap = 1.0 - om_ * (1.0 - smoothstep(dd / max(self.cap_D_over_H * H, 1e-6)))
                    Y[r, jB:root + 1] = y_c[r] - (y_c[r] - Y[r, jB:root + 1]) * fcap
            A[r, :jB + 1] = A0[r, 0] + self.fb[r] * (A[r, jB] - A0[r, 0])
            Y[r, :jB + 1] = 0.0
            # ---- 単純な本体（小さい行）：前面を頂を中心に横 F 倍・縦 sy 倍
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
            # ---- 内壁の錨 X_ja と内壁・谷（ja〜j_E）
            ja = int(self.ja[r])
            y_ja = sy * Y0[r, ja]
            # 錨の横の位置：頂からの距離 ΔA = H_r·[D(σ)(1 − E) + q*·E]（D は段階 a〜c で前から頂の真下（少し後ろ）へ smoothstep で戻る。
            # E は t* へ K* の値 q* = (a*_ja − a*_頂)/H_r へ寄せる ease-in）。切った版（ds_tube_shape を切る）は頂の真下より後ろへ行かない。
            qst = (self.K_ja[r, 0] - ar) / H
            # 切った版は頂の真下より後ろへ行かない（0.02H で滑らかに止める：折れ目で錨が急に止まらないように）
            Dr_ = Dtab[r] if self.sw["ds_tube_shape"] else 0.02 + 0.03 * math.log1p(math.exp((Dtab[r] - 0.02) / 0.03))
            a_ja = ac + H * (Dr_ * (1.0 - Eanc[r]) + qst * Eanc[r])
            gam = math.atan2(max(y_c[r] - y_ja, 1e-6), a_ja - ac)
            fw = max(A0[r, jE] - ar, 1e-6)
            a_ft = ac + F[r] * fw
            a_ft_max = A0[r, -1] - margin_f
            if a_ft > a_ft_max:
                a_ft = a_ft_max
                info["foot_capped"] += 1
            if not self.sw["ds_body_narrow"]:
                gW = fw + (self.grp_Wb - fw) * self.w_grp[r]
                a_ft = min(ac + gW, a_ft_max) - 2.0 * math.log1p(math.exp(-abs(ac + gW - a_ft_max) / 2.0))   # 滑らかな最小
            Lw, th, ell = self.wall[r]
            s_w = sw_[r] if self.sw["ds_tube_shape"] else 0.6 * sw_[r]
            wsm = math.radians(8.0)                      # 上限の滑らかな最小（折れ目で錨の動きが急に止まらないように）
            g_w = gam - wsm * math.log1p(math.exp((gam - self.wall_start_max) / wsm))
            th0 = -g_w * (1.0 - smoothstep((ell - 0.65) / 0.35))
            thb = s_w * th + (1.0 - s_w) * th0
            x = np.concatenate([[0.0], np.cumsum(Lw * np.cos(thb))])
            z = np.concatenate([[0.0], np.cumsum(Lw * np.sin(thb))])
            if z[-1] >= -1e-9 or x[-1] <= 1e-6 or a_ft - a_ja <= 0.05 * fw:
                info["wall_bad"] += 1
                a_ft = max(a_ft, a_ja + 0.05 * fw)
                if x[-1] <= 1e-6:
                    x = np.linspace(0, 1, len(x))
                if z[-1] >= -1e-9:
                    z = -np.linspace(0, 1, len(z))
            kz = -y_ja / z[-1]
            kx = (a_ft - a_ja) / x[-1]
            A[r, ja:jE + 1] = a_ja + kx * x
            Y[r, ja:jE + 1] = y_ja + kz * z
            Y[r, jE] = 0.0
            A[r, jE:] = A[r, jE] + self.ff[r] * (A0[r, -1] - A[r, jE])
            Y[r, jE:] = 0.0
            X_ja = np.array([A[r, ja], Y[r, ja]])
            D_ja = unit(np.array([A[r, ja + 1] - A[r, ja], Y[r, ja + 1] - Y[r, ja]]))
            P_top = np.array([ac, y_c[r]])
            # ---- 本体の上の前面（頂〜ja）：Hermite と K* の相似変換を ψ_b で混ぜる
            kap = self.kappa[r] if r in self.lip else 0.0
            if kap < 1.0:
                sb = self.seam_body[r]
                D0 = angle_dir(float(th1[r]))
                Hc = sb.hermite(P_top, D0, X_ja, D_ja, self.herm_scale)
                Bu = Hc if psi_b[r] <= 0.0 else (1 - psi_b[r]) * Hc + psi_b[r] * sb.similarity(P_top, X_ja)
            # ---- 唇（層4）と管の天井
            if kap > 0.0:
                Lp = self.lip[r]
                Xg, rel, off = self.lip_state(r, tau, sig[r])
                # 放出の前は頂（地面）+ 置き場。地面 → 局所：+ D_pk(T)
                crest_g = np.array([self.a_root[r] - self.D(T, self.T_row[r]), y_c[r]])
                Xp = crest_g[None, :] + off
                Xl = np.where(rel[:, None], Xg, Xp)
                Dr = float(self.D(T, self.T_row[r]))
                Xl[:, 0] += Dr + self.w_body[r] * (Dpk - Dr)
                rim = int(Lp["rim"])
                cols_l = Lp["cols"]
                i_rim = len(cols_l) - 1
                X_rim = Xl[i_rim]
                # rim の接線：放出の前は帯の下面の向き、放出の後 rim_tangent_blend_s で唇の下面の向き（rim と 8 列前の差）へ移す
                kb = min(8, i_rim)
                d2p = angle_dir(float(self.tab_th2(sig[r])))
                lam = float(smoothstep((Lp["Tc"][i_rim] - T) / self.rim_tangent_blend_s))
                D_rim = unit((1 - lam) * d2p + lam * unit(Xl[i_rim] - Xl[i_rim - kb]))
                st = self.seam_tube[r]
                Ht = st.hermite(X_rim, D_rim, X_ja, D_ja, self.herm_scale)
                psi_t = float(ease_in((tau + self.T_row[r]) / self.T_row[r])) if self.sw["ds_tube_shape"] else 0.0
                if psi_t <= 0.0:
                    Tu = Ht
                else:
                    Sm = st.similarity(X_rim, X_ja)
                    wB = float(self.P["tube"].get("translate_blend", 0.0))
                    if wB > 0:
                        # 設計27修正の1回目：K* の管の天井の相似変換（rim と錨の弦で回して拡大）は、rim が重力で落ちると
                        # 弦から遠い点の加速度を約 2 倍にする（t* の直前に 2 g、P13(2)）。管の奥ほど、K* の管の天井を
                        # 両端の変位の線形補間で平行に動かす形 Bm へ寄せる（重み wB·S(u)、u は rim → 錨の列の比。時間によらない）。
                        # t* では Sm = Bm = K* なので t* の姿は変わらない
                        Kt_ = st.K
                        uu = np.linspace(0.0, 1.0, len(Kt_))[:, None]
                        Bm = Kt_ + (1 - uu) * (X_rim - Kt_[0])[None] + uu * (X_ja - Kt_[-1])[None]
                        ww = wB * smoothstep(uu)
                        Sm = (1 - ww) * Sm + ww * Bm
                    Tu = (1 - psi_t) * Ht + psi_t * Sm
                Lf = np.zeros((ja - root + 1, 2))
                Lf[0] = P_top
                Lf[1:len(cols_l) + 1] = Xl
                Lf[len(cols_l):] = Tu                       # rim は唇と管で同じ点
                if kap < 1.0:
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
        if self.xs_on:
            # 唇・管の領域の K* からの変位を、波峰線方向に隣の行とならす（K* の列の割り付けが行ごとに変わる所で、
            # 同じ列が隣の行と違う役（唇／管）になって辺が伸びるのを防ぐ）。t* では変位 0 なので K* のまま。
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
            return A, Y, dict(info, a_c=a_c, y_c=y_c, sigma=sig, shear=shear)
        return A, Y

    # ------------------------------------------------------------ 海（層1）
    def _sea_setup(self):
        P = self.P["sea"]
        K = self.K
        lam = self.lam_p
        fp = math.sqrt(G / (2 * math.pi * lam))
        ha = math.radians(self.half_angle)
        dirs = []
        for sgn in (1.0, -1.0):
            d = math.cos(ha) * K.t + sgn * math.sin(ha) * K.e
            dirs.append(np.array([d[0], d[2]]))
        self.sea_dirs = dirs
        # 搬送波（集中する単位の波群、焦点で 1）
        n = int(P["carrier_components_per_system"])
        f0, f1 = P["carrier_f_range_over_fp"]
        fq = np.linspace(f0 * fp, f1 * fp, n)
        Sf = jonswap(fq, fp, self.gamma_j)
        amp = Sf if P.get("carrier_weighting", "newwave") == "newwave" else np.sqrt(Sf)
        amp = amp / amp.sum()
        k = (2 * math.pi * fq) ** 2 / G
        om = 2 * math.pi * fq
        kx = np.concatenate([k * dirs[0][0], k * dirs[1][0]])
        kz = np.concatenate([k * dirs[0][1], k * dirs[1][1]])
        self.car = dict(kx=kx, kz=kz, om=np.concatenate([om, om]), amp=np.concatenate([amp, amp]) * 0.5,
                        ph=np.zeros(2 * n), f=np.concatenate([fq, fq]), k=np.concatenate([k, k]))
        # 背景のうねり（ランダムな位相、Hs）
        ns = int(P["swell_components_per_system"])
        f0, f1 = P["swell_f_range_over_fp"]
        fs = np.linspace(f0 * fp, f1 * fp, ns)
        Ss = jonswap(fs, fp, self.gamma_j)
        a2 = Ss / Ss.sum()                      # 1 系あたり分散 0.5·m0
        m0 = (self.Hs / 4.0) ** 2
        aw = np.sqrt(2 * a2 * 0.5 * m0)         # Σ a²/2 = m0/2 per system
        rng = np.random.default_rng(int(P["swell_seed"]))
        ph = rng.uniform(0, 2 * math.pi, 2 * ns)
        ks = (2 * math.pi * fs) ** 2 / G
        self.swl = dict(kx=np.concatenate([ks * dirs[0][0], ks * dirs[1][0]]), kz=np.concatenate([ks * dirs[0][1], ks * dirs[1][1]]),
                        om=np.concatenate([2 * math.pi * fs] * 2), amp=np.concatenate([aw, aw]), ph=ph,
                        f=np.concatenate([fs, fs]), k=np.concatenate([ks, ks]))
        self.swell_rms = float(math.sqrt((self.swl["amp"] ** 2).sum() / 2))
        self.win_half = float(P["window_half_m"])
        self.Ac_max = float(P["Ac_max_m"])
        self.n_marg = int(P["margin_samples"])
        self.band_b, self.band_f = [float(v) for v in P["replace_edge_band_m"]]
        self.Ac_row_smooth = float(P["Ac_row_smooth_m"])
        self.R_min = float(P["balance_denominator_min_m"])
        self.swell_repl = bool(P.get("swell_replaced_by_body", False))
        self.cap_pow = float(P.get("Ac_soft_cap_power", 0.0))
        cc = self.K.c
        Wc = np.exp(-0.5 * ((cc[:, None] - cc[None, :]) / self.Ac_row_smooth) ** 2)
        self.Ac_smooth = Wc / Wc.sum(1, keepdims=True)
        cl = self.P["calm"]
        self.calm_s = cl["swell_calm_tau_s"]
        self.calm_c = cl["sea_calm_painting_tau_s"]

    def field(self, comp, x, z, tau):
        """成分の和 Σ amp cos(kx·(x − Ox) + kz·(z − Oz) − ω τ + φ)。x, z はワールド（任意の形）。"""
        O = self.K.O
        x = np.asarray(x, np.float64)
        z = np.asarray(z, np.float64)
        shp = x.shape
        X = x.reshape(-1) - O[0]
        Z = z.reshape(-1) - O[2]
        out = np.empty(X.shape[0])
        c0 = comp["om"] * tau - comp["ph"]
        n = 8192
        for i in range(0, X.shape[0], n):
            ph = X[i:i + n, None] * comp["kx"][None, :] + Z[i:i + n, None] * comp["kz"][None, :] - c0[None, :]
            out[i:i + n] = np.cos(ph) @ comp["amp"]
        return out.reshape(shp)

    def line_integral(self, comp, O_tau, c, a0, a1, tau):
        """行の線（ワールド = O(τ) + c·e + a·t、a は局所）に沿った ∫_{a0}^{a1} Σ amp cos(...) da（解析）。"""
        K = self.K
        base = O_tau + c * K.e - K.O
        p0 = comp["kx"] * base[0] + comp["kz"] * base[2] - comp["om"] * tau + comp["ph"]
        q = comp["kx"] * K.t[0] + comp["kz"] * K.t[2]
        return float((comp["amp"] * (np.sin(p0 + q * a1) - np.sin(p0 + q * a0)) / q).sum())

    def calm_factors(self, tau):
        ks = 1.0 - float(smoothstep((tau - self.calm_s[0]) / (self.calm_s[1] - self.calm_s[0]))) if self.sw["ds_swell_calm"] else 1.0
        kc = 1.0 - float(smoothstep((tau - self.calm_c[0]) / (self.calm_c[1] - self.calm_c[0]))) if self.sw["ds_sea_calm_painting"] else 1.0
        return kc, ks

    def margin_weight(self, a, a_bf, a_ff):
        """本体が搬送波の山を置き換える重み。本体と平らな余白は 1、シートの外端の帯（後ろ band_b・前 band_f、余白の 8 割まで）で
        smoothstep で 0 へ（外端で解析式の海とつながる）。"""
        # 設計27修正の1回目：帯の幅の min を滑らかな最小（softplus、幅 0.5 m）にする。足が前へ出て min が切り替わる所で
        # 余白の頂点の速度が折れ、keypose の Hermite の差と二階差分が跳んでいた（前の足の列 394〜396、τ −4.4〜−3.1 s）
        bb = max(smin(self.band_b, 0.8 * (a_bf - self.sheet_a0), 0.5), 1e-3)
        bf = max(smin(self.band_f, 0.8 * (self.sheet_a1 - a_ff), 0.5), 1e-3)
        wb = smoothstep((a - self.sheet_a0) / bb)
        wf = smoothstep((self.sheet_a1 - a) / bf)
        return np.minimum(wb, wf)

    def sea(self, tau, A, Y, diag=False):
        """海（層1）を足した y と、行ごとの搬送波の振幅 A_c,r(τ)。A, Y は本体の断面（局所）。"""
        K = self.K
        nv = K.nv
        O_tau = self.origin(tau)
        kc, ks = self.calm_factors(tau)
        W = self.world_xz(tau, A)
        car, swl = self.car, self.swl
        Ac = np.zeros(nv)
        Abal = np.full(nv, np.nan)
        res = np.zeros(nv)
        apos = np.zeros(nv)
        for r in range(nv):
            a_bf, a_ff = A[r, self.jB], A[r, self.jE]
            wb = self.w_body[r] if self.has_body[r] else 0.0
            a_top = A[r, int(self.root[r])] if self.has_body[r] else 0.0
            a0w, a1w = a_top - self.win_half, a_top + self.win_half
            Cw = self.line_integral(car, O_tau, K.c[r], a0w, a1w, tau)
            Sw = self.line_integral(swl, O_tau, K.c[r], a0w, a1w, tau)
            if wb > 0:
                core = self.line_integral(car, O_tau, K.c[r], a_bf, a_ff, tau)
                ab = np.linspace(self.sheet_a0, a_bf, self.n_marg)
                af = np.linspace(a_ff, self.sheet_a1, self.n_marg)
                am = np.concatenate([ab, af])
                wm = self.margin_weight(am, a_bf, a_ff)
                P3 = O_tau[None, :] + K.c[r] * K.e[None, :] + am[:, None] * K.t[None, :]
                cm = self.field(car, P3[:, 0], P3[:, 2], tau)
                marg = np.trapezoid(wm[:self.n_marg] * cm[:self.n_marg], ab) + np.trapezoid(wm[self.n_marg:] * cm[self.n_marg:], af)
                repl = wb * (core + marg)
                if self.swell_repl:
                    # 設計27修正の1回目：うねりも本体が置き換える（本体の上にうねりを足さない。頂の高さの単調 P13(4)）。釣り合いに入れる
                    core_s = self.line_integral(swl, O_tau, K.c[r], a_bf, a_ff, tau)
                    sm_ = self.field(swl, P3[:, 0], P3[:, 2], tau)
                    marg_s = np.trapezoid(wm[:self.n_marg] * sm_[:self.n_marg], ab) + np.trapezoid(wm[self.n_marg:] * sm_[self.n_marg:], af)
                    srepl = wb * (core_s + marg_s)
                else:
                    srepl = 0.0
            else:
                repl = 0.0
                srepl = 0.0
            areaB = float(np.sum((A[r, 1:] - A[r, :-1]) * (Y[r, 1:] + Y[r, :-1]) / 2.0))
            Rr = repl - Cw
            if wb > 0:
                # 滑らかな正則化した逆数（分母が小さい行で振幅が跳ばないように）と、上限の滑らかな飽和
                ab = max(areaB + Sw - srepl, 0.0) * max(Rr, 0.0) / (Rr * Rr + self.R_min ** 2)
                if self.cap_pow > 0:
                    # 設計27修正の2回目：tanh の飽和は 0.7·A_max で既に約 15% 低く、窓の釣り合いが残っていた（P2・P3）。
                    # 上限の手前までほぼ恒等な滑らかな上限 x/(1 + (x/A_max)^p)^(1/p) にした
                    Abal[r] = float(ab / (1.0 + (ab / self.Ac_max) ** self.cap_pow) ** (1.0 / self.cap_pow))
                else:
                    Abal[r] = float(self.Ac_max * math.tanh(ab / self.Ac_max))
        # 行ごとの振幅：本体の強さを掛け（本体のない行は 0）、波峰線方向に平滑する（うねりは釣り合いに入れない）
        raw = np.where(np.isfinite(Abal), Abal, 0.0) * np.where(self.has_body, self.w_body, 0.0)
        Ac = self.Ac_smooth @ raw
        # 頂点の海
        wv = np.ones_like(A)
        for r in range(nv):
            wb = self.w_body[r] if self.has_body[r] else 0.0
            wm = self.margin_weight(A[r], A[r, self.jB], A[r, self.jE])
            wm[self.jB:self.jE + 1] = 1.0
            wv[r] = wb * wm
        need = (1.0 - wv) > 1e-12
        Cv = np.zeros_like(A)
        if need.any():
            Cv[need] = self.field(car, W[..., 0][need], W[..., 1][need], tau)
        Sv = self.field(swl, W[..., 0], W[..., 1], tau)
        ws = (1.0 - wv) if self.swell_repl else 1.0
        Ynew = Y + (1.0 - wv) * kc * Ac[:, None] * Cv + ks * ws * Sv
        if diag:
            # 窓の符号付きの断面積（入れた値で。静める前の物理の値）
            for r in range(nv):
                a_top = A[r, int(self.root[r])] if self.has_body[r] else 0.0
                a0w, a1w = a_top - self.win_half, a_top + self.win_half
                yph = Y[r] + (1.0 - wv[r]) * Ac[r] * Cv[r] + ((1.0 - wv[r]) if self.swell_repl else 1.0) * Sv[r]
                area_sheet = float(np.sum((A[r, 1:] - A[r, :-1]) * (yph[1:] + yph[:-1]) / 2.0))
                outb = Ac[r] * self.line_integral(car, O_tau, K.c[r], a0w, A[r, 0], tau) + self.line_integral(swl, O_tau, K.c[r], a0w, A[r, 0], tau)
                outf = Ac[r] * self.line_integral(car, O_tau, K.c[r], A[r, -1], a1w, tau) + self.line_integral(swl, O_tau, K.c[r], A[r, -1], a1w, tau)
                res[r] = area_sheet + outb + outf
                apos[r] = float(np.sum(np.clip((A[r, 1:] - A[r, :-1]) * (np.clip(yph[1:], 0, None) + np.clip(yph[:-1], 0, None)) / 2.0, None, None)))
            return Ynew, dict(Ac=Ac, Abal=Abal, A_net=res, A_pos_sheet=apos, kc=kc, ks=ks, wv=wv)
        return Ynew, dict(Ac=Ac, kc=kc, ks=ks)

    def world_xz(self, tau, A):
        """局所の断面の a から、各頂点のワールドの (x, z)（(nv, nu, 2)）。"""
        K = self.K
        O = self.origin(tau)
        x = O[0] + K.c[:, None] * K.e[0] + A * K.t[0]
        z = O[2] + K.c[:, None] * K.e[2] + A * K.t[2]
        return np.stack([x, z], -1)

    # ------------------------------------------------------------ 出力
    def section_y(self, tau, diag=False):
        A, Y, d1 = self.sections(tau, diag=True)
        Yn, d2 = self.sea(tau, A, Y, diag=diag)
        d1.update(d2)
        return A, Yn, d1

    def to_local(self, A, Y):
        K = self.K
        return K.c[:, None, None] * K.e[None, None, :] + A[..., None] * K.t[None, None, :] + Y[..., None] * K.up[None, None, :]

    def local(self, tau, diag=False, info=False):
        """局所座標 (240, 400, 3)。diag=True で (X, A, Y, 情報)（窓の断面積も計算）、info=True で (X, A, Y, 情報)（軽い）。"""
        tau = float(min(tau, 0.0))
        A, Y, d = self.section_y(tau, diag=diag)
        X = self.to_local(A, Y)
        if diag or info:
            return X, A, Y, d
        return X

    def sea_outside(self, tau, Ac, a_ground):
        """シートの外の解析式の海（設計30 の周りの海と同じ式・同じ A_c,r(τ)・同じ静める係数）を、行の断面に沿った地面の a で標本化。
        (nv, na) float64。"""
        K = self.K
        kc, ks = self.calm_factors(tau)
        a = np.asarray(a_ground, np.float64)
        x = K.O[0] + K.c[:, None] * K.e[0] + a[None, :] * K.t[0]
        z = K.O[2] + K.c[:, None] * K.e[2] + a[None, :] * K.t[2]
        return kc * Ac[:, None] * self.field(self.car, x, z, tau) + ks * self.field(self.swl, x, z, tau)

    def sea_model_record(self):
        """設計30 の周りの海が同じ式を使えるように、成分の表と係数を記録する。"""
        def comp(c):
            return dict(kx=[float(v) for v in c["kx"]], kz=[float(v) for v in c["kz"]], omega=[float(v) for v in c["om"]],
                        amp=[float(v) for v in c["amp"]], phase=[float(v) for v in c["ph"]])
        return dict(formula_ja="η(x, z, τ) = κ_c(τ)·A_c,r(τ)·Σ amp·cos(kx·(x − Ox) + kz·(z − Oz) − ω·τ + φ)（搬送波）＋ κ_s(τ)·Σ（うねり、同じ形）。"
                              "(Ox, Oz) = 焦点（K* の断面の原点、ワールド）。x, z はワールド（m）、τ は物理の時刻（s）。シートの上では本体の列は搬送波を持たず、"
                              "平らな余白は本体の足（重み 1）からシートの外端（重み 0）へ smoothstep で搬送波に戻る。A_c,r は行ごと・節点ごとの表（ds27_sea.npz の Ac）。",
                    focus_world=[float(v) for v in self.K.O], carrier=comp(self.car), swell=comp(self.swl),
                    swell_rms_m=self.swell_rms, swell_seed=int(self.P["sea"]["swell_seed"]),
                    calm=dict(ds_swell_calm=bool(self.sw["ds_swell_calm"]), swell_calm_tau_s=self.calm_s,
                              ds_sea_calm_painting=bool(self.sw["ds_sea_calm_painting"]), sea_calm_painting_tau_s=self.calm_c,
                              shape_ja="κ = 1 − smoothstep((τ − τ0)/(τ1 − τ0))。切った版は κ = 1"),
                    window_half_m=self.win_half, sheet_local_a_range=[self.sheet_a0, self.sheet_a1])

    def world(self, tau):
        return self.local(tau) + self.origin(tau)[None, None, :]

    # ------------------------------------------------------------ 白（層6）
    def twhite(self):
        K = self.K
        A0, Y0 = K.A, K.Y
        nv, nu = K.nv, K.nu
        W = self.P["white"]
        NEVER = float(W["never"])
        T = np.full((nv, nu), NEVER, np.float64)
        for r in range(nv):
            if not self.has_body[r] or self.H[r] < 0.3:
                continue
            root = int(self.root[r])
            T_row = float(self.T_row[r])
            t0 = -T_row + float(W["crest_start_after_onset_s"])
            t_back = float(W["back_arrive_tau_s"])
            sa = self.sarc[r]
            # 頂と背面（頂 → j_B）、後ろの平らな海は足と同じ
            lb = (sa[root] - sa[self.jB:root + 1]) / max(sa[root] - sa[self.jB], 1e-6)
            T[r, self.jB:root + 1] = t0 + lb * (t_back - t0)
            T[r, :self.jB] = t_back
            ja = int(self.ja[r])
            if r in self.lip and self.kappa[r] >= 0.5:
                L = self.lip[r]
                tl = -L["Ti"] + float(W["lip_delay_s"])
                if not self.e4_curled[r]:
                    # 設計27修正の1回目：巻きの行（張り出し ≥ 0.2H）でない行（奥の壁の手前）の唇は、白を少し遅らせる。
                    # 最初の白が巻きの行の唇先だけに出る（P9）。奥の壁は t* まで砕けない（ds_farwall_hold）
                    tl = tl + float(W.get("noncurl_lip_extra_delay_s", 0.0))
                if self.version == "art_on":
                    tl = np.minimum(tl, float(W["lip_latest_tau_s"]))
                T[r, L["cols"]] = tl
                rim = int(L["rim"])
                if self.sw["ds_tube_white_early"]:
                    ts = float(W["tube_start_tau_s"]) + float(W["tube_start_lag_factor"]) * float(self.lag[r])
                    te = float(W["tube_arrive_tau_s"])
                    lt = (sa[rim + 1:self.jE + 1] - sa[rim]) / max(sa[self.jE] - sa[rim], 1e-6)
                    T[r, rim + 1:self.jE + 1] = ts + lt * (te - ts)
                    T[r, self.jE + 1:] = te
                else:
                    T[r, rim + 1:] = NEVER
            else:
                te = float(W["front_noncurl_arrive_tau_s"])
                lf = (sa[root + 1:self.jE + 1] - sa[root]) / max(sa[self.jE] - sa[root], 1e-6)
                T[r, root + 1:self.jE + 1] = t0 + lf * (te - t0)
                T[r, self.jE + 1:] = te
        return T.astype(np.float32)

    # ------------------------------------------------------------ 記録
    def summary(self):
        lp = [self.lip[r] for r in self.lip]
        n_ev = sum(L["n_eval"] for L in lp)
        n_ok = sum(L["n_ok"] for L in lp)
        return dict(version=self.version, switches=self.sw, c_pk=self.c_pk, T_row_range=[float(self.T_row.min()), float(self.T_row.max())],
                    lip_rows=int(len(self.lip)), lip_rows_kappa1=int(sum(1 for r in self.lip if self.kappa[r] >= 1.0)),
                    lip_vertices=int(sum(len(L["cols"]) for L in lp)),
                    lip_plausible_fraction=(n_ok / n_ev if n_ev else None), lip_plausible_n_eval=n_ev,
                    swell_rms_m=self.swell_rms, kstar_recon_max_m=self.K.recon_max_m,
                    frame_X_at_tau_min_m=self.frame_X(self.tau_min))
