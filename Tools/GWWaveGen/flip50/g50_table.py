# -*- coding: utf-8 -*-
"""FLIP50 (option D): the complex-amplitude inflow table of the directional periodic sea, its numpy mirror of the band VEX, and the numpy
checks (numpy only: py -3.10 -B, and importable from hython). 2026-10-15 written new (Claude). No flip45-flip49 file is edited.

The sea (g50_dirfield.DirField, the same code that made the design screens): N Airy components of ONE period T, directions theta_j uniform
over +-theta_max (+-theta pairs, so symmetric about y = 0), equal amplitudes a_j = a_sum/N at h0, WKB shoaling + refraction over the
laterally straight D19B bed (k_y,j = k(h0) sin theta_j conserved), phases 0 at the focus (x_f, 0) at t = t_f + nT:
    eta(x, y, t) = Re(A(x, y) e^{-i omega (t - t_f)}),  A = sum_j A_j(x) exp(i(Phi_j(x) + k_y,j y))
Every component has the same omega, so A is time independent (a fixed hot spot that a crest passes once per period) and, at a given x, every
component has the same |k| = k(h(x)): the linear horizontal velocity at elevation z is the surface value times cosh(k(z + h))/cosh(k h).
So the table needs only 2D surface fields:
    er, ei   eta = er cos(omega t') + ei sin(omega t'),  t' = t - t_f
    ur, ui   U at z = 0 (x velocity), same convention
    vr, vi   V at z = 0 (lateral velocity)
    hh, kk   local still depth h(x) and k(h(x)) (the vertical profile)
    mx, my   zero-mean-mass-flux return current (m/s, depth uniform) for unit band factor [chosen, the FLIP49 Fenton inlet has u2 = 0]:
             with Wheeler stretching z' = h (z - eta)/(h + eta) the depth integral of the stretched linear velocity is (1 + eta/h) q, q = U tanh(kh)/k,
             whose period mean is M = Re(A conj(Q))/(2h) (about 0.8 of the Stokes transport here). u_r = -M/h cancels it.
VEX (g50_tanklib.dirwave) evaluates, for the band factor g = gain x ramp x wall tapers x side-band factor:
    eta_t = g (er c + ei s);  z' = clamp(h (z - eta_t)/max(h + eta_t, 0.1 h), -h, 0);  P = cosh(k (z' + h))/cosh(k h)
    U = g (ur c + ui s) P + ret_on g^2 mx;  V = g (vr c + vi s) P + ret_on g^2 my
Grid: x 0-214 m and y 0-W m, 1 m (bilinear between nodes = Houdini volumesample on voxel centres; float32 storage).
The npz name carries a content hash (sha of the arrays and the info), so the same sea always gives the same file name.

usage (py -3.10 -B):
  g50_table.py write DM1|DF1 [--W=140]     write Unity/Build/FLIP50/tables/D_<case>_T<T>_<hash12>.npz (if not there) and print its path
  g50_table.py check DM1|DF1               numpy checks (focus vs theory, phase integral, continuity/volume flux, symmetry, interpolation,
                                           vertical profile, mean mass flux) -> Unity/Build/FLIP50/plan/table_check_<case>.json
"""
import os, sys, json, math, hashlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g50_dirfield as DF          # noqa: E402
import g50_common as GC            # noqa: E402

BED_DF = dict(h0=GC.H0, x_toe=GC.X_TOE, s=GC.SLOPE_S, kind="beach")   # g50_dirfield bed spec = D19B


X_FULL_END = 262.0      # the DirField grid must CONTAIN the focus x_f (220.25 m): its phase reference is np.interp(x_f, x, cum), which
                        # clamps at the grid end. The table keeps only x <= 214 m of this grid (2026-10-15: found while writing; the
                        # design screens used grids that contained x_f, so their phases were right)


def full_grid(x_f, dx=GC.TABLE_DX, end=X_FULL_END):
    return np.union1d(np.arange(GC.TABLE_X[0], end + 1e-9, dx), [float(x_f)])


