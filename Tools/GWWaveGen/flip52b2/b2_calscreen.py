# -*- coding: utf-8 -*-
"""FLIP52B2 calibrated linear screen (CS1) for the DFG-2B round-2 design step (py -3.10 -B; numpy).
2026-10-18 written new (Claude). Replaces, for the design step only, the dfg52b_screen FLIP prediction (R_T7 x the local 2nd-order crest shifted
by the X2 dX / dT), which put the DFG-2B-E converged crest at x 255.5 m / t_f - 1.04 s while FLIP made it at x 228.5-238.5 m / t_f - 3.4..4.0 s.
Imports READ ONLY: flip50/g50_dirfield, flip51/e51_metrics (through b2_common). Reads diag/harm_DFGB2E.npz, diag/track_DFGB2E.json;
writes diag/calscreen_52b2.json (calib), diag/calscreen_validate.json (validate), diag/cs1_model.json (cs1), diag/cs1_<label>.json (predict).

Model CS1 (the 'cs1' / 'predict' commands; each piece measured on DFG-2B-E 0.5 m unless tagged otherwise):
  1 sources the WKB DirField design sea (g52b_table field: 3 layers x 34 directions, phases 0 at (x_f, 0), t_f); for EVERY cell (x, y <= 95 m)
            and component j the ray through the cell is traced back through the refracting bed (Snell, k_y conserved, y = 0 a mirror):
            Fin_j = 1 if it reaches the inlet band end x_in (100 m) without entering the side band |y| >= sd0 (95 m); otherwise Fsd_j = the
            side-band generated fraction at its crossing x' (1 for x' <= sd_gen, linear to 0 at sd_sw) [computed] ('2D aperture')
  2 bands   A_n(x, y) = (e_in,n sum_j Fin_j C_j + e_sd,n sum_j Fsd_j C_j) exp(-a_n (x - x_in)): complex generation efficiencies of the inlet
            band and of the side band per layer and a propagation damping, least squares on the FLIP harmonic maps (t 69-125 s) over
            x 110-230 m, y <= 95 m (before the depth-limited crest) [calibrated]; optional generator phase pre-compensation e^{-i dphi_n}
  3 crest   FLIP crest = kappa x the CS1 summit crest (kappa = FLIP Hc / model crest at the converged instant; kappa_t: the ratio along the
            crest from conv - 3 s to conv + 3.5 s) [calibrated]; FLIP position = model position + the measured offset at conv;
            DEPTH SATURATION: converged = the first instant kappa x crest >= gamma_s h(x) (gamma_s = measured Hc / h on the depth-limited
            crest), else the unsaturated maximum [measured]
  4 curl    the 1:10 lip clock: lip = converged + dt_lip (measured 2.25 s; kinematic onset B >= 0.85 at + 1.33 s) [measured on 1:10; a steeper
            bed is NOT modelled: [guess] from DFG-S, lip 0.5-1.1 s after the critical point]
  5 shape   W50_m(lip) = rho_lip x the model W50_m at the lip instant (rho_lip measured); Hc(lip) = gamma_lip h(lip); W80, W95 from the measured
            ratios at the lip; S2 = the measured lip S2; core miss with the frozen e51 ranges [calibrated]
The 'calib' command keeps the first, simpler calibration for the record: LINap = the centre-row (per column) aperture and R'_n(x) =
FLIP / LINap lateral regression, kappa(t_rel) against that field (diag/calscreen_52b2.json); CS1 supersedes it for predictions.
usage:
  py -3.10 -B b2_calscreen.py calib                       (record: per-column aperture + R'(x), kappa(t_rel), gamma_s, lip clock)
  py -3.10 -B b2_calscreen.py validate                    (FLIP51 X2 and X2B' monochromatic T 7 runs: LIN / LINap / FLIP harmonic and scan peaks)
  py -3.10 -B b2_calscreen.py cs1                         (CS1 build on DFG-2B-E, self-check, T 7 transfer check -> diag/cs1_model.json)
  py -3.10 -B b2_calscreen.py predict [x_f] [--dphi=a,b,c] [--sdgen=g,sw] [--label=..]   (-> diag/cs1_<label>.json)
Tags: [measured] [computed] [calibrated] [guess].
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b2_common as B                   # noqa: E402
import numpy as np                      # noqa: E402

EM = B.EM
LAY_D = dict(x_in=100.0, sd0=95.0, sd_gen=180.25, sd_sw=210.25, W=140.0)
X = 0.5 + np.arange(0, 341)              # hf cell centres x 0.5 .. 340.5
NY = 96
Y = 0.5 + np.arange(NY)                  # y 0.5 .. 95.5
XT = np.arange(110.5, 340.6, 5.0)        # frac table columns
X_SAT_CAL = 230.0                        # R' used up to here (DFG-2B-E: the crest saturates at x 236-238 m) [chosen]
TREL = np.arange(-14.0, 10.0 + 1e-9, 1.0 / 24.0)
SCAN_X = (150.0, 300.0)
META = dict(x0=0.5, dx=1.0, z0=0.5, dz=1.0)


# ============================================================================ geometry: generated fraction per (layer, direction, column)
def frac_at(x_t, T_list, th, lay, bed=B.BED):
    xg = np.arange(0.0, max(x_t, lay["x_in"] + 1.0) + 0.5, 0.5)
    out = []
    for T in T_list:
        d = B.DF.DirField(T, th, np.ones(len(th)) / len(th), 1.0, np.union1d(xg, [x_t]), bed, x_t)
        fr = []
        for j in range(len(th)):
            xs, yy = d.ray_back(j, lay["x_in"])
            if yy[-1] <= lay["W"] + 1e-9:
                f = 1.0
            else:
                i = int(np.argmax(yy >= lay["sd0"])); xc = float(xs[i])
                f = 1.0 if xc <= lay["sd_gen"] else (0.0 if xc >= lay["sd_sw"] else 1.0 - (xc - lay["sd_gen"]) / (lay["sd_sw"] - lay["sd_gen"]))
            fr.append(f)
        out.append(fr)
    return np.array(out)


def frac_table(T_list, th, lay):
    F = np.array([frac_at(float(x), T_list, th, lay) for x in XT])          # (nxt, nl, nd)
    Fx = np.empty((len(X),) + F.shape[1:])
    for k in range(F.shape[1]):
        for j in range(F.shape[2]):
            Fx[:, k, j] = np.interp(X, XT, F[:, k, j])
    Fx[X < XT[0]] = F[0]
    return Fx                                                                 # (nx, nl, nd)


# ============================================================================ linear maps
def lin_maps(sea, x_f, Fx=None):
    """per layer complex (NY, nx) maps of the WKB sea with phases 0 at (x_f, 0); Fx: generated fractions (nx, nl, nd) or None (all)."""
    dfs, xg = B.dirfields(X, sea, x_f)
    idx = np.array([int(np.argmin(np.abs(xg - v))) for v in X])
    out = []
    for k, d in enumerate(dfs):
        A = np.zeros((NY, len(X)), complex)
        for j in range(len(d.a)):
            w = 1.0 if Fx is None else Fx[:, k, j]
            A += np.exp(1j * d.ky[j] * Y)[:, None] * (w * d.Aj[j, idx] * np.exp(1j * d.Phi[j, idx]))[None, :]
        out.append(A)
    return out


def regress(Af, Al):
    num = np.nansum(Af * np.conj(Al), 0); den = np.nansum(np.abs(Al) ** 2, 0)
    return num / np.where(den > 0, den, np.nan)


# ============================================================================ field analysis
def field_fun(maps, oms, R=None, dphi=None):
    Ms = []
    for k, (A, om) in enumerate(zip(maps, oms)):
        f = (R[k][None, :] if R is not None else 1.0) * (np.exp(-1j * dphi[k]) if dphi is not None else 1.0)
        Ms.append(A * f)

    def fun(tp):
        e = np.zeros(Ms[0].shape)
        for A, om in zip(Ms, oms):
            e += np.real(A * np.exp(-1j * om * tp))
        return e
    return fun


def half(e):
    a = np.full((140, 412), np.nan); a[:e.shape[0], :e.shape[1]] = e
    return a


def summit_track(fun, t_conv, x_conv, t_lo=-4.0, t_hi=4.0, step=1.0 / 24.0, with_widths=True):
    """the 2D summit followed from (t_conv, x_conv) forward and backward (window x_prev - 3 .. + 4 m, |y| <= 25 m) with e51 widths
    (xwin x_pk +- 15 m). Returns rows sorted by t_rel = t' - t_conv."""
    rows = {}
    for direction in (1, -1):
        xp = x_conv
        n = int(round((t_hi if direction > 0 else -t_lo) / step))
        for i in range(0 if direction > 0 else 1, n + 1):
            tp = t_conv + direction * i * step
            e = fun(tp)
            lo, hi = (xp - 3.0, xp + 4.0) if direction > 0 else (xp - 4.0, xp + 3.0)
            sx = (X >= lo) & (X <= hi)
            v = np.where((Y <= 25.0)[:, None] & sx[None, :], e, np.nan)
            j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            xp = float(X[ix])
            r = dict(t_rel=round(tp - t_conv, 5), tp=tp, x=xp, y=float(Y[iy]), crest=float(v[iy, ix]), h=float(B.h_of(xp)))
            if with_widths:
                m = EM.hf_metrics(half(e), META, 0.0, xwin=(xp - 15.0, xp + 15.0)) or {}
                if "W50" in m:
                    r.update(Hc=m["Hc"], W50=m["W50"], W80=m["W80"], W95=m["W95"], S2=m["S2"], W50_m=m["W50"] * m["Hc"],
                             W80_m=m["W80"] * m["Hc"], W95_m=m["W95"] * m["Hc"])
            rows[r["t_rel"]] = r
    return [rows[k] for k in sorted(rows)]


