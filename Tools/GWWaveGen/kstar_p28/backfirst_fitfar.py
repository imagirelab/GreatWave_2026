# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）：奥の端の「輪郭を作る縁」だけの当てはめ（py -3.10）。

手順：大きな形を先に決める（奥の頂の線を c に沿ってならす far_crest_smooth、背の掃引）→ その上で奥の行の相似の動き
far.s（唇先のまわりの大きさ）・far.da（T の向きのずれ）の鍵だけを、原画の輪郭 72（と 132）の大きな輪郭（σ 12 px）の線に
候補の被覆の境が乗るよう、最小二乗で解く。
  残差  1 符号つき距離（候補の被覆の距離場を真値の線の点で読む。px / 2）… 72・132 の大きな輪郭の線の点
        2 原画の空（管の口と唇の上）の点が候補の外にあること（距離 < 1.5 px の分）
        3 奥の頂の線（列 90 の a と高さ、c +3〜+15 を 0.5 m で取り直す）の 2 階差（なめらかさ。重み --w-crest）
        4 鍵の 2 階差
  ヤコビアンは差分（並列）。ドームの測り（評審の R4 / R6）は最後に測る（費用には頂の線のなめらかさとして入れる）。
usage: py -3.10 backfirst_fitfar.py OUT_DIR design.json [--iters 12] [--workers 10] [--w-crest 1.0]
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
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "kstar_h"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "rubric"))
import numpy as np  # noqa: E402

W_CREST = [1.0]
W_KEYS = [float(os.environ.get("BF_W_KEYS", "0.3"))]
_T = {}


def targets():
    if "t" in _T:
        return _T["t"]
    import cv2
    import backfirst_eval as BE
    g, V1, tgt, fr, seacov = BE._gate_obj()
    pts = []; lab = []
    for k, step in (("72", 6.0), ("132", 10.0)):
        P = g.lf[k]
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        t = np.arange(0, s[-1], step)
        pts.append(np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], -1)); lab += [k] * len(t)
    T = np.vstack(pts)
    # painted sky near 72 / 132 (tube mouth and above the lip), sampled every 6 px
    sky = g.truth.cov["sky_envelope"] > 0.5
    from scipy.spatial import cKDTree
    kd = cKDTree(T)
    gy, gx = np.mgrid[300:760:6, 760:1130:6]
    G = np.stack([gx.ravel(), gy.ravel()], -1).astype(float)
    d, _ = kd.query(G)
    ok = sky[G[:, 1].astype(int), G[:, 0].astype(int)] & (d > 5.0) & (d < 60.0)
    S = G[ok]
    _T["t"] = (T, np.array(lab), S)
    return _T["t"]


def sdf(c, A, Y):
    import cv2
    import backfirst_eval as BE
    g, V1, tgt, fr, seacov = BE._gate_obj()
    X = fr.world(c, A, Y)
    cov = (V1.rasterize(fr.cam, X, V1.triangles(A.shape[1], A.shape[0])) > 0.5).astype(np.uint8)
    din = cv2.distanceTransform(cov, cv2.DIST_L2, 5)
    dout = cv2.distanceTransform(1 - cov, cv2.DIST_L2, 5)
    return dout - din


