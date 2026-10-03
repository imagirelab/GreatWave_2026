# -*- coding: utf-8 -*-
"""美術の見本02 BACK：背が一つの山かを測る（要求書 S4）。py -3.10 back_measure.py <out.json> label=rows.npz [label=rows.npz ...]

測るもの（どれも参照モデルを読まない）：
  H(c)          行ごとの頂の高さ（シートの行の座標 c）。一つの山か（へこみの深さ dip ＝ 水を張った時の深さ）。
  背の等高線     高さ f·H0 ごとの背の位置 d(c) = −a_back（平面で後ろへ出ているほど大きい）。
                 入り江の深さ bay（上に凸な包絡との差 ＝ 平面の等高線の背の側の凹み）と、へこみの深さ dip。
                 弦（等高線の両端を結ぶ線）からの出っ張り g(c) の最大の位置（中ほどにあるか）。
  縦の溝         d(c) の c 方向の二階微分（σ 0.6 m でならす）の正の最大（溝の強さ、1/m）。
  後ろからの輪郭 粘土の描画と同じカメラ（後ろ 65° b65、真後ろ b90、−c 側の後ろ b115）の画で、各画素の列の波の一番上。
                 一つの山か（dip、画素）と、その輪郭を作る行の c。
  F04 の近い値   側面の影の幅（すべての行の断面を重ねた a の幅、0.5H0・0.9H0）、奥（c > 0）の水面より上の断面積の和。
                 （評価基準 rubric の定義と同じ読み。正の値は rubric_check で確かめる）
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import back_common as BC  # noqa: E402

LEVELS = (0.05, 0.15, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90)
VIEWS = ("b65_back65_clay", "b90_back_straight", "b115_back_minus_c")
WIN_C0 = -14.0          # b区域（c < −14）は別の稜（F10 の「肩の第二の波頭」）として、背の山の読みから外す


def side_shadow_width(A, Y, f):
    y = f * BC.H0
    lo, hi = np.inf, -np.inf
    for i in range(len(A)):
        a, yy = A[i], Y[i]
        s = np.sign(yy - y)
        k = np.nonzero(s[:-1] * s[1:] < 0)[0]
        if not len(k):
            continue
        t = (y - yy[k]) / (yy[k + 1] - yy[k])
        aa = a[k] + t * (a[k + 1] - a[k])
        lo = min(lo, aa.min()); hi = max(hi, aa.max())
    return float(hi - lo) if np.isfinite(lo) else 0.0


def section_area(a, y):
    yy = np.maximum(y, 0.0)
    P = np.c_[np.r_[a, a[-1], a[0]], np.r_[yy, 0.0, 0.0]]
    x, z = P[:, 0], P[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1)))


def measure(c, A, Y, views):
    H, jt, at = BC.crest(A, Y)
    out = {}
    hw = c >= WIN_C0
    out["H"] = {"all_rows": BC.shape_stats(c, H), "hero_window_c_ge_-14": BC.shape_stats(c[hw], H[hw])}
    out["H_profile"] = {"c": [round(float(x), 3) for x in c], "H": [round(float(x), 4) for x in H], "a_top": [round(float(x), 4) for x in at]}
    lv = {}
    _, _, _, prof = BC.back_profiles(c, A, Y, LEVELS)
    for k, v in prof.items():
        d = -v["a_back"]
        ok = np.isfinite(d) & (c >= WIN_C0)
        # c −0.8 を含む連続区間
        im = int(np.argmin(np.abs(c + 0.8)))
        idx = np.nonzero(ok)[0]
        if not ok[im] or len(idx) < 5:
            continue
        i0 = im
        while i0 - 1 >= 0 and ok[i0 - 1]:
            i0 -= 1
        i1 = im
        while i1 + 1 < len(c) and ok[i1 + 1]:
            i1 += 1
        cc = c[i0:i1 + 1]; dd = d[i0:i1 + 1]
        chord = dd[0] + (dd[-1] - dd[0]) * (cc - cc[0]) / max(cc[-1] - cc[0], 1e-9)
        g = dd - chord
        gr = BC.lateral_groove(cc, dd)
        st = BC.shape_stats(cc, dd)
        kg = int(np.argmax(g))
        rel = (v["depth_behind_crest"])[i0:i1 + 1]
        lv[k] = {"y_m": round(v["y"], 3), "c_range": [round(float(cc[0]), 2), round(float(cc[-1]), 2)],
                 "dip_depth_m": round(st["dip_depth"], 3), "c_at_dip": round(st["x_at_dip"], 2),
                 "bay_depth_m": round(st["bay_depth"], 3), "c_at_bay": round(st["x_at_bay"], 2),
                 "bulge_over_chord_max_m": round(float(g[kg]), 3), "c_at_bulge_max": round(float(cc[kg]), 2),
                 "bulge_over_chord_dip_m": round(float(BC.dip_profile(g).max()), 3),
                 "groove_curv_max_per_m": round(float(np.nanmax(gr)), 4), "c_at_groove": round(float(cc[int(np.nanargmax(gr))]), 2),
                 "thickness_behind_crest_max_m": round(float(np.nanmax(rel)), 3), "c_at_thickness_max": round(float(cc[int(np.nanargmax(rel))]), 2),
                 "thickness_dip_m": round(float(BC.dip_profile(rel).max()), 3),
                 "profile": {"c": [round(float(x), 3) for x in cc], "d": [round(float(x), 4) for x in dd], "bulge": [round(float(x), 4) for x in g]}}
    out["levels"] = lv
    sv = {}
    allv = BC.load_views()
    for vn in views:
        v = allv[vn]
        top, ctop = BC.silhouette_top(c, A, Y, v)
        ok = np.isfinite(top)
        xs = np.nonzero(ok)[0]
        hgt = (v["h"] - top[ok])          # 画素の高さ（上ほど大きい）
        # 背の山の範囲だけ（b区域より +c 側）
        cw = ctop[ok] >= WIN_C0
        st_all = BC.shape_stats(xs.astype(float), hgt)
        st_w = BC.shape_stats(xs[cw].astype(float), hgt[cw]) if cw.sum() > 5 else None
        sv[vn] = {"all": st_all, "hero_window": st_w,
                  "profile": {"x": xs.tolist(), "h_px": [round(float(x), 2) for x in hgt], "c": [round(float(x), 2) for x in ctop[ok]]}}
    out["silhouette_views"] = sv
    vol = sum(section_area(A[i], Y[i]) * (c[min(i + 1, len(c) - 1)] - c[max(i - 1, 0)]) * 0.5 for i in range(len(c)) if c[i] > 0)
    out["F04_like"] = {"side_shadow_0p5H0_m": round(side_shadow_width(A, Y, 0.5), 3),
                       "side_shadow_0p9H0_m": round(side_shadow_width(A, Y, 0.9), 3),
                       "far_volume_c_gt_0_m3": round(float(vol), 1),
                       "highest_point": {"H_over_H0": round(float(H.max() / BC.H0), 4), "c": round(float(c[int(np.argmax(H))]), 2)},
                       "front_width_rows_H_ge_0p75H0_m": round(float(np.ptp(c[H >= 0.75 * BC.H0])), 2)}
    return out


def summary(m):
    lv = m["levels"]
    return {"H_dip_hero_m": round(m["H"]["hero_window_c_ge_-14"]["dip_depth"], 3),
            "H_dip_all_m": round(m["H"]["all_rows"]["dip_depth"], 3),
            "H_max_c": m["H"]["all_rows"]["x_at_max"],
            "back_dip_max_m": max(v["dip_depth_m"] for v in lv.values()),
            "back_bay_max_m": max(v["bay_depth_m"] for v in lv.values()),
            "back_bulge_dip_max_m": max(v["bulge_over_chord_dip_m"] for v in lv.values()),
            "groove_curv_max": max(v["groove_curv_max_per_m"] for v in lv.values()),
            "bulge_peak_c_by_level": {k: v["c_at_bulge_max"] for k, v in lv.items()},
            "silhouette_dip_px_hero": {k: (round(v["hero_window"]["dip_depth"], 2) if v["hero_window"] else None) for k, v in m["silhouette_views"].items()},
            "silhouette_dip_px_all": {k: round(v["all"]["dip_depth"], 2) for k, v in m["silhouette_views"].items()},
            "F04_like": m["F04_like"]}


def main():
    out = sys.argv[1]
    res = {"schema": "GreatWave.AS02.back_measure/1", "levels_f_of_H0": LEVELS, "H0_m": BC.H0, "window_c0": WIN_C0,
           "views": VIEWS, "inputs": {}, "measure": {}, "summary": {}}
    for arg in sys.argv[2:]:
        lab, p = arg.split("=", 1)
        c, A, Y = BC.load_rows(p)
        res["inputs"][lab] = {"rows": p, "sha256": BC.sha256(p)}
        m = measure(c, A, Y, VIEWS)
        res["measure"][lab] = m
        res["summary"][lab] = summary(m)
    BC.jdump(res, out)
    for lab, s in res["summary"].items():
        print(lab, json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
