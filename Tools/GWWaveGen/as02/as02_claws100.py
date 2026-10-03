# -*- coding: utf-8 -*-
"""美術の見本02（Q30-1・Q30-2）爪の部：利用者が爪形分析で原画から切り出した 100 本の爪を、1 本ずつ 3D の爪に戻し、
t*（τ = 0）の主役波 K*′ P28R2rec（仕上げ32 の hero_pkg、時間曲線 G_p28rec）の、原画のその位置に当たる所へ置く。

入力（読み取りのみ）：
  - G:/research/爪形分析/final_100_claws_centerlines_from_fill_masks_v3/clawNNN/{fill_mask.png, centerline_raw.csv}
    （利用者の塗りのマスクと中心線。D14・D23：画像・マスクはリポジトリへ写さない。ここではメモリの中で使うだけ）
  - 同 final_100_claw_structural_points_v2/final_points_long.csv（利用者の構造点 S…T）
  - 仕上げ32 の位置合わせ（切り抜き → 原画 DP130155 の 2×3）：Build/Design/32/list+ids/ds32_user100_registration.json と、
    修正の回 1 で当て直した 9 本（Build/Polish/32/fix01/list/ds32_user100_correspondence_pl32f.json の pl32f.reregister）
  - 利用者の爪の模型を測った水準 Build/Polish/sample02/claws/user_claw_standard.json（as02_user_claw_standard.py）
  - 参照モデルから測った置き方の数 Build/Polish/sample02/claws/ref/as02_ref_claw_placement_r0.7.json（as02_ref_claws.py。数だけ。OBJ は読まない、F13-1）
  - 主役波（as01 の claws_common.load_hero：Build/Polish/32/white/hero_pkg の τ = 0）、原画のカメラ PaintingCam v1
作り方（1 本ずつ）：
  1. 2 次元（切り抜きの画素）：利用者の中心線を背骨にし（先が塗りの先まで届かない時は、塗りの中の真ん中を通る道で先まで延ばす）、
     背骨に直交する向きに塗りの縁まで測って幅と真ん中を求め、真ん中へ寄せてならす（2 回）。先の 25% は利用者の模型の細りの法則
     （w ∝ u^p、u は先からの長さの割合）を上限にして鋭い先にする。根元の外側（巻きの外）に模型のかかとと同じ割合の小さなかかとを足す。
  2. 3 次元：原画のカメラから根元の画素の射線を主役波に当て（根元は面の上）、爪の面を平面 Π に置く。Π は根元を通り、
     画面の根元の向き τ に当たる 3D の向き D1 = cos α τ3 + sin α (−v)、画面の直交の向き ν に当たる D2 = cos β ν3 + sin β (−v) で張る
     （v は射線の向き。α・β はカメラへ起こす角）。爪のどの点も、その画素の射線と Π の交わりに置くので、原画のカメラからの影は 2 次元の形と同じ。
     α・β は、根元の向きと面の法線の角が参照モデルの値（θ_t）に近く、爪が面の中へ潜らず、Π がカメラに対して斜めになりすぎない
     （引き伸ばし 1/|m·v| ≤ STRETCH_MAX）ものを格子で選ぶ。
  3. 断面：利用者の模型の割合のレンズ形（幅 : 厚み ≈ 1.3、先で 1.6）。輪の 8 頂点（設計33 の並び。PL29 Claw Shade の色の段は頂点の番号で決まる）。
     根元は射線の奥へ少し沈めて面に埋める（原画のカメラからの形は変わらない）。
出力（Git 対象外）：--out（既定 Unity/Build/Polish/sample02/claws/mesh）に ds33_claw_layout.json の書式（コマ 1 つ＝t* の静止）、
  as02_claws.obj（同じ形）、as02_claws_report.json（爪ごとの記録：位置合わせ、根元、α・β、角、長さ、IoU、水準の検査）、as02_entries.npy（下見用）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_claws100.py [--out DIR]
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time

import cv2
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import claws_common as CC  # noqa: E402
from as02_mini_render import outline_lumps  # noqa: E402

U = CC.U
USER = "G:/research/爪形分析"
CROPS = USER + "/final_100_claws_centerlines_from_fill_masks_v3"
POINTS = USER + "/final_100_claw_structural_points_v2/final_points_long.csv"
REG = REPO + "/Unity/Build/Design/32/list+ids/ds32_user100_registration.json"
CORR = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_user100_correspondence_pl32f.json"
STD = REPO + "/Unity/Build/Polish/sample02/claws/user_claw_standard.json"
REFP = REPO + "/Unity/Build/Polish/sample02/claws/ref/as02_ref_claw_placement_r0.7.json"
OUTD = REPO + "/Unity/Build/Polish/sample02/claws/mesh"
RING = 8

P = dict(
    TAPER_P=0.63,          # 先の細りの法則 w ∝ u^p（claw_low の先 30% の当てはめ。user_claw_standard.json）
    TAPER_U=0.25,          # 法則を上限にする先の範囲（長さの割合）
    RATIO_MID=1.30,        # 断面の幅 : 厚み（claw_mid 1.27・claw_low 1.31 の中ほど 60% の中央値）
    RATIO_TIP=1.60,        # 先の幅 : 厚み（claw_low の先 10% で 1.25 → 1.53）
    LENS_A=0.78, LENS_B=0.72,   # 輪の ±45° の頂点の位置（幅・厚みの割合）。塗りの割合 (A+B)/2 = 0.75（模型の断面の塗り 0.74〜0.81）
    HEEL_H=0.16,           # かかとの出っ張り / 最大幅（claw_low 0.144・claw_mid 0.244 の間の下寄り）
    HEEL_S=0.07, HEEL_W=0.05,   # かかとの位置と幅（長さの割合）
    THETA_T=24.0,          # 根元の向きと面の法線の角の目標（参照モデル：p50 18.1°（開く半径 0.42 m）・23.7°（0.7 m）・29.8°（1.0 m））
    STRETCH_MAX=2.30,      # Π の引き伸ばし 1/|m·v| のふだんの上限（カメラに対して約 64° まで）。これを超えると費用を強く足す
    STRETCH_HARD=3.30,     # 引き伸ばしの絶対の上限（面へ潜るのを避けるためだけに、約 72° まで）
    SINK=1.0,              # 根元を射線の奥へ沈める量 / 根元の厚みの半分
    SINK_S=0.10,           # 沈める範囲（長さの割合）
    CLEAR=0.02,            # 根元の範囲の外で、面からの高さ ≥ 厚みの半分 + CLEAR [m]
    ST_MIN=24, ST_MAX=48,  # 輪の数
    N_ORTHO=0.5,           # 断面の厚みの向き：射線の向きを接線から直交させる割合（1 で直交、0 で射線そのもの）
    FOOT=1.2,              # 根元の足の厚み / 中ほどの幅（claw_mid：足の厚み ≈ 最大幅の 0.95 倍、指の中ほどの幅は最大幅の約 0.7 倍）
    FOOT_S0=0.08, FOOT_S1=0.30,   # 足の厚みが減り始める所と、減り終わるまでの長さ（割合）
    ROOT_TH_CAP=1.0,       # 厚みの上限：中ほどの幅 × この値 / 比（根元の広い所が塊にならないように）
    SPLINE_TOL=0.05,       # 輪郭の平滑化スプラインの残差の目安 / 中ほどの幅
    OUTLINE_SMOOTH=0.025,  # 輪郭の鎖のならしの σ（長さの割合。マスクの手描きの小さなでこぼこを消す）
    SMOOTH_W=0.025,        # 幅のならしの σ（長さの割合）
    SMOOTH_C=0.03,         # 真ん中の線のならしの σ（長さの割合）
    ROOT_SEARCH_PX=8.0,    # 根元の画素が主役波に当たらない時、背骨に沿って探す長さ（表示の px）
    DUP_FRAC=0.6,          # 重複とみなす原画視点の影の重なり（小さい方の面積の割合）
    HOVER=0.30,            # 案 C：面からの浮き H = HOVER × 爪の長さ（画面の長さを根元の深さで m にしたもの）
    HOVER_SR=0.35,         # 案 C：浮きが H に届く長さの割合
    HOVER_COSMIN=0.30,     # 案 C：射線と法線の内積の下限（面を斜めから見る所で、射線の上の移動が大きくなりすぎないように）
    HOVER_MAXOFF=1.0,      # 案 C：射線の上でカメラへ寄せる量の上限 / 爪の長さ
    MODE="paint",          # paint：原画視点の影を守る（射線の上で奥行きだけ動かす）。ref：参照モデルの置き方を優先（硬く回して法線から THETA_T へ起こす）
)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def imread_u(p, flag):
    return cv2.imdecode(np.fromfile(p, np.uint8), flag)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / max(np.linalg.norm(v), 1e-12)


def resample_poly(Pp, n):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]
    s = np.linspace(0, d[-1], n)
    return np.stack([np.interp(s, d, Pp[:, k]) for k in range(Pp.shape[1])], -1), d[-1]


def gsmooth_keep_ends(Pp, sig):
    """端を固定したガウスのならし（端の向きを保つため、端の外へ点で鏡映してから）。"""
    if sig <= 0:
        return Pp.copy()
    sig = min(sig, max((len(Pp) - 2) / 3.0, 0.5))      # 短い点列で鏡映がはみ出さないように（今までの爪では効かない）
    k = int(np.ceil(3 * sig))
    a = 2 * Pp[0] - Pp[1:k + 1][::-1]
    b = 2 * Pp[-1] - Pp[-k - 1:-1][::-1]
    Q = np.vstack([a, Pp, b])
    Q = ndimage.gaussian_filter1d(Q, sig, axis=0, mode="nearest")
    return Q[k:k + len(Pp)]


# ---------------------------------------------------------------- 利用者のデータ
def load_user():
    reg = json.load(open(REG, encoding="utf-8"))
    corr = json.load(open(CORR, encoding="utf-8"))
    rr = corr["pl32f"]["reregister"]
    status = {c["user_id"]: c for c in corr["claws"]}
    add = {a["user_id"]: a for a in corr["pl32f"]["additions"]}
    pts = {}
    for r in csv.DictReader(open(POINTS, encoding="utf-8-sig")):
        pts.setdefault(r["claw_id"], []).append((int(r["point_order"]), r["label"], float(r["x"]), float(r["y"])))
    out = []
    for c in reg["claws"]:
        uid = c["user_id"]
        A = np.array(c["A_crop_to_ref"], np.float64)
        ncc = c["ncc_after_ecc"]
        src = "ds32"
        if uid in rr:
            A = np.array(rr[uid]["A_crop_to_ref"], np.float64)
            ncc = rr[uid]["ncc_after_ecc"]
            src = "pl32f_reregister"
        d = CROPS + "/" + uid
        out.append(dict(uid=uid, A=A, ncc=ncc, reg_src=src, dir=d, status=status.get(uid, {}), addition=add.get(uid),
                        points=sorted(pts.get(uid, []))))
    return out, reg, corr


def crop_to_disp(A, q):
    q = np.asarray(q, np.float64)
    r = q @ A[:, :2].T + A[:, 2]
    return U.to_disp(r)


def disp_affine(A):
    """切り抜きの画素 → 表示の画素 の 2×3。"""
    s = U.A_DISP
    M = s * A.copy()
    M[0, 2] += s * 0.5 - 0.5 + 156.66152659984573
    M[1, 2] += s * 0.5 - 0.5
    return M


# ---------------------------------------------------------------- 2 次元の形
def medial_path(mask, dt, a, b):
    """塗りの中で a → b を、真ん中を通る道（費用 1/(dt+0.5)）で結ぶ。点は (x, y)。"""
    from skimage.graph import MCP_Geometric
    cost = np.where(mask, 1.0 / (dt + 0.5), np.inf)
    m = MCP_Geometric(cost)
    m.find_costs([(int(round(a[1])), int(round(a[0])))], [(int(round(b[1])), int(round(b[0])))])
    path = m.traceback((int(round(b[1])), int(round(b[0]))))
    return np.array([(p[1], p[0]) for p in path], np.float64)


def geodesic_far(mask, start):
    from skimage.graph import MCP_Geometric
    cost = np.where(mask, 1.0, np.inf)
    m = MCP_Geometric(cost)
    d, _ = m.find_costs([(int(round(start[1])), int(round(start[0])))])
    d = np.where(np.isfinite(d), d, -1)
    y, x = np.unravel_index(np.argmax(d), d.shape)
    return np.array([x, y], np.float64), float(d[y, x])


def bilinear(img, x, y):
    return ndimage.map_coordinates(img, [np.atleast_1d(y), np.atleast_1d(x)], order=1, mode="constant", cval=0.0)


def march(field, p, nu, dmax, step=0.25):
    """p から nu の向きに、field（0〜1、塗り）が 0.5 を切るまでの距離（線形の補間で詰める）。"""
    ts = np.arange(0, dmax + step, step)
    xs = p[0] + nu[0] * ts
    ys = p[1] + nu[1] * ts
    v = bilinear(field, xs, ys)
    out = np.nonzero(v < 0.5)[0]
    if not len(out):
        return dmax
    i = out[0]
    if i == 0:
        return 0.0
    a, b = v[i - 1], v[i]
    return ts[i - 1] + step * (a - 0.5) / max(a - b, 1e-9)


def chain_between(n, a, b, avoid):
    """閉じた輪郭（n 点）の上で、a から b へ、avoid を通らない向きの添字の並び。"""
    fwd = [(a + k) % n for k in range(((b - a) % n) + 1)]
    if avoid not in fwd[1:-1]:
        return fwd
    return [(a - k) % n for k in range(((a - b) % n) + 1)]


def track_param(chain, sp, win):
    """輪郭の鎖の点ごとに、背骨の最も近い点の番号を、前の点の近く（−win/4〜+win）で追って決める（巻きの向こうの腕へ飛ばない）。"""
    ns = len(sp)
    idx = np.zeros(len(chain), int)
    prev = 0
    for i, p in enumerate(chain):
        lo, hi = max(prev - win // 4, 0), min(prev + win, ns - 1)
        d = np.linalg.norm(sp[lo:hi + 1] - p, axis=1)
        prev = lo + int(np.argmin(d))
        idx[i] = prev
    return np.maximum.accumulate(idx)


def chain_at(chain, prm, s_q):
    """鎖（点列）を背骨の割合 prm（非減少）で引き、s_q の点を返す（弧長で補間）。"""
    a = np.r_[0, np.cumsum(np.linalg.norm(np.diff(chain, axis=0), axis=1))]
    x = prm + np.linspace(0, 1e-6, len(prm))
    aq = np.interp(s_q, x, a)
    return np.stack([np.interp(aq, a, chain[:, k]) for k in range(2)], -1)


def spline_fit(C, tol):
    """点列 C を平滑化スプラインで当て直す（端を固定）。tol は残差の二乗平均の目安（px）。"""
    from scipy.interpolate import splprep, splev
    if len(C) < 8 or tol <= 0:
        return C
    Cr, _ = resample_poly(C, max(min(len(C), 400), 16))
    w = np.ones(len(Cr))
    w[:3] = w[-3:] = 50.0
    try:
        tck, u = splprep([Cr[:, 0], Cr[:, 1]], w=w, s=len(Cr) * tol * tol, k=3)
    except Exception:  # noqa: BLE001
        return C
    uu = np.linspace(0, 1, len(C))
    x, y = splev(uu, tck)
    out = np.stack([x, y], -1)
    out[0], out[-1] = C[0], C[-1]
    return out


def per_len(Pp):
    return float(np.sum(np.linalg.norm(np.diff(Pp, axis=0), axis=1)))


def shape2d(c, std):
    """1 本の 2 次元の形（切り抜きの画素）。輪郭の左右の鎖と、背骨の割合で引いた肋（左 L・右 R の点）を返す。
    面から見た形は利用者のマスクの輪郭そのもの（ならしただけ）。背骨は利用者の中心線（先が塗りの先まで届かない時は真ん中の道で延ばす）。"""
    mask0 = imread_u(c["dir"] + "/fill_mask.png", cv2.IMREAD_GRAYSCALE) > 127
    mask0 = ndimage.binary_fill_holes(mask0)
    lab, nl = ndimage.label(mask0)
    if nl > 1:
        sz = ndimage.sum(mask0, lab, range(1, nl + 1))
        mask0 = lab == (1 + int(np.argmax(sz)))
    dt = ndimage.distance_transform_edt(np.pad(mask0, 1))[1:-1, 1:-1]
    cl = np.array([[float(r["x"]), float(r["y"])] for r in csv.DictReader(open(c["dir"] + "/centerline_raw.csv", encoding="utf-8-sig"))])
    cl1, L1 = resample_poly(cl, max(int(np.ceil(np.sum(np.linalg.norm(np.diff(cl, axis=0), axis=1)))), 8))
    rec = {"centerline_len_px": round(float(L1), 2)}
    # 中心線の初めが塗りの縁（切り抜きの枠）に沿って走る所は落とす（根元の開きの真ん中から始める）
    dcl = bilinear(dt, cl1[:, 0], cl1[:, 1])
    thr = max(1.5, 0.3 * float(np.median(dcl)))
    i0 = int(np.argmax(dcl >= thr)) if (dcl >= thr).any() else 0
    rec["root_trim_px"] = int(i0)
    if i0 > 0:
        cl1, L1 = resample_poly(cl1[i0:], max(len(cl1) - i0, 8))
    far, fd = geodesic_far(mask0, cl1[0])
    gap = float(np.linalg.norm(far - cl1[-1]))
    rec["tip_gap_px"] = round(gap, 2)
    if gap > 2.0:
        ext = medial_path(mask0, dt, cl1[-1], far)[1:]
        spine = np.vstack([cl1, ext])
        rec["tip_extended_px"] = round(float(np.sum(np.linalg.norm(np.diff(np.vstack([cl1[-1:], ext]), axis=0), axis=1))), 2)
    else:
        spine = cl1
        rec["tip_extended_px"] = 0.0
    sp, L = resample_poly(spine, max(int(L1 + 8), 30))
    sp = gsmooth_keep_ends(sp, max(2.0, 0.02 * len(sp)))
    sp, L = resample_poly(sp, max(int(L), 40))
    ns = len(sp)
    s_sp = np.linspace(0, 1, ns)
    # 輪郭（画素の縁の上）を 0.5 px ごとに
    C = mask_contour(mask0)
    C, per = resample_poly(np.vstack([C, C[:1]]), max(int(per_len(C) * 2), 60))
    C = C[:-1]
    n = len(C)
    tr = cKDTree(C)
    # 先：背骨の終わりに最も近い輪郭の点
    iT = int(tr.query(sp[-1])[1])
    # 根元の角：最初の背骨の点から ±ν へ輪郭まで
    T0 = unit(sp[min(4, ns - 1)] - sp[0])
    nu0 = np.array([-T0[1], T0[0]])
    field = ndimage.gaussian_filter(mask0.astype(np.float32), 0.7)
    dmax = max(3.0 * float(dt.max()), 6.0)
    pR = sp[0] + nu0 * march(field, sp[0], nu0, dmax)
    pL = sp[0] - nu0 * march(field, sp[0], -nu0, dmax)
    iR = int(tr.query(pR)[1])
    iL = int(tr.query(pL)[1])
    if iR == iL:
        iL = (iR + 2) % n
    chR = chain_between(n, iR, iT, iL)
    chL = chain_between(n, iL, iT, iR)
    cap = chain_between(n, iL, iR, iT)
    CR, CL = C[chR], C[chL]
    # ならす（端は固定）
    sig = max(2.0, P["OUTLINE_SMOOTH"] * L) * 2.0     # 0.5 px ごとの点なので 2 倍
    ok_ = float(P.get("OUTLINE_K", 1.0))              # 修正の回 1（as02_fix01_outline）：爪ごとに輪郭のならしを強める倍率（既定 1 ＝ 今まで）
    sig *= ok_ * float(P.get("GAUSS_K", 1.0))
    sc_ = float(P.get("SHRINK_COMP", 0.0))
    if sc_ > 0:
        # 修正の回 1（as02_fix01_bandpass）：ならした分の動き D = G_σ(C) − C のうち、長い波（σ·SHRINK_COMP より長い：巻き全体の縮みと
        # 体の巻きの内へのずれ）は戻し、短い波（手描きの縁の小さな波）だけを消す。細い指の体がずれて重なりが落ちるのを防ぐ
        def _bp(Cc):
            C1 = gsmooth_keep_ends(Cc, sig)
            D = C1 - Cc
            D2 = gsmooth_keep_ends(D, sig * sc_)
            D2 = D2 - np.linspace(0, 1, len(D2))[:, None] * (D2[-1] - D2[0])[None, :] - D2[0][None, :]   # 端は 0 のまま
            return C1 - D2
        CR = _bp(CR)
        CL = _bp(CL)
    else:
        CR = gsmooth_keep_ends(CR, sig)
        CL = gsmooth_keep_ends(CL, sig)
    # 平滑化スプライン（as02_outline_spline）：手描きのマスクの縁の小さな波を消し、彫った模型のような滑らかな曲線にする。
    # 残差の二乗平均 ≈ (SPLINE_TOL × 中ほどの幅の目安)²。端（根元の角と先）は重みを大きくして動かさない
    w_est = 2.0 * float(np.median(bilinear(dt, sp[:, 0], sp[:, 1])))
    CR = spline_fit(CR, P["SPLINE_TOL"] * ok_ * float(P.get("SPLINE_K", 1.0)) * w_est)
    CL = spline_fit(CL, P["SPLINE_TOL"] * ok_ * float(P.get("SPLINE_K", 1.0)) * w_est)
    win = max(int(0.15 * ns), 6)
    # 背骨の最も近い点の割合と、鎖の弧長の割合を半分ずつ（内の角で肋が扇に集まらないように）
    def prm(ch):
        a = np.r_[0, np.cumsum(np.linalg.norm(np.diff(ch, axis=0), axis=1))]
        pr = np.maximum.accumulate(0.5 * s_sp[track_param(ch, sp, win)] + 0.5 * a / max(a[-1], 1e-9))
        ps = float(P.get("PAIR_SIG", 0.0))
        if ps > 0:
            # 修正の回 1（as02_fix01_pair）：肋の組み方の割合を鎖の弧長でならす（背骨の最も近い点の番号は段になり、
            # 腋（塊から指へ移る所）で片側の鎖だけが進むので、肋の真ん中の線が揺れる。輪郭の点はそのまま、組み方だけを変える）
            L_ = max(a[-1], 1e-9)
            x = np.linspace(0, L_, max(int(L_ / 0.25), 16))
            px = np.interp(x, a, pr)
            sg = ps * float(w_est) / (x[1] - x[0])
            k_ = min(int(np.ceil(3 * sg)), len(px) - 2)
            ext = np.r_[-px[1:k_ + 1][::-1], px, 2.0 - px[-k_ - 1:-1][::-1]]
            px = ndimage.gaussian_filter1d(ext, sg, mode="nearest")[k_:k_ + len(px)]
            pr = np.maximum.accumulate(np.interp(a, x, px))
            pr = (pr - pr[0]) / max(pr[-1] - pr[0], 1e-9)
        return pr
    pr_R = prm(CR)
    pr_L = prm(CL)
    pr_R[0] = pr_L[0] = 0.0
    pr_R[-1] = pr_L[-1] = 1.0
    # 標本の肋（細かく）
    sq = np.linspace(0, 1, 241)
    R = chain_at(CR, pr_R, sq)
    Lp = chain_at(CL, pr_L, sq)
    w = np.linalg.norm(R - Lp, axis=1)
    mid = (sq > 0.2) & (sq < 0.6)
    w_mid = float(np.median(w[mid])) if mid.any() else float(np.median(w))
    wmax = float(w.max())
    # 先の細り：u < TAPER_U で w ≤ w(TAPER_U)·(u/TAPER_U)^p（両側を真ん中へ寄せる）
    u = 1.0 - sq
    iu = int(np.argmin(np.abs(u - P["TAPER_U"])))
    law = w[iu] * np.clip(u / P["TAPER_U"], 0, None) ** P["TAPER_P"]
    k = np.where((u < P["TAPER_U"]) & (w > law), law / np.maximum(w, 1e-9), 1.0)
    if P.get("TAPER_SOFT", 0):
        # 修正の回 1（as02_fix01_taper）：法則との小さい方を滑らかな最小（q = 4）にし、範囲の外へ 0.5·TAPER_U でなめらかに戻す
        # （硬い最小は幅の折れ目になり、先の近くの輪郭に小さなでこぼこを作っていた）
        qq = 4.0
        soft = law / np.maximum((w ** qq + law ** qq), 1e-30) ** (1.0 / qq)
        blend = np.clip((u - P["TAPER_U"]) / (0.5 * P["TAPER_U"]), 0, 1)
        k = np.where(u < 1.5 * P["TAPER_U"], (1 - blend) * soft + blend * 1.0, 1.0)
    cen = 0.5 * (R + Lp)
    R = cen + (R - cen) * k[:, None]
    Lp = cen + (Lp - cen) * k[:, None]
    # かかと：巻きの外の側（輪郭の長い方の鎖）を、根元の近くで外へ押す
    lenR = per_len(CR)
    lenL = per_len(CL)
    outer = "R" if lenR >= lenL else "L"
    bump = P["HEEL_H"] * w_mid * np.exp(-((sq - P["HEEL_S"]) / P["HEEL_W"]) ** 2)
    dirn = R - Lp
    dirn /= np.maximum(np.linalg.norm(dirn, axis=1, keepdims=True), 1e-9)
    if outer == "R":
        R = R + dirn * bump[:, None]
    else:
        Lp = Lp - dirn * bump[:, None]
    w = np.linalg.norm(R - Lp, axis=1)
    cen = 0.5 * (R + Lp)
    tipP = C[iT]
    # 根元の縁（as02_root_cap）：マスクの根元の開きの線（角 L → 角 R）を半分に分け、左半分と右半分を同じ割合で結ぶ肋にして、
    # 背骨の割合の負の側（−depth/L … 0）へ足す。根元は開きの線の形で丸く閉じる（面へ沈める）
    rec["root_cap"] = False
    i_root = 0
    if len(cap) > 6:
        cp_ = gsmooth_keep_ends(C[cap], sig)
        a_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cp_, axis=0), axis=1))]
        half = 0.5 * a_[-1]
        ncap = 24
        g = np.linspace(0, 1, ncap)
        capL = np.stack([np.interp(g * half, a_, cp_[:, k]) for k in range(2)], -1)
        capR = np.stack([np.interp(a_[-1] - g * half, a_, cp_[:, k]) for k in range(2)], -1)
        c0 = 0.5 * (R[0] + Lp[0])
        T0r = unit(cen[min(8, len(cen) - 1)] - cen[0])
        depth = float(-((capL[-1] - c0) @ T0r))
        if depth > 0.5:
            s_c = -(depth / L) * g
            sq = np.r_[s_c[::-1][:-1], sq]
            R = np.vstack([capR[::-1][:-1], R])
            Lp = np.vstack([capL[::-1][:-1], Lp])
            w = np.linalg.norm(R - Lp, axis=1)
            cen = 0.5 * (R + Lp)
            i_root = ncap - 1
            rec["root_cap"] = True
            rec["root_cap_depth_px"] = round(depth, 2)
    rsc, rsw = float(P.get("RIB_SC", 0.0)), float(P.get("RIB_SW", 0.0))
    if rsc > 0 or rsw > 0:
        # 修正の回 1（as02_fix01_ribs）：肋の真ん中の線（背骨）を σ = RIB_SC·中ほどの幅、肋の半分の向きと長さ（幅）を σ = RIB_SW·中ほどの幅
        # で、それぞれ弧長でならす（根元の縁の真ん中の点と先は動かさない）。かかとは外してからならし、先の細りの法則とかかとを当て直す。
        # 輪郭の鎖そのものをならすと細い指の体が巻きの内へずれて重なり（IoU）が落ちるので、背骨と幅を分けてならす。
        nb = len(dirn)
        hb = np.zeros_like(R)
        hb[len(R) - nb:] = dirn * bump[:, None]
        if outer == "R":
            R = R - hb
        else:
            Lp = Lp + hb
        R2, L2 = rib_smooth(R, Lp, w_mid, rsc, rsw)
        # 根元の縁（塊）の肋はならさない（塊の幅は中ほどの幅よりずっと広く、肋の向きが扇に開くので、ならすと塊の輪郭が大きく崩れる）。
        # 根元の角の線（sq = 0）から RIB_BLEND の長さの割合でならした形へなめらかに移す
        wgt = U.smoothstep(sq / max(float(P.get("RIB_BLEND", 0.08)), 1e-6))[:, None] * (sq >= 0)[:, None]
        R = R + wgt * (R2 - R)
        Lp = Lp + wgt * (L2 - Lp)
        cen = 0.5 * (R + Lp)
        w = np.linalg.norm(R - Lp, axis=1)
        body = sq >= 0
        u = 1.0 - sq
        iu = int(np.argmin(np.abs(np.where(body, u, 9.0) - P["TAPER_U"])))
        law = w[iu] * np.clip(u / P["TAPER_U"], 0, None) ** P["TAPER_P"]
        k = np.where(body & (u < P["TAPER_U"]) & (w > law), law / np.maximum(w, 1e-9), 1.0)
        R = cen + (R - cen) * k[:, None]
        Lp = cen + (Lp - cen) * k[:, None]
        bump2 = np.where(body, P["HEEL_H"] * w_mid * np.exp(-((sq - P["HEEL_S"]) / P["HEEL_W"]) ** 2), 0.0)
        dirn2 = R - Lp
        dirn2 /= np.maximum(np.linalg.norm(dirn2, axis=1, keepdims=True), 1e-9)
        if outer == "R":
            R = R + dirn2 * bump2[:, None]
        else:
            Lp = Lp - dirn2 * bump2[:, None]
        cen = 0.5 * (R + Lp)
        w = np.linalg.norm(R - Lp, axis=1)
        rec["rib_smooth"] = dict(sc=rsc, sw=rsw)
    # 面から見た輪郭の多角形：右の鎖 → 先 → 左の鎖（逆）（根元の縁を含む）
    poly = np.vstack([R, tipP[None], Lp[::-1]])
    H, W = mask0.shape
    S = 8

    def raster(pp):
        img = np.zeros((H * S, W * S), np.uint8)
        cv2.fillPoly(img, [np.round(((pp + 0.5) * S - 0.5) * 16).astype(np.int32)], 255, lineType=cv2.LINE_8, shift=4)
        return img > 0
    mk = cv2.resize(mask0.astype(np.uint8), (W * S, H * S), interpolation=cv2.INTER_NEAREST) > 0
    pr = raster(poly)
    iou = float((pr & mk).sum() / max((pr | mk).sum(), 1))
    Tq = np.gradient(cen, axis=0)
    Tq /= np.maximum(np.linalg.norm(Tq, axis=1, keepdims=True), 1e-9)
    ang = np.unwrap(np.arctan2(Tq[:, 1], Tq[:, 0]))
    rec.update(dict(L_px=round(float(L), 2), wmax_px=round(wmax, 2), w_mid_px=round(w_mid, 2), turn_deg=round(float(np.degrees(ang[-1] - ang[0])), 1),
                    heel_side=outer, contour_pts=n, root_cap_pts=len(cap), iou_face_2d=round(iou, 4)))
    # 修正の回 1（as02_fix01_sweep）で使う：ならした輪郭の鎖・根元の縁・かかとの側
    capS = None
    if rec["root_cap"]:
        capS = cp_
    return dict(sq=sq, R=R, Lp=Lp, cen=cen, w=w, w_mid=w_mid, wmax=wmax, tip=tipP, L=L, rec=rec, mask=mask0, poly=poly, sp=sp, i_root=i_root,
                c=cen, s=sq, CR=CR, CL=CL, capS=capS, outer=outer)


# ---------------------------------------------------------------- 修正の回 1（as02_fix01_sweep）：背骨と幅で作り直す
def _seg_hits(p, n, O):
    """点 p（k×2）から向き n（k×2）の直線と、閉じた折れ線 O（m×2）の交わり。正の側の最も近い t と、負の側の最も近い t（無ければ nan）。"""
    A_ = O
    B_ = np.roll(O, -1, 0)
    E = B_ - A_
    den = n[:, 0:1] * E[None, :, 1] - n[:, 1:2] * E[None, :, 0]
    den = np.where(np.abs(den) < 1e-12, np.nan, den)
    AP = A_[None, :, :] - p[:, None, :]
    t = (AP[..., 0] * E[None, :, 1] - AP[..., 1] * E[None, :, 0]) / den
    u = (AP[..., 0] * n[:, None, 1] - AP[..., 1] * n[:, None, 0]) / den
    ok = (u >= 0) & (u <= 1) & np.isfinite(t)
    tp = np.where(ok & (t > 1e-6), t, np.inf).min(1)
    tm = np.where(ok & (t < -1e-6), t, -np.inf).max(1)
    tp[~np.isfinite(tp)] = np.nan
    tm[~np.isfinite(tm)] = np.nan
    return tp, tm


def _arc(Pp):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]


def _gs_arc(Pp, sig_len):
    """弧長で等間隔に置き直し、端を固定したガウスでならして、元の弧長の位置へ戻す。"""
    a = _arc(Pp)
    L = a[-1]
    n = max(int(L / 0.25), 16)
    x = np.linspace(0, L, n)
    Q = np.stack([np.interp(x, a, Pp[:, k]) for k in range(Pp.shape[1])], -1)
    sig = sig_len / (L / (n - 1))
    Qs = gsmooth_keep_ends(Q, sig) if sig > 0.3 else Q
    return np.stack([np.interp(a, x, Qs[:, k]) for k in range(Pp.shape[1])], -1)


def _g1_arc(v, a, sig_len):
    """1 次元の値 v（弧長 a の上）を、端を点で鏡映してからガウスでならす（端の値と傾きを保つ）。"""
    L = a[-1]
    n = max(int(L / 0.25), 16)
    x = np.linspace(0, L, n)
    vv = np.interp(x, a, v)
    sig = sig_len / (L / (n - 1))
    if sig <= 0.3:
        return v.copy()
    k = min(int(np.ceil(3 * sig)), n - 2)
    e0 = 2 * vv[0] - vv[1:k + 1][::-1]
    e1 = 2 * vv[-1] - vv[-k - 1:-1][::-1]
    q = ndimage.gaussian_filter1d(np.r_[e0, vv, e1], sig, mode="nearest")[k:k + n]
    return np.interp(a, x, q)


def _tangent_normal(cs):
    T = np.gradient(cs, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    return T, np.stack([-T[:, 1], T[:, 0]], -1)


def sweep_refit(sh, sc, sw, n_st=320, iters=3):
    """as02_fix01_sweep（修正の回 1）：手描きのマスクの輪郭（ならした鎖と根元の縁、sh の CR・CL・capS）はそのままに、肋の組み方を背骨の法線で
    決め直し、背骨（真ん中の線）と左右の幅を、それぞれ弧長でならした滑らかな関数として作り直す（彫った模型のように、背骨も輪郭も滑らかにする）。
    今までの肋は左右の鎖の進みの割合で組んだので、真ん中の線が細かく揺れ、背骨の曲率の跳び（C2）が模型より大きくなっていた。
      1. 背骨の初め：今の肋の真ん中（根元の縁の真ん中の点 → 先）を弧長で σ = sc·中ほどの幅 でならす。
      2. 背骨の各点の法線と、閉じた輪郭（根元の縁 → 右の鎖 → 先 → 左の鎖）の交わりを左右に取って肋にし、その真ん中を再びならす（iters 回）。
      3. 左右の幅（背骨から法線の向きに輪郭まで）を σ = sw·中ほどの幅 でならし、内の側は背骨の曲率半径の 0.92 倍までにする（輪郭が折り返さない）。
      4. 先の細り（w ≤ 法則）を滑らかな最小（q = 4）で、かかとを外の側へ（今と同じ大きさ・位置）。
    返す sh は shape2d と同じ鍵（sq は根元の角の線で 0、先で 1。根元の縁は負）。"""
    wm = float(sh["w_mid"])
    cap = sh.get("capS") is not None
    if cap:
        O = np.vstack([sh["capS"], sh["CR"][1:], sh["CL"][::-1][1:-1]])
    else:
        O = np.vstack([sh["CR"], sh["CL"][::-1][1:-1]])
    cR0, cL0 = sh["CR"][0], sh["CL"][0]
    tipP = sh["tip"]
    cen0 = 0.5 * (sh["R"] + sh["Lp"])
    cen0 = np.vstack([cen0[:-1], tipP[None]])
    cs = _gs_arc(cen0, sc * wm)
    cs, _ = resample_poly(cs, n_st)
    sR = 1.0
    lim = 1.6 * max(float(sh["wmax"]), wm)
    for it in range(iters):
        T, Nn = _tangent_normal(cs)
        tp, tm = _seg_hits(cs, Nn, O)
        tp = np.where(tp <= lim, tp, np.nan)
        tm = np.where(-tm <= lim, tm, np.nan)
        if it == 0:
            mid_old = 0.5 * (sh["R"] + sh["Lp"])
            k = cKDTree(cs).query(mid_old)[1]
            sR = 1.0 if float(np.nansum(np.sum((sh["R"] - mid_old) * Nn[k], 1))) >= 0 else -1.0
        wR = tp if sR > 0 else -tm
        wL = -tm if sR > 0 else tp
        a = _arc(cs)
        if cap:
            wR[0] = wL[0] = 0.0
        wR[-1] = wL[-1] = 0.0
        okR = np.isfinite(wR)
        okL = np.isfinite(wL)
        wR = np.interp(a, a[okR], wR[okR])
        wL = np.interp(a, a[okL], wL[okL])
        mid = cs + (0.5 * (wR - wL) * sR)[:, None] * Nn
        mid[0], mid[-1] = cs[0], cs[-1]
        if it < iters - 1:
            cs = _gs_arc(mid, sc * wm)
            cs, _ = resample_poly(cs, n_st)
    T, Nn = _tangent_normal(cs)
    a = _arc(cs)
    wR = np.maximum(_g1_arc(wR, a, sw * wm), 0.0)
    wL = np.maximum(_g1_arc(wL, a, sw * wm), 0.0)
    kap = (T[:, 0] * np.gradient(T[:, 1]) - T[:, 1] * np.gradient(T[:, 0])) / np.maximum(np.gradient(a), 1e-9)
    kap = ndimage.gaussian_filter1d(kap, 2.0, mode="nearest")
    rad = 1.0 / np.maximum(np.abs(kap), 1e-9)
    inner_is_R = (np.sign(kap) * sR) > 0
    wR = np.where(inner_is_R, np.minimum(wR, 0.92 * rad), wR)
    wL = np.where(~inner_is_R, np.minimum(wL, 0.92 * rad), wL)
    k0 = int(cKDTree(cs).query(0.5 * (cR0 + cL0))[1]) if cap else 0
    a0 = a[k0]
    Lb = max(a[-1] - a0, 1e-6)
    sq = (a - a0) / Lb
    # 先の細り（滑らかな最小。法則を上限にする範囲の外へは 0.5·TAPER_U でなめらかに戻す）
    w = wR + wL
    u = 1.0 - sq
    iu = int(np.argmin(np.abs(u - P["TAPER_U"])))
    law = w[iu] * np.clip(u / P["TAPER_U"], 0, None) ** P["TAPER_P"]
    qq = 4.0
    soft = w * law / np.maximum((w ** qq + law ** qq), 1e-30) ** (1.0 / qq)
    blend = np.clip((u - P["TAPER_U"]) / (0.5 * P["TAPER_U"]), 0, 1)
    wn = np.where(u < 1.5 * P["TAPER_U"], (1 - blend) * soft + blend * w, w)
    kk = wn / np.maximum(w, 1e-12)
    wR, wL = wR * kk, wL * kk
    bump = P["HEEL_H"] * wm * np.exp(-((sq - P["HEEL_S"]) / P["HEEL_W"]) ** 2)
    if sh["outer"] == "R":
        wR = wR + bump
    else:
        wL = wL + bump
    R = cs + (sR * wR)[:, None] * Nn
    Lp = cs - (sR * wL)[:, None] * Nn
    R[-1] = Lp[-1] = cs[-1]
    cen = 0.5 * (R + Lp)
    w = np.linalg.norm(R - Lp, axis=1)
    out = dict(sh)
    i_root = int(np.argmax(sq >= 0)) if (sq < 0).any() else 0
    out.update(sq=sq, R=R, Lp=Lp, cen=cen, c=cen, s=sq, w=w, tip=cs[-1].copy(), poly=np.vstack([R, Lp[::-1][1:]]), i_root=i_root, L=float(Lb))
    sel = (sq > 0.2) & (sq < 0.6)
    out["w_mid"] = float(np.median(w[sel])) if sel.any() else float(np.median(w))
    out["wmax"] = float(w.max())
    rec = dict(sh["rec"])
    rec.update(sweep=dict(sc=sc, sw=sw, n_st=n_st, iters=iters), L_px=round(float(Lb), 2), wmax_px=round(float(w.max()), 2), w_mid_px=round(out["w_mid"], 2))
    out["rec"] = rec
    rec["iou_face_2d"] = round(iou_mask2d(out), 4)
    return out


def rib_smooth(R, Lp, wm, sc, sw):
    """as02_fix01_ribs：肋（右 R・左 Lp の点の組）の真ん中の線を σ = sc·wm、半分の肋のベクトル（真ん中の線の法線と接線の成分）を σ = sw·wm で、
    弧長でならす（両端は鏡映で値と傾きを保つ）。"""
    cen = 0.5 * (R + Lp)
    hv = 0.5 * (R - Lp)
    cs = _gs_arc(cen, sc * wm) if sc > 0 else cen.copy()
    cs[0], cs[-1] = cen[0], cen[-1]
    T, Nn = _tangent_normal(cs)
    a = _arc(cs)
    hn = (hv * Nn).sum(1)
    ht = (hv * T).sum(1)
    if sw > 0:
        hn = _g1_arc(hn, a, sw * wm)
        ht = _g1_arc(ht, a, sw * wm)
    R2 = cs + hn[:, None] * Nn + ht[:, None] * T
    L2 = cs - hn[:, None] * Nn - ht[:, None] * T
    return R2, L2


FIX01_GAUSS = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
FIX01_SPLINE = (1.0, 1.5, 2.0, 3.0)
FIX01_WSCALE = (1.0, 0.97, 1.03, 1.06, 1.10)
FIX01_BANDPASS = (0.0, 3.0)        # SHRINK_COMP：0 ＝ ふつうのならし、3 ＝ 長い波の動きを戻すならし（as02_fix01_bandpass）
FIX01_NORTHO = (0.5, 0.3, 0.15, 0.0)
FIX01_IOU_PAINT_OK = 0.86


def scale_width(sh, f):
    """肋の半分を真ん中の線から f 倍にした形（滑らかさは変わらない。手描きの縁をならして細った分を戻す）。"""
    if abs(f - 1.0) < 1e-9:
        return sh
    out = dict(sh)
    cen = 0.5 * (sh["R"] + sh["Lp"])
    R = cen + f * (sh["R"] - cen)
    Lp = cen + f * (sh["Lp"] - cen)
    w = np.linalg.norm(R - Lp, axis=1)
    sq = sh["sq"]
    sel = (sq > 0.2) & (sq < 0.6)
    out.update(R=R, Lp=Lp, w=w, poly=np.vstack([R, sh["tip"][None], Lp[::-1]]),
               w_mid=float(np.median(w[sel])) if sel.any() else float(np.median(w)), wmax=float(w.max()))
    rec = dict(sh["rec"])
    rec["width_scale"] = f
    out["rec"] = rec
    return out


def clip_crop(sh):
    """as02_fix01_clip：形の肋の点を切り抜きの枠（画素の縁）の中へ寄せる。利用者のマスクは根元の塊が切り抜きの枠で切れている爪が多く、
    ならし・かかと・幅の倍率で枠の外へ出た分は、原画視点で利用者の塗りの外になる（IoU を下げる）。枠の外は利用者が見ていない所なので、枠で止める。"""
    H, W = sh["mask"].shape
    lo = np.array([-0.5, -0.5])
    hi = np.array([W - 0.5, H - 0.5])
    R = np.clip(sh["R"], lo, hi)
    Lp = np.clip(sh["Lp"], lo, hi)
    if np.allclose(R, sh["R"]) and np.allclose(Lp, sh["Lp"]):
        return sh
    out = dict(sh)
    w = np.linalg.norm(R - Lp, axis=1)
    sq = sh["sq"]
    sel = (sq > 0.2) & (sq < 0.6)
    tip = np.clip(sh["tip"], lo, hi)
    out.update(R=R, Lp=Lp, w=w, cen=0.5 * (R + Lp), c=0.5 * (R + Lp), tip=tip, poly=np.vstack([R, tip[None], Lp[::-1]]),
               w_mid=float(np.median(w[sel])) if sel.any() else float(np.median(w)), wmax=float(w.max()))
    out["rec"] = dict(sh["rec"], clipped_to_crop=True)
    return out


def choose_shape_fix01(c, std):
    """修正の回 1（as02_fix01_choose）：爪ごとに、輪郭のならしの強さ（GAUSS_K × SPLINE_K）と幅の倍率の組を試し、
    利用者の模型の水準の 2 次元の検査（輪郭のでこぼこ ≤ claw_mid + 2、背骨の曲率の跳び ≤ 模型）を通る組のうち、
    利用者のマスクとの重なり（IoU、面から）が最も大きいものを採る。通る組が無い時は、でこぼこと跳びの超えが最も小さい組。
    肋の組み方のならし（PAIR_SIG）は全部の組で入れる。"""
    lim_l = std["models"]["claw_mid"]["outline_lumps_hysteresis"] + 2
    lim_j = max(std["models"]["claw_mid"]["spine_curvature_x_wmax"]["jump_p95"], std["models"]["claw_low"]["spine_curvature_x_wmax"]["jump_p95"])
    tried = []
    best = None
    save = dict(P)
    for g, sk, bp in [(g, sk, bp) for bp in FIX01_BANDPASS for g in FIX01_GAUSS for sk in FIX01_SPLINE]:
        if True:
            P.update(GAUSS_K=g, SPLINE_K=sk, SHRINK_COMP=bp)
            try:
                sh0 = shape2d(c, std)
            except Exception:  # noqa: BLE001
                P.clear(); P.update(save)
                continue
            P.clear(); P.update(save)
            for f in FIX01_WSCALE:
                sh = scale_width(sh0, f)
                if P.get("CLIP_CROP", 0):
                    sh = clip_crop(sh)
                lu = outline_lumps(sh["poly"], sh["w_mid"] / 0.75)
                jp = spine_jump_p95(sh)
                io = iou_mask2d(sh)
                ok = (lu <= lim_l) and (jp <= lim_j)
                tried.append((g, sk, bp, f, lu, round(jp, 3), round(io, 4)))
                key = (1 if ok else 0, io if ok else -(max(lu - lim_l, 0) + 4 * max(jp - lim_j, 0)) + 0.001 * io)
                if best is None or key > best[0]:
                    best = (key, sh, dict(gauss_k=g, spline_k=sk, bandpass=bp, width_scale=f, lumps=lu, spine_jump_p95=round(jp, 3),
                                          iou_face_2d=round(io, 4), c2_2d_pass=ok))
    if best is None:
        raise RuntimeError("形の候補が作れない")
    sh = best[1]
    sh["rec"] = dict(sh["rec"], iou_face_2d=best[2]["iou_face_2d"], fix01=best[2], fix01_candidates=len(tried))
    return sh, best[2]


def iou_mask2d(sh, S=8):
    """面から見た 2 次元の形（多角形）と利用者のマスクの IoU（切り抜きの画素を S 倍に）。
    shape2d の iou_face_2d は切り抜きの枠の中だけで塗るので、形が枠の外へはみ出た分（根元の塊が枠に接する爪で、ならしやかかとで外へ出た分）を
    数えず、原画視点の IoU より高く出ていた。ここでは枠の外に余白をとって塗る（修正の回 1）。"""
    mask0 = sh["mask"]
    H, W = mask0.shape
    poly = sh["poly"]
    lo = np.floor(np.minimum(poly.min(0), [0, 0])) - 2
    hi = np.ceil(np.maximum(poly.max(0), [W - 1, H - 1])) + 2
    ox, oy = int(-lo[0]), int(-lo[1])
    Wp, Hp = int(hi[0] - lo[0]) + 1, int(hi[1] - lo[1]) + 1
    img = np.zeros((Hp * S, Wp * S), np.uint8)
    cv2.fillPoly(img, [np.round(((poly + [ox, oy] + 0.5) * S - 0.5) * 16).astype(np.int32)], 255, lineType=cv2.LINE_8, shift=4)
    mk = np.zeros((Hp, Wp), np.uint8)
    mk[oy:oy + H, ox:ox + W] = mask0
    mk = cv2.resize(mk, (Wp * S, Hp * S), interpolation=cv2.INTER_NEAREST) > 0
    pr = img > 0
    return float((pr & mk).sum() / max((pr | mk).sum(), 1))


def spine_jump_p95(sh):
    """standard_check と同じ背骨の曲率の跳び（p95）。"""
    wm = sh["w_mid"]
    cp, Lc = resample_poly(sh["cen"], 201)
    T = np.gradient(cp, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    ds = Lc / 200.0
    kap = (T[:, 0] * np.gradient(T[:, 1]) - T[:, 1] * np.gradient(T[:, 0])) / ds * wm
    ss = np.linspace(0, 1, 201)
    selk = (ss > 0.10) & (ss < 0.95)
    dk = np.abs(np.diff(kap[selk]))
    return float(np.percentile(dk, 95)) if len(dk) else 0.0


# ---------------------------------------------------------------- 主役波への当たり
SEA_NEAR = REPO + "/Unity/Build/Polish/30/sea/near/ds30_tstar.gwb"


def load_sea():
    """仕上げ30 の近い海（t* の網。手前の小波を含む）。"""
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/kstar_h")
    import kh_common as K
    g = K.read_gwb(SEA_NEAR)
    V = g["X"]
    F = g["tris"].astype(np.int64)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn[fn[:, 1] < 0] *= -1
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    vn[vn[:, 1] < 0] *= -1
    return V, F, vn


class Hit:
    """原画視点の z バッファ（主役波の本体 ＋ 近い海）。画素の射線が最初に当たる面（hero か sea）と、その点・法線（カメラ側）を返す。"""

    def __init__(self, hero, cam, sea):
        self.h, self.cam = hero, cam
        self.sV, self.sF, self.sN = sea
        tri_h = hero.V[hero.Tg]
        tri_s = self.sV[self.sF]
        self.nh = len(hero.Tg)
        self.idb, self.zb = U.raster(cam, np.concatenate([tri_h, tri_s]), np.arange(1, self.nh + len(self.sF) + 1))
        # 面からの高さ：主役波の本体の頂点（空気の側の法線）と海の頂点（上向き）
        self.HV = np.concatenate([hero.V[hero.vi], self.sV])
        self.HN = np.concatenate([hero.Nf[hero.vi], self.sN])
        self.tree = cKDTree(self.HV)

    def height(self, Q):
        sh = Q.shape[:-1]
        Qf = Q.reshape(-1, 3)
        d, j = self.tree.query(Qf)
        return (((Qf - self.HV[j]) * self.HN[j]).sum(-1)).reshape(sh)

    def at(self, px):
        x, y = int(round(px[0])), int(round(px[1]))
        if not (0 <= x < self.cam.W and 0 <= y < self.cam.H):
            return None
        t = int(self.idb[y, x]) - 1
        if t < 0:
            return None
        d = self.cam.ray(np.array([px[0]]), np.array([px[1]]))[0]
        if t < self.nh:
            tv = self.h.V[self.h.Tg[t]]
            s_, u, v = U.ray_tri_many(self.cam.pos, d[None, :], tv[0][None], tv[1][None], tv[2][None])
            if not np.isfinite(s_[0]):
                return None
            r, cc = U.tri_to_rc(np.array([t]), u, v, self.h.b1 - self.h.b0, self.h.b0)
            n = self.h.frame(np.array([float(r[0])]), np.array([float(cc[0])]))[0][2]
            return dict(surf="hero", P=self.cam.pos + s_[0] * d, r=float(r[0]), c=float(cc[0]), tri=t, depth=float(s_[0]), n=n)
        ts = t - self.nh
        tv = self.sV[self.sF[ts]]
        s_, u, v = U.ray_tri_many(self.cam.pos, d[None, :], tv[0][None], tv[1][None], tv[2][None])
        if not np.isfinite(s_[0]):
            return None
        n = unit(np.cross(tv[1] - tv[0], tv[2] - tv[0]))
        if n[1] < 0:
            n = -n
        return dict(surf="sea", P=self.cam.pos + s_[0] * d, r=-1.0, c=-1.0, tri=ts, depth=float(s_[0]), n=n)


def lift(cam, q, P0, m):
    """表示の画素 q（k×2）の射線と、P0 を通り法線 m の平面の交わり。"""
    q = np.atleast_2d(q)
    d = cam.ray(q[:, 0], q[:, 1])
    lam = ((P0 - cam.pos) @ m) / (d @ m)
    return cam.pos + lam[:, None] * d, d


def build_rings(sh, M, cam, P0, m, nvis, ratio_fn, n_st, hero, root_sink=True, center_lift=None):
    """2 次元の肋（左 L・右 R、切り抜きの画素）を表示の画素へ写して平面 Π（P0, m）へ持ち上げ、レンズ形の輪を作る。"""
    sq = sh["sq"]
    t = np.linspace(0, 1, n_st)
    # 輪の位置：肋の両端の動き（左右の鎖の進み）で等分した位置と、長さの割合の等分を半分ずつ（根元の扇の所に輪を多く）
    mv = np.r_[0, np.cumsum(0.5 * (np.linalg.norm(np.diff(sh["R"], axis=0), axis=1) + np.linalg.norm(np.diff(sh["Lp"], axis=0), axis=1)))]
    mv /= max(mv[-1], 1e-9)
    s_mv = np.interp(t, mv + np.linspace(0, 1e-9, len(mv)), sq)
    s0 = float(sq[0])
    uu = 0.5 * (0.5 - 0.5 * np.cos(np.pi * t)) + 0.5 * t
    s_st = 0.5 * s_mv + 0.5 * (s0 + (1.0 - s0) * uu)
    s_st = np.minimum(s_st, 0.985)

    def at(arr, ss):
        return np.stack([np.interp(ss, sq, arr[:, k]) for k in range(arr.shape[1])], -1)
    Rq = at(sh["R"], s_st)
    Lq = at(sh["Lp"], s_st)
    cc = 0.5 * (Rq + Lq)

    def to_d(q):
        return np.asarray(q) @ M[:, :2].T + M[:, 2]
    Cd = to_d(cc)
    if center_lift is None:
        Pc, dc = lift(cam, Cd, P0, m)
        Ptip, dtip = lift(cam, to_d(sh["tip"][None]), P0, m)
    else:
        Pall, dall = center_lift(np.vstack([Cd, to_d(sh["tip"][None])]), np.r_[s_st, 1.0])
        Pc, dc = Pall[:-1], dall[:-1]
        Ptip, dtip = Pall[-1:], dall[-1:]
    allp = np.vstack([Pc, Ptip])
    Tg = np.gradient(allp, axis=0)[:-1]
    Tg = ndimage.gaussian_filter1d(Tg, 1.0, axis=0, mode="nearest")
    Tg /= np.maximum(np.linalg.norm(Tg, axis=1, keepdims=True), 1e-12)
    # 断面の厚みの向き N は、射線の向き（カメラへ）を接線に直交させたもの。幅の向き Bv = N × T は射線にも直交する
    # （原画のカメラから見て、厚みは奥行きにだけ出て、影の幅は 2 次元の形のまま。as02_section_faces_camera）
    # 射線の向きを接線から半分だけ直交させる（as02_section_half_ortho：断面は少し斜めになるが、厚みが原画のカメラの画面で背骨の向きへ出る量が半分になる）
    N = -dc - P["N_ORTHO"] * (np.sum(-dc * Tg, 1))[:, None] * Tg
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    Bv = np.cross(N, Tg)
    # 縁の点：左右の画素の射線と、その輪の面（Pc を通り法線 N）の交わり
    def lift_local(qd):
        d = cam.ray(qd[:, 0], qd[:, 1])
        lam = np.sum((Pc - cam.pos) * N, 1) / np.sum(d * N, 1)
        return cam.pos + lam[:, None] * d
    PR = lift_local(to_d(Rq))
    PL = lift_local(to_d(Lq))
    sgnR = np.sign(((PR - PL) * Bv).sum(1))
    sgnR[sgnR == 0] = 1.0
    Pp = np.where(sgnR[:, None] > 0, PR, PL)    # +Bv の側
    Pm = np.where(sgnR[:, None] > 0, PL, PR)
    halfw = 0.5 * np.linalg.norm(Pp - Pm, axis=1)
    # 厚み：幅 / 比。根元の広い所は、中ほどの幅の 1.25 倍で頭打ち（根元が塊にならないように）
    sel = (s_st > 0.2) & (s_st < 0.6)
    wmid3 = float(np.median(2 * halfw[sel])) if sel.any() else float(np.median(2 * halfw))
    th = np.minimum(2 * halfw, P["ROOT_TH_CAP"] * wmid3) / ratio_fn(s_st) * 0.5
    rmx = float(P.get("RATIO_MAX_MID", 0.0))
    if rmx > 0:
        # 修正の回 1（as02_fix01_ratio）：中ほど（s 0.15〜0.85）の幅が中ほどの幅の頭打ち（ROOT_TH_CAP）より広い所は、幅 : 厚み が
        # 利用者の模型の範囲（1.1〜1.7）を越えていた（claw057 で 1.83）。厚みを 幅 / RATIO_MAX_MID まで足す
        mm = (s_st >= 0.15) & (s_st <= 0.85)
        th = np.where(mm, np.maximum(th, halfw / rmx), th)
    # 根元の足（as02_foot）：利用者の模型 claw_mid の厚みは根元の足で最大（最大幅の約 0.95 倍＝指の中ほどの幅の約 1.2〜1.4 倍）で、
    # 先へ向かって細る。厚みの向き（射線に近い向き）だけを根元で厚くする（原画のカメラからの影は変わらない）
    foot = P["FOOT"] * wmid3 * 0.5 * (1.0 - U.smoothstep((s_st - P["FOOT_S0"]) / P["FOOT_S1"]))
    th = np.maximum(th, foot)
    sink = np.zeros(n_st)
    if root_sink:
        th_root = float(np.interp(0.0, s_st, th)) if s_st[0] < 0 else float(th[0])
        sink = P["SINK"] * th_root * np.clip(1.0 - s_st / P["SINK_S"], 0, 1) ** 2
    off = dc * sink[:, None]
    Pc_s, Pp_s, Pm_s = Pc + off, Pp + off, Pm + off
    A_, B_ = P["LENS_A"], P["LENS_B"]
    ring = np.zeros((n_st, RING, 3))
    ring[:, 0] = Pp_s
    ring[:, 4] = Pm_s
    ring[:, 2] = Pc_s + N * th[:, None]
    ring[:, 6] = Pc_s - N * th[:, None]
    ring[:, 1] = Pc_s + (Pp_s - Pc_s) * A_ + N * (B_ * th)[:, None]
    ring[:, 3] = Pc_s + (Pm_s - Pc_s) * A_ + N * (B_ * th)[:, None]
    ring[:, 5] = Pc_s + (Pm_s - Pc_s) * A_ - N * (B_ * th)[:, None]
    ring[:, 7] = Pc_s + (Pp_s - Pc_s) * A_ - N * (B_ * th)[:, None]
    root_pt = Pc_s[0] + dc[0] * (P["SINK"] * max(th[0], 0.3 * float(th.max())) * 0.5) - Tg[0] * (0.25 * halfw[0])
    V = np.concatenate([root_pt[None], ring.reshape(-1, 3), Ptip, np.repeat(root_pt[None], 9, 0)], 0)
    return dict(V=V, ring=ring, Pc=Pc_s, Pc0=Pc, Ptip=Ptip[0], Tg=Tg, N=N, Bv=Bv, halfw=halfw, th=th, s_st=s_st, Cd=Cd, cc2=cc)


def make_arch_lift(cam, hit, P0, nvis, Lm, sgn):
    """案 C（as02_arch_hover）：背骨の点ごとに、その画素の射線が当たる面（主役波・近い海）から、面の法線の向きに h(s) だけ離れた所へ、
    射線の上で置く（原画のカメラからの形は変わらない）。h(s) = H·(1 − (1 − min(s/S_R, 1))²)、H = HOVER × 爪の長さ。
    射線が面に当たらない点（空へ出る先）と、当たる深さが前の点から跳ぶ点（稜の向こうの面）は、前の点の深さの傾きで延ばす。"""
    H = P["HOVER"] * Lm

    def f(Q2, s_vals):
        d = cam.ray(Q2[:, 0], Q2[:, 1])
        lam = np.full(len(Q2), np.nan)
        for i, q in enumerate(Q2):
            h0 = hit.at(q)
            if h0 is None:
                continue
            n = h0["n"]
            if n @ (cam.pos - h0["P"]) < 0:
                n = -n
            hs = H * (1.0 - (1.0 - min(s_vals[i] / P["HOVER_SR"], 1.0)) ** 2)
            c = max(float(-d[i] @ n), P["HOVER_COSMIN"])
            off = min(hs / c, P["HOVER_MAXOFF"] * Lm)
            lam[i] = h0["depth"] - off
        # 根元は面の上
        lam0 = float(((P0 - cam.pos) @ d[0]))
        if not np.isfinite(lam[0]):
            lam[0] = lam0
        # 跳び・欠けを前の傾きで埋める
        step_lim = max(0.25 * Lm, 0.3)
        out = lam.copy()
        for i in range(1, len(out)):
            ok = np.isfinite(lam[i]) and abs(lam[i] - out[i - 1]) <= step_lim * (1 + 2 * (s_vals[i] - s_vals[i - 1]) * 10)
            if not ok:
                slope = (out[i - 1] - out[i - 2]) if i >= 2 else 0.0
                out[i] = out[i - 1] + slope
        # ならす（根元は動かさない）
        k = ndimage.gaussian_filter1d(out, 1.5, mode="nearest")
        k[0] = out[0]
        return cam.pos + k[:, None] * d, d
    return f


def rotate_rings(B, P0, d0, nvis, theta_t):
    """build_rings の結果を、根元 P0 の周りに、向き d0 が法線 nvis から theta_t 度になるよう硬く回す（d0 と nvis の張る面の中の最小の回転）。"""
    cur = math.degrees(math.acos(np.clip(d0 @ nvis, -1, 1)))
    rot = math.radians(cur - theta_t)
    ax = np.cross(d0, nvis)
    if np.linalg.norm(ax) < 1e-9 or rot <= 0:
        return dict(B)
    ax = unit(ax)
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    R = np.eye(3) + math.sin(rot) * K + (1 - math.cos(rot)) * (K @ K)
    out = dict(B)
    for k in ("V", "Pc", "Pc0"):
        out[k] = (B[k] - P0) @ R.T + P0
    out["ring"] = (B["ring"] - P0) @ R.T + P0
    out["Ptip"] = (B["Ptip"] - P0) @ R.T + P0
    for k in ("N", "Bv", "Tg"):
        out[k] = B[k] @ R.T
    return out


def ratio_fn(s):
    return P["RATIO_MID"] + (P["RATIO_TIP"] - P["RATIO_MID"]) * U.smoothstep((np.asarray(s) - 0.75) / 0.25)


def plane_from(cam, P0, q0d, tau_d, al, be):
    v = unit(P0 - cam.pos)
    t3 = unit(cam.r * tau_d[0] - cam.u * tau_d[1])
    t3 = unit(t3 - (t3 @ v) * v)
    n3 = unit(np.cross(v, t3))
    # n3 の画面の向きが ν（τ を +90°：x → −y）に合うように
    nu_d = np.array([-tau_d[1], tau_d[0]])
    if (cam.r * nu_d[0] - cam.u * nu_d[1]) @ n3 < 0:
        n3 = -n3
    D1 = math.cos(al) * t3 - math.sin(al) * v
    D2 = math.cos(be) * n3 - math.sin(be) * v
    m = unit(np.cross(D1, D2))
    if m @ (cam.pos - P0) < 0:
        m = -m
    return m, D1, D2, v, t3, n3


def heights(hit, Q, sgn):
    return sgn * hit.height(Q)


def place(sh, c, hero, cam, hit, M, rep):
    """1 本を置く。戻り値 entry（V・T・…）か None。"""
    cd = sh["c"] @ M[:, :2].T + M[:, 2]          # 表示の画素の背骨
    Ld = np.sum(np.linalg.norm(np.diff(cd, axis=0), axis=1))
    rep["L_disp_px"] = round(float(Ld), 2)
    # 根元の当たり：根元の画素、だめなら背骨に沿って ROOT_SEARCH_PX まで
    h0 = None
    sd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cd, axis=0), axis=1))]
    ir = int(sh.get("i_root", 0))
    sd = sd - sd[ir]
    for i in range(ir, len(cd)):
        if sd[i] > P["ROOT_SEARCH_PX"]:
            break
        h0 = hit.at(cd[i])
        if h0 is not None:
            rep["root_search_px"] = round(float(sd[i]), 2)
            break
    if h0 is None:
        rep["placed"] = False
        rep["why_not_ja"] = "根元の画素（と背骨に沿った %.0f 表示 px）の射線が主役波にも近い海にも当たらない（空）" % P["ROOT_SEARCH_PX"]
        return None
    i0 = int(np.argmin(np.abs(sd - sd[i])))
    P0 = h0["P"]
    n = h0["n"]
    sgn = 1.0 if n @ (cam.pos - P0) > 0 else -1.0
    nvis = sgn * n
    # 根元の画面の向き（背骨の最初の 12%）
    j = max(int(0.12 * len(cd)), 2)
    tau = unit(cd[min(i0 + j, len(cd) - 1)] - cd[i0])
    # 先の範囲の外の点（面より上にあるか調べる点）
    best = None
    s_n = sh["sq"]
    chk = np.nonzero(s_n > 0.12)[0][::2]
    qchk = cd[chk]
    wchk = np.interp(s_n[chk], sh["s"], sh["w"]) * np.linalg.norm(M[:, :2], axis=1).mean()   # 表示の px の幅
    for al_d in np.arange(0, 73, 3.0):
        for be_d in np.arange(-45, 46, 5.0):
            al, be = math.radians(al_d), math.radians(be_d)
            m, D1, D2, v, t3, n3 = plane_from(cam, P0, cd[i0], tau, al, be)
            stretch = 1.0 / max(abs(m @ v), 1e-6)
            if stretch > P["STRETCH_HARD"]:
                continue
            Q, dq = lift(cam, qchk, P0, m)
            # 厚みの半分（m）：幅の px × 深さの px の大きさ / 比
            z = (Q - cam.pos) @ cam.f
            pxm = z * 2.0 * cam.t / cam.H
            th = 0.5 * wchk * pxm / P["RATIO_MID"]
            hh = heights(hit, Q, sgn)
            pen = np.clip(th + P["CLEAR"] - hh, 0, None)
            ang = math.degrees(math.acos(np.clip(D1 @ nvis, -1, 1)))
            cost = abs(ang - P["THETA_T"]) / 10.0 + 30.0 * float(np.sum(pen ** 2) / max(np.mean(th) ** 2, 1e-6) / len(pen)) \
                + 0.5 * (stretch - 1.0) + 3.0 * max(0.0, stretch - P["STRETCH_MAX"]) + 0.002 * (al_d + abs(be_d))
            if best is None or cost < best[0]:
                best = (cost, al_d, be_d, m, D1, ang, stretch, float(pen.max()), float(hh.min()))
    if best is None:
        rep["placed"] = False
        rep["why_not_ja"] = "引き伸ばしの上限の中で平面が選べない"
        return None
    cost, al_d, be_d, m, D1, ang, stretch, penmax, hmin = best
    n_st = int(np.clip(round((per_len(sh["R"]) + per_len(sh["Lp"])) / float(P.get("ST_PER_PX", 6.0))), P["ST_MIN"], P["ST_MAX"]))
    B = build_rings(sh, M, cam, P0, m, nvis, ratio_fn, n_st, hero)
    if P["MODE"] == "arch":
        al_d, be_d = 0.0, 0.0
        m, D1, D2, v, t3, n3 = plane_from(cam, P0, cd[i0], tau, 0.0, 0.0)
        z0 = float((P0 - cam.pos) @ cam.f)
        Lm = float(Ld) * z0 * 2.0 * cam.t / cam.H
        B = build_rings(sh, M, cam, P0, m, nvis, ratio_fn, n_st, hero, center_lift=make_arch_lift(cam, hit, P0, nvis, Lm, sgn))
        hh_a = heights(hit, B["ring"][:, [1, 2, 3, 5, 6, 7]].reshape(-1, 3), sgn).reshape(n_st, 6).min(1)
        penmax = float(np.clip(-hh_a[B["s_st"] > P["SINK_S"]], 0, None).max()) if (B["s_st"] > P["SINK_S"]).any() else 0.0
        stretch = float(np.sum(np.linalg.norm(np.diff(B["Pc0"], axis=0), axis=1)) / max(Lm, 1e-6))
        ang = float("nan")
    if P["MODE"] == "ref":
        # 案 B（参照モデルの置き方を優先）：カメラに正対した平面（α = β = 0）で作った爪を、根元の周りに硬く回し、根元の向きを面の法線から
        # THETA_T の角へ起こす（最小の回転：根元の向きと法線の張る面の中）。原画視点の影は変わる（IoU を記録する）。面へ潜る時は THETA_T を
        # 5° ずつ小さくする（法線へ近づける）
        al_d, be_d = 0.0, 0.0
        m, D1, D2, v, t3, n3 = plane_from(cam, P0, cd[i0], tau, 0.0, 0.0)
        stretch = 1.0 / max(abs(m @ v), 1e-6)
        B0 = build_rings(sh, M, cam, P0, m, nvis, ratio_fn, n_st, hero)
        j3_ = max(int(0.3 * n_st), 1)
        d0 = unit(B0["Pc0"][j3_] - B0["Pc0"][0])
        best_r = None
        for th_t in np.arange(P["THETA_T"], -1.0, -5.0):
            Br = rotate_rings(B0, P0, d0, nvis, th_t)
            hh_r = heights(hit, Br["ring"][:, [1, 2, 3, 5, 6, 7]].reshape(-1, 3), sgn).reshape(n_st, 6).min(1)
            pen_r = float(np.clip(-hh_r[Br["s_st"] > P["SINK_S"]], 0, None).max()) if (Br["s_st"] > P["SINK_S"]).any() else 0.0
            if best_r is None or pen_r < best_r[1] - 1e-4:
                best_r = (Br, pen_r, th_t)
            if pen_r <= 0.01:
                break
        B, penmax, th_used = best_r
        ang = float(th_used)
        rep["ref_mode_theta_used_deg"] = float(th_used)
    T, kind = CC.layout_tris(n_st, 0)
    # 記録：角・長さ・面からの高さ
    Tg = B["Tg"]
    L3 = float(np.sum(np.linalg.norm(np.diff(np.vstack([B["Pc0"], B["Ptip"][None]]), axis=0), axis=1)))
    j3 = max(int(0.3 * n_st), 1)
    d_root = unit(B["Pc0"][j3] - B["Pc0"][0])
    d_all = unit(B["Ptip"] - B["Pc0"][0])
    d_tip = unit(B["Ptip"] - B["Pc0"][-3])
    hh_all = heights(hit, B["ring"][:, [1, 2, 3]].reshape(-1, 3), sgn).reshape(n_st, 3).max(1)
    hc = heights(hit, B["Pc"], sgn)
    rep.update(dict(
        placed=True, root_hit=dict(surface=h0["surf"], r=round(h0["r"], 2), c=round(h0["c"], 2), depth_m=round(h0["depth"], 2), P=[round(float(x), 3) for x in P0]),
        n_dot_view=round(float(nvis @ unit(cam.pos - P0)), 3), alpha_deg=float(al_d), beta_deg=float(be_d), stretch=round(stretch, 3),
        root_dir_vs_normal_deg=round(math.degrees(math.acos(np.clip(d_root @ nvis, -1, 1))), 1),
        plane_D1_vs_normal_deg=round(ang, 1),
        overall_dir_vs_normal_deg=round(math.degrees(math.acos(np.clip(d_all @ nvis, -1, 1))), 1),
        curl_root_to_tip_deg=round(math.degrees(math.acos(np.clip(d_root @ d_tip, -1, 1))), 1),
        tip_down_component=round(float(-d_tip[1]), 3),
        length_3d_m=round(L3, 3), width_max_m=round(float(2 * B["halfw"].max()), 3), thick_max_m=round(float(2 * B["th"].max()), 3),
        min_center_height_beyond_root_m=round(float(hc[B["s_st"] > P["SINK_S"]].min()) if (B["s_st"] > P["SINK_S"]).any() else 0.0, 3),
        penetration_max_m=round(penmax, 3), stations=n_st,
    ))
    # 作り直した爪そのもの（置く前、as02_canonical）：カメラに正対した平面（α = β = 0）の上の平らな三日月。置く時は、この爪を
    # 原画の射線の上で奥行きだけ動かす（原画のカメラからの影は変わらない）。面から見た IoU はこの爪で測る
    m0 = plane_from(cam, P0, cd[i0], tau, 0.0, 0.0)[0]
    Bc = build_rings(sh, M, cam, P0, m0, nvis, ratio_fn, n_st, hero)
    e = dict(id="Y%s" % c["uid"][-3:], uid=c["uid"], V=B["V"], T=T, kind=kind, n=n_st, zone="user100", B=B, m=m, P0=P0, nvis=nvis, sgn=sgn,
             d_root=d_root, d_all=d_all, Bcan=Bc, m0=m0)
    return e


# ---------------------------------------------------------------- 検査
def tri_raster(px, tris, W, H, S=1, x0=0.0, y0=0.0):
    img = np.zeros((H, W), np.uint8)
    pp = np.round(((px - [x0, y0]) * S) * 16).astype(np.int32)
    for t in tris:
        cv2.fillConvexPoly(img, pp[t], 255, lineType=cv2.LINE_8, shift=4)
    return img > 0


def iou_painting(e, c, sh, M, cam, hit):
    """原画のカメラからの爪の影（厚み込み）と、利用者のマスクを表示の画素へ写したものの IoU（8 倍の細かさで、爪の周りだけ）。
    vis は主役波に隠れた所を除いた影で測った値。"""
    q, z = cam.project(e["V"])
    mask = sh["mask"]
    Hm, Wm = mask.shape
    corners = np.array([[0, 0], [Wm, 0], [0, Hm], [Wm, Hm]], np.float64) - 0.5
    cd = corners @ M[:, :2].T + M[:, 2]
    allp = np.vstack([q, cd])
    x0, y0 = np.floor(allp.min(0)) - 2
    x1, y1 = np.ceil(allp.max(0)) + 2
    # 細かさ。OpenCV の fillConvexPoly は縁の画素も塗る（影が約 1 画素太る）ので、細く小さい爪ほど IoU が低く出る。
    # 修正の回 1（as02_fix01_iou_ss）は 32 にして、この偏りを 1/4 にする（今までの 8 の値も記録に残す）
    S = int(P.get("IOU_SS", 8))
    W, H = int((x1 - x0) * S), int((y1 - y0) * S)
    sil = tri_raster(q, e["T"], W, H, S, x0, y0)
    # マスクを同じ枠へ（切り抜き → 表示 → 枠）
    Mf = np.vstack([M, [0, 0, 1]])
    Sf = np.array([[S, 0, -x0 * S], [0, S, -y0 * S], [0, 0, 1]], np.float64)
    # 画素の中心の約束：表示の点 x → 枠の画素 (x − x0)·S（cv2.warpAffine は画素の中心の座標を写す）
    G = (Sf @ Mf)[:2]
    G2 = G.copy()
    G2[:, 2] += (S - 1) * 0.5 * 0   # 簡単のため中心の補正はしない（S=8 で 0.44 表示 px 以下の差）
    mk = cv2.warpAffine(mask.astype(np.uint8) * 255, G2, (W, H), flags=cv2.INTER_LINEAR) > 127
    inter = (sil & mk).sum()
    uni = (sil | mk).sum()
    # 主役波に隠れる所：枠の画素の中心の射線で、爪の深さ（三角形の中の深さは近似で頂点の最小）と主役波の z
    ys, xs = np.nonzero(sil)
    vis = sil.copy()
    if len(xs):
        X = xs / S + x0
        Y = ys / S + y0
        xi = np.clip(np.round(X).astype(int), 0, cam.W - 1)
        yi = np.clip(np.round(Y).astype(int), 0, cam.H - 1)
        zh = hit.zb[yi, xi]
        dh = np.where(zh > 0, 1.0 / np.maximum(zh, 1e-12), np.inf)
        zc = np.percentile(z, 50)
        hid = dh < zc - 0.6
        vis[ys[hid], xs[hid]] = False
    iv = (vis & mk).sum()
    uv = (vis | mk).sum()
    return float(inter / max(uni, 1)), float(iv / max(uv, 1)), float(sil.sum() / S / S), float(mk.sum() / S / S), float(vis.sum() / max(sil.sum(), 1))


def mask_contour(mask, K=4):
    """塗りの外の輪郭（画素の縁の上。4 倍に拡げてから取り、切り抜きの画素の座標へ戻す）。"""
    big = cv2.resize(mask.astype(np.uint8), (mask.shape[1] * K, mask.shape[0] * K), interpolation=cv2.INTER_NEAREST)
    cs, _ = cv2.findContours(big, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    C = max(cs, key=len)[:, 0, :].astype(np.float64)
    return (C + 0.5) / K - 0.5


def iou_face(e, c, sh, M, cam):
    """面から見た（断面の厚みの向き N の平均の向きの正射影）爪の影と、利用者のマスクの輪郭を爪の面へ持ち上げて同じ正射影へ写したものの IoU。
    輪郭の点は、2 次元で最も近い輪の真ん中の点の、輪の面（真ん中を通り法線 N）と、その画素の射線の交わりへ置く。"""
    B = e["B"]
    nf = unit(B["N"].mean(0))
    e1 = unit(B["Bv"][len(B["Bv"]) // 3])
    e1 = unit(e1 - (e1 @ nf) * nf)
    e2 = np.cross(nf, e1)
    P0 = e["P0"]
    V = e["V"]
    X = np.stack([(V - P0) @ e1, (V - P0) @ e2], -1)
    C = mask_contour(sh["mask"])
    k = cKDTree(B["cc2"]).query(C)[1]
    Cd = C @ M[:, :2].T + M[:, 2]
    d = cam.ray(Cd[:, 0], Cd[:, 1])
    Nk, Pk = B["N"][k], B["Pc"][k]
    lam = np.sum((Pk - cam.pos) * Nk, 1) / np.sum(d * Nk, 1)
    Q = cam.pos + lam[:, None] * d
    Y = np.stack([(Q - P0) @ e1, (Q - P0) @ e2], -1)
    allp = np.vstack([X, Y])
    lo = allp.min(0)
    ext = (allp.max(0) - lo).max()
    npx = float(P.get("IOU_FACE_PX", 600.0))       # 修正の回 1 は 2400（縁の画素の偏りを 1/4 に）
    S = npx / max(ext, 1e-6)
    W = H = int(npx + 20)
    px = (X - lo) * S + 10
    sil = tri_raster(px, e["T"], W, H, 1)
    mk = np.zeros((H, W), np.uint8)
    cv2.fillPoly(mk, [np.round(((Y - lo) * S + 10) * 16).astype(np.int32)], 255, shift=4)
    mk = mk > 0
    return float((sil & mk).sum() / max((sil | mk).sum(), 1)), dict(e1=e1, e2=e2, lo=lo, S=S, nf=nf)


def standard_check(e, sh, std):
    """利用者の模型の水準との比べ（数）。"""
    B = e["B"]
    hw = B["halfw"]
    th = B["th"]
    s = B["s_st"]
    ratio = (2 * hw) / np.maximum(2 * th, 1e-9)
    mid = (s > 0.2) & (s < 0.8)
    # 先の細り：幅（2D、切り抜き）を先からの割合 u で
    u = 1 - sh["s"]
    w = sh["w"]
    # 模型の「最大幅」は根元のかかとの合流の所の幅で、指の中ほどの幅の約 1/0.75 倍。こちらの爪は根元が泡の塊へ広がる切り抜きなので、
    # 最大幅の代わりに中ほどの幅 / 0.75 を使う（先の角・細りの割合を模型と同じ物差しで測る）
    wmax = float(sh["w_mid"]) / 0.75
    sel = (u > 0.01) & (u < 0.30) & (w > 0)
    p = float(np.polyfit(np.log(u[sel]), np.log(w[sel] / wmax), 1)[0]) if sel.sum() > 4 else float("nan")
    w_at = {k: round(float(np.interp(k, u[::-1], (w / wmax)[::-1])), 3) for k in (0.02, 0.05, 0.10, 0.20)}
    # 先の角：先から 0.15·wmax・0.30·wmax の長さの所の幅から
    Lpx = sh["L"]
    def tip_angle(frac):
        du = frac * wmax / Lpx
        ww = float(np.interp(du, u[::-1], w[::-1]))
        return math.degrees(2 * math.atan2(0.5 * ww, frac * wmax))
    # 滑らかさ：背骨（真ん中の線）の曲率（中ほどの幅で無次元化）の隣どうしの差（模型と同じ 201 点、根元の 10% と先の 5% を除く）と、
    # 面から見た輪郭の曲率の符号の変わり（模型と同じ：輪郭を幅の 4% でならし、400 点）
    wm = sh["w_mid"]
    cpath = sh["cen"]
    cp, Lc = resample_poly(cpath, 201)
    T = np.gradient(cp, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    ds = Lc / 200.0
    kap = (T[:, 0] * np.gradient(T[:, 1]) - T[:, 1] * np.gradient(T[:, 0])) / ds * wm
    ss = np.linspace(0, 1, 201)
    selk = (ss > 0.10) & (ss < 0.95)
    dk = np.abs(np.diff(kap[selk]))
    poly = sh["poly"]
    Pr, _ = resample_poly(np.vstack([poly, poly[:1]]), 400)
    k_s = max(int(round(0.04 * wm * 400 / max(per_len(np.vstack([poly, poly[:1]])), 1e-9))), 1)
    Pr = ndimage.uniform_filter1d(Pr, size=2 * k_s + 1, axis=0, mode="wrap")
    a1 = np.gradient(Pr, axis=0)
    a2 = np.gradient(a1, axis=0)
    kc = ndimage.uniform_filter1d(a1[:, 0] * a2[:, 1] - a1[:, 1] * a2[:, 0], 9, mode="wrap")
    sc = int(np.sum(np.sign(kc[:-1]) != np.sign(kc[1:])))
    return dict(width_over_thickness_mid=round(float(np.median(ratio[mid])), 3) if mid.any() else None,
                section_fill=round((P["LENS_A"] + P["LENS_B"]) / 2, 3),
                taper_power_tip30=round(p, 3), w_over_wmax_at_u=w_at,
                tip_angle_deg_015=round(tip_angle(0.15), 1), tip_angle_deg_030=round(tip_angle(0.30), 1),
                heel_protrusion_over_wmax=P["HEEL_H"],
                spine_curv_jump_p95=round(float(np.percentile(dk, 95)), 4) if len(dk) else None, spine_curv_jump_max=round(float(dk.max()), 4) if len(dk) else None,
                outline_curvature_sign_changes=sc,
                outline_lumps_hysteresis=outline_lumps(sh["poly"], wmax),
                length_over_wmax=round(float(Lpx / wmax), 3))


def judge(chk, std):
    """模型の水準（claw_mid・claw_low のうち緩い方を下限）と比べた合否。"""
    mm = std["models"]
    fails = []
    r = chk["width_over_thickness_mid"]
    if r is None or not (1.1 <= r <= 1.7):
        fails.append("断面の幅:厚み %s が 1.1〜1.7 の外" % r)
    if not (chk["tip_angle_deg_015"] <= 90.0):
        fails.append("先の角 %.0f° > 90°（claw_low 66°、claw_mid の上端は丸い）" % chk["tip_angle_deg_015"])
    if chk["taper_power_tip30"] != chk["taper_power_tip30"] or chk["taper_power_tip30"] < 0.3:
        fails.append("先の細りの指数 %.2f < 0.3（先が太いまま終わる）" % chk["taper_power_tip30"])
    # claw_low は面の少ない模型で面の角が数に出る（30）ので、滑らかな claw_mid（8）＋かかとの 2 を上限にする
    lim_sc = mm["claw_mid"]["outline_lumps_hysteresis"] + 2
    if chk["outline_lumps_hysteresis"] > lim_sc:
        fails.append("輪郭のでこぼこ %d > %d（claw_mid + かかとの 2）" % (chk["outline_lumps_hysteresis"], lim_sc))
    lim_j = max(mm["claw_mid"]["spine_curvature_x_wmax"]["jump_p95"], mm["claw_low"]["spine_curvature_x_wmax"]["jump_p95"])
    if chk["spine_curv_jump_p95"] > lim_j:
        fails.append("背骨の曲率の跳び p95 %.2f > 模型 %.2f" % (chk["spine_curv_jump_p95"], lim_j))
    return fails


# ---------------------------------------------------------------- 並べ・書き出し
def write_layout(out, entries, extra):
    os.makedirs(out, exist_ok=True)
    V, T, A, claws = [], [], [], []
    off = 0
    for k, e in enumerate(entries):
        nv = len(e["V"])
        assert nv == 8 * e["n"] + 11, (e["id"], nv)
        V.append(e["V"])
        T.append(e["T"] + off)
        A.append(np.stack([np.full(len(e["kind"]), k), e["kind"]], 1))
        claws.append({"id": e["id"], "index": k, "vert_offset": off, "vert_count": nv, "stations": e["n"], "type": e["zone"], "user_id": e["uid"]})
        off += nv
    Vv = np.concatenate(V).astype(np.float32)[None]
    Tt = np.concatenate(T).astype(np.int32)
    Aa = np.concatenate(A).astype(np.uint16)
    assert np.isfinite(Vv).all()
    fn = dict(frames="ds33_claw_frames_f32.bin", tris="ds33_claw_tris_i32.bin", tri_attr="ds33_claw_tri_attr_u16.bin", skel="ds33_claw_skel_f32.bin")
    Vv.tofile(os.path.join(out, fn["frames"]))
    Tt.tofile(os.path.join(out, fn["tris"]))
    Aa.tofile(os.path.join(out, fn["tri_attr"]))
    np.zeros((1, len(entries), 36), np.float32).tofile(os.path.join(out, fn["skel"]))
    files = {k: {"file": v, "sha256": sha(os.path.join(out, v)), "bytes": os.path.getsize(os.path.join(out, v))} for k, v in fn.items()}
    lay = {"schema": "GreatWave.DS33.claw_layout/1", "frames": 1, "hz": 30.0, "vertices": int(off), "triangles": int(len(Tt)),
           "clock_ja": "美術の見本02：コマ 1 つ（t* の静止）。DS34ClawPlayer はどの時刻でもこのコマを使う", "timewarp": "なし（静止）",
           "claws": claws, "files": files,
           "vertex_order_ja": "爪ごとに 根元 1・輪 stations × 8・先 1・根元の円の中心 1・円 8（設計33 と同じ並び。根元の円は根元の点に潰した）。"
                              "輪の 8 頂点はレンズ形：q0・q4 が縁（水色の版）、q1〜3 がカメラ側の面、q5〜7 が裏の面",
           "as02": dict(tool="Tools/GWWaveGen/as02/as02_claws100.py", params=P, **extra)}
    json.dump(lay, open(os.path.join(out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(out, "as02_claws.obj"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# 美術の見本02 利用者の 100 本の爪を 3D に戻したもの（t* の静止、ワールドの m。Unity の左手系の座標のまま）\n")
        for v in Vv[0]:
            f.write("v %.5f %.5f %.5f\n" % (v[0], v[1], v[2]))
        for k, e in enumerate(entries):
            f.write("g %s_%s\n" % (e["id"], e["uid"]))
            o = claws[k]["vert_offset"]
            for t, kd in zip(e["T"], e["kind"]):
                if kd == 2:
                    continue
                f.write("f %d %d %d\n" % (t[0] + o + 1, t[1] + o + 1, t[2] + o + 1))
    return lay


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUTD)
    ap.add_argument("--only", default="", help="利用者の爪の番号（claw001,claw002…）だけ")
    ap.add_argument("--mode", default="paint", choices=["paint", "ref", "arch"])
    ap.add_argument("--hero", default="", help="主役波の hero_pkg（既定は仕上げ32 の Build/Polish/32/white/hero_pkg。形の部が背を直した時に置き直すため）")
    ap.add_argument("--st-max", default=200, type=int, help="--fix01 の時の輪の数の上限")
    ap.add_argument("--fix01", action="store_true",
                    help="美術の見本02 の修正の回 1：肋の組み方をならし（PAIR_SIG）、爪ごとに輪郭のならしと幅の倍率を選び（C2 の 2 次元の検査を通る中で IoU 最大）、"
                         "原画視点の IoU が %.2f に届かない爪は厚みの向きを射線へ寄せ（N_ORTHO を下げ）、中ほどの断面の比の上限を 1.65 にする" % 0.86)
    a = ap.parse_args()
    P["MODE"] = a.mode
    if a.fix01:
        # 輪の数を増やす（輪の間は直線なので、少ない輪では面から見た輪郭がマスクの縁から離れ、原画視点・面から見た IoU が 2 次元の形より落ちていた）
        # 原画視点の IoU と面から見た IoU は縁の画素の偏りを減らすため細かく測る（IOU_SS 32・IOU_FACE_PX 2400）。形は切り抜きの枠で止める（CLIP_CROP）
        P.update(PAIR_SIG=0.6, RATIO_MAX_MID=1.65, FIX01=1, ST_MAX=int(a.st_max), ST_PER_PX=3.0, CLIP_CROP=1, IOU_SS=32, IOU_FACE_PX=2400.0)
    if a.hero:
        CC.HERO = a.hero if os.path.isabs(a.hero) else os.path.join(REPO, a.hero)
    t0 = time.time()
    std = json.load(open(STD, encoding="utf-8"))
    refp = json.load(open(REFP, encoding="utf-8"))
    P["THETA_T"] = float(refp["angle_root_dir_vs_surface_normal_deg"]["p50"])
    X0 = CC.load_hero()
    hero = CC.Hero(X0)
    cam = CC.painting_cam()
    hit = Hit(hero, cam, load_sea())
    users, reg, corr = load_user()
    if a.only:
        keep = set(a.only.split(","))
        users = [u for u in users if u["uid"] in keep]
    ents, recs = [], []
    N_ORTHO0 = P["N_ORTHO"]
    for c in users:
        P["N_ORTHO"] = N_ORTHO0          # 爪ごとに選ぶ値（--fix01）を次の爪へ持ち越さない
        rep = dict(user_id=c["uid"], registration=dict(source=c["reg_src"], ncc_after_ecc=c["ncc"]),
                   pl32_status=c["status"].get("status"), pl32_best_id=c["status"].get("best_id"),
                   pl32_reason_ja=c["status"].get("reason_ja"),
                   pl32_addition=(c["addition"] or {}).get("decision"))
        try:
            if a.fix01:
                sh, _sel = choose_shape_fix01(c, std)
            else:
                sh = shape2d(c, std)
        except Exception as ex:  # noqa: BLE001
            rep["placed"] = False
            rep["why_not_ja"] = "2 次元の形を作れない: %r" % (ex,)
            recs.append(rep)
            continue
        rep["shape2d"] = sh["rec"]
        M = disp_affine(c["A"])
        if a.fix01:
            # 修正の回 1（as02_fix01_northo）：原画視点の IoU（と面から見た IoU の小さい方）が届かない爪は、断面の厚みの向きを射線へ寄せる
            # （N_ORTHO を下げる。厚みが原画のカメラの画面で横へはみ出す分が減る）。届く最初の値、届かなければ小さい方の IoU が最大の値
            n0 = P["N_ORTHO"]
            trial = []
            for nv in FIX01_NORTHO:
                P["N_ORTHO"] = nv
                rep_t = dict(rep)
                e_t = place(sh, c, hero, cam, hit, M, rep_t)
                if e_t is None:
                    trial.append((nv, None, rep_t, None))
                    break
                # 原画視点の IoU と面から見た IoU（作り直した爪）の小さい方で選ぶ（C3 はどちらも 0.85 以上）
                ip_t = min(iou_painting(e_t, c, sh, M, cam, hit)[0],
                           iou_face(dict(e_t, V=e_t["Bcan"]["V"], B=e_t["Bcan"], m=e_t["m0"]), c, sh, M, cam)[0])
                trial.append((nv, ip_t, rep_t, e_t))
                if ip_t >= FIX01_IOU_PAINT_OK:
                    break
            okt = [t for t in trial if t[1] is not None]
            pick = next((t for t in okt if t[1] >= FIX01_IOU_PAINT_OK), max(okt, key=lambda t: t[1]) if okt else trial[-1])
            P["N_ORTHO"] = pick[0]
            rep.clear(); rep.update(pick[2])
            rep["fix01_n_ortho"] = pick[0]
            rep["fix01_n_ortho_trials"] = [(t[0], None if t[1] is None else round(t[1], 4)) for t in trial]
            e = pick[3]
        else:
            e = place(sh, c, hero, cam, hit, M, rep)
        if e is not None:
            if a.fix01:
                e["n_ortho"] = P["N_ORTHO"]
            ip, ipv, a_sil, a_mask, vis = iou_painting(e, c, sh, M, cam, hit)
            iff, _ = iou_face(dict(e, V=e["Bcan"]["V"], B=e["Bcan"], m=e["m0"]), c, sh, M, cam)
            iff_own, _ = iou_face(e, c, sh, M, cam)
            rep["iou_face_placed_own_axis"] = round(iff_own, 4)
            chk = standard_check(e, sh, std)
            fails = judge(chk, std)
            rep.update(dict(iou_painting=round(ip, 4), iou_painting_visible=round(ipv, 4), area_painting_px=round(a_sil, 1),
                            area_mask_px=round(a_mask, 1), visible_fraction=round(vis, 3), iou_face=round(iff, 4), standard=chk,
                            standard_fails_ja=fails))
            if iff < 0.85:
                rep["standard_fails_ja"].append("面から見た IoU %.3f < 0.85" % iff)
            if a.fix01:
                # 今までの細かさ（原画視点 S 8、面から 600 px）の値も残す（測り方を変えた分を見えるように）
                ss0, fp0 = P["IOU_SS"], P["IOU_FACE_PX"]
                P["IOU_SS"], P["IOU_FACE_PX"] = 8, 600.0
                rep["iou_painting_s8"] = round(iou_painting(e, c, sh, M, cam, hit)[0], 4)
                rep["iou_face_600px"] = round(iou_face(dict(e, V=e["Bcan"]["V"], B=e["Bcan"], m=e["m0"]), c, sh, M, cam)[0], 4)
                P["IOU_SS"], P["IOU_FACE_PX"] = ss0, fp0
            e["rep"] = rep
            ents.append(e)
        recs.append(rep)
        print(c["uid"], "placed" if e is not None else "-", rep.get("iou_face"), rep.get("iou_painting"), rep.get("alpha_deg"), rep.get("beta_deg"),
              rep.get("root_dir_vs_normal_deg"), rep.get("length_3d_m"), rep.get("standard_fails_ja"), flush=True)
    # 重複：原画視点の影が、小さい方の面積の DUP_FRAC 以上重なる 2 本は同じ爪の 2 回の切り抜き（利用者の 100 本には重複がある。
    # 仕上げ32 の記録：claw069・076 は claw053 と同じ指、claw099 は claw098 と同じ所）。位置合わせの NCC の高い方を残す
    sil0 = []
    for e in ents:
        q, z = cam.project(e["Bcan"]["V"])     # 置き方によらず、作り直した爪（カメラに正対）の影で決める
        sil0.append(tri_raster(q, e["T"], cam.W, cam.H, 1))
    area = np.array([s_.sum() for s_ in sil0], float)
    drop = set()
    order = sorted(range(len(ents)), key=lambda i: -ents[i]["rep"]["registration"]["ncc_after_ecc"])
    for ii, i in enumerate(order):
        if i in drop:
            continue
        for j in order[ii + 1:]:
            if j in drop:
                continue
            inter = float((sil0[i] & sil0[j]).sum())
            if inter / max(min(area[i], area[j]), 1.0) >= P["DUP_FRAC"]:
                drop.add(j)
                r = ents[j]["rep"]
                r["placed"] = False
                r["duplicate_of"] = ents[i]["uid"]
                r["why_not_ja"] = "重複：原画視点の影が %s と小さい方の面積の %.0f%% 重なる（同じ爪の 2 回の切り抜き）。位置合わせの NCC の高い %s を残した" % (
                    ents[i]["uid"], 100 * inter / max(min(area[i], area[j]), 1.0), ents[i]["uid"])
    ents = [e for k, e in enumerate(ents) if k not in drop]
    P["N_ORTHO"] = N_ORTHO0
    print("duplicates dropped", sorted(ents_uid for ents_uid in [r["user_id"] for r in recs if r.get("duplicate_of")]), flush=True)
    # 並び：間隔・扇・重なり（原画視点）・爪どうしの交わり
    R = np.array([e["P0"] for e in ents])
    Ls = np.array([e["rep"]["length_3d_m"] for e in ents])
    spacing = None
    if len(ents) > 2:
        tr = cKDTree(R)
        dd, jj = tr.query(R, k=2)
        fan = [math.degrees(math.acos(np.clip(ents[i]["d_all"] @ ents[jj[i, 1]]["d_all"], -1, 1))) for i in range(len(ents))]
        nfan = [math.degrees(math.acos(np.clip(ents[i]["nvis"] @ ents[jj[i, 1]]["nvis"], -1, 1))) for i in range(len(ents))]
        for i, e in enumerate(ents):
            e["rep"]["nearest_root_m"] = round(float(dd[i, 1]), 3)
            e["rep"]["nearest_root_over_length"] = round(float(dd[i, 1] / max(Ls[i], 1e-6)), 3)
            e["rep"]["fan_to_nearest_deg"] = round(fan[i], 1)
            e["rep"]["normal_spread_to_nearest_deg"] = round(nfan[i], 1)
        spacing = dict(nearest_root_m=dd[:, 1], over_len=dd[:, 1] / np.maximum(Ls, 1e-6), fan=np.array(fan), nfan=np.array(nfan))
    # 交わり：背骨の点どうしの距離 < 厚みの半分の和
    coll = []
    for i in range(len(ents)):
        for j in range(i + 1, len(ents)):
            if np.linalg.norm(R[i] - R[j]) > Ls[i] + Ls[j]:
                continue
            Bi, Bj = ents[i]["B"], ents[j]["B"]
            D = np.linalg.norm(Bi["Pc"][:, None, :] - Bj["Pc"][None, :, :], axis=-1)
            lim = Bi["th"][:, None] + Bj["th"][None, :]
            if (D < lim).any():
                coll.append((ents[i]["uid"], ents[j]["uid"], round(float((lim - D).max()), 3)))
    # 原画視点の重なり
    cover = np.zeros((cam.H, cam.W), np.int32)
    sils = []
    for e in ents:
        q, z = cam.project(e["V"])
        sil = tri_raster(q, e["T"], cam.W, cam.H, 1)
        sils.append(sil)
        cover += sil
    for e, sil in zip(ents, sils):
        e["rep"]["painting_overlap_fraction"] = round(float((cover[sil] > 1).mean()) if sil.any() else 0.0, 3)
    lay = write_layout(a.out, ents, dict(hero_pkg=os.path.relpath(CC.HERO, REPO).replace("\\", "/"), user_root=USER))

    def st(x):
        x = np.asarray([v for v in x if v is not None and v == v], float)
        if not len(x):
            return None
        return {"n": int(len(x)), "p10": round(float(np.percentile(x, 10)), 3), "p50": round(float(np.percentile(x, 50)), 3),
                "p90": round(float(np.percentile(x, 90)), 3), "min": round(float(x.min()), 3), "max": round(float(x.max()), 3)}
    placed = [r for r in recs if r.get("placed")]
    summ = dict(
        users=len(recs), placed=len(placed), not_placed=[(r["user_id"], r.get("why_not_ja")) for r in recs if not r.get("placed")],
        iou_face=st([r["iou_face"] for r in placed]), iou_painting=st([r["iou_painting"] for r in placed]),
        iou_painting_visible=st([r["iou_painting_visible"] for r in placed]),
        iou_face_below_085=[r["user_id"] for r in placed if r["iou_face"] < 0.85],
        iou_painting_below_085=[r["user_id"] for r in placed if r["iou_painting"] < 0.85],
        standard_fail=[(r["user_id"], r["standard_fails_ja"]) for r in placed if r["standard_fails_ja"]],
        alpha_deg=st([r["alpha_deg"] for r in placed]), beta_deg=st([r["beta_deg"] for r in placed]), stretch=st([r["stretch"] for r in placed]),
        root_dir_vs_normal_deg=st([r["root_dir_vs_normal_deg"] for r in placed]),
        overall_dir_vs_normal_deg=st([r["overall_dir_vs_normal_deg"] for r in placed]),
        curl_root_to_tip_deg=st([r["curl_root_to_tip_deg"] for r in placed]), tip_down_component=st([r["tip_down_component"] for r in placed]),
        length_3d_m=st([r["length_3d_m"] for r in placed]), width_max_m=st([r["width_max_m"] for r in placed]),
        thick_max_m=st([r["thick_max_m"] for r in placed]),
        penetration_max_m=st([r["penetration_max_m"] for r in placed]),
        nearest_root_over_length=st(spacing["over_len"]) if spacing else None, nearest_root_m=st(spacing["nearest_root_m"]) if spacing else None,
        fan_to_nearest_deg=st(spacing["fan"]) if spacing else None, normal_spread_to_nearest_deg=st(spacing["nfan"]) if spacing else None,
        painting_overlap_fraction=st([e["rep"]["painting_overlap_fraction"] for e in ents]),
        painting_layers=dict(p50=float(np.percentile(cover[cover > 0], 50)) if (cover > 0).any() else 0,
                             p90=float(np.percentile(cover[cover > 0], 90)) if (cover > 0).any() else 0, max=int(cover.max())),
        collisions=coll,
        reference=dict((k, refp[k]) for k in ("angle_root_dir_vs_surface_normal_deg", "angle_overall_dir_vs_surface_normal_deg", "curl_root_to_tip_deg",
                                              "tip_down_component", "nearest_root_spacing_over_length", "fan_angle_to_nearest_deg",
                                              "normal_angle_to_nearest_deg", "painting_view_overlap_fraction_per_claw")),
    )
    report = dict(schema="GreatWave.AS02.claws100_report/1", params=P,
                  inputs=dict(registration=dict(path=os.path.relpath(REG, REPO).replace("\\", "/"), sha256=sha(REG)),
                              correspondence=dict(path=os.path.relpath(CORR, REPO).replace("\\", "/"), sha256=sha(CORR)),
                              points_csv=dict(path=POINTS, sha256=sha(POINTS)),
                              user_claw_standard=dict(path=os.path.relpath(STD, REPO).replace("\\", "/"), sha256=sha(STD)),
                              ref_placement=dict(path=os.path.relpath(REFP, REPO).replace("\\", "/"), sha256=sha(REFP)),
                              hero_pkg=os.path.relpath(CC.HERO, REPO).replace("\\", "/")),
                  user_files_sha256_see="Build/Design/32/list+ids/ds32_user100_registration.json の user_files_sha256",
                  summary=summ, claws=recs, layout=dict(vertices=lay["vertices"], triangles=lay["triangles"], files=lay["files"]),
                  elapsed_s=round(time.time() - t0, 1))
    U.jdump(os.path.join(a.out, "as02_claws_report.json"), report)
    np.save(os.path.join(a.out, "as02_entries.npy"),
            np.array([dict(id=e["id"], uid=e["uid"], V=e["V"], T=e["T"], kind=e["kind"], n=e["n"], m=e["m"], P0=e["P0"], nvis=e["nvis"],
                           Bv=e["B"]["Bv"], N=e["B"]["N"], s_st=e["B"]["s_st"], Vcan=e["Bcan"]["V"], Ncan=e["Bcan"]["N"]) for e in ents],
                     dtype=object), allow_pickle=True)
    print("AS02_CLAWS_DONE placed", len(ents), "of", len(recs), "vertices", lay["vertices"], "%.1fs" % (time.time() - t0))
    print(json.dumps({k: v for k, v in summ.items() if k not in ("reference",)}, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    main()
