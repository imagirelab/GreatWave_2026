# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1-3：白の地と、白が藍の面へ垂れる縁（丸い先の舌）を、主役波 AS02C の t* の面の上の関数として作る（共有の白の印）。

考え方（視点によらない。Q28）：
- 白は面の属性だけで決まる。原画のカメラの投影の色は使わない。
- 前（頂の列より前、巻きの向き）：行ごとの境 s_b(r)（頂からの本当の弧長 m）より頂の側が白。境は、原画の視点から見た原画の
  「藍の面の始まり」（調べ S2 の藍の面の塊を、原画の画素 → 面の点の表で行・列へ集めたもの）に合わせた数値の線を、行の向きに
  ならしたもの。原画で藍の面が見えない行は、唇の先を回り込んだ所（唇の先の列 200 から 1.5 m）を境にする（彫刻の冠は唇の縁から垂れる）。
- 境には丸い先の白い舌を足す（白が藍へ垂れる）。舌は境に沿う長さ L（境の点を 3D でつないだ長さ）と、境からの弧長 y の平面の
  カプセル（半幅 b、長さ len、先は半円）。白の地とはなめらかな最小（k = 0.25 m）でつなぐので、舌の間の藍は丸い頭になる。
  - 原画の視点で見えて、原画に藍の面がある所（主の面の上の縁・b区域・右の端）：原画の舌の数（S2：深さ p50 0.46 m・p90 0.68 m、
    藍の頭の間隔 p50 1.0 m）で、原画視点の藍の面を白で覆わない。
  - 原画の視点から見えない所（唇の裏・回り込み）：彫刻の舌の数（S1：幅 1.35 m・間隔 2.5 m・見える長さ 3.1 m、先は半円）。
- 背（頂の列より後ろ）：見本 A と同じ規則 hrel > 0.40 ＋ ゆるい波（S1：背の白は海面から 0.25〜0.40 H まで、境は一本のゆるい曲線）。
- 出力（Git 対象外、Unity/Build/Polish/sample03/shared/）：格子の頂点ごとの値、頂の帯を細かくした格子の頂点ごとの値、境と舌の表、README。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as03/crown_whitemask.py --ver v1
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_common as G  # noqa: E402

PGRID = G.OUT + "/tmp/painting_on_grid.npz"
S2MAP = G.STUDY + "/tmp/s2_map.npz"
S2Z = G.STUDY + "/tmp/s2_zones.npz"
S2C = G.STUDY + "/tmp/s2_classes.npz"
SEED = 31


def painting_on_grid(R, C):
    """S2 の表（原画の画素 → 主役波の行・列）で、原画の藍の面・白の区域を格子の頂点へ数える（測るためだけ）。"""
    if os.path.exists(PGRID):
        return np.load(PGRID)
    d = np.load(S2MAP)
    z = np.load(S2Z)
    cl = np.load(S2C)
    m = d["surf"] == 1
    ri = np.rint(d["r"][m]).astype(int)
    ci = np.rint(d["c"][m]).astype(int)

    def acc(v):
        a = np.zeros((R, C))
        np.add.at(a, (ri, ci), v)
        return a
    cnt = acc(np.ones(len(ri)))
    lab = {k: acc(z[k][m].astype(float)) / np.maximum(cnt, 1) for k in ["z_crest_top", "z_lip", "z_b_crest", "big_white", "face", "flecks"]}
    cls = cl["cls"][m]
    for k in range(6):
        lab["cls%d" % k] = acc((cls == k).astype(float)) / np.maximum(cnt, 1)
    np.savez_compressed(PGRID, cnt=cnt, **lab)
    return np.load(PGRID)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def gauss1d(y, sig):
    n = int(3 * sig) + 1
    x = np.arange(-n, n + 1)
    k = np.exp(-0.5 * (x / sig) ** 2)
    k /= k.sum()
    yp = np.pad(y, n, mode="edge")
    return np.convolve(yp, k, mode="valid")


