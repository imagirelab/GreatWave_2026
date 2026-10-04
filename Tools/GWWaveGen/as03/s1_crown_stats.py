# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：s1_crown.py の一時の結果（キャッシュのフォルダー）から、波頭の冠の数をまとめる（数だけ）。
H（主の頂の高さ）・L（冠の縁の長さ）を参照モデルの上で測り、指の数・長さ・太さ・細り・枝分かれ・先の形・向き・列・すき間を、
H と L に対する比で出す。出力は study/s1_crown_numbers%s.json（数だけ。形・頂点・画像は書かない）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_crown_stats.py <tag>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_obj as SO  # noqa: E402

SEA_Y = 1.1982310754126466     # 整列 B の参照モデルの海面（世界 y の中央値。align_B_upright.json）


def st(x, nd=3):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "p10": round(float(np.percentile(x, 10)), nd), "p25": round(float(np.percentile(x, 25)), nd),
            "p50": round(float(np.percentile(x, 50)), nd), "p75": round(float(np.percentile(x, 75)), nd),
            "p90": round(float(np.percentile(x, 90)), nd), "mean": round(float(x.mean()), nd)}


def smooth(x, k=9):
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    if ok.sum() < 3:
        return x
    xi = np.interp(np.arange(len(x)), np.nonzero(ok)[0], x[ok])
    ker = np.ones(k) / k
    xs = np.convolve(np.pad(xi, k // 2, mode="edge"), ker, mode="valid")
    xs[~ok] = np.nan
    return xs


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "_v06"
    R = json.load(open(SO.CACHE_DIR + "/tmp_crown_raw%s.json" % tag))
    c = np.array(R["c"])
    ty = np.array(R["body_top_y"], float)
    ta = np.array(R["body_top_a"], float)
    oy = np.array(R["occ_top_y"], float)
    cl = R["claws"]
    root = np.array([q["root"] for q in cl])
    tip = np.array([q["tip"] for q in cl])
    Lg = np.array([q["len_geo"] for q in cl])
    Lc = np.array([q["len_chord"] for q in cl])
    rp = np.array([q["r_profile"] for q in cl], float)        # 10 区間の半径 [m]
    H_body = float(np.nanmax(ty)) - SEA_Y
    H_occ = float(np.nanmax(oy)) - SEA_Y
    H = H_occ
    # 冠の範囲（指の根元の c の範囲）と縁の線の長さ
    c_lo, c_hi = float(np.percentile(root[:, 2], 1)), float(np.percentile(root[:, 2], 99))
    sel = (c >= c_lo) & (c <= c_hi) & np.isfinite(ty)
    tys, tas = smooth(ty, 15), smooth(ta, 15)
    P = np.stack([tas[sel], tys[sel], c[sel]], 1)
    L_top = float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)))
    # 前の縁（唇）の線：各 c で、胴の y が 12〜22 m の帯での a の最大（最も前）とその高さ
    lip_a = np.full(len(c), np.nan)
    lip_y = np.full(len(c), np.nan)
    for key, d in R["body_a_at_y"].items():
        am = np.array(d["amax"], float)
        better = np.isfinite(am) & (~np.isfinite(lip_a) | (am > lip_a))
        lip_a[better] = am[better]
        lip_y[better] = float(key)
    la, ly = smooth(lip_a, 15), smooth(lip_y, 15)
    Pl = np.stack([la[sel], ly[sel], c[sel]], 1)
    okl = np.all(np.isfinite(Pl), 1)
    L_lip = float(np.sum(np.linalg.norm(np.diff(Pl[okl], axis=0), axis=1)))
    # 根元の場所：その c の胴の頂からの下がり（y）と前への出（a）
    yk = np.interp(root[:, 2], c[np.isfinite(tys)], tys[np.isfinite(tys)])
    ak = np.interp(root[:, 2], c[np.isfinite(tas)], tas[np.isfinite(tas)])
    dy = root[:, 1] - yk
    da = root[:, 0] - ak
    # 根元の向きの分け：前（唇の側、a が頂より前）か後ろか
    front = da > 0
    # 太さ：根元 0〜0.2 の最大、中 0.4〜0.6、先 0.8〜1.0 の半径
    r_base = np.nanmax(rp[:, 0:2], 1)
    r_mid = np.nanmax(rp[:, 4:6], 1)
    r_tip = np.nanmax(rp[:, 8:10], 1)
    r_last = rp[:, 9]
    r_neck = rp[:, 7]
    # 細りの法則：r(f)/r_base を f = 0.05..0.95 で 1 − k f^p に合わせる（全部の指の中央値で）
    f = (np.arange(10) + 0.5) / 10
    rn = rp / np.maximum(r_base[:, None], 1e-6)
    med = np.nanmedian(rn, 0)
    best = None
    for p_ in np.linspace(0.3, 3.0, 55):
        for k_ in np.linspace(0.0, 1.0, 101):
            e = np.nansum((1 - k_ * f ** p_ - med) ** 2)
            if best is None or e < best[0]:
                best = (e, k_, p_)
    # 先の形：先の区間の半径 / 首（0.7〜0.8）の半径。≥ 1 は丸い膨らみ（しずく）、0.6〜1 は丸い先、< 0.6 は尖る
    tip_ratio = r_last / np.maximum(r_neck, 1e-6)
    shape = np.where(tip_ratio >= 1.0, "bulb", np.where(tip_ratio >= 0.6, "rounded", "sharp"))
    # 枝分かれ
    fe = np.array([q["free_ends"] for q in cl])
    brf = [x for q in cl for x in q["branch_fr"] if 0.1 < x < 0.95]
    # 向き
    A = lambda k: np.array([q[k] for q in cl])
    dall = np.array([q["dall"] for q in cl])
    dtip = np.array([q["dtip"] for q in cl])
    d0 = np.array([q["d0"] for q in cl])
    out = {
        "tag": tag, "vox_m": R["vox_m"], "r_open_m": R["r_open_m"], "min_len_m": R["min_len_m"], "y_lo": R["y_lo"],
        "H_ref_m": round(H, 3), "H_ref_body_m": round(H_body, 3), "sea_y": SEA_Y,
        "crown_c_range_m": [round(c_lo, 2), round(c_hi, 2)],
        "L_top_m": round(L_top, 3), "L_lip_m": round(L_lip, 3),
        "n_fingers": int(len(cl)),
        "fingers_per_m_top": round(len(cl) / L_top, 3), "fingers_per_m_lip": round(len(cl) / L_lip, 3),
        "fingers_per_H_of_rim": round(len(cl) / L_top * H, 3),
        "len_geo_m": st(Lg), "len_geo_over_H": st(Lg / H), "len_chord_over_geo": st(Lc / np.maximum(Lg, 1e-6)),
        "r_base_m": st(r_base), "r_mid_m": st(r_mid), "r_tip_m": st(r_tip),
        "diam_base_over_H": st(2 * r_base / H), "diam_tip_over_H": st(2 * r_tip / H),
        "len_over_base_diam": st(Lg / np.maximum(2 * r_base, 1e-6)),
        "r_profile_norm_median": [round(float(x), 3) for x in med],
        "taper_fit": {"law": "r/r_base = 1 - k f^p (f = 道のりの割合)", "k": round(best[1], 3), "p": round(best[2], 3)},
        "tip_ratio_last_over_neck": st(tip_ratio), "tip_shape_counts": {s: int((shape == s).sum()) for s in ("bulb", "rounded", "sharp")},
        "free_ends_per_finger": st(fe), "free_ends_hist": {str(k): int((fe == k).sum()) for k in range(0, 7)},
        "branch_point_fraction_of_length": st(brf),
        "root_dy_below_body_top_m": st(dy), "root_dy_over_H": st(dy / H), "root_da_in_front_of_top_m": st(da),
        "root_front_fraction": round(float(front.mean()), 3),
        "ang_overall_vs_normal_deg": st(A("ang_all_n")), "ang_root_vs_normal_deg": st(A("ang_root_n")), "ang_tip_vs_normal_deg": st(A("ang_tip_n")),
        "ang_overall_vs_up_deg": st(A("ang_all_up")), "ang_tip_vs_up_deg": st(A("ang_tip_up")), "ang_root_vs_up_deg": st(A("ang_root_up")),
        "ang_overall_vs_forward_deg": st(A("ang_all_fwd")), "curl_root_to_tip_deg": st(A("curl")),
        "tip_dir_down_fraction": round(float((dtip[:, 1] < 0).mean()), 3), "overall_dir_down_fraction": round(float((dall[:, 1] < 0).mean()), 3),
        "overall_dir_forward_fraction": round(float((dall[:, 0] > 0).mean()), 3),
        "by_group": {},
    }
    # 前（唇の側）と後ろ・頂の上の群に分けた向き
    for nm, s_ in (("front_of_top", da > 0.5), ("on_top", np.abs(da) <= 0.5), ("behind_top", da < -0.5)):
        if s_.sum() == 0:
            continue
        out["by_group"][nm] = {"n": int(s_.sum()), "len_over_H": st(Lg[s_] / H), "ang_overall_vs_up_deg": st(A("ang_all_up")[s_]),
                               "ang_tip_vs_up_deg": st(A("ang_tip_up")[s_]), "ang_overall_vs_normal_deg": st(A("ang_all_n")[s_]),
                               "tip_down_fraction": round(float((dtip[s_, 1] < 0).mean()), 3), "root_dy_over_H": st(dy[s_] / H)}
    # 列（層）：前の群の根元の、頂からの下がりの分布を 0.5 m 刻みで数える
    hist, edges = np.histogram(dy, bins=np.arange(np.floor(dy.min()), 0.51, 0.5))
    out["root_dy_hist_0p5m"] = {"edges": [round(float(e), 2) for e in edges], "counts": [int(h) for h in hist]}
    # c ごとの数（3 m の窓）と、最も近い根元の間隔
    from scipy.spatial import cKDTree
    tr = cKDTree(root)
    dd, jj = tr.query(root, k=2)
    out["nearest_root_spacing_m"] = st(dd[:, 1])
    out["nearest_root_spacing_over_len"] = st(dd[:, 1] / Lg)
    # 隣の指との向きの開き
    fan = [float(np.degrees(np.arccos(np.clip(dall[i] @ dall[jj[i, 1]], -1, 1)))) for i in range(len(cl))]
    out["fan_angle_to_nearest_deg"] = st(fan)
    # 前から見たすき間：唇の前の帯（各 c の唇の高さの下 0〜2 m）で、指が覆う割合（前から +a 向きの投影）
    json.dump(out, open(SO.STUDY + "/s1_crown_numbers%s.json" % tag, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
