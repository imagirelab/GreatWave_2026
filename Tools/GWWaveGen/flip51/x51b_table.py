# -*- coding: utf-8 -*-
"""FLIP51 X2B': the directional inflow table of the X2 direction set focused at x_f 275.25 m, on the grid x 0-244 m, and its numpy checks
(gate G1). py -3.10 -B. 2026-10-17 written new (Claude). flip50 / flip51 modules are imported READ ONLY (g50_table: the numpy mirror of the band
VEX and its helpers; g50_dirfield: the design field and the ray-supply rule; x51_common: the X2 set). No existing file is edited.

Why a new file: x51_table.build() is the X2 table builder; it fixes x_f = 220.25 m and refuses any grid other than x 0-214 m. X2B' needs
x_f 275.25 m and a table up to x 244 m (the side band now blends to absorbing at 240.25 m). The code below is x51_table.build / write /
linear_refs / checks / table_record with exactly these parameters changed (x_f, the DirField grid end 300 m so it contains x_f, the table end
244 m, the side-band generating end 210.25 m in the band steepness report) and one report added (the ray supply of the focal crest).
Same npz format, fields, convention and VEX (Houdini/FLIP50/g50_tank.hiplc reads d_x0 / d_x1 / nx from the npz, clamps x to the table).

usage:
  py -3.10 -B x51b_table.py write      Unity/Build/FLIP51/tables/X2B_T7_W140_xf275p25_<hash12>.npz (if not there)
  py -3.10 -B x51b_table.py check      G1 numpy checks -> Unity/Build/FLIP51/plan/table_check_X2B.json
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import x51b_common as XB             # noqa: E402
import x51_common as XC              # noqa: E402  read only
import g50_common as GC              # noqa: E402  read only
import g50_table as TB               # noqa: E402  read only
import g50_dirfield as DF            # noqa: E402  read only

BED_DF = TB.BED_DF                   # D19B (h0 19, toe 160.25, 1:10 beach)
G1_FOCUS_TOL = 0.01                  # as plan E G1: focal amplitude vs theory within 1 %


def full_grid(dx=GC.TABLE_DX):
    return TB.full_grid(XB.X_F, dx=dx, end=XB.DF_END)


def dirfield(x=None):
    th, w = XB.components()
    x = full_grid() if x is None else np.asarray(x, float)
    if not (x[0] <= XB.X_F <= x[-1]):
        raise ValueError("the DirField grid must contain x_f")
    return DF.DirField(XC.T7, th, w, XC.A_SUM, x, BED_DF, XB.X_F)


def build(W=XC.W):
    """x51_table.build with x_f 275.25 and the table x 0-244 m. Returns (F, info, df, x, y, m)."""
    th, w = XB.components()
    y = np.arange(0.0, float(W) + 1e-9, GC.TABLE_DX)
    df = dirfield()
    m = df.x <= XB.TABLE_X[1] + 1e-9
    x = df.x[m]
    if not np.allclose(np.diff(x), GC.TABLE_DX) or abs(x[0] - XB.TABLE_X[0]) > 1e-12 or abs(x[-1] - XB.TABLE_X[1]) > 1e-9:
        raise ValueError("table x grid is not uniform %g..%g m" % XB.TABLE_X)
    A = df.complex_amp(y)[m]
    Uc, Vc = df.complex_vel(y, depth_avg=False, z=0.0)
    Uc = Uc[m]; Vc = Vc[m]
    h = df.h[m]; k = df.k[m]
    q_fac = np.tanh(k * h) / k
    Mx = np.real(A * np.conj(Uc * q_fac[:, None])) / (2.0 * h[:, None])
    My = np.real(A * np.conj(Vc * q_fac[:, None])) / (2.0 * h[:, None])
    F = dict(er=np.real(A), ei=np.imag(A), ur=np.real(Uc), ui=np.imag(Uc), vr=np.real(Vc), vi=np.imag(Vc),
             hh=np.repeat(h[:, None], len(y), 1), kk=np.repeat(k[:, None], len(y), 1), mx=-Mx / h[:, None], my=-My / h[:, None])
    F = {nm: np.ascontiguousarray(v.T) for nm, v in F.items()}
    a_j = XC.A_SUM * np.asarray(w, float)
    info = dict(case="E_" + XB.CASE, plan="X2B", T=float(XC.T7), omega=2 * math.pi / float(XC.T7), theta_max_deg=float(np.abs(th).max()), n=int(len(th)),
                weight="explicit", theta_deg=[float(v) for v in th], w=[float(v) for v in w], a_j_list=[float(v) for v in a_j],
                a_sum=float(XC.A_SUM), a_j=float(a_j.max()), a_j_max=float(a_j.max()), a_j_min=float(a_j.min()),
                x_f=float(XB.X_F), t_f=float(XB.T_F), h0=GC.H0, bed=BED_DF, k0=float(df.k0), L0=float(2 * math.pi / df.k0),
                x0=float(x[0]), dx=float(GC.TABLE_DX), nx=int(len(x)), y0=float(y[0]), dy=float(GC.TABLE_DX), ny=int(len(y)),
                x1=float(x[-1]), y1=float(y[-1]), fields=list(GC.TABLE_FIELDS),
                convention="eta(t) = er cos(om (t - t_f)) + ei sin(om (t - t_f)); U, V likewise at z = 0, times cosh(k(z'+h))/cosh(kh); "
                           "return current mx, my (m/s, depth uniform) multiplied by g^2 when ret_on 1",
                set_rule=XB.CASE_REC["set_rule"], side_band=dict(sd_gen=XB.SD_GEN, sd_sw=XB.SD_SW),
                source="Tools/GWWaveGen/flip51/x51b_table.py build() (x51_table.build with x_f 275.25 m and the table x 0-244 m) on "
                       "g50_dirfield.DirField, DirField grid 0-300 m + x_f")
    return F, info, df, x, y, m


def table_path(ch, W=XC.W):
    return (XB.TABLE_DIR + "/X2B_T7_W%s_xf275p25_%s.npz" % (GC.tag(W), ch[:12])).replace("\\", "/")


def write(W=XC.W):
    F, info, _, _, _, _ = build(W)
    ch = TB.content_hash(F, info)
    os.makedirs(XB.TABLE_DIR, exist_ok=True)
    p = table_path(ch, W)
    info["content_sha256"] = ch
    if not os.path.exists(p):
        np.savez(p, info=np.array(json.dumps(info, default=float)), **{nm: np.asarray(F[nm], np.float32) for nm in GC.TABLE_FIELDS})
    return p, XB.sha256_file(p), ch, info


def linear_refs(df=None):
    """as x51_table.linear_refs: A_lin_x110_y0p5 (G2 denominator), |A(x_f, 0)| (the linear design crest), the axis maximum |A(x, 0)| over
    x 150-300 m and its x, the gauges' linear heights. All [computed] from the design field."""
    tab = TB.load(write()[0])
    a = complex(TB._bilinear(tab, "er", 110.0, 0.5), TB._bilinear(tab, "ei", 110.0, 0.5))
    xg = np.union1d(np.arange(100.0, 300.0 + 1e-9, 0.5), [XB.X_F])
    d2 = dirfield(x=np.union1d(np.arange(0.0, XB.DF_END + 1e-9, 0.5), [XB.X_F]))
    Ax_all = np.abs(d2.complex_amp(np.array([0.0]))[:, 0])
    Ax = np.interp(xg, d2.x, Ax_all)
    i_f = int(np.argmin(np.abs(xg - XB.X_F)))
    sel = (xg >= 150.0) & (xg <= 300.0)
    j = int(np.argmax(np.where(sel, Ax, -1.0)))
    gl = {}
    for xq in GC.GAUGE_X:
        for yq in GC.GAUGE_Y:
            c = complex(TB._bilinear(tab, "er", xq, yq), TB._bilinear(tab, "ei", xq, yq))
            gl["x%g_y%g" % (xq, yq)] = dict(x=xq, y=yq, H_lin=2.0 * abs(c), A_lin=abs(c), phase_rad=float(np.angle(c)))
    th, w = XB.components()
    return dict(A_lin_x110_y0p5=abs(a), design_crest_xf=float(Ax_all[int(np.argmin(np.abs(d2.x - XB.X_F)))]), axis_max_A=float(Ax[j]),
                axis_max_x=float(xg[j]), a_j_max=float(XC.A_SUM * np.max(w)), gauges_lin=gl, axis=dict(x=xg, A=Ax),
                tags="computed (g50_dirfield WKB field of the table; bilinear on the float32 table for the gauges, as g50_pcfg.gauges_lin). "
                     "NOTE: the WKB field has no depth limit: past the break (~282 m [computed]) the linear |A| is not a FLIP prediction")


