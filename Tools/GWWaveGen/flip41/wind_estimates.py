"""wind_estimates.py -- numbers for Unity/Build/FLIP41/research/wind_ja.md

Every number in wind_ja.md that is marked [wind_estimates] comes from this script.
Only numpy is used. Run:  py -3.10 wind_estimates.py  (writes wind_estimates.json next to wind_ja.md)

Formulas and their sources (see wind_ja.md for the full citations):
- Linear dispersion  w^2 = g k tanh(k h)                                       (Airy theory)
- Drag coefficient   Cd = 1.2e-3 (4-11 m/s), (0.49 + 0.065 U10) e-3 (11-25 m/s) (Large & Pond 1981)
                     held at the 25 m/s value above 25 m/s (choice, see Powell et al. 2003)
- Wind stress        tau = rho_a Cd U10^2,  u* = sqrt(tau / rho_a)
- Fetch-limited deep water growth (JONSWAP, Hasselmann et al. 1973):
                     g Hm0 / U10^2 = 1.6e-3 (g F / U10^2)^(1/2)
                     g Tp  / U10   = 0.286  (g F / U10^2)^(1/3)
  full development cap (Pierson-Moskowitz, as quoted by Takagi & Takahashi): Hm0 = 0.0246 U10^2
- JONSWAP spectrum as coded in Houdini 22 ocean.h (TMAspectrum): alpha = 0.076 chi^-0.22,
  wp = 2 pi 3.5 (g/U) chi^-0.33, gamma = 3.3, sigma 0.07/0.09  -> integrated here to cross-check Hm0
- Depth-limited peak: kp h -> 1.363 (Karimpour et al. 2017)
- Miles-type growth (Plant 1982): gamma_E = 0.04 (u*/c)^2 w   (energy growth rate, +-50 %)
- Jeffreys sheltering pressure (Jeffreys 1925; S = 0.5 as in Giovanangeli, Kharif & Touboul 2006):
  p = rho_a S (U - c)^2 d(eta)/dx ; if applied on every crest the linear energy growth rate is
  gamma_E = (rho_a / rho_w) S ((U - c)/c)^2 w   (derived in wind_ja.md section 1.4)
- Rayleigh wave heights: P(H > h) = exp(-2 h^2 / Hs^2)
"""
import json
import math
import os

import numpy as np

G = 9.81
RHO_A = 1.2
RHO_W = 1025.0


def wavenumber(T, h):
    w = 2 * math.pi / T
    k = w * w / G  # deep-water start
    for _ in range(200):
        f = G * k * math.tanh(k * h) - w * w
        df = G * math.tanh(k * h) + G * k * h / math.cosh(k * h) ** 2
        k -= f / df
    return k


def dispersion_row(T, h):
    k = wavenumber(T, h)
    w = 2 * math.pi / T
    L = 2 * math.pi / k
    c = w / k
    n = 0.5 * (1 + 2 * k * h / math.sinh(2 * k * h))
    cg = n * c
    L0 = G * T * T / (2 * math.pi)
    c0 = G * T / (2 * math.pi)
    cg0 = c0 / 2
    Ks = math.sqrt(cg0 / cg)  # shoaling coefficient relative to deep water
    miche = 0.142 * L * math.tanh(k * h)  # Miche limiting height
    return dict(T=T, h=h, kh=round(k * h, 3), L=round(L, 1), L0=round(L0, 1), c=round(c, 2),
                c_over_c0=round(c / c0, 3), cg=round(cg, 2), Ks=round(Ks, 3),
                H_limit_miche=round(miche, 1), H_limit_078h=round(0.78 * h, 1))


def cd_large_pond(U):
    if U < 11:
        return 1.2e-3
    return (0.49 + 0.065 * min(U, 25.0)) * 1e-3


