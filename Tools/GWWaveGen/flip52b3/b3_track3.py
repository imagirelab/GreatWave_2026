# -*- coding: utf-8 -*-
"""FLIP52B3 step 1: the converged crest of every group of the three 0.5 m runs DFG-2B-E (1:10), DFG-S-E140 (flat 20 m + 1:3 step to a 6 m
shelf) and DFGB3 (1:10 + a 1:3 face from x 235.25 m to a 6 m shelf) followed frame by frame, with the breaker numbers at four instants
(py -3.10 -B; numpy, scipy). 2026-10-18 written new (Claude); generalises flip52b2/b2_track.py (read only, not imported) to any bed.
Reads the runs' hf / r2 / r4 records, judge and pv53 jsons (read only); writes Unity/Build/FLIP52B3/diag/track3_<run>.json.

Per frame (24 fps) on the tracked crest (window conv - 5 s .. max(print-like, conv + 4.5 s) + 1.5 s):
  summit    largest 3x3-median hf - eta0 in x [x_prev - 3, x_prev + 4] m (forward; mirrored backward), |y| <= 25 m -> Hc, x_pk, y_pk [measured]
  bed       still depth h and bed slope tan(beta) under the centre crest x_c0 (the run's own bed formula; slope = mean over x_c0 +- 5 m and over the
            crest's front quarter wavelength) [computed]
  e51       frozen hf_metrics, xwin x_pk +- 15 m, every 2nd frame: W50, W80, W95, K, S2, core miss, H_front_row (summit row, crest - front trough
            within 30 m) [measured]
  centre    centre-row crest x_c0, eta_c0; crest speed c = d x_c0 / dt (least squares over +-0.5 s) [measured]
  r2        u_s = largest x velocity in the two top water cells of x_c0 +- 2 m; B = u_s / c (onset ~0.85, Barthelemy et al. 2018 [literature]);
            frozen section_metrics face_deg / back_deg / overhang; the AM-DFG1 lip test (>= 2 water runs, gap above eta0 + 0.5 m) x_c0 +- 20 m [measured]
  pv53      the pv53 series of the frame (score3, lip, chord, hood) [measured, pv53 json]
  r4        (every 3rd frame) the lateral extent of AM-DFG1 lips on the per-y sections y 0-94 m, x 190-335 m (D19B runs only) [measured]
Per group: converged (judge 'conv'), kinematic onset (first B >= 0.85 from conv - 1 s), first centre lip on the track, most print-like (pv53 best),
with t, x, Hc, H_front, h, Hc/h, H_front/h, slope, Iribarren numbers (local slope; T_m 7 s, range 5.6-9.33 s):
  xi_b  = tan(beta) / sqrt(H_front / L0)                           (Battjes 1974 breaker form: spilling < 0.4 < plunging < 2.0 < collapsing/surging)
  xi_bc = tan(beta) / sqrt(Hc / L0)                                (the round-2 plan's form: H = Hc)
  xi_0  = tan(beta) / sqrt(s0), s0 = H0' / L0, H0' = H_front(conv) / Ks(T_m, h_conv) = the group's equivalent deep-water steepness
          (deep-water form: spilling < 0.5 < plunging < 3.3 < surging) [computed from measured H]
usage: py -3.10 -B b3_track3.py [B2E|S2E|B3 ...]
Tags: [measured] [computed] [literature] [guess].
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b3_common as B                   # noqa: E402
import numpy as np                      # noqa: E402

EM = B.EM
GA = B.GA52
B_TH = 0.85
YMAX_TRACK = 25.0


def masked(a, meta, ymax):
    ny, nx = a.shape
    yh = float(meta["z0"]) + float(meta["dz"]) * np.arange(ny)
    b = a.copy(); b[yh > ymax + 1e-9, :] = np.nan
    return b


def crop(a, meta, xlo, xhi):
    nx = a.shape[1]
    xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
    i0 = max(int(np.searchsorted(xs, xlo)), 0); i1 = min(int(np.searchsorted(xs, xhi)) + 1, nx)
    m2 = dict(meta); m2["x0"] = float(xs[i0])
    return a[:, i0:i1], m2


def sub_peak(v, i):
    if 0 < i < len(v) - 1 and np.all(np.isfinite(v[i - 1:i + 2])):
        d = v[i - 1] - 2 * v[i] + v[i + 1]
        if d < 0:
            return float(np.clip(0.5 * (v[i - 1] - v[i + 1]) / d, -0.5, 0.5))
    return 0.0


def r2_crest(sdf, u, meta, eta0, x_c):
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
            if jj >= 0 and neg[jj, i] and i + 1 < u.shape[1]:
                us.append(0.5 * (float(u[jj, i]) + float(u[jj, i + 1])))
    return (max(us) if us else float("nan")), x, zs


def r4_lips(S4, f, eta0, x_c, ylim=94):
    """lateral extent of AM-DFG1 lips on the r4 per-y sections at frame f within x_c - 25 .. x_c + 25 m."""
    s, meta = S4.get(f)
    if s is None:
        return None
    # s: (n_lat, n_vert, nx); lateral rows z0 + dz k, vertical y0 + dy j
    nl, nv, nx = s.shape
    xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx)
    ys = float(meta["z0"]) + float(meta["dz"]) * np.arange(nl)
    zs = float(meta["y0"]) + float(meta["dy"]) * np.arange(nv) - eta0
    xok = (xs >= x_c - 25.0) & (xs <= x_c + 25.0)
    hit = []
    for k in range(nl):
        fl = GA.lip_cols(s[k], zs, xok)
        j = GA.lip_hit(fl)
        if j is not None:
            hit.append((float(ys[k]), float(xs[j])))
    if not hit:
        return dict(n=0)
    yy = np.array([h[0] for h in hit]); xx = np.array([h[1] for h in hit])
    return dict(n=len(hit), y_min=float(yy.min()), y_max=float(yy.max()), x_med=float(np.median(xx)), y_rows=[float(v) for v in yy])


def track_run(key):
    t0 = time.time()
    R = B.run_ctx(key)
    bed = R["bed"]; eta0 = R["eta0"]; ymax = R["ymax"]; J = R["J"]; PV = R["PV"]
    H = GA.Blocks(R["rd"], "hf", "eta"); RS = GA.Blocks(R["rd"], "r2", "sdf"); RU = GA.Blocks(R["rd"], "r2", "u")
    S4 = GA.Blocks(R["rd"], "r4", "sdf")
    r4_ok = len(S4.frames()) > 0
    pvp = {int(p["n"]): p for p in PV["periods"]}
    pvs = {int(k): {int(r["frame"]): r for r in v} for k, v in PV["series"].items()}
    out = dict(run=key, name=R["name"], rd=R["rd"].replace(B.REPO + "/", ""), eta0=eta0, ymax=ymax, B_threshold=B_TH,
               bed=dict(h0=bed.h0, x0=bed.x0, s=bed.s, shelf_h=bed.hs, pg_hL=bed.hL, pg_s2=bed.s2),
               date=time.strftime("%Y-%m-%d %H:%M:%S"), groups=[])
    for g in J["groups"]:
        n = int(g["n"]); tfn = float(g["t_fn"])
        fc = int(g["conv"]["f"]); fpl = int(pvp[n]["best"]["frame"])
        f0 = fc - 120; f1 = max(fpl, fc + 108) + 36
        rows = {}
        xprev = float(g["conv"]["x"])
        order = list(range(fc, f1 + 1)) + list(range(fc - 1, f0 - 1, -1))
        for f in order:
            if f == fc - 1:
                xprev = float(g["conv"]["x"])
            a, meta = H.get(f)
            if a is None:
                continue
            am = masked(a, meta, ymax)
            e = EM.median3(am) - eta0
            ny, nx = e.shape
            xs = float(meta["x0"]) + float(meta["dx"]) * np.arange(nx); yh = float(meta["z0"]) + float(meta["dz"]) * np.arange(ny)
            fwd = f >= fc
            lo, hi = (xprev - 3.0, xprev + 4.0) if fwd else (xprev - 4.0, xprev + 3.0)
            sx = (xs >= lo) & (xs <= hi); sy = yh <= YMAX_TRACK
            v = np.where(sy[:, None] & sx[None, :], e, np.nan)
            j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            xpk = float(xs[ix]); xprev = xpk
            r = dict(f=f, t=(f - 1) / B.FPS, Hc_loc=float(v[iy, ix]), x_pk=xpk, y_pk=float(yh[iy]))
            c0 = e[0]; scx = (xs >= xpk - 6.0) & (xs <= xpk + 6.0)
            i0 = int(np.nanargmax(np.where(scx, c0, np.nan)))
            r["x_c0"] = float(xs[i0] + sub_peak(c0, i0)); r["eta_c0"] = float(c0[i0])
            fr_ = (xs >= r["x_c0"]) & (xs <= r["x_c0"] + 30.0)
            r["trough_front_c0"] = float(np.nanmin(c0[fr_])) if np.isfinite(c0[fr_]).any() else None
            bk_ = (xs >= r["x_c0"] - 45.0) & (xs <= r["x_c0"])
            r["trough_back_c0"] = float(np.nanmin(c0[bk_])) if np.isfinite(c0[bk_]).any() else None
            r["h"] = float(bed.h(r["x_c0"])); r["h_pk"] = float(bed.h(xpk))
            r["slope5"] = float((bed.h(r["x_c0"] - 5.0) - bed.h(r["x_c0"] + 5.0)) / 10.0)
            _, cg, kk = B.cg_c(B.T_M, max(r["h"], 0.5))
            Lq = 0.25 * 2 * math.pi / kk
            r["slope_frontq"] = float((bed.h(r["x_c0"]) - bed.h(r["x_c0"] + Lq)) / Lq)
            if (f - fc) % 2 == 0 or f == fpl:
                ac, mc = crop(am, meta, xpk - 60.0, xpk + 35.0)
                m = EM.hf_metrics(ac, mc, eta0, xwin=(xpk - 15.0, xpk + 15.0)) or {}
                for k in ("Hc", "W20", "W50", "W80", "W95", "S2", "K", "H_front_row", "trough_front"):
                    if k in m:
                        r["e51_" + k] = m[k]
                if "W50" in m:
                    miss, _ = EM.score_vs_target(m); r["miss"] = miss; r["W50_m"] = m["W50"] * m["Hc"]; r["W95_m"] = m["W95"] * m["Hc"]
            s, smeta = RS.get(f); uu, _ = RU.get(f)
            if s is not None:
                us, xr, zr = r2_crest(s, uu, smeta, eta0, r["x_c0"])
                r["u_s"] = us
                sm = EM.section_metrics(s, smeta, eta0, r["x_c0"]) or {}
                for k in ("face_deg", "back_deg", "overhang", "Hs", "x_c_sec", "concavity"):
                    if k in sm:
                        r["sec_" + k] = sm[k]
                fl = GA.lip_cols(s, zr, (xr >= r["x_c0"] - 20.0) & (xr <= r["x_c0"] + 20.0))
                k = GA.lip_hit(fl)
                r["lip_r2"] = k is not None
                r["lip_r2_x"] = float(xr[k]) if k is not None else None
            if r4_ok and (f in S4.where):
                r["r4"] = r4_lips(S4, f, eta0, r["x_c0"])
            q = pvs.get(n, {}).get(f)
            if q:
                for k in ("score3", "lip", "chord", "hood", "eta_c", "x_c", "foot"):
                    r["pv_" + k] = q.get(k)
            rows[f] = r
        fr = sorted(rows)
        T = np.array([rows[f]["t"] for f in fr]); XC = np.array([rows[f]["x_c0"] for f in fr]); XP = np.array([rows[f]["x_pk"] for f in fr])
        c = np.full(len(fr), np.nan); cp = np.full(len(fr), np.nan)
        for i in range(12, len(fr) - 12):
            c[i] = float(np.polyfit(T[i - 12:i + 13], XC[i - 12:i + 13], 1)[0])
            cp[i] = float(np.polyfit(T[i - 12:i + 13], XP[i - 12:i + 13], 1)[0])
        tc = (fc - 1) / B.FPS
        for i, f in enumerate(fr):
            rr = rows[f]
            rr["c"] = float(c[i]) if np.isfinite(c[i]) else None
            rr["c_pk"] = float(cp[i]) if np.isfinite(cp[i]) else None
            u = rr.get("u_s")
            rr["B"] = (u / c[i]) if (u is not None and np.isfinite(c[i]) and c[i] > 1.0 and np.isfinite(u)) else None
            rr["t_rel_fn"] = rr["t"] - tfn; rr["t_rel_conv"] = rr["t"] - tc
            cl, cgl, _ = B.cg_c(B.T_M, max(rr["h"], 0.5))
            rr["c_lin_T7"] = cl; rr["c_sw_solitary"] = math.sqrt(B.G * (rr["h"] + max(rr["eta_c0"], 0.0)))
            tf = rr.get("trough_front_c0")
            rr["H_front_c0"] = rr["eta_c0"] - tf if tf is not None else None
        # converged-instant H for s0
        rc = rows[fc]
        Hf_c = rc.get("e51_H_front_row") or rc.get("H_front_c0")
        Ks = None
        c0_, cg0_, _ = B.cg_c(B.T_M, 200.0); c1_, cg1_, _ = B.cg_c(B.T_M, rc["h_pk"])
        Ks = math.sqrt(cg0_ / cg1_)
        H0p = Hf_c / Ks
        s0 = H0p / B.L0(B.T_M)
        fB = next((f for f in fr if f >= fc - 24 and rows[f].get("B") is not None and rows[f]["B"] >= B_TH), None)
        fLip = next((f for f in fr if f >= fc - 24 and rows[f].get("lip_r2")), None)
        Bs = [(rows[f]["B"], f) for f in fr if rows[f].get("B") is not None and f >= fc - 24]
        fBmax = max(Bs)[1] if Bs else None
        fr_after = [f for f in fr if f >= fc]
        fOv = max(fr_after, key=lambda f: (rows[f].get("sec_overhang") if rows[f].get("sec_overhang") is not None else -9)) if fr_after else None
        fFace = max(fr_after, key=lambda f: (rows[f].get("sec_face_deg") if rows[f].get("sec_face_deg") is not None else -9)) if fr_after else None
        # first r4 lip anywhere on the crest (D19B runs)
        fR4 = next((f for f in fr if f >= fc - 24 and (rows[f].get("r4") or {}).get("n", 0) > 0), None)

        def near_e51(f):
            """the e51 numbers of f or of the nearest frame that has them."""
            for d in (0, 1, -1, 2, -2):
                q = rows.get(f + d)
                if q and "e51_W50" in q:
                    return q
            return rows[f]

        def inst(f, label):
            if f is None:
                return None
            r = rows[f]; q = near_e51(f)
            Hc = q.get("e51_Hc", r["Hc_loc"]); Hf = q.get("e51_H_front_row") or r.get("H_front_c0")
            sl = r["slope5"]; slq = r["slope_frontq"]
            o = dict(label=label, f=f, t=r["t"], t_rel_fn=r["t_rel_fn"], t_rel_conv=r["t_rel_conv"], x_pk=r["x_pk"], y_pk=r["y_pk"], x_c0=r["x_c0"],
                     Hc=Hc, eta_c0=r["eta_c0"], H_front=Hf, H_front_c0=r.get("H_front_c0"), h=r["h"], h_pk=r["h_pk"],
                     Hc_over_h=Hc / max(r["h_pk"], 0.1), eta_c0_over_h=r["eta_c0"] / max(r["h"], 0.1), H_front_over_h=(Hf / max(r["h"], 0.1)) if Hf else None,
                     slope5=sl, slope_frontq=slq, W50=q.get("e51_W50"), W80=q.get("e51_W80"), W95=q.get("e51_W95"), S2=q.get("e51_S2"), K=q.get("e51_K"),
                     W50_m=q.get("W50_m"), W95_m=q.get("W95_m"), miss=q.get("miss"), c=r.get("c"), c_pk=r.get("c_pk"), c_lin_T7=r["c_lin_T7"],
                     c_sw_solitary=r["c_sw_solitary"], u_s=r.get("u_s"), B=r.get("B"), face_deg_sec=r.get("sec_face_deg"), back_deg_sec=r.get("sec_back_deg"),
                     overhang=r.get("sec_overhang"), lip_r2=r.get("lip_r2"), r4=r.get("r4"),
                     pv_score3=r.get("pv_score3"), pv_lip=r.get("pv_lip"), pv_chord=r.get("pv_chord"), pv_hood=r.get("pv_hood"))
            for nm, slv in (("", sl), ("_frontq", slq)):
                if Hf:
                    o["xi_b" + nm] = B.iribarren(slv, Hf); o["xi_b" + nm + "_Trange"] = [B.iribarren(slv, Hf, T) for T in B.T_RANGE]
                o["xi_bc" + nm] = B.iribarren(slv, Hc)
                o["xi_0" + nm] = slv / math.sqrt(s0)
            return o
        gi = dict(n=n, t_fn=tfn, frames=[f0, f1], s0=dict(H_front_conv=Hf_c, Ks_T7=Ks, H0p=H0p, L0_T7=B.L0(B.T_M), s0=s0,
                                                             xi0_1to3=(1 / 3) / math.sqrt(s0), xi0_1to5=0.2 / math.sqrt(s0), xi0_1to7=(1 / 7) / math.sqrt(s0),
                                                             xi0_1to10=0.1 / math.sqrt(s0)),
                  converged=inst(fc, "converged (judge 'conv')"),
                  kinematic_onset=inst(fB, "first B = u_s / c >= %.2f from t_conv - 1 s" % B_TH),
                  B_max=inst(fBmax, "largest B on the track"),
                  lip_onset_track=inst(fLip, "first centre (r2) lip within x_c0 +- 20 m"),
                  r4_lip_first=inst(fR4, "first r4 lip (any y 0-94 m) within x_c0 +- 25 m"),
                  max_overhang=inst(fOv, "largest section overhang after conv"),
                  max_face=inst(fFace, "steepest section face after conv"),
                  print_like=inst(fpl, "pv53 most print-like (best) of the group"),
                  pv53_best=pvp[n]["best"], pv53_conv_print=pvp[n]["conv_print"])
        ks = ["f", "t", "t_rel_conv", "x_pk", "y_pk", "x_c0", "Hc_loc", "e51_Hc", "eta_c0", "H_front_c0", "e51_H_front_row", "h", "h_pk", "slope5",
              "W50_m", "e51_W50", "e51_W95", "miss", "c", "c_pk", "u_s", "B", "lip_r2", "sec_face_deg", "sec_back_deg", "sec_overhang",
              "pv_score3", "pv_lip", "pv_chord"]
        gi["series"] = {k: [rows[f].get(k) for f in fr[::2]] for k in ks}
        gi["series"]["r4_n"] = [(rows[f].get("r4") or {}).get("n") if rows[f].get("r4") is not None else None for f in fr[::2]]
        gi["r4_lip_frames"] = [dict(f=f, t_rel_conv=rows[f]["t_rel_conv"], x_c0=rows[f]["x_c0"], **{k: v for k, v in rows[f]["r4"].items() if k != "y_rows"})
                               for f in fr if (rows[f].get("r4") or {}).get("n", 0) > 0]
        out["groups"].append(gi)
        k_ = gi["kinematic_onset"] or {}; l_ = gi["lip_onset_track"] or {}; p_ = gi["print_like"]
        print(key, "group", n, "conv", round(gi["converged"]["t_rel_fn"], 2), gi["converged"]["x_pk"], round(gi["converged"]["Hc"], 2),
              "| B", k_.get("t_rel_conv"), k_.get("x_c0"), "| lip", l_.get("t_rel_conv"), l_.get("x_c0"), "| print", round(p_["t_rel_conv"], 2), p_["x_c0"],
              "| r4lips", len(gi["r4_lip_frames"]), round(time.time() - t0, 1), "s", flush=True)
    out["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(out, B.OUT + "/track3_%s.json" % key)
    return out


if __name__ == "__main__":
    keys = sys.argv[1:] or ["B2E", "S2E", "B3"]
    for k in keys:
        track_run(k)
