# -*- coding: utf-8 -*-
"""仕上げ28修正01 の変種 RIDGE：kh_eval・r2_metrics にない、この変種の測り（py -3.10）。
  * 背の溝（後ろから見た縦の溝）：各高さ y の背の等高線 b(c) = −a_b(c, y)（後ろへの出）について、c −8〜+8 の「水の溜まる深さ」
    max_c [min(左の最大, 右の最大) − b(c)] を測る（へこみ＝溝。0 なら溝がない）。高さ 4〜19 m（1 m ごと）の最大と、その c・y。
  * 頂の線（背骨：列 90 の点 (a, H)）の 3 次元の曲がり（1/m）の最大と場所、立面 H(c) の原画の頂（c −2.4〜+1）の後ろのへこみ
    （原画の頂の最高 − c +3 までの最小）、最高点の H と c、H の 2 階差の最大。
  * 頂の丸み：c −2〜+9 の各行の頂の ±2 m の弦の角と、頂の 3 点の円の半径（rubric の F02 と同じ読みではない、記録用の速い読み）。
usage: py -3.10 r01_ridge_metrics.py <out.json> label=rows.npz ...
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_ridge_common as RR  # noqa: E402
import r01_ridge_build as RB  # noqa: E402


def groove(c, A, Y, ys=np.arange(4.0, 19.01, 1.0), c0=-8.0, c1=12.0):
    out = []
    for y in ys:
        ab = RB.RidgeBuild.back_contour(A, Y, y)
        m = np.isfinite(ab) & (c >= c0) & (c <= c1)
        if m.sum() < 5:
            continue
        cc = c[m]; b = -ab[m]
        lm = np.maximum.accumulate(b); rm = np.maximum.accumulate(b[::-1])[::-1]
        d = np.minimum(lm, rm) - b
        k = int(np.argmax(d))
        out.append([float(y), round(float(d[k]), 3), round(float(cc[k]), 2)])
    return out


def chord_angle(a, y, j, L=2.0):
    s = np.r_[0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]
    s0 = s[j]
    pa = np.array([np.interp(s0 - L, s, a), np.interp(s0 - L, s, y)]); pb = np.array([np.interp(s0 + L, s, a), np.interp(s0 + L, s, y)])
    p0 = np.array([a[j], y[j]])
    u = pa - p0; v = pb - p0
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-12), -1, 1))))


def measure(p):
    z = np.load(p); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    g = groove(c, A, Y)
    gm = max(g, key=lambda x: x[1]) if g else None
    H = Y[:, 90]
    top = (c >= -2.4) & (c <= 1.0); after = (c > -0.8) & (c <= 3.0)
    Hpk = float(H[top].max()); dip = Hpk - float(H[after].min())
    Hm = Y.max(1)
    rows = np.nonzero((c >= -2.0) & (c <= 9.0))[0]
    ch = []
    for i in rows:
        jt = int(np.argmax(Y[i, :200]))
        ch.append([round(float(c[i]), 2), round(chord_angle(A[i], Y[i], jt), 1)])
    chv = np.array([x[1] for x in ch])
    d2 = np.abs(np.diff(Hm, 2)); d2m = float(d2[Hm[1:-1] > 5].max())
    # 評価基準 F02 と同じ読みの頂の円の半径（rubric_check.corner_q17、H ≥ 0.5 H0 の行）
    sys.path.insert(0, os.path.join(RR.REPO, "Tools", "GWWaveGen", "rubric"))
    import rubric_check as RCK
    H0 = Hm[int(np.argmin(np.abs(c)))]
    big = np.nonzero(Hm >= 0.5 * H0)[0]
    rq = {int(r): RCK.corner_q17(A[r], Y[r], 200) for r in big}
    z1 = [r for r in big if -5 <= c[r] <= 3]; z2 = [r for r in big if c[r] > 3]
    rmin1 = min(z1, key=lambda r: rq[r]["Rmin_m"]); rmin2 = min(z2, key=lambda r: rq[r]["Rmin_m"])
    f02 = {"Rmin_c-5_3": [round(rq[rmin1]["Rmin_m"], 3), round(float(c[rmin1]), 2)], "Rmin_far": [round(rq[rmin2]["Rmin_m"], 3), round(float(c[rmin2]), 2)],
           "rows_c-5_3_Rmin_lt1.5": [round(float(c[r]), 1) for r in z1 if rq[r]["Rmin_m"] < 1.5],
           "chord2_min_c-5_3": round(min(rq[r]["chord2_deg"] for r in z1), 1), "fold_max_c-5_3": round(max(rq[r]["fold_deg"] for r in z1), 2)}
    return {"rows_sha256": RR.sha256(p), "groove_depth_by_y": g, "groove_max": gm,
            "spine3d": RB.spine_curvature(c, A, Y), "H_top_painted": round(Hpk, 3), "H_dip_behind_painted_top_m": round(dip, 3),
            "H_max": round(float(Hm.max()), 3), "c_H_max": round(float(c[int(np.argmax(Hm))]), 2), "H_d2_max_m": round(d2m, 3),
            "top_chord_pm2m_min_deg_c-2_9": [round(float(chv.min()), 1), ch[int(np.argmin(chv))][0]],
            "top_chord_rows_lt125": int((chv < 125).sum()), "top_chord_rows_lt110": int((chv < 110).sum()), "F02_like": f02}


def main():
    out = sys.argv[1]
    res = {}
    for a in sys.argv[2:]:
        k, p = a.split("=", 1)
        res[k] = measure(p)
        r = res[k]
        print(k, "groove max", r["groove_max"], "| spine kappa", r["spine3d"]["kappa_max_per_m"], "@", r["spine3d"]["c_of_kappa_max"],
              "| dip", r["H_dip_behind_painted_top_m"], "| Hmax", r["H_max"], "@", r["c_H_max"], "| chord min", r["top_chord_pm2m_min_deg_c-2_9"],
              "<125:", r["top_chord_rows_lt125"], "| F02", r["F02_like"], flush=True)
    RR.jdump(res, out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
