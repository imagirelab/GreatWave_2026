# -*- coding: utf-8 -*-
"""FLIP51 bathymetric-convergence screen: linear time-domain mild-slope solver (numpy only, py -3.10 -B).
2026-10-17 written new (Claude). Reads nothing from the running hero chain except read-only imports of pure functions.

Equation (Copeland 1985 hyperbolic form of the Berkhoff mild-slope equation, one frequency omega):
    (cg / c) eta_tt = div( c cg grad eta ) - mu eta_t
  whose time-harmonic solutions eta = Re(A e^{-i omega t}) satisfy div(c cg grad A) + k^2 c cg A = 0 (refraction, diffraction,
  shoaling, reflection; linear, no breaking, no amplitude dispersion).
Grid: plan (y, x) nodes, y = 0 mirror (half tank, as FLIP), Neumann walls elsewhere; leapfrog in time.
Bands (as the FLIP tanks): relaxation toward a time-harmonic target A_T (inlet band, side band) with per-step weight w(x, y);
  absorbing sponge mu(x, y) (exit / swash / far side).
Output: complex amplitude A(x, y) by demodulation over whole periods after the start-up.
Tags: [computed] everything here.
"""
import math
import numpy as np

G = 9.80665


def kdisp(om, h):
    h = np.asarray(h, float)
    k0 = om * om / G
    k = np.maximum(k0 / np.sqrt(np.tanh(k0 * np.maximum(h, 1e-6))), om / np.sqrt(G * np.maximum(h, 1e-6)))
    for _ in range(60):
        th = np.tanh(k * h)
        f = G * k * th - om * om
        df = G * th + G * k * h * (1 - th * th)
        k = k - f / df
    return k


def cgc(om, h):
    k = kdisp(om, h)
    kh = k * np.asarray(h, float)
    c = om / k
    n = 0.5 * (1 + 2 * kh / np.sinh(2 * kh))
    return k, c, n * c


def smooth01(c):
    c = np.clip(c, 0.0, 1.0)
    return c * c * (3 - 2 * c)


class Tank:
    def __init__(self, T, x, y, h, hmin=0.6):
        self.T = float(T); self.om = 2 * math.pi / self.T
        self.x = np.asarray(x, float); self.y = np.asarray(y, float)
        self.dx = float(self.x[1] - self.x[0]); self.dy = float(self.y[1] - self.y[0])
        self.h = np.asarray(h, float)                      # (ny, nx), positive depth (may be < 0 = dry)
        he = np.maximum(self.h, hmin)
        self.k, self.c, self.cg = cgc(self.om, he)
        self.p = self.cg / self.c
        self.q = self.c * self.cg
        self.qx = 0.5 * (self.q[:, 1:] + self.q[:, :-1])
        self.qy = 0.5 * (self.q[1:, :] + self.q[:-1, :])
        self.cmax = float(np.max(self.c))

    def lap(self, e):
        dx, dy = self.dx, self.dy
        fx = self.qx * (e[:, 1:] - e[:, :-1]) / dx
        fy = self.qy * (e[1:, :] - e[:-1, :]) / dy
        d = np.zeros_like(e)
        d[:, 1:-1] += (fx[:, 1:] - fx[:, :-1]) / dx
        d[:, 0] += 2 * fx[:, 0] / dx
        d[:, -1] += -2 * fx[:, -1] / dx
        d[1:-1, :] += (fy[1:, :] - fy[:-1, :]) / dy
        d[0, :] += 2 * fy[0, :] / dy                         # mirror at y = 0
        d[-1, :] += -2 * fy[-1, :] / dy
        return d

    def run(self, A_T=None, w=None, mu=None, n_per=None, periods=24, demod=3, ramp_T=2.0, cfl=0.5, snap_times=None):
        """A_T: complex target (ny, nx) for the relaxation bands; w: per-step blend weight (0..1); mu: sponge (1/s).
        Returns dict(A=complex amplitude, dt, steps)."""
        om, T = self.om, self.T
        dtmax = cfl * min(self.dx, self.dy) / (self.cmax * math.sqrt(2.0))
        if n_per is None:
            n_per = int(math.ceil(T / dtmax))
        dt = T / n_per
        ny, nx = self.h.shape
        if mu is None:
            mu = np.zeros((ny, nx))
        if w is None:
            w = np.zeros((ny, nx))
        if A_T is None:
            A_T = np.zeros((ny, nx), complex)
        e0 = np.zeros((ny, nx)); e1 = np.zeros((ny, nx))
        a = 1 + 0.5 * mu * dt; b = 1 - 0.5 * mu * dt
        fac = dt * dt / self.p
        nsteps = periods * n_per
        nd0 = (periods - demod) * n_per
        Aacc = np.zeros((ny, nx), complex)
        wm = w > 0
        Tw = A_T[wm]
        ww = w[wm]
        snaps = {}
        for n in range(1, nsteps + 1):
            t = n * dt
            e2 = (2 * e1 - b * e0 + fac * self.lap(e1)) / a
            if wm.any():
                r = 1.0 if t >= ramp_T * T else 0.5 * (1 - math.cos(math.pi * t / (ramp_T * T)))
                tgt = r * np.real(Tw * np.exp(-1j * om * t))
                e2[wm] = (1 - ww) * e2[wm] + ww * tgt
            e0, e1 = e1, e2
            if n > nd0:
                Aacc += e1 * np.exp(1j * om * t)
            if snap_times is not None:
                for ts in snap_times:
                    if abs(t - ts) < 0.5 * dt:
                        snaps[ts] = e1.copy()
        A = Aacc * 2.0 / (demod * n_per)
        return dict(A=A, dt=dt, steps=nsteps, n_per=n_per, snaps=snaps)


