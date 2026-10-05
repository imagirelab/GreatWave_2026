# -*- coding: utf-8 -*-
"""Q20 final K*': post-warp relaxation of the sheet (no reference data).
  crest_floor(): per row, iterative curvature-limited smoothing inside +-win m (arc) of the row top, until the Q17-style
                 radius (0.1 m resample, 3-tap) is >= rmin everywhere in the window (F02 round top), with a small
                 column-space Laplacian so that no vertex moves more than cap.
  cross_rows(): Gaussian smoothing of the grid along the crest (rows, sigma in metres of c) with a per-vertex weight
                (F11 cross-row creases / zig-zag); rows stay planar (only A, Y change).
"""
import numpy as np
from scipy.ndimage import gaussian_filter1d


def q17_curv(a, y, jm, win):
    s = np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]
    ss = np.arange(max(s[jm] - win, 0), min(s[jm] + win, s[-1]), 0.1)
    P = np.stack([np.interp(ss, s, a), np.interp(ss, s, y)], -1)
    d1 = np.gradient(P, 0.1, axis=0); d2 = np.gradient(d1, 0.1, axis=0)
    k = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.linalg.norm(d1, axis=1) ** 3, 1e-12)
    return ss, np.convolve(k, np.ones(3) / 3, "same"), s


def crest_floor(A, Y, c, rows, rmin, win=3.2, iters=60, jmax=200, step=0.35):
    A = A.copy(); Y = Y.copy()
    for r in rows:
        a, y = A[r].copy(), Y[r].copy()
        for it in range(iters):
            jm = int(np.argmax(y[:jmax]))
            ss, ks, s = q17_curv(a, y, jm, win + 0.3)
            bad = ss[np.abs(ks) > 1.0 / rmin]
            bad = bad[np.abs(bad - s[jm]) <= win + 0.05]
            if len(bad) == 0:
                break
            # columns within 0.35 m (arc) of a bad sample: Laplacian step toward the neighbour mean
            cols = np.unique(np.concatenate([np.nonzero(np.abs(s - b) < 0.35)[0] for b in bad]))
            cols = cols[(cols > 0) & (cols < len(a) - 1)]
            na = 0.5 * (a[cols - 1] + a[cols + 1]); ny = 0.5 * (y[cols - 1] + y[cols + 1])
            a[cols] += step * (na - a[cols]); y[cols] += step * (ny - y[cols])
        A[r], Y[r] = a, y
    return A, Y


def cross_rows(A, Y, c, sig_m, weight=None, iters=1):
    """weighted Gaussian smoothing of every column along the rows (sigma in metres of c)."""
    nv, nu = A.shape
    sg = np.broadcast_to(np.asarray(sig_m, float), c.shape)[:, None]
    Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sg) ** 2); Wm /= Wm.sum(1, keepdims=True)
    A2, Y2 = A.copy(), Y.copy()
    for _ in range(iters):
        As = Wm @ A2; Ys = Wm @ Y2
        w = np.ones_like(A2) if weight is None else weight
        A2 = A2 + w * (As - A2); Y2 = Y2 + w * (Ys - Y2)
    return A2, Y2


def cross_rows_ll(A, Y, c, sig_m, weight=None, iters=1):
    """loop 2: LOCAL-LINEAR Gaussian smoothing of every column along the rows (sigma in metres of c).  Unlike the plain
    Gaussian average it keeps linear trends at the ends of the sheet (the tail that runs into the sea is not lifted:
    the plain average raised the last row of the far tail to 4.5 m, which showed as a cut slab)."""
    nv, nu = A.shape
    sg = np.broadcast_to(np.asarray(sig_m, float), c.shape)[:, None]
    D = c[None, :] - c[:, None]
    Wm = np.exp(-0.5 * (D / sg) ** 2)
    S0 = Wm.sum(1); S1 = (Wm * D).sum(1); S2 = (Wm * D * D).sum(1)
    den = np.maximum(S0 * S2 - S1 * S1, 1e-12)
    L = (Wm * S2[:, None] - Wm * D * S1[:, None]) / den[:, None]      # rows sum to 1, first moment 0
    A2, Y2 = A.copy(), Y.copy()
    for _ in range(iters):
        As = L @ A2; Ys = L @ Y2
        w = np.ones_like(A2) if weight is None else weight
        A2 = A2 + w * (As - A2); Y2 = Y2 + w * (Ys - Y2)
    return A2, Y2


def cross_rows_norm(A, Y, c, sig_m, weight=None, iters=1):
    """loop 2: Gaussian smoothing along the rows of the row SHAPE (a relative to the row's crest a, both divided by the
    row height), then rescaled with each row's own height and crest position: the height profile H(c) and the crest
    line are kept (the far tail that runs into the sea is not lifted by the one-sided average at the sheet's end)."""
    nv, nu = A.shape
    H = np.maximum(Y.max(1), 0.3)[:, None]
    jt = np.argmax(Y[:, :200], 1)
    aT = A[np.arange(nv), jt][:, None]
    An = (A - aT) / H; Yn = Y / H
    An2, Yn2 = cross_rows(An, Yn, c, sig_m, weight=weight, iters=iters)
    return aT + An2 * H, Yn2 * H