def supply(df=None):
    """ray supply ('aperture') of the focal crest with the X2B bands and, for reference, with the X2 bands (g50_dirfield.aperture, the rule
    validated against X2's FLIP envelope in x51b_screen.py calap) [computed]."""
    df = df or dirfield()
    a_new = DF.aperture(df, GC.W_MAIN, GC.SD_BAND, GC.IN_X1, XB.SD_GEN, XB.SD_SW)
    a_old = DF.aperture(df, GC.W_MAIN, GC.SD_BAND, GC.IN_X1, GC.SD_GEN, GC.SD_SW)
    return dict(frac_X2B_bands=a_new["frac"], frac_X2_bands=a_old["frac"],
                comps=[dict(theta_deg=c["theta_deg"], x_cross_side=c["x_cross_side"], frac=c["frac"]) for c in a_new["comps"]],
                rule="fraction of the focal linear amplitude whose rays, traced back from (x_f, 0), start where the bands generate: inlet band "
                     "(ray at x 100 m has y <= W) or leaving the side band's inner edge y 95 m at x <= sd_gen (full), sd_gen..sd_sw (linear fade), "
                     "> sd_sw (none). Design screen: 0.985 with the X2B bands, 0.67-0.73 with the X2 bands at x_f 270-280 m [computed]")


