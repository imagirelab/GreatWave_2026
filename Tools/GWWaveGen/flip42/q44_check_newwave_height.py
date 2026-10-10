# -*- coding: utf-8 -*-
"""Q44 の見直し（2026-10-09）：q44_newwave_height.py とは別に書いた、線形 NewWave の H/η_c の確かめ。
q44_newwave_height.py の関数を使わない。成分は 20,001 本の台形の積分（160 本も比べる）、谷は頂の後の
ゼロを下へ切る点から次に上へ切る点までの最小。JONSWAP のほか TMA（Kitaigorodskii の水深の係数）も比べる。
2 次は Dean & Dalrymple の形 (k a²/4) cosh kh (2 + cosh 2kh) / sinh³ kh で係数を出し直す。
使い方: py -3.10 -B q44_check_newwave_height.py （書き出しはしない。結果は Unity/Build/FLIP42/correct_check_ja.md）
"""
# Independent recheck of linear NewWave H/eta_c (not reusing q44_newwave_height.py).
# Different discretisation: dense trapezoid quadrature in frequency; trough found by
# zero-crossing (crest -> next down-crossing -> next up-crossing, min between).
import math, numpy as np
g = 9.80665
Tp, h, gam = 7.5, 25.0, 3.3
wp = 2*math.pi/Tp

def kdisp(w):
    # fixed-point on k = w^2/(g tanh(kh)), vectorised
    k = w*w/g
    for _ in range(200):
        k = w*w/(g*np.tanh(k*h))
    return k

def spec(w, tma=False):
    s = np.where(w <= wp, 0.07, 0.09)
    S = w**-5*np.exp(-1.25*(wp/w)**4)*gam**np.exp(-(w-wp)**2/(2*s*s*wp*wp))
    if tma:  # Kitaigorodskii depth factor (Thompson & Vincent approx.)
        wh = w*math.sqrt(h/g)
        phi = np.where(wh <= 1, 0.5*wh**2, 1-0.5*(2-wh)**2)
        phi = np.where(wh > 2, 1.0, phi)
        S = S*phi
    return S

def trough_after(s, y):
    i = np.argmax(y < 0)          # first down-crossing
    j = i + np.argmax(y[i:] > 0)  # next up-crossing
    m = i + np.argmin(y[i:j])
    return s[m], y[m]

def ratio(fmax=2.5, fmin=0.5, n=20001, tma=False):
    w = np.linspace(fmin*wp, fmax*wp, n)
    wt = np.full(n, 1.0); wt[0] = wt[-1] = 0.5
    a = spec(w, tma)*wt; a = a/a.sum()   # amplitudes per unit linear crest
    k = kdisp(w)
    t = np.linspace(0, 8, 8001)
    et = np.cos(np.outer(t, w)) @ a
    x = np.linspace(0, 80, 8001)
    ex = np.cos(np.outer(x, k)) @ a
    tt, yt = trough_after(t, et)
    xx, yx = trough_after(x, ex)
    return tt, yt, xx, yx, k, w, a

for tma in (False, True):
    for fmax in (2.0, 2.5, 3.0, 4.0):
        tt, yt, xx, yx, *_ = ratio(fmax, tma=tma)
        print(f"{'TMA ' if tma else 'JONS'} fmax={fmax}: time trough {yt:+.3f} at {tt:.2f}s  H/eta_c={1-yt:.3f} | space trough {yx:+.3f} at {xx:.1f}m H/eta_c={1-yx:.3f}")

# 160-component discretisation as in the report (check same numbers)
tt, yt, xx, yx, k, w, a = ratio(2.5, n=160)
print("n=160 uniform (end weights halved):", round(1-yt,3), round(1-yx,3))

tt, yt, xx, yx, k, w, a = ratio(2.5)
rt, rx = 1-yt, 1-yx
for H in (10., 12.):
    print(f"H={H}: eta_c needed {H/rt:.2f} (time) .. {H/rx:.2f} (space)")
print(f"eta_c=5: H_lin {5*rx:.2f} .. {5*rt:.2f}")
kp = float(kdisp(np.array([wp]))[0]); print("kp", round(kp,4), "Lp", round(2*math.pi/kp,1), "kph", round(kp*h,2))
# Stokes 2nd (Dean & Dalrymple form): eta2 = (k a^2/4) cosh kh (2+cosh 2kh)/sinh^3 kh
C = kp/4*math.cosh(kp*h)*(2+math.cosh(2*kp*h))/math.sinh(kp*h)**3
print("C", round(C,4), "deep", round(kp/2,4))
for r in (rt, rx):
    A = 10/r; tr = -(r-1)*A
    c2 = A + C*A*A; t2 = tr + C*tr*tr
    print(f"A={A:.2f} kpA={kp*A:.3f} crest2={c2:.2f} trough_lin={tr:.2f} trough2={t2:.2f} H2={c2-t2:.2f}")
# component resolution shares (n=160 as in proposal)
w = np.linspace(0.5*wp, 2.5*wp, 160); a = spec(w); a = a/a.sum(); L = 2*math.pi/kdisp(w)
for dp in (0.25, 0.3):
    lg = L/(2*dp)
    print(f"dp={dp}: L/grid peak {2*math.pi/kp/(2*dp):.0f} shortest {lg.min():.0f}; share<150 {a[lg<150].sum():.3f}; share<78 {a[lg<78].sum():.3f}")
# unidirectional kp*eta at 250 m upstream (sigma0 max_over_A 0.681 from mc_proposal_numbers.json)
for A in (5.0, 10/rt, 10/rx):
    print(f"1-dir 250 m: A={A:.2f} kp*eta={kp*A*0.681:.3f}")
