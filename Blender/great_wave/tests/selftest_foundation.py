"""基盤ライブラリ gw.* の自己検証。無画面で実行する。

  blender.exe --background --factory-startup --python tests/selftest_foundation.py -- [--skip-render] [--quick]

or   tools/run_blender.ps1 tests/selftest_foundation.py

出力（results/step1_prepare/foundation/）：
  landmarks_overlay.png (+ _1600.png), crop_S1_crest.png, crop_S2_inner_arc.png,
  crop_S6_claw_tip.png, demo_plot.png, demo_draw.png, font_sheet.png,
  cam_print_render_check.png (if the headless render works), selftest_report.json
"""
import argparse
import math
import os
import sys
import time

_SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import numpy as np  # noqa: E402

from gw import bootstrap, draw, frame, imgio, paths, plot  # noqa: E402

log = bootstrap.log
CHECKS = []
FACTS = {}


def check(name, ok, detail=""):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    log("検証 %s %s | %s" % ("PASS" if ok else "FAIL", name, detail))
    return bool(ok)


def close(a, b, tol):
    return abs(float(a) - float(b)) <= tol


# ---------------------------------------------------------------------------- A
def test_frame():
    F = frame.get_frame()
    FACTS["frame"] = F.summary()
    log("画角", {k: (round(v, 6) if isinstance(v, float) else v) for k, v in F.summary().items()})
    # 導出した定数と仕様第4節の丸めた数値を比較
    for name, got, want, tol in [
        ("frame_h", F.frame_h, 1.5152, 5e-5), ("frame_w", F.frame_w, 2.2540, 1e-4),
        ("x_left", F.x_left, -0.861, 5e-4), ("x_right", F.x_right, 1.393, 5e-4),
        ("z_top", F.z_top, 1.132, 5e-4), ("z_bottom", F.z_bottom, -0.383, 5e-4),
        ("1pct_in_H", float(F.pct_h_to_H(1.0)), 0.01515, 5e-6),
        ("2pct_in_H", float(F.pct_h_to_H(2.0)), 0.0303, 5e-5),
        ("1pct_in_m_at_H11", float(F.pct_h_to_m(1.0)) * 11.0 / F.H, 0.167, 5e-4),
        ("2pct_in_m_at_H11", float(F.pct_h_to_m(2.0)) * 11.0 / F.H, 0.333, 5e-4),
        ("1pct_in_px", float(F.pct_h_to_px(1.0)), 25.94, 1e-9),
    ]:
        check("frame.const.%s" % name, close(got, want, tol), "実測 %.6f、仕様 %.4f" % (got, want))
    # 設計側が指定した厳密な式
    fh = 1.0 / 0.66
    fw = fh * 3859.0 / 2594.0
    check("frame.formula", close(F.frame_h, fh, 1e-12) and close(F.frame_w, fw, 1e-12)
          and close(F.x_left, -0.382 * fw, 1e-12) and close(F.z_top, 1 + 0.087 * fh, 1e-12)
          and close(F.x_right, -0.382 * fw + fw, 1e-12) and close(F.z_bottom, 1 + 0.087 * fh - fh, 1e-12),
          "frame_h=%.6f frame_w=%.6f x_left=%.6f x_right=%.6f z_top=%.6f z_bottom=%.6f"
          % (F.frame_h, F.frame_w, F.x_left, F.x_right, F.z_top, F.z_bottom))
    # 特徴点
    X, Z = F.pct_to_H(38.2, 8.7)
    check("frame.S1_crest", close(X, 0.0, 1e-9) and close(Z, 1.0, 1e-9), "(%.6f, %.6f)、期待値 (0, 1)" % (X, Z))
    X, Z = F.pct_to_H(38.2, 74.7)
    check("frame.trough_74.7pct", close(Z, 0.0, 1e-9), "Z=%.3e、期待値 0" % Z)
    X, Z = F.pct_to_H(39.5, 46.3)
    check("frame.S2", close(X, 0.029, 5e-4) and close(Z, 0.430, 5e-4), "(%.6f, %.6f)、仕様 (+0.029, 0.430)" % (X, Z))
    X, Z = F.pct_to_H(59.2, 33.0)
    check("frame.S6", close(X, 0.473, 5e-4) and close(Z, 0.632, 5e-4), "(%.6f, %.6f)、仕様 (+0.473, 0.632)" % (X, Z))
    over = X * 100.0
    ang = math.degrees(math.atan2(1.0 - Z, X))
    check("frame.S6_derived", close(over, 47.0, 0.5) and close(ang, 38.0, 0.5),
          "張り出しは H の %.2f %%（仕様 47）、方向は水平から下へ %.2f 度（仕様 38）" % (over, ang))
    FACTS["S6_derived"] = {"overhang_pct_of_H": over, "dir_below_horizontal_deg": ang}
    # 四隅
    X, Z = F.px_to_H([0, 3859], [0, 2594])
    check("frame.corners", close(X[0], F.x_left, 1e-12) and close(X[1], F.x_right, 1e-12)
          and close(Z[0], F.z_top, 1e-12) and close(Z[1], F.z_bottom, 1e-12), "画素の四隅が画角の辺に対応")
    # 往復変換（配列化）
    rng = np.random.default_rng(1)
    xp = rng.uniform(0, 3859, 1000)
    yp = rng.uniform(0, 2594, 1000)
    x2, y2 = F.H_to_px(*F.px_to_H(xp, yp))
    e1 = max(np.abs(x2 - xp).max(), np.abs(y2 - yp).max())
    x3, y3 = F.m_to_px(*F.px_to_m(xp, yp))
    e2 = max(np.abs(x3 - xp).max(), np.abs(y3 - yp).max())
    l4, t4 = F.px_to_pct(*F.pct_to_px(rng.uniform(0, 100, 50), rng.uniform(0, 100, 50)))
    pts = np.stack([xp, yp], axis=1)
    e3 = np.abs(F.pts_H_to_px(F.pts_px_to_H(pts)) - pts).max()
    check("frame.roundtrip", e1 < 1e-9 and e2 < 1e-9 and e3 < 1e-9, "最大誤差 px：H %.2e、m %.2e、点列 %.2e" % (e1, e2, e3))
    # 長さ
    check("frame.lengths", close(F.px_to_pct_h(25.94), 1.0, 1e-12) and close(F.H_to_pct_h(F.pct_h_to_H(3.3)), 3.3, 1e-12)
          and close(F.px_to_H_len(2594), F.frame_h, 1e-12) and close(F.m_to_pct_h(F.pct_h_to_m(1.7)), 1.7, 1e-12),
          "pct_h <-> px <-> H <-> m")
    # 等方性：縦横どちらも 1 px は同じ H 長
    check("frame.isotropic_px", close(F.frame_w / F.width_px, F.frame_h / F.height_px, 1e-15), "1 px 当たりの H 長が縦横で一致")
    check("frame.angle", close(F.px_dir_to_deg(1, 1), -45.0, 1e-12) and close(F.px_dir_to_deg(0, -1), 90.0, 1e-12),
          "画素方向を角度へ変換（画素 y は下向き、シーン Z は上向き）")
    # WAVE_HEIGHT_M が許容範囲内にあること
    e = paths.load_params()["WAVE_HEIGHT_M"]
    check("params.WAVE_HEIGHT_M_range", e["allowed_min"] <= e["value"] <= e["allowed_max"],
          "%.2f in [%.1f, %.1f]" % (e["value"], e["allowed_min"], e["allowed_max"]))
    cam = F.cam_print()
    check("frame.cam_print_numbers", close(cam["ortho_scale"], F.frame_w * F.H, 1e-12)
          and cam["resolution_x"] == 3859 and cam["resolution_y"] == 2594
          and close(cam["z_range_covered_m"][0], cam["z_range_m"][0], 1e-9)
          and close(cam["z_range_covered_m"][1], cam["z_range_m"][1], 1e-9),
          "直交投影の尺度 %.6f m、位置 (%.4f, %.1f, %.4f)、解像度 %d×%d" % (
              cam["ortho_scale"], cam["location"][0], cam["location"][1], cam["location"][2],
              cam["resolution_x"], cam["resolution_y"]))
    FACTS["cam_print"] = cam


