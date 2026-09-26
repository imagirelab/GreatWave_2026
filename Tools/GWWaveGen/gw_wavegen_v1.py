# -*- coding: utf-8 -*-
"""gw_wavegen v1（番号26「主役波の終態 K*」、立体解釈 30°/45°/60°）。

番号24 の v0（gw_wavegen.py）は変えずに、そのカメラ・投影・検査の関数を読み込んで使う。
v0 は主断面を PaintingCam 中心に相似変形して並べた「光線に沿う錐」で、原画視点の輪郭は構成上一致するが、
側面から見ると楔形になる（Step_24 の限界 3）。v1 は立体解釈ごとに本物の 3D の掃引を作る。

  1. 波峰線 e（水平）を画面と角 α で置き、断面は e に垂直な平行の鉛直面にする。
  2. 主断面 P0 は、原画の包絡輪郭の最上点 → 132 → 唇先端 → 72 → 内壁の下端を、藍線の半幅だけ内側へ
     補正してから主断面へ逆投影した曲線と、背面の坂（参照モデル Q5 の壁の厚さ 0.27H）でつくる。
  3. 各行は P0 を e 方向へ平行移動して変える：手前の肩は原画の許容領域（空でない所）に収まる最大の高さ D、
     唇は c の滑らかな関数 λ(c) で厚みを潰してから縮め、奥側は唇先から先を後ろへ下げて（後退 r）から海面へ下げる。
     この結果、原画視点のシルエットは各行の像の包絡線になる（行ごとに輪郭へ接する）。
  4. はみ出しが残る所と届かない所は、主断面 P0 の輪郭部分を断面内の法線方向へ動かして直す（逆畳み込み）。
  5. シルエット頂点を目標の射線上へ貼り付け（投影固定）、その移動を (σ, c) 空間の薄板スプライン（TPS）で
     内部へ広げる。変位の上限は局所寸法（行の頂の高さ）の 8%。
  6. 近くの三角形の交差（面の折り返し）を調べ、主断面の輪郭の頂点を動かさずに近くの頂点の平滑化で解く。
  手前の肩と主断面では断面が波峰線にほぼ垂直になり、奥の端（頂から約 3 m）では頂の列が後ろへ曲がる（記録する）。

使い方（リポジトリ根で）:
    py -3.10 Tools/GWWaveGen/gw_wavegen_v1.py [--only a45] [--out DIR]
出力（既定 Unity/Build/ArtFirst/26/kstar、Git 対象外の /Unity/Build/ の下）:
    kstar_aXX.gwb        GWW0 形式（番号24 と同じ書式、1 フレーム＝t* の K*）
    kstar_aXX.obj        同じ頂点・UV・三角形（番号28 の焼き込み用。Unity 座標のまま、m）
    kstar_aXX_meta.json  パラメータ、行ごとの変形量、主断面、検査、参照比率の自己検査、入力の SHA-256
    preview/             numpy ラスタライズによる t* の設計確認（Unity 描画ではない）
numpy と OpenCV だけを使う。座標は Unity のワールド座標（左手系、Y 上、m）。
"""
import argparse
import datetime
import json
import math
import os
import platform
import struct
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import gw_wavegen as G0  # noqa: E402  番号24 の v0（変更しない）

DEFAULT_PARAMS = os.path.join(HERE, "params_v1_kstar.json")
DEFAULT_OUT = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26", "kstar")
UP = np.array([0.0, 1.0, 0.0])
SEGS = ["78", "130", "131", "132", "72"]
MAGIC = b"GWW0"
FORMAT_VERSION = 1


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def arclen(P):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def resample(P, n):
    s = arclen(P)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])], -1)


def resample_adaptive(P, n, wk):
    """曲率の大きい所（爪の包絡のくぼみなど）に点を多く置く再標本化。密度 ∝ 1 + wk·|曲率|（wk は m）。"""
    s = arclen(P)
    Pd = resample(P, 4 * n)
    sd = np.linspace(0.0, s[-1], 4 * n)
    d1 = np.gradient(Pd, sd, axis=0)
    d2 = np.gradient(d1, sd, axis=0)
    kap = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.linalg.norm(d1, axis=1) ** 3, 1e-12)
    kap = np.convolve(np.pad(kap, 4, mode="edge"), np.ones(9) / 9, "valid")
    w = 1.0 + np.minimum(wk * kap, 3.0)   # 最大で 4 倍の密度（角で点が重ならないように）
    cw = np.concatenate([[0.0], np.cumsum(0.5 * (w[1:] + w[:-1]) * np.diff(sd))])
    t = np.interp(np.linspace(0, cw[-1], n), cw, sd)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])], -1)


def resample_with_corners(P, n, turn_deg):
    """鋭い角（爪の包絡のくぼみの頂点など。前後 3 点で向きが turn_deg 以上変わる所）を必ず標本点にして、
    角の間は弧長で一様に再標本化する。点の総数は n。"""
    s = arclen(P)
    d = np.diff(P, axis=0)
    ang = np.arctan2(d[:, 1], d[:, 0])
    k = 3
    turn = np.zeros(len(P))
    for i in range(k, len(P) - k):
        a0 = ang[i - k:i].mean() if False else math.atan2(*(P[i] - P[i - k])[::-1])
        a1 = math.atan2(*(P[i + k] - P[i])[::-1])
        turn[i] = abs((a1 - a0 + math.pi) % (2 * math.pi) - math.pi)
    cand = np.nonzero(np.degrees(turn) >= turn_deg)[0]
    knots = []
    for i in cand:
        # 近い候補の中で曲がりが最大の点だけ
        lo, hi = i - 2 * k, i + 2 * k
        if turn[i] >= turn[max(lo, 0):hi + 1].max() and (not knots or s[i] - s[knots[-1]] > 0.5):
            knots.append(int(i))
    bounds = [0] + knots + [len(P) - 1]
    L = s[-1]
    # 区間ごとの点数を長さに比例させる（各区間の両端は共有）
    segL = np.array([s[b] - s[a] for a, b in zip(bounds[:-1], bounds[1:])])
    m = np.maximum(1, np.round(segL / L * (n - 1)).astype(int))
    while m.sum() > n - 1:
        m[np.argmax(m)] -= 1
    while m.sum() < n - 1:
        m[np.argmax(segL / m)] += 1
    out = [P[0]]
    knot_idx = []
    pos = 0
    for (a, b), mi in zip(zip(bounds[:-1], bounds[1:]), m):
        t = np.linspace(s[a], s[b], mi + 1)[1:]
        out.append(np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], -1))
        pos += mi
        knot_idx.append(pos)
    return np.vstack([np.atleast_2d(o) for o in out]), [float(s[i]) for i in knots], knot_idx[:-1]


def monotone_redistribute(a, gap=0.02):
    """a を増加列にする。折り返した区間（前の最大値より手前へ戻る点の並び）は、区間の前後の値の間へ一様に並べ直す。"""
    a = a.copy()
    n = len(a)
    j = 1
    while j < n:
        if a[j] > a[j - 1] + 1e-9:
            j += 1
            continue
        k = j
        while k < n and a[k] <= a[j - 1] + gap:
            k += 1
        lo = a[j - 1]
        hi = a[k] if k < n else lo + gap * (k - j + 1)
        if hi <= lo:
            hi = lo + gap * (k - j + 1)
        a[j:k] = lo + (hi - lo) * np.arange(1, k - j + 1) / (k - j + 1)
        j = k
    return a


def untangle_rows(A, Y, max_iter=80):
    """行の断面が折り返した所（隣り合わない線分の交差）を、その近くの頂点の平滑化で解く。直した行と回数を返す。"""
    fixed = {}
    for v in range(A.shape[0]):
        for it in range(max_iter):
            hit = section_crossings(np.stack([A[v], Y[v]], -1))
            if not hit:
                break
            for i, j in hit:
                for kk in (i, j):
                    lo, hi = max(kk - 3, 1), min(kk + 5, A.shape[1] - 1)
                    for q in range(lo, hi):
                        A[v, q] = 0.25 * A[v, q - 1] + 0.5 * A[v, q] + 0.25 * A[v, q + 1]
                        Y[v, q] = 0.25 * Y[v, q - 1] + 0.5 * Y[v, q] + 0.25 * Y[v, q + 1]
            fixed[v] = it + 1
    return A, Y, fixed


def _seg_tri_hits(P, Q, V0, V1, V2, eps=1e-7):
    """線分 P→Q が三角形の内部（辺・頂点を除く）を通るか（Möller–Trumbore、配列で一括）。"""
    d = Q - P
    e1 = V1 - V0
    e2 = V2 - V0
    h = np.cross(d, e2)
    a = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(a) > 1e-14
    f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
    sv = P - V0
    u = f * np.einsum("ij,ij->i", sv, h)
    q = np.cross(sv, e1)
    v = f * np.einsum("ij,ij->i", d, q)
    t = f * np.einsum("ij,ij->i", e2, q)
    return ok & (u > eps) & (v > eps) & (u + v < 1 - eps) & (t > eps) & (t < 1 - eps)


