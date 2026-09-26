# -*- coding: utf-8 -*-
"""番号23 原画基準の抽出（半自動）。入力は原画 Met_JP1847_DP130155.jpg（v0.2 から、3859×2594）と手入力の注記だけ。

使い方（リポジトリ根で）:
    py -3.10 Tools/PaintingTruth/extract.py [--evidence Docs/Evidence/ArtFirst/23]

出力:
    Tools/PaintingTruth/targets/            凍結する真値（被覆率 PNG、折れ線 JSON、調色板 JSON、線幅プロファイル、manifest）
    Tools/PaintingTruth/build/              再生成できる中間物（表示フレームの原画など。Git に入れない）
    Tools/PaintingTruth/unity_gate.json     平塗り色区の srgb8 を調色板に合わせて書き換える（sync_unity_gate_colors）
    <evidence>/23_*.png                     人が確かめるための 1920×1080 重ね図
    <evidence>/23_extract_record.json       v0.1 との差、障壁を 1 本ずつ外した場合の差、途切れの閉じの対照（記録のみ）
    <evidence>/23_line_width.json           線幅プロファイルの要約と、表示解像度で ±20% を判定できるかの記録
旧原画 Met_JP1847.jpg は v0.1 の真値を同じ規則で作り直して比べるためだけに読む（legacy_sky_v01）。
"""
import argparse
import datetime
import json
import math
import os
import re
import platform
import sys

import cv2
import numpy as np

import truthlib as T

VERSIONS = ("envelope", "claws")
SEG_BACKLOG = {
    "78": "左端から斜め上へ続く外形（B003-01）",
    "130": "左側の傾き（B003-02）",
    "131": "上側へのつながり（B003-03）",
    "132": "船側への曲がり（B003-04）",
    "72": "上側から下側へ続く内側輪郭（B002-03）",
}
PALETTE_ORDER = ["white", "mizuiro", "ai_mid", "ai_dark", "sky_top", "sky_bottom", "boat_ochre", "fuji_snow", "fuji_slope"]
PALETTE_JA = {
    "white": "白・生成り", "mizuiro": "水色", "ai_mid": "藍中", "ai_dark": "藍濃",
    "sky_top": "空上", "sky_bottom": "空下（水平線際）", "boat_ochre": "船の黄土",
    "fuji_snow": "富士の雪", "fuji_slope": "富士の山肌",
}


def lloyd(X, centers, iters=30):
    """決定的な Lloyd 反復（高解像度で画素数が多いので、距離は 50 万点ずつ計算する）。"""
    C = np.asarray(centers, np.float64).copy()
    for _ in range(iters):
        k = np.empty(len(X), np.int32)
        for s in range(0, len(X), 500000):
            d = ((X[s:s + 500000, None, :] - C[None, :, :]) ** 2).sum(-1)
            k[s:s + 500000] = d.argmin(1)
        newC = np.stack([X[k == j].mean(0) if np.any(k == j) else C[j] for j in range(len(C))])
        if np.allclose(newC, C, atol=1e-6):
            break
        C = newC
    return C


def classify(lab, C):
    X = lab.reshape(-1, 3).astype(np.float64)
    out = np.empty(len(X), np.int32)
    for k in range(0, len(X), 200000):
        d = ((X[k:k + 200000, None, :] - C[None]) ** 2).sum(-1)
        out[k:k + 200000] = d.argmin(1)
    return out.reshape(lab.shape[:2])


