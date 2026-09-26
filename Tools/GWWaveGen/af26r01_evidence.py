# -*- coding: utf-8 -*-
"""番号26修正01（唇を波峰方向へ延ばし、波峰全体を巻かせる、45°）の証拠一式をまとめる。
gw_wavegen_v2 → af26r01_views.py → Unity（AF26R01KStar）→ Blender（af26r01_blender.py）→ 参照モデルの比較（af26r01_reference.py）の後に実行する。

入力（Git 対象外）:
    Unity/Build/ArtFirst/26修正01/kstar/（K* v2）、render/（Unity の描画・ID 画像）、af26r01_views.json、af26r01_build_report.json、af26r01_render_report.json、
    blender/af26r01_blender.json・cmp_*.png、ref/26R01_ref_*.png・26R01_ref_compare.json
    Unity/Build/ArtFirst/26/kstar/kstar_a45_*（CP1 の K* 45°、比較用）、Unity/Build/ArtFirst/27R01/place/af27r01_place.json・eval/noline/metrics.json
入力（Git 対象）: Tools/GWContext/seat_v1.json、Tools/PaintingTruth/ の真値 v0.2 と評価器
出力: Docs/Evidence/ArtFirst/26R01/（図、metrics.json、run.json）、Unity/Build/ArtFirst/26修正01/eval/（評価器の出力）、orbit の MP4

使い方（リポジトリ根で）: py -3.10 Tools/GWWaveGen/af26r01_evidence.py
"""
import datetime
import glob
import json
import math
import os
import platform
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import gw_wavegen as G0  # noqa: E402

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01")
RDIR = os.path.join(BUILD, "render")
KDIR = os.path.join(BUILD, "kstar")
K26 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26", "kstar")
R27 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "27R01")
EVID = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "26R01")
SEAT_JSON = os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")
FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
REC = []


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def r4(v, n=4):
    if v is None:
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return [r4(x, n) for x in v]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    v = float(v)
    if math.isinf(v) or math.isnan(v):
        return str(v)
    return round(v, n)


def font(size):
    try:
        return ImageFont.truetype(FONT_R, size)
    except OSError:
        return ImageFont.load_default()


def label(img, lines, xy=(20, 16), size=24, fill=(255, 255, 255)):
    im = Image.fromarray(np.ascontiguousarray(img))
    dr = ImageDraw.Draw(im)
    f = font(size)
    if lines:
        w = max(dr.textlength(s, font=f) for s in lines)
        dr.rectangle([xy[0] - 8, xy[1] - 6, xy[0] + w + 8, xy[1] + len(lines) * (size + 8) + 2], fill=(20, 20, 20))
    for i, s in enumerate(lines):
        dr.text((xy[0], xy[1] + i * (size + 8)), s, font=f, fill=fill)
    return np.array(im)


def tile(path, w=960, h=540):
    return cv2.resize(T.imread_rgb(path), (w, h), interpolation=cv2.INTER_AREA)


def run_eval(render, ids, idmap, out_dir, name):
    cmd = [sys.executable, os.path.join(REPO, "Tools", "PaintingTruth", "evaluate.py"), "--render", render, "--ids", ids,
           "--idmap", idmap, "--out-dir", out_dir, "--name", name]
    subprocess.run(cmd, check=True, cwd=REPO, stdout=subprocess.DEVNULL)
    REC.append("py -3.10 Tools/PaintingTruth/evaluate.py --render %s --ids %s --idmap %s --out-dir %s --name %s" % (
        T.repo_rel(render), T.repo_rel(ids), T.repo_rel(idmap), T.repo_rel(out_dir), name))
    return T.load_json(os.path.join(out_dir, "metrics.json"))


def measures(em):
    out = {}
    for key, it in em["items"].items():
        for m in it["measures"]:
            out[(key, m.get("target"), m.get("version"))] = m
    return out


def mval(m):
    return m.get("value_max_px") if m.get("value_max_px") is not None else m.get("value")


def boat_stats(ids, color):
    mk = np.all(ids == np.array(color, np.uint8), -1)
    ys, xs = np.nonzero(mk)
    if not len(xs):
        return mk, None
    return mk, [float(xs.min()) / 2, float(ys.min()) / 2, float(xs.max()) / 2, float(ys.max()) / 2]


