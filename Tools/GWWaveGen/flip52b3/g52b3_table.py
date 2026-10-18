# -*- coding: utf-8 -*-
"""FLIP52B3 plan DFGB4 (DFG-2B-V): the N-layer complex-amplitude inflow table = DFG-2B-E's WKB table over the D19B beach x the two registered
generator maps (the inlet-only n5 phase calibration and the 3 % side-band taper), and its numpy checks = gate G1 (numpy only: py -3.10 -B, and
importable from hython). 2026-10-18 written new (Claude) by adapting flip52b2/g52b2_table.py (DFGB3, FROZEN, not edited). Read only (imported):
flip52/g52_table (the N-layer npz format, the numpy mirror of the band VEX dirwave_np / relax_np / load / content_hash, used unchanged),
flip50/g50_dirfield (DirField). Read only (compared): DFG-2B-E's table Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz,
DM1A's input table, the design-step G4 map Unity/Build/FLIP52B3/_scratch/g4map.npz (report screen only).

The DESIGN sea = DFG-2B-E's, bit for bit (G1 'design_equals_DFGB_E'). The GENERATOR table, per layer n and node (x, y):
    er/ei, ur/ui, vr/vi (complex)  x  F_n(x) g(x, y),    F_5(x) = exp(-i PHI5 b(x)),  F_3 = F_4 = 1,
    b(x) = 1 - smooth01((x - 80)/20),  g(x, y) = 1 - 0.03 clip((x-140)/20, 0, 1) clip((125-y)/20, 0, 1) smooth01((y-75)/20)
    kk<n>, hh unchanged; the return current mx, my x g^2 (period means of A conj U: invariant under a per-layer phase, quadratic in the gain).
The LINEAR REFERENCES for the gates and reports are the DESIGN's (= DFG-2B-E's): G2f measures realised vs design (the generator content at the
gauges is recorded beside it as *_table; at x 110 m it equals the design because b(110) = 0 and g(110, y) = 1).
Convention as flip52: eta(t) = sum_n er<n> cos(2 pi n (t - t_f)/P) + ei<n> sin(...) = sum_n Re(A_n e^{-i w_n (t - t_f)}).

G1 continuity for this table (registered in plan_DFGB4): a spatially varying factor cannot keep the generator an exact linear solution where it
varies (its gradient adds U q dF/dx + V q dF/dy), so (a) the DESIGN layers pass the frozen flat-part rule < 5e-3 (= DFG-2B); (b) the GENERATOR
passes < 5e-3 on the flat part wherever the maps are constant (3 m away from the seam x 80-100 m and the taper x 140-160 m / y 75-125 m); (c) in
those strips its raw residual is <= 0.10 (the G1 WKB-slope report level every earlier run accepted) and, weighted by the band relaxation weight x
the target factor of the frozen VEX, <= 0.10 x the same weighted residual that the frozen wall / side-wall tapers already put into the effective
band target (computed here the same way) - i.e. the seam adds less than a tenth of what the D19B bands already accept.

usage (py -3.10 -B):
  g52b3_table.py write          Unity/Build/FLIP52B3/tables/DFGB4_P28_xf272p25_W140_<hash12>.npz (if not there) and print its path
  g52b3_table.py check          G1 numpy checks -> Unity/Build/FLIP52B3/plan/table_check_DFGB4.json
  g52b3_table.py energy         the Q84 energy numbers (spectral and in-tank), json to stdout
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52b3_common as GC          # noqa: E402
import g52_table as TB52           # noqa: E402  read only (npz format, VEX mirror)
import g50_dirfield as DF          # noqa: E402  read only (WKB DirField)

dirwave_np = TB52.dirwave_np
relax_np = TB52.relax_np
load = TB52.load
from_build = TB52.from_build
content_hash = TB52.content_hash
fields_of = TB52.fields_of
G1_TOL = dict(focus_rel=1e-3, phase_rad=1e-6, continuity_flat=5e-3, continuity_slope_report=0.10, seam_raw=0.10, seam_vs_frozen_tapers=0.10,
              interpolation=0.02, vertical=1e-4, mass_flux_rel=1e-6, symmetry=1e-9, periodic_rel=1e-9, map_rel=2e-6, seam_margin_m=3.0)
RHO = 1000.0
AM_DFGB1B = dict(DM1A=dict(inlet_var=2.316, P_in_MW=42.87, P_full_MW=36.44), DFGB_E=dict(inlet_var=0.295, P_in_MW=10.05, P_full_MW=4.39))
KP_G4 = 0.088136                   # = b3_g4map.KP (kp at h0 19 m, T 7 s)


def full_grid():
    return np.union1d(np.arange(GC.TABLE_X[0], GC.X_FULL_END + 1e-9, GC.TABLE_DX), [float(GC.X_F)])


def dirfields(x=None):
    """one DirField per harmonic (WKB over the DESIGN bed = D19B beach), phases referenced to (x_f, 0) (= DFG-2B-E)."""
    C = GC.components()
    x = full_grid() if x is None else np.asarray(x, float)
    out = []
    for n, h_ in enumerate(GC.HARMONICS):
        T = GC.P_S / float(h_)
        out.append(DF.DirField(T, C["th"], C["wd"], C["a_sum"] * float(C["wf"][n]), x, GC.BED_DF_DESIGN, GC.X_F))
    return C, out


def build_design():
    """the DESIGN arrays (ny, nx) float64 = DFG-2B-E's table content (before the float32 cast), the per-layer mass-flux pieces (nx, ny)."""
    C, dfs = dirfields()
    y = np.arange(GC.TABLE_Y[0], GC.TABLE_Y[1] + 1e-9, GC.TABLE_DX)
    m = dfs[0].x <= GC.TABLE_X[1] + 1e-9
    x = dfs[0].x[m]
    if not np.allclose(np.diff(x), GC.TABLE_DX) or abs(x[0] - GC.TABLE_X[0]) > 1e-12 or abs(x[-1] - GC.TABLE_X[1]) > 1e-9:
        raise ValueError("table x grid is not uniform 0..214 m")
    F = {}
    h = dfs[0].h[m]
    Mx = np.zeros((len(x), len(y))); My = np.zeros_like(Mx)
    per_layer_M = []
    for n, d in enumerate(dfs):
        A = d.complex_amp(y)[m]
        Uc, Vc = d.complex_vel(y, depth_avg=False, z=0.0)
        Uc = Uc[m]; Vc = Vc[m]
        k = d.k[m]
        q = np.tanh(k * h) / k
        mxn = np.real(A * np.conj(Uc * q[:, None])) / (2.0 * h[:, None])
        myn = np.real(A * np.conj(Vc * q[:, None])) / (2.0 * h[:, None])
        per_layer_M.append((-mxn / h[:, None], -myn / h[:, None]))
        Mx += mxn; My += myn
        for nm, v in (("er", A.real), ("ei", A.imag), ("ur", Uc.real), ("ui", Uc.imag), ("vr", Vc.real), ("vi", Vc.imag),
                      ("kk", np.repeat(k[:, None], len(y), 1))):
            F["%s%d" % (nm, n)] = np.ascontiguousarray(v.T)
    F["hh"] = np.ascontiguousarray(np.repeat(h[:, None], len(y), 1).T)
    F["mx"] = np.ascontiguousarray((-Mx / h[:, None]).T)
    F["my"] = np.ascontiguousarray((-My / h[:, None]).T)
    return F, C, dfs, x, y, per_layer_M


