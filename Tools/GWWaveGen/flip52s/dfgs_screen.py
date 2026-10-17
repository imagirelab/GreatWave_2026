# -*- coding: utf-8 -*-
"""FLIP52S 'DFG-S' design screen: DFG-2's sea and tank (flat 20 m, P 28 s group of T 9.33 / 7 / 5.6 s, the plan E X2 directions,
a_sum = DM1A's 6.331 m) plus a LATERALLY UNIFORM steep step (slope 1:s from the toe x_t at 20 m up to a shelf of depth h_top that runs
to the exit sponge), so that the converged crest meets near-limiting depth on the step face while it is still converged.
(py -3.10 -B; numpy, scipy).  2026-10-18 written new (Claude, DFG-S design task). Writes only Unity/Build/FLIP52S/screens/.

Imports READ ONLY (no file of a running / queued pipeline is edited): flip50/g50_dirfield (WKB DirField with the 'shelf' bed, kdisp, cg),
flip51/dfg51_screen (Sharma-Dean kernels), flip51/e51_metrics (frozen ruler: hf_metrics, score_vs_target, median3),
flip52/g52_common (dirset, freqset, A_SUM, P_S, HARMONICS = the DFG-2 sea).

Model (per component n (frequency), j (direction); bed depends on x only, so k_y is conserved = Snell refraction, WKB shoaling):
    eta1 = sum f_nj A_nj(x) cos(Phi_nj(x) + k_y y - w_n (t - t_f)),  A = a Ks Kr  (g50_dirfield.DirField)
    eta2 = column-wise LOCAL Sharma-Dean 2nd order (locally flat kernels at h(x); an approximation on a 1:3-1:5 face) [computed]
    f_nj = 1 (generated) / 0 (its ray to the focus starts in the absorbing part of the side band) / linear fade in the blend [computed]
  phase modes  'design' : the table is re-phased by WKB over the step: every component has phase 0 at (x_f, 0) at t_f (as DFG-2B on D19B)
               'dfg2'   : DFG-2's table unchanged (flat-bed phases, focus (150, 0) at t 44 s); over the step the phases follow WKB
  side band    'gen180' : DFG-2 band (sd_gen 180, sd_sw 210): it would generate over the step -> needs a WKB target there
               'flat'   : generate only on the flat bed (sd_gen = x_t - 10 m, sd_sw = x_t + 15 m), absorbing over the face and shelf
FLIP calibration on DFG-2 itself (same sea, same tank, 0.5 m) [measured]: R = measured median Hc / screen focal Hc (2nd order and linear),
dX / dT = measured summit x / t minus the screen's, W ratios = measured / screen widths. Applied unchanged on the step [guess: transfer].
Onset: first centre-track point with R * crest >= gamma * h(x); gamma 0.81 = D19B 1:10 onsets DM1A / DF1A / DG1 [measured], 0.77-0.95 band
(the upper part for a steeper face, Weggel 1972 trend [literature]).
usage:  py -3.10 -B dfgs_screen.py calib | run NAME [NAME ...] | all | list
Tags: [measured] [computed] [literature] [guess] [chosen].
"""
import os, sys, json, math, time

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")                     # hython (X2B') shares the machine: keep numpy modest
REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in (REPO + "/Tools/GWWaveGen/flip50", REPO + "/Tools/GWWaveGen/flip51", REPO + "/Tools/GWWaveGen/flip52"):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                                    # noqa: E402
from scipy import ndimage as ndi                      # noqa: E402
import g50_dirfield as DF                             # noqa: E402  read only
import dfg51_screen as D51                            # noqa: E402  read only
import e51_metrics as EM                              # noqa: E402  read only (frozen ruler)
import g52_common as G52                              # noqa: E402  read only

