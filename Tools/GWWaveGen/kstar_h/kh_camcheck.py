# -*- coding: utf-8 -*-
"""Houdini の PaintingCam が評価器のカメラと同じであることを確かめる（py -3.10）。
入力は kh_bridge.py camcheck が書いた npz（GWW0 の全頂点を Houdini の toNDC で射影したもの）。
  1. Houdini の toNDC → 表示 px と、評価器（gw_wavegen.PaintingCam.project）の表示 px の差（全頂点・輪郭の頂点）
  2. Houdini の射影だけで被覆を塗り、評価器（evaluate.evaluate_core、包絡版）で輪郭 78/130/131/132/72/71 を採点し、
     numpy の射影での採点・K* の meta に記録された値と並べる
usage: py -3.10 kh_camcheck.py <ndc.npz> <gwb> <out.json> [--meta <kstar_meta.json>]
"""
import os
import sys
import json

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kh_common as KC  # noqa: E402
sys.path.insert(0, os.path.join(KC.REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, os.path.join(KC.REPO, "Tools", "GWWaveGen"))
import numpy as np  # noqa: E402
import cv2  # noqa: E402
import truthlib as TL  # noqa: E402
import gw_wavegen_v1 as V1  # noqa: E402
import gw_wavegen as G0  # noqa: E402


class ProxyCam:
    """評価器の rasterize が呼ぶ project() に、あらかじめ計算した表示 px を返すだけのカメラ。"""

    def __init__(self, xyz, W, H):
        self.xyz, self.W, self.H = xyz, W, H

    def project(self, P):
        assert len(P) == len(self.xyz)
        return self.xyz


def envelope(cam, tgt, X, tris, out_png, title):
    import evaluate as E
    cov = V1.rasterize(cam, X, tris)
    seacov, yh = G0.sea_horizon_cover(G0.PaintingCam(tgt.spec), tgt.spec)
    other = np.maximum(cov, seacov)
    truth = E.Truth()
    reg = {"sky": 1.0 - other, "boat_left": np.zeros_like(cov), "boat_mid": np.zeros_like(cov), "boat_fg": np.zeros_like(cov)}
    m, det, rp = E.evaluate_core(truth, truth.disp_rgb, reg, versions=("envelope",), contour_judged=True)
    res = {}
    for k in ("78", "130", "131", "132", "72", "71"):
        for me in m["items"].get(k, {}).get("measures", []):
            if me.get("version") == "envelope":
                res[k] = {"max_px": me["value_max_px"], "p95_px": me["p95_px"], "worst_xy": me.get("worst_display_xy")}
    if out_png:
        img = (truth.disp_rgb * 0.5 + np.dstack([other * 60, other * 90, other * 140]) * 0.5).astype(np.uint8)
        E.overlay_png(truth, img, det, rp, out_png, title, ("envelope",))
    return res, cov


def main():
    npz, gwb, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    meta = sys.argv[sys.argv.index("--meta") + 1] if "--meta" in sys.argv else KC.KSTAR_META
    z = np.load(npz)
    ndc = z["ndc"]; Pc = z["Pcam"]
    G = KC.read_gwb(gwb)
    X = G["X"]; tris = G["tris"]
    tgt = V1.Target()
    params = TL.load_json(os.path.join(KC.REPO, "Tools", "GWWaveGen", "params_v2_af26r01.json"))
    fr = V1.Frame(tgt.spec, float(params["alpha_deg"]), params["anchor"], tgt)
    P_eval = fr.cam.project(X)                                 # evaluator camera (numpy)
    P_kc = KC.project_unity(X)                                 # kh_common's copy of the same formula
    xy_h = KC.ndc_to_display(ndc)                              # Houdini toNDC
    depth_h = -ndc[:, 2]
    ok = P_eval[:, 2] > 0.5
    d_all = np.linalg.norm(xy_h[ok] - P_eval[ok, :2], axis=1)
    # Houdini camera matrix route (world -> camera space with the camera's worldTransform, then pinhole with focal/aperture)
    foc = KC.houdini_focal_mm(); ap = KC.HOU_APERTURE
    xs = (Pc[:, 0] / -Pc[:, 2]) * foc / (ap / 2.0)             # [-1, 1] across the width
    ys = (Pc[:, 1] / -Pc[:, 2]) * foc / (ap / 2.0) * KC.CAM_W / KC.CAM_H
    xy_m = np.stack([(xs * 0.5 + 0.5) * KC.CAM_W - 0.5, (1.0 - (ys * 0.5 + 0.5)) * KC.CAM_H - 0.5], -1)
    d_mat = np.linalg.norm(xy_m[ok] - P_eval[ok, :2], axis=1)
    # silhouette vertices (image within 3 px of the coverage boundary; same rule as candA4_checks.silhouette_band)
    cov = (V1.rasterize(fr.cam, X, tris) > 0.5).astype(np.uint8)
    edge = cv2.morphologyEx(cov, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    dt = cv2.distanceTransform(1 - edge, cv2.DIST_L2, 5)
    xi = np.clip(np.round(P_eval[:, 0]).astype(int), 0, KC.CAM_W - 1); yi = np.clip(np.round(P_eval[:, 1]).astype(int), 0, KC.CAM_H - 1)
    inside = (P_eval[:, 0] >= 0) & (P_eval[:, 0] < KC.CAM_W) & (P_eval[:, 1] >= 0) & (P_eval[:, 1] < KC.CAM_H) & ok
    sil = inside & (dt[yi, xi] <= 3.0)
    d_sil = np.linalg.norm(xy_h[sil] - P_eval[sil, :2], axis=1)
    out_dir = os.path.dirname(os.path.abspath(outp))
    env_h, cov_h = envelope(ProxyCam(np.c_[xy_h, depth_h], KC.CAM_W, KC.CAM_H), tgt, X, tris,
                            os.path.join(out_dir, "camcheck_houdini_projection_overlay.png"), "K* through the Houdini PaintingCam (toNDC)")
    env_n, cov_n = envelope(fr.cam, tgt, X, tris, None, "")
    rec = json.load(open(meta, encoding="utf-8")).get("numpy_preview_envelope", {})
    diff_cov = int(np.abs((cov_h > 0.5).astype(int) - (cov_n > 0.5).astype(int)).sum())
    res = {"schema": "GreatWave.kstar_h.camcheck/1", "gwb": gwb, "gwb_sha256": KC.sha256(gwb), "houdini_ndc": npz,
           "camera_info_houdini": json.loads(str(z["info"])),
           "projection_diff_px_all_vertices": {"n": int(ok.sum()), "max": float(d_all.max()), "p99": float(np.percentile(d_all, 99)), "mean": float(d_all.mean())},
           "projection_diff_px_silhouette_vertices": {"n": int(sil.sum()), "max": float(d_sil.max()), "p99": float(np.percentile(d_sil, 99)), "mean": float(d_sil.mean())},
           "projection_diff_px_houdini_matrix_route": {"max": float(d_mat.max())},
           "depth_diff_m_max": float(np.abs(depth_h[ok] - P_eval[ok, 2]).max()),
           "kh_common_vs_evaluator_px_max": float(np.abs(P_kc - P_eval).max()),
           "coverage_pixels_differing_houdini_vs_numpy": diff_cov,
           "envelope_houdini_projection": env_h, "envelope_numpy_projection": env_n, "envelope_recorded_in_meta": rec,
           "max_abs_diff_houdini_vs_recorded": {k: {"max_px": abs(env_h[k]["max_px"] - rec[k]["max_px"]), "p95_px": abs(env_h[k]["p95_px"] - rec[k]["p95_px"])}
                                                for k in env_h if k in rec}}
    json.dump(res, open(outp, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    brief = {k: res[k] for k in ("projection_diff_px_all_vertices", "projection_diff_px_silhouette_vertices", "projection_diff_px_houdini_matrix_route",
                                 "coverage_pixels_differing_houdini_vs_numpy", "max_abs_diff_houdini_vs_recorded")}
    print(json.dumps(brief, indent=1, default=float))


if __name__ == "__main__":
    main()
