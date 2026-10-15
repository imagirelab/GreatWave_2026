# -*- coding: utf-8 -*-
"""FLIP49：周期の波で大きな細い巻き波を何度も出す 3D の水槽（PER49）の道具が共に使う物（numpy だけ。hython からも py -3.10 からも読む）。
2026-10-15 新しく書いた（周期の波の計画を実装する役、Claude）。flip45〜flip48 のファイルは一つも書き換えない。読むだけの物：
  g48_common（flip48。置き場所の定数・箱 box48・FLIP48 の海底 bed_z・bed_grad・bed_spec。既存の海底はここを通して 1 bit も違わずに使う）
  g46_common（flip46。g48_common 経由：hython のパス・2 進の箱・コマの数・優先度・待ち合わせ）
  g47_sfwave（flip47。流れ関数の規則波 solve・eta・vel・table・highest_H）
計画：指導教員の Q52（「一つの波ができればよいわけではなく、大波が定期的に現れるような状態が作れる方法を検討してください。」）に、
  規則的なうねり（流れ関数の波 T 12 s・H 7.5 m、水深 17 m）を固定した海底に入れ、同じ所で何度も大きな細い巻き波を出す方法で答える。
  海底 PG12s：集める所（先細りの sech² の尾根、1:10 で 17 → 12 m）と崩す所（12 m から 1:2.5 の段で礁の上 1.7 m。|y| ≤ 12 m で等深線がまっすぐ）を
  分け（C3B の決まり）、礁の上 20 m の先は 1:2 で水深 6 m の礁湖へ下げて横の深い所へ水を返す（閉じた池にしない）。
  決まり（P1〜P5・PER1〜PER5・H・D2 の決まり・2 段目の引き金・原画に最も近いコマの決まり）は Unity/Build/FLIP49/plan/plan_frozen.json に凍らせる
  （g49_pcfg.py freeze）。

座標は FLIP48 と同じ（計画の x＝波の進む向き・x = 0 が上流の壁、y＝横・y = 0 が対称の面、z＝上・静かな水面 0、平らな海底 −17 m。
Houdini の中は上が y・横が z。Houdini = 計画 + o）。

海底（bed_z・bed_grad）：
  - FLIP49 の新しい項（礁の段 pg_hL > 0、頂の平ら b_end > 0、礁湖 x_back < 1e8）がどれも無ければ、g48_common.bed_z・bed_grad をそのまま呼ぶ
    （R0〜R4・C3 の海底は 1 bit も違わない。g49_pcfg.py check が R1・R2b・R3・R4・C3 の cfg で np.array_equal を確かめる）。
  - 新しい項があれば U3 の u3_beds.depth（Unity/Build/FLIP48/diag/U3_bed、読むだけ）と同じ式・同じ順：
      y_e = max(|y| − b(x), 0)、b(x) = b_end·clip((x − xb1)/(xb2 − xb1), 0, 1)
      k(x) = k + (k_end − k)·clip((x − xk1)/(xk2 − xk1), 0, 1)
      R(x)：u = x − x_toe、u ≤ 0 で 0、u ≤ u_L = (h0 − pg_hL)·s までは u/s、その先 (h0 − pg_hL) + (u − u_L)/pg_s2（1:pg_s2 は軸の外でも続く）
      d1 = max(h_r, h0 − R(x) sech²(k(x) y_e/h0))（h_r = shelf_h）
      溝（ch_h > 0、g48 と同じ式）：w = ½(1 + tanh((|y| − ch_y0)/ch_w))·clip((x − ch_x0)/ch_lx, 0, 1)、d2 = d1(1 − w) + max(d1, ch_h) w
      礁湖：x > x_back で d = max(d2, min(h_lag, h_r + (x − x_back)/s_back))
    g48 の段（s1・dL・s2）と新しい項を同時に使うことはしない（止める）。
"""
import os, sys, math, json, hashlib

sys.dont_write_bytecode = True
TOOLS48 = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48"
TOOLS47 = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47"
for _p in (TOOLS48,):
    if _p not in sys.path:
        sys.path.append(_p)           # 後ろに足す（flip49 の名前が先に見つかるように）
import g48_common as G48               # noqa: E402  読むだけ（変えない）
from g48_common import (REPO, HY, FFMPEG, G, H0, FPS, Z_BOTTOM, H_BOX, Z_TOP, is_binary_exact, check_dp, sha256_file, rup,   # noqa: E402,F401
                        box48, frames_for, t_of_frame, unthrottle_self, rss_gb, hython_running, wait_no_hython, keep_awake, free_gb)

