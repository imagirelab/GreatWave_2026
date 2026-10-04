# -*- coding: utf-8 -*-
"""美術の見本05 の組み立て（Q33）：形 B の主役波に、材質 AS05 の T6 の規則（mat_edge.py の既定の規則）を、見本04 の主役波で決めた行・縁のまま当てる。

  py -3.10 -B Tools/GWWaveGen/as05/fx5_b_edge.py <形の静止のメッシュ.json> <出力.json>
  （直しの回 fix1：asm5_b_edge.py（変えない）の写しで、入力と出力のパスを引数にしただけ）

なぜ：形 B は形づくりの係が自分の規則で原画視点の内の縁の白を藍にしてあるので、mat_edge.py をそのまま回すと「主の視点の縁の画素に白がない」で
何も変えない（ほかの視点 seat・seat_toward_wave・crest0・crest45 の確かめも飛ばす）。その結果、波頭の回り台 45° などで右の脇の稜の頂の白・水色の帯が
形 B だけに残り、形 A（と材質の係の AS05F）と材質がそろわない。
どうする：右の脇の稜の行（c 5.7〜13.7 m）は、形 A・形 B・見本04 で点の位置が同じ（K-top：行 c ≥ −8 m の動き 0）。そこで mat_edge.run_rule を
見本04 の静止のメッシュ（主役波 AS04F ＋ wave4、材質の係の AS05F と同じ入力）で回してサブ行ごとの縁の t と重みを得て、mat_edge.apply を形 B の whiteSD に当てる
（new = old + w·lim·(min(old, t_cut − margin − t) − old)。白を縁から見えない側へ下げるだけで、藍を白にはしない）。
書くのは形 B の主役波の頂点の whiteSD（uv5.z）だけ。位置・三角形・ほかのチャンネル・wave4 は形 B のまま。
出力：Unity/Build/Polish/sample05/assemble/B/mesh/union_AS05B_m2.json（.bin）と _edge_report.json
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_common as M  # noqa: E402
import mat_edge as E  # noqa: E402

P5 = M.P5
SRC_B = sys.argv[1] if len(sys.argv) > 1 else P5 + "/fix1/B/union/union.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else P5 + "/fix1/assemble/B/mesh/union_AS05B_f1.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)


def main():
    t0 = time.time()
    rule = E.DEFAULT_RULES[0]
    ch4, tri4, j4 = M.read_static(M.UNION04F)
    H4 = M.Hero(ch4, tri4, M.N_HERO04F)
    res, rec = E.run_rule(rule, ch4, tri4, H4, M.CLAWS04F)
    tc, w = res
    E.log("見本04 の主役波で規則を決めた", rec.get("subrows"), rec.get("c_m"), rec.get("extend_end"))
    chB, triB, jB = M.read_static(SRC_B)
    HB = M.Hero(chB, triB, M.N_HERO04F)
    same_rows = bool(np.array_equal(HB.row_values, H4.row_values))
    if not same_rows:
        raise SystemExit("形 B と見本04 のサブ行が違う")
    ws = w[HB.sr] > 0
    pos_diff = float(np.abs(HB.pos[ws] - H4.pos[ws]).max())
    t_diff = float(np.abs(HB.t[ws] - H4.t[ws]).max())
    if pos_diff > 1e-6 or t_diff > 1e-6:
        raise SystemExit("規則の行で点の位置が見本04 と違う：%g %g" % (pos_diff, t_diff))
    newB, wv = E.apply(HB, HB.wsd.copy(), tc, w, rule)
    flipped = (HB.wsd > 0) & (newB <= 0)
    ch2 = {k: v.copy() for k, v in chB.items()}
    ch2["uv5"][:M.N_HERO04F, 2] = newB.astype(np.float32)
    h = M.write_static(OUT, ch2, triB, {"as05_asm_b_edge": {"source": M.rel(SRC_B), "source_sha256": jB.get("sha256"),
                                                            "note_ja": "形 B の主役波の whiteSD だけを fx5_b_edge.py（asm5_b_edge.py の写し）で書き換えた（見本04 の主役波で決めた T6 の規則）"}})
    # 見本04 の AS05F（材質の係）と同じ行・同じ縁になっているかの確かめ
    chF, _, _ = M.read_static(M.MAT + "/mesh/union_as05.json")
    wf = chF["uv5"][:M.N_HERO04F, 2].astype(np.float64)
    d4 = (wf - H4.wsd)
    dB = (newB - HB.wsd)
    rep = {"schema": "GreatWave.AS05.fx5_b_edge/1", "date": time.strftime("%Y-%m-%d %H:%M"), "tool": M.rel(__file__), "tool_sha256": M.sha(__file__),
           "rule": rule, "rule_result_on_AS04F": rec,
           "input_B": {"mesh": M.rel(SRC_B), "bin_sha256": jB.get("sha256")}, "output": {"mesh": M.rel(OUT), "bin_sha256": h},
           "check": {"same_subrows_as_AS04F": same_rows, "rule_rows_position_max_diff_m": pos_diff, "rule_rows_t_max_diff_m": t_diff,
                     "rule_vertices": int(ws.sum()),
                     "AS05F_vertices_changed": int((np.abs(d4) > 1e-6).sum()), "B_vertices_changed": int((np.abs(dB) > 1e-6).sum()),
                     "AS05F_white_to_indigo": int(((H4.wsd > 0) & (wf <= 0)).sum()), "B_white_to_indigo": int(flipped.sum()),
                     "B_white_to_indigo_area_m2": M.rnd(HB.varea[flipped].sum(), 2),
                     "B_indigo_to_white": int(((HB.wsd <= 0) & (newB > 0)).sum())},
           "seconds": round(time.time() - t0, 1),
           "note_ja": ("原画の色は面へ写さない。原画のカメラ（とほかの 4 視点）は見本04 の主役波で縁の頂点を探すのにだけ使った。"
                       "右の脇の稜の行は形 B と見本04 で点の位置が同じなので、同じ規則がそのまま当たる")}
    M.jdump(os.path.splitext(OUT)[0] + "_edge_report.json", rep)
    E.log(json.dumps(rep["check"], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
