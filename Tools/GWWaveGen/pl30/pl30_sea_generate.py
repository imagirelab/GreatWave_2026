# -*- coding: utf-8 -*-
"""仕上げ30：周りの海のシート（DS27 の書式、主役波 G_p28rec と同じ knot_tau と波の枠）を作る（設計30 の ds30_generate.py を写して直したもの）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_generate.py [--out Unity/Build/Polish/30/sea] [--params Tools/GWWaveGen/pl30/pl30_params.json]
出力（Git 対象外）:
    <out>/near/  ds27_keypose.json・ds27_pos_rgba16.bin・ds27_pos_lo_rgba8.bin・ds27_twhite_r32f.bin・ds30_class_u8.bin・ds30_tstar.gwb・ds30_ring0_index.json・pl30_rows.json
    <out>/far/   同じ（行 0 は近い海の外周の全部の列＝T 字なし）
    <out>/sea_function.json   設計43 の船が読む式（遠い海の弱めも書く）
    <out>/pl30_generate_log.json
設計30 からの変更（pl30_params.json の note_ja）：
    ① 主役波を G_p28rec（251 節点）へ替え、行 0 をその本体の境の輪にする（仕上げ28 の継ぎ目の隔たり最大 4.134 m をなくす）
    ② 近い海の行を 60 にし、各列で右の高い波の稜を横切る所に行を集める（pl30_rows.json に列ごとの稜の位置と重み）
    ③ 地形の誘導は pl30_sea.Features（右の高い波を PCHIP、肩の稜、育ちの遅れ pl30_right_lag）
    ④ 船の支えは帯を混ぜた後の当て布（継ぎ目では 0）
    ⑤ 遠い海の列は近い海の外周と同じ（far_subsample 1）
網の約束は設計30 と同じ（行 r = 輪、列 = 外周を一周、最後の列は最初の列の写し、外積 (P[r+1,c]−P[r,c])×(P[r,c+1]−P[r,c]) が +y）。
"""
import argparse
import json
import math
import os
import struct
import sys
import time

import numpy as np
from scipy.ndimage import gaussian_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl30_sea as S  # noqa: E402

REPO = S.REPO
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds30"))
from ds30_generate import ring0_loop, ray_dirs, ray_to_stadium, quantize, write_gwb  # noqa: E402


