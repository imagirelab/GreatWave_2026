# -*- coding: utf-8 -*-
"""設計33（爪の部）の共通の道具（numpy。Unity の描画ではない）。

- 置き場所と入力のパス、SHA-256、JSON の書き出し
- シート（主役波の網、行 R × 列 C）の評価：描画と同じ三角形の分け方での補間（tri_eval）、双線形の偏微分、最も近い点への射影（project_to_sheet）
- 任意の大きさの画像のカメラ（CamWH）と、原画視点の一部を拡大するカメラ（CropCam）
- z バッファの描画（raster。ds30_checks.raster_ids を幅・高さを引数にして写したもの）
- 中心を通る Catmull-Rom（centripetal）の曲線
"""
import hashlib
import json
import math
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/ds30", "Tools/GWWaveGen/ds31", "Tools/GWWaveGen/ds32", "Tools/PaintingTruth",
           "Tools/GWWaveGen", "Tools/GWWaveGen/kstar3", "Tools/GWWaveGen/kstar_h"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import ds30_checks as K  # noqa: E402
import ds31_white as W31  # noqa: E402

C27 = K.C27
OUT = REPO + "/Unity/Build/Design/33/claws"
D32 = REPO + "/Unity/Build/Design/32/list+ids"
HERO = REPO + "/Unity/Build/Design/31/white/hero_pkg"
SEA = REPO + "/Unity/Build/Design/30/sea"
WARP = REPO + "/Unity/Build/Design/28R01F/F_final/timewarp_F_final.json"
TRUTH = REPO + "/Tools/PaintingTruth/painting_truth.json"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
INV29 = REPO + "/Tools/PaintingTruth/claws29/claw_inventory.json"
CLAW_README = "G:/Unity/Ukeyoe_Claw/Docs/Research/Claw_Analysis/README.md"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FPS, NFR = 30, 421
BODY = (18, 394)
A_DISP = 0.416345               # 表示の画素 / 原画（DP130155）の画素
# 調色板（Tools/PaintingTruth/targets/palette.json の sRGB）。描画は BGR で使う
PAL_RGB = dict(white=(251, 246, 227), mizuiro=(192, 211, 199), ai_mid=(41, 105, 148), ai_dark=(34, 63, 96),
               sky=(249, 232, 196), line=(24, 38, 70))


def bgr(name):
    r, g, b = PAL_RGB[name]
    return (b, g, r)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _np(o):
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


def jdump(p, o):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=_np)
        f.write("\n")


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rnd(v, k=4):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    if v is None:
        return None
    v = float(v)
    return None if not math.isfinite(v) else round(v, k)


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def to_disp(q):
    q = np.asarray(q, np.float64)
    return np.stack([A_DISP * (q[..., 0] + 0.5) - 0.5 + 156.66153, A_DISP * (q[..., 1] + 0.5) - 0.5], -1)


# ---------------------------------------------------------------- シートの評価
def _cell(X, r, c):
    R, C = X.shape[:2]
    r = np.asarray(r, np.float64)
    c = np.asarray(c, np.float64)
    r0 = np.clip(np.floor(r).astype(int), 0, R - 2)
    c0 = np.clip(np.floor(c).astype(int), 0, C - 2)
    return r0, c0, r - r0, c - c0


def tri_eval(X, r, c):
    """描画の三角形（grid_tris：(a,b,cc) と (cc,b,d)）の上の点。a=(r,c) b=(r+1,c) cc=(r,c+1) d=(r+1,c+1)。"""
    r0, c0, fr, fc = _cell(X, r, c)
    A = X[r0, c0]; B = X[r0 + 1, c0]; Cc = X[r0, c0 + 1]; D = X[r0 + 1, c0 + 1]
    lo = (fr + fc) <= 1.0
    p_lo = A + fr[..., None] * (B - A) + fc[..., None] * (Cc - A)
    u = 1.0 - fc
    v = fr + fc - 1.0
    p_hi = Cc + u[..., None] * (B - Cc) + v[..., None] * (D - Cc)
    return np.where(lo[..., None], p_lo, p_hi)


def bilin(X, r, c):
    r0, c0, fr, fc = _cell(X, r, c)
    fr = fr[..., None]; fc = fc[..., None]
    return (X[r0, c0] * (1 - fr) * (1 - fc) + X[r0 + 1, c0] * fr * (1 - fc) + X[r0, c0 + 1] * (1 - fr) * fc + X[r0 + 1, c0 + 1] * fr * fc)


