# -*- coding: utf-8 -*-
"""番号27修正01（座席を唇の真下の右船へ移す）の証拠一式をまとめる（AF27R01Seat の Unity 描画と Blender の射線検査の後に実行）。

入力（Git 対象外）:
    Unity/Build/ArtFirst/27R01/render/af27r01_*.png・idmap.json、af27r01_build_report.json、af27r01_render_report.json、
    af27r01_seat_rays_blender.json（番号26 の af26_blender_qa.py を座席 v1 の目で実行した結果）、place/af27r01_place.json、water/
    Unity/Build/ArtFirst/CP1/render/a45/（CP1 の描画。原画視点が変わっていないかの比較の基準）、CP1/eval/a45・a45_line/metrics.json
    Unity/Build/ArtFirst/26/kstar/kstar_a45_meta.json・_rows.npz
入力（Git 対象）: Tools/GWContext/seat_v1.json、context_layout.json、Tools/PaintingTruth/ の真値 v0.2 と評価器
出力: Docs/Evidence/ArtFirst/27R01/（図、metrics.json、run.json）、Unity/Build/ArtFirst/27R01/eval/（評価器の出力）

使い方（リポジトリ根で）: py -3.10 Tools/GWContext/af27r01_evidence.py
"""
import datetime
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
sys.path.insert(0, HERE)
import af27common as C  # noqa: E402
from af27common import T  # noqa: E402
import evaluate as EV  # noqa: E402

REPO = C.REPO
BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "27R01")
RDIR = os.path.join(BUILD, "render")
CP1 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "CP1")
B26 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26", "kstar")
EVID = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "27R01")
SEAT_JSON = os.path.join(HERE, "seat_v1.json")
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
DIFF_THRESHOLD = 8        # 色画像の差：RGB のどれかが 8 段より大きく違えば「変わった画素」
CONTOUR_IDS = ["78", "130", "131", "132", "72", "71"]
REC = []


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def r4(v, n=4):
    if v is None:
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return [r4(x, n) for x in v]
    v = float(v)
    if math.isinf(v) or math.isnan(v):
        return str(v)
    return round(v, n)


def font(size):
    try:
        return ImageFont.truetype(FONT_R, size)
    except OSError:
        return ImageFont.load_default()


def label(img, lines, xy=(20, 16), size=24, fill=(255, 255, 255), shadow=(0, 0, 0), box=True):
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    f = font(size)
    if box and lines:
        w = max(dr.textlength(s, font=f) for s in lines)
        dr.rectangle([xy[0] - 8, xy[1] - 6, xy[0] + w + 8, xy[1] + len(lines) * (size + 8) + 2], fill=(20, 20, 20))
    for i, s in enumerate(lines):
        x, y = xy[0], xy[1] + i * (size + 8)
        if shadow is not None and not box:
            dr.text((x + 1, y + 1), s, font=f, fill=shadow)
        dr.text((x, y), s, font=f, fill=fill)
    return np.array(im)


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
            k = (key, m.get("target"), m.get("version"))
            out[k] = m
    return out


def mval(m):
    return m.get("value_max_px") if m.get("value_max_px") is not None else m.get("value")


def boat_stats(ids, color):
    mk = np.all(ids == np.array(color, np.uint8), -1)
    ys, xs = np.nonzero(mk)
    if not len(xs):
        return mk, None, None
    bbox = [float(xs.min()) / 2, float(ys.min()) / 2, float(xs.max()) / 2, float(ys.max()) / 2]
    Q = np.stack([xs, ys], -1).astype(np.float64) / 2.0
    _, _, vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False)
    pr = (Q - Q.mean(0)) @ vt[0]
    return mk, bbox, float(pr.max() - pr.min())


