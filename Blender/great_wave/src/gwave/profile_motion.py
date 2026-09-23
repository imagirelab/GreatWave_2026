"""Great Wave の断面曲線による運動モデル。numpy のみを使用し、bpy は使用しない。

各時点の波は XZ 平面上の1本の断面曲線（H 単位）である。固定数の点で標本化し、
点の番号は UV の U に対応する。背面端→峰→波頭の先端→下面→内側の弧→谷→前面端の順に並ぶ。

* 最終形状: target/base_contour.json。左画面外の背面を滑らかに延長し（仕様7b）、
            隠れた内側の弧の末端と平らな谷を描き直す（仕様7c）。
* 初期形状: 同じ標本点を置いた穏やかなガウス形のうねり。
* 中間形状: 点の位置ではなく接線角と線分長を補間し、点ごとに遅れを付ける。
            背面と前面が先に上昇し、波頭の上部が張り出し、先端と下面が最後に巻き込む。
            tau=1 では全点が同時に最終形状へ到達する。
* 時間: (1, 0)、（張り出し開始フレーム, tau_onset）、（巻き込み開始フレーム, tau_curl）、
        （最終フレーム, 1）を通る単調な3次曲線。終端の傾きは0（停止前の減速、仕様M5）。
* 高さ: フレームと高さの指定点を通る別の単調3次曲線。波頭の角度と長さを独立して変えながら上昇を保つ。
        最終形状は再スケーリングしない。
* 3D: 断面を Y 方向に掃引し、'lift_clip' 方式では輪郭を保つ側面の絞り込みを行う。
"""
import json
import math
import os

import numpy as np

from gw import profile_metrics as pm

PROJECT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
WAVE_PARAMS_JSON = os.path.join(PROJECT, "wave_params.json")


def load_wave_params(path=None):
    with open(path or WAVE_PARAMS_JSON, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    values = {k: v["value"] for k, v in raw.items() if isinstance(v, dict) and "value" in v}
    for key in ("blend_path", "cache_path"):
        value = os.path.expanduser(values[key])
        values[key] = os.path.normpath(value if os.path.isabs(value) else os.path.join(PROJECT, value))
    return values


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _ramp_in(x):
    """w(0)=0, w'(0)=0, w(1)=1, w'(1)=1 の単調関数。開始を緩め、終端の減速は tau(t) に委ねる。"""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (2.0 - x)


def _bezier(p0, p1, p2, p3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + (t ** 3) * p3


def _arclen(p):
    return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])))])


# ------------------------------------------------------------------------------------------ 最終形状
def build_final_profile(WP):
    """H 単位の最終断面 q (n_u, 2)、峰・先端・最深点の番号などを辞書で返す。"""
    bc_path = WP["base_contour"]
    if not os.path.isabs(bc_path):
        bc_path = os.path.join(PROJECT, bc_path)
    bc = pm.load_base_contour(bc_path)
    poly = pm.base_contour_polyline(bc)
    p = poly["pts_H"].copy()
    in_s7 = poly["in_S7"]
    one_pct = float(pm.pct_h_to_H(1.0))

    # ---- 右端（仕様7c）: 判定対象外の補完端を描き直し、Z=0 に水平に接続する。
    k0 = int(np.nonzero(in_s7)[0][-1])
    a = p[k0]
    ta = p[k0] - p[max(0, k0 - 12)]
    ta = ta / np.hypot(*ta)
    e = np.array([p[-1, 0] + WP["right_completion_reach_H"], 0.0])
    reach = np.hypot(*(e - a))
    right = _bezier(a, a + ta * 0.40 * reach, e - np.array([0.45 * reach, 0.0]), e, 80)
    flat = np.stack([np.linspace(e[0], e[0] + WP["right_flat_H"], 40), np.zeros(40)], axis=1)

    # ---- 左端（仕様7b）: 背面を C1 連続で静水面まで延ばし、傾きを単調に0へ近づける。
    s = _arclen(p)
    k = int(np.searchsorted(s, WP["left_slope_chord_pct_h"] * one_pct))
    d = p[max(k, 2)] - p[0]
    alpha = math.atan2(d[1], d[0])
    A = p[0]
    L = float(WP["left_extension_H"])
    L = max(L, 1.25 * A[1] / max(math.tan(alpha), 1e-3))          # 根元の傾きを単調にするのに十分な長さ。
    B = np.array([A[0] - L, 0.0])
    b = min(0.45 * L, 0.8 * A[1] / max(math.sin(alpha), 1e-6))
    P2 = A - b * np.array([math.cos(alpha), math.sin(alpha)])
    P1x = P2[0] - P2[1] / (0.75 * math.tan(alpha))
    P1x = max(P1x, B[0] + 0.1 * L)
    left = _bezier(B, np.array([P1x, 0.0]), P2, A, 120)

    full = np.concatenate([left[:-1], p[:k0 + 1], right[1:], flat[1:]])
    C = pm.Curve(full)

    # ---- n_u 点に適応的に再標本化する。曲率が高い箇所は密にする。
    n_u = int(WP["n_u"])
    sf = np.linspace(0.0, C.length, 6000)
    pf = C.at(sf)
    ang = np.unwrap(np.arctan2(np.gradient(pf[:, 1]), np.gradient(pf[:, 0])))
    curv = np.abs(np.gradient(ang, sf))
    ker = np.exp(-0.5 * (np.arange(-60, 61) / 20.0) ** 2)
    curv = np.convolve(curv, ker / ker.sum(), mode="same")
    dens = 1.0 + WP["density_gain"] * np.minimum(curv / WP["density_curv_ref_per_H"], 1.0)
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(sf))])
    su = np.interp(np.linspace(0.0, cum[-1], n_u), cum, sf)
    q = C.at(su)
    q[0, 1] = 0.0
    q[-1, 1] = 0.0

    m = pm.measure_profile(q)
    lmk = m["landmarks"]
    out = {"q": q, "i_crest": int(lmk["crest"]["index"]), "i_tip": int(lmk["head_tip"]["index"]),
           "i_deep": int(lmk["inner_deepest"]["index"]), "metrics": m, "base_contour": bc,
           "left_alpha_deg": math.degrees(alpha), "left_extension_used_H": L,
           "x_frame_left_H": float(p[0, 0]), "i_flat_start": int(np.argmin(np.abs(su - (C.length - WP["right_flat_H"]))))}
    # 判定対象の輪郭が始まる位置（画面の左端）の標本番号。
    out["i_frame_edge"] = int(np.argmin(np.hypot(q[:, 0] - A[0], q[:, 1] - A[1])))
    return out


