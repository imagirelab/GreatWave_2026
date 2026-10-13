# -*- coding: utf-8 -*-
"""FLIP47：周期の波の実験（S2・S5 の海底で、後ろに谷のある波を同じ所で繰り返し崩す）の設計の数（py -3.10 -B。numpy・scipy だけ）。
2026-10-13 周期の波の設計の役（Claude）が新しく書いた。Houdini は使わない。ほかの道具は読むだけ（targets.json の海底、g47_common の箱）。
書く物：Unity/Build/FLIP47/periodic/（中間の表）と Unity/Build/FLIP47/periodic_design.json。

何を出すか
  1 規則波の浅くなる間の高さ：19 m の平らで流れ関数の解（g47_sfwave、平均の質量の流れ 0）を入れ、エネルギーの流れを保って浅い所の H を解く
    （ゆっくり変わる海底の近似。跳ね返りなし）。定常の波で運べなくなる水深 h_SF（＝それより前に崩れ始める目安）を出す。
  2 崩れる所の予測【推定】：(a) h_SF、(b) Goda 2010 の崩れの指数（規則波、A 0.17、1 + 11 tan^{4/3}β。Goda 1970 の 15 も並べる）。
    h_SF より浅い所の H は Green の式（h^{-1/4}）で延ばす（定常の限りを越えて急な斜面で育つ分の下限の目安）。
    崩れの頂 η_c,b = （h_SF の解の η_c/H）× H_b。Iribarren の数 ξ0・ξb、跳ね返り Kr ≈ 0.1 ξ0²（Battjes 1974）。
  3 群の案：(b) 集まる群（f_n = m_n/P、FLIP44 の繰り返しの入口）の 19 m での集まりの効き、(c) 二つの周波数の群の束縛の長い波。
  4 3 本の計算（P1・P2・P3）と予備（R4）の水槽・帯・吸う帯・コマ・費用・判定の量と帯。
使い方：py -3.10 -B g47_periodic.py [explore|design]
  explore：T 12・14・16 s × H19 の表（periodic/shoal_table.json）だけ。design：設計を書く（explore の表も作り直す）。
"""
import os, sys, json, math, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_sfwave as SF
import g47_common as GC

G = SF.G
H0 = 19.0
B47 = GC.B47
OUTD = B47 + "/periodic"
TARGETS = B47 + "/targets.json"
DP = 0.25
PPM2 = 838720.0 / 6611.0          # 粒子 0.25 m の 1 m² あたりの粒子（S2 の 1 コマ目 83.9 万 ÷ 水の面積 6,611 m²）【測った】
SEC_PER_FRAME_PER_M = (1.0, 1.6)  # 1 コマ・百万粒子あたりの秒。海底の組 0.93〜1.17（着水の 2.5 s 後まで）【測った】、続けて崩れる分を上に見る【推定】
GROWTH = (1.0, 1.5)              # reseed で粒子が増える倍率（海底の組で 1.4〜1.5 倍【測った】）
FPS = 24.0


def beds():
    t = json.load(open(TARGETS, encoding="utf8"))
    out = {}
    for s in t["scan"]:
        if s["id"] == "S2_s1-10":
            out["S2"] = dict(id=s["id"], bed=s["bed"], s=float(s["s"]), x_toe=570.0, x_top=float(s["x_top"]), h_top=1.9, name_ja=s["name_ja"])
        if s["id"] == "S5_ledge1-7":
            out["S5"] = dict(id=s["id"], bed=s["bed"], s=float(s["s"]), x_toe=570.0, x_top=float(s["x_top"]), h_top=3.8, name_ja=s["name_ja"])
    return out


def L0_of(T):
    return G * T * T / (2 * math.pi)


def goda_Hb(h, T, s, coef=11.0, A=0.17):
    L0 = L0_of(T)
    return A * L0 * (1 - math.exp(-1.5 * math.pi * h / L0 * (1 + coef * s ** (4.0 / 3.0))))


# ------------------------------------------------------------------ 1 浅くなる間（海底によらない：水深だけで決まる）
def track(T, H19, N=40, h_end=2.0):
    s = SF.solve(H0, T, H19, N=N)
    if not s["ok"]:
        raise RuntimeError("19 m の解が解けない T %g H %g: %s" % (T, H19, s["msg"]))
    F0 = SF.energy_flux(s)
    rows = []

    def row(sv, h):
        pm = SF.profile_measures(sv)
        return dict(h=h, H=sv["H"], H_over_Hmax=sv["H"] / SF.highest_H(h, T), eta_c=pm["eta_c"], eta_t=pm["eta_t"], eta_c_over_H=pm["eta_c_over_H"],
                    width07=pm["width07_over_eta_c"], back_deg=pm["back_angle_07_09_deg"], c=sv["c"], u1=sv["u1"], L=sv["L"], ursell=sv["ursell"])
    rows.append(row(s, H0))
    h = H0; prev = s; h_sf = None; best = None
    while h > h_end + 1e-9:
        dh = 0.5 if rows[-1]["H_over_Hmax"] < 0.85 else 0.25
        hn = round(h - dh, 4)
        sn, bestF, Hcap = SF.shoal_step(F0, hn, T, prev)
        if sn is None:
            # もう少し細かく：h と hn の間を 0.05 m で
            hh = h
            while hh - 0.05 > hn - 1e-9:
                hq = round(hh - 0.05, 4)
                sq, bF, _ = SF.shoal_step(F0, hq, T, prev)
                if sq is None:
                    h_sf = hq; best = bF
                    break
                rows.append(row(sq, hq)); prev = sq; hh = hq
            if h_sf is None:
                h_sf = hn; best = bestF
            break
        rows.append(row(sn, hn)); prev = sn; h = hn
    return dict(T=T, H19=H19, F0=F0, rows=rows, h_SF=h_sf, F_best_at_hSF_over_F0=(best / F0 if best else None),
                sol19=SF.table(s), prof19=SF.profile_measures(s))


