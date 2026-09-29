# -*- coding: utf-8 -*-
"""設計31 白の部：主役波のシートの白の出現（T_white）を、設計31 の「発生位置と時刻」として表にし、
102（白が 0 から連続して現れ、終態の白の内側）を頂点の空間で測り、Unity の確かめ用の印（粒子の枠の書式）を書く。

入力（読むだけ。どれも SHA-256 を記録する）：
  - 主役波の動きのパッケージ Unity/Build/Design/28R01F/F_final/art_on（ds27_keypose.json・ds27_pos_rgba16.bin・ds27_pos_lo_rgba8.bin・ds27_twhite_r32f.bin）
  - 時間曲線 Unity/Build/Design/28R01F/F_final/timewarp_F_final.json（t → τ、240 Hz の表、線形補間。DS27TimeWarp.TauAt と同じ）
  - 29修正01 の色面（K*′ へ焼き直した色区の符号付き距離 af28r01_uvsdf_a45.bin と列・行の UV の表 af28r01_uvwarp_a45.json）
出力（Git 対象外、Unity/Build/Design/31/white/）：
  - ds31_white_onset.json ＋ ds31_white_onset_f32.bin：発生の表。頂点ごと（T_white が有限で、終態の色区が白のもの）に
    行・列・T_white（τ）・t_white（体験の時刻）・その時のワールドの位置・シートの速度（ワールド、m/s、τ の秒あたり）・区間の番号・t* の法線。
  - ds31_marks_born.json/.bin：「いま白くなった所」の印（30 Hz のコマごと、白くなって 0.25 s 以内の頂点。最大 3000、赤）。
  - ds31_marks_trace.json/.bin：移流の印（層別に選んだ 600 頂点。白くなった後はシートの頂点に付いて動く。朱）。
    粒子の枠の書式 GreatWave.DS31.particles/1：float32 のコマ × 数 × 4（x, y, z, 半径。半径 0 は描かない）、ワールドの m。
  - ds31_white_numpy.json：102 の頂点の空間の測り（白くなった頂点の割合と世界の面積の 30 Hz の増分、最初の白、終態の白の外の白 0 の確かめ）。
座標：ワールド = O(τ) + 局所（主役波の GameObject は単位の変換。設計30 の報告の wave27Transform）。
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
PKG = REPO + "/Unity/Build/Design/28R01F/F_final/art_on"
WARP = REPO + "/Unity/Build/Design/28R01F/F_final/timewarp_F_final.json"
SDF = REPO + "/Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin"
UVW = REPO + "/Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json"
OUT = REPO + "/Unity/Build/Design/31/white"
FPS = 30
T_END = 14.0
T_STAR = 12.0
NEVER = 1e8


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


class Pkg:
    """DS27 の keypose（精度の層つき）を numpy の Hermite で読む（DS27KeyposeCore.cginc と同じ式）。"""

    def __init__(self, d):
        self.meta = json.load(open(d + "/ds27_keypose.json", encoding="utf-8"))
        m = self.meta
        self.L, self.R, self.C = m["layers"], m["rows"], m["cols"]
        self.n = self.R * self.C
        self.kt = np.array(m["knot_tau"], dtype=np.float64)
        self.bmin = np.array(m["bbox_min"], dtype=np.float64)
        self.bsz = np.array(m["bbox_size"], dtype=np.float64)
        hi = np.fromfile(d + "/" + m["pos_file"], dtype="<u2").reshape(self.L, self.n, 4)[:, :, :3]
        lo = np.fromfile(d + "/" + m["pos_lo_file"], dtype=np.uint8).reshape(self.L, self.n, 4)[:, :, :3]
        # 位置 = bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size（float32 で持つ。精度の層の約 7 µm には float32 で足りる）
        self.P = (self.bmin + (hi.astype(np.float64) + lo.astype(np.float64) / 255.0 - 0.5) / 65535.0 * self.bsz).astype(np.float32)
        del hi, lo
        fr = m["frame"]
        self.ftau = np.array(fr["tau"], dtype=np.float64)
        self.forg = np.array(fr["origin"], dtype=np.float64)
        self.tw = np.fromfile(d + "/" + m["twhite_file"], dtype="<f4").astype(np.float64)

    def origin(self, tau):
        tau = np.atleast_1d(tau)
        return np.stack([np.interp(tau, self.ftau, self.forg[:, k]) for k in range(3)], -1)

    def dorigin(self, tau, h=1e-3):
        return (self.origin(tau + h) - self.origin(tau - h)) / (2 * h)

    def _slope(self, i, idx):
        L = self.L
        a, b = max(i - 1, 0), min(i + 1, L - 1)
        return (self.P[b, idx].astype(np.float64) - self.P[a, idx]) / (self.kt[b] - self.kt[a])

    def eval(self, tau, idx=None, vel=False):
        """1 つの τ で、頂点 idx（None は全部）の局所の位置（と dP/dτ）。"""
        if idx is None:
            idx = slice(None)
        kt = self.kt
        if tau <= kt[0]:
            p = self.P[0, idx].astype(np.float64)
            return (p, np.zeros_like(p)) if vel else p
        if tau >= kt[-1]:
            p = self.P[-1, idx].astype(np.float64)
            return (p, np.zeros_like(p)) if vel else p
        i = int(np.searchsorted(kt, tau, side="right") - 1)
        i = min(max(i, 0), self.L - 2)
        h = kt[i + 1] - kt[i]
        s = (tau - kt[i]) / h
        p0 = self.P[i, idx].astype(np.float64)
        p1 = self.P[i + 1, idx].astype(np.float64)
        m0 = self._slope(i, idx)
        m1 = self._slope(i + 1, idx)
        s2, s3 = s * s, s * s * s
        h00, h10, h01, h11 = 2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2
        p = h00 * p0 + h10 * h * m0 + h01 * p1 + h11 * h * m1
        if not vel:
            return p
        d00, d10, d01, d11 = 6 * s2 - 6 * s, 3 * s2 - 4 * s + 1, -6 * s2 + 6 * s, 3 * s2 - 2 * s
        v = (d00 * p0 + d10 * h * m0 + d01 * p1 + d11 * h * m1) / h
        return p, v


def load_warp(p):
    w = json.load(open(p, encoding="utf-8"))
    return np.array(w["t"], dtype=np.float64), np.array(w["tau"], dtype=np.float64)


def tau_at(t, wt, wtau):
    return np.interp(t, wt, wtau)


def t_of_tau(tau, wt, wtau):
    """τ → t（τ(t) は単調に増える所だけを使う。t* の後の保持は除く）。"""
    k = int(np.argmax(wtau >= wtau.max() - 1e-12))
    return np.interp(tau, wtau[: k + 1], wt[: k + 1])


def tri_index(R, C):
    r, c = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    a = (r * C + c).ravel()
    b = ((r + 1) * C + c).ravel()
    cc = (r * C + c + 1).ravel()
    d = ((r + 1) * C + c + 1).ravel()
    # (r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1)（設計27 と同じ割り方）
    return np.concatenate([np.stack([a, b, cc], 1), np.stack([cc, b, d], 1)])


def tri_area(P, T):
    e1 = P[T[:, 1]] - P[T[:, 0]]
    e2 = P[T[:, 2]] - P[T[:, 0]]
    return 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)


def vertex_class(R, C):
    """29修正01 の色面：頂点の UV3 = (uWarp[列], vWarp[行]) の最も近いテクセルの色区（符号付き距離の最大の通り道。0 白・1 淡い水色・2 藍中・3 藍濃）。
    シェーダーは画素ごとに双線形で読むので、頂点の色区は目安（境の 1 テクセルで食い違いうる）。"""
    w = json.load(open(UVW, encoding="utf-8"))
    u = np.array(w["uWarp"], dtype=np.float64)
    v = np.array(w["vWarp"], dtype=np.float64)
    S = 4096
    sdf = np.fromfile(SDF, dtype=np.uint8).reshape(S, S, 4)
    x = np.clip(np.round(u * S - 0.5).astype(int), 0, S - 1)
    y = np.clip(np.round(v * S - 0.5).astype(int), 0, S - 1)
    X, Y = np.meshgrid(x, y)   # 行 × 列
    d = sdf[Y, X].astype(np.int16)   # R × C × 4
    return np.argmax(d, axis=-1).astype(np.int8).ravel(), d.reshape(-1, 4)


_TEX = {}


def texel_setup(R, C):
    """終態の色区が白のテクセル（本体の列 18〜394 の中）ごとの、UV の格子の四角の番号と四角の中の位置。"""
    if _TEX:
        return _TEX
    w = json.load(open(UVW, encoding="utf-8"))
    uW = np.array(w["uWarp"], dtype=np.float64); vW = np.array(w["vWarp"], dtype=np.float64)
    S = 4096
    sdf = np.fromfile(SDF, dtype=np.uint8).reshape(S, S, 4)
    tcls = np.argmax(sdf, axis=-1).astype(np.int8)   # [y, x]（y = v·S、LoadRawTextureData の並び）
    del sdf
    uc = (np.arange(S) + 0.5) / S
    ci = np.clip(np.searchsorted(uW, uc, side="right") - 1, 0, C - 2)
    cs = np.clip((uc - uW[ci]) / np.maximum(uW[ci + 1] - uW[ci], 1e-12), 0, 1)
    ri = np.clip(np.searchsorted(vW, uc, side="right") - 1, 0, R - 2)
    rs = np.clip((uc - vW[ri]) / np.maximum(vW[ri + 1] - vW[ri], 1e-12), 0, 1)
    inside_u = (uc >= uW[0]) & (uc <= uW[-1]); inside_v = (uc >= vW[0]) & (uc <= vW[-1])
    ys, xs = np.nonzero((tcls == 0) & inside_v[:, None] & inside_u[None, :] & (ci[None, :] >= 18) & (ci[None, :] + 1 <= 394))
    _TEX.update(rr=ri[ys], cc=ci[xs], q=rs[ys], s=cs[xs])
    return _TEX


def texel_T(TW, fin, R, C):
    """102：テクセルの空間（美術優先31 と同じ読み）。終態の色区が白のテクセルごとに、シェーダーと同じ三角形の線形補間で T_white を求める
    （UV3 は列の表 uWarp・行の表 vWarp の直積なので、UV の格子は直交格子）。t* まで白にならない頂点（行 0・1・239）は、シェーダーでは τ + 1 に
    置き換わる（その三角形は t* までほぼ白くならない）。ここでは +∞ として数える。戻り値：並べた T、テクセルの数、t* まで白にならない数"""
    X = texel_setup(R, C)
    rr, cc_, q, s = X["rr"], X["cc"], X["q"], X["s"]
    Tg = np.where(fin, TW, np.inf).reshape(R, C)
    T00, T01, T10, T11 = Tg[rr, cc_], Tg[rr, cc_ + 1], Tg[rr + 1, cc_], Tg[rr + 1, cc_ + 1]
    low = s + q <= 1
    with np.errstate(invalid="ignore"):
        Tt = np.where(low, T00 + s * (T01 - T00) + q * (T10 - T00), T11 + (1 - s) * (T10 - T11) + (1 - q) * (T01 - T11))
    Tt = np.where(np.isnan(Tt), np.inf, Tt)
    return np.sort(Tt), len(Tt), int(np.isinf(Tt).sum())


def rate_cap(TW, fin, R, C, frames_t, frames_tau, wt, wtau, cap):
    """名前の付いた美術の誘導 ds31_white_rate_cap：白くなるテクセルの割合の 30 Hz の 1 コマの増分を cap 以下にする、T_white の単調な付け替え。
    F_k（今の割合）から後ろ向きに G_k = max(F_k, G_{k+1} − cap) を作り（G ≥ F：白は早まるだけで遅れない）、各値の T を
    t′ = G⁻¹(F(t(T))) → T′ = τ(t′) へ移す。T の順番（白の広がる順と場所）は変わらない。"""
    Ts, ntex, _ = texel_T(TW, fin, R, C)
    F = np.searchsorted(Ts, frames_tau, side="right") / ntex
    G = F.copy()
    for k in range(len(F) - 2, -1, -1):
        G[k] = max(F[k], G[k + 1] - cap)
    # 値ごとの分位（テクセルの中での順位）→ G の逆（区分線形、G の平らな所は最初の時刻）
    fv = np.searchsorted(Ts, TW[fin], side="right") / ntex
    # G は単調非減少。G の値が同じ区間は最初のコマを取る
    Gu, first = np.unique(G, return_index=True)
    tu = frames_t[first]
    t_new = np.interp(fv, Gu, tu)
    t_old = t_of_tau(TW[fin], wt, wtau)
    # 誘導が要らない所（G = F の所）は元の時刻のまま（区分線形の逆の丸めで動かさない）
    keep = np.interp(t_old, frames_t, G - F) <= 1e-12
    t_new = np.where(keep, t_old, np.minimum(t_new, t_old))
    TWn = TW.copy()
    TWn[fin] = np.interp(t_new, wt, wtau)
    TWn[fin] = np.minimum(TWn[fin], TW[fin])
    shift = t_old - t_new
    return TWn, {"cap": cap, "frames_changed": int((G - F > 1e-12).sum()), "vertices_moved": int((np.abs(TWn[fin] - TW[fin]) > 1e-9).sum()),
                 "t_shift_max_s": float(shift.max()), "tau_shift_max_s": float((TW[fin] - TWn[fin]).max()),
                 "window_t": [float(frames_t[np.argmax(G - F > 1e-12)]), float(frames_t[len(G) - 1 - np.argmax((G - F > 1e-12)[::-1])])] if (G - F > 1e-12).any() else None}


def write_particles(path, frames, colour, note, extra=None):
    """粒子の枠の書式（GreatWave.DS31.particles/1）。frames：K × N × 4 の float32（x, y, z, 半径）。"""
    frames = np.ascontiguousarray(frames, dtype="<f4")
    K, N, _ = frames.shape
    binp = path + ".bin"
    frames.tofile(binp)
    meta = {
        "schema": "GreatWave.DS31.particles/1",
        "frames": int(K), "hz": FPS, "t0": 0.0, "count": int(N),
        "file": os.path.basename(binp), "sha256": sha(binp), "bytes": os.path.getsize(binp),
        "layout_ja": "float32 リトルエンディアン、コマ × 数 × 4（x, y, z, 半径）。ワールドの m。半径 0 は描かない。コマ k は体験の時刻 t = t0 + k/hz（t ≥ 12 s は t* の静止）",
        "colour": colour, "note_ja": note,
    }
    if extra:
        meta.update(extra)
    json.dump(meta, open(path + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--born-window", type=float, default=0.25, help="「いま白くなった所」の印を出す長さ（体験の秒）")
    ap.add_argument("--born-max", type=int, default=3000)
    ap.add_argument("--trace-n", type=int, default=600)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--rate-cap", type=float, default=0.018, help="ds31_white_rate_cap：30 Hz の 1 コマで白くなるテクセルの割合の上限（0 で切る）")
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    log = {}
    pk = Pkg(PKG)
    R, C, n = pk.R, pk.C, pk.n
    wt, wtau = load_warp(WARP)
    frames_t = np.arange(int(round(T_END * FPS)) + 1) / FPS
    frames_tau = tau_at(frames_t, wt, wtau)
    K = len(frames_t)

    TW0 = pk.tw
    fin = TW0 < NEVER
    before = {}
    Ts0, ntex0, _ = texel_T(TW0, fin, R, C)
    f0 = np.searchsorted(Ts0, frames_tau, side="right") / ntex0
    before["texel_fraction_max_increment_per_frame"] = float(np.diff(f0).max())
    if a.rate_cap > 0:
        TW, capinfo = rate_cap(TW0, fin, R, C, frames_t, frames_tau, wt, wtau, a.rate_cap)
        capinfo["before"] = before
        TW.astype("<f4").tofile(OUT + "/ds31_twhite_r32f.bin")
        capinfo["file"] = "ds31_twhite_r32f.bin"; capinfo["sha256"] = sha(OUT + "/ds31_twhite_r32f.bin")
    else:
        TW, capinfo = TW0, None
    cls, _ = vertex_class(R, C)
    white_final = cls == 0
    rows = np.repeat(np.arange(R), C)
    cols = np.tile(np.arange(C), R)
    # 設計30 の描画は本体の列 18〜394 だけ（余白は near の接続帯が置き換える）
    body = (cols >= 18) & (cols <= 394)
    onset = fin & white_final & body
    log["vertices"] = int(n)
    log["twhite_finite"] = int(fin.sum())
    log["class_white_vertices"] = int(white_final.sum())
    log["class_white_body"] = int((white_final & body).sum())
    log["onset_vertices"] = int(onset.sum())
    log["class_white_never_white"] = int((white_final & body & ~fin).sum())
    log["class_white_never_white_rows"] = sorted(set(int(x) for x in rows[white_final & body & ~fin]))

    # 区間：行ごとの t* の頂（本体の列の中で最も高い頂点）と、K*′ の目印（j_tip 200、j_corner 314、j_E 394）
    kst = pk.meta["kstar"]
    j_tip = int(kst["j_tip"]); j_corner = int(kst["landmarks"]["j_corner"]); j_E = int(kst["landmarks"]["j_E"])
    Pst = pk.P[-1].astype(np.float64)
    Yst = Pst[:, 1].reshape(R, C)
    j_top = np.argmax(np.where((np.arange(C) >= 18) & (np.arange(C) <= j_tip), Yst, -1e9), axis=1)
    region = np.zeros(n, dtype=np.int8)   # 0 背面、1 唇の上面、2 唇の下面、3 内壁
    jt = j_top[rows]
    region[(cols >= jt) & (cols < j_tip)] = 1
    region[(cols >= j_tip) & (cols < j_corner)] = 2
    region[(cols >= j_corner)] = 3
    reg_names = ["背面（頂より後ろ）", "唇の上面（頂 → 唇先）", "唇の下面（唇先 → 角）", "内壁（角 → 前の足）"]

    # ---- 発生の表（頂点ごと、T_white の時の位置と速度）
    idx = np.where(onset)[0]
    order = np.argsort(TW[idx], kind="stable")
    idx = idx[order]
    tw_on = TW[idx]
    t_on = t_of_tau(tw_on, wt, wtau)
    pos = np.zeros((len(idx), 3)); vel = np.zeros((len(idx), 3))
    # τ ごとにまとめて評価する（T_white は 0.001 s 刻みに丸めてから同じ値をまとめる。位置の差は ≤ 速さ × 0.0005 s）
    key = np.round(tw_on, 3)
    uk, inv = np.unique(key, return_inverse=True)
    for g, tv in enumerate(uk):
        sel = np.where(inv == g)[0]
        p, v = pk.eval(float(tv), idx[sel], vel=True)
        o = pk.origin(float(tv))[0]
        do = pk.dorigin(float(tv))[0]
        pos[sel] = p + o
        vel[sel] = v + do
    # t* の法線（格子の隣の差の外積。+y の約束の向き）
    Pg = Pst.reshape(R, C, 3)
    du = np.gradient(Pg, axis=1)
    dv = np.gradient(Pg, axis=0)
    nrm = np.cross(dv, du)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-12)
    nrm = nrm.reshape(-1, 3)
    rec = np.zeros((len(idx), 15), dtype="<f4")
    rec[:, 0] = rows[idx]; rec[:, 1] = cols[idx]; rec[:, 2] = tw_on; rec[:, 3] = t_on
    rec[:, 4:7] = pos; rec[:, 7:10] = vel; rec[:, 10] = region[idx]
    rec[:, 11:14] = nrm[idx]; rec[:, 14] = idx
    rec.tofile(OUT + "/ds31_white_onset_f32.bin")
    spd = np.linalg.norm(vel, axis=1)
    reg_sum = {}
    for r_ in range(4):
        s_ = region[idx] == r_
        if s_.any():
            reg_sum[str(r_)] = {"name_ja": reg_names[r_], "vertices": int(s_.sum()),
                                "tau_first": float(tw_on[s_].min()), "tau_last": float(tw_on[s_].max()),
                                "t_first": float(t_on[s_].min()), "t_last": float(t_on[s_].max()),
                                "speed_median_mps": float(np.median(spd[s_])), "speed_p95_mps": float(np.percentile(spd[s_], 95))}
    onset_meta = {
        "schema": "GreatWave.DS31.white_onset/1",
        "number_ja": "設計31 白の部：白の出現（T_white）を設計31 の発生位置と時刻にした表",
        "file": "ds31_white_onset_f32.bin", "sha256": sha(OUT + "/ds31_white_onset_f32.bin"),
        "records": int(len(idx)), "fields": ["row", "col", "tau_white", "t_white", "x", "y", "z", "vx", "vy", "vz", "region", "nx", "ny", "nz", "vertex"],
        "layout_ja": "float32 リトルエンディアン、記録 × 15。T_white の早い順。位置はワールド（m）、速度はワールドの m/s（τ の秒あたり、波の枠の動きを含む）、法線は t* の格子の法線（+y の約束）。region：0 背面・1 唇の上面・2 唇の下面・3 内壁",
        "selection_ja": "T_white が有限（t* までに白になる）かつ 29修正01 の色面で頂点の色区が白、かつ設計30 で描く本体の列 18〜394 の頂点",
        "regions": reg_sum,
        "j_top_per_row_range": [int(j_top[2:239].min()), int(j_top[2:239].max())],
        "landmarks": {"j_tip": j_tip, "j_corner": j_corner, "j_E": j_E},
        "inputs": {"package": PKG, "pos_sha256": pk.meta["pos_sha256"], "pos_lo_sha256": pk.meta["pos_lo_sha256"],
                   "twhite_sha256": pk.meta["twhite_sha256"], "warp": WARP, "warp_sha256": sha(WARP),
                   "sdf": SDF, "sdf_sha256": sha(SDF), "uvwarp": UVW, "uvwarp_sha256": sha(UVW)},
    }
    json.dump(onset_meta, open(OUT + "/ds31_white_onset.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 102：頂点の空間の連続（30 Hz）。白 = T_white ≤ τ（シェーダーの頂点の旗と同じ）。面積は三角形の面積 × 白の頂点の割合（シェーダーの線形補間の近さ）
    Tri = tri_index(R, C)
    tri_body = (cols[Tri[:, 0]] >= 18) & (cols[Tri[:, 2]] <= 394) & (cols[Tri[:, 1]] >= 18)
    Tri = Tri[tri_body]
    elig = onset.astype(np.float64)   # 終態の白の頂点
    wcount = np.zeros(K); warea = np.zeros(K); outside = np.zeros(K, dtype=np.int64)
    area_final = None
    for k in range(K):
        tau = float(frames_tau[k])
        w = (TW <= tau)
        wcount[k] = (w & onset).sum()
        outside[k] = (w & ~fin).sum()   # t* まで白にならない頂点が白：作りから 0
        need = k == K - 1 or (wcount[k] > 0) or k % 30 == 0
        if need:
            P = pk.eval(tau)
            A = tri_area(P, Tri)
            ww = (w & onset).astype(np.float64)
            warea[k] = float((A * ww[Tri].mean(1)).sum())
            if k == K - 1:
                area_final = float((A * elig[Tri].mean(1)).sum())
    frac = wcount / max(wcount[-1], 1)
    afrac = warea / max(area_final, 1e-9)
    inc = np.diff(frac); ainc = np.diff(afrac)

    Ts, ntex, tex_never = texel_T(TW, fin, R, C)
    tex_count = np.searchsorted(Ts, frames_tau, side="right").astype(np.float64)
    tfrac = tex_count / max(ntex, 1)
    tinc = np.diff(tfrac)
    first_k = int(np.argmax(wcount > 0))
    k_all = int(np.argmax(wcount >= wcount[-1]))
    # 白の頂点の面積（世界）の単調さ：面積は形とともに変わるので記録だけ。頂点の数は単調（T_white ≤ τ で τ が単調）
    res102 = {
        "rule_ja": "美術優先31 と同じ読み：白は 0 から連続して現れる（30 Hz の 1 コマで白くなる割合が終態の白の 2% 以下）、終態の白の外に白が出ない",
        "first_white_t": float(frames_t[first_k]), "first_white_tau": float(frames_tau[first_k]),
        "first_white_tau_exact": float(tw_on.min()), "first_white_t_exact": float(t_on.min()),
        "all_white_t": float(frames_t[k_all]), "all_white_tau": float(frames_tau[k_all]),
        "white_before_first": int(wcount[:first_k].sum()),
        "vertex_fraction_max_increment_per_frame": float(inc.max()),
        "vertex_fraction_max_increment_frame": int(np.argmax(inc) + 1),
        "vertex_fraction_monotone": bool((inc >= -1e-12).all()),
        "area_fraction_max_increment_per_frame": float(ainc.max()),
        "area_fraction_max_increment_frame": int(np.argmax(ainc) + 1),
        "area_final_m2": area_final,
        "never_white_vertices_turning_white": int(outside.max()),
        "threshold_increment": 0.02,
        "note_vertex_ja": "頂点の数の割合は、唇の帯の列が 2 cm おきに詰まっているので、面の広がりの読みにならない（記録のみ）。判定はテクセルの割合と世界の面積（美術優先31 と同じ）",
        "texel_white_final": int(ntex), "texel_never_white_by_tstar": tex_never,
        "texel_fraction_max_increment_per_frame": float(tinc.max()),
        "texel_fraction_max_increment_frame": int(np.argmax(tinc) + 1),
        "texel_fraction_monotone": bool((tinc >= -1e-12).all()),
        "texel_fraction_at_tstar": float(tfrac[int(round(T_STAR * FPS))]),
        "texel_first_white_t": float(frames_t[int(np.argmax(tex_count > 0))]),
        "pass": bool(tinc.max() <= 0.02 and ainc.max() <= 0.02 and outside.max() == 0 and wcount[:first_k].sum() == 0),
        "af31_values_ja": "美術優先31：最初の白 2.012 s、30 Hz の 1 フレームの増分の最大 0.72%（テクセル）、世界の面積の 1 フレームの増分の最大 1.16%、終態が白でないテクセルが白になる数 0",
        "series": {"t": frames_t.round(4).tolist(), "tau": frames_tau.round(5).tolist(),
                   "vertex_fraction": frac.round(6).tolist(), "area_fraction": afrac.round(6).tolist(),
                   "texel_fraction": tfrac.round(6).tolist()},
    }

    # ---- 印 1：いま白くなった所（白くなって born_window 秒以内。多ければ等間隔に間引く）。シートの上に置く（法線の向きへ 0.03 m）
    rng = np.random.default_rng(a.seed)
    bw = a.born_window
    born = np.zeros((K, a.born_max, 4), dtype=np.float32)
    born_counts = np.zeros(K, dtype=np.int64)
    for k in range(K):
        t = frames_t[k]
        if t >= T_STAR:
            continue
        sel = np.where((t_on <= t) & (t_on > t - bw))[0]
        born_counts[k] = len(sel)
        if len(sel) == 0:
            continue
        if len(sel) > a.born_max:
            sel = sel[np.linspace(0, len(sel) - 1, a.born_max).astype(int)]
        tau = float(frames_tau[k])
        p = pk.eval(tau, idx[sel]) + pk.origin(tau)[0]
        # 白くなってからの経過で半径を 0.30 → 0.18 m に小さくする（生まれた所を目立たせる。左の側面の遠い視点でも数画素になる大きさ）
        age = np.clip((t - t_on[sel]) / bw, 0, 1)
        born[k, : len(sel), :3] = p + 0.03 * nrm[idx[sel]]
        born[k, : len(sel), 3] = 0.30 - 0.12 * age
    mb = write_particles(OUT + "/ds31_marks_born", born, [0.86, 0.10, 0.08],
                         "いま白くなった所（T_white を過ぎて %.2f s 以内の頂点、コマごと最大 %d、シートに付く）。確認用の印で、作品には入れない" % (bw, a.born_max),
                         {"born_counts_max": int(born_counts.max())})

    # ---- 印 2：移流（区間と行で層別に選んだ頂点。白くなった後、シートの頂点に付いて t* まで動く）
    pick = []
    per = max(1, a.trace_n // 4)
    for r_ in range(4):
        cand = np.where(region[idx] == r_)[0]
        if len(cand) == 0:
            continue
        # 行の方向に等間隔（c の広がり）→ 列はばらばら
        oc = cand[np.argsort(rows[idx[cand]] * 1000 + rng.random(len(cand)) * 999)]
        pick.extend(oc[np.linspace(0, len(oc) - 1, min(per, len(oc))).astype(int)].tolist())
    pick = np.array(sorted(set(pick)))
    trace = np.zeros((K, len(pick), 4), dtype=np.float32)
    for k in range(K):
        t = frames_t[k]
        tau = float(frames_tau[k])
        alive = t_on[pick] <= t
        if not alive.any():
            continue
        s = pick[alive]
        p = pk.eval(tau, idx[s]) + pk.origin(tau)[0]
        trace[k, np.where(alive)[0], :3] = p + 0.03 * nrm[idx[s]]
        trace[k, np.where(alive)[0], 3] = 0.26
    # 移流の距離（白くなってから t* まで、頂点がワールドでどれだけ運ばれたか）
    p_on = pos[pick]
    p_end = Pst[idx[pick]] + pk.origin(0.0)[0]
    carry = np.linalg.norm(p_end - p_on, axis=1)
    mt = write_particles(OUT + "/ds31_marks_trace", trace, [0.93, 0.42, 0.10],
                         "移流の印（区間ごとに層別に選んだ %d 頂点。白くなった時から t* までシートの頂点に付いて動く）。確認用の印で、作品には入れない" % len(pick),
                         {"carry_m_median": float(np.median(carry)), "carry_m_max": float(carry.max()), "carry_m_min": float(carry.min()),
                          "picked_regions": {str(r_): int((region[idx[pick]] == r_).sum()) for r_ in range(4)}})

    log["seconds"] = time.time() - t0
    out = {"schema": "GreatWave.DS31.white_numpy/1", "log": log, "onset": {k: onset_meta[k] for k in ("records", "regions", "j_top_per_row_range", "landmarks", "selection_ja")},
           "b102_vertex": res102, "ds31_white_rate_cap": capinfo, "marks": {"born": mb, "trace": mt}, "inputs": onset_meta["inputs"],
           "python": sys.version.split()[0], "numpy": np.__version__}
    json.dump(out, open(OUT + "/ds31_white_numpy.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"cap": capinfo, "log": log, "b102": {k: v for k, v in res102.items() if k != "series"}, "regions": reg_sum,
                      "born_max": int(born_counts.max()), "trace_n": int(len(pick)), "carry_med": float(np.median(carry))}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