def bilin_d(X, r, c):
    """双線形の ∂P/∂r、∂P/∂c。"""
    r0, c0, fr, fc = _cell(X, r, c)
    fr = fr[..., None]; fc = fc[..., None]
    A = X[r0, c0]; B = X[r0 + 1, c0]; Cc = X[r0, c0 + 1]; D = X[r0 + 1, c0 + 1]
    dr = (1 - fc) * (B - A) + fc * (D - Cc)
    dc = (1 - fr) * (Cc - A) + fr * (D - B)
    return dr, dc


def normal_at(X, r, c):
    dr, dc = bilin_d(X, r, c)
    n = np.cross(dr, dc)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)


def frame_at(X, r, c):
    """(r, c) の局所の座標系（設計32 と同じ）：行 e1 = ∂P/∂c、n = (∂P/∂r)×(∂P/∂c)（空気の側）、e2 = n × e1。戻り値 …×3×3（行が基底）。"""
    h = 0.5
    R, C = X.shape[:2]
    r = np.asarray(r, np.float64); c = np.asarray(c, np.float64)
    rp, rm = np.clip(r + h, 0, R - 1), np.clip(r - h, 0, R - 1)
    cp, cm = np.clip(c + h, 0, C - 1), np.clip(c - h, 0, C - 1)
    dr = (bilin(X, rp, c) - bilin(X, rm, c)) / np.maximum(rp - rm, 1e-9)[..., None]
    dc = (bilin(X, r, cp) - bilin(X, r, cm)) / np.maximum(cp - cm, 1e-9)[..., None]
    e1 = dc / np.maximum(np.linalg.norm(dc, axis=-1, keepdims=True), 1e-12)
    n = np.cross(dr, dc)
    n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    e2 = np.cross(n, e1)
    return np.stack([e1, e2, n], -2)


def project_to_sheet(X, q, rc0, iters=12, max_step=3.0, c_lo=0, c_hi=None):
    """点 q（n×3）に最も近いシート（双線形）の点 (r, c) を、rc0 から Gauss-Newton で探す。戻り値 r, c, h（法線の向きの高さ）, 接線の残り。"""
    R, C = X.shape[:2]
    c_hi = C - 1 if c_hi is None else c_hi
    q = np.asarray(q, np.float64)
    r = np.array(rc0[:, 0], np.float64)
    c = np.array(rc0[:, 1], np.float64)
    for _ in range(iters):
        P = bilin(X, r, c)
        dr, dc = bilin_d(X, r, c)
        e = q - P
        a11 = (dr * dr).sum(-1); a12 = (dr * dc).sum(-1); a22 = (dc * dc).sum(-1)
        b1 = (dr * e).sum(-1); b2 = (dc * e).sum(-1)
        det = np.maximum(a11 * a22 - a12 * a12, 1e-18)
        d_r = np.clip((a22 * b1 - a12 * b2) / det, -max_step, max_step)
        d_c = np.clip((a11 * b2 - a12 * b1) / det, -max_step, max_step)
        r = np.clip(r + d_r, 0, R - 1)
        c = np.clip(c + d_c, c_lo, c_hi)
    P = bilin(X, r, c)
    n = normal_at(X, r, c)
    e = q - P
    h = (e * n).sum(-1)
    tang = np.linalg.norm(e - h[..., None] * n, axis=-1)
    return r, c, h, tang


# ---------------------------------------------------------------- カメラ
class CamWH(C27.Cam):
    """PaintingCam v1 と同じ式で、画像の大きさ W × H を選べるカメラ。"""

    def __init__(self, spec, W, H, position=None, target=None, vfov=None):
        super().__init__(spec, position, target, vfov)
        self.W, self.H = int(W), int(H)
        self.aspect = self.W / self.H
        self.focal_px = (self.H / 2.0) / self.t

    def project(self, P):
        d = np.asarray(P, np.float64) - self.pos
        cx, cy, cz = d @ self.r, d @ self.u, d @ self.f
        vx = 0.5 + 0.5 * (cx / cz) / (self.t * self.aspect)
        vy = 0.5 + 0.5 * (cy / cz) / self.t
        return np.stack([vx * self.W - 0.5, (1.0 - vy) * self.H - 0.5], -1), cz

    def ray(self, x, y):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        vx = (x + 0.5) / self.W
        vy = 1.0 - (y + 0.5) / self.H
        d = self.f + ((2 * vx - 1) * self.t * self.aspect)[..., None] * self.r + ((2 * vy - 1) * self.t)[..., None] * self.u
        return d / np.linalg.norm(d, axis=-1, keepdims=True)