class Mask:
    def __init__(self, h, ver="v1"):
        self.h = h
        self.ver = ver
        R, C = h.R, h.C
        X = h.X
        seg = np.linalg.norm(np.diff(X, axis=1), axis=-1)
        Sx = np.concatenate([np.zeros((R, 1)), np.cumsum(seg, 1)], 1)
        top = h.top_col
        self.s = Sx - Sx[np.arange(R), top][:, None]        # 頂の列からの本当の弧長（前が +）
        self.top = top
        P = painting_on_grid(R, C)
        self.P = P
        face, cnt = P["face"], P["cnt"]
        foamz = P["z_crest_top"] + P["z_lip"] + P["z_b_crest"]       # S2 の泡の区域（頂の冠・唇の泡・b区域の冠）
        # ---- 原画の藍の面の始まり（行ごと）：見えている所で、藍の面が 1.8 m 以上続く最初の所（見えない 2 列までの切れ目は続きとみなす）。
        #      小さな藍の点・窓（b区域の白い塊の穴など、1.8 m 未満）は境にしない。
        s_face = np.full(R, np.nan)
        j_face = np.full(R, -1)
        mode = np.full(R, 2)                                  # 1 = 原画の藍の面に合わせた、2 = 唇の回り込み、3 = 唇の先より奥の原画の白まで
        # 唇の先を回り込む：主の頂・唇は 1.5 m、b区域（左の肩、行 ≤ 112＝c ≤ −10.4 m）は 3.0 m（原画で唇の裏の側まで白い泡の塊が見える）
        wrap = self.s[np.arange(R), 200] + np.where(np.arange(R) <= 112, 3.0, 1.5)
        sb = wrap.copy()
        for r in range(R):
            j0 = top[r] + 2
            runs = []                                         # (始まりの列, 終わりの列, 長さ m)
            j = j0
            while j < 330:
                if cnt[r, j] >= 1 and face[r, j] >= 0.5:
                    k = j
                    last = j
                    gap = 0
                    while k + 1 < 330:
                        k += 1
                        if cnt[r, k] < 1:
                            gap += 1
                            if gap > 2:
                                break
                            continue
                        if face[r, k] >= 0.5:
                            last = k
                            gap = 0
                        else:
                            break
                    runs.append((j, last, self.s[r, last] - self.s[r, j]))
                    j = last + 1
                else:
                    j += 1
            long_runs = [q for q in runs if q[2] >= 1.8]
            jf = long_runs[0][0] if long_runs else 330
            if jf <= 215:
                s_face[r] = self.s[r, jf] - 0.5 * (self.s[r, jf] - self.s[r, jf - 1])
                j_face[r] = jf
                sb[r] = s_face[r]
                mode[r] = 1
                continue
            # 唇の先より奥：見えている原画の泡の区域（S2 の頂の冠・唇の泡・b区域の冠の塊）が唇の先の後ろに 1.5 m 以上あるなら、
            # その最後の泡の 0.3 m 先まで白（唇の泡の塊・b区域の白い塊が、原画の視点から唇の裏まで見える所）。
            vis_w = [k for k in range(216, jf) if cnt[r, k] >= 1 and face[r, k] < 0.5 and foamz[r, k] >= 0.5]
            if vis_w and (self.s[r, vis_w[-1]] - self.s[r, vis_w[0]]) >= 1.5:
                sb[r] = min(self.s[r, vis_w[-1]] + 0.3, self.s[r, min(jf, C - 1)] - 0.1, self.s[r, 245])
                if jf < 330:
                    s_face[r] = self.s[r, jf]
                    j_face[r] = jf
                mode[r] = 3
        self.s_face, self.j_face = s_face, j_face
        if self.ver == "v1":
            # v1：孤立した値（前後 3 行と 3 m 以上違う 1〜2 行）を中央値でならし、行の向きに σ 1.0 m（5 行）でならす
            med = np.array([np.median(sb[max(0, r - 3):r + 4]) for r in range(R)])
            sb = np.where(np.abs(sb - med) > 3.0, med, sb)
            sbs = gauss1d(sb, 5.0)
        else:
            # v2：原画の藍の面に合わせた行（決め方 1）と、それ以外の行を別々にならし、境目だけ 4 行（0.8 m）でつなぐ
            # （v1 は σ 5 行のならしで、主の藍の面の上の縁の行が隣の回り込みの行に 1〜4 m 引かれた）
            rr = np.arange(R)
            is1 = mode == 1
            oth = ~is1
            sb_o = np.interp(rr, rr[oth], sb[oth]) if oth.any() else sb.copy()
            med = np.array([np.median(sb_o[max(0, r - 3):r + 4]) for r in range(R)])
            sb_o = np.where(np.abs(sb_o - med) > 3.0, med, sb_o)
            sb_o = gauss1d(sb_o, 5.0)
            if is1.any():
                sb_f = np.interp(rr, rr[is1], sb[is1])
                med = np.array([np.median(sb_f[max(0, r - 2):r + 3]) for r in range(R)])
                sb_f = np.where(np.abs(sb_f - med) > 2.0, med, sb_f)
                sb_f = gauss1d(sb_f, 2.0)
                dist = np.array([np.min(np.abs(rr[is1] - r)) for r in rr])
                wf = 1.0 - G.sm(dist / 4.0)
                sbs = wf * sb_f + (1 - wf) * sb_o
            else:
                sbs = sb_o
        # 細かい行（主役波の範囲 c −19〜+15、0.2 m おき）の外はならしだけ
        self.sb = np.maximum(sbs, 0.6)
        self.mode = mode
        # 境の点（行ごとの列の位置）と、境に沿う長さ L
        jb = np.zeros(R)
        for r in range(R):
            jb[r] = np.interp(self.sb[r], self.s[r, top[r]:], np.arange(top[r], C)) if self.sb[r] < self.s[r, -1] else C - 1
        self.jb = jb
        Bp = np.stack([np.array([np.interp(jb[r], np.arange(C), X[r, :, k]) for r in range(R)]) for k in range(3)], -1)
        self.Bp = Bp
        dL = np.linalg.norm(np.diff(Bp, axis=0), axis=-1)
        self.Lrow = np.concatenate([[0.0], np.cumsum(dL)])
        # 原画の視点で見える境（境の列の周り ±3 列のどれかが見える）か
        vis = np.zeros(R, bool)
        for r in range(R):
            j = int(round(jb[r]))
            vis[r] = cnt[r, max(0, j - 3):min(C, j + 4)].sum() > 0
        self.vis = vis
        self.tongues = self.place_tongues()

    def place_tongues(self):
        rng = np.random.default_rng(SEED)
        R = self.h.R
        L = self.Lrow
        # 舌を置く範囲：細かい行（69〜239）で、境が背の高さの 0.1 H0 より上
        rows = np.arange(R)
        ok = (rows >= 66) & (rows <= 236)
        Lmin, Lmax = L[ok].min(), L[ok].max()
        out = []
        x = Lmin + 0.6
        k = 0
        while x < Lmax - 0.4:
            r = int(np.clip(np.searchsorted(L, x), 0, R - 1))
            paint = bool(self.vis[r] and self.mode[r] in (1, 3))
            if paint:   # 原画の舌（S2）
                b = rng.uniform(0.20, 0.30)
                ln = float(np.clip(rng.normal(0.46, 0.14), 0.26, 0.68))
                gap = rng.uniform(0.82, 1.25)
                src = "S2_painting_main_face_tongues"
            else:       # 彫刻の舌（S1）
                b = 0.675 * rng.uniform(0.8, 1.2)
                ln = 3.1 * rng.uniform(0.55, 1.0)
                gap = 2.49 * rng.uniform(0.8, 1.2)
                src = "S1_sculpture_tongue_edge"
            out.append(dict(id=k, L=round(float(x), 4), row=round(float(np.interp(x, L, rows)), 3), half_width_m=round(float(b), 4),
                            length_m=round(float(ln), 4), start_m=-0.3, regime=src, painting_visible=paint))
            k += 1
            x += gap
        return out

    def eval(self, r, j, s, hrel, w):
        """頂点（行 r、列 j は小数でよい）の白（0..1）・符号付きの距離 sd [m]（負が白）・領域・舌の番号。"""
        h = self.h
        R = h.R
        r = np.asarray(r, np.float64)
        rr = np.clip(r, 0, R - 1)
        sb = np.interp(rr, np.arange(R), self.sb)
        Lr = np.interp(rr, np.arange(R), self.Lrow)
        top = np.interp(rr, np.arange(R), self.top.astype(np.float64))
        y = s - sb                                 # 境からの弧長（前・巻きの奥が +）
        sd_front = y.copy()
        tid = np.full(y.shape, -1, np.int32)
        best = np.full(y.shape, np.inf)
        for t in self.tongues:
            dx = Lr - t["L"]
            near = np.abs(dx) < (t["half_width_m"] + 1.0)
            if not near.any():
                continue
            yy = y[near]
            q = np.clip(yy, t["start_m"], t["length_m"] - t["half_width_m"])
            d = np.hypot(dx[near], yy - q) - t["half_width_m"]
            sub = sd_front[near]
            sd_front[near] = smin(sub, d, 0.25)
            bb = best[near]
            upd = d < bb
            bb[upd] = d[upd]
            best[near] = bb
            ti = tid[near]
            ti[upd & (d < 0.05)] = t["id"]
            tid[near] = ti
        # 背
        hb = 0.40 + 0.025 * np.sin(2 * np.pi * w / 16.0) + 0.012 * np.sin(2 * np.pi * w / 6.1 + 0.7)
        Hrow = np.maximum(np.interp(rr, np.arange(R), h.X[np.arange(R), h.top_col, 1]), 2.0)
        sd_back = (hb - hrel) * Hrow
        front = j >= top
        sd = np.where(front, sd_front, sd_back)
        reg = np.where(front, np.where(sd < 0, np.where(tid >= 0, 3, 2), 0), np.where(sd < 0, 1, 0)).astype(np.int32)
        aa = 0.06
        white = 1.0 - G.sm((sd + aa) / (2 * aa))
        tid = np.where(front, tid, -1)
        return white, sd, reg, tid