# ---------------------------------------------------------------------------- B
def test_config():
    P = paths.load_params()
    bad = [k for k, v in P.items() if not k.startswith("_")
           and not (isinstance(v, dict) and "value" in v and v.get("provenance") and v.get("comment"))]
    check("params.every_entry_has_value_provenance_comment", not bad, "不備のある項目：%s" % bad)
    check("params.backlog_sum", close(sum(P["backlog_phase_seconds"]["value"]) * P["fps"]["value"], P["total_frames"]["value"], 1e-9),
          "区間秒数の合計×fps = %.1f、total_frames = %d" % (sum(P["backlog_phase_seconds"]["value"]) * P["fps"]["value"], P["total_frames"]["value"]))
    T = paths.load_thresholds()
    ids = ["S%d" % i for i in range(1, 9)] + ["M%d" % i for i in range(1, 7)] + ["G%d" % i for i in range(1, 6)]
    missing = [i for i in ids if i not in T]
    check("thresholds.all_ids_present", not missing, "欠落：%s" % missing)
    bad, n = [], 0
    for tid in ids:
        for cname, c in T.get(tid, {}).get("checks", {}).items():
            n += 1
            ok = ("value" in c and "unit" in c and c.get("provenance") in ("backlog", "spec initial value")
                  and set(c.get("tiers", {}).keys()) == set(paths.TIER_NAMES)
                  and c["tiers"]["spec"] == c["value"])
            if not ok:
                bad.append("%s.%s" % (tid, cname))
    check("thresholds.entries_wellformed", not bad, "検査 %d 件、不備のある項目：%s" % (n, bad))
    # 両階層を常に報告
    r = paths.check_threshold("S1", "dx_pct_h", -3.1)
    check("thresholds.check_reports_both_tiers", r["tiers"]["spec"]["pass"] is False and r["tiers"]["user_relaxed_5pct"]["pass"] is True
          and close(r["tiers"]["spec"]["margin"], -1.1, 1e-9), paths.format_check(r))
    r = paths.check_threshold("S4", "mid_max_deg", 46.0)
    check("thresholds.report_only", r["tiers"]["spec"]["pass"] is None, paths.format_check(r))
    check("thresholds.positional_relaxed_to_5", all(paths.threshold(t, c, "user_relaxed_5pct") == 5.0 for t, c in [
        ("S1", "dx_pct_h"), ("S1", "dz_pct_h"), ("S2", "dist_pct_h"), ("S3", "height_err_pct_h"), ("S5", "pos_pct_h"),
        ("S7", "mean_dev_pct_h"), ("S7", "p95_dev_pct_h")]), "S1 S2 S3 S5.pos S7 -> 5.0 in tier user_relaxed_5pct")


# ---------------------------------------------------------------------------- C
def scratch_dir():
    roots = paths.param("allowed_write_roots")
    for r in roots[1:]:
        if os.path.isdir(r):
            return paths.ensure_dir(os.path.join(r, "selftest_foundation"))
    return paths.ensure_dir(os.path.join(paths.RESULTS_DIR, "_tmp_selftest"))


