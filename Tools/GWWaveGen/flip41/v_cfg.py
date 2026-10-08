# -*- coding: utf-8 -*-
"""FLIP41 確かめ：計算 1 本の設定（JSON）を作る。py -3.10 v_cfg.py <kind> key=value ... → 標準出力に JSON。
kind：
  B1  一定の水深の規則波（T, h, HL か a, dp, wm=relax|piston, 変える所 band_vox, minsub, vt, nb）
  B2  ゆるい斜面の浅水変形（T, h0, h1, n, a, dp, wm）
  T1  風の圧力の単位の確かめ（静かな水に p0u + p0c cos(kx)）
  T2  風の圧力で波が育つか（B1 と同じ水槽に、斜面と同じ位相の圧力 P0 と接線の応力 tau）
水槽の寸法（B1）：造波の帯 1 波長、測る区間 3 波長（帯の出口から 0.5〜3.5 波長）、吸う帯 1.5 波長。
時間：始めのなだらかさ 3 周期。測る窓は、波の先頭（群速度）が測る区間の端を過ぎて 2 周期の後から 5 周期。
"""
import sys, json, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
from v_lin import props, biesel_HS, bed_profile, k_of_omega

FPS = 24


def rup(v, q):
    return float(math.ceil(v / q - 1e-9) * q)


def rnd(v, q):
    return float(round(v / q) * q)


def common(dp, a, h0, extra_air=0.0):
    vox = 2.0 * dp
    Lz = 4 * vox
    air = max(3.0 * a + 2 * vox, 4 * vox, extra_air)
    box = rup(h0 + 2 + air, vox)
    ytop = box - h0 - 2
    return vox, Lz, ytop


def b1(T, h, dp, HL=0.01, a=None, wm="relax", band_vox=4, minsub=1, maxsub=2, vt="apic", nb=1, name=None,
       n_meas=3.0, n_abs=1.5, nwin=5, P0=0.0, tau=0.0, wind=False, tag=""):
    p = props(T, h)
    L, k, om, cg = p["L"], p["k"], p["om"], p["cg"]
    if a is None:
        a = HL * L / 2
    vox, Lz, ytop = common(dp, a, h)
    xg = max(rnd(L, vox), 10 * vox)
    xm0 = xg + 0.5 * L
    xm1 = xg + (0.5 + n_meas) * L
    xa0 = rnd(xg + (1.0 + n_meas) * L, vox)
    Lx = rup(xa0 + n_abs * L, vox)
    ramp = 3 * T
    t_w0 = 0.5 * ramp + xm1 / cg + 2 * T
    t_w0 = math.ceil(t_w0 / T) * T
    t_w1 = t_w0 + nwin * T
    f_end = int(math.ceil(t_w1 * FPS)) + 2
    parms = dict(dp=dp, gridscale=2.0, Lz=Lz, Lx=Lx, h0=h, slope_n=0.0, xs0=1e6, h1=h, ytop=ytop, x_left=0.0,
                 band_vox=float(band_vox), maxsub=float(maxsub), minsub=float(minsub),
                 wm_mode=1.0, wa=a, wom=om, wk=k, ramp_s=ramp, xg_end=xg, relax_g=1.0, wall_taper_m=rnd(0.25 * xg, vox),
                 xp0=0.0, pS2=0.0, xa0=xa0, abs_sigma=0.8, abs_pow=2.0,
                 p_mode=0.0, p0u=0.0, p0c=0.0, pk=0.0, P0=0.0, tau=0.0, rho_w=1000.0, p_ramp=ramp, pw_x0=0.0, pw_x1=1e6, pw_tap=0.5 * L)
    if nb == 0:
        # 帯を使わない時は、初めの粒子を水の全体に置く（帯の厚さの値を水深より大きくする。2026-10-08 22:40 の
        # B1_T7_h25_dp1_relax_nb0 は帯の中だけに粒子を置いたので、帯より下の水が落ちて見張りで止まった）
        parms["band_vox"] = 1000.0
    if wm == "piston":
        xp0 = max(3 * vox, 2.0)
        HS = biesel_HS(p["kh"])
        parms.update(wm_mode=2.0, relax_g=0.0, x_left=xp0, xp0=xp0, pS2=a / HS)
    if wind:
        parms.update(p_mode=2.0 if P0 > 0 else 0.0, P0=P0, tau=tau, pw_x0=xg, pw_x1=xa0, pw_tap=0.5 * L)
    case = dict(kind="B1", T=T, h=h, a=a, H=2 * a, HL=2 * a / L, dp=dp, vox=vox, wm=wm, L=L, k=k, om=om, c=p["c"], cg=cg, kh=p["kh"],
                xg=xg, x_meas=[xm0, xm1], xa0=xa0, t_win=[t_w0, t_w1], band_vox=band_vox, minsub=minsub, vt=vt, nb=nb,
                a_over_vox=a / vox, L_over_vox=L / vox, h_over_vox=h / vox, P0=P0, tau=tau)
    if name is None:
        name = "B1_T%g_h%g_dp%g_%s%s" % (T, h, dp, wm, tag)
    return dict(run_id=name, parms=parms, solver=dict(veltransfer=vt, donarrowband=nb), case=case,
                f_start=1, f_end=f_end, ckpt_on=1, ckpt_every=240, wall_limit_s=1740, level_guard_m=1.0,
                note="FLIP41 確かめ %s：一定の水深 %g m、周期 %g s、高さ %.3f m（H/L %.4f）、粒子 %g m、%s" % (
                    name, h, T, 2 * a, 2 * a / L, dp, "緩和の帯" if wm == "relax" else "ピストン板"))


