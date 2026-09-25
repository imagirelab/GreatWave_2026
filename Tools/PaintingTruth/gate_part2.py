# -*- coding: utf-8 -*-
"""編号23 第2部：Unity 較正門の測定と M1 Revision01 基線差の報告。

前提: Unity の AF23CalibrationGate.RunAll が Unity/Build/ArtFirst/23 に描画を書き出していること。
使い方（リポジトリ根で）:
    py -3.10 Tools/PaintingTruth/gate_part2.py

1) 世界標識 5 点: 描画の円板の重心（被覆率の重み付き）と numpy 投影（truthlib.project_world）の差 ≤0.5 px。
   標識は点灯成分の組（色）で見分け、numpy の予測位置は探索に使わない。
2) 平塗り色区: Unity の sRGB 経路で描いた色区の中央値（3 px ではなく 6 px 内側）と調色板の ΔE00 < 0.5。
   線形 RT に描いた対照（sRGB 符号化が抜ける誤り）も測って記録する。
3) 第1部の自己テスト（selftest.json）と合わせて 23_gate.json を書く（all_pass）。門を回した時の真値
   （targets/truth_manifest.json と painting_truth.json）の SHA-256 も書き、evaluate.py はそれが今と違えば暫定にする。
   較正門は評価器の測り方と真値の精度を見るもので、真値の完全性は判定しない（scope_ja、records.truth_completeness）。
4) M1 Revision01 の基線を評価器（ID モード）にかけ、23_baseline_M1R01_* を Docs/Evidence/ArtFirst/23 へ置く。
5) 編号23 の metrics.json・run.json へ第2部を入れる（evaluate.merge_step23_part2）。
"""
import datetime
import json
import math
import os
import platform
import shutil
import subprocess
import sys

import cv2
import numpy as np

import truthlib as T
import evaluate as E

BUILD = T.repo_abs("Unity/Build/ArtFirst/23")
EVID = T.repo_abs("Docs/Evidence/ArtFirst/23")
GATE_DEF = os.path.join(T.HERE, "unity_gate.json")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def b(p):
    return os.path.join(BUILD, p)


# ---------------------------------------------------------------- 標識
def measure_markers(spec, gdef, png, unity_markers):
    img = T.imread_rgb(png).astype(np.float64) / 255.0
    on = img > 0
    code = on[..., 0] * 1 + on[..., 1] * 2 + on[..., 2] * 4
    H, W = code.shape
    yy, xx = np.mgrid[0:H, 0:W]
    um = {m["id"]: m for m in unity_markers}
    out = []
    for m in gdef["markers"]:
        c = int(round(m["color"][0])) + 2 * int(round(m["color"][1])) + 4 * int(round(m["color"][2]))
        msk = code == c
        n_comp = cv2.connectedComponents(msk.astype(np.uint8), connectivity=8)[0] - 1
        w = img.max(-1) * msk
        s = float(w.sum())
        cx = float((w * xx).sum() / s) if s > 0 else float("nan")
        cy = float((w * yy).sum() / s) if s > 0 else float("nan")
        x, y, z, _, _ = T.project_world(spec, m["world"])
        u = um[m["id"]]
        ux = float(u["unityDisplayPx"]["x"])
        uy = float(u["unityDisplayPx"]["y"])
        touches_edge = bool(msk[0, :].any() or msk[-1, :].any() or msk[:, 0].any() or msk[:, -1].any())
        out.append({
            "id": m["id"], "world": m["world"], "depth_m": round(z, 5),
            "render_centroid_px": [round(cx, 4), round(cy, 4)],
            "numpy_projection_px": [round(x, 4), round(y, 4)],
            "diff_px": round(math.hypot(cx - x, cy - y), 4),
            "diff_xy_px": [round(cx - x, 4), round(cy - y, 4)],
            "unity_math_px": [round(ux, 4), round(uy, 4)],
            "unity_math_vs_numpy_px": round(math.hypot(ux - x, uy - y), 5),
            "coverage_sum_px2": round(s, 3), "expected_area_px2": round(math.pi * m["radius_px"] ** 2, 3),
            "components": int(n_comp), "touches_edge": touches_edge,
        })
    return out