def dirfield(case, x=None, a_sum=None):
    c = GC.CASES[case]
    th, w = DF.components(c["theta_max_deg"], c["n"], c["weight"])
    x = full_grid(c["x_f"]) if x is None else np.asarray(x, float)
    if not (x[0] <= c["x_f"] <= x[-1]):
        raise ValueError("the DirField grid must contain the focus x_f %.2f m (got %.2f..%.2f)" % (c["x_f"], x[0], x[-1]))
    return DF.DirField(c["T"], th, w, c["a_sum"] if a_sum is None else a_sum, x, BED_DF, c["x_f"])


def build(case, W=GC.W_MAIN):
    """arrays (ny, nx) float64 and the info dict. Returns (F, info, df on the full grid, table x, y, table mask on the full grid)."""
    c = GC.CASES[case]
    y = np.arange(0.0, float(W) + 1e-9, GC.TABLE_DX)
    df = dirfield(case)
    m = df.x <= GC.TABLE_X[1] + 1e-9
    x = df.x[m]
    if not np.allclose(np.diff(x), GC.TABLE_DX) or abs(x[0] - GC.TABLE_X[0]) > 1e-12 or abs(x[-1] - GC.TABLE_X[1]) > 1e-9:
        raise ValueError("table x grid is not uniform 0..214 m")
    A = df.complex_amp(y)[m]                                  # (nx, ny)
    Uc, Vc = df.complex_vel(y, depth_avg=False, z=0.0)        # surface velocity
    Uc = Uc[m]; Vc = Vc[m]
    h = df.h[m]; k = df.k[m]
    q_fac = np.tanh(k * h) / k                                # depth integral of cosh(k(z+h))/cosh(kh)
    Mx = np.real(A * np.conj(Uc * q_fac[:, None])) / (2.0 * h[:, None])
    My = np.real(A * np.conj(Vc * q_fac[:, None])) / (2.0 * h[:, None])
    F = dict(er=np.real(A), ei=np.imag(A), ur=np.real(Uc), ui=np.imag(Uc), vr=np.real(Vc), vi=np.imag(Vc),
             hh=np.repeat(h[:, None], len(y), 1), kk=np.repeat(k[:, None], len(y), 1), mx=-Mx / h[:, None], my=-My / h[:, None])
    F = {nm: np.ascontiguousarray(v.T) for nm, v in F.items()}          # (ny, nx): x fastest (Houdini volume order)
    info = dict(case=case, T=float(c["T"]), omega=2 * math.pi / float(c["T"]), theta_max_deg=float(c["theta_max_deg"]), n=int(c["n"]),
                weight=c["weight"], a_sum=float(c["a_sum"]), a_j=float(c["a_sum"]) / int(c["n"]), x_f=float(c["x_f"]), t_f=float(c["t_f"]),
                h0=GC.H0, bed=BED_DF, k0=float(df.k0), L0=float(2 * math.pi / df.k0),
                x0=float(x[0]), dx=float(GC.TABLE_DX), nx=int(len(x)), y0=float(y[0]), dy=float(GC.TABLE_DX), ny=int(len(y)),
                x1=float(x[-1]), y1=float(y[-1]), fields=list(GC.TABLE_FIELDS),
                convention="eta(t) = er cos(om (t - t_f)) + ei sin(om (t - t_f)); U, V likewise at z = 0, times cosh(k(z'+h))/cosh(kh); "
                           "return current mx, my (m/s, depth uniform) multiplied by g^2 when ret_on 1",
                source="Tools/GWWaveGen/flip50/g50_table.py build() on g50_dirfield.DirField (the design screen code), DirField grid 0-262 m + x_f")
    return F, info, df, x, y, m


def content_hash(F, info):
    h = hashlib.sha256()
    for nm in GC.TABLE_FIELDS:
        h.update(nm.encode()); h.update(np.asarray(F[nm], np.float32).tobytes())
    h.update(json.dumps(info, sort_keys=True, default=float).encode())
    return h.hexdigest()


