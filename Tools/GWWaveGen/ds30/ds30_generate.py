# -*- coding: utf-8 -*-
"""設計30：周りの海のシート（DS27 の書式、主役波と同じ knot_tau と波の枠）を作る。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/ds30/ds30_generate.py [--out Unity/Build/Design/30/sea]
（配置の一次設計（参照モデルの配置に合わせた数値）は ds30_layout.py の記録と図だけで、パッケージは二次設計だけを作る）
出力（Git 対象外）:
    <out>/near/  ds27_keypose.json・ds27_pos_rgba16.bin・ds27_pos_lo_rgba8.bin・ds27_twhite_r32f.bin・ds30_tstar.gwb・ds30_ring0_index.json
    <out>/far/   同じ（ds30_ring0_index.json の代わりに近い海の外周との対応）
    <out>/sea_function.json   設計43 の船が読む式（成分・焦点・A_c の表の出典・静める係数・地形の誘導・育つ係数）
    <out>/ds30_generate_log.json
網の約束（第B部の README_interface.txt と同じ）：
    行 r = 輪（0 が内側）、列 = 外周を一周（最後の列は最初の列の写し）。四角 (r,c)(r+1,c)(r,c+1)(r+1,c+1) を
    (r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1) に割る（主役波と同じ）。この並びで外積 (P[r+1,c]−P[r,c])×(P[r,c+1]−P[r,c])
    が +y を向く（主役波と同じ向き）。
"""
import argparse
import json
import math
import os
import struct
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds30_sea as S  # noqa: E402

REPO = S.REPO


def ring0_loop(jb, je, rows):
    """主役波の本体の境の輪（行, 列）と、各点の線分の向きの種類。"""
    L, kind = [], []
    for j in range(jb, je + 1):          # 行 0（左の錐の点）：扇（後ろ −t → −e → 前 +t）
        L.append((0, j)); kind.append(("fanL", (j - jb) / (je - jb)))
    for r in range(1, rows):             # 列 je（前の縁）：+t
        L.append((r, je)); kind.append(("front", 0.0))
    n_r = je - jb                        # 行 rows−1 の列 je−1 → jb（右の錐の点）：扇（前 +t → +e → 後ろ −t）
    for k, j in enumerate(range(je - 1, jb - 1, -1)):
        L.append((rows - 1, j)); kind.append(("fanR", (k + 1) / n_r))
    for r in range(rows - 2, 0, -1):     # 列 jb（後ろの縁）：−t
        L.append((r, jb)); kind.append(("back", 0.0))
    return np.array(L, np.int64), kind


def ray_dirs(kind):
    """(a, c) の平面の単位の向き。"""
    th = np.zeros(len(kind))
    for i, (k, f) in enumerate(kind):
        if k == "front":
            th[i] = 0.0
        elif k == "back":
            th[i] = math.pi
        elif k == "fanL":
            th[i] = math.pi + math.pi * f
        else:
            th[i] = math.pi * f
    return np.stack([np.cos(th), np.sin(th)], 1), th


def ray_to_stadium(p, d, kind, G):
    """t* の輪の点 p=(a, c) から向き d の線分が競技場形の外周に当たる点。"""
    AF, AB, CR, CL = G["stadium_a_front_m"], G["stadium_a_back_m"], G["stadium_c_right_m"], G["stadium_c_left_m"]
    am = 0.5 * (AF + AB)
    ra = 0.5 * (AF - AB)
    out = np.zeros_like(p)
    for i in range(len(p)):
        k = kind[i][0]
        a, c = p[i]
        da, dc = d[i]
        if k == "front":
            out[i] = (AF, c)
        elif k == "back":
            out[i] = (AB, c)
        else:
            c0, rc = (15.0, CR - 15.0) if k == "fanR" else (-60.0, -60.0 - CL)
            # 半楕円 ((a−am)/ra)² + ((c−c0)/rc)² = 1 と、p + λ d の交点（λ > 0）
            A = (da / ra) ** 2 + (dc / rc) ** 2
            B = 2 * ((a - am) * da / ra ** 2 + (c - c0) * dc / rc ** 2)
            Cq = ((a - am) / ra) ** 2 + ((c - c0) / rc) ** 2 - 1.0
            lam = (-B + math.sqrt(B * B - 4 * A * Cq)) / (2 * A)
            out[i] = (a + lam * da, c + lam * dc)
    return out


