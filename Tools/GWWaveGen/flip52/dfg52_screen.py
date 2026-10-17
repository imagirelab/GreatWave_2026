# -*- coding: utf-8 -*-
"""FLIP52 'DFG-2' design screen: a PERIODIC MULTI-FREQUENCY DIRECTIONAL group on a FLAT bed (numpy + scipy.ndimage; py -3.10 -B).
2026-10-17 written new (Claude). Reads nothing from any run folder. Imports READ ONLY: flip51/e51_metrics (frozen hf_metrics,
score_vs_target, median3, mirror_y) and flip51/dfg51_screen (kdisp, the Sharma-Dean / Dalzell / Forristall 2nd-order kernels,
second_order, field). Writes only Unity/Build/FLIP52/screens/.

The sea (all phases 0 at the focus X = x - x_f = 0, y = 0 at t = t_f + mP; eta P-periodic because f_n = n/P):
    eta1 = sum_{n in ns} sum_j a_nj cos(k_n (cos th_j X + sin th_j y) - w_n t),   a_nj = a_sum wf_n wd_j  (sum a_nj = a_sum)
    eta2 = Sharma-Dean sum/difference terms of every pair (dfg51_screen.second_order)
Per candidate inlet set it reports (tags: [computed] unless noted):
  focus   linear and 2nd-order e51 hf_metrics at the focal instant (2nd order: the dt in -0.6..0.6 s with the largest Hc), the core miss
  N1      spatial isolation at that instant (plan E definition: 15 m max filter, r <= 100 m, outside r < 4 Hc of the summit and of its
          mirror, / Hc) inside the tank interior (x_in + 10 .. xa0 - 5 m, |y| <= sd0 - 5 m)
  Nt      temporal isolation over one period P: largest crest anywhere in the interior at |t - t_f| >= Tp/2 (mod P) / the focal crest
          (linear scan every 0.25 s; the 3 largest secondary instants re-evaluated at 2nd order)
  c_in    largest incoming crest over one period on the line x = x_in + 10 m, |y| <= sd0 - 5 m (the plan E 'c_in110' analogue), linear
          and 2nd order; gains Hc / c_in and Hc / max a_nj (Q39)
  bands   k_p x max crest and max |grad eta| over one period in the inlet band (x wall_taper..x_in) and the generating side band
          (y >= sd0, x <= sd_gen): G4 analogue
  rays    aperture (fraction of the focal linear sum whose straight rays start in a generating band) and the arrival time
          ramp + path / c_g of every component (the earliest fully developed focus)
  sponge  Perić & Abdel-Maksoud (2018) 1D reflection of the exit sponge and of the side band's absorbing part per frequency and incidence
          (the theory as coded in flip45/r45_gen_numbers.reflection, copied here)
usage:  py -3.10 -B dfg52_screen.py run [case ...] | variants [name ...] | sponge | list
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")                     # a hython run shares the machine: keep numpy modest
HERE = os.path.dirname(os.path.abspath(__file__))
F51 = os.path.join(os.path.dirname(HERE), "flip51")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if F51 not in sys.path:
    sys.path.append(F51)
import numpy as np                                    # noqa: E402
from scipy import ndimage as ndi                      # noqa: E402
import e51_metrics as EM                              # noqa: E402  read only
import dfg51_screen as D51                            # noqa: E402  read only

G = D51.G
OUT = EM.ROOT + "/Unity/Build/FLIP52/screens"
A_SUM_DM1A = 6.331240146143423                        # DM1A input sum (g50_common.CASES['DM1']['a_sum']) [chosen reference]
SUMA2_DM1A = A_SUM_DM1A ** 2 / 30.0                   # DM1A: 30 equal components -> sum a_j^2 = 1.33616 m^2 [computed]
TP = 7.0

# the proposed FLIP52 tank (half tank, mirror y = 0, flat bed) [chosen; checked by this screen]
LAYOUT = dict(h=20.0, Lx=290.0, W=100.0, x_in=50.0, wall_taper=12.5, sd0=70.0, sd_gen=180.0, sd_sw=210.0, sd_taper=7.5,
              x_f=150.0, xa0=210.0, ramp_s=14.0, abs_sigma=1.0, abs_pow=2.0, sd_sigma=1.41, sd_pow=2.0)
# sd_gen = x_f + 30 m (2026-10-17, after the first sponge study): a 30 m absorbing side band reflects 0.2-0.45 of T 7-9.33 s waves at
# 10-40 deg incidence (Peric 1D, any sigma) [computed], so the side band RELAXES TO THE LINEAR TARGET (which contains the outgoing waves)
# up to 30 m past the focus and only blends into absorbing at the exit sponge start (x 210 m); exit sponge 80 m, sigma 1.0 = min-max of
# the 1D reflection over T 9.33/7/5.6 s and incidence 0-50 deg (rays at < 49 deg reach x 210 m inside |y| < 70 m) [computed]


# ============================================================================================ inlet sets
def dirset(spec):
    """-> (theta deg, weight sum 1). ('cross', beta, sigma, n): th = linspace(-(b + 2.5 s), b + 2.5 s, n), two Gaussian lobes;
    ('uni', thmax, n); ('hyb', centre, sigma, cap, nhalf): the plan E X2 rule +-linspace(max(c - 2.5 s, 2), min(c + 2.5 s, cap), nhalf)."""
    k = spec[0]
    if k == "cross":
        b, s, n = spec[1:]
        tm = min(b + 2.5 * s, 85.0)
        th = np.linspace(-tm, tm, int(n))
        w = np.exp(-0.5 * ((th - b) / s) ** 2) + np.exp(-0.5 * ((th + b) / s) ** 2)
    elif k == "uni":
        tm, n = spec[1:]
        th = np.linspace(-tm, tm, int(n)); w = np.ones(len(th))
    elif k == "hyb":
        c, s, cap, nh = spec[1:]
        t1 = np.linspace(max(c - 2.5 * s, 2.0), min(c + 2.5 * s, cap), int(nh))
        w1 = np.exp(-0.5 * ((t1 - c) / s) ** 2)
        th = np.concatenate([-t1[::-1], t1]); w = np.concatenate([w1[::-1], w1])
    else:
        raise ValueError(k)
    return th.astype(float), w / w.sum()


def freqset(P, ns, fw):
    """-> (omega, weight sum 1). fw: 'eq' | 'jonswap' (gamma 3.3, Tp 7, amplitude ~ S(f_n), as dfg51 'per') | list of weights."""
    f = np.asarray(ns, float) / float(P)
    if isinstance(fw, (list, tuple)):
        w = np.asarray(fw, float)
    elif fw == "eq":
        w = np.ones(len(f))
    elif fw == "jonswap":
        fp = 1.0 / TP
        sig = np.where(f <= fp, 0.07, 0.09)
        w = f ** -5 * np.exp(-1.25 * (fp / f) ** 4) * 3.3 ** np.exp(-0.5 * ((f - fp) / (sig * fp)) ** 2)
    else:
        raise ValueError(fw)
    return 2 * math.pi * f, w / w.sum()


def components(P, ns, fw, dspec, a_sum, h, real=None):
    """real: optional per-frequency realization factors (FLIP inlet realization x propagation damping) applied to a_nj [guess input]."""
    om, wf = freqset(P, ns, fw)
    th, wd = dirset(dspec)
    a = a_sum * np.outer(wf, wd)                                   # (nf, nd)
    if real is not None:
        a = a * np.asarray(real, float)[:, None]
    k = D51.kdisp(om, h)
    TH = np.radians(th)
    c = dict(a=a.ravel(), om=np.repeat(om, len(th)), k=np.repeat(k, len(th)), kx=np.outer(k, np.cos(TH)).ravel(),
             ky=np.outer(k, np.sin(TH)).ravel(), th=np.tile(th, len(om)), fi=np.repeat(np.arange(len(om)), len(th)), h=h)
    keep = c["a"] > 1e-6 * c["a"].max()
    for kk in ("a", "om", "k", "kx", "ky", "th", "fi"):
        c[kk] = c[kk][keep]
    c.update(P=float(P), ns=list(ns), om_n=om, wf=wf, k_n=k, th_set=th, wd=wd, a_sum=float(a_sum))
    return c


def grad_field(c, x, y, t):
    """|grad eta1| on (y, x) (linear)."""
    A = c["a"] * np.exp(-1j * c["om"] * t)
    Ey = np.exp(1j * np.outer(y, c["ky"]))
    Ex = np.exp(1j * np.outer(c["kx"], x))
    gx = ((Ey * (A * 1j * c["kx"])[None, :]) @ Ex).real
    gy = ((Ey * (A * 1j * c["ky"])[None, :]) @ Ex).real
    return np.hypot(gx, gy)


def eta12(c, c2, x, y, t):
    e1 = D51.field(c, x, y, t)
    return e1, (e1 + D51.field(c2, x, y, t)) if c2 is not None else e1


# ============================================================================================ isolation (plan E N1 definition)
def n1_iso(e_half, x, yh, m, xr, ymax, rmax=100.0, rex_Hc=4.0, win=15.0):
    Hc = float(m["Hc"]); xp = float(m["x_pk"]); yp = abs(float(m["y_pk"]))
    eta = np.concatenate([e_half[::-1], e_half], 0); y = np.concatenate([-yh[::-1], yh])
    e = np.where(np.isfinite(eta), eta, -99.0)
    hw = max(1, int(math.floor(0.5 * win / 1.0)))
    mx = ndi.maximum_filter(e, size=(2 * hw + 1, 2 * hw + 1), mode="constant", cval=-99.0)
    XX, YY = np.meshgrid(x, y)
    r = np.hypot(XX - xp, YY - yp); rm = np.hypot(XX - xp, YY + yp)
    rex = rex_Hc * Hc
    pk = ((e >= mx - 1e-12) & (e > 0.0) & (XX >= xr[0]) & (XX <= xr[1]) & (np.abs(YY) <= ymax) & (r <= rmax) & (r >= rex) & (rm >= rex))
    if not pk.any():
        return dict(N1=0.0, at=None)
    i = int(np.argmax(np.where(pk, e, -99.0)))
    return dict(N1=float(e.flat[i] / Hc), at=[float(XX.flat[i]), float(YY.flat[i])], dist_m=float(r.flat[i]))


KEYS = ["Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "Lx50", "A50"]


def slim(m, kp):
    o = {k: (round(float(m[k]), 4) if isinstance(m.get(k), (float, int)) and not isinstance(m.get(k), bool) else m.get(k)) for k in KEYS if k in m}
    o["kpHc"] = round(kp * m["Hc"], 4)
    o["W50_m"] = round(m["W50"] * m["Hc"], 2)
    miss, per = EM.score_vs_target(m)
    o["miss"] = round(miss, 3)
    o["miss_per"] = {k: (round(v, 3) if v is not None else None) for k, v in per.items()}
    return o


# ============================================================================================ rays / arrival (flat bed: straight rays)
def cg_of(om, h):
    k = float(D51.kdisp(om, h)[0]); kh = k * h
    return om / k * 0.5 * (1 + 2 * kh / math.sinh(2 * kh))


def rays(c, L):
    xf = L["x_f"]; rows = []; num = 0.0
    for a, om, th in zip(c["a"], c["om"], c["th"]):
        t = math.radians(abs(th))
        y_in = (xf - L["x_in"]) * math.tan(t)
        if y_in <= L["sd0"] + 1e-9:
            frac = 1.0; path = (xf - L["x_in"]) / math.cos(t); src = "inlet"; xc = None
        else:
            xc = xf - L["sd0"] / math.tan(t)
            frac = 1.0 if xc <= L["sd_gen"] else (0.0 if xc >= L["sd_sw"] else 1.0 - (xc - L["sd_gen"]) / (L["sd_sw"] - L["sd_gen"]))
            path = L["sd0"] / math.sin(t); src = "side"
        cg = cg_of(om, L["h"])
        rows.append(dict(T=2 * math.pi / om, th=float(th), a=float(a), src=src, x_cross_side=xc, frac=frac, path_m=path, cg=cg,
                         arrive_s=L["ramp_s"] + path / cg))
        num += frac * a
    sig = [r for r in rows if r["a"] >= 0.05 * max(rr["a"] for rr in rows)]
    return dict(aperture=num / float(np.sum(c["a"])), t_full_s=max(r["arrive_s"] for r in sig),
                t_full_note="ramp_s + max over components with a >= 5 % of max of path / c_g [computed; the group front is smeared by the ramp spectrum, so the plan adds a margin before the first judged focus]",
                per_T={("%.3f" % (2 * math.pi / o)): dict(cg=cg_of(o, L["h"]), max_arrive_s=max(r["arrive_s"] for r in sig if abs(r["T"] - 2 * math.pi / o) < 1e-6))
                       for o in c["om_n"]},
                min_frac=min(r["frac"] for r in rows))


# ============================================================================================ one candidate
def evaluate(name, P, ns, fw, dspec, a_sum=A_SUM_DM1A, L=LAYOUT, second=True, dt_scan=0.25, real=None):
    t0 = time.time()
    h = L["h"]
    c = components(P, ns, fw, dspec, a_sum, h, real=real)
    kp = float(D51.kdisp(2 * math.pi / TP, h)[0]); Lp = 2 * math.pi / kp
    xr = (L["x_in"] + 10.0 - L["x_f"], L["xa0"] - 5.0 - L["x_f"])       # interior x (focus coordinates)
    ymax = L["sd0"] - 5.0
    x = np.arange(-100.0, 60.0 + 0.5, 1.0)
    yh = 0.5 + np.arange(0, 100)
    meta = dict(z0=0.5, dz=1.0, x0=float(x[0]), dx=1.0)
    res = dict(name=name, P=P, ns=list(ns), T_n=[round(P / n, 4) for n in ns], fw=(fw if isinstance(fw, str) else list(fw)), dspec=list(dspec),
               a_sum=a_sum, a_sum_over_DM1A=a_sum / A_SUM_DM1A, realization=(list(real) if real is not None else None),
               a_sum_realized=float(np.sum(c["a"])), ncomp=int(len(c["a"])), kp=kp, Lp=Lp, kph=kp * h,
               kp_asum=kp * a_sum, wf=[round(float(v), 5) for v in c["wf"]], k_n=[round(float(v), 6) for v in c["k_n"]],
               kh_n=[round(float(v) * h, 4) for v in c["k_n"]], L_n=[round(2 * math.pi / float(v), 2) for v in c["k_n"]],
               a_max_comp=float(c["a"].max()), sum_a2=float(np.sum(c["a"] ** 2)), sum_a2_over_DM1A=float(np.sum(c["a"] ** 2) / SUMA2_DM1A),
               a_sum_energy_match=float(a_sum * math.sqrt(SUMA2_DM1A / np.sum(c["a"] ** 2))),
               amp_per_freq=[round(float(a_sum * w), 5) for w in c["wf"]],
               steep_per_freq_kA=[round(float(a_sum * w * k), 5) for w, k in zip(c["wf"], c["k_n"])])
    # ---------------------------------------------------------------- focus (linear at t = 0; 2nd order: best dt)
    e1 = D51.field(c, x, yh, 0.0)
    ml = EM.hf_metrics(e1, meta, 0.0, xwin=(-40.0, 40.0))
    res["lin"] = slim(ml, kp)
    res["lin"]["N1"] = n1_iso(EM.median3(e1), x, yh, ml, xr, ymax)
    c2 = D51.second_order(c) if second else None
    if second:
        best = None
        for dt in (-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6):
            e = e1 if dt == 0.0 and False else D51.field(c, x, yh, dt) + D51.field(c2, x, yh, dt)
            m = EM.hf_metrics(e, meta, 0.0, xwin=(-40.0, 40.0))
            if m and (best is None or m["Hc"] > best[0]["Hc"]):
                best = (m, dt, e)
        m2, dt2, e2 = best
        res["nl2"] = slim(m2, kp)
        res["nl2"]["t"] = dt2
        res["nl2"]["Hc_over_asum"] = m2["Hc"] / a_sum
        res["nl2"]["N1"] = n1_iso(EM.median3(e2), x, yh, m2, xr, ymax)
        res["n_pairs"] = int(len(c2["a"]))
    # ---------------------------------------------------------------- temporal isolation over one period (interior, linear scan)
    xi = np.arange(xr[0], xr[1] + 0.5, 1.0); yi = np.arange(0.0, ymax + 0.5, 1.0)
    ts = np.arange(-P / 2.0, P / 2.0 - 1e-9, dt_scan)
    Hmax = np.zeros(len(ts)); loc = []
    focus_pt = np.zeros(len(ts))
    for q, t in enumerate(ts):
        f = D51.field(c, xi, yi, t)
        i = int(np.argmax(f)); Hmax[q] = f.flat[i]
        loc.append([float(xi[i % len(xi)]), float(yi[i // len(xi)])])
        focus_pt[q] = f[0, int(np.argmin(np.abs(xi)))]
    H0 = float(Hmax[int(np.argmin(np.abs(ts)))])
    far = np.abs(ts) >= TP / 2.0 - 1e-9
    order = np.argsort(-np.where(far, Hmax, -1e9))
    sec = []
    for q in order:
        if not far[q]:
            continue
        if any(abs(ts[q] - s["t"]) < 1.0 for s in sec):
            continue
        sec.append(dict(t=float(ts[q]), H_lin=float(Hmax[q]), at=loc[q]))
        if len(sec) >= 3:
            break
    res["Nt_lin"] = float(Hmax[far].max() / H0)
    res["Nt_lin_at"] = sec[0] if sec else None
    res["focus_point_secondary_lin"] = float(focus_pt[far].max() / focus_pt[int(np.argmin(np.abs(ts)))])
    res["Hmax_t_lin"] = dict(t=[round(float(v), 3) for v in ts[::4]], H=[round(float(v), 3) for v in Hmax[::4]])
    if second:
        for s in sec:
            bestH = -1.0
            for dd in (-0.25, 0.0, 0.25):
                f2 = D51.field(c, xi, yi, s["t"] + dd) + D51.field(c2, xi, yi, s["t"] + dd)
                if f2.max() > bestH:
                    bestH = float(f2.max()); j = int(np.argmax(f2)); s["at2"] = [float(xi[j % len(xi)]), float(yi[j // len(xi)])]
            s["H_nl2"] = bestH
        res["Nt_nl2"] = (max(s["H_nl2"] for s in sec) / res["nl2"]["Hc"]) if sec else 0.0
        res["Nt_secondary"] = sec
    # ---------------------------------------------------------------- incoming crest on the line x = x_in + 10 (|y| <= ymax), one period
    xl = np.array([xr[0]]); yl = np.arange(0.0, ymax + 0.5, 1.0)
    cin1 = 0.0; cin2 = 0.0
    for t in np.arange(-P / 2.0, P / 2.0 - 1e-9, dt_scan):
        f = D51.field(c, xl, yl, t)
        cin1 = max(cin1, float(f.max()))
        if second:
            cin2 = max(cin2, float((f + D51.field(c2, xl, yl, t)).max()))
    res["c_in_line_lin"] = cin1
    res["c_in_line_x_tank_m"] = L["x_f"] + xr[0]
    Hc_ = res["nl2"]["Hc"] if second else res["lin"]["Hc"]
    if second:
        res["c_in_line_nl2"] = cin2
        res["gain_over_c_in_nl2"] = Hc_ / cin2
    res["gain_over_c_in_lin"] = res["lin"]["Hc"] / cin1
    res["gain_over_max_component"] = Hc_ / res["a_max_comp"]
    # incoming crest as dfg51 (unbounded linear field, r >= 1.5 Lp, x in [-3 Lp, 0.5 Lp], y in [0, 2 Lp]) for comparability
    xb = np.arange(-3.0 * Lp, 0.5 * Lp, 2.0); yb = np.arange(0.0, 2.0 * Lp, 2.0)
    XX, YY = np.meshgrid(xb, yb); farr = np.hypot(XX, YY) >= 1.5 * Lp
    inc = 0.0
    for t in np.arange(-P / 2.0, P / 2.0 - 1e-9, 0.5):
        inc = max(inc, float(D51.field(c, xb, yb, t)[farr].max()))
    res["incoming_r15L_lin"] = inc
    res["gain_over_incoming_r15L"] = Hc_ / inc
    # ---------------------------------------------------------------- band steepness over one period (G4 analogue)
    xin = np.arange(L["wall_taper"], L["x_in"] + 0.5, 2.0) - L["x_f"]; yin = np.arange(0.0, L["W"] - L["sd_taper"] + 0.5, 2.0)
    xsd = np.arange(0.0, L["sd_gen"] + 0.5, 2.0) - L["x_f"]; ysd = np.arange(L["sd0"], L["W"] - L["sd_taper"] + 0.5, 2.0)
    bi1 = bs1 = bi2 = bs2 = gi = gs = 0.0
    for t in np.arange(-P / 2.0, P / 2.0 - 1e-9, 0.5):
        a1, a2 = eta12(c, c2, xin, yin, t); b1, b2 = eta12(c, c2, xsd, ysd, t)
        bi1 = max(bi1, float(a1.max())); bs1 = max(bs1, float(b1.max())); bi2 = max(bi2, float(a2.max())); bs2 = max(bs2, float(b2.max()))
        gi = max(gi, float(grad_field(c, xin, yin, t).max())); gs = max(gs, float(grad_field(c, xsd, ysd, t).max()))
    res["bands"] = dict(kp_crest_inlet_lin=kp * bi1, kp_crest_side_lin=kp * bs1, kp_crest_inlet_nl2=kp * bi2, kp_crest_side_nl2=kp * bs2,
                        max_slope_inlet_lin=gi, max_slope_side_lin=gs, crest_inlet_nl2_m=bi2, crest_side_nl2_m=bs2)
    # ---------------------------------------------------------------- rays
    res["rays"] = rays(c, L)
    res["cpu_s"] = round(time.time() - t0, 1)
    return res


# ============================================================================================ sponge reflection (Perić & Abdel-Maksoud 2018, 1D)
def reflection(kx_free, rate_cells, om, dx, k_free, theta=0.0, mode="iso"):
    """copied from flip45/r45_gen_numbers.reflection (2026-10-12): cells of constant rate r_j (1/s) relaxing the horizontal velocity to
    0; iso: kx_j^2 = k^2 (cos^2 th + i r_j / om); wall behind the band. Returns |B/A| at the band entrance."""
    c2 = math.cos(theta) ** 2
    ks = []
    for r in rate_cells:
        q = k_free ** 2 * (c2 + 1j * r / om) if mode == "iso" else k_free ** 2 * c2 * (1 + 1j * r / om)
        kj = np.sqrt(q + 0j)
        if kj.imag < 0:
            kj = -kj
        ks.append(kj)
    rr = -1.0 + 0j
    for j in range(len(ks) - 1, -1, -1):
        kj = ks[j]
        rr = rr * np.exp(2j * kj * dx)
        Yv = (1 + rr) / (1j * kj * (1 - rr))
        kprev = ks[j - 1] if j > 0 else kx_free + 0j
        rr = (1j * kprev * Yv - 1) / (1j * kprev * Yv + 1)
    return float(abs(rr))


def CR(T_, h_, xd, sigma, p=2.0, dx=0.5, theta_deg=0.0):
    om = 2 * math.pi / T_
    k = float(D51.kdisp(om, h_)[0])
    n = max(1, int(round(xd / dx)))
    chi = (np.arange(n) + 0.5) / n
    th = math.radians(theta_deg)
    return reflection(k * math.cos(th), sigma * chi ** p, om, xd / n, k, th)


def sponge_study(Ts=(28 / 3.0, 7.0, 5.6), h=20.0):
    out = dict(theory="Perić & Abdel-Maksoud 2018 1D (flip45 r45_gen_numbers.reflection, copied); check: FLIP45 CR 0.037 for 36 m, sigma 2.37, T 7, h 20",
               check_flip45=CR(7.004, 20.0, 36.0, 2.37))
    rows = {}
    for xd in (60.0, 70.0, 80.0, 90.0, 100.0):
        best = None
        for s in np.geomspace(0.2, 8.0, 61):
            v = max(CR(T, h, xd, s) for T in Ts)
            if best is None or v < best[1]:
                best = (float(s), v)
        rows["%d" % xd] = dict(sigma_minmax=best[0], CR_max_normal=best[1],
                               per_T={("%.2f" % T): {str(a): CR(T, h, xd, best[0], theta_deg=a) for a in (0, 30, 50, 70)} for T in Ts},
                               sigma_1p41={("%.2f" % T): CR(T, h, xd, 1.41) for T in Ts})
    out["exit"] = rows
    # side band absorbing part (thickness W - sd0 = 30 m, sigma 1.41, pow 2, the D values) for waves leaving the focus sideways:
    # incidence on the band = 90 deg - |theta| (a +theta component moving away from the axis)
    sd = {}
    for thick in (30.0, 35.0):
        sd["%d" % thick] = {("%.2f" % T): {str(th): CR(T, h, thick, 1.41, theta_deg=90.0 - th) for th in (30, 50, 70, 80)} for T in Ts}
    out["side_absorbing_sigma1p41"] = sd
    sw = {}
    for thick in (30.0, 40.0, 50.0):
        best = None
        for s in np.geomspace(0.3, 12.0, 50):
            v = [CR(T, h, thick, s, theta_deg=a) for T in Ts for a in (10, 25, 40)]
            if best is None or max(v) < best[1]:
                best = (float(s), max(v))
        sw["%d" % thick] = dict(sigma=best[0], CR_max_incidence_10_40=best[1])
    out["side_absorbing_best_sigma"] = sw
    ex = {}
    for xd in (70.0, 80.0, 90.0, 100.0):
        best = None
        for s in np.geomspace(0.3, 12.0, 50):
            v = [CR(T, h, xd, s, theta_deg=a) for T in Ts for a in (0, 30, 50)]
            if best is None or max(v) < best[1]:
                best = (float(s), max(v), v)
        ex["%d" % xd] = dict(sigma=best[0], CR_max_incidence_0_50=best[1], CR_rows_T_by_angle=[round(v, 4) for v in best[2]])
    out["exit_best_sigma_oblique"] = ex
    out["chosen_exit"] = dict(length_m=80.0, sigma=1.0, pow=2.0, CR={("%.2f" % T): {str(a): CR(T, h, 80.0, 1.0, theta_deg=a) for a in (0, 30, 50)} for T in Ts})
    return out


# ============================================================================================ cases (frozen list; a_sum = DM1A unless named *_E)
CASES = [
    # name, P, ns, fw, dspec
    ("M7_cross50s12", 7.0, (1,), "eq", ("cross", 50.0, 12.0, 25)),                 # monochromatic reference (DFG-1 like) on the same bed
    ("P28_345_jon_cross50s12", 28.0, (3, 4, 5), "jonswap", ("cross", 50.0, 12.0, 25)),   # the campaign-E DFG-2 proposal, a_sum not enlarged
    ("P28_345_eq_cross50s12", 28.0, (3, 4, 5), "eq", ("cross", 50.0, 12.0, 25)),
    ("P28_345_eq_hyb60s28", 28.0, (3, 4, 5), "eq", ("hyb", 60.0, 28.0, 85.0, 17)),       # the plan E X2 direction set, 3 frequencies
    ("P28_345_eq_uni80", 28.0, (3, 4, 5), "eq", ("uni", 80.0, 25)),
    ("P28_345_eq_cross60s15", 28.0, (3, 4, 5), "eq", ("cross", 60.0, 15.0, 25)),
    ("P21_234_eq_cross50s12", 21.0, (2, 3, 4), "eq", ("cross", 50.0, 12.0, 25)),
    ("P28_345_mid_cross50s12", 28.0, (3, 4, 5), [0.3, 0.4, 0.3], ("cross", 50.0, 12.0, 25)),
    # round 2 (added after round 1 was read: the X2 hybrid set gave the best isolation, cross60s15 the narrowest crest)
    ("P28_345_jon_hyb60s28", 28.0, (3, 4, 5), "jonswap", ("hyb", 60.0, 28.0, 85.0, 17)),
    ("P28_345_mid_hyb60s28", 28.0, (3, 4, 5), [0.3, 0.4, 0.3], ("hyb", 60.0, 28.0, 85.0, 17)),
    ("P28_345_eq_hyb60s20", 28.0, (3, 4, 5), "eq", ("hyb", 60.0, 20.0, 85.0, 17)),
    ("P28_345_eq_hyb65s25", 28.0, (3, 4, 5), "eq", ("hyb", 65.0, 25.0, 85.0, 17)),
    ("P28_345_eq_hyb55s28", 28.0, (3, 4, 5), "eq", ("hyb", 55.0, 28.0, 85.0, 17)),
    ("P28_345_eq_cross60s20", 28.0, (3, 4, 5), "eq", ("cross", 60.0, 20.0, 25)),
    ("P21_234_eq_hyb60s28", 21.0, (2, 3, 4), "eq", ("hyb", 60.0, 28.0, 85.0, 17)),
    ("M7_hyb60s28", 7.0, (1,), "eq", ("hyb", 60.0, 28.0, 85.0, 17)),
]


# variants of the chosen set (round 3, after rounds 1-2 were read): realization models and the decision-rule branches
#   name, base case, a_sum, per-frequency realization (n = 3, 4, 5)
VARIANTS = [
    ("DFG2_real_mid", "P28_345_eq_hyb60s28", A_SUM_DM1A, (0.95, 0.88, 0.80)),   # FLIP45 r0(0.5) 0.88 at T 7 + damping ~ (dx/L)^1 [guess]
    ("DFG2_real_low", "P28_345_eq_hyb60s28", A_SUM_DM1A, (0.92, 0.83, 0.68)),   # damping ~ (dx/L)^2 and the 5.5 %/L upper rate [guess]
    ("DFG2_k62", "P28_345_eq_hyb60s28", 7.10, None),                             # branch B2: kpA 0.62 (a_sum x1.12), below the energy match
    ("DFG2_k62_real_mid", "P28_345_eq_hyb60s28", 7.10, (0.95, 0.88, 0.80)),
    ("DFG2n_hyb65s25_real_mid", "P28_345_eq_hyb65s25", A_SUM_DM1A, (0.95, 0.88, 0.80)),   # branch B1: narrower lobes, one change
]


def run_variants(names=None):
    p = os.path.join(OUT, "dfg52_screen.json")
    with open(p, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = []
    for nm, base, aS, real in VARIANTS:
        if names and nm not in names:
            continue
        b = [cc for cc in CASES if cc[0] == base][0]
        r = evaluate(nm, b[1], b[2], b[3], b[4], a_sum=aS, real=real)
        r["base_case"] = base
        rows.append(r)
        pr(r)
    new = {r["name"] for r in rows}
    doc["rows"] = [o for o in doc["rows"] if o["name"] not in new] + rows
    doc["date_variants"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=float)
    print("wrote", p)


def run(names=None):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "dfg52_screen.json")
    old = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            old = json.load(fh).get("rows", [])
    rows = []
    for nm, P, ns, fw, ds in CASES:
        if names and nm not in names and not any(n.startswith(nm + "_E") for n in names):
            continue
        r = evaluate(nm, P, ns, fw, ds)
        rows.append(r)
        pr(r)
    # energy-matched variants (sum a^2 = DM1A) on request: name + '_E'
    for n in (names or []):
        if n.endswith("_E"):
            base = [cc for cc in CASES if cc[0] == n[:-2]][0]
            c = components(base[1], base[2], base[3], base[4], 1.0, LAYOUT["h"])
            aE = math.sqrt(SUMA2_DM1A / np.sum(c["a"] ** 2))
            r = evaluate(n, base[1], base[2], base[3], base[4], a_sum=aE)
            rows.append(r)
            pr(r)
    names_new = {r["name"] for r in rows}
    allrows = [o for o in old if o["name"] not in names_new] + rows
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip52/dfg52_screen.py", layout=LAYOUT, rows=allrows),
                  fh, indent=1, default=float)
    print("wrote", p)


def pr(r):
    L = r["lin"]; N = r.get("nl2", {})
    print("%-26s a_sum %.3f (x%.2f, sum a2 x%.2f, aE %.2f) nc %3d | lin Hc %.2f W50 %.2f W80 %.2f W95 %.2f K %.2f S2 %.2f ring %.2f N1 %.2f miss %.2f |"
          " nl2 Hc %.2f W50 %.2f W80 %.2f W95 %.2f S2 %.2f ring %.2f N1 %.2f miss %.2f | Nt lin %.2f nl2 %.2f | c_in %.2f/%.2f gain %.2f amax %.3f |"
          " bands kp*crest in %.2f sd %.2f | ap %.3f t_full %.1f | %.0fs" % (
              r["name"], r["a_sum"], r["a_sum_over_DM1A"], r["sum_a2_over_DM1A"], r["a_sum_energy_match"], r["ncomp"],
              L["Hc"], L["W50"], L["W80"], L["W95"], L["K"], L["S2"], L.get("ring_max", float("nan")), L["N1"]["N1"], L["miss"],
              N.get("Hc", 0), N.get("W50", 0), N.get("W80", 0), N.get("W95", 0), N.get("S2", 0), N.get("ring_max", float("nan")),
              (N.get("N1") or {}).get("N1", float("nan")), N.get("miss", 0), r["Nt_lin"], r.get("Nt_nl2", float("nan")),
              r["c_in_line_lin"], r.get("c_in_line_nl2", float("nan")), r.get("gain_over_c_in_nl2", float("nan")), r["a_max_comp"],
              r["bands"]["kp_crest_inlet_nl2"], r["bands"]["kp_crest_side_nl2"], r["rays"]["aperture"], r["rays"]["t_full_s"], r["cpu_s"]), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run":
        run(a[1:] or None)
    elif a and a[0] == "variants":
        run_variants(a[1:] or None)
    elif a and a[0] == "sponge":
        o = sponge_study()
        os.makedirs(OUT, exist_ok=True)
        json.dump(o, open(os.path.join(OUT, "dfg52_sponge.json"), "w", encoding="utf-8"), indent=1)
        print(json.dumps({k: (v["sigma_minmax"], round(v["CR_max_normal"], 4)) for k, v in o["exit"].items()}), "check", round(o["check_flip45"], 4))
    elif a and a[0] == "list":
        for cc in CASES:
            print(cc)
    else:
        print(__doc__)
