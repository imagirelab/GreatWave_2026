# -*- coding: utf-8 -*-
"""設計33：爪の独立の測定器（harness）。爪は作らない。爪の部の出力を、爪の部とは別の式で測る（numpy/OpenCV。Unity の描画ではない）。

測るもの（計画 §2.2 設計33 の最小の受入と §2.0 の回帰。バックログの項目番号）：
  A 原画視点（PaintingCam v1、t* のコマ）の重ね図：設計32 の一覧（領域の多角形・中心線・根元・先端）と、描いた爪（メッシュの投影）。
    爪ごとの位置・向きの対応（根元・先端のずれ px、根元 → 先端の向きの差 °、一覧の中心線から描いた爪までの距離 px、領域の IoU、
    縁の対称 Hausdorff px）。爪ごとの 4 px は記録のみ（101・103・104 の終点の先端と輪郭。精度は仕上げ32・33）。
    「対応が見て取れる」の自動の読み（この測定器の既定。進行役の判断）：描いた爪がない・自分の ID が最も近い一覧の爪でない・
    根元のずれ > 12 px・向きの差 > 45°・中心線までの平均の距離 > 12 px・シートに隠れる（シートが手前の画素が爪の画素の 0.5 超）の
    どれにも当たらない。ほかの爪が手前の画素は隠れに数えない（見える割合 visible_frac は記録）。
  B 輪郭 132・72 の細部込み（爪をシートの上に載せた被覆）：美術優先23 の評価器（evaluate_core、包絡版）で 132 最大・72 p95 を測り、
    設計28修正01 の値（132 最大 5.911 px・72 p95 8.717 px。同じ測り方の爪なしの基準も測り直す）と比べる。回帰の項目（計画 §2.0）として
    78・130・131（≤ 4 px）、132 の大きな輪郭 σ12 最大・72 の大きな輪郭 σ24 p95（≤ 4 px、K*′ の幾何 3.905・3.746）も測る。
  C 根元から水面までの距離 ≤ 1 mm（105）：各コマ（30 Hz、421 コマ）で、見えている爪の根元の点から、そのコマの主役波のシート
    （Unity と同じ三角形の分け方 ds30_checks.grid_tris、精度の層つきの位置）までの最短の距離。双線形の面までの距離も記録する。
  D 根元の滑り 0（137）：根元の最も近いシートの点の (行, 列) が、結び付けの (行, 列) から動かない。滑り＝同じコマの面の上での
    2 点の距離（m）。許容は 1 mm（float32 の丸めの分。値は記録する）。遅れ（前のコマの面に付いている）もこれで見える。
  E 成長の途中の欠落 0（139）：各爪で、最初に見えたコマから t* まで、見えないコマ・NaN・面積 0 のコマが 0。本数（下）と、ds32 の
    結び付けた爪で出てこないもの 0。追加の読み（139b、形の続き）：面積が 1 コマで 10% を超えて減るコマ（爪の一部が消える・つぶれる）0、
    頂点の突出 0。根元から最も遠い頂点までの距離の減り（曲がると減りうる）は記録のみ。
    本数は 150 ± 15（美術優先計画 29 の受入「爪の数 150±15（139 に従う）」）。一覧の結び付けた爪で出てこないものを挙げる。
  F 頂点の数：1 本あたり ≤ 600（最大のコマで数える）。
  記録：頂点の突出（爪の頂点の根元に対する 1 コマの動きが、前後のコマの 4 倍 + 余裕を超えるコマ。余裕は爪の大きさ × 0.2 を 5 mm〜5 cm に
    収めた値。設計32 の突出の規則 4 倍 + 5 cm を爪の大きさに合わせたもの）。
  記録のみ：136（成長の始まり τ と根元の T_white、t* で伸び切るか＝t* の面積 ÷ t* までの最大の面積 ≥ 0.98）、138（根元の近くの向きを根元の局所の座標系で見た角の変化）。

爪の部から呼ぶ形（README_interface.txt に同じ説明）：
  import sys; sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/ds33")
  import ds33_harness as HN
  res = HN.evaluate(provider, out_dir="G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/33/harness/run_xxx")
  provider は次を持つもの（ClawFramesFile はファイルの書式 GreatWave.DS33.claw_frames/1 を読む実装）：
    ids：爪の ID の並び（"C001" など。設計32 の ID）
    n_frames：コマの数（30 Hz、既定 421）
    frame(f) → dict：V (N,3) ワールドの m、T (M,3) 頂点の添字、cid (N,) 頂点の爪の番号（ids の添字。−1 は爪でないもの＝白の帯など）、
      root (K,3) 根元の点（任意。なければ root_vertices の重心、それもなければ一覧の結び付けの点に最も近い頂点）、
      tip (K,3) 先端（任意。なければ根元から最も遠い頂点）、visible (K,) bool（任意。なければ面積 > 0）
    root_rc (K,2)：任意。根元のシートの (行, 列)（なければ設計32 の ds32_ids.json の sheet_rc）
    root_vertices：任意。爪ごとの根元の断面の頂点の添字の並び（あれば、その頂点の面までの距離も記録）

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds33/ds33_harness.py --claws <manifest.json> [--out <dir>] [--unity-ids <af28r01_class_ids.png>]
    py -3.10 -B Tools/GWWaveGen/ds33/ds33_harness.py --selftest [--out <dir>]
"""
import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/PaintingTruth", "Tools/GWWaveGen", "Tools/GWWaveGen/kstar3", "Tools/GWWaveGen/kstar_h", "Tools/GWWaveGen/ds30",
           "Tools/GWWaveGen/ds27", "Tools/GWContext", "Tools/GWWaveGen/ds33"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)

HERO = REPO + "/Unity/Build/Design/31/white/hero_pkg"
WARP = REPO + "/Unity/Build/Design/28R01F/F_final/timewarp_F_final.json"
TRUTH = REPO + "/Tools/PaintingTruth/painting_truth.json"
DS32 = REPO + "/Unity/Build/Design/32/list+ids"
OUT_DEFAULT = REPO + "/Unity/Build/Design/33/harness"
UNITY_BASE_IDS = REPO + "/Unity/Build/Design/31/white/unity/main/t28_white/t28/render/af28r01_class_ids.png"
W, H = 1920, 1080
FPS, NFR = 30, 421
REF_28R01 = {"132_raw_max_px": 5.911, "72_raw_p95_px": 8.717, "78_max_px": 2.741, "130_max_px": 3.831, "131_max_px": 2.924,
             "132_lf_sigma12_max_px": 3.905, "72_lf_sigma24_p95_px": 3.746,
             "source_ja": "Docs/Progress/Design_28_修正01_ja.md §0 の 4・§4.3（K*′ R4、幾何）"}
P = dict(root_dist_max_m=1e-3, slip_max_m=1e-3, length_drop_m=1e-3, area_drop_frac=0.10, spike_factor=4.0, spike_abs_m=0.05, spike_len_frac=0.2, spike_min_m=0.005, vertex_budget=600, count_range=[135, 165],
         corr_root_px=12.0, corr_angle_deg=45.0, corr_centerline_px=12.0, corr_visible_frac=0.5, per_claw_px=4.0,
         window_cells=6, window_cells_wide=24)


# ---------------------------------------------------------------- 小道具
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
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


def jdump(p, o):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=_np)
        f.write("\n")


def rnd(v, k=4):
    if v is None:
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    v = float(v)
    return None if not math.isfinite(v) else round(v, k)


def to_disp(q):
    """DP130155 の画素中心の整数系 → 番号23 の表示フレーム（ds32_ids.to_disp と同じ式）。"""
    q = np.asarray(q, np.float64)
    return np.stack([0.416345 * (q[..., 0] + 0.5) - 0.5 + 156.66153, 0.416345 * (q[..., 1] + 0.5) - 0.5], -1)


def imwrite(p, img):
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("PNG の書き出しに失敗: " + p)
    buf.tofile(p)


# ---------------------------------------------------------------- 面の上の点（三角形・双線形）
def tri_interp(X, r, c):
    """(行 r, 列 c) の連続の座標 → Unity と同じ三角形の分け方（a=(r,c) b=(r+1,c) cc=(r,c+1) ／ cc b d=(r+1,c+1)）の面の上の点。"""
    R, C = X.shape[:2]
    r = np.asarray(r, np.float64); c = np.asarray(c, np.float64)
    r0 = np.clip(np.floor(r).astype(int), 0, R - 2); c0 = np.clip(np.floor(c).astype(int), 0, C - 2)
    fr = (r - r0)[..., None]; fc = (c - c0)[..., None]
    a = X[r0, c0]; b = X[r0 + 1, c0]; cc = X[r0, c0 + 1]; d = X[r0 + 1, c0 + 1]
    lo = (fr + fc) <= 1.0
    p0 = a + fr * (b - a) + fc * (cc - a)
    p1 = d + (1 - fr) * (cc - d) + (1 - fc) * (b - d)
    return np.where(lo, p0, p1)


def bilin(X, r, c):
    R, C = X.shape[:2]
    r = np.asarray(r, np.float64); c = np.asarray(c, np.float64)
    r0 = np.clip(np.floor(r).astype(int), 0, R - 2); c0 = np.clip(np.floor(c).astype(int), 0, C - 2)
    fr = (r - r0)[..., None]; fc = (c - c0)[..., None]
    return (X[r0, c0] * (1 - fr) * (1 - fc) + X[r0 + 1, c0] * fr * (1 - fc) + X[r0, c0 + 1] * (1 - fr) * fc + X[r0 + 1, c0 + 1] * fr * fc)


def local_frame(X, r, c):
    """(r, c) の局所の座標系（ds32_ids.frame_at と同じ定義。e1 = ∂P/∂c、n = ∂P/∂r × ∂P/∂c（空気の側）、e2 = n × e1）。"""
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


