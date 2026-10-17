# -*- coding: utf-8 -*-
"""FLIP51 idea X2B: choose the focus x_f (and t_f) of the X2 direction set so that the converged crest reaches breaking AT the focus.
2026-10-17 written new (Claude). numpy only, py -3.10 -B. Read only on every flip50 / flip51 file and on the run folders.
Writes only under Unity/Build/FLIP51/_scratch/x2b/ (git-ignored).

X2B = X2 (T 7 s, +-linspace(2, 85, 17) deg Gaussian lobes about +-60 deg sigma 28 deg, 34 components, a_sum 6.331240 m, D19B tank)
with ONE change: the focus point x_f (and the table built for it). Nothing here builds a table or a cfg.

usage (outputs Unity/Build/FLIP51/_scratch/x2b/<name>.json):
  py -3.10 -B x51b_screen.py cal        FLIP centre-line crest envelope of X2 (T 7) and DM1A (T 12) vs their linear / 2nd-order fields
  py -3.10 -B x51b_screen.py calap      ray-supply ('aperture') check: FLIP / supplied linear amplitude along the axis (X2, DM1A)
  py -3.10 -B x51b_screen.py screen     candidate x_f, supply fixed at the focus (superseded by screen2)
  py -3.10 -B x51b_screen.py screen2    candidate x_f, supply per axis point (the validated rule); screen2DM = DM1A check
  py -3.10 -B x51b_screen.py supplyfix  x_f x side-band generation end sd_gen (a second change) -> focal supply, break x, band k|A|
  py -3.10 -B x51b_screen.py detail     chosen configurations: break / summit metrics (depth-capped), curl widening, lattice, Iribarren
Result (2026-10-17): with the X2 bands (sd_gen 180.25 / sd_sw 210.25) no x_f in 220-300 m makes the converged crest break at the focus:
  the high-angle rays to a shoreward focus leave the side band where it absorbs, the supplied focal crest falls as fast as the depth
  (Hc / h_f 0.42 -> 0.53 for x_f 220 -> 280) and the break stays at x 308-316 m (h ~4 m, Hc ~3 m). With sd_gen 210.25 / sd_sw 240.25
  the supply returns (ap >= 0.97) and the break moves to x ~282 m (h 6.9, Hc 5.6) for any x_f 260-280; x_f 275.25 puts it ~7 m past the focus.
Tags in the outputs: [measured] (read from FLIP records), [computed] (linear / 2nd-order field), [chosen], [guess].
"""
import os, sys, json, math, glob, time

sys.dont_write_bytecode = True
ROOT = "G:/Unity/GreatWave_2026_Fresh"
for p in (ROOT + "/Tools/GWWaveGen/flip50", ROOT + "/Tools/GWWaveGen/flip51", ROOT + "/Tools/GWWaveGen/flip51/cross"):
    if p not in sys.path:
        sys.path.append(p)
import numpy as np                  # noqa: E402
import g50_dirfield as DF           # noqa: E402  read only
import x51_common as XC             # noqa: E402  read only
import c51_screen as CS             # noqa: E402  read only (2nd-order Field)
import e51_metrics as EM            # noqa: E402  read only

OUT = ROOT + "/Unity/Build/FLIP51/_scratch/x2b"
RUN_X2 = ROOT + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5"
RUN_DM1A = ROOT + "/Unity/Build/FLIP50/runs/DM1A_D19B_T12_th80_dp0p5"
BED = dict(h0=19.0, x_toe=160.25, s=10.0, kind="beach")
A_SUM = XC.A_SUM


def depth(x):
    return 19.0 - np.maximum(np.asarray(x, float) - 160.25, 0.0) / 10.0