TOOLS = REPO + "/Tools/GWWaveGen/flip49"
B49 = REPO + "/Unity/Build/FLIP49"
HIP = REPO + "/Houdini/FLIP49/g49_tank.hiplc"
PLAN_DIR = B49 + "/plan"
PLAN_FROZEN = PLAN_DIR + "/plan_frozen.json"
PLAN_COPY48 = REPO + "/Unity/Build/FLIP48/plan/plan_P_frozen.json"     # 同じバイトの写し（タスクの書いた置き場所。本体は PLAN_FROZEN）
U3_DIR = REPO + "/Unity/Build/FLIP48/diag/U3_bed"                      # U3 の海底の式（u3_beds.py。読むだけ）
SCRATCH_U4 = B49 + "/screen_u4"                                         # U4 の下見の数（2026-10-15 に会話の一時置き場から Build/FLIP49 へ移した）
SCREEN_JSON = ("u3_PGs_ledge10_s40__dx1__h_L12__x_toe180.25__xb1200__xb2230.json",      # PG12s、格子 1 m（主の下見）
               "u3_PGs_ledge10_s40__h_L12__x_toe180.25__xb1200__xb2230.json",           # PG12s、格子 2 m
               "u3_PG_ledge10__ch_h0__L_ex70__dx1__h_L12__x_toe220.25__xb1240__xb2270.json")   # ずらさない双子（Lx 400）
CT_NODE = "/obj/G49_SETUP/CTRL"

# ------------------------------------------------------------------ 定数（理由は plan_frozen.json の design と honesty）
LX = 360.0                     # 箱の長さ（m）【選び】
W_MAIN = 85.0                  # 3D の半幅（m）。y = 85 m は壁 → 170 m ごとに礁が並ぶのと同じ【選び】
W_STRIP = 6.0                  # 準 2D の板の半幅（m）
T_WAVE = 12.0                  # うねりの周期（s）【選び】
H_WAVE = 7.5                   # うねりの波高（m、水深 17 m の平らで）【選び】
SF_N = 40                      # 流れ関数の項の数
X_P = 80.0                     # 入口の目標の位相の基準 x_p（m）。U3 の下見（x_ref 80 m）と同じにして、その巻き始めの時刻の見込み 37 + 12k s を使えるように【選び】
IN_X1 = 100.0                  # 入口の帯の終わり（m）= 0.67 L【選び】
WALL_TAPER = 20.0              # 入口の目標を上流の壁の近くで 0 へ落とす長さ（m）【選び】
RAMP_S = 24.0                  # 始めのなだらかさ（半余弦、s）= 2 T【選び】
EX_X0 = 290.0                  # 出口の帯（スポンジ）の始まり（m）。帯 70 m ≈ 0.47 L【選び】
EX_SIGMA = 1.41                # スポンジの σmax（1/s）。w = 1 − exp(−σ χ² dt)（FLIP45 ex_mode 0 の形）。2026-10-15 見直し：FLIP45 の 2.37 は
                               # T 7 s・帯 36 m（0.5 λ）の最適で、T 12 s・水深 17 m・帯 70 m では跳ね返り 0.166（S0b の門 Kr ≤ 0.1 を越える）。
                               # 同じ理論（Perić & Abdel-Maksoud 2018 の 1 次元、FLIP45 r45_gen_numbers.reflection）で 70 m の最適 1.41 → 0.046
                               # （水深 6 m の礁湖 0.073、T 10 s 0.044）【計算】
EX_SIGMA_THEORY = dict(sigma_old=2.37, CR_old_T12_h17=0.166, CR_old_T12_h6=0.093, sigma=1.41, CR_T12_h17=0.046, CR_T12_h6=0.073, CR_T10_h17=0.044,
                       band_m=70.0, source="Perić & Abdel-Maksoud 2018 1D theory as coded in flip45/r45_gen_numbers.reflection (reproduces FLIP45 CR 0.037 for 36 m, sigma 2.37, T 7 s, h 20 m)")
EX_POW = 2.0
VOL_X = (110.0, 285.0)         # 水の量の直し（段 A）の発散を置く窓（両方の帯の外）【選び】
VOL_TAU = 4.0                  # 段 A の時定数（s）
VOL_DMAX = 0.004               # 段 A の目標の発散の上限（1/s）
VOL_TCAP = 1.5                 # V0 = 1.0〜1.5 s の平均
VOL_MEASURE = "column"         # 段 A・B の V の読み。2026-10-15 S0a の虫探しの後に 'sdf'（凍らせた元の読み：surface の SDF の重み）から
                               # 'column'（一番上の水面 − 海底の柱の高さの和）へ。平らな海底の静かな水（帯あり・段 A）で 'sdf' は直しの発散を入れると
                               # 上がり続け、直しが走った（30 s で直しの量 −112 m³、柱の量 −19 m³、窓の流れ 0.17 m/s）【測定】。計画の補い：
                               # Unity/Build/FLIP49/plan/amendments.jsonl（凍らせた計画の判定の数は変えていない）
