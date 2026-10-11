# -*- coding: utf-8 -*-
"""Independent C4 for the fine source (hold-out interpolation with landmark correspondence, own code).
For each k in 3319..3742: interpolate frames k and k+2 at alpha 0.5 and compare with frame k+1 inside crest(k+1) +-30 m:
fail if max > 0.25 m or p99 > 0.05 m. Observed order from (k, k+3) at 1/3, 2/3. Self-intersection of the BAKED interpolated pairs at j/30.
Usage: py -3.10 q_c4.py"""
import json, time
import numpy as np
from multiprocessing import Pool
import q_lib as Q

OFF = Q.still_offset_fine()
K = 3745
NP = 8192


def mains(frames):
    out = {}
    for f in frames:
        phi, xs, ys = Q.load_phi(f)
        out[f] = Q.main_curve(phi, xs, ys - OFF)
    return out


def crest_index(P, xc_prev, search=40.0):
    m = np.abs(P[:, 0] - xc_prev) <= search
    return int(np.where(m)[0][int(np.argmax(P[m, 1]))])


def lip_index(P, ic, vox=0.5, reach=30.0):
    xx = P[:, 0]; xc = xx[ic]
    for j in range(ic + 1, len(xx) - 1):
        if xx[j] - xc > reach:
            return None
        if xx[j] >= xx[j - 1] and xx[j] > xx[j + 1]:
            k = j + 1
            mn = xx[j]
            while k < len(xx) and xx[k] <= xx[j]:
                mn = min(mn, xx[k]); k += 1
            if xx[j] - mn >= vox:
                return j
    return None


def correspond(Pa, la, Pb, lb):
    """la, lb: landmark vertex indices (same count). Returns Ra, Rb (NP points each), piecewise arc-length uniform."""
    sa = Q.arclen(Pa); sb = Q.arclen(Pb)
    ba = [0.0] + [sa[i] for i in la] + [sa[-1]]
    bb = [0.0] + [sb[i] for i in lb] + [sb[-1]]
    La = np.diff(ba); Lb = np.diff(bb); M = 0.5 * (La + Lb)
    idx = np.rint(np.concatenate([[0], np.cumsum(M)]) / M.sum() * (NP - 1)).astype(int)
    qa = np.empty(NP); qb = np.empty(NP)
    for s in range(len(M)):
        n = idx[s + 1] - idx[s] + 1
        qa[idx[s]:idx[s + 1] + 1] = np.linspace(ba[s], ba[s + 1], n)
        qb[idx[s]:idx[s + 1] + 1] = np.linspace(bb[s], bb[s + 1], n)
    Ra = np.stack([np.interp(qa, sa, Pa[:, 0]), np.interp(qa, sa, Pa[:, 1])], 1)
    Rb = np.stack([np.interp(qb, sb, Pb[:, 0]), np.interp(qb, sb, Pb[:, 1])], 1)
    return Ra, Rb


def landmarks(P, ic):
    return ic, lip_index(P, ic)


def wdist(I, C, xc, w=30.0, h=0.01):
    Id = Q.densify(I, h); Cd = Q.densify(C, h)
    Id = Id[np.abs(Id[:, 0] - xc) <= w]; Cd = Cd[np.abs(Cd[:, 0] - xc) <= w]
    d = np.concatenate([Q.seg_dist(Id, C), Q.seg_dist(Cd, I)])
    return float(d.max()), float(np.percentile(d, 99))


G = {}


def init():
    frames = list(range(3319, 3746))
    G["M"] = mains(frames)
    xc = 261.53670245673754
    G["ic"] = {}
    for f in frames:
        i = crest_index(G["M"][f], xc); xc = G["M"][f][i, 0]; G["ic"][f] = i
    G["lip"] = {f: lip_index(G["M"][f], G["ic"][f]) for f in frames}


def interp(a, b, alpha):
    Pa, Pb = G["M"][a], G["M"][b]
    la = [G["ic"][a]]; lb = [G["ic"][b]]
    if G["lip"][a] is not None and G["lip"][b] is not None:
        la.append(G["lip"][a]); lb.append(G["lip"][b])
    Ra, Rb = correspond(Pa, la, Pb, lb)
    return (1 - alpha) * Ra + alpha * Rb


def job(k):
    if not G:
        init()
    r = dict(k=k)
    I = interp(k, k + 2, 0.5)
    C = G["M"][k + 1]; xc = C[G["ic"][k + 1], 0]
    r["max"], r["p99"] = wdist(I, C, xc)
    if k + 3 <= 3744:
        r["e3"] = []
        for alpha, f in ((1 / 3, k + 1), (2 / 3, k + 2)):
            I3 = interp(k, k + 3, alpha)
            C3 = G["M"][f]
            r["e3"].append(wdist(I3, C3, C3[G["ic"][f], 0])[0])
    return r


