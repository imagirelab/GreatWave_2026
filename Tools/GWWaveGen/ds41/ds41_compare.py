# -*- coding: utf-8 -*-
"""設計41 第「モデル」部：押送船のモデルへ置き換えた後の原画視点・座席・船の近くを測り、記録する。

入力（どれも Git 対象外）:
    Unity/Build/Design/41/model/blender/  ds41_boat_blender.py の出力（報告・部品の頂点・画像）
    Unity/Build/Design/41/model/unity/    DS41Boats.ImportCheck・BuildScene・Render の出力、ds30b_tstar_regress.py の出力
    Unity/Build/Design/40/compare/        設計40 の出力（比べの基準：評価器23 の値、回帰の評価器の値、t* の画像）
    Unity/Build/Design/41/research/       調べの部の表（寸法の出典）
入力（Git 対象）:
    Docs/Evidence/ArtFirst/CP1/metrics.json（CP1 の値）、Tools/GWContext/seat_v1.json（座席 v1。変えない）
処理:
    1) 設計07 の検査（Unity の取り込みで尺度・軸・左右の反転なし）の結果をまとめる。
    2) 評価器23（ID モード）を、紙の 3 層を切った原画視点の色画像と全体の ID 画像（線なし・線あり）で回す。74・75・157・159 と空の項目。
    3) 回帰：t* の主役波の画像（t28 の組）が設計40 と画素まで同じか、回帰の評価器の値が設計40 と同じか。68・69・70・212・94。
    4) 座席 v1 の目と船縁・床の関係（座席の定義は変えない）。
    5) 図と metrics.json・run.json。
出力：Unity/Build/Design/41/model/{eval/,fig/,ds41_model_metrics.json,ds41_model_run.json}

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds41/ds41_compare.py [--skip-eval]
"""
import argparse
import datetime
import hashlib
import json
import math
import os
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
import gw_wavegen as G0  # noqa: E402

OUT = os.path.join(REPO, "Unity", "Build", "Design", "41", "model")
U41 = os.path.join(OUT, "unity")
B41 = os.path.join(OUT, "blender")
U40 = os.path.join(REPO, "Unity", "Build", "Design", "40", "compare", "unity")
E40 = os.path.join(REPO, "Unity", "Build", "Design", "40", "compare", "eval")
RES = os.path.join(REPO, "Unity", "Build", "Design", "41", "research")
KSTAR = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final")
CP1M = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "CP1", "metrics.json")
SEAT = os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")
PAINT = os.path.join(REPO, "Tools", "PaintingTruth", "build", "painting_display.png")
MASKS = os.path.join(REPO, "Tools", "PaintingTruth", "targets", "masks")
FIG = os.path.join(OUT, "fig")
EVAL = os.path.join(OUT, "eval")
FONT_R = r"C:\Windows\Fonts\YuGothM.ttc"
W, H = 1920, 1080
IDMAP = {"classes": {"sky": [0, 255, 255], "boat_left": [34, 0, 0], "boat_mid": [0, 34, 0], "boat_fg": [34, 34, 0]},
         "note_ja": "設計41 の全体の ID 画像（設計40 と同じ作り方、3840×2160、線形、MSAA なし）。船は AF24 ID Flat に 0.4 を渡し線形の描画先で 34。"}
PAINTING_CAM_CP1 = [0.0, 3.0, -62.0]
BOATS = {"boat_fg": ("75", "手前の船"), "boat_left": ("157", "左奥の船"), "boat_mid": ("159", "右の船（座席の船）")}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def r4(v, n=4):
    if v is None:
        return None
    v = float(v)
    return None if (math.isnan(v) or math.isinf(v)) else round(v, n)


def rgb(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1].copy()


def font(size):
    try:
        return ImageFont.truetype(FONT_R, size)
    except OSError:
        return ImageFont.load_default()


def label(im, lines, xy=(10, 8), size=22):
    im = im.copy()
    dr = ImageDraw.Draw(im)
    f = font(size)
    for i, s in enumerate(lines):
        x, y = xy[0], xy[1] + i * (size + 8)
        dr.text((x + 1, y + 1), s, font=f, fill=(0, 0, 0))
        dr.text((x, y), s, font=f, fill=(255, 255, 255))
    return im


def meas(em, item, target=None):
    it = em["items"].get(item)
    if it is None:
        return None
    for m in it["measures"]:
        if target is None or m.get("target") == target:
            return m
    return None


def run_eval(render, ids, name, skip):
    od = os.path.join(EVAL, name)
    os.makedirs(od, exist_ok=True)
    idmap = os.path.join(EVAL, "idmap.json")
    cmd_s = "py -3.10 -B Tools/PaintingTruth/evaluate.py --render %s --ids %s --idmap %s --out-dir %s --name %s" % (rel(render), rel(ids), rel(idmap), rel(od), name)
    if not (skip and os.path.exists(os.path.join(od, "metrics.json"))):
        subprocess.run([sys.executable, "-B", os.path.join(REPO, "Tools", "PaintingTruth", "evaluate.py"), "--render", render, "--ids", ids, "--idmap", idmap,
                        "--out-dir", od, "--name", name], check=True, cwd=REPO, stdout=subprocess.DEVNULL)
    return load(os.path.join(od, "metrics.json")), cmd_s


