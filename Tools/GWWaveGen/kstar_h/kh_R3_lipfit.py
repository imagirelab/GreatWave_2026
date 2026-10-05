# -*- coding: utf-8 -*-
"""K*′ 精修 R3：唇の頭の移動（lip_shift / lip_drop）を、鍵の間隔を広げたまま原画の輪郭 72（と 132）へ合わせる（py -3.10）。
kh_R3_sil.py（線形化の繰り返し）が止まってしまうので、公式の測り方の点ごとの誤差（kh_R1_snap.Snap.fixed：真値の点 → 描画の縁、
描画の縁 → 真値の点、132・72 は大きな輪郭の線）を残差にして、scipy の least_squares（差分のヤコビアン、上下限つき）で解く。
鍵の 2 階差を罰する行を足す（唇の縁を波打たせない）。edgeL・edge_* などほかの鍵は動かさない。
usage: py -3.10 kh_R3_lipfit.py in.json out.json [--step 3.0] [--lam 2.0] [--iters 30] [--w132 1.0] [--bound 1.2]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys
import json
import time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"),
          os.path.join(REPO, "Tools", "GWWaveGen")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402
import kh_designR3 as D  # noqa: E402
import kh_R1_snap as SN  # noqa: E402


def keyset(step):
    return [-12.0] + [float(x) for x in np.arange(-12.0 + step, 15.0 - 0.5 * step, step)] + [15.0]


def main():
    a = sys.argv[1:]
    din, dout = a[0], a[1]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d  # noqa: E731
    step, lam, iters, w132, bound = opt("--step", 3.0), opt("--lam", 2.0), opt("--iters", 30), opt("--w132", 1.0), opt("--bound", 1.2)
    names = ["lip_shift", "lip_drop"]
    d = D.Design.load(din)
    c = D.c_rows()
    kc = keyset(step)
    n = len(kc)
    B = np.stack([D.bspline_ramp(kc, np.eye(n)[i], c) for i in range(n)], 1)
    th0 = []
    for nm in names:
        cur = D.bspline_ramp(d.keys[nm][0], d.keys[nm][1], c) if len(d.keys[nm][0]) > 1 else np.full(len(c), d.keys[nm][1][0])
        v, *_ = np.linalg.lstsq(B, cur, rcond=None)
        th0.append(np.clip(v[1:-1], -bound, bound))
    x0 = np.concatenate(th0)
    S = SN.Snap()
    t0 = time.time()
    log = []

    def set_x(x):
        for i, nm in enumerate(names):
            v = np.r_[0.0, x[i * (n - 2):(i + 1) * (n - 2)], 0.0]
            d.keys[nm] = (list(kc), [float(t) for t in v])

    def resid(x):
        set_x(x)
        cc, A, Y, P = D.build(d, c)
        out, met = S.fixed(cc, A, Y)
        r = [np.r_[out["72"][0], out["72"][1]], w132 * np.r_[out["132"][0], out["132"][1]],
             0.5 * np.r_[out["131"][0], out["131"][1]]]
        reg = []
        for i in range(len(names)):
            v = np.r_[0.0, x[i * (n - 2):(i + 1) * (n - 2)], 0.0]
            reg.append(lam * 10.0 * (v[:-2] - 2 * v[1:-1] + v[2:]))
        rr = np.concatenate(r + reg)
        sc = max(met["132"]["max"], met["72"]["p95"], met["78"]["max"], met["130"]["max"], met["131"]["max"])
        log.append({"t": round(time.time() - t0), "score": round(sc, 3), "132": round(met["132"]["max"], 2), "72p95": round(met["72"]["p95"], 2),
                    "131": round(met["131"]["max"], 2), "cost": round(float(rr @ rr), 1)})
        if len(log) % 10 == 1:
            print(json.dumps(log[-1]), flush=True)
        resid.best = min(getattr(resid, "best", (1e9, None)), (sc, x.copy()), key=lambda t: t[0])
        return rr

    print("keys", kc, "params", len(x0), flush=True)
    least_squares(resid, x0, bounds=(-bound, bound), diff_step=0.03, max_nfev=iters * (len(x0) + 1), x_scale=0.3, verbose=0)
    sc, xb = resid.best
    set_x(xb)
    j = d.to_json()
    j["lipfit_log"] = {"keys": kc, "lam": lam, "best_score": sc, "evals": len(log), "seconds": round(time.time() - t0), "trace": log[::10] + log[-1:]}
    json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("FINAL best score", sc, "evals", len(log), flush=True)


if __name__ == "__main__":
    main()
