# E4b: mesh validity of the lip strip and the lip/tube-roof seam (30 Hz, all 133 curled rows, t*-2.7 s .. t*).
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e4b_mesh.py
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
# Proxies (stand-in for the design-27 body rig; NOT the rig):
#   columns < jt            : K* back face moved with the row crest and lowered by vH*T
#   columns jt..rim         : lip (parked strip or crest-top point before release, release ramp after; e4_common)
#   tube roof rim+1..ja-1   : rule 'parked'  = parked down the face, then smoothstep to K* from the row onset (first proxy)
#                             rule 'similar' = K*'s own tube-roof curve mapped by the similarity transform that sends
#                                              K*(rim)->X_rim(t) and K*(ja)->X_ja(t)  (seam rule proposed for design 27)
#   columns >= ja           : K* inner wall / face moved with the row crest and lowered by vH*T (anchor ja = inner wall at 0.3H)
import sys, json, math
import numpy as np
from e4_common import *
import ds26_paths as DP
out = DP.outdir(DP.OUT_FEAS)

J0 = min(q['jt'] for q in rows) - 3
J1 = max(q['ja'] for q in rows) + 2
Jall = np.arange(J0, J1 + 1)

def row_positions(q, cf, R, T, tube):
    a = A[q['r']]; y = Y[q['r']]
    nt = len(T); P = np.zeros((len(Jall), nt, 2)); kind = np.zeros(len(Jall), int)
    X, _, _ = state(q, cf, R, T)
    Dr = D_r(T, R['T_row'], cf)
    d1 = np.array([math.cos(math.radians(cf.th1)), -math.sin(math.radians(cf.th1))])
    d2 = np.array([math.cos(math.radians(cf.th2)), -math.sin(math.radians(cf.th2))])
    dl = max(cf.delta, 0.02); nose = q['n_up'] * dl * d1
    cg = crest_g(T, q, R['T_row'], cf)
    Sb = smooth((R['T_row'] - T) / R['T_row'])
    body = lambda j: np.stack([a[j] - Dr, y[j] - cf.vH * T], -1)
    for jj, j in enumerate(Jall):
        if j < q['jt'] or j >= q['ja']:
            P[jj] = body(j); kind[jj] = 0 if j < q['jt'] else 3
        elif j <= q['rim']:
            P[jj] = X[int(np.where(q['cols'] == j)[0][0])]; kind[jj] = 1
        else:
            kind[jj] = 2
            if tube == 'parked':
                park = cg + nose[None, :] + (j - q['jtip']) * dl * d2[None, :]
                P[jj] = (1 - Sb)[:, None] * park + Sb[:, None] * np.array([a[j], y[j]])[None, :]
    if tube == 'similar':
        irim = int(np.where(Jall == q['rim'])[0][0]); ia = int(np.where(Jall == q['ja'])[0][0])
        zr = complex(a[q['rim']], y[q['rim']]); za = complex(a[q['ja']], y[q['ja']])
        Xr = P[irim, :, 0] + 1j * P[irim, :, 1]; Xa = P[ia, :, 0] + 1j * P[ia, :, 1]
        M = (Xa - Xr) / (za - zr)                           # rotation*scale per time
        for jj in range(irim + 1, ia):
            j = Jall[jj]; z = complex(a[j], y[j])
            w = Xr + M * (z - zr)
            P[jj, :, 0] = w.real; P[jj, :, 1] = w.imag
    return P, kind

def seg_inter_pairs(Pl):
    n = len(Pl) - 1; hits = []
    p1 = Pl[:-1]; p2 = Pl[1:]
    for i in range(n):
        q1 = p1[i + 2:]; q2 = p2[i + 2:]
        if len(q1) == 0:
            continue
        d = p2[i] - p1[i]
        c1 = d[0] * (q1[:, 1] - p1[i][1]) - d[1] * (q1[:, 0] - p1[i][0])
        c2 = d[0] * (q2[:, 1] - p1[i][1]) - d[1] * (q2[:, 0] - p1[i][0])
        e = q2 - q1
        c3 = e[:, 0] * (p1[i][1] - q1[:, 1]) - e[:, 1] * (p1[i][0] - q1[:, 0])
        c4 = e[:, 0] * (p2[i][1] - q1[:, 1]) - e[:, 1] * (p2[i][0] - q1[:, 0])
        for k in np.where((c1 * c2 < 0) & (c3 * c4 < 0))[0]:
            hits.append((i, i + 2 + int(k)))
    return hits

