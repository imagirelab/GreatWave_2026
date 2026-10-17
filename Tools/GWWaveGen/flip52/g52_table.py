# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: the N-layer (one layer per frequency) complex-amplitude inflow table, its numpy mirror of the band VEX
(g52_tanklib.dirwave + the unchanged g50 bands50 / relax_apply), and the numpy table checks = gate G1 (numpy only: py -3.10 -B, and
importable from hython). 2026-10-17 written new (Claude). flip50 modules are imported READ ONLY (g50_table: bilinear, bands_np, tapers_np,
rampT, relaxw, chch). No flip45-flip51 file is edited.

The sea (flat bed h = 20 m, so every component is an exact Airy plane wave; no WKB):
    eta(x, y, t) = sum_n Re(A_n(x, y) e^{-i w_n (t - t_f)}),   w_n = 2 pi n / P  (n = 3, 4, 5; P = 28 s, so eta is P-periodic)
    A_n(x, y) = sum_j a_nj exp(i (k_n cos th_j (x - x_f) + k_n sin th_j y)),   a_nj = a_sum wf_n wd_j
Every component has phase 0 at (x_f, 0) at t = t_f + m P. Layer n stores (2D surface fields, x fastest = Houdini volume order):
    er<n>, ei<n>   eta_n = er cos(w_n t') + ei sin(w_n t'),  t' = t - t_f
    ur<n>, ui<n>   U_n at z = 0 (x velocity: sum_j a_nj w_n coth(k_n h) cos th_j e^{...}), same convention
    vr<n>, vi<n>   V_n at z = 0 (lateral velocity, sin th_j)
    kk<n>          k_n (the layer's own wavenumber: its own vertical profile)
  shared: hh (still depth), mx, my (zero-mean-mass-flux return current, m/s, depth uniform, for unit band factor):
    with Wheeler stretching z' = h (z - eta_t)/(h + eta_t) on the TOTAL eta_t, the depth integral of the stretched velocity is
    (1 + eta_t/h) sum_n q_n, q_n = U_n tanh(k_n h)/k_n; its mean over P is sum_n Re(A_n conj(Q_n)) / (2 h) (cross-frequency products of
    distinct harmonics of 1/P average to zero over P), so u_r = -sum_n Re(A_n conj(Q_n)) / (2 h^2) cancels it, layer by layer.
VEX (g52_tanklib.dirwave) for the band factor g = gain x ramp x wall tapers x side-band factor, layers n = 0 .. d_nlayer - 1:
    eta_t = g sum_n (er_n c_n + ei_n s_n), c_n = cos(2 pi h_n t'/P), s_n = sin(...)
    z' = clamp(h (z - eta_t)/max(h + eta_t, 0.1 h), -h, 0)
    U = g sum_n (ur_n c_n + ui_n s_n) cosh(k_n (z' + h))/cosh(k_n h) + ret_on g^2 mx;  V likewise with vr, vi, my (horizontal only)
Grid: x 0-214 m and y 0-100 m, 1 m (bilinear between nodes = Houdini volumesample on voxel centres; float32 storage).
The npz name carries a content hash (sha of the arrays and the info), so the same sea always gives the same file name.

usage (py -3.10 -B):
  g52_table.py write DFG2|B2|B1|all     Unity/Build/FLIP52/tables/DFG_<set>_P28_W100_<hash12>.npz (if not there) and print its path
  g52_table.py check DFG2|B2|B1|all     the G1 numpy checks -> Unity/Build/FLIP52/plan/table_check_<set>.json
"""
import os, sys, json, math, time, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g52_common as GC            # noqa: E402
import g50_table as TB50           # noqa: E402  read only (bilinear, bands_np, tapers_np, rampT, relaxw, chch)

TWO_PI = 6.283185307179586476925   # the same literal is in the VEX (independent of the precision of VEX PI)
_bilinear = TB50._bilinear
bands_np = TB50.bands_np
tapers_np = TB50.tapers_np
rampT = TB50.rampT
relaxw = TB50.relaxw
chch = TB50.chch
G1_TOL = dict(focus_rel=1e-3, phase_rad=1e-6, continuity=5e-3, interpolation=0.02, vertical=1e-4, mass_flux_rel=1e-6, symmetry=1e-9,
              periodic_rel=1e-9)


def fields_of(nl):
    return ["%s%d" % (b, n) for n in range(nl) for b in GC.FIELDS_LAYER] + list(GC.FIELDS_SHARED)


def grid():
    x = np.arange(GC.TABLE_X[0], GC.TABLE_X[1] + 1e-9, GC.TABLE_DX)
    y = np.arange(GC.TABLE_Y[0], GC.TABLE_Y[1] + 1e-9, GC.TABLE_DX)
    return x, y


# ======================================================================== the exact linear sea (direct component sums)
def layer_complex(C, n, x, y):
    """complex amplitudes on (y, x) of layer n: A_n, U_n (surface), V_n (surface) and q_n = tanh(k h)/k. Exact (flat bed)."""
    k = float(C["k"][n]); om = float(C["om"][n]); h = C["h"]
    th = np.radians(C["th"]); a = C["a"][n]
    Ey = np.exp(1j * np.outer(np.asarray(y, float), k * np.sin(th)))             # (ny, nd)
    Ex = np.exp(1j * np.outer(k * np.cos(th), np.asarray(x, float) - C["x_f"]))  # (nd, nx)
    fac = om * math.cosh(k * h) / math.sinh(k * h)
    A = (Ey * a[None, :]) @ Ex
    U = (Ey * (a * fac * np.cos(th))[None, :]) @ Ex
    V = (Ey * (a * fac * np.sin(th))[None, :]) @ Ex
    return A, U, V, math.tanh(k * h) / k


def direct(C, x, y, z, t, layers=None, stretch=True):
    """the exact linear sea at points (broadcast arrays): eta (sum over the chosen layers), and the stretched linear velocity (U, V) at the
    elevation z (z' = h (z - eta)/(h + eta) on the eta of the chosen layers; z above the surface -> z' = 0). Component sums (independent of
    the table)."""
    x = np.asarray(x, float); y = np.asarray(y, float); z = np.asarray(z, float); t = np.asarray(t, float)
    x, y, z, t = np.broadcast_arrays(x, y, z, t)
    h = C["h"]; th = np.radians(C["th"])
    L = range(len(C["om"])) if layers is None else layers
    eta = np.zeros(x.shape); ph = {}
    for n in L:
        k = C["k"][n]; om = C["om"][n]
        P_ = k * np.cos(th)[None, :] * (x.ravel()[:, None] - C["x_f"]) + k * np.sin(th)[None, :] * y.ravel()[:, None] \
            - om * (t.ravel()[:, None] - C["t_f"])
        ph[n] = P_
        eta += (C["a"][n][None, :] * np.cos(P_)).sum(1).reshape(x.shape)
    if stretch:
        zp = np.clip(h * (z - eta) / np.maximum(h + eta, 0.1 * h), -h, 0.0)
    else:
        zp = np.minimum(z, 0.0)
    U = np.zeros(x.shape); V = np.zeros(x.shape)
    for n in L:
        k = C["k"][n]; om = C["om"][n]
        prof = om * np.cosh(k * (zp.ravel() + h)) / math.sinh(k * h)
        c_ = C["a"][n][None, :] * np.cos(ph[n])
        U += (prof * (c_ * np.cos(th)[None, :]).sum(1)).reshape(x.shape)
        V += (prof * (c_ * np.sin(th)[None, :]).sum(1)).reshape(x.shape)
    return eta, U, V


# ======================================================================== the table
def build(set_name="DFG2"):
    """arrays (ny, nx) float64 and the info dict."""
    C = GC.components(set_name)
    x, y = grid()
    nl = len(C["om"])
    if nl > GC.MAX_LAYERS:
        raise ValueError("at most %d layers (VEX d_n0..d_n3)" % GC.MAX_LAYERS)
    h = C["h"]
    F = {}
    Mx = np.zeros((len(y), len(x))); My = np.zeros_like(Mx)
    per_layer_M = []
    for n in range(nl):
        A, U, V, q = layer_complex(C, n, x, y)
        F["er%d" % n] = A.real; F["ei%d" % n] = A.imag
        F["ur%d" % n] = U.real; F["ui%d" % n] = U.imag
        F["vr%d" % n] = V.real; F["vi%d" % n] = V.imag
        F["kk%d" % n] = np.full(A.shape, float(C["k"][n]))
        mxn = np.real(A * np.conj(U * q)) / (2.0 * h)
        myn = np.real(A * np.conj(V * q)) / (2.0 * h)
        per_layer_M.append((mxn, myn))
        Mx += mxn; My += myn
    F["hh"] = np.full((len(y), len(x)), h)
    F["mx"] = -Mx / h
    F["my"] = -My / h
    F = {nm: np.ascontiguousarray(v) for nm, v in F.items()}
    th = C["th"]; wd = C["wd"]; wf = C["wf"]
    info = dict(set=set_name, plan="DFG-2", plan_frozen=GC.PLAN_REL, P=float(GC.P_S), harmonics=[int(v) for v in GC.HARMONICS],
                n_layers=int(nl), omega=[float(v) for v in C["om"]], T=[float(GC.P_S / v) for v in GC.HARMONICS], k=[float(v) for v in C["k"]],
                kh=[float(v * h) for v in C["k"]], h=float(h), freq_weights=[float(v) for v in wf], theta_deg=[float(v) for v in th],
                dir_weights=[float(v) for v in wd], dspec=list(GC.SETS[set_name]["dspec"]), a_sum=float(C["a_sum"]),
                a_max_component=float(C["a"].max()), amp_per_freq=[float(C["a_sum"] * v) for v in wf], sum_a2=float(np.sum(C["a"] ** 2)),
                n_components=int(C["a"].size), x_f=float(GC.X_F), t_f=float(GC.T_F), foci=[float(v) for v in GC.FOCI],
                x0=float(x[0]), dx=float(GC.TABLE_DX), nx=int(len(x)), y0=float(y[0]), dy=float(GC.TABLE_DX), ny=int(len(y)),
                x1=float(x[-1]), y1=float(y[-1]), fields=fields_of(nl),
                convention="eta(t) = sum_n er<n> cos(2 pi h_n (t - t_f)/P) + ei<n> sin(...); U, V likewise at z = 0, times cosh(k_n(z'+h))/cosh(k_n h) "
                           "with z' stretched on the total eta; return current mx, my (m/s, depth uniform) multiplied by g^2 when ret_on 1",
                source="Tools/GWWaveGen/flip52/g52_table.py build() (exact flat-bed component sums, a_nj = a_sum wf_n wd_j)")
    return F, info, C, x, y, per_layer_M


def content_hash(F, info):
    h = hashlib.sha256()
    for nm in info["fields"]:
        h.update(nm.encode()); h.update(np.asarray(F[nm], np.float32).tobytes())
    h.update(json.dumps(info, sort_keys=True, default=float).encode())
    return h.hexdigest()


def table_path(set_name, ch):
    return (GC.TABLE_DIR + "/DFG_%s_P%s_W%s_%s.npz" % (set_name, GC.tag(GC.P_S), GC.tag(GC.W_MAIN), ch[:12])).replace("\\", "/")


def write(set_name="DFG2", dry=False):
    """write the npz if a file with the same content hash is not there yet. Returns (path, file sha256 or None if dry, content hash, info)."""
    F, info, _, _, _, _ = build(set_name)
    ch = content_hash(F, info)
    p = table_path(set_name, ch)
    info["content_sha256"] = ch
    if dry:
        return p, (GC.sha256_file(p) if os.path.exists(p) else None), ch, info
    os.makedirs(GC.TABLE_DIR, exist_ok=True)
    if not os.path.exists(p):
        np.savez(p, info=np.array(json.dumps(info, default=float)), **{nm: np.asarray(F[nm], np.float32) for nm in info["fields"]})
    return p, GC.sha256_file(p), ch, info


def load(path):
    """the table as the VEX sees it (float32 fields widened to float64)."""
    d = np.load(path, allow_pickle=False)
    info = json.loads(str(d["info"]))
    tab = dict(info=info)
    for nm in info["fields"]:
        tab[nm] = np.asarray(d[nm], np.float32).astype(np.float64)
    return tab


def from_build(F, info):
    """the table as the VEX would see it, straight from build() (float32 rounding)."""
    tab = dict(info=info)
    for nm in info["fields"]:
        tab[nm] = np.asarray(F[nm], np.float32).astype(np.float64)
    return tab


# ======================================================================== numpy mirror of the VEX (g52_tanklib)
def dirwave_np(tab, x, yv, zl, t, g, tf=None, ret_on=1.0, layers=None):
    """VEX dirwave (N layers): returns (eta_t, U, V) for band factor g (arrays broadcast). layers: restrict to these layer indices (checks only;
    the VEX always uses all d_nlayer layers)."""
    I = tab["info"]
    P = float(I["P"]); tf = float(I["t_f"]) if tf is None else float(tf)
    tt = np.asarray(t, float) - tf
    S = lambda nm: _bilinear(tab, nm, x, zl)
    L = list(range(int(I["n_layers"]))) if layers is None else list(layers)
    cs = {}; sn = {}
    es = 0.0
    for n in L:
        hn = float(I["harmonics"][n])
        ph = TWO_PI * hn * tt / P
        cs[n] = np.cos(ph); sn[n] = np.sin(ph)
        es = es + (S("er%d" % n) * cs[n] + S("ei%d" % n) * sn[n])
    eta = g * es
    h = S("hh")
    ye = np.clip(h * (np.asarray(yv, float) - eta) / np.maximum(h + eta, 0.1 * h), -h, 0.0)
    us = 0.0; vs = 0.0
    for n in L:
        k = S("kk%d" % n)
        prof = chch(k * (ye + h), k * h)
        us = us + (S("ur%d" % n) * cs[n] + S("ui%d" % n) * sn[n]) * prof
        vs = vs + (S("vr%d" % n) * cs[n] + S("vi%d" % n) * sn[n]) * prof
    U = g * us; V = g * vs
    if ret_on > 0.5:
        U = U + g * g * S("mx"); V = V + g * g * S("my")
    return eta, U, V


def relax_np(pl, v0, t, dts, P, tab=None, du_abs=0.0):
    """VEX relax_apply (g50 code, unchanged; dirwave = the N-layer one): pl = (x, vertical, lateral) plan coordinates, v0 = (vx, vy vertical,
    vz lateral). FLIP52 has no Fenton inlet (sf_on 0)."""
    x, yv, zl = float(pl[0]), float(pl[1]), float(pl[2])
    v = np.array(v0, float)
    wdt, ftg, inb, insd = bands_np(x, zl, dts, P)
    if wdt <= 0.0:
        return v
    wt, ws = tapers_np(x, zl, P)
    gb = P["in_gain"] if inb else P["sd_gain"]
    gm = gb * ftg * wt * ws * rampT(t, P["ramp_s"])
    tv = np.zeros(3)
    if gm != 0.0:
        if P["dir_on"] > 0.5 and tab is not None:
            _, U, V = dirwave_np(tab, x, yv, zl, t, gm, tf=P["dir_tf"], ret_on=P["ret_on"])
            tv = np.array([float(U), 0.0, float(V)])
        elif P.get("sf_on", 0.0) > 0.5:
            raise ValueError("FLIP52 has no Fenton inlet (sf_on must be 0)")
    ux = tv[0]
    if inb and P["duabs_on"] > 0.5:
        ux += wt * du_abs
    return np.array([v[0] + (ux - v[0]) * wdt, v[1], v[2] + (tv[2] - v[2]) * wdt])


# ======================================================================== linear references (gates and reports)
def linear_refs(set_name="DFG2"):
    """[computed] from the exact linear sea: the G2f gauge amplitudes per frequency (x 60 m, y 0.5/15/30/45/60 m), the focal design crest,
    the incoming-crest line x 60 m over one period, the report gauges."""
    C = GC.components(set_name)
    nl = len(C["om"])
    g2 = {}
    for yg in GC.GAUGE_Y:
        row = {}
        for n in range(nl):
            A, _, _, _ = layer_complex(C, n, np.array([60.0]), np.array([yg]))
            a = complex(A[0, 0])
            row["n%d" % C["harmonics"][n]] = [a.real, a.imag]
        g2["y%g" % yg] = row
    rep = {}
    for xg, yg in ((150.0, 0.5), (190.0, 0.5), (200.0, 0.5), (190.0, 30.0), (200.0, 30.0)):
        row = {}
        for n in range(nl):
            A, _, _, _ = layer_complex(C, n, np.array([xg]), np.array([yg]))
            a = complex(A[0, 0])
            row["n%d" % C["harmonics"][n]] = [a.real, a.imag]
        rep["x%g_y%g" % (xg, yg)] = row
    yl = np.arange(0.0, GC.INTERIOR_Y + 1e-9, 1.0)
    ts = GC.T_F + np.arange(-GC.P_S / 2.0, GC.P_S / 2.0 - 1e-9, 0.125)
    cin = 0.0
    for t in ts:
        e, _, _ = direct(C, 60.0, yl, 0.0, t, stretch=False)
        cin = max(cin, float(e.max()))
    ef, _, _ = direct(C, GC.X_F, 0.0, 0.0, GC.T_F, stretch=False)
    kp = GC.kp()
    return dict(G2f_gauges=dict(x=60.0, y=list(GC.GAUGE_Y), A_n=g2, convention="A = er + i ei of eta_n = Re(A e^{-i w_n (t - t_f)})"),
                report_gauges=rep, design_crest_m=float(ef), a_sum=C["a_sum"], amp_per_freq=[float(C["a_sum"] * v) for v in C["wf"]],
                a_max_component=float(C["a"].max()), c_in_line_x60_lin_m=cin, gain_lin_over_c_in=float(ef) / cin if cin > 0 else None,
                kp=kp, kp_asum=kp * C["a_sum"], harmonics=C["harmonics"], omega=[float(v) for v in C["om"]],
                tags="computed (exact linear component sums on the flat 20 m bed)")


# ======================================================================== G1: numpy checks
def _deriv4(f, axis, d):
    """4th-order central difference on interior points (2 cells trimmed at each end of the axis)."""
    f = np.moveaxis(f, axis, 0)
    out = (-f[4:] + 8 * f[3:-1] - 8 * f[1:-3] + f[:-4]) / (12.0 * d)
    return np.moveaxis(out, 0, axis)


def checks(set_name="DFG2"):
    t0 = time.time()
    F, info, C, x, y, per_layer_M = build(set_name)
    info["content_sha256"] = content_hash(F, info)
    tab = from_build(F, info)
    nl = info["n_layers"]; h = C["h"]; P = info["P"]
    out = dict(set=set_name, info={k: v for k, v in info.items() if k != "fields"}, tolerances=G1_TOL)
    # ---- 1. focus: per layer A_n(x_f, 0) = sum_j a_nj, phase 0; total eta(x_f, 0, t_f + mP) = a_sum, against independent sums
    i_f = int(np.argmin(np.abs(x - GC.X_F))); j0 = 0
    PL = GC.plan()
    pl_ = PL["sea"]
    plan_a_sum = float(PL["decision_after_first_0p5"]["branch_screens"]["B2"]["a_sum_m"]) if set_name == "B2" else float(pl_["a_sum_m"])
    plan_wf = [float(v) for v in pl_["freq_weights"]]
    per = []
    for n in range(nl):
        Af = complex(tab["er%d" % n][j0, i_f], tab["ei%d" % n][j0, i_f])
        ind = float(np.sum(C["a"][n]))
        plan_amp = plan_a_sum * plan_wf[n]
        per.append(dict(n=info["harmonics"][n], abs_A=abs(Af), phase_rad=float(np.angle(Af)), independent_sum=ind, rel_err=abs(Af) / ind - 1.0,
                        plan_amp_per_freq=plan_amp, rel_err_vs_plan=abs(Af) / plan_amp - 1.0))
    tot = []
    for m, tf_ in enumerate(GC.FOCI):
        e, _, _ = dirwave_np(tab, GC.X_F, 50.0, 0.0, tf_, 1.0, ret_on=0.0)
        tot.append(dict(t=tf_, eta=float(e), rel_err_vs_a_sum=float(e) / C["a_sum"] - 1.0,
                        rel_err_vs_plan=float(e) / plan_a_sum - 1.0, plan_a_sum=plan_a_sum))
    # the focus is the maximum of the linear field in space and time (scan around it)
    xs_ = np.arange(GC.X_F - 30.0, GC.X_F + 30.01, 1.0); ys_ = np.arange(0.0, 30.01, 1.0)
    best = (-1e9, None)
    for t in GC.T_F + np.arange(-3.0, 3.001, 0.125):
        e, _, _ = direct(C, xs_[None, :], ys_[:, None], 0.0, t, stretch=False)
        j = int(np.argmax(e))
        if e.flat[j] > best[0]:
            best = (float(e.flat[j]), (float(xs_[j % len(xs_)]), float(ys_[j // len(xs_)]), float(t)))
    out["focus"] = dict(per_layer=per, total=tot, space_time_max=dict(value=best[0], x=best[1][0], y=best[1][1], t=best[1][2]),
                        tag="computed: the float32 table at the focus node against the component sums and the plan's amp_per_freq / a_sum")
    ok_focus = bool(all(abs(r["rel_err"]) < G1_TOL["focus_rel"] and abs(r["rel_err_vs_plan"]) < G1_TOL["focus_rel"] and abs(r["phase_rad"]) < G1_TOL["phase_rad"]
                        for r in per)
                    and all(abs(r["rel_err_vs_a_sum"]) < G1_TOL["focus_rel"] and abs(r["rel_err_vs_plan"]) < G1_TOL["focus_rel"] for r in tot)
                    and abs(best[1][0] - GC.X_F) < 1e-9 and best[1][1] == 0.0 and abs(best[1][2] - GC.T_F) < 1e-9)
    # ---- 2. symmetry about y = 0
    symm = []
    yy = np.array([3.0, 17.5, 41.0, 88.0])
    for n in range(nl):
        Ap, Up, Vp, _ = layer_complex(C, n, x, yy); An, Un, Vn, _ = layer_complex(C, n, x, -yy)
        sc = float(np.abs(Ap).max())
        symm.append(dict(n=info["harmonics"][n], V_at_y0_max=float(np.hypot(tab["vr%d" % n][0], tab["vi%d" % n][0]).max()),
                         eta_mirror=float(np.abs(Ap - An).max()) / sc, U_mirror=float(np.abs(Up - Un).max()) / sc,
                         V_antisym=float(np.abs(Vp + Vn).max()) / sc))
    out["symmetry"] = dict(per_layer=symm, set_symmetric=bool(np.allclose(np.sort(C["th"]), -np.sort(C["th"])[::-1], rtol=0, atol=0)
                                                             and np.array_equal(C["wd"], C["wd"][::-1])), tag="computed")
    sc_u = max(float(np.hypot(tab["ur%d" % n], tab["ui%d" % n]).max()) for n in range(nl))
    ok_sym = bool(out["symmetry"]["set_symmetric"] and all(r["V_at_y0_max"] < 1e-6 * sc_u and r["eta_mirror"] < G1_TOL["symmetry"]
                                                          and r["U_mirror"] < G1_TOL["symmetry"] and r["V_antisym"] < G1_TOL["symmetry"] for r in symm))
    # ---- 3. continuity per layer (flat bed): -i w A + d/dx(U q) + d/dy(V q) = 0 on the float32 table, 4th-order differences
    cont = []
    for n in range(nl):
        om = C["om"][n]; q = math.tanh(C["k"][n] * h) / C["k"][n]
        A = tab["er%d" % n] + 1j * tab["ei%d" % n]
        U = (tab["ur%d" % n] + 1j * tab["ui%d" % n]) * q
        V = (tab["vr%d" % n] + 1j * tab["vi%d" % n]) * q
        res = -1j * om * A[2:-2, 2:-2] + _deriv4(U, 1, GC.TABLE_DX)[2:-2, :] + _deriv4(V, 0, GC.TABLE_DX)[:, 2:-2]
        sc = om * float(np.abs(A).max())
        cont.append(dict(n=info["harmonics"][n], max_rel_residual=float(np.abs(res).max() / sc), scale=sc))
    out["continuity"] = dict(per_layer=cont, note="4th-order central differences on the 1 m float32 table (interior nodes)", tag="computed")
    ok_cont = bool(all(r["max_rel_residual"] < G1_TOL["continuity"] for r in cont))
    # ---- 4. interpolation: float32 table + bilinear (= the VEX) against the exact sea at 400 random points and times (surface values)
    rng = np.random.default_rng(52)
    xq = rng.uniform(0.0, GC.TABLE_X[1], 400); yq = rng.uniform(0.0, GC.TABLE_Y[1], 400); tq = rng.uniform(0.0, 110.0, 400)
    e_np, U_np, V_np = dirwave_np(tab, xq, 50.0 + 0 * xq, yq, tq, 1.0, ret_on=0.0)
    e_ex, U_ex, V_ex = direct(C, xq, yq, 50.0, tq)
    sc_e = float(C["a_sum"])
    out["interpolation"] = dict(n=400, max_rel_eta=float(np.abs(e_np - e_ex).max() / sc_e), max_rel_U=float(np.abs(U_np - U_ex).max() / sc_u),
                                max_rel_V=float(np.abs(V_np - V_ex).max() / sc_u), scale_eta=sc_e, scale_u=sc_u,
                                note="vertical 50 m: above the surface -> z' = 0 (surface values); bilinear on 1 m nodes", tag="computed")
    ok_int = bool(max(out["interpolation"]["max_rel_eta"], out["interpolation"]["max_rel_U"], out["interpolation"]["max_rel_V"]) < G1_TOL["interpolation"])
    # ---- 5. vertical profile per layer (own k_n) and total, at table nodes (no interpolation error), stretched on the eta of the same layers
    vert = []
    ix = [int(np.argmin(np.abs(x - v))) for v in (20.0, 60.0, 120.0, 150.0, 200.0)]
    jy = [int(np.argmin(np.abs(y - v))) for v in (0.0, 23.0, 61.0, 99.0)]
    XX = np.array([x[i] for i in ix for _ in jy for _z in range(3) for _t in range(4)])
    YY = np.array([y[j] for _ in ix for j in jy for _z in range(3) for _t in range(4)])
    ZZ = np.array([z for _ in ix for _j in jy for z in (-2.0, -8.0, -15.0) for _t in range(4)])
    TT = np.array([t for _ in ix for _j in jy for _z in range(3) for t in (41.3, 44.0, 57.7, 99.1)])
    for L in [[n] for n in range(nl)] + [list(range(nl))]:
        e1, U1, V1 = dirwave_np(tab, XX, ZZ, YY, TT, 1.0, ret_on=0.0, layers=L)
        e2, U2, V2 = direct(C, XX, YY, ZZ, TT, layers=L)
        vert.append(dict(layers=[info["harmonics"][n] for n in L], max_rel_err=float(max(np.abs(U1 - U2).max(), np.abs(V1 - V2).max()) / sc_u),
                         max_rel_eta=float(np.abs(e1 - e2).max() / sc_e), n=int(len(XX))))
    out["vertical_profile"] = dict(per_layer_and_total=vert, tag="computed (float32 storage; the reference uses cosh(k_n (z' + h))/sinh(k_n h) per component)")
    ok_vert = bool(all(r["max_rel_err"] < G1_TOL["vertical"] for r in vert))
    # ---- 6. zero period-mean mass flux per layer (with its own return current) and in total (stored mx), through x = const (half tank):
    #         time mean over P (64 samples) of the lateral trapezoid of the depth integral (24-point Gauss-Legendre from the bed to eta_t) of the
    #         mirror's stretched velocity U
    gx, gw = np.polynomial.legendre.leggauss(24)
    ts = GC.T_F + P * np.arange(64) / 64.0
    trap = getattr(np, "trapezoid", None) or np.trapz
    flux = {}
    sumM_err = 0.0
    mx_tot = np.zeros_like(F["mx"])
    for n in range(nl):
        mx_tot += -per_layer_M[n][0] / h
    sumM_err = float(np.abs(np.asarray(F["mx"], np.float32).astype(float) - mx_tot).max())
    for xq_ in (25.0, 60.0, 150.0, 200.0):
        i = int(np.argmin(np.abs(x - xq_)))
        row = {}
        for L in [[n] for n in range(nl)] + [list(range(nl))]:
            tabL = dict(tab)
            if len(L) == 1:                             # this layer's own return current
                n = L[0]
                tabL["mx"] = np.asarray(-per_layer_M[n][0] / h, np.float32).astype(float)
                tabL["my"] = np.asarray(-per_layer_M[n][1] / h, np.float32).astype(float)
            vals = {}
            for ret in (0.0, 1.0):
                Ms = []
                for t in ts:
                    e, _, _ = dirwave_np(tabL, x[i] + 0 * y, 50.0, y, t, 1.0, ret_on=0.0, layers=L)
                    zt = e[None, :]
                    zz = -h + (zt + h) * (gx[:, None] + 1.0) / 2.0          # (24, ny) physical z from the bed to eta
                    _, U, _ = dirwave_np(tabL, x[i] + 0 * zz, zz, np.broadcast_to(y, zz.shape), t, 1.0, ret_on=ret, layers=L)
                    col = ((zt + h) / 2.0 * (gw[:, None] * U).sum(0))[0]
                    Ms.append(float(trap(col, y)))
                vals[ret] = float(np.mean(Ms))
            key = "n%d" % info["harmonics"][L[0]] if len(L) == 1 else "total"
            row[key] = dict(mean_flux_without_return_m3s=vals[0.0], with_return_m3s=vals[1.0],
                            rel=abs(vals[1.0]) / max(abs(vals[0.0]), 1e-30))
        flux["x%g" % xq_] = row
    out["mean_mass_flux"] = dict(per_x=flux, stored_mx_equals_sum_of_layers_max_abs=sumM_err,
                                 max_return_current_mps=float(np.abs(F["mx"]).max()), max_lateral_return_mps=float(np.abs(F["my"]).max()),
                                 note="each layer with its own return current, and all layers with the stored (summed) mx, my: the cross-frequency "
                                      "products average to zero over P", tag="computed (numeric depth and time integration of the VEX mirror)")
    ok_flux = bool(all(r["rel"] < G1_TOL["mass_flux_rel"] for row in flux.values() for r in row.values()) and sumM_err < 1e-6)
    # ---- 7. P-periodicity of the target at the G2f gauges and the focus
    gp = []
    for xg, yg in [(60.0, v) for v in GC.GAUGE_Y] + [(GC.X_F, 0.0)]:
        tt = np.arange(30.0, 58.0, 0.37)
        e0, U0, V0 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt, 1.0, ret_on=1.0)
        e1, U1, V1 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt + P, 1.0, ret_on=1.0)
        e2, U2, V2 = dirwave_np(tab, xg + 0 * tt, 50.0, yg + 0 * tt, tt + 2 * P, 1.0, ret_on=1.0)
        gp.append(dict(x=xg, y=yg, max_rel=float(max(np.abs(e1 - e0).max(), np.abs(e2 - e0).max()) / sc_e),
                       max_rel_U=float(max(np.abs(U1 - U0).max(), np.abs(U2 - U0).max(), np.abs(V1 - V0).max()) / sc_u)))
    out["periodicity"] = dict(rows=gp, tag="computed (t, t + P, t + 2P)")
    ok_per = bool(all(r["max_rel"] < G1_TOL["periodic_rel"] and r["max_rel_U"] < G1_TOL["periodic_rel"] for r in gp))
    # ---- 8. band steepness of the linear target over one period (report; G4 watches the realised 3x3-median field)
    kp = GC.kp()
    xin = np.arange(GC.WALL_TAPER, GC.IN_X1 + 0.5, 2.0); yin = np.arange(0.0, GC.W_MAIN - GC.SD_TAPER + 0.5, 2.0)
    xsd = np.arange(0.0, GC.SD_GEN + 0.5, 2.0); ysd = np.arange(GC.SD0, GC.W_MAIN - GC.SD_TAPER + 0.5, 2.0)
    bi = bs = 0.0
    for t in GC.T_F + np.arange(-P / 2.0, P / 2.0, 0.5):
        a1, _, _ = direct(C, xin[None, :], yin[:, None], 0.0, t, stretch=False)
        b1, _, _ = direct(C, xsd[None, :], ysd[:, None], 0.0, t, stretch=False)
        bi = max(bi, float(a1.max())); bs = max(bs, float(b1.max()))
    out["band_linear_steepness"] = dict(kp=kp, kp_crest_inlet_lin=kp * bi, kp_crest_side_lin=kp * bs, crest_inlet_lin_m=bi, crest_side_lin_m=bs,
                                        screen_nl2=dict(inlet=0.16, side=0.29), G4_max=0.40, tag="computed (linear; the screen's 2nd-order values in screen_nl2)")
    out["linear_refs"] = linear_refs(set_name)
    out["ok"] = dict(focus=ok_focus, symmetry=ok_sym, continuity=ok_cont, interpolation=ok_int, vertical=ok_vert, zero_mass_flux=ok_flux,
                     periodic=ok_per, layers_le_4=bool(nl <= GC.MAX_LAYERS))
    out["all_ok"] = bool(all(out["ok"].values()))
    out["gate"] = "G1 numpy table check (plan gates.A_validity.G1) -> %s" % ("PASS" if out["all_ok"] else "FAIL")
    out["content_sha256"] = info["content_sha256"]
    out["cpu_s"] = round(time.time() - t0, 2)
    return out


def table_record(set_name="DFG2", dry=False):
    """cfg['dir'] block for the set (the npz is written if missing; dry: never written, sha None if missing)."""
    p, sha, ch, info = write(set_name, dry=dry)
    return dict(set=set_name, npz=p, npz_sha256=sha, content_sha256=ch, P=info["P"], harmonics=info["harmonics"], n_layers=info["n_layers"],
                omega=info["omega"], T=info["T"], k=info["k"], freq_weights=info["freq_weights"], theta_deg=info["theta_deg"],
                dir_weights=info["dir_weights"], dspec=info["dspec"], a_sum=info["a_sum"], a_max_component=info["a_max_component"],
                amp_per_freq=info["amp_per_freq"], n_components=info["n_components"], x_f=info["x_f"], t_f=info["t_f"], foci=info["foci"],
                grid=dict(x=[info["x0"], info["x1"]], y=[info["y0"], info["y1"]], d=info["dx"]), fields=info["fields"],
                linear_refs=linear_refs(set_name))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    sets = list(GC.SETS) if a[1] == "all" else [a[1]]
    for s in sets:
        if s not in GC.SETS:
            print(__doc__); sys.exit(1)
        if a[0] == "write":
            p, sha, ch, info = write(s)
            print("table", s, p, "sha256", sha[:16], "content", ch[:16], "layers %d components %d a_max %.5f" % (info["n_layers"], info["n_components"],
                                                                                                             info["a_max_component"]))
        elif a[0] == "check":
            o = checks(s)
            os.makedirs(GC.PLAN_DIR, exist_ok=True)
            p = GC.PLAN_DIR + "/table_check_%s.json" % s
            GC.jdump(o, p)
            print(s, json.dumps({k: o[k] for k in ("ok", "all_ok", "cpu_s")}), "->", p)
        else:
            print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
