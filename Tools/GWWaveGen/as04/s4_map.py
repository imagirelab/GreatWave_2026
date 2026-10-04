# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S の 1（Q32）：利用者の区域 ①②③・④・出っ張りを、原画のカメラの射線（z バッファ）で t* の主役波 AS02C の
シートの行・列・xyz へ結ぶ。行ごとの原画視点での見え方（輪郭を作る行・見えない行・画の外の行）と、④（左端の小さな青い波の上の縁）を
今どの物が作っているか、別の小さな青い波を置くなら射線の上のどの深さか、を測る。

入力（読み取りのみ）：見本03 の調べ S2 の z バッファの表 s2_map.npz（原画の画素 → 主役波の行・列・深さ・xyz。AS02C と近い海 PL30）、
原画の色の分類 s2_classes.npz、原画の輪郭の真値（PaintingTruth の main_wave_outline_envelope.json）、AS02C の行の npz。
原画の色は面へ写さない（Q28）。参照モデルの OBJ・写真は読まない。
使い方：py -3.10 -B Tools/GWWaveGen/as04/s4_map.py
出力：Unity/Build/Polish/sample04/map/s4_map.json、tmp/s4_vertex_regions.npz（区域ごとの頂点の印）
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_common as S  # noqa: E402

CLASSES = S.REPO + "/Unity/Build/Polish/sample03/study/tmp/s2_classes.npz"


def c_of_r(cm, r):
    return np.interp(r, np.arange(len(cm)), cm)


