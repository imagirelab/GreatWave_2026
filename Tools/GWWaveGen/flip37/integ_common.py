# -*- coding: utf-8 -*-
"""FLIP37 組み込みの準備（integration_prep）の共通部。py -3.10（numpy・scipy）。

流体の水面（コマごとの三角形の網目、計算の座標 x＝進む向き・y＝上・z＝峰に沿う向き）を、
作品の主役波の約束（240 行 × 400 列の固定の網目、AS05 の頂点の属性）へ写すための道具。

- 行ごとの切り口：平面 z = 一定 で網目を切り、線分をつないで折れ線にする（slice_mesh_z）。
- 断面の目印（後ろの裾 B・背の足・頂・唇の先・空洞の奥・前の谷・前の裾）を折れ線の上で決め（section_landmarks）、
  列を目印の間の長さで並べ直す（layout_columns：目印どおりの並べ方と一様の並べ方を半分ずつ混ぜる）。
- AS05 の頂点の属性（Unity/Build/Polish/sample04/mat/README.md の 3 節の約束）を作る（sheet_attributes）。
- Unity の座標への置き方は p2_common.place（P2 の比べ方と同じ一様の倍率と回転と平行移動だけ。形は変えない）。

ここで作るものは試作の確かめ用で、作品の場面・材質・素材には触れない。
"""
import os, json, math, hashlib
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/FLIP37/integration_prep"
NU, NV = 400, 240                       # 列（断面を回る向き）、行（峰に沿う向き）。作品の 240 × 400 と同じ
KNOTS_J = np.array([0, 18, 90, 200, 314, 379, 394, 399])   # 目印の列（見本06 R9 の j_B・頂・唇の先・空洞の奥・前の面の下・E と同じ番号）
H0 = 20.753                              # 材質の高さの基準（_BandLam.w）
BANDLAM = (0.056, 0.045, 0.035, 20.753)  # AS05 の _BandLam


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def lam_y(y):
    """帯の周期 λ(y)（AS05Lam と同じ式）。y は Unity のワールドの高さ m。"""
    a, b, c, H = BANDLAM
    t = np.asarray(y, float) / max(H, 1.0)
    e = np.exp(2.0 * np.clip((t - 0.5) / 0.3, -10.0, 10.0))
    ts = 0.5 + 0.3 * (e - 1.0) / (e + 1.0)
    x = (ts - 0.5) / 0.25
    return (b + 0.5 * (c - a) * x + 0.5 * (a - 2.0 * b + c) * x * x) * H


# ---------------------------------------------------------------- 切り口
def tri_zrange(P, tri):
    z = P[tri, 2]
    return z.min(1), z.max(1)


def slice_mesh_z(P, tri, z0, zr=None):
    """網目を平面 z = z0 で切る。戻り：折れ線のリスト [(K,2) の (x, y)]、各々 closed（bool）。
    つながりは辺（頂点の組）で決める。開いた線は端から、閉じた線は任意の点から歩く。"""
    if zr is None:
        zr = tri_zrange(P, tri)
    sel = (zr[0] < z0) & (zr[1] > z0)
    t = tri[sel]
    if len(t) == 0:
        return []
    d = P[:, 2] - z0
    d = np.where(np.abs(d) < 1e-6, 1e-6, d)
    s = d[t] > 0
    e_list = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        e_list.append(s[:, a] != s[:, b])
    E = np.stack(e_list, 1)                       # (m,3) どの辺が切られるか
    ok = E.sum(1) == 2
    t = t[ok]; E = E[ok]
    N = len(P)
    keys = np.zeros((len(t), 2), np.int64)
    k = 0
    cols = []
    for ei, (a, b) in enumerate(((0, 1), (1, 2), (2, 0))):
        va, vb = t[:, a], t[:, b]
        key = np.minimum(va, vb).astype(np.int64) * N + np.maximum(va, vb)
        cols.append(np.where(E[:, ei], key, -1))
    C = np.stack(cols, 1)
    C.sort(1)
    keys = C[:, 1:]                               # 切られる 2 辺（-1 を除く）
    uk, inv = np.unique(keys.ravel(), return_inverse=True)
    inv = inv.reshape(-1, 2)
    va = uk // N; vb = uk % N
    da, db = d[va], d[vb]
    w = da / (da - db)
    pts = P[va] + (P[vb] - P[va]) * w[:, None]
    nn = len(uk)
    nb = -np.ones((nn, 2), np.int64)
    deg = np.zeros(nn, np.int64)
    # 2026-10-06 23:40 追加（R18）：流体の網目に、まれに同じ三角形の重複や 3 枚以上が共有する辺（非多様体）がある（R18 で 1 コマ 0〜3 本、
    # 巻きの段）。同じ組は 1 回だけ使い、3 本目のつながりは捨てる（線がそこで切れるだけ）。R05・P1sweep は該当なし（結果は変わらない）
    inv = np.unique(np.sort(inv, 1), axis=0)
    for i0, i1 in inv:
        if i0 == i1 or deg[i0] >= 2 or deg[i1] >= 2:
            continue
        nb[i0, deg[i0]] = i1; deg[i0] += 1
        nb[i1, deg[i1]] = i0; deg[i1] += 1
    seen = np.zeros(nn, bool)
    out = []
    starts = list(np.where(deg == 1)[0]) + list(np.where(deg == 2)[0])
    for st in starts:
        if seen[st]:
            continue
        chain = [st]; seen[st] = True
        prev, cur = -1, st
        closed = False
        while True:
            n0, n1 = nb[cur]
            nxt = n0 if n0 != prev else n1
            if nxt < 0:
                break
            if seen[nxt]:
                closed = nxt == st
                break
            chain.append(nxt); seen[nxt] = True
            prev, cur = cur, nxt
        out.append((pts[chain][:, :2].copy(), bool(closed and deg[st] == 2)))
    return out


