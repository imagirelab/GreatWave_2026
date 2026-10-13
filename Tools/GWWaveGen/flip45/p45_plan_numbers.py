# -*- coding: utf-8 -*-
"""FLIP45 計画の数を出す（py -3.10 -I、numpy だけ。流体の計算はしない。Houdini も使わない）。

計画：Unity/Build/FLIP45/plan/plan_ja.md。この道具が出す数：Unity/Build/FLIP45/plan/plan_numbers.json。
3D の向きの集まり（Fochesato・Grilli・Dias 2007 の再現、向きの分け方の変化、同じ周期の扇を送り続けた時の繰り返し）の
入口の成分、仮の水槽（横の壁 ±300 m）の線形の場、窓の形、計算の並び・費用・置き場所・日付、判定の数、Unity での再生の大きさを出す。

読むもの（読むだけ。書き換えない。SHA-256 を出力の sources に書く）：
  Unity/Build/FLIP42/plan/plan_numbers.json          FLIP42 の水槽の大きさ（粒子の密度を出すため）
  Unity/Build/FLIP42/runs/{R1b,R2,R3,R4d}/ana.json   1 コマの秒、粒子の数、巻き始めのコマ、静かな水面のずれ
  Unity/Build/FLIP44/plan/plan_numbers.json          形の量（STUDY52 と同じ定義）の原画・R3・R4d の値と物差し
  Unity/Build/FLIP45/research/generation_numbers.json 帯の跳ね返りの理論の値（Perić & Abdel-Maksoud 2018 を斜めへ広げた物）
  Unity/Build/FLIP45/research/fochesato_linear.json   壁ありの線形の場（g 9.81 で出した物。照らし合わせだけ）
  Unity/Build/FLIP45/research/u_surfsize/run2/u_surfsize_result.json      面の大きさ（m² あたりの三角形、面を作る時間）
  Unity/Build/FLIP45/research/u_surfsize/run3_abc/u_surfsize_abc_result.json Alembic の 1 三角形のバイト

2026-10-12 07:20〜 見直し（plan/review_ja.md）を当てて直した所：入口の帯を造波板の下流（x 0〜36 m）に置き、目標を因果の
ある全部の形（消えていく形を含む）にし、始めを −2 s にした（H1）。帯の目標に掛ける壁のなだらかさを帯の厚さの 1/4 にし、
始めのなだらかさは使わない（H2）。海底を全部の粒子で箱の底 −20 m にした（M3）。X60 の領域を x 412 m まで延ばし、
横の帯の起こす所を 250 m まで、切り替えを 250〜280 m にした（M6）。V1h（CFL 半分の全長、粒子 0.5 m）と V4（横に広い窓の
F45、粒子 0.5 m）を足した（M4・M5）。X45 を 2 回目の報告に回した（M14）。置き場所の空きを 10⁹ バイトの GB で測り直した（L6）。
判定の数（criteria）に、同じ頂・前へ巻く・軸の外の巻き始め・入口の利得と条件・窓の前提・伝わる間の減り・長い波・帯に近い・
細かさの条件を足し、煙の試しの数（smoke）と途中保存の残し方（ckpt_rule）を出すようにした。

使い方：
  py -3.10 -I p45_plan_numbers.py            → plan_numbers.json（2 回走らせて同じ SHA-256 になることを確かめる）
  py -3.10 -I p45_plan_numbers.py --freeze   → plan_ja.md・plan_numbers.json・この道具・review_ja.md の SHA-256 を plan/plan_frozen.json に書く
                                               （作っていない別の者の見直しを当てた後、煙の試しの前に 1 回だけ。数は出し直さない）

数の種類：成分・線形の場は【計算】（ω² = g k tanh kh、g = 9.80665 は Houdini の重力の既定値）。
線形の場は Fochesato ら 2007 の水槽（幅 600 m、横は水を通さない壁、x = 0 の全幅に底で回る板の snake）を、横の余弦の形
cos(jπy/300 m) に分けて解く（Unity/Build/FLIP45/research/fochesato_ja.md §5、r45_fgd07_walled_linear.py と同じ解き方。
その道具は読み込むと走って書き出すので、関数をここへ写した）。立ち上げは tanh(t/T)（計画 §4 で決めた）。
費用は FLIP42 の記録からの【推定】で、3D の 1 コマの秒は測っていない（下見 V1 の全部の記録で測り直す。見直し M9）。
"""
import os, sys, json, math, hashlib, datetime
import numpy as np

# 優先度を「通常より下」にし、Windows の電力の抑え（EcoQoS）を使わないよう頼む（FLIP42・44 の決まり）
try:
    import ctypes
    from ctypes import wintypes

    class _PPTS(ctypes.Structure):
        _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]

    _k = ctypes.windll.kernel32
    _h = _k.GetCurrentProcess()
    _s = _PPTS(1, 0x1, 0x0)
    _k.SetProcessInformation(_h, 4, ctypes.byref(_s), ctypes.sizeof(_s))
    _k.SetPriorityClass(_h, 0x00004000)
except Exception:
    pass

ROOT = "G:/Unity/GreatWave_2026_Fresh"
OUTDIR = ROOT + "/Unity/Build/FLIP45/plan"
SRC = dict(
    plan42=ROOT + "/Unity/Build/FLIP42/plan/plan_numbers.json",
    ana_R1b=ROOT + "/Unity/Build/FLIP42/runs/R1b/ana.json",
    ana_R2=ROOT + "/Unity/Build/FLIP42/runs/R2/ana.json",
    ana_R3=ROOT + "/Unity/Build/FLIP42/runs/R3/ana.json",
    ana_R4d=ROOT + "/Unity/Build/FLIP42/runs/R4d/ana.json",
    plan44=ROOT + "/Unity/Build/FLIP44/plan/plan_numbers.json",
    gen45=ROOT + "/Unity/Build/FLIP45/research/generation_numbers.json",
    lin45=ROOT + "/Unity/Build/FLIP45/research/fochesato_linear.json",
    surf45=ROOT + "/Unity/Build/FLIP45/research/u_surfsize/run2/u_surfsize_result.json",
    abc45=ROOT + "/Unity/Build/FLIP45/research/u_surfsize/run3_abc/u_surfsize_abc_result.json",
)


def load(p):
    return json.load(open(p, encoding="utf-8"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def r(v, n=3):
    if isinstance(v, np.ndarray):
        return [r(x, n) for x in v.tolist()]
    if isinstance(v, (list, tuple)):
        return [r(x, n) for x in v]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.floating, float)):
        return float(round(float(v), n))
    if isinstance(v, (np.integer,)):
        return int(v)
    return v


# ------------------------------------------------------------------ 定数（Fochesato ら 2007 の刊行版 §3.2・§3.3）
G = 9.80665
FPS = 24.0
D = 20.0                 # 水深
OM = 0.8971              # 角振動数 Ω（rad/s）
T = 2 * math.pi / OM     # 周期 7.004 s
XF = 250.0               # 線形の焦点の x（y = 0）
LH = 300.0               # 仮の水槽の半分の幅（横の壁まで）
J = 60                   # 横の形の数（j = 0..J）
A_STROKE_F45 = 0.2       # 基準の例の板の振れの振幅（m）
TSCALE = math.sqrt(D / G)


def k_real(om, h=D):
    k = om * om / G
    for _ in range(80):
        f = G * k * math.tanh(k * h) - om * om
        df = G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2
        k -= f / df
    return k


def k_complex(om):
    om = np.asarray(om, dtype=complex)
    k = np.array([k_real(abs(w.real)) if abs(w.real) > 1e-6 else 1e-6 for w in om], dtype=complex)
    for _ in range(50):
        th = np.tanh(k * D)
        f = G * k * th - om * om
        df = G * th + G * k * D * (1 - th * th)
        k = k - f / df
    return k


def flap_F(k):
    kd = k * D
    return 4 * np.sinh(kd) * (1 - np.cosh(kd) + kd * np.sinh(kd)) / (kd * (np.sinh(2 * kd) + 2 * kd))


K0 = k_real(OM)
L0 = 2 * math.pi / K0
C0 = OM / K0
CG0 = C0 * 0.5 * (1 + 2 * K0 * D / math.sinh(2 * K0 * D))
F0 = float(flap_F(K0))


def stokes2_ratio(a):
    """一つの平らな波の Stokes 2 次の束縛の成分の振幅 ÷ 1 次の振幅（水深 20 m、周期 7 s）。"""
    kh = K0 * D
    return K0 * a / 4 * math.cosh(kh) * (2 + math.cosh(2 * kh)) / math.sinh(kh) ** 3


# ------------------------------------------------------------------ 入口の成分（計画 §4.2）
def theta_uniform(thmax, n=30):
    return np.linspace(-thmax, thmax, n)


th45 = theta_uniform(45.0)
A_STAR = float((A_STROKE_F45 * F0 / np.cos(np.radians(th45))).sum())     # 基準の例の線形の焦点の和（壁なしの和）


def case_uniform(name, thmax, ja):
    th = theta_uniform(thmax)
    w = 1.0 / np.cos(np.radians(th))
    a = A_STAR / (F0 * w.sum())                         # 板の振れ（全部同じ）。和を基準の例にそろえる
    A = a * F0 * w
    return dict(name=name, ja=ja, kind="uniform", theta=th, stroke=np.full_like(th, a), A=A,
                params=dict(theta_max_deg=thmax, n=30, stroke_m=a, sigma_theta_deg=thmax / math.sqrt(3)))


def case_cross(name, dtheta, sig, ja, n_per=15, nsig=1.5):
    mu = dtheta / 2
    tp = np.linspace(mu - nsig * sig, mu + nsig * sig, n_per)
    th = np.concatenate([-tp[::-1], tp])
    # 各群の成分は自分の群のガウスの重みだけを持つ（群ごとに等しい間隔で置くので、二つの群が重なる所では成分の数で密度が足される）
    wp = np.exp(-0.5 * ((tp - mu) / sig) ** 2)
    wgt = np.concatenate([wp[::-1], wp])
    A = A_STAR * wgt / wgt.sum()
    stroke = A * np.cos(np.radians(th)) / F0
    return dict(name=name, ja=ja, kind="cross", theta=th, stroke=stroke, A=A,
                params=dict(dtheta_deg=dtheta, sigma_group_deg=sig, n=2 * n_per, cut_nsigma=nsig,
                            sigma_total_deg=math.sqrt(sig ** 2 + mu ** 2)))


