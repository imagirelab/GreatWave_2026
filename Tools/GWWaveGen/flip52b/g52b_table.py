# -*- coding: utf-8 -*-
"""FLIP52B plan DFG-2B: the N-layer (one layer per frequency) complex-amplitude inflow table over the D19B bed (WKB per component: shoaling +
refraction, as the option-D tables), and its numpy checks = gate G1 (numpy only: py -3.10 -B, and importable from hython).
2026-10-17 written new (Claude). Read only (imported): flip52/g52_table (the N-layer npz format, the numpy mirror of the band VEX dirwave_np /
relax_np / load / content_hash, used unchanged: they read hh and kk<n> per node, so a depth-varying table needs no new VEX), flip50/g50_dirfield
(DirField: the WKB field that made every option-D table). No flip45-flip52 file is edited.

The sea: for each harmonic n (T 9.33 / 7 / 5.6 s) a DirField with the plan E X2 directions and weights wd_j and the amplitude sum a_sum wf_n at
the generation depth h0 19 m, phases 0 at the focus (x_f, 0) at t = t_f (+ 28 m): A_n(x, y) = sum_j A_nj(x) exp(i (Phi_nj(x) + k_y,nj y)).
Layer n stores er<n>, ei<n> (eta_n), ur<n>, ui<n>, vr<n>, vi<n> (surface velocity, local cosh profile), kk<n> = k_n(h(x)) (its own local
wavenumber); shared hh = h(x), mx, my = -sum_n Re(A_n conj(U_n q_n)) / (2 h^2), q_n = tanh(k_n h)/k_n (zero period-mean mass flux, per layer).
Convention as flip52: eta(t) = sum_n er<n> cos(2 pi n (t - t_f)/P) + ei<n> sin(...). Grid x 0-214 m, y 0-140 m, 1 m (the bands: inlet 0-100 m,
side band 95-140 m to x 210.25 m). The DirField grid runs to x 300 m so that it contains x_f (its phase reference); the table keeps x <= 214 m.

usage (py -3.10 -B):
  g52b_table.py write          Unity/Build/FLIP52B/tables/DFGB_P28_xf<x_f>_W140_<hash12>.npz (if not there) and print its path
  g52b_table.py check          G1 numpy checks -> Unity/Build/FLIP52B/plan/table_check_DFGB.json
2026-10-18 (Claude) AM-DFGB1: with G52B_SEA=E (g52b_common) the same code writes the energy-matched table DFGBE_P28_xf<x_f>_W140_<hash12>.npz
(info set DFG2BE, + amendment / energy keys) and its check plan/table_check_DFGBE.json against the AM-DFGB1 sea numbers (g52b_common.plan_sea);
G52B_SEA unset: names, info and content hash exactly as frozen.
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52b_common as GC           # noqa: E402
import g52_table as TB52           # noqa: E402  read only (npz format, VEX mirror)
import g50_dirfield as DF          # noqa: E402  read only (WKB DirField)

dirwave_np = TB52.dirwave_np
relax_np = TB52.relax_np
load = TB52.load
from_build = TB52.from_build
content_hash = TB52.content_hash
fields_of = TB52.fields_of
G1_TOL = dict(focus_rel=1e-3, phase_rad=1e-6, continuity_flat=5e-3, continuity_slope_report=0.10, interpolation=0.02, vertical=1e-4,
              mass_flux_rel=1e-6, symmetry=1e-9, periodic_rel=1e-9)


def full_grid():
    return np.union1d(np.arange(GC.TABLE_X[0], GC.X_FULL_END + 1e-9, GC.TABLE_DX), [float(GC.X_F)])


def dirfields(x=None):
    """one DirField per harmonic (WKB over D19B), phases referenced to (x_f, 0)."""
    C = GC.components()
    x = full_grid() if x is None else np.asarray(x, float)
    out = []
    for n, h_ in enumerate(GC.HARMONICS):
        T = GC.P_S / float(h_)
        out.append(DF.DirField(T, C["th"], C["wd"], C["a_sum"] * float(C["wf"][n]), x, GC.BED_DF, GC.X_F))
    return C, out


def build():
    """arrays (ny, nx) float64 and the info dict."""
    C, dfs = dirfields()
    y = np.arange(GC.TABLE_Y[0], GC.TABLE_Y[1] + 1e-9, GC.TABLE_DX)
    m = dfs[0].x <= GC.TABLE_X[1] + 1e-9
    x = dfs[0].x[m]
    if not np.allclose(np.diff(x), GC.TABLE_DX) or abs(x[0] - GC.TABLE_X[0]) > 1e-12 or abs(x[-1] - GC.TABLE_X[1]) > 1e-9:
        raise ValueError("table x grid is not uniform 0..214 m")
    nl = len(dfs)
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
    info = dict(set=GC.SET, plan="DFG-2B", plan_frozen=GC.PLAN_REL, P=float(GC.P_S), harmonics=[int(v) for v in GC.HARMONICS], n_layers=int(nl),
                omega=[float(d.om) for d in dfs], T=[float(d.T) for d in dfs], k=[float(d.k0) for d in dfs], kh0=[float(d.k0 * GC.H0) for d in dfs],
                h=float(GC.H0), h0=float(GC.H0), bed=GC.BED_DF, freq_weights=[float(v) for v in C["wf"]], theta_deg=[float(v) for v in C["th"]],
                dir_weights=[float(v) for v in C["wd"]], dspec=list(GC.DSPEC), a_sum=float(C["a_sum"]), a_max_component=float(C["a"].max()),
                amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]], sum_a2=float(np.sum(C["a"] ** 2)), n_components=int(C["a"].size),
                x_f=float(GC.X_F), h_f=float(GC.h_of(GC.X_F)), t_f=float(GC.T_F), foci=[float(v) for v in GC.FOCI],
                x0=float(x[0]), dx=float(GC.TABLE_DX), nx=int(len(x)), y0=float(y[0]), dy=float(GC.TABLE_DX), ny=int(len(y)),
                x1=float(x[-1]), y1=float(y[-1]), fields=fields_of(nl), dirfield_grid=[float(dfs[0].x[0]), float(dfs[0].x[-1])],
                convention="eta(t) = sum_n er<n> cos(2 pi h_n (t - t_f)/P) + ei<n> sin(...); U, V likewise at z = 0, times cosh(k_n(z'+h))/cosh(k_n h) "
                           "with z' stretched on the total eta and k_n = kk<n> (local); return current mx, my (m/s, depth uniform) x g^2 when ret_on 1",
                source="Tools/GWWaveGen/flip52b/g52b_table.py build() on g50_dirfield.DirField per harmonic (WKB shoaling + refraction over D19B)")
    if GC.SEA == "E":                      # AM-DFGB1 only (the frozen info, and so its content hash, stays as it was)
        info.update(amendment=GC.AMENDMENT_ID, sea_variant="E", energy_scale=float(GC.E_SCALE), a_sum_frozen=float(GC.A_SUM_FROZEN),
                    sum_a2_DM1A=float(GC.DM1A_SUM_A2), energy_rule="every component x energy_scale: sum a^2 at h0 19 m = DM1A's (equal energy density)")
    return F, info, C, dfs, x, y, per_layer_M


def table_path(ch):
    return (GC.TABLE_DIR + "/%s_P%s_xf%s_W%s_%s.npz" % (GC.TAG, GC.tag(GC.P_S), GC.tag(GC.X_F), GC.tag(GC.W_MAIN), ch[:12])).replace("\\", "/")


def write(dry=False):
    F, info, _, _, _, _, _ = build()
    ch = content_hash(F, info)
    p = table_path(ch)
    info["content_sha256"] = ch
    if dry:
        return p, (GC.sha256_file(p) if os.path.exists(p) else None), ch, info
    os.makedirs(GC.TABLE_DIR, exist_ok=True)
    if not os.path.exists(p):
        np.savez(p, info=np.array(json.dumps(info, default=float)), **{nm: np.asarray(F[nm], np.float32) for nm in info["fields"]})
    return p, GC.sha256_file(p), ch, info


# ======================================================================== linear references (gates and reports)
def linear_refs():
    """[computed] per-frequency complex amplitudes at the G2f gauges (x 110 m, y 0.5/20/40/60/80 m), the report gauges, the focal design
    crest (DirField at x_f), the c_in line x 110 m over one period."""
    C, dfs = dirfields()
    g2 = {}
    for yg in GC.GAUGE_Y:
        row = {}
        for n, d in enumerate(dfs):
            A = d.complex_amp(np.array([yg]))
            a = complex(np.interp(110.0, d.x, A[:, 0].real) + 1j * np.interp(110.0, d.x, A[:, 0].imag))
            row["n%d" % GC.HARMONICS[n]] = [a.real, a.imag]
        g2["y%g" % yg] = row
    rep = {}
    for xg, yg in ((128.0, 0.5), (160.0, 0.5), (200.0, 0.5), (240.0, 0.5), (256.0, 0.5), (GC.X_F, 0.5)):
        row = {}
        for n, d in enumerate(dfs):
            A = d.complex_amp(np.array([yg]))
            a = complex(np.interp(xg, d.x, A[:, 0].real) + 1j * np.interp(xg, d.x, A[:, 0].imag))
            row["n%d" % GC.HARMONICS[n]] = [a.real, a.imag]
        rep["x%g_y%g" % (xg, yg)] = row
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
    return dict(G2f_gauges=dict(x=110.0, y=list(GC.GAUGE_Y), A_n=g2, convention="A = er + i ei of eta_n = Re(A e^{-i w_n (t - t_f)})"),
                report_gauges=rep, design_crest_xf_m=design, a_sum=C["a_sum"], amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]],
                a_max_component=float(C["a"].max()), c_in_line_x110_lin_m=cin, gain_lin_over_c_in=design / cin if cin > 0 else None,
                kp=kp, kp_asum=kp * C["a_sum"], harmonics=list(GC.HARMONICS), omega=[float(d.om) for d in dfs],
                tags="computed (linear WKB DirField per harmonic on D19B)")


# ======================================================================== G1: numpy checks
def _deriv4(f, axis, d):
    f = np.moveaxis(f, axis, 0)
    out = (-f[4:] + 8 * f[3:-1] - 8 * f[1:-3] + f[:-4]) / (12.0 * d)
    return np.moveaxis(out, 0, axis)


def checks():
    t0 = time.time()
    F, info, C, dfs, x, y, per_layer_M = build()
    info["content_sha256"] = content_hash(F, info)
    tab = from_build(F, info)
    nl = info["n_layers"]
    out = dict(set=GC.SET, info={k: v for k, v in info.items() if k != "fields"}, tolerances=G1_TOL)
    # ---- 1. focus (on the DirField grid, which contains x_f; the table stops at 214 m): per layer |A_n(x_f, 0)| = the independent sum
    #         sum_j a_nj Ks_n(x_f) Kr_nj(x_f), phase 0; the frozen plan's a_sum / per-frequency amounts at the generation depth
    PL = dict(sea=GC.plan_sea()) if os.path.exists(GC.PLAN) else None        # AM-DFGB1: the E numbers when G52B_SEA=E
    per = []
    for n, d in enumerate(dfs):
        i_f = int(np.argmin(np.abs(d.x - GC.X_F)))
        Af = complex(d.complex_amp(np.array([0.0]))[i_f, 0])
        ind = float(np.sum(d.a * d.Ks[i_f] * d.Kr[:, i_f]))
        gen = float(np.sum(d.a))
        row = dict(n=GC.HARMONICS[n], x_f_node=float(d.x[i_f]), abs_A=abs(Af), phase_rad=float(np.angle(Af)), independent_sum=ind, rel_err=abs(Af) / ind - 1.0,
                   generation_sum=gen, shoal_refr_gain=abs(Af) / gen)
        if PL:
            pa = float(PL["sea"]["amp_per_freq_m"][n])
            row["plan_amp_per_freq"] = pa; row["rel_err_gen_vs_plan"] = gen / pa - 1.0
        per.append(row)
    ok_focus = bool(all(abs(r["rel_err"]) < G1_TOL["focus_rel"] and abs(r["phase_rad"]) < G1_TOL["phase_rad"] and abs(r["x_f_node"] - GC.X_F) < 1e-12
                        and (("rel_err_gen_vs_plan" not in r) or abs(r["rel_err_gen_vs_plan"]) < G1_TOL["focus_rel"]) for r in per))
    out["focus"] = dict(per_layer=per, total_design_crest_m=float(sum(r["abs_A"] for r in per)), a_sum=C["a_sum"],
                        tag="computed: DirField at the focus node against the independent component sums (WKB Ks Kr) and the plan's per-frequency sums")
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
    # ---- 3. continuity per layer: -i w A + d/dx(U q) + d/dy(V q) on the float32 table; flat part x <= 158 m (exact plane waves) judged,
    #         the slope part x 162-212 m (WKB, O(slope) error) reported
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
    # ---- 4. interpolation: bilinear on the 1 m float32 table (= the VEX) against an independent 0.5 m DirField at cell centres
    xh = np.union1d(np.arange(0.0, GC.X_FULL_END + 1e-9, 0.5), [float(GC.X_F)])
    _, dfh = dirfields(xh)
    rng = np.random.default_rng(52)
    xq = rng.choice(np.arange(0.5, 213.0, 1.0), 300); yq = rng.choice(np.arange(0.5, 139.0, 1.0), 300); tq = rng.uniform(30.0, 130.0, 300)
    e_np, U_np, V_np = dirwave_np(tab, xq, 50.0 + 0 * xq, yq, tq, 1.0, ret_on=0.0)
    e_ex = np.zeros(len(xq)); U_ex = np.zeros(len(xq)); V_ex = np.zeros(len(xq))
    for n, d in enumerate(dfh):
        ix = np.array([int(np.argmin(np.abs(d.x - v))) for v in xq])
        for q_, (i_, y_, t_) in enumerate(zip(ix, yq, tq)):
            A = d.complex_amp(np.array([y_]))[i_, 0]
            Uc, Vc = d.complex_vel(np.array([y_]), depth_avg=False, z=0.0)
            ph = np.exp(-1j * d.om * (t_ - GC.T_F))
            e_ex[q_] += float(np.real(A * ph)); U_ex[q_] += float(np.real(Uc[i_, 0] * ph)); V_ex[q_] += float(np.real(Vc[i_, 0] * ph))
    sc_e = float(C["a_sum"])
    out["interpolation"] = dict(n=int(len(xq)), max_rel_eta=float(np.abs(e_np - e_ex).max() / sc_e), max_rel_U=float(np.abs(U_np - U_ex).max() / sc_u),
                                max_rel_V=float(np.abs(V_np - V_ex).max() / sc_u), scale_eta=sc_e, scale_u=sc_u,
                                note="cell centres of the 1 m table vs a 0.5 m DirField (independent grid and phase integral)", tag="computed")
    ok_int = bool(max(out["interpolation"]["max_rel_eta"], out["interpolation"]["max_rel_U"], out["interpolation"]["max_rel_V"]) < G1_TOL["interpolation"])
    # ---- 5. vertical profile per layer at table nodes: VEX mirror (own local k_n) vs the DirField complex velocity at depth z
    vert = []
    ixs = [int(np.argmin(np.abs(x - v))) for v in (20.0, 110.0, 165.0, 190.0, 212.0)]
    jys = [int(np.argmin(np.abs(y - v))) for v in (0.0, 37.0, 101.0)]
    for n, d in enumerate(dfs):
        mx_ = 0.0
        for z in (-2.0, -7.0, -12.0):
            Uc, Vc = d.complex_vel(y[jys], depth_avg=False, z=z)
            for i_ in ixs:
                if -z >= d.h[i_]:
                    continue
                for jj, j_ in enumerate(jys):
                    for t_ in (41.3, 63.0, 97.7):
                        ph = np.exp(-1j * d.om * (t_ - GC.T_F))
                        Uref = float(np.real(Uc[i_, jj] * ph)); Vref = float(np.real(Vc[i_, jj] * ph))
                        # mirror with this layer only and no stretching influence: z' = z when eta of the layer is used -> evaluate at eta-free depth
                        k = float(tab["kk%d" % n][j_, i_]); h = float(tab["hh"][j_, i_])
                        prof = float(TB52.chch(k * (z + h), k * h))
                        U1 = (tab["ur%d" % n][j_, i_] * math.cos(d.om * (t_ - GC.T_F)) + tab["ui%d" % n][j_, i_] * math.sin(d.om * (t_ - GC.T_F))) * prof
                        V1 = (tab["vr%d" % n][j_, i_] * math.cos(d.om * (t_ - GC.T_F)) + tab["vi%d" % n][j_, i_] * math.sin(d.om * (t_ - GC.T_F))) * prof
                        mx_ = max(mx_, abs(U1 - Uref) / sc_u, abs(V1 - Vref) / sc_u)
        vert.append(dict(n=GC.HARMONICS[n], max_rel_err=mx_))
    ok_vert = bool(all(r["max_rel_err"] < G1_TOL["vertical"] for r in vert))
    out["vertical_profile"] = dict(per_layer=vert, tag="computed (float32 table x cosh(k_n (z + h))/cosh(k_n h) vs DirField velocity at depth z)")
    # ---- 6. zero period-mean mass flux per layer and in total through x = const (as flip52 g52_table.checks)
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
    ok_flux = bool(all(r["rel"] < G1_TOL["mass_flux_rel"] for row in flux.values() for r in row.values()) and sumM_err < 1e-6)
    out["mean_mass_flux"] = dict(per_x=flux, stored_mx_equals_sum_of_layers_max_abs=sumM_err, max_return_current_mps=float(np.abs(F["mx"]).max()),
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
    # ---- 8. band steepness of the linear target over one period (report; G4 watches the realised field)
    kp = GC.kp()
    bi = bs = 0.0
    xin = np.arange(GC.WALL_TAPER, GC.IN_X1 + 0.5, 2.0); yin = np.arange(0.0, GC.W_MAIN - GC.SD_TAPER + 0.5, 2.0)
    xsd = np.arange(0.0, GC.SD_GEN + 0.5, 2.0); ysd = np.arange(GC.SD0, GC.W_MAIN - GC.SD_TAPER + 0.5, 2.0)
    for t in GC.T_F + np.arange(-P / 2.0, P / 2.0, 0.5):
        a1, _, _ = dirwave_np(tab, xin[None, :] + 0 * yin[:, None], 50.0, yin[:, None] + 0 * xin[None, :], t, 1.0, ret_on=0.0)
        b1, _, _ = dirwave_np(tab, xsd[None, :] + 0 * ysd[:, None], 50.0, ysd[:, None] + 0 * xsd[None, :], t, 1.0, ret_on=0.0)
        bi = max(bi, float(a1.max())); bs = max(bs, float(b1.max()))
    out["band_linear_steepness"] = dict(kp=kp, kp_crest_inlet_lin=kp * bi, kp_crest_side_lin=kp * bs, G4_max=0.40, tag="computed (linear)")
    out["linear_refs"] = linear_refs()
    out["ok"] = dict(focus=ok_focus, symmetry=ok_sym, continuity_flat=ok_cont, interpolation=ok_int, vertical=ok_vert, zero_mass_flux=ok_flux,
                     periodic=ok_per, layers_le_4=bool(nl <= GC.MAX_LAYERS), table_covers_bands=bool(x[-1] >= GC.SD_SW and y[-1] >= GC.W_MAIN))
    out["all_ok"] = bool(all(out["ok"].values()))
    out["gate"] = "G1 numpy table check (plan_DFGB gates.A_validity.G1) -> %s" % ("PASS" if out["all_ok"] else "FAIL")
    out["content_sha256"] = info["content_sha256"]
    out["cpu_s"] = round(time.time() - t0, 2)
    return out


def table_record(dry=False):
    """cfg['dir'] block (the npz is written if missing; dry: never written)."""
    p, sha, ch, info = write(dry=dry)
    return dict(set=info["set"], npz=p, npz_sha256=sha, content_sha256=ch, P=info["P"], harmonics=info["harmonics"], n_layers=info["n_layers"],
                omega=info["omega"], T=info["T"], k=info["k"], freq_weights=info["freq_weights"], theta_deg=info["theta_deg"],
                dir_weights=info["dir_weights"], dspec=info["dspec"], a_sum=info["a_sum"], a_max_component=info["a_max_component"],
                amp_per_freq=info["amp_per_freq"], n_components=info["n_components"], x_f=info["x_f"], h_f=info["h_f"], t_f=info["t_f"],
                foci=info["foci"], grid=dict(x=[info["x0"], info["x1"]], y=[info["y0"], info["y1"]], d=info["dx"]), fields=info["fields"],
                bed=info["bed"], linear_refs=linear_refs())


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
        print(json.dumps(GC.clean({k: o[k] for k in ("ok", "all_ok", "cpu_s")})), "->", p)
        print(json.dumps(GC.clean(dict(focus=o["focus"], continuity=o["continuity"], interpolation=o["interpolation"], vertical=o["vertical_profile"],
                                       bands=o["band_linear_steepness"])))[:2500])
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