def polyline_len(c):
    return float(np.hypot(*np.diff(c, axis=0).T).sum()) if len(c) > 1 else 0.0


def main_curve(chains):
    """開いた線のうち一番長いもの（箱の後ろの端から前の端まで続く水面）。後ろ（x の小さい端）から前へ向ける。
    戻り：curve、落とした線の数と長さ。"""
    opens = [(polyline_len(c), c) for c, cl in chains if not cl]
    if not opens:
        return None, len(chains), sum(polyline_len(c) for c, _ in chains)
    L, c = max(opens, key=lambda x: x[0])
    if c[0, 0] > c[-1, 0]:
        c = c[::-1]
    dropped = [polyline_len(cc) for cc, _ in chains if cc is not c]
    return c, len(chains) - 1, float(sum(dropped) - 0.0)


def resample(c, ds=0.1):
    seg = np.hypot(*np.diff(c, axis=0).T)
    keep = np.r_[True, seg > 1e-9]
    c = c[keep]
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    n = max(int(s[-1] / ds) + 1, 2)
    si = np.linspace(0, s[-1], n)
    return np.stack([np.interp(si, s, c[:, 0]), np.interp(si, s, c[:, 1])], 1), si


# ---------------------------------------------------------------- 目印と列の並べ方
def _centroid_region(s, f, i0, thr):
    """f が thr 以上の、i0 を含む続いた区間の弧長の重心（重み f − thr）。"""
    n = len(f)
    lo = i0
    while lo - 1 >= 0 and f[lo - 1] >= thr:
        lo -= 1
    hi = i0
    while hi + 1 < n and f[hi + 1] >= thr:
        hi += 1
    w = f[lo:hi + 1] - thr + 1e-9
    return float((s[lo:hi + 1] * w).sum() / w.sum())


