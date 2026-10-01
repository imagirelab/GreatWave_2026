# -*- coding: utf-8 -*-
"""仕上げ28修正01 SHOULDER：原画視点が変わらないことの確かめ（py -3.10）。
  1. 原画視点の厳密な z バッファー（rec_common.zbuf、ss=1 と 2）：土台 P28R2rec と候補で、波が覆う画素・見えている三角形の番号・奥行きを比べる。
  2. 設計38 の主役波の外殻線（反転シェル、rec_common.shell_lines、印は ds38_hero_linemask を読むだけ）：土台に対して新しく出た線の画素。
  3. 断面の自己交差（行ごと）、三角形の面積の最小、行の頂の列（top_argmax_col）の変化、海の帯の単調さ。
usage: py -3.10 r01_shoulder_check.py <out.json> <cand_rows.npz> [base_rows.npz]
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_shoulder_common as S  # noqa: E402
import rec_common as RC  # noqa: E402
import r2_build as B2  # noqa: E402

KC = S.KC


def main():
    out, cand = sys.argv[1], sys.argv[2]
    base = sys.argv[3] if len(sys.argv) > 3 else S.BASE_ROWS
    c0, A0, Y0 = S.load_rows(base)
    c1, A1, Y1 = S.load_rows(cand)
    assert np.array_equal(c0, c1)
    res = {"base": base, "cand": cand}
    mv = np.hypot(A1 - A0, Y1 - Y0)
    res["moved_vertices_gt_1mm"] = int((mv > 1e-3).sum())
    res["max_move_m"] = round(float(mv.max()), 3)
    rr, jj = np.nonzero(mv > 1e-3)
    if len(rr):
        res["moved_rows_c_range"] = [round(float(c0[rr.min()]), 2), round(float(c0[rr.max()]), 2)]
        res["moved_cols_range"] = [int(jj.min()), int(jj.max())]
    for ss in (1, 2):
        z0, i0 = RC.zbuf(c0, A0, Y0, ss)
        z1, i1 = RC.zbuf(c1, A1, Y1, ss)
        cov0 = np.isfinite(z0); cov1 = np.isfinite(z1)
        same_id = (i0 == i1)
        dz = np.abs(np.where(cov0 & cov1, z1 - z0, 0.0))
        res["painting_zbuffer_ss%d" % ss] = {
            "coverage_px_base": int(cov0.sum()), "coverage_px_cand": int(cov1.sum()),
            "coverage_changed_px": int((cov0 != cov1).sum()),
            "visible_triangle_changed_px": int((~same_id & (cov0 | cov1)).sum()),
            "depth_change_max_m": round(float(dz.max()), 6)}
    mask = RC.load_linemask()
    l0, _, _ = RC.shell_lines(c0, A0, Y0, mask, ss=1)
    l1, _, _ = RC.shell_lines(c1, A1, Y1, mask, ss=1)
    import cv2
    l0d = cv2.dilate(l0.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    res["shell_lines_ss1"] = {"line_px_base": int(l0.sum()), "line_px_cand": int(l1.sum()),
                              "new_line_px_vs_base": int((l1 & ~l0d).sum()), "identical": bool(np.array_equal(l0, l1))}
    sx0 = np.array([B2.seg_selfx(A0[i], Y0[i], 0, None) for i in range(len(c0))])
    sx1 = np.array([B2.seg_selfx(A1[i], Y1[i], 0, None) for i in range(len(c0))])
    res["section_selfx_rows_base_cand"] = [int((sx0 > 0).sum()), int((sx1 > 0).sum())]
    res["section_selfx_rows_new"] = [round(float(c0[i]), 2) for i in np.nonzero(sx1 > sx0)[0]]
    X = KC.world(c1, A1, Y1).reshape(-1, 3)
    T = KC.triangles(A1.shape[1], A1.shape[0])
    ar = 0.5 * np.linalg.norm(np.cross(X[T[:, 1]] - X[T[:, 0]], X[T[:, 2]] - X[T[:, 0]]), axis=1)
    res["min_triangle_area_m2"] = float(ar.min())
    res["sea_band_monotone"] = bool(np.all(np.diff(A1[:, :19], axis=1) > 0))
    res["sea_band_height_max_m"] = float(np.abs(Y1[:, :18]).max())
    t0 = np.array([int(np.argmax(Y0[r, :200])) for r in range(len(c0))])
    t1 = np.array([int(np.argmax(Y1[r, :200])) for r in range(len(c0))])
    res["top_col_changed_rows"] = {"%.2f" % c0[r]: [int(t0[r]), int(t1[r])] for r in np.nonzero(t0 != t1)[0]}
    res["H_change_max_m"] = round(float(np.abs(Y1.max(1) - Y0.max(1)).max()), 4)
    res["boundary_ring_unchanged"] = bool(np.array_equal(A1[0], A0[0]) and np.array_equal(A1[-1], A0[-1]) and np.array_equal(A1[:, 0], A0[:, 0])
                                          and np.array_equal(A1[:, -1], A0[:, -1]) and np.array_equal(Y1[0], Y0[0]) and np.array_equal(Y1[-1], Y0[-1])
                                          and np.array_equal(Y1[:, 0], Y0[:, 0]) and np.array_equal(Y1[:, -1], Y0[:, -1]))
    S.jdump(res, out)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
