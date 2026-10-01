# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）の最適化（py -3.10）。背の大きな形（ρ の鍵）と奥の端の相似の族（s・a0・ρ の鍵）だけを動かし、
原画には輪郭を作る縁だけで合わせる。費用は関門だけでなく、ドーム（評審の R4 / R6）、3 m の撓み、横の厚み F04、量感、
断面の自己交差、鍵の 2 階差（なめらかさ）を含む。

  費用の残差（scipy.optimize.least_squares、soft_l1）
    関門   78/130/131 最大、132 大きな輪郭（σ 12）最大、72 大きな輪郭（σ 12）p95 の、上限 3.6 / 3.6 / 3.4 px を超えた分（重み 3）、
           空へのはみ出しの画素（/300）
    ドーム R6 p99 / 0.30、R4 p99 / 0.20（重み --w-dome）
    撓み   3 m の撓み p99 / 0.6
    F04    側面の影の幅 0.5H0 が 18.5 m を超えた分 / 2（重み --w-f04）
    量感   面積 / H² の参照比が 0.95 を下回った分 × 5
    網     断面の自己交差の行の数、唇の上下の間隔 < 0.05 m の分
    なめらかさ 各鍵の列の 2 階差（重み --w-smooth）
  ヤコビアンは差分（--workers の並列）。
usage: py -3.10 backfirst_opt.py OUT_DIR [--init design.json] [--iters 8] [--workers 8] [--w-dome 1] [--w-f04 1] [--w-smooth 1]
"""
import os
import sys
import json
import time
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402

VARS = [("far", "s", [0, 1, 2, 3, 4, 5, 6]), ("far", "da", [0, 1, 2, 3, 4, 5, 6, 7]), ("back", "rho", [0, 1, 2, 3, 4, 5, 6, 7])]
SCALE = {"s": 0.05, "da": 0.5, "rho": 0.05}
W = {"dome": 1.0, "f04": 1.0, "smooth": 1.0}


def pack(d):
    return np.array([d[g][k][i] for g, k, ii in VARS for i in ii], float)


def unpack(d0, x):
    d = json.loads(json.dumps(d0))
    n = 0
    for g, k, ii in VARS:
        for i in ii:
            d[g][k][i] = float(x[n]); n += 1
    return d


def residuals_from_metrics(r, d):
    g = r["gate"]
    res = []
    def hinge(v, lim):
        return max(v - lim, 0.0)
    res += [3 * hinge(g["78"]["max"], 3.6), 3 * hinge(g["130"]["max"], 3.9), 3 * hinge(g["131"]["max"], 3.6),
            3 * hinge(g["132lf"]["max"], 3.6), 3 * hinge(g["72lf"]["p95"], 3.4), 1.0 * hinge(g["72lf"]["max"], 7.0),
            max(g["spill_px"] - 3700.0, 0.0) / 300.0]
    res += [W["dome"] * r["dome"]["R6"]["p99"] / 0.30, W["dome"] * r["dome"]["R4"]["p99"] / 0.20]
    res += [r["sag"]["p99"] / 0.6]
    res += [W["f04"] * hinge(r["f04"]["side_0p5"], 18.5) / 2.0]
    res += [5 * hinge(0.95, r["full"]["ratio_vs_ref"])]
    res += [2.0 * r["selfx"]["section_selfx_rows"], 20 * hinge(0.05, r["selfx"]["lip_clear_min"])]
    # smoothness of the key sequences (second differences), scaled
    for g_, k, ii in VARS:
        v = np.array(d[g_][k], float)
        if len(v) >= 3:
            dd = np.diff(v, 2) / SCALE[k]
            res += list(W["smooth"] * 0.15 * dd)
    return np.array(res, float)


def evaluate(d):
    import backfirst_model as M
    import backfirst_eval as BE
    c, A, Y = M.build(d)
    if not np.isfinite(A).all() or not np.isfinite(Y).all():
        return None
    r = BE.quick(c, A, Y)
    return r


def _work(args):
    d, = args
    try:
        r = evaluate(d)
        if r is None:
            return None
        return residuals_from_metrics(r, d).tolist(), r
    except Exception as e:  # a broken design (e.g. degenerate) -> big residual
        return None


def main():
    from multiprocessing import Pool
    from scipy.optimize import least_squares
    import backfirst_model as M
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    args = sys.argv[2:]
    def opt(name, default):
        return type(default)(args[args.index(name) + 1]) if name in args else default
    iters = opt("--iters", 8); workers = opt("--workers", 8)
    W["dome"] = opt("--w-dome", 1.0); W["f04"] = opt("--w-f04", 1.0); W["smooth"] = opt("--w-smooth", 1.0)
    d0 = json.load(open(args[args.index("--init") + 1], encoding="utf-8")) if "--init" in args else M.init_design()
    x0 = pack(d0)
    xs = np.array([SCALE[k] for g, k, ii in VARS for i in ii])
    log = open(os.path.join(out, "opt_log.txt"), "a", encoding="utf-8")
    best = {"f": np.inf, "x": x0.copy(), "r": None}
    pool = Pool(workers)
    nres = [None]
    t0 = time.time()

    def fun_many(X):
        outs = pool.map(_work, [(unpack(d0, x),) for x in X])
        R = []
        for x, o in zip(X, outs):
            if o is None:
                R.append(None); continue
            res, met = o
            f = float(np.sum(np.square(res)))
            if f < best["f"]:
                best.update(f=f, x=np.array(x).copy(), r=met)
                import backfirst_eval as BE
                msg = "%7.1fs best f=%.3f %s" % (time.time() - t0, f, BE.brief(met))
                print(msg, flush=True); log.write(msg + "\n"); log.flush()
                json.dump(unpack(d0, x), open(os.path.join(out, "best_design.json"), "w", encoding="utf-8"), indent=1)
            R.append(np.array(res))
            nres[0] = len(res)
        return R

    def fun(x):
        R = fun_many([x])[0]
        if R is None:
            return np.full(nres[0] or 40, 50.0)
        return R

    def jac(x):
        h = xs * 0.25
        X = [x + h[i] * np.eye(len(x))[i] for i in range(len(x))]
        R = fun_many(X)
        f0 = fun(x)
        J = np.zeros((len(f0), len(x)))
        for i, Ri in enumerate(R):
            if Ri is None or len(Ri) != len(f0):
                continue
            J[:, i] = (Ri - f0) / h[i]
        return J

    fun(x0)
    try:
        least_squares(fun, x0, jac=jac, x_scale=xs, loss="soft_l1", f_scale=1.0, max_nfev=iters, method="trf")
    finally:
        pool.close()
    d = unpack(d0, best["x"])
    json.dump(d, open(os.path.join(out, "best_design.json"), "w", encoding="utf-8"), indent=1)
    c, A, Y = M.build(d)
    np.savez_compressed(os.path.join(out, "best_rows.npz"), A=A, Y=Y, c=c)
    json.dump(best["r"], open(os.path.join(out, "best_metrics.json"), "w", encoding="utf-8"), indent=1, default=float)
    print("done %.0fs f=%.3f" % (time.time() - t0, best["f"]), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
