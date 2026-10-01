# -*- coding: utf-8 -*-
"""仕上げ28 の原画視点の後退の回復（rec）の共通部。py -3.10（numpy・OpenCV・PIL）。

第2回（r2）で採った K*′ P28R2 は、管を前へ出す段（T）で、原画視点の左の船（157 boat_left）を隠し、原画視点の波の面の中に
新しい線（反転シェルの外殻線）を出した（評審の must_fix の 1・2）。回復は、同じ生成器（r2_build.py）の設計に、
原画視点で「土台で波に覆われていない画素」を通る射線の禁止域（画面の覆いの禁止域）と、新しい輪郭（表裏の境）を作らない条件を
加えて作り直す。この共通部は、原画視点の z バッファー（candA2_common.zbuffer と同じ厳密な z バッファー）、
四角形ごとの表裏、外殻線の出る画素の予測（設計38 の線の印 ds38_hero_linemask を読む）、Unity の t* の ID 画像との比べを持つ。
座標は kh_common と同じ（a = 進行方向 T、y = 高さ、c = 波峰線 E）。参照モデルは読まない（F13-1）。
"""
import os
import sys
import json
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for _p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"),
           os.path.join(REPO, "Tools", "PaintingTruth"), os.path.join(REPO, "Tools", "GWWaveGen")):
    if _p not in sys.path:
        sys.path.append(_p)
import candA2_common as C2  # noqa: E402

NU, NV = 400, 240
P28 = os.path.join(REPO, "Unity", "Build", "Polish", "28")
OUT = os.path.join(P28, "rec")
ROWS = {
    "R4": os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz"),
    "P28R1": os.path.join(P28, "r1_rays", "cand", "kstarP28R1_a45_rows.npz"),
    "P28R2": os.path.join(P28, "kstar_p28", "kstarP28R2_a45_rows.npz"),
}
LINEMASK = os.path.join(REPO, "Unity", "Build", "Design", "38", "outlines", "unity", "prep", "ds38_hero_linemask_f32.bin")
# Unity の t* の ID 画像（設計40 の全体の ID 画像と同じ作り方、3840×2160）：段階9 の場面（主役波 R4）
IDS_STAGE9 = os.path.join(P28, "unity", "scene_stage9", "full", "ids_noline_noclaws.png")
ID_COL = {"sky": (0, 255, 255), "boat_left": (34, 0, 0), "boat_mid": (0, 34, 0), "boat_fg": (34, 34, 0), "cpu": (0, 0, 0)}


def load_rows(p):
    z = np.load(p)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def frame():
    return C2.pframe()


def world(c, A, Y):
    V1, tgt, fr = frame()
    return fr.world(c, A, Y)


def cam_pos():
    """原画視点のカメラの位置（world 座標）。fr.cam の投影の中心。"""
    V1, tgt, fr = frame()
    cam = fr.cam
    for k in ("pos", "position", "C", "eye"):
        if hasattr(cam, k):
            return np.asarray(getattr(cam, k), float)
    raise AttributeError("camera position")


def zbuf(c, A, Y, ss=1):
    """原画視点の厳密な z バッファー（H×W の奥行き、inf＝空）と三角形の番号（+1、0＝空）。"""
    return C2.zbuffer(c, A, Y, ss=ss, want_ids=True, max_px=128)