# ---------------------------------------------------------------- beds
def bed_beach(x, y, h0=19.0, x_toe=160.25, s=10.0):
    X, Y = np.meshgrid(x, y)
    return h0 - np.maximum(X - x_toe, 0.0) / s


def mound(x, y, xc, Rx, Ry, dh, shape="cos2", yc=0.0):
    """depth reduction of a smooth mound (elliptic footprint semi-axes Rx, Ry; top reduction dh)."""
    X, Y = np.meshgrid(x, y)
    r = np.sqrt(((X - xc) / Rx) ** 2 + ((Y - yc) / Ry) ** 2)
    if shape == "cos2":
        f = np.where(r < 1.0, np.cos(0.5 * math.pi * r) ** 2, 0.0)
    elif shape == "cap":                                   # Berkhoff-like flattened cap
        f = np.where(r < 1.0, np.sqrt(np.maximum(1 - r * r, 0.0)), 0.0)
    elif shape == "cone":
        f = np.where(r < 1.0, 1 - r, 0.0)
    else:
        raise ValueError(shape)
    return dh * f


def bed_da3(x, y):
    """FLIP49 DA3 spur_channel_drop bed (cfg.json bed.formula), depth positive."""
    X, Y = np.meshgrid(x, y)
    h0, x_toe, s, k, k_end, xk1, xk2 = 17.0, 180.25, 10.0, 0.35, 1.0, 277.25, 333.25
    h_r, ch_y0, ch_w, ch_h, ch_x0, ch_lx = 1.7, 30.0, 4.0, 25.0, 187.25, 40.0
    x_back, s_back, h_lag = 353.25, 2.0, 6.0
    kx = k + (k_end - k) * np.clip((X - xk1) / (xk2 - xk1), 0, 1)
    d1 = np.maximum(h_r, h0 - np.maximum(X - x_toe, 0) / s / np.cosh(kx * np.abs(Y) / h0) ** 2)
    wch = 0.5 * (1 + np.tanh((np.abs(Y) - ch_y0) / ch_w)) * np.clip((X - ch_x0) / ch_lx, 0, 1)
    d2 = d1 * (1 - wch) + np.maximum(d1, ch_h) * wch
    d = np.where(X > x_back, np.maximum(d2, np.minimum(h_lag, h_r + (X - x_back) / s_back)), d2)
    return d


# ---------------------------------------------------------------- targets (straight-bed WKB, as the FLIP tables)
def wkb_plane(T, x, h_row, a, x_ref=0.0):
    """plane wave along x over a y-uniform depth row h_row(x): A(x) = a Ks(x) exp(i int k dx)."""
    om = 2 * math.pi / T
    hk = np.maximum(h_row, 0.3)
    k, c, cg = cgc(om, hk)
    k0, c0, cg0 = cgc(om, np.array([h_row[0]]))
    Ks = np.sqrt(cg0[0] / cg)
    ph = np.concatenate([[0.0], np.cumsum(0.5 * (k[1:] + k[:-1]) * np.diff(x))])
    ph -= np.interp(x_ref, x, ph)
    return a * Ks * np.exp(1j * ph)


def fan_target(T, x, y, h0, x_toe, s, a_sum, x_f, thm=80.0, n=30):
    """option-D fan over the straight beach (WKB per component, same math as g50_dirfield, re-written here)."""
    om = 2 * math.pi / T
    th = np.radians(np.linspace(-thm, thm, n))
    aj = a_sum / n * np.ones(n)
    hrow = h0 - np.maximum(x - x_toe, 0) / s
    wet = hrow > 0.05
    hk = np.where(wet, hrow, 0.05)
    k0 = float(kdisp(om, np.array([h0]))[0])
    k, c, cg = cgc(om, hk)
    _, _, cg0 = cgc(om, np.array([h0]))
    Ks = np.sqrt(cg0[0] / cg)
    ky = k0 * np.sin(th)
    kx = np.sqrt(np.maximum(k[None, :] ** 2 - ky[:, None] ** 2, 0.0))
    Kr = np.sqrt(np.cos(th)[:, None] / np.maximum(kx / k[None, :], 1e-6))
    Aj = aj[:, None] * Ks[None, :] * Kr
    cum = np.concatenate([np.zeros((n, 1)), np.cumsum(0.5 * (kx[:, 1:] + kx[:, :-1]) * np.diff(x)[None, :], axis=1)], axis=1)
    cf = np.array([np.interp(x_f, x, cc) for cc in cum])
    Phi = cum - cf[:, None]
    Aj[:, ~wet] = 0
    A = np.zeros((len(y), len(x)), complex)
    for j in range(n):
        A += np.exp(1j * ky[j] * y)[:, None] * (Aj[j] * np.exp(1j * Phi[j]))[None, :]
    return A