def conv_of(fun, t_rng=(-12.0, 6.0)):
    best = (-1e9, None, None)
    sx = (X >= SCAN_X[0]) & (X <= SCAN_X[1])
    for tp in TREL:
        if not (t_rng[0] - 1e-9 <= tp <= t_rng[1] + 1e-9):
            continue
        e = fun(tp)
        v = np.where(sx[None, :], e, np.nan)
        j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
        if v[iy, ix] > best[0]:
            best = (float(v[iy, ix]), tp, float(X[ix]))
    return dict(crest=best[0], t_rel=best[1], x=best[2], h=float(B.h_of(best[2])))


# ============================================================================ calib (DFG-2B-E)
def calib():
    t0 = time.time()
    c = B.cfg(); sea = B.sea_of(c)
    Z = np.load(B.OUT + "/harm_DFGB2E.npz")
    oms = [float(v) for v in Z["om"]]; ns = [int(v) for v in Z["ns"]]
    assert np.allclose(Z["x"], X)
    AF = [np.nan_to_num(Z["W2_n%d" % n].astype(complex)[:NY]) for n in ns]
    Fx = frac_table(sea["T"], sea["th"], LAY_D)
    AL = lin_maps(sea, sea["x_f"])
    ALap = lin_maps(sea, sea["x_f"], Fx)
    R = [regress(a, l) for a, l in zip(AF, AL)]
    Rp = [regress(a, l) for a, l in zip(AF, ALap)]
    # aperture per column on the centre row and the 'design amplitude' sums
    ap = dict(x=X[::5], centre_lin=[np.abs(l[0])[::5] for l in AL], centre_lin_ap=[np.abs(l[0])[::5] for l in ALap])
    # R' used by CS1: measured up to X_SAT_CAL, held at the mean over 200 .. X_SAT_CAL beyond
    Ruse = []
    for r in Rp:
        rr = np.nan_to_num(r.copy(), nan=0.0)
        m = (X >= 200.0) & (X <= X_SAT_CAL)
        rr[X > X_SAT_CAL] = np.mean(rr[m])
        Ruse.append(rr)
    # fields
    F_lin = field_fun(AL, oms); F_ap = field_fun(ALap, oms); F_cal = field_fun(ALap, oms, Ruse)
    cv = {nm: conv_of(f) for nm, f in (("LIN", F_lin), ("LINap", F_ap), ("CAL", F_cal))}
    # CAL summit track around its converged instant, with widths
    trk = summit_track(F_cal, cv["CAL"]["t_rel"], cv["CAL"]["x"], -4.0, 4.0)
    # FLIP tracks (b2_track) -> kappa(t_rel) and W ratios, aligned at each group's converged instant / at equal x
    TJ = B.jload(B.OUT + "/track_DFGB2E.json")
    tr_cal = {round(r["t_rel"], 3): r for r in trk}
    kap = {}
    for g in TJ["groups"]:
        s = g["series"]
        for i, tr in enumerate(s["t_rel_conv"]):
            k = round(round(tr * 24.0) / 24.0, 3)
            q = tr_cal.get(k)
            if q is None or s["e51_Hc"][i] is None:
                continue
            kap.setdefault(k, []).append(dict(n=g["n"], kappa=s["e51_Hc"][i] / q["crest"], W50m_ratio=(s["W50_m"][i] / q["W50_m"]) if (s["W50_m"][i] and q.get("W50_m")) else None,
                                              x_FLIP=s["x_pk"][i], x_CAL=q["x"], Hc_FLIP=s["e51_Hc"][i], Hc_CAL=q["crest"], h_FLIP=s["h"][i]))
    kap_t = sorted(kap)
    kappa = dict(t_rel=kap_t, kappa_med=[float(np.median([v["kappa"] for v in kap[k]])) for k in kap_t],
                 W50m_ratio_med=[float(np.median([v["W50m_ratio"] for v in kap[k] if v["W50m_ratio"]])) if any(v["W50m_ratio"] for v in kap[k]) else None for k in kap_t],
                 dx_FLIP_minus_CAL_med=[float(np.median([v["x_FLIP"] - v["x_CAL"] for v in kap[k]])) for k in kap_t])
    # depth saturation and curl numbers [measured]
    sat = []
    for g in TJ["groups"]:
        s = g["series"]
        r_after = [s["e51_Hc"][i] / s["h"][i] for i, tr in enumerate(s["t_rel_conv"]) if 0.0 <= tr <= 1.5 and s["e51_Hc"][i]]
        cvg = g["converged"]; lip = g["print_like"]; kin = g["kinematic_onset"]
        sat.append(dict(n=g["n"], Hc_over_h_conv=cvg["Hc_over_h"], Hc_over_h_0_1p5s_median=float(np.median(r_after)), Hc_over_h_0_1p5s_range=[min(r_after), max(r_after)],
                        h_conv=cvg["h_at_x_pk"], h_kin=kin["h_at_x_pk"] if kin else None, h_lip=lip["h_at_x_pk"], dh_lip=cvg["h_at_x_pk"] - lip["h_at_x_pk"],
                        dt_lip=lip["t_rel_conv"], dt_kin=kin["t_rel_conv"] if kin else None, Hc_over_h_lip=lip["Hc_over_h"],
                        W80_over_W50_lip=(lip["W80"] / lip["W50"]) if lip["W50"] else None, W95_over_W50_lip=(lip["W95"] / lip["W50"]) if lip["W50"] else None,
                        W50_m_conv=cvg["W50_m"], W50_m_lip=lip["W50_m"]))
    gs = [q["Hc_over_h_0_1p5s_median"] for q in sat[1:]]                      # groups 2 and 3: saturated at the converged instant
    rule = dict(gamma_s=float(np.median(gs)), gamma_s_groups=[q["Hc_over_h_0_1p5s_median"] for q in sat],
                gamma_s_src="median Hc / h on the tracked crest over t_conv .. t_conv + 1.5 s, groups 2 and 3 (group 1 reached 0.75 only at +1.5 s) [measured]",
                dh_lip=float(np.median([q["dh_lip"] for q in sat])), dt_lip=float(np.median([q["dt_lip"] for q in sat])),
                dt_kin=float(np.median([q["dt_kin"] for q in sat if q["dt_kin"] is not None])),
                W80_over_W50_lip=float(np.median([q["W80_over_W50_lip"] for q in sat])), W95_over_W50_lip=float(np.median([q["W95_over_W50_lip"] for q in sat])),
                X_SAT_CAL=X_SAT_CAL)
    k0 = [v for k, v in zip(kappa["t_rel"], kappa["kappa_med"]) if abs(k) < 1e-6]
    w0 = [v for k, v in zip(kappa["t_rel"], kappa["W50m_ratio_med"]) if abs(k) < 1e-6]
    rule["kappa_conv"] = k0[0] if k0 else None
    rule["W50m_ratio_conv"] = w0[0] if w0 else None
    out = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), run=B.RUN.replace(B.REPO + "/", ""), layout=LAY_D,
               R_lin=[dict(n=n, x=X[::5], abs=np.abs(R[k])[::5], delay_s=(np.angle(R[k]) / oms[k])[::5]) for k, n in enumerate(ns)],
               R_ap=[dict(n=n, x=X[::5], abs=np.abs(Rp[k])[::5], delay_s=(np.angle(Rp[k]) / oms[k])[::5]) for k, n in enumerate(ns)],
               R_use=[dict(n=n, x=X, re=np.real(Ruse[k]), im=np.imag(Ruse[k])) for k, n in enumerate(ns)],
               aperture_centre=ap, conv=cv, cal_track=[{k: v for k, v in r.items() if k != "tp"} for r in trk], kappa=kappa, saturation=sat, rule=rule,
               cpu_s=round(time.time() - t0, 1))
    B.jdump(out, B.OUT + "/calscreen_52b2.json")
    print(json.dumps(dict(conv=cv, rule=rule), default=float))
    return out


