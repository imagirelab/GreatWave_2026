# -*- coding: utf-8 -*-
"""FLIP50 after DG1: the DG2 model-validity gate (AM-D22, dg2_frozen.json model_validity_gate; numpy only, CPU < 5 s). 2026-10-17 new (Claude).
Registered (sha256 in AM-D22) before any DG1 main-run result. It is read ONLY when the user opts into DG2; it never makes DG2 a default.

The row model (a depth-threshold model; logic copied unchanged from Unity/Build/FLIP50/_scratch/post_dg1/rm_g2.py `run`, which reproduces
_scratch/dg1/dg1_rowmodel.json bit for bit): every DM1A row y that overturned at x_b,y with still depth h_b,y overturns on a groove bed where
the still depth first falls to h_b,y; extra time = extra distance / that breaker's crest speed; curl width at max overturn = 2 x 1 m x the
contiguous rows from y 0.5 whose lag behind the new centre time is <= t_mo. sigma = Gaussian lateral smoothing of dz (stand-in for FLIP's
lateral coupling), scale = effective groove depth factor, hc = Hc factor. Rows: post_dg1/cw_flip_DM1A.json (sha256 frozen in dg2_frozen).

Gate (rule frozen before DG1's result):
  1. predict DG1's per-breaker curl/Hc at max overturn on the DM1A rows for every (sigma, scale, hc) of the grid
     sigma {0, 1, 2, 3, 4.5, 6, 7.5, 9} m x scale {1.0, 0.75} x hc {1.0, 0.96};
  2. error E = median over the breakers judged in BOTH DG1 and DM1A (k02..k05) of |model - DG1 measured curl_w_maxov_over_Hc|; need >= 3;
  3. the fit = the grid point with the smallest E (ties: smaller |median difference|, smaller sigma, larger scale, larger hc);
     the model holds only if E <= 0.5 Hc 【選び】 (else: the model is refuted for FLIP -> no DG2); the CONSISTENT set = every grid point
     with E <= E_min + 0.05 Hc 【選び】 (the data cannot tell them apart);
  4. predict L12, H and L12D4 at every consistent grid point (L12D4 only if DG1's S3 margin H_front / 10.283 - 1 >= 2.5 %); a candidate
     passes only if >= 3 consecutive breakers have curl <= 2.5 Hc at EVERY consistent point; pick the passing candidate with the largest
     predicted S3 margin
     (H_pred = H_DG1 x (1 + dH), dH: L12 0, H +0.011, L12D4 -0.023 from the U3 fit post_dg1/h_u3fit.json 【計算+推測】; ties L12, H, L12D4);
     none passes -> no DG2.
usage: py -3.10 -B g50dg2_gate.py run <DG1 run dir> [--out=<json>]     (default out: _scratch/post_dg1/dg2/gate_dg2.json)
       py -3.10 -B g50dg2_gate.py selftest                             (copied model vs post_dg1/rm_g2.run and dg1_rowmodel.json)
"""
import os, sys, json, time, hashlib
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
B50 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP50"
POST = B50 + "/_scratch/post_dg1"
ROWS_DM1A = POST + "/cw_flip_DM1A.json"
OUT_DEFAULT = POST + "/dg2/gate_dg2.json"
DG1 = dict(D=3.0, b=8.0, Y=25.0, x1=238.0, x2=262.0, x3=320.0, x4=350.0)
CANDS = dict(L12=dict(DG1, x1=250.0, x2=274.0), H=dict(DG1, D=2.5, b=6.0, x1=250.0, x2=274.0), L12D4=dict(DG1, D=4.0, x1=250.0, x2=274.0))
DH = dict(L12=0.0, H=0.011, L12D4=-0.023)          # 【計算+推測】 U3 height fit (h_u3fit.json); extrapolated, inside run noise
ORDER = ("L12", "H", "L12D4")
SIGMAS = (0.0, 1.0, 2.0, 3.0, 4.5, 6.0, 7.5, 9.0)
SCALES = (1.0, 0.75)
HCS = (1.0, 0.96)
E_MAX = 0.5               # 【選び】 median |model - measured| (Hc units)
E_TIE = 0.05              # 【選び】 grid points within E_min + 0.05 Hc are equally consistent with DG1
N_MIN = 3
FLOOR_S3 = 10.283
S3_MARGIN_D4 = 0.025
YY = np.arange(-120.0, 120.0001, 0.125)