def breaking(tr, bed, coef):
    """崩れる所の予測。coef = None なら h_SF（定常の限り）、数なら Goda の 1 + coef tan^{4/3}β。"""
    T = tr["T"]; s = bed["s"]; rows = tr["rows"]
    last = rows[-1]
    xof = lambda h: bed["x_toe"] + (H0 - h) / s
    L0 = L0_of(T)
    H0eq = math.sqrt(8 * tr["F0"] / (G * G * T / (4 * math.pi)))      # 深い水の線形の同じエネルギーの流れの高さ
    xi0 = s / math.sqrt(H0eq / L0)
    if coef is None:
        hb = last["h"]; Hb = last["H"]; ec = last["eta_c"]; how = "h_SF（定常の波で運べる最後の水深）"
    else:
        hb = None
        hs = np.arange(H0, bed["h_top"] - 1e-9, -0.01)
        rh = np.array([r["h"] for r in rows])[::-1]; rH = np.array([r["H"] for r in rows])[::-1]
        for h in hs:
            if h >= last["h"]:
                H = float(np.interp(h, rh, rH))
            else:
                H = last["H"] * (last["h"] / h) ** 0.25
            if H >= goda_Hb(h, T, s, coef):
                hb = float(h); Hb = H
                break
        if hb is None:
            return dict(method="goda_%g" % coef, broke=False, note_ja="棚の上まで崩れない（Goda の指数に届かない）")
        ec = last["eta_c_over_H"] * Hb
        how = "Goda %s（1 + %g tan^{4/3}β、A 0.17）。h_SF より浅い所の H は Green の式で延ばした" % ("2010" if coef == 11 else "1970", coef)
    xb = xof(hb)
    return dict(method=("h_SF" if coef is None else "goda_%g" % coef), how_ja=how, broke=True, h_b=hb, x_b=xb, H_b=Hb, eta_c_b=ec,
                gamma_b=Hb / hb, xi0=xi0, xib=s / math.sqrt(Hb / L0), H0_deepwater_equiv=H0eq, Kr_battjes=min(1.0, 0.1 * xi0 ** 2),
                on_slope=bool(xb < bed["x_top"]))