# ============================================================================ 2D aperture: the source of every component at every cell
def sources_2d(sea, x_f, lay, bed=B.BED):
    """per layer: (Fin, Fsd) of shape (nd, NY, nx): Fin = 1 where the ray of component j through (x, y), traced back through the refracting
    bed (Snell, k_y conserved, the y = 0 wall a mirror), reaches the inlet band end x_in without entering the side band |y| >= sd0;
    Fsd = the side-band generated fraction (1 for a crossing at x <= sd_gen, linear to 0 at sd_sw) where it enters the side band first.
    Ray offset: y(x') = y - (Q_j(x) - Q_j(x')), Q_j = int k_y / k_x dx; |Q| is monotonic, so the crossing |y(x')| = sd0 is at
    |Q_j(x')| = |Q_j(x)| - (sd0 - s_j y), s_j = sign(k_y) (k_y < 0: the ray came from +y) [computed]."""
    dfs, xg = B.dirfields(X, sea, x_f)
    out = []
    for d in dfs:
        tn = d.ky[:, None] / np.maximum(d.kx, 1e-9)                                  # (nd, nxg)
        Q = np.concatenate([np.zeros((len(d.a), 1)), np.cumsum(0.5 * (tn[:, 1:] + tn[:, :-1]) * np.diff(xg)[None, :], 1)], 1)
        P = np.abs(Q)
        Pin = np.array([np.interp(lay["x_in"], xg, P[j]) for j in range(len(d.a))])
        Px = np.array([np.interp(X, xg, P[j]) for j in range(len(d.a))])           # (nd, nx)
        Fin = np.zeros((len(d.a), NY, len(X))); Fsd = np.zeros_like(Fin)
        for j in range(len(d.a)):
            sgn = -1.0 if d.ky[j] < 0 else 1.0                                       # ky < 0: y grows going back
            need = lay["sd0"] + sgn * Y                                               # |dQ| at the crossing (ky<0: sd0 - y; ky>0: sd0 + y)
            need = np.where(d.ky[j] < 0, lay["sd0"] - Y, lay["sd0"] + Y)
            avail = Px[j][None, :] - Pin[j]                                           # |dQ| from x back to x_in
            inl = avail[None, :] if False else (avail < need[:, None])
            Pc = Px[j][None, :] - need[:, None]                                       # |Q| at the crossing
            # crossing x' = P^{-1}(Pc) (P monotonic increasing in x for ky != 0)
            if abs(d.ky[j]) < 1e-12:
                Fin[j] = 1.0; continue
            xc = np.interp(Pc, P[j], xg)
            f = np.where(xc <= lay["sd_gen"], 1.0, np.where(xc >= lay["sd_sw"], 0.0, 1.0 - (xc - lay["sd_gen"]) / (lay["sd_sw"] - lay["sd_gen"])))
            Fin[j] = np.where(inl, 1.0, 0.0)
            Fsd[j] = np.where(inl, 0.0, f)
        out.append((Fin, Fsd))
    return out, dfs, xg


