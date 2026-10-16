# -*- coding: utf-8 -*-
"""FLIP50 (option D): linear directional monochromatic wave field over a laterally straight bed (numpy only, py -3.10 -I).
2026-10-15 written new for the option D design (Claude). No flip45-flip49 file is edited or imported here.

What it is
  A monochromatic (one period T) sea made of N plane-wave components that all have the same frequency but different
  directions theta_j (angle from +x at the generation depth h0). The bed depends on x only (flat h0, then a straight 1:s slope,
  then a shelf or a beach), so every component keeps its lateral wavenumber k_y,j = k(h0) sin(theta_j) (Snell), refracts toward
  the shore normal (sin theta_j(x) = k_y,j / k(x)), and shoals. WKB (slowly varying) amplitude per component:
      A_j(x) = a_j * Ks(x) * Kr_j(x),  Ks = sqrt(cg(h0)/cg(h)),  Kr_j = sqrt(cos theta_j0 / cos theta_j(x))
  phase  phi_j(x, y, t) = Phi_j(x) + k_y,j y - omega (t - t_f),  Phi_j(x) = integral_{x_f}^{x} k_x,j dx'
  so every component has phase 0 at the chosen focus point (x_f, y = 0) at t = t_f.  eta = sum_j A_j cos(phi_j).
  Components come in +-theta pairs, so the field is symmetric about y = 0 (the symmetry plane of the half tank).
Consequences used by the design
  * every component has the same omega, so A(x, y) = sum_j A_j exp(i(Phi_j + k_y,j y)) is time independent: the focus is a fixed
    hot spot and a crest passes it once per period (eta = Re(A e^{-i omega (t - t_f)})). This is the periodicity.
  * the lateral wavenumbers are bounded by k(h0) (k_y <= k(h0)), whatever the bed does later, because a y-uniform bed conserves k_y.
Limits: linear (no crest-trough asymmetry, no amplitude dispersion), WKB on a 1:10 slope (no slope reflection), no breaking.
"""
import math
import numpy as np

G = 9.80665


def kdisp(om, h):
    """linear wavenumber k(h) for angular frequency om (vectorised Newton)."""
    h = np.asarray(h, float)
    k0 = om * om / G
    k = np.maximum(k0 / np.sqrt(np.tanh(k0 * np.maximum(h, 1e-6))), om / np.sqrt(G * np.maximum(h, 1e-6)))
    for _ in range(60):
        th = np.tanh(k * h)
        f = G * k * th - om * om
        df = G * th + G * k * h * (1 - th * th)
        k = k - f / df
    return k


def cg(om, h):
    k = kdisp(om, h)
    kh = k * np.asarray(h, float)
    return om / k * 0.5 * (1 + 2 * kh / np.sinh(2 * kh))


def bed_h(x, spec):
    """still-water depth (positive, may be negative = dry beach) of the laterally straight bed.
    spec: h0, x_toe, s (slope 1:s), kind 'beach' (slope continues through the still level) or 'shelf' (depth floor h_s),
    for 'shelf' optional back drop: x_back, s_back, h_lag (as FLIP49 option A: x > x_back, d = max(d, min(h_lag, h_s + (x - x_back)/s_back)))."""
    x = np.asarray(x, float)
    d = spec["h0"] - np.maximum(x - spec["x_toe"], 0.0) / spec["s"]
    if spec.get("kind", "beach") == "shelf":
        d = np.maximum(d, spec["h_s"])
        xb = spec.get("x_back")
        if xb is not None:
            d = np.where(x > xb, np.maximum(d, np.minimum(spec["h_lag"], spec["h_s"] + (x - xb) / spec["s_back"])), d)
    return d


def components(theta_max_deg, n, weight="uniform", s_cos=None):
    """symmetric set of n directions uniform in theta over [-theta_max, theta_max] (Fochesato et al. 2007 style) and relative
    amplitudes w_j (sum 1). weight: 'uniform' (equal a_j), 'fgd' (a_j ∝ 1/cos theta_j, the FGD07 flap-stroke rule),
    'cos2s' (a_j ∝ cos^{2s}(theta_j / 2), s = s_cos)."""
    th = np.linspace(-theta_max_deg, theta_max_deg, n)
    r = np.radians(th)
    if weight == "uniform":
        w = np.ones(n)
    elif weight == "fgd":
        w = 1.0 / np.cos(r)
    elif weight == "cos2s":
        w = np.cos(r / 2.0) ** (2 * float(s_cos))
    else:
        raise ValueError(weight)
    return th, w / w.sum()


