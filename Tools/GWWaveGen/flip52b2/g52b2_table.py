# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3: the N-layer complex-amplitude inflow table (DFG-2B-E's WKB table over the D19B beach, every layer n multiplied by the
calibration factor exp(-i phi_n)) and its numpy checks = gate G1 (numpy only: py -3.10 -B, and importable from hython).
2026-10-18 written new (Claude) by adapting flip52b/g52b_table.py (DFG-2B / DFG-2B-E, FROZEN, not edited). Read only (imported): flip52/g52_table
(the N-layer npz format, the numpy mirror of the band VEX dirwave_np / relax_np / load / content_hash, used unchanged), flip50/g50_dirfield
(DirField). Read only (compared): DFG-2B-E's table Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz and DM1A's input table.

The DESIGN sea = DFG-2B-E's, bit for bit: for each harmonic n (T 9.33 / 7 / 5.6 s) a DirField with the plan E X2 directions and weights wd_j and
the energy-matched amplitude sum a_sum wf_n (a_sum 10.640186 m) at the generation depth h0 19 m, phases 0 at the design focus (272.25, 0) at
t = 63 (+ 28 m) s over the D19B beach (the DirField bed; x <= 235.25 m equal to the DFGB3 bed, the table keeps x <= 214 m).
The GENERATOR table = design x exp(-i phi_n) per layer (round-2 calibration (b): phi = DFG-2B-E's measured G2f phase errors n3 -0.060788,
n4 +0.279111, n5 +0.513994 rad): er<n> + i ei<n>, ur<n> + i ui<n>, vr<n> + i vi<n> are rotated; kk<n>, hh and the return current mx, my (a
period mean of A conj(U), invariant under a common phase) are the design's. |factor| = 1: sum a^2 (= DM1A's 1.336153 m^2) and the period-mean
in-tank power are unchanged.
The LINEAR REFERENCES for the gates and reports (G2f gauges, report gauges, design crest, c_in) are the DESIGN's (= DFG-2B-E's): the calibration
aims at a realised wave equal to the design, so G2f measures realised vs design (the generator content is recorded beside it as *_table).
Convention as flip52: eta(t) = sum_n er<n> cos(2 pi n (t - t_f)/P) + ei<n> sin(...) = sum_n Re(A_n e^{-i w_n (t - t_f)}).

usage (py -3.10 -B):
  g52b2_table.py write          Unity/Build/FLIP52B2/tables/DFGB3_P28_xf272p25_W140_<hash12>.npz (if not there) and print its path
  g52b2_table.py check          G1 numpy checks -> Unity/Build/FLIP52B2/plan/table_check_DFGB3.json
  g52b2_table.py energy         the Q84 energy numbers (spectral and in-tank), json to stdout
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52b2_common as GC          # noqa: E402
import g52_table as TB52           # noqa: E402  read only (npz format, VEX mirror)
import g50_dirfield as DF          # noqa: E402  read only (WKB DirField)

dirwave_np = TB52.dirwave_np
relax_np = TB52.relax_np
load = TB52.load
from_build = TB52.from_build
content_hash = TB52.content_hash
fields_of = TB52.fields_of
G1_TOL = dict(focus_rel=1e-3, phase_rad=1e-6, continuity_flat=5e-3, continuity_slope_report=0.10, interpolation=0.02, vertical=1e-4,
              mass_flux_rel=1e-6, symmetry=1e-9, periodic_rel=1e-9, comp_phase_rad=1e-5, comp_abs_rel=1e-5)
RHO = 1000.0
AM_DFGB1B = dict(DM1A=dict(inlet_var=2.316, P_in_MW=42.87, P_full_MW=36.44), DFGB_E=dict(inlet_var=0.295, P_in_MW=10.05, P_full_MW=4.39))


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
    """the DESIGN arrays (ny, nx) float64 = DFG-2B-E's table content (before the float32 cast), the per-layer mass-flux pieces."""
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