# ------------------------------------------------------------------------------------------ 運動モデル
class WaveMotion:
    def __init__(self, WP=None):
        self.WP = WP or load_wave_params()
        WP = self.WP
        F = build_final_profile(WP)
        self.final = F
        q = F["q"]
        self.q = q
        self.n_u = q.shape[0]
        self.i_c, self.i_t, self.i_d = F["i_crest"], F["i_tip"], F["i_deep"]
        d = np.diff(q, axis=0)
        self.ds1 = np.hypot(d[:, 0], d[:, 1])
        self.psi1 = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
        S1 = _arclen(q)
        self.S1 = S1

        # ---- 初期形状: 同じ標本点を穏やかなガウス形のうねりに置く。
        A0, sg = float(WP["swell_amplitude_H"]), float(WP["swell_sigma_H"])
        lam = float(WP["front_length_ratio"])
        xs = np.linspace(-(S1[self.i_c] + 2.0), (S1[-1] - S1[self.i_c]) * lam + 2.0, 8000)
        zs = A0 * np.exp(-(xs / sg) ** 2)
        sw = pm.Curve(np.stack([xs, zs], axis=1))
        s_crest_sw = float(np.interp(0.0, xs, sw.s))
        # 各線分の初期長を最終長の比率で決める。波頭（峰→先端→下面）は短く始まり、
        # 張り出しと巻き込みで峰から伸びる。それ以外の線分は `lam` を保つ。
        i_c, i_t, i_d = self.i_c, self.i_t, self.i_d
        Sm = 0.5 * (S1[1:] + S1[:-1])
        lam_head = float(WP["head_start_length_ratio"])
        s_in = S1[i_c] + 0.12 * (S1[i_t] - S1[i_c])
        s_out0 = S1[i_t] + 0.65 * (S1[i_d] - S1[i_t])
        ratio = np.ones(self.n_u - 1)
        fr = Sm >= S1[i_c]
        ratio[fr] = lam
        head_w = _smooth((Sm - S1[i_c]) / max(s_in - S1[i_c], 1e-9)) * (1.0 - _smooth((Sm - s_out0) / max(S1[i_d] - s_out0, 1e-9)))
        ratio = np.where(fr, lam + (lam_head - lam) * head_w, ratio)
        self.len_ratio0 = ratio
        off = np.concatenate([[0.0], np.cumsum(self.ds1 * ratio)])
        off = off - off[i_c]
        p0 = sw.at(s_crest_sw + off)
        d0 = np.diff(p0, axis=0)
        self.ds0 = np.hypot(d0[:, 0], d0[:, 1])
        self.psi0 = np.arctan2(d0[:, 1], d0[:, 0])
        # 波頭が -90 度から -180 度へ時計回りに回るよう psi1 を psi0 に対して連続化し、±360 度の跳びを避ける。
        self.dpsi = self.psi1 - self.psi0

        # ---- 断面に沿う遅れマスク。0 が最初に動き、1 が最後に動く。
        mask = np.zeros(self.n_u)
        i_c, i_t, i_d = self.i_c, self.i_t, self.i_d
        i_f = F["i_flat_start"]
        mask[i_c:i_t + 1] = _smooth((S1[i_c:i_t + 1] - S1[i_c]) / max(S1[i_t] - S1[i_c], 1e-9))
        v_d, v_f = float(WP["lag_inner_deepest"]), float(WP["lag_trough"])
        mask[i_t:i_d + 1] = 1.0 + (v_d - 1.0) * _smooth((S1[i_t:i_d + 1] - S1[i_t]) / max(S1[i_d] - S1[i_t], 1e-9))
        mask[i_d:i_f + 1] = v_d + (v_f - v_d) * _smooth((S1[i_d:i_f + 1] - S1[i_d]) / max(S1[i_f] - S1[i_d], 1e-9))
        mask[i_f:] = v_f * (1.0 - _smooth((S1[i_f:] - S1[i_f]) / max(S1[-1] - S1[i_f], 1e-9)))
        mseg = 0.5 * (mask[1:] + mask[:-1])                                  # 線分ごとの値。
        self.lag_ang = float(WP["lag_angle_max"]) * mseg                     # 角度が少し先行し、
        self.lag_len = float(WP["lag_length_max"]) * mseg                    # 長さが後から伸びる。

        # 最終形状で内側の弧の上端にあたる物質点の番号。先端の後に現れる Z の最初の極小点を探し、
        # その点から最深点までの間で最も高い点を選ぶ。
        k = i_t
        while k < i_d and q[k + 1, 1] <= q[k, 1]:
            k += 1
        self.i_armpit = int(k + np.argmax(q[k:i_d + 1, 1])) if k < i_d else int(i_t)

        self.n_frames = int(WP["n_frames"])
        self.x_c_final = float(q[self.i_c, 0])
        self._tau_table = None

        height_keys = np.asarray(WP["height_keyframes_H"], dtype=np.float64)
        if (height_keys.ndim != 2 or height_keys.shape[1] != 2 or height_keys.shape[0] < 2
                or not np.isfinite(height_keys).all() or height_keys[0, 0] != 1
                or height_keys[-1, 0] != self.n_frames or np.any(np.diff(height_keys[:, 0]) <= 0)
                or np.any(np.diff(height_keys[:, 1]) < 0) or height_keys[0, 1] <= 0):
            raise ValueError("height_keyframes_H にはフレーム1から n_frames まで単調増加する有限のフレーム・高さの組が必要です")
        if abs(float(height_keys[-1, 1]) - float(q[:, 1].max())) > 1e-8:
            raise ValueError("最後の高さの指定値は最終断面の峰の高さと正確に一致する必要があります")
        self.height_keys = height_keys
        widths = np.diff(height_keys[:, 0])
        secants = np.diff(height_keys[:, 1]) / widths
        slopes = np.zeros(height_keys.shape[0], dtype=np.float64)  # 両端では変化速度を0にする。
        for i in range(1, len(slopes) - 1):
            if secants[i - 1] <= 0 or secants[i] <= 0:
                continue
            w1, w2 = 2.0 * widths[i] + widths[i - 1], widths[i] + 2.0 * widths[i - 1]
            slopes[i] = (w1 + w2) / (w1 / secants[i - 1] + w2 / secants[i])
        self.height_slopes = slopes

    # ---- 変形パラメーター tau は [0, 1]。峰の標本点を X=0 に置く。
    def shape(self, tau):
        if tau >= 1.0:
            out = self.q.copy()
            out[:, 0] -= self.x_c_final
            return out
        w_a = _ramp_in((tau - self.lag_ang) / (1.0 - self.lag_ang))
        w_l = _ramp_in((tau - self.lag_len) / (1.0 - self.lag_len))
        psi = self.psi0 + w_a * self.dpsi
        ds = self.ds0 + w_l * (self.ds1 - self.ds0)
        x = np.concatenate([[0.0], np.cumsum(ds * np.cos(psi))])
        z = np.concatenate([[0.0], np.cumsum(ds * np.sin(psi))])
        s = np.concatenate([[0.0], np.cumsum(ds)])
        z = np.maximum(z - z[-1] * (s / s[-1]), 0.0)   # 両端は静水面に置き、それより下を作らない（仕様7d）。
        x = x - x[self.i_c]
        return np.stack([x, z], axis=1)

    def shape_rows(self, taus):
        """複数の変形パラメーターの shape() を一括計算する。(x, z) は各 (R, n_u)、峰は X=0。"""
        t = np.clip(np.asarray(taus, dtype=np.float64), 0.0, 1.0)[:, None]
        w_a = _ramp_in((t - self.lag_ang[None, :]) / (1.0 - self.lag_ang[None, :]))
        w_l = _ramp_in((t - self.lag_len[None, :]) / (1.0 - self.lag_len[None, :]))
        psi = self.psi0[None, :] + w_a * self.dpsi[None, :]
        ds = self.ds0[None, :] + w_l * (self.ds1 - self.ds0)[None, :]
        zero = np.zeros((t.shape[0], 1))
        x = np.concatenate([zero, np.cumsum(ds * np.cos(psi), axis=1)], axis=1)
        z = np.concatenate([zero, np.cumsum(ds * np.sin(psi), axis=1)], axis=1)
        s = np.concatenate([zero, np.cumsum(ds, axis=1)], axis=1)
        z = np.maximum(z - z[:, -1:] * (s / s[:, -1:]), 0.0)   # 仕様7d: 谷と静水面より下を作らない。
        x = x - x[:, [self.i_c]]
        done = t[:, 0] >= 1.0
        if done.any():
            x[done] = (self.q[:, 0] - self.x_c_final)[None, :]
            z[done] = self.q[:, 1][None, :]
        return x, z

    # ---- 時間関数
    def tau_onset(self):
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if pm.measure_profile(self.shape(mid))["overhanging"]:
                hi = mid
            else:
                lo = mid
        return hi

    def tau_of_frame(self, frame):
        if self._tau_table is None:
            WP = self.WP
            t_on = self.tau_onset()
            t_cu = t_on + float(WP["curl_start_fraction"]) * (1.0 - t_on)
            xk = np.array([1.0, float(WP["frame_overhang_onset"]), float(WP["frame_curl_start"]), float(self.n_frames)])
            yk = np.array([0.0, t_on, t_cu, 1.0])
            h = np.diff(xk)
            dl = np.diff(yk) / h
            mk = np.zeros(4)
            for i in (1, 2):                            # PCHIP 内部の傾きは加重調和平均で単調性を保つ。
                w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                mk[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
            mk[0] = 0.0                                 # 静止から始める。
            mk[3] = 0.0                                 # 停止へ向けて減速する（仕様M5）。
            self._tau_table = (xk, yk, mk, t_on, t_cu)
        xk, yk, mk, _a, _b = self._tau_table
        f = float(np.clip(frame, xk[0], xk[-1]))
        i = int(min(np.searchsorted(xk, f, side="right") - 1, 2))
        hh = xk[i + 1] - xk[i]
        t = (f - xk[i]) / hh
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return float(h00 * yk[i] + h10 * hh * mk[i] + h01 * yk[i + 1] + h11 * hh * mk[i + 1])

    def x_c_of_frame(self, frame):
        u = (float(np.clip(frame, 1, self.n_frames)) - 1.0) / (self.n_frames - 1.0)
        return self.x_c_final - float(self.WP["xc_travel_H"]) * (1.0 - u) ** float(self.WP["xc_travel_power"])

    def height_of_frame(self, frame):
        """波頭の変形とは別に制御する、H 単位の目標峰高。"""
        keys, slopes = self.height_keys, self.height_slopes
        f = float(np.clip(frame, keys[0, 0], keys[-1, 0]))
        i = min(int(np.searchsorted(keys[:, 0], f, side="right") - 1), len(keys) - 2)
        width = keys[i + 1, 0] - keys[i, 0]
        t = (f - keys[i, 0]) / width
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return float(h00 * keys[i, 1] + h10 * width * slopes[i] + h01 * keys[i + 1, 1] + h11 * width * slopes[i + 1])

    def height_gain(self, frame):
        if frame >= self.n_frames:
            return 1.0  # 原画から標本化した輪郭を厳密に保つ。
        raw = self.shape(self.tau_of_frame(frame))
        raw_height = float(raw[:, 1].max())
        if raw_height <= 0:
            raise ValueError("生成した断面の峰高が正の値ではありません")
        return self.height_of_frame(frame) / raw_height

    def profile(self, frame):
        """シーンの `frame` における断面。H 単位で、X はワールド座標。"""
        if frame >= self.n_frames:
            return self.q.copy()  # 原画に対応する最終形状を厳密に保ったまま静止させる。
        p = self.shape(self.tau_of_frame(frame))
        p[:, 1] *= self.height_gain(frame)
        p[:, 0] += self.x_c_of_frame(frame)
        return p


# ------------------------------------------------------------------------------------------ 3D 掃引
def v_layout(WP):
    """(y_H (n_v,), 絞り込み座標 d (n_v,)) を返す。d は中央の一定幅部分で1、外端で0。"""
    half, tl = float(WP["crest_half_length_H"]), float(WP["taper_length_H"])
    nc, nt = int(WP["n_v_center"]), int(WP["n_v_taper"])
    d_side = np.linspace(1.0, 0.0, nt + 1)[1:]
    y_side = half + (1.0 - d_side) * tl
    y_c = np.linspace(-half, half, nc)
    y = np.concatenate([-y_side[::-1], y_c, y_side])
    d = np.concatenate([d_side[::-1], np.ones(nc), d_side])
    return y, d


LIFT_END_D = 0.8


def lift_clip_sections(profile_H, x_clip_target, d, under_branch=None):
    """輪郭を保ちながら側面を丸く絞る。絞り込み座標の二乗で高い峰を Y 方向に狭める。
    前に伸びた波頭は平面の切断壁へ潰さず、峰へ向かって縮める。
    波頭が後退する前に下面を持ち上げ、残る盛り上がりを静水面へなじませる。
    (X, Z) はそれぞれ (n_v, n_u)。"""
    d = np.asarray(d, dtype=np.float64) ** 2
    x, z = profile_H[:, 0], profile_H[:, 1]
    z_lift = z.copy()
    if under_branch is not None and int(under_branch[1]) > int(under_branch[0]):
        i_t, i_d = int(under_branch[0]), int(under_branch[1])
        z_lift[i_t:i_d + 1] = np.maximum.accumulate(z[i_t:i_d + 1][::-1])[::-1]
    x_max = x.max()
    w_lift = _smooth((1.0 - d) / (1.0 - LIFT_END_D))[:, None]
    qq = _smooth((LIFT_END_D - d) / (LIFT_END_D - 0.5))
    g = _smooth(d / 0.5)[:, None]
    c = (x_max - qq * (x_max - x_clip_target))[:, None]
    Zj = z[None, :] + w_lift * (z_lift - z)[None, :]
    x_crest = float(x[np.argmax(z)])
    head_fraction = np.clip((x - x_crest) / max(x_max - x_crest, 1e-8), 0.0, 1.0)
    X = x[None, :] - (x_max - c) * head_fraction[None, :]
    # 各行の切断線における上側の境界高さ。
    for j in np.nonzero(qq > 0.0)[0]:
        cj = c[j, 0]
        over = x > cj
        if over.any():
            k = int(np.argmax(x >= cj))
            if k > 0 and x[k] > x[k - 1]:
                z_top = z[k - 1] + (cj - x[k - 1]) / (x[k] - x[k - 1]) * (z[k] - z[k - 1])
            else:
                z_top = z[k]
            sel = over.copy()
            sel[:k] = False
            Zj[j] = np.where(sel, np.minimum(Zj[j], z_top), Zj[j])
    return X, Zj * g


# ------------------------------------------------------------------------------------------ 'regress' 方式の側面
def v_layout_regress(WP):
    """(y_H (n_v,), u (n_v,) = |y| / 半幅) を返す。u は中央行で0、両端で1。"""
    n_v = int(WP["n_v_center"]) + 2 * int(WP["n_v_taper"])
    half = float(WP["crest_half_length_H"])
    y = np.linspace(-half, half, n_v)
    return y, np.abs(y) / half


def _points_in_polygon(px, pz, poly, chunk=4000):
    """偶奇則を配列に一括適用する。px, pz は (N,)、poly は暗黙に閉じる (M, 2)。結果は bool (N,)。"""
    x0, z0 = poly[:, 0], poly[:, 1]
    x1, z1 = np.roll(x0, -1), np.roll(z0, -1)
    out = np.zeros(px.shape[0], dtype=bool)
    dz = np.where(z1 == z0, 1e-30, z1 - z0)
    for a in range(0, px.shape[0], chunk):
        X, Z = px[a:a + chunk, None], pz[a:a + chunk, None]
        cond = (z0[None, :] > Z) != (z1[None, :] > Z)
        xi = x0[None, :] + (Z - z0[None, :]) * (x1 - x0)[None, :] / dz[None, :]
        out[a:a + chunk] = (np.count_nonzero(cond & (X < xi), axis=1) % 2) == 1
    return out


def _nearest_on_polyline(px, pz, line, chunk=2000):
    a, b = line[:-1], line[1:]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-30)
    ox, oz = np.empty_like(px), np.empty_like(pz)
    for k in range(0, px.shape[0], chunk):
        P = np.stack([px[k:k + chunk], pz[k:k + chunk]], axis=1)
        t = np.clip(((P[:, None, :] - a[None, :, :]) * ab[None, :, :]).sum(2) / L2[None, :], 0.0, 1.0)
        Q = a[None, :, :] + t[:, :, None] * ab[None, :, :]
        d2 = ((Q - P[:, None, :]) ** 2).sum(2)
        j = np.argmin(d2, axis=1)
        sel = Q[np.arange(P.shape[0]), j]
        ox[k:k + chunk], oz[k:k + chunk] = sel[:, 0], sel[:, 1]
    return ox, oz


