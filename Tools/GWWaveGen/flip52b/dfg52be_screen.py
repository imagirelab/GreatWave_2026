# -*- coding: utf-8 -*-
"""FLIP52B AM-DFGB1 (user Q84, 2026-10-18 ~00:00: 「DFG-2B 按总能量和 DM1A 相同来跑，报告里写明。」): the energy-matched DFG-2B sea, screened
BEFORE any run (py -3.10 -B; numpy, scipy). 2026-10-18 written new (Claude). Nothing of the frozen screen is edited: this file imports
flip52b/dfg52b_screen.py READ ONLY and only passes a_sum (dfgb_sea(..., a_sum=...)); the frozen calibration screens/calib_52b.json is read, not
recomputed. Writes only Unity/Build/FLIP52B/screens/dfg52be_*.json.

What it computes
  energy    DM1A's input (its ready cfg: 30 equal components a_j, T 12 s, uniform +-80 deg, h0 19 m) against the DFG-2B components (g52b_common
            with the frozen a_sum): energy density E = 0.5 rho g sum a^2 (rho 1000, g 9.80665) and energy flux F = sum 0.5 rho g a^2 c_g(h0)
            (and its x part F_x = sum ... cos theta) at the generation depth h0 19 m; the scale s = sqrt(E_DM1A / E_DFGB) (CHOSEN basis, see
            AM-DFGB1) and the flux-matched scale for the report.
  screen    the frozen DFG-2B screen (run_candidate: WKB DirField + local Sharma-Dean 2nd order, FLIP calibration R_T7 / dX / dT / gamma of
            calib_52b.json, print expectation) with a_sum = s x 6.331240 m at the frozen focus x_f 272.25 m (t_f1 recomputed by the frozen rule).
  bands     G4 screen: kp x the largest crest over one period, linear AND linear + local 2nd order, in the inlet band (x <= 100 m, all y) and
            the generating side band (y >= 95 m, x <= 180.25 m) = the g52b_ana G4 regions, for the frozen and the energy-matched a_sum; the
            same screen on the plan E X2 sea against X2's measured G4 (validation of the 2nd-order screen in this tank and band code).
  levers    layout levers for G4 (direction set and frequencies kept): the design focus x_f (side-band linear maximum and aperture) and a
            shorter generating side band sd_gen (aperture and the G4-region 2nd-order maximum).
  DM1A c_in the largest incoming DM1A crest on the line x 110 m (|y| <= 95 m, linear, one period) for the 'no single incoming wave enlarged' text.
usage: py -3.10 -B dfg52be_screen.py run
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                    # noqa: E402
import dfg52b_screen as S             # noqa: E402  frozen screen, read only
import g50_dirfield as DF             # noqa: E402  read only
import g52_common as G52              # noqa: E402  read only

REPO = S.REPO
OUT = S.OUT
DM1A_CFG = REPO + "/Unity/Build/FLIP50/runs/ready/DM1A_D19B_T12_th80_dp0p5.json"
X2_JUDGE = REPO + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/e51/judge_E05.json"
RHO = 1000.0
H0 = 19.0
X_F = 272.25
P = 28.0
G4_REG = dict(inlet=(0.0, 100.0, 0.0, 140.0), side=(0.0, 180.25, 95.0, 140.0))


def energy():
    c = json.load(open(DM1A_CFG, encoding="utf8"))
    d = c["dir"]
    th_d, wd_d = DF.components(float(d["theta_max_deg"]), int(d["n"]), d["weight"])
    a_d = float(d["a_sum"]) * wd_d
    om_d = 2 * math.pi / float(d["T"])
    cg_d = float(DF.cg(om_d, H0))
    om, wf = G52.freqset(G52.P_S, G52.HARMONICS, "eq")
    th, wd = G52.dirset(("hyb", 60.0, 28.0, 85.0, 17))
    a = G52.A_SUM * np.outer(wf, wd)
    cg = np.array([float(DF.cg(w, H0)) for w in om])
    k = np.array([float(DF.kdisp(w, H0)) for w in om])
    rg = 0.5 * RHO * DF.G
    E_d = rg * float(np.sum(a_d ** 2)); F_d = rg * float(np.sum(a_d ** 2)) * cg_d
    Fx_d = rg * float(np.sum(a_d ** 2 * np.cos(np.radians(th_d)))) * cg_d
    E_b = rg * float(np.sum(a ** 2)); F_b = rg * float(np.sum(a ** 2, 1) @ cg)
    Fx_b = rg * float(np.sum((a ** 2 * np.cos(np.radians(th))[None, :]).sum(1) * cg))
    sE = math.sqrt(E_d / E_b); sF = math.sqrt(F_d / F_b); sFx = math.sqrt(Fx_d / Fx_b)
    return dict(
        DM1A=dict(source=DM1A_CFG.replace(REPO + "/", ""), n=int(d["n"]), a_j_m=float(a_d[0]), a_sum_m=float(np.sum(a_d)), T_s=float(d["T"]),
                  theta_max_deg=float(d["theta_max_deg"]), sum_a2_m2=float(np.sum(a_d ** 2)), Hm0_m=4 * math.sqrt(float(np.sum(a_d ** 2)) / 2),
                  k_h0=float(DF.kdisp(om_d, H0)), cg_h0_mps=cg_d, E_Jm2=E_d, F_Wm=F_d, Fx_Wm=Fx_d),
        DFGB_frozen=dict(a_sum_m=float(G52.A_SUM), sum_a2_m2=float(np.sum(a ** 2)), a_max_m=float(a.max()), Hm0_m=4 * math.sqrt(float(np.sum(a ** 2)) / 2),
                         T_s=[2 * math.pi / w for w in om], k_h0=k.tolist(), cg_h0_mps=cg.tolist(), E_Jm2=E_b, F_Wm=F_b, Fx_Wm=Fx_b,
                         E_over_DM1A=E_b / E_d, F_over_DM1A=F_b / F_d, Fx_over_DM1A=Fx_b / Fx_d),
        scale_energy_density=sE, scale_energy_flux=sF, scale_energy_flux_x=sFx,
        a_sum_energy_density_m=float(G52.A_SUM) * sE, a_sum_energy_flux_m=float(G52.A_SUM) * sF, a_sum_energy_flux_x_m=float(G52.A_SUM) * sFx,
        chosen=dict(basis="energy density (= variance, = Hm0) at the generation depth h0 19 m", scale=sE, a_sum_m=float(G52.A_SUM) * sE,
                    a_max_component_m=float(a.max()) * sE, amp_per_freq_m=[float(G52.A_SUM) * sE * float(v) for v in wf],
                    E_Jm2=E_b * sE ** 2, E_over_DM1A=E_b * sE ** 2 / E_d, F_Wm=F_b * sE ** 2, F_over_DM1A=F_b * sE ** 2 / F_d,
                    Fx_Wm=Fx_b * sE ** 2, Fx_over_DM1A=Fx_b * sE ** 2 / Fx_d, Hm0_m=4 * math.sqrt(float(np.sum(a ** 2)) * sE ** 2 / 2)),
        flux_matched_would_give=dict(scale=sF, a_sum_m=float(G52.A_SUM) * sF, E_over_DM1A=E_b * sF ** 2 / E_d, a_max_component_m=float(a.max()) * sF),
        rule="E = 0.5 rho g sum a^2, F = sum 0.5 rho g a^2 c_g(h0), F_x = sum 0.5 rho g a^2 c_g(h0) cos theta, rho 1000 kg/m3, g 9.80665, h0 19 m; "
             "the ratios do not depend on rho [computed]")


def band_max(sea, reg, second=True, dt=0.25, dy=1.0, kp=None):
    xlo, xhi, ylo, yhi = reg
    XG = S.XG
    cols = np.where((XG >= xlo - 1e-9) & (XG <= xhi + 1e-9))[0]
    y = np.arange(ylo, yhi + 1e-9, dy)
    Y1 = np.exp(1j * np.outer(y, sea.ky)); C1 = sea.C[:, cols]
    if second:
        sea.prep2(cols)
        Pq = sea._nl2
        Y2 = np.exp(1j * np.outer(y, Pq["KY"]))
    b1 = np.full((len(y), len(cols)), -9.0); b2 = b1.copy(); t1 = np.zeros_like(b1); t2 = np.zeros_like(b1)
    per = max(sea.T) * 3.0 if len(sea.T) > 1 else sea.T[0]
    for t in sea.t_f + np.arange(-per / 2.0, per / 2.0 - 1e-9, dt):
        e1 = ((Y1 * np.exp(-1j * sea.om * (t - sea.t_f))[None, :]) @ C1).real
        m = e1 > b1; b1[m] = e1[m]; t1[m] = t
        if second:
            e2 = e1 + ((Y2 * np.exp(-1j * Pq["OM"] * (t - sea.t_f))[None, :]) @ Pq["S"]).real
            m = e2 > b2; b2[m] = e2[m]; t2[m] = t
    xs = XG[cols]
    kk = (np.full(len(xs), kp) if kp is not None else DF.kdisp(2 * math.pi / 7.0, np.maximum(DF.bed_h(xs, S.BED), 0.5)))[None, :]

    def at(b, tb):
        v = kk * b
        i = int(np.argmax(v)); jy, ix = np.unravel_index(i, v.shape)
        prof = {("x%g" % xs[j]): round(float(v[:, j].max()), 4) for j in range(0, len(xs), 10)}
        return dict(kA=float(v.max()), crest_m=float(b[jy, ix]), x=float(xs[ix]), y=float(y[jy]), t_rel_tf=float(tb[jy, ix] - sea.t_f), profile_x=prof)
    out = dict(lin=at(b1, t1), k_rule=("kp = k(T 7 s, h0 19 m) (= g52b_ana G4)" if kp is not None else "local k(T 7 s, h(x)) (= X2 judge G4)"))
    if second:
        out["nl2"] = at(b2, t2)
    return out


def dm1a_c_in():
    sea = S.dm_sea(12.0, "DM1A")
    c = int(np.argmin(np.abs(S.XG - 110.0)))
    y = 0.5 + np.arange(0, 95)
    cin = 0.0
    for t in sea.t_f + np.arange(-6.0, 6.0 - 1e-9, 0.125):
        cin = max(cin, float(sea.eta1(np.array([c]), y, t).max()))
    return dict(c_in110_lin_m=cin, a_component_m=float(sea.a.max()), rule="largest linear DM1A crest on the line x 110 m, |y| <= 94.5 m, one period "
                "(dfg52b_screen.dm_sea: the DM1A components, x_f 220.25 m) [computed]")


def levers(a_sum, kp):
    out = dict(x_f_scan=[], sd_gen_scan=[])
    for xf in (252.25, 262.25, 272.25, 282.25, 292.25):
        s = S.dfgb_sea(xf, 63.0, a_sum=a_sum)
        r = band_max(s, G4_REG["side"], second=False, dt=0.5, dy=2.0, kp=kp)
        ap = S.dfgb_sea(xf, 0.0, a_sum=a_sum).arrival()["aperture"]
        out["x_f_scan"].append(dict(x_f=xf, side_lin_kA=r["lin"]["kA"], at=[r["lin"]["x"], r["lin"]["y"]], aperture=ap))
    lay0 = dict(S.LAY)
    sea = S.dfgb_sea(X_F, 63.0, a_sum=a_sum)
    try:
        for g, sw in ((180.25, 210.25), (160.25, 190.25), (150.25, 180.25), (145.25, 175.25), (140.25, 170.25)):
            S.LAY["sd_gen"] = g; S.LAY["sd_sw"] = sw
            ap = S.dfgb_sea(X_F, 0.0, a_sum=a_sum).arrival()["aperture"]
            r = band_max(sea, (0.0, g, 95.0, 140.0), second=True, dt=0.5, dy=2.0, kp=kp)
            out["sd_gen_scan"].append(dict(sd_gen=g, sd_sw=sw, aperture=ap, a_sum_x_aperture_m=a_sum * ap, G4_side_lin=r["lin"]["kA"], G4_side_nl2=r["nl2"]["kA"]))
    finally:
        S.LAY.clear(); S.LAY.update(lay0)
    out["note"] = ("x_f: the generating-side-band maximum stays at the slope toe (x ~160 m, y ~116 m) for every x_f; sd_gen: a shorter generating "
                   "band drops the large-angle components that make both that maximum and part of the focus [computed]")
    return out


def run():
    t0 = time.time()
    cal = json.load(open(OUT + "/calib_52b.json", encoding="utf8"))
    en = energy()
    aE = en["chosen"]["a_sum_m"]
    kp = float(DF.kdisp(2 * math.pi / 7.0, H0))
    # ---- the frozen screen with the energy-matched a_sum (every call of dfgb_sea in run_candidate gets a_sum = aE)
    orig = S.dfgb_sea
    S.dfgb_sea = lambda x_f, t_f, a_sum=None: orig(x_f, t_f, a_sum=aE if a_sum is None else a_sum)
    try:
        cand = S.run_candidate(X_F, cal, label="DFG-2B energy-matched (AM-DFGB1) x_f %.2f" % X_F)
    finally:
        S.dfgb_sea = orig
    sh = S.short(cand)
    # ---- G4 bands: frozen and energy-matched a_sum (g52b_ana regions, kp), X2 validation (local k, X2 judge regions)
    bands = {}
    for nm, a in (("frozen", float(G52.A_SUM)), ("E", aE)):
        s = S.dfgb_sea(X_F, cand["t_f1"], a_sum=a)
        bands[nm] = {k: band_max(s, v, kp=kp) for k, v in G4_REG.items()}
    x2 = S.x2_sea()
    x2s = {k: band_max(x2, v, kp=None, dt=0.125) for k, v in G4_REG.items()}
    xj = json.load(open(X2_JUDGE, encoding="utf8"))["gates"]["G4_no_band_breaking"]
    x2v = dict(screen=x2s, measured=dict(inlet=xj["kA_inlet_max"], side=xj["kA_side_max"]),
               measured_over_nl2=dict(inlet=xj["kA_inlet_max"] / x2s["inlet"]["nl2"]["kA"], side=xj["kA_side_max"] / x2s["side"]["nl2"]["kA"]),
               measured_over_lin=dict(inlet=xj["kA_inlet_max"] / x2s["inlet"]["lin"]["kA"], side=xj["kA_side_max"] / x2s["side"]["lin"]["kA"]))
    pred = dict(inlet=bands["E"]["inlet"]["nl2"]["kA"] * x2v["measured_over_nl2"]["inlet"], side=bands["E"]["side"]["nl2"]["kA"] * x2v["measured_over_nl2"]["side"])
    g4 = dict(limit=0.40, frozen=bands["frozen"], E=bands["E"], X2_validation=x2v, E_predicted_measured=pred,
              E_pass_predicted=dict(inlet=bool(pred["inlet"] <= 0.40), side=bool(pred["side"] <= 0.40)),
              rule="kp x the largest crest over one period P in the g52b_ana G4 regions (inlet x <= 100 m all y; generating side band y >= 95 m, "
                   "x <= 180.25 m); prediction = 2nd-order screen x (X2 measured / X2 2nd-order screen) per band [computed, calibrated]")
    lev = levers(aE, kp)
    dm = dm1a_c_in()
    out = dict(amendment="AM-DFGB1", date=time.strftime("%Y-%m-%d %H:%M:%S"), energy=en, candidate=cand, short=sh, G4=g4, levers=lev, DM1A_c_in=dm,
               tool="Tools/GWWaveGen/flip52b/dfg52be_screen.py (imports dfg52b_screen.py read only)", cpu_s=round(time.time() - t0, 1))
    S.jdump(out, OUT + "/dfg52be_xf272p25.json")
    print(json.dumps(dict(energy=en["chosen"], scale_flux=en["scale_energy_flux"], short=sh, G4=dict(E_lin=dict(inlet=bands["E"]["inlet"]["lin"]["kA"],
                     side=bands["E"]["side"]["lin"]["kA"]), E_nl2=dict(inlet=bands["E"]["inlet"]["nl2"]["kA"], side=bands["E"]["side"]["nl2"]["kA"]),
                     frozen_nl2=dict(inlet=bands["frozen"]["inlet"]["nl2"]["kA"], side=bands["frozen"]["side"]["nl2"]["kA"]), pred=pred,
                     X2=x2v["measured_over_nl2"]), levers=lev, DM1A_c_in=dm, cpu_s=out["cpu_s"]), default=float))
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if sys.argv[1:2] == ["run"]:
        run()
    else:
        print(__doc__); sys.exit(1)
