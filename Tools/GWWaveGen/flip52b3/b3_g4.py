# -*- coding: utf-8 -*-
"""FLIP52B3 step 2: where and when the G4 band-steepness gate (kp x (3x3-median hf - eta0) <= 0.40 from t 30 s) is approached or exceeded in the
three 0.5 m runs DFG-2B-E / DFG-S-E140 / DFGB3, and what differs between DFGB3 and DFG-2B-E at DFGB3's hot spot (py -3.10 -B; numpy).
2026-10-18 written new (Claude). Reads hf records and judge jsons (read only); writes Unity/Build/FLIP52B3/diag/g4_3runs.json.
Bands = each run's own frozen G4 rule (read from its judge): D19B runs: inlet x <= 100 m (all y), side y >= 95 m, x <= 180.25 m;
DFG-S-E140: inlet x <= 50 m (all y), side core 110 <= y <= 132.5 m, wall strip y > 132.5 m, x <= 180 m (gated: inlet + core).
Per frame: band maxima and their (x, y); per group cycle (t_fn - 14 .. t_fn + 14 s): the maxima; all frames above 0.38; for DFGB3 vs DFG-2B-E:
the DFG-2B-E value at DFGB3's hot spot and frame, and the harmonic (n 3/4/5, P 28 s, t 69-125 s) amplitudes and phases at the hot spot in both
runs (what the generator phase calibration and the face reflection changed there) [measured].
usage: py -3.10 -B b3_g4.py
"""
import os, sys, json, math, time, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b3_common as B                   # noqa: E402
import numpy as np                      # noqa: E402

EM = B.EM
GA = B.GA52
KP = {"B2E": 0.088136, "B3": 0.088136, "S2E": 0.087313}         # the judges' kp (T 7 at h0) [measured from the judge]
BANDS = {"B2E": dict(inlet_x=100.0, side_y=95.0, side_y1=None, side_x=180.25),
         "B3": dict(inlet_x=100.0, side_y=95.0, side_y1=None, side_x=180.25),
         "S2E": dict(inlet_x=50.0, side_y=110.0, side_y1=132.5, side_x=180.0)}


def scan(key):
    R = B.run_ctx(key); eta0 = R["eta0"]; kp = KP[key]; bd = BANDS[key]
    H = GA.Blocks(R["rd"], "hf", "eta")
    fr = [f for f in H.frames() if (f - 1) / B.FPS >= 30.0 - 1e-9]
    o = dict(f=[], t=[], kin=[], kin_at=[], ksd=[], ksd_at=[], kwall=[], kwall_at=[])
    masks = None
    for f in fr:
        a, meta = H.get(f)
        e = EM.median3(a) - eta0
        if masks is None:
            ny, nx = e.shape
            xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx); yh = float(meta["z0"]) + float(meta["dz"]) * np.arange(ny)
            inl = np.zeros(e.shape, bool); inl[:, xs <= bd["inlet_x"] + 1e-9] = True
            xsd = xs <= bd["side_x"] + 1e-9
            ylo = yh >= bd["side_y"] - 1e-9
            yhi = (yh <= bd["side_y1"] + 1e-9) if bd["side_y1"] else np.ones_like(ylo)
            sd = np.zeros(e.shape, bool); sd[np.ix_(ylo & yhi, xsd)] = True
            wall = np.zeros(e.shape, bool)
            if bd["side_y1"]:
                wall[np.ix_(yh > bd["side_y1"] + 1e-9, xsd)] = True
            masks = (inl, sd, wall, xs, yh)
        inl, sd, wall, xs, yh = masks
        o["f"].append(f); o["t"].append((f - 1) / B.FPS)
        for m, k in ((inl, "kin"), (sd, "ksd"), (wall, "kwall")):
            if not m.any():
                o[k].append(np.nan); o[k + "_at"].append([np.nan, np.nan]); continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                v = np.where(m, e, np.nan)
            j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            o[k].append(float(kp * v[iy, ix])); o[k + "_at"].append([float(xs[ix]), float(yh[iy])])
    for k in ("t", "kin", "ksd", "kwall"):
        o[k] = np.asarray(o[k], float)
    o["fr"] = np.asarray(o["f"])
    return R, o


def summarise(key, R, o):
    tfns = [float(g["t_fn"]) for g in R["J"]["groups"]]
    res = dict(run=key, name=R["name"], kp=KP[key], bands=BANDS[key], judge_G4=R["J"]["gates"]["G4"])
    for k in ("kin", "ksd", "kwall"):
        v = o[k]
        if not np.isfinite(v).any():
            continue
        i = int(np.nanargmax(v))
        tn = min(tfns, key=lambda q: abs(o["t"][i] - q))
        res[k + "_max"] = dict(value=float(v[i]), t=float(o["t"][i]), f=int(o["fr"][i]), at=o[k + "_at"][i], t_rel_fn=float(o["t"][i] - tn))
        cyc = []
        for tn in tfns:
            m = (o["t"] >= tn - 14.0) & (o["t"] < tn + 14.0)
            if m.any() and np.isfinite(v[m]).any():
                j = np.where(m)[0][int(np.nanargmax(v[m]))]
                cyc.append(dict(t_fn=tn, value=float(v[j]), t_rel_fn=float(o["t"][j] - tn), at=o[k + "_at"][j]))
        res[k + "_per_cycle"] = cyc
        hi = np.where(v > 0.38)[0]
        ev = []
        for j in hi:
            if ev and o["fr"][j] - ev[-1]["f_last"] <= 3:
                ev[-1]["f_last"] = int(o["fr"][j])
                if v[j] > ev[-1]["value"]:
                    ev[-1].update(value=float(v[j]), t=float(o["t"][j]), at=o[k + "_at"][j])
            else:
                ev.append(dict(f_first=int(o["fr"][j]), f_last=int(o["fr"][j]), value=float(v[j]), t=float(o["t"][j]), at=o[k + "_at"][j]))
        for q in ev:
            tn = min(tfns, key=lambda z: abs(q["t"] - z)); q["t_rel_fn"] = q["t"] - tn; q["dur_s"] = (q["f_last"] - q["f_first"] + 1) / B.FPS
        res[k + "_events_gt_0p38"] = ev
    return res


