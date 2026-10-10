# -*- coding: utf-8 -*-
"""2c. 取り直しの誤差（計画 C3）を、焼いた A・B（float32）と自分の R3 の線で、頂点も含めた正確な距離で測る（両向き、x 100〜925 m の全部）。
出力：out/k_c3exact.json"""
import numpy as np
from k_lib import *

my = MyFrames(); pairs, man = load_pairs()
per = []
for p in range(570):
    for side, f in ((0, F0 + p), (1, F0 + p + 1)):
        P = pairs[p, side].astype(np.float64); P[:, 0] += X0B
        R = my.main_of(f)
        d1, _ = SegTree([R]).dist(P)
        Q = np.vstack([R, densify(R, 0.01)])
        d2, _ = SegTree([P]).dist(Q)
        per.append((float(max(d1.max(), d2.max())), p, side, float(d1.max())))
m = max(per)
res = dict(max=m[0], pair=m[1], side=m[2], max_baked_to_r3=max(v[3] for v in per), n_over_0_02=sum(1 for v in per if v[0] > 0.02), n=len(per))
print(res)
jsave(OUT + "/k_c3exact.json", res)
