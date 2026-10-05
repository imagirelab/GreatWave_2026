# -*- coding: utf-8 -*-
"""Q21 candidate A3b, step 3: the b-region (the left-shoulder second crest, Q21 "b区域") as a large form.

The painted band (Q16 user region; top edge smoothed as in the rubric F09, lower = claw edge) is cast from PaintingCam
onto the sheet: every band pixel's ray hits the shoulder's front face at a vertex (row, column) with a band coordinate
u (0 at the top edge, 1 at the lower edge).  The tier is a smooth roll on that face: each vertex of the hit region is
moved inside its row plane along the row curve's outward normal by h * B(u) * taper, where B rises quickly below the top
edge (the roll's crest) and falls to 0 at the claw edge; the field is splatted to the grid and smoothed in (row, column)
so the roll is one continuous large form (claws are stage 6).  Iterated: the projected top / lower edges of the roll are
measured (pixels whose vertex carries tier weight > 0.5) and the targets corrected, so that both edges land within
~10 px of the painted band (Q21-3).  Rows stay planar; the grid / landmarks do not change.
usage: py -3.10 candA3b_tier.py in_rows.npz out_rows.npz [params.json]
"""
import sys, os, json, math, time
import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3b_common as B
import fin_eval as FE

X0, X1 = 241.0, 710.0


def band_targets():
    top, bot = B.band_edges()
    xs = np.arange(X0, X1 + 0.1, 2.0)
    t = np.interp(xs, B.B_TOP_SMOOTH[:, 0], B.B_TOP_SMOOTH[:, 1])
    b = np.interp(xs, bot[:, 0], bot[:, 1])
    b = gaussian_filter1d(b, 6.0, mode="nearest")
    return xs, t, b


