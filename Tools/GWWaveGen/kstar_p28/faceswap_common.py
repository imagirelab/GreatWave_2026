# -*- coding: utf-8 -*-
"""仕上げ28 第1回（FACE-SWAP）の共通部（py -3.10）。numpy だけ。
原画カメラ PaintingCam v1 の射線と、行の面（c 一定）との交わり（視錐の跡）を求める。座標と約束は kh_common と同じ。
参照モデル（他者の作品）は読まない（F13-1）。"""
import os
import sys
import json
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
KH = os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h")
if KH not in sys.path:
    sys.path.insert(0, KH)
import kh_common as KC  # noqa: E402

R4_DIR = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final")
R4_ROWS = os.path.join(R4_DIR, "kstarR4_a45_rows.npz")
R4_GWB = os.path.join(R4_DIR, "kstarR4_a45.gwb")
OUT = os.path.join(REPO, "Unity", "Build", "Polish", "28", "r1_faceswap")
ENVELOPE = os.path.join(REPO, "Tools", "PaintingTruth", "targets", "main_wave_outline_envelope.json")


def load_r4():
    z = np.load(R4_ROWS)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def outline_segments():
    d = json.load(open(ENVELOPE, encoding="utf-8"))
    return {s["id"]: np.array(s["points_display"], float) for s in d["segments"]}


def pixel_rays(px):
    """表示 px (n,2)（画素中心が整数、y 下向き）→ Unity ワールドの射線の向き (n,3)（単位）。project_unity の逆。"""
    pos, r, u, f = KC.cam_basis_unity()
    t = math.tan(math.radians(KC.CAM_VFOV) / 2.0)
    asp = KC.CAM_W / float(KC.CAM_H)
    px = np.atleast_2d(np.asarray(px, float))
    vx = (px[:, 0] + 0.5) / KC.CAM_W
    vy = 1.0 - (px[:, 1] + 0.5) / KC.CAM_H
    cx = (2 * vx - 1) * t * asp
    cy = (2 * vy - 1) * t
    d = f[None, :] + cx[:, None] * r[None, :] + cy[:, None] * u[None, :]
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def ray_row_trace(px, c0):
    """射線と面 c = c0 の交点の断面座標 (a, y)。(n,2)。"""
    pos = KC.CAM_POS_U
    d = pixel_rays(px)
    ps = KC.sec(pos[None])[0]
    ds = np.stack([d @ KC.T, d[:, 1], d @ KC.E], -1)
    s = (c0 - ps[2]) / ds[:, 2]
    return np.stack([ps[0] + s * ds[:, 0], ps[1] + s * ds[:, 1]], -1), s


