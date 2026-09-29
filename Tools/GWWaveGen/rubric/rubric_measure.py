# -*- coding: utf-8 -*-
"""Q20 rubric measurement tool (numpy + scipy, py -3.10).

Measures the section / crest-line / wall / lip / trough numbers of the rubric on
  * a K* grid (kstar_*_rows.npz: A, Y, c in the K* 26修正01 section frame), and
  * the aligned reference model (TEMP cache written by bl_rubric_views.py; never copied into the repo).
Both are cut by the same planes c = const and go through the same code, so the numbers compare.

Frame (K* 26修正01 meta): a = along travel t (+ = lip side), y = height (still water 0; model sea 1.198),
c = along the crest e (- = camera-side shoulder). H0 = 20.75 m (K* main section, row 159, c = 0).

usage:  py -3.10 rubric_measure.py kstar <rows.npz> <out.json>
        py -3.10 rubric_measure.py ref   <ref_cache.npz> <out.json>
"""
import sys, json
import numpy as np
from scipy.ndimage import grey_opening, gaussian_filter1d

E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
DA = 0.05          # envelope bin (m)
OPEN_W = 1.5       # claw / nub removal: grey opening width (m) on the top envelope


def sec(P):
    Q = np.atleast_2d(P) - O
    return np.c_[Q @ T, Q[:, 1], Q @ E]


# ------------------------------------------------------------------ section geometry as 2-D segments
def slice_mesh(S, tris, c0):
    """segments (k,2,2) in (a, y) where the plane c = c0 cuts the triangles."""
    d = S[:, 2] - c0
    dt = d[tris]
    s = np.sign(dt); s[s == 0] = 1
    cut = ~((s[:, 0] == s[:, 1]) & (s[:, 1] == s[:, 2]))
    tr = tris[cut]; dt = dt[cut]
    P = S[tr][:, :, :2]
    segs = []
    for (i, j) in ((0, 1), (1, 2), (2, 0)):
        m = np.sign(dt[:, i]) != np.sign(dt[:, j])
        t = dt[:, i] / np.where(m, dt[:, i] - dt[:, j], 1.0)
        pts = P[:, i] + t[:, None] * (P[:, j] - P[:, i])
        segs.append((m, pts))
    out = []
    for k in range(len(tr)):
        pk = [segs[e][1][k] for e in range(3) if segs[e][0][k]]
        if len(pk) >= 2:
            out.append([pk[0], pk[1]])
    return np.array(out) if out else np.zeros((0, 2, 2))


def poly_to_segs(a, y):
    P = np.stack([a, y], -1)
    return np.stack([P[:-1], P[1:]], 1)


def sample_segs(segs, step=0.02):
    L = np.linalg.norm(segs[:, 1] - segs[:, 0], axis=1)
    n = np.maximum((L / step).astype(int), 1)
    idx = np.repeat(np.arange(len(segs)), n + 1)
    t = np.concatenate([np.linspace(0, 1, k + 1) for k in n])
    return segs[idx, 0] + t[:, None] * (segs[idx, 1] - segs[idx, 0])


def envelope(pts, a0, a1, fn=np.maximum):
    bins = np.arange(a0, a1 + DA, DA)
    ib = np.clip(((pts[:, 0] - a0) / DA).round().astype(int), 0, len(bins) - 1)
    env = np.full(len(bins), -np.inf if fn is np.maximum else np.inf)
    fn.at(env, ib, pts[:, 1])
    return bins, env


def crossings(segs, yv):
    y0, y1 = segs[:, 0, 1], segs[:, 1, 1]
    m = (y0 - yv) * (y1 - yv) < 0
    t = (yv - y0[m]) / (y1[m] - y0[m])
    return np.sort(segs[m, 0, 0] + t * (segs[m, 1, 0] - segs[m, 0, 0]))


