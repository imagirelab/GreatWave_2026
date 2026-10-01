# -*- coding: utf-8 -*-
"""仕上げ29（Q28）：主役波の視点によらない立体の材質（PL29 Ukiyoe Keypose）が読む、頂点ごとの面の座標を K*′ の格子から作る。

原画カメラは使わない（投影なし）。入力は K*′ の .gwb（頂点の t* の位置・UV2＝(K* の σ [m], 行の c [m])）と、
その meta の目印の列（profile.index：j_B 背の足・j_top 頂・j_tip 唇の先・j_corner 管の奥・j_facebot 前面の下・j_E 端）だけ。
出力は頂点ごとの float32 × 12（Unity のメッシュの UV3・UV4・UV5 の 3 つの float4 に入れる）：

［仕上げ29 修正の回（--param arc、既定）］UV2 の s・c は K*′ の t* の面の本当の弧長ではない（UV2.x は前の K* の σ、UV2.y は行ごとに一定の c）。
3 次元で測ると、c の 1 m は p50 で 1.16 m、p95 で 2.9 m に伸び、溝・点・舌の間隔が場所で 2〜3 倍に広がった（作る部の評審）。
そこで、t* の面の上の本当の弧長を作る：
  sa  行ごとに列に沿って測った 3 次元の弧長 [m]。頂の列 j_top で UV2.x と同じ値に合わせる。
  ca  列ごとに行を渡って測った 3 次元の弧長 [m]。主の行（meta の profile.index.main_row）で行の c と同じ値に合わせ、そこから両側へ積む。
どちらも K*′ の t* の位置だけから作る（生成器の中だけの変更。原画カメラは使わない）。--param uv2 で前の版（UV2 の s のまま、ca なし）を作る。

  A.x  F    流れの座標（列に沿う）。弧長（arc：sa、uv2：s）を目印の列の間で線形に分けた値：背の足 0 → 頂 1 → 唇の先 2 → 管の奥 3 → 前面の下 4 → 端 5。
            目印の外（列 < j_B、> j_E）は隣の区間の UV2.x の傾きで外へ延ばす（arc でも同じ。余白は白にならない）。
  A.y  hrel t* の高さ y* ／その行の t* の頂の高さ Hrow（列 j_B〜j_E の y の最大）。行ごとの相対の高さ。
  A.z  arc：kc 行の間隔の 3 次元の倍率（行の c の 1 m が t* の面の上で何 m か＝1/|∇c|。頂点のまわりの三角形の面積の重みの平均。0.05〜16 に切る）。
            材質は溝を行の c の上に並べ、3 次元の間隔がいつも約 λ になるよう kc で本数を 2 倍ずつ変える。
       uv2：yabs t* の高さ y* ／ H0（K*′ の meta の H0_m。前の版。材質は読まない）。
  A.w  hrow その行の Hrow ／ H0。
  B.x  s    列に沿う弧長 [m]（arc：sa、uv2：UV2.x のまま）
  B.y  c    行の c [m]（UV2.y のまま。頂に沿う向きの座標。白の範囲の折れ線 F_end(c)・b(c) はこの値で決める）
  B.z  dtip 唇の先からの弧長 [m]（s − s(j_tip)。負は頂の側、正は唇の下の側）
  B.w  dtop 頂からの弧長 [m]（s − s(j_top)）
  C.xyz n*  t* の面の法線（ワールド＝波の枠。DS27Normal と同じ格子の三角形の和。空気の側を向く）。白の中の陰（淡い水色の段）を t* の向きで決めるため
            （形成の途中の位置の量子化で、斜めから見た陰の境が 1 コマだけ揺れるのを避ける。仕上げ29 の F7-1 の数え）
  C.w  ca   行を渡る 3 次元の弧長 [m]（arc。溝・点・舌の並びはこの値で決める。uv2 では前の版と同じ 0）

どれも K*′ の格子の頂点（面の上の材料の点）に付いた値で、形成の途中は keypose の位置とともに動く（シェーダーは τ の位置・法線と T_white を別に読む）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb <K*′ .gwb> --meta <meta.json> --out <dir> [--param arc|uv2]
出力：<out>/pl29_hero_attr_f32.bin（N × 12 float32、頂点の順は .gwb と同じ＝行 × 400 ＋ 列。A・B・C）、<out>/pl29_hero_attr.json（入力と出力の SHA-256・統計）。
"""
import argparse
import hashlib
import json
import os
import struct

import numpy as np


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
    o += ntri * 12
    pos = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3)
    return nu, nv, uv, uv2, pos


