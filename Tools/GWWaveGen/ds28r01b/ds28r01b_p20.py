# -*- coding: utf-8 -*-
"""設計28修正01 試行B：P20（名前の付いた美術の誘導の大きさ、記録）。生成器を直接呼び、入れた版とその 1 つだけを切った版の頂点の差を測る
（量子化なし）。

  ds_lip_carry（唇の運び。唇の下のえぐりの早め＝錨の時計の lead を含む）：入れた版 − 運びを切った版（＝設計28 の入れた版）
  ds_lip_carry のうち唇の下のえぐりの早め（undercut lead）だけ：入れた版 − lead を 0 にした版
  ds_claws_follow_lip：入れた版 − 爪の細部を運ばない版（細部は設計28 と同じく放出の後の打ち出しで育つ）
使い方（リポジトリの根で。1 変種 約 3〜4 分）：py -3.10 -B Tools/GWWaveGen/ds28r01b/ds28r01b_p20.py --variant V75 [--out Unity/Build/Design/28R01B/p20]
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds28r01b_model as MB  # noqa: E402

TAUS = [-6.0, -5.0, -4.2, -4.0, -3.8, -3.6, -3.4, -3.2, -3.0, -2.8, -2.6, -2.4, -2.2, -2.0, -1.8, -1.6, -1.4, -1.2, -1.0, -0.8, -0.6,
        -0.4, -0.2, 0.0]


def diff(g1, g0, taus):
    rows = []
    for tau in taus:
        X1 = g1.local(tau)
        X0 = g0.local(tau)
        dd = np.linalg.norm(X1 - X0, axis=-1)
        i = np.unravel_index(int(dd.argmax()), dd.shape)
        rows.append(dict(tau=tau, max_m=round(float(dd.max()), 4), rms_m=round(float(np.sqrt((dd ** 2).mean())), 5),
                         max_at=dict(row=int(i[0]), col=int(i[1]), c_m=round(float(g1.K.c[i[0]]), 2)), vertices_over_5cm=int((dd > 0.05).sum()),
                         main_row_max_m=round(float(dd[int(g1.K.main_row)].max()), 4), peak_row_max_m=round(float(dd[192].max()), 4)))
    k = max(rows, key=lambda r: r["max_m"])
    first = next((r["tau"] for r in rows if r["max_m"] > 0.005), None)
    return dict(max_m=k["max_m"], max_tau=k["tau"], max_at=k["max_at"], rms_max_m=max(r["rms_m"] for r in rows),
                first_tau_over_5mm=first, at_tstar_max_m=rows[-1]["max_m"], per_tau=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--out", default=os.path.join(MB.REPO, "Unity", "Build", "Design", "28R01B", "p20"))
    a = ap.parse_args()
    t0 = time.time()
    v = a.variant
    g_on = MB.Generator("art_on", carry_variant=v)
    g_nc = MB.Generator("art_on", carry_variant=v, claws_follow=False)
    g_nu = MB.Generator("art_on", carry_variant=v, overrides={"variants": {v: {"undercut_lead_s": 0.0}}})
    g_28 = MB.Generator("art_on", carry_variant=v, lip_carry=False)
    out = dict(variant=v, method_ja="生成器を直接呼ぶ（量子化なし）。差は全頂点の 3 次元の距離（m）。入れた版 − その 1 つだけを切った版",
               ds_lip_carry=diff(g_on, g_28, TAUS), ds_lip_carry_undercut_lead_only=diff(g_on, g_nu, TAUS),
               ds_claws_follow_lip=diff(g_on, g_nc, TAUS), seconds=round(time.time() - t0, 1))
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, "p20_%s.json" % v)
    json.dump(out, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print(json.dumps({k: (dict((kk, vv) for kk, vv in o.items() if kk != "per_tau") if isinstance(o, dict) else o) for k, o in out.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