def maps(x, y):
    """(ny, nx) maps on the table nodes: the complex layer factors F_n g and the gain g."""
    X, Y = np.meshgrid(np.asarray(x, float), np.asarray(y, float))
    return [GC.layer_factor(n, X, Y) for n in range(len(GC.HARMONICS))], GC.gain(X, Y), X, Y


def calibrate(Fd, x, y, per_layer_M):
    """the generator arrays: layer n's complex fields x F_n(x) g(x, y); kk, hh unchanged; mx, my x g^2; the per-layer mass-flux pieces x g^2."""
    fac, g, X, Y = maps(x, y)
    F = dict(Fd)
    for n in range(len(GC.HARMONICS)):
        c = fac[n]
        for a, b in (("er", "ei"), ("ur", "ui"), ("vr", "vi")):
            z = (Fd["%s%d" % (a, n)] + 1j * Fd["%s%d" % (b, n)]) * c
            F["%s%d" % (a, n)] = np.ascontiguousarray(z.real)
            F["%s%d" % (b, n)] = np.ascontiguousarray(z.imag)
    F["mx"] = np.ascontiguousarray(Fd["mx"] * g ** 2)
    F["my"] = np.ascontiguousarray(Fd["my"] * g ** 2)
    pM = [(mx_ * (g ** 2).T, my_ * (g ** 2).T) for mx_, my_ in per_layer_M]
    return F, pM


def build():
    """generator arrays (ny, nx) float64 and the info dict."""
    Fd, C, dfs, x, y, per_layer_M_d = build_design()
    F, per_layer_M = calibrate(Fd, x, y, per_layer_M_d)
    nl = len(dfs)
    info = dict(set=GC.SET, plan="DFGB4", plan_name=GC.NAME, plan_frozen=GC.PLAN_REL, P=float(GC.P_S), harmonics=[int(v) for v in GC.HARMONICS],
                n_layers=int(nl), omega=[float(d.om) for d in dfs], T=[float(d.T) for d in dfs], k=[float(d.k0) for d in dfs],
                kh0=[float(d.k0 * GC.H0) for d in dfs], h=float(GC.H0), h0=float(GC.H0), bed=GC.BED_DF_DESIGN, freq_weights=[float(v) for v in C["wf"]],
                theta_deg=[float(v) for v in C["th"]], dir_weights=[float(v) for v in C["wd"]], dspec=list(GC.DSPEC), a_sum=float(C["a_sum"]),
                a_max_component=float(C["a"].max()), amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]], sum_a2=float(np.sum(C["a"] ** 2)),
                n_components=int(C["a"].size), x_f=float(GC.X_F), h_f_design=float(GC.H0 - (GC.X_F - GC.X_TOE) / GC.SLOPE_S), h_f=float(GC.h_of(GC.X_F)),
                t_f=float(GC.T_F), foci=[float(v) for v in GC.FOCI],
                x0=float(x[0]), dx=float(GC.TABLE_DX), nx=int(len(x)), y0=float(y[0]), dy=float(GC.TABLE_DX), ny=int(len(y)),
                x1=float(x[-1]), y1=float(y[-1]), fields=fields_of(nl), dirfield_grid=[float(dfs[0].x[0]), float(dfs[0].x[-1])],
                energy_scale=float(GC.E_SCALE), a_sum_frozen=float(GC.A_SUM_FROZEN), sum_a2_DM1A=float(GC.DM1A_SUM_A2),
                calibration=dict(n=GC.CAL_N, phi5_rad=GC.PHI5, phi5_measured_rad=GC.PHI5_MEAS, scale=GC.CAL_SCALE5, x_full_m=GC.CAL_X_FULL,
                                 x_zero_m=GC.CAL_X_ZERO, rule=GC.CAL_RULE),
                taper=dict(d=GC.TAPER_D, x=list(GC.TAPER_X), y=list(GC.TAPER_Y), y_in=list(GC.TAPER_YIN), rule=GC.TAPER_RULE),
                design_table="Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz (DFG-2B-E; content %s)" % GC.DFGBE_TABLE_CONTENT[:16],
                convention="eta(t) = sum_n er<n> cos(2 pi h_n (t - t_f)/P) + ei<n> sin(...); U, V likewise at z = 0, times cosh(k_n(z'+h))/cosh(k_n h) "
                           "with z' stretched on the total eta and k_n = kk<n> (local); return current mx, my (m/s, depth uniform) x g^2 when ret_on 1; "
                           "layer n of this GENERATOR table = the design x F_n(x) g(x, y) (the plan_DFGB4 maps)",
                source="Tools/GWWaveGen/flip52b3/g52b3_table.py build(): g50_dirfield.DirField per harmonic (WKB over D19B, = DFG-2B-E) x the DFGB4 maps")
    return F, info, C, dfs, x, y, per_layer_M, Fd, per_layer_M_d


def table_path(ch):
    return (GC.TABLE_DIR + "/%s_P%s_xf%s_W%s_%s.npz" % (GC.TAG, GC.tag(GC.P_S), GC.tag(GC.X_F), GC.tag(GC.W_MAIN), ch[:12])).replace("\\", "/")


def write(dry=False):
    F, info, *_ = build()
    ch = content_hash(F, info)
    p = table_path(ch)
    info["content_sha256"] = ch
    if dry:
        return p, (GC.sha256_file(p) if os.path.exists(p) else None), ch, info
    os.makedirs(GC.TABLE_DIR, exist_ok=True)
    if not os.path.exists(p):
        np.savez(p, info=np.array(json.dumps(info, default=float)), **{nm: np.asarray(F[nm], np.float32) for nm in info["fields"]})
    return p, GC.sha256_file(p), ch, info


# ======================================================================== linear references (gates and reports): the DESIGN's
def _amp_at(dfs, xg, yg, factor=False):
    row = {}
    for n, d in enumerate(dfs):
        A = d.complex_amp(np.array([yg]))
        a = complex(np.interp(xg, d.x, A[:, 0].real) + 1j * np.interp(xg, d.x, A[:, 0].imag))
        if factor:
            a *= complex(GC.layer_factor(n, np.array(xg), np.array(yg)))
        row["n%d" % GC.HARMONICS[n]] = [a.real, a.imag]
    return row