HOLD_X = (20.0, 95.0)          # 段 B：帯の芯（水面を保つ所。発散もここに置く）
HOLD_TI = 300.0                # 段 B の積分の時間（s）≥ 4 × 閉じた水槽の静振 56〜66 s【計算】
PROBE_C = (100.0, 110.0)       # 段 C：Sommerfeld の項の水面を読む所
GAUGE_X = (110.0, 128.0, 160.0)   # 波高計（18 m = 0.12 L で Goda & Suzuki の分け）
GAUGE_Y = (0.5, 80.0)          # 波高計の行（真ん中・横の端）
LEVEL_GUARD_M = 5.0            # 水面の見張り（1 m は FLIP47 P1c の打ち上げで誤って止めた）
T_JUDGE = 45.0                 # 判定する崩れ：真ん中の巻き始めが t ≥ 45 s【選び】
X_P1_MAX = 285.0               # P1 の x の上限（出口の帯の 5 m 手前）【選び：凍らせた 330 m を締めた】
SIDE_BAND = (70.0, 84.0)       # P4a の横の端の帯
X_CREST_MIN = 150.0            # 頂を探す x の始まり（次の波は入口の帯の出口 ≈ 90〜115 m にいる）

# 平均の水面の所（計画の座標。x0・x1・|y| の下・上。どれも 1 周期の平均を判定・解析で使う。lvl_reg の 5 つの所は別に残す）
LEVEL_REGIONS = [
    ("band_core", 20.0, 95.0, 0.0, 1e9),
    ("probe_c", PROBE_C[0], PROBE_C[1], 0.0, 1e9),
    ("flat", 110.0, 160.0, 0.0, 1e9),
    ("window", VOL_X[0], VOL_X[1], 0.0, 1e9),
    ("ledge_front", 215.0, 225.0, 0.0, 1e9),
    ("reef_flat", 258.0, 274.0, 0.0, 10.0),
    ("lagoon", 300.0, 320.0, 0.0, 20.0),
    ("side", 240.0, 260.0, 70.0, 84.0),
    ("asym_centre", 110.0, 160.0, 0.0, 10.0),
    ("asym_side", 110.0, 160.0, 75.0, 85.0),
]

# ------------------------------------------------------------------ 海底 PG12s（U3 の PGs_ledge10_s40 の段の足を 10 → 12 m、頂の平らと先細りをそろえた）
PG12S = dict(k=0.35, x_toe=180.25, s=10.0, h0=H0, on=True, shelf_h=1.7, k_end=1.0, xk1=200.0, xk2=256.0,
             ch_y0=55.0, ch_w=4.0, ch_h=0.0, ch_x0=150.0, ch_lx=40.0, s1=0.0, dL=0.0, s2=0.0,
             pg_hL=12.0, pg_s2=2.5, b_end=12.0, xb1=200.0, xb2=230.0, x_back=276.0, s_back=2.0, h_lag=6.0)
# U3 の名前（u3_beds.depth の引数。check が 1e-9 m で比べる）
PG12S_U3 = dict(k=0.35, k_end=1.0, xk1=200.0, xk2=256.0, ch_h=0.0, x_toe=180.25, h_L=12.0, s2=2.5, b_end=12.0, xb1=200.0, xb2=230.0,
                x_back=276.0, s_back=2.0, h_lag=6.0)
NEW_DEFAULTS = dict(pg_hL=0.0, pg_s2=0.0, b_end=0.0, xb1=200.0, xb2=230.0, x_back=1e9, s_back=2.0, h_lag=6.0)
BED48_KEYS = ("k", "x_toe", "s", "h0", "on", "shelf_h", "k_end", "xk1", "xk2", "ch_y0", "ch_w", "ch_h", "ch_x0", "ch_lx", "s1", "dL", "s2")


def pg_axis(spec=None):
    """準 2D の板（横に一様）：真ん中の断面の海底（k 0・先細りなし → sech²(0) = 1 がどの y でも）。"""
    sp = dict(spec or PG12S)
    sp.update(k=0.0, k_end=None)
    return sp


def flat_spec():
    return dict(PG12S, on=False)


