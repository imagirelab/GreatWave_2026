# -*- coding: utf-8 -*-
"""FLIP51 crossing: predicted FLIP metrics for the candidate setups (2026-10-17, Claude; numpy only, py -3.10 -B).
Rule (frozen here before any crossing FLIP run exists):
  * shape = the 2nd-order screen field (c51_screen.Field) at the amplitude whose 2nd-order crest equals the predicted FLIP crest Hc;
  * predicted FLIP crest Hc = f_H x (2nd-order crest at the design a_sum), f_H in {0.77, 0.86, 0.95}: 0.77-0.86 = FLIP45 V1 measured
    (Ac 6.19 m at onset, 6.91 m max) / screen 2nd-order crest of the same Fochesato case (8.00 m); 0.95 = 'crossing breaks later'
    (McAllister et al. 2019: breaking is less crest-limiting at large crossing angles) [guess];
  * lateral widening f_W in {1.0, 1.12, 1.25}: FLIP / screen lateral width at the same Hc (DF1A ~1.0, DM1A ~1.14, V1 ~1.23) [measured/computed];
    applied by stretching the field in y (eta'(x, y) = eta(x, y / f_W)) before e51_metrics.hf_metrics.
Output: Unity/Build/FLIP51/cross/predict.json
"""
import sys, json, math, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip51/cross")
import numpy as np
import c51_screen as C

FH = (0.77, 0.86, 0.95)
FW = (1.0, 1.12, 1.25)
KEYS = ["Hc", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "Lx50", "A50", "target_miss"]


def stretch_metrics(F, s, fw, xwin, tg):
    best = (-1e9, None)
    sel = (F.x >= xwin[0]) & (F.x <= xwin[1])
    for t in tg:
        v = float(F.eta(s, t, 2)[sel].max())
        if v > best[0]:
            best = (v, t)
    e = F.eta(s, best[1], 2)                       # (nx, ny), y >= 0
    y = F.y
    es = np.array([np.interp(y / fw, y, row) for row in e])
    meta = dict(x0=float(F.x[0]), dx=float(F.x[1] - F.x[0]), z0=float(y[0]), dz=float(y[1] - y[0]))
    m = C.EM.hf_metrics(es.T.copy(), meta, 0.0, xwin=xwin)
    m["target_miss"], _ = C.EM.score_vs_target(m)
    return {k: float(m[k]) for k in KEYS if k in m}


def solve_s(F, Hc_goal, xwin, tg, s_hi):
    lo, hi = 0.05 * s_hi, 1.5 * s_hi
    sel = (F.x >= xwin[0]) & (F.x <= xwin[1])
    def crest(s):
        return max(float(F.eta(s, t, 2)[sel].max()) for t in tg)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if crest(mid) < Hc_goal:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def predict(name, T, th, w, x_f, a_sum, bed=C.BED, W=140.0, xr=70.0):
    x = np.arange(0.0, x_f + xr + 1e-9, 1.0); y = np.arange(0.0, W + 1e-9, 1.0)
    F = C.Field(T, th, w, x_f, x, y, bed)
    xwin = (x_f - 60.0, x_f + 35.0); tg = np.linspace(-0.3 * T, 0.3 * T, 49)
    sel = (F.x >= xwin[0]) & (F.x <= xwin[1])
    Hs = max(float(F.eta(a_sum, t, 2)[sel].max()) for t in tg)
    Hl = max(float(F.eta(a_sum, t, 1)[sel].max()) for t in tg)
    c_in, a_band = C.incoming(F, a_sum)
    out = dict(name=name, T=T, n=len(th), theta=[float(v) for v in th], x_f=x_f, h_f=F.hf, k_f=F.kf, L_f=2 * math.pi / F.kf,
               k0=float(F.df.k0), L0=float(2 * math.pi / F.df.k0), a_sum=a_sum, a_j=a_sum / len(th), A_f_lin=a_sum * F.Af_unit,
               eps_lin=F.kf * a_sum * F.Af_unit, Hc_lin=Hl, Hc_2nd=Hs, c_in_x110=c_in, kA_inlet_band_max=float(F.df.k0 * a_band),
               aperture=C.DF.aperture(F.df, W, 45.0, 100.0, 180.25, 210.25)["frac"], grid={})
    for fh in FH:
        Hc = fh * Hs
        s = solve_s(F, Hc, xwin, tg, a_sum)
        for fw in FW:
            out["grid"]["fH%.2f_fW%.2f" % (fh, fw)] = stretch_metrics(F, s, fw, xwin, tg)
    g = out["grid"]
    out["range"] = {k: [min(v[k] for v in g.values() if k in v), max(v[k] for v in g.values() if k in v)] for k in KEYS}
    out["central"] = g["fH0.86_fW1.12"]
    out["gains"] = dict(Hc_central=out["central"]["Hc"], over_component=out["central"]["Hc"] / (a_sum / len(th)),
                        over_incoming_crest_x110=out["central"]["Hc"] / c_in, over_linear_design=out["central"]["Hc"] / Hl)
    return out


