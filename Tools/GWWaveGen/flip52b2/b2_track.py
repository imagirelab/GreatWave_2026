# -*- coding: utf-8 -*-
"""FLIP52B2 diagnosis step 3: the converged crest followed frame by frame from 3 s before the judge's converged instant to 2 s after the
most print-like instant, per group of the DFG-2B-E 0.5 m run (py -3.10 -B; numpy, scipy). 2026-10-18 written new (Claude).
Reads the run's hf / r2 records, judge_DFGB.json and the pv53 json (read only); writes diag/track_DFGB2E.json.

Per frame (24 fps) on the tracked crest:
  summit    the largest 3x3-median hf - eta0 in a moving window x [x_prev - 3, x_prev + 4] m (forward; mirrored backward), |y| <= 25 m
            -> Hc, x_pk, y_pk; local still depth h(x_pk) (1:10 from x 160.25 m) and Hc / h [measured]
  e51       the frozen ruler hf_metrics on the frame (rows y > 95 m NaN) with xwin = x_pk +- 15 m (this crest only): W20/50/80/95, S2, K,
            core miss; W50_m = W50 x Hc = the lateral width at half height in metres [measured]
  centre    the centre-row (y 0.5 m) crest near x_pk: eta_c0, x_c0; crest speed c = d x_c0 / dt (least-squares slope over +-0.5 s) [measured]
  r2        the centre section: the frozen section_metrics (face_deg, back_deg, overhang, Hs) at x_c0; the overturning-lip test of AM-DFG1 in
            x_c0 +- 20 m; the horizontal particle velocity at the crest u_s = the largest x velocity in the two top water cells of the
            columns x_c0 +- 2 m; the kinematic breaking-onset parameter B = u_s / c (Barthelemy et al. 2018, Derakhti et al. 2020:
            onset at B ~ 0.85 [literature]; FLIP's 1 m grid smooths u_s, so B is a lower bound [guess])
  pv53      the pv53 series of the same frame (score3, lip, section crest x_c) [measured, pv53 json]
Per group: the four instants converged (judge) / kinematic onset (first B >= 0.85) / r2 lip onset (judge) / most print-like (pv53 best),
their t, x, Hc, h, Hc/h, W50, W50_m, miss, lip, back; the crest's decay and lateral spreading rates between converged and print-like.
usage: py -3.10 -B b2_track.py
Tags: [measured] [computed] [literature] [guess].
"""
import os, sys, json, math, time, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b2_common as B                   # noqa: E402
import numpy as np                      # noqa: E402

EM = B.EM
GA = B.GA52
B_TH = 0.85
YMAX_TRACK = 25.0


def masked(a, meta):
    _, yh = B.axes(meta, a.shape[0], a.shape[1])
    b = a.copy(); b[yh > B.INTERIOR_Y + 1e-9, :] = np.nan
    return b


def sub_peak(v, i):
    if 0 < i < len(v) - 1 and np.all(np.isfinite(v[i - 1:i + 2])):
        d = v[i - 1] - 2 * v[i] + v[i + 1]
        if d < 0:
            return float(np.clip(0.5 * (v[i - 1] - v[i + 1]) / d, -0.5, 0.5))
    return 0.0


def r2_crest(sdf, u, meta, eta0, x_c):
    """top surface per column and the crest particle velocity near x_c on the centre section."""
    nz, nx = sdf.shape
    x = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
    zs = float(meta["y0"]) + float(meta["dy"]) * np.arange(nz) - eta0
    neg = sdf < 0
    has = neg.any(0)
    jtop = np.where(has, nz - 1 - np.argmax(neg[::-1], axis=0), -1)
    cols = np.where((x >= x_c - 2.0) & (x <= x_c + 2.0) & has)[0]
    us = []
    for i in cols:
        j = int(jtop[i])
        for jj in (j, j - 1):
            if jj >= 0 and neg[jj, i]:
                us.append(0.5 * (float(u[jj, i]) + float(u[jj, i + 1])))   # u on the two x faces of cell i
    return (max(us) if us else float("nan")), x, zs


