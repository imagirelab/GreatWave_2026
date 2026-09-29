# -*- coding: utf-8 -*-
"""設計34 の記録：証拠（Docs/Evidence/Design/34/）を作り、metrics.json と run.json を書く。

値は次の出力から読む（どれも Git 対象外）。
  - Unity の部：Unity/Build/Design/34/unity3/（metrics.json・run.json・main/ds34_render_report.json・
    main/ds30_tstar_regress.json・main/tstar_sym_t28_{claws,white}/tstar_sym.json・playmode/ds34_playmode.csv・図と動画）
  - 進行役の独立の検査：リポジトリの外のコード。コードと出力の写しは Unity/Build/Design/34/indep_check/（ic34_*.json・図）
この道具で新しく数えるのは、次の数え直しだけ（Unity/Build/Design/34/record/ds34_record_counts.json にも書く）。
  - 描画の報告の遮蔽・両眼・時刻の表を足し直す（A1〜A3 の値が報告のまとめと合うか）
  - Play モードの CSV（814 行）の時刻の差と入切の旗
  - 色区の項目を、設計29修正01 が採った「両側の読み」で、爪なし → 爪ありに並べる（267 の白の平塗りの帯を含む）
  - 作業の時刻（ファイルの時刻）
図は 1920×1080 の枠に収め、余白に日本語の説明を入れる（元の図の英語の見出しは残す）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds34/ds34_record.py
"""
import csv
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
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
B34 = REPO + "/Unity/Build/Design/34"
U3 = B34 + "/unity3"
IND = B34 + "/indep_check"
REC = B34 + "/record"
EV = REPO + "/Docs/Evidence/Design/34"
FFPROBE = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
FONT = "C:/Windows/Fonts/meiryo.ttc"
MP4_LIMIT = 5 * 1024 * 1024
W, H = 1920, 1080
CLAW_FRAMES_SHA_DS33 = "6e7629889a47efc0172d40c28364b59eadef48e419d0dad5c279e3fa3d7f7565"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jload_nan(p):
    """NaN を含む JSON（Python の json.dump の既定）を読み、NaN を None にして返す。"""
    with open(p, encoding="utf-8") as f:
        d = json.load(f)

    def fix(o):
        if isinstance(o, float) and math.isnan(o):
            return None
        if isinstance(o, dict):
            return {k: fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [fix(v) for v in o]
        return o
    return fix(d)


def jdump(p, d):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1, allow_nan=False)
        f.write("\n")


def imread(p):
    im = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit("画像を読めない: " + p)
    return im


def imwrite(p, im):
    ok, buf = cv2.imencode(".png", im)
    if not ok:
        raise SystemExit("PNG を書けない: " + p)
    buf.tofile(p)


