# -*- coding: utf-8 -*-
"""【見直しの前の版 v0。写しで、出力は plan/v0_before_review/。凍結した計画の数は p_plan_numbers.py】
FLIP42 計画（走らせる前）：実験の「集まって前へ巻いて崩れる波」（Rapp & Melville 1990 の巻き波の組、
Derakhti & Kirby の表 3.1 の P3）を、フルードの相似で大きくした写しの数を出す（py -3.10、numpy）。
新しい流体の計算はしない。読むのは FLIP41 の計算の記録（runs.jsonl、読むだけ）。
出力：Unity/Build/FLIP42/plan/plan_numbers.json

数の種類：
- 実験の組の値は【文献】（Derakhti 2013 の修士論文の表 3.1・式 2.33。Rapp & Melville の原文は大きすぎて読めていない）。
- 線形の重ね合わせの値は【計算】（成分ごとに ω² = g k tanh(kh)、g は Houdini の既定 9.80665）。
- 計算の時間と、格子による速さの誤差の模型は【推定】（FLIP41 の測った値からの比）。
"""
import os, json
import numpy as np
import v_lin as L

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
OUT = os.path.join(ROOT, "Unity/Build/FLIP42/plan/v0_before_review/plan_numbers.json")   # 見直しの前の版（2026-10-09 に写した。出す値は元の plan_numbers.json と同じ）
RUNS41 = os.path.join(ROOT, "Unity/Build/FLIP41/verify/runs.jsonl")
G = L.G
LAB_TC = 1.0 / 0.88   # 中心の周期（実験室）

# ---- 実験の組（実験室の大きさ）【文献】
LAB = dict(h=0.60, fc=0.88, dff=0.73, N=32, S=0.352, xb=8.46, tb=20.5,
           tob_DK=19.04, xob_DK=8.35,   # D&K の表 3.1：前へ出た噴流が静かな水面に当たった時刻と場所（実験の値か計算の値かは表から確かめきれない）
           S_incipient=0.257, S_spilling=0.278)
S_LOW = 0.10          # 低い群（線形と比べる確かめ）
H_TARGET = (10.0, 12.0)   # Cartwright & Nakamura 2009：山から谷までの高さ（波高）
LAM = 70.0            # 選んだ倍率（下で理由の数を出す）
DPS = [0.5, 0.35, 0.25, 0.177, 0.125]   # 粒子の間隔（実物の大きさ、m）。格子 = 粒子 × 2
FPS = 24.0


def comps(S, h=LAB["h"], fc=LAB["fc"], dff=LAB["dff"], N=LAB["N"]):
    f = np.linspace(fc * (1 - dff / 2), fc * (1 + dff / 2), N)
    om = 2 * np.pi * f
    k = np.array([L.k_of_omega(o, h) for o in om])
    a = np.full(N, S / k.sum())          # どの成分も振幅が同じ群：S = Σ a k
    cg = np.array([L.props(2 * np.pi / o, h)["cg"] for o in om])
    return f, om, k, a, cg


def eta(x, t, om, k, a, xb=LAB["xb"], tb=LAB["tb"], kk=None):
    """線形の重ね合わせ η = Σ a cos(k(x − xb) − ω(t − tb))（式 2.33 と同じ。x = 0 が造波の位置）。
    kk を与えると、x ≥ 0 の自由な所だけ波数を kk にする（格子による遅れの模型。x = 0 の位相は同じ）。"""
    x = np.atleast_1d(np.asarray(x, float)); t = np.atleast_1d(np.asarray(t, float))
    ph0 = -k * xb                                   # x = 0 での位相（t = tb のとき）
    kx = k if kk is None else kk
    th = ph0[None, None, :] + kx[None, None, :] * x[:, None, None] - om[None, None, :] * (t[None, :, None] - tb)
    return (a[None, None, :] * np.cos(th)).sum(-1)   # (x, t)


