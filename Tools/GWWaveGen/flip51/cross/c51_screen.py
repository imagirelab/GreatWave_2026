# -*- coding: utf-8 -*-
"""FLIP51 mechanism screen 'crossing seas' (numpy only, py -3.10 -B). 2026-10-17 written new (Claude). Read only on flip50 / e51 code.

Question: can two swell systems crossing at a large angle (McAllister et al. 2019, JFM 860: Draupner recreated only with two systems
crossing at a large angle; breaking is less crest-limiting and forms near-vertical jets) give a summit that converges upward like the
user's target (W50/Hc ~2, W80/Hc ~1, S2 ~0.2), and how far does a non-breaking (2nd-order) estimate get?

Field: the FLIP50 option-D monochromatic directional sea (g50_dirfield.DirField: WKB shoaling + Snell refraction over the laterally
straight D19B bed, all phases 0 at (x_f, 0) at t = 0), with the direction set changed from 'uniform +-80 deg' to two lobes at
+-theta0 (half width delta, equal amplitudes) = a crossing pair (+theta and -theta; the half tank mirror makes the pair).
Second order: Sharma & Dean (1981) / Forristall (2000) sum and difference kernels for equal-frequency directional components, with the
local k(x), kx_j(x), ky_j, h(x) per column (R = om^2/g is the same for all components).
Metrics: e51_metrics.hf_metrics (the frozen target metrics) on the synthetic height field at the instant of the largest crest.
Outputs: Unity/Build/FLIP51/cross/screen_<tag>.json
usage: py -3.10 -B c51_screen.py selftest | sweep | one <T> <theta0> <delta> <eps> [x_f]
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
ROOT = r"G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, ROOT + "/Tools/GWWaveGen/flip50")
sys.path.insert(0, ROOT + "/Tools/GWWaveGen/flip51")
import numpy as np                 # noqa: E402
import g50_dirfield as DF          # noqa: E402  (read only)
import e51_metrics as EM           # noqa: E402  (read only)

G = DF.G
OUT = ROOT + "/Unity/Build/FLIP51/cross"
BED = dict(h0=19.0, x_toe=160.25, s=10.0, kind="beach")


def comp_set(kind, theta0=None, delta=None, n_lobe=None, theta_max=80.0, n=30):
    if kind == "uniform":
        th, w = DF.components(theta_max, n, "uniform")
        return th, w
    if delta <= 0:
        th1 = np.array([theta0])
    else:
        th1 = np.linspace(theta0 - delta, theta0 + delta, n_lobe)
    th = np.concatenate([-th1[::-1], th1])
    w = np.ones_like(th)
    return th, w / w.sum()


def kernels(k, kxv, kyv, h, R):
    """K+ and K- (n x n) for equal-frequency components with wavevectors (kxv, kyv) at depth h."""
    cosD = (np.outer(kxv, kxv) + np.outer(kyv, kyv)) / (k * k)
    kdot = k * k * cosD
    kp = np.sqrt(np.maximum((kxv[:, None] + kxv[None, :]) ** 2 + (kyv[:, None] + kyv[None, :]) ** 2, 0.0))
    Dp = (4 * R * (k * k - R * R) + 8 * R * (kdot - R * R)) / (4 * R - kp * np.tanh(kp * h))
    Kp = 0.25 * ((Dp - (kdot - R * R)) / R + 2 * R)
    Km = 0.25 * (R - kdot / R)          # D- = 0 for equal frequencies (numerator vanishes, denominator -k_ tanh(k_ h) != 0)
    return Kp, Km


def selftest():
    out = {}
    for h, T in ((19.0, 7.0), (19.0, 12.0), (1000.0, 7.0)):
        om = 2 * math.pi / T
        k = float(DF.kdisp(om, h)); R = om * om / G
        Kp, Km = kernels(k, np.array([k]), np.array([0.0]), h, R)
        st = k / 4 * math.cosh(k * h) * (2 + math.cosh(2 * k * h)) / math.sinh(k * h) ** 3 if k * h < 50 else k / 2
        sd = -k / (2 * math.sinh(2 * k * h)) if k * h < 50 else 0.0
        out["stokes_h%g_T%g" % (h, T)] = dict(Kp=float(Kp[0, 0]), stokes=st, rel=float(Kp[0, 0] / st - 1),
                                             Km_x1=float(Km[0, 0]), setdown=sd)
    # deep collinear bichromatic is not representable (equal frequency); check deep standing: B+ (0,180) = 0, B- = k/2
    k = 0.05; R = k
    Kp, Km = kernels(k, np.array([k, -k]), np.array([0.0, 0.0]), 1e4, R)
    out["deep_standing"] = dict(Kp01=float(Kp[0, 1]), Km01=float(Km[0, 1]), expect_Kp=0.0, expect_Km=k / 2)
    # deep crossing 120 deg: set-up (K- > 0)
    th = math.radians(60)
    Kp, Km = kernels(k, np.array([k * math.cos(th)] * 2), np.array([k * math.sin(th), -k * math.sin(th)]), 1e4, R)
    out["deep_cross120"] = dict(Kp01=float(Kp[0, 1]), Km01=float(Km[0, 1]), note="K- > 0: bound set-up under crossing at 120 deg")
    return out


class Field:
    def __init__(self, T, th, w, x_f, x, y, bed=BED):
        self.T = T; self.om = 2 * math.pi / T; self.R = self.om ** 2 / G
        self.x = x; self.y = y; self.x_f = x_f
        self.df = DF.DirField(T, th, w, 1.0, x, bed, x_f)          # unit a_sum; scaled later
        self.h = self.df.h
        # unit-amplitude complex components on the grid: M_j(x, y) = A_j(x) exp(i(Phi_j(x) + ky_j y))
        df = self.df
        self.E = (df.Aj * np.exp(1j * df.Phi))[:, :, None] * np.exp(1j * df.ky[:, None] * y[None, :])[:, None, :]   # (n, nx, ny)
        self.A1 = self.E.sum(0)                                                                                     # (nx, ny)
        n, nx, ny = self.E.shape
        self.Pp = np.zeros((nx, ny), complex); self.Pm = np.zeros((nx, ny))
        for i in range(nx):
            if not df.wet[i] or df.h[i] < 0.5:
                continue
            Kp, Km = kernels(df.k[i], df.kx[:, i], df.ky, df.h[i], self.R)
            M = self.E[:, i, :]                                    # (n, ny)
            self.Pp[i] = np.einsum("my,mn,ny->y", M, Kp, M)
            self.Pm[i] = np.real(np.einsum("my,mn,ny->y", M, Km, np.conj(M)))
        jf = int(np.argmin(np.abs(x - x_f)))
        self.Af_unit = float(abs(self.A1[jf, 0]))
        self.kf = float(df.k[jf]); self.hf = float(df.h[jf])

    def eta(self, s, t, order=2):
        """s = a_sum scale; returns eta(x, y) at time t."""
        e = np.real(s * self.A1 * np.exp(-1j * self.om * t))
        if order >= 2:
            e = e + np.real(s * s * self.Pp * np.exp(-2j * self.om * t)) + s * s * self.Pm
        return e


def metrics_at(F, s, order, xwin, tgrid):
    best = (-1e9, None)
    sel = (F.x >= xwin[0]) & (F.x <= xwin[1])
    for t in tgrid:
        e = F.eta(s, t, order)
        v = float(e[sel].max())
        if v > best[0]:
            best = (v, t)
    t = best[1]
    e = F.eta(s, t, order)
    meta = dict(x0=float(F.x[0]), dx=float(F.x[1] - F.x[0]), z0=float(F.y[0]), dz=float(F.y[1] - F.y[0]))
    m = EM.hf_metrics(e.T.copy(), meta, 0.0, xwin=xwin)
    m["t_max"] = t
    sc, per = EM.score_vs_target(m)
    m["target_miss"] = sc; m["target_miss_per"] = per
    return m, e


def incoming(F, s, x_g=110.0, order=2):
    """max crest (over y in 0-95 m and one period) at the gauge line x_g, and max linear |A| over the inlet band x 20-100 m."""
    i = int(np.argmin(np.abs(F.x - x_g)))
    ts = np.linspace(0, F.T, 49)
    c = max(float(F.eta(s, t, order)[i, F.y <= 95.0].max()) for t in ts)
    band = (F.x >= 20.0) & (F.x <= 100.0)
    a_band = float(np.abs(s * F.A1[band][:, F.y <= 95.0]).max())
    return c, a_band


KEYS = ["Hc", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "ring_mean", "Lx50", "A50", "target_miss",
        "W50_cens", "W20_cens", "t_max", "x_pk", "c_side_6Hc"]


def run_case(T, kind, theta0, delta, n_lobe, x_f, eps_list, dx=1.0):
    x = np.arange(0.0, x_f + 70.0 + 1e-9, dx)
    y = np.arange(0.0, 140.0 + 1e-9, dx)
    th, w = comp_set(kind, theta0, delta, n_lobe)
    F = Field(T, th, w, x_f, x, y)
    ap = DF.aperture(F.df, 140.0, 45.0, 100.0, 180.25, 210.25)["frac"]
    xwin = (x_f - 60.0, x_f + 35.0)
    tgrid = np.linspace(-0.3 * T, 0.3 * T, 61)
    rows = []
    for eps in eps_list:
        s = eps / (F.kf * F.Af_unit)              # a_sum giving linear k_f A_f = eps at the focus
        r = dict(eps=eps, a_sum=s, a_j=s / len(th), A_f_lin=s * F.Af_unit)
        for order in (1, 2):
            m, e = metrics_at(F, s, order, xwin, tgrid)
            r["o%d" % order] = {k: (float(m[k]) if isinstance(m.get(k), (int, float, np.floating)) else m.get(k)) for k in KEYS if k in m}
            r["o%d" % order]["kHc"] = float(F.kf * m["Hc"])
            r["o%d" % order]["ky0Hc"] = float(F.df.k0 * math.sin(math.radians(theta0 if kind != "uniform" else 80.0)) * m["Hc"])
            r["o%d" % order]["W50_m"] = float(m["W50"] * m["Hc"])
            r["o%d" % order]["Lx50_m"] = float(m["Lx50"] * m["Hc"])
        c_in, a_band = incoming(F, s)
        r["c_in_x110"] = c_in; r["max_linA_inlet_band"] = a_band
        r["gain_over_incoming"] = r["o2"]["Hc"] / c_in
        r["gain_over_component"] = r["o2"]["Hc"] / (s / len(th))
        r["gain_nonlin"] = r["o2"]["Hc"] / r["A_f_lin"]
        r["k_inlet_band_max"] = float(F.df.k0 * a_band)
        rows.append(r)
    return dict(T=T, kind=kind, theta0=theta0, delta=delta, n=len(th), x_f=x_f, h_f=F.hf, k_f=F.kf, k0=float(F.df.k0),
                L0=float(2 * math.pi / F.df.k0), L_f=float(2 * math.pi / F.kf), aperture=ap, rows=rows)


def main():
    a = sys.argv[1:]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    if not a or a[0] == "selftest":
        print(json.dumps(selftest(), indent=1)); return
    if a[0] == "one":
        T, th0, dl, eps = float(a[1]), float(a[2]), float(a[3]), float(a[4])
        xf = float(a[5]) if len(a) > 5 else 190.25
        kind = "uniform" if th0 <= 0 else "lobes"
        r = run_case(T, kind, th0, dl, 7 if dl > 0 else 1, xf, [eps])
        print(json.dumps(r, indent=1, default=float)); print("cpu %.1f s" % (time.time() - t0)); return
    if a[0] == "sweep":
        tag = a[1] if len(a) > 1 else "A"
        cases = []
        if tag == "cal":     # calibration against the measured D runs (uniform +-80, their own T, x_f, at the linear design eps)
            for T in (12.0, 10.0):
                cases.append(run_case(T, "uniform", None, None, None, 220.25, [0.20, 0.30, 0.40]))
        elif tag == "A":     # crossing pairs at T 7 s, focus x_f 190.25 (h 16 m)
            for th0, dl in ((80.0, -1), (45.0, 0.0), (60.0, 0.0), (70.0, 0.0), (45.0, 15.0), (60.0, 15.0), (70.0, 10.0), (60.0, 25.0)):
                kind = "uniform" if dl < 0 else "lobes"
                cases.append(run_case(7.0, kind, th0, max(dl, 0.0), 7 if dl > 0 else 1, 190.25, [0.25, 0.35, 0.45]))
        elif tag == "B":     # period sweep at the chosen crossing
            for T in (6.0, 8.0, 10.0):
                cases.append(run_case(T, "lobes", 60.0, 15.0, 7, 190.25, [0.25, 0.35, 0.45]))
        p = OUT + "/screen_%s.json" % tag
        json.dump(dict(cases=cases, cpu_s=time.time() - t0, selftest=selftest()), open(p, "w", encoding="utf8"), indent=1, default=float)
        for c in cases:
            for r in c["rows"]:
                o = r["o2"]; o1 = r["o1"]
                print("T%4.1f %-7s th0 %5s dl %5s eps %.2f | Hc %5.2f kHc %.2f nl %.2f | W50 %5.2f(%5.1fm) W80 %4.2f W95 %4.2f K %4.2f S2 %5.2f ring %4.2f Lx50 %4.2f A50 %4.2f miss %4.2f | lin W50 %5.2f | gin %.2f kAband %.2f ap %.2f"
                      % (c["T"], c["kind"], c["theta0"], c["delta"], r["eps"], o["Hc"], o["kHc"], r["gain_nonlin"], o["W50"], o["W50_m"], o["W80"], o["W95"],
                         o["K"], o["S2"], o.get("ring_max", float("nan")), o["Lx50"], o["A50"], o["target_miss"], o1["W50"],
                         r["gain_over_incoming"], r["k_inlet_band_max"], c["aperture"] or float("nan")))
        print("cpu %.1f s -> %s" % (time.time() - t0, p))


if __name__ == "__main__":
    main()