def explore(Ts=(12.0, 14.0, 16.0), H19s=(9.0, 10.0, 10.5, 11.0)):
    B = beds()
    out = []
    for T in Ts:
        for H19 in H19s:
            if H19 >= 0.9 * SF.highest_H(H0, T):
                continue
            t0 = time.time()
            tr = track(T, H19)
            br = {}
            for bk, bd in B.items():
                br[bk] = [breaking(tr, bd, None), breaking(tr, bd, 11.0), breaking(tr, bd, 15.0)]
            out.append(dict(T=T, H19=H19, H19_over_Hmax=H19 / SF.highest_H(H0, T), h_SF=tr["h_SF"], track=tr["rows"], F0=tr["F0"],
                            prof19=tr["prof19"], u1_19=tr["sol19"]["u1_mean_current"], ursell19=tr["sol19"]["ursell"], c19=tr["sol19"]["c"],
                            L19=tr["sol19"]["L"], breaking=br, secs=time.time() - t0))
            b2 = br["S2"]
            print("T %4.1f H19 %5.2f (%.2f Hmax) h_SF %5.2f | S2: " % (T, H19, H19 / SF.highest_H(H0, T), tr["h_SF"] or -1) +
                  " ; ".join("%s h %.2f x %.0f Hb %.2f ec %.2f" % (b["method"], b.get("h_b", -1), b.get("x_b", -1), b.get("H_b", -1), b.get("eta_c_b", -1))
                             for b in b2 if b.get("broke")) +
                  " | S5: " + " ; ".join("%s h %.2f ec %.2f" % (b["method"], b.get("h_b", -1), b.get("eta_c_b", -1)) for b in br["S5"] if b.get("broke")) +
                  "  (%.0fs)" % (time.time() - t0))
            sys.stdout.flush()
    os.makedirs(OUTD, exist_ok=True)
    json.dump(out, open(OUTD + "/shoal_table.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


# ------------------------------------------------------------------ 3 群の案の数（19 m の水深で）
def bed_h_fn(bed):
    bx = np.array([p[0] for p in bed]); bd = np.array([p[1] for p in bed])
    return lambda x: np.interp(x, bx, bd)


def focus_gain(bed, xp, xf, ms, P, dx=0.5):
    """(b) 集まる群：f_n = m_n/P、同じ振幅。線形・ゆっくり変わる海底（位相 ∫k dx、振幅 √(cg0/cg)）で、xf に集めた時の
    xf の頂と、帯の出口 xp の最も高い頂の比（1 に近いほど、集まりで高くならない＝入口で大波を作ることになる）。"""
    hf = bed_h_fn(bed)
    fs = np.array(ms, float) / P
    xs = np.arange(xp, xf + 1e-9, dx); hx = hf(xs)
    K = np.array([[SF.k_lin(1 / f, h) for h in hx] for f in fs])
    CG = np.array([[SF.cg_lin(1 / f, h) for h in hx] for f in fs])
    Phi = np.concatenate([np.zeros((len(fs), 1)), np.cumsum(0.5 * (K[:, 1:] + K[:, :-1]) * dx, axis=1)], axis=1)
    amp = np.sqrt(np.array([SF.cg_lin(1 / f, H0) for f in fs])[:, None] / CG)
    phi = -Phi[:, -1]
    t = np.arange(-P / 2, P / 2, 0.05)
    e_f = (amp[:, -1, None] * np.cos(Phi[:, -1, None] - 2 * np.pi * fs[:, None] * t[None, :] + phi[:, None])).sum(0)
    e_p = (amp[:, 0, None] * np.cos(Phi[:, 0, None] - 2 * np.pi * fs[:, None] * t[None, :] + phi[:, None])).sum(0)
    c = np.array([2 * np.pi * f / SF.k_lin(1 / f, H0) for f in fs])
    return dict(ms=list(ms), P=P, T_range=[1 / fs[-1], 1 / fs[0]], xp=xp, xf=xf, h_f=float(hf(xf)),
                crest_focus_per_a=float(e_f.max()), crest_xp_max_per_a=float(e_p.max()), ratio_xp_over_focus=float(e_p.max() / e_f.max()),
                arrival_spread_s=float((xf - xp) * (1 / c.min() - 1 / c.max())))


def lhs_setdown(a1, a2, T1, T2, h):
    """(c) 二つの周波数の群の束縛の長い波（Longuet-Higgins & Stewart 1962 の狭い帯の近似）：振幅 a1 a2 g (2n − 1/2)/(g h − cg²)。
    n・cg は平均の周波数で。帯が狭くない（Δf/f 0.29）ので目安【計算・近似】。"""
    fm = 0.5 * (1 / T1 + 1 / T2); Tm = 1 / fm
    k = SF.k_lin(Tm, h); c = 2 * math.pi / (k * Tm); cg = SF.cg_lin(Tm, h); n = cg / c
    return dict(T_mean=Tm, n=n, cg=cg, gh_minus_cg2=G * h - cg * cg, eta_L_amp=a1 * a2 * G * (2 * n - 0.5) / (G * h - cg * cg),
                k_diff=abs(SF.k_lin(T2, h) - SF.k_lin(T1, h)), f_diff=abs(1 / T2 - 1 / T1))


def stokes2_ratio(a, T, h):
    k = SF.k_lin(T, h); th = math.tanh(k * h)
    return k * a * (3 - th * th) / (4 * th ** 3)      # 2 次の高調波の振幅 ÷ a


# ------------------------------------------------------------------ 4 水槽と費用
def water_area(bed, x0, x1, dx=0.25):
    hf = bed_h_fn(bed)
    xs = np.arange(x0, x1 + 1e-9, dx)
    return float(np.trapezoid(hf(xs), xs))


def cost(area, frames):
    n0 = PPM2 * area
    lo = frames * n0 * GROWTH[0] / 1e6 * SEC_PER_FRAME_PER_M[0] / 3600
    hi = frames * n0 * GROWTH[1] / 1e6 * SEC_PER_FRAME_PER_M[1] / 3600
    return dict(particles0=n0, particles_range=[n0 * GROWTH[0], n0 * GROWTH[1]], frames=frames, hours=[lo, hi],
                note_ja="1 コマ・百万粒子あたり %.1f〜%.1f s【測った値の幅＋続けて崩れる分を上に見た推定】× 粒子（1 コマ目 × %.1f〜%.1f、reseed の増え）" % (
                    SEC_PER_FRAME_PER_M + GROWTH))


def set_envelope(t, P, up, flat, down):
    tau = np.mod(t, P)
    E = np.zeros_like(tau)
    m1 = tau < up; E[m1] = 0.5 - 0.5 * np.cos(np.pi * tau[m1] / up)
    m2 = (tau >= up) & (tau < up + flat); E[m2] = 1.0
    m3 = (tau >= up + flat) & (tau < up + flat + down); E[m3] = 0.5 + 0.5 * np.cos(np.pi * (tau[m3] - up - flat) / down)
    return E


DESIGN = dict(T=14.0, H19=11.0, N=40)          # 規則波の設計（下の design() の理由の文を見よ）
LAYOUT = dict(x0=144.0, xg_end=432.0, x1=900.0, xa0=dict(S2=790.0, S5=760.0, R4slab=760.0), wall_taper_m=30.0, relax_g=1.0,
              abs_sigma=0.8, abs_pow=2.0)
SETS = dict(P=84.0, up=14.0, flat=28.0, down=14.0)
R4SLAB_BED = [[0.0, 19.0], [570.0, 19.0], [630.0, 13.0], [639.2, 3.8], [1130.0, 3.8]]


def design():
    B = beds()
    os.makedirs(OUTD, exist_ok=True)
    tab = explore()
    T, H19, N = DESIGN["T"], DESIGN["H19"], DESIGN["N"]
    tr = track(T, H19, N=N)
    s19 = SF.solve(H0, T, H19, N=N)
    # 確かめ：表の値で、節の間の水面の条件と、平均の質量の流れ
    r_kin, r_bern = SF._bc_residuals(s19)
    tabl = SF.table(s19)
    tabl.update(bc_residual_kin_rel=r_kin, bc_residual_bern_rel=r_bern, mass_flux_m2s=SF.mass_flux(s19), energy_flux=SF.energy_flux(s19),
                profile=SF.profile_measures(s19), Hmax_fit_19=SF.highest_H(H0, T))
    # 頂の下の流速（水面の直下）と谷の下
    uc, wc = SF.vel(s19, np.array([0.0]), np.array([s19["eta_crest"] - 0.01]))
    ut, wt = SF.vel(s19, np.array([s19["L"] / 2]), np.array([s19["eta_trough"] - 0.01]))
    ub, _ = SF.vel(s19, np.array([0.0]), np.array([-H0 + 0.01]))
    tabl.update(u_crest=float(uc[0]), u_trough=float(ut[0]), u_bed_under_crest=float(ub[0]), crest_particle_speed_over_c=float(uc[0] / s19["c"]))
    brk = {k: [breaking(tr, bd, None), breaking(tr, bd, 11.0), breaking(tr, bd, 15.0)] for k, bd in B.items()}
    slabbed = dict(id="R4_slab", bed=R4SLAB_BED, s=0.1, x_toe=570.0, x_top=630.0, h_top=13.0)
    brk["R4_slab_on_1to10_part"] = [breaking(tr, slabbed, None), breaking(tr, slabbed, 11.0), breaking(tr, slabbed, 15.0)]

    # 群
    grp_b = [focus_gain(B["S2"]["bed"], LAYOUT["xg_end"], 640.0, ms, P) for ms, P in
             (((4, 5, 6, 7, 8, 9), 72.0), ((4, 5, 6, 7, 8, 9, 10, 11), 84.0), (tuple(range(3, 14)), 120.0))]
    a_bi = H19 / 4.0
    grp_c = dict(T1=49.0 / 3, T2=49.0 / 4, P=49.0, a_each_linear=a_bi, setdown=lhs_setdown(a_bi, a_bi, 49.0 / 3, 49.0 / 4, H0),
                 stokes2_over_a_T14=stokes2_ratio(a_bi * 2, 14.0, H0),
                 note_ja="一つの群に大きい波 1 つ（隣は線形で 0.62 倍）、群の周期 49 s。大波の H を規則波と同じ 11 m（線形 4a）にすると a = 2.75 m")
    # 時刻（規則波）
    c = s19["c"]; Lw = s19["L"]
    x_b_mid = {k: 0.5 * (v[1]["x_b"] + v[2]["x_b"]) for k, v in brk.items() if v[1].get("broke")}
    runs = {}
    for rid, bk, kind in (("P1_S2_sf14", "S2", "regular"), ("P2_S5_sf14", "S5", "regular"), ("P3_S2_sets14", "S2", "sets")):
        bd = B[bk]
        x0, xg, x1 = LAYOUT["x0"], LAYOUT["xg_end"], LAYOUT["x1"]
        area = water_area(bd["bed"], x0, x1)
        travel = (x_b_mid[bk] - xg) / c
        if kind == "regular":
            t_first_full = 2 * T + travel            # 始めのなだらかさ 2T の後の波が崩れる所に着く目安
            n_meas = (5, 10)
            t_end = 190.0
            ev_note = "崩れの順に k = 1, 2, …（g47_video の見つけ方）。k 1〜4 は立ち上がり（ならし）として除き、k 5〜10 の 6 回を測る"
        else:
            t_first_full = SETS["up"] + 0.5 * SETS["flat"] + travel
            n_meas = (2, 5)
            t_end = math.ceil(t_first_full + 4 * SETS["P"] + T + 4.0)
            ev_note = "組（セット）ごとに 2 つの満ちた波＋立ち上がり・下りの波。組 1 は静かな水へ入るので除き、組 2〜5 の 4 組で、組の中の高さの順位 1・2 の崩れ（計 8 回）を測る"
        frames = GC.frames_for(t_end)
        runs[rid] = dict(bed_key=bk, bed=bd["bed"], kind=kind, x0=x0, xg_end=xg, x_p=xg, x1=x1, xa0=LAYOUT["xa0"][bk], area_m2=area,
                         t_end_s=t_end, f_end=frames, t_first_full_break_est_s=t_first_full, measure_events=n_meas, events_note_ja=ev_note,
                         cost=cost(area, frames))
    # 予備 R4（ばらつきの広い 2 つの案。走らせるのは 1 つ）
    areaR = water_area(R4SLAB_BED, LAYOUT["x0"], LAYOUT["x1"])
    runs["R4_slab_sf14"] = dict(bed_key="R4slab", bed=R4SLAB_BED, kind="regular", x0=LAYOUT["x0"], xg_end=LAYOUT["xg_end"], x_p=LAYOUT["xg_end"],
                                x1=LAYOUT["x1"], xa0=LAYOUT["xa0"]["R4slab"], area_m2=areaR, t_end_s=190.0, f_end=GC.frames_for(190.0),
                                measure_events=(5, 10), cost=cost(areaR, GC.frames_for(190.0)))
    trT16 = track(16.0, 10.5, N=N)
    brk16 = {k: [breaking(trT16, bd, None), breaking(trT16, bd, 11.0), breaking(trT16, bd, 15.0)] for k, bd in B.items()}
    runs["R4_T16"] = dict(kind="regular", T=16.0, H19=10.5, note_ja="P1・P2 の良い方の海底で、周期 16 s・H19 10.5 m（ξ0 を 0.1〜0.15 上げる）",
                          sol19=SF.table(SF.solve(H0, 16.0, 10.5, N=N)), breaking=brk16,
                          cost=cost(water_area(B["S2"]["bed"], LAYOUT["x0"], LAYOUT["x1"]), GC.frames_for(200.0)), t_end_s=200.0,
                          f_end=GC.frames_for(200.0), x0=LAYOUT["x0"], xg_end=LAYOUT["xg_end"], x1=LAYOUT["x1"])
    # 煙の試し（粒子 0.5 m、4 本に数えない）
    flat_bed = [[0.0, 19.0], [1130.0, 19.0]]
    smoke = dict(
        SM1_flat_sf14_dp0p5=dict(bed=flat_bed, x0=144.0, xg_end=432.0, x1=900.0, xa0=700.0, t_end_s=120.0, f_end=GC.frames_for(120.0), dp=0.5,
                                 cost=dict(particles0=PPM2 / 4 * water_area(flat_bed, 144.0, 900.0), hours_est=[0.1, 0.3]),
                                 purpose_ja="平らな 19 m で、流れ関数の目標の帯が目標の波（H・c・η_c・平均の流れ）を出すか。跳ね返りなし（吸う帯は 19 m の所）"),
        SM2_P1_dp0p5=dict(bed=B["S2"]["bed"], x0=144.0, xg_end=432.0, x1=900.0, xa0=790.0, t_end_s=190.0, f_end=GC.frames_for(190.0), dp=0.5,
                          cost=dict(particles0=PPM2 / 4 * water_area(B["S2"]["bed"], 144.0, 900.0), hours_est=[0.2, 0.5]),
                          purpose_ja="P1 を粗く：崩れる所・回数・19 m の平らで崩れないこと・漏れ。形は読まない"))
    out = dict(
        note_ja="FLIP47 の周期の波の実験の設計（2026-10-13、周期の波の設計の役）。数は Tools/GWWaveGen/flip47/g47_periodic.py が書く。"
                "印：measured（記録から測った）・computed（式で計算）・literature（文献）・inferred（推定・確かめていない）",
        design_wave=dict(T=T, H19=H19, h_gen=H0, N=N, why_ja="周期 14 s は台風 0709 の湘南の有義波 6 m・14 s（石川ら 2008）と平塚の最大の有義波周期 14.2 s（国交省京浜河川事務所の資料の要約）。"
                         "H19 11 m は 19 m で最も高い波の 0.82 倍で、Goda の崩れの予測で崩れの頂 10.4〜11.1 m（原画の 10〜12 m）になる最小に近い値",
                         label="computed+literature", sf_table=tabl, shoal_track=tr["rows"], h_SF=tr["h_SF"], breaking=brk,
                         T16_alternative=dict(track_h_SF=trT16["h_SF"], breaking=brk16)),
        explore_table_file="Unity/Build/FLIP47/periodic/shoal_table.json",
        groups=dict(focused_b=grp_b, bichromatic_c=grp_c, sets=dict(SETS, envelope_ja="τ = t mod P。0〜up で 0→1（余弦）、up〜up+flat で 1、その後 down で 1→0、残りは 0")),
        layout=LAYOUT, runs=runs, smoke=smoke)
    json.dump(out, open(OUTD + "/periodic_numbers.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


# ------------------------------------------------------------------ 5 設計の json（そのまま cfg にできる形）
PRINT_BANDS = dict(
    face_chord_deg_01_05=dict(cn=64.32, band=[60.53, 77.99]), front_x01_rel=dict(cn=0.254, band=[0.182, 0.278]),
    hood_area=dict(cn=0.1855, band=[0.1427, 0.2290]), gap_max=dict(cn=0.541, band=[0.491, None], note_ja="原画は下限"),
    lip_thick_mid=dict(cn=0.350, band=[0.318, 0.389], note_ja="生の値と E1a の偏りで割り戻した値（÷1.534）の両方を書く"),
    back_angle_07_09_deg=dict(cn=31.35, band=[29.20, 38.38]), width07_silhouette=dict(cn=1.324, band=[1.019, 1.416]),
    eta_c_m=dict(cn=None, band=[10.0, 12.0], note_ja="Cartwright & Nakamura 2009 の読み（10〜12 m の巻き波）。静かな水面から"))


def spec():
    Nn = json.load(open(OUTD + "/periodic_numbers.json", encoding="utf8"))
    B = beds()
    dw = Nn["design_wave"]; sft = dw["sf_table"]
    solver = dict(GC.solver_for(GC.VELTRANSFER_RECOMMENDED), donarrowband=0)

    def parms_for(bed, x0, x1, xa0, sets=False, ramp_s=28.0):
        b = GC.box(DP, x0, x1, bed, floor_pad=2)
        p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], Lz=b["Lz"], y_floor=b["y_floor"], Hy=b["Hy"], h0=H0, hmax=b["hmax"],
                 maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0, ox=b["ox"], oy=b["oy"], oz=b["oz"], bed_gap=0.5, floor_pad=2.0,
                 wave_on=0.0, relax_on=1.0, abs_on=1.0, x_p=LAYOUT["xg_end"], xg_end=LAYOUT["xg_end"], relax_g=LAYOUT["relax_g"], dt0=1.0 / 24.0,
                 ramp_s=ramp_s, wall_taper_m=LAYOUT["wall_taper_m"], amp_gain=1.0, rep_P=0.0, xa0=xa0, abs_sigma=LAYOUT["abs_sigma"],
                 abs_pow=LAYOUT["abs_pow"],
                 # 足す物（新しい CTRL の値。既定は sf_on 0・relax_w 0・set_P 0 で前と同じ）
                 sf_on=1.0, relax_w=1.0, set_P=(SETS["P"] if sets else 0.0), set_up=SETS["up"], set_flat=SETS["flat"], set_down=SETS["down"])
        return p, b

    sf_cfg = dict(h=sft["h"], T=sft["T"], H=sft["H"], N=sft["N"], k=sft["k"], c=sft["c"], Ubar=sft["Ubar"], u1_mean_current=sft["u1_mean_current"],
                  B=sft["B"], E=sft["E"], crest_at="x = x_p, t = 0（帯の出口。始めのなだらかさの中）",
                  formula_ja="X = x − x_p − c t、η = Σ_{j=0}^{N} E_j cos(j k X)、Y = min(y, η) + h、"
                             "u = c − Ū + Σ_{j=1}^{N} j k B_j cosh(j k Y)/cosh(j k h) cos(j k X)、w = Σ j k B_j sinh(j k Y)/cosh(j k h) sin(j k X)")
    runs = {}
    order = [("P1_S2_sf14", "S2", False), ("P2_S5_sf14", "S5", False), ("P3_S2_sets14", "S2", True)]
    for rid, bk, sets in order:
        rn = Nn["runs"][rid]
        p, b = parms_for(B[bk]["bed"], rn["x0"], rn["x1"], rn["xa0"], sets=sets, ramp_s=(0.0 if sets else 2 * DESIGN["T"]))
        secx = [520.0, 800.0] if bk == "S2" else [520.0, 760.0]
        runs[rid] = dict(
            run_id=rid + "_dp0p25", out_root="runs", stage="FLIP47", kind="periodic", hip="Houdini/FLIP47/g47_tank_periodic.hiplc", hip_note_ja="新しく作る（§7 の 3）。g47_tank.hiplc は変えない",
            bed=B[bk]["bed"], bed_name_ja=B[bk]["name_ja"], wave="sets（組）" if sets else "regular（規則波）",
            f_start=1, f_first=1, f_end=rn["f_end"], t_end_s=rn["t_end_s"], parms=p, box=b, solver=solver, sf=sf_cfg,
            sets=(dict(SETS, n_full_waves=2, note_ja="組ごとに満ちた波 2、立ち上がり・下りの波が 1 つずつ。84 s のうち 28 s は 0（静か）") if sets else None),
            sec=dict(x0=secx[0], x1=secx[1], t0=20.0, block=120, allz=True), n1_x=[440.0, b["x1"] - 20.0], n1_window=[0.5, 1.5],
            stop_touchdown=None, init_check_frames=[1, 2], pstats_frames=[1, 2, rn["f_end"]], fieldbox_frames=[2], leak_every=24,
            ckpt_on=1, ckpt_every=240, ckpt_list=[480, 240, 120, 48], wall_limit_s=1740, level_guard_m=1.0, disk_stop_free_gb=25.0,
            max_hours=(12.0 if sets else 6.0), wait_hython_max_s=1800,
            measure_events=rn["measure_events"], events_note_ja=rn["events_note_ja"], cost_estimate=rn["cost"],
            breaking_prediction=Nn["design_wave"]["breaking"][bk] if bk in Nn["design_wave"]["breaking"] else None,
            frames_limit_note_ja="途中保存の名前は v.$SF4.sim（4 桁）なので f_end は 9999 以下にする")
    # 予備 R4（一つだけ走らせる。決まりは decision_rules）
    rn = Nn["runs"]["R4_slab_sf14"]
    p, b = parms_for(R4SLAB_BED, rn["x0"], rn["x1"], rn["xa0"])
    runs["R4a_slab_sf14"] = dict(run_id="R4a_slab_sf14_dp0p25", kind="periodic", hip=runs["P1_S2_sf14"]["hip"], bed=R4SLAB_BED,
                                 bed_name_ja="1:10 で 19 m → 13 m（x 630）、1:1 の段で水深 3.8 m の岩棚へ（S5 と同じ棚の深さ）", wave="regular（規則波）",
                                 f_start=1, f_first=1, f_end=rn["f_end"], t_end_s=rn["t_end_s"], parms=p, box=b, solver=solver, sf=sf_cfg,
                                 sec=dict(x0=540.0, x1=760.0, t0=20.0, block=120, allz=True), stop_touchdown=None, n1_x=[440.0, b["x1"] - 20.0],
                                 n1_window=[0.5, 1.5], ckpt_on=1, ckpt_every=240, ckpt_list=[480, 240, 120, 48], wall_limit_s=1740, max_hours=6.0,
                                 measure_events=[5, 10], cost_estimate=rn["cost"], breaking_prediction=Nn["design_wave"]["breaking"]["R4_slab_on_1to10_part"])
    r16 = Nn["runs"]["R4_T16"]
    sol16 = r16["sol19"]
    runs["R4b_T16"] = dict(run_id="R4b_<P1 か P2 の良い方の海底>_sf16_dp0p25", kind="periodic", wave="regular（規則波）T 16 s・H19 10.5 m",
                           note_ja=r16["note_ja"], t_end_s=r16["t_end_s"], f_end=r16["f_end"], parms_note_ja="P1・P2 と同じ。ramp_s 32（2T）",
                           sf=dict(h=sol16["h"], T=sol16["T"], H=sol16["H"], N=sol16["N"], k=sol16["k"], c=sol16["c"], Ubar=sol16["Ubar"],
                                   u1_mean_current=sol16["u1_mean_current"], B=sol16["B"], E=sol16["E"]),
                           cost_estimate=r16["cost"], breaking_prediction=r16["breaking"])
    smoke = {}
    for sid, sm in Nn["smoke"].items():
        p, b = parms_for(sm["bed"], sm["x0"], sm["x1"], sm["xa0"])
        b5 = GC.box(0.5, sm["x0"], sm["x1"], sm["bed"], floor_pad=2)
        p.update(dp=b5["dp"], x0=b5["x0"], Lx=b5["Lx"], Lz=b5["Lz"], y_floor=b5["y_floor"], Hy=b5["Hy"], ox=b5["ox"], oy=b5["oy"], oz=b5["oz"])
        smoke[sid] = dict(run_id=sid, out_root="smoke", kind="periodic_smoke", hip=runs["P1_S2_sf14"]["hip"], bed=sm["bed"], f_start=1, f_first=1,
                          f_end=sm["f_end"], t_end_s=sm["t_end_s"], parms=p, box=b5, solver=solver, sf=sf_cfg,
                          sec=dict(x0=440.0, x1=sm["x1"], t0=20.0, block=120, allz=False), stop_touchdown=None, n1_x=[440.0, b5["x1"] - 20.0],
                          n1_window=[0.5, 1.5], ckpt_on=0, wall_limit_s=1740, max_hours=1.0, purpose_ja=sm["purpose_ja"], cost_estimate=sm["cost"])
    prereg = dict(
        note_ja="走らせる前に凍結する量と帯（2026-10-13）。値は主の層（iz 1、z −0.25 m）、FLIP の受け渡しでは 4 層の平均の場も並べる。"
                "長さは η_c で割る。η_c は静かな水面から（still_offset を引く）。同じ量を局所の平均の水面からも出す（崩れの所の平均の下がりを分けるため）",
        inflow=dict(gauges_x=[450.0, 480.0, 510.0, 540.0, 560.0], waves="測る回と同じ時間の波（崩れの k 5〜10 に入る波）",
                    pass_bands=dict(H_rel=[-0.05, 0.05], eta_c_rel=[-0.05, 0.05], c_rel=[-0.02, 0.02], H_cv_max=0.03),
                    report=["平均の水面（x 440〜560）", "跳ね返り Kr（Goda & Suzuki 1976 の 2 点法、x 480・510）", "帯の出口の H の時間の流れ"],
                    target=dict(H=sft["H"], eta_c=sft["eta_crest"], eta_t=sft["eta_trough"], c=sft["c"], L=sft["L"]),
                    one_fix_rule_ja="SM1 で H が帯の外なら、H_target × (H_target / H_測った) で解き直して 1 回だけやり直す（0.9 H_max 以下）。直しても外なら止めて伺う"),
        per_event=dict(
            detect_ja="崩れ＝前の面に初めて鉛直の接線（格子 1 個分の弦 90° 以上。g47_analyze・g47_video と同じ）。着水＝最初に触れたコマ（閉じた空気の穴か隙間 0.015 h0）。"
                      "崩れの順に k（g47_video.py events と同じ）",
            measures=["eta_c（崩れのコマ・最も近いコマ・着水のコマ）", "H（頂 − 前の谷）", "x_b（崩れのコマの頂の x）", "h_b（x_b の静かな水深）", "t_onset",
                      "face_chord_deg_01_05", "front_x01_rel", "hood_area", "gap_max（唇の下の空気）", "lip_thick_mid（唇の厚み）",
                      "back_angle_07_09_deg", "width07_silhouette", "score3（弦・足・覆い。凍結した式）", "score_back（後ろの角・幅の 2 つ、同じ式）",
                      "AJ/Hb²・AO/Hb²・W/L・θo（着水）", "4 層の AO/Hb² の幅（最大 − 最小）÷ 平均"],
            closest_frame_ja="巻き始め〜着水で score3 が最小のコマ（同じなら覆いの高い方）。着水のコマの値も必ず並べる",
            print_bands=PRINT_BANDS),
        repeatability=dict(events="P1・P2・R4：k 5〜10（6 回）。P3：組 2〜5 の順位 1・2（8 回、順位ごとに 4 回で比べる）",
                           pass_bands=dict(cv_eta_c_max=0.05, cv_h_b_max=0.05, std_x_b_over_Lb_max=0.05, std_onset_phase_over_T_max=0.05,
                                           drift_eta_c_rel_max=0.05, drift_x_b_m_max=5.0),
                           definitions_ja="CV＝標準偏差 ÷ 平均。L_b＝崩れの水深の線形の波長。崩れの位相＝t_onset,k − k T（P3 は組の始まりから）。"
                                          "流れ（drift）＝回の番号への直線の当てはめの傾き × (回数 − 1)。x_b の CV は原点で変わるので、水深 h_b の CV と L_b で割った標準偏差で見る",
                           extend_rule_ja="k 5〜10 で η_c か x_b に流れがある（帯の外）時は、途中保存から +6 T 続け、k 8〜13 でもう一度見る（1 回だけ）"),
        problem1_back=dict(baseline_measured=dict(S2_solitary_back_deg=8.0, S2_solitary_width07=3.05),
                           improved_if_ja="測る回の中央値で、後ろの角 ≥ 20° かつ 0.7 η_c の幅 ≤ 2.0 η_c（S2 の孤立波から原画への道の半分より先）",
                           in_print_band_if_ja="中央値が後ろの角 29〜38°・幅 1.02〜1.42 に入る",
                           expectation_inferred=dict(back_deg=[20.0, 30.0], width07=[1.3, 2.0],
                                                     why_ja="流れ関数の定常の波は、最も高い波の 0.9〜0.98 倍で後ろの角 22〜28°・幅 1.4〜2.0（この役が計算）。崩れの直前はこの近くにいる見込み")),
        problem3_layers=dict(pass_if_ja="4 層の AO/Hb² の（最大 − 最小）÷ 平均 ≤ 0.2（FLIP の受け渡し。層の差を調べる役の推奨）"),
        physics_checks=dict(leak_ja="海底の中・箱の外の粒子 0", level_ja="x 440〜560 の平均の水面の流れ ≤ 0.1 m（測る回の間）",
                            flat_ja="19 m の平らの所（x < 570）で崩れない", particles_ja="粒子の数の増えを記録（一番上の水面の積分の増えと並べる）",
                            setup_ja="棚の上（S2：x 745〜785、S5：x 680〜755）の平均の水面の上がりを記録"),
        frozen_ja="この帯は走らせた後に変えない。変える時は理由と日付を record_ja.md に書き、前の帯の判定も並べる")
    decision_rules = [
        dict(step="SM1（粒子 0.5 m、平らな 19 m）", pass_ja="inflow の帯（H・η_c ±5 %、c ±2 %）", fail_ja="1 回だけ H を直してやり直す。まだ外なら止めて伺う（P1〜P3 を走らせない）"),
        dict(step="SM2（P1 を粒子 0.5 m）", pass_ja="190 s までに斜面の上（x 575〜700）で崩れ 8 回以上、x < 570 で崩れなし、漏れ 0",
             fail_ja="止めて伺う（崩れる所が予測と違う時は、h_b と η_c を測って書く）"),
        dict(step="P1・P2（粒子 0.25 m）", order_ja="P1 → P2。それぞれ終わったら動画と表を出す", note_ja="2 本は互いに待たない（hython は一度に一つ）"),
        dict(step="4 本目の選び（P1・P2 の後）",
             rule_ja="(1) P1・P2 のどちらかで測る回の半分以上が前へ巻いて閉じた空気を作った → P3（組）。"
                     "(2) どちらも巻きが弱い（閉じた空気が半分未満）→ P3 の代わりに R4b（T 16 s、ξ0 を上げる）。"
                     "P3 を走らせた後、P1・P2 の良い方の前の面の弦の中央値が 50° 未満なら、R4a（岩棚の段）を 5 本目として伺う（4 本の外）"),
    ]
    videos = dict(
        dir="Unity/Build/FLIP47/videos/",
        per_run=[
            "全体：g47_video.py run <run_id> --t0=0 --t1=<t_end> --speed=4 --slow=1 --hold=0（上に領域の全部の断面と 10 m の目盛り、帯・吸う帯の印）",
            "測る回の代表：中央値の score3 の回と最も近い回の 2 つ。g47_video.py run <run_id> --k=<k> --around=1 --pre=8 --post=3（スロー 0.25 倍、原画に最も近いコマで止め、原画の輪郭を重ねる）",
            "繰り返し：測る回の全部の最も近いコマを η_c で割って重ねた 1 枚の図と、回ごとに 2 s ずつの短い動画をつないだ物（g47_video.py montage を回で）"],
        labels_ja=["海底（名前と点）", "波（規則波 T 14 s・H19 11 m、流れ関数の解）", "粒子 0.25 m", "時刻と回の番号 k", "帯（入口）と吸う帯の場所"],
        design_preview="Unity/Build/FLIP47/videos/periodic_design_preview.mp4（この役が作った設計の下見。流体の計算ではない）")
    impl = [
        dict(what="g47_sfwave.py（済み）", detail_ja="流れ関数の解・表・場の式。確かめ x47_sfwave_test.py（線形の極み・Stokes 2 次・3 次・質量の流れ 0・項の数）"),
        dict(what="g47_tanklib.py に sfwave() と、relax_zones の流れ関数の枝を足す",
             detail_ja="CTRL の sf_on（既定 0）・relax_w（既定 0）・set_P（既定 0）・set_up・set_flat・set_down と、文字の sf_tab（k c h Ubar N B… E…）。"
                       "OUT_SF（detail の 64 ビットの配列）を inlet_table と同じ作りで。目標の流速は水面の上では目標の水面の値（Y = min(y, η) + h。伸ばしなし）。"
                       "E = walltaper(x) × rampT(t, ramp_s) × Eset(t)。relax_w 1 なら vel.y も同じ重みで寄せる。sf_on 0 なら今の式のまま（ビットまで同じ）",
             accept_ja="x47_sfrelax_test.py：SOP の wrangle で sfwave() を 5 点（帯の中の深い所・水面の近く・水面の上）× 5 時刻で呼び、numpy（g47_sfwave.vel）と u・w・η の差 ≤ 1e-6 c・1e-6 H"),
        dict(what="g47_build_tank.py に出力先の引数を足し、Houdini/FLIP47/g47_tank_periodic.hiplc を作る", detail_ja="g47_tank.hiplc は変えない（ほかの役が使う）"),
        dict(what="g47_run.py に cfg の hip（既定 GC.HIP）と sf（あれば sf_tab に入れる）を足す", detail_ja="既定は前と同じ"),
        dict(what="g47_periodic.py に cfg の書き出し（ready の json）", detail_ja="この json の runs・smoke をそのまま runs/ready/ と smoke/ready/ へ"),
        dict(what="g47_periodic_ana.py（新しく）", detail_ja="入口の 5 点の波（H・η_c・c・平均の水面・2 点法の Kr）、崩れの回（g47_video の見つけ方）、回ごとの量（g47_analyze の物差し）、"
                                                      "繰り返しの表、帯との判定、図（回の重ね、x_b・η_c の回ごとの点）"),
        dict(what="動画", detail_ja="g47_video.py（動画の役、済み）をそのまま使う。周期の長い計算は --t0 --t1 --speed で")]
    physics_basis = [
        dict(item="台風 0709 号の湘南の有義波 6 m・周期 14 s", label="literature", src="石川・宇多・青島・吉岡・三波 2008、海洋開発論文集 24, 441–446（J-STAGE の要旨）"),
        dict(item="平塚の最大の有義波周期 14.2 s（14 s 以上の出現 約 0.1 %）、波浮の最大の有義波高 8.31 m（10.4 s）（台風 0709 号）", label="literature",
             src="国交省京浜河川事務所の西湘海岸の資料（検索の要約。元の PDF は 404 で読めていない）"),
        dict(item="平塚の観測塔の波高のピーク 6.1 m（台風 0709 号）、大磯の沖 8.8 m（2019 台風 19 号、推定）", label="literature", src="国交省関東地方整備局の資料（検索の要約）"),
        dict(item="平塚の観測塔の最後の有義波高 7.25 m（2017 台風 21 号 Lan、塔が壊れる前）", label="literature", src="Sasmal, Waseda & Webb, EGU2018-2052（検索の要約）"),
        dict(item="最大の 1 波 ≈ 有義波高 × 1.5（100 波）〜1.8（3 時間）→ 10〜13 m", label="computed", src="Rayleigh 分布"),
        dict(item="19 m・14 s の最も高い波 13.33 m、設計の H 11 m はその 0.825 倍", label="computed", src="Fenton 1990 の当てはめ"),
        dict(item="kh 0.62 < 1.363 で変調の不安定なし（規則波の列が自分で群にならない）", label="literature+computed", src="Benjamin & Feir 1967"),
        dict(item="東京湾の中の嵐の海は 4〜7.6 s、外海の波のエネルギーは湾に 5 % 未満：14 s のうねりは相模湾・湾の入口の波（場所の仮定、要確認）",
             label="literature（リポジトリの調べ）", src="Docs/Research/WindWaves_Kanagawa_ja.md（Takagi & Takahashi）"),
        dict(item="巻き波の範囲 0.5 < ξ0 < 3.3、跳ね返り Kr ≈ 0.1 ξ0²", label="literature", src="Battjes 1974"),
        dict(item="規則波の崩れの指数 H_b/L0 = 0.17[1 − exp(−1.5π h_b/L0 (1 + 11 tan^{4/3}β))]、散らばり 6〜14 %（1:10 まで）", label="literature",
             src="Goda 2010, Coastal Eng. J. 52(1)（要旨・Coastal Wiki）"),
        dict(item="礁の上の水深が波高に比べて浅いほど崩れが強く、噴流の下の空気が大きい（1:10 の潜った礁）", label="literature", src="Blenkinsopp & Chaplin 2008（要旨）")]
    findings = [
        dict(ja="原画の大きさの周期の波は斜面の途中（水深 9.6〜12.4 m、S2 x 636〜646・S5 x 628〜636）で崩れ、浅い平らに届かない", label="inferred"),
        dict(ja="定常の波の限りの手前（17.75 m、0.95 倍）の頂は後ろの角 25°・幅 1.55 η_c（原画 31°・1.32、孤立波 12°・3.87）", label="computed"),
        dict(ja="19 m・208 m では集まる群の帯の出口の頂が焦点の 0.75〜0.88 倍（集まりで高くならない）", label="computed"),
        dict(ja="二つの周波数の群で大波 11 m：束縛の長い波 1.5 m、2 次の高調波 0.65 a（線形の入口は目標にならない）", label="computed")]
    out = dict(
        title_ja="FLIP47 周期の波の実験の設計（S2・S5 の海底、規則波と組）", date="2026-10-13", author="周期の波の設計の役（Claude）",
        findings=findings, physics_basis=physics_basis,
        doc="Unity/Build/FLIP47/periodic_design_ja.md", numbers="Unity/Build/FLIP47/periodic/periodic_numbers.json",
        labels=dict(measured="記録から測った", computed="式で計算した", literature="文献", inferred="推定（確かめていない）"),
        design_wave=dict(T=DESIGN["T"], H19=DESIGN["H19"], h_gen=H0, sf=sf_cfg, profile_19m=sft["profile"], u_crest=sft["u_crest"],
                         u_bed_under_crest=sft["u_bed_under_crest"], ursell=sft["ursell"], Hmax_fit_19=sft["Hmax_fit_19"],
                         check=dict(bc_residual_kin_rel=sft["bc_residual_kin_rel"], bc_residual_bern_rel=sft["bc_residual_bern_rel"],
                                    mass_flux_m2s=sft["mass_flux_m2s"]), label="computed"),
        predictions=dict(label="inferred", breaking=dw["breaking"], h_SF=dw["h_SF"], T16=dw["T16_alternative"],
                         shoal_track_design=dw["shoal_track"]),
        groups_evaluated=dict(label="computed", focused_b=Nn["groups"]["focused_b"], bichromatic_c=Nn["groups"]["bichromatic_c"],
                              sets=Nn["groups"]["sets"]),
        runs=runs, smoke=smoke, prereg=prereg, decision_rules=decision_rules, videos=videos, implementation=impl,
        total_cost_hours=dict(first_round_P1_P2_P3=[sum(runs[r]["cost_estimate"]["hours"][0] for r in ("P1_S2_sf14", "P2_S5_sf14", "P3_S2_sets14")),
                                                    sum(runs[r]["cost_estimate"]["hours"][1] for r in ("P1_S2_sf14", "P2_S5_sf14", "P3_S2_sets14"))],
                              label="inferred"))
    json.dump(out, open(B47 + "/periodic_design.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "explore"
    if what == "explore":
        explore()
    elif what == "spec":
        o = spec()
        print("written", B47 + "/periodic_design.json", "cost", o["total_cost_hours"])
        for k, v in o["runs"].items():
            print(k, v.get("run_id"), v.get("f_end"), (v.get("box") or {}).get("cells"), (v.get("cost_estimate") or {}).get("hours"))
    elif what == "design":
        o = design()
        for k, v in o["runs"].items():
            print(k, {q: v.get(q) for q in ("area_m2", "t_end_s", "f_end", "t_first_full_break_est_s")}, v.get("cost", {}).get("hours"))
        print("groups b", [(g["ms"], round(g["ratio_xp_over_focus"], 2), round(g["arrival_spread_s"], 1)) for g in o["groups"]["focused_b"]])
        print("groups c", o["groups"]["bichromatic_c"])
        d = o["design_wave"]
        print("design", {k: d["sf_table"][k] for k in ("c", "L", "u1_mean_current", "eta_crest", "eta_trough", "ursell", "u_crest", "u_bed_under_crest",
                                                         "bc_residual_kin_rel", "bc_residual_bern_rel", "mass_flux_m2s")})
        for k, v in d["breaking"].items():
            print(k, [(b["method"], round(b.get("h_b", -1), 2), round(b.get("x_b", -1), 1), round(b.get("H_b", -1), 2), round(b.get("eta_c_b", -1), 2),
                       round(b.get("xi0", -1), 2)) for b in v if b.get("broke")])
