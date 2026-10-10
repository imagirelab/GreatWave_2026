# -*- coding: utf-8 -*-
"""Q44 の訂正（2026-10-09）：線形 NewWave の「頂の高さ η_c（静かな水面から山まで）」と
「波高 H（山から隣の谷まで）」を分けて出す（py -3.10、numpy だけ。流体の計算はしない）。

相手のスペクトルは FLIP41 の提案（mc_proposal_numbers.py の newwave と同じ）：
  JONSWAP γ 3.3、Tp 7.5 s、水深 25 m、0.5〜2.5 fp を 160 成分、一方向。

線形 NewWave（Tromans ら 1991）は、焦点（x = 0、t = 0）で
  η(x, t) = Σ a_i cos(k_i x − ω_i t)、a_i = A · S_i / Σ S_j
なので、焦点の点の時系列は η(0, t) = A · ρ(t)（ρ は時間の自己相関）、焦点の時刻の空間の形は
η(x, 0) = A · Σ S_i cos(k_i x) / Σ S_j になる。A は成分の振幅の和で、焦点の線形の頂（η_c）。
頂の隣の谷の深さ |ρ_min|·A から、線形の波高 H = A (1 + |ρ_min|)、比 H/η_c = 1 + |ρ_min|。

出すもの：
1. 比 H/η_c（焦点の点の時系列と、焦点の時刻の空間の形の両方）。上の切りの周波数 2.0・2.5・3.0・4.0 fp の感度。
2. 波高 10 m（と 12 m）に要る線形の頂 A = H / (H/η_c)、旧提案の A = 5 m が線形でどの H になるか。
3. 非線形の向きの目安：Stokes 2 次の係数（有限水深）をピークの波数で使う狭い帯の見積もり。
   山は +C·A²、谷は +C·(|ρ_min|A)² だけ上がる（山は高く、谷は浅くなる）。差の波（set-down）と
   帯の広さは入れていない。崩れの近くでは 2 次の式は当たらないので、実際の頂と波高は計算で測る。
4. 粒子 0.25・0.3 m（格子はその 2 倍）で、波長/格子 が 150 未満の成分が線形の頂 A の何割を運ぶか
   （FLIP41 で速さ 1 % と減り 5 %/3 波長に両方入ったのは 波長/格子 149〜239 の 2 組だけ）。
使い方: py -3.10 -B q44_newwave_height.py
  → Unity/Build/FLIP42/report/q44_newwave_height.json と Docs/Evidence/FLIPMethodCheck/q44_newwave_height.json
"""
import json
import math
import os

import numpy as np

G = 9.80665
ROOT = r"G:/Unity/GreatWave_2026_Fresh"
OUTS = [ROOT + "/Unity/Build/FLIP42/report/q44_newwave_height.json",
        ROOT + "/Docs/Evidence/FLIPMethodCheck/q44_newwave_height.json"]

TP, H_DEPTH, GAMMA, N = 7.5, 25.0, 3.3, 160


def wavenumber(om, h):
    k = om * om / G
    for _ in range(100):
        f = G * k * math.tanh(k * h) - om * om
        df = G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2
        k -= f / df
    return k


def jonswap(om, omp, gamma=GAMMA):
    sig = np.where(om <= omp, 0.07, 0.09)
    r = np.exp(-((om - omp) ** 2) / (2 * sig ** 2 * omp ** 2))
    return om ** -5 * np.exp(-1.25 * (omp / om) ** 4) * gamma ** r


def components(fmax=2.5, n=N):
    omp = 2 * math.pi / TP
    om = np.linspace(0.5 * omp, fmax * omp, n)
    S = jonswap(om, omp)
    w = S / S.sum()                       # a_i = A · w_i
    k = np.array([wavenumber(x, H_DEPTH) for x in om])
    return om, k, w


def first_min(s, y):
    """s > 0 の側で、最初の極小（頂の隣の谷）。"""
    for i in range(1, len(y) - 1):
        if y[i] < y[i - 1] and y[i] <= y[i + 1]:
            return float(s[i]), float(y[i])
    raise RuntimeError("no minimum")