def tri_quad(ids):
    """三角形の番号（+1）→ 四角形の (行, 列)。空は -1。"""
    t = ids - 1
    q = np.where(t >= 0, t // 2, -1)
    iv = np.where(q >= 0, q // (NU - 1), -1)
    iu = np.where(q >= 0, q % (NU - 1), -1)
    return iv, iu


def quad_facing(c, A, Y, eye):
    """四角形ごとの表裏（+1 表：面の法線（三角形の順、平らな海で +Y が表）がカメラを向く、-1 裏）と、法線とカメラの向きの内積（単位）。"""
    X = world(c, A, Y)                      # (NV, NU, 3)
    p00 = X[:-1, :-1]; p10 = X[1:, :-1]; p01 = X[:-1, 1:]; p11 = X[1:, 1:]
    # 三角形 (a=p00, b=p10, c=p01) と (c=p01, b=p10, d=p11) の法線の和
    n = np.cross(p10 - p00, p01 - p00) + np.cross(p10 - p01, p11 - p01)
    cen = 0.25 * (p00 + p10 + p01 + p11)
    v = eye[None, None, :] - cen
    d = (n * v).sum(-1) / (np.linalg.norm(n, axis=-1) * np.linalg.norm(v, axis=-1) + 1e-12)
    return np.where(d > 0, 1, -1), d


def upright_tri_mask(Y, y_min=0.15):
    """三角形ごとに「立ち上がった波の面」か（3 頂点の最大の高さ > y_min。平らな海の帯を除く）。"""
    V1, tgt, fr = frame()
    T = V1.triangles(NU, NV)
    yv = Y.reshape(-1)
    return yv[T].max(1) > y_min


def load_linemask():
    m = np.fromfile(LINEMASK, dtype=np.float32)
    return m.reshape(NV, NU)


def line_pixels(c, A, Y, ids, eye, mask=None, ss=1):
    """外殻線の出る画素の予測：見えている表の四角形のうち、格子の隣（±1 行・±1 列）に裏の四角形があるもの（輪郭の手前の側）で、
    その四角形の 4 頂点の線の印の最小が 0.5 以上（原画視点で描く）ものの画素。設計38 の反転シェルは、裏の三角形を法線の向きへ
    押し出して描くので、線は見えている輪郭に沿って出る（押し出しの幅 ≥ 1.5 px）。"""
    f, _ = quad_facing(c, A, Y, eye)
    back = f < 0
    nb = np.zeros_like(back)
    nb[1:] |= back[:-1]; nb[:-1] |= back[1:]; nb[:, 1:] |= back[:, :-1]; nb[:, :-1] |= back[:, 1:]
    cont = (f > 0) & nb
    if mask is not None:
        mq = np.minimum.reduce([mask[:-1, :-1], mask[1:, :-1], mask[:-1, 1:], mask[1:, 1:]])
        cont &= mq >= 0.5
    iv, iu = tri_quad(ids)
    vis = iv >= 0
    out = np.zeros(ids.shape, bool)
    out[vis] = cont[iv[vis], iu[vis]]
    return out, cont


def raster(Xv, T, attr=None, ss=1, max_px=256):
    """一般の三角形の原画視点の厳密な z バッファー（candA2_common.zbuffer と同じ作り、遠近の正しい奥行き）。
    Xv (N,3) world、T (M,3)。attr (N,) を与えると、見えている三角形の重心座標で（遠近を正しく）補間した値の画像も返す。
    返り値：z (H,W)（inf＝空）、tri (H,W)（三角形の番号、-1＝空）、val (H,W) か None。"""
    V1, tgt, fr = frame()
    P = fr.cam.project(Xv)
    W, H = fr.cam.W * ss, fr.cam.H * ss
    xy = (P[:, :2] + 0.5) * ss - 0.5
    iz = 1.0 / np.maximum(P[:, 2], 1e-6)
    ok = (P[T, 2] > 0.5).all(1)
    t0, t1, t2 = xy[T[:, 0]], xy[T[:, 1]], xy[T[:, 2]]
    x0 = np.floor(np.minimum.reduce([t0[:, 0], t1[:, 0], t2[:, 0]])).astype(int)
    x1 = np.ceil(np.maximum.reduce([t0[:, 0], t1[:, 0], t2[:, 0]])).astype(int)
    y0 = np.floor(np.minimum.reduce([t0[:, 1], t1[:, 1], t2[:, 1]])).astype(int)
    y1 = np.ceil(np.maximum.reduce([t0[:, 1], t1[:, 1], t2[:, 1]])).astype(int)
    ok &= (x1 >= 0) & (x0 < W) & (y1 >= 0) & (y0 < H)
    x0 = np.clip(x0, 0, W - 1); x1 = np.clip(x1, 0, W - 1); y0 = np.clip(y0, 0, H - 1); y1 = np.clip(y1, 0, H - 1)
    bs = np.maximum(x1 - x0 + 1, y1 - y0 + 1)
    z = np.full(W * H, np.inf)
    recs = []
    for lo, hi in ((0, 4), (4, 8), (8, 16), (16, 32), (32, 64), (64, 128), (128, 256)):
        if lo >= max_px:
            break
        sel = np.nonzero(ok & (bs > lo) & (bs <= hi))[0]
        if not len(sel):
            continue
        n = hi
        chunk = max(1, int(2e6 // (n * n)))
        g = np.arange(n)
        for k in range(0, len(sel), chunk):
            s = sel[k:k + chunk]
            px = np.broadcast_to(x0[s, None, None] + g[None, None, :], (len(s), n, n))
            py = np.broadcast_to(y0[s, None, None] + g[None, :, None], (len(s), n, n))
            inb = (px <= x1[s, None, None]) & (py <= y1[s, None, None])
            a_, b_, c_ = t0[s], t1[s], t2[s]
            den = (b_[:, 1] - c_[:, 1]) * (a_[:, 0] - c_[:, 0]) + (c_[:, 0] - b_[:, 0]) * (a_[:, 1] - c_[:, 1])
            good = np.abs(den) > 1e-12
            den = np.where(good, den, 1.0)[:, None, None]
            l0 = ((b_[:, 1] - c_[:, 1])[:, None, None] * (px - c_[:, 0, None, None]) + (c_[:, 0] - b_[:, 0])[:, None, None] * (py - c_[:, 1, None, None])) / den
            l1 = ((c_[:, 1] - a_[:, 1])[:, None, None] * (px - c_[:, 0, None, None]) + (a_[:, 0] - c_[:, 0])[:, None, None] * (py - c_[:, 1, None, None])) / den
            l2 = 1 - l0 - l1
            e = -1e-9
            inside = inb & good[:, None, None] & (l0 >= e) & (l1 >= e) & (l2 >= e)
            w0 = l0 * iz[T[s, 0]][:, None, None]; w1 = l1 * iz[T[s, 1]][:, None, None]; w2 = l2 * iz[T[s, 2]][:, None, None]
            izs = w0 + w1 + w2
            dep = 1.0 / np.maximum(izs, 1e-12)
            ti, yy_, xx_ = np.nonzero(inside)
            pix = py[ti, yy_, xx_] * W + px[ti, yy_, xx_]
            d = dep[ti, yy_, xx_]
            np.minimum.at(z, pix, d)
            v = None
            if attr is not None:
                vv = (w0 * attr[T[s, 0]][:, None, None] + w1 * attr[T[s, 1]][:, None, None] + w2 * attr[T[s, 2]][:, None, None]) / np.maximum(izs, 1e-12)
                v = vv[ti, yy_, xx_]
            recs.append((pix, d, s[ti], v))
    tri = np.full(W * H, -1, np.int64)
    val = np.zeros(W * H) if attr is not None else None
    for pix, d, tr, v in recs:
        m = d <= z[pix] + 1e-9
        tri[pix[m]] = tr[m]
        if val is not None:
            val[pix[m]] = v[m]
    return z.reshape(H, W), tri.reshape(H, W), (val.reshape(H, W) if val is not None else None)


def vertex_normals_win(X, col_lo=18, col_hi=394):
    """DS38NormalWin と同じ頂点の法線（6 つの三角形の外積の和、列の範囲の外の隣は無いもの）。X (NV, NU, 3)。"""
    nv, nu = X.shape[:2]
    n = np.zeros_like(X)
    r = np.arange(nv)[:, None]; cidx = np.arange(nu)[None, :]
    hu = np.broadcast_to(r > 0, (nv, nu)); hd = np.broadcast_to(r + 1 < nv, (nv, nu))
    hl = np.broadcast_to(cidx > col_lo, (nv, nu)); hr = np.broadcast_to(cidx + 1 <= col_hi, (nv, nu))

    def sh(dr, dc):
        out = np.zeros_like(X)
        rs = slice(max(dr, 0), nv + min(dr, 0)); rd = slice(max(-dr, 0), nv + min(-dr, 0))
        cs = slice(max(dc, 0), nu + min(dc, 0)); cd = slice(max(-dc, 0), nu + min(-dc, 0))
        out[rd, cd] = X[rs, cs] - X[rd, cd]
        return out
    dD = sh(1, 0); dR = sh(0, 1); dU = sh(-1, 0); dL = sh(0, -1); dDL = sh(1, -1); dUR = sh(-1, 1)
    m = (hd & hr)[..., None]; n += np.where(m, np.cross(dD, dR), 0)
    m = (hd & hl)[..., None]; n += np.where(m, np.cross(dL, dDL) + np.cross(dDL, dD), 0)
    m = (hu & hr)[..., None]; n += np.where(m, np.cross(dUR, dU) + np.cross(dR, dUR), 0)
    m = (hu & hl)[..., None]; n += np.where(m, np.cross(dU, dL), 0)
    ln = np.linalg.norm(n, axis=-1, keepdims=True)
    return np.where(ln > 1e-30, n / np.maximum(ln, 1e-30), np.array([0.0, 1.0, 0.0]))


def shell_lines(c, A, Y, mask, eye=None, ss=1, col_lo=18, col_hi=394, line_angle=0.0012865962, max_w=0.3, min_px=1.5, want_src=False):
    """設計38 の主役波の外殻線（反転シェル）を原画視点で numpy で描いた線の画素の予測（原画視点の重み 0：押し下げなし、
    面の法線で表裏、頂点の印 mask を重心で補間して 0.5 未満は描かない）。返り値：line (H,W) bool、面の z、シェルの z。"""
    V1, tgt, fr = frame()
    eye = cam_pos() if eye is None else eye
    X = world(c, A, Y)
    nv, nu = X.shape[:2]
    T = V1.triangles(nu, nv)
    q = np.arange(len(T)) // 2
    qc = q % (nu - 1)
    inwin = (qc >= col_lo) & (qc + 1 <= col_hi)
    Xv = X.reshape(-1, 3)
    zs, ts, _ = raster(Xv, T[inwin], None, ss)
    # 裏を向く三角形（面の法線）
    p0, p1, p2 = Xv[T[:, 0]], Xv[T[:, 1]], Xv[T[:, 2]]
    fn = np.cross(p1 - p0, p2 - p0)
    cen = (p0 + p1 + p2) / 3.0
    back = (fn * (eye[None, :] - cen)).sum(1) <= 0
    sel = back & inwin
    nrm = vertex_normals_win(X, col_lo, col_hi).reshape(-1, 3)
    d = np.linalg.norm(Xv - eye[None, :], axis=1)
    pixang = 2.0 * fr.cam.t / (fr.cam.H * ss)
    w = np.maximum(np.minimum(d * line_angle, max_w), d * min_px * pixang)
    Xs = Xv + nrm * w[:, None]
    zl, tl, kv = raster(Xs, T[sel], mask.reshape(-1).astype(float), ss)
    line = np.isfinite(zl) & (zl < zs - 1e-4) & (kv >= 0.5)
    if want_src:
        src = np.full(tl.shape, -1, np.int64)
        idx = np.nonzero(sel)[0]
        ok = tl >= 0
        src[ok] = idx[tl[ok]] // 2          # 四角形の番号（行 = q // (nu-1)、列 = q % (nu-1)）
        return line, zs, zl, src
    return line, zs, zl


def stage9_classes(ss=1):
    """段階9 の Unity の ID 画像（3840×2160）を ss×(1920×1080) へ（最近傍）落とし、クラスごとの bool を返す。"""
    from PIL import Image
    im = np.array(Image.open(IDS_STAGE9).convert("RGB"))
    H, W = 1080 * ss, 1920 * ss
    f = im.shape[0] // H
    im = im[f // 2::f, f // 2::f][:H, :W]
    return {k: np.all(im == np.array(v, np.uint8)[None, None, :], -1) for k, v in ID_COL.items()}


def sha256(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
