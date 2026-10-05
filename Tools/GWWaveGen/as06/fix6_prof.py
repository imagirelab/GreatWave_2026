# -*- coding: utf-8 -*-
"""美術の見本06 の直しの回（段の行 R8 → R9）：行の断面から、批評の直しの目標を数で出す（形だけ。Unity の描画ではない）。
py -3.10 -B Tools/GWWaveGen/as06/fix6_prof.py <rows.npz> [<out.json>] [--base=<rows.npz>]

出す数：
  head：唇の頭の厚さ。断面ごとに縁の頂 E（列 130〜200 の最も高い点）と唇の先 T（列 200）。T の 0.5 m 後ろの縦の線で、外の面と唇の下の面の高さの差。
        さらに唇の出（T の a − 唇の下の引っ込みの最も奥の a）と、出の中ほどの縦の厚さ / 出（≥ 1/3 が目標）。
  lower：段の体の下の半分の傾き。内の面（列 200 以後）で、高さ T.y/2 と 0.3 m を通る点の弦の角（水平から、≤ 65° が目標）。
  left：③ の左の端（c ≤ −21）で、背の頂（列 < 106）の高さ − 縁の頂 E の高さ（H0 の割合、≥ 0.04 が目標）と、左の端の外の面の傾き。
  dihedral：行の格子の世界の座標の四角の法線の、隣どうしの角（c の向き＝行の間、列の向き）。段の体（c −24.6〜−8.4、列 106〜300、高さ > 0.3 m）で、
        唇の先の回り（列 196〜206）は列の向きから外す（唇の丸みは形の意図）。
原画のカメラは使わない。参照モデル・写真は読まない。
"""
import json
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as05")
import shapeB_common as B  # noqa: E402

H0 = B.H0
CS = [-23.5, -22.5, -21.5, -21.0, -20.0, -19.42, -18.5, -17.5, -14.5, -13.6, -12.5, -11.5, -10.5]


def crossings(a, y, a0, j0, j1):
    """列 j0..j1 の折れ線が縦の線 a = a0 を通る所の (列の位置, y) の列。"""
    out = []
    for j in range(j0, j1):
        d0, d1 = a[j] - a0, a[j + 1] - a0
        if d0 == 0 or d0 * d1 < 0:
            t = d0 / (d0 - d1) if d0 != d1 else 0.0
            out.append((j + t, y[j] + t * (y[j + 1] - y[j])))
    return out


def ycross(a, y, y0, j0, j1):
    out = []
    for j in range(j0, j1):
        d0, d1 = y[j] - y0, y[j + 1] - y0
        if d0 == 0 or d0 * d1 < 0:
            t = d0 / (d0 - d1) if d0 != d1 else 0.0
            out.append((j + t, a[j] + t * (a[j + 1] - a[j])))
    return out


def section(c, A, Y, i):
    a, y = A[i], Y[i]
    je = 130 + int(np.argmax(y[130:201]))
    E = (a[je], y[je]); T = (a[200], y[200])
    r = {"c": round(float(c[i]), 2), "E_y_H0": round(float(E[1] / H0), 3), "T": [round(float(T[0]), 2), round(float(T[1]), 2)]}
    # 唇の下の引っ込みの最も奥（列 200〜300 で y が T.y − 6 m より上の所の最小の a）
    jj = np.arange(200, 300)
    m = y[jj] > T[1] - 6.0
    if m.any():
        jr = int(jj[m][np.argmin(a[jj][m])])
        prot = float(T[0] - a[jr])
        r["lip_protrusion_m"] = round(prot, 2)
        r["recess_col"] = jr
        for nm, a0 in (("head_0.5_m", T[0] - 0.5), ("mid", T[0] - 0.5 * prot)):
            top = [q for q in crossings(a, y, a0, 106, 200)]
            bot = [q for q in crossings(a, y, a0, 200, jr + 1)]
            if top and bot:
                yt = max(q[1] for q in top); yb = max(q[1] for q in bot if q[1] < yt) if any(q[1] < yt for q in bot) else None
                if yb is not None:
                    r[nm] = round(float(yt - yb), 2)
        if "mid" in r and prot > 0:
            r["mid_thick_over_protrusion"] = round(r["mid"] / prot, 3)
    # 下の半分の傾き（内の面、列 200 以後で最初に下向きに通る所）
    yh = 0.5 * T[1]
    c1 = [q for q in ycross(a, y, yh, 200, 398)]
    c2 = [q for q in ycross(a, y, 0.3, 200, 398)]
    if c1 and c2:
        j1, a1 = c1[0]
        later = [q for q in c2 if q[0] > j1]
        if later:
            j2, a2 = later[0]
            da = a2 - a1
            r["lower_half_chord_deg"] = round(float(np.degrees(np.arctan2(yh - 0.3, max(da, 1e-6)))), 1)
            r["lower_half_run_m"] = round(float(da), 2)
            # 区間の中の局所の角（0.25 m ごと）
            ja, jb = int(np.floor(j1)), int(np.ceil(j2))
            seg = np.c_[a[ja:jb + 1], y[ja:jb + 1]]
            d = np.diff(seg, axis=0)
            L = np.hypot(d[:, 0], d[:, 1])
            ang = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
            ok = L > 1e-4
            if ok.any():
                r["lower_half_local_deg_p90"] = round(float(np.percentile(np.abs(ang[ok]), 90)), 1)
    r["back_crest_y_H0"] = round(float(y[:106].max() / H0), 3)
    r["back_minus_E_H0"] = round(float((y[:106].max() - E[1]) / H0), 3)
    return r