def is_new(spec):
    """FLIP49 の新しい項を使うか。"""
    return bool((spec.get("pg_hL") or 0.0) > 0.0 or (spec.get("b_end") or 0.0) > 0.0 or (spec.get("x_back") if spec.get("x_back") is not None else 1e9) < 1e8)


def _split(spec):
    s48 = {k: spec[k] for k in BED48_KEYS if k in spec}
    new = dict(NEW_DEFAULTS)
    new.update({k: spec[k] for k in NEW_DEFAULTS if k in spec})
    return s48, new


def _b_of_x(x, n):
    import numpy as np
    if n["b_end"] > 0:
        r = (x - n["xb1"]) / max(n["xb2"] - n["xb1"], 1e-9)
        return n["b_end"] * np.clip(r, 0.0, 1.0), np.where((r > 0.0) & (r < 1.0), n["b_end"] / max(n["xb2"] - n["xb1"], 1e-9), 0.0)
    return 0.0, 0.0


def _rise2(x, s48, n):
    """u3_beds._rise と同じ 2 段の上り R と R'（1:s で水深 pg_hL まで、その先 1:pg_s2 がずっと）。"""
    import numpy as np
    u = x - s48["x_toe"]
    s1 = s48["s"]; s2 = n["pg_s2"] or 0.0; hL = n["pg_hL"] or 0.0
    if s2 > 0 and hL > s48["shelf_h"]:
        uL = (s48["h0"] - hL) * s1
        R = np.where(u <= 0, 0.0, np.where(u <= uL, u / s1, (s48["h0"] - hL) + (u - uL) / s2))
        Rp = np.where(u <= 0, 0.0, np.where(u <= uL, 1.0 / s1, 1.0 / s2))
        return R, Rp
    return np.maximum(u, 0.0) / s1, np.where(u > 0.0, 1.0 / s1, 0.0)


def _k_of_x(x, s48):
    import numpy as np
    k = s48["k"]; ke = s48.get("k_end")
    if ke is None or ke < 0:
        return k, 0.0
    r = (x - s48["xk1"]) / (s48["xk2"] - s48["xk1"])
    return k + (ke - k) * np.clip(r, 0.0, 1.0), np.where((r > 0.0) & (r < 1.0), (ke - k) / (s48["xk2"] - s48["xk1"]), 0.0)


def _check_combo(s48, n):
    if (s48.get("s1") or 0.0) > 0.0:
        raise ValueError("g48 の段（s1・dL・s2）と FLIP49 の新しい項（pg_hL・b_end・x_back）は同時に使わない")


def bed_z(x, y_lat=0.0, **spec):
    """海底の高さ（静かな水面 0、上向き）。新しい項が無ければ g48_common.bed_z そのもの。"""
    import numpy as np
    s48, n = _split(spec)
    if not is_new(spec):
        return G48.bed_z(x, y_lat, **s48)
    _check_combo(s48, n)
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y_lat, dtype=np.float64)
    if not s48.get("on", True):
        return np.full(np.broadcast(x, y).shape, -float(s48["h0"]))
    h0 = s48["h0"]
    kk, _ = _k_of_x(x, s48)
    b, _ = _b_of_x(x, n)
    ye = np.maximum(np.abs(y) - b, 0.0)
    sh = 1.0 / np.cosh(kk * ye / h0)
    R, _ = _rise2(x, s48, n)
    d = np.maximum(s48["shelf_h"], h0 - R * sh * sh)
    if (s48.get("ch_h") or 0.0) > 0:
        w, _, _ = G48._channel_w(x, y, s48["ch_y0"], s48["ch_w"], s48["ch_x0"], s48["ch_lx"])
        d = d * (1.0 - w) + np.maximum(d, s48["ch_h"]) * w
    if n["x_back"] < 1e8:
        lag = np.minimum(n["h_lag"], s48["shelf_h"] + np.maximum(x - n["x_back"], 0.0) / n["s_back"])
        d = np.where(x > n["x_back"], np.maximum(d, lag), d)
    return -d