# ---------------------------------------------------------------- small cv2 plots (no matplotlib here)
class Plot:
    def __init__(self, xlim, ylim, w=520, h=360, title=""):
        self.xlim, self.ylim, self.w, self.h = xlim, ylim, w, h
        self.img = np.full((h, w, 3), 255, np.uint8)
        import cv2
        self.cv2 = cv2
        for g in np.arange(math.ceil(xlim[0] / 5) * 5, xlim[1] + 1e-9, 5):
            x = self.X(g); cv2.line(self.img, (x, 0), (x, h), (230, 230, 230), 1)
        for g in np.arange(math.ceil(ylim[0] / 5) * 5, ylim[1] + 1e-9, 5):
            y = self.Yp(g); cv2.line(self.img, (0, y), (w, y), (230, 230, 230), 1)
        cv2.line(self.img, (0, self.Yp(0)), (w, self.Yp(0)), (160, 160, 160), 1)
        step = 10 if (xlim[1] - xlim[0]) > 30 else 5
        for gx in np.arange(math.ceil(xlim[0] / step) * step, xlim[1] + 1e-9, step):
            cv2.putText(self.img, "%g" % gx, (self.X(gx) + 2, h - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (120, 120, 120), 1, cv2.LINE_AA)
        for gy in np.arange(math.ceil(ylim[0] / 5) * 5, ylim[1] + 1e-9, 5):
            cv2.putText(self.img, "%g" % gy, (2, self.Yp(gy) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (120, 120, 120), 1, cv2.LINE_AA)
        cv2.putText(self.img, title, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    def X(self, v):
        return int(round((v - self.xlim[0]) / (self.xlim[1] - self.xlim[0]) * (self.w - 1)))

    def Yp(self, v):
        return int(round((1 - (v - self.ylim[0]) / (self.ylim[1] - self.ylim[0])) * (self.h - 1)))

    def line(self, xs, ys, col, th=1):
        P = np.stack([[self.X(a) for a in xs], [self.Yp(b) for b in ys]], -1).astype(np.int32)
        self.cv2.polylines(self.img, [P.reshape(-1, 1, 2)], False, col, th, self.cv2.LINE_AA)

    def dot(self, x, y, col, r=3):
        self.cv2.circle(self.img, (self.X(x), self.Yp(y)), r, col, -1, self.cv2.LINE_AA)

    def text(self, s, x, y, col=(0, 0, 0)):
        self.cv2.putText(self.img, s, (x, y), self.cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, self.cv2.LINE_AA)


def grid_images(imgs, ncol):
    h = max(i.shape[0] for i in imgs); w = max(i.shape[1] for i in imgs)
    nrow = (len(imgs) + ncol - 1) // ncol
    S = np.full((h * nrow, w * ncol, 3), 255, np.uint8)
    for k, im in enumerate(imgs):
        r, cc = divmod(k, ncol)
        S[r * h:r * h + im.shape[0], cc * w:cc * w + im.shape[1]] = im
    return S


# ---------------------------------------------------------------- quick painting gate (same machinery as kh_gate_lf / evaluate.py)
class QuickGate:
    """78/130/131/132 と 72 を、定義どおりの読み（包絡版の原画の線そのもの）と σ12 の大きな輪郭（132・72）の両方で測る。
    測り方は kh_gate_lf.LFGate と同じ（評価器の空の被覆の 0.5 等値線、ラベルつき対称 Hausdorff）。"""

    def __init__(self):
        import kh_gate_lf as KG
        self.KG = KG
        self.lf = KG.LFGate()
        tr = self.lf.truth
        F = tr.fam["sky_envelope"]
        self.raw_pts, self.raw_lab = F["pts"], F["label"]

    def measure_rows(self, c, A, Y):
        import candA_common as C
        import gw_wavegen as G0
        V1, tgt, fr = C.painting_frame()
        X = fr.world(c, A, Y)
        cov = V1.rasterize(fr.cam, X, V1.triangles(A.shape[1], A.shape[0]))
        seacov, _ = G0.sea_horizon_cover(fr.cam, tgt.spec)
        other = np.maximum(cov, seacov)
        T = self.lf.T
        rpts = T.boundary_points(1.0 - other, self.lf.truth.spec, self.lf.truth.fmap)
        out = {}
        for k in ("78", "130", "131", "132", "72"):
            res, _, worst = T.labelled_hausdorff(self.raw_pts, self.raw_lab == k, rpts)
            out[k] = {"max_px": float(res["max_px"]), "p95_px": float(res["p95_px"]),
                      "worst_xy": None if worst is None else [round(float(worst[0]), 1), round(float(worst[1]), 1)]}
        for k in ("132", "72"):
            res, _, worst = T.labelled_hausdorff(self.lf.pts, self.lf.lab == k, rpts)
            out[k + "_lf12"] = {"max_px": float(res["max_px"]), "p95_px": float(res["p95_px"]),
                                "worst_xy": None if worst is None else [round(float(worst[0]), 1), round(float(worst[1]), 1)]}
        # 空へのはみ出し・波の中の穴（原画の空の境から 4 px より離れた所だけ数える。記録）
        import cv2
        if not hasattr(self, "_dt"):
            sky = self.lf.truth.cov["sky_envelope"] > 0.5
            e = cv2.morphologyEx(sky.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
            self._dt = cv2.distanceTransform(1 - e, cv2.DIST_L2, 5)
            self._sky = sky
            xs = np.arange(1920)
            self._frame = (xs >= 158) & (xs <= 1762)
        far = (self._dt > 4.0) & self._frame[None, :] & (seacov < 0.5)
        out["spill_px"] = int(((cov > 0.5) & self._sky & far).sum())
        out["hole_px"] = int(((cov < 0.5) & ~self._sky & far & (np.arange(1080)[:, None] < 700)).sum())
        ok = (all(out[k]["max_px"] <= 4 for k in ("78", "130", "131")) and out["132_lf12"]["max_px"] <= 4
              and out["72_lf12"]["p95_px"] <= 4)
        out["pass_def78_lf12"] = bool(ok)
        return out, cov

    @staticmethod
    def brief(g):
        return "78 %.2f 130 %.2f 131 %.2f | 132 raw %.2f lf %.2f | 72 raw p95 %.2f lf p95 %.2f %s" % (
            g["78"]["max_px"], g["130"]["max_px"], g["131"]["max_px"], g["132"]["max_px"], g["132_lf12"]["max_px"],
            g["72"]["p95_px"], g["72_lf12"]["p95_px"], "PASS" if g["pass_def78_lf12"] else "fail") + " | spill %d hole %d" % (g.get("spill_px", -1), g.get("hole_px", -1))


def outline_generators(c, A, Y, segs=("78", "130", "131"), n_per=7, ymin=0.2):
    """左の外輪郭の各点を描いている頂点（原画視点で、その画素の列で最も上に投影される頂点）の行・列・(a, y)。
    FACE-SWAP で輪郭を描く面が頂（列 ~90）から前の唇の上面（列 > 100）へ移ったかを数で見る。"""
    X = KC.world(c, A, Y)
    P = KC.project_unity(X.reshape(-1, 3)).reshape(A.shape[0], A.shape[1], 3)
    px, py = P[..., 0], P[..., 1]
    seg = outline_segments()
    out = []
    for sid in segs:
        pts = seg[sid]
        for k in np.linspace(0, len(pts) - 1, n_per).astype(int):
            x0, y0 = pts[k]
            m = (np.abs(px - x0) < 1.5) & (Y > ymin)
            if not m.any():
                continue
            idx = np.argwhere(m)
            yy = py[m]
            i = int(np.argmin(yy))
            r, cl = idx[i]
            out.append({"seg": sid, "px": [round(float(x0), 1), round(float(y0), 1)], "row": int(r), "c": round(float(c[r]), 2),
                        "col": int(cl), "a": round(float(A[r, cl]), 2), "y": round(float(Y[r, cl]), 2),
                        "row_top_col": int(np.argmax(Y[r, :200])), "row_H": round(float(Y[r].max()), 2)})
    return out


def apex_chord_angle(a, y, half=2.0, j_hi=200):
    """行の頂（列 0..j_hi の最も高い点）から断面に沿って ±half m の 2 点へ引いた弦のなす角（度。180 = 平ら、90 = 直角）。"""
    s = KC.arclen(a, y)
    jm = int(np.argmax(y[:j_hi]))
    sm = s[jm]
    if sm - half < s[0] or sm + half > s[-1]:
        return None
    p0 = np.array([np.interp(sm - half, s, a), np.interp(sm - half, s, y)])
    p1 = np.array([np.interp(sm + half, s, a), np.interp(sm + half, s, y)])
    pm = np.array([a[jm], y[jm]])
    u, v = p0 - pm, p1 - pm
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1))))