def heading_turn_per_m(a, y, win=1.0, step=0.05):
    """re-sample the curve by arc length; return s, heading(deg), max |heading change| over any `win` m window at each s."""
    s = np.r_[0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]
    if s[-1] < 2 * win:
        return None
    ss = np.arange(0, s[-1], step)
    aa = np.interp(ss, s, a); yy = np.interp(ss, s, y)
    h = np.degrees(np.unwrap(np.arctan2(np.gradient(yy), np.gradient(aa))))
    k = int(round(win / step))
    turn = np.abs(h[k:] - h[:-k])
    return ss, aa, yy, h, turn, k


def section_metrics(segs, sea, H0, open_w=None):
    out = {}
    ow = OPEN_W if open_w is None else open_w
    if len(segs) < 10:
        return None
    pts = sample_segs(segs)
    pts = pts[pts[:, 1] > sea - 3.0]
    a0, a1 = pts[:, 0].min() - 1, pts[:, 0].max() + 1
    bins, env = envelope(pts, a0, a1)
    ok = np.isfinite(env)
    env_f = np.interp(bins, bins[ok], env[ok])
    k = max(int(round(ow / DA)), 1)
    env_o = grey_opening(env_f, size=k) if k > 1 else env_f.copy()                 # removes claws / nubs narrower than OPEN_W
    it = int(np.argmax(env_o)); a_top, y_top = bins[it], env_o[it]
    H = y_top - sea
    out.update(H=float(H), H_over_H0=float(H / H0), a_top=float(a_top), y_top=float(y_top), H_raw=float(env_f.max() - sea))
    if H < 2.0:
        return out
    # theta_c (Design 26): chord angle from the top to the envelope 0.1H below, back and front
    lvl = y_top - 0.1 * H
    ib = it
    while ib > 0 and env_o[ib] > lvl:
        ib -= 1
    jf = it
    while jf < len(bins) - 1 and env_o[jf] > lvl:
        jf += 1
    vb = np.array([bins[ib] - a_top, env_o[ib] - y_top]); vf = np.array([bins[jf] - a_top, env_o[jf] - y_top])
    out["theta_c_deg"] = float(np.degrees(np.arccos(np.clip(vb @ vf / np.linalg.norm(vb) / np.linalg.norm(vf), -1, 1))))
    # top arc: Kasa circle fit on the opened envelope inside the top 0.1H band
    m = (np.arange(len(bins)) >= ib) & (np.arange(len(bins)) <= jf)
    x, yv = bins[m], env_o[m]
    A = np.c_[2 * x, 2 * yv, np.ones_like(x)]
    sol, *_ = np.linalg.lstsq(A, x ** 2 + yv ** 2, rcond=None)
    out["R_top_fit_m"] = float(np.sqrt(sol[2] + sol[0] ** 2 + sol[1] ** 2))
    # max heading change per 1 m of arc in the top zone (y >= y_top - 0.15H), envelope lightly smoothed (sigma 0.15 m)
    zone = env_o >= y_top - 0.15 * H
    iz = np.nonzero(zone)[0]
    seg_lo, seg_hi = iz.min(), iz.max()
    ya = gaussian_filter1d(env_o, 0.15 / DA)
    r = heading_turn_per_m(bins[seg_lo:seg_hi + 1], ya[seg_lo:seg_hi + 1])
    if r is not None:
        ss, aa, yy, h, turn, kk = r
        out["top_turn_max_deg_per_m"] = float(turn.max())
        out["top_R_equiv_min_m"] = float(np.degrees(1.0) / max(turn.max(), 1e-6))
    # back contour (a < a_top): steepest slope 0.2H..0.9H and the largest turn per 1 m (crease / corner test)
    bm = (bins < a_top - 0.3) & (env_o > sea + 0.15 * H) & (env_o < y_top - 0.02 * H)
    if bm.sum() > 20:
        xb, yb = bins[bm], gaussian_filter1d(env_o, 0.15 / DA)[bm]
        sl = np.degrees(np.arctan(np.gradient(yb, xb)))
        mid = (yb > sea + 0.2 * H) & (yb < sea + 0.9 * H)
        out["back_slope_max_deg"] = float(sl[mid].max()) if mid.any() else None
        rb = heading_turn_per_m(xb, yb)
        if rb is not None:
            out["back_turn_max_deg_per_m"] = float(rb[4].max())
        # back foot: where the back envelope first rises above 0.05H (distance behind the top, in H)
        foot = xb[yb > sea + 0.05 * H]
        out["back_foot_behind_top_over_H"] = float((a_top - foot.min()) / H) if len(foot) else None
    # wall thickness at 0.25/0.5/0.75 H: first solid band from the back
    for f in (0.25, 0.5, 0.75):
        xs = crossings(segs, sea + f * H)
        out["wall_%02d_m" % int(f * 100)] = float(xs[1] - xs[0]) if len(xs) >= 2 else None
    w5 = out.get("wall_50_m")
    out["wall_50_over_H"] = float(w5 / H) if w5 is not None else None
    # lip tip (most forward point above 0.3H, in front of the top), overhang from the inner wall at 0.3H
    fr = pts[(pts[:, 1] > sea + 0.3 * H) & (pts[:, 0] > a_top)]
    if len(fr):
        i = int(np.argmax(fr[:, 0])); a_tip, y_tip = fr[i]
        out.update(a_tip=float(a_tip), y_tip=float(y_tip), tip_height_over_H=float((y_tip - sea) / H))
        xs = crossings(segs, sea + 0.3 * H)
        if len(xs) >= 2:
            a_in = xs[1]
            out["inner_wall_a_at_0p3H"] = float(a_in)
            out["overhang_m"] = float(a_tip - a_in)
            out["overhang_over_H"] = float((a_tip - a_in) / H)
        # lip vertical thickness at 0.75 / 2 m behind the tip: the vertical line a = a_tip - d cuts the section;
        # thickness = top crossing minus the next crossing below it (the lip's upper and lower surfaces)
        for dist, key in ((0.75, "lip_thick_0p75_m"), (2.0, "lip_thick_2m_m")):
            at = a_tip - dist
            a0s, a1s = segs[:, 0, 0], segs[:, 1, 0]
            mm = (a0s - at) * (a1s - at) < 0
            tt = (at - a0s[mm]) / (a1s[mm] - a0s[mm])
            ys = np.sort(segs[mm, 0, 1] + tt * (segs[mm, 1, 1] - segs[mm, 0, 1]))[::-1]
            ys = ys[ys > sea + 0.3 * H]
            out[key] = float(ys[0] - ys[1]) if len(ys) >= 2 else None
    # front trough: lowest surface point below 0.3H from the inner wall to 25 m in front of it (relative to the sea)
    if "inner_wall_a_at_0p3H" in out:
        a_in = out["inner_wall_a_at_0p3H"]
        low = pts[(pts[:, 1] < sea + 0.3 * H) & (pts[:, 0] > a_in) & (pts[:, 0] < a_in + 25)]
        if len(low):
            bins2, env2 = envelope(low, a_in, a_in + 25)
            okk = np.isfinite(env2)
            j = int(np.argmin(np.where(okk, env2, np.inf)))
            out["front_trough_depth_m"] = float(sea - env2[j])
            out["front_trough_depth_over_H"] = float((sea - env2[j]) / H)
            out["front_trough_a_from_inner"] = float(bins2[j] - a_in)
    return out


