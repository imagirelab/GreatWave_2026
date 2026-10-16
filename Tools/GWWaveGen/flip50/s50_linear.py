# -*- coding: utf-8 -*-
"""FLIP50 option D, screen S1: linear directional focusing (WKB shoaling + refraction) on a laterally straight 1:10 slope.
numpy only (py -3.10 -I). 2026-10-15, Claude. Ranks candidates; never judges. Output: screen/s50_linear.json.

Per candidate (T, theta_max, weights, focus offset delta = x_f - x_b_target):
  1. unit field (sum a_j = 1) -> gamma(x, y) = 2|A|/h (linear wave height over depth).
  2. scale a_sum so the centre row (y = 0) first reaches gamma_b at x_b_target (h_b,target) or earlier (then x_b0 = that x).
     gamma_b is calibrated on FLIP47 P1c (2D, same 1:10 slope): incoming H 11 m at h0 19 m, T 14 s, onsets at h_b 10.82-11.82 m.
  3. each row y breaks where gamma first reaches gamma_b (x_b(y)); the crest that passes there arrives at t = psi(x_b(y), y)/omega
     (psi = unwrapped phase of A, continuous from the centre row) -> lag dt(y) behind the centre onset.
  4. curl-width proxy w(D) = 2 * contiguous y from 0 with dt(y) <= D; D = 0.25 s (P2, onset), 0.75 s (P3, most overturned),
     1.5 s (P3, touchdown). Hc_est = 0.86 h_b0 (P1c: eta_c/h_b 0.83-0.91).
  5. crest profile c(y) at the centre onset instant (per-row max of eta over x_c0 +- L0/2, as g49_periodic_ana.crest_window),
     P4a proxy c0 / mean c(|y| 70-84 m), P4b proxy c0 / c(4 Hc_est) and rows |y| >= 4 Hc_est whose break lag mod T is within
     [-0.5, 1.5] s of the centre onset.
  6. offshore safety: max gamma on the flat (x < x_toe) / gamma_b; incident 2|A| at the gauges x 110/128/160 (rows 0.5 and 80 m).
  7. aperture: fraction of the focal amplitude whose rays start inside the generating bands for W 120 (side band 35 m) and W 150 (50 m).
"""
import os, sys, json, math, time, itertools
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g50_dirfield as DF

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen")
G = DF.G


def calib_gamma():
    """gamma_b from FLIP47 P1c [measured]: H 11 m (design; measured 10.44-11.10 m) at h0 19 m, T 14 s; onsets k2-k4 at h_b 10.88, 10.82, 11.82 m."""
    om = 2 * math.pi / 14.0
    hb = np.array([10.88, 10.82, 11.82])
    Ks = np.sqrt(DF.cg(om, 19.0) / DF.cg(om, hb))
    g = 11.0 * Ks / hb
    eta_c = np.array([9.94, 8.98, 9.99])
    return dict(gamma_b=float(g.mean()), gamma_each=[float(v) for v in g], Ks=[float(v) for v in Ks], h_b=hb.tolist(),
                etac_over_hb=[float(v) for v in eta_c / hb], etac_over_hb_mean=float((eta_c / hb).mean()),
                source="FLIP47 P1c k2-k4 (Docs/Progress/FLIP47_2D_Seabed_ja.md 5.5) [measured]; linear shoaling [computed]")


SPEC = dict(h0=17.0, x_toe=180.25, s=10.0, kind="beach")
X_BAND = 100.0
HB_TARGET = 11.0


