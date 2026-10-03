# -*- coding: utf-8 -*-
"""美術の見本01 B（原画のような舌形）の共通の道具（numpy。Unity の描画ではない）。
- K*′ P28R2rec の .gwb（t* の位置＝ワールド m）を読む
- 描画の記録（PL36Render の report の images の camPos・camForward・camUp・fov）と同じカメラ
- z バッファの描画で、画素ごとの三角形と重心座標（遠近補正つき）を出す
原画の色は面へ写さない（原画の色区は、見本の設計の目的関数の比べる相手としてだけ使う。投影はしない）。"""
import hashlib
import struct

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
GWB = REPO + "/Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb"
META = REPO + "/Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_meta.json"
ATTR29 = REPO + "/Unity/Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin"
LABELS = REPO + "/Tools/PaintingTruth/colour/masks/mw_colour_labels.png"
W, H = 1920, 1080

# PL36Render（Unity/Build/Polish/36/r_after/pl33_render_report.json）の t* の視点（Unity の左手系。right = up × forward）
CAMS = {
    "painting": dict(pos=(0.0, 3.0, -62.0), fwd=(-0.03765837475657463, 0.10092444717884064, 0.9941810965538025),
                     up=(0.003820155980065465, 0.9948940873146057, -0.1008521169424057), fov=26.0),
    "seat": dict(pos=(3.954400062561035, 1.8322999477386475, -15.030799865722656), fwd=(-0.29017001390457153, 0.8942115306854248, 0.3408622443675995),
                 up=(0.5796414613723755, 0.4476446211338043, -0.6809039115905762), fov=80.0),
    "seat_toward_wave": dict(pos=(3.954400062561035, 1.8322999477386475, -15.030799865722656), fwd=(-0.7333651781082153, 0.0, 0.6798349618911743),
                             up=(0.0, 1.0, 0.0), fov=70.0),
    "side_left": dict(pos=(-90.0, 30.0, -14.0), fwd=(0.9605900049209595, -0.2486233115196228, 0.12431160360574722),
                      up=(0.24656720459461212, 0.9686002731323242, 0.03190871328115463), fov=45.0),
    "side_right": dict(pos=(-2.2348499298095703, 30.0, 80.67579650878906), fwd=(-0.051287658512592316, -0.24862337112426758, -0.967241644859314),
                       up=(-0.013164675794541836, 0.9686002135276794, -0.24827459454536438), fov=45.0),
    "back65": dict(pos=(-41.18864440917969, 18.0, 80.63341522216797), fwd=(0.3750360608100891, -0.11043152213096619, -0.9204091429710388),
                   up=(0.041670672595500946, 0.9938837289810181, -0.10226766765117645), fov=26.0),
    "top": dict(pos=(-7.227685928344727, 150.0, -2.713169813156128), fwd=(5.96e-08, -1.0, -1.04e-07),
                up=(-0.7333652377128601, -1.04e-07, 0.6798349022865295), fov=40.0),
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_gwb(p=GWB):
    b = open(p, "rb").read()
    assert b[:4] == b"GWW0"
    ver, nu, nv, nf = struct.unpack("<4i", b[4:20])
    tsf, ntri = struct.unpack("<2i", b[24:32])
    n = nu * nv
    o = 32
    uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2); o += n * 8
    uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2); o += n * 8
    tri = np.frombuffer(b, np.int32, ntri * 3, o).reshape(ntri, 3); o += ntri * 12
    pos = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3)
    return dict(nu=nu, nv=nv, uv=uv.astype(np.float64), uv2=uv2.astype(np.float64), tri=tri.copy(), pos=pos.astype(np.float64))


def load_attr29(p=ATTR29):
    return np.fromfile(p, np.float32).reshape(-1, 12).astype(np.float64)


class Cam:
    def __init__(self, pos, fwd, up, fov, Wd=W, Hd=H):
        self.pos = np.asarray(pos, np.float64)
        f = np.asarray(fwd, np.float64); f = f / np.linalg.norm(f)
        u = np.asarray(up, np.float64)
        r = np.cross(u, f); r = r / np.linalg.norm(r)
        u = np.cross(f, r)
        self.f, self.r, self.u = f, r, u
        self.t = np.tan(np.radians(fov) / 2)
        self.W, self.H = Wd, Hd
        self.aspect = Wd / Hd

    def project(self, P):
        d = np.asarray(P, np.float64) - self.pos
        cx, cy, cz = d @ self.r, d @ self.u, d @ self.f
        czs = np.where(np.abs(cz) < 1e-9, 1e-9, cz)
        vx = 0.5 + 0.5 * (cx / czs) / (self.t * self.aspect)
        vy = 0.5 + 0.5 * (cy / czs) / self.t
        return np.stack([vx * self.W - 0.5, (1.0 - vy) * self.H - 0.5], -1), cz


def cam(name, Wd=W, Hd=H):
    c = CAMS[name]
    return Cam(c["pos"], c["fwd"], c["up"], c["fov"], Wd, Hd)


class UVGrid:
    """面の座標の平面 (U, V) の格子（テクスチャ）を描く「カメラ」。列 x = (V − V0)/h、行 y = (U − U0)/h、深さはいつも 1。
    raster_bary に P = (U, V, 0) を渡すと、テクセルごとの三角形と重心座標が出る（面の座標の逆の写像）。"""

    def __init__(self, U0, V0, h, Wd, Hd):
        self.U0, self.V0, self.h, self.W, self.H = float(U0), float(V0), float(h), int(Wd), int(Hd)

    def project(self, P):
        P = np.asarray(P, np.float64)
        return np.stack([(P[:, 1] - self.V0) / self.h, (P[:, 0] - self.U0) / self.h], -1), np.ones(len(P))