def jonswap_fetch(U, F):
    chi = G * F / U ** 2
    Hm0 = 1.6e-3 * math.sqrt(chi) * U ** 2 / G
    Tp = 0.286 * chi ** (1 / 3) * U / G
    Hcap = 0.0246 * U ** 2
    return Hm0, Tp, Hcap, chi


def houdini_tma_hm0(U, F, gamma=3.3):
    """Integrate the JONSWAP part of Houdini's TMAspectrum (deep water, no spreading) -> Hm0."""
    chi = G * F / U ** 2
    alpha = 0.076 * chi ** -0.22
    wp = 2 * math.pi * 3.5 * (G / U) * chi ** -0.33
    w = np.linspace(0.3 * wp, 8 * wp, 20000)
    sigma = np.where(w <= wp, 0.07, 0.09)
    peak = gamma ** np.exp(-((w - wp) / (sigma * wp)) ** 2 / 2.0)
    S = peak * alpha * G * G / w ** 5 * np.exp(-1.25 * (wp / w) ** 4)
    m0 = np.trapz(S, w)
    return 4 * math.sqrt(m0), 2 * math.pi / wp


def depth_limited_tp(h):
    kp = 1.363 / h
    w = math.sqrt(G * kp * math.tanh(kp * h))
    return 2 * math.pi / w


def min_duration_estimate(U, F, n=4000):
    """Time for energy to travel the fetch at the deep-water group speed of the local peak.
    t = int_0^F dx / cg(Tp(x)),  cg = g Tp / (4 pi).  A rough lower bound of the duration needed."""
    x = np.linspace(F / n, F, n)
    Tp = 0.286 * (G * x / U ** 2) ** (1 / 3) * U / G
    cg = G * Tp / (4 * math.pi)
    return float(np.trapz(1 / cg, x) + (F / n) / cg[0])


def growth_in_domain(U, T, transit_s):
    Cd = cd_large_pond(U)
    tau = RHO_A * Cd * U ** 2
    ustar = math.sqrt(tau / RHO_A)
    w = 2 * math.pi / T
    c = G / w
    gam_plant = 0.04 * (ustar / c) ** 2 * w
    gam_jeff_all = (RHO_A / RHO_W) * 0.5 * ((U - c) / c) ** 2 * w if U > c else 0.0
    dE_plant = math.exp(gam_plant * transit_s) - 1
    dH_plant = math.sqrt(1 + dE_plant) - 1
    return dict(U10=U, T=T, Cd=round(Cd, 5), tau_Pa=round(tau, 2), ustar=round(ustar, 3),
                c=round(c, 2), wave_age_c_over_U10=round(c / U, 2), ustar_over_c=round(ustar / c, 3),
                gammaE_plant_per_s=float(f"{gam_plant:.2e}"),
                efold_energy_plant_min=round(1 / gam_plant / 60, 1),
                gammaE_jeffreys_everywhere_per_s=float(f"{gam_jeff_all:.2e}"),
                transit_s=round(transit_s, 1),
                energy_gain_plant_pct=round(100 * dE_plant, 1),
                height_gain_plant_pct=round(100 * dH_plant, 1),
                height_gain_plant_range_pct=[round(100 * (math.sqrt(math.exp(f * gam_plant * transit_s)) - 1), 1)
                                             for f in (0.5, 1.5)])