def linear_refs():
    """[computed] per-frequency complex amplitudes of the DESIGN (= DFG-2B-E's table) at the G2f gauges (x 110 m, y 0.5/20/40/60/80 m), the
    report gauges, the focal design crest (DirField at x_f), the c_in line x 110 m over one period; beside them the generator content (_table)."""
    C, dfs = dirfields()
    g2 = {"y%g" % yg: _amp_at(dfs, 110.0, yg) for yg in GC.GAUGE_Y}
    g2t = {"y%g" % yg: _amp_at(dfs, 110.0, yg, factor=True) for yg in GC.GAUGE_Y}
    rep = {}
    for xg, yg in ((128.0, 0.5), (160.0, 0.5), (200.0, 0.5), (228.5, 0.5), (235.5, 0.5), (240.0, 0.5), (262.0, 0.5)):
        rep["x%g_y%g" % (xg, yg)] = _amp_at(dfs, xg, yg)
    i_f = int(np.argmin(np.abs(dfs[0].x - GC.X_F)))
    design = float(sum(np.abs(d.complex_amp(np.array([0.0]))[i_f, 0]) for d in dfs))
    yl = np.arange(0.0, GC.INTERIOR_Y + 1e-9, 1.0)
    i110 = int(np.argmin(np.abs(dfs[0].x - 110.0)))
    A110 = [d.complex_amp(yl)[i110] for d in dfs]
    cin = 0.0
    for t in GC.T_F + np.arange(-GC.P_S / 2.0, GC.P_S / 2.0 - 1e-9, 0.125):
        e = sum(np.real(A * np.exp(-1j * d.om * (t - GC.T_F))) for A, d in zip(A110, dfs))
        cin = max(cin, float(e.max()))
    kp = GC.kp()
    return dict(G2f_gauges=dict(x=110.0, y=list(GC.GAUGE_Y), A_n=g2, convention="A = er + i ei of eta_n = Re(A e^{-i w_n (t - t_f)}); the DESIGN "
                                "target (= DFG-2B-E's table at the gauges): G2f compares the realised wave with it (DFGB4 calibration)"),
                G2f_gauges_table=dict(x=110.0, y=list(GC.GAUGE_Y), A_n=g2t, note="the generator table content at the gauges (= the design: b(110) = 0, "
                                      "g(110, y) = 1), report"),
                report_gauges=rep, design_crest_xf_m=design, a_sum=C["a_sum"], amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]],
                a_max_component=float(C["a"].max()), c_in_line_x110_lin_m=cin, gain_lin_over_c_in=design / cin if cin > 0 else None,
                kp=kp, kp_asum=kp * C["a_sum"], harmonics=list(GC.HARMONICS), omega=[float(d.om) for d in dfs],
                calibration=dict(n=GC.CAL_N, phi5_rad=GC.PHI5), taper_d=GC.TAPER_D,
                tags="computed (linear WKB DirField per harmonic on D19B = DFG-2B-E's design)")


# ======================================================================== the Q84 energy numbers
def _layers_npz(p):
    d = np.load(p)
    info = json.loads(str(d["info"]))
    if "er" in d.files:
        L = [((d["er"] + 1j * d["ei"]).astype(complex), (d["ur"] + 1j * d["ui"]).astype(complex), (d["vr"] + 1j * d["vi"]).astype(complex),
              d["kk"].astype(float))]
    else:
        L = [((d["er%d" % n] + 1j * d["ei%d" % n]).astype(complex), (d["ur%d" % n] + 1j * d["ui%d" % n]).astype(complex),
              (d["vr%d" % n] + 1j * d["vi%d" % n]).astype(complex), d["kk%d" % n].astype(float)) for n in range(int(info["n_layers"]))]
    return L, d["hh"].astype(float), info


def tank_energy(L, h, x_in, sd0, sd_gen):
    """[computed] linear, period-mean, half tank, nodes of the 1 m table (x index = x, y index = y): surface variance 0.5 sum_n |A_n|^2;
    energy flux per layer rho g <eta u0> (2kh + sinh 2kh) / (4k cosh^2 kh) = rho g 0.5 Re(A conj U) (...) (exact for linear waves, the
    directions of one frequency summed in A, U; distinct frequencies do not mix in the period mean); node sums x 1 m (the AM-DFGB1b rule,
    which this reproduces: DM1A 2.316 m^2 / 42.87 MW). Interior = x >= x_in, y <= sd0: through x_in (y 0-sd0) + through y = sd0 (x_in-sd_gen)."""
    var = sum(0.5 * np.abs(A) ** 2 for A, _, _, _ in L)
    Fx = 0.0; Fy = 0.0
    for A, U, V, k in L:
        fac = (2 * k * h + np.sinh(2 * k * h)) / (4 * k * np.cosh(k * h) ** 2)
        Fx = Fx + RHO * GC.G * 0.5 * np.real(A * np.conj(U)) * fac
        Fy = Fy + RHO * GC.G * 0.5 * np.real(A * np.conj(V)) * fac
    ix, jy, ig = int(round(x_in)), int(round(sd0)), int(round(sd_gen))
    vin = float(var[:, :ix + 1].mean())
    px = float(Fx[:jy + 1, ix].sum()); py = float(Fy[jy, ix:ig + 1].sum()); pf = float(Fx[:, ix].sum())
    return dict(inlet_band_mean_variance_m2=vin, inlet_band_Hm0_equiv_m=4.0 * math.sqrt(vin), power_into_interior_MW=(px - py) / 1e6,
                power_through_x_in_MW=px / 1e6, power_through_side_edge_MW=-py / 1e6, power_across_x_in_full_half_width_MW=pf / 1e6,
                layout=dict(x_in=x_in, sd0=sd0, sd_gen=sd_gen, W=float(h.shape[0] - 1)))


def energy_in_tank():
    """the incoming linear sea inside the tank from the input tables (Q84 honesty: 'equal spectral energy' is not 'equal in-tank energy'):
    DFGB4's generator table, DFG-2B-E's table and DM1A's table, all on the D19B layout (x 100 m, y 95 m, side band generating to 180.25 m);
    the DM1A / DFG-2B-E numbers reproduce AM-DFGB1b (check)."""
    F, info, *_ = build()
    nl = info["n_layers"]
    f32 = lambda v: np.asarray(v, np.float32)
    L4 = [((f32(F["er%d" % n]) + 1j * f32(F["ei%d" % n])).astype(complex), (f32(F["ur%d" % n]) + 1j * f32(F["ui%d" % n])).astype(complex),
           (f32(F["vr%d" % n]) + 1j * f32(F["vi%d" % n])).astype(complex), f32(F["kk%d" % n]).astype(float)) for n in range(nl)]
    lay = (GC.IN_X1, GC.SD0, GC.SD_GEN)
    out = dict(rule=tank_energy.__doc__.split("[computed] ")[1][:500], tag="[computed] numpy on the linear input tables")
    out["DFGB4"] = tank_energy(L4, f32(F["hh"]).astype(float), *lay)
    for nm, p in (("DM1A", GC.DM1A_TABLE), ("DFGB_E", GC.DFGBE_TABLE)):
        if os.path.exists(p):
            L, h, _ = _layers_npz(p)
            out[nm] = tank_energy(L, h, *lay)
            out[nm]["table"] = p.replace(GC.REPO + "/", "")
    D = out.get("DM1A")
    if D:
        for nm in ("DFGB4", "DFGB_E"):
            if out.get(nm):
                out[nm]["inlet_variance_over_DM1A"] = out[nm]["inlet_band_mean_variance_m2"] / D["inlet_band_mean_variance_m2"]
                out[nm]["interior_power_over_DM1A"] = out[nm]["power_into_interior_MW"] / D["power_into_interior_MW"]
        rep = {}
        for nm in ("DM1A", "DFGB_E"):
            if out.get(nm):
                a = AM_DFGB1B[nm]; b = out[nm]
                rep[nm] = dict(inlet_var_rel=b["inlet_band_mean_variance_m2"] / a["inlet_var"] - 1.0, P_in_rel=b["power_into_interior_MW"] / a["P_in_MW"] - 1.0,
                               P_full_rel=b["power_across_x_in_full_half_width_MW"] / a["P_full_MW"] - 1.0)
        out["reproduces_AM_DFGB1b"] = dict(rel_diff=rep, ok=bool(rep and all(abs(v) < 0.005 for r in rep.values() for v in r.values())))
    if out.get("DFGB_E"):
        E4, EE = out["DFGB4"], out["DFGB_E"]
        out["DFGB4_vs_DFGB_E"] = dict(interior_power_ratio=E4["power_into_interior_MW"] / EE["power_into_interior_MW"],
                                      inlet_variance_ratio=E4["inlet_band_mean_variance_m2"] / EE["inlet_band_mean_variance_m2"],
                                      side_edge_power_ratio=(E4["power_through_side_edge_MW"] / EE["power_through_side_edge_MW"]
                                                             if abs(EE["power_through_side_edge_MW"]) > 1e-12 else None),
                                      note="the n5 phase factor changes no period-mean power; the taper scales the side-band target (side edge y 95 m, x 140-180 m)")
    C = GC.components()
    out["spectral"] = dict(sum_a2_m2=float(np.sum(C["a"] ** 2)), DM1A_sum_a2_m2=GC.DM1A_SUM_A2, ratio=float(np.sum(C["a"] ** 2)) / GC.DM1A_SUM_A2,
                           E_Jm2=0.5 * RHO * GC.G * float(np.sum(C["a"] ** 2)), Hm0_spectral_m=4.0 * math.sqrt(0.5 * float(np.sum(C["a"] ** 2))))
    E = out["DFGB4"]
    out["statement_en"] = ("equal SPECTRAL energy (Q84): sum a^2 = %.6f m^2 = DM1A's %.6f m^2 at the generation depth h0 19 m (energy density "
                           "0.5 rho g sum a^2 = %.0f J/m^2, spectral Hm0 %.2f m); inside the tank the incoming linear waves carry less: inlet-band "
                           "surface variance %.3f x DM1A's (Hm0-equivalent %.2f m vs %.2f m) and the power entering the interior %.3f x DM1A's "
                           "(%.2f vs %.2f MW per half tank) [computed, the AM-DFGB1b rule on the generator table; DFG-2B-E: interior power %.3f x; the "
                           "n5 phase factor changes no power, the 3 %% side-band taper changes the interior power by x %.4f]"
                           % (out["spectral"]["sum_a2_m2"], GC.DM1A_SUM_A2, out["spectral"]["E_Jm2"], out["spectral"]["Hm0_spectral_m"],
                              E.get("inlet_variance_over_DM1A", float("nan")), E["inlet_band_Hm0_equiv_m"], (D or {}).get("inlet_band_Hm0_equiv_m", float("nan")),
                              E.get("interior_power_over_DM1A", float("nan")), E["power_into_interior_MW"], (D or {}).get("power_into_interior_MW", float("nan")),
                              (out.get("DFGB_E") or {}).get("interior_power_over_DM1A", float("nan")),
                              (out.get("DFGB4_vs_DFGB_E") or {}).get("interior_power_ratio", float("nan"))))
    return out