def ordered_outline(cov, fmap, spec, lm_disp, tol=None):
    """被覆率（空）から主浪の外周を順序付き折れ線で取る。4 倍に拡大して 0.5 で二値化し、輪郭追跡する。"""
    sig = float(spec["scoring"]["contour"]["boundary_smoothing_sigma_px"])
    f = cv2.GaussianBlur(cov.astype(np.float64), (0, 0), sig)
    hi = cv2.resize(f, (fmap.W * 4, fmap.H * 4), interpolation=cv2.INTER_LINEAR)
    water = (hi < 0.5).astype(np.uint8)
    cnts, _ = cv2.findContours(water, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    best = None
    for c in cnts:
        if len(c) < 200:
            continue
        P = (c[:, 0, :].astype(np.float64) + 0.5) / 4.0 - 0.5
        d, idx = T.nearest(lm_disp, P)
        tl = np.full(len(d), 3.0) if tol is None else np.asarray(tol, np.float64)
        score = (d / tl).max()
        if best is None or score < best[0]:
            best = (score, P, idx, d)
    score, P, idx, d = best
    if score > 1.0:
        raise RuntimeError("目印が輪郭から離れすぎています: " + str(np.round(d, 2)))
    n = len(P)
    order = list(idx)
    fwd = [(order[k + 1] - order[k]) % n for k in range(len(order) - 1)]
    if sum(fwd) > n:  # 逆向き
        P = P[::-1].copy()
        order = [n - 1 - i for i in order]
        fwd = [(order[k + 1] - order[k]) % n for k in range(len(order) - 1)]
    if sum(fwd) > n:
        raise RuntimeError("目印の順序が輪郭上で一致しません")
    path = [P[(order[0] + t) % n] for t in range(sum(fwd) + 1)]
    cuts = np.concatenate([[0], np.cumsum(fwd)])
    return np.array(path), cuts, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="Docs/Evidence/ArtFirst/23")
    args = ap.parse_args()
    spec = T.load_spec()
    man = T.load_manual()
    fmap = T.FrameMap(spec)
    ex = spec["extraction"]
    polys = man["polygons_ref"]
    os.makedirs(os.path.join(T.TARGET_DIR, "masks"), exist_ok=True)
    os.makedirs(T.BUILD_DIR, exist_ok=True)
    ev_dir = T.repo_abs(args.evidence)
    os.makedirs(ev_dir, exist_ok=True)

    ref_rgb, disp_rgb = T.painting_display(spec, fmap)
    T.imwrite(os.path.join(T.BUILD_DIR, "painting_display.png"), disp_rgb)
    lab_ref = T.srgb8_to_lab(ref_rgb)
    lab_disp = T.srgb8_to_lab(disp_rgb)

    # ---- 空（爪入り = 原画そのまま）と包絡（爪なし）
    fills = [polys["sky_fill_cartouche"]["points"], polys["sky_fill_signature"]["points"]]
    barriers = list(man.get("barriers_ref", {}).values())
    sky_claws = T.segment_sky(lab_ref, ex["sky"], fills, barriers)
    # 確認用の対照（真値には入れない）：v0.1 の真値（旧原画・旧規則で作り直したもの）、途切れの閉じと手動の障壁を外した空、
    # 手動の障壁を 1 本ずつ外した空。
    sky_v01_ref, sky_v01_legacy = legacy_sky_v01(spec, man, sky_claws.shape)
    p0 = dict(ex["sky"], barrier_dilate_ref_px=0)
    sky_no_barrier = T.segment_sky(lab_ref, p0, fills)
    record = extract_record(spec, man, lab_ref, fills, barriers, sky_claws, sky_no_barrier, sky_v01_ref, fmap)
    barrier_ref = T.barrier_lines_mask(sky_claws.shape, barriers)
    barrier_dist = cv2.distanceTransform((~barrier_ref).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    zone = T.poly_mask(sky_claws.shape, polys["claw_zone"]["points"])
    water_env = T.envelope_water(~sky_claws, zone, ex["envelope"])
    sky_env = T.fill_small_enclosed(~water_env, ex["sky"]["small_enclosed_area_ref_px"])
    q16 = lambda c: np.round(np.clip(c, 0.0, 1.0) * 65535.0) / 65535.0  # 保存形式（16bit）と同じ値で以後を計算する
    cov = {"claws": q16(T.ref_mask_to_cov(sky_claws, fmap)), "envelope": q16(T.ref_mask_to_cov(sky_env, fmap))}

    # ---- 調色板（参照解像度で色クラス → 表示フレームで収縮・中央値）
    seed = ex["palette_seed_lab"]
    names5 = ["white", "mizuiro", "mix", "ai_mid", "ai_dark"]
    mainzone = T.poly_mask(sky_claws.shape, polys["main_wave_palette_zone"]["points"])
    boat_left_roi = T.poly_mask(sky_claws.shape, polys["boat_left_roi"]["points"])
    sel = mainzone & ~sky_claws & ~boat_left_roi
    C = lloyd(lab_ref[sel].astype(np.float64), [seed[k] for k in names5])
    cls = classify(lab_ref, C)
    ochre = T.ochre_mask(lab_ref, sky_claws, ex["ochre"])
    fuji_zone = T.poly_mask(sky_claws.shape, polys["fuji_zone"]["points"])
    rows = np.arange(sky_claws.shape[0])[:, None]
    cols = np.arange(sky_claws.shape[1])[None, :]
    band = ex["sky_bands_ref"]
    top = (rows >= band["top_y"][0]) & (rows <= band["top_y"][1]) & (cols >= band["top_x"][0]) & (cols <= band["top_x"][1])
    bot = (rows >= band["bottom_y"][0]) & (rows <= band["bottom_y"][1])
    boats = {}
    for name, key in (("boat_left", "boat_left_roi"), ("boat_mid", "boat_mid_roi"), ("boat_fg", "boat_fg_roi")):
        boats[name] = T.boat_mask(ochre, polys[key]["points"], ex["boat"])
    region_ref = {
        "white": sel & (cls == 0) & ~ochre,
        "mizuiro": sel & (cls == 1) & ~ochre,
        "ai_mid": sel & (cls == 3),
        "ai_dark": sel & (cls == 4),
        "sky_top": sky_claws & top,
        "sky_bottom": sky_claws & bot,
        "boat_ochre": boats["boat_mid"] | boats["boat_fg"],
        "fuji_snow": fuji_zone & ~sky_claws & (cls == 0) & ~ochre,
        "fuji_slope": fuji_zone & ~sky_claws & ((cls == 3) | (cls == 4)),
    }
    er = int(spec["scoring"]["color"]["erosion_px"])
    label_img = np.zeros((fmap.H, fmap.W), np.uint8)
    palette = {}
    for i, name in enumerate(PALETTE_ORDER, start=1):
        m_disp = T.ref_mask_to_cov(region_ref[name], fmap) > 0.5
        m_disp[:, :fmap.x0] = False
        m_disp[:, fmap.x1 + 1:] = False
        label_img[m_disp] = i
        core = T.erode(m_disp, er)
        med = T.median_lab(lab_disp, core)
        med_ref = T.median_lab(lab_ref, region_ref[name])
        palette[name] = {
            "label_value": i,
            "name_ja": PALETTE_JA[name],
            "lab": [round(float(v), 6) for v in med],  # 修正2回目：4 桁の丸めで自己比較の ΔE00 が 1e-4 残ったため 6 桁にした
            "srgb8": [int(v) for v in T.lab_to_srgb8_best(med)[0]],
            "srgb8_quantisation_dE00": round(T.lab_to_srgb8_best(med)[1], 4),
            "pixels_display_eroded": int(core.sum()),
            "pixels_ref": int(region_ref[name].sum()),
            "lab_ref_frame_median": [round(float(v), 4) for v in med_ref],
            "source": "auto+manual" if name in ("sky_top", "sky_bottom", "boat_ochre", "fuji_snow", "fuji_slope") else "auto",
        }
    L_mid = round(0.5 * (palette["sky_top"]["lab"][0] + palette["sky_bottom"]["lab"][0]), 4)
    T.imwrite(os.path.join(T.TARGET_DIR, "masks", "palette_regions.png"), label_img)

    # ---- 被覆率マスク（表示フレーム）
    T.save_cov_png(os.path.join(T.TARGET_DIR, "masks", "sky_envelope_cov.png"), cov["envelope"])
    T.save_cov_png(os.path.join(T.TARGET_DIR, "masks", "sky_claws_cov.png"), cov["claws"])
    sky_dark = T.sky_dark_mask(lab_disp, cov["claws"], L_mid, ex["sky_dark"], fmap)
    T.save_cov_png(os.path.join(T.TARGET_DIR, "masks", "sky_dark_cov.png"), sky_dark)
    for name, m in boats.items():
        T.save_cov_png(os.path.join(T.TARGET_DIR, "masks", name + "_cov.png"), T.ref_mask_to_cov(m, fmap))

    # ---- 順序付き折れ線（主浪の外周 78→130→131→132、唇先端、内側 72）
    lm = man["landmarks_ref"]
    zone_disp = cv2.warpAffine(zone.astype(np.uint8), fmap.M, (fmap.W, fmap.H), flags=cv2.INTER_NEAREST).astype(bool)
    outlines = {}
    tip_disp = None
    for ver in ("envelope", "claws"):
        base = [lm["outer_start_left_edge"]["xy"], lm["b78_130"]["xy"], lm["b130_131"]["xy"], lm["b131_132"]["xy"]]
        if tip_disp is None:
            # 唇先端: 包絡線の claw_zone 内で x 最大の点
            path0, _, _ = ordered_outline(cov["envelope"], fmap, spec, tol=[4, 12, 12, 12, 6],
                                          lm_disp=
                                          T.poly_to_disp(fmap, base + [lm["inner_end"]["xy"]]))
            zi = zone_disp[np.clip(np.round(path0[:, 1]).astype(int), 0, fmap.H - 1),
                           np.clip(np.round(path0[:, 0]).astype(int), 0, fmap.W - 1)]
            if zi.any():
                cand = path0[zi]
                tip_disp = cand[int(np.argmax(cand[:, 0]))]
                tip_source = "auto（包絡線の claw_zone 内で x 最大）"
            else:
                tip_disp = T.poly_to_disp(fmap, [lm["lip_tip_fallback"]["xy"]])[0]
                tip_source = "manual（fallback）"
        lm_disp = np.vstack([T.poly_to_disp(fmap, base), tip_disp[None], T.poly_to_disp(fmap, [lm["inner_end"]["xy"]])])
        path, cuts, snap = ordered_outline(cov[ver], fmap, spec, lm_disp, tol=[4, 12, 12, 12, 40, 6])
        # 原画左端（採点列 x >= 157）より左を切る
        keep_from = int(np.argmax(path[:, 0] >= fmap.x0))
        cuts = np.maximum(cuts - keep_from, 0)
        path = path[keep_from:]
        segs = []
        ids = ["78", "130", "131", "132", "72"]
        for k, sid in enumerate(ids):
            P = path[cuts[k]:cuts[k + 1] + 1][::2] if cuts[k + 1] > cuts[k] else path[cuts[k]:cuts[k] + 1]
            if len(P) and not np.allclose(P[-1], path[cuts[k + 1]]):
                P = np.vstack([P, path[cuts[k + 1]]])
            length = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
            if ver == "envelope":
                src = "auto+manual（claw_zone 内は形態処理の包絡）" if sid in ("132", "72") else "auto（空マスク境界）＋manual（区間境界）"
            else:
                src = "auto（空マスク境界）＋manual（区間境界）"
            # 手動の障壁（藍線の途切れを閉じた線）に沿う点。障壁から 1.5 参照 px 以内を数える。
            Pr = fmap.disp_to_ref(P)
            db = cv2.remap(barrier_dist, Pr[:, 0].astype(np.float32).reshape(1, -1), Pr[:, 1].astype(np.float32).reshape(1, -1),
                           cv2.INTER_LINEAR).ravel() if len(barriers) else np.full(len(P), np.inf)
            nb = int((db <= 1.5).sum())
            if nb:
                src += "＋manual（藍線の途切れを閉じる障壁に沿う %d 点）" % nb
            segs.append({
                "id": sid,
                "backlog": [int(sid)],
                "name_ja": SEG_BACKLOG[sid],
                "source": src,
                "n_points": int(len(P)),
                "n_points_on_manual_barrier": nb,
                "length_display_px": round(length, 2),
                "points_display": np.round(P, 3).tolist(),
                "points_ref": np.round(fmap.disp_to_ref(P), 3).tolist(),
            })
        outlines[ver] = {"segments": segs, "landmark_snap_px": np.round(snap, 3).tolist()}

    # ---- 出力 JSON
    common = {
        "schema": "GreatWave.PaintingTruth.polyline/1",
        "truth_version": spec["version"],
        "coordinate_convention_ja": spec["coordinate_convention_ja"],
        "frame": {"width": fmap.W, "height": fmap.H, "scale": fmap.s, "offset_x": fmap.ox, "scored_columns": [fmap.x0, fmap.x1]},
        "reference_path": spec["reference"]["path"],
        "reference_sha256": spec["reference"]["sha256"],
        "reference_size": [spec["reference"]["width"], spec["reference"]["height"]],
        "painting_cam": {k: spec["painting_cam"][k] for k in ("id", "position", "target", "up", "vertical_fov_deg", "aspect", "near", "far")},
        "t_star_s": spec["timeline"]["t_star_s"],
        "outline_edge_ja": "真値は空とそれ以外の境界（藍の輪郭線の外縁）。線幅の半分の内側補正は含まない。",
        "lip_tip_display": np.round(tip_disp, 3).tolist(),
        "lip_tip_source": tip_source,
    }
    env = dict(common)
    env.update({
        "id": "main_wave_outline_envelope",
        "version": "envelope",
        "description_ja": "主浪の外周（左端→波頭→唇先端）と内側輪郭（唇先端→内壁の下端）。爪なし包絡版。claw_zone 内は空マスクの水側に閉じ（半径 %d 参照 px）→開き（半径 %d）→ガウス σ%.2f をかけた形（v0.1 の旧参照 px 20・10・4 を高解像度 px へ換算）。生成器（番号24/26）の K* 中央剖面の入力。" % (
            ex["envelope"]["close_radius_ref_px"], ex["envelope"]["open_radius_ref_px"], ex["envelope"]["smooth_sigma_ref_px"]),
        "segments": outlines["envelope"]["segments"],
        "landmark_snap_px": outlines["envelope"]["landmark_snap_px"],
    })
    claws = dict(common)
    claws.update({
        "id": "main_wave_outline_claws",
        "version": "claws",
        "description_ja": "同じ区間の爪入り版（原画の空境界そのもの）。爪の間の閉じた小空域は水側に入る（空と連結しないため）。",
        "segments": outlines["claws"]["segments"],
        "landmark_snap_px": outlines["claws"]["landmark_snap_px"],
    })
    T.save_json(os.path.join(T.TARGET_DIR, "main_wave_outline_envelope.json"), env)
    T.save_json(os.path.join(T.TARGET_DIR, "main_wave_outline_claws.json"), claws)

    regions = {
        "schema": "GreatWave.PaintingTruth.regions/1",
        "truth_version": spec["version"],
        "polygons_display": {k: np.round(T.poly_to_disp(fmap, v["points"]), 3).tolist() for k, v in polys.items()},
        "polygons_ref": {k: v["points"] for k, v in polys.items()},
        "barriers_ref": {k: {"points": v["points"], "width_ref_px": v["width_ref_px"]} for k, v in man.get("barriers_ref", {}).items()},
        "barriers_display": {k: np.round(T.poly_to_disp(fmap, v["points"]), 3).tolist() for k, v in man.get("barriers_ref", {}).items()},
        "source": "manual（manual_annotations.json）",
        "masks": {
            "sky_envelope": "masks/sky_envelope_cov.png",
            "sky_claws": "masks/sky_claws_cov.png",
            "sky_dark": "masks/sky_dark_cov.png",
            "boat_left": "masks/boat_left_cov.png",
            "boat_mid": "masks/boat_mid_cov.png",
            "boat_fg": "masks/boat_fg_cov.png",
            "palette_regions": "masks/palette_regions.png",
        },
        "mask_format_ja": "被覆率は 16bit グレー PNG（0..65535 = 0..1）、表示フレーム 1920×1080。palette_regions は 8bit ラベル（palette.json の label_value）。",
        "targets": [
            {"id": "71", "backlog": [71], "family": "sky", "select": "region71_clip の内側（辺から 1 px 以上内）の空境界点", "note_ja": "唇の下に開く空域。IoU も記録。", "source": "auto+manual"},
            {"id": "72", "backlog": [72], "family": "sky", "select": "segment 72", "source": "auto+manual"},
            {"id": "78", "backlog": [78], "family": "sky", "select": "segment 78", "source": "auto+manual"},
            {"id": "130", "backlog": [130], "family": "sky", "select": "segment 130", "source": "auto+manual"},
            {"id": "131", "backlog": [131], "family": "sky", "select": "segment 131", "source": "auto+manual"},
            {"id": "132", "backlog": [132], "family": "sky", "select": "segment 132", "source": "auto+manual"},
            {"id": "fuji_ridge", "backlog": [74, 161], "family": "sky", "select": "fuji_zone 内の空境界点", "source": "auto+manual", "note_ja": "報告項目（番号27）"},
            {"id": "sky_dark", "backlog": [76], "family": "sky_dark", "select": "全境界点", "source": "auto"},
            {"id": "sky_transition", "backlog": [213], "family": "sky_dark", "select": "空境界から 1 px より離れた点（明暗の移行線）", "source": "auto"},
            {"id": "boat_fg", "backlog": [75], "family": "boat_fg", "select": "全境界点（船体の黄土色部分のみ、漕ぎ手は含まない）", "source": "auto+manual", "note_ja": "報告項目"},
            {"id": "boat_left", "backlog": [157], "family": "boat_left", "select": "全境界点", "source": "auto+manual", "note_ja": "報告項目"},
            {"id": "boat_mid", "backlog": [159], "family": "boat_mid", "select": "全境界点", "source": "auto+manual", "note_ja": "報告項目"},
        ],
        "L_mid": round(L_mid, 4),
    }
    T.save_json(os.path.join(T.TARGET_DIR, "regions.json"), regions)
    save_other_polylines(spec, fmap, cov, sky_dark, boats, regions, common)
    pal = {
        "schema": "GreatWave.PaintingTruth.palette/1",
        "truth_version": spec["version"],
        "statistic_ja": "表示フレームの原画（双線形）で、各色区マスクを半径 3 px 収縮した内側の CIELAB 成分ごとの中央値。",
        "classes_lloyd_centers_lab": {names5[i]: [round(float(v), 4) for v in C[i]] for i in range(5)},
        "L_mid_sky": round(L_mid, 4),
        "palette": palette,
    }
    T.save_json(os.path.join(T.TARGET_DIR, "palette.json"), pal)
    gate_sync = sync_unity_gate_colors(palette)

    # ---- 線幅プロファイル（記録のみ。高解像度で測り、表示解像度で同じ測り方をした値と比べる）
    lw = line_width_truth(spec, fmap, lab_ref, lab_disp, sky_claws, cov["claws"], claws)
    T.save_json(os.path.join(T.TARGET_DIR, "line_width_profile.json"), lw["profile"])
    T.save_json(os.path.join(ev_dir, "23_line_width.json"), lw["summary"])

    # ---- 重ね図（人の確認用）
    make_overlays(spec, fmap, disp_rgb, cov, env, claws, regions, palette, label_img, sky_dark, boats, ev_dir)
    make_fix_figures(fmap, disp_rgb, ref_rgb, sky_claws, sky_v01_ref, zone, env, claws, man, ev_dir)
    make_line_width_figure(fmap, disp_rgb, lw, ev_dir)
    record["unity_gate_colour_sync"] = gate_sync
    T.save_json(os.path.join(ev_dir, "23_extract_record.json"), record)

    # ---- manifest
    outs = sorted(
        [os.path.join(dp, f) for dp, _, fs in os.walk(T.TARGET_DIR) for f in fs if f != "truth_manifest.json"])
    manifest = {
        "schema": "GreatWave.PaintingTruth.manifest/1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "command": "py -3.10 Tools/PaintingTruth/extract.py --evidence " + args.evidence,
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "os": platform.platform()},
        "inputs": {T.repo_rel(p): T.sha256_file(p) for p in [
            T.repo_abs(spec["reference"]["path"]), T.repo_abs(spec["legacy_reference"]["path"]), T.SPEC_PATH, T.MANUAL_PATH,
            os.path.join(T.HERE, "truthlib.py"), os.path.abspath(__file__)]},
        "inputs_note_ja": "旧原画（legacy_reference）は v0.1 の真値を作り直して比べる確認用の図と記録にだけ使い、真値の出力には入らない。",
        "outputs": {T.repo_rel(p): T.sha256_file(p) for p in outs},
        "build_outputs_not_committed": {T.repo_rel(os.path.join(T.BUILD_DIR, "painting_display.png")):
                                        T.sha256_file(os.path.join(T.BUILD_DIR, "painting_display.png"))},
    }
    T.save_json(os.path.join(T.TARGET_DIR, "truth_manifest.json"), manifest)
    print("EXTRACT_DONE", {k: len(v["segments"]) for k, v in outlines.items()}, "L_mid=%.3f" % L_mid)