def main():
    out = {}
    # 1. dispersion: which periods feel the seabed at the depths off Kanagawa
    out["dispersion"] = [dispersion_row(T, h) for T in (5, 6, 7, 8, 10, 12, 14) for h in (15, 25, 40, 60)]

    # 2. fetch-limited wind sea in Tokyo Bay
    rows = []
    for U in (15, 20, 25, 30, 35):
        for F_km in (10, 15, 20, 30, 40):
            F = F_km * 1000.0
            Hm0, Tp, Hcap, chi = jonswap_fetch(U, F)
            Hh, Th = houdini_tma_hm0(U, F)
            rows.append(dict(U10=U, F_km=F_km, chi=round(chi, 0), Hm0=round(min(Hm0, Hcap), 2),
                             Tp=round(Tp, 2), cp_over_U10=round(G * Tp / (2 * math.pi) / U, 2),
                             steep_Hs_over_L0=round(Hm0 / (G * Tp ** 2 / (2 * math.pi)), 3),
                             Hm0_houdini_jonswap=round(Hh, 2), Tp_houdini=round(Th, 2),
                             tmin_h=round(min_duration_estimate(U, F) / 3600, 2)))
    out["fetch_limited"] = rows
    out["depth_limited_Tp"] = {f"h{h}": round(depth_limited_tp(h), 2) for h in (15, 17, 20, 25, 30, 40)}

    # 3. extreme single waves in a Rayleigh sea
    ray = []
    for Hs in (2.3, 3.4, 4.0, 5.6):
        for Hmax in (7.0, 10.0, 12.0):
            r = Hmax / Hs
            p = math.exp(-2 * r * r)
            ray.append(dict(Hs=Hs, H=Hmax, ratio=round(r, 2), p_per_wave=float(f"{p:.2e}")))
    out["rayleigh"] = ray
    # expected max in N waves (approx) for a 3 h storm with Tz = Tp/1.3
    exp_max = []
    for Hs, Tp in ((2.3, 5.7), (3.4, 7.1), (4.0, 7.5), (5.6, 8.0)):
        N = 3 * 3600 / (Tp / 1.3)
        exp_max.append(dict(Hs=Hs, Tp=Tp, N_3h=round(N), Hmax_mode=round(Hs * math.sqrt(math.log(N) / 2), 1)))
    out["rayleigh_expected_max_3h"] = exp_max

    # 4. wind input inside the simulated domain (800 m crossed at group speed)
    dom = []
    for U in (20, 25, 30):
        for T in (6, 7, 8, 12):
            cg = G * T / (4 * math.pi)
            dom.append(growth_in_domain(U, T, 800.0 / cg))
    out["growth_in_domain_800m"] = dom
    # tangential stress acting on a 2 m surface voxel layer for 150 s
    out["surface_layer_du_150s"] = {f"U{U}": round(RHO_A * cd_large_pond(U) * U ** 2 * 150 / (RHO_W * 2.0), 3)
                                    for U in (20, 25, 30)}
    # Jeffreys pressure on a steep crest: p per unit slope, and relative to rho g H for H = 10 m
    jp = []
    for U, T in ((25, 7), (30, 8)):
        c = G * T / (2 * math.pi)
        p_per_slope = RHO_A * 0.5 * (U - c) ** 2
        jp.append(dict(U10=U, T=T, c=round(c, 2), p_per_unit_slope_Pa=round(p_per_slope, 1),
                       p_at_slope_0p5_Pa=round(0.5 * p_per_slope, 1),
                       ratio_to_rho_g_10m=float(f"{0.5 * p_per_slope / (RHO_W * G * 10):.1e}")))
    out["jeffreys_pressure"] = jp

    # 5. fetch growth from inflow to outflow of an 800 m domain (Hm0 ~ F^0.5)
    out["fetch_growth_over_800m_pct"] = {f"F{F}km": round(100 * (math.sqrt((F + 0.8) / F) - 1), 1)
                                         for F in (10, 15, 20, 30)}

    # 6. steepness of a 10-12 m wave at bay periods
    st = []
    for H in (7, 10, 11, 12):
        for T in (6, 7, 7.5, 8, 9):
            L0 = G * T * T / (2 * math.pi)
            st.append(dict(H=H, T=T, L0=round(L0, 1), H_over_L0=round(H / L0, 3)))
    out["steepness"] = st

    here = os.path.dirname(os.path.abspath(__file__))
    dst = os.path.normpath(os.path.join(here, "..", "..", "..", "Unity", "Build", "FLIP41", "research",
                                        "wind_estimates.json"))
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