class DirField:
    """WKB tables per component on an x grid (laterally straight bed). Phases are referenced to (x_f, 0, t_f)."""

    def __init__(self, T, theta_deg, w, a_sum, x, spec, x_f, h_gen=None):
        self.T = float(T); self.om = 2 * math.pi / self.T
        self.x = np.asarray(x, float); self.spec = dict(spec); self.x_f = float(x_f)
        self.h = bed_h(self.x, spec)
        self.h_gen = float(h_gen if h_gen is not None else spec["h0"])
        self.k0 = float(kdisp(self.om, self.h_gen))
        self.theta0 = np.radians(np.asarray(theta_deg, float))
        self.a = float(a_sum) * np.asarray(w, float)                 # a_j at the generation depth (sum = linear focal amplitude there)
        self.ky = self.k0 * np.sin(self.theta0)
        wet = self.h > 0.05
        self.wet = wet
        hk = np.where(wet, self.h, 0.05)
        self.k = kdisp(self.om, hk)
        self.Ks = np.sqrt(cg(self.om, self.h_gen) / cg(self.om, hk))
        kx = np.sqrt(np.maximum(self.k[None, :] ** 2 - self.ky[:, None] ** 2, 0.0))   # (n, nx)
        self.kx = kx
        cos0 = np.cos(self.theta0)[:, None]
        cosx = kx / self.k[None, :]
        self.Kr = np.sqrt(cos0 / np.maximum(cosx, 1e-6))
        self.Aj = self.a[:, None] * self.Ks[None, :] * self.Kr                       # (n, nx)
        # Phi_j(x) = int_{x_f}^{x} kx dx (trapezoid on the grid, then shift so Phi_j(x_f) = 0)
        dx = np.diff(self.x)
        cum = np.concatenate([np.zeros((len(self.a), 1)), np.cumsum(0.5 * (kx[:, 1:] + kx[:, :-1]) * dx[None, :], axis=1)], axis=1)
        cf = np.array([np.interp(self.x_f, self.x, c) for c in cum])
        self.Phi = cum - cf[:, None]
        self.Aj[:, ~wet] = 0.0

    def complex_amp(self, y):
        """A(x, y) on the x grid and the given y (array): sum_j A_j exp(i (Phi_j + ky_j y)). Returns (nx, ny) complex."""
        y = np.asarray(y, float)
        A = np.zeros((len(self.x), len(y)), complex)
        for j in range(len(self.a)):
            A += (self.Aj[j] * np.exp(1j * self.Phi[j]))[:, None] * np.exp(1j * self.ky[j] * y)[None, :]
        return A

    def eta(self, y, t, tf=0.0):
        return np.real(self.complex_amp(y) * np.exp(-1j * self.om * (t - tf)))

    def depth_avg_vel(self, y, t, tf=0.0):
        """depth-averaged linear velocity (U, V) from mass conservation per component: U = sum A_j (om / (k h)) cos(th_j(x)) cos(phi),
        V = sum A_j (om / (k h)) sin(th_j(x)) cos(phi). For the Boussinesq screen inlet target (flat part, h = h0)."""
        y = np.asarray(y, float)
        U = np.zeros((len(self.x), len(y))); V = np.zeros_like(U)
        hk = np.where(self.wet, self.h, 1.0)
        for j in range(len(self.a)):
            ph = self.Phi[j][:, None] + self.ky[j] * y[None, :] - self.om * (t - tf)
            amp = (self.Aj[j] * self.om / (self.k * hk))[:, None] * np.cos(ph)
            U += amp * (self.kx[j] / self.k)[:, None]
            V += amp * (self.ky[j] / self.k)[:, None]
        return U, V

    def complex_vel(self, y, depth_avg=True, z=None):
        """complex amplitudes (Uc, Vc) on (x grid, y) with U(t) = Re(Uc e^{-i om (t - t_f)}).
        depth_avg True: depth-averaged velocity om/(k h) per component (Boussinesq screen). Otherwise the linear velocity at
        elevation z (<= 0, m) with the local cosh profile: om cosh(k (z + h))/sinh(k h) (FLIP band target, per depth level)."""
        y = np.asarray(y, float)
        Uc = np.zeros((len(self.x), len(y)), complex); Vc = np.zeros_like(Uc)
        hk = np.where(self.wet, self.h, 1.0)
        if depth_avg:
            fac = self.om / (self.k * hk)
        else:
            zz = np.maximum(float(z), -hk)
            fac = self.om * np.cosh(self.k * (zz + hk)) / np.sinh(self.k * hk)
        for j in range(len(self.a)):
            base = (self.Aj[j] * fac * np.exp(1j * self.Phi[j]))[:, None] * np.exp(1j * self.ky[j] * y)[None, :]
            Uc += base * (self.kx[j] / self.k)[:, None]
            Vc += base * (self.ky[j] / self.k)[:, None]
        return Uc, Vc

    def ray_back(self, j, x_stop):
        """y of the ray of component j that reaches the focus (x_f, 0), traced back to x_stop (< x_f): y(x) = int_x^{x_f} tan(theta_j) dx'.
        Positive y = the side the ray came from in the half tank. Returns (x array from x_f down to x_stop, y array)."""
        m = (self.x >= x_stop) & (self.x <= self.x_f)
        xs = self.x[m][::-1]
        tn = (self.ky[j] / np.maximum(self.kx[j][m][::-1], 1e-9))
        yy = np.concatenate([[0.0], np.cumsum(0.5 * (tn[1:] + tn[:-1]) * np.abs(np.diff(xs)))])
        return xs, np.abs(yy)


def aperture(df, W, side_band, x_band_end, x_gen, x_sw):
    """fraction of the focal linear amplitude whose rays (traced back from the focus) start where the bands generate the target:
    inside the inlet band (ray at x_band_end has y <= W) or leaving the inner edge of the side band (y = W - side_band) at
    x <= x_gen (full), x_gen..x_sw (linear fade), > x_sw (missing). Returns dict(frac, per-component list)."""
    y_in = W - side_band
    out = []
    num = 0.0
    for j in range(len(df.a)):
        xs, yy = df.ray_back(j, x_band_end)
        if yy[-1] <= W + 1e-9:
            f = 1.0; xc = None
        else:
            i = int(np.argmax(yy >= y_in))
            xc = float(xs[i])
            f = 1.0 if xc <= x_gen else (0.0 if xc >= x_sw else 1.0 - (xc - x_gen) / (x_sw - x_gen))
        A_f = float(np.interp(df.x_f, df.x, df.Aj[j]))
        num += f * A_f
        out.append(dict(theta_deg=float(np.degrees(df.theta0[j])), y_at_band=float(yy[-1]), x_cross_side=xc, frac=f))
    tot = float(sum(np.interp(df.x_f, df.x, df.Aj[j]) for j in range(len(df.a))))
    return dict(frac=num / tot if tot > 0 else None, comps=out)
