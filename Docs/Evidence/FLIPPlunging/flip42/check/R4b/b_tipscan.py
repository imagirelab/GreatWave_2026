# -*- coding: utf-8 -*-
"""R4b 確かめ：着水の後から終わり（187.8 s）まで、噴流の先（自前の読み）の最も低い所。py -3.10 b_tipscan.py R4d R3"""
import sys
import numpy as np
import b_common as B
import b_geom as G

out = {}
for rid in sys.argv[1:]:
    cf = B.cfg(rid); xp = cf["parms"]["x_p"]; vox = cf["parms"]["dp"] * 2
    D = B.hf(rid); off = B.still(D, xp, "mid")
    S = B.SecReader(rid)
    t0 = {"R4d": 156.125, "R3": 156.0, "R2": 155.292}[rid]
    lows = []
    for fr in S.frames:
        t = (fr - 1) / 24
        if t <= t0:
            continue
        g = G.frame_geo(S.get(fr), S.meta, off, xp, vox)
        if g and g["tip"] is not None:
            lows.append((g["tip"][1], t, g["tip"][0]))
    lows.sort()
    out[rid] = dict(n_frames_with_tip=len(lows), lowest=lows[:5], below_zero=[l for l in lows if l[0] <= 0][:5])
    print(rid, out[rid])
B.dump("b_tipscan.json", out)
