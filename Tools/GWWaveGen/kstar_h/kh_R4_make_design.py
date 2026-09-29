# -*- coding: utf-8 -*-
"""K*′ 精修 R4：R3 の設計（kstarR3_design.json）から R4 の設計を作り直す手順を 1 つにまとめたもの（py -3.10、約 3 分）。
R4 の作業の途中で順に試して選んだ鍵の変更を、同じ順で当てる（値は kh_designR4 の説明と kstarR4_difference_record.json）：
  1 far_top（奥の行の頂を丸く）：c 5.5 で 0 → 8.5 から奥で 1
  2 far_back（奥の行の背をなめらかに）：c 3 で 0 → 6 から奥で 1
  3 唇の頭の鍵 lip_shift / lip_drop：c 0〜9.5 を σ 0.6 m でならして 1 m おきの鍵へ当て直す（kh_R4_lipsmooth.py、c 0 より手前と 9.5 より奥は元のまま）
  4 lip_thick の c −26 の鍵 0.02 → 0.05（尾の唇の上下の間隔）
  5 crest_height の手前の端の鍵（c −40 → 2.4 m、c −34 → 5.0 m。鍵の数は同じ）と tail_fade（c −21 より手前の尾をうねりへ）
  6 back_depth の c −25 の鍵 0.3 → 0.42（肩と尾の境の足のくびれ）
  7 整えの層 sculpt_01..15 を kh_R4_sculpt.py で解く（引数は SCULPT_ARGS）
モジュールの定数（kh_designR4 の BS_C0/BS_C1 = −3/9、SCULPT_SIG = 8、SC_TOP_C = 0.5 など）は kh_designR4.py の中。
usage: py -3.10 kh_R4_make_design.py <kstarR3_design.json> <out.json> [--check <R4 design.json>]
"""
import os
import sys
import json
import subprocess
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import kh_designR4 as D  # noqa: E402

SCULPT_ARGS = ["--iters", "16", "--pin", "50", "--bound", "1.5", "--notch", "1.0", "--wr4", "3.0", "--t4", "0.2", "--lamdc", "10",
               "--lamdr", "1.0", "--notch-hmax", "10", "--wfair", "0.5"]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")


def set_key(d, name, c, v):
    cs, vs = d.keys[name]
    cs = list(cs); vs = list(vs)
    vs[cs.index(c)] = v
    d.keys[name] = (cs, vs)


def main():
    a = sys.argv[1:]
    src, out = a[0], a[1]
    tmp = out + ".base.json"
    d = D.Design.load(src)
    for n in D.SCULPT_NAMES:
        d.keys[n] = ([0.0], [0.0])
    d.keys["far_top"] = ([5.5, 8.5, 16.0], [0.0, 1.0, 1.0])
    d.keys["far_back"] = ([3.0, 6.0, 16.0], [0.0, 1.0, 1.0])
    d.save(tmp)
    subprocess.run(["py", "-3.10", os.path.join(HERE, "kh_R4_lipsmooth.py"), tmp, tmp, "--sig", "0.6", "--keep-near", "0.0", "--keep-far", "9.5"],
                   check=True, env=ENV)
    d = D.Design.load(tmp)
    set_key(d, "lip_thick", -26.0, 0.05)
    set_key(d, "crest_height", -40.0, 2.4)
    set_key(d, "crest_height", -34.0, 5.0)
    d.keys["tail_fade"] = ([-60.0, -50.0, -42.0, -35.0, -30.0, -26.0, -23.0, -21.0, -18.0, 0.0, 18.0],
                           [1.0, 1.0, 1.0, 1.0, 0.95, 0.55, 0.12, 0.0, 0.0, 0.0, 0.0])
    set_key(d, "back_depth", -25.0, 0.42)
    d.save(tmp)
    subprocess.run(["py", "-3.10", os.path.join(HERE, "kh_R4_sculpt.py"), tmp, out] + SCULPT_ARGS, check=True, env=ENV)
    os.remove(tmp)
    if "--check" in a:
        ref = D.Design.load(a[a.index("--check") + 1]); new = D.Design.load(out)
        worst = 0.0
        for n in D.PNAMES:
            ca, va = ref.keys[n]; cb, vb = new.keys[n]
            if len(ca) != len(cb) or np.max(np.abs(np.array(ca) - np.array(cb))) > 1e-9:
                print("keys differ:", n); worst = 9.0; continue
            worst = max(worst, float(np.max(np.abs(np.array(va) - np.array(vb)))))
        c1, A1, Y1, _ = D.build(ref); c2, A2, Y2, _ = D.build(new)
        print(json.dumps({"max_key_value_diff": worst, "max_vertex_diff_m": float(max(np.abs(A1 - A2).max(), np.abs(Y1 - Y2).max()))}))


if __name__ == "__main__":
    main()
