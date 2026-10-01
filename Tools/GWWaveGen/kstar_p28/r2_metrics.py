# -*- coding: utf-8 -*-
"""仕上げ28 第2回（r2）：評審と同じ読みのドームの測りと、第2回で足した測りを候補ごとに出す（py -3.10）。
kh_eval の表（eval/kh_eval_table.md）にない物だけをここで測る：
  * 評審の j_dome（_judge/numbers/j_dome.py の関数をそのまま使う）：R6・R4（j_bulge6、row_step 2・col_step 3）、
    背の楕円の面の割合（K > 0 かつ H > 0）、c 方向に凸（R < 25 m）の割合、背の平面の弓なり（0.5H0・0.7H0、±8 m の弦）、
    F04 の側面の幅、頂の ±2 m の弦の角（手前の尾 c −39.8〜−26.6、本体 c −24〜+12）
  * 背のくびれ（kh_R4_notch、高さ 1〜16 m と手前の足）
  * 唇の縁の波打ち bump4（kh_fit.bump4、d1 の p99・最大）
  * 奥の行の背と管の角の壁の厚さ（c 10〜12.4、水平）
  * 行をまたぐ折れ（面積 > 1e-4 m² の四角の組）> 30°・> 60°
usage: py -3.10 r2_metrics.py <out.json> label=rows.npz ...
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_common as R  # noqa: E402
REPO = R.REPO
# 仕上げ28 の回復：評審の j_dome.py（Git 対象外）の関数の部分をリポジトリへ写した judge_dome_defs.py を読む（中身は同じ）
JD = os.path.join(HERE, "judge_dome_defs.py")
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"))
import kh_R4_notch as NOTCH  # noqa: E402
import kh_fit as KF  # noqa: E402
import r2_build as B  # noqa: E402

src = open(JD, encoding="utf-8").read().split("\nres = {}")[0]
G = {"__name__": "j_dome_defs"}
exec(compile(src, JD, "exec"), G)
Q, pct, back_contours, chord_sag, curv, arcs, RM, KC = G["Q"], G["pct"], G["back_contours"], G["chord_sag"], G["curv"], G["arcs"], G["RM"], G["KC"]


def measure(p):
    z = np.load(p); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    nv, nu = A.shape
    Xw = KC.world(c, A, Y)
    H = Y.max(1); top = Y.argmax(1); r0 = int(np.argmin(np.abs(c))); H0 = H[r0]
    o = {"H0": round(float(H0), 2), "Hmax": round(float(H.max()), 2), "c_Hmax": round(float(c[np.argmax(H)]), 2)}
    b = Q.bulge6(c, A, Y, row_step=2, col_step=3)
    o["R6_p99"], o["R6_max"] = b["R6"]["p99"], b["R6"]["max"]
    o["R4_p99"], o["R4_max"] = b["R4"]["p99"], b["R4"]["max"]
    M = Q._CACHE["bulgemap_R6"]
    reg = {}
    for name, (c0, c1) in {"shoulder<-5": (-16, -5), "main-5..3": (-5, 3), "mid3..9": (3, 9), "far9..16": (9, 16)}.items():
        rr = (c >= c0) & (c < c1)
        reg[name] = pct(M[rr], 99)
    Mb = M.copy(); Ml = M.copy()
    for r in range(nv):
        Mb[r, top[r]:] = np.nan; Ml[r, :top[r]] = np.nan
    reg["back-cols"] = pct(Mb, 99); reg["lip-cols(top..)"] = pct(Ml, 99)
    o["R6_regions_p99"] = reg
    kc, K, Hm, area = curv(c, Xw)
    msk = np.zeros_like(Y, bool)
    for r in range(nv):
        if -16 <= c[r] <= 12 and H[r] > 3:
            msk[r, 18:top[r] + 1] = True
    msk &= Y >= 0.3 * H[:, None]
    w = area[msk]
    o["back_elliptic_frac"] = round(float(w[(K[msk] > 1 / 900.) & (Hm[msk] > 0)].sum() / w.sum()), 3)
    o["back_convex_along_c_R25_frac"] = round(float(w[kc[msk] > 1 / 25.].sum() / w.sum()), 3)
    m2 = msk & (Y >= 0.6 * H[:, None]); w2 = area[m2]
    o["upper_back_elliptic_frac"] = round(float(w2[(K[m2] > 1 / 900.) & (Hm[m2] > 0)].sum() / w2.sum()), 3)
    bc = back_contours(c, A, Y, [0.5 * H0, 0.7 * H0]); cq = np.arange(-16, 12.01, 0.5)
    for h, ab in bc.items():
        o["back_plan_bow_%.1fH0_L8_max_m" % (h / H0)] = pct(chord_sag(c, ab, cq, 8.0), 100)
    lo, hi = [], []
    for r in range(nv):
        if H[r] < 0.5 * H0:
            lo.append(np.nan); hi.append(np.nan); continue
        xs = RM.crossings(RM.poly_to_segs(A[r], Y[r]), 0.5 * H0)
        if len(xs) >= 2:
            lo.append(xs.min()); hi.append(xs.max())
        else:
            lo.append(np.nan); hi.append(np.nan)
    lo = np.array(lo); hi = np.array(hi)
    o["F04_side_width_0.5H0_m"] = round(float(np.nanmax(hi) - np.nanmin(lo)), 2)
    o["F04_rows_abs_c_le_6_m"] = round(float(np.nanmax(hi[np.abs(c) <= 6]) - np.nanmin(lo[np.abs(c) <= 6])), 2)
    ang = arcs(c, A, Y)
    tail = (c >= -39.8) & (c <= -26.6); main = (c >= -24) & (c <= 12)
    o["arcs_pm2m"] = {"near_tail_min_deg": pct(ang[tail], 0), "near_tail_rows_lt110": int(np.nansum(ang[tail] < 110)),
                      "main_min_deg": pct(ang[main], 0), "main_rows_lt110": int(np.nansum(ang[main] < 110))}
    nt = NOTCH.all_notches(c, A, Y)
    o["waist_notch"] = {"body_max_m": round(float(max(v[0] for v in nt["c-10..+12_h1..16"].values())), 3),
                        "near_foot_max_m": round(float(max(v[0] for v in nt["c-30..-10_h1..4.5"].values())), 3)}
    bb = KF.bump4(c, A, Y)
    o["bump4_d1_p99_max"] = [round(float(np.percentile(bb["d1"], 99)), 3), round(float(bb["d1"].max()), 3)]
    walls = {}
    for cc in (10.0, 10.4, 10.8, 11.2, 11.6, 12.0, 12.4):
        i = int(np.argmin(abs(c - cc))); jj = np.arange(230, 379)
        walls["%.1f" % cc] = round(B.Build.wall_min_of(np.c_[A[i, 18:90], Y[i, 18:90]], A[i, jj], Y[i, jj]), 2)
    o["far_back_to_tube_wall_m"] = walls
    a = Xw[1:, :-1] - Xw[:-1, :-1]; bq = Xw[:-1, 1:] - Xw[:-1, :-1]
    n = np.cross(bq, a); L = np.linalg.norm(n, axis=-1); n = n / np.maximum(L, 1e-12)[..., None]
    d = np.degrees(np.arccos(np.clip((n[1:] * n[:-1]).sum(-1), -1, 1)))
    ok = (L[1:] > 1e-4) & (L[:-1] > 1e-4)
    o["cross_row_folds_gt30_gt60"] = [int(((d > 30) & ok).sum()), int(((d > 60) & ok).sum())]
    return o


def main():
    out = sys.argv[1]
    res = {}
    for arg in sys.argv[2:]:
        lab, p = arg.split("=", 1)
        res[lab] = {"rows": p, **measure(p)}
        print(lab, json.dumps({k: v for k, v in res[lab].items() if k not in ("rows", "R6_regions_p99", "far_back_to_tube_wall_m")}, ensure_ascii=False), flush=True)
    R.jdump(res, out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