def summarize(secs, H0):
    cs = np.array(sorted(secs)); H = np.array([secs[c]["H"] for c in cs])
    Hn = H / H0
    res = {"c": cs.tolist()}
    for f in (0.25, 0.5, 0.75, 0.9):
        m = Hn >= f
        res["c_extent_H_ge_%.2f" % f] = [float(cs[m].min()), float(cs[m].max())] if m.any() else None
    i = int(np.argmax(H)); res["c_of_max_H"] = float(cs[i]); res["max_H_over_H0"] = float(Hn[i])
    at = np.array([secs[c].get("a_top", np.nan) for c in cs])
    yt = np.array([secs[c].get("y_top", np.nan) for c in cs])
    m = Hn >= 0.5
    if m.sum() >= 5:
        p = np.polyfit(cs[m], at[m], 2)
        res["crest_plan_quad_a_of_c"] = p.tolist()
        res["crest_plan_radius_m_at_cmaxH"] = float((1 + (2 * p[0] * cs[i] + p[1]) ** 2) ** 1.5 / max(abs(2 * p[0]), 1e-9))
        res["crest_plan_sagitta_m"] = float(np.ptp(at[m] - np.polyval(np.polyfit(cs[m], at[m], 1), cs[m])))
        res["crest_plan_a_range_m"] = [float(np.nanmin(at[m])), float(np.nanmax(at[m]))]
    # elevation: near-side and far-side taper (height drop per metre of crest between 0.9H and 0.25H)
    for side, sel in (("near", cs <= cs[i]), ("far", cs >= cs[i])):
        c9 = cs[sel & (Hn >= 0.9)]; c25 = cs[sel & (Hn >= 0.25)]
        if len(c9) and len(c25):
            c_9 = c9.min() if side == "near" else c9.max(); c_25 = c25.min() if side == "near" else c25.max()
            res["taper_%s_0.9H_to_0.25H_m" % side] = float(abs(c_9 - c_25))
    return res