# ---------------------------------------------------------------- band maps
def band_maps(x, y, h, inlet_x1=100.0, wall_taper=20.0, side=None, exit_x0=None, exit_sigma=1.4, swash_h=2.5, swash_sigma=1.4,
              wmax=0.25, far_side_sponge=None):
    """w: relaxation weight; mu: sponge. side = (y0, x_gen, x_sw) generating side band (target) then absorbing."""
    X, Y = np.meshgrid(x, y)
    w = np.zeros_like(X); mu = np.zeros_like(X)
    chi = np.clip((inlet_x1 - X) / inlet_x1, 0, 1)
    w = np.maximum(w, wmax * smooth01(chi * 1.0) ** 1)
    if side is not None:
        y0, xg, xs = side
        W = y[-1]
        cs = np.clip((Y - y0) / (W - y0), 0, 1)
        gen = 1 - smooth01((X - xg) / max(xs - xg, 1e-6))
        w = np.maximum(w, wmax * smooth01(cs) * gen)
        mu = np.maximum(mu, exit_sigma * cs ** 2 * (1 - gen))
    if exit_x0 is not None:
        cx = np.clip((X - exit_x0) / (x[-1] - exit_x0), 0, 1)
        mu = np.maximum(mu, exit_sigma * cx ** 2)
    if swash_h is not None:
        mu = np.maximum(mu, swash_sigma * np.clip((swash_h - h) / swash_h, 0, 1) ** 1)
    if far_side_sponge is not None:
        y0 = far_side_sponge
        cs = np.clip((Y - y0) / (y[-1] - y0), 0, 1)
        mu = np.maximum(mu, exit_sigma * cs ** 2)
    return w, mu


# ---------------------------------------------------------------- linear crest-line metrics (same definitions as e51 hf_metrics,
# applied to eta(x, y, t*) = Re(A e^{-i om t*}) at the instant the hot spot crest is highest)
def run_width(prof, coord, i0, level):
    n = len(prof)
    if prof[i0] < level:
        return 0.0, False
    cens = False
    j = i0
    while j + 1 < n and prof[j + 1] >= level:
        j += 1
    if j + 1 >= n:
        hi = coord[j]; cens = True
    else:
        a_, b_ = prof[j], prof[j + 1]; hi = coord[j] + (coord[j + 1] - coord[j]) * (a_ - level) / max(a_ - b_, 1e-12)
    j = i0
    while j - 1 >= 0 and prof[j - 1] >= level:
        j -= 1
    if j - 1 < 0:
        lo = coord[j]; cens = True
    else:
        a_, b_ = prof[j], prof[j - 1]; lo = coord[j] - (coord[j] - coord[j - 1]) * (a_ - level) / max(a_ - b_, 1e-12)
    return float(hi - lo), cens


def crest_metrics(eta_half, x, y, x_pk_hint=None, xwin=(-60.0, 35.0), cw=(30.0, 10.0), Hc_override=None):
    """eta_half (ny, nx) on y >= 0; mirror to full; summit = max; widths in metres and / Hc (Hc = summit or override)."""
    eta = np.concatenate([eta_half[:0:-1], eta_half], 0)
    yy = np.concatenate([-y[:0:-1], y])
    if x_pk_hint is not None:
        sel = (x >= x_pk_hint + xwin[0]) & (x <= x_pk_hint + xwin[1])
    else:
        sel = np.ones_like(x, bool)
    sub = np.where(sel[None, :], eta, -np.inf)
    iy, ix = np.unravel_index(np.argmax(sub), sub.shape)
    Hc = float(eta[iy, ix]); x_pk = float(x[ix])
    cwin = (x >= x_pk - cw[0]) & (x <= x_pk + cw[1])
    c = np.max(np.where(cwin[None, :], eta, -np.inf), axis=1)
    out = dict(Hc_lin=Hc, x_pk=x_pk, y_pk=float(abs(yy[iy])))
    for f in (0.2, 0.5, 0.8, 0.95):
        wv, ce = run_width(c, yy, iy, f * Hc)
        out["W%d_m" % int(round(f * 100))] = wv
        out["W%d_cens" % int(round(f * 100))] = ce
    for nm, kk in (("S1", 1.0), ("S2", 2.0)):
        pass
    out["c_profile"] = (yy, c)
    return out


def wkb_ks(T, h_from, h_to):
    om = 2 * math.pi / T
    _, _, cg1 = cgc(om, np.array([h_from]))
    _, _, cg2 = cgc(om, np.array([h_to]))
    return float(np.sqrt(cg1[0] / cg2[0]))