def unity_project(cam, P):
    V = np.array(cam["worldToCamera"], np.float64).reshape(4, 4)
    Pm = np.array(cam["projection"], np.float64).reshape(4, 4)
    X = np.c_[np.asarray(P, np.float64), np.ones(len(P))]
    c = (Pm @ (V @ X.T)).T
    nd = c[:, :2] / c[:, 3:4]
    return np.stack([(nd[:, 0] * 0.5 + 0.5) * W, (1 - (nd[:, 1] * 0.5 + 0.5)) * H], 1), c[:, 3]


def b2u(p):
    """Blender の局所 (x, y, z) → Unity の船の根の局所 (−x, z, −y)（設計07 の実測の対応）。"""
    p = np.asarray(p, np.float64)
    return np.stack([-p[..., 0], p[..., 2], -p[..., 1]], -1)


def u2b(p):
    p = np.asarray(p, np.float64)
    return np.stack([-p[..., 0], -p[..., 2], p[..., 1]], -1)


def ray_down(geom, names, org):
    """Blender の局所で、org から −Z へ下ろした射線が最初に当たる点の z（Möller–Trumbore）。"""
    best = None
    d = np.array([0, 0, -1.0])
    for n in names:
        V, Tr = geom[n + "__v"].astype(np.float64), geom[n + "__t"]
        a, b, c = V[Tr[:, 0]], V[Tr[:, 1]], V[Tr[:, 2]]
        e1, e2 = b - a, c - a
        pv = np.cross(d, e2)
        det = (e1 * pv).sum(1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        tv = org - a
        u = (tv * pv).sum(1) * inv
        qv = np.cross(tv, e1)
        v = (qv @ d) * inv
        t = (e2 * qv).sum(1) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
        if hit.any():
            tt = float(t[hit].min())
            if best is None or tt < best[0]:
                best = (tt, n)
    return None if best is None else (org[2] - best[0], best[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-eval", action="store_true")
    a = ap.parse_args()
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(EVAL, exist_ok=True)
    save(os.path.join(EVAL, "idmap.json"), IDMAP)
    brep = load(os.path.join(B41, "ds41_blender_report.json"))
    chk = load(os.path.join(U41, "ds41_import_check.json"))
    bld = load(os.path.join(U41, "ds41_build_report.json"))
    rep = load(os.path.join(U41, "ds41_render_report.json"))
    rep40 = load(os.path.join(U40, "ds40_render_report.json"))
    cams = {c["view"]: c for c in rep["cameras"]}
    geom = dict(np.load(os.path.join(B41, "ds41_boat_geom.npz")))
    res = {"schema": "GreatWave.DS41.model_metrics/1", "number": "設計41 第「モデル」部", "generated_utc": now(),
           "evidence_kind_ja": "Blender 5.2.2 ヘッドレスの制作と往復の検査、Unity 6000.4.3f1 Editor の batchmode の取り込みの検査と PC オフスクリーン描画（camera.Render、RTX 3080、Direct3D11）、その画像の numpy・OpenCV の測定。HMD 実機の結果ではない。"}

    # ---------------------------------------------------------------- 1. 設計07 の検査
    ok07 = bool(chk["pass"]) and chk["fbxSha256"] == brep["files"]["ds41_oshiokuri.fbx"]["sha256"]
    res["design07_check"] = {
        "criterion_ja": "Unity の実際の取り込みで尺度・軸・左右の反転なし（設計07 の検査）。FBX を原点に置き、部品ごとのワールドの頂点の範囲を Blender の値の (x, y, z) → (−x, z, −y) と比べる",
        "fbx_same_as_blender_output": chk["fbxSha256"] == brep["files"]["ds41_oshiokuri.fbx"]["sha256"],
        "importer": chk["importerJa"], "bounds_max_abs_diff_units": chk["boundsMaxAbsDiff"],
        "tip_to_tip_units": chk["tipToTip"], "beam_units": chk["beam"], "bow_tip_measured": chk["bowTipMeasured"], "stern_tip_measured": chk["sternTipMeasured"],
        "forward": chk["forward"], "up": chk["up"], "right": chk["right"], "triple_product": chk["triple"],
        "starboard_oars_plusX": chk["starboardOarsPlusX"], "port_oars_minusX": chk["portOarsMinusX"],
        "hull_outward_fraction": chk["hullOutwardFraction"], "scale": chk["scalePass"], "axis": chk["axisPass"], "mirror": chk["mirrorPass"],
        "normals": chk["normalsPass"], "blender_roundtrip": brep["roundtrip"], "verdict": "pass" if ok07 else "fail"}

    # ---------------------------------------------------------------- 2. 評価器23
    p_off = os.path.join(U41, "full", "painting_t120_off.png")
    em, cmds = {}, []
    for k, idn in (("off_noline", "ids_noline"), ("off_line", "ids_line")):
        em[k], c = run_eval(p_off, os.path.join(U41, "full", idn + ".png"), k, a.skip_eval)
        cmds.append(c)
        print("eval", k, flush=True)
    em40 = {k: load(os.path.join(E40, k, "metrics.json")) for k in ("off_noline", "off_line")}
    cp1 = load(CP1M)["items"]
    boats = {}
    for key, (item, nm) in BOATS.items():
        m, m40 = meas(em["off_noline"], item, key), meas(em40["off_noline"], item, key)
        c1 = cp1[item]["by_interpretation"]["a45"]
        boats[item] = {"name_ja": nm, "target": key, "ds41_max_px": r4(m["value_max_px"]), "ds41_p95_px": r4(m["p95_px"]), "ds41_p50_px": r4(m["p50_px"]),
                       "ds41_truth_to_render_max": r4(m["max_truth_to_render"]), "ds41_render_to_truth_max": r4(m["max_render_to_truth"]),
                       "ds41_worst_display_xy": m.get("worst_display_xy"),
                       "ds40_max_px": r4(m40["value_max_px"]), "ds40_p95_px": r4(m40["p95_px"]),
                       "cp1_max_px": r4(c1["max_px"]), "cp1_p95_px": r4(c1["p95_px"]),
                       "change_vs_cp1_max_px": r4(m["value_max_px"] - c1["max_px"]), "change_vs_cp1_p95_px": r4(m["p95_px"] - c1["p95_px"]),
                       "change_vs_ds40_max_px": r4(m["value_max_px"] - m40["value_max_px"]), "change_vs_ds40_p95_px": r4(m["p95_px"] - m40["p95_px"]),
                       "verdict": "record-only（判定は仕上げ40・41）"}
    m74, m74b = meas(em["off_noline"], "74", "fuji_ridge"), meas(em40["off_noline"], "74", "fuji_ridge")
    boats["74"] = {"name_ja": "富士の稜線（74・161）", "ds41_max_px": r4(m74["value_max_px"]), "ds41_p95_px": r4(m74["p95_px"]),
                   "ds40_max_px": r4(m74b["value_max_px"]), "cp1_max_px": r4(cp1["74"]["by_interpretation"]["a45"]["max_px"]),
                   "cp1_p95_px": r4(cp1["74"]["by_interpretation"]["a45"]["p95_px"]),
                   "change_vs_cp1_max_px": r4(m74["value_max_px"] - cp1["74"]["by_interpretation"]["a45"]["max_px"]), "verdict": "record-only（判定は仕上げ40）"}
    # 船の ID と原画の船の塗りのマスクの IoU（記録。評価器23 の項目ではない）
    ids = rgb(os.path.join(U41, "full", "ids_noline.png"))
    ids40 = rgb(os.path.join(U40, "full", "ids_noline.png"))
    iou = {}
    for key in BOATS:
        tm = np.array(Image.open(os.path.join(MASKS, key + "_cov.png"))).astype(np.float64) / 65535.0 > 0.5
        out = {}
        for tag, im in (("ds41", ids), ("ds40", ids40)):
            mk = np.all(im == np.array(IDMAP["classes"][key], np.uint8), -1).reshape(H, 2, W, 2).mean((1, 3)) > 0.5
            out[tag] = r4((tm & mk).sum() / max(1, (tm | mk).sum()))
            out[tag + "_render_px"] = int(mk.sum())
        out["truth_px"] = int(tm.sum())
        iou[key] = out
    res["painting_view_boats"] = boats
    res["boat_mask_iou_record"] = {"values": iou, "note_ja": "原画の船の塗りのマスク（targets/masks/*_cov.png、0.5 で二値）と、全体の ID 画像の船の色の画素（1920×1080 に 2×2 平均して 0.5）の IoU。記録のみ。"}
    res["evaluator_commands"] = cmds
    res["evaluator_gate"] = {k: {"provisional": v["provisional"], "truth_manifest_sha256": v["truth"]["manifest_sha256"]} for k, v in em.items()}

    # ---------------------------------------------------------------- 3. 回帰
    same = {}
    for s in ("t28_claws", "t28_white"):
        d41, d40 = os.path.join(U41, s, "t28", "render"), os.path.join(U40, s, "t28", "render")
        for f in sorted(os.listdir(d41)):
            same[s + "/" + f] = sha(os.path.join(d41, f)) == sha(os.path.join(d40, f))
    wave_imgs = {k: v for k, v in same.items() if not (k.endswith("af28r01_painting.png") or k.endswith("af28r01_seat.png") or k.endswith("af28r01_seat_low.png"))}
    reg = load(os.path.join(U41, "ds30_tstar_regress.json"))
    reg40 = load(os.path.join(U40, "ds30_tstar_regress.json"))

    def numbers(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("utc", "generated_utc", "out", "run", "path", "command", "cwd"):
                    continue
                yield from numbers(v, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from numbers(v, path + "[%d]" % i)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            yield path, float(o)
    n41, n40 = dict(numbers(reg["sets"])), dict(numbers(reg40["sets"]))
    diffs = {k: (n41[k], n40.get(k)) for k in n41 if n40.get(k) is None or abs(n41[k] - n40[k]) > 1e-9}
    cl = reg["sets"]["t28_claws"]
    sil = {k: cl["verdict"]["silhouettes_vs_kstar_prime"]["rows"][k]["unity_max_px"] for k in ("78", "130", "131")}
    lf = {"132_sigma12_max": cl["lfgate"]["132_sigma12_max"], "72_sigma24_p95": cl["lfgate"]["72_sigma24_p95"],
          "72_sigma24_p95_noclaws": reg["sets"]["t28_white"]["lfgate"]["72_sigma24_p95"]}
    sym = {s: reg["sets"][s]["sym"]["worst_diff_vs_29r01_px"] for s in reg["sets"]}
    # 68・69・70（CP1・設計40 と同じ式）
    meta = load(os.path.join(KSTAR, "kstarR4_a45_meta.json"))
    rows = np.load(os.path.join(KSTAR, "kstarR4_a45_rows.npz"))
    fr = meta["frame"]
    tt, O0 = np.array(fr["t_travel"]), np.array(fr["section_origin_world"])
    vm = int(meta["rows"]["main_row"])
    Aa, Yy = rows["A"][vm], rows["Y"][vm]
    ix = meta["profile"]["index"]
    jt, jk, jf = ix["j_top"], ix["j_corner"], ix["j_facebot"]
    world = lambda aa, yy: O0 + aa * tt + np.array([0, 1.0, 0]) * yy  # noqa: E731
    jtip = jt + int(np.argmax(Aa[jt:jk + 1]))
    tip, fb, crest, sea_below = world(Aa[jtip], Yy[jtip]), world(Aa[jf], Yy[jf]), world(Aa[jt], Yy[jt]), world(Aa[jt], 0.0)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    cam = G0.PaintingCam(spec)
    p_crest, p_sea = cam.project(crest[None])[0], cam.project(sea_below[None])[0]
    seat = load(SEAT)
    eye = np.array(seat["seat"]["eye_world"], np.float64)
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
    m212, m212b = meas(em["off_line"], "212", "sky_top"), meas(em40["off_line"], "212", "sky_top")
    pc = next(c for c in rep["cameras"] if c["view"] == "painting")
    dpos = float(np.abs(np.array([pc["position"][k] for k in "xyz"]) - np.array(PAINTING_CAM_CP1)).max())
    geo = {"68": {"horizontal_distance_seat_to_lip_tip_m": r4(d_tip, 3), "horizontal_distance_seat_to_face_bottom_m": r4(d_fb, 3),
                  "verdict": "pass" if d_tip < d_fb else "fail", "note_ja": "座席 v1 と K*′ は変えていないので設計40 と同じ値になるはず"},
           "69": {"right_boat_bbox_display_px": [r4(v, 1) for v in bbox], "inside_scored_columns": inside, "scored_columns": [fm.x0, fm.x1],
                  "wave_crest_display_y": r4(p_crest[1], 2), "wave_base_display_y": r4(p_sea[1], 2),
                  "verdict": "pass" if (inside and 0 < p_crest[1] and p_sea[1] < fm.H) else "fail"},
           "70": {"wave_vertical_extent_display_px": r4(wave_vert, 2), "right_boat_length_display_px": r4(blen, 2),
                  "verdict": "pass" if wave_vert > blen else "fail"},
           "212": {"ds41_dE00": r4(m212["value"]), "ds40_dE00": r4(m212b["value"]), "verdict": m212["verdict"]},
           "94": {"painting_camera_position": pc["position"], "max_position_delta_vs_cp1_m": r4(dpos, 6), "verdict": "pass" if dpos < 1e-4 else "fail"}}
    # 71・76・213（記録）
    m71, m71b = meas(em["off_noline"], "71"), meas(em40["off_noline"], "71")
    m76, m76b = meas(em["off_line"], "76", "sky_dark"), meas(em40["off_line"], "76", "sky_dark")
    m213, m213b = meas(em["off_line"], "213", "sky_transition"), meas(em40["off_line"], "213", "sky_transition")
    rec_only = {"71": {"ds41_max_px": r4(m71["value_max_px"]), "ds40_max_px": r4(m71b["value_max_px"])},
                "76": {"ds41_max_px": r4(m76["value_max_px"]), "ds40_max_px": r4(m76b["value_max_px"])},
                "213": {"ds41_max_px": r4(m213["value_max_px"]), "ds40_max_px": r4(m213b["value_max_px"])},
                "note_ja": "71・76・213 は Q7 の既定で記録のみ（仕上げ30 の後に仕上げ40 で判定）。76 の下の境は船も作る"}
    prev_pass = {"78", "130", "131", "132", "72", "69", "70", "212"}
    regressed = []
    if not all(wave_imgs.values()) or diffs:
        regressed.append("t* の主役波の画像または回帰の評価器の値が設計40 と違う")
    for k in ("69", "70", "212", "68", "94"):
        if geo[k]["verdict"] != "pass":
            regressed.append(k)
    res["regression"] = {
        "criterion_ja": "計画 §2.0：原画視点に触れる番号で、合格していた項目（78・130・131・132 大きな輪郭・72 σ24 p95・69・70・212、色区は 29修正01 が戻した読み）を後退させない。比べの基準は直前の番号（設計40）",
        "t_star_wave_images_identical_to_ds40": wave_imgs, "context_images_changed_ja": "af28r01_painting.png・af28r01_seat.png・af28r01_seat_low.png は船を含む合成なので変わってよい",
        "context_images_same": {k: v for k, v in same.items() if k not in wave_imgs},
        "regress_evaluator_numbers_compared": len(n41), "regress_evaluator_numbers_differing_from_ds40": {k: v for k, v in list(diffs.items())[:20]},
        "silhouettes_78_130_131_max_px": sil, "lfgate": lf, "sym_worst_diff_vs_29r01_px": sym, "geometry_items": geo, "record_only": rec_only,
        "items_previously_pass": sorted(prev_pass), "regressed_items": regressed, "pass": len(regressed) == 0}

    # ---------------------------------------------------------------- 4. 座席 v1 の目と船縁・床
    bm = next(b for b in rep["boats"] if b["key"] == "boat_mid")
    M = np.array(bm["localToWorld"], np.float64).reshape(4, 4)
    Minv = np.linalg.inv(M)
    s_mid = float(bm["lossyScale"]["x"])
    eye_l = (Minv @ np.r_[eye, 1.0])[:3]
    eye_b = u2b(eye_l)
    vis = [n[:-3] for n in geom if n.endswith("__v") and not (n.startswith("Boat41_Col") or n.startswith("Boat41_Buoyancy"))]
    probe_b = u2b(np.array(seat["seat"]["probe_local"], np.float64))
    hit = ray_down(geom, vis, probe_b)
    deck_b = np.array([probe_b[0], probe_b[1], hit[0]])
    deck_w = (M @ np.r_[b2u(deck_b), 1.0])[:3]
    old_deck_w = np.array(seat["seat"]["deck_hit_world"], np.float64)
    st = brep["stations"]
    ysh = np.array([s["sheer"][1] for s in st])
    zsh = np.array([s["sheer"][2] for s in st])
    xsh = np.array([s["sheer"][0] for s in st])
    ye = float(eye_b[1])
    w_e, z_e = float(np.interp(ye, ysh, xsh)), float(np.interp(ye, ysh, zsh)) + brep["params"]["values"]["gunwale"]["top_above_sheer"]
    rails = {}
    for side, sx in (("starboard（Blender −X、Unity +X）", -1), ("port（Blender +X、Unity −X）", 1)):
        pb = np.array([sx * w_e, ye, z_e])
        pw = (M @ np.r_[b2u(pb), 1.0])[:3]
        rails[side] = {"world": [r4(v) for v in pw], "eye_above_rail_world_vertical_m": r4(eye[1] - pw[1], 3),
                       "horizontal_distance_eye_to_rail_m": r4(float(np.hypot(*(pw - eye)[[0, 2]])), 3)}
    # blockout（M1）の船縁と甲板（比べ。M1 の STATIONS から）
    ST = [(-5.0, .04, .74, 1.74), (-4.6, .23, .40, 1.43), (-3.8, .48, .16, 1.19), (-2.8, .69, .04, 1.04), (-1.5, .85, .00, .98), (0.0, .90, .00, .96),
          (1.5, .86, .00, .98), (2.8, .71, .04, 1.05), (3.8, .50, .18, 1.22), (4.6, .25, .39, 1.43), (5.0, .10, .64, 1.65)]
    yb_ = np.array([s[0] for s in ST])
    old_top = float(np.interp(ye, yb_, [s[3] for s in ST])) + 0.035
    old_w = float(np.interp(ye, yb_, [s[1] for s in ST]))
    old_rails = {}
    for side, sx in (("starboard", -1), ("port", 1)):
        pw = (M @ np.r_[b2u(np.array([sx * old_w, ye, old_top])), 1.0])[:3]
        old_rails[side] = r4(eye[1] - pw[1], 3)
    seatrec = {
        "seat_v1_unchanged": True, "seat_eye_world": eye.tolist(), "seat_rule_ja": seat["seat"]["rule_ja"],
        "boat_mid_scale": r4(s_mid, 6), "eye_in_boat_local_blender_units": [r4(v) for v in eye_b],
        "new_deck_hit": {"object": hit[1], "local_z_units": r4(hit[0]), "world": [r4(v) for v in deck_w],
                         "eye_above_new_deck_world_m": r4(eye[1] - deck_w[1], 3),
                         "old_deck_hit_world": old_deck_w.tolist(), "deck_shift_world_m": r4(float(np.linalg.norm(deck_w - old_deck_w)), 4),
                         "note_ja": "座席 v1 の規則（船の根の局所 (0, 10, 3) から船の局所の下向きに最初に当たる面）を新しい船で測り直した点。座席の目は seat_v1.json のまま変えない（計画 R11）"},
        "gunwale_top_at_seat_station": {"local_z_units": r4(z_e), "half_width_units": r4(w_e), "rails": rails,
                                        "eye_above_rail_local_m": r4((eye_b[2] - z_e) * s_mid, 3),
                                        "rail_above_new_deck_local_m": r4((z_e - hit[0]) * s_mid, 3)},
        "blockout_for_comparison": {"gunwale_top_local_units": r4(old_top), "half_width_units": r4(old_w), "eye_above_rail_world_vertical_m": old_rails,
                                    "eye_above_rail_local_m": r4((eye_b[2] - old_top) * s_mid, 3)},
        "note_ja": "船は t* で縦 33°・軸まわり 25° 傾いているので、世界の鉛直で測った目と船縁の高さの差は左右で違う。局所の値は船の床に対する座った目の高さの読み。"}
    res["seat_v1_vs_gunwale"] = seatrec

    # ---------------------------------------------------------------- 5. 実寸（船ごとの縮尺）と資料
    P = brep["params"]["values"]
    ru = brep["derived_units"]
    real = {}
    for b in rep["boats"]:
        s = float(b["lossyScale"]["x"])
        real[b["key"]] = {"scale": r4(s, 6), "tip_to_tip_m": r4(10 * s, 3), "beam_m": r4(2 * ru["half_beam_max"] * s, 3), "depth_mid_m": r4(ru["depth_mid"] * s, 3),
                          "vs_source_length_11_667_m_percent": r4((10 * s / 11.667 - 1) * 100, 2),
                          "root_position": b["position"], "root_rotation": b["rotation"]}
    root_same = {}
    for b in rep["boats"]:
        o = next((x for x in rep40["objects"] if x["name"] == "find:AF27 船 " + b["key"]), None)
        root_same[b["key"]] = None if o is None else r4(float(np.abs(np.array([b["position"][k] for k in "xyz"]) - np.array([o["position"][k] for k in "xyz"])).max()), 7)
    # 原画視点の両端の投影：新しい船の先端の頂点と、blockout の先端（af27_place.py の TIP_PLUS_Z・TIP_MINUS_Z）を同じ根で投影して比べる
    allv = np.concatenate([geom[n + "__v"] for n in vis]).astype(np.float64)
    tips_px = {}
    for b in rep["boats"]:
        Mb = np.array(b["localToWorld"], np.float64).reshape(4, 4)
        row = {}
        for nm, tb, blk in (("bow", P["frame"]["bow_tip_blender"], [0.012, 1.775, 5.0]), ("stern", P["frame"]["stern_tip_blender"], [0.012, 1.685, -5.0])):
            v = allv[np.argmin(np.linalg.norm(allv - np.array(tb), axis=1))]
            pn, _ = unity_project(pc, [(Mb @ np.r_[b2u(v), 1.0])[:3]])
            po, _ = unity_project(pc, [(Mb @ np.r_[np.array(blk), 1.0])[:3]])
            row[nm] = {"ds41_px": [r4(x, 3) for x in pn[0]], "blockout_px": [r4(x, 3) for x in po[0]], "diff_px": r4(float(np.linalg.norm(pn[0] - po[0])), 4)}
        tips_px[b["key"]] = row
    res["painting_view_tip_projection"] = {"values": tips_px, "note_ja": "blockout の先端の点は x = 0.012（blockout の頂点）、新しい船は x = 0。差はその 12 mm × 縮尺の分だけ"}
    hyd = brep["hydrostatics"]
    res["model"] = {
        "reference_length_m": P["reference_length_m"], "real_dimensions_per_boat": real, "root_position_diff_vs_ds40_m": root_same,
        "parts": {k: {"vertices": v["vertices"], "polygons": v["polygons"], "materials": v["materials"]} for k, v in brep["objects"].items()},
        "collision": brep["tables"]["collision"], "buoyancy_hull_volume_units3": hyd["closed_mesh_volume_units3"],
        "hydrostatics_table_units": hyd["table"], "buoyancy_points": brep["buoyancy_points"],
        "hydrostatics_boat_mid_at_research_draft": {
            "draft_m": r4(0.171 * real["boat_mid"]["scale"], 3), "volume_m3": r4(next(r for r in hyd["table"] if abs(r["draft_units"] - 0.171) < 1e-9)["volume_units3"] * real["boat_mid"]["scale"] ** 3, 3),
            "displacement_t_seawater_1025": r4(next(r for r in hyd["table"] if abs(r["draft_units"] - 0.171) < 1e-9)["volume_units3"] * real["boat_mid"]["scale"] ** 3 * 1.025, 3),
            "note_ja": "調べの部の喫水の推定 0.20 m（全長 11.667 m）を右船の縮尺へ直した値。静水の釣り合いは設計42"},
        "blender_checks": brep["checks"], "tips": brep["tips"], "research_input": brep.get("research_input"),
        "prefab_parts": bld["prefabParts"], "scene_build": {"scene41": bld["scene41"], "scene41_sha256": bld["scene41Sha256"], "prefab_sha256": bld["prefabSha256"],
                                                             "scene39_unchanged": bld["scene39Sha256Before"] == bld["scene39Sha256After"], "boats": bld["boats"],
                                                             "protected_unchanged": bld["protectedUnchanged"]},
        "render_protected_unchanged": rep["protectedUnchanged"]}

    # ---------------------------------------------------------------- 6. 図
    paint = Image.open(PAINT).convert("RGB")
    after = Image.open(p_off).convert("RGB")
    before = Image.open(os.path.join(U41, "views", "painting_t120_off_blockout.png")).convert("RGB")
    box = (150, 440, 1710, 1000)
    tiles = [label(paint.crop(box), ["原画（Met JP1847、表示の枠）"]),
             label(before.crop(box), ["置き換えの前（M1 の blockout。設計40 と画素まで同じ）"]),
             label(after.crop(box), ["設計41：押送船のモデル（根の置き方は同じ）"])]
    sheet = Image.new("RGB", (box[2] - box[0], (box[3] - box[1]) * 3))
    for i, t in enumerate(tiles):
        sheet.paste(t, (0, i * (box[3] - box[1])))
    sheet.save(os.path.join(FIG, "fig_ds41_painting_before_after.png"))
    label(after, ["設計41 原画視点 t* = 12 s（紙の 3 層は切、PaintingCam v1）"]).save(os.path.join(FIG, "ds41_painting_t120_off.png"))
    # 原画 50% の重ね（船の周り）
    ov = Image.blend(after, paint, 0.5)
    label(ov.crop(box), ["原画 50% の重ね（船の周り）"]).save(os.path.join(FIG, "fig_ds41_painting_overlay50_boats.png"))
    # 船の近く（前と後）
    tw, th = 960, 540
    cs = Image.new("RGB", (tw * 2, th * 3))
    for i, k in enumerate(("boat_mid", "boat_fg", "boat_left")):
        b0 = Image.open(os.path.join(U41, "views", "close_%s_t120_off_blockout.png" % k)).convert("RGB").resize((tw, th))
        b1 = Image.open(os.path.join(U41, "views", "close_%s_t120_off.png" % k)).convert("RGB").resize((tw, th))
        cs.paste(label(b0, ["%s 前（blockout）" % k]), (0, i * th))
        cs.paste(label(b1, ["%s 後（設計41）" % k]), (tw, i * th))
    cs.save(os.path.join(FIG, "fig_ds41_close_before_after.png"))
    # 座席 v1（前と後）・座席の低い視点・横・背面
    vs = Image.new("RGB", (tw * 2, th * 3))
    items = [("seat_t120_off_blockout", "座席 v1 前（blockout）"), ("seat_t120_off", "座席 v1 後"), ("seat_low_t120_off", "座席 v1（唇の方位、仰角 20°）"),
             ("seat_toward_wave_t120_off", "座席から波の方向"), ("side_left_t120_off", "左の側面"), ("back_t120_off", "背面（CP1 と同じ位置）")]
    for i, (f, lb) in enumerate(items):
        vs.paste(label(Image.open(os.path.join(U41, "views", f + ".png")).convert("RGB").resize((tw, th)), [lb]), ((i % 2) * tw, (i // 2) * th))
    vs.save(os.path.join(FIG, "fig_ds41_views.png"))
    # Blender の図
    bs = Image.new("RGB", (tw * 2, th * 3))
    bl = [("preview_visual_side_port", "Blender 左舷の側面（正射影）"), ("preview_visual_top", "Blender 上から（船首は左）"),
          ("preview_visual_three_quarter_bow", "Blender 船首の側から"), ("preview_visual_inside_from_stern", "Blender 船尾の上から船内"),
          ("preview_helpers_three_quarter_bow", "衝突形状（凸包 3 つ）と浮力用の船体"), ("preview_helpers_side_port", "衝突形状と浮力用の船体（側面）")]
    for i, (f, lb) in enumerate(bl):
        bs.paste(label(Image.open(os.path.join(B41, f + ".png")).convert("RGB").resize((tw, th)), [lb]), ((i % 2) * tw, (i // 2) * th))
    bs.save(os.path.join(FIG, "fig_ds41_blender_model.png"))
    # 評価器の偏差図（船の周り）
    ovp = os.path.join(EVAL, "off_noline", "off_noline_overlay.png")
    if os.path.exists(ovp):
        Image.open(ovp).convert("RGB").crop(box).save(os.path.join(FIG, "fig_ds41_eval_overlay_boats.png"))
    res["figures"] = {f: {"sha256": sha(os.path.join(FIG, f)), "bytes": os.path.getsize(os.path.join(FIG, f))} for f in sorted(os.listdir(FIG))}

    # ---------------------------------------------------------------- 7. 受入
    acc = {
        "design07_no_scale_axis_mirror_error": res["design07_check"]["verdict"] == "pass",
        "record_74_75_157_159_and_change_from_cp1": all(k in boats for k in ("74", "75", "157", "159")),
        "record_seat_v1_eye_vs_gunwale": True,
        "no_regression_painting_view": res["regression"]["pass"],
    }
    res["acceptance"] = {"items": acc, "pass": all(acc.values()),
                         "criterion_ja": "計画 §2.4 設計41 の最小の受入：Unity で尺度・軸・左右の反転なし（設計07 の検査）。原画視点の 74・75・157・159 を記録し CP1 からの変化を示す（判定は仕上げ40・41）。座席 v1 の目の高さと船縁の関係を記録。＋計画 §2.0 の回帰なし"}
    save(os.path.join(OUT, "ds41_model_metrics.json"), res)

    # ---------------------------------------------------------------- run.json
    def files(d, pat=None):
        out = {}
        for root, _, fs in os.walk(d):
            for f in fs:
                p = os.path.join(root, f)
                if pat and not any(f.endswith(x) for x in pat):
                    continue
                out[rel(p)] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
        return out
    run = {"schema": "GreatWave.DS41.model_run/1", "generated_utc": now(),
           "tools": {"blender": brep["software"], "unity": rep["unity"], "device": rep["device"], "graphics_api": rep["graphicsApi"], "python": sys.version.split()[0],
                     "numpy": np.__version__, "opencv": cv2.__version__},
           "commands_ja": [
               '"G:/SteamLibrary/steamapps/common/Blender/blender.exe" --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/ds41/ds41_boat_blender.py',
               "py -3.10 -B Tools/GWWaveGen/ds41/ds41_stage_unity.py",
               "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds41/run_ds41_unity.ps1 -Method GreatWave.Design41.EditorTools.DS41Boats.ImportCheck -Log ImportCheck",
               "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds41/run_ds41_unity.ps1 -Method GreatWave.Design41.EditorTools.DS41Boats.BuildScene -Log BuildScene",
               "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds41/run_ds41_unity.ps1 -Method GreatWave.Design41.EditorTools.DS41Boats.Render -Log Render",
               "py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/41/model/unity --sets t28_claws,t28_white",
               "py -3.10 -B Tools/GWWaveGen/ds41/ds41_compare.py"] + cmds,
           "inputs": {rel(p): sha(p) for p in [SEAT, CP1M, PAINT, os.path.join(U40, "ds30_tstar_regress.json"), os.path.join(U40, "ds40_render_report.json"),
                                              os.path.join(RES, "oshiokuri_dimensions.json")] + ([os.path.join(RES, "dims.json")] if os.path.exists(os.path.join(RES, "dims.json")) else [])},
           "code": files(os.path.join(REPO, "Tools", "GWWaveGen", "ds41"), (".py", ".json", ".ps1")),
           "unity_assets": {rel(p): sha(p) for p in [os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design41", "Editor", "DS41Boats.cs"),
                                                      os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design41", "Models", "ds41_oshiokuri.fbx"),
                                                      os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design41", "Models", "ds41_oshiokuri.fbx.meta"),
                                                      os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design41", "Prefabs", "DS41_Oshiokuri.prefab"),
                                                      os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design41", "Scenes", "DS41_Boats.unity")]},
           "outputs_blender": files(B41), "outputs_unity": files(U41, (".json", ".png")), "outputs_eval": files(EVAL), "figures": res["figures"],
           "not_committed_ja": "Unity/Build/Design/41/model/ 以下はすべて Git 対象外（/Unity/Build/）。.blend・FBX の制作元は Build に置き、Unity の資産の FBX は同じバイト（ds41_stage_unity.py が写す）。"}
    save(os.path.join(OUT, "ds41_model_run.json"), run)
    print("DS41_COMPARE acceptance=%s regression=%s design07=%s" % (res["acceptance"]["pass"], res["regression"]["pass"], res["design07_check"]["verdict"]))
    print(json.dumps({k: (v.get("ds41_max_px"), v.get("cp1_max_px"), v.get("ds40_max_px")) for k, v in boats.items()}, ensure_ascii=False))
    print(json.dumps(seatrec["gunwale_top_at_seat_station"], ensure_ascii=False))
    print(json.dumps(seatrec["new_deck_hit"], ensure_ascii=False))


if __name__ == "__main__":
    main()
