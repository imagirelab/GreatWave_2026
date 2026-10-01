# -*- coding: utf-8 -*-
"""仕上げ31 修正01：書き出した飛沫の表（pl31_spray_table.json）を読み直して、150（水面へ引き戻されない・水の中に入らない）と 149（放出の 0.2 s 後の距離）を
主役波の本体の列・近い海の全部の行・遠い海の全部の行で確かめる（生成器の中の検査とは別に、表から読み直す 2 回目の読み）。
偶奇（真上への半直線の交差の数）は --parity-hz ごとに全部の点で調べる（既定 60 Hz。生成器は 30 Hz）。t* の保持の位置（τ = 0）が水の中かは、τ = 0 の網で別に数える（inside_tstar_hold）。
使い方：py -3.10 -B Tools/GWWaveGen/pl31/pl31_fx01_check150.py --spray Unity/Build/Polish/31/spray --out Unity/Build/Polish/31/fix01/check150_fx01.json
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl31_spray as SP  # noqa: E402

REPO = SP.REPO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spray", required=True)
    ap.add_argument("--hero-pkg", default=SP.HERO_PKG)
    ap.add_argument("--parity-hz", type=float, default=60.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    tab = json.load(open(os.path.join(a.spray, "pl31_spray_table.json"), encoding="utf-8"))["particles"]
    hero = SP.K.Pkg(a.hero_pkg)
    near = SP.K.Pkg(os.path.join(SP.SEA_DIR, "near")); far = SP.K.Pkg(os.path.join(SP.SEA_DIR, "far"))
    paths = [dict(p_e=t["p_e"], v0=t["v0"], tau_e=t["tau_e"], radius=t["radius_m"]) for t in tab]
    chk = SP.check_paths_full(paths, hero, near, far, min(SP.P["tau_e"][0], min(t["tau_e"] for t in tab)), parity_hz=a.parity_hz)
    kinds = np.array([t["kind"] for t in tab]); rules = np.array([t.get("rule", t.get("mode", "")) for t in tab])
    # t* の保持の位置（τ = 0）が水の中か：主役波の本体の列・近い海・遠い海の網で、真上への半直線の交差の偶奇
    jb, je = 18, 394
    Xh = hero.world(0.0)[:, jb:je + 1]; Xn = near.world(0.0); Xf = far.world(0.0)
    V = np.concatenate([Xh.reshape(-1, 3), Xn.reshape(-1, 3), Xf.reshape(-1, 3)])
    Cb = je - jb + 1
    Tall = np.concatenate([SP.K.grid_tris(hero.R, Cb), SP.K.grid_tris(near.R, near.C) + hero.R * Cb,
                           SP.K.grid_tris(far.R, far.C) + hero.R * Cb + near.R * near.C])
    pe = np.array([q["p_e"] for q in paths]); v0 = np.array([q["v0"] for q in paths]); te = np.array([q["tau_e"] for q in paths])
    P0 = SP.D.traj(pe, v0, te, np.zeros(len(paths)))
    o_ = np.lexsort((np.floor(P0[:, 2] / 4.0), np.floor(P0[:, 0] / 4.0)))
    par0 = np.zeros(len(paths), int)
    par0[o_] = SP.D.crossings_up(P0[o_], V, Tall) % 2
    hold_in = np.nonzero(par0 == 1)[0]
    bad_in = np.nonzero(chk["inside"] > 0)[0]
    res = dict(schema="GreatWave.Polish31.check150/1", spray=a.spray.replace(REPO + "/", ""), particles=len(tab), parity_hz=a.parity_hz,
               rule_ja="主役波の本体の列 18〜394・近い海 64 行・遠い海 19 行の全部。240 Hz の各コマで最も近い頂点までの距離（接触）、偶奇は頂点から 1 m 以内と、"
                       "parity_hz ごとと τ = 0 には全部の点。離れない（放出から 0.3 s のうちに半径 + 0.10 m 離れない）も数える",
               inside=int((chk["inside"] > 0).sum()), inside_tstar_hold=int(len(hold_in)),
               inside_tstar_hold_examples=[dict(index=int(i), kind=str(kinds[i]), rule=str(rules[i]), p=[float(x) for x in P0[i]]) for i in hold_in[:20]],
               contact=int((chk["contact"] > 0).sum()), never_left=int(chk["never_left"].sum()),
               inside_by_kind={k: int(((chk["inside"] > 0) & (kinds == k)).sum()) for k in ("parent", "child")},
               inside_examples=[dict(index=int(i), kind=str(kinds[i]), rule=str(rules[i]), **(chk["inside_where"][i] or {})) for i in bad_in[:20]],
               gap_0p2s_m={k: dict(min=float(np.nanmin(chk["dist_gap"][kinds == k])), median=float(np.nanmedian(chk["dist_gap"][kinds == k])),
                                   under_0p1=int((chk["dist_gap"][kinds == k] < 0.1).sum())) for k in ("parent", "child") if (kinds == k).any()},
               seconds=time.time() - t0)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "inside_examples"}, ensure_ascii=False))
    print(res["inside_examples"][:10])


if __name__ == "__main__":
    main()