OUT = REPO + "/Unity/Build/FLIP52S/screens"
G = DF.G
H0 = 20.0
# DFG-2 tank (Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/cfg.json parms) [measured from the cfg]
LAY = dict(W=100.0, sd0=70.0, x_in=50.0, sd_gen=180.0, sd_sw=210.0, ramp_s=14.0, wall_taper=12.5, sd_taper=7.5, xa0=210.0, Lx=290.0)
XG = np.arange(0.0, 290.0 + 1e-9, 1.0)
XWIN = (80.0, 205.0)                 # track / metrics window (records crop x 90-190 m; exit sponge from 210 m)
YROWS = 0.5 + np.arange(0, 100)
YMAX = 65.0                          # DFG-2 judge metrics |y| <= 65 m
TP = 7.0
KP = float(DF.kdisp(2 * math.pi / TP, H0))
DFG2_TF = 44.0
DFG2_XF = 150.0
DFG2_RUN = REPO + "/Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/g52/judge_DFG.json"
DFG2_PV = REPO + "/Unity/Build/FLIP53/pv53/DFG2_flat20_P28_dp0p5/pv53_DFG2_flat20_P28_dp0p5.json"
PRINT_REF = dict(back_deg_07_09=31.3, back_band=[29.0, 38.0], width07=1.32, width07_band=[1.02, 1.42], lip=0.35, chord_deg=64.3, hood=0.186)
# analogues for the breaker after onset (centre-section print ruler, best instant) [measured]
ANALOGUES = {
    "DM1A (3D fan T 12, 1:10 D19B, 0.5 m)": dict(s3=0.65, back=13.8, w07=2.54, lip=0.46, chord=152.0, hood=0.343, Hc_on=7.85, h_b=9.38, xi_b=0.47),
    "DF1A (3D fan T 10, 1:10 D19B, 0.5 m)": dict(s3=0.56, back=16.1, w07=1.90, lip=0.40, chord=142.0, hood=0.266, Hc_on=7.26, h_b=9.38, xi_b=0.42),
    "FLIP47 S5 (2D, 1:7 ledge to 0.2 h0, GN a0/h0 0.6, 0.25 m)": dict(s3=1.00, chord=68.0, foot=0.59),
    "FLIP47 S2 (2D, 1:10 to 0.1 h0 flat, 0.25 m)": dict(s3=0.49, chord=91.0, foot=0.35, hood=0.154, lip=0.35, back=8.0, w07=3.1),
    "campaign B S2 (2D, 1:10 17->13 m, 1:3 to a 1.7 m shelf, T 12 H 7.5, un-converged)": dict(s3=0.935, Hc_on=2.89, h_b=1.70, back=4.3, w07=4.03,
                                                                                             lip=0.32, chord=97.5, hood=0.145),
    "campaign B S0 (2D, DA3 ridge axis, T 12 H 7.5)": dict(s3=0.705, Hc_on=5.98, h_b=8.08, back=13.5, w07=2.56, lip=0.37, chord=97.6, hood=0.141),
    "DFG-2 (flat, no break) best print instant": dict(s3=2.484, back=10.9, w07=4.95, lip=0.0, chord=12.7, hood=0.0, foot=4.5),
}
GAMMA = dict(central=0.84, lo=0.77, hi=0.95, D19B_mean=0.814,
             src="Hc / h_b at the centre onset: DM1A 0.837, DF1A 0.774, DG1 0.832 on 1:10 [measured]; a steeper face raises the breaking index "
                 "(Weggel 1972: H_b/h_b 0.75 -> 0.83 from m 0.1 to 0.25 at H_b/gT^2 0.017) [literature] -> band 0.77-0.95, central 0.84 [chosen]")


def kdisp(om, h):
    return DF.kdisp(om, h)


def bed_spec(x_toe=None, s=4.0, h_top=7.5):
    if x_toe is None:
        return dict(h0=H0, x_toe=1e9, s=10.0, kind="beach")
    return dict(h0=H0, x_toe=float(x_toe), s=float(s), kind="shelf", h_s=float(h_top))


def x_edge(bed):
    if bed["kind"] != "shelf":
        return None
    return bed["x_toe"] + bed["s"] * (H0 - bed["h_s"])


def side_lay(bed, side):
    L = dict(LAY)
    if side == "flat" and bed["kind"] == "shelf":
        L["sd_gen"] = bed["x_toe"] - 10.0
        L["sd_sw"] = bed["x_toe"] + 15.0
    return L


