# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：s1_crown2.py の一時の結果から、冠の数を H（主の頂の高さ）・L（冠の縁の長さ）に対する比でまとめる（数だけ）。
出力：study/s1_crown2_numbers<tag>.json（形・頂点・画像は書かない）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_crown2_stats.py <tag>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_obj as SO  # noqa: E402

SEA_Y = 1.1982310754126466


def st(x, nd=3):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "p10": round(float(np.percentile(x, 10)), nd), "p25": round(float(np.percentile(x, 25)), nd),
            "p50": round(float(np.percentile(x, 50)), nd), "p75": round(float(np.percentile(x, 75)), nd),
            "p90": round(float(np.percentile(x, 90)), nd), "mean": round(float(x.mean()), nd)}


def smooth_nan(x, k):
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    xi = np.interp(np.arange(len(x)), np.nonzero(ok)[0], x[ok])
    ker = np.ones(k) / k
    return np.convolve(np.pad(xi, k // 2, mode="edge"), ker, mode="valid")[:len(x)]


def rim(R, c_lo, c_hi):
    c = np.array(R["c"])
    ty = np.array(R["body_top_y"], float)
    ta = np.array(R["body_top_a"], float)
    vox = R["vox_m"]
    k1 = max(3, int(round(1.0 / vox)) | 1)      # 高さは 1 m の窓
    k3 = max(3, int(round(3.0 / vox)) | 1)      # 平面の曲がりは 3 m の窓
    ys = smooth_nan(ty, k1)
    as_ = smooth_nan(ta, k3)
    s = (c >= c_lo) & (c <= c_hi)
    P = np.stack([as_[s], ys[s], c[s]], 1)
    L3 = float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)))
    Pc = np.stack([ys[s], c[s]], 1)
    Lcy = float(np.sum(np.linalg.norm(np.diff(Pc, axis=0), axis=1)))
    return L3, Lcy, c, ys, as_


