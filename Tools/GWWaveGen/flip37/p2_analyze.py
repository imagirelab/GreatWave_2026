# -*- coding: utf-8 -*-
"""P2 の 1 本の計算の解析（py -3.10）。使い方: py -3.10 p2_analyze.py <run_dir> [--quiet]

1. 峰に沿う頂の高さ（hf.npz の一番上の水面 η(z, x) から、z ごとの最大）と、張り出し（列の水の区間が 2 以上）の広がりを時刻ごとに出す。
2. 原画カメラから見たシルエット（網目 mesh_XXXX.npz）を原画の大波の面と比べる：
   置き方は p2_common.place（頂を原画の頂の画素の光線に乗せ、進む向きの角度 ψ と一様の倍率 s を探す）。
   点数＝窓の中の IoU（主）と、原画の輪郭からシルエットの縁までの平均の距離（px、1920 表示）。どちらも記録だけ（合否に使わない）。
   いちばん原画に近い瞬間＝IoU が最大のコマ（同じ時は距離の小さい方）。
3. その瞬間の値：峰に沿う頂の高さの形（山の数＝一つの山か、左の肩・最も左の小さな区域にあたる 2 番目・3 番目の高まり）、
   峰の長さ（頂が 0.75 Hc 以上の z の長さ、15 m 以上の長さ）、横のうねり（z の両端 ±100〜120 m の頂の高さ）、
   z の切り口（sec/zXXXX）ごとの断面の値（P1 の p1_analyze.shape_metrics と同じ定義）、出来事の時刻（中央の切り口）。
出力：<run_dir>/analysis.json、<run_dir>/painting_fit.json
"""
import sys, os, json, glob, math
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_common as C  # noqa: E402
import p1_analyze as A1  # noqa: E402

SC = 0.5   # シルエットの解像度（960×540）
PSIS = [0, 10, 20, 30, 40, 50, 60]
SCALES = [0.9, 1.0, 1.1]


def load_hf(rd):
    d = np.load(os.path.join(rd, "hf.npz"))
    g = json.loads(str(d["grid"]))
    eta = d["eta"].astype(np.float32)
    nf, nz, nx = eta.shape
    xs = g["x0"] + g["dx"] * np.arange(nx); zs = g["z0"] + g["dz"] * np.arange(nz)
    seg = d["seg"]
    # R01 は升目の置き直しの誤りで、x と z の 1 つおきの列が空（NaN）。空の列と行を落とす（4 m おきの標本になる）
    k = min(len(eta) - 1, 10)
    okz = ~np.isnan(eta[k]).all(axis=1); okx = ~np.isnan(eta[k]).all(axis=0)
    eta = eta[:, okz][:, :, okx]; seg = seg[:, okz][:, :, okx]; xs = xs[okx]; zs = zs[okz]
    mirror, Lz = C.run_mirror(rd)
    if mirror:
        # z=-Lz/2 の壁（対称の面）で鏡に映して全体の波にする（版 3 の mirror_z=1 の計算）
        zm = -Lz - zs[::-1]; keep = zm < zs.min() - 1e-6
        zs = np.concatenate([zm[keep], zs])
        eta = np.concatenate([eta[:, ::-1][:, keep], eta], axis=1); seg = np.concatenate([seg[:, ::-1][:, keep], seg], axis=1)
    return {"eta": eta, "seg": seg, "t": d["t"], "frames": d["frames"], "xs": xs, "zs": zs, "lvl": d["lvl"], "mirror": mirror}


def crest_profile(hf, k, xwin=(380, 706)):
    """コマ k の峰に沿う頂の高さ（z ごと）と、その x。"""
    e = hf["eta"][k]
    m = (hf["xs"] >= xwin[0]) & (hf["xs"] <= xwin[1])
    ee = np.where(np.isfinite(e[:, m]), e[:, m], -99)
    j = np.argmax(ee, axis=1)
    return ee[np.arange(len(j)), j], hf["xs"][m][j]


