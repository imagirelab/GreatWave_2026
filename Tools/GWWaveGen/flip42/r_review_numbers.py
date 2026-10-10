# -*- coding: utf-8 -*-
"""FLIP42 計画の見直し（review_ja.md）の数を出す（py -3.10、numpy）。新しい流体の計算はしない。
読むもの（読むだけ）：Unity/Build/FLIP42/plan/plan_numbers.json、Unity/Build/FLIP41/verify/runs.jsonl。
出力：Unity/Build/FLIP42/plan/review_numbers.json

出す数：
1. 線形の重ね合わせの群（実物の大きさ λ = 70）の、測る点ごとの包絡（ヒルベルト変換）と、包絡 ÷ 格子。
   エネルギー（η²）で重みを付けた平均と、包絡が格子 1 個・2 個より小さい所を通るエネルギーの割合【計算】。
2. 線形の焦点の形（前で静かな水面を切る点、前の谷、最も深い谷）と、粒子の帯（Narrow Band 4 格子）の厚さ【計算】。
3. Σ(a_i k_i)²（3 次の非線形の速さの補正の大きさの目安）【計算】。
4. 計算の終わりを t_ob + 3 Tc にした時のコマ数と、その時の群のエネルギーの先頭の位置【計算】。
5. 途中保存 t_b − 3.5 Tc の後に入口から出るエネルギーの割合【計算】。
6. 2 次の和・差の周波数と重ならない帯域と、その中の成分の番号【計算】。
7. 計算の時間：FLIP41 の帯 4 格子の計算から「水のある格子 1 個・1 コマ（小刻み）あたりの秒」、
   帯なしの計算から「百万粒子・1 コマあたりの秒」を出し、FLIP42 の各計算の時間の幅を出す【推定】。
"""
import os, json
import numpy as np
import v_lin as L

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
PLAN = os.path.join(ROOT, "Unity/Build/FLIP42/plan/v0_before_review/plan_numbers.json")   # 2026-10-09 計画の凍結で、見直した版（v0）の写しを読むように替えた（出す値は同じ）
RUNS41 = os.path.join(ROOT, "Unity/Build/FLIP41/verify/runs.jsonl")
OUT = os.path.join(ROOT, "Unity/Build/FLIP42/plan/review_numbers.json")
FPS = 24.0
DPS = [0.5, 0.35, 0.25, 0.177]

P = json.load(open(PLAN, encoding="utf-8"))
lam = P["full"]["lam"]; s = np.sqrt(lam)
h = P["full"]["h"]; xb = P["full"]["xb"]; tb = P["full"]["tb"]; Tc = P["full"]["Tc"]; Lc = P["full"]["Lc"]
tob = P["full"]["tob_DK"]
fc = P["lab"]["fc"] / s; dff = P["lab"]["dff"]; N = P["lab"]["N"]
f = np.linspace(fc * (1 - dff / 2), fc * (1 + dff / 2), N); om = 2 * np.pi * f
k = np.array([L.k_of_omega(o, h) for o in om])
cg = np.array([L.props(2 * np.pi / o, h)["cg"] for o in om])
kc = L.props(1 / fc, h)["k"]


def eta_xt(x, t, S):
    a = S / k.sum()
    th = k[None, :] * (x - xb) - om[None, :] * (t[:, None] - tb)
    return (a * np.cos(th)).sum(1)


