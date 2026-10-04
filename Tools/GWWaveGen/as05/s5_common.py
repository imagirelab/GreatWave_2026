# -*- coding: utf-8 -*-
"""美術の見本05 の調べ（Q33）の共通部：三つの層 ①②③ を形で分けるための読みと測り。py -3.10（numpy・scipy・OpenCV）。

- 地にする形：見本04 の最後（主役波 K*′ AS04F の t* の行 240 × 列 400 ＋ 左端の別の青い波 wave4（fix1））。
- 断面の座標（kh_common）：a = 進行方向 T（+ が前・原画のカメラの側）、y = 高さ、c = 波峰線 E（+ が原画視点の右・奥）。
  原画のカメラは断面の座標で a ≈ +45.6 m、y = 3 m、c ≈ −38.6 m にあり、射線は −a・+c の向きへ進む（手前 = a が大きく c が小さい）。
- 層の測り：上から見た高さの場 h(a, c)（面の点の高さの最大を 0.25 m の格子へ）で、峰（局所の最大）と、峰から自分より高い所へ行く道の
  いちばん低い所（鞍）を、最も高い鞍を通る道（ボトルネックの最短路）で求める。峰の突出 = 峰の高さ − 鞍の高さ。
  峰が原画のカメラで利用者の区域の多角形（原画の画素。±40 画素まで広げる）に入れば、その区域の層の峰と読む。
- 原画の色は面へ写さない（Q28）。原画のカメラは測りにだけ使う。参照モデルの OBJ は s5_obj.py だけが一時キャッシュで読む（生成器は読まない）。
出力はすべて Git 対象外の Unity/Build/Polish/sample05/study/ の下。
"""
import heapq
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as04", "Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import s4_common as S4  # noqa: E402
import w4_common as W4  # noqa: E402

K = S4.K
CC = S4.CC
U = S4.U
P = REPO + "/Unity/Build/Polish"
P4 = P + "/sample04"
OUT = P + "/sample05/study"
TMP = OUT + "/tmp"
ROWS04F = P4 + "/fix1/shape/final/cand/kstarAS04F_a45_rows.npz"
ROWS02C = P + "/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz"
WAVE4_F1 = P4 + "/wave4/mesh_fix1/wave4.json"
UNION_F1 = P4 + "/wave4/mesh_fix1/union.json"
RENDER_F1 = P4 + "/assemble/render/FX1"
PAINT = S4.PAINT
H0 = S4.H0
J_B, J_TOP, J_TIP, J_CORNER, J_FACEBOT = 18, 90, 200, 314, 379
CAM_SEC = K.sec(K.CAM_POS_U[None])[0]          # (a, y, c) of the painting camera
REG = S4.regions_ref()                          # 原画の画素の多角形 r1..r4・bulge
REG_JA = {"r1": "①浪尖（頂と唇）", "r2": "②b区域", "r3": "③最左側の小区域", "r4": "④左端の青い波の縁"}
# 利用者の切り出し（Q33）：見本04 の原画視点の描画（表示の画素）で x 736〜891、y 300〜721
T6_CROP_DISP = (736, 300, 891, 721)

# 上から見た高さの場の格子（断面の座標）
GA0, GA1, GC0, GC1, GRES = -32.0, 24.0, -40.0, 16.0, 0.25


def sha(p):
    return S4.sha(p)


def jdump(p, o):
    S4.jdump(p, o)


def rnd(v, k=3):
    return S4.rnd(v, k)


def load_rows(p=ROWS04F):
    z = np.load(p)
    return z["c"].astype(np.float64), z["A"].astype(np.float64), z["Y"].astype(np.float64)


def rows_points(c, A, Y, up=3, j0=J_B, j1=J_FACEBOT):
    """行の格子を行・列の向きに up 倍へ双一次で細かくした点（a, y, c）。列 j0..j1 だけ（背の根元〜前の面の下）。"""
    A = A[:, j0:j1 + 1]; Y = Y[:, j0:j1 + 1]
    R, C = A.shape
    rr = np.linspace(0, R - 1, (R - 1) * up + 1)
    cc = np.linspace(0, C - 1, (C - 1) * up + 1)
    r0 = np.minimum(np.floor(rr).astype(int), R - 2); fr = (rr - r0)[:, None]
    k0 = np.minimum(np.floor(cc).astype(int), C - 2); fc = (cc - k0)[None, :]

    def bil(M):
        a = M[r0][:, k0]; b = M[r0][:, k0 + 1]; d = M[r0 + 1][:, k0]; e = M[r0 + 1][:, k0 + 1]
        return (a * (1 - fc) + b * fc) * (1 - fr) + (d * (1 - fc) + e * fc) * fr
    cg = np.interp(rr, np.arange(R), c)[:, None] * np.ones((1, len(cc)))
    return np.stack([bil(A).ravel(), bil(Y).ravel(), cg.ravel()], -1)


