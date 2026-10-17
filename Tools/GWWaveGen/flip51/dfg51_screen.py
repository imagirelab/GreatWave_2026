# -*- coding: utf-8 -*-
"""FLIP51 mechanism screen 'deep focused groups' (numpy only; py -3.10 -B). 2026-10-17 written new (Claude).
Reads nothing from the run folders; imports the frozen metric code e51_metrics (read only) and writes only under
Unity/Build/FLIP51/screens/dfg51/.

What it does: linear + second-order (Sharma & Dean 1981 / Dalzell 1999 / Forristall 2000 sum and difference kernels) superposition
of a directionally spread wave field that focuses at (0, 0) at t = 0, on a flat bed of depth h, then the FLIP51 convergence
metrics (e51_metrics.hf_metrics: the same 3x3 median, crest line c(y) over x_pk - 30 .. x_pk + 10 m, W(f), S1/S2, ring) of the plan
field at the instant of the largest crest near t = 0.

    eta1 = sum_j a_j cos(k_j . x - w_j t)                       (all phases 0 at the focus)
    eta2 = 1/4 sum_m sum_n a_m a_n [K+_mn cos(psi_m + psi_n) + K-_mn cos(psi_m - psi_n)]
    K+- = [D+-_mn - (k_m . k_n -+ R_m R_n)] / sqrt(R_m R_n) + (R_m + R_n),  R = w^2 / g
    D+ = {(sR_m + sR_n)[sR_m (k_n^2 - R_n^2) + sR_n (k_m^2 - R_m^2)] + 2 (sR_m + sR_n)^2 (k_m . k_n - R_m R_n)}
         / {(sR_m + sR_n)^2 - k+ tanh(k+ h)}
    D- = {(sR_m - sR_n)[sR_n (k_m^2 - R_m^2) - sR_m (k_n^2 - R_n^2)] + 2 (sR_m - sR_n)^2 (k_m . k_n + R_m R_n)}
         / {(sR_m - sR_n)^2 - k- tanh(k- h)}          (m = n: limit along the same direction, d omega -> 0)
Self-test: collinear pair -> finite-depth Stokes 2nd order, deep crossing pair -> known values.

usage:  py -3.10 -B dfg51_screen.py selftest | run
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import e51_metrics as EM  # noqa: E402  (read only: hf_metrics, score_vs_target, TARGET)

G = 9.81
OUT = os.path.join(EM.ROOT, "Unity/Build/FLIP51/screens/dfg51")


def kdisp(w, h):
    w = np.atleast_1d(np.asarray(w, float))
    k = w * w / G / np.sqrt(np.tanh(w * w / G * h))
    for _ in range(60):
        th = np.tanh(k * h)
        f = G * k * th - w * w
        df = G * th + G * k * h * (1 - th * th)
        k = k - f / df
    return k


# ---------------------------------------------------------------------------------------------------------------- spectra
def spread_weights(spread, n):
    """-> theta (rad), weight (sum 1). spread: ('uni', deg) | ('cos2s', s, deg_max) | ('cross', beta_deg, sigma_deg)."""
    kind = spread[0]
    if kind == "uni":
        tm = math.radians(spread[1])
        th = np.linspace(-tm, tm, n)
        w = np.ones(n)
    elif kind == "cos2s":
        s = spread[1]; tm = math.radians(spread[2])
        th = np.linspace(-tm, tm, n)
        w = np.cos(th / 2.0) ** (2 * s)
    elif kind == "fgd":
        tm = math.radians(spread[1])
        th = np.linspace(-tm, tm, n)
        w = 1.0 / np.maximum(np.cos(th), math.cos(math.radians(spread[2])))
    elif kind == "cross":
        b = math.radians(spread[1]); sg = math.radians(spread[2])
        th = np.linspace(-b - 2.5 * sg, b + 2.5 * sg, n)
        w = np.exp(-0.5 * ((th - b) / sg) ** 2) + np.exp(-0.5 * ((th + b) / sg) ** 2)
    else:
        raise ValueError(kind)
    return th, w / w.sum()


def freq_weights(band, Tp):
    """-> omega (rad/s), weight (sum 1), period of the field P (s, None = not periodic).
    band: ('mono',) | ('per', P, f_lo/fp, f_hi/fp, gamma) harmonics n/P in the band, JONSWAP amplitude spectrum shape x df
          | ('nw', nf, f_lo/fp, f_hi/fp, gamma) dense NewWave (amplitude ~ S(f) df)."""
    fp = 1.0 / Tp
    if band[0] == "mono":
        return np.array([2 * math.pi * fp]), np.array([1.0]), Tp
    if band[0] == "per":
        P, lo, hi, gam = band[1:]
        n = np.arange(math.ceil(lo * fp * P - 1e-9), math.floor(hi * fp * P + 1e-9) + 1)
        f = n / P
        Pfield = P
    else:
        nf, lo, hi, gam = band[1:]
        f = np.linspace(lo * fp, hi * fp, nf)
        Pfield = None
    sig = np.where(f <= fp, 0.07, 0.09)
    S = f ** -5 * np.exp(-1.25 * (fp / f) ** 4) * gam ** np.exp(-0.5 * ((f - fp) / (sig * fp)) ** 2)
    return 2 * math.pi * f, S / S.sum(), Pfield


def components(Tp, h, band, spread, A, ntheta):
    w, fw, P = freq_weights(band, Tp)
    th, dw = spread_weights(spread, ntheta)
    W, TH = np.meshgrid(w, th, indexing="ij")
    a = A * np.outer(fw, dw).ravel()
    om = W.ravel()
    k = kdisp(om, h)
    kx = k * np.cos(TH.ravel()); ky = k * np.sin(TH.ravel())
    keep = a > 1e-6 * a.max()
    return dict(a=a[keep], om=om[keep], k=k[keep], kx=kx[keep], ky=ky[keep], h=h, P=P, Tp=Tp, A=A)


# ---------------------------------------------------------------------------------------------------------------- 2nd order
def kernels(c, i, j):
    """K+ and K- for index arrays i, j (vectorised)."""
    h = c["h"]
    R1 = c["om"][i] ** 2 / G; R2 = c["om"][j] ** 2 / G
    s1 = np.sqrt(R1); s2 = np.sqrt(R2)
    k1 = c["k"][i]; k2 = c["k"][j]
    kk = c["kx"][i] * c["kx"][j] + c["ky"][i] * c["ky"][j]
    kp = np.hypot(c["kx"][i] + c["kx"][j], c["ky"][i] + c["ky"][j])
    km = np.hypot(c["kx"][i] - c["kx"][j], c["ky"][i] - c["ky"][j])
    Dp = ((s1 + s2) * (s1 * (k2 ** 2 - R2 ** 2) + s2 * (k1 ** 2 - R1 ** 2)) + 2 * (s1 + s2) ** 2 * (kk - R1 * R2)) / \
         ((s1 + s2) ** 2 - kp * np.tanh(kp * h))
    Kp = (Dp - (kk - R1 * R2)) / np.sqrt(R1 * R2) + (R1 + R2)
    den = (s1 - s2) ** 2 - km * np.tanh(km * h)
    with np.errstate(invalid="ignore", divide="ignore"):
        Dm = ((s1 - s2) * (s2 * (k1 ** 2 - R1 ** 2) - s1 * (k2 ** 2 - R2 ** 2)) + 2 * (s1 - s2) ** 2 * (kk + R1 * R2)) / den
        Km = (Dm - (kk + R1 * R2)) / np.sqrt(R1 * R2) + (R1 + R2)
    return Kp, Km


def km_self(c, idx):
    """K-_mm: limit d omega -> 0 along the same direction (the set-down of a group of this component)."""
    eps = 1e-4
    out = np.zeros(len(idx))
    for q, m in enumerate(idx):
        om2 = c["om"][m] * (1 + eps)
        k2 = kdisp(om2, c["h"])[0]
        u = np.array([c["kx"][m], c["ky"][m]]) / c["k"][m]
        cc = dict(om=np.array([c["om"][m], om2]), k=np.array([c["k"][m], k2]), kx=np.array([c["kx"][m], k2 * u[0]]),
                  ky=np.array([c["ky"][m], k2 * u[1]]), h=c["h"])
        _, Km = kernels(cc, np.array([0]), np.array([1]))
        out[q] = Km[0]
    return out


def second_order(c):
    """-> list of (amp, Kx, Ky, Om) arrays for eta2 (sum and difference waves), using m <= n with factor 2 off the diagonal."""
    n = len(c["a"])
    I, J = np.triu_indices(n)
    Kp, Km = kernels(c, I, J)
    diag = I == J
    Km[diag] = km_self(c, I[diag])
    fac = np.where(diag, 1.0, 2.0) * 0.25 * c["a"][I] * c["a"][J]
    amp = np.concatenate([fac * Kp, fac * Km])
    Kx = np.concatenate([c["kx"][I] + c["kx"][J], c["kx"][I] - c["kx"][J]])
    Ky = np.concatenate([c["ky"][I] + c["ky"][J], c["ky"][I] - c["ky"][J]])
    Om = np.concatenate([c["om"][I] + c["om"][J], c["om"][I] - c["om"][J]])
    ok = np.isfinite(amp) & (np.abs(amp) > 0)
    return dict(a=amp[ok], kx=Kx[ok], ky=Ky[ok], om=Om[ok])


def field(comp, x, y, t, chunk=20000):
    """Re sum a exp(i(kx x + ky y - om t)) on the grid y (rows) x x (cols)."""
    out = np.zeros((len(y), len(x)))
    n = len(comp["a"])
    for s in range(0, n, chunk):
        sl = slice(s, s + chunk)
        A = comp["a"][sl] * np.exp(-1j * comp["om"][sl] * t)
        Ey = np.exp(1j * np.outer(y, comp["ky"][sl])) * A[None, :]
        Ex = np.exp(1j * np.outer(comp["kx"][sl], x))
        out += (Ey @ Ex).real
    return out


# ---------------------------------------------------------------------------------------------------------------- one case
def evaluate(name, Tp, h, band, spread, kA, ntheta=31, xwin=(-100.0, 60.0), ywid=130.0, second=True, scan=(-3.0, 3.0, 0.05),
             r_in=None):
    c0 = components(Tp, h, band, spread, 1.0, ntheta)
    kp = float(kdisp(2 * math.pi / Tp, h)[0]); Lp = 2 * math.pi / kp
    A = kA / kp
    c = components(Tp, h, band, spread, A, ntheta)
    x = np.arange(xwin[0], xwin[1] + 0.5, 1.0)
    yh = 0.5 + np.arange(0, int(ywid))
    # linear: time of the largest crest near t = 0 (centre row, cheap)
    ts = np.arange(scan[0], scan[1] + 1e-9, scan[2])
    lin_c = [field(c, x, np.array([0.5]), t).max() for t in ts]
    t1 = float(ts[int(np.argmax(lin_c))])
    res = dict(name=name, Tp=Tp, h=h, band=list(band), spread=list(spread), kA=kA, A_lin_sum=A, Lp=Lp, kph=kp * h, ncomp=len(c["a"]),
               a_max_comp=float(c["a"].max()), period_field_s=c["P"])
    meta = dict(z0=0.5, dz=1.0, x0=float(x[0]), dx=1.0)
    eta_l = field(c, x, yh, t1)
    ml = EM.hf_metrics(eta_l, meta, 0.0, xwin=(-40.0, 40.0))
    res["lin"] = slim(ml, kp)
    res["lin"]["t"] = t1
    if second:
        c2 = second_order(c)
        best = None
        for dt in (-0.5, -0.3, -0.15, 0.0, 0.15, 0.3, 0.5):
            e = eta_l if False else field(c, x, yh, t1 + dt) + field(c2, x, yh, t1 + dt)
            m = EM.hf_metrics(e, meta, 0.0, xwin=(-40.0, 40.0))
            if m and (best is None or m["Hc"] > best[0]["Hc"]):
                best = (m, t1 + dt, e)
        m2, t2, e2 = best
        res["nl2"] = slim(m2, kp)
        res["nl2"]["t"] = t2
        res["nl2"]["Hc_over_Alin"] = m2["Hc"] / A
        res["n_pairs"] = len(c2["a"])
    # incoming crest: the largest linear crest at r >= r_in from the focus over one field period (or +-40 s), coarse grid
    r_in = 1.5 * Lp if r_in is None else r_in
    xb = np.arange(-3.0 * Lp, 0.5 * Lp, 2.0); yb = np.arange(0.0, 2.0 * Lp, 2.0)
    XX, YY = np.meshgrid(xb, yb)
    far = np.hypot(XX, YY) >= r_in
    Pw = c["P"] if c["P"] else 80.0
    tt = np.arange(-Pw / 2, Pw / 2, 0.25)
    inc = 0.0
    for t in tt:
        f = field(c, xb, yb, t)
        inc = max(inc, float(f[far].max()))
    res["incoming_crest_lin"] = inc
    res["r_in_m"] = r_in
    Hc = res["nl2"]["Hc"] if second else res["lin"]["Hc"]
    res["gain_over_incoming"] = Hc / inc
    res["gain_over_component"] = Hc / res["a_max_comp"]
    return res


KEYS = ["Hc", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "Lx50", "A50", "W20_cens", "W50_cens"]


def slim(m, kp):
    o = {k: (round(float(m[k]), 4) if isinstance(m.get(k), (float, int)) and not isinstance(m.get(k), bool) else m.get(k))
         for k in KEYS if k in m}
    o["kHc"] = round(kp * m["Hc"], 4)
    o["W50_m"] = round(m["W50"] * m["Hc"], 2)
    miss, per = EM.score_vs_target(m)
    o["miss"] = round(miss, 3)
    return o


# ---------------------------------------------------------------------------------------------------------------- self test
def selftest():
    out = {}
    for kh in (0.8, 1.75, 4.0):
        h = 20.0; k = kh / h; om = math.sqrt(G * k * math.tanh(kh))
        c = dict(om=np.array([om, om]), k=np.array([k, k]), kx=np.array([k, k]), ky=np.array([0.0, 0.0]), h=h)
        Kp, _ = kernels(c, np.array([0]), np.array([0]))
        stokes = k / 4 * math.cosh(kh) * (2 + math.cosh(2 * kh)) / math.sinh(kh) ** 3   # coefficient of a^2 cos 2psi
        out["collinear_kh%.2f" % kh] = dict(code=float(0.25 * Kp[0]), stokes=stokes)
    # deep, opposing equal waves: the sum term has no spatial part (k+ = 0) and its coefficient -> 0
    h = 500.0; k = 0.05; om = math.sqrt(G * k)
    c = dict(om=np.array([om, om]), k=np.array([k, k]), kx=np.array([k, -k]), ky=np.array([0.0, 0.0]), h=h)
    Kp, Km = kernels(c, np.array([0]), np.array([1]))
    out["deep_opposing"] = dict(Kp=float(Kp[0]), Km_over_k=float(Km[0] / k), note="standing wave: eta2 = (k a^2/2) cos 2kx from K- "
                                "(expected Km = 2k: with the diagonal Stokes terms eta2 = (k A^2/2) cos 2kx cos^2 wt for A = 2a, Rayleigh)")
    return out


CASES = [
    # name, Tp, h, band, spread, kA list, ntheta
    ("F07_fochesato_uni45", 7.004, 20.0, ("mono",), ("uni", 45.0), [0.549], 30),
    ("M_uni80_T7h20", 7.0, 20.0, ("mono",), ("uni", 80.0), [0.15, 0.35, 0.55], 41),
    ("M_uni90_T7h20", 7.0, 20.0, ("mono",), ("uni", 90.0), [0.15, 0.35, 0.55], 41),
    ("M_cross120_T7h20", 7.0, 20.0, ("mono",), ("cross", 60.0, 8.0), [0.15, 0.35, 0.55], 41),
    ("M_cross90_T7h20", 7.0, 20.0, ("mono",), ("cross", 45.0, 8.0), [0.15, 0.35, 0.55], 41),
    ("P28_uni80_T7h20", 7.0, 20.0, ("per", 28.0, 0.6, 1.6, 3.3), ("uni", 80.0), [0.15, 0.35, 0.55], 25),
    ("P42_uni80_T7h20", 7.0, 20.0, ("per", 42.0, 0.6, 1.6, 3.3), ("uni", 80.0), [0.15, 0.35, 0.55], 25),
    ("P42_cross120_T7h20", 7.0, 20.0, ("per", 42.0, 0.6, 1.6, 3.3), ("cross", 60.0, 8.0), [0.15, 0.35, 0.55], 25),
    ("NW_uni80_T7h20", 7.0, 20.0, ("nw", 14, 0.6, 1.8, 3.3), ("uni", 80.0), [0.15, 0.35, 0.55], 21),
    ("P42_uni80_T7h40deep", 7.0, 40.0, ("per", 42.0, 0.6, 1.6, 3.3), ("uni", 80.0), [0.15, 0.35, 0.55], 25),
    ("P42_uni80_T7h12", 7.0, 12.0, ("per", 42.0, 0.6, 1.6, 3.3), ("uni", 80.0), [0.15, 0.35, 0.55], 25),
    ("M_uni80_T12h19_DM1Alike", 12.0, 19.0, ("mono",), ("uni", 80.0), [0.15, 0.35], 30),
    ("P48_uni80_T8h25", 8.0, 25.0, ("per", 48.0, 0.6, 1.6, 3.3), ("uni", 80.0), [0.15, 0.35, 0.55], 25),
    ("M_uni80_T8h25", 8.0, 25.0, ("mono",), ("uni", 80.0), [0.15, 0.35, 0.55], 41),
    # round 2 (added after round 1 was read): wider lobes, other crossing angles, large-angle weighting, steeper focus
    ("M_cross120s15_T7h20", 7.0, 20.0, ("mono",), ("cross", 60.0, 15.0), [0.55, 0.7], 41),
    ("P28_cross120_T7h20", 7.0, 20.0, ("per", 28.0, 0.6, 1.6, 3.3), ("cross", 60.0, 8.0), [0.55, 0.7], 25),
    ("P28_cross120s15_T7h20", 7.0, 20.0, ("per", 28.0, 0.6, 1.6, 3.3), ("cross", 60.0, 15.0), [0.55, 0.7], 25),
    ("P28_cross140s12_T7h20", 7.0, 20.0, ("per", 28.0, 0.6, 1.6, 3.3), ("cross", 70.0, 12.0), [0.55, 0.7], 25),
    ("P28_cross100s12_T7h20", 7.0, 20.0, ("per", 28.0, 0.6, 1.6, 3.3), ("cross", 50.0, 12.0), [0.55, 0.7], 25),
    ("P28_fgd85_T7h20", 7.0, 20.0, ("per", 28.0, 0.6, 1.6, 3.3), ("fgd", 85.0, 80.0), [0.55, 0.7], 25),
    ("P28n_cross120s15_T7h20", 7.0, 20.0, ("per", 28.0, 0.75, 1.35, 3.3), ("cross", 60.0, 15.0), [0.55, 0.7], 25),
    ("M_uni90_T7h20_k70", 7.0, 20.0, ("mono",), ("uni", 90.0), [0.7], 41),
    ("P28_uni80_T7h20_k70", 7.0, 20.0, ("per", 28.0, 0.6, 1.6, 3.3), ("uni", 80.0), [0.7], 25),
    # round 3: the two proposed setups (DFG-1 monochromatic fan / crossing, DFG-2 periodic 3-frequency group)
    ("M_uni80_T7h20_r3", 7.0, 20.0, ("mono",), ("uni", 80.0), [0.62, 0.7], 41),
    ("M_cross100s12_T7h20", 7.0, 20.0, ("mono",), ("cross", 50.0, 12.0), [0.62, 0.7], 41),
    ("P28n_cross100s12_T7h20", 7.0, 20.0, ("per", 28.0, 0.75, 1.35, 3.3), ("cross", 50.0, 12.0), [0.62, 0.7], 25),
    ("P28n_uni80_T7h20", 7.0, 20.0, ("per", 28.0, 0.75, 1.35, 3.3), ("uni", 80.0), [0.62, 0.7], 25),
]


def run(names=None):
    os.makedirs(OUT, exist_ok=True)
    rows = []
    t0 = time.time()
    for nm, Tp, h, band, spread, kAs, nth in CASES:
        if names and nm not in names:
            continue
        for kA in kAs:
            t1 = time.time()
            r = evaluate(nm, Tp, h, band, spread, kA, ntheta=nth)
            r["wall_s"] = round(time.time() - t1, 1)
            rows.append(r)
            L, N = r["lin"], r["nl2"]
            print("%-26s kA %.2f Lp %5.1f kh %.2f | lin Hc %5.2f W50 %5.2f W80 %5.2f W95 %5.2f K %4.2f S2 %5.2f ring %5.2f miss %4.2f |"
                  " nl2 Hc %5.2f (x%.2f) kHc %.2f W50 %5.2f (%5.1f m) W80 %5.2f W95 %5.2f taper %.2f K %4.2f S1 %.2f S2 %5.2f ring %5.2f"
                  " Lx50 %4.2f miss %4.2f | linLx50 %4.2f linring %.2f | inc %.2f gain %.2f P %s  %.0fs" % (
                      nm, kA, r["Lp"], r["kph"], L["Hc"], L["W50"], L["W80"], L["W95"], L["K"], L["S2"], L.get("ring_max", float("nan")),
                      L["miss"], N["Hc"], N["Hc_over_Alin"], N["kHc"], N["W50"], N["W50_m"], N["W80"], N["W95"], N["taper"], N["K"], N["S1"],
                      N["S2"], N.get("ring_max", float("nan")), N["Lx50"], N["miss"], L["Lx50"], L.get("ring_max", float("nan")), r["incoming_crest_lin"], r["gain_over_incoming"],
                      r["period_field_s"], r["wall_s"]), flush=True)
    p = os.path.join(OUT, "dfg51_screen.json")
    old = []
    if names and os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            old = [o for o in json.load(fh)["rows"] if o["name"] not in names]
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip51/dfg51_screen.py", rows=old + rows,
                       wall_s=round(time.time() - t0, 1)), fh, indent=1)
    print("wrote", p, "%.0f s" % (time.time() - t0))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps(selftest(), indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        run(sys.argv[2:] or None)
    else:
        print(__doc__)