def section_landmarks(c, Lb_skirt=30.0, front_search=60.0, smooth_m=None, ds=0.1, version=2):
    """折れ線 c（後ろ→前、(x, y)）の目印の弧長。戻り dict（s_knots は KNOTS_J の各列の弧長）。
    版 2（コマの間で跳ばないように、最小・最大の点ではなく、区間の重心と、傾きのある所での高さの横切りで決める）：
    - なめらかにする幅：線の点の間隔の中央値と 0.6 m の大きいほう（粗い網目で角度が段々になるのを消す）。
    - 頂：高さの柔らかい最大（重み exp((y − y_max)/(0.01 × 高さの幅))）の弧長。
    - 背の足：頂の 60 m 後ろまでの一番低い高さ yb から、頂までの高さの 15 % の高さを、頂から後ろへ最初に横切る点（45 m まで）。
    - 唇の先：頂から前の探す範囲（x が頂 + front_search まで）で、接線の角度（巻きの向き、ほどかない）の柔らかい最小（重み exp((a_min − a)/3°)）
      （張り出しが無ければ前の面の一番急な所。張り出しが育つと唇の先へ移る）。
    - 空洞の奥：唇の先から後で x が一番小さい点（張り出しが無ければ唇の先。列の間隔の下限で唇の先から離す）。
    - 前の谷：空洞の奥から後で、一番低い高さ yf から頂までの高さの 15 % の高さを最初に下へ横切る点（平らな谷の底で跳ばないように）。
    - B＝背の足の 30 m 後ろ、E0＝前の谷の 8 m 先、E＝前の谷の 30 m 先（弧長）。"""
    r, s = resample(c, ds)
    seg = np.hypot(*np.diff(c, axis=0).T)
    h = float(np.median(seg)) if len(seg) else ds
    sm = smooth_m if smooth_m is not None else max(0.6, h)
    k = max(int(round(sm / ds)), 1)
    xs = ndi.gaussian_filter1d(r[:, 0], k, mode="nearest")
    ys = ndi.gaussian_filter1d(r[:, 1], k, mode="nearest")
    n = len(s)
    it = int(np.argmax(ys))
    ytop = float(ys[it])
    i_b0 = max(0, int(np.searchsorted(s, s[it] - 60.0)))
    yb = float(ys[i_b0:it + 1].min())
    fr0 = np.where((np.arange(n) > it) & (xs >= xs[it] + front_search))[0]
    i_end0 = int(fr0[0]) if len(fr0) else n - 1
    yf = float(ys[it:i_end0 + 1].min())
    span = max(ytop - min(yb, yf), 0.5)
    # 頂：高さの柔らかい最大（重み exp((y − y_max)/(0.01 · 高さの幅))。二つの山が同じ高さに近づいても跳ばない）
    wt = np.exp(np.clip((ys - ytop) / (0.01 * span), -50, 0))
    s_top = float((s * wt).sum() / wt.sum())
    i_top = int(np.clip(np.searchsorted(s, s_top), 0, n - 1))
    x_top, y_top = float(np.interp(s_top, s, r[:, 0])), float(np.interp(s_top, s, r[:, 1]))
    # 背の足
    thr_b = yb + 0.15 * max(ytop - yb, 0.5)
    back = np.where(ys[:i_top] <= thr_b)[0]
    if len(back):
        i = int(back[-1])
        # 横切りの点を線形に補う
        y0_, y1_ = ys[i], ys[min(i + 1, n - 1)]
        f = (thr_b - y0_) / (y1_ - y0_) if y1_ != y0_ else 0.0
        s_bf = float(s[i] + np.clip(f, 0, 1) * (s[min(i + 1, n - 1)] - s[i]))
    else:
        s_bf = float(s[i_b0])
    s_bf = max(s_bf, s_top - 45.0, 0.0)
    s_B = max(0.0, s_bf - Lb_skirt)
    # 前の探す範囲
    fr = np.where((np.arange(n) > i_top) & (xs >= x_top + front_search))[0]
    i_end = int(fr[0]) if len(fr) else n - 1
    tx = np.gradient(xs); ty = np.gradient(ys)
    ang = np.unwrap(np.arctan2(ty, tx))
    a = ang[i_top:i_end + 1] - ang[i_top]
    # 唇の先：接線の角度の柔らかい最小（重み exp((a_min − a)/3°)、探す範囲の全体で。急な所が二つあっても跳ばない）
    wa = np.exp(np.clip((a.min() - a) / np.radians(3.0), -50, 0))
    s_tip = float((s[i_top:i_end + 1] * wa).sum() / wa.sum())
    s_tip = max(s_tip, s_top + 0.5)
    i_tip = int(np.clip(np.searchsorted(s, s_tip), i_top + 1, n - 1))
    i_cor = i_tip + int(np.argmin(xs[i_tip:i_end + 1]))
    s_cor = float(s[i_cor])
    thr_f = yf + 0.15 * max(ytop - yf, 0.5)
    dn = np.where(ys[i_cor:i_end + 1] <= thr_f)[0]
    if len(dn):
        i = i_cor + int(dn[0])
        y0_, y1_ = ys[max(i - 1, 0)], ys[i]
        f = (y0_ - thr_f) / (y0_ - y1_) if y0_ != y1_ else 1.0
        s_fb = float(s[max(i - 1, 0)] + np.clip(f, 0, 1) * (s[i] - s[max(i - 1, 0)]))
    else:
        s_fb = float(s[i_cor + int(np.argmin(ys[i_cor:i_end + 1]))])
    s_fb = max(s_fb, s_cor)
    s_E0 = min(s_fb + 8.0, float(s[-1]))
    s_E = min(s_fb + 30.0, float(s[-1]))
    kn = np.array([s_B, s_bf, s_top, s_tip, s_cor, s_fb, s_E0, s_E], float)
    return {"s_knots": kn, "s": s, "r": r, "x_top": x_top, "y_top": y_top, "min_angle_deg": float(np.degrees(a.min())),
            "overhang": bool(xs[i_cor] < xs[i_tip] - 0.5), "smooth_m": sm}


