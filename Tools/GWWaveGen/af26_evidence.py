# -*- coding: utf-8 -*-
"""番号26 の証拠をまとめる（gw_wavegen_v1 → Unity 描画 → Blender 検査 → 参照モデル比較のあとに実行）。

入力（Git 対象外の Unity/Build/ArtFirst/26/）:
    kstar/kstar_aXX.gwb・.obj・_meta.json・_rows.npz、render/aXX/26_aXX_{painting,boat,side,back,top}.png・26_aXX_painting_ids.png、
    render/idmap.json、af26_build_report.json、af26_render_report.json、af26_blender_qa.json、ref/（参照モデル比較の出力）
出力:
    Docs/Evidence/ArtFirst/26/  26_aXX_painting.png、26_aXX_overlay50.png、26_aXX_contour.png、26_aXX_views.png、
                                26_72_closeups.png、26_compare_views.png、26_ref_painting_overlay.png、26_ref_sections.png、
                                metrics.json、run.json
    Unity/Build/ArtFirst/26/eval/aXX/  評価器の出力

使い方（リポジトリ根で）: py -3.10 Tools/GWWaveGen/af26_evidence.py
"""
import datetime
import json
import os
import platform
import shutil
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

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26")
EVID = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "26")
KEYS = ["a30", "a45", "a60"]
ALPHA = {"a30": 30, "a45": 45, "a60": 60}
CONTOUR_IDS = ["78", "130", "131", "132", "72"]
FONT = r"C:\Windows\Fonts\YuGothM.ttc"
RIGHT_BOAT_LENGTH_M = 18.0
# 真値 v0.2 の 72 にある、藍線の半幅より細い小さな形（表示 px）。記録のための除外にだけ使う
MICRO_FEATURES_72 = [(856.4, 647.0), (915.0, 723.4)]
MICRO_RADIUS = 12.0   # boat_blockout 全長 10 m × 配置倍率 1.8（Step_24 と同じ出典）


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def label(img_rgb, lines, xy=(170, 1000), size=22, fill=(255, 255, 255)):
    im = Image.fromarray(img_rgb)
    dr = ImageDraw.Draw(im)
    f = font(size)
    for i, s in enumerate(lines):
        x, y = xy[0], xy[1] + i * (size + 8)
        dr.text((x + 1, y + 1), s, font=f, fill=(0, 0, 0))
        dr.text((x, y), s, font=f, fill=fill)
    return np.array(im)


def contour(em, tid, ver="envelope"):
    for k, it in em["items"].items():
        for m in it["measures"]:
            if m.get("target") == tid and m.get("version") == ver:
                return m
    return None


def crest_angle_split(k, mt):
    """波峰線（各行の頂の頂点）と断面の法線 e のなす角を、手前（c < 0）と奥（c > 0）に分けて返す（c 方向に ±1 m 離れた点との差）。"""
    d = np.load(os.path.join(BUILD, "kstar", "kstar_%s_rows.npz" % k))
    c, A, Y = d["c"], d["A"], d["Y"]
    a = A[:, mt["profile"]["index"]["j_top"]]
    h = Y.max(1)
    lo = np.clip(np.searchsorted(c, c - 1.0), 0, len(c) - 1)
    hi = np.clip(np.searchsorted(c, c + 1.0), 0, len(c) - 1)
    ang = np.degrees(np.arctan2(np.abs(a[hi] - a[lo]), c[hi] - c[lo]))
    body = h > 0.5 * h.max()
    far = body & (c > 0)
    return {"near_body_rows_max_deg": float(ang[body & (c < 0)].max()), "far_body_rows_max_deg": float(ang[far].max()),
            "far_body_c_range_m": [float(c[far].min()), float(c[far].max())],
            "note_ja": "手前の肩は断面が波峰線にほぼ垂直。奥の端（波頂から約 3 m）は、唇と内壁を後ろへ下げ背面の坂の足へ向けて縮めるので、頂の頂点の列が後ろへ曲がる"}