def screen_one(T, thm, n=30, weight="uniform", delta=0.0, gamma_b=1.0, hc_ratio=0.86, dx=0.5, dy=0.5, ymax=120.0, spec=SPEC,
               hb_target=HB_TARGET, s_cos=None, apertures=((120.0, 35.0), (150.0, 50.0)), gen_offsets=(0.0, 20.0)):
    om = 2 * math.pi / T
    x_toe = spec["x_toe"]; s = spec["s"]
    xb_t = x_toe + (spec["h0"] - hb_target) * s
    x_f = xb_t + delta
    x = np.arange(X_BAND, x_toe + spec["h0"] * s - 2.0, dx)           # to h ~ 0.2 m (beach)
    y = np.arange(0.0, ymax + 1e-9, dy)
    th, w = DF.components(thm, n, weight, s_cos)
    df = DF.DirField(T, th, w, 1.0, x, spec, x_f)
    A = df.complex_amp(y)
    h = df.h
    hh = np.where(h > 0.3, h, np.nan)
    gam = 2 * np.abs(A) / hh[:, None]
    m0 = (x <= xb_t + 1e-9)
    gmax = np.nanmax(gam[m0, 0])
    a_sum = gamma_b / gmax
    gam *= a_sum
    A *= a_sum
    df.Aj *= a_sum; df.a *= a_sum
    i0 = int(np.argmax(gam[:, 0] >= gamma_b - 1e-9))
    xb0 = float(x[i0]); hb0 = float(h[i0])
    Hc = hc_ratio * hb0
    # phase, unwrapped from the centre row
    psi = np.angle(A)
    p0 = np.unwrap(psi[:, 0])
    psi = np.unwrap(psi + (p0 - psi[:, 0])[:, None], axis=1)
    t0 = psi[i0, 0] / om
    # per-row break
    hit = gam >= gamma_b
    hit[np.isnan(gam)] = False
    has = hit.any(axis=0)
    ib = np.where(has, np.argmax(hit, axis=0), -1)
    xb = np.where(has, x[np.maximum(ib, 0)], np.nan)
    dt = np.where(has, psi[np.maximum(ib, 0), np.arange(len(y))] / om - t0, np.nan)
    amp_min_path = np.array([np.abs(A[max(ib[j], 0), :j + 1]).min() / max(np.abs(A[max(ib[j], 0), 0]), 1e-9) if has[j] else np.nan for j in range(len(y))])

    def width(D):
        ok = has & (dt <= D + 1e-9)
        if not ok[0]:
            return 0.0
        nbad = np.argmax(~ok) if (~ok).any() else len(y)
        return 2.0 * (y[nbad - 1] + 0.5 * dy) if nbad > 0 else 0.0
    wd = {str(D): width(D) for D in (0.25, 0.75, 1.5, 2.0)}
    # crest profile at the centre onset instant
    L0 = 2 * math.pi / df.k0
    eta0 = np.real(A * np.exp(-1j * om * t0))
    jc = int(np.argmax(np.where((x > xb0 - 0.5 * L0) & (x < xb0 + 0.5 * L0), eta0[:, 0], -1e9)))
    xc0 = float(x[jc])
    win = (x >= xc0 - 0.5 * L0) & (x <= xc0 + 0.5 * L0)
    c = eta0[win].max(axis=0)
    c0 = float(c[0])
    sb = (y >= 70.0) & (y <= 84.0)
    c_side = float(c[sb].mean())
    c4 = float(np.interp(4 * Hc, y, c))
    half = c_side + 0.5 * (c0 - c_side)
    fwhm_ex = 2 * float(y[np.argmax(c < half)]) if (c < half).any() else None
    w90 = 2 * float(y[np.argmax(c < 0.9 * c0)]) if (c < 0.9 * c0).any() else None
    # rows beyond 4 Hc breaking within [-0.5, 1.5] s of the centre onset (mod T)
    far = (y >= 4 * Hc) & has
    lagm = np.mod(dt + 0.5 * T, T) - 0.5 * T
    beyond = far & (lagm >= -0.5) & (lagm <= 1.5)
    # first break lag of rows beyond 4 Hc (the same crest), and their x
    fr = {}
    if far.any():
        jj = np.where(far)[0]
        k = jj[np.argmin(dt[jj])]
        fr = dict(y=float(y[k]), dt_s=float(dt[k]), x_b=float(xb[k]), h_b=float(np.interp(xb[k], x, h)))
    # offshore safety and incident heights
    flat = x < x_toe
    g_flat = float(np.nanmax(gam[flat])) / gamma_b
    gauges = {}
    for xg in (110.0, 128.0, 160.0):
        ig = int(np.argmin(np.abs(x - xg)))
        gauges[str(int(xg))] = dict(H_y0p5=float(2 * np.abs(A[ig, 1])), H_y80=float(2 * np.abs(A[ig, int(80 / dy)])),
                                    H_mean_0_85=float(2 * np.abs(A[ig, y <= 85]).mean()))
    # on-axis amplitude profile around the break (focus gain and focal length)
    Aax = np.abs(A[:, 0])
    # offshore steepness check: linear H on the axis against the 2D highest wave (Fenton 1990 fit, g47_sfwave.highest_H) at the local
    # depth, and the same scaled by the x-velocity factor <cos> = |sum A_j cos th_j e^{i phi}| / |sum A_j e^{i phi}| (a spread crest
    # carries less x-velocity per metre of height, so its kinematic limit is higher; estimate, not a validated criterion)
    sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47")
    import g47_sfwave as SF
    Ux = np.zeros(len(x), complex)
    for j in range(len(df.a)):
        Ux += df.Aj[j] * (df.kx[j] / df.k) * np.exp(1j * df.Phi[j])
    cosf = np.abs(Ux) / np.maximum(Aax, 1e-9)
    hm_cache = {}
    def hmax(hv):
        key = round(float(hv), 1)
        if key not in hm_cache:
            hm_cache[key] = SF.highest_H(max(key, 2.0), T)
        return hm_cache[key]
    sel = (x >= 110.0) & (x <= spec["x_toe"] + 1e-9)
    r2d = np.array([2 * Aax[i] / hmax(h[i]) for i in np.where(sel)[0]])
    r3d = r2d * cosf[sel]
    ii = np.where(sel)[0]
    k2 = int(np.argmax(r2d)); k3 = int(np.argmax(r3d))
    steep = dict(R2d_max=float(r2d[k2]), x_R2d=float(x[ii[k2]]), h_R2d=float(h[ii[k2]]), R3d_max=float(r3d[k3]), x_R3d=float(x[ii[k3]]),
                 cos_factor_at=float(cosf[ii[k3]]), H_axis_x160=float(2 * Aax[int(np.argmin(np.abs(x - 160)))]),
                 Hmax2d_h17=float(hmax(spec["h0"])), rule="flat part (x <= x_toe) on the axis; P1c (2D, did not break offshore) had H/Hmax(h0) ~0.83 [computed from measured H]")
    ap = {}
    for W, Ls in apertures:
        for go in gen_offsets:
            r = DF.aperture(df, W, Ls, X_BAND, x_toe + go, x_toe + go + 30.0)
            ap["W%d_sb%d_gen+%d" % (W, Ls, go)] = round(r["frac"], 3)
    res = dict(T=T, theta_max=thm, n=n, weight=weight, s_cos=s_cos, delta=delta, x_f=x_f, a_sum=float(a_sum), a_comp_max=float(df.a.max()),
               k0=df.k0, L0=L0, x_b0=xb0, h_b0=hb0, Hc_est=Hc, t0=float(t0),
               widths_m=wd, widths_over_Hc={k: v / Hc for k, v in wd.items()},
               c0_lin=c0, c_side_lin=c_side, P4a_lin=c0 / c_side if c_side > 0 else None, c_4Hc_lin=c4, P4b_lin=c0 / c4 if c4 > 0 else None,
               fwhm_excess_m=fwhm_ex, w90_m=w90, x_crest_c0=xc0,
               rows_beyond_4Hc_in_window=bool(beyond.any()), first_beyond_4Hc=fr,
               gamma_flat_over_b=g_flat, gauges=gauges, steep=steep,
               axis_amp_at_xb=float(Aax[i0]), axis_amp_max=float(Aax.max()), x_axis_amp_max=float(x[int(np.argmax(Aax))]),
               aperture=ap, dt_rows={str(int(yy)): (round(float(dt[int(yy / dy)]), 3) if has[int(yy / dy)] else None) for yy in (5, 10, 15, 20, 30, 40, 60, 80)},
               xb_rows={str(int(yy)): (round(float(xb[int(yy / dy)]), 1) if has[int(yy / dy)] else None) for yy in (5, 10, 15, 20, 30, 40, 60, 80)},
               path_min_rel_amp=float(np.nanmin(amp_min_path[:int(40 / dy)])))
    return res