# ======================================================================== G1: numpy checks
def _deriv4(f, axis, d):
    f = np.moveaxis(f, axis, 0)
    out = (-f[4:] + 8 * f[3:-1] - 8 * f[1:-3] + f[:-4]) / (12.0 * d)
    return np.moveaxis(out, 0, axis)


def _cont_resid(tab, n, om, gm=None, sc_tab=None):
    """complex linear continuity residual / (om max|A|) of layer n of a table (optionally of the effective band target gm x table), (ny-4, nx-4);
    the scale is max|A| of sc_tab (default: tab itself)."""
    k = np.asarray(tab["kk%d" % n], float); h = np.asarray(tab["hh"], float)
    q = np.tanh(k * h) / k
    s = 1.0 if gm is None else gm
    A = (np.asarray(tab["er%d" % n], float) + 1j * np.asarray(tab["ei%d" % n], float)) * s
    U = (np.asarray(tab["ur%d" % n], float) + 1j * np.asarray(tab["ui%d" % n], float)) * q * s
    V = (np.asarray(tab["vr%d" % n], float) + 1j * np.asarray(tab["vi%d" % n], float)) * q * s
    res = -1j * om * A[2:-2, 2:-2] + _deriv4(U, 1, GC.TABLE_DX)[2:-2, :] + _deriv4(V, 0, GC.TABLE_DX)[:, 2:-2]
    st = tab if sc_tab is None else sc_tab
    sc = om * float(np.abs((np.asarray(st["er%d" % n], float) + 1j * np.asarray(st["ei%d" % n], float))).max())
    return res / sc


def band_weight(X, Y):
    """the per-dt0 relaxation weight of the frozen D19B bands (VEX bands50 at dts = dt0: inlet relaxw((100 - x)/100), side band relaxw((y - 95)/45)
    on the generating part x (1 - smooth01((x - 180.25)/30)), corner = the larger) and the frozen target factor walltaper(x) sdtaper(y) x the side
    factor (1 - s); numpy of g50_tanklib.bands50 / relax_apply (ramp 1, gains 1)."""
    relaxw = lambda c: (np.exp(np.clip(c, 0.0, 1.0) ** 3.5) - 1.0) / (math.e - 1.0)
    s = GC._s01((X - GC.SD_GEN) / (GC.SD_SW - GC.SD_GEN))
    w_in = np.where(X < GC.IN_X1, relaxw((GC.IN_X1 - X) / GC.IN_X1), 0.0)
    insd = Y > GC.SD0
    w_sd = np.where(insd, relaxw((Y - GC.SD0) / (GC.W_MAIN - GC.SD0)) * (1.0 - s), 0.0)
    W = np.maximum(w_in, w_sd)
    tf = GC._s01(X / GC.WALL_TAPER) * GC._s01((GC.W_MAIN - Y) / GC.SD_TAPER) * np.where(insd, 1.0 - s, 1.0)
    return W, tf


def g4_screen(F):
    """[calibrated, report] the design step's per-cell G4 screen (diag/g4map.json rule) on THIS generator table: predicted side-band G4 =
    max over the side-band cells (y 95-140, x 0-180 m, cells with DFG-2B-E's linear max > 1 m) of r_B2E x kp x the table's largest linear crest
    over one period; r_B2E = DFG-2B-E's measured FLIP / linear ratio map (Unity/Build/FLIP52B3/_scratch/g4map.npz)."""
    if not os.path.exists(GC.G4MAP_NPZ):
        return dict(available=False, why="g4map.npz missing (%s)" % GC.G4MAP_NPZ)
    Z = np.load(GC.G4MAP_NPZ)
    r, L2 = Z["r"], Z["L2"]
    YS = np.arange(95, 140); XS = np.arange(0, 180)
    lay = []
    for n in range(len(GC.HARMONICS)):
        A = np.asarray(F["er%d" % n], np.float32).astype(float) + 1j * np.asarray(F["ei%d" % n], np.float32).astype(float)
        c = 0.25 * (A[YS[0]:YS[-1] + 1, XS[0]:XS[-1] + 1] + A[YS[0]:YS[-1] + 1, XS[0] + 1:XS[-1] + 2]
                    + A[YS[0] + 1:YS[-1] + 2, XS[0]:XS[-1] + 1] + A[YS[0] + 1:YS[-1] + 2, XS[0] + 1:XS[-1] + 2])
        lay.append(c)
    M = np.full(lay[0].shape, -9.0)
    for t in np.linspace(0.0, GC.P_S, 673):
        e = sum(np.real(A * np.exp(-1j * 2 * math.pi * GC.HARMONICS[k] / GC.P_S * t)) for k, A in enumerate(lay))
        M = np.maximum(M, e)
    ok = L2 > 1.0
    pred = np.where(ok, r * KP_G4 * M, np.nan)
    j = int(np.nanargmax(pred)); iy, ix = np.unravel_index(j, pred.shape)
    jl = int(np.argmax(KP_G4 * M)); ly, lx = np.unravel_index(jl, M.shape)
    out = dict(available=True, predicted_G4_side=float(pred[iy, ix]), at=[float(XS[ix] + 0.5), float(YS[iy] + 0.5)],
               linear_max=float(KP_G4 * M[ly, lx]), linear_at=[float(XS[lx] + 0.5), float(YS[ly] + 0.5)],
               g4map_npz_sha256=GC.sha256_file(GC.G4MAP_NPZ), rule=g4_screen.__doc__.split("[calibrated, report] ")[1][:400],
               reference="diag/g4map.json: DFG-2B-E measured 0.397 (screen 0.397), DFGB3 measured 0.419 (screen 0.412), 'design + taper 3 %' 0.387",
               tag="[calibrated]")
    if os.path.exists(GC.G4MAP_JSON):
        try:
            gj = GC.jload(GC.G4MAP_JSON)
            out["g4map_candidate_taper3"] = (gj.get("candidates") or {}).get("design + taper 3 % (x 140-180, y 95-125)")
        except Exception:
            pass
    return out


