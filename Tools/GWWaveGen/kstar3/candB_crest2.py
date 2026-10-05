# -*- coding: utf-8 -*-
"""Q20 candidate B, step 4: the back-left second crest (Q16 point 5, art direction ds_second_crest).

On the near shoulder (c -16.5 .. -3), the outer part of each row's lip becomes a tier: the lip top dips after the
main crest and rises again to a ridge (the painted second crest line), whose front drops to a hooked claw edge; the
tube pocket under the hook is the painted indigo island.  Heights come from the painting: the top and bottom edges of
the painted foam band are back-projected along PaintingCam rays onto each row plane at the ridge / tip positions.
The ridge protrusion is modulated in three lobes A / B / C (c ranges from the Q16 study of the painting and of the
reference model's lobe count); the form is ours (no reference geometry is read)."""
import numpy as np
from scipy.interpolate import PchipInterpolator
from candB_common import *
from candB_geom import resample, row_inside, sanitize
from candB_zbuf import band_mask_display
import candB_tube as TUBE

LOBES = {"A": (-11.0, -7.8), "B": (-14.0, -11.0), "C": (-17.0, -14.0)}   # where the painted band lands on the shoulder rows (first-hit surfaces)
_EDGE = {}


def band_edges():
    if "top" not in _EDGE:
        B = band_mask_display()
        top = []; bot = []
        for x in range(236, 711):
            col = np.nonzero(B[:, x])[0]
            if len(col):
                top.append((x, col.min())); bot.append((x, col.max()))
        _EDGE["top"] = np.array(top, float); _EDGE["bot"] = np.array(bot, float)
    return _EDGE["top"], _EDGE["bot"]


def backproj(pts, cc):
    g = gate_env(); cam = g["fr"].cam
    d = cam.rays(pts); p0 = O + cc * E
    s = ((p0 - cam.pos) @ E) / (d @ E)
    X = cam.pos[None, :] + s[:, None] * d
    Q = X - O
    return np.stack([Q @ T, X[:, 1]], -1)


def edge_height(which, cc, a_at):
    top, bot = band_edges()
    P = backproj(top if which == "top" else bot, cc)
    o = np.argsort(P[:, 0])
    if a_at < P[o[0], 0] or a_at > P[o[-1], 0]:
        return None
    # the edge is noisy (claw tendrils): median of the points within +-0.6 m of a_at
    m = np.abs(P[:, 0] - a_at) < 0.6
    return float(np.median(P[m, 1])) if m.any() else float(np.interp(a_at, P[o, 0], P[o, 1]))


def lobe_mod(cc):
    m = 0.0
    for k, (c0, c1) in LOBES.items():
        u = (cc - c0) / (c1 - c0)
        if 0 <= u <= 1:
            m = max(m, 0.5 * (1 - np.cos(2 * np.pi * u)))
    return m


def tier_params(a, y, cc, prm):
    jt = int(np.argmax(y[:200])); ac, H = a[jt], y[jt]
    m = lobe_mod(cc)
    prot = prm["tier_prot0"] + prm["tier_prot1"] * m
    a_t = a[200] - prm["tier_tip_back"] * (1 - m)
    a_r = a_t - prot
    y_r = edge_height("top", cc, a_r); y_b = edge_height("bot", cc, a_t)
    return {"m": m, "prot": prot, "a_t": a_t, "a_r": a_r, "y_r": y_r, "y_b": y_b, "H": H, "ac": ac}