def dihedral(c, A, Y, sel_c=(-24.6, -8.4), cols=(106, 300), skip_tip=(196, 206)):
    rows = np.nonzero((c >= sel_c[0]) & (c <= sel_c[1]))[0]
    r0, r1 = rows.min(), rows.max() + 1
    j0, j1 = cols
    cc = np.repeat(c[r0:r1, None], j1 - j0, 1)
    X = B.K.world(c[r0:r1], A[r0:r1, j0:j1], Y[r0:r1, j0:j1]).reshape(r1 - r0, j1 - j0, 3)
    du = X[1:, :-1] - X[:-1, :-1]; dv = X[:-1, 1:] - X[:-1, :-1]
    n = np.cross(du, dv)
    ln = np.linalg.norm(n, axis=-1, keepdims=True)
    n = n / np.maximum(ln, 1e-12)
    yq = Y[r0:r1 - 1, j0:j1 - 1]
    cq = cc[:-1, :-1]
    jq = np.arange(j0, j1 - 1)[None, :].repeat(r1 - r0 - 1, 0)
    ok = (yq > 0.3) & (ln[..., 0] > 1e-8)
    out = {}
    # 行の間（c の向き）
    dr = np.degrees(np.arccos(np.clip((n[1:] * n[:-1]).sum(-1), -1, 1)))
    okr = ok[1:] & ok[:-1]
    # 列の向き
    dc = np.degrees(np.arccos(np.clip((n[:, 1:] * n[:, :-1]).sum(-1), -1, 1)))
    okc = ok[:, 1:] & ok[:, :-1] & ~((jq[:, 1:] >= skip_tip[0]) & (jq[:, 1:] <= skip_tip[1]))
    for nm, D, M, CQ, JQ in (("across_rows", dr, okr, cq[1:], jq[1:]), ("along_cols", dc, okc, cq[:, 1:], jq[:, 1:])):
        v = D[M]
        k = np.argmax(np.where(M, D, -1))
        ki = np.unravel_index(k, D.shape)
        big = M & (D > 30)
        out[nm] = {"max_deg": round(float(v.max()), 1), "p999_deg": round(float(np.percentile(v, 99.9)), 1),
                   "at_c_col": [round(float(CQ[ki]), 2), int(JQ[ki])], "n_over_30": int(big.sum()),
                   "over_30_c_range": [round(float(CQ[big].min()), 2), round(float(CQ[big].max()), 2)] if big.any() else None}
    return out


