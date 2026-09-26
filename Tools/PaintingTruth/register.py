# -*- coding: utf-8 -*-
"""番号23 修正2回目：高解像度原画（Met_JP1847_DP130155.jpg）と旧原画（Met_JP1847.jpg）の位置合わせ。

使い方（リポジトリ根で）:
    py -3.10 Tools/PaintingTruth/register.py [--evidence Docs/Evidence/ArtFirst/23]

確かめること:
1) 画素中心の約束での縮小（x_legacy + 0.5 = (x_h + 0.5)·1200/3859、y も同様）からの残差。
   高解像度原画を INTER_AREA で 1200×807 に縮小し、旧原画との ECC（平行移動・アフィン）で残りのずれを測る。
2) 特徴点（SIFT＋RANSAC）による独立の相似変換・アフィン推定と、その残差（旧参照 px）。
3) 新しい表示写像（painting_truth.json の display_frame）と v0.1 の写像の差（表示 px）。
出力: <evidence>/23_registration.json、<evidence>/23_registration.png（1920×1080）
"""
import argparse
import datetime
import math
import os
import platform
import sys

import cv2
import numpy as np

import truthlib as T

V01 = {"scale": 1080.0 / 807.0, "offset_x": (1920 - 1200 * 1080.0 / 807.0) / 2.0, "offset_y": 0.0}


def ecc(template, inp, mode):
    W = np.eye(2, 3, dtype=np.float32)
    cc, W = cv2.findTransformECC(template, inp, W, mode,
                                 (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 500, 1e-8), None, 5)
    return float(cc), W.astype(np.float64)