def comp_maps(dfs, xg):
    """per layer: (nd, NY, nx) complex component fields C_j(x) e^{i ky y}."""
    idx = np.array([int(np.argmin(np.abs(xg - v))) for v in X])
    out = []
    for d in dfs:
        C = (d.Aj[:, idx] * np.exp(1j * d.Phi[:, idx]))[:, None, :] * np.exp(1j * d.ky[:, None] * Y[None, :])[:, :, None]
        out.append(C)
    return out


def fit_eff(AF, Cs, srcs, xr=(110.0, 230.0), damp=False):
    """complex generation efficiencies per layer: A_FLIP ~ e_in sum_j Fin C_j + e_sd sum_j Fsd C_j (+ optional damping exp(-a (x - x_in)))
    by least squares over x in xr, y <= 95 m [calibrated]."""
    res = []
    m = (X >= xr[0]) & (X <= xr[1])
    for A, C, (Fin, Fsd) in zip(AF, Cs, srcs):
        Bi = np.sum(Fin * C, 0); Bs = np.sum(Fsd * C, 0)
        best = None
        for a in (np.linspace(0.0, 0.008, 33) if damp else [0.0]):
            g = np.exp(-a * np.maximum(X - 100.0, 0.0))[None, :]
            M = np.stack([(Bi * g)[:, m].ravel(), (Bs * g)[:, m].ravel()], 1)
            y = A[:, m].ravel()
            ok = np.isfinite(y)
            coef, *_ = np.linalg.lstsq(M[ok], y[ok], rcond=None)
            r = y[ok] - M[ok] @ coef
            rel = float(np.sqrt(np.sum(np.abs(r) ** 2) / np.sum(np.abs(y[ok]) ** 2)))
            if best is None or rel < best["rel_resid"]:
                best = dict(e_in=complex(coef[0]), e_sd=complex(coef[1]), damp_per_m=float(a), rel_resid=rel)
        res.append(best)
    return res