def summarize(R, cl, H, L, c, ys, as_, label):
    if not cl:
        return {"n": 0}
    root = np.array([q["root"] for q in cl])
    tip = np.array([q["tip"] for q in cl])
    Lg = np.array([q["len_geo"] for q in cl])
    rp = np.array([q["r_profile"] for q in cl], float)
    r_base = np.nanmax(rp[:, 0:2], 1)
    r_mid = np.nanmax(rp[:, 4:6], 1)
    r_tip = np.nanmax(rp[:, 8:10], 1)
    r_last = rp[:, 9]
    r_neck = rp[:, 7]
    yk = np.interp(root[:, 2], c, ys)
    ak = np.interp(root[:, 2], c, as_)
    dy = root[:, 1] - yk
    da = root[:, 0] - ak
    dall = np.array([q["dall"] for q in cl])
    dtip = np.array([q["dtip"] for q in cl])
    A = lambda k: np.array([q[k] for q in cl])
    f = (np.arange(10) + 0.5) / 10
    rn = rp / np.maximum(r_base[:, None], 1e-6)
    med = np.nanmedian(rn, 0)
    best = None
    for p_ in np.linspace(0.3, 3.0, 55):
        for k_ in np.linspace(0.0, 1.0, 101):
            e = np.nansum((1 - k_ * f ** p_ - med) ** 2)
            if best is None or e < best[0]:
                best = (e, k_, p_)
    tip_ratio = r_last / np.maximum(r_neck, 1e-6)
    out = {
        "label": label, "n": int(len(cl)), "per_m_of_L": round(len(cl) / L, 3), "per_H_of_L": round(len(cl) / L * H, 3),
        "len_geo_m": st(Lg), "len_over_H": st(Lg / H, 4),
        "diam_base_over_H": st(2 * r_base / H, 4), "diam_mid_over_H": st(2 * r_mid / H, 4), "diam_tip_over_H": st(2 * r_tip / H, 4),
        "len_over_base_diam": st(Lg / np.maximum(2 * r_base, 1e-6)),
        "r_profile_norm_median_10bands": [round(float(x), 3) for x in med],
        "taper_fit_r_over_rbase_eq_1_minus_k_f_pow_p": {"k": round(best[1], 3), "p": round(best[2], 3)},
        "tip_last_over_neck_radius": st(tip_ratio),
        "tip_class_counts": {"bulb_ge1.0": int((tip_ratio >= 1.0).sum()), "rounded_0.6_1.0": int(((tip_ratio >= 0.6) & (tip_ratio < 1.0)).sum()),
                             "narrow_lt0.6": int((tip_ratio < 0.6).sum())},
        "root_dy_below_rim_over_H": st(dy / H, 4), "root_da_ahead_of_rim_over_H": st(da / H, 4),
        "root_height_above_sea_over_H": st((root[:, 1] - SEA_Y) / H, 4),
        "ang_overall_vs_normal_deg": st(A("ang_all_n"), 1), "ang_root_vs_normal_deg": st(A("ang_root_n"), 1),
        "ang_overall_vs_up_deg": st(A("ang_all_up"), 1), "ang_tip_vs_up_deg": st(A("ang_tip_up"), 1),
        "curl_root_to_tip_deg": st(A("curl"), 1),
        "frac_tip_pointing_down": round(float((dtip[:, 1] < 0).mean()), 3), "frac_overall_down": round(float((dall[:, 1] < 0).mean()), 3),
        "frac_overall_forward_plus_a": round(float((dall[:, 0] > 0).mean()), 3),
        "ang_overall_vs_forward_plus_a_deg": st(np.degrees(np.arccos(np.clip(dall[:, 0], -1, 1))), 1),
    }
    if "n_tips" in cl[0]:
        nt = np.array([q["n_tips"] for q in cl])
        out["skeleton_tips_per_unit"] = st(nt)
        out["skeleton_tips_hist"] = {str(k): int((nt == k).sum()) for k in range(0, int(nt.max()) + 1) if (nt == k).any()}
    groups = {}
    for nm, s_ in (("ahead_of_rim_da_gt_0.5m", da > 0.5), ("on_rim_abs_da_le_0.5m", np.abs(da) <= 0.5), ("behind_rim_da_lt_-0.5m", da < -0.5)):
        if s_.sum():
            groups[nm] = {"n": int(s_.sum()), "len_over_H": st(Lg[s_] / H, 4), "ang_overall_vs_up_deg": st(A("ang_all_up")[s_], 1),
                          "ang_tip_vs_up_deg": st(A("ang_tip_up")[s_], 1), "ang_overall_vs_normal_deg": st(A("ang_all_n")[s_], 1),
                          "frac_tip_down": round(float((dtip[s_, 1] < 0).mean()), 3), "root_dy_below_rim_over_H": st(dy[s_] / H, 4)}
    out["by_position"] = groups
    # 高さの帯（海面からの高さ / H）ごとの数
    h = (root[:, 1] - SEA_Y) / H
    out["count_by_root_height_over_H"] = {"edges": [0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                                          "counts": [int(x) for x in np.histogram(h, bins=[0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])[0]]}
    out["count_by_c_4m"] = {"edges": list(range(-17, 18, 4)), "counts": [int(x) for x in np.histogram(root[:, 2], bins=np.arange(-17, 18, 4))[0]]}
    # 列（層）：根元の、縁の線からの下がり（dy/H）の分布 0.02 H 刻み
    hist, edges = np.histogram(dy / H, bins=np.arange(-0.6, 0.06, 0.04))
    out["rows_dy_over_H_hist_0p04"] = {"edges": [round(float(e), 3) for e in edges], "counts": [int(x) for x in hist]}
    from scipy.spatial import cKDTree
    tr = cKDTree(root)
    dd, jj = tr.query(root, k=2)
    out["nearest_root_spacing_over_H"] = st(dd[:, 1] / H, 4)
    out["nearest_root_spacing_over_len"] = st(dd[:, 1] / Lg)
    fan = [float(np.degrees(np.arccos(np.clip(dall[i] @ dall[jj[i, 1]], -1, 1)))) for i in range(len(cl))]
    out["fan_angle_to_nearest_deg"] = st(fan, 1)
    return out


def main():
    tag = sys.argv[1]
    R = json.load(open(SO.CACHE_DIR + "/tmp_crown2_raw%s.json" % tag))
    occ_top = np.array(R["occ_top_y"], float)
    H = float(np.nanmax(occ_top)) - SEA_Y
    H_body = float(np.nanmax(R["body_top_y"])) - SEA_Y
    dig = R["digit"]
    hand = R["hand"]
    roots = np.array([q["root"] for q in dig + hand])
    c_lo, c_hi = float(roots[:, 2].min()), float(roots[:, 2].max())
    L3, Lcy, c, ys, as_ = rim(R, c_lo, c_hi)
    out = {"tag": tag, "vox_m": R["vox_m"], "r_digit_m": R["r_digit_m"], "r_hand_m": R["r_hand_m"], "y_lo": R["y_lo"],
           "H_ref_m_incl_fingers": round(H, 3), "H_ref_body_m": round(H_body, 3), "sea_y": SEA_Y,
           "crown_root_c_range_m": [round(c_lo, 2), round(c_hi, 2)],
           "rim_len_3d_m": round(L3, 3), "rim_len_cy_m": round(Lcy, 3), "rim_len_over_H": round(L3 / H, 3),
           "digits": summarize(R, dig, H, L3, c, ys, as_, "digit (open radius %.2f m)" % R["r_digit_m"]),
           "hands": summarize(R, hand, H, L3, c, ys, as_, "hand (open radius %.2f m)" % R["r_hand_m"])}
    nd = np.array([len(q["digits"]) for q in hand])
    out["hands"]["digits_per_hand"] = st(nd)
    out["hands"]["digits_per_hand_hist"] = {str(k): int((nd == k).sum()) for k in range(0, int(nd.max()) + 1) if (nd == k).any()}
    fr2 = [x for q in hand for x in q.get("digit_start_fr", [])]
    out["hands"]["digit_start_fraction_of_hand_length"] = st(fr2)
    out["front_proj_finger_px"] = R.get("front_proj_finger_px")
    out["front_proj_body_px"] = R.get("front_proj_body_px")
    json.dump(out, open(SO.STUDY + "/s1_crown2_numbers%s.json" % tag, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False)[:9000])


if __name__ == "__main__":
    main()