def ids(fr, V1, c, A, Y):
    nv, nu = A.shape
    X = fr.world(c, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    zb, ib = FE.zbuf_ids(P, V1.triangles(nu, nv), 1920, 1080)
    return ib, P


def tier_field(c, A, Y, fr, V1, xs, top, bot, sig_rc=(2.0, 3.0)):
    """weight W(r, j) and band coordinate U(r, j) of the vertices seen through the band."""
    nv, nu = A.shape
    ib, P = ids(fr, V1, c, A, Y)
    Wsum = np.zeros((nv, nu)); Usum = np.zeros((nv, nu))
    for x, t, b in zip(xs, top, bot):
        ys = np.arange(t, b + 0.1, 1.5)
        xi = int(round(x)); yi = np.round(ys).astype(int)
        v = ib[yi, xi]
        ok = v >= 0
        r = v[ok] // nu; j = v[ok] % nu
        u = (ys[ok] - t) / max(b - t, 1.0)
        np.add.at(Wsum, (r, j), 1.0)
        np.add.at(Usum, (r, j), u)
    Wg = gaussian_filter(Wsum, sig_rc); Ug = gaussian_filter(Usum, sig_rc)
    U = np.where(Wg > 1e-6, Ug / np.maximum(Wg, 1e-9), 0.0)
    Wn = np.clip(Wg / max(np.percentile(Wg[Wg > 1e-6], 60), 1e-9), 0, 1) if (Wg > 1e-6).any() else Wg
    return Wn, U


def tier_field_image(c, A, Y, fr, V1, xs, top, bot, tp):
    """band coordinate straight from the painting-camera image: every vertex on the visible front face (depth within
    `vis_m` of the z-buffer) gets u = (y_img - top(x)) / (bot(x) - top(x)); the weight tapers at the band's ends in x
    and fades out outside u in [0, 1] (the roll's profile is 0 there).  D then varies smoothly over the face in 3-D
    (no mixing of rows through the column parametrisation)."""
    nv, nu = A.shape
    X = fr.world(c, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    tris = V1.triangles(nu, nv)
    tid, _ = B.raster_ids(fr.cam, fr.world(c, A, Y), tris)
    # per-pixel depth of the front surface from the id buffer (depth of the triangle's first vertex)
    zt = P[tris[:, 0], 2]
    xi = np.clip(np.round(P[:, 0]).astype(int), 0, 1919); yi = np.clip(np.round(P[:, 1]).astype(int), 0, 1079)
    t_ = tid[yi, xi]
    zf = np.where(t_ >= 0, zt[np.maximum(t_, 0)], np.inf)
    vis = (P[:, 2] <= zf + tp.get("vis_m", 0.8)) & (P[:, 2] > 1)
    x = P[:, 0]; y = P[:, 1]
    tt = np.interp(x, xs, top); bb = np.interp(x, xs, bot)
    u = (y - tt) / np.maximum(bb - tt, 5.0)
    ex = tp.get("end_taper_px", 30.0)
    wx = smooth01((x - xs[0]) / ex) * smooth01((xs[-1] - x) / ex)
    W_ = (vis & (u > -0.3) & (u < 1.3)).astype(float) * wx
    return W_.reshape(nv, nu), np.clip(u, 0, 1).reshape(nv, nu)


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def roll_profile(u, u_peak=0.35):
    """0 at the top edge (u 0), 1 at u_peak, back to 0 at the claw edge (u 1): a roll whose crest sits just below the
    painted top edge and whose underside hangs to the claw edge."""
    u = np.clip(u, 0.0, 1.0)
    up = np.where(u < u_peak, np.sin(0.5 * np.pi * u / u_peak), np.cos(0.5 * np.pi * (u - u_peak) / (1 - u_peak)))
    return np.clip(up, 0, 1) ** 1.2


def outward_normal(A, Y):
    dA = np.gradient(A, axis=1); dY = np.gradient(Y, axis=1)
    L = np.maximum(np.hypot(dA, dY), 1e-9)
    return -dY / L, dA / L


def measure_edges(c, A, Y, fr, V1, tw, xs, thr=0.2):
    """projected top / lower edges of the tier (filled-triangle id buffer; pixels whose triangle carries a mean tier
    weight > thr), per band column."""
    nv, nu = A.shape
    tris = V1.triangles(nu, nv)
    tid, P = B.raster_ids(fr.cam, fr.world(c, A, Y), tris)
    twt = tw.reshape(-1)[tris].mean(1)
    wmap = np.where(tid >= 0, twt[np.maximum(tid, 0)], 0.0)
    et = np.full(len(xs), np.nan); eb = np.full(len(xs), np.nan)
    for k, x in enumerate(xs):
        # the roll's extent in this image column: the contiguous run around the column's peak where the roll
        # displacement exceeds `thr` of the column's peak (a per-column threshold: the ends of the band are lower rolls)
        colv = wmap[:, int(round(x))]
        pk = int(np.argmax(colv))
        if colv[pk] <= 0.05:
            continue
        m = colv > thr * colv[pk]
        i0 = pk
        while i0 > 0 and m[i0 - 1]:
            i0 -= 1
        i1 = pk
        while i1 < len(m) - 1 and m[i1 + 1]:
            i1 += 1
        et[k] = i0; eb[k] = i1
    return et, eb, wmap


def apply(c, A0, Y0, prm, log=print):
    V1, tgt, fr = C.painting_frame()
    xs, top, bot = band_targets()
    tp = prm["tier"]
    ttop, tbot = top.copy(), bot.copy()
    hist = []
    best = None
    inner = (xs >= 260) & (xs <= 690)
    for it in range(tp.get("iters", 3)):
        if tp.get("mode", "splat") == "image":
            Wn, U = tier_field_image(c, A0, Y0, fr, V1, xs, ttop, tbot, tp)
        else:
            Wn, U = tier_field(c, A0, Y0, fr, V1, xs, ttop, tbot, tuple(tp.get("splat_sig", (2.0, 3.0))))
        # end tapers along the band (x) are carried by the splat; extra taper at the band's ends in c
        prof = roll_profile(U, tp["u_peak"]) * Wn
        na, ny = outward_normal(A0, Y0)
        h = tp["h"]
        D = gaussian_filter(prof, tp.get("smooth_rc", (1.5, 2.0)))
        # one smooth roll: the displacement is smoothed along the crest in metres (rows are non-uniform)
        D = np.stack([gaussian_filter1d(D[:, j], 1.0) for j in range(D.shape[1])], 1)
        D = C.gauss1d_nonuniform(D, c, tp.get("smooth_c_m", 0.6))
        A = A0 + h * D * na; Y = Y0 + h * D * ny
        tw = D / max(D.max(), 1e-9)
        et, eb, _ = measure_edges(c, A, Y, fr, V1, tw, xs)
        dt = et - top; db = eb - bot
        okt = np.isfinite(dt); okb = np.isfinite(db)
        info = {"iter": it, "top_err_px": {"max": float(np.nanmax(np.abs(dt))) if okt.any() else None, "median": float(np.nanmedian(np.abs(dt))) if okt.any() else None,
                                           "covered_frac": float(okt.mean())},
                "lower_err_px": {"max": float(np.nanmax(np.abs(db))) if okb.any() else None, "median": float(np.nanmedian(np.abs(db))) if okb.any() else None,
                                 "covered_frac": float(okb.mean())},
                "move_max_m": float(np.hypot(A - A0, Y - Y0).max())}
        hist.append(info); log(json.dumps(info))
        sc_ = np.nanmax(np.abs(dt[inner])) + np.nanmax(np.abs(db[inner])) + np.nanmedian(np.abs(dt)) + np.nanmedian(np.abs(db))
        if best is None or sc_ < best[0]:
            best = (sc_, A.copy(), Y.copy(), tw.copy(), et.copy(), eb.copy(), it)
        # correct the targets for the next pass (the roll moves toward the camera, its image drifts)
        ttop = ttop - np.where(okt, np.clip(gaussian_filter1d(np.nan_to_num(dt), 4.0), -25, 25), 0.0) * tp.get("gain", 0.8)
        tbot = tbot - np.where(okb, np.clip(gaussian_filter1d(np.nan_to_num(db), 4.0), -25, 25), 0.0) * tp.get("gain", 0.8)
    _, A, Y, tw, et, eb, itb = best
    log("tier: best iteration %d" % itb)
    return A, Y, tw, {"history": hist, "best_iter": itb, "xs": xs.tolist(), "top_painted": top.tolist(), "lower_painted": bot.tolist(),
                      "top_ours": et.tolist(), "lower_ours": eb.tolist()}


def main(inp, out, prm_path):
    prm = json.load(open(prm_path, encoding="utf-8"))
    z = np.load(inp)
    A0, Y0, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    A, Y, tw, rep = apply(c, A0, Y0, prm)
    extra = {k: z[k] for k in z.files if k not in ("A", "Y", "c")}
    np.savez_compressed(out, A=A, Y=Y, c=c, A_pretier=A0, Y_pretier=Y0, tier_w=tw, **extra)
    json.dump(rep, open(os.path.splitext(out)[0] + "_tier.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "candA3b_params.json"))