def regress_sections(motion, frame, WP, u, stats=None):
    """自然な側面。中央行から離れるほど、同じ運動の発達が遅い断面にする。
    変形量を減らすことで峰を低く、波頭の先端を短くし、肩には張り出しを作らない。
    両端では静水面まで下げ、X 方向に遅らせて三日月形の峰線を作る。
    次に各側面頂点を中央断面の内部へ収める。背面は水平方向に制限し、前面は
    多角形の内外判定と輪郭への投影を用いる。このため CAM_print から見た側面の
    輪郭は全フレームで中央断面と一致し、空洞を塞がない。
    (X, Z) はそれぞれ (n_v, n_u)、H 単位。"""
    tau_c = motion.tau_of_frame(frame)
    x_c = motion.x_c_of_frame(frame)
    u0, uk = float(WP["flank_plateau"]), float(WP["flank_height_start"])
    A = 1.0 - _smooth((u - u0) / (1.0 - u0)) ** float(WP["flank_development_power"])
    K = 1.0 - _smooth((u - uk) / (1.0 - uk))
    # 三日月形は波とともに発達する。低いうねりでは峰線が直線になる。
    # 中央の一定幅領域は中央行と同じで位置ずれがない。その外側では三日月形が発達する。
    D = (float(WP["flank_back_shift_H"]) * _smooth((u - u0) / (1.0 - u0)) ** float(WP["flank_back_shift_power"])
         * float(_smooth((tau_c - 0.25) / 0.5)))
    xr, zr = motion.shape_rows(tau_c * A)
    Z = zr * K[:, None] * motion.height_gain(frame)
    mid = int(np.argmin(u))
    same = u <= u0                                # 中央の一定幅領域には制限処理を適用しない。
    i_c, i_t, i_d = motion.i_c, motion.i_t, motion.i_d
    z_lo, z_hi = 0.04, 0.10                       # 判定対象の輪郭に現れる部分だけを制限する。

    # 中央断面の背面境界 x(z)。低い傾きでは手描き由来の揺らぎにより Z が厳密には単調でない。
    # 峰から背面へ向かう Z の累積最小値を安全側の包絡線に使い、一価かつ内部側に保つ。
    ker = np.exp(-0.5 * (np.arange(-24, 25) / 8.0) ** 2)
    ker /= ker.sum()
    zs_mid = np.convolve(np.pad(Z[mid], 24, mode="edge"), ker, mode="valid")   # 境界計算用に細かな揺らぎを除いた複製。
    zb = np.minimum.accumulate(zs_mid[:i_c + 1][::-1])[::-1]
    zb = zb + 1e-7 * np.arange(zb.size)                                       # 同じ高さが続かないよう厳密に増加させる。
    xb = xr[mid, :i_c + 1] + x_c
    Zb = Z[:, :i_c + 1]
    lim = np.interp(Zb, zb, xb)
    X = xr + x_c - D[:, None]
    pc = np.stack([X[mid], Z[mid]], axis=1)

    # 背面では、遅れる肩の部分が輪郭を内部から満たす。背面を原画輪郭にあたる中央断面へ制限する。
    # 押し戻しを波頭上部で消し、峰に折れ目を作らない。
    h_mid = float(Z[mid].max())
    push = (np.maximum(lim - X[:, :i_c + 1], 0.0) * _smooth((Zb - z_lo) / (z_hi - z_lo))
            * _smooth((0.97 * h_mid - Zb) / max(0.12 * h_mid, 1e-6))        # 平らな峰の頂部では x(z) が不安定。
            * _smooth(D / 0.04)[:, None])                                   # 遅れが小さい行は押し戻さない。
    push[same] = 0.0
    Xb = X[:, :i_c + 1] + push
    Xb[~same] = np.maximum.accumulate(Xb[~same], axis=1)      # 行内の頂点順を保ち、折り返しを避ける。
    X[:, :i_c + 1] = Xb
    fade = 1.0 - _smooth((motion.S1[i_c:i_t + 1] - motion.S1[i_c]) / max(motion.S1[i_t] - motion.S1[i_c], 1e-9))
    X[:, i_c + 1:i_t + 1] += (Xb[:, -1:] - (xr[:, [i_c]] + x_c - D[:, None])) * fade[None, 1:]

    # 前面下部（内側の弧とその下の前面）は中央断面の前面より後ろに水平方向で制限する。
    # 各頂点の高さを維持するため、行が滑らかで頂点が密集しない。
    # 境界 x_lim(z) は最深点より下の内側の弧／前面の安全側包絡線と、その上の最深点を通る鉛直線。
    # 波頭の下では中央断面の空洞境界（先端→最深点）より頂点が低い距離に応じて引き戻す。
    # これによりフレーム間で効果が突然切り替わらない。
    zc = pc[:, 1]
    mm = pm.measure_profile(pc)
    over = bool(mm["overhanging"])
    if over:
        # 測定で求めた特徴点ではなく、最終形状の固定された物質点番号を使う。最深点付近の内側の弧は
        # ほぼ鉛直なので、測定位置を使うとフレームごとに番号が揺れる。
        k_t, k_d = i_t, i_d
    else:
        k_t = k_d = int(np.argmax(zc))             # 張り出しがない場合、前面は峰から始まる。
    z_env = np.minimum.accumulate(zs_mid[k_d:]) - 1e-7 * np.arange(zs_mid.size - k_d)   # 厳密に減少させる。
    zf = z_env[::-1]
    xf = pc[k_d:, 0][::-1]
    Xf, Zf = X[:, i_c + 1:], Z[:, i_c + 1:]
    soft = _smooth((Zf - 0.004) / 0.02)
    # (b) 最深点の高さより下を内側の弧／前面の後ろへ収める。近い境界を用い、連続性を保つ。
    # 張り出しがない場合、境界は x(z) が不安定な平らな峰から始まる。
    # 張り出しがある場合は、鉛直で計算が安定し、規則 (c) と連続につながる最深点から始める。
    cap = 1.0 if over else _smooth((0.97 * zf[-1] - Zf) / max(0.12 * zf[-1], 1e-6))
    pull = np.maximum(Xf - np.interp(Zf, zf, xf), 0.0) * soft * (Zf <= zf[-1]) * cap
    if over:
        # 行ごとに2つの状態を扱い、内部に収めた位置がほぼ一致する場所だけで混合する。
        # 幹状の行（まだ張り出さない、または先端が出始めた行）には規則 (c) を適用する。
        # 最深点から内側の弧の上端までを上側の内弧の後ろへ寄せ、幹の中に隠す。
        # これらの行は自然な前面が空洞内の空間に出るため、完全に引き戻す必要がある。
        # 明確な先端を持つ行には規則 (d) を適用する。波頭の各頂点を中央断面の
        # 同じ物質点での境界（外向き法線）に照らして判定し、小さな張り出しと空洞を中央の内側に保つ。
        # 混合はその行で張り出しが始まる直後、先端が首の内部にある場所でだけ行う。
        # 2つの位置の間に空気の隙間がある段階では混合しない。
        i_a = motion.i_armpit
        tau_on = motion._tau_table[3]
        w_row = (1.0 - _smooth((tau_c * A - (tau_on + 0.02)) / 0.10))[:, None]
        seg = slice(i_c + 1, i_d + 1)
        tx = np.gradient(pc[:, 0])[seg]
        tz = np.gradient(zs_mid)[seg]
        tn = np.maximum(np.hypot(tx, tz), 1e-12)
        nx, nz = -tz / tn, tx / tn                                   # 中央断面の外向き（空気側）法線。
        dn = (X[:, seg] - pc[seg, 0][None, :]) * nx[None, :] + (Z[:, seg] - pc[seg, 1][None, :]) * nz[None, :]
        corr = np.maximum(dn, 0.0) * (1.0 - w_row)
        corr[same] = 0.0
        X[:, seg] -= corr * nx[None, :]
        Z[:, seg] -= corr * nz[None, :]
        Xf, Zf = X[:, i_c + 1:], Z[:, i_c + 1:]
        soft = _smooth((Zf - 0.004) / 0.02)
        az = np.minimum.accumulate(zs_mid[i_a:i_d + 1]) - 1e-7 * np.arange(i_d + 1 - i_a)      # 内弧上端→最深点へ単調減少。
        x_arc = np.interp(Zf, az[::-1], pc[i_a:i_d + 1, 0][::-1])
        pull_c = np.maximum(Xf - x_arc, 0.0) * soft * (Zf > zf[-1]) * (Zf < float(az[0])) * w_row
        pull = np.maximum(Xf - np.interp(Zf, zf, xf), 0.0) * soft * (Zf <= zf[-1]) * cap + pull_c
    pull[same] = 0.0
    Xn = Xf - pull
    lo = i_d - (i_c + 1)
    Xn[~same, lo:] = np.minimum.accumulate(Xn[~same][:, lo:][:, ::-1], axis=1)[:, ::-1]   # 頂点順を保つ。
    X[:, i_c + 1:] = Xn

    # 中央断面の根元より前では側面を平らな水面にし、谷より前に隆起を作らない。
    k_foot = k_d + int(np.argmax(pc[k_d:, 1] <= 0.004)) if (pc[k_d:, 1] <= 0.004).any() else pc.shape[0] - 1
    flat = 1.0 - _smooth((X[:, i_d:] - (pc[k_foot, 0] - 0.10)) / 0.10)
    flat[same] = 1.0
    Z[:, i_d:] *= flat
    n_out, max_move = int(np.count_nonzero(pull > 1e-9)), float(pull.max())
    if stats is not None:
        stats.append((frame, n_out, max_move, float(push.max())))
    return X, Z