def test_imgio(out_dir, quick):
    tmp = scratch_dir()
    rng = np.random.default_rng(7)
    # 1. byte ramp: are .pixels the stored bytes / 255 ?  (independent of Blender's writer)
    ramp = np.tile(np.arange(256, dtype=np.uint8)[None, :], (8, 1))
    p = imgio.save_png(os.path.join(tmp, "ramp_gray.png"), ramp)
    back, info = imgio.load_image(p)
    ok = back.shape[:2] == ramp.shape and all(np.array_equal(back[:, :, c], ramp) for c in range(3))
    check("imgio.bpy_pixels_are_stored_bytes_over_255", ok and info["max_abs_dev_from_byte"] < 1e-3,
          "灰色階調 0..255 を bpy で再読込：一致=%s、max|v*255−丸め|=%.2e、色空間=%s、深度=%s"
          % (ok, info["max_abs_dev_from_byte"], info["colorspace"], info["depth"]))
    FACTS["bpy_ramp_info"] = info
    # 2. random round trips
    cases = {
        "gray": rng.integers(0, 256, (37, 53), dtype=np.uint8),
        "rgb": rng.integers(0, 256, (41, 67, 3), dtype=np.uint8),
        "rgba": rng.integers(0, 256, (29, 31, 4), dtype=np.uint8),
    }
    cases["rgba"][:, :, 3] = np.where(cases["rgba"][:, :, 3] < 128, 255, cases["rgba"][:, :, 3])  # see rgba_lowalpha below
    for name, arr in cases.items():
        for mode in ("adaptive", "none", "sub", "up"):
            p = imgio.save_png(os.path.join(tmp, "rt_%s_%s.png" % (name, mode)), arr, filter_mode=mode)
            d = imgio.roundtrip_max_abs_diff(p, arr, "both")
            check("imgio.roundtrip.%s.%s" % (name, mode), d["numpy"] == 0 and d["bpy"] is not None and d["bpy"] <= 1,
                  "最大絶対差 NumPy 読取=%s、bpy 読込=%s" % (d["numpy"], d["bpy"]))
    # bpy 経由の低アルファ RGBA：ほぼ透明な画素の RGB が変わり得るため報告専用
    low = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
    p = imgio.save_png(os.path.join(tmp, "rt_rgba_lowalpha.png"), low)
    d = imgio.roundtrip_max_abs_diff(p, low, "both")
    FACTS["rgba_any_alpha_roundtrip"] = d
    check("imgio.roundtrip.rgba_any_alpha.numpy", d["numpy"] == 0, "numpy=%s bpy=%s (bpy value is informational)" % (d["numpy"], d["bpy"]))
    # 真偽値マスク
    m = rng.random((20, 30)) > 0.5
    p = imgio.save_png(os.path.join(tmp, "rt_bool.png"), m)
    check("imgio.roundtrip.bool", np.array_equal(imgio.read_png(p) > 127, m), "真偽値マスクを 0／255 で保存")
    # 3. write guard
    try:
        imgio.save_png("C:/Users/Public/gw_should_not_exist.png", ramp)
        guard = False
    except PermissionError:
        guard = True
    check("paths.write_guard_outside_roots", guard and not os.path.exists("C:/Users/Public/gw_should_not_exist.png"),
          "save_png outside the allowed roots raises PermissionError")
    try:
        paths.assert_writable(paths.param("painting_path"))
        guard = False
    except PermissionError:
        guard = True
    check("paths.write_guard_inputs", guard, "原画のパスへの書込みを拒否")
    # 4. the painting
    t0 = time.perf_counter()
    painting, pinfo = imgio.load_image(paths.painting_path())
    t_load = time.perf_counter() - t0
    painting = np.ascontiguousarray(painting[:, :, :3])
    FACTS["painting_info"] = pinfo
    FACTS["painting_load_seconds"] = t_load
    check("painting.size_3859x2594", painting.shape == (2594, 3859, 3), "形状 %r、読込 %.2f 秒" % (painting.shape, t_load))
    check("painting.pixels_are_bytes", pinfo["max_abs_dev_from_byte"] < 1e-3 and not pinfo["is_float"],
          "max|v*255-round|=%.2e depth=%s colorspace=%s channels=%s" % (
              pinfo["max_abs_dev_from_byte"], pinfo["depth"], pinfo["colorspace"], pinfo["channels"]))
    FACTS["painting_mean_rgb"] = [float(v) for v in painting.reshape(-1, 3).mean(axis=0)]
    FACTS["painting_probe_px"] = {"(100,100)": painting[100, 100].tolist(), "(1474,225)": painting[225, 1474].tolist(),
                                  "(1524,1201)": painting[1201, 1524].tolist(), "(2284,856)": painting[856, 2284].tolist(),
                                  "(3000,500)": painting[500, 3000].tolist()}
    log("原画の標本 px (x,y)→rgb", FACTS["painting_probe_px"])
    if not quick:
        t0 = time.perf_counter()
        p = imgio.save_png(os.path.join(tmp, "painting_roundtrip.png"), painting)
        t_save = time.perf_counter() - t0
        t0 = time.perf_counter()
        d_np = imgio.roundtrip_max_abs_diff(p, painting, "numpy")["numpy"]
        t_np = time.perf_counter() - t0
        t0 = time.perf_counter()
        d_bpy = imgio.roundtrip_max_abs_diff(p, painting, "bpy")["bpy"]
        t_bpy = time.perf_counter() - t0
        FACTS["painting_png_roundtrip"] = {"save_s": t_save, "read_png_s": t_np, "bpy_load_s": t_bpy,
                                           "file_MB": os.path.getsize(p) / 1e6, "diff_numpy": d_np, "diff_bpy": d_bpy}
        check("imgio.roundtrip.painting_full_res", d_np == 0 and d_bpy is not None and d_bpy <= 1,
              "3859x2594 RGB: save %.2f s (%.1f MB), read_png %.2f s diff %s, bpy load %.2f s diff %s"
              % (t_save, os.path.getsize(p) / 1e6, t_np, d_np, t_bpy, d_bpy))
    # 5. the user's WebP reference images decode?
    for key in ("ref_image_tank_frames", "ref_image_houdini_viewport"):
        try:
            a = imgio.load_image_rgb(paths.param(key))
            FACTS[key + "_size"] = [int(a.shape[1]), int(a.shape[0])]
            check("imgio.webp.%s" % key, a.ndim == 3 and a.shape[0] > 10, "復号 %d×%d" % (a.shape[1], a.shape[0]))
        except Exception as exc:  # report, do not hide
            check("imgio.webp.%s" % key, False, "%s: %s" % (type(exc).__name__, exc))
    return painting