def vertex_normals(P):
    """DS27KeyposeCore.cginc の DS27Normal と同じ：四角 (r, c) ごとに T1 = (r,c)(r+1,c)(r,c+1)、T2 = (r,c+1)(r+1,c)(r+1,c+1) の
    正規化しない外積を、頂点を含む面について足して正規化する。"""
    n = np.zeros_like(P)
    a, b, c_, d = P[:-1, :-1], P[1:, :-1], P[:-1, 1:], P[1:, 1:]
    t1 = np.cross(b - a, c_ - a)
    t2 = np.cross(b - c_, d - c_)
    n[:-1, :-1] += t1
    n[1:, :-1] += t1
    n[:-1, 1:] += t1
    n[:-1, 1:] += t2
    n[1:, :-1] += t2
    n[1:, 1:] += t2
    l = np.linalg.norm(n, axis=-1, keepdims=True)
    return np.where(l > 1e-30, n / np.maximum(l, 1e-30), np.array([0.0, 1.0, 0.0]))


def arc_coords(P, s_uv, c, j_top, main_row):
    """t* の面の上の本当の弧長：sa は行ごとに列に沿って、ca は列ごとに行を渡って積む。"""
    nv, nu, _ = P.shape
    ds = np.linalg.norm(np.diff(P, axis=1), axis=-1)            # nv × (nu-1)
    sa = np.concatenate([np.zeros((nv, 1)), np.cumsum(ds, axis=1)], axis=1)
    sa = sa - sa[:, j_top:j_top + 1] + s_uv[:, j_top:j_top + 1]
    dc = np.linalg.norm(np.diff(P, axis=0), axis=-1)            # (nv-1) × nu
    r0 = int(np.clip(main_row, 0, nv - 1))
    ca = np.zeros((nv, nu))
    ca[r0] = c[r0]
    for r in range(r0 + 1, nv):
        ca[r] = ca[r - 1] + dc[r - 1]
    for r in range(r0 - 1, -1, -1):
        ca[r] = ca[r + 1] - dc[r]
    return sa, ca, r0