def corner_disp(W, w, h):
    """ECC の変換（テンプレート座標 → 入力座標）の四隅での移動量（px）。"""
    C = np.array([[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]], np.float64)
    D = C @ W[:, :2].T + W[:, 2] - C
    return float(np.linalg.norm(D, axis=1).max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="Docs/Evidence/ArtFirst/23")
    a = ap.parse_args()
    spec = T.load_spec()
    leg = spec["legacy_reference"]
    lp = T.repo_abs(leg["path"])
    if T.sha256_file(lp) != leg["sha256"]:
        raise RuntimeError("旧原画の SHA-256 が記録と違います")
    hi = T.imread_rgb(T.repo_abs(spec["reference"]["path"]))
    lo = T.imread_rgb(lp)
    Hh, Wh = hi.shape[:2]
    Hl, Wl = lo.shape[:2]
    gh = cv2.cvtColor(hi, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gl = cv2.cvtColor(lo, cv2.COLOR_RGB2GRAY).astype(np.float32)
    kx, ky = Wh / Wl, Hh / Hl

    # 1) 画素中心の約束での縮小と ECC
    area = cv2.resize(gh, (Wl, Hl), interpolation=cv2.INTER_AREA)
    cc_t, Wt = ecc(area, gl, cv2.MOTION_TRANSLATION)
    cc_a, Wa = ecc(area, gl, cv2.MOTION_AFFINE)
    area_rgb = cv2.resize(hi, (Wl, Hl), interpolation=cv2.INTER_AREA)
    dif = np.abs(area_rgb.astype(np.int16) - lo.astype(np.int16))
    # 2) SIFT＋RANSAC（高解像度 → 旧原画）
    sift = cv2.SIFT_create(nfeatures=20000)
    kh, dh = sift.detectAndCompute(gh.astype(np.uint8), None)
    kl, dl = sift.detectAndCompute(gl.astype(np.uint8), None)
    ms = cv2.BFMatcher(cv2.NORM_L2).knnMatch(dl, dh, k=2)
    good = [m for m, n in ms if m.distance < 0.75 * n.distance]
    pl = np.float32([kl[m.queryIdx].pt for m in good])
    ph = np.float32([kh[m.trainIdx].pt for m in good])
    model = np.array([[1 / kx, 0, 0.5 / kx - 0.5], [0, 1 / ky, 0.5 / ky - 0.5]])
    feats = {}
    cv2.setRNGSeed(23)
    for name, fn in (("similarity", cv2.estimateAffinePartial2D), ("affine", cv2.estimateAffine2D)):
        M, inl = fn(ph, pl, method=cv2.RANSAC, ransacReprojThreshold=1.0, maxIters=20000, confidence=0.9999)
        inl = inl.ravel().astype(bool)
        r = np.linalg.norm(ph @ M[:, :2].T + M[:, 2] - pl, axis=1)[inl]
        rm = np.linalg.norm(ph @ model[:, :2].T + model[:, 2] - pl, axis=1)[inl]
        feats[name] = {"matrix_hi_to_legacy": np.round(M, 8).tolist(), "inliers": int(inl.sum()), "matches": len(good),
                       "residual_rms_legacy_px": round(float(np.sqrt((r ** 2).mean())), 4),
                       "residual_p95_legacy_px": round(float(np.percentile(r, 95)), 4),
                       "pixel_centre_model_residual_rms_legacy_px": round(float(np.sqrt((rm ** 2).mean())), 4),
                       "scale_x": round(float(np.hypot(M[0, 0], M[1, 0])), 7), "scale_y": round(float(np.hypot(M[0, 1], M[1, 1])), 7),
                       "rotation_deg": round(float(math.degrees(math.atan2(M[1, 0], M[0, 0]))), 5)}
    # 3) 表示写像の差（v0.1 → v0.2、同じ内容の点）
    fm = T.FrameMap(spec)
    so_x = V01["scale"] / kx
    so_y = V01["scale"] / ky

    def old_disp(xh, yh):
        return (so_x * (xh + 0.5) - 0.5 + V01["offset_x"], so_y * (yh + 0.5) - 0.5 + V01["offset_y"])
    xs = np.array([-0.5, 0.0, Wh / 2 - 0.5, Wh - 1.0, Wh - 0.5])
    new = fm.ref_to_disp(np.stack([xs, np.zeros_like(xs)], -1))
    ox_, _ = old_disp(xs, 0.0)
    ys = np.array([-0.5, Hh - 0.5])
    dy = fm.ref_to_disp(np.stack([np.zeros_like(ys), ys], -1))[:, 1] - np.array([old_disp(0.0, y)[1] for y in ys])

    def shift_at(xd_old):
        xh = (xd_old + 0.5 - V01["offset_x"]) / so_x - 0.5
        return float(fm.ref_to_disp(np.array([[xh, 0.0]]))[0, 0] - xd_old)
    shift = {"dx_at_x_display": {str(v): round(shift_at(float(v)), 4) for v in (157, 400, 700, 959.5, 1108, 1400, 1762)},
             "dx_max_abs_painting": round(float(np.abs(new[:, 0] - ox_).max()), 4),
             "dx_main_wave_range_157_1110": [round(shift_at(157.0), 4), round(shift_at(1110.0), 4)],
             "dy_max_abs": round(float(np.abs(dy).max()), 6)}

    R = {
        "schema": "GreatWave.Step23.registration/1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__},
        "reference": {"path": spec["reference"]["path"], "sha256": T.sha256_file(T.repo_abs(spec["reference"]["path"])), "size": [Wh, Hh]},
        "legacy": {"path": leg["path"], "sha256": leg["sha256"], "size": [Wl, Hl]},
        "pixel_centre_model": {"x_legacy_plus_half": "(x_h + 0.5) * %d / %d" % (Wl, Wh), "y_legacy_plus_half": "(y_h + 0.5) * %d / %d" % (Hl, Hh),
                               "scale_x": kx, "scale_y": ky, "anisotropy_percent": round(100 * (kx / ky - 1), 4)},
        "ecc_area_resized_vs_legacy": {
            "translation": {"correlation": round(cc_t, 6), "dx_dy_legacy_px": [round(Wt[0, 2], 5), round(Wt[1, 2], 5)]},
            "affine": {"correlation": round(cc_a, 6), "matrix": np.round(Wa, 6).tolist(),
                       "max_corner_displacement_legacy_px": round(corner_disp(Wa, Wl, Hl), 4),
                       "max_corner_displacement_display_px": round(corner_disp(Wa, Wl, Hl) * V01["scale"], 4)},
            "rgb_abs_diff_mean_8bit": round(float(dif.mean()), 3), "rgb_abs_diff_p99_8bit": float(np.percentile(dif, 99)),
            "note_ja": "高解像度原画を INTER_AREA（画素中心の約束）で 1200×807 に縮小し、旧原画との ECC で残りのずれを測った。"
                       "幾何の残差は小さいが、画素値は平均 %.1f（8bit）違う。旧原画は別の縮小フィルターと JPEG 圧縮を経たとみられる。" % float(dif.mean())},
        "features_sift_ransac": feats,
        "features_note_ja": "SIFT の特徴点は縮尺の違う画像の間で位置に 0.1〜0.2 旧参照 px の偏りが出る。幾何の判断は ECC を主にし、特徴点は独立の確認（回転・倍率）に使う。",
        "conclusion_ja": ("旧原画は新原画を画素中心の約束で縦横別の倍率（%.5f・%.5f、差 %.3f%%）に縮小したもので、裁ち落としと余白の差はない。"
                          "ECC のアフィン残差は四隅で最大 %.3f 旧参照 px（%.3f 表示 px）、回転は %.4f°（特徴点）。" %
                          (kx, ky, 100 * (kx / ky - 1), corner_disp(Wa, Wl, Hl), corner_disp(Wa, Wl, Hl) * V01["scale"], feats["similarity"]["rotation_deg"])),
        "display_mapping": {"v0_1": V01, "v0_2": {"scale": fm.s, "offset_x": fm.ox, "offset_y": fm.oy},
                            "shift_v0_2_minus_v0_1_display_px": shift,
                            "note_ja": "同じ原画の内容の点の表示位置の差（v0.2 − v0.1）。縦は 0。横は旧原画の縦横比の歪みを除いた分で、x_d に比例する。"},
    }
    ev = T.repo_abs(a.evidence)
    T.save_json(os.path.join(ev, "23_registration.json"), R)
    figure(spec, fm, hi, lo, R, os.path.join(ev, "23_registration.png"))
    print("REGISTER_DONE", R["conclusion_ja"])
    return 0


def figure(spec, fm, hi, lo, R, path):
    """新（v0.2）と旧（v0.1）の表示フレーム画像の市松（80 px）と、唇先端付近の 6 倍拡大（市松 12 px）。"""
    new = fm.warp_to_disp(hi, cv2.INTER_LINEAR)
    Mo = np.array([[V01["scale"], 0, 0.5 * V01["scale"] - 0.5 + V01["offset_x"]], [0, V01["scale"], 0.5 * V01["scale"] - 0.5]])
    old = cv2.warpAffine(lo, Mo, (fm.W, fm.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    yy, xx = np.mgrid[0:fm.H, 0:fm.W]
    chk = ((xx // 80 + yy // 80) % 2 == 0)
    img = np.where(chk[..., None], new, old).copy()
    img[:, :fm.x0] //= 6
    img[:, fm.x1 + 1:] //= 6
    # 拡大（表示 px 1020–1180, 290–410 を 5 倍。拡大図は左下に置き、元の範囲と重ならないようにする）
    x0, y0, w, h, z = 1020, 290, 160, 120, 5
    sub_n = new[y0:y0 + h, x0:x0 + w]
    sub_o = old[y0:y0 + h, x0:x0 + w]
    yy2, xx2 = np.mgrid[0:h, 0:w]
    c2 = ((xx2 // 12 + yy2 // 12) % 2 == 0)
    sub = np.where(c2[..., None], sub_n, sub_o)
    big = cv2.resize(sub, (w * z, h * z), interpolation=cv2.INTER_NEAREST)
    bx, by = 170, 1080 - h * z - 95
    img[by:by + h * z, bx:bx + w * z] = big
    cv2.rectangle(img, (bx - 1, by - 1), (bx + w * z, by + h * z), (255, 255, 255), 1)
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (255, 255, 0), 1)
    e = R["ecc_area_resized_vs_legacy"]
    s = R["display_mapping"]["shift_v0_2_minus_v0_1_display_px"]
    lines = ["23 fix-2 registration: checkerboard 80 px, tiles = new hi-res 3859x2594 (v0.2 mapping) / old 1200x807 (v0.1 mapping)",
             "old = pixel-centre resize of new: scale %.5f / %.5f (anisotropy %.3f%%); ECC affine residual max %.3f legacy px (corners), corr %.4f" % (
                 R["pixel_centre_model"]["scale_x"], R["pixel_centre_model"]["scale_y"], R["pixel_centre_model"]["anisotropy_percent"],
                 e["affine"]["max_corner_displacement_legacy_px"], e["affine"]["correlation"]),
             "display shift v0.2 - v0.1: dy = 0, dx linear in x: %.3f px at x=157, %.3f at lip tip x=1108, %.3f at x=1762" % (
                 s["dx_at_x_display"]["157"], s["dx_at_x_display"]["1108"], s["dx_at_x_display"]["1762"]),
             "inset (lower left): display px %d-%d, %d-%d (yellow box) x%d, checkerboard 12 px" % (x0, x0 + w, y0, y0 + h, z)]
    for i, t in enumerate(lines):
        cv2.putText(img, t, (170, 1000 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(img, t, (170, 1000 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    T.save_png_reserved(path, img, [(255, 255, 255), (0, 0, 0), (255, 255, 0)])


if __name__ == "__main__":
    sys.exit(main())