def main():
    os.makedirs(EVID, exist_ok=True)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    cam = C.Cam(spec)
    S = C.load_json(SEAT_JSON)
    place = C.load_json(os.path.join(BUILD, "place", "af27r01_place.json"))
    rep_b = C.load_json(os.path.join(BUILD, "af27r01_build_report.json"))
    rep_r = C.load_json(os.path.join(BUILD, "af27r01_render_report.json"))
    rays = C.load_json(os.path.join(BUILD, "af27r01_seat_rays_blender.json"))
    idmap_p = os.path.join(RDIR, "idmap.json")
    idmap = C.load_json(idmap_p)

    # ---------------------------------------------------------------- 評価器（原画視点）
    render = os.path.join(RDIR, "af27r01_painting.png")
    em = run_eval(render, os.path.join(RDIR, "af27r01_painting_ids.png"), idmap_p, os.path.join(BUILD, "eval", "noline"), "af27r01_painting")
    eml = run_eval(render, os.path.join(RDIR, "af27r01_painting_ids_line.png"), idmap_p, os.path.join(BUILD, "eval", "line"), "af27r01_painting_line")
    cp_em = C.load_json(os.path.join(CP1, "eval", "a45", "metrics.json"))
    cp_eml = C.load_json(os.path.join(CP1, "eval", "a45_line", "metrics.json"))
    M, Ml, Mc, Mcl = measures(em), measures(eml), measures(cp_em), measures(cp_eml)
    compare = []
    for (key, tgt, ver), m in sorted(M.items(), key=lambda kv: str(kv[0])):
        if key == "line_width":
            continue
        use_line = key in ("76", "213", "212")      # 空の項目は CP1 と同じく外殻線ありの ID で判定する
        mm = (Ml if use_line else M).get((key, tgt, ver), m)
        cc = (Mcl if use_line else Mc).get((key, tgt, ver))
        a, b = mval(mm), (mval(cc) if cc else None)
        compare.append({"item": key, "target": tgt, "version": ver, "ids": "line" if use_line else "noline",
                        "cp1_a45": r4(b), "r01": r4(a), "cp1_p95": r4(cc.get("p95_px")) if cc else None, "r01_p95": r4(mm.get("p95_px")),
                        "delta": r4(a - b) if (a is not None and b is not None and not isinstance(a, str) and not isinstance(b, str)) else None,
                        "verdict_r01": mm.get("verdict"), "verdict_cp1": cc.get("verdict") if cc else None,
                        "worst_display_xy": mm.get("worst_display_xy")})

    # ---------------------------------------------------------------- 原画視点が変わっていないか（CP1 の 45° の描画との差）
    new_rgb = T.imread_rgb(render)
    old_rgb = T.imread_rgb(os.path.join(CP1, "render", "a45", "cp1_a45_painting.png"))
    dmax = np.abs(new_rgb.astype(np.int16) - old_rgb.astype(np.int16)).max(-1)
    changed = dmax > DIFF_THRESHOLD
    ys, xs = np.nonzero(changed)
    diff_bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    ids_new = T.imread_rgb(os.path.join(RDIR, "af27r01_painting_ids.png"))
    ids_old = T.imread_rgb(os.path.join(CP1, "render", "a45", "cp1_a45_painting_ids.png"))
    id_diff = {}
    for cls, col in list(idmap["classes"].items()) + [("other", idmap["other"])]:
        a = np.all(ids_new == np.array(col, np.uint8), -1)
        b = np.all(ids_old == np.array(col, np.uint8), -1)
        id_diff[cls] = {"cp1_px_display": r4(b.sum() / 4.0, 2), "r01_px_display": r4(a.sum() / 4.0, 2),
                        "xor_px_display": r4((a ^ b).sum() / 4.0, 2), "gained_px_display": r4((a & ~b).sum() / 4.0, 2),
                        "lost_px_display": r4((~a & b).sum() / 4.0, 2)}
    mid_new, bbox_new, len_new = boat_stats(ids_new, idmap["classes"]["boat_mid"])
    mid_old, bbox_old, len_old = boat_stats(ids_old, idmap["classes"]["boat_mid"])
    # 変わった画素の色画像の図：新しい描画を暗くし、変わった画素を赤、右船の ID の輪郭（CP1 = 水色、27修正01 = 黄）を重ねる
    vis = (new_rgb.astype(np.float32) * 0.45).astype(np.uint8)
    vis[changed] = (255, 40, 40)
    for mk, col in ((mid_old, (0, 255, 255)), (mid_new, (255, 220, 0))):
        m1 = cv2.resize(mk.astype(np.uint8), (1920, 1080), interpolation=cv2.INTER_NEAREST)
        cs = cv2.findContours(m1, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
        cv2.drawContours(vis, cs, -1, col, 1)
    lines = ["原画視点の比較：CP1（K* 45°、番号27 の右船）と 27修正01（右船を k 倍して手前へ、右船の水面を作り直した）。Unity の PC オフスクリーン描画、t* = 12.0 s。",
             "赤＝色が %d 段より大きく変わった画素 %d px（%.3f%%）。水色＝CP1 の右船の見える範囲、黄＝27修正01 の右船の見える範囲（ID 画像）。" % (
                 DIFF_THRESHOLD, int(changed.sum()), 100.0 * changed.mean()),
             "右船の両端の投影は同じ（差 %.1e px）。右船の見える画素：CP1 %.0f px → %.0f px（増 %.0f・減 %.0f）。" % (
                 place["tips_projected_max_diff_px"], id_diff["boat_mid"]["cp1_px_display"], id_diff["boat_mid"]["r01_px_display"],
                 id_diff["boat_mid"]["gained_px_display"], id_diff["boat_mid"]["lost_px_display"])]
    vis = label(vis, lines, xy=(20, 16), size=22)
    # 右船の周りの拡大（左：CP1、右：27修正01）
    x0, y0, x1, y1 = 1000, 520, 1720, 940
    crop_o = cv2.resize(old_rgb[y0:y1, x0:x1], ((x1 - x0) * 4 // 3, (y1 - y0) * 4 // 3), interpolation=cv2.INTER_LINEAR)
    crop_n = cv2.resize(new_rgb[y0:y1, x0:x1], ((x1 - x0) * 4 // 3, (y1 - y0) * 4 // 3), interpolation=cv2.INTER_LINEAR)
    zoom = np.full((1080, 1920, 3), 30, np.uint8)
    h, w = crop_o.shape[:2]
    zoom[140:140 + h, 0:w] = crop_o
    zoom[140:140 + h, 1920 - w:1920] = crop_n
    zoom = label(zoom, ["右船の周りの拡大（表示 x %d〜%d、y %d〜%d を 4/3 倍）。左：CP1（番号27 の右船・右の斜面の仮置き）、右：27修正01。" % (x0, x1, y0, y1),
                        "27修正01 では右船を投影中心へ向けて縮めて手前へ置いた（像は同じ）。右の斜面の仮置きは船の周りだけ作り直し、船を載せる水面にした。"],
                 xy=(20, 30), size=24)
    T.imwrite(os.path.join(EVID, "27R01_painting.png"), new_rgb)
    T.imwrite(os.path.join(EVID, "27R01_painting_diff.png"), vis)
    T.imwrite(os.path.join(EVID, "27R01_painting_zoom.png"), zoom)

    # ---------------------------------------------------------------- 68・69・70
    meta = C.load_json(os.path.join(B26, "kstar_a45_meta.json"))
    rows = np.load(os.path.join(B26, "kstar_a45_rows.npz"))
    fr_t = np.array(meta["frame"]["t_travel"])
    O0 = np.array(meta["frame"]["section_origin_world"])
    vm = meta["rows"]["main_row"]
    A, Y = rows["A"][vm], rows["Y"][vm]
    jt = meta["profile"]["index"]["j_top"]
    crest = O0 + A[jt] * fr_t + np.array([0, Y[jt], 0])
    sea_below = O0 + A[jt] * fr_t
    p_crest, p_sea = cam.project(np.stack([crest, sea_below]))[0]
    wave_vert_px = float(p_sea[1] - p_crest[1])
    inside = bool(bbox_new and bbox_new[0] > fm.x0 and bbox_new[2] < fm.x1)
    tips_px = np.array(place["tips_projected_px"])
    tips_in = bool(np.all((tips_px[:, 0] > fm.x0) & (tips_px[:, 0] < fm.x1) & (tips_px[:, 1] > 0) & (tips_px[:, 1] < 1080)))
    eye = np.array(S["seat"]["eye_world"])
    look = np.array(S["view"]["target_world"])

    # ---------------------------------------------------------------- 座席の図
    def tile(path, w=960, h=540):
        return cv2.resize(T.imread_rgb(path), (w, h), interpolation=cv2.INTER_AREA)
    m68 = place["item68"]
    chosen = [c for c in place["seat_candidates"] if c["probe_local_z"] == S["seat"]["probe_local"][2]][0]
    seat_lip = label(T.imread_rgb(os.path.join(RDIR, "af27r01_seat_lip.png")),
                     ["座席 v1（右船、甲板から 1.2 m 上の座位の目）から唇へ。t* = 12.0 s、K* 45°＋NPR v1、縦画角 80°。Unity の PC オフスクリーン描画（HMD ではない）。",
                      "目 (%.2f, %.2f, %.2f) → 注視点＝唇先の線のうち座席に水平で最も近い点 (%.2f, %.2f, %.2f)：水平 %.2f m・仰角 %.1f°。" % (
                          *eye, *look, chosen["nearest_lip_tip_horizontal_m"], chosen["nearest_lip_tip_elevation_deg"]),
                      "主断面の唇先まで水平 %.2f m・仰角 %.1f°、頂の仰角 %.1f°。唇は波峰線の方向に短い（番号26 の限界 3、26修正01 で延ばす）。" % (
                          m68["a45"]["horizontal_distance_seat_to_lip_tip_m"], m68["a45"]["lip_tip_elevation_deg"], m68["a45"]["crest_elevation_deg"])],
                     xy=(20, 16), size=22)
    T.imwrite(os.path.join(EVID, "27R01_seat_lip.png"), seat_lip)
    seat_low = label(T.imread_rgb(os.path.join(RDIR, "af27r01_seat_low.png")),
                     ["座席 v1 から唇の方位（水平の向き %.1f°）を仰角 20° で見る。右下の藍の帯は自分の船の舷（すぐ横）、白い面は番号27 の仮置き（前景のうねり・斜面、番号39/40 で置き換え）。" % S["view"]["yaw_deg"],
                      "t* = 12.0 s、K* 45°＋NPR v1、縦画角 80°。Unity の PC オフスクリーン描画（HMD ではない）。"], xy=(20, 16), size=22)
    T.imwrite(os.path.join(EVID, "27R01_seat_low.png"), seat_low)
    ins = place["inside_boat_below_water"]
    seat_bow = label(T.imread_rgb(os.path.join(RDIR, "af27r01_seat_bow.png")),
                     ["座席 v1 から船首（船の根の局所 (0, 0.5, 4.2)）を見下ろす。黄土＝船の内側、藍の帯＝舷と梁。上の白は船の外の水面（右の斜面の作り直し）。",
                      "甲板・舷・梁の頂点で水面より下のものは 0（甲板と水面の間は最小 %.2f m）。ただし甲板の前の尖った船首の内側（局所 z > 3.5）では、" % ins["Boat_Deck_Planks"]["min_clearance_m"],
                      "平らな海（K* の y = 0 と参照海面、藍のレンズ形）と右の斜面の作り直しの縁（小さな白い三角）が船底より上に見える（限界）。Unity の PC オフスクリーン描画。"],
                     xy=(20, 16), size=22)
    T.imwrite(os.path.join(EVID, "27R01_seat_bow.png"), seat_bow)
    side = label(T.imread_rgb(os.path.join(RDIR, "af27r01_side_near.png")),
                 ["横（手前から近く、目 (5, 7, −44) → (3, 7, −13)、縦画角 50°）。右船は右の斜面を作り直した水面に船底を沈めて載る。唇は船首の上、約 4 m 奥。",
                  "Unity の PC オフスクリーン描画、t* = 12.0 s。白い角柱・板は番号27 の仮置き（番号39/40 で置き換え）。"], xy=(20, 16), size=22)
    T.imwrite(os.path.join(EVID, "27R01_side_near.png"), side)
    stern = label(T.imread_rgb(os.path.join(RDIR, "af27r01_stern.png")),
                  ["船尾の側の上から（目 (34, 22, −27) → (3, 7, −13)、縦画角 50°）。右船（中央下）は主役波の足もとの手前、唇の下。左下は手前の船（旧い座席）。",
                   "Unity の PC オフスクリーン描画、t* = 12.0 s。白い面は右の斜面の仮置きを作り直した水面と、番号27 の仮置き。"], xy=(20, 16), size=22)
    T.imwrite(os.path.join(EVID, "27R01_stern.png"), stern)
    cs = place["contact_summary"]
    contact = label(T.imread_rgb(os.path.join(RDIR, "af27r01_contact.png")),
                    ["接地の確認（右船・右船の水面・参照海面・K*・空だけを表示した確認図。場面の見え方ではない）。船の軸に直交する水平方向から仰角 12°。",
                     "船体中央部（局所 |z| ≤ 3）の船底の沈み %.2f〜%.2f m（喫水 %.2f m）。船首の先 %.2f〜%.2f m。反り上がった船尾の先は水面から最大 %.2f m 出る。" % (
                         cs["immersion_mid_min_m"], cs["immersion_mid_max_m"], place["draft_m"],
                         min(q["immersion_m"] for q in place["contact"] if q["local_z"] > 3), max(q["immersion_m"] for q in place["contact"] if q["local_z"] > 3),
                         -cs["immersion_all_min_m"])], xy=(20, 16), size=22)
    T.imwrite(os.path.join(EVID, "27R01_contact.png"), contact)
    # 旧い座席との比較（CP1 の手前の船、CP1 の候補 (a)＝番号27 の右船の置き方）と座席 v1
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    sheet[0:540, 0:960] = label(tile(os.path.join(CP1, "render", "a45", "cp1_a45_seat.png")), ["CP1 までの座席（手前の船、番号27）"], size=20)
    sheet[0:540, 960:1920] = label(tile(os.path.join(CP1, "render", "a45", "cp1_a45_seatmid.png")), ["CP1 の候補 (a)：番号27 の右船の置き方のまま（確認用）"], size=20)
    sheet[540:1080, 0:960] = label(tile(os.path.join(RDIR, "af27r01_seat_low.png")), ["座席 v1（27修正01）：唇の方位、仰角 20°"], size=20)
    sheet[540:1080, 960:1920] = label(tile(os.path.join(RDIR, "af27r01_seat_lip.png")), ["座席 v1（27修正01）：唇へ（仰角 %.0f°）" % S["view"]["pitch_deg"]], size=20)
    T.imwrite(os.path.join(EVID, "27R01_seat_compare.png"), sheet)

    # ---------------------------------------------------------------- metrics.json
    cmpd = {(c["item"], c["target"], c["version"]): c for c in compare}

    def cval(item, target, version=None):
        c = cmpd.get((item, target, version))
        return c

    items = {}
    items["D7_seat"] = {"backlog": "定義第11行（原画／船上機位の特定）", "value": {"eye_world": S["seat"]["eye_world"], "boat": "boat_mid", "seat_json": "Tools/GWContext/seat_v1.json"},
                        "verdict": "record-only", "note_ja": "D7（座席を唇の下の右船へ）を利用者が CP1 で裁定した。船上機位はこの座席 v1 に特定した。原画の機位（PaintingCam v1）は番号23 のまま。"}
    items["68"] = {"backlog": 68, "criterion": "同じ K* を原画視点と船上の両方に描き、波の上側（唇の先）が下側（内壁の下端）より座席の船側にある（番号26・CP1 と同じ式）",
                   "seat_eye_world": S["seat"]["eye_world"], "by_interpretation": m68, "verdict": m68["a45"]["verdict"],
                   "note_ja": "座席（D7）が決まったので、CP1 の「D7 待ち」の条件は解けた。判定は 45°（D6 の裁定）。t* と外輪郭の区間の境界点が番号23 で暫定である点は CP1 と同じ。"}
    items["69"] = {"backlog": 69, "criterion": "原画視点で右船の船首・船尾と波の上下がすべて画面内（採点列 %d〜%d）" % (fm.x0, fm.x1),
                   "right_boat_visible_bbox_display_px": r4(bbox_new, 2), "right_boat_visible_bbox_cp1": r4(bbox_old, 2),
                   "right_boat_tips_projected_px": r4(tips_px, 3), "tips_inside": tips_in,
                   "wave_crest_display_y": r4(p_crest[1], 2), "wave_base_display_y": r4(p_sea[1], 2),
                   "verdict": "pass" if (inside and tips_in and p_crest[1] > 0 and p_sea[1] < 1080) else "fail"}
    items["70"] = {"backlog": 70, "criterion": "原画視点で波の上下の長さが右船の全長より大きい",
                   "wave_vertical_px": r4(wave_vert_px, 2), "right_boat_visible_length_px": r4(len_new, 2), "right_boat_visible_length_px_cp1": r4(len_old, 2),
                   "right_boat_tip_to_tip_px": r4(float(np.linalg.norm(tips_px[0] - tips_px[1])), 2),
                   "world_ja": "世界の寸法では、波高 %.1f m、右船の先端間 %.2f m（番号27 は 14.61 m）。" % (meta["crest_line"]["peak_height_m"], S["boat"]["tip_to_tip_length_m"]),
                   "verdict": "pass" if wave_vert_px > max(len_new or 0, float(np.linalg.norm(tips_px[0] - tips_px[1]))) else "fail"}
    for tid in CONTOUR_IDS:
        c = cval(tid, tid, "envelope")
        v = {"cp1_a45_max_px": c["cp1_a45"], "r01_max_px": c["r01"], "cp1_p95_px": c["cp1_p95"], "r01_p95_px": c["r01_p95"], "delta_max_px": c["delta"],
             "evaluator_verdict": c["verdict_r01"]}
        if tid == "72":
            v["verdict"] = "pass" if c["r01_p95"] <= 4.0 else "fail"
            v["rule_ja"] = "72 は p95 ≤4 px で判定し、最大は記録する（利用者の CP1 回答 2026-09-26）。K* は番号26 のまま（この番号では変えていない）。"
        elif tid == "71":
            v["verdict"] = "record-only"
            v["rule_ja"] = "71・76・213 は番号39・40 が前景と右側の仮置きを置き換えた後に判定する（利用者の CP1 回答 2026-09-26）。"
        else:
            v["verdict"] = c["verdict_r01"]
        items[tid] = {"backlog": int(tid), **v}
    for key, tgt, name in (("76", "sky_dark", "76"), ("213", "sky_transition", "213")):
        c = cval(key, tgt, None)
        items[name] = {"backlog": int(name), "target": tgt, "cp1_a45_max_px": c["cp1_a45"], "r01_max_px": c["r01"], "delta_max_px": c["delta"],
                       "evaluator_verdict": c["verdict_r01"], "verdict": "record-only",
                       "rule_ja": "71・76・213 は番号39・40 の後に判定する（利用者の CP1 回答）。外殻線ありの ID で測る（CP1 と同じ）。"}
    c = cval("76", "sky_bottom", None)
    items["76"]["color_delta_e00"] = {"cp1_a45": c["cp1_a45"], "r01": c["r01"]}
    c = cval("212", "sky_top", None)
    items["212"] = {"backlog": 212, "cp1_a45_delta_e00": c["cp1_a45"], "r01_delta_e00": c["r01"], "verdict": c["verdict_r01"]}
    for tid, tgt, ver in (("74", "fuji_ridge", "claws"), ("75", "boat_fg", None), ("157", "boat_left", None), ("159", "boat_mid", None)):
        c = cval(tid, tgt, ver)
        items[tid] = {"backlog": int(tid), "target": tgt, "cp1_a45_max_px": c["cp1_a45"], "r01_max_px": c["r01"], "delta_max_px": c["delta"], "verdict": "record-only"}
    items["83_115_116_precheck"] = {"backlog": [83, 115, 116], "value": {k: v["rays"] for k, v in rays["meshes"].items()},
                                    "eye": rays["eye"], "look_at": rays["look_at"], "verdict": "record-only",
                                    "note_ja": "番号26 の af26_blender_qa.py を座席 v1 の目で実行（K* と海面だけ、5 万本、半球の中心は唇の方位・仰角 20°）。合否は番号41。"}
    items["89_contact"] = {"backlog": 89, "value": place["contact_summary"], "draft_m": place["draft_m"], "per_slice": place["contact"],
                           "verdict": "record-only",
                           "note_ja": "右船の船底（船の根の局所 z の切り口ごとの最も低い点）の、船の外側の水面（右船の水面＝右の斜面の作り直し、K* の平らな海、参照海面の最も高いもの）からの沈み。"
                                      "正が水面より下。89（航行中の接水）は V1 の項目で、ここは t* の静止した置き方の記録。"}
    items["90_inside"] = {"backlog": 90, "value": place["inside_boat_below_water"], "eye_above_water_m": place["eye_above_water_m"], "verdict": "record-only",
                          "note_ja": "甲板・舷・梁の頂点のうち、その真下の水面（穴を開けた後の右船の水面・K*・参照海面）より低いものの数。0 なら水面は甲板と座席を横切らない。"
                                     "船首の先（甲板の前、局所 z > 3.5）の内側は、平らな海（K* の y = 0 と参照海面）が船底より上を通る（限界）。"}
    painting_check = {"color_changed_px": int(changed.sum()), "color_changed_fraction": r4(changed.mean(), 6), "threshold_8bit": DIFF_THRESHOLD,
                      "color_changed_bbox_display": diff_bbox, "id_class_diff_display_px": id_diff,
                      "right_boat_tips_projected_px_27": place["tips_projected_px_27"], "right_boat_tips_projected_px": place["tips_projected_px"],
                      "right_boat_tips_max_diff_px": place["tips_projected_max_diff_px"],
                      "contours_max_abs_delta_px": r4(max(abs(cval(t, t, "envelope")["delta"]) for t in ["78", "130", "131", "132", "72"]), 4)}
    status = {k: v.get("verdict") for k, v in items.items()}
    M_out = {
        "schema": "GreatWave.AF27R01.metrics/1", "number": "27修正01", "generated_utc": now(),
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor（batchmode、%s、%s、%s）の PC オフスクリーン描画と、その画像を番号23 の評価器（ID モード、包絡版、真値 v0.2）で測った値。"
                            "座席からの射線は Blender 5.2.2 ヘッドレス。接水と浸水は numpy。HMD 実機の結果ではない。" % (rep_r["graphicsApi"], rep_r["colorSpace"], rep_r["device"]),
        "evaluator_provisional": em.get("provisional"),
        "decisions_ja": "D7 = 右船（唇の真下）、D6 = 45°、72 は p95 ≤4 px で判定、71・76・213 は番号39・40 の後に判定（利用者の CP1 回答 2026-09-26）。",
        "seat_v1": {"eye_world": S["seat"]["eye_world"], "target_world": S["view"]["target_world"], "yaw_deg": S["view"]["yaw_deg"], "pitch_deg": S["view"]["pitch_deg"],
                    "probe_local": S["seat"]["probe_local"], "eye_unity_minus_numpy_m": r4(rep_b["eyeDiff"], 7)},
        "right_boat": {"k": place["k"], "tips_depth_m_27": place["tips_depth_m_27"], "tips_depth_m": place["tips_depth_m"],
                       "root_depth_m_27": place["root_depth_m_27"], "root_depth_m": place["root_depth_m"],
                       "tip_to_tip_length_m_27": place["tip_to_tip_length_m_27"], "tip_to_tip_length_m": place["tip_to_tip_length_m"],
                       "position_27": place["position_27"], "position": place["position"], "scale": place["scale"], "draft_m": place["draft_m"],
                       "keel_line": place["keel_line"], "water_mesh": place["water"]},
        "seat_candidates": place["seat_candidates"],
        "painting_view_check": painting_check,
        "evaluator_compare_cp1_a45": compare,
        "unity_contact_check": {"water_probes": [{k: r4(v, 4) if not isinstance(v, bool) else v for k, v in q.items()} for q in rep_r["waterProbes"]],
                                "water_minus_keel_line_min_m": r4(min(q["waterMinusKeelLine"] for q in rep_r["waterProbes"]), 4),
                                "water_minus_keel_line_max_m": r4(max(q["waterMinusKeelLine"] for q in rep_r["waterProbes"]), 4),
                                "draft_m": place["draft_m"],
                                "note_ja": "Unity の MeshCollider で、船の軸に沿った s = −3, 0, +3 m、軸から左右へ水平に 1.75 m の点の真上から右船の水面へ射線を当てた。"
                                           "水面の高さ − 竜骨の線（numpy の当てはめ）が喫水に近ければ、船の外側の水位が船底の線に沿っている。"
                                           "船の根の原点の真下は船体の足跡の穴（船底より 5 cm 下）なので使わない（keel_mid_hole_surface_below_root_m はその穴の面の記録）。",
                                "keel_mid_hole_surface_below_root_m": r4(rep_r["keelMidBelowWater"], 4)},
        "items": items, "status": status,
    }
    C.save_json(os.path.join(EVID, "metrics.json"), M_out)

    # ---------------------------------------------------------------- run.json
    def sha_rel(p):
        return {T.repo_rel(p): C.sha256(p)}
    committed_inputs = [SEAT_JSON, C.LAYOUT_JSON, os.path.join(HERE, "af27r01_seat.py"), os.path.join(HERE, "af27r01_evidence.py"),
                        os.path.join(HERE, "run_af27r01_unity.ps1"), os.path.join(HERE, "af27common.py"), os.path.join(HERE, "af27_place.py"),
                        os.path.join(REPO, "Unity", "Assets", "GreatWave", "ArtFirst", "Editor", "AF27R01Seat.cs"),
                        os.path.join(REPO, "Unity", "Assets", "GreatWave", "ArtFirst", "Meshes", "AF27R01_RightSlope.asset"),
                        os.path.join(REPO, "Unity", "Assets", "GreatWave", "ArtFirst", "Prefabs", "AF27R01_Context.prefab"),
                        os.path.join(REPO, "Unity", "Assets", "GreatWave", "Scenes", "Tests", "AF27R01_Seat.unity"),
                        os.path.join(REPO, "Tools", "PaintingTruth", "evaluate.py"), os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json"),
                        os.path.join(REPO, "Tools", "GWWaveGen", "af26_blender_qa.py")]
    not_committed = [os.path.join(RDIR, f) for f in sorted(os.listdir(RDIR))] + [
        os.path.join(BUILD, "water", "af27r01_right_slope.bin"), os.path.join(BUILD, "water", "af27r01_right_slope.json"),
        os.path.join(BUILD, "place", "af27r01_place.json"), os.path.join(BUILD, "af27r01_seat_rays_blender.json"),
        os.path.join(BUILD, "af27r01_build_report.json"), os.path.join(BUILD, "af27r01_render_report.json"),
        os.path.join(BUILD, "eval", "noline", "metrics.json"), os.path.join(BUILD, "eval", "line", "metrics.json"),
        os.path.join(CP1, "render", "a45", "cp1_a45_painting.png"), os.path.join(CP1, "render", "a45", "cp1_a45_painting_ids.png"),
        os.path.join(CP1, "eval", "a45", "metrics.json"), os.path.join(CP1, "eval", "a45_line", "metrics.json"),
        os.path.join(B26, "kstar_a45.gwb"), os.path.join(B26, "kstar_a45_meta.json"), os.path.join(B26, "kstar_a45_rows.npz"),
        os.path.join(C.BUILD, "dump", "boat_blockout.bin"), os.path.join(C.BUILD, "dump", "revision_slopes.bin"), os.path.join(C.BUILD, "dump", "dump.json")]
    outs = [os.path.join(EVID, f) for f in sorted(os.listdir(EVID)) if f not in ("run.json",)]
    run = {
        "schema": "GreatWave.AF27R01.run/1", "number": "27修正01", "generated_utc": now(),
        "commands": ["py -3.10 Tools/GWContext/af27r01_seat.py",
                     "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWContext/run_af27r01_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF27R01Seat.BuildAndRender -Log build_render",
                     "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26_blender_qa.py -- Unity/Build/ArtFirst/26/kstar "
                     "Unity/Build/ArtFirst/27R01/af27r01_seat_rays_blender.json %s %s" % (" ".join("%.4f" % v for v in rays["eye"]), " ".join("%.4f" % v for v in rays["look_at"])),
                     "py -3.10 Tools/GWContext/af27r01_evidence.py"] + REC,
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": Image.__version__,
                  "unity": rep_b["unity"], "graphics": "%s / %s / %s" % (rep_r["device"], rep_r["graphicsApi"], rep_r["colorSpace"]),
                  "blender": rays["blender"]},
        "unity_build_report": {k: rep_b[k] for k in ("utc", "sceneSha256", "prefabSha256", "meshSha256", "meshVertices", "eyeDiff", "protectedUnchanged")},
        "unity_protected_files_unchanged": rep_b["protectedUnchanged"] and rep_r["protectedUnchanged"],
        "unity_protected_files": rep_b["protectedFiles"],
        "committed_sha256": {k: v for p in committed_inputs for k, v in sha_rel(p).items()},
        "outputs_sha256": {k: v for p in outs for k, v in sha_rel(p).items()},
        "not_committed_sha256": {k: v for p in not_committed if os.path.exists(p) for k, v in sha_rel(p).items()},
        "forbidden_ja": "旧試作の禁止場所、G:\\research\\model（参照モデルを含む）、732e198 より前の履歴には触れていない。Houdini は使っていない。番号26・27・28・CP1 のファイルは変えていない（Unity の前後の SHA-256 と Git の差分で確認）。",
    }
    C.save_json(os.path.join(EVID, "run.json"), run)
    print(json.dumps(status, ensure_ascii=False))
    print("painting changed px", int(changed.sum()), diff_bbox, "boat_mid", id_diff["boat_mid"])
    for c in compare:
        print(c["item"], c["target"], c["version"], c["ids"], c["cp1_a45"], "->", c["r01"], c["delta"])


if __name__ == "__main__":
    main()