def refine():
    """second sweep: T 10/11/12, theta_max 60-85, delta -40..0, h_b target 11 m (Hc ~9.5) and 10 m (Hc ~8.6); W 120/150 apertures."""
    t_start = time.time()
    cal = calib_gamma(); gb = cal["gamma_b"]
    rows = []
    for T, thm, delta, hbt in itertools.product((10.0, 11.0, 12.0), (60.0, 70.0, 80.0, 85.0), (-40.0, -30.0, -20.0, -10.0, 0.0), (11.0, 10.0)):
        rows.append(screen_one(T, thm, delta=delta, gamma_b=gb, hb_target=hbt))
    out = dict(tool="Tools/GWWaveGen/flip50/s50_linear.py refine", date=time.strftime("%Y-%m-%d %H:%M:%S"), tag="computed (screen, linear WKB); ranks only",
               calibration=cal, spec=SPEC, rows=rows, cpu_s=round(time.time() - t_start, 1))
    p = os.path.join(OUT, "s50_linear_refine.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("T  thm  dlt  hbt  xb0   Hc  w.25 w.75 w1.5 (/Hc)       P4a   P4b  w90  R2d  R3d  xR3d  ap120g0 ap120g20 ap150 dt20 dt40")
    for r in rows:
        wh = r["widths_over_Hc"]; a = r["aperture"]; st = r["steep"]
        print("%4.0f %3.0f %4.0f %4.0f %6.1f %4.1f %4.1f %4.1f %4.1f (%3.1f %3.1f %3.1f) %5.2f %5.2f %4s %4.2f %4.2f %5.1f %5.2f %5.2f %5.2f %5.2f %5.2f" % (
            r["T"], r["theta_max"], r["delta"], r["h_b0"], r["x_b0"], r["Hc_est"], r["widths_m"]["0.25"], r["widths_m"]["0.75"], r["widths_m"]["1.5"],
            wh["0.25"], wh["0.75"], wh["1.5"], r["P4a_lin"] or 0, r["P4b_lin"] or 0, ("%.0f" % r["w90_m"]) if r["w90_m"] else "-",
            st["R2d_max"], st["R3d_max"], st["x_R3d"], a["W120_sb35_gen+0"], a["W120_sb35_gen+20"], a["W150_sb50_gen+0"],
            r["dt_rows"]["20"] or -1, r["dt_rows"]["40"] or -1))
    print("cpu %.1f s -> %s" % (time.time() - t_start, p))


def depth19():
    """h0 19 m (FLIP47 S2/P1c depth) against h0 17 m (FLIP48/49 depth), same 1:10 slope, flat-part steepness and widths."""
    cal = calib_gamma(); gb = cal["gamma_b"]
    rows = []
    for h0 in (17.0, 19.0):
        sp = dict(SPEC, h0=h0)
        for T, thm, delta, hbt in itertools.product((10.0, 11.0, 12.0), (70.0, 80.0), (-30.0, -20.0), (11.0, 10.0)):
            r = screen_one(T, thm, delta=delta, gamma_b=gb, hb_target=hbt, spec=sp); r["h0"] = h0
            rows.append(r)
    json.dump(dict(tool="s50_linear.py depth19", rows=rows, calibration=cal), open(os.path.join(OUT, "s50_linear_depth19.json"), "w"), indent=1)
    print("h0  T  thm dlt hbt  xb0   Hc  w/Hc(.25 .75 1.5)  P4a  P4b  R2d_flat R3d_flat H160  Hmax17  ap120")
    for r in rows:
        wh = r["widths_over_Hc"]; st = r["steep"]
        print("%3.0f %3.0f %3.0f %4.0f %3.0f %6.1f %4.1f  %3.1f %3.1f %3.1f  %5.2f %5.2f  %5.2f %5.2f %5.2f %5.2f %5.2f" % (
            r["h0"], r["T"], r["theta_max"], r["delta"], r["h_b0"], r["x_b0"], r["Hc_est"], wh["0.25"], wh["0.75"], wh["1.5"],
            r["P4a_lin"], r["P4b_lin"], st["R2d_max"], st["R3d_max"], st["H_axis_x160"], st["Hmax2d_h17"], r["aperture"]["W120_sb35_gen+0"]))


def main():
    if "refine" in sys.argv[1:]:
        return refine()
    if "depth19" in sys.argv[1:]:
        return depth19()
    t_start = time.time()
    cal = calib_gamma()
    gb = cal["gamma_b"]
    rows = []
    for T, thm, delta in itertools.product((8.0, 10.0, 12.0, 14.0), (30.0, 45.0, 60.0, 75.0), (-60.0, -40.0, -20.0, 0.0, 20.0)):
        rows.append(screen_one(T, thm, delta=delta, gamma_b=gb))
    # weights and N sensitivity at the T 12 s / 10 s best spreads
    extra = []
    for T in (10.0, 12.0):
        for wgt, sc in (("fgd", None), ("cos2s", 2.0)):
            for thm in (45.0, 60.0):
                extra.append(screen_one(T, thm, delta=-20.0, gamma_b=gb, weight=wgt, s_cos=sc))
        extra.append(screen_one(T, 60.0, n=16, delta=-20.0, gamma_b=gb))
        extra.append(screen_one(T, 60.0, n=60, delta=-20.0, gamma_b=gb))
    # gamma_b sensitivity (+-15 %)
    sens = [screen_one(12.0, 60.0, delta=-20.0, gamma_b=gb * f) for f in (0.85, 1.15)]
    out = dict(tool="Tools/GWWaveGen/flip50/s50_linear.py", date=time.strftime("%Y-%m-%d %H:%M:%S"), tag="computed (screen, linear WKB); ranks only",
               calibration=cal, spec=SPEC, hb_target=HB_TARGET, rows=rows, extra=extra, gamma_sens=sens, cpu_s=round(time.time() - t_start, 1))
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "s50_linear.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("gamma_b %.3f (%s)" % (gb, ", ".join("%.3f" % v for v in cal["gamma_each"])))
    hdr = "T  thm  dlt  xb0    hb0   Hc   asum  w.25 w.75 w1.5 (/Hc)      P4a  P4b  fwhm  w90  beyond flat  ap120g0 ap120g20 ap150g0 dt10 dt20 dt40"
    print(hdr)
    for r in rows + extra + sens:
        wh = r["widths_over_Hc"]
        a = r["aperture"]
        print("%4.0f %3.0f %4.0f %6.1f %5.2f %4.1f %5.2f %4.1f %4.1f %4.1f (%3.1f %3.1f %3.1f) %4.2f %4.2f %5s %5s %5s %4.2f %5.2f %5.2f %5.2f %s %s %s %s" % (
            r["T"], r["theta_max"], r["delta"], r["x_b0"], r["h_b0"], r["Hc_est"], r["a_sum"], r["widths_m"]["0.25"], r["widths_m"]["0.75"], r["widths_m"]["1.5"],
            wh["0.25"], wh["0.75"], wh["1.5"], r["P4a_lin"] or 0, r["P4b_lin"] or 0, ("%.0f" % r["fwhm_excess_m"]) if r["fwhm_excess_m"] else "-",
            ("%.0f" % r["w90_m"]) if r["w90_m"] else "-", r["rows_beyond_4Hc_in_window"], r["gamma_flat_over_b"],
            a["W120_sb35_gen+0"], a["W120_sb35_gen+20"], a["W150_sb50_gen+0"], r["dt_rows"]["10"], r["dt_rows"]["20"], r["dt_rows"]["40"],
            r["weight"] + ("" if r["n"] == 30 else "n%d" % r["n"])))
    print("cpu %.1f s -> %s" % (time.time() - t_start, p))


if __name__ == "__main__":
    main()
