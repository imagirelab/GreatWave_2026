# -*- coding: utf-8 -*-
"""編号23 原画基準の抽出（半自動）。入力は原画 Met_JP1847.jpg と手入力の注記だけ。

使い方（リポジトリ根で）:
    py -3.10 Tools/PaintingTruth/extract.py [--evidence Docs/Evidence/ArtFirst/23]

出力:
    Tools/PaintingTruth/targets/            凍結する真値（被覆率 PNG、折れ線 JSON、調色板 JSON、manifest）
    Tools/PaintingTruth/build/              再生成できる中間物（表示フレームの原画など。Git に入れない）
    <evidence>/23_*.png                     人が確かめるための 1920×1080 重ね図
"""
import argparse
import datetime
import os
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
    C = np.asarray(centers, np.float64).copy()
    for _ in range(iters):
        d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        k = d.argmin(1)
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
    # 手動の障壁なし（v0 と同じ規則）の空。確認用の図（修正前後の比較）にだけ使い、真値には入れない。
    sky_no_barrier = T.segment_sky(lab_ref, ex["sky"], fills)
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
        boats[name] = T.boat_mask(ochre, polys[key]["points"])
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
            "lab": [round(float(v), 4) for v in med],
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
        "reference_sha256": spec["reference"]["sha256"],
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
        "description_ja": "主浪の外周（左端→波頭→唇先端）と内側輪郭（唇先端→内壁の下端）。爪なし包絡版。claw_zone 内は空マスクの水側に閉じ（半径 20 参照 px）→開き（半径 10）→ガウス σ4 をかけた形。生成器（編号24/26）の K* 中央剖面の入力。",
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
            {"id": "fuji_ridge", "backlog": [74, 161], "family": "sky", "select": "fuji_zone 内の空境界点", "source": "auto+manual", "note_ja": "報告項目（編号27）"},
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

    # ---- 重ね図（人の確認用）
    make_overlays(spec, fmap, disp_rgb, cov, env, claws, regions, palette, label_img, sky_dark, boats, ev_dir)
    make_fix_figures(fmap, disp_rgb, ref_rgb, sky_claws, sky_no_barrier, zone, env, claws, man, ev_dir)

    # ---- manifest
    outs = sorted(
        [os.path.join(dp, f) for dp, _, fs in os.walk(T.TARGET_DIR) for f in fs if f != "truth_manifest.json"])
    manifest = {
        "schema": "GreatWave.PaintingTruth.manifest/1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "command": "py -3.10 Tools/PaintingTruth/extract.py --evidence " + args.evidence,
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "os": platform.platform()},
        "inputs": {T.repo_rel(p): T.sha256_file(p) for p in [
            T.repo_abs(spec["reference"]["path"]), T.SPEC_PATH, T.MANUAL_PATH,
            os.path.join(T.HERE, "truthlib.py"), os.path.abspath(__file__)]},
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
    _label(img, "23 PaintingTruth v0: envelope (thick) / claws (thin white) / display 1920x1080, bars excluded", (170, 1068), (255, 255, 255), 0.55)
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


def make_fix_figures(fmap, disp, ref, sky_claws, sky_no_barrier, zone, env, claws, man, ev_dir):
    """修正1回目の確認図。唇の右端の拡大（表示 px の 5 倍、両方の折れ線）と、claw_zone 全体の空の斜線図（障壁なし／あり）。"""
    bars = man.get("barriers_ref", {})
    # 4) 唇の右端の拡大（表示 px 850-1234, 190-406 を 5 倍）
    x0, y0, z = 850, 190, 5
    x1, y1 = x0 + 1920 // z, y0 + 1080 // z
    big = cv2.resize(disp[y0:y1, x0:x1], (1920, 1080), interpolation=cv2.INTER_LINEAR)
    big = (big.astype(np.float32) * 0.85 + 255 * 0.15).astype(np.uint8)
    tr = lambda P: (np.asarray(P, np.float64) + 0.5 - [x0, y0]) * z - 0.5
    for k, v in bars.items():
        P = tr(T.poly_to_disp(fmap, v["points"]))
        _poly(big, P, BARRIER_COLOR, int(round(v["width_ref_px"] * fmap.s * z)))
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
    _label(big, "23 lip close-up (display px %d-%d, %d-%d, x%d): envelope=colour (132 blue, 72 purple), claws=white, manual barriers=magenta"
           % (x0, x1, y0, y1, z), (20, 1040), (255, 255, 255), 0.7)
    _label(big, "truth v0.1: the claw cluster at the lip end is water; the indigo-line gaps were closed by 3 manual barriers", (20, 1068), (255, 255, 255), 0.7)
    save_quantized(os.path.join(ev_dir, "23_lip_closeup_x5.png"), big, [BARRIER_COLOR])

    # 5) claw_zone 全体の空（斜線）。左 = 障壁なし（v0 と同じ規則）、右 = 障壁あり（v0.1 の真値）
    zp = np.array(man["polygons_ref"]["claw_zone"]["points"])
    bx0, by0 = int(zp[:, 0].min()) - 5, int(zp[:, 1].min()) - 5
    bx1, by1 = int(zp[:, 0].max()) + 6, int(zp[:, 1].max()) + 6
    zs = min(930.0 / (bx1 - bx0), 990.0 / (by1 - by0))
    W, H = int(round((bx1 - bx0) * zs)), int(round((by1 - by0) * zs))
    canvas = np.full((1080, 1920, 3), 24, np.uint8)
    changed = sky_no_barrier != sky_claws
    for k, (skym, title) in enumerate(((sky_no_barrier, "without manual barriers (same rule as v0): sky = red hatch"),
                                       (sky_claws, "truth v0.1 (3 manual barriers, magenta): sky = red hatch"))):
        crop = cv2.resize(ref[by0:by1, bx0:bx1], (W, H), interpolation=cv2.INTER_LINEAR)
        m = cv2.resize(skym[by0:by1, bx0:bx1].astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST).astype(bool)
        yy, xx = np.mgrid[0:H, 0:W]
        crop[m & (((xx + yy) // 2) % 5 == 0)] = HATCH_COLOR
        ch = cv2.resize(changed[by0:by1, bx0:bx1].astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
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
        _label(canvas, title, (ox, 38), (255, 255, 255), 0.6)
    _label(canvas, "23 claw_zone (ref px %d-%d, %d-%d, x%.2f). yellow outline = changed pixels (%d sky -> water, %d water -> sky, ref px)"
           % (bx0, bx1, by0, by1, zs, int((sky_no_barrier & ~sky_claws).sum()), int((~sky_no_barrier & sky_claws).sum())),
           (20, 1068), (255, 255, 255), 0.6)
    T.save_png_reserved(os.path.join(ev_dir, "23_claw_zone_sky_tint.png"), canvas,
                        [HATCH_COLOR, CHANGED_COLOR, ZONE_COLOR, BARRIER_COLOR, (255, 255, 255), (0, 0, 0)])


if __name__ == "__main__":
    sys.exit(main())