# ============================================================================ CS1 model build (DFG-2B-E calibration) and prediction
def model_maps(sea, x_f, lay, eff, dphi=None):
    """per layer complex maps of the CS1 field: sum_j (e_in Fin_j + e_sd Fsd_j) C_j exp(-a (x - x_in)) exp(-i dphi_n)."""
    srcs, dfs, xg = sources_2d(sea, x_f, lay)
    Cs = comp_maps(dfs, xg)
    out = []
    for k, ((Fin, Fsd), C) in enumerate(zip(srcs, Cs)):
        e = eff[k]
        g = np.exp(-e["damp_per_m"] * np.maximum(X - lay["x_in"], 0.0))[None, :]
        A = (e["e_in"] * np.sum(Fin * C, 0) + e["e_sd"] * np.sum(Fsd * C, 0)) * g
        if dphi is not None:
            A = A * np.exp(-1j * float(dphi[k]))
        out.append(A)
    return out


def build_cs1():
    """calibrate CS1 on DFG-2B-E: band efficiencies (with propagation damping, x 110-230 m), kappa, gamma_s, the 1:10 lip clock and the
    lip shape ratios."""
    t0 = time.time()
    sea = B.sea_of()
    Z = np.load(B.OUT + "/harm_DFGB2E.npz"); oms = [float(v) for v in Z["om"]]
    AF = [Z["W2_n%d" % n].astype(complex)[:NY] for n in (3, 4, 5)]
    srcs, dfs, xg = sources_2d(sea, sea["x_f"], LAY_D)
    Cs = comp_maps(dfs, xg)
    eff = fit_eff(AF, Cs, srcs, xr=(110.0, 230.0), damp=True)
    maps = model_maps(sea, sea["x_f"], LAY_D, eff)
    f = field_fun(maps, oms)
    cv = conv_of(f)
    trk = summit_track(f, cv["t_rel"], cv["x"], -3.0, 3.5)
    TJ = B.jload(B.OUT + "/track_DFGB2E.json")
    cal = B.jload(B.OUT + "/calscreen_52b2.json")["rule"]
    g_c = [g["converged"] for g in TJ["groups"]]; g_l = [g["print_like"] for g in TJ["groups"]]
    Hc_conv = float(np.median([q["Hc"] for q in g_c]))
    kappa = Hc_conv / cv["crest"]
    tl = cal["dt_lip"]
    ml = min(trk, key=lambda r: abs(r["t_rel"] - tl)); m0 = min(trk, key=lambda r: abs(r["t_rel"]))
    rho_lip = float(np.median([q["W50_m"] for q in g_l])) / ml["W50_m"]
    rho_conv = float(np.median([q["W50_m"] for q in g_c])) / m0["W50_m"]
    S2_lip = float(np.median([q["S2"] for q in g_l]))
    gam_lip = float(np.median([q["Hc_over_h"] for q in g_l]))
    # FLIP / CS1-model ratios along the crest, aligned at the converged instants (t_rel = t - t_conv) [calibrated]
    trm = {round(r["t_rel"], 3): r for r in trk}
    kt = {}
    for g in TJ["groups"]:
        s = g["series"]
        for i, tr in enumerate(s["t_rel_conv"]):
            q = trm.get(round(round(tr * 24.0) / 24.0, 3))
            if q is None or s["e51_Hc"][i] is None:
                continue
            kt.setdefault(round(tr, 3), []).append((s["e51_Hc"][i] / q["crest"], (s["W50_m"][i] / q["W50_m"]) if (s["W50_m"][i] and q.get("W50_m")) else np.nan,
                                                    s["x_pk"][i] - q["x"], s["e51_Hc"][i], q["crest"], s["miss"][i] if s["miss"][i] is not None else np.nan))
    kts = sorted(kt)
    kappa_t = dict(t_rel=kts, Hc_ratio=[float(np.median([v[0] for v in kt[k]])) for k in kts],
                   W50m_ratio=[float(np.nanmedian([v[1] for v in kt[k]])) for k in kts], dx_m=[float(np.median([v[2] for v in kt[k]])) for k in kts],
                   Hc_FLIP=[float(np.median([v[3] for v in kt[k]])) for k in kts], crest_model=[float(np.median([v[4] for v in kt[k]])) for k in kts],
                   miss_FLIP=[float(np.nanmedian([v[5] for v in kt[k]])) for k in kts],
                   rule="median over the 3 groups of FLIP (b2_track) / CS1 model summit track at the same time after the respective converged instant")
    cs1 = dict(eff=[dict(n=n, e_in=[e["e_in"].real, e["e_in"].imag], e_in_abs=abs(e["e_in"]), e_in_phase=float(np.angle(e["e_in"])),
                         e_sd=[e["e_sd"].real, e["e_sd"].imag], e_sd_abs=abs(e["e_sd"]), e_sd_phase=float(np.angle(e["e_sd"])),
                         damp_per_m=e["damp_per_m"], rel_resid=e["rel_resid"]) for n, e in zip((3, 4, 5), eff)],
               kappa=kappa, gamma_s=cal["gamma_s"], gamma_lip=gam_lip, dt_lip_1to10=tl, dh_lip_1to10=cal["dh_lip"], dt_kin_1to10=cal["dt_kin"],
               rho_W50m_conv=rho_conv, rho_W50m_lip=rho_lip, W80_over_W50_lip=cal["W80_over_W50_lip"], W95_over_W50_lip=cal["W95_over_W50_lip"],
               S2_lip_measured=S2_lip, model_conv=cv, model_W50m_conv=m0["W50_m"], model_W50m_lip=ml["W50_m"], kappa_t=kappa_t,
               measured=dict(conv_x=[q["x_pk"] for q in g_c], conv_t_rel_fn=[q["t_rel_fn"] for q in g_c], conv_Hc=[q["Hc"] for q in g_c],
                             lip_x=[q["x_pk"] for q in g_l], lip_t_rel_fn=[q["t_rel_fn"] for q in g_l], lip_W50=[q["W50"] for q in g_l],
                             lip_miss=[q["miss"] for q in g_l]),
               fit_rule="A_FLIP,n(x, y) ~ (e_in sum_j Fin_j C_j + e_sd sum_j Fsd_j C_j) exp(-a (x - 100)), least squares over x 110-230 m, y <= 95 m, "
                        "harmonic maps of t 69-125 s; a scanned 0-0.008 /m [calibrated]",
               cpu_s=round(time.time() - t0, 1))
    return cs1


