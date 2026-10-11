# -*- coding: utf-8 -*-
"""R4b 確かめ：A3' の入れ方の感度（A2' だけを入れる形、計画 §5 A3' の文のまま）。b_spec.json の A2' の値だけを使う。
py -3.10 b_a3var.py → b_a3var.json"""
import json, os
import numpy as np
import b_common as B
import b_spec as BS


def main():
    P = B.plan(); C = B.components(P)
    gz = P["gauges"]; x_e = gz["band_exit"]["x_rel"]; x15 = gz["kc(x-xb)=-15"]["x_rel"]; dx2 = x15 - x_e
    d = json.load(open(os.path.join(B.OUT, "b_spec.json"), encoding="utf-8"))
    out = {}
    for rid in ("R1b", "R2", "R3", "R4d"):
        a = d[rid]["A2p"]
        fr = np.array(a["f"]); e = np.array(a["e"]); g = np.array(a["g"])
        e_i = np.interp(C["f"], fr, e); g_i = np.interp(C["f"], fr, g)
        one = np.ones(len(C["f"])) * (1 + 0j)
        o = {}
        # (1) A2' の速さだけ（振幅は変えない）
        o["speed_only"] = BS.a3p(C, one, e_i, np.ones(len(C["f"])), x_e, dx2, 501, 451, +1)
        # (2) A2' の速さと振幅の変化（成分ごとの g を一度だけ掛ける＝定数）
        o["A2p_const_amp"] = BS.a3p(C, g_i.astype(complex), e_i, np.ones(len(C["f"])), x_e, dx2, 501, 451, +1)
        # (3) A2' の速さと振幅の変化（距離で伸ばす）
        o["A2p_dist_amp"] = BS.a3p(C, one, e_i, g_i, x_e, dx2, 501, 451, +1)
        # (4) (1) の 10/9 の符号
        o["speed_only_old_sign"] = BS.a3p(C, one, e_i, np.ones(len(C["f"])), x_e, dx2, 501, 451, -1)
        out[rid] = o
        for k, r in o.items():
            print(rid, k, round(r["dx_Lc"], 4), round(r["dt_Tc"], 4), round(r["crest_ratio"], 4), round(r["H_ratio_075Lc"], 4), round(r["H_ratio_first_trough"], 4))
    B.dump("b_a3var.json", out)


if __name__ == "__main__":
    main()