def text_lines(img, lines, x, y, size=24, col=(20, 20, 20), gap=8):
    """BGR の画像に日本語の行を描く（PIL）。"""
    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, size)
    for ln in lines:
        d.text((x, y), ln, font=f, fill=(col[2], col[1], col[0]))
        y += size + gap
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def label_box(img, x, y, text, size=22):
    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, size)
    bb = d.textbbox((x, y), text, font=f)
    d.rectangle([bb[0] - 5, bb[1] - 3, bb[2] + 5, bb[3] + 3], fill=(30, 30, 30))
    d.text((x, y), text, font=f, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def fit(img, box_w, box_h):
    s = min(box_w / img.shape[1], box_h / img.shape[0], 1.0)
    if s < 1.0:
        img = cv2.resize(img, (int(round(img.shape[1] * s)), int(round(img.shape[0] * s))), interpolation=cv2.INTER_AREA)
    return img, s


def canvas():
    return np.full((H, W, 3), 245, np.uint8)


def paste(cv, img, x, y):
    h, w = img.shape[:2]
    cv[y:y + h, x:x + w] = img
    return cv


def fig_single(src, dst, caption, cap_h=None):
    """1 枚の図を 1920×1080 に収め、下の余白に日本語の説明を入れる。"""
    im = imread(src)
    n = len(caption)
    ch = cap_h if cap_h is not None else 20 + n * 34
    small, s = fit(im, W, H - ch)
    cv = canvas()
    x0 = (W - small.shape[1]) // 2
    paste(cv, small, x0, 0)
    cv = text_lines(cv, caption, 24, small.shape[0] + 12, size=24)
    imwrite(dst, cv)
    return {"src": rel(src), "src_sha256": sha(src), "scale": round(s, 4), "dst": rel(dst)}


def fig_stack(srcs, dst, caption):
    """横長の図を縦に重ねて 1920×1080 に収める。"""
    ims = [imread(p) for p in srcs]
    ch = 20 + len(caption) * 34
    tot = sum(i.shape[0] for i in ims)
    s = min(1.0, (H - ch) / tot, W / max(i.shape[1] for i in ims))
    cv = canvas()
    y = 0
    for im in ims:
        sm = cv2.resize(im, (int(round(im.shape[1] * s)), int(round(im.shape[0] * s))), interpolation=cv2.INTER_AREA) if s < 1 else im
        paste(cv, sm, (W - sm.shape[1]) // 2, y)
        y += sm.shape[0]
    cv = text_lines(cv, caption, 24, y + 12, size=24)
    imwrite(dst, cv)
    return {"src": [rel(p) for p in srcs], "src_sha256": [sha(p) for p in srcs], "scale": round(s, 4), "dst": rel(dst)}


def fig_grid2x2(srcs, labels, dst, caption):
    ims = [imread(p) for p in srcs]
    ch = 20 + len(caption) * 34
    cw, chh = W // 2, (H - ch) // 2
    cv = canvas()
    scale = None
    for i, (im, lb) in enumerate(zip(ims, labels)):
        sm, s = fit(im, cw, chh)
        scale = s
        x, y = (i % 2) * cw, (i // 2) * chh
        paste(cv, sm, x, y)
        cv = label_box(cv, x + 10, y + 8, lb, size=22)
    cv = text_lines(cv, caption, 24, 2 * chh + 12, size=24)
    imwrite(dst, cv)
    return {"src": [rel(p) for p in srcs], "src_sha256": [sha(p) for p in srcs], "scale": round(scale, 4), "dst": rel(dst)}


def ftime(p):
    t = os.path.getmtime(p)
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def ctime(p):
    t = os.path.getctime(p)
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def probe(p):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,nb_frames,r_frame_rate,codec_name", "-of", "json", p],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]


# ------------------------------------------------------------------ 数え直し
def recount_render_report(rr):
    occ = rr["occlusion"]
    by = {}
    for o in occ:
        k = o["layer"]
        by.setdefault(k, {"hiddenByBoat": 0, "leak": 0, "cases": 0})
        by[k]["hiddenByBoat"] += o["hiddenByBoat"]
        by[k]["leak"] += o["leak"]
        by[k]["cases"] += 1
    views = sorted({o["view"] for o in occ})
    times = sorted({o["t"] for o in occ})
    painting_claws_hidden = sum(o["hiddenByBoat"] for o in occ if o["view"] == "painting" and o["layer"] == "claws")
    painting_claws_hidden_t = sorted({o["t"] for o in occ if o["view"] == "painting" and o["layer"] == "claws" and o["hiddenByBoat"] > 0})
    fp = sum(x["clawDiagPx"] + x["sprayDiagPx"] for x in rr["falsePositives"])
    st = rr["stereo"]
    judged = [x for x in st if min(x["clawPxL"], x["clawPxR"]) >= 500]
    rec_only = [x for x in st if min(x["clawPxL"], x["clawPxR"]) < 500]
    tm = rr["timing"]
    claw_off = max(abs(x["clawFrame"] - x["k"]) for x in tm)
    spray_off = max(abs(x["sprayFrame"] - x["k"]) for x in tm)
    return {
        "A1_capture": {"frames": len(tm), "max_abs_claw_frame_minus_k": claw_off, "max_abs_spray_frame_minus_k": spray_off,
                       "max_abs_hero_tau_minus_warp_tau": max(abs(x["heroTau"] - x["warpTau"]) for x in tm),
                       "root_max_mm_all": rr["rootMaxMmAll"], "root_tri_max_mm_all": rr["rootTriMaxMmAll"],
                       "control_one_frame_early_median_of_frame_max_mm": rr["rootMaxPrevMmMedian"],
                       "claws_in_root_table": len(rr["rootPerClaw"])},
        "A2_occlusion": {"views": views, "times_s": times, "cases": len(occ), "by_layer": by,
                         "painting_claws_hidden_px": painting_claws_hidden, "painting_claws_hidden_times_s": painting_claws_hidden_t,
                         "false_positive_px": fp},
        "A3_stereo": {"pairs": len(st), "judged": len(judged),
                      "max_rel_diff_judged": max(abs(x["clawPxL"] - x["clawPxR"]) / max(x["clawPxL"], x["clawPxR"]) for x in judged),
                      "record_only": [[x["view"], x["t"], x["clawPxL"], x["clawPxR"]] for x in rec_only],
                      "spray_max_rel_diff": max(x["sprayRelDiff"] for x in st)},
        "shader_all_compiled": rr["shaderAllCompiled"],
        "stereo_variant_rt_array_index": any(x.get("rtArrayIndexInOutput") for x in rr["shaderChecks"]),
        "protected_unchanged": rr["protectedUnchanged"], "changed_files": rr["changedFiles"],
        "claw_frames_sha256": rr["clawFramesSha256"], "claw_frames_same_as_ds33": rr["clawFramesSha256"] == CLAW_FRAMES_SHA_DS33,
    }


def recount_playmode(p):
    rows = []
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    fl = lambda r, k: float(r[k])  # noqa: E731
    d_claw = max(abs(fl(r, "claw_t") - fl(r, "t")) for r in rows)
    d_spray = max(abs(fl(r, "spray_t") - fl(r, "t")) for r in rows)
    d_tau = max(abs(fl(r, "hero_tau") - fl(r, "warp_tau")) for r in rows)
    ph = max(abs(fl(r, "claw_frame") - 30.0 * fl(r, "t")) for r in rows)
    mism_claw = sum(1 for r in rows if r["claws_on"] != r["claw_renderer"])
    mism_spray = sum(1 for r in rows if r["spray_on"] != r["spray_draw"])
    states = []
    for r in rows:
        s = (r["white_band"], r["claws_on"], r["spray_on"])
        if not states or states[-1][0] != s:
            states.append([s, r["t"]])
    dts = sorted({r["deltaTime"] for r in rows})
    return {"rows": len(rows), "dt_values": dts[:3] + (["…"] if len(dts) > 3 else []),
            "max_abs_claw_t_minus_t_s": d_claw, "max_abs_spray_t_minus_t_s": d_spray,
            "max_abs_hero_tau_minus_warp_tau": d_tau, "max_abs_claw_frame_minus_30t": ph,
            "claw_flag_vs_renderer_mismatch_rows": mism_claw, "spray_flag_vs_draw_mismatch_rows": mism_spray,
            "toggle_sequence_white_claws_spray": [["".join(s), t] for s, t in states]}


def colour_table(sym_white, sym_claws):
    """色区の項目を、両側の読みで爪なし → 爪ありに並べる。"""
    def rows(d):
        return {(r["item"], r["measure"]): r for r in d["rows"]}
    rw, rc = rows(sym_white), rows(sym_claws)
    out = []
    for key in rw:
        a, b = rw[key], rc[key]
        out.append({"item": key[0], "measure": key[1], "base_28r01_px": a["r28_sym_max_px"],
                    "no_claws_px": a["kp_sym_max_px"], "claws_px": b["kp_sym_max_px"],
                    "verdict_no_claws": a["kp_verdict_sym"], "verdict_claws": b["kp_verdict_sym"]})
    fw, fc = sym_white["flat_painting_view_266_267"]["kp"], sym_claws["flat_painting_view_266_267"]["kp"]
    flat = {}
    for cls in ("white", "mizuiro", "ai_mid", "ai_dark"):
        flat[cls] = {"no_claws_bands_ge_20px_sym": fw[cls]["sym"]["bands_ge_20px"], "claws_bands_ge_20px_sym": fc[cls]["sym"]["bands_ge_20px"],
                     "no_claws_bands_ge_20px_strict": fw[cls]["strict"]["bands_ge_20px"], "claws_bands_ge_20px_strict": fc[cls]["strict"]["bands_ge_20px"],
                     "no_claws_dE00_std_sym": fw[cls]["sym"]["dE00_to_median_std"], "claws_dE00_std_sym": fc[cls]["sym"]["dE00_to_median_std"]}
    flips = sorted({r["item"] for r in out if r["verdict_no_claws"] == "pass" and r["verdict_claws"] == "fail"}, key=int)
    white267 = flat["white"]
    if white267["no_claws_bands_ge_20px_sym"] == 0 and white267["claws_bands_ge_20px_sym"] > 0:
        flips.append("267")
    return {"rows": out, "flat_266_267": flat,
            "pass_to_fail_in_sym_reading": flips,
            "note_ja": "両側の読み（設計29修正01 が採った読み。原画の空と描画の空から 2 px 以内を色区の項目から除く）。"
                       "267 の白の平塗りは、設計29修正01 の記録どおり、両側の読みの 20 px 以上の帯が 0 のとき合格と読む"
                       "（tstar_sym.json の verdicts_kp_sym の 267 は評価器の定義のままの判定の写しなので使わない）。"}


def sky_count():
    """212（空の上の方、表示の行 0〜379）の目安：爪が、爪なしの画像で空だった画素をいくつ変えるか（評価器の 212 の判定ではない）。"""
    R = U3 + "/main/t28_{}/t28/render/"
    a, b = imread(R.format("white") + "af28r01_class_ids.png"), imread(R.format("claws") + "af28r01_class_ids.png")
    ca, cb = imread(R.format("white") + "af28r01_painting.png"), imread(R.format("claws") + "af28r01_painting.png")
    sky = (a == 255).all(2)
    sy = a.shape[0] // ca.shape[0]
    sky1 = cv2.resize(sky.astype(np.uint8), (ca.shape[1], ca.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
    dc = (ca != cb).any(2)
    di = (a != b).any(2)
    return {"colour_changed_px": int(dc.sum()), "colour_changed_rows_0_379": int(dc[:380].sum()),
            "colour_changed_on_no_claw_sky_rows_0_379": int((dc & sky1)[:380].sum()),
            "class_id_scale": sy, "class_id_changed_px": int(di.sum()), "class_id_changed_on_sky": int((di & sky).sum()),
            "note_ja": "色の画像は 1920×1080、色区 ID の画像は 3840×2160（2 倍）。空は爪なしの色区 ID の白"}


def main():
    os.makedirs(EV, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    m3 = jload(U3 + "/metrics.json")
    r3 = jload(U3 + "/run.json")
    rr = jload(U3 + "/main/ds34_render_report.json")
    reg = jload(U3 + "/main/ds30_tstar_regress.json")
    sym_w = jload(U3 + "/main/tstar_sym_t28_white/tstar_sym.json")
    sym_c = jload(U3 + "/main/tstar_sym_t28_claws/tstar_sym.json")
    ic = jload(IND + "/ic34_summary.json")

    # 作り手の記録と、いまのコードが同じか（違えば止まる）
    code_now = {k: sha(REPO + "/" + k) for k in r3["code_sha256"]}
    code_diff = [k for k in code_now if code_now[k] != r3["code_sha256"][k]]
    if code_diff:
        raise SystemExit("Unity の部の run.json とコードの SHA-256 が違う: " + ", ".join(code_diff))
    if rr["clawFramesSha256"] != CLAW_FRAMES_SHA_DS33:
        raise SystemExit("爪のコマの表が設計33 と違う")

    counts = {
        "schema": "GreatWave.DS34.record_counts/1",
        "render_report": recount_render_report(rr),
        "playmode": recount_playmode(U3 + "/playmode/ds34_playmode.csv"),
        "colour_sym": colour_table(sym_w, sym_c),
        "sky_212_claws": sky_count(),
        "outline": {"t28_white": reg["sets"]["t28_white"]["lfgate"], "t28_claws": reg["sets"]["t28_claws"]["lfgate"],
                    "silhouette_78_130_131_claws": reg["sets"]["t28_claws"]["silhouette_diff_vs_29r01_px"],
                    "base_29r01": {"132_sigma12_max": reg["base_29r01"]["lfgate"]["132_sigma12_max"],
                                   "72_sigma24_p95": reg["base_29r01"]["lfgate"]["72_sigma24_p95"]}},
        "playmode_images_same": {"1_all_vs_5_all_on_again": sha(U3 + "/playmode/ds34_playmode_painting_hold_1_all.png") ==
                                 sha(U3 + "/playmode/ds34_playmode_painting_hold_5_all_on_again.png")},
        "file_times": {
            "build34_created": ctime(B34), "unity3_started_txt": ftime(U3 + "/_started.txt"),
            "code_ds34_created": ctime(REPO + "/Tools/GWWaveGen/ds34"), "assets_design34_created": ctime(REPO + "/Unity/Assets/GreatWave/Design34"),
            "unity_logs": {os.path.basename(p): [ctime(p), ftime(p)] for p in sorted(
                [U3 + "/logs/" + x for x in os.listdir(U3 + "/logs")])},
            "unity3_metrics": ftime(U3 + "/metrics.json"), "unity3_readme": ftime(U3 + "/README_interface.txt"),
            "indep_check_created": ctime(IND), "indep_check_summary": ftime(IND + "/ic34_summary.json"),
            "record_run": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    jdump(REC + "/ds34_record_counts.json", counts)

    # ------------------------------------------------------------ 図
    figs = []
    F = U3 + "/fig/"
    figs.append(fig_stack([F + "fig_ds34_toggles_painting_t12p00.png", F + "fig_ds34_toggles_seat_t12p00.png"],
                          EV + "/fig_ds34_toggles_t12p00.png",
                          ["層の入切 2³＝8 通り（Unity の PC 描画、t＝12 s＝t*）。上＝原画視点、下＝座席 v1。",
                           "none＝3 層とも切、white band＝白の帯（シートの T_white の色）、claws＝爪（結合メッシュ）、spray＝飛沫（instancing）。",
                           "白の帯を切った枠は、主役波の白を白の前の色で塗る（形は同じ）。"]))
    figs.append(fig_stack([F + "fig_ds34_toggles_painting_t11p50.png", F + "fig_ds34_toggles_seat_t11p50.png"],
                          EV + "/fig_ds34_toggles_t11p50.png",
                          ["層の入切 8 通り（Unity の PC 描画、t＝11.5 s。爪が伸びている途中）。上＝原画視点、下＝座席 v1。",
                           "見出しの英語は上の図と同じ意味。"]))
    shutil.copyfile(F + "fig_ds34_stills_sheet.png", EV + "/fig_ds34_stills_sheet.png")
    figs.append({"src": rel(F + "fig_ds34_stills_sheet.png"), "src_sha256": sha(F + "fig_ds34_stills_sheet.png"), "scale": 1.0,
                 "dst": rel(EV + "/fig_ds34_stills_sheet.png")})
    figs.append(fig_single(F + "fig_ds34_occlusion_boat.png", EV + "/fig_ds34_occlusion_boat.png",
                           ["船の後ろの遮蔽（確認用の色、MSAA なし）。列：色の画像／船なし（爪＝マゼンタ・飛沫＝シアン）／船あり／赤＝船に隠された画素。",
                            "行：原画視点 爪 t 10 s（127 px）、occl_mid 爪 t 11 s（359 px）、occl_fg 爪 t 10 s（69 px）、occl_mid 飛沫 t 11 s（2,297 px）。漏れはどれも 0。"]))
    figs.append(fig_single(F + "fig_ds34_mock_stereo.png", EV + "/fig_ds34_mock_stereo.png",
                           ["Mock の両眼（カメラを ±32 mm ずらして 2 回描く PC の代理。立体の描画経路 SPI ではない）。",
                            "左 2 列＝L・R の色の画像、右 2 列＝爪を確認用の色にした画像と画素数。座席 t 11・12 s、原画視点 t 11・12 s。"]))
    shutil.copyfile(F + "fig_ds34_one_clock.png", EV + "/fig_ds34_one_clock.png")
    figs.append({"src": rel(F + "fig_ds34_one_clock.png"), "src_sha256": sha(F + "fig_ds34_one_clock.png"), "scale": 1.0,
                 "dst": rel(EV + "/fig_ds34_one_clock.png")})
    figs.append(fig_single(F + "fig_ds34_colour133_claws.png", EV + "/fig_ds34_colour133_claws.png",
                           ["色区 133 の最悪の点（表示 (751, 188)、マゼンタの円）。左から：色区 ID 爪なし／色区 ID 爪あり／色 爪なし／色 爪あり。",
                            "ID の色：赤＝白、緑＝淡い水色、黄＝藍中、青＝藍濃。爪の白と淡い水色の帯が、焼き込みの色面の白と淡い水色の模様の上に重なる。",
                            "爪を色区 ID に入れた読みでは 133 が 0.718 → 8.837 px（両側の読み）で不合格になる。この番号では記録のみ（第 3.4 節）。"]))
    P = U3 + "/playmode/"
    figs.append(fig_grid2x2([P + "ds34_playmode_painting_hold_1_all.png", P + "ds34_playmode_painting_hold_2_white_off.png",
                             P + "ds34_playmode_painting_hold_3_white_claws_off.png", P + "ds34_playmode_painting_hold_4_all_off.png"],
                            ["① 3 層すべて", "② 白の帯を切る", "③ 白の帯と爪を切る", "④ 3 層とも切る"],
                            EV + "/fig_ds34_playmode_toggles.png",
                            ["Play モード（Editor の batch、dt 0.02 s）で t* の保持の間に層を順に切った原画視点（960×540 の画像）。",
                             "⑤ すべて入れ直した画像は ① と SHA-256 まで同じ。HMD でも PC ビルドでもない。"]))
    figs.append(fig_stack([IND + "/ic34_vis_tstar_crop.png", IND + "/ic34_vis_lip_zoom.png"],
                          EV + "/fig_ds34_claws_tstar_look.png",
                          ["進行役の独立の検査が動画から取り出した t*（コマ 360）の原画視点。上：左＝白の帯だけ、右＝3 層すべて。",
                           "下：唇の先の拡大（左＝白の帯だけ、中＝3 層すべて、右＝爪だけ）。爪の白い上面は白の帯に溶け、",
                           "淡い水色の細い弧が焼き込みの模様の上に重なって見える。空へ出る爪の先は唇の輪郭に小さな白い欠けを作る。"]))

    # ------------------------------------------------------------ 動画
    vids = []
    for src in [U3 + "/video/ds34_layers_2x2_painting_30fps.mp4", U3 + "/video/ds34_layers_2x2_seat_30fps.mp4",
                U3 + "/video_run/video/ds34_all_painting_30fps.mp4"]:
        dst = EV + "/" + os.path.basename(src)
        if os.path.getsize(src) > MP4_LIMIT:
            raise SystemExit("動画が 5 MB を超える: " + src)
        shutil.copyfile(src, dst)
        pr = probe(dst)
        vids.append({"src": rel(src), "dst": rel(dst), "bytes": os.path.getsize(dst), "sha256": sha(dst),
                     "width": pr["width"], "height": pr["height"], "frames": int(pr["nb_frames"]), "fps": pr["r_frame_rate"]})

    # ------------------------------------------------------------ JSON の写し
    copies = {
        U3 + "/metrics.json": "ds34_unity3_metrics.json",
        U3 + "/main/ds30_tstar_regress.json": "ds34_tstar_regress.json",
        U3 + "/main/tstar_sym_t28_white/tstar_sym.json": "ds34_tstar_sym_no_claws.json",
        U3 + "/main/tstar_sym_t28_claws/tstar_sym.json": "ds34_tstar_sym_claws.json",
        IND + "/ic34_summary.json": "ds34_indep_summary.json",
        IND + "/ic34_a1_sheet_line.json": "ds34_indep_a1_sheet_line.json",
        IND + "/ic34_a1_roots.json": "ds34_indep_a1_roots.json",
        IND + "/ic34_a1_sheet_whiteoff.json": "ds34_indep_a1_sheet_whiteoff.json",
        IND + "/ic34_a2_recount.json": "ds34_indep_a2_recount.json",
        IND + "/ic34_a2_video.json": "ds34_indep_a2_video.json",
        IND + "/ic34_a3_stereo.json": "ds34_indep_a3_stereo.json",
    }
    json_out = {}
    for src, name in copies.items():
        jdump(EV + "/" + name, jload_nan(src))
        json_out[name] = {"src": rel(src), "src_sha256": sha(src)}
    jdump(EV + "/ds34_indep_a1_video.json", jload_nan(IND + "/ic34_a1_video.json"))
    json_out["ds34_indep_a1_video.json"] = {"src": rel(IND + "/ic34_a1_video.json"), "src_sha256": sha(IND + "/ic34_a1_video.json"),
                                            "note_ja": "元の NaN を null にした"}
    # 描画の報告は大きい（347 KB）ので、コマごとの表を除いたまとめを写す
    rr_small = {k: v for k, v in rr.items() if k not in ("timing", "rootPerClaw", "files", "filesSha256")}
    rr_small["rootPerClaw_worst5"] = sorted(rr["rootPerClaw"], key=lambda x: -x["maxMm"])[:5]
    jdump(EV + "/ds34_render_report_summary.json", rr_small)
    json_out["ds34_render_report_summary.json"] = {"src": rel(U3 + "/main/ds34_render_report.json"), "src_sha256": sha(U3 + "/main/ds34_render_report.json"),
                                                   "note_ja": "コマごとの時刻の表・爪ごとの根元の表・画像の一覧を除いた"}
    jdump(EV + "/ds34_record_counts.json", counts)
    json_out["ds34_record_counts.json"] = {"src": rel(REC + "/ds34_record_counts.json")}

    # ------------------------------------------------------------ metrics.json
    ct = counts["colour_sym"]
    crow = {(r["item"], r["measure"]): r for r in ct["rows"]}
    A = m3["acceptance"]
    metrics = {
        "schema": "GreatWave.DS34.metrics/1",
        "number": "設計34",
        "title_ja": "帯・爪・小飛沫を別々に Unity で再生する",
        "generated_local": counts["file_times"]["record_run"],
        "evidence_kind_ja": "Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）と、Editor の batch の Play モード（dt 0.02 s 固定）。"
                            "進行役の独立の検査は、Unity の部のコードを使わない numpy/OpenCV（動画から取り出したコマと保存された画像）。HMD 実機の結果ではない。利用者は確かめていない。",
        "acceptance": {
            "ja": "計画 §2.2 の設計34 の最小の受入（Q26：この番号は最小の受入だけを満たす。修正は 1 回まで）",
            "A1_three_layers_time_offset_0": {
                "unity_part": {k: A["A1_three_layers_time_offset_0"][k] for k in (
                    "capture_frames", "capture_max_claw_frame_offset", "capture_max_spray_frame_offset", "capture_max_hero_tau_minus_tau_t",
                    "unity_root_to_sheet_max_mm", "unity_root_to_sheet_triangle_max_mm", "control_claws_one_frame_early_median_of_frame_max_mm_t0_to_tstar",
                    "playmode_frames", "playmode_frame_index_mismatch_claws", "playmode_frame_index_mismatch_spray",
                    "playmode_max_abs_claw_t_minus_t_s", "playmode_max_abs_spray_t_minus_t_s", "playmode_max_abs_hero_tau_minus_tau_t")},
                "independent": ic["A1_time_offset_0"],
                "record_recount": {"capture": counts["render_report"]["A1_capture"], "playmode": counts["playmode"]},
                "verdict": "合格",
            },
            "A2_claws_spray_behind_hull_hidden": {
                "unity_part": {k: A["A2_claws_spray_behind_hull_hidden"][k] for k in (
                    "views", "times_s", "cases", "hidden_by_boat_px_claws", "hidden_by_boat_px_spray", "leak_px_total", "false_positive_px")},
                "independent": ic["A2_boat_occlusion"],
                "record_recount": counts["render_report"]["A2_occlusion"],
                "verdict": "合格",
            },
            "A3_mock_two_eye_claw_px_lr_diff_lt_10pct": {
                "unity_part": {"judged": A["A3_mock_two_eye_claw_px_lr_diff_lt_10pct"]["judged"],
                               "record_only": A["A3_mock_two_eye_claw_px_lr_diff_lt_10pct"]["record_only"],
                               "max_rel_diff_judged": A["A3_mock_two_eye_claw_px_lr_diff_lt_10pct"]["max_rel_diff_judged"],
                               "min_px_for_verdict": 500},
                "independent": ic["A3_mock_stereo"],
                "record_recount": counts["render_report"]["A3_stereo"],
                "verdict": "合格（PC の代理）",
            },
            "HMD_H1_H3_H4": {"verdict": "保留", "ja": "PS VR2 は未導入（利用者の手が要る）。Mock の両眼と PC の描画で代えた。爪のシェーダーは STEREO_INSTANCING_ON の変種のコンパイルだけ確かめた"},
            "all_pass": True,
        },
        "backlog": {
            "ja": "計画 §2.2 の設計34：148（奥の線が透けない、事前検査）、206（記録）",
            "items": {
                "148": {"value_ja": "爪・飛沫は不透明（ZWrite On・ZTest LEqual）。遮蔽の検査で、船の後ろの爪・飛沫が透ける画素は 0。爪の後ろの藍の線が透けないことは設計38 で測る",
                        "verdict": "記録のみ（事前検査）"},
                "206": {"value_ja": "原画視点 t* の Unity の爪の画素 L 15,310・R 15,287 px。射線の検査の値は設計33 の numpy の再投影（骨格と一覧の中心線の対称 Hausdorff 中央値 0.62 px・最大 3.9 px）を引き継ぎ、Unity では測り直していない",
                        "verdict": "記録のみ"},
            },
        },
        "regression": {
            "rule_ja": "計画 §2.0：原画視点に爪を足したので評価器（ds30b_tstar_regress.py、設計29修正01 と同じ 3 つの読み）を回した",
            "t28_no_claws_identical_to_ds31": m3["regression"]["t28_white_identical_to_ds31"]["all"],
            "outline_claws_in_ids": {"78_130_131_px": [3.0289, 3.5131, 3.0431],
                                     "132_sigma12_max_px": reg["sets"]["t28_claws"]["lfgate"]["132_sigma12_max"],
                                     "72_sigma24_p95_px": reg["sets"]["t28_claws"]["lfgate"]["72_sigma24_p95"],
                                     "base_29r01": counts["outline"]["base_29r01"], "verdict": "後退なし（72 σ24 p95 は良くなった）"},
            "colour_sheet_without_claw_layer": {"verdict": "後退なし（爪なしの 10 枚が設計31 と SHA-256 まで同じ）",
                                                "reading": "採った読み（進行役の決定、Q24）"},
            "colour_claws_in_ids_sym_reading": {
                "rows": ct["rows"], "flat_266_267": ct["flat_266_267"],
                "pass_to_fail": ct["pass_to_fail_in_sym_reading"],
                "worse_but_pass": {"79": [crow[("79", "boundary")]["no_claws_px"], crow[("79", "boundary")]["claws_px"]],
                                   "270_boundary": [crow[("270", "boundary")]["no_claws_px"], crow[("270", "boundary")]["claws_px"]],
                                   "270_record_mizuiro_reading": [crow[("270", "record_mizuiro_reading")]["no_claws_px"], crow[("270", "record_mizuiro_reading")]["claws_px"]]},
                "reading": "記録のみ（限界。設計36・設計38・仕上げ33・仕上げ28 へ）",
            },
            "colour_claws_in_ids_definition_reading": {k: v for k, v in m3["regression"]["colour_items_with_claws_in_class_ids"]["items"].items()},
        },
        "decision": {
            "taken_ja": "色区の項目は、爪の層を除いたシートの色（爪なしの色区 ID）で測る読みを採り、爪を色区 ID に入れた両側の読みの 133・134・267 の合格 → 不合格は限界として記録する（Unity の部の推奨。進行役の決定、Q24。利用者の決定ではない）",
            "reason_ja": ["原画の爪は、29修正01 の焼き込みの色面の白と淡い水色の模様として、すでにシートに描かれている。設計33 の 3D の爪はその上に重なるので、評価器の色区の真値（爪の層を持たない）とは二重になる",
                          "爪の色（白と淡い水色の平塗り）と色区への当てはめは、設計36（限定色）と仕上げ33 で決める作業で、この番号の Q26 の 1 回の修正で先取りすると番号の順を崩す",
                          "輪郭の項目は爪を ID に入れても後退がない（72 は良くなる）"],
            "dropped_ja": ["爪を色区 ID に入れた読みを関門にして統合しないこと（計画 §2.0 の文言どおりの読み）。段階6 の Unity の再生の土台（設計35 の比較）が止まる",
                           "Q26 の 1 回の修正で、爪の色を下の色区の色に合わせるか、焼き込みの爪の模様を 3D の爪の所で消すこと。設計36 の作業の先取りになる"],
            "dissent_ja": "進行役の独立の検査は、この読みは設計31 の飛沫の除き方より弱いと述べた（飛沫が変えた画素は主に空 13,979／14,000 だが、爪は波の本体の上にあり、原画視点の色を本当に変える）。その指摘のとおり、爪の見え方の問題として設計36・38 へ渡す",
        },
        "revisions": {"count": 0, "ja": "受入のための修正は 0 回（Q26 の 1 回は使っていない）。作り手の開発中の直し 2 つ（確認用の視点を舷の外へ置き直して④を足した、入切の一覧のファイル名の重なり）は受入の値を決める前の検査の道具の直しで、数えない"},
        "independent": {"verdict": "pass（必須の指摘 0）", "summary": ic},
        "discrepancies_ja": [
            "Unity の部の README の作業時間 01:05〜02:55 は誤り。ファイルの時刻では開始 01:02:16（_started.txt）、再開 01:11:52、最後の出力 01:35:30（README）",
            "Unity の部の metrics.json の色区の表の『爪なし』の列は評価器の定義のままの読み（134 8.996 px 不合格など）で、設計29修正01 が採った両側の読み（134 0.634 px 合格）と混ざっている。両側の読みでは 133 と 134 の両方が合格 → 不合格",
            "両側の読みでは 267（白の平塗り）も、20 px 以上の白の帯が 0 → 49 になる（Unity の部と独立の検査の報告には出ていない。記録の時に tstar_sym.json から数えた）",
            "独立の検査の報告の作業時間 01:48〜02:10 に対し、ファイルの時刻では indep_check の作成 01:39:57、最後の出力 02:04:06",
            "独立の検査の報告の『±1 で 0.99〜4.9 px』は、ds34_indep_a1_sheet_line.json の平均の差の列では 0.992〜4.603 px。『±1 で約 130〜150 mm』は ds34_indep_a1_roots.json では 128.2〜152.9 mm",
            "独立の検査の報告の『25／25 で d＝0』は、ファイルでは 25 コマ（k 210〜354）のうち k 210〜348 の 24 コマで d＝0、k 354 は d＝−1（0.343 と 0.389 px で差 0.05 px）",
            "独立の検査の報告の『爪のコマの位相 ≤ 9.7e-5』は、記録の数え直し（|claw_frame − 30t| の最大）では 9.91e-5 コマ",
            "Unity の部の README の『原画視点では爪 286 px が船の後ろ（t 10〜11.5 s）』は、描画の報告では t 10 s の 127 px と t 10.5 s の 159 px だけ",
        ],
        "handoffs": {
            "設計35": "3 版の比較はこの場面（DS34_ThreeLayers）と DS34ClawPlayer・DS31InstancedParticles の上で行う。最大密度の性能の代理",
            "設計36": "爪の色（白と淡い水色の平塗り）を色区と焼き込みの模様に合わせ、爪を色区 ID に入れた読みの 133・134・267 を合格へ戻す。175 は仕上げ36",
            "設計38": "爪の縁の線（今は線なし）、空へ出る爪が唇の輪郭に作る白い欠け、148 の奥の線",
            "設計39": "評価器に飛沫と爪の層を分けるマスク（設計31 からの引き継ぎ。この番号は層の入切の 2 つの読みで代えた）",
            "仕上げ33": "爪の幅と色区への当てはめ、C072 の断面の回り（設計33 からの引き継ぎ）",
            "仕上げ28": "133・134 の項目の群（計画 §5）",
            "設計08〜10・PS VR2 の導入の後": "H1・H3・H4",
        },
        "time": {
            "limit_ja": "Q26 の日程で 3 時間。範囲は最小の受入だけで、修正は 1 回まで",
            "file_times": counts["file_times"],
            "unity_runs_s": {"main": 26, "video": 65, "toggles": 18, "playmode": 19, "evaluator": 221},
        },
    }
    jdump(EV + "/metrics.json", metrics)

    # ------------------------------------------------------------ run.json
    ev_files = sorted(os.listdir(EV))
    run = {
        "schema": "GreatWave.DS34.run/1",
        "number": "設計34",
        "tools": {"unity": r3["unity"], "device": r3["device"], "graphics_api": r3["graphics_api"],
                  "python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                  "pillow": Image.__version__, "ffprobe": FFPROBE},
        "commands_unity_part": r3["commands"],
        "commands_record": ["py -3.10 -B Tools/GWWaveGen/ds34/ds34_record.py"],
        "independent_check_ja": "進行役の独立の検査はリポジトリの外のコード。コードと出力の写しは Git 対象外の Unity/Build/Design/34/indep_check/（ic34_*.py・ic34_*.json）",
        "scene34_sha256": r3["scene34_sha256"],
        "protected_unchanged": r3["protected_unchanged"],
        "protected_files": r3["protected_files"],
        "inputs_sha256": r3["inputs_sha256"],
        "code_sha256": dict(r3["code_sha256"], **{"Tools/GWWaveGen/ds34/ds34_record.py": sha(REPO + "/Tools/GWWaveGen/ds34/ds34_record.py")}),
        "claw_frames_sha256_seen_by_unity": r3["claw_frames_sha256_seen_by_unity"],
        "spray_sha256_seen_by_unity": r3["spray_sha256_seen_by_unity"],
        "unity_part_outputs_sha256": {k: r3["outputs_sha256"][k] for k in r3["outputs_sha256"]
                                      if k.startswith("fig/") or k.startswith("video") or k in ("metrics.json", "main/ds30_tstar_regress.json", "main/ds34_render_report.json")},
        "unity_part_run_json_sha256": sha(U3 + "/run.json"),
        "figures": figs,
        "videos": vids,
        "json_copies": json_out,
        "evidence_sha256": {f: sha(EV + "/" + f) for f in ev_files if f not in ("run.json",)},
    }
    jdump(EV + "/run.json", run)

    # ------------------------------------------------------------ 確かめ
    bad = []
    for f in os.listdir(EV):
        p = EV + "/" + f
        if f.endswith(".png"):
            im = imread(p)
            if im.shape[:2] != (H, W):
                bad.append(f + " の大きさ " + str(im.shape[:2]))
        if f.endswith(".mp4") and os.path.getsize(p) > MP4_LIMIT:
            bad.append(f + " が 5 MB を超える")
    if bad:
        raise SystemExit("証拠の確かめで不合格: " + "; ".join(bad))
    print("DS34_RECORD_DONE evidence files", len(os.listdir(EV)), "flips_sym", ct["pass_to_fail_in_sym_reading"])


if __name__ == "__main__":
    main()