def bed_grad(x, y_lat=0.0, **spec):
    """d bed_z/dx・d bed_z/dy。新しい項が無ければ g48_common.bed_grad そのもの。新しい項の式（VEX の bedgrad_pg と同じ）：
    ∂d/∂x = −(R' S − 2 R S tanh(a) ∂a/∂x)、∂d/∂y = 2 R S tanh(a) ∂a/∂y、a = k(x) y_e/h0、∂a/∂x = (k' y_e + k ∂y_e/∂x)/h0、
    ∂y_e/∂x = −b'(x)、∂y_e/∂y = sign(y)（|y| > b の所。中は 0）。礁の上（d ≤ h_r）は 0。溝は g48 と同じ混ぜ方、礁湖は 1/s_back（深さの上限で 0）。"""
    import numpy as np
    s48, n = _split(spec)
    if not is_new(spec):
        return G48.bed_grad(x, y_lat, **s48)
    _check_combo(s48, n)
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y_lat, dtype=np.float64)
    x, y = np.broadcast_arrays(x, y)
    if not s48.get("on", True):
        return np.zeros(x.shape), np.zeros(x.shape)
    h0 = s48["h0"]; hr = s48["shelf_h"]
    b, db = _b_of_x(x, n)
    ay = np.abs(y)
    out_ = (ay > b).astype(np.float64)
    ye = np.maximum(ay - b, 0.0)
    dye_dx = -db * out_; dye_dy = np.sign(y) * out_
    kk, dk = _k_of_x(x, s48)
    a = kk * ye / h0
    sh = 1.0 / np.cosh(a); S = sh * sh; th = np.tanh(a)
    R, Rp = _rise2(x, s48, n)
    dep = h0 - R * S
    da_dx = (dk * ye + kk * dye_dx) / h0; da_dy = kk * dye_dy / h0
    ddx = -(Rp * S - 2.0 * R * S * th * da_dx)
    ddy = 2.0 * R * S * th * da_dy
    flat = dep <= hr
    dep = np.where(flat, hr, dep); ddx = np.where(flat, 0.0, ddx); ddy = np.where(flat, 0.0, ddy)
    if (s48.get("ch_h") or 0.0) > 0:
        w, wx, wy = G48._channel_w(x, y, s48["ch_y0"], s48["ch_w"], s48["ch_x0"], s48["ch_lx"])
        deep = dep > s48["ch_h"]
        D2 = np.maximum(dep, s48["ch_h"])
        nx = ddx * (1.0 - w) + np.where(deep, ddx, 0.0) * w + (D2 - dep) * wx
        ny = ddy * (1.0 - w) + np.where(deep, ddy, 0.0) * w + (D2 - dep) * wy
        dep = dep * (1.0 - w) + D2 * w
        ddx, ddy = nx, ny
    if n["x_back"] < 1e8:
        raw = hr + np.maximum(x - n["x_back"], 0.0) / n["s_back"]
        lag = np.minimum(n["h_lag"], raw)
        on = (x > n["x_back"]) & (lag > dep)
        ddx = np.where(on, np.where(raw < n["h_lag"], 1.0 / n["s_back"], 0.0), ddx)
        ddy = np.where(on, 0.0, ddy)
    return -ddx, -ddy


def bed_sdf(x, z, y_lat, **spec):
    """VEX の bedsdf_out と同じ近似の SDF（海底の外で正）：(z − bed)/√(1 + |∇bed|²)。side_pad は使わない。"""
    import numpy as np
    gx, gy = bed_grad(x, y_lat, **spec)
    return (np.asarray(z, float) - bed_z(x, y_lat, **spec)) / np.sqrt(1.0 + gx * gx + gy * gy)


def bed_spec(cfg=None, parms=None):
    """cfg['bed']（あれば先）か parms（CTRL の名前）から bed_z の引数。g48_common.bed_spec の上に FLIP49 の新しい項（無ければ既定 = 無し）を足す。"""
    b = (cfg or {}).get("bed") if isinstance((cfg or {}).get("bed"), dict) else None
    P = parms if parms is not None else ((cfg or {}).get("parms") or {})
    sp = G48.bed_spec(cfg, parms)
    if b:
        for k_ in NEW_DEFAULTS:
            sp[k_] = float(b.get(k_, NEW_DEFAULTS[k_]))
    else:
        sp.update(pg_hL=float(P.get("pg_hL", 0.0)), pg_s2=float(P.get("pg_s2", 0.0)), b_end=float(P.get("b_end", 0.0)),
                  xb1=float(P.get("b_x1", NEW_DEFAULTS["xb1"])), xb2=float(P.get("b_x2", NEW_DEFAULTS["xb2"])),
                  x_back=float(P.get("lag_xb", 1e9)), s_back=float(P.get("lag_s", 2.0)), h_lag=float(P.get("lag_h", 6.0)))
    return sp