# ---------------------------------------------------------------- copied unchanged from post_dg1/rm_g2.py
def S(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def gy(y, g):
    y = np.asarray(y, float)
    return (1.0 - np.exp(-(y / g["b"]) ** 2)) * np.exp(-(y / g["Y"]) ** 2)


def rx(x, g, shift=0.0):
    x = np.asarray(x, float) - shift
    return S((x - g["x1"]) / (g["x2"] - g["x1"])) * (1.0 - S((x - g["x3"]) / (g["x4"] - g["x3"])))


def gy_eff(y, g, sigma):
    if sigma <= 0:
        return gy(y, g)
    w = np.exp(-0.5 * ((YY[None, :] - np.asarray(y, float)[:, None]) / sigma) ** 2)
    w /= w.sum(axis=1, keepdims=True)
    return (gy(YY, g)[None, :] * w).sum(axis=1)


def h_d19b(x):
    return 19.0 - np.maximum(np.asarray(x, float) - 160.25, 0.0) / 10.0


def run(d, cc, g, sigma=0.0, scale=1.0, shift=0.0, hc=1.0):
    out = {}
    for k, w in d["waves"].items():
        rows = sorted(w["C"], key=lambda r: r["y"])
        c = cc[k]
        ys = np.array([r["y"] for r in rows])
        gE = gy_eff(ys, g, sigma)
        dts, xbs = [], []
        for r, ge in zip(rows, gE):
            xs = np.arange(r["x_b"], r["x_b"] + 120.0, 0.25)
            hh = h_d19b(xs) + scale * g["D"] * ge * rx(xs, g, shift=shift)
            ok = hh <= r["h_b"] + 1e-9
            if ok.any():
                xn = float(xs[np.argmax(ok)])
                dts.append(r["dt"] + (xn - r["x_b"]) / c); xbs.append(xn)
            else:
                dts.append(None); xbs.append(None)
        d0 = dts[0]
        cdel = (d0 - rows[0]["dt"]) if d0 is not None else None

        def width(T):
            n = 0
            for v in dts:
                if v is not None and d0 is not None and (v - cdel) <= T + 1e-9:
                    n += 1
                else:
                    break
            return 2.0 * n
        Hc = w["Hc"] * hc
        out[k] = dict(x_on=w["x_on"], Hc=round(Hc, 3), r_at_onset=round(float(rx(w["x_on"], g, shift=shift)), 3),
                      centre_delay_s=None if cdel is None else round(cdel, 2), centre_dx_m=None if xbs[0] is None else round(xbs[0] - rows[0]["x_b"], 2),
                      w_mo_m=width(w["t_mo"]), w_td_m=width(w["t_td"]),
                      mo_Hc=round(width(w["t_mo"]) / Hc, 2), td_Hc=round(width(w["t_td"]) / Hc, 2))
    ks = sorted(out)
    passes = [out[k]["mo_Hc"] <= 2.5 for k in ks]
    best_run = 0; cur = 0
    for p in passes:
        cur = cur + 1 if p else 0
        best_run = max(best_run, cur)
    mo = [out[k]["mo_Hc"] for k in ks]
    return dict(mo_Hc=mo, td_Hc=[out[k]["td_Hc"] for k in ks], mo_m=[out[k]["w_mo_m"] for k in ks],
                centre_delay_s=[out[k]["centre_delay_s"] for k in ks], centre_dx_m=[out[k]["centre_dx_m"] for k in ks],
                r_at_onset=[out[k]["r_at_onset"] for k in ks],
                median_mo_Hc=float(np.median(mo)), n_consecutive_le_2p5=best_run, curl_clause=bool(best_run >= 3), keys=ks)
# ---------------------------------------------------------------- end of the copy (only 'keys' added to the returned dict)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def load_dm1a_rows():
    d = json.load(open(ROWS_DM1A, encoding="utf-8"))
    cc = {k: (w.get("peel") or {}).get("c_crest_mps") for k, w in d["waves"].items()}
    return d, cc


def measured(ana):
    """DG1 judged per-breaker curl/Hc at max overturn, keyed 'k%02d'."""
    ks = set(ana.get("judged_k") or [])
    return {"k%02d" % r["k"]: r.get("curl_w_maxov_over_Hc") for r in ana.get("rows") or [] if r.get("k") in ks}


def gate(ana_dg1, rows=None):
    t0 = time.process_time()
    o = _gate(ana_dg1, rows)
    o["cpu_s"] = round(time.process_time() - t0, 2)
    o["tags"] = "【計算】 row model on measured DM1A FLIP rows; 【選び】 grid, E_MAX, dH from the U3 fit (extrapolated 【推測】)"
    return o


def _gate(ana_dg1, rows=None):
    d, cc = rows or load_dm1a_rows()
    meas = measured(ana_dg1)
    H = (ana_dg1.get("medians_judged") or {}).get("H_front")
    fits = []
    for sg in SIGMAS:
        for sc in SCALES:
            for hc in HCS:
                r = run(d, cc, DG1, sigma=sg, scale=sc, hc=hc)
                pred = dict(zip(r["keys"], r["mo_Hc"]))
                common = [k for k in r["keys"] if meas.get(k) is not None]
                if len(common) < N_MIN:
                    continue
                err = [abs(pred[k] - meas[k]) for k in common]
                E = float(np.median(err))
                dmed = abs(float(np.median([pred[k] for k in common])) - float(np.median([meas[k] for k in common])))
                fits.append(dict(sigma=sg, scale=sc, hc=hc, E=round(E, 3), d_median=round(dmed, 3), n=len(common),
                                 pred={k: pred[k] for k in common}))
    out = dict(rule=__doc__.split("Gate (rule frozen before DG1's result):")[1].split("usage:")[0].strip(), rows_file=ROWS_DM1A,
               rows_sha256=sha256_file(ROWS_DM1A), measured_DG1=meas, H_front_DG1=H, n_fits=len(fits))
    if not fits:
        out.update(ok=False, pick=None, why="fewer than %d breakers judged in both DG1 and DM1A" % N_MIN)
        return out
    fits.sort(key=lambda f: (f["E"], f["d_median"], f["sigma"], -f["scale"], -f["hc"]))
    best = fits[0]
    out["fit"] = best
    out["fits_top5"] = fits[:5]
    if best["E"] > E_MAX:
        out.update(ok=False, pick=None, why="the row model does not reproduce DG1 (best E %.2f Hc > %.2f at sigma %g, scale %g, hc %g): the model is "
                   "refuted for FLIP -> no DG2" % (best["E"], E_MAX, best["sigma"], best["scale"], best["hc"]))
        return out
    margin_dg1 = (H / FLOOR_S3 - 1.0) if H is not None else None
    cons = [f for f in fits if f["E"] <= best["E"] + E_TIE + 1e-12]
    out["consistent"] = [dict(sigma=f["sigma"], scale=f["scale"], hc=f["hc"], E=f["E"]) for f in cons]
    cands = {}
    for v in ORDER:
        per = [run(d, cc, CANDS[v], sigma=f["sigma"], scale=f["scale"], hc=f["hc"]) for f in cons]
        r = per[0]
        allowed = v != "L12D4" or (margin_dg1 is not None and margin_dg1 >= S3_MARGIN_D4)
        hp = H * (1.0 + DH[v]) if H is not None else None
        cands[v] = dict(params=CANDS[v], mo_Hc=r["mo_Hc"], median_mo_Hc=r["median_mo_Hc"], curl_clause=bool(all(x["curl_clause"] for x in per)),
                        curl_clause_at_best_fit=r["curl_clause"], n_consistent_pass=sum(1 for x in per if x["curl_clause"]), n_consistent=len(per),
                        worst_median_mo_Hc=max(x["median_mo_Hc"] for x in per), allowed=allowed,
                        H_pred=hp, S3_margin_pred=(hp / FLOOR_S3 - 1.0) if hp is not None else None, dH=DH[v])
    ok_c = [v for v in ORDER if cands[v]["curl_clause"] and cands[v]["allowed"]]
    out["candidates"] = cands
    out["S3_margin_DG1"] = margin_dg1
    if not ok_c:
        out.update(ok=False, pick=None, why="no allowed candidate passes the curl clause at all %d consistent grid points (best fit sigma %g, "
                   "scale %g, hc %g) -> no DG2" % (len(cons), best["sigma"], best["scale"], best["hc"]))
    else:
        pick = max(ok_c, key=lambda v: (cands[v]["S3_margin_pred"] if cands[v]["S3_margin_pred"] is not None else -9, -ORDER.index(v)))
        out.update(ok=True, pick=pick, why="fit E %.2f Hc at sigma %g, scale %g, hc %g (%d consistent points); passing at all of them %s; pick %s "
                   "(largest predicted S3 margin %+.1f %%)" % (best["E"], best["sigma"], best["scale"], best["hc"], len(cons), ok_c, pick,
                                                              100 * (cands[pick]["S3_margin_pred"] or 0)))
    return out


def selftest():
    sys.path.insert(0, POST)
    import rm_g2 as RM
    d, cc = load_dm1a_rows()
    same = []
    for nm, g in [("DG1", DG1)] + list(CANDS.items()):
        for sg in (0.0, 3.0, 4.5):
            for sc in (1.0, 0.75):
                a = run(d, cc, g, sigma=sg, scale=sc, hc=0.96)
                b = RM.run(d, cc, g, sigma=sg, scale=sc, hc=0.96)
                same.append(a["mo_Hc"] == b["mo_Hc"] and a["td_Hc"] == b["td_Hc"])
    d1, cc1 = RM.load_rows("DM1")
    fz = json.load(open(B50 + "/_scratch/dg1/dg1_rowmodel.json", encoding="utf-8"))["cases"]
    frz = []
    for key in ("sig0.0_sc1.00_sh+0_hc1.00", "sig2.0_sc1.00_sh+0_hc1.00", "sig3.0_sc1.00_sh+0_hc1.00"):
        sg = float(key[3:6])
        frz.append(run(d1, cc1, DG1, sigma=sg)["mo_Hc"] == fz[key]["mo_Hc"])
    return dict(copy_equals_rm_g2=all(same), n=len(same), dm1_rows_equal_dg1_rowmodel=all(frz))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if a and a[0] == "selftest":
        print(json.dumps(selftest()))
    elif len(a) >= 2 and a[0] == "run":
        ana = json.load(open(os.path.join(a[1], "pana", "planD_ana.json"), encoding="utf-8"))
        o = gate(ana)
        o["dg1_run"] = a[1]
        o["date"] = time.strftime("%Y-%m-%d %H:%M:%S")
        outp = ([x.split("=", 1)[1] for x in a if x.startswith("--out=")] or [OUT_DEFAULT])[0]
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        json.dump(o, open(outp, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
        print(json.dumps(dict(ok=o["ok"], pick=o.get("pick"), why=o.get("why"), fit=o.get("fit"), out=outp), ensure_ascii=False, default=float))
    else:
        print(__doc__); sys.exit(1)