def envelope(e):
    n = len(e); F = np.fft.fft(e); H = np.zeros(n); H[0] = 1
    if n % 2 == 0:
        H[n // 2] = 1; H[1:n // 2] = 2
    else:
        H[1:(n + 1) // 2] = 2
    return np.abs(np.fft.ifft(F * H))


# ---- 1. 包絡 ÷ 格子
t = np.arange(-60.0, 300.0, 0.05)
win = (t >= 0) & (t <= P["tank"]["t_end_full"])
gauges = {"x=0（帯の出口）": 0.0, "帯の出口+0.25Lc": 0.25 * Lc}
for q in [-20, -15, -10, -5, 0]:
    gauges["kc(x-xb)=%d" % q] = xb + q / kc
env_tab = {}
for S in (0.352, 0.10):
    rows = {}
    for nm, x in gauges.items():
        e = eta_xt(x, t, S)[win]; en = envelope(e); w = e * e; W = w.sum()
        r = dict(x=float(x), max_abs_eta=float(np.abs(e).max()), env_Eweighted=float((en * w).sum() / W))
        for dp in DPS:
            dx = 2 * dp
            r["dp%.3f" % dp] = dict(env_over_dx=float(r["env_Eweighted"] / dx), maxeta_over_dx=float(r["max_abs_eta"] / dx),
                                    E_frac_env_lt_1cell=float(w[en / dx < 1].sum() / W), E_frac_env_lt_2cell=float(w[en / dx < 2].sum() / W))
        rows[nm] = r
    env_tab["S%.3f" % S] = rows

# ---- 2. 線形の焦点の形と粒子の帯
shape = {}
for S in (0.352, 0.10):
    a = S / k.sum(); xs = np.linspace(0, 120, 120001)
    e = (a * np.cos(np.outer(xs, k))).sum(1)
    i = int(np.argmax(e < 0)); j = i
    while e[j + 1] < e[j]:
        j += 1
    shape["S%.3f" % S] = dict(eta_c=float(e[0]), x_zero_cross=float(xs[i]), front_trough=float(e[j]), x_front_trough=float(xs[j]),
                              sum_ak2=float(((a * k) ** 2).sum()), ak_min=float(a * k[0]), ak_max=float(a * k[-1]))
a = 0.352 / k.sum(); ts = np.arange(0, P["tank"]["t_end_full"], 0.25); deepest = 0.0
for x in np.linspace(-135, 900, 208):
    deepest = min(deepest, float(eta_xt(x, ts, 0.352).min()))
shape["deepest_linear_trough_S0.352"] = deepest
band = {("dp%.3f" % dp): dict(narrowband_4vox_m=4 * 2 * dp, initial_particle_depth_m=5 * 2 * dp, band_vox_for_4m=float(np.ceil(4.0 / (2 * dp) - 1e-9)),
                              particle_depth_ratio_4m_vs_4vox=float((np.ceil(4.0 / (2 * dp) - 1e-9) + 1) / 5.0)) for dp in DPS}

# ---- 4・5. 終わりの時刻と途中保存の後のエネルギー
t_end_new = tob + 3 * Tc
front_x = xb + cg.max() * (t_end_new - tb)
T_rep = 1.0 / (f[1] - f[0])          # 成分の間隔で決まる、群がくり返す周期（1 周期の窓だけで積む）
cgc = L.props(1 / fc, h)["cg"]
late = {}
for nm, x in (("x=0", 0.0), ("帯の出口+0.25Lc", 0.25 * Lc), ("kc(x-xb)=-15", xb - 15 / kc)):
    tcen = tb - (xb - x) / cgc
    tl = np.arange(tcen - T_rep / 2, tcen + T_rep / 2, 0.02)
    e = eta_xt(x, tl, 0.352); E = np.cumsum(e * e); E /= E[-1]
    late[nm] = {("after_%.1f" % tt): float(1 - E[np.searchsorted(tl, tt)]) for tt in (tb - 3.5 * Tc, t_end_new)}
    late[nm]["before_0"] = float(E[np.searchsorted(tl, 0.0)])

# ---- 6. 2 次の和・差の周波数と重ならない帯域
f_lo = f[-1] - f[0]; f_hi = 2 * f[0]
clean = [int(i + 1) for i in range(N) if f_lo < f[i] < f_hi]
spectral = dict(f1=float(f[0]), fN=float(f[-1]), diff_max=float(f_lo), sum_min=float(f_hi), clean_components=[clean[0], clean[-1]],
                n_clean=len(clean), df_component=float(f[1] - f[0]), fft_bin_end_new=float(1 / t_end_new),
                subbands_A1=[[1, 11], [12, 21], [22, 32]])

# ---- 7. 計算の時間
rows = [json.loads(l) for l in open(RUNS41, encoding="utf-8")]
cell, part_nb0, part_b4 = [], [], []
for r in rows:
    p = r["parms"]
    if r["run_id"].startswith("smoke") or r["f_end_done"] - r["f_start"] < 500 or p.get("minsub", 1) > 1:
        continue
    dp = p["dp"]; dx = dp * p.get("gridscale", 2.0); xs = np.linspace(0, p["Lx"], 2000)
    hb = L.bed_profile(xs, p["h0"], p.get("xs0", 1e6), p.get("slope_n", 0), p.get("h1", p["h0"]))
    ncell = (p["Lx"] / dx) * (hb.mean() / dx) * 4
    spf = r["wall_per_frame_median_s"]
    if p.get("band_vox", 4) > 100:
        part_nb0.append((r["run_id"], spf / (r["particles_max"] / 1e6)))
    elif p.get("band_vox", 4) == 4:
        part_b4.append(spf / (r["particles_max"] / 1e6))
        if ncell >= 1e5:
            cell.append((r["run_id"], ncell, spf / ncell * 1e6))
us = [c[2] for c in cell]; us_rng = (min(us), max(us))
nb_big = [v for (rid, v) in part_nb0 if "dp0.5" in rid]      # 帯なしで粒子 0.5 m の 2 本（B1・B2）
pp_rng = (min(nb_big), max(nb_big))
Lx = P["tank"]["Lx_total_full"]
sub_jet = {d["dp"]: d["substeps_jet"] for d in P["resolutions"]}
t_on = tob - Tc; t_off = tob + 3 * Tc      # 計画と同じ：噴流の区間は t_ob − 1 Tc 〜 t_ob + 3 Tc、その外は小刻み 1


def subframes(t0, t1, dp, mult=1):
    jet = max(0.0, min(t1, t_off) - max(t0, t_on)) * FPS
    other = max(0.0, t1 - t0) * FPS - jet
    return (other + jet * sub_jet[dp]) * mult


def cells(dp):
    dx = 2 * dp; return (Lx / dx) * (h / dx) * 4


def parts_nb0(dp):
    dx = 2 * dp; return Lx * (h + 2) * (4 * dx) / dp ** 3


def hours(nsf, dp):
    return dict(band4=[u * 1e-6 * cells(dp) * nsf / 3600 for u in us_rng], nb0=[q * parts_nb0(dp) / 1e6 * nsf / 3600 for q in pp_rng])


t_end_plan = P["tank"]["t_end_full"]; t_low = tb + 1.5 * Tc; t_rs = tb - 3.5 * Tc
plan_h = {r["id"]: r["hours"] for r in P["runs"]}
cost = dict(
    flip41_band4_us_per_cell_frame=dict(runs=[[c[0], round(c[1]), round(c[2], 2)] for c in cell], range=list(us_rng)),
    flip41_band4_s_per_frame_per_Mparticle_range=[min(part_b4), max(part_b4)],
    flip41_nb0_s_per_frame_per_Mparticle=[[rid, round(v, 2)] for rid, v in part_nb0], nb0_range_used=list(pp_rng),
    cells_M={("dp%.3f" % dp): cells(dp) / 1e6 for dp in DPS}, particles_nb0_M={("dp%.3f" % dp): parts_nb0(dp) / 1e6 for dp in DPS},
    plan_runs=dict(
        R1=dict(plan=plan_h["R1"], **hours(subframes(0, t_end_plan, 0.5), 0.5)),
        R2=dict(plan=plan_h["R2"], **hours(subframes(0, t_end_plan, 0.35), 0.35)),
        R3=dict(plan=plan_h["R3"], **hours(subframes(0, t_end_plan, 0.25), 0.25)),
        R4=dict(plan=plan_h["R4"], **hours(subframes(0, t_end_plan, 0.177), 0.177)),
        R5=dict(plan=plan_h["R5"], **hours(subframes(0, t_end_plan, 0.25, 2), 0.25)),
        L1=dict(plan=plan_h["L1"], **hours(t_low * FPS, 0.5)),
        L2=dict(plan=plan_h["L2"], **hours(t_low * FPS, 0.35)),
        L3=dict(plan=plan_h["L3"], **hours(t_low * FPS, 0.25)),
        R6=dict(plan=[r["hours"] for r in P["runs_conditional"] if r["id"] == "R6"][0], **hours(subframes(0, t_end_plan, 0.125), 0.125))),
    revised_runs=dict(
        R1=hours(subframes(0, t_end_new, 0.5), 0.5), R1b=hours(subframes(0, t_end_new, 0.5), 0.5),
        R2=hours(subframes(0, t_end_new, 0.35), 0.35), R3=hours(subframes(0, t_end_new, 0.25), 0.25),
        R5r=hours(subframes(t_rs, t_end_new, 0.25, 2), 0.25), R4=hours(subframes(0, t_end_new, 0.177), 0.177)),
    substep_frames=dict(R3_plan_end=subframes(0, t_end_plan, 0.25), R3_new_end=subframes(0, t_end_new, 0.25),
                        R5_full=subframes(0, t_end_plan, 0.25, 2), R5r=subframes(t_rs, t_end_new, 0.25, 2)),
    note_ja="帯 4 格子の計算は、水のある格子が 10 万個以上の FLIP41 の計算から（小さい計算は 1 コマの決まった手間が目立つので除いた）。"
            "帯なしは粒子 0.5 m の 2 本（B1・B2）の幅。噴流の区間（t_ob − 1 Tc から終わりまで）は計画の小刻みの数。どれも【推定】")
for d in (cost["plan_runs"], cost["revised_runs"]):
    for v in d.values():
        for kk in ("band4", "nb0"):
            v[kk] = [round(x, 2) for x in v[kk]]

# FLIP41 の測った減り（summary_tables.md から写した。【測った】）
flip41_decay = [
    dict(run="B1_T7_h25_dp0.5_relax", a_dx=0.37, L_dx=74, c_err=-7.63, decay_3L=35.9),
    dict(run="B1_T5_h25_dp0.5_relax_HL0.04", a_dx=0.78, L_dx=39, c_err=-6.91, decay_3L=28.3),
    dict(run="B1_T7_h10_dp0.5_relax_H1.0", a_dx=0.50, L_dx=60, c_err=-2.50, decay_3L=27.8),
    dict(run="B1_T7_h5_dp0.25_relax_H0.5", a_dx=0.50, L_dx=91, c_err=-1.71, decay_3L=9.7),
    dict(run="B1_T7_h10_dp0.25_relax_H1.0", a_dx=1.00, L_dx=120, c_err=-0.86, decay_3L=15.0),
    dict(run="B1_T7_h25_dp0.5_relax_HL0.04", a_dx=1.49, L_dx=74, c_err=-4.55, decay_3L=9.9),
    dict(run="B1_T5_h25_dp0.25_relax_HL0.04", a_dx=1.56, L_dx=78, c_err=-3.25, decay_3L=3.9),
    dict(run="B1_T7_h10_dp0.125_relax_H1.0", a_dx=2.00, L_dx=239, c_err=-0.45, decay_3L=2.9),
    dict(run="B1_T10_h25_dp0.5_relax_HL0.04", a_dx=2.61, L_dx=130, c_err=-1.72, decay_3L=5.2),
    dict(run="B1_T7_h25_dp0.25_relax_HL0.04", a_dx=2.97, L_dx=149, c_err=-0.46, decay_3L=1.2)]

out = dict(schema="GreatWave.FLIP42.review_numbers/1", date="2026-10-09",
           note_ja="計画の見直しの数。新しい流体の計算はしていない。包絡と線形の形は【計算】、時間は【推定】、FLIP41 の値は【測った】",
           distance_inlet_to_focus=dict(m=xb, over_Lc=xb / Lc, over_Lshort=xb / P["full"]["L_range"][0], over_Llong=xb / P["full"]["L_range"][1]),
           envelope=env_tab, linear_shape=shape, narrow_band=band,
           end_time=dict(t_end_plan=t_end_plan, t_end_new=t_end_new, frames_new=int(round(t_end_new * FPS)),
                         energy_front_x_at_new_end=float(front_x), cg_max=float(cg.max()), free_region_end_if_175Lc=float(xb + 1.75 * Lc),
                         Lx_total_if_175Lc=float(xb + 1.75 * Lc + Lc + Lc), restart_time=t_rs),
           energy_after=late, spectral=spectral, cost=cost, flip41_decay=flip41_decay,
           speed_model_A3_dp025=P["resolutions"][2]["speed_error_model"])
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(dict(env={kS: {g: {kk: (round(vv, 3) if isinstance(vv, float) else {a2: round(b2, 3) for a2, b2 in vv.items()}) for kk, vv in r.items()} for g, r in rows_.items()} for kS, rows_ in env_tab.items()},
                      shape=shape, band=band, end=out["end_time"], late=late, spectral=spectral,
                      cost=dict(us=us_rng, nb0=pp_rng, b4pp=[min(part_b4), max(part_b4)], plan=cost["plan_runs"], revised=cost["revised_runs"], sf=cost["substep_frames"]),
                      dist=out["distance_inlet_to_focus"]), ensure_ascii=False, indent=1))