def bed_parms(spec):
    """bed_z の引数 → CTRL の parms（g48 の物と FLIP49 の新しい項）。"""
    p = dict(ridge_on=1.0 if spec.get("on", True) else 0.0, ridge_x0=float(spec["x_toe"]), ridge_k=float(spec["k"]), ridge_s=float(spec["s"]),
             shelf_h=float(spec["shelf_h"]), h0=float(spec.get("h0", H0)))
    p.update(G48.bed_parms(spec))
    n = dict(NEW_DEFAULTS); n.update({k: spec[k] for k in NEW_DEFAULTS if k in spec})
    p.update(pg_hL=float(n["pg_hL"]), pg_s2=float(n["pg_s2"]), b_end=float(n["b_end"]), b_x1=float(n["xb1"]), b_x2=float(n["xb2"]),
             lag_xb=float(n["x_back"]), lag_s=float(n["s_back"]), lag_h=float(n["h_lag"]))
    return p


def bed_kind(spec):
    if not spec.get("on", True):
        return "flat"
    if is_new(spec):
        k0 = spec.get("k", 0.0) == 0.0 and spec.get("k_end") is None
        return ("pg_reef_axis_strip" if k0 else "pg_reef") + ("_channel" if (spec.get("ch_h") or 0) > 0 else "")
    return G48.bed_kind(spec)


def bed_formula(spec):
    if not is_new(spec):
        return G48.bed_formula(spec) if spec.get("on", True) else "z_b = -h0 (flat)"
    f = ("z_b = -d; y_e = max(|y| - b(x), 0), b(x) = b_end*clip((x-xb1)/(xb2-xb1),0,1); k(x) = k + (k_end-k)*clip((x-xk1)/(xk2-xk1),0,1); "
         "R(x) = 0 (x <= x_toe), (x-x_toe)/s up to R = h0-pg_hL, then (h0-pg_hL) + (x-x_L)/pg_s2 (1:pg_s2 continues off the axis); "
         "d1 = max(h_r, h0 - R(x)*sech^2(k(x)*y_e/h0))")
    if (spec.get("ch_h") or 0) > 0:
        f += "; w = 0.5*(1+tanh((|y|-ch_y0)/ch_w))*clip((x-ch_x0)/ch_lx,0,1); d2 = d1*(1-w) + max(d1,ch_h)*w"
    if (spec.get("x_back") or 1e9) < 1e8:
        f += "; x > x_back: d = max(d, min(h_lag, h_r + (x-x_back)/s_back))"
    return f


def bed_record(spec, box=None):
    """cfg に書く海底の dict（bed_spec(cfg) で読み戻せる鍵）。"""
    d = {k: (None if spec.get(k) is None else (bool(spec[k]) if k == "on" else float(spec[k]))) for k in BED48_KEYS}
    d["h_sh"] = d["shelf_h"]
    d.update({k: float(spec.get(k, NEW_DEFAULTS[k])) for k in NEW_DEFAULTS})
    d["kind"] = bed_kind(spec)
    d["formula"] = bed_formula(spec)
    if box is not None:
        import numpy as np
        xs = np.arange(0.0, box["Lx"], 0.5); ys = np.arange(0.0, box["W"], 0.5)
        d["max_depth_m"] = float(-bed_z(xs[None, :], ys[:, None], **spec).min())
        d["min_depth_m"] = float(-bed_z(xs[None, :], ys[:, None], **spec).max())
        d["box_floor_zb_m"] = float(box["z_bottom"])
    if is_new(spec) and spec.get("on", True):
        d["x_edge_axis_m"] = edge_x(spec)
        d["x_foot_axis_m"] = foot_x(spec)
    return d


def foot_x(spec):
    """段の足（水深 pg_hL になる軸の x）。"""
    if (spec.get("pg_hL") or 0) <= 0:
        return None
    return float(spec["x_toe"] + (spec["h0"] - spec["pg_hL"]) * spec["s"])


def edge_x(spec, y=0.0, x0=150.0, x1=400.0):
    """軸（y）で水深が shelf_h + 0.05 m 以下になる最初の x（礁の縁。u3_beds.edge_x と同じ決まり）。"""
    import numpy as np
    xs = np.arange(x0, x1, 0.05)
    d = -bed_z(xs, np.full_like(xs, y), **spec)
    i = np.where(d <= spec["shelf_h"] + 0.05)[0]
    return float(xs[i[0]]) if len(i) else float("nan")


def u3_depth_fn():
    """U3 の u3_beds.depth（Unity/Build/FLIP48/diag/U3_bed、読むだけ）。"""
    if U3_DIR not in sys.path:
        sys.path.append(U3_DIR)
    import u3_beds as U3
    return U3.depth


# ------------------------------------------------------------------ 流れ関数の規則波（g47_sfwave、読むだけ）
def sfwave_mod():
    if TOOLS47 not in sys.path:
        sys.path.append(TOOLS47)
    import g47_sfwave as SFW
    return SFW


