# -*- coding: utf-8 -*-
"""K*′ 精修 R3：原画の輪郭を「輪郭を作る縁」だけで合わせる段（py -3.10）。kh_R2_sil.py の R3 版（kh_designR3 を使う）。
R3 で変えた所：唇の頭の移動 lip_shift / lip_drop の鍵を 3 m おき（R2 は 1 m おきで唇の縁が波打った、評審の must-fix 3）。唇の上面の細い帯
edgeL の鍵を 2 m おき（R2 は 1 m）。鍵の 2 階差の罰を強めた（--lam、既定 3.0）。以下は R2 の説明。

K*′ 精修 R2：原画の輪郭を「輪郭を作る縁」だけで合わせる段（py -3.10）。R1 の kh_R1_snap.py の考え方を広げたもの。

解くもの（どれも CTRL の ramp の鍵。本体の大きな形は動かさない）
  lip_shift       唇の頭（列 186〜214、列 140 / 268 までなめらかに 0）を唇先の法線の向きへまとめて動かす [m]（輪郭 72）
  edgeL_1..12     唇の上面の細い帯（列 97〜185、σ 5 列）の、原画カメラの視線がかすめる所だけ [m]（輪郭 132）
  edge_1..9       R1 の太い帯（視線がかすめる所だけ）[m]（選べば）
方法（線形化をくり返す。差分のヤコビアンは使わない）
  1 評価器と同じ測り方（真値の点 = 包絡版の空の境界、132・72 は大きな輪郭の線、kh_R1_snap.Snap）で、項目ごとに符号つきの誤差 e（+ = 候補が
    小さい、外へ出す）と描画の点 q を出す。
  2 q に一番近い網の頂点 (r, j)（原画視点で前にある波の頂点）を責任の頂点とし、各モードの単位の量でその頂点が動く像の動きの、描画の境界の
    外向きの成分 g（px / ramp の単位）を出す。
  3 e ≈ Σ_m g_m Σ_k B_k(c_r) Δθ_mk（B = ramp の B-spline の基底）を、大きな誤差ほど重く、鍵の 2 階差と大きさを罰して最小二乗で解く。
  4 公式の数（78/130/131 最大、132 大きな輪郭の最大、72 大きな輪郭の p95）で直線探索し、一番よかった鍵を残す。上限 --bound を守る。
usage: py -3.10 kh_R3_sil.py in.json out.json [--iters 12] [--modes lip_shift,edgeL] [--bound-shift 0.9] [--bound-edge 0.35]
"""
import os
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
import cv2  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
import kh_designR3 as D  # noqa: E402
import kh_R1_snap as SN  # noqa: E402

T_ = D.FRAME_T
UP = np.array([0.0, 1.0, 0.0])

# key sets (c) of each solved ramp; the first and last keys are held at 0
KEYS = {
    "lip_shift": [-12.0, -9.0, -6.0, -3.0, 0.0, 3.0, 6.0, 9.0, 12.0, 15.0],        # R3: 3 m apart (R2: 1 m); --ls-step changes it
    "edgeL": [-7.0, -5.0, -3.0, -1.0, 1.0, 3.0],                                     # R3: 2 m apart (R2: 1 m); --el-step changes it
    "lip_under": [-11.0] + [float(x) for x in np.arange(-9.0, 14.01, 1.0)] + [15.5],   # R3: the underside thickness (1 m; the tip line stays)
    "edge_lo": [-2.0] + [float(x) for x in np.arange(0.0, 14.01, 1.5)] + [16.0],       # edge_6..9 (lip underside / tube bands)
    "edge_hi": [-26.0] + [float(x) for x in np.arange(-22.0, 4.01, 2.0)] + [6.0],     # edge_1..5
}


def keyset(name):
    if name in ("lip_shift", "lip_drop"):
        return KEYS["lip_shift"]
    if name == "lip_under":
        return KEYS["lip_under"]
    if name.startswith("edgeL_"):
        return KEYS["edgeL"]
    k = int(name.split("_")[1]) if name.startswith("edge_") and name != "edge_tip" else 0
    return KEYS["edge_lo"] if k >= 6 else KEYS["edge_hi"]


def score(met):
    return max(met["78"]["max"], met["130"]["max"], met["131"]["max"], met["132"]["max"], met["72"]["p95"]) + 0.05 * met["72"]["max"]


def ramp_basis(kc, c):
    n = len(kc)
    return np.stack([D.bspline_ramp(kc, np.eye(n)[i], c) for i in range(n)], 1)