def main():
    t0 = time.time()
    J = B.jload(B.JUDGE); PV = B.jload(B.PV53)
    eta0 = float(J["eta0"])
    H = GA.Blocks(B.RUN, "hf", "eta"); RS = GA.Blocks(B.RUN, "r2", "sdf"); RU = GA.Blocks(B.RUN, "r2", "u")
    pvp = {int(p["n"]): p for p in PV["periods"]}
    pvs = {int(k): {int(r["frame"]): r for r in v} for k, v in PV["series"].items()}
    out = dict(run=B.RUN.replace(B.REPO + "/", ""), eta0=eta0, B_threshold=B_TH, date=time.strftime("%Y-%m-%d %H:%M:%S"), groups=[])
    for g in J["groups"]:
        n = int(g["n"]); tfn = float(g["t_fn"])
        fc = int(g["conv"]["f"]); fon = int(g["onset"]["frame"]); fpl = int(pvp[n]["best"]["frame"])
        f0 = fc - 72; f1 = max(fon, fpl) + 48
        rows = {}
        # ---- summit track (forward from the converged frame, then backward)
        xprev = float(g["conv"]["x"])
        order = list(range(fc, f1 + 1)) + list(range(fc - 1, f0 - 1, -1))
        for f in order:
            if f == fc - 1:
                xprev = float(g["conv"]["x"])
            a, meta = H.get(f)
            e = EM.median3(masked(a, meta)) - eta0
            xs, yh = B.axes(meta, e.shape[0], e.shape[1])
            fwd = f >= fc
            lo, hi = (xprev - 3.0, xprev + 4.0) if fwd else (xprev - 4.0, xprev + 3.0)
            sx = (xs >= lo) & (xs <= hi); sy = yh <= YMAX_TRACK
            v = np.where(sy[:, None] & sx[None, :], e, np.nan)
            j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            xpk = float(xs[ix]); xprev = xpk
            m = EM.hf_metrics(masked(a, meta), meta, eta0, xwin=(xpk - 15.0, xpk + 15.0)) or {}
            r = dict(f=f, t=(f - 1) / B.FPS, Hc_loc=float(v[iy, ix]), x_pk=xpk, y_pk=float(yh[iy]), h=float(B.h_of(xpk)))
            for k in ("Hc", "W20", "W50", "W80", "W95", "S2", "K", "y_pk"):
                if k in m:
                    r["e51_" + k] = m[k]
            if "W50" in m:
                miss, _ = EM.score_vs_target(m); r["miss"] = miss; r["W50_m"] = m["W50"] * m["Hc"]
            # centre row crest near x_pk
            c0 = e[0]; scx = (xs >= xpk - 6.0) & (xs <= xpk + 6.0)
            i0 = int(np.nanargmax(np.where(scx, c0, np.nan)))
            r["x_c0"] = float(xs[i0] + sub_peak(c0, i0)); r["eta_c0"] = float(c0[i0])
            # r2 section
            s, smeta = RS.get(f); uu, _ = RU.get(f)
            if s is not None:
                us, xr, zr = r2_crest(s, uu, smeta, eta0, r["x_c0"])
                r["u_s"] = us
                sm = EM.section_metrics(s, smeta, eta0, r["x_c0"]) or {}
                for k in ("face_deg", "back_deg", "overhang", "Hs", "x_c_sec"):
                    if k in sm:
                        r["sec_" + k] = sm[k]
                fl = GA.lip_cols(s, zr, (xr >= r["x_c0"] - 20.0) & (xr <= r["x_c0"] + 20.0))
                k = GA.lip_hit(fl)
                r["lip_r2"] = k is not None
                r["lip_r2_x"] = float(xr[k]) if k is not None else None
            q = pvs.get(n, {}).get(f)
            if q:
                r["pv_score3"] = q.get("score3"); r["pv_lip"] = q.get("lip"); r["pv_x_c"] = q.get("x_c"); r["pv_eta_c"] = q.get("eta_c")
            rows[f] = r
        fr = sorted(rows)
        T = np.array([rows[f]["t"] for f in fr]); XC = np.array([rows[f]["x_c0"] for f in fr])
        # crest speed: least-squares slope of x_c0(t) over +-12 frames (1 s window; the 1 m grid makes frame differences noisy)
        c = np.full(len(fr), np.nan)
        for i in range(12, len(fr) - 12):
            c[i] = float(np.polyfit(T[i - 12:i + 13], XC[i - 12:i + 13], 1)[0])
        for i, f in enumerate(fr):
            rows[f]["c"] = float(c[i]) if np.isfinite(c[i]) else None
            u = rows[f].get("u_s")
            rows[f]["B"] = (u / c[i]) if (u is not None and np.isfinite(c[i]) and c[i] > 1.0 and np.isfinite(u)) else None
            rows[f]["t_rel_fn"] = rows[f]["t"] - tfn
            rows[f]["t_rel_conv"] = rows[f]["t"] - (fc - 1) / B.FPS
        fB = next((f for f in fr if f >= fc - 24 and rows[f].get("B") is not None and rows[f]["B"] >= B_TH), None)
        fLip = next((f for f in fr if f >= fc - 24 and rows[f].get("lip_r2")), None)
        Bs = [(rows[f]["B"], f) for f in fr if rows[f].get("B") is not None]
        fBmax = max(Bs)[1] if Bs else None

        def inst(f, label):
            if f is None:
                return None
            r = rows[f]
            o = dict(label=label, f=f, t=r["t"], t_rel_fn=r["t_rel_fn"], t_rel_conv=r["t_rel_conv"], x_pk=r["x_pk"], y_pk=r["y_pk"], x_c0=r["x_c0"],
                     Hc=r.get("e51_Hc", r["Hc_loc"]), Hc_loc=r["Hc_loc"], eta_c0=r["eta_c0"], h_at_x_pk=r["h"], h_at_x_c0=float(B.h_of(r["x_c0"])),
                     Hc_over_h=r.get("e51_Hc", r["Hc_loc"]) / max(r["h"], 0.1), eta_c0_over_h=r["eta_c0"] / max(float(B.h_of(r["x_c0"])), 0.1),
                     W50=r.get("e51_W50"), W50_m=r.get("W50_m"), W80=r.get("e51_W80"), W95=r.get("e51_W95"), S2=r.get("e51_S2"), miss=r.get("miss"),
                     back_deg_sec=r.get("sec_back_deg"), face_deg_sec=r.get("sec_face_deg"), overhang=r.get("sec_overhang"), c=r.get("c"),
                     u_s=r.get("u_s"), B=r.get("B"), lip_r2=r.get("lip_r2"), pv_score3=r.get("pv_score3"), pv_lip=r.get("pv_lip"))
            return o
        gi = dict(n=n, t_fn=tfn, frames=[f0, f1],
                  converged=inst(fc, "converged (judge: largest Hc, x 150-300 m, |y| <= 95 m, [t_fn - 8, t_fn + 2])"),
                  kinematic_onset=inst(fB, "first B = u_s / c >= %.2f from t_conv - 1 s on the tracked crest" % B_TH),
                  B_max=inst(fBmax, "largest B on the track"),
                  lip_onset_track=inst(fLip, "first r2 lip within x_c0 +- 20 m on the tracked crest"),
                  lip_onset_judge=dict(g["onset"], on_tracked_crest=bool(fLip == g["onset"]["frame"])),
                  print_like=inst(fpl, "pv53 most print-like (min score3, lip >= 0) of the group"),
                  pv53_best=pvp[n]["best"], pv53_conv_print=pvp[n]["conv_print"])
        cv = gi["converged"]; pl = gi["print_like"]
        dt = pl["t"] - cv["t"]
        gi["between_conv_and_print_like"] = dict(
            dt_s=dt, dx_m=pl["x_c0"] - cv["x_c0"], mean_crest_speed=(pl["x_c0"] - cv["x_c0"]) / dt,
            dHc_m=pl["Hc"] - cv["Hc"], Hc_decay_rate_m_per_s=(pl["Hc"] - cv["Hc"]) / dt, Hc_ratio=pl["Hc"] / cv["Hc"],
            eta_c0_decay_rate_m_per_s=(pl["eta_c0"] - cv["eta_c0"]) / dt,
            W50_m_conv=cv["W50_m"], W50_m_print=pl["W50_m"], lateral_spread_rate_m_per_s=((pl["W50_m"] or 0) - (cv["W50_m"] or 0)) / dt,
            W50_rel_change=(pl["W50"] / cv["W50"]) if (pl["W50"] and cv["W50"]) else None,
            depth_conv=cv["h_at_x_pk"], depth_print=pl["h_at_x_pk"],
            note="Hc = e51 summit of the frame (this crest, xwin x_pk +- 15 m); W50_m = full lateral width at Hc/2 in metres [measured]")
        # the compact time series (every 3 frames) for plots / the calibration
        ks = ["f", "t", "t_rel_conv", "x_pk", "y_pk", "x_c0", "Hc_loc", "e51_Hc", "eta_c0", "h", "W50_m", "e51_W50", "e51_W80", "e51_W95",
              "e51_S2", "miss", "c", "u_s", "B", "lip_r2", "sec_back_deg", "sec_face_deg", "sec_overhang", "pv_score3", "pv_lip"]
        gi["series"] = {k: [rows[f].get(k) for f in fr[::3]] for k in ks}
        out["groups"].append(gi)
        print("group", n, "conv", round(cv["t"], 2), cv["x_pk"], round(cv["Hc"], 2), "| B onset", (gi["kinematic_onset"] or {}).get("t"),
              (gi["kinematic_onset"] or {}).get("x_c0"), "| Bmax", round((gi["B_max"] or {}).get("B") or 0, 2), (gi["B_max"] or {}).get("t"),
              "| lip", (gi["lip_onset_track"] or {}).get("t"), "| print", round(pl["t"], 2), pl["x_pk"], round(pl["Hc"], 2),
              round(time.time() - t0, 1), "s", flush=True)
    # medians over groups
    def med(path):
        v = []
        for gi in out["groups"]:
            o = gi
            for p in path:
                o = (o or {}).get(p)
            if isinstance(o, (int, float)) and o is not None:
                v.append(o)
        return float(np.median(v)) if v else None
    out["median"] = {"%s.%s" % (a, b): med((a, b)) for a in ("converged", "kinematic_onset", "print_like")
                     for b in ("t_rel_fn", "t_rel_conv", "x_c0", "Hc", "h_at_x_pk", "Hc_over_h", "eta_c0_over_h", "W50", "W50_m", "miss", "back_deg_sec", "B")}
    out["median"].update({"between.%s" % k: med(("between_conv_and_print_like", k)) for k in
                          ("dt_s", "dx_m", "mean_crest_speed", "Hc_decay_rate_m_per_s", "Hc_ratio", "lateral_spread_rate_m_per_s", "W50_rel_change")})
    out["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(out, B.OUT + "/track_DFGB2E.json")
    print(json.dumps(out["median"], default=float))


if __name__ == "__main__":
    main()