def crest_and_H(S):
    f, om, k, a, cg = comps(S)
    ec = float(a.sum())
    xs = np.linspace(-3, 3, 12001)
    ex = (a[None, :] * np.cos(np.outer(xs, k))).sum(1)
    i = np.argmin(abs(xs)); j = i
    while ex[j + 1] < ex[j]:
        j += 1
    ts = np.linspace(-3, 3, 12001)
    et = (a[None, :] * np.cos(np.outer(ts, om))).sum(1)
    m = np.argmin(abs(ts)); n = m
    while et[n + 1] < et[n]:
        n += 1
    return dict(eta_c_lin=ec, trough_x=float(ex[j]), trough_x_dist=float(xs[j]), H_x=float(ec - ex[j]),
                trough_t=float(et[n]), trough_t_lag=float(ts[n]), H_t=float(ec - et[n]),
                H_over_eta_c_x=float((ec - ex[j]) / ec), H_over_eta_c_t=float((ec - et[n]) / ec),
                a=float(a[0]), ka_min=float(a[0] * k[0]), ka_max=float(a[0] * k[-1]))


def envelope(S, xs, t0=0.0, t1=26.0, dt=0.005):
    f, om, k, a, cg = comps(S)
    ts = np.arange(t0, t1, dt)
    out = []
    for x in xs:
        e = eta([x], ts, om, k, a)[0]
        out.append(float(np.max(np.abs(e))))
    return out


def inlet_window(S, x):
    """x での η(t)²の積み上げ：始めの何 % がどの時刻までにあるか。"""
    f, om, k, a, cg = comps(S)
    ts = np.arange(-20.0, 40.0, 0.002)
    e = eta([x], ts, om, k, a)[0]
    E = np.cumsum(e * e); E /= E[-1]
    env = np.abs(e)
    res = {}
    for t in [LAB_TC, 2.0, 3.0]:
        i = np.searchsorted(ts, t)
        res["%.2f" % t] = dict(energy_before=float(E[i]), max_abs_before=float(env[:i][ts[:i] >= 0].max() if np.any(ts[:i] >= 0) else 0.0) / float(env.max()))
    # 出入りの主な時間（全体の 1 %〜99 % のエネルギー）
    return dict(per_t_start=res, t_1pct=float(ts[np.searchsorted(E, 0.01)]), t_99pct=float(ts[np.searchsorted(E, 0.99)]),
                max_abs=float(env.max()))


def focus_with_speed_error(S, dx_lab, Cerr):
    """格子による遅れの模型：成分 i の速さが c(1 − e_i)、e_i = C (dx/L_i)²（FLIP41 の平らな底の測った値の当てはめ）。
    x = 0 の位相は造波で決まるので同じ。焦点（水面の最大）の場所・時刻と、頂・高さ（前の谷まで）の比を出す。"""
    f, om, k, a, cg = comps(S)
    Lw = 2 * np.pi / k
    e = Cerr * (dx_lab / Lw) ** 2
    kk = k / (1 - e)
    p = L.props(1 / LAB["fc"], LAB["h"])
    xs = LAB["xb"] + np.linspace(-1.0, 1.5, 1001) * p["L"]
    ts = LAB["tb"] + np.linspace(-1.5, 3.0, 901) * p["T"]
    E0 = eta(xs, ts, om, k, a)
    E1 = eta(xs, ts, om, k, a, kk=kk)
    i0 = np.unravel_index(np.argmax(E0), E0.shape); i1 = np.unravel_index(np.argmax(E1), E1.shape)

    def Hfront(E, ix, it):
        row = E[:, it]; j = ix
        while j + 1 < len(row) and row[j + 1] < row[j]:
            j += 1
        return float(row[ix] - row[j])
    return dict(e_short=float(e[-1]), e_center=float(Cerr * (dx_lab / p["L"]) ** 2), e_long=float(e[0]),
                dx_focus_over_Lc=float((xs[i1[0]] - xs[i0[0]]) / p["L"]),
                dt_focus_over_Tc=float((ts[i1[1]] - ts[i0[1]]) / p["T"]),
                crest_ratio=float(E1[i1] / E0[i0]),
                H_ratio=float(Hfront(E1, *i1) / Hfront(E0, *i0)))