def write(case, W=GC.W_MAIN):
    """write the npz if a file with the same content hash is not there yet. Returns (path, file sha256, content hash, info)."""
    F, info, _, _, _, _ = build(case, W)
    ch = content_hash(F, info)
    os.makedirs(GC.TABLE_DIR, exist_ok=True)
    p = (GC.TABLE_DIR + "/D_%s_T%s_W%s_%s.npz" % (case, GC.tag(info["T"]), GC.tag(W), ch[:12])).replace("\\", "/")
    info["content_sha256"] = ch
    if not os.path.exists(p):
        np.savez(p, info=np.array(json.dumps(info, default=float)), **{nm: np.asarray(F[nm], np.float32) for nm in GC.TABLE_FIELDS})
    return p, GC.sha256_file(p), ch, info


def load(path):
    """the table as the VEX sees it (float32 fields widened to float64)."""
    d = np.load(path, allow_pickle=False)
    info = json.loads(str(d["info"]))
    tab = dict(info=info)
    for nm in GC.TABLE_FIELDS:
        tab[nm] = np.asarray(d[nm], np.float32).astype(np.float64)
    return tab


# ======================================================================== numpy mirror of the VEX (g50_tanklib)
def _bilinear(tab, nm, x, zl):
    """Houdini volumesample on voxel centres with the position clamped to the centre range (dtab_pos): bilinear."""
    I = tab["info"]
    x = np.clip(np.asarray(x, float), I["x0"], I["x1"]); zl = np.clip(np.asarray(zl, float), I["y0"], I["y1"])
    fx = (x - I["x0"]) / I["dx"]; fy = (zl - I["y0"]) / I["dy"]
    i0 = np.clip(np.floor(fx).astype(int), 0, I["nx"] - 2); j0 = np.clip(np.floor(fy).astype(int), 0, I["ny"] - 2)
    wx = fx - i0; wy = fy - j0
    a = tab[nm]
    return ((1 - wx) * (1 - wy) * a[j0, i0] + wx * (1 - wy) * a[j0, i0 + 1] + (1 - wx) * wy * a[j0 + 1, i0] + wx * wy * a[j0 + 1, i0 + 1])


def chch(a, b):
    """cosh(a)/cosh(b) without overflow (VEX sf_chch)."""
    return (np.exp(a - b) + np.exp(-a - b)) / (1.0 + np.exp(-2.0 * b))


def dirwave_np(tab, x, yv, zl, t, g, tf=0.0, ret_on=1.0):
    """VEX dirwave: returns (eta_t, U, V) for band factor g (arrays broadcast)."""
    om = tab["info"]["omega"]
    ph = om * (np.asarray(t, float) - tf)
    c = np.cos(ph); s = np.sin(ph)
    S = lambda nm: _bilinear(tab, nm, x, zl)
    eta = g * (S("er") * c + S("ei") * s)
    h = S("hh"); k = S("kk")
    ye = np.clip(h * (np.asarray(yv, float) - eta) / np.maximum(h + eta, 0.1 * h), -h, 0.0)
    prof = chch(k * (ye + h), k * h)
    U = g * (S("ur") * c + S("ui") * s) * prof
    V = g * (S("vr") * c + S("vi") * s) * prof
    if ret_on > 0.5:
        U = U + g * g * S("mx"); V = V + g * g * S("my")
    return eta, U, V


def relaxw(chi):
    c = np.clip(chi, 0.0, 1.0)
    return (np.exp(c ** 3.5) - 1.0) / (math.e - 1.0)


def rampT(t, R):
    if R <= 0:
        return 1.0
    return 0.5 - 0.5 * math.cos(math.pi * min(max(t / R, 0.0), 1.0))