# ============================================================================================== the sea over the step
class StepSea:
    def __init__(self, bed, x_f, t_f, mode="design", side="gen180", label=""):
        self.bed = dict(bed); self.mode = mode; self.side = side; self.label = label
        self.lay = side_lay(bed, side)
        self.x_f = float(x_f); self.t_f = float(t_f)
        om, wf = G52.freqset(G52.P_S, G52.HARMONICS, "eq")
        th, wd = G52.dirset(("hyb", 60.0, 28.0, 85.0, 17))
        self.T = [G52.P_S / n for n in G52.HARMONICS]
        self.th = np.asarray(th, float)
        xg = np.union1d(XG, [self.x_f, DFG2_XF])
        self.xg = xg
        self.dfs = [DF.DirField(T, th, wd, G52.A_SUM * w, xg, bed, self.x_f) for T, w in zip(self.T, wf)]
        if mode == "dfg2":
            # DFG-2's table unchanged: flat-bed phases referenced to (150, 0, 44 s); identical upstream of the toe, WKB over the step
            flat = [DF.DirField(T, th, wd, G52.A_SUM * w, xg, bed_spec(None), DFG2_XF) for T, w in zip(self.T, wf)]
            xr = min(bed.get("x_toe", 1e9), LAY["x_in"]) if bed["kind"] == "shelf" else LAY["x_in"]
            ir = int(np.argmin(np.abs(xg - xr)))
            for d, f in zip(self.dfs, flat):
                d.Phi = d.Phi - (d.Phi[:, ir] - f.Phi[:, ir])[:, None]
            self.t_f = DFG2_TF
        nd = len(th)
        self.a = np.concatenate([d.a for d in self.dfs])
        self.om = np.concatenate([np.full(nd, d.om) for d in self.dfs])
        self.ky = np.concatenate([d.ky for d in self.dfs])
        self.fi = np.concatenate([np.full(nd, i) for i in range(len(self.dfs))])
        self.thc = np.concatenate([self.th for _ in self.dfs])
        icol = np.array([int(np.argmin(np.abs(xg - v))) for v in XG])
        self.icol = icol
        self.C0 = np.concatenate([d.Aj[:, icol] * np.exp(1j * d.Phi[:, icol]) for d in self.dfs], 0)
        self.h = DF.bed_h(XG, bed)
        self.arr = self.arrival()
        self.frac = np.array([r["frac"] for r in self.arr["rows"]])
        self.C = self.C0 * self.frac[:, None]
        self._nl2 = None

    # ---------------------------------------------------------------- rays: which components reach the focus from a generating band
    def arrival(self, x_focus=None):
        L = self.lay
        rows = []; num = 0.0; tot = 0.0
        amax = float(self.a.max())
        xF = self.x_f if x_focus is None else float(x_focus)
        for n, d in enumerate(self.dfs):
            cgx = DF.cg(d.om, np.maximum(d.h, 0.05))
            for j in range(len(d.a)):
                m = (d.x >= L["x_in"]) & (d.x <= xF)
                xs = d.x[m][::-1]
                kx = d.kx[j][m][::-1]; kk = d.k[m][::-1]; cgs = cgx[m][::-1]
                tn = d.ky[j] / np.maximum(kx, 1e-9)
                yy = np.abs(np.concatenate([[0.0], np.cumsum(0.5 * (tn[1:] + tn[:-1]) * np.abs(np.diff(xs)))]))
                if yy[-1] <= L["sd0"] + 1e-9:
                    stop = len(xs) - 1; src = "inlet"; frac = 1.0; xc = None
                else:
                    stop = int(np.argmax(yy >= L["sd0"])); src = "side"; xc = float(xs[stop])
                    frac = 1.0 if xc <= L["sd_gen"] else (0.0 if xc >= L["sd_sw"] else 1.0 - (xc - L["sd_gen"]) / (L["sd_sw"] - L["sd_gen"]))
                dx = np.abs(np.diff(xs[:stop + 1]))
                cos_ = np.maximum(kx[:stop + 1] / kk[:stop + 1], 1e-3)
                tt = float(np.sum(dx / (0.5 * (cos_[1:] + cos_[:-1]) * 0.5 * (cgs[1:stop + 1] + cgs[:stop])))) if stop > 0 else 0.0
                A_f = float(np.interp(xF, d.x, d.Aj[j]))
                num += frac * A_f; tot += A_f
                hx = float(DF.bed_h(np.array([xc]), self.bed)[0]) if xc is not None else None
                rows.append(dict(T=self.T[n], th=float(self.th[j]), a=float(d.a[j]), src=src, x_cross_side=xc, h_at_cross=hx, frac=frac, travel_s=tt))
        sig = [r for r in rows if r["a"] >= 0.05 * amax and r["frac"] > 0]
        t_full = LAY["ramp_s"] + max(r["travel_s"] for r in sig)
        over_step = [r for r in rows if r["src"] == "side" and r["frac"] > 0 and self.bed["kind"] == "shelf" and r["x_cross_side"] > self.bed["x_toe"]]
        A_over = sum(np.interp(xF, self.dfs[self.T.index(r["T"])].x, self.dfs[self.T.index(r["T"])].Aj[list(self.th).index(r["th"])])
                     for r in over_step)
        return dict(aperture=num / tot, t_full_s=t_full, rows=rows, n_side=sum(1 for r in rows if r["src"] == "side"),
                    frac_of_focal_sum_from_side_over_step=float(A_over / tot) if tot > 0 else 0.0,
                    rule="ray traced back from the focus (Snell over the step) to the inlet band end x 50 m or the side band inner edge y 70 m; "
                         "frac 1 if it crosses y 70 m at x <= sd_gen, 0 beyond sd_sw, linear between; travel = sum dx / (cos th c_g) [computed]")

    # ---------------------------------------------------------------- fields
    def eta1(self, cols, y, t):
        A = np.exp(1j * np.outer(np.asarray(y, float), self.ky)) * np.exp(-1j * self.om * (t - self.t_f))[None, :]
        return (A @ self.C[:, cols]).real

    def prep2(self, cols):
        n = len(self.a)
        I, J = np.triu_indices(n)
        diag = I == J
        Sp = np.zeros((len(I), len(cols)), complex); Sm = np.zeros_like(Sp)
        for q, i in enumerate(cols):
            h = float(self.h[i])
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
                         OM=np.concatenate([self.om[I] + self.om[J], self.om[I] - self.om[J]]))

    def eta2(self, y, t):
        P = self._nl2
        A = np.exp(1j * np.outer(np.asarray(y, float), P["KY"])) * np.exp(-1j * P["OM"] * (t - self.t_f))[None, :]
        return (A @ P["S"]).real

    def field(self, y, t, second=True):
        cols = self._nl2["cols"]
        e = self.eta1(cols, y, t)
        return e + self.eta2(y, t) if second else e


# ============================================================================================== measures
def masked(e):
    b = e.copy()
    b[YROWS > YMAX + 1e-9, :] = np.nan
    return b


def metrics(e, xs, xwin):
    meta = dict(z0=0.5, dz=1.0, x0=float(xs[0]), dx=1.0)
    return EM.hf_metrics(masked(e), meta, 0.0, xwin=xwin)


def slim(m):
    keys = ["Hc", "x_pk", "y_pk", "W20", "W50", "W80", "W95", "K", "S1", "S2", "Lx50", "A50"]
    o = {k: (round(float(m[k]), 4) if isinstance(m.get(k), (float, int)) and not isinstance(m.get(k), bool) and np.isfinite(m[k]) else m.get(k))
         for k in keys if k in m}
    if "W50" in m:
        miss, per = EM.score_vs_target(m)
        o["miss"] = round(miss, 3)
        o["miss_per"] = {k: (round(v, 3) if v is not None else None) for k, v in per.items()}
        o["W50_m"] = round(m["W50"] * m["Hc"], 2)
    o["kpHc"] = round(KP * m["Hc"], 4)
    return o