def flip41_cost():
    rows = [json.loads(l) for l in open(RUNS41, encoding="utf-8")]
    per_m, per_mp = [], []
    for r in rows:
        p = r["parms"]
        if r["run_id"].startswith("smoke") or r["f_end_done"] - r["f_start"] < 500:
            continue
        if p.get("band_vox", 4) > 100 or p.get("minsub", 1) > 1:
            continue
        per_m.append(r["particles_max"] * p["dp"] / p["Lx"])          # 粒子の数 × dp / 水槽の長さ
        per_mp.append(r["wall_per_frame_median_s"] / (r["particles_max"] / 1e6))   # 1 コマの秒 ÷ 百万粒子
    return dict(n_runs=len(per_m), particles_dp_per_m_median=float(np.median(per_m)),
                particles_dp_per_m_range=[float(min(per_m)), float(max(per_m))],
                s_per_frame_per_Mparticle_median=float(np.median(per_mp)),
                s_per_frame_per_Mparticle_q25_q75=[float(np.percentile(per_mp, 25)), float(np.percentile(per_mp, 75))],
                note_ja="FLIP41 の帯あり・最小の小刻み 1 の計算（smoke と短い計算を除く）。ほとんどのコマは小刻み 1 で済んでいた【推定】")


def main():
    lab = dict(LAB)
    p = L.props(1 / LAB["fc"], LAB["h"])
    f, om, k, a, cg = comps(LAB["S"])
    lab.update(Tc=p["T"], Lc=p["L"], kc=p["k"], cc=p["c"], cgc=float(p["cg"]), kch=p["kh"],
               f_range=[float(f[0]), float(f[-1])], L_range=[float(2 * np.pi / k[0]), float(2 * np.pi / k[-1])],
               kh_range=[float(k[0] * LAB["h"]), float(k[-1] * LAB["h"])],
               cg_range=[float(cg[-1]), float(cg[0])], kc_xb=float(p["k"] * LAB["xb"]),
               tob_minus_tb_over_Tc=float((LAB["tob_DK"] - LAB["tb"]) / p["T"]),
               xob_minus_xb_over_Lc=float((LAB["xob_DK"] - LAB["xb"]) / p["L"]),
               breaking_band_RM_x=[float(LAB["xb"] - 5 / p["k"]), float(LAB["xb"])])
    ch = {"%.3f" % S: crest_and_H(S) for S in [LAB["S"], LAB["S_spilling"], LAB["S_incipient"], S_LOW]}
    # 倍率：線形の山から前の谷までの高さ（その時刻の水面の形）を 10〜12 m の真ん中 11 m に合わせる
    Hx = ch["%.3f" % LAB["S"]]["H_x"]
    lam_exact = 11.0 / Hx
    lam = LAM; s = np.sqrt(lam)
    full = dict(lam=lam, lam_exact_for_H11=lam_exact, sqrt_lam=s,
                H_lin_x=Hx * lam, eta_c_lin=ch["%.3f" % LAB["S"]]["eta_c_lin"] * lam, H_lin_t=ch["%.3f" % LAB["S"]]["H_t"] * lam,
                H_target_range_lam=[H_TARGET[0] / Hx, H_TARGET[1] / Hx],
                h=LAB["h"] * lam, Tc=p["T"] * s, T_range=[1 / f[-1] * s, 1 / f[0] * s], Lc=p["L"] * lam,
                L_range=[lab["L_range"][1] * lam, lab["L_range"][0] * lam], cc=p["c"] * s, cgc=float(p["cg"]) * s,
                xb=LAB["xb"] * lam, tb=LAB["tb"] * s, xob_DK=LAB["xob_DK"] * lam, tob_DK=LAB["tob_DK"] * s,
                a_component=a[0] * lam, breaking_band_RM_x=[v * lam for v in lab["breaking_band_RM_x"]],
                low=dict(S=S_LOW, eta_c_lin=ch["%.3f" % S_LOW]["eta_c_lin"] * lam, H_lin_x=ch["%.3f" % S_LOW]["H_x"] * lam))
    # 水槽（実験室の大きさで決めて、倍率を掛ける）
    Lc = p["L"]
    band = (-1.0 * Lc, 0.0)
    x_abs0 = LAB["xb"] + 2.5 * Lc
    x_end = x_abs0 + 1.0 * Lc
    # 遠い壁で跳ね返った波が、焦点の 0.5 波長先まで戻る最も早い時刻（いちばん速い成分の群速度）
    cgmax = float(cg.max())
    t_refl = LAB["tb"] + (x_end - LAB["xb"]) / cgmax + (x_end - (LAB["xb"] + 0.5 * Lc)) / cgmax
    t_start = 0.0          # 実験と同じく造波の始めから（帯の目標に 1 周期のなだらかな始まりを掛ける）
    t_end = 26.0           # 下流の測る点 kc(x − xb) = +10 を群の 95 % が通り過ぎる時刻（線形）
    win = {"x0": inlet_window(LAB["S"], 0.0), "x_band_far": inlet_window(LAB["S"], band[0])}
    tank = dict(band_lab=band, x_abs0_lab=x_abs0, x_end_lab=x_end, Lx_total_lab=x_end - band[0],
                band_full=[v * lam for v in band], x_abs0_full=x_abs0 * lam, x_end_full=x_end * lam,
                Lx_total_full=(x_end - band[0]) * lam, y_bottom_full=-LAB["h"] * lam, y_top_full=18.0,
                t_start_lab=t_start, t_end_lab=t_end, t_start_full=t_start * s, t_end_full=t_end * s,
                ramp_lab=1.0 * p["T"], ramp_full=1.0 * p["T"] * s,
                frames=int(round((t_end - t_start) * s * FPS)),
                t_reflection_back_lab=t_refl, reflection_after_end=bool(t_refl > t_end),
                inlet_window=win,
                low_end_lab=LAB["tb"] + 1.5 * p["T"])
    tank["frames_low"] = int(round((tank["low_end_lab"] - t_start) * s * FPS))
    # 場所ごとの包絡（時間の最大の |η|）
    xs_named = {"band_far": band[0], "x0": 0.0}
    for q in [-20, -15, -10, -5, 0, 5]:
        xs_named["kc(x-xb)=%d" % q] = LAB["xb"] + q / p["k"]
    env_hi = envelope(LAB["S"], list(xs_named.values()))
    env_lo = envelope(S_LOW, list(xs_named.values()))
    env = {n: dict(x_lab=x, x_full=x * lam, max_eta_full_S0352=v1 * lam, max_eta_full_S010=v2 * lam)
           for (n, x), v1, v2 in zip(xs_named.items(), env_hi, env_lo)}
    cost = flip41_cost()
    # 噴流と崩れの前の速さの目安（小刻みの見積もり用）【推定】
    u_pre = float((a * om).sum()) * s           # 線形の焦点の頂の水平の流速
    u_jet = float(np.sqrt((p["c"] * s) ** 2 + 2 * G * Hx * lam))   # 位相の速さで出て、高さ H だけ落ちる
    t_on_lab = LAB["tob_DK"] - 1.0 * p["T"]     # 崩れの前後で小刻みが増える区間（D&K の噴流の時刻の 1 周期前から 3 周期後まで）
    t_off_lab = LAB["tob_DK"] + 3.0 * p["T"]
    n_post = int(round((t_off_lab - t_on_lab) * s * FPS)); n_pre = tank["frames"] - n_post
    n_post_low = 0
    res = []
    for dp in DPS:
        dx = 2 * dp; dx_lab = dx / lam
        npart = cost["particles_dp_per_m_median"] * tank["Lx_total_full"] / dp
        sub_pre = max(1, int(np.ceil(u_pre / FPS / dx)))
        sub_jet = max(1, int(np.ceil(u_jet / FPS / dx)))
        spf = cost["s_per_frame_per_Mparticle_median"] * npart / 1e6
        wall = spf * (n_pre * sub_pre + n_post * sub_jet)
        wall_low = spf * tank["frames_low"] * sub_pre
        errs = {("C%d" % C): focus_with_speed_error(LAB["S"], dx_lab, C) for C in (100, 250, 290)}
        errs_low = focus_with_speed_error(S_LOW, dx_lab, 250)
        res.append(dict(dp=dp, dx=dx, dx_lab_mm=dx_lab * 1000, Lc_over_dx=full["Lc"] / dx,
                        Lshort_over_dx=full["L_range"][0] / dx, Llong_over_dx=full["L_range"][1] / dx,
                        H_lin_over_dx=full["H_lin_x"] / dx, eta_c_over_dx=full["eta_c_lin"] / dx,
                        inlet_amp_over_dx_S0352=env["x0"]["max_eta_full_S0352"] / dx,
                        inlet_amp_over_dx_S010=env["x0"]["max_eta_full_S010"] / dx,
                        nx=int(round(tank["Lx_total_full"] / dx)), ny=int(round((tank["y_top_full"] - tank["y_bottom_full"]) / dx)),
                        particles_est=npart, substeps_pre=sub_pre, substeps_jet=sub_jet,
                        s_per_frame_est=spf, hours_plunge=wall / 3600, hours_plunge_dt_half=2 * wall / 3600,
                        hours_low=wall_low / 3600, speed_error_model=errs, speed_error_model_low_C250=errs_low))
    rr = {r["dp"]: r for r in res}
    # 帯なし（水の全体に粒子）の粒子の数：水深 + 頂の分の厚さ × 板の厚さ（8 dp）÷ dp³
    nb0_part = (LAB["h"] * lam + 5.0) * 8 * 0.5 / 0.5 ** 3 * tank["Lx_total_full"]
    nb0_h = cost["s_per_frame_per_Mparticle_median"] * nb0_part / 1e6 * (n_pre * rr[0.5]["substeps_pre"] + n_post * rr[0.5]["substeps_jet"]) / 3600
    runs = [
        dict(id="R1", what_ja="巻き波の組 P3・粒子 0.5 m（最初の動画）", dp=0.5, kind="plunge", hours=rr[0.5]["hours_plunge"]),
        dict(id="R3", what_ja="巻き波の組 P3・粒子 0.25 m（主な候補）", dp=0.25, kind="plunge", hours=rr[0.25]["hours_plunge"]),
        dict(id="L3", what_ja="低い群 S 0.10・粒子 0.25 m", dp=0.25, kind="low", hours=rr[0.25]["hours_low"]),
        dict(id="L1", what_ja="低い群 S 0.10・粒子 0.5 m", dp=0.5, kind="low", hours=rr[0.5]["hours_low"]),
        dict(id="L2", what_ja="低い群 S 0.10・粒子 0.35 m", dp=0.35, kind="low", hours=rr[0.35]["hours_low"]),
        dict(id="R2", what_ja="巻き波の組 P3・粒子 0.35 m（細かさの並び）", dp=0.35, kind="plunge", hours=rr[0.35]["hours_plunge"]),
        dict(id="R4", what_ja="巻き波の組 P3・粒子 0.177 m（いちばん細かい組）", dp=0.177, kind="plunge", hours=rr[0.177]["hours_plunge"]),
        dict(id="R5", what_ja="巻き波の組 P3・粒子 0.25 m・時間の刻み半分", dp=0.25, kind="plunge_dt_half", hours=rr[0.25]["hours_plunge_dt_half"]),
    ]
    cond = [
        dict(id="R1b", what_ja="R1 と同じで粒子の帯なし（条件つき）", dp=0.5, kind="plunge_nb0", particles_est=nb0_part, hours=nb0_h),
        dict(id="R6", what_ja="巻き波の組 P3・粒子 0.125 m（条件つき）", dp=0.125, kind="plunge", hours=rr[0.125]["hours_plunge"]),
    ]
    total = sum(r["hours"] for r in runs)
    flip41_pairs = [  # FLIP41 の平らな底で、振幅/格子 1.5 以上の組の（波長/格子、速さの誤差）【測った：summary_tables.md】
        dict(run="B1_T5_h25_dp0.25_relax_HL0.04", L_over_dx=78, a_over_dx=1.56, c_err=-0.0325),
        dict(run="B1_T7_h25_dp0.5_relax_HL0.04", L_over_dx=74, a_over_dx=1.49, c_err=-0.0455),
        dict(run="B1_T7_h25_dp0.25_relax_HL0.04", L_over_dx=149, a_over_dx=2.97, c_err=-0.0046),
        dict(run="B1_T7_h10_dp0.125_relax_H1.0", L_over_dx=239, a_over_dx=2.00, c_err=-0.0045),
        dict(run="B1_T10_h25_dp0.5_relax_HL0.04", L_over_dx=130, a_over_dx=2.61, c_err=-0.0172)]
    for q in flip41_pairs:
        q["C_fit"] = -q["c_err"] * q["L_over_dx"] ** 2
    Lcf, Tcf = full["Lc"], full["Tc"]
    gauges = dict(band_exit=0.25 * Lcf, **{("kc(x-xb)=%+d" % q): (LAB["xb"] + q / p["k"]) * lam for q in [-20, -15, -10, -5, 0, 5, 10]})
    section = dict(x_range=[full["xb"] - 2 * Lcf, full["xb"] + 2 * Lcf], t_from=full["tb"] - 3.5 * Tcf, every_frames=1,
                   note_ja="板の真ん中の断面の水面の場（符号付き距離）。巻くと水面は一つの高さで表せないため")
    criteria = {  # 走らせる前に決めた判定の幅（plan_ja.md §5）
        "A1_band_exit": dict(amp_ratio_tol=0.05, phase_tol_rad=0.1, x=gauges["band_exit"], runs="全部"),
        "A2_low_H_focus": dict(target_H=full["low"]["H_lin_x"], tol=0.05, runs="L1-L3"),
        "A3_low_focus_shift": dict(dx_tol_Lc=0.1, dt_tol_Tc=0.1, at_dp=0.25, also="細かくするとずれが小さくなること", runs="L1-L3"),
        "B1_energy_loss_pre": dict(max_loss=0.05, from_x=gauges["band_exit"], to_x=gauges["kc(x-xb)=-10"], runs="R3,R4,L3"),
        "B3_breaking_loss": dict(record_only=True, up_x=gauges["kc(x-xb)=-10"], down_x=gauges["kc(x-xb)=+10"], ref_ja="R&M：巻き波で 25 % まで"),
        "C1_onset": dict(dt_tol_Tc=0.1, dx_tol_Lc=0.1, pairs=[["R3", "R4"], ["R3", "R5"]]),
        "C2_H_eta_c_onset": dict(tol=0.05),
        "C3_front_steepness_onset": dict(tol=0.10),
        "C4_jet_time_reach": dict(tol=0.10),
        "D1_type": "plunging",
        "D2_onset_x": dict(x_range=full["breaking_band_RM_x"]),
        "D3_touchdown": dict(t=full["tob_DK"], x=full["xob_DK"], dt_tol_Tc=0.25, dx_tol_Lc=0.25),
        "definitions_ja": dict(onset="前の面が初めて鉛直になった時刻と場所", touchdown="前へ出た噴流の先が静かな水面の高さ y = 0 に届いた時刻と場所（D&K の t_ob・x_ob と同じ）",
                               H="その時刻の水面で頂から前の谷まで", eta_c="静かな水面から頂まで",
                               energy_flux="水面のスペクトル × 成分の群速度の和を、同じ時間の窓の線形の値で割る"),
    }
    out = dict(schema="GreatWave.FLIP42.plan_numbers/1", date="2026-10-09",
               note_ja="走らせる前の数。実験の組は【文献】、線形の値は【計算】、時間と速さの誤差の模型は【推定】（2〜4 倍外れうる）",
               sources_ja={"組": "Derakhti, M. 2013 修士論文（University of Delaware）表 3.1・式 2.33・表 3.3（Rapp & Melville 1990 の巻き波の組 P3 を 3D LES で再現）",
                           "崩れの場所": "同論文 §4.2：Rapp & Melville は kc(x − xb) = −5〜0 で崩れたと報告",
                           "エネルギーの減り": "Rapp & Melville 1990 の要旨：群のエネルギーの流れの減りは、一つの崩れ（spilling）で 10 %、巻き波で 25 % まで",
                           "高さの目安": "Cartwright & Nakamura 2009：山から谷までの高さ 10〜12 m（学生の文献整理から）"},
               lab=lab, crest_and_height_lab=ch, full=full, tank=tank, envelope=env, flip41_cost=cost,
               speeds_full=dict(u_crest_lin=u_pre, u_jet_est=u_jet), frames_split=dict(pre=n_pre, post=n_post),
               speed_error_model_note_ja="成分の速さの誤差 e = C (dx/L)²。C は FLIP41 の 5 組の当てはめで 102〜291（中央 250）。焦点がずれる量の目安で、群で確かめた値ではない【推定】",
               flip41_speed_pairs=flip41_pairs,
               gauges_full=gauges, section_record=section, criteria=criteria,
               resolutions=res, runs=runs, runs_conditional=cond, hours_total_runs=total,
               hours_total_range_x2_x4=[2 * total, 4 * total])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(dict(lab={k2: lab[k2] for k2 in ["Tc", "Lc", "kc", "kc_xb", "L_range", "kh_range", "cg_range", "tob_minus_tb_over_Tc", "xob_minus_xb_over_Lc", "breaking_band_RM_x"]},
                          ch=ch, full=full, tank={k2: v for k2, v in tank.items() if k2 != "inlet_window"}, win=win, env=env,
                          cost=cost, speeds=out["speeds_full"], split=out["frames_split"], runs=runs, cond=cond, total=total), ensure_ascii=False, indent=1))
    for r in res:
        print("dp %.3f dx %.2f lab %.1f mm Lc/dx %.0f Ls/dx %.0f H/dx %.1f inlet a/dx %.2f (low %.2f) nx %d part %.2fM sub %d/%d s/f %.2f h %.2f (dt/2 %.2f, low %.2f)" % (
            r["dp"], r["dx"], r["dx_lab_mm"], r["Lc_over_dx"], r["Lshort_over_dx"], r["H_lin_over_dx"], r["inlet_amp_over_dx_S0352"],
            r["inlet_amp_over_dx_S010"], r["nx"], r["particles_est"] / 1e6, r["substeps_pre"], r["substeps_jet"], r["s_per_frame_est"],
            r["hours_plunge"], r["hours_plunge_dt_half"], r["hours_low"]))
        for kk, v in r["speed_error_model"].items():
            print("   ", kk, {k3: round(v3, 4) for k3, v3 in v.items()})
        print("    low C250", {k3: round(v3, 4) for k3, v3 in r["speed_error_model_low_C250"].items()})


if __name__ == "__main__":
    main()
