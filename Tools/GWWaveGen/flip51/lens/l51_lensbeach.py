# -*- coding: utf-8 -*-
"""Plane swell + submerged shoal lens on the h0 flat + straight 1:s beach. Calibrated linear predictor (l51_pin). py -3.10 -B [computed]"""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M, l51_screen as S, l51_pin as P


def lens_beach(T, h0, xc, Rx, Ry, h_top, x_toe, s=10.0, W=240.0, shape="cos2", periods=30):
    Lx = x_toe + h0 * s + 40.0
    x = np.arange(0, Lx + 1e-9, S.DX); y = np.arange(0, W + 1e-9, S.DX)
    hb = M.bed_beach(x, y, h0=h0, x_toe=x_toe, s=s)
    h = hb - M.mound(x, y, xc, Rx, Ry, h0 - h_top, shape=shape)
    h = np.minimum(h, hb)
    tk, A1, AT = S.run_case(T, x, y, h, target_kind="plane", side=(W - 45.0, 1e9, 1e9 + 1), swash=(6.0, 2.0, 2), periods=periods)
    # straight-bed target row: use the far row (no lens there)
    return tk, A1


if __name__ == "__main__":
    t0 = time.time()
    grid = json.loads(sys.argv[1])
    tagname = sys.argv[2]
    res = []
    a_list = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5]
    for g in grid:
        T, xc, Rx, Ry, ht, xt = g
        tk, A1 = lens_beach(float(T), 19.0, float(xc), float(Rx), float(Ry), float(ht), float(xt))
        for gb in (1.2, 1.4):
            rows = P.sweep_ainc(tk, A1, gb, 0.80, a_list)
            ok = [r for r in rows if r.get("broke") and r["early"] < 0.9]
            best = min(ok, key=lambda r: r["miss"], default=None)
            res.append(dict(case=g, gamma_b=gb, rows=rows, best=best))
            if best:
                print("T%g xc%d Rx%d Ry%d ht%g xt%d gb%.1f | a%.2f xb%.0f hb%.1f Hc%.1f gain%.2f early%.2f | W20 %.1f W50 %.2f W80 %.2f W95 %.2f K %.2f S2 %.2f ring %.2f Lx50 %.2f cin/Hc %.2f miss %.2f" % (
                    T, xc, Rx, Ry, ht, xt, gb, best["a_inc"], best["x_b"], best["h_b"], best["Hc_pred"], best["gain_b"], best["early"], best["W20"], best["W50"], best["W80"],
                    best["W95"], best["K"], best["S2"], best["ring_max"], best["Lx50"], best["c_in_over_Hc"], best["miss"]), flush=True)
            else:
                print("T%g xc%d Rx%d Ry%d ht%g xt%d gb%.1f | no clean break" % (T, xc, Rx, Ry, ht, xt, gb), flush=True)
    json.dump(dict(res=res, wall_s=time.time() - t0), open(os.path.join(S.OUT, "lensbeach_%s.json" % tagname), "w"), indent=1, default=float)
    print("wall", time.time() - t0)
