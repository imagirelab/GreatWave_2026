# -*- coding: utf-8 -*-
"""Own K for the fine source: first frame whose (air, water, undecided) closed-loop counts inside crest +-30 m (x-range overlap) change."""
import json, numpy as np
import q_lib as Q
OFF = Q.still_offset_fine()
man = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
crest = {r["frame"]: r["crest_x"] for r in man["frames"]}
prev = None; K = None; rows = []
for f in range(3319, 3790):
    phi, xs, ys = Q.load_phi(f)
    xc = crest[f]
    m = (xs >= xc - 32) & (xs <= xc + 32)
    cnt = [0, 0, 0]
    for P, ph, A in Q.closed_loops(phi[:, m], xs[m], ys - OFF):
        if P[:, 0].max() >= xc - 30 and P[:, 0].min() <= xc + 30:
            cnt[{1: 0, -1: 1, 0: 2}[ph]] += 1
    cnt = tuple(cnt)
    mt = tuple(man["frames"][f - 3319]["topo_air_water_unknown"])
    rows.append([f, cnt, mt])
    if prev is not None and cnt != prev and K is None:
        K = f
    prev = cnt
print("own K", K, "manifest K", man["playback"]["K"])
print("frames where own counts differ from manifest:", [r for r in rows if tuple(r[1]) != tuple(r[2])][:10])
print([r for r in rows if 3740 <= r[0] <= 3750])
json.dump(dict(K=K, rows=rows), open(Q.OUT + "/q_k.json", "w"))
