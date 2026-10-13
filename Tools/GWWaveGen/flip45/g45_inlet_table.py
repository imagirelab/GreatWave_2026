# -*- coding: utf-8 -*-
"""FLIP45：入口の表（帯の目標の線形の場）を作る（numpy だけ。py -3.10 -I。Houdini は使わない）。
2026-10-12 進行役が新しく書いた。計画 plan_ja.md §3.1・§4.1・§10.1 の g45_inlet_table.py。

目標の場（計画 §4.1）：Fochesato ら 2007 の水槽（幅 600 m、横は水を通さない壁、x = 0 の全幅に底で回る板の列）の線形の過渡。
  板の振れを横の形 cos(q_j y)（q_j = jπ/300 m、j = 0〜60）に分け、周波数ごと（0.05〜3 rad/s、刻み 2π/3276.8 s）に板の伝達で運ぶ。
  x > 0 で消えていく形を含む全部の形を足す。立ち上げ R(t) = tanh(t/T)（既定。ramp_kind "tanh"）。計画 §2 の V3 だけは
  R(t) = 0.5{1 + tanh(2t/T − 3)}（ramp_kind "tanh_s"。t < 0 は 0 で、t = 0 で 0.0025 跳ぶ。r45_gen_numbers.py・r45_fgd07_walled_linear.py の
  tanh_s と同じ形）。2026-10-12 12:44 に足した（別の者の確かめ check_ja.md の F1：V3 の設定が V1 と同じだった）。
  解き方は p45_plan_numbers.py の transient・band_precursor と同じ
  （ラプラス変換で窓の折り返しを消し、負の時刻は窓の終わりに折り返った所を t − TW に戻す）。p45 は読み込むと走って plan_numbers.json を
  書くので読み込まず、成分を作る関数をここへ写した（plan_numbers.json の cases の値と照らし合わせる。check_cases）。
表の中身（帯の VEX が読む）：水面 η(x, y, t) と水平の流速（x の向き U・横の向き V）。流速の深さの扱いは二つ（計画 §4.1、煙の試し S4 で決める）：
  method "nb"（Ω の深さの形を使う狭い帯の近似）：水面の高さの U・V だけを持ち、VEX で cosh(K0 (z' + h))/cosh(K0 h) を掛ける。
  method "depth"（深さごとの表。2026-10-12 の S4 (b) で狭い帯の近似が外れたので既定にした。record_ja.md）：z' = 0・−4・−8・−12・−16・−20 m の
    6 つの深さで、周波数ごとの深さの形 cosh(k (z' + h))/cosh(k h) を掛けた正しい流速を、Ω の深さの形で割った値 U0〜U5・V0〜V5 を持つ。
    VEX は z' の間を線形に補って Ω の深さの形を掛ける（numpy の試しで、中間の深さの差は各深さの最大の 1.5 % 以内）。
  z' は Wheeler の伸ばし h (z − η)/(h + η)（FLIP44 と同じ）。
  入口の利得 G(dp, θ_j) を横の形 j ごとに掛ける（計画 §4.1。θ_j = asin(q_j/k)、45° より斜めと消えていく形は 45° の値）。
  壁のなだらかさ E と横の帯の切り替えは VEX で掛ける（表には入れない）。
試しの目標（煙の試し S2a・S2b・S2c・S3・S3b）：平らな一つの波（向き +x か −x）、y = 0 で写した ±θ の組、0。立ち上げは同じ tanh(t/T)（ramp_kind で替えられる）。
表の格子：x 1 m・y 1 m・t 0.1 s（FFT の刻みそのもの）。Houdini の体積の軸は X = x、Y = t、Z = y（g45_run.py が bgeo にする）。
使い方：
  py -3.10 -I g45_inlet_table.py --case F45 --layout L1 --dp 0.5 --t-end 69.5 --out <npz> [--gain-file <json>|--no-gain] [--ramp tanh|tanh_s]
  py -3.10 -I g45_inlet_table.py --check-cases     （p45 の成分と plan_numbers.json の cases の照らし合わせだけ）
"""
import os, sys, json, math, time, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC

G, D, OM, T, K0, F0, LH, J = GC.G, GC.D, GC.OM, GC.T, GC.K0, GC.F0, GC.LH, GC.J
XF = GC.XF
A_STROKE_F45 = 0.2
QJ = np.arange(J + 1) * math.pi / LH


def k_complex(om):
    om = np.asarray(om, dtype=complex)
    k = np.array([GC.k_real(abs(w.real)) if abs(w.real) > 1e-6 else 1e-6 for w in om], dtype=complex)
    for _ in range(50):
        th = np.tanh(k * D)
        f = G * k * th - om * om
        df = G * th + G * k * D * (1 - th * th)
        k = k - f / df
    return k


def flap_F(k):
    kd = k * D
    return 4 * np.sinh(kd) * (1 - np.cosh(kd) + kd * np.sinh(kd)) / (kd * (np.sinh(2 * kd) + 2 * kd))


# ------------------------------------------------------------------ 成分（p45_plan_numbers.py の case_uniform・case_cross・そろえ方を写した）
def theta_uniform(thmax, n=30):
    return np.linspace(-thmax, thmax, n)


_th45 = theta_uniform(45.0)
A_STAR = float((A_STROKE_F45 * F0 / np.cos(np.radians(_th45))).sum())


def case_uniform(name, thmax):
    th = theta_uniform(thmax)
    w = 1.0 / np.cos(np.radians(th))
    a = A_STAR / (F0 * w.sum())
    return dict(name=name, kind="uniform", theta=th, stroke=np.full_like(th, a), A=a * F0 * w)


def case_cross(name, dtheta, sig, n_per=15, nsig=1.5):
    mu = dtheta / 2
    tp = np.linspace(mu - nsig * sig, mu + nsig * sig, n_per)
    th = np.concatenate([-tp[::-1], tp])
    wp = np.exp(-0.5 * ((tp - mu) / sig) ** 2)
    wgt = np.concatenate([wp[::-1], wp])
    A = A_STAR * wgt / wgt.sum()
    return dict(name=name, kind="cross", theta=th, stroke=A * np.cos(np.radians(th)) / F0, A=A)


def proj(p):
    I = LH * (np.sinc((p - QJ) * LH / math.pi) + np.sinc((p + QJ) * LH / math.pi))
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