CASES = [
    case_uniform("F45", 45.0, "基準の例（Fochesato ら 2007 の水深 20 m・±45°）。30 成分を −45〜45° に一様、板の振れ 0.2 m"),
    case_uniform("F40", 40.0, "Fochesato ら 2007 の水深 20 m・±40°（表 1 に答えがある 2 つ目の例）。板の振れ 0.206 m（論文と同じく和 6.3 m）"),
    case_cross("X45", 45.0, 20.0, "二つの群が 45° で交わる（各群の中心 ±22.5°、各 σθ 20°、各群の中心から ±1.5σ で切る）"),
    case_cross("X60", 60.0, 20.0, "比べ：二つの群が 60° で交わる（各群の中心 ±30°、各 σθ 20°、±1.5σ で切る）"),
]
qj = np.arange(J + 1) * math.pi / LH


def proj(p):
    """cos(p y) を [−LH, LH] の cos(qj y) に分けた係数（j = 0..J）。"""
    I = LH * (np.sinc((p - qj) * LH / math.pi) + np.sinc((p + qj) * LH / math.pi))
    c = I / LH
    c[0] = I[0] / (2 * LH)
    return c


def modes(case):
    th = np.radians(case["theta"])
    pn = K0 * np.sin(th)
    psi = -K0 * XF * np.cos(th)
    C = np.array([proj(p) for p in pn])
    P = (case["stroke"][:, None] * C * np.cos(psi)[:, None]).sum(axis=0)
    Q = (case["stroke"][:, None] * C * np.sin(psi)[:, None]).sum(axis=0)
    return P, Q