def bands_np(x, zl, dts, P):
    """VEX bands50: (wdt, ftg, inb, insd)."""
    dt0 = P["dt0"]; rg = P["relax_g"]
    wdt = 0.0; ftg = 1.0; inb = 0; insd = 0
    xg = P["xg_end"]
    if P["relax_on"] > 0.5 and rg > 0.0 and x < xg:
        w = min(max(float(relaxw((xg - x) / max(xg - P["x0"], 1e-6))) * rg, 0.0), 1.0)
        wdt = max(wdt, 1.0 - (1.0 - w) ** (dts / dt0)); inb = 1
    a = P["sd0"]; b = P["W"]
    if P["sd_on"] > 0.5 and zl > a:
        chi = min(max((zl - a) / max(b - a, 1e-6), 0.0), 1.0)
        s = float(GC.smooth01((x - P["sd_gen"]) / max(P["sd_sw"] - P["sd_gen"], 1e-6)))
        wg = 1.0 - (1.0 - min(max(float(relaxw(chi)) * rg, 0.0), 1.0)) ** (dts / dt0)
        wa = 1.0 - math.exp(-P["sd_sigma"] * chi ** P["sd_pow"] * dts)
        wdt = max(wdt, wg + (wa - wg) * s); ftg *= (1.0 - s); insd = 1
    x1 = P["x0"] + P["Lx"]
    if P["abs_on"] > 0.5 and x > P["xa0"]:
        chi = min(max((x - P["xa0"]) / max(x1 - P["xa0"], 1e-6), 0.0), 1.0)
        wdt = max(wdt, 1.0 - math.exp(-P["abs_sigma"] * chi ** P["abs_pow"] * dts)); ftg = 0.0
    return wdt, ftg, inb, insd


def tapers_np(x, zl, P):
    wt = float(GC.smooth01((x - P["x0"]) / P["wall_taper_m"])) if P["wall_taper_m"] > 0 else 1.0
    ws = float(GC.smooth01((P["W"] - zl) / P["sd_taper_m"])) if (P["sd_on"] > 0.5 and P["sd_taper_m"] > 0) else 1.0
    return wt, ws


def relax_np(pl, v0, t, dts, P, tab=None, sf=None, du_abs=0.0):
    """VEX relax_apply (g50_tanklib): pl = (x, vertical, lateral) plan coordinates, v0 = (vx, vy vertical, vz lateral)."""
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
        elif P["sf_on"] > 0.5 and sf is not None:
            E = gm * float(GC.set_env(x, t, P))
            _, u, _, _, _ = GC.sf_target(x, yv, t, sf, P, E=E)
            tv = np.array([float(u.ravel()[0]), 0.0, 0.0])
    ux = tv[0]
    if inb and P["duabs_on"] > 0.5:
        ux += wt * du_abs
    return np.array([v[0] + (ux - v[0]) * wdt, v[1], v[2] + (tv[2] - v[2]) * wdt])


# ======================================================================== numpy checks
def _k_of(om, h):
    k = om * om / GC.G
    for _ in range(100):
        th = math.tanh(k * h)
        k -= (GC.G * k * th - om * om) / (GC.G * th + GC.G * k * h * (1 - th * th))
    return k


def _cg_of(om, h):
    k = _k_of(om, h)
    return om / k * 0.5 * (1 + 2 * k * h / math.sinh(2 * k * h))


def _trap(v, x):
    f = getattr(np, "trapezoid", None) or np.trapz
    return f(v, x)