def fix_knots(kn, eps=0.06):
    """目印の弧長を前へ単調にする（列 1 つあたり eps m 以上）。"""
    kn = kn.copy()
    for i in range(1, len(kn)):
        kn[i] = max(kn[i], kn[i - 1] + eps * (KNOTS_J[i] - KNOTS_J[i - 1]))
    return kn


def layout_columns(kn, alpha=0.5):
    j = np.arange(NU, dtype=float)
    s_land = np.interp(j, KNOTS_J, kn)
    s_uni = kn[0] + (kn[-1] - kn[0]) * j / (NU - 1)
    return alpha * s_land + (1 - alpha) * s_uni


def sample_curve(r, s, sj):
    sj = np.clip(sj, s[0], s[-1])
    return np.stack([np.interp(sj, s, r[:, 0]), np.interp(sj, s, r[:, 1])], 1)


# ---------------------------------------------------------------- 1 コマの網目 → 240 × 400
def frame_rows(P, tri, zrows):
    """1 コマの網目を行の平面で切り、行ごとの目印を出す。戻り：rows（行ごとの dict か None）、K（頂からの弧長の目印、行の向きに埋めた）。"""
    zr = tri_zrange(P, tri)
    rows = []
    for z0 in zrows:
        ch = slice_mesh_z(P, tri, z0, zr)
        c, ndrop, Ldrop = main_curve(ch)
        if c is None or polyline_len(c) < 20:
            rows.append(None); continue
        lm = section_landmarks(c)
        lm["ndrop"] = ndrop; lm["Ldrop"] = Ldrop
        rows.append(lm)
    ok = np.array([r is not None for r in rows])
    if not ok.any():
        raise RuntimeError("どの行も切れなかった")
    K = np.zeros((len(rows), len(KNOTS_J)))
    for i, r in enumerate(rows):
        if r is not None:
            K[i] = r["s_knots"] - r["s_knots"][2]
    idx = np.where(ok)[0]
    for k in range(len(KNOTS_J)):
        K[:, k] = np.interp(np.arange(len(rows)), idx, K[idx, k])
    return rows, K


def build_sheet(rows, K, zrows, row_smooth=2.0, alpha=1.0):
    """行ごとの目印 K（頂からの弧長。行と時間の向きにならした後のもの）で 400 列へ並べる。
    戻り：G（NV, NU, 3）の計算の座標、info。切れない行は近い行の線を使う。"""
    ok = np.array([r is not None for r in rows])
    idx = np.where(ok)[0]
    if row_smooth > 0:
        K = ndi.gaussian_filter1d(K, row_smooth, axis=0, mode="nearest")
    G = np.zeros((len(rows), NU, 3))
    Sj = np.zeros((len(rows), NU))
    info = {"ok": ok, "K": K, "y_top": np.full(len(rows), np.nan), "x_top": np.full(len(rows), np.nan),
            "overhang": np.zeros(len(rows), bool), "ndrop": np.zeros(len(rows), int), "Ldrop": np.zeros(len(rows)),
            "min_angle_deg": np.full(len(rows), np.nan), "s_top": np.zeros(len(rows))}
    for i, r in enumerate(rows):
        rr = r if r is not None else rows[idx[np.argmin(np.abs(idx - i))]]
        kn = fix_knots(K[i] + rr["s_knots"][2])
        kn = np.clip(kn, rr["s"][0], rr["s"][-1])
        kn = fix_knots(kn, eps=1e-4)
        sj = layout_columns(kn, alpha)
        xy = sample_curve(rr["r"], rr["s"], sj)
        G[i, :, 0] = xy[:, 0]; G[i, :, 1] = xy[:, 1]; G[i, :, 2] = zrows[i]
        Sj[i] = sj - kn[2]
        info["y_top"][i] = rr["y_top"]; info["x_top"][i] = rr["x_top"]; info["overhang"][i] = rr["overhang"]
        info["ndrop"][i] = rr.get("ndrop", 0); info["Ldrop"][i] = rr.get("Ldrop", 0.0)
        info["min_angle_deg"][i] = rr["min_angle_deg"]; info["s_top"][i] = kn[2]
    info["u"] = Sj
    return G, info