def raster_bary(cm, pos, tri, near=0.5):
    """z バッファ。戻り値：tid (H,W) int（-1 は無し）、b (H,W,3) 遠近補正の重心座標、z (H,W) 深さ。三角形が全部カメラの前のものだけ描く。"""
    Wd, Hd = cm.W, cm.H
    xy, z = cm.project(pos)
    T = tri
    ok = (z[T] > near).all(1)
    T = T[ok]
    tids = np.nonzero(ok)[0]
    X = xy[T]
    Z = z[T]
    x0 = np.floor(X[..., 0].min(1)).astype(np.int64); x1 = np.ceil(X[..., 0].max(1)).astype(np.int64)
    y0 = np.floor(X[..., 1].min(1)).astype(np.int64); y1 = np.ceil(X[..., 1].max(1)).astype(np.int64)
    vis = (x1 >= 0) & (x0 < Wd) & (y1 >= 0) & (y0 < Hd)
    X, Z, tids, x0, x1, y0, y1 = X[vis], Z[vis], tids[vis], x0[vis], x1[vis], y0[vis], y1[vis]
    x0 = np.clip(x0, 0, Wd - 1); x1 = np.clip(x1, 0, Wd - 1); y0 = np.clip(y0, 0, Hd - 1); y1 = np.clip(y1, 0, Hd - 1)
    size = np.maximum(x1 - x0 + 1, y1 - y0 + 1)
    zb = np.full(Hd * Wd, np.inf)
    tb = np.full(Hd * Wd, -1, np.int64)
    ax, ay = X[:, 0, 0], X[:, 0, 1]; bx, by = X[:, 1, 0], X[:, 1, 1]; cx, cy = X[:, 2, 0], X[:, 2, 1]
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    iz = 1.0 / Z
    done = np.zeros(len(size), bool)
    for K in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048):
        sel = np.nonzero((~done) & (size <= K))[0]
        done[sel] = True
        if not len(sel):
            continue
        oy, ox = np.meshgrid(np.arange(K), np.arange(K), indexing="ij")
        oy = oy.ravel(); ox = ox.ravel()
        step = max(1, 80_000 // (K * K))
        for s0 in range(0, len(sel), step):
            ss = sel[s0:s0 + step]
            px = x0[ss][:, None] + ox[None, :]; py = y0[ss][:, None] + oy[None, :]
            inb = (px <= x1[ss][:, None]) & (py <= y1[ss][:, None])
            dd0 = den[ss][:, None]; okd = np.abs(dd0) > 1e-12; dd = np.where(okd, dd0, 1.0)
            l1 = ((by[ss][:, None] - cy[ss][:, None]) * (px - cx[ss][:, None]) + (cx[ss][:, None] - bx[ss][:, None]) * (py - cy[ss][:, None])) / dd
            l2 = ((cy[ss][:, None] - ay[ss][:, None]) * (px - cx[ss][:, None]) + (ax[ss][:, None] - cx[ss][:, None]) * (py - cy[ss][:, None])) / dd
            l3 = 1 - l1 - l2
            ins = inb & okd & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
            if not ins.any():
                continue
            izz = l1 * iz[ss][:, 0:1] + l2 * iz[ss][:, 1:2] + l3 * iz[ss][:, 2:3]
            zz = 1.0 / izz
            ti = np.broadcast_to(np.arange(len(ss))[:, None], ins.shape)[ins]
            pix = (py * Wd + px)[ins]; zv = zz[ins]; tv = ss[ti]
            o = np.lexsort((zv, pix))
            pix, zv, tv = pix[o], zv[o], tv[o]
            first = np.ones(len(pix), bool); first[1:] = pix[1:] != pix[:-1]
            pix, zv, tv = pix[first], zv[first], tv[first]
            upd = zv < zb[pix]
            zb[pix[upd]] = zv[upd]; tb[pix[upd]] = tv[upd]
    has = tb >= 0
    k = tb[has]
    pidx = np.nonzero(has)[0]
    px = (pidx % Wd).astype(np.float64); py = (pidx // Wd).astype(np.float64)
    l1 = ((by[k] - cy[k]) * (px - cx[k]) + (cx[k] - bx[k]) * (py - cy[k])) / den[k]
    l2 = ((cy[k] - ay[k]) * (px - cx[k]) + (ax[k] - cx[k]) * (py - cy[k])) / den[k]
    l3 = 1 - l1 - l2
    w = np.stack([l1 * iz[k, 0], l2 * iz[k, 1], l3 * iz[k, 2]], -1)
    w /= w.sum(1, keepdims=True)
    bary = np.zeros((Hd * Wd, 3)); bary[pidx] = w
    tid = np.full(Hd * Wd, -1, np.int64); tid[pidx] = tids[k]
    zb[~has] = np.nan
    return tid.reshape(Hd, Wd), bary.reshape(Hd, Wd, 3), zb.reshape(Hd, Wd)


def interp(tid, bary, tri, vals):
    """頂点ごとの値 vals (N,...) を画素へ（重心座標）。無い画素は NaN。"""
    Hd, Wd = tid.shape
    v = np.asarray(vals, np.float64)
    sh = v.shape[1:]
    out = np.full((Hd, Wd) + sh, np.nan)
    m = tid >= 0
    T = tri[tid[m]]
    b = bary[m]
    if len(sh) == 0:
        out[m] = (v[T] * b).sum(1)
    else:
        out[m] = (v[T] * b[..., None]).sum(1)
    return out