def quantize(X, bmin, bsz):
    u = (X - bmin) / bsz * 65535.0
    q = np.clip(np.round(u), 0, 65535)
    e = u - q
    lo = np.clip(np.round((e + 0.5) * 255.0), 0, 255)
    return q.astype(np.uint16), lo.astype(np.uint8)


def write_package(outdir, name, Xl, hero, extra, twhite=None, cls=None):
    """Xl：(層, 行, 列, 3) の局所座標（ワールド − O(τ)）。DS27 の書式で書く。"""
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
        schema="GreatWave.DS27.keypose/1", schema_ds30="GreatWave.DS30.seasheet/1", number="設計30", version=name,
        layers=Lr, rows=R, cols=C, bbox_min=[float(v) for v in bmin], bbox_size=[float(v) for v in bsz],
        knot_tau=k["knot_tau"], t_star_layer=Lr - 1,
        frame=dict(tau=k["frame"]["tau"], origin=k["frame"]["origin"], hz=k["frame"]["hz"],
                   note_ja="主役波（F_final/art_on）の frame と同じ配列。海のシートは波の枠とともに動く切り抜き。"),
        pos_file="ds27_pos_rgba16.bin", pos_sha256=h1.hexdigest(), pos_bytes=os.path.getsize(hp),
        pos_format_ja=k["pos_format_ja"],
        pos_lo_file="ds27_pos_lo_rgba8.bin", pos_lo_sha256=h2.hexdigest(), pos_lo_bytes=os.path.getsize(lp),
        pos_lo_format_ja=k["pos_lo_format_ja"], extensions=["pos_lo_rgba8/1", "ds30_grid/1"],
        pos_precision=dict(hi_step_mm=float(bsz.max() / 65535 * 1000), max_err_hi_m=maxerr_hi, max_err_fine_m=maxerr_fine),
        twhite_file="ds27_twhite_r32f.bin", twhite_sha256=S.sha256_file(tp), twhite_bytes=len(tw), twhite_never=1.0e9,
        twhite_format_ja="R32F、行 × 列。τ ≥ T_white で白（ds30_class_u8.bin が 1 のテクセルだけ。地形の誘導の上の面）。高い所ほど早い：g(τ)·F ≥ min(3 m, 0.8·F) になる最初の節点の τ（F は t* の地形の誘導の高さ）。+1e9 = 白にならない（海）。",
        class_file=("ds30_class_u8.bin" if cls is not None else None),
        class_format_ja="uint8、行 × 列。t* の色区の手がかり：0 = 海（藍濃 ai_dark）、1 = 地形の誘導の上の面（白。右の高い波・手前の小波の t* の高さ ≥ 0.5 m）。仮置き（上面が白）の像に合わせるための手がかりで、原画の色区の焼き付けではない。",
        interpolation_ja=k["interpolation_ja"],
        grid_ja="行 r = 輪（0 が内側）、列 = 外周を一周（最後の列は最初の列の写し）。四角 (r,c)(r+1,c)(r,c+1)(r+1,c+1) を (r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1) の 2 つの三角形に割る（主役波と同じ）。",
        winding_ja="この並びで外積 (P[r+1,c] − P[r,c]) × (P[r,c+1] − P[r,c]) は +y（上）を向く（主役波の格子と同じ約束。DS27 の再生器・シェーダーの法線の式がそのまま使える）。",
        gpu_estimate=dict(layer_mib=R * C * 8 / 2 ** 20, rgba16_mib=Lr * R * C * 8 / 2 ** 20, rgba8_mib=Lr * R * C * 4 / 2 ** 20,
                          packed_hi_plus_lo_mib=Lr * R * C * 12 / 2 ** 20),
        hero_package=os.path.relpath(hero.dir, REPO).replace("\\", "/"), hero_sha256=hero.sha(),
    )
    meta.update(extra)
    S.save_json(os.path.join(outdir, "ds27_keypose.json"), meta)
    return meta


