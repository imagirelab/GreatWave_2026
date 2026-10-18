# -*- coding: utf-8 -*-
"""FLIP52B2 diagnosis step 2: WHERE and WHEN the DFG-2B-E focus forms, and why it is seaward of the design (py -3.10 -B; numpy).
2026-10-18 written new (Claude). Reads diag/harm_DFGB2E.npz (b2_harm.py) and the run's hf / judge (read only); writes diag/focus_DFGB2E.json.

Fields compared on the same cells (x 0.5-340.5 m, y 0.5-95.5 m, t' = t - t_fn over [-10, +8] s, one group):
  LIN     linear design: the WKB DirField per harmonic, all 34 directions (= the g52b table / dfg52b screen eta1) [computed]
  LINap   LIN with each component weighted by its generated fraction (rays traced back from the centre-row point (x, 0) through the refracting
          bed: inlet band x <= 100 m -> 1; crossing the side band edge y 95 m at x <= 180.25 m -> 1, fading to 0 at 210.25 m), per column x
          [computed]; the aperture loss vs x
  CAL     calibrated linear: LIN x R_n(x) per harmonic, R_n(x) = the measured complex lateral regression FLIP / LIN over y <= 95 m (b2_harm W2)
          [calibrated]; CAL_amp (|R_n| only), CAL_ph (arg R_n only), CAL_in (R_n frozen at its x 110 m value = the inlet calibration error only)
  F3      FLIP's own periodic 3-layer field: sum_n Re(A_fit,n e^{-i w_n t'}) from the harmonic maps (W2) [measured]
  F3+     F3 + the nuisance harmonics 1, 2, 6, 7, 8 and the mean (the periodic part of the hf incl. bound / set-down terms) [measured]
  FLIP    the 3x3-median hf - eta0 of the three groups [measured]
Per field: the 'converged' instant = the largest crest over x 150-300 m, y <= 95 m in [t_fn - 8, t_fn + 2] s (the judge rule), its x, t',
Hc, e51 widths / core miss; the centre-row focus function max_t eta(x, y 0.5, t) and its argmax.
usage: py -3.10 -B b2_focus.py
Tags: [measured] [computed] [calibrated].
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b2_common as B                   # noqa: E402
import numpy as np                      # noqa: E402

TREL = np.arange(-10.0, 8.0 + 1e-9, 1.0 / 24.0)
CONV_T = (-8.0, 2.0)
SCAN_X = (150.0, 300.0)
NY = 96                                  # rows y 0.5 .. 95.5


def frac_at(x_t, sea, lay=dict(x_in=100.0, sd0=95.0, sd_gen=180.25, sd_sw=210.25, W=140.0)):
    """generated fraction per (layer, direction) of the components reaching (x_t, 0) [computed, ray tracing as g50_dirfield.aperture]."""
    xg = np.arange(0.0, max(x_t, 101.0) + 0.5, 0.5)
    out = []
    for T, w in zip(sea["T"], sea["wf"]):
        d = B.DF.DirField(T, sea["th"], sea["wd"], sea["a_sum"] * w, np.union1d(xg, [x_t]), B.BED, x_t)
        fr = []
        for j in range(len(d.a)):
            xs, yy = d.ray_back(j, lay["x_in"])
            if yy[-1] <= lay["W"] + 1e-9:
                f = 1.0
            else:
                i = int(np.argmax(yy >= lay["sd0"])); xc = float(xs[i])
                f = 1.0 if xc <= lay["sd_gen"] else (0.0 if xc >= lay["sd_sw"] else 1.0 - (xc - lay["sd_gen"]) / (lay["sd_sw"] - lay["sd_gen"]))
            fr.append(f)
        out.append(fr)
    return np.array(out)


def recon(Amaps, oms, extra=None):
    """function t' -> field (ny, nx) = sum_n Re(A_n e^{-i w_n t'}) (+ extra(t'))."""
    def f(tp):
        e = np.zeros(Amaps[0].shape)
        for A, om in zip(Amaps, oms):
            e += np.real(A * np.exp(-1j * om * tp))
        if extra is not None:
            e += extra(tp)
        return e
    return f


def half_frame(e, X):
    """(96, nx) field on x 0.5.. -> (140, 412) half-tank array (NaN outside) for the frozen ruler."""
    a = np.full((140, 412), np.nan)
    a[:e.shape[0], :e.shape[1]] = e
    return a


META = dict(x0=0.5, dx=1.0, z0=0.5, dz=1.0)


def analyse_field(fun, X, label, centre=True):
    xs = X
    sx = (xs >= SCAN_X[0]) & (xs <= SCAN_X[1])
    best = (-1e9, None)
    cmax = np.full(len(xs), -1e9); ct = np.zeros(len(xs))
    track = []
    for tp in TREL:
        e = fun(tp)
        if CONV_T[0] - 1e-9 <= tp <= CONV_T[1] + 1e-9:
            v = np.where(sx[None, :], e[:NY], np.nan)
            j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            if v[iy, ix] > best[0]:
                best = (float(v[iy, ix]), tp)
        if centre:
            r = e[0]
            m = r > cmax; cmax[m] = r[m]; ct[m] = tp
            i = int(np.nanargmax(np.where(sx, r, np.nan))); track.append((float(tp), float(xs[i]), float(r[i])))
    Hc, tb = best
    eb = fun(tb)
    m = B.EM.hf_metrics(half_frame(eb[:NY], X), META, 0.0, xwin=SCAN_X)
    out = dict(label=label, conv=dict(t_rel=tb, Hc=m.get("Hc"), x=m.get("x_pk"), y=m.get("y_pk"), h=float(B.h_of(m.get("x_pk")))))
    if m and "W50" in m:
        miss, per = B.EM.score_vs_target(m)
        out["conv"].update(W50=m["W50"], W80=m["W80"], W95=m["W95"], K=m["K"], S2=m["S2"], miss=miss, W50_m=m["W50"] * m["Hc"])
    if centre:
        i = int(np.argmax(np.where(sx, cmax, -1e9)))
        out["centre_focus"] = dict(x=float(xs[i]), t_rel=float(ct[i]), crest=float(cmax[i]))
        out["centre_crest_vs_x"] = {("x%d" % int(xv)): [round(float(cmax[k]), 3), round(float(ct[k]), 3)] for k, xv in enumerate(xs) if (xv - 0.5) % 10 == 0 and 150 <= xv <= 300}
        out["_track"] = track
    return out


def main():
    t0 = time.time()
    c = B.cfg(); sea = B.sea_of(c)
    Z = np.load(B.OUT + "/harm_DFGB2E.npz")
    X = Z["x"]; Y = Z["y"]; ns = [int(v) for v in Z["ns"]]; oms = [float(v) for v in Z["om"]]
    W = "W2"
    AL = [Z["lin_n%d" % n].astype(complex)[:NY] for n in ns]
    AF = [np.nan_to_num(Z["%s_n%d" % (W, n)].astype(complex)[:NY]) for n in ns]
    nuis = {n: np.nan_to_num(Z["%s_n%d" % (W, n)].astype(complex)[:NY]) for n in (1, 2, 6, 7, 8)}
    mean = np.nan_to_num(Z["%s_mean" % W].astype(float)[:NY])
    res = dict(window=W, date=time.strftime("%Y-%m-%d %H:%M:%S"))
    # ---- per-x complex regression R_n(x) over y <= 95 (the calibration of the linear screen)
    R = []
    for A, L in zip(AF, AL):
        num = np.sum(A * np.conj(L), 0); den = np.sum(np.abs(L) ** 2, 0)
        R.append(num / np.where(den > 0, den, np.nan))
    R = [np.nan_to_num(r, nan=0.0) for r in R]
    i110 = int(np.argmin(np.abs(X - 110.5)))
    # ---- aperture: generated fraction per column (centre-row point) [computed]
    xs_ap = np.arange(120.5, 300.6, 10.0)
    ap_rows = []
    fr_x = {}
    for xt in xs_ap:
        fr = frac_at(float(xt), sea)
        fr_x[float(xt)] = fr
        dfs, xg = B.dirfields(np.array([xt]), sea)
        i = int(np.argmin(np.abs(xg - xt)))
        full = [float(np.abs(np.sum(d.Aj[:, i] * np.exp(1j * d.Phi[:, i])))) for d in dfs]
        gen = [float(np.abs(np.sum(fr[k] * d.Aj[:, i] * np.exp(1j * d.Phi[:, i])))) for k, d in enumerate(dfs)]
        ap_rows.append(dict(x=float(xt), h=float(B.h_of(xt)), centre_amp_full=full, centre_amp_generated=gen,
                            aperture=[g / f if f > 0 else None for g, f in zip(gen, full)],
                            aperture_all=sum(gen) / sum(full)))
    res["aperture_vs_x"] = dict(rows=ap_rows, rule="|sum_j frac_j A_j e^{i Phi_j}| / |sum_j A_j e^{i Phi_j}| at (x, 0): the phase-aligned design amplitude of the "
                                                   "generated components over all components (rays from (x, 0)) [computed]")
    # LINap field: frac per column interpolated from the 10 m table
    dfs, xg = B.dirfields(X, sea)
    idx = np.array([int(np.argmin(np.abs(xg - v))) for v in X])
    ALap = []
    for k, d in enumerate(dfs):
        Fk = np.array([fr_x[float(xs_ap[min(max(int(round((xv - 120.5) / 10.0)), 0), len(xs_ap) - 1)])][k] for xv in X])   # (nx, ndir)
        A = np.zeros((NY, len(X)), complex)
        for j in range(len(d.a)):
            A += np.exp(1j * d.ky[j] * Y[:NY])[:, None] * (Fk[:, j] * d.Aj[j, idx] * np.exp(1j * d.Phi[j, idx]))[None, :]
        ALap.append(A)
    # ---- fields
    fields = {
        "LIN": recon(AL, oms),
        "LINap": recon(ALap, oms),
        "CAL": recon([r[None, :] * L for r, L in zip(R, AL)], oms),
        "CAL_amp": recon([np.abs(r)[None, :] * L for r, L in zip(R, AL)], oms),
        "CAL_ph": recon([np.exp(1j * np.angle(r))[None, :] * L for r, L in zip(R, AL)], oms),
        "CAL_in": recon([np.where(X > 110.5, r[i110], r)[None, :] * L for r, L in zip(R, AL)], oms),
        "CAL_amp_in_ph": recon([(np.abs(r) * np.exp(1j * np.angle(np.where(X > 110.5, r[i110], r))))[None, :] * L for r, L in zip(R, AL)], oms),
        "F3": recon(AF, oms),
        "F3+": recon(AF, oms, extra=lambda tp: mean + sum(np.real(nuis[n] * np.exp(-1j * 2 * math.pi * n / sea["P"] * tp)) for n in nuis)),
    }
    out = {}
    for nm, f in fields.items():
        out[nm] = analyse_field(f, X, nm)
        print(nm, json.dumps(out[nm]["conv"]), out[nm].get("centre_focus"), round(time.time() - t0, 1), flush=True)
    # ---- the measured FLIP groups (3x3 median hf), same rule, centre-row focus function
    J = B.jload(B.JUDGE); eta0 = float(J["eta0"])
    flip = []
    for g in J["groups"]:
        tfn = g["t_fn"]
        f_lo = int(round((tfn - 10.0) * B.FPS)) + 1; f_hi = int(round((tfn + 8.0) * B.FPS)) + 1
        t, E, meta, fr = B.load_frames(f_lo, f_hi, rows=np.arange(140), xcols=np.arange(len(X)), med3=True)
        E = E.astype(float) - eta0
        tm = {round(tt - tfn, 4): i for i, tt in enumerate(t)}
        fun = (lambda E_, tm_: (lambda tp: E_[tm_[min(tm_, key=lambda q: abs(q - tp))]]))(E, tm)
        o = analyse_field(fun, X, "FLIP_g%d" % g["n"])
        o["judge_conv"] = g["conv"]
        flip.append(o)
        print("FLIP", g["n"], json.dumps(o["conv"]), o.get("centre_focus"), flush=True)
    out["FLIP"] = flip
    for k in out:
        if isinstance(out[k], dict):
            out[k].pop("_track", None)
    for o in flip:
        o.pop("_track", None)
    res["fields"] = out
    res["R_x"] = {("n%d" % n): dict(x=X[::5], abs=np.abs(R[k])[::5], phase=np.angle(R[k])[::5], delay_s=(np.angle(R[k]) / oms[k])[::5]) for k, n in enumerate(ns)}
    res["rule"] = __doc__.split("Fields compared")[1].split("usage")[0]
    res["cpu_s"] = round(time.time() - t0, 1)
    np.savez_compressed(B.OUT + "/calR_DFGB2E.npz", x=X, ns=np.array(ns), om=np.array(oms), **{"R_n%d" % n: R[k] for k, n in enumerate(ns)})
    B.jdump(res, B.OUT + "/focus_DFGB2E.json")
    print("cpu", res["cpu_s"])


if __name__ == "__main__":
    main()