def crease_stats_grid(A, Y, c, rows=None):
    """K* grid only: dihedral angles between the two triangles of each quad and across row / column edges (degrees)."""
    X = np.stack([A, Y, np.broadcast_to(c[:, None], A.shape)], -1)
    nv, nu, _ = X.shape
    du = X[:, 1:, :] - X[:, :-1, :]; dv = X[1:, :, :] - X[:-1, :, :]
    n = np.cross(du[:-1, :, :], dv[:, :-1, :])
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
    ang_row = np.degrees(np.arccos(np.clip((n[1:] * n[:-1]).sum(-1), -1, 1)))   # across rows (c direction)
    ang_col = np.degrees(np.arccos(np.clip((n[:, 1:] * n[:, :-1]).sum(-1), -1, 1)))  # along the section
    area_ok = (Y[:-1, :-1] > 0.3)
    r = {}
    for nm, ang, msk in (("across_rows", ang_row, area_ok[1:]), ("along_section", ang_col, area_ok[:, 1:])):
        v = ang[msk]
        r[nm] = {"p50": float(np.percentile(v, 50)), "p95": float(np.percentile(v, 95)), "p99": float(np.percentile(v, 99)),
                 "max": float(v.max()), "n_gt_20deg": int((v > 20).sum()), "n_gt_30deg": int((v > 30).sum()), "n_quads": int(v.size)}
    return r


def main():
    kind, src, outp = sys.argv[1:4]
    secs = {}
    if kind == "kstar":
        z = np.load(src); A, Y, c = z["A"], z["Y"], z["c"]
        H0 = float(Y[np.argmin(np.abs(c))].max()); sea = 0.0
        for r in range(len(c)):
            if -18.5 <= c[r] <= 15.0:
                m = section_metrics(poly_to_segs(A[r], Y[r]), sea, H0)
                if m:
                    m["row"] = r; secs[round(float(c[r]), 3)] = m
        extra = {"crease_grid": crease_stats_grid(A, Y, c)}
    else:
        z = np.load(src); V = z["V"].astype(np.float64); tris = z["tris"]
        S = sec(V); sea = 1.198; H0 = 21.70
        for c0 in np.arange(-18.0, 15.01, 0.5):
            segs = slice_mesh(S, tris, c0)
            m = section_metrics(segs, sea, H0)
            if m:
                secs[round(float(c0), 3)] = m
        extra = {}
    res = {"kind": kind, "src": src, "H0": H0, "sea": sea, "open_w_m": OPEN_W, "sections": {str(k): v for k, v in secs.items()},
           "summary": summarize(secs, H0)}
    res.update(extra)
    json.dump(res, open(outp, "w", encoding="utf-8"), indent=1)
    print(json.dumps(res["summary"], indent=1)); print(json.dumps(extra, indent=1))


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------ added: back arc / straight run, shell thickness, tube roundness
def ray_hits(segs, p, d):
    """distances t > 0 where the ray p + t d hits the 2-D segments."""
    a = segs[:, 0]; b = segs[:, 1]; e = b - a
    den = d[0] * (-e[:, 1]) - d[1] * (-e[:, 0])
    ok = np.abs(den) > 1e-12
    q = a - p
    t = (q[:, 0] * (-e[:, 1]) - q[:, 1] * (-e[:, 0])) / np.where(ok, den, 1)
    u = (d[0] * q[:, 1] - d[1] * q[:, 0]) / np.where(ok, den, 1)
    m = ok & (t > 1e-3) & (u >= 0) & (u <= 1)
    return np.sort(t[m])


