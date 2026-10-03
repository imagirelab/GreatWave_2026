# -*- coding: utf-8 -*-
"""美術の見本01 B（原画のような舌形）第 2 版（2026-10-03、再開の回）。第 1 版 s01b_design.py（10/2 の b3 まで）を土台に、次を直した。
  1) 面の座標の範囲を背（F ≥ −0.35）まで広げ、背の白の下の藍の胴にも、同じ (u, w) の上の線（巻きの向き、隣と一様な間）を置く
     （前の版の背は仕上げ29 の行の c の溝のままで、Q29 の「歪んだ」溝が側面・後ろから見えていた）。
  2) 線の間を、面の上の m（(u, w) の計量 M）で測る（w の 1 m が面の上で 1 m でない所でも、線の 3 次元の間がそろう）。
  3) 線の向きの場（原画の藍中の線の向き＋巻きの向きの事前）を、テンソルのまま σ_b のガウスで平らにし、流線を 1 m の窓で平らにする
     （唇の上で線が角を作って折れたのを減らす）。
  4) 舌の頭：前の線は爪の帯の縁 U_cz1 から始め、始まりの 1.2 m で太さを 0.3 → 1 に育てる。舌の頭は丸い弧で帯へ食い込み、
     頭と頭の間に淡い水色の小さな切れ込みが残って、そこから藍中の線が生まれる（原画の舌の頭と線の生まれ方。前の版は線の始まりが淡い水色の棒に見えた）。
  5) 白い点：頂の近くに多く、下へ行くほど少なく小さく。背はまばら。
原画の色を面へ写さない（投影なし）。原画は、線の向き・間隔・帯の境を合わせる目的関数の相手としてだけ使う（前の版と同じ）。
出力（--out）：s01b_design_f16.bin（行 = U、列 = V、RGBA = 白・淡い水色・藍濃・点の符号付きの距離 m、half）、s01b_design.json、s01b_attr_f32.bin、図。"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s01b_common as S
import s01b_param as P
from s01b_design import round_intersect, smooth_curve

WORK = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/work/"


def floats(x):
    return [float(v) for v in x.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--param", default="a")
    ap.add_argument("--out", required=True)
    ap.add_argument("--h", type=float, default=0.06, help="テクセル m")
    ap.add_argument("--hp", type=float, default=0.5, help="向きの場の粗い格子 m")
    ap.add_argument("--lam0", type=float, default=2.2, help="線の間隔の事前の値 m（原画の見えない所）")
    ap.add_argument("--lam-back", type=float, default=2.0, help="背の線の間隔 m")
    ap.add_argument("--lam-clip", default="1.6,3.4")
    ap.add_argument("--sigma", type=float, default=6.0, help="原画の線の向きを広げる半径 m")
    ap.add_argument("--blur", type=float, default=2.0, help="向きの場（テンソル）を平らにする半径 m")
    ap.add_argument("--w-prior", type=float, default=0.03)
    ap.add_argument("--aniso-max", type=float, default=5.0)
    ap.add_argument("--max-rot", type=float, default=45.0)
    ap.add_argument("--seed", type=int, default=29)
    ap.add_argument("--fcz0", type=float, default=1.22)
    ap.add_argument("--fcz1", type=float, default=1.5)
    ap.add_argument("--cz0-max", type=float, default=9.0)
    ap.add_argument("--cz-width", default="1.6,2.6")
    ap.add_argument("--fit-w", type=float, default=1.0)
    ap.add_argument("--f-back", type=float, default=-0.35, help="範囲の背の側の F")
    ap.add_argument("--f-bseed", type=float, default=0.9, help="背の線を始める F（頂のすぐ後ろ。白の下に隠れる）")
    ap.add_argument("--hw", type=floats, default=[0.12, 0.10, 0.25, 0.26, 0.12],
                    help="前の線の半幅 m：細い線の下限,幅,太い線の割合,太い線の下限,幅")
    ap.add_argument("--hw-back", type=floats, default=[0.10, 0.08], help="背の線の半幅 m：下限,幅")
    ap.add_argument("--top-wedge", type=floats, default=[0.40, 5.0], help="前の線（帯の縁から）の始まりの半幅 m と、胴の太さへ細る長さ m（原画の線は頭の間で太く、下で細い）")
    ap.add_argument("--head", type=floats, default=[0.8, 1.2, 1.7], help="舌の頭：高さ（舌の半幅の倍）,高さの上限 m,頭を作る舌の半幅の上限 m（それより広い間は平らな縁）")
    ap.add_argument("--end-taper", type=float, default=3.0, help="線の終わりで細る長さ m")
    ap.add_argument("--tip-lo", type=float, default=-0.5, help="舌の先（頭の付け根）の帯の縁からのずれの下限 m")
    ap.add_argument("--tip-hi", type=float, default=0.1)
    ap.add_argument("--arch", type=float, default=1.0, help="舌の頭の弧の高さ（舌の半幅の倍）")
    ap.add_argument("--arch-max", type=float, default=1.4, help="舌の頭の弧の高さの上限 m")
    ap.add_argument("--lobe", type=float, default=0.35)
    ap.add_argument("--miz-off", type=float, default=0.12, help="淡い水色の帯の下の縁（帯の縁 U_cz1 からの m）")
    ap.add_argument("--dsep", type=float, default=0.85)
    ap.add_argument("--dtest", type=float, default=0.45)
    ap.add_argument("--fill-top", type=float, default=0.6, help="間に生まれた線が上へ伸びてよい帯の縁からの m")
    ap.add_argument("--smooth-win", type=float, default=1.0, help="流線を平らにする窓 m")
    ap.add_argument("--dots", type=floats, default=[0.45, 0.05, 0.04, 0.05, 0.045, 0.06],
                    help="点：頂の近くの確率,1 m ごとの減り,下限,背の確率,半径の下限,幅")
    ap.add_argument("--dot-cell", type=float, default=0.6)
    ap.add_argument("--dot-v2", type=floats, default=None,
                    help="改善の回 1（美術監督の項目 7）白い点：帯の縁からの減り m,群れの強さ,群れの波長 m,半径の下限 m,半径の幅 m,半径の偏りの冪"
                         "（点を帯の縁と舌の頭の近くに群れさせ、大きさを不揃いに、下ほど少なく。省くと前の決まり）")
    ap.add_argument("--lam-grow", type=float, default=0.0, help="前の線の間を帯の縁から下へ広げる長さ m（du がこの長さで間が 2 倍。0 で広げない）")
    ap.add_argument("--seed-jit", type=float, default=0.0, help="帯の縁の線の始まりの間の不揃い（λ の倍の ± 幅）")
    ap.add_argument("--early", type=floats, default=[0.0, 6.0, 16.0], help="帯の縁の線のうち途中で終える割合,長さの下限 m,上限 m")
    ap.add_argument("--head-var", type=float, default=0.0, help="舌の頭の高さの不揃い（倍の ± 幅）")
    ap.add_argument("--band-rel", type=float, default=0.0, help="唇の長さ（頂 F 1 → 唇の先 F 2 の u の差 m）がこれより短い所では、帯の幅・白の終わり・舌の頭を唇の長さに比べて縮める（0 で縮めない）")
    a = ap.parse_args()
    t_start = time.time()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    UV, pinfo = P.load(a.param)
    A = S.load_attr29()
    g = S.load_gwb()
    tri = g["tri"]; pos = g["pos"]
    F = A[:, 0]; hrow = A[:, 3]
    # ---------------- 範囲（背の足の少し前〜前面の下、低すぎない行）
    m = (F > a.f_back) & (F < 4.9) & (hrow > 0.03)
    U0, V0 = UV[m].min(0) - 2.0
    U1, V1 = UV[m].max(0) + 2.0
    h = a.h
    Hd = int(np.ceil((U1 - U0) / h)) + 1
    Wd = int(np.ceil((V1 - V0) / h)) + 1
    print("domain U", round(U0, 2), round(U1, 2), "V", round(V0, 2), round(V1, 2), "tex", Hd, Wd)
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

    def fillnan(x):
        ok = np.isfinite(x)
        return np.interp(np.arange(len(x)), np.nonzero(ok)[0], x[ok]) if ok.any() else np.zeros_like(x)
    uF1 = fillnan(u_at_F(1.0)); uD0 = fillnan(u_at_F(a.fcz0)); uD1 = fillnan(u_at_F(a.fcz1))
    uF4 = fillnan(u_at_F(4.0)); uF2 = fillnan(u_at_F(2.0)); uB = fillnan(u_at_F(a.f_bseed))
    # ---------------- 原画視点の画素 → (U, V) とヤコビ行列（第 1 版と同じ）
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
    # ---------------- 爪の帯の境：V の箱ごとの誤りの最小（第 1 版の rim の形）
    vb = 0.5
    nb = int(np.ceil((V1 - V0) / vb))
    pu = Up[good]; pv = Vp[good]; pc = cls[good]
    bi = np.clip(((pv - V0) / vb).astype(int), 0, nb - 1)
    b0 = np.full(nb, np.nan); w0 = np.zeros(nb)
    for k in range(nb):
        s_ = bi == k
        if s_.sum() < 30:
            continue
        uu = pu[s_]; cl = pc[s_]
        o = np.argsort(uu); uu = uu[o]; cl = cl[o]
        isl = (cl == 0).astype(np.float64)
        err = np.concatenate([[0], np.cumsum(1 - isl)]) + (isl.sum() - np.concatenate([[0], np.cumsum(isl)]))
        j = int(np.argmin(err))
        nlo, nhi = isl.sum(), (1 - isl).sum()
        if nlo < 15 or nhi < 15:
            continue
        b0[k] = uu[-1] if j >= len(uu) else (uu[0] if j == 0 else 0.5 * (uu[j - 1] + uu[j]))
        w0[k] = min(nlo, nhi) / (1.0 + err[j])
    vbc = V0 + vb * (np.arange(nb) + 0.5)
    v0c = np.interp(Vt, vbc, np.nan_to_num(b0))
    w0c = np.interp(Vt, vbc, np.where(np.isfinite(b0), w0, 0.0)) * (np.interp(Vt, vbc, np.isfinite(b0).astype(float)) > 0.99)
    w0c = a.fit_w * w0c / max(w0c.max(), 1e-9)
    ss = (1.0 / h) ** 4 * 2.0
    Ucz0 = smooth_curve(v0c, w0c, uD0, ss * 0.5, 0.02)
    czw = floats(a.cz_width)
    # 小さな波（右の脇の低い行など）では唇が短いので、帯を唇の長さに比べて縮める（第 2 版。右の脇で帯が唇の全部を覆い、原画視点の管の右の縁に
    # 淡い水色の帯と角ばった舌の頭が出たのを直す）
    lipL = uF2 - uF1
    sbd = np.clip(lipL / a.band_rel, 0.25, 1.0) if a.band_rel > 0 else np.ones_like(lipL)
    Ucz0 = np.clip(Ucz0, uF1 + 0.5 * sbd, uF1 + a.cz0_max * sbd)
    kn2 = np.arange(V0 - 3, V1 + 3, 3.0)
    Ucz1 = Ucz0 + sbd * np.interp(Vt, kn2, czw[0] + (czw[1] - czw[0]) * rng.random(len(kn2)))
    print("lip length p5/p50/p95", np.percentile(lipL, [5, 50, 95]).round(2).tolist(), "band scale<1 cols", int((sbd < 0.999).sum()), "of", len(sbd))
    print("boundaries", round(time.time() - t_start, 1))
    # ---------------- 原画の藍中の線：向きと間隔 → 面の上の目標（第 1 版と同じ）
    sk = np.load(WORK + "target_skel.npz")
    allx = []; ally = []; allc = []
    for ci in range(int(sk["n"])):
        allx.append(sk[f"x{ci}"]); ally.append(sk[f"y{ci}"]); allc.append(np.full(len(sk[f"x{ci}"]), ci))
    allx = np.concatenate(allx).astype(float); ally = np.concatenate(ally).astype(float); allc = np.concatenate(allc)
    xy = np.stack([allx, ally], 1)
    kd = cKDTree(xy)
    tang = np.zeros((len(xy), 2))
    for i, nbr in enumerate(kd.query_ball_point(xy, r=5.0)):
        nbr = [j for j in nbr if allc[j] == allc[i]]
        if len(nbr) < 3:
            continue
        q = xy[nbr] - xy[nbr].mean(0)
        _, v_ = np.linalg.eigh(q.T @ q)
        tang[i] = v_[:, 1]
    nimg = np.stack([-tang[:, 1], tang[:, 0]], 1)
    sp_img = np.full(len(xy), np.nan)
    for i, nbr in enumerate(kd.query_ball_point(xy, r=90.0)):
        if not np.any(tang[i]):
            continue
        nbr = np.array([j for j in nbr if allc[j] != allc[i]], int)
        if len(nbr) == 0:
            continue
        d = xy[nbr] - xy[i]
        dist = np.linalg.norm(d, axis=1)
        sel_ = np.abs(d @ nimg[i]) / np.maximum(dist, 1e-6) > np.cos(np.radians(25))
        if sel_.any():
            sp_img[i] = dist[sel_].min()
    xi = allx.astype(int); yi = ally.astype(int)
    okd = okp[yi, xi] & face[yi, xi] & (aniso[yi, xi] < a.aniso_max) & np.any(tang != 0, 1) & np.isfinite(gUx[yi, xi]) & np.isfinite(gVx[yi, xi])
    J = np.stack([np.stack([gUx[yi, xi], gUy[yi, xi]], -1), np.stack([gVx[yi, xi], gVy[yi, xi]], -1)], 1)
    t_uv = np.einsum("nij,nj->ni", J, tang)
    t_len = np.linalg.norm(t_uv, axis=1)
    okd &= t_len > 1e-6
    t_uv = t_uv / np.maximum(t_len[:, None], 1e-9)
    n_uv = np.stack([-t_uv[:, 1], t_uv[:, 0]], 1)
    n_uv *= np.sign(n_uv[:, 1] + 1e-9)[:, None]
    rot = np.degrees(np.arctan2(np.abs(n_uv[:, 0]), n_uv[:, 1]))
    okd &= rot < a.max_rot
    sp_uv = np.linalg.norm(np.einsum("nij,nj->ni", J, nimg) * sp_img[:, None], axis=1)
    lc = floats(a.lam_clip)
    lam_p = np.where(np.isfinite(sp_uv), np.clip(sp_uv, lc[0], lc[1]), a.lam0)
    conf = np.nan_to_num(okd / (1.0 + 0.5 * (aniso[yi, xi] - 1.0)))
    pu_ = Up[yi, xi].astype(float); pv_ = Vp[yi, xi].astype(float)
    sel = conf > 0
    nn = n_uv[sel]
    cp = conf[sel]; pu_s = pu_[sel]; pv_s = pv_[sel]; lam_s = lam_p[sel]
    print("stripe data", int(sel.sum()), "rot p50/p90", np.percentile(rot[okd], [50, 90]).round(1).tolist(),
          "lam p10/p50/p90", np.percentile(lam_s, [10, 50, 90]).round(2).tolist())
    # ---------------- 粗い格子の向きの場：データのテンソル（σ）＋事前、さらにテンソルを σ_b で平らにする
    hp = a.hp
    nU = int(np.ceil((U1 - U0) / hp)) + 1
    nV = int(np.ceil((V1 - V0) / hp)) + 1
    gu_c = U0 + hp * np.arange(nU); gv_c = V0 + hp * np.arange(nV)
    Txx = np.zeros((nU, nV)); Txy = np.zeros((nU, nV)); Tyy = np.zeros((nU, nV)); Til = np.zeros((nU, nV)); accW = np.zeros((nU, nV))
    rad = int(np.ceil(3 * a.sigma / hp))
    iu = np.round((pu_s - U0) / hp).astype(int); iv = np.round((pv_s - V0) / hp).astype(int)
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
            np.add.at(Til, (ic, jc), wk / lam_s)
            np.add.at(accW, (ic, jc), wk)
    wpr = a.w_prior * np.percentile(accW[accW > 0], 90) if (accW > 0).any() else 1.0
    # 背（頂の線 uB より後ろ）は原画のデータを使わない（原画の線は前の面のもの）
    UUc = gu_c[:, None] + 0 * gv_c[None, :]
    uBc = np.interp(gv_c, Vt, uB)[None, :]
    back_c = UUc < uBc + 0.5
    for T_ in (Txx, Txy, Tyy, Til, accW):
        T_[back_c] = 0.0
    lamprior = np.where(back_c, a.lam_back, a.lam0)
    Tyy = Tyy + wpr
    Til = Til + wpr / lamprior
    accW = accW + wpr
    sb = a.blur / hp
    if sb > 0:
        Txx = gaussian_filter(Txx, sb, mode="nearest"); Txy = gaussian_filter(Txy, sb, mode="nearest"); Tyy = gaussian_filter(Tyy, sb, mode="nearest")
        Til = gaussian_filter(Til, sb, mode="nearest"); accW = gaussian_filter(accW, sb, mode="nearest")
    ang = 0.5 * np.arctan2(2 * Txy, Txx - Tyy)
    nUx = np.cos(ang); nVy = np.sin(ang)
    sgn = np.where(nVy < 0, -1.0, 1.0)
    nUx *= sgn; nVy *= sgn
    invlam = Til / accW
    lam_g = np.clip(1.0 / invlam, lc[0], lc[1])
    lam_g = np.where(back_c, a.lam_back, lam_g)
    # ---------------- 面の計量 M（(u, w) の 1 歩が面の上で何 m か）：三角形ごと → 頂点 → テクセル（第 1 版と同じ）
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
    Muu = Gww / dG; Muw = -Guw / dG; Mww = Guu / dG
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

    def metric(uq, wq):
        i = min(max(int(round((uq - U0) / h)), 0), Hd - 1); j = min(max(int(round((wq - V0) / h)), 0), Wd - 1)
        return Mt[i, j]

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
        lam = bl(lam_g)
        if a.lam_grow > 0:
            duq = uq - float(np.interp(wq, Vt, Ucz1))
            if duq > 0:
                lam *= 1.0 + duq / a.lam_grow
        return tx, ty, lam

    def valid_at(uq, wq):
        i = int(round((uq - U0) / h)); j = int(round((wq - V0) / h))
        return 0 <= i < Hd and 0 <= j < Wd and bool(validt[i, j])

    def F_at(uq, wq):
        i = min(max(int(round((uq - U0) / h)), 0), Hd - 1); j = min(max(int(round((wq - V0) / h)), 0), Wd - 1)
        return float(Ft[i, j]) if validt[i, j] else np.nan
    # ---------------- 流線（間を面の上の m で測る）
    cellg = 0.3
    occ = {}

    def occ_add(pts, lid):
        for (uq, wq) in pts:
            occ.setdefault((int(uq // cellg), int(wq // cellg)), []).append((uq, wq, lid))

    def near_dist(uq, wq, rmax, skip=None):
        M = metric(uq, wq)
        ci, cj = int(uq // cellg), int(wq // cellg)
        rr = int(np.ceil(rmax / cellg / np.sqrt(min(M[0], M[2]))))
        best = 1e18
        for di in range(-rr, rr + 1):
            for dj in range(-rr, rr + 1):
                for (u2, w2, l2) in occ.get((ci + di, cj + dj), ()):
                    if l2 == skip:
                        continue
                    du_, dw_ = u2 - uq, w2 - wq
                    dd = du_ * du_ * M[0] + 2 * du_ * dw_ * M[1] + dw_ * dw_ * M[2]
                    if dd < best:
                        best = dd
        return best ** 0.5
    f4c = np.maximum(uF4, Ucz1 + 6.0)
    step = 0.12

    def trace(u_s, w_s, lid, direction, region, top_lim, Lmax=90.0):
        pts = [(u_s, w_s)]
        uq, wq = u_s, w_s
        L = 0.0
        while L < Lmax:
            tx, ty, lam = field(uq, wq)
            um, wm = uq + 0.5 * step * tx * direction, wq + 0.5 * step * ty * direction
            tx2, ty2, _ = field(um, wm)
            un, wn = uq + step * tx2 * direction, wq + step * ty2 * direction
            if not valid_at(un, wn):
                break
            if region == "front":
                if direction > 0 and un > float(np.interp(wn, Vt, f4c)) + 1.5:
                    break
                if direction < 0 and un < float(np.interp(wn, Vt, Ucz1)) + top_lim:
                    break
            else:
                if direction > 0 and un > float(np.interp(wn, Vt, uB)):
                    break
                fq = F_at(un, wn)
                if direction < 0 and (not np.isfinite(fq) or fq < a.f_back + 0.05):
                    break
            if near_dist(un, wn, a.dtest * lam + 0.1, skip=lid) < a.dtest * lam:
                break
            L += step
            uq, wq = un, wn
            pts.append((uq, wq))
        return pts

    def offset_seed(pt, tx, ty, lam, sgn_):
        nu_, nw_ = -ty * sgn_, tx * sgn_
        M = metric(*pt)
        ln = np.sqrt(max(nu_ * nu_ * M[0] + 2 * nu_ * nw_ * M[1] + nw_ * nw_ * M[2], 1e-6))
        return pt[0] + lam * nu_ / ln, pt[1] + lam * nw_ / ln

    lines = []        # (pts, kind)：0 前・帯の縁から、1 前・間に生まれた、2 背・頂の後ろから、3 背・間に生まれた
    for region, kind0 in (("front", 0), ("back", 2)):
        queue = []
        wq = V0 + 0.5
        while wq < V1 - 0.5:
            uq = float(np.interp(wq, Vt, Ucz1)) if region == "front" else float(np.interp(wq, Vt, uB)) - 0.2
            if valid_at(uq, wq):
                queue.append((uq, wq, kind0))
            _, _, lam = field(uq, wq)
            M = metric(uq, wq)
            jit = 1.0 + a.seed_jit * (2 * rng.random() - 1) if region == "front" else 1.0
            wq += jit * lam / np.sqrt(max(M[2], 0.2))
        qi = 0
        while qi < len(queue) and len(lines) < 6000:
            uq, wq, kind = queue[qi]; qi += 1
            if not valid_at(uq, wq):
                continue
            if region == "front" and uq < float(np.interp(wq, Vt, Ucz1)) + (a.fill_top if kind == 1 else -0.05):
                continue
            if region == "back" and uq > float(np.interp(wq, Vt, uB)):
                continue
            _, _, lam = field(uq, wq)
            if near_dist(uq, wq, a.dsep * lam + 0.1) < a.dsep * lam:
                continue
            lid = len(lines)
            if kind == 0:
                Lmax = a.early[1] + (a.early[2] - a.early[1]) * rng.random() if rng.random() < a.early[0] else 90.0
                pts = trace(uq, wq, lid, 1, region, a.fill_top, Lmax)
            elif kind == 2:
                pts = trace(uq, wq, lid, -1, region, 0)
            else:
                fw = trace(uq, wq, lid, 1, region, a.fill_top)
                bw = trace(uq, wq, lid, -1, region, a.fill_top)
                pts = bw[::-1] + fw[1:]
            if kind == 2:
                pts = pts[::-1]      # 背の線も U の増える向きにそろえる（始まり＝背の足の側）
            pts = np.array(pts)
            if len(pts) * step < 2.0:
                continue
            lines.append((pts, kind))
            occ_add(pts, lid)
            for k in range(0, len(pts), max(1, int(1.0 / step))):
                tx, ty, lam = field(*pts[k])
                for sgn_ in (-1, 1):
                    su, sw = offset_seed(pts[k], tx, ty, lam, sgn_)
                    queue.append((su, sw, 1 if region == "front" else 3))
    kind_l = np.array([k for (_, k) in lines])
    print("streamlines", len(lines), "kinds", np.bincount(kind_l, minlength=4).tolist(), round(time.time() - t_start, 1))
    # ---------------- 流線を平らにする（端は留める）→ 0.08 m おきの点
    win = max(1, int(round(a.smooth_win / step)))
    LP = []; LI = []; LS = []; LL = []
    for lid, (pts, kind) in enumerate(lines):
        q = pts.copy()
        if len(q) > 2 * win + 2:
            ker = np.ones(2 * win + 1) / (2 * win + 1)
            for _ in range(2):
                qq = q.copy()
                for c_ in range(2):
                    pad = np.concatenate([np.full(win, q[0, c_]), q[:, c_], np.full(win, q[-1, c_])])
                    qq[:, c_] = np.convolve(pad, ker, mode="valid")
                qq[0] = q[0]; qq[-1] = q[-1]
                q = qq
        seg = np.linalg.norm(np.diff(q, axis=0), axis=1)
        sacc = np.concatenate([[0], np.cumsum(seg)])
        L = sacc[-1]
        ss_ = np.arange(0, L, 0.08)
        LP.append(np.stack([np.interp(ss_, sacc, q[:, 0]), np.interp(ss_, sacc, q[:, 1])], 1))
        LI.append(np.full(len(ss_), lid)); LS.append(ss_); LL.append(np.full(len(ss_), L))
    LP = np.concatenate(LP); LI = np.concatenate(LI); LS = np.concatenate(LS); LL = np.concatenate(LL)
    nl = len(lines)
    rr1, rr2, rr3 = rng.random(nl), rng.random(nl), rng.random(nl)
    hw_l = a.hw[0] + a.hw[1] * rr1
    hw_l = np.where(rr2 < a.hw[2], a.hw[3] + a.hw[4] * rr3, hw_l)
    backl = kind_l >= 2
    hw_l = np.where(backl, a.hw_back[0] + a.hw_back[1] * rr1, hw_l)
    kdl = cKDTree(LP)
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
        lid = LI[iqc]; s_ = LS[iqc]; L_ = LL[iqc]; kd_ = kind_l[lid]
        tap_end = np.sqrt(np.clip((L_ - s_) / a.end_taper, 0, 1))
        tap_st = np.where(kd_ == 0, 1.0, np.where(kd_ == 2, 1.0, np.sqrt(np.clip(s_ / 2.0, 0, 1))))
        if True:   # 背の線は背の足の側（始まり）で細る。頂の側（終わり）は白の下なので細らせない
            tap_end = np.where(kd_ == 2, 1.0, tap_end)
            tap_st = np.where(kd_ == 2, np.sqrt(np.clip(s_ / a.end_taper, 0, 1)), tap_st)
        dist_m[r0:r1_] = np.where(okq, dm, 9.0).reshape(r1_ - r0, Wd)
        hwl = hw_l[lid]
        hwl = np.where(kd_ == 0, hwl + np.maximum(a.top_wedge[0] - hwl, 0) * np.exp(-s_ / a.top_wedge[1]), hwl)
        hw[r0:r1_] = np.where(okq, hwl * tap_end * tap_st, 0.0).reshape(r1_ - r0, Wd)
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
    cz1 = Ucz1[None, :].astype(np.float32); cz0 = Ucz0[None, :].astype(np.float32); ub = uB[None, :].astype(np.float32)
    du = UU - cz1
    a_side = dist_m - hw
    Wt = np.minimum(dist_m + d2_m, 2.2 * lamt)
    theta = np.clip(dist_m / np.maximum(Wt, 1e-3), 0, 0.5)
    hpair = np.where(pair >= 0, ((pair * 2654435761) % 1000003) / 1000003.0, 0.5).astype(np.float32)
    t_m = a.tip_lo + (a.tip_hi - a.tip_lo) * hpair
    arch = np.minimum(np.maximum(0.5 * Wt - hw, 0.1) * a.arch, a.arch_max) * np.sqrt(np.clip(1 - (1 - 2 * theta) ** 2, 0, 1))
    # 舌の頭（第 2 版）：帯の縁 U_cz1 から始まる線の始まりの w を並べ、隣り合う 2 本の間を 1 枚の舌とし、
    # その頭を半楕円（幅 = 舌の幅、高さ = head[0] × 半幅、上限 head[1] m）で帯へ食い込ませる。舌ごとに付け根を t（tip-lo〜tip-hi）ずらす。
    st = np.array([lines[k][0][0] for k in range(nl) if kind_l[k] == 0])
    st = st[np.argsort(st[:, 1])]
    hb = np.full(Wd, np.nan, np.float32)
    nt = len(st) - 1
    tk = a.tip_lo + (a.tip_hi - a.tip_lo) * rng.random(max(nt, 1))
    for k in range(nt):
        wa, wb = st[k, 1], st[k + 1, 1]
        b_ = 0.5 * (wb - wa)
        j0 = max(int(np.ceil((wa - V0) / h)), 0); j1 = min(int(np.floor((wb - V0) / h)), Wd - 1)
        if j1 < j0:
            continue
        vv = V0 + h * np.arange(j0, j1 + 1)
        if b_ > a.head[2]:
            # 広すぎる間（線の始まりが無い所）は平らな縁、端だけ丸める
            x_ = np.minimum(vv - wa, wb - vv)
            Hh = np.minimum(a.head[0] * a.head[2], a.head[1]) * np.interp(vv, Vt, sbd) * np.sqrt(np.clip(1 - (1 - np.clip(x_ / a.head[2], 0, 1)) ** 2, 0, 1))
        else:
            xx_ = (vv - 0.5 * (wa + wb)) / max(b_, 1e-3)
            hv = 1.0 + a.head_var * (2 * rng.random() - 1)
            sbk = float(np.interp(0.5 * (wa + wb), Vt, sbd))
            Hh = min(a.head[0] * hv * b_, a.head[1]) * sbk * np.sqrt(np.clip(1 - xx_ ** 2, 0, 1))
        hb[j0:j1 + 1] = tk[k] * float(np.interp(0.5 * (wa + wb), Vt, sbd)) - Hh
    hb = np.where(np.isfinite(hb), hb, 0.0).astype(np.float32)
    Dhead = (du - hb[None, :]).astype(np.float32)
    Dfront = round_intersect(a_side, Dhead, np.full_like(a_side, 0.12))
    backside = UU < 0.5 * (ub + cz0)
    Ddark = np.where(backside, a_side, Dfront).astype(np.float32)
    Dmiz = (cz1 + a.miz_off - UU).astype(np.float32)
    Dmiz = np.where(backside, -1.0, Dmiz).astype(np.float32)
    Dwhite = (cz0 + a.lobe * (2 * theta) ** 2 - UU).astype(np.float32)
    # ---------------- 白い点（面の上の m の円）
    Ddot = np.full((Hd, Wd), -1.0, np.float32)
    cell = a.dot_cell
    gu_ = np.arange(U0, U1, cell); gv_ = np.arange(V0, V1, cell)
    CU, CV = np.meshgrid(gu_, gv_, indexing="ij")
    CU = CU.ravel() + cell * (0.1 + 0.8 * rng.random(CU.size)); CV = CV.ravel() + cell * (0.1 + 0.8 * rng.random(CV.size))
    pd = a.dots
    iu2 = np.clip(((CU - U0) / h).astype(int), 0, Hd - 1); iv2 = np.clip(((CV - V0) / h).astype(int), 0, Wd - 1)
    duu = CU - Ucz1[iv2]
    prob = np.clip(pd[0] - pd[1] * duu, pd[2], pd[0])
    prob = np.where(backside[iu2, iv2], pd[3], prob)
    radd = pd[4] + pd[5] * rng.random(CU.size) ** 1.7 * np.clip(1.2 - 0.03 * np.maximum(duu, 0), 0.5, 1.2)
    if a.dot_v2 is not None:
        dv = a.dot_v2
        # 帯の縁（舌の頭）から下へ指数で減る。群れ：(u, w) の 2 つの斜めの波の積（面の上の m。視点によらない）
        ph1, ph2 = rng.random(2) * 6.2831853
        lamc = max(dv[2], 0.5)
        clus = np.sin(6.2831853 * (CU + 0.6 * CV) / lamc + ph1) * np.sin(6.2831853 * (CV - 0.4 * CU) / (1.37 * lamc) + ph2)
        prob = pd[0] * np.exp(-np.maximum(duu, 0) / max(dv[0], 0.1)) * np.clip(1.0 + dv[1] * clus, 0.0, 2.0)
        prob = np.where(backside[iu2, iv2], pd[3], np.clip(prob, 0.0, 0.95))
        radd = dv[3] + dv[4] * rng.random(CU.size) ** dv[5] * np.clip(1.15 - 0.04 * np.maximum(duu, 0), 0.45, 1.15)
    keep = (Ddark[iu2, iv2] > radd + 0.07) & validt[iu2, iv2] & (rng.random(CU.size) < prob)
    CU, CV, radd = CU[keep], CV[keep], radd[keep]
    K = int(np.ceil(0.2 / h)) + 1
    for du_i in range(-K, K + 1):
        for dv_i in range(-K, K + 1):
            ii = np.clip(((CU - U0) / h).round().astype(int) + du_i, 0, Hd - 1)
            jj = np.clip(((CV - V0) / h).round().astype(int) + dv_i, 0, Wd - 1)
            mm = Mt[ii, jj]
            dU = U0 + h * ii - CU; dV = V0 + h * jj - CV
            dmet = np.sqrt(np.maximum(dU * dU * mm[:, 0] + 2 * dU * dV * mm[:, 1] + dV * dV * mm[:, 2], 0))
            np.maximum.at(Ddot, (ii, jj), (radd - dmet).astype(np.float32))
    print("dots", len(CU), round(time.time() - t_start, 1))
    tex = np.stack([np.clip(Dwhite, -4, 4), np.clip(Dmiz, -4, 4), np.clip(Ddark, -4, 4), np.clip(Ddot, -4, 4)], -1).astype(np.float16)
    tex.tofile(os.path.join(a.out, "s01b_design_f16.bin"))
    attr = A.astype(np.float32).copy()
    attr[:, 6] = UV[:, 0]; attr[:, 7] = UV[:, 1]
    attr.tofile(os.path.join(a.out, "s01b_attr_f32.bin"))
    # ---------------- 数：線の 3 次元の間（線の点から別の線までの面の上の m。前の舌の帯と背の胴）
    stats = {}
    for name, ksel in (("front", kind_l < 2), ("back", kind_l >= 2)):
        msk = ksel[LI]
        if msk.sum() < 10:
            continue
        P_ = LP[msk][::5]; Li_ = LI[msk][::5]
        dd, ii2 = kd2.query(P_, k=40, distance_upper_bound=8.0)
        okk = np.isfinite(dd) & (LI2[np.where(np.isfinite(dd), ii2, 0)] != Li_[:, None])
        fst = np.where(okk.any(1), okk.argmax(1), -1)
        hv = fst >= 0
        j_ = ii2[np.arange(len(P_)), np.maximum(fst, 0)][hv]
        iu3 = np.clip(((P_[hv, 0] - U0) / h).astype(int), 0, Hd - 1); iv3 = np.clip(((P_[hv, 1] - V0) / h).astype(int), 0, Wd - 1)
        d3 = mlen(P_[hv] - LP2[j_], Mt[iu3, iv3])
        stats[name] = dict(lines=int(ksel.sum()), nearest_other_line_m_p10_p50_p90=np.percentile(d3, [10, 50, 90]).round(2).tolist())
    meta = dict(schema="GreatWave.Sample01B.design/4", param=pinfo, U0=float(U0), V0=float(V0), h=h, rows_U=Hd, cols_V=Wd,
                channels=["Dwhite m", "Dmizuiro m", "Ddark m", "Ddot m"], layout="row-major, row = U index (U0 + h*i), col = V index (V0 + h*j), RGBA half",
                args=vars(a), stripe_data_points=int(sel.sum()), streamlines=len(lines),
                streamlines_by_kind=np.bincount(kind_l, minlength=4).tolist(), spacing=stats,
                dots=int(len(CU)), design_sha256=S.sha256(os.path.join(a.out, "s01b_design_f16.bin")),
                attr_sha256=S.sha256(os.path.join(a.out, "s01b_attr_f32.bin")), seconds=time.time() - t_start)
    json.dump(meta, open(os.path.join(a.out, "s01b_design.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    np.savez_compressed(os.path.join(a.out, "s01b_curves.npz"), Vt=Vt, Ucz0=Ucz0, Ucz1=Ucz1, uF1=uF1, uF4=uF4, uB=uB, U0=U0, V0=V0, hp=hp)
    print(json.dumps(stats))
    # ---------------- 図：(U, V) の平面の設計（縮小）
    col = np.zeros((Hd, Wd, 3), np.uint8)
    pal = dict(white=(251, 246, 227), miz=(192, 211, 199), mid=(41, 105, 148), dark=(34, 63, 96))
    col[:] = pal["mid"]
    col[Ddark > 0] = pal["dark"]
    col[(Ddot > 0) & (Ddark > 0)] = pal["white"]
    col[(Dmiz > 0) & ~(Ddark > 0)] = pal["miz"]
    col[(Dwhite > 0) & ~backside] = pal["white"]
    col[~validt] = (90, 90, 90)
    for arr, c_ in ((Ucz0, (255, 160, 0)), (Ucz1, (0, 200, 0)), (uF1, (200, 0, 200)), (uF4, (200, 0, 200)), (uF2, (120, 0, 200)), (uB, (255, 0, 0))):
        ii = ((arr - U0) / h)
        okk = np.isfinite(ii)
        col[np.clip(ii[okk].astype(int), 0, Hd - 1), np.arange(Wd)[okk]] = c_
    Image.fromarray(col).resize((Wd // 2, Hd // 2), Image.NEAREST).save(os.path.join(a.out, "s01b_design_uv.png"))
    print("done", round(time.time() - t_start, 1))


if __name__ == "__main__":
    main()