def main():
    os.makedirs(EVID, exist_ok=True)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    cam = G0.PaintingCam(spec)
    S = T.load_json(SEAT_JSON)
    eye = np.array(S["seat"]["eye_world"], float)
    meta = T.load_json(os.path.join(KDIR, "kstar_a45_meta.json"))
    rows = np.load(os.path.join(KDIR, "kstar_a45_rows.npz"))
    meta26 = T.load_json(os.path.join(K26, "kstar_a45_meta.json"))
    rows26 = np.load(os.path.join(K26, "kstar_a45_rows.npz"))
    views = T.load_json(os.path.join(BUILD, "af26r01_views.json"))
    rep_b = T.load_json(os.path.join(BUILD, "af26r01_build_report.json"))
    rep_r = T.load_json(os.path.join(BUILD, "af26r01_render_report.json"))
    bl = T.load_json(os.path.join(BUILD, "blender", "af26r01_blender.json"))
    refc = T.load_json(os.path.join(BUILD, "ref", "26R01_ref_compare.json")) if os.path.exists(os.path.join(BUILD, "ref", "26R01_ref_compare.json")) else None
    place = T.load_json(os.path.join(R27, "place", "af27r01_place.json"))
    idmap_p = os.path.join(RDIR, "idmap.json")
    idmap = T.load_json(idmap_p)

    # ---------------------------------------------------------------- 評価器（原画視点、外殻線なしの ID、番号26 と同じ条件）
    em = run_eval(os.path.join(RDIR, "af26r01_painting_r01.png"), os.path.join(RDIR, "af26r01_painting_ids.png"), idmap_p,
                  os.path.join(BUILD, "eval", "r01"), "af26r01_painting")
    emc = run_eval(os.path.join(RDIR, "af26r01_painting_cp1.png"), os.path.join(RDIR, "af26r01_painting_ids_cp1k.png"), idmap_p,
                   os.path.join(BUILD, "eval", "cp1k"), "af26r01_painting_cp1k")
    em27 = T.load_json(os.path.join(R27, "eval", "noline", "metrics.json"))
    M, Mc, M27 = measures(em), measures(emc), measures(em27)
    compare = []
    for (key, tgt, ver), m in sorted(M.items(), key=lambda kv: str(kv[0])):
        if key == "line_width":
            continue
        c1, c27 = Mc.get((key, tgt, ver)), M27.get((key, tgt, ver))
        a, b = mval(m), (mval(c1) if c1 else None)
        compare.append({"item": key, "target": tgt, "version": ver, "r01": r4(a), "r01_p95": r4(m.get("p95_px")), "verdict_r01": m.get("verdict"),
                        "cp1_kstar_same_scene": r4(b), "cp1_kstar_p95": r4(c1.get("p95_px")) if c1 else None,
                        "27R01_noline": r4(mval(c27)) if c27 else None,
                        "delta_vs_cp1_kstar": r4(a - b) if (isinstance(a, (int, float)) and isinstance(b, (int, float))) else None,
                        "worst_display_xy": m.get("worst_display_xy")})
    cmpd = {(c["item"], c["target"]): c for c in compare}

    def cv(item, target):
        return cmpd.get((item, target), {})

    # ---------------------------------------------------------------- 原画視点の ID の差（CP1 の K* と 26修正01 の K*、同じ場面）
    ids_new = T.imread_rgb(os.path.join(RDIR, "af26r01_painting_ids.png"))
    ids_old = T.imread_rgb(os.path.join(RDIR, "af26r01_painting_ids_cp1k.png"))
    sky_n = np.all(ids_new == np.array(idmap["classes"]["sky"], np.uint8), -1)
    sky_o = np.all(ids_old == np.array(idmap["classes"]["sky"], np.uint8), -1)
    xor_sky = sky_n ^ sky_o
    mid_new, bbox_new = boat_stats(ids_new, idmap["classes"]["boat_mid"])
    # ---------------------------------------------------------------- 68・69・70
    fr = meta["frame"]
    e = np.array(fr["e_crest"]); t = np.array(fr["t_travel"]); O0 = np.array(fr["section_origin_world"])
    idx = meta["profile"]["index"]
    jt, jp, jk, jf = idx["j_top"], idx["j_tip"], idx["j_corner"], idx["j_facebot"]
    c, A, Y = rows["c"], rows["A"], rows["Y"]
    vm = meta["rows"]["main_row"]

    def world(v, j):
        return O0 + c[v] * e + A[v, j] * t + np.array([0.0, Y[v, j], 0.0])
    tip = world(vm, jt + int(np.argmax(A[vm, jt:jk + 1])))
    fb = world(vm, jf)
    cr = world(vm, jt)
    d_tip = math.hypot(*(tip - eye)[[0, 2]])
    d_fb = math.hypot(*(fb - eye)[[0, 2]])
    # 唇先が頂より 0.2H 以上前に出る行すべてで同じ式（記録）。この行の判定は、curl_along_crest の「巻きのある行」
    # （0.3H の高さの内壁から唇先までの張り出し ≥0.2H、gw_wavegen v2 の meta の curl）とは別なので、両方で数える。
    H = Y.max(1)
    crun = meta["curl"]["longest_curl_run_c_range_m"]
    n_ok = n_all = n_ok_curl = n_all_curl = 0
    for v in range(len(c)):
        if H[v] < 2.0:
            continue
        tp_ = world(v, jt + int(np.argmax(A[v, jt:jk + 1])))
        fb_ = world(v, jf)
        ok_ = int(math.hypot(*(tp_ - eye)[[0, 2]]) < math.hypot(*(fb_ - eye)[[0, 2]]))
        if crun and crun[0] - 1e-6 <= c[v] <= crun[1] + 1e-6:
            n_all_curl += 1
            n_ok_curl += ok_
        a_tip = A[v, jt:jk + 1].max()
        if a_tip - A[v, jt] < 0.2 * H[v]:
            continue
        n_all += 1
        n_ok += ok_
    sea_below = O0 + A[vm, jt] * t
    p_crest, p_sea = cam.project(np.stack([cr, sea_below]))
    wave_vert_px = float(p_sea[1] - p_crest[1])
    tips_px = np.array(place["tips_projected_px"])
    boat_len_px = float(np.linalg.norm(tips_px[0] - tips_px[1]))
    tips_in = bool(np.all((tips_px[:, 0] > fm.x0) & (tips_px[:, 0] < fm.x1) & (tips_px[:, 1] > 0) & (tips_px[:, 1] < 1080)))
    boat_in = bool(bbox_new and bbox_new[0] > fm.x0 and bbox_new[2] < fm.x1)

    # ---------------------------------------------------------------- 巻き・端・唇の厚み（gw_wavegen v2 の meta）
    curl = meta["curl"]
    cl = meta["crest_line"]
    H0 = fr["H0_m"]
    ends = {"first_row_max_height_m": float(H[0]), "last_row_max_height_m": float(H[-1])}
    # 端の傾き：波峰線（頂の列）の平面の弧長に対する行の高さの変化の最大（崖かどうかの記録）
    crest = np.stack([world(v, jt) for v in range(len(c))])
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(crest[:, [0, 2]], axis=0), axis=1))])
    dH = np.abs(np.diff(H)) / np.maximum(np.diff(arc), 1e-6)
    near_end = arc < arc[vm]
    ends["max_height_slope_along_crest_near_side"] = float(dH[near_end[:-1]].max())
    ends["max_height_slope_along_crest_far_side"] = float(dH[~near_end[:-1]].max())
    # 巻きのある行のうち、高さが主断面の高さの半分を超える区間（波峰線の平面の弧長、最初の行から最後の行まで）。
    # 作業計画 9.3 の目安は「高さがピークの半分を超える区間 ≈1.2H、高さは中央が最大」だが、この K* のピークは奥の唇のない壁
    # （中央ではない）なので、基準を主断面の高さに替えた値も記録する。ピーク基準の値（meta の curl・crest_line）と並べる。
    v_c0 = int(np.argmin(np.abs(c - curl["longest_curl_run_c_range_m"][0])))
    v_c1 = int(np.argmin(np.abs(c - curl["longest_curl_run_c_range_m"][1])))
    run_rows = np.arange(v_c0, v_c1 + 1)
    H_main = float(H[vm])
    am = run_rows[H[run_rows] > 0.5 * H_main]
    ap = run_rows[H[run_rows] > 0.5 * cl["peak_height_m"]]
    curl_half_main = {
        "rows": int(len(am)), "contiguous": bool(len(am) and np.all(np.diff(am) == 1)),
        "c_range_m": [r4(c[am[0]], 2), r4(c[am[-1]], 2)] if len(am) else None,
        "crest_arc_m": float(arc[am[-1]] - arc[am[0]]) if len(am) else 0.0,
    }
    curl_half_peak_c = [r4(c[ap[0]], 2), r4(c[ap[-1]], 2)] if len(ap) else None
    H26 = rows26["Y"].max(1)
    c26 = rows26["c"]
    crest26 = np.stack([np.array(meta26["frame"]["section_origin_world"]) + c26[v] * np.array(meta26["frame"]["e_crest"]) +
                        rows26["A"][v, jt] * np.array(meta26["frame"]["t_travel"]) + np.array([0, rows26["Y"][v, jt], 0]) for v in range(len(c26))])
    arc26 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(crest26[:, [0, 2]], axis=0), axis=1))])
    dH26 = np.abs(np.diff(H26)) / np.maximum(np.diff(arc26), 1e-6)
    ends["cp1_max_height_slope_along_crest_far_side"] = float(dH26[c26[:-1] > 0].max())
    qa = bl["meshes"]["r01_a45"]
    qa_old = bl["meshes"]["cp1_a45_same_seat"]
    rays = qa["rays"]

    # ---------------------------------------------------------------- 図
    def rimg(k):
        return os.path.join(RDIR, "af26r01_%s.png" % k)
    rel = meta["seat_v1_relation_record_only"]
    img = label(T.imread_rgb(rimg("painting_r01")),
                ["26修正01 の K*（45°、gw_wavegen v2）の原画視点。t* = 12.0 s、PaintingCam v1。Unity の PC オフスクリーン描画（HMD ではない）。",
                 "主役波は確認用のクレイ（仮の色、原画の色ではない。色の焼き直しは 28修正01）。背景は番号27修正01 のプレハブ（右船の置き直し・座席 v1）。",
                 "外輪郭 78/130/131/132 = %.2f/%.2f/%.2f/%.2f px、72 p95 %.2f px（最大 %.2f px）。" % (
                     cv("78", "78").get("r01", float("nan")), cv("130", "130").get("r01", float("nan")), cv("131", "131").get("r01", float("nan")),
                     cv("132", "132").get("r01", float("nan")), cv("72", "72").get("r01_p95", float("nan")), cv("72", "72").get("r01", float("nan")))],
                xy=(180, 16), size=21)
    T.imwrite(os.path.join(EVID, "26R01_painting.png"), img)
    ov = glob.glob(os.path.join(BUILD, "eval", "r01", "*overlay*.png"))
    if ov:
        o = T.imread_rgb(ov[0])
        if o.shape[:2] != (1080, 1920):
            o = cv2.resize(o, (1920, 1080), interpolation=cv2.INTER_AREA)
        T.imwrite(os.path.join(EVID, "26R01_contour.png"), o)
    # 原画視点の差（CP1 の K* → 26修正01 の K*）：空と主役波の境の違い
    base = (T.imread_rgb(rimg("painting_r01")).astype(np.float32) * 0.45).astype(np.uint8)
    x1 = cv2.resize(xor_sky.astype(np.uint8), (1920, 1080), interpolation=cv2.INTER_AREA) > 0
    base[x1] = (255, 60, 40)
    base = label(base, ["原画視点の ID 画像の差（同じ場面で K* だけを替えた）：赤＝空かどうかが CP1 の K* 45° と 26修正01 の K* で違う画素 %.0f px（表示 px 換算）。" % (xor_sky.sum() / 4.0),
                        "奥の断面を巻かせても、原画視点では手前の断面と主断面の像の内側に収まる（評価器の値は metrics.json）。"], xy=(180, 16), size=21)
    T.imwrite(os.path.join(EVID, "26R01_painting_diff.png"), base)
    # 座席 v1 からの比較（CP1 の K* ／ 26修正01 の K*）
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    sheet[0:540, 0:960] = label(tile(rimg("seat_lip_cp1")), ["CP1 の K* 45°（番号26）：座席 v1 から唇へ"], size=20)
    sheet[0:540, 960:1920] = label(tile(rimg("seat_lip_r01")), ["26修正01 の K*：座席 v1 から唇へ（仰角 %.0f°）" % rel["nearest_lip_point_above_3m"]["elevation_deg"]], size=20)
    sheet[540:1080, 0:960] = label(tile(rimg("seat_up_cp1")), ["CP1 の K* 45°：座席 v1 から唇の方位を仰角 55°"], size=20)
    sheet[540:1080, 960:1920] = label(tile(rimg("seat_up_r01")), ["26修正01 の K*：座席 v1 から唇の方位を仰角 55°"], size=20)
    T.imwrite(os.path.join(EVID, "26R01_seat_compare.png"), sheet)
    big = label(T.imread_rgb(rimg("seat_lip_r01")),
                ["座席 v1（右船、甲板から 1.2 m 上の座位の目、番号27修正01）から 26修正01 の K* の唇へ。縦画角 80°、Unity の PC オフスクリーン描画（HMD ではない）。",
                 "唇（目より 3 m 以上高い唇の点）で最も近い点まで水平 %.2f m・仰角 %.1f°。唇先の線で最も近い点まで水平 %.2f m・仰角 %.1f°（c = %.1f m の行）。" % (
                     rel["nearest_lip_point_above_3m"]["horizontal_m"], rel["nearest_lip_point_above_3m"]["elevation_deg"],
                     rel["nearest_lip_tip"]["horizontal_m"], rel["nearest_lip_tip"]["elevation_deg"], rel["nearest_lip_tip"]["row_c"]),
                 "主役波は確認用のクレイ（仮の色）。赤紫が見えたら開いた裏面（なし）。"], xy=(20, 16), size=21)
    T.imwrite(os.path.join(EVID, "26R01_seat_lip.png"), big)
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    sheet[0:540, 0:960] = label(tile(rimg("seat_left_r01")), ["座席 v1 から手前の肩（左、c = −10 m の頂の方位、仰角 30°）"], size=20)
    sheet[0:540, 960:1920] = label(tile(rimg("seat_right_r01")), ["座席 v1 から奥（右、c = +3 m の頂の方位、仰角 30°）"], size=20)
    sheet[540:1080, 0:960] = label(tile(rimg("tube_near_r01_waveonly")), ["管の口（c ≈ −1.5 m、内壁から 9 m 前・高さ 4 m）から手前の肩へ（主役波・空・海だけ）"], size=20)
    sheet[540:1080, 960:1920] = label(tile(rimg("tube_far_r01_waveonly")), ["同じ所から奥へ（錐の行と、唇を縮めて閉じる所。主役波・空・海だけ）"], size=20)
    T.imwrite(os.path.join(EVID, "26R01_seat_sides.png"), sheet)
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    for i, (vk, name) in enumerate((("side_left", "側面（左、CP1 と同じ機位）"), ("back", "背面（番号26・CP1 と同じ機位）"), ("front", "前の斜め上（波の進む側）"))):
        sheet[i * 360:(i + 1) * 360, 0:960] = label(tile(rimg("%s_cp1_waveonly" % vk), 960, 360), ["CP1 の K* 45°：" + name], size=18)
        sheet[i * 360:(i + 1) * 360, 960:1920] = label(tile(rimg("%s_r01_waveonly" % vk), 960, 360), ["26修正01 の K*：" + name], size=18)
    T.imwrite(os.path.join(EVID, "26R01_views_compare.png"), sheet)
    # 真上と平面図
    sheet = np.full((1080, 1920, 3), 250, np.uint8)
    sheet[0:540, 0:960] = label(tile(rimg("top_cp1_waveonly")), ["CP1 の K* 45°：真上"], size=20)
    sheet[0:540, 960:1920] = label(tile(rimg("top_r01_waveonly")), ["26修正01 の K*：真上"], size=20)
    plan = np.full((540, 1920, 3), 250, np.uint8)

    def PS(p):
        return (int(960 + (p[0] + 12) * 10), int(520 - (p[2] + 26) * 10))
    tipW = np.array(meta["curl"]["lip_tip_world_every_5_rows"])
    crest26 = crest26
    for arr, col, th in ((crest26, (150, 150, 150), 2), (crest, (0, 0, 0), 2)):
        pts = np.array([PS(p) for p in arr], np.int32)
        cv2.polylines(plan, [pts], False, col, th, cv2.LINE_AA)
    tip_all = np.stack([world(v, jt + int(np.argmax(A[v, jt:jk + 1]))) for v in range(len(c)) if H[v] > 1.0])
    cv2.polylines(plan, [np.array([PS(p) for p in tip_all], np.int32)], False, (220, 40, 40), 2, cv2.LINE_AA)
    cv2.circle(plan, PS(eye), 7, (0, 150, 0), -1)
    cam_dir = np.array(fr["h"])
    p0 = np.array([0.0, 0.0, -30.0])
    cv2.arrowedLine(plan, PS(p0), PS(p0 + 10 * cam_dir), (40, 90, 200), 2, tipLength=0.2)
    plan = label(plan, ["平面図（真上から、x 右・z 上、1 m = 10 px）：灰＝CP1 の波峰線、黒＝26修正01 の波峰線（各行の頂）、赤＝26修正01 の唇先の線、緑＝座席 v1、青の矢＝PaintingCam の向き。",
                        "手前の肩は 45° の波峰線のまま。奥は主断面に隠れる錐（投影中心へ向かう射線に沿って後ろへ）で巻きを保ち、唇を縮めて閉じてから、後ろへ下げながら海面へ下ろした。"],
                 xy=(20, 12), size=18)
    sheet[540:1080] = plan
    T.imwrite(os.path.join(EVID, "26R01_top_plan.png"), sheet)
    # 断面（行ごと、世界の m）
    sec = Image.new("RGB", (1920, 1080), (250, 248, 242))
    dr = ImageDraw.Draw(sec)
    f_s = font(20)
    picks = [-22.0, -16.0, -12.0, -8.0, -4.0, -1.5, 0.0, 2.0, 4.0, 5.5, 8.0, 11.0]
    cmap = cv2.applyColorMap(np.linspace(0, 255, len(picks)).astype(np.uint8)[:, None], cv2.COLORMAP_JET)[:, 0, ::-1]
    ox, oy, sc_ = 700, 1000, 36

    def SP(a, y):
        return (ox + a * sc_, oy - y * sc_)
    for gy in range(0, 26, 5):
        dr.line([SP(-19, gy), SP(26, gy)], fill=(225, 225, 225))
        dr.text(SP(-19, gy), "%d m" % gy, font=f_s, fill=(120, 120, 120))
    v26 = meta26["rows"]["main_row"]
    dr.line([SP(a_, y_) for a_, y_ in zip(rows26["A"][v26] - rows26["A"][v26, jt], rows26["Y"][v26])], fill=(170, 170, 170), width=5)
    for i, cc in enumerate(picks):
        v = int(np.argmin(np.abs(c - cc)))
        col = tuple(int(x) for x in cmap[i])
        a0 = A[v] - A[vm, jt]
        dr.line([SP(a_, y_) for a_, y_ in zip(a0, Y[v]) if -20 < a_ < 26], fill=col, width=3 if v == vm else 2)
        dr.text((1250, 90 + 26 * i), "c = %+.1f m：高さ %.1f m、s %.2f、m %.2f、q %.2f、ac %+.1f m" % (
            c[v], H[v], rows["s"][v], rows["m"][v], rows["q"][v], rows["ac"][v]), font=f_s, fill=col)
    dr.text((20, 20), "26修正01 の K* の断面（波峰線に直交する行、断面内の座標 a（右が唇の向き）と高さ y、m。横の原点は主断面の頂）。太い灰＝CP1 の K* 45° の主断面。", font=f_s, fill=(20, 20, 20))
    dr.text((20, 48), "手前の肩（c < 0）は主断面と相似の巻きを高さに合わせて小さくし、主断面の近くでは唇を少し持ち上げた。奥（c > 0）は錐の行（像が主断面と同じ）で、唇を縮めて閉じてから海面へ下ろす。", font=f_s, fill=(20, 20, 20))
    dr.text((1250, 400), "s：相似の倍率、m：唇の長さ（1 = 主断面）、q：唇の持ち上げ（1 = なし）、ac：頂の断面内の前後（負が後ろ）", font=font(16), fill=(60, 60, 60))
    sec.save(os.path.join(EVID, "26R01_sections.png"))
    # 参照モデルとの比較（記録のみ）
    for src, dst in (("26R01_ref_sections.png", "26R01_ref_sections.png"), ("26R01_ref_painting.png", "26R01_ref_painting.png")):
        sp = os.path.join(BUILD, "ref", src)
        if os.path.exists(sp):
            T.imwrite(os.path.join(EVID, dst), T.imread_rgb(sp))
    cmp = os.path.join(BUILD, "blender")
    if os.path.exists(os.path.join(cmp, "cmp_ref_seat_lip.png")):
        grid = np.full((1080, 1920, 3), 245, np.uint8)
        vks = ["seat_lip", "seat_up", "side", "back"]
        names = {"seat_lip": "座席 v1 → 唇", "seat_up": "座席 v1 → 仰角 55°", "side": "側面（左）", "back": "背面"}
        for ci, obj in enumerate(("ref", "cp1", "r01")):
            for ri, vk in enumerate(vks):
                tl = tile(os.path.join(cmp, "cmp_%s_%s.png" % (obj, vk)), 640, 250)
                nm = {"ref": "参照モデル（Q5・解B）", "cp1": "CP1 の K* 45°", "r01": "26修正01 の K*"}[obj]
                grid[80 + ri * 250:80 + (ri + 1) * 250, ci * 640:(ci + 1) * 640] = label(tl, [nm + "・" + names[vk]], size=16, xy=(10, 8))
        grid = label(grid, ["参照モデル（Q5）・CP1 の K* 45°・26修正01 の K* の並べ図（Blender 5.2.2 Workbench、同じ機位・同じ光。記録のみ）。",
                            "参照モデルは読むだけで、形状は成果物に入れていない。海面は y = −0.07 の平面。座席は座席 v1（番号27修正01）。"], xy=(20, 10), size=20)
        T.imwrite(os.path.join(EVID, "26R01_ref_views.png"), grid)
    # 回り込みの動画（Unity の 96 枚、主役波・空・参照海面だけ）
    frames = sorted(glob.glob(os.path.join(RDIR, "af26r01_orbit_*_r01_waveonly.png")))
    mp4 = os.path.join(BUILD, "26R01_orbit.mp4")
    if frames:
        lst = os.path.join(BUILD, "orbit_frames.txt")
        with open(lst, "w", encoding="utf-8") as fo:
            for fpath in frames:
                fo.write("file '%s'\nduration %.6f\n" % (fpath.replace("\\", "/"), 1.0 / 24))
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-r", "24", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", mp4]
        subprocess.run(cmd, check=True)
        REC.append("ffmpeg -f concat -safe 0 -i Unity/Build/ArtFirst/26修正01/orbit_frames.txt -r 24 -c:v libx264 -pix_fmt yuv420p -crf 24 Unity/Build/ArtFirst/26修正01/26R01_orbit.mp4")
        if os.path.getsize(mp4) <= 5 * 1024 * 1024:
            import shutil
            shutil.copyfile(mp4, os.path.join(EVID, "26R01_orbit.mp4"))
        # 動画の代表 4 コマ
        sheet = np.full((1080, 1920, 3), 30, np.uint8)
        for i, fi in enumerate([0, 24, 48, 72]):
            sheet[(i // 2) * 540:(i // 2 + 1) * 540, (i % 2) * 960:(i % 2 + 1) * 960] = label(tile(frames[fi]), ["回り込み %d° （原画視点の側から上から見て時計回り）" % (fi * 360 // len(frames))], size=20)
        T.imwrite(os.path.join(EVID, "26R01_orbit_frames.png"), sheet)

    # ---------------------------------------------------------------- metrics.json
    items, status = {}, {}

    def put(key, verdict, **kw):
        items[key] = dict(kw, verdict=verdict)
        status[key] = verdict
    for k in ("78", "130", "131", "132"):
        m = cv(k, k)
        put(k, "pass" if (m.get("r01") is not None and m["r01"] <= 4.0) else "fail", criterion="最大 ≤4 px（表示 px、外殻線なしの ID、包絡版）",
            max_px=m.get("r01"), p95_px=m.get("r01_p95"), cp1_kstar_max_px=m.get("cp1_kstar_same_scene"), worst_display_xy=m.get("worst_display_xy"))
    m72 = cv("72", "72")
    put("72", "pass" if (m72.get("r01_p95") is not None and m72["r01_p95"] <= 4.0) else "fail",
        criterion="p95 ≤4 px で判定し、最大は記録（CP1 の利用者の裁定）", p95_px=m72.get("r01_p95"), max_px_record=m72.get("r01"),
        cp1_kstar_p95_px=m72.get("cp1_kstar_p95"), cp1_kstar_max_px=m72.get("cp1_kstar_same_scene"), worst_display_xy=m72.get("worst_display_xy"))
    m71 = cv("71", "71")
    put("71", "record-only", criterion="番号39・40 が前景と右側の仮置きを置き換えた後に判定（CP1 の裁定）", max_px=m71.get("r01"), p95_px=m71.get("r01_p95"),
        cp1_kstar_max_px=m71.get("cp1_kstar_same_scene"))
    put("68", "pass" if d_tip < d_fb else "fail", criterion="座席 v1 から、波の上側（主断面の唇先）が下側（内壁の下端）より水平に近い（番号26・27修正01 と同じ式）",
        horizontal_seat_to_lip_tip_m=r4(d_tip, 3), horizontal_seat_to_face_bottom_m=r4(d_fb, 3),
        lip_tip_elevation_deg=r4(math.degrees(math.atan2(tip[1] - eye[1], d_tip)), 2),
        lip_tip_ahead_0p2H_rows_same_formula_ok=n_ok, lip_tip_ahead_0p2H_rows_total=n_all,
        lip_tip_ahead_0p2H_rows_criterion_ja="唇先が頂より 0.2H 以上前に出る行（断面内で唇先の a − 頂の a ≥ 0.2H、H は行の高さ、H ≥ 2 m の行）。"
                                             "curl_along_crest の「巻きのある行」（0.3H の内壁から唇先までの張り出し ≥0.2H）とは別の判定",
        curl_rows_same_formula_ok=n_ok_curl, curl_rows_total=n_all_curl,
        curl_rows_criterion_ja="巻きのある行（0.3H の高さの内壁から唇先までの張り出し ≥0.2H。curl_along_crest・Step_26_修正01_ja.md 本文と同じ定義）")
    put("69", "pass" if (tips_in and boat_in and 0 < p_crest[1] < 1080 and 0 < p_sea[1] < 1080) else "fail",
        criterion="原画視点で右船の両端と波の上下が採点列の中", boat_visible_bbox_display=r4(bbox_new, 1), boat_tips_projected_px=r4(tips_px, 1),
        wave_top_y_px=r4(p_crest[1], 1), sea_below_main_crest_y_px=r4(p_sea[1], 1))
    put("70", "pass" if wave_vert_px > boat_len_px else "fail", criterion="波の上下の像の長さ > 右船の先端間の投影",
        wave_vertical_px=r4(wave_vert_px, 1), boat_tip_to_tip_px=r4(boat_len_px, 1), wave_height_main_section_m=r4(H[vm], 2),
        crest_peak_height_m_far_lipless_wall=r4(cl["peak_height_m"], 2), boat_length_m=S["boat"]["tip_to_tip_length_m"],
        note_ja="wave_vertical_px は主断面の頂と、その下の海面の像の縦の長さ。高さは主断面（wave_height_main_section_m）で比べる。"
                "波峰線の最高点（crest_peak_height_m_far_lipless_wall）は奥の唇のない壁で、原画視点では主断面に隠れる")
    mesh_ok = (qa["nonmanifold_edges_gt2_faces"] == 0 and qa["flipped_inconsistent_winding_edges"] == 0 and qa["self_intersecting_face_pairs"] == 0
               and qa["degenerate_faces_area_lt_1e-8"] == 0 and qa["boundary_edges"] == qa["boundary_edges_expected_grid_perimeter"] and qa["wire_edges"] == 0
               and qa["flat_sea_faces_facing_down"] == 0)
    put("mesh_checks", "pass" if mesh_ok else "fail", criterion="非多様体・面の反転・自己交差・面積 0 の面がすべて 0、縁の辺が格子の外周と一致（Blender 5.2.2）",
        **{k: qa[k] for k in ("vertices", "faces", "nonmanifold_edges_gt2_faces", "boundary_edges", "boundary_edges_expected_grid_perimeter", "wire_edges",
                              "flipped_inconsistent_winding_edges", "degenerate_faces_area_lt_1e-8", "self_intersecting_face_pairs", "flat_sea_faces_facing_down")})
    ray_ok = rays["wave_back_open"] == 0 and rays["cut_end"] == 0 and rays["hole"] == 0
    put("83_115_116_precheck", "pass" if ray_ok else "fail",
        criterion="座席 v1 から 5 万本：開いた背面・切断端・穴がすべて 0（事前検査。バックログの判定は番号41）", rays=rays,
        rays_elevation_ge_60deg=qa["rays_elevation_ge_60deg"], cp1_kstar_same_seat_rays=qa_old["rays"], cp1_kstar_rays_elevation_ge_60deg=qa_old["rays_elevation_ge_60deg"])
    put("lip_thickness", "pass" if (curl["lip_thickness_min_over_curl_rows_m"] or 0) >= 0.3 else "fail",
        criterion="唇の厚み ≥0.3 m（巻きのある行で、唇先から 0.75 m 奥の鉛直の厚さの最小）", min_m=curl["lip_thickness_min_over_curl_rows_m"],
        at_row_c_m=curl["lip_thickness_min_row_c"])
    put("ends_to_sea", "pass" if (ends["first_row_max_height_m"] < 0.05 and ends["last_row_max_height_m"] < 0.05) else "fail",
        criterion="両端の行は海面の高さ（最初と最後の行の最大の高さ < 0.05 m）。端の傾き（行の高さの変化／波峰線の弧長）は記録", **{k: r4(v, 3) for k, v in ends.items()})
    put("fixed_topology", "pass" if (meta["vertex_count"] == meta["nu"] * meta["nv"] and rep_r["newVertexCount"] == meta["vertex_count"]) else "fail",
        criterion="固定位相の格子（nu×nv、UV つき）。Unity で読んだ頂点数が一致", nu=meta["nu"], nv=meta["nv"], vertices=meta["vertex_count"],
        triangles=meta["triangle_count"], unity_vertex_count=rep_r["newVertexCount"])
    put("curl_along_crest", "record-only", criterion="波峰の全体が巻く（記録）：巻きのある行（0.3H の内壁から唇先までの張り出し ≥0.2H）が続く区間の波峰線の弧長。"
        "作業計画 9.3 の目安は「高さがピークの半分を超える波峰線の区間 ≈1.2H（参照モデル）、高さは中央が最大」",
        curl_rows=curl["curl_rows"],
        longest_curl_run_c_range_m=curl["longest_curl_run_c_range_m"], longest_curl_run_crest_arc_m=r4(curl["longest_curl_run_crest_arc_m"], 2),
        longest_curl_run_crest_arc_over_H0=r4(curl["longest_curl_run_crest_arc_over_H0"], 3),
        curl_above_half_peak_crest_arc_m=r4(curl["curl_above_half_peak_crest_arc_m"], 2),
        curl_above_half_peak_crest_arc_over_H0=r4(curl["curl_above_half_peak_crest_arc_m"] / H0, 3), curl_above_half_peak_c_range_m=curl_half_peak_c,
        curl_above_half_main_section_height_crest_arc_m=r4(curl_half_main["crest_arc_m"], 2),
        curl_above_half_main_section_height_crest_arc_over_H0=r4(curl_half_main["crest_arc_m"] / H0, 3),
        curl_above_half_main_section_height_c_range_m=curl_half_main["c_range_m"], curl_above_half_main_section_height_rows=curl_half_main["rows"],
        curl_above_half_main_section_height_rows_contiguous=curl_half_main["contiguous"],
        main_section_height_m=r4(H_main, 2), half_main_section_height_m=r4(0.5 * H_main, 2), H0_m=r4(H0, 3),
        crest_above_half_peak_arc_m=r4(cl["above_half_peak_arc_length_m"], 2), crest_above_half_peak_arc_over_H0=r4(cl["above_half_peak_arc_length_over_H0"], 3),
        crest_above_half_peak_c_range_m=r4(cl["above_half_peak_c_range_m"], 2),
        cp1_above_half_peak_length_over_H=meta26["crest_line"]["above_half_peak_length_over_H"], peak_height_m=r4(cl["peak_height_m"], 2),
        peak_row_c_m=r4(cl["peak_row_c"], 2), peak_at_far_lipless_wall=bool(cl["peak_row_c"] > curl["longest_curl_run_c_range_m"][1]),
        plan_9_3_height_max_at_centre_met=bool(abs(cl["peak_row_c"]) < 1e-6 or cl["peak_height_m"] <= H_main + 1e-6),
        definitions_ja={
            "crest_above_half_peak": "作業計画 9.3 の定義どおり：高さ（行の最大の高さ）がピークの半分を超える波峰線の区間。巻きの有無は見ない",
            "curl_above_half_peak": "巻きのある行のうち、高さがピークの半分を超える区間（最初の行から最後の行までの弧長）",
            "curl_above_half_main_section_height": "巻きのある行のうち、高さが主断面の高さの半分を超える区間（同じ弧長）。ピークが奥の唇のない壁で中央にないため、"
                                                   "基準をピークから主断面の高さに替えた値（計画 9.3 の定義そのものではない）",
            "note": "ピークの行 c = %.2f m、ピーク／主断面の高さ = %.2f。ピークが中央（主断面）にないときは、計画 9.3 の「高さは中央が最大」を満たさない" % (
                cl["peak_row_c"], cl["peak_height_m"] / H_main)},
        reaches_1p2H={"crest_above_half_peak": bool(cl["above_half_peak_arc_length_over_H0"] >= 1.2),
                      "curl_above_half_peak": bool(curl["curl_above_half_peak_crest_arc_m"] / H0 >= 1.2),
                      "curl_above_half_main_section_height": bool(curl_half_main["crest_arc_m"] / H0 >= 1.2)},
        plan_angle_to_screen_deg=cl["plan_angle_to_screen_deg"])
    put("seat_view_lip", "record-only", criterion="座席 v1 から唇と管の内側が見える（記録。108/109 は番号30）", **rel)
    ref_dev = bl.get("deviation")
    put("reference_model", "record-only", criterion="参照モデル（Q5）との比較（記録のみ、合否に数えない）",
        central_rows_ratios=meta["reference_ratios_self_check_record_only"]["central_rows_c_-12_to_4"],
        main_row=meta["reference_ratios_self_check_record_only"]["main_row"], targets=meta["reference_ratios_self_check_record_only"]["targets_q5"],
        deviation=ref_dev, compare=refc)
    for k, tgt in (("76", "sky_dark"), ("212", "sky_top"), ("213", "sky_transition"), ("74", "fuji_ridge"), ("75", "boat_fg"), ("157", "boat_left"), ("159", "boat_mid")):
        m = cv(k, tgt)
        if m:
            put(k, "record-only" if k != "212" else ("pass" if m.get("verdict_r01") == "pass" else "fail"),
                criterion="主役波以外の項目の記録（K* を替えても変わらないことの確認）", value=m.get("r01"), cp1_kstar_same_scene=m.get("cp1_kstar_same_scene"),
                value_27R01=m.get("27R01_noline"))
    M_out = {
        "schema": "GreatWave.AF26R01.metrics/1", "number": "26修正01", "generated_utc": now(),
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode による PC のオフスクリーン描画と、その画像を番号23 の評価器（ID モード、包絡版、真値 v0.2）で測った値。メッシュ検査と座席からの射線は Blender 5.2.2 ヘッドレス。HMD 実機の結果ではない。",
        "evaluator": {"provisional": em.get("provisional"), "gate": em.get("gate"), "truth": em.get("truth")},
        "kstar": {"gwb_sha256": meta["files"]["gwb_sha256"], "obj_sha256": meta["files"]["obj_sha256"], "nu": meta["nu"], "nv": meta["nv"],
                  "generator": meta["generator"], "fit_info": meta["rows"]["fit_info"]["final"], "checks": meta["checks"],
                  "snap_tps": {k: meta["snap_tps"][k] for k in ("total_field_abs_max_m", "total_field_over_local_size_max", "within_cap")},
                  "deconvolution_delta_abs_max_m": meta["profile"]["deconvolution_delta_abs_max_m"]},
        "painting_view_id_diff_vs_cp1_kstar": {"sky_xor_px_display": r4(xor_sky.sum() / 4.0, 1)},
        "evaluator_compare": compare, "items": items, "status": status,
    }
    T.save_json(os.path.join(EVID, "metrics.json"), M_out)

    # ---------------------------------------------------------------- run.json
    def sha_rel(p):
        return {T.repo_rel(p): T.sha256_file(p)}
    committed_inputs = [SEAT_JSON, os.path.join(HERE, "gw_wavegen_v2.py"), os.path.join(HERE, "params_v2_af26r01.json"), os.path.join(HERE, "gw_wavegen_v1.py"),
                        os.path.join(HERE, "gw_wavegen.py"), os.path.join(HERE, "af26r01_views.py"), os.path.join(HERE, "af26r01_blender.py"),
                        os.path.join(HERE, "af26r01_reference.py"), os.path.join(HERE, "af26_reference.py"), os.path.join(HERE, "af26r01_evidence.py"),
                        os.path.join(HERE, "run_af26r01_unity.ps1"), os.path.join(HERE, "run_af26r01.ps1"),
                        os.path.join(REPO, "Unity", "Assets", "GreatWave", "ArtFirst", "Editor", "AF26R01KStar.cs"),
                        os.path.join(REPO, "Unity", "Assets", "GreatWave", "Scenes", "Tests", "AF26R01_KStar.unity"),
                        os.path.join(REPO, "Tools", "PaintingTruth", "evaluate.py"), os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json"),
                        os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "26", "reference", "align_B_upright.json")]
    not_committed = ([os.path.join(KDIR, f) for f in sorted(os.listdir(KDIR)) if os.path.isfile(os.path.join(KDIR, f))] +
                     [os.path.join(RDIR, f) for f in sorted(os.listdir(RDIR)) if not f.startswith("af26r01_orbit_")] +
                     [os.path.join(BUILD, f) for f in ("af26r01_views.json", "af26r01_build_report.json", "af26r01_render_report.json", "26R01_orbit.mp4")] +
                     [os.path.join(BUILD, "blender", "af26r01_blender.json"), os.path.join(BUILD, "eval", "r01", "metrics.json"), os.path.join(BUILD, "eval", "cp1k", "metrics.json")] +
                     [os.path.join(BUILD, "ref", f) for f in ("26R01_ref_compare.json", "26R01_ref_sections.png", "26R01_ref_painting.png")] +
                     [os.path.join(K26, f) for f in ("kstar_a45.gwb", "kstar_a45.obj", "kstar_a45_meta.json", "kstar_a45_rows.npz")] +
                     [os.path.join(R27, "place", "af27r01_place.json"), os.path.join(R27, "eval", "noline", "metrics.json")])
    orbit_sha = {T.repo_rel(p): T.sha256_file(p) for p in frames}
    outs = [os.path.join(EVID, f) for f in sorted(os.listdir(EVID)) if f != "run.json"]
    run = {
        "schema": "GreatWave.AF26R01.run/1", "number": "26修正01", "generated_utc": now(),
        "commands": ["py -3.10 Tools/GWWaveGen/gw_wavegen_v2.py",
                     "py -3.10 Tools/GWWaveGen/af26r01_views.py",
                     "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af26r01_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF26R01KStar.BuildAndRender -Log build_render",
                     "py -3.10 Tools/GWWaveGen/af26r01_reference.py --align Docs/Evidence/ArtFirst/26/reference/align_B_upright.json --tmp-dir <一時フォルダー>",
                     "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26r01_blender.py -- Unity/Build/ArtFirst/26修正01/kstar "
                     "Unity/Build/ArtFirst/26/kstar Unity/Build/ArtFirst/26修正01/blender Unity/Build/ArtFirst/26修正01/af26r01_views.json %s %s "
                     "G:/research/model/wave_repair_zbrush2.obj Docs/Evidence/ArtFirst/26/reference/align_B_upright.json <一時フォルダー>/ref_selected_world.npy" % (
                         " ".join("%.4f" % v for v in bl["eye"]), " ".join("%.4f" % v for v in bl["look_at"])),
                     "py -3.10 Tools/GWWaveGen/af26r01_evidence.py"] + REC,
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": Image.__version__,
                  "unity": rep_b["unity"], "graphics": "%s / %s / %s" % (rep_r["device"], rep_r["graphicsApi"], rep_r["colorSpace"]), "blender": bl["blender"]},
        "unity_build_report": rep_b, "unity_render_seconds": rep_r["totalSeconds"],
        "unity_protected_files_unchanged": bool(rep_b["protectedUnchanged"] and rep_r["protectedUnchanged"]),
        "reference_model": {"path": "G:/research/model/wave_repair_zbrush2.obj", "sha256_expected": "ab4124f9720d6e27d80e2ae063916292898c87606a64441043f6a64de3d53d40",
                            "temp_cache": refc["temp_cache"] if refc else None,
                            "note_ja": "読み取りのみ。SHA-256 を照合してから一時キャッシュ（Git 対象外）を作り、番号の終了時に消した。形状は成果物に入れていない。"},
        "committed_sha256": {k: v for p in committed_inputs if os.path.exists(p) for k, v in sha_rel(p).items()},
        "outputs_sha256": {k: v for p in outs for k, v in sha_rel(p).items()},
        "not_committed_sha256": {k: v for p in not_committed if os.path.exists(p) for k, v in sha_rel(p).items()},
        "orbit_frames_sha256": orbit_sha,
        "forbidden_ja": "旧試作の禁止場所と 732e198 より前の履歴には触れていない。G:\\research\\model は wave_repair_zbrush2.obj の 1 ファイルだけを SHA-256 の照合後に読んだ（同じフォルダーのほかのファイルは開いていない・一覧も取っていない）。Houdini は使っていない。番号26・27・27修正01・28・CP1 のファイルは変えていない。",
    }
    T.save_json(os.path.join(EVID, "run.json"), run)
    print(json.dumps(status, ensure_ascii=False))
    for cc in compare:
        if cc["item"] in ("78", "130", "131", "132", "72", "71", "76", "212", "213", "159"):
            print(cc["item"], cc["target"], cc["version"], "r01", cc["r01"], "p95", cc["r01_p95"], "cp1k", cc["cp1_kstar_same_scene"], "27R01", cc["27R01_noline"])


if __name__ == "__main__":
    main()