def solve(design, names, iters=12, bound_shift=0.9, bound_edge=0.35, lam_d2=1.5, lam_0=0.08, log=print, items_w=None):
    S = SN.Snap()
    d = D.Design.from_json(design.to_json())
    c = D.c_rows()
    # current values resampled onto the solver keys
    B = {n: ramp_basis(keyset(n), c) for n in names}
    th = {}
    for n in names:
        kc = keyset(n)
        cur = D.bspline_ramp(d.keys[n][0], d.keys[n][1], c) if len(d.keys[n][0]) > 1 else np.full(len(c), d.keys[n][1][0])
        v = np.zeros(len(kc))
        if np.any(np.abs(cur) > 1e-9):
            v, *_ = np.linalg.lstsq(B[n], cur, rcond=None)
        v[0] = v[-1] = 0.0
        th[n] = v

    def set_design(tt):
        for n in names:
            d.keys[n] = (list(keyset(n)), [float(x) for x in tt[n]])

    def shape(tt):
        set_design(tt)
        c_, A, Y, P = D.build(d, c)
        return A, Y

    def bnd(n):
        return bound_shift if n in ("lip_shift", "lip_drop") else (0.8 if n == "lip_under" else bound_edge)

    best = None
    hist = []
    tr = 0.25
    for it in range(iters + 1):
        set_design(th)
        c_, Ap, Yp, P = D.build_pre_edges(d, c)
        M = D.edge_modes(c, Ap, Yp)
        A, Y = D.apply_edges(c, Ap, Yp, P, modes=M)
        met, recs, X, skys = S.errors(c, A, Y)
        sc = score(met)
        hist.append({"it": it, "score": round(sc, 3), "met": {k: [round(m["max"], 2), round(m["p95"], 2)] for k, m in met.items()},
                     "max_abs": {n: round(float(np.abs(th[n]).max()), 3) for n in names if n in ("lip_shift", "lip_drop")}})
        log(json.dumps(hist[-1]))
        if best is None or sc < best[0]:
            best = (sc, {n: th[n].copy() for n in names}, met)
        if it == iters:
            break
        # --- linearise
        cam = S.fr.cam
        Pj = cam.project(X.reshape(-1, 3))
        body = (Y.reshape(-1) > 0.3) & (Pj[:, 2] > 0.5)
        idx = np.nonzero(body)[0]
        kd = cKDTree(Pj[idx, :2])
        qs = np.array([q for _, q, _ in recs]); es = np.array([e for _, _, e in recs]); ks = [k for k, _, _ in recs]
        dd, ii = kd.query(qs)
        vid = idx[ii]
        r_ = vid // D.NU; j_ = vid % D.NU
        Xw = X.reshape(-1, 3)[vid]
        gx = cv2.Sobel(skys, cv2.CV_64F, 1, 0, ksize=3); gy = cv2.Sobel(skys, cv2.CV_64F, 0, 1, ksize=3)
        gv = np.stack([S.samp(gx, qs), S.samp(gy, qs)], -1)
        gv /= np.maximum(np.linalg.norm(gv, axis=1, keepdims=True), 1e-9)
        P0_ = Pj[vid, :2]

        def gain(disp_sec):          # disp_sec: (n, 2) section-plane displacement per unit -> px outward
            dw = disp_sec[:, 0:1] * T_[None, :] + disp_sec[:, 1:2] * UP[None, :]
            P1 = cam.project(Xw + 0.05 * dw)[:, :2]
            return np.sum((P1 - P0_) / 0.05 * gv, 1)
        nsec = np.stack([np.stack(D.row_normals(A[r], Y[r]).T, 0) for r in range(len(c))], 0)     # (nv, 2, nu)
        ns = np.stack([nsec[r_, 0, j_], nsec[r_, 1, j_]], -1)
        ntip = D.tip_normals(Ap, Yp)
        wls = D.lipshift_weight()
        cols = []
        for n in names:
            if n == "lip_shift":
                g = gain(wls[j_][:, None] * ntip[r_] * D.body_mask(Y[r_, j_])[:, None])
            elif n == "lip_drop":
                g = gain(wls[j_][:, None] * np.array([[0.0, -1.0]]) * D.body_mask(Y[r_, j_])[:, None])
            elif n == "lip_under":
                g = gain(D.lipunder_weight()[j_][:, None] * ns * D.body_mask(Y[r_, j_])[:, None])
            else:
                b = D.EDGE_NAMES.index(n)
                g = gain(M[b][r_, j_][:, None] * ns)
            cols.append(g[:, None] * B[n][r_])
        J = np.concatenate(cols, 1)
        ok = (dd < 6.0) & (np.abs(es) > 0.25)
        es_c = np.clip(es, -15.0, 15.0)
        iw = items_w or {}
        wi = np.array([iw.get(k, 1.0) for k in ks]) * (1.0 + (np.abs(es_c) / 3.0) ** 2) * ok
        # a row of J that no mode can move carries no information
        sw = np.sqrt(wi)
        Aeq = J * sw[:, None]; beq = es_c * sw
        R = []; rb = []
        off = 0
        th_all = np.concatenate([th[n] for n in names])
        for n in names:
            nk = len(keyset(n)); sc_ = 1.0 if n not in ("lip_shift", "lip_drop") else 0.6
            for k in range(1, nk - 1):
                row = np.zeros(len(th_all)); row[off + k - 1] = 1; row[off + k] = -2; row[off + k + 1] = 1
                R.append(row * lam_d2 * 20.0 * sc_); rb.append(-lam_d2 * 20.0 * sc_ * (th[n][k - 1] - 2 * th[n][k] + th[n][k + 1]))
            for k in range(nk):
                row = np.zeros(len(th_all)); row[off + k] = lam_0 * 20.0 * sc_
                R.append(row); rb.append(-lam_0 * 20.0 * sc_ * th[n][k])
            for k in (0, nk - 1):
                row = np.zeros(len(th_all)); row[off + k] = 1000.0; R.append(row); rb.append(-1000.0 * th[n][k])
            off += nk
        Am = np.vstack([Aeq, np.array(R)]); bm = np.r_[beq, np.array(rb)]
        dth, *_ = np.linalg.lstsq(Am, bm, rcond=None)
        # trust region: at most `tr` m per key per step (halved after a step that did not improve the score)
        mx = np.abs(dth).max()
        if mx > tr:
            dth *= tr / mx
        trial = []
        for a in (1.0, 0.55, 0.25):
            tt = {}
            off = 0
            for n in names:
                nk = len(keyset(n))
                tt[n] = np.clip(th[n] + a * dth[off:off + nk], -bnd(n), bnd(n)); tt[n][0] = tt[n][-1] = 0.0
                off += nk
            At, Yt = shape(tt)
            mt, _, _, _ = S.errors(c, At, Yt)
            trial.append((score(mt), a, tt))
        trial.sort(key=lambda t: t[0])
        if trial[0][0] < sc - 1e-3:
            th = trial[0][2]
            tr = min(0.25, tr * 1.3)
        else:
            tr *= 0.5                      # no improvement: keep the keys, shrink the trust region
            if tr < 0.01:
                break
    sc, th, met = best
    set_design(th)
    return d, met, hist