def chord_table(c, A, Y, c_lo=-42.0, c_hi=15.0, hmin=2.5):
    out = []
    for r in range(len(c)):
        if c[r] < c_lo or c[r] > c_hi or Y[r].max() < hmin:
            continue
        ang = apex_chord_angle(A[r], Y[r])
        if ang is not None:
            out.append((round(float(c[r]), 2), round(float(Y[r].max()), 2), round(ang, 1)))
    return out


def generator_shift(c, A, Y, n_per=9):
    """同じ原画の画素で、輪郭を描く点が R4 からどれだけ動いたか（FACE-SWAP の確かめ）。
    fwd_of_R4_crest = 候補の点の a − 同じ行の R4 の頂（列 90）の a（+ = 背の頂より前＝唇の側）。
    d_a / d_c / d_y = 候補の点 − R4 の点（同じ画素）。列の番号は組み直しで意味が変わるので、位置で見る。"""
    c0, A0, Y0 = load_r4()
    g0 = outline_generators(c0, A0, Y0, n_per=n_per)
    g1 = outline_generators(c, A, Y, n_per=n_per)
    rows = []
    for x0, x1 in zip(g0, g1):
        rows.append({"seg": x1["seg"], "px": x1["px"], "fwd_of_R4_crest_m": round(x1["a"] - float(A0[x1["row"], 90]), 2),
                     "d_a_m": round(x1["a"] - x0["a"], 2), "d_c_m": round(x1["c"] - x0["c"], 2), "d_y_m": round(x1["y"] - x0["y"], 2)})
    f = np.array([r["fwd_of_R4_crest_m"] for r in rows]); da = np.array([r["d_a_m"] for r in rows])
    dc = np.array([r["d_c_m"] for r in rows]); dy = np.array([r["d_y_m"] for r in rows])
    return {"samples": rows, "share_forward_of_R4_crest_ge_0p5m": round(float((f >= 0.5).mean()), 3),
            "d_a_mean_min_max_m": [round(float(da.mean()), 2), round(float(da.min()), 2), round(float(da.max()), 2)],
            "d_c_mean_min_max_m": [round(float(dc.mean()), 2), round(float(dc.min()), 2), round(float(dc.max()), 2)],
            "d_y_mean_min_max_m": [round(float(dy.mean()), 2), round(float(dy.min()), 2), round(float(dy.max()), 2)]}
