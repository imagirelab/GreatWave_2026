# -*- coding: utf-8 -*-
"""FLIP52B3 step 3: what the DFGB3 generator phase calibration did to the realised layers along the tank (py -3.10 -B; numpy, scipy).
2026-10-18 written new (Claude). Reads the DFGB3 hf records (read only) and Unity/Build/FLIP52B2/diag/harm_DFGB2E.npz (DFG-2B-E's harmonic maps
and the design's WKB maps on the same grid, read only); writes Unity/Build/FLIP52B3/diag/harm_B3_vs_B2E.json.
Same projection as flip52b2/b2_harm.py (window W2 = t 69-125 s, whole periods, mean + n 3/4/5 + nuisance 1, 2, 6-10, P 28 s, t' = t - 63 s, on the
3x3-median hf - eta0), restricted to x 60-250 m, y <= 95 m. Per n and x: R_reg = sum_y A_fit conj(A_lin) / sum |A_lin|^2 (y <= 95 m) -> |R| and
the arrival delay arg(R) / w (> 0: later than the design) for DFGB3 and DFG-2B-E, and their difference (= the calibration's realised effect
plus the face reflection) [measured].
usage: py -3.10 -B b3_harm.py
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b3_common as B                   # noqa: E402
import numpy as np                      # noqa: E402
from scipy import ndimage as ndi        # noqa: E402

GA = B.GA52
P = 28.0; NS = (3, 4, 5); TF = 63.0
XR = (60.0, 250.0); YMAX = 95.0


def main():
    t0 = time.time()
    Z = np.load(B.REPO + "/Unity/Build/FLIP52B2/diag/harm_DFGB2E.npz")
    X = Z["x"]; Y = Z["y"]
    xsel = np.where((X >= XR[0]) & (X <= XR[1]))[0]; ysel = np.where(Y <= YMAX + 1e-9)[0]
    R = B.run_ctx("B3"); eta0 = R["eta0"]
    H = GA.Blocks(R["rd"], "hf", "eta")
    fr = [f for f in H.frames() if 69.0 - 1e-9 <= (f - 1) / B.FPS <= 125.0 - 0.5 / B.FPS]
    a0, meta = H.get(fr[0])
    xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(a0.shape[1]); ys = float(meta["z0"]) + float(meta["dz"]) * np.arange(a0.shape[0])
    ix = np.array([int(np.argmin(np.abs(xs - v))) for v in X[xsel]]); iy = np.array([int(np.argmin(np.abs(ys - v))) for v in Y[ysel]])
    r0, r1 = iy.min() - 1, iy.max() + 2; c0, c1 = ix.min() - 1, ix.max() + 2
    E = np.empty((len(fr), len(iy), len(ix)), np.float32)
    for i, f in enumerate(fr):
        a, _ = H.get(f)
        sub = ndi.median_filter(np.nan_to_num(a[max(r0, 0):r1, c0:c1], nan=-30.0), size=3, mode="nearest")
        E[i] = sub[np.ix_(iy - max(r0, 0), ix - c0)] - eta0
    t = (np.asarray(fr, float) - 1) / B.FPS
    allns = list(NS) + [1, 2, 6, 7, 8, 9, 10]
    cols = [np.ones_like(t)]
    for n in allns:
        w = 2 * math.pi * n / P
        cols += [np.cos(w * (t - TF)), np.sin(w * (t - TF))]
    M = np.stack(cols, 1)
    C = np.linalg.pinv(M) @ E.reshape(len(t), -1)
    out = dict(run_B3=R["rd"].replace(B.REPO + "/", ""), window_s=[69.0, 125.0], x=X[xsel][::2], date=time.strftime("%Y-%m-%d %H:%M:%S"),
               phi_comp_rad=R["cfg"]["dir"]["phase_comp_rad"], profiles={})
    for k, n in enumerate(NS):
        A3 = (C[1 + 2 * k] + 1j * C[2 + 2 * k]).reshape(len(iy), len(ix))
        A2 = Z["W2_n%d" % n][np.ix_(ysel, xsel)].astype(complex)
        AL = Z["lin_n%d" % n][np.ix_(ysel, xsel)].astype(complex)
        om = 2 * math.pi * n / P
        prof = {}
        for nm, A in (("B3", A3), ("B2E", A2)):
            good = np.isfinite(A)
            num = np.nansum(np.where(good, A * np.conj(AL), 0), 0); den = np.nansum(np.where(good, np.abs(AL) ** 2, 0), 0)
            Rr = num / np.where(den > 0, den, np.nan)
            prof[nm] = dict(R_abs=np.abs(Rr)[::2], delay_s=(np.angle(Rr) / om)[::2],
                            centre_abs=np.abs(A[0])[::2], centre_delay_s=(np.angle(A[0] * np.conj(AL[0])) / om)[::2])
        # B3 / B2E complex ratio over the interior (calibration + reflection)
        num = np.nansum(A3 * np.conj(A2), 0); den = np.nansum(np.abs(A2) ** 2, 0)
        Q = num / np.where(den > 0, den, np.nan)
        prof["B3_over_B2E"] = dict(abs=np.abs(Q)[::2], dphase_rad=np.angle(Q)[::2], dt_s=(np.angle(Q) / om)[::2],
                                   expected_dphase_rad=-float(R["cfg"]["dir"]["phase_comp_rad"][str(n)]))
        out["profiles"]["n%d" % n] = prof
    out["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(out, B.OUT + "/harm_B3_vs_B2E.json")
    xx = out["x"]
    pick = [i for i, v in enumerate(xx) if abs(((v - 0.5) % 20.0)) < 1e-6]
    for n in NS:
        p = out["profiles"]["n%d" % n]
        print("n%d x" % n, [round(float(xx[i])) for i in pick])
        for nm in ("B3", "B2E"):
            print("   %-4s |R| " % nm, [round(float(p[nm]["R_abs"][i]), 2) for i in pick])
            print("   %-4s dly " % nm, [round(float(p[nm]["delay_s"][i]), 2) for i in pick])
        print("   B3/B2E |Q|", [round(float(p["B3_over_B2E"]["abs"][i]), 3) for i in pick])
        print("   B3/B2E dt ", [round(float(p["B3_over_B2E"]["dt_s"][i]), 2) for i in pick], "expected dphase", p["B3_over_B2E"]["expected_dphase_rad"])
    print("cpu", out["cpu_s"])


if __name__ == "__main__":
    main()