if __name__ == "__main__":
    din, dout = sys.argv[1], sys.argv[2]
    iters = int(sys.argv[sys.argv.index("--iters") + 1]) if "--iters" in sys.argv else 12
    bs = float(sys.argv[sys.argv.index("--bound-shift") + 1]) if "--bound-shift" in sys.argv else 0.9
    be = float(sys.argv[sys.argv.index("--bound-edge") + 1]) if "--bound-edge" in sys.argv else 0.35
    lam = float(sys.argv[sys.argv.index("--lam") + 1]) if "--lam" in sys.argv else 3.0
    ms = sys.argv[sys.argv.index("--modes") + 1].split(",") if "--modes" in sys.argv else ["lip_shift", "edgeL"]
    if "--ls-step" in sys.argv:          # R3: the key spacing of lip_shift / lip_drop (m), keys from c -12 (0) to c +15 (0)
        st = float(sys.argv[sys.argv.index("--ls-step") + 1])
        KEYS["lip_shift"] = [-12.0] + [float(x) for x in np.arange(-12.0 + st, 15.0 - 0.5 * st, st)] + [15.0]
    if "--el-step" in sys.argv:          # R3: the key spacing of edgeL (m), keys from c -7 (0) to c +3 (0)
        st = float(sys.argv[sys.argv.index("--el-step") + 1])
        KEYS["edgeL"] = [-7.0] + [float(x) for x in np.arange(-7.0 + st, 3.0 - 0.5 * st, st)] + [3.0]
    print("keys", json.dumps({k: KEYS[k] for k in ("lip_shift", "edgeL")}), flush=True)
    names = []
    for m in ms:
        if m == "edgeL":
            names += ["edgeL_%d" % (k + 1) for k in range(len(D.EDGEL_CENTERS))]
        elif m == "edge_lo":
            names += ["edge_%d" % k for k in (6, 7, 8, 9)]
        elif m == "edge_hi":
            names += ["edge_%d" % k for k in (1, 2, 3, 4, 5)]
        else:
            names.append(m)
    t0 = time.time()
    d = D.Design.load(din)
    out, met, hist = solve(d, names, iters, bs, be, lam_d2=lam, log=lambda *a: print(*a, flush=True))
    j = out.to_json(); j["sil_log"] = {"modes": names, "best": met, "history": hist, "seconds": round(time.time() - t0)}
    json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("FINAL", json.dumps({k: [round(v["max"], 2), round(v["p95"], 2)] for k, v in met.items()}))
