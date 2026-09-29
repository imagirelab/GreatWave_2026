# -*- coding: utf-8 -*-
"""K*′ 精修 R4：主断面のまわり（c −3〜+3）の唇の頭の鍵（lip_shift / lip_drop、1 m おき）の波打ちを、原画の関門を守る範囲でなめらかにする
（py -3.10、scipy の Powell）。最小にするもの：鍵の c 方向の 2 階差の 2 乗和（唇の縁の波打ち）＋ 関門の超えの罰
（78/130/131 の最大、132 の大きな輪郭の最大、72 の大きな輪郭 R4（σ 24 px）の p95 のどれかが limit を超えた分の 2 乗 × 大きな重み）。
usage: py -3.10 kh_R4_lip132.py in.json out.json [--limit 3.92] [--keys -3,-2,-1,0,1,2,3] [--maxev 400]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
import sys
import json
import time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
from scipy.optimize import minimize  # noqa: E402
import kh_designR4 as D  # noqa: E402
import kh_gate_lfR4 as KG  # noqa: E402
import kh_R1_quick as Q1  # noqa: E402


def main():
    a = sys.argv[1:]
    din, dout = a[0], a[1]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d  # noqa: E731
    limit, maxev = opt("--limit", 3.92), opt("--maxev", 400)
    keys = [float(x) for x in opt("--keys", "-3,-2,-1,0,1,2,3").split(",")]
    d = D.Design.load(din)
    g = KG.LFGate()
    idx = {}
    for n in ("lip_shift", "lip_drop"):
        cs = d.keys[n][0]
        idx[n] = [cs.index(k) for k in keys]
    x0 = np.array([d.keys[n][1][i] for n in ("lip_shift", "lip_drop") for i in idx[n]])
    nk = len(keys)
    log = []
    t0 = time.time()

    def setx(x):
        for q, n in enumerate(("lip_shift", "lip_drop")):
            vs = list(d.keys[n][1])
            for m, i in enumerate(idx[n]):
                vs[i] = float(x[q * nk + m])
            d.keys[n] = (d.keys[n][0], vs)

    def rough():
        r = 0.0
        for n in ("lip_shift", "lip_drop"):
            cs, vs = d.keys[n]
            v = np.array(vs); c_ = np.array(cs)
            m = (c_ >= keys[0] - 2) & (c_ <= keys[-1] + 2)
            vv = v[m]
            r += float(np.sum((vv[:-2] - 2 * vv[1:-1] + vv[2:]) ** 2))
        return r

    def gates():
        c, A, Y, P = D.build_pre_sculpt(d)
        og = Q1.official_gate(c, A, Y)
        lf, _ = g.measure_rows(c, A, Y)
        return max(og["78"]["max"], og["130"]["max"], og["131"]["max"], lf["132"]["max_px"], lf["72"]["p95_px"]), og, lf

    best = [None]

    def f(x):
        setx(x)
        gm, og, lf = gates()
        rg = rough()
        J = rg + 200.0 * max(0.0, gm - limit) ** 2
        log.append({"t": round(time.time() - t0), "J": round(J, 4), "rough": round(rg, 4), "gmax": round(gm, 3)})
        if gm <= limit and (best[0] is None or rg < best[0][0]):
            best[0] = (rg, x.copy(), gm, {k: og[k]["max"] for k in ("78", "130", "131")}, round(lf["132"]["max_px"], 3), round(lf["72"]["p95_px"], 3))
        if len(log) % 20 == 1:
            print(json.dumps(log[-1]), flush=True)
        return J

    setx(x0)
    print("start rough %.4f gates %.3f" % (rough(), gates()[0]), flush=True)
    minimize(f, x0, method="Powell", options={"maxfev": maxev, "xtol": 0.005, "ftol": 1e-4})
    if best[0] is None:
        print("no feasible point"); return
    rg, xb, gm, og, g132, g72 = best[0]
    setx(xb)
    j = d.to_json()
    j["lip132_log"] = {"keys": keys, "limit": limit, "best": {"rough": rg, "gmax": gm, "78/130/131": og, "132lf": g132, "72lf24_p95": g72},
                       "evals": len(log), "seconds": round(time.time() - t0)}
    json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("FINAL", json.dumps(j["lip132_log"]), flush=True)


if __name__ == "__main__":
    main()
