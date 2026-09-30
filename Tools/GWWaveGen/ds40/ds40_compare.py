# -*- coding: utf-8 -*-
"""設計40 第「比較」部：段階7（設計36〜39）までを入れた t*（t = 12 s）の原画視点を、美術優先23 の評価器の全項目で測り、
座席 v1・側面・背面の並べ図と、参照モデル（Q5・D24）の配置との比較図（記録のみ。数値と印だけで、参照モデルは描かない）を作る。

入力（どれも Git 対象外）:
    Unity/Build/Design/40/compare/unity/   DS40Render.Render の出力（full/ の色画像と全体の ID 画像、views/、mock/、t28_*、ds40_render_report.json）
    Unity/Build/Design/40/compare/unity/ds30_tstar_regress.json  ds30b_tstar_regress.py の出力（色区の項目・大きな輪郭の関門・両側の読み）
    Unity/Build/Design/39/paper/unity/     設計39 の出力（紙の 3 層を切った画像が同じであることの照合）
    Unity/Build/Design/30/ref/ds30_ref_layout.json  設計30 が参照モデルから測った配置の数値だけ（この番号では OBJ を開かない）
    Unity/Build/Design/28R01F/kstar_final/ K*′ R4 の meta と rows（68・69・70 の式。CP1 と同じ）
    Unity/Build/ArtFirst/CP1/render/a45/   CP1 の画像（並べ図）、Unity/Build/Design/30/unity/single_fix1/stills/ 設計30 の t* の画像
入力（Git 対象）:
    Docs/Evidence/ArtFirst/CP1/metrics.json（CP1 の値）、Docs/Evidence/Design/30/ds30_layout_record.json・run.json（配置の二次設計と海のパッケージの SHA-256）
処理:
    1) 評価器 Tools/PaintingTruth/evaluate.py（ID モード）を、紙の 3 層を切った作品のままの色画像（白・爪・飛沫・線）と全体の ID 画像で回す。
       輪郭（78〜72・71、富士・3隻）は線なしの ID、空の項目（76・212・213）は線ありの ID（CP1 と同じ組み合わせ）。
       記録：紙の 3 層を全部入れた色画像、爪を ID から除いた線なしの ID。
    2) 68・69・70 を CP1 と同じ式で K*′ と座席 v1 から測る。94 はカメラの値の照合。
    3) 計画 §2.0 の回帰の表：29修正01・設計30（段階5 の終わり）・設計39 の値と比べ、CP1／26修正01 に対する後退（段階5確認 §6.3）も並べる。
    4) 図：原画 50% の重ね図、評価器の偏差図、座席 v1・側面・背面の並べ図、配置の比較図、項目の表。
出力：Unity/Build/Design/40/compare/{eval/,fig/,ds40_compare_metrics.json,ds40_acceptance.json}

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds40/ds40_compare.py [--skip-eval]
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
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

OUT = os.path.join(REPO, "Unity", "Build", "Design", "40", "compare")
U40 = os.path.join(OUT, "unity")
U39 = os.path.join(REPO, "Unity", "Build", "Design", "39", "paper", "unity")
U38 = os.path.join(REPO, "Unity", "Build", "Design", "38", "outlines", "unity")
CP1R = os.path.join(REPO, "Unity", "Build", "ArtFirst", "CP1", "render", "a45")
S30 = os.path.join(REPO, "Unity", "Build", "Design", "30", "unity", "single_fix1", "stills")
KSTAR = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final")
REF30 = os.path.join(REPO, "Unity", "Build", "Design", "30", "ref", "ds30_ref_layout.json")
LAY30 = os.path.join(REPO, "Docs", "Evidence", "Design", "30", "ds30_layout_record.json")
RUN30 = os.path.join(REPO, "Docs", "Evidence", "Design", "30", "run.json")
CP1M = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "CP1", "metrics.json")
SEAT = os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")
FIG = os.path.join(OUT, "fig")
EVAL = os.path.join(OUT, "eval")
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
FONT_B = r"C:\Windows\Fonts\YuGothB.ttc"
W, H = 1920, 1080
# 全体の ID 画像の色（DS40Render の凡例。船は AF24 ID Flat に 0.4 を渡し、線形の RT で 34 になった値をそのまま使う）
IDMAP = {"classes": {"sky": [0, 255, 255], "boat_left": [34, 0, 0], "boat_mid": [0, 34, 0], "boat_fg": [34, 34, 0]},
         "other_ja": "ほかの色はすべて other：keypose のシート・爪の色区 ID（白 (255,0,0)・水色 (0,255,0)・藍中 (0,0,255)・藍濃 (255,255,0)）、線 (255,0,255)、CPU のメッシュ (0,0,0)",
         "note_ja": "設計40 の全体の ID 画像（3840×2160、線形、MSAA なし）。空＝空のドームとカメラの背景。3隻はそれぞれの色。飛沫は入れない。"}
PAINTING_CAM_CP1 = {"position": [0.0, 3.0, -62.0], "euler": [354.20758056640625, 357.83074951171875, 0.0]}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")


def r4(v, n=4):
    if v is None:
        return None
    v = float(v)
    return None if (math.isnan(v) or math.isinf(v)) else round(v, n)


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT_R, size)
    except OSError:
        return ImageFont.load_default()


def label(img, lines, xy=(10, 8), size=22, fill=(255, 255, 255), shadow=(0, 0, 0)):
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    f = font(size)
    for i, s in enumerate(lines):
        x, y = xy[0], xy[1] + i * (size + 8)
        if shadow is not None:
            dr.text((x + 1, y + 1), s, font=f, fill=shadow)
        dr.text((x, y), s, font=f, fill=fill)
    return np.array(im)


def rgb(p):
    return cv2.imread(p, cv2.IMREAD_COLOR)[:, :, ::-1].copy()


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


def run_eval(render, ids, name):
    od = os.path.join(EVAL, name)
    os.makedirs(od, exist_ok=True)
    idmap = os.path.join(EVAL, "idmap.json")
    cmd = [sys.executable, "-B", os.path.join(REPO, "Tools", "PaintingTruth", "evaluate.py"), "--render", render, "--ids", ids, "--idmap", idmap,
           "--out-dir", od, "--name", name]
    subprocess.run(cmd, check=True, cwd=REPO, stdout=subprocess.DEVNULL)
    return load(os.path.join(od, "metrics.json")), "py -3.10 -B Tools/PaintingTruth/evaluate.py --render %s --ids %s --idmap %s --out-dir %s --name %s" % (
        rel(render), rel(ids), rel(idmap), rel(od), name)


def unity_project(cam, P):
    """Unity の worldToCameraMatrix・projectionMatrix（行優先 16 個）で表示 px へ（y は上から）。"""
    V = np.array(cam["worldToCamera"], np.float64).reshape(4, 4)
    Pm = np.array(cam["projection"], np.float64).reshape(4, 4)
    X = np.c_[np.asarray(P, np.float64), np.ones(len(P))]
    c = (Pm @ (V @ X.T)).T
    nd = c[:, :2] / c[:, 3:4]
    return np.stack([(nd[:, 0] * 0.5 + 0.5) * W, (1 - (nd[:, 1] * 0.5 + 0.5)) * H], 1), c[:, 3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-eval", action="store_true")
    a = ap.parse_args()
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(EVAL, exist_ok=True)
    save(os.path.join(EVAL, "idmap.json"), IDMAP)
    rep = load(os.path.join(U40, "ds40_render_report.json"))
    cams = {c["view"]: c for c in rep["cameras"]}
    imgs = {(i["view"], i["cond"]): i for i in rep["images"]}
    res = {"schema": "GreatWave.DS40.compare/1", "number": "設計40 第「比較」部", "generated_utc": now(),
           "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode の PC オフスクリーン描画（camera.Render、RTX 3080、Direct3D11）と、その画像の numpy・OpenCV の測定。HMD 実機の結果ではない。",
           "unity_report": {"path": rel(os.path.join(U40, "ds40_render_report.json")), "sha256": sha(os.path.join(U40, "ds40_render_report.json")),
                            "protectedUnchanged": rep["protectedUnchanged"], "scene": rep["scene"], "sceneSha256": rep["sceneSha256"], "secondsTotal": rep["secondsTotal"]}}

    # ---------------------------------------------------------------- 0. 照合：紙の 3 層を切った画像は設計38・39 と同じ
    chk = {"t28_same_as_39": {}, "t28_same_as_38": {}}
    for s in ("t28_claws", "t28_white"):
        d40 = os.path.join(U40, s, "t28", "render")
        for f in sorted(os.listdir(d40)):
            chk["t28_same_as_39"][s + "/" + f] = sha(os.path.join(d40, f)) == sha(os.path.join(U39, s, "t28", "render", f))
            p38 = os.path.join(U38, s, "t28", "render", f)
            chk["t28_same_as_38"][s + "/" + f] = (sha(os.path.join(d40, f)) == sha(p38)) if os.path.exists(p38) else None
    p_off = os.path.join(U40, "full", "painting_t120_off.png")
    p_all = os.path.join(U40, "full", "painting_t120_all.png")
    a0, b0 = rgb(p_off), rgb(os.path.join(U39, "onoff", "ds39_painting_t120_off.png"))
    a1, b1 = rgb(p_all), rgb(os.path.join(U39, "onoff", "ds39_painting_t120_all.png"))
    chk["painting_off_vs_ds39_off_differing_px"] = int((np.abs(a0.astype(int) - b0.astype(int)).max(-1) > 0).sum())
    d_all = np.abs(a1.astype(int) - b1.astype(int)).max(-1)
    chk["painting_all_vs_ds39_all_differing_px"] = int((d_all > 0).sum())
    chk["painting_all_vs_ds39_all_max_channel_diff"] = int(d_all.max())
    ys, xs = np.nonzero(d_all > 0)
    chk["painting_all_vs_ds39_all_bbox_xyxy"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    chk["note_ja"] = ("紙の 3 層を切った原画視点（評価の状態）は設計39 の切の画像と画素まで同じ。全部入の画像の違いは記録（小飛沫の子の粒の描き順か、"
                      "設計39 の onoff が同じ場面で ①→②→③ の順に入切した後の描画であることによる。評価には使わない）。")
    # ID 画像の色の数え（凡例のとおりか）
    idc = {}
    for nm in ("ids_noline", "ids_line", "ids_noline_noclaws", "ids_line_noclaws"):
        im = rgb(os.path.join(U40, "full", nm + ".png"))
        u, cnt = np.unique(im.reshape(-1, 3), axis=0, return_counts=True)
        idc[nm] = {"colours": {"%d,%d,%d" % tuple(int(x) for x in uu): int(c) for uu, c in zip(u, cnt)}, "n_colours": int(len(u))}
    chk["id_colour_census"] = idc
    res["crosscheck"] = chk

    # ---------------------------------------------------------------- 1. 評価器（全項目）
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    truth = EV.Truth()
    runs = {"off_noline": (p_off, "ids_noline"), "off_line": (p_off, "ids_line"), "all_line": (p_all, "ids_line"),
            "off_noline_noclaws": (p_off, "ids_noline_noclaws"), "all_noline": (p_all, "ids_noline")}
    em, cmds = {}, []
    for k, (rp, idn) in runs.items():
        idp = os.path.join(U40, "full", idn + ".png")
        if a.skip_eval and os.path.exists(os.path.join(EVAL, k, "metrics.json")):
            em[k] = load(os.path.join(EVAL, k, "metrics.json"))
            cmds.append("（前回の出力を読んだ）" + k)
        else:
            em[k], c = run_eval(rp, idp, k)
            cmds.append(c)
        print("eval", k, flush=True)
    res["evaluator_commands"] = cmds
    res["evaluator_gate"] = {k: {"provisional": v["provisional"], "truth_manifest_sha256": v["truth"]["manifest_sha256"]} for k, v in em.items()}

    # ---------------------------------------------------------------- 2. 68・69・70・94（CP1 と同じ式）
    meta = load(os.path.join(KSTAR, "kstarR4_a45_meta.json"))
    rows = np.load(os.path.join(KSTAR, "kstarR4_a45_rows.npz"))
    fr = meta["frame"]
    et, tt, O0 = np.array(fr["e_crest"]), np.array(fr["t_travel"]), np.array(fr["section_origin_world"])
    vm = int(meta["rows"]["main_row"])
    Aa, Yy = rows["A"][vm], rows["Y"][vm]
    ix = meta["profile"]["index"]
    jt, jk, jf = ix["j_top"], ix["j_corner"], ix["j_facebot"]
    world = lambda aa, yy: O0 + aa * tt + np.array([0, 1.0, 0]) * yy  # noqa: E731
    jtip = jt + int(np.argmax(Aa[jt:jk + 1]))
    tip, fb, crest, sea_below = world(Aa[jtip], Yy[jtip]), world(Aa[jf], Yy[jf]), world(Aa[jt], Yy[jt]), world(Aa[jt], 0.0)
    cam = G0.PaintingCam(spec)
    p_crest, p_sea = cam.project(crest[None])[0], cam.project(sea_below[None])[0]
    pu, _ = unity_project(cams["painting"], np.stack([crest, sea_below]))
    seat = load(SEAT)
    eye = np.array(seat["seat"]["eye_world"], np.float64)
    ids = rgb(os.path.join(U40, "full", "ids_noline.png"))
    mid = np.all(ids == np.array(IDMAP["classes"]["boat_mid"], np.uint8), -1)
    ys, xs = np.nonzero(mid)
    Q = np.stack([xs, ys], -1).astype(np.float64) / 2.0
    _, _, vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False)
    pr = (Q - Q.mean(0)) @ vt[0]
    blen = float(pr.max() - pr.min())
    bbox = [float(xs.min()) / 2, float(ys.min()) / 2, float(xs.max()) / 2, float(ys.max()) / 2]
    d_tip, d_fb = float(np.hypot(*(tip - eye)[[0, 2]])), float(np.hypot(*(fb - eye)[[0, 2]]))
    wave_vert = float(p_sea[1] - p_crest[1])
    inside = bool(bbox[0] > fm.x0 and bbox[2] < fm.x1)
    geo = {
        "68": {"criterion": "同じ波を原画視点と座席の両方に描き、唇の先が内壁の下端より座席の船側にある（水平距離）",
               "seat_eye_world": eye.tolist(), "seat_source": "Tools/GWContext/seat_v1.json（D7 で決まった座席 v1）",
               "horizontal_distance_seat_to_lip_tip_m": r4(d_tip, 3), "horizontal_distance_seat_to_face_bottom_m": r4(d_fb, 3),
               "lip_tip_elevation_deg": r4(math.degrees(math.atan2(tip[1] - eye[1], d_tip)), 1),
               "verdict": "pass" if d_tip < d_fb else "fail",
               "note_ja": "CP1 と同じ式（K* の主断面の唇の先・内壁の下端）。形は K*′ R4（設計28修正01 の最後の一コマ）。CP1 は座席（D7）未確定で pass-conditional、今は座席 v1 が決まっている。"},
        "69": {"criterion": "原画視点で右船（座席の船 boat_mid）の船首・船尾と波の上下がすべて画面内（採点列 %d〜%d）" % (fm.x0, fm.x1),
               "right_boat_bbox_display_px": [r4(v, 1) for v in bbox], "right_boat_inside_scored_columns": inside,
               "wave_crest_display_y": r4(p_crest[1], 2), "wave_base_display_y_main_section_sea": r4(p_sea[1], 2),
               "unity_camera_crosscheck_px": r4(float(np.abs(pu - np.stack([p_crest[:2], p_sea[:2]])).max()), 3),
               "verdict": "pass" if (inside and 0 < p_crest[1] and p_sea[1] < fm.H) else "fail"},
        "70": {"criterion": "原画視点の同じ画面で、波の上下の長さが右船の船首から船尾までの長さを超える",
               "wave_vertical_extent_display_px": r4(wave_vert, 2), "right_boat_visible_length_display_px": r4(blen, 2),
               "crest_height_m": r4(float(crest[1]), 3), "verdict": "pass" if wave_vert > blen else "fail"},
    }
    pc = cams["painting"]
    geo["94"] = {"criterion": "原画視点のカメラが t* の前後で動かない（番号27 の 510 コマの検査を引き継ぐ）",
                 "painting_camera_position": pc["position"], "painting_camera_euler": pc["euler"], "fov": pc["fov"],
                 "cp1_camera": PAINTING_CAM_CP1,
                 "max_position_delta_vs_cp1_m": r4(float(np.abs(np.array([pc["position"][k] for k in "xyz"]) - np.array(PAINTING_CAM_CP1["position"])).max()), 6),
                 "verdict": "pass" if float(np.abs(np.array([pc["position"][k] for k in "xyz"]) - np.array(PAINTING_CAM_CP1["position"])).max()) < 1e-4 else "fail",
                 "note_ja": "この番号では静止画だけで、コマを通したカメラの検査は回していない（CP1 と同じく番号27 の 510 コマの値を引き継ぐ）。場面のカメラの値が CP1 の PaintingCam v1 と同じことを照合した。"}
    res["geometry_items"] = geo

    # ---------------------------------------------------------------- 3. 項目の表
    cp1 = load(CP1M)["items"]
    reg = load(os.path.join(U40, "ds30_tstar_regress.json"))
    reg39 = os.path.join(U39, "ds30_tstar_regress.json")
    rem = {s: load(os.path.join(U40, s, "ds27_tstar_remeasure.json")) for s in ("t28_claws", "t28_white")}
    symj = {s: load(os.path.join(U40, "tstar_sym_" + s, "tstar_sym.json")) for s in ("t28_claws", "t28_white")}
    base29 = reg["base_29r01"]
    table = []

    def row(item, name, reading, v40, v39=None, v30=None, v29=None, vcp1=None, v26=None, verdict=None, judged=True, note=""):
        table.append({"item": item, "name_ja": name, "reading_ja": reading, "cp1": vcp1, "r26r01": v26, "r29r01": v29, "ds30": v30, "ds39": v39,
                      "ds40": v40, "verdict_ds40": verdict, "judged": judged, "note_ja": note})

    cl, wh = reg["sets"]["t28_claws"], reg["sets"]["t28_white"]
    s26 = {r["item"]: r for r in rem["t28_claws"]["silhouettes_vs_26r01_28r01"]}
    for k, nm in (("78", "左端から斜め上への外形"), ("130", "左側の傾き"), ("131", "上側へのつながり")):
        rv = cl["verdict"]["silhouettes_vs_kstar_prime"]["rows"][k]
        b = base29["silhouettes_vs_kstar_prime"]["rows"][k]
        row(k, nm, "t* の主役波の ID（評価器23、包絡版）の最大 px。判定は K*′ の幾何の値との差 ≤0.5 px（29修正01 の読み）",
            rv["unity_max_px"], v39=rv["unity_max_px"], v30=b["unity_max_px"], v29=b["unity_max_px"], vcp1=cp1[k]["by_interpretation"]["a45"]["max_px"],
            v26=s26[k]["r26r01_max_px"], verdict="pass" if (abs(rv["diff_px"]) <= 0.5 and rv["unity_max_px"] <= 4) else "fail",
            note="全体の合成（near・船・富士入り）の値は %.4f px（記録）" % contour(em["off_noline"], k)["value_max_px"])
    row("132", "船側への曲がり", "大きな輪郭 σ12 の最大 px（28修正01 の関門の読み）", r4(cl["lfgate"]["132_sigma12_max"]), v39=r4(cl["lfgate"]["132_sigma12_max"]),
        v30=r4(base29["lfgate"]["132_sigma12_max"]), v29=r4(base29["lfgate"]["132_sigma12_max"]), vcp1=cp1["132"]["by_interpretation"]["a45"]["max_px"],
        v26=s26["132"]["r26r01_max_px"], verdict="pass" if cl["lfgate"]["132_sigma12_max"] <= 4 else "fail",
        note="細部込みの最大（評価器23、t* の主役波の ID）%.4f px、全体の合成 %.4f px（記録）" % (s26["132"]["ds27_max_px"], contour(em["off_noline"], "132")["value_max_px"]))
    row("72", "内側の輪郭", "大きな輪郭 σ24 の p95 px（28修正01 の関門の読み）。爪あり（判定）", r4(cl["lfgate"]["72_sigma24_p95"]), v39=r4(cl["lfgate"]["72_sigma24_p95"]),
        v30=r4(base29["lfgate"]["72_sigma24_p95"]), v29=r4(base29["lfgate"]["72_sigma24_p95"]), vcp1=cp1["72"]["by_interpretation"]["a45"]["p95_px"],
        v26=s26["72"]["r26r01_p95_px"], verdict="pass" if cl["lfgate"]["72_sigma24_p95"] <= 4 else "fail",
        note="爪なし %.4f px（段階5 の終わりと同じ）。細部込みの p95 %.4f px・全体の合成 p95 %.4f px（記録）" % (
            wh["lfgate"]["72_sigma24_p95"], s26["72"]["ds27_p95_px"], contour(em["off_noline"], "72")["p95_px"]))
    m71 = contour(em["off_noline"], "71")
    row("71", "内側の空域", "評価器23 の最大 px（全体の合成、線なしの ID）。記録のみ（Q7 の既定）", m71["value_max_px"], vcp1=cp1["71"]["by_interpretation"]["a45"]["max_px"],
        verdict="record-only", judged=False, note="p95 %.4f px、IoU %s。下辺は near の小波・右の高い波と座席の船" % (m71["p95_px"], m71.get("iou")))
    g = geo
    row("68", "唇の先が内壁の下端より座席の船側", "座席 v1 から唇の先・内壁の下端までの水平距離 m", "%.2f < %.2f" % (g["68"]["horizontal_distance_seat_to_lip_tip_m"], g["68"]["horizontal_distance_seat_to_face_bottom_m"]),
        vcp1="%.1f < %.1f（座席未確定）" % (cp1["68"]["by_interpretation"]["a45"]["horizontal_distance_seat_to_lip_tip_m"], cp1["68"]["by_interpretation"]["a45"]["horizontal_distance_seat_to_face_bottom_m"]),
        verdict=g["68"]["verdict"], note="CP1 は旧い座席（番号27）で pass-conditional")
    row("69", "右船と波の上下が画面内", "右船の bbox（表示 px）と頂・海の y", "船 x %.0f〜%.0f、頂 y %.1f・海 y %.1f" % (g["69"]["right_boat_bbox_display_px"][0], g["69"]["right_boat_bbox_display_px"][2], g["69"]["wave_crest_display_y"], g["69"]["wave_base_display_y_main_section_sea"]),
        vcp1="船 x %.0f〜%.0f、頂 y %.1f・海 y %.1f" % (cp1["69"]["by_interpretation"]["a45"]["right_boat_bbox_display_px"][0], cp1["69"]["by_interpretation"]["a45"]["right_boat_bbox_display_px"][2],
                                                cp1["69"]["by_interpretation"]["a45"]["wave_crest_display_y"], cp1["69"]["by_interpretation"]["a45"]["wave_base_display_y_main_section_sea"]),
        verdict=g["69"]["verdict"], note="29修正01・設計30 では測っていない（段階6確認 §4.1）")
    row("70", "波の上下 > 右船の全長", "表示 px", "%.1f > %.1f" % (g["70"]["wave_vertical_extent_display_px"], g["70"]["right_boat_visible_length_display_px"]),
        vcp1="%.1f > %.1f" % (cp1["70"]["by_interpretation"]["a45"]["wave_vertical_extent_display_px"], cp1["70"]["by_interpretation"]["a45"]["right_boat_visible_length_display_px"]),
        verdict=g["70"]["verdict"], note="頂の高さ %.2f m（K*′）。CP1 は旧い K*（20.88 m）と番号27 の右船" % g["70"]["crest_height_m"])
    m212 = meas(em["off_line"], "212", "sky_top")
    row("212", "空の上の方", "ΔE00（空の上の色区の中央値、線ありの ID）", r4(m212["value"]), vcp1=cp1["212"]["by_interpretation"]["a45"]["dE00_sky_top"],
        verdict=m212["verdict"], note="紙の 3 層を全部入れた記録 ΔE00 %.4f" % meas(em["all_line"], "212", "sky_top")["value"])
    m76c, m76d = meas(em["off_line"], "76", "sky_dark"), meas(em["off_line"], "76", "sky_bottom")
    row("76", "暗い空の範囲・色", "範囲の最大 px／ΔE00。記録のみ（Q7 の既定）", "%.2f px／ΔE00 %.3f" % (m76c["value_max_px"], m76d["value"]),
        vcp1="%.2f px／ΔE00 %.3f" % (cp1["76"]["by_interpretation"]["a45"]["contour_max_px"], cp1["76"]["by_interpretation"]["a45"]["color_dE00_sky_bottom"]),
        verdict="record-only", judged=False, note="範囲の p95 %.2f px（CP1 %.2f）" % (m76c["p95_px"], cp1["76"]["by_interpretation"]["a45"]["contour_p95_px"]))
    m213 = meas(em["off_line"], "213", "sky_transition")
    row("213", "明暗の移行線", "最大 px。記録のみ（Q7 の既定）", "%.2f px" % m213["value_max_px"], vcp1="%.2f px" % cp1["213"]["by_interpretation"]["a45"]["transition_max_px"],
        verdict="record-only", judged=False, note="p95 %.2f px（CP1 %.2f）" % (m213["p95_px"], cp1["213"]["by_interpretation"]["a45"]["transition_p95_px"]))
    row("94", "原画視点のカメラが動かない", "場面のカメラの値の照合", "位置の差 %.6f m" % g["94"]["max_position_delta_vs_cp1_m"], vcp1="510 コマで差 0（番号27）",
        verdict="pass" if g["94"]["max_position_delta_vs_cp1_m"] < 1e-4 else "fail", note="静止画の照合だけ。コマを通した検査は番号27 のまま")
    for n, tgt, nm in (("74", "fuji_ridge", "富士の稜線（74・161）"), ("75", "boat_fg", "手前の船"), ("157", "boat_left", "左奥の船"), ("159", "boat_mid", "右船（座席の船）")):
        m = meas(em["off_noline"], n, tgt)
        row(n if n != "74" else "74・161", nm, "評価器23 の最大 px（報告項目）", "%.2f px（p95 %.2f）" % (m["value_max_px"], m["p95_px"]),
            vcp1="%.2f px（p95 %.2f）" % (cp1[n]["by_interpretation"]["a45"]["max_px"], cp1[n]["by_interpretation"]["a45"]["p95_px"]), verdict="record-only", judged=False)
    m162s, m162l = meas(em["off_noline"], "162", "fuji_snow"), meas(em["off_noline"], "162", "fuji_slope")
    row("162", "富士の雪・斜面の色", "ΔE00（報告項目）", "雪 %.2f・斜面 %.2f" % (m162s["value"], m162l["value"]),
        vcp1="雪 %.2f・斜面 %.2f" % (cp1["162"]["by_interpretation"]["a45"]["fuji_snow_dE00"], cp1["162"]["by_interpretation"]["a45"]["fuji_slope_dE00"]), verdict="record-only", judged=False)
    # 色区（t28_claws が判定、t28_white は記録）。値は評価器の定義のままの読み（28修正01 との差）と、両側の読み（29修正01 が採った読み）
    b29 = load(os.path.join(REPO, "Unity", "Build", "Design", "29R01", "unity", "tstar_sym", "tstar_sym.json"))
    b29rows = {(r["item"], r["measure"]): r for r in b29["rows"]}
    bnd = {}
    for r in rem["t28_claws"]["boundaries_vs_28r01"]:
        bnd.setdefault(r["item"], r)
    srows = {}
    for r in symj["t28_claws"]["rows"]:
        srows.setdefault(r["item"], []).append(r)
    names = {"73": "内側の水色（藍中）の色区の境界", "77": "下側から始まる縞", "79": "縞の並び", "118": "内側の色区の境界", "120": "境界", "133": "左から上へ続く白",
             "134": "白帯の広狭", "263": "内側から下方へ続く水色", "270": "白と水色の境", "175": "爪の色区（もともと不合格）"}
    sv = rem["t28_claws"]["summary_verdicts_ds27"]
    for k in ("73", "77", "79", "118", "120", "133", "134", "263", "270", "175"):
        rs = srows.get(k, [])
        worst = max(rs, key=lambda r: r["kp_sym_max_px"]) if rs else None
        d29 = max((abs(r["kp_sym_max_px"] - b29rows[(r["item"], r["measure"])]["kp_sym_max_px"]) for r in rs if (r["item"], r["measure"]) in b29rows), default=None)
        v29 = b29rows.get((worst["item"], worst["measure"]), {}).get("kp_sym_max_px") if worst else None
        vsym = "pass" if (worst and worst["kp_verdict_sym"] == "pass") else ("fail" if worst else None)
        row(k, names[k], "両側の読み（29修正01 が採った読み）の最大 px、爪あり", worst["kp_sym_max_px"] if worst else None, v39=v29 if d29 == 0 else None, v30=v29, v29=v29,
            vcp1=cp1.get("28_" + k, {}).get("verdict"), verdict=vsym, judged=(k != "175"),
            note="29修正01 との差 %s px。評価器の定義のままの読み %.3f px（28修正01 %.3f、記録）" % (r4(d29, 3), bnd[k]["ds27_max_px"], bnd[k]["r28r01_max_px"]))
    for k in ("265", "266", "267"):
        v = rem["t28_claws"]["colour_265_266_267"][k]
        if k == "265":
            val = "ΔE00 %.3f" % v["ds27"]["dE00"]
        elif k == "266":
            val = "判定 %s" % v["ds27"]["verdict"]
        else:
            val = "評価器の定義 %s／両側の読み 20 px 以上の帯 %s" % (v["ds27_verdict"], {c: symj["t28_claws"]["flat_painting_view_266_267"]["kp"][c]["sym"]["bands_ge_20px"]
                                                                        for c in ("white", "mizuiro", "ai_mid", "ai_dark") if symj["t28_claws"]["flat_painting_view_266_267"]["kp"][c]["sym"]})
        sym_ok = all((symj["t28_claws"]["flat_painting_view_266_267"]["kp"][c]["sym"] or {}).get("bands_ge_20px", 0) == 0 for c in ("white", "mizuiro", "ai_mid", "ai_dark"))
        vd = v["ds27_verdict"] if k != "267" else ("pass" if sym_ok else "fail")
        row(k, {"265": "内側の面の色", "266": "色面の均一（原画視点・座席）", "267": "色面の帯（原画視点）"}[k], "評価器 28修正01／両側の読み", val,
            vcp1=cp1.get("28_" + k, {}).get("verdict"), verdict=vd,
            note="267 は評価器の定義のままでは 29修正01 から不合格（設計36 §2.2 の読み）。両側の読みで帯 0" if k == "267" else "")
    res["item_table"] = table
    res["regression_evaluator"] = {"output": rel(os.path.join(U40, "ds30_tstar_regress.json")), "sha256": sha(os.path.join(U40, "ds30_tstar_regress.json")),
                                   "ds39_output_sha256": sha(reg39), "identical_to_ds39": sha(os.path.join(U40, "ds30_tstar_regress.json")) == sha(reg39),
                                   "sym_worst_diff_vs_29r01_px": {s: reg["sets"][s]["sym"]["worst_diff_vs_29r01_px"] for s in reg["sets"]},
                                   "silhouette_diff_vs_29r01_px": {s: reg["sets"][s]["silhouette_diff_vs_29r01_px"] for s in reg["sets"]},
                                   "lfgate_diff_vs_29r01_px": {s: reg["sets"][s]["lfgate_diff_vs_29r01_px"] for s in reg["sets"]}}
    # 全体の合成の評価器の値（記録。紙の全部入・爪を除いた ID も）
    full = {}
    for k, e in em.items():
        full[k] = {tid: {"max_px": contour(e, tid)["value_max_px"], "p95_px": contour(e, tid)["p95_px"], "verdict_evaluator": contour(e, tid)["verdict"]}
                   for tid in ("78", "130", "131", "132", "72", "71")}
        full[k]["212_dE00"] = meas(e, "212", "sky_top")["value"]
        full[k]["76_max_px"] = meas(e, "76", "sky_dark")["value_max_px"]
        full[k]["76_dE00"] = meas(e, "76", "sky_bottom")["value"]
        full[k]["213_max_px"] = meas(e, "213", "sky_transition")["value_max_px"]
        full[k]["render_sha256"] = e["input"]["render_sha256"]
        full[k]["ids_sha256"] = e["input"]["ids_sha256"]
    res["full_composite_evaluator"] = full
    res["full_composite_note_ja"] = ("全体の合成（near の海・右の高い波・3隻・富士・飛沫入り）を評価器23 に通した値。78〜72 は主役波の外輪郭のほか、"
                                     "near の海や船が空と接する所の点も入るので、判定には t* の主役波の ID（t28_claws）の値を使う（29修正01 からの読み）。")

    # ---------------------------------------------------------------- 4. 受入
    judged = [r for r in table if r["judged"]]
    prev_pass = {"78", "130", "131", "132", "72", "69", "70", "212", "73", "77", "79", "118", "120", "133", "134", "263", "265", "266", "267", "270"}
    regress = [r["item"] for r in judged if r["item"] in prev_pass and r["verdict_ds40"] != "pass"]
    acc = {
        "no_regression_vs_29r01_ds30": {
            "criterion_ja": "計画 §2.0 の項目（78・130・131・132 大きな輪郭・72 σ24 p95・69・70・212、色区は 29修正01 が戻した読み）が、29修正01／設計30 で合格した判定のまま",
            "regressed_items": regress, "silhouette_and_lfgate_diff_vs_29r01_px": res["regression_evaluator"],
            "pass": len(regress) == 0 and all(v == 0.0 for v in res["regression_evaluator"]["sym_worst_diff_vs_29r01_px"].values())},
        "cp1_26r01_regression_stated": {
            "criterion_ja": "CP1／26修正01 に対する後退（段階5確認 §6.3）を隠さずに書く",
            "rows": [{"item": r["item"], "cp1": r["cp1"], "r26r01": r["r26r01"], "ds40": r["ds40"]} for r in table if r["item"] in ("78", "130", "131", "132", "72")],
            "pass": True},
        "record_only_71_76_213": {"items": ["71", "76", "213"], "pass": True},
        "hmd_h4_h5": {"verdict": "保留", "note_ja": "PS VR2 の導入は利用者の手。Mock の両眼（座席 v1、±0.032 m）と PC の描画だけ。"},
    }
    res["acceptance"] = acc

    # ---------------------------------------------------------------- 5. 図
    disp = truth.disp_rgb
    off = a0.astype(np.float32)
    ov = off.copy()
    ov[:, fm.x0:fm.x1 + 1] = 0.5 * off[:, fm.x0:fm.x1 + 1] + 0.5 * disp[:, fm.x0:fm.x1 + 1].astype(np.float32)
    ov[:, :fm.x0] *= 0.35
    ov[:, fm.x1 + 1:] *= 0.35
    ov = label(np.clip(np.round(ov), 0, 255).astype(np.uint8), ["設計40：段階7までの原画視点（白・爪・飛沫・線、紙の 3 層は切＝評価の状態）＋ 原画 50%。Unity の PC オフスクリーン描画、t* = 12.0 s"], xy=(170, 1040), size=22)
    cv2.imwrite(os.path.join(FIG, "fig_ds40_painting_overlay50.png"), ov[:, :, ::-1])
    for k, lines in (("off_noline", ["輪郭の偏差図（線なしの全体の ID。評価器23）：78〜72・71、富士・3隻（報告）。判定の 78〜72 は t* の主役波の ID の値（表）"]),
                     ("off_line", ["空の偏差図（線ありの全体の ID。評価器23）：76 暗い空の範囲・213 移行線（記録のみ、Q7）・212 空の上の色"])):
        o = rgb(os.path.join(EVAL, k, k + "_overlay.png"))
        cv2.imwrite(os.path.join(FIG, "fig_ds40_contour_%s.png" % k), label(o, lines, xy=(170, 8), size=20)[:, :, ::-1])
    # 並べ図：行＝原画視点・座席 v1・側面・背面、列＝CP1・設計30・設計40（切）・設計40（全部入）
    tw, th = 480, 270
    blank = np.full((1080, 1920, 3), 40, np.uint8)

    def tile(p, txt):
        im = rgb(p) if (p and os.path.exists(p)) else label(blank.copy(), ["（この視点の画像はない）"], xy=(700, 500), size=40)
        return label(cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA), [txt], xy=(6, 4), size=16)
    rowsdef = [("原画視点", os.path.join(CP1R, "cp1_a45_painting.png"), os.path.join(S30, "ds30_painting_t12.0s_tau+0.000.png"), p_off, p_all),
               ("座席 v1", os.path.join(CP1R, "cp1_a45_seat.png"), os.path.join(S30, "ds30_seat_t12.0s_tau+0.000.png"),
                os.path.join(U40, "views", "seat_t120_off.png"), os.path.join(U40, "views", "seat_t120_all.png")),
               ("左の側面", os.path.join(CP1R, "cp1_a45_side.png"), os.path.join(S30, "ds30_side_left_t12.0s_tau+0.000.png"),
                os.path.join(U40, "views", "side_left_t120_off.png"), os.path.join(U40, "views", "side_left_t120_all.png")),
               ("背面", os.path.join(CP1R, "cp1_a45_back.png"), None, os.path.join(U40, "views", "back_t120_off.png"), os.path.join(U40, "views", "back_t120_all.png"))]
    colnames = ["CP1（K* 45°、旧い座席）", "設計30（段階5 の終わり）", "設計40 段階7（紙は切）", "設計40 段階7（紙・摺り・小飛沫を入）"]
    grid = []
    for rn, *ps in rowsdef:
        grid.append(np.hstack([tile(p, "%s・%s" % (rn, colnames[i])) for i, p in enumerate(ps)]))
    sheet = np.vstack(grid)
    cv2.imwrite(os.path.join(FIG, "fig_ds40_views_sheet.png"), sheet[:, :, ::-1])
    extra = [("seat_low 唇を見上げる（t 12）", os.path.join(U40, "views", "seat_low_t120_off.png")),
             ("座席から波の方向 t 10.5", os.path.join(U40, "views", "seat_toward_wave_t105_off.png")),
             ("座席から波の方向 t 12", os.path.join(U40, "views", "seat_toward_wave_t120_off.png")),
             ("側面（波だけ）", os.path.join(U40, "views", "side_left_t120_off_waveonly.png")),
             ("背面（波だけ）", os.path.join(U40, "views", "back_t120_off_waveonly.png")),
             ("座席から波の方向 t 10.5（紙などを入）", os.path.join(U40, "views", "seat_toward_wave_t105_all.png")),
             ("Mock 左目（座席 v1、−0.032 m）", os.path.join(U40, "mock", "seat_t120_L.png")),
             ("Mock 右目（座席 v1、+0.032 m）", os.path.join(U40, "mock", "seat_t120_R.png"))]
    tw2, th2 = 480, 270
    t2 = [label(cv2.resize(rgb(p), (tw2, th2), interpolation=cv2.INTER_AREA), [n], xy=(6, 4), size=16) for n, p in extra]
    cv2.imwrite(os.path.join(FIG, "fig_ds40_views_extra.png"), np.vstack([np.hstack(t2[0:4]), np.hstack(t2[4:8])])[:, :, ::-1])
    # Mock の左右差（線の画素の数は設計38 の測りに任せ、ここでは画像の違いの記録だけ）
    L, R = rgb(os.path.join(U40, "mock", "seat_t120_L.png")), rgb(os.path.join(U40, "mock", "seat_t120_R.png"))
    res["mock_seat_t12"] = {"differing_px": int((np.abs(L.astype(int) - R.astype(int)).max(-1) > 8).sum()), "note_ja": "Mock の両眼の画像の違いの画素（チャンネル差 > 8）。視差があるので 0 にはならない。記録のみ。"}

    # ---------------------------------------------------------------- 6. 配置の比較（参照モデルの数値だけ。D24）
    ref = load(REF30)
    lay = load(LAY30)
    run30 = open(RUN30, encoding="utf-8").read()
    sea_sha = {}
    for m in re.finditer(r'"(Unity/Build/Design/30/sea/[^"]+)"\s*:\s*"([0-9a-f]{64})"', run30):
        p = os.path.join(REPO, m.group(1))
        if os.path.exists(p):
            sea_sha[m.group(1)] = {"ds30": m.group(2), "now": sha(p), "same": sha(p) == m.group(2)}
    # 波の枠：設計30 の配置の (a, c) は、主役波のパッケージの sea_model.focus_world を原点にした値（ds30_sea.Hero().focus と同じ）
    p30 = load(os.path.join(REPO, "Tools", "GWWaveGen", "ds30", "ds30_params.json"))
    kp = load(os.path.join(REPO, p30["hero"]["package"], "ds27_keypose.json"))
    focus = np.array(kp["sea_model"]["focus_world"], np.float64)
    focus[1] = 0.0
    hero = lay["hero"]

    def W3(a_, c_, h_):
        p = focus + a_ * tt + c_ * et
        return np.array([p[0], h_, p[2]])
    fd, sd = lay["first_design"], lay["second_design"]
    pts = [("主役波の頂（共通の原点）", W3(hero["top_a"], hero["top_c"], hero["H_m"]), W3(hero["top_a"], hero["top_c"], hero["H_m"])),
           ("手前の小波の頂", W3(fd["small_wave"]["a"], fd["small_wave"]["c"], fd["small_wave"]["h"]), W3(sd["small_wave"]["a"], sd["small_wave"]["c"], sd["small_wave"]["h"])),
           ("大波の下の谷の底", W3(fd["trough"]["a"], fd["trough"]["c"], -fd["trough"]["depth"]), W3(sd["trough_in_sheet"]["a"], sd["trough_in_sheet"]["c"], -sd["trough_in_sheet"]["depth"])),
           ("右側の最も高い所／右の高い波の頂", W3(fd["right_side"]["a"], fd["right_side"]["c"], fd["right_side"]["h"]), W3(sd["right_wave_peak"]["a"], sd["right_wave_peak"]["c"], sd["right_wave_peak"]["h"]))]
    P1 = np.stack([p[1] for p in pts]); P2 = np.stack([p[2] for p in pts])
    q1, w1 = unity_project(cams["painting"], P1)
    q2, w2 = unity_project(cams["painting"], P2)
    lay_rows = []
    for i, (nm, x1, x2) in enumerate(pts):
        lay_rows.append({"name_ja": nm, "reference_first_design_world": [r4(v, 3) for v in x1], "current_world": [r4(v, 3) for v in x2],
                         "delta_m": r4(float(np.linalg.norm(x2 - x1)), 3),
                         "painting_px_reference": [r4(v, 1) for v in q1[i]] if w1[i] > 0 else None, "painting_px_current": [r4(v, 1) for v in q2[i]] if w2[i] > 0 else None,
                         "painting_px_delta": r4(float(np.linalg.norm(q2[i] - q1[i])), 1) if (w1[i] > 0 and w2[i] > 0) else None})
    boats = {o["name"].replace("find:AF27 船 ", ""): o for o in rep["objects"] if o["name"].startswith("find:AF27 船")}
    bpx = {}
    for k, o in boats.items():
        c3 = np.array([o["boundsCenter"][t] for t in "xyz"])
        q, w_ = unity_project(cams["painting"], c3[None])
        bpx[k] = {"bounds_center_world": [r4(v, 3) for v in c3], "painting_px": [r4(v, 1) for v in q[0]] if w_[0] > 0 else None}
    res["layout_vs_reference"] = {
        "d24_ja": "D24（既定値・利用者未回答）：参照モデル（Q5）の配置は記録のみの比較図。数値と印だけで、参照モデルの形・画像は描かない。",
        "reference_numbers": {"file": rel(REF30), "sha256": sha(REF30), "source": ref["source"], "source_sha256": ref["source_sha256"], "credit_ja": ref["credit_ja"],
                              "obj_opened_in_ds40": False, "note_ja": "設計30 の ds30_refmeasure.py が測った数値（Δa・Δc・h/H）だけを読む。この番号では OBJ を開かず、一時キャッシュも作らない。"},
        "first_design_from_ds30": rel(LAY30), "first_design_sha256": sha(LAY30),
        "frame_focus_world": [r4(v, 3) for v in focus], "scale_hero_over_ref": hero["scale_hero_over_ref"],
        "rows": lay_rows, "boats_now": bpx,
        "sea_package_unchanged_since_ds30": sea_sha, "differences_ds30": [d["id"] + " " + d["item"] for d in lay["differences"]],
        "not_compared_ja": "参照モデルの船は殻に溶け込んだ浮彫で、位置を数値にしていない（設計30 D30-8）。富士・空は参照モデルにない。"}
    # 図：原画視点の上に 2 つの印（白 × ＝参照モデルの数値から置いた一次設計、赤 ◇ ＝今の配置）。右に平面図（設計30 の図を写す）
    img = (a0.astype(np.float32) * 0.55 + 255 * 0.45).astype(np.uint8)
    img = np.ascontiguousarray(img[:, :, ::-1])
    for i, rr in enumerate(lay_rows):
        if rr["painting_px_reference"] and rr["painting_px_current"]:
            p1 = tuple(int(round(v)) for v in rr["painting_px_reference"]); p2 = tuple(int(round(v)) for v in rr["painting_px_current"])
            cv2.line(img, p1, p2, (80, 80, 80), 2)
            cv2.drawMarker(img, p1, (255, 255, 255), cv2.MARKER_TILTED_CROSS, 26, 4)
            cv2.drawMarker(img, p1, (0, 0, 0), cv2.MARKER_TILTED_CROSS, 22, 2)
            cv2.drawMarker(img, p2, (0, 0, 255), cv2.MARKER_DIAMOND, 26, 3)
    for k, b in bpx.items():
        if b["painting_px"]:
            cv2.circle(img, tuple(int(round(v)) for v in b["painting_px"]), 10, (0, 160, 255), 3)
    img = img[:, :, ::-1]
    txt = ["配置の比較（記録のみ、D24）：黒白の × ＝参照モデルの配置の数値を主役波の頂を原点に H 比 %.3f で置いた一次設計、赤の ◇ ＝今の配置（設計30 の二次設計、段階7 まで不変）、橙の ○ ＝船の中心" % hero["scale_hero_over_ref"],
           "参照モデルの形は描いていない（数値の印だけ）。背景は設計40 の原画視点（t*、紙は切）を淡くしたもの"]
    def onscr(q):
        return q is not None and 0 <= q[0] < W and 0 <= q[1] < H
    for i, rr in enumerate(lay_rows):
        rr["on_screen_reference"], rr["on_screen_current"] = onscr(rr["painting_px_reference"]), onscr(rr["painting_px_current"])
        off = [n for n, f in (("× は画面外", rr["on_screen_reference"]), ("◇ は画面外", rr["on_screen_current"])) if not f]
        txt.append("%s：差 %s m、画面で %s px%s" % (rr["name_ja"], rr["delta_m"], rr["painting_px_delta"], "（" + "・".join(off) + "）" if off else ""))
    txt.append("右側：参照モデルは大波の右の部分（0.71 H）で、別の波はない。今の右の高い波（D30-6）とは別の物なので、この行の差は配置のずれではない")
    img = label(img, txt, xy=(20, 12), size=20, fill=(20, 20, 20), shadow=None)
    plan = os.path.join(REPO, "Docs", "Evidence", "Design", "30", "fig_ds30_layout_plan.png")
    pim = rgb(plan)
    ph = int(round(pim.shape[0] * (1080 / pim.shape[0])))
    pim = cv2.resize(pim, (int(round(pim.shape[1] * 1080 / pim.shape[0])), 1080), interpolation=cv2.INTER_AREA)
    pim = label(pim, ["平面図（設計30 の図をそのまま。白 × 一次設計、赤 ◇ 二次設計）"], xy=(10, 1040), size=20)
    cv2.imwrite(os.path.join(FIG, "fig_ds40_layout_reference.png"), np.hstack([img, pim])[:, :, ::-1])
    res["layout_vs_reference"]["plan_figure_source"] = {"path": rel(plan), "sha256": sha(plan)}

    # ---------------------------------------------------------------- 7. 表の図
    V = {"pass": "合格", "fail": "不合格", "record-only": "記録のみ", None: "—"}
    th_ = 34
    hdr = ["項目", "名前", "CP1", "26修正01", "29修正01", "設計30", "設計40", "判定"]
    xs_ = [10, 110, 520, 800, 950, 1100, 1250, 1740]
    n = len(table)
    tb = np.full((th_ * (n + 3), 1920, 3), 250, np.uint8)
    im = Image.fromarray(tb); dr = ImageDraw.Draw(im); fb_ = font(20, True); fr_ = font(18)
    dr.text((10, 6), "設計40：段階7 までの原画視点の評価器の全項目（t*、Unity の PC 描画）。判定の 78〜72 は t* の主役波の ID（爪あり）の読み、色区は両側の読み（29修正01）", font=fb_, fill=(0, 0, 0))
    for j, hname in enumerate(hdr):
        dr.text((xs_[j], th_ + 6), hname, font=fb_, fill=(0, 0, 0))

    def fmt(v):
        if v is None:
            return "—"
        if isinstance(v, float):
            return "%.4g" % v
        return str(v)
    for i, r in enumerate(table):
        y = th_ * (i + 2) + 4
        col = {"pass": (46, 125, 50), "fail": (198, 40, 40), "record-only": (110, 110, 110)}.get(r["verdict_ds40"], (0, 0, 0))
        if i % 2 == 0:
            dr.rectangle([0, y - 3, 1920, y + th_ - 4], fill=(238, 238, 238))
        vals = [r["item"], r["name_ja"], fmt(r["cp1"]), fmt(r["r26r01"]), fmt(r["r29r01"]), fmt(r["ds30"]), fmt(r["ds40"]), V.get(r["verdict_ds40"], r["verdict_ds40"])]
        for j, v in enumerate(vals):
            s = str(v)
            lim = [8, 22, 16, 10, 10, 10, 30, 8][j]
            dr.text((xs_[j], y), s if len(s) <= lim else s[:lim - 1] + "…", font=fr_, fill=col if j == 7 else (0, 0, 0))
    tb = np.array(im)
    cv2.imwrite(os.path.join(FIG, "fig_ds40_item_table.png"), tb[:, :, ::-1])

    res["figures"] = sorted(rel(os.path.join(FIG, f)) for f in os.listdir(FIG))
    save(os.path.join(OUT, "ds40_compare_metrics.json"), res)
    save(os.path.join(OUT, "ds40_acceptance.json"), {"schema": "GreatWave.DS40.acceptance/1", "generated_utc": now(), "acceptance": acc,
                                                     "item_table_short": [{k: r[k] for k in ("item", "ds40", "verdict_ds40", "judged")} for r in table]})
    print(json.dumps({"acceptance": {k: v.get("pass", v.get("verdict")) for k, v in acc.items()}, "regressed": regress}, ensure_ascii=False))


if __name__ == "__main__":
    main()
