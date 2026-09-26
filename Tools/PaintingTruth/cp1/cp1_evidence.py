# -*- coding: utf-8 -*-
"""完成点 CP1 の証拠一式をまとめる（AF_CP1.unity の合成を Unity で描いた後に実行）。

CP1 の合成 = 番号27 の空のドーム・海・3隻・富士・仮置き ＋ 番号26 の K*（30°／45°／60°）＋ 番号28 の NPR shader v1・外殻線 v0。
この合成を原画視点（t* = 12.0 s、PaintingCam v1）で番号23 の評価器（ID モード、包絡版）にかけ、形・空・船・富士の項目を測り直す。
色面（番号28）と爪の一覧（番号29 草稿）は各番号の metrics.json の値を引き継ぐ（出典の SHA-256 を記録する）。

入力（Git 対象外）:
    Unity/Build/ArtFirst/CP1/render/<key>/cp1_<key>_{painting,seat,side,back,overview}.png、cp1_<key>_painting_ids.png、
    cp1_<key>_painting_ids_line.png、render/idmap.json、cp1_build_report.json、cp1_render_report.json、
    cp1_seat_rays_blender.json（番号26 の af26_blender_qa.py を番号27 の座席の目で実行した結果）
    Unity/Build/ArtFirst/26/kstar/kstar_<key>_meta.json・_rows.npz
入力（Git 対象）:
    Docs/Evidence/ArtFirst/{26,27,28,29}/metrics.json、Docs/Evidence/ArtFirst/29/29_claws_overlay_display.png、
    Tools/GWContext/context_layout.json、Tools/PaintingTruth/ の真値 v0.2
出力:
    Docs/Evidence/ArtFirst/CP1/  CP1_*.png、metrics.json、run.json
    Unity/Build/ArtFirst/CP1/eval/<key>/、eval/<key>_line/（評価器の出力）

使い方（リポジトリ根で）: py -3.10 Tools/PaintingTruth/cp1/cp1_evidence.py
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
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen"))
import truthlib as T  # noqa: E402
import evaluate as EV  # noqa: E402
import gw_wavegen as G0  # noqa: E402

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "CP1")
B26 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26")
EVID = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "CP1")
SRC = {n: os.path.join(REPO, "Docs", "Evidence", "ArtFirst", n, "metrics.json") for n in ("26", "27", "28", "29")}
LAYOUT = os.path.join(REPO, "Tools", "GWContext", "context_layout.json")
KEYS = ["a30", "a45", "a60"]
ALPHA = {"a30": 30, "a45": 45, "a60": 60}
PREF = "a45"   # 作業計画 D6 の既定値（利用者未回答）
CONTOUR_IDS = ["78", "130", "131", "132", "72", "71"]
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
FONT_B = r"C:\Windows\Fonts\YuGothB.ttc"
# 番号26 と同じ：真値 v0.2 の 72 にある、藍線の半幅より細い小さな形（表示 px）。記録のための除外にだけ使う
MICRO_FEATURES_72 = [(856.4, 647.0), (915.0, 723.4)]
MICRO_RADIUS = 12.0
# 番号27 と同じ：213 の飛沫のくぼみ（記録のための除外）
SPRAY_DIP = (875, 912, 652)
RIGHT_BOAT_LENGTH_M_27 = 14.61   # 番号27 の右船の先端間の長さ（Step_27）


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def r4(v, n=4):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    v = float(v)
    if math.isinf(v) or math.isnan(v):
        return str(v)
    return round(v, n)


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT_R, size)
    except OSError:
        return ImageFont.load_default()


def label(img_rgb, lines, xy=(170, 1000), size=22, fill=(255, 255, 255), shadow=(0, 0, 0)):
    im = Image.fromarray(img_rgb)
    dr = ImageDraw.Draw(im)
    f = font(size)
    for i, s in enumerate(lines):
        x, y = xy[0], xy[1] + i * (size + 8)
        if shadow is not None:
            dr.text((x + 1, y + 1), s, font=f, fill=shadow)
        dr.text((x, y), s, font=f, fill=fill)
    return np.array(im)


def meas(em, item, target=None, version=None):
    it = em["items"].get(item)
    if it is None:
        return None
    for m in it["measures"]:
        if (target is None or m.get("target") == target) and (version is None or m.get("version") == version):
            return m
    return None


def contour(em, tid):
    for it in em["items"].values():
        for m in it["measures"]:
            if m.get("target") == tid and m.get("version") == "envelope":
                return m
    return None


def run_eval(render, ids, idmap, out_dir, name):
    cmd = [sys.executable, os.path.join(REPO, "Tools", "PaintingTruth", "evaluate.py"), "--render", render, "--ids", ids,
           "--idmap", idmap, "--out-dir", out_dir, "--name", name]
    subprocess.run(cmd, check=True, cwd=REPO, stdout=subprocess.DEVNULL)
    shown = "py -3.10 Tools/PaintingTruth/evaluate.py --render %s --ids %s --idmap %s --out-dir %s --name %s" % (
        T.repo_rel(render), T.repo_rel(ids), T.repo_rel(idmap), T.repo_rel(out_dir), name)
    return T.load_json(os.path.join(out_dir, "metrics.json")), shown


def main():
    os.makedirs(EVID, exist_ok=True)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    truth = EV.Truth()
    disp = truth.disp_rgb
    cam = G0.PaintingCam(spec)
    rep_b = T.load_json(os.path.join(BUILD, "cp1_build_report.json"))
    rep_r = T.load_json(os.path.join(BUILD, "cp1_render_report.json"))
    rays = T.load_json(os.path.join(BUILD, "cp1_seat_rays_blender.json"))
    lay = T.load_json(LAYOUT)["unity"]
    eye = np.array(lay["seat"]["eyeNumpy"], np.float64)
    idmap_p = os.path.join(BUILD, "render", "idmap.json")
    idmap = T.load_json(idmap_p)
    src = {n: T.load_json(p) for n, p in SRC.items()}

    per, eval_cmds = {}, []
    for k in KEYS:
        rdir = os.path.join(BUILD, "render", k)
        render = os.path.join(rdir, "cp1_%s_painting.png" % k)
        em, c1 = run_eval(render, os.path.join(rdir, "cp1_%s_painting_ids.png" % k), idmap_p, os.path.join(BUILD, "eval", k), "cp1_%s_painting" % k)
        eml, c2 = run_eval(render, os.path.join(rdir, "cp1_%s_painting_ids_line.png" % k), idmap_p, os.path.join(BUILD, "eval", k + "_line"),
                           "cp1_%s_painting_line" % k)
        eval_cmds += [c1, c2]
        ids = T.imread_rgb(os.path.join(rdir, "cp1_%s_painting_ids.png" % k))
        reg = EV.render_regions_ids(truth, ids, idmap)
        rgb = T.imread_rgb(render)
        P = {"em": em, "eml": eml}
        # 72：真値の小さな形の周り 12 px を除いた値（番号26 と同じ記録）
        F = truth.fam["sky_envelope"]
        near_mf = np.zeros(len(F["pts"]), bool)
        for q in MICRO_FEATURES_72:
            near_mf |= np.linalg.norm(F["pts"] - np.array(q), axis=1) < MICRO_RADIUS
        rp_sky = T.boundary_points(reg["sky"], spec, fm)
        r_, _, w_ = T.labelled_hausdorff(F["pts"], F["sel"]["72"] & ~near_mf, rp_sky)
        P["72_excl_micro"] = {"max_px": r4(r_["max_px"]), "p95_px": r4(r_["p95_px"]),
                              "worst_display_xy": [r4(w_[0], 2), r4(w_[1], 2)] if w_ is not None else None}
        # 76 の境界を、何が境を作っているかで分ける（番号27 と同じ手順、記録）。213 は飛沫のくぼみを除いた値も記録する
        # 色画像には外殻線が描かれているので、空の領域は同じ外殻線ありの ID 画像から取る（外殻線なしの ID と組むと、線の画素が暗い空に数えられる）
        ids_l = T.imread_rgb(os.path.join(rdir, "cp1_%s_painting_ids_line.png" % k))
        reg_l = EV.render_regions_ids(truth, ids_l, idmap)
        lab_r = T.srgb8_to_lab(rgb)
        dark_r = T.sky_dark_mask(lab_r, reg_l["sky"], truth.L_mid, spec["extraction"]["sky_dark"], fm)
        rp_dark = T.boundary_points(dark_r, spec, fm)
        Fd = truth.fam["sky_dark"]
        tpts, is_tr = Fd["pts"], Fd["sel"]["sky_transition"]
        Fc = truth.fam["sky_claws"]
        _, ii = T.nearest(tpts, Fc["pts"])
        cls = np.where(is_tr, "transition", Fc["label"][ii]).astype(object)
        mid_near = cv2.dilate((truth.cov["boat_mid"] > 0.5).astype(np.uint8), T.disk(12)).astype(bool)
        xi = np.clip(np.round(tpts[:, 0]).astype(int), 0, fm.W - 1)
        yi = np.clip(np.round(tpts[:, 1]).astype(int), 0, fm.H - 1)
        cls[(~is_tr) & mid_near[yi, xi]] = "boat_mid"
        cls[(~is_tr) & (cls == "other")] = "other_waves"
        d_tr, _ = T.nearest(tpts, rp_dark)
        bd = {}
        for c in sorted(set(cls)):
            s = (cls == c) & fm.scored(tpts)
            if s.any():
                j = int(np.argmax(np.where(s, d_tr, -1)))
                bd[c] = {"n_truth_points": int(s.sum()), "max_truth_to_render_px": r4(d_tr[s].max()),
                         "p95_truth_to_render_px": r4(np.percentile(d_tr[s], 95)), "worst_display_xy": [r4(tpts[j, 0], 2), r4(tpts[j, 1], 2)]}
        P["76_breakdown"] = bd
        dip = is_tr & (tpts[:, 0] > SPRAY_DIP[0]) & (tpts[:, 0] < SPRAY_DIP[1]) & (tpts[:, 1] > SPRAY_DIP[2])
        res_nodip, _, _ = T.labelled_hausdorff(tpts, is_tr & ~dip, rp_dark)
        P["213_excl_dip"] = {"max_px": r4(res_nodip.get("max_px")), "p95_px": r4(res_nodip.get("p95_px"))}
        # 68・69・70（番号26 と同じ式。座席は番号27 の置き直した座席、右船は番号27 の配置）
        meta = T.load_json(os.path.join(B26, "kstar", "kstar_%s_meta.json" % k))
        rows = np.load(os.path.join(B26, "kstar", "kstar_%s_rows.npz" % k))
        fr_e, fr_t = np.array(meta["frame"]["e_crest"]), np.array(meta["frame"]["t_travel"])
        O0 = np.array(meta["frame"]["section_origin_world"])
        vm = meta["rows"]["main_row"]
        A, Y = rows["A"][vm], rows["Y"][vm]
        jt, jk, jf = meta["profile"]["index"]["j_top"], meta["profile"]["index"]["j_corner"], meta["profile"]["index"]["j_facebot"]
        world = lambda aa, yy: O0 + aa * fr_t + np.array([0, 1.0, 0]) * yy  # noqa: E731
        jtip = jt + int(np.argmax(A[jt:jk + 1]))
        tip, fb, crest, sea_below = world(A[jtip], Y[jtip]), world(A[jf], Y[jf]), world(A[jt], Y[jt]), world(A[jt], 0.0)
        p_crest, p_sea = cam.project(crest[None])[0], cam.project(sea_below[None])[0]
        mid = np.all(ids == np.array(idmap["classes"]["boat_mid"], np.uint8), -1)
        ys, xs = np.nonzero(mid)
        if len(xs):
            bbox = [float(xs.min()) / 2, float(ys.min()) / 2, float(xs.max()) / 2, float(ys.max()) / 2]
            Q = np.stack([xs, ys], -1).astype(np.float64) / 2.0
            _, _, vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False)
            pr = (Q - Q.mean(0)) @ vt[0]
            blen = float(pr.max() - pr.min())
        else:
            bbox, blen = None, None
        ceye = np.array([rep_b["candidateRightBoatEye"][c] for c in "xyz"], np.float64)
        P["candidate_right_boat"] = {"eye_world": [r4(v, 3) for v in ceye], "horizontal_distance_to_lip_tip_m": r4(np.hypot(*(tip - ceye)[[0, 2]]), 2),
                                     "horizontal_distance_to_face_bottom_m": r4(np.hypot(*(fb - ceye)[[0, 2]]), 2),
                                     "lip_tip_elevation_deg": r4(math.degrees(math.atan2(tip[1] - ceye[1], np.hypot(*(tip - ceye)[[0, 2]]))), 1),
                                     "crest_elevation_deg": r4(math.degrees(math.atan2(crest[1] - ceye[1], np.hypot(*(crest - ceye)[[0, 2]]))), 1)}
        P["seat_current"] = {"lip_tip_elevation_deg": r4(math.degrees(math.atan2(tip[1] - eye[1], np.hypot(*(tip - eye)[[0, 2]]))), 1),
                             "crest_elevation_deg": r4(math.degrees(math.atan2(crest[1] - eye[1], np.hypot(*(crest - eye)[[0, 2]]))), 1)}
        P.update({"d_tip": float(np.hypot(*(tip - eye)[[0, 2]])), "d_fb": float(np.hypot(*(fb - eye)[[0, 2]])),
                  "p_crest": p_crest.tolist(), "p_sea": p_sea.tolist(), "wave_vert_px": float(p_sea[1] - p_crest[1]),
                  "boat_bbox": bbox, "boat_len_px": blen, "crest_height_m": meta["crest_line"]["peak_height_m"]})
        # 左奥の船（157）が見えるか：ID 画像の画素数
        P["boat_left_visible_px_display"] = float(np.all(ids == np.array(idmap["classes"]["boat_left"], np.uint8), -1).sum()) / 4.0
        per[k] = P

    # ------------------------------------------------------------------ 図
    pr = per[PREF]
    shutil.copyfile(os.path.join(BUILD, "render", PREF, "cp1_%s_painting.png" % PREF), os.path.join(EVID, "CP1_painting.png"))
    rgb = T.imread_rgb(os.path.join(BUILD, "render", PREF, "cp1_%s_painting.png" % PREF)).astype(np.float32)
    ov = rgb.copy()
    ov[:, fm.x0:fm.x1 + 1] = 0.5 * rgb[:, fm.x0:fm.x1 + 1] + 0.5 * disp[:, fm.x0:fm.x1 + 1].astype(np.float32)
    ov[:, :fm.x0] *= 0.35
    ov[:, fm.x1 + 1:] *= 0.35
    ov = label(np.clip(np.round(ov), 0, 255).astype(np.uint8),
               ["CP1 合成（K* 45°＋NPR v1・外殻線 v0＋空・船・富士）Unity の PC オフスクリーン描画、t* = 12.0 s、PaintingCam v1 ＋ 原画 50%"], xy=(170, 1040), size=22)
    T.save_png_reserved(os.path.join(EVID, "CP1_painting_overlay50.png"), ov, [(255, 255, 255), (0, 0, 0)])
    # 偏差図は 2 枚にする。輪郭の項目（78〜72・71、富士・3隻）は外殻線なしの ID 画像（番号26 と同じ条件）で、
    # 空の項目（76・212・213）は色画像と同じ外殻線ありの ID 画像で判定する。評価器の図には両方の項目の値が出るので、
    # それぞれの図に「どの項目の判定に使う図か」を書き込み、もう一方の項目の値は記録値であることを示す。
    ov_reserved = [(0, 255, 255), (60, 230, 60), (255, 220, 0), (255, 40, 40), (255, 60, 60), (255, 255, 255), (0, 0, 0)]
    sky_nl = (meas(pr["em"], "76", "sky_dark")["value_max_px"], meas(pr["em"], "213", "sky_transition")["value_max_px"])
    sky_l = (meas(pr["eml"], "76", "sky_dark")["value_max_px"], meas(pr["eml"], "213", "sky_transition")["value_max_px"])
    ov_c = T.imread_rgb(os.path.join(BUILD, "eval", PREF, "cp1_%s_painting_overlay.png" % PREF))
    ov_c = label(ov_c, ["輪郭の判定用の偏差図（外殻線なしの ID 画像、番号26 と同じ条件）：78〜72・71 の輪郭を判定する。富士・3隻は報告項目。",
                        "この図の sky_dark %.2f・sky_transition %.2f は測り方の不整合による記録値。76・213 の判定は CP1_contour_a45_sky.png（%.2f・%.2f px）。"
                        % (sky_nl[0], sky_nl[1], sky_l[0], sky_l[1])], xy=(170, 8), size=20)
    T.save_png_reserved(os.path.join(EVID, "CP1_contour_a45.png"), ov_c, ov_reserved)
    ov_s = T.imread_rgb(os.path.join(BUILD, "eval", PREF + "_line", "cp1_%s_painting_line_overlay.png" % PREF))
    ov_s = label(ov_s, ["空の判定用の偏差図（色画像と同じ外殻線ありの ID 画像）：76 暗い空の範囲（sky_dark）・213 明暗の移行線（sky_transition）を判定する。",
                        "この図の 78〜72 の値は外殻線の外縁を含む記録値で、輪郭の判定には使わない（判定は CP1_contour_a45.png）。"], xy=(170, 8), size=20)
    T.save_png_reserved(os.path.join(EVID, "CP1_contour_a45_sky.png"), ov_s, ov_reserved)
    for k in KEYS:
        shutil.copyfile(os.path.join(BUILD, "render", k, "cp1_%s_seat.png" % k), os.path.join(EVID, "CP1_seat_%s.png" % k))
    shutil.copyfile(os.path.join(BUILD, "render", PREF, "cp1_%s_overview.png" % PREF), os.path.join(EVID, "CP1_overview_a45.png"))
    # 3 解釈 × 船上座席・側面・背面
    tiles = []
    for v, vn in (("seat", "船上座席"), ("side", "側面（左から）"), ("back", "背面")):
        row = []
        for k in KEYS:
            im = cv2.resize(T.imread_rgb(os.path.join(BUILD, "render", k, "cp1_%s_%s.png" % (k, v))), (640, 360), interpolation=cv2.INTER_AREA)
            row.append(label(im, ["%s・K* %d°" % (vn, ALPHA[k])], xy=(10, 8), size=22))
        tiles.append(np.hstack(row))
    grid = np.vstack(tiles)
    T.imwrite(os.path.join(EVID, "CP1_views_grid.png"), grid)
    # 同じ機位で、主役波・海・空だけ（番号27 の船・富士・仮置きを隠した確認図）
    tiles = []
    for v, vn in (("seat", "船上座席"), ("side", "側面（左から）"), ("back", "背面")):
        row = []
        for k in KEYS:
            im = cv2.resize(T.imread_rgb(os.path.join(BUILD, "render", k, "cp1_%s_%s_waveonly.png" % (k, v))), (640, 360), interpolation=cv2.INTER_AREA)
            row.append(label(im, ["%s・K* %d°（主役波・海・空だけ）" % (vn, ALPHA[k])], xy=(10, 8), size=22))
        tiles.append(np.hstack(row))
    T.imwrite(os.path.join(EVID, "CP1_views_waveonly.png"), np.vstack(tiles))
    # D7 の判断材料：今の座席（番号27 の手前の船）と座席の候補 (a)（右船＝唇の下の船）
    tiles = []
    for v, vn in (("seat", "今の座席（手前の船、番号27）"), ("seatmid", "座席の候補 (a)：右船（唇の下の船）")):
        row = []
        for k in KEYS:
            im = cv2.resize(T.imread_rgb(os.path.join(BUILD, "render", k, "cp1_%s_%s.png" % (k, v))), (640, 360), interpolation=cv2.INTER_AREA)
            row.append(label(im, ["%s・K* %d°" % (vn, ALPHA[k])], xy=(10, 8), size=20))
        tiles.append(np.hstack(row))
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    sheet[:720] = np.vstack(tiles)
    lines = ["D7（座席の船）の判断材料。Unity の PC オフスクリーン描画、t* = 12.0 s の K*＋NPR v1＋番号27 の背景。縦画角 80°、目は甲板から 1.2 m 上。"]
    for k in KEYS:
        a, b = per[k]["seat_current"], per[k]["candidate_right_boat"]
        lines.append("K* %d°：今の座席から唇の先まで水平 %.1f m・仰角 %.1f°／右船から唇の先まで水平 %.1f m・仰角 %.1f°、頂の仰角 %.1f°" % (
            ALPHA[k], per[k]["d_tip"], a["lip_tip_elevation_deg"], b["horizontal_distance_to_lip_tip_m"], b["lip_tip_elevation_deg"], b["crest_elevation_deg"]))
    lines.append("右船は番号27 の置き方（船首の側が右の斜面の仮置きに沈み、軸まわりに 25° 傾く）。候補の座席は決定ではない（利用者の D7 待ち）。")
    sheet = label(sheet, lines, xy=(30, 750), size=24, fill=(235, 235, 235))
    T.imwrite(os.path.join(EVID, "CP1_seat_candidates.png"), sheet)
    # 番号29 の爪の一覧の草稿の重ね図（原画視点）をそのまま複製する
    shutil.copyfile(os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "29", "29_claws_overlay_display.png"), os.path.join(EVID, "CP1_claws29_draft_overlay.png"))

    # ------------------------------------------------------------------ metrics.json
    items = {}

    def by_k(fn):
        return {k: fn(k) for k in KEYS}

    for tid in CONTOUR_IDS:
        def one(k, tid=tid):
            m = contour(per[k]["em"], tid)
            d = {"max_px": m["value_max_px"], "p95_px": m["p95_px"], "worst_display_xy": m.get("worst_display_xy"), "verdict": m["verdict"]}
            if tid == "71":
                d["iou_region71_clip"] = m.get("iou")
            s26 = src["26"]["items"][tid]["by_interpretation"][k]
            d["number26_max_px"] = s26["max_px"]
            ml = contour(per[k]["eml"], tid)
            d["record_with_outline_max_px"] = ml["value_max_px"] if ml else None
            return d
        items[tid] = {"backlog": int(tid), "source": "CP1 合成で再測定",
                      "criterion": "t* の PaintingCam v1・1920×1080、評価器 ID モード（3840×2160）、包絡版、外殻線なしの最大 ≤4 px",
                      "by_interpretation": by_k(one), "verdict_default_45": contour(per[PREF]["em"], tid)["verdict"]}
    items["72"]["record_excluding_truth_micro_features"] = {"note_ja": "記録のみ。番号26 と同じく、真値の内壁の外縁にある 2 つの小さな形の周り 12 px を除いた値",
                                                            "by_interpretation": by_k(lambda k: per[k]["72_excl_micro"])}
    items["71"]["note_ja"] = "空域の下辺は番号27 の前景のうねり・右の斜面の仮置きと右船が作る（番号39・40・G18 の範囲）。上辺と左辺は 72 と同じ点列。"
    fx0, fx1 = fm.x0, fm.x1
    items["68"] = {"backlog": 68, "source": "CP1 合成で再測定（座席は番号27 の座席）",
                   "criterion": "同じ K* を原画視点と船上の両方に描き、波の上側（唇の先）が下側（内壁の下端）より座席の船側にある",
                   "seat_eye_world": eye.tolist(),
                   "by_interpretation": by_k(lambda k: {"horizontal_distance_seat_to_lip_tip_m": r4(per[k]["d_tip"], 3),
                                                        "horizontal_distance_seat_to_face_bottom_m": r4(per[k]["d_fb"], 3),
                                                        "verdict": "pass" if per[k]["d_tip"] < per[k]["d_fb"] else "fail"}),
                   "final_ja": "座席の船（D7）が未確定なので、定義第11行（原画／船上機位の特定まで合格としない）により最終の合格ではない。"}
    items["69"] = {"backlog": 69, "source": "CP1 合成で再測定（右船は番号27 の配置）",
                   "criterion": "原画視点で右船の船首・船尾と波の上下がすべて画面内（採点列 %d〜%d）にある" % (fx0, fx1),
                   "by_interpretation": by_k(lambda k: {"right_boat_bbox_display_px": per[k]["boat_bbox"],
                                                        "right_boat_inside_scored_columns": bool(per[k]["boat_bbox"] and per[k]["boat_bbox"][0] > fx0 and per[k]["boat_bbox"][2] < fx1),
                                                        "wave_crest_display_y": r4(per[k]["p_crest"][1], 2), "wave_base_display_y_main_section_sea": r4(per[k]["p_sea"][1], 2),
                                                        "verdict": "pass" if (per[k]["boat_bbox"] and per[k]["boat_bbox"][0] > fx0 and per[k]["boat_bbox"][2] < fx1
                                                                              and 0 < per[k]["p_crest"][1] and per[k]["p_sea"][1] < fm.H) else "fail"}),
                   "note_ja": "右船の見える範囲（ID 画像）で判定した。番号27 の右船は船首の側が右の斜面の仮置きの中へ沈む（Step_27）。船の形（G18）は未着手。"}
    items["70"] = {"backlog": 70, "source": "CP1 合成で再測定",
                   "criterion": "原画視点の同じ画面で、波の上下の長さが右船の船首から船尾までの長さを超える",
                   "by_interpretation": by_k(lambda k: {"wave_vertical_extent_display_px": r4(per[k]["wave_vert_px"], 2), "right_boat_visible_length_display_px": r4(per[k]["boat_len_px"], 2),
                                                        "crest_height_m": per[k]["crest_height_m"], "right_boat_length_m_number27": RIGHT_BOAT_LENGTH_M_27,
                                                        "verdict": "pass" if (per[k]["boat_len_px"] and per[k]["wave_vert_px"] > per[k]["boat_len_px"]) else "fail"}),
                   "note_ja": "右船の長さは ID 画像の見える画素の主軸方向の長さ（船首の側が斜面に沈むので、船全体の像の長さより短い）。3D では頂の高さ約 20.8 m、右船の先端間 14.61 m。"}
    items["D7_seat_candidates_record"] = {"source": "CP1 合成（記録のみ）", "verdict": "record-only",
                                          "current_seat_eye": eye.tolist(), "candidate_right_boat_eye": per[PREF]["candidate_right_boat"]["eye_world"],
                                          "by_interpretation": by_k(lambda k: {"current_seat": {**per[k]["seat_current"], "horizontal_distance_to_lip_tip_m": r4(per[k]["d_tip"], 2)},
                                                                               "candidate_right_boat": per[k]["candidate_right_boat"]}),
                                          "note_ja": "座席の候補 (a)（唇の下の船＝右船）は番号27 と同じ測り方で甲板の 1.2 m 上に置いた確認用の機位で、座席は決めていない。"}
    items["83_115_116_precheck"] = {"backlog": [83, 115, 116], "source": "番号26 の af26_blender_qa.py を番号27 の座席の目で実行",
                                    "criterion": "座席から 5 万本の射線で、見える穴・切断端・開いた背面がすべて 0（事前検査。判定は番号41）",
                                    "eye": rays["eye"], "look_at": rays["look_at"], "blender": rays["blender"],
                                    "by_interpretation": by_k(lambda k: {**rays["meshes"][k]["rays"],
                                                                         "verdict_precheck": "pass" if (rays["meshes"][k]["rays"]["hole"] == 0 and rays["meshes"][k]["rays"]["cut_end"] == 0
                                                                                                        and rays["meshes"][k]["rays"]["wave_back_open"] == 0) else "fail"}),
                                    "verdict": "record-only",
                                    "note_ja": "K* と海面（y = −0.07）だけを置き、船・前景は入れていない。番号26 は M1 の座席の目で同じ検査をした（3 案とも 0）。"}
    # 空・船・富士（CP1 合成で再測定）
    # 空の項目（76・212・213）は、色画像と同じ外殻線ありの ID 画像で測った評価器の値を使う
    def m76(k):
        c = meas(per[k]["eml"], "76", "sky_dark")
        d = meas(per[k]["eml"], "76", "sky_bottom")
        return {"contour_max_px": c["value_max_px"], "contour_p95_px": c["p95_px"], "worst_display_xy": c.get("worst_display_xy"),
                "color_dE00_sky_bottom": d["value"], "verdict": "pass" if (c["verdict"] == "pass" and d["verdict"] == "pass") else "fail",
                "boundary_breakdown_truth_to_render": per[k]["76_breakdown"]}
    items["76"] = {"backlog": 76, "source": "CP1 合成で再測定", "criterion": "暗い空の範囲 ≤4 px、ΔE00 ≤5", "by_interpretation": by_k(m76),
                   "number27": {"contour_max_px": src["27"]["items"]["76"]["value"]["contour_max_px"], "color_dE00": src["27"]["items"]["76"]["value"]["color_dE00_sky_bottom"]},
                   "measurement_note_ja": "空の項目（76・212・213）は、色画像（外殻線あり）と同じ外殻線ありの ID 画像で測った。最初の集計では外殻線なしの ID 画像と組み合わせたため、"
                                          "空の側に入った線の画素が暗い空と数えられ、76 が最大 86.6〜94.4 px、213 が 21.6 px になった（下の record_noline_ids）。これは測り方の不整合で、判定には使わない。",
                   "record_noline_ids": by_k(lambda k: {"76_contour_max_px": meas(per[k]["em"], "76", "sky_dark")["value_max_px"],
                                                        "213_transition_max_px": meas(per[k]["em"], "213", "sky_transition")["value_max_px"]})}
    def m213(k):
        c = meas(per[k]["eml"], "213", "sky_transition")
        b = meas(per[k]["eml"], "213", "boat_ochre")
        return {"transition_max_px": c["value_max_px"], "transition_p95_px": c["p95_px"], "worst_display_xy": c.get("worst_display_xy"),
                "transition_excluding_spray_dip_record": per[k]["213_excl_dip"], "boat_ochre_dE00_record": b["value"] if b else None,
                "verdict": c["verdict"]}
    items["213"] = {"backlog": 213, "source": "CP1 合成で再測定（段差と船の既定配色は番号27 の値）", "criterion": "移行線 ≤4 px、余分な帯状段差なし、波と船の既定配色 ΔE00 ≤5",
                    "by_interpretation": by_k(m213), "number27_band_step_and_boat_colour": {k: src["27"]["items"]["213"]["value"][k] for k in
                                                                                         ("band_step_render_minus_float_dome_max_8bit", "boat_pixels_median_dE00_vs_palette")}}
    items["212"] = {"backlog": 212, "source": "CP1 合成で再測定", "criterion": "上方が水平線付近より明るく、ΔE00 ≤5",
                    "by_interpretation": by_k(lambda k: {"dE00_sky_top": meas(per[k]["eml"], "212", "sky_top")["value"],
                                                         "verdict": meas(per[k]["eml"], "212", "sky_top")["verdict"]})}
    items["94"] = {"backlog": 94, "source": "番号27 から引き継ぎ（CP1 は静止画だけで再測定していない）", "value": src["27"]["items"]["94"]["value"],
                   "verdict": src["27"]["items"]["94"]["verdict"]}
    for n, tgt, fam in (("74", "fuji_ridge", None), ("161", "fuji_ridge", None), ("75", "boat_fg", None), ("157", "boat_left", None), ("159", "boat_mid", None)):
        items[n] = {"backlog": int(n), "source": "CP1 合成で再測定（報告項目）", "verdict": "record-only",
                    "by_interpretation": by_k(lambda k, n=n, tgt=tgt: {"max_px": meas(per[k]["em"], n, tgt)["value_max_px"], "p95_px": meas(per[k]["em"], n, tgt)["p95_px"]}),
                    "number27_max_px": src["27"]["items"][n]["value"]["value_max_px"]}
    items["157"]["boat_left_visible_display_px2"] = by_k(lambda k: per[k]["boat_left_visible_px_display"])
    items["162"] = {"backlog": 162, "source": "CP1 合成で再測定（報告項目）", "verdict": "record-only",
                    "by_interpretation": by_k(lambda k: {"fuji_snow_dE00": meas(per[k]["em"], "162", "fuji_snow")["value"],
                                                         "fuji_slope_dE00": meas(per[k]["em"], "162", "fuji_slope")["value"]})}
    # 色面（番号28 から引き継ぎ。45° が判定、30°／60° は記録）
    s28 = src["28"]
    for n in ("73", "77", "79", "118", "120", "133", "134", "175", "263", "270", "265", "266", "267", "uv_no_empty_texels", "142", "143", "178"):
        it = s28["items"][n]
        items["28_" + n] = {"backlog": int(n) if n.isdigit() else None, "source": "番号28 から引き継ぎ（45°、主役波だけの描画＋主役波以外は原画で合成した評価）",
                            "name_ja": it.get("name_ja"), "verdict": it.get("verdict"),
                            "record_a30_a60": {kk: s28["record_other_interpretations"][kk].get(n) for kk in ("a30", "a60")} if n in s28["record_other_interpretations"]["a30"] else None}
    items["28_175"]["value_summary"] = {"regions_total": s28["items"]["175"]["value"]["regions_total"], "regions_retained": s28["items"]["175"]["value"]["regions_retained"],
                                       "lost": [x["id"] for x in s28["items"]["175"]["value"]["lost"]], "boundary_max_px": 18.38,
                                       "without_two_contour_touching_regions_max_px": 2.25}
    # 爪（番号29 草稿）
    items["29_claws_draft"] = {"source": "番号29（草稿 draft1）から引き継ぎ", "verdict": "record-only", "items": src["29"]["items"][:4]}

    # ------------------------------------------------------------------ 状態の一覧（表の元）
    def fmt3(tid):
        return " / ".join("%.2f" % items[tid]["by_interpretation"][k]["max_px"] for k in KEYS)

    V = {"pass": "合格", "fail": "不合格", "record-only": "記録のみ", "not-yet": "未着手", "pass-conditional": "合格（D7待ち）", "unverified": "未検証"}
    status = []

    def add(group, nums, name, value, verdict, note="", nums_ja=None):
        status.append({"group": group, "backlog": nums, "backlog_ja": nums_ja or ("、".join(str(n) for n in nums) if nums else "—"),
                       "name_ja": name, "value_ja": value, "verdict": verdict, "verdict_ja": V[verdict], "note_ja": note})

    g1 = "形（CP1 合成で再測定。値は 30°/45°/60° の最大 px）"
    for tid, nm in (("78", "左端から斜め上への外形"), ("130", "左側の傾き"), ("131", "上側へのつながり"), ("132", "船側への曲がり")):
        add(g1, [int(tid)], nm, fmt3(tid), items[tid]["verdict_default_45"], "外殻線を含めた記録 45°：%.2f" % items[tid]["by_interpretation"][PREF]["record_with_outline_max_px"])
    add(g1, [72], "内側の輪郭", fmt3("72"), items["72"]["verdict_default_45"],
        "真値の小さな形 2 か所を除くと %s（記録）" % " / ".join("%.2f" % per[k]["72_excl_micro"]["max_px"] for k in KEYS))
    add(g1, [71], "内側の空域", fmt3("71"), items["71"]["verdict_default_45"], "下辺は前景・斜面の仮置きと右船（39・40・G18）")
    add(g1, [68], "上側が下側より座席の船側", " / ".join("%.1f<%.1f m" % (per[k]["d_tip"], per[k]["d_fb"]) for k in KEYS),
        "pass-conditional" if all(items["68"]["by_interpretation"][k]["verdict"] == "pass" for k in KEYS) else "fail", "座席（D7）未確定：定義第11行")
    v69 = items["69"]["by_interpretation"][PREF]
    add(g1, [69], "右船と波の上下が画面内", "右船 x %.0f〜%.0f" % (v69["right_boat_bbox_display_px"][0], v69["right_boat_bbox_display_px"][2]) if v69["right_boat_bbox_display_px"] else "右船なし",
        v69["verdict"], "採点列 %d〜%d" % (fx0, fx1))
    v70 = items["70"]["by_interpretation"][PREF]
    add(g1, [70], "波の上下 > 右船の全長", "%.0f px > %.0f px" % (v70["wave_vertical_extent_display_px"], v70["right_boat_visible_length_display_px"] or 0), v70["verdict"],
        "右船は見える部分の長さ")
    add(g1, [83, 115, 116], "座席からの射線（事前検査）", "穴・切断端・開いた背面 %s" % " / ".join(
        "%d" % (rays["meshes"][k]["rays"]["hole"] + rays["meshes"][k]["rays"]["cut_end"] + rays["meshes"][k]["rays"]["wave_back_open"]) for k in KEYS),
        "record-only", "判定は番号41。番号27 の座席で 5 万本")
    g2 = "空・船・富士（番号27 の配置、CP1 合成で再測定。45°）"
    a76 = items["76"]["by_interpretation"][PREF]
    add(g2, [76], "暗い空の範囲と色", "%.2f px／ΔE00 %.2f" % (a76["contour_max_px"], a76["color_dE00_sky_bottom"]), a76["verdict"],
        ("最大は右船の船首 (%d, %d)。色は合格" % tuple(a76["worst_display_xy"])) if a76.get("worst_display_xy") else "")
    a212 = items["212"]["by_interpretation"][PREF]
    add(g2, [212], "上方の明るい空", "ΔE00 %.2f" % a212["dE00_sky_top"], a212["verdict"])
    a213 = items["213"]["by_interpretation"][PREF]
    add(g2, [213], "空の明暗の移行線", "%.2f px" % a213["transition_max_px"], a213["verdict"],
        "飛沫のくぼみを除くと %.2f（記録）" % a213["transition_excluding_spray_dip_record"]["max_px"])
    add(g2, [94], "原画視点のカメラ固定", "510 フレームで差 0", items["94"]["verdict"], "番号27 の値（CP1 は静止画）")
    add(g2, [74, 161], "富士の稜線", "%.2f px" % items["74"]["by_interpretation"][PREF]["max_px"], "record-only", "報告項目")
    add(g2, [162], "富士の雪と山肌", "雪 ΔE00 %.1f／山肌 %.2f" % (items["162"]["by_interpretation"][PREF]["fuji_snow_dE00"], items["162"]["by_interpretation"][PREF]["fuji_slope_dE00"]),
        "record-only", "報告項目")
    for n, nm in (("75", "手前の船"), ("159", "右の船"), ("157", "左奥の船")):
        v = items[n]["by_interpretation"][PREF]["max_px"]
        note = "報告項目（G18 で形を直す）"
        if n == "157":
            note = "30° %s／60° %s（隠れて見えない＝inf）" % tuple(("%.1f" % items["157"]["by_interpretation"][kk]["max_px"]) if not isinstance(items["157"]["by_interpretation"][kk]["max_px"], str) else "inf" for kk in ("a30", "a60"))
        add(g2, [int(n)], nm + "の外形", ("%.1f px" % v) if not isinstance(v, str) else v, "record-only", note)
    g3 = "色面（番号28 の値。45°、主役波だけ＋遮蔽物は原画）"
    for n, nm in (("73", "内側の水色（藍中）"), ("77", "下側から始まる縞"), ("79", "左側の白"), ("118", "主要な縞の両側"), ("120", "唇の白と内側の水色"),
                  ("133", "左から上へ続く白"), ("134", "白帯の広狭"), ("263", "内側から下方へ続く水色"), ("270", "白と水色の境")):
        b = s28["items"][n]["value"]
        bb = b.get("boundary") or b.get("lower_ends") or b.get("boundary_lower") or {}
        add(g3, [int(n)], nm, "%.2f px" % bb.get("max_px", float("nan")), s28["items"][n]["verdict"])
    add(g3, [175], "白の中の藍・水色が全部残る", "198 中 196、18.38 px", "fail", "輪郭に接する 2 つ（M171・A073）。除くと 2.25 px")
    add(g3, [265], "内側の水色の表示色", "ΔE00 %.2f" % s28["items"]["265"]["value"]["dE00"], s28["items"]["265"]["verdict"])
    add(g3, [266, 267], "水色・白の平塗り（照明・灰色の帯 0）", "標準偏差 <1、帯 0", "pass-conditional", "船上の値は座席（D7）未確定")
    add(g3, [142, 143], "外周の藍線（事前検査）", "中心のずれ 4.14／3.02 px", "record-only", "正式な判定は番号36")
    add(g3, [178], "縞の枝分かれ", "候補 23 か所", "record-only", "延期（計画の損切り）")
    g4 = "爪の一覧（番号29 草稿。すべて記録のみ）"
    add(g4, [139], "爪の数（約150本）", "主浪 135／右側 25（計 160）", "record-only", "CP2 で確認")
    add(g4, [], "和集合と爪の白の IoU（≥0.85）", "0.877（指＋幹だけ 0.695）", "record-only",
        "分母は波頭の平らな白を除いた白（除かないと 0.601、審査の値）。定義は CP2")
    add(g4, [123, 124, 125, 126], "代表10形の候補", "C010, C079, C082, C011, C057 …", "record-only", "D8（CP2）")
    add(g4, [95, 96, 97, 98], "船側中央の爪の候補", "C098 / C096 / C099", "record-only", "C098 は根元幅の条件に当たらない")
    g5 = "未着手・未検証（CP1 の範囲外）"
    add(g5, [80, 106, 107, 108, 111, 117], "形成の動き K0→K*", "—", "not-yet", "番号30（CP2）", "80・106〜108・111・117")
    add(g5, [102, 135, 176, 177], "白の出現・縞の追従", "—", "not-yet", "番号31（CP2）")
    add(g5, [81, 112], "性能（3080 の代理測定）", "—", "not-yet", "番号32（CP2）")
    add(g5, [95, 96, 97, 98, 122, 123, 124, 125, 126, 127, 128, 200], "爪の終態造形と 3 列の配置", "—", "not-yet", "番号33（CP3）", "95〜98・122〜128・200")
    add(g5, [142, 143, 146, 147, 148, 191, 192], "藍線（外輪郭の正式判定・爪の縁・遮蔽）", "—", "not-yet", "番号36（CP4）", "142・143・146〜148・191・192")
    add(g5, [149, 150, 151, 152], "飛沫", "—", "not-yet", "番号37", "149〜152")
    add(g5, [], "HMD 実機（H1〜H7、Step_05 L23-34）", "—", "unverified", "HMD 未所持。PC 描画は HMD の結果ではない")

    counts = {}
    for s in status:
        counts[s["verdict"]] = counts.get(s["verdict"], 0) + 1

    M = {
        "schema": "GreatWave.CP1.metrics/1",
        "number": "CP1（原画視点の静止した大波：形・色・線・空・船・富士の合成）",
        "note_time_ja": "生成時刻は run.json にだけ記録する（同じ入力で metrics.json の SHA-256 が一致するように）。",
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode による PC オフスクリーン描画（Camera.Render → RenderTexture → PNG、RTX 3080、Direct3D11、Linear）と、"
                            "番号23 の評価器（ID モード、包絡版）。座席からの射線は Blender 5.2.2 ヘッドレス（番号26 のスクリプト）。HMD 実機の結果ではない。",
        "t_star_s": 12.0,
        "scene": {"path": rep_b["scene"], "sha256": rep_b["sceneSha256"], "protected_unchanged_build": rep_b["protectedUnchanged"],
                  "protected_unchanged_render": rep_r["protectedUnchanged"]},
        "composition_ja": "番号27 のプレハブ AF27_Context（空のドーム・海・3隻・富士・前景と斜面の仮置き）＋番号26 の K*（kstar_a30／a45／a60.gwb）＋番号28 の AF28_NPR.mat（色区テクスチャ af28_uvsdf_<key>.bin）と AF28_Outline.mat。",
        "preferred_key": PREF, "preferred_ja": "45°（作業計画 D6 の既定値・利用者未回答）",
        "seat": {"source": "Tools/GWContext/context_layout.json（番号27 の置き直した手前の船）", "eye": lay["seat"]["eyeNumpy"], "target": lay["seat"]["target"], "fov": lay["seat"]["fov"]},
        "evaluator": {"commands": eval_cmds, "provisional": {k: per[k]["em"]["provisional"] for k in KEYS},
                      "truth_version": per[PREF]["em"]["truth"]["version"], "truth_manifest_sha256": per[PREF]["em"]["truth"]["manifest_sha256"],
                      "gate": {kk: per[PREF]["em"].get("gate", {}).get(kk) for kk in ("path", "sha256", "gate_all_pass", "truth_unchanged_since_gate", "all_pass")},
                      "note_ja": "真値 v0.2 と較正門は番号23修正02 の版（CP1 の作業時点では未コミットの作業ツリーの状態）。CP1 はこれに依存する。"},
        "sources": {n: {"path": T.repo_rel(p), "sha256": T.sha256_file(p)} for n, p in SRC.items()},
        "status_counts": counts,
        "status": status,
        "items": items,
    }
    T.save_json(os.path.join(EVID, "metrics.json"), M)

    # ------------------------------------------------------------------ 数値表の画像（2 枚）
    draw_table(os.path.join(EVID, "CP1_metrics_table_1.png"), [s for s in status if s["group"] in (g1, g2)],
               "CP1 数値表 1/2：形・空・船・富士（t* = 12.0 s、PaintingCam v1、1920×1080、評価器 ID モード、真値 v0.2）")
    draw_table(os.path.join(EVID, "CP1_metrics_table_2.png"), [s for s in status if s["group"] in (g3, g4, g5)],
               "CP1 数値表 2/2：色面・線（番号28）、爪の一覧（番号29 草稿）、未着手・未検証")

    # ------------------------------------------------------------------ run.json
    ins = ["Tools/PaintingTruth/cp1/cp1_evidence.py", "Tools/PaintingTruth/cp1/run_cp1_unity.ps1",
           "Unity/Assets/GreatWave/ArtFirst/Editor/AFCP1Composite.cs", "Unity/Assets/GreatWave/Scenes/Tests/AF_CP1.unity",
           "Unity/Assets/GreatWave/ArtFirst/Prefabs/AF27_Context.prefab", "Unity/Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat",
           "Unity/Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF24IdFlat.shader",
           "Unity/Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Unity/Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs",
           "Tools/GWContext/context_layout.json", "Tools/GWWaveGen/af26_blender_qa.py", "Tools/GWWaveGen/gw_wavegen.py",
           "Tools/PaintingTruth/painting_truth.json", "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/evaluate.py",
           "Tools/PaintingTruth/targets/truth_manifest.json", "Docs/Evidence/ArtFirst/23/23_gate.json",
           "Docs/Evidence/ArtFirst/29/29_claws_overlay_display.png"] + [T.repo_rel(p) for p in SRC.values()]
    outs = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(EVID) for f in fs if f != "run.json")
    nc = []
    for k in KEYS:
        nc += ["Unity/Build/ArtFirst/26/kstar/kstar_%s.gwb" % k, "Unity/Build/ArtFirst/26/kstar/kstar_%s_meta.json" % k,
               "Unity/Build/ArtFirst/26/kstar/kstar_%s_rows.npz" % k, "Unity/Build/ArtFirst/26/kstar/kstar_%s.obj" % k,
               "Unity/Build/ArtFirst/28/bake/af28_uvsdf_%s.bin" % k, "Unity/Build/ArtFirst/28/bake/af28_uvwarp_%s.json" % k]
        for v in ("painting", "seat", "side", "back", "overview", "seatmid", "seat_waveonly", "side_waveonly", "back_waveonly", "painting_ids", "painting_ids_line"):
            nc.append("Unity/Build/ArtFirst/CP1/render/%s/cp1_%s_%s.png" % (k, k, v))
        nc += ["Unity/Build/ArtFirst/CP1/eval/%s/metrics.json" % k, "Unity/Build/ArtFirst/CP1/eval/%s_line/metrics.json" % k]
    nc += ["Unity/Build/ArtFirst/CP1/render/idmap.json", "Unity/Build/ArtFirst/CP1/cp1_build_report.json", "Unity/Build/ArtFirst/CP1/cp1_render_report.json",
           "Unity/Build/ArtFirst/CP1/cp1_seat_rays_blender.json"]
    R = {
        "schema": "GreatWave.CP1.run/1", "generated_utc": now(),
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/PaintingTruth/cp1/run_cp1_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AFCP1Composite.BuildAndRender -Log build_render",
            "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26_blender_qa.py -- Unity/Build/ArtFirst/26/kstar Unity/Build/ArtFirst/CP1/cp1_seat_rays_blender.json 2.9554 1.1602 -32.152 -7 5 3",
            "py -3.10 Tools/PaintingTruth/cp1/cp1_evidence.py"],
        "evaluator_commands": eval_cmds,
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": Image.__version__,
                  "unity": rep_r["unity"], "unity_device": rep_r["device"], "unity_graphics_api": rep_r["graphicsApi"], "unity_color_space": rep_r["colorSpace"],
                  "blender": rays["blender"], "platform": platform.platform()},
        "unity_render_seconds": rep_r["totalSeconds"],
        "inputs_sha256": {p: T.sha256_file(os.path.join(REPO, p)) for p in ins},
        "outputs_sha256": {T.repo_rel(p): T.sha256_file(p) for p in outs},
        "not_committed_sha256": {p: T.sha256_file(os.path.join(REPO, p)) for p in nc},
        "note_ja": "Unity/Build/ 以下は Git 対象外。参照モデル（Q5 の OBJ）は CP1 では開いていない（比較図は番号26 の証拠へのリンク）。",
    }
    T.save_json(os.path.join(EVID, "run.json"), R)
    print("CP1_EVIDENCE_DONE", json.dumps(counts, ensure_ascii=False))
    for k in KEYS:
        print(k, {tid: contour(per[k]["em"], tid)["value_max_px"] for tid in CONTOUR_IDS},
              "76", meas(per[k]["eml"], "76", "sky_dark")["value_max_px"], "213", meas(per[k]["eml"], "213", "sky_transition")["value_max_px"],
              "76_noline_ids_record", meas(per[k]["em"], "76", "sky_dark")["value_max_px"],
              "69", items["69"]["by_interpretation"][k]["verdict"], "70", items["70"]["by_interpretation"][k]["verdict"], "68", items["68"]["by_interpretation"][k])


COLORS = {"pass": (46, 125, 50), "fail": (198, 40, 40), "record-only": (110, 110, 110), "not-yet": (70, 70, 90),
          "pass-conditional": (200, 130, 0), "unverified": (90, 60, 130)}


def draw_table(path, rows, title):
    W_, H_ = 1920, 1080
    im = Image.new("RGB", (W_, H_), (250, 248, 242))
    dr = ImageDraw.Draw(im)
    dr.text((30, 18), title, font=font(28, True), fill=(20, 20, 20))
    dr.text((30, 58), "判定の凡例：合格／不合格／合格（D7待ち＝座席の船が未確定のため定義第11行により最終の合格ではない）／記録のみ／未着手／未検証。PC のオフスクリーン描画で、HMD 実機ではない。",
            font=font(18), fill=(60, 60, 60))
    cols = [(30, "番号"), (290, "内容"), (740, "値"), (1150, "判定"), (1330, "備考")]
    y = 96
    fh = 20
    n_rows = len(rows) + len({r["group"] for r in rows})
    lh = max(26, min(38, (H_ - y - 20) // max(1, n_rows + 1)))
    for x, t in cols:
        dr.text((x, y), t, font=font(fh, True), fill=(20, 20, 20))
    y += lh
    dr.line([(24, y - 4), (W_ - 24, y - 4)], fill=(120, 120, 120), width=1)
    cur = None
    for r in rows:
        if r["group"] != cur:
            cur = r["group"]
            dr.rectangle([24, y - 2, W_ - 24, y + lh - 6], fill=(228, 224, 212))
            dr.text((30, y), cur, font=font(fh, True), fill=(30, 30, 30))
            y += lh
        ns = r["backlog_ja"]
        fit_text(dr, (30, y), ns, 250, fh, False, (20, 20, 20))
        fit_text(dr, (290, y), r["name_ja"], 440, fh, False, (20, 20, 20))
        fit_text(dr, (740, y), r["value_ja"], 400, fh, False, (20, 20, 20))
        c = COLORS[r["verdict"]]
        dr.rounded_rectangle([1146, y - 1, 1146 + 170, y + lh - 9], radius=5, fill=c)
        fit_text(dr, (1154, y), r["verdict_ja"], 156, fh, True, (255, 255, 255))
        fit_text(dr, (1330, y), r["note_ja"], W_ - 30 - 1330, fh - 2, False, (50, 50, 50))
        y += lh
    im.save(path, optimize=True)


def fit_text(dr, xy, text, maxw, size, bold, fill):
    """幅に収まるまで文字を小さくして書く（最小 12 px）。"""
    s = size
    while s > 12 and dr.textlength(text, font=font(s, bold)) > maxw:
        s -= 1
    dr.text((xy[0], xy[1] + (size - s) // 2), text, font=font(s, bold), fill=fill)


if __name__ == "__main__":
    main()
