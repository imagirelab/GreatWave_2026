# -*- coding: utf-8 -*-
"""C2 (a) with the sec range included (sec crossings counted above 25 m below still level), split before/after first contact."""
import json, numpy as np
import q_lib as Q
OFF = Q.still_offset_fine()
cm = json.load(open(Q.DATA + "/coarse/manifest.json", encoding="utf8"))
crest = {r["frame"]: r["crest_x"] for r in cm["frames"]}
D = {"before": [], "after": []}; W = {"before": (0, None), "after": (0, None)}; Din = {"before": [], "after": []}
for f in range(3319, 3890):
    phi, xs, ys = Q.load_phi(f)
    hfin, nchg = Q.top_height(phi, ys - OFF)
    eta, xh = Q.load_hf(f); eta = eta - Q.OFF_R3
    slope = np.degrees(np.arctan(np.abs(np.gradient(eta, 0.5))))
    S, sx, sy = Q.load_sec(f); sy = sy - Q.OFF_R3; S = S[int(np.searchsorted(sy, -25.0)):]
    ns = np.abs(np.diff((S < 0).astype(np.int8), axis=0)).sum(0)
    x4 = xs[::4]; h4 = hfin[::4]; n4 = nchg[::4]
    ii = np.rint((x4 - xh[0]) / 0.5).astype(int)
    ins = (x4 >= sx[0] - 1e-6) & (x4 <= sx[-1] + 1e-6)
    js = np.clip(np.rint((x4 - sx[0]) / 0.5).astype(int), 0, len(sx) - 1)
    nsa = np.ones(len(x4), int); nsa[ins] = ns[js[ins]]
    ok = (np.abs(x4 - crest[f]) > 20) & (n4 == 1) & (nsa == 1) & (slope[ii] < 30) & np.isfinite(h4)
    d = np.abs(h4[ok] - eta[ii[ok]])
    key = "before" if f < 3745 else "after"
    D[key].append(d); Din[key].append(np.abs(h4[ok & ins] - eta[ii[ok & ins]]))
    if d.max() > W[key][0]:
        k = int(np.argmax(d)); W[key] = (float(d.max()), [f, float(x4[ok][k]), float(x4[ok][k] - crest[f])])
out = {}
for k in D:
    a = np.concatenate(D[k]); b = np.concatenate(Din[k])
    out[k] = dict(n=int(len(a)), p99=float(np.percentile(a, 99)), max=float(a.max()), worst=W[k][1], n_in_sec=int(len(b)),
                  p99_in_sec=float(np.percentile(b, 99)), max_in_sec=float(b.max()), n_over_0p25=int((a > 0.25).sum()))
    print(k, out[k])
json.dump(out, open(Q.OUT + "/q_c2a_split.json", "w"), indent=1)