def write_gwb(path, P, rows, cols, uv2):
    """t* の網（GWW0 の書式：K* の .gwb と同じ。頂点はワールド）。"""
    n = rows * cols
    r, c = np.meshgrid(np.arange(rows - 1), np.arange(cols - 1), indexing="ij")
    a = (r * cols + c).ravel(); b = ((r + 1) * cols + c).ravel(); cc = (r * cols + c + 1).ravel(); d = ((r + 1) * cols + c + 1).ravel()
    tris = np.stack([np.stack([a, b, cc], 1), np.stack([cc, b, d], 1)], 1).reshape(-1, 3).astype(np.int32)
    rr, ccg = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    uv = np.stack([ccg / (cols - 1), rr / (rows - 1)], -1).reshape(-1, 2).astype(np.float32)
    with open(path, "wb") as f:
        f.write(b"GWW0" + struct.pack("<4i", 1, cols, rows, 1) + struct.pack("<f", 30.0) + struct.pack("<2i", 0, len(tris)))
        f.write(uv.tobytes()); f.write(uv2.reshape(-1, 2).astype(np.float32).tobytes()); f.write(tris.tobytes())
        f.write(P.reshape(-1, 3).astype(np.float32).tobytes())
    return len(tris)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Unity/Build/Design/30/sea")
    ap.add_argument("--variant", default="second", choices=["second"])
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    P = S.load_json(S.PARAMS)
    G = P["grid"]
    B = P["band"]
    hero = S.Hero()
    sea = S.Sea(hero)
    feat = S.Features(hero, P)
    jb, je = P["hero"]["body_cols"]
    loop, kind = ring0_loop(jb, je, hero.R)
    # 列の順は ring0_loop の逆（この順で面の外積が +y を向く。t* で確かめる）
    loop, kind = loop[::-1].copy(), kind[::-1]
    NL = len(loop)
    fs = int(G["far_subsample"])
    assert NL % fs == 0, (NL, fs)
    L = hero.L
    knots = hero.knots
    t_ax, e_ax = hero.t, hero.e
    # 1) 主役波の輪 0 と内側の隣（各節点）、頂の高さ
    R0 = np.zeros((L, NL, 3)); IN = np.zeros((L, NL, 3)); IN2 = np.zeros((L, NL, 3)); hmax = np.zeros(L)
    inner = []; inner2 = []
    for (r, j), (k, f) in zip(loop, kind):
        if k == "front":
            inner.append((r, j - 1)); inner2.append((r, j - 2))
        elif k == "back":
            inner.append((r, j + 1)); inner2.append((r, j + 2))
        elif k == "fanL":
            inner.append((1, j)); inner2.append((2, j))
        else:
            inner.append((hero.R - 2, j)); inner2.append((hero.R - 3, j))
    inner = np.array(inner); inner2 = np.array(inner2)
    for i in range(L):
        X = hero.layer(i)
        R0[i] = X[loop[:, 0], loop[:, 1]]
        IN[i] = X[inner[:, 0], inner[:, 1]]
        IN2[i] = X[inner2[:, 0], inner2[:, 1]]
        hmax[i] = X[:, jb:je + 1, 1].max()
    feat.set_growth(hmax)
    # 2) 線分の向きと外周（t* の輪から、局所の (a, c)）
    d_ac, th = ray_dirs(kind)
    p_t = np.stack([R0[-1] @ t_ax, R0[-1] @ e_ax], 1)
    q_out = ray_to_stadium(p_t, d_ac, kind, G)
    # 遠い海の継ぎ目：外周の 5 点おきの間は線形に補う
    q_lin = q_out.copy()
    for m in range(0, NL, fs):
        j0, j1 = m, (m + fs) % NL
        for kk in range(1, fs):
            s = kk / fs
            q_lin[m + kk] = (1 - s) * q_out[j0] + s * q_out[j1]
    q_out = q_lin
    out_xz = q_out[:, 0:1] * t_ax[[0, 2]][None, :] + q_out[:, 1:2] * e_ax[[0, 2]][None, :]   # 局所の (x, z)
    zeta = np.array(G["near_ring_s_m"], np.float64) / float(G["near_ring_s_ref_m"])
    zeta[-1] = 1.0
    NR = len(zeta)
    NC = NL + 1
    # 作業の配列はファイルに裏付けた memmap（Git 対象外の Unity/Build/Design/30/_work。PC のコミットの余裕が小さいので RAM に持たない）
    wk = os.path.join(REPO, "Unity", "Build", "Design", "30", "_work")
    os.makedirs(wk, exist_ok=True)
    near = np.memmap(os.path.join(wk, "near_f64.tmp"), dtype=np.float64, mode="w+", shape=(L, NR, NC, 3))
    diag = dict(sigma_abs_max=0.0)
    for i in range(L):
        tau = float(knots[i])
        O = hero.origin(tau)
        r0 = R0[i]
        xz0 = r0[:, [0, 2]]
        Pxz = xz0[None, :, :] + (out_xz[None, :, :] - xz0[None, :, :]) * zeta[:, None, None]      # (NR, NL, 2)
        s_m = np.linalg.norm(Pxz - xz0[None], axis=-1)
        # 外向きの傾き σ（主役波の格子の 2 つ内側の点までの弦から、線分の向きへの成分。修正1：1 つ内側の点だけでは、主役波の後ろの足の
        # 行 44〜45 の τ −5.7 s ごろに隣の点が 0.2 m 未満に寄って σ が ±3 に振れ、帯が 1 コマで 3 m 跳んだ。輪に沿って 5 点の中央値でならし ±1.5 に抑える）
        g_xz = xz0 - IN2[i][:, [0, 2]]
        gl = np.linalg.norm(g_xz, axis=1)
        dirw = out_xz - xz0
        dl = np.maximum(np.linalg.norm(dirw, axis=1), 1e-9)
        cosang = np.where(gl > 1e-3, (g_xz * dirw).sum(1) / (np.maximum(gl, 1e-9) * dl), 0.0)
        sig = np.where(gl > 1e-3, (r0[:, 1] - IN2[i][:, 1]) / np.maximum(gl, 1e-9), 0.0) * np.clip(cosang, 0.0, 1.0)
        sp = np.stack([np.roll(sig, k) for k in (-2, -1, 0, 1, 2)], 0)
        sig = np.clip(np.median(sp, axis=0), -1.5, 1.5)
        diag["sigma_abs_max"] = max(diag["sigma_abs_max"], float(np.abs(sig).max()))
        base = r0[None, :, 1] + sig[None, :] * s_m * np.exp(-s_m / B["slope_decay_m"])
        wx = Pxz[..., 0] + O[0]
        wz = Pxz[..., 1] + O[2]
        Ts = sea.eta(wx, wz, tau, knot=i)
        a_l = Pxz[..., 0] * t_ax[0] + Pxz[..., 1] * t_ax[2]
        c_l = Pxz[..., 0] * e_ax[0] + Pxz[..., 1] * e_ax[2]
        shp = feat.shape(a_l, c_l)
        Fv = shp["total"] * feat.growth_knots[i]
        wc = S.smootherstep(s_m / B["carrier_blend_m"])
        wf = S.smootherstep(s_m / B["feature_blend_m"])
        if "boat_w" in shp:
            # 修正1：船の支えの所だけは地形の誘導の重みを 1 m で立ち上げる（4 m の帯では t* の竜骨の中ほどが水面より最大 2.0 m 浮いた。
            # 継ぎ目の折れは船体の下に隠れる所に限る）
            wf = np.maximum(wf, shp["boat_w"] * S.smootherstep(s_m / B.get("boat_blend_m", 1.0)))
        y = (1 - wc) * base + wc * Ts + wf * Fv
        near[i, :, :NL, 0] = Pxz[..., 0]
        near[i, :, :NL, 1] = y
        near[i, :, :NL, 2] = Pxz[..., 1]
        near[i, 0, :NL] = r0                              # 行 0 は主役波の頂点そのもの
        # 外周の 5 点おきの間は、両隣の線形補間（高さも）
        yo = near[i, -1, :NL, 1].copy()
        for m in range(0, NL, fs):
            j0, j1 = m, (m + fs) % NL
            for kk in range(1, fs):
                s = kk / fs
                yo[m + kk] = (1 - s) * yo[j0] + s * yo[j1]
        near[i, -1, :NL, 1] = yo
        near[i, :, NL] = near[i, :, 0]                    # 閉じる列
    # 向きの確かめ（t*、+y を向くか）
    Xt = near[-1]
    fn = np.cross(Xt[1:, :-1] - Xt[:-1, :-1], Xt[:-1, 1:] - Xt[:-1, :-1])
    up_frac = float((fn[..., 1] > 0).mean())
    flip_cols = up_frac < 0.5
    if flip_cols:
        raise SystemExit("輪の向きが逆です（+y の割合 %.3f）。" % up_frac)
    # 3) 遠い海
    NF = NL // fs
    FC = NF + 1
    FR = int(G["far_ring_count"]) + 1          # 最後の 1 行はすそ
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
        Pxz = inn[None] + (outer_f - inn)[None] * zf[:, None, None]     # (nring, NF, 2)
        rad = np.linalg.norm(Pxz - cen_xz[None, None], axis=-1)
        taper = 1.0 - S.smoothstep((rad - G["far_taper_start_m"]) / (G["far_taper_end_m"] - G["far_taper_start_m"]))
        Ts = sea.eta(Pxz[..., 0] + O[0], Pxz[..., 1] + O[2], tau, knot=i)
        a_l = Pxz[..., 0] * t_ax[0] + Pxz[..., 1] * t_ax[2]
        c_l = Pxz[..., 0] * e_ax[0] + Pxz[..., 1] * e_ax[2]
        Fv = feat.shape(a_l, c_l)["total"] * feat.growth_knots[i]
        y = taper * Ts + Fv
        far[i, :nring, :NF, 0] = Pxz[..., 0]
        far[i, :nring, :NF, 1] = y
        far[i, :nring, :NF, 2] = Pxz[..., 1]
        far[i, 0, :NF] = near[i, -1, 0:NL:fs]           # 行 0 は近い海の外周の 5 点おきそのもの
        far[i, nring - 1, :NF, 1] = 0.0                 # 外周は y = 0
        far[i, nring, :NF] = far[i, nring - 1, :NF]
        far[i, nring, :NF, 1] = G["skirt_depth_m"]      # すそ
        far[i, :, NF] = far[i, :, 0]
    fnf = np.cross(far[-1][1:, :-1] - far[-1][:-1, :-1], far[-1][:-1, 1:] - far[-1][:-1, :-1])
    up_far = float((fnf[:-1, :, 1] > 0).mean())
    log = dict(number="設計30", variant=args.variant, seconds=round(time.time() - t0, 1), ring0_count=NL, near_rows=NR, near_cols=NC,
               far_rows=FR, far_cols=FC, near_up_fraction_tstar=up_frac, far_up_fraction_tstar_excluding_skirt=up_far,
               growth_knots=[float(v) for v in feat.growth_knots], hero_hmax_knots=[float(v) for v in hmax],
               small_apex=dict(a=feat.small["a"], c=feat.small["c"], h=feat.small["h"], world=[float(v) for v in feat.small["world"]],
                               ray_from=feat.small["ray_from"], ray_through=feat.small["ray_through"]),
               stadium=dict(a_front=AF, a_back=AB, c_right=CR, c_left=CL, center_ac=cen_ac.tolist()), diag=diag,
               near_y_range=[float(min(near[i, :, :, 1].min() for i in range(L))), float(max(near[i, :, :, 1].max() for i in range(L)))],
               far_y_range_excluding_skirt=[float(min(far[i, :-1, :, 1].min() for i in range(L))), float(max(far[i, :-1, :, 1].max() for i in range(L)))])
    print(json.dumps({k: v for k, v in log.items() if k not in ("growth_knots", "hero_hmax_knots")}, ensure_ascii=False)[:1500])
    if args.no_write:
        return
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    idx = [dict(near_col=int(j), hero_row=int(r), hero_col=int(c), ray=kind[j][0]) for j, (r, c) in enumerate(loop)]
    ex_near = dict(
        role_ja="近い海：接続帯と、右の高い波・手前の小波・谷の続き・船の支え。行 0 は主役波の本体の境の輪の頂点そのもの。",
        ring0_ja="近い海の列 j（0 ≤ j < %d）の行 0 は、主役波の（行, 列）= ds30_ring0_index.json の j 番目。列 %d は列 0 の写し。" % (NL, NL),
        hero_draw_ja="主役波は本体の列 %d〜%d の四角だけを描く（列 0〜%d と %d〜399 の平らな余白は描かない）。" % (jb, je, jb - 1, je + 1),
        far_seam_ja="外周（最後の行）の列 j は、j が %d の倍数なら遠い海の行 0 の列 j/%d と同じ位置。その間の点は両隣の線形補間（各節点）。" % (fs, fs),
        ring_zeta=[float(v) for v in zeta], stadium=log["stadium"], y_min_m=log["near_y_range"][0], y_max_m=log["near_y_range"][1],
        features=P["features"], small_apex=log["small_apex"], growth_knots=log["growth_knots"], band=P["band"], variant=args.variant,
        params=os.path.relpath(S.PARAMS, REPO).replace("\\", "/"), params_sha256=S.sha256_file(S.PARAMS),
        code_sha256={f: S.sha256_file(os.path.join(HERE, f)) for f in ("ds30_sea.py", "ds30_generate.py")})
    def class_tw(X):
        """t* の色区の手がかりと T_white。高い所ほど早く白くなる：各頂点の t* の地形の誘導の高さ F について、
        g(τ)·F ≥ min(3.0 m, 0.8·F) になる最初の節点の τ（頂から裾へ白が広がる。一斉に白くならない）。"""
        a_l = X[..., 0] * t_ax[0] + X[..., 2] * t_ax[2]
        c_l = X[..., 0] * e_ax[0] + X[..., 2] * e_ax[2]
        sh = feat.shape(a_l, c_l)
        Fv = sh["right"] + sh["small"]
        cl = (Fv >= 0.5) & (X[..., 1] >= 0.5)
        thr = np.minimum(3.0, 0.8 * np.maximum(Fv, 1e-6))
        gk = feat.growth_knots
        tw = np.full(Fv.shape, 1.0e9)
        for idx_ in zip(*np.nonzero(cl)):
            ok = np.nonzero(gk * Fv[idx_] >= thr[idx_])[0]
            tw[idx_] = float(knots[ok[0]]) if len(ok) else 0.0
        return cl.astype(np.uint8), tw
    cln, twn = class_tw(near[-1])
    cln[0] = 0; twn[0] = 1.0e9
    ex_near["twhite_tau_s"] = float(twn[cln == 1].min()) if (cln == 1).any() else None
    m1 = write_package(os.path.join(out, "near"), "near", near, hero, ex_near, twhite=twn, cls=cln)
    S.save_json(os.path.join(out, "near", "ds30_ring0_index.json"), dict(loop=idx, body_cols=[jb, je]), indent=None)
    uv2n = np.zeros((NR, NC, 2))
    Xt = near[-1] + hero.origin(0.0)[None, None, :]
    uv2n[..., 0] = near[-1][..., 0] * t_ax[0] + near[-1][..., 2] * t_ax[2]
    uv2n[..., 1] = near[-1][..., 0] * e_ax[0] + near[-1][..., 2] * e_ax[2]
    write_gwb(os.path.join(out, "near", "ds30_tstar.gwb"), Xt, NR, NC, uv2n)
    ex_far = dict(role_ja="遠い海：近い海の外周から半径 %.0f m の円まで。外周は y = 0、最後の行は y = %.1f のすそ。" % (Rf, G["skirt_depth_m"]),
                  near_seam_ja="行 0 の列 k（k < %d）は近い海の外周の列 %d·k と同じ。列 %d は列 0 の写し。" % (NF, fs, NF),
                  y_min_m=log["far_y_range_excluding_skirt"][0], y_max_m=log["far_y_range_excluding_skirt"][1], ring_zeta=[float(v) for v in zf],
                  params=os.path.relpath(S.PARAMS, REPO).replace("\\", "/"), params_sha256=S.sha256_file(S.PARAMS), variant=args.variant)
    clf, twf = class_tw(far[-1])
    m2 = write_package(os.path.join(out, "far"), "far", far, hero, ex_far, twhite=twf, cls=clf)
    uv2f = np.zeros((FR, FC, 2))
    uv2f[..., 0] = far[-1][..., 0] * t_ax[0] + far[-1][..., 2] * t_ax[2]
    uv2f[..., 1] = far[-1][..., 0] * e_ax[0] + far[-1][..., 2] * e_ax[2]
    write_gwb(os.path.join(out, "far", "ds30_tstar.gwb"), far[-1] + hero.origin(0.0)[None, None, :], FR, FC, uv2f)
    # 設計43 の船が読む式
    sf = dict(schema="GreatWave.DS30.sea_function/1", number="設計30",
              formula_ja="η(x, z, τ) = κ_c(τ)·A_c(c, τ)·Σ_car amp·cos(kx·(x − Ox) + kz·(z − Oz) − ω·τ + φ) + κ_s(τ)·Σ_swell（同じ形）+ g(τ)·F(a, c)。"
                         "c = (x − Ox)·e_x + (z − Oz)·e_z、a = (x − O_x(τ))·t_x + (z − O_z(τ))·t_z（O(τ) は主役波の frame.origin の線形補間）。"
                         "A_c(c, τ)：hero の ds27_sea.npz の Ac_knots（節点 × 行、行の c は npz の c）を τ で線形・c で線形に補い、c の範囲の外は端の値 × exp(−(Δc/%.0f)²)。"
                         "κ_c・κ_s は calm（1 − smoothstep）。F は features（ds30_sea.py の Features.shape と同じ式）、g は growth_knots の線形補間。"
                         "主役波のシートの内側（本体の境の輪の中）と接続帯（輪 0 から 10 m）では式ではなくシートを読む。" % P["sea"]["Ac_lateral_taper_m"],
              reference_impl="Tools/GWWaveGen/ds30/ds30_sea.py（sea_eta）", focus_world=hero.sea_model["focus_world"],
              e_crest=hero.e.tolist(), t_travel=hero.t.tolist(), carrier=hero.sea_model["carrier"], swell=hero.sea_model["swell"],
              calm=hero.sea_model["calm"], Ac_source=dict(file=os.path.relpath(os.path.join(hero.dir, "ds27_sea.npz"), REPO).replace("\\", "/"),
                                                        sha256=sea.sea_npz_sha, keys=["knot_tau", "c", "Ac_knots"]),
              frame_origin_source=dict(file=os.path.relpath(hero.jp, REPO).replace("\\", "/"), key="frame"),
              features=P["features"], small_apex=log["small_apex"], knot_tau=hero.k["knot_tau"], growth_knots=log["growth_knots"],
              Ac_lateral_taper_m=P["sea"]["Ac_lateral_taper_m"])
    S.save_json(os.path.join(out, "sea_function.json"), sf)
    log["near"] = dict(pos_sha256=m1["pos_sha256"], pos_lo_sha256=m1["pos_lo_sha256"], bbox_size=m1["bbox_size"], precision=m1["pos_precision"], gpu=m1["gpu_estimate"])
    log["far"] = dict(pos_sha256=m2["pos_sha256"], pos_lo_sha256=m2["pos_lo_sha256"], bbox_size=m2["bbox_size"], precision=m2["pos_precision"], gpu=m2["gpu_estimate"])
    log["seconds"] = round(time.time() - t0, 1)
    S.save_json(os.path.join(out, "ds30_generate_log.json"), log)
    for arr, nm in ((near, "near_f64.tmp"), (far, "far_f64.tmp")):
        arr._mmap.close()
        os.remove(os.path.join(wk, nm))
    print("written", out, log["seconds"], "s")


if __name__ == "__main__":
    main()