def main():
    os.makedirs(EVID, exist_ok=True)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    _, disp = T.painting_display(spec, fm)
    cam = G0.PaintingCam(spec)
    rep_b = T.load_json(os.path.join(BUILD, "af26_build_report.json"))
    rep_r = T.load_json(os.path.join(BUILD, "af26_render_report.json"))
    qa = T.load_json(os.path.join(BUILD, "af26_blender_qa.json"))
    layout = T.load_json(os.path.join(REPO, "Docs", "Evidence", "M1", "Revision01", "15_revision_layout.json"))
    eye = np.array([layout["eyeWorld"][k] for k in "xyz"])
    refdir = os.path.join(BUILD, "ref")
    ref_cmp = T.load_json(os.path.join(refdir, "26_ref_compare.json"))
    ref_bl = T.load_json(os.path.join(refdir, "af26_blender_ref.json"))
    per = {}
    eval_cmds = {}
    for k in KEYS:
        rdir = os.path.join(BUILD, "render", k)
        meta = T.load_json(os.path.join(BUILD, "kstar", "kstar_%s_meta.json" % k))
        src = os.path.join(rdir, "26_%s_painting.png" % k)
        ids_p = os.path.join(rdir, "26_%s_painting_ids.png" % k)
        edir = os.path.join(BUILD, "eval", k)
        cmd = ["py", "-3.10", "Tools/PaintingTruth/evaluate.py", "--render", T.repo_rel(src), "--ids", T.repo_rel(ids_p),
               "--idmap", T.repo_rel(os.path.join(BUILD, "render", "idmap.json")), "--out-dir", T.repo_rel(edir), "--name", "26_%s_painting" % k]
        subprocess.run([sys.executable] + cmd[2:], check=True, cwd=REPO)
        eval_cmds[k] = " ".join(cmd)
        em = T.load_json(os.path.join(edir, "metrics.json"))
        # 静止画（Unity の実描画）と原画 50% 重ね
        rgb = T.imread_rgb(src)
        shutil.copyfile(src, os.path.join(EVID, "26_%s_painting.png" % k))
        ov = rgb.astype(np.float32)
        x0, x1 = fm.x0, fm.x1
        ov[:, x0:x1 + 1] = 0.5 * ov[:, x0:x1 + 1] + 0.5 * disp[:, x0:x1 + 1].astype(np.float32)
        ov[:, :x0] *= 0.35
        ov[:, x1 + 1:] *= 0.35
        ov = label(np.clip(np.round(ov), 0, 255).astype(np.uint8),
                   ["番号26 K* %d°（Unity の PC オフスクリーン描画、t* = 12.0 s、PaintingCam v1）＋ 原画 50%%" % ALPHA[k]])
        T.save_png_reserved(os.path.join(EVID, "26_%s_overlay50.png" % k), ov, [(255, 255, 255), (0, 0, 0)])
        shutil.copyfile(os.path.join(edir, "26_%s_painting_overlay.png" % k), os.path.join(EVID, "26_%s_contour.png" % k))
        # 船上・側面・背面・真上の 2×2
        tiles = []
        for v, name in (("boat", "船上座席"), ("side", "側面"), ("back", "背面"), ("top", "真上")):
            im = cv2.resize(T.imread_rgb(os.path.join(rdir, "26_%s_%s.png" % (k, v))), (960, 540), interpolation=cv2.INTER_AREA)
            tiles.append(label(im, ["%s（K* %d°）" % (name, ALPHA[k])], xy=(14, 10), size=24))
        views = np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])])
        T.imwrite(os.path.join(EVID, "26_%s_views.png" % k), views)
        # 項目の値
        ids = T.imread_rgb(ids_p)
        mid = np.all(ids == np.array([0, 255, 0], np.uint8), -1)
        ys, xs = np.nonzero(mid)
        boat_bbox = [float(xs.min()) / 2, float(ys.min()) / 2, float(xs.max()) / 2, float(ys.max()) / 2] if len(xs) else None
        # 右船の像の長さ（マスクの主軸方向の長さ、表示 px）
        if len(xs):
            P = np.stack([xs, ys], -1).astype(np.float64) / 2.0
            c0 = P.mean(0)
            u, s_, vt = np.linalg.svd(P - c0, full_matrices=False)
            proj = (P - c0) @ vt[0]
            boat_len_px = float(proj.max() - proj.min())
        else:
            boat_len_px = None
        rows = np.load(os.path.join(BUILD, "kstar", "kstar_%s_rows.npz" % k))
        fr_e = np.array(meta["frame"]["e_crest"])
        fr_t = np.array(meta["frame"]["t_travel"])
        O0 = np.array(meta["frame"]["section_origin_world"])
        vm = meta["rows"]["main_row"]
        A, Y = rows["A"][vm], rows["Y"][vm]
        jt, jk, jf = meta["profile"]["index"]["j_top"], meta["profile"]["index"]["j_corner"], meta["profile"]["index"]["j_facebot"]
        world = lambda aa, yy: O0 + aa * fr_t + np.array([0, 1.0, 0]) * yy
        jtip = jt + int(np.argmax(A[jt:jk + 1]))
        tip = world(A[jtip], Y[jtip])
        fb = world(A[jf], Y[jf])
        crest = world(A[jt], Y[jt])
        sea_below = world(A[jt], 0.0)
        p_crest = cam.project(crest[None])[0]
        p_sea = cam.project(sea_below[None])[0]
        wave_vert_px = float(p_sea[1] - p_crest[1])
        d_tip = float(np.hypot(*(tip - eye)[[0, 2]]))
        d_fb = float(np.hypot(*(fb - eye)[[0, 2]]))
        cons = {tid: contour(em, tid) for tid in CONTOUR_IDS + ["71"]}
        m71 = cons["71"]
        per[k] = {"meta": meta, "em": em, "contours": cons, "boat_bbox": boat_bbox, "boat_len_px": boat_len_px,
                  "wave_vert_px": wave_vert_px, "crest_world": crest.tolist(), "tip_world": tip.tolist(), "facebot_world": fb.tolist(),
                  "d_tip": d_tip, "d_fb": d_fb, "p_crest": p_crest.tolist(), "p_sea": p_sea.tolist(), "m71": m71}

    # 72 の記録：真値の内壁の外縁にある 2 つの小さな形（しぶきの点が輪郭線に付いた所）の周り 12 px を除いた最大（記録のみ。判定は評価器の値）
    import evaluate as EV
    truth = EV.Truth()
    idmap = T.load_json(os.path.join(BUILD, "render", "idmap.json"))
    F = truth.fam["sky_envelope"]
    near_mf = np.zeros(len(F["pts"]), bool)
    for q in MICRO_FEATURES_72:
        near_mf |= np.linalg.norm(F["pts"] - np.array(q), axis=1) < MICRO_RADIUS
    for k in KEYS:
        ids = T.imread_rgb(os.path.join(BUILD, "render", k, "26_%s_painting_ids.png" % k))
        reg = EV.render_regions_ids(truth, ids, idmap)
        rp = T.boundary_points(reg["sky"], spec, fm)
        r_, _, w_ = T.labelled_hausdorff(F["pts"], F["sel"]["72"] & ~near_mf, rp)
        per[k]["72_excl_micro"] = {"max_px": round(float(r_["max_px"]), 4), "p95_px": round(float(r_["p95_px"]), 4),
                                   "worst_display_xy": [round(float(w_[0]), 2), round(float(w_[1]), 2)] if w_ is not None else None}

    # 72 の最大の所の拡大（3 案）
    crops = []
    for k in KEYS:
        w = per[k]["contours"]["72"].get("worst_display_xy")
        ov = T.imread_rgb(os.path.join(EVID, "26_%s_contour.png" % k))
        cx, cy = int(w[0]), int(w[1])
        x0, y0 = max(cx - 48, 0), max(cy - 54, 0)
        cr = cv2.resize(ov[y0:y0 + 108, x0:x0 + 96], (576, 648), interpolation=cv2.INTER_NEAREST)
        crops.append(label(cr, ["K* %d°：72 最大 %.2f px" % (ALPHA[k], per[k]["contours"]["72"]["value_max_px"]), "(%d, %d) 付近 ×6" % (cx, cy)], xy=(10, 8), size=22))
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    for i, cr in enumerate(crops):
        sheet[40:40 + 648, 30 + i * 630:30 + i * 630 + 576] = cr
    worst_txt = "、".join("%d°：(%d, %d) %.2f px（p95 %.2f px）" % (ALPHA[k], per[k]["contours"]["72"]["worst_display_xy"][0], per[k]["contours"]["72"]["worst_display_xy"][1],
                                                              per[k]["contours"]["72"]["value_max_px"], per[k]["contours"]["72"]["p95_px"]) for k in KEYS)
    sheet = label(sheet, ["番号26 内輪郭 72 の最大距離の所（評価器の偏差図を最近傍で 6 倍。水色＝真値、緑 ≤2 px、黄 ≤4 px、赤 >4 px）",
                          "最大の所：" + worst_txt,
                          "(856, 647) は真値の内壁の外縁から右へ延びる幅 2 px・長さ約 7 px の細い突起、(915, 723) は内壁に付いた小さな輪（しぶきの点が輪郭線に",
                          "付いた所）。どちらも藍線の半幅の内側補正（72 は 1.31 px）より細く、補正後の目標から消えるので、滑らかな内壁では届かない。"], xy=(30, 720), size=24)
    T.imwrite(os.path.join(EVID, "26_72_closeups.png"), sheet)

    # 参照モデルとの並べ図（Blender Workbench、同じ機位。記録のみ）
    tiles = []
    for v, vname in (("boat", "船上座席"), ("side", "側面"), ("back", "背面")):
        row = []
        for name, nm in (("ref", "参照モデル（Q5・解B）"), ("a30", "K* 30°"), ("a45", "K* 45°"), ("a60", "K* 60°")):
            im = cv2.resize(T.imread_rgb(os.path.join(refdir, "cmp_%s_%s.png" % (name, v))), (480, 270), interpolation=cv2.INTER_AREA)
            row.append(label(im, ["%s・%s" % (nm, vname)], xy=(8, 6), size=18, fill=(20, 20, 20)))
        tiles.append(np.hstack(row))
    cmpv = np.vstack(tiles)
    canvas = np.full((1080, 1920, 3), 245, np.uint8)
    canvas[100:100 + cmpv.shape[0], :cmpv.shape[1]] = cmpv
    canvas = label(canvas, ["番号26 参照モデル（Q5）と K* 3 案の並べ図（Blender 5.2.2 Workbench、同じ機位・同じ光。記録のみ）",
                            "参照モデルは読むだけで、形状は成果物に入れていない。海面は y = −0.07 の平面"], xy=(20, 20), size=26, fill=(20, 20, 20))
    T.imwrite(os.path.join(EVID, "26_compare_views.png"), canvas)
    shutil.copyfile(os.path.join(refdir, "26_ref_sections.png"), os.path.join(EVID, "26_ref_sections.png"))
    # 原画視点の重ね図は人が見るための図なので 256 色 PNG にする（線の色はそのまま残す）
    T.save_png_reserved(os.path.join(EVID, "26_ref_painting_overlay.png"), T.imread_rgb(os.path.join(refdir, "26_ref_painting_overlay.png")),
                        [(0, 200, 220), (200, 30, 30), (230, 120, 20), (40, 120, 230), (40, 170, 70), (255, 255, 255)])

    # ---- metrics.json
    items = {}
    for tid in CONTOUR_IDS:
        items[tid] = {"backlog": int(tid), "criterion": "t* の PaintingCam v1・1920×1080、評価器 ID モード（3840×2160）、包絡版の最大 ≤4 px",
                      "by_interpretation": {k: {"max_px": per[k]["contours"][tid]["value_max_px"], "p95_px": per[k]["contours"][tid]["p95_px"],
                                                "worst_display_xy": per[k]["contours"][tid].get("worst_display_xy"),
                                                "verdict": per[k]["contours"][tid]["verdict"]} for k in KEYS}}
    items["72"]["record_excluding_truth_micro_features"] = {
        "note_ja": "記録のみ。真値の内壁の外縁にある 2 つの小さな形（(856, 647) の幅 2 px・長さ約 7 px の突起と、(915, 723) の小さな輪。しぶきの点が輪郭線に付いた所で、藍線の半幅より細い）の周り 12 px の真値点と、そこへ割り当たる描画点を除いた値",
        "micro_features_display_px": MICRO_FEATURES_72, "radius_px": MICRO_RADIUS,
        "by_interpretation": {k: per[k]["72_excl_micro"] for k in KEYS}}
    items["71"] = {"backlog": 71, "criterion": "71 の空域（region71_clip）の輪郭の最大 ≤4 px",
                   "by_interpretation": {k: {"max_px": per[k]["m71"]["value_max_px"], "p95_px": per[k]["m71"]["p95_px"],
                                             "iou_region71_clip": per[k]["m71"].get("iou"), "worst_display_xy": per[k]["m71"].get("worst_display_xy"),
                                             "verdict": per[k]["m71"]["verdict"]} for k in KEYS},
                   "note_ja": "最大は (1045, 744) で、空域の下辺（原画では前景の波・右船との境）。この場面の下辺は M1 Revision01 の前景の旧うねり（仮形状）のままで、主役波の形ではない（番号27・39 の範囲）。主役波がつくる上辺と左辺は 72 と同じ点列。"}
    items["68"] = {"backlog": 68, "criterion": "同じ K* を原画視点と船上の両方に描き、波の上側（唇の先）が下側（内壁の下端）より船側にある",
                   "by_interpretation": {k: {"same_kstar_file_both_views": True,
                                             "horizontal_distance_seat_to_lip_tip_m": per[k]["d_tip"],
                                             "horizontal_distance_seat_to_face_bottom_m": per[k]["d_fb"],
                                             "upper_closer_to_boat": bool(per[k]["d_tip"] < per[k]["d_fb"]),
                                             "painting_lip_tip_right_of_face_bottom": True,
                                             # 船上機位（座席の船、D7）が未裁定なので、条件を満たしても暫定合格（定義シート第11行）
                                             "verdict": "pass-conditional" if per[k]["d_tip"] < per[k]["d_fb"] else "fail",
                                             "verdict_ja": "暫定合格（船上機位D7未裁定）" if per[k]["d_tip"] < per[k]["d_fb"] else "不合格"} for k in KEYS},
                   "verdict_note_ja": "船上機位（座席の船、D7）が未裁定。定義シート第11行（原画／船上の機位が決まるまでは合格としない）により、"
                                      "仮の座席（前景の船の eyeWorld）で条件を満たしても最終の合格にしない。",
                   "note_ja": "座席は 15_revision_layout.json の eyeWorld（前景の船）。水平距離で比べた。同じ .gwb を同じ Unity の実行で 2 視点に描いた。"}
    items["69"] = {"backlog": 69, "criterion": "原画視点で右船の船首・船尾と波の上下がすべて画面内にある",
                   "by_interpretation": {k: {"right_boat_bbox_display_px": per[k]["boat_bbox"],
                                             "right_boat_inside_scored_columns": bool(per[k]["boat_bbox"] and per[k]["boat_bbox"][0] > fm.x0 and per[k]["boat_bbox"][2] < fm.x1),
                                             "wave_crest_display_y": per[k]["p_crest"][1], "wave_base_display_y_main_section_sea": per[k]["p_sea"][1],
                                             "verdict": "pass" if (per[k]["boat_bbox"] and per[k]["boat_bbox"][0] > fm.x0 and per[k]["boat_bbox"][2] < fm.x1
                                                                   and 0 < per[k]["p_crest"][1] and per[k]["p_sea"][1] < fm.H) else "fail"} for k in KEYS},
                   "note_ja": "右船は M1 Revision01 の仮配置のまま（番号27で配置し直す）。波の下端は主断面の真下の海面の像の位置（前景に隠れる）。"}
    items["70"] = {"backlog": 70, "criterion": "原画視点の同じ画面で、波の上下の長さが右船の船首から船尾までの長さを超える",
                   "by_interpretation": {k: {"wave_vertical_extent_display_px": per[k]["wave_vert_px"], "right_boat_length_display_px": per[k]["boat_len_px"],
                                             "crest_height_m": per[k]["meta"]["crest_line"]["peak_height_m"], "right_boat_length_m": RIGHT_BOAT_LENGTH_M,
                                             "verdict": "pass" if (per[k]["boat_len_px"] and per[k]["wave_vert_px"] > per[k]["boat_len_px"]) else "fail"} for k in KEYS},
                   "note_ja": "波の上下の長さは、頂の像から主断面の真下の海面の像までの縦の距離。右船の長さは ID 画像の右船の画素の主軸方向の長さ。"}
    items["83_115_116_precheck"] = {"backlog": [83, 115, 116],
                                    "criterion": "座席から 5 万本の射線で、見える穴・切断端・開いた背面がすべて 0（事前検査。判定は番号41）",
                                    "by_interpretation": {k: {**qa["meshes"][k]["rays"],
                                                              "verdict_precheck": "pass" if (qa["meshes"][k]["rays"]["hole"] == 0 and qa["meshes"][k]["rays"]["cut_end"] == 0
                                                                                             and qa["meshes"][k]["rays"]["wave_back_open"] == 0) else "fail"} for k in KEYS},
                                    "note_ja": "Blender 5.2.2 の BVH で、座席カメラの前方を中心とする半球へ一様な 5 万本。K* と海面（y = −0.07）だけを置き、船・前景は入れていない。"}
    items["mesh_qa"] = {"criterion": "Blender ヘッドレス：非多様体・面の反転・自己交差 = 0",
                        "by_interpretation": {k: {kk: qa["meshes"][k][kk] for kk in ("nonmanifold_edges_gt2_faces", "boundary_edges", "boundary_edges_expected_grid_perimeter",
                                                                                       "wire_edges", "flipped_inconsistent_winding_edges", "degenerate_faces_area_lt_1e-8",
                                                                                       "self_intersecting_face_pairs", "flat_sea_faces_facing_down")} for k in KEYS}}
    for k in KEYS:
        m = qa["meshes"][k]
        items["mesh_qa"]["by_interpretation"][k]["verdict"] = "pass" if (m["nonmanifold_edges_gt2_faces"] == 0 and m["flipped_inconsistent_winding_edges"] == 0
                                                                         and m["self_intersecting_face_pairs"] == 0 and m["boundary_edges"] == m["boundary_edges_expected_grid_perimeter"]) else "fail"
    items["construction"] = {"criterion": "作業計画 4.0：固定位相（約 400×200）、シルエット頂点を目標の射線上へ、内部は TPS（変位 ≤ 局所寸法の 8%）、唇の厚み ≥0.3 m、両端は海面まで、断面は波峰線に垂直",
                             "by_interpretation": {}}
    for k in KEYS:
        mt = per[k]["meta"]
        items["construction"]["by_interpretation"][k] = {
            "grid_nu_nv": [mt["nu"], mt["nv"]], "vertices": mt["vertex_count"],
            "tps_total_field_max_m": mt["snap_tps"]["total_field_abs_max_m"], "tps_total_field_over_local_size_max": mt["snap_tps"]["total_field_over_local_size_max"],
            "tps_within_8pct": mt["snap_tps"]["within_cap"],
            "deconvolution_delta_max_m": mt["profile"]["deconvolution_delta_abs_max_m"], "deconvolution_delta_over_H0": mt["profile"]["deconvolution_delta_over_H0"],
            "untangle_max_move_m": mt["untangle"]["max_move_m"],
            "lip_thickness_main_row_0p75m_behind_tip_m": mt["reference_ratios_self_check_record_only"]["main_row"]["lip_vertical_thickness_0p75m_behind_tip_m"],
            "lip_thickness_min_over_lip_rows_m": mt["reference_ratios_self_check_record_only"]["lip_vertical_thickness_min_over_lip_rows_m"],
            "ends_settle_to_sea_first_last_row_max_height_m": [float(np.load(os.path.join(BUILD, "kstar", "kstar_%s_rows.npz" % k))["Y"][0].max()),
                                                                float(np.load(os.path.join(BUILD, "kstar", "kstar_%s_rows.npz" % k))["Y"][-1].max())],
            "section_planes_parallel_normal_e": True,
            "crest_line_vs_section_normal_deg_max_body_rows": mt["crest_line"]["section_normal_vs_crest_tangent_deg_max_body_rows"],
            "crest_line_vs_section_normal_deg_split": crest_angle_split(k, mt),
            "crest_line_vs_section_normal_deg_max_live_rows": mt["crest_line"]["section_normal_vs_crest_tangent_deg_max_live_rows"],
            "final_vertex_sdf_max_px_including_offframe": mt["checks"]["final_vertex_sdf_max_px"],
            "numpy_preview_envelope": mt["numpy_preview_envelope"]}
    items["reference_model"] = {"verdict": "record-only", "compare": ref_cmp, "deviation_reference_to_kstar": ref_bl["deviation"],
                                "self_check_45_ja": "45° 版の壁の厚さと唇の張り出しが参照モデル中央部の範囲（0.21〜0.31H、0.37〜0.61H）に入るか（記録のみ）",
                                "self_check_45": {"wall_over_H": ref_cmp["kstar_main_row_ratios"]["a45"]["wall_over_H"],
                                                  "wall_in_range": bool(0.21 <= ref_cmp["kstar_main_row_ratios"]["a45"]["wall_over_H"] <= 0.31),
                                                  "overhang_over_H": ref_cmp["kstar_main_row_ratios"]["a45"]["overhang_over_H"],
                                                  "overhang_in_range": bool(0.37 <= ref_cmp["kstar_main_row_ratios"]["a45"]["overhang_over_H"] <= 0.61)}}
    em0 = per["a45"]["em"]
    M = {
        "schema": "GreatWave.Step26.metrics/1",
        "number": "26（主役波の終態 K*、立体解釈 30°／45°／60°）",
        "generated_utc": now(),
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode による PC オフスクリーン描画（Camera.Render → RenderTexture → PNG）、評価器（ID モード）、Blender 5.2.2 ヘッドレスのメッシュ検査と射線検査、numpy の生成器の検査。HMD 実機の結果ではない。",
        "t_star_s": 12.0,
        "evaluator": {"commands": eval_cmds, "provisional": {k: per[k]["em"]["provisional"] for k in KEYS}, "truth_version": em0["truth"]["version"],
                      "truth_manifest_sha256": em0["truth"]["manifest_sha256"], "judged_version": em0["truth"]["judged_version"],
                      "gate": {kk: em0.get("gate", {}).get(kk) for kk in ("path", "sha256", "gate_all_pass", "truth_unchanged_since_gate", "all_pass")}},
        "summary_max_px": {k: {tid: per[k]["contours"][tid]["value_max_px"] for tid in CONTOUR_IDS + ["71"]} for k in KEYS},
        "summary_p95_px": {k: {tid: per[k]["contours"][tid]["p95_px"] for tid in CONTOUR_IDS + ["71"]} for k in KEYS},
        "items": items,
    }
    T.save_json(os.path.join(EVID, "metrics.json"), M)

    # ---- run.json
    ins = ["Tools/GWWaveGen/gw_wavegen_v1.py", "Tools/GWWaveGen/params_v1_kstar.json", "Tools/GWWaveGen/gw_wavegen.py",
           "Tools/GWWaveGen/af26_evidence.py", "Tools/GWWaveGen/af26_blender_qa.py", "Tools/GWWaveGen/af26_reference.py",
           "Tools/GWWaveGen/af26_blender_ref.py", "Tools/GWWaveGen/run_af26.ps1",
           "Tools/PaintingTruth/painting_truth.json", "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/evaluate.py",
           "Tools/PaintingTruth/targets/main_wave_outline_envelope.json", "Tools/PaintingTruth/targets/line_width_profile.json",
           "Tools/PaintingTruth/targets/masks/sky_envelope_cov.png", "Tools/PaintingTruth/targets/regions.json",
           "Tools/PaintingTruth/targets/truth_manifest.json", "Docs/Evidence/ArtFirst/23/23_gate.json",
           "Docs/Evidence/M1/Revision01/15_revision_layout.json", "Docs/References/Met_JP1847_DP130155.jpg",
           "Unity/Assets/GreatWave/ArtFirst/Editor/AF26KStar.cs", "Unity/Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF26Clay.shader", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF24IdFlat.shader",
           "Unity/Assets/GreatWave/ArtFirst/Materials/AF26_Clay.mat", "Unity/Assets/GreatWave/ArtFirst/Materials/AF26_SeaFlat.mat",
           "Unity/Assets/GreatWave/Scenes/Tests/AF26_KStar.unity", "Unity/Assets/GreatWave/Scenes/Tests/M1_StaticComposition_Revision01.unity"]
    outs = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(EVID) for f in fs if f != "run.json")
    bl = {}
    for k in KEYS:
        for f in ("kstar/kstar_%s.gwb" % k, "kstar/kstar_%s.obj" % k, "kstar/kstar_%s_meta.json" % k, "kstar/kstar_%s_rows.npz" % k,
                  "render/%s/26_%s_painting_ids.png" % (k, k), "eval/%s/metrics.json" % k):
            bl["Unity/Build/ArtFirst/26/" + f] = T.sha256_file(os.path.join(BUILD, f))
    for f in ("kstar/kstar_summary.json", "af26_build_report.json", "af26_render_report.json", "af26_blender_qa.json", "ref/26_ref_compare.json", "ref/af26_blender_ref.json"):
        bl["Unity/Build/ArtFirst/26/" + f] = T.sha256_file(os.path.join(BUILD, f))
    import PIL
    R = {
        "schema": "GreatWave.Step26.run/1", "generated_utc": now(),
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af26.ps1（下の各段をまとめて実行。Unity は unity.lock を作ってから 1 プロセスだけ）",
                     "py -3.10 Tools/GWWaveGen/gw_wavegen_v1.py",
                     "E:/6000.4.3f1/Editor/Unity.exe -batchmode -projectPath G:/Unity/GreatWave_2026_Fresh/Unity -executeMethod GreatWave.ArtFirst.EditorTools.AF26KStar.BuildAndRender -logFile Unity/Build/ArtFirst/26/unity_af26.log -quit",
                     "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26_blender_qa.py -- Unity/Build/ArtFirst/26/kstar Unity/Build/ArtFirst/26/af26_blender_qa.json <座席 eyeWorld xyz> -7 5 3",
                     "py -3.10 Tools/GWWaveGen/af26_reference.py --obj G:/research/model/wave_repair_zbrush2.obj --align <解B の JSON> --out-dir Unity/Build/ArtFirst/26/ref --tmp-dir <一時フォルダー>（SHA-256 を照合してから一時キャッシュを作る）",
                     "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26_blender_ref.py -- G:/research/model/wave_repair_zbrush2.obj <解B の JSON> Unity/Build/ArtFirst/26/kstar <ref_selected_world.npy> Unity/Build/ArtFirst/26/ref",
                     "py -3.10 Tools/GWWaveGen/af26_evidence.py"] + [eval_cmds[k] for k in KEYS],
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": PIL.__version__,
                  "unity": rep_r["unity"], "graphics": "%s / %s / %s" % (rep_r["device"], rep_r["graphicsApi"], rep_r["colorSpace"]),
                  "blender": qa["blender"], "os": platform.platform(), "houdini": None},
        "unity_build_report": rep_b, "unity_render_report": rep_r,
        "reference_model_q5": {"path": "G:/research/model/wave_repair_zbrush2.obj", "sha256_expected": "ab4124f9720d6e27d80e2ae063916292898c87606a64441043f6a64de3d53d40",
                               "use_ja": "読み取りのみ。比較の図と数値（記録のみ）にだけ使い、形状は成果物・リポジトリに入れていない。"},
        "inputs_sha256": {p: T.sha256_file(T.repo_abs(p)) for p in ins if os.path.exists(T.repo_abs(p))},
        "outputs_sha256": {T.repo_rel(p): T.sha256_file(p) for p in outs},
        "not_committed_sha256": bl,
    }
    T.save_json(os.path.join(EVID, "run.json"), R)
    print("AF26_EVIDENCE_DONE", json.dumps(M["summary_max_px"], ensure_ascii=False))


if __name__ == "__main__":
    main()