def bilin(img, P):
    x = np.clip(P[:, 0], 0, img.shape[1] - 1.001); y = np.clip(P[:, 1], 0, img.shape[0] - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


def crest_line_d2(c, A, Y, c0=3.0, c1=14.6):
    cq = np.arange(c0, c1 + 1e-6, 0.5)
    a = np.interp(cq, c, A[:, 90]); h = np.interp(cq, c, Y[:, 90])
    foot = np.interp(cq, c, A[:, 18])
    return np.r_[np.diff(a, 2), np.diff(h, 2), 0.5 * np.diff(foot, 2)]


VARS_FAR = [("far", "s", [1, 2, 3, 4, 5, 6]), ("far", "da", [1, 2, 3, 4, 5, 6, 7])]
VARS_REACH = [("reach_adjust", "da", list(range(int(os.environ.get("BF_NK", "6"))))), ("reach_adjust", "dy", list(range(int(os.environ.get("BF_NK", "6")))))]
VARS = VARS_REACH if os.environ.get("BF_FIT_VARS", "reach") == "reach" else VARS_FAR
SCALE = {"s": 0.04, "da": 0.4, "dy": 0.4}


def pack(d):
    return np.array([d[g][k][i] for g, k, ii in VARS for i in ii], float)


def unpack(d0, x):
    d = json.loads(json.dumps(d0)); n = 0
    for g, k, ii in VARS:
        for i in ii:
            d[g][k][i] = float(x[n]); n += 1
    return d


def residuals(d):
    import backfirst_model as M
    c, A, Y = M.build(d)
    T, lab, S = targets()
    F = sdf(c, A, Y)
    r1 = bilin(F, T) / 2.0
    r2 = np.maximum(1.5 - bilin(F, S), 0.0) / 1.5
    r3 = W_CREST[0] * crest_line_d2(c, A, Y) / 0.05
    r4 = []
    for g, k, ii in VARS:
        v = np.array(d[g][k], float)
        r4 += list(W_KEYS[0] * np.diff(v, 2) / SCALE[k])
    import kh_designR4 as D
    sx = D.section_selfx(A, Y)
    mins, _ = D.lip_clearance(A, Y)
    r5 = [3.0 * len(sx), 20.0 * max(0.03 - float(mins[(c > 3) & (c < 14.5)].min()), 0.0)]
    if os.environ.get("BF_TOP_PEN", "0") == "1":
        # the far rows' tops must stay arcs: rows whose highest point is on the lip (col > 150), and rows with a +-2 m chord < 100 deg
        import rubric_check as RC_
        H = Y.max(1)
        rr = np.nonzero((c > 3) & (H >= 3.0))[0]
        lip_top = sum(1 for r in rr if int(np.argmax(Y[r, :200])) > 150)
        sharp = sum(max(100.0 - RC_.corner_q17(A[r], Y[r], 200)["chord2_deg"], 0.0) / 10.0 for r in rr)
        r5 += [3.0 * lip_top, float(sharp)]
    return np.r_[r1, r2, r3, np.array(r4), np.array(r5)]


def _work(args):
    d, = args
    try:
        return residuals(d)
    except Exception:
        return None


def main():
    from multiprocessing import Pool
    from scipy.optimize import least_squares
    import backfirst_model as M
    import backfirst_eval as BE
    out = sys.argv[1]; d0 = json.load(open(sys.argv[2], encoding="utf-8"))
    args = sys.argv[3:]
    def opt(name, default):
        return type(default)(args[args.index(name) + 1]) if name in args else default
    iters = opt("--iters", 12); workers = opt("--workers", 10); W_CREST[0] = opt("--w-crest", 1.0)
    os.makedirs(out, exist_ok=True)
    x0 = pack(d0); xs = np.array([SCALE[k] for g, k, ii in VARS for i in ii])
    pool = Pool(workers, initializer=_init_w, initargs=(W_CREST[0],))
    t0 = time.time()
    best = {"f": np.inf, "x": x0}

    def fun_many(X):
        R = pool.map(_work, [(unpack(d0, x),) for x in X])
        for x, r in zip(X, R):
            if r is not None:
                f = float(np.sum(r ** 2))
                if f < best["f"]:
                    best.update(f=f, x=np.array(x))
                    print("%6.1fs f=%.2f" % (time.time() - t0, f), flush=True)
        return R

    def fun(x):
        r = fun_many([x])[0]
        return r if r is not None else np.full(len(fun.n), 30.0)

    def jac(x):
        h = xs * 0.5
        X = [x + h[i] * np.eye(len(x))[i] for i in range(len(x))]
        R = fun_many(X); f0 = fun(x)
        J = np.zeros((len(f0), len(x)))
        for i, Ri in enumerate(R):
            if Ri is not None:
                J[:, i] = (Ri - f0) / h[i]
        return J

    r0 = fun(x0); fun.n = r0
    try:
        least_squares(fun, x0, jac=jac, x_scale=xs, loss="soft_l1", f_scale=1.0, max_nfev=iters, method="trf")
    finally:
        pool.close()
    d = unpack(d0, best["x"])
    json.dump(d, open(os.path.join(out, "fitfar_design.json"), "w", encoding="utf-8"), indent=1)
    c, A, Y = M.build(d)
    np.savez_compressed(os.path.join(out, "fitfar_rows.npz"), A=A, Y=Y, c=c)
    r = BE.quick(c, A, Y)
    json.dump(r, open(os.path.join(out, "fitfar_quick.json"), "w", encoding="utf-8"), indent=1, default=float)
    print("done %.0fs f=%.2f" % (time.time() - t0, best["f"]))
    print(BE.brief(r))


def _init_w(wc):
    W_CREST[0] = wc


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
