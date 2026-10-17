# -*- coding: utf-8 -*-
"""FLIP52S2 plan DFG-S-E140: the N-layer (one layer per frequency) complex-amplitude inflow table over the DFG-S step (WKB per component:
Snell refraction + shoaling, DirField kind 'shelf'), its numpy checks = gate G1, and the in-tank energy of the linear input (Q84 honesty)
(numpy only: py -3.10 -B, and importable from hython).
2026-10-18 written new (Claude) by adapting flip52s/g52s_table.py (DFG-S, frozen, not edited). Read only (imported): flip52/g52_table (the N-layer
npz format, the numpy mirror of the band VEX dirwave_np / relax_np / load / content_hash, used unchanged), flip50/g50_dirfield (DirField).

The sea: for each harmonic n (T 9.33 / 7 / 5.6 s) a DirField with the plan E X2 directions and weights wd_j and the amplitude sum a_sum wf_n at
the generation depth h0 20 m, a_sum = 10.640186 m = DFG-S's x 1.680585 (ENERGY-MATCHED, user Q84: sum a^2 = DM1A's 1.336153 m^2; the AM-DFGB1
sea), over the DFG-S step (flat 20 m to x 108 m, 1:3 to x 150 m, 6 m shelf), phases 0 at the focus (x_f 145, 0) at t = t_f (+ 28 m), t_f 48 s.
The table itself is DFG-S's table x 1.680585 on the wider grid y 0-140 m (the DirField is linear in a; t_f enters only through the VEX dir_tf).
Layer n stores er<n>, ei<n> (eta_n), ur<n>, ui<n>, vr<n>, vi<n> (surface velocity, local cosh profile), kk<n> = k_n(h(x)); shared hh = h(x),
mx, my = -sum_n Re(A_n conj(U_n q_n)) / (2 h^2), q_n = tanh(k_n h)/k_n (zero period-mean mass flux, per layer).
Convention as flip52: eta(t) = sum_n er<n> cos(2 pi n (t - t_f)/P) + ei<n> sin(...). Grid x 0-214 m, y 0-140 m, 1 m (the bands: inlet 0-50 m,
side band 110-140 m to x 210 m).

usage (py -3.10 -B):
  g52s2_table.py write          Unity/Build/FLIP52S2/tables/DFGS2E_P28_xf145_W140_<hash12>.npz (if not there) and print its path
  g52s2_table.py check          G1 numpy checks -> Unity/Build/FLIP52S2/plan/table_check_DFGS2.json
  g52s2_table.py energy         the in-tank energy of the linear input vs DM1A (json to stdout; the plan freezes it)
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")                     # another hython may share the machine: keep numpy modest
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52s2_common as GC           # noqa: E402
import g52_table as TB52           # noqa: E402  read only (npz format, VEX mirror)
import g50_dirfield as DF          # noqa: E402  read only (WKB DirField)

dirwave_np = TB52.dirwave_np
relax_np = TB52.relax_np
load = TB52.load
from_build = TB52.from_build
content_hash = TB52.content_hash
fields_of = TB52.fields_of
G1_TOL = dict(focus_rel=1e-3, phase_rad=1e-6, continuity_flat=5e-3, continuity_face_report=0.15, interpolation=0.02, vertical=1e-4,
              mass_flux_rel=1e-6, mass_flux_total_rel=1e-3, symmetry=1e-9, periodic_rel=1e-9)
# mass_flux_total_rel: the all-layer sum through x = const in the stretched-depth VEX mirror carries a higher-order (eta^3 and up) residual of
# the stretched profile at the energy-matched amplitude (1e-4 at x 190 m on the shelf, 3e-6 at x 145 m [computed]; DFG-S 1e-8); each layer
# (the quantity the return current cancels exactly) is still judged at 1e-6 [chosen 2026-10-18 before any FLIP52S2 run]


def full_grid():
    return np.union1d(np.arange(GC.TABLE_X[0], GC.TABLE_X[1] + 1e-9, GC.TABLE_DX), [float(GC.X_F)])


def dirfields(x=None):
    """one DirField per harmonic (WKB over the step), phases referenced to (x_f, 0)."""
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
    info = dict(set=GC.SET, plan="DFG-S-E140", plan_frozen=GC.PLAN_REL, P=float(GC.P_S), harmonics=[int(v) for v in GC.HARMONICS], n_layers=int(nl),
                omega=[float(d.om) for d in dfs], T=[float(d.T) for d in dfs], k=[float(d.k0) for d in dfs], kh0=[float(d.k0 * GC.H0) for d in dfs],
                h=float(GC.H0), h0=float(GC.H0), bed=GC.BED_DF, freq_weights=[float(v) for v in C["wf"]], theta_deg=[float(v) for v in C["th"]],
                dir_weights=[float(v) for v in C["wd"]], dspec=list(GC.DSPEC), a_sum=float(C["a_sum"]), a_max_component=float(C["a"].max()),
                amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]], sum_a2=float(np.sum(C["a"] ** 2)), n_components=int(C["a"].size),
                x_f=float(GC.X_F), h_f=float(GC.h_of(GC.X_F)), t_f=float(GC.T_F), foci=[float(v) for v in GC.FOCI],
                x0=float(x[0]), dx=float(GC.TABLE_DX), nx=int(len(x)), y0=float(y[0]), dy=float(GC.TABLE_DX), ny=int(len(y)),
                x1=float(x[-1]), y1=float(y[-1]), fields=fields_of(nl), dirfield_grid=[float(dfs[0].x[0]), float(dfs[0].x[-1])],
                convention="eta(t) = sum_n er<n> cos(2 pi h_n (t - t_f)/P) + ei<n> sin(...); U, V likewise at z = 0, times cosh(k_n(z'+h))/cosh(k_n h) "
                           "with z' stretched on the total eta and k_n = kk<n> (local); return current mx, my (m/s, depth uniform) x g^2 when ret_on 1",
                source="Tools/GWWaveGen/flip52s2/g52s2_table.py build() on g50_dirfield.DirField per harmonic (WKB Snell refraction + shoaling over "
                       "the step: flat 20 m to x 108 m, 1:3 to x 150 m, 6 m shelf), a_sum = DFG-S x %.6f (energy-matched, Q84), y 0-%g m" % (GC.E_SCALE, GC.W_MAIN))
    return F, info, C, dfs, x, y, per_layer_M


def table_path(ch):
    return (GC.TABLE_DIR + "/DFGS2E_P%s_xf%s_W%s_%s.npz" % (GC.tag(GC.P_S), GC.tag(GC.X_F), GC.tag(GC.W_MAIN), ch[:12])).replace("\\", "/")


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
def _amp_at(d, xg, yg):
    A = d.complex_amp(np.array([yg]))
    return complex(np.interp(xg, d.x, A[:, 0].real) + 1j * np.interp(xg, d.x, A[:, 0].imag))


def linear_refs():
    """[computed] per-frequency complex amplitudes at the G2f gauges (x 60 m, y 0.5/15/30/45/60 m), the report gauges, the focal design
    crest (DirField at x_f), the c_in line x 60 m over one period (|y| <= 65 m)."""
    C, dfs = dirfields()
    g2 = {}
    for yg in GC.GAUGE_Y:
        g2["y%g" % yg] = {"n%d" % GC.HARMONICS[n]: [a.real, a.imag] for n, a in ((n, _amp_at(d, 60.0, yg)) for n, d in enumerate(dfs))}
    rep = {}
    for xg, yg in ((100.0, 0.5), (127.5, 0.5), (GC.X_F, 0.5), (150.0, 0.5), (190.0, 0.5), (200.0, 0.5), (190.0, 30.0), (200.0, 30.0)):
        rep["x%g_y%g" % (xg, yg)] = {"n%d" % GC.HARMONICS[n]: [a.real, a.imag] for n, a in ((n, _amp_at(d, xg, yg)) for n, d in enumerate(dfs))}
    i_f = int(np.argmin(np.abs(dfs[0].x - GC.X_F)))
    design = float(sum(np.abs(d.complex_amp(np.array([0.0]))[i_f, 0]) for d in dfs))
    yl = np.arange(0.0, GC.INTERIOR_Y + 1e-9, 1.0)
    i60 = int(np.argmin(np.abs(dfs[0].x - 60.0)))
    A60 = [d.complex_amp(yl)[i60] for d in dfs]
    cin = 0.0
    for t in GC.T_F + np.arange(-GC.P_S / 2.0, GC.P_S / 2.0 - 1e-9, 0.125):
        e = sum(np.real(A * np.exp(-1j * d.om * (t - GC.T_F))) for A, d in zip(A60, dfs))
        cin = max(cin, float(e.max()))
    kp = GC.kp()
    return dict(G2f_gauges=dict(x=60.0, y=list(GC.GAUGE_Y), A_n=g2, convention="A = er + i ei of eta_n = Re(A e^{-i w_n (t - t_f)})"),
                report_gauges=rep, design_crest_xf_m=design, design_crest_m=design, a_sum=C["a_sum"],
                amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]], a_max_component=float(C["a"].max()), c_in_line_x60_lin_m=cin,
                gain_lin_over_c_in=design / cin if cin > 0 else None, kp=kp, kp_asum=kp * C["a_sum"], harmonics=list(GC.HARMONICS),
                omega=[float(d.om) for d in dfs], tags="computed (linear WKB DirField per harmonic over the DFG-S step, energy-matched a_sum)")


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
    # ---- 1. focus: per layer |A_n(x_f, 0)| = the independent sum sum_j a_nj Ks_n(x_f) Kr_nj(x_f), phase 0; the plan's per-frequency sums
    PL = GC.plan() if os.path.exists(GC.PLAN) else None
    per = []
    for n, d in enumerate(dfs):
        i_f = int(np.argmin(np.abs(d.x - GC.X_F)))
        Af = complex(d.complex_amp(np.array([0.0]))[i_f, 0])
        ind = float(np.sum(d.a * d.Ks[i_f] * d.Kr[:, i_f]))
        gen = float(np.sum(d.a))
        row = dict(n=GC.HARMONICS[n], x_f_node=float(d.x[i_f]), h_f=float(d.h[i_f]), abs_A=abs(Af), phase_rad=float(np.angle(Af)), independent_sum=ind,
                   rel_err=abs(Af) / ind - 1.0, generation_sum=gen, shoal_refr_gain=abs(Af) / gen, Ks=float(d.Ks[i_f]),
                   Kr_range=[float(d.Kr[:, i_f].min()), float(d.Kr[:, i_f].max())])
        if PL:
            pa = float(PL["sea"]["amp_per_freq_m"][n])
            row["plan_amp_per_freq"] = pa; row["rel_err_gen_vs_plan"] = gen / pa - 1.0
        per.append(row)
    ok_focus = bool(all(abs(r["rel_err"]) < G1_TOL["focus_rel"] and abs(r["phase_rad"]) < G1_TOL["phase_rad"] and abs(r["x_f_node"] - GC.X_F) < 1e-12
                        and (("rel_err_gen_vs_plan" not in r) or abs(r["rel_err_gen_vs_plan"]) < G1_TOL["focus_rel"]) for r in per))
    out["focus"] = dict(per_layer=per, total_design_crest_m=float(sum(r["abs_A"] for r in per)), a_sum=C["a_sum"],
                        tag="computed: DirField at the focus node against the independent component sums (WKB Ks Kr) and the plan's per-frequency sums")
    # ---- 1b. the flat part equals DFG-2's exact plane-wave amplitudes (|A_nj| = a_nj, k = k(20 m)) and the shelf part is constant
    i_fl = int(np.argmin(np.abs(dfs[0].x - 60.0))); i_sh = int(np.argmin(np.abs(dfs[0].x - 180.0)))
    flat_ok = all(np.allclose(d.Aj[:, i_fl], d.a, rtol=1e-12, atol=0) and abs(d.k[i_fl] - d.k0) < 1e-12 for d in dfs)
    shelf_const = all(np.allclose(d.Aj[:, i_sh], d.Aj[:, int(np.argmin(np.abs(d.x - 200.0)))], rtol=1e-12, atol=0) for d in dfs)
    out["flat_and_shelf"] = dict(flat_equals_DFG2_amplitudes=bool(flat_ok), shelf_amplitudes_constant=bool(shelf_const),
                                 shelf_k=[float(d.k[i_sh]) for d in dfs], shelf_Ks=[float(d.Ks[i_sh]) for d in dfs],
                                 shelf_theta_deg_max=[float(np.degrees(np.arcsin(np.max(np.abs(d.ky)) / d.k[i_sh]))) for d in dfs],
                                 tag="computed (Snell: k_y conserved; on the shelf the crossing lobes turn from +-60 deg toward the normal)")
    # ---- 2. symmetry about y = 0
    symm = []
    yy = np.array([3.0, 17.5, 41.0, 69.0, 93.0, 111.0, 133.0])
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
    # ---- 3. continuity per layer: -i w A + d/dx(U q) + d/dy(V q) on the float32 table; the flat part x <= 106 m and the shelf x >= 152 m
    #         (exact plane waves at constant depth) are judged, the 1:3 face x 110-148 m (WKB on a steep face) is reported
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
        fl = xi <= GC.X_TOE - 2.0; shf = xi >= GC.X_EDGE + 2.0; fc = (xi >= GC.X_TOE + 2.0) & (xi <= GC.X_EDGE - 2.0)
        cont.append(dict(n=GC.HARMONICS[n], max_rel_flat=float(np.abs(res[:, fl]).max() / sc), max_rel_shelf=float(np.abs(res[:, shf]).max() / sc),
                         max_rel_face=float(np.abs(res[:, fc]).max() / sc), p95_rel_face=float(np.percentile(np.abs(res[:, fc]), 95) / sc)))
    ok_cont = bool(all(r["max_rel_flat"] < G1_TOL["continuity_flat"] and r["max_rel_shelf"] < G1_TOL["continuity_flat"] for r in cont))
    out["continuity"] = dict(per_layer=cont, note="flat and shelf parts judged (exact plane waves at constant depth); the 1:3 face = WKB residual, "
                                                  "report only (warning above %.2f)" % G1_TOL["continuity_face_report"],
                             face_warning=bool(any(r["max_rel_face"] > G1_TOL["continuity_face_report"] for r in cont)), tag="computed")
    # ---- 4. interpolation: bilinear on the 1 m float32 table (= the VEX) against an independent 0.5 m DirField at cell centres
    xh = np.union1d(np.arange(0.0, GC.TABLE_X[1] + 1e-9, 0.5), [float(GC.X_F)])
    _, dfh = dirfields(xh)
    rng = np.random.default_rng(52)
    xq = rng.choice(np.arange(0.5, 213.0, 1.0), 300); yq = rng.choice(np.arange(0.5, GC.W_MAIN - 1.0, 1.0), 300); tq = rng.uniform(30.0, 110.0, 300)
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
    ixs = [int(np.argmin(np.abs(x - v))) for v in (20.0, 110.0, 125.0, 140.0, 165.0, 205.0)]
    jys = [int(np.argmin(np.abs(y - v))) for v in (0.0, 37.0, 81.0, 121.0)]
    for n, d in enumerate(dfs):
        mx_ = 0.0
        for z in (-2.0, -5.0, -7.0, -12.0):
            Uc, Vc = d.complex_vel(y[jys], depth_avg=False, z=z)
            for i_ in ixs:
                if -z >= d.h[i_]:
                    continue
                for jj, j_ in enumerate(jys):
                    for t_ in (46.3, 48.0, 102.7):
                        ph = np.exp(-1j * d.om * (t_ - GC.T_F))
                        Uref = float(np.real(Uc[i_, jj] * ph)); Vref = float(np.real(Vc[i_, jj] * ph))
                        k = float(tab["kk%d" % n][j_, i_]); h = float(tab["hh"][j_, i_])
                        prof = float(TB52.chch(k * (z + h), k * h))
                        U1 = (tab["ur%d" % n][j_, i_] * math.cos(d.om * (t_ - GC.T_F)) + tab["ui%d" % n][j_, i_] * math.sin(d.om * (t_ - GC.T_F))) * prof
                        V1 = (tab["vr%d" % n][j_, i_] * math.cos(d.om * (t_ - GC.T_F)) + tab["vi%d" % n][j_, i_] * math.sin(d.om * (t_ - GC.T_F))) * prof
                        mx_ = max(mx_, abs(U1 - Uref) / sc_u, abs(V1 - Vref) / sc_u)
        vert.append(dict(n=GC.HARMONICS[n], max_rel_err=mx_))
    ok_vert = bool(all(r["max_rel_err"] < G1_TOL["vertical"] for r in vert))
    out["vertical_profile"] = dict(per_layer=vert, tag="computed (float32 table x cosh(k_n (z + h))/cosh(k_n h) vs DirField velocity at depth z)")
    # ---- 6. zero period-mean mass flux per layer and in total through x = const (flat, face, shelf)
    gx, gw = np.polynomial.legendre.leggauss(24)
    P = info["P"]
    ts = GC.T_F + P * np.arange(64) / 64.0
    trap = getattr(np, "trapezoid", None) or np.trapz
    flux = {}
    mx_sum = np.zeros_like(F["mx"])
    for n in range(nl):
        mx_sum += per_layer_M[n][0].T
    sumM_err = float(np.abs(np.asarray(F["mx"], np.float32).astype(float) - mx_sum).max())
    for xq_ in (60.0, 120.0, 145.0, 190.0):
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
    ok_flux = bool(all(r["rel"] < (G1_TOL["mass_flux_total_rel"] if k == "total" else G1_TOL["mass_flux_rel"]) for row in flux.values()
                       for k, r in row.items()) and sumM_err < 1e-6)
    out["mean_mass_flux"] = dict(per_x=flux, stored_mx_equals_sum_of_layers_max_abs=sumM_err, max_return_current_mps=float(np.abs(F["mx"]).max()),
                                 rule="per layer rel < %g; the all-layer total rel < %g (higher-order residual of the stretched profile at the "
                                      "energy-matched amplitude)" % (G1_TOL["mass_flux_rel"], G1_TOL["mass_flux_total_rel"]),
                                 tag="computed (numeric depth and time integration of the VEX mirror)")
    # ---- 7. P-periodicity at the G2f gauges
    gp = []
    for xg, yg in [(60.0, v) for v in GC.GAUGE_Y]:
        tt = np.arange(30.0, 58.0, 0.37)
        e0, U0, V0 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt, 1.0, ret_on=1.0)
        e1, U1, V1 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt + P, 1.0, ret_on=1.0)
        gp.append(dict(x=xg, y=yg, max_rel=float(np.abs(e1 - e0).max() / sc_e), max_rel_U=float(max(np.abs(U1 - U0).max(), np.abs(V1 - V0).max()) / sc_u)))
    ok_per = bool(all(r["max_rel"] < G1_TOL["periodic_rel"] and r["max_rel_U"] < G1_TOL["periodic_rel"] for r in gp))
    out["periodicity"] = dict(rows=gp, tag="computed (t, t + P)")
    # ---- 8. band steepness of the linear target over one period (report; G4 watches the realised field): inlet band, side-band core
    #         (y 70-92.5 m), the outer-wall taper strip (y > 92.5 m), deep kp and the local k(h(x)) at T 7 s
    kp = GC.kp()
    xin = np.arange(GC.WALL_TAPER, GC.IN_X1 + 0.5, 2.0); yin = np.arange(0.0, GC.W_MAIN + 0.5, 2.0)
    xsd = np.arange(0.0, GC.SD_GEN + 0.5, 2.0); ysd = np.arange(GC.SD0, GC.SD_CORE_Y1 + 1e-9, 2.0); ywl = np.arange(GC.SD_CORE_Y1 + 1.0, GC.W_MAIN + 1e-9, 1.0)
    kloc = GC.kdisp(2 * math.pi / GC.TP, GC.step_depth(xsd))
    bi = bs = bw = bl = 0.0
    for t in GC.T_F + np.arange(-P / 2.0, P / 2.0, 0.5):
        a1, _, _ = dirwave_np(tab, xin[None, :] + 0 * yin[:, None], 50.0, yin[:, None] + 0 * xin[None, :], t, 1.0, ret_on=0.0)
        b1, _, _ = dirwave_np(tab, xsd[None, :] + 0 * ysd[:, None], 50.0, ysd[:, None] + 0 * xsd[None, :], t, 1.0, ret_on=0.0)
        c1, _, _ = dirwave_np(tab, xsd[None, :] + 0 * ywl[:, None], 50.0, ywl[:, None] + 0 * xsd[None, :], t, 1.0, ret_on=0.0)
        bi = max(bi, float(a1.max())); bs = max(bs, float(b1.max())); bw = max(bw, float(c1.max())); bl = max(bl, float((b1 * kloc[None, :]).max()))
    out["band_linear_steepness"] = dict(kp=kp, kp_crest_inlet_lin=kp * bi, kp_crest_side_core_lin=kp * bs, kp_crest_wall_strip_lin_target=kp * bw,
                                        klocal_crest_side_core_lin=bl, G4_max=0.40,
                                        note="target only (the band tapers it to 0 at the outer wall; the realised field there adds the wall's "
                                             "reflection: DFG-2's G4 0.41 at x 179.5 m, y 99.5 m [measured]); here the side core is y 110-132.5 m, "
                                             "the wall strip y > 132.5 m", tag="computed (linear)")
    out["linear_refs"] = linear_refs()
    out["ok"] = dict(focus=ok_focus, flat_equals_DFG2=bool(flat_ok), shelf_constant=bool(shelf_const), symmetry=ok_sym, continuity_flat_shelf=ok_cont,
                     interpolation=ok_int, vertical=ok_vert, zero_mass_flux=ok_flux, periodic=ok_per, layers_le_4=bool(nl <= GC.MAX_LAYERS),
                     table_covers_bands=bool(x[-1] >= GC.SD_SW and y[-1] >= GC.W_MAIN))
    out["all_ok"] = bool(all(out["ok"].values()))
    out["gate"] = "G1 numpy table check (plan_DFGS2 gates.A_validity.G1) -> %s" % ("PASS" if out["all_ok"] else "FAIL")
    out["content_sha256"] = info["content_sha256"]
    out["cpu_s"] = round(time.time() - t0, 2)
    return out


# ======================================================================== in-tank energy of the linear input (Q84 honesty; AM-DFGB1b rule)
DM1A_TABLE = GC.REPO + "/Unity/Build/FLIP50/tables/D_DM1_T12_W140_c5c22196af32.npz"          # read only (DM1A's input table)
DFGBE_TABLE = GC.REPO + "/Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz"   # read only (DFG-2B-E, AM-DFGB1b check)
DFGS_TABLE = GC.REPO + "/Unity/Build/FLIP52S/tables/DFGS_P28_xf145_W100_f277b5e223dc.npz"       # read only (DFG-S)
RHO = 1000.0
AM_DFGB1B = dict(DM1A=dict(inlet_var=2.316, P_in_MW=42.87, P_full_MW=36.44), DFGB_E=dict(inlet_var=0.295, P_in_MW=10.05, P_full_MW=4.39))


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
    directions of one frequency summed in A, U); node sums x 1 m (the AM-DFGB1b rule, which this reproduces: DM1A 2.316 m^2 / 42.87 MW)."""
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
    """the incoming linear sea inside each tank, from the input tables (Q84 honesty: 'equal spectral energy' is not 'equal in-tank energy').
    DFG-S-E140 on its own layout (inlet x 0-50 m all y; interior x >= 50 m, y <= 110 m: through x 50 m (y 0-110) + through y 110 m (x 50-180 m));
    DFG-S on its layout (y 70 m); DM1A and DFG-2B-E on the D19B layout (x 100 m, y 95 m) = the AM-DFGB1b numbers (reproduced as a check)."""
    F, info, _, _, _, _, _ = build()
    nl = info["n_layers"]
    f32 = lambda v: np.asarray(v, np.float32)
    L2 = [((f32(F["er%d" % n]) + 1j * f32(F["ei%d" % n])).astype(complex), (f32(F["ur%d" % n]) + 1j * f32(F["ui%d" % n])).astype(complex),
           (f32(F["vr%d" % n]) + 1j * f32(F["vi%d" % n])).astype(complex), f32(F["kk%d" % n]).astype(float)) for n in range(nl)]
    out = dict(rule=tank_energy.__doc__.split("[computed] ")[1][:400], tag="[computed] numpy on the linear input tables")
    out["DFGS2E"] = tank_energy(L2, f32(F["hh"]).astype(float), GC.IN_X1, GC.SD0, GC.SD_GEN)
    for nm, p, lay in (("DFGS", DFGS_TABLE, (50.0, 70.0, 180.0)), ("DM1A", DM1A_TABLE, (100.0, 95.0, 180.0)), ("DFGB_E", DFGBE_TABLE, (100.0, 95.0, 180.0))):
        if os.path.exists(p):
            L, h, _ = _layers_npz(p)
            out[nm] = tank_energy(L, h, *lay)
            out[nm]["table"] = p.replace(GC.REPO + "/", "")
    D = out.get("DM1A")
    if D:
        for nm in ("DFGS2E", "DFGS", "DFGB_E"):
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
    E = out["DFGS2E"]
    out["statement_en"] = ("equal SPECTRAL energy (Q84): sum a^2 = %.6f m^2 = DM1A's at the generation depth; inside the tank the incoming linear "
                           "waves carry less: inlet-band surface variance %.3f x DM1A's (Hm0-equivalent %.2f m vs %.2f m) and the power entering "
                           "the interior %.3f x DM1A's (%.1f vs %.1f MW per half tank) [computed, the AM-DFGB1b rule on DFG-S-E140's own layout]"
                           % (GC.DM1A_SUM_A2, E.get("inlet_variance_over_DM1A", float("nan")), E["inlet_band_Hm0_equiv_m"],
                              (D or {}).get("inlet_band_Hm0_equiv_m", float("nan")), E.get("interior_power_over_DM1A", float("nan")),
                              E["power_into_interior_MW"], (D or {}).get("power_into_interior_MW", float("nan"))))
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
        p = GC.PLAN_DIR + "/table_check_DFGS2.json"
        GC.jdump(o, p)
        print(json.dumps(GC.clean({k: o[k] for k in ("ok", "all_ok", "cpu_s")})), "->", p)
        print(json.dumps(GC.clean(dict(focus=o["focus"], flat_and_shelf=o["flat_and_shelf"], continuity=o["continuity"], interpolation=o["interpolation"],
                                       vertical=o["vertical_profile"], bands=o["band_linear_steepness"])))[:3500])
    elif a[0] == "energy":
        print(json.dumps(GC.clean(energy_in_tank()), ensure_ascii=False, indent=1))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
