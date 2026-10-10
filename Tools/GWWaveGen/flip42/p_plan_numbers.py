# -*- coding: utf-8 -*-
"""FLIP42 計画（凍結版）の数を出す（py -3.10、numpy）。新しい流体の計算はしない。
見直し（plan/review_ja.md、数は plan/review_numbers.json）を受けて、走らせる前に直した版。
見直しの前の版は p_plan_numbers_v0.py（出力 plan/v0_before_review/plan_numbers.json）。
読むもの（読むだけ）：Unity/Build/FLIP41/verify/runs.jsonl。
出力：Unity/Build/FLIP42/plan/plan_numbers.json

数の種類：
- 実験の組の値は【文献】（Derakhti 2013 の修士論文の表 3.1・式 2.33）。
- 線形の重ね合わせの値は【計算】（成分ごとに ω² = g k tanh(kh)、g は Houdini の既定 9.80665）。
- 計算の時間と、格子による速さの誤差の模型は【推定】（FLIP41 の測った値からの比）。

v0 から変えた所（理由は plan_ja.md §0.1）：
- 水槽の座標を FLIP41 と同じにした（造波の帯 0〜x_p、造波板の位置 x_p = 1 Lc）。位置は「造波板からの距離 x − x_p」と場面の x の両方で出す。
- 計算の終わりを t_ob + 3 Tc にした。測る点 +5・+10 を取った。群が集まる所を写す広い窓を足した。
- 低い群の L1・L2 を取り、L3 は任意にした。判定（criteria）を A1・A2'・A3'・B1・B2・N1・N2・C1〜C4・D1〜D3 にした（B3・D4 を取った）。
- 粒子の帯の厚さを m で決めた（4 m）。帯なしの R1b を必ず走らせる。
- 最大小刻みを 8 にした。時間の刻みの比べは、R3 の途中保存から始める R5'。
- 計算の時間を、水のある格子の数から見積もり直した（見直し §6 と同じ式）。帯を厚くして粒子が増える分の上限も出す。
"""
import os, json
import numpy as np
import v_lin as L

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
OUT = os.path.join(ROOT, "Unity/Build/FLIP42/plan/plan_numbers.json")
RUNS41 = os.path.join(ROOT, "Unity/Build/FLIP41/verify/runs.jsonl")
G = L.G

# ---- 実験の組（実験室の大きさ）【文献】
LAB = dict(h=0.60, fc=0.88, dff=0.73, N=32, S=0.352, xb=8.46, tb=20.5,
           tob_DK=19.04, xob_DK=8.35,   # D&K の表 3.1：前へ出た噴流が静かな水面に当たった時刻と場所（実験の値か計算の値かは表から確かめきれない）
           S_incipient=0.257, S_spilling=0.278, xb_S2=7.46)   # S 0.278 の組（表 3.1 の S2）は焦点 x_b が 7.46 m で、P3 と違う
S_LOW = 0.10          # 低い群（L3 だけ。任意）
H_TARGET = (10.0, 12.0)   # Cartwright & Nakamura 2009：山から谷までの高さ（波高）
LAM = 70.0            # 選んだ倍率
DPS = [0.5, 0.35, 0.25, 0.177, 0.125]   # 粒子の間隔（実物の大きさ、m）。格子 = 粒子 × 2
FPS = 24.0
NB_M = 4.0            # 粒子の帯（Narrow Band）の厚さ（m）。どの細かさでも同じ
MAXSUB = 8            # 最大小刻み
CKPT_EVERY_R3 = 237   # R3 の途中保存の間隔（コマ）。237 × 14 = 3318 コマ目（t_b − 3.5 Tc の直前）に途中保存ができる
A1_SUBBANDS = [[1, 11], [12, 21], [22, 32]]


def comps(S, h=LAB["h"], fc=LAB["fc"], dff=LAB["dff"], N=LAB["N"]):
    f = np.linspace(fc * (1 - dff / 2), fc * (1 + dff / 2), N)
    om = 2 * np.pi * f
    k = np.array([L.k_of_omega(o, h) for o in om])
    a = np.full(N, S / k.sum())          # どの成分も振幅が同じ群：S = Σ a k
    cg = np.array([L.props(2 * np.pi / o, h)["cg"] for o in om])
    return f, om, k, a, cg