def checks():
    t0 = time.time()
    F, info, C, dfs, x, y, per_layer_M, Fd, per_layer_M_d = build()
    info["content_sha256"] = content_hash(F, info)
    tab = from_build(F, info)
    tabD = from_build(Fd, dict(info, content_sha256="design"))
    nl = info["n_layers"]
    fac, g, X, Y = maps(x, y)
    out = dict(set=GC.SET, info={k: v for k, v in info.items() if k != "fields"}, tolerances=G1_TOL)
    # ---- 0. the DESIGN equals DFG-2B-E's table (float32, every field)
    d0 = dict(table=GC.DFGBE_TABLE.replace(GC.REPO + "/", ""), exists=os.path.exists(GC.DFGBE_TABLE))
    if d0["exists"]:
        z = np.load(GC.DFGBE_TABLE)
        zi = json.loads(str(z["info"]))
        d0["content_sha256"] = zi.get("content_sha256")
        d0["content_is_AM_DFGB1a"] = bool(zi.get("content_sha256") == GC.DFGBE_TABLE_CONTENT)
        eq = {nm: bool(np.array_equal(np.asarray(Fd[nm], np.float32), z[nm])) for nm in fields_of(nl)}
        d0["fields_equal_float32"] = eq
        d0["all_equal"] = bool(all(eq.values()))
        d0["info_match"] = bool(abs(float(zi["a_sum"]) - info["a_sum"]) < 1e-9 and float(zi["x_f"]) == info["x_f"] and float(zi["t_f"]) == info["t_f"]
                                and zi["theta_deg"] == info["theta_deg"] and zi["dir_weights"] == info["dir_weights"] and int(zi["n_layers"]) == nl)
    ok_design = bool(d0.get("all_equal") and d0.get("content_is_AM_DFGB1a") and d0.get("info_match"))
    out["design_equals_DFGB_E"] = dict(d0, ok=ok_design, tag="computed (float32 arrays of the rebuilt design vs DFG-2B-E's npz, every field)")
    # ---- 0b. the generator = design x F_n g exactly (float32), the maps as registered
    comp = []
    for n in range(nl):
        hN = GC.HARMONICS[n]
        Ad = Fd["er%d" % n] + 1j * Fd["ei%d" % n]
        At = tab["er%d" % n].astype(float) + 1j * tab["ei%d" % n].astype(float)
        Ud = Fd["ur%d" % n] + 1j * Fd["ui%d" % n]
        Ut = tab["ur%d" % n].astype(float) + 1j * tab["ui%d" % n].astype(float)
        big = np.abs(Ad) > 1e-3 * float(np.abs(Ad).max())
        bigu = np.abs(Ud) > 1e-3 * float(np.abs(Ud).max())
        rel = np.abs(At[big] / (Ad[big] * fac[n][big]) - 1.0)
        relu = np.abs(Ut[bigu] / (Ud[bigu] * fac[n][bigu]) - 1.0)
        recomputed_bit = True
        for a, b in (("er", "ei"), ("ur", "ui"), ("vr", "vi")):
            zz_ = (Fd["%s%d" % (a, n)] + 1j * Fd["%s%d" % (b, n)]) * fac[n]
            recomputed_bit = recomputed_bit and bool(np.array_equal(tab["%s%d" % (a, n)], np.asarray(zz_.real, np.float32))
                                                     and np.array_equal(tab["%s%d" % (b, n)], np.asarray(zz_.imag, np.float32)))
        ph = np.angle(At[big] * np.conj(Ad[big]))
        comp.append(dict(n=hN, max_rel_dev_eta=float(rel.max()), max_rel_dev_u=float(relu.max()), recomputed_bit_equal=bool(recomputed_bit),
                         phase_min_rad=float(ph.min()), phase_max_rad=float(ph.max()), gain_min=float(np.abs(fac[n]).min()), gain_max=float(np.abs(fac[n]).max()),
                         kk_equal=bool(np.array_equal(tab["kk%d" % n], np.asarray(Fd["kk%d" % n], np.float32))),
                         downstream_x_ge_100_phase_zero=bool(np.all(np.abs(np.angle(fac[n][:, x >= 100.0])) < 1e-15)),
                         inlet_x_le_80_phase=float(np.angle(fac[n][0, int(np.argmin(np.abs(x - 50.0)))]))))
    meas = GC.dfgbe_g2f_phases()
    gm = dict(g_min=float(g.min()), g_max=float(g.max()), g_at_hot_spot_168_108=float(GC.gain(168.0, 108.0)),
              g_inlet_band_all_one=bool(np.all(g[:, x <= 140.0] == 1.0)), g_interior_y_le_75_one=bool(np.all(g[y <= 75.0, :] == 1.0)),
              mx_scaled_g2=bool(np.array_equal(tab["mx"], np.asarray(Fd["mx"] * g ** 2, np.float32)) and
                                np.array_equal(tab["my"], np.asarray(Fd["my"] * g ** 2, np.float32))))
    ok_map = bool(all(r["max_rel_dev_eta"] < G1_TOL["map_rel"] * 10 and r["max_rel_dev_u"] < G1_TOL["map_rel"] * 10 and r["recomputed_bit_equal"]
                      and r["kk_equal"] and r["downstream_x_ge_100_phase_zero"] for r in comp)
                  and abs(comp[2]["inlet_x_le_80_phase"] + GC.PHI5) < 1e-12 and abs(comp[0]["inlet_x_le_80_phase"]) < 1e-15
                  and abs(comp[1]["inlet_x_le_80_phase"]) < 1e-15
                  and abs(gm["g_min"] - (1.0 - GC.TAPER_D)) < 1e-12 and gm["g_max"] == 1.0 and gm["g_inlet_band_all_one"] and gm["g_interior_y_le_75_one"]
                  and gm["mx_scaled_g2"] and bool(np.array_equal(tab["hh"], np.asarray(Fd["hh"], np.float32)))
                  and meas is not None and abs(meas[5] - GC.PHI5_MEAS) < 1e-9 and abs(GC.PHI5 - GC.CAL_SCALE5 * meas[5]) < 1e-9)
    out["calibration_maps"] = dict(per_layer=comp, gain=gm, phi5_rad=GC.PHI5, phi5_from_DFGB_E_judge=(meas or {}).get(5), scale=GC.CAL_SCALE5,
                                   time_advance_s=GC.PHI5 / (2 * math.pi * GC.CAL_N / GC.P_S), cal_rule=GC.CAL_RULE, taper_rule=GC.TAPER_RULE, ok=ok_map,
                                   tag="computed (the stored float32 generator vs the design x F_n g; the maps as registered)")
    # ---- 1. focus: the DESIGN at the focus node (phase 0 = DFG-2B-E's); the generator maps are 1 there (x_f lies beyond the table)
    S = GC.AM_DFGB1_SEA
    per = []
    for n, d in enumerate(dfs):
        i_f = int(np.argmin(np.abs(d.x - GC.X_F)))
        Af = complex(d.complex_amp(np.array([0.0]))[i_f, 0])
        ind = float(np.sum(d.a * d.Ks[i_f] * d.Kr[:, i_f]))
        gen = float(np.sum(d.a))
        per.append(dict(n=GC.HARMONICS[n], x_f_node=float(d.x[i_f]), abs_A=abs(Af), phase_rad_design=float(np.angle(Af)), independent_sum=ind,
                        rel_err=abs(Af) / ind - 1.0, generation_sum=gen, shoal_refr_gain=abs(Af) / gen, plan_amp_per_freq=float(S["amp_per_freq_m"][n]),
                        rel_err_gen_vs_plan=gen / float(S["amp_per_freq_m"][n]) - 1.0))
    ok_focus = bool(all(abs(r["rel_err"]) < G1_TOL["focus_rel"] and abs(r["phase_rad_design"]) < G1_TOL["phase_rad"] and abs(r["x_f_node"] - GC.X_F) < 1e-12
                        and abs(r["rel_err_gen_vs_plan"]) < G1_TOL["focus_rel"] for r in per) and GC.X_F > GC.TABLE_X[1])
    out["focus"] = dict(per_layer=per, total_design_crest_m=float(sum(r["abs_A"] for r in per)), a_sum=C["a_sum"],
                        tag="computed: DirField at the design focus node against the independent component sums (WKB Ks Kr) and the AM-DFGB1 per-frequency "
                            "sums (phase 0); x_f lies beyond the table (the generator maps act only at x <= 214 m)")
    # ---- 2. symmetry about y = 0 (table: V(y = 0) = 0; DirField: eta(+y) = eta(-y), U symmetric, V antisymmetric; the maps are even in y)
    symm = []
    yy = np.array([3.0, 17.5, 41.0, 88.0, 131.0])
    for n, d in enumerate(dfs):
        Ap = d.complex_amp(yy); An = d.complex_amp(-yy)
        Up, Vp = d.complex_vel(yy, depth_avg=False, z=0.0); Un, Vn = d.complex_vel(-yy, depth_avg=False, z=0.0)
        sc = float(np.abs(Ap).max())
        symm.append(dict(n=GC.HARMONICS[n], V_at_y0_max=float(np.hypot(tab["vr%d" % n][0], tab["vi%d" % n][0]).max()),
                         eta_mirror=float(np.abs(Ap - An).max()) / sc, U_mirror=float(np.abs(Up - Un).max()) / sc, V_antisym=float(np.abs(Vp + Vn).max()) / sc))
    sc_u = max(float(np.hypot(tab["ur%d" % n], tab["ui%d" % n]).max()) for n in range(nl))
    set_sym = bool(np.array_equal(np.sort(C["th"]), -np.sort(C["th"])[::-1]) and np.array_equal(C["wd"], C["wd"][::-1]))
    gy0 = bool(np.all(np.abs(GC.gain(x[None, :], np.array([[0.0], [2.0]])) - 1.0) == 0.0))      # the gain is 1 near y = 0 (y <= 75 m): even
    ok_sym = bool(set_sym and gy0 and all(r["V_at_y0_max"] < 1e-6 * sc_u and r["eta_mirror"] < G1_TOL["symmetry"] and r["U_mirror"] < G1_TOL["symmetry"]
                                          and r["V_antisym"] < G1_TOL["symmetry"] for r in symm))
    out["symmetry"] = dict(per_layer=symm, set_symmetric=set_sym, maps_even_near_y0=gy0, tag="computed")
    # ---- 3. continuity (registered DFGB4 rule): design exact; generator exact where the maps are constant; seam / taper strips bounded
    xi = x[2:-2]; yi = y[2:-2]
    fl = xi <= GC.X_TOE - 2.0
    mg = G1_TOL["seam_margin_m"]
    XI, YI = np.meshgrid(xi, yi)
    seam = ((XI >= GC.CAL_X_FULL - mg) & (XI <= GC.CAL_X_ZERO + mg))
    taper = ((XI >= GC.TAPER_X[0] - mg) & (YI >= GC.TAPER_YIN[0] - mg) & (YI <= GC.TAPER_Y[0] + mg))
    vary = seam | taper
    W, tf = band_weight(X, Y)
    Wi = (W * tf)[2:-2, 2:-2]
    gm_frozen = tf                                                           # the frozen walltaper x sdtaper x side factor (on the DESIGN)
    cont = []
    for n in range(nl):
        om = float(info["omega"][n])
        rdc = _cont_resid(tabD, n, om)
        rgc = _cont_resid(tab, n, om, sc_tab=tabD)
        rt_ = np.abs(_cont_resid(tabD, n, om, gm=gm_frozen))                 # the effective band target of the frozen tapers (design table)
        rd_ = np.abs(rdc); rg_ = np.abs(rgc)
        flv = fl[None, :] & vary
        flc = fl[None, :] & ~vary
        rec = dict(n=GC.HARMONICS[n], design_max_rel_flat=float(rd_[:, fl].max()), generator_max_rel_flat_const_maps=float(rg_[flc].max()),
                   generator_max_rel_flat_seam_taper=float(rg_[flv].max()) if flv.any() else 0.0,
                   generator_weighted_max_seam_taper=float((rg_ * Wi)[flv].max()) if flv.any() else 0.0,
                   frozen_tapers_weighted_max=float((rt_ * Wi)[fl[None, :] & (Wi > 0)].max()),
                   max_rel_slope_generator=float(rg_[:, xi >= GC.X_TOE + 2.0].max()), p95_rel_slope_generator=float(np.percentile(rg_[:, xi >= GC.X_TOE + 2.0], 95)))
        # the seam's own added residual (generator - design, complex) weighted, vs the frozen tapers' weighted residual
        add = np.abs(rgc - rdc)
        rec["seam_added_weighted_max"] = float((add * Wi)[flv].max()) if flv.any() else 0.0
        rec["seam_over_frozen_tapers"] = rec["seam_added_weighted_max"] / max(rec["frozen_tapers_weighted_max"], 1e-30)
        j = np.unravel_index(int(np.argmax(np.where(flv, rg_, -1.0))), rg_.shape)
        rec["generator_seam_max_at_xy"] = [float(xi[j[1]]), float(yi[j[0]])]
        cont.append(rec)
    ok_cont = bool(all(r["design_max_rel_flat"] < G1_TOL["continuity_flat"] and r["generator_max_rel_flat_const_maps"] < G1_TOL["continuity_flat"]
                       and r["generator_max_rel_flat_seam_taper"] <= G1_TOL["seam_raw"] and r["seam_over_frozen_tapers"] <= G1_TOL["seam_vs_frozen_tapers"]
                       for r in cont))
    out["continuity"] = dict(per_layer=cont, rule="registered DFGB4 rule: (a) design flat < 5e-3 (= DFG-2B); (b) generator flat < 5e-3 where the maps "
                                                  "are constant (3 m margin to the seam x 80-100 m and the taper x >= 140 m, y 75-125 m); (c) seam / taper "
                                                  "strips: raw <= 0.10 and the seam's added residual weighted by the band weight x target factor <= 0.10 x "
                                                  "the frozen wall / side-wall tapers' weighted residual of the effective band target",
                             slope_note="slope part x >= 162 m = WKB residual, report only", tag="computed")
    # ---- 4. interpolation: bilinear on the 1 m float32 generator table (= the VEX) against an independent 0.5 m DirField x F_n g
    xh = np.union1d(np.arange(0.0, GC.X_FULL_END + 1e-9, 0.5), [float(GC.X_F)])
    _, dfh = dirfields(xh)
    rng = np.random.default_rng(52)
    xq = rng.choice(np.arange(0.5, 213.0, 1.0), 300); yq = rng.choice(np.arange(0.5, 139.0, 1.0), 300); tq = rng.uniform(30.0, 130.0, 300)
    xq = np.concatenate([xq, np.arange(78.5, 102.0, 1.0), np.arange(138.5, 182.0, 2.0)])
    yq = np.concatenate([yq, np.linspace(1.0, 135.0, len(np.arange(78.5, 102.0, 1.0))), np.linspace(96.0, 126.0, len(np.arange(138.5, 182.0, 2.0)))])
    tq = np.concatenate([tq, np.linspace(40.0, 90.0, len(xq) - len(tq))])
    e_np, U_np, V_np = dirwave_np(tab, xq, 50.0 + 0 * xq, yq, tq, 1.0, ret_on=0.0)
    e_ex = np.zeros(len(xq)); U_ex = np.zeros(len(xq)); V_ex = np.zeros(len(xq))
    for n, d in enumerate(dfh):
        ix = np.array([int(np.argmin(np.abs(d.x - v))) for v in xq])
        for q_, (i_, x_, y_, t_) in enumerate(zip(ix, xq, yq, tq)):
            cf = complex(GC.layer_factor(n, np.array(x_), np.array(y_)))
            A = d.complex_amp(np.array([y_]))[i_, 0] * cf
            Uc, Vc = d.complex_vel(np.array([y_]), depth_avg=False, z=0.0)
            ph = np.exp(-1j * d.om * (t_ - GC.T_F))
            e_ex[q_] += float(np.real(A * ph)); U_ex[q_] += float(np.real(Uc[i_, 0] * cf * ph)); V_ex[q_] += float(np.real(Vc[i_, 0] * cf * ph))
    sc_e = float(C["a_sum"])
    out["interpolation"] = dict(n=int(len(xq)), max_rel_eta=float(np.abs(e_np - e_ex).max() / sc_e), max_rel_U=float(np.abs(U_np - U_ex).max() / sc_u),
                                max_rel_V=float(np.abs(V_np - V_ex).max() / sc_u), scale_eta=sc_e, scale_u=sc_u,
                                note="cell centres of the 1 m generator table vs a 0.5 m DirField x F_n g (independent grid and phase integral); 300 random "
                                     "points + the seam x 78.5-101.5 m + the taper x 138.5-180.5 m, y 96-126 m", tag="computed")
    ok_int = bool(max(out["interpolation"]["max_rel_eta"], out["interpolation"]["max_rel_U"], out["interpolation"]["max_rel_V"]) < G1_TOL["interpolation"])
    # ---- 5. vertical profile per layer at table nodes: VEX mirror (own local k_n) vs the DirField complex velocity x F_n g at depth z
    vert = []
    ixs = [int(np.argmin(np.abs(x - v))) for v in (20.0, 90.0, 110.0, 165.0, 190.0, 212.0)]
    jys = [int(np.argmin(np.abs(y - v))) for v in (0.0, 37.0, 101.0, 110.0)]
    for n, d in enumerate(dfs):
        mx_ = 0.0
        for z in (-2.0, -7.0, -12.0):
            Uc, Vc = d.complex_vel(y[jys], depth_avg=False, z=z)
            for i_ in ixs:
                if -z >= d.h[i_]:
                    continue
                for jj, j_ in enumerate(jys):
                    cf = complex(fac[n][j_, i_])
                    for t_ in (41.3, 63.0, 97.7):
                        ph = np.exp(-1j * d.om * (t_ - GC.T_F))
                        Uref = float(np.real(Uc[i_, jj] * cf * ph)); Vref = float(np.real(Vc[i_, jj] * cf * ph))
                        k = float(tab["kk%d" % n][j_, i_]); h = float(tab["hh"][j_, i_])
                        prof = float(TB52.chch(k * (z + h), k * h))
                        U1 = (tab["ur%d" % n][j_, i_] * math.cos(d.om * (t_ - GC.T_F)) + tab["ui%d" % n][j_, i_] * math.sin(d.om * (t_ - GC.T_F))) * prof
                        V1 = (tab["vr%d" % n][j_, i_] * math.cos(d.om * (t_ - GC.T_F)) + tab["vi%d" % n][j_, i_] * math.sin(d.om * (t_ - GC.T_F))) * prof
                        mx_ = max(mx_, abs(U1 - Uref) / sc_u, abs(V1 - Vref) / sc_u)
        vert.append(dict(n=GC.HARMONICS[n], max_rel_err=mx_))
    ok_vert = bool(all(r["max_rel_err"] < G1_TOL["vertical"] for r in vert))
    out["vertical_profile"] = dict(per_layer=vert, tag="computed (float32 table x cosh(k_n (z + h))/cosh(k_n h) vs DirField velocity x F_n g)")
    # ---- 6. zero period-mean mass flux per layer and in total through x = const (as flip52b g52b_table.checks; x 150 / 160 / 190 cross the taper)
    gx, gw = np.polynomial.legendre.leggauss(24)
    P = info["P"]
    ts = GC.T_F + P * np.arange(64) / 64.0
    trap = getattr(np, "trapezoid", None) or np.trapz
    flux = {}
    mx_sum = np.zeros_like(F["mx"])
    for n in range(nl):
        mx_sum += per_layer_M[n][0].T
    sumM_err = float(np.abs(np.asarray(F["mx"], np.float32).astype(float) - mx_sum).max())
    for xq_ in (60.0, 90.0, 110.0, 150.0, 160.0, 190.0):
        i = int(np.argmin(np.abs(x - xq_)))
        row = {}
        for L in [[n] for n in range(nl)] + [list(range(nl))]:
            tabL = dict(tab)
            if len(L) == 1:
                tabL["mx"] = np.asarray(per_layer_M[L[0]][0].T, np.float32).astype(float)
                tabL["my"] = np.asarray(per_layer_M[L[0]][1].T, np.float32).astype(float)
            vals = {}
            for ret in (0.0, 1.0):
                Ms = []
                for t in ts:
                    e, _, _ = dirwave_np(tabL, x[i] + 0 * y, 50.0, y, t, 1.0, ret_on=0.0, layers=L)
                    h = float(tab["hh"][0, i])
                    zt = e[None, :]
                    zz = -h + (zt + h) * (gx[:, None] + 1.0) / 2.0
                    _, U, _ = dirwave_np(tabL, x[i] + 0 * zz, zz, np.broadcast_to(y, zz.shape), t, 1.0, ret_on=ret, layers=L)
                    col = ((zt + h) / 2.0 * (gw[:, None] * U).sum(0))[0]
                    Ms.append(float(trap(col, y)))
                vals[ret] = float(np.mean(Ms))
            key = "n%d" % GC.HARMONICS[L[0]] if len(L) == 1 else "total"
            row[key] = dict(without_return_m3s=vals[0.0], with_return_m3s=vals[1.0], rel=abs(vals[1.0]) / max(abs(vals[0.0]), 1e-30))
        flux["x%g" % xq_] = row
    tot = [row["total"]["rel"] for row in flux.values()]
    ok_flux = bool(all(r["rel"] < G1_TOL["mass_flux_rel"] for row in flux.values() for r in row.values()) and sumM_err < 1e-6)
    out["mean_mass_flux"] = dict(per_x=flux, stored_mx_equals_sum_of_layers_max_abs=sumM_err, max_return_current_mps=float(np.abs(F["mx"]).max()),
                                 total_rel_max=float(max(tot)), rule="every layer and the all-layer total rel < 1e-6 (= the DFG-2B G1 rule; mx, my x g^2)",
                                 tag="computed (numeric depth and time integration of the VEX mirror)")
    # ---- 7. P-periodicity at the G2f gauges and in the seam / taper
    gp = []
    for xg, yg in [(110.0, v) for v in GC.GAUGE_Y] + [(90.0, 50.0), (90.0, 120.0), (165.0, 110.0)]:
        tt = np.arange(30.0, 58.0, 0.37)
        e0, U0, V0 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt, 1.0, ret_on=1.0)
        e1, U1, V1 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt + P, 1.0, ret_on=1.0)
        gp.append(dict(x=xg, y=yg, max_rel=float(np.abs(e1 - e0).max() / sc_e), max_rel_U=float(max(np.abs(U1 - U0).max(), np.abs(V1 - V0).max()) / sc_u)))
    ok_per = bool(all(r["max_rel"] < G1_TOL["periodic_rel"] and r["max_rel_U"] < G1_TOL["periodic_rel"] for r in gp))
    out["periodicity"] = dict(rows=gp, tag="computed (t, t + P)")
    # ---- 8. band steepness of the linear generator target over one period (report) + the design's + the calibrated G4 screen
    kp = GC.kp()
    xin = np.arange(GC.WALL_TAPER, GC.IN_X1 + 0.5, 2.0); yin = np.arange(0.0, GC.W_MAIN - GC.SD_TAPER + 0.5, 2.0)
    xsd = np.arange(0.0, GC.SD_GEN + 0.5, 2.0); ysd = np.arange(GC.SD0, GC.W_MAIN - GC.SD_TAPER + 0.5, 2.0)
    bands = {}
    for nm, tb_ in (("generator", tab), ("design", tabD)):
        bi = bs = 0.0
        for t in GC.T_F + np.arange(-P / 2.0, P / 2.0, 0.5):
            a1, _, _ = dirwave_np(tb_, xin[None, :] + 0 * yin[:, None], 50.0, yin[:, None] + 0 * xin[None, :], t, 1.0, ret_on=0.0)
            b1, _, _ = dirwave_np(tb_, xsd[None, :] + 0 * ysd[:, None], 50.0, ysd[:, None] + 0 * xsd[None, :], t, 1.0, ret_on=0.0)
            bi = max(bi, float(a1.max())); bs = max(bs, float(b1.max()))
        bands[nm] = dict(kp_crest_inlet_lin=kp * bi, kp_crest_side_lin=kp * bs)
    out["band_linear_steepness"] = dict(kp=kp, **bands["generator"], design=bands["design"], G4_max=0.40,
                                        tag="computed (linear; the realised G4 of DFG-2B-E was 0.397 in the side band [measured])")
    out["g4_screen"] = g4_screen(F)
    # ---- 9. energy (Q84): spectral sum a^2 = DM1A's (from DM1A's own cfg); |F_n| = 1; the taper is a local target gain, not the spectrum
    try:
        dm = json.load(open(GC.DM1A_CFG, encoding="utf8"))["dir"]
        s_dm = float(int(dm["n"]) * float(dm["a_j"]) ** 2)
    except Exception:
        s_dm = None
    s_c = float(np.sum(C["a"] ** 2))
    phase_unit = all(bool(np.allclose(np.abs(fac[n]), g, rtol=0, atol=1e-14)) for n in range(nl))
    out["energy"] = dict(sum_a2_m2=s_c, DM1A_sum_a2_from_cfg_m2=s_dm, ratio=(s_c / s_dm) if s_dm else None, phase_factor_unit_modulus=bool(phase_unit),
                         gain_range=[float(g.min()), float(g.max())], components_unchanged=bool(abs(s_c - GC.AM_DFGB1_SEA["sum_a2_m2"]) < 1e-5),
                         ok=bool(s_dm and abs(s_c / s_dm - 1.0) < 1e-9 and phase_unit and abs(s_c - GC.AM_DFGB1_SEA["sum_a2_m2"]) < 1e-5
                                 and abs(float(g.min()) - (1.0 - GC.TAPER_D)) < 1e-12))
    out["linear_refs"] = linear_refs()
    out["ok"] = dict(design_equals_DFGB_E=ok_design, calibration_maps=ok_map, focus=ok_focus, symmetry=ok_sym, continuity=ok_cont,
                     interpolation=ok_int, vertical=ok_vert, zero_mass_flux=ok_flux, periodic=ok_per, layers_le_4=bool(nl <= GC.MAX_LAYERS),
                     table_covers_bands=bool(x[-1] >= GC.SD_SW and y[-1] >= GC.W_MAIN), energy_equals_DM1A=bool(out["energy"]["ok"]))
    out["all_ok"] = bool(all(out["ok"].values()))
    out["gate"] = "G1 numpy table check (plan_DFGB4 A_validity.G1) -> %s" % ("PASS" if out["all_ok"] else "FAIL")
    out["content_sha256"] = info["content_sha256"]
    out["cpu_s"] = round(time.time() - t0, 2)
    return out