KIND = {0: 'back', 1: 'lip', 2: 'tube', 3: 'wall'}

def mesh_check(cf, tube, hz=30):
    T = np.arange(0, 2.7 + 1e-9, 1 / hz)[::-1]
    pos = []; kinds = []
    for q in rows:
        R = ramp_solve(q, cf)
        P, kind = row_positions(q, cf, R, T, tube); pos.append(P); kinds.append(kind)
    pos = np.array(pos); kinds = np.array(kinds)
    cv = np.array([q['c'] for q in rows])
    Kp = np.stack([np.stack([A[q['r']][Jall], Y[q['r']][Jall]], -1) for q in rows])
    seg = np.linalg.norm(np.diff(pos, axis=1), axis=-1)                   # (nr, nj-1, nt)
    segK = np.linalg.norm(np.diff(Kp, axis=1), axis=-1)[:, :, None]
    st = seg / np.maximum(segK, 1e-6)
    lipe = ((kinds[:, :-1] == 1) | (kinds[:, 1:] == 1) | (kinds[:, :-1] == 2) | (kinds[:, 1:] == 2))[:, :, None] & np.ones(len(T), bool)
    seam = ((kinds[:, :-1] == 1) & (kinds[:, 1:] == 2))[:, :, None] & np.ones(len(T), bool)
    res = dict(tube_rule=tube, hz=hz, window_tau=[-float(T[0]), 0.0])
    def loc(idx):
        ir, jj, it = idx
        return dict(c=round(float(cv[ir]), 2), col=int(Jall[jj]), kinds=KIND[int(kinds[ir, jj])] + '-' + KIND[int(kinds[ir, jj + 1])], tau=round(-float(T[it]), 3))
    v = np.where(lipe, seg, np.inf); i = np.unravel_index(np.argmin(v), v.shape)
    res['row_edge_min_m'] = float(v[i]); res['row_edge_min_at'] = loc(i)
    res['row_edge_p1_m'] = float(np.percentile(seg[lipe], 1))
    v = np.where(lipe, st, -np.inf); i = np.unravel_index(np.argmax(v), v.shape)
    res['row_edge_stretch_max'] = float(v[i]); res['row_edge_stretch_max_at'] = loc(i)
    res['row_edge_stretch_p99'] = float(np.percentile(st[lipe], 99))
    v = np.where(lipe, st, np.inf); res['row_edge_compress_min'] = float(v.min())
    res['seam_stretch_max'] = float(st[seam].max()); res['seam_stretch_min'] = float(st[seam].min())
    res['seam_len_max_m'] = float(seg[seam].max()); res['seam_len_min_m'] = float(seg[seam].min())
    # self intersections: row polyline jt-3 .. ja+2
    hits = []
    for ir, q in enumerate(rows):
        lo = int(np.where(Jall == q['jt'] - 3)[0][0]); hi = int(np.where(Jall == min(q['ja'] + 2, J1))[0][0])
        for it in range(len(T)):
            for (i1, i2) in seg_inter_pairs(pos[ir, lo:hi + 1, it, :]):
                hits.append((round(float(cv[ir]), 2), round(-float(T[it]), 3), int(Jall[lo + i1]), KIND[int(kinds[ir, lo + i1])] + '-' + KIND[int(kinds[ir, lo + i1 + 1])],
                             int(Jall[lo + i2]), KIND[int(kinds[ir, lo + i2])] + '-' + KIND[int(kinds[ir, lo + i2 + 1])]))
    res['row_self_intersections_total'] = len(hits)
    res['row_self_intersection_samples'] = hits[:8]
    if hits:
        res['row_self_intersections_c_range'] = [min(h[0] for h in hits), max(h[0] for h in hits)]
        res['row_self_intersections_tau_range'] = [min(h[1] for h in hits), max(h[1] for h in hits)]
    # 3-D triangles between consecutive K* rows that are both curled; triangles touching lip or tube columns
    amin = (np.inf, None); flips = []; ndmin = 1.0; crossmax = (0.0, None); aKmin = np.inf
    for ir in range(len(rows) - 1):
        if rows[ir + 1]['r'] != rows[ir]['r'] + 1:
            continue
        v3 = lambda P, c: np.concatenate([P, np.full(P.shape[:-1] + (1,), c)], -1)
        Q0 = v3(pos[ir], cv[ir]); Q1 = v3(pos[ir + 1], cv[ir + 1])
        K0 = v3(Kp[ir], cv[ir]); K1 = v3(Kp[ir + 1], cv[ir + 1])
        tch = (kinds[ir] == 1) | (kinds[ir + 1] == 1) | (kinds[ir] == 2) | (kinds[ir + 1] == 2)
        tj = tch[:-1] | tch[1:]
        for tri, (a_, b_, c_, ka, kb, kc) in enumerate(((Q0[:-1], Q0[1:], Q1[:-1], K0[:-1], K0[1:], K1[:-1]), (Q1[:-1], Q0[1:], Q1[1:], K1[:-1], K0[1:], K1[1:]))):
            nrm = np.cross(b_ - a_, c_ - a_); ar = 0.5 * np.linalg.norm(nrm, axis=-1)
            nK = np.cross(kb - ka, kc - ka); aKmin = min(aKmin, float((0.5 * np.linalg.norm(nK, axis=-1))[tj].min()))
            arm = np.where(tj[:, None], ar, np.inf); k = np.unravel_index(np.argmin(arm), arm.shape)
            if arm[k] < amin[0]:
                amin = (float(arm[k]), dict(c=round(float(cv[ir]), 2), col=int(Jall[k[0]]), tri=tri, tau=round(-float(T[k[1]]), 3),
                                            kinds=KIND[int(kinds[ir, k[0]])] + '/' + KIND[int(kinds[ir, k[0] + 1])]))
            un_ = nrm / np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-15)
            dots = np.sum(un_[:, 1:] * un_[:, :-1], -1)
            dots = np.where(tj[:, None], dots, 1.0)
            ndmin = min(ndmin, float(dots.min()))
            for jj, it in zip(*np.where(dots < 0)):
                flips.append((round(float(cv[ir]), 2), int(Jall[jj]), KIND[int(kinds[ir, jj])] + '/' + KIND[int(kinds[ir, jj + 1])], round(-float(T[it + 1]), 3)))
        e = np.linalg.norm(Q1 - Q0, axis=-1); eK = np.linalg.norm(K1 - K0, axis=-1)[:, None]
        sr = np.where(tch[:, None], e / np.maximum(eK, 1e-6), 0.0); k = np.unravel_index(np.argmax(sr), sr.shape)
        if sr[k] > crossmax[0]:
            crossmax = (float(sr[k]), dict(c=round(float(cv[ir]), 2), col=int(Jall[k[0]]), tau=round(-float(T[k[1]]), 3), kind=KIND[int(kinds[ir, k[0]])]))
    res.update(tri_area_min_m2=amin[0], tri_area_min_at=amin[1], tri_area_min_kstar_m2=aKmin,
               face_flips=len(flips), face_flip_samples=flips[:8], face_normal_dot_min=ndmin,
               cross_row_edge_stretch_max=crossmax[0], cross_row_edge_stretch_max_at=crossmax[1])
    if flips:
        res['face_flip_kinds'] = sorted(set(f[2] for f in flips))
        res['face_flip_tau_range'] = [min(f[3] for f in flips), max(f[3] for f in flips)]
        res['face_flip_c_range'] = [min(f[0] for f in flips), max(f[0] for f in flips)]
    return res

cases = [('A0 point (E1/E3), tube parked', Cfg('p', rule='point', floor=1.2, tr_rule='half'), 'parked'),
         ('B strip, tube parked', Cfg('s', rule='strip', floor=1.2, tr_rule='half'), 'parked'),
         ('C strip, tube similarity (default)', Cfg('s', rule='strip', floor=1.2, tr_rule='half'), 'similar')]
allres = {}
for name, cf, tube in cases:
    allres[name] = mesh_check(cf, tube)
    print(name, json.dumps(allres[name]))
json.dump(allres, open(out + '/e4b_mesh_result.json', 'w'), indent=1)