def back_shape(segs, sea, H, a_top):
    """back contour (top envelope behind the crest, 0.15H..0.95H): circle-fit radius, longest near-straight run
    (heading change < 6 deg), shell thickness along the inward normal (median / min / max for 0.2..0.8H)."""
    pts = sample_segs(segs); pts = pts[pts[:, 1] > sea - 3]
    bins, env = envelope(pts, pts[:, 0].min() - 1, a_top + 0.01)
    ok = np.isfinite(env); env = np.interp(bins, bins[ok], env[ok])
    env = gaussian_filter1d(env, 0.15 / DA)
    m = (env > sea + 0.15 * H) & (env < sea + 0.95 * H) & (bins < a_top)
    if m.sum() < 30:
        return {}
    x, y = bins[m], env[m]
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    sol, *_ = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)
    R = float(np.sqrt(sol[2] + sol[0] ** 2 + sol[1] ** 2))
    s = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
    ss = np.arange(0, s[-1], 0.05); xx = np.interp(ss, s, x); yy = np.interp(ss, s, y)
    h = np.degrees(np.unwrap(np.arctan2(np.gradient(yy), np.gradient(xx))))
    best = 0.0; j0 = 0
    for j1 in range(len(h)):
        while h[j0:j1 + 1].max() - h[j0:j1 + 1].min() > 6.0:
            j0 += 1
        best = max(best, ss[j1] - ss[j0])
    # inward normal thickness (normal of the back contour pointing into the water body: rotate tangent by -90 deg)
    th = []
    for i in range(0, len(xx), 10):
        if not (sea + 0.2 * H <= yy[i] <= sea + 0.8 * H):
            continue
        tg = np.array([np.cos(np.radians(h[i])), np.sin(np.radians(h[i]))])
        nrm = np.array([tg[1], -tg[0]])
        hits = ray_hits(segs, np.array([xx[i], yy[i]]) + 0.02 * nrm, nrm)
        if len(hits):
            hits = hits[hits > 0.3]
            if len(hits):
                th.append(hits[0])
    th = np.array(th)
    return {"back_R_fit_m": R, "back_R_over_H": R / H, "back_longest_straight_m": float(best), "back_longest_straight_over_H": float(best / H),
            "back_heading_range_deg": [float(h.min()), float(h.max())],
            "shell_thick_normal_m": [float(np.min(th)), float(np.median(th)), float(np.max(th))] if len(th) else None,
            "shell_thick_normal_over_H": [float(np.min(th) / H), float(np.median(th) / H), float(np.max(th) / H)] if len(th) else None}


def tube_shape(segs, sea, H, a_in, a_tip, y_tip):
    """cast rays from a centre inside the tube; the first hits form the tube wall. Closure = angular span of the
    rays that hit a wall within 1.2H; roundness = circle fit residual; corner = max heading change per 1 m."""
    cen = np.array([(a_in + a_tip) / 2.0, sea + 0.5 * (y_tip - sea)])
    for it in range(3):
        ang = np.radians(np.arange(0, 360, 1.0))
        P = []; hit = []
        for t in ang:
            d = np.array([np.cos(t), np.sin(t)]); hs = ray_hits(segs, cen, d)
            if len(hs) and hs[0] < 1.2 * H:
                P.append(cen + hs[0] * d); hit.append(True)
            else:
                P.append(cen); hit.append(False)
        P = np.array(P); hit = np.array(hit)
        if hit.sum() < 20:
            return {}
        Q = P[hit]
        A = np.c_[2 * Q[:, 0], 2 * Q[:, 1], np.ones(len(Q))]
        sol, *_ = np.linalg.lstsq(A, (Q ** 2).sum(1), rcond=None)
        cen_new = sol[:2]; R = np.sqrt(sol[2] + (sol[:2] ** 2).sum())
        if np.linalg.norm(cen_new - cen) < 0.05:
            break
        # keep the centre inside the cavity: only accept if the new centre sees walls in most directions
        cen = 0.5 * cen + 0.5 * cen_new
    res = np.abs(np.linalg.norm(Q - sol[:2], axis=1) - R)
    # closure: longest run of consecutive hits (circular)
    hh = np.r_[hit, hit]; run = best = 0
    for v in hh:
        run = run + 1 if v else 0; best = max(best, run)
    closure = min(best, 360)
    # corner test along the hit boundary (ordered by angle, only the longest run)
    return {"tube_center_a_y": [float(cen[0]), float(cen[1])], "tube_R_fit_m": float(R), "tube_R_over_H": float(R / H),
            "tube_fit_rms_over_R": float(np.sqrt((res ** 2).mean()) / R), "tube_closure_deg": float(closure)}