def bilin(A, r, c):
    R, C = A.shape[:2]
    r0 = np.clip(np.floor(r).astype(int), 0, R - 2)
    c0 = np.clip(np.floor(c).astype(int), 0, C - 2)
    fr = (r - r0)[..., None] if A.ndim == 3 else (r - r0)
    fc = (c - c0)[..., None] if A.ndim == 3 else (c - c0)
    return (A[r0, c0] * (1 - fr) * (1 - fc) + A[r0 + 1, c0] * fr * (1 - fc) + A[r0, c0 + 1] * (1 - fr) * fc + A[r0 + 1, c0 + 1] * fr * fc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", default="v1")
    a = ap.parse_args()
    t0 = time.time()
    h = G.HeroData()
    M = Mask(h, a.ver)
    R, C = h.R, h.C
    rr, jj = np.meshgrid(np.arange(R, dtype=np.float64), np.arange(C, dtype=np.float64), indexing="ij")
    white, sd, reg, tid = M.eval(rr, jj, M.s, h.hrel, h.w)
    out = os.path.join(G.SHARED, "white_mask_" + a.ver)
    os.makedirs(out, exist_ok=True)
    grid = np.stack([white, sd, reg.astype(np.float64), tid.astype(np.float64)], -1).astype(np.float32)
    grid.reshape(-1, 4).tofile(os.path.join(out, "white_mask_grid_f32.bin"))
    # 頂の帯を細かくした格子：行 60〜239 を 4 倍、列 60〜270 を 2 倍
    r0, r1, c0, c1, SR, SCc = 60, 239, 60, 270, 4, 2
    rs = np.linspace(r0, r1, (r1 - r0) * SR + 1)
    cs = np.linspace(c0, c1, (c1 - c0) * SCc + 1)
    RS, CS = np.meshgrid(rs, cs, indexing="ij")
    Pb = bilin(h.X, RS, CS)
    sbd = bilin(M.s, RS, CS)
    hb = bilin(h.hrel, RS, CS)
    wb = bilin(h.w, RS, CS)
    ub = bilin(h.u, RS, CS)
    wh2, sd2, reg2, tid2 = M.eval(RS, CS, sbd, hb, wb)
    band = np.concatenate([RS[..., None], CS[..., None], Pb, ub[..., None], wb[..., None], wh2[..., None], sd2[..., None],
                           reg2[..., None].astype(np.float64), tid2[..., None].astype(np.float64)], -1).astype(np.float32)
    band.reshape(-1, band.shape[-1]).tofile(os.path.join(out, "white_mask_band_f32.bin"))
    # 境と舌の表
    rows_tab = [dict(row=int(r), c_m=round(float(h.c_row[r]), 3), s_b_m=round(float(M.sb[r]), 4), col_b=round(float(M.jb[r]), 3),
                     mode={1: "painting_face_start", 2: "lip_wrap_1p5m", 3: "painting_white_beyond_lip"}[int(M.mode[r])],
                     s_face_painting_m=(None if not np.isfinite(M.s_face[r]) else round(float(M.s_face[r]), 4)),
                     L_along_edge_m=round(float(M.Lrow[r]), 4), painting_visible=bool(M.vis[r])) for r in range(R)]
    nt = len(M.tongues)
    reg_counts = {str(k): int((reg == k).sum()) for k in range(4)}
    tg = M.tongues
    paint_t = [t for t in tg if t["painting_visible"]]
    s1_t = [t for t in tg if not t["painting_visible"]]
    params = {
        "schema": "GreatWave.AS03.white_mask/1", "version": a.ver, "date": time.strftime("%Y-%m-%d %H:%M"),
        "hero": {"pkg": os.path.relpath(G.HERO_PKG, G.REPO).replace("\\", "/"), "gwb_sha256": G.sha(G.GWB), "rows": R, "cols": C,
                 "attr_sha256": G.sha(G.ATTR)},
        "definition_ja": __doc__.strip(),
        "formula": {
            "front": "列 j ≥ 頂の列 top(r)：y = s − s_b(r)（s は頂の列からの行に沿う本当の弧長 m）。sd = smin_k(y, min_k capsule_k) 、k = 0.25 m。capsule_k = |(L(r) − L_k, y − clamp(y, start, len_k − b_k))| − b_k",
            "back": "列 j < top(r)：sd = (hb(w) − hrel) × H_row、hb(w) = 0.40 + 0.025 sin(2πw/16) + 0.012 sin(2πw/6.1 + 0.7)、H_row = その行の頂の高さ",
            "white": "white = 1 − smoothstep(−0.06, +0.06, sd)（AA の幅 ±0.06 m。シェーダーで sd と fwidth を使う方がよい）",
            "region": "0 = 藍（白の外）、1 = 背の白、2 = 前の白の地（冠）、3 = 垂れる舌"},
        "rows": rows_tab, "tongues": tg,
        "stats": {"tongues_total": nt, "tongues_painting_regime": len(paint_t), "tongues_S1_regime": len(s1_t),
                  "edge_length_m": round(float(M.Lrow[236] - M.Lrow[66]), 3),
                  "painting_regime_len_m": G.pct([t["length_m"] for t in paint_t]), "S1_regime_len_m": G.pct([t["length_m"] for t in s1_t]),
                  "grid_region_counts": reg_counts, "grid_white_frac_front": float((white[jj >= M.top[:, None]] > 0.5).mean())},
        "files": {
            "white_mask_grid_f32.bin": {"layout": "頂点ごと float32 × 4（.gwb と同じ順＝行 × 400 ＋ 列、96,000 頂点）：white(0..1), sd_m(負＝白), region, tongue_id(−1 なし)",
                                         "sha256": None},
            "white_mask_band_f32.bin": {"layout": "細かい格子の頂点ごと float32 × 12：r, c（主役波の格子の小数の行・列）, x, y, z（Unity の世界 m、t*）, u, w（見本02 の面の座標）, white, sd_m, region, tongue_id",
                                        "rows": [r0, r1], "cols": [c0, c1], "subdiv_rows": SR, "subdiv_cols": SCc,
                                        "shape": [len(rs), len(cs)], "order": "細かい行 × 細かい列（行の速い向きは列）", "sha256": None}},
        "sources": {"S1_sculpture_spec": [os.path.relpath(G.SPEC, G.REPO).replace("\\", "/"), G.sha(G.SPEC)],
                    "S2_painting_crest": [os.path.relpath(G.PCREST, G.REPO).replace("\\", "/"), G.sha(G.PCREST)],
                    "S2_map_and_zones": [os.path.relpath(S2MAP, G.REPO).replace("\\", "/"), os.path.relpath(S2Z, G.REPO).replace("\\", "/")]},
        "no_projection_ja": "原画の色は面へ写していない。原画は、行ごとの境の位置（藍の面の始まり）と、舌の大きさの決め分け（原画の視点で見える所か）を決める数にだけ使った。白は (行, 弧長 s, 境に沿う長さ L, hrel, w) だけで決まる。",
    }
    for fn in ("white_mask_grid_f32.bin", "white_mask_band_f32.bin"):
        params["files"][fn]["sha256"] = G.sha(os.path.join(out, fn))
    G.jdump(os.path.join(out, "white_mask_params.json"), params)
    # B2 との約束（shared/README.md の B2 → B1）：格子の頂点ごとの float32 1 つ、面に沿った符号付きの距離（m、+ が白、− が藍）
    sdB2 = (-sd).astype(np.float32)
    sdB2.reshape(-1).tofile(os.path.join(out, "white_mask_f32.bin"))
    spec = {"schema": "GreatWave.AS03.white_mask_sd/1", "version": a.ver, "date": params["date"],
            "file": "white_mask_f32.bin", "sha256": G.sha(os.path.join(out, "white_mask_f32.bin")),
            "layout_ja": "主役波 AS02C の格子（行 240 × 列 400、添字 = 行 × 400 + 列。.gwb と同じ並び）の頂点ごとの float32 1 つ。面に沿った符号付きの距離 m（+ が白、− が藍。0 が境）",
            "hero": params["hero"], "definition_ja": params["definition_ja"], "formula": params["formula"],
            "note_ja": "式の中の sd は負が白。このファイルは B2 の約束に合わせて符号を反転した（+ が白）。詳しい表（行ごとの境・舌）は white_mask_params.json、細かい格子は white_mask_band_f32.bin（こちらの sd_m は負が白のまま）",
            "stats": params["stats"], "sources": params["sources"], "no_projection_ja": params["no_projection_ja"]}
    G.jdump(os.path.join(out, "white_mask.json"), spec)
    # 共有の場所（最新）へも同じ物を置く
    import shutil
    for fn in ("white_mask_f32.bin", "white_mask.json", "white_mask_grid_f32.bin", "white_mask_band_f32.bin", "white_mask_params.json"):
        shutil.copyfile(os.path.join(out, fn), os.path.join(G.SHARED, fn))
    np.save(os.path.join(G.OUT, "tmp", "mask_obj_%s.npy" % a.ver), np.array([0]))
    # ---- 下見の図：格子の展開図（行 × 列）と、原画の画素 → 面の点の表で見た原画視点（原画の色ではなく白の印）
    S = 3
    vis = M.P["cnt"] > 0
    img = np.zeros((R, C, 3), np.float64)
    img[:] = (40, 40, 40)
    img[white > 0.5] = (235, 235, 235)
    img[white <= 0.5] = (110, 60, 25)
    img[(reg == 3)] = (180, 230, 250)
    # 原画の藍の面の縁（見えている所）
    fm = ((M.P["face"] > 0.5) & vis).astype(np.uint8)
    im = np.repeat(np.repeat(img, S, 0), S, 1).astype(np.uint8)
    fmS = np.repeat(np.repeat(fm, S, 0), S, 1)
    e = cv2.morphologyEx(fmS, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    im[e] = (255, 0, 255)
    for r in range(R):
        y = r * S + 1
        x = int(round(M.jb[r] * S))
        cv2.circle(im, (x, y), 1, (0, 200, 255), -1)
    for j in (90, 150, 200, 250, 314):
        im[:, j * S] = (0, 255, 255)
    im = im[60 * S:, 60 * S:330 * S]
    cv2.imencode(".png", im)[1].tofile(os.path.join(out, "preview_grid.png"))
    # 原画視点（S2 の表で、原画の画素ごとに面の点の白を引く。描画ではない）
    d = np.load(S2MAP)
    surf = d["surf"]
    rp, cp = d["r"], d["c"]
    pv = np.full(surf.shape + (3,), (235, 225, 200), np.uint8)
    m = surf == 1
    wv = bilin(white, np.nan_to_num(rp[m]), np.nan_to_num(cp[m]))
    rgv = bilin(reg.astype(np.float64), np.nan_to_num(rp[m]), np.nan_to_num(cp[m]))
    col = np.where(wv[:, None] > 0.5, np.array([[240, 240, 240]]), np.array([[110, 60, 25]]))
    col = np.where((rgv[:, None] > 2.5) & (wv[:, None] > 0.5), np.array([[180, 230, 250]]), col)
    pv[m] = col.astype(np.uint8)
    pv[surf == 2] = (120, 90, 60)
    pt = cv2.imdecode(np.fromfile(G.U.PAINT, np.uint8), cv2.IMREAD_COLOR)[:surf.shape[0], :surf.shape[1]]
    both = np.concatenate([cv2.resize(pt, (surf.shape[1] // 3, surf.shape[0] // 3), interpolation=cv2.INTER_AREA),
                           cv2.resize(pv, (surf.shape[1] // 3, surf.shape[0] // 3), interpolation=cv2.INTER_AREA)], 1)
    cv2.imencode(".png", both)[1].tofile(os.path.join(out, "preview_painting_view.png"))
    shutil.copyfile(os.path.join(out, "preview_painting_view.png"), os.path.join(G.SHARED, "white_mask_preview_painting_view.png"))
    shutil.copyfile(os.path.join(out, "preview_grid.png"), os.path.join(G.SHARED, "white_mask_preview_grid.png"))
    print(json.dumps(params["stats"], ensure_ascii=False))
    print("WHITE_MASK_DONE", out, round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