def predict(cs1, x_f=None, dphi=None, lay=None, label="", a_scale=1.0):
    """CS1 prediction for a design variant on the D19B 1:10 bed (times relative to the variant's own t_f). The lip clock and the lip width
    ratio are the 1:10 measurements; a steeper segment (candidate c) is NOT modelled here (see diag/track_DFGB2E.json: the measured state
    of the crest at conv + dt)."""
    sea = dict(B.sea_of())
    if x_f is not None:
        sea["x_f"] = float(x_f)
    sea["a_sum"] *= a_scale
    lay = lay or LAY_D
    oms = [2 * math.pi / T for T in sea["T"]]
    eff = [dict(e_in=complex(*e["e_in"]), e_sd=complex(*e["e_sd"]), damp_per_m=e["damp_per_m"]) for e in cs1["eff"]]
    maps = model_maps(sea, sea["x_f"], lay, eff, dphi)
    f = field_fun(maps, oms)
    cv = conv_of(f, (-14.0, 8.0))
    trk = summit_track(f, cv["t_rel"], cv["x"], -6.0, 5.0)
    k = cs1["kappa"]; gs = cs1["gamma_s"]
    dx0 = float(np.median(cs1["measured"]["conv_x"])) - cs1["model_conv"]["x"]          # FLIP - model x at conv (DFG-2B-E) [calibrated]
    dt0 = float(np.median(cs1["measured"]["conv_t_rel_fn"])) - cs1["model_conv"]["t_rel"]  # FLIP - model t at conv [calibrated]
    sat = None; peak = None
    for r in trk:
        xF = r["x"] + dx0; hF = float(B.h_of(xF)); HF = k * r["crest"]
        r["x_FLIP"] = xF; r["Hc_FLIP_unsat"] = HF; r["h_FLIP"] = hF; r["t_FLIP"] = r["tp"] + dt0
        if sat is None and HF >= gs * hF:
            sat = r
        if peak is None or HF > peak["Hc_FLIP_unsat"]:
            peak = r
    saturated = sat is not None and sat["t_rel"] <= peak["t_rel"]
    conv = sat if saturated else peak
    Hc_conv = min(k * conv["crest"], gs * conv["h_FLIP"])
    t_lip = conv["t_rel"] + cs1["dt_lip_1to10"]
    lp = min(trk, key=lambda r: abs(r["t_rel"] - t_lip))
    x_lip = lp["x_FLIP"]
    h_lip = float(B.h_of(x_lip)); Hc_lip = min(cs1["gamma_lip"] * h_lip, k * lp["crest"])
    W50m_lip = cs1["rho_W50m_lip"] * lp.get("W50_m", float("nan"))
    W50_lip = W50m_lip / Hc_lip
    W80 = W50_lip * cs1["W80_over_W50_lip"]; W95 = W50_lip * cs1["W95_over_W50_lip"]
    miss, per = EM.score_vs_target(dict(W50=W50_lip, W80=W80, W95=W95, K=None, S2=cs1["S2_lip_measured"]))
    W50m_c = cs1["rho_W50m_conv"] * conv.get("W50_m", float("nan"))
    return dict(label=label, x_f=sea["x_f"], dphi=list(dphi) if dphi is not None else None, layout=lay, a_scale=a_scale, model_conv=cv,
                converged=dict(t_rel_tf=conv["t_FLIP"], x=conv["x_FLIP"], h=conv["h_FLIP"], Hc=Hc_conv, saturated=bool(saturated),
                               Hc_over_h=Hc_conv / conv["h_FLIP"], W50_m=W50m_c, W50=W50m_c / Hc_conv if Hc_conv > 0 else None,
                               unsat_peak=dict(t_rel_tf=peak["t_FLIP"], x=peak["x_FLIP"], Hc=peak["Hc_FLIP_unsat"])),
                lip=dict(t_rel_tf=lp["t_FLIP"], dt_after_conv=lp["t_rel"] - conv["t_rel"], x=x_lip, h=h_lip, Hc=Hc_lip, W50_m=W50m_lip, W50=W50_lip,
                         W80=W80, W95=W95, miss_core=miss, miss_per=per),
                G6_window_ok=bool(-4.0 <= conv["t_FLIP"] <= 2.0 and 225.0 <= conv["x_FLIP"] <= 295.0),
                track=[dict(t_rel_tf=round(r["t_FLIP"], 3), x_FLIP=r["x_FLIP"], Hc_FLIP_unsat=round(r["Hc_FLIP_unsat"], 3), h=r["h_FLIP"],
                            W50_m_model=r.get("W50_m")) for r in trk[::6]])


