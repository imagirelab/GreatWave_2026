# -*- coding: utf-8 -*-
"""C2 (a) re-check: (1) reproduce the project's column selection (sec crossings counted over the whole sec column, incl. the bed),
(2) the plan's intent (sec crossings counted only above 25 m below still level), with the coarse-manifest crest window."""
import json, numpy as np
import q_lib as Q
OFF = Q.still_offset_fine()
cm = json.load(open(Q.DATA + "/coarse/manifest.json", encoding="utf8"))
crest = {r["frame"]: r["crest_x"] for r in cm["frames"]}
res = {}
for variant in ("project_full_sec_column", "sec_above_minus25"):
    D = []; rows = []; ncols_in_sec = 0
    for f in range(3319, 3890):
        phi, xs, ys = Q.load_phi(f)
        hfin, nchg = Q.top_height(phi, ys - OFF)
        eta, xh = Q.load_hf(f); eta = eta - Q.OFF_R3
        slope = np.degrees(np.arctan(np.abs(np.gradient(eta, 0.5))))
        S, sx, sy = Q.load_sec(f); sy = sy - Q.OFF_R3
        if variant == "sec_above_minus25":
            j0 = int(np.searchsorted(sy, -25.0)); S = S[j0:]
        ns = np.abs(np.diff((S < 0).astype(np.int8), axis=0)).sum(0)
        x4 = xs[::4]; h4 = hfin[::4]; n4 = nchg[::4]
        ii = np.rint((x4 - xh[0]) / 0.5).astype(int)
        ins = (x4 >= sx[0] - 1e-6) & (x4 <= sx[-1] + 1e-6)
        js = np.clip(np.rint((x4 - sx[0]) / 0.5).astype(int), 0, len(sx) - 1)
        nsa = np.ones(len(x4), int); nsa[ins] = ns[js[ins]]
        ok = (np.abs(x4 - crest[f]) > 20) & (n4 == 1) & (nsa == 1) & (slope[ii] < 30) & np.isfinite(h4)
        ncols_in_sec += int((ok & ins).sum())
        d = np.abs(h4[ok] - eta[ii[ok]])
        D.append(d)
        for k in np.where(d > 0.25)[0]:
            rows.append([f, float(x4[ok][k]), float(d[k]), float(h4[ok][k]), float(eta[ii[ok]][k]), float(x4[ok][k] - crest[f])])
    D = np.concatenate(D)
    rows = np.array(rows) if rows else np.zeros((0, 6))
    res[variant] = dict(n=int(len(D)), n_in_sec=ncols_in_sec, p99=float(np.percentile(D, 99)), max=float(D.max()),
                        n_over_0p25=int(len(rows)), frames_over=sorted(set(int(r[0]) for r in rows)),
                        n_over_before_contact=int((rows[:, 0] < 3745).sum()) if len(rows) else 0,
                        worst=rows[np.argmax(rows[:, 2])].tolist() if len(rows) else None,
                        x_minus_crest_range=[float(rows[:, 5].min()), float(rows[:, 5].max())] if len(rows) else None)
    print(variant, json.dumps(res[variant]))
    if len(rows):
        print("  examples", rows[np.argsort(-rows[:, 2])[:8]].round(3).tolist())
json.dump(res, open(Q.OUT + "/q_c2a.json", "w"), indent=1)