def peaks_1d(y, z, prom=1.0):
    """1 次元の山（両側へ prom m 以上下がる高まり）。戻り：[(z, 高さ, 目立ち)]（高い順）。
    19:55 直し：同じ高さの二つ並び（間のへこみが prom より浅い）を一つの山に数える（scipy の find_peaks の後で、
    となりの山との間の最低が両方の低い方より prom 以上下がらない組を、高い方へまとめる）。"""
    from scipy.signal import find_peaks
    y = np.asarray(y, float)
    pk, pr = find_peaks(y, prominence=prom)
    idx = list(pk)
    merged = True
    while merged and len(idx) > 1:
        merged = False
        for a in range(len(idx) - 1):
            i, j = idx[a], idx[a + 1]
            if y[i:j + 1].min() > min(y[i], y[j]) - prom:
                idx.pop(a + 1 if y[i] >= y[j] else a); merged = True; break
    out = []
    for i in idx:
        # 目立ち：左右で同じか高い所（自分以外の山）に出会うまでの最低からの高さ（端までなら端まで）
        hi = [j for j in idx if j != i and y[j] >= y[i]]
        lj = max([j for j in hi if j < i], default=None); rj = min([j for j in hi if j > i], default=None)
        lmin = y[lj:i + 1].min() if lj is not None else y[:i + 1].min()
        rmin = y[i:rj + 1].min() if rj is not None else y[i:].min()
        out.append((float(z[i]), float(y[i]), float(y[i] - max(lmin, rmin))))
    return sorted(out, key=lambda q: -q[1])


def fit_painting(rd, hf, quiet=False, t_range=(-1e9, 1e9), z_anchor=None):
    cam = C.painting_cam(SC)
    pm, outer, inner = C.painting_mask(SC)
    win = C.window_mask(SC)
    P_area = (pm & win).sum()
    files = sorted(glob.glob(os.path.join(rd, "mesh", "mesh_*.npz")))
    res = []
    for f in files:
        fr = int(os.path.basename(f)[5:9])
        k = int(np.argmin(np.abs(hf["frames"] - fr)))
        cp, cx = crest_profile(hf, k)
        if cp.max() < 12.0 or not (t_range[0] <= float(hf["t"][k]) <= t_range[1]):
            continue
        iz = int(np.argmax(cp))
        if z_anchor is not None:
            # 21:15 から：巻いた所（最初に垂直を過ぎた切り口の z）の頂を原画の頂の画素へ置く（巻いた中ほどは肩より低くなるため、最高点ではなく）
            iz = int(np.argmin(np.abs(hf["zs"] - z_anchor)))
        anchor = (float(cx[iz]), float(cp[iz]), float(hf["zs"][iz]))
        Pm, tri, t = C.load_mesh_full(f, *C.run_mirror(rd))
        # 頂の近く（x: 頂 −160〜+90 m）だけ
        keep = (Pm[:, 0] > anchor[0] - 160) & (Pm[:, 0] < anchor[0] + 90)
        tk = tri[keep[tri].all(1)]
        best = None
        ek = hf["eta"][k]
        for psi in PSIS:
            for s in SCALES:
                U, O = C.place(Pm, anchor, psi, s, cam)
                # カメラが水の中（カメラの真下の水面が 2 m より高い）になる置き方は使わない（原画のカメラは海面から 3 m）
                Tv, Ev = C.TE(psi)
                Qc = (cam.pos - O) / s
                xc_, zc_ = Qc @ Tv + anchor[0], Qc @ Ev + anchor[2]
                ix_ = int(np.argmin(np.abs(hf["xs"] - xc_))); iz_ = int(np.argmin(np.abs(hf["zs"] - zc_)))
                inside = (hf["xs"][0] <= xc_ <= hf["xs"][-1]) and (hf["zs"][0] <= zc_ <= hf["zs"][-1])
                eta_cam = float(ek[iz_, ix_]) if inside and np.isfinite(ek[iz_, ix_]) else None
                if eta_cam is not None and eta_cam * s > cam.pos[1] - 1.0:
                    continue
                m = C.raster_mask(cam, U, tk) & win
                inter = (m & pm).sum(); uni = (m | (pm & win)).sum()
                iou = inter / max(uni, 1)
                cand = {"frame": fr, "t": t, "psi_deg": psi, "scale": s, "iou": float(iou), "anchor": anchor, "O": O.tolist(),
                        "camera_in_sim": [float(xc_), float(zc_)], "eta_under_camera": eta_cam,
                        "fluid_area_px": int(m.sum()), "painting_area_px": int(P_area),
                        "recall_painting_covered": float(inter / max(P_area, 1)),
                        "outside_covered": float((m & ~pm).sum() / max((win & ~pm).sum(), 1))}
                if best is None or iou > best["iou"]:
                    best = cand; best_m = m
        if best is None:
            continue
        best["outline_dist"] = C.outline_distance(best_m, outer, inner, SC)
        res.append(best)
        if not quiet:
            print("fit f=%d t=%.2f psi=%d s=%.1f IoU=%.3f dist=%.1f" % (fr, t, best["psi_deg"], best["scale"], best["iou"],
                                                                      best["outline_dist"]["mean_px"] if best["outline_dist"] else -1))
    return res