def mesh_points(ch_pos, tri=None, sub=2):
    """静止のメッシュ（Unity ワールド）の点を断面の座標へ。tri を渡せば三角形の中にも点を足す（sub 段の重心の格子）。"""
    Pw = ch_pos.astype(np.float64)
    pts = [Pw]
    if tri is not None and sub > 0:
        V = Pw[tri]
        for i in range(1, sub + 1):
            for j in range(0, sub + 1 - i):
                k = sub + 1 - i - j
                w = np.array([i, j, k], float) / (sub + 1)
                pts.append((V * w[None, :, None]).sum(1))
    return K.sec(np.concatenate(pts))


def heightfield(Q, res=GRES, box=(GA0, GA1, GC0, GC1), y_floor=0.0):
    """Q (n, 3) = (a, y, c) → h (nc, na)：格子ごとの y の最大。点のない所は y_floor（海）。小さな穴は 3×3 の最大でふさぐ。"""
    a0, a1, c0, c1 = box
    na = int(round((a1 - a0) / res)) + 1; nc = int(round((c1 - c0) / res)) + 1
    ia = np.round((Q[:, 0] - a0) / res).astype(int); ic = np.round((Q[:, 2] - c0) / res).astype(int)
    m = (ia >= 0) & (ia < na) & (ic >= 0) & (ic < nc)
    h = np.full(nc * na, -np.inf)
    np.maximum.at(h, ic[m] * na + ia[m], Q[m, 1])
    h = h.reshape(nc, na)
    empty = ~np.isfinite(h)
    hd = cv2.dilate(np.where(empty, -1e9, h).astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.float64)
    h = np.where(empty & (hd > -1e8), hd, h)
    h = np.where(np.isfinite(h), np.maximum(h, y_floor), y_floor)
    return h, {"a0": a0, "c0": c0, "res": res, "na": na, "nc": nc}


def cell_xyz(g, ic, ia, h):
    return np.array([g["a0"] + ia * g["res"], h[ic, ia], g["c0"] + ic * g["res"]])


