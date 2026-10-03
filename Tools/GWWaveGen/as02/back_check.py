# -*- coding: utf-8 -*-
"""美術の見本02 BACK：候補が原画視点を変えていないことの確かめ。py -3.10 back_check.py <out.json> <cand_rows.npz> [base_rows.npz]
  1. 原画視点の厳密な z バッファー（rec_common.zbuf、ss 1・2）：覆う画素・見えている三角形・奥行き。
  2. 原画視点の反エイリアスの覆い（評価器の関門 preview_metrics と同じ rasterize、ss 1）：値が 1e-4 を超えて変わる画素の数。
  3. 設計38 の主役波の外殻線（rec_common.shell_lines）：新しく出た線の画素。
  4. 断面の自己交差・三角形の面積の最小・海の帯の単調さ・頂の高さ H(c) の変化・境の輪。
参照モデルは読まない。
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import back_common as BC  # noqa: E402
sys.path.insert(0, os.path.join(BC.REPO, "Tools", "GWWaveGen", "kstar_p28"))
import rec_common as RC  # noqa: E402
import r2_build as B2  # noqa: E402
import candA2_common as C2  # noqa: E402

KC = BC.KC


def main():
    out, cand = sys.argv[1], sys.argv[2]
    base = sys.argv[3] if len(sys.argv) > 3 else BC.BASE_ROWS
    c0, A0, Y0 = BC.load_rows(base)
    c1, A1, Y1 = BC.load_rows(cand)
    assert np.array_equal(c0, c1)
    res = {"base": base, "cand": cand, "base_sha256": BC.sha256(base), "cand_sha256": BC.sha256(cand)}
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
        dz = np.abs(np.where(cov0 & cov1, z1 - z0, 0.0))
        res["painting_zbuffer_ss%d" % ss] = {
            "coverage_px_base": int(cov0.sum()), "coverage_px_cand": int(cov1.sum()),
            "coverage_changed_px": int((cov0 != cov1).sum()),
            "visible_triangle_changed_px": int(((i0 != i1) & (cov0 | cov1)).sum()),
            "depth_change_max_m": round(float(dz.max()), 6)}
    a0 = C2.coverage(c0, A0, Y0, 1); a1 = C2.coverage(c1, A1, Y1, 1)
    d = np.abs(a1 - a0)
    res["painting_aa_coverage_ss1"] = {"changed_px_gt_1e-4": int((d > 1e-4).sum()), "max_abs_change": round(float(d.max()), 6)}
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
    X = KC.world(c1, A1, Y1).reshape(-1, 3)
    T = KC.triangles(A1.shape[1], A1.shape[0])
    ar = 0.5 * np.linalg.norm(np.cross(X[T[:, 1]] - X[T[:, 0]], X[T[:, 2]] - X[T[:, 0]]), axis=1)
    res["min_triangle_area_m2"] = float(ar.min())
    res["sea_band_monotone"] = bool(np.all(np.diff(A1[:, :19], axis=1) > 0))
    res["sea_band_height_max_m"] = float(np.abs(Y1[:, :18]).max())
    res["H_change_max_m"] = round(float(np.abs(Y1[:, :200].max(1) - Y0[:, :200].max(1)).max()), 4)
    res["boundary_ring_unchanged"] = bool(np.array_equal(A1[0], A0[0]) and np.array_equal(A1[-1], A0[-1]) and np.array_equal(A1[:, 0], A0[:, 0])
                                          and np.array_equal(A1[:, -1], A0[:, -1]) and np.array_equal(Y1[0], Y0[0]) and np.array_equal(Y1[-1], Y0[-1]))
    res["painting_view_unchanged"] = bool(res["painting_zbuffer_ss1"]["coverage_changed_px"] == 0
                                          and res["painting_zbuffer_ss1"]["visible_triangle_changed_px"] == 0
                                          and res["painting_zbuffer_ss2"]["coverage_changed_px"] == 0
                                          and res["painting_zbuffer_ss2"]["visible_triangle_changed_px"] == 0
                                          and res["painting_aa_coverage_ss1"]["changed_px_gt_1e-4"] == 0)
    BC.jdump(res, out)
    print(json.dumps(res, ensure_ascii=False)[:2500])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