def centre_shape(row, xs, i_pk):
    """centre-row (y 0.5 m) shape around the crest at index i_pk: width at 0.7 eta_c (/eta_c), back angle between 0.7 and 0.9 eta_c
    (rear face, deg), face chord 0.1-0.5 eta_c (front, deg), front foot 0.1 eta_c distance (/eta_c). Pre-breaking surface only."""
    ec = float(row[i_pk])
    if ec <= 0.3:
        return None

    def cross(level, direction):
        i = i_pk
        while 0 < i < len(row) - 1 and row[i] >= level:
            i += direction
        if row[i] >= level:
            return None
        a, b = row[i], row[i - direction]
        f = (level - a) / (b - a) if b != a else 0.0
        return float(xs[i] + f * (xs[i - direction] - xs[i]))

    out = dict(eta_c=ec, x_c=float(xs[i_pk]))
    f07 = cross(0.7 * ec, +1); b07 = cross(0.7 * ec, -1); b09 = cross(0.9 * ec, -1)
    f01 = cross(0.1 * ec, +1); f05 = cross(0.5 * ec, +1)
    if f07 is not None and b07 is not None:
        out["w07"] = (f07 - b07) / ec
    if b07 is not None and b09 is not None and b09 > b07:
        out["back_deg"] = math.degrees(math.atan2(0.2 * ec, b09 - b07))
    if f01 is not None and f05 is not None and f01 > f05:
        out["chord_deg"] = math.degrees(math.atan2(0.4 * ec, f01 - f05))
    if f01 is not None:
        out["foot"] = (f01 - float(xs[i_pk])) / ec
    return out


def n1_iso(e_half, xs, m, rex_Hc=4.0, win=15.0):
    Hc = float(m["Hc"]); xp = float(m["x_pk"]); yp = abs(float(m["y_pk"]))
    eta = np.concatenate([e_half[::-1], e_half], 0); y = np.concatenate([-YROWS[::-1], YROWS])
    e = np.where(np.isfinite(eta), eta, -99.0)
    hw = int(math.floor(0.5 * win))
    mx = ndi.maximum_filter(e, size=(2 * hw + 1, 2 * hw + 1), mode="constant", cval=-99.0)
    XX, YY = np.meshgrid(xs, y)
    r = np.hypot(XX - xp, YY - yp); rm = np.hypot(XX - xp, YY + yp)
    pk = (e >= mx - 1e-12) & (e > 0.0) & (np.abs(YY) <= YMAX) & (r >= rex_Hc * Hc) & (rm >= rex_Hc * Hc)
    if not pk.any():
        return dict(N1=0.0, at=None)
    i = int(np.argmax(np.where(pk, e, -99.0)))
    return dict(N1=float(e.flat[i] / Hc), at=[float(XX.flat[i]), float(YY.flat[i])])


def reflection(bed, T_list):
    """first-order (Born) reflection of a normally incident wave from the face: R = |int 1/2 d ln c / dx exp(2 i int k dx) dx| [computed;
    an estimate, oblique incidence and breaking lower it]."""
    if bed["kind"] != "shelf":
        return {("%.2f" % T): 0.0 for T in T_list}
    x = np.arange(bed["x_toe"] - 5.0, x_edge(bed) + 5.0 + 1e-9, 0.25)
    h = DF.bed_h(x, bed)
    out = {}
    for T in T_list:
        om = 2 * math.pi / T
        k = DF.kdisp(om, h); c = om / k
        ph = np.concatenate([[0.0], np.cumsum(0.5 * (k[1:] + k[:-1]) * np.diff(x))])
        dl = np.gradient(np.log(c), x)
        out["%.2f" % T] = float(abs(np.trapezoid(0.5 * dl * np.exp(2j * ph), x)))
    return out