def section_runs(rd):
    res = {}
    for sd in sorted(glob.glob(os.path.join(rd, "sec", "z*"))):
        try:
            res[os.path.basename(sd)] = A1.analyze(sd, quiet=True)
        except Exception as e:
            res[os.path.basename(sd)] = {"error": str(e)[:200]}
    return res


def sections(SR, t_best):
    out = {}
    for name, r in SR.items():
        if "error" in r:
            out[name] = r
            continue
        tl = r["timeline"]
        q = min(tl, key=lambda q: abs(q["t"] - t_best)) if tl else None
        keys = ("crest", "lip_tip", "inner_wall", "reach_over_Hc", "drop_over_Hc", "overhang_over_Hc", "tube_aspect_w_over_h",
                "front_face_chord_angle_deg", "tube_inscribed_r_m", "covered_air_area_m2", "back_dx_to_075Hc_m", "trough_ahead_m", "overturned")
        out[name] = {"events": r["events"], "plunging": r["plunging"],
                                     "at_best": ({k: q.get(k) for k in keys} | {"t": q["t"]}) if q else None,
                                     "best_vs_painting_A": r["best_frame_vs_painting"].get("A_side")}
    return out


def analyze(rd, quiet=False):
    run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    hf = load_hf(rd)
    zs = hf["zs"]
    # 時刻ごとの頂の高さの最大と、張り出しの列の数
    tl = []
    for k in range(len(hf["t"])):
        cp, cx = crest_profile(hf, k)
        ov = (hf["seg"][k] >= 2)
        tl.append({"t": float(hf["t"][k]), "crest_max": float(cp.max()), "z_at_max": float(zs[int(np.argmax(cp))]),
                   "x_at_max": float(cx[int(np.argmax(cp))]), "n_over_cols": int(ov.sum()),
                   "over_z_extent_m": float((ov.any(axis=1)).sum() * float(np.median(np.diff(zs))))})
    # 足元の波の高さ（P1 と同じ：斜面の足元の手前 x=400 m の水面計の、頂が通る時の山から谷）。z = 0・±100 m
    toe = {}
    ig = int(np.argmin(np.abs(hf["xs"] - 400.0)))
    for zz in ((0.0, -100.0, 100.0, -120.0) if hf.get("mirror") else (0.0, -100.0, 100.0)):
        iz = int(np.argmin(np.abs(zs - zz)))
        eg = hf["eta"][:, iz, ig].astype(float); tg = hf["t"]
        if np.isfinite(eg).sum() > 10:
            kmax = int(np.nanargmax(eg))
            toe["z%+d" % zz] = {"crest_m": float(eg[kmax]), "t_crest": float(tg[kmax]),
                                "H_toe_m": float(eg[kmax] - min(np.nanmin(eg[:kmax + 1]), np.nanmin(eg[kmax:])))}
    # 原画に近い瞬間を探すコマの範囲：切り口のどれかで前の面が垂直を過ぎた時刻の 0.5 秒前〜2.5 秒後。
    # 垂直を過ぎなかった計算は、砕けの始まり（B>0.85）の最も早い時刻から終わりまで。それもなければ、頂が最高の 0.95 倍以上のコマ。
    SR = section_runs(rd)
    def tmin(key):
        v = [r["events"][key]["t"] for r in SR.values() if "events" in r and r["events"].get(key)]
        return min(v) if v else None
    t_ov, t_on = tmin("face_past_vertical"), tmin("breaking_onset_B085")
    cmax = np.array([q["crest_max"] for q in tl]); tt_ = np.array([q["t"] for q in tl])
    # 20:40 直し：「いちばん原画に近い瞬間」を、巻いた所の断面の形で決める。
    #   最初に前の面が垂直を過ぎた切り口（同じ時刻なら頂の高い方）の、P1 と同じ点数（原画の読み A に対する唇の届き・落ち・かぶり、
    #   前の面の弦、空洞の幅/高さ）が最小のコマ。原画カメラのシルエットの IoU は、流体が窓をほぼ埋めてどの瞬間も 0.58〜0.61 で
    #   差がつかないため、瞬間の選び方には使わず、その瞬間の値として記録する（IoU が最大のコマも best_iou として残す）。
    sec_hump, t_shape = None, None
    ov_secs = [(r["events"]["face_past_vertical"]["t"], -(r["events"].get("crest_max_before_overturn_m") or 0), n)
               for n, r in SR.items() if "events" in r and r["events"].get("face_past_vertical")]
    if ov_secs:
        sec_hump = min(ov_secs)[2]
        bA = (SR[sec_hump].get("best_frame_vs_painting") or {}).get("A_side")
        t_shape = bA["t"] if bA else None
    if t_ov is not None:
        t_range = (t_ov - 0.5, max(t_ov + 2.5, (t_shape or 0) + 0.2)); rule = "overturn-0.5..+2.5"
    elif t_on is not None:
        t_range = (t_on, 1e9); rule = "onset..end"
    else:
        t_range = (float(tt_[cmax >= 0.95 * cmax.max()].min()), 1e9); rule = "crest>=0.95max"
    z_anchor = float(int(sec_hump[1:])) if sec_hump else None
    fits = fit_painting(rd, hf, quiet, t_range, z_anchor)
    best_iou = max(fits, key=lambda q: (q["iou"], -(q["outline_dist"] or {}).get("mean_px", 1e9))) if fits else None
    if t_shape is not None and fits:
        best = dict(min(fits, key=lambda q: abs(q["t"] - t_shape)))
        best["rule_ja"] = "巻いた所の断面（%s）が原画の読み A にいちばん近いコマ（t=%.2f s）に最も近い網目のコマ" % (sec_hump, t_shape)
    else:
        best = dict(best_iou) if best_iou else None
        if best:
            best["rule_ja"] = "前の面が垂直を過ぎた切り口がないので、原画カメラのシルエットの IoU が最大のコマ"
    out = {"run_id": run["run_id"], "stopped": run.get("stopped"), "parms": {k: run["parms"][k] for k in (
        "H", "T", "dp", "hr", "slope_n", "lens_A", "lens_zl", "lens_dh", "obl_deg", "cross_deg", "lg1_d", "lg1_x", "lg1_z", "lg2_d", "lg2_x", "lg2_z", "band_vox", "lens_z0", "cross_z0", "mirror_z")
        if k in run["parms"]},
           "f_end_done": run.get("f_end_done"), "parts": run.get("parts"), "concurrent_with": run.get("concurrent_with"),
           "wall_total_s": run.get("wall_total_s"), "wall_per_frame_median_s": run.get("wall_per_frame_median_s"),
           "particles_max": run.get("particles_max"), "rss_peak_gb": run.get("rss_peak_gb"),
           "toe_gauge_x400": toe, "t_first_overturn_any_section": t_ov, "t_first_onset_any_section": t_on,
           "fit_t_range": list(t_range), "fit_rule": rule, "timeline": tl, "fits": fits, "best": best, "best_iou": best_iou,
           "section_hump": sec_hump, "t_shape": t_shape, "z_anchor": z_anchor,
           "anchor_rule_ja": ("巻いた所（%s）の頂を原画の頂の画素へ置く" % sec_hump) if sec_hump else "その瞬間の最も高い頂を原画の頂の画素へ置く"}
    if best:
        best["M_sim_to_unity"] = C.placement_matrix(best["anchor"], best["psi_deg"], best["scale"], best["O"]).round(5).tolist()
        k = int(np.argmin(np.abs(hf["t"] - best["t"])))
        cp, cx = crest_profile(hf, k)
        Hc = float(cp.max())
        pk = peaks_1d(cp, zs, prom=0.8)
        ov = hf["seg"][k] >= 2
        ovz = ov.any(axis=1)
        dz = float(np.median(np.diff(zs)))
        zc_ = float(zs[int(np.argmax(cp))])
        side = {"z<-100": float(np.nanmax(cp[zs < -100])) if (zs < -100).any() else None, "z>100": float(np.nanmax(cp[zs > 100])) if (zs > 100).any() else None,
                "near_dz<=-100": float(np.nanmax(cp[zs <= zc_ - 100])) if (zs <= zc_ - 100).any() else None,
                "far_dz>=100": float(np.nanmax(cp[zs >= zc_ + 100])) if (zs >= zc_ + 100).any() else None,
                "near_dz-46": float(np.interp(zc_ - 46, zs, cp)), "far_dz+46": float(np.interp(zc_ + 46, zs, cp))}
        out["at_best"] = {
            "t": best["t"], "Hc_m": Hc, "z_crest": float(zs[int(np.argmax(cp))]),
            "crest_profile": {"z": zs.round(2).tolist(), "y": cp.round(2).tolist(), "x": cx.round(1).tolist()},
            "peaks": pk, "n_peaks_prom08": len(pk), "one_hill": len(pk) == 1, "mirror": bool(hf.get("mirror")),
            "crest_len_075Hc_m": float((cp >= 0.75 * Hc).sum() * dz), "crest_len_15m_m": float((cp >= 15.0).sum() * dz),
            "overturned_z_extent_m": float(ovz.sum() * dz),
            "overturned_z_range": [float(zs[ovz].min()), float(zs[ovz].max())] if ovz.any() else None,
            "side_swell_m": side,
        }
        out["sections"] = sections(SR, best["t"])
    # 砕けの始まり（どれかの切り口で B>0.85）と、最初に前の面が垂直を過ぎた時の、峰に沿う頂の高さの形（巻く前の「一つの山」の確かめ）
    for key, tq in (("at_onset", t_on), ("at_first_overturn", t_ov)):
        if tq is None:
            continue
        k2 = int(np.argmin(np.abs(hf["t"] - tq)))
        cp2, cx2 = crest_profile(hf, k2)
        pk2 = peaks_1d(cp2, zs, prom=0.8)
        zc2 = float(zs[int(np.argmax(cp2))]); H2 = float(cp2.max())
        out[key] = {"t": float(hf["t"][k2]), "Hc_m": H2, "z_crest": zc2, "peaks": pk2, "n_peaks_prom08": len(pk2), "one_hill": len(pk2) == 1,
                    "near_dz-46": float(np.interp(zc2 - 46, zs, cp2)), "far_dz+46": float(np.interp(zc2 + 46, zs, cp2)),
                    "half_width_m": float((cp2 >= 0.5 * (H2 + np.nanmin(cp2))).sum() * float(np.median(np.diff(zs)))),
                    "crest_len_075Hc_m": float((cp2 >= 0.75 * H2).sum() * float(np.median(np.diff(zs)))),
                    "x_crest": float(cx2[int(np.argmax(cp2))]), "x_lag_at_dz100": float(cx2[int(np.argmax(cp2))] - np.interp(zc2 - 100, zs, cx2)) if zc2 - 100 >= zs.min() else None}
    # 原画カメラで一番合った時の点数の推移も残す
    json.dump(out, open(os.path.join(rd, "analysis.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    if not quiet:
        b = out.get("best"); a = out.get("at_best")
        print(json.dumps({"run": out["run_id"], "best": b, "at_best": {k: v for k, v in (a or {}).items() if k != "crest_profile"}},
                         ensure_ascii=False, indent=1, default=float))
    return out


if __name__ == "__main__":
    analyze(sys.argv[1], quiet="--quiet" in sys.argv)