def stats(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if not len(v):
        return None
    return {"min": S.rnd(v.min()), "p05": S.rnd(np.percentile(v, 5)), "p50": S.rnd(np.percentile(v, 50)),
            "p95": S.rnd(np.percentile(v, 95)), "max": S.rnd(v.max())}


def main():
    t0 = time.time()
    z = np.load(S.S2MAP)
    surf = z["surf"]; rr = z["r"]; cc = z["c"]; dep = z["depth"]
    P3 = z["P"]
    QH, QW = surf.shape
    cm = S.rows_c()
    X0 = S.load_hero()
    SX = S.hero_sec(X0)
    R, C = X0.shape[:2]
    regs = S.regions_ref()
    out = {"schema": "GreatWave.ArtSample04.study_map/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "inputs": {"s2_map": {"path": os.path.relpath(S.S2MAP, S.REPO).replace("\\", "/"), "sha256": S.sha(S.S2MAP)},
                      "rows": {"path": os.path.relpath(S.ROWS, S.REPO).replace("\\", "/"), "sha256": S.sha(S.ROWS)},
                      "outline": {"path": os.path.relpath(S.OUTLINE_ENV, S.REPO).replace("\\", "/"), "sha256": S.sha(S.OUTLINE_ENV)}},
           "frame_ja": "a = 進行方向（+ が前・唇の側）、y = 高さ、c = 波峰線（+ が原画視点の右・奥）。行 r（0..239）は c 一定の断面、列 j（0..399）は背の根元 18 → 頂 90 → 唇の先 200 → 角 314 → 前の面の下 379。H0 = 20.75 m。",
           "regions": {}}
    vmask = {}
    for k, poly in regs.items():
        m = np.zeros((QH, QW), np.uint8)
        cv2.fillPoly(m, [np.round(poly).astype(np.int32)], 1)
        m = m.astype(bool)
        s = surf[m]
        hm = m & (surf == 1)
        r_ = rr[hm]; j_ = cc[hm]; P = P3[hm].astype(np.float64)
        Q = S.K.sec(P) if len(P) else np.zeros((0, 3))
        e = {"name_ja": S.REGION_JA[k], "polygon_ref_px": S.rnd(poly, 1), "polygon_display_px": S.rnd(S.ref_to_disp(poly), 1),
             "px_total": int(m.sum()), "px_hero": int((s == 1).sum()), "px_near_sea": int((s == 2).sum()), "px_empty": int((s == 0).sum()),
             "row": stats(r_), "col": stats(j_), "c_m": stats(c_of_r(cm, r_)) if len(r_) else None,
             "a_m": stats(Q[:, 0]) if len(Q) else None, "y_m": stats(Q[:, 1]) if len(Q) else None,
             "y_over_H0": stats(Q[:, 1] / S.H0) if len(Q) else None,
             "depth_m": stats(dep[hm]), "xyz_min": S.rnd(P.min(0)) if len(P) else None, "xyz_max": S.rnd(P.max(0)) if len(P) else None}
        # 列の帯ごとの画素の割合（背 18〜90・唇の外 90〜200・唇の下 200〜314・前の面 314〜394）
        if len(j_):
            bands = [(18, 90, "背"), (90, 200, "頂〜唇の先（外）"), (200, 314, "唇の下〜角（内の面）"), (314, 394, "前の面")]
            e["col_band_share"] = {nm: S.rnd(((j_ >= a) & (j_ < b)).mean()) for a, b, nm in bands}
        out["regions"][k] = e
        vm = np.zeros((R, C), bool)
        if len(r_):
            vm[np.clip(np.round(r_).astype(int), 0, R - 1), np.clip(np.round(j_).astype(int), 0, C - 1)] = True
        vmask[k] = vm
        print(k, e["px_total"], e["px_hero"], e["row"], e["col"], flush=True)

    # ---------------------------------------------------------------- 行ごとの原画視点の見え方
    hm = surf == 1
    rv = np.round(rr[hm]).astype(int)
    xs = np.nonzero(hm)[1]
    vis_px = np.bincount(rv, minlength=R)
    xmin = np.full(R, np.nan); xmax = np.full(R, np.nan)
    for i in range(R):
        s = rv == i
        if s.any():
            xmin[i] = xs[s].min(); xmax[i] = xs[s].max()
    # 輪郭の真値の点ごとに、波の側の 3 画素以内で最も近い主役波の画素の行・列
    segs = S.outline_segments()
    sil_rows = {}
    seg_rc = {}
    ys_h, xs_h = np.nonzero(hm)
    from scipy.spatial import cKDTree
    tree = cKDTree(np.c_[xs_h, ys_h])
    for sid, pts in segs.items():
        d, ii = tree.query(pts, k=1)
        ok = d <= 6.0
        r_s = rr[ys_h[ii], xs_h[ii]]; j_s = cc[ys_h[ii], xs_h[ii]]
        seg_rc[sid] = {"n_points": int(len(pts)), "n_hero_within_6px": int(ok.sum()),
                       "row": stats(r_s[ok]), "col": stats(j_s[ok]), "c_m": stats(c_of_r(cm, r_s[ok])),
                       "x_ref": [S.rnd(pts[:, 0].min(), 1), S.rnd(pts[:, 0].max(), 1)]}
        for r_i in np.unique(np.round(r_s[ok]).astype(int)):
            sil_rows.setdefault(int(r_i), set()).add(sid)
    rows = []
    for i in range(R):
        st = "画の外" if vis_px[i] == 0 else ("輪郭を作る" if i in sil_rows else "見える（輪郭なし）")
        rows.append({"row": i, "c_m": S.rnd(cm[i]), "crest_y_m": S.rnd(SX[i, S.J_B:S.J_TIP, 1].max()),
                     "painting_px": int(vis_px[i]), "x_ref_range": [S.rnd(xmin[i], 0), S.rnd(xmax[i], 0)],
                     "outline_segments": sorted(sil_rows.get(i, [])), "status_ja": st})
    out["rows_painting_view"] = rows
    out["outline_segments_rows"] = seg_rc
    pinned = [r["row"] for r in rows if r["outline_segments"]]
    out["rows_summary"] = {
        "rows_outside_or_hidden": [r["row"] for r in rows if r["painting_px"] == 0],
        "rows_outline": pinned,
        "c_outline_range": [S.rnd(cm[min(pinned)]), S.rnd(cm[max(pinned)])] if pinned else None,
        "note_ja": "原画視点で見える画素が 0 の行は、原画の関門（78・130・131・132・72）に入らない（自由に動かせる）。輪郭を作る行は、輪郭の真値の点から 6 画素以内に主役波の画素がある行。"}

    # ---------------------------------------------------------------- ④：左端の小さな青い波の上の縁
    cls = np.load(CLASSES)["cls"]
    s78 = segs["78"]
    xs4 = np.arange(0, 481, 4)
    r4 = []
    for x in xs4:
        k = np.argmin(np.abs(s78[:, 0] - x))
        y_out = float(s78[k, 1]) if abs(s78[k, 0] - x) < 3 else np.nan
        col = surf[:, x]
        kk = np.nonzero(col > 0)[0]
        y_top = int(kk[0]) if len(kk) else -1
        obj = int(col[y_top]) if len(kk) else 0
        # 青い楔の下の縁：輪郭から下へ、生成りの白（cls 1）が 25 画素のうち 92% 以上になる所の始まり
        # （楔の中の白い点は 20 画素より小さい。楔の上の水色の帯は cls 2 なので白に数えない）。後で x の向きに中央値でならす
        y_low = np.nan
        if np.isfinite(y_out):
            y0 = int(round(y_out)) + 4
            wcol = (cls[y0:y0 + 400, x] == 1).astype(float)
            run = np.convolve(wcol, np.ones(25) / 25, mode="valid")
            q = np.nonzero(run > 0.92)[0]
            if len(q):
                y_low = float(y0 + q[0])
        e = {"x_ref": int(x), "outline_y_ref": S.rnd(y_out, 1), "wedge_lower_edge_y_ref": S.rnd(y_low, 1),
             "wedge_thickness_px": S.rnd(y_low - y_out, 1) if np.isfinite(y_low) and np.isfinite(y_out) else None,
             "current_top_y_ref": y_top, "current_top_object": {0: "なし", 1: "主役波", 2: "近い海"}[obj]}
        if obj == 1:
            yy = y_top + 1
            r_i, j_i = float(rr[yy, x]), float(cc[yy, x])
            P = P3[yy, x].astype(np.float64)
            q3 = S.K.sec(P[None])[0]
            e.update({"hero_row": S.rnd(r_i, 2), "hero_col": S.rnd(j_i, 2), "hero_c_m": S.rnd(c_of_r(cm, r_i)), "hero_a_m": S.rnd(q3[0]),
                      "hero_y_m": S.rnd(q3[1]), "hero_xyz": S.rnd(P), "hero_depth_m": S.rnd(dep[yy, x])})
            # 下の縁まで白を下げるときの高さの差（その深さで）：画素の大きさ × 画素の差
            if np.isfinite(y_low):
                pxm = dep[yy, x] * 2 * np.tan(np.radians(13.0)) / 1080 * S.A_DISP
                e["lower_by_m_at_hero_depth"] = S.rnd((y_low - y_top) * pxm)
        r4.append(e)
    # 楔の下の縁を x の向きに中央値でならす（爪の先の細い白で跳ぶ列を除く）。下げる高さもならした値で出し直す
    from scipy.ndimage import median_filter
    yl = np.array([np.nan if e["wedge_lower_edge_y_ref"] is None else e["wedge_lower_edge_y_ref"] for e in r4])
    ok = np.isfinite(yl)
    yls = yl.copy()
    yls[ok] = median_filter(yl[ok], size=9, mode="nearest")
    for e, v in zip(r4, yls):
        e["wedge_lower_edge_y_ref_smooth"] = S.rnd(v, 1)
        if np.isfinite(v) and e.get("outline_y_ref") is not None:
            e["wedge_thickness_px"] = S.rnd(v - e["outline_y_ref"], 1)
        if "hero_depth_m" in e and np.isfinite(v):
            pxm = e["hero_depth_m"] * 2 * np.tan(np.radians(13.0)) / 1080 * S.A_DISP
            e["lower_by_m_at_hero_depth"] = S.rnd((v - e["current_top_y_ref"]) * pxm)
    # 別の小さな青い波を置く深さ：輪郭の点の射線の上で、頂の高さ h を決めると深さが決まる
    cam = CC_painting()
    opts = []
    for x in (0, 60, 120, 180, 240, 300, 360):
        k = np.argmin(np.abs(s78[:, 0] - x))
        xr, yr = s78[k]
        xd, yd = S.ref_to_disp(np.array([xr, yr]))
        d = cam.ray(np.array([xd]), np.array([yd]))[0]
        row = {"x_ref": S.rnd(xr, 1), "y_ref": S.rnd(yr, 1), "ray_dir": S.rnd(d, 4), "by_crest_height": []}
        for h in (6.0, 8.0, 10.0, 12.0, 14.0):
            s_ = (h - cam.pos[1]) / d[1]
            P = cam.pos + s_ * d
            q3 = S.K.sec(P[None])[0]
            row["by_crest_height"].append({"h_m": h, "dist_m": S.rnd(s_), "xyz": S.rnd(P), "a_m": S.rnd(q3[0]), "c_m": S.rnd(q3[2])})
        opts.append(row)
    out["region4"] = {"columns": r4, "separate_wave_ray_options": opts,
                      "note_ja": "outline_y_ref は原画の輪郭の真値（78）、wedge_lower_edge_y_ref は原画の左端の青い楔の下の縁（その下は白）。current_top は今の主役波（と近い海）の一番上の画素。lower_by_m_at_hero_depth は、主役波の左の白を楔の下の縁まで下げるときの、今の深さでの高さの差（m）。separate_wave_ray_options は、輪郭の点の射線の上で、別の波の頂の高さ h を決めたときの位置（深さ dist_m、a・c）。"}
    np.savez_compressed(S.TMP + "/s4_vertex_regions.npz", **vmask)
    S.jdump(S.OUT + "/s4_map.json", out)
    print("done", round(time.time() - t0, 1), "s")


def CC_painting():
    return S.CC.painting_cam()


if __name__ == "__main__":
    os.makedirs(S.TMP, exist_ok=True)
    main()
