# -*- coding: utf-8 -*-
"""FLIP39 D2：仕組みの調べに添える、線形理論だけの見積もり（流体の計算ではない）。
出力：G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D2/estimates.json

中身
 1. 分散の関係：周期と水深ごとの波長・速さ・群速度
 2. 浅くなることによる高まり（線形の浅水係数）：60 m → 26 m など。グリーンの法則（h^-1/4）と並べる
 3. 幅 240 m（両側が滑る壁）の水路で伝わる横の形の数と角度（幅 480 m＝壁を対称の面に使う場合も）
 4. 分散による集中（一方向・平らな海・線形）：造波の位置で最も高い山 と 集まった所の山 の比
 5. 逆向きの流れによる高まり（波の作用の保存・深い海）と、波が止められる流れの速さ
 6. 変調の不安定（Benjamin-Feir）が 1 回 e 倍に育つのに要る距離
 7. イリバーレン数（斜面と波の険しさ）
どれも線形（または弱い非線形の公式）の見積もりで、FLIP の粘り・格子の粗さ・砕けは入らない。
"""
import json
import numpy as np

G = 9.81
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D2/estimates.json"


def kdisp(om, h):
    om = np.asarray(om, float)
    h = np.asarray(h, float)
    k = om * om / G / np.sqrt(np.tanh(om * om * h / G))
    for _ in range(50):
        th = np.tanh(k * h)
        f = G * k * th - om * om
        df = G * th + G * k * h * (1 - th * th)
        k = k - f / df
    return k


def wave(T, h):
    om = 2 * np.pi / T
    k = float(kdisp(om, h))
    kh = k * h
    n = 0.5 * (1 + 2 * kh / np.sinh(2 * kh))
    c = om / k
    return dict(T=T, h=h, L=2 * np.pi / k, k=k, kh=kh, c=c, cg=n * c, n=n)


def ks(T, h):
    w = wave(T, h)
    return 1.0 / np.sqrt(w["n"] * np.tanh(w["kh"]))  # 深い海に対する浅水係数


res = {"note": "線形理論の見積もり。FLIP の計算ではない。g=9.81"}

# 1. 分散
tab = []
for T in (8, 10, 12, 14, 16):
    for h in (26, 40, 60, 80, 100, 1e4):
        w = wave(T, h)
        tab.append({kk: round(float(v), 3) for kk, v in w.items()})
res["dispersion"] = tab

# 2. 浅水変形
sh = []
for T in (10, 12, 14, 16):
    for h1, h2 in ((60, 26), (60, 20), (80, 26), (100, 26), (60, 15)):
        r = ks(T, h2) / ks(T, h1)
        sh.append(dict(T=T, h_from=h1, h_to=h2, linear_ratio=round(float(r), 3),
                       greens_law_ratio=round(float((h1 / h2) ** 0.25), 3),
                       kh_from=round(wave(T, h1)["kh"], 3), kh_to=round(wave(T, h2)["kh"], 3)))
res["shoaling"] = sh

# 3. 水路の横の形（両側が滑る壁：η ∝ cos(nπ(z+W/2)/W)）
modes = []
for W in (240.0, 480.0):
    for T in (8, 10, 12, 14, 16):
        for h in (26, 60, 80):
            w = wave(T, h)
            nmax = int(np.floor(W * w["k"] / np.pi))
            ang = [round(float(np.degrees(np.arcsin(n * np.pi / (W * w["k"])))), 1) for n in range(nmax + 1)]
            sym = [a for n, a in enumerate(ang) if n % 2 == 0]  # 中央に腹（対称）の形
            modes.append(dict(W=W, T=T, h=h, L=round(w["L"], 1), n_propagating=nmax + 1,
                              angles_deg=ang, symmetric_angles_deg=sym))
res["channel_modes"] = modes


# 4. 分散による集中（一方向、平らな海、線形）
def focus_ratio(Tc, h, xf, bw, spec="flat", N=96):
    fc = 1.0 / Tc
    f = np.linspace(fc * (1 - bw / 2), fc * (1 + bw / 2), N)
    if spec == "flat":          # Rapp & Melville 型：成分の振幅をそろえる
        a = np.ones(N)
    else:                       # JONSWAP γ=3.3 の形（NewWave の重み）
        fp = fc
        sig = np.where(f <= fp, 0.07, 0.09)
        S = f ** -5 * np.exp(-1.25 * (fp / f) ** 4) * 3.3 ** np.exp(-((f - fp) ** 2) / (2 * sig ** 2 * fp ** 2))
        a = S
    a = a / a.sum()             # 集まった所の線形の山 = 1
    om = 2 * np.pi * f
    k = kdisp(om, h)
    cg = np.array([wave(1 / fi, h)["cg"] for fi in f])
    # 造波の位置 x=0 の時系列（焦点の時刻 tf=0 の前後）。成分の間隔 δf の周期 1/δf より短い窓だけを見る
    span = xf / cg.min() + 6 * Tc
    t = np.arange(-span, 2 * Tc, Tc / 40)
    eta0 = (a[:, None] * np.cos(k[:, None] * (0 - xf) - om[:, None] * t[None, :])).sum(0)
    # 群が造波の位置を通る長さ（包絡が 0.2 を越える時間）
    from scipy.signal import hilbert
    env = np.abs(hilbert(eta0))
    above = t[env > 0.2 * env.max()]
    dur = float(above.max() - above.min()) if above.size else 0.0
    S = float((a * k).sum())    # 集まった所の振幅 1 m あたりの群の険しさ Σ a_n k_n
    return dict(Tc=Tc, h=h, xf=xf, bw=bw, spec=spec,
                ratio_focus_over_wavemaker_max=round(float(1.0 / np.abs(eta0).max()), 3),
                group_duration_at_wavemaker_s=round(dur, 1),
                S_per_metre=round(S, 5),
                A_focus_at_S025_m=round(0.25 / S, 2), A_focus_at_S034_m=round(0.34 / S, 2))


