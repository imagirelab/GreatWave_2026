# -*- coding: utf-8 -*-
"""美術の見本05 の材質 AS05（Q33、要求書 T5・T6）の共通部。py -3.10（numpy・scipy・OpenCV・Pillow）。

- 静止のメッシュ（書式 GreatWave.AS03.static_mesh/1、属性の約束は Unity/Build/Polish/sample04/mat/README.md と
  Unity/Build/Polish/sample05/mat/README.md）の読み書き。主役波の頂点は先頭の N 個（union なら 314,400、主役波だけのメッシュなら全部）。
- 視点の numpy の z バッファ（Unity の描画ではない）：主役波・ほかのメッシュ（wave4）・近い海・爪を 1 つの場面にして、
  画素ごとに三角形の番号・深さ・印を出す。主役波の輪郭のうち「空」（何も描かれない画素）に接する画素を「縁の画素」とする。
- 原画の色は面へ写さない（Q28・G1）。原画のカメラは、どの頂点（行・列・u）が縁を作るかを探すのと、測りにだけ使う。
"""
import hashlib
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as04", "Tools/GWWaveGen/as05", "Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
os.environ.setdefault("AS04_FIX", "fix1")
import asm4_common as A  # noqa: E402
import w4_common as W4  # noqa: E402

K = A.K
P = REPO + "/Unity/Build/Polish"
P4 = P + "/sample04"
P5 = P + "/sample05"
MAT = P5 + "/mat"
# 見本04 の最後（fix1）の入力
UNION04F = P4 + "/wave4/mesh_fix1/union.json"           # 主役波 AS04F（頂点 0〜314,399）＋ wave4
HERO04F = P4 + "/fix1/shape/mesh/hero_smooth_as04f.json"
CLAWS04F = P4 + "/fix1/shape/claws/ds33_claw_layout.json"
RENDER04F = P4 + "/assemble/render/FX1"
N_HERO04F = 314400
NCOL = 400
# 利用者の切り出し（Q33）：見本04 の原画視点の描画（表示の画素 1920×1080）で x 736〜891、y 300〜721
T6_CROP = (736, 300, 891, 721)
VIEWS7 = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    p = os.path.abspath(p).replace("\\", "/")
    r = REPO.replace("\\", "/") + "/"
    return p[len(r):] if p.startswith(r) else p


def rnd(v, k=3):
    if v is None:
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    return round(float(v), k)


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=float)


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def read_static(p):
    ch, tri, j = W4.read_static(p)
    return ch, tri.astype(np.int64), j


def write_static(p, ch, tri, extra=None):
    return W4.write_static(p, ch, tri, extra)


class Hero:
    """静止のメッシュの主役波の部分。サブ行（uv6.x の値ごと）× 列（uv6.y）の格子として読む。"""

    def __init__(self, ch, tri, n_hero):
        self.n = int(n_hero)
        self.pos = ch["position"][:self.n].astype(np.float64)
        self.u = ch["uv3"][:self.n, 2].astype(np.float64)
        self.F = ch["uv3"][:self.n, 0].astype(np.float64)
        self.hrow = ch["uv4"][:self.n, 1].astype(np.float64)
        self.wsd = ch["uv5"][:self.n, 2].astype(np.float64)
        self.row = ch["uv6"][:self.n, 0].astype(np.float64)
        self.col = ch["uv6"][:self.n, 1].astype(np.float64)
        rv, self.sr = np.unique(np.round(self.row, 4), return_inverse=True)
        self.row_values = rv                 # サブ行の行の値（0〜239 の小数）
        self.nsr = len(rv)
        Q = K.sec(self.pos)
        self.c = Q[:, 2]
        self.y = Q[:, 1]
        self.c_sr = np.bincount(self.sr, self.c, self.nsr) / np.maximum(np.bincount(self.sr, None, self.nsr), 1)
        # 断面に沿う弧長 t（m）：サブ行ごとに列の順に頂点をたどった距離の累積。u は唇を短くした鼻（列 200〜265 ほど）でほとんど
        # 変わらない（見本04 の AS04F）ので、縁の位置と白の境の距離は t で測る。
        self.t = np.zeros(self.n)
        order = np.lexsort((self.col, self.sr))
        ps = self.pos[order]
        seg = np.linalg.norm(np.diff(ps, axis=0), axis=1)
        same = np.diff(self.sr[order]) == 0
        seg = np.where(same, seg, 0.0)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        start = np.concatenate([[True], ~same])
        base = np.maximum.accumulate(np.where(start, cum, 0.0))
        self.t[order] = cum - base
        self.tri_h = tri[(tri < self.n).all(1)]
        self.tri_o = tri[(tri >= self.n).all(1)]
        nrm = np.cross(self.pos[self.tri_h[:, 1]] - self.pos[self.tri_h[:, 0]], self.pos[self.tri_h[:, 2]] - self.pos[self.tri_h[:, 0]])
        ta = 0.5 * np.linalg.norm(nrm, axis=1)
        self.varea = np.bincount(self.tri_h.ravel(), np.repeat(ta / 3.0, 3), self.n)   # 頂点の受け持つ面積（m²）


