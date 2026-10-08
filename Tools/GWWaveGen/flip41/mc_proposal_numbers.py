# -*- coding: utf-8 -*-
"""FLIP41 まとめ（10/9）：提案（Docs/Progress/FLIP_MethodCheck_ja.md §6）の数を出す（py -3.10、numpy だけ）。
流体の計算はしない。式と、FLIP41 の確かめで測った値（summary.json）と、FLIP39 R の時間の記録からの見積もり。

1. 嵐と高さ：レイリー分布の 3 時間の最大の見込み（最頻値 Hs·√(ln N / 2)、N = 3 h ÷ (Tp/1.3)。wind_estimates.py と同じ取り方）。
   10 m がその嵐の 3 時間の最大の見込みになる Hs と、それを吹送距離の式（JONSWAP、深い海）で作る風速。
2. その周期の波が、神奈川沖の水深でどれだけ遅くなるか（線形の分散の式）と、崩れの限界（Miche）。
3. NewWave（Tromans ら 1991）の一方向の線形の群：焦点から手前の距離ごとに、そこを通る間の水面の最大が焦点の何割か。
   FLIP の窓をどこから始めるかの目安（窓の入口の険しさが小さい所）。
4. FLIP の細かさ：FLIP41 B1 で速さ 1 %・減り 5 % に両方入った「波長/格子 ≥ 150、振幅/格子 ≥ 2」をピーク周期に当てる。
5. 3D の窓の計算時間：FLIP39 R（270 × 100 m、粒子 0.3 m、1 コマ 15〜16 秒）からの比（格子の数 ∝ 粒子^-3、刻み ∝ 粒子^-1 まで幅をとる）。
6. 窓の中の風（Miles 型の圧力、β = 34、Plant 1982）が窓を渡る間に増やす高さと、FLIP41 で測った数値の減りの比べ。
使い方: py -3.10 -B mc_proposal_numbers.py  → Unity/Build/FLIP41/report/mc_proposal_numbers.json
"""
import json
import math
import os

import numpy as np

G = 9.80665          # Houdini の重力の既定値（v_lin.py と同じ）
RHO_A = 1.2
RHO_FLIP = 1000.0    # FLIP の水の密度の既定値（T1・T2 と同じ）
ROOT = r"G:/Unity/GreatWave_2026_Fresh"
OUT = ROOT + "/Unity/Build/FLIP41/report/mc_proposal_numbers.json"


def wavenumber(om, h):
    k = om * om / G
    for _ in range(100):
        f = G * k * math.tanh(k * h) - om * om
        df = G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2
        k -= f / df
    return k


def wave(T, h):
    om = 2 * math.pi / T
    k = wavenumber(om, h)
    c = om / k
    n = 0.5 * (1 + 2 * k * h / math.sinh(2 * k * h))
    c0 = G * T / (2 * math.pi)
    return dict(T=T, h=h, k=k, L=2 * math.pi / k, kh=k * h, c=c, cg=n * c, c_over_c0=c / c0,
                miche_H=0.142 * (2 * math.pi / k) * math.tanh(k * h))


def n3h(Tp):
    return 3 * 3600 / (Tp / 1.3)


def mpm(Hs, Tp):
    return Hs * math.sqrt(math.log(n3h(Tp)) / 2)


def fetch_law(U, F):
    chi = G * F / U ** 2
    Hs = 1.6e-3 * math.sqrt(chi) * U ** 2 / G
    Tp = 0.286 * chi ** (1 / 3) * U / G
    return Hs, Tp


def U_for_Hs(Hs, F):
    # Hs = 1.6e-3 sqrt(g F) U / g  (深い海の JONSWAP の式を U について解く)
    return Hs * G / (1.6e-3 * math.sqrt(G * F))


def depth_limited_Tp(h):
    kp = 1.363 / h  # Karimpour ら 2017
    return 2 * math.pi / math.sqrt(G * kp * math.tanh(kp * h))


def cd(U):
    if U < 11:
        return 1.2e-3
    return (0.49 + 0.065 * min(U, 25.0)) * 1e-3  # Large & Pond 1981、25 m/s より上は止める（wind_ja.md §1.3）


def jonswap(om, omp, gamma=3.3):
    sig = np.where(om <= omp, 0.07, 0.09)
    r = np.exp(-((om - omp) ** 2) / (2 * sig ** 2 * omp ** 2))
    return om ** -5 * np.exp(-1.25 * (omp / om) ** 4) * gamma ** r