def b2(T, h0, h1, n, dp, a, wm="relax", name=None, nwin=5, tag="", nb=1):
    p0 = props(T, h0); p1 = props(T, h1)
    L0, L1 = p0["L"], p1["L"]
    vox, Lz, ytop = common(dp, a * 1.3, h0)
    xg = max(rnd(L0, vox), 10 * vox)
    xs0 = rnd(xg + 2.5 * L0, vox)
    xs1 = xs0 + (h0 - h1) * n
    xa0 = rnd(xs1 + 2.0 * L1, vox)
    Lx = rup(xa0 + 2.0 * L1, vox)
    ramp = 3 * T
    xx = np.linspace(0, xa0, 4001)
    hh = bed_profile(xx, h0, xs0, n, h1)
    cgs = np.array([props(T, v)["cg"] for v in hh])
    t_arr = float(np.trapezoid(1 / cgs, xx))
    t_w0 = math.ceil((0.5 * ramp + t_arr + 2 * T) / T) * T
    t_w1 = t_w0 + nwin * T
    f_end = int(math.ceil(t_w1 * FPS)) + 2
    parms = dict(dp=dp, gridscale=2.0, Lz=Lz, Lx=Lx, h0=h0, slope_n=float(n), xs0=xs0, h1=h1, ytop=ytop, x_left=0.0,
                 band_vox=4.0, maxsub=2.0, minsub=1.0,
                 wm_mode=1.0, wa=a, wom=p0["om"], wk=p0["k"], ramp_s=ramp, xg_end=xg, relax_g=1.0, wall_taper_m=rnd(0.25 * xg, vox),
                 xp0=0.0, pS2=0.0, xa0=xa0, abs_sigma=0.8, abs_pow=2.0,
                 p_mode=0.0, p0u=0.0, p0c=0.0, pk=0.0, P0=0.0, tau=0.0, rho_w=1000.0, p_ramp=ramp, pw_x0=0.0, pw_x1=1e6, pw_tap=10.0)
    if wm == "piston":
        xp0 = max(3 * vox, 2.0)
        parms.update(wm_mode=2.0, relax_g=0.0, x_left=xp0, xp0=xp0, pS2=a / biesel_HS(p0["kh"]))
    if int(nb) == 0:
        parms["band_vox"] = 1000.0
    case = dict(kind="B2", T=T, h0=h0, h1=h1, n=n, a=a, dp=dp, vox=vox, wm=wm, L0=L0, L1=L1, om=p0["om"], k0=p0["k"], nb=int(nb),
                xg=xg, xs0=xs0, xs1=xs1, xa0=xa0, x_off=[xg + 0.5 * L0, xs0 - 0.25 * L0], t_win=[t_w0, t_w1])
    if name is None:
        name = "B2_T%g_h%g-%g_n%g_dp%g_%s%s" % (T, h0, h1, n, dp, wm, tag)
    return dict(run_id=name, parms=parms, solver=dict(veltransfer="apic", donarrowband=int(nb)), case=case,
                f_start=1, f_end=f_end, ckpt_on=1, ckpt_every=240, wall_limit_s=1740, level_guard_m=1.0,
                note="FLIP41 確かめ %s：水深 %g → %g m（1:%g）、周期 %g s、沖の振幅 %.3f m、粒子 %g m" % (name, h0, h1, n, T, a, dp))


