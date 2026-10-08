# -*- coding: utf-8 -*-
"""FLIP41 基準の問題の調べ（benchmarks_ja.md）で使う理論の値を出す。流体の計算はしない。
使い方: py -3.10 b_theory_numbers.py  → 標準出力に表、Unity/Build/FLIP41/research/b_theory_numbers.json に保存。
式：線形の分散 ω² = g k tanh(kh)、群速度 cg = c (1 + 2kh/sinh 2kh)/2、線形の浅水係数 Ks = sqrt(cg0/cg)、
Stokes 2 次の拘束された 2 倍の波の振幅 a2 = k a² cosh(kh)(2 + cosh 2kh) / (4 sinh³ kh)、
自由な 2 倍の波とのうなりの長さ Lb = 2π / |k(2ω) − 2k(ω)|、ピストン造波の Biésel の比 H/S = 2(cosh 2kh − 1)/(sinh 2kh + 2kh)、
Grilli ら（1997）の孤立波の分け方 S0 = 1.521 tanβ / sqrt(H/h)、成分の位相の誤差の許し（0.3 rad）から出す速さの誤差の上限。
"""
import json, os
import numpy as np

g = 9.81
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/research/b_theory_numbers.json"


def k_of(T, h):
    w = 2 * np.pi / T; k = w * w / g
    for _ in range(200):
        f = g * k * np.tanh(k * h) - w * w
        k -= f / (g * np.tanh(k * h) + g * k * h / np.cosh(k * h) ** 2)
    return float(k)


def props(T, h):
    k = k_of(T, h); w = 2 * np.pi / T; c = w / k
    cg = 0.5 * c * (1 + 2 * k * h / np.sinh(2 * k * h))
    return dict(T=T, h=h, k=k, L=2 * np.pi / k, c=c, cg=float(cg), kh=k * h)


R = {}
# 1. 速さの表（前の試作の水深と、神奈川沖の水深の両方）
R["speed_table"] = [props(T, h) for T in [5, 7, 8, 10, 12, 14, 16, 20, 21.8] for h in [10, 15, 25, 26, 40, 60]]
# 2. 水深による速さの比と浅水係数
pairs = [(12, 60, 26), (8, 60, 26), (16, 60, 26), (12, 60, 20), (16, 60, 20), (7, 40, 8), (7, 40, 15), (10, 40, 8), (5, 40, 8)]
R["depth_change"] = []
for T, h0, h1 in pairs:
    a, b = props(T, h0), props(T, h1)
    R["depth_change"].append(dict(T=T, h0=h0, h1=h1, c_ratio=b["c"] / a["c"], Ks=float(np.sqrt(a["cg"] / b["cg"]))))
# 3. 斜面を上る時間（位相）と、一定の水深なら掛かる時間
R["slope_travel"] = []
for T, h0, h1, n in [(12, 60, 20, 30), (16, 60, 20, 30), (7, 40, 8, 30), (10, 40, 8, 30)]:
    xs = np.linspace(0, (h0 - h1) * n, 4001); hh = h0 - xs / n
    cs = np.array([props(T, v)["c"] for v in hh]); cgs = np.array([props(T, v)["cg"] for v in hh])
    R["slope_travel"].append(dict(T=T, h0=h0, h1=h1, slope=1.0 / n, length=float(xs[-1]),
                                  t_phase=float(np.trapezoid(1 / cs, xs)), t_phase_const=float(xs[-1] / props(T, h0)["c"]),
                                  t_group=float(np.trapezoid(1 / cgs, xs))))
# 4. 位相の誤差 0.3 rad を許す時の、速さの誤差の上限（距離 X を進む成分）
R["phase_tol"] = []
for T, h, X in [(7.5, 60, 406), (12, 60, 406), (21.8, 60, 406), (5, 25, 400), (7, 25, 400)]:
    p = props(T, h); R["phase_tol"].append(dict(T=T, h=h, X=X, kX=p["k"] * X, dc_over_c=0.3 / (p["k"] * X),
                                                 coherent_loss=float(1 - np.exp(-0.3 ** 2 / 2))))
