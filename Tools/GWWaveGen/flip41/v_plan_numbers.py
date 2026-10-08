# -*- coding: utf-8 -*-
"""FLIP41 確かめの計画（verify/plan_ja.md）に書く理論の値を出す。py -3.10 v_plan_numbers.py → verify/plan_numbers.json
式は v_lin.py（線形の分散・群速度・浅水係数・Biésel・Stokes）。風は Plant（1982）の γ = 0.04 (u*/c)² ω と、
水面の圧力 p = P0 ∂η/∂x がする仕事から出る γ = P0 k ω /(ρw g)（wind_ja.md §1.2 の導出）。"""
import json, math, sys
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
from v_lin import props, ks, biesel_HS, stokes2_a2, stokes3_dc, bed_profile, G
import v_cfg

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/verify/plan_numbers.json"
R = {}
# B1 の組
B1 = [(7, 25), (5, 25), (10, 25), (7, 10), (7, 5), (12, 60), (12, 26)]
R["B1"] = []
for T, h in B1:
    p = props(T, h)
    a = 0.01 * p["L"] / 2
    row = dict(T=T, h=h, L=p["L"], kh=p["kh"], c=p["c"], cg=p["cg"], H=2 * a, a=a, HS=biesel_HS(p["kh"]),
               stokes3_dc=stokes3_dc(a, p["k"], h), a2_over_a=stokes2_a2(a, p["k"], h) / a)
    for dp in (1.0, 0.5, 0.35, 0.25):
        vox = 2 * dp
        row["dp%g" % dp] = dict(L_vox=p["L"] / vox, H_vox=2 * a / vox, h_vox=h / vox)
    c = v_cfg.b1(T, h, 1.0)
    row["Lx"] = c["parms"]["Lx"]; row["t_end"] = c["case"]["t_win"][1]; row["frames"] = c["f_end"]
    row["x_meas"] = c["case"]["x_meas"]; row["xa0"] = c["case"]["xa0"]
    R["B1"].append(row)
# 同じ周期で水深を変えた時の速さ（深い 60 m に対する比）
R["same_T_depth"] = [dict(T=T, h=h, c=props(T, h)["c"], ratio_to_60=props(T, h)["c"] / props(T, 60)["c"]) for T in (7,) for h in (60, 25, 10, 5)]
# 位相の許し 0.3 rad → 速さの誤差（距離 X）
R["phase_tol"] = [dict(T=T, h=h, X=X, dc=0.3 / (props(T, h)["k"] * X)) for T, h, X in [(5, 25, 400), (7, 25, 400), (12, 60, 406)]]
# B2：40 → 12 m、1:20
R["B2"] = []
for T in (7, 10):
    h0, h1, n = 40.0, 12.0, 20.0
    p0, p1 = props(T, h0), props(T, h1)
    L = (h0 - h1) * n
    xx = np.linspace(0, L, 4001); hh = h0 - xx / n
    cs = np.array([props(T, v)["c"] for v in hh])
    t_ph = float(np.trapezoid(1 / cs, xx)); t_const = L / p0["c"]
    a = 0.375
    c = v_cfg.b2(T, h0, h1, n, 1.0, a)
    Ur = 2 * a * ks(T, h0, h1) * p1["L"] ** 2 / h1 ** 3
    R["B2"].append(dict(T=T, h0=h0, h1=h1, slope=1 / n, length=L, c_ratio=p1["c"] / p0["c"], Ks=ks(T, h0, h1),
                        t_phase=t_ph, t_phase_const=t_const, t_diff=t_ph - t_const, L0=p0["L"], L1=p1["L"], kh0=p0["kh"], kh1=p1["kh"],
                        H_off=2 * a, H_shallow=2 * a * ks(T, h0, h1), Ursell_shallow=Ur, H_over_h_shallow=2 * a * ks(T, h0, h1) / h1,
                        Lx=c["parms"]["Lx"], t_end=c["case"]["t_win"][1], frames=c["f_end"]))
# T1：圧力 5000 Pa の cos → 水面 −0.51 m
R["T1"] = dict(p0c=5000.0, eta=-5000.0 / (1000 * G), p0u=2000.0, lam=40.0, T_nat=2 * math.pi / math.sqrt(G * (2 * math.pi / 40) * math.tanh(2 * math.pi / 40 * 25)))
# T2：周期 5 s・水深 25 m、U10 30 m/s（Large & Pond の Cd を 25 m/s で止めた 2.1e-3、wind_ja.md §1.3）
rho_a, rho_w = 1.2, 1000.0
U10 = 30.0; Cd = (0.49 + 0.065 * 25.0) * 1e-3
tau = rho_a * Cd * U10 ** 2; us = math.sqrt(tau / rho_a)
R["T2"] = []
for T in (5.0,):
    p = props(T, 25.0)
    k, om, c, cg = p["k"], p["om"], p["c"], p["cg"]
    for nm, P0 in [("Miles β=34", 34 * rho_a * us * us), ("Jeffreys S=0.5", rho_a * 0.5 * (U10 - c) ** 2)]:
        gam = P0 * k * om / (rho_w * G)
        gam_plant = 0.04 * (us / c) ** 2 * om * (1025.0 / rho_w if nm.startswith("Miles") else 1.0)
        alpha = gam / (2 * cg)
        R["T2"].append(dict(name=nm, T=T, P0=P0, gamma=gam, gamma_plant_mid=0.04 * (us / c) ** 2 * om, gamma_plant_range=[0.02 * (us / c) ** 2 * om, 0.06 * (us / c) ** 2 * om],
                            alpha_amp_per_m=alpha, amp_gain_3L=math.exp(alpha * 3 * p["L"]) - 1, L=p["L"], u_star=us, tau=tau, Cd=Cd,
                            p_amp_at_ak01=P0 * 0.1))
json.dump(R, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
for k, v in R.items():
    print(k, json.dumps(v, ensure_ascii=False)[:1800])
