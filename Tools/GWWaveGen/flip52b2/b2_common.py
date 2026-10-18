# -*- coding: utf-8 -*-
"""FLIP52B2 (DFG-2B round 2) shared helpers for the DIAGNOSIS of the DFG-2B-E 0.5 m run and the calibrated linear screen
(py -3.10 -B; numpy, scipy). 2026-10-18 written new (Claude).

Nothing of FLIP52B / FLIP52S2 is edited: the run folder, its cfg and the frozen tools are READ ONLY. Imports READ ONLY:
  flip50/g50_dirfield (WKB DirField: kdisp, cg, bed_h, DirField), flip51/e51_metrics (frozen ruler: median3, hf_metrics, score_vs_target),
  flip52/g52_ana (generic readers: Blocks, still offset, harmonic_fit, r2 lip test), flip52/g52_common (dirset, freqset).
Writes only under Unity/Build/FLIP52B2/ (diag/, _scratch/).
The sea of the run is read from the run's own cfg.json (dir: a_sum, theta, weights, harmonics, x_f, t_f), never from G52B_SEA.
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, math

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = os.environ.get("B2_THREADS", "2")      # a Houdini sim shares the machine: numpy stays at 1-2 threads
REPO = "G:/Unity/GreatWave_2026_Fresh"
T50 = REPO + "/Tools/GWWaveGen/flip50"
T51 = REPO + "/Tools/GWWaveGen/flip51"
T52 = REPO + "/Tools/GWWaveGen/flip52"
for _p in (T50, T51, T52):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                      # noqa: E402
import g50_dirfield as DF               # noqa: E402  read only
import e51_metrics as EM                # noqa: E402  read only (frozen ruler)
import g52_ana as GA52                  # noqa: E402  read only (readers, harmonic_fit, lips)
import g52_common as G52                # noqa: E402  read only (dirset, freqset)

RUN = REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5"
JUDGE = RUN + "/g52b/judge_DFGB.json"
COEQ = RUN + "/g52b/coequal_DFGB.json"
PV53 = REPO + "/Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json"
OUT = REPO + "/Unity/Build/FLIP52B2/diag"
SCR = REPO + "/Unity/Build/FLIP52B2/_scratch"
FPS = 24.0
G = DF.G
BED = dict(h0=19.0, x_toe=160.25, s=10.0, kind="beach")     # D19B (cfg bed: ridge_shelf with k 0 = the straight 1:10 beach)
INTERIOR_Y = 95.0


def jload(p):
    with open(p, encoding="utf8") as fh:
        return json.load(fh)


def jdump(o, p):
    def cl(v):
        if isinstance(v, dict):
            return {str(k): cl(w) for k, w in v.items()}
        if isinstance(v, (list, tuple)):
            return [cl(w) for w in v]
        if isinstance(v, (np.floating, float)):
            return None if not np.isfinite(v) else round(float(v), 6)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, np.ndarray):
            return cl(v.tolist())
        if isinstance(v, complex):
            return [round(v.real, 6), round(v.imag, 6)]
        return v
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf8") as fh:
        json.dump(cl(o), fh, ensure_ascii=False, indent=1)


def h_of(x):
    x = np.asarray(x, float)
    return BED["h0"] - np.maximum(x - BED["x_toe"], 0.0) / BED["s"]


def x_of_h(h):
    return BED["x_toe"] + (BED["h0"] - np.asarray(h, float)) * BED["s"]


def cfg():
    return jload(RUN + "/cfg.json")


def sea_of(c=None):
    """the run's sea from its cfg (dir block) [measured from the cfg]."""
    c = c or cfg()
    d = c["dir"]
    return dict(P=float(d["P"]), ns=[int(v) for v in d["harmonics"]], T=[float(v) for v in d["T"]], om=[float(v) for v in d["omega"]],
                wf=[float(v) for v in d["freq_weights"]], th=np.asarray(d["theta_deg"], float), wd=np.asarray(d["dir_weights"], float),
                a_sum=float(d["a_sum"]), x_f=float(d["x_f"]), t_f=float(d["t_f"]), foci=[float(v) for v in d["foci"]])


def dirfields(x, sea=None, x_f=None, a_scale=1.0):
    """one WKB DirField per harmonic (phases 0 at (x_f, 0), t_f), on the x grid given (exactly g52b_table.dirfields with the run's sea)."""
    s = sea or sea_of()
    xf = s["x_f"] if x_f is None else float(x_f)
    xg = np.union1d(np.asarray(x, float), [xf])
    return [DF.DirField(T, s["th"], s["wd"], s["a_sum"] * a_scale * w, xg, BED, xf) for T, w in zip(s["T"], s["wf"])], xg


def lin_maps(x, y, sea=None, x_f=None, frac=None):
    """complex linear amplitude maps A_n(y, x) (eta_n = Re(A_n e^{-i w_n (t - t_f)})) on the grid given. frac: optional per-layer per-direction
    weights (n_layers, n_dir) multiplying the components (aperture: generated fraction)."""
    dfs, xg = dirfields(x, sea, x_f)
    idx = np.array([int(np.argmin(np.abs(xg - v))) for v in np.asarray(x, float)])
    out = []
    y = np.asarray(y, float)
    for n, d in enumerate(dfs):
        A = np.zeros((len(y), len(idx)), complex)
        for j in range(len(d.a)):
            w = 1.0 if frac is None else float(frac[n][j])
            if w == 0.0:
                continue
            A += w * np.exp(1j * d.ky[j] * y)[:, None] * (d.Aj[j, idx] * np.exp(1j * d.Phi[j, idx]))[None, :]
        out.append(A)
    return out, dfs


def design_matrix(t, P, ns, tf, nuis=(1, 2, 6, 7, 8, 9, 10)):
    allns = list(ns) + [n for n in nuis if n not in ns]
    cols = [np.ones_like(t)]
    for n in allns:
        w = 2 * math.pi * n / P
        cols += [np.cos(w * (t - tf)), np.sin(w * (t - tf))]
    return np.stack(cols, 1), allns


def load_frames(f_lo, f_hi, rows=None, xcols=None, med3=False):
    """hf frames f_lo..f_hi (inclusive) -> (t, eta (nt, ny, nx) float32 absolute heights, meta). med3: 3x3 median per frame (C median filter;
    the frozen ruler uses a nan-median, equal away from NaN cells)."""
    from scipy import ndimage as ndi
    H = GA52.Blocks(RUN, "hf", "eta")
    fr = [f for f in H.frames() if f_lo <= f <= f_hi]
    a0, meta = H.get(fr[0])
    ny, nx = a0.shape
    rr = np.arange(ny) if rows is None else np.asarray(rows)
    cc = np.arange(nx) if xcols is None else np.asarray(xcols)
    E = np.empty((len(fr), len(rr), len(cc)), np.float32)
    for i, f in enumerate(fr):
        a, _ = H.get(f)
        if med3:
            a = ndi.median_filter(np.nan_to_num(a, nan=-30.0), size=3, mode="nearest")
        E[i] = a[np.ix_(rr, cc)]
    t = (np.asarray(fr, float) - 1.0) / FPS
    return t, E, meta, np.asarray(fr)


def axes(meta, ny, nx):
    return float(meta["x0"]) + float(meta["dx"]) * np.arange(nx), float(meta["z0"]) + float(meta["dz"]) * np.arange(ny)
