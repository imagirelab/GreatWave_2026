# -*- coding: utf-8 -*-
"""R4b 確かめ：巻き始めの読み（弦の長さ・コマ）での C3 の感度と、群の次の頂の巻き始め。py -3.10 b_sens.py → b_sens.json
b_geom.py の自前の関数を使う。"""
import numpy as np
import b_common as B
import b_geom as G


_CACHE = {}


def onset_scan(rid, chord_cells, f0=3600, f1=3800):
    cf = B.cfg(rid); xp = cf["parms"]["x_p"]; vox = cf["parms"]["dp"] * 2
    if rid not in _CACHE:
        D = B.hf(rid); _CACHE[rid] = (D, B.SecReader(rid))
    D, S = _CACHE[rid]
    off = B.still(D, xp, "mid"); x = D["x"] - xp
    fidx = {int(f): i for i, f in enumerate(D["frames"])}
    res = {}
    for fr in S.frames:
        if fr < f0 or fr > f1:
            continue
        g = G.frame_geo(S.get(fr), S.meta, off, xp, vox, chord_cells=chord_cells)
        tp = G.top(D["eta"][fidx[int(fr)], 2, :] - off, x)
        res[int(fr)] = (g["thmax"], g["vert_x"], tp["steep"], tp["eta_c"], tp["H"])
    return res, D, S, off, xp, vox, x, fidx


def first_onset(res):
    for fr in sorted(res):
        if np.isfinite(res[fr][0]) and res[fr][0] >= 90:
            return fr
    return None


def main():
    out = {}
    base = {}
    for rid in ("R3", "R4d"):
        vox = B.cfg(rid)["parms"]["dp"] * 2
        o = {}
        for nm, cc in dict(cell1=1.0, cell2=2.0, cell05=0.5, m1p0=1.0 / vox).items():
            res, D, S, off, xp, vox_, x, fidx = onset_scan(rid, cc)
            fo = first_onset(res)
            o[nm] = dict(frame=fo, t=(fo - 1) / 24, x=res[fo][1], steep=res[fo][2], eta_c=res[fo][3], H=res[fo][4],
                         steep_pm1=[res[fo - 1][2], res[fo][2], res[fo + 1][2]], chord_m=round(cc * 2) * 0.5 * vox)
        out[rid] = o
        # 群の次の頂（175 s から、頂を 650 m より先に限る）
        nxt = None
        for fr in S.frames:
            t = (fr - 1) / 24
            if t < 175.0:
                continue
            g = G.frame_geo(S.get(fr), S.meta, off, xp, vox, xmin=650.0)
            if g is None or not np.isfinite(g.get("thmax", np.nan)):
                continue
            if g["thmax"] >= 90:
                tp = G.top(D["eta"][fidx[int(fr)], 2, :] - off, x, xmin=650.0)
                lips = []
                for f2 in S.frames:
                    if fr <= f2 <= fr + 48:
                        g2 = G.frame_geo(S.get(f2), S.meta, off, xp, vox, xmin=650.0)
                        if g2 and g2["reach"]:
                            lips.append(g2["reach"])
                nxt = dict(frame=int(fr), t=t, vert_x=g["vert_x"], crest_x=g["xc"], steep=tp["steep"], lip_max_2s=max(lips) if lips else None)
                break
        out[rid]["next_crest"] = nxt
        print(rid, out[rid])
    # C3 の比（基準 R4）
    c3 = {}
    for nm in ("cell1", "cell2", "cell05", "m1p0"):
        c3[nm] = out["R3"][nm]["steep"] / out["R4d"][nm]["steep"] - 1
    pm = []
    for i in range(3):
        for j in range(3):
            pm.append(out["R3"]["cell1"]["steep_pm1"][i] / out["R4d"]["cell1"]["steep_pm1"][j] - 1)
    c3["pm1_range"] = [min(pm), max(pm)]
    c3["both_one_later"] = out["R3"]["cell1"]["steep_pm1"][2] / out["R4d"]["cell1"]["steep_pm1"][2] - 1
    out["C3"] = c3
    print(c3)
    B.dump("b_sens.json", out)


if __name__ == "__main__":
    main()
