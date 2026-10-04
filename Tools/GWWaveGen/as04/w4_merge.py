# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4：主役波の静止のメッシュと別の波（④）の静止のメッシュを 1 つにつなぐ（描画の道具 AS03AsmRender の -as03Surf は 1 つだけ読むため）。
どちらも書式 GreatWave.AS03.static_mesh/1・同じチャンネル（position・normal・tangent・uv3〜uv6）。頂点と三角形を順に並べるだけで、値は変えない。
使い方：py -3.10 -B Tools/GWWaveGen/as04/w4_merge.py <主役波.json> <別の波.json> <出力.json>
"""
import sys

import numpy as np

import w4_common as W


def main(h, w, o):
    ch1, t1, j1 = W.read_static(h)
    ch2, t2, j2 = W.read_static(w)
    n1 = len(ch1["position"])
    ch = {k: np.concatenate([ch1[k], ch2[k]]) for k, _ in W.CHANNELS}
    tri = np.concatenate([t1.astype(np.int64), t2.astype(np.int64) + n1])
    hs = W.write_static(o, ch, tri, {"note_ja": "見本04 W4：主役波と別の波（④）をつないだ静止のメッシュ（頂点 0〜%d が主役波、その後が別の波）" % (n1 - 1),
                                     "parts": [{"json": h, "bin_sha256": j1["sha256"], "vertices": int(n1), "triangles": int(len(t1))},
                                               {"json": w, "bin_sha256": j2["sha256"], "vertices": int(len(ch2["position"])), "triangles": int(len(t2))}]})
    print("merged", o, n1 + len(ch2["position"]), len(tri), hs)


if __name__ == "__main__":
    main(*sys.argv[1:4])
