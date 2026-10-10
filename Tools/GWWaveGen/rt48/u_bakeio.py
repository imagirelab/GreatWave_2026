"""RT48：Unity で再生する焼き（計画 §2.4）の形を書く・読む・確かめるための共通の部品（numpy だけ）。

焼きのフォルダー  Unity/Build/RT48/bake/<元>/
  meta.json   UTF-8。下の META_KEYS（平らな配列だけ。Unity の JsonUtility で読む）
  pairs.bin   float32 リトルエンディアン。[組 p][曲線 c（0 = A、1 = B）][点 i][x, y]。
              組 p はコマ frame_first + p と frame_first + p + 1 の間。A はコマ p、B はコマ p + 1 を、
              目印の対応で点の番号をそろえて取り直したもの（A と B の同じ番号の点を線形に混ぜる）。
              x は x_origin_m（既定 527.0 m、最初の接触の所）からの距離、y は静かな水面からの高さ（m）。
  loops.bin   float32 リトルエンディアン。閉じた線の点 [点][x, y] を全部のコマぶん続けたもの（閉じる点は重ねない）。
              どのコマのどの線かは meta の loop_frame_first / loop_frame_count / loop_kind / loop_point_first / loop_point_count。
              loop_kind 0 = 離れた水、1 = 水に囲まれた空気。
時刻：コマ f の時刻は (f − 1) / fps。
補間：pair_interp[p] = 1 の組だけ、混ぜる割合 (t − t_p) × fps で A と B を混ぜる。0 の組は A（コマ p）を保つ。
      pair_reason：0 補間する、1 K から先、2 C4 で外れた、3 補間した線が自分と交わる、4 その他。
船：一番上の水面 ＝ その x の鉛直の線と主な曲線（x の両端の下ろしを掛けた後）の交わりのうち最も高い点。
    上下 ＝ 船体の 9 点（座席 ±6 m、1.5 m おき）の平均、縦揺れ ＝ 同じ 9 点の最小二乗の傾きの角。
    補間する組では描いている曲線（同じ組・同じ割合）から、補間しない組と最後のコマでは、コマごとの値を時刻で線形に補間する。
Unity 側の読み手は Assets/GreatWave/RT48/Scripts/RT48Bake.cs。式を変える時は両方を同じに変える。
"""
import hashlib
import json
import math
import os

import numpy as np

SCHEMA = "GreatWave.RT48.bake/1"
N_POINTS = 8192
X_ORIGIN = 527.0
FPS = 24.0
HULL_DX = np.array([-6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0])
FRAME_EPS = 1e-9  # 時刻からコマを決める時の床の余裕（Unity と同じ）

META_KEYS = [
    "schema", "source_id", "label_ja", "caption1_ja", "is_synthetic", "interp_verified", "created_utc", "tool", "note_ja",
    "x_origin_m", "n_points", "fps", "frame_first", "frame_count", "pair_count", "k_frame",
    "pair_interp", "pair_reason", "pair_lm_crest", "pair_lm_lip", "crest_x_m", "x_range_m", "taper_m",
    "onset_s", "onset_x_m", "contact_s", "contact_x_m", "side_end_s", "seat_x_m", "seat_end_s",
    "loop_frame_first", "loop_frame_count", "loop_kind", "loop_point_first", "loop_point_count",
    "files_name", "files_bytes", "files_sha256",
]


# ---------------------------------------------------------------- 時刻とコマ
def frame_time(frame, fps=FPS):
    return (frame - 1) / fps


def state_at(meta, t):
    """時刻 t から、見せる組・混ぜる割合・補間するか。Unity の RecordedSectionSource.StateAt と同じ式。"""
    fps = float(meta["fps"])
    t0 = (meta["frame_first"] - 1) / fps
    F = int(meta["frame_count"])
    u = (t - t0) * fps
    k = int(math.floor(u + FRAME_EPS))
    if k < 0:
        return {"frame": 0, "pair": 0, "alpha": 0.0, "interp": False, "last": False, "w": 0.0}
    if k >= F - 1:
        return {"frame": F - 1, "pair": F - 2, "alpha": 1.0, "interp": False, "last": True, "w": 0.0}
    w = min(1.0, max(0.0, u - k))
    if meta["pair_interp"][k]:
        return {"frame": k, "pair": k, "alpha": w, "interp": True, "last": False, "w": w}
    return {"frame": k, "pair": k, "alpha": 0.0, "interp": False, "last": False, "w": w}


