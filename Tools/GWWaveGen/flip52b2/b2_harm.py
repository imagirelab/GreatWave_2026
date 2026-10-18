# -*- coding: utf-8 -*-
"""FLIP52B2 diagnosis step 1: per-frequency harmonic maps of the DFG-2B-E 0.5 m run against the linear WKB design (py -3.10 -B).
2026-10-18 written new (Claude). Reads the run's hf records (read only); writes Unity/Build/FLIP52B2/diag/harm_DFGB2E.npz and .json.

What it measures
  G2f       the frozen G2f fit repeated per gauge (x 110 m, y 0.5/20/40/60/80 m, t 49-105 s, P 28 s, harmonics 3/4/5, nuisance 6-10,
            3x3-median hf - eta0) against the cfg linear references: R_n, phase error per gauge and summed (= judge G2f) [measured]
  maps      the same least-squares projection at EVERY hf cell (x 0.5-340.5 m, y 0.5-139.5 m) over the windows W1 = 49-105 s (= G2f),
            W2 = 69-125 s (the periodic state on the beach) and the single periods 49-77 / 77-105 / 97-125 s (stationarity), nuisance
            harmonics 1, 2, 6-10 (orthogonal on whole periods) [measured]
  linear    the design's WKB DirField per harmonic on the same cells (= the g52b_table field, all 34 directions, phases 0 at (272.25, 0),
            t_f 63 s) [computed]; table cross-check at x <= 214 m
  ratios    per harmonic n and x: the complex regression R_n(x) = sum_y A_fit conj(A_lin) / sum_y |A_lin|^2 over y <= 95 m (the interior),
            the centre-row ratio A_fit / A_lin at y 0.5 m, and the arrival delay dt_n = arg(R_n) / w_n (> 0: FLIP later than the design)
usage: py -3.10 -B b2_harm.py
Tags: [measured] [computed].
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b2_common as B                   # noqa: E402  (sets the thread caps before numpy)
import numpy as np                      # noqa: E402

GY = [0.5, 20.0, 40.0, 60.0, 80.0]
WINDOWS = {"W1": (49.0, 105.0), "W2": (69.0, 125.0), "P1": (49.0, 77.0), "P2": (77.0, 105.0), "P3": (97.0, 125.0)}
XMAX = 340.5


def g2f_per_gauge(t, E, xs, ys, eta0, c, sea):
    """the frozen G2f (x 110 m) per gauge; E: 3x3-median frames (nt, ny, nx) absolute."""
    lin = c["dir"]["linear_refs"]["G2f_gauges"]["A_n"]
    sel = (t >= 49.0 - 1e-9) & (t <= 105.0 + 1e-9)
    i0 = int(np.searchsorted(xs, 110.0) - 1); wx = (110.0 - xs[i0]) / (xs[i0 + 1] - xs[i0])
    out = {}
    fits = []
    for yg in GY:
        j0 = int(np.clip(np.searchsorted(ys, yg) - 1, 0, len(ys) - 2)); wy = float(np.clip((yg - ys[j0]) / (ys[j0 + 1] - ys[j0]), 0.0, 1.0))
        e = ((1 - wx) * (1 - wy) * E[:, j0, i0] + wx * (1 - wy) * E[:, j0, i0 + 1] + (1 - wx) * wy * E[:, j0 + 1, i0] + wx * wy * E[:, j0 + 1, i0 + 1])
        fits.append(B.GA52.harmonic_fit(t[sel], e[sel].astype(float) - eta0, P=sea["P"], ns=sea["ns"], nuisance=(6, 10), tf=sea["t_f"]))
    for n, om in zip(sea["ns"], sea["om"]):
        Af = [f["A"][n] for f in fits]
        Al = [complex(*lin["y%g" % yg]["n%d" % n]) for yg in GY]
        R = sum(abs(a) for a in Af) / sum(abs(a) for a in Al)
        ph = float(np.angle(sum(a * np.conj(b) for a, b in zip(Af, Al))))
        out["n%d" % n] = dict(R=R, phase_err_rad=ph, delay_s=ph / om,
                              per_gauge=[dict(y=yg, fit_abs=abs(a), lin_abs=abs(b), ratio=abs(a) / abs(b), phase_err=float(np.angle(a * np.conj(b))),
                                              delay_s=float(np.angle(a * np.conj(b))) / om, weight_in_sum=abs(a) * abs(b))
                                         for yg, a, b in zip(GY, Af, Al)])
    return out


def main():
    t0 = time.time()
    c = B.cfg(); sea = B.sea_of(c)
    J = B.jload(B.JUDGE)
    eta0 = float(J["eta0"])
    f_lo = int(round(49.0 * B.FPS)) + 1; f_hi = int(round(125.0 * B.FPS)) + 1
    t, E, meta, fr = B.load_frames(f_lo, f_hi, med3=True)
    ny, nx = E.shape[1], E.shape[2]
    xs, ys = B.axes(meta, ny, nx)
    print("loaded", E.shape, round(time.time() - t0, 1), "s", flush=True)
    res = dict(run=B.RUN.replace(B.REPO + "/", ""), eta0=eta0, sea=dict(a_sum=sea["a_sum"], x_f=sea["x_f"], t_f=sea["t_f"], T=sea["T"]),
               date=time.strftime("%Y-%m-%d %H:%M:%S"))
    res["G2f_per_gauge"] = g2f_per_gauge(t, E, xs, ys, eta0, c, sea)
    res["G2f_judge"] = J["G2f"]["per_n"]
    # ---- maps
    xc = np.where(xs <= XMAX + 1e-9)[0]
    X = xs[xc]
    D = E[:, :, xc].reshape(len(t), -1) - np.float32(eta0)
    good = np.all(np.isfinite(D) & (D > -25.0), axis=0)
    maps = {}
    for nm, (a, b) in WINDOWS.items():
        sel = (t >= a - 1e-9) & (t <= b - 0.5 / B.FPS)        # whole periods (end frame excluded) -> exactly orthogonal harmonics
        M, allns = B.design_matrix(t[sel], sea["P"], sea["ns"], sea["t_f"])
        Pm = np.linalg.pinv(M).astype(np.float32)
        C = Pm @ D[sel]
        A = {}
        for i, n in enumerate(allns):
            Z = (C[1 + 2 * i] + 1j * C[2 + 2 * i]).reshape(ny, len(xc))
            Z[~good.reshape(ny, len(xc))] = np.nan
            A[n] = Z
        resid = D[sel] - M.astype(np.float32) @ C
        maps[nm] = dict(A=A, mean=C[0].reshape(ny, len(xc)), rms_res=np.sqrt(np.mean(resid ** 2, 0)).reshape(ny, len(xc)), nt=int(sel.sum()))
        print("window", nm, int(sel.sum()), "frames", round(time.time() - t0, 1), "s", flush=True)
    del D
    # ---- linear maps (WKB DirField, all directions)
    AL, dfs = B.lin_maps(X, ys, sea)
    # table cross-check (x <= 214 m: bilinear at the hf cell centres)
    tab = np.load(c["dir"]["npz"])
    chk = []
    for n in range(3):
        T = tab["er%d" % n] + 1j * tab["ei%d" % n]               # (141, 215) on y 0..140, x 0..214
        for (xq, yq) in ((110.5, 0.5), (150.5, 40.5), (200.5, 80.5), (60.5, 120.5)):
            i = int(xq); j = int(yq)
            v = 0.25 * (T[j, i] + T[j, i + 1] + T[j + 1, i] + T[j + 1, i + 1])
            ix = int(np.argmin(np.abs(X - xq))); iy = int(np.argmin(np.abs(ys - yq)))
            chk.append(dict(n=sea["ns"][n], x=xq, y=yq, table=complex(v), wkb=complex(AL[n][iy, ix]), rel=float(abs(v - AL[n][iy, ix]) / max(abs(v), 1e-6))))
    res["table_check"] = dict(points=chk, max_rel=max(q["rel"] for q in chk),
                              note="table = the same DirField sampled on the integer grid; the 4-point average at the half cell differs by the 2nd difference")
    # ---- ratio profiles
    yin = ys <= B.INTERIOR_Y + 1e-9
    prof = {}
    for nm, mp in maps.items():
        pr = dict(x=X[::2])
        for k, n in enumerate(sea["ns"]):
            Af = mp["A"][n]; Al = AL[k]
            num = np.nansum((Af * np.conj(Al))[yin], 0); den = np.nansum((np.abs(Al) ** 2)[yin], 0)
            Rr = num / np.where(den > 0, den, np.nan)
            g2 = np.nansum(np.abs(Af)[yin], 0) / np.nansum(np.abs(Al)[yin], 0)
            Rc = Af[0] / Al[0]
            om = sea["om"][k]
            pr["n%d" % n] = dict(R_reg_abs=np.abs(Rr)[::2], R_reg_phase=np.angle(Rr)[::2], delay_reg_s=(np.angle(Rr) / om)[::2],
                                 R_sum=g2[::2], centre_fit_abs=np.abs(Af[0])[::2], centre_lin_abs=np.abs(Al[0])[::2],
                                 centre_ratio=np.abs(Rc)[::2], centre_phase=np.angle(Rc)[::2], centre_delay_s=(np.angle(Rc) / om)[::2],
                                 centre_fit_phase=np.angle(Af[0])[::2], centre_lin_phase=np.angle(Al[0])[::2])
        pr["mean_centre"] = mp["mean"][0][::2]
        pr["rms_res_centre"] = mp["rms_res"][0][::2]
        prof[nm] = pr
    res["profiles"] = prof
    res["rule"] = ("A_fit: least squares over whole periods of the window, columns 1, cos/sin of harmonics 3/4/5 and nuisance 1, 2, 6-10 "
                   "(P 28 s, t' = t - 63 s), on the 3x3-median hf - eta0; A_lin: WKB DirField per harmonic (all 34 directions); R_reg = "
                   "sum_y<=95 A_fit conj(A_lin) / sum |A_lin|^2; delay = arg / w (> 0: FLIP later) [measured / computed]")
    res["cpu_s"] = round(time.time() - t0, 1)
    np.savez_compressed(B.OUT + "/harm_DFGB2E.npz", x=X, y=ys, ns=np.array(sea["ns"]), om=np.array(sea["om"]),
                        **{"lin_n%d" % n: AL[k].astype(np.complex64) for k, n in enumerate(sea["ns"])},
                        **{"%s_n%d" % (w, n): maps[w]["A"][n].astype(np.complex64) for w in maps for n in list(sea["ns"]) + [1, 2, 6, 7, 8]},
                        **{"%s_mean" % w: maps[w]["mean"].astype(np.float32) for w in maps},
                        **{"%s_rms" % w: maps[w]["rms_res"].astype(np.float32) for w in maps})
    B.jdump(res, B.OUT + "/harm_DFGB2E.json")
    g = res["G2f_per_gauge"]
    print(json.dumps({k: dict(R=round(v["R"], 3), ph=round(v["phase_err_rad"], 3), per=[(q["y"], round(q["ratio"], 2), round(q["phase_err"], 2))
                                                                                       for q in v["per_gauge"]]) for k, v in g.items()}))
    print("table max rel", round(res["table_check"]["max_rel"], 4), "cpu", res["cpu_s"])


if __name__ == "__main__":
    main()