def lobes(th0, dl, n):
    th1 = np.linspace(th0 - dl, th0 + dl, n)
    th = np.concatenate([-th1[::-1], th1]); w = np.ones_like(th)
    return th, w / w.sum()


def main():
    t0 = time.time()
    res = []
    A_D = 6.331240146143423            # DM1A a_sum (same input amplitude budget)
    th, w = lobes(60.0, 15.0, 11); res.append(predict("X1_T7_L60d15_xf220", 7.0, th, w, 220.25, A_D))
    th, w = lobes(50.0, 15.0, 11); res.append(predict("X2_T7_L50d15_xf220", 7.0, th, w, 220.25, A_D))
    th, w = lobes(65.0, 15.0, 11); res.append(predict("X3_T7_L65d15_xf220", 7.0, th, w, 220.25, A_D))
    th, w = C.DF.components(80.0, 30, "uniform"); res.append(predict("U7_T7_uniform80_xf220 (period-only control)", 7.0, th, w, 220.25, A_D))
    # validation of the rule on measured runs (shape only: the measured Hc is used, so f_H is not tested here)
    th, w = C.DF.components(80.0, 30, "uniform")
    x = np.arange(0.0, 290.25, 1.0); y = np.arange(0.0, 140.0 + 1e-9, 1.0)
    val = {}
    for nm, T, Hm in (("DF1A_max", 10.0, 7.97), ("DM1A_max", 12.0, 7.83)):
        F = C.Field(T, th, w, 220.25, x, y)
        xwin = (160.25, 255.25); tg = np.linspace(-0.3 * T, 0.3 * T, 49)
        s = solve_s(F, Hm, xwin, tg, 6.4)
        val[nm] = {"fW%.2f" % fw: stretch_metrics(F, s, fw, xwin, tg) for fw in FW}
    th, w = C.DF.components(45.0, 30, "uniform")
    bed = dict(h0=20.0, x_toe=1e9, s=10.0, kind="beach")
    F = C.Field(7.004, th, w, 250.0, np.arange(0.0, 330.0, 1.0), np.arange(0.0, 108.0 + 1e-9, 1.0), bed)
    xwin = (190.0, 285.0); tg = np.linspace(-2.1, 2.1, 43)
    s = solve_s(F, 6.91, xwin, tg, 6.3)
    val["V1_max"] = {"fW%.2f" % fw: stretch_metrics(F, s, fw, xwin, tg) for fw in FW}
    val["measured"] = dict(DF1A_max=dict(W50=6.35, W80=3.5, W95=1.5, K=2.8, S2=0.76, ring_max=0.77, Lx50=2.3, miss=3.3),
                           DM1A_max=dict(W50=9.3, W80=5.7, W95=2.7, K=2.5, S2=0.89, ring_max=0.89, Lx50=2.7, miss=4.9),
                           V1_max=dict(W50=9.19, W80=5.45, W95=1.38, K=2.50, S2=0.90, ring_max=0.98, Lx50=1.85, miss=4.15))
    out = dict(rule=__doc__, setups=res, validation=val, cpu_s=time.time() - t0)
    json.dump(out, open(C.OUT + "/predict.json", "w", encoding="utf8"), indent=1, default=float)
    for r in res:
        print(r["name"], "a_j %.3f A_f %.2f eps %.2f Hc_lin %.2f Hc_2nd %.2f c_in %.2f kAband %.2f ap %.2f L_f %.1f h_f %.1f" % (
            r["a_j"], r["A_f_lin"], r["eps_lin"], r["Hc_lin"], r["Hc_2nd"], r["c_in_x110"], r["kA_inlet_band_max"], r["aperture"], r["L_f"], r["h_f"]))
        c = r["central"]
        print("   central", " ".join("%s %.2f" % (k, c[k]) for k in KEYS if k in c))
        print("   range  ", " ".join("%s %.2f-%.2f" % (k, *r["range"][k]) for k in KEYS))
        print("   gains  ", json.dumps({k: round(v, 2) for k, v in r["gains"].items()}))
    for nm in ("DF1A_max", "DM1A_max", "V1_max"):
        for fw, m in val[nm].items():
            print("val", nm, fw, " ".join("%s %.2f" % (k, m[k]) for k in ("Hc", "W50", "W80", "W95", "K", "S2", "ring_max", "Lx50", "target_miss")))
        print("   measured", val["measured"][nm])
    print("cpu %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