def steady(P, Q, x, y, progressive_only=False):
    """ω = Ω の複素の振幅（壁あり）。progressive_only なら Ω で進む形（qj < k）だけ。"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    Z = np.zeros(np.broadcast(x, y).shape, dtype=complex)
    for P1, Q1, q1 in zip(P, Q, qj):
        if abs(P1) + abs(Q1) < 1e-14:
            continue
        if progressive_only and q1 >= K0:
            continue
        kx = np.sqrt(K0 * K0 - q1 * q1 + 0j)
        kx = np.conj(kx) if kx.imag != 0 else kx
        if kx.imag > 0:
            kx = -kx
        Z = Z + (P1 - 1j * Q1) * 1j * F0 * (K0 / kx) * np.exp(-1j * kx * x) * np.cos(q1 * y)
    return Z


# 交わる群の 2 例は、仮の水槽の y = 0 の定常の最大を基準の例と同じにそろえる（FLIP が受け取る同じ水槽の線形の頂で比べるため）
_XSP = np.arange(100.0, 340.01, 1.0)
_P, _Q = modes(CASES[0])
PEAK_F45 = float(np.abs(steady(_P, _Q, _XSP, 0.0)).max())
for _cs in CASES:
    if _cs["kind"] == "cross":
        _P, _Q = modes(_cs)
        _pk = float(np.abs(steady(_P, _Q, _XSP, 0.0)).max())
        _f = PEAK_F45 / _pk
        _cs["A"] = _cs["A"] * _f
        _cs["stroke"] = _cs["stroke"] * _f
        _cs["params"]["peak_before_scale_m"] = _pk
        _cs["params"]["scale_to_F45_walled_peak"] = _f

# 過渡（立ち上げ tanh(t/T)）。r45_fgd07_walled_linear.py の transient と同じ解き方（ラプラス変換で窓の折り返しを消す）
DT = 0.1
NT = 2 ** 15
TW = NT * DT
SIG = 10.0 / TW
TT = np.arange(NT) * DT
OMB = 2 * math.pi * np.fft.rfftfreq(NT, DT)
USE = (OMB >= 0.05) & (OMB <= 3.0)
OMC = OMB[USE] - 1j * SIG
KC = k_complex(OMC)
FC = flap_F(KC)
T_KEEP = TT <= 130.0 + 1e-9
TK = TT[T_KEEP]


def ramp(t):
    return np.tanh(t / T)


def transient(P, Q, x_eval):
    R = ramp(TT)
    damp = np.exp(-SIG * TT)
    keep_e = np.exp(SIG * TK)
    Sc = np.fft.rfft(R * np.cos(OM * TT) * damp)
    Ss = np.fft.rfft(R * np.sin(OM * TT) * damp)
    out = np.zeros((len(qj), len(x_eval), len(TK)))
    for j, (P1, Q1, q1) in enumerate(zip(P, Q, qj)):
        if abs(P1) + abs(Q1) < 1e-12:
            continue
        X = P1 * Sc + Q1 * Ss
        kx = np.sqrt(KC * KC - q1 * q1)
        kx = np.where(kx.imag > 0, -kx, kx)
        Hn = 1j * FC * KC / kx
        spec = np.zeros((len(x_eval), len(OMB)), dtype=complex)
        spec[:, USE] = X[USE][None, :] * Hn[None, :] * np.exp(-1j * np.outer(x_eval, kx))
        out[j] = np.fft.irfft(spec, n=NT, axis=1)[:, T_KEEP] * keep_e[None, :]
    return out


def first_cross(ser, level, tmin=0.0):
    i = np.where((np.abs(ser) >= level) & (TK >= tmin))[0]
    return float(TK[i[0]]) if len(i) else None


# 負の時刻（板が動き始める前）の目標。FFT の窓の終わりに折り返った所を t − TW に戻し、ラプラスの減衰を戻す（見直し H1）
TW_ALL = np.where(np.arange(NT) < NT // 2, TT, TT - TW)


def smooth01(c):
    c = np.clip(c, 0.0, 1.0)
    return c * c * (3.0 - 2.0 * c)


def band_precursor(P, Q, xs, ys, x_wall, y_wall, Lw, tmin=-40.0, tmax=6.0):
    """帯の目標（全部の横の形・全部の周波数、x > 0 で消えていく枝。壁のなだらかさを掛けた物）の水面を負の時刻まで出す。
    返す物：時刻（並べた物）と、その時刻の帯の中の |η| の最大。"""
    sel = (TW_ALL >= tmin) & (TW_ALL <= tmax)
    ts = TW_ALL[sel]
    o = np.argsort(ts)
    ts = ts[o]
    R = ramp(TT)
    damp = np.exp(-SIG * TT)
    Sc = np.fft.rfft(R * np.cos(OM * TT) * damp)
    Ss = np.fft.rfft(R * np.sin(OM * TT) * damp)
    e = np.zeros((len(xs), len(ys), len(ts)))
    for P1, Q1, q1 in zip(P, Q, qj):
        if abs(P1) + abs(Q1) < 1e-12:
            continue
        X = P1 * Sc + Q1 * Ss
        kx = np.sqrt(KC * KC - q1 * q1)
        kx = np.where(kx.imag > 0, -kx, kx)
        spec = np.zeros((len(xs), len(OMB)), dtype=complex)
        spec[:, USE] = X[USE][None, :] * (1j * FC * KC / kx)[None, :] * np.exp(-1j * np.outer(xs, kx))
        ej = np.fft.irfft(spec, n=NT, axis=1)[:, sel][:, o] * np.exp(SIG * ts)[None, :]
        e += ej[:, None, :] * np.cos(q1 * ys)[None, :, None]
    tap = smooth01((xs - x_wall) / Lw)[:, None] * smooth01((y_wall - ys) / Lw)[None, :]
    return ts, np.abs(e * tap[:, :, None]).max(axis=(0, 1))


def upstream_precursor(P, Q, x, ys, mode, tmin=-60.0, tmax=2.0):
    """選ばなかった案（造波板より上流 x < 0 に帯を置き、場を上流へ延ばす）の、t < 0 の目標の |η| の最大（y の中の最大）。
    mode "omega"：Ω で進む横の形（q_j < k）だけ、全部の周波数。mode "perfreq"：周波数ごとに進む成分（Re(k² − q²) > 0）だけ。"""
    sel = (TW_ALL >= tmin) & (TW_ALL <= tmax)
    ts = TW_ALL[sel]
    o = np.argsort(ts)
    ts = ts[o]
    R = ramp(TT)
    damp = np.exp(-SIG * TT)
    Sc = np.fft.rfft(R * np.cos(OM * TT) * damp)
    Ss = np.fft.rfft(R * np.sin(OM * TT) * damp)
    e = np.zeros((len(ys), len(ts)))
    idx_use = np.where(USE)[0]
    for P1, Q1, q1 in zip(P, Q, qj):
        if abs(P1) + abs(Q1) < 1e-12 or (mode == "omega" and q1 >= K0):
            continue
        X = P1 * Sc + Q1 * Ss
        k2 = KC * KC - q1 * q1
        kx = np.sqrt(k2)
        kx = np.where(kx.imag > 0, -kx, kx)
        use = np.ones(len(KC), bool) if mode == "omega" else (k2.real > 0)
        spec = np.zeros(len(OMB), dtype=complex)
        idx = idx_use[use]
        spec[idx] = X[idx] * (1j * FC * KC / kx)[use] * np.exp(-1j * kx[use] * x)
        ej = np.fft.irfft(spec, n=NT)[sel][o] * np.exp(SIG * ts)
        e += ej[None, :] * np.cos(q1 * ys)[:, None]
    m = np.abs(e).max(axis=0)
    w = lambda a, b: r(m[(ts >= a) & (ts < b)].max(), 3)
    return dict(max_t_m60_m40=w(-60, -40), max_t_m40_m20=w(-40, -20), max_t_m20_m10=w(-20, -10), max_t_m10_0=w(-10, 0),
                at_t0=r(m[np.argmin(np.abs(ts))], 3))


T0_PADDLE = -2.0                              # 造波板から解く窓（L1・L1w・L1x・L3）の始めの時刻（見直し H1。計画 §3.1）
XS = np.arange(0.0, 412.01, 2.0)              # y = 0 の線（造波板から 412 m まで。X60 の延ばした領域 L1x の端）
YW = np.arange(0.0, 144.01, 6.0)              # 窓 L2・L2w の静かさの確かめの y
case_out = {}
for cs in CASES:
    P, Q = modes(cs)
    th = cs["theta"]
    # 定常（y = 0）
    xs1 = np.arange(0.0, 412.01, 1.0)
    Z0 = np.abs(steady(P, Q, xs1, 0.0))
    ipk = int(np.argmax(Z0[100:])) + 100           # 造波板の近くの揺れを除き、x 100 m より先で最大を探す
    x_pk = float(xs1[ipk])
    # 帯の上の定常の振幅（見直し H1 の後：入口の帯は造波板の下流 x 0〜36 m（L3 は 0〜72 m）で、目標は全部の形の場。
    # 壁のなだらかさの所（帯の厚さの 1/4）を除いた所で数える）
    Xb, Yb = np.meshgrid(np.arange(9.0, 36.01, 1.5), np.arange(0.0, 108.01, 2.0), indexing="ij")
    band_L1 = np.abs(steady(P, Q, Xb, Yb))
    Xb3, Yb3 = np.meshgrid(np.arange(18.0, 72.01, 2.0), np.arange(0.0, 144.01, 2.0), indexing="ij")
    band_L3 = np.abs(steady(P, Q, Xb3, Yb3))
    Xs, Ys = np.meshgrid(np.arange(0.0, 200.01, 2.0), np.arange(72.0, 108.01, 2.0), indexing="ij")
    side_L1 = np.abs(steady(P, Q, Xs, Ys))
    Xs2, Ys2 = np.meshgrid(np.arange(0.0, 250.01, 2.0), np.arange(108.0, 144.01, 2.0), indexing="ij")
    side_L1w = np.abs(steady(P, Q, Xs2, Ys2))
    Xi, Yi = np.meshgrid(np.arange(130.0, 166.01, 2.0), np.arange(0.0, 108.01, 2.0), indexing="ij")
    in_L2 = np.abs(steady(P, Q, Xi, Yi))
    # 板が動き始める前（t < 0）の帯の目標（見直し H1）。壁のなだらかさ（帯の厚さの 1/4）を掛けた |η| の最大
    pre = {}
    for tag, xb1, ymax, lw, yin in [("L1_band0_36_y108", 36.0, 108.0, 9.0, 72.0), ("L1w_band0_36_y144", 36.0, 144.0, 9.0, 108.0),
                                    ("L3_band0_72_y144", 72.0, 144.0, 18.0, 72.0)]:
        ts_, m_ = band_precursor(P, Q, np.arange(0.0, xb1 + 0.01, 1.5), np.arange(0.0, ymax + 0.01, 3.0), 0.0, ymax, lw)
        ts2, m2 = band_precursor(P, Q, np.arange(xb1, 200.01, 12.0), np.arange(yin, ymax + 0.01, 6.0), 0.0, ymax, lw)
        m_ = np.maximum(m_, m2)
        cm = np.maximum.accumulate(m_)
        f02 = float(ts_[np.argmax(cm > 0.02)]) if (cm > 0.02).any() else None
        f05 = float(ts_[np.argmax(cm > 0.05)]) if (cm > 0.05).any() else None
        pre[tag] = dict(t_first_over_002m_s=r(f02, 1), t_first_over_005m_s=r(f05, 1),
                        max_upto_t0_m=r(m_[ts_ <= T0_PADDLE + 1e-9].max(), 4),
                        max_in_t0_to_0_m=r(m_[(ts_ > T0_PADDLE + 1e-9) & (ts_ < 0.0)].max(), 4),
                        max_in_0_to_1_m=r(m_[(ts_ >= 0.0) & (ts_ < 1.0)].max(), 3))
        if m_[ts_ <= T0_PADDLE + 1e-9].max() > 0.02:
            raise SystemExit("precursor at t0 exceeds 0.02 m: %s %s" % (cs["name"], tag))
    # 選ばなかった案（帯を造波板より上流に置く。前の版の計画）の t < 0 の目標。見直し H1 の確かめ
    rej = {}
    for xu, ymax in [(-36.0, 108.0), (-72.0, 144.0)]:
        for mode in ["omega", "perfreq"]:
            rej["x%d_%s" % (int(xu), mode)] = upstream_precursor(P, Q, xu, np.arange(0.0, ymax + 0.01, 4.0), mode)
    # 過渡（y = 0）
    eta = transient(P, Q, XS)
    e0 = eta.sum(axis=0)
    ipkx = int(np.argmin(np.abs(XS - x_pk)))
    env = np.abs(steady(P, Q, XS, 0.0))
    ser = e0[ipkx]
    t50 = first_cross(ser, 0.5 * env[ipkx]); t90 = first_cross(ser, 0.9 * env[ipkx])
    t_max = float(math.ceil(t90 + 2 * T))
    # 窓 L2（x 130〜340、y 0〜108）・L2w（y 0〜144）・L2x（x 130〜412、y 0〜144）の水面が 0.05 m を初めて越える時刻
    iw = np.where((XS >= 130.0) & (XS <= 340.0 + 1e-9))[0]
    ew = np.einsum("jxt,jy->yxt", eta[:, iw, :], np.cos(np.outer(qj, YW)))
    mx = np.abs(ew[YW <= 108.0 + 1e-9]).max(axis=(0, 1))
    t_win = float(TK[np.argmax(mx >= 0.05)])
    t0_L2 = float(math.floor(t_win))
    mxw = np.abs(ew).max(axis=(0, 1))
    t_win_w = float(TK[np.argmax(mxw >= 0.05)])
    t0_L2w = float(math.floor(t_win_w))
    iwx = np.where(XS >= 130.0)[0]
    ewx = np.einsum("jxt,jy->yxt", eta[:, iwx, :], np.cos(np.outer(qj, YW)))
    t_win_x = float(TK[np.argmax(np.abs(ewx).max(axis=(0, 1)) >= 0.05)])
    t0_L2x = float(math.floor(t_win_x))
    # 時刻ごとの y = 0 のいちばん高い線形の頂（巻き始めの比べで「線形からの先行き」を出す元）
    largest = []
    for tv in np.arange(20.0, 80.01, 2.0):
        it = int(np.argmin(np.abs(TK - tv)))
        ix = int(np.argmax(e0[:, it]))
        largest.append([float(tv), r(e0[ix, it], 2), float(XS[ix])])
    # 光線（見直し M5・M6）：横の帯の内の縁を横切る x。焦点 (250, 0) へ向かう最も斜めの光線と、起こす所の終わりから
    # 出ていく光線。y = 0 の各 x へ届く成分のうち、帯が起こす（起こす所で内の縁を横切るか、入口の帯から直に来る）振幅の割合
    thm = float(np.abs(th).max())
    rays = {}
    for yin, g_end, s_end in [(72.0, 200.0, 230.0), (108.0, 200.0, 230.0), (108.0, 250.0, 280.0)]:
        x_in = XF - yin / math.tan(math.radians(thm))
        x_out = g_end + yin / math.tan(math.radians(thm))
        kept = {}
        for xt in [212, 240, 260, 280, 290, 300, 310, 320, 340, 360]:
            w = np.ones_like(cs["A"])
            for i_, tt_ in enumerate(np.radians(np.abs(th))):
                if tt_ < 1e-9 or xt * math.tan(tt_) <= yin:
                    continue
                xc = xt - yin / math.tan(tt_)
                w[i_] = 1.0 if xc <= g_end else (0.0 if xc >= s_end else (s_end - xc) / (s_end - g_end))
            kept[str(xt)] = r((cs["A"] * w).sum() / cs["A"].sum(), 3)
        rays["inner_y%d_gen%d_switch%d" % (int(yin), int(g_end), int(s_end))] = dict(
            x_cross_toward_focus_m=r(x_in, 1), x_cross_leaving_m=r(x_out, 1),
            fits=bool(x_in <= g_end - 10.0 and x_out >= s_end + 10.0), share_kept_at_y0=kept)
    # 向きの分け方の形：θ = 0 の密度 ÷ 最大の密度（二つの山がはっきりしているか）。一様なら 1
    if cs["kind"] == "cross":
        mu_, sg_ = cs["params"]["dtheta_deg"] / 2, cs["params"]["sigma_group_deg"]
        tg = np.linspace(-90, 90, 3601)
        Dn = np.exp(-0.5 * ((tg - mu_) / sg_) ** 2) + np.exp(-0.5 * ((tg + mu_) / sg_) ** 2)
        dip = float(Dn[np.argmin(np.abs(tg))] / Dn.max())
    else:
        dip = 1.0
    case_out[cs["name"]] = dict(
        ja=cs["ja"], kind=cs["kind"], params={k: r(v, 4) for k, v in cs["params"].items()},
        theta_deg=r(th, 3), stroke_m=r(cs["stroke"], 5), A_m=r(cs["A"], 5),
        sum_A_m=r(cs["A"].sum(), 4), theta_max_deg=r(thm, 2),
        density_at_theta0_over_max=r(dip, 3),
        steady_walled=dict(x_peak_y0_m=x_pk, amp_peak_y0_m=r(Z0[ipk], 3),
                           amp_y0_at=dict({str(int(x)): r(Z0[int(x)], 3) for x in [36, 40, 50, 100, 130, 166, 200, 211, 250, 266, 300, 340, 376, 412]}),
                           band_L1_inlet_x9_36_y0_108=dict(median=r(np.median(band_L1), 3), max=r(band_L1.max(), 3)),
                           band_L3_inlet_x18_72_y0_144=dict(median=r(np.median(band_L3), 3), max=r(band_L3.max(), 3)),
                           band_L1_side_x0_200_y72_108=dict(median=r(np.median(side_L1), 3), max=r(side_L1.max(), 3)),
                           band_L1w_side_x0_250_y108_144=dict(median=r(np.median(side_L1w), 3), max=r(side_L1w.max(), 3)),
                           band_L2_inlet_x130_166=dict(median=r(np.median(in_L2), 3), max=r(in_L2.max(), 3)),
                           stokes2_ratio=dict(L1_inlet_median=r(stokes2_ratio(np.median(band_L1)), 3),
                                              L1_inlet_max=r(stokes2_ratio(band_L1.max()), 3),
                                              L3_inlet_median=r(stokes2_ratio(np.median(band_L3)), 3),
                                              L3_inlet_max=r(stokes2_ratio(band_L3.max()), 3),
                                              L2_inlet_median=r(stokes2_ratio(np.median(in_L2)), 3),
                                              L2_inlet_max=r(stokes2_ratio(in_L2.max()), 3))),
        band_target_before_t0=pre, rejected_upstream_band_before_t0=rej,
        transient_tanh=dict(t50_at_peak_s=r(t50, 2), t90_at_peak_s=r(t90, 2), t_max_s=t_max,
                            t_first_005m_in_L2_window_s=r(t_win, 2), t0_L2_s=t0_L2,
                            t_first_005m_in_L2w_window_s=r(t_win_w, 2), t0_L2w_s=t0_L2w,
                            t_first_005m_in_L2x_window_s=r(t_win_x, 2), t0_L2x_s=t0_L2x,
                            largest_linear_crest_y0=largest),
        rays=rays,
    )

# 照らし合わせ：r45 の線形の場（g 9.81）と同じ値が出るか（基準の例）
lin45 = load(SRC["lin45"])
crosscheck = dict(
    walled_x_peak_r45=lin45["steady"]["walled_x_of_max"], walled_amp_peak_r45=r(lin45["steady"]["walled_max_amp_y0"], 3),
    walled_x_peak_here=case_out["F45"]["steady_walled"]["x_peak_y0_m"], walled_amp_peak_here=case_out["F45"]["steady_walled"]["amp_peak_y0_m"],
    A_star_r45=r(lin45["inputs"]["A_star_ideal_sum_A0_over_cos"], 4), A_star_here=r(A_STAR, 4),
    note_ja="r45 は g 9.81、ここは g 9.80665（Houdini の既定）。差は波数の 0.02 % ほど",
)

# ------------------------------------------------------------------ Fochesato ら 2007 の表 1（水深 20 m の 2 例。fochesato_ja.md §3.1・§3.2 の m・s の値）
BEM = dict(
    F45=dict(tBP_s=48.20, xc_m=211.7, Ac_m=7.16, At1_m=3.60, At2_m=2.14, H1_m=10.76, H2_m=9.30, lam1_m=81.5, lam2_m=74.5,
             s=1.765, mu1=0.666, mu2=0.770, ell_m=66.0, width_at_xc_m=51.4, widest_behind_crest_m=5.0,
             u_crest_top_ms=11.1, u_z0_ms=3.9, u_bed_ms=1.1),
    F40=dict(tBP_s=36.2, xc_m=153.0, Ac_m=6.74, At1_m=3.28, At2_m=1.48, H1_m=10.02, H2_m=8.22, lam1_m=81.2, lam2_m=81.9,
             s=1.07, ell_m=60.6),
)
TOL = 0.05
repro = {}
for c, b in BEM.items():
    repro[c] = {k: [r(b[k] * (1 - TOL), 2), r(b[k] * (1 + TOL), 2)] for k in ["xc_m", "Ac_m", "H1_m", "ell_m", "tBP_s"]}

# ------------------------------------------------------------------ 費用の元（FLIP42 の記録）
P42 = load(SRC["plan42"])
ana = {k: load(SRC["ana_" + k]) for k in ["R1b", "R2", "R3", "R4d"]}
rec = {}
for k, a in ana.items():
    c = a["cost"]
    N = c["particles_max"]
    fr = a["frames_done"]
    on = a["onset"]["frame"]
    tot_s = c["wall_sum_h"] * 3600
    pre_s = on * c["wall_per_frame_median"]
    post_rate = (tot_s - pre_s) / (fr - on)
    rec[k] = dict(particles=N, frames=fr, onset_frame=on, wall_h=r(c["wall_sum_h"], 3),
                  median_s_per_frame=r(c["wall_per_frame_median"], 3),
                  us_per_particle_frame_median=r(c["wall_per_frame_median"] / N * 1e6, 4),
                  us_per_particle_frame_mean=r(tot_s / fr / N * 1e6, 4),
                  post_onset_over_median=r(post_rate / c["wall_per_frame_median"], 2),
                  still_offset_m=r(a["still_level_offset_m"], 4))
LX42 = math.ceil(P42["tank"]["Lx"] / 0.5 - 1e-9) * 0.5
RHO_025 = ana["R3"]["cost"]["particles_max"] / (LX42 * 42.0 * 2.0)      # 粒子 0.25 m の水 1 m³ あたりの粒子（R3 の最大）
R_PRE_LO = rec["R3"]["us_per_particle_frame_median"] * 1e-6               # 崩れの前（R3 の中央値）
R_PRE_HI = max(rec["R1b"]["us_per_particle_frame_median"], rec["R3"]["us_per_particle_frame_median"]) * 1e-6 * 1.5
# ↑ 粒子 0.5 m と 0.25 m の中央値の大きい方 × 1.5（3D の圧力の解きの重さは測っていない分）。R2（0.35 m）の 0.405 は機械の混み具合の
#   違いを分けられないので使わない（FLIP44 S1c：同じ設定の 1 コマの秒が数分の間に 18 % 動いた）
M_POST_LO = rec["R2"]["post_onset_over_median"]                            # 崩れの後の重さ（中央値に対する倍、空いた機械の記録の小さい方）
M_POST_HI = rec["R4d"]["post_onset_over_median"]                           # 同じく大きい方（R3 はゲームの重さが入り 8.9 倍）
FINE_FACTOR = rec["R4d"]["us_per_particle_frame_median"] / rec["R3"]["us_per_particle_frame_median"]   # 粒子 0.177 m の小刻みの増え
CHAIN = (1.10, 1.30)                                                       # 区切った起動のやり直し（FLIP44 §5.1 の 1.01〜1.57、FLIP42 R2・R4d の 1.12・1.15 から）
SURF_US = None
surf = load(SRC["surf45"])
abc = load(SRC["abc45"])
for rr in surf["results"]:
    if rr["name"] == "A":
        SURF_US = rr["t_surface_s"] / surf["particles"] * 1e6                 # 面を作る秒 ÷ 百万粒子（粒子 0.25 m、面の格子 0.25 m）
        TRI_025 = rr["tris_per_m2_plan"]
    if rr["name"] == "C":
        TRI_05 = rr["tris_per_m2_plan"]
ABC_B_PER_TRI = None
for rr in abc.get("results", []):
    if rr.get("name") == "A" and rr.get("abc_bytes_per_tri"):
        ABC_B_PER_TRI = rr["abc_bytes_per_tri"]
if ABC_B_PER_TRI is None:
    ABC_B_PER_TRI = 34.3          # unity3d_ja.md §3.3（run3_abc の A：4,008,071 バイト ÷ 116,811 三角形）
CUSTOM_B_PER_TRI = 20.0           # unity3d_ja.md §2.3（16 bit の位置、法線、半精度の v、32 bit の添字）
CKPT_B_PER_PARTICLE = 55.0        # R3 の途中保存（Houdini の大波の調べ §6.4）
CKPT_B_PER_CELL_HI = 40.0         # 3D の場の分（上の端だけに足す）【推定】
CKPT_IO_GBS = (0.154, 0.10)       # 途中保存の読み書きの速さ（FLIP44 の 0.54 GB を 3.5 s から）
LAUNCH_S = 1740.0                 # 1 回の起動の上限（AGENTS.md の 30 分の決まりから余りを引いた FLIP44 の値）
FREE_G_GB = 505.4                 # G: の空き（10⁹ バイト）【測った：2026-10-12 07:18、Get-PSDrive の Free ÷ 10⁹】
FREE_F_GB = 1089.8                # F:（USB の SSD）の空き【測った：同じ】
# ↑ 前の版の 470.9・1,015 は 2³⁰ バイト（GiB）で読んだ値だった（06:22）。途中保存の大きさは 10⁹ バイトで出すので、単位をそろえた
STOP_FREE_GB = 25.0               # 起動ごとに G: の空きがこれより少なければ止めて伺う（FLIP44 の N8）


def rho(dp):
    return RHO_025 * (0.25 / dp) ** 3


def rup(v, q):
    return float(math.ceil(v / q - 1e-9) * q)


AIR = 16.0
# 見直しの後の窓（H1：入口の帯は造波板の下流。M6：X60 は x 412 m まで）。side_gen：横の帯の起こす所の終わり、side_sw：切り替えの終わり
LAYOUTS = dict(
    L1=dict(ja="造波板から（入口の帯は造波板の線 x 0 から下流へ 36 m。目標は Fochesato らの水槽の線形の場そのもの）", x=(0.0, 340.0), y=(0.0, 108.0),
            inlet=(0.0, 36.0), exit=(304.0, 340.0), side=(72.0, 108.0), side_gen=200.0, side_sw=230.0,
            crop_x=(36.0, 304.0), crop_y=(0.0, 72.0), vdb_x=(100.0, 304.0)),
    L2=dict(ja="窓（入口を x 130 m に置く、調べの案）", x=(130.0, 340.0), y=(0.0, 108.0),
            inlet=(130.0, 166.0), exit=(304.0, 340.0), side=(72.0, 108.0), side_gen=200.0, side_sw=230.0,
            crop_x=(166.0, 304.0), crop_y=(0.0, 72.0), vdb_x=(166.0, 304.0)),
    L1w=dict(ja="造波板から・横に広い（52.5° の成分を横の帯が焦点の手前で起こせるよう、帯の内の縁を y 108 m に）", x=(0.0, 340.0), y=(0.0, 144.0),
             inlet=(0.0, 36.0), exit=(304.0, 340.0), side=(108.0, 144.0), side_gen=200.0, side_sw=230.0,
             crop_x=(36.0, 304.0), crop_y=(0.0, 108.0), vdb_x=(100.0, 304.0)),
    L2w=dict(ja="窓・横に広い", x=(130.0, 340.0), y=(0.0, 144.0),
             inlet=(130.0, 166.0), exit=(304.0, 340.0), side=(108.0, 144.0), side_gen=200.0, side_sw=230.0,
             crop_x=(166.0, 304.0), crop_y=(0.0, 108.0), vdb_x=(166.0, 304.0)),
    L1x=dict(ja="X60 用：造波板から・横に広い・長い（出口の帯 376〜412 m、横の帯の起こす所は 250 m まで、切り替え 250〜280 m）", x=(0.0, 412.0), y=(0.0, 144.0),
             inlet=(0.0, 36.0), exit=(376.0, 412.0), side=(108.0, 144.0), side_gen=250.0, side_sw=280.0,
             crop_x=(36.0, 376.0), crop_y=(0.0, 108.0), vdb_x=(100.0, 376.0)),
    L2x=dict(ja="X60 用：窓・横に広い・長い", x=(130.0, 412.0), y=(0.0, 144.0),
             inlet=(130.0, 166.0), exit=(376.0, 412.0), side=(108.0, 144.0), side_gen=250.0, side_sw=280.0,
             crop_x=(166.0, 376.0), crop_y=(0.0, 108.0), vdb_x=(166.0, 376.0)),
    L3=dict(ja="繰り返し用（入口・出口・横の帯を 72 m に。入口の帯は造波板の線 x 0 から下流へ 72 m）", x=(0.0, 376.0), y=(0.0, 144.0),
            inlet=(0.0, 72.0), exit=(304.0, 376.0), side=(72.0, 144.0), side_gen=200.0, side_sw=230.0,
            crop_x=(72.0, 304.0), crop_y=(0.0, 72.0), vdb_x=(100.0, 304.0)),
)
WALL_TAPER_FRAC = 0.25      # 帯の目標に掛ける壁のなだらかさの長さ ÷ 帯の厚さ（FLIP42 の 33.87 m ÷ 135.5 m と同じ割合。見直し H2）
RAMP_S = 0.0                # g44 の rampT の秒。目標の表が立ち上げ tanh(t/T) を持つので 0 にして掛けない（見直し H2）


def geom(L, dp):
    """箱の底は全部の粒子で −20 m ちょうど（閉じた壁。見直し M3）。高さ・長さは格子の倍数に切り上げるので、端は 2 進で割り切れる。"""
    vox = 2 * dp
    lx = rup(L["x"][1] - L["x"][0], vox); ly = rup(L["y"][1] - L["y"][0], vox)
    hz = rup(D + AIR, vox)
    vol = lx * ly * D
    N = rho(dp) * vol
    cells = (lx / vox) * (ly / vox) * (hz / vox)
    crop = (L["crop_x"][1] - L["crop_x"][0]) * (L["crop_y"][1] - L["crop_y"][0])
    vdb = (L["vdb_x"][1] - L["vdb_x"][0]) * (L["crop_y"][1] - L["crop_y"][0])
    ends = (vox, lx, ly, hz, -D + hz, L["x"][0] + lx)
    exact = all(abs(v * 2 ** 20 - round(v * 2 ** 20)) < 1e-6 for v in ends)
    return dict(vox=vox, Lx=lx, Ly=ly, Hz=hz, z_top=-D + hz, bed_exact=True, ends_binary_exact=bool(exact),
                x_cells=int(round(lx / vox)), y_cells=int(round(ly / vox)), z_cells=int(round(hz / vox)),
                particles_M=N / 1e6, grid_cells_M=cells / 1e6, crop_m2=crop, vdb_m2=vdb)


def per_frame_bytes(L, g, dp, hi):
    vox = g["vox"]
    eta_top = g["x_cells"] * g["y_cells"] * 4 * 0.7
    sec = g["x_cells"] * g["z_cells"] * (6 + 8)                          # y = 0（SDF・u・w）と y = 33 m（SDF・u・v・w）、半精度
    vdb = g["vdb_m2"] / vox ** 2 * 6 * 4 * (1.3 * (1.5 if hi else 1.0))  # 水面の狭い帯の SDF（格子 6 つ）
    # 面の格子は粒子の間隔と同じ（0.1768 m の計算も比べのため 0.25 m）。0.25 と 0.5 m の間は測った 2 点の対数で結ぶ
    if dp <= 0.25:
        tpm = TRI_025
    else:
        tpm = TRI_025 * (TRI_05 / TRI_025) ** (math.log(dp / 0.25) / math.log(2.0))
    tri = tpm * g["crop_m2"] * (1.5 if hi else 1.0)
    surf = tri * CUSTOM_B_PER_TRI
    return dict(eta_top=eta_top, sections=sec, vdb=vdb, surface=surf, total=eta_top + sec + vdb + surf, triangles=tri)


def run_cost(L, dp, t0, t_onset, t_end, t_surf0, fine=False, cfl=1.0):
    """t0 から t_end まで。t_onset より後を崩れの後とする。t_surf0 から面を毎コマ作る。"""
    g = geom(L, dp)
    N = g["particles_M"] * 1e6
    f_pre = max(0.0, (min(t_onset, t_end) - t0)) * FPS
    f_post = max(0.0, (t_end - t_onset)) * FPS
    f_surf = max(0.0, (t_end - max(t_surf0, t0))) * FPS
    ff = (FINE_FACTOR if fine else 1.0) * cfl      # cfl：CFL を半分にした計算の小刻みの増え（2 倍と置いた）
    layer = g["crop_m2"] * rho(dp)
    out = {}
    for tag, rpre, mpost, ch, lay_t, iob in [("lo", R_PRE_LO, M_POST_LO, CHAIN[0], 2.5, CKPT_IO_GBS[0]),
                                            ("hi", R_PRE_HI, M_POST_HI, CHAIN[1], 5.0, CKPT_IO_GBS[1])]:
        spf = N * rpre * ff
        sim_s = spf * (f_pre + mpost * f_post)
        surf_s = SURF_US * 1e-6 * layer * lay_t * f_surf
        fb = per_frame_bytes(L, g, dp, tag == "hi")
        write_s = fb["total"] / (100e6 if tag == "lo" else 30e6) * (f_pre + f_post)
        ck = (CKPT_B_PER_PARTICLE * N + (CKPT_B_PER_CELL_HI * g["grid_cells_M"] * 1e6 if tag == "hi" else 0.0)) / 1e9
        hours = (sim_s + surf_s + write_s) * ch / 3600
        launch_over = 6.0 + 2 * ck / iob
        launches = math.ceil(hours * 3600 / (LAUNCH_S - launch_over))
        ck_per_launch = 1.0 if tag == "lo" else 2.0
        rec_gb = fb["total"] * (f_pre + f_post) / 1e9
        out[tag] = dict(hours=r(hours, 2), sim_s_per_frame_pre=r(spf, 1), surf_s_per_frame=r(SURF_US * 1e-6 * layer * lay_t, 1),
                        launches=launches, ckpt_GB=r(ck, 2), ckpt_keep_all_GB=r(ck * launches * ck_per_launch, 0),
                        ckpt_keep4_GB=r(ck * 4, 1), records_GB=r(rec_gb, 1), MB_per_frame=r(fb["total"] / 1e6, 2),
                        triangles_per_frame=int(fb["triangles"]))
    mem = 5.3 + 0.12 * g["particles_M"] + 80e-9 * g["grid_cells_M"] * 1e6
    return dict(layout_dims=dict(Lx=r(g["Lx"], 4), Ly=r(g["Ly"], 4), Hz=r(g["Hz"], 4), z_bottom=-D, z_top=r(g["z_top"], 6), vox=g["vox"],
                                 bed_is_box_bottom=g["bed_exact"], ends_binary_exact=g["ends_binary_exact"],
                                 cells=[g["x_cells"], g["y_cells"], g["z_cells"]],
                                 u2_half_step_mm=r((L["crop_x"][1] - L["crop_x"][0]) / 65535.0 / 2.0 * 1000.0, 2)),
                particles_M=r(g["particles_M"], 1), grid_cells_M=r(g["grid_cells_M"], 1), mem_GB=r(mem, 1),
                frames=int(round((t_end - t0) * FPS)), t0_s=t0, t_end_s=t_end, **{"cost_" + k: v for k, v in out.items()})


TB = BEM["F45"]["tBP_s"]
# 終わりの時刻：計算の中で着水を見つけたら着水 + 1 T で止める（下の端の見込みは BEM の巻き始め + 1.3 s + T）。見つからなければ t_max
co = case_out
ONSET_LO = dict(F45=TB, F40=BEM["F40"]["tBP_s"])
for c in ["X45", "X60"]:
    # 答えのない例は、基準の例と同じく「焦点の線形の包絡が 50 % に届いてから同じ秒数の後」に巻くと置いた【推定。費用の見込みだけに使う】
    ONSET_LO[c] = co[c]["transient_tanh"]["t50_at_peak_s"] + (TB - co["F45"]["transient_tanh"]["t50_at_peak_s"])
END_LO = {c: ONSET_LO[c] + 1.3 + T for c in ONSET_LO}      # 巻き始め → 着水 1.3 s（FLIP42 R3）、その後 1 T で止める
END_HI = {c: min(ONSET_LO[c] * 1.1 + 1.3 + T, co[c]["transient_tanh"]["t_max_s"]) for c in ONSET_LO}   # 巻き始めが 1 割遅れた時
T_SURF0 = 24.0          # 面を毎コマ作り始める時刻（窓の中に波が来る前は作らない）
RPT_T_END = 120.0

RUNS = []


def add(name, case, layout, dp, kind, gate_ja, what_ja, t0=0.0, fine=False, t_end_fixed=None, t_surf0=T_SURF0, cfl=1.0, t0_from_onset=None):
    c = co[case]
    t_cap = t_end_fixed if t_end_fixed is not None else c["transient_tanh"]["t_max_s"]
    te_hi = t_end_fixed if t_end_fixed is not None else END_HI[case]
    te_lo = t_end_fixed if t_end_fixed is not None else END_LO[case]
    on = ONSET_LO[case]
    if t0_from_onset is not None:      # 途中保存から始める計算：巻き始めの t0_from_onset 秒前から
        t0 = on - t0_from_onset
    lo = run_cost(LAYOUTS[layout], dp, t0, on, te_lo, t_surf0, fine, cfl)
    hi = run_cost(LAYOUTS[layout], dp, (on * 1.1 - t0_from_onset) if t0_from_onset is not None else t0, on * 1.1, te_hi, t_surf0, fine, cfl)
    cap = run_cost(LAYOUTS[layout], dp, t0, on, t_cap, t_surf0, fine, cfl)
    RUNS.append(dict(name=name, case=case, layout=layout, dp=dp, kind=kind, gate_ja=gate_ja, what_ja=what_ja,
                     t0_s=t0, t_end_lo_s=r(te_lo, 1), t_end_hi_s=r(te_hi, 1), t_cap_s=t_cap,
                     hours_at_cap_hi=cap["cost_hi"]["hours"], max_hours=r(2 * hi["cost_hi"]["hours"], 1),
                     particles_M=hi["particles_M"], mem_GB=hi["mem_GB"], grid_cells_M=hi["grid_cells_M"], dims=hi["layout_dims"],
                     hours=dict(lo=lo["cost_lo"]["hours"], hi=hi["cost_hi"]["hours"]),
                     launches=dict(lo=lo["cost_lo"]["launches"], hi=hi["cost_hi"]["launches"]),
                     ckpt_GB=dict(lo=lo["cost_lo"]["ckpt_GB"], hi=hi["cost_hi"]["ckpt_GB"]),
                     ckpt_keep_all_GB=dict(lo=lo["cost_lo"]["ckpt_keep_all_GB"], hi=hi["cost_hi"]["ckpt_keep_all_GB"]),
                     ckpt_keep4_GB=hi["cost_hi"]["ckpt_keep4_GB"],
                     records_GB=dict(lo=lo["cost_lo"]["records_GB"], hi=hi["cost_hi"]["records_GB"]),
                     MB_per_frame=dict(lo=lo["cost_lo"]["MB_per_frame"], hi=hi["cost_hi"]["MB_per_frame"]),
                     sim_s_per_frame_pre=dict(lo=lo["cost_lo"]["sim_s_per_frame_pre"], hi=hi["cost_hi"]["sim_s_per_frame_pre"]),
                     surf_s_per_frame=dict(lo=lo["cost_lo"]["surf_s_per_frame"], hi=hi["cost_hi"]["surf_s_per_frame"]),
                     triangles_per_frame=dict(lo=lo["cost_lo"]["triangles_per_frame"], hi=hi["cost_hi"]["triangles_per_frame"]),
                     frames_hi=hi["frames"]))


t0L2 = {c: co[c]["transient_tanh"]["t0_L2_s"] for c in co}
t0L2w = {c: co[c]["transient_tanh"]["t0_L2w_s"] for c in co}
t0L2x = {c: co[c]["transient_tanh"]["t0_L2x_s"] for c in co}
TP = T0_PADDLE
add("V1", "F45", "L1", 0.5, "preview", "準備（道具・場面・煙の試し・別の者の確かめ・凍結）が終わったら（Q57 の B。指導教員の合意を待たない）",
    "粗い下見：基準の例を造波板から。利用者に見せる。3D の 1 コマの秒を測る。入口の振幅と x 130 m までの減りを確かめる", t0=TP)
add("V2", "F45", "L2", 0.5, "preview", "V1 が §6.8 の前提（x 130 m の振幅 ±3 %・位相 ±0.10 rad）を満たした時だけ。利用者が良いと言えば合意の前、そうでなければ合意の後の最初",
    "粗い下見：同じ例を窓で。V1 と比べて、窓を本番に使えるかを決める（§6.8）", t0=t0L2["F45"])
add("V3", "F45", "L1", 0.5, "conditional", "V1 の巻き始めの時刻が ±5 % の外の時だけ。M1 の前",
    "立ち上げの感度（記録だけ）：立ち上げを 0.5{1 + tanh(2t/T − 3)} にした V1。判定は変えない", t0=TP)
add("V1h", "F45", "L1", 0.5, "check05", "合意の後、M1h の次（利用者が良いと言えば合意の前）",
    "時間の刻みの確かめ（全長）：CFL を半分にした V1。伝わる間の減りが時間の刻みで変わるか（見直し M4）", t0=TP, cfl=2.0)
add("V4", "F45", "L1w", 0.5, "check05", "合意の後、V1h の次（利用者が良いと言えば合意の前）",
    "横の帯の位置の感度：横の帯の内の縁を 108 m にした V1。F45（内の縁 72 m）と X60（108 m）を比べてよいか（見直し M5）", t0=TP)
for lay, wide, longw, tag in [("L2", "L2w", "L2x", "A"), ("L1", "L1w", "L1x", "B")]:
    t0 = t0L2["F45"] if lay == "L2" else TP
    add("M1_" + lay, "F45", lay, 0.25, "main", "指導教員の合意の後。並び " + tag,
        "本番の再現：基準の例（粒子 0.25 m）。§6.1 の判定", t0=t0)
    add("M1h_" + lay, "F45", lay, 0.25, "main", "合意の後。並び " + tag + "。M1 の途中保存（巻き始めの 7 s 前より前の最後の物）から",
        "時間の刻みの確かめ：CFL を半分（cflcond 0.5・partcflcond 0.375）にして M1 の巻き始めの前から着水 + 1 T まで（FLIP42 の R5' と同じ形）",
        cfl=2.0, t0_from_onset=7.0, t_surf0=1e9)
    add("M1c_" + lay, "F45", lay, 0.34375, "main", "合意の後。並び " + tag + "（細かさの 3 段：0.5・0.34375・0.25 m）",
        "細かさの間の段（粒子 11/32 m）", t0=t0)
    add("X45_" + wide, "X45", wide, 0.25, "main", "合意の後。並び " + tag + "。2 回目の報告（見直し M14）", co["X45"]["ja"],
        t0=(t0L2w["X45"] if wide == "L2w" else TP))
    add("X60_" + longw, "X60", longw, 0.25, "main", "合意の後。並び " + tag + "。最初の報告", co["X60"]["ja"],
        t0=(t0L2x["X60"] if longw == "L2x" else TP))
add("F40_L1", "F40", "L1", 0.25, "main", "合意の後。並び A・B とも（BEM の巻き始めが 153 m で、窓の入口の帯 130〜166 m に入るので、窓では解けない）",
    co["F40"]["ja"], t0=TP)
add("M1f_L2", "F45", "L2", 0.1767578125, "main", "合意の後。並び A の最後（日が足りなければ落とし、そう書く）",
    "細かさの確かめ（粒子 181/1024 m）", t0=t0L2["F45"], fine=True)
add("M1f_L1", "F45", "L1", 0.1767578125, "infeasible", "並び B では走らせない（費用の記録だけ）", "細かさの確かめ（L1）", t0=TP, fine=True)
add("RPT05", "F45", "L3", 0.5, "main", "合意の後。並び A・B とも V4 の次",
    "同じ周期の扇を送り続ける（−2〜120 s、約 10 周期）。毎周期同じ所で大きな頂になるか（§6.6）。粒子 0.5 m の粗い計算",
    t0=TP, t_end_fixed=RPT_T_END, t_surf0=40.0)
add("RPT034", "F45", "L3", 0.34375, "option", "RPT05 で繰り返しが見え、利用者と指導教員が細かい版を望んだ時だけ（日程に入れていない）",
    "繰り返しの細かい版（粒子 11/32 m）", t0=TP, t_end_fixed=RPT_T_END, t_surf0=40.0)
add("M1w_L1w", "F45", "L1w", 0.25, "option", "V4 で横の帯の位置が量を動かした時に伺う（日程に入れていない）",
    "F45 を X60 と同じ横の帯の位置（内の縁 108 m）で解く本番", t0=TP)
RUN = {x["name"]: x for x in RUNS}

SEQ = dict(
    A=["M1_L2", "M1h_L2", "V1h", "V4", "RPT05", "X60_L2x", "M1c_L2", "F40_L1", "X45_L2w", "M1f_L2"],
    B=["M1_L1", "M1h_L1", "V1h", "V4", "RPT05", "X60_L1x", "M1c_L1", "F40_L1", "X45_L1w"],
)
GAPS = {"M1_L2": 1.0, "M1_L1": 1.0, "M1h_L2": 0.5, "M1h_L1": 0.5, "RPT05": 0.5, "X45_L2w": 0.5, "X45_L1w": 0.5,
        "X60_L2x": 0.5, "X60_L1x": 0.5}     # 計算の後の人の作業（確かめ）の時間（h）
REPORT_AFTER = {"A": "X60_L2x", "B": "X60_L1x"}     # 最初の報告に入れる最後の計算


def timeline(start, seq, which="hi"):
    t = start
    out = []
    rep = None
    for nm in seq:
        t0 = t
        t = t + datetime.timedelta(hours=RUN[nm]["hours"][which])
        out.append(dict(run=nm, start=t0.strftime("%m/%d %H:%M"), end=t.strftime("%m/%d %H:%M")))
        if nm in GAPS:
            t = t + datetime.timedelta(hours=GAPS[nm])
    return out, t


def dt(m, d, h, mi=0):
    return datetime.datetime(2026, m, d, h, mi)


READY = dt(10, 13, 10)          # 準備が終わる時刻の例（計画 §8。見込みで、決まりではない）
prev = {}
for which in ["lo", "hi"]:
    t = READY
    v1e = t + datetime.timedelta(hours=RUN["V1"]["hours"][which])
    v2e = v1e + datetime.timedelta(hours=RUN["V2"]["hours"][which])
    prev[which] = dict(V1_start=READY.strftime("%m/%d %H:%M"), V1_end=v1e.strftime("%m/%d %H:%M"), V2_end_if_run_now=v2e.strftime("%m/%d %H:%M"))
sched = {}
for agree, start0 in [("10/13", dt(10, 13, 19)), ("10/14", dt(10, 14, 19))]:
    sched[agree] = {}
    for sk, seq in SEQ.items():
        for which in ["lo", "hi"]:
            # 本番は合意の日の 19:00 か、下見（V1、並び A は V2 も）の終わり + 1 時間の遅い方から（見直し L7）
            pv = READY + datetime.timedelta(hours=RUN["V1"]["hours"][which] + (RUN["V2"]["hours"][which] if sk == "A" else 0.0) + 1.0)
            start = max(start0, pv)
            tl, tend = timeline(start, seq, which)
            rep_end = [x for x in tl if x["run"] == REPORT_AFTER[sk]][0]["end"]
            rep_dt = datetime.datetime.strptime("2026/" + rep_end, "%Y/%m/%d %H:%M") + datetime.timedelta(hours=24)
            sched[agree][sk + "_" + which] = dict(start=start.strftime("%m/%d %H:%M"), timeline=tl, all_end=tend.strftime("%m/%d %H:%M"),
                                                  first_report_ready=rep_dt.strftime("%m/%d %H:%M"))
tot = {}
for sk, seq in SEQ.items():
    tot[sk] = dict(lo=r(sum(RUN[n]["hours"]["lo"] for n in seq), 1), hi=r(sum(RUN[n]["hours"]["hi"] for n in seq), 1),
                   at_cap_hi=r(sum(RUN[n]["hours_at_cap_hi"] for n in seq), 1),
                   until_first_report_at_cap_hi=r(sum(RUN[n]["hours_at_cap_hi"] for n in seq[:seq.index(REPORT_AFTER[sk]) + 1]), 1),
                   until_first_report_lo=r(sum(RUN[n]["hours"]["lo"] for n in seq[:seq.index(REPORT_AFTER[sk]) + 1]), 1),
                   until_first_report_hi=r(sum(RUN[n]["hours"]["hi"] for n in seq[:seq.index(REPORT_AFTER[sk]) + 1]), 1),
                   ckpt_keep_all_GB_lo=r(sum(RUN[n]["ckpt_keep_all_GB"]["lo"] for n in seq), 0),
                   ckpt_keep_all_GB_hi=r(sum(RUN[n]["ckpt_keep_all_GB"]["hi"] for n in seq), 0),
                   ckpt_keep4_GB=r(sum(RUN[n]["ckpt_keep4_GB"] for n in seq), 0),
                   records_GB_hi=r(sum(RUN[n]["records_GB"]["hi"] for n in seq), 0))

# ------------------------------------------------------------------ 帯の跳ね返り（調べの理論の値を写す）
gen = load(SRC["gen45"])
refl = gen["reflection"]["T7_h20"]
band_refl = {}
for key in refl:
    v = refl[key].get("sponge_chi2_best_sigma_normal")
    if v:
        band_refl[key] = dict(sigma_per_s=r(v["sigma"], 3), CR_0deg=r(v["CR"], 3), CR_by_angle={a: r(c, 3) for a, c in v["CR_at_30_45_60"].items()})
    w = refl[key].get("relaxw_dt0_1_24(FLIP42 band)")
    if w:
        band_refl[key]["FLIP42_inlet_weight_CR"] = {a: r(c, 3) for a, c in w.items()}
t_return = dict(exit_band_earliest_s=76.0, side_band_earliest_s=63.0, inlet_band_L2_earliest_s=54.0,
                note_ja="跳ね返りが x 211 m へ戻る最も早い時刻。generation_ja.md §5.4 の値（群速度 6.24 m/s、線形の群の前線から）を写した")

# ------------------------------------------------------------------ 判定の数（走らせる前に決めた。理由は plan_ja.md §6）
P44 = load(SRC["plan44"])
shape = [dict(key=m["key"], ja=m["ja"], unit=m["unit"], print_cn=r(m["print_cn"], 4), print_range=r(m["print_range"], 4),
              print_is_lower_bound=m["print_is_lower_bound"], R3=r(m["R3"], 4), R4d=r(m["R4d"], 4), yardstick_2d=r(m["yardstick"], 4))
         for m in P44["shape"]["measures"]]
criteria = dict(
    reproduction=dict(tol_rel=TOL, bands=repro, primary=["xc_m", "Ac_m", "H1_m", "ell_m"], time_band_judged_separately=True,
                      same_crest_dt_s=r(0.5 * T, 2),
                      same_crest_rule_ja="「再現した」と書くには、巻き始めの時刻が論文の tBP から ±T/2（±3.50 s）の中（同じ頂が巻いた）。外なら「論文と違う頂（n 周期後・前）が巻いた」と書き、4 つの量は並べるが「再現した」とは書かない（見直し M1）",
                      plunge_rule_ja="巻き始めの後、t_end までに y = 0 の断面で、(a) 唇が前の水面と空気を囲む（閉じた空気の線の面積が格子 1 個以上）か、(b) 唇の先が静かな水面以下に届き、同じコマに覆いかぶさり（同じ x の列で下から水・空気・水と並ぶ所）が x に格子 2 個以上続く（見直し M10）",
                      onset_rule_ja="y = 0 の断面（対称の壁に接する格子の層）の水面の線で、前の面の弦（格子 1 個）の傾きが初めて 90° 以上になったコマ。場所はそのコマの頂の x",
                      offaxis_onset_rule_ja="R4 の水面の場で、どの y の x–z 断面でも前の面の弦が初めて 90° 以上になったコマと、その y・x も記録する（見直し M7。X45・X60 は両方を報告。F45・F40 の判定は論文と同じ y = 0）",
                      ell_note_ja="論文の横の要素は Δy 4.3 m（双 3 次）で、ℓ の幅 ±3.3 m と同じ大きさ。ℓ が幅を外れ、外れの量が 4.3 m より小さい時は、外れたと書いたうえで、その大きさが論文の横の要素より小さいことを並べる（見直し L8）",
                      inlet_qualify_ja="M1・F40 の N3（入口の振幅の比）が 0.95〜1.05 の外なら、§6.1 の文に「入口の振幅が目標の r 倍だった中で」と付ける（見直し H3）",
                      resolution_qualify_ja="並び A は M1 と M1f（あれば M1c）で判定（入った・外れた）が同じかを書く。並び B は「粒子 0.25 m が十分かは 3D の細かい計算で確かめていない（0.5・0.34375・0.25 m の 3 段の目安だけ）」と書く（見直し M2）"),
    layout_decision=dict(onset_dt_s=r(0.1 * T, 2), onset_dx_m=r(0.1 * L0, 2), Ac_rel=0.05, H1_rel=0.05, ell_rel=0.05,
                         precondition_V1_x130_amp_rel=0.03, precondition_V1_x130_phase_rad=0.10,
                         precondition_ja="V1 の y = 0・24・48 m の x 130 m で、周期 7 s の成分の振幅が線形の過渡の ±3 %、位相が ±0.10 rad に全部入った時だけ V2 を走らせて比べる。入らなければ V2 を走らせず並び B（見直し H5）"),
    resolution=dict(C1_onset_dt_s=r(0.1 * T, 2), C1_onset_dx_m=r(0.1 * L0, 2), C2_rel=0.05, C3_rel=0.10, C4_rel=0.10, ell_rel=0.05,
                    base_ja="細かい方を元にする（FLIP42 の読み方 17）"),
    repetition=dict(dt_s=r(0.05 * T, 3), dx_m=r(0.05 * L0, 2), eta_c_rel=0.05, H_rel=0.05,
                    steady_from_s=None, min_events=4, window_x_m=r(0.5 * L0, 1)),
    numerics=dict(still_window_after_t0_s=[0.5, 2.0], level_guard_m=1.0, inlet_amp_ratio=[0.95, 1.05], inlet_amp_gate_preview=[0.90, 1.10],
                  inlet_phase_rad=0.10, inlet_points_x_L1=[40.0, 72.0], inlet_points_x_L3=[76.0, 108.0], inlet_points_x_L2=[170.0],
                  inlet_points_y=[0.0, 24.0, 48.0],
                  L2_initial_still_m=0.05, disk_stop_free_GB=STOP_FREE_GB, max_substeps=8,
                  cflcond=1.0, partcflcond=0.75,
                  dissipation_D1=dict(ratio_min=0.975, x_from=40.0, x_to=130.0,
                                      rule_ja="造波板から解く窓で、y = 0 の x 130 m の（FLIP ÷ 線形の過渡）の周期 7 s の振幅の比を、x 40 m の同じ比で割った値が 0.975 以上（エネルギーの流れで 5 % 以内。FLIP42 の B1 と同じ 5 %。見直し M12）。窓 L2 では測れないと書く"),
                  long_wave=dict(period_min_s=20.0, x_m=[100.0, 150.0, 200.0], note_frac_of_Ac=0.01,
                                 rule_ja="周期 20 s より長い水面の動きの振幅を y = 0 の x 100・150・200 m で巻き始めまで記録し、x 200 m で Ac の 1 %（0.07 m）を越えたら Ac・H1 の判定の横に値を書く（見直し M11）"),
                  near_band_rule_ja="巻き始めの x が出口の帯の内の縁の 0.5 λ（36 m）手前より先、または光線の見積もりで y = 0 のその x へ帯が起こす振幅の割合が 0.95 より小さい時は「帯に近い」と書き、形の量の比べから外す（見直し M6）"),
    inflow=dict(wall_taper_frac_of_band=WALL_TAPER_FRAC, wall_taper_m=dict(band36=36.0 * WALL_TAPER_FRAC, band72=72.0 * WALL_TAPER_FRAC),
                ramp_s=RAMP_S, t0_paddle_layouts_s=T0_PADDLE,
                taper_ja="E = smooth01((x − x_min)/L_w) × smooth01((y_max − y)/L_w)。x_min は箱の上流の壁、y_max は横の外の壁、L_w は帯の厚さの 1/4（36 m の帯で 9 m、72 m で 18 m）。角は掛け算。y = 0（対称の面）と吸う帯には掛けない（見直し H2）",
                gain_ja="入口の利得 G(dp, θ_j)：煙の試し S2b（2D の板、直角）で粒子ごとに測った帯の出口の振幅の比 r0(dp) と、S2a（粒子 0.5 m、±30°・±45°）で測った斜めの比 r(θ)/r0 から、G = 1 / {r0(dp) · r(θ_j)/r0(0.5)}。θ_j = asin(q_j / k) の横の形ごとに線形に補間し、45° より斜めは 45° の値。煙の試しの後に決めて record_ja.md に書き、その後は変えない（見直し H3）"),
    shape_measures=shape,
    shape_floor_note_ja="物差し Y は 2D の |R3 − R4d| と床（長さ 0.03 η_c、面積 0.005 η_c²、角度 1°）の大きい方（FLIP44 §3.3 (b) と同じ）。M1 と M1f がそろえば 3D の値に置き換える",
)
# 繰り返しの「落ち着いた」時刻：線形の包絡が焦点で 95 % に届く時刻
ser_pk = None
P, Q = modes(CASES[0])
eta = transient(P, Q, np.array([co["F45"]["steady_walled"]["x_peak_y0_m"]]))
ser_pk = eta.sum(axis=0)[0]
amp_pk = co["F45"]["steady_walled"]["amp_peak_y0_m"]
t95 = first_cross(ser_pk, 0.95 * amp_pk)
criteria["repetition"]["steady_from_s"] = r(t95, 2)

# ------------------------------------------------------------------ Unity での再生の大きさ（unity3d_ja.md §4 と同じ数え方）
unity = {}
for nm in ["V1", "M1_L2", "M1_L1", "RPT05", "X60_L1x"]:
    R_ = RUN[nm]
    tri = R_["triangles_per_frame"]["hi"]
    unity[nm] = dict(triangles_hi=tri, custom_MB_per_frame=r(tri * CUSTOM_B_PER_TRI / 1e6, 2), alembic_MB_per_frame=r(tri * ABC_B_PER_TRI / 1e6, 2),
                     clip7s_GB=r(tri * CUSTOM_B_PER_TRI * 168 / 1e9, 2), clip20s_GB=r(tri * CUSTOM_B_PER_TRI * 480 / 1e9, 2),
                     alembic_swap_ms_est=r(tri / 1000 * 0.092, 1),
                     U2_tol_mm=r(R_["dims"]["u2_half_step_mm"] + 0.1, 2))      # 量子化の刻みの半分（その計算の面の箱の x の長さ ÷ 65535 ÷ 2）+ 0.1 mm（見直し L1）

# ------------------------------------------------------------------ 煙の試しの数（見直し H3・H4・M8・L4 の後）
kk = K0
s2_lat = {}
for ang in (30, 45):
    p_ = kk * math.sin(math.radians(ang))
    s2_lat[str(ang)] = dict(lateral_wavenumber=r(p_, 5), node_spacing_m=r(math.pi / p_, 2), first_node_y_m=r(0.5 * math.pi / p_, 2),
                            amp_factor_at_y={str(y): r(abs(math.cos(p_ * y)), 3) for y in (0, 18, 36, 66)})
slab = {}
for dp_ in (0.5, 0.34375, 0.25, 0.1767578125):
    ly_ = 4 * 2 * dp_
    n_ = rho(dp_) * 180.0 * ly_ * D
    fr_ = 48 * FPS
    slab[str(dp_)] = dict(Ly_m=ly_, particles_M=r(n_ / 1e6, 2),
                          minutes=[r(n_ * R_PRE_LO * fr_ / 60 * (FINE_FACTOR if dp_ < 0.2 else 1.0), 1),
                                   r(n_ * R_PRE_HI * fr_ / 60 * (FINE_FACTOR if dp_ < 0.2 else 1.0), 1)])
smoke = dict(
    S2=dict(box_x=[0.0, 180.0], inlet=[0.0, 36.0], exit=[144.0, 180.0], box_y=[0.0, 108.0], side=[72.0, 108.0], dp=0.5,
            amp_per_component_m=1.0, t_end_s=48.0, windows_s=[24.0, 45.0], points_xy=[[72.0, 0.0], [72.0, 18.0], [108.0, 0.0], [108.0, 18.0], [72.0, 66.0]],
            amp_tol_rel=0.05, dir_tol_deg=3.0, lateral=s2_lat,
            note_ja="y 36 m は ±30° の組の節（|cos| ≈ 0）なので点にしない（見直し H4）。向きは y 0〜70 m の振幅の横の形 |cos(p y)| に合わせた p から asin(p/k) で出す（FLIP の速さの誤りが入らない）"),
    S2b=dict(slab_x=[0.0, 180.0], band=[0.0, 36.0], exit=[144.0, 180.0], cells_y=4, amp_m=2.0, t_end_s=48.0, points_x=[40.0, 56.0],
             windows_s=[21.0, 42.0], per_dp=slab,
             note_ja="2D の板（y の両側は閉じた壁）で、直角に来る周期 7 s・振幅 2 m の波を 36 m の帯（FLIP42 の重み、壁のなだらかさ 9 m）で起こし、帯の出口の振幅の比 r0(dp) を測る（見直し H3）"),
    S3b=dict(note_ja="起こす帯（FLIP42 の重み）の跳ね返り：2D の板（粒子 0.5 m）で、反対の端から周期 7 s・振幅 1 m の波を目標 0 の起こす帯（36 m・72 m）へ送り、跳ね返りを測る。理論の値（36 m で 33 %、72 m で 13 %）の 1.5 倍を越えたら、RPT05 の帯の作りを伺う（見直し M8）",
             theory_CR_normal={"36": band_refl.get("xd_36m(0.50lambda)", {}).get("FLIP42_inlet_weight_CR", {}).get("0"),
                               "72": band_refl.get("xd_72m(1.00lambda)", {}).get("FLIP42_inlet_weight_CR", {}).get("0")}),
    S1=dict(wall_layer_vs_interior_m=0.02,
            note_ja="静かな水面を、y = 0 の壁に接する格子の層と、内側（y 10 m より先）で別に出し、差が 0.02 m 以下。越えたら N1 を y = 0 の断面だけで別に出して引く（見直し L4）"),
    S4=dict(t_le0_eta_m=0.02, t_le0_speed_ms=0.02,
            note_ja="t0（−2 s）での表の目標（壁のなだらかさを掛けた物）が |η| ≤ 0.02 m・水平の速さ ≤ 0.02 m/s（見直し H1）"),
)
ckpt_rule = dict(M1_keep_all_from_s=30.0,
                 note_ja="M1 の途中保存は、計算の中で巻き始めを見つけるまで、時刻 30 s（論文の tBP の 0.8 倍 − 7 s = 31.6 s より前）より後の物を消さない。見つけた後は M1h の始めに使う 2 個と、いちばん新しい 2 個を残す（見直し L3。消すのは利用者の許しの後だけ）")

out = dict(
    schema="flip45_plan_numbers_v2", date="2026-10-12",
    note_ja="FLIP45 計画（plan_ja.md）の数。流体の計算はしていない。費用は FLIP42 の 2D の記録からの推定で、3D の 1 コマの秒は V1 で測る",
    sources={k: dict(path=v.replace(ROOT + "/", ""), sha256=sha(v)) for k, v in SRC.items()},
    constants=dict(g=G, depth_m=D, Omega=OM, T_s=r(T, 4), k=r(K0, 6), lambda_m=r(L0, 3), c_ms=r(C0, 3), cg_ms=r(CG0, 3), kh=r(K0 * D, 4),
                   flap_F=r(F0, 5), A_star_m=r(A_STAR, 4), xf_m=XF, half_width_wall_m=LH, modes_J=J, sqrt_d_over_g_s=r(TSCALE, 4),
                   fps=FPS, ramp="tanh(t/T)", stroke_sign_ja="So > 0 で水の側（+x）へ倒れる（fochesato_ja.md §5.1。式 (17)・(18) の読み）"),
    cases=case_out, crosscheck_r45=crosscheck, bem_table1=BEM,
    flip42_records=rec, cost_model=dict(rho_particles_per_m3_at_025=r(RHO_025, 2), r_pre_lo_us=r(R_PRE_LO * 1e6, 4), r_pre_hi_us=r(R_PRE_HI * 1e6, 4),
                                        m_post_lo=M_POST_LO, m_post_hi=M_POST_HI, fine_factor=r(FINE_FACTOR, 3), chain=CHAIN,
                                        surf_us_per_particle=r(SURF_US, 4), surf_layer_m=[2.5, 5.0], tri_per_m2_025=TRI_025, tri_per_m2_05=TRI_05,
                                        custom_B_per_tri=CUSTOM_B_PER_TRI, abc_B_per_tri=ABC_B_PER_TRI, ckpt_B_per_particle=CKPT_B_PER_PARTICLE,
                                        ckpt_B_per_cell_hi=CKPT_B_PER_CELL_HI, launch_s=LAUNCH_S, air_m=AIR,
                                        free_G_GB=FREE_G_GB, free_F_GB=FREE_F_GB, stop_free_GB=STOP_FREE_GB,
                                        end_lo_s={k: r(v, 1) for k, v in END_LO.items()}, onset_lo_s={k: r(v, 1) for k, v in ONSET_LO.items()},
                                        t_surf0_s=T_SURF0),
    layouts={k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in LAYOUTS.items()},
    runs=RUNS, sequences=SEQ, human_gaps_h=GAPS, totals=tot, preview_schedule=prev, schedule=sched,
    band_reflection_theory=band_refl, reflection_return=t_return, criteria=criteria, unity=unity,
    smoke=smoke, ckpt_rule=ckpt_rule,
)


def dump(o):
    return json.dumps(o, ensure_ascii=False, indent=1, sort_keys=False)


os.makedirs(OUTDIR, exist_ok=True)
OUT = OUTDIR + "/plan_numbers.json"
txt = dump(out)
if "--freeze" in sys.argv:
    cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if cur != txt:
        print("plan_numbers.json differs from this tool's output; run without --freeze first")
        sys.exit(1)
    files = [OUTDIR + "/plan_ja.md", OUT, os.path.abspath(__file__), OUTDIR + "/review_ja.md"]
    fr = dict(frozen_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
              frozen=[dict(path=f.replace("\\", "/").replace(ROOT + "/", ""), sha256=sha(f), bytes=os.path.getsize(f)) for f in files])
    with open(OUTDIR + "/plan_frozen.json", "w", encoding="utf-8") as f:
        json.dump(fr, f, ensure_ascii=False, indent=1)
    print("frozen", OUTDIR + "/plan_frozen.json")
    sys.exit(0)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
print("wrote", OUT, hashlib.sha256(txt.encode("utf-8")).hexdigest())