# ============================================================================ validate: the aperture rule on the FLIP51 T 7 runs (independent designs)
VAL_RUNS = {"X2": B.REPO + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5",
            "X2B'": B.REPO + "/Unity/Build/FLIP51/runs/S51X2B_D19B_T7_g60s28_xf275_dp0p5"}


def validate(t_win=(42.0, 70.0)):
    """X2 (x_f 220.25, side band generating to 180.25 / 210.25) and X2B' (x_f 275.25, side band to 210.25 / 240.25): T 7 s, the X2 34
    directions, a_sum 6.33 m, D19B. Per run: the linear amplitude |A| (centre row and 2D max over y <= 95 m) of LIN and LINap, the FLIP
    harmonic amplitude at w = 2 pi / 7 (least squares over t 42-70 s = 4 periods, nuisance 2 w, 3 w and the mean, 3x3-median hf - eta0) and
    the FLIP crest scan (largest crest per frame over x 150-300 m, |y| <= 95 m; median x over the frames whose crest is in the top 10 %)."""
    out = {}
    for nm, rd in VAL_RUNS.items():
        c = B.jload(rd + "/cfg.json"); d = c["dir"]; p = c["parms"]
        th = np.asarray(d["theta_deg"], float); wd = np.asarray(d["w"], float); wd = wd / wd.sum()
        sea = dict(T=[float(d["T"])], wf=[1.0], th=th, wd=wd, a_sum=float(d["a_sum"]), x_f=float(d["x_f"]), t_f=float(d.get("t_f", 0.0)))
        lay = dict(LAY_D, sd_gen=float(p["sd_gen"]), sd_sw=float(p["sd_sw"]))
        Fx = frac_table(sea["T"], th, lay)
        AL = lin_maps(sea, sea["x_f"])[0]; AP = lin_maps(sea, sea["x_f"], Fx)[0]
        # FLIP harmonic map
        import glob as _g
        H = B.GA52.Blocks(rd, "hf", "eta")
        eta0 = float(B.jload(rd + "/e51/judge_E05.json")["eta0"])
        fr = [f for f in H.frames() if t_win[0] <= (f - 1) / B.FPS < t_win[1] - 1e-9]
        from scipy import ndimage as ndi
        E = []
        for f in fr:
            a, meta = H.get(f)
            a = ndi.median_filter(np.nan_to_num(a, nan=-30.0), size=3, mode="nearest")
            x0 = float(meta["x0"]); z0 = float(meta["z0"])
            ix = np.round(X - x0).astype(int); iy = np.round(Y - z0).astype(int)
            E.append(a[np.ix_(iy, ix)] - eta0)
        E = np.asarray(E); t = (np.asarray(fr, float) - 1) / B.FPS
        om = 2 * math.pi / float(d["T"])
        M = np.stack([np.ones_like(t)] + sum([[np.cos(k * om * (t - sea["t_f"])), np.sin(k * om * (t - sea["t_f"]))] for k in (1, 2, 3)], []), 1)
        Cf = np.linalg.pinv(M) @ E.reshape(len(t), -1)
        AF = (Cf[1] + 1j * Cf[2]).reshape(NY, len(X))
        sx = (X >= SCAN_X[0]) & (X <= SCAN_X[1])

        def peak2d(A):
            v = np.where(sx[None, :], np.abs(A), np.nan); j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            return dict(x=float(X[ix]), y=float(Y[iy]), amp=float(v[iy, ix]))

        def peakc(A):
            v = np.where(sx, np.abs(A[0]), np.nan); i = int(np.nanargmax(v))
            return dict(x=float(X[i]), amp=float(v[i]))
        # crest scan of the frames
        e2 = np.where(sx[None, None, :], E, np.nan).reshape(len(t), -1)
        cm = np.nanmax(e2, 1); jx = np.nanargmax(e2, 1) % len(X)
        top = cm >= np.percentile(cm, 90)
        Rr = regress(AF[None, :, :][0], AP)
        out[nm] = dict(x_f=sea["x_f"], sd_gen=lay["sd_gen"], sd_sw=lay["sd_sw"], LIN_2d=peak2d(AL), LINap_2d=peak2d(AP), FLIP_harm_2d=peak2d(AF),
                       LIN_centre=peakc(AL), LINap_centre=peakc(AP), FLIP_harm_centre=peakc(AF),
                       FLIP_scan_top10=dict(x_median=float(np.median(X[jx[top]])), crest_median=float(np.median(cm[top])), n=int(top.sum())),
                       judge_median_x_scan=float(np.median([q["x_scan"] for q in B.jload(rd + "/e51/judge_E05.json")["periods"] if q.get("x_scan")])),
                       R_ap_abs={("x%d" % int(xv)): round(float(np.abs(Rr[i])), 3) for i, xv in enumerate(X) if (xv - 0.5) % 20 == 0 and 100 <= xv <= 300},
                       aperture_centre={("x%d" % int(xv)): round(float(np.abs(AP[0, i]) / max(np.abs(AL[0, i]), 1e-9)), 3) for i, xv in enumerate(X)
                                        if (xv - 0.5) % 20 == 0 and 140 <= xv <= 300})
        print(nm, json.dumps({k: v for k, v in out[nm].items() if k not in ("R_ap_abs", "aperture_centre")}), flush=True)
    B.jdump(out, B.OUT + "/calscreen_validate.json")
    return out