def jd(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    XC.jdump(o, p)


# ------------------------------------------------------------------ FLIP centre-line envelope [measured]
def centre_rows(rd, eta0, t_lo, t_hi, x_lo=140.0, x_hi=365.0):
    """centre-line height (3x3 median of the mirrored field at y = 0.5 m) minus eta0 for every frame in [t_lo, t_hi].
    -> t (nt,), x (nx,), e (nt, nx). Later launch wins for overlapping frames."""
    rows = {}
    for p in sorted(glob.glob(os.path.join(rd, "hf_c*_b*.npz"))):
        with np.load(p) as d:
            t = np.array(d["t"]); fr = np.array(d["frames"])
            sel = (t >= t_lo - 1e-6) & (t <= t_hi + 1e-6)
            if not sel.any():
                continue
            meta = json.loads(str(d["meta"]))
            a = np.array(d["eta"][sel, 0:3, :], np.float64)
        x = meta["x0"] + meta["dx"] * np.arange(a.shape[-1])
        for i, f in enumerate(fr[sel]):
            rows[int(f)] = a[i]
    fs = sorted(rows)
    x = meta["x0"] + meta["dx"] * np.arange(rows[fs[0]].shape[-1])
    m = (x >= x_lo) & (x <= x_hi)
    out = []
    for f in fs:
        a = rows[f]                                    # (3, nx) rows y 0.5, 1.5, 2.5
        st = np.stack([a[1], a[0], a[0], a[1]], 0)     # y -1.5, -0.5, 0.5, 1.5 (mirror)
        r3 = st[1:4]                                   # rows -0.5, 0.5, 1.5 around y = 0.5
        p_ = np.pad(r3, ((0, 0), (1, 1)), mode="edge")
        nb = np.stack([p_[:, j:j + r3.shape[1]] for j in range(3)], 0).reshape(9, -1)
        out.append(np.nanmedian(nb, axis=0)[m] - eta0)
    t = np.array([(f - 1) / 24.0 for f in fs])
    return t, x[m], np.array(out)


def envelope_by_period(t, x, e, T, ns, t_f=0.0):
    """per period n (window t_f + nT +- T/2): max over t of the centre height at each x, and the time of that max relative to t_f + nT."""
    res = {}
    for n in ns:
        c = t_f + n * T
        s = (t >= c - 0.5 * T) & (t < c + 0.5 * T)
        if s.sum() < 0.8 * 24 * T:
            continue
        sub = e[s]
        i = np.nanargmax(sub, axis=0)
        res[int(n)] = dict(env=np.nanmax(sub, axis=0), tmax=t[s][i] - c)
    return res


def linear_axis(T, th, w, a_sum, x_f, x):
    df = DF.DirField(T, th, w, a_sum, x, BED, x_f)
    A = df.complex_amp(np.array([0.0]))[:, 0]
    om = 2 * math.pi / T
    t_cr = np.angle(A) / om                  # crest passes x at t_f + t_cr (mod T)
    return df, np.abs(A), t_cr


def cal():
    t0 = time.time()
    out = {}
    # X2
    eta0 = 0.075945
    th, w = XC.components("X2")
    t, x, e = centre_rows(RUN_X2, eta0, 38.5, 73.5)
    env = envelope_by_period(t, x, e, 7.0, range(6, 11))
    xg = np.union1d(np.arange(0.0, 365.0, 0.5), [220.25])
    df, Al, tcr = linear_axis(7.0, th, w, A_SUM, 220.25, xg)
    # 2nd-order crest along the axis (max over one period)
    xs = np.arange(0.0, 360.0 + 1e-9, 1.0); ys = np.arange(0.0, 6.0 + 1e-9, 1.0)
    F = CS.Field(7.0, th, w, 220.25, xs, ys)
    ts = np.linspace(-3.5, 3.5, 85)
    E2 = np.array([F.eta(A_SUM, tt, 2)[:, 0] for tt in ts]); A2 = E2.max(0); t2 = ts[E2.argmax(0)]
    rows = []
    for xq in np.arange(150.0, 361.0, 5.0):
        j = int(np.argmin(np.abs(x - (xq + 0.5))))      # hf cell centres at .5
        ev = [env[n]["env"][j] for n in env]; tv = [env[n]["tmax"][j] for n in env]
        al = float(np.interp(xq, xg, Al)); a2 = float(np.interp(xq, xs, A2))
        rows.append(dict(x=xq, h=float(depth(xq)), flip_med=float(np.median(ev)), flip_min=float(np.min(ev)), flip_max=float(np.max(ev)),
                         flip_tmax_med=float(np.median(tv)), lin=al, lin_tcr=float(np.interp(xq, xg, tcr)), o2=a2,
                         o2_t=float(np.interp(xq, xs, t2)), r_lin=float(np.median(ev)) / al if al > 0 else None,
                         r_o2=float(np.median(ev)) / a2 if a2 > 0 else None, flip_over_h=float(np.median(ev)) / max(float(depth(xq)), 1e-6)))
    out["X2"] = dict(rows=rows, periods=sorted(env), eta0=eta0, lin_axis_max_x=float(xg[np.argmax(np.where((xg > 150) & (xg < 300), Al, 0))]),
                     tag="[measured] FLIP centre-line envelope (3x3 median, mirrored, y 0.5 m) per period n 6-10, median over periods; "
                         "[computed] linear |A(x,0)| and 2nd-order max crest of the same set at x_f 220.25")
    # DM1A (T 12, uniform +-80, 30 components)
    eta0d = 0.07596755
    thd, wd = DF.components(80.0, 30, "uniform")
    t, x, e = centre_rows(RUN_DM1A, eta0d, 42.0, 90.0)
    envd = envelope_by_period(t, x, e, 12.0, range(4, 8))
    dfd, Ald, tcrd = linear_axis(12.0, thd, wd, A_SUM, 220.25, xg)
    Fd = CS.Field(12.0, thd, wd, 220.25, xs, ys)
    ts = np.linspace(-6.0, 6.0, 121)
    E2 = np.array([Fd.eta(A_SUM, tt, 2)[:, 0] for tt in ts]); A2d = E2.max(0); t2d = ts[E2.argmax(0)]
    rows = []
    for xq in np.arange(150.0, 361.0, 5.0):
        j = int(np.argmin(np.abs(x - (xq + 0.5))))
        ev = [envd[n]["env"][j] for n in envd]; tv = [envd[n]["tmax"][j] for n in envd]
        al = float(np.interp(xq, xg, Ald)); a2 = float(np.interp(xq, xs, A2d))
        rows.append(dict(x=xq, h=float(depth(xq)), flip_med=float(np.median(ev)), flip_min=float(np.min(ev)), flip_max=float(np.max(ev)),
                         flip_tmax_med=float(np.median(tv)), lin=al, lin_tcr=float(np.interp(xq, xg, tcrd)), o2=a2, o2_t=float(np.interp(xq, xs, t2d)),
                         r_lin=float(np.median(ev)) / al if al > 0 else None, r_o2=float(np.median(ev)) / a2 if a2 > 0 else None,
                         flip_over_h=float(np.median(ev)) / max(float(depth(xq)), 1e-6)))
    out["DM1A"] = dict(rows=rows, periods=sorted(envd), eta0=eta0d,
                       lin_axis_max_x=float(xg[np.argmax(np.where((xg > 150) & (xg < 300), Ald, 0))]),
                       tag="[measured] as X2, periods n 4-7 (t 42-90 s); [computed] linear / 2nd-order of uniform +-80 deg, 30 comps, T 12, x_f 220.25")
    out["cpu_s"] = time.time() - t0
    jd(out, OUT + "/cal.json")
    for nm in ("X2", "DM1A"):
        print("==", nm, "periods", out[nm]["periods"], "lin axis max x", out[nm]["lin_axis_max_x"])
        for r in out[nm]["rows"]:
            print("x %5.1f h %5.2f | FLIP %5.2f [%5.2f-%5.2f] t %+5.2f | lin %5.2f t %+5.2f | o2 %5.2f t %+5.2f | FLIP/lin %5.2f FLIP/o2 %5.2f FLIP/h %5.2f" % (
                r["x"], r["h"], r["flip_med"], r["flip_min"], r["flip_max"], r["flip_tmax_med"], r["lin"], r["lin_tcr"], r["o2"], r["o2_t"],
                r["r_lin"] or 0, r["r_o2"] or 0, r["flip_over_h"]))
    print("cpu %.1f s" % out["cpu_s"])


# ------------------------------------------------------------------ candidate screen [computed] + calibration rules
GAMMA = (0.76, 0.82, 0.88)          # crest / still depth at the measured centre break onsets: X2 (x 317-322 m) 0.76 / 0.77 / 0.84 and
                                    # DM1A (x 253-260 m) 0.81 / 0.84 / 0.85 / 0.85 (pana/events.json on_eta / depth_on) [measured]


def kh_of(T, h):
    om = 2 * math.pi / T
    return float(DF.kdisp(om, max(float(h), 0.05))) * max(float(h), 0.05)


def ursell(T, A, h):
    """Ur = (H / h) / (k h)^2 with H = 2 A (linear crest amplitude A)."""
    kh = kh_of(T, h)
    return (2.0 * A / h) / (kh * kh)


R_FIT = dict(a=0.98, b=0.075, tag="[guess] FLIP crest / linear |A| on the axis vs Ursell: X2 summit (Ur 0.38 -> 1.01) and DM1A pre-break "
                                   "(Ur 1.8 -> 1.11, Ur 4.35 -> 1.31) [measured in cal.json]; r = a + b Ur, scatter +-0.07")


def r_of(Ur, d=0.0):
    return R_FIT["a"] + R_FIT["b"] * Ur + d


def miche_limit(T, h, beta):
    """'3D Miche' crest limit: Hc_b = beta * 0.142 tanh(kh) L (beta calibrated where both runs broke, kh ~0.52)."""
    om = 2 * math.pi / T
    k = float(DF.kdisp(om, max(h, 0.05)))
    return beta * 0.142 * math.tanh(k * h) * 2 * math.pi / k


def field(T, th, w, x_f, x, y):
    df = DF.DirField(T, th, w, 1.0, x, BED, x_f)
    E = (df.Aj * np.exp(1j * df.Phi))[:, :, None] * np.exp(1j * df.ky[:, None] * y[None, :])[:, None, :]    # (n, nx, ny), unit a_sum
    return df, E


def axis_profile(df, E, fr, a_sum, T):
    """effective (aperture-weighted) linear axis amplitude, crest time, predicted FLIP crest (central r and +-0.07) and Hc / h."""
    A = a_sum * np.tensordot(fr, E[:, :, 0], axes=(0, 0))          # y index 0 = 0.5 m
    om = 2 * math.pi / T
    out = []
    for i, xx in enumerate(df.x):
        h = float(df.h[i])
        if h < 0.5:
            out.append(None); continue
        a = float(abs(A[i])); Ur = ursell(T, a, h)
        out.append(dict(x=float(xx), h=h, A=a, t=float(np.angle(A[i]) / om), Ur=Ur, kh=kh_of(T, h),
                        Hc=[a * r_of(Ur, -0.07), a * r_of(Ur), a * r_of(Ur, 0.07)]))
    return out


def first_cross(prof, x_lo, crit):
    """first x >= x_lo where crit(row) >= 0 (linear interpolation of the margin)."""
    prev = None
    for r in prof:
        if r is None or r["x"] < x_lo:
            continue
        m = crit(r)
        if m >= 0:
            if prev is None:
                return r["x"]
            x0, m0 = prev
            return x0 + (r["x"] - x0) * (-m0) / (m - m0)
        prev = (r["x"], m)
    return None


def lateral_metrics(df, E, fr, a_sum, T, x_star, scale, fwin=(20.0, 20.0)):
    """e51 hf_metrics + N1 on the effective linear field at the instant its axis crest is at x_star, scaled so that the axis crest equals
    the predicted FLIP crest (scale = r). -> metrics dict (W in units of the scaled Hc)."""
    import x51_ana as XA            # read only (scipy)
    om = 2 * math.pi / T
    A = a_sum * np.tensordot(fr, E, axes=(0, 0))                  # (nx, ny)
    i = int(np.argmin(np.abs(df.x - x_star)))
    t = float(np.angle(A[i, 0]) / om)
    e = scale * np.real(A * np.exp(-1j * om * t))                 # (nx, ny)
    meta = dict(x0=float(df.x[0]), dx=float(df.x[1] - df.x[0]), z0=0.5, dz=1.0)
    eh = e.T.copy()                                               # (ny, nx) half tank
    eh[(0.5 + np.arange(eh.shape[0])) > 95.0, :] = np.nan        # interior only, as the judge
    m = EM.hf_metrics(eh, meta, 0.0, xwin=(x_star - fwin[0], x_star + fwin[1]))
    if not m or "W50" not in m:
        return m
    m["miss"], m["miss_per"] = EM.score_vs_target(m)
    iso = XA.n1_isolation(EM.median3(eh), meta, m)
    m["N1"] = iso.get("N1"); m["N1_at"] = iso.get("at")
    m["W50_m"] = m["W50"] * m["Hc"]; m["W80_m"] = m["W80"] * m["Hc"]
    m["t_star"] = t
    return m


def break_map(df, E, fr, a_sum, T, x_lo, gamma):
    """predicted crest-to-depth map R(x, y) = r(x) |A_eff(x, y)| / h(x) (r from the axis Ursell; the time max of a monochromatic field is |A|):
    first x where any |y| <= 95 m reaches gamma and its y."""
    A = a_sum * np.abs(np.tensordot(fr, E, axes=(0, 0)))          # (nx, ny)
    y = 0.5 + np.arange(A.shape[1])
    ok = y <= 95.0
    res = dict(first_any=None, first_any_y=None)
    R = np.full(A.shape, np.nan)
    for i, xx in enumerate(df.x):
        h = float(df.h[i])
        if h < 0.5 or xx < x_lo:
            continue
        Ur = ursell(T, float(A[i, 0]), h)
        R[i] = r_of(Ur) * A[i] / h
    for i, xx in enumerate(df.x):
        if not np.isfinite(R[i, 0]):
            continue
        j = np.where(ok & (R[i] >= gamma))[0]
        if len(j):
            res["first_any"] = float(xx); res["first_any_y"] = float(y[j[np.argmax(R[i, j])]]); break
    return R, y, res


def half_width_ge(R, y, df, x, gamma):
    i = int(np.argmin(np.abs(df.x - x)))
    if not np.isfinite(R[i, 0]) or R[i, 0] < gamma:
        return 0.0
    j = 0
    while j + 1 < len(y) and R[i, j + 1] >= gamma:
        j += 1
    return float(y[j])


def screen(cands=None, T=7.0, setname="X2", tag=""):
    t0 = time.time()
    if setname == "X2":
        th, w = XC.components("X2")
    else:
        th, w = DF.components(80.0, 30, "uniform")
    cands = cands or [220.25, 240.25, 250.25, 255.25, 260.25, 265.25, 270.25, 280.25]
    y = 0.5 + np.arange(140.0)
    res = dict(set=setname, T=T, rule=dict(gamma=GAMMA, r_fit=R_FIT,
                                           aperture="g50_dirfield.aperture(W 140, side band 45, inlet end 100, gen 180.25, switch 210.25) "
                                                    "per component; the effective field weights each component by its generated fraction",
                                           instant="the axis crest at x* = min(predicted break x (gamma central), x of the predicted crest maximum)"),
               cands=[])
    b_x2 = [e_ / miche_limit(7.0, h_, 1.0) for e_, h_ in ((2.1, 2.775), (2.522, 3.275), (2.5, 2.975))]
    b_dm = [e_ / miche_limit(12.0, h_, 1.0) for e_, h_ in ((7.97, 9.375), (7.581, 9.075), (7.804, 9.675), (7.887, 9.375))]
    beta = (min(b_x2 + b_dm), float(np.median(b_x2 + b_dm)), max(b_x2 + b_dm))
    res["rule"]["beta_miche3d"] = dict(X2=b_x2, DM1A=b_dm, range=beta, tag="[measured] Hc at centre onset / (0.142 tanh(kh) L)")
    keep = ("Hc", "x_pk", "W20", "W50", "W80", "W95", "K", "S1", "S2", "ring_max", "Lx50", "A50", "miss", "N1", "N1_at", "W50_m", "W80_m", "t_star")
    for x_f in cands:
        x = np.arange(0.5, min(x_f + 95.0, 349.0), 1.0)
        df, E = field(T, th, w, x_f, x, y)
        ap = DF.aperture(df, 140.0, 45.0, 100.0, 180.25, 210.25)
        fr = np.array([c["frac"] for c in ap["comps"]])
        prof = axis_profile(df, E, fr, A_SUM, T)
        prof_full = axis_profile(df, E, np.ones_like(fr), A_SUM, T)
        rows = [r for r in prof if r is not None and r["x"] >= 150.0]
        jmax = int(np.argmax([r["Hc"][1] for r in rows]))
        jlin = int(np.argmax([r["A"] for r in rows]))
        i_f = int(np.argmin(np.abs(df.x - x_f)))
        A_f = prof[i_f]["A"]; A_f_full = prof_full[i_f]["A"]
        xb = {}
        for g in GAMMA:
            for si, nm in enumerate(("lo", "mid", "hi")):
                xb["g%.2f_r%s" % (g, nm)] = first_cross(prof, 150.0, lambda r, g=g, si=si: r["Hc"][si] - g * r["h"])
        xm = {}
        for b in beta:
            xm["beta%.2f" % b] = first_cross(prof, 150.0, lambda r, b=b: r["Hc"][1] - miche_limit(T, r["h"], b))
        xb_c = xb["g0.82_rmid"]
        x_star = min(xb_c if xb_c is not None else 1e9, rows[jmax]["x"])
        r_star = prof[int(np.argmin(np.abs(df.x - x_star)))]
        lm = lateral_metrics(df, E, fr, A_SUM, T, x_star, r_of(r_star["Ur"]))
        lm_f = lateral_metrics(df, E, fr, A_SUM, T, x_f, r_of(prof[i_f]["Ur"]))
        R, yy, bm = break_map(df, E, fr, A_SUM, T, 150.0, GAMMA[1])
        hw = {}
        if xb_c is not None:
            for dx_ in (0.0, 5.0, 10.0, 20.0):
                hw["xb+%g" % dx_] = half_width_ge(R, yy, df, xb_c + dx_, GAMMA[1])
        c = dict(x_f=x_f, h_f=float(XC.bed_h(x_f)), kh_f=kh_of(T, float(XC.bed_h(x_f))),
                 aperture=ap["frac"], comp_frac={"%.1f" % cc["theta_deg"]: round(cc["frac"], 3) for cc in ap["comps"] if cc["theta_deg"] > 0},
                 A_f_design=A_f_full, A_f_eff=A_f, Ur_f=prof[i_f]["Ur"], Hc_f_pred=prof[i_f]["Hc"],
                 Hc_over_h_f=[v / prof[i_f]["h"] for v in prof[i_f]["Hc"]],
                 lin_max_x=rows[jlin]["x"], lin_max_A=rows[jlin]["A"], pred_max_x=rows[jmax]["x"], pred_max_Hc=rows[jmax]["Hc"],
                 x_break_gamma=xb, x_break_miche3d=xm, x_star=x_star, Hc_star=r_star["Hc"], h_star=r_star["h"],
                 lateral_at_xstar={k: lm.get(k) for k in keep}, lateral_at_xf={k: lm_f.get(k) for k in keep},
                 offaxis=dict(first_any_x=bm["first_any"], first_any_y=bm["first_any_y"], half_width_ge_gamma=hw),
                 axis=[dict(x=r["x"], h=r["h"], A=round(r["A"], 3), Hc=[round(v, 3) for v in r["Hc"]], Hc_over_h=round(r["Hc"][1] / r["h"], 3),
                            t=round(r["t"], 3), Ur=round(r["Ur"], 3)) for r in rows if (r["x"] - 0.5) % 5 == 0])
        res["cands"].append(c)
        print("x_f %6.2f h_f %5.2f kh %.2f ap %.3f | A_f design %.2f eff %.2f Ur %.2f Hc_f %.2f [%.2f-%.2f] Hc/h_f %.2f | lin max x %.1f (%.2f) pred max x %.1f (%.2f)" % (
            x_f, c["h_f"], c["kh_f"], ap["frac"], A_f_full, A_f, c["Ur_f"], c["Hc_f_pred"][1], c["Hc_f_pred"][0], c["Hc_f_pred"][2], c["Hc_over_h_f"][1],
            c["lin_max_x"], c["lin_max_A"], c["pred_max_x"], c["pred_max_Hc"][1]))
        print("    break x (Hc >= g h):", {k: (round(v, 1) if v is not None else None) for k, v in xb.items()})
        print("    break x (3D Miche):", {k: (round(v, 1) if v is not None else None) for k, v in xm.items()}, "| off-axis first", bm["first_any"],
              "y", bm["first_any_y"], "| half width >= g:", hw)
        for nm, m in (("x*", lm), ("x_f", lm_f)):
            print("    %-3s %.1f: Hc %.2f W50 %.2f (%.1f m) W80 %.2f W95 %.2f K %.2f S2 %.2f ring %.2f Lx50 %.2f N1 %.2f at %s miss %.2f" % (
                nm, x_star if nm == "x*" else x_f, m["Hc"], m["W50"], m["W50_m"], m["W80"], m["W95"], m["K"], m["S2"], m.get("ring_max", float("nan")),
                m["Lx50"], m["N1"] or 0, m.get("N1_at"), m["miss"]))
    res["cpu_s"] = time.time() - t0
    jd(res, OUT + "/screen%s.json" % tag)
    print("beta", [round(v, 3) for v in beta], "cpu %.1f s" % res["cpu_s"])
    return res


def local_aperture_profile(T, th, w, x_f, xs):
    """for every axis point x_q: the band-supply fraction f_j(x_q) of each component's ray through (x_q, 0) (g50_dirfield.aperture with the
    ray start moved to x_q; the phases stay referenced to x_f), and the supplied linear amplitude |sum_j f_j A_j e^{i Phi_j}| at (x_q, 0)."""
    x = np.union1d(np.arange(0.0, 349.0, 0.5), [x_f])
    df = DF.DirField(T, th, w, A_SUM, x, BED, x_f)
    out = []
    for xq in xs:
        i = int(np.argmin(np.abs(df.x - xq)))
        full = df.Aj[:, i] * np.exp(1j * df.Phi[:, i])
        df.x_f = float(df.x[i])
        ap = DF.aperture(df, 140.0, 45.0, 100.0, 180.25, 210.25)
        df.x_f = float(x_f)
        fr = np.array([c["frac"] for c in ap["comps"]])
        out.append(dict(x=float(df.x[i]), lin=float(abs(full.sum())), supplied=float(abs((fr * full).sum())), ap=ap["frac"]))
    return out


def cal_aperture():
    """does the ray-supply (aperture) loss explain FLIP / linear < 1 past the X2 focus? (X2 and DM1A, their own x_f 220.25)."""
    cal_ = json.load(open(OUT + "/cal.json", encoding="utf-8"))
    res = {}
    for nm, T, (th, w) in (("X2", 7.0, XC.components("X2")), ("DM1A", 12.0, DF.components(80.0, 30, "uniform"))):
        rows = cal_[nm]["rows"]
        xs = [r["x"] for r in rows if 150 <= r["x"] <= 330]
        lp = local_aperture_profile(T, th, w, 220.25, xs)
        out = []
        for r, l in zip([r for r in rows if 150 <= r["x"] <= 330], lp):
            out.append(dict(x=r["x"], h=r["h"], flip=r["flip_med"], lin=l["lin"], supplied=l["supplied"], ap=l["ap"],
                            flip_over_lin=r["flip_med"] / l["lin"], flip_over_supplied=r["flip_med"] / l["supplied"] if l["supplied"] > 0 else None))
            print("%-5s x %5.1f h %5.2f | FLIP %5.2f lin %5.2f supplied %5.2f (ap %.3f) | FLIP/lin %.2f FLIP/supplied %.2f" % (
                nm, r["x"], r["h"], r["flip_med"], l["lin"], l["supplied"], l["ap"], out[-1]["flip_over_lin"], out[-1]["flip_over_supplied"] or 0))
        res[nm] = out
    jd(res, OUT + "/cal_aperture.json")


def supply_weights(df, x_q):
    """supply fraction f_j of each component's ray through (x_q, 0) (g50_dirfield.aperture with the ray start at x_q)."""
    xf0 = df.x_f
    df.x_f = float(x_q)
    try:
        ap = DF.aperture(df, 140.0, 45.0, 100.0, 180.25, 210.25)
    finally:
        df.x_f = xf0
    return np.array([c["frac"] for c in ap["comps"]]), ap["frac"]


def screen2(cands=None, T=7.0, setname="X2", tag="2"):
    """as screen(), with the ray supply evaluated at EVERY axis point (validated on X2: FLIP / supplied 0.98-1.02 at x 255-285 m where
    FLIP / linear was 0.80-0.86, cal_aperture.json [measured]) and the lateral field at x* built with the supply weights of x*."""
    t0 = time.time()
    th, w = (XC.components("X2") if setname == "X2" else DF.components(80.0, 30, "uniform"))
    cands = cands or [220.25, 230.25, 240.25, 250.25, 260.25, 270.25, 280.25, 290.25, 300.25]
    y = 0.5 + np.arange(140.0)
    keep = ("Hc", "x_pk", "W20", "W50", "W80", "W95", "K", "S1", "S2", "ring_max", "Lx50", "A50", "miss", "N1", "N1_at", "W50_m", "W80_m", "t_star")
    res = dict(set=setname, T=T, rule=dict(gamma=GAMMA, r_fit=R_FIT, supply="per axis point (screen2)"), cands=[])
    om = 2 * math.pi / T
    for x_f in cands:
        x = np.arange(0.5, 340.0, 1.0)
        df, E = field(T, th, w, x_f, x, y)
        rows = []
        fr_at = {}
        for i, xx in enumerate(df.x):
            h = float(df.h[i])
            if xx < 150.0 or h < 1.0:
                continue
            fr, ap = supply_weights(df, xx)
            fr_at[float(xx)] = fr
            Ac = A_SUM * complex(np.dot(fr, E[:, i, 0]))
            Afull = A_SUM * complex(E[:, i, 0].sum())
            a = abs(Ac); Ur = ursell(T, a, h)
            rows.append(dict(x=float(xx), h=h, A=a, A_full=abs(Afull), ap=ap, t=float(np.angle(Ac) / om), Ur=Ur,
                             Hc=[a * r_of(Ur, -0.07), a * r_of(Ur), a * r_of(Ur, 0.07)]))
        i_f = int(np.argmin([abs(r["x"] - x_f) for r in rows]))
        xb = {}
        for g in GAMMA:
            for si, nm in enumerate(("lo", "mid", "hi")):
                xb["g%.2f_r%s" % (g, nm)] = first_cross(rows, 150.0, lambda r, g=g, si=si: r["Hc"][si] - g * r["h"])
        xb_c = xb["g0.82_rmid"]
        sel = [r for r in rows if r["x"] <= (xb_c if xb_c is not None else 330.0)]
        jmax = int(np.argmax([r["Hc"][1] for r in sel]))
        x_sum = sel[jmax]["x"]
        out_lat = {}
        for nm, xq in (("summit", x_sum), ("break", xb_c), ("focus", x_f)):
            if xq is None:
                continue
            xq_ = float(df.x[int(np.argmin(np.abs(df.x - xq)))])
            fr = fr_at.get(xq_)
            if fr is None:
                fr, _ = supply_weights(df, xq_)
            r_ = rows[int(np.argmin([abs(r["x"] - xq_) for r in rows]))]
            m = lateral_metrics(df, E, fr, A_SUM, T, xq_, r_of(r_["Ur"]))
            out_lat[nm] = dict(x=xq_, **{k: m.get(k) for k in keep})
        c = dict(x_f=x_f, h_f=float(XC.bed_h(x_f)), ap_f=rows[i_f]["ap"], A_f_full=rows[i_f]["A_full"], A_f_sup=rows[i_f]["A"],
                 Hc_f=rows[i_f]["Hc"], Hc_over_h_f=[v / rows[i_f]["h"] for v in rows[i_f]["Hc"]], x_summit=x_sum, Hc_summit=sel[jmax]["Hc"],
                 h_summit=sel[jmax]["h"], x_break=xb, lateral=out_lat,
                 axis=[dict(x=r["x"], h=r["h"], A=round(r["A"], 3), ap=round(r["ap"], 3), Hc=[round(v, 3) for v in r["Hc"]],
                            Hc_over_h=round(r["Hc"][1] / r["h"], 3), t=round(r["t"], 3)) for r in rows if (r["x"] - 0.5) % 5 == 0])
        res["cands"].append(c)
        print("x_f %6.2f h_f %5.2f ap_f %.3f | A_f full %.2f supplied %.2f Hc_f %.2f [%.2f-%.2f] Hc/h_f %.2f | summit x %.1f Hc %.2f (h %.1f) | break(0.82) %s [%s-%s]" % (
            x_f, c["h_f"], c["ap_f"], c["A_f_full"], c["A_f_sup"], c["Hc_f"][1], c["Hc_f"][0], c["Hc_f"][2], c["Hc_over_h_f"][1], x_sum, sel[jmax]["Hc"][1],
            sel[jmax]["h"], None if xb_c is None else round(xb_c, 1),
            None if xb["g0.76_rhi"] is None else round(xb["g0.76_rhi"], 1), None if xb["g0.88_rlo"] is None else round(xb["g0.88_rlo"], 1)))
        for nm, m in out_lat.items():
            print("    %-6s x %5.1f: Hc %.2f W50 %.2f (%.1f m) W80 %.2f W95 %.2f K %.2f S2 %.2f ring %.2f Lx50 %.2f N1 %.2f at %s miss %.2f" % (
                nm, m["x"], m["Hc"], m["W50"], m["W50_m"], m["W80"], m["W95"], m["K"], m["S2"], m.get("ring_max") or float("nan"),
                m["Lx50"], m["N1"] or 0, m.get("N1_at"), m["miss"]))
    res["cpu_s"] = time.time() - t0
    jd(res, OUT + "/screen%s.json" % tag)
    print("cpu %.1f s" % res["cpu_s"])
    return res


def supplyfix():
    """what a SECOND change would need: the side band generating further shoreward (sd_gen, sd_sw = sd_gen + 30 m; table x range must then
    cover sd_sw). Per (x_f, sd_gen): focal supply, predicted focal crest / h, break x by the gamma rule (supply per axis point with that
    band), linear band steepness k|A| in the generating side band (G4 limit 0.40) and the first off-axis point reaching gamma."""
    th, w = XC.components("X2")
    T = 7.0; om = 2 * math.pi / T
    y = 0.5 + np.arange(140.0)
    out = []
    for x_f in (260.25, 270.25, 275.25, 280.25):
        x = np.arange(0.5, 340.0, 1.0)
        df, E = field(T, th, w, x_f, x, y)
        Afull = A_SUM * np.abs(E.sum(0))                         # (nx, ny)
        kA = df.k[:, None] * Afull
        for sg in (180.25, 210.25, 230.25, 250.25, 270.25):
            ssw = sg + 30.0
            def sup(xq):
                xf0 = df.x_f; df.x_f = float(xq)
                try:
                    ap = DF.aperture(df, 140.0, 45.0, 100.0, sg, ssw)
                finally:
                    df.x_f = xf0
                return np.array([c["frac"] for c in ap["comps"]]), ap["frac"]
            rows = []
            for i, xx in enumerate(df.x):
                h = float(df.h[i])
                if xx < 150.0 or h < 1.0:
                    continue
                fr, ap = sup(xx)
                a = abs(A_SUM * complex(np.dot(fr, E[:, i, 0]))); Ur = ursell(T, a, h)
                rows.append(dict(x=float(xx), h=h, A=a, ap=ap, Hc=[a * r_of(Ur, -0.07), a * r_of(Ur), a * r_of(Ur, 0.07)]))
            i_f = int(np.argmin([abs(r["x"] - x_f) for r in rows]))
            xb = {"g%.2f_r%s" % (g, nm): first_cross(rows, 150.0, lambda r, g=g, si=si: r["Hc"][si] - g * r["h"])
                  for g in GAMMA for si, nm in enumerate(("lo", "mid", "hi"))}
            xbc = xb["g0.82_rmid"]
            sel = [r for r in rows if r["x"] <= (xbc if xbc is not None else 330.0)]
            jm = int(np.argmax([r["Hc"][1] for r in sel]))
            band = (y[None, :] >= 95.0) & (df.x[:, None] <= sg) & (df.h[:, None] > 1.0)
            kA_band = float(kA[band].max())
            # lateral metrics at the break (or summit) with the supply of that point
            xq = xbc if xbc is not None else sel[jm]["x"]
            xq_ = float(df.x[int(np.argmin(np.abs(df.x - xq)))])
            fr, _ = sup(xq_)
            r_ = rows[int(np.argmin([abs(r["x"] - xq_) for r in rows]))]
            m = lateral_metrics(df, E, fr, A_SUM, T, xq_, r_of(r_["Ur"] if "Ur" in r_ else ursell(T, r_["A"], r_["h"])))
            # off-axis: R = r |A_sup(x, y)| / h with the focal supply weights (first x where any y reaches gamma 0.82)
            frf, _ = sup(x_f)
            A2 = A_SUM * np.abs(np.tensordot(frf, E, axes=(0, 0)))
            first = None
            for i, xx in enumerate(df.x):
                h = float(df.h[i])
                if xx < 150.0 or h < 1.0:
                    continue
                R = r_of(ursell(T, float(A2[i, 0]), h)) * A2[i] / h
                j = np.where((y <= 95.0) & (R >= GAMMA[1]))[0]
                if len(j):
                    first = (float(xx), float(y[j[np.argmax(R[j])]])); break
            row = dict(x_f=x_f, sd_gen=sg, sd_sw=ssw, ap_f=rows[i_f]["ap"], A_f=rows[i_f]["A"], Hc_f=rows[i_f]["Hc"],
                       Hc_over_h_f=rows[i_f]["Hc"][1] / rows[i_f]["h"], x_break=xb, summit_x=sel[jm]["x"], summit_Hc=sel[jm]["Hc"],
                       kA_side_band=kA_band, first_offaxis=first,
                       at_break={k: m.get(k) for k in ("x_pk", "Hc", "W50", "W50_m", "W80", "W95", "K", "S2", "ring_max", "N1", "N1_at", "miss")})
            out.append(row)
            print("x_f %.2f sd_gen %.2f | ap_f %.3f A_f %.2f Hc_f %.2f [%.2f-%.2f] Hc/h_f %.2f | summit %.1f (%.2f) break %s [%s-%s] | kA band %.2f | off-axis first %s | at break: Hc %.2f W50 %.2f (%.1f m) W80 %.2f S2 %.2f N1 %.2f miss %.2f" % (
                x_f, sg, row["ap_f"], row["A_f"], row["Hc_f"][1], row["Hc_f"][0], row["Hc_f"][2], row["Hc_over_h_f"], row["summit_x"], row["summit_Hc"][1],
                None if xbc is None else round(xbc, 1), None if xb["g0.76_rhi"] is None else round(xb["g0.76_rhi"], 1),
                None if xb["g0.88_rlo"] is None else round(xb["g0.88_rlo"], 1), kA_band, first, m["Hc"], m["W50"], m["W50_m"], m["W80"], m["S2"],
                m["N1"] or 0, m["miss"]))
    jd(dict(rows=out, tag="[computed] ray supply with an extended side band (a second change, not X2B); gamma / r rules as screen2"),
       OUT + "/supplyfix.json")


def detail():
    """chosen configurations: break-instant lateral metrics with a depth-limited cap (crest <= 0.88 h: shoreward of the break the linear
    WKB field otherwise explodes and fakes N1), curl widening (half width of R >= gamma at x_b + 0/5/10/20 m), the highest off-axis
    R / centre R near the break (lattice spots), Iribarren number at the break; DM1A (T 12, +-80) as the wide-curl reference."""
    import x51_ana as XA
    y = 0.5 + np.arange(140.0)
    cfgs = [("X2_ref", 7.0, "X2", 220.25, 180.25), ("X2B_240", 7.0, "X2", 240.25, 180.25), ("X2B_260", 7.0, "X2", 260.25, 180.25),
            ("X2Bs_270", 7.0, "X2", 270.25, 210.25), ("X2Bs_275", 7.0, "X2", 275.25, 210.25), ("X2Bs_280", 7.0, "X2", 280.25, 210.25),
            ("X2Bs_275_g230", 7.0, "X2", 275.25, 230.25), ("DM1A_ref", 12.0, "U80", 220.25, 180.25)]
    out = {}
    for nm, T, sn, x_f, sg in cfgs:
        th, w = (XC.components("X2") if sn == "X2" else DF.components(80.0, 30, "uniform"))
        om = 2 * math.pi / T
        x = np.arange(0.5, 345.0, 1.0)
        df, E = field(T, th, w, x_f, x, y)
        def sup(xq):
            xf0 = df.x_f; df.x_f = float(xq)
            try:
                ap = DF.aperture(df, 140.0, 45.0, 100.0, sg, sg + 30.0)
            finally:
                df.x_f = xf0
            return np.array([c["frac"] for c in ap["comps"]]), ap["frac"]
        rows = []
        for i, xx in enumerate(df.x):
            h = float(df.h[i])
            if xx < 150.0 or h < 1.0:
                continue
            fr, ap = sup(xx)
            Ac = A_SUM * complex(np.dot(fr, E[:, i, 0])); a = abs(Ac); Ur = ursell(T, a, h)
            rows.append(dict(x=float(xx), h=h, A=a, ap=ap, Ur=Ur, t=float(np.angle(Ac) / om), Hc=[a * r_of(Ur, -0.07), a * r_of(Ur), a * r_of(Ur, 0.07)]))
        xb = {"g%.2f_r%s" % (g, k): first_cross(rows, 150.0, lambda r, g=g, si=si: r["Hc"][si] - g * r["h"])
              for g in GAMMA for si, k in enumerate(("lo", "mid", "hi"))}
        xbc = xb["g0.82_rmid"]
        sel = [r for r in rows if r["x"] <= xbc]
        jm = int(np.argmax([r["Hc"][1] for r in sel]))
        ib = int(np.argmin(np.abs(df.x - xbc)))
        rb = rows[int(np.argmin([abs(r["x"] - df.x[ib]) for r in rows]))]
        fr, apb = sup(df.x[ib])
        A = A_SUM * np.tensordot(fr, E, axes=(0, 0))
        scale = r_of(rb["Ur"])
        t = float(np.angle(A[ib, 0]) / om)
        e = scale * np.real(A * np.exp(-1j * om * t))
        cap = (0.88 * np.maximum(df.h, 0.0))[:, None]
        e = np.where(df.h[:, None] > 0.3, np.minimum(e, cap), 0.0)
        meta = dict(x0=float(df.x[0]), dx=1.0, z0=0.5, dz=1.0)
        eh = e.T.copy(); eh[y > 95.0, :] = np.nan
        m = EM.hf_metrics(eh, meta, 0.0, xwin=(xbc - 20.0, xbc + 20.0))
        m["miss"], _ = EM.score_vs_target(m)
        iso = XA.n1_isolation(EM.median3(eh), meta, m)
        # summit instant (largest predicted crest before the break)
        isu = int(np.argmin(np.abs(df.x - sel[jm]["x"])))
        frs, _ = sup(df.x[isu])
        As = A_SUM * np.tensordot(frs, E, axes=(0, 0))
        ts = float(np.angle(As[isu, 0]) / om)
        es = r_of(sel[jm]["Ur"]) * np.real(As * np.exp(-1j * om * ts))
        es = np.where(df.h[:, None] > 0.3, np.minimum(es, cap), 0.0)
        ehs = es.T.copy(); ehs[y > 95.0, :] = np.nan
        ms = EM.hf_metrics(ehs, meta, 0.0, xwin=(sel[jm]["x"] - 20.0, sel[jm]["x"] + 20.0))
        ms["miss"], _ = EM.score_vs_target(ms)
        isos = XA.n1_isolation(EM.median3(ehs), meta, ms)
        # curl widening and lattice: R = r |A_sup| / h with the break supply
        R = np.full(A.shape, np.nan)
        for i, xx in enumerate(df.x):
            h = float(df.h[i])
            if h < 1.0:
                continue
            R[i] = r_of(ursell(T, float(abs(A[i, 0])), h)) * np.abs(A[i]) / h
        hw = {"xb+%g" % d: half_width_ge(R, y, df, xbc + d, GAMMA[1]) for d in (0.0, 5.0, 10.0, 20.0)}
        win = ((df.x >= xbc - 30.0) & (df.x <= xbc + 0.5))[:, None] & (y[None, :] >= 20.0) & (y[None, :] <= 95.0)   # same or deeper water than the centre break
        side = float(np.nanmax(np.where(win, R, np.nan)) / R[ib, 0])
        # Iribarren at the break: H_b = Hc_b / f_c with crest fraction f_c 0.7-0.8 [guess], L0 = g T^2 / 2 pi
        L0 = DF.G * T * T / (2 * math.pi)
        Hcb = rb["Hc"][1]
        xi = [0.1 / math.sqrt((Hcb / fc) / L0) for fc in (0.8, 0.7)]
        out[nm] = dict(T=T, x_f=x_f, sd_gen=sg, sd_sw=sg + 30.0, x_break=xb, x_break_central=xbc, h_break=rb["h"], Hc_break=rb["Hc"], ap_break=apb,
                       t_break_rel_tf=t, summit_x=sel[jm]["x"], summit_Hc=sel[jm]["Hc"],
                       at_break={k: m.get(k) for k in ("Hc", "W20", "W50", "W80", "W95", "K", "S1", "S2", "ring_max", "Lx50", "A50", "miss")},
                       N1_break=iso.get("N1"), N1_break_at=iso.get("at"),
                       at_summit={k: ms.get(k) for k in ("Hc", "x_pk", "W50", "W80", "W95", "K", "S2", "ring_max", "miss")},
                       N1_summit=isos.get("N1"), N1_summit_at=isos.get("at"),
                       curl_half_width_m=hw, side_spot_R_over_centre=side, iribarren_break=xi)
        b = out[nm]["at_break"]; s = out[nm]["at_summit"]
        print("%-14s x_f %.2f sd_gen %.2f | break %.1f [%s-%s] h %.2f Hc %.2f t %+.2f s | summit %.1f (%.2f) | break: W50 %.2f W80 %.2f W95 %.2f K %.2f S2 %.2f N1 %.2f@%s miss %.2f | summit: W50 %.2f W80 %.2f S2 %.2f N1 %.2f miss %.2f | curl hw %s | side R/centre %.2f | xi_b %.2f-%.2f" % (
            nm, x_f, sg, xbc, None if xb["g0.76_rhi"] is None else round(xb["g0.76_rhi"], 1), None if xb["g0.88_rlo"] is None else round(xb["g0.88_rlo"], 1),
            rb["h"], Hcb, t, sel[jm]["x"], sel[jm]["Hc"][1], b["W50"], b["W80"], b["W95"], b["K"], b["S2"], iso.get("N1") or 0, iso.get("at"), b["miss"],
            s["W50"], s["W80"], s["S2"], isos.get("N1") or 0, s["miss"], hw, side, xi[0], xi[1]))
    jd(out, OUT + "/detail.json")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "detail":
        detail()
    elif a and a[0] == "supplyfix":
        supplyfix()
    elif a and a[0] == "screen2":
        screen2()
    elif a and a[0] == "screen2DM":
        screen2([220.25], T=12.0, setname="U80", tag="2_DM1A")
    elif a and a[0] == "calap":
        cal_aperture()
    elif a and a[0] == "cal":
        cal()
    elif a and a[0] == "screen":
        screen()
    elif a and a[0] == "screenDM":          # validation of the rules on the DM1A sea (T 12, uniform +-80, x_f 220.25)
        screen([220.25], T=12.0, setname="U80", tag="_DM1A")
    else:
        print(__doc__)
