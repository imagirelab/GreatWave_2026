# -*- coding: utf-8 -*-
"""FLIP51 bathymetric-convergence screen (lens / pinnacle / fan), linear time-domain mild-slope (l51_mse). py -3.10 -B.
2026-10-17 written new (Claude). Outputs under Unity/Build/FLIP51/lens/. [computed] unless stated.

Per case (linear, unit incident amplitude, then scaled):
  axis gamma(x) = 2 |A|_s / h (|A|_s = rms over a half local wavelength: removes the partial-standing ripple of the beach reflection);
  break x_b = first x (downstream of the inlet band) where gamma >= gamma_b at the chosen incident amplitude;
  'early' = gamma max anywhere upstream of x_b - 20 m on rows |y| <= 140 (over a lens top) / gamma_b;
  crest metrics at the instant the crest is at (x_b, 0): c(y) = max over x in [x_b - 30, x_b + 10] of eta_lin(x, y, t*);
  Hc_pred = r_hc h_b (calibrated on DM1A / DF1A onsets), widths of c_lin at f Hc_pred (W50, W20 good; W80/W95 rough because the
  summit is capped by breaking), S2 = c_lin(+-2 Hc_pred) / Hc_pred, ring_max over 2-5 Hc_pred seaward of x_b + 10;
  side-feeding proxies: (a) crest lag of the side crest at |y| = 1, 2, 3 Hc behind the summit (m; < 0 = side crest AHEAD, it
  reaches shallow water first); (b) SF = lateral wave-energy inflow into the strip |y| <= 1 Hc over the last 2 s of travel before x_b,
  over the energy flux along x through the strip at x_b (energy flux F = 0.5 rho g c cg / om Im(A* grad A)).
"""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP51/lens"
DX = 2.0


def smooth_rms(a, x, L):
    """rms of |a| over a running window of length L (1D)."""
    n = max(1, int(round(L / (x[1] - x[0]))))
    k = np.ones(n) / n
    return np.sqrt(np.convolve(np.abs(a) ** 2, k, mode="same"))


def energy_flux(tk, A):
    """time-mean energy flux (per rho g / 2): c cg / om * Im(conj(A) grad A)."""
    gy, gx = np.gradient(A, tk.dy, tk.dx)
    f = tk.c * tk.cg / tk.om
    return f * np.imag(np.conj(A) * gx), f * np.imag(np.conj(A) * gy)