def peaks(h, rad_m=1.5, res=GRES, hmin=0.15 * H0):
    """局所の最大（半径 rad_m の円の中で最大）の格子の (ic, ia) の並び（高い順）。"""
    r = max(1, int(round(rad_m / res)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    mx = cv2.dilate(h.astype(np.float32), k).astype(np.float64)
    pk = (h >= mx - 1e-6) & (h > hmin)
    ic, ia = np.nonzero(pk)
    # 平らな頂の重複を除く（同じ高さの隣どうしは 1 つ）
    o = np.argsort(-h[ic, ia])
    out, taken = [], np.zeros_like(pk)
    for t in o:
        i, j = ic[t], ia[t]
        if taken[max(0, i - r):i + r + 1, max(0, j - r):j + r + 1].any():
            continue
        taken[i, j] = True
        out.append((int(i), int(j)))
    return out


def key_saddle(h, src, higher_than=None, target_mask=None):
    """src から、src より高い所（または target_mask）へ行く道のうち、道の最低点がいちばん高い道（ボトルネック路）。
    戻り値：(鞍の高さ, 鞍の格子, 行き着いた格子, 道の格子の並び)。行き着けなければ (None, ...)。"""
    nc, na = h.shape
    hs = h[src] if higher_than is None else higher_than
    if target_mask is None:
        target_mask = h > hs + 1e-6
    best = np.full(h.shape, -np.inf)
    prev = -np.ones(h.shape + (2,), int)
    best[src] = h[src]
    heap = [(-h[src], src[0], src[1])]
    seen = np.zeros(h.shape, bool)
    while heap:
        nb, i, j = heapq.heappop(heap)
        if seen[i, j]:
            continue
        seen[i, j] = True
        if target_mask[i, j] and (i, j) != tuple(src):
            # 道をたどって鞍（道の最低点）を探す
            path = [(i, j)]
            while tuple(prev[path[-1]]) != (-1, -1):
                path.append(tuple(prev[path[-1]]))
            path = path[::-1]
            hv = np.array([h[p] for p in path])
            k = int(np.argmin(hv))
            return float(hv[k]), path[k], (i, j), path
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                ii, jj = i + di, j + dj
                if 0 <= ii < nc and 0 <= jj < na and not seen[ii, jj]:
                    v = min(-nb, h[ii, jj])
                    if v > best[ii, jj]:
                        best[ii, jj] = v
                        prev[ii, jj] = (i, j)
                        heapq.heappush(heap, (-v, ii, jj))
    return None, None, None, []


def painting_cam():
    return S4.CC.painting_cam()


def sec_to_ref_px(Q):
    """断面の座標の点 (n, 3) = (a, y, c) → 原画の画素（3859×2594）と、カメラの前か。"""
    Q = np.atleast_2d(np.asarray(Q, float))
    Pw = K.O[None, :] + Q[:, 0:1] * K.T[None, :] + Q[:, 1:2] * K.UP[None, :] + Q[:, 2:3] * K.E[None, :]
    cam = painting_cam()
    xy, cz = cam.project(Pw)
    return S4.disp_to_ref(xy), cz > 0


def in_poly(pts, poly, grow_px=0.0):
    """原画の画素の点が多角形（原画の画素）に入るか。grow_px だけ外へ広げて判定（距離で）。"""
    poly = np.asarray(poly, np.float32).reshape(-1, 1, 2)
    out = []
    for p in np.atleast_2d(pts):
        d = cv2.pointPolygonTest(poly, (float(p[0]), float(p[1])), True)
        out.append(d >= -grow_px)
    return np.array(out, bool)


def crest_layers(h, g, grow_px=60.0, rad_m=1.5, hmin=0.15 * H0, max_peaks=40):
    """高さの場の峰ごとに、突出（鞍まで）、鞍の場所、原画の区域を求める。"""
    pk = peaks(h, rad_m, g["res"], hmin)[:max_peaks]
    out = []
    gmax = max(h[p] for p in pk) if pk else None
    for p in pk:
        xyz = cell_xyz(g, p[0], p[1], h)
        px, front = sec_to_ref_px(xyz[None])
        regs = [k for k in ("r1", "r2", "r3", "r4") if in_poly(px, REG[k], grow_px)[0]]
        if h[p] >= gmax - 1e-6:
            sad, sc, tgt = None, None, None
            prom = None
        else:
            sad, sc, tgt, path = key_saddle(h, p)
            prom = h[p] - sad if sad is not None else None
        rec = {"cell": p, "a": rnd(xyz[0], 2), "y": rnd(xyz[1], 2), "y_over_H0": rnd(xyz[1] / H0), "c": rnd(xyz[2], 2),
               "painting_px": rnd(px[0], 1), "regions": regs, "prominence_m": rnd(prom, 2) if prom is not None else "global_max"}
        if sc is not None:
            sx = cell_xyz(g, sc[0], sc[1], h)
            tx = cell_xyz(g, tgt[0], tgt[1], h)
            rec.update({"saddle": {"a": rnd(sx[0], 2), "y": rnd(sx[1], 2), "c": rnd(sx[2], 2)},
                        "higher_ground_reached": {"a": rnd(tx[0], 2), "y": rnd(tx[1], 2), "c": rnd(tx[2], 2)},
                        "crest_ahead_of_saddle_a_m": rnd(xyz[0] - sx[0], 2),
                        "crest_to_saddle_plan_m": rnd(np.hypot(xyz[0] - sx[0], xyz[2] - sx[2]), 2)})
        out.append(rec)
    return out


# ---------------------------------------------------------------- 色の区分（原画と描画を同じ規則で）
CLS_JA = {0: "その他（線・移り目）", 1: "藍（濃・中）", 2: "水色", 3: "白・紙", 4: "船の生成り"}


def color_classes(rgb):
    """(H, W, 3) uint8 → 区分 0..4。1 藍：明るさ < 120。2 水色：明るさ ≥ 140 で g − r > 6。3 白・紙：明るさ ≥ 170 で g − r ≤ 6、r − b ≤ 50。
    4 船の生成り：明るさ ≥ 140 で r − b > 50。"""
    x = rgb.astype(np.int32)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    L = (r * 299 + g * 587 + b * 114) // 1000
    cls = np.zeros(r.shape, np.uint8)
    cls[L < 120] = 1
    pale = L >= 140
    cls[pale & ((g - r) > 6)] = 2
    cls[(L >= 170) & ((g - r) <= 6) & ((r - b) <= 50)] = 3
    cls[pale & ((r - b) > 50)] = 4
    return cls


def poly_mask(poly, W, H):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(np.asarray(poly) * 8).astype(np.int32)], 1, shift=3)
    return m.astype(bool)