def newwave_envelope(Tp, h, A, dists, sigma_deg=0.0, fmax=2.5, n=160):
    """線形 NewWave（焦点の頂 A、焦点は原点・時刻 0）。焦点から波の来る向きへ D 手前の点（中心の線の上）を
    群が通る間の水面の最大 / A と、その所の険しさ k_p·η_max。向きの広がりは正規分布（標準偏差 sigma_deg）。"""
    omp = 2 * math.pi / Tp
    om = np.linspace(0.5 * omp, fmax * omp, n)
    S = jonswap(om, omp)
    if sigma_deg <= 0:
        th = np.array([0.0]); Dn = np.array([1.0])
    else:
        s = math.radians(sigma_deg)
        th = np.linspace(-3 * s, 3 * s, 61); Dn = np.exp(-0.5 * (th / s) ** 2)
    W = S[:, None] * Dn[None, :]
    a = (A * W / W.sum()).ravel()
    k = np.array([wavenumber(w, h) for w in om])
    kx = (k[:, None] * np.cos(th)[None, :]).ravel()
    omm = np.repeat(om, len(th))
    kp = wavenumber(omp, h)
    tau = np.linspace(-200.0, 60.0, 5201)
    rows = []
    for D in dists:
        X = -float(D)
        eta = (a[None, :] * np.cos(kx[None, :] * X - omm[None, :] * tau[:, None])).sum(axis=1)
        m = float(np.abs(eta).max())
        rows.append(dict(D_m=float(D), max_over_A=round(m / A, 3), kp_eta=round(kp * m, 3)))
    return rows