# ============================================================================================== one sea
def analyse(sea, t_lo=-8.0, t_hi=5.0, dt=0.125):
    t0 = time.time()
    cols = np.where((XG >= XWIN[0] - 1e-9) & (XG <= XWIN[1] + 1e-9))[0]
    xs = XG[cols]
    sea.prep2(cols)
    h = sea.h[cols]
    ts = sea.t_f + np.arange(t_lo, t_hi + 1e-9, dt)
    tr = []
    for t in ts:
        e = sea.field(np.array([0.5]), t)[0]
        e1 = sea.eta1(cols, np.array([0.5]), t)[0]
        i = int(np.argmax(e)); il = int(np.argmax(e1))
        tr.append(dict(t=float(t), x=float(xs[i]), eta=float(e[i]), eta_lin=float(e1[il]), x_lin=float(xs[il]), h=float(h[i]),
                       ratio=float(e[i] / h[i]), shape=centre_shape(e, xs, i)))
    i_best = int(np.argmax([r["eta"] for r in tr]))
    tb = tr[i_best]["t"]
    best = None
    for t in tb + np.arange(-0.5, 0.5 + 1e-9, 0.125):
        e = sea.field(YROWS, t)
        m = metrics(e, xs, XWIN)
        if m and "W50" in m and (best is None or m["Hc"] > best[0]["Hc"]):
            best = (m, t, e)
    m2, t2, e2 = best
    foc = slim(m2)
    foc["t"] = t2; foc["t_rel_tf"] = t2 - sea.t_f
    foc["h_at_pk"] = float(DF.bed_h(np.array([m2["x_pk"]]), sea.bed)[0])
    foc["N1"] = n1_iso(EM.median3(masked(e2)), xs, m2)
    i_pk = int(np.argmin(np.abs(xs - m2["x_pk"])))
    foc["centre_shape"] = centre_shape(e2[0], xs, int(np.argmax(e2[0])))
    e1 = sea.eta1(cols, YROWS, t2)
    m1 = metrics(e1, xs, XWIN)
    lin = slim(m1) if m1 and "W50" in m1 else None
    # temporal isolation Nt (linear, interior x 90-200 m, |y| <= 65 m) over one period around the linear converged instant
    il = int(np.argmax([r["eta_lin"] for r in tr])); tc = tr[il]["t"]
    xi = np.where((XG >= 90.0) & (XG <= 200.0))[0]; yi = 0.5 + np.arange(0, 65)
    tsC = tc + np.arange(-14.0, 14.0 - 1e-9, 0.25)
    HmC = np.array([float(sea.eta1(xi, yi, t).max()) for t in tsC])
    farC = np.abs(tsC - tc) >= 3.5 - 1e-9
    Nt = float(HmC[farC].max() / HmC[int(np.argmin(np.abs(tsC - tc)))])
    t_Nt = float(tsC[farC][int(np.argmax(HmC[farC]))] - tc)
    far5 = np.abs(tsC - tc) >= 5.0 - 1e-9
    Nt5 = float(HmC[far5].max() / HmC[int(np.argmin(np.abs(tsC - tc)))])
    # the second-largest crest's own centre-row depth ratio (does the neighbour crest also break?) - linear, x 90-200 m
    # c_in on x 60 m (|y| <= 65 m) over one period (DFG-2 E3 line)
    c60 = int(np.argmin(np.abs(XG - 60.0)))
    cin = max(float(sea.eta1(np.array([c60]), 0.5 + np.arange(0, 65), t).max()) for t in tc + np.arange(-14.0, 14.0 - 1e-9, 0.25))
    # bands (linear, one period): inlet x 12.5-50 m, all y <= 92.5; generating side band y >= 70 m, x <= sd_gen
    L = sea.lay
    xin = np.where((XG >= LAY["wall_taper"]) & (XG <= LAY["x_in"]))[0]; yin = np.arange(0.5, LAY["W"] - LAY["sd_taper"] + 0.5, 2.0)
    xsd = np.where(XG <= L["sd_gen"])[0]; ysd = np.arange(LAY["sd0"], LAY["W"] - 0.4, 2.0)
    bi = bs = 0.0
    for t in tc + np.arange(-14.0, 14.0 - 1e-9, 0.5):
        bi = max(bi, float(sea.eta1(xin, yin, t).max())); bs = max(bs, float(sea.eta1(xsd, ysd, t).max()))
    out = dict(label=sea.label, x_f=sea.x_f, t_f=sea.t_f, focus=foc, focus_lin=lin, Nt_lin=Nt, Nt_t_rel=t_Nt, Nt5_lin=Nt5, conv_lin_t=tc, c_in60_lin=cin,
               gain_over_c_in60=float(m2["Hc"] / cin) if cin > 0 else None, bands_kp_crest_lin=dict(inlet=KP * bi, side=KP * bs),
               track=tr, cpu_s=round(time.time() - t0, 1))
    out["_e2"] = (e2, xs)
    return out


# ============================================================================================== calibration on DFG-2 (flat, measured)
def calib():
    t0 = time.time()
    J = json.load(open(DFG2_RUN, encoding="utf8"))
    md = J["median"]
    PV = json.load(open(DFG2_PV, encoding="utf8"))
    s = StepSea(bed_spec(None), DFG2_XF, DFG2_TF, mode="design", side="gen180", label="DFG-2 flat (calibration)")
    r = analyse(s)
    f = r["focus"]
    summit_t = J["gates"]["G3P"]["summit_t"]
    t_meas = float(np.median([t - 28.0 * i for i, t in enumerate(summit_t)])) - DFG2_TF
    cal = dict(measured=dict(Hc=md["Hc"], x_pk=md["x_pk"], W50=md["W50"], W80=md["W80"], W95=md["W95"], K=md["K"], S2=md["S2"], miss=md["miss"],
                             N1=md["N1"], Nt=md["Nt"], c_in60=md["c_in60"], t_rel=t_meas, back_deg_e51=md.get("back_deg"),
                             pv53_best=[p["best"] for p in PV["periods"]]),
               screen=dict(focus=f, focus_lin=r["focus_lin"], Nt_lin=r["Nt_lin"], c_in60_lin=r["c_in60_lin"], bands=r["bands_kp_crest_lin"],
                           aperture=s.arr["aperture"], t_full=s.arr["t_full_s"]))
    R = md["Hc"] / f["Hc"]; R_lin = md["Hc"] / r["focus_lin"]["Hc"]
    dX = md["x_pk"] - f["x_pk"]; dT = t_meas - f["t_rel_tf"]
    Wr = {k: md[k] / f[k] for k in ("W50", "W80", "W95") if f.get(k)}
    Wr["W20"] = Wr["W50"]
    # measured crest track (centre row, from the hf records, see a1 in the DFG-S design notes): Hc >= 5 m from x 125 to 160 m,
    # apparent speed 15 m/s (crossing pattern c / cos th) [measured]
    cal["rule"] = dict(R_nl2=R, R_lin=R_lin, dX_m=dX, dT_s=dT, W_ratio=Wr, band_side_ratio=0.40988 / r["bands_kp_crest_lin"]["side"],
                       band_inlet_ratio=0.186471 / r["bands_kp_crest_lin"]["inlet"],
                       note="FLIP 0.5 m on DFG-2 = R x screen focal crest (nl2 / lin), shifted by dX, dT; widths x W ratio [measured / computed]")
    cal["track_screen"] = [dict(t=round(q["t"] - DFG2_TF, 3), x=q["x"], eta=round(q["eta"], 3), eta_lin=round(q["eta_lin"], 3)) for q in r["track"][::2]]
    cal["cpu_s"] = round(time.time() - t0, 1)
    return cal