def t1(dp, h=25.0, lam=40.0, p0u=2000.0, p0c=5000.0, t_end=60.0, ramp=30.0, name=None, nb=1):
    vox, Lz, ytop = common(dp, 1.0, h)
    Lx = rup(4 * lam, vox)
    kk = 2 * math.pi / lam
    parms = dict(dp=dp, gridscale=2.0, Lz=Lz, Lx=Lx, h0=h, slope_n=0.0, xs0=1e6, h1=h, ytop=ytop, x_left=0.0,
                 band_vox=4.0, maxsub=2.0, minsub=1.0, wm_mode=0.0, wa=0.0, wom=1.0, wk=kk, ramp_s=1.0, xg_end=0.0, relax_g=0.0,
                 wall_taper_m=0.0, xp0=0.0, pS2=0.0, xa0=1e6, abs_sigma=0.0, abs_pow=2.0,
                 p_mode=1.0, p0u=p0u, p0c=p0c, pk=kk, P0=0.0, tau=0.0, rho_w=1000.0, p_ramp=ramp, pw_x0=0.0, pw_x1=1e6, pw_tap=1.0)
    if int(nb) == 0:
        parms["band_vox"] = 1000.0
    case = dict(kind="T1", dp=dp, h=h, lam=lam, k=kk, p0u=p0u, p0c=p0c, ramp=ramp, t_win=[t_end - 15.0, t_end], nb=int(nb),
                eta_expect=-p0c / (1000.0 * 9.80665), T_nat=2 * math.pi / math.sqrt(9.80665 * kk * math.tanh(kk * h)))
    if name is None:
        name = "T1_dp%g" % dp
    return dict(run_id=name, parms=parms, solver=dict(veltransfer="apic", donarrowband=int(nb)), case=case,
                f_start=1, f_end=int(t_end * FPS) + 1, ckpt_on=0, ckpt_every=240, wall_limit_s=1740, level_guard_m=1.0, diag=1,
                note="FLIP41 確かめ %s：静かな水に水面の圧力 %g + %g cos(kx) Pa（波長 %g m）" % (name, p0u, p0c, lam))


if __name__ == "__main__":
    kind = sys.argv[1]
    kw = {}
    for s in sys.argv[2:]:
        k, v = s.split("=")
        try:
            kw[k] = float(v)
        except ValueError:
            kw[k] = v
    for k in ("band_vox", "minsub", "maxsub", "nb", "nwin"):
        if k in kw:
            kw[k] = int(kw[k])
    if "wind" in kw:
        kw["wind"] = bool(int(kw["wind"]))
    f = dict(B1=b1, B2=b2, T1=t1)[kind]
    print(json.dumps(f(**kw), ensure_ascii=True))