# 5. Stokes 2 次と自由な 2 倍の波
R["stokes2"] = []
for T, h, HL in [(12, 60, 0.02), (12, 60, 0.04), (12, 26, 0.04), (7, 25, 0.04), (5, 25, 0.04), (2.02, 0.4, 0.02 / 3.737)]:
    p = props(T, h); a = HL * p["L"] / 2; kh = p["kh"]
    a2 = p["k"] * a * a / 4 * np.cosh(kh) * (2 + np.cosh(2 * kh)) / np.sinh(kh) ** 3
    k2 = k_of(T / 2, h)
    R["stokes2"].append(dict(T=T, h=h, H=2 * a, ka=p["k"] * a, a2=float(a2), a2_over_a=float(a2 / a), beat_L=2 * np.pi / abs(k2 - 2 * p["k"])))
# 6. 実験の基準の問題の kh
labs = [("Beji_Battjes_A_h0.4", 2.02, 0.4), ("Beji_Battjes_A_crest_h0.1", 2.02, 0.1), ("BB_2nd_free_h0.4", 1.01, 0.4), ("BB_3rd_free_h0.4", 2.02 / 3, 0.4),
        ("Luth_B1", 1.01, 0.4), ("Luth_B3", 2.525, 0.4), ("Ting_Kirby_spill", 2.0, 0.4), ("Ting_Kirby_plunge", 5.0, 0.4),
        ("Berkhoff_offshore", 1.0, 0.45), ("Berkhoff_on_shoal_h0.1", 1.0, 0.1), ("Rapp_Melville_fc0.88", 1 / 0.88, 0.6), ("CCP_WSI_BT1_Tp1.456", 1.456, 2.93)]
R["lab_kh"] = [dict(name=n, **props(T, h)) for n, T, h in labs]
# 7. Beji & Battjes をフルード則で 150 倍にした値（水深 60 m）
s = 150.0
R["bb_scale150"] = dict(scale=s, h=0.4 * s, h_crest=0.1 * s, T=2.02 * np.sqrt(s), H=0.02 * s, x_up=[6 * s, 12 * s], x_crest=[12 * s, 14 * s], x_down=[14 * s, 17 * s],
                        gauges_luth=[x * s for x in [10.5, 12.5, 13.5, 14.5, 15.7, 17.3, 19.0, 21.0]],
                        H_over_dx={str(dx): 3.0 / dx for dx in [0.6, 1.0, 2.0]})
# 8. ピストン造波の Biésel の比
R["biesel_piston"] = []
for T, h in [(12, 60), (7, 25), (2.02, 0.4)]:
    kh = props(T, h)["kh"]; R["biesel_piston"].append(dict(T=T, h=h, kh=kh, H_over_S=float(2 * (np.cosh(2 * kh) - 1) / (np.sinh(2 * kh) + 2 * kh))))
# 9. Grilli ら（1997）の S0：FLIP37 P1 の孤立波 2 本（SW1：水深 20 m・高さ 9 m・1:15、SW2：同じ・1:4）
R["grilli_S0"] = [dict(run=n, slope=1.0 / m, H_over_h=Hh, S0=1.521 / m / np.sqrt(Hh)) for n, m, Hh in [("SW1_h20_Hs9_n15", 15, 0.45), ("SW2_h20_Hs9_n4", 4, 0.45)]]
# 10. FLIP39 C1 の成分：間隔と、成分を分けるのに要る窓の長さ
om = np.linspace(0.288, 0.8378, 32)
R["c1_components"] = dict(n=32, a_each=0.085, d_omega=float(om[1] - om[0]), window_needed_s=float(2 * np.pi / (om[1] - om[0])), record_s=95.0, voxel=2.0)

for key in ["depth_change", "slope_travel", "phase_tol", "stokes2", "biesel_piston", "grilli_S0"]:
    print("==", key)
    for r in R[key]:
        print("  ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
print("== lab_kh")
for r in R["lab_kh"]:
    print("   %-28s T %.3f h %.2f L %.3f kh %.2f" % (r["name"], r["T"], r["h"], r["L"], r["kh"]))
print("== bb_scale150", R["bb_scale150"])
print("== c1_components", R["c1_components"])
print("== speed (h=25 m)")
for r in R["speed_table"]:
    if r["h"] in (25, 15, 40):
        print("   T %4.1f h %2d L %6.1f c %5.2f cg %5.2f kh %.2f" % (r["T"], r["h"], r["L"], r["c"], r["cg"], r["kh"]))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(R, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("saved", OUT)