def eta(x, t, om, k, a, xb=LAB["xb"], tb=LAB["tb"], kk=None):
    """線形の重ね合わせ η = Σ a cos(k(x − xb) − ω(t − tb))（式 2.33 と同じ。x = 0 が造波板の位置）。
    kk を与えると、x ≥ 0 の自由な所だけ波数を kk にする（格子による遅れの模型。x = 0 の位相は同じ）。"""
    x = np.atleast_1d(np.asarray(x, float)); t = np.atleast_1d(np.asarray(t, float))
    ph0 = -k * xb
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


def inlet_window(S, x):
    """x での η(t)² の積み上げ：始めの 1 周期に入る割合など。"""
    f, om, k, a, cg = comps(S)
    ts = np.arange(-20.0, 40.0, 0.002)
    e = eta([x], ts, om, k, a)[0]
    E = np.cumsum(e * e); E /= E[-1]
    i = np.searchsorted(ts, 1.0 / LAB["fc"])
    return dict(energy_before_t_Tc=float(E[i]), t_1pct=float(ts[np.searchsorted(E, 0.01)]), t_99pct=float(ts[np.searchsorted(E, 0.99)]))


def focus_with_speed_error(S, dx_lab, Cerr):
    """格子による遅れの模型：成分 i の速さが c(1 − e_i)、e_i = C (dx/L_i)²（FLIP41 の平らな底の測った値の当てはめ）。
    x = 0 の位相は造波で決まるので同じ。焦点（水面の最大）の場所・時刻と、頂・高さ（前の谷まで）の比を出す。
    A3' では、e_i の代わりに A2' で測った値を入れる。"""
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