def checks(W=XC.W):
    """G1 (as x51_table.checks): focus eta(x_f, 0, t = nT) = sum_j A_j(x_f) against an independent Snell + shoaling sum (1 %), phase integral,
    continuity, symmetry, zero mean mass flux with the return current, float32 + bilinear interpolation (= the VEX), vertical profile; band
    steepness (report; generating side band now x <= 210.25 m); ray supply (report)."""
    t0 = time.time()
    F, info, df, x, y, m = build(W)
    out = dict(case=XB.CASE, info={k: v for k, v in info.items() if k not in ("fields",)})
    om = info["omega"]; T = info["T"]
    A = (F["er"] + 1j * F["ei"]).T
    th_deg, w = XB.components()
    a = XC.A_SUM * np.asarray(w, float)
    # 1. focus
    jf = int(np.where(np.abs(df.x - info["x_f"]) < 1e-12)[0][0])
    A_axis = df.complex_amp(np.array([0.0]))[:, 0]
    A_f = complex(A_axis[jf])
    hf = GC.H0 - (info["x_f"] - GC.X_TOE) / GC.SLOPE_S
    k0 = TB._k_of(om, GC.H0); kf = TB._k_of(om, hf); Ks = math.sqrt(TB._cg_of(om, GC.H0) / TB._cg_of(om, hf))
    th0 = np.radians(np.asarray(th_deg, float))
    thf = np.arcsin(k0 * np.sin(th0) / kf)
    theory = float(Ks * np.sum(a * np.sqrt(np.cos(th0) / np.cos(thf))))
    out["focus"] = dict(x_f=info["x_f"], h_f=hf, eta_t0=float(A_f.real), abs_A=float(abs(A_f)), phase_rad=float(np.angle(A_f)),
                        crest_time_mod_T_s=float((np.angle(A_f) / om) % T), theory_sum=theory, Ks=Ks, focal_crest_linear_m=float(abs(A_f)),
                        rel_err_vs_theory=float(A_f.real / theory - 1.0), Hc_over_h_linear=float(abs(A_f) / hf),
                        note="the linear focal crest |A(x_f)| has no depth limit; the design predicts the crest breaks ~7 m past x_f at ~0.82 h "
                             "(Hc ~5.6 m) [computed]",
                        tag="computed: the table's DirField and an independent Snell/shoaling sum at the focus")
    # 2. phase integral
    xs_ = np.linspace(GC.X_TOE, info["x_f"], 4001)
    ks_ = np.array([TB._k_of(om, GC.H0 - (xx - GC.X_TOE) / GC.SLOPE_S) for xx in xs_])
    errs = []
    for j in (0, len(df.a) // 2, len(df.a) - 1):
        kx_ = np.sqrt(np.maximum(ks_ ** 2 - df.ky[j] ** 2, 0.0))
        slope_int = float(np.sum((kx_[1:] + kx_[:-1]) * 0.5 * np.diff(xs_)))
        for xq in (0.0, 50.0, 100.0, 150.0):
            ref = -slope_int - math.sqrt(max(k0 ** 2 - df.ky[j] ** 2, 0.0)) * (GC.X_TOE - xq)
            errs.append(abs(float(np.interp(xq, df.x, df.Phi[j])) - ref))
    out["phase_integral"] = dict(max_abs_err_rad=float(max(errs)), tag="computed (1 m trapezoid vs 4001-point trapezoid + analytic flat part)")
    # 3. continuity
    h = df.h[m]; k = df.k[m]
    qf = (np.tanh(k * h) / k)[:, None]
    U = (F["ur"] + 1j * F["ui"]).T * qf; V = (F["vr"] + 1j * F["vi"]).T * qf
    res = -1j * om * A + np.gradient(U, x, axis=0) + np.gradient(V, y, axis=1)
    scale = om * float(np.abs(A).max())
    R_ = np.abs(res[2:-2, 2:-2]); flat = x[2:-2] <= GC.X_TOE - GC.TABLE_DX
    out["continuity"] = dict(max_rel_residual_flat=float(R_[flat].max() / scale), max_rel_residual_toe_and_slope=float(R_[~flat].max() / scale),
                             scale_om_maxA=scale, tag="computed")
    # 4. symmetry
    A_neg = df.complex_amp(-y)[m]; A_pos = df.complex_amp(y)[m]
    Uc_n, Vc_n = df.complex_vel(-y, depth_avg=False, z=0.0); Uc_p, Vc_p = df.complex_vel(y, depth_avg=False, z=0.0)
    out["symmetry"] = dict(max_abs_V_at_y0=float(np.abs(F["vr"][0] + 1j * F["vi"][0]).max()), max_eta_mirror_diff=float(np.abs(A_neg - A_pos).max()),
                           max_U_mirror_diff=float(np.abs(Uc_n - Uc_p).max()), max_V_antisym_diff=float(np.abs(Vc_n + Vc_p).max()), tag="computed")
    # 5. mean mass flux and the return current
    Mx = -F["mx"].T * h[:, None]
    flux = {}
    for xq in (25.0, 50.0, 75.0, 100.0):
        i = int(np.argmin(np.abs(x - xq)))
        flux["x%g" % xq] = dict(M_without_return_m3s=float(TB._trap(Mx[i], y)), with_return_m3s=float(TB._trap(Mx[i] + F["mx"].T[i] * h[i], y)))
    out["mean_mass_flux"] = dict(per_x=flux, max_return_current_mps=float(np.abs(F["mx"]).max()), max_lateral_return_mps=float(np.abs(F["my"]).max()),
                                 tag="computed")
    # 6. interpolation (float32 + bilinear = the VEX) against an exact field on a 0.05 m grid
    rng = np.random.default_rng(51)
    dff = dirfield(full_grid(dx=0.05))
    cand = np.where(dff.x <= XB.TABLE_X[1])[0]
    iq = rng.choice(cand, 300); yq = rng.uniform(0.0, float(W), 300); tq = rng.uniform(0.0, T, 300)
    tab = dict(info=info, **{nm: np.asarray(F[nm], np.float32).astype(np.float64) for nm in GC.TABLE_FIELDS})
    e_np, U_np, V_np = TB.dirwave_np(tab, dff.x[iq], 0.0 * yq + 50.0, yq, tq, 1.0, ret_on=0.0)
    Af = dff.complex_amp(yq); Uf, Vf = dff.complex_vel(yq, depth_avg=False, z=0.0)
    ph = np.exp(-1j * om * tq); ii = np.arange(300)
    ex = np.real(Af[iq, ii] * ph); ux = np.real(Uf[iq, ii] * ph); vx = np.real(Vf[iq, ii] * ph)
    sc_e = float(np.abs(A).max()); sc_u = float(np.abs(F["ur"] + 1j * F["ui"]).max())
    out["interpolation"] = dict(max_rel_eta=float(np.abs(e_np - ex).max() / sc_e), max_rel_U=float(np.abs(U_np - ux).max() / sc_u),
                                max_rel_V=float(np.abs(V_np - vx).max() / sc_u), n=300, tag="computed")
    # 7. vertical profile
    errs7 = []
    for z in (-2.0, -8.0, -13.0):
        Uz, Vz = df.complex_vel(y, depth_avg=False, z=z)
        Uz = Uz[m]; Vz = Vz[m]
        for xx in (20.0, 60.0, 99.0, 150.0, 200.0):
            i = int(np.argmin(np.abs(x - xx)))
            for yy in (0.0, 40.0, 100.0, 130.0):
                jj = int(np.argmin(np.abs(y - yy)))
                tq_ = (math.atan2(F["ei"][jj, i], F["er"][jj, i]) + math.pi / 2) / om
                _, Uv, Vv = TB.dirwave_np(tab, x[i], z, y[jj], tq_, 1.0, ret_on=0.0)
                p_ = np.exp(-1j * om * tq_)
                errs7.append(max(abs(float(Uv) - np.real(Uz[i, jj] * p_)), abs(float(Vv) - np.real(Vz[i, jj] * p_))) / sc_u)
    out["vertical_profile"] = dict(max_rel_err=float(max(errs7)), tag="computed (float32 storage)")
    # 8. band steepness of the linear target (report; G4 watches the realised value; the generating side band is now x <= 210.25 m)
    kk = F["kk"]
    absA = np.hypot(F["er"], F["ei"])
    inlet = np.zeros_like(absA, bool); inlet[:, x < GC.IN_X1] = True
    side = np.zeros_like(absA, bool); side[np.ix_(y >= GC.SD0, x <= XB.SD_GEN)] = True
    side_new = np.zeros_like(absA, bool); side_new[np.ix_(y >= GC.SD0, (x > GC.SD_GEN) & (x <= XB.SD_GEN))] = True
    out["band_linear_steepness"] = dict(kA_inlet_band_max=float((kk * absA)[inlet].max()), kA_side_band_max=float((kk * absA)[side].max()),
                                        kA_side_band_new_part_max=float((kk * absA)[side_new].max()),
                                        tag="computed (linear |A| of the table x local k); new part = x 180.25-210.25 m, y >= 95 m (on the 1:10 slope)")
    out["supply"] = supply(df)
    out["linear_refs"] = {k_: v for k_, v in linear_refs().items() if k_ != "axis"}
    ok = dict(focus=bool(abs(out["focus"]["rel_err_vs_theory"]) < G1_FOCUS_TOL and abs(out["focus"]["phase_rad"]) < 1e-9),
              phase=bool(out["phase_integral"]["max_abs_err_rad"] < 0.02), continuity_flat=bool(out["continuity"]["max_rel_residual_flat"] < 5e-3),
              symmetry=bool(out["symmetry"]["max_abs_V_at_y0"] < 1e-9 and out["symmetry"]["max_eta_mirror_diff"] < 1e-9
                            and out["symmetry"]["max_V_antisym_diff"] < 1e-9),
              return_zero=bool(all(abs(v["with_return_m3s"]) < 1e-6 * max(1.0, abs(v["M_without_return_m3s"])) for v in flux.values())),
              interpolation=bool(max(out["interpolation"]["max_rel_eta"], out["interpolation"]["max_rel_U"], out["interpolation"]["max_rel_V"]) < 0.02),
              vertical=bool(out["vertical_profile"]["max_rel_err"] < 1e-4),
              symmetric_set=bool(np.allclose(np.sort(th_deg), -np.sort(th_deg)[::-1]) and abs(float(np.sum(w)) - 1.0) < 1e-12),
              covers_bands=bool(info["x1"] >= XB.SD_SW and info["y1"] >= float(W) - 1e-9),
              same_set_as_X2=bool(np.array_equal(np.asarray(th_deg), np.asarray(XC.components("X2")[0]))
                                  and np.array_equal(np.asarray(w), np.asarray(XC.components("X2")[1]))))
    out["ok"] = ok
    out["all_ok"] = bool(all(ok.values()))
    out["gate"] = "G1 (X2B): focus vs theory < 1 %%, symmetry, continuity, interpolation, vertical profile, covers the bands, X2 set -> %s" % (
        "PASS" if out["all_ok"] else "FAIL")
    p, sha, ch, _ = write(W)
    out["npz"] = p; out["npz_sha256"] = sha; out["info"]["content_sha256"] = ch
    out["cpu_s"] = round(time.time() - t0, 2)
    return out


def table_record():
    """cfg['dir'] block (as x51_table.table_record) for X2B."""
    p, sha, ch, info = write()
    lr = linear_refs()
    return dict(case=info["case"], npz=p, npz_sha256=sha, content_sha256=ch, T=info["T"], omega=info["omega"], theta_max_deg=info["theta_max_deg"],
                n=info["n"], weight=info["weight"], theta_deg=info["theta_deg"], w=info["w"], a_sum=info["a_sum"], a_j=info["a_j"],
                a_j_max=info["a_j_max"], x_f=info["x_f"], t_f=info["t_f"],
                grid=dict(x=[info["x0"], info["x1"]], y=[info["y0"], info["y1"]], d=info["dx"]), fields=info["fields"],
                gauges_lin={k: dict(x=v["x"], y=v["y"], H_lin=v["H_lin"], phase_rad=v["phase_rad"]) for k, v in lr["gauges_lin"].items()},
                linear_refs=dict(A_lin_x110_y0p5=lr["A_lin_x110_y0p5"], design_crest_xf=lr["design_crest_xf"], axis_max_A=lr["axis_max_A"],
                                 axis_max_x=lr["axis_max_x"], a_j_max=lr["a_j_max"]))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "write":
        p, sha, ch, info = write()
        print(json.dumps(dict(table=p, sha256=sha, content=ch, n=info["n"], x=[info["x0"], info["x1"]], x_f=info["x_f"]), ensure_ascii=False))
    elif a[0] == "check":
        o = checks()
        XB.jdump(o, XB.TABLE_CHECK)
        print(json.dumps(XC.clean(dict(ok=o["ok"], all_ok=o["all_ok"], focus_abs_A=o["focus"]["abs_A"], rel=o["focus"]["rel_err_vs_theory"],
                                       Hc_over_h_lin=o["focus"]["Hc_over_h_linear"], supply=o["supply"]["frac_X2B_bands"],
                                       supply_X2_bands=o["supply"]["frac_X2_bands"], band=o["band_linear_steepness"], refs=o["linear_refs"],
                                       npz=o["npz"], cpu_s=o["cpu_s"], out=XB.TABLE_CHECK)), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