def row_spacing_factor(P, c):
    """kc = 1/|∇c|（行の c の 1 m が t* の面の上で何 m か）。四角の 2 つの三角形（DS27Normal と同じ）の面の上の勾配から、頂点のまわりの面積の重みで平均する。"""
    nv, nu, _ = P.shape
    acc = np.zeros((nv, nu)); wsum = np.zeros((nv, nu))
    quads = [((0, 0), (1, 0), (0, 1)), ((0, 1), (1, 0), (1, 1))]
    for (a0, a1, a2) in quads:
        p0 = P[a0[0]:nv - 1 + a0[0], a0[1]:nu - 1 + a0[1]]
        p1 = P[a1[0]:nv - 1 + a1[0], a1[1]:nu - 1 + a1[1]]
        p2 = P[a2[0]:nv - 1 + a2[0], a2[1]:nu - 1 + a2[1]]
        u0 = c[a0[0]:nv - 1 + a0[0], a0[1]:nu - 1 + a0[1]]
        u1 = c[a1[0]:nv - 1 + a1[0], a1[1]:nu - 1 + a1[1]]
        u2 = c[a2[0]:nv - 1 + a2[0], a2[1]:nu - 1 + a2[1]]
        e1, e2 = p1 - p0, p2 - p0
        a11 = (e1 * e1).sum(-1); a12 = (e1 * e2).sum(-1); a22 = (e2 * e2).sum(-1)
        det = a11 * a22 - a12 * a12
        ok = det > 1e-18
        d = np.where(ok, det, 1.0)
        du1, du2 = u1 - u0, u2 - u0
        x1 = (a22 * du1 - a12 * du2) / d
        x2 = (-a12 * du1 + a11 * du2) / d
        g = np.linalg.norm(x1[..., None] * e1 + x2[..., None] * e2, axis=-1)
        k = np.where(ok & (g > 1e-9), 1.0 / np.maximum(g, 1e-9), 0.0)
        area = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=-1) * ok
        for (rr, cc) in (a0, a1, a2):
            acc[rr:nv - 1 + rr, cc:nu - 1 + cc] += k * area
            wsum[rr:nv - 1 + rr, cc:nu - 1 + cc] += area
    kc = np.where(wsum > 0, acc / np.maximum(wsum, 1e-30), 1.0)
    return np.clip(kc, 0.05, 16.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gwb", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--param", choices=["arc", "uv2"], default="arc")
    a = ap.parse_args()
    nu, nv, uv, uv2, pos = load_gwb(a.gwb)
    with open(a.meta, encoding="utf-8") as f:
        meta = json.load(f)
    idx = meta["profile"]["index"]
    J = [idx["j_B"], idx["j_top"], idx["j_tip"], idx["j_corner"], idx["j_facebot"], idx["j_E"]]
    H0 = float(meta["H0_m"])
    s_uv = uv2[:, 0].reshape(nv, nu).astype(np.float64)
    c = uv2[:, 1].reshape(nv, nu).astype(np.float64)
    P = pos.reshape(nv, nu, 3).astype(np.float64)
    y = P[..., 1]
    if a.param == "arc":
        sa, ca, r0 = arc_coords(P, s_uv, c, J[1], int(idx["main_row"]))
        s = sa
    else:
        s, ca, r0 = s_uv, np.zeros_like(c), None   # 前の版と同じファイル（C.w = 0）
    # 流れの座標 F（行ごとに弧長を目印の列の間で線形に）
    F = np.zeros((nv, nu))
    cols = np.arange(nu)
    for r in range(nv):
        sk = s[r, J]
        if np.any(np.diff(sk) <= 0):
            raise ValueError("行 %d の目印の弧長が単調でない: %s" % (r, sk))
        F[r] = np.interp(s[r], sk, np.arange(len(J), dtype=np.float64))
        # 目印の外（余白）は UV2.x の傾きで延ばす（arc では、小さな行の目印の間が数 cm しかなく、3 次元の弧長の傾きで延ばすと数千になるため。
        # 目印の列では arc と uv2 の F はどちらも 0・5 なのでつながる）
        su = s_uv[r]
        sku = su[J]
        lo = cols < J[0]
        F[r, lo] = (su[lo] - sku[0]) / (sku[1] - sku[0])
        hi = cols > J[-1]
        F[r, hi] = 5.0 + (su[hi] - sku[-1]) / (sku[-1] - sku[-2])
    hrow = y[:, J[0]:J[-1] + 1].max(axis=1)
    hrow_c = np.maximum(hrow, 1e-3)
    hrel = y / hrow_c[:, None]
    yabs = y / H0
    if a.param == "arc":
        yabs = row_spacing_factor(P, c)   # A.z は kc（前の版の yabs は材質が読まなかった）
    dtip = s - s[:, J[2]][:, None]
    dtop = s - s[:, J[1]][:, None]
    A = np.stack([F, hrel, yabs, np.repeat((hrow / H0)[:, None], nu, axis=1)], -1)
    B = np.stack([s, c, dtip, dtop], -1)
    Cn = vertex_normals(pos.reshape(nv, nu, 3).astype(np.float64))
    C = np.concatenate([Cn, ca[..., None]], -1)
    out = np.concatenate([A, B, C], -1).reshape(nv * nu, 12).astype(np.float32)
    if not np.all(np.isfinite(out)):
        raise ValueError("NaN／Inf がある")
    os.makedirs(a.out, exist_ok=True)
    bp = os.path.join(a.out, "pl29_hero_attr_f32.bin")
    out.tofile(bp)
    rec = {
        "schema": "GreatWave.Polish29.hero_attr/1",
        "noteJa": __doc__.strip().split("\n")[0],
        "layoutJa": ("頂点ごとの float32 × 12：A = (F, hrel, kc, hrow)、B = (s（t* の弧長）, c, dtip, dtop)、C = (t* の法線 xyz, ca（t* の弧長）)。" if a.param == "arc" else
                     "頂点ごとの float32 × 12：A = (F, hrel, yabs, hrow)、B = (s, c, dtip, dtop)、C = (t* の法線 xyz, 0)。") + "Unity のメッシュの UV3 = A、UV4 = B、UV5 = C（TEXCOORD3・4・5）。",
        "inputs": {"gwb": a.gwb.replace("\\", "/"), "gwb_sha256": sha256(a.gwb), "meta": a.meta.replace("\\", "/"), "meta_sha256": sha256(a.meta)},
        "projection_used": False,
        "param": a.param,
        "param_noteJa": ("s・ca は K*′ の t* の面の本当の弧長（行ごと・列ごと）。主の行 %d で ca = c、頂の列で s = UV2.x" % r0) if r0 is not None else "s は UV2.x、C.w は 0（前の版）",
        "grid": {"rows": nv, "cols": nu, "landmark_cols": J, "H0_m": H0},
        "stats": {
            "F_range": [float(F.min()), float(F.max())],
            "hrow_m_min_max": [float(hrow.min()), float(hrow.max())],
            "c_range_m": [float(c.min()), float(c.max())],
            "row_dc_m_median": float(np.median(np.diff(c[:, 0]))),
            "s_range_m": [float(s.min()), float(s.max())],
            "ca_range_m": [float(ca.min()), float(ca.max())],
            "A_z_p5_p50_p95": [float(v) for v in np.percentile(yabs, [5, 50, 95])],
        },
        "output": {"path": bp.replace("\\", "/"), "sha256": sha256(bp), "bytes": os.path.getsize(bp), "vertices": nv * nu, "floats_per_vertex": 12},
    }
    with open(os.path.join(a.out, "pl29_hero_attr.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps(rec["stats"], ensure_ascii=False), rec["output"]["sha256"])


if __name__ == "__main__":
    main()