def checks(case, W=GC.W_MAIN):
    import time
    t0 = time.time()
    F, info, df, x, y, m = build(case, W)
    out = dict(case=case, info={k: v for k, v in info.items() if k not in ("fields",)})
    om = info["omega"]; T = info["T"]
    A = (F["er"] + 1j * F["ei"]).T                                    # table (nx, ny)
    # 1. focus (same DirField as the table, full grid 0-262 m + x_f): eta(x_f, 0, t = nT) = sum_j A_j(x_f) because every phase is 0 there;
    #    against an independent Snell + shoaling sum a_j Ks sum_j sqrt(cos th0_j / cos th_j(x_f)); crest time at the focus = t_f (mod T)
    jf = int(np.where(np.abs(df.x - info["x_f"]) < 1e-12)[0][0])
    A_axis = df.complex_amp(np.array([0.0]))[:, 0]
    A_f = complex(A_axis[jf])
    hf = GC.H0 - (info["x_f"] - GC.X_TOE) / GC.SLOPE_S
    k0 = _k_of(om, GC.H0); kf = _k_of(om, hf); Ks = math.sqrt(_cg_of(om, GC.H0) / _cg_of(om, hf))
    th0 = np.radians(np.linspace(-info["theta_max_deg"], info["theta_max_deg"], info["n"]))
    thf = np.arcsin(k0 * np.sin(th0) / kf)
    theory = float(info["a_j"] * Ks * np.sum(np.sqrt(np.cos(th0) / np.cos(thf))))
    out["focus"] = dict(x_f=info["x_f"], h_f=hf, eta_t0=float(A_f.real), abs_A=float(abs(A_f)), phase_rad=float(np.angle(A_f)),
                        crest_time_mod_T_s=float((np.angle(A_f) / om) % T), theory_sum=theory, Ks=Ks, focal_crest_linear_m=float(abs(A_f)),
                        rel_err_vs_theory=float(A_f.real / theory - 1.0),
                        tag="computed: the table's DirField and an independent Snell/shoaling sum at the focus")
    ax = np.abs(A_axis)
    out["focus"]["axis_max_abs_A"] = dict(x=float(df.x[int(np.argmax(ax))]), value=float(ax.max()), grid_end=float(df.x[-1]),
                                          note="linear |A| on the axis peaks in the focal zone just onshore of x_f and then slowly decreases; "
                                               "the break follows from 2|A|/h reaching gamma_b as the depth decreases")
    # 1b. the table at the gauges (the generation report uses these) = the design screen linear gauges (s50_final.json)
    try:
        scr = json.load(open(GC.SCREEN_FINAL, encoding="utf8"))["configs"][GC.CASES[case]["screen_key"]]["linear"]["gauges"]
        tb_ = dict(info=info, er=F["er"], ei=F["ei"])
        gd = {}
        for xg in GC.GAUGE_X:
            for yg, key in ((0.5, "H_y0p5"), (80.0, "H_y80")):
                Ht = 2.0 * float(np.abs(_bilinear(tb_, "er", xg, yg) + 1j * _bilinear(tb_, "ei", xg, yg)))
                Hs = float(scr["%g" % xg][key])
                gd["x%g_y%g" % (xg, yg)] = dict(H_table=Ht, H_screen=Hs, rel=Ht / Hs - 1.0)
        out["gauges_vs_screen"] = dict(rows=gd, max_abs_rel=float(max(abs(v["rel"]) for v in gd.values())), tag="computed")
    except Exception as e:
        out["gauges_vs_screen"] = dict(error=repr(e)[:200])
    # 2. phase integral: Phi_j on the flat against an analytic flat part + a 4001-point slope integral
    xs_ = np.linspace(GC.X_TOE, info["x_f"], 4001)
    ks_ = np.array([_k_of(om, GC.H0 - (xx - GC.X_TOE) / GC.SLOPE_S) for xx in xs_])
    errs = []
    for j in (0, len(df.a) // 2, len(df.a) - 1):
        kx_ = np.sqrt(np.maximum(ks_ ** 2 - df.ky[j] ** 2, 0.0))
        slope_int = float(np.sum((kx_[1:] + kx_[:-1]) * 0.5 * np.diff(xs_)))
        for xq in (0.0, 50.0, 100.0, 150.0):
            ref = -slope_int - math.sqrt(max(k0 ** 2 - df.ky[j] ** 2, 0.0)) * (GC.X_TOE - xq)
            errs.append(abs(float(np.interp(xq, df.x, df.Phi[j])) - ref))
    out["phase_integral"] = dict(max_abs_err_rad=float(max(errs)), tag="computed (1 m trapezoid vs 4001-point trapezoid + analytic flat part)")
    # 3. continuity (volume flux of the target): -i om eta + d/dx q_x + d/dy q_y = 0, q = (U, V) tanh(kh)/k
    h = df.h[m]; k = df.k[m]
    qf = (np.tanh(k * h) / k)[:, None]
    U = (F["ur"] + 1j * F["ui"]).T * qf; V = (F["vr"] + 1j * F["vi"]).T * qf
    res = -1j * om * A + np.gradient(U, x, axis=0) + np.gradient(V, y, axis=1)
    scale = om * float(np.abs(A).max())
    R_ = np.abs(res[2:-2, 2:-2]); flat = x[2:-2] <= GC.X_TOE - GC.TABLE_DX     # the stencil at x 160 straddles the toe kink of k(x)
    out["continuity"] = dict(max_rel_residual_flat=float(R_[flat].max() / scale), max_rel_residual_toe_and_slope=float(R_[~flat].max() / scale),
                             scale_om_maxA=scale, note="central differences on the 1 m grid; the slope part is WKB (slowly varying amplitude)", tag="computed")
    # 4. symmetry about y = 0
    A_neg = df.complex_amp(-y)[m]; A_pos = df.complex_amp(y)[m]
    Uc_n, Vc_n = df.complex_vel(-y, depth_avg=False, z=0.0); Uc_p, Vc_p = df.complex_vel(y, depth_avg=False, z=0.0)
    out["symmetry"] = dict(max_abs_V_at_y0=float(np.abs(F["vr"][0] + 1j * F["vi"][0]).max()), max_eta_mirror_diff=float(np.abs(A_neg - A_pos).max()),
                           max_U_mirror_diff=float(np.abs(Uc_n - Uc_p).max()), max_V_antisym_diff=float(np.abs(Vc_n + Vc_p).max()), tag="computed")
    # 5. mean mass flux of the stretched linear target through x = const (half tank) and the return current
    Mx = -F["mx"].T * h[:, None]
    flux = {}
    for xq in (25.0, 50.0, 75.0, 100.0):
        i = int(np.argmin(np.abs(x - xq)))
        flux["x%g" % xq] = dict(M_without_return_m3s=float(_trap(Mx[i], y)), with_return_m3s=float(_trap(Mx[i] + F["mx"].T[i] * h[i], y)))
    out["mean_mass_flux"] = dict(per_x=flux, stretched_over_stokes=float(math.tanh(k0 * GC.H0) / (k0 * GC.H0)),
                                 max_return_current_mps=float(np.abs(F["mx"]).max()), max_lateral_return_mps=float(np.abs(F["my"]).max()),
                                 inlet_band_return_mps=dict(max=float(np.abs(F["mx"][:, x < GC.IN_X1]).max()), mean=float(np.abs(F["mx"][:, x < GC.IN_X1]).mean())),
                                 side_band_return_mps=dict(max_x=float(np.abs(F["mx"][np.ix_(y >= GC.SD0, x <= GC.SD_SW)]).max()),
                                                           max_y=float(np.abs(F["my"][np.ix_(y >= GC.SD0, x <= GC.SD_SW)]).max())),
                                 lateral_mean_absA2_x100_m2=float(np.mean(np.abs(A[int(np.argmin(np.abs(x - 100.0)))]) ** 2)),
                                 incoherent_sum_aj2_m2=float(np.sum(df.a ** 2)),
                                 implied_volume_92s_without_return_m3=float(flux["x100"]["M_without_return_m3s"] * 92.0),
                                 note="ret_on 1: zero mean mass flux through the band target (as the FLIP49 Fenton inlet, u2 = 0); stage C (du_abs) stays",
                                 tag="computed")
    # 6. interpolation: float32 table + bilinear (= the VEX) against an exact DirField on a 0.05 m grid (also 0..262 m + x_f)
    rng = np.random.default_rng(50)
    dff = dirfield(case, full_grid(info["x_f"], dx=0.05))
    cand = np.where(dff.x <= GC.TABLE_X[1])[0]
    iq = rng.choice(cand, 300); yq = rng.uniform(0.0, float(W), 300); tq = rng.uniform(0.0, T, 300)
    tab = dict(info=info, **{nm: np.asarray(F[nm], np.float32).astype(np.float64) for nm in GC.TABLE_FIELDS})
    e_np, U_np, V_np = dirwave_np(tab, dff.x[iq], 0.0 * yq + 50.0, yq, tq, 1.0, ret_on=0.0)   # vertical 50 m: above the surface -> z' = 0 (surface value)
    Af = dff.complex_amp(yq); Uf, Vf = dff.complex_vel(yq, depth_avg=False, z=0.0)
    ph = np.exp(-1j * om * tq); ii = np.arange(300)
    ex = np.real(Af[iq, ii] * ph); ux = np.real(Uf[iq, ii] * ph); vx = np.real(Vf[iq, ii] * ph)
    sc_e = float(np.abs(A).max()); sc_u = float(np.abs(F["ur"] + 1j * F["ui"]).max())
    out["interpolation"] = dict(max_rel_eta=float(np.abs(e_np - ex).max() / sc_e), max_rel_U=float(np.abs(U_np - ux).max() / sc_u),
                                max_rel_V=float(np.abs(V_np - vx).max() / sc_u), n=300,
                                note="includes the 1 m trapezoid phase error of the table against the 0.05 m reference", tag="computed")
    # 7. vertical profile: VEX profile at a time with eta_t = 0 equals the linear cosh profile (DirField.complex_vel at z)
    errs7 = []
    for z in (-2.0, -8.0, -13.0):
        Uz, Vz = df.complex_vel(y, depth_avg=False, z=z)
        Uz = Uz[m]; Vz = Vz[m]
        for xx in (20.0, 60.0, 99.0, 150.0, 200.0):
            i = int(np.argmin(np.abs(x - xx)))
            for yy in (0.0, 40.0, 100.0, 130.0):
                jj = int(np.argmin(np.abs(y - yy)))
                tq_ = (math.atan2(F["ei"][jj, i], F["er"][jj, i]) + math.pi / 2) / om
                _, Uv, Vv = dirwave_np(tab, x[i], z, y[jj], tq_, 1.0, ret_on=0.0)
                p_ = np.exp(-1j * om * tq_)
                errs7.append(max(abs(float(Uv) - np.real(Uz[i, jj] * p_)), abs(float(Vv) - np.real(Vz[i, jj] * p_))) / sc_u)
    out["vertical_profile"] = dict(max_rel_err=float(max(errs7)), tag="computed (float32 storage)")
    # 8. lateral wavenumber bound (physics answer Q2)
    out["ky_bound"] = dict(k0=float(df.k0), ky_max=float(np.abs(df.ky).max()),
                           first_lateral_zero_scale_m=float(math.pi / (df.k0 * math.sin(math.radians(info["theta_max_deg"])))),
                           tag="computed; pi/(k0 sin theta_max) ~ distance to the first lateral zero of the focal crest")
    ok = dict(focus=bool(abs(out["focus"]["rel_err_vs_theory"]) < 2e-3 and abs(out["focus"]["phase_rad"]) < 1e-9),
              gauges_vs_screen=bool((out.get("gauges_vs_screen") or {}).get("max_abs_rel", 1.0) < 2e-3),
              phase=bool(out["phase_integral"]["max_abs_err_rad"] < 0.02), continuity_flat=bool(out["continuity"]["max_rel_residual_flat"] < 5e-3),
              symmetry=bool(out["symmetry"]["max_abs_V_at_y0"] < 1e-9 and out["symmetry"]["max_eta_mirror_diff"] < 1e-9
                            and out["symmetry"]["max_V_antisym_diff"] < 1e-9),
              return_zero=bool(all(abs(v["with_return_m3s"]) < 1e-6 * max(1.0, abs(v["M_without_return_m3s"])) for v in flux.values())),
              interpolation=bool(max(out["interpolation"]["max_rel_eta"], out["interpolation"]["max_rel_U"], out["interpolation"]["max_rel_V"]) < 0.02),
              vertical=bool(out["vertical_profile"]["max_rel_err"] < 1e-4))
    out["ok"] = ok
    out["all_ok"] = bool(all(ok.values()))
    out["cpu_s"] = round(time.time() - t0, 2)
    return out


def main():
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    opt = {v[2:].split("=", 1)[0]: (v.split("=", 1)[1] if "=" in v else "1") for v in sys.argv[1:] if v.startswith("--")}
    if len(a) < 2 or a[1] not in GC.CASES:
        print(__doc__); sys.exit(1)
    W = float(opt.get("W", GC.W_MAIN))
    if a[0] == "write":
        p, sha, ch, info = write(a[1], W)
        print("table", p, "sha256", sha[:16], "content", ch[:16], "omega %.6f a_j %.5f" % (info["omega"], info["a_j"]))
    elif a[0] == "check":
        o = checks(a[1], W)
        os.makedirs(GC.PLAN_DIR, exist_ok=True)
        p = GC.PLAN_DIR + "/table_check_%s.json" % a[1]
        json.dump(o, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
        print(json.dumps({k: o[k] for k in ("ok", "all_ok", "cpu_s")}), "->", p)
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