def hilbert_env(e):
    n = len(e); F = np.fft.fft(e); Hh = np.zeros(n); Hh[0] = 1
    if n % 2 == 0:
        Hh[n // 2] = 1; Hh[1:n // 2] = 2
    else:
        Hh[1:(n + 1) // 2] = 2
    return np.abs(np.fft.ifft(F * Hh))


def extrema_pairs(e):
    """時系列の隣り合う頂と谷の差の最大と、深い谷 3 つ。"""
    d = np.diff(e); idx = np.where(np.sign(d[1:]) != np.sign(d[:-1]))[0] + 1
    ex = e[idx]
    Hadj = float(np.max(np.abs(np.diff(ex)))) if len(ex) > 1 else 0.0
    troughs = np.sort(ex[ex < 0])[:3]
    return Hadj, [float(v) for v in troughs]


def flip41_costs():
    """FLIP41 の記録から（読むだけ）：
    - 帯 4 格子の計算の粒子の数 ×dp÷水槽の長さ（v0 と同じ選び方）
    - 帯 4 格子で水のある格子が 10 万個以上の計算の「格子 1 個・1 コマ（小刻み）あたりの秒」（見直し §6 と同じ選び方）
    - 帯なしで粒子 0.5 m の 2 本の「百万粒子・1 コマあたりの秒」（同じ）"""
    rows = [json.loads(l) for l in open(RUNS41, encoding="utf-8")]
    per_m, cell, nb0 = [], [], []
    for r in rows:
        p = r["parms"]
        if r["run_id"].startswith("smoke") or r["f_end_done"] - r["f_start"] < 500 or p.get("minsub", 1) > 1:
            continue
        spf = r["wall_per_frame_median_s"]
        if p.get("band_vox", 4) > 100:
            if "dp0.5" in r["run_id"]:
                nb0.append((r["run_id"], spf / (r["particles_max"] / 1e6)))
            continue
        per_m.append(r["particles_max"] * p["dp"] / p["Lx"])
        if p.get("band_vox", 4) == 4:
            dx = p["dp"] * p.get("gridscale", 2.0); xs = np.linspace(0, p["Lx"], 2000)
            hb = L.bed_profile(xs, p["h0"], p.get("xs0", 1e6), p.get("slope_n", 0), p.get("h1", p["h0"]))
            ncell = (p["Lx"] / dx) * (hb.mean() / dx) * 4
            if ncell >= 1e5:
                cell.append((r["run_id"], ncell, spf / ncell * 1e6))
    us = [c[2] for c in cell]; pp = [v for _, v in nb0]
    return dict(particles_dp_per_m_median=float(np.median(per_m)), particles_dp_per_m_range=[float(min(per_m)), float(max(per_m))],
                us_per_cell_frame_range=[float(min(us)), float(max(us))], us_runs=[[c[0], round(c[1]), round(c[2], 2)] for c in cell],
                nb0_s_per_frame_per_Mparticle_range=[float(min(pp)), float(max(pp))], nb0_runs=[[a, round(b, 2)] for a, b in nb0],
                note_ja="帯 4 格子の粒子の数は v0 と同じ選び方。格子と帯なしの秒は見直し（review_numbers.json の cost）と同じ選び方【測った・推定】")


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
    Hx = ch["%.3f" % LAB["S"]]["H_x"]
    lam = LAM; s = np.sqrt(lam)
    full = dict(lam=lam, lam_exact_for_H11=11.0 / Hx, sqrt_lam=s,
                H_lin_x=Hx * lam, eta_c_lin=ch["%.3f" % LAB["S"]]["eta_c_lin"] * lam, H_lin_t=ch["%.3f" % LAB["S"]]["H_t"] * lam,
                H_target_range_lam=[H_TARGET[0] / Hx, H_TARGET[1] / Hx],
                h=LAB["h"] * lam, Tc=p["T"] * s, T_range=[1 / f[-1] * s, 1 / f[0] * s], Lc=p["L"] * lam,
                L_range=[lab["L_range"][1] * lam, lab["L_range"][0] * lam], cc=p["c"] * s, cgc=float(p["cg"]) * s,
                xb=LAB["xb"] * lam, tb=LAB["tb"] * s, xob_DK=LAB["xob_DK"] * lam, tob_DK=LAB["tob_DK"] * s,
                a_component=a[0] * lam, breaking_band_RM_x=[v * lam for v in lab["breaking_band_RM_x"]],
                f_range=[float(f[0] / s), float(f[-1] / s)],
                low=dict(S=S_LOW, eta_c_lin=ch["%.3f" % S_LOW]["eta_c_lin"] * lam, H_lin_x=ch["%.3f" % S_LOW]["H_x"] * lam))
    Tc, Lc, xb, tb, tob = full["Tc"], full["Lc"], full["xb"], full["tb"], full["tob_DK"]
    kc_full = 2 * np.pi / Lc
    # ---- 水槽（実物の大きさ。座標は FLIP41 と同じ：x = 0 が左の壁、造波の帯 0〜x_p、x_p が造波板の位置）
    XP = 1.0 * Lc
    x_abs0_rel = xb + 2.5 * Lc            # 吸う帯の始まり（造波板から）
    x_end_rel = x_abs0_rel + 1.0 * Lc     # 右の壁（造波板から）
    Lx = XP + x_end_rel
    cg_full = cg * s
    t_end = tob + 3.0 * Tc                # 噴流が水面に当たってから 3 周期（見た目に要る着水と跳ね上がりまで）
    frames = int(round(t_end * FPS))
    t_rs = tb - 3.5 * Tc                  # 断面の記録の始め・R5' の始め
    f_rs = CKPT_EVERY_R3 * int(np.floor((t_rs * FPS + 1) / CKPT_EVERY_R3))   # Houdini はコマ f の時刻が (f − 1)/24
    t_rs_ck = (f_rs - 1) / FPS
    t_refl = tb + (x_end_rel - xb) / cg_full.max() + (x_end_rel - (xb + 0.5 * Lc)) / cg_full.max()
    win = inlet_window(LAB["S"], 0.0)
    tank = dict(coords_ja="場面の x：0 が左の壁。造波の帯 0〜x_p（中心の波長 1 つ）。x_p が造波板の位置（実験の x = 0）。記録と図の位置は x − x_p",
                x_p=XP, band=[0.0, XP], wall_taper_m=0.25 * Lc, free=[XP, XP + x_abs0_rel], absorber=[XP + x_abs0_rel, Lx], Lx=Lx,
                free_rel=[0.0, x_abs0_rel], absorber_rel=[x_abs0_rel, x_end_rel],
                y_bottom=-full["h"], y_top=18.0, slab_cells_z=4,
                t_start=0.0, t_end=t_end, frames=frames, ramp=1.0 * Tc, inlet_energy_in_first_period=win["energy_before_t_Tc"],
                t_reflection_back_at_focus_plus_half_Lc=t_refl, reflection_after_end=bool(t_refl > t_end),
                energy_front_x_rel_at_end=float(xb + cg_full.max() * (t_end - tb)),
                restart_R5=dict(t_target=t_rs, ckpt_every_R3=CKPT_EVERY_R3, frame=f_rs, t=t_rs_ck),
                note_ja="x_p は CTRL に置き、成分の位相は k_i(x − x_p − x_b) − ω_i(t − t_b) で書く（FLIP41 の重みの式 relaxw((xg_end − x)/xg_end) は帯が 0〜xg_end にある前提）")
    # ---- 測る点（造波板からの距離）
    gauges_rel = dict(band_exit=0.25 * Lc, **{("kc(x-xb)=%+d" % q): xb + q / kc_full for q in [-20, -15, -10, -5, 0]})
    gauges = {n: dict(x_rel=v, x_scene=v + XP) for n, v in gauges_rel.items()}
    ts = np.arange(0.0, t_end, 0.02)
    for n, g in gauges.items():
        e = eta([g["x_rel"] / lam], ts / s, om, k, a)[0] * lam
        en = hilbert_env(e); w = e * e
        Hadj, tr = extrema_pairs(e)
        g.update(H_lin_adjacent_max=Hadj, deepest_troughs_lin=tr, env_Eweighted=float((en * w).sum() / w.sum()),
                 env_over_dx={("dp%.3f" % dp): float((en * w).sum() / w.sum() / (2 * dp)) for dp in DPS})
    section = dict(x_rel=[xb - 2 * Lc, xb + 2 * Lc], t_from=t_rs, every_frames=1,
                   note_ja="板の真ん中の断面の水面の場（符号付き距離）。巻くと水面は一つの高さで表せないため")
    wide_view = dict(x_rel=[150.0, 750.0], t_from=tb - 6 * Tc, source_ja="一番上の水面の高さの記録（巻く前）。巻いた後は断面の記録",
                     note_ja="群が集まり、険しくなる所を写す広い窓。計算は足さない")
    # ---- 細かさ・帯・小刻み・時間
    cost = flip41_costs()
    u_pre = float((a * om).sum()) * s
    u_jet = float(np.sqrt((p["c"] * s) ** 2 + 2 * G * Hx * lam))
    t_on, t_off = tob - Tc, t_end     # 噴流の区間（小刻みが増える）：t_ob − 1 Tc から終わりまで

    def subframes(t0, t1, sub_jet, mult=1):
        jet = max(0.0, min(t1, t_off) - max(t0, t_on)) * FPS
        other = max(0.0, t1 - t0) * FPS - jet
        return (other + jet * sub_jet) * mult

    res = []
    for dp in DPS:
        dx = 2 * dp
        bv = int(np.ceil(NB_M / dx - 1e-9))
        ratio = (bv + 1) / 5.0                    # 粒子を置く厚さ (band_vox + 1)·dx。FLIP41 の帯 4 格子との比
        cells = (Lx / dx) * (full["h"] / dx) * 4
        parts_b = cost["particles_dp_per_m_median"] * Lx / dp * ratio
        parts_nb0 = Lx * (full["h"] + 2) * (4 * dx) / dp ** 3
        sub_pre = max(1, int(np.ceil(u_pre / FPS / dx)))
        sub_jet = max(1, int(np.ceil(u_jet / FPS / dx)))
        errs = {("C%d" % C): focus_with_speed_error(LAB["S"], dx / lam, C) for C in (100, 250, 290)}
        res.append(dict(dp=dp, dx=dx, dx_lab_mm=dx / lam * 1000, Lc_over_dx=Lc / dx, Lshort_over_dx=full["L_range"][0] / dx,
                        H_lin_over_dx=full["H_lin_x"] / dx, band_vox=bv, band_m=bv * dx, particle_depth_ratio_vs_4vox=ratio,
                        nx=int(round(Lx / dx)), cells_M=cells / 1e6, particles_band_M=parts_b / 1e6, particles_nb0_M=parts_nb0 / 1e6,
                        substeps_pre=sub_pre, substeps_jet=sub_jet, substeps_jet_ok=bool(sub_jet <= MAXSUB),
                        speed_error_model=errs))
    rr = {r["dp"]: r for r in res}
    us_lo, us_hi = cost["us_per_cell_frame_range"]; pp_lo, pp_hi = cost["nb0_s_per_frame_per_Mparticle_range"]

    def hours(dp, nsf):
        r = rr[dp]; c = r["cells_M"] * 1e6
        b = [us_lo * 1e-6 * c * nsf / 3600, us_hi * 1e-6 * c * nsf / 3600]
        return dict(band4m=[round(b[0], 2), round(b[1], 2)], band4m_upper_if_particles=round(b[1] * r["particle_depth_ratio_vs_4vox"], 2),
                    nb0=[round(pp_lo * r["particles_nb0_M"] * nsf / 3600, 2), round(pp_hi * r["particles_nb0_M"] * nsf / 3600, 2)])

    def sf(dp, t0=0.0, t1=t_end, mult=1):
        return subframes(t0, t1, rr[dp]["substeps_jet"], mult)

    t_low = tb + 1.5 * Tc
    runs = [
        dict(order=1, id="R1", dp=0.5, setting_ja="帯 4 m（粒子 0.5 m では 4 格子）", t=[0.0, t_end],
             purpose_ja="道具の通しと下見の動画。判定しない（巻かないこともある）。N1・N2 の片方", hours_used="band4m", **hours(0.5, sf(0.5))),
        dict(order=2, id="R1b", dp=0.5, setting_ja="帯なし（水の全体に粒子）", t=[0.0, t_end],
             purpose_ja="帯を決める（N1・N2）。帯なしの重さを測る", hours_used="nb0", **hours(0.5, sf(0.5))),
        dict(order=3, id="R3", dp=0.25, setting_ja="R1・R1b で決めた帯。途中保存 %d コマごと" % CKPT_EVERY_R3, t=[0.0, t_end],
             purpose_ja="評価に出す最初の動画。A1・A2'・A3'・B1・D1〜D3", hours_used="band4m か nb0（N1・N2 で決まる）", **hours(0.25, sf(0.25))),
        dict(order=4, id="R5'", dp=0.25, setting_ja="R3 の %d コマ目（%.1f s）の途中保存から、CFL の値を半分・最小小刻み 2" % (f_rs, t_rs_ck), t=[t_rs_ck, t_end],
             purpose_ja="(c) 時間の刻み（C1〜C4 を R3 と比べる）", hours_used="band4m か nb0（N1・N2 で決まる）", **hours(0.25, sf(0.25, t_rs_ck, t_end, 2))),
        dict(order=5, id="R4", dp=0.177, setting_ja="R3 と同じ設定", t=[0.0, t_end],
             purpose_ja="(c) 細かさ（C1〜C4 を R3 と比べる）。A1・A2'・A3'・B1・D1〜D3", hours_used="band4m か nb0（N1・N2 で決まる）", **hours(0.177, sf(0.177))),
    ]
    cond = [
        dict(id="R2", dp=0.35, t=[0.0, t_end], when_ja="(c) で R3 と R4 が幅に入らなかった時の細かさの並び、または帯なしで R4 が 12 時間を越える見込みの時に R3 と先に比べる",
             **hours(0.35, sf(0.35))),
        dict(id="L3", dp=0.25, S=S_LOW, t=[0.0, t_low], when_ja="任意。判定に使わない。R の計算が全部終わって時間が残れば。入口の包絡 1.6 格子で、FLIP41 の同じ範囲では 3 波長で 4〜15 % 減った",
             **hours(0.25, t_low * FPS)),
        dict(id="R6", dp=0.125, t=[0.0, t_end], when_ja="この段では走らせない（参考）。(c) が入らず細かくする必要が出たら、その事実と時間を報告する",
             **hours(0.125, sf(0.125))),
    ]
    main_ids = ["R1", "R1b", "R3", "R5'", "R4"]
    hb = {r["id"]: r for r in runs}
    tot_band = [round(hb["R1"]["band4m"][0] + hb["R1b"]["nb0"][0] + sum(hb[i]["band4m"][0] for i in main_ids[2:]), 2),
                round(hb["R1"]["band4m"][1] + hb["R1b"]["nb0"][1] + sum(hb[i]["band4m"][1] for i in main_ids[2:]), 2)]
    tot_band_up = round(hb["R1"]["band4m"][1] + hb["R1b"]["nb0"][1] + sum(hb[i]["band4m_upper_if_particles"] for i in main_ids[2:]), 2)
    tot_nb0 = [round(hb["R1"]["band4m"][0] + sum(hb[i]["nb0"][0] for i in main_ids[1:]), 2),
               round(hb["R1"]["band4m"][1] + sum(hb[i]["nb0"][1] for i in main_ids[1:]), 2)]
    # ---- 判定（走らせる前に決めた。plan_ja.md §5）
    clean = [i + 1 for i in range(len(f)) if (f[-1] - f[0]) < f[i] < 2 * f[0]]
    criteria = {
        "A1_band_exit": dict(x_rel=gauges_rel["band_exit"], window_s=[0.0, t_end], subbands_components=A1_SUBBANDS,
                             amp_ratio_tol=0.05, phase_tol_rad=0.1, S_measured_tol=0.05, S_range=[0.352 * 0.95, 0.352 * 1.05], runs="全部",
                             on_fail_ja="帯を直す（まず帯を 2 Lc に長くする）。直し方と理由を record_ja.md に書き、2 回まで"),
        "A2p_propagation": dict(points_rel=[gauges_rel["band_exit"], gauges_rel["kc(x-xb)=-15"]], window_s=[0.0, t_end],
                                band_Hz=[float((f[-1] - f[0]) / s), float(2 * f[0] / s)], components=[clean[0], clean[-1]],
                                record_ja="周波数ごとの速さの誤差と振幅の変化（線形の値のフーリエ変換との比の、二つの点の間の変わり方）",
                                third_order_speed_bias_est=[0.002, 0.004], runs="R1・R1b・R3・R5'・R4（判定は A3' と B1 で）"),
        "A3p_focusing": dict(crest_ratio_min=0.95, H_ratio_min=0.95, dx_tol_Lc=0.1, dt_tol_Tc=0.1, also="R4 のずれが R3 より小さいこと",
                             runs="R3・R4", on_fail_ja="D3 を R4 の値で判定する。主な細かさは B1 と (c) で決める"),
        "B1_energy_loss_pre": dict(max_loss=0.05, from_x_rel=gauges_rel["band_exit"], to_x_rel=gauges_rel["kc(x-xb)=-10"],
                                   sum_ja="成分の帯域（f_1〜f_N）の中で足す。帯域の外のエネルギーは別に書く", runs="R3・R4（R1・R1b は記録）"),
        "B2_dissipation_effect": "細かさで減りが変わっても (c) が幅に入れば、減りは結果を変えていないと読む。粒子の帯による減りは N1・N2 で見る",
        "N1_band_troughs": dict(points_rel=[gauges_rel["band_exit"], gauges_rel["kc(x-xb)=-20"], gauges_rel["kc(x-xb)=-10"]],
                                quantity_ja="群が通る間の最も深い谷 3 つの深さの平均（R1 と R1b の差）。平均にするのは、一つの谷の読みのばらつきで判定が動かないようにするため", tol_frac_of_local_H_lin=0.05,
                                deepest_troughs_lin={n: gauges[n]["deepest_troughs_lin"] for n in ["band_exit", "kc(x-xb)=-20", "kc(x-xb)=-10"]},
                                local_H_lin={n: gauges[n]["H_lin_adjacent_max"] for n in ["band_exit", "kc(x-xb)=-20", "kc(x-xb)=-10"]}),
        "N2_band_shape": dict(quantity_ja="最も険しくなった時刻（巻き始めがあればその時刻）の H・η_c（±5 %）と前の面の険しさ（±10 %）", tol_H=0.05, tol_steep=0.10,
                              decide_ja="N1 か N2 が幅を越えたら、以後は帯なし。どちらも入れば帯 4 m"),
        "C1_onset": dict(dt_tol_Tc=0.1, dx_tol_Lc=0.1, pairs=[["R3", "R4"], ["R3", "R5'"]]),
        "C2_H_eta_c_onset": dict(tol=0.05),
        "C3_front_steepness_onset": dict(tol=0.10),
        "C4_jet_time_reach": dict(tol=0.10),
        "D1_type": "plunging",
        "D2_onset_x_rel": dict(x_range=full["breaking_band_RM_x"]),
        "D3_touchdown": dict(t=tob, x_rel=full["xob_DK"], dt_tol_Tc=0.25, dx_tol_Lc=0.25),
        "R1_note_ja": "R1（実験室の格子 14.3 mm）は D&K の 2D の確かめで形が出なかった 16 mm に近い。R1 で前へ巻かなくても方法の失敗とは読まない",
        "definitions_ja": dict(onset="前の面が初めて鉛直になった時刻と場所", touchdown="前へ出た噴流の先が静かな水面の高さ y = 0 に届いた時刻と場所（D&K の t_ob・x_ob と同じ）",
                               H="その時刻の水面で頂から前の谷まで", eta_c="静かな水面から頂まで",
                               energy_flux="水面のスペクトル × 成分の群速度の和を、同じ時間の窓の線形の値で割る"),
    }
    solver = dict(veltransfer="apic", gridscale=2.0, minsub=1, maxsub=MAXSUB, cfl_ja="既定の値（R5' だけ半分。パラメーターの名前は場面で確かめる）",
                  narrowband_m=NB_M, relax_weight_ja="w_dt = 1 − (1 − w)^(dt/dt0)、dt0 = 1/24 s（小刻みの長さに合わせる）",
                  stretch_ja="水面より上の流速は、32 成分を足した η で全成分を伸ばす（Wheeler の形）",
                  record_ja="一番上の水面の高さ（毎コマ）、断面の水面の場、各コマの小刻みの数（または刻みの長さ）")
    out = dict(schema="GreatWave.FLIP42.plan_numbers/2", date="2026-10-09", frozen=True,
               note_ja="凍結した計画の数（見直しを受けて走らせる前に直した版）。実験の組は【文献】、線形の値は【計算】、時間と速さの誤差の模型は【推定】",
               v0="plan/v0_before_review/plan_numbers.json（p_plan_numbers_v0.py）", review="plan/review_numbers.json（r_review_numbers.py）",
               sources_ja={"組": "Derakhti, M. 2013 修士論文（University of Delaware）表 3.1・式 2.33・表 3.3（Rapp & Melville 1990 の巻き波の組 P3 を 3D LES で再現）",
                           "崩れの場所": "同論文 §4.2：Rapp & Melville は kc(x − xb) = −5〜0 で崩れたと報告",
                           "高さの目安": "Cartwright & Nakamura 2009：山から谷までの高さ 10〜12 m（学生の文献整理から。どちらの意味の波高かは読めていない）"},
               lab=lab, crest_and_height_lab=ch, full=full, tank=tank, gauges=gauges, section_record=section, wide_view=wide_view,
               solver=solver, flip41_cost=cost, speeds_full=dict(u_crest_lin=u_pre, u_jet_est=u_jet),
               speed_error_model_note_ja="成分の速さの誤差 e = C (dx/L)²。C は FLIP41 の 5 組の当てはめで 102〜291（中央 250）。焦点がずれる量の目安で、群で確かめた値ではない【推定】",
               criteria=criteria, resolutions=res, runs=runs, runs_conditional=cond,
               hours_total=dict(band4m=tot_band, band4m_upper_if_particles=tot_band_up, nb0=tot_nb0,
                                note_ja="R1〜R4 の 5 本。帯 4 m の道は R1b を帯なしで数える。崩れの後の重さと、FLIP41 より大きい格子での伸び方は入っていない【推定】"),
               tool_work_hours=[4, 6])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(dict(full={k2: full[k2] for k2 in ["Tc", "Lc", "xb", "tb", "tob_DK", "xob_DK", "H_lin_x", "eta_c_lin", "f_range", "T_range", "L_range"]},
                          tank={k2: v for k2, v in tank.items() if not k2.endswith("_ja")}, gauges=gauges, wide=wide_view, section=section,
                          A2p=criteria["A2p_propagation"], N1=criteria["N1_band_troughs"], cost={k2: v for k2, v in cost.items() if k2 != "us_runs"},
                          runs=runs, cond=cond, totals=out["hours_total"]), ensure_ascii=False, indent=1))
    for r in res:
        print("dp %.3f dx %.3f lab %.1f mm Lc/dx %.0f Ls/dx %.0f bv %d (%.2f m) ratio %.1f nx %d cells %.2fM part band %.2fM nb0 %.2fM sub %d/%d" % (
            r["dp"], r["dx"], r["dx_lab_mm"], r["Lc_over_dx"], r["Lshort_over_dx"], r["band_vox"], r["band_m"], r["particle_depth_ratio_vs_4vox"],
            r["nx"], r["cells_M"], r["particles_band_M"], r["particles_nb0_M"], r["substeps_pre"], r["substeps_jet"]))
        print("    C250", {k3: round(v3, 4) for k3, v3 in r["speed_error_model"]["C250"].items()})


if __name__ == "__main__":
    main()