# ============================================================================================== FLIP prediction on the step
def flip_predict(res, sea, cal, gamma, mode="nl2"):
    C = cal["rule"]
    R = C["R_nl2"] if mode == "nl2" else C["R_lin"]
    dX = C["dX_m"]; dT = C["dT_s"]
    out = []
    for r in res["track"]:
        xF = r["x"] + dX
        hF = float(DF.bed_h(np.array([xF]), sea.bed)[0])
        v = r["eta"] if mode == "nl2" else r["eta_lin"]
        out.append(dict(t=r["t"] + dT, x=xF, Hc=R * v, h=hF, ratio=R * v / hF, t_screen=r["t"], x_screen=r["x"]))
    il = int(np.argmax([r["eta_lin"] for r in res["track"]]))
    conv = out[il]
    # onset: first point (in time, from 4 s before the converged instant) whose crest reaches gamma x depth
    on = next((p for p in out if p["t"] >= conv["t"] - 4.0 and p["ratio"] >= gamma), None)
    pk = max(out, key=lambda p: p["Hc"])
    xe = x_edge(sea.bed)
    res_ = dict(onset=on, peak=pk, converged=conv, gamma=gamma, mode=mode,
                onset_after_converged_s=(on["t"] - conv["t"]) if on else None, onset_minus_converged_x_m=(on["x"] - conv["x"]) if on else None,
                breaks_at_converged_crest=bool(on is not None and -1.0 <= on["t"] - conv["t"] <= 3.0 and on["x"] - conv["x"] <= 25.0),
                onset_on_face_or_edge=bool(on is not None and xe is not None and on["x"] <= xe + 10.0),
                onset_h_over_h_top=(on["h"] / sea.bed["h_s"]) if (on and sea.bed["kind"] == "shelf") else None)
    return res_


def onset_metrics(sea, pred, cal):
    on = pred["onset"]
    if on is None:
        return None
    cols = sea._nl2["cols"]; xs = XG[cols]
    ts = on["t_screen"] + np.arange(-3.0, 1.5 + 1e-9, 0.25)
    xw = (max(on["x_screen"] - 60.0, XWIN[0]), min(on["x_screen"] + 35.0, XWIN[1]))
    best = None
    for t in ts:
        e = sea.field(YROWS, t)
        m = metrics(e, xs, xw)
        if m and "W50" in m and (best is None or m["Hc"] > best[0]["Hc"]):
            best = (m, t, e)
    m, t, e = best
    o = slim(m)
    o["t_screen"] = t
    o["N1"] = n1_iso(EM.median3(masked(e)), xs, m)
    o["centre_shape"] = centre_shape(e[0], xs, int(np.argmax(np.where((xs >= xw[0]) & (xs <= xw[1]), e[0], -99))))
    Wr = cal["rule"]["W_ratio"]
    cm = dict(m)
    for k in ("W50", "W80", "W95", "W20"):
        cm[k] = m[k] * Wr[k]
    cm["K"] = cm["W20"] / cm["W80"]
    # widths are /Hc: the FLIP crest is R x the screen crest, the absolute width is the screen's -> divide by R/R_flat (= 1 on the flat case)
    miss_c, per_c = EM.score_vs_target(cm)
    o["DFG2_calibrated"] = dict(W50=cm["W50"], W80=cm["W80"], W95=cm["W95"], K=cm["K"], S2=m.get("S2"), miss=miss_c,
                                per={k: (round(v, 3) if v is not None else None) for k, v in per_c.items()},
                                rule="screen widths x DFG-2 measured / screen width ratios [calibrated]")
    return o


def iribarren(Hb, T, slope):
    L0 = G * T * T / (2 * math.pi)
    return slope / math.sqrt(Hb / L0)