def harm_at(R, x, y, t_lo=69.0, t_hi=125.0, P=28.0, ns=(3, 4, 5), tf=63.0):
    H = GA.Blocks(R["rd"], "hf", "eta")
    fr = [f for f in H.frames() if t_lo - 1e-9 <= (f - 1) / B.FPS <= t_hi - 0.5 / B.FPS]
    ts = []; vs = []
    for f in fr:
        a, meta = H.get(f)
        ix = int(round((x - float(meta["x0"])) / float(meta["dx"]))); iy = int(round((y - float(meta["z0"])) / float(meta["dz"])))
        sub = a[iy - 1:iy + 2, ix - 1:ix + 2]
        vs.append(float(np.nanmedian(sub)) - R["eta0"]); ts.append((f - 1) / B.FPS)
    t = np.asarray(ts); v = np.asarray(vs)
    allns = list(ns) + [1, 2, 6, 7, 8, 9, 10]
    cols = [np.ones_like(t)]
    for n in allns:
        w = 2 * math.pi * n / P
        cols += [np.cos(w * (t - tf)), np.sin(w * (t - tf))]
    M = np.stack(cols, 1)
    c, *_ = np.linalg.lstsq(M, v, rcond=None)
    out = {}
    for i, n in enumerate(allns):
        A = complex(c[1 + 2 * i], c[2 + 2 * i])
        out["n%d" % n] = dict(abs=abs(A), phase=float(np.angle(A)))
    out["sum_abs_345"] = sum(out["n%d" % n]["abs"] for n in ns)
    out["max_series"] = float(np.max(v)); out["t_of_max"] = float(t[int(np.argmax(v))])
    return out, t, v


def main():
    t0 = time.time()
    res = {}; raw = {}
    for key in ("B2E", "B3", "S2E"):
        R, o = scan(key)
        raw[key] = (R, o)
        res[key] = summarise(key, R, o)
        print(key, json.dumps({k: v for k, v in res[key].items() if k.endswith("_max")}), round(time.time() - t0, 1), "s", flush=True)
    # DFGB3 vs DFG-2B-E at DFGB3's side-band hot spot
    R3, o3 = raw["B3"]; R2, o2 = raw["B2E"]
    hs = res["B3"]["ksd_max"]; x, y = hs["at"]; f = hs["f"]
    H2 = GA.Blocks(R2["rd"], "hf", "eta"); H3 = GA.Blocks(R3["rd"], "hf", "eta")
    cmp_ = []
    for df in range(-48, 49, 6):
        a2, m2 = H2.get(f + df); a3, m3 = H3.get(f + df)
        if a2 is None or a3 is None:
            continue
        e2 = EM.median3(a2) - R2["eta0"]; e3 = EM.median3(a3) - R3["eta0"]
        ix = int(round(x - float(m2["x0"]))); iy = int(round(y - float(m2["z0"])))
        w2 = e2[iy - 6:iy + 7, ix - 6:ix + 7]; w3 = e3[iy - 6:iy + 7, ix - 6:ix + 7]
        cmp_.append(dict(df=df, t=(f + df - 1) / B.FPS, B3_at=float(KP["B3"] * e3[iy, ix]), B2E_at=float(KP["B2E"] * e2[iy, ix]),
                         B3_max13=float(KP["B3"] * np.nanmax(w3)), B2E_max13=float(KP["B2E"] * np.nanmax(w2)),
                         diff_rms13_m=float(np.sqrt(np.nanmean((e3 - e2)[iy - 6:iy + 7, ix - 6:ix + 7] ** 2)))))
    h3, _, _ = harm_at(R3, x, y); h2, _, _ = harm_at(R2, x, y)
    hs2 = res["B2E"]["ksd_max"]; x2, y2 = hs2["at"]
    h3b, _, _ = harm_at(R3, x2, y2); h2b, _, _ = harm_at(R2, x2, y2)
    res["B3_vs_B2E_hotspot"] = dict(B3_hotspot=hs, frames_around=cmp_, harmonics_B3_hotspot=dict(B3=h3, B2E=h2),
                                    B2E_hotspot=hs2, harmonics_B2E_hotspot=dict(B3=h3b, B2E=h2b),
                                    rule="kp x 3x3-median crest at the hot spot and the max over +-6 m; harmonic fit (mean + n 3/4/5 + nuisance 1, 2, 6-10, "
                                         "P 28 s, t 69-125 s, t' = t - 63 s) of the 3x3 median at the hot spot [measured]")
    res["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(res, B.OUT + "/g4_3runs.json")
    print(json.dumps(res["B3_vs_B2E_hotspot"]["harmonics_B3_hotspot"], default=float)[:1500])
    print(json.dumps(res["B3_vs_B2E_hotspot"]["harmonics_B2E_hotspot"], default=float)[:1500])


if __name__ == "__main__":
    main()