# ---------------------------------------------------------------- 色区
def measure_patches(gdef, palette, png):
    img = T.imread_rgb(png)
    lab = T.srgb8_to_lab(img)
    mg = int(gdef["patch_margin_px"])
    out = []
    for p in gdef["patches"]:
        x0, y0, x1, y1 = p["rect_px"]
        m = np.zeros(img.shape[:2], bool)
        m[y0 + mg:y1 - mg, x0 + mg:x1 - mg] = True
        med = T.median_lab(lab, m)
        lab_in = T.srgb8_to_lab(np.array(p["srgb8"], np.float64))
        if p["name"] in palette:
            ref, ref_kind = np.array(palette[p["name"]]["lab"]), "palette.json の lab（調色板の値）"
        else:
            ref, ref_kind = lab_in, "入力 8bit sRGB の lab"
        px = img[m].astype(int)
        full = np.zeros_like(m)
        full[y0:y1, x0:x1] = True
        out.append({
            "name": p["name"], "srgb8_input": p["srgb8"], "rect_px": p["rect_px"],
            "render_median_lab": [round(float(v), 4) for v in med], "reference_lab": [round(float(v), 4) for v in ref],
            "reference_kind": ref_kind,
            "dE00_vs_reference": round(float(T.ciede2000(med, ref)), 4),
            "dE00_vs_input_srgb8": round(float(T.ciede2000(med, lab_in)), 4),
            "max_abs_8bit_diff": int(np.abs(px - np.array(p["srgb8"])[None, :]).max()),
            "distinct_colors_inside": int(len(np.unique(px, axis=0))),
            "nonblack_pixels_in_rect": int((img[full].sum(-1) > 0).sum()), "rect_pixels": int(full.sum()),
        })
    return out