# ---------------------------------------------------------------- 曲線の取り直し（目印の対応）
def arclen(c):
    d = np.hypot(np.diff(c[:, 0]), np.diff(c[:, 1]))
    return np.concatenate([[0.0], np.cumsum(d)])


def _sample(c, s_cum, s0, s1, m):
    """c の弧長 s0〜s1 を m 区間に等しく分けた m + 1 点。"""
    u = s0 + (s1 - s0) * np.arange(m + 1) / m
    return np.stack([np.interp(u, s_cum, c[:, 0]), np.interp(u, s_cum, c[:, 1])], axis=1)


def resample_pair(ca, cb, lm_a, lm_b, n=N_POINTS):
    """開いた線 ca・cb（頂点の並び）を、目印（頂点の番号の並び、同じ数、増える順）で区切り、区間ごとに弧長で等しく取り直す。
    区間の点の数は二つの線の区間の長さの平均で割り振る（各区間 1 以上、合わせて n 点、境の点は共有）。
    返り値：A (n,2)、B (n,2)、目印の出力の番号の並び。"""
    assert len(lm_a) == len(lm_b)
    sa, sb = arclen(ca), arclen(cb)
    ba = [0.0] + [sa[i] for i in lm_a] + [sa[-1]]
    bb = [0.0] + [sb[i] for i in lm_b] + [sb[-1]]
    L = np.array([0.5 * ((ba[s + 1] - ba[s]) + (bb[s + 1] - bb[s])) for s in range(len(ba) - 1)])
    S = len(L)
    total = n - 1
    raw = L / L.sum() * (total - S) + 1.0  # 各区間 1 以上
    m = np.floor(raw).astype(int)
    rest = total - m.sum()
    order = np.argsort(-(raw - m), kind="stable")
    m[order[:rest]] += 1
    A, B, idx = [], [], [0]
    for s in range(S):
        pa = _sample(ca, sa, ba[s], ba[s + 1], int(m[s]))
        pb = _sample(cb, sb, bb[s], bb[s + 1], int(m[s]))
        if s > 0:
            pa, pb = pa[1:], pb[1:]
        A.append(pa)
        B.append(pb)
        idx.append(idx[-1] + int(m[s]))
    A, B = np.concatenate(A), np.concatenate(B)
    assert len(A) == n and len(B) == n
    return A, B, idx[1:-1]


def find_crest(c, x_prev, half=40.0):
    """前のコマの頂 x_prev から ±half の中で、主な曲線の頂点のうち最も高いもの（計画の読み方 5）。"""
    m = np.abs(c[:, 0] - x_prev) <= half
    ids = np.nonzero(m)[0]
    return int(ids[np.argmax(c[ids, 1])])


def find_lip_tip(c, i_crest):
    """頂から前へ主な曲線をたどり、x が初めて減り始める点（読み方 9）。なければ −1。"""
    dx = np.diff(c[i_crest:, 0])
    neg = np.nonzero(dx < 0)[0]
    return int(i_crest + neg[0]) if len(neg) else -1


# ---------------------------------------------------------------- 表示の形・一番上の水面・船
def taper_weight(xs, taper_s):
    """x の両端の下ろしの重み（x は保存の座標＝x_origin からの距離）。taper_s = (a0, a1, b0, b1)。"""
    a0, a1, b0, b1 = taper_s
    xs = np.asarray(xs, dtype=np.float64)
    w = np.ones_like(xs)
    w = np.where(xs <= a0, 0.0, w)
    w = np.where(xs >= b1, 0.0, w)
    m = (xs > a0) & (xs < a1)
    w = np.where(m, 0.5 - 0.5 * np.cos(math.pi * (xs - a0) / (a1 - a0)), w)
    m = (xs > b0) & (xs < b1)
    w = np.where(m, 0.5 + 0.5 * np.cos(math.pi * (xs - b0) / (b1 - b0)), w)
    return w


