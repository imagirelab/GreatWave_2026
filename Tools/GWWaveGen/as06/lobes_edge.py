# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：T6（Q33 の切り出し、原画視点の唇の下の内の縁に白を置かない）の白の印の書き換えを、見本05 B10 から写す。
見本05 の fx5_b_edge.py（変えない）は見本04 と同じサブ行の並びを前提にする。見本06 は ③ の左の端のため静止のメッシュの行の範囲を
c −24.4 m からにした（サブ行の番号がずれる）ので、B10 で白 → 藍に書き換えた頂点（右の脇の稜、c 5.7〜13.7 m の行。形は見本04・B10・AS06L で同じ）を、
同じ位置（1e−4 m 以内）の AS06L の頂点へ、書き換えた後の値ごと写す。原画のカメラの投影は使わない（頂点の位置だけ）。
py -3.10 -B Tools/GWWaveGen/as06/lobes_edge.py <AS06L の union.json> <出力.json> <AS06L の主役波の静止のメッシュ.json>
"""
import json
import os
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05")
import mat_common as M  # noqa: E402

P5 = M.P5
B_PRE = P5 + "/fix1/B/union/union.json"
B_EDGE = P5 + "/fix1/assemble/B/mesh/union_AS05B_f1.json"


def main():
    t0 = time.time()
    src, out, hero = sys.argv[1], sys.argv[2], sys.argv[3]
    nh = json.load(open(hero, encoding="utf-8"))["vertices"]
    chp, _, _ = M.read_static(B_PRE)
    che, _, je = M.read_static(B_EDGE)
    n4 = M.N_HERO04F
    wpre = chp["uv5"][:n4, 2].astype(np.float64); wedge = che["uv5"][:n4, 2].astype(np.float64)
    chg = np.nonzero(np.abs(wedge - wpre) > 1e-6)[0]
    Pb = che["position"][:n4][chg].astype(np.float64)
    ch, tri, js = M.read_static(src)
    P = ch["position"][:nh].astype(np.float64)
    d, k = cKDTree(P).query(Pb)
    ok = d < 1e-4
    w = ch["uv5"][:nh, 2].astype(np.float64).copy()
    before = w[k[ok]].copy()
    w[k[ok]] = wedge[chg][ok]
    ch2 = {kk: v.copy() for kk, v in ch.items()}
    ch2["uv5"][:nh, 2] = w.astype(np.float32)
    h = M.write_static(out, ch2, tri, {"as06_lobes_edge": {"source": M.rel(src), "source_sha256": js.get("sha256"),
                                                          "note_ja": "B10 の T6 の白の書き換え（fx5_b_edge.py）を、同じ位置の頂点へ写した"}})
    rep = {"schema": "GreatWave.AS06.lobes_edge/1", "date": time.strftime("%Y-%m-%d %H:%M"), "tool": M.rel(__file__), "tool_sha256": M.sha(__file__),
           "b10_pre": M.rel(B_PRE), "b10_edge": M.rel(B_EDGE), "b10_edge_bin_sha256": je.get("sha256"),
           "b10_changed_vertices": int(len(chg)), "matched": int(ok.sum()), "max_match_dist_m": float(d.max()),
           "white_to_indigo": int(((before > 0) & (w[k[ok]] <= 0)).sum()), "output": {"mesh": M.rel(out), "bin_sha256": h},
           "seconds": round(time.time() - t0, 1)}
    M.jdump(os.path.splitext(out)[0] + "_edge_report.json", rep)
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