def closest_on_tris(p, A, B, C):
    """点 p (n,3) と三角形の組 A,B,C (n,m,3) の最短の点（Ericson の場合分けを numpy で）。戻り値：距離 (n,m)、重心の座標 (n,m,3)。"""
    p = p[:, None, :]
    ab = B - A; ac = C - A; ap = p - A
    d1 = np.einsum("nmk,nmk->nm", ab, ap); d2 = np.einsum("nmk,nmk->nm", ac, ap)
    bp = p - B
    d3 = np.einsum("nmk,nmk->nm", ab, bp); d4 = np.einsum("nmk,nmk->nm", ac, bp)
    cp = p - C
    d5 = np.einsum("nmk,nmk->nm", ab, cp); d6 = np.einsum("nmk,nmk->nm", ac, cp)
    va = d3 * d6 - d5 * d4; vb = d5 * d2 - d1 * d6; vc = d1 * d4 - d3 * d2
    shp = d1.shape
    u = np.zeros(shp); v = np.zeros(shp); w = np.zeros(shp)   # 重心の座標：A の重み u、B の重み v、C の重み w
    done = np.zeros(shp, bool)

    def put(m, uu, vv, ww):
        nonlocal done
        m = m & ~done
        u[m] = uu[m] if np.ndim(uu) else uu
        v[m] = vv[m] if np.ndim(vv) else vv
        w[m] = ww[m] if np.ndim(ww) else ww
        done |= m
    one = np.ones(shp); zero = np.zeros(shp)
    put((d1 <= 0) & (d2 <= 0), one, zero, zero)
    put((d3 >= 0) & (d4 <= d3), zero, one, zero)
    put((d6 >= 0) & (d5 <= d6), zero, zero, one)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(np.abs(d1 - d3) > 0, d1 / (d1 - d3), 0.0)
        put((vc <= 0) & (d1 >= 0) & (d3 <= 0), 1 - t, t, zero)
        t = np.where(np.abs(d2 - d6) > 0, d2 / (d2 - d6), 0.0)
        put((vb <= 0) & (d2 >= 0) & (d6 <= 0), 1 - t, zero, t)
        t = np.where(np.abs((d4 - d3) + (d5 - d6)) > 0, (d4 - d3) / ((d4 - d3) + (d5 - d6)), 0.0)
        put((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), zero, 1 - t, t)
        den = va + vb + vc
        den = np.where(np.abs(den) > 0, den, 1.0)
        put(np.ones(shp, bool), va / den, vb / den, vc / den)
    q = u[..., None] * A + v[..., None] * B + w[..., None] * C
    dist = np.linalg.norm(p - q, axis=-1)
    return dist, np.stack([u, v, w], -1)


def nearest_on_sheet(X, pts, rc0, half):
    """点 pts (n,3) に最も近いシートの面の点を、結び付けの (行, 列) rc0 (n,2) のまわり ±half 升の三角形から探す。
    戻り値：距離 (n)、(行, 列) (n,2)、窓の縁に当たったか (n)。"""
    R, C = X.shape[:2]
    n = len(pts)
    ar = np.arange(-half, half + 1)
    r0 = np.clip(np.floor(rc0[:, 0]).astype(int), 0, R - 2)
    c0 = np.clip(np.floor(rc0[:, 1]).astype(int), 0, C - 2)
    rr = np.clip(r0[:, None, None] + ar[None, :, None], 0, R - 2)
    cc = np.clip(c0[:, None, None] + ar[None, None, :], 0, C - 2)
    rr, cc = np.broadcast_arrays(rr, cc)
    rr = rr.reshape(n, -1); cc = cc.reshape(n, -1)
    a = X[rr, cc]; b = X[rr + 1, cc]; c_ = X[rr, cc + 1]; d = X[rr + 1, cc + 1]
    d0, w0 = closest_on_tris(pts, a, b, c_)
    d1, w1 = closest_on_tris(pts, c_, b, d)
    use1 = d1 < d0
    dist = np.where(use1, d1, d0)
    k = np.argmin(dist, axis=1)
    ii = np.arange(n)
    dmin = dist[ii, k]
    r_c = rr[ii, k].astype(np.float64); c_c = cc[ii, k].astype(np.float64)
    w0k = w0[ii, k]; w1k = w1[ii, k]
    # tri0：A=(r,c) B=(r+1,c) C=(r,c+1) → (r + wB, c + wC)。tri1：A=(r,c+1) B=(r+1,c) C=(r+1,c+1) → (r + wB + wC, c + wA + wC)
    rt0 = r_c + w0k[:, 1]; ct0 = c_c + w0k[:, 2]
    rt1 = r_c + w1k[:, 1] + w1k[:, 2]; ct1 = c_c + w1k[:, 0] + w1k[:, 2]
    u1 = use1[ii, k]
    rc = np.stack([np.where(u1, rt1, rt0), np.where(u1, ct1, ct0)], -1)
    edge = (np.abs(rr[ii, k] - r0) >= half) | (np.abs(cc[ii, k] - c0) >= half)
    return dmin, rc, edge


# ---------------------------------------------------------------- 文脈（主役波・時計・カメラ・一覧）
class Context:
    def __init__(self):
        import ds30_checks as K
        import candA_common as CA
        import af27common as C27
        self.K = K
        self.hero = K.Pkg(HERO)
        self.R, self.C = self.hero.R, self.hero.C
        warp = json.load(open(WARP, encoding="utf-8"))
        self.wt, self.wtau = np.array(warp["t"]), np.array(warp["tau"])
        self.taus = np.interp(np.arange(NFR) / FPS, self.wt, self.wtau)
        self.f_star = int(np.nonzero(self.taus >= -1e-12)[0][0])
        self.V1, self.tgt, self.fr = CA.painting_frame()
        self.pcam = self.fr.cam                      # gw_wavegen.PaintingCam（被覆の描画）
        self.spec = json.load(open(TRUTH, encoding="utf-8"))
        self.cam = C27.Cam(self.spec)                # af27common.Cam（投影・z バッファ。PaintingCam と同じ式）
        self.tris_all = K.grid_tris(self.R, self.C)
        self.inv = json.load(open(DS32 + "/ds32_claw_inventory.json", encoding="utf-8"))
        self.ids32 = json.load(open(DS32 + "/ds32_ids.json", encoding="utf-8"))
        self.list_by_id = {c["id"]: c for c in self.inv["claws"]}
        self.bind_by_id = {c["id"]: c for c in self.ids32["claws"] if c.get("bound")}
        tw = np.fromfile(HERO + "/" + self.hero.k["twhite_file"], "<f4").reshape(self.R, self.C).astype(np.float64)
        self.twhite = np.where(tw > 1e8, np.inf, tw)
        self._X = {}
        self.inputs = {p: sha(p) for p in (WARP, TRUTH, DS32 + "/ds32_claw_inventory.json", DS32 + "/ds32_ids.json",
                                           HERO + "/ds27_keypose.json", HERO + "/" + self.hero.k["pos_file"],
                                           HERO + "/" + self.hero.k["pos_lo_file"], HERO + "/" + self.hero.k["twhite_file"])}

    def X(self, f):
        if f not in self._X:
            if len(self._X) > 4:
                self._X.pop(next(iter(self._X)))
            self._X[f] = self.hero.world(float(self.taus[f]))
        return self._X[f]


# ---------------------------------------------------------------- 爪の部の出力を読む（ファイルの書式）
class ClawFramesFile:
    """書式 GreatWave.DS33.claw_frames/1（README_interface.txt）。位相（三角形・頂点の爪の番号）は全コマで同じ。
    manifest（JSON）：schema, ids, frames, vertex_count, triangle_count, fps,
      positions_file（float32、frames × N × 3、ワールドの m）, triangles_file（int32、M × 3）, cid_file（int32、N）,
      任意：root_file（float32、frames × K × 3）, tip_file（float32、frames × K × 3）, visible_file（uint8、frames × K）,
            root_rc（K × 2 の JSON の並び）, root_vertices_file（int32 の JSON：{"offsets": [...], "file": ...}）
    ファイル名は manifest のフォルダーからの相対。"""

    def __init__(self, manifest):
        self.path = manifest
        d = os.path.dirname(manifest)
        m = json.load(open(manifest, encoding="utf-8"))
        self.m = m
        self.ids = list(m["ids"])
        self.n_frames = int(m["frames"])
        N, M, K = int(m["vertex_count"]), int(m["triangle_count"]), len(self.ids)
        self.files = {}

        def fp(key):
            p = os.path.join(d, m[key])
            self.files[key] = p
            return p
        self.pos = np.memmap(fp("positions_file"), "<f4", "r", shape=(self.n_frames, N, 3))
        self.T = np.fromfile(fp("triangles_file"), "<i4").reshape(M, 3)
        self.cid = np.fromfile(fp("cid_file"), "<i4").reshape(N)
        self.root = np.memmap(fp("root_file"), "<f4", "r", shape=(self.n_frames, K, 3)) if m.get("root_file") else None
        self.tip = np.memmap(fp("tip_file"), "<f4", "r", shape=(self.n_frames, K, 3)) if m.get("tip_file") else None
        self.vis = np.memmap(fp("visible_file"), "u1", "r", shape=(self.n_frames, K)) if m.get("visible_file") else None
        self.root_rc = np.array(m["root_rc"], np.float64) if m.get("root_rc") else None
        self.root_vertices = None
        if m.get("root_vertices"):
            rv = m["root_vertices"]
            flat = np.fromfile(os.path.join(d, rv["file"]), "<i4")
            off = rv["offsets"]
            self.root_vertices = [flat[off[k]:off[k + 1]] for k in range(K)]

    def frame(self, f):
        out = dict(V=np.asarray(self.pos[f], np.float64), T=self.T, cid=self.cid)
        if self.root is not None:
            out["root"] = np.asarray(self.root[f], np.float64)
        if self.tip is not None:
            out["tip"] = np.asarray(self.tip[f], np.float64)
        if self.vis is not None:
            out["visible"] = np.asarray(self.vis[f]).astype(bool)
        return out


