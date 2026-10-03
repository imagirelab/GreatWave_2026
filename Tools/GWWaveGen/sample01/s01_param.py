# -*- coding: utf-8 -*-
"""美術の見本01（Q29）：t* の主役波の面に、巻きの向きにそろえた、世界の寸法で一様な面の座標 (u, w) を作る（見本 A・B で共用）。

なぜ：仕上げ29 の溝・点・舌は、シートの生の座標（流れの座標 F と行の c、行ごとの弧長 sa、列ごとの弧長 ca）の上に置いていた。
シートの格子は行（原画の進む向き Tdir の鉛直の断面）と列（目印の列の間を線形に分けた列）でできていて、
列の間隔は 0.009〜2 m、行の間隔の 3 次元の倍率 kc は 1〜2.4、格子の角は p5 で 34° まで傾く。そのため、溝は場所で
2 倍以上に開き、頂の線に対して斜めに走り、Q29 の「原画的贴图效果更是歪的很」になった。

作り方（原画カメラは使わない。参照モデルの OBJ も読まない。入力は K*′ P28R2rec の .gwb と、仕上げ29 の面の座標の F だけ）：
 1. 頂に並ぶ向き X（頂の線・唇の先の線に平行な向き）を、F の等値線の接線として格子の差分から頂点ごとに作る：
    X0 = ∂P/∂r − ∂P/∂j ·(∂F/∂r)/(∂F/∂j)。面へ射影して正規化し、+c の向きにそろえる。
 2. X0 を、面の上で半径およそ R の重みで平らにする（有限要素の剛性 K と質量 M による (M + R² K) X = M X0。
    成分ごとに解いてから面へ射影し正規化。X は唇の折り返しの両側で同じ向きなので、成分ごとに平らにしてよい）。
 3. 巻きの向き Y = n × X（背の足 → 頂 → 唇の先 → 管 → 前面の向きにそろえる）。
 4. w：Σ_t A_t |∇w − X_t|² を最小にする（ポアソン方程式 K w = Gᵀ M X）。溝は w の等値線で、巻きの向きに走り、
    世界の寸法で |∇w| ≈ 1（1 m ごとに w が 1 m 進む）。X が積分できない所（巻きの線が扇に開く所）は、L2 の意味で最も近い勾配になり、
    |∇w| が 1 からずれる（その倍率 gw を頂点ごとに残す。材質は gw で溝の本数を 2 倍ずつ変えてよい）。
 5. u：巻きの向きの弧長 [m]。巻きの線の長さは行ごとに違う（70〜170 m）ので、等方のポアソンでは |∇u| が縮む。
    そこで Σ_t A_t [(∇u·Y_t − 1)² + β (∇u·X_t)²] ＋ 頂の列（j_top）の頂点を u = 0 に強く留める項、を最小にする
    （巻きの線に沿って頂から測った弧長に近い。背の側が負、唇の側が正）。
 6. w の定数：主の行・頂の列の頂点で w = c（行の座標）に合わせる。

出力（<out>）：
  s01_param_f32.bin  頂点ごとの float32 × 8（頂点の順は .gwb と同じ＝行 × 400 ＋ 列）：
      0 u   巻きの向きの弧長 [m]（頂の列で 0）
      1 w   頂に並ぶ向きの座標 [m]（溝・舌はこの等値線に置く）
      2 gu  |∇u|（隣の三角形の面積の重みの平均）
      3 gw  |∇w|（同じ。世界の 1 m で w が何 m 進むか。溝の 3 次元の間隔は λ / gw）
      4-6 X t* の頂に並ぶ向き（波の枠の xyz、単位、面の接線）
      7 q   使ってよさ（0〜1。行の頂の高さ hrow が低い行（< 0.08 H0）と余白の列で 0 へ下がる。統計の重み）
  s01_param.json     入力と出力の SHA-256、統計（|∇w|・|∇u| の分布、∇w と X の角、∇u と ∇w の直交、行の格子との比較）
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/sample01/s01_param.py --gwb <.gwb> --meta <meta.json> --attr <pl29_hero_attr_f32.bin> --out <dir>
"""
import argparse
import hashlib
import json
import os
import struct
import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_gwb(p):
    b = open(p, "rb").read()
    if b[:4] != b"GWW0":
        raise ValueError("GWW0 ではない: " + p)
    ver, nu, nv, nf = struct.unpack("<4i", b[4:20])
    tsf, ntri = struct.unpack("<2i", b[24:32])
    n = nu * nv
    o = 32
    uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2); o += n * 8
    uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2); o += n * 8
    tri = np.frombuffer(b, np.int32, ntri * 3, o).reshape(ntri, 3).astype(np.int64); o += ntri * 12
    pos = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3)
    return nu, nv, uv, uv2, tri, pos.astype(np.float64)