def write_package(outdir, name, Xl, hero, extra, twhite=None, cls=None):
    """Xl：(層, 行, 列, 3) の局所座標（ワールド − O(τ)）。DS27 の書式で書く（設計30 の write_package と同じ。番号の書き方だけ違う）。"""
    import hashlib
    os.makedirs(outdir, exist_ok=True)
    Lr, R, C, _ = Xl.shape
    bmin = np.min([Xl[i].reshape(-1, 3).min(0) for i in range(Xl.shape[0])], axis=0) - 0.01
    bmax = np.max([Xl[i].reshape(-1, 3).max(0) for i in range(Xl.shape[0])], axis=0) + 0.01
    bsz = bmax - bmin
    hp = os.path.join(outdir, "ds27_pos_rgba16.bin")
    lp = os.path.join(outdir, "ds27_pos_lo_rgba8.bin")
    h1, h2 = hashlib.sha256(), hashlib.sha256()
    maxerr_hi, maxerr_fine = 0.0, 0.0
    with open(hp, "wb") as fh, open(lp, "wb") as fl:
        for i in range(Lr):
            q, lo = quantize(Xl[i], bmin, bsz)
            a16 = np.empty((R, C, 4), "<u2"); a16[..., :3] = q; a16[..., 3] = 65535
            a8 = np.empty((R, C, 4), np.uint8); a8[..., :3] = lo; a8[..., 3] = 255
            b16, b8 = a16.tobytes(), a8.tobytes()
            fh.write(b16); fl.write(b8); h1.update(b16); h2.update(b8)
            rec_hi = bmin + q / 65535.0 * bsz
            rec_f = bmin + (q + lo / 255.0 - 0.5) / 65535.0 * bsz
            maxerr_hi = max(maxerr_hi, float(np.abs(rec_hi - Xl[i]).max()))
            maxerr_fine = max(maxerr_fine, float(np.abs(rec_f - Xl[i]).max()))
    tw = (np.full((R, C), 1.0e9, np.float32) if twhite is None else twhite.astype(np.float32)).tobytes()
    if cls is not None:
        open(os.path.join(outdir, "ds30_class_u8.bin"), "wb").write(cls.astype(np.uint8).tobytes())
    tp = os.path.join(outdir, "ds27_twhite_r32f.bin")
    open(tp, "wb").write(tw)
    k = hero.k
    meta = dict(
        schema="GreatWave.DS27.keypose/1", schema_ds30="GreatWave.DS30.seasheet/1", number="仕上げ30", version=name,
        layers=Lr, rows=R, cols=C, bbox_min=[float(v) for v in bmin], bbox_size=[float(v) for v in bsz],
        knot_tau=k["knot_tau"], t_star_layer=Lr - 1,
        frame=dict(tau=k["frame"]["tau"], origin=k["frame"]["origin"], hz=k["frame"]["hz"],
                   note_ja="主役波（G_p28rec/art_on）の frame と同じ配列。海のシートは波の枠とともに動く切り抜き。"),
        pos_file="ds27_pos_rgba16.bin", pos_sha256=h1.hexdigest(), pos_bytes=os.path.getsize(hp),
        pos_format_ja=k["pos_format_ja"],
        pos_lo_file="ds27_pos_lo_rgba8.bin", pos_lo_sha256=h2.hexdigest(), pos_lo_bytes=os.path.getsize(lp),
        pos_lo_format_ja=k["pos_lo_format_ja"], extensions=["pos_lo_rgba8/1", "ds30_grid/1"],
        pos_precision=dict(hi_step_mm=float(bsz.max() / 65535 * 1000), max_err_hi_m=maxerr_hi, max_err_fine_m=maxerr_fine),
        twhite_file="ds27_twhite_r32f.bin", twhite_sha256=S.sha256_file(tp), twhite_bytes=len(tw), twhite_never=1.0e9,
        twhite_format_ja="R32F、行 × 列。仕上げ30 の海の材質（PL30 Ukiyoe Sea）は白を今の高さで決め、この値を読まない（全部 +1e9 = 白にならない。設計27 の NPR で描いたときに白くしないため）。",
        class_file=("ds30_class_u8.bin" if cls is not None else None),
        class_format_ja="uint8、行 × 列。t* の地形の誘導の区分（記録と検査のため）：0 = 海、1 = 右の高い波・肩の稜（t* の高さ ≥ 0.5 m）、2 = 手前の小波（≥ 0.5 m）。",
        interpolation_ja=k["interpolation_ja"],
        grid_ja="行 r = 輪（0 が内側）、列 = 外周を一周（最後の列は最初の列の写し）。四角 (r,c)(r+1,c)(r,c+1)(r+1,c+1) を (r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1) の 2 つの三角形に割る（主役波と同じ）。",
        winding_ja="この並びで外積 (P[r+1,c] − P[r,c]) × (P[r,c+1] − P[r,c]) は +y（上）を向く（主役波の格子と同じ約束）。",
        gpu_estimate=dict(layer_mib=R * C * 8 / 2 ** 20, rgba16_mib=Lr * R * C * 8 / 2 ** 20, rgba8_mib=Lr * R * C * 4 / 2 ** 20,
                          packed_hi_plus_lo_mib=Lr * R * C * 12 / 2 ** 20),
        hero_package=os.path.relpath(hero.dir, REPO).replace("\\", "/"), hero_sha256=hero.sha(),
    )
    meta.update(extra)
    S.save_json(os.path.join(outdir, "ds27_keypose.json"), meta)
    return meta