def seg_intersections(P):
    """count proper/touching intersections between non-adjacent segments of polyline P (vectorised O(n^2))."""
    a = P[:-1]; b = P[1:]
    n = len(a)
    if n < 3:
        return 0
    A = a[:, None, :]; B = b[:, None, :]; C = a[None, :, :]; D = b[None, :, :]
    def orient(p, q, r):
        return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
    o1 = orient(A, B, C); o2 = orient(A, B, D); o3 = orient(C, D, A); o4 = orient(C, D, B)
    hit = (o1 * o2 <= 0) & (o3 * o4 <= 0)
    ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    hit &= (jj > ii + 1)
    # exclude collinear disjoint false positives: require bbox overlap
    bx = (np.minimum(A[..., 0], B[..., 0]) <= np.maximum(C[..., 0], D[..., 0])) & (np.minimum(C[..., 0], D[..., 0]) <= np.maximum(A[..., 0], B[..., 0]))
    by = (np.minimum(A[..., 1], B[..., 1]) <= np.maximum(C[..., 1], D[..., 1])) & (np.minimum(C[..., 1], D[..., 1]) <= np.maximum(A[..., 1], B[..., 1]))
    return int((hit & bx & by).sum())


def selfx(p):
    pairs = np.memmap(Q.DATA + "/fine/pairs.bin", dtype="<f4", mode="r", shape=(570, 2, NP, 2))
    m = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
    A = np.array(pairs[p, 0], dtype=np.float64); B = np.array(pairs[p, 1], dtype=np.float64)
    xa = m["frames"][p]["crest_x"] - Q.X0B; xb = m["frames"][p + 1]["crest_x"] - Q.X0B
    lo, hi = min(xa, xb) - 30, max(xa, xb) + 30
    nx = 0; nmono = 0
    for j in range(1, 30):
        al = j / 30
        I = (1 - al) * A + al * B
        inw = (I[:, 0] >= lo) & (I[:, 0] <= hi)
        idx = np.where(inw)[0]
        seg = I[max(idx[0] - 1, 0):min(idx[-1] + 2, NP)]
        nx += seg_intersections(seg)
        out = I[~inw]
        # monotonic x outside the window (each side separately)
        left = I[:idx[0]]; right = I[idx[-1] + 1:]
        nmono += int((np.diff(left[:, 0]) <= 0).sum() + (np.diff(right[:, 0]) <= 0).sum())
    return p, nx, nmono


if __name__ == "__main__":
    T0 = time.time()
    ks = list(range(3319, 3743))
    with Pool(10, initializer=init) as pool:
        rows = pool.map(job, ks)
    rows.sort(key=lambda r: r["k"])
    man = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
    mrows = {r["k"]: r for r in man["checks"]["C4"]["rows"]}
    fails = [r["k"] for r in rows if r["max"] > 0.25 or r["p99"] > 0.05]
    blocked = set()
    for k in fails:
        blocked.update([k, k + 1])
    interp_pairs = [k for k in range(3319, 3744) if k not in blocked]
    E2 = float(np.median([r["max"] for r in rows]))
    E3 = float(np.median([v for r in rows if "e3" in r for v in r["e3"]]))
    p_obs = float(np.log((9 / 8) * E3 / E2) / np.log(1.5))
    man_interp = [pp["k"] for pp in man["pairs"] if pp["interp"]]
    near = sum(1 for r in rows if abs(r["p99"] - 0.05) <= 0.002)
    dp99 = np.array([r["p99"] - mrows[r["k"]]["p99"] for r in rows])
    dmax = np.array([r["max"] - mrows[r["k"]]["max"] for r in rows])
    disagree = [r["k"] for r in rows if (r["max"] > 0.25 or r["p99"] > 0.05) != (not mrows[r["k"]]["ok"])]
    # crest track vs fine manifest
    M = mains([3319])
    s = dict(n=len(rows), n_fail=len(fails), n_fail_by_max=sum(1 for r in rows if r["max"] > 0.25), fails=fails,
             n_interp=len(interp_pairs), interp_range=[min(interp_pairs), max(interp_pairs)] if interp_pairs else None,
             n_interp_manifest=len(man_interp), interp_set_equal=(set(interp_pairs) == set(man_interp)),
             interp_only_mine=sorted(set(interp_pairs) - set(man_interp)), interp_only_manifest=sorted(set(man_interp) - set(interp_pairs)),
             median_max=E2, median_p99=float(np.median([r["p99"] for r in rows])), max_of_max=float(max(r["max"] for r in rows)),
             max_of_p99=float(max(r["p99"] for r in rows)), E2=E2, E3=E3, p_observed=p_obs, n_p99_within_0p002_of_tol=near,
             fail_verdict_disagreements_vs_manifest=disagree, p99_diff_vs_manifest_median_abs=float(np.median(np.abs(dp99))),
             p99_diff_vs_manifest_max_abs=float(np.abs(dp99).max()), max_diff_vs_manifest_max_abs=float(np.abs(dmax).max()))
    # self-intersection of the baked interpolated pairs
    with Pool(10) as pool:
        sx = pool.map(selfx, [pp["p"] for pp in man["pairs"] if pp["interp"]])
    s["baked_interp_pairs_selfx_total"] = int(sum(v[1] for v in sx))
    s["baked_interp_pairs_nonmonotonic_outside_window"] = int(sum(v[2] for v in sx))
    s["pairs_with_selfx"] = [v[0] for v in sx if v[1] > 0]
    s["seconds"] = round(time.time() - T0, 1)
    print(json.dumps(s, indent=1))
    json.dump(dict(summary=s, rows=rows), open(Q.OUT + "/q_c4.json", "w"), indent=1)
