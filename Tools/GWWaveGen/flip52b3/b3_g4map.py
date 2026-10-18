# -*- coding: utf-8 -*-
"""FLIP52B3 step 4: a recalibrated G4 side-band screen (py -3.10 -B; numpy). 2026-10-18 written new (Claude).
The round-2 linear G4 screen (flip52b2/b2_screen2.py, read only, not imported) took the global maximum of the linear target in the side band
(x 160, y 115-116, t_f + 3.3 s) and one FLIP / linear ratio (1.04): it predicted DFGB3 0.396, FLIP gave 0.419 (at x 164-170, y 107-109,
t_fn + 3.8..4.1 s). Here, per cell of the generating side band (y >= 95 m, x <= 180.25 m):
  lin(x, y)  = the largest linear crest of the run's own generator table over one period (3 layers, P 28 s) [computed]
  flip(x, y) = the largest kp x (3x3-median hf - eta0) from t 30 s [measured]
  r(x, y)    = flip / (kp lin), measured on DFG-2B-E; prediction for another table = max over cells of r_B2E x kp x lin_table [calibrated]
Validation: the DFGB3 table with DFG-2B-E's r map vs DFGB3's measured 0.419. Candidates: tables built in memory from DFG-2B-E's table
(inlet-only phase calibration, side-band taper) -> predicted G4 side [calibrated].
Reads hf records and the two generator tables (read only); writes Unity/Build/FLIP52B3/diag/g4map.json and _scratch/g4map.npz.
usage: py -3.10 -B b3_g4map.py
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b3_common as B                   # noqa: E402
import numpy as np                      # noqa: E402

EM = B.EM
GA = B.GA52
KP = 0.088136
TAB = {"B2E": B.REPO + "/Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz",
       "B3": B.REPO + "/Unity/Build/FLIP52B2/tables/DFGB3_P28_xf272p25_W140_626e71de5aab.npz"}
YS = np.arange(95, 140); XS = np.arange(0, 180)          # x <= 179.5 (G4 x <= 180.25); table integer nodes; hf cell centres at +0.5
P = 28.0


def flip_max(key):
    R = B.run_ctx(key); H = GA.Blocks(R["rd"], "hf", "eta")
    fr = [f for f in H.frames() if (f - 1) / B.FPS >= 30.0 - 1e-9]
    M = np.full((len(YS), len(XS)), -9.0); Tm = np.zeros_like(M)
    for f in fr:
        a, meta = H.get(f)
        sub = a[90:141, 0:186]
        e = EM.median3(sub)[5:5 + len(YS), 0:len(XS)] - R["eta0"]
        up = e > M
        M[up] = e[up]; Tm[up] = (f - 1) / B.FPS
    return M, Tm


def lin_max(layers):
    """layers: list of 3 complex (len(YS), len(XS)) maps at the hf cell centres; largest crest over one period."""
    tt = np.linspace(0.0, P, 673)
    M = np.full(layers[0].shape, -9.0); Tm = np.zeros_like(M)
    for t in tt:
        e = sum(np.real(A * np.exp(-1j * 2 * math.pi * (3 + k) / P * t)) for k, A in enumerate(layers))
        up = e > M
        M[up] = e[up]; Tm[up] = t
    return M, Tm


def table_layers(path, phase=None, gain=None):
    T = np.load(path)
    out = []
    for n in range(3):
        A = T["er%d" % n] + 1j * T["ei%d" % n]
        c = 0.25 * (A[YS[0]:YS[-1] + 1, XS[0]:XS[-1] + 1] + A[YS[0]:YS[-1] + 1, XS[0] + 1:XS[-1] + 2]
                    + A[YS[0] + 1:YS[-1] + 2, XS[0]:XS[-1] + 1] + A[YS[0] + 1:YS[-1] + 2, XS[0] + 1:XS[-1] + 2])   # hf cell centres
        if phase is not None:
            c = c * np.exp(-1j * phase[n])
        if gain is not None:
            c = c * gain
        out.append(c)
    return out


def main():
    t0 = time.time()
    F2, T2 = flip_max("B2E"); print("flip B2E", round(time.time() - t0, 1), flush=True)
    F3, T3 = flip_max("B3"); print("flip B3", round(time.time() - t0, 1), flush=True)
    L2, _ = lin_max(table_layers(TAB["B2E"])); L3, _ = lin_max(table_layers(TAB["B3"]))
    r = (KP * F2) / np.maximum(KP * L2, 1e-6)
    ok = L2 > 1.0
    pred3 = np.where(ok, r * KP * L3, np.nan)

    def amax(a):
        j = int(np.nanargmax(a)); iy, ix = np.unravel_index(j, a.shape)
        return dict(value=float(a[iy, ix]), x=float(XS[ix] + 0.5), y=float(YS[iy] + 0.5))
    res = dict(rule="r(x, y) = FLIP max / linear-table max per side-band cell, measured on DFG-2B-E; predicted G4 side = max over cells of "
                    "r_B2E x kp x lin_table (cells with lin > 1 m) [calibrated]",
               B2E_flip=amax(KP * F2), B3_flip=amax(KP * F3), B2E_lin=amax(KP * L2), B3_lin=amax(KP * L3),
               B3_predicted_with_r_B2E=amax(pred3),
               r_at_B2E_flip_max=None, r_stats=dict(median=float(np.nanmedian(r[ok])), p90=float(np.nanpercentile(r[ok], 90)), max=float(np.nanmax(r[ok]))))
    m = res["B2E_flip"]; iy = int(m["y"] - 0.5 - YS[0]); ix = int(m["x"] - 0.5)
    res["r_at_B2E_flip_max"] = float(r[iy, ix])
    # candidates on DFG-2B-E's (design) table
    phi_g2f = np.array([-0.060788, 0.279111, 0.513994])
    cands = {}
    cands["design_uncalibrated (= DFG-2B-E side band)"] = table_layers(TAB["B2E"])
    cands["G2f phase on the side band (= DFGB3)"] = table_layers(TAB["B2E"], phase=phi_g2f)
    for half in (0.5,):
        cands["half G2f phase on the side band"] = table_layers(TAB["B2E"], phase=half * phi_g2f)
    # side-band amplitude taper near the hot spot (y 95-115, x 150-180): gain 1 - d * w(x, y)
    yy, xx = np.meshgrid(YS + 0.5, XS + 0.5, indexing="ij")
    for d in (0.03, 0.05):
        w = np.clip((xx - 140.0) / 20.0, 0, 1) * np.clip((125.0 - yy) / 20.0, 0, 1)
        cands["design + taper %.0f %% (x 140-180, y 95-125)" % (100 * d)] = table_layers(TAB["B2E"], gain=1.0 - d * w)
    cres = {}
    for nm, lay in cands.items():
        L, _ = lin_max(lay)
        pr = np.where(ok, r * KP * L, np.nan)
        cres[nm] = dict(pred=amax(pr), lin=amax(KP * L))
        print(nm, cres[nm], flush=True)
    res["candidates"] = cres
    res["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(res, B.OUT + "/g4map.json")
    np.savez_compressed(B.SCR + "/g4map.npz", F2=F2, F3=F3, L2=L2, L3=L3, r=r, T2=T2, T3=T3, xs=XS + 0.5, ys=YS + 0.5)
    print(json.dumps({k: v for k, v in res.items() if k != "candidates"}, default=float))


if __name__ == "__main__":
    main()