def sf_solve(h=H0, T=T_WAVE, H=H_WAVE, N=SF_N):
    """g47_sfwave.solve(h, T, H, N) と table（cfg の sf に入れる形）。"""
    SFW = sfwave_mod()
    s = SFW.solve(float(h), float(T), float(H), N=int(N))
    if not s["ok"]:
        raise SystemExit("流れ関数の解が解けない：%s" % s["msg"])
    tb = SFW.table(s)
    tb["u2_mean_mass_flux"] = float(s["u2"])
    tb["Hmax_fit"] = float(s["Hmax_fit"])
    tb["H_over_Hmax"] = float(H) / float(s["Hmax_fit"])
    tb["source"] = "g47_sfwave.solve(%g, %g, %g, N=%d)（Fenton の流れ関数法、平均の質量の流れ 0）" % (h, T, H, N)
    return s, tb


def sf_from_table(sf):
    """cfg の sf（table の形）→ g47_sfwave の eta・vel が受ける dict。"""
    import numpy as np
    return dict(h=float(sf["h"]), k=float(sf["k"]), c=float(sf["c"]), Ubar=float(sf["Ubar"]), B=np.asarray(sf["B"], float),
                E=np.asarray(sf["E"], float), L=float(sf["L"]), T=float(sf["T"]), H=float(sf["H"]))


def sf_tab_string(sf):
    """cfg の sf → CTRL の sf_tab（g47_tanklib.sf_tab_string と同じ並び：h k c Ub N B1..BN E0..EN、repr の桁で 64 ビット）。"""
    B = [float(v) for v in sf["B"]]; E = [float(v) for v in sf["E"]]
    if len(E) != len(B) + 1:
        raise ValueError("sf の E は B より 1 つ多い（E0..EN）：B %d、E %d" % (len(B), len(E)))
    head = [repr(float(sf["h"])), repr(float(sf["k"])), repr(float(sf["c"])), repr(float(sf["Ubar"])), str(len(B))]
    return " ".join(head + [repr(v) for v in B] + [repr(v) for v in E])


def smooth01(c):
    import numpy as np
    c = np.clip(c, 0.0, 1.0)
    return c * c * (3.0 - 2.0 * c)


def envelope(x, t, P):
    """入口の目標に掛ける E（VEX の relax_apply と同じ）：in_gain × walltaper(x) × rampT(t) × 組の包絡（set_P 0 なら 1）。"""
    import numpy as np
    x = np.asarray(x, float); t = np.asarray(t, float)
    L = float(P.get("wall_taper_m", WALL_TAPER))
    wt = smooth01((x - float(P.get("x0", 0.0))) / L) if L > 0 else 1.0
    R = float(P.get("ramp_s", RAMP_S))
    rp = (0.5 - 0.5 * np.cos(np.pi * np.clip(t / R, 0.0, 1.0))) if R > 0 else 1.0
    return float(P.get("in_gain", 1.0)) * wt * rp * set_env(x, t, P)


def set_env(x, t, P):
    """組の包絡（VEX の sf_setenv と同じ）。set_cg > 0 なら遅れた時刻 t − (x − x_p)/set_cg で読む（2 段目の組の時だけ）。"""
    import numpy as np
    Pp = float(P.get("set_P", 0.0))
    t = np.asarray(t, float) + 0.0 * np.asarray(x, float)
    if Pp <= 0:
        return np.ones_like(t)
    cg = float(P.get("set_cg", 0.0))
    tr = t - (np.asarray(x, float) - float(P.get("x_p", X_P))) / cg if cg > 0 else t
    up = float(P["set_up"]); fl = float(P["set_flat"]); dn = float(P["set_down"])
    tau = tr - Pp * np.floor(tr / Pp)
    return np.where(tau < up, 0.5 - 0.5 * np.cos(np.pi * tau / max(up, 1e-9)),
                    np.where(tau < up + fl, 1.0, np.where(tau < up + fl + dn, 0.5 + 0.5 * np.cos(np.pi * (tau - up - fl) / max(dn, 1e-9)), 0.0)))


def _sh_over_ch(a, b):
    import numpy as np
    return (np.exp(a - b) - np.exp(-a - b)) / (1 + np.exp(-2 * b))


def _ch_over_ch(a, b):
    import numpy as np
    return (np.exp(a - b) + np.exp(-a - b)) / (1 + np.exp(-2 * b))