def run_candidate(name, spec, cal):
    t0 = time.time()
    bed = bed_spec(spec.get("x_toe"), spec.get("s", 4.0), spec.get("h_top", 7.5))
    mode = spec.get("mode", "design"); side = spec.get("side", "gen180")
    x_f = spec.get("x_f", DFG2_XF)
    if mode == "design" and spec.get("t_f") is None:
        s0 = StepSea(bed, x_f, 0.0, mode, side)
        t_f = float(math.ceil(s0.arr["t_full_s"] + 3.9))
    else:
        t_f = spec.get("t_f", DFG2_TF)
    sea = StepSea(bed, x_f, t_f, mode, side, label=name)
    r = analyse(sea)
    preds = {}
    for gk in ("central", "lo", "hi"):
        preds[gk] = flip_predict(r, sea, cal, GAMMA[gk], "nl2")
    preds["lin_central"] = flip_predict(r, sea, cal, GAMMA["central"], "lin")
    preds["lin_lo"] = flip_predict(r, sea, cal, GAMMA["lo"], "lin")
    om = onset_metrics(sea, preds["central"], cal) or onset_metrics(sea, preds["lo"], cal)
    xe = x_edge(bed)
    slope = (1.0 / bed["s"]) if bed["kind"] == "shelf" else 0.0
    on = preds["central"]["onset"] or preds["lo"]["onset"]
    irb = None
    if on is not None and slope > 0:
        irb = {("H/Hc %.2f T %.2f" % (q, T)): iribarren(on["Hc"] * q, T, slope) for q in (1.0, 1.32) for T in (5.6, 7.0, 9.333)}
    e2, xs = r.pop("_e2")
    res = dict(name=name, spec=spec, bed=bed, x_edge=xe, t_f=t_f, mode=mode, side=side, lay=sea.lay,
               arrival={k: v for k, v in sea.arr.items() if k != "rows"},
               arrival_rows_side=[q for q in sea.arr["rows"] if q["src"] == "side"],
               screen={k: v for k, v in r.items() if k != "track"},
               track=[dict(t=round(q["t"] - t_f, 3), x=q["x"], eta=round(q["eta"], 3), eta_lin=round(q["eta_lin"], 3), h=round(q["h"], 2),
                           ratio=round(q["ratio"], 3), shape=({k: round(v, 3) for k, v in q["shape"].items()} if q["shape"] else None))
                      for q in r["track"]],
               flip_pred={k: {kk: vv for kk, vv in v.items()} for k, v in preds.items()},
               onset_metrics=om, iribarren_b=irb, reflection=reflection(bed, sea.T), cpu_s=round(time.time() - t0, 1))
    return res


def shapecal():
    """centre-row shape ruler (centre_shape: w07, back 0.7-0.9, chord 0.1-0.5, foot) on DFG-2 0.5 m hf (rows y 0.5-2.5 m median, eta0 0.0756)
    at the three group summits t_s + dt (dt -1.5 .. 0 s) [measured] vs the screen of the same sea at t_f + dt [computed] -> ratios
    measured / screen. Used to translate the screen's pre-break shape on the step into an expected FLIP shape [calibrated; transfer guessed]."""
    import glob
    R = REPO + "/Unity/Build/FLIP52/runs/DFG2_flat20_P28_dp0p5/"
    summ = (43.916667, 72.041667, 100.0)
    dts = (-1.5, -1.0, -0.5, 0.0)
    want = {(i, dt): s + dt for i, s in enumerate(summ) for dt in dts}
    got = {}
    xs2 = np.arange(290) + 0.5
    for f in sorted(glob.glob(R + "hf_c*_b*.npz")):
        if f.endswith("b00001.npz"):
            continue
        d = np.load(f); t = d["t"]
        idx = {k: int(np.argmin(np.abs(t - v))) for k, v in want.items() if t[0] - 0.03 <= v <= t[-1] + 0.03}
        if not idx:
            continue
        e = d["eta"]
        for k, i in idx.items():
            if k in got:
                continue
            row = np.median(np.asarray(e[i, 0:3, :], float), axis=0) - 0.0756
            m = (xs2 > 90) & (xs2 < 200)
            got[k] = centre_shape(row, xs2, int(np.argmax(np.where(m, row, -9))))
        del e, d
    sea = StepSea(bed_spec(None), DFG2_XF, DFG2_TF, "design", "gen180")
    cols = np.where((XG >= XWIN[0]) & (XG <= XWIN[1]))[0]; xs = XG[cols]
    sea.prep2(cols)
    scr = {}
    for dt in dts:
        e = sea.field(np.array([0.5]), DFG2_TF + dt)[0]
        scr[dt] = centre_shape(e, xs, int(np.argmax(e)))
    out = dict(measured={"%d_%+.1f" % k: v for k, v in got.items()}, screen={"%+.1f" % k: v for k, v in scr.items()})
    rat = {}
    for key in ("w07", "back_deg", "chord_deg", "foot"):
        for dt in dts:
            ms = [got[(i, dt)][key] for i in range(3) if (i, dt) in got and got[(i, dt)] and key in got[(i, dt)]]
            if ms and scr[dt] and key in scr[dt]:
                rat.setdefault(key, {})["%+.1f" % dt] = float(np.median(ms) / scr[dt][key])
    out["ratio_meas_over_screen"] = rat
    out["at_summit"] = {k: v.get("+0.0") for k, v in rat.items()}
    out["range_dt_-1.5_0"] = {k: [min(v.values()), max(v.values())] for k, v in rat.items()}
    out["note"] = "pre-break surface only; the screen over-sharpens (2nd order) - on the step the 2nd-order part is larger, so the transfer is a guess"
    return out


def particles_est(bed):
    """water volume ratio to DFG-2's flat tank x DFG-2's particle count (5.11 M max at 0.5 m) [measured rate, computed volume]."""
    x = np.arange(0.0, 290.0, 0.25) + 0.125
    h = DF.bed_h(x, bed)
    V = float(np.sum(h) * 0.25 * LAY["W"])
    return dict(V_m3=V, ratio=V / (290.0 * 100.0 * H0), particles_M=5.114992 * V / (290.0 * 100.0 * H0))