def tier_row(a, y, cc, lk, prm, tp):
    jt = int(np.argmax(y[:200])); ac, H = a[jt], y[jt]
    a_t, a_r, prot = tp["a_t"], tp["a_r"], tp["prot"]
    y_r = min(tp["y_r"], H - prm["tier_step_min"]); y_b = min(tp["y_b"], y_r - 0.8)
    j_s = jt + 12
    ps = np.array([a[j_s], y[j_s]])
    if a_r < ps[0] + 1.0:
        return a, y, None
    a_d = 0.5 * (ps[0] + a_r); y_d = min(y_r - prm["tier_dip"], np.interp(a_d, a[jt:201], y[jt:201]))
    xs = [ps[0], a_d, a_r, a_r + 0.45 * prot]
    ys = [ps[1], y_d, y_r, y_r - 0.25 * (y_r - y_b)]
    if not np.all(np.diff(xs) > 0.2):
        return a, y, None
    f = PchipInterpolator(xs, ys)
    xa = np.linspace(xs[0], xs[-1], 200)
    top = np.stack([xa, f(xa)], -1)
    p0 = top[-1]; p2 = np.array([a_t, y_b]); p1 = np.array([a_t + 0.3, p0[1] - 0.2 * (p0[1] - y_b)])
    tt = np.linspace(0, 1, 60)[:, None]
    front = (1 - tt) ** 2 * p0 + 2 * (1 - tt) * tt * p1 + tt ** 2 * p2
    curve = np.vstack([top, front[1:]])
    a2 = a.copy(); y2 = y.copy()
    Q = resample(curve, 200 - j_s + 1)
    a2[j_s:201] = Q[:, 0]; y2[j_s:201] = Q[:, 1]
    return a2, y2, {"a_r": a_r, "y_r": y_r, "a_t": a_t, "y_b": y_b, "lobe": tp["m"]}


def step4_crest2(A, Y, c, lk, prm, log=print):
    """two passes: painting heights per row (gaps filled along c, then smoothed), then the tier lip top.
    Only columns up to the lip tip (200) change here; the tube under the new tip is rebuilt by step 5."""
    from scipy.ndimage import gaussian_filter1d as g1
    A = A.copy(); Y = Y.copy(); info = {}
    rows = [r for r in range(NV) if prm["tier_c0"] - 1.0 <= c[r] <= prm["tier_c1"] + 3.0]
    tps = [tier_params(A[r], Y[r], c[r], prm) for r in rows]
    cr = np.array([c[r] for r in rows])
    for key in ("y_r", "y_b"):
        v = np.array([np.nan if t[key] is None else t[key] for t in tps])
        ok = np.isfinite(v)
        if ok.sum() < 3:
            return A, Y, info
        v = np.interp(cr, cr[ok], v[ok])          # fill (constant extrapolation at the ends)
        v = g1(v, 2.0, mode="nearest")
        for t, x in zip(tps, v):
            t[key] = float(x)
    for r, tp in zip(rows, tps):
        cc = c[r]
        w = smoothstep((cc - prm["tier_c0"]) / 1.5) * smoothstep((prm["tier_c1"] + 1.8 - cc) / 2.4)
        if w <= 0:
            continue
        a2, y2, inf = tier_row(A[r], Y[r], cc, lk[r], prm, tp)
        if inf is None:
            continue
        a3 = (1 - w) * A[r] + w * a2; y3 = (1 - w) * Y[r] + w * y2
        free = ~lk[r]
        a3[~free] = A[r, ~free]; y3[~free] = Y[r, ~free]
        bad = ~row_inside(a3, y3, cc, prm["margin_px"]) & (y3 > 2.5) & free
        for t in np.linspace(0.8, 0.0, 5):
            if not bad.any():
                break
            a3[bad] = A[r, bad] + t * (a3[bad] - A[r, bad]); y3[bad] = Y[r, bad] + t * (y3[bad] - Y[r, bad])
            bad = ~row_inside(a3, y3, cc, prm["margin_px"]) & (y3 > 2.5) & free
        A[r], Y[r] = sanitize(a3, y3, keep=~free); info[int(r)] = inf
    return A, Y, info


def s1_fraction(A, Y, c, prm):
    """share of the painted foam-band pixels whose PaintingCam ray first hits the tier (lip outer part of the
    shoulder rows c -17..-2.5, columns from 20 before the ridge to the hook)."""
    from candB_zbuf import id_raster
    B = band_mask_display()
    rid, cid, zb = id_raster(A, Y, c, 230, 720, 330, 625, rows=range(60, 165), step=2)
    Bs = B[330:625:2, 230:720:2][:rid.shape[0], :rid.shape[1]]
    r = rid[Bs]; j = cid[Bs]
    ok = (r >= 0)
    cr = np.where(ok, c[np.clip(r, 0, NV - 1)], 99)
    tier = ok & (cr >= -17) & (cr <= -2.5) & (j >= 150) & (j <= 230)
    return float(tier.sum() / max(Bs.sum(), 1)), int(Bs.sum())