def sf_vel(s, x, y, t=0.0):
    """g47_sfwave.vel の写し（numpy だけ。hython には scipy が無いので g47_sfwave を読めない。g49_pcfg.py check が g47_sfwave.vel と比べる）。"""
    import numpy as np
    x = np.atleast_1d(np.asarray(x, float)); y = np.atleast_1d(np.asarray(y, float))
    X = x - s["c"] * t; Y = y + s["h"]; k = s["k"]; h = s["h"]
    u = np.full(X.shape, s["c"] - s["Ubar"]); w = np.zeros(X.shape)
    for jj, Bj in enumerate(s["B"], 1):
        a = jj * k * np.maximum(Y, 0.0); b = jj * k * h
        u = u + jj * k * Bj * _ch_over_ch(a, b) * np.cos(jj * k * X)
        w = w + jj * k * Bj * _sh_over_ch(a, b) * np.sin(jj * k * X)
    return u, w


def sf_table_file(H=None, T=None):
    """x49_build.py が py -3.10 で解いて書く流れ関数の表（hython の場面の確かめが読む）。"""
    return B49 + "/_logs/sf_table_T%s_H%s.json" % (tag(T or T_WAVE), tag(H or H_WAVE))


def sf_target(x, y, t, sf, P, E=None):
    """入口の帯の目標（VEX の sfwave と同じ）：X = x − x_p − c t、η = Σ E_j cos(j k X)、Y = max(min(y, η) + h, 0) で u・w。
    返り値 (E η, E u, E w, η, E)。E を与えなければ envelope(x, t, P)。numpy だけ（hython でも動く）。"""
    import numpy as np
    s = sf_from_table(sf)
    x = np.atleast_1d(np.asarray(x, float)); y = np.atleast_1d(np.asarray(y, float)); t = np.atleast_1d(np.asarray(t, float))
    x, y, t = np.broadcast_arrays(x, y, t)
    xr = x - float(P.get("x_p", X_P))
    j = np.arange(len(s["E"]))
    X = xr - s["c"] * t
    eta = (s["E"][:, None] * np.cos(j[:, None] * s["k"] * X.ravel()[None, :])).sum(0).reshape(X.shape)
    ye = np.minimum(y, eta)
    u, w = sf_vel(s, xr.ravel(), ye.ravel(), t.ravel())
    u = u.reshape(X.shape); w = w.reshape(X.shape)
    EE = envelope(x, t, P) if E is None else np.broadcast_to(np.asarray(E, float), X.shape)
    return EE * eta, EE * u, EE * w, eta, EE


# ------------------------------------------------------------------ 粒子の数（場面の init_particles と同じ決まり、静かな水から）
def count_particles(spec, Lx, W, dp, zb=Z_BOTTOM, bed_gap=0.5, eta=0.0):
    """列 (ix+½)dp・(iz+½)dp、段 zb + (k+½)dp、海底 + bed_gap·dp ≤ 段 < η。返り値 (数, 水の体積 m³ = 数 × dp³)。"""
    import numpy as np
    xs = (np.arange(int(round(Lx / dp))) + 0.5) * dp
    ys = (np.arange(int(round(W / dp))) + 0.5) * dp
    n = 0
    for j0 in range(0, len(ys), 64):
        yy = ys[j0:j0 + 64]
        bed = bed_z(xs[None, :], yy[:, None], **spec) if spec else np.full((len(yy), len(xs)), zb)
        bed = np.broadcast_to(bed, (len(yy), len(xs)))
        k_lo = np.ceil((bed + bed_gap * dp - zb) / dp - 0.5 - 1e-9)
        k_hi = np.ceil((eta - zb) / dp - 0.5 - 1e-9)
        n += int(np.maximum(k_hi - np.maximum(k_lo, 0), 0).sum())
    return n, n * dp ** 3


# ------------------------------------------------------------------ 記録の印
def module_shas():
    out = {}
    for nm in ("g49_common.py", "g49_tanklib.py", "g49_run.py", "g49_build_tank.py", "g49_chain.py", "g49_pcfg.py", "g49_periodic_ana.py"):
        p = os.path.join(TOOLS, nm)
        out["flip49/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g48_common.py", "g48_analyze.py", "g48_peak_metrics.py"):
        p = os.path.join(TOOLS48, nm)
        out["flip48/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    p = os.path.join(TOOLS47, "g47_sfwave.py")
    out["flip47/g47_sfwave.py"] = sha256_file(p)[:16] if os.path.exists(p) else None
    return out


def guard_out49(path):
    """FLIP49 の置き場所の外には書かない。"""
    o = os.path.abspath(path).replace("\\", "/")
    if not (o.lower() + "/").startswith(B49.lower() + "/"):
        raise SystemExit("出力の置き場所 %s は Unity/Build/FLIP49 の外。書かない" % o)
    os.makedirs(o, exist_ok=True)
    return o


def tag(v):
    return ("%g" % v).replace(".", "p")