CANDS = {
    # name: x_toe, s (slope 1:s), h_top, mode, side, x_f (design focus), t_f (None = arrival rule)
    "S0_dfg2tab_s4_h75": dict(x_toe=100.0, s=4.0, h_top=7.5, mode="dfg2", side="flat"),
    "S1_s4_h75_xf145": dict(x_toe=100.0, s=4.0, h_top=7.5, mode="design", side="gen180", x_f=145.0),
    "S1f_s4_h75_xf145": dict(x_toe=100.0, s=4.0, h_top=7.5, mode="design", side="flat", x_f=145.0),
    "S2_s3_h7_xf145": dict(x_toe=111.0, s=3.0, h_top=7.0, mode="design", side="gen180", x_f=145.0),
    "S3_s5_h75_xf145": dict(x_toe=87.5, s=5.0, h_top=7.5, mode="design", side="gen180", x_f=145.0),
    "S4_s4_h6_xf140": dict(x_toe=94.0, s=4.0, h_top=6.0, mode="design", side="gen180", x_f=140.0),
    "S5_s4_h65_xf145": dict(x_toe=96.0, s=4.0, h_top=6.5, mode="design", side="gen180", x_f=145.0),
    "S6_s3_h65_xf145": dict(x_toe=109.5, s=3.0, h_top=6.5, mode="design", side="gen180", x_f=145.0),
    "S7_s3_h6_xf145": dict(x_toe=108.0, s=3.0, h_top=6.0, mode="design", side="gen180", x_f=145.0),
    "S4b_s4_h6_xf145": dict(x_toe=94.0, s=4.0, h_top=6.0, mode="design", side="gen180", x_f=145.0),
}


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


def short(res):
    f = res["screen"]["focus"]; P = res["flip_pred"]
    def on_(p):
        o = p["onset"]
        return None if o is None else dict(x=round(o["x"], 1), t_rel=round(o["t"] - res["t_f"], 2), Hc=round(o["Hc"], 2), h=round(o["h"], 2),
                                            dt_conv=round(p["onset_after_converged_s"], 2), face=p["onset_on_face_or_edge"],
                                            at_conv=p["breaks_at_converged_crest"])
    c = P["central"]["converged"]
    om = res["onset_metrics"] or {}
    return dict(name=res["name"], x_toe=res["bed"].get("x_toe"), s=res["bed"].get("s"), h_top=res["bed"].get("h_s"), x_edge=res["x_edge"],
                mode=res["mode"], side=res["side"], x_f=res["spec"].get("x_f"), t_f=res["t_f"], aperture=round(res["arrival"]["aperture"], 3),
                side_over_step=round(res["arrival"]["frac_of_focal_sum_from_side_over_step"], 3),
                screen_focus=dict(Hc=f["Hc"], x=f["x_pk"], h=round(f["h_at_pk"], 2), t_rel=round(f["t_rel_tf"], 2), W50=f.get("W50"), miss=f.get("miss")),
                conv_FLIP=dict(x=round(c["x"], 1), t_rel=round(c["t"] - res["t_f"], 2), Hc=round(c["Hc"], 2), h=round(c["h"], 2), ratio=round(c["ratio"], 3)),
                onset=dict(central=on_(P["central"]), g_lo=on_(P["lo"]), g_hi=on_(P["hi"]), lin=on_(P["lin_central"]), lin_g_lo=on_(P["lin_lo"])),
                onset_miss_cal=(om.get("DFG2_calibrated") or {}).get("miss"), onset_W50_cal=(om.get("DFG2_calibrated") or {}).get("W50"),
                onset_shape=om.get("centre_shape"), Nt=round(res["screen"]["Nt_lin"], 3), Nt_t=res["screen"]["Nt_t_rel"], Nt5=round(res["screen"]["Nt5_lin"], 3), gain60=round(res["screen"]["gain_over_c_in60"] or 0, 2),
                bands=res["screen"]["bands_kp_crest_lin"], iribarren=res["iribarren_b"], refl=res["reflection"], particles=particles_est(res["bed"]),
                cpu_s=res["cpu_s"])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if not a:
        print(__doc__); sys.exit(1)
    calp = OUT + "/calib_52s.json"
    if a[0] == "list":
        print(json.dumps(CANDS, indent=1)); return
    if a[0] == "shapecal":
        sc = shapecal()
        jdump(sc, OUT + "/shapecal_52s.json")
        print("shapecal", json.dumps(dict(at_summit=sc["at_summit"], rng=sc["range_dt_-1.5_0"]), default=float)); return
    if a[0] in ("calib", "all"):
        cal = calib()
        jdump(cal, calp)
        print("calib", json.dumps(dict(rule=cal["rule"], screen_focus={k: cal["screen"]["focus"].get(k) for k in ("Hc", "x_pk", "t_rel_tf", "W50", "W80", "W95", "miss")},
                                       lin_Hc=cal["screen"]["focus_lin"]["Hc"], aperture=cal["screen"]["aperture"], t_full=cal["screen"]["t_full"],
                                       Nt=cal["screen"]["Nt_lin"], bands=cal["screen"]["bands"], cpu=cal["cpu_s"]), default=float), flush=True)
    if a[0] in ("run", "all"):
        cal = json.load(open(calp, encoding="utf8"))
        names = a[1:] if (a[0] == "run" and len(a) > 1) else list(CANDS)
        p = OUT + "/dfgs_screen_summary.json"
        summ = json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}
        for nm in names:
            spec = CANDS[nm] if nm in CANDS else json.loads(nm)
            nm2 = nm if nm in CANDS else spec.pop("name")
            r = run_candidate(nm2, spec, cal)
            jdump(r, OUT + "/dfgs_%s.json" % nm2)
            s = short(r)
            summ[nm2] = s
            print("cand", json.dumps(s, default=float), flush=True)
        jdump(summ, p)


if __name__ == "__main__":
    main()
