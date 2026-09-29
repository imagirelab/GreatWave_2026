# -*- coding: utf-8 -*-
"""設計31 の記録：証拠（Docs/Evidence/Design/31/）を作り、metrics.json と run.json を書く。

値は、白の部（ds31_white.py・DS31Render・ds31_white_evidence.py）、飛沫の部（ds31_spray.py・ds31_spray_checks.py）、
進行役の独立の検査（リポジトリの外のコード。出力の写しは Git 対象外の Unity/Build/Design/31/indep_check/）の出力ファイルから読む。
この道具で新しく数えるのは次の 3 つだけ（どれも Unity の出力の画像・動画から。結果は Unity/Build/Design/31/record/ にも書く）。
  1) 飛沫を色区 ID に入れた t* の ID 画像で、飛沫が変えた画素のうち、飛沫なしの ID で空だった画素の数
  2) 原画の点（186 個）のうち、t* の飛沫なしの ID で空でない画素（主役波の前）に来る点の数
  3) 段階5確認の S5-1（コマ 184→185 の 1 コマの切り替わり）を、設計31 の左の側面の動画で数え直す（設計30 の証拠の動画と並べる）

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds31/ds31_record.py
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
B31 = os.path.join(REPO, "Unity", "Build", "Design", "31")
WH = os.path.join(B31, "white")
SP = os.path.join(B31, "spray")
UM = os.path.join(WH, "unity", "main")
IND = os.path.join(B31, "indep_check")
REC = os.path.join(B31, "record")
EV = os.path.join(REPO, "Docs", "Evidence", "Design", "31")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"


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


def jdump(o, p):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)
        f.write("\n")


def imread(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def imwrite(p, im):
    ok, buf = cv2.imencode(".png", im)
    assert ok
    buf.tofile(p)


def fit1080(im, label=None):
    """1920×1080 の枠に収める（縮尺だけ変える。余白は白）。label は下の余白に書く ASCII の説明。"""
    h, w = im.shape[:2]
    s = min(1920 / w, 1080 / h)
    if abs(s - 1) > 1e-9:
        im = cv2.resize(im, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_NEAREST)
    out = np.full((1080, 1920, 3), 255, np.uint8)
    h, w = im.shape[:2]
    out[:h, (1920 - w) // 2:(1920 - w) // 2 + w] = im
    if label and h < 1040:
        y = h + 36
        for line in label.split("\n"):
            cv2.putText(out, line, (24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (40, 40, 40), 2, cv2.LINE_AA)
            y += 38
    return out


def best_window(mask, ww, wh):
    ii = cv2.integral(mask.astype(np.uint8))
    H, W = mask.shape
    best, bx, by = -1, 0, 0
    for y in range(0, H - wh + 1, 20):
        for x in range(0, W - ww + 1, 20):
            c = ii[y + wh, x + ww] - ii[y, x + ww] - ii[y + wh, x] + ii[y, x]
            if c > best:
                best, bx, by = c, x, y
    return bx, by


def fig_152():
    """152 の見る図：飛沫あり（Unity、作品の色）の拡大（2 倍、最近傍）。左 原画視点 t 11.0 s、右 座席 t 11.5 s。"""
    tiles = []
    for name in ("painting_t11.0", "seat_t11.5"):
        on = imread(os.path.join(UM, "pairs", name + "_on.png"))
        off = imread(os.path.join(UM, "pairs", name + "_off.png"))
        m = (np.abs(on.astype(int) - off.astype(int)).max(-1) > 6)
        x, y = best_window(m, 480, 540)
        crop = cv2.resize(on[y:y + 540, x:x + 480], (960, 1080), interpolation=cv2.INTER_NEAREST)
        cv2.putText(crop, "%s  spray on  (Unity, x2 nearest, crop x%d y%d)" % (name, x, y), (12, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)
        tiles.append(crop)
    return np.hstack(tiles)


def ids_counts():
    """1) と 2)。ID の色は idmap.json（空 = 白 (255,255,255)）。"""
    idm = jload(os.path.join(UM, "t28_spray", "t28", "render", "idmap.json"))["classes"]
    sky = np.array(idm["sky"], np.uint8)[::-1]  # BGR
    a = imread(os.path.join(UM, "t28_white", "t28", "render", "af28r01_class_ids.png"))
    b = imread(os.path.join(UM, "t28_spray", "t28", "render", "af28r01_class_ids.png"))
    chg = np.any(a != b, -1)
    a_sky = np.all(a == sky, -1)
    tab = jload(os.path.join(SP, "ds31_spray_table.json"))["particles"]
    sx = a.shape[1] / 1920.0
    sy = a.shape[0] / 1080.0
    on_wave = []
    for p in tab:
        xi = int(np.clip(round(p["x_d"] * sx - 0.5), 0, a.shape[1] - 1))
        yi = int(np.clip(round(p["y_d"] * sy - 0.5), 0, a.shape[0] - 1))
        if not a_sky[yi, xi]:
            on_wave.append(p["dot_id"])
    return {
        "ids_size": [int(a.shape[1]), int(a.shape[0])],
        "spray_changed_id_px": int(chg.sum()),
        "spray_changed_id_px_on_sky": int((chg & a_sky).sum()),
        "spray_changed_id_px_on_wave": int((chg & ~a_sky).sum()),
        "dots_on_wave_at_tstar": len(on_wave),
        "dots_on_wave_ids": on_wave,
        "dots_total": len(tab),
        "note_ja": "t* の原画視点の色区 ID（3840×2160）。飛沫なし（t28_white）と飛沫あり（t28_spray）の違い。"
                   "点の位置は ds31_spray_table.json の x_d・y_d（表示 1920×1080）を ID の大きさへ直した画素の中心",
    }


def frames(video, n0, n1):
    cmd = [FFMPEG, "-v", "error", "-i", video, "-vf", "select=between(n\\,%d\\,%d)" % (n0, n1), "-vsync", "0",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    k = len(raw) // (1920 * 1080 * 3)
    return np.frombuffer(raw, np.uint8)[:k * 1920 * 1080 * 3].reshape(k, 1080, 1920, 3)


def s51():
    """3) S5-1：コマ n→n+1 の差（全画素の平均の絶対差、0〜255）と、どれかの色で差 > 16 の画素の数。"""
    out = {}
    vids = {
        "ds31_air_side_left": os.path.join(UM, "video", "ds31_air_side_left_30fps.mp4"),
        "ds30_side_left_evidence": os.path.join(REPO, "Docs", "Evidence", "Design", "30", "ds30_side_left_30fps.mp4"),
    }
    n0, n1 = 178, 191
    for key, v in vids.items():
        f = frames(v, n0, n1).astype(np.int16)
        rows = []
        for i in range(len(f) - 1):
            d = np.abs(f[i + 1] - f[i])
            rows.append({"from": n0 + i, "to": n0 + i + 1, "mean_abs": round(float(d.mean()), 3),
                         "px_gt16": int((d.max(-1) > 16).sum())})
        out[key] = {"video": rel(v), "sha256": sha(v), "rows": rows}
    out["note_ja"] = ("段階5確認の S5-1（コマ 184→185、t ≈ 6.17 s）。左の側面の動画のコマを ffmpeg で取り出し、隣のコマとの差を数えた。"
                      "ds31_air_side_left は設計31 の Unity の描画（作品の色、飛沫あり）、ds30_side_left_evidence は設計30 の証拠の動画")
    return out


def main():
    os.makedirs(EV, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    # ---- 入力 ----
    mw = jload(os.path.join(WH, "evidence", "metrics_white.json"))
    rw = jload(os.path.join(WH, "evidence", "run_white.json"))
    sc = jload(os.path.join(SP, "ds31_spray_checks.json"))
    sg = jload(os.path.join(SP, "ds31_spray_generate_log.json"))
    spk = jload(os.path.join(SP, "ds31_spray_package.json"))
    rr = jload(os.path.join(UM, "ds31_render_report.json"))
    tr = jload(os.path.join(UM, "ds30_tstar_regress.json"))
    cw = jload(os.path.join(IND, "chk_white.json"))
    c150 = jload(os.path.join(IND, "chk_150.json"))
    c150s = jload(os.path.join(IND, "chk_150_section.json"))
    c152 = jload(os.path.join(IND, "chk_152.json"))
    with open(os.path.join(IND, "emit2_out.txt"), encoding="utf-8") as f:
        emit2 = f.read().strip()

    # ---- この道具で数えるもの ----
    idc = ids_counts()
    jdump(idc, os.path.join(REC, "ds31_ids_spray_sky.json"))
    s5 = s51()
    jdump(s5, os.path.join(REC, "ds31_s51_frames.json"))

    # ---- 証拠：画像 ----
    pngs = {}

    def put_png(name, im, src):
        p = os.path.join(EV, name)
        imwrite(p, im)
        pngs[name] = {"source": src}

    put_png("ds31_painting_tstar_spray.png", imread(os.path.join(UM, "t28_spray", "t28", "render", "af28r01_painting.png")),
            "Unity/Build/Design/31/white/unity/main/t28_spray/t28/render/af28r01_painting.png（Unity、t*、飛沫あり。そのまま）")
    put_png("ds31_air_side_top_t11.png", imread(os.path.join(UM, "stills", "ds31_air_side_top_t11.00s.png")),
            "Unity/Build/Design/31/white/unity/main/stills/ds31_air_side_top_t11.00s.png（Unity、確認用の視点 side_top、t 11 s、作品の色。そのまま）")
    put_png("ds31_air_painting_t11.png", imread(os.path.join(UM, "stills", "ds31_air_painting_t11.00s.png")),
            "Unity/Build/Design/31/white/unity/main/stills/ds31_air_painting_t11.00s.png（Unity、原画視点、t 11 s、作品の色。そのまま）")
    put_png("fig_ds31_white_onset.png", imread(os.path.join(WH, "evidence", "fig_ds31_white_onset.png")),
            "Unity/Build/Design/31/white/evidence/fig_ds31_white_onset.png（numpy の白の割合と Unity の ID の数。そのまま）")
    for s, lab in (("gen", "gen: red = marks where the sheet has just turned white, magenta = spray (diagnostic colour)"),
                   ("adv", "adv: orange = marks carried with the sheet after turning white, magenta = spray (diagnostic colour)"),
                   ("air", "air: spray only, in the artwork colour (palette white)")):
        put_png("fig_ds31_%s_stills_sheet.png" % s,
                fit1080(imread(os.path.join(WH, "evidence", "fig_ds31_%s_stills_sheet.png" % s)),
                        "Unity 6000.4.3f1 PC offscreen (not HMD). rows: painting / seat / side_left / side_top, cols: t = 9, 10, 10.5, 11, 12 s\n" + lab),
                "Unity/Build/Design/31/white/evidence/fig_ds31_%s_stills_sheet.png（1920×864 を 1920×1080 の枠へ。縮尺は同じ）" % s)
    put_png("fig_ds31_spray_tstar_compare.png",
            fit1080(imread(os.path.join(SP, "fig", "fig_ds31_spray_tstar_compare.png")),
                    "numpy (not Unity). left: painting (Met JP1847), middle: 186 extracted white dots in the lip zone,\nright: numpy render of t* with spray v0 (42-vertex spheres, unlit)"),
            "Unity/Build/Design/31/spray/fig/fig_ds31_spray_tstar_compare.png（3240×1080 を縮めて枠へ）")
    put_png("fig_ds31_spray_stills.png",
            fit1080(imread(os.path.join(SP, "fig", "fig_ds31_spray_stills.png")),
                    "numpy (not Unity). top: painting view at tau = -1.0, -0.7, -0.45, -0.2, 0 s\nbottom: side cutaway of hero rows 100-190 with the spray paths drawn relative to the wave frame (diagnostic)"),
            "Unity/Build/Design/31/spray/fig/fig_ds31_spray_stills.png（5400×1560 を縮めて枠へ）")
    put_png("fig_ds31_152_crops.png", fig_152(),
            "Unity/Build/Design/31/white/unity/main/pairs/painting_t11.0_on.png・seat_t11.5_on.png（飛沫が変えた画素の最も多い 480×540 の窓を 2 倍に拡大、最近傍）")

    # ---- 証拠：動画・JSON の写し ----
    vids = {
        "ds31_grid_3x4_30fps.mp4": os.path.join(WH, "evidence", "ds31_grid_3x4_30fps.mp4"),
        "ds31_air_painting_30fps.mp4": os.path.join(UM, "video", "ds31_air_painting_30fps.mp4"),
        "ds31_air_side_top_30fps.mp4": os.path.join(UM, "video", "ds31_air_side_top_30fps.mp4"),
        "ds31_gen_painting_30fps.mp4": os.path.join(UM, "video", "ds31_gen_painting_30fps.mp4"),
        "ds31_adv_painting_30fps.mp4": os.path.join(UM, "video", "ds31_adv_painting_30fps.mp4"),
    }
    jsons = {
        "ds31_white_metrics.json": os.path.join(WH, "evidence", "metrics_white.json"),
        "ds31_white_run.json": os.path.join(WH, "evidence", "run_white.json"),
        "ds31_white_onset.json": os.path.join(WH, "ds31_white_onset.json"),
        "ds31_spray_checks.json": os.path.join(SP, "ds31_spray_checks.json"),
        "ds31_spray_generate_log.json": os.path.join(SP, "ds31_spray_generate_log.json"),
        "ds31_spray_package.json": os.path.join(SP, "ds31_spray_package.json"),
        "ds31_tstar_regress.json": os.path.join(UM, "ds30_tstar_regress.json"),
        "ds31_ids_spray_sky.json": os.path.join(REC, "ds31_ids_spray_sky.json"),
        "ds31_s51_frames.json": os.path.join(REC, "ds31_s51_frames.json"),
    }
    copied = {}
    for k, v in list(vids.items()) + list(jsons.items()):
        assert os.path.getsize(v) <= 5 * 1024 * 1024, v
        shutil.copyfile(v, os.path.join(EV, k))
        copied[k] = {"source": rel(v), "sha256": sha(v)}
    # Unity の報告は大きいので、要る所だけ抜き出す
    us = {k: rr[k] for k in ("unity", "device", "graphicsApi", "heroPkg", "heroTwhiteSha256", "scene31", "scene31Sha256", "noteJa",
                             "particles", "stereo", "videos", "shaderChecks", "protectedFiles", "changedFiles",
                             "protectedUnchanged", "shaderAllCompiled", "secondsTotal", "tauAtTStar")}
    us["source_ja"] = "Unity/Build/Design/31/white/unity/main/ds31_render_report.json（SHA-256 %s）から ids・alive・files の配列を除いて抜き出した" % sha(os.path.join(UM, "ds31_render_report.json"))
    jdump(us, os.path.join(EV, "ds31_unity_summary.json"))

    # ---- metrics.json ----
    b102 = mw["numpy"]
    b152 = mw["acceptance"]["152"]
    ids_p, ids_s = mw["ids"]["painting"], mw["ids"]["seat"]
    reg = mw["regression"]
    lf = reg["spray_in_ids_evaluator"]
    base = tr["base_29r01"]
    sb = sc["b150"]
    metrics = {
        "schema": "GreatWave.DS31.metrics/1",
        "number": "設計31",
        "title_ja": "主役波から少量の白波を出す（白の出現 T_white ＋ 飛沫 v0）",
        "generated_utc": now,
        "evidence_kind_ja": "numpy の生成器と検査（白の部・飛沫の部）、Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）、"
                            "美術優先28修正01 の評価器（29修正01・設計30 の読み）、進行役の独立の検査（作り手のコードを使わない numpy。リポジトリの外）。"
                            "HMD 実機の結果ではない。Play モードの描画は確かめていない",
        "acceptance": {
            "ja": "計画 §2.2 の設計31 の最小の受入（Q26：この番号は最小の受入だけを満たす）",
            "102": {
                "rule_ja": mw["acceptance"]["102"]["rule_ja"],
                "author_texel_max_increment": b102["texel_fraction_max_increment_per_frame"],
                "author_texel_max_increment_before_rate_cap": mw["rate_cap"]["before"]["texel_fraction_max_increment_per_frame"],
                "author_area_max_increment": b102["area_fraction_max_increment_per_frame"],
                "first_white_t_s": b102["first_white_t_exact"],
                "all_white_t_s": b102["all_white_t"],
                "never_white_turning_white_vertices": b102["never_white_vertices_turning_white"],
                "unity_ids_disp_white_final_not": [ids_p["disp_white_final_not_total"], ids_s["disp_white_final_not_total"]],
                "unity_ids_times": [ids_p["times"], ids_s["times"]],
                "independent_texel_bilinear_max_increment": cw["b102_texel_bilinear_new"]["max_inc"],
                "independent_frames_over_2pct": cw["b102_texel_bilinear_new"]["frames_over_2pct"],
                "independent_before_rate_cap": cw["b102_texel_bilinear_old"]["max_inc"],
                "verdict": "合格（ds31_white_rate_cap の後。これがこの番号の直しの 1 回）",
            },
            "176": {
                "rule_ja": mw["acceptance"]["176"]["rule_ja"],
                "value_ja": mw["acceptance"]["176"]["value_ja"],
                "independent": {"painting": cw["ids"]["painting"], "seat": cw["ids"]["seat"]},
                "verdict": "合格",
            },
            "150": {
                "rule_ja": "飛沫：水面へ引き戻されるもの 0",
                "spray_checks": {"pulled_back": sb["pulled_back"], "inside_water_any": sb["inside_water_any"],
                                 "never_separated": sb["never_separated"], "hz": sb["hz"],
                                 "min_clearance_after_sep_m": sb["min_clearance_after_sep_m"],
                                 "clearance_tstar_m": sb["clearance_tstar_m"]},
                "independent": {"distance_reading": c150, "section_polygon_reading": c150s},
                "note_ja": "独立の検査の最も近い三角形の符号の読みは 31・84 の 2 粒を水の側とした。どちらも最も近い点が網の頂点で符号が決まらない所で、"
                           "断面の多角形の内外の読み（120 Hz、20,602 の標本）では水の中の標本 0。描く半径（0.08 s で 0 から大きくなる）では距離が 0 以下にならない",
                "verdict": "合格（飛沫の部の検査 0、独立の検査の断面の読み 0）",
            },
            "152": {
                "rule_ja": b152["rule_ja"],
                "unity_pairs": {k: b152[k] for k in ("pairs", "changed_px", "dark_edge_px", "glow_px", "components", "components_ge64px",
                                                    "square_components", "fill_ratio_max", "fill_ratio_median")},
                "numpy_tstar": sc["b152"],
                "independent_unity": c152,
                "verdict": "合格（Unity の描画。numpy の描画でも 0）",
            },
            "video": {
                "rule_ja": "発生位置・移流・空中の粒子を動画で見せる",
                "value_ja": "Unity の動画 12 本（gen・adv・air × painting・seat・side_left・side_top、1920×1080、30 fps、421 コマ）と 3×4 の並べ動画。証拠には 5 本を写した",
                "videos": [{"set": v["set"], "view": v["view"], "frames": v["frames"], "fps": v["fps"], "sha256": v["sha256"]} for v in rr["videos"]],
                "verdict": "合格（PC の描画。左の側面では空中の飛沫は見えない）",
            },
            "regression_2_0": {
                "rule_ja": "計画 §2.0：原画視点の回帰がない（段階5確認 §6.3：直前の番号と CP1 の両方で書く）",
                "vs_ds30": {"t28_white_identical_all10": reg["white_identical_all10"],
                            "independent_identical": cw["regress_t28_white_vs_d30"]},
                "values_same_as_ds30_29r01": {"78_130_131_px": [base["silhouettes_vs_kstar_prime"]["rows"][k]["unity_max_px"] for k in ("78", "130", "131")],
                                              "132_sigma12_max_px": base["lfgate"]["132_sigma12_max"],
                                              "72_sigma24_p95_px": base["lfgate"]["72_sigma24_p95"],
                                              "colour_worst_abs_diff_px": base["colour_worst_abs_diff_px"],
                                              "sym_worst_abs_diff_px": base["sym_worst_abs_diff_px"]},
                "vs_cp1_ja": "段階5確認の記録 §6.3 の表のまま（t* の画像が設計30 と同じなので）：78／130／131 1.64／1.95／1.80 → 3.03／3.51／3.04 px、"
                             "132 1.57 → 細部込み 5.95・σ12 3.7552 px、72 p95 1.72 → 細部込み 8.75・σ24 4.0075 px、134・267 合格 → 不合格。設計31 による後退はない",
                "spray_in_ids_record": {"lfgate": lf["lfgate"], "lfgate_diff_vs_29r01_px": lf["lfgate_diff_vs_29r01_px"],
                                        "silhouette_diff_vs_29r01_px": lf["silhouette_diff_vs_29r01_px"],
                                        "colour_worst_abs_diff_px": lf["colour_worst_abs_diff_px"],
                                        "sym_worst_diff_vs_29r01_px": lf["sym_worst_diff_vs_29r01_px"],
                                        "ids_spray_sky": idc},
                "verdict": "合格（採った読み：飛沫の層を色区 ID に入れない。設計30 と画素まで同じ）。飛沫を ID に入れた読みでは 132・72 が約 +123／+119 px（評価器が空の中の飛沫の点を輪郭と読む。記録のみ）",
            },
        },
        "design": {
            "white": {
                "twhite_file": "Unity/Build/Design/31/white/ds31_twhite_r32f.bin",
                "twhite_sha256": mw["rate_cap"]["sha256"],
                "twhite_source_sha256": rw["inputs"]["twhite_sha256"],
                "rate_cap": mw["rate_cap"],
                "onset": mw["onset"],
                "marks": {k: {kk: mw["marks"][k][kk] for kk in ("count", "frames", "sha256", "note_ja")} for k in ("born", "trace")},
                "carry_m": {"median": mw["marks"]["trace"]["carry_m_median"], "min": mw["marks"]["trace"]["carry_m_min"], "max": mw["marks"]["trace"]["carry_m_max"]},
            },
            "spray": {
                "params": sg["params"],
                "extract": sg["extract"], "place": sg["place"], "emit": sg["emit"],
                "ballistic": sc["ballistic"], "reprojection_tstar_px": sc["reprojection_tstar_px"],
                "package": {k: spk[k] for k in ("count", "eval_ja", "inst_sha256", "knots_sha256", "knots_hermite_vs_analytic_max_m",
                                                "mesh_vertices", "mesh_triangles", "colour_srgb8", "colour_source", "render_ja")},
                "frames_sha256": sg["outputs"]["ds31_spray_frames.bin"],
            },
            "unity": {k: us[k] for k in ("particles", "shaderAllCompiled", "protectedUnchanged", "secondsTotal", "scene31", "scene31Sha256")},
        },
        "backlog": {
            "ja": "計画 §2.2 の設計31：102・135・176・177（引き継ぎ）、149〜152（使える水準）",
            "items": {
                "102": {"value_ja": mw["acceptance"]["102"]["value_ja"], "verdict": "合格"},
                "135": {"value_ja": "この番号では測り直していない。美術優先31 の値（上側から船側へ、順位相関 0.988）は古い動き（美術優先30）のもの。"
                                    "今の T_white は唇の上面（区間 1）で最初に白くなる（t 5.80 s）", "verdict": "記録のみ（仕上げ31 で今の動きで測る）"},
                "176": {"value_ja": mw["acceptance"]["176"]["value_ja"], "verdict": "合格"},
                "177": {"value_ja": "この番号では測り直していない。176 の Unity の ID の連続で、白でない色区の表示は全 64 時刻で終態と同じ（縞の色は UV に付いている）。"
                                    "同じ縞が同じ水面とともに上がるかの高さの測りはしていない", "verdict": "記録のみ（仕上げ31）"},
                "149": {"value": sc["b149_record"], "verdict": "記録（放出の 0.2 s 後の隙間の最小 %.3f m。隙間が見えるかは動画で）" % sc["b149_record"]["dist_gap_0p2s_m"]["min"]},
                "150": {"verdict": "合格（0）"},
                "151": {"value": sc["b151_record"], "verdict": "記録のみ（ΔE00 の中央値 %.2f、p90 %.2f、最大 %.1f。≤5 は全部では満たさない。仕上げ31・設計36）" % (
                    sc["b151_record"]["dE00_median"], sc["b151_record"]["dE00_p90"], sc["b151_record"]["dE00_max"])},
                "152": {"verdict": "合格（Unity の描画で 0）"},
            },
        },
        "record_only": {
            "vertex_count_reading_102": {"value": b102["vertex_fraction_max_increment_per_frame"],
                                         "note_ja": b102["note_vertex_ja"] + "。独立の検査も同じ値（%.4f）" % cw["b102_vertex_count"]["max_inc"]},
            "never_white_texels": {"value": b102["texel_never_white_by_tstar"], "of": b102["texel_white_final"],
                                   "note_ja": "終態の白のテクセルのうち t* までに白にならない数（独立の検査も同じ数）。主役波のパッケージからの引き継ぎ。t = 12 s の原画視点・座席の ID では表示の白と終態の白が同じ"},
            "emitters_on_non_white": {"value_ja": emit2, "classes_ja": "1 = 淡い水色、2 = 藍中、3 = 藍濃（af31_white.py の CLASS_NAMES の順）",
                                      "note_ja": "飛沫の放出点の頂点のうち、29修正01 の色面で終態が白でないもの。τ_e ≥ T_white の条件はこれらの頂点では意味がない（白にならないので）。"
                                                 "進行役の独立の検査（Unity/Build/Design/31/indep_check/emit2_out.txt）"},
            "spray_count": {"value": sg["emit"]["ballistic"] + sg["emit"]["f8"], "plan": "2〜3 千個",
                            "instancing_drawn": {p["name"]: p["count"] for p in rr["particles"]}},
            "dots_on_wave_at_tstar": {"value": idc["dots_on_wave_at_tstar"], "of": idc["dots_total"]},
            "mock_stereo": mw["acceptance"]["mock_stereo_record"],
            "s5_1": s5,
            "play_mode": "Play モードの描画（Update の DrawMeshInstancedProcedural）は確かめていない。Play モードは 30 Hz のコマの間を線形に補う",
            "player_build_shader": "DS31InstancedParticles はシェーダーを Shader.Find で探し、材質の資産から参照していない。PC ビルドでシェーダーが除かれないかは確かめていない（設計34・47）",
            "hmd": "保留（PS VR2 の導入は利用者の手。SPI のキーワードでのコンパイルと Mock の両眼だけ）",
        },
        "revisions": {
            "fix1_ja": "直し1（Q26 の 1 回）：102 の目安（1 コマ ≤ 2%%）を満たすため、名前の付いた誘導 ds31_white_rate_cap で主役波の T_white を早める向きだけに付け替えた（%d 頂点、最大 %.3f s）。前 %.2f%% → 後 %.2f%%" % (
                mw["rate_cap"]["vertices_moved"], mw["rate_cap"]["t_shift_max_s"],
                100 * mw["rate_cap"]["before"]["texel_fraction_max_increment_per_frame"], 100 * b102["texel_fraction_max_increment_per_frame"]),
            "spray_internal_ja": "飛沫の部の作る途中の直し（値を決める前）：水の側の読みを符号から半直線の偶奇に変えた（唇の折り返しで符号が誤る）。"
                                 "偶奇で残った放出の直後の 1〜2 mm のかすめ 3 粒を、放出点を空気の側へ（半径 + 0.01 m）離して消した。直しの 2 回目はない",
        },
        "independent": {
            "files": {k: "Unity/Build/Design/31/indep_check/" + k for k in ("chk_white.json", "chk_150.json", "chk_150_section.json", "chk_152.json", "emit2_out.txt")},
            "ja": "進行役の独立の検査。コードは会話の作業フォルダー（リポジトリの外）。Unity は走らせていない。git は使っていない",
        },
        "discrepancies_ja": [
            "ds31_white_rate_cap で動いた頂点：白の部の記録 %d、独立の検査 %d（比べ方の違い。原因は確かめていない）" % (mw["rate_cap"]["vertices_moved"], cw["retime_vertices_moved"]),
            "rate_cap の目標は 1.8%%（cap %.3f）だが、テクセルの読みの結果は %.2f%%（白の部）・%.2f%%（独立の検査の双一次の読み）。判定の目安 2%% の内" % (
                mw["rate_cap"]["cap"], 100 * b102["texel_fraction_max_increment_per_frame"], 100 * cw["b102_texel_bilinear_new"]["max_inc"]),
            "最初の白：numpy は t %.3f s、Unity の ID は t %.2f s（ID は 0.25 s おきの時刻なので）" % (b102["first_white_t_exact"], ids_p["first_white_t"]),
            "150 の離れた後の最小の距離：飛沫の部 %.3f m（離れた＝半径 + 0.10 m）、独立の検査 %.4f m（離れた＝半径 + 0.02 m）。定義の違い" % (
                sb["min_clearance_after_sep_m"], c150["min_clearance_after_separation_m"]),
            "離れるまでの時間の最大：150 の検査 %.3f s、149 の記録 %.3f s（生成器の読み）" % (sb["sep_after_s"]["max"], sc["b149_record"]["sep_after_s_max"]),
            "DS31Render.cs の説明は実行の手順を run_ds31_unity.ps1 と書くが、ファイルは run_ds31w_unity.ps1",
            "ds31_spray.py の冒頭の説明は放出の候補の確かめを 120 Hz と書くが、生成の記録の値（params.check_hz）は %.0f Hz" % sg["params"]["check_hz"],
            "作業の指示の白の部の要約は開始を 18:34 とするが、最初のフォルダー（Unity/Build/Design/31）の作成は 18:36:47",
        ],
        "decision": {
            "adopted_ja": "白の出現は主役波のパッケージの T_white（物理の時刻）に ds31_white_rate_cap を掛けたもの。飛沫 v0 は原画の唇の前の区域の白い点 186 個を射線の上の 0.5〜3 m の層へ置き、"
                          "逆弾道で唇の頂点から出す。描画は光を使わない不透明の単色の小球（42 頂点）の instancing。原画視点の回帰は飛沫を色区 ID に入れない読みで測る",
            "dropped_ja": "(1) 飛沫を ID に入れた読みで回帰を判定する：評価器が空の中の点を輪郭と読むので採らない（評価器の飛沫の層のマスクは設計34・39 か仕上げ）。"
                          "(2) 102 を頂点の数で読む：唇の帯の列が 2 cm おきに詰まっているので面の広がりにならない（記録のみ）。"
                          "(3) 飛沫の区域を空全体・波の面へ広げる：波の面の白い点は 29修正01 の色面にある。区域の外は仕上げ31。"
                          "(4) 放出点を終態が白の頂点に限る：見つけたのは独立の検査の後で、Q26 の直しの 1 回は 102 に使ったので、仕上げ31 へ",
        },
        "handoffs": {
            "polish31_ja": "放出点を終態が白の頂点・テクセルに限る、点の抽出を手の注記と照合する、区域の外の点（右上の空・左の波・船の近く）、ΔE00（151）、135・177 を今の動きで測る、飛沫の大小と分布",
            "design32_33_ja": "発生の表（ds31_white_onset、27,027 記録）は爪の根元の候補。唇の塊の前に来る点は設計33 の爪ができるまで青の上の白い点に見える",
            "design34_39_ja": "評価器に飛沫の層を除くマスク。設計34 は 3 層を一つの時計で（飛沫は解析式を推奨）。設計39 の小飛沫で数を 2〜3 千個へ",
            "polish30_ja": "S5-1（コマ 184→185 の切り替わり）は設計31 の描画にも残る（ds31_s51_frames.json）",
            "hmd_ja": "設計08〜10（PS VR2 の導入の後）。ステレオ（SPI）・実時間の再生・Play モードの描画は未検証",
        },
        "time": {"limit_h": 3,
                 "ja": "Q26 の日程で 3 時間（計画 §2.6 の Q26 の表）。ファイルの時刻で 9/29 18:36:47（Unity/Build/Design/31 の作成）〜19:26:41（白の部の最後）、"
                       "独立の検査 19:29〜19:40、記録は 19:42〜。上限の内。Unity の 1 回は DS31Render の中の時間で %.1f s" % rr["secondsTotal"]},
    }
    jdump(metrics, os.path.join(EV, "metrics.json"))

    # ---- run.json ----
    ev_files = sorted(os.listdir(EV))
    scripts = sorted([os.path.join(HERE, f) for f in os.listdir(HERE) if f.endswith((".py", ".ps1"))])
    unity_src = []
    for root, _, fs in os.walk(os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design31")):
        unity_src += [os.path.join(root, f) for f in fs]
    unity_src.append(os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design31.meta"))
    run = {
        "schema": "GreatWave.DS31.run/1",
        "number": "設計31",
        "generated_utc": now,
        "machine": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "unity": "6000.4.3f1（Editor batchmode、PC オフスクリーン描画、RTX 3080、Direct3D11）",
        "ffmpeg": FFMPEG,
        "commands": [
            "（白の部）py -3.10 Tools/GWWaveGen/ds31/ds31_white.py（出力 Unity/Build/Design/31/white。--rate-cap 0 で誘導を切る）",
            "（飛沫の部）py -3.10 Tools/GWWaveGen/ds31/ds31_spray.py（出力 Unity/Build/Design/31/spray。白の部の ds31_twhite_r32f.bin を読む）",
            "（飛沫の部）py -3.10 Tools/GWWaveGen/ds31/ds31_spray_checks.py（出力 spray/ds31_spray_checks.json と fig/）",
        ] + ["（白の部）" + c for c in rw["commands"][1:2]] + [
            "（白の部、飛沫を色区 ID に入れた読みの記録）py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/31/white/unity/main --sets t28_spray（設計30 の道具。出力 ds30_tstar_regress.json）",
        ] + ["（白の部）" + c for c in rw["commands"][2:]] + [
            "（進行役の独立の検査：リポジトリの外の numpy。出力の写しは Unity/Build/Design/31/indep_check/）",
            "（記録）py -3.10 -B Tools/GWWaveGen/ds31/ds31_record.py",
        ],
        "scripts": {rel(p): sha(p) for p in scripts},
        "unity_sources": {rel(p): sha(p) for p in sorted(unity_src)},
        "inputs": {
            "white": rw["inputs"],
            "spray": sg["inputs"],
            "spray_code_sha256_at_generate": sg["code_sha256"],
            "stage5_selfreview": {"file": "Docs/Progress/Stage5_SelfReview_ja.md", "sha256": sha(os.path.join(REPO, "Docs", "Progress", "Stage5_SelfReview_ja.md"))},
        },
        "build_outputs": {
            "white/ds31_twhite_r32f.bin": sha(os.path.join(WH, "ds31_twhite_r32f.bin")),
            "spray/ds31_spray_inst_f32.bin": sha(os.path.join(SP, "ds31_spray_inst_f32.bin")),
            "spray/ds31_spray_knots_f32.bin": sha(os.path.join(SP, "ds31_spray_knots_f32.bin")),
            "spray/ds31_spray_frames.bin": sha(os.path.join(SP, "ds31_spray_frames.bin")),
            "spray/ds31_sphere42.obj": sha(os.path.join(SP, "ds31_sphere42.obj")),
            "white/ds31_marks_born.bin": sha(os.path.join(WH, "ds31_marks_born.bin")),
            "white/ds31_marks_trace.bin": sha(os.path.join(WH, "ds31_marks_trace.bin")),
            "white/unity/main/ds31_render_report.json": sha(os.path.join(UM, "ds31_render_report.json")),
            "indep_check": {f: sha(os.path.join(IND, f)) for f in sorted(os.listdir(IND))},
            "record": {f: sha(os.path.join(REC, f)) for f in sorted(os.listdir(REC))},
        },
        "evidence": {f: sha(os.path.join(EV, f)) for f in ev_files if f not in ("run.json",)},
        "evidence_sources": {**pngs, **copied, "ds31_unity_summary.json": {"source": rel(os.path.join(UM, "ds31_render_report.json"))}},
        "protected_ja": "DS31Render の報告で protectedUnchanged = %s（設計30 の場面・スクリプトなど %d 件）" % (rr["protectedUnchanged"], len(rr["protectedFiles"])),
        "not_in_repo_ja": "パッケージの大きなファイル、Unity の描画の全出力（Unity/Build/Design/31/white/unity/main）、試しの出力（white/_tests、spray/_work）、"
                          "独立の検査のコード（リポジトリの外）と出力の写し（Unity/Build/Design/31/indep_check）は Git 対象外。"
                          "爪形分析・参照モデル・利用者の解算は使っていない",
    }
    jdump(run, os.path.join(EV, "run.json"))
    print("DS31_RECORD_DONE", len(os.listdir(EV)), "files")
    print(json.dumps({"ids": {k: v for k, v in idc.items() if k != "dots_on_wave_ids"}, "s51": {k: s5[k]["rows"] for k in s5 if k != "note_ja"}}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