# 波頭の回り台（描画の道具 AS03AsmRender の crest の段、mat_render.sh の引数と同じ）：中心・距離・仰角・画角。方位 0 = 中心から原画のカメラへ向く水平の向き、反時計回り
CREST = {"center": (-6.63, 16.5, -3.27), "dist": 34.0, "el": 5.0, "fov": 35.0}


def crest_cam(az_deg, W=1920, H=1080):
    ctr = np.array(CREST["center"], np.float64)
    pc = np.array(A.CC.VIEWS["painting"][0], np.float64) - ctr
    az = np.arctan2(pc[2], pc[0]) + np.radians(az_deg)
    el = np.radians(CREST["el"])
    d = CREST["dist"]
    eye = ctr + np.array([d * np.cos(el) * np.cos(az), d * np.sin(el), d * np.cos(el) * np.sin(az)])
    return A.CC.Cam(eye, ctr - eye, (0, 1, 0), CREST["fov"], W, H)


def cam(view, W=1920, H=1080):
    """視点の名前：painting・seat などの 7 視点、tt<方位>（回り台）、crest<方位>（波頭の回り台）。"""
    if view == "painting":
        return A.painting_cam()
    if view.startswith("crest"):
        return crest_cam(float(view[5:]), W, H)
    return A.view_cam(view, W, H)


def scene(ch, tri, n_hero, claws=CLAWS04F, with_sea=True):
    """(tris (N,3,3), lab (N,), src_tri)：lab 1 主役波・5 ほかのメッシュ（wave4）・6 近い海・7 爪。src_tri は主役波の三角形の頂点の番号（主役波だけ）。"""
    pos = ch["position"].astype(np.float64)
    th = tri[(tri < n_hero).all(1)]
    to = tri[~(tri < n_hero).all(1)]
    parts, labs = [pos[th]], [np.full(len(th), 1, np.int16)]
    if len(to):
        parts.append(pos[to]); labs.append(np.full(len(to), 5, np.int16))
    if with_sea:
        st = A.sea_tris()
        parts.append(st); labs.append(np.full(len(st), 6, np.int16))
    if claws:
        cl, _ = A.claws_tris(claws)
        for c in cl:
            parts.append(c["verts"][c["tris"]]); labs.append(np.full(len(c["tris"]), 7, np.int16))
    return np.concatenate(parts), np.concatenate(labs), th


def raster(view, tris, lab, W=1920, H=1080):
    cm = cam(view, W, H)
    idb, D, L = A.raster(cm, tris, lab)
    return cm, idb, D, L


def sky_contour(D, L, hero_label=1):
    """主役波の画素のうち、4 近傍に空（何も描かれない画素）がある画素。"""
    sky = ~np.isfinite(D)
    nb = np.zeros_like(sky)
    nb[1:] |= sky[:-1]; nb[:-1] |= sky[1:]; nb[:, 1:] |= sky[:, :-1]; nb[:, :-1] |= sky[:, 1:]
    return (L == hero_label) & nb, sky


def poly_mask(poly, W=1920, H=1080):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(np.asarray(poly, np.float64) * 8).astype(np.int32)], 1, shift=3)
    return m.astype(bool)


def rect_poly(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# ---------------------------------------------------------------- 色の区分（s5_common.color_classes と同じ規則）
def color_classes(rgb):
    """(H, W, 3) uint8 → 区分 0..4。1 藍：明るさ < 120。2 水色：明るさ ≥ 140 で g − r > 6。3 白・紙：明るさ ≥ 170 で g − r ≤ 6、r − b ≤ 50。
    4 船の生成り：明るさ ≥ 140 で r − b > 50。0 その他（線・移り目）。"""
    x = rgb.astype(np.int32)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    Lm = (r * 299 + g * 587 + b * 114) // 1000
    cls = np.zeros(r.shape, np.uint8)
    cls[Lm < 120] = 1
    pale = Lm >= 140
    cls[pale & ((g - r) > 6)] = 2
    cls[(Lm >= 170) & ((g - r) <= 6) & ((r - b) <= 50)] = 3
    cls[pale & ((r - b) > 50)] = 4
    return cls