def mesh_dihedral(path, boxes):
    """静止のメッシュ（主役波の頂点だけ）の、辺を分ける三角形の法線の角。boxes = {名前: (c0, c1)}。高さ > 0.3 m、a は前の側（列の範囲の代わりに
    a ≥ 背の頂の列の a − 1 m はとらず、c の窓だけ）。"""
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/as04")
    import os
    os.environ.setdefault("AS04_FIX", "fix1")
    import asm4_common as A4
    ch, tri, _ = A4.read_static(path)
    nh = int(A4.jl(path)["vertices"])
    pos = ch["position"].astype(np.float64)
    tri = tri[tri[:, 0] < nh].astype(np.int64)
    Q = A4.K.sec(pos[:nh])
    n = np.cross(pos[tri[:, 1]] - pos[tri[:, 0]], pos[tri[:, 2]] - pos[tri[:, 0]])
    ln = np.linalg.norm(n, axis=1)
    n = n / np.maximum(ln, 1e-12)[:, None]
    E = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    F = np.tile(np.arange(len(tri)), 3)
    E.sort(1)
    key = E[:, 0] * (len(pos) + 1) + E[:, 1]
    o = np.argsort(key, kind="stable")
    ks = key[o]
    same = np.nonzero(ks[1:] == ks[:-1])[0]
    f0, f1 = F[o[same]], F[o[same + 1]]
    ang = np.degrees(np.arccos(np.clip((n[f0] * n[f1]).sum(1), -1, 1)))
    ok = (ln[f0] > 1e-10) & (ln[f1] > 1e-10)
    cm = Q[:, 2][tri].mean(1); ym = Q[:, 1][tri].mean(1); am = Q[:, 0][tri].mean(1)
    out = {}
    # 左の端の壁（③ の左の端、c −26〜−20.5、高さ > 0.3 m）：断面の座標 (a, y, c) での三角形の法線が左（−c）を向き（n_c ≤ −0.5）、
    # 水平からの傾きが 45° を超える面の面積（m²、断面の座標で）。a ≥ 1 m の段の体だけ（背の頂の山は変えないので外す）。60° を超える面積も。見本06 の批評の「左の端の壁・端の面」の数
    Pq = Q[tri]
    nq = np.cross(Pq[:, 1] - Pq[:, 0], Pq[:, 2] - Pq[:, 0])
    aq = 0.5 * np.linalg.norm(nq, axis=1)
    nn = nq / np.maximum(2 * aq, 1e-12)[:, None]
    slope = np.degrees(np.arccos(np.clip(np.abs(nn[:, 1]), 0, 1)))
    left = (cm >= -26.0) & (cm <= -20.5) & (ym > 0.3) & (nn[:, 2] <= -0.5) & (am >= 1.0)   # a ≥ 1 m：段の体だけ（背の頂の山の左の斜面は見本04 のまま）
    out["left_end_walls"] = {"area_left_facing_slope_gt45_m2": round(float(aq[left & (slope > 45)].sum()), 2),
                             "area_left_facing_slope_gt60_m2": round(float(aq[left & (slope > 60)].sum()), 2),
                             "area_left_facing_slope_gt75_m2": round(float(aq[left & (slope > 75)].sum()), 2),
                             "max_height_of_gt60_m": round(float(ym[left & (slope > 60)].max()), 2) if (left & (slope > 60)).any() else None}
    for nm, (c0, c1, a_min) in boxes.items():
        m = ok & (cm[f0] >= c0) & (cm[f0] <= c1) & (ym[f0] > 0.3) & (am[f0] >= a_min)
        v = ang[m]
        if not len(v):
            continue
        k = int(np.argmax(np.where(m, ang, -1)))
        big = m & (ang > 30)
        out[nm] = {"edges": int(m.sum()), "max_deg": round(float(v.max()), 1), "p999_deg": round(float(np.percentile(v, 99.9)), 1),
                   "n_over_30": int(big.sum()), "max_at_c_a_y": [round(float(cm[f0[k]]), 2), round(float(am[f0[k]]), 2), round(float(ym[f0[k]]), 2)],
                   "over_30_c": sorted(set(round(float(x), 1) for x in cm[f0[big]]))[:40]}
    return out


def main():
    p = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    c, A, Y = B.load_rows(p)
    res = {"rows": p, "sections": []}
    for cc in CS:
        i = int(np.argmin(np.abs(c - cc)))
        res["sections"].append(section(c, A, Y, i))
    # 左の端の下がり：c −26〜−21 の行で、段の縁（唇の頂、列 160〜205 の最も高い所）と背の頂（列 < 106）の高さを c の向きに比べ、隣の行どうしの傾き（度）の最大
    sel = np.nonzero((c >= -26.0) & (c <= -21.0))[0]
    ye = np.array([Y[i, 160:206].max() for i in sel]); yb = np.array([Y[i, :106].max() for i in sel])
    dc = np.diff(c[sel])
    res["left_end_descent"] = {"c": [round(float(x), 2) for x in c[sel]], "tier_crest_y_m": [round(float(x), 2) for x in ye], "back_crest_y_m": [round(float(x), 2) for x in yb],
                               "tier_crest_max_slope_deg": round(float(np.degrees(np.arctan(np.abs(np.diff(ye)) / dc)).max()), 1),
                               "back_crest_max_slope_deg": round(float(np.degrees(np.arctan(np.abs(np.diff(yb)) / dc)).max()), 1),
                               "back_minus_tier_min_H0_c_le_-21": round(float(((yb - ye) / H0).min()), 3)}
    res["dihedral_tier_bodies"] = dihedral(c, A, Y)
    res["dihedral_flank3"] = dihedral(c, A, Y, (-21.0, -17.0), (150, 300))
    res["dihedral_under2"] = dihedral(c, A, Y, (-12.5, -10.0), (150, 300))
    for a_ in sys.argv:
        if a_.startswith("--mesh="):
            res["mesh_dihedral"] = mesh_dihedral(a_[7:], {"flank3_c-21_-17": (-21.0, -17.0, -1e9), "under2_c-12.5_-10": (-12.5, -10.0, -1e9),
                                                          "tiers_c-24.6_-8.4": (-24.6, -8.4, -1e9)})
            print("mesh_dihedral", json.dumps(res["mesh_dihedral"], ensure_ascii=False))
    if outp:
        B.jdump(outp, res)
    for s in res["sections"]:
        print(" ".join("%s=%s" % (k, v) for k, v in s.items() if k not in ("T",)))
    for k in ("dihedral_tier_bodies", "dihedral_flank3", "dihedral_under2"):
        print(k, json.dumps(res[k], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
