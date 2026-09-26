# -*- coding: utf-8 -*-
"""番号27：Unity の描画を番号23 の評価器で測り、証拠一式（PNG・MP4・metrics.json・run.json）を作る。

使い方（リポジトリ根で）: py -3.10 Tools/GWContext/af27_evidence.py [--ffmpeg PATH] [--ffprobe PATH]
前提: af27_sky.py → af27_place.py → Unity（AF27ContextBuilder.Dump、AF27ContextScene.BuildAndRender）の順に実行済み。
ffmpeg の場所は --ffmpeg、環境変数 GW_FFMPEG、既定値の順に決める（番号24 と同じ）。
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys

import cv2
import numpy as np

import af27common as C
from af27common import T

sys.path.insert(0, C.PT_DIR)
import evaluate as E  # noqa: E402
import af27_sky as S  # noqa: E402

DEFAULT_FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
B = C.BUILD
EV = C.EVIDENCE
BAND_STEP_MAX = 1.0   # 213「余分な帯状段差がない」を、この番号では「描画の空が、量子化前のドームの式（滑らかな色の表）から 8bit で 1 段を超えて外れない」と読む


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("失敗: %s\n%s" % (" ".join(cmd), r.stderr[-2000:]))
    return r.stdout


def resolve_ffmpeg(a_ff, a_fp):
    if a_ff:
        ff, src = a_ff, "--ffmpeg"
    elif os.environ.get("GW_FFMPEG"):
        ff, src = os.environ["GW_FFMPEG"], "環境変数 GW_FFMPEG"
    else:
        ff, src = DEFAULT_FFMPEG, "既定値"
    if a_fp:
        fp, fsrc = a_fp, "--ffprobe"
    elif os.environ.get("GW_FFPROBE"):
        fp, fsrc = os.environ["GW_FFPROBE"], "環境変数 GW_FFPROBE"
    else:
        d, b = os.path.split(ff)
        fp, fsrc = os.path.join(d, b.lower().replace("ffmpeg", "ffprobe")), "ffmpeg と同じフォルダー"
    return {"ffmpeg": ff, "ffmpeg_source": src, "ffprobe": fp, "ffprobe_source": fsrc}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def r4(v, n=4):
    if v is None:
        return None
    if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
        return str(v)
    return round(float(v), n)


def ids_to_cov(ids, rgb):
    m = np.all(ids == np.array(rgb, np.uint8)[None, None, :], axis=-1).astype(np.float64)
    return m.reshape(C.H, 2, C.W, 2).mean((1, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffmpeg")
    ap.add_argument("--ffprobe")
    a = ap.parse_args()
    ff = resolve_ffmpeg(a.ffmpeg, a.ffprobe)
    os.makedirs(EV, exist_ok=True)
    eval_dir = os.path.join(B, "eval")
    os.makedirs(eval_dir, exist_ok=True)
    render = os.path.join(B, "27_painting_tstar.png")
    ids_p = os.path.join(B, "27_painting_tstar_ids.png")
    idmap_p = os.path.join(B, "27_idmap.json")
    # ---- 1) 評価器（番号23、ID モード、包絡版で判定）
    cmd_eval = [sys.executable, os.path.join(C.PT_DIR, "evaluate.py"), "--render", render, "--ids", ids_p, "--idmap", idmap_p,
                "--out-dir", eval_dir, "--name", "27_painting_tstar"]
    run(cmd_eval)
    M = C.load_json(os.path.join(eval_dir, "metrics.json"))
    items = M["items"]

    def meas(k, target=None):
        for m in items[k]["measures"]:
            if target is None or m.get("target") == target:
                return m
        return None

    tr = E.Truth()
    spec, fm = tr.spec, tr.fmap
    rgb = T.imread_rgb(render)
    ids = T.imread_rgb(ids_p)
    idmap = C.load_json(idmap_p)
    sky_r = ids_to_cov(ids, idmap["classes"]["sky"])
    lab_r = T.srgb8_to_lab(rgb)
    RR = C.load_json(os.path.join(B, "af27_render_report.json"))
    BR = C.load_json(os.path.join(B, "af27_build_report.json"))
    PF = C.load_json(os.path.join(B, "place", "place_fit.json"))
    SK = C.load_json(C.SKY_JSON)
    LAY = C.load_json(C.LAYOUT_JSON)

    # ---- 2) 76 の境界を、何が境を作っているかで分ける（真値→描画の距離、記録）
    reg = {"sky": sky_r}
    for k in ("boat_left", "boat_mid", "boat_fg"):
        reg[k] = ids_to_cov(ids, idmap["classes"][k])
    dark_r = T.sky_dark_mask(lab_r, sky_r, tr.L_mid, spec["extraction"]["sky_dark"], fm)
    rp_dark = T.boundary_points(dark_r, spec, fm)
    Fd = tr.fam["sky_dark"]
    tpts = Fd["pts"]
    is_tr = Fd["sel"]["sky_transition"]
    Fc = tr.fam["sky_claws"]
    dd, ii = T.nearest(tpts, Fc["pts"])
    lab_near = Fc["label"][ii]
    mid_cov = tr.cov["boat_mid"] > 0.5
    mid_near = cv2.dilate(mid_cov.astype(np.uint8), T.disk(12)).astype(bool)
    cls = np.where(is_tr, "transition", lab_near).astype(object)
    xi = np.clip(np.round(tpts[:, 0]).astype(int), 0, C.W - 1)
    yi = np.clip(np.round(tpts[:, 1]).astype(int), 0, C.H - 1)
    cls[(~is_tr) & mid_near[yi, xi]] = "boat_mid"
    cls[(~is_tr) & (cls == "other")] = "other_waves"
    d_tr, _ = T.nearest(tpts, rp_dark)
    breakdown = {}
    for c in sorted(set(cls)):
        s = cls == c
        breakdown[c] = {"n_truth_points": int(s.sum()), "max_truth_to_render_px": r4(d_tr[s].max()), "p95_truth_to_render_px": r4(np.percentile(d_tr[s], 95))}
    # 飛沫のくぼみ（213 の最大の所）を除いた移行線
    dip = is_tr & (tpts[:, 0] > 875) & (tpts[:, 0] < 912) & (tpts[:, 1] > 652)
    tr_only = is_tr & ~dip
    rp_trans_sel = None
    res_nodip, _, _ = T.labelled_hausdorff(tpts, tr_only, rp_dark)
    # 描画の移行線（描画の暗い空の境界のうち、描画の空境界から 1 px より離れた点）。確認図に描く。
    dr, _ = T.nearest(rp_dark, T.boundary_points(sky_r, spec, fm))
    rp_trans = rp_dark[dr > 1.0]
    sf_pts = tpts[is_tr]
    # ---- 3) 空の段差（213）と、Unity の空と numpy の予測（シェーダーが式どおりか）
    sky_in = T.erode(sky_r > 0.5, 2)
    both = sky_in[1:, :] & sky_in[:-1, :]
    dstep = T.ciede2000(lab_r[1:, :][both], lab_r[:-1, :][both])
    cam = C.Cam(spec)
    yy, xx = np.mgrid[0:C.H, 0:C.W].astype(np.float64)
    EL, AZ = C.el_az(cam.ray(xx, yy))
    dome = S.Dome(SK)
    pred = S.linear_to_srgb8(dome.linear(EL, AZ))
    sel = sky_in
    diff8 = np.abs(rgb[sel].astype(int) - pred[sel].astype(int))
    dEp = T.ciede2000(lab_r[sel], T.srgb8_to_lab(pred[sel]))
    lin = np.clip(dome.linear(EL, AZ), 0, 1)
    predf = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055) * 255.0  # 量子化前の 8bit 値
    dev_float = np.abs(rgb[sel].astype(np.float64) - predf[sel])
    # 色の表そのものの滑らかさ：表示の縦 1 px（約 0.0245°）あたりの L* の変化の最大と、その変化の隣どうしの差（二階差分）の最大
    lab_lut = np.array(SK["gradient"]["lab"])
    px_per_deg = cam.focal_px * math.pi / 180.0
    dL = np.diff(lab_lut[:, 0]) / SK["gradient"]["step"] / px_per_deg
    lut_smooth = {"max_dL_per_display_px": r4(np.abs(dL).max()), "max_second_diff_L_per_px2": r4(np.abs(np.diff(dL)).max() / (SK["gradient"]["step"] * px_per_deg))}
    # 原画の空の段差（参考）
    lab_p = tr.lab_disp
    skp = T.erode(tr.cov["sky_claws"] > 0.5, 2)
    bp = skp[1:, :] & skp[:-1, :]
    dstep_p = T.ciede2000(lab_p[1:, :][bp], lab_p[:-1, :][bp])
    # ---- 4) ドームが世界に固定されていること：形成の全フレームで、右上の空の区画（波が届かない）の画素が t* と同じか
    frames = sorted(f for f in os.listdir(os.path.join(B, "frames_painting")) if f.endswith(".png"))
    ref_f = T.imread_rgb(os.path.join(B, "frames_painting", "f_%04d.png" % RR["tStarFrame"]))
    patch = (slice(10, 100), slice(1650, 1910))
    patch2 = (slice(600, 700), slice(1180, 1300))  # 暗い空の帯（右船・富士の上）
    maxd, maxd2, n2 = 0, 0, 0
    wave_free2 = sky_r[patch2].min() > 0.99
    for f in frames:
        im = T.imread_rgb(os.path.join(B, "frames_painting", f))
        maxd = max(maxd, int(np.abs(im[patch].astype(int) - ref_f[patch].astype(int)).max()))
    # ---- 5) 船と波の既定の配色（213 の後半）：描画の船の画素の中央値、非空の画素のうち調色板の色そのものの割合
    pal = C.load_json(os.path.join(T.TARGET_DIR, "palette.json"))["palette"]
    boat_px = np.zeros((C.H, C.W), bool)
    for k in ("boat_left", "boat_mid", "boat_fg"):
        boat_px |= T.erode(reg[k] > 0.99, 2)
    boat_med = np.median(lab_r[boat_px], axis=0) if boat_px.any() else None
    boat_dE = float(T.ciede2000(boat_med, np.array(pal["boat_ochre"]["lab"]))) if boat_med is not None else None
    nonsky = (sky_r < 0.01)
    nonsky[:, :fm.x0] = False
    nonsky[:, fm.x1 + 1:] = False
    cols = rgb[nonsky].reshape(-1, 3)
    uq, cnt = np.unique(cols, axis=0, return_counts=True)
    pl_lab = np.array([v["lab"] for v in pal.values()])
    uq_lab = T.srgb8_to_lab(uq)
    dmin = np.min(np.stack([T.ciede2000(uq_lab, pl_lab[i][None, :]) for i in range(len(pl_lab))], -1), -1)
    w = cnt / cnt.sum()
    near_pal = {"le_1": round(float(w[dmin <= 1.0].sum()), 4), "le_5": round(float(w[dmin <= 5.0].sum()), 4),
                "n_distinct_colours": int(len(uq))}
    # ---- 6) 証拠の画像
    ref, disp = T.painting_display(spec, fm)
    shutil.copyfile(render, os.path.join(EV, "27_painting_tstar.png"))
    blend = (0.5 * rgb.astype(np.float32) + 0.5 * disp.astype(np.float32)).astype(np.uint8)
    blend[:, :fm.x0] = (blend[:, :fm.x0] * 0.35).astype(np.uint8)
    blend[:, fm.x1 + 1:] = (blend[:, fm.x1 + 1:] * 0.35).astype(np.uint8)
    cv2.putText(blend, "27 context (Unity PC offscreen, t*=12.0s, PaintingCam v1) + Met JP1847 50%", (170, 1066),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    T.save_png_reserved(os.path.join(EV, "27_painting_overlay.png"), blend, [(255, 255, 255)])
    idv = ids[::2, ::2].copy()
    T.save_png_reserved(os.path.join(EV, "27_painting_ids.png"), idv, [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 0)])
    shutil.copyfile(os.path.join(eval_dir, "27_painting_tstar_overlay.png"), os.path.join(EV, "27_contour_overlay.png"))
    sky_detail(os.path.join(EV, "27_sky_detail.png"), os.path.join(eval_dir, "27_painting_tstar_overlay.png"), disp, rgb, tr, sf_pts, rp_trans)
    sky_profile(os.path.join(EV, "27_sky_profile.png"), tr, SK, cam, EL, AZ, rgb, sky_r)
    for n in ("27_boat_tstar.png", "27_side_tstar.png", "27_overview_tstar.png"):
        shutil.copyfile(os.path.join(B, n), os.path.join(EV, n))
    tiles = [cv2.resize(T.imread_rgb(os.path.join(B, "27_contact_%s.png" % k)), (960, 540), interpolation=cv2.INTER_AREA) for k in ("boat_fg", "boat_mid", "boat_left")]
    info = np.full((540, 960, 3), 24, np.uint8)
    lines = ["27 contact check (Unity PC offscreen, t*): boat + its support + sky dome only",
             "top-left: boat_fg (seat boat) on the flat sea",
             "top-right: boat_mid on the right-slope placeholder",
             "bottom-left: boat_left on the left-support placeholder"]
    for c in RR["contacts"]:
        lines.append("%s: keel mid %.2f m below surface, lowest hull pt %.2f m below" % (c["boat"], c["keelMidBelowSurface"], c["penetration"]))
    for i, t in enumerate(lines):
        cv2.putText(info, t, (20, 50 + 40 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
    T.imwrite(os.path.join(EV, "27_contact.png"), np.vstack([np.hstack(tiles[:2]), np.hstack([tiles[2], info])]))
    # MP4（形成の全区間、PaintingCam）
    mp4 = os.path.join(EV, "27_formation_painting.mp4")
    run([ff["ffmpeg"], "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(B, "frames_painting", "f_%04d.png"),
         "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4])
    vinfo = json.loads(run([ff["ffprobe"], "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height,r_frame_rate,nb_read_frames,duration", "-of", "json", mp4]))["streams"][0]

    # ---- 7) metrics.json
    def ver(v, thr):
        return None if v is None else ("pass" if v <= thr else "fail")
    m76c, m76d, m213c, m212 = meas("76", "sky_dark"), meas("76", "sky_bottom"), meas("213", "sky_transition"), meas("212", "sky_top")
    mboat = meas("213", "boat_ochre")
    step_max = float(dstep.max())
    seat = PF["seat"]
    boats = {k: {kk: v[kk] for kk in ("role_ja", "depth_plane_m", "position", "rotation_quat_xyzw", "scale", "tip_to_tip_length_m", "roll_about_axis_deg",
                                      "iou_target", "iou_m1_revision01", "fit", "tips_used_px", "landmarks_px", "keel_mid_point", "draft_m")}
             for k, v in PF["boats"].items()}
    # keelMaxAboveSurface は竜骨の中線ではなく、船の根の空間 z = +5 の端の船首／船尾材の 36 頂点の「面より上に出ている量」の最大
    # （AF27ContextScene.Contacts() の注記）。記録の名前もそれに合わせる。
    contacts = {c["boat"]: {"support": c["support"], "keel_mid_below_surface_m": r4(c["keelMidBelowSurface"]), "lowest_hull_below_surface_m": r4(c["penetration"]),
                            "plus_z_end_post_top_above_surface_m": r4(c["keelMaxAboveSurface"]), "pass_keel_mid_in_contact": bool(c["keelMidHit"] and c["keelMidBelowSurface"] >= 0.0)}
                for c in RR["contacts"]}
    contacts_note = ("keel_mid_below_surface_m は竜骨の中央（船の根の原点）が支えの面より下にある量、lowest_hull_below_surface_m は船体の最も低い頂点が面より下にある量。"
                     "plus_z_end_post_top_above_surface_m は、船の根の空間 z = +5 の端の船首／船尾材の 36 頂点が面より上に出ている量の最大（ほぼ材の最上点）で、"
                     "竜骨（船底の線）の浮きの量ではない（最初の版では keel_max_above_surface_m と誤って名付けていた）。船底の線の面からの高さは Step_27 の接地の表を見る。")
    out = {
        "schema": "GreatWave.Step27.metrics/1",
        "number": "27 空のドーム・船・富士の配置",
        "generated_utc": now(),
        "truth_version": spec["version"],
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor（batchmode、Direct3D11、Linear、Built-in RP）の PC オフスクリーン描画と、その PNG を番号23 の評価器（ID モード）"
                            "と numpy で測った結果。HMD 実機の結果ではない。主役波は番号24 の v0（t*）を仮に置いた。",
        "evaluator": {"metrics": C.rel(os.path.join(eval_dir, "metrics.json")), "provisional": M["provisional"], "provisional_ja": M["provisional_ja"],
                      "command": M["command"]},
        "items": {
            "76": {"backlog": 76, "requirement_ja": "暗い空の範囲が原画の対応領域から 4 px 以内、表示色の差 ΔE00 ≤ 5",
                   "value": {"contour_max_px": m76c["value_max_px"], "contour_p95_px": m76c["p95_px"], "worst_display_xy": m76c.get("worst_display_xy"),
                             "color_dE00_sky_bottom": m76d["value"], "boundary_breakdown_truth_to_render": breakdown},
                   "verdict": "fail" if (m76c["verdict"] == "fail" or m76d["verdict"] == "fail") else "pass",
                   "verdict_parts": {"contour": m76c["verdict"], "color": m76d["verdict"]},
                   "note_ja": "評価器は暗い空の境界の全体（上の移行線と、下で波・富士・右船が空を遮る所）を 4 px で測る。色は合格。境界の最大は右船の船首の所"
                              "（blockout の船が原画の三日月形と違う）で、内訳は boundary_breakdown（transition は空の中の移行線、boat_mid は右船、"
                              "72・fuji_ridge・other_waves はそれぞれ主役波の内側・富士・その他の波が遮る所）。"},
            "212": {"backlog": 212, "requirement_ja": "画面上方が水平線付近より明るく、上方の表示色と原画との色差 ΔE00 ≤ 5",
                    "value": {"color_dE00_sky_top": m212["value"], "render_lab_sky_top": m212.get("render_lab"),
                              "L_upper_minus_L_horizon": r4(float(m212["render_lab"][0]) - float(m76d["render_lab"][0]))},
                    "verdict": m212["verdict"]},
            "213": {"backlog": 213, "requirement_ja": "空の明暗移行域のずれ ≤ 4 px、余分な帯状段差がない。波と船の既定配色は ΔE00 ≤ 5",
                    "value": {"transition_max_px": m213c["value_max_px"], "transition_p95_px": m213c["p95_px"], "worst_display_xy": m213c.get("worst_display_xy"),
                              "transition_max_px_excluding_spray_dip": r4(res_nodip.get("max_px")), "transition_p95_px_excluding_spray_dip": r4(res_nodip.get("p95_px")),
                              "band_step_render_minus_float_dome_max_8bit": r4(dev_float.max()), "band_step_lut_smoothness": lut_smooth,
                              "band_step_adjacent_rows_dE00_max_record": r4(step_max), "band_step_adjacent_rows_dE00_p99_record": r4(np.percentile(dstep, 99)),
                              "band_step_painting_adjacent_rows_dE00_p99_record": r4(np.percentile(dstep_p, 99)),
                              "boat_ochre_region_dE00_evaluator": mboat["value"], "boat_pixels_median_dE00_vs_palette": r4(boat_dE),
                              "nonsky_pixels_nearest_palette_dE00_fraction": near_pal},
                    "verdict": "fail" if (m213c["verdict"] == "fail" or dev_float.max() > BAND_STEP_MAX or (boat_dE is not None and boat_dE > 5)) else "pass",
                    "verdict_parts": {"transition_4px": m213c["verdict"], "band_step": ver(float(dev_float.max()), BAND_STEP_MAX),
                                      "default_colours_boat": ver(boat_dE, 5.0)},
                    "note_ja": "移行線の最大は表示 (895, 668) の 1 か所（原画の飛沫の白点が暗い空の帯の上端にかかり、真値の移行線が約 17 px くぼむ所）。"
                               "そこを除くと最大は transition_max_px_excluding_spray_dip。段差は、描画の空が量子化前のドームの式から 8bit で 1 段を超えて"
                               "外れないこと（量子化の段だけ）と、色の表が滑らかなこと（band_step_lut_smoothness）で見た。この基準はこの番号で決めた読み方で、"
                               "バックログに数値はない。隣り合う画素の ΔE00（記録）は原画のぼかしの急な所で 1 を少し超えるが、原画自体の隣り合う画素の差（紙の質感）より小さい。"
                               "波の既定配色は番号24 v0 の仮の平塗り（真値 v0.1 の調色板の 8bit 値で、v0.2 と 1 段違う色がある）なので、非空の画素ごとに"
                               "最も近い調色板の色との ΔE00 を測り、≤1・≤5 の画素の割合を記録した（残りは MSAA の縁の混色）。"},
            "94": {"backlog": 94, "requirement_ja": "原画構図の観察位置と向きは全形成区間で一定",
                   "value": {"frames": RR["renderedFrames"], "max_position_delta_m": RR["cameraMaxPositionDelta"], "max_angle_delta_deg": RR["cameraMaxAngleDeltaDeg"],
                             "max_fov_delta_deg": RR["cameraMaxFovDelta"], "max_projection_matrix_delta": RR["cameraMaxProjectionDelta"],
                             "max_view_matrix_delta": RR["cameraMaxViewDelta"], "camera_position": RR["cameraPosition"], "camera_euler": RR["cameraEuler"],
                             "sky_patch_max_abs_diff_8bit_vs_tstar": maxd},
                   "verdict": "pass" if (RR["cameraMaxPositionDelta"] == 0 and RR["cameraMaxAngleDeltaDeg"] == 0 and RR["cameraMaxFovDelta"] == 0
                                         and RR["cameraMaxProjectionDelta"] == 0 and RR["cameraMaxViewDelta"] == 0) else "fail",
                   "note_ja": "形成の全 510 フレーム（30 Hz、0〜17 s）で PaintingCam の位置・回転・画角・投影行列・ビュー行列を毎フレーム記録し、最初の値との差の最大。"
                              "sky_patch は右上の空の区画（x 1650〜1909、y 10〜99）の画素が全フレームで t* と同じか（空のドームが世界に固定され、波の形成で変わらない）。"},
            "74": {"backlog": 74, "value": {k: meas("74")[k] for k in ("value_max_px", "p95_px", "worst_display_xy") if k in meas("74")}, "verdict": "record-only",
                   "note_ja": "富士の稜線（fuji_zone 内の空境界、爪入り版）。報告項目。"},
            "161": {"backlog": 161, "value": {k: meas("161")[k] for k in ("value_max_px", "p95_px") if k in meas("161")},
                    "fuji_height_m": PF["fuji"]["height_m"], "fuji_base_width_m": PF["fuji"]["base_width_m"], "verdict": "record-only"},
            "162": {"backlog": 162, "value": {"fuji_snow_dE00": meas("162", "fuji_snow")["value"], "fuji_slope_dE00": meas("162", "fuji_slope")["value"]},
                    "verdict": "record-only", "note_ja": "原画の雪の領域の中央値と比べるので、blockout の雪の形（頂だけ）が原画（山の上半分が白）と違う分がそのまま出る。"},
            "75": {"backlog": 75, "value": {k: meas("75")[k] for k in ("value_max_px", "p95_px", "worst_display_xy") if k in meas("75")}, "verdict": "record-only"},
            "157": {"backlog": 157, "value": {k: meas("157")[k] for k in ("value_max_px", "p95_px") if k in meas("157")}, "verdict": "record-only",
                    "note_ja": "左奥の船は、仮に置いた番号24 v0 の主役波に全部隠れる（描画側の境界なし＝inf）。番号26 の K* で左下の波の形が決まってから測り直す。"},
            "159": {"backlog": 159, "value": {k: meas("159")[k] for k in ("value_max_px", "p95_px", "worst_display_xy") if k in meas("159")}, "verdict": "record-only"},
            "other_evaluator_items_record": {k: {"verdict_evaluator": v["verdict"], "measures": [{kk: mm.get(kk) for kk in ("target", "version", "value_max_px", "p95_px", "value")}
                                                                                              for mm in v["measures"]]}
                                             for k, v in items.items() if k in ("78", "130", "131", "132", "72", "71", "265")},
        },
        "sky_dome": {"theta0_deg": SK["theta0_deg"], "json": "Tools/GWContext/sky_dome.json",
                     "unity_vs_numpy_prediction": {"max_abs_8bit": int(diff8.max()), "dE00_max": r4(dEp.max()), "dE00_p99": r4(np.percentile(dEp, 99)),
                                                   "n_pixels": int(sel.sum()),
                                                   "note_ja": "Unity のシェーダーの出力と numpy の式（af27_sky.Dome）の差。空の画素（ID の空を 2 px 縮めた内側）。"}},
        "boats": boats,
        "boat_contacts": contacts,
        "boat_contacts_note_ja": contacts_note,
        "boats_no_longer_floating": all(v["pass_keel_mid_in_contact"] for v in contacts.values()),
        "seat": {"boat": seat["boat"], "eye_world_new": seat["eye_world"], "eye_world_m1_revision01": seat["eye_world_m1_revision01"],
                 "eye_moved_m": seat["eye_moved_m"], "eye_delta": seat["eye_delta"], "eye_unity": [BR["eyeUnity"][k] for k in "xyz"], "eye_unity_minus_numpy_m": BR["eyeDiff"],
                 "rule_ja": seat["rule_ja"]},
        "fuji": PF["fuji"],
        "placeholders": PF["placeholders"],
        "id_image": {"distinct_colors": RR["idDistinctColors"], "path_not_committed": C.rel(ids_p), "sha256": C.sha256(ids_p)},
        "mp4": {"path": C.rel(mp4), "info": vinfo},
    }
    C.save_json(os.path.join(EV, "metrics.json"), out)
    # ---- 8) run.json
    ins = [C.SKY_JSON, C.LAYOUT_JSON, os.path.join(C.HERE, "manual_landmarks.json")]
    ins += [os.path.join(C.HERE, f) for f in ("af27common.py", "af27_sky.py", "af27_place.py", "af27_evidence.py", "run_af27_unity.ps1")]
    ins += [C.REPO + "/" + p for p in ("Unity/Assets/GreatWave/ArtFirst/Editor/AF27ContextBuilder.cs", "Unity/Assets/GreatWave/ArtFirst/Editor/AF27ContextScene.cs",
                                        "Unity/Assets/GreatWave/ArtFirst/Shaders/AF27Flat.shader", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF27SkyDome.shader")]
    ins += [os.path.join(T.TARGET_DIR, "truth_manifest.json"), T.SPEC_PATH, os.path.join(C.PT_DIR, "evaluate.py"), os.path.join(C.PT_DIR, "truthlib.py"),
            os.path.join(C.REPO, "Docs", "Evidence", "M1", "Revision01", "15_revision_layout.json"),
            os.path.join(C.REPO, "Unity", "Build", "ArtFirst", "24", "wave", "wave_v0.gwb")]
    unity_assets = ["Unity/Assets/GreatWave/Scenes/Tests/AF27_Context.unity", "Unity/Assets/GreatWave/ArtFirst/Prefabs/AF27_Context.prefab",
                    "Unity/Assets/GreatWave/ArtFirst/Prefabs/AF27_SkyDome.prefab", "Unity/Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat",
                    "Unity/Assets/GreatWave/ArtFirst/Textures/AF27_SkyThetaT.asset", "Unity/Assets/GreatWave/ArtFirst/Textures/AF27_SkyGradient.asset"]
    unity_assets += sorted("Unity/Assets/GreatWave/ArtFirst/Materials/" + f for f in os.listdir(os.path.join(C.REPO, "Unity/Assets/GreatWave/ArtFirst/Materials"))
                           if f.startswith("AF27_Flat_") and f.endswith(".mat"))
    ev_files = sorted(os.path.join(EV, f) for f in os.listdir(EV) if f not in ("run.json",))
    nc = [os.path.join(B, n) for n in ("27_painting_tstar.png", "27_painting_tstar_ids.png", "27_idmap.json", "27_boat_tstar.png", "27_side_tstar.png",
                                        "27_overview_tstar.png", "27_contact_boat_fg.png", "27_contact_boat_mid.png", "27_contact_boat_left.png",
                                        "af27_build_report.json", "af27_render_report.json", "place/place_fit.json", "place/place_fit.png",
                                        "sky/sky_prediction.json", "eval/metrics.json", "eval/27_painting_tstar_overlay.png", "dump/dump.json")]
    h = hashlib.sha256()
    for f in frames:
        h.update(f.encode())
        with open(os.path.join(B, "frames_painting", f), "rb") as fh:
            h.update(fh.read())
    ffv = run([ff["ffmpeg"], "-version"]).splitlines()[0]
    R = {
        "schema": "GreatWave.Step27.run/1",
        "generated_utc": now(),
        "cwd": "リポジトリ根（G:/Unity/GreatWave_2026_Fresh）",
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWContext/run_af27_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF27ContextBuilder.Dump -Log dump",
            "py -3.10 Tools/GWContext/af27_sky.py",
            "py -3.10 Tools/GWContext/af27_place.py",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWContext/run_af27_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF27ContextScene.BuildAndRender -Log build_render",
            "py -3.10 Tools/GWContext/af27_evidence.py（内部で Tools/PaintingTruth/evaluate.py と ffmpeg を呼ぶ）",
        ],
        "unity_lock_ja": "Unity は run_af27_unity.ps1 が Unity/Build/unity.lock を排他的に作ってから起動し、終了後に消した（同じプロジェクトで1プロセスだけ）。",
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": __import__("PIL").__version__,
                  "unity": RR["unity"], "unity_device": RR["device"], "unity_api": RR["graphicsApi"], "unity_color_space": RR["colorSpace"],
                  "ffmpeg": ffv, "os": platform.platform(), "houdini": None, "blender": None},
        "ffmpeg_resolved": ff,
        "unity_render_seconds": RR["totalSeconds"],
        "inputs": {C.rel(p): C.sha256(p) for p in ins},
        "outputs_committed": {C.rel(p): C.sha256(p) for p in ev_files},
        "unity_assets": {p: C.sha256(os.path.join(C.REPO, p)) for p in unity_assets},
        "tools_outputs": {C.rel(p): C.sha256(p) for p in (C.SKY_JSON, C.LAYOUT_JSON)},
        "not_committed": {C.rel(p): C.sha256(p) for p in nc},
        "not_committed_frames": {"dir": C.rel(os.path.join(B, "frames_painting")), "count": len(frames), "sha256_of_names_and_bytes": h.hexdigest()},
        "not_committed_ja": "Unity/Build/ArtFirst/27/ は既存の .gitignore（/Unity/Build/）で Git 対象外。ID 画像（3840×2160）、Unity の生の描画、形成の全フレーム、評価器の生出力、報告 JSON。",
        "reference_model_ja": "参照モデル（Q5 の wave_repair_zbrush2.obj）はこの番号では開いていない（D20 の既定値：船・前景の小波は 27/39 で使わない）。",
    }
    C.save_json(os.path.join(EV, "run.json"), R)
    print(json.dumps({k: out["items"][k]["verdict"] for k in ("76", "212", "213", "94")}, ensure_ascii=False))
    print("76", out["items"]["76"]["value"]["contour_max_px"], out["items"]["76"]["value"]["color_dE00_sky_bottom"])
    print("213", out["items"]["213"]["value"]["transition_max_px"], out["items"]["213"]["value"]["transition_max_px_excluding_spray_dip"],
          "band", step_max, "float dev", float(dev_float.max()))
    print("breakdown", breakdown)
    print("unity vs numpy", out["sky_dome"]["unity_vs_numpy_prediction"])
    print("contacts", contacts)


def sky_detail(path, overlay_path, disp, rgb, tr, sf_pts, rp_trans):
    """暗い空の帯の拡大（上：評価器の偏差図、下：原画と描画の半々、どちらも 2.4 倍）。"""
    ov = T.imread_rgb(overlay_path)
    x0, x1, y0, y1 = 840, 1640, 600, 820
    a = cv2.resize(ov[y0:y1, x0:x1], None, fx=2.4, fy=2.4, interpolation=cv2.INTER_NEAREST)[:, :1920]
    bl = (0.5 * rgb[y0:y1, x0:x1].astype(np.float32) + 0.5 * disp[y0:y1, x0:x1].astype(np.float32)).astype(np.uint8)
    for p in sf_pts:
        if x0 <= p[0] < x1 and y0 <= p[1] < y1:
            bl[int(round(p[1])) - y0, int(round(p[0])) - x0] = (255, 0, 255)
    for p in rp_trans:
        if x0 <= p[0] < x1 and y0 <= p[1] < y1:
            bl[int(round(p[1])) - y0, int(round(p[0])) - x0] = (0, 255, 0)
    b = cv2.resize(bl, None, fx=2.4, fy=2.4, interpolation=cv2.INTER_NEAREST)[:, :1920]
    img = np.zeros((1080, 1920, 3), np.uint8)
    img[:528] = a[:528]
    img[540:1068] = b[:528]
    cv2.putText(img, "top: evaluator overlay x2.4 (display x 840-1640, y 600-820). cyan=truth, green<=2px yellow<=4px red>4px", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, "bottom: render/painting 50% x2.4. green=render transition, magenta=truth transition (213). spray dots at x~885-905 make the truth dip", (10, 560),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    T.save_png_reserved(path, img, [(255, 255, 255), (0, 255, 0), (255, 0, 255), (0, 255, 255), (60, 230, 60), (255, 220, 0), (255, 40, 40), (255, 60, 60)])


def sky_profile(path, tr, SK, cam, EL, AZ, rgb, sky_r):
    """仰角 e' ごとの L*・b*：原画（灰）、ドームの表（赤）、Unity の描画（青）。1920×1080。"""
    dome = S.Dome(SK)
    lab_p = tr.lab_disp
    lab_r = T.srgb8_to_lab(rgb)
    sp = tr.cov["sky_claws"] > 0.5
    sr = sky_r > 0.99
    EP = dome.eprime(EL, AZ)
    img = np.full((1080, 1920, 3), 255, np.uint8)
    e_lo, e_hi = -0.5, 20.0

    def X(e):
        return (80 + (np.asarray(e) - e_lo) / (e_hi - e_lo) * 1800).astype(int)

    panels = ((0, 40, 100, 60, 560, "L*"), (2, 0, 25, 620, 1020, "b*"))
    bins = np.arange(e_lo, e_hi, 0.05)
    for c, lo, hi, top, bot, name in panels:
        Y = lambda v: (bot - (np.asarray(v) - lo) / (hi - lo) * (bot - top)).astype(int)
        cv2.rectangle(img, (80, top), (1880, bot), (200, 200, 200), 1)
        cv2.putText(img, name, (20, (top + bot) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        for v in range(lo, hi + 1, 10 if c == 0 else 5):
            cv2.putText(img, str(v), (40, int(Y(v)) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
            cv2.line(img, (80, int(Y(v))), (1880, int(Y(v))), (235, 235, 235), 1)
        for src, m, col in ((lab_p, sp, (150, 150, 150)), (lab_r, sr, (40, 60, 220))):
            idx = np.digitize(EP[m], bins)
            vals = src[..., c][m]
            for bi in range(1, len(bins)):
                s = idx == bi
                if s.sum() > 30:
                    cv2.circle(img, (int(X(bins[bi - 1] + 0.025)), int(Y(np.median(vals[s])))), 2, col, -1)
        e = dome.e
        lab_lut = np.array(SK["gradient"]["lab"])
        s = (e >= e_lo) & (e <= e_hi)
        cv2.polylines(img, [np.stack([X(e[s]), Y(lab_lut[s, c])], -1).astype(np.int32)], False, (220, 40, 40), 2)
        cv2.line(img, (int(X(SK["theta0_deg"])), top), (int(X(SK["theta0_deg"])), bot), (40, 160, 40), 1)
    for e in range(0, 21, 2):
        cv2.putText(img, str(e), (int(X(e)) - 6, 1045), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.putText(img, "27 sky dome: median per 0.05 deg of e' (warped world elevation). gray=painting sky, blue=Unity render sky, red=dome LUT, green=theta0",
                (80, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "e' (deg)", (900, 1072), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    T.imwrite(path, img)


if __name__ == "__main__":
    main()