def taper_stored(meta):
    return tuple(float(v) - float(meta["x_origin_m"]) for v in meta["taper_m"])


def displayed(curve, taper_s):
    """保存の曲線 (n,2) から、表示の (x 保存, y×重み)。"""
    c = np.asarray(curve, dtype=np.float64)
    return np.stack([c[:, 0], c[:, 1] * taper_weight(c[:, 0], taper_s)], axis=1)


def top_surface(c, xq):
    """鉛直の線 x = xq と折れ線 c の交わりのうち最も高い y。端を含む。鉛直の線分は両端の高い方。交わらなければ nan。
    Unity の RT48BoatMotion.TopSurface と同じ式。"""
    x0, x1, y0, y1 = c[:-1, 0], c[1:, 0], c[:-1, 1], c[1:, 1]
    lo, hi = np.minimum(x0, x1), np.maximum(x0, x1)
    m = (xq >= lo) & (xq <= hi)
    if not m.any():
        return float("nan")
    dx = x1[m] - x0[m]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(dx != 0, (xq - x0[m]) / np.where(dx != 0, dx, 1.0), 0.0)
    y = np.where(dx != 0, y0[m] + s * (y1[m] - y0[m]), np.maximum(y0[m], y1[m]))
    return float(y.max())


def boat_fit(ys):
    ys = np.asarray(ys, dtype=np.float64)
    heave = float(ys.sum() / len(ys))
    slope = float((HULL_DX * (ys - heave)).sum() / (HULL_DX * HULL_DX).sum())
    return heave, math.degrees(math.atan(slope)), slope


def boat_from_curve(curve_stored, seat_x, meta):
    c = displayed(curve_stored, taper_stored(meta))
    xs = seat_x - float(meta["x_origin_m"]) + HULL_DX
    ys = [top_surface(c, x) for x in xs]
    h, p, _ = boat_fit(ys)
    return h, p, ys


# ---------------------------------------------------------------- 読み書き
def pairs_view(pairs_flat, meta):
    P, N = int(meta["pair_count"]), int(meta["n_points"])
    return pairs_flat.reshape(P, 2, N, 2)


def frame_curve(pairs, meta, k):
    """コマ k（0 始まり）の曲線：組 k の A。最後のコマは最後の組の B。"""
    F = int(meta["frame_count"])
    return pairs[k, 0] if k < F - 1 else pairs[F - 2, 1]


def curve_for_state(pairs, st):
    a = pairs[st["pair"], 0].astype(np.float64)
    b = pairs[st["pair"], 1].astype(np.float64)
    return a + (b - a) * st["alpha"]


