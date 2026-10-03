# -*- coding: utf-8 -*-
"""美術の見本01 B（原画のような舌形）：主役波 K*′ P28R2rec の面の座標 (U, V) = 部 A の (u, w)（m。u は巻きの向きの弧長で頂の列 0・唇と前面の側が正、
w は頂に並ぶ向きで |∇w| ≈ 1）の上に、太い藍濃の舌と藍中の線、淡い水色の爪の帯、白い頂を「設計」し、符号付きの距離（m）のテクスチャに焼く。
原画の色を面へ写さない（投影なし）。原画は、設計の数（線の向き・間隔・帯の境）を合わせる目的関数の相手としてだけ使う。

設計の作り（どれも面の座標の上）：
  1) 舌の並びの位相の場 φ(U, V)：藍中の線の中心が φ の整数の等値線。
     目標の勾配の場 G(U, V) を作り、∇φ ≈ G となめらかさ（2 階の差分）の最小二乗で φ を解く（整数の割り当ては要らない）。
     G は、原画視点で原画の藍中の線（色区から読んだ中心の点列）の向きと間隔を、画素から面への写像のヤコビ行列で面の上の向きと間隔（m）に直したもの
     （写像が斜めすぎる画素は使わない・重みを下げる）を、半径 σ の重みで面の座標の上に広げ、データの無い所は事前の (0, 1/λ0)（w の等値線＝巻きの向き、
     間隔 λ0）へ戻したもの。最後に、原画の線の点で cos 2πφ の和が最大になるよう位相を一つずらす。
     → 原画視点で見える所は原画の線の向き・密度に近く、見えない所は巻きの向きにそろった一様な線（どの視点からも一続き）。
  2) 爪の帯（白い頂の前の縁）：原画視点の原画の白の頂・爪の輪・藍の面を、V（w）ごとの U（u）の境 U_cz0（白 → 淡い水色）・U_cz1（淡い水色 → 藍の舌）
     として数え、V に沿う罰則つきの平滑化で決める（見えない V は既定の F の値。白の終わりは頂から 0.5〜9 m、帯の幅は 1〜5 m に切る）。
  3) 舌：藍濃は、藍中の線（線ごとに太さが違い、下で細って終わる。幅は面の上の m：|∇φ| を 3 次元の三角形で測る）の外で、
     爪の帯の縁 U_cz1 + t_m（舌ごとにずらす）より下。角は半径 R の円で丸める（舌の先が丸い）。
  4) 白い点：藍濃の中に、面の上で m の大きさの点。
出力（--out）：s01b_design_f16.bin（行 = U、列 = V、RGBA = 白・淡い水色・藍濃・点の符号付きの距離 m、half）、s01b_design.json、
  s01b_attr_f32.bin（頂点ごと 12 float。仕上げ29 の面の座標の B.z・B.w を U・V に置き換えたもの。S01B の材質が読む）、図。"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from PIL import Image
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s01b_common as S
import s01b_param as P

WORK = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/work/"


def smooth_curve(vals, wts, default, lam_s, w_def):
    """1 次元の罰則つきの平滑化：Σ w (x − vals)² + w_def (x − default)² + lam_s Σ (Δ² x)²"""
    n = len(vals)
    W = sp.diags(wts + w_def)
    rhs = wts * np.nan_to_num(vals) + w_def * default
    D2 = sp.diags([np.ones(n - 2), -2 * np.ones(n - 2), np.ones(n - 2)], [0, 1, 2], shape=(n - 2, n))
    A = W + lam_s * (D2.T @ D2)
    return spla.spsolve(A.tocsc(), rhs)


def bilinear_weights(gu, gv, U0, V0, hp, nU, nV):
    fu = (gu - U0) / hp
    fv = (gv - V0) / hp
    i0 = np.clip(np.floor(fu).astype(np.int64), 0, nU - 2)
    j0 = np.clip(np.floor(fv).astype(np.int64), 0, nV - 2)
    a = np.clip(fu - i0, 0, 1)
    b = np.clip(fv - j0, 0, 1)
    idx = np.stack([i0 * nV + j0, i0 * nV + j0 + 1, (i0 + 1) * nV + j0, (i0 + 1) * nV + j0 + 1], 1)
    w = np.stack([(1 - a) * (1 - b), (1 - a) * b, a * (1 - b), a * b], 1)
    return idx, w


def sample_grid(G, gu, gv, U0, V0, hp):
    nU, nV = G.shape
    idx, w = bilinear_weights(gu, gv, U0, V0, hp, nU, nV)
    return (G.ravel()[idx] * w).sum(1)


def round_intersect(a, b, R):
    """二つの「正が内」の距離の交わり（min）の角を半径 R の円で丸める（正が内）。"""
    qa = np.maximum(R - a, 0.0)
    qb = np.maximum(R - b, 0.0)
    out = np.minimum(a, b)
    both = (a < R) & (b < R)
    return np.where(both, R - np.sqrt(qa * qa + qb * qb), out)


def tri_grad_mag(pos, tri, f):
    """頂点の値 f の 3 次元の三角形の上の勾配の大きさを、頂点のまわりの面積の重みで平均する。"""
    p0, p1, p2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    a11 = (e1 * e1).sum(1); a12 = (e1 * e2).sum(1); a22 = (e2 * e2).sum(1)
    det = a11 * a22 - a12 * a12
    ok = det > 1e-12
    d = np.where(ok, det, 1.0)
    d1 = f[tri[:, 1]] - f[tri[:, 0]]; d2 = f[tri[:, 2]] - f[tri[:, 0]]
    x1 = (a22 * d1 - a12 * d2) / d; x2 = (-a12 * d1 + a11 * d2) / d
    gm = np.linalg.norm(x1[:, None] * e1 + x2[:, None] * e2, axis=1)
    area = 0.5 * np.sqrt(np.maximum(det, 0)) * ok
    acc = np.zeros(len(pos)); ws = np.zeros(len(pos))
    for k in range(3):
        np.add.at(acc, tri[:, k], gm * area)
        np.add.at(ws, tri[:, k], area)
    return np.where(ws > 0, acc / np.maximum(ws, 1e-12), np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--param", default="a")
    ap.add_argument("--out", default=WORK + "design")
    ap.add_argument("--h", type=float, default=0.06, help="テクセル m")
    ap.add_argument("--hp", type=float, default=0.5, help="位相の場の粗い格子 m")
    ap.add_argument("--lam0", type=float, default=1.9, help="舌の間隔の事前の値 m（見えない所）")
    ap.add_argument("--lam-clip", default="1.1,3.6", help="原画から読んだ間隔の下限・上限 m")
    ap.add_argument("--sigma", type=float, default=3.0, help="原画の線の向きを広げる半径 m")
    ap.add_argument("--w-prior", type=float, default=0.15, help="事前の勾配の重み（データの重みの合計に対して）")
    ap.add_argument("--aniso-max", type=float, default=5.0)
    ap.add_argument("--max-rot", type=float, default=55.0, help="線の向きを巻きの向きから回してよい角の上限（度）")
    ap.add_argument("--seed", type=int, default=29)
    ap.add_argument("--fcz0", type=float, default=1.22, help="見えない所の白の終わりの既定（F）")
    ap.add_argument("--fcz1", type=float, default=1.5, help="見えない所の舌の始まりの既定（F）")
    ap.add_argument("--cz0-max", type=float, default=9.0, help="白の終わりの頂からの上限 m")
    ap.add_argument("--cz-width", default="1.2,5.0", help="淡い水色の帯の幅の下限・上限 m")
    ap.add_argument("--fit-w", type=float, default=1.0, help="原画の数えの重み（0 で既定の F だけ）")
    ap.add_argument("--wander", type=float, default=0.06, help="線のうねり（位相の単位）")
    ap.add_argument("--eps", type=float, default=0.6, help="（使わない）")
    ap.add_argument("--hw", type=lambda x: [float(v) for v in x.split(",")], default=[0.09, 0.11, 0.2, 0.28, 0.17],
                    help="線の半幅 m：細い線の下限,幅,太い帯の割合,太い帯の下限,幅")
    ap.add_argument("--tip-lo", type=float, default=-1.0, help="舌の先の帯の縁からのずれの下限 m")
    ap.add_argument("--tip-hi", type=float, default=0.2, help="舌の先の帯の縁からのずれの上限 m")
    ap.add_argument("--arch", type=float, default=0.9, help="舌の先の弧の高さ（舌の半幅の倍）")
    ap.add_argument("--lobe", type=float, default=0.35, help="白の縁が舌の上で下がる量 m")
    ap.add_argument("--cz-mode", default="face", choices=["face", "fit", "rim"], help="face：舌の帯の縁（原画の藍の面の始まり）を優先し、白の終わりは帯の幅だけ上")
    ap.add_argument("--dsep", type=float, default=0.85, help="新しい線を始める隣との最小の間（λ の倍）")
    ap.add_argument("--dtest", type=float, default=0.42, help="線を終える隣との間（λ の倍）")
    ap.add_argument("--lenf", default="0.55,0.4", help="線の長さの割合：最小,幅")
    a = ap.parse_args()
    t_start = time.time()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    UV, pinfo = P.load(a.param)
    A = S.load_attr29()
    g = S.load_gwb()
    tri = g["tri"]; pos = g["pos"]
    F = A[:, 0]; hrow = A[:, 3]
    # ---------------- 範囲（前の面：F 0.6〜4.9、低すぎない行）
    m = (F > 0.6) & (F < 4.9) & (hrow > 0.03)
    U0, V0 = UV[m].min(0) - 2.0
    U1, V1 = UV[m].max(0) + 2.0
    h = a.h
    Hd = int(np.ceil((U1 - U0) / h)) + 1
    Wd = int(np.ceil((V1 - V0) / h)) + 1
    print("domain U", U0, U1, "V", V0, V1, "tex", Hd, Wd)
    P3 = np.stack([UV[:, 0], UV[:, 1], np.zeros(len(UV))], 1)
    grid = S.UVGrid(U0, V0, h, Wd, Hd)
    tidt, baryt, _ = S.raster_bary(grid, P3, tri, near=-1)
    baryt = baryt.astype(np.float32)
    validt = tidt >= 0
    Ft = S.interp(tidt, baryt, tri, F).astype(np.float32)
    print("uv raster", round(time.time() - t_start, 1), round(float(validt.mean()), 3))
    Vt = V0 + h * np.arange(Wd)

    def u_at_F(fv):
        ok = validt & (Ft >= fv)
        first = np.where(ok.any(0), ok.argmax(0), -1)
        return np.where(first >= 0, U0 + h * first, np.nan)
    uF1 = u_at_F(1.0); uD0 = u_at_F(a.fcz0); uD1 = u_at_F(a.fcz1); uF4 = u_at_F(4.0); uF2 = u_at_F(2.0)

    def fillnan(x):
        ok = np.isfinite(x)
        return np.interp(np.arange(len(x)), np.nonzero(ok)[0], x[ok]) if ok.any() else np.zeros_like(x)
    uF1 = fillnan(uF1); uD0 = fillnan(uD0); uD1 = fillnan(uD1); uF4 = fillnan(uF4); uF2 = fillnan(uF2)
    # ---------------- 原画視点の画素 → (U, V) とヤコビ行列
    r = np.load(WORK + "raster_painting.npz")
    tid, bary = r["tid"], r["bary"]
    Up = S.interp(tid, bary, tri, UV[:, 0]).astype(np.float32)
    Vp = S.interp(tid, bary, tri, UV[:, 1]).astype(np.float32)
    Fp = S.interp(tid, bary, tri, F).astype(np.float32)
    del bary, r
    okp = np.isfinite(Up)
    gUy, gUx = np.gradient(np.where(okp, Up, np.nan))
    gVy, gVx = np.gradient(np.where(okp, Vp, np.nan))
    mpp = np.sqrt(np.abs(gUx * gVy - gUy * gVx))
    aniso = np.sqrt(gUx ** 2 + gUy ** 2 + gVx ** 2 + gVy ** 2) / np.maximum(mpp, 1e-6)
    lab = np.array(Image.open(S.LABELS))
    face = np.array(Image.open(WORK + "target_face.png")) > 0
    sky = np.isin(lab, [0, 9, 6, 7])
    near_sky = cv2.dilate(sky.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    inner_line = (lab == 5) & ~near_sky
    claw_seed = (lab == 2) | inner_line
    claw = (cv2.dilate(claw_seed.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))) > 0) & np.isin(lab, [1, 2, 5]) & ~face
    top = (lab == 1) & ~claw & ~face
    cls = np.full(lab.shape, -1, np.int8)
    cls[top] = 0; cls[claw] = 1; cls[face] = 2
    good = okp & (cls >= 0) & (Fp > 0.85) & (aniso < a.aniso_max)
    # ---------------- 爪の帯の境：V の箱ごとの誤りの最小
    vb = 0.5
    nb = int(np.ceil((V1 - V0) / vb))
    pu = Up[good]; pv = Vp[good]; pc = cls[good]
    bi = np.clip(((pv - V0) / vb).astype(int), 0, nb - 1)
    b0 = np.full(nb, np.nan); b1 = np.full(nb, np.nan); w0 = np.zeros(nb); w1 = np.zeros(nb)
    for k in range(nb):
        s = bi == k
        if s.sum() < 30:
            continue
        uu = pu[s]; cl = pc[s]
        o = np.argsort(uu); uu = uu[o]; cl = cl[o]
        for (lo_set, store_b, store_w) in (((0,), b0, w0), ((0, 1), b1, w1)):
            isl = np.isin(cl, lo_set).astype(np.float64)
            err = np.concatenate([[0], np.cumsum(1 - isl)]) + (isl.sum() - np.concatenate([[0], np.cumsum(isl)]))
            j = int(np.argmin(err))
            nlo, nhi = isl.sum(), (1 - isl).sum()
            if nlo < 15 or nhi < 15:
                continue
            x = uu[-1] if j >= len(uu) else (uu[0] if j == 0 else 0.5 * (uu[j - 1] + uu[j]))
            store_b[k] = x
            store_w[k] = min(nlo, nhi) / (1.0 + err[j])
    vbc = V0 + vb * (np.arange(nb) + 0.5)

    def to_cols(b, w):
        vals = np.interp(Vt, vbc, np.nan_to_num(b))
        wt = np.interp(Vt, vbc, np.where(np.isfinite(b), w, 0.0))
        near = np.interp(Vt, vbc, np.isfinite(b).astype(float))
        return vals, wt * (near > 0.99)
    v0c, w0c = to_cols(b0, w0)
    v1c, w1c = to_cols(b1, w1)
    w0c = a.fit_w * w0c / max(w0c.max(), 1e-9)
    w1c = a.fit_w * w1c / max(w1c.max(), 1e-9)
    ss = (1.0 / h) ** 4 * 2.0
    Ucz0 = smooth_curve(v0c, w0c, uD0, ss * 0.5, 0.02)
    Ucz1 = smooth_curve(v1c, w1c, uD1, ss * 0.5, 0.02)
    czw = [float(x) for x in a.cz_width.split(",")]
    if a.cz_mode == "face":
        Ucz1 = np.maximum(Ucz1, uF1 + 0.5 + czw[0])
        Ucz0 = np.clip(Ucz0, Ucz1 - czw[1], Ucz1 - czw[0])
        Ucz0 = np.maximum(Ucz0, uF1 + 0.5)
    elif a.cz_mode == "rim":
        # 白の終わりは原画の白い頂（爪の輪の前）の境、舌はそのすぐ下から（淡い水色の帯は czw の幅だけ。唇の前も藍の舌の地）
        Ucz0 = np.clip(Ucz0, uF1 + 0.5, uF1 + a.cz0_max)
        kn2 = np.arange(V0 - 3, V1 + 3, 3.0)
        rimw = np.interp(Vt, kn2, czw[0] + (czw[1] - czw[0]) * rng.random(len(kn2)))
        Ucz1 = Ucz0 + rimw
    else:
        Ucz0 = np.clip(Ucz0, uF1 + 0.5, uF1 + a.cz0_max)
        Ucz1 = np.clip(Ucz1, Ucz0 + czw[0], Ucz0 + czw[1])
    print("boundaries", round(time.time() - t_start, 1))
    # ---------------- 原画の藍中の線：向きと間隔 → 面の上の目標の勾配
    sk = np.load(WORK + "target_skel.npz")
    allx = []; ally = []; allc = []
    for ci in range(int(sk["n"])):
        allx.append(sk[f"x{ci}"]); ally.append(sk[f"y{ci}"]); allc.append(np.full(len(sk[f"x{ci}"]), ci))
    allx = np.concatenate(allx).astype(float); ally = np.concatenate(ally).astype(float); allc = np.concatenate(allc)
    xy = np.stack([allx, ally], 1)
    kd = cKDTree(xy)
    nb_idx = kd.query_ball_point(xy, r=5.0)
    tang = np.zeros((len(xy), 2))
    for i, nbr in enumerate(nb_idx):
        nbr = [j for j in nbr if allc[j] == allc[i]]
        if len(nbr) < 3:
            continue
        q = xy[nbr] - xy[nbr].mean(0)
        w_, v_ = np.linalg.eigh(q.T @ q)
        tang[i] = v_[:, 1]
    # 間隔：画像の法線の向きに、別の線の点までの距離
    nimg = np.stack([-tang[:, 1], tang[:, 0]], 1)
    sp_img = np.full(len(xy), np.nan)
    far_idx = kd.query_ball_point(xy, r=90.0)
    for i, nbr in enumerate(far_idx):
        if not np.any(tang[i]):
            continue
        nbr = np.array([j for j in nbr if allc[j] != allc[i]], int)
        if len(nbr) == 0:
            continue
        d = xy[nbr] - xy[i]
        dist = np.linalg.norm(d, axis=1)
        cosang = np.abs(d @ nimg[i]) / np.maximum(dist, 1e-6)
        sel = cosang > np.cos(np.radians(25))
        if sel.any():
            sp_img[i] = dist[sel].min()
    xi = allx.astype(int); yi = ally.astype(int)
    okd = okp[yi, xi] & face[yi, xi] & (aniso[yi, xi] < a.aniso_max) & np.any(tang != 0, 1) & np.isfinite(gUx[yi, xi]) & np.isfinite(gVx[yi, xi])
    J = np.stack([np.stack([gUx[yi, xi], gUy[yi, xi]], -1), np.stack([gVx[yi, xi], gVy[yi, xi]], -1)], 1)   # (n, 2, 2)：d(U,V)/d(x,y)
    t_uv = np.einsum("nij,nj->ni", J, tang)
    t_len = np.linalg.norm(t_uv, axis=1)
    okd &= t_len > 1e-6
    t_uv = t_uv / np.maximum(t_len[:, None], 1e-9)
    n_uv = np.stack([-t_uv[:, 1], t_uv[:, 0]], 1)
    n_uv *= np.sign(n_uv[:, 1] + 1e-9)[:, None]                # V が増える向きへ
    rot = np.degrees(np.arctan2(np.abs(n_uv[:, 0]), n_uv[:, 1]))
    okd &= rot < a.max_rot
    sp_uv = np.linalg.norm(np.einsum("nij,nj->ni", J, nimg) * sp_img[:, None], axis=1)
    lc = [float(x) for x in a.lam_clip.split(",")]
    lam_p = np.where(np.isfinite(sp_uv), np.clip(sp_uv, lc[0], lc[1]), a.lam0)
    conf = okd / (1.0 + 0.5 * (aniso[yi, xi] - 1.0))
    conf = np.nan_to_num(conf)
    pu_ = Up[yi, xi].astype(float); pv_ = Vp[yi, xi].astype(float)
    sel = conf > 0
    Gp = n_uv[sel] / lam_p[sel, None]
    cp = conf[sel]; pu_s = pu_[sel]; pv_s = pv_[sel]
    print("stripe data", int(sel.sum()), "rot p50/p90", np.percentile(rot[okd], [50, 90]).round(1).tolist(),
          "lam p10/p50/p90", np.percentile(lam_p[sel], [10, 50, 90]).round(2).tolist())
    # ---------------- 粗い格子の上の目標の勾配の場（ガウスの重みで広げる＋事前）
    hp = a.hp
    nU = int(np.ceil((U1 - U0) / hp)) + 1
    nV = int(np.ceil((V1 - V0) / hp)) + 1
    gu_c = U0 + hp * np.arange(nU); gv_c = V0 + hp * np.arange(nV)
    # 向きは符号のない量なので、テンソル n nᵀ の重みつきの和で広げる（向きの 180° の取り違えで打ち消し合わない）。間隔は 1/λ の重みつきの平均
    Txx = np.zeros((nU, nV)); Txy = np.zeros((nU, nV)); Tyy = np.zeros((nU, nV)); Til = np.zeros((nU, nV)); accW = np.zeros((nU, nV))
    rad = int(np.ceil(3 * a.sigma / hp))
    iu = np.round((pu_s - U0) / hp).astype(int); iv = np.round((pv_s - V0) / hp).astype(int)
    nn = Gp * lam_p[sel, None]
    for du_ in range(-rad, rad + 1):
        for dv_ in range(-rad, rad + 1):
            ii = iu + du_; jj = iv + dv_
            okk = (ii >= 0) & (ii < nU) & (jj >= 0) & (jj < nV)
            ic = np.clip(ii, 0, nU - 1); jc = np.clip(jj, 0, nV - 1)
            d2 = (gu_c[ic] - pu_s) ** 2 + (gv_c[jc] - pv_s) ** 2
            wk = cp * np.exp(-0.5 * d2 / a.sigma ** 2) * okk
            np.add.at(Txx, (ic, jc), wk * nn[:, 0] * nn[:, 0])
            np.add.at(Txy, (ic, jc), wk * nn[:, 0] * nn[:, 1])
            np.add.at(Tyy, (ic, jc), wk * nn[:, 1] * nn[:, 1])
            np.add.at(Til, (ic, jc), wk / lam_p[sel])
            np.add.at(accW, (ic, jc), wk)
    wpr = a.w_prior * np.percentile(accW[accW > 0], 90) if (accW > 0).any() else 1.0
    Tyy = Tyy + wpr
    # 主の向き（2×2 の対称の固有ベクトル）
    ang = 0.5 * np.arctan2(2 * Txy, Txx - Tyy)          # x 軸（U）からの角
    nUx = np.cos(ang); nVy = np.sin(ang)
    sgn = np.where(nVy < 0, -1.0, 1.0)
    nUx *= sgn; nVy *= sgn
    invlam = (Til + wpr / a.lam0) / (accW + wpr)
    GU = nUx * invlam
    GV = nVy * invlam
    dataw = accW / (accW + wpr)
    # ---------------- 面の計量（(u, w) の 1 歩が面の上で何 m か）：三角形ごとの ∇u・∇w から逆の計量 → 計量 M（頂点の平均 → テクセル）
    p0, p1, p2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    a11 = (e1 * e1).sum(1); a12 = (e1 * e2).sum(1); a22 = (e2 * e2).sum(1)
    det = a11 * a22 - a12 * a12
    okt = det > 1e-12
    dd_ = np.where(okt, det, 1.0)

    def tgrad(f):
        d1 = f[tri[:, 1]] - f[tri[:, 0]]; d2 = f[tri[:, 2]] - f[tri[:, 0]]
        x1 = (a22 * d1 - a12 * d2) / dd_; x2 = (-a12 * d1 + a11 * d2) / dd_
        return x1[:, None] * e1 + x2[:, None] * e2
    gu3 = tgrad(UV[:, 0]); gw3 = tgrad(UV[:, 1])
    Guu = (gu3 * gu3).sum(1); Guw = (gu3 * gw3).sum(1); Gww = (gw3 * gw3).sum(1)
    dG = np.maximum(Guu * Gww - Guw * Guw, 1e-6)
    Muu = Gww / dG; Muw = -Guw / dG; Mww = Guu / dG            # 計量 = 逆の計量の逆
    area = 0.5 * np.sqrt(np.maximum(det, 0)) * okt
    accm = np.zeros((len(pos), 3)); wsm = np.zeros(len(pos))
    for k in range(3):
        np.add.at(accm, tri[:, k], np.stack([Muu, Muw, Mww], 1) * area[:, None])
        np.add.at(wsm, tri[:, k], area)
    Mv = accm / np.maximum(wsm, 1e-12)[:, None]
    Mv[:, 0] = np.clip(Mv[:, 0], 0.2, 5); Mv[:, 2] = np.clip(Mv[:, 2], 0.2, 5)
    Mv[:, 1] = np.clip(Mv[:, 1], -0.9 * np.sqrt(Mv[:, 0] * Mv[:, 2]), 0.9 * np.sqrt(Mv[:, 0] * Mv[:, 2]))
    Mt = np.stack([S.interp(tidt, baryt, tri, Mv[:, k]).astype(np.float32) for k in range(3)], -1)
    Mt[~validt] = (1.0, 0.0, 1.0)
    del baryt, p0, p1, p2, e1, e2, gu3, gw3
    # ---------------- 線の向き（粗い格子の単位の法線 nUx・nVy → 接線 t = (nVy, −nUx)）と間隔 λ
    lam_g = np.clip(1.0 / invlam, float(a.lam_clip.split(",")[0]), float(a.lam_clip.split(",")[1]))

    def field(uq, wq):
        fu = min(max((uq - U0) / hp, 0), nU - 1.001); fv = min(max((wq - V0) / hp, 0), nV - 1.001)
        i = int(fu); j = int(fv); x = fu - i; y = fv - j

        def bl(G):
            return (G[i, j] * (1 - x) * (1 - y) + G[i, j + 1] * (1 - x) * y + G[i + 1, j] * x * (1 - y) + G[i + 1, j + 1] * x * y)
        nu_, nv_ = bl(nUx), bl(nVy)
        tx, ty = nv_, -nu_
        ln = max(np.hypot(tx, ty), 1e-9)
        tx /= ln; ty /= ln
        if tx < 0:
            tx, ty = -tx, -ty
        return tx, ty, bl(lam_g)

    def valid_at(uq, wq):
        i = int(round((uq - U0) / h)); j = int(round((wq - V0) / h))
        return 0 <= i < Hd and 0 <= j < Wd and bool(validt[i, j])
    # ---------------- 等間隔の流線（Jobard–Lefer の簡略）：線は帯の縁から巻きの向きに下り、隣と近づきすぎると終わり（合流）、間が開くと新しい線が生まれる
    cellg = 0.3
    occ = {}

    def occ_add(pts, lid):
        for (uq, wq) in pts:
            occ.setdefault((int(uq // cellg), int(wq // cellg)), []).append((uq, wq, lid))

    def near_dist(uq, wq, rmax, skip=None):
        ci, cj = int(uq // cellg), int(wq // cellg)
        rr = int(np.ceil(rmax / cellg))
        best = 1e18
        for di in range(-rr, rr + 1):
            for dj in range(-rr, rr + 1):
                for (u2, w2, l2) in occ.get((ci + di, cj + dj), ()):
                    if l2 == skip:
                        continue
                    dd = (u2 - uq) ** 2 + (w2 - wq) ** 2
                    if dd < best:
                        best = dd
        return best ** 0.5
    f4c = np.maximum(uF4, Ucz1 + 6.0)
    step = 0.12

    def trace(u_s, w_s, lid, direction=1):
        pts = [(u_s, w_s)]
        uq, wq = u_s, w_s
        L = 0.0
        while L < 70.0:
            tx, ty, lam = field(uq, wq)
            um, wm = uq + 0.5 * step * tx * direction, wq + 0.5 * step * ty * direction
            tx2, ty2, _ = field(um, wm)
            un, wn = uq + step * tx2 * direction, wq + step * ty2 * direction
            if not valid_at(un, wn):
                break
            if direction > 0 and un > float(np.interp(wn, Vt, f4c)) + 1.5:
                break
            if direction < 0 and un < float(np.interp(wn, Vt, Ucz1)) - 0.3:
                break
            if near_dist(un, wn, a.dtest * lam + 0.1, skip=lid) < a.dtest * lam:
                break
            L += step
            uq, wq = un, wn
            pts.append((uq, wq))
        return pts
    lines = []        # (pts (n,2), kind 0 = 帯の縁から, 1 = 間に生まれた)
    queue = []
    wq = V0 + 0.5
    while wq < V1 - 0.5:
        uq = float(np.interp(wq, Vt, Ucz1)) - 0.3
        if valid_at(uq, wq):
            queue.append((uq, wq, 0))
        _, _, lam = field(uq, wq)
        wq += lam
    qi = 0
    while qi < len(queue) and len(lines) < 4000:
        uq, wq, kind = queue[qi]; qi += 1
        if not valid_at(uq, wq):
            continue
        _, _, lam = field(uq, wq)
        if near_dist(uq, wq, a.dsep * lam + 0.1) < a.dsep * lam:
            continue
        lid = len(lines)
        fw = trace(uq, wq, lid, 1)
        if kind == 1:
            bw = trace(uq, wq, lid, -1)
            pts = bw[::-1] + fw[1:]
        else:
            pts = fw
        pts = np.array(pts)
        if len(pts) * step < 2.0:
            continue
        lines.append((pts, kind))
        occ_add(pts, lid)
        for k in range(0, len(pts), max(1, int(1.0 / step))):
            tx, ty, lam = field(*pts[k])
            for sgn in (-1, 1):
                queue.append((pts[k][0] - sgn * lam * ty, pts[k][1] + sgn * lam * tx, 1))
    kind_l = np.array([k for (_, k) in lines])
    print("streamlines", len(lines), "top", int((kind_l == 0).sum()), round(time.time() - t_start, 1))
    # ---------------- 線の点（0.08 m おき）と、線ごとの太さ・始まりと終わりの細り
    LP = []; LI = []; LS = []; LL = []
    for lid, (pts, kind) in enumerate(lines):
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        sacc = np.concatenate([[0], np.cumsum(seg)])
        L = sacc[-1]
        ss_ = np.arange(0, L, 0.08)
        uu = np.interp(ss_, sacc, pts[:, 0]); ww = np.interp(ss_, sacc, pts[:, 1])
        LP.append(np.stack([uu, ww], 1)); LI.append(np.full(len(ss_), lid)); LS.append(ss_); LL.append(np.full(len(ss_), L))
    LP = np.concatenate(LP); LI = np.concatenate(LI); LS = np.concatenate(LS); LL = np.concatenate(LL)
    nl = len(lines)
    rr1, rr2, rr3 = rng.random(nl), rng.random(nl), rng.random(nl)
    hw_l = a.hw[0] + a.hw[1] * rr1
    hw_l = np.where(rr2 < a.hw[2], a.hw[3] + a.hw[4] * rr3, hw_l)
    kdl = cKDTree(LP)
    # 舌の中の位置：最も近い線までの距離 d1 と、別の線までの距離 d2（線の点を 0.3 m おきに間引いた木で 40 近傍から探す）
    sub = np.zeros(len(LP), bool)
    for lid in range(nl):
        ix = np.nonzero(LI == lid)[0]
        sub[ix[::4]] = True
        sub[ix[-1]] = True
    LP2 = LP[sub]; LI2 = LI[sub]
    kd2 = cKDTree(LP2)
    UU = np.broadcast_to((U0 + h * np.arange(Hd)).astype(np.float32)[:, None], (Hd, Wd))
    VV = np.broadcast_to((V0 + h * np.arange(Wd)).astype(np.float32)[None, :], (Hd, Wd))
    dist_m = np.full((Hd, Wd), 9.0, np.float32); hw = np.zeros((Hd, Wd), np.float32)
    d2_m = np.full((Hd, Wd), 9.0, np.float32); pair = np.full((Hd, Wd), -1, np.int64)

    def mlen(dvec, mm):
        return np.sqrt(np.maximum(dvec[:, 0] ** 2 * mm[:, 0] + 2 * dvec[:, 0] * dvec[:, 1] * mm[:, 1] + dvec[:, 1] ** 2 * mm[:, 2], 0))
    for r0 in range(0, Hd, 64):
        r1_ = min(Hd, r0 + 64)
        q = np.stack([UU[r0:r1_].ravel(), VV[r0:r1_].ravel()], 1).astype(np.float64)
        mm = Mt[r0:r1_].reshape(-1, 3)
        dq, iq = kdl.query(q, k=1, distance_upper_bound=4.0)
        okq = np.isfinite(dq)
        iqc = np.where(okq, iq, 0)
        dm = mlen(q - LP[iqc], mm)
        lid = LI[iqc]; s_ = LS[iqc]; L_ = LL[iqc]
        tap_end = np.sqrt(np.clip((L_ - s_) / 2.5, 0, 1))
        tap_st = np.where(kind_l[lid] == 1, np.sqrt(np.clip(s_ / 2.0, 0, 1)), 1.0)
        dist_m[r0:r1_] = np.where(okq, dm, 9.0).reshape(r1_ - r0, Wd)
        hw[r0:r1_] = np.where(okq, hw_l[lid] * tap_end * tap_st, 0.0).reshape(r1_ - r0, Wd)
        d2q, i2q = kd2.query(q, k=40, distance_upper_bound=5.0)
        ok2 = np.isfinite(d2q)
        l2 = np.where(ok2, LI2[np.where(ok2, i2q, 0)], -1)
        other = ok2 & (l2 != lid[:, None])
        first = np.where(other.any(1), other.argmax(1), -1)
        has2 = (first >= 0) & okq
        j2 = np.where(has2, i2q[np.arange(len(q)), np.maximum(first, 0)], 0)
        dm2 = mlen(q - LP2[j2], mm)
        d2_m[r0:r1_] = np.where(has2, dm2, 9.0).reshape(r1_ - r0, Wd)
        lo = np.minimum(lid, LI2[j2]); hi = np.maximum(lid, LI2[j2])
        pair[r0:r1_] = np.where(has2, lo * 100000 + hi, -1).reshape(r1_ - r0, Wd)
    print("stripe sdf", round(time.time() - t_start, 1))
    fu = np.clip((UU - U0) / hp, 0, nU - 1.001); fv = np.clip((VV - V0) / hp, 0, nV - 1.001)
    ii_ = fu.astype(int); jj_ = fv.astype(int); xx = fu - ii_; yy = fv - jj_
    lamt = (lam_g[ii_, jj_] * (1 - xx) * (1 - yy) + lam_g[ii_, jj_ + 1] * (1 - xx) * yy + lam_g[ii_ + 1, jj_] * xx * (1 - yy) + lam_g[ii_ + 1, jj_ + 1] * xx * yy).astype(np.float32)
    del fu, fv, ii_, jj_, xx, yy
    cz1 = Ucz1[None, :].astype(np.float32); cz0 = Ucz0[None, :].astype(np.float32)
    du = UU - cz1
    widen = 1.0 + 0.5 * np.clip(1.0 - du / 1.5, 0.0, 1.0)     # 帯の縁の近くで少し太る（扇）
    hw = hw * widen
    a_side = dist_m - hw
    # 舌の幅 Wt と舌の中の位置 θ（0 = 線の上、0.5 = 舌の中心）。舌の先は丸い弧（半円に近い）で、舌ごとに高さをずらす
    Wt = np.minimum(dist_m + d2_m, 2.2 * lamt)
    theta = np.clip(dist_m / np.maximum(Wt, 1e-3), 0, 0.5)
    hpair = np.where(pair >= 0, ((pair * 2654435761) % 1000003) / 1000003.0, 0.5).astype(np.float32)
    t_m = a.tip_lo + (a.tip_hi - a.tip_lo) * hpair                      # 舌の先の帯の縁からのずれ（m。負は淡い水色の帯へ食い込む）
    arch = np.maximum(0.5 * Wt - hw, 0.1) * a.arch * np.sqrt(np.clip(1 - (1 - 2 * theta) ** 2, 0, 1))
    b_tip = du - (t_m - arch)
    Ddark = round_intersect(a_side, b_tip, np.full_like(a_side, 0.12)).astype(np.float32)
    Dmiz = (cz1 + 0.25 - UU).astype(np.float32)
    lobe = a.lobe * (2 * theta) ** 2
    Dwhite = (cz0 + lobe - UU).astype(np.float32)
    pht = theta.astype(np.float32); g3t = lamt
    info = 0; align = 0.0; delta = 0.0
    phi = np.zeros((nU, nV)); g3 = np.ones(len(pos)) / a.lam0
    # 白い点
    Ddot = np.full((Hd, Wd), -1.0, np.float32)
    cell = 0.6
    gu_ = np.arange(U0, U1, cell); gv_ = np.arange(V0, V1, cell)
    CU, CV = np.meshgrid(gu_, gv_, indexing="ij")
    CU = CU.ravel() + cell * (0.1 + 0.8 * rng.random(CU.size)); CV = CV.ravel() + cell * (0.1 + 0.8 * rng.random(CV.size))
    radd = 0.05 + 0.07 * rng.random(CU.size) ** 1.7
    iu2 = np.clip(((CU - U0) / h).astype(int), 0, Hd - 1); iv2 = np.clip(((CV - V0) / h).astype(int), 0, Wd - 1)
    duu = CU - Ucz1[iv2]
    prob = np.clip(0.6 - 0.03 * duu, 0.12, 0.6)
    keep = (Ddark[iu2, iv2] > radd + 0.07) & validt[iu2, iv2] & (rng.random(CU.size) < prob)
    CU, CV, radd = CU[keep], CV[keep], radd[keep]
    K = int(np.ceil(0.13 / h)) + 1
    for du_i in range(-K, K + 1):
        for dv_i in range(-K, K + 1):
            ii = np.clip(((CU - U0) / h).round().astype(int) + du_i, 0, Hd - 1)
            jj = np.clip(((CV - V0) / h).round().astype(int) + dv_i, 0, Wd - 1)
            d = radd - np.sqrt((U0 + h * ii - CU) ** 2 + (V0 + h * jj - CV) ** 2)
            np.maximum.at(Ddot, (ii, jj), d.astype(np.float32))
    print("dots", len(CU), round(time.time() - t_start, 1))
    tex = np.stack([np.clip(Dwhite, -4, 4), np.clip(Dmiz, -4, 4), np.clip(Ddark, -4, 4), np.clip(Ddot, -4, 4)], -1).astype(np.float16)
    tex.tofile(os.path.join(a.out, "s01b_design_f16.bin"))
    np.save(os.path.join(a.out, "dbg_phi_tex.npy"), np.stack([pht, g3t, hw.astype(np.float32)], -1).astype(np.float16))
    attr = A.astype(np.float32).copy()
    attr[:, 6] = UV[:, 0]; attr[:, 7] = UV[:, 1]
    attr.tofile(os.path.join(a.out, "s01b_attr_f32.bin"))
    # 線の 3 次元の間隔の統計（主役波の本体の舌の帯：F 1.2〜4.2、行の頂の高さ ≥ 0.3）
    body = (F > 1.2) & (F < 4.2) & (hrow > 0.3)
    meta = dict(schema="GreatWave.Sample01B.design/3", param=pinfo, U0=float(U0), V0=float(V0), h=h, rows_U=Hd, cols_V=Wd,
                channels=["Dwhite m", "Dmizuiro m", "Ddark m", "Ddot m"], layout="row-major, row = U index (U0 + h*i), col = V index (V0 + h*j), RGBA half",
                args=vars(a), phase_cg=int(info), phase_align_mean_cos=align, phase_delta=float(delta),
                stripe_data_points=int(sel.sum()), streamlines=len(lines), streamlines_top=int((kind_l == 0).sum()),
                dots=int(len(CU)), design_sha256=S.sha256(os.path.join(a.out, "s01b_design_f16.bin")),
                attr_sha256=S.sha256(os.path.join(a.out, "s01b_attr_f32.bin")), seconds=time.time() - t_start)
    json.dump(meta, open(os.path.join(a.out, "s01b_design.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    np.savez_compressed(os.path.join(a.out, "s01b_curves.npz"), Vt=Vt, Ucz0=Ucz0, Ucz1=Ucz1, v0c=v0c, w0c=w0c, v1c=v1c, w1c=w1c, uF1=uF1, uF4=uF4,
                        phi=phi.astype(np.float32), dataw=dataw.astype(np.float32), U0=U0, V0=V0, hp=hp)
    # ---------------- 図：(U, V) の平面の設計（縮小）
    col = np.zeros((Hd, Wd, 3), np.uint8)
    pal = dict(white=(251, 246, 227), miz=(192, 211, 199), mid=(41, 105, 148), dark=(34, 63, 96))
    col[:] = pal["mid"]
    col[Ddark > 0] = pal["dark"]
    col[(Ddot > 0) & (Ddark > 0)] = pal["white"]
    col[(Dmiz > 0) & ~(Ddark > 0)] = pal["miz"]
    col[Dwhite > 0] = pal["white"]
    col[~validt] = (90, 90, 90)
    for k_ in range(len(pu_s)):
        pass
    ii = np.clip(((pu_s - U0) / h).astype(int), 0, Hd - 1); jj = np.clip(((pv_s - V0) / h).astype(int), 0, Wd - 1)
    col[ii, jj] = (255, 40, 40)
    for arr, c_ in ((Ucz0, (255, 160, 0)), (Ucz1, (0, 200, 0)), (uF1, (200, 0, 200)), (uF4, (200, 0, 200)), (uF2, (120, 0, 200))):
        ii = ((arr - U0) / h)
        okk = np.isfinite(ii)
        col[np.clip(ii[okk].astype(int), 0, Hd - 1), np.arange(Wd)[okk]] = c_
    Image.fromarray(col).resize((Wd // 2, Hd // 2), Image.NEAREST).save(os.path.join(a.out, "s01b_design_uv.png"))
    print("done", round(time.time() - t_start, 1))


if __name__ == "__main__":
    main()