if __name__ == "__main__":
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if a[:1] == ["calib"]:
        calib()
    elif a[:1] == ["validate"]:
        validate()
    elif a[:1] == ["cs1"]:
        cs1 = build_cs1()
        cs1["self_check"] = predict(cs1, label="self-check: DFG-2B-E as run")
        # transfer check on the independent FLIP51 T 7 runs with the n = 4 (T 7) efficiencies (amplitude field |A| peak, x 150-300 m)
        val = B.jload(B.OUT + "/calscreen_validate.json") if os.path.exists(B.OUT + "/calscreen_validate.json") else {}
        e4 = cs1["eff"][1]
        chk = {}
        sx = (X >= SCAN_X[0]) & (X <= SCAN_X[1])
        for nm, rd in VAL_RUNS.items():
            c_ = B.jload(rd + "/cfg.json"); d_ = c_["dir"]; p_ = c_["parms"]
            th_ = np.asarray(d_["theta_deg"], float); wd_ = np.asarray(d_["w"], float); wd_ = wd_ / wd_.sum()
            sea_ = dict(T=[float(d_["T"])], wf=[1.0], th=th_, wd=wd_, a_sum=float(d_["a_sum"]), x_f=float(d_["x_f"]), t_f=0.0)
            lay_ = dict(LAY_D, sd_gen=float(p_["sd_gen"]), sd_sw=float(p_["sd_sw"]))
            A_ = model_maps(sea_, sea_["x_f"], lay_, [dict(e_in=complex(*e4["e_in"]), e_sd=complex(*e4["e_sd"]), damp_per_m=e4["damp_per_m"])])[0]
            v_ = np.where(sx[None, :], np.abs(A_), np.nan); j_ = int(np.nanargmax(v_)); iy_, ix_ = np.unravel_index(j_, v_.shape)
            chk[nm] = dict(x_f=sea_["x_f"], CS1_peak_x=float(X[ix_]), CS1_peak_amp=float(v_[iy_, ix_]), LIN_peak_x=(val.get(nm) or {}).get("LIN_2d", {}).get("x"),
                           FLIP_harm_peak_x=(val.get(nm) or {}).get("FLIP_harm_2d", {}).get("x"), FLIP_scan_top10_x=(val.get(nm) or {}).get("FLIP_scan_top10", {}).get("x_median"),
                           judge_median_x_scan=(val.get(nm) or {}).get("judge_median_x_scan"))
        cs1["transfer_check_T7"] = dict(runs=chk, rule="CS1 with the DFG-2B-E n 4 (T 7) efficiencies applied to the monochromatic T 7 X2 / X2B' designs "
                                                       "(a_sum 6.33 m, their own side-band extents); FLIP numbers from calscreen_validate.json [calibrated vs measured]")
        B.jdump(cs1, B.OUT + "/cs1_model.json")
        print(json.dumps(dict(eff=cs1["eff"], kappa=cs1["kappa"], conv=cs1["self_check"]["converged"], lip=cs1["self_check"]["lip"],
                              measured=cs1["measured"]), default=float))
    elif a[:1] == ["predict"]:
        cs1 = B.jload(B.OUT + "/cs1_model.json")
        kw = {}
        for v in sys.argv[1:]:
            if v.startswith("--dphi="):
                kw["dphi"] = [float(q) for q in v.split("=")[1].split(",")]
            if v.startswith("--sdgen="):
                g_, w_ = [float(q) for q in v.split("=")[1].split(",")]
                kw["lay"] = dict(LAY_D, sd_gen=g_, sd_sw=w_)
            if v.startswith("--label="):
                kw["label"] = v.split("=", 1)[1]
        xf = float(a[1]) if len(a) > 1 else None
        r = predict(cs1, x_f=xf, **kw)
        tag = (kw.get("label") or ("xf%s" % (a[1] if len(a) > 1 else "base"))).replace(" ", "_").replace("/", "_")
        B.jdump(r, B.OUT + "/cs1_%s.json" % tag)
        print(json.dumps(dict(conv=r["converged"], lip=r["lip"], G6=r["G6_window_ok"]), default=float))
    else:
        print(__doc__)