class CropCam:
    """原画視点（1920×1080 の表示の画素）の矩形 [x0, x0 + W/s) × [y0, y0 + H/s) を s 倍で W × H に描くカメラ（同じ視点・同じ射影）。"""

    def __init__(self, base, x0, y0, s, W, H):
        self.base, self.x0, self.y0, self.s = base, float(x0), float(y0), float(s)
        self.W, self.H = int(W), int(H)
        self.pos, self.f = base.pos, base.f

    def project(self, P):
        q, z = self.base.project(P)
        return (q - [self.x0, self.y0]) * self.s + (self.s - 1) * 0.5, z

    def ray(self, x, y):
        x = (np.asarray(x, np.float64) - (self.s - 1) * 0.5) / self.s + self.x0
        y = (np.asarray(y, np.float64) - (self.s - 1) * 0.5) / self.s + self.y0
        return self.base.ray(x, y)


def look_cam(spec, pos, target, vfov, W, H):
    return CamWH(spec, W, H, position=np.asarray(pos, np.float64), target=np.asarray(target, np.float64), vfov=vfov)


# ---------------------------------------------------------------- z バッファ
def raster(cam, tris, ids, near_clip=0.1):
    """ds30_checks.raster_ids と同じ手順（近い面で切る → 大きさごとに画素を塗る）。W・H はカメラから取る。
    tris：(N,3,3)、ids：(N,) int（0 は使わない）。戻り値 (H,W) の id と 1/z。"""
    W, H = cam.W, cam.H
    d = (tris - cam.pos[None, None, :]) @ cam.f - near_clip
    nin = (d > 0).sum(1)
    keep = [tris[nin == 3]]; kid = [ids[nin == 3]]
    for m_in in (1, 2):
        sel = np.nonzero(nin == m_in)[0]
        for k in sel:
            P3, D = tris[k], d[k]
            poly = []
            for a in range(3):
                b = (a + 1) % 3
                if D[a] > 0:
                    poly.append(P3[a])
                if (D[a] > 0) != (D[b] > 0):
                    tt = D[a] / (D[a] - D[b])
                    poly.append(P3[a] + tt * (P3[b] - P3[a]))
            for q in range(1, len(poly) - 1):
                keep.append(np.array([[poly[0], poly[q], poly[q + 1]]])); kid.append(ids[k:k + 1])
    tris = np.concatenate(keep); ids = np.concatenate(kid)
    P = tris.reshape(-1, 3)
    xy, z = cam.project(P)
    xy = xy.reshape(-1, 3, 2); z = z.reshape(-1, 3)
    ok = np.all(z > near_clip * 0.5, axis=1) & np.all(np.isfinite(xy), axis=(1, 2))
    xy, z, ids = xy[ok], z[ok], ids[ok]
    iz = 1.0 / z
    x0 = np.floor(xy[..., 0].min(1)).astype(np.int64); x1 = np.ceil(xy[..., 0].max(1)).astype(np.int64)
    y0 = np.floor(xy[..., 1].min(1)).astype(np.int64); y1 = np.ceil(xy[..., 1].max(1)).astype(np.int64)
    vis = (x1 >= 0) & (x0 < W) & (y1 >= 0) & (y0 < H)
    xy, iz, ids, x0, x1, y0, y1 = xy[vis], iz[vis], ids[vis], x0[vis], x1[vis], y0[vis], y1[vis]
    x0 = np.clip(x0, 0, W - 1); x1 = np.clip(x1, 0, W - 1); y0 = np.clip(y0, 0, H - 1); y1 = np.clip(y1, 0, H - 1)
    size = np.maximum(x1 - x0 + 1, y1 - y0 + 1)
    zb = np.zeros(H * W); idb = np.zeros(H * W, np.int32)
    ax, ay = xy[:, 0, 0], xy[:, 0, 1]; bx, by = xy[:, 1, 0], xy[:, 1, 1]; cx, cy = xy[:, 2, 0], xy[:, 2, 1]
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)

    def splat(sel, Kk):
        if not len(sel):
            return
        oy, ox = np.meshgrid(np.arange(Kk), np.arange(Kk), indexing="ij")
        oy = oy.ravel(); ox = ox.ravel()
        step = max(1, 800_000 // (Kk * Kk))
        for s0 in range(0, len(sel), step):
            ss = sel[s0:s0 + step]
            px = x0[ss][:, None] + ox[None, :]; py = y0[ss][:, None] + oy[None, :]
            inb = (px <= x1[ss][:, None]) & (py <= y1[ss][:, None])
            dd0 = den[ss][:, None]
            okd = np.abs(dd0) > 1e-12
            dd = np.where(okd, dd0, 1.0)
            l1 = ((by[ss][:, None] - cy[ss][:, None]) * (px - cx[ss][:, None]) + (cx[ss][:, None] - bx[ss][:, None]) * (py - cy[ss][:, None])) / dd
            l2 = ((cy[ss][:, None] - ay[ss][:, None]) * (px - cx[ss][:, None]) + (ax[ss][:, None] - cx[ss][:, None]) * (py - cy[ss][:, None])) / dd
            l3 = 1 - l1 - l2
            ins = inb & okd & (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
            if not ins.any():
                continue
            zz = l1 * iz[ss][:, 0:1] + l2 * iz[ss][:, 1:2] + l3 * iz[ss][:, 2:3]
            ti = np.broadcast_to(np.arange(len(ss))[:, None], ins.shape)[ins]
            pix = (py * W + px)[ins]; zv = zz[ins]; iv = ids[ss][ti]
            o = np.lexsort((-zv, pix))
            pix, zv, iv = pix[o], zv[o], iv[o]
            first = np.ones(len(pix), bool); first[1:] = pix[1:] != pix[:-1]
            pix, zv, iv = pix[first], zv[first], iv[first]
            upd = zv > zb[pix]
            zb[pix[upd]] = zv[upd]; idb[pix[upd]] = iv[upd]
    done = np.zeros(len(size), bool)
    for Kk in (1, 2, 4, 8, 16, 32, 64):
        sel = np.nonzero((~done) & (size <= Kk))[0]
        splat(sel, Kk)
        done[sel] = True
    for t in np.nonzero(~done)[0]:
        Xg, Yg = np.meshgrid(np.arange(x0[t], x1[t] + 1), np.arange(y0[t], y1[t] + 1))
        dd = den[t]
        if abs(dd) < 1e-12:
            continue
        l1 = ((by[t] - cy[t]) * (Xg - cx[t]) + (cx[t] - bx[t]) * (Yg - cy[t])) / dd
        l2 = ((cy[t] - ay[t]) * (Xg - cx[t]) + (ax[t] - cx[t]) * (Yg - cy[t])) / dd
        l3 = 1 - l1 - l2
        ins = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        zz = l1 * iz[t, 0] + l2 * iz[t, 1] + l3 * iz[t, 2]
        pix = (Yg * W + Xg)[ins]; zv = zz[ins]
        upd = zv > zb[pix]
        zb[pix[upd]] = zv[upd]; idb[pix[upd]] = ids[t]
    return idb.reshape(H, W), zb.reshape(H, W)


def ray_tri_many(o, d, A, B, Cc):
    """射線 o + s·d（d：n×3）と三角形（n×3 ずつ）の交点の s, u, v（交点 = A + u(B−A) + v(C−A)）。"""
    e1, e2 = B - A, Cc - A
    p = np.cross(d, e2)
    det = (e1 * p).sum(-1)
    det = np.where(np.abs(det) < 1e-14, 1e-14, det)
    inv = 1.0 / det
    tv = o[None, :] - A
    u = (tv * p).sum(-1) * inv
    q = np.cross(tv, e1)
    v = (d * q).sum(-1) * inv
    s = (e2 * q).sum(-1) * inv
    return s, u, v


def tri_to_rc(t, u, v, ncol, c_off):
    """grid_tris の三角形の番号 t と重心座標 (u, v) → シートの (r, c)。"""
    cell, half = np.divmod(t, 2)
    r0, c0 = np.divmod(cell, ncol)
    c0 = c0 + c_off
    rr = np.where(half == 0, r0 + u, r0 + u + v)
    cc = np.where(half == 0, c0 + v, c0 + 1 - u)
    return rr, cc


# ---------------------------------------------------------------- 曲線
def catmull_rom(P, n_per=16, alpha=0.5):
    """点列 P（m×3、m ≥ 2）を通る centripetal Catmull-Rom。戻り値：(n_per·(m−1)+1)×3 と、各点の元の区間の番号＋区間の中の位置。"""
    P = np.asarray(P, np.float64)
    m = len(P)
    if m == 2:
        t = np.linspace(0, 1, n_per + 1)
        return P[0] + t[:, None] * (P[1] - P[0]), t
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = [P[0:1]]
    par = [np.array([0.0])]
    for i in range(1, m):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-9) ** alpha
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-9) ** alpha
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-9) ** alpha
        t = np.linspace(t1, t2, n_per + 1)[1:][:, None]
        A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
        B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
        Cc = (t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2
        out.append(Cc)
        par.append(i - 1 + np.linspace(0, 1, n_per + 1)[1:])
    return np.vstack(out), np.concatenate(par)


def resample_arc(Pd, n):
    """密な折れ線 Pd を弧長で n 点（両端を含む）に取り直す。戻り値：点と、元の点の弧長の割合。"""
    seg = np.linalg.norm(np.diff(Pd, axis=0), axis=1)
    s = np.r_[0.0, np.cumsum(seg)]
    L = max(s[-1], 1e-12)
    t = np.linspace(0, L, n)
    Q = np.stack([np.interp(t, s, Pd[:, j]) for j in range(Pd.shape[1])], -1)
    return Q, s / L, L