def boat_at(pairs, meta, t, seat_x, frame_cache=None):
    """時刻 t の船の上下・縦揺れ。補間する組は描いている曲線から、ほかはコマごとの値を時刻で線形に補間。"""
    st = state_at(meta, t)
    if st["interp"]:
        h, p, _ = boat_from_curve(curve_for_state(pairs, st), seat_x, meta)
        return h, p, "curve", st
    if frame_cache is None:
        frame_cache = {}

    def fb(k):
        if k not in frame_cache:
            frame_cache[k] = boat_from_curve(frame_curve(pairs, meta, k).astype(np.float64), seat_x, meta)[:2]
        return frame_cache[k]
    if st["last"]:
        h, p = fb(int(meta["frame_count"]) - 1)
        return h, p, "frame_last", st
    k, w = st["frame"], st["w"]
    h0, p0 = fb(k)
    h1, p1 = fb(k + 1)
    return h0 + (h1 - h0) * w, p0 + (p1 - p0) * w, "frame_lerp", st


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def write_bake(out_dir, meta, pairs, loops):
    """pairs：(P, 2, N, 2) float32。loops：[(frame_index, kind, pts (m,2)), ...]（コマの順）。meta の残りを足して書く。"""
    os.makedirs(out_dir, exist_ok=True)
    pairs = np.ascontiguousarray(pairs, dtype="<f4")
    P, two, N, _ = pairs.shape
    assert two == 2 and N == meta["n_points"] and P == meta["frame_count"] - 1
    pairs.tofile(os.path.join(out_dir, "pairs.bin"))
    F = int(meta["frame_count"])
    loops = sorted(loops, key=lambda e: e[0])
    lf_first = [0] * F
    lf_count = [0] * F
    kinds, pfirst, pcount, pts = [], [], [], []
    acc = 0
    for li, (fi, kind, p) in enumerate(loops):
        if lf_count[fi] == 0:
            lf_first[fi] = li
        lf_count[fi] += 1
        kinds.append(int(kind))
        pfirst.append(acc)
        pcount.append(len(p))
        pts.append(np.asarray(p, dtype="<f4"))
        acc += len(p)
    for fi in range(F):
        if lf_count[fi] == 0:
            lf_first[fi] = len(kinds)
    arr = np.concatenate(pts) if pts else np.zeros((0, 2), "<f4")
    np.ascontiguousarray(arr, dtype="<f4").tofile(os.path.join(out_dir, "loops.bin"))
    meta = dict(meta)
    meta.update({"schema": SCHEMA, "pair_count": P, "loop_frame_first": lf_first, "loop_frame_count": lf_count,
                 "loop_kind": kinds, "loop_point_first": pfirst, "loop_point_count": pcount})
    names = ["pairs.bin", "loops.bin"]
    meta["files_name"] = names
    meta["files_bytes"] = [os.path.getsize(os.path.join(out_dir, n)) for n in names]
    meta["files_sha256"] = [sha256_file(os.path.join(out_dir, n)) for n in names]
    missing = [k for k in META_KEYS if k not in meta]
    assert not missing, missing
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({k: meta[k] for k in META_KEYS}, f, ensure_ascii=False, indent=1)
    return meta


def load_bake(d):
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    pairs = np.fromfile(os.path.join(d, "pairs.bin"), dtype="<f4")
    loops = np.fromfile(os.path.join(d, "loops.bin"), dtype="<f4").reshape(-1, 2)
    return meta, pairs_view(pairs, meta), loops


def loops_of_frame(meta, loops_pts, k):
    out = []
    a, n = meta["loop_frame_first"][k], meta["loop_frame_count"][k]
    for li in range(a, a + n):
        p0, pc = meta["loop_point_first"][li], meta["loop_point_count"][li]
        out.append((meta["loop_kind"][li], loops_pts[p0:p0 + pc].astype(np.float64)))
    return out


# ---------------------------------------------------------------- 交わりと多価の列（合成の元とテストのため）
def segments_intersect_count(c):
    """折れ線 c の線分どうし（隣り合うものを除く）の交わりの数（O(m²)、窓の中の点だけを渡す）。"""
    p, q = c[:-1], c[1:]
    m = len(p)
    if m < 3:
        return 0
    d = q - p
    cnt = 0
    for i in range(m - 2):
        a, b = p[i], q[i]
        P2, Q2 = p[i + 2:], q[i + 2:]
        D2 = d[i + 2:]
        den = d[i, 0] * D2[:, 1] - d[i, 1] * D2[:, 0]
        ok = den != 0
        w = P2 - a
        s = np.where(ok, (w[:, 0] * D2[:, 1] - w[:, 1] * D2[:, 0]) / np.where(ok, den, 1), -1)
        u = np.where(ok, (w[:, 0] * d[i, 1] - w[:, 1] * d[i, 0]) / np.where(ok, den, 1), -1)
        hit = ok & (s > 0) & (s < 1) & (u > 0) & (u < 1)
        cnt += int(hit.sum())
    return cnt


def crossings(c, xq, closed=False):
    """鉛直の線 x = xq と折れ線の交わりの数（端の重なりは半開区間で 1 回に数える）。"""
    if closed:
        c = np.vstack([c, c[:1]])
    x0, x1 = c[:-1, 0], c[1:, 0]
    return int((((x0 <= xq) & (x1 > xq)) | ((x1 <= xq) & (x0 > xq))).sum())
