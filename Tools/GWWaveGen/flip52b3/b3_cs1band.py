# -*- coding: utf-8 -*-
"""FLIP52B3 step 5: CS1 checked against DFGB3 and extended to a BAND-SPECIFIC generator phase calibration (py -3.10 -B; numpy).
2026-10-18 written new (Claude). Imports READ ONLY flip52b2/b2_calscreen (CS1: sources_2d, comp_maps, field_fun, conv_of, summit_track) and
reads diag/cs1_model.json (CS1 calibrated on DFG-2B-E); writes Unity/Build/FLIP52B3/diag/cs1band.json.
CS1 per layer n: A_n = (e_in,n exp(-i p_in,n) sum_j Fin_j C_j + e_sd,n exp(-i p_sd,n) sum_j Fsd_j C_j) exp(-a_n (x - 100)).
  DFGB3 as run: p_in = p_sd = phi_G2f = (-0.061, 0.279, 0.514) rad (one factor on the whole table).
  band-specific: p_in = arg(e_in) (the inlet band's own measured lag), p_sd = 0 (the side band is realised on time: measured at the G4
  hot spot, DFG-2B-E realised - table phase n3 -0.17, n4 -0.01, n5 -0.05 rad) [calibrated].
Outputs per variant: G2f (R_n, phase error vs the cfg design reference at x 110 m, the 5 gauges), the regression delay vs the design over
y <= 95 m at x 150-240 m (the alignment of the 3 layers where the crest converges), the CS1 converged crest (kappa x crest, depth saturation)
and its x / t. Validation rows: DFG-2B-E and DFGB3 measured G2f and delays (judges, diag/harm_B3_vs_B2E.json).
usage: py -3.10 -B b3_cs1band.py
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
B2DIR = os.path.join(os.path.dirname(HERE), "flip52b2")
for p in (HERE, B2DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
import b3_common as B3                  # noqa: E402
import b2_calscreen as CS               # noqa: E402  read only (CS1)
import numpy as np                      # noqa: E402

BC = CS.B                               # b2_common (DFG-2B-E run, 1:10 bed) read only
X = CS.X; Y = CS.Y; NY = CS.NY
GY = [0.5, 20.0, 40.0, 60.0, 80.0]


def band_maps(sea, lay, eff, p_in, p_sd):
    srcs, dfs, xg = CS.sources_2d(sea, sea["x_f"], lay)
    Cs = CS.comp_maps(dfs, xg)
    out = []
    for k, ((Fin, Fsd), C) in enumerate(zip(srcs, Cs)):
        e = eff[k]
        g = np.exp(-e["damp_per_m"] * np.maximum(X - lay["x_in"], 0.0))[None, :]
        A = (e["e_in"] * np.exp(-1j * p_in[k]) * np.sum(Fin * C, 0) + e["e_sd"] * np.exp(-1j * p_sd[k]) * np.sum(Fsd * C, 0)) * g
        out.append(A)
    return out


def g2f(maps, ref):
    i0 = int(np.searchsorted(X, 110.0) - 1); wx = (110.0 - X[i0]) / (X[i0 + 1] - X[i0])
    res = {}
    for k, n in enumerate((3, 4, 5)):
        Af = []; Al = []
        for yg in GY:
            j0 = int(np.clip(np.searchsorted(Y, yg) - 1, 0, NY - 2)); wy = float(np.clip((yg - Y[j0]) / (Y[j0 + 1] - Y[j0]), 0, 1))
            A = maps[k]
            v = ((1 - wx) * (1 - wy) * A[j0, i0] + wx * (1 - wy) * A[j0, i0 + 1] + (1 - wx) * wy * A[j0 + 1, i0] + wx * wy * A[j0 + 1, i0 + 1])
            Af.append(v); Al.append(complex(*ref["y%g" % yg]["n%d" % n]))
        res["n%d" % n] = dict(R=sum(abs(a) for a in Af) / sum(abs(b) for b in Al), phase_err_rad=float(np.angle(sum(a * np.conj(b) for a, b in zip(Af, Al)))))
    return res


def delays(maps, lin, oms, xs=(150.5, 170.5, 190.5, 200.5, 210.5, 220.5, 230.5, 240.5)):
    out = {}
    for k, n in enumerate((3, 4, 5)):
        num = np.nansum(maps[k] * np.conj(lin[k]), 0); den = np.nansum(np.abs(lin[k]) ** 2, 0)
        Rr = num / np.where(den > 0, den, np.nan)
        out["n%d" % n] = {("x%d" % int(x)): round(float(np.angle(Rr[int(np.argmin(np.abs(X - x)))]) / oms[k]), 3) for x in xs}
    return out


def converge(maps, oms, cs1):
    f = CS.field_fun(maps, oms)
    cv = CS.conv_of(f, (-14.0, 8.0))
    trk = CS.summit_track(f, cv["t_rel"], cv["x"], -6.0, 4.0, with_widths=False)
    k = cs1["kappa"]; gs = cs1["gamma_s"]
    dx0 = float(np.median(cs1["measured"]["conv_x"])) - cs1["model_conv"]["x"]
    dt0 = float(np.median(cs1["measured"]["conv_t_rel_fn"])) - cs1["model_conv"]["t_rel"]
    sat = None; peak = None
    for r in trk:
        xF = r["x"] + dx0; hF = float(BC.h_of(xF)); HF = k * r["crest"]
        r.update(x_FLIP=xF, h_FLIP=hF, Hc_FLIP=HF, t_FLIP=r["tp"] + dt0)
        if sat is None and HF >= gs * hF:
            sat = r
        if peak is None or HF > peak["Hc_FLIP"]:
            peak = r
    c = sat if (sat is not None and sat["t_rel"] <= peak["t_rel"]) else peak
    return dict(model_crest=cv["crest"], model_x=cv["x"], model_t_rel=cv["t_rel"], conv_x=c["x_FLIP"], conv_t_rel_fn=c["t_FLIP"],
                conv_Hc=min(k * c["crest"], gs * c["h_FLIP"]), saturated=bool(c is sat), unsat_peak_Hc=peak["Hc_FLIP"], unsat_peak_x=peak["x_FLIP"],
                track=[dict(t=round(r["t_FLIP"], 3), x=r["x_FLIP"], Hc=round(r["Hc_FLIP"], 3)) for r in trk[::6]])


def main():
    t0 = time.time()
    cs1 = BC.jload(BC.OUT + "/cs1_model.json")
    sea = BC.sea_of(); oms = [2 * math.pi / T for T in sea["T"]]
    eff = [dict(e_in=complex(*e["e_in"]), e_sd=complex(*e["e_sd"]), damp_per_m=e["damp_per_m"]) for e in cs1["eff"]]
    ref = BC.cfg()["dir"]["linear_refs"]["G2f_gauges"]["A_n"]
    lin = CS.lin_maps(sea, sea["x_f"])
    phi = np.array([-0.060788, 0.279111, 0.513994])
    arg_in = np.array([float(np.angle(e["e_in"])) for e in eff]); arg_sd = np.array([float(np.angle(e["e_sd"])) for e in eff])
    V = {"none (= DFG-2B-E)": (np.zeros(3), np.zeros(3)),
         "phi_G2f on both bands (= DFGB3)": (phi, phi),
         "inlet only: arg(e_in)": (arg_in, np.zeros(3)),
         "inlet only: phi_G2f": (phi, np.zeros(3)),
         "both bands to design: arg(e_in), arg(e_sd)": (arg_in, arg_sd)}
    res = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), arg_e_in=arg_in, arg_e_sd=arg_sd, phi_G2f=phi, variants={})
    for nm, (pi, ps) in V.items():
        maps = band_maps(sea, CS.LAY_D, eff, pi, ps)
        r = dict(p_in=pi, p_sd=ps, G2f=g2f(maps, ref), delay_vs_design_s=delays(maps, lin, oms), converged=converge(maps, oms, cs1))
        r["G2f_pass_phase_0p35"] = bool(all(abs(v["phase_err_rad"]) <= 0.35 for v in r["G2f"].values()))
        res["variants"][nm] = r
        print(nm, json.dumps(dict(G2f={k: (round(v["R"], 3), round(v["phase_err_rad"], 3)) for k, v in r["G2f"].items()},
                                  conv={k: (round(v, 2) if isinstance(v, float) else v) for k, v in r["converged"].items() if k != "track"},
                                  dly={k: [v["x200"], v["x210"], v["x220"], v["x230"]] for k, v in r["delay_vs_design_s"].items()})), flush=True)
    # measured rows for validation
    JB2 = B3.jload(B3.RUNS["B2E"]["rd"] + "/" + B3.RUNS["B2E"]["judge"]); JB3 = B3.jload(B3.RUNS["B3"]["rd"] + "/" + B3.RUNS["B3"]["judge"])
    HB = B3.jload(B3.OUT + "/harm_B3_vs_B2E.json")
    xx = HB["x"]

    def mdel(run):
        out = {}
        for n in (3, 4, 5):
            p = HB["profiles"]["n%d" % n][run]
            out["n%d" % n] = {("x%d" % int(x)): round(float(p["delay_s"][int(np.argmin(np.abs(np.array(xx) - x)))]), 3) for x in (150.5, 170.5, 190.5, 200.5, 210.5, 220.5, 230.5, 240.5)}
        return out
    res["measured"] = {"DFG-2B-E": dict(G2f={k: dict(R=v["R"], phase_err_rad=v["phase_err_rad"]) for k, v in JB2["gates"]["G2f"]["per_n"].items()},
                                       delay_vs_design_s=mdel("B2E"), conv=[g["conv"] for g in JB2["groups"]]),
                       "DFGB3": dict(G2f={k: dict(R=v["R"], phase_err_rad=v["phase_err_rad"]) for k, v in JB3["gates"]["G2f"]["per_n"].items()},
                                     delay_vs_design_s=mdel("B3"), conv=[g["conv"] for g in JB3["groups"]])}
    res["cpu_s"] = round(time.time() - t0, 1)
    B3.jdump(res, B3.OUT + "/cs1band.json")
    for k, v in res["measured"].items():
        print("measured", k, json.dumps(dict(G2f={q: (round(w["R"], 3), round(w["phase_err_rad"], 3)) for q, w in v["G2f"].items()},
                                             dly={q: [w["x200"], w["x210"], w["x220"], w["x230"]] for q, w in v["delay_vs_design_s"].items()})))
    print("cpu", res["cpu_s"])


if __name__ == "__main__":
    main()