def extra_section(segs, sea, H0):
    m = section_metrics(segs, sea, H0)
    if not m or m.get("H", 0) < 0.5 * H0:
        return m
    m.update(back_shape(segs, sea, m["H"], m["a_top"]))
    if "inner_wall_a_at_0p3H" in m and "a_tip" in m:
        m.update(tube_shape(segs, sea, m["H"], m["inner_wall_a_at_0p3H"], m["a_tip"], m["y_tip"]))
    return m


def tube_shape2(segs, sea, H, a_in, a_tip, y_tip):
    """fixed centre inside the tube (45 % from the inner wall at 0.3H to the lip tip, 45 % of the tip height);
    rays every 1 deg; first hits within 1.0H form the tube wall (the trough floor included). Reports the circle fit
    (R/H, rms/R), closure (longest run of hitting rays, deg) and the largest heading change per 1 m along that wall."""
    cen = np.array([a_in + 0.45 * (a_tip - a_in), sea + 0.45 * (y_tip - sea)])
    ang = np.arange(0, 360, 1.0)
    P = np.full((360, 2), np.nan)
    for i, t in enumerate(np.radians(ang)):
        d = np.array([np.cos(t), np.sin(t)]); hs = ray_hits(segs, cen, d)
        if len(hs) and hs[0] < 1.0 * H:
            P[i] = cen + hs[0] * d
    hit = np.isfinite(P[:, 0])
    if hit.sum() < 30:
        return {}
    # longest circular run
    best = (0, 0); run = 0; start = 0
    hh = np.r_[hit, hit]
    for i, v in enumerate(hh):
        if v:
            if run == 0:
                start = i
            run += 1
            if run > best[0]:
                best = (min(run, 360), start)
        else:
            run = 0
    n, s0 = best
    idx = (np.arange(s0, s0 + n) % 360)
    Q = P[idx]
    A = np.c_[2 * Q[:, 0], 2 * Q[:, 1], np.ones(len(Q))]
    sol, *_ = np.linalg.lstsq(A, (Q ** 2).sum(1), rcond=None)
    R = float(np.sqrt(sol[2] + (sol[:2] ** 2).sum()))
    res = np.abs(np.linalg.norm(Q - sol[:2], axis=1) - R)
    r = heading_turn_per_m(gaussian_filter1d(Q[:, 0], 1.0), gaussian_filter1d(Q[:, 1], 1.0))
    return {"tube_center_used": cen.tolist(), "tube_R_fit_m": R, "tube_R_over_H": R / H,
            "tube_fit_rms_over_R": float(np.sqrt((res ** 2).mean()) / R), "tube_closure_deg": float(n),
            "tube_wall_turn_max_deg_per_m": float(r[4].max()) if r else None}


def extra_section2(segs, sea, H0):
    m = section_metrics(segs, sea, H0)
    if not m or m.get("H", 0) < 0.5 * H0:
        return m
    b = back_shape(segs, sea, m["H"], m["a_top"])
    m.update(b)
    if "inner_wall_a_at_0p3H" in m and "a_tip" in m:
        m.update(tube_shape2(segs, sea, m["H"], m["inner_wall_a_at_0p3H"], m["a_tip"], m["y_tip"]))
    return m