def table_record(dry=False):
    """cfg['dir'] block (the npz is written if missing; dry: never written)."""
    p, sha, ch, info = write(dry=dry)
    return dict(set=info["set"], npz=p, npz_sha256=sha, content_sha256=ch, P=info["P"], harmonics=info["harmonics"], n_layers=info["n_layers"],
                omega=info["omega"], T=info["T"], k=info["k"], freq_weights=info["freq_weights"], theta_deg=info["theta_deg"],
                dir_weights=info["dir_weights"], dspec=info["dspec"], a_sum=info["a_sum"], a_max_component=info["a_max_component"],
                amp_per_freq=info["amp_per_freq"], n_components=info["n_components"], x_f=info["x_f"], h_f=info["h_f"], h_f_design=info["h_f_design"],
                t_f=info["t_f"], foci=info["foci"], grid=dict(x=[info["x0"], info["x1"]], y=[info["y0"], info["y1"]], d=info["dx"]), fields=info["fields"],
                bed=info["bed"], calibration=info["calibration"], taper=info["taper"], linear_refs=linear_refs())


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
        print("table", p, "sha256", sha[:16], "content", ch[:16], "layers %d components %d a_max %.5f" % (info["n_layers"], info["n_components"],
                                                                                                         info["a_max_component"]))
    elif a[0] == "check":
        o = checks()
        p = GC.TABLE_CHECK
        GC.jdump(o, p)
        print(json.dumps(GC.clean({k: o[k] for k in ("ok", "all_ok", "cpu_s", "content_sha256")})), "->", p)
        print(json.dumps(GC.clean(dict(design=o["design_equals_DFGB_E"]["ok"], maps=o["calibration_maps"], continuity=o["continuity"]["per_layer"],
                                       interp=o["interpolation"], bands=o["band_linear_steepness"], g4=o["g4_screen"],
                                       flux_total=o["mean_mass_flux"]["total_rel_max"], energy=o["energy"])))[:6000])
    elif a[0] == "energy":
        print(json.dumps(GC.clean(energy_in_tank()), ensure_ascii=False, indent=1))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