def compensate(Fd):
    """the generator arrays: each layer's complex fields x exp(-i phi_n); kk, hh, mx, my unchanged (mx, my are period means of A conj U)."""
    F = dict(Fd)
    for n in range(len(GC.HARMONICS)):
        c = GC.phase_factor(n)
        for a, b in (("er", "ei"), ("ur", "ui"), ("vr", "vi")):
            z = (Fd["%s%d" % (a, n)] + 1j * Fd["%s%d" % (b, n)]) * c
            F["%s%d" % (a, n)] = np.ascontiguousarray(z.real)
            F["%s%d" % (b, n)] = np.ascontiguousarray(z.imag)
    return F


def build():
    """generator arrays (ny, nx) float64 and the info dict."""
    Fd, C, dfs, x, y, per_layer_M = build_design()
    F = compensate(Fd)
    nl = len(dfs)
    info = dict(set=GC.SET, plan="DFGB3", plan_frozen=GC.PLAN_REL, P=float(GC.P_S), harmonics=[int(v) for v in GC.HARMONICS], n_layers=int(nl),
                omega=[float(d.om) for d in dfs], T=[float(d.T) for d in dfs], k=[float(d.k0) for d in dfs], kh0=[float(d.k0 * GC.H0) for d in dfs],
                h=float(GC.H0), h0=float(GC.H0), bed=GC.BED_DF_DESIGN, freq_weights=[float(v) for v in C["wf"]], theta_deg=[float(v) for v in C["th"]],
                dir_weights=[float(v) for v in C["wd"]], dspec=list(GC.DSPEC), a_sum=float(C["a_sum"]), a_max_component=float(C["a"].max()),
                amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]], sum_a2=float(np.sum(C["a"] ** 2)), n_components=int(C["a"].size),
                x_f=float(GC.X_F), h_f_design=float(GC.H0 - (GC.X_F - GC.X_TOE) / GC.SLOPE_S), h_f=float(GC.h_of(GC.X_F)), t_f=float(GC.T_F),
                foci=[float(v) for v in GC.FOCI],
                x0=float(x[0]), dx=float(GC.TABLE_DX), nx=int(len(x)), y0=float(y[0]), dy=float(GC.TABLE_DX), ny=int(len(y)),
                x1=float(x[-1]), y1=float(y[-1]), fields=fields_of(nl), dirfield_grid=[float(dfs[0].x[0]), float(dfs[0].x[-1])],
                energy_scale=float(GC.E_SCALE), a_sum_frozen=float(GC.A_SUM_FROZEN), sum_a2_DM1A=float(GC.DM1A_SUM_A2),
                phase_comp_rad={str(k): float(v) for k, v in GC.PHI_COMP.items()}, phase_comp_rule=GC.PHI_RULE,
                design_table="Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz (DFG-2B-E; content %s)" % GC.DFGBE_TABLE_CONTENT[:16],
                convention="eta(t) = sum_n er<n> cos(2 pi h_n (t - t_f)/P) + ei<n> sin(...); U, V likewise at z = 0, times cosh(k_n(z'+h))/cosh(k_n h) "
                           "with z' stretched on the total eta and k_n = kk<n> (local); return current mx, my (m/s, depth uniform) x g^2 when ret_on 1; "
                           "layer n of this GENERATOR table = the design x exp(-i phi_n)",
                source="Tools/GWWaveGen/flip52b2/g52b2_table.py build(): g50_dirfield.DirField per harmonic (WKB over D19B, = DFG-2B-E) x exp(-i phi_n)")
    return F, info, C, dfs, x, y, per_layer_M, Fd


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
            a *= GC.phase_factor(n)
        row["n%d" % GC.HARMONICS[n]] = [a.real, a.imag]
    return row