def mask_polylines(cov, spec, fmap, keep=None, min_len=8.0, step=1.0):
    """被覆率の 0.5 等値線を順序付き折れ線で返す（4 倍拡大して輪郭追跡、約 step px 間隔に間引く）。

    keep(P) が与えられたときは、各点で真のものだけを残し、連続する部分ごとに折れ線にする。
    """
    sig = float(spec["scoring"]["contour"]["boundary_smoothing_sigma_px"])
    f = cv2.GaussianBlur(np.asarray(cov, np.float64), (0, 0), sig)
    hi = (cv2.resize(f, (fmap.W * 4, fmap.H * 4), interpolation=cv2.INTER_LINEAR) >= 0.5).astype(np.uint8)
    cnts, _ = cv2.findContours(hi, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cnts:
        P = (c[:, 0, :].astype(np.float64) + 0.5) / 4.0 - 0.5
        ok = fmap.scored(P)
        if keep is not None:
            ok &= keep(P)
        # 連続区間に分ける
        idx = np.flatnonzero(np.diff(np.concatenate([[0], ok.astype(np.int8), [0]])))
        for a, b in zip(idx[::2], idx[1::2]):
            Q = P[a:b]
            if len(Q) < 2:
                continue
            L = float(np.linalg.norm(np.diff(Q, axis=0), axis=1).sum())
            if L < min_len:
                continue
            Q = T.resample_polyline(Q, step)
            out.append(Q)
    return out


def save_other_polylines(spec, fmap, cov, sky_dark, boats, regions, common):
    """主浪以外の目標（富士の稜線、暗い空、71、三船）の折れ線を表示 px と参照 px で保存する。"""
    P = regions["polygons_display"]
    fz = np.asarray(P["fuji_zone"], np.float32)
    c71 = np.asarray(P["region71_clip"], np.float32)

    def inside(poly, margin):
        return lambda Q: np.array([cv2.pointPolygonTest(poly, (float(x), float(y)), True) > margin for x, y in Q])

    sky_cl = cov["claws"]
    items = []

    def add(tid, backlog, polys, src, note):
        items.append({
            "id": tid, "backlog": backlog, "source": src, "note_ja": note, "n_polylines": len(polys),
            "polylines_display": [np.round(Q, 3).tolist() for Q in polys],
            "polylines_ref": [np.round(fmap.disp_to_ref(Q), 3).tolist() for Q in polys],
        })

    add("fuji_ridge", [74, 161], mask_polylines(sky_cl, spec, fmap, inside(fz, 0.0)), "auto+manual",
        "fuji_zone 内の空境界（富士の稜線と、範囲内に入る船・海の縁）。報告項目。")
    add("sky_dark", [76], mask_polylines(sky_dark, spec, fmap), "auto", "暗い空（L* < L_mid）の外周。")
    dark_bd = mask_polylines(sky_dark, spec, fmap, step=0.5)
    skyP = np.vstack(mask_polylines(sky_cl, spec, fmap, step=0.5))
    trans = []
    for Q in dark_bd:
        d, _ = T.nearest(Q, skyP)
        ok = d > 1.0
        idx = np.flatnonzero(np.diff(np.concatenate([[0], ok.astype(np.int8), [0]])))
        for a, b in zip(idx[::2], idx[1::2]):
            if b - a >= 8:
                trans.append(T.resample_polyline(Q[a:b], 1.0))
    add("sky_transition", [213], trans, "auto", "暗い空の外周のうち、空境界から 1 px より離れた部分（明暗の移行線）。")
    for ver in ("envelope", "claws"):
        add("region71_" + ver, [71], mask_polylines(cov[ver], spec, fmap, inside(c71, 1.0)), "auto+manual",
            "空 ∩ region71_clip の境界（弦の上は含まない）。%s 版。" % ver)
    for name, bl in (("boat_fg", [75]), ("boat_left", [157]), ("boat_mid", [159])):
        add(name, bl, mask_polylines(T.ref_mask_to_cov(boats[name], fmap), spec, fmap), "auto+manual",
            "黄土色の船体（漕ぎ手は含まない）。報告項目。" + ("断片的。" if name == "boat_left" else ""))
    out = dict(common)
    out.update({"id": "other_targets", "description_ja": "主浪の外周以外の目標折れ線。評価器は被覆率マスク（targets/masks）から同じ境界を点列にして使う。この折れ線は確認と他ツール用。",
                "targets": items})
    T.save_json(os.path.join(T.TARGET_DIR, "other_polylines.json"), out)


# ---------------------------------------------------------------- 修正2回目：v0.1 との比較、障壁の記録、色区の同期、線幅
def legacy_sky_v01(spec, man, shape_ref):
    """v0.1 の真値の空（旧原画 1200×807、v0.1 の規則、旧座標の注記と障壁 3 本）を作り直し、高解像度の格子へ写す。確認用。"""
    leg = spec["legacy_reference"]
    lp = T.repo_abs(leg["path"])
    if T.sha256_file(lp) != leg["sha256"]:
        raise RuntimeError("旧原画の SHA-256 が記録と違います")
    lab_l = T.srgb8_to_lab(T.imread_rgb(lp))
    P = man["polygons_ref"]
    fills = [P["sky_fill_cartouche"]["legacy_ref_points"], P["sky_fill_signature"]["legacy_ref_points"]]
    bars = [{"points": v["legacy_ref_points"], "width_ref_px": v["legacy_width_ref_px"]}
            for v in man["barriers_ref"].values() if "legacy_width_ref_px" in v]
    sky_l = T.segment_sky(lab_l, spec["extraction"]["legacy_v0_1"]["sky"], fills, bars)
    H, W = shape_ref
    h, w = sky_l.shape
    M = np.array([[W / w, 0.0, 0.5 * W / w - 0.5], [0.0, H / h, 0.5 * H / h - 0.5]])  # 画素中心の約束
    sky_h = cv2.warpAffine(sky_l.astype(np.float32), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE) > 0.5
    return sky_h, sky_l


def _components(mask, fmap, k, min_area):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    out = []
    for i in range(1, n):
        if st[i, 4] < min_area:
            continue
        c = cen[i]
        out.append({"area_ref_px": int(st[i, 4]), "area_legacy_ref_px2": round(float(st[i, 4]) / (k * k), 1),
                    "bbox_ref_xywh": [int(v) for v in st[i, :4]],
                    "centroid_ref": [round(float(c[0]), 1), round(float(c[1]), 1)],
                    "centroid_legacy_ref": [round((float(c[0]) + 0.5) / k - 0.5, 1), round((float(c[1]) + 0.5) / k - 0.5, 1)],
                    "centroid_display": [round(float(v), 1) for v in fmap.ref_to_disp(c)]})
    out.sort(key=lambda d: -d["area_ref_px"])
    return out


def extract_record(spec, man, lab_ref, fills, barriers, sky, sky_nb0, sky_v01, fmap):
    """記録のみ：v0.1 → v0.2 の空の差、障壁を 1 本ずつ外した差、途切れの閉じ（半径）を変えた場合の流れ込み。"""
    ex = spec["extraction"]
    k = float(spec["reference"]["px_per_legacy_ref_px"])
    inner = T.erode(~sky, 20)  # v0.2 の水の面から 20 px 以上内側

    def cmp(other, min_area):
        return {"to_sky_px": int((other & ~sky).sum()), "to_water_px": int((~other & sky).sum()),
                "interior_water_to_sky_px": int((other & inner).sum()),
                "components_to_sky": _components(other & ~sky, fmap, k, min_area)[:8],
                "components_to_water": _components(~other & sky, fmap, k, min_area)[:8]}
    rec = {"schema": "GreatWave.Step23.extract_record/1", "truth_version": spec["version"], "verdict": "record-only",
           "note_ja": "値は高解像度 px（ref）の画素数。to_sky は v0.2 の真値で水・比べる側で空、to_water はその逆。"
                      "interior_water_to_sky は v0.2 の水の面から 20 px 以上内側が空になった画素で、流れ込みの目安。"}
    rec["v0_1_to_v0_2"] = dict(cmp(sky_v01, 60), note_ja="比べる側 = v0.1 の真値（旧原画・旧規則・障壁 3 本で作り直し、画素中心の約束で高解像度へ写した）。")
    rec["control_no_gap_closing_no_manual_barriers"] = dict(cmp(sky_nb0, 200), note_ja="比べる側 = 途切れの閉じ（barrier_dilate_ref_px）を 0 にし、手動の障壁を外した空。")
    abl = {}
    for i, name in enumerate(man["barriers_ref"].keys()):
        others = [b for j, b in enumerate(barriers) if j != i]
        abl[name] = cmp(T.segment_sky(lab_ref, ex["sky"], fills, others), 20)
    rec["barrier_ablation"] = dict(abl, note_ja="比べる側 = その障壁 1 本だけを外した空（ほかの障壁と途切れの閉じは同じ）。")
    gc = {}
    for r in range(0, int(ex["sky"]["barrier_dilate_ref_px"])):
        o = T.segment_sky(lab_ref, dict(ex["sky"], barrier_dilate_ref_px=r), fills, barriers)
        gc["radius_%d" % r] = {"to_sky_px": int((o & ~sky).sum()), "to_water_px": int((~o & sky).sum()),
                               "interior_water_to_sky_px": int((o & inner).sum())}
    rec["gap_closing_radius"] = dict(gc, used=int(ex["sky"]["barrier_dilate_ref_px"]),
                                     note_ja="手動の障壁 4 本はそのままで、途切れの閉じの半径だけを小さくした場合。")
    return rec


def sync_unity_gate_colors(palette):
    """unity_gate.json の平塗り色区の srgb8 を調色板（palette.json）に合わせる（gate_part2.py が一致を確かめる）。"""
    p = os.path.join(T.HERE, "unity_gate.json")
    with open(p, encoding="utf-8", newline="") as f:
        s = f.read()
    changed = {}
    for name, v in palette.items():
        pat = re.compile(r'(\{ "name": "%s", "srgb8": \[)([0-9, ]+)(\])' % re.escape(name))
        m = pat.search(s)
        if m is None:
            continue
        new = "%d, %d, %d" % tuple(v["srgb8"])
        if m.group(2) != new:
            changed[name] = {"from": "[" + m.group(2) + "]", "to": "[" + new + "]"}
        s = pat.sub(lambda mm: mm.group(1) + new + mm.group(3), s)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    return {"path": T.repo_rel(p), "changed": changed}


LW_SEGS = ["78", "130", "131", "132", "72"]


def line_width_truth(spec, fmap, lab_ref, lab_disp, sky_ref, cov_claws, claws):
    """藍の輪郭線の幅プロファイル（爪入り版の 5 区間、記録のみ）。

    高解像度で測った幅（真値）と、同じ点・同じ測り方で表示フレームの原画（3×3 超標本化の縮小）から測った幅を比べ、
    1920×1080 の描画で ±20% の判定ができるかを確かめる。再現性は、点を間隔の半分ずらした 2 回目の測定との差で見る。
    """
    k = float(spec["reference"]["px_per_legacy_ref_px"])
    pr = spec["scoring"]["line_width"]["profile"]
    kd = k * fmap.s
    p_ref = {"sky_side": pr["sky_side_legacy_ref_px"] * k, "max_width": pr["max_width_legacy_ref_px"] * k,
             "step": pr["step_ref_px"], "min_depth": pr["min_depth_L"]}
    p_disp = {"sky_side": pr["sky_side_legacy_ref_px"] * kd, "max_width": pr["max_width_legacy_ref_px"] * kd,
              "step": pr["step_display_px"], "min_depth": pr["min_depth_L"]}
    L_ref = lab_ref[..., 0].astype(np.float32)
    L_disp = lab_disp[..., 0].astype(np.float32)
    sky_f = sky_ref.astype(np.float32)
    zone = T.poly_mask(sky_ref.shape, T.load_manual()["polygons_ref"]["claw_zone"]["points"])
    spacing = float(pr["spacing_legacy_ref_px"]) * kd
    prof = {"schema": "GreatWave.PaintingTruth.line_width_profile/1", "truth_version": spec["version"],
            "reference_sha256": spec["reference"]["sha256"], "outline": "main_wave_outline_claws.json",
            "params_ref_px": p_ref, "params_display_px": p_disp, "spacing_display_px": round(spacing, 4),
            "method_ja": pr["method_ja"], "judged": False, "segments": []}
    summ = {"schema": "GreatWave.Step23.line_width/1", "truth_version": spec["version"], "verdict": "record-only",
            "unit_note_ja": "width_ref_px は高解像度 px、width_display_px は表示 px（= 高解像度 px × %.6f）。" % fmap.s,
            "segments": {}}
    allrel, allrep = [], []
    for s in claws["segments"]:
        if s["id"] not in LW_SEGS:
            continue
        Pd = T.resample_polyline(np.array(s["points_display"]), spacing)
        Pr = fmap.disp_to_ref(Pd)
        a = T.line_width_profile(L_ref, Pr, T.outline_normals(Pr, sky_f, 2.0 * k), p_ref)
        Pr2 = fmap.disp_to_ref(0.5 * (Pd[1:] + Pd[:-1]))
        a2 = T.line_width_profile(L_ref, Pr2, T.outline_normals(Pr2, sky_f, 2.0 * k), p_ref)
        b = T.line_width_profile(L_disp, Pd, T.outline_normals(Pd, cov_claws, 2.0), p_disp)
        inz = zone[np.clip(np.round(Pr[:, 1]).astype(int), 0, zone.shape[0] - 1), np.clip(np.round(Pr[:, 0]).astype(int), 0, zone.shape[1] - 1)]
        wr = a["width"]
        wrd = wr * fmap.s
        wd = b["width"]
        both = np.isfinite(wrd) & np.isfinite(wd)
        rel = wd[both] / wrd[both] - 1.0
        allrel.append(rel)
        ok = np.isfinite(wr)
        ok2 = np.isfinite(a2["width"])
        med = float(np.median(wr[ok])) if ok.any() else None
        med2 = float(np.median(a2["width"][ok2])) if ok2.any() else None
        rep = (med2 / med - 1.0) if (med and med2) else None
        if rep is not None:
            allrep.append(rep)
        # 局所の揺れ（隣の点との差 / √2）。本当の太さの変化も含む上限の目安。
        wv = wr[ok]
        local = float(np.median(np.abs(np.diff(wv))) / math.sqrt(2)) if len(wv) > 2 else None
        arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=1))])
        prof["segments"].append({
            "id": s["id"], "backlog": [int(s["id"])], "n_points": int(len(Pd)),
            "arc_display_px": np.round(arc, 2).tolist(),
            "points_display": np.round(Pd, 3).tolist(),
            "width_ref_px": [None if not np.isfinite(v) else round(float(v), 3) for v in wr],
            "width_display_px_measured_at_display": [None if not np.isfinite(v) else round(float(v), 3) for v in wd],
            "reason": a["reason"].astype(int).tolist(), "in_claw_zone": inz.astype(int).tolist(),
            "reason_ja": "0 = 測定、1 = 線なし（深さ < min_depth）、2 = 線が暗い面に続く（merged）"})

        def q(v, p):
            return round(float(np.percentile(v, p)), 3) if len(v) else None
        summ["segments"][s["id"]] = {
            "n_points": int(len(Pd)), "n_measured_ref": int(ok.sum()), "n_no_line_ref": int((a["reason"] == 1).sum()),
            "n_merged_ref": int((a["reason"] == 2).sum()), "n_in_claw_zone": int(inz.sum()),
            "width_ref_px": {"median": q(wr[ok], 50), "p10": q(wr[ok], 10), "p90": q(wr[ok], 90)},
            "width_display_px": {"median": q(wrd[ok], 50), "p10": q(wrd[ok], 10), "p90": q(wrd[ok], 90)},
            "tolerance_display_px_at_median": round(0.2 * float(np.median(wrd[ok])), 3) if ok.any() else None,
            "measured_at_display": {"n_measured": int(np.isfinite(wd).sum()), "median_display_px": q(wd[np.isfinite(wd)], 50),
                                    "median_ratio_minus_1": round(float(np.median(wd[np.isfinite(wd)]) / np.median(wrd[ok]) - 1.0), 4) if (ok.any() and np.isfinite(wd).any()) else None,
                                    "per_point_rel_error_abs_median": q(np.abs(rel), 50), "per_point_rel_error_abs_p95": q(np.abs(rel), 95),
                                    "per_point_within_20pct": round(float((np.abs(rel) <= 0.2).mean()), 4) if len(rel) else None},
            "repeatability_half_spacing_median_rel": round(rep, 4) if rep is not None else None,
            "local_variation_ref_px": round(local, 3) if local is not None else None,
        }
    rel = np.concatenate(allrel) if allrel else np.zeros(0)
    seg_err = [abs(v["measured_at_display"]["median_ratio_minus_1"]) for v in summ["segments"].values()
               if v["measured_at_display"]["median_ratio_minus_1"] is not None]
    feas_seg = bool(seg_err and max(seg_err) <= 0.05 and all(abs(r) <= 0.05 for r in allrep))
    p95 = float(np.percentile(np.abs(rel), 95)) if len(rel) else None
    feas_pt = bool(p95 is not None and p95 <= 0.10)
    summ["feasibility"] = {
        "segment_median_rel_error_max": round(max(seg_err), 4) if seg_err else None,
        "repeatability_rel_max": round(max(abs(r) for r in allrep), 4) if allrep else None,
        "per_point_rel_error_abs_p95_all": round(p95, 4) if p95 is not None else None,
        "per_point_within_20pct_all": round(float((np.abs(rel) <= 0.2).mean()), 4) if len(rel) else None,
        "segment_level_feasible": feas_seg, "per_point_feasible": feas_pt,
        "criteria_ja": "区間の中央値の判定ができる条件：表示解像度で測った区間中央値と高解像度の区間中央値の差 ≤5%、かつ点を半間隔ずらした再測定の差 ≤5%"
                       "（±20% の 1/4）。点ごとの判定ができる条件：点ごとの相対差の p95 ≤10%（±20% の半分）。",
    }
    return {"profile": prof, "summary": summ}