foc = []
for spec in ("flat", "jonswap"):
    for Tc in (10, 12, 14, 16):
        for h in (60, 80, 100):
            for xf in (300, 450, 600):
                for bw in (0.6, 1.0):
                    foc.append(focus_ratio(Tc, h, xf, bw, spec))
res["dispersive_focusing"] = foc

# 4b. 断面の水槽を延ばした場合（焦点まで 800〜1400 m、水深 80 m、帯域 ±50 %）
long = []
for Tc in (12, 14):
    for xf in (800.0, 1000.0, 1200.0, 1400.0):
        for spec in ("flat", "jonswap"):
            long.append(focus_ratio(Tc, 80.0, xf, 1.0, spec))
with open(OUT.replace("estimates.json", "focus_long_tank.json"), "w", encoding="utf-8") as fo:
    json.dump({"note": "線形の見積もり。長い断面の水槽（2.5D）を仮定。水深 80 m、帯域 1.0", "cases": long}, fo, ensure_ascii=False, indent=1)


# 5. 逆向きの流れ（深い海、波の作用の保存。Longuet-Higgins & Stewart 1961 の形）
def current_amp(T, U):
    om = 2 * np.pi / T
    # 絶対の周波数 ω を保つ：ω = σ + kU、σ² = g k（深い海）。U<0 が逆向き
    ks_ = np.linspace(1e-4, 5, 200000) * om * om / G
    sig = np.sqrt(G * ks_)
    F = sig + ks_ * U - om
    i = np.where(np.sign(F[:-1]) != np.sign(F[1:]))[0]
    if i.size == 0:
        return None
    k = ks_[i[0]]
    s = np.sqrt(G * k)
    cgr = 0.5 * s / k
    k0 = om * om / G
    cg0 = 0.5 * om / k0
    # 作用 A = E/σ、作用の流れ (cg_r + U) A は場所によらず変わらない
    E_ratio = (cg0 / om) / ((cgr + U) / s)
    return dict(T=T, U=U, k_over_k0=round(float(k / k0), 3), H_ratio=round(float(np.sqrt(E_ratio)), 3),
                steepness_ratio=round(float(np.sqrt(E_ratio) * k / k0), 3))


cur = {"blocking_U_deep_ms": {str(T): round(G * T / (2 * np.pi) / 4, 2) for T in (8, 10, 12, 14, 16)}, "cases": []}
for T in (10, 12, 14):
    for U in (-0.5, -1.0, -2.0, -3.0, -4.0):
        r = current_amp(T, U)
        if r:
            cur["cases"].append(r)
res["opposing_current"] = cur

# 6. 変調の不安定：e 倍に育つ距離 ≈ 1/(k ε²)（深い海、最も速い成長 ω ε²/2、群速度 c/2）
mi = []
for T in (8, 10, 12, 14):
    w = wave(T, 1e4)
    for eps in (0.05, 0.1, 0.15, 0.2):
        Lgrow = 1.0 / (w["k"] * eps * eps)
        mi.append(dict(T=T, ka=eps, L_deep=round(w["L"], 1), efold_distance_m=round(Lgrow, 0),
                       efold_in_wavelengths=round(Lgrow / w["L"], 1)))
res["modulational_instability"] = mi
res["MI_kh_threshold_note"] = "有限水深では kh > 1.363 でだけ不安定。下の kh_at_60m を見る"
res["kh_at_60m"] = {str(T): round(wave(T, 60)["kh"], 3) for T in (8, 10, 12, 14, 16)}

# 7. イリバーレン数 ξ0 = tanβ / sqrt(H0/L0)
ib = []
for T in (10, 12, 14, 16):
    L0 = G * T * T / (2 * np.pi)
    for H0 in (8, 12, 16, 20):
        for slope in (10, 6, 4, 3):
            xi = (1 / slope) / np.sqrt(H0 / L0)
            typ = "spilling" if xi < 0.5 else ("plunging" if xi < 3.3 else "surging/collapsing")
            ib.append(dict(T=T, H0=H0, slope="1:%d" % slope, xi0=round(float(xi), 2), type=typ))
res["iribarren"] = ib

# 8. フルード相似：McAllister ら 2019 の FloWave（直径 25 m・水深 2 m）を 1:35 に直す
res["froude_flowave_1to35"] = dict(diameter_m=25 * 35, depth_m=2 * 35, time_factor=round(35 ** 0.5, 3))

with open(OUT, "w", encoding="utf-8") as fo:
    json.dump(res, fo, ensure_ascii=False, indent=1)
print("wrote", OUT)
