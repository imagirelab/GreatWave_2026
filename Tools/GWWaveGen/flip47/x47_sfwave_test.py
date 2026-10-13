# -*- coding: utf-8 -*-
"""g47_sfwave.py（流れ関数の解）の確かめ。py -3.10 -B x47_sfwave_test.py → 標準出力と Unity/Build/FLIP47/periodic/sfwave_test.json
1 線形の極み（H 1 cm）：k・c・B1・エネルギーの流れが線形の式と合う
2 深い水の Stokes の 3 次：c = √(g/k)(1 + (ka)²/2)
3 中くらいの水深の Stokes の 2 次：頂の高さ η_c ≈ a + (k a²/4) cosh kh (2 + cosh 2kh)/sinh³ kh
4 節の間の点で水面の 2 つの条件（運動・Bernoulli）が成り立つ。項の数を変えて頂・c が動かない（h 19 m・T 14 s・H 10 m）
5 平均の質量の流れが 0（閉じた水路の決まり）
"""
import os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_sfwave as SF

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP47/periodic"
os.makedirs(OUT, exist_ok=True)
R = {}
g = SF.G

# 1 線形の極み
h, T, H = 19.0, 14.0, 0.01
s = SF.solve(h, T, H)
kl = SF.k_lin(T, h); a = H / 2
cl = 2 * math.pi / (kl * T)
F = SF.energy_flux(s); Fl = g * H * H / 8 * SF.cg_lin(T, h)
R["linear"] = dict(k_rel=s["k"] / kl - 1, c_rel=s["c"] / cl - 1, B1_rel=s["B"][0] / (cl * a / math.tanh(kl * h)) - 1, F_rel=F / Fl - 1,
                   ok=bool(abs(s["k"] / kl - 1) < 1e-5 and abs(F / Fl - 1) < 1e-3))
# 2 深い水
h, T, H = 400.0, 6.0, 2.0
s = SF.solve(h, T, H)
ka = s["k"] * H / 2
c3 = math.sqrt(g / s["k"]) * (1 + 0.5 * ka ** 2)
R["deep_stokes3"] = dict(ka=ka, c=s["c"], c_stokes3=c3, rel=s["c"] / c3 - 1, ok=bool(abs(s["c"] / c3 - 1) < 2e-4))
# 3 中くらいの水深の 2 次
h, T, H = 19.0, 10.0, 0.6
s = SF.solve(h, T, H)
k = s["k"]; a = H / 2; kh = k * h
ec2 = a + k * a * a / 4 * math.cosh(kh) * (2 + math.cosh(2 * kh)) / math.sinh(kh) ** 3
R["stokes2_crest"] = dict(eta_c=s["eta_crest"], eta_c_stokes2=ec2, diff_m=s["eta_crest"] - ec2, second_order_part=ec2 - a,
                          ok=bool(abs(s["eta_crest"] - ec2) < 0.1 * (ec2 - a)))
# 4・5 本番の大きさ
h, T, H = 19.0, 14.0, 10.0
s1 = SF.solve(h, T, H, N=24); s2 = SF.solve(h, T, H, N=40)
r1 = SF._bc_residuals(s2)
R["design_like"] = dict(H_over_h=H / h, Hmax_fit=s2["Hmax_fit"], N24_eta_c=s1["eta_crest"], N40_eta_c=s2["eta_crest"], N24_c=s1["c"], N40_c=s2["c"],
                        kin_res_rel=r1[0], bern_res_rel=r1[1], mass_flux_m2s=SF.mass_flux(s2), u1_mean_current=s2["u1"],
                        F_N24=SF.energy_flux(s1), F_N40=SF.energy_flux(s2),
                        ok=bool(abs(s1["eta_crest"] - s2["eta_crest"]) < 0.01 and abs(s1["c"] - s2["c"]) < 1e-3 and r1[0] < 1e-4 and r1[1] < 1e-3
                                and abs(SF.mass_flux(s2)) < 1e-3 * s2["c"] * h))
R["all_ok"] = bool(all(v.get("ok") for v in R.values() if isinstance(v, dict)))
json.dump(R, open(os.path.join(OUT, "sfwave_test.json"), "w", encoding="utf8"), indent=1, default=float)
for k_, v in R.items():
    print(k_, v)