def linear_refs():
    """[computed] per-frequency complex amplitudes of the DESIGN (= DFG-2B-E's table) at the G2f gauges (x 110 m, y 0.5/20/40/60/80 m), the
    report gauges, the focal design crest (DirField at x_f), the c_in line x 110 m over one period; beside them the generator content (_table)."""
    C, dfs = dirfields()
    g2 = {"y%g" % yg: _amp_at(dfs, 110.0, yg) for yg in GC.GAUGE_Y}
    g2t = {"y%g" % yg: _amp_at(dfs, 110.0, yg, factor=True) for yg in GC.GAUGE_Y}
    rep = {}
    for xg, yg in ((128.0, 0.5), (160.0, 0.5), (200.0, 0.5), (228.5, 0.5), (235.25, 0.5), (240.0, 0.5), (251.75, 0.5)):
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
                                "target (= DFG-2B-E's table at the gauges): G2f compares the realised wave with it (calibration (b))"),
                G2f_gauges_table=dict(x=110.0, y=list(GC.GAUGE_Y), A_n=g2t, note="the generator table content at the gauges (design x exp(-i phi_n)), report"),
                report_gauges=rep, design_crest_xf_m=design, a_sum=C["a_sum"], amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]],
                a_max_component=float(C["a"].max()), c_in_line_x110_lin_m=cin, gain_lin_over_c_in=design / cin if cin > 0 else None,
                kp=kp, kp_asum=kp * C["a_sum"], harmonics=list(GC.HARMONICS), omega=[float(d.om) for d in dfs], phase_comp_rad=dict(GC.PHI_COMP),
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
    DFGB3's generator table, DFG-2B-E's table and DM1A's table, all on the D19B layout (x 100 m, y 95 m, side band generating to 180.25 m);
    the DM1A / DFG-2B-E numbers reproduce AM-DFGB1b (check)."""
    F, info, *_ = build()
    nl = info["n_layers"]
    f32 = lambda v: np.asarray(v, np.float32)
    L3 = [((f32(F["er%d" % n]) + 1j * f32(F["ei%d" % n])).astype(complex), (f32(F["ur%d" % n]) + 1j * f32(F["ui%d" % n])).astype(complex),
           (f32(F["vr%d" % n]) + 1j * f32(F["vi%d" % n])).astype(complex), f32(F["kk%d" % n]).astype(float)) for n in range(nl)]
    lay = (GC.IN_X1, GC.SD0, GC.SD_GEN)
    out = dict(rule=tank_energy.__doc__.split("[computed] ")[1][:500], tag="[computed] numpy on the linear input tables")
    out["DFGB3"] = tank_energy(L3, f32(F["hh"]).astype(float), *lay)
    for nm, p in (("DM1A", GC.DM1A_TABLE), ("DFGB_E", GC.DFGBE_TABLE)):
        if os.path.exists(p):
            L, h, _ = _layers_npz(p)
            out[nm] = tank_energy(L, h, *lay)
            out[nm]["table"] = p.replace(GC.REPO + "/", "")
    D = out.get("DM1A")
    if D:
        for nm in ("DFGB3", "DFGB_E"):
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
        out["DFGB3_equals_DFGB_E_power"] = bool(abs(out["DFGB3"]["power_into_interior_MW"] / out["DFGB_E"]["power_into_interior_MW"] - 1.0) < 1e-5
                                               and abs(out["DFGB3"]["inlet_band_mean_variance_m2"] / out["DFGB_E"]["inlet_band_mean_variance_m2"] - 1.0) < 1e-5)
    C = GC.components()
    out["spectral"] = dict(sum_a2_m2=float(np.sum(C["a"] ** 2)), DM1A_sum_a2_m2=GC.DM1A_SUM_A2, ratio=float(np.sum(C["a"] ** 2)) / GC.DM1A_SUM_A2,
                           E_Jm2=0.5 * RHO * GC.G * float(np.sum(C["a"] ** 2)), Hm0_spectral_m=4.0 * math.sqrt(0.5 * float(np.sum(C["a"] ** 2))))
    E = out["DFGB3"]
    out["statement_en"] = ("equal SPECTRAL energy (Q84): sum a^2 = %.6f m^2 = DM1A's %.6f m^2 at the generation depth h0 19 m (energy density "
                           "0.5 rho g sum a^2 = %.0f J/m^2, spectral Hm0 %.2f m); inside the tank the incoming linear waves carry less: inlet-band "
                           "surface variance %.3f x DM1A's (Hm0-equivalent %.2f m vs %.2f m) and the power entering the interior %.3f x DM1A's "
                           "(%.2f vs %.2f MW per half tank) [computed, the AM-DFGB1b rule on the generator table; = DFG-2B-E's: the phase-only "
                           "calibration changes neither]"
                           % (out["spectral"]["sum_a2_m2"], GC.DM1A_SUM_A2, out["spectral"]["E_Jm2"], out["spectral"]["Hm0_spectral_m"],
                              E.get("inlet_variance_over_DM1A", float("nan")), E["inlet_band_Hm0_equiv_m"], (D or {}).get("inlet_band_Hm0_equiv_m", float("nan")),
                              E.get("interior_power_over_DM1A", float("nan")), E["power_into_interior_MW"], (D or {}).get("power_into_interior_MW", float("nan"))))
    return out


# ======================================================================== G1: numpy checks
def _deriv4(f, axis, d):
    f = np.moveaxis(f, axis, 0)
    out = (-f[4:] + 8 * f[3:-1] - 8 * f[1:-3] + f[:-4]) / (12.0 * d)
    return np.moveaxis(out, 0, axis)


def checks():
    t0 = time.time()
    F, info, C, dfs, x, y, per_layer_M, Fd = build()
    info["content_sha256"] = content_hash(F, info)
    tab = from_build(F, info)
    nl = info["n_layers"]
    out = dict(set=GC.SET, info={k: v for k, v in info.items() if k != "fields"}, tolerances=G1_TOL)
    # ---- 0. the DESIGN equals DFG-2B-E's table (float32, every field), and the generator = design x exp(-i phi_n)
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
    comp = []
    for n in range(nl):
        hN = GC.HARMONICS[n]
        Ad = Fd["er%d" % n] + 1j * Fd["ei%d" % n]
        At = tab["er%d" % n].astype(float) + 1j * tab["ei%d" % n].astype(float)
        Ud = Fd["ur%d" % n] + 1j * Fd["ui%d" % n]
        Ut = tab["ur%d" % n].astype(float) + 1j * tab["ui%d" % n].astype(float)
        big = np.abs(Ad) > 1e-3 * float(np.abs(Ad).max())
        bigu = np.abs(Ud) > 1e-3 * float(np.abs(Ud).max())
        ph = np.angle(At[big] * np.conj(Ad[big]))
        phu = np.angle(Ut[bigu] * np.conj(Ud[bigu]))
        comp.append(dict(n=hN, phi_rad=GC.PHI_COMP[hN], phase_eta_mean_rad=float(np.mean(ph)), phase_eta_maxdev_rad=float(np.abs(ph + GC.PHI_COMP[hN]).max()),
                         phase_u_maxdev_rad=float(np.abs(phu + GC.PHI_COMP[hN]).max()),
                         abs_rel_max=float(np.abs(np.abs(At[big]) / np.abs(Ad[big]) - 1.0).max()),
                         kk_equal=bool(np.array_equal(tab["kk%d" % n], np.asarray(Fd["kk%d" % n], np.float32)))))
    meas = GC.dfgbe_g2f_phases()
    ok_comp = bool(all(r["phase_eta_maxdev_rad"] < G1_TOL["comp_phase_rad"] and r["phase_u_maxdev_rad"] < G1_TOL["comp_phase_rad"]
                       and r["abs_rel_max"] < G1_TOL["comp_abs_rel"] and r["kk_equal"] for r in comp)
                   and bool(np.array_equal(tab["hh"], np.asarray(Fd["hh"], np.float32))) and bool(np.array_equal(tab["mx"], np.asarray(Fd["mx"], np.float32)))
                   and bool(np.array_equal(tab["my"], np.asarray(Fd["my"], np.float32)))
                   and meas is not None and all(abs(meas[k] - v) < 1e-9 for k, v in GC.PHI_COMP.items()))
    out["phase_compensation"] = dict(per_layer=comp, phi_from_DFGB_E_judge=meas, rule=GC.PHI_RULE, ok=ok_comp,
                                     tag="computed (the stored float32 generator vs the design: phase = -phi_n, |A| equal, kk / hh / mx / my equal)")
    # ---- 1. focus: the DESIGN at the focus node (phase 0 = DFG-2B-E's) and the generator's intended offsets (-phi_n)
    S = GC.AM_DFGB1_SEA
    per = []
    for n, d in enumerate(dfs):
        i_f = int(np.argmin(np.abs(d.x - GC.X_F)))
        Af = complex(d.complex_amp(np.array([0.0]))[i_f, 0])
        ind = float(np.sum(d.a * d.Ks[i_f] * d.Kr[:, i_f]))
        gen = float(np.sum(d.a))
        Ag = Af * GC.phase_factor(n)
        per.append(dict(n=GC.HARMONICS[n], x_f_node=float(d.x[i_f]), abs_A=abs(Af), phase_rad_design=float(np.angle(Af)), independent_sum=ind,
                        rel_err=abs(Af) / ind - 1.0, generation_sum=gen, shoal_refr_gain=abs(Af) / gen, plan_amp_per_freq=float(S["amp_per_freq_m"][n]),
                        rel_err_gen_vs_plan=gen / float(S["amp_per_freq_m"][n]) - 1.0, phase_rad_generator=float(np.angle(Ag)),
                        intended_offset_rad=-GC.PHI_COMP[GC.HARMONICS[n]]))
    ok_focus = bool(all(abs(r["rel_err"]) < G1_TOL["focus_rel"] and abs(r["phase_rad_design"]) < G1_TOL["phase_rad"] and abs(r["x_f_node"] - GC.X_F) < 1e-12
                        and abs(r["rel_err_gen_vs_plan"]) < G1_TOL["focus_rel"]
                        and abs(r["phase_rad_generator"] - r["intended_offset_rad"]) < G1_TOL["phase_rad"] for r in per))
    out["focus"] = dict(per_layer=per, total_design_crest_m=float(sum(r["abs_A"] for r in per)), a_sum=C["a_sum"],
                        tag="computed: DirField at the design focus node against the independent component sums (WKB Ks Kr) and the AM-DFGB1 per-frequency "
                            "sums (phase 0), and the generator's intended phase offsets -phi_n")
    # ---- 2. symmetry about y = 0 (table: V(y = 0) = 0; DirField: eta(+y) = eta(-y), U symmetric, V antisymmetric)
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
    ok_sym = bool(set_sym and all(r["V_at_y0_max"] < 1e-6 * sc_u and r["eta_mirror"] < G1_TOL["symmetry"] and r["U_mirror"] < G1_TOL["symmetry"]
                                  and r["V_antisym"] < G1_TOL["symmetry"] for r in symm))
    out["symmetry"] = dict(per_layer=symm, set_symmetric=set_sym, tag="computed")
    # ---- 3. continuity per layer on the float32 GENERATOR table: flat part x <= 158 m judged, slope part x 162-212 m reported
    cont = []
    for n in range(nl):
        om = float(info["omega"][n])
        k = tab["kk%d" % n]; h = tab["hh"]
        q = np.tanh(k * h) / k
        A = tab["er%d" % n] + 1j * tab["ei%d" % n]
        U = (tab["ur%d" % n] + 1j * tab["ui%d" % n]) * q
        V = (tab["vr%d" % n] + 1j * tab["vi%d" % n]) * q
        res = -1j * om * A[2:-2, 2:-2] + _deriv4(U, 1, GC.TABLE_DX)[2:-2, :] + _deriv4(V, 0, GC.TABLE_DX)[:, 2:-2]
        sc = om * float(np.abs(A).max())
        xi = x[2:-2]
        fl = xi <= GC.X_TOE - 2.0; sl = xi >= GC.X_TOE + 2.0
        cont.append(dict(n=GC.HARMONICS[n], max_rel_flat=float(np.abs(res[:, fl]).max() / sc), max_rel_slope=float(np.abs(res[:, sl]).max() / sc),
                         p95_rel_slope=float(np.percentile(np.abs(res[:, sl]), 95) / sc)))
    ok_cont = bool(all(r["max_rel_flat"] < G1_TOL["continuity_flat"] for r in cont))
    out["continuity"] = dict(per_layer=cont, note="flat part judged (exact); slope part = WKB residual, report only (limit for a warning %.2f)"
                                                  % G1_TOL["continuity_slope_report"],
                             slope_warning=bool(any(r["max_rel_slope"] > G1_TOL["continuity_slope_report"] for r in cont)), tag="computed")
    # ---- 4. interpolation: bilinear on the 1 m float32 generator table (= the VEX) against an independent 0.5 m DirField x exp(-i phi_n)
    xh = np.union1d(np.arange(0.0, GC.X_FULL_END + 1e-9, 0.5), [float(GC.X_F)])
    _, dfh = dirfields(xh)
    rng = np.random.default_rng(52)
    xq = rng.choice(np.arange(0.5, 213.0, 1.0), 300); yq = rng.choice(np.arange(0.5, 139.0, 1.0), 300); tq = rng.uniform(30.0, 130.0, 300)
    e_np, U_np, V_np = dirwave_np(tab, xq, 50.0 + 0 * xq, yq, tq, 1.0, ret_on=0.0)
    e_ex = np.zeros(len(xq)); U_ex = np.zeros(len(xq)); V_ex = np.zeros(len(xq))
    for n, d in enumerate(dfh):
        cf = GC.phase_factor(n)
        ix = np.array([int(np.argmin(np.abs(d.x - v))) for v in xq])
        for q_, (i_, y_, t_) in enumerate(zip(ix, yq, tq)):
            A = d.complex_amp(np.array([y_]))[i_, 0] * cf
            Uc, Vc = d.complex_vel(np.array([y_]), depth_avg=False, z=0.0)
            ph = np.exp(-1j * d.om * (t_ - GC.T_F))
            e_ex[q_] += float(np.real(A * ph)); U_ex[q_] += float(np.real(Uc[i_, 0] * cf * ph)); V_ex[q_] += float(np.real(Vc[i_, 0] * cf * ph))
    sc_e = float(C["a_sum"])
    out["interpolation"] = dict(n=int(len(xq)), max_rel_eta=float(np.abs(e_np - e_ex).max() / sc_e), max_rel_U=float(np.abs(U_np - U_ex).max() / sc_u),
                                max_rel_V=float(np.abs(V_np - V_ex).max() / sc_u), scale_eta=sc_e, scale_u=sc_u,
                                note="cell centres of the 1 m generator table vs a 0.5 m DirField x exp(-i phi_n) (independent grid and phase integral)",
                                tag="computed")
    ok_int = bool(max(out["interpolation"]["max_rel_eta"], out["interpolation"]["max_rel_U"], out["interpolation"]["max_rel_V"]) < G1_TOL["interpolation"])
    # ---- 5. vertical profile per layer at table nodes: VEX mirror (own local k_n) vs the DirField complex velocity x exp(-i phi_n) at depth z
    vert = []
    ixs = [int(np.argmin(np.abs(x - v))) for v in (20.0, 110.0, 165.0, 190.0, 212.0)]
    jys = [int(np.argmin(np.abs(y - v))) for v in (0.0, 37.0, 101.0)]
    for n, d in enumerate(dfs):
        cf = GC.phase_factor(n)
        mx_ = 0.0
        for z in (-2.0, -7.0, -12.0):
            Uc, Vc = d.complex_vel(y[jys], depth_avg=False, z=z)
            for i_ in ixs:
                if -z >= d.h[i_]:
                    continue
                for jj, j_ in enumerate(jys):
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
    out["vertical_profile"] = dict(per_layer=vert, tag="computed (float32 table x cosh(k_n (z + h))/cosh(k_n h) vs DirField velocity x exp(-i phi_n))")
    # ---- 6. zero period-mean mass flux per layer and in total through x = const (as flip52b g52b_table.checks)
    gx, gw = np.polynomial.legendre.leggauss(24)
    P = info["P"]
    ts = GC.T_F + P * np.arange(64) / 64.0
    trap = getattr(np, "trapezoid", None) or np.trapz
    flux = {}
    mx_sum = np.zeros_like(F["mx"])
    for n in range(nl):
        mx_sum += per_layer_M[n][0].T
    sumM_err = float(np.abs(np.asarray(F["mx"], np.float32).astype(float) - mx_sum).max())
    for xq_ in (60.0, 110.0, 150.0, 190.0):
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
                                 total_rel_max=float(max(tot)), rule="every layer and the all-layer total rel < 1e-6 (= the DFG-2B G1 rule, unchanged)",
                                 tag="computed (numeric depth and time integration of the VEX mirror)")
    # ---- 7. P-periodicity at the G2f gauges
    gp = []
    for xg, yg in [(110.0, v) for v in GC.GAUGE_Y]:
        tt = np.arange(30.0, 58.0, 0.37)
        e0, U0, V0 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt, 1.0, ret_on=1.0)
        e1, U1, V1 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt + P, 1.0, ret_on=1.0)
        gp.append(dict(x=xg, y=yg, max_rel=float(np.abs(e1 - e0).max() / sc_e), max_rel_U=float(max(np.abs(U1 - U0).max(), np.abs(V1 - V0).max()) / sc_u)))
    ok_per = bool(all(r["max_rel"] < G1_TOL["periodic_rel"] and r["max_rel_U"] < G1_TOL["periodic_rel"] for r in gp))
    out["periodicity"] = dict(rows=gp, tag="computed (t, t + P)")
    # ---- 8. band steepness of the linear generator target over one period (report; G4 watches the realised field) + the design's for comparison
    kp = GC.kp()
    tabD = from_build(Fd, dict(info, content_sha256="design"))
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
    # ---- 9. energy (Q84): spectral sum a^2 = DM1A's (from DM1A's own cfg), unchanged by |factor| = 1
    try:
        dm = json.load(open(GC.DM1A_CFG, encoding="utf8"))["dir"]
        s_dm = float(int(dm["n"]) * float(dm["a_j"]) ** 2)
    except Exception:
        s_dm = None
    s_c = float(np.sum(C["a"] ** 2))
    amp_eq = all(abs(float(np.abs(Fd["er%d" % n] + 1j * Fd["ei%d" % n]).max()) - float(np.abs(F["er%d" % n] + 1j * F["ei%d" % n]).max())) < 1e-12
                 for n in range(nl))
    out["energy"] = dict(sum_a2_m2=s_c, DM1A_sum_a2_from_cfg_m2=s_dm, ratio=(s_c / s_dm) if s_dm else None, amplitude_unchanged_by_factor=bool(amp_eq),
                         ok=bool(s_dm and abs(s_c / s_dm - 1.0) < 1e-9 and amp_eq and abs(s_c - GC.AM_DFGB1_SEA["sum_a2_m2"]) < 1e-5))
    out["linear_refs"] = linear_refs()
    out["ok"] = dict(design_equals_DFGB_E=ok_design, phase_compensation=ok_comp, focus=ok_focus, symmetry=ok_sym, continuity_flat=ok_cont,
                     interpolation=ok_int, vertical=ok_vert, zero_mass_flux=ok_flux, periodic=ok_per, layers_le_4=bool(nl <= GC.MAX_LAYERS),
                     table_covers_bands=bool(x[-1] >= GC.SD_SW and y[-1] >= GC.W_MAIN), energy_equals_DM1A=bool(out["energy"]["ok"]))
    out["all_ok"] = bool(all(out["ok"].values()))
    out["gate"] = "G1 numpy table check (plan_DFGB3 A_validity.G1) -> %s" % ("PASS" if out["all_ok"] else "FAIL")
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
                bed=info["bed"], phase_comp_rad=info["phase_comp_rad"], phase_comp_rule=info["phase_comp_rule"], linear_refs=linear_refs())


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
        print(json.dumps(GC.clean(dict(design=o["design_equals_DFGB_E"], comp=o["phase_compensation"]["per_layer"], focus=o["focus"]["per_layer"],
                                       bands=o["band_linear_steepness"], flux_total=o["mean_mass_flux"]["total_rel_max"], energy=o["energy"])))[:4000])
    elif a[0] == "energy":
        print(json.dumps(GC.clean(energy_in_tank()), ensure_ascii=False, indent=1))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