# ---------------------------------------------------------------------------- D
def test_draw(out_dir):
    # 太い水平線：厳密な画素行
    img = draw.canvas(40, 60, "white")
    draw.line(img, (5, 20), (55, 20), "black", 4, aa=False)
    rows = np.nonzero((img[:, 30, 0] < 128))[0]
    check("draw.line_thickness", rows.tolist() == [18, 19, 20, 21], "y=20 の幅 4 の線が通る行：%s" % rows.tolist())
    # アンチエイリアス線の面積保存：幅 3・長さ 40 px は約 120 px の描画量と丸い端部
    img = draw.canvas(40, 80, "white")
    draw.line(img, (20, 10.3), (60, 30.7), "black", 3)
    ink = (255 - img[:, :, 0].astype(np.float64)).sum() / 255.0
    want = 3 * math.hypot(40, 20.4) + math.pi * 1.5 ** 2
    check("draw.line_aa_ink", abs(ink - want) / want < 0.12, "描画面積 %.1f px²、理想の線分カプセル %.1f px²（縁の補間で幅が約 1 px 増える）" % (ink, want))
    # 多角形マスク：矩形と円の面積
    m = draw.polygon_mask((50, 60), [(10, 5), (30, 5), (30, 45), (10, 45)])
    check("draw.polygon_mask_rect", int(m.sum()) == 20 * 40 and m[5, 10] and not m[4, 10] and m[44, 29] and not m[45, 29],
          "area %d (want 800)" % int(m.sum()))
    t = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    m = draw.polygon_mask((300, 300), np.stack([150 + 100 * np.cos(t), 150 + 100 * np.sin(t)], axis=1))
    check("draw.polygon_mask_circle", abs(m.sum() - math.pi * 100 ** 2) / (math.pi * 100 ** 2) < 0.003,
          "area %d vs pi r^2 %.0f" % (int(m.sum()), math.pi * 100 ** 2))
    ol = draw.mask_outline(m)
    check("draw.mask_outline", 500 < ol.sum() < 900 and not (ol & ~m).any(), "輪郭 %d px（周長 %.0f）" % (int(ol.sum()), 2 * math.pi * 100))
    # 縮小：ボックスフィルタは平均を保ち、整数倍率ならブロック平均と一致
    rng = np.random.default_rng(3)
    a = rng.integers(0, 256, (120, 180, 3), dtype=np.uint8)
    b = draw.resize(a, 60, 40)
    blk = a.reshape(40, 3, 60, 3, 3).mean(axis=(1, 3))
    check("draw.resize_box_integer", np.abs(b.astype(np.float64) - blk).max() <= 0.5 + 1e-6, "3 倍のボックス縮小がブロック平均と一致（最大偏差 %.3f）" % np.abs(b - blk).max())
    c = draw.resize(a, 77, 53)
    check("draw.resize_box_fractional", abs(c.mean() - a.mean()) < 0.6 and c.shape == (53, 77, 3), "平均 %.2f→%.2f" % (a.mean(), c.mean()))
    up = draw.resize(a[:4, :4], scale=3, method="nearest")
    check("draw.resize_nearest", np.array_equal(up, np.repeat(np.repeat(a[:4, :4], 3, 0), 3, 1)), "最近傍の 3 倍拡大が np.repeat と一致")
    ub = draw.resize(a[:8, :8], scale=2, method="bilinear")
    check("draw.resize_bilinear", ub.shape == (16, 16, 3) and abs(ub.mean() - a[:8, :8].mean()) < 6, "形状 %r" % (ub.shape,))
    # 切り抜きと視野の対応
    v = draw.View(a, 10, 20, 70, 60, scale=3)
    pt = v.to_view((10, 20))
    check("draw.view_mapping", v.img.shape == (120, 180, 3) and close(pt[0], 0, 1e-9) and close(pt[1], 0, 1e-9)
          and np.allclose(v.to_image(v.to_view([(33.3, 44.4)])), [(33.3, 44.4)]), "View.to_view / to_image round trip")
    # 重ね描き
    base = draw.canvas(10, 10, (100, 100, 100))
    mk = np.zeros((10, 10), bool)
    mk[2:5, 2:5] = True
    draw.overlay_mask(base, mk, (200, 0, 0), 0.5)
    check("draw.overlay_mask", base[3, 3].tolist() == [150, 50, 50] and base[0, 0].tolist() == [100, 100, 100], "灰色に赤を 50%% 重ねると %s" % base[3, 3].tolist())
    # 文字
    w, h = draw.text_size("Hello, H=11", 2)
    check("draw.text_size", (w, h) == ((11 * 6 - 1) * 2, 18), "%d×%d（下にはみ出す行を含む 5×9 セル、倍率 2）" % (w, h))
    # 境界事例：グレースケール、画像外の描画、視野、NaN の切れ目
    gimg = draw.canvas(30, 40, 0, channels=1)
    draw.polyline(gimg, [(-20, -5), (20, 15), (np.nan, np.nan), (30, 5), (90, 60)], 255, 3)
    draw.circle(gimg, (38, 28), 6, 200)
    draw.text(gimg, 30, 22, "clip", 255, 2)
    draw.rect(gimg, -5, -5, 10, 10, 128, 1)
    draw.marker(gimg, (500, 500), "o", 5, 255)
    check("draw.edge_cases_gray_and_clipping", gimg.ndim == 2 and gimg.max() == 255 and gimg[10, 10] > 0, "二次元灰色画像、画面外で切れる図形、NaN の切れ目")
    big = draw.canvas(50, 50, "white")
    sub_view = big[10:40, 10:40]
    draw.line(sub_view, (-10, 15), (60, 15), "black", 2, aa=False)
    check("draw.draws_into_numpy_views", big[25, 5, 0] == 255 and big[25, 20, 0] == 0 and big[25, 45, 0] == 255, "部分配列への描画は部分配列の境界で切れる")
    flipped = big[::-1, ::2]
    pth = imgio.save_png(os.path.join(scratch_dir(), "noncontig.png"), flipped)
    check("imgio.save_noncontiguous", np.array_equal(imgio.read_png(pth), flipped), "連続しない配列のビューを厳密に保存")
    # ---- demo sheet (looked at by the agent)
    demo = draw.canvas(520, 900, "white")
    draw.text(demo, 10, 8, "gw.draw demo: lines, dashes, markers, polygon, overlay, text", "black", 2)
    for k, wd in enumerate((1, 2, 4, 8)):
        draw.line(demo, (20, 50 + 22 * k), (300, 70 + 22 * k), draw.PALETTE[k], wd)
        draw.text(demo, 310, 52 + 22 * k, "width %d" % wd, draw.PALETTE[k], 2)
    tt = np.linspace(0, 1, 200)
    wave = np.stack([20 + 560 * tt, 200 + 40 * np.sin(tt * 12)], axis=1)
    draw.polyline(demo, wave, "blue", 3)
    draw.polyline(demo, wave + (0, 30), "red", 3, dash=(14, 8))
    draw.polyline(demo, [(620, 60), (860, 60), (860, 200), (620, 200)], "green", 3, closed=True)
    draw.polyline(demo, [(640, 80), (840, 80), (840, 180), (640, 180)], "orange", 2, closed=True, dash=(10, 6))
    for k, kind in enumerate("oO+xsd"):
        draw.marker(demo, (40 + 60 * k, 300), kind, 10, draw.PALETTE[k], 2, outline="black" if k % 2 else None)
        draw.text(demo, 40 + 60 * k, 320, kind, "black", 2, anchor="ct")
    draw.fill_polygon(demo, [(450, 280), (560, 300), (520, 380), (430, 350)], "cyan", 0.6)
    draw.circle(demo, (700, 320), 50, "purple", fill=False, width=3)
    draw.circle(demo, (700, 320), 20, "magenta", fill=True, alpha=0.5)
    draw.rect(demo, 780, 270, 880, 370, "brown", 3)
    draw.rect(demo, 800, 290, 860, 350, "yellow", fill=True, alpha=0.5)
    draw.label_point(demo, (120, 430), "label_point (120,430)", "red", 2, offset=(12, -12))
    draw.text(demo, 450, 430, "anchor=cm on gray box", "white", 2, bg="darkgray", anchor="cm")
    draw.text(demo, 10, 470, "multi-line\ntext scale 1", "black", 1)
    draw.text(demo, 200, 470, "scale 3: 0.4303 H", "navy", 3)
    imgio.save_png(os.path.join(out_dir, "demo_draw.png"), demo)
    # フォント一覧
    chars = "".join(chr(c) for c in range(32, 127))
    lines = [chars[i:i + 32] for i in range(0, len(chars), 32)]
    sheet = draw.canvas(150, 32 * 6 * 4 + 20, "white")
    draw.text(sheet, 10, 10, "\n".join(lines), "black", 4)
    imgio.save_png(os.path.join(out_dir, "font_sheet.png"), sheet)
    # 一覧画像
    cells = [draw.canvas(60 + 10 * k, 100, draw.PALETTE[k]) for k in range(5)]
    sheet2 = draw.grid(cells, ncols=3, labels=["cell %d" % k for k in range(5)], label_scale=1)
    check("draw.grid", sheet2.ndim == 3 and sheet2.shape[1] == 3 * 100 + 4 * 8, "格子 %d×%d" % (sheet2.shape[1], sheet2.shape[0]))
    hs = draw.hstack([cells[0], cells[4]], gap=5)
    vs = draw.vstack([cells[0], cells[4]], gap=5)
    check("draw.hstack_vstack", hs.shape == (100, 205, 3) and vs.shape == (165, 100, 3), "横結合 %r、縦結合 %r" % (hs.shape, vs.shape))