def grid_faces(n_u, n_v):
    j, i = np.meshgrid(np.arange(n_v - 1), np.arange(n_u - 1), indexing="ij")
    a = (j * n_u + i).ravel()
    return np.stack([a, a + n_u, a + n_u + 1, a + 1], axis=1)       # 法線は上向き／外向き。


def frame_vertices(motion, frame, y, d, H, state=None):
    """1フレーム分のワールド頂点 (n_v * n_u, 3) をメートル単位で返す。
    `state` は平滑化した制限位置を保持する。flank_mode が 'regress'（既定値）の場合、
    d は v_layout_regress の側面座標 u。'lift_clip' の場合は絞り込み座標。"""
    if str(motion.WP.get("flank_mode", "regress")) == "regress":
        stats = state.setdefault("stats", []) if state is not None else None
        X, Z = regress_sections(motion, frame, motion.WP, d, stats)
        mid = int(np.argmin(d))
        p = np.stack([X[mid], Z[mid]], axis=1)
        Y = np.repeat(y[:, None], X.shape[1], axis=1)
        return np.stack([X * H, Y * H, Z * H], axis=-1).reshape(-1, 3), p, None
    p = motion.profile(frame)
    m = pm.measure_profile(p)
    lm = m["landmarks"]
    if m["overhanging"]:
        ub = [int(lm["head_tip"]["index"]), int(lm["inner_deepest"]["index"])]
        xt = float(lm["inner_deepest"]["H"][0])
    else:
        ub = None
        xt = float(lm["theta_point"]["H"][0])
    xt_rel = xt - float(p[motion.i_c, 0])                           # 峰の標本点に対する相対位置にして時間方向に滑らかにする。
    if state is not None:
        prev = state.get("xt_rel")
        if prev is not None:
            xt_rel = prev + float(np.clip(xt_rel - prev, -0.012, 0.012))   # 変化速度を制限し、側面の跳びを避ける。
        state["xt_rel"] = xt_rel
    X, Z = lift_clip_sections(p, xt_rel + float(p[motion.i_c, 0]), d, ub)
    Y = np.repeat(y[:, None], p.shape[0], axis=1)
    V = np.stack([X * H, Y * H, Z * H], axis=-1).reshape(-1, 3)
    return V, p, m


def polyline_self_intersections(p):
    """隣接しない線分同士の交差数を返す。計算量は O(n^2)、n は約420。"""
    a, b = p[:-1], p[1:]
    n = len(a)
    r = b - a

    def cross(u, v):
        return u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]

    qp = a[None, :, :] - a[:, None, :]
    rxs = cross(r[:, None, :], r[None, :, :])
    t = cross(qp, r[None, :, :]) / np.where(rxs == 0, np.nan, rxs)
    u = cross(qp, r[:, None, :]) / np.where(rxs == 0, np.nan, rxs)
    hit = (t > 1e-9) & (t < 1 - 1e-9) & (u > 1e-9) & (u < 1 - 1e-9)
    idx = np.arange(n)
    hit &= np.abs(idx[:, None] - idx[None, :]) > 1
    return int(np.count_nonzero(hit) // 2)
