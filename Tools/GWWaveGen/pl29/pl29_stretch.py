# -*- coding: utf-8 -*-
"""仕上げ29 修正の回：主役波の材質の面の座標（s・c）が、K*′ の t* の面の上でどれだけ伸び縮みするかを測る（記録用。描画はしない）。

入力：K*′ の .gwb（t* の位置・UV2）と、pl29_hero_attr.py の出力（前の版 --param uv2、修正の版 --param arc）。
三角形（DS27Normal と同じ四角の 2 つの三角形）ごとに、面の上の座標 u の 3 次元の勾配 ∇u を求め、面積で重みを付けて数える：
  ・溝の間隔の倍率 g = 1/|∇c|（溝は c（arc では ca）の周期 λ で並ぶので、3 次元の溝の間隔は λ・g）
  ・流れの向きの倍率 1/|∇s|（溝の切れ・点の格子・うねりの長さの倍率）
  ・異方性：(s, c) → 3 次元の写像のヤコビアンの特異値の比 σ1/σ2
  ・溝の向きのずれ（arc だけ）：溝の向き（面の上で ∇ca に直交）と列の向き（流れ）の角度
  ［修正の回の材質の溝］溝は ca ではなく行の c の上に並べ、kc（= 1/|∇c|）で本数を 2 倍ずつ変える（PL29_Ukiyoe_Hero.shader の FlowLines）。
  三角形ごとに L = log2(1/|∇c|)、f = L − floor(L) とし、基の溝の 3 次元の間隔の倍率 2^f（1〜2）と、間の溝が太さ f で加わった実効の倍率 2^f/(1+f)
  （溝の本数が 1 + f 本に増えたとみた平均の間隔）を数える。点・房・泡の粒は (s, ca) の上に置くので、(s, ca) の異方性と面積の倍率も数える。
数える範囲：列 j_B〜j_E（背の足〜端）で、三角形の面積が 1e-6 m² より大きいもの。c の 5〜15 m（右の管）も別に数える。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl29/pl29_stretch.py --gwb <K*′ .gwb> --meta <meta.json>
    --before <前の版の pl29_hero_attr_f32.bin> --after <修正の版の pl29_hero_attr_f32.bin> --lambda 0.95 --out <json>
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pl29_hero_attr import load_gwb  # noqa: E402


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tris(nv, nu, j0, j1):
    r, c = np.meshgrid(np.arange(nv - 1), np.arange(j0, j1), indexing="ij")
    r = r.ravel(); c = c.ravel()
    i00 = r * nu + c; i10 = (r + 1) * nu + c; i01 = r * nu + c + 1; i11 = (r + 1) * nu + c + 1
    t1 = np.stack([i00, i10, i01], 1)
    t2 = np.stack([i01, i10, i11], 1)
    return np.concatenate([t1, t2], 0)


def grad3(P, u, T):
    """三角形の面の上の u の 3 次元の勾配（三角形 × 3）と面積。"""
    p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    a11 = (e1 * e1).sum(1); a12 = (e1 * e2).sum(1); a22 = (e2 * e2).sum(1)
    det = a11 * a22 - a12 * a12
    du1 = u[T[:, 1]] - u[T[:, 0]]; du2 = u[T[:, 2]] - u[T[:, 0]]
    ok = det > 1e-18
    detc = np.where(ok, det, 1.0)
    x1 = (a22 * du1 - a12 * du2) / detc
    x2 = (-a12 * du1 + a11 * du2) / detc
    g = x1[:, None] * e1 + x2[:, None] * e2
    area = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    return g, area, ok


def jac_ratio(P, s, c, T):
    """(s, c) → 3 次元のヤコビアン J（3×2）の特異値の比。"""
    p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    E = np.stack([p1 - p0, p2 - p0], 2)                                  # n × 3 × 2
    M = np.stack([np.stack([s[T[:, 1]] - s[T[:, 0]], s[T[:, 2]] - s[T[:, 0]]], 1),
                  np.stack([c[T[:, 1]] - c[T[:, 0]], c[T[:, 2]] - c[T[:, 0]]], 1)], 1)   # n × 2 × 2
    det = M[:, 0, 0] * M[:, 1, 1] - M[:, 0, 1] * M[:, 1, 0]
    ok = np.abs(det) > 1e-12
    Mi = np.zeros_like(M)
    d = np.where(ok, det, 1.0)
    Mi[:, 0, 0] = M[:, 1, 1] / d; Mi[:, 1, 1] = M[:, 0, 0] / d; Mi[:, 0, 1] = -M[:, 0, 1] / d; Mi[:, 1, 0] = -M[:, 1, 0] / d
    J = np.einsum("nij,njk->nik", E, Mi)
    sv = np.linalg.svd(J, compute_uv=False)
    r = sv[:, 0] / np.maximum(sv[:, 1], 1e-12)
    return r, ok


def wpct(x, w, q):
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw = np.cumsum(w) / w.sum()
    return [float(np.interp(qq / 100.0, cw, x)) for qq in q]


def stats(name, s, c, P, T, area_ok, cmask, lam, colvec=None):
    gc, area, ok1 = grad3(P, c, T)
    gs, _, ok2 = grad3(P, s, T)
    jr, ok3 = jac_ratio(P, s, c, T)
    m = area_ok & ok1 & ok2 & ok3
    gcn = np.linalg.norm(gc, axis=1); gsn = np.linalg.norm(gs, axis=1)
    m &= (gcn > 1e-9) & (gsn > 1e-9)
    fc = 1.0 / np.where(m, gcn, 1.0); fs = 1.0 / np.where(m, gsn, 1.0)
    w = area
    out = {"name": name, "triangles": int(m.sum()), "area_m2": float(w[m].sum())}
    p = wpct(fc[m], w[m], [5, 50, 95])
    out["groove_spacing_factor_p5_p50_p95"] = [round(v, 3) for v in p]
    out["groove_spacing_m_p50_p95"] = [round(lam * p[1], 3), round(lam * p[2], 3)]
    out["groove_spacing_area_frac_gt2"] = round(float(w[m & (fc > 2)].sum() / w[m].sum()), 3)
    out["groove_spacing_area_frac_lt0p5"] = round(float(w[m & (fc < 0.5)].sum() / w[m].sum()), 3)
    mm = m & cmask
    out["c5_15_groove_spacing_factor_p50"] = round(wpct(fc[mm], w[mm], [50])[0], 3)
    out["c5_15_area_frac_gt2"] = round(float(w[mm & (fc > 2)].sum() / w[mm].sum()), 3)
    out["flow_length_factor_p5_p50_p95"] = [round(v, 3) for v in wpct(fs[m], w[m], [5, 50, 95])]
    out["anisotropy_p50_p95"] = [round(v, 3) for v in wpct(jr[m], w[m], [50, 95])]
    if colvec is not None:
        # 溝の向き：面の法線 n と ∇c の外積（面の上で ∇c に直交）。列の向き（流れ）との角度
        p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
        n = np.cross(p1 - p0, p2 - p0)
        gdir = np.cross(n, gc)
        cos = np.abs((gdir * colvec).sum(1)) / np.maximum(np.linalg.norm(gdir, axis=1) * np.linalg.norm(colvec, axis=1), 1e-12)
        ang = np.degrees(np.arccos(np.clip(cos, 0, 1)))
        out["groove_vs_flow_angle_deg_p50_p95"] = [round(v, 2) for v in wpct(ang[m], w[m], [50, 95])]
    return out


def octave(P, c, T, area_ok):
    gc, area, ok = grad3(P, c, T)
    g = np.linalg.norm(gc, axis=1)
    m = area_ok & ok & (g > 1e-9)
    fc = 1.0 / np.where(m, g, 1.0)
    L = np.log2(np.maximum(fc, 1e-6))
    f = L - np.floor(L)
    base = 2.0 ** f
    eff = base / (1.0 + f)
    w = area
    return {"groove_base_spacing_factor_p5_p50_p95": [round(v, 3) for v in wpct(base[m], w[m], [5, 50, 95])],
            "groove_effective_spacing_factor_p5_p50_p95": [round(v, 3) for v in wpct(eff[m], w[m], [5, 50, 95])],
            "groove_effective_area_frac_gt1p2": round(float(w[m & (eff > 1.2)].sum() / w[m].sum()), 3),
            "groove_effective_area_frac_lt0p8": round(float(w[m & (eff < 0.8)].sum() / w[m].sum()), 3),
            "noteJa": "溝は行の c の上、kc で本数を 2 倍ずつ（FlowLines）。基の間隔は λ·2^f、間の溝が太さ f で加わる。実効の間隔は λ·2^f/(1+f)（0.94〜1.0 λ）"}


def area_factor(P, s, c, T, area_ok):
    p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    a3 = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    a2 = 0.5 * np.abs((s[T[:, 1]] - s[T[:, 0]]) * (c[T[:, 2]] - c[T[:, 0]]) - (s[T[:, 2]] - s[T[:, 0]]) * (c[T[:, 1]] - c[T[:, 0]]))
    m = area_ok & (a2 > 1e-12)
    r = a3 / np.where(m, a2, 1.0)
    return [round(v, 3) for v in wpct(r[m], a3[m], [5, 50, 95])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gwb", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--lambda", dest="lam", type=float, default=0.95)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    nu, nv, uv, uv2, pos = load_gwb(a.gwb)
    meta = json.load(open(a.meta, encoding="utf-8"))
    idx = meta["profile"]["index"]
    j0, j1 = idx["j_B"], idx["j_E"]
    P = pos.astype(np.float64)
    T = tris(nv, nu, j0, j1)
    B = np.fromfile(a.before, np.float32).reshape(-1, 12).astype(np.float64)
    A = np.fromfile(a.after, np.float32).reshape(-1, 12).astype(np.float64)
    c_row = B[:, 5]
    cmask = (c_row[T].mean(1) >= 5.0) & (c_row[T].mean(1) <= 15.0)
    _, area, _ = grad3(P, B[:, 5], T)
    area_ok = area > 1e-6
    # 列の向き（流れ）：三角形の中の列の向きの辺
    colvec = P[T[:, 2]] - P[T[:, 0]]
    colvec[len(T) // 2:] = P[T[len(T) // 2:, 2]] - P[T[len(T) // 2:, 1]]
    res = {
        "schema": "GreatWave.Polish29.stretch/1",
        "noteJa": __doc__.strip().split("\n")[0],
        "inputs": {"gwb": a.gwb, "gwb_sha256": sha256(a.gwb), "before": a.before, "before_sha256": sha256(a.before), "after": a.after, "after_sha256": sha256(a.after)},
        "lambda_m": a.lam, "cols": [j0, j1],
        "before_uv2": stats("前の版（UV2 の s・行の c）", B[:, 4], B[:, 5], P, T, area_ok, cmask, a.lam),
        "after_arc": stats("修正の版（t* の面の弧長 sa・ca）", A[:, 4], A[:, 11], P, T, area_ok, cmask, a.lam, colvec),
        "after_grooves_octave": octave(P, B[:, 5], T, area_ok),
        "after_grooves_octave_c5_15": octave(P, B[:, 5], T, area_ok & cmask),
        "area_factor_p5_p50_p95": {"before_uv2_s_c": area_factor(P, B[:, 4], B[:, 5], T, area_ok), "after_sa_ca": area_factor(P, A[:, 4], A[:, 11], T, area_ok)},
        "readingJa": ("before_uv2 は作る部の材質（溝・点・舌を UV2 の s と行の c の上に置いた）。after_arc の groove_* は ca の上に溝を置いた場合の値（ずれが大きいので溝には使わない）。"
                      "修正の回の溝は after_grooves_octave（行の c の上、kc で本数を 2 倍ずつ）。点・房・泡の粒は after_arc の (sa, ca)。"),
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res["before_uv2"], ensure_ascii=False))
    print(json.dumps(res["after_arc"], ensure_ascii=False))
    print(json.dumps(res["after_grooves_octave"], ensure_ascii=False))
    print(json.dumps(res["after_grooves_octave_c5_15"], ensure_ascii=False))
    print(json.dumps(res["area_factor_p5_p50_p95"], ensure_ascii=False))


if __name__ == "__main__":
    main()