class ArrayProvider:
    """爪の部が手元の配列から呼ぶための薄い包み：frame_fn(f) → dict（V, T, cid, 任意で root, tip, visible, root_vertices）。"""

    def __init__(self, ids, frame_fn, n_frames=NFR, root_rc=None, root_vertices=None, path=None):
        self.ids = list(ids)
        self.frame = frame_fn
        self.n_frames = int(n_frames)
        self.root_rc = None if root_rc is None else np.asarray(root_rc, np.float64)
        self.root_vertices = root_vertices
        self.path = path


# ---------------------------------------------------------------- 1 コマの爪ごとの量
def per_claw_geometry(fd, K, root_hint):
    """fd：provider.frame(f)。戻り値：root (K,3)、tip (K,3)、visible (K,)、length (K,)、area (K,)、nverts (K,)、finite (K,)、
    近根の向き near_dir (K,3)（根元から長さの 5〜25% の頂点の重心への単位ベクトル、ワールド）。"""
    V, T, cid = fd["V"], fd["T"], np.asarray(fd["cid"])
    isc = cid >= 0
    cc = np.clip(cid, 0, max(K - 1, 0))
    nverts = np.bincount(cid[isc], minlength=K)[:K]
    finite_v = np.all(np.isfinite(V), axis=1)
    bad = np.bincount(cid[isc & ~finite_v], minlength=K)[:K]
    Vf = np.where(finite_v[:, None], V, 0.0)
    tc = cid[T[:, 0]]
    ar = 0.5 * np.linalg.norm(np.cross(Vf[T[:, 1]] - Vf[T[:, 0]], Vf[T[:, 2]] - Vf[T[:, 0]]), axis=1)
    area = np.zeros(K)
    okt = tc >= 0
    np.add.at(area, tc[okt], ar[okt])
    if fd.get("root") is not None:
        root = np.asarray(fd["root"], np.float64).copy()
    else:
        root = np.full((K, 3), np.nan)
        rv = fd.get("root_vertices")
        if rv is not None:
            for k in range(K):
                if len(rv[k]):
                    root[k] = Vf[rv[k]].mean(0)
        need = ~np.all(np.isfinite(root), axis=1)
        if need.any():
            if root_hint is not None:
                dh = np.linalg.norm(Vf - np.nan_to_num(root_hint)[cc], axis=1)
                dh = np.where(isc & np.all(np.isfinite(root_hint), axis=1)[cc], dh, np.inf)
            else:
                dh = np.where(isc, np.arange(len(cid), dtype=np.float64), np.inf)   # 爪の最初の頂点
            order = np.lexsort((dh, cid))
            cs = cid[order]
            first = np.ones(len(cs), bool); first[1:] = cs[1:] != cs[:-1]
            sel = order[first & (cs >= 0) & np.isfinite(dh[order])]
            put = need[cid[sel]]
            root[cid[sel][put]] = Vf[sel][put]
    dv = np.linalg.norm(Vf - np.nan_to_num(root)[cc], axis=1)
    dv = np.where(isc, dv, -1.0)
    length = np.zeros(K)
    np.maximum.at(length, cc[isc], dv[isc])
    if fd.get("tip") is not None:
        tip = np.asarray(fd["tip"], np.float64)
    else:
        tip = np.full((K, 3), np.nan)
        order = np.lexsort((-dv, cid))
        cs = cid[order]
        first = np.ones(len(cs), bool); first[1:] = cs[1:] != cs[:-1]
        sel = order[first & (cs >= 0)]
        tip[cid[sel]] = Vf[sel]
    L = length[cc]
    m = isc & (dv >= 0.05 * L) & (dv <= 0.25 * L) & (L > 1e-6)
    sm = np.zeros((K, 3)); cn = np.zeros(K)
    np.add.at(sm, cc[m], Vf[m]); np.add.at(cn, cc[m], 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        nd = sm / cn[:, None] - root
        nd = nd / np.linalg.norm(nd, axis=1, keepdims=True)
    nd[cn == 0] = np.nan
    vis = fd.get("visible")
    vis = (area > 0) if vis is None else (np.asarray(vis, bool) & (nverts > 0))
    return dict(root=root, tip=tip, visible=vis, length=length, area=area, nverts=nverts, finite=(bad == 0), near_dir=nd)


# ---------------------------------------------------------------- C・D・E・F（全コマ）
def measure_tracks(ctx, prov, log=print):
    ids = list(prov.ids)
    K = len(ids)
    nfr = min(int(prov.n_frames), NFR)
    rc_bind = getattr(prov, "root_rc", None)
    rc = np.full((K, 2), np.nan)
    rc_from = ["none"] * K
    for k, cid in enumerate(ids):
        if rc_bind is not None and np.all(np.isfinite(rc_bind[k])):
            rc[k] = rc_bind[k]; rc_from[k] = "provider"
        elif cid in ctx.bind_by_id:
            rc[k] = ctx.bind_by_id[cid]["sheet_rc"]; rc_from[k] = "ds32_ids"
    bound = np.all(np.isfinite(rc), axis=1)
    rv = getattr(prov, "root_vertices", None)
    # 記録用の配列
    dist_tri = np.full((nfr, K), np.nan)      # 根元 → 三角形の面（m）
    dist_bil = np.full((nfr, K), np.nan)      # 根元 → 双線形の点 (r, c) との差（m、結び付けの点そのもの）
    slip = np.full((nfr, K), np.nan)          # 同じコマの面の上での、最も近い点と結び付けの点の距離（m）
    slip_rc = np.full((nfr, K), np.nan)       # (行, 列) の動き（升）
    bind_off = np.full((nfr, K), np.nan)      # 根元の最も近い点と、結び付け（爪の部の root_rc か ds32 の sheet_rc）の点の距離（m、記録）
    rc_birth = np.full((K, 2), np.nan)        # 最初に見えたコマの根元の (行, 列)（滑りの基準）
    edge_hits = 0
    signed = np.full((nfr, K), np.nan)        # 法線の向きの符号つき（空気の側が正）
    rootv_max = np.full((nfr, K), np.nan)     # 根元の断面の頂点の面までの距離の最大（任意）
    vis = np.zeros((nfr, K), bool)
    length = np.full((nfr, K), np.nan)
    area = np.full((nfr, K), np.nan)
    nverts = np.zeros((nfr, K), np.int64)
    finite = np.ones((nfr, K), bool)
    ang_local = np.full((nfr, K, 3), np.nan)  # 根元の近くの向き（根元の局所の座標系）
    relmove = np.full((nfr, K), np.nan)       # 根元に対する頂点の動きの最大（前のコマから、m）。頂点の段（瞬間移動）を見る
    dev2 = np.full((nfr, K), np.nan)          # 根元に対する頂点の位置の 2 階差分の最大 |q(f) − (q(f−1)+q(f+1))/2|（m）。1 コマだけの突出を見る
    prevV = prevR = None
    qhist = []
    t0 = time.time()
    for f in range(nfr):
        fd = prov.frame(f)
        if rv is not None and "root_vertices" not in fd:
            fd["root_vertices"] = rv
        X = ctx.X(f)
        hint = np.where(bound[:, None], tri_interp(X, np.nan_to_num(rc[:, 0]), np.nan_to_num(rc[:, 1])), np.nan)
        g = per_claw_geometry(fd, K, hint)
        vis[f] = g["visible"]; length[f] = g["length"]; area[f] = g["area"]; nverts[f] = g["nverts"]; finite[f] = g["finite"]
        sel = np.nonzero(g["visible"] & bound & np.all(np.isfinite(g["root"]), axis=1))[0]
        if len(sel):
            pr = g["root"][sel]
            d, rcs, edge = nearest_on_sheet(X, pr, rc[sel], P["window_cells"])
            if edge.any():
                e = np.nonzero(edge)[0]
                d2, rc2, edge2 = nearest_on_sheet(X, pr[e], rc[sel][e], P["window_cells_wide"])
                better = d2 < d[e]
                d[e[better]] = d2[better]; rcs[e[better]] = rc2[better]
                edge_hits += int(edge2.sum())
            dist_tri[f, sel] = d
            pb = bilin(X, rc[sel, 0], rc[sel, 1])
            pt = tri_interp(X, rc[sel, 0], rc[sel, 1])
            dist_bil[f, sel] = np.linalg.norm(pr - pb, axis=1)
            q = tri_interp(X, rcs[:, 0], rcs[:, 1])
            nb = ~np.all(np.isfinite(rc_birth[sel]), axis=1)
            rc_birth[sel[nb]] = rcs[nb]
            pbirth = tri_interp(X, rc_birth[sel, 0], rc_birth[sel, 1])
            slip[f, sel] = np.linalg.norm(q - pbirth, axis=1)
            slip_rc[f, sel] = np.linalg.norm(rcs - rc_birth[sel], axis=1)
            bind_off[f, sel] = np.linalg.norm(q - pt, axis=1)
            Fm = local_frame(X, rc[sel, 0], rc[sel, 1])
            signed[f, sel] = np.einsum("nk,nk->n", pr - q, Fm[:, 2])
            # 根元の近くの向き（根元から長さの 5〜25% の頂点の重心への向き）を根元の局所の座標系で
            ang_local[f, sel] = np.einsum("nij,nj->ni", Fm, g["near_dir"][sel])
            rvs = fd.get("root_vertices")
            if rvs is not None:
                lens = np.array([len(rvs[k]) for k in sel])
                if lens.sum():
                    allv = np.concatenate([rvs[k] for k in sel if len(rvs[k])])
                    rep = np.repeat(np.arange(len(sel)), lens)
                    dv_, _, _ = nearest_on_sheet(X, fd["V"][allv], rcs[rep], P["window_cells"])
                    mxv = np.full(len(sel), np.nan)
                    np.fmax.at(mxv, rep, dv_)
                    rootv_max[f, sel] = mxv
        V_, cid_ = fd["V"], np.asarray(fd["cid"])
        if prevV is not None and len(prevV) == len(V_):
            okc = cid_ >= 0
            cc_ = np.clip(cid_, 0, K - 1)
            rel = np.linalg.norm((V_ - np.nan_to_num(g["root"])[cc_]) - (prevV - np.nan_to_num(prevR)[cc_]), axis=1)
            rel = np.where(okc & np.isfinite(rel), rel, -1.0)
            mv = np.full(K, -1.0)
            np.maximum.at(mv, cc_[okc], rel[okc])
            both = g["visible"] & vis[f - 1]
            relmove[f] = np.where(both & (mv >= 0), mv, np.nan)
        qrel = V_ - np.nan_to_num(g["root"])[np.clip(cid_, 0, K - 1)]
        if len(qhist) == 2 and len(qhist[0]) == len(V_) and len(qhist[1]) == len(V_):
            q0, q1 = qhist
            okc = cid_ >= 0
            cc_ = np.clip(cid_, 0, K - 1)
            dd = np.linalg.norm(q1 - 0.5 * (q0 + qrel), axis=1)
            dd = np.where(okc & np.isfinite(dd), dd, -1.0)
            mv = np.full(K, -1.0)
            np.maximum.at(mv, cc_[okc], dd[okc])
            both = g["visible"] & vis[f - 1] & vis[f - 2]
            dev2[f - 1] = np.where(both & (mv >= 0), mv, np.nan)
        qhist = (qhist + [qrel])[-2:]
        prevV, prevR = V_.copy(), g["root"].copy()
        if f % 60 == 0:
            log("  tracks frame %d/%d  %.1fs" % (f, nfr, time.time() - t0))
    f_star = min(ctx.f_star, nfr - 1)
    per = []
    for k, cid in enumerate(ids):
        v = vis[:, k]
        rec = dict(id=cid, bound=bool(bound[k]), rc_from=rc_from[k], sheet_rc=rnd(rc[k], 4) if bound[k] else None)
        if not v.any():
            rec.update(appears=False)
            per.append(rec)
            continue
        b = int(np.argmax(v))
        seg = slice(b, f_star + 1)
        gaps = int((~v[seg]).sum()) if b <= f_star else 0
        L = length[:, k]
        dL = np.diff(L[seg]) if b < f_star else np.zeros(0)
        len_dec = int((dL < -P["length_drop_m"]).sum())          # 根元から最も遠い頂点までの距離の減り（曲がると減りうる。記録のみ）
        Ar = area[seg, k]
        drops = int(((Ar[1:] < (1 - P["area_drop_frac"]) * Ar[:-1]) & v[seg][1:] & v[seg][:-1]).sum()) if len(Ar) > 1 else 0
        zero_area = int(((area[seg, k] <= 0) & v[seg]).sum())
        nonfinite = int((~finite[seg, k]).sum())
        Lmax = float(np.nanmax(L[seg])) if b <= f_star else float("nan")
        Amax = float(np.nanmax(area[seg, k])) if b <= f_star else float("nan")
        after = v[f_star:]
        rec.update(appears=True, birth_frame=b, birth_t=rnd(b / FPS, 4), birth_tau=rnd(ctx.taus[b], 4),
                   gaps_birth_to_tstar=gaps, area_drops=drops, length_decrease_frames=len_dec, zero_area_frames=zero_area,
                   nonfinite_frames=nonfinite, worst_length_decrease_m=rnd(float(-dL.min()) if len(dL) and dL.min() < 0 else 0.0, 5),
                   area_tstar_m2=rnd(area[f_star, k], 5),
                   length_tstar_m=rnd(L[f_star], 4), length_max_m=rnd(Lmax, 4),
                   grown_at_tstar=rnd(area[f_star, k] / Amax if Amax > 0 else float("nan"), 4),
                   reach_at_tstar=rnd(L[f_star] / Lmax if Lmax > 0 else float("nan"), 4),
                   visible_after_tstar_frames=int(after.sum()), frames_after_tstar=int(len(after)),
                   vertices_max=int(nverts[:, k].max()))
        rm = relmove[:, k]
        spk = []
        for f in range(1, nfr - 1):
            a0, a1, a2 = rm[f - 1], rm[f], rm[f + 1]
            add = float(np.clip(P["spike_len_frac"] * (length[f, k] if np.isfinite(length[f, k]) else 0.0), P["spike_min_m"], P["spike_abs_m"]))
            step = np.isfinite(a1) and np.isfinite(a0) and np.isfinite(a2) and a1 > P["spike_factor"] * max(a0, a2) + add
            b1 = dev2[f, k]
            nb = [dev2[j, k] for j in (f - 2, f + 2) if 0 <= j < nfr and np.isfinite(dev2[j, k])]
            pulse = np.isfinite(b1) and len(nb) > 0 and b1 > P["spike_factor"] * max(nb) + add
            if step or pulse:
                spk.append(f)
        rec.update(vertex_spike_frames=spk, rel_move_max_m=rnd(np.nanmax(rm) if np.isfinite(rm).any() else float("nan"), 4))
        if bound[k]:
            dt = dist_tri[:, k]; ds_ = slip[:, k]
            rec.update(root_dist_tri_max_m=rnd(np.nanmax(dt), 6), root_dist_tri_p99_m=rnd(np.nanpercentile(dt[np.isfinite(dt)], 99), 6),
                       root_dist_bilinear_max_m=rnd(np.nanmax(dist_bil[:, k]), 6),
                       root_signed_min_m=rnd(np.nanmin(signed[:, k]), 6), root_signed_max_m=rnd(np.nanmax(signed[:, k]), 6),
                       slip_max_m=rnd(np.nanmax(ds_), 6), slip_rc_max_cells=rnd(np.nanmax(slip_rc[:, k]), 5),
                       root_rc_birth=rnd(rc_birth[k], 4), bind_offset_max_m=rnd(np.nanmax(bind_off[:, k]), 5),
                       root_vertices_dist_max_m=rnd(np.nanmax(rootv_max[:, k]), 6) if np.isfinite(rootv_max[:, k]).any() else None)
            if cid in ctx.bind_by_id:
                tb = ctx.bind_by_id[cid]["tau_birth"]
                rec.update(tau_birth_ds32=tb, birth_minus_twhite_s=rnd(ctx.taus[b] - tb, 4))
            a = ang_local[:, k]
            okf = np.all(np.isfinite(a), axis=1)
            okf[:b] = False
            if okf.any():
                ref = a[f_star] if np.all(np.isfinite(a[f_star])) else a[np.nonzero(okf)[0][-1]]
                cosang = np.clip(a[okf] @ ref, -1, 1)
                grown = okf & (L >= 0.3 * (Lmax if np.isfinite(Lmax) else 0))
                cg = np.clip(a[grown] @ ref, -1, 1) if grown.any() else np.array([1.0])
                rec.update(root_angle_change_max_deg=rnd(np.degrees(np.arccos(cosang.min())), 3),
                           root_angle_change_after30pct_deg=rnd(np.degrees(np.arccos(cg.min())), 3),
                           root_elev_tstar_deg=rnd(np.degrees(np.arcsin(np.clip(ref[2], -1, 1))), 3))
        per.append(rec)
    app = [r for r in per if r.get("appears")]
    bnd = [r for r in app if r["bound"]]

    def mx(key, rs):
        v = [r[key] for r in rs if r.get(key) is not None]
        return max(v) if v else None
    missing_vs_ds32 = sorted(set(ctx.bind_by_id) - set(r["id"] for r in app))
    summary = dict(
        frames=nfr, f_star=f_star, claws=K, appear=len(app), bound_appear=len(bnd), missing_vs_ds32_bound=missing_vs_ds32,
        window_edge_hits_after_widen=edge_hits,
        root_dist_tri_max_m=rnd(mx("root_dist_tri_max_m", bnd), 6),
        root_dist_bilinear_max_m=rnd(mx("root_dist_bilinear_max_m", bnd), 6),
        slip_max_m=rnd(mx("slip_max_m", bnd), 6), slip_rc_max_cells=rnd(mx("slip_rc_max_cells", bnd), 5),
        bind_offset_max_m=rnd(mx("bind_offset_max_m", bnd), 5),
        bind_offset_over_0p05m=[r["id"] for r in bnd if (r.get("bind_offset_max_m") or 0) > 0.05],
        gaps_total=int(sum(r["gaps_birth_to_tstar"] for r in app)), area_drops_total=int(sum(r["area_drops"] for r in app)),
        length_decrease_total=int(sum(r["length_decrease_frames"] for r in app)),
        zero_area_total=int(sum(r["zero_area_frames"] for r in app)), nonfinite_total=int(sum(r["nonfinite_frames"] for r in app)),
        vertices_max=mx("vertices_max", app), vertices_total_max_frame=int(nverts.sum(1).max()),
        over_budget=[r["id"] for r in app if r["vertices_max"] > P["vertex_budget"]],
        not_grown_at_tstar=[r["id"] for r in app if r.get("grown_at_tstar") is not None and r["grown_at_tstar"] < 0.98],
        claws_with_gaps=[r["id"] for r in app if r["gaps_birth_to_tstar"]],
        vertex_spikes={r["id"]: r["vertex_spike_frames"] for r in app if r.get("vertex_spike_frames")}, claws_with_drops=[r["id"] for r in app if r["area_drops"]],
        claws_with_length_decrease=[r["id"] for r in app if r["length_decrease_frames"]],
        root_dist_over=[r["id"] for r in bnd if r["root_dist_tri_max_m"] is not None and r["root_dist_tri_max_m"] > P["root_dist_max_m"]],
        slip_over=[r["id"] for r in bnd if r["slip_max_m"] is not None and r["slip_max_m"] > P["slip_max_m"]],
        root_angle_change_after30pct_max_deg=rnd(mx("root_angle_change_after30pct_deg", bnd), 3),
        birth_minus_twhite_abs_max_s=rnd(max([abs(r["birth_minus_twhite_s"]) for r in bnd if r.get("birth_minus_twhite_s") is not None] or [float("nan")]), 4),
        vis_count_per_frame=vis.sum(1).tolist())
    arrays = dict(dist_tri=dist_tri, slip=slip, vis=vis, length=length)
    return summary, per, arrays


# ---------------------------------------------------------------- A・B（t* の原画視点）
def rasterize_cover(ctx, V, T):
    return ctx.V1.rasterize(ctx.pcam, V, T)


def clip_near(cam, tris, near_clip=0.1):
    """三角形 (N,3,3) をカメラの前 near_clip の面で切る（ds30_checks.raster_ids と同じ考え方を、この測定器で書き直したもの）。"""
    d = (tris - cam.pos[None, None, :]) @ cam.f - near_clip
    nin = (d > 0).sum(1)
    out = [tris[nin == 3]]
    for k in np.nonzero((nin == 1) | (nin == 2))[0]:
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
            out.append(np.array([[poly[0], poly[q], poly[q + 1]]]))
    return np.concatenate(out)


def cover_world_tris(ctx, tris, ss=2):
    """ワールドの三角形 (N,3,3) → PaintingCam v1 の被覆（1920×1080、ss×ss の超標本化。gw_wavegen_v1.rasterize と同じ塗り方）。"""
    tris = clip_near(ctx.cam, tris)
    xy, z = ctx.cam.project(tris.reshape(-1, 3))
    xy = xy.reshape(-1, 3, 2)
    ip = np.round(((xy + 0.5) * ss - 0.5) * 16)
    ok = np.all(np.abs(ip) < 2 ** 26, axis=(1, 2))
    ip = ip[ok].astype(np.int32)
    img = np.zeros((H * ss, W * ss), np.uint8)
    for tri in ip:
        cv2.fillConvexPoly(img, tri, 255, lineType=cv2.LINE_8, shift=4)
    return (img > 0).astype(np.float64).reshape(H, ss, W, ss).mean((1, 3))


class _OffsetCam:
    """投影した画素の座標を (dx, dy) だけ引くカメラ（画素の中心の標本を副画素へずらす）。"""

    def __init__(self, cam, dx, dy):
        self.cam, self.dx, self.dy = cam, dx, dy
        self.pos, self.f = cam.pos, cam.f

    def project(self, P):
        xy, z = self.cam.project(P)
        return xy - np.array([self.dx, self.dy]), z


def cover_center_sampled(ctx, tris):
    """ワールドの三角形 → 画素の中心で標本を取る被覆（GPU と同じ「中心が三角形の内側なら塗る」の規則）。2×2 の副画素
    （±0.25 px）で ds30_checks.raster_ids を 4 回回し、平均する。Unity の ID 画像（3840×2160 を 2×2 で平均）に近い読み。"""
    acc = np.zeros((H, W))
    ids = np.ones(len(tris), np.int32)
    for dy in (-0.25, 0.25):
        for dx in (-0.25, 0.25):
            idb, _ = ctx.K.raster_ids(_OffsetCam(ctx.cam, dx, dy), tris, ids)
            acc += idb > 0
    return acc / 4.0


def scene_tris_tstar(ctx):
    """設計30 の t* の場面（主役波の本体・near・far・残す仮置き・船。ds30_checks.scene_tris の "after"）。"""
    if hasattr(ctx, "_scene"):
        return ctx._scene
    K = ctx.K
    sea = REPO + "/Unity/Build/Design/30/sea"
    near = K.Pkg(sea + "/near"); far = K.Pkg(sea + "/far")
    idx = json.load(open(sea + "/near/ds30_ring0_index.json", encoding="utf-8"))
    cls_near = np.fromfile(sea + "/near/ds30_class_u8.bin", np.uint8).reshape(near.R, near.C)
    cls_far = np.fromfile(sea + "/far/ds30_class_u8.bin", np.uint8).reshape(far.R, far.C)
    jb, je = idx["body_cols"]
    tr, ii = K.scene_tris(0.0, ctx.hero, near, far, jb, je, "after", K.boats_tris(), K.placeholder_tris(), cls_near, cls_far)
    for p in (sea + "/near/" + near.k["pos_file"], sea + "/far/" + far.k["pos_file"], sea + "/near/ds30_ring0_index.json"):
        ctx.inputs[p] = sha(p)
    ctx._scene = tr
    return tr


def outline_gates(ctx, cov, seacov=None):
    import evaluate as E
    import gw_wavegen as G0
    import kh_gate_lf as L12
    import kh_gate_lfR4 as L24
    if not hasattr(ctx, "_truth"):
        ctx._truth = E.Truth()
        ctx._g12 = L12.LFGate()
        ctx._g24 = L24.LFGate()
    if seacov is None:
        seacov, _ = G0.sea_horizon_cover(ctx.pcam, ctx.tgt.spec)
    other = np.maximum(cov, seacov)
    reg = {"sky": 1.0 - other, "boat_left": np.zeros_like(cov), "boat_mid": np.zeros_like(cov), "boat_fg": np.zeros_like(cov)}
    m, det, rp = E.evaluate_core(ctx._truth, ctx._truth.disp_rgb, reg, versions=("envelope",), contour_judged=True)
    res = {}
    for k in ("78", "130", "131", "132", "72"):
        for me in m["items"].get(k, {}).get("measures", []):
            if me.get("version") == "envelope":
                res[k] = {"max_px": rnd(me["value_max_px"], 4), "p95_px": rnd(me["p95_px"], 4), "worst_xy": me.get("worst_display_xy")}
    g12 = ctx._g12.measure(cov, seacov)
    g24 = ctx._g24.measure(cov, seacov)
    res["132_lf_sigma12"] = {"max_px": rnd(g12["132"]["max_px"], 4), "worst_xy": g12["132"]["worst_xy"]}
    res["72_lf_sigma24"] = {"p95_px": rnd(g24["72"]["p95_px"], 4), "max_px": rnd(g24["72"]["max_px"], 4), "worst_xy": g24["72"]["worst_xy"]}
    res["72_lf_sigma12"] = {"p95_px": rnd(g12["72"]["p95_px"], 4)}
    return res, (det, rp, other)


def unity_ids_cover(png):
    im = cv2.imdecode(np.fromfile(png, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]
    h, w = im.shape[:2]
    sky = np.all(im == 255, axis=-1).astype(np.float64)
    if (h, w) != (H, W):
        sky = sky.reshape(H, h // H, W, w // W).mean((1, 3))
    return 1.0 - sky


def list_geometry(ctx, cid):
    c = ctx.list_by_id.get(cid)
    if c is None:
        return None
    return dict(root=np.array(c["root_display"], float), tip=np.array(c["tip_display"], float),
                centerline=to_disp(np.array(c["centerline_ref"], float)),
                region=to_disp(np.array(c["region_polygon_ref"], float)) if c.get("region_polygon_ref") else None,
                row=c.get("row"), b_region=c.get("b_region_q16"))


def poly_mask(poly, shape=(H, W)):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.round(poly * 16).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=4)
    return m.astype(bool)


def contour_pts(mask):
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return np.zeros((0, 2))
    return np.concatenate([c.reshape(-1, 2) for c in cs]).astype(np.float64)


def sym_hausdorff(a, b):
    if not len(a) or not len(b):
        return None, None
    from scipy.spatial import cKDTree
    da, _ = cKDTree(b).query(a)
    db, _ = cKDTree(a).query(b)
    d = np.concatenate([da, db])
    return float(d.max()), float(np.percentile(d, 95))


def measure_painting(ctx, prov, out_dir, f=None, log=print, tag=""):
    K = len(prov.ids)
    f = ctx.f_star if f is None else f
    fd = prov.frame(f)
    X = ctx.X(f)
    hint = np.full((K, 3), np.nan)
    for k, cid in enumerate(prov.ids):
        rcp = getattr(prov, "root_rc", None)
        rck = rcp[k] if rcp is not None and np.all(np.isfinite(rcp[k])) else (ctx.bind_by_id[cid]["sheet_rc"] if cid in ctx.bind_by_id else None)
        if rck is not None:
            hint[k] = tri_interp(X, rck[0], rck[1])
    if getattr(prov, "root_vertices", None) is not None and "root_vertices" not in fd:
        fd["root_vertices"] = prov.root_vertices
    g = per_claw_geometry(fd, K, hint)
    V, T, cidv = fd["V"], fd["T"], fd["cid"]
    tc = cidv[T[:, 0]]
    fin = np.all(np.isfinite(V), axis=1)
    okT = fin[T].all(1)
    # B：被覆（シート全体 + 爪 + 白の帯など）と、爪なしの基準
    cov0 = rasterize_cover(ctx, X.reshape(-1, 3), ctx.tris_all)
    Vall = np.concatenate([X.reshape(-1, 3), np.where(fin[:, None], V, 0.0)])
    Tall = np.concatenate([ctx.tris_all, T[okT] + X.shape[0] * X.shape[1]])
    cov1 = rasterize_cover(ctx, Vall, Tall)
    Tcl = T[okT & (tc >= 0)] + X.shape[0] * X.shape[1]
    cov_claws_only = rasterize_cover(ctx, Vall, np.concatenate([ctx.tris_all, Tcl]))
    base, _ = outline_gates(ctx, cov0)
    withc, (det, rp, other) = outline_gates(ctx, cov1)
    claws_only, _ = outline_gates(ctx, cov_claws_only)
    # 場面の読み（設計30 の t* の場面 ＋ 爪。海は場面の網なので参照の海面の被覆は 0。Unity の ID 画像の読みに近い）
    scene = None
    try:
        st = scene_tris_tstar(ctx)
        cs0 = cover_center_sampled(ctx, st)
        cs1 = cover_center_sampled(ctx, np.concatenate([st, V[T[okT]]]))
        z0 = np.zeros_like(cs0)
        s0, _ = outline_gates(ctx, cs0, z0)
        s1, _ = outline_gates(ctx, cs1, z0)
        scene = dict(note_ja="設計30 の t* の場面（ds30_checks.scene_tris の after）＋爪を、画素の中心の標本（2×2 の副画素、GPU の規則）で被覆にした読み（記録）。"
                             "設計30・31 の Unity の値（132 σ12 3.7552、72 σ24 p95 4.0075）と爪なしの値で比べてから差を読む",
                     no_claws=s0, with_claws=s1,
                     delta_px={"132_raw_max": rnd(s1["132"]["max_px"] - s0["132"]["max_px"], 4), "72_raw_p95": rnd(s1["72"]["p95_px"] - s0["72"]["p95_px"], 4),
                               "132_lf_sigma12": rnd(s1["132_lf_sigma12"]["max_px"] - s0["132_lf_sigma12"]["max_px"], 4),
                               "72_lf_sigma24_p95": rnd(s1["72_lf_sigma24"]["p95_px"] - s0["72_lf_sigma24"]["p95_px"], 4)})
    except Exception as e:      # 場面の読みは記録のみ。失敗しても主の読みは残す
        scene = dict(error="%s: %s" % (type(e).__name__, e))
    # A：z バッファの ID（シート = 1、爪 k = 2 + k、爪でないもの = 2 + K）
    tris_w = np.concatenate([X.reshape(-1, 3)[ctx.tris_all], V[T[okT]]])
    tid = np.concatenate([np.ones(len(ctx.tris_all), np.int32), np.where(tc[okT] >= 0, 2 + tc[okT], 2 + K).astype(np.int32)])
    t0 = time.time()
    idb, _ = ctx.K.raster_ids(ctx.cam, tris_w, tid)
    log("  zbuffer %.1fs" % (time.time() - t0))
    per = []
    proj = lambda Q: ctx.cam.project(np.asarray(Q, float).reshape(-1, 3))[0]  # noqa: E731
    rroot = np.full((K, 2), np.nan); rtip = np.full((K, 2), np.nan)
    masks_all = {}
    for k, cid in enumerate(prov.ids):
        sel = okT & (tc == k)
        rec = dict(id=cid)
        lg = list_geometry(ctx, cid)
        if lg is not None:
            rec.update(row=lg["row"], b_region_q16=lg["b_region"])
        if not sel.any() or not g["visible"][k]:
            rec.update(rendered=False)
            per.append(rec)
            continue
        m_all = np.zeros((H * 2, W * 2), np.uint8)
        P2 = proj(V[T[sel]].reshape(-1, 3)).reshape(-1, 3, 2)
        ip = np.round(((P2 + 0.5) * 2 - 0.5) * 16).astype(np.int32)
        for tri in ip:
            cv2.fillConvexPoly(m_all, tri, 1, lineType=cv2.LINE_8, shift=4)
        m_all = m_all.reshape(H, 2, W, 2).max((1, 3)).astype(bool)
        masks_all[k] = m_all
        m_vis = idb == 2 + k
        nall = int(m_all.sum()); nvis = int((m_vis & m_all).sum())
        nsheet = int(((idb == 1) & m_all).sum())      # 主役波のシートが手前にある画素（ほかの爪が手前の画素は数えない）
        pr = proj(g["root"][k])[0]; pt = proj(g["tip"][k])[0]
        rroot[k] = pr; rtip[k] = pt
        rec.update(rendered=True, px_all=nall, px_visible=nvis, visible_frac=rnd(nvis / max(nall, 1), 4),
                   hidden_by_sheet_frac=rnd(nsheet / max(nall, 1), 4),
                   root_px=rnd(pr, 2), tip_px=rnd(pt, 2))
        if lg is not None:
            er = float(np.linalg.norm(pr - lg["root"])); et = float(np.linalg.norm(pt - lg["tip"]))
            v1 = pt - pr; v0 = lg["tip"] - lg["root"]
            ang = float(np.degrees(np.arccos(np.clip(v1 @ v0 / max(np.linalg.norm(v1) * np.linalg.norm(v0), 1e-9), -1, 1))))
            dtm = cv2.distanceTransform((~m_all).astype(np.uint8), cv2.DIST_L2, 5)
            cl = lg["centerline"]
            xi = np.clip(np.round(cl[:, 0]).astype(int), 0, W - 1); yi = np.clip(np.round(cl[:, 1]).astype(int), 0, H - 1)
            dcl = dtm[yi, xi]
            rec.update(root_err_px=rnd(er, 3), tip_err_px=rnd(et, 3), angle_err_deg=rnd(ang, 3),
                       length_ratio_px=rnd(np.linalg.norm(v1) / max(np.linalg.norm(v0), 1e-9), 4),
                       centerline_mean_px=rnd(dcl.mean(), 3), centerline_max_px=rnd(dcl.max(), 3),
                       centerline_in_frac=rnd((dcl <= 1.0).mean(), 4))
            if lg["region"] is not None:
                rm = poly_mask(lg["region"])
                inter = int((rm & m_all).sum()); uni = int((rm | m_all).sum())
                hmax, hp95 = sym_hausdorff(contour_pts(m_all), contour_pts(rm))
                rec.update(region_iou=rnd(inter / max(uni, 1), 4), region_covered=rnd(inter / max(int(rm.sum()), 1), 4),
                           outline_hausdorff_max_px=rnd(hmax, 3), outline_hausdorff_p95_px=rnd(hp95, 3))
        per.append(rec)
    # 自分の ID が最も近い一覧の爪か（根元と先端の平均のずれ）
    lid = [c for c in ctx.list_by_id]
    LR = np.array([ctx.list_by_id[c]["root_display"] for c in lid], float)
    LT = np.array([ctx.list_by_id[c]["tip_display"] for c in lid], float)
    for k, rec in enumerate(per):
        if not rec.get("rendered"):
            continue
        dd = 0.5 * (np.linalg.norm(LR - rroot[k], axis=1) + np.linalg.norm(LT - rtip[k], axis=1))
        j = int(np.argmin(dd))
        rec["nearest_list_id"] = lid[j]
        rec["nearest_is_self"] = lid[j] == rec["id"]
        rec["nearest_mean_err_px"] = rnd(dd[j], 3)
        flags = []
        if "root_err_px" not in rec:
            flags.append("一覧にない ID")
        else:
            if not rec["nearest_is_self"]:
                flags.append("最も近い一覧の爪が %s" % lid[j])
            if rec["root_err_px"] > P["corr_root_px"]:
                flags.append("根元のずれ > %g px" % P["corr_root_px"])
            if rec["angle_err_deg"] > P["corr_angle_deg"]:
                flags.append("向きの差 > %g°" % P["corr_angle_deg"])
            if rec["centerline_mean_px"] > P["corr_centerline_px"]:
                flags.append("中心線までの平均 > %g px" % P["corr_centerline_px"])
        if rec["hidden_by_sheet_frac"] > 1 - P["corr_visible_frac"]:
            flags.append("シートに隠れる（シートが手前の割合 > %g）" % (1 - P["corr_visible_frac"]))
        rec["flags"] = flags
    for rec in per:
        if not rec.get("rendered"):
            rec["flags"] = ["描いた爪がない"]
    rend = [r for r in per if r.get("rendered") and "root_err_px" in r]

    def stat(key):
        v = np.array([r[key] for r in rend if r.get(key) is not None], float)
        if not len(v):
            return None
        return dict(median=rnd(np.median(v), 3), p90=rnd(np.percentile(v, 90), 3), max=rnd(v.max(), 3),
                    n_le_4px=int((v <= P["per_claw_px"]).sum()) if key.endswith("_px") else None, n=int(len(v)))
    missing_bound = sorted(set(ctx.bind_by_id) - set(r["id"] for r in per if r.get("rendered")))
    summary = dict(frame=f, t=rnd(f / FPS, 4), tau=rnd(ctx.taus[f], 6), claws=K, rendered=len([r for r in per if r.get("rendered")]),
                   compared_with_list=len(rend), missing_vs_ds32_bound=missing_bound,
                   flagged=[{"id": r["id"], "flags": r["flags"]} for r in per if r["flags"]],
                   nearest_is_self=int(sum(1 for r in rend if r.get("nearest_is_self"))),
                   root_err_px=stat("root_err_px"), tip_err_px=stat("tip_err_px"), angle_err_deg=stat("angle_err_deg"),
                   centerline_mean_px=stat("centerline_mean_px"), region_iou=stat("region_iou"),
                   outline_hausdorff_max_px=stat("outline_hausdorff_max_px"), outline_hausdorff_p95_px=stat("outline_hausdorff_p95_px"),
                   visible_frac=stat("visible_frac"), hidden_by_sheet_frac=stat("hidden_by_sheet_frac"),
                   per_claw_4px_record=dict(root_le4=int(sum(1 for r in rend if r["root_err_px"] <= 4)),
                                            tip_le4=int(sum(1 for r in rend if r["tip_err_px"] <= 4)),
                                            outline_p95_le4=int(sum(1 for r in rend if (r.get("outline_hausdorff_p95_px") or 1e9) <= 4)),
                                            outline_max_le4=int(sum(1 for r in rend if (r.get("outline_hausdorff_max_px") or 1e9) <= 4)),
                                            n=len(rend)))
    outline = dict(reference_28r01=REF_28R01, sheet_only_same_method=base, with_claws=withc, claws_without_other_meshes=claws_only,
                   scene_reading_record=scene)
    d132 = withc["132"]["max_px"] - base["132"]["max_px"]
    d72 = withc["72"]["p95_px"] - base["72"]["p95_px"]
    outline["delta_vs_sheet_only_px"] = {"132_raw_max": rnd(d132, 4), "72_raw_p95": rnd(d72, 4)}
    outline["raw_improved"] = {"132": withc["132"]["max_px"] < REF_28R01["132_raw_max_px"], "72": withc["72"]["p95_px"] < REF_28R01["72_raw_p95_px"]}
    reg = {k: withc[k]["max_px"] for k in ("78", "130", "131")}
    outline["regression_items"] = dict(
        m78_130_131_le4={k: v <= 4.0 for k, v in reg.items()},
        lf132_sigma12_le4=withc["132_lf_sigma12"]["max_px"] <= 4.0, lf72_sigma24_p95_le4=withc["72_lf_sigma24"]["p95_px"] <= 4.0,
        worse_than_sheet_only_px={k: rnd(withc[k]["max_px"] - base[k]["max_px"], 4) for k in ("78", "130", "131")}
        | {"132_lf_sigma12": rnd(withc["132_lf_sigma12"]["max_px"] - base["132_lf_sigma12"]["max_px"], 4),
           "72_lf_sigma24_p95": rnd(withc["72_lf_sigma24"]["p95_px"] - base["72_lf_sigma24"]["p95_px"], 4)})
    figs = draw_painting_figs(ctx, prov, per, masks_all, rroot, rtip, other, det, rp, out_dir, tag, withc, base)
    return summary, per, outline, figs


# ---------------------------------------------------------------- 図
def plate():
    import evaluate as E
    t = E.Truth()
    return cv2.cvtColor(t.disp_rgb, cv2.COLOR_RGB2BGR)


def draw_painting_figs(ctx, prov, per, masks_all, rroot, rtip, other, det, rp, out_dir, tag, withc, base):
    os.makedirs(out_dir, exist_ok=True)
    pl = cv2.cvtColor(ctx._truth.disp_rgb, cv2.COLOR_RGB2BGR)
    img = (pl * 0.6).astype(np.uint8)
    over = np.zeros((H, W), bool)
    for k, m in masks_all.items():
        over |= m
    img[over] = (img[over] * 0.55 + np.array([255, 60, 255]) * 0.45).astype(np.uint8)
    cs, _ = cv2.findContours(over.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, cs, -1, (255, 0, 255), 1, cv2.LINE_8)
    for rec in per:
        lg = list_geometry(ctx, rec["id"])
        if lg is None:
            continue
        if lg["region"] is not None:
            cv2.polylines(img, [np.round(lg["region"] * 4).astype(np.int32)], True, (255, 255, 0), 1, cv2.LINE_AA, shift=2)
        cv2.polylines(img, [np.round(lg["centerline"] * 4).astype(np.int32)], False, (0, 255, 255), 1, cv2.LINE_AA, shift=2)
        cv2.circle(img, tuple(np.round(lg["root"]).astype(int)), 2, (0, 255, 255), -1, cv2.LINE_AA)
    for k, rec in enumerate(per):
        if not rec.get("rendered"):
            continue
        a, b = rroot[k], rtip[k]
        cv2.line(img, tuple(np.round(a * 4).astype(int)), tuple(np.round(b * 4).astype(int)), (0, 0, 255), 1, cv2.LINE_AA, shift=2)
        cv2.circle(img, tuple(np.round(a).astype(int)), 2, (0, 0, 255), -1, cv2.LINE_AA)
    for rec in per:
        if rec.get("flags"):
            lg = list_geometry(ctx, rec["id"])
            q = lg["root"] if lg is not None else (rroot[prov.ids.index(rec["id"])] if rec.get("rendered") else None)
            if q is not None and np.all(np.isfinite(q)):
                cv2.putText(img, rec["id"], (int(q[0]) + 3, int(q[1]) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (40, 40, 255), 1, cv2.LINE_AA)
    lines = ["DS33 harness %s: painting view t* (numpy raster of the claw meshes, not Unity)" % tag,
             "cyan = ds32 list region (inside the indigo outline), yellow = list centerline + root, magenta = rendered claws (fill + outline), red = rendered root->tip",
             "red ID = flagged (missing / not nearest / root > %g px / angle > %g deg / centerline > %g px / hidden)" % (P["corr_root_px"], P["corr_angle_deg"], P["corr_centerline_px"])]
    for i, s in enumerate(lines):
        cv2.putText(img, s, (20, 1010 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    p1 = os.path.join(out_dir, "fig_ds33h_overlay_tstar%s.png" % tag)
    imwrite(p1, img)
    # 列ごとの拡大（一覧の爪の根元の外接で 4 枚）
    rows = {}
    for rec in per:
        lg = list_geometry(ctx, rec["id"])
        if lg is None:
            continue
        key = "b区域" if lg["b_region"] else lg["row"]
        rows.setdefault(key, []).append(np.vstack([lg["root"], lg["tip"]]))
    tiles = []
    for key in sorted(rows):
        pts = np.vstack(rows[key])
        x0, y0 = np.floor(pts.min(0) - 25).astype(int); x1, y1 = np.ceil(pts.max(0) + 25).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W), min(y1, H)
        crop = img[y0:y1, x0:x1]
        tiles.append((key, crop))
    comp = np.zeros((H, W, 3), np.uint8)
    n = max(1, len(tiles))
    cols = 2 if n > 1 else 1
    rws = int(math.ceil(n / cols))
    tw_, th_ = W // cols, H // rws
    for i, (key, crop) in enumerate(tiles):
        s = min(tw_ / crop.shape[1], (th_ - 24) / crop.shape[0])
        cr = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), max(1, int(crop.shape[0] * s))), interpolation=cv2.INTER_NEAREST if s > 1 else cv2.INTER_AREA)
        oy, ox = (i // cols) * th_ + 24, (i % cols) * tw_
        comp[oy:oy + cr.shape[0], ox:ox + cr.shape[1]] = cr
        cv2.putText(comp, "%s  (x%.2f)" % (ROW_EN.get(key, key.encode("ascii", "replace").decode()), s), (ox + 6, oy - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    p2 = os.path.join(out_dir, "fig_ds33h_overlay_rows%s.png" % tag)
    imwrite(p2, comp)
    # 輪郭の図（評価器の重ね図と同じ描き方に、132・72 の値）
    import evaluate as E
    p3 = os.path.join(out_dir, "fig_ds33h_outline_132_72%s.png" % tag)
    im3 = (ctx._truth.disp_rgb * 0.5 + np.dstack([other * 60, other * 90, other * 140]) * 0.5).astype(np.uint8)
    E.overlay_png(ctx._truth, im3, det, rp, p3, "DS33 harness %s: sheet + claws (numpy). 132 raw max %.3f (sheet %.3f, 28R01 5.911)  72 raw p95 %.3f (sheet %.3f, 28R01 8.717)" % (
        tag, withc["132"]["max_px"], base["132"]["max_px"], withc["72"]["p95_px"], base["72"]["p95_px"]), ("envelope",))
    return [p1, p2, p3]


ROW_EN = {"上側": "upper row", "途中": "middle row", "船側": "boat-side row", "右側": "right side (untouched)", "b区域": "b-region (Q16)"}


def draw_tracks_fig(ctx, summ, arrays, out_dir, tag=""):
    """根元の距離・滑りの各コマの最大、見える爪の数、長さの曲線（一部）。"""
    img = np.full((H, W, 3), 255, np.uint8)
    nfr = arrays["vis"].shape[0]
    panels = [("root -> sheet distance, max over claws (mm)  [105: <= 1 mm]", np.nanmax(np.where(np.isfinite(arrays["dist_tri"]), arrays["dist_tri"], -1), axis=1) * 1e3, 1.0),
              ("root slip on the sheet, max over claws (mm)  [137: 0, tol 1 mm]", np.nanmax(np.where(np.isfinite(arrays["slip"]), arrays["slip"], -1), axis=1) * 1e3, 1.0),
              ("visible claws per frame", arrays["vis"].sum(1).astype(float), None)]
    ph = 250
    for i, (title, y, lim) in enumerate(panels):
        oy = 30 + i * (ph + 40)
        x0, x1 = 90, W - 40
        cv2.rectangle(img, (x0, oy), (x1, oy + ph), (0, 0, 0), 1)
        yv = np.where(y < 0, np.nan, y)
        top = np.nanmax(yv) if np.isfinite(yv).any() else 1.0
        top = max(top, lim * 1.2 if lim else 1.0, 1e-9)
        xs = x0 + (x1 - x0) * np.arange(nfr) / max(nfr - 1, 1)
        ys = oy + ph - ph * np.nan_to_num(yv, nan=0.0) / top
        pts = np.stack([xs, ys], 1)
        cv2.polylines(img, [np.round(pts * 4).astype(np.int32)], False, (200, 60, 0), 1, cv2.LINE_AA, shift=2)
        if lim:
            yl = oy + ph - ph * lim / top
            cv2.line(img, (x0, int(yl)), (x1, int(yl)), (0, 0, 220), 1)
        xs_ = x0 + (x1 - x0) * ctx.f_star / max(nfr - 1, 1)
        cv2.line(img, (int(xs_), oy), (int(xs_), oy + ph), (0, 160, 0), 1)
        cv2.putText(img, title + "   top %.4g" % top, (x0, oy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "DS33 harness %s: frames 0..%d at 30 Hz (green = t*, red = limit). numpy on the hero sheet (Unity triangulation), not Unity." % (tag, nfr - 1),
                (90, H - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    p = os.path.join(out_dir, "fig_ds33h_tracks%s.png" % tag)
    imwrite(p, img)
    return p


# ---------------------------------------------------------------- 判定
def verdicts(tr, pa, outline):
    v = {}
    v["105_root_to_surface_le_1mm"] = dict(value_m=tr["root_dist_tri_max_m"], limit_m=P["root_dist_max_m"],
                                           verdict="合格" if tr["root_dist_tri_max_m"] is not None and tr["root_dist_tri_max_m"] <= P["root_dist_max_m"] else "不合格",
                                           over=tr["root_dist_over"], bilinear_point_max_m=tr["root_dist_bilinear_max_m"],
                                           note_ja="面は Unity と同じ三角形の分け方（精度の層つき）。双線形の点の値は、根元を ds32 の式（双線形）で置いたときの差の記録")
    v["137_root_slip_0"] = dict(value_m=tr["slip_max_m"], value_cells=tr["slip_rc_max_cells"], tol_m=P["slip_max_m"],
                                verdict="合格" if tr["slip_max_m"] is not None and tr["slip_max_m"] <= P["slip_max_m"] else "不合格", over=tr["slip_over"])
    cnt_ok = P["count_range"][0] <= tr["appear"] <= P["count_range"][1]
    ok139 = tr["gaps_total"] == 0 and tr["zero_area_total"] == 0 and tr["nonfinite_total"] == 0 and cnt_ok and not tr["missing_vs_ds32_bound"]
    okg = tr["area_drops_total"] == 0 and not tr["vertex_spikes"]
    v["139b_geometry_continuity"] = dict(area_drops=tr["area_drops_total"], claws_with_area_drops=tr["claws_with_drops"],
                                         vertex_spikes=tr["vertex_spikes"],
                                         rule_ja="この測定器の追加の読み：成長の途中で、面積が 1 コマで %g%% を超えて減る（爪の一部が消える・つぶれる）コマ 0、頂点の突出 0" % (
                                             100 * P["area_drop_frac"]),
                                         verdict="合格" if okg else "不合格")
    v["139_no_missing_mid_growth"] = dict(gaps=tr["gaps_total"], zero_area=tr["zero_area_total"],
                                          length_decrease_record=tr["length_decrease_total"],
                                          nonfinite=tr["nonfinite_total"], count=tr["appear"], count_range=P["count_range"],
                                          missing_vs_ds32_bound=tr["missing_vs_ds32_bound"], claws_with_gaps=tr["claws_with_gaps"],
                                          claws_with_drops=tr["claws_with_drops"], verdict="合格" if ok139 else "不合格")
    v["vertex_spike_record"] = dict(claws=tr["vertex_spikes"], count=int(sum(len(x) for x in tr["vertex_spikes"].values())),
                                    rule_ja="段：爪の頂点の、根元に対する 1 コマの動きの最大が、前後のコマの大きい方の %g 倍 + 余裕 を超える。"
                                            "突出：根元に対する位置の 2 階差分 |q(f) − (q(f−1)+q(f+1))/2| の最大が、2 コマ前後の値の大きい方の同じ倍 + 余裕を超える。"
                                            "余裕＝その爪の根元から最も遠い頂点までの距離 × %g を %g〜%g m に収めた値"
                                            "（設計32 の突出の規則 4 倍 + 5 cm を、爪の大きさに合わせて小さくした形）" % (
                                        P["spike_factor"], P["spike_len_frac"], P["spike_min_m"], P["spike_abs_m"]),
                                    verdict="記録（0 でなければ爪の部へ返す）" if tr["vertex_spikes"] else "0（記録）")
    v["vertex_budget_le_600"] = dict(max=tr["vertices_max"], over=tr["over_budget"],
                                     verdict="合格" if tr["vertices_max"] is not None and tr["vertices_max"] <= P["vertex_budget"] else "不合格")
    okA = not pa["flagged"] and not pa["missing_vs_ds32_bound"]
    v["A_painting_correspondence"] = dict(rendered=pa["rendered"], flagged=len(pa["flagged"]), missing=pa["missing_vs_ds32_bound"],
                                          nearest_is_self=pa["nearest_is_self"], root_err_px=pa["root_err_px"], angle_err_deg=pa["angle_err_deg"],
                                          verdict="合格（自動の読み。図で確かめる）" if okA else "不合格（自動の読み。図で確かめる）",
                                          rule_ja="描いた爪がない・自分の ID が最も近い一覧の爪でない・根元 > %g px・向き > %g°・中心線まで > %g px・シートが手前の割合 > %g のどれもない（この測定器の既定）" % (
                                              P["corr_root_px"], P["corr_angle_deg"], P["corr_centerline_px"], 1 - P["corr_visible_frac"]))
    v["per_claw_4px_record"] = dict(pa["per_claw_4px_record"], verdict="記録のみ")
    w = outline["with_claws"]
    v["132_72_raw_vs_28r01"] = dict(r132_max_px=w["132"]["max_px"], r72_p95_px=w["72"]["p95_px"],
                                    sheet_only_132=outline["sheet_only_same_method"]["132"]["max_px"],
                                    sheet_only_72=outline["sheet_only_same_method"]["72"]["p95_px"], ref_28r01=[REF_28R01["132_raw_max_px"], REF_28R01["72_raw_p95_px"]],
                                    improved=outline["raw_improved"], verdict="記録（段階6 で下げる目標。上がれば後退として挙げる）",
                                    regressed={"132": w["132"]["max_px"] > REF_28R01["132_raw_max_px"] + 0.05, "72": w["72"]["p95_px"] > REF_28R01["72_raw_p95_px"] + 0.05})
    ri = outline["regression_items"]
    okR = all(ri["m78_130_131_le4"].values()) and ri["lf132_sigma12_le4"] and ri["lf72_sigma24_p95_le4"]
    v["regression_78_130_131_132lf_72lf"] = dict(items=ri, values={k: w[k]["max_px"] for k in ("78", "130", "131")} | {
        "132_lf_sigma12_max": w["132_lf_sigma12"]["max_px"], "72_lf_sigma24_p95": w["72_lf_sigma24"]["p95_px"]},
        verdict="後退なし" if okR else "後退あり")
    sc = outline.get("scene_reading_record") or {}
    if "with_claws" in sc:
        a, b = sc["no_claws"], sc["with_claws"]
        keys = [("78", "max_px"), ("130", "max_px"), ("131", "max_px"), ("132_lf_sigma12", "max_px"), ("72_lf_sigma24", "p95_px"),
                ("132", "max_px"), ("72", "p95_px")]
        d = {k: rnd(b[k][m] - a[k][m], 4) for k, m in keys}
        v["scene_reading_unity_like"] = dict(no_claws={k: a[k][m] for k, m in keys}, with_claws={k: b[k][m] for k, m in keys}, delta=d,
                                             unity_31_values={"78": 3.0289, "130": 3.5131, "131": 3.0431, "132_lf_sigma12": 3.7552, "72_lf_sigma24": 4.0075},
                                             verdict="後退なし" if all(x <= 0.05 for x in d.values()) else "後退あり（爪で悪くなった項目がある）",
                                             note_ja="画素の中心の標本の読み。爪なしの値が設計31 の Unity の値と一致するかを見てから、爪あり − 爪なしで後退を読む（+0.05 px まで同じとみなす）")
    v["136_birth_record"] = dict(birth_minus_twhite_abs_max_s=tr["birth_minus_twhite_abs_max_s"], not_grown_at_tstar=tr["not_grown_at_tstar"], verdict="記録のみ")
    v["138_root_angle_record"] = dict(change_after30pct_max_deg=tr["root_angle_change_after30pct_max_deg"], verdict="記録のみ")
    return v


# ---------------------------------------------------------------- 入口
def evaluate(prov, out_dir=OUT_DEFAULT, tag="", unity_ids=None, ctx=None, log=print, figures=True):
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    ctx = ctx or Context()
    log("harness: %d claws, %d frames" % (len(prov.ids), prov.n_frames))
    tr, tper, arrays = measure_tracks(ctx, prov, log)
    log("tracks done %.1fs" % (time.time() - t0))
    pa, pper, outline, figs = measure_painting(ctx, prov, out_dir, log=log, tag=tag)
    log("painting done %.1fs" % (time.time() - t0))
    if figures:
        figs.append(draw_tracks_fig(ctx, tr, arrays, out_dir, tag))
    uni = None
    if unity_ids:
        uni = {}
        for lab, png in (("unity_base_31", UNITY_BASE_IDS), ("unity_claws", unity_ids)):
            if png and os.path.isfile(png):
                cov = unity_ids_cover(png)
                r, _ = outline_gates(ctx, cov, np.zeros_like(cov))
                uni[lab] = dict(png=png, sha256=sha(png), gates=r)
    ver = verdicts(tr, pa, outline)
    per = {}
    for r in tper:
        per.setdefault(r["id"], {}).update(tracks=r)
    for r in pper:
        per.setdefault(r["id"], {}).update(painting=r)
    res = dict(schema="GreatWave.DS33.harness/1", number="設計33", part="harness（独立の測定器）", tag=tag,
               kind_ja="numpy/OpenCV の計算（主役波のシートと爪のメッシュ）。Unity の描画ではない。HMD 実機ではない。",
               params=P, verdicts=ver, tracks=tr, painting=pa, outline=outline, unity_ids=uni,
               elapsed_s=round(time.time() - t0, 1))
    jdump(os.path.join(out_dir, "harness_metrics%s.json" % tag), res)
    jdump(os.path.join(out_dir, "harness_per_claw%s.json" % tag), dict(schema="GreatWave.DS33.harness_per_claw/1", claws=per))
    run = dict(schema="GreatWave.DS33.harness_run/1", command=" ".join(sys.argv), python=sys.version.split()[0], numpy=np.__version__,
               opencv=cv2.__version__, platform=platform.platform(), inputs_sha256=ctx.inputs,
               provider=dict(kind=type(prov).__name__, path=getattr(prov, "path", None),
                             files={k: dict(path=v, sha256=sha(v)) for k, v in getattr(prov, "files", {}).items()}),
               tool_sha256={p: sha(p) for p in (os.path.abspath(__file__),)}, figures=figs, elapsed_s=res["elapsed_s"])
    jdump(os.path.join(out_dir, "harness_run%s.json" % tag), run)
    log("harness done %.1fs → %s" % (time.time() - t0, out_dir))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claws", help="GreatWave.DS33.claw_frames/1 の manifest（JSON）")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--tag", default="")
    ap.add_argument("--unity-ids", default=None, help="Unity の t* の色区 ID 画像（空 = 白）。あれば輪郭をその画像からも測る")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        import ds33_harness_selftest as ST
        ST.main(a.out)
        return
    if not a.claws:
        ap.error("--claws か --selftest が要る")
    prov = ClawFramesFile(a.claws)
    evaluate(prov, a.out, a.tag, a.unity_ids)


if __name__ == "__main__":
    main()