def convert_frame_sheet(P, tri, zrows, row_smooth=2.0, alpha=1.0):
    """1 コマだけで並べる（時間の向きにならさない）。"""
    rows, K = frame_rows(P, tri, zrows)
    return build_sheet(rows, K, zrows, row_smooth, alpha)


def grid_triangles(nv=NV, nu=NU):
    r, c = np.meshgrid(np.arange(nv - 1), np.arange(nu - 1), indexing="ij")
    a = (r * nu + c).ravel(); b = a + 1; d = a + nu; e = d + 1
    return np.concatenate([np.stack([a, d, b], 1), np.stack([b, d, e], 1)]).astype(np.int64)


def grid_normals(G):
    """格子の法線（行と列の差分の外積）。頂の法線が上を向くように符号を決める。"""
    dj = np.gradient(G, axis=1)
    dr = np.gradient(G, axis=0)
    n = np.cross(dj, dr)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    sgn = np.sign(np.nanmean(n[:, 90, 1]))
    return n * (sgn if sgn != 0 else 1.0)


def vertex_normals(P, tri):
    fn = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    vn = np.zeros_like(P)
    for k in range(3):
        np.add.at(vn, tri[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    if np.nanmean(vn[:, 1]) < 0:
        vn = -vn
    return vn


# ---------------------------------------------------------------- 材質の属性（AS05、静止のメッシュの道 _AS03Src = 1）
def white_rule(u, F, info, w, H=H0):
    """試作の白の印（作品の白の区域の設計ではない。README 3 節の約束の形だけ合わせた仮の決め方）：
    白＝頂の少し後ろ（u > −(0.07 H + 揺れ)）から唇の先の少し先まで。張り出しの無い行は頂の前 0.12 H まで。
    whiteSD＝白の境までの断面に沿った符号付きの距離（m、+ が白）。whiteOn＝その行の前の面が 60° を超えて急になったか。"""
    nv, nu = u.shape
    wob = 0.6 * np.sin(w / 4.3) + 0.4 * np.sin(w / 1.7 + 1.3)
    ub = -(0.07 * H + 0.5 + wob)
    tip_u = info["K"][:, 3] - info["K"][:, 2]
    uf = np.where(info["overhang"], tip_u + 1.5, 0.12 * H)[:, None] + 0.3 * wob
    sd = np.minimum(u - ub, uf - u)
    on = (info["min_angle_deg"] < -60.0)[:, None] & np.ones((1, nu), bool)
    return sd, on.astype(float)


def sheet_attributes(info, zrows, zc):
    """240 × 400 の行の情報から、断面の座標 u（頂から前へ +、m）・F（背の足 0 → 頂 2 → 前の谷 4、裾は外へ）・w（峰に沿う m）を作る。"""
    u = info["u"]
    K = info["K"]
    nv, nu = u.shape
    s_bf = K[:, 1][:, None] - K[:, 2][:, None]
    s_fb = K[:, 5][:, None] - K[:, 2][:, None]
    F = np.where(u < 0, 2.0 * (u - s_bf) / np.maximum(-s_bf, 1e-3), 2.0 + 2.0 * u / np.maximum(s_fb, 1e-3))
    F = np.where(u < s_bf, (u - s_bf) / 10.0, F)
    F = np.where(u > s_fb, 4.0 + (u - s_fb) / 10.0, F)
    w = np.broadcast_to((np.asarray(zrows, float) - zc)[:, None], (nv, nu)).copy()
    return u, F, w


def as05_channels(Gu, Nu, u, F, w, ez, hrow, whiteSD, whiteOn, row=None, col=None):
    """AS05 の静止のメッシュの道のチャンネル（平らな配列）。ez＝Unity の座標での峰に沿う向き（w の向き）。"""
    P = Gu.reshape(-1, 3); N = Nu.reshape(-1, 3)
    n_ez = N @ ez
    gw = np.sqrt(np.clip(1.0 - n_ez ** 2, 1e-4, 1.0))
    lam = lam_y(P[:, 1])
    gq = gw / lam
    q = w.reshape(-1) / lam
    Lq = -np.log2(gw)
    uv3 = np.stack([F.reshape(-1), np.zeros(len(P)), u.reshape(-1), w.reshape(-1)], 1)
    uv4 = np.stack([gq, hrow.reshape(-1), Lq, q], 1)
    uv5 = np.stack([np.ones(len(P)), np.ones(len(P)), whiteSD.reshape(-1), np.zeros(len(P))], 1)
    rr = row.reshape(-1) if row is not None else np.zeros(len(P))
    cc = col.reshape(-1) if col is not None else np.zeros(len(P))
    uv6 = np.stack([rr, cc, lam, whiteOn.reshape(-1)], 1)
    return {"position": P, "normal": N, "uv3": uv3, "uv4": uv4, "uv5": uv5, "uv6": uv6}


def smooth_grid(A, sig_rows, sig_cols):
    return ndi.gaussian_filter(A, (sig_rows, sig_cols), mode="nearest")


def write_static_mesh(path_json, ch, tri, extra=None):
    """書式 GreatWave.AS03.static_mesh/1（AS03StaticMesh.cs と同じ：チャンネルごとの平面の float32、続いて uint32 の三角形）。"""
    order = [("position", 3), ("normal", 3), ("uv3", 4), ("uv4", 4), ("uv5", 4), ("uv6", 4)]
    binp = path_json[:-5] + ".bin"
    with open(binp, "wb") as f:
        for name, k in order:
            a = np.ascontiguousarray(ch[name], dtype=np.float32)
            assert a.shape == (len(ch["position"]), k), (name, a.shape)
            f.write(a.tobytes())
        f.write(np.ascontiguousarray(tri, dtype=np.uint32).tobytes())
    meta = {"schema": "GreatWave.AS03.static_mesh/1", "vertices": int(len(ch["position"])), "triangles": int(len(tri)),
            "channels": [[n, k] for n, k in order], "bin": os.path.basename(binp), "sha256": sha256(binp)}
    if extra:
        meta.update(extra)
    json.dump(meta, open(path_json, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return os.path.getsize(binp)


# ---------------------------------------------------------------- 当てはまりの測り
def point_tri_dist(p, a, b, c):
    """点 p（n,3）と三角形 (a,b,c)（n,3 ずつ）の距離（Ericson の最近点）。"""
    ab = b - a; ac = c - a; ap = p - a
    d1 = (ab * ap).sum(1); d2 = (ac * ap).sum(1)
    bp = p - b; d3 = (ab * bp).sum(1); d4 = (ac * bp).sum(1)
    cp = p - c; d5 = (ab * cp).sum(1); d6 = (ac * cp).sum(1)
    vc = d1 * d4 - d3 * d2; vb = d5 * d2 - d1 * d6; va = d3 * d6 - d5 * d4
    den = np.where(np.abs(va + vb + vc) < 1e-20, 1e-20, va + vb + vc)
    v = vb / den; w = vc / den
    q = a + ab * v[:, None] + ac * w[:, None]
    # 縁と頂点の場合
    def seg(p, x, y):
        d = y - x; t = np.clip(((p - x) * d).sum(1) / np.maximum((d * d).sum(1), 1e-20), 0, 1)
        return x + d * t[:, None]
    inside = (va >= 0) & (vb >= 0) & (vc >= 0)
    cands = [np.where(inside[:, None], q, np.inf), seg(p, a, b), seg(p, b, c), seg(p, c, a)]
    dd = np.stack([np.linalg.norm(p - x, axis=1) for x in cands], 1)
    return np.nan_to_num(dd, nan=np.inf).min(1)


def surf_distance(Q, P, tri, k=8, tree=None):
    """点 Q から網目 (P, tri) の面までの距離（近い頂点 k 個に付く三角形の中で一番近いもの）。"""
    tree = tree or cKDTree(P)
    _, nn = tree.query(Q, k=k)
    # 頂点 → 三角形の対応（CSR）
    m = len(tri)
    vt = np.repeat(np.arange(m), 3); vv = tri.ravel()
    order = np.argsort(vv, kind="stable")
    vv = vv[order]; vt = vt[order]
    start = np.searchsorted(vv, np.arange(len(P) + 1))
    best = np.full(len(Q), np.inf)
    maxdeg = int(np.diff(start).max()) if len(P) else 0
    for kk in range(k):
        v = nn[:, kk]
        for dgi in range(maxdeg):
            idx = start[v] + dgi
            okm = idx < start[v + 1]
            if not okm.any():
                break
            ti = vt[np.where(okm, idx, 0)]
            t = tri[ti]
            d = point_tri_dist(Q, P[t[:, 0]], P[t[:, 1]], P[t[:, 2]])
            best = np.where(okm, np.minimum(best, d), best)
    return best