# ---------------------------------------------------------------------------- E
def test_plot(out_dir):
    t = np.linspace(0, 9.5, 286)
    h = np.where(t < 4, 0.2 + 0.8 * (t / 4) ** 2, 1.0 - 0.03 * np.clip((t - 4) / 3, 0, 1))
    o = np.clip((t - 4) / 5.5, 0, 1) ** 1.5 * 0.35
    th = np.clip(20 + 70 * t / 4.0, 0, 95)
    th[120:130] = np.nan
    p1 = dict(series=[{"label": "h(t) [H]", "x": t, "y": h, "color": "blue"},
                      {"label": "o(t) [H]", "x": t, "y": o, "color": "red", "dash": (10, 6)},
                      {"label": "samples", "x": t[::15], "y": h[::15], "color": "black", "marker": "o", "line": False}],
              title="demo: synthetic h(t), o(t)  (NOT measured data)", xlabel="t [s]", ylabel="length [H]",
              vlines=[{"x": 4.0, "label": "rise end"}, {"x": 7.0, "label": "overhang end"}],
              spans=[{"x0": 0, "x1": 4, "label": "takamaru", "color": "green"},
                     {"x0": 4, "x1": 7, "label": "haridasu", "color": "orange"},
                     {"x0": 7, "x1": 9.5, "label": "makikomu", "color": "purple"}],
              hlines=[{"y": 1.0, "label": "H"}], ylim=(0, 1.2), size=(1200, 480))
    p2 = dict(series=[{"label": "theta(t) [deg] (gap = NaN)", "x": t, "y": th, "color": "green"}],
              title="demo: synthetic theta(t)", xlabel="t [s]", ylabel="angle [deg]",
              hlines=[{"y": 30, "label": "M1 30 deg", "color": "red"}, {"y": 80, "label": "M2 80 deg", "color": "red"}],
              size=(1200, 380))
    fig = plot.multi_plot([p1, p2], ncols=1, title="gw.plot self-test (synthetic curves)")
    imgio.save_png(os.path.join(out_dir, "demo_plot.png"), fig)
    empty = plot.line_plot([], title="no data", size=(400, 300))
    one = plot.line_plot([{"label": "single point", "x": [1.0], "y": [2.0], "marker": "o"}], size=(400, 300))
    allnan = plot.line_plot([{"label": "all NaN", "x": [0, 1, 2], "y": [np.nan] * 3}], size=(400, 300))
    check("plot.degenerate_inputs", empty.shape == one.shape == allnan.shape == (300, 400, 3), "空・一点・全 NaN の系列でも例外にならない")
    ticks, step = plot.nice_ticks(0.0, 9.5, 8)
    check("plot.nice_ticks", close(step, 2.0, 1e-12) or close(step, 1.0, 1e-12) or close(step, 2.5, 1e-12), "目盛 %s" % np.round(ticks, 3).tolist())
    # 軸内に青画素があり、曲線が実際に描かれていること
    sub = plot.line_plot(**p1)
    blue = (sub[:, :, 2] > 180) & (sub[:, :, 0] < 90)
    # h(t) の線は長さ約 1000 px・幅 2 px。アンチエイリアス端の画素は数えない。
    check("plot.curve_drawn", blue.sum() > 800 and sub.shape == (480, 1200, 3), "青い曲線 %d px、図 %r" % (int(blue.sum()), fig.shape))
    lay = [plot.line_plot(_layout_only=True, **p) for p in (p1, p2)]
    check("plot.multi_plot_layout", lay[0]["legend_width"] != lay[1]["legend_width"] and fig.shape[1] == 1200,
          "凡例の幅 %s は multi_plot(align_axes=True) で揃う" % [l["legend_width"] for l in lay])
    eq = plot.line_plot([{"label": "unit circle", "x": np.cos(np.linspace(0, 6.3, 100)), "y": np.sin(np.linspace(0, 6.3, 100))}],
                        title="equal_aspect: unit circle", size=(700, 420), equal_aspect=True, legend=None,
                        xlabel="X [H]", ylabel="Z [H]")
    imgio.save_png(os.path.join(paths.step1_dir("foundation"), "demo_plot_equal_aspect.png"), eq)
    red_or_blue = (eq[:, :, 2] > 180) & (eq[:, :, 0] < 90)
    ys, xs = np.nonzero(red_or_blue)
    ratio = (xs.max() - xs.min()) / float(ys.max() - ys.min())
    check("plot.equal_aspect", abs(ratio - 1.0) < 0.05, "画素上の円の幅／高さ = %.3f" % ratio)


