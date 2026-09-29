# -*- coding: utf-8 -*-
"""K*′ 精修 R1：側の縁（輪郭を作る縁）だけで原画の輪郭へ寄せる最後の段（py -3.10）。

設計の「本体」（頂の線・唇・管・殻・唇の上面の断面の形・b 区域）は kh_R1_fit.py で当てはめ、ここでは 9 本の列の帯の edge_k の ramp
（c の鍵 1.5 m おき、|値| ≤ 0.3 m）だけを解く。動くのは原画カメラの視線がかすめる所（graze の重み）だけ。

方法（線形化を繰り返す。差分のヤコビアンは使わない）
  1 評価器と同じ測り方（真値の点 = 包絡版の空の境界、132・72 は大きな輪郭の線；描画の点 = 描画の空 = 1 − max(波, 参照の海面) の
    0.5 等値線）で、項目ごとに「真値 → 描画」「描画 → 真値」の点の符号つきの誤差 e（+ = 候補が小さい、外へ出す）を出す。
  2 各点の描画の点に一番近い網の頂点 (r, j) を責任の頂点とし、その頂点を断面の法線の向きへ 1 m 動かしたときの像の移動の、
    描画の境界の外向きの成分 g（px/m）を求める。
  3 e ≈ g · ΔS(r, j)、ΔS = Σ_b ramp_b(c_r) M_b(r, j)（M_b は kh_designR1.edge_modes）。鍵の値の線形最小二乗（大きな誤差ほど重く、
    鍵の 2 階差と大きさを罰する）を解いて鍵を更新し、形を作り直して繰り返す。一番よかった鍵を残す。
usage: py -3.10 kh_R1_snap.py design_in.json design_out.json [--iters 10] [--step 1.5] [--bound 0.3]
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
import kh_designR1 as D  # noqa: E402

ITEMS = ("78", "130", "131", "132", "72")
T_ = np.array([0.7333652004044829, 0.0, -0.6798348938056156])


class Snap:
    def __init__(self):
        import candA_common as C
        import kh_gate_lfA as KG
        import gw_wavegen as G0
        self.V1, self.tgt, self.fr = C.painting_frame()
        self.g = KG.LFGate()
        self.TL = self.g.T
        self.spec, self.fmap = self.g.truth.spec, self.g.truth.fmap
        self.sig = float(self.spec["scoring"]["contour"]["boundary_smoothing_sigma_px"])
        self.seacov, _ = G0.sea_horizon_cover(self.fr.cam, self.tgt.spec)
        self.tris = self.V1.triangles(D.NU, D.NV)
        self.kd_truth = cKDTree(self.g.pts)

    def render(self, c, A, Y):
        X = self.fr.world(c, A, Y)
        cov = self.V1.rasterize(self.fr.cam, X, self.tris)
        other = np.maximum(cov, self.seacov)
        sky = 1.0 - other
        rpts = self.TL.boundary_points(sky, self.spec, self.fmap)
        skys = cv2.GaussianBlur(sky.astype(np.float64), (0, 0), self.sig) if self.sig > 0 else sky
        return X, rpts, skys

    @staticmethod
    def samp(img, P):
        x = np.clip(P[:, 0], 0, img.shape[1] - 1.001); y = np.clip(P[:, 1], 0, img.shape[0] - 1.001)
        x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
        return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)

    def errors(self, c, A, Y):
        """→ metrics {item: max, p95}, records list of (item, q (render pt), e signed px)."""
        X, rpts, skys = self.render(c, A, Y)
        pts, lab = self.g.pts, self.g.lab
        kd_r = cKDTree(rpts)
        d_all, i_all = self.kd_truth.query(rpts)
        met, recs = {}, []
        for k in ITEMS:
            sel = lab == k
            Tk = pts[sel]
            d_tr, i_tr = kd_r.query(Tk)
            cov_at = 1.0 - self.samp(skys, Tk)                  # > 0.5: the candidate covers the truth point
            e_tr = np.where(cov_at > 0.5, -d_tr, d_tr)
            asg = sel[i_all]
            q_rt = rpts[asg]; d_rt = d_all[asg]
            sky_paint = self.tgt.sample(q_rt, comp=True) if len(q_rt) else np.zeros(0)
            e_rt = np.where(sky_paint > 0, -d_rt, d_rt)
            both = np.r_[d_tr, d_rt]
            met[k] = {"max": float(both.max()), "p95": float(np.percentile(both, 95))}
            for q, e in zip(rpts[i_tr], e_tr):
                recs.append((k, q, float(e)))
            for q, e in zip(q_rt, e_rt):
                recs.append((k, q, float(e)))
        return met, recs, X, skys


    def fixed(self, c, A, Y):
        """fixed-length signed errors per item for a least-squares fit (same measure as the official gate, 132 / 72 against the
        large-form lines): e_tr[i] = signed distance truth point i -> rendered boundary (+ = not covered: grow), e_rt[i] = the
        largest distance among the rendered boundary points whose nearest truth point is i (signed: + in the painted wave, − in
        the painted sky; 0 when none).  -> {item: (e_tr, e_rt)}, metrics"""
        X, rpts, skys = self.render(c, A, Y)
        pts, lab = self.g.pts, self.g.lab
        out, met = {}, {}
        if len(rpts) == 0:
            for k in ITEMS:
                n = int((lab == k).sum()); out[k] = (np.full(n, 50.0), np.zeros(n)); met[k] = {"max": 99.0, "p95": 99.0}
            return out, met
        kd_r = cKDTree(rpts)
        d_all, i_all = self.kd_truth.query(rpts)
        for k in ITEMS:
            sel = np.nonzero(lab == k)[0]
            Tk = pts[sel]
            d_tr, _ = kd_r.query(Tk)
            cov_at = 1.0 - self.samp(skys, Tk)
            e_tr = np.where(cov_at > 0.5, -d_tr, d_tr)
            asg = np.isin(i_all, sel)
            e_rt = np.zeros(len(sel))
            if asg.any():
                q = rpts[asg]; dq = d_all[asg]; iq = i_all[asg]
                sg = np.where(self.tgt.sample(q, comp=True) > 0, -1.0, 1.0)
                pos = np.searchsorted(sel, iq)
                o = np.argsort(dq)                       # the largest distance per truth point wins (written last)
                e_rt[pos[o]] = (sg * dq)[o]
                both = np.r_[d_tr, dq]
            else:
                both = d_tr
            out[k] = (e_tr, e_rt)
            met[k] = {"max": float(both.max()), "p95": float(np.percentile(both, 95))}
        return out, met


def score(met):
    return max(met["78"]["max"], met["130"]["max"], met["131"]["max"], met["132"]["max"], met["72"]["p95"], 0.5 * met["72"]["max"])


def ramp_basis(kc, c):
    n = len(kc)
    return np.stack([D.bspline_ramp(kc, np.eye(n)[i], c) for i in range(n)], 1)


def snap(design, iters=10, step=1.5, bound=0.3, lam_d2=2.0, lam_0=0.05, log=print, modes=None, crange=(-24.0, 15.0), items_w=None):
    S = Snap()
    c = D.c_rows()
    # the body (everything but the edges) is fixed during the snap
    d0 = D.Design.from_json(design.to_json())
    sel_names = list(D.EDGE_NAMES) if not modes else [n for n in D.EDGE_NAMES if n in modes]
    for n in D.EDGE_NAMES:
        d0.keys[n] = ([0.0], [0.0])
    c, A0, Y0, P0 = D.build_base(d0, c)
    A0, Y0 = D.apply_lipprof(c, A0, Y0, P0)
    A0, Y0 = D.apply_ledge(c, A0, Y0, P0)
    Mall = D.edge_modes(c, A0, Y0)                       # (nb_all, nv, nu)
    # the modes that are not solved keep their current ramps (a fixed offset field)
    fixed = np.zeros_like(A0)
    for b, n in enumerate(D.EDGE_NAMES):
        if n not in sel_names and len(design.keys[n][0]) > 1:
            fixed += D.bspline_ramp(design.keys[n][0], design.keys[n][1], c)[:, None] * Mall[b]
    M = np.stack([Mall[D.EDGE_NAMES.index(n)] for n in sel_names])
    nb = len(sel_names)
    kc = [float(x) for x in np.r_[crange[0] - 2.0, np.arange(crange[0], crange[1] + 1e-9, step), crange[1] + 2.0]]
    nk = len(kc)
    B = ramp_basis(kc, c)                               # (nv, nk)
    # current key values (resample the design's edge ramps onto the snap keys)
    v = np.zeros((nb, nk))
    for b, n in enumerate(sel_names):
        cur = D.bspline_ramp(design.keys[n][0], design.keys[n][1], c) if len(design.keys[n][0]) > 1 else np.full(len(c), design.keys[n][1][0])
        if np.any(np.abs(cur) > 1e-9):
            v[b], *_ = np.linalg.lstsq(B, cur, rcond=None)
    # section normals of the fixed body -> world, and the image motion per metre of normal offset
    nrm = np.stack([np.stack(D.row_normals(A0[r], Y0[r]).T, 0) for r in range(len(c))], 0)       # (nv, 2, nu)
    na, ny = nrm[:, 0, :], nrm[:, 1, :]

    def shape(vv):
        Dm = np.einsum("bk,rk,brj->rj", vv, B, M) + fixed
        return A0 + Dm * na, Y0 + Dm * ny, Dm

    def solve_step(vv, recs, X, skys, A, Y):
        cam = S.fr.cam
        Pj = cam.project(X.reshape(-1, 3))
        body = (Y.reshape(-1) > 0.3) & (Pj[:, 2] > 0.5)
        idx = np.nonzero(body)[0]
        kd = cKDTree(Pj[idx, :2])
        qs = np.array([q for _, q, _ in recs]); es = np.array([e for _, _, e in recs]); ks = [k for k, _, _ in recs]
        dd, ii = kd.query(qs)
        vid = idx[ii]
        r_ = vid // D.NU; j_ = vid % D.NU
        # image motion of those vertices for +1 m along the section normal
        Xw = X.reshape(-1, 3)[vid]
        nw = na[r_, j_][:, None] * T_[None, :] + ny[r_, j_][:, None] * np.array([0.0, 1.0, 0.0])[None, :]
        P1 = cam.project(Xw + 0.05 * nw)[:, :2]; P0_ = Pj[vid, :2]
        dP = (P1 - P0_) / 0.05
        gx = cv2.Sobel(skys, cv2.CV_64F, 1, 0, ksize=3); gy = cv2.Sobel(skys, cv2.CV_64F, 0, 1, ksize=3)
        gv = np.stack([S.samp(gx, qs), S.samp(gy, qs)], -1)
        gv /= np.maximum(np.linalg.norm(gv, axis=1, keepdims=True), 1e-9)
        g = np.sum(dP * gv, 1)                           # px per metre, + = moving along +n moves the boundary outward
        ok = (dd < 6.0) & (np.abs(es) > 0.3)
        es = np.clip(es, -15.0, 15.0)
        iw = items_w or {}
        wi = np.array([iw.get(k, 1.0 if k != "72" else 0.8) for k in ks]) * (1.0 + (np.abs(es) / 3.0) ** 2)
        wi = wi * ok
        # rows of the linear system: g_i * sum_bk B[r_i,k] M_b[r_i,j_i] dv_bk = e_i
        Jb = M[:, r_, j_]                                # (nb, n)
        Jk = B[r_]                                       # (n, nk)
        J = (g[:, None, None] * Jb.T[:, :, None] * Jk[:, None, :]).reshape(len(es), nb * nk)
        sw = np.sqrt(wi)
        Aeq = J * sw[:, None]; beq = es * sw
        # regularisation: second differences along the keys (per band) and the size of the values
        R = []; rb = []
        for b in range(nb):
            for k in range(1, nk - 1):
                row = np.zeros(nb * nk); row[b * nk + k - 1] = 1; row[b * nk + k] = -2; row[b * nk + k + 1] = 1
                R.append(row * lam_d2); rb.append(-lam_d2 * (vv[b, k - 1] - 2 * vv[b, k] + vv[b, k + 1]))
        for i in range(nb * nk):
            row = np.zeros(nb * nk); row[i] = lam_0; R.append(row); rb.append(-lam_0 * vv.ravel()[i])
        # the end keys stay 0
        for b in range(nb):
            for k in (0, nk - 1):
                row = np.zeros(nb * nk); row[b * nk + k] = 100.0; R.append(row); rb.append(-100.0 * vv[b, k])
        Am = np.vstack([Aeq, np.array(R)]); bm = np.r_[beq, np.array(rb)]
        dv, *_ = np.linalg.lstsq(Am, bm, rcond=None)
        return dv.reshape(nb, nk), int(ok.sum())

    best = None
    hist = []
    for it in range(iters + 1):
        A, Y, Dm = shape(v)
        met, recs, X, skys = S.errors(c, A, Y)
        sc = score(met)
        hist.append({"it": it, "score": round(sc, 2), "met": {k: [round(m["max"], 2), round(m["p95"], 2)] for k, m in met.items()},
                     "max_offset_m": round(float(np.abs(Dm).max()), 3)})
        log(json.dumps(hist[-1]))
        if best is None or sc < best[0]:
            best = (sc, v.copy(), met)
        if it == iters:
            break
        dv, nuse = solve_step(v, recs, X, skys, A, Y)
        # line search on the real score (the linearisation is local)
        trial = []
        for a in (1.0, 0.6, 0.3):
            vt = np.clip(v + a * dv, -bound, bound)
            At, Yt, _ = shape(vt)
            mt, _, _, _ = S.errors(c, At, Yt)
            trial.append((score(mt) + 0.02 * sum(m["p95"] for m in mt.values()), a, vt))
        trial.sort(key=lambda t: t[0])
        v = trial[0][2]
    sc, v, met = best
    out = D.Design.from_json(design.to_json())
    for b, n in enumerate(sel_names):
        out.keys[n] = (list(kc), [float(x) for x in v[b]])
    return out, met, hist


if __name__ == "__main__":
    din, dout = sys.argv[1], sys.argv[2]
    iters = int(sys.argv[sys.argv.index("--iters") + 1]) if "--iters" in sys.argv else 10
    step = float(sys.argv[sys.argv.index("--step") + 1]) if "--step" in sys.argv else 1.5
    bound = float(sys.argv[sys.argv.index("--bound") + 1]) if "--bound" in sys.argv else 0.3
    lam = float(sys.argv[sys.argv.index("--lam") + 1]) if "--lam" in sys.argv else 2.0
    modes = sys.argv[sys.argv.index("--modes") + 1].split(",") if "--modes" in sys.argv else None
    cr = tuple(float(x) for x in sys.argv[sys.argv.index("--crange") + 1].split(",")) if "--crange" in sys.argv else (-24.0, 15.0)
    t0 = time.time()
    d = D.Design.load(din)
    out, met, hist = snap(d, iters, step, bound, lam_d2=lam, modes=modes, crange=cr)
    j = out.to_json(); j["snap_log"] = {"best": met, "history": hist, "seconds": round(time.time() - t0)}
    try:
        j["fit_log"] = json.load(open(din, encoding="utf-8")).get("fit_log")
    except Exception:
        pass
    json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("FINAL", json.dumps(met))