def analyse(tk, A1, a_inc, gamma_b, r_hc, x_min=110.0, x_b_force=None, label=""):
    x, y, h = tk.x, tk.y, tk.h
    om = tk.om
    A = A1 * a_inc
    hax = h[0]
    kax = tk.k[0]
    L_loc = 2 * math.pi / np.median(kax[(x > x_min) & (hax > 3)])
    As = smooth_rms(A[0], x, 0.5 * L_loc) * math.sqrt(1.0)      # rms of |A| over L/2 (|A| itself, not eta)
    gam = np.where(hax > 1.0, 2 * As / np.maximum(hax, 1e-6), np.nan)
    ok = (x >= x_min) & np.isfinite(gam)
    if x_b_force is not None:
        ib = int(np.argmin(np.abs(x - x_b_force)))
    else:
        hit = ok & (gam >= gamma_b)
        if not hit.any():
            return dict(label=label, broke=False, gamma_max=float(np.nanmax(gam[ok])), a_inc=a_inc)
        ib = int(np.argmax(hit))
    xb = float(x[ib]); hb = float(hax[ib])
    # early breaking anywhere upstream (lens top, flanks)
    Ag = np.abs(A)
    gm2 = np.where(h > 1.0, 2 * Ag / np.maximum(h, 1e-6), 0)
    up = (x[None, :] >= x_min) & (x[None, :] <= xb - 20.0) & (np.abs(y[:, None]) <= 140)
    early = float(np.max(np.where(up, gm2, 0)) / gamma_b)
    # instant: crest at (x_b, 0)
    ph = np.angle(A[0, ib])
    ts = ph / om
    eta = np.real(A * np.exp(-1j * om * ts))
    Hc = r_hc * hb
    Hlin = float(eta[0, ib])
    cwin = (x >= xb - 30) & (x <= xb + 10)
    c = np.max(np.where(cwin[None, :], eta, -np.inf), axis=1)
    yy = np.concatenate([-y[:0:-1], y]); cc = np.concatenate([c[:0:-1], c])
    i0 = len(y) - 1
    cc_cap = np.minimum(cc, Hc)
    out = dict(label=label, broke=True, a_inc=a_inc, x_b=xb, h_b=hb, Hc_pred=Hc, H_lin_at_b=Hlin, amp_s_b=float(As[ib]),
               gamma_b=gamma_b, early_over_gamma_b=early, gain_lin_b=float(As[ib] / a_inc), L_loc=L_loc)
    for f in (0.2, 0.5, 0.8, 0.95):
        wv, ce = M.run_width(cc_cap, yy, i0, f * Hc)
        out["W%d_m" % int(round(f * 100))] = wv
        out["W%d" % int(round(f * 100))] = wv / Hc
        out["W%d_cens" % int(round(f * 100))] = ce
    Hl = float(cc[i0])
    out["H_lin_win"] = Hl
    for f in (0.2, 0.5, 0.8, 0.95):
        wv, ce = M.run_width(cc, yy, i0, f * Hl)
        out["Ws%d_m" % int(round(f * 100))] = wv
        out["Ws%d_cens" % int(round(f * 100))] = ce
    out["Ks"] = out["Ws20_m"] / out["Ws80_m"] if out["Ws80_m"] > 0 else None
    out["K"] = out["W20"] / out["W80"] if out["W80"] > 0 else None
    out["taper"] = out["W80"] / out["W50"] if out["W50"] > 0 else None
    for nm, kk in (("S1", 1.0), ("S2", 2.0)):
        out[nm] = float(np.interp(kk * Hc, y, c) / Hc)
    XX, YY = np.meshgrid(x, y)
    r = np.hypot(XX - xb, YY)
    ring = (r >= 2 * Hc) & (r <= 5 * Hc) & (XX <= xb + 10)
    out["ring_max"] = float(np.max(eta[ring]) / Hc)
    out["ring_p90"] = float(np.percentile(eta[ring], 90) / Hc)
    # incident crest (linear) and side level far away
    out["c_in_over_Hc"] = a_inc / Hc
    # side crest lag
    lag = {}
    for kk in (1, 2, 3):
        j = int(np.argmin(np.abs(y - kk * Hc)))
        row = np.where(cwin, eta[j], -np.inf)
        lag[str(kk)] = float(xb - x[int(np.argmax(row))])
    out["side_lag_m"] = lag
    # energy-flux side-feeding proxy
    Fx, Fy = energy_flux(tk, A)
    js = int(np.argmin(np.abs(y - Hc)))
    cgb = float(tk.cg[0, ib])
    x0 = xb - 2.0 * cgb
    mx = (x >= x0) & (x <= xb)
    inflow = -np.trapz(Fy[js, mx], x[mx]) * 2          # both sides (mirror), positive = toward the axis
    through = np.trapz(Fx[:js + 1, ib], y[:js + 1]) * 2
    out["SF"] = float(inflow / through) if through > 0 else None
    # energy-flux convergence along the whole path: lateral inflow from the inlet to x_b over flux at the inlet across the strip
    mx2 = (x >= x_min) & (x <= xb)
    infl2 = -np.trapz(Fy[js, mx2], x[mx2]) * 2
    out["SF_path"] = float(infl2 / through) if through > 0 else None
    out["profile_y"] = y[:: max(1, int(4 / DX))].tolist()
    out["profile_c_over_Hc"] = (c[:: max(1, int(4 / DX))] / Hc).tolist()
    return out


def run_case(T, x, y, h, target_kind="plane", a_ref=1.0, fan=None, side=None, swash=(6.0, 2.0, 2), exit_x0=None, periods=30,
             inlet_x1=100.0):
    tk = M.Tank(T, x, y, h)
    if target_kind == "plane":
        row = h[0].copy()
        # the target is the straight-bed field: flat h0 upstream of any feature (use the far-side row as the y-uniform bed)
        row = h[-1].copy()
        AT = np.tile(M.wkb_plane(T, x, row, a_ref), (len(y), 1))
    else:
        AT = M.fan_target(T, x, y, **fan)
    w, mu = M.band_maps(x, y, h, inlet_x1=inlet_x1, side=side, exit_x0=exit_x0, swash_h=None)
    if swash is not None:
        hs, sig, pw = swash
        mu = np.maximum(mu, sig * np.clip((hs - h) / hs, 0, 1) ** pw)
    r = tk.run(AT, w, mu, periods=periods)
    return tk, r["A"], AT


if __name__ == "__main__":
    pass