def steady(P, Q, x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    Z = np.zeros(np.broadcast(x, y).shape, dtype=complex)
    for P1, Q1, q1 in zip(P, Q, QJ):
        if abs(P1) + abs(Q1) < 1e-14:
            continue
        kx = np.sqrt(K0 * K0 - q1 * q1 + 0j)
        kx = np.conj(kx) if kx.imag != 0 else kx
        if kx.imag > 0:
            kx = -kx
        Z = Z + (P1 - 1j * Q1) * 1j * F0 * (K0 / kx) * np.exp(-1j * kx * x) * np.cos(q1 * y)
    return Z


def make_cases():
    cs = {c["name"]: c for c in [case_uniform("F45", 45.0), case_uniform("F40", 40.0),
                                  case_cross("X45", 45.0, 20.0), case_cross("X60", 60.0, 20.0)]}
    xsp = np.arange(100.0, 340.01, 1.0)
    P, Q = modes(cs["F45"])
    pk45 = float(np.abs(steady(P, Q, xsp, 0.0)).max())
    for c in cs.values():
        if c["kind"] == "cross":
            P, Q = modes(c)
            f = pk45 / float(np.abs(steady(P, Q, xsp, 0.0)).max())
            c["A"] = c["A"] * f
            c["stroke"] = c["stroke"] * f
    return cs


CASES = make_cases()


def check_cases(plan=None):
    """plan_numbers.json の cases（丸めた値）と、ここで作った成分の差。返り値 dict（ok は丸めの幅に入ったか）。"""
    plan = plan or GC.load_plan()
    out = {}
    for n, c in CASES.items():
        pc = plan["cases"][n]
        dth = float(np.max(np.abs(np.array(pc["theta_deg"]) - c["theta"])))
        dst = float(np.max(np.abs(np.array(pc["stroke_m"]) - c["stroke"])))
        dA = float(np.max(np.abs(np.array(pc["A_m"]) - c["A"])))
        dsum = abs(float(pc["sum_A_m"]) - float(c["A"].sum()))
        out[n] = dict(max_dtheta_deg=dth, max_dstroke_m=dst, max_dA_m=dA, dsumA_m=dsum,
                      ok=bool(dth <= 6e-4 and dst <= 6e-4 and dA <= 6e-6 and dsum <= 6e-5))
    return out


# ------------------------------------------------------------------ 周波数の刻み（p45 と同じ）
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


# 立ち上げの形（計画 §4.1・§2 の V3）。名前 → (表の情報に書く式, 関数)。関数は t ≥ 0 の値（t < 0 は板が動かないので 0。FFT の窓は t ≥ 0 だけ）
RAMPS = {
    "tanh": ("tanh(t/T)", lambda t: np.tanh(t / T)),                                  # 計画 §4.1 の立ち上げ（V1・M1 など全部）
    "tanh_s": ("0.5{1+tanh(2t/T-3)}", lambda t: 0.5 * (1 + np.tanh(2 * t / T - 3))),  # 計画 §2 の V3（立ち上げの感度。t = 0 で 0.0025）
}


def check_ramp(kind):
    if kind not in RAMPS:
        raise ValueError("立ち上げの形 %r は使わない（%s だけ）" % (kind, "・".join(RAMPS)))
    return kind


def ramp(t, kind="tanh"):
    return RAMPS[check_ramp(kind)][1](np.asarray(t))


_SPEC_CACHE = {}


def paddle_spectra(kind="tanh"):
    """板の振れ R(t)·cos(Ωt)・R(t)·sin(Ωt) に e^{−σt} を掛けた物の rfft（立ち上げの形ごとに一度だけ作る）。"""
    kind = check_ramp(kind)
    if kind not in _SPEC_CACHE:
        R = ramp(TT, kind)
        damp = np.exp(-SIG * TT)
        _SPEC_CACHE[kind] = (np.fft.rfft(R * np.cos(OM * TT) * damp), np.fft.rfft(R * np.sin(OM * TT) * damp))
    return _SPEC_CACHE[kind]


SC, SS = paddle_spectra("tanh")      # 既定の立ち上げ（前からの名前。ほかの道具が読む）


def time_index(times):
    """表の時刻（0.1 s の倍数）→ FFT の窓の番号（負の時刻は窓の終わりに折り返った所）。"""
    n = np.round(np.asarray(times, float) / DT).astype(np.int64)
    if np.max(np.abs(n * DT - np.asarray(times, float))) > 1e-6:
        raise ValueError("表の時刻は 0.1 s の倍数")
    return np.where(n >= 0, n, NT + n)


def theta_of_mode():
    """横の形 j の角 θ_j = asin(q_j/k)（度）。消えていく形（q_j ≥ k）は 90。"""
    s = QJ / K0
    return np.where(s < 1.0, np.degrees(np.arcsin(np.clip(s, 0.0, 1.0))), 90.0)


def gains_for(dp, gainrec):
    """入口の利得 G(dp, θ_j)（計画 §4.1）。gainrec：{"r0": {"0.5": .., ...}, "r_theta_05": {"30": .., "45": ..}}。
    G = 1 / {r0(dp) · r(θ_j) / r0(0.5)}、r(0°) = r0(0.5)、θ は線形に補間、45° より斜めと消えていく形は 45° の値。"""
    if gainrec is None or gainrec.get("method") == "inlet_band_scalar":
        return np.ones(J + 1)          # 帯ごとの利得（入口の帯だけに VEX の in_gain で掛ける）の時は、表に利得を入れない
    r0 = float(gainrec["r0"][repr(float(dp))] if repr(float(dp)) in gainrec["r0"] else gainrec["r0"][str(dp)])
    r05 = float(gainrec["r0"]["0.5"])
    th_pts = np.array([0.0, 30.0, 45.0])
    r_pts = np.array([r05, float(gainrec["r_theta_05"]["30"]), float(gainrec["r_theta_05"]["45"])])
    th = np.minimum(theta_of_mode(), 45.0)
    r = np.interp(th, th_pts, r_pts)
    return 1.0 / (r0 * r / r05)


def mode_series(P, Q, xs, times, gains=None, depth_z=None, ramp_kind="tanh"):
    """横の形ごとの時系列。返り値 dict：eta[j, t, x]、U[j, t, x]（水面の高さの x の流速）、V[j, t, x]（横の流速は
    Σ_j (−q_j sin(q_j y)) V_j）。depth_z（z' の並び）を渡すと、Ud・Vd[j, z, t, x] に周波数ごとの深さの形を掛けた正しい値も返す。
    ramp_kind：立ち上げの形（RAMPS の名前。既定 tanh）。"""
    SC, SS = paddle_spectra(ramp_kind)
    xs = np.asarray(xs, float)
    idx = time_index(times)
    keep = np.exp(SIG * np.asarray(times, float))
    gains = np.ones(J + 1) if gains is None else np.asarray(gains, float)
    nj, nt, nx = J + 1, len(idx), len(xs)
    out = dict(eta=np.zeros((nj, nt, nx)), U=np.zeros((nj, nt, nx)), V=np.zeros((nj, nt, nx)))
    if depth_z is not None:
        dz = np.asarray(depth_z, float)
        out["Ud"] = np.zeros((nj, len(dz), nt, nx)); out["Vd"] = np.zeros((nj, len(dz), nt, nx))
    ph = None
    for j, (P1, Q1, q1) in enumerate(zip(P, Q, QJ)):
        if abs(P1) + abs(Q1) < 1e-12:
            continue
        X = (P1 * SC + Q1 * SS)[USE]
        kx = np.sqrt(KC * KC - q1 * q1)
        kx = np.where(kx.imag > 0, -kx, kx)
        E0 = X * (1j * FC * KC / kx)                      # x = 0 の水面（横の形あたり）
        ph = np.exp(-1j * np.outer(xs, kx))                # (nx, nω)
        facs = dict(eta=np.ones_like(KC), U=G * kx / OMC, V=1j * G / OMC)
        for nm, fac in facs.items():
            spec = np.zeros((nx, len(OMB)), dtype=complex)
            spec[:, USE] = (E0 * fac)[None, :] * ph
            s = np.fft.irfft(spec, n=NT, axis=1)[:, idx] * keep[None, :]
            out[nm][j] = gains[j] * s.T
        if depth_z is not None:
            for iz, zz in enumerate(dz):
                prof = np.cosh(KC * (zz + D)) / np.cosh(KC * D)
                for nm, fac in (("Ud", G * kx / OMC), ("Vd", 1j * G / OMC)):
                    spec = np.zeros((nx, len(OMB)), dtype=complex)
                    spec[:, USE] = (E0 * fac * prof)[None, :] * ph
                    s = np.fft.irfft(spec, n=NT, axis=1)[:, idx] * keep[None, :]
                    out[nm][j, iz] = gains[j] * s.T
    return out


def combine_y(ms, ys):
    """横の形を y で足す。返り値 eta・U・V[y, t, x]（float64）。"""
    ys = np.asarray(ys, float)
    Cc = np.cos(np.outer(ys, QJ))                       # (ny, nj)
    Ss = -QJ[None, :] * np.sin(np.outer(ys, QJ))
    nj, nt, nx = ms["eta"].shape
    res = {}
    for nm, M in (("eta", Cc), ("U", Cc), ("V", Ss)):
        res[nm] = (M @ ms[nm].reshape(nj, nt * nx)).reshape(len(ys), nt, nx)
    return res


# ------------------------------------------------------------------ 試しの目標（解析の式。立ち上げは同じ tanh(t/T)）
def test_field(spec, xs, ys, times, gain=1.0, ramp_kind="tanh"):
    """spec：{"kind": "plane", "amp": A, "dir": +1/−1} か {"kind": "pair", "amp": a, "theta_deg": θ} か {"kind": "zero"}。
    返り値 eta・U・V[y, t, x]。x の位相の原点は x = 0（箱の上流の壁）。"""
    xs = np.asarray(xs, float); ys = np.asarray(ys, float); tt = np.asarray(times, float)
    R = ramp(np.maximum(tt, 0.0), ramp_kind)
    if ramp_kind != "tanh":
        R = np.where(tt >= 0.0, R, 0.0)            # tanh_s は t = 0 で 0 でないので、t < 0 を 0 にする（tanh は前と同じ値のまま）
    R = R[None, :, None]
    shape = (len(ys), len(tt), len(xs))
    k = spec["kind"]
    if k == "zero":
        z = np.zeros(shape)
        return dict(eta=z, U=z.copy(), V=z.copy())
    if k == "plane":
        A = gain * float(spec["amp"]); s = float(spec.get("dir", 1.0))
        ph = s * K0 * xs[None, None, :] - OM * tt[None, :, None]
        eta = A * np.cos(ph) * R * np.ones((len(ys), 1, 1))
        U = s * A * (G * K0 / OM) * np.cos(ph) * R * np.ones((len(ys), 1, 1))
        return dict(eta=eta, U=U, V=np.zeros(shape))
    if k == "pair":
        a = gain * float(spec["amp"]); th = math.radians(float(spec["theta_deg"]))
        cx, sy = K0 * math.cos(th), K0 * math.sin(th)
        phi = cx * xs[None, None, :] - OM * tt[None, :, None]
        By = sy * ys[:, None, None]
        eta = 2 * a * np.cos(By) * np.cos(phi) * R
        U = 2 * a * (G * K0 * math.cos(th) / OM) * np.cos(By) * np.cos(phi) * R
        V = -2 * a * (G * K0 * math.sin(th) / OM) * np.sin(By) * np.sin(phi) * R
        return dict(eta=eta, U=U, V=V)
    raise ValueError(k)


# ------------------------------------------------------------------ 表を作る・読む
def grid_for(x0, x1, y0, y1, t0, t1, dx=1.0, dy=1.0, dt=DT):
    nx = int(math.ceil((x1 - x0) / dx - 1e-9)) + 1
    ny = int(math.ceil((y1 - y0) / dy - 1e-9)) + 1
    nt = int(math.ceil((t1 - t0) / dt - 1e-9)) + 1
    return (x0 + dx * np.arange(nx), y0 + dy * np.arange(ny), np.round((t0 + dt * np.arange(nt)) / DT) * DT)


ZLEV = (0.0, -4.0, -8.0, -12.0, -16.0, -20.0)      # 深さごとの表の深さ（z'、m）


def depth_profile(zp):
    return np.cosh(K0 * (np.asarray(zp, float) + D)) / math.cosh(K0 * D)


def _accumulate_case(P, Q, xs, ys, times, gains, method, levels, ramp_kind="tanh"):
    """横の形ごとに時系列を作り、すぐ y の形を掛けて足す（大きな配列を形の数だけ持たない）。返り値 dict（float32、[y, t, x]）。"""
    SC, SS = paddle_spectra(ramp_kind)
    idx = time_index(times)
    keep = np.exp(SIG * np.asarray(times, float))
    ny, nt, nx = len(ys), len(idx), len(xs)
    names = ["eta"] + (["U", "V"] if method == "nb" else ["U%d" % i for i in range(len(levels))] + ["V%d" % i for i in range(len(levels))])
    out = {nm: np.zeros((ny, nt, nx), np.float32) for nm in names}
    cosy = np.cos(np.outer(ys, QJ)); siny = -QJ[None, :] * np.sin(np.outer(ys, QJ))
    for j, (P1, Q1, q1) in enumerate(zip(P, Q, QJ)):
        if abs(P1) + abs(Q1) < 1e-12:
            continue
        X = (P1 * SC + Q1 * SS)[USE]
        kx = np.sqrt(KC * KC - q1 * q1)
        kx = np.where(kx.imag > 0, -kx, kx)
        E0 = X * (1j * FC * KC / kx)
        ph = np.exp(-1j * np.outer(xs, kx))

        def ser(fac):
            spec = np.zeros((nx, len(OMB)), dtype=complex)
            spec[:, USE] = (E0 * fac)[None, :] * ph
            return (gains[j] * (np.fft.irfft(spec, n=NT, axis=1)[:, idx] * keep[None, :]).T).astype(np.float32)   # (nt, nx)
        jobs = [("eta", np.ones_like(KC), cosy[:, j])]
        if method == "nb":
            jobs += [("U", G * kx / OMC, cosy[:, j]), ("V", 1j * G / OMC, siny[:, j])]
        else:
            for i, zl in enumerate(levels):
                pr = np.cosh(KC * (zl + D)) / np.cosh(KC * D) / depth_profile(zl)
                jobs += [("U%d" % i, G * kx / OMC * pr, cosy[:, j]), ("V%d" % i, 1j * G / OMC * pr, siny[:, j])]
        for nm, fac, wy in jobs:
            s_ = ser(fac)
            out[nm] += wy.astype(np.float32)[:, None, None] * s_[None, :, :]
    return out


def build(target, x_range, y_range, t_range, dp=None, gainrec=None, dx=1.0, dy=1.0, out=None, note="", method="depth", levels=ZLEV,
          ramp_kind="tanh"):
    """target："F45" などの例の名前か、試しの spec（dict）。返り値 (表の dict, 情報)。out を渡すと npz に書く。
    ramp_kind：立ち上げの形（"tanh" = tanh(t/T)、"tanh_s" = 0.5{1 + tanh(2t/T − 3)}。計画 §2 の V3 だけ tanh_s）。"""
    ramp_kind = check_ramp(ramp_kind)
    t_start = time.time()
    xs, ys, ts = grid_for(x_range[0], x_range[1], y_range[0], y_range[1], t_range[0], t_range[1], dx, dy)
    info = dict(target=target if isinstance(target, str) else dict(target), dp=dp, x0=float(xs[0]), dx=dx, nx=len(xs),
                y0=float(ys[0]), dy=dy, ny=len(ys), t0=float(ts[0]), dt=DT, nt=len(ts), K0=K0, h=D, g=G, Omega=OM, T=T,
                method=method, levels=[float(v) for v in levels] if method == "depth" else None,
                depth_profile=("Ω の深さの形で割った深さごとの正しい流速（VEX が Ω の深さの形を掛ける）" if method == "depth" else "narrowband_K0"),
                ramp=RAMPS[ramp_kind][0], ramp_kind=ramp_kind, note=note)
    if isinstance(target, str):
        c = CASES[target]
        P, Q = modes(c)
        gains = gains_for(dp, gainrec) if gainrec is not None else np.ones(J + 1)
        info["gains_by_mode"] = [float(v) for v in gains]
        info["theta_of_mode_deg"] = [float(v) for v in theta_of_mode()]
        tab = _accumulate_case(P, Q, xs, ys, ts, gains, method, levels, ramp_kind)
    else:
        gain = 1.0
        if gainrec is not None and gainrec.get("method") != "inlet_band_scalar" and target.get("kind") in ("plane", "pair"):
            th = 0.0 if target["kind"] == "plane" else abs(float(target["theta_deg"]))
            r0 = float(gainrec["r0"]["0.5"])
            r = np.interp(min(th, 45.0), [0.0, 30.0, 45.0], [r0, float(gainrec["r_theta_05"]["30"]), float(gainrec["r_theta_05"]["45"])])
            rdp = float(gainrec["r0"][repr(float(dp))])
            gain = 1.0 / (rdp * r / r0)
        info["gain_scalar"] = gain
        f = test_field(target, xs, ys, ts, gain, ramp_kind)
        tab = {"eta": f["eta"].astype(np.float32)}
        if method == "nb":
            tab["U"] = f["U"].astype(np.float32); tab["V"] = f["V"].astype(np.float32)
        else:                        # 試しの目標は Ω の深さの形そのもの（割った値は全部の深さで水面の値）
            for i in range(len(levels)):
                tab["U%d" % i] = f["U"].astype(np.float32); tab["V%d" % i] = f["V"].astype(np.float32)
    info["fields"] = sorted(tab.keys())
    info["max_abs"] = {k: float(np.abs(v).max()) for k, v in tab.items()}
    info["build_s"] = round(time.time() - t_start, 1)
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        np.savez(out, info=json.dumps(info, ensure_ascii=False), **tab)
        info["file"] = out
        info["sha256"] = GC.sha256_file(out)
    return tab, info


def load(path):
    d = np.load(path)
    info = json.loads(str(d["info"]))
    return {k: d[k] for k in info.get("fields", ["eta", "U", "V"])}, info


def sample(tab, info, x, y, t):
    """表の 3 次の線形の補間（Houdini の volumesample と同じ：格子の中心の間の 3 方向の線形）。x・y・t は同じ形の配列。"""
    x = np.asarray(x, float); y = np.asarray(y, float); t = np.asarray(t, float)
    fx = (x - info["x0"]) / info["dx"]; fy = (y - info["y0"]) / info["dy"]; ft = (t - info["t0"]) / info["dt"]
    res = {}
    i0 = np.clip(np.floor(fx).astype(int), 0, info["nx"] - 2); ax = np.clip(fx - i0, 0, 1)
    j0 = np.clip(np.floor(fy).astype(int), 0, info["ny"] - 2); ay = np.clip(fy - j0, 0, 1)
    k0 = np.clip(np.floor(ft).astype(int), 0, info["nt"] - 2); at = np.clip(ft - k0, 0, 1)
    for nm in tab:
        A = tab[nm].astype(np.float64)
        v = 0.0
        for dj, wy in ((0, 1 - ay), (1, ay)):
            for dk, wt in ((0, 1 - at), (1, at)):
                for di, wx in ((0, 1 - ax), (1, ax)):
                    v = v + wy * wt * wx * A[j0 + dj, k0 + dk, i0 + di]
        res[nm] = v
    return res


def table_velocity(tab, info, x, y, t, zp):
    """表の流速（VEX と同じ読み方）：(u, v)。zp は z'（伸ばした深さ、−h〜0）。"""
    s = sample(tab, info, x, y, t)
    zp = np.clip(np.asarray(zp, float), -D, 0.0)
    pr = depth_profile(zp)
    if info.get("method", "nb") == "nb":
        return s["U"] * pr, s["V"] * pr
    lev = info["levels"]; dz = -lev[1]
    f = np.clip(-zp / dz, 0, len(lev) - 1)
    k = np.minimum(np.floor(f).astype(int), len(lev) - 2); w = f - k
    U = np.zeros(np.shape(f)); V = np.zeros(np.shape(f))
    for i in range(len(lev)):
        wi = np.where(k == i, 1 - w, 0.0) + np.where(k + 1 == i, w, 0.0)
        U = U + wi * s["U%d" % i]; V = V + wi * s["V%d" % i]
    return U * pr, V * pr


def exact_points(target, pts, times, dp=None, gainrec=None, depth_z=(0.0,), ramp_kind="tanh"):
    """正しい線形の場（周波数ごとの深さの形）を点で。pts：[(x, y), ...]。返り値 eta[p, t]、u・v[p, z, t]。試しの spec は式のまま。"""
    times = np.asarray(times, float)
    dz = np.asarray(depth_z, float)
    if isinstance(target, str):
        c = CASES[target]
        P, Q = modes(c)
        gains = gains_for(dp, gainrec) if gainrec is not None else np.ones(J + 1)
        eta = np.zeros((len(pts), len(times))); u = np.zeros((len(pts), len(dz), len(times))); v = np.zeros_like(u)
        xs_u = sorted(set(float(p[0]) for p in pts))
        ms = mode_series(P, Q, xs_u, times, gains, depth_z=dz, ramp_kind=ramp_kind)
        for ip, (px, py) in enumerate(pts):
            ix = xs_u.index(float(px))
            cy = np.cos(QJ * py); sy = -QJ * np.sin(QJ * py)
            eta[ip] = cy @ ms["eta"][:, :, ix]
            for iz in range(len(dz)):
                u[ip, iz] = cy @ ms["Ud"][:, iz, :, ix]
                v[ip, iz] = sy @ ms["Vd"][:, iz, :, ix]
        return dict(eta=eta, u=u, v=v)
    # 試しの目標：深さの形は Ω の形そのもの（一つの周波数ではないが、立ち上げの後は Ω）
    eta = np.zeros((len(pts), len(times))); u = np.zeros((len(pts), len(dz), len(times))); v = np.zeros_like(u)
    for ip, (px, py) in enumerate(pts):
        f = test_field(target, [px], [py], times, ramp_kind=ramp_kind)
        eta[ip] = f["eta"][0, :, 0]
        for iz, zz in enumerate(dz):
            u[ip, iz] = f["U"][0, :, 0] * depth_profile(zz)
            v[ip, iz] = f["V"][0, :, 0] * depth_profile(zz)
    return dict(eta=eta, u=u, v=v)


def series_at(case, pts, times, ramp_kind="tanh"):
    """解析（N3・N5・N10・N11）の線形の目標：水面 η(t) を点で（利得なし。目標は線形の場そのもの）。pts：[(x, y)]。
    ramp_kind はその計算の表と同じ立ち上げ（cfg の table.ramp）。"""
    return exact_points(case, pts, times, depth_z=(0.0,), ramp_kind=ramp_kind)["eta"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case"); ap.add_argument("--layout"); ap.add_argument("--dp", type=float)
    ap.add_argument("--t-end", type=float); ap.add_argument("--t0", type=float, default=None)
    ap.add_argument("--out"); ap.add_argument("--gain-file", default=None); ap.add_argument("--no-gain", action="store_true")
    ap.add_argument("--check-cases", action="store_true"); ap.add_argument("--ramp", default="tanh", choices=sorted(RAMPS))
    a = ap.parse_args()
    GC.unthrottle_self()
    if a.check_cases:
        print(json.dumps(check_cases(), ensure_ascii=False, indent=1))
        return
    plan = GC.load_plan()
    L = plan["layouts"][a.layout]
    b = GC.box(L, a.dp)
    gainrec = None
    if not a.no_gain:
        gf = a.gain_file or GC.GAIN_FILE
        gainrec = json.load(open(gf, encoding="utf-8"))
    t0 = a.t0 if a.t0 is not None else (-2.0 if b["x0"] == 0.0 else 12.0)
    tab, info = build(a.case, (b["x0"], b["side_sw"] + 1.0), (0.0, b["W"]), (t0, a.t_end), dp=a.dp, gainrec=gainrec, out=a.out,
                      ramp_kind=a.ramp)
    print(json.dumps({k: v for k, v in info.items() if k not in ("gains_by_mode", "theta_of_mode_deg")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