def row_layout(P, feat, p_t, q_out, NL):
    """列ごとの行の並び ζ_j(k)（k = 0..NR−1）。設計30 の 44 行の並び u→ζ に、右の高い波の稜の所の密度の山を足す。"""
    G = P["grid"]
    zdef = np.array(G["near_ring_s_m"], np.float64) / float(G["near_ring_s_ref_m"])
    zdef[-1] = 1.0
    ud = np.linspace(0.0, 1.0, len(zdef))
    NR = int(G["near_rows"])
    RD = G["ridge_density"]
    # 各列で稜を横切る所：線分に沿って t* の右の誘導（右の高い波＋肩の稜）の最大
    nz = 801
    zz = np.linspace(0.0, 1.0, nz)
    A = p_t[:, None, 0] + (q_out[:, None, 0] - p_t[:, None, 0]) * zz[None, :]
    Cc = p_t[:, None, 1] + (q_out[:, None, 1] - p_t[:, None, 1]) * zz[None, :]
    F = feat.sample(A, Cc, "right")
    k = np.argmax(F, axis=1)
    Fm = F[np.arange(NL), k]
    zstar = zz[k]
    w = S.smoothstep((Fm - RD["h_min_m"]) / (RD["h_full_m"] - RD["h_min_m"]))
    # ζ* → u*（設計30 の並びの番号の割合）
    ustar = np.interp(zstar, zdef, ud)
    # 列に沿ってならす（重み付き、輪なので wrap）
    sc = float(RD["smooth_cols"])
    wn = gaussian_filter1d(w, sc, mode="wrap")
    us = gaussian_filter1d(w * ustar, sc, mode="wrap") / np.maximum(wn, 1e-6)
    us = np.where(wn > 1e-4, us, ustar)
    wn = np.clip(wn, 0.0, 1.0)
    # 密度 ρ(u) = 1 + bump·w·exp(−((u − u*)/σ)²) の累積の逆で行を置く
    nu = 4001
    uu = np.linspace(0.0, 1.0, nu)
    zeta = np.zeros((NR, NL))
    # 修正01：線分が稜の系を 2 度横切る所（扇の線分が肩の稜と右の高い波の上の方を両方横切る）で、2 度目の稜の行が粗く（3〜5 m）、
    # 細くなった白の頂（閾値 0.80）が行の間で切れた（真上から見た右の高い波の上の方の切れ目）。最大の稜の山のほかに、
    # 地形の誘導の t* の高さ F が region_h_m を超える所の全部に行の密度を region_bump だけ足す。
    zu = np.interp(uu, ud, zdef)                                   # 並びの番号の割合 u → 線分の割合 ζ
    rb = float(RD.get("region_bump", 0.0)); rh = RD.get("region_h_m", [0.5, 3.5])
    for j in range(NL):
        rho = 1.0 + RD["bump"] * wn[j] * np.exp(-((uu - us[j]) / RD["sigma_u"]) ** 2)
        if rb > 0:
            rho = rho + rb * S.smoothstep((np.interp(zu, zz, F[j]) - rh[0]) / (rh[1] - rh[0]))
        cdf = np.concatenate([[0.0], np.cumsum(0.5 * (rho[1:] + rho[:-1]) * np.diff(uu))])
        cdf /= cdf[-1]
        uk = np.interp(np.linspace(0.0, 1.0, NR), cdf, uu)
        zeta[:, j] = np.interp(uk, ud, zdef)
    zeta[0] = 0.0
    zeta[-1] = 1.0
    rec = dict(near_rows=NR, ridge_density=RD, zstar=zstar.tolist(), weight=wn.tolist(), u_star=us.tolist(), ridge_h_tstar=Fm.tolist(),
               note_ja="列 j の行 k の位置 = 行 0 の点 + (外周の点 − 行 0 の点)·zeta[k][j]（t* の線分で決めた並びを、すべての節点で使う）。")
    return zeta, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Unity/Build/Polish/30/sea")
    ap.add_argument("--params", default=S.PARAMS)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    P = S.load_json(args.params)
    G = P["grid"]
    B = P["band"]
    hero = S.Hero(P)
    sea = S.Sea(hero, P)
    feat = S.Features(hero, P)
    print("raster", round(time.time() - t0, 1), "s")
    jb, je = P["hero"]["body_cols"]
    loop, kind = ring0_loop(jb, je, hero.R)
    loop, kind = loop[::-1].copy(), kind[::-1]
    NL = len(loop)
    fs = int(G["far_subsample"])
    assert NL % fs == 0, (NL, fs)
    L = hero.L
    knots = hero.knots
    t_ax, e_ax = hero.t, hero.e
    R0 = np.zeros((L, NL, 3)); IN2 = np.zeros((L, NL, 3)); hmax = np.zeros(L)
    inner2 = []
    for (r, j), (k, f) in zip(loop, kind):
        if k == "front":
            inner2.append((r, j - 2))
        elif k == "back":
            inner2.append((r, j + 2))
        elif k == "fanL":
            inner2.append((2, j))
        else:
            inner2.append((hero.R - 3, j))
    inner2 = np.array(inner2)
    for i in range(L):
        X = hero.layer(i)
        R0[i] = X[loop[:, 0], loop[:, 1]]
        IN2[i] = X[inner2[:, 0], inner2[:, 1]]
        hmax[i] = X[:, jb:je + 1, 1].max()
    feat.set_growth(hmax)
    d_ac, th = ray_dirs(kind)
    # 修正01：帯の傾き σ の扇の列のならし。扇（錐の点から放射に出る列）は行 0 が同じ 1 点なので、隣の列の σ の差がそのまま横の傾きになる
    # （横の傾き ≈ dσ/dθ。5 列の中央値では 80° を超える三角形が出た）。扇の中は角度で広くならし（ガウス fan_smooth_cols 列）、倍率 fan_scale を掛け、
    # 扇の端から fan_blend_cols 列で前・後ろの列の値へ戻す。錐の点は継ぎ目の法線の検査の外（pl30_checks.seam）。
    fan = np.array([k[0] in ("fanL", "fanR") for k in kind])
    nonfan_idx = np.nonzero(~fan)[0]
    jj = np.arange(NL)
    dfan = np.min(np.minimum(np.abs(jj[:, None] - nonfan_idx[None, :]), NL - np.abs(jj[:, None] - nonfan_idx[None, :])), axis=1).astype(np.float64)
    wfan = S.smoothstep(dfan / float(B.get("fan_blend_cols", 12)))
    sig_cap = float(B.get("sigma_cap", 1.5))
    p_t = np.stack([R0[-1] @ t_ax, R0[-1] @ e_ax], 1)
    # 修正01：谷の縁のうねり（名前の付いた美術の誘導 pl30_trough_rim。Q16「浪前方缺少自然的凹陷」）。t* の主役波の谷は主役波のシートの中にあり
    # （前の縁から内へ 3〜6 m で底 −2〜−5.4 m、縁で 0）、海の帯は平ら（t* の σ は 0.1〜0.2）なので、谷の外の縁が継ぎ目の折れにしかならず読めない。
    # 前の列で、主役波の谷の深さ D に応じて、継ぎ目から s_rim の所を頂とする低いうねり h·x²·e^{1−x²}（x = s/s_rim。継ぎ目で 0、傾きも 0）を帯に足し、
    # 谷の外の縁を海の側に作る。育ちは主役波の頂の高さの比 g(τ) の grow_pow 乗。座席の船の支えの当て布はこの後に当てる（当て布の中は当て布が勝つ）。
    RM = B.get("rim", {"on": False})
    W_rim = np.zeros(NL)
    if RM.get("on"):
        Xt = hero.layer(L - 1)
        D = np.zeros(NL)
        for j, ((r, c_), (k, f)) in enumerate(zip(loop, kind)):
            if k == "front":
                D[j] = max(0.0, -float(Xt[r, max(jb, c_ - int(RM["depth_cols"])):c_ + 1, 1].min()))
        W_rim = S.smoothstep((D - RM["depth_min_m"]) / RM["depth_full_m"])
        W_rim = np.clip(gaussian_filter1d(W_rim, float(RM["smooth_cols"]), mode="wrap"), 0.0, 1.0)
        rim_rec = dict(W=[round(float(v), 4) for v in W_rim], D=[round(float(v), 3) for v in D], s_rim_m=RM["s_rim_m"], h_m=RM["h_m"], grow_pow=RM["grow_pow"],
                       note_ja="列 j（ds30_ring0_index.json の順）の谷の縁のうねりの重み W と、主役波の t* の谷の深さ D（前の列の、境から depth_cols 列の内の最も低い y の負）。")
    q_out = ray_to_stadium(p_t, d_ac, kind, G)
    if fs > 1:
        q_lin = q_out.copy()
        for m in range(0, NL, fs):
            j0, j1 = m, (m + fs) % NL
            for kk in range(1, fs):
                s = kk / fs
                q_lin[m + kk] = (1 - s) * q_out[j0] + s * q_out[j1]
        q_out = q_lin
    out_xz = q_out[:, 0:1] * t_ax[[0, 2]][None, :] + q_out[:, 1:2] * e_ax[[0, 2]][None, :]
    zeta, rows_rec = row_layout(P, feat, p_t, q_out, NL)
    NR = zeta.shape[0]
    NC = NL + 1
    # 修正01：σ のならしを列の数ではなく弧長で行う。t* の継ぎ目から arc_ref_s_m の点を結ぶ輪の弧長 A_j の上に σ を一様に取り直し、
    # ガウス（sigma_arc_m）でならして戻す（錐の点のまわりの扇や、前・後ろの縁の列の詰まった所では隣の列が数 cm しか離れないので、
    # 列の数のならしでは横の傾きが残った）。谷の縁のうねりは、線分が継ぎ目に斜めに出る所（前の縁が c に対して斜めの所）で
    # 線分に沿う距離 s が継ぎ目からの垂直の距離より長いので、s_rim を 1/sinθ 倍して垂直の距離で同じ形にする。
    xz0t = R0[-1][:, [0, 2]]
    dir_t = out_xz - xz0t
    dir_t = dir_t / np.maximum(np.linalg.norm(dir_t, axis=1, keepdims=True), 1e-9)
    Pref = xz0t + dir_t * float(B.get("arc_ref_s_m", 2.5))
    segA = np.linalg.norm(np.diff(np.vstack([Pref, Pref[:1]]), axis=0), axis=1)
    Acum = np.concatenate([[0.0], np.cumsum(segA)])
    Aper = float(Acum[-1])
    nA = int(max(256, round(Aper / 0.05)))
    Agrid = np.linspace(0.0, Aper, nA, endpoint=False)
    sig_arc = float(B.get("sigma_arc_m", 0.0))

    def smooth_arc(v):
        if sig_arc <= 0:
            return v
        vg = np.interp(Agrid, Acum, np.concatenate([v, v[:1]]), period=Aper)
        vg = gaussian_filter1d(vg, sig_arc / (Aper / nA), mode="wrap")
        return np.interp(Acum[:-1], np.concatenate([Agrid, [Aper]]), np.concatenate([vg, vg[:1]]))
    Tg = np.roll(xz0t, -1, axis=0) - np.roll(xz0t, 1, axis=0)
    Tl = np.linalg.norm(Tg, axis=1)
    sin_th = np.where(Tl > 1e-4, np.abs(Tg[:, 0] * dir_t[:, 1] - Tg[:, 1] * dir_t[:, 0]) / np.maximum(Tl, 1e-9), 1.0)
    sin_th = np.clip(gaussian_filter1d(sin_th, 4.0, mode="wrap"), float(B.get("rim_sin_min", 0.3)), 1.0)
    print("rows", NR, "ridge cols w>0.5:", int((np.array(rows_rec["weight"]) > 0.5).sum()), round(time.time() - t0, 1), "s")
    wk = os.path.join(REPO, "Unity", "Build", "Polish", "30", "_work")
    os.makedirs(wk, exist_ok=True)
    near = np.memmap(os.path.join(wk, "near_f64.tmp"), dtype=np.float64, mode="w+", shape=(L, NR, NC, 3))
    diag = dict(sigma_abs_max=0.0)
    BS = P["features"]["ds30_boat_support"]
    for i in range(L):
        tau = float(knots[i])
        O = hero.origin(tau)
        r0 = R0[i]
        xz0 = r0[:, [0, 2]]
        Pxz = xz0[None, :, :] + (out_xz[None, :, :] - xz0[None, :, :]) * zeta[:, :, None]      # (NR, NL, 2)
        s_m = np.linalg.norm(Pxz - xz0[None], axis=-1)
        g_xz = xz0 - IN2[i][:, [0, 2]]
        gl = np.linalg.norm(g_xz, axis=1)
        dirw = out_xz - xz0
        dl = np.maximum(np.linalg.norm(dirw, axis=1), 1e-9)
        cosang = np.where(gl > 1e-3, (g_xz * dirw).sum(1) / (np.maximum(gl, 1e-9) * dl), 0.0)
        sig = np.where(gl > 1e-3, (r0[:, 1] - IN2[i][:, 1]) / np.maximum(gl, 1e-9), 0.0) * np.clip(cosang, 0.0, 1.0)
        sp = np.stack([np.roll(sig, k) for k in (-2, -1, 0, 1, 2)], 0)
        sig = np.clip(np.median(sp, axis=0), -sig_cap, sig_cap)
        # 扇の中だけ弧長でならして fan_scale 倍し、扇の端から fan_blend_cols 列で元の値へ戻す（扇の外の列＝錐の点の隣の列は継ぎ目の法線の検査の内なので、元のまま）
        sig = (1.0 - wfan) * sig + wfan * smooth_arc(sig) * float(B.get("fan_scale", 1.0))
        diag["sigma_abs_max"] = max(diag["sigma_abs_max"], float(np.abs(sig).max()))
        ell = np.where(sig[None, :] < 0, B.get("slope_decay_neg_m", B["slope_decay_m"]), B["slope_decay_m"])
        base = r0[None, :, 1] + sig[None, :] * s_m * np.exp(-s_m / ell)
        wx = Pxz[..., 0] + O[0]
        wz = Pxz[..., 1] + O[2]
        Ts = sea.eta(wx, wz, tau, knot=i)
        a_l = Pxz[..., 0] * t_ax[0] + Pxz[..., 1] * t_ax[2]
        c_l = Pxz[..., 0] * e_ax[0] + Pxz[..., 1] * e_ax[2]
        Fv = feat.total(a_l, c_l, i)
        wc = S.smootherstep(s_m / B["carrier_blend_m"])
        wf = S.smootherstep(s_m / B["feature_blend_m"])
        y = (1 - wc) * base + wc * Ts + wf * Fv
        if RM.get("on"):
            xr = s_m * sin_th[None, :] / float(RM["s_rim_m"])
            # 地形の誘導（右の高い波・小波など）の t* の高さのある所では付けない（滑らかに 0 へ。右の高い波の稜の上に足すと原画視点で富士の雪を隠した）。
            # 座席の船の当て布の中は、当て布が y を竜骨へ引くので、ここでは切らない（切り替えると形成の途中で頂点が当て布へ入る時に跳ぶ）。
            fts = feat.total_tstar(a_l, c_l)
            # 座席の船の竜骨の線からの平面図の距離 boat_off_m[0]〜[1] で滑らかに 0 へ（当て布の稜・溝を増やさない）
            bdk = feat.sample_clamped(a_l, c_l, "boat_dk")
            bo = RM.get("boat_off_m", [4.0, 8.0])
            wrim = W_rim[None, :] * (1.0 - S.smoothstep(fts / float(RM.get("feature_off_m", 1.0)))) * S.smoothstep((bdk - bo[0]) / (bo[1] - bo[0]))
            y = y + (feat.growth_knots[i] ** float(RM["grow_pow"])) * wrim * float(RM["h_m"]) * xr * xr * np.exp(1.0 - xr * xr)
        if BS["on"] and BS.get("mode") == "patch":
            wB = feat.sample(a_l, c_l, "boat_w") * S.smootherstep(s_m / BS["patch_seam_m"])
            yk = feat.sample(a_l, c_l, "boat_y")
            y = y + wB * (feat.growth_right_knots[i] * yk - y)
        near[i, :, :NL, 0] = Pxz[..., 0]
        near[i, :, :NL, 1] = y
        near[i, :, :NL, 2] = Pxz[..., 1]
        near[i, 0, :NL] = r0
        near[i, :, NL] = near[i, :, 0]
    Xt = near[-1]
    fn = np.cross(Xt[1:, :-1] - Xt[:-1, :-1], Xt[:-1, 1:] - Xt[:-1, :-1])
    up_frac = float((fn[..., 1] > 0).mean())
    if up_frac < 0.5:
        raise SystemExit("輪の向きが逆です（+y の割合 %.3f）。" % up_frac)
    print("near done", round(time.time() - t0, 1), "s")
    # 遠い海：行 0 は近い海の外周の fs 列おき（fs = 1 なら全部の列）
    NF = NL // fs
    FC = NF + 1
    FR = int(G["far_ring_count"]) + 1
    AF, AB, CR, CL = G["stadium_a_front_m"], G["stadium_a_back_m"], G["stadium_c_right_m"], G["stadium_c_left_m"]
    cen_ac = np.array([0.5 * (AF + AB), 0.5 * (CR + CL)])
    cen_xz = cen_ac[0] * t_ax[[0, 2]] + cen_ac[1] * e_ax[[0, 2]]
    inn = out_xz[::fs][:NF]
    ang = np.arctan2(inn[:, 1] - cen_xz[1], inn[:, 0] - cen_xz[0])
    Rf = float(G["far_radius_m"])
    outer_f = cen_xz[None, :] + Rf * np.stack([np.cos(ang), np.sin(ang)], 1)
    nring = int(G["far_ring_count"])
    zf = (np.geomspace(1.0, 1.0 + 30.0, nring) - 1.0) / 30.0
    zf[0] = 0.0; zf[-1] = 1.0
    far = np.memmap(os.path.join(wk, "far_f64.tmp"), dtype=np.float64, mode="w+", shape=(L, FR, FC, 3))
    for i in range(L):
        tau = float(knots[i])
        O = hero.origin(tau)
        Pxz = inn[None] + (outer_f - inn)[None] * zf[:, None, None]
        rad = np.linalg.norm(Pxz - cen_xz[None, None], axis=-1)
        taper = 1.0 - S.smoothstep((rad - G["far_taper_start_m"]) / (G["far_taper_end_m"] - G["far_taper_start_m"]))
        Ts = sea.eta(Pxz[..., 0] + O[0], Pxz[..., 1] + O[2], tau, knot=i)
        a_l = Pxz[..., 0] * t_ax[0] + Pxz[..., 1] * t_ax[2]
        c_l = Pxz[..., 0] * e_ax[0] + Pxz[..., 1] * e_ax[2]
        Fv = feat.total(a_l, c_l, i)
        y = taper * Ts + Fv
        far[i, :nring, :NF, 0] = Pxz[..., 0]
        far[i, :nring, :NF, 1] = y
        far[i, :nring, :NF, 2] = Pxz[..., 1]
        far[i, 0, :NF] = near[i, -1, 0:NL:fs]
        far[i, nring - 1, :NF, 1] = 0.0
        far[i, nring, :NF] = far[i, nring - 1, :NF]
        far[i, nring, :NF, 1] = G["skirt_depth_m"]
        far[i, :, NF] = far[i, :, 0]
    fnf = np.cross(far[-1][1:, :-1] - far[-1][:-1, :-1], far[-1][:-1, 1:] - far[-1][:-1, :-1])
    up_far = float((fnf[:-1, :, 1] > 0).mean())
    print("far done", round(time.time() - t0, 1), "s")
    log = dict(number="仕上げ30", seconds=round(time.time() - t0, 1), ring0_count=NL, near_rows=NR, near_cols=NC,
               far_rows=FR, far_cols=FC, far_subsample=fs, near_up_fraction_tstar=up_frac, far_up_fraction_tstar_excluding_skirt=up_far,
               growth_knots=[float(v) for v in feat.growth_knots], growth_right_knots=[float(v) for v in feat.growth_right_knots],
               lag_knots=[float(v) for v in feat.lag_knots], hero_hmax_knots=[float(v) for v in hmax],
               growth_shoulder_knots=[float(v) for v in feat.growth_shoulder_knots], shoulder_raise_on=bool("shoulder_raise" in feat.r),
               small_apex=dict(a=feat.small["a"], c=feat.small["c"], h=feat.small["h"], world=[float(v) for v in feat.small["world"]],
                               ray_from=feat.small["ray_from"], ray_through=feat.small["ray_through"]),
               stadium=dict(a_front=AF, a_back=AB, c_right=CR, c_left=CL, center_ac=cen_ac.tolist()), diag=diag,
               near_y_range=[float(min(near[i, :, :, 1].min() for i in range(L))), float(max(near[i, :, :, 1].max() for i in range(L)))],
               far_y_range_excluding_skirt=[float(min(far[i, :-1, :, 1].min() for i in range(L))), float(max(far[i, :-1, :, 1].max() for i in range(L)))])
    print(json.dumps({k: v for k, v in log.items() if not k.endswith("knots")}, ensure_ascii=False)[:1500])
    if args.no_write:
        return
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    idx = [dict(near_col=int(j), hero_row=int(r), hero_col=int(c), ray=kind[j][0]) for j, (r, c) in enumerate(loop)]
    psha = S.sha256_file(args.params)
    ex_near = dict(
        role_ja="近い海：接続帯と、右の高い波・肩の稜・手前の小波・谷の続き・船の支え。行 0 は主役波（G_p28rec）の本体の境の輪の頂点そのもの。",
        ring0_ja="近い海の列 j（0 ≤ j < %d）の行 0 は、主役波の（行, 列）= ds30_ring0_index.json の j 番目。列 %d は列 0 の写し。" % (NL, NL),
        hero_draw_ja="主役波は本体の列 %d〜%d の四角だけを描く。" % (jb, je),
        far_seam_ja="外周（最後の行）の列 j は、遠い海の行 0 の列 j/%d と同じ位置（fs = %d。T 字なし）。" % (fs, fs),
        rows_file="pl30_rows.json", stadium=log["stadium"], y_min_m=log["near_y_range"][0], y_max_m=log["near_y_range"][1],
        features=P["features"], small_apex=log["small_apex"], growth_knots=log["growth_knots"], growth_right_knots=log["growth_right_knots"],
        band=P["band"], params=os.path.relpath(args.params, REPO).replace("\\", "/"), params_sha256=psha,
        code_sha256={f: S.sha256_file(os.path.join(HERE, f)) for f in ("pl30_sea.py", "pl30_sea_generate.py")})

    def class_of(X):
        a_l = X[..., 0] * t_ax[0] + X[..., 2] * t_ax[2]
        c_l = X[..., 0] * e_ax[0] + X[..., 2] * e_ax[2]
        r = feat.sample(a_l, c_l, "right")
        s = feat.sample(a_l, c_l, "small")
        cl = np.zeros(X.shape[:2], np.uint8)
        cl[(r >= 0.5) & (X[..., 1] >= 0.5)] = 1
        cl[(s >= 0.5) & (X[..., 1] >= 0.5)] = 2
        return cl
    cln = class_of(near[-1]); cln[0] = 0
    m1 = write_package(os.path.join(out, "near"), "near", near, hero, ex_near, twhite=None, cls=cln)
    S.save_json(os.path.join(out, "near", "ds30_ring0_index.json"), dict(loop=idx, body_cols=[jb, je]), indent=None)
    S.save_json(os.path.join(out, "near", "pl30_rows.json"), rows_rec, indent=None)
    if RM.get("on"):
        rim_rec["sin_theta"] = [round(float(v), 4) for v in sin_th]
        rim_rec["note_sin_ja"] = "列ごとの sinθ（線分と継ぎ目の接線の角）。谷の縁のうねりの頂は線分に沿って s_rim/sinθ の所。"
        S.save_json(os.path.join(out, "near", "pl30_rim.json"), rim_rec, indent=None)
    uv2n = np.zeros((NR, NC, 2))
    uv2n[..., 0] = near[-1][..., 0] * t_ax[0] + near[-1][..., 2] * t_ax[2]
    uv2n[..., 1] = near[-1][..., 0] * e_ax[0] + near[-1][..., 2] * e_ax[2]
    write_gwb(os.path.join(out, "near", "ds30_tstar.gwb"), near[-1] + hero.origin(0.0)[None, None, :], NR, NC, uv2n)
    ex_far = dict(role_ja="遠い海：近い海の外周から半径 %.0f m の円まで。外周は y = 0、最後の行は y = %.1f のすそ。" % (Rf, G["skirt_depth_m"]),
                  near_seam_ja="行 0 の列 k（k < %d）は近い海の外周の列 %d·k と同じ。列 %d は列 0 の写し。" % (NF, fs, NF),
                  y_min_m=log["far_y_range_excluding_skirt"][0], y_max_m=log["far_y_range_excluding_skirt"][1], ring_zeta=[float(v) for v in zf],
                  params=os.path.relpath(args.params, REPO).replace("\\", "/"), params_sha256=psha)
    clf = class_of(far[-1])
    m2 = write_package(os.path.join(out, "far"), "far", far, hero, ex_far, twhite=None, cls=clf)
    uv2f = np.zeros((FR, FC, 2))
    uv2f[..., 0] = far[-1][..., 0] * t_ax[0] + far[-1][..., 2] * t_ax[2]
    uv2f[..., 1] = far[-1][..., 0] * e_ax[0] + far[-1][..., 2] * e_ax[2]
    write_gwb(os.path.join(out, "far", "ds30_tstar.gwb"), far[-1] + hero.origin(0.0)[None, None, :], FR, FC, uv2f)
    sf = dict(schema="GreatWave.PL30.sea_function/1", number="仕上げ30",
              formula_ja="η(x, z, τ) = taper(r)·[κ_c(τ)·A_c(c, τ)·Σ_car amp·cos(kx·(x − Ox) + kz·(z − Oz) − ω·τ + φ) + κ_s(τ)·Σ_swell（同じ形）] + F(a, c, τ)。"
                         "c = (x − Ox)·e_x + (z − Oz)·e_z、a = (x − O_x(τ))·t_x + (z − O_z(τ))·t_z（O(τ) は主役波の frame.origin の線形補間）。"
                         "A_c は ds27_sea.npz の Ac_knots（節点 × 行）を τ・c で線形に補い、c の範囲の外は端の値 × exp(−(Δc/%.0f)²)。κ_c・κ_s は calm（1 − smoothstep）。"
                         "F(a, c, τ) = g_r(τ)·F_right(a, c) + g(τ)·(F_small + F_trough)（pl30_sea.py の Features.total。F は t* の形を raster に作ったもの、g・g_r は growth_knots・growth_right_knots の線形補間）。"
                         "修正02：肩の稜の上り口を高くした足し分 F_raise がある時は g_r(τ)·(F_right − F_raise) + g_sh(τ)·F_raise（g_sh は growth_shoulder_knots）。"
                         "taper(r)：遠い海だけ。r は競技場の中心 center_ac からの水平の距離、taper = 1 − smoothstep((r − %.0f)/(%.0f − %.0f))（設計30 の限界 7 で式の記録になかったもの）。"
                         "主役波のシートの内側と接続帯（輪 0 から 10 m）、座席の船の支えの当て布の中では、式ではなくシートを読む。"
                         % (P["sea"]["Ac_lateral_taper_m"], G["far_taper_start_m"], G["far_taper_end_m"], G["far_taper_start_m"]),
              reference_impl="Tools/GWWaveGen/pl30/pl30_sea.py（sea_eta。taper は pl30_sea_generate.py の遠い海）", focus_world=hero.sea_model["focus_world"],
              e_crest=hero.e.tolist(), t_travel=hero.t.tolist(), carrier=hero.sea_model["carrier"], swell=hero.sea_model["swell"],
              calm=hero.sea_model["calm"], Ac_source=dict(file=os.path.relpath(os.path.join(hero.dir, "ds27_sea.npz"), REPO).replace("\\", "/"),
                                                        sha256=sea.sea_npz_sha, keys=["knot_tau", "c", "Ac_knots"]),
              frame_origin_source=dict(file=os.path.relpath(hero.jp, REPO).replace("\\", "/"), key="frame"),
              far_taper=dict(center_ac=cen_ac.tolist(), start_m=G["far_taper_start_m"], end_m=G["far_taper_end_m"]),
              features=P["features"], small_apex=log["small_apex"], knot_tau=hero.k["knot_tau"], growth_knots=log["growth_knots"],
              growth_right_knots=log["growth_right_knots"], growth_shoulder_knots=log["growth_shoulder_knots"], shoulder_raise_on=log["shoulder_raise_on"],
              Ac_lateral_taper_m=P["sea"]["Ac_lateral_taper_m"])
    S.save_json(os.path.join(out, "sea_function.json"), sf)
    np.savez_compressed(os.path.join(out, "pl30_feature_raster.npz"), a=feat.ra, c=feat.rc, **{k: v.astype(np.float32) for k, v in feat.r.items()})
    log["near"] = dict(pos_sha256=m1["pos_sha256"], pos_lo_sha256=m1["pos_lo_sha256"], bbox_size=m1["bbox_size"], precision=m1["pos_precision"], gpu=m1["gpu_estimate"])
    log["far"] = dict(pos_sha256=m2["pos_sha256"], pos_lo_sha256=m2["pos_lo_sha256"], bbox_size=m2["bbox_size"], precision=m2["pos_precision"], gpu=m2["gpu_estimate"])
    log["shoulder_path"] = {k: [float(v) for v in vv[::20]] for k, vv in getattr(feat, "shoulder_path", {}).items()}
    log["params_sha256"] = psha
    log["seconds"] = round(time.time() - t0, 1)
    S.save_json(os.path.join(out, "pl30_generate_log.json"), log)
    for arr, nm in ((near, "near_f64.tmp"), (far, "far_f64.tmp")):
        arr._mmap.close()
        os.remove(os.path.join(wk, nm))
    print("written", out, log["seconds"], "s")


if __name__ == "__main__":
    main()