def main():
    out = {"note_ja": "提案の数（FLIP_MethodCheck_ja.md §6）。流体の計算はしていない。式・FLIP41 の測った値・FLIP39 R の時間の記録からの見積もり"}

    # 1. 嵐と高さ
    H_target = 10.0
    sc = []
    for name, Hs, Tp in (("記録（2019 台風 15 号、東京港）", 3.39, 7.1),
                         ("文献の仮の嵐（Takagi の台風の半径 3 倍、横浜沖）", 4.0, 7.5),
                         ("C&N が引いた値", 5.6, 8.0)):
        N = n3h(Tp)
        p = math.exp(-2 * (H_target / Hs) ** 2)
        U35 = U_for_Hs(Hs, 35000.0)
        sc.append(dict(name=name, Hs=Hs, Tp_assumed=Tp, N_3h=round(N), Hmax_3h_mpm=round(mpm(Hs, Tp), 2),
                       p_H_gt_10_per_wave=float(f"{p:.1e}"), expected_count_H_gt_10_in_3h=float(f"{p * N:.1e}"),
                       storms_per_10m_event=round(1 / (p * N), 2),
                       U10_for_this_Hs_at_35km=round(U35, 1), Tp_fetch_law_at_35km=round(fetch_law(U35, 35000.0)[1], 2)))
    # 10 m が 3 時間の最大の見込みになる Hs（Tp は 7.5〜8.5 s の幅で）
    need = []
    for Tp in (7.5, 8.0, 8.5):
        Hs_req = H_target / math.sqrt(math.log(n3h(Tp)) / 2)
        winds = []
        for F_km in (10, 20, 35):
            U = U_for_Hs(Hs_req, F_km * 1000.0)
            _, Tp_f = fetch_law(U, F_km * 1000.0)
            winds.append(dict(F_km=F_km, U10_needed=round(U, 1), Tp_from_fetch_law=round(Tp_f, 2)))
        need.append(dict(Tp=Tp, Hs_needed=round(Hs_req, 2), ratio_to_record_3p39=round(Hs_req / 3.39, 2), winds=winds,
                         steep_Hs_over_L0=round(Hs_req / (G * Tp * Tp / (2 * math.pi)), 3)))
    out["storm"] = dict(H_target=H_target, scenarios=sc, Hs_for_10m_as_3h_mpm=need,
                        depth_limited_Tp={"h17": round(depth_limited_Tp(17), 2), "h25": round(depth_limited_Tp(25), 2),
                                          "h40": round(depth_limited_Tp(40), 2)},
                        record_wind_note_ja="台風 15 号の上陸時の 10 分平均の最大風速 41 m/s（Takagi & Takahashi の表 1、陸上・上陸時の値）")

    # 2. 水深の効き（神奈川沖の点の値 18〜50 m）
    out["depth"] = []
    for T in (5.0, 6.0, 7.0, 7.5, 8.0):
        for h in (15.0, 25.0, 40.0):
            w = wave(T, h)
            out["depth"].append(dict(T=T, h=h, kh=round(w["kh"], 2), L=round(w["L"], 1), c=round(w["c"], 2),
                                     cg=round(w["cg"], 2), c_over_deep=round(w["c_over_c0"], 3),
                                     miche_H=round(w["miche_H"], 1)))

    # 3. NewWave の群：窓をどこから始めるか（向きの広がり 0・20・30°）
    Tp, h = 7.5, 25.0  # (A) の吹送距離の式 7.1 s と (B) の 7.7 s の間
    A = H_target / 2  # 線形の頂（崩れる前の高さの半分）
    dists = [0, 80, 160, 250, 400, 600, 800]
    wp = wave(Tp, h)
    out["newwave"] = dict(Tp=Tp, h=h, A_focus=A, Lp=round(wp["L"], 1), cg_p=round(wp["cg"], 2),
                          by_spreading={f"sigma{s:g}": newwave_envelope(Tp, h, A, dists, sigma_deg=s) for s in (0.0, 20.0, 30.0)},
                          note_ja="線形。JONSWAP γ 3.3、0.5〜2.5 fp を 160 成分 × 向き 61。焦点の手前 D の中心の線の上で、群が通る間の水面の最大 ÷ 焦点の頂。kp·η は険しさの目安（Stokes の限界は約 0.44）")

    # 4. FLIP の細かさ（B1 の目安：波長/格子 ≥ 150、振幅/格子 ≥ 2）
    res = []
    for T in (6.0, 7.0, 7.5, 8.0):
        w = wave(T, h)
        grid = w["L"] / 150.0
        res.append(dict(T=T, h=h, L=round(w["L"], 1), grid_for_L150=round(grid, 2), particle=round(grid / 2, 2)))
    out["flip_resolution"] = dict(rule_ja="FLIP41 B1：速さ 1 %・減り 5 %/3 波長に両方入ったのは 振幅/格子 2〜3・波長/格子 150〜240 の組だけ（record_ja.md §3.2）",
                                  rows=res, grid_0p5_L_over_grid={str(T): round(wave(T, h)["L"] / 0.5, 0) for T in (5.0, 6.0, 7.0, 8.0)})

    # 5. 3D の窓の計算時間（FLIP39 R からの比）
    R_wall_per_sim_s = 15.5 * 24  # 1 コマ 15〜16 秒、24 コマ/秒（benchmarks_ja.md §4）
    R_area, R_dp = 270.0 * 100.0, 0.3
    boxes = []
    Lp, cgp = wp["L"], wp["cg"]
    for (D_in, Lz, dp) in ((250.0, 120.0, 0.3), (250.0, 120.0, 0.25), (400.0, 150.0, 0.3)):
        # 窓の長さ = 入口の帯 1 波長 + 焦点まで D_in + 焦点の後 80 m + 出口の帯 1.5 波長
        Lx = Lp + D_in + 80.0 + 1.5 * Lp
        f_area = Lx * Lz / R_area
        lo = R_wall_per_sim_s * f_area * (R_dp / dp) ** 3
        hi = R_wall_per_sim_s * f_area * (R_dp / dp) ** 4
        sim_s = D_in / cgp + 10.0   # 線形の解で窓を満たして始め（途中から始める）、群が焦点まで進み、崩れの 10 秒
        boxes.append(dict(D_focus_from_inlet=D_in, Lx=round(Lx), Lz=Lz, particle=dp, L_over_grid_peak=round(Lp / (2 * dp)),
                          wall_per_sim_s=[round(lo), round(hi)], sim_s=round(sim_s, 1),
                          wall_h=[round(lo * sim_s / 3600, 1), round(hi * sim_s / 3600, 1)]))
    out["box_cost"] = dict(ref_ja="FLIP39 R：270 × 100 m、粒子 0.3 m、1 コマ 15〜16 秒（約 372 秒/計算 1 秒）", rows=boxes,
                           note_ja="費用 ∝ 面積 × 粒子^-3〜^-4（格子の数と刻みの数）。周期 7.5 s・水深 25 m のピーク（波長 84 m、群の速さ 6.6 m/s）")

    # 6. 窓の中の風（Miles 型）と、測った数値の減り
    wind = []
    for U in (42.0, 54.0):  # (A) Hs 4.0 m・(B) Hs 5.2 m を吹送距離 35 km で作る風速
        ustar = math.sqrt(cd(U)) * U
        P0 = 34.0 * RHO_A * ustar ** 2
        for T in (7.0, 8.0):
            w = wave(T, h)
            om = 2 * math.pi / T
            gam = P0 * w["k"] * om / (RHO_FLIP * G)          # エネルギーの成長率（T2 で式どおりと確かめた形）
            t_wl = w["L"] / w["cg"]
            gain_wl = math.exp(gam * t_wl / 2) - 1               # 1 波長進む間の高さの増え
            t_box = 250.0 / w["cg"]
            gain_box = math.exp(gam * t_box / 2) - 1
            wind.append(dict(U10=U, T=T, ustar=round(ustar, 2), P0_Pa=round(P0, 1), gammaE=float(f"{gam:.2e}"),
                             height_gain_per_wavelength_pct=round(100 * gain_wl, 2),
                             height_gain_over_250m_pct=round(100 * gain_box, 1)))
    out["wind_in_box"] = dict(rows=wind,
                              measured_decay_ja="FLIP41 B1：周期 7 s・水深 25 m・粒子 0.25 m で 3 波長 1.2 %（1 波長 約 0.4 %）、周期 5 s・粒子 0.25 m で 3.9 %（約 1.3 %）。T2 の風なし（周期 5 s、6 波長）で 1 波長 1.6 %")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