# ---------------------------------------------------------------- 重ね図
SEG_COLORS ={"78": (255, 80, 40), "130": (255, 170, 0), "131": (60, 200, 60), "132": (40, 140, 255), "72": (200, 60, 230)}


def _dim(img, k=0.55):
    return (img.astype(np.float32) * k + 255 * (1 - k) * 0.15).astype(np.uint8)


def _poly(img, P, color, th=2):
    P = np.round(np.asarray(P) * 4).astype(np.int32)
    cv2.polylines(img, [P.reshape(-1, 1, 2)], False, color, th, cv2.LINE_AA, shift=2)


def _label(img, text, xy, color, scale=0.6):
    x, y = int(xy[0]), int(xy[1])
    cv2.putText(img, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def _bars(img, fmap):
    img[:, :fmap.x0] = (img[:, :fmap.x0] * 0.12).astype(np.uint8)
    img[:, fmap.x1 + 1:] = (img[:, fmap.x1 + 1:] * 0.12).astype(np.uint8)


OVERLAY_COLORS = list(SEG_COLORS.values()) + [(235, 235, 235), (255, 255, 120), (120, 255, 255), (255, 210, 120),
                                              (180, 180, 255), (255, 255, 255), (0, 0, 0)]


def save_quantized(path, rgb, extra=()):
    T.save_png_reserved(path, rgb, OVERLAY_COLORS + list(extra))


def make_overlays(spec, fmap, disp, cov, env, claws, regions, palette, label_img, sky_dark, boats, ev_dir):
    # 1) 目標折れ線
    img = _dim(disp)
    _bars(img, fmap)
    for s in claws["segments"]:
        _poly(img, s["points_display"], (235, 235, 235), 1)
    for s in env["segments"]:
        c = SEG_COLORS[s["id"]]
        _poly(img, s["points_display"], c, 3)
        P = np.array(s["points_display"])
        m = P[len(P) // 2]
        _label(img, s["id"], (m[0] + 8, m[1] - 8), c, 0.8)
    poly71 = np.array(regions["polygons_display"]["region71_clip"])
    cv2.polylines(img, [np.round(poly71).astype(np.int32).reshape(-1, 1, 2)], True, (255, 255, 120), 1, cv2.LINE_AA)
    _label(img, "71 clip", poly71[0] + [4, 18], (255, 255, 120))
    fz = np.array(regions["polygons_display"]["fuji_zone"])
    cv2.polylines(img, [np.round(fz).astype(np.int32).reshape(-1, 1, 2)], True, (120, 255, 255), 1, cv2.LINE_AA)
    _label(img, "fuji 74/161", fz[0] + [2, -6], (120, 255, 255))
    for name, color in (("boat_left", (255, 210, 120)), ("boat_mid", (255, 210, 120)), ("boat_fg", (255, 210, 120))):
        m = (T.ref_mask_to_cov(boats[name], fmap) > 0.5).astype(np.uint8)
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(img, cs, -1, color, 1, cv2.LINE_AA)
        if cs:
            x, y, w, h = cv2.boundingRect(max(cs, key=cv2.contourArea))
            _label(img, {"boat_left": "157", "boat_mid": "159", "boat_fg": "75"}[name], (x, y - 4), color)
    dk = (sky_dark > 0.5).astype(np.uint8)
    cs, _ = cv2.findContours(dk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, cs, -1, (180, 180, 255), 1, cv2.LINE_AA)
    _label(img, "76/213 dark-sky L*<%.1f" % regions["L_mid"], (1000, 640), (180, 180, 255))
    tip = env["lip_tip_display"]
    cv2.circle(img, (int(round(tip[0])), int(round(tip[1]))), 7, (255, 255, 255), 2, cv2.LINE_AA)
    _label(img, "lip tip", (tip[0] + 10, tip[1] + 4), (255, 255, 255))
    _label(img, "23 PaintingTruth v0.2 (hi-res 3859x2594): envelope (thick) / claws (thin white) / display 1920x1080, bars excluded", (170, 1068), (255, 255, 255), 0.55)
    save_quantized(os.path.join(ev_dir, "23_targets_overlay.png"), img)

    # 2) 唇まわりの拡大（爪入りと包絡の差）
    x0, y0, x1, y1 = 640, 90, 1280, 450  # 表示 px（16:9）
    crop = disp[y0:y1, x0:x1].copy()
    big = cv2.resize(crop, (1920, 1080), interpolation=cv2.INTER_NEAREST)
    sx, sy = 1920 / (x1 - x0), 1080 / (y1 - y0)
    for s in claws["segments"]:
        P = (np.array(s["points_display"]) - [x0, y0]) * [sx, sy]
        _poly(big, P, (255, 255, 255), 2)
    for s in env["segments"]:
        P = (np.array(s["points_display"]) - [x0, y0]) * [sx, sy]
        _poly(big, P, SEG_COLORS[s["id"]], 4)
    _label(big, "claw zone detail (display px %d-%d, %d-%d): envelope=colour, claws=white" % (x0, x1, y0, y1), (20, 1060), (255, 255, 255), 0.8)
    save_quantized(os.path.join(ev_dir, "23_claw_zone_detail.png"), big)

    # 3) 色区と調色板
    img = _dim(disp, 0.35)
    _bars(img, fmap)
    for name, p in palette.items():
        m = label_img == p["label_value"]
        img[m] = (0.35 * img[m] + 0.65 * np.array(p["srgb8"])).astype(np.uint8)
    for k, name in enumerate(PALETTE_ORDER):
        p = palette[name]
        y = 20 + k * 52
        cv2.rectangle(img, (1500, y), (1560, y + 44), tuple(int(v) for v in p["srgb8"]), -1)
        cv2.rectangle(img, (1500, y), (1560, y + 44), (255, 255, 255), 1)
        _label(img, "%s L%.1f a%.1f b%.1f n=%d" % (name, *p["lab"], p["pixels_display_eroded"]), (1568, y + 28), (255, 255, 255), 0.45)
    _label(img, "23 palette regions (median CIELAB inside 3 px erosion)", (170, 1068), (255, 255, 255), 0.55)
    save_quantized(os.path.join(ev_dir, "23_palette_regions.png"), img, [tuple(p["srgb8"]) for p in palette.values()])


BARRIER_COLOR = (255, 0, 255)
HATCH_COLOR = (230, 30, 30)
CHANGED_COLOR = (255, 230, 0)
ZONE_COLOR = (0, 170, 255)
V01_COLOR = (0, 200, 0)


def _ref_crop_to(ref, fmap, x0d, y0d, z, W=1920, H=1080):
    """高解像度原画から、表示 px (x0d, y0d) を左上に z 倍した W×H の拡大図を作る（表示を経ずに原画から直接写す）。"""
    a = z * fmap.s
    M = np.array([[a, 0.0, z * (fmap.tx + 0.5 - x0d) - 0.5], [0.0, a, z * (fmap.ty + 0.5 - y0d) - 0.5]])
    return cv2.warpAffine(ref, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE), M


def _mask_contours_to(mask, M, W=1920, H=1080):
    m = cv2.warpAffine(mask.astype(np.float32), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE) > 0.5
    cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    return cs


def make_fix_figures(fmap, disp, ref, sky_claws, sky_v01, zone, env, claws, man, ev_dir):
    """修正の確認図。唇の右端の拡大（表示 px の 5 倍、高解像度から直接）、claw_zone 全体の空の斜線図（v0.1 / v0.2）、
    波頭上部の爪の拡大（v0.1 / v0.2、修正2回目で加えた障壁）。"""
    bars = man.get("barriers_ref", {})
    # 4) 唇の右端の拡大（表示 px 850-1234, 190-406 を 5 倍）
    x0, y0, z = 850, 190, 5
    x1, y1 = x0 + 1920 // z, y0 + 1080 // z
    big, M = _ref_crop_to(ref, fmap, x0, y0, z)
    big = (big.astype(np.float32) * 0.85 + 255 * 0.15).astype(np.uint8)
    tr = lambda P: (np.asarray(P, np.float64) + 0.5 - [x0, y0]) * z - 0.5
    cv2.drawContours(big, _mask_contours_to(sky_v01, M), -1, V01_COLOR, 2, cv2.LINE_AA)
    for k, v in bars.items():
        P = tr(T.poly_to_disp(fmap, v["points"]))
        _poly(big, P, BARRIER_COLOR, max(2, int(round(v["width_ref_px"] * fmap.s * z))))
    for s in claws["segments"]:
        _poly(big, tr(s["points_display"]), (0, 0, 0), 5)
        _poly(big, tr(s["points_display"]), (255, 255, 255), 2)
    for s in env["segments"]:
        _poly(big, tr(s["points_display"]), SEG_COLORS[s["id"]], 4)
    tip = tr(env["lip_tip_display"])
    cv2.circle(big, (int(round(tip[0])), int(round(tip[1]))), 16, (255, 255, 255), 2, cv2.LINE_AA)
    _label(big, "lip tip", (tip[0] + 20, tip[1] + 6), (255, 255, 255), 0.8)
    for k in range(0, 1920, 50 * z):  # 50 表示 px ごとの目盛り
        _label(big, str(x0 + k // z), (k + 4, 22), (255, 255, 255), 0.5)
    for k in range(50 * z, 1080, 50 * z):
        _label(big, str(y0 + k // z), (4, k - 4), (255, 255, 255), 0.5)
    cv2.line(big, (1700, 1000), (1700 + 4 * z, 1000), (255, 255, 255), 3)
    _label(big, "= 4 display px", (1700 + 4 * z + 8, 1006), (255, 255, 255), 0.6)
    _label(big, "23 lip close-up from hi-res 3859x2594 (display px %d-%d, %d-%d, x%d): envelope=colour (132 blue, 72 purple), claws=white, barriers=magenta"
           % (x0, x1, y0, y1, z), (20, 1040), (255, 255, 255), 0.62)
    _label(big, "truth v0.2 (hi-res). green = v0.1 sky boundary (1200x807) for comparison", (20, 1068), (255, 255, 255), 0.62)
    save_quantized(os.path.join(ev_dir, "23_lip_closeup_x5.png"), big, [BARRIER_COLOR, V01_COLOR])

    # 5) claw_zone 全体の空（斜線）。左 = v0.1 の真値（旧原画から作り直して高解像度へ写した）、右 = v0.2 の真値
    zp = np.array(man["polygons_ref"]["claw_zone"]["points"])
    bx0, by0 = int(zp[:, 0].min()) - 15, int(zp[:, 1].min()) - 15
    bx1, by1 = int(zp[:, 0].max()) + 16, int(zp[:, 1].max()) + 16
    zs = min(930.0 / (bx1 - bx0), 990.0 / (by1 - by0))
    W, H = int(round((bx1 - bx0) * zs)), int(round((by1 - by0) * zs))
    canvas = np.full((1080, 1920, 3), 24, np.uint8)
    changed = sky_v01 != sky_claws
    # 境界の 1〜2 px の揺れを除き、開き（半径 1）の後に 60 px 以上残る塊だけを変化として囲む
    sig = cv2.morphologyEx(changed.astype(np.uint8), cv2.MORPH_OPEN, T.disk(1))
    n_, lab_, st_, _ = cv2.connectedComponentsWithStats(sig, connectivity=8)
    changed_sig = np.isin(lab_, [i for i in range(1, n_) if st_[i, 4] >= 60])
    crop0 = cv2.resize(ref[by0:by1, bx0:bx1], (W, H), interpolation=cv2.INTER_AREA)
    for k, (skym, title) in enumerate(((sky_v01, "truth v0.1 (1200x807, 3 barriers): sky = red hatch"),
                                       (sky_claws, "truth v0.2 (hi-res, gap closing r=3 px + 4 barriers magenta): sky = red hatch"))):
        crop = crop0.copy()
        m = cv2.resize(skym[by0:by1, bx0:bx1].astype(np.float32), (W, H), interpolation=cv2.INTER_AREA) > 0.5
        yy, xx = np.mgrid[0:H, 0:W]
        crop[m & (((xx + yy) // 2) % 5 == 0)] = HATCH_COLOR
        ch = cv2.dilate((cv2.resize(changed_sig[by0:by1, bx0:bx1].astype(np.float32), (W, H), interpolation=cv2.INTER_AREA) > 0.05).astype(np.uint8), np.ones((5, 5), np.uint8))
        cs, _ = cv2.findContours(ch, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(crop, cs, -1, CHANGED_COLOR, 2, cv2.LINE_AA)
        P = np.round((zp - [bx0, by0] + 0.5) * zs - 0.5).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(crop, [P], True, ZONE_COLOR, 2, cv2.LINE_AA)
        if k == 1:
            for v in bars.values():
                Q = (np.asarray(v["points"], np.float64) - [bx0, by0] + 0.5) * zs - 0.5
                _poly(crop, Q, BARRIER_COLOR, 3)
        ox = 20 + k * 960
        canvas[50:50 + H, ox:ox + W] = crop
        _label(canvas, title, (ox, 38), (255, 255, 255), 0.55)
    _label(canvas, "23 claw_zone (ref px %d-%d, %d-%d, x%.3f). yellow outline = changed areas >= 60 hi-res px after 1 px opening (all changed: %d sky -> water, %d water -> sky, hi-res px)"
           % (bx0, bx1, by0, by1, zs, int((sky_v01 & ~sky_claws).sum()), int((~sky_v01 & sky_claws).sum())),
           (20, 1068), (255, 255, 255), 0.55)
    T.save_png_reserved(os.path.join(ev_dir, "23_claw_zone_sky_tint.png"), canvas,
                        [HATCH_COLOR, CHANGED_COLOR, ZONE_COLOR, BARRIER_COLOR, (255, 255, 255), (0, 0, 0)])

    # 6) 波頭上部の爪（修正2回目で障壁を加えた所）。高解像度 px 1790-1950, 395-535 を 6 倍、左 = v0.1、右 = v0.2
    cx0, cy0, cw, chh, cz = 1790, 395, 160, 140, 6
    kk = 3859.0 / 1200.0
    canvas = np.full((1080, 1920, 3), 24, np.uint8)
    for k, (skym, title) in enumerate(((sky_v01, "truth v0.1: sky = red hatch"),
                                       (sky_claws, "truth v0.2: sky = red hatch, barrier crest_hook_bottom_gap = magenta"))):
        crop = cv2.resize(ref[cy0:cy0 + chh, cx0:cx0 + cw], (cw * cz, chh * cz), interpolation=cv2.INTER_NEAREST)
        m = cv2.resize(skym[cy0:cy0 + chh, cx0:cx0 + cw].astype(np.uint8), (cw * cz, chh * cz), interpolation=cv2.INTER_NEAREST).astype(bool)
        yy, xx = np.mgrid[0:chh * cz, 0:cw * cz]
        crop[m & (((xx + yy) // 3) % 4 == 0)] = HATCH_COLOR
        if k == 1:
            for v in bars.values():
                Q = (np.asarray(v["points"], np.float64) - [cx0, cy0] + 0.5) * cz - 0.5
                _poly(crop, Q, BARRIER_COLOR, 3)
        for g in range(0, cw, 10):
            crop[:, g * cz] = crop[:, g * cz] // 2 + 60
        for g in range(0, chh, 10):
            crop[g * cz, :] = crop[g * cz, :] // 2 + 60
        ox = k * 960
        canvas[60:60 + chh * cz, ox:ox + cw * cz] = crop
        _label(canvas, title, (ox + 10, 45), (255, 255, 255), 0.6)
    _label(canvas, "23 upper-crest claw, hi-res px %d-%d, %d-%d (x%d, 10 px grid; legacy ref px ~%d-%d, %d-%d). v0.1 leak into the pale-blue claw body is closed in v0.2"
           % (cx0, cx0 + cw, cy0, cy0 + chh, cz, (cx0 + 0.5) / kk, (cx0 + cw) / kk, (cy0 + 0.5) / kk, (cy0 + chh) / kk),
           (10, 1000), (255, 255, 255), 0.55)
    T.save_png_reserved(os.path.join(ev_dir, "23_crest_closeup.png"), canvas,
                        [HATCH_COLOR, BARRIER_COLOR, (255, 255, 255), (0, 0, 0)])


def make_line_width_figure(fmap, disp, lw, ev_dir):
    """線幅プロファイル：上は原画（表示フレーム）の上に幅を色で、下は区間ごとの幅（弧長 → 表示 px）。"""
    img = _dim(disp, 0.5)
    _bars(img, fmap)
    lo, hi_ = 1.5, 5.0
    segs = lw["profile"]["segments"]
    for s in segs:
        P = np.array(s["points_display"])
        w = np.array([np.nan if v is None else v * fmap.s for v in s["width_ref_px"]])
        for p, v in zip(P, w):
            if np.isfinite(v):
                c = cv2.applyColorMap(np.uint8([[int(np.clip((v - lo) / (hi_ - lo), 0, 1) * 255)]]), cv2.COLORMAP_TURBO)[0, 0][::-1]
                cv2.circle(img, (int(round(p[0])), int(round(p[1]))), 2, tuple(int(x) for x in c), -1)
            else:
                cv2.circle(img, (int(round(p[0])), int(round(p[1]))), 1, (90, 90, 90), -1)
    for i in range(200):
        c = cv2.applyColorMap(np.uint8([[int(i / 199 * 255)]]), cv2.COLORMAP_TURBO)[0, 0][::-1]
        cv2.line(img, (1500 + i, 40), (1500 + i, 56), tuple(int(x) for x in c), 1)
    _label(img, "%.1f" % lo, (1490, 76), (255, 255, 255), 0.5)
    _label(img, "%.1f display px" % hi_, (1680, 76), (255, 255, 255), 0.5)
    # 下の図（y 700-1030）：区間ごと、弧長を横に並べる
    y0, y1 = 700, 1030
    x0, x1 = 170, 1750
    cv2.rectangle(img, (x0 - 30, y0 - 44), (x1 + 10, y1 + 10), (20, 20, 20), -1)
    total = sum(max(s["arc_display_px"]) for s in segs) + 20 * (len(segs) - 1)
    sx = (x1 - x0) / total
    wmax = 6.0
    Y = lambda w: y1 - (min(max(w, 0.0), wmax) / wmax) * (y1 - y0)  # 枠の外（> 6 px）は上端に切り詰める
    for g in range(0, int(wmax) + 1):
        cv2.line(img, (x0, int(Y(g))), (x1, int(Y(g))), (60, 60, 60), 1)
        _label(img, str(g), (x0 - 22, int(Y(g)) + 5), (200, 200, 200), 0.45)
    off = 0.0
    summ = lw["summary"]["segments"]
    for si, s in enumerate(segs):
        arc = np.array(s["arc_display_px"])
        wr = np.array([np.nan if v is None else v * fmap.s for v in s["width_ref_px"]])
        wd = np.array([np.nan if v is None else v for v in s["width_display_px_measured_at_display"]])
        X = x0 + (off + arc) * sx
        med = summ[s["id"]]["width_display_px"]["median"]
        if med is not None:
            for f in (0.8, 1.2):
                cv2.line(img, (int(X[0]), int(Y(med * f))), (int(X[-1]), int(Y(med * f))), (255, 220, 0), 1)
            cv2.line(img, (int(X[0]), int(Y(med))), (int(X[-1]), int(Y(med))), (255, 220, 0), 2)
        for i in range(len(X) - 1):
            if np.isfinite(wr[i]) and np.isfinite(wr[i + 1]):
                cv2.line(img, (int(X[i]), int(Y(wr[i]))), (int(X[i + 1]), int(Y(wr[i + 1]))), (255, 255, 255), 1, cv2.LINE_AA)
        for xx_, v in zip(X, wd):
            if np.isfinite(v):
                cv2.circle(img, (int(xx_), int(Y(v))), 1, (0, 255, 255), -1)
        _label(img, s["id"] + (" med %.2f" % med if med is not None else ""), (int(X[0]) + 4, y0 - 8 - 14 * (si % 2)), SEG_COLORS[s["id"]], 0.5)
        off += arc[-1] + 20
    f = lw["summary"]["feasibility"]
    _label(img, "23 line-width profile (record only): white = hi-res half-depth width x %.4f, cyan = same method on the 1920x1080 display image, yellow = segment median +-20%%" % fmap.s,
           (170, 1052), (255, 255, 255), 0.5)
    _label(img, "segment median error at display res max %.1f%%, repeatability max %.1f%%, per-point |error| p95 %.1f%% -> segment-level %s, per-point %s"
           % (100 * (f["segment_median_rel_error_max"] or 0), 100 * (f["repeatability_rel_max"] or 0), 100 * (f["per_point_rel_error_abs_p95_all"] or 0),
              "feasible" if f["segment_level_feasible"] else "not feasible", "feasible" if f["per_point_feasible"] else "not feasible"),
           (170, 1074), (255, 255, 255), 0.5)
    T.save_png_reserved(os.path.join(ev_dir, "23_line_width_profile.png"), img,
                        [(255, 255, 255), (0, 255, 255), (255, 220, 0), (0, 0, 0), (90, 90, 90), (20, 20, 20), (60, 60, 60)] + list(SEG_COLORS.values()))


if __name__ == "__main__":
    sys.exit(main())