def local_self_intersections(X, win=6):
    """格子のシート X (nv, nu, 3) の、近く（同じ帯と隣の帯、列の差が win 以内）で頂点を共有しない三角形どうしの交差。
    交差した三角形の頂点の (行, 列) を返す（Blender の BVH 検査の前に生成器の中で消すため）。"""
    nv, nu, _ = X.shape
    V = X.reshape(-1, 3)
    tris = triangles(nu, nv)
    nt = len(tris)
    q = np.arange(nt) // 2
    tv = q // (nu - 1)
    tj = q % (nu - 1)
    bad = set()
    for dv in (0, 1):
        for dj in range(-win, win + 1):
            for s0 in (0, 1):
                for s1 in (0, 1):
                    if dv == 0 and (dj < 0 or (dj == 0 and s1 <= s0)):
                        continue
                    ia = np.nonzero((tris[:, 0] >= 0) & (np.arange(nt) % 2 == s0))[0]
                    ib_q = (tv[ia] + dv) * (nu - 1) + (tj[ia] + dj)
                    okq = (tv[ia] + dv < nv - 1) & (tj[ia] + dj >= 0) & (tj[ia] + dj < nu - 1)
                    ia = ia[okq]
                    ib = 2 * ib_q[okq] + s1
                    A_ = tris[ia]
                    B_ = tris[ib]
                    share = (A_[:, :, None] == B_[:, None, :]).any((1, 2))
                    ia, ib, A_, B_ = ia[~share], ib[~share], A_[~share], B_[~share]
                    if len(ia) == 0:
                        continue
                    hit = np.zeros(len(ia), bool)
                    for (T1, T2) in ((A_, B_), (B_, A_)):
                        for e0, e1 in ((0, 1), (1, 2), (2, 0)):
                            hit |= _seg_tri_hits(V[T1[:, e0]], V[T1[:, e1]], V[T2[:, 0]], V[T2[:, 1]], V[T2[:, 2]])
                    for t in np.concatenate([A_[hit].ravel(), B_[hit].ravel()]):
                        bad.add((int(t // nu), int(t % nu)))
    return bad


def push_in_pokes(fam, A, Y, locked, prm):
    """目標の外へ 0.25 px より多く出た頂点（locked 以外）を、断面の面内の法線方向へ内側へ戻す。戻した頂点の数を返す。"""
    idx = np.arange(fam.nv)
    s, pj = fam.sdf(idx, A, Y)
    Pn = np.stack([A, Y], -1)
    d = np.gradient(Pn, axis=1)
    d /= np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-12)
    n = np.stack([d[..., 1], -d[..., 0]], -1)
    eps = 0.01
    s2, _ = fam.sdf(idx, A + eps * n[..., 0], Y + eps * n[..., 1])
    g = (s2 - s) / eps
    inframe = (pj[..., 0] >= fam.tgt.x0 - 2) & (pj[..., 0] <= fam.tgt.x1 + 2) & (pj[..., 1] >= -2) & (pj[..., 1] <= 1081)
    sel = (s > 0.25) & (s > -1e8) & (g < -prm.get("g_min_px_per_m", 10.0)) & ~locked & inframe
    dd = np.where(sel, (s + 0.1) / np.abs(np.where(sel, g, -1.0)), 0.0)
    dd = np.clip(dd, 0.0, prm.get("snap_max_m", 0.1))
    return A + dd * n[..., 0], Y + dd * n[..., 1], int(sel.sum())


def fix_self_intersections(fr, c, A, Y, max_iter=20, win=6, locked=None):
    """近くの三角形の交差を、交差した頂点とその隣の平滑化（断面の面内の座標 a, y だけ）で解く。
    locked の頂点（主断面の輪郭の頂点など、目標の射線上へ貼り付けた頂点）は動かさない。"""
    moved = np.zeros_like(A)
    A0, Y0 = A.copy(), Y.copy()
    history = []
    for it in range(max_iter):
        X = fr.world(c, A, Y)
        bad = local_self_intersections(X, win)
        history.append(len(bad))
        if not bad:
            break
        nv, nu = A.shape
        mark = np.zeros((nv, nu), bool)
        for v, j in bad:
            mark[max(v - 1, 0):v + 2, max(j - 2, 0):j + 3] = True
        mark[:, 0] = mark[:, -1] = False
        mark[0, :] = mark[-1, :] = False
        if locked is not None:
            mark &= ~locked
        An = A.copy()
        Yn = Y.copy()
        An[1:-1, 1:-1] = 0.5 * A[1:-1, 1:-1] + 0.125 * (A[:-2, 1:-1] + A[2:, 1:-1] + A[1:-1, :-2] + A[1:-1, 2:])
        Yn[1:-1, 1:-1] = 0.5 * Y[1:-1, 1:-1] + 0.125 * (Y[:-2, 1:-1] + Y[2:, 1:-1] + Y[1:-1, :-2] + Y[1:-1, 2:])
        A = np.where(mark, An, A)
        Y = np.where(mark, Yn, Y)
    return A, Y, history, float(np.hypot(A - A0, Y - Y0).max())


def gauss_rows(x, sigma):
    """行方向の 1 次元ガウス平滑（端は端の値で延長）。"""
    if sigma <= 0:
        return x.copy()
    r = int(math.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(x, r, mode="edge"), k, "valid")


# ---------------------------------------------------------------- 目標（許容領域の符号付き距離）
class Target:
    """原画の空マスク（包絡版）の外側＝許容領域。符号付き距離（表示 px、正＝空の側）を 2 倍の格子で持つ。
    主浪の輪郭（78/130/131/132/72）の近く（12 px 以内、20 px までで 0 へ）だけ、区間ごとの藍線の半幅（線幅プロファイルの
    区間中央値の半分）を足し、目標を線の中心まで内側へ補正する（作業計画 4.0「目標輪郭は藍線の半幅だけ内側へ補正」）。"""

    def __init__(self, ss=2):
        self.spec = T.load_spec()
        self.fm = T.FrameMap(self.spec)
        td = T.TARGET_DIR
        reg = T.load_json(os.path.join(td, "regions.json"))
        cov = T.load_cov_png(os.path.join(td, reg["masks"]["sky_envelope"]))
        H, W = cov.shape
        self.ss = ss
        cov2 = cv2.resize(cov.astype(np.float32), (W * ss, H * ss), interpolation=cv2.INTER_LINEAR)
        sky = (cov2 > 0.5).astype(np.uint8)
        din = cv2.distanceTransform(sky, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        dout = cv2.distanceTransform(1 - sky, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        sdf = np.where(sky > 0, din - 0.5, -(dout - 0.5)) / ss
        env = T.load_json(os.path.join(td, "main_wave_outline_envelope.json"))
        self.seg = {s["id"]: np.array(s["points_display"], np.float64) for s in env["segments"]}
        lw = T.load_json(os.path.join(td, "line_width_profile.json"))
        self.half_w = {}
        for s in lw["segments"]:
            w = np.array([v for v in s["width_ref_px"] if v is not None])
            self.half_w[s["id"]] = float(np.median(w)) * self.fm.s / 2.0
        lab = np.zeros((H * ss, W * ss), np.uint8)
        ids = {k: i + 1 for i, k in enumerate(SEGS)}
        for k in SEGS:
            P = np.round((self.seg[k] + 0.5) * ss - 0.5).astype(np.int32)
            cv2.polylines(lab, [P], False, ids[k], 1)
        mask = np.where(lab > 0, 0, 1).astype(np.uint8)
        dist, labels = cv2.distanceTransformWithLabels(mask, cv2.DIST_L2, cv2.DIST_MASK_5, labelType=cv2.DIST_LABEL_PIXEL)
        zi = np.flatnonzero(mask.ravel() == 0)
        lab_of_label = np.zeros(labels.max() + 1, np.uint8)
        lab_of_label[1:len(zi) + 1] = lab.ravel()[zi]
        segimg = lab_of_label[labels]
        hw = np.zeros_like(sdf, np.float32)
        for k in SEGS:
            hw[segimg == ids[k]] = self.half_w[k]
        taper = 1.0 - smoothstep((dist / ss - 12.0) / 8.0)
        self.sdf_raw = sdf.astype(np.float32)
        self.sdf = (sdf + hw * taper).astype(np.float32)
        self.x0, self.x1 = self.fm.x0, self.fm.x1

    def sample(self, xy, comp=True):
        """双線形で標本化。採点列の外は採点列の端の列で評価し（左右へ水平に延長）、画面の上端より上は上へ出た分を足す。"""
        f = self.sdf if comp else self.sdf_raw
        ss = self.ss
        x = (np.clip(xy[:, 0], self.x0, self.x1) + 0.5) * ss - 0.5
        y = (xy[:, 1] + 0.5) * ss - 0.5
        above = np.maximum(-y / ss, 0.0)
        xc = np.clip(x, 0, f.shape[1] - 1.001)
        yc = np.clip(y, 0, f.shape[0] - 1.001)
        x0 = np.floor(xc).astype(int)
        y0 = np.floor(yc).astype(int)
        fx = xc - x0
        fy = yc - y0
        v = (f[y0, x0] * (1 - fx) * (1 - fy) + f[y0, x0 + 1] * fx * (1 - fy) + f[y0 + 1, x0] * (1 - fx) * fy + f[y0 + 1, x0 + 1] * fx * fy)
        return v + above


def inward_offset_display(P, hw, sky_sdf):
    """表示 px の折れ線を水側（空の SDF が小さくなる側）へ hw だけ動かす。"""
    d = np.gradient(P, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    n = np.stack([-d[:, 1], d[:, 0]], -1)
    s1 = sky_sdf(P + 2.0 * n)
    s2 = sky_sdf(P - 2.0 * n)
    sign = np.where(s1 < s2, 1.0, -1.0)[:, None]
    return P + sign * n * hw[:, None]


def remove_loops(P):
    """折れ線の小さな輪（内側への平行移動で、爪の包絡の鋭いくぼみにできる）を交点で切り取る。"""
    P = P.copy()
    for _ in range(200):
        hit = section_crossings(P)
        if not hit:
            break
        i, j = hit[0]
        p, r = P[i], P[i + 1] - P[i]
        q, s_ = P[j], P[j + 1] - P[j]
        den = r[0] * s_[1] - r[1] * s_[0]
        t = ((q - p)[0] * s_[1] - (q - p)[1] * s_[0]) / den
        x = p + t * r
        P = np.vstack([P[:i + 1], x[None, :], P[j + 1:]])
    return P


# ---------------------------------------------------------------- 立体解釈の座標系
class Frame:
    def __init__(self, spec, alpha_deg, anchor_prm, tgt):
        self.cam = G0.PaintingCam(spec)
        cam = self.cam
        h = cam.f.copy()
        h[1] = 0.0
        self.h = h / np.linalg.norm(h)
        ea = np.cross(UP, self.h)
        self.ea = ea / np.linalg.norm(ea)
        a = math.radians(alpha_deg)
        self.alpha = float(alpha_deg)
        self.e = math.cos(a) * self.ea + math.sin(a) * self.h   # 波峰線（右奥）
        self.t = math.sin(a) * self.ea - math.cos(a) * self.h   # 進行方向（右手前）、断面内の横軸 a
        allp = np.vstack([tgt.seg[k] for k in SEGS])
        itop = int(np.argmin(allp[:, 1]))
        self.top_display = allp[itop]
        O = np.array(anchor_prm["v0_plane_through"], np.float64)
        A = G0.intersect_plane(cam.pos, cam.rays(self.top_display[None]), O, self.h)[0]
        self.A = A                                   # 波頂の錨点（主断面の頂）
        self.O0 = np.array([A[0], 0.0, A[2]])       # 主断面の原点（海面）
        self.H0 = float(A[1])

    def K(self, c):
        return self.O0[None, :] + np.asarray(c, np.float64)[:, None] * self.e[None, :]

    def to_sec(self, X, c=0.0):
        d = X - (self.O0 + c * self.e)
        return np.stack([d @ self.t, X[:, 1]], -1)

    def world(self, c, a, y):
        return self.K(c)[:, None, :] + a[..., None] * self.t[None, None, :] + y[..., None] * UP[None, None, :]


# ---------------------------------------------------------------- 主断面
class Profile:
    def __init__(self, fr, tgt, prm):
        cam = fr.cam
        n = prm["n"]
        H0 = fr.H0
        pts, labs = [], []
        for k in SEGS:
            P = tgt.seg[k]
            if pts and np.allclose(pts[-1][-1], P[0]):
                P = P[1:]
            pts.append(P)
            labs += [k] * len(P)
        disp = np.vstack(pts)
        labs = np.array(labs)
        hw = np.array([tgt.half_w[k] for k in labs])
        comp = inward_offset_display(disp, hw, lambda q: tgt.sample(q, comp=False))
        i0 = int(np.argmin(np.linalg.norm(disp - fr.top_display, axis=1)))
        front = comp[i0:]
        lab = labs[i0:]
        n_before = len(front)
        front2 = remove_loops(front)
        # 輪を切り取った後の点のラベルは、元の点列で最も近い点のラベルにする
        _, near_i = T.nearest(front2, front)
        lab = lab[near_i]
        self.loops_removed_points = int(n_before - len(front2))
        front = front2
        Wf = G0.intersect_plane(cam.pos, cam.rays(front), fr.A, fr.e)
        Q = fr.to_sec(Wf, 0.0)
        self.front_display_comp = front
        C, self.corner_knots, kidx = resample_with_corners(Q, n["C"], prm.get("corner_turn_deg", 50.0))
        # 再標本化でできる小さな尖り（折り返しかけた 3 点）を、端点を固定した軽い平滑化で消す（0.1 px 程度しか動かない）
        sm = prm.get("C_smooth_samples", 0.8)
        if sm > 0:
            Cs = np.stack([gauss_rows(C[:, 0], sm), gauss_rows(C[:, 1], sm)], -1)
            Cs[0], Cs[-1] = C[0], C[-1]
            C = Cs
        _, near_q = T.nearest(C, Q)
        labC = lab[near_q]
        i72 = np.nonzero(labC == "72")[0]
        j_tip_c = int(i72[0])
        up72 = i72[C[i72, 1] > 0.35 * H0]
        j_corner_c = int(up72[np.argmin(C[up72, 0])])
        face = C[j_corner_c:]
        yh = 0.5 * H0
        k = np.nonzero((face[:-1, 1] - yh) * (face[1:, 1] - yh) <= 0)[0]
        if len(k):
            k = int(k[0])
            tt = (yh - face[k, 1]) / (face[k + 1, 1] - face[k, 1])
            a_face_half = face[k, 0] + tt * (face[k + 1, 0] - face[k, 0])
        else:
            a_face_half = float(C[j_corner_c, 0])
        a_bf = 2.0 * (a_face_half - prm["wall_ratio"] * H0)   # smoothstep 坂の半分の高さは足と頂の中点
        uB = np.linspace(0, 1, n["B"] + 1)[:-1]
        B = np.stack([a_bf * (1 - uB), H0 * smoothstep(uB)], -1)
        Aseg = np.stack([np.linspace(a_bf - prm["flat_back_m"], a_bf, n["A"] + 1)[:-1], np.zeros(n["A"])], -1)
        p = C[-1]
        rt = min(prm["trough_radius_m"], 0.8 * p[1])
        nd1 = n["D"] // 2
        nd2 = n["D"] - nd1
        seg1 = np.stack([np.full(nd1, p[0]), np.linspace(p[1], rt, nd1 + 1)[1:]], -1)
        th = np.linspace(0, np.pi / 2, nd2 + 1)[1:]
        seg2 = np.stack([p[0] + rt * (1 - np.cos(th)), rt - rt * np.sin(th)], -1)
        Dseg = np.vstack([seg1, seg2])
        Dseg[-1, 1] = 0.0
        endp = Dseg[-1]
        E = np.stack([np.linspace(endp[0], endp[0] + prm["flat_front_m"], n["E"] + 1)[1:], np.zeros(n["E"])], -1)
        self.P = np.vstack([Aseg, B, C, Dseg, E])
        self.nu = len(self.P)
        self.j_B = n["A"]
        self.j_top = n["A"] + n["B"]
        self.j_tip = self.j_top + j_tip_c
        self.j_corner = self.j_top + j_corner_c
        self.j_facebot = self.j_top + n["C"] - 1
        self.j_E = self.j_facebot + n["D"] + 1
        self.a_face_half = float(a_face_half)
        self.a_bf = float(a_bf)
        self.driven = np.zeros(self.nu, bool)
        self.driven[self.j_top:self.j_facebot + 1] = True
        # 鋭い角（爪の包絡のくぼみの頂点）の標本点。角では断面内の法線が定まらないので、貼り付けに使わない
        self.knot_cols = [self.j_top + int(k) for k in kidx]
        self.labC = labC

    @staticmethod
    def normals(P):
        d = np.gradient(P, axis=0)
        d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
        return np.stack([d[:, 1], -d[:, 0]], -1)   # 水側（面内の内向き）


def lip_midline(P, jt, jp, jk):
    """唇の上側と下側を、同じ横位置の反対側との中点へ寄せるための中線の y（番号24 v0 の _kstar_rows と同じ考え方）。"""
    ym = P[:, 1].copy()
    upper = [(k, k + 1) for k in range(jt, jp)]
    lower = [(k, k + 1) for k in range(jp, jk)] + [(jk, jt)]
    for j in range(jt + 1, jk):
        aj, yj = P[j]
        edges = lower if j <= jp else upper + [(jk, jt)]
        best = None
        for e0, e1 in edges:
            p0, p1 = P[e0], P[e1]
            if (p0[0] - aj) * (p1[0] - aj) > 0 or p0[0] == p1[0]:
                continue
            t = (aj - p0[0]) / (p1[0] - p0[0])
            yc = p0[1] + t * (p1[1] - p0[1])
            if (j <= jp and yc < yj - 1e-6) or (j > jp and yc > yj + 1e-6):
                if best is None or abs(yc - yj) < abs(best - yj):
                    best = yc
        if best is not None:
            ym[j] = 0.5 * (yj + best)
    return ym


# ---------------------------------------------------------------- 行（断面の族）
class Family:
    def __init__(self, fr, prof, tgt, prm_rows, prm_fit):
        self.fr, self.prof, self.tgt = fr, prof, tgt
        self.pf = prm_fit
        nv, nn = prm_rows["nv"], prm_rows["rows_near"]
        nf = nv - nn - 1
        un = np.arange(nn) / nn
        c_near = prm_rows["c_min"] * (1.0 - un) ** prm_rows["near_pow"]
        uf = np.arange(1, nf + 1) / nf
        c_far = prm_rows["c_max"] * uf ** prm_rows["far_pow"]
        self.c = np.concatenate([c_near, [0.0], c_far])
        self.nv = nv
        self.v_main = nn
        self.near = self.c < 0
        self.far = self.c > 0
        c = self.c
        self.D_design = np.where(self.near, np.exp(-(np.abs(c) / prm_fit["D_design_near_sigma_m"]) ** prm_fit["D_design_near_pow"]),
                                 np.exp(-(np.maximum(c - prm_fit["far_D_design_delay_m"], 0.0) / prm_fit["far_D_design_sigma_m"]) ** 2))
        self.D = np.ones(nv)
        self.kap = np.zeros(nv)
        self.m = np.ones(nv)
        self.ret = np.zeros(nv)
        self.r_max = prm_fit["retreat_max_m"]
        self.set_profile(prof.P)

    def set_profile(self, P):
        pr = self.prof
        self.P = P
        jt, jk, jp = pr.j_top, pr.j_corner, pr.j_tip
        self.ymid = lip_midline(P, jt, jp, jk)
        s = arclen(P)
        rho = (s[jt:jk + 1] - s[jt]) / (s[jk] - s[jt])
        self.F = P[jt][None, :] + rho[:, None] * (P[jk] - P[jt])[None, :]
        om = np.zeros(pr.nu)
        om[jt:jp + 1] = smoothstep((s[jt:jp + 1] - s[jt]) / (s[jp] - s[jt]))
        om[jp + 1:] = 1.0
        self.omega = om
        # 唇先の近く（弧長で tip_collapse_taper_m 以内）は厚みを潰さない（縦に寄せると唇先で面が折り返すため）。縮め（m）だけで引っ込める
        tw = self.pf.get("tip_collapse_taper_m", 1.5)
        self.kap_w = smoothstep(np.abs(s - s[jp]) / tw) if tw > 0 else np.ones(pr.nu)

    def rows(self, idx, D=None, kap=None, m=None, ret=None, P=None):
        """行 idx の断面内座標 (a, y)。変形の順：唇の厚みを潰す（κ）→ 唇を縮める（m、1 で原形、0 で頂と角を結ぶ直線 F 上）→
        前面の後退（r、唇先端から先は全量）→ 高さ（手前は y だけ D 倍、奥は背面の坂の足へ向けて D 倍に縮める）。"""
        pr = self.prof
        idx = np.atleast_1d(idx)
        P = self.P if P is None else P
        D = self.D[idx] if D is None else np.broadcast_to(D, idx.shape).astype(float)
        kap = self.kap[idx] if kap is None else np.broadcast_to(kap, idx.shape).astype(float)
        m = self.m[idx] if m is None else np.broadcast_to(m, idx.shape).astype(float)
        ret = self.ret[idx] if ret is None else np.broadcast_to(ret, idx.shape).astype(float)
        n = len(idx)
        A = np.repeat(P[None, :, 0], n, 0)
        Y = np.repeat(P[None, :, 1], n, 0)
        jt, jk = pr.j_top, pr.j_corner
        sl = slice(jt, jk + 1)
        ym = self.ymid if P is self.P else lip_midline(P, jt, pr.j_tip, jk)
        Ym = Y[:, sl] + (kap[:, None] * self.kap_w[None, sl]) * (ym[None, sl] - Y[:, sl])
        F = self.F
        A[:, sl] = F[None, :, 0] + m[:, None] * (A[:, sl] - F[None, :, 0])
        Y[:, sl] = F[None, :, 1] + m[:, None] * (Ym - F[None, :, 1])
        # 後退は、同じ高さの背面の坂との水平距離の retreat_wall_frac 倍を超えない（前面が背面を突き抜けない）
        if (ret > 0).any():
            ab_y = self.back_a_at(Y)
            room = np.maximum(A - ab_y, 0.0) * self.pf["retreat_wall_frac"]
            room = np.where(Y > 1e-6, room, np.inf)
            A = A - np.minimum(ret[:, None] * self.omega[None, :], room)
        far = self.c[idx] > 0
        ab = pr.a_bf
        sh = np.maximum(D, self.pf["far_shrink_floor"])
        A = np.where(far[:, None], ab + sh[:, None] * (A - ab), A)
        Y = Y * D[:, None]
        # 高さがほぼ 0 になる行では、断面の横位置を単調にする（平らになった面が自分に重なって裏返らないように）
        fl = smoothstep(D / self.pf["flatten_monotone_below_D"])[:, None]
        if (fl < 1).any():
            jb = pr.j_B
            Am = A.copy()
            for r in np.nonzero(fl[:, 0] < 1)[0]:
                Am[r, jb:] = monotone_redistribute(A[r, jb:])
            A = Am + fl * (A - Am)
        return A, Y

    def back_a_at(self, Y):
        """主断面の背面の坂（B：y = H0·smoothstep(u)、a = a_bf·(1 − u)）で、高さ Y の所の a。"""
        H0 = self.fr.H0
        yy = np.clip(Y / H0, 0.0, 1.0)
        # smoothstep の逆関数：u = 0.5 − sin(asin(1 − 2y)/3)
        u = 0.5 - np.sin(np.arcsin(np.clip(1.0 - 2.0 * yy, -1.0, 1.0)) / 3.0)
        return self.prof.a_bf * (1.0 - u)

    def project(self, idx, A, Y):
        X = self.fr.world(self.c[np.atleast_1d(idx)], A, Y)
        pp = self.fr.cam.project(X.reshape(-1, 3)).reshape(X.shape[0], X.shape[1], 3)
        return X, pp

    def sdf(self, idx, A, Y):
        X, pp = self.project(idx, A, Y)
        tg = self.tgt
        mg = self.pf["offframe_clamp_px"]
        valid = (Y > self.pf["check_min_y_m"]) & (pp[..., 2] > 1.0) & (pp[..., 0] >= tg.x0 - mg) & (pp[..., 0] <= tg.x1 + mg)
        s = tg.sample(pp[..., :2].reshape(-1, 2)).reshape(Y.shape)
        return np.where(valid, s, -1e9), pp

    def rowmax(self, idx, cols=None, **kw):
        A, Y = self.rows(idx, **kw)
        s, _ = self.sdf(idx, A, Y)
        if cols is not None:
            s = s[:, cols]
        return s.max(1)

    def bisect(self, idx, key, lo, hi, want, fixed, iters, cols=None):
        """行ごとの 1 変数の二分法。want='max' は収まる最大値、'min' は収まる最小値。収まらなければ安全側の端を返す。
        cols を渡すと、その列（例：唇の頂点だけ）のはみ出しだけで判定する（ほかの所のはみ出しは別の変数と逆畳み込みで扱う）。"""
        lo = np.broadcast_to(lo, idx.shape).astype(float).copy()
        hi = np.broadcast_to(hi, idx.shape).astype(float).copy()

        def ok(v):
            kw = dict(fixed)
            kw[key] = v
            return self.rowmax(idx, cols=cols, **kw) <= self.pf["fit_tol_px"]
        if want == "max":
            good_hi = ok(hi)
            a, b = lo.copy(), hi.copy()
            for _ in range(iters):
                mid = 0.5 * (a + b)
                o = ok(mid)
                a = np.where(o, mid, a)
                b = np.where(o, b, mid)
            return np.where(good_hi, hi, a), good_hi
        else:
            good_lo = ok(lo)
            good_hi = ok(hi)
            a, b = lo.copy(), hi.copy()
            for _ in range(iters):
                mid = 0.5 * (a + b)
                o = ok(mid)
                b = np.where(o, mid, b)
                a = np.where(o, a, mid)
            return np.where(good_lo, lo, b), good_hi

    def fit(self):
        """行の変形量を決める。唇（κ, m）と奥側の後退 r は c の滑らかな関数（設計値）、高さ D は許容領域に収まる最大値。"""
        pf = self.pf
        it = pf["bisect_iters"]
        cmx = pf["lip_collapse_max"]
        near = np.nonzero(self.near)[0]
        far = np.nonzero(self.far)[0]
        c = self.c
        sig = pf["smooth_rows"]
        info = {}
        # 唇の強さ λ(c)：波頂の行で 1、両側へガウス型に 0 へ。λ が 1→0.5 で厚みを潰し（κ: 0→κmax）、0.5→0 で頂と角を結ぶ直線 F へ縮める（m: 1→0）。
        # 唇の減り方の幅は像の上の距離で決める（解釈ごとに、唇の点が c 方向 1 m で像の上を動く量 rate_lip で割って m にする）
        pr = self.prof
        jl = np.arange(pr.j_top + 1, pr.j_corner, 5)
        Pl = self.P[jl]
        Xl = self.fr.world(np.array([0.0]), Pl[None, :, 0], Pl[None, :, 1])[0]
        cam = self.fr.cam
        rate_lip = float(np.median(np.linalg.norm(cam.project(Xl + 0.1 * self.fr.e[None, :])[:, :2] - cam.project(Xl)[:, :2], axis=1) / 0.1))
        sn = pf["lip_sigma_near_px"] / rate_lip
        sf = pf["lip_sigma_far_px"] / rate_lip
        self.lip_sigma_m = (sn, sf)
        lam = np.where(c < 0, np.exp(-(c / sn) ** 2), np.exp(-(c / sf) ** 2))
        self.lam = lam
        self.kap = cmx * np.clip(2.0 * (1.0 - lam), 0.0, 1.0)
        self.m = np.clip(2.0 * lam, 0.0, 1.0)
        # 奥側の前面の後退 r(c)：c0 までは 2 次、その先は傾き β の直線。壁の厚さの retreat_max_ratio_of_wall 倍で頭打ち。
        cf = np.maximum(c, 0.0)
        c0 = pf["retreat_c0_m"]
        # β は解釈ごとに像の上の速さから決める：内壁の点を c 方向へ 1 m 動かしたときの像の横移動と、−a 方向へ 1 m 動かしたときの
        # 横移動の比（内壁が右へずれる分を後退で打ち消すのに要る傾き）に、余裕 retreat_beta_margin を掛ける
        pr = self.prof
        jf = np.arange(pr.j_corner, pr.j_facebot + 1, 5)
        P0 = self.P[jf]
        X0 = self.fr.world(np.array([0.0]), P0[None, :, 0], P0[None, :, 1])[0]
        cam = self.fr.cam
        x0 = cam.project(X0)[:, 0]
        xc = cam.project(X0 + 0.1 * self.fr.e[None, :])[:, 0]
        xb = cam.project(X0 - 0.1 * self.fr.t[None, :])[:, 0]
        ratio = float(np.median((xc - x0) / np.maximum(x0 - xb, 1e-6)))
        beta = pf["retreat_beta_margin"] * ratio
        self.retreat_beta_used = beta
        self.image_rate_ratio = ratio
        self.ret = np.minimum(beta * np.where(cf < c0, cf * cf / (2 * c0), cf - c0 / 2), self.r_max)
        # ---- 手前の肩：唇のない状態で収まる最大の高さ D
        z = np.zeros(len(near))
        Dfit, _ = self.bisect(near, "D", 0.0, 1.0, "max", {"kap": np.full(len(near), cmx), "m": z, "ret": z}, it)
        Dn = np.minimum(self.D_design[near], Dfit)
        A1, Y1 = self.rows(near, D=Dn, kap=np.full(len(near), cmx), m=z, ret=z)
        _, pj1 = self.project(near, A1, Y1)
        inframe = pj1[:, self.prof.j_top, 0] >= self.tgt.x0
        i_edge = int(np.nonzero(inframe)[0][0]) if inframe.any() else len(near) - 1
        cn = c[near]
        c_edge = cn[i_edge]
        gap, Loff = pf["offframe_gap_m"], pf["offframe_decay_m"]
        Dn = Dn * np.exp(-(np.maximum(c_edge - gap - cn, 0.0) / Loff) ** 2)
        for i in range(len(Dn) - 2, -1, -1):
            if cn[i] < c_edge - gap:
                Dn[i] = min(Dn[i], Dn[i + 1])
        # 行ごとの二分法の揺れだけを取る軽い平滑化（安全側＝小さくへだけ。σ を大きくすると肩全体が下がる）
        Dn = np.minimum(gauss_rows(Dn, pf["near_D_smooth_rows"]), Dn)
        self.D[near] = Dn
        info["near_edge_row_c"] = float(c_edge)
        # ---- 奥側：唇を F まで縮めた状態で、唇以外の列が収まる最大の D（設計値以下、単調に減る。背面の坂の足へ向けて縮める）
        lipc = np.arange(self.prof.j_top + 1, self.prof.j_corner)
        nonlip = np.setdiff1d(np.arange(self.prof.nu), lipc)
        zf = np.zeros(len(far))
        Df = self.D_design[far].copy()
        nolip = self.m[far] < 0.05
        if nolip.any():
            fi = far[nolip]
            Dfit_f, _ = self.bisect(fi, "D", 0.0, self.D_design[fi], "max", {"kap": self.kap[fi], "m": self.m[fi], "ret": self.ret[fi]}, it)
            Df[nolip] = np.minimum(Df[nolip], Dfit_f)
        Df = np.minimum.accumulate(Df)
        Df = np.minimum(gauss_rows(Df, pf["near_D_smooth_rows"]), Df)
        self.D[far] = Df
        # ---- 唇：予定の強さ m（λ から）を上限に、唇の列が収まる最大の m を行ごとに求める（手前・奥とも。lip_row_fit のときだけ）
        rows_lip = np.concatenate([near, far]) if pf.get("lip_row_fit", False) else np.zeros(0, int)
        mm = self.m.copy()
        if len(rows_lip):
            m_s = self.m[rows_lip].copy()
            mfit, _ = self.bisect(rows_lip, "m", 0.0, m_s, "max", {"D": self.D[rows_lip], "kap": self.kap[rows_lip], "ret": self.ret[rows_lip]}, it, cols=lipc)
            mm[rows_lip] = mfit
        # 波頂から離れるほど単調に弱く（手前は c の減る向き、奥は増える向き）、安全側（小さく）へ平滑化
        vn = self.v_main
        mm[:vn] = np.minimum.accumulate(mm[:vn][::-1])[::-1]
        mm[vn + 1:] = np.minimum.accumulate(mm[vn + 1:])
        mm = np.minimum(gauss_rows(mm, 1.0), mm)
        mm[vn] = 1.0
        info["lip_m_reduced_rows"] = int(np.count_nonzero(mm < self.m - 1e-6))
        self.m = mm
        info["retreat_beta_used"] = float(beta)
        info["lip_image_rate_px_per_m"] = rate_lip
        info["lip_sigma_near_far_m"] = [float(sn), float(sf)]
        info["image_rate_c_over_back"] = float(ratio)
        info["far_retreat_reached_max_from_c"] = float(c[far][np.argmax(self.ret[far] >= self.r_max - 1e-9)]) if (self.ret[far] >= self.r_max - 1e-9).any() else None
        self.D[self.v_main] = 1.0
        return info

    def all_rows(self, P=None):
        return self.rows(np.arange(self.nv), P=P)


# ---------------------------------------------------------------- 逆畳み込み（主断面の輪郭部分）
def deconvolve(fam, prm, log=print):
    pr = fam.prof
    P0 = fam.P.copy()
    n0 = Profile.normals(P0)
    delta = np.zeros(pr.nu)
    drv = pr.driven
    idx = np.arange(fam.nv)
    eps = 0.02
    ker_sig = prm["smooth_sigma_samples"]
    hist = []
    best = (np.inf, delta.copy())
    for it in range(prm["iterations"]):
        P = P0 + delta[:, None] * n0
        A, Y = fam.rows(idx, P=P)
        s, _ = fam.sdf(idx, A, Y)
        # 輪郭部分（driven）は全行の像のうち最も外へ出る点が目標に接するように（包絡線）、ほかの列ははみ出しだけを消す
        E = s.max(0)
        vs = s.argmax(0)
        A2, Y2 = fam.rows(idx, P=P + eps * n0)
        s2, _ = fam.sdf(idx, A2, Y2)
        ar = np.arange(pr.nu)
        g = (s2[vs, ar] - s[vs, ar]) / eps
        gm = (s2[fam.v_main, ar] - s[fam.v_main, ar]) / eps
        valid = (E > -1e8) & (g < -2.0) & (np.abs(g) >= 0.5 * np.maximum(np.abs(gm), 2.0))
        Ed = np.where(drv, E, np.maximum(E, 0.0))
        st = np.where(valid, prm["gain"] * Ed / np.abs(np.where(valid, g, -1.0)), 0.0)
        st = np.clip(st, -prm["max_step_m"], prm["max_step_m"])
        st = gauss_rows(st, ker_sig)
        ev = E[drv & (E > -1e8)]
        score = max(float(np.abs(ev).max()), float(max(E[~drv].max(), 0.0)))
        if score < best[0]:
            best = (score, delta.copy())
        delta = np.clip(delta + st, -prm["delta_max_m"], prm["delta_max_m"])
        hist.append({"it": it, "E_driven_max_px": float(ev.max()), "E_driven_min_px": float(ev.min()),
                     "E_nondriven_max_px": float(E[~drv].max()), "delta_abs_max_m": float(np.abs(delta).max())})
    # いちばん良かった反復の δ を採る（最後の反復が悪化していても戻す）
    delta = best[1]
    # δ で主断面が小さく折り返した所（断面の自己交差）は、その近くの δ を平滑化して解く
    for _ in range(60):
        P = P0 + delta[:, None] * n0
        hit = section_crossings(P)
        if not hit:
            break
        for i, j in hit:
            for k in (i, j):
                lo, hi = max(k - 8, 0), min(k + 9, len(delta))
                delta[lo:hi] = gauss_rows(delta[lo:hi], 2.0)
    hist.append({"best_score_px": best[0]})
    P = P0 + delta[:, None] * n0
    return P, delta, hist


def section_crossings(P):
    """断面の折れ線 P の、隣り合わない線分どうしの交差（線分添字の組）。"""
    p, q = P[:-1], P[1:]
    dd = q - p
    dx = dd[:, None, :]
    ex = dd[None, :, :]
    w = p[None, :, :] - p[:, None, :]
    den = dx[..., 0] * ex[..., 1] - dx[..., 1] * ex[..., 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (w[..., 0] * ex[..., 1] - w[..., 1] * ex[..., 0]) / den
        t = (w[..., 0] * dx[..., 1] - w[..., 1] * dx[..., 0]) / den
    hit = (np.abs(den) > 1e-12) & (s > 1e-9) & (s < 1 - 1e-9) & (t > 1e-9) & (t < 1 - 1e-9)
    ii, jj = np.nonzero(np.triu(hit, 2))
    return list(zip(ii.tolist(), jj.tolist()))


# ---------------------------------------------------------------- 投影固定と TPS
def tps_solve(ctrl, vals, reg=1e-6):
    n = len(ctrl)
    d = np.linalg.norm(ctrl[:, None, :] - ctrl[None, :, :], axis=-1)
    K = np.where(d > 0, d * d * np.log(np.maximum(d, 1e-12)), 0.0)
    Pm = np.hstack([np.ones((n, 1)), ctrl])
    M = np.zeros((n + 3, n + 3))
    M[:n, :n] = K + reg * np.eye(n)
    M[:n, n:] = Pm
    M[n:, :n] = Pm.T
    rhs = np.zeros((n + 3, vals.shape[1]))
    rhs[:n] = vals
    sol = np.linalg.solve(M, rhs)
    return sol[:n], sol[n:]


def tps_eval(ctrl, w, aff, q, chunk=4000):
    out = np.zeros((len(q), w.shape[1]))
    for k in range(0, len(q), chunk):
        qq = q[k:k + chunk]
        d = np.linalg.norm(qq[:, None, :] - ctrl[None, :, :], axis=-1)
        K = np.where(d > 0, d * d * np.log(np.maximum(d, 1e-12)), 0.0)
        out[k:k + chunk] = K @ w + np.hstack([np.ones((len(qq), 1)), qq]) @ aff
    return out


def snap_tps(fam, A, Y, prm, log=print):
    """シルエット頂点（補正後の目標から band_px 以内、はみ出しを含む）を断面の面内の法線方向へ動かして SDF = 0（目標の射線上）に置き、
    その移動量を (σ, c) 空間の TPS で内部へ広げる。"""
    idx = np.arange(fam.nv)
    pr = fam.prof
    sig_u = arclen(fam.P)
    stats = []
    tot = np.zeros(A.shape + (2,))
    rowh = np.maximum(Y.max(1), 1.0)
    # 鋭い角（爪の包絡のくぼみの頂点、唇先など、主断面で隣の線分との向きが sharp_turn_deg 以上変わる列）と唇先の近くは、
    # 断面内の法線が定まらず行ごとに向きが揺れて面が折り返すので、貼り付けに使わない（逆畳み込みの位置のまま）
    Pm = fam.P
    dP = np.diff(Pm, axis=0)
    angP = np.degrees(np.abs((np.arctan2(dP[1:, 1], dP[1:, 0]) - np.arctan2(dP[:-1, 1], dP[:-1, 0]) + np.pi) % (2 * np.pi) - np.pi))
    sharp_cols = sorted(set((np.nonzero(angP >= prm.get("sharp_turn_deg", 35.0))[0] + 1).tolist() + list(pr.knot_cols) + [pr.j_tip]))
    for rnd in range(prm["rounds"]):
        s, pj = fam.sdf(idx, A, Y)
        Pn = np.stack([A, Y], -1)
        d = np.gradient(Pn, axis=1)
        d /= np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-12)
        n = np.stack([d[..., 1], -d[..., 0]], -1)
        eps = 0.01
        s2, _ = fam.sdf(idx, A + eps * n[..., 0], Y + eps * n[..., 1])
        g = (s2 - s) / eps
        # 面内の法線方向に動かしても像がほとんど動かない頂点（法線が視線に沿う所）は貼り付けに使わない（|g| ≥ g_min_px_per_m）
        inframe = (pj[..., 0] >= fam.tgt.x0 - 2) & (pj[..., 0] <= fam.tgt.x1 + 2) & (pj[..., 1] >= -2) & (pj[..., 1] <= 1081)
        gok = (s > -1e8) & (g < -prm.get("g_min_px_per_m", 10.0)) & inframe
        for kc in sharp_cols:
            gok[:, max(kc - 3, 0):kc + 4] = False
        gok[:, max(pr.j_tip - 6, 0):pr.j_tip + 7] = False
        sel = (s > -prm["band_px"]) & gok
        # 主断面の輪郭部分（原画の外輪郭・内輪郭を逆投影した所）は、内側に残っていても必ず目標の射線上へ貼り付ける（被覆の保証）
        mainsel = np.zeros_like(sel)
        mainsel[fam.v_main, pr.driven] = True
        mainsel &= gok
        sel |= mainsel
        dd = np.where(sel, s / np.abs(np.where(sel, g, -1.0)), 0.0)        # 内向きへ動かす量（m）
        cap = np.where(mainsel, prm.get("snap_main_max_m", 0.5), prm.get("snap_max_m", 0.1))
        dd = np.clip(dd, -cap, cap)
        disp = dd[..., None] * n
        vv, jj = np.nonzero(sel)
        # アンカー：格子の縁と、輪郭から遠い頂点の粗い格子（移動 0）
        gu, gv = prm["anchor_grid"]
        ju = np.linspace(0, pr.nu - 1, gu).round().astype(int)
        jv = np.linspace(0, fam.nv - 1, gv).round().astype(int)
        av, aj = np.meshgrid(jv, ju, indexing="ij")
        av, aj = av.ravel(), aj.ravel()
        far_ok = (s[av, aj] < -20.0) | (s[av, aj] < -1e8) | (av == 0) | (av == fam.nv - 1) | (aj == 0) | (aj == pr.nu - 1)
        av, aj = av[far_ok], aj[far_ok]
        # 制御点は (σ, c) の 0.5 m 格子ごとに 1 点へ間引く（近すぎる点どうしの食い違いで TPS が振動しないように）
        cell = prm.get("ctrl_cell_m", 0.5)
        key = np.stack([np.floor(sig_u[jj] / cell), np.floor(fam.c[vv] / cell)], -1)
        _, first = np.unique(key, axis=0, return_index=True)
        vc, jc = vv[first], jj[first]
        ctrl = np.vstack([np.stack([sig_u[jc], fam.c[vc]], -1), np.stack([sig_u[aj], fam.c[av]], -1)])
        vals = np.vstack([disp[vc, jc], np.zeros((len(av), 2))])
        _, uidx = np.unique(np.round(ctrl / cell), axis=0, return_index=True)
        uidx = np.sort(uidx)
        ctrl, vals = ctrl[uidx], vals[uidx]
        if len(vv) == 0:
            stats.append({"round": rnd, "n_silhouette": 0})
            break
        reg = prm.get("tps_reg", 0.1)
        w, aff = tps_solve(ctrl, vals, reg)
        q = np.stack(np.meshgrid(sig_u, fam.c), -1).reshape(-1, 2)   # (nv*nu, 2): (σ_j, c_v)
        field = tps_eval(ctrl, w, aff, q).reshape(fam.nv, pr.nu, 2)
        # TPS の広がりはシルエット頂点の近く（(σ, c) で falloff_m 程度）に限る（輪郭から遠い所は動かさない）
        sil_pts = np.stack([sig_u[jj], fam.c[vv]], -1)
        dmin = np.full(q.shape[0], np.inf)
        for k0 in range(0, len(sil_pts), 2000):
            dd2 = np.linalg.norm(q[:, None, :] - sil_pts[None, k0:k0 + 2000, :], axis=-1).min(1)
            dmin = np.minimum(dmin, dd2)
        fall = np.exp(-(dmin / prm.get("falloff_m", 2.0)) ** 2).reshape(fam.nv, pr.nu, 1)
        field = field * fall
        # 平らな海（y≈0）と、輪郭の近く（像が補正後の目標から lock_px 以内）でシルエットでない頂点は動かさない
        # （TPS が隣の行の貼り付けを広げて、別の所で輪郭をつくっている頂点を内側へ引き込まないように）
        flat = Y <= fam.pf["check_min_y_m"]
        near_sil = (s > -prm.get("lock_px", 8.0)) & ~sel
        field[flat | near_sil] = 0.0
        field[sel] = disp[sel]       # シルエット頂点は厳密に貼り付ける
        An = A + field[..., 0]
        Yn = Y + field[..., 1]
        # 貼り付けで断面が折り返した所は、交差した線分の近くの頂点の移動だけをやめる（記録する）
        undone = 0
        for v in range(fam.nv):
            if section_crossings(np.stack([A[v], Y[v]], -1)):
                continue
            for _ in range(40):
                hit = section_crossings(np.stack([An[v], Yn[v]], -1))
                if not hit:
                    break
                for i, j in hit:
                    for kk in (i, j):
                        lo, hi = max(kk - 3, 0), min(kk + 5, pr.nu)
                        An[v, lo:hi], Yn[v, lo:hi] = A[v, lo:hi], Y[v, lo:hi]
                        field[v, lo:hi] = 0.0
                        undone += hi - lo
            else:
                An[v], Yn[v] = A[v], Y[v]
                field[v] = 0.0
        A, Y = An, Yn
        tot += field
        ratio = np.linalg.norm(field, axis=-1) / rowh[:, None]
        stats.append({"round": rnd, "n_silhouette": int(sel.sum()), "n_ctrl": int(len(ctrl)),
                      "snap_abs_max_m": float(np.abs(dd[sel]).max()), "snap_abs_max_px": float(np.abs(s[sel]).max()),
                      "field_abs_max_m": float(np.linalg.norm(field, axis=-1).max()), "field_ratio_max": float(ratio.max()),
                      "vertices_undone_for_crossing": int(undone)})
    total_ratio = np.linalg.norm(tot, axis=-1) / rowh[:, None]
    return A, Y, stats, float(np.linalg.norm(tot, axis=-1).max()), float(total_ratio.max())


# ---------------------------------------------------------------- メッシュ・検査
def triangles(nu, nv):
    iu, iv = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1))
    a = (iv * nu + iu).ravel()
    b = ((iv + 1) * nu + iu).ravel()
    c = (iv * nu + iu + 1).ravel()
    d = ((iv + 1) * nu + iu + 1).ravel()
    # 番号24 と同じ順（平らな海で上 +Y が表）
    return np.stack([np.stack([a, b, c], -1), np.stack([c, b, d], -1)], 1).reshape(-1, 3).astype(np.int32)


def mesh_checks(X, tris, A, Y, nv, nu):
    V = X.reshape(-1, 3)
    p0, p1, p2 = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
    fn = np.cross(p1 - p0, p2 - p0)
    area = 0.5 * np.linalg.norm(fn, axis=1)
    flat = (np.abs(p0[:, 1]) < 1e-6) & (np.abs(p1[:, 1]) < 1e-6) & (np.abs(p2[:, 1]) < 1e-6)
    si = G0.self_intersections(A, Y)
    el = np.concatenate([np.linalg.norm(p1 - p0, axis=1), np.linalg.norm(p2 - p1, axis=1), np.linalg.norm(p0 - p2, axis=1)])
    return {
        "vertex_count": int(len(V)), "triangle_count": int(len(tris)),
        "nan": int(np.count_nonzero(~np.isfinite(V))),
        "degenerate_triangles_area_lt_1e-6_m2": int(np.count_nonzero(area < 1e-6)),
        "min_triangle_area_m2": float(area.min()), "min_edge_m": float(el.min()),
        "flat_sea_triangles_facing_down": int(np.count_nonzero(flat & (fn[:, 1] < 0))),
        "section_self_intersections_total": int(sum(si)), "section_self_intersection_rows": [i for i, k in enumerate(si) if k > 0],
    }


def write_gwb(path, nu, nv, uv, uv2, tris, X):
    with open(path, "wb") as fo:
        fo.write(MAGIC + struct.pack("<iiiifii", FORMAT_VERSION, nu, nv, 1, 30.0, 0, len(tris)))
        for arr in (uv.astype(np.float32), uv2.astype(np.float32), tris.astype(np.int32), X.reshape(-1, 3).astype(np.float32)):
            fo.write(np.ascontiguousarray(arr).tobytes())


def write_obj(path, X, uv, tris, header):
    V = X.reshape(-1, 3)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for h in header:
            f.write("# %s\n" % h)
        f.write("o kstar\n")
        f.write("".join("v %.6f %.6f %.6f\n" % tuple(p) for p in V))
        f.write("".join("vt %.7f %.7f\n" % tuple(t) for t in uv))
        f.write("".join("f %d/%d %d/%d %d/%d\n" % (a + 1, a + 1, b + 1, b + 1, c + 1, c + 1) for a, b, c in tris))


def rasterize(cam, X, tris, ss=2):
    Pp = cam.project(X.reshape(-1, 3))
    W, H = cam.W * ss, cam.H * ss
    xy = (Pp[:, :2] + 0.5) * ss - 0.5
    ok = Pp[:, 2] > 0.5
    img = np.zeros((H, W), np.uint8)
    ip = np.round(xy * 16).astype(np.int32)
    tv = ok[tris].all(1)
    for tri in ip[tris[tv]]:
        cv2.fillConvexPoly(img, tri, 255, lineType=cv2.LINE_8, shift=4)
    return (img > 0).astype(np.float64).reshape(cam.H, ss, cam.W, ss).mean((1, 3))


def preview_metrics(fr, tgt, X, tris, out_png, title):
    import evaluate as E
    cam = fr.cam
    cov = rasterize(cam, X, tris)
    seacov, yh = G0.sea_horizon_cover(cam, tgt.spec)
    other = np.maximum(cov, seacov)
    truth = E.Truth()
    reg = {"sky": 1.0 - other, "boat_left": np.zeros_like(cov), "boat_mid": np.zeros_like(cov), "boat_fg": np.zeros_like(cov)}
    m, det, rp = E.evaluate_core(truth, truth.disp_rgb, reg, versions=("envelope",), contour_judged=True)
    res = {}
    for k in ("78", "130", "131", "132", "72", "71"):
        for me in m["items"].get(k, {}).get("measures", []):
            if me.get("version") == "envelope":
                res[k] = {"max_px": me["value_max_px"], "p95_px": me["p95_px"], "worst_xy": me.get("worst_display_xy")}
    img = (truth.disp_rgb * 0.5 + np.dstack([other * 60, other * 90, other * 140]) * 0.5).astype(np.uint8)
    E.overlay_png(truth, img, det, rp, out_png, title, ("envelope",))
    return res


# ---------------------------------------------------------------- 参照比率（Q5）の自己検査（記録のみ）
def section_ratios(A_row, Y_row, pr, H):
    """1 行の断面で、0.5H の壁の厚さ、0.3H の内壁から唇先までの張り出し、唇先から 0.75 m 奥の鉛直の唇の厚さを測る。"""
    P = np.stack([A_row, Y_row], -1)

    def hits(yv, j0, j1):
        out = []
        for k in range(j0, j1):
            y0, y1 = P[k, 1], P[k + 1, 1]
            if (y0 - yv) * (y1 - yv) <= 0 and y0 != y1:
                t = (yv - y0) / (y1 - y0)
                out.append(P[k, 0] + t * (P[k + 1, 0] - P[k, 0]))
        return out
    jt, jk, jp, jf = pr.j_top, pr.j_corner, pr.j_tip, pr.j_facebot + pr.nu - pr.j_E
    back = hits(0.5 * H, pr.j_B, pr.j_top)
    # 0.5H の水平線が背面の坂の次に断面を横切る所（内壁、または角の近くの唇の下側）までを壁の厚さとする
    front = [x for x in hits(0.5 * H, pr.j_top, pr.j_E) if back and x > max(back)]
    wall = (min(front) - max(back)) if (back and front) else None
    face03 = hits(0.3 * H, pr.j_corner, pr.j_E)
    a_tip = float(P[jt:jk + 1, 0].max())
    over = (a_tip - min(face03)) if face03 else None
    at = a_tip - 0.75
    up, lo = [], []
    for k in range(jt, jk):
        a0, a1 = P[k, 0], P[k + 1, 0]
        if (a0 - at) * (a1 - at) <= 0 and a0 != a1:
            t = (at - a0) / (a1 - a0)
            yv = P[k, 1] + t * (P[k + 1, 1] - P[k, 1])
            (up if k < jp else lo).append(yv)
    lip_t = (min(up) - max(lo)) if (up and lo) else None
    return {"H_m": float(H), "wall_at_half_H_m": wall, "wall_over_H": (wall / H) if wall is not None else None,
            "lip_tip_a_m": a_tip, "overhang_face03_to_tip_m": over, "overhang_over_H": (over / H) if over is not None else None,
            "lip_vertical_thickness_0p75m_behind_tip_m": lip_t}


# ---------------------------------------------------------------- 1 解釈を作る
def build(key, iprm, params, tgt, out_dir, log=print):
    t0 = time.time()
    alpha = float(iprm["alpha_deg"])
    fr = Frame(tgt.spec, alpha, params["anchor"], tgt)
    prof = Profile(fr, tgt, params["profile"])
    fam = Family(fr, prof, tgt, params["rows"], params["fit"])
    P_init = prof.P.copy()
    info1 = fam.fit()
    log("[%s] fit %.1fs" % (key, time.time() - t0))
    P, delta, hist = deconvolve(fam, params["deconvolution"], log)
    fam.set_profile(P)
    info2 = fam.fit()          # 主断面が変わったので行をもう一度合わせる
    P, delta2, hist2 = deconvolve(fam, params["deconvolution"], log)
    delta = delta + delta2
    fam.set_profile(P)
    log("[%s] deconvolution %.1fs  best score %.2f px" % (key, time.time() - t0, hist2[-1]["best_score_px"]))
    A, Y = fam.all_rows()
    A, Y, snap_stats, tps_max_m, tps_ratio = snap_tps(fam, A, Y, params["snap_tps"], log)
    A0u, Y0u = A.copy(), Y.copy()
    A, Y, untangled = untangle_rows(A, Y)
    # 主断面の輪郭の頂点（目標の射線上へ貼り付けた頂点）は動かさずに、近くの三角形の交差を解く。
    # 解いた後に隣の行の頂点が目標の外へ出たら内側へ戻し（はみ出しの除去）、もう一度交差を調べる。
    locked = np.zeros_like(A, bool)
    locked[fam.v_main, prof.driven] = True
    si_hist, si_move = [], 0.0
    for rnd in range(4):
        A, Y, h_, mv_ = fix_self_intersections(fr, fam.c, A, Y, locked=locked)
        si_hist += h_
        si_move = max(si_move, mv_)
        A, Y, npoke = push_in_pokes(fam, A, Y, locked, params["snap_tps"])
        si_hist.append("poke:%d" % npoke)
        if npoke == 0 and h_[-1] == 0:
            break
    # 最後にもう一度交差を解き、それでも残るときだけ主断面の頂点も含めて平滑化する（記録する）
    A, Y, h_, mv_ = fix_self_intersections(fr, fam.c, A, Y, locked=locked)
    si_hist += h_
    si_move = max(si_move, mv_)
    if h_[-1] > 0:
        A, Y, h_, mv_ = fix_self_intersections(fr, fam.c, A, Y, locked=None)
        si_hist += ["unlocked"] + h_
        si_move = max(si_move, mv_)
    log("[%s] local self-intersections %s (move %.3f m)" % (key, si_hist, si_move))
    A, Y, untangled2 = untangle_rows(A, Y)
    untangled.update(untangled2)
    untangle_move = float(np.hypot(A - A0u, Y - Y0u).max())
    log("[%s] snap+TPS %.1fs  field max %.3f m (ratio %.4f)" % (key, time.time() - t0, tps_max_m, tps_ratio))
    X = fr.world(fam.c, A, Y)
    nu, nv = prof.nu, fam.nv
    tris = triangles(nu, nv)
    s_u = arclen(fam.P)
    uv = np.stack(np.meshgrid(s_u / s_u[-1], (fam.c - fam.c[0]) / (fam.c[-1] - fam.c[0])), -1).reshape(-1, 2)
    uv2 = np.stack(np.meshgrid(s_u, fam.c), -1).reshape(-1, 2)
    checks = mesh_checks(X, tris, A, Y, nv, nu)
    s_fin, pj_fin = fam.sdf(np.arange(nv), A, Y)
    checks["final_vertex_sdf_max_px"] = float(s_fin.max())
    inf = (pj_fin[..., 0] >= tgt.x0) & (pj_fin[..., 0] <= tgt.x1) & (pj_fin[..., 1] >= 0) & (pj_fin[..., 1] <= 1079)
    checks["final_vertex_sdf_max_px_in_frame"] = float(np.where(inf, s_fin, -1e9).max())
    checks["note_ja"] = "final_vertex_sdf_max_px は画面の外（採点列の左右 400 px まで、採点列の端の列で評価）も含む。in_frame は PaintingCam の画面内の頂点だけ。"
    # 行ごとの頂（波峰線）と高さ
    jtop = np.argmax(Y, axis=1)
    crest = X[np.arange(nv), jtop]
    crest_h = Y.max(1)
    peak = float(crest_h.max())
    above = fam.c[crest_h > 0.5 * peak]
    # 波峰線の平面図の接線と断面の法線 e のなす角（断面が波峰線に垂直かの記録）
    live = crest_h > 0.5
    body = crest_h > 0.5 * crest_h.max()
    cv = X[:, prof.j_top]                      # 主断面の頂の頂点の列（波峰線）
    # 行の間隔が 2 cm ほどの所もあるので、c 方向に ±1 m 離れた点との差で接線をとる（mm 単位の貼り付けの動きで角度が暴れないように）
    cxz = cv[:, [0, 2]]
    lo_i = np.clip(np.searchsorted(fam.c, fam.c - 1.0), 0, fam.nv - 1)
    hi_i = np.clip(np.searchsorted(fam.c, fam.c + 1.0), 0, fam.nv - 1)
    dcr = cxz[hi_i] - cxz[lo_i]
    e2 = fr.e[[0, 2]]
    ang = np.degrees(np.arccos(np.clip(np.abs(dcr @ e2) / np.maximum(np.linalg.norm(dcr, axis=1), 1e-9), 0, 1)))
    ratios_main = section_ratios(A[fam.v_main], Y[fam.v_main], prof, crest_h[fam.v_main])
    lip_rows = np.nonzero((fam.m > 0.5) & (fam.kap < 0.5))[0]
    lip_t = [section_ratios(A[v], Y[v], prof, crest_h[v])["lip_vertical_thickness_0p75m_behind_tip_m"] for v in lip_rows]
    lip_t = [v for v in lip_t if v is not None]
    os.makedirs(out_dir, exist_ok=True)
    gwb = os.path.join(out_dir, "kstar_%s.gwb" % key)
    obj = os.path.join(out_dir, "kstar_%s.obj" % key)
    write_gwb(gwb, nu, nv, uv, uv2, tris, X)
    np.savez_compressed(os.path.join(out_dir, "kstar_%s_rows.npz" % key), A=A, Y=Y, c=fam.c, P=fam.P, P_init=P_init)
    write_obj(obj, X, uv, tris, ["gw_wavegen v1 K* %s (alpha %.0f deg), Unity world coordinates (left-handed, Y up, metres)" % (key, alpha),
                                 "vertex index = row * %d + column; row = crest-line section (c), column = section arc (sigma)" % nu,
                                 "vt = (sigma / sigma_total, (c - c_min) / (c_max - c_min))"])
    prev_dir = os.path.join(out_dir, "preview")
    os.makedirs(prev_dir, exist_ok=True)
    prev = preview_metrics(fr, tgt, X, tris, os.path.join(prev_dir, "kstar_%s_numpy_overlay.png" % key),
                           "26 gw_wavegen v1 %s numpy preview at t* (not Unity)" % key)
    log("[%s] preview %s (%.1fs)" % (key, json.dumps({k: v["max_px"] for k, v in prev.items()}), time.time() - t0))
    meta = {
        "schema": "GreatWave.GWWaveGen.kstar_meta/1", "generator": "gw_wavegen v1", "number": "26", "key": key,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "alpha_deg": alpha, "interpretation_ja": params["interpretation_definition_ja"],
        "files": {"gwb": os.path.basename(gwb), "gwb_sha256": T.sha256_file(gwb), "gwb_bytes": os.path.getsize(gwb),
                  "obj": os.path.basename(obj), "obj_sha256": T.sha256_file(obj), "obj_bytes": os.path.getsize(obj)},
        "format_ja": "gwb は番号24 と同じ GWW0 書式（先頭 32 バイト = 'GWW0' + int32 版 1, nu, nv, フレーム数 1, float32 fps 30, int32 t* フレーム 0, 三角形数。続いて UV (N×2 float32)、UV2 (N×2 float32)、三角形 (M×3 int32)、頂点位置 (N×3 float32、Unity ワールド座標 m)）。N = nu×nv、頂点添字 = 行×nu + 列。",
        "uv_layout_ja": "UV0 = (σ/σ_total, (c − c_min)/(c_max − c_min))。σ は主断面 P0 の弧長（全行で同じ列は同じ σ）、c は波峰線方向の断面位置（m、負がカメラ側の手前の肩）。u は後ろの平らな海（0）→ 背面の坂 → 頂 → 唇の上側 → 唇先端 → 唇の下側 → 内壁 → 谷 → 前の平らな海（1）、v は手前の端（0）→ 奥の端（1）。UV2 = (σ [m], c [m])。",
        "nu": nu, "nv": nv, "vertex_count": nu * nv, "triangle_count": int(len(tris)),
        "frame": {"e_crest": fr.e.tolist(), "t_travel": fr.t.tolist(), "h": fr.h.tolist(), "ea": fr.ea.tolist(),
                  "anchor_crest_top_world": fr.A.tolist(), "section_origin_world": fr.O0.tolist(), "H0_m": fr.H0,
                  "crest_top_display_px": fr.top_display.tolist()},
        "profile": {"index": {"j_B": prof.j_B, "j_top": prof.j_top, "j_tip": prof.j_tip, "j_corner": prof.j_corner, "j_facebot": prof.j_facebot, "j_E": prof.j_E},
                    "a_back_foot_m": prof.a_bf, "a_face_at_half_H_m": prof.a_face_half,
                    "P0_final": np.round(fam.P, 5).tolist(), "P0_initial": np.round(P_init, 5).tolist(),
                    "deconvolution_delta_abs_max_m": float(np.abs(delta).max()),
                    "deconvolution_delta_over_H0": float(np.abs(delta).max() / fr.H0)},
        "rows": {"c_m": np.round(fam.c, 5).tolist(), "D": np.round(fam.D, 5).tolist(), "kappa_lip_collapse": np.round(fam.kap, 5).tolist(),
                 "m_lip_extent": np.round(fam.m, 5).tolist(), "retreat_m": np.round(fam.ret, 5).tolist(), "main_row": fam.v_main,
                 "retreat_max_m": fam.r_max, "fit_info": {"pass1": {k: v for k, v in info1.items() if k != "near_D_fit_raw"},
                                                          "pass2": {k: v for k, v in info2.items() if k != "near_D_fit_raw"}}},
        "crest_line": {"peak_height_m": peak, "above_half_peak_c_range_m": [float(above.min()), float(above.max())],
                       "above_half_peak_length_m": float(above.max() - above.min()),
                       "above_half_peak_length_over_H": float((above.max() - above.min()) / peak),
                       "crest_world_every_10_rows": np.round(crest[::10], 3).tolist(),
                       "crest_vertex_line_note_ja": "波峰線は各行の頂の頂点（主断面 P0 の頂 j_top）の列。断面の法線 e と、その平面図での接線のなす角を記録する",
                       "section_normal_vs_crest_tangent_deg_max_body_rows": float(ang[body].max()) if body.any() else None,
                       "section_normal_vs_crest_tangent_deg_max_live_rows": float(ang[live].max()) if live.any() else None,
                       "section_normal_vs_crest_tangent_deg_p95_live_rows": float(np.percentile(ang[live], 95)) if live.any() else None,
                       "rows_over_10deg_c_m": [float(v) for v in fam.c[live & (ang > 10.0)]][:60]},
        "reference_ratios_self_check_record_only": {"main_row": ratios_main,
                                                    "lip_vertical_thickness_min_over_lip_rows_m": float(min(lip_t)) if lip_t else None,
                                                    "lip_rows_count": int(len(lip_rows))},
        "deconvolution_history_last": hist2[-2:], "snap_tps": {"rounds": snap_stats, "total_field_abs_max_m": tps_max_m,
                                                              "total_field_over_local_size_max": tps_ratio,
                                                              "cap_ratio": params["snap_tps"]["cap_ratio"],
                                                              "within_cap": bool(tps_ratio <= params["snap_tps"]["cap_ratio"])},
        "checks": checks, "untangle": {"rows_fixed": {str(k): v for k, v in untangled.items()}, "max_move_m": untangle_move,
                                       "local_self_intersection_vertices_per_iteration": si_hist,
                                       "note_ja": "断面の小さな折り返しを近くの頂点の平滑化で解いた行と反復回数、最大移動量"},
        "corner_knots_arc_m": prof.corner_knots,
        "numpy_preview_envelope": prev, "seconds": time.time() - t0,
    }
    T.save_json(os.path.join(out_dir, "kstar_%s_meta.json" % key), meta)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--only", default=None)
    ap.add_argument("--summary-only", action="store_true", help="書き出し済みの meta から kstar_summary.json だけを作り直す（解釈ごとに並列で作ったとき）")
    a = ap.parse_args()
    params = T.load_json(a.params)
    tgt = None if a.summary_only else Target()
    keys = [a.only] if a.only else list(params["interpretations"].keys())
    inputs = [os.path.abspath(a.params), T.SPEC_PATH, os.path.join(HERE, "gw_wavegen_v1.py"), os.path.join(HERE, "gw_wavegen.py"),
              os.path.join(REPO, "Tools", "PaintingTruth", "truthlib.py")] + [T.repo_abs(v) for k, v in params["inputs"].items()]
    summary = {"generator": "gw_wavegen v1", "inputs_sha256": {T.repo_rel(p): T.sha256_file(p) for p in inputs},
               "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__}, "interpretations": {}}
    for k in keys:
        meta = T.load_json(os.path.join(a.out, "kstar_%s_meta.json" % k)) if a.summary_only else build(k, params["interpretations"][k], params, tgt, a.out)
        summary["interpretations"][k] = {"meta": "kstar_%s_meta.json" % k, "gwb_sha256": meta["files"]["gwb_sha256"],
                                         "obj_sha256": meta["files"]["obj_sha256"], "numpy_preview_envelope": meta["numpy_preview_envelope"]}
    if not a.only:
        T.save_json(os.path.join(a.out, "kstar_summary.json"), summary)
    print("KSTAR_DONE", json.dumps({k: {kk: vv["max_px"] for kk, vv in v["numpy_preview_envelope"].items()} for k, v in summary["interpretations"].items()}))


if __name__ == "__main__":
    main()
