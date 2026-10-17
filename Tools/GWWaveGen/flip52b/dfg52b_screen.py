# -*- coding: utf-8 -*-
"""FLIP52B 'DFG-2B' design screen: the DFG-2 periodic multi-frequency directional group (P 28 s, T 9.33 / 7 / 5.6 s, the plan E X2 direction set,
a_sum = DM1A input sum) generated in the D19B tank (h0 19 m flat to x 160.25 m, straight 1:10 beach, side band 95-140 m as option D), with the
focus placed on the slope so that the converged crest reaches near-limiting height while it starts to shoal (py -3.10 -B; numpy, scipy).
2026-10-17 written new (Claude). Reads (read only) the X2 0.5 m and DM1A / DF1A judged numbers for the calibration; writes only
Unity/Build/FLIP52B/screens/. Imports READ ONLY: flip50/g50_dirfield (WKB DirField, kdisp, cg), flip51/dfg51_screen (Sharma-Dean kernels),
flip51/e51_metrics (frozen ruler: hf_metrics, score_vs_target, median3), flip52/g52_common (dirset, freqset, A_SUM, P_S, HARMONICS).

The sea on the beach (per frequency n, direction j; WKB over the laterally straight bed: k_y conserved, Snell refraction, shoaling):
    eta1 = sum_nj A_nj(x) cos(Phi_nj(x) + k_y,nj y - w_n (t - t_f)),  A_nj = a_nj Ks_n(x) Kr_nj(x),  Phi_nj(x_f) = 0   (g50_dirfield.DirField)
    eta2 = column-wise LOCAL Sharma-Dean sum / difference terms: at each x column the kernels use the local depth h(x) and the local wave vectors
           (k_x,nj(x), k_y,nj) and the local amplitudes and phases (a locally flat 2nd order; [computed], an approximation on a 1:10 slope).
Per candidate focus x_f (the design focus; every component has phase 0 at (x_f, 0) at t = t_f + 28 m):
  arrival   ray tracing back from the focus through the refracting bed to the inlet band end (x 100 m) or the side band inner edge (y 95 m);
            t_full = ramp 14 s + max travel time (path / c_g) over the components with a >= 5 % of the largest; t_f1 = ceil(t_full + 3.9 s)
            (the DFG-2 margin rule); aperture as g50_dirfield.aperture (per frequency, amplitude weighted)
  track     centre-row (y 0.5 m) crest of eta1 + eta2 every 0.125 s over [t_f - 12, t_f + 8] s, x 150-300 m: crest x, elevation, local depth
  focus     e51 hf_metrics (frozen ruler) at the largest 2nd-order crest over x 150-300 m, |y| <= 95 m (rows y > 95 m NaN as plan E)
  FLIP      the calibrated prediction (CAL below): crest track scaled by R and shifted upstream by dX / earlier by dT (X2 0.5 m [measured]);
            onset = first track point with R eta_c >= gamma h(x) (gamma from DM1A / DF1A onsets [measured]); e51 metrics at the 'max' instant
            of the onset (largest crest in [on - 3 s, on + 1.5 s], x [on_x - 60, on_x + 35]) on the screen field
  isolation N1 (plan E definition) at that instant; Nt = largest interior crest (linear) at |t - t_max| >= 3.5 s over one period / focal crest;
            c_in = largest incoming crest on the line x 110 m (|y| <= 95 m) over one period (plan E c_in110)
  bands     kp x largest linear crest over one period in the inlet band (x 20-100 m) and in the generating side band (y >= 95 m, x <= 180.25 m)
  print     breaker type (Iribarren), expected print-ruler numbers from the D19B plunging breakers DM1A / DF1A / DG1 [measured] with the period
            trend [guess]; see print_expectation()
usage:  py -3.10 -B dfg52b_screen.py calib | run [x_f ...] | all          (each case <= 2 min CPU)
Tags: [measured] [computed] [literature] [guess] [chosen].
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")                     # a hython run shares the machine: keep numpy modest
REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in (REPO + "/Tools/GWWaveGen/flip50", REPO + "/Tools/GWWaveGen/flip51", REPO + "/Tools/GWWaveGen/flip52"):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                                    # noqa: E402
from scipy import ndimage as ndi                      # noqa: E402
import g50_dirfield as DF                             # noqa: E402  read only
import dfg51_screen as D51                            # noqa: E402  read only
import e51_metrics as EM                              # noqa: E402  read only (frozen ruler)
import g52_common as G52                              # noqa: E402  read only (dirset, freqset, constants of DFG-2)

OUT = REPO + "/Unity/Build/FLIP52B/screens"
G = DF.G
BED = dict(h0=19.0, x_toe=160.25, s=10.0, kind="beach")            # D19B (= g50_common.SPEC_D19B through the FLIP48 plain path)
LAY = dict(W=140.0, sd0=95.0, x_in=100.0, sd_gen=180.25, sd_sw=210.25, ramp_s=14.0, wall_taper=20.0, sd_taper=11.25)   # option D bands
XG = np.arange(0.0, 330.0 + 1e-9, 1.0)                              # DirField grid (wet to x 330 m, h 2.0 m)
XWIN = (150.0, 300.0)                                                # screen window (x): h >= 5 m (x <= 300.25 m); h 5-6 m flagged "extrapolated"
YROWS = 0.5 + np.arange(0, 100)                                       # y 0.5 .. 99.5 (rows y > 95 m set NaN for the metrics, plan E)
YMAX = 95.0
TP = 7.0
H_MIN_TRACK = 5.0                                                     # the track is not read in water shallower than 5 m (x > 300.25 m);
                                                                      # local 2nd order is not valid there (Ursell) [chosen]
FPS = 24.0

# ---------------------------------------------------------------------------------------------- calibration inputs [measured]
X2_RUN = REPO + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/e51/judge_E05.json"
D_TABLES = {"DM1A": REPO + "/Unity/Build/FLIP50/runs/DM1A_D19B_T12_th80_dp0p5/pana/planD_ana.json",
            "DF1A": REPO + "/Unity/Build/FLIP50/runs/DF1A_D19B_T10_th80_dp0p5/pana/planD_ana.json",
            "DG1": REPO + "/Unity/Build/FLIP50/runs/DG1_D19Bgr_T12_th80_dp0p5/pana/planD_ana.json"}
# the D19B plunging breakers (pana/planD_table.txt medians over the judged breakers, read 2026-10-17 22:10) [measured]
D_BREAKERS = {
    "DM1A": dict(T=12.0, x_on=256.5, h_b=9.38, Hc=7.85, H_front=10.33, back_best=13.8, w07_best=2.54, lip=0.46, chord=152.0, hood=0.343, s3=0.65),
    "DF1A": dict(T=10.0, x_on=256.5, h_b=9.38, Hc=7.26, H_front=9.85, back_best=16.1, w07_best=1.90, lip=0.40, chord=142.0, hood=0.266, s3=0.56),
    "DG1": dict(T=12.0, x_on=255.5, h_b=9.47, Hc=7.88, H_front=10.30, back_best=14.7, w07_best=2.18, lip=0.36, chord=68.0, hood=0.216, s3=0.76),
}
PRINT_REF = dict(back_deg_07_09=31.3, back_band=[29.0, 38.0], width07=1.32, width07_band=[1.02, 1.42], lip=0.35, chord_deg=64.3, hood=0.186,
                 src="Unity/Build/FLIP50/plan/plan_D_frozen.json criteria.print_reference (STUDY52 ruler on the print) [measured on the print]")


# ============================================================================================== the sea on the beach
class BeachSea:
    """WKB multi-frequency directional sea on D19B. comps: one row per (n, j)."""

    def __init__(self, T_list, wf, th_deg, wd, a_sum, x_f, t_f, label=""):
        self.label = label
        self.x_f = float(x_f); self.t_f = float(t_f)
        xg = np.union1d(XG, [self.x_f])
        self.xg = xg
        self.T = [float(v) for v in T_list]
        self.dfs = [DF.DirField(T, th_deg, wd, a_sum * w, xg, BED, self.x_f) for T, w in zip(self.T, wf)]
        nd = len(th_deg)
        self.th = np.asarray(th_deg, float)
        self.a = np.concatenate([d.a for d in self.dfs])                       # generation amplitudes a_nj
        self.om = np.concatenate([np.full(nd, d.om) for d in self.dfs])
        self.ky = np.concatenate([d.ky for d in self.dfs])
        self.fi = np.concatenate([np.full(nd, i) for i in range(len(self.dfs))])
        icol = np.array([int(np.argmin(np.abs(xg - v))) for v in XG])           # integer-grid columns of the DirField grid
        self.icol = icol
        self.C = np.concatenate([d.Aj[:, icol] * np.exp(1j * d.Phi[:, icol]) for d in self.dfs], 0)    # (ncomp, nx) complex
        self.KX = np.concatenate([d.kx[:, icol] for d in self.dfs], 0)
        self.KL = np.concatenate([np.repeat(d.k[None, icol], nd, 0) for d in self.dfs], 0)
        self.h = DF.bed_h(XG, BED)
        self.a_sum = float(a_sum)
        self._nl2 = None

    # ---------------------------------------------------------------- linear
    def eta1(self, cols, y, t):
        A = np.exp(1j * np.outer(np.asarray(y, float), self.ky)) * np.exp(-1j * self.om * (t - self.t_f))[None, :]
        return (A @ self.C[:, cols]).real

    # ---------------------------------------------------------------- local 2nd order (column-wise kernels)
    def prep2(self, cols):
        n = len(self.a)
        I, J = np.triu_indices(n)
        diag = I == J
        Sp = np.zeros((len(I), len(cols)), complex); Sm = np.zeros_like(Sp)
        for q, i in enumerate(cols):
            h = float(self.h[i])
            # local wavenumbers with the kernels' own g (dfg51_screen g = 9.81): km_self takes a finite-difference limit with its kdisp, so a
            # k from g = 9.80665 (DirField) would put a 2e-4 relative mismatch into a 1e-4 difference (found 2026-10-17: K-_mm = 216 at h 8.2 m)
            kl = D51.kdisp(self.om, h)
            c = dict(om=self.om, k=kl, kx=np.sqrt(np.maximum(kl ** 2 - self.ky ** 2, 0.0)), ky=self.ky, h=h)
            Kp, Km = D51.kernels(c, I, J)
            Km = np.where(diag, 0.0, Km)
            Km[diag] = D51.km_self(c, I[diag])
            fac = np.where(diag, 1.0, 2.0) * 0.25
            Ci = self.C[I, i]; Cj = self.C[J, i]
            Sp[:, q] = fac * Kp * Ci * Cj
            Sm[:, q] = fac * Km * Ci * np.conj(Cj)
        Sp[~np.isfinite(Sp)] = 0.0; Sm[~np.isfinite(Sm)] = 0.0
        self._nl2 = dict(cols=np.asarray(cols), S=np.concatenate([Sp, Sm], 0),
                         KY=np.concatenate([self.ky[I] + self.ky[J], self.ky[I] - self.ky[J]]),
                         OM=np.concatenate([self.om[I] + self.om[J], self.om[I] - self.om[J]]), n_pairs=int(len(I)))

    def eta2(self, y, t):
        P = self._nl2
        A = np.exp(1j * np.outer(np.asarray(y, float), P["KY"])) * np.exp(-1j * P["OM"] * (t - self.t_f))[None, :]
        return (A @ P["S"]).real

    def field(self, y, t, second=True):
        cols = self._nl2["cols"]
        e = self.eta1(cols, y, t)
        return e + self.eta2(y, t) if second else e

    # ---------------------------------------------------------------- rays and arrival
    def arrival(self):
        rows = []; num = 0.0; tot = 0.0
        amax = float(self.a.max())
        for n, d in enumerate(self.dfs):
            cgx = DF.cg(d.om, np.maximum(d.h, 0.05))
            for j in range(len(d.a)):
                xs, yy = d.ray_back(j, LAY["x_in"])
                # ray direction cosine along the path (x descending from x_f): cos th = kx / k
                m = (d.x >= LAY["x_in"]) & (d.x <= d.x_f)
                kx = d.kx[j][m][::-1]; kk = d.k[m][::-1]; cgs = cgx[m][::-1]
                if yy[-1] <= LAY["W"] + 1e-9:
                    stop = len(xs) - 1; src = "inlet"; frac = 1.0; xc = None
                else:
                    stop = int(np.argmax(yy >= LAY["sd0"])); src = "side"; xc = float(xs[stop])
                    frac = 1.0 if xc <= LAY["sd_gen"] else (0.0 if xc >= LAY["sd_sw"] else 1.0 - (xc - LAY["sd_gen"]) / (LAY["sd_sw"] - LAY["sd_gen"]))
                dx = np.abs(np.diff(xs[:stop + 1]))
                cos_ = np.maximum(kx[:stop + 1] / kk[:stop + 1], 1e-3)
                tt = float(np.sum(dx / (0.5 * (cos_[1:] + cos_[:-1]) * 0.5 * (cgs[1:stop + 1] + cgs[:stop])))) if stop > 0 else 0.0
                A_f = float(np.interp(d.x_f, d.x, d.Aj[j]))
                num += frac * A_f; tot += A_f
                rows.append(dict(T=self.T[n], th=float(self.th[j]), a=float(d.a[j]), src=src, x_cross_side=xc, frac=frac, travel_s=tt))
        sig = [r for r in rows if r["a"] >= 0.05 * amax]
        t_full = LAY["ramp_s"] + max(r["travel_s"] for r in sig)
        per_T = {("%.2f" % T): max(r["travel_s"] for r in sig if r["T"] == T) for T in self.T}
        return dict(aperture=num / tot, t_full_s=t_full, max_travel_per_T_s=per_T, min_frac=min(r["frac"] for r in rows),
                    n_side=sum(1 for r in rows if r["src"] == "side"), n_inlet=sum(1 for r in rows if r["src"] == "inlet"),
                    rule="ray traced back from the focus through the refracting bed (g50_dirfield.DirField.ray_back); travel = sum dx / (cos th c_g) "
                         "from the inlet band end x 100 m or the side band inner edge y 95 m; t_full = ramp 14 s + max over a >= 5 % [computed]")


def slim(m, kp):
    keys = ["Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "Lx50", "A50"]
    o = {k: (round(float(m[k]), 4) if isinstance(m.get(k), (float, int)) and not isinstance(m.get(k), bool) and np.isfinite(m[k]) else m.get(k))
         for k in keys if k in m}
    if "W50" in m:
        miss, per = EM.score_vs_target(m)
        o["miss"] = round(miss, 3)
        o["miss_per"] = {k: (round(v, 3) if v is not None else None) for k, v in per.items()}
        o["W50_m"] = round(m["W50"] * m["Hc"], 2)
    o["kpHc"] = round(kp * m["Hc"], 4)
    return o


def masked_rows(e):
    b = e.copy()
    b[YROWS > YMAX + 1e-9, :] = np.nan
    return b


def metrics(sea, e, xs, xwin):
    meta = dict(z0=0.5, dz=1.0, x0=float(xs[0]), dx=1.0)
    return EM.hf_metrics(masked_rows(e), meta, 0.0, xwin=xwin)


def n1_iso(e_half, xs, m, xr=(110.0, 340.0), ymax=90.0, rmax=100.0, rex_Hc=4.0, win=15.0):
    """plan E N1 (x51_ana N1DEF) on the screen field."""
    Hc = float(m["Hc"]); xp = float(m["x_pk"]); yp = abs(float(m["y_pk"]))
    eta = np.concatenate([e_half[::-1], e_half], 0); y = np.concatenate([-YROWS[::-1], YROWS])
    e = np.where(np.isfinite(eta), eta, -99.0)
    hw = int(math.floor(0.5 * win))
    mx = ndi.maximum_filter(e, size=(2 * hw + 1, 2 * hw + 1), mode="constant", cval=-99.0)
    XX, YY = np.meshgrid(xs, y)
    r = np.hypot(XX - xp, YY - yp); rm = np.hypot(XX - xp, YY + yp)
    pk = ((e >= mx - 1e-12) & (e > 0.0) & (XX >= xr[0]) & (XX <= xr[1]) & (np.abs(YY) <= ymax) & (r <= rmax) & (r >= rex_Hc * Hc) & (rm >= rex_Hc * Hc))
    if not pk.any():
        return dict(N1=0.0, at=None)
    i = int(np.argmax(np.where(pk, e, -99.0)))
    return dict(N1=float(e.flat[i] / Hc), at=[float(XX.flat[i]), float(YY.flat[i])], dist_m=float(r.flat[i]))


# ============================================================================================== one sea: track, focus, isolation
def analyse(sea, period, t_lo=-12.0, t_hi=8.0, dt=0.125, second=True, full_instants=None):
    t0 = time.time()
    cols = np.where((XG >= XWIN[0] - 1e-9) & (XG <= XWIN[1] + 1e-9))[0]
    xs = XG[cols]
    if second:
        sea.prep2(cols)
    else:
        sea._nl2 = dict(cols=cols)
    kp = float(DF.kdisp(2 * math.pi / TP, BED["h0"]))
    h = sea.h[cols]
    # centre-row track
    ts = sea.t_f + np.arange(t_lo, t_hi + 1e-9, dt)
    tr = []
    for t in ts:
        e = sea.field(np.array([0.5]), t, second)[0]
        e1 = sea.eta1(cols, np.array([0.5]), t)[0]
        ok = h >= H_MIN_TRACK
        i = int(np.argmax(np.where(ok, e, -99.0)))
        il = int(np.argmax(np.where(ok, e1, -99.0)))
        tr.append(dict(t=float(t), x=float(xs[i]), eta=float(e[i]), eta_lin=float(e1[il]), x_lin=float(xs[il]), h=float(h[i]), ratio=float(e[i] / h[i])))
    # 2D max instant over the window (scan the 2nd-order field every 0.25 s near the centre-row maximum)
    i_best = int(np.argmax([r["eta"] for r in tr]))
    tb = tr[i_best]["t"]
    best = None
    for t in tb + np.arange(-0.75, 0.75 + 1e-9, 0.25):
        e = sea.field(YROWS, t, second)
        m = metrics(sea, e, xs, XWIN)
        if m and "W50" in m and (best is None or m["Hc"] > best[0]["Hc"]):
            best = (m, t, e)
    m2, t2, e2 = best
    foc = slim(m2, kp)
    foc["t"] = t2; foc["t_rel_tf"] = t2 - sea.t_f
    foc["h_at_pk"] = float(DF.bed_h(np.array([m2["x_pk"]]), BED)[0])
    foc["N1"] = n1_iso(EM.median3(masked_rows(e2)), xs, m2)
    # linear at the same instant
    e1 = sea.eta1(cols, YROWS, t2)
    m1 = metrics(sea, e1, xs, XWIN)
    lin = slim(m1, kp) if m1 and "W50" in m1 else None
    # temporal isolation (linear, interior x 110-300 m, |y| <= 90 m) over one period
    xi_cols = np.where((XG >= 110.0) & (XG <= XWIN[1]))[0]
    yi = 0.5 + np.arange(0, 90)
    tsP = t2 + np.arange(-period / 2.0, period / 2.0 - 1e-9, 0.25)
    Hm = []; at = []
    for t in tsP:
        f = sea.eta1(xi_cols, yi, t)
        j = int(np.argmax(f)); Hm.append(float(f.flat[j])); at.append([float(XG[xi_cols][j % len(xi_cols)]), float(yi[j // len(xi_cols)])])
    Hm = np.array(Hm)
    far = np.abs(tsP - t2) >= 3.5 - 1e-9
    H0 = float(Hm[int(np.argmin(np.abs(tsP - t2)))])
    jf = int(np.where(far)[0][np.argmax(Hm[far])])
    Nt = dict(Nt_lin=float(Hm[jf] / H0), at=at[jf], t_rel=float(tsP[jf] - t2))
    # the judged region of DFG-2B excludes the shoaling zone shoreward of x 275 m (h < 7.5 m), where every crest grows [chosen]
    xi2 = np.where((XG >= 110.0) & (XG <= 275.0))[0]
    Hm2 = np.array([float(sea.eta1(xi2, yi, t).max()) for t in tsP])
    Nt["Nt_lin_x275"] = float(Hm2[far].max() / Hm2[int(np.argmin(np.abs(tsP - t2)))])
    # and relative to the converged (linear-focus) crest of the centre track instead of the 2D window maximum
    il = int(np.argmax([r["eta_lin"] for r in tr])); tc = tr[il]["t"]
    tsC = tc + np.arange(-period / 2.0, period / 2.0 - 1e-9, 0.25)
    HmC = np.array([float(sea.eta1(xi2, yi, t).max()) for t in tsC])
    farC = np.abs(tsC - tc) >= 3.5 - 1e-9
    Nt["Nt_lin_x275_conv"] = float(HmC[farC].max() / HmC[int(np.argmin(np.abs(tsC - tc)))])
    # c_in on the line x 110 m (|y| <= 95 m) over one period (linear and with the 2nd-order ratio of the focus)
    c110 = int(np.argmin(np.abs(XG - 110.0)))
    cin = 0.0
    for t in t2 + np.arange(-period / 2.0, period / 2.0 - 1e-9, 0.25):
        cin = max(cin, float(sea.eta1(np.array([c110]), 0.5 + np.arange(0, 95), t).max()))
    # bands (linear, one period)
    xin = np.where((XG >= LAY["wall_taper"]) & (XG <= LAY["x_in"]))[0]; yin = np.arange(0.0, LAY["W"] - LAY["sd_taper"] + 0.5, 2.0)
    xsd = np.where(XG <= LAY["sd_gen"])[0]; ysd = np.arange(LAY["sd0"], LAY["W"] - LAY["sd_taper"] + 0.5, 2.0)
    bi = bs = 0.0
    for t in t2 + np.arange(-period / 2.0, period / 2.0 - 1e-9, 0.5):
        bi = max(bi, float(sea.eta1(xin, yin, t).max())); bs = max(bs, float(sea.eta1(xsd, ysd, t).max()))
    out = dict(label=sea.label, x_f=sea.x_f, t_f=sea.t_f, focus=foc, focus_lin=lin, Nt=Nt, c_in110_lin=cin,
               gain_over_c_in110=float(m2["Hc"] / cin) if cin > 0 else None, a_sum=sea.a_sum, a_max_comp=float(sea.a.max()),
               bands_kp_crest_lin=dict(inlet=kp * bi, side=kp * bs, kp=kp), track=tr, n_pairs=(sea._nl2 or {}).get("n_pairs"),
               cpu_s=round(time.time() - t0, 1))
    out["_e2"] = (e2, xs)
    return out


# ============================================================================================== calibration (X2 0.5 m, DM1A, DF1A)
def x2_sea():
    th, wd = G52.dirset(("hyb", 60.0, 28.0, 85.0, 17))
    return BeachSea([7.0], [1.0], th, wd, G52.A_SUM, 220.25, 42.0, label="X2 (T 7, X2 set, x_f 220.25, t_f 7n)")


def dm_sea(T, label):
    th, wd = DF.components(80.0, 30, "uniform")
    a_sum = 6.331240146143423 if T == 12.0 else 6.5028694292482845
    return BeachSea([T], [1.0], th, wd, a_sum, 220.25, 0.0 + T * (4 if T == 12.0 else 5), label=label)


def track_at_x(track, x_on):
    """the crest of the track passing x_on: the track point with the crest nearest x_on, among the points within 4 m (the largest)."""
    c = [r for r in track if abs(r["x"] - x_on) <= 4.0]
    return max(c, key=lambda r: r["eta"]) if c else None


def calib():
    t0 = time.time()
    J = json.load(open(X2_RUN, encoding="utf8"))
    md = J["median"]
    per = [p for p in J["periods"] if p.get("instant", "scan") == "scan" or "g50" not in str(p.get("instant"))]
    meas = dict(Hc=md["Hc"], x_pk=md["x_pk"], W50=md["W50"], W80=md["W80"], W95=md["W95"], K=md["K"], S2=md["S2"], miss=md["miss"], N1=md["N1"],
                c_in110=md["c_in110"], scan_x=[p["x_scan"] for p in J["periods"]], scan_t_rel=[p["t"] - 7.0 * p["n"] for p in J["periods"]],
                scan_Hc=[p["Hc_scan"] for p in J["periods"]], onsets=J.get("g50_events"))
    s = x2_sea()
    r = analyse(s, 7.0, t_lo=-5.0, t_hi=3.5)
    f = r["focus"]
    cal = dict(X2=dict(measured=meas, screen_focus=f, screen_lin=r["focus_lin"], screen_N1=f["N1"], screen_Nt=r["Nt"], screen_c_in110=r["c_in110_lin"]))
    R_X2 = md["Hc"] / f["Hc"]
    dX = float(np.median(meas["scan_x"])) - f["x_pk"]
    dT = float(np.median(meas["scan_t_rel"])) - f["t_rel_tf"]
    cal["X2"]["R"] = R_X2; cal["X2"]["dX_m"] = dX; cal["X2"]["dT_s"] = dT
    R_lin = md["Hc"] / r["focus_lin"]["Hc"] if r.get("focus_lin") else None
    ap_x2 = s.arrival()["aperture"]
    cal["X2"]["R_lin"] = R_lin; cal["X2"]["aperture"] = ap_x2
    cal["X2"]["W_ratio"] = {k: md[k] / f[k] for k in ("W50", "W80", "W95") if f.get(k)}
    cal["X2"]["note"] = ("R = measured median Hc / screen (WKB + local 2nd order) focal Hc; dX, dT = measured median scan-max x / t (t - 7n) minus the screen's "
                         "[measured / computed]")
    # D19B plunging breakers: screen crest passing the measured onset x -> R_D and the onset ratio gamma = Hc / h_b [measured]
    for nm, T in (("DM1A", 12.0), ("DF1A", 10.0)):
        sd = dm_sea(T, nm)
        rd = analyse(sd, T, t_lo=-T / 2.0, t_hi=T * 1.5, dt=0.125)
        B = D_BREAKERS[nm]
        pt = track_at_x(rd["track"], B["x_on"])
        cal[nm] = dict(measured=B, screen_focus=rd["focus"], screen_at_onset_x=pt,
                       R=(B["Hc"] / pt["eta"]) if pt else None, gamma_meas=B["Hc"] / B["h_b"],
                       gamma_screen=(pt["eta"] / pt["h"]) if pt else None)
    g = [cal[k]["gamma_meas"] for k in ("DM1A", "DF1A")] + [D_BREAKERS["DG1"]["Hc"] / D_BREAKERS["DG1"]["h_b"]]
    # T 7 onsets near the shore (X2 / X1 0.5 m, g50 events: on_eta / local depth) [measured]: a check of gamma at kh ~ 0.6
    t7 = []
    for rp in (X2_RUN, X2_RUN.replace("S51X2_D19B_T7_g60s28_dp0p5", "S51X1_D19B_T7_l60d15_dp0p5")):
        try:
            for ev in json.load(open(rp, encoding="utf8")).get("g50_events") or []:
                hb = float(DF.bed_h(np.array([ev["on_x"]]), BED)[0])
                t7.append(dict(run=os.path.basename(os.path.dirname(os.path.dirname(rp))), x=ev["on_x"], h=hb, eta=ev["on_eta"], ratio=ev["on_eta"] / hb))
        except Exception:
            pass
    cal["T7_shore_onsets"] = t7
    cal["rule"] = dict(R_T7=R_X2, R_lin_T7=R_lin, aperture_X2=ap_x2, dX_m=dX, dT_s=dT, gamma=float(np.mean(g)), gamma_range=[float(min(g)), float(max(g))],
                       gamma_T7_shore=[float(min(q["ratio"] for q in t7)), float(np.median([q["ratio"] for q in t7])), float(max(q["ratio"] for q in t7))] if t7 else None,
                       gamma_src="Hc / h_b at the centre onset of DM1A / DF1A / DG1 (D19B, 0.5 m) [measured]",
                       note="FLIP prediction of a T 7 group on D19B: crest = R_T7 x screen crest, shifted upstream by dX and in time by dT (X2 0.5 m); "
                            "onset where that crest >= gamma x local depth [calibrated, guess for a multi-frequency group]")
    cal["cpu_s"] = round(time.time() - t0, 1)
    return cal


# ============================================================================================== DFG-2B candidates
def dfgb_sea(x_f, t_f, a_sum=None):
    om, wf = G52.freqset(G52.P_S, G52.HARMONICS, "eq")
    th, wd = G52.dirset(("hyb", 60.0, 28.0, 85.0, 17))
    T = [G52.P_S / n for n in G52.HARMONICS]
    return BeachSea(T, wf, th, wd, G52.A_SUM if a_sum is None else a_sum, x_f, t_f, label="DFG-2B x_f %.2f" % x_f)


def flip_predict(res, cal, gamma=None, mode="nl2", aperture=None):
    """the calibrated FLIP crest track and the predicted onset.
    mode 'nl2' (central): FLIP crest = R_T7 x (aperture / aperture_X2) x the 2nd-order screen crest; 'lin' (conservative: FLIP realised the LINEAR
    crest at the X2 focus, Hc / linear 1.01, so the 2nd-order growth may not appear): R_lin_T7 x (aperture / aperture_X2) x the linear crest.
    Both shifted upstream by dX and in time by dT (X2 0.5 m). The converged crest = the linear focus (largest linear centre crest of the track)."""
    C = cal["rule"]
    R = C["R_T7"] if mode == "nl2" else C["R_lin_T7"]
    ap = 1.0 if aperture is None else float(aperture) / float(C["aperture_X2"])
    dX = C["dX_m"]; dT = C["dT_s"]
    gm = C["gamma"] if gamma is None else gamma
    out = []
    for r in res["track"]:
        xF = r["x"] + dX
        hF = float(DF.bed_h(np.array([xF]), BED)[0])
        v = r["eta"] if mode == "nl2" else r["eta_lin"]
        out.append(dict(t=r["t"] + dT, x=xF, Hc=R * ap * v, h=hF, ratio=R * ap * v / hF if hF > 0 else None, t_screen=r["t"], x_screen=r["x"]))
    on = next((p for p in out if p["ratio"] is not None and p["ratio"] >= gm), None)
    pk = max(out, key=lambda p: p["Hc"])
    il = int(np.argmax([r["eta_lin"] for r in res["track"]]))
    conv = out[il]
    edge = bool(pk["x_screen"] >= XWIN[1] - 2.0)
    return dict(track=out, onset=on, peak=pk, converged=conv, peak_at_window_edge=edge, gamma=gm, mode=mode, aperture_factor=ap,
                onset_after_converged_s=(on["t"] - conv["t"]) if on else None, onset_minus_converged_x_m=(on["x"] - conv["x"]) if on else None,
                breaks_at_converged_crest=bool(on is not None and -1.0 <= on["t"] - conv["t"] <= 3.0 and on["x"] - conv["x"] <= 25.0),
                rule="FLIP crest = %.3f x aperture factor %.3f x screen %s centre crest at x %+.1f m, t %+.2f s; onset = first point with crest >= %.3f x h(x); "
                     "'breaks at the converged crest' = onset within -1 .. +3 s and <= 25 m shoreward of the linear focus instant [calibrated, chosen]"
                     % (R, ap, mode, dX, dT, gm))


def onset_metrics(sea, res, pred, cal):
    """e51 metrics on the screen field at the screen instant of the predicted onset's 'max' (largest crest in [on - 3 s, on + 1.5 s],
    x [on_x - 60, on_x + 35]); widths are scale-free so the R scaling does not change them."""
    on = pred["onset"]
    if on is None:
        return None
    cols = sea._nl2["cols"]; xs = XG[cols]
    ts = on["t_screen"] + np.arange(-3.0, 1.5 + 1e-9, 0.25)
    xw = (on["x_screen"] - 60.0, on["x_screen"] + 35.0)
    best = None
    for t in ts:
        e = sea.field(YROWS, t)
        m = metrics(sea, e, xs, xw)
        if m and "W50" in m and (best is None or m["Hc"] > best[0]["Hc"]):
            best = (m, t, e)
    if best is None:
        return None
    m, t, e = best
    kp = float(DF.kdisp(2 * math.pi / TP, BED["h0"]))
    o = slim(m, kp)
    o["t_screen"] = t
    o["N1"] = n1_iso(EM.median3(masked_rows(e)), xs, m)
    Wr = cal["X2"]["W_ratio"]
    cal_m = dict(m)
    for k in ("W50", "W80", "W95"):
        if k in Wr and k in cal_m:
            cal_m[k] = cal_m[k] * Wr[k]
    cal_m["W20"] = m["W20"] * Wr.get("W50", 1.0)
    cal_m["K"] = cal_m["W20"] / cal_m["W80"] if cal_m.get("W80") else m.get("K")
    miss_c, per_c = EM.score_vs_target(cal_m)
    o["X2_width_calibrated"] = dict(W50=cal_m["W50"], W80=cal_m["W80"], W95=cal_m["W95"], K=cal_m["K"], miss=miss_c,
                                    rule="screen widths x the X2 measured / screen width ratios (W50, W80, W95; W20 with the W50 ratio) [calibrated]")
    return o


def iribarren(H_b, T, slope=0.1):
    L0 = G * T * T / (2 * math.pi)
    return slope / math.sqrt(H_b / L0)


def print_expectation(pred, T_eff=7.0):
    """expected print-ruler numbers at the most print-like frame [guess], from the D19B plunging breakers (DM1A T 12, DF1A T 10, DG1 T 12 groove)
    [measured] extrapolated in period to T_eff with the T 12 -> T 10 trend, and the breaker type from the Iribarren number of the onset."""
    on = pred["onset"]
    dm, df = D_BREAKERS["DM1A"], D_BREAKERS["DF1A"]
    per_s = lambda k: (df[k] - dm[k]) / (df["T"] - dm["T"])          # change per second of period (T 12 -> 10)
    ext = {k: dm[k] + per_s(k) * (T_eff - dm["T"]) for k in ("back_best", "w07_best", "lip", "chord", "hood", "s3")}
    out = dict(T_eff=T_eff, linear_period_extrapolation=ext,
               D19B_breakers=D_BREAKERS, print=PRINT_REF)
    if on is not None:
        Hb = on["Hc"] * D_BREAKERS["DM1A"]["H_front"] / D_BREAKERS["DM1A"]["Hc"]      # crest-to-front-trough from the D ratio H_front / Hc [measured ratio]
        xi = iribarren(Hb, T_eff); xi_dm = iribarren(dm["H_front"], dm["T"]); xi_df = iribarren(df["H_front"], df["T"])
        out.update(H_front_est=Hb, iribarren_b=xi, iribarren_DM1A=xi_dm, iribarren_DF1A=xi_df,
                   breaker_type=("plunging" if xi >= 0.4 else ("spilling / plunging boundary" if xi >= 0.3 else "spilling")),
                   iribarren_note="xi_b = slope / sqrt(H_front / L0), Battjes 1974: spilling < 0.4 < plunging (with H_b); the D19B plunging breakers "
                                  "had xi_b 0.47 (DM1A) / 0.42 (DF1A) [computed from measured H_front]")
    # the central expectation [guess]: half of the linear period extrapolation (the trend need not continue to T 7), bounded by the D runs
    cen = {}
    for k in ("back_best", "w07_best", "lip", "chord", "hood"):
        a = dm[k]; b = ext[k]
        lo, hi = sorted([df[k], b])
        cen[k] = dict(central=0.5 * (df[k] + b), range=[lo, hi])
    if on is not None and out.get("iribarren_b", 1.0) < 0.4:
        cen["lip"] = dict(central=0.25, range=[0.0, 0.4], note="Iribarren below 0.4: spilling possible (lip 0) [guess]")
    out["expected"] = cen
    out["expected_tag"] = "[guess] (5 measured breakers of 3 runs, one period trend, no T 7 plunging breaker measured on D19B)"
    return out


def run_candidate(x_f, cal, t_f=None, label=None):
    t0 = time.time()
    s0 = dfgb_sea(x_f, 0.0)
    arr = s0.arrival()
    t_f1 = float(math.ceil(arr["t_full_s"] + 3.9)) if t_f is None else float(t_f)
    s = dfgb_sea(x_f, t_f1)
    r = analyse(s, G52.P_S)
    ap = arr["aperture"]
    pred = flip_predict(r, cal, aperture=ap)
    pred_lo = flip_predict(r, cal, gamma=cal["rule"]["gamma_range"][1], aperture=ap)
    pred_hi = flip_predict(r, cal, gamma=cal["rule"]["gamma_range"][0], aperture=ap)
    pred_lin = flip_predict(r, cal, mode="lin", aperture=ap)
    om = onset_metrics(s, r, pred, cal)
    pe = print_expectation(pred)
    e2, xs = r.pop("_e2")
    res = dict(x_f=x_f, h_f=float(DF.bed_h(np.array([x_f]), BED)[0]), t_f1=t_f1, foci=[t_f1, t_f1 + 28.0, t_f1 + 56.0], arrival=arr, screen=r,
               flip_pred=dict(onset=pred["onset"], peak=pred["peak"], converged=pred["converged"], gamma=pred["gamma"],
                              breaks_at_converged_crest=pred["breaks_at_converged_crest"], onset_after_converged_s=pred["onset_after_converged_s"],
                              onset_minus_converged_x_m=pred["onset_minus_converged_x_m"], peak_at_window_edge=pred["peak_at_window_edge"],
                              aperture_factor=pred["aperture_factor"], rule=pred["rule"], onset_gamma_hi=pred_lo["onset"], onset_gamma_lo=pred_hi["onset"],
                              linear_mode=dict(onset=pred_lin["onset"], converged=pred_lin["converged"], peak=pred_lin["peak"],
                                               breaks_at_converged_crest=pred_lin["breaks_at_converged_crest"], rule=pred_lin["rule"])),
               onset_metrics=om, print_expectation=pe, cpu_s=round(time.time() - t0, 1), label=label or s.label)
    res["screen"]["track"] = [dict(t=round(q["t"], 3), x=q["x"], eta=round(q["eta"], 3), h=round(q["h"], 2)) for q in r["track"][::2]]
    return res


def jdump(o, p):
    def cl(v):
        if isinstance(v, dict):
            return {str(k): cl(w) for k, w in v.items()}
        if isinstance(v, (list, tuple)):
            return [cl(w) for w in v]
        if isinstance(v, (np.floating, float)):
            return None if not np.isfinite(v) else round(float(v), 6)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, np.ndarray):
            return cl(v.tolist())
        return v
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf8") as fh:
        json.dump(cl(o), fh, ensure_ascii=False, indent=1)


def onset_short(o):
    return dict(x=o["x"], t=round(o["t"], 2), Hc=round(o["Hc"], 2), h_b=round(o["h"], 2)) if o else None


def short(res):
    f = res["screen"]["focus"]; p = res["flip_pred"]; on = p["onset"]; om = res["onset_metrics"] or {}
    return dict(x_f=res["x_f"], h_f=res["h_f"], t_f1=res["t_f1"], aperture=round(res["arrival"]["aperture"], 3),
                screen_Hc=f["Hc"], screen_x_pk=f["x_pk"], screen_h_pk=round(f["h_at_pk"], 2), screen_miss=f.get("miss"), screen_W50=f.get("W50"),
                screen_N1=round(f["N1"]["N1"], 3), Nt=round(res["screen"]["Nt"]["Nt_lin"], 3), gain110=round(res["screen"]["gain_over_c_in110"] or 0, 2),
                bands=res["screen"]["bands_kp_crest_lin"],
                conv_FLIP=dict(x=p["converged"]["x"], t=round(p["converged"]["t"], 2), Hc=round(p["converged"]["Hc"], 2), h=round(p["converged"]["h"], 2),
                               ratio=round(p["converged"]["ratio"], 3)),
                onset_FLIP=(dict(x=on["x"], t=round(on["t"], 2), Hc=round(on["Hc"], 2), h_b=round(on["h"], 2), dt_after_conv=round(p["onset_after_converged_s"], 2))
                            if on else None),
                onset_FLIP_lin=onset_short(p["linear_mode"]["onset"]),
                conv_FLIP_lin_Hc=round(p["linear_mode"]["converged"]["Hc"], 2),
                breaks_at_converged=p["breaks_at_converged_crest"], breaks_at_converged_lin=p["linear_mode"]["breaks_at_converged_crest"],
                onset_miss=om.get("miss"), onset_miss_X2cal=(om.get("X2_width_calibrated") or {}).get("miss"),
                iribarren=round(res["print_expectation"].get("iribarren_b") or 0, 3), cpu_s=res["cpu_s"])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if not a:
        print(__doc__); sys.exit(1)
    calp = OUT + "/calib_52b.json"
    if a[0] in ("calib", "all"):
        cal = calib()
        jdump(cal, calp)
        print("calib", json.dumps(dict(rule=cal["rule"], X2=dict(R=cal["X2"]["R"], dX=cal["X2"]["dX_m"], dT=cal["X2"]["dT_s"], W_ratio=cal["X2"]["W_ratio"],
                                                                 screen_Hc=cal["X2"]["screen_focus"]["Hc"], screen_x=cal["X2"]["screen_focus"]["x_pk"],
                                                                 screen_miss=cal["X2"]["screen_focus"].get("miss")),
                                       DM1A=dict(R=cal["DM1A"]["R"], gs=cal["DM1A"]["gamma_screen"]), DF1A=dict(R=cal["DF1A"]["R"], gs=cal["DF1A"]["gamma_screen"]),
                                       cpu=cal["cpu_s"]), default=float), flush=True)
    if a[0] in ("run", "all"):
        cal = json.load(open(calp, encoding="utf8"))
        xs = [float(v) for v in a[1:]] if (a[0] == "run" and len(a) > 1) else [210.25, 220.25, 230.25, 240.25, 250.25, 260.25]
        allr = {}
        for x_f in xs:
            r = run_candidate(x_f, cal)
            allr["xf%.2f" % x_f] = r
            jdump(r, OUT + "/dfg52b_xf%s.json" % ("%.2f" % x_f).replace(".", "p"))
            print("cand", json.dumps(short(r), default=float), flush=True)
        summ = {k: short(v) for k, v in allr.items()}
        p = OUT + "/dfg52b_screen_summary.json"
        old = json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}
        old.update(summ)
        jdump(old, p)


if __name__ == "__main__":
    main()