# ---------------------------------------------------------------- 図
def fig_markers(spec, png, res, path):
    img = T.imread_rgb(png)
    H, W = img.shape[:2]
    canvas = (img.astype(np.float32) * 0.9 + 18).clip(0, 255).astype(np.uint8)
    fm = T.FrameMap(spec)
    canvas[:, :fm.x0] //= 3
    canvas[:, fm.x1 + 1:] //= 3
    # 各標識の拡大（25×25 px を 8 倍）を、標識のない中段に並べる
    Z, half = 8, 12
    tile = (2 * half + 1) * Z
    y_top = 420
    for k, r in enumerate(res):
        cx, cy = r["render_centroid_px"]
        nx, ny = r["numpy_projection_px"]
        ix, iy = int(round(nx)), int(round(ny))
        x0, y0 = ix - half, iy - half
        crop = np.zeros((2 * half + 1, 2 * half + 1, 3), np.uint8)
        sx0, sy0 = max(0, x0), max(0, y0)
        sx1, sy1 = min(W, x0 + 2 * half + 1), min(H, y0 + 2 * half + 1)
        crop[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = img[sy0:sy1, sx0:sx1]
        big = cv2.resize(crop, (tile, tile), interpolation=cv2.INTER_NEAREST)
        for g in range(0, tile + 1, Z):
            big[:, min(g, tile - 1)] = (big[:, min(g, tile - 1)] // 2 + 40)
            big[min(g, tile - 1), :] = (big[min(g, tile - 1), :] // 2 + 40)

        def to_big(px, py):
            return int(round((px - x0 + 0.5) * Z)), int(round((py - y0 + 0.5) * Z))
        bx, by = to_big(nx, ny)
        cv2.line(big, (bx - 10, by - 10), (bx + 10, by + 10), (0, 255, 255), 2, cv2.LINE_AA)
        cv2.line(big, (bx - 10, by + 10), (bx + 10, by - 10), (0, 255, 255), 2, cv2.LINE_AA)
        rx, ry = to_big(cx, cy)
        cv2.line(big, (rx - 16, ry), (rx + 16, ry), (255, 255, 255), 1, cv2.LINE_AA)
        cv2.line(big, (rx, ry - 16), (rx, ry + 16), (255, 255, 255), 1, cv2.LINE_AA)
        ox = 380 + k * (tile + 24)
        canvas[y_top:y_top + tile, ox:ox + tile] = big
        cv2.rectangle(canvas, (ox - 1, y_top - 1), (ox + tile, y_top + tile), (200, 200, 200), 1)
        lbl = "%s  d=%.3f px" % (r["id"].split("_")[0], r["diff_px"])
        cv2.putText(canvas, lbl, (ox, y_top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        # 全体図の上で標識と拡大枠を結ぶ
        cv2.circle(canvas, (ix, iy), 16, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(canvas, r["id"].split("_")[0], (ix + 18, iy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)
    mx = max(r["diff_px"] for r in res)
    cv2.putText(canvas, "23 calibration gate: Unity-rendered markers (PaintingCam v1, 1920x1080, MSAA 8x) vs numpy projection",
                (380, 790), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, "insets 8x (25x25 px): white + = render centroid, cyan x = numpy projection.  max diff %.3f px (threshold 0.5)" % mx,
                (380, 818), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    T.imwrite(path, canvas)


def fig_patches(png, ctrl_png, res, ctrl, path):
    a = T.imread_rgb(png)
    c = T.imread_rgb(ctrl_png)
    canvas = np.full((1080, 1920, 3), 24, np.uint8)
    canvas[40:580, 0:960] = cv2.resize(a, (960, 540), interpolation=cv2.INTER_AREA)
    canvas[40:580, 960:1920] = cv2.resize(c, (960, 540), interpolation=cv2.INTER_AREA)
    for off, rr in ((0, res), (960, ctrl)):
        for r in rr:
            x0, y0, x1, y1 = r["rect_px"]
            tx, ty = off + x0 // 2 + 6, 40 + y0 // 2 + 22
            L = r["render_median_lab"][0]
            col = (0, 0, 0) if L > 55 else (255, 255, 255)
            cv2.putText(canvas, r["name"], (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
            cv2.putText(canvas, "dE00 %.3f" % r["dE00_vs_reference"], (tx, ty + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
            cv2.putText(canvas, "rgb %d,%d,%d" % tuple(int(round(v)) for v in _lab_to_rgb(r["render_median_lab"])),
                        (tx, ty + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)
    cv2.putText(canvas, "Unity sRGB path (gate): sRGB RT, MSAA 8x -> resolve -> RGB24 -> PNG", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, "control (record only): same scene into a Linear RT (sRGB encode missing)", (970, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    y = 640
    lines = ["23 calibration gate: flat colour patch read-back (Linear colour space project, Unity 6000.4.3f1, D3D11)",
             "gate path max dE00 vs palette = %.3f (threshold < 0.5); vs input 8-bit sRGB = %.3f; max 8-bit diff = %d" % (
                 max(r["dE00_vs_reference"] for r in res), max(r["dE00_vs_input_srgb8"] for r in res), max(r["max_abs_8bit_diff"] for r in res)),
             "control (Linear RT) dE00 range %.1f .. %.1f  -> the check detects a missing sRGB encode" % (
                 min(r["dE00_vs_reference"] for r in ctrl), max(r["dE00_vs_reference"] for r in ctrl)),
             "palette dE00 > 0 on the gate path is the 8-bit rounding of palette.json lab (same as the part-1 numpy flat patch)."]
    for s in lines:
        cv2.putText(canvas, s, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
        y += 40
    T.imwrite(path, canvas)


def _lab_to_rgb(lab):
    return T.lab_to_srgb8(np.array(lab, np.float64))


def fig_baseline_blend(truth, render_png, ids_png, idmap, path):
    rgb = T.imread_rgb(render_png)
    fm = truth.fmap
    img = (0.5 * rgb.astype(np.float32) + 0.5 * truth.disp_rgb.astype(np.float32)).astype(np.uint8)
    img[:, :fm.x0] //= 4
    img[:, fm.x1 + 1:] //= 4
    # 真値（包絡版の主浪 5 区間・71 の空域境界）＝シアン、M1 Revision01 の空境界（ID 画像から）＝赤
    for s in truth.outline["envelope"]["segments"]:
        P = np.round(np.array(s["points_display"])).astype(np.int32)
        cv2.polylines(img, [P.reshape(-1, 1, 2)], False, (0, 255, 255), 2, cv2.LINE_AA)
    reg = E.render_regions_ids(truth, T.imread_rgb(ids_png), idmap)
    rp = T.boundary_points(reg["sky"], truth.spec, fm)
    xi = np.clip(np.round(rp[:, 0]).astype(int), 0, fm.W - 1)
    yi = np.clip(np.round(rp[:, 1]).astype(int), 0, fm.H - 1)
    img[yi, xi] = (255, 40, 40)
    cv2.putText(img, "23 baseline: M1 Revision01 (Unity, PaintingCam v1) 50% over Met JP1847", (170, 1040),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, "cyan = target envelope outline 78/130/131/132/72,  red = M1 Revision01 sky boundary", (170, 1066),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    T.save_png_reserved(path, img, [(0, 255, 255), (255, 40, 40), (255, 255, 255)])


# ---------------------------------------------------------------- 本体
def main():
    spec = T.load_spec()
    gdef = T.load_json(GATE_DEF)
    palette = T.load_json(os.path.join(T.TARGET_DIR, "palette.json"))["palette"]
    ur = T.load_json(b("af23_gate_unity_report.json"))
    br = T.load_json(b("af23_baseline_unity_report.json"))
    problems = []
    # 入力の一致（Unity が今の painting_truth.json / unity_gate.json で描いたか、色区の色が調色板と同じか）
    if ur["truthJsonSha256"] != T.sha256_file(T.SPEC_PATH):
        problems.append("Unity が読んだ painting_truth.json が現在のファイルと違う")
    if ur["gateJsonSha256"] != T.sha256_file(GATE_DEF):
        problems.append("Unity が読んだ unity_gate.json が現在のファイルと違う")
    for p in gdef["patches"]:
        if p["name"] in palette and list(p["srgb8"]) != list(palette[p["name"]]["srgb8"]):
            problems.append("色区 %s の srgb8 が palette.json と違う" % p["name"])
    if ur["colorSpace"] != "Linear":
        problems.append("色空間が Linear ではない: %s" % ur["colorSpace"])

    # 1) 標識
    mk = measure_markers(spec, gdef, b("af23_markers.png"), ur["markers"])
    mk_n = measure_markers(spec, gdef, b("af23_markers_nomsaa.png"), ur["markers"])
    thr = float(gdef["marker_threshold_px"])
    mk_ok = all(r["diff_px"] <= thr and r["components"] == 1 and not r["touches_edge"] for r in mk) and not problems
    view, proj = T.cam_matrices(spec)
    uv = np.array(ur["worldToCameraMatrix"]).reshape(4, 4)
    up = np.array(ur["projectionMatrix"]).reshape(4, 4)
    eu = T.cam_euler_deg(spec)
    ue = [ur["cameraEuler"][k] for k in "xyz"]

    # 2) 色区
    pt = measure_patches(gdef, palette, b("af23_flat_patch.png"))
    pc = measure_patches(gdef, palette, b("af23_flat_patch_linear_rt_control.png"))
    pthr = float(gdef["patch_threshold_dE00"])
    pt_ok = all(r["dE00_vs_reference"] < pthr and r["nonblack_pixels_in_rect"] == r["rect_pixels"] for r in pt) and not problems

    # 3) 第1部（自己テスト）と合わせた較正門
    S = T.load_json(os.path.join(EVID, "selftest.json"))
    items = {
        "sharma2005_ciede2000": {"value": S["sharma2005_ciede2000"]["max_abs_error"], "threshold": 1e-4,
                                 "pass": S["sharma2005_ciede2000"]["pass"], "source": "selftest.json（第1部）"},
        "self_zero": {"value": S["self_zero"]["max_over_all_contours_and_colors"], "threshold": 0.0,
                      "pass": S["self_zero"]["pass"], "source": "selftest.json（第1部）"},
        "synthetic_shift_3px": {"value": S["synthetic_shift"]["checked"], "expected": 3.0, "tolerance": 0.1,
                                "pass": S["synthetic_shift"]["pass"], "source": "selftest.json（第1部）"},
        "flat_patch_numpy_dE00": {"value": max(S["flat_patch"]["deltaE00"].values()), "threshold": 0.5,
                                  "pass": S["flat_patch"]["pass"], "source": "selftest.json（第1部、numpy の合成画像）"},
        "canny_support": {"value": S["canny_support"]["overall_claws_ratio"], "threshold": 0.95,
                          "pass": S["canny_support"]["pass"], "source": "selftest.json（第1部）"},
        "unity_markers_0p5px": {
            "value_max_px": max(r["diff_px"] for r in mk), "threshold_px": thr, "pass": bool(mk_ok), "per_marker": mk,
            "source": "gate_part2.py（第2部）",
            "note_ja": "Unity 6000.4.3f1（Editor batchmode、Direct3D11、Linear 色空間）で painting_truth.json の PaintingCam v1 を組み、"
                       "画像面に平行な半径 8 px の円板 5 枚を線形 RT・MSAA 8x・1920×1080 で描いた。被覆率で重み付けた重心を、"
                       "numpy の投影（truthlib.project_world、画素中心 = 整数）と比べた。"},
        "unity_flat_patch_dE00": {
            "value_max": max(r["dE00_vs_reference"] for r in pt), "threshold": pthr, "pass": bool(pt_ok), "per_patch": pt,
            "source": "gate_part2.py（第2部）",
            "note_ja": "Linear 色空間で、Color 型のプロパティ（8bit sRGB 値）を無光照で sRGB の RT（MSAA 8x → 解決 → RGB24 → PNG）へ描いた。"
                       "基線の色画像と同じ経路。色区の縁から 6 px 内側の中央値を調色板の lab（灰は入力値）と比べた。"},
    }
    support = {
        "camera_vs_unity_records": {"pass": S["camera_crosscheck"]["pass"], "euler_max_diff_deg": S["camera_crosscheck"]["euler_max_diff_deg"],
                                    "fuji_apex_diff_px": S["camera_crosscheck"]["fuji_apex_diff_px"], "source": "selftest.json（第1部、補助）"},
    }
    records = {
        "unity_markers_no_msaa": {"value_max_px": max(r["diff_px"] for r in mk_n), "per_marker": mk_n,
                                  "note_ja": "MSAA なし（1 標本）で描いた同じ標識。記録のみ。"},
        "unity_math_vs_numpy_px": {"value_max_px": max(r["unity_math_vs_numpy_px"] for r in mk),
                                   "note_ja": "Unity の Camera.WorldToViewportPoint（float 計算）を表示 px にした値と numpy 投影の差。描画を通さない数式だけの照合。"},
        "camera_matrices": {
            "worldToCamera_max_abs_diff": float(np.abs(uv - view).max()), "projection_max_abs_diff": float(np.abs(up - proj).max()),
            "unity_euler_deg": ue, "numpy_euler_deg": [round(v, 6) for v in eu],
            "euler_max_diff_deg": float(max(abs(((a - c + 180) % 360) - 180) for a, c in zip(eu, ue))),
            "note_ja": "Unity の worldToCameraMatrix / projectionMatrix（OpenGL 規約）と truthlib.cam_matrices の差（float と float64 の差）。"},
        "flat_patch_linear_rt_control": {
            "value_min": min(r["dE00_vs_reference"] for r in pc), "value_max": max(r["dE00_vs_reference"] for r in pc), "per_patch": pc,
            "note_ja": "対照：同じ色区を線形（sRGB 符号化なし）の RT に描いた場合。暗い色ほど大きくずれ、較正門がこの誤りを検出できることを示す。記録のみ。"},
        "truth_completeness": {
            "truth": {k: v for k, v in S["truth_completeness_record"]["truth"].items() if k != "largest_sky_components"},
            "control_without_manual_barriers": {k: v for k, v in S["truth_completeness_record"]["control_without_manual_barriers"].items()
                                                if k != "largest_sky_components"},
            "white_rule": S["truth_completeness_record"]["white_rule"],
            "source": "selftest.json（第1部、truth_completeness_record。塊の一覧もそこにある）",
            "note_ja": "記録のみ。真値が原画の水の面を漏れなく含むか（完全性）の目安で、較正門の合否には入れない。"},
    }
    all_pass = all(v["pass"] for v in items.values()) and all(v["pass"] for v in support.values())
    unity = {"version": ur["unity"], "device": ur["device"], "graphics_api": ur["graphicsApi"], "color_space": ur["colorSpace"],
             "method_ja": ur["method"], "gate_render_seconds": ur["seconds"], "baseline_render_seconds": br["seconds"]}
    G = {
        "schema": "GreatWave.Step23.gate/1",
        "number": "23",
        "generated_utc": _now(),
        "all_pass": bool(all_pass),
        "gate_complete": True,
        "verdict_ja": ("較正門の全項目が合格した（第1部 5 項目＋補助 1、第2部 Unity 2 項目）。編号26 の前提を満たす。" if all_pass else
                       "較正門に不合格の項目がある。しきい値は変えずに報告する。編号26 は開始できない。"),
        "scope_ja": ("較正門が確かめるのは、評価器の測り方（CIEDE2000 の式、輪郭距離、平行移動、画面写像、Unity の投影と色の経路）と、"
                     "真値の折れ線が原画のエッジに乗っているか（Canny 支持率＝精度）である。真値が原画の水の面を漏れなく含むか（完全性）は"
                     "判定しない。v0 の真値は唇の右端の爪群が空として抜けていたが、抜けた所の境界も藍線に沿うため Canny 支持率は 98.56% で"
                     "合格していた。完全性は records.truth_completeness（記録のみ）と、人が拡大図で確かめることで見る。"),
        "truth_manifest_sha256": T.sha256_file(os.path.join(T.TARGET_DIR, "truth_manifest.json")),
        "painting_truth_sha256": T.sha256_file(T.SPEC_PATH),
        "truth_sha256_ja": "この較正門を回した時の真値。evaluate.py はこの 2 つが今のファイルと違えば provisional: false を出さない。",
        "problems": problems,
        "items": items,
        "support": support,
        "records": records,
        "unity": unity,
        "evidence_kind_ja": "Unity Editor（batchmode）の PC オフスクリーン描画と numpy/OpenCV 測定。PC ビルド・HMD 実機の結果ではない。",
    }
    T.save_json(os.path.join(EVID, "23_gate.json"), G)
    fig_markers(spec, b("af23_markers.png"), mk, os.path.join(EVID, "23_gate_markers.png"))
    fig_patches(b("af23_flat_patch.png"), b("af23_flat_patch_linear_rt_control.png"), pt, pc, os.path.join(EVID, "23_gate_flat_patch.png"))

    # 4) M1 Revision01 の基線差（評価器 v0、ID モード）
    if not br.get("passed") or not br.get("dependenciesUnchanged"):
        raise SystemExit("基線描画の検査が不合格（af23_baseline_unity_report.json）")
    ev_dir = b("eval_M1R01")
    cmd = [sys.executable, os.path.join(T.HERE, "evaluate.py"), "--render", b("af23_baseline_M1R01.png"),
           "--ids", b("af23_baseline_M1R01_ids.png"), "--idmap", b("af23_baseline_M1R01_idmap.json"),
           "--out-dir", ev_dir, "--name", "23_baseline_M1R01"]
    subprocess.run(cmd, check=True, cwd=T.REPO)
    shutil.copyfile(os.path.join(ev_dir, "metrics.json"), os.path.join(EVID, "23_baseline_M1R01_metrics.json"))
    ov = T.imread_rgb(os.path.join(ev_dir, "23_baseline_M1R01_overlay.png"))
    T.save_png_reserved(os.path.join(EVID, "23_baseline_M1R01_overlay.png"), ov,
                        [(0, 255, 255), (60, 230, 60), (255, 220, 0), (255, 40, 40), (255, 60, 60), (255, 255, 255), (0, 0, 0)])
    shutil.copyfile(b("af23_baseline_M1R01.png"), os.path.join(EVID, "23_baseline_M1R01_render.png"))
    truth = E.Truth()
    fig_baseline_blend(truth, b("af23_baseline_M1R01.png"), b("af23_baseline_M1R01_ids.png"),
                       T.load_json(b("af23_baseline_M1R01_idmap.json")), os.path.join(EVID, "23_baseline_M1R01_blend.png"))

    # 5) 実行記録と編号23 の metrics.json・run.json への統合
    ins = [T.SPEC_PATH, GATE_DEF, os.path.join(T.TARGET_DIR, "palette.json"), os.path.join(T.TARGET_DIR, "truth_manifest.json"),
           os.path.join(EVID, "selftest.json"),
           os.path.join(T.HERE, "gate_part2.py"), os.path.join(T.HERE, "evaluate.py"), os.path.join(T.HERE, "truthlib.py"),
           os.path.join(T.HERE, "run_af23_part2.ps1"),
           T.repo_abs("Unity/Assets/GreatWave/ArtFirst/Editor/AF23CalibrationGate.cs"),
           T.repo_abs("Unity/Assets/GreatWave/ArtFirst/Editor/AF23GateFlat.shader"),
           T.repo_abs("Unity/Assets/GreatWave/Scenes/Tests/M1_StaticComposition_Revision01.unity")]
    outs = [os.path.join(EVID, f) for f in ("23_gate.json", "23_gate_markers.png", "23_gate_flat_patch.png", "23_baseline_M1R01_render.png",
                                           "23_baseline_M1R01_overlay.png", "23_baseline_M1R01_blend.png", "23_baseline_M1R01_metrics.json")]
    build_files = sorted(f for f in os.listdir(BUILD) if os.path.isfile(b(f)) and not f.endswith(".log"))
    run_part2 = {
        "generated_utc": _now(),
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/PaintingTruth/run_af23_part2.ps1",
                     "（内訳）py -3.10 Tools/PaintingTruth/evaluate.py --selftest --out-dir Docs/Evidence/ArtFirst/23",
                     "（内訳）E:\\6000.4.3f1\\Editor\\Unity.exe -batchmode -projectPath Unity -executeMethod "
                     "GreatWave.ArtFirst.EditorTools.AF23CalibrationGate.RunAll -logFile Unity/Build/ArtFirst/23/unity_af23_gate.log -quit",
                     "（内訳）py -3.10 Tools/PaintingTruth/gate_part2.py",
                     "（gate_part2.py の中）py -3.10 " + " ".join(T.repo_rel(c) if os.path.isabs(c) and c.startswith(T.REPO) else c for c in cmd[1:])],
        "cwd": "リポジトリ根（G:/Unity/GreatWave_2026_Fresh）",
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                  "pillow": __import__("PIL").__version__, "os": platform.platform()},
        "unity": unity,
        "inputs": {T.repo_rel(p): T.sha256_file(p) for p in ins},
        "outputs": {T.repo_rel(p): T.sha256_file(p) for p in outs},
        "not_committed": {T.repo_rel(b(f)): {"sha256": T.sha256_file(b(f)), "bytes": os.path.getsize(b(f))} for f in build_files},
        "not_committed_ja": "Unity/Build/ArtFirst/23（Git 対象外）。Unity の生の描画・ID 画像（3840×2160）・Unity の報告 JSON・評価器の生出力。"
                            "run_af23_part2.ps1 で作り直せる。",
        "baseline_scene_dependencies_unchanged": br["dependenciesUnchanged"],
        "baseline_scene_sha256": br["sceneSha256"],
    }
    E.merge_step23_part2(EVID, run_part2)
    print("GATE all_pass=%s markers_max=%.4f px patches_max=%.4f dE00 problems=%s" % (
        all_pass, items["unity_markers_0p5px"]["value_max_px"], items["unity_flat_patch_dE00"]["value_max"], problems))
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