def ratios(fmax=2.5):
    om, k, w = components(fmax)
    t = np.linspace(0.0, 2.0 * TP, 4001)
    rho_t = (w[None, :] * np.cos(om[None, :] * t[:, None])).sum(axis=1)
    tt, rt = first_min(t, rho_t)
    Lp = 2 * math.pi / wavenumber(2 * math.pi / TP, H_DEPTH)
    x = np.linspace(0.0, 2.0 * Lp, 4001)
    rho_x = (w[None, :] * np.cos(k[None, :] * x[:, None])).sum(axis=1)
    xx, rx = first_min(x, rho_x)
    return dict(fmax_over_fp=fmax,
                time_at_focus=dict(trough_dt_s=round(tt, 2), trough_over_crest=round(rt, 3), H_over_eta_c=round(1 - rt, 3)),
                space_at_focus_time=dict(trough_dx_m=round(xx, 1), trough_over_crest=round(rx, 3), H_over_eta_c=round(1 - rx, 3)))


def main():
    omp = 2 * math.pi / TP
    kp = wavenumber(omp, H_DEPTH)
    Lp = 2 * math.pi / kp
    sens = [ratios(f) for f in (2.0, 2.5, 3.0, 4.0)]
    base = sens[1]
    r_t = base["time_at_focus"]["H_over_eta_c"]
    r_x = base["space_at_focus_time"]["H_over_eta_c"]

    linear = []
    for H in (10.0, 12.0):
        linear.append(dict(H_m=H, eta_c_needed_time=round(H / r_t, 2), eta_c_needed_space=round(H / r_x, 2)))
    old = dict(eta_c_m=5.0, H_linear_time=round(5.0 * r_t, 2), H_linear_space=round(5.0 * r_x, 2))

    # 3. 狭い帯の Stokes 2 次（有限水深）。η2 = C·a²·cos2θ、C = (k/4)(3 − σ²)/σ³、σ = tanh(kh)
    sg = math.tanh(kp * H_DEPTH)
    C = kp / 4 * (3 - sg * sg) / sg ** 3
    nl = []
    for H in (10.0,):
        for name, r in (("time", r_t), ("space", r_x)):
            A = H / r
            tr = -(r - 1) * A                    # 線形の谷（負）
            crest2 = A + C * A * A
            trough2 = tr + C * tr * tr
            nl.append(dict(basis=name, eta_c_linear=round(A, 2), trough_linear=round(tr, 2),
                           eta_c_2nd=round(crest2, 2), trough_2nd=round(trough2, 2), H_2nd=round(crest2 - trough2, 2),
                           kp_eta_c_linear=round(kp * A, 3)))

    # 4. 波長/格子 < 150 の成分が運ぶ A の割合
    om, k, w = components(2.5)
    L = 2 * math.pi / k
    res = []
    for dp in (0.25, 0.3):
        grid = 2 * dp
        lg = L / grid
        res.append(dict(particle_m=dp, grid_m=grid, L_over_grid_peak=round(Lp / grid, 0),
                        L_over_grid_shortest=round(float(lg.min()), 0),
                        share_of_A_with_L_over_grid_lt_150=round(float(w[lg < 150].sum()), 3),
                        share_of_A_with_L_over_grid_lt_78=round(float(w[lg < 78].sum()), 3)))

    out = dict(
        note_ja="Q44 の訂正の数（FLIP_MethodCheck_ja.md の〔訂正 10/9・Q44〕）。線形 NewWave、JONSWAP γ 3.3・Tp 7.5 s・水深 25 m・"
                "0.5〜2.5 fp・160 成分・一方向（mc_proposal_numbers.py と同じ）。η_c＝静かな水面から山まで、H＝山から隣の谷まで。"
                "2 次はピークの波数での狭い帯の目安で、差の波と帯の広さを入れていない",
        spectrum=dict(Tp=TP, h=H_DEPTH, gamma=GAMMA, n=N, f_range_over_fp=[0.5, 2.5], kp=round(kp, 4), Lp=round(Lp, 1), kph=round(kp * H_DEPTH, 2)),
        H_over_eta_c=base, sensitivity_fmax=sens,
        eta_c_for_H=linear, old_proposal_eta_c_5m=old,
        stokes2_narrowband=dict(C_per_m=round(C, 4), deep_water_C_per_m=round(kp / 2, 4), rows=nl),
        resolution_of_components=res,
    )
    for p in OUTS:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=True, indent=1))


if __name__ == "__main__":
    main()