# ---------------------------------------------------------------------------- F
def test_cam_print(out_dir, skip_render):
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    F = frame.get_frame()
    scene = bootstrap.reset_scene()
    cam = F.make_cam_print(scene)
    bpy.context.view_layer.update()
    worst = 0.0
    for name, (lp, tp) in list(frame.SPEC_LANDMARKS_PCT.items()) + [("corner_tl", (0, 0)), ("corner_br", (100, 100))]:
        Xm, Zm = F.px_to_m(*F.pct_to_px(lp, tp))
        co = world_to_camera_view(scene, cam, Vector((float(Xm), 3.7, float(Zm))))
        px = co.x * scene.render.resolution_x
        py = (1.0 - co.y) * scene.render.resolution_y
        wx, wy = F.pct_to_px(lp, tp)
        worst = max(worst, abs(px - wx), abs(py - wy))
    fwd = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    check("cam_print.projection", worst < 1e-2, "world_to_camera_view と Frame.H_to_px の最大誤差 %.2e px（float32 行列）" % worst)
    check("cam_print.looks_along_plus_Y", abs(fwd.y - 1.0) < 1e-6 and cam.data.type == "ORTHO", "視線方向 (%.3f, %.3f, %.3f)" % tuple(fwd))
    FACTS["cam_print_projection_max_err_px"] = worst
    if skip_render:
        return
    # 任意：X=[0, X_S6]、Z=[0,H] の矩形を画面なしで実レンダリング
    try:
        H = F.H
        xs6 = float(F.pct_to_H(59.2, 33.0)[0]) * H
        mesh = bpy.data.meshes.new("probe_rect")
        mesh.from_pydata([(0, 0, 0), (xs6, 0, 0), (xs6, 0, H), (0, 0, H)], [], [(0, 1, 2, 3)])
        obj = bpy.data.objects.new("probe_rect", mesh)
        scene.collection.objects.link(obj)
        obj.color = (0.0, 0.0, 0.0, 1.0)
        world = bpy.data.worlds.new("w")
        world.color = (1.0, 1.0, 1.0)
        scene.world = world
        scene.render.engine = "BLENDER_WORKBENCH"
        sh = scene.display.shading
        sh.light = "FLAT"
        sh.color_type = "OBJECT"
        sh.background_type = "VIEWPORT"
        sh.background_color = (1.0, 1.0, 1.0)
        sh.show_backface_culling = False
        scene.view_settings.view_transform = "Standard"
        scene.render.dither_intensity = 0.0          # dithering turns the white background into 254/255 noise
        scene.render.film_transparent = False
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        path = os.path.join(out_dir, "cam_print_render_check.png")
        scene.render.filepath = paths.assert_writable(path)
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        dt = time.perf_counter() - t0
        r = imgio.load_image_rgb(path)
        dark = r[:, :, 0].astype(np.float64) < 128
        if dark.sum() == 0:
            check("cam_print.render_rect", False, "描画に暗い画素がない（画面なしの Workbench 描画が使えない可能性）")
            return
        # 黒矩形のアンチエイリアス被覆率：描画は線形光で合成し、ファイルは sRGB 符号化
        v = r[:, :, 0].astype(np.float64) / 255.0
        lin = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
        cov = 1.0 - lin
        ys, xs = np.nonzero(dark)
        row = cov[(ys.min() + ys.max()) // 2]
        col = cov[:, (xs.min() + xs.max()) // 2]
        def edges(profile):
            hit = np.nonzero(profile > 0.03)[0]          # first / last (partially) covered pixel
            a, b = int(hit[0]), int(hit[-1])
            return a + (1.0 - profile[a]), b + profile[b]

        x_lo, x_hi = edges(row)
        y_lo, y_hi = edges(col)
        want = (float(F.pct_to_px(38.2, 8.7)[0]), float(F.pct_to_px(59.2, 8.7)[0]),
                float(F.pct_to_px(0, 8.7)[1]), float(F.pct_to_px(0, 74.7)[1]))
        got = (x_lo, x_hi, y_lo, y_hi)
        err = max(abs(g - w) for g, w in zip(got, want))
        FACTS["cam_print_render"] = {"edges_px_got": got, "edges_px_want": want, "max_err_px": err, "render_s": dt,
                                     "size": [int(r.shape[1]), int(r.shape[0])]}
        check("cam_print.render_rect", r.shape[:2] == (2594, 3859) and err < 1.0,
              "矩形の辺の画素値は (%.2f %.2f %.2f %.2f)、期待値 (%.2f %.2f %.2f %.2f)、最大誤差 %.2f px、描画 %.1f 秒"
              % (got + want + (err, dt)))
    except Exception as exc:
        check("cam_print.render_rect", False, "画面なしの描画に失敗：%s：%s" % (type(exc).__name__, exc))


# ---------------------------------------------------------------------------- G
def rough_probes(painting):
    """単純な色のしきい値による概略画素測定。目視確認に添える妥当性の数値に限る。
    S1～S6 の精密な再測定は輪郭作業で行う。"""
    F = frame.get_frame()
    out = {}
    r = painting[:, :, 0].astype(np.int32)
    g = painting[:, :, 1].astype(np.int32)
    b = painting[:, :, 2].astype(np.int32)
    luma = (299 * r + 587 * g + 114 * b) // 1000
    ink = (luma < 120) & (b >= r)                      # dark blue outline / dark blue water
    # S1：大波の濃い輪郭の上辺。横幅の 30～46 % にある列
    x0, x1 = int(0.30 * F.width_px), int(0.46 * F.width_px)
    sub = ink[:int(0.30 * F.height_px), x0:x1]
    run = sub[:-2] & sub[1:-1] & sub[2:]               # >= 3 ink px vertically: ignores paper specks
    first = np.where(run.any(axis=0), run.argmax(axis=0), 10 ** 6)
    ymin = int(first.min())
    cols = np.nonzero(first <= ymin + 2)[0] + x0
    sx = float(F.pct_to_px(38.2, 8.7)[0])
    c_spec = int(sx) - x0
    thick = int(np.argmin(sub[first[c_spec]:first[c_spec] + 40, c_spec])) if first[c_spec] < 10 ** 6 else None
    out["S1_probe"] = {
        "method": "列ごとに濃青輪郭の上辺を探す（輝度<120、B>=R、縦に 3 px 以上）。横幅の 30～46 % の列を対象。"
                  "y は最上の行、x はそこから 2 px 以内にある列の平均。頂部が平坦なので x は一意ではない",
        "x_px": float(cols.mean() + 0.5), "y_px": float(ymin),
        "plateau_x_px_range_within_2px": [int(cols.min()), int(cols.max()) + 1],
        "plateau_width_pct_h": float(F.px_to_pct_h(cols.max() + 1 - cols.min())),
        "outline_top_edge_y_px_at_spec_column": float(first[c_spec]) if first[c_spec] < 10 ** 6 else None,
        "outline_thickness_px_at_spec_column": thick,
    }
    # S2：巻き込み下の空の領域の左端＝青い波腹の右端。高さの 43～58 % にある行
    wy0, wy1 = int(0.43 * F.height_px), int(0.58 * F.height_px)
    wx0, wx1 = int(0.36 * F.width_px), int(0.60 * F.width_px)
    sky = ((r >= b) & (luma > 140))[wy0:wy1, wx0:wx1]
    bx = np.full(sky.shape[0], np.nan)
    for j in range(sky.shape[0]):
        d = np.diff(np.concatenate([[0], sky[j].astype(np.int8), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        if starts.size:
            k = int(np.argmax(ends - starts))          # その行で最も長い空の区間
            bx[j] = wx0 + starts[k]
    half = 7
    med = np.array([np.nanmedian(bx[max(0, j - half):j + half + 1]) for j in range(len(bx))])
    jmin = int(np.nanargmin(med))
    near = np.nonzero(med <= med[jmin] + 2)[0]
    out["S2_probe"] = {
        "method": "上から 43～58 % の各行で、横幅の 36～60 % にある空らしい画素（R>=B、輝度>140）の最長区間の左端を探す。"
                  "15 行の中央値を使い、x は最小の境界、y はそこから 2 px 以内の行の中心",
        "x_px": float(med[jmin]), "y_px": float(wy0 + near.mean() + 0.5),
        "rows_within_2px_y_px_range": [int(wy0 + near.min()), int(wy0 + near.max()) + 1],
        "boundary_x_px_at_spec_row": float(med[int(F.pct_to_px(0, 46.3)[1]) - wy0]),
    }
    # S6：爪の最右輪郭画素。窓は x=50～66 %、y=22～45 %
    wx0, wx1 = int(0.50 * F.width_px), int(0.66 * F.width_px)
    wy0, wy1 = int(0.22 * F.height_px), int(0.45 * F.height_px)
    sub = ink[wy0:wy1, wx0:wx1]
    run = sub[:, :-2] & sub[:, 1:-1] & sub[:, 2:]
    colhit = np.nonzero(run.any(axis=0))[0]
    if colhit.size:
        cx = int(colhit.max()) + 2                                  # 最も右の 3 画素連続区間の終列
        rows = np.nonzero(sub[:, cx])[0]
        out["S6_probe"] = {
            "method": "窓 x=50～66 %、y=22～45 % 内の、横に 3 px 以上連なる濃青輪郭の最右画素。x は輪郭の右端",
            "x_px": float(wx0 + cx + 1), "y_px": float(wy0 + rows.mean() + 0.5),
        }
    for key in list(out.keys()):
        p = out[key]
        lp, tp = F.px_to_pct(p["x_px"], p["y_px"])
        p["left_pct"], p["top_pct"] = float(lp), float(tp)
        X, Z = F.px_to_H(p["x_px"], p["y_px"])
        p["X_H"], p["Z_H"] = float(X), float(Z)
        name = {"S1_probe": "S1_crest", "S2_probe": "S2_inner_arc_deepest", "S6_probe": "S6_claw_rightmost"}[key]
        sx, sy = F.pct_to_px(*frame.SPEC_LANDMARKS_PCT[name])
        p["dx_pct_h_vs_spec"] = float(F.px_to_pct_h(p["x_px"] - sx))
        p["dy_pct_h_vs_spec"] = float(F.px_to_pct_h(p["y_px"] - sy))
        log("標本 %s：px (%.1f, %.1f) = 左から %.2f %%、上から %.2f %%；仕様との差 dx %+.2f %%h、dy（下方向）%+.2f %%h"
            % (key, p["x_px"], p["y_px"], p["left_pct"], p["top_pct"], p["dx_pct_h_vs_spec"], p["dy_pct_h_vs_spec"]))
    return out


def make_overlay(painting, out_dir, probes):
    F = frame.get_frame()
    img = painting.copy()
    W, Hh = F.width_px, F.height_px
    one = float(F.pct_h_to_px(1.0))
    # 画角は原画の境界と一致し、各辺をシーン座標へ写す
    draw.rect(img, 0, 0, W, Hh, "magenta", 8)
    draw.text(img, 20, 20, "frame: X_H [%.3f, %.3f]  Z_H [%.3f, %.3f]   (1%% of image height = %.2f px = %.5f H)"
              % (F.x_left, F.x_right, F.z_bottom, F.z_top, one, float(F.pct_h_to_H(1.0))), "magenta", 4, bg="white", bg_alpha=0.85)
    # 下辺と左辺に H 単位の目盛
    for k in range(-8, 14):
        xh = k * 0.1
        x, _ = F.H_to_px(xh, 0)
        if 0 <= x <= W:
            big = (k % 5 == 0)
            draw.line(img, (x, Hh - (60 if big else 30)), (x, Hh), "magenta", 4 if big else 2)
            if big:
                draw.text(img, x + 6, Hh - 70, "X=%.1fH" % xh, "magenta", 3, bg="white", bg_alpha=0.8, anchor="lb")
    for k in range(-3, 12):
        zh = k * 0.1
        _, y = F.H_to_px(0, zh)
        if 0 <= y <= Hh:
            big = (k % 5 == 0)
            draw.line(img, (0, y), (60 if big else 30, y), "magenta", 4 if big else 2)
            if big:
                draw.text(img, 70, y, "Z=%.1fH" % zh, "magenta", 3, bg="white", bg_alpha=0.8, anchor="lm")
    # Z=0 の波谷線、Z=H の波頂線、X=0 の波頂鉛直線
    _, y0 = F.H_to_px(0, 0)
    _, y1 = F.H_to_px(0, 1)
    x0, _ = F.H_to_px(0, 0)
    draw.hline(img, float(y0), "cyan", 5)
    draw.text(img, W - 20, float(y0) - 10, "Z=0 trough water level (74.7% from top)", "cyan", 4, bg="black", bg_alpha=0.6, anchor="rb")
    draw.hline(img, float(y1), "yellow", 4, dash=(30, 20))
    draw.text(img, W - 20, float(y1) + 10, "Z=H crest level (8.7% from top)", "yellow", 4, bg="black", bg_alpha=0.6, anchor="rt")
    draw.vline(img, float(x0), "lime", 5)
    draw.text(img, float(x0) + 12, Hh - 110, "X=0 crest plumb line (38.2% from left)", "lime", 4, bg="black", bg_alpha=0.6, anchor="lb")
    # 特徴点
    info = {"S1_crest": ("S1 crest 38.2/8.7 -> (0, 1.000H)", (40, -60)),
            "S2_inner_arc_deepest": ("S2 inner-arc deepest 39.5/46.3 -> (+0.029, 0.430H)", (60, 30)),
            "S6_claw_rightmost": ("S6 claw right-most 59.2/33.0 -> (+0.473, 0.632H)", (60, -40))}
    for name, (lp, tp) in frame.SPEC_LANDMARKS_PCT.items():
        c = [float(v) for v in F.pct_to_px(lp, tp)]
        draw.circle(img, c, 2 * one, "red", fill=False, width=4)
        draw.circle(img, c, one, "red", fill=False, width=3)
        draw.marker(img, c, "+", 3 * one, "red", 3, outline="white")
        draw.text(img, c[0] + info[name][1][0], c[1] + info[name][1][1], info[name][0], "red", 4, bg="white", bg_alpha=0.85,
                  anchor="l" + ("b" if info[name][1][1] < 0 else "t"))
    # S6 の構成線：波頂から爪先端へ、水平から下向き 38 度
    c1 = [float(v) for v in F.pct_to_px(38.2, 8.7)]
    c6 = [float(v) for v in F.pct_to_px(59.2, 33.0)]
    draw.line(img, c1, c6, "orange", 3, dash=(24, 16))
    draw.text(img, 20, 80, "red rings: radius 1% and 2% of image height around each spec landmark", "red", 4, bg="white", bg_alpha=0.85)
    imgio.save_png(os.path.join(out_dir, "landmarks_overlay.png"), img)
    imgio.save_png(os.path.join(out_dir, "landmarks_overlay_1600.png"), draw.fit_width(img, 1600))

    # 原画の清浄な切り抜き。拡大後に細い印を描き、原画を見えるまま保つ。
    crops = {"S1_crest": "crop_S1_crest.png", "S2_inner_arc_deepest": "crop_S2_inner_arc.png",
             "S6_claw_rightmost": "crop_S6_claw_tip.png"}
    probe_of = {"S1_crest": "S1_probe", "S2_inner_arc_deepest": "S2_probe", "S6_claw_rightmost": "S6_probe"}
    for name, fn in crops.items():
        lp, tp = frame.SPEC_LANDMARKS_PCT[name]
        cx, cy = [float(v) for v in F.pct_to_px(lp, tp)]
        hw, hh = 10.0 * one, 7.5 * one                       # +-10 % x +-7.5 % of image height
        v = draw.View(painting, cx - hw, cy - hh, cx + hw, cy + hh, scale=3.0, method="bilinear")
        c = v.to_view((cx, cy))
        r1 = v.length(one)
        # 1 % grid (thin) centred on the landmark
        for k in range(-10, 11):
            a = 0.7 if k % 5 == 0 else 0.35                 # mid gray shows on the pale sky and on the dark water
            draw.vline(v.img, c[0] + k * r1, "gray", 1, alpha=a)
            draw.hline(v.img, c[1] + k * r1, "gray", 1, alpha=a)
        draw.circle(v.img, c, r1, "red", fill=False, width=2)
        draw.circle(v.img, c, 2 * r1, "red", fill=False, width=2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            draw.line(v.img, (c[0] + dx * 0.25 * r1, c[1] + dy * 0.25 * r1), (c[0] + dx * 3 * r1, c[1] + dy * 3 * r1), "red", 2)
        if name == "S1_crest" or name == "S2_inner_arc_deepest":
            xv = v.to_view((float(F.H_to_px(0, 0)[0]), cy))[0]
            draw.vline(v.img, xv, "lime", 2, dash=(12, 8))
        if name == "S1_crest":
            yv = v.to_view((cx, float(F.H_to_px(0, 1)[1])))[1]
            draw.hline(v.img, yv, "yellow", 2, dash=(12, 8))
        if name == "S1_crest" and "S1_probe" in probes:
            xa, xb = probes["S1_probe"]["plateau_x_px_range_within_2px"]
            yb = probes["S1_probe"]["y_px"] - 5.0
            pa, pb = v.to_view((xa, yb)), v.to_view((xb, yb))
            draw.line(v.img, pa, pb, "cyan", 2)
            draw.line(v.img, (pa[0], pa[1] - 8), (pa[0], pa[1] + 8), "cyan", 2)
            draw.line(v.img, (pb[0], pb[1] - 8), (pb[0], pb[1] + 8), "cyan", 2)
            draw.text(v.img, pa[0], pa[1] - 12, "plateau: outline top within 2 px of its highest row", "cyan", 2,
                      bg="black", bg_alpha=0.7, anchor="lb")
        pk = probe_of.get(name)
        if pk and pk in probes:
            pp = v.to_view((probes[pk]["x_px"], probes[pk]["y_px"]))
            draw.marker(v.img, pp, "x", 14, "cyan", 2, outline="black")
            draw.text(v.img, 10, v.img.shape[0] - 10, "cyan x = rough probe (%.1f, %.1f) px = %.2f%% / %.2f%%"
                      % (probes[pk]["x_px"], probes[pk]["y_px"], probes[pk]["left_pct"], probes[pk]["top_pct"]),
                      "cyan", 2, bg="black", bg_alpha=0.7, anchor="lb")
        draw.text(v.img, 10, 10, "%s  spec %.1f%% / %.1f%% = px (%.1f, %.1f)\nred rings r = 1%% and 2%% of image height; grid = 1%% (%.2f px); zoom 3x"
                  % (name, lp, tp, cx, cy, one), "red", 2, bg="white", bg_alpha=0.85)
        imgio.save_png(os.path.join(out_dir, fn), v.img)
    return img


# ---------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--quick", action="store_true", help="フル解像度 PNG の往復保存検査を省略")
    args = bootstrap.parse_args(ap)
    out_dir = paths.step1_dir("foundation")
    log("基礎自己検証  Blender=%s  出力=%s" % (bootstrap.blender_version(), out_dir))
    check("bootstrap.src_on_sys_path", bootstrap.add_src_to_path() in sys.path,
          "src=%s ; PYTHONPATH env var present (informational, never set by us): %s" % (bootstrap.SRC_DIR, "PYTHONPATH" in os.environ))
    FACTS["PYTHONPATH_present_in_env"] = "PYTHONPATH" in os.environ
    check("bootstrap.script_args", bootstrap.script_args(["blender", "-b", "--", "--a", "1"]) == ["--a", "1"]
          and bootstrap.script_args(["blender"]) == [], "引数は '--' より後")
    expected_project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    expected_repository = os.path.dirname(os.path.dirname(expected_project))
    check("paths.project_root", paths.norm(paths.PROJECT_ROOT).lower() == paths.norm(expected_project).lower()
          and paths.norm(paths.RESEARCH_ROOT).lower() == paths.norm(expected_repository).lower(), paths.norm(paths.PROJECT_ROOT))
    for d in ("target", "target/candidates/a", "target/candidates/b", "results/step1_prepare", "docs/records", "tests/fixtures"):
        check("skeleton.dir.%s" % d, os.path.isdir(os.path.join(paths.PROJECT_ROOT, d)), "")
    with bootstrap.Timer("frame"):
        test_frame()
    test_config()
    with bootstrap.Timer("imgio"):
        painting = test_imgio(out_dir, args.quick)
    with bootstrap.Timer("draw"):
        test_draw(out_dir)
    with bootstrap.Timer("plot"):
        test_plot(out_dir)
    with bootstrap.Timer("cam_print"):
        test_cam_print(out_dir, args.skip_render)
    with bootstrap.Timer("probes"):
        probes = rough_probes(painting)
        FACTS["rough_probes"] = probes
    with bootstrap.Timer("overlay"):
        make_overlay(painting, out_dir, probes)
    n_fail = sum(1 for c in CHECKS if not c["ok"])
    report = {"blender": bootstrap.blender_version(), "python": sys.version.split()[0], "numpy": np.__version__,
              "n_checks": len(CHECKS), "n_fail": n_fail, "checks": CHECKS, "facts": FACTS}
    paths.write_json(os.path.join(out_dir, "selftest_report.json"), report)
    log("集計：%d 件検証、%d 件失敗" % (len(CHECKS), n_fail))
    for c in CHECKS:
        if not c["ok"]:
            log("失敗：%s | %s" % (c["name"], c["detail"]))
    bootstrap.finish(n_fail == 0, "selftest_foundation")


if __name__ == "__main__":
    main()
