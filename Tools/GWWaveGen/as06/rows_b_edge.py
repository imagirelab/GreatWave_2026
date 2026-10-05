# -*- coding: utf-8 -*-
"""美術の見本06 の段の行（B-ROWS）：as05/fx5_b_edge.py（変えない）の写し。材質 AS05 の T6 の規則（mat_edge.py の既定の規則、見本04 の主役波で決めた
サブ行ごとの縁の t と重み）を、AS06R の主役波の whiteSD に当てる。
変えた所：AS06R の静止のメッシュは行の範囲を c −25.2 m まで広げた（rows_mesh.py）ので、サブ行の数が見本04 と違う（主役波の頂点 326,400、見本04 は 314,400）。
サブ行を「行の値（uv6.x、0〜239 の小数）」で見本04 のサブ行へ対応させ、見本04 に無いサブ行（c < −22 m）は規則を当てない（重み 0）。
規則が当たる行（右の脇の稜 c 5.7〜13.7 m）は AS06R と見本04 で点の位置が同じ（K-top）ことを確かめる。
py -3.10 -B Tools/GWWaveGen/as06/rows_b_edge.py <union.json> <hero_smooth.json> <出力.json>
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05")
import mat_common as M  # noqa: E402
import mat_edge as E  # noqa: E402

SRC, HERO_JSON, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(os.path.dirname(OUT), exist_ok=True)


def main():
    t0 = time.time()
    rule = E.DEFAULT_RULES[0]
    ch4, tri4, j4 = M.read_static(M.UNION04F)
    H4 = M.Hero(ch4, tri4, M.N_HERO04F)
    res, rec = E.run_rule(rule, ch4, tri4, H4, M.CLAWS04F)
    tc4, w4 = res
    E.log("見本04 の主役波で規則を決めた", rec.get("subrows"), rec.get("c_m"), rec.get("extend_end"))
    nh = int(json.load(open(HERO_JSON, encoding="utf-8")).get("vertices") or 0)
    chB, triB, jB = M.read_static(SRC)
    if not nh:
        chH, _, _ = M.read_static(HERO_JSON)
        nh = len(chH["position"])
    HB = M.Hero(chB, triB, nh)
    # サブ行の対応（行の値で）
    idx = np.searchsorted(H4.row_values, HB.row_values)
    idx = np.clip(idx, 0, len(H4.row_values) - 1)
    ok = np.abs(H4.row_values[idx] - HB.row_values) < 1e-3
    tc = np.where(ok, tc4[idx], 0.0)
    w = np.where(ok, w4[idx], 0.0)
    ws = w[HB.sr] > 0
    # 規則の行で、点の位置と t が見本04 と同じか（同じサブ行・同じ列の頂点どうし）
    key4 = {(int(sr_), int(round(cl_))): i for i, (sr_, cl_) in enumerate(zip(H4.sr, H4.col)) if w4[sr_] > 0}
    pd_, td_ = 0.0, 0.0
    for i in np.nonzero(ws)[0]:
        j = key4.get((int(idx[HB.sr[i]]), int(round(HB.col[i]))))
        if j is None:
            continue
        pd_ = max(pd_, float(np.abs(HB.pos[i] - H4.pos[j]).max())); td_ = max(td_, abs(float(HB.t[i] - H4.t[j])))
    if pd_ > 1e-5 or td_ > 1e-5:
        raise SystemExit("規則の行で点の位置が見本04 と違う：%g %g" % (pd_, td_))
    newB, wv = E.apply(HB, HB.wsd.copy(), tc, w, rule)
    flipped = (HB.wsd > 0) & (newB <= 0)
    ch2 = {k: v.copy() for k, v in chB.items()}
    ch2["uv5"][:nh, 2] = newB.astype(np.float32)
    h = M.write_static(OUT, ch2, triB, {"as06_rows_b_edge": {"source": M.rel(SRC), "source_sha256": jB.get("sha256"),
                                                             "note_ja": "AS06R の主役波の whiteSD だけを rows_b_edge.py（fx5_b_edge.py の写し）で書き換えた（見本04 の主役波で決めた T6 の規則）"}})
    rep = {"schema": "GreatWave.AS06.rows_b_edge/1", "date": time.strftime("%Y-%m-%d %H:%M"), "tool": M.rel(__file__), "tool_sha256": M.sha(__file__),
           "rule": rule, "rule_result_on_AS04F": rec, "hero_vertices": nh,
           "input": {"mesh": M.rel(SRC), "bin_sha256": jB.get("sha256")}, "output": {"mesh": M.rel(OUT), "bin_sha256": h},
           "check": {"subrows_AS06R": int(HB.nsr), "subrows_AS04F": int(H4.nsr), "subrows_matched": int(ok.sum()),
                     "rule_rows_position_max_diff_m": pd_, "rule_rows_t_max_diff_m": td_, "rule_vertices": int(ws.sum()),
                     "white_to_indigo": int(flipped.sum()), "white_to_indigo_area_m2": M.rnd(HB.varea[flipped].sum(), 2),
                     "indigo_to_white": int(((HB.wsd <= 0) & (newB > 0)).sum())},
           "seconds": round(time.time() - t0, 1),
           "note_ja": "原画の色は面へ写さない。原画のカメラ（とほかの 4 視点）は見本04 の主役波で縁の頂点を探すのにだけ使った"}
    M.jdump(os.path.splitext(OUT)[0] + "_edge_report.json", rep)
    E.log(json.dumps(rep["check"], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
