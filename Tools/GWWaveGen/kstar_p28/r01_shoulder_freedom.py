# -*- coding: utf-8 -*-
"""仕上げ28修正01 SHOULDER：後ろから見た山の輪郭 H(c) が、原画視点を変えずにどれだけ動けるか（記録、py -3.10）。
行ごとに：土台の頂 H、原画視点で見えている頂点の最も高い y（その行の H はこれより下げられない。見える頂点は動かせない）、
頂の a での空の射線の禁止域の天井（膨らみ 3 px、その行の H はこれより上げられない）、頂より後ろ（a < 頂の a）での天井の最大。
あわせて、候補と土台の真後ろ（b90）の輪郭の差を、行の頂の高さ（max y）で比べる（後ろから見た山の輪郭は、背の殻の高さが頂を越えない限り H(c)）。
usage: py -3.10 r01_shoulder_freedom.py <out.json> <cand_rows.npz>"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_shoulder_common as S  # noqa: E402
import r01_shoulder_build as SB  # noqa: E402

R = S.R


def main():
    out, cand = sys.argv[1], sys.argv[2]
    c, A0, Y0 = S.load_rows()
    _, A1, Y1 = S.load_rows(cand)
    G = R.keepout_grids(c, 3, 2, cache=S.KEEPOUT_CACHE)
    _, visv = SB.vis_vertices(c, A0, Y0, cache=os.path.join(S.OUT, "cache", "vis_quads_base.npy"))
    yy = R.GY0 + np.arange(R.NY) * R.GRES
    rows = []
    for cc in [-16, -12, -10, -8, -6, -4, -2, -1, 0, 1.4, 2, 3, 4, 5, 6, 7, 8, 9, 9.6, 10.2, 10.8, 11.4, 12, 12.6, 13.2, 13.8, 14.4]:
        r = int(np.argmin(np.abs(c - cc)))
        jt = int(np.argmax(Y0[r, :200])); at = A0[r, jt]; H = Y0[r, jt]
        v = np.nonzero(visv[r])[0]
        vmax = float(Y0[r, v].max()) if len(v) else None
        crest_pinned = bool(visv[r, jt])
        ia = int(round((at - R.GA0) / R.GRES))
        col = G[r, :, ia]; k = np.nonzero(col & (yy > H))[0]
        ceil_at = float(yy[k[0]]) if len(k) else None
        ceil_back = []
        for ia2 in range(max(0, ia - int(12 / R.GRES)), ia + 1):
            k2 = np.nonzero(G[r, :, ia2] & (yy > 0))[0]
            ceil_back.append(yy[k2[0]] if len(k2) else 40.0)
        rows.append({"c": round(float(c[r]), 2), "H_base": round(float(H), 2), "H_cand": round(float(Y1[r].max()), 2),
                     "crest_visible_in_painting": crest_pinned, "visible_max_y": None if vmax is None else round(vmax, 2),
                     "ceiling_above_crest": None if ceil_at is None else round(ceil_at, 2),
                     "ceiling_max_within_12m_behind_crest": round(float(max(ceil_back)), 2)})
    res = {"note_ja": "頂が原画視点で見える行（crest_visible_in_painting）は H を変えられない。見えない行でも、H は visible_max_y（管の口から見える唇と管の天井）より下げられず、"
                      "ceiling_above_crest より上げられない（頂の a のまま）。後ろへずらせば天井は ceiling_max_within_12m_behind_crest まで上がる。",
           "rows": rows, "H_change_max_m_cand_vs_base": round(float(np.abs(Y1.max(1) - Y0.max(1)).max()), 4)}
    S.jdump(res, out)
    for x in rows:
        print(x)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