def unit(v, eps=1e-12):
    l = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(l, eps)


def vertex_normals(P):
    """pl29_hero_attr.vertex_normals と同じ（DS27Normal の格子の三角形の和）。"""
    n = np.zeros_like(P)
    a, b, c_, d = P[:-1, :-1], P[1:, :-1], P[:-1, 1:], P[1:, 1:]
    t1 = np.cross(b - a, c_ - a)
    t2 = np.cross(b - c_, d - c_)
    n[:-1, :-1] += t1; n[1:, :-1] += t1; n[:-1, 1:] += t1
    n[:-1, 1:] += t2; n[1:, :-1] += t2; n[1:, 1:] += t2
    return unit(n)


def grad_operator(pos, tri):
    """三角形ごとの勾配の作用素 G（3T × N）と面積 A、単位法線 nt。"""
    p0, p1, p2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    N = np.cross(p1 - p0, p2 - p0)
    dbl = np.linalg.norm(N, axis=1)
    A = 0.5 * dbl
    nt = N / np.maximum(dbl, 1e-30)[:, None]
    # ∇f = Σ_k f_k (nt × e_k) / (2A)、e_k は頂点 k の向かいの辺（反時計回り）
    e0 = p2 - p1; e1 = p0 - p2; e2 = p1 - p0
    inv = 1.0 / np.maximum(dbl, 1e-30)
    g0 = np.cross(nt, e0) * inv[:, None]
    g1 = np.cross(nt, e1) * inv[:, None]
    g2 = np.cross(nt, e2) * inv[:, None]
    T = tri.shape[0]
    # 並び：k（三角形の頂点）ごとに d（成分）ごと。行 = 3t + d、列 = tri[t, k]
    vals = np.concatenate([g[:, d] for g in (g0, g1, g2) for d in range(3)])
    rows = np.concatenate([np.arange(T) * 3 + d for k in range(3) for d in range(3)])
    cols = np.concatenate([tri[:, k] for k in range(3) for d in range(3)])
    G = sp.csr_matrix((vals, (rows, cols)), shape=(3 * T, pos.shape[0]))
    return G, A, nt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gwb", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--attr", required=True, help="仕上げ29 の面の座標（pl29_hero_attr.py --param arc の出力。F と c を読む）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--smooth_m", type=float, default=3.0, help="X を平らにする半径 R [m]")
    ap.add_argument("--minrowh", type=float, default=0.08, help="使ってよさ q を下げる行の頂の高さ（H0 の倍）")
    ap.add_argument("--beta", type=float, default=0.05, help="（--dir isoF）u の頂に並ぶ向きの成分を 0 へ寄せる重み")
    ap.add_argument("--dir", choices=["heat", "isoF"], default="heat", help="巻きの向きの作り方：heat＝頂の線からの面の上の距離（熱の方法）の勾配、isoF＝F の等値線に直交")
    ap.add_argument("--heat_m", type=float, default=3.0, help="（--dir heat）熱の時間の長さ √t [m]")
    a = ap.parse_args()
    t0 = time.time()
    nu, nv, uv, uv2, tri, pos = load_gwb(a.gwb)
    with open(a.meta, encoding="utf-8") as f:
        meta = json.load(f)
    idx = meta["profile"]["index"]
    J = [idx["j_B"], idx["j_top"], idx["j_tip"], idx["j_corner"], idx["j_facebot"], idx["j_E"]]
    H0 = float(meta["H0_m"])
    main_row = int(idx["main_row"])
    attr_json = os.path.join(os.path.dirname(a.attr), "pl29_hero_attr.json")
    if os.path.exists(attr_json):
        aj = json.load(open(attr_json, encoding="utf-8"))
        if aj["inputs"]["gwb_sha256"] != sha256(a.gwb):
            raise ValueError("面の座標の入力の .gwb が違う")
    at = np.fromfile(a.attr, np.float32).reshape(nv * nu, 12).astype(np.float64)
    F = at[:, 0].reshape(nv, nu)
    c = uv2[:, 1].reshape(nv, nu).astype(np.float64)
    P = pos.reshape(nv, nu, 3)
    n_v = vertex_normals(P)

    # ---- 1. 頂に並ぶ向き X0（F の等値線の接線）
    def d_axis(Q, ax):
        D = np.zeros_like(Q)
        if ax == 1:
            D[:, 1:-1] = 0.5 * (Q[:, 2:] - Q[:, :-2]); D[:, 0] = Q[:, 1] - Q[:, 0]; D[:, -1] = Q[:, -1] - Q[:, -2]
        else:
            D[1:-1] = 0.5 * (Q[2:] - Q[:-2]); D[0] = Q[1] - Q[0]; D[-1] = Q[-1] - Q[-2]
        return D
    tj = d_axis(P, 1); tr = d_axis(P, 0)
    Fj = d_axis(F, 1); Fr = d_axis(F, 0)
    ratio = np.where(np.abs(Fj) > 1e-9, Fr / np.where(np.abs(Fj) > 1e-9, Fj, 1.0), 0.0)
    X0 = tr - tj * ratio[..., None]
    X0 = X0 - (X0 * n_v).sum(-1, keepdims=True) * n_v
    bad0 = np.linalg.norm(X0, axis=-1) < 1e-9
    X0 = np.where(bad0[..., None], unit(tr - (tr * n_v).sum(-1, keepdims=True) * n_v), unit(X0))
    sgn = np.sign((X0 * tr).sum(-1)); sgn[sgn == 0] = 1
    X0 = X0 * sgn[..., None]
    # 行の格子の向き（比較用）：行の接線 tj に直交する面の向き
    Xrow = unit(np.cross(unit(tj), n_v)); Xrow = Xrow * np.sign((Xrow * tr).sum(-1, keepdims=True) + 1e-30)

    # ---- 有限要素の作用素
    N = nv * nu
    G, A, nt = grad_operator(pos, tri)
    Mt = sp.diags(np.repeat(A, 3))
    K = (G.T @ Mt @ G).tocsc()
    mv = np.zeros(N); np.add.at(mv, tri.reshape(-1), np.repeat(A / 3.0, 3))
    mv = np.maximum(mv, 1e-12)
    Mv = sp.diags(mv)
    t_ops = time.time() - t0

    # ---- 2. X0 を面の上で平らにする
    R = a.smooth_m
    lu_s = spla.splu((Mv + (R * R) * K).tocsc())
    X0f = X0.reshape(N, 3)
    Xs = np.stack([lu_s.solve(mv * X0f[:, k]) for k in range(3)], -1)
    nvf = n_v.reshape(N, 3)
    Xs = Xs - (Xs * nvf).sum(-1, keepdims=True) * nvf
    Xs = unit(Xs)
    Ys = unit(np.cross(nvf, Xs))
    # Y を巻きの向き（列が増える向き tj）へそろえる
    tjf = tj.reshape(N, 3)
    sy = np.sign((Ys * tjf).sum(-1)); sy[sy == 0] = 1
    flip_frac = float((sy < 0).mean())
    Ys = Ys * sy[:, None]

    # ---- 4・5. ポアソン（三角形ごとの目標は頂点の向きの平均を三角形の面へ射影して単位にしたもの）
    def tri_target(V):
        Vt = V[tri].mean(1)
        Vt = Vt - (Vt * nt).sum(-1, keepdims=True) * nt
        return unit(Vt)
    Xt = tri_target(Xs)
    Yt = tri_target(Ys)
    eps = 1e-8 * float(K.diagonal().mean())
    lu_p = spla.splu((K + eps * Mv).tocsc())
    T = tri.shape[0]
    crest = np.zeros(N); crest[np.arange(nv) * nu + J[1]] = 1.0
    u_heat = None
    if a.dir == "heat":
        # 熱の方法（Crane ほか 2013）：頂の線から熱を流し、その勾配の向き（頂から離れる向き）を、背の側（F < 1）で裏返して
        # 「背の足 → 頂 → 唇の先 → 管 → 前面」の向きにそろえ、ポアソンで積分すると、頂の線からの面の上の符号付きの距離 u になる。
        # 巻きの向き Y はこの勾配、頂に並ぶ向き X = n × Y。等値線（頂の線に平行な線）は等距離、Y の流線は頂の線に直交する面の上の最短の線。
        ht = a.heat_m ** 2
        h = spla.splu((Mv + ht * K).tocsc()).solve(mv * crest)
        gh = (G @ h).reshape(-1, 3)
        Ft = F.reshape(-1)[tri].mean(1)
        st = np.where(Ft < 1.0, 1.0, -1.0)            # 熱は頂で高い：−∇h が頂から離れる向き。背の側は頂へ向けるため裏返す
        Yt = unit(-gh * st[:, None])
        Yt = unit(Yt - (Yt * nt).sum(-1, keepdims=True) * nt)
        Xt = unit(np.cross(nt, Yt))
        # X を +c の向きへ（三角形の行の向きと比べる）
        trt = tr.reshape(N, 3)[tri].mean(1)
        sx = np.sign((Xt * trt).sum(-1)); sx[sx == 0] = 1
        Xt = Xt * sx[:, None]
        u_heat = lu_p.solve(G.T @ (Mt @ Yt.reshape(-1)))
        u_heat = u_heat - np.median(u_heat[crest > 0])
        # 頂点の X（出力用）：隣の三角形の X の面積の重みの平均
        Xs = np.zeros((N, 3))
        for k in range(3):
            np.add.at(Xs, tri[:, k], Xt * A[:, None])
        Xs = Xs - (Xs * nvf).sum(-1, keepdims=True) * nvf
        Xs = unit(Xs)
        # 比べるための isoF の向き
        Yt_iso = tri_target(Ys)
    bw = G.T @ (Mt @ Xt.reshape(-1))
    bu = G.T @ (Mt @ Yt.reshape(-1))
    w = lu_p.solve(bw)
    i0 = main_row * nu + J[1]
    w = w - w[i0] + c.reshape(-1)[i0]
    # u：巻きの線は行ごとに長さが違う（70〜170 m）ので、等方のポアソンでは |∇u| が 0.64 倍に縮む（try1）。
    # そこで、巻きの向き Y の成分だけを 1 に合わせ（∇u·Y = 1）、頂に並ぶ向きの成分は弱く 0 へ（β (∇u·X)²）、
    # 頂の列（j_top）の頂点を u = 0 に強く留める：Σ A_t[(∇u·Y_t − 1)² + β (∇u·X_t)²] + μ Σ_crest m_i u_i²。
    if u_heat is not None:
        u = u_heat
    else:
        ridx = np.repeat(np.arange(T), 3); cidx = np.arange(3 * T)
        Dy = sp.csr_matrix((Yt.reshape(-1), (ridx, cidx)), shape=(T, 3 * T))
        Dx = sp.csr_matrix((Xt.reshape(-1), (ridx, cidx)), shape=(T, 3 * T))
        Gy = (Dy @ G).tocsr(); Gx = (Dx @ G).tocsr()
        At = sp.diags(A)
        mu = 1e3 * float((Gy.T @ At @ Gy).diagonal().mean())
        Ku = (Gy.T @ At @ Gy + a.beta * (Gx.T @ At @ Gx) + sp.diags(mu * crest) + eps * Mv).tocsc()
        u = spla.splu(Ku).solve(Gy.T @ (A * 1.0))

    # ---- 統計
    gwt = (G @ w).reshape(-1, 3); gut = (G @ u).reshape(-1, 3)
    gw_t = np.linalg.norm(gwt, axis=1); gu_t = np.linalg.norm(gut, axis=1)
    acc_w = np.zeros(N); acc_u = np.zeros(N); acc_a = np.zeros(N)
    for k in range(3):
        np.add.at(acc_w, tri[:, k], gw_t * A); np.add.at(acc_u, tri[:, k], gu_t * A); np.add.at(acc_a, tri[:, k], A)
    gw = acc_w / np.maximum(acc_a, 1e-30); gu = acc_u / np.maximum(acc_a, 1e-30)
    # 使ってよさ q
    hrow = P[:, J[0]:J[-1] + 1, 1].max(axis=1)
    qrow = np.clip((hrow / H0 - 0.5 * a.minrowh) / (0.5 * a.minrowh), 0, 1)
    qcol = np.zeros(nu); qcol[J[0]:J[-1] + 1] = 1.0
    q = (qrow[:, None] * qcol[None, :]).reshape(-1)
    qt = q[tri].min(1)
    wts = A * (qt > 0.99)
    def wpct(x, ws, ps):
        o = np.argsort(x); cw = np.cumsum(ws[o]); cw /= cw[-1]
        return [float(np.interp(p / 100.0, cw, x[o])) for p in ps]
    ang_w_X = np.degrees(np.arccos(np.clip((unit(gwt) * Xt).sum(-1), -1, 1)))
    ang_u_Y = np.degrees(np.arccos(np.clip((unit(gut) * Yt).sum(-1), -1, 1)))
    orth = np.degrees(np.arcsin(np.clip(np.abs((unit(gwt) * unit(gut)).sum(-1)), 0, 1)))
    # 行の格子（仕上げ29 の溝の並べ方：行の c の上）との比較：溝の向きが巻きの向き Y からどれだけ傾くか
    Xrow_t = tri_target(Xrow.reshape(N, 3))
    ang_row = np.degrees(np.arccos(np.clip(np.abs((Xrow_t * Xt).sum(-1)), 0, 1)))
    kc = at[:, 2]
    kc_t = kc[tri].mean(1)
    # 頂点ごとの角の外れ（図のため）
    # 波の本体（目に入る所）：行の頂の高さ ≥ 0.3 H0、F が 0.3〜4.2（背の上半から頂・唇・管・前面）
    Ftri = F.reshape(-1)[tri].mean(1)
    hrow_t = np.repeat(hrow, nu)[tri].min(1)
    wc = A * (qt > 0.99) * (hrow_t >= 0.3 * H0) * (Ftri >= 0.3) * (Ftri <= 4.2)
    # 平らにする前の向き X0（F の等値線の接線そのもの）に対する ∇w のずれ（平らにする半径を比べるための、共通の物差し）
    X0t = tri_target(X0.reshape(N, 3))
    ang_w_X0 = np.degrees(np.arccos(np.clip(np.abs((unit(gwt) * X0t).sum(-1)), 0, 1)))
    ang_row_X0 = np.degrees(np.arccos(np.clip(np.abs((Xrow_t * X0t).sum(-1)), 0, 1)))
    core_stats = {
        "noteJa": "波の本体（行の頂の高さ ≥ 0.3 H0、F 0.3〜4.2）の三角形の面積の重み。面積 %.0f m²" % wc.sum(),
        "gw_p5_p50_p95": wpct(gw_t, wc, [5, 50, 95]),
        "gw_area_frac_outside_0.8_1.25": float(wc[(gw_t < 0.8) | (gw_t > 1.25)].sum() / wc.sum()),
        "gu_p5_p50_p95": wpct(gu_t, wc, [5, 50, 95]),
        "angle_gradw_vs_X_deg_p50_p95": wpct(ang_w_X, wc, [50, 95]),
        "nonorthogonality_u_w_deg_p50_p95": wpct(orth, wc, [50, 95]),
        "angle_gradw_vs_rawX0_deg_p50_p95": wpct(ang_w_X0, wc, [50, 95]),
        "before_angle_rowgroove_vs_rawX0_deg_p50_p95": wpct(ang_row_X0, wc, [50, 95]),
        "before_kc_p5_p50_p95": wpct(kc_t, wc, [5, 50, 95]),
        "before_angle_rowgroove_vs_curl_deg_p50_p95": wpct(ang_row, wc, [50, 95]),
    }
    ang_heat_iso = None
    if a.dir == "heat":
        ang_heat_iso = np.degrees(np.arccos(np.clip(np.abs((Yt * Yt_iso).sum(-1)), 0, 1)))
    stats = {
        "body_weight_noteJa": "統計は、行の頂の高さ ≥ %.2f H0 の行・列 j_B〜j_E の三角形の面積の重み" % a.minrowh,
        "gw_p5_p50_p95": wpct(gw_t, wts, [5, 50, 95]),
        "gw_p1_p99": wpct(gw_t, wts, [1, 99]),
        "gw_area_frac_outside_0.8_1.25": float(wts[(gw_t < 0.8) | (gw_t > 1.25)].sum() / wts.sum()),
        "gw_area_frac_outside_0.67_1.5": float(wts[(gw_t < 0.67) | (gw_t > 1.5)].sum() / wts.sum()),
        "gu_p5_p50_p95": wpct(gu_t, wts, [5, 50, 95]),
        "angle_gradw_vs_X_deg_p50_p95": wpct(ang_w_X, wts, [50, 95]),
        "angle_gradu_vs_Y_deg_p50_p95": wpct(ang_u_Y, wts, [50, 95]),
        "nonorthogonality_u_w_deg_p50_p95": wpct(orth, wts, [50, 95]),
        "before_row_grid": {
            "noteJa": "仕上げ29 の溝は行の c の上（溝の向き＝行の接線、間隔＝kc）。同じ重みで",
            "kc_p5_p50_p95": wpct(kc_t, wts, [5, 50, 95]),
            "kc_area_frac_outside_0.8_1.25": float(wts[(kc_t < 0.8) | (kc_t > 1.25)].sum() / wts.sum()),
            "angle_rowgroove_vs_curl_deg_p50_p95": wpct(ang_row, wts, [50, 95]),
        },
        "core": core_stats,
        "Y_flipped_to_column_order_frac": flip_frac,
        "angle_heatY_vs_isoF_Y_deg_p50_p95": wpct(ang_heat_iso, wts, [50, 95]) if ang_heat_iso is not None else None,
        "u_range_m": [float(u.min()), float(u.max())],
        "w_range_m": [float(w.min()), float(w.max())],
    }
    os.makedirs(a.out, exist_ok=True)
    out = np.stack([u, w, gu, gw, Xs[:, 0], Xs[:, 1], Xs[:, 2], q], -1).astype(np.float32)
    if not np.all(np.isfinite(out)):
        raise ValueError("NaN／Inf がある")
    bp = os.path.join(a.out, "s01_param_f32.bin")
    out.tofile(bp)
    rec = {
        "schema": "GreatWave.Sample01.param/1",
        "noteJa": __doc__.strip().split("\n")[0],
        "layoutJa": "頂点ごとの float32 × 8：u [m], w [m], gu, gw, X.xyz（t* の頂に並ぶ向き、波の枠）, q（使ってよさ）。頂点の順は .gwb と同じ（行 × 400 ＋ 列）",
        "inputs": {"gwb": a.gwb.replace("\\", "/"), "gwb_sha256": sha256(a.gwb), "meta": a.meta.replace("\\", "/"), "meta_sha256": sha256(a.meta),
                   "attr": a.attr.replace("\\", "/"), "attr_sha256": sha256(a.attr)},
        "projection_used": False, "reference_obj_read": False,
        "params": {"dir": a.dir, "heat_m": a.heat_m, "smooth_m": R, "minrowh": a.minrowh, "eps": eps, "beta": a.beta, "gauge": {"w": "主の行 %d・頂の列 %d で w = c" % (main_row, J[1]), "u": ("頂の列 %d の頂点の中央値で u = 0" if a.dir == "heat" else "頂の列 %d の頂点を u = 0 に留める（重み μ）") % J[1]}},
        "grid": {"rows": nv, "cols": nu, "landmark_cols": J, "H0_m": H0, "triangles": int(tri.shape[0])},
        "stats": stats,
        "seconds": {"operators": round(t_ops, 2), "total": round(time.time() - t0, 2)},
        "output": {"path": bp.replace("\\", "/"), "sha256": sha256(bp), "bytes": os.path.getsize(bp), "vertices": N, "floats_per_vertex": 8},
    }
    with open(os.path.join(a.out, "s01_param.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print(rec["output"]["sha256"], rec["seconds"])


if __name__ == "__main__":
    main()
