# -*- coding: utf-8 -*-
"""設計34 Unity の部：Unity の採取（DS34Render・DS34PlayModeCheck）の出力から、図・並べ動画・metrics.json・run.json を作る。

入力（Git 対象外、Unity/Build/Design/34/unity3/）：
  main/ds34_render_report.json（採取の報告）、main/ds30_tstar_regress.json（評価器。ds30b_tstar_regress.py --sets t28_claws,t28_white）、
  main/{stills,toggles,occl,stereo}/、video_run/video/*.mp4、playmode/ds34_playmode.csv と画像。
出力（同じフォルダー）：fig/fig_ds34_*.png、video/ds34_layers_2x2_*_30fps.mp4、metrics.json、run.json。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds34/ds34u3_evidence.py
Unity の描画を読むだけで、3 層の中身（設計31・33 の出力）は変えない。
"""
import csv
import hashlib
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
U3 = os.path.join(REPO, "Unity", "Build", "Design", "34", "unity3")
MAIN = os.path.join(U3, "main")
FIG = os.path.join(U3, "fig")
VID = os.path.join(U3, "video")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = cv2.FONT_HERSHEY_SIMPLEX


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def rd(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def wr(p, im):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    ok, buf = cv2.imencode(".png", im)
    buf.tofile(p)
    return p


def label(im, text, org=(12, 34), scale=0.9):
    cv2.putText(im, text, org, FONT, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(im, text, org, FONT, scale, (255, 255, 255), 2, cv2.LINE_AA)
    return im


def fit(im, w, h):
    return cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)


def fig_toggles(rep):
    out = []
    for view in ("painting", "seat"):
        for t in ("11.50", "12.00"):
            tiles = []
            for tag, name in (("W0C0S0", "none"), ("W1C0S0", "white band"), ("W0C1S0", "claws"), ("W0C0S1", "spray"),
                              ("W1C1S0", "white+claws"), ("W1C0S1", "white+spray"), ("W0C1S1", "claws+spray"), ("W1C1S1", "all 3 layers")):
                p = os.path.join(U3, "toggles_run", "toggles", "ds34_%s_%s_t%ss.png" % (tag, view, t))
                im = fit(rd(p), 480, 270)
                tiles.append(label(im, name, (8, 26), 0.7))
            g = np.vstack([np.hstack(tiles[:4]), np.hstack(tiles[4:])])
            g = cv2.copyMakeBorder(g, 44, 0, 0, 0, cv2.BORDER_CONSTANT, value=(40, 40, 40))
            label(g, "DS34 layer toggles (Unity, %s view, t = %s s). white band = sheet colour (T_white), claws = combined mesh, spray = instancing" % (view, t), (10, 30), 0.62)
            out.append(wr(os.path.join(FIG, "fig_ds34_toggles_%s_t%s.png" % (view, t.replace(".", "p"))), g))
    return out


def fig_stills():
    ts = ("08.00", "10.00", "11.00", "12.00")
    rows = []
    for view in ("painting", "seat", "seat_low", "seat_toward_wave"):
        rows.append(np.hstack([label(fit(rd(os.path.join(MAIN, "stills", "ds34_all_%s_t%ss.png" % (view, t))), 480, 270), "%s t %s s" % (view, t), (8, 26), 0.6) for t in ts]))
    return wr(os.path.join(FIG, "fig_ds34_stills_sheet.png"), np.vstack(rows))


def crop_box(mask, pad=90, W=1920, H=1080, minw=320):
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    half = max(minw // 2, (x1 - x0) // 2 + pad, int(((y1 - y0) // 2 + pad) * 16 / 9))
    half = min(half, W // 2)
    hh = int(half * 9 / 16)
    x0 = int(np.clip(cx - half, 0, W - 2 * half)); y0 = int(np.clip(cy - hh, 0, H - 2 * hh))
    return x0, y0, 2 * half, 2 * hh


def fig_occlusion(rep):
    occ = rep["occlusion"]
    cand = [o for o in occ if o["hiddenByBoat"] > 0 and o["t"] in (10.0, 11.0, 12.0)]
    # 視点と層ごとに、船に隠された画素の最も多い時刻を 1 つ
    best = {}
    for o in cand:
        k = (o["view"], o["layer"])
        if k not in best or o["hiddenByBoat"] > best[k]["hiddenByBoat"]:
            best[k] = o
    order = sorted(best.values(), key=lambda o: (o["view"] != "painting", o["layer"], -o["hiddenByBoat"]))
    rows = []
    for o in order[:6]:
        base = os.path.join(MAIN, "occl", "%s_%s_t%04.1f" % (o["view"], o["layer"], o["t"]))
        col, full, nob, beh = rd(base + "_colour.png"), rd(base + "_full.png"), rd(base + "_noboat.png"), rd(base + "_behind.png")
        m = beh[:, :, 0] > 127
        x, y, w, h = crop_box(m)
        ov = full.copy()
        ov[m] = (0.35 * ov[m] + 0.65 * np.array([0, 0, 255])).astype(np.uint8)
        tiles = [col, nob, full, ov]
        names = ["colour (all layers)", "no boat: %s in diag colour" % o["layer"], "with boat (diag)", "red = hidden by boat (%d px), leak %d" % (o["hiddenByBoat"], o["leak"])]
        row = np.hstack([label(fit(im[y:y + h, x:x + w], 480, 270), n, (8, 24), 0.55) for im, n in zip(tiles, names)])
        row = cv2.copyMakeBorder(row, 30, 0, 0, 0, cv2.BORDER_CONSTANT, value=(40, 40, 40))
        label(row, "%s view, %s, t %.1f s" % (o["view"], o["layer"], o["t"]), (8, 22), 0.6)
        rows.append(row)
    return wr(os.path.join(FIG, "fig_ds34_occlusion_boat.png"), np.vstack(rows)), [(o["view"], o["layer"], o["t"]) for o in order[:6]]


def fig_stereo(rep):
    st = {(s["view"], s["t"]): s for s in rep["stereo"]}
    rows = []
    for view in ("seat", "painting"):
        for t in (11.0, 12.0):
            s = st[(view, t)]
            L = rd(os.path.join(MAIN, "stereo", "%s_t%04.1f_L.png" % (view, t)))
            R = rd(os.path.join(MAIN, "stereo", "%s_t%04.1f_R.png" % (view, t)))
            Ld = rd(os.path.join(MAIN, "stereo", "%s_t%04.1f_L_clawdiag.png" % (view, t)))
            Rd = rd(os.path.join(MAIN, "stereo", "%s_t%04.1f_R_clawdiag.png" % (view, t)))
            tiles = [label(fit(L, 480, 270), "L", (8, 26), 0.7), label(fit(R, 480, 270), "R", (8, 26), 0.7),
                     label(fit(Ld, 480, 270), "L claws %d px" % s["clawPxL"], (8, 26), 0.6),
                     label(fit(Rd, 480, 270), "R claws %d px" % s["clawPxR"], (8, 26), 0.6)]
            row = np.hstack(tiles)
            row = cv2.copyMakeBorder(row, 30, 0, 0, 0, cv2.BORDER_CONSTANT, value=(40, 40, 40))
            label(row, "Mock two-eye (IPD 64 mm), %s view, t %.0f s: claw px L/R diff %.2f %%, spray %.2f %%" % (view, t, 100 * s["clawRelDiff"], 100 * s["sprayRelDiff"]), (8, 22), 0.6)
            rows.append(row)
    return wr(os.path.join(FIG, "fig_ds34_mock_stereo.png"), np.vstack(rows))


def fig_timing(rep, play):
    """OpenCV だけで描く（この環境の Python に matplotlib はない）。上：根元とシートの距離（対数）、下：層ごとのコマのずれ。"""
    T = rep["timing"]
    W, H = 1920, 1080
    im = np.full((H, W, 3), 255, np.uint8)
    # 上の図：x = コマ 0〜420、y = log10(mm) の −4〜3
    x0, x1, y0, y1 = 120, 1880, 70, 560
    X = lambda k: int(x0 + (x1 - x0) * k / 420.0)
    Y = lambda mm: int(y1 - (y1 - y0) * (math.log10(max(mm, 1e-4)) + 4.0) / 7.0)
    cv2.rectangle(im, (x0, y0), (x1, y1), (0, 0, 0), 1)
    for e in range(-4, 4):
        yy = Y(10.0 ** e)
        cv2.line(im, (x0, yy), (x1, yy), (220, 220, 220), 1)
        cv2.putText(im, "1e%d mm" % e, (10, yy + 5), FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    for kk in range(0, 421, 60):
        cv2.putText(im, str(kk), (X(kk) - 10, y1 + 22), FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(im, (X(360), y0), (X(360), y1), (0, 160, 0), 1)
    cv2.line(im, (x0, Y(1.0)), (x1, Y(1.0)), (0, 0, 0), 2)
    def poly(vals, col, th):
        pts = np.array([[X(k), Y(v)] for k, v in vals if not (isinstance(v, float) and math.isnan(v))], np.int32)
        cv2.polylines(im, [pts], False, col, th, cv2.LINE_AA)
    poly([(r["k"], r["rootMaxPrevMm"]) for r in T[1:]], (0, 0, 230), 1)
    poly([(r["k"], r["rootMaxNextMm"]) for r in T[:-1]], (200, 0, 200), 1)
    poly([(r["k"], r["rootMaxMm"]) for r in T], (200, 60, 0), 2)
    for i, (txt, col) in enumerate([("same frame k: max over 148 claws |root(k) - sheet point(k)| (Unity GPU readback of the hero sheet)", (200, 60, 0)),
                                    ("control: claws one frame early (k-1) against the sheet at k", (0, 0, 230)),
                                    ("control: claws one frame late (k+1) against the sheet at k", (200, 0, 200)),
                                    ("1 mm (backlog 105);  green line = t* (frame 360)", (0, 0, 0))]):
        cv2.putText(im, txt, (x0 + 10, y0 + 22 + 22 * i), FONT, 0.55, col, 1, cv2.LINE_AA)
    cv2.putText(im, "DS34 one clock (Unity capture, 421 frames, t = k/30 s)", (x0, 45), FONT, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    # 下の図：ずれ（コマ）。±1e-4 コマの帯
    y2, y3 = 650, 1000
    cv2.rectangle(im, (x0, y2), (x1, y3), (0, 0, 0), 1)
    Z = lambda d: int((y2 + y3) / 2 - (y3 - y2) / 2 * max(-1.0, min(1.0, d / 1e-4)))
    for d, t in ((1e-4, "+1e-4"), (0.0, "0"), (-1e-4, "-1e-4")):
        cv2.putText(im, t, (40, Z(d) + 5), FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    for r in T:
        cv2.circle(im, (X(r["k"]), Z(r["clawFrame"] - r["k"])), 2, (200, 60, 0), -1)
        cv2.circle(im, (X(r["k"]), Z(r["sprayFrame"] - r["k"]) + 4), 1, (0, 0, 230), -1)
    if play:
        pts = np.array([[X(min(420.0, float(r["t"]) * 30)), Z((float(r["claw_t"]) - float(r["t"])) * 30) - 4] for r in play], np.int32)
        cv2.polylines(im, [pts], False, (0, 150, 0), 1, cv2.LINE_AA)
    mc = max(abs(r["clawFrame"] - r["k"]) for r in T); ms = max(abs(r["sprayFrame"] - r["k"]) for r in T)
    pm = max(abs(float(r["claw_t"]) - float(r["t"])) * 30 for r in play) if play else float("nan")
    for i, (txt, col) in enumerate([("capture: claw frame - k (max %g)" % mc, (200, 60, 0)), ("capture: spray frame - k (max %g, drawn 4 px lower)" % ms, (0, 0, 230)),
                                    ("Play mode (Editor, dt 0.02 s, %d frames): (claw t - t) x 30, max %.1e frames (float GWClock), drawn 4 px higher" % (len(play), pm), (0, 150, 0))]):
        cv2.putText(im, txt, (x0 + 10, y2 + 22 + 22 * i), FONT, 0.55, col, 1, cv2.LINE_AA)
    cv2.putText(im, "layer frame offsets (frames)", (x0, y2 - 12), FONT, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
    return wr(os.path.join(FIG, "fig_ds34_one_clock.png"), im)


def fig_colour133():
    w = rd(os.path.join(MAIN, "t28_white", "t28", "render", "af28r01_class_ids.png"))
    c = rd(os.path.join(MAIN, "t28_claws", "t28", "render", "af28r01_class_ids.png"))
    pw = rd(os.path.join(MAIN, "t28_white", "t28", "render", "af28r01_painting.png"))
    pc = rd(os.path.join(MAIN, "t28_claws", "t28", "render", "af28r01_painting.png"))
    x, y, r = 751, 188, 120   # 評価器の 133 の最悪の点（表示の画素）
    X, Y = 2 * x, 2 * y
    t = [w[Y - 2 * r:Y + 2 * r, X - 2 * r:X + 2 * r], c[Y - 2 * r:Y + 2 * r, X - 2 * r:X + 2 * r],
         cv2.resize(pw[y - r:y + r, x - r:x + r], (4 * r, 4 * r), interpolation=cv2.INTER_NEAREST),
         cv2.resize(pc[y - r:y + r, x - r:x + r], (4 * r, 4 * r), interpolation=cv2.INTER_NEAREST)]
    names = ["class ID, no claws", "class ID, claws", "colour, no claws", "colour, claws"]
    tiles = []
    for im, n in zip(t, names):
        im = im.copy()
        cv2.circle(im, (2 * r, 2 * r), 10, (255, 0, 255), 2)
        tiles.append(label(fit(im, 480, 480), n, (8, 26), 0.7))
    g = np.hstack(tiles)
    g = cv2.copyMakeBorder(g, 34, 0, 0, 0, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    label(g, "item 133 worst point (display 751,188): claws' white/mizuiro drawn over the painted white/mizuiro pattern (record only)", (8, 24), 0.6)
    return wr(os.path.join(FIG, "fig_ds34_colour133_claws.png"), g)


def grid_videos():
    os.makedirs(VID, exist_ok=True)
    out = []
    for view in ("painting", "seat"):
        ins = [os.path.join(U3, "video_run", "video", "ds34_%s_%s_30fps.mp4" % (s, view)) for s in ("white", "claws", "spray", "all")]
        o = os.path.join(VID, "ds34_layers_2x2_%s_30fps.mp4" % view)
        fc = ("[0:v]scale=960:540[a];[1:v]scale=960:540[b];[2:v]scale=960:540[c];[3:v]scale=960:540[d];"
              "[a][b]hstack[t];[c][d]hstack[u];[t][u]vstack[v]")
        cmd = [FFMPEG, "-y", "-loglevel", "error"] + sum([["-i", p] for p in ins], []) + ["-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", o]
        subprocess.run(cmd, check=True)
        out.append(o)
    return out


def main():
    os.makedirs(FIG, exist_ok=True)
    rep = jload(os.path.join(MAIN, "ds34_render_report.json"))
    reg = jload(os.path.join(MAIN, "ds30_tstar_regress.json"))
    play = list(csv.DictReader(open(os.path.join(U3, "playmode", "ds34_playmode.csv"), encoding="utf-8")))
    figs = []
    figs += fig_toggles(rep)
    figs.append(fig_stills())
    fo, occl_rows = fig_occlusion(rep)
    figs.append(fo)
    figs.append(fig_stereo(rep))
    figs.append(fig_timing(rep, play))
    figs.append(fig_colour133())
    vids = grid_videos()

    # ---- 受入の値
    T = rep["timing"]
    occ = rep["occlusion"]
    st = rep["stereo"]
    MINPX = 500
    st_acc = [s for s in st if min(s["clawPxL"], s["clawPxR"]) >= MINPX]
    st_rec = [s for s in st if min(s["clawPxL"], s["clawPxR"]) < MINPX]
    pf = [float(r["t"]) for r in play]
    play_mis_c = sum(1 for r in play if math.floor(float(r["claw_t"]) * 30 + 1e-9) != math.floor(float(r["t"]) * 30 + 1e-9))
    play_mis_s = sum(1 for r in play if math.floor(float(r["spray_t"]) * 30 + 1e-9) != math.floor(float(r["t"]) * 30 + 1e-9))
    play_dt = max(abs(float(r["claw_t"]) - float(r["t"])) for r in play)
    play_ds = max(abs(float(r["spray_t"]) - float(r["t"])) for r in play)
    play_tau = max(abs(float(r["hero_tau"]) - float(r["warp_tau"])) for r in play)
    prev_med = float(np.median([r["rootMaxPrevMm"] for r in T[1:] if r["k"] <= 360]))
    occl_by = {}
    for o in occ:
        a = occl_by.setdefault("%s/%s" % (o["view"], o["layer"]), {"frames": 0, "only": 0, "behind": 0, "hiddenByBoat": 0, "leak": 0, "fullVisible": 0})
        a["frames"] += 1
        for key in ("only", "behind", "hiddenByBoat", "leak", "fullVisible"):
            a[key] += o[key]
    leak_total = sum(o["leak"] for o in occ)
    hid_claws = sum(o["hiddenByBoat"] for o in occ if o["layer"] == "claws")
    hid_spray = sum(o["hiddenByBoat"] for o in occ if o["layer"] == "spray")
    sc, sw = reg["sets"]["t28_claws"], reg["sets"]["t28_white"]
    base = reg["base_29r01"]
    white_same = {}
    d31 = os.path.join(REPO, "Unity", "Build", "Design", "31", "white", "unity", "main", "t28_white", "t28", "render")
    for f in ["af28r01_painting.png", "af28r01_seat.png", "af28r01_seat_low.png", "af28r01_painting_kstar.png", "af28r01_seat_kstar.png",
              "af28r01_seat_low_kstar.png", "af28r01_class_ids.png", "af28r01_seat_class_ids.png", "af28r01_seat_low_class_ids.png", "af28r01_line_ids.png"]:   # Unity が書いた 10 枚（評価器が同じフォルダーに書く図は除く）
        white_same[f] = sha256(os.path.join(MAIN, "t28_white", "t28", "render", f)) == sha256(os.path.join(d31, f))
    vc = jload(os.path.join(MAIN, "t28_claws", "ds29r01_tstar_verdict.json"))["colour_boundaries"]["items"]
    vw = jload(os.path.join(MAIN, "t28_white", "ds29r01_tstar_verdict.json"))["colour_boundaries"]["items"]
    colour_cmp = {k: {"no_claws_px": vw[k]["now_max_px"], "claws_px": vc[k]["now_max_px"], "verdict_no_claws": vw[k]["verdict_now"], "verdict_claws": vc[k]["verdict_now"]} for k in vc}

    acceptance = {
        "A1_three_layers_time_offset_0": {
            "criterion_ja": "3 層の時刻のずれ 0（同じフレーム番号で描く）",
            "capture_frames": len(T),
            "capture_max_claw_frame_offset": max(abs(r["clawFrame"] - r["k"]) for r in T),
            "capture_max_spray_frame_offset": max(abs(r["sprayFrame"] - r["k"]) for r in T),
            "capture_max_hero_tau_minus_tau_t": max(abs(r["heroTau"] - r["warpTau"]) for r in T),
            "capture_claws_on_grid_frames": sum(1 for r in T if r["clawOnGrid"]),
            "unity_root_to_sheet_max_mm": rep["rootMaxMmAll"],
            "unity_root_to_sheet_triangle_max_mm": rep["rootTriMaxMmAll"],
            "control_claws_one_frame_early_median_of_frame_max_mm_t0_to_tstar": prev_med,
            "playmode_frames": len(play),
            "playmode_dt_s": float(np.median([float(r["deltaTime"]) for r in play])),
            "playmode_frame_index_mismatch_claws": play_mis_c,
            "playmode_frame_index_mismatch_spray": play_mis_s,
            "playmode_max_abs_claw_t_minus_t_s": play_dt,
            "playmode_max_abs_spray_t_minus_t_s": play_ds,
            "playmode_max_abs_hero_tau_minus_tau_t": play_tau,
            "note_ja": "採取：コマ k = 0〜420 ごとに 1 つの t = k/30 を再生器（主役波・海の τ(t)）・爪（コマの表 k）・飛沫（コマの表 k）へ渡す。ずれは 0。"
                       "Unity の GPU で読み戻した主役波の頂点で、爪の根元とシートの結び付けの点の距離は最大 %.4f mm（1 コマずらすと中央値 %.0f mm）。"
                       "Play モード（Editor、dt 0.02 s）：爪と飛沫は GWClock の秒（float）を読むので t との差は最大 %.1e s、フレーム番号の食い違い 0。" % (rep["rootMaxMmAll"], prev_med, max(play_dt, play_ds)),
            "frame_tolerance_ja": "コマの位置の比べは 1e-6 コマまでを同じとする（飛沫の報告の値 (t − t0)·hz の倍精度の丸め 2.8e-14 コマのため。飛沫の再生器も s ≤ 1e-6 を格子の上として扱い、s が 1 に近いときは次のコマの値をそのまま使う）",
            "pass": bool(max(abs(r["clawFrame"] - r["k"]) for r in T) <= 1e-6 and max(abs(r["sprayFrame"] - r["k"]) for r in T) <= 1e-6
                         and max(abs(r["heroTau"] - r["warpTau"]) for r in T) == 0 and play_mis_c == 0 and play_mis_s == 0 and rep["rootMaxMmAll"] <= 1.0),
        },
        "A2_claws_spray_behind_hull_hidden": {
            "criterion_ja": "船体の後ろの爪・飛沫が船に隠れる",
            "views": sorted(set(o["view"] for o in occ)), "times_s": sorted(set(o["t"] for o in occ)),
            "renders_per_case": 4, "cases": len(occ),
            "hidden_by_boat_px_claws": hid_claws, "hidden_by_boat_px_spray": hid_spray, "leak_px_total": leak_total,
            "by_view_layer": occl_by,
            "occl_cams": rep["occlCams"],
            "note_ja": "①その層だけ ②その層＋船（深度だけ）③場面全体 ④場面全体から船を消す、を同じコマで描く（確認用の色：爪マゼンタ・飛沫シアン、MSAA なし）。"
                       "①にあって②にない画素＝船の後ろ。そのうち④で見えるもの＝船がなければ見える画素（船に隠されるべき画素）。③で見えている数が漏れ。"
                       "原画視点（爪 t 10〜11.5 s）・座席の低い視点・座席から波の方向と、確認用の視点 occl_mid・occl_fg・occl_left（舷の外、上端の 0.35 m 下）で数えた。"
                       "確認用の色が普通の描画に出る画素（誤検出）は 0（falsePositives）。",
            "false_positive_px": sum(f["clawDiagPx"] + f["sprayDiagPx"] for f in rep["falsePositives"]),
            "pass": bool(leak_total == 0 and hid_claws > 0 and hid_spray > 0),
        },
        "A3_mock_two_eye_claw_px_lr_diff_lt_10pct": {
            "criterion_ja": "Mock の両眼で爪の画素数の左右差 <10%",
            "method_ja": "座席 v1・原画視点のカメラを右の向きへ ±32 mm（IPD 64 mm）ずらして 2 回描き、確認用の色の爪の画素を数える（場面全体、遮蔽あり、MSAA なし）。"
                         "両目とも %d px 以上のコマを判定に使い、それより少ないコマは記録のみ（爪が生え始めで小さい）。" % MINPX,
            "min_px_for_verdict": MINPX,
            "judged": [{"view": s["view"], "t": s["t"], "L": s["clawPxL"], "R": s["clawPxR"], "rel_diff": round(s["clawRelDiff"], 5)} for s in st_acc],
            "record_only": [{"view": s["view"], "t": s["t"], "L": s["clawPxL"], "R": s["clawPxR"], "rel_diff": round(s["clawRelDiff"], 5)} for s in st_rec],
            "max_rel_diff_judged": max(s["clawRelDiff"] for s in st_acc),
            "spray_max_rel_diff_record": max(s["sprayRelDiff"] for s in st if min(s["sprayPxL"], s["sprayPxR"]) >= MINPX),
            "pass": bool(len(st_acc) > 0 and max(s["clawRelDiff"] for s in st_acc) < 0.10),
        },
        "HMD_H1_H3_H4": {"status": "保留", "note_ja": "PS VR2 は未導入（利用者の手が要る）。Mock の両眼（カメラを 2 回描く PC の代理）と PC の描画で代えた。立体の描画経路（SPI）は爪のシェーダーのコンパイルだけ確かめた（STEREO_INSTANCING_ON の変種、SV_RenderTargetArrayIndex あり）。"},
    }
    regression = {
        "rule_ja": "計画 §2.0：原画視点に触れたので評価器（ds30b_tstar_regress.py、設計29修正01 と同じ 3 つの読み）を回した。",
        "t28_white_identical_to_ds31": {"all": all(white_same.values()), "files": white_same},
        "outline_with_claws": {"78_130_131_px": [sc["verdict"]["silhouettes_vs_kstar_prime"]["rows"][k]["unity_max_px"] for k in ("78", "130", "131")],
                               "132_sigma12_max_px": sc["lfgate"]["132_sigma12_max"], "72_sigma24_p95_px": sc["lfgate"]["72_sigma24_p95"],
                               "diff_vs_29r01": {**sc["silhouette_diff_vs_29r01_px"], **sc["lfgate_diff_vs_29r01_px"]},
                               "verdict_ja": "後退なし（78／130／131・132 σ12 は差 0、72 σ24 p95 は 4.0075 → %.4f px で良くなった。設計33 の numpy の 3.84 px と同じ）" % sc["lfgate"]["72_sigma24_p95"]},
        "outline_without_claws": {"132_sigma12_max_px": sw["lfgate"]["132_sigma12_max"], "72_sigma24_p95_px": sw["lfgate"]["72_sigma24_p95"], "diff_vs_29r01": {**sw["silhouette_diff_vs_29r01_px"], **sw["lfgate_diff_vs_29r01_px"]}},
        "colour_items_sheet_without_claw_layer": {"worst_abs_diff_px": sw["verdict"]["colour_worst_abs_diff_px"], "sym_worst_diff_vs_29r01_px": sw.get("sym", {}).get("worst_diff_vs_29r01_px"),
                                                  "verdict_changes_vs_28r01": sw["verdict"]["verdict_changes_vs_28r01"],
                                                  "verdict_ja": "設計31（＝29修正01）と画像が同じなので値も同じ。後退なし"},
        "colour_items_with_claws_in_class_ids": {"items": colour_cmp, "worst_abs_diff_px": sc["verdict"]["colour_worst_abs_diff_px"],
                                                 "verdict_changes_vs_28r01": sc["verdict"]["verdict_changes_vs_28r01"],
                                                 "sym_worst_diff_vs_29r01_px": sc.get("sym", {}).get("worst_diff_vs_29r01_px"),
                                                 "verdict_ja": "爪を色区 ID に入れた読みでは、133（左側から上側へ続く白と上側の境界）が 0.718 → 8.837 px で合格 → 不合格になる"
                                                               "（最悪の点は表示 (751, 188)：描画の白が真値の白の境界から離れる向き。爪の白と淡い水色の帯が、焼き込みの色面の白と淡い水色の模様の上に重なる）。"
                                                               "134（8.996 → 9.399）・175（もともと不合格）は悪くなり、79（1.012 → 1.608）・270 の記録の読み（1.028 → 8.65）は合格のまま悪くなる。"
                                                               "評価器の色区の真値（W001 の帯の境界など）は爪の層を含まない。"},
        "reading_taken_ja": "採った読み（進行役の判断を待つ推奨）：輪郭の項目は爪を ID に入れて測り（後退なし）、色区の項目はシートの色（爪の層を除く）で測る（後退なし）。"
                            "設計31 が飛沫を ID に入れない読みを採ったのと同じ形。爪を入れた色区の読みの 133 の不合格は限界として記録し、仕上げ33（爪の幅・色区への当てはめ）・設計36（爪の調色）へ渡す。",
    }
    record_only = {
        "148": "事前検査（記録）：爪・飛沫は不透明（ZWrite On・ZTest LEqual）。遮蔽の検査の③で、船の後ろの爪・飛沫が透ける画素は 0。爪の後ろの藍の線が透けないことは設計38 の線で測る。",
        "206": "記録：原画視点の t* で、Unity の爪の画素は L %d・R %d px（Mock の片目ずつ、遮蔽あり）。射線の検査の値は設計33 の numpy の再投影（骨格と一覧の中心線の対称 Hausdorff 中央値 0.62 px・最大 3.9 px）を引き継ぎ、Unity では測り直していない。"
               % (next(s["clawPxL"] for s in st if s["view"] == "painting" and s["t"] == 12.0), next(s["clawPxR"] for s in st if s["view"] == "painting" and s["t"] == 12.0)),
        "shader_checks": rep["shaderChecks"],
        "claw_mesh": {"claws": rep["clawCount"], "vertices": rep["clawVertices"], "triangles": rep["clawTriangles"], "white_triangles": rep["clawWhiteTriangles"], "mizuiro_triangles": rep["clawMizuiroTriangles"], "frames": rep["clawFrames"], "hz": rep["clawHz"], "load_s": rep["clawLoadSeconds"]},
        "spray": {"count": rep["sprayCount"], "frames": rep["sprayFrames"], "hz": rep["sprayHz"]},
    }
    limits = [
        "爪を色区 ID に入れた評価器の読みで、色区 133 が不合格（8.837 px）、134・175 が悪くなる。爪の帯が焼き込みの色面の模様の上に重なるため。仕上げ33・設計36 へ（上の regression）。",
        "Mock の両眼は PC でカメラを 2 回描く代理で、立体の描画経路（SPI）ではない。PS VR2 の H1・H3・H4 は保留（未導入）。",
        "Play モードの確認は Editor の batch（dt 0.02 s 固定）。実時間の PC ビルドと HMD では確かめていない。",
        "Play モードの爪・飛沫は GWClock の秒（float）を読むので、再生器の t（double）と最大 %.1e s ずれる（フレーム番号は同じ）。" % max(play_dt, play_ds),
        "確認用の視点 occl_mid・occl_fg・occl_left は検査のためだけの視点で、場面には保存していない。飛沫が船に隠される画素は occl_mid だけで確かめた（原画視点と座席では飛沫が船の後ろに来ない）。",
        "色と線は仮（爪は白と淡い水色の平塗り、線なし）。設計36・38。",
    ]
    metrics = {
        "schema": "GreatWave.DS34.unity3_metrics/1", "number": "設計34 Unity の部（unity3）", "date": "2026-09-30",
        "evidence_kind_ja": "Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、%s）と Editor の batch の Play モード。HMD 実機ではない。" % rep["graphicsApi"],
        "acceptance": acceptance, "regression": regression, "record_only": record_only, "limits_ja": limits,
        "backlog": {"148": "記録（事前検査）", "206": "記録"},
        "fix_rounds": 0,
        "dev_changes_ja": ["層の入切の一覧のファイル名（W/w の大文字・小文字で入切を書いていた）が Windows で重なり、8 通りが 1 枚に上書きされていたので、W0/W1 の形に直して一覧だけ撮り直した（toggles_run。受入の値にはかかわらない）。",
                           "確認用の視点を船の中心の延長（水の中になった）から、舷の外・上端の 0.35 m 下へ置き直し、④（船を消した場面全体）を足した（受入の値を決める前の作り手の直し。1 回目の採取では確認用の視点の漏れの検査が水面に隠されて自明になっていた）。"],
        "figures": [os.path.relpath(p, REPO).replace("\\", "/") for p in figs], "videos": [os.path.relpath(p, REPO).replace("\\", "/") for p in vids],
        "occlusion_figure_rows": occl_rows,
    }
    with open(os.path.join(U3, "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")
    # run.json
    ins = {p: sha256(os.path.join(REPO, "Unity", p)) for p in [
        "Build/Design/33/claws/ds33_claw_layout.json", "Build/Design/33/claws/ds33_claw_frames_f32.bin", "Build/Design/33/claws/ds33_claw_tris_i32.bin",
        "Build/Design/33/claws/ds33_claw_tri_attr_u16.bin", "Build/Design/33/claws/ds33_claw_rig.json", "Build/Design/31/spray/ds31_spray_frames.bin",
        "Build/Design/31/spray/ds31_spray_frames.json", "Build/Design/31/white/ds31_twhite_r32f.bin", "Build/Design/28R01F/F_final/timewarp_F_final.json",
        "Assets/GreatWave/Design31/Scenes/DS31_WhiteSpray.unity"]}
    code = {p: sha256(os.path.join(REPO, p)) for p in [
        "Unity/Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs", "Unity/Assets/GreatWave/Design34/Scripts/DS34LayerSet.cs",
        "Unity/Assets/GreatWave/Design34/Shaders/DS34_Claw_Unlit.shader", "Unity/Assets/GreatWave/Design34/Shaders/DS34_DepthOnly.shader",
        "Unity/Assets/GreatWave/Design34/Editor/DS34Render.cs", "Unity/Assets/GreatWave/Design34/Editor/DS34PlayModeCheck.cs",
        "Unity/Assets/GreatWave/Design34/Scenes/DS34_ThreeLayers.unity", "Tools/GWWaveGen/ds34/run_ds34_unity.ps1", "Tools/GWWaveGen/ds34/ds34u3_evidence.py"]}
    outs = {}
    for root, _, fs in os.walk(U3):
        for fn in fs:
            if fn.endswith((".png", ".mp4", ".json", ".csv")) and "_stale" not in root and not fn.startswith("_dbg"):
                p = os.path.join(root, fn)
                if os.path.getsize(p) > 0 and fn not in ("run.json",):
                    outs[os.path.relpath(p, U3).replace("\\", "/")] = sha256(p)
    run = {
        "schema": "GreatWave.DS34.unity3_run/1", "unity": rep["unity"], "device": rep["device"], "graphics_api": rep["graphicsApi"],
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds34/run_ds34_unity.ps1 -Method GreatWave.Design34.EditorTools.DS34Render.Render -Log main2 -Extra \"-ds34Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/34/unity3/main -ds34Skip video\"（26.1 s）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds34/run_ds34_unity.ps1 -Method GreatWave.Design34.EditorTools.DS34Render.Render -Log video -Extra \"-ds34Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/34/unity3/video_run -ds34Skip scene,t28,timing,stills,toggles,occl,stereo,shader\"（65 s）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds34/run_ds34_unity.ps1 -Method GreatWave.Design34.EditorTools.DS34Render.Render -Log toggles -Extra \"-ds34Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/34/unity3/toggles_run -ds34Skip scene,t28,timing,stills,occl,stereo,shader,video\"（18 s。層の入切の一覧だけを撮り直した。main2 の回の一覧はファイル名の大文字・小文字が Windows で重なり 4 枚に上書きされたので main/_stale_run1 へ退けた）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds34/run_ds34_unity.ps1 -NoQuit -Method GreatWave.Design34.EditorTools.DS34PlayModeCheck.Run -Log playmode -Extra \"-ds34Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/34/unity3/playmode\"（19 s）",
            "py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/34/unity3/main --sets t28_claws,t28_white（3 分 41 s）",
            "py -3.10 -B Tools/GWWaveGen/ds34/ds34u3_evidence.py",
        ],
        "scene34_sha256": rep["scene34Sha256"], "protected_unchanged": rep["protectedUnchanged"], "protected_files": rep["protectedFiles"],
        "inputs_sha256": ins, "code_sha256": code, "outputs_sha256": outs,
        "claw_frames_sha256_seen_by_unity": rep["clawFramesSha256"], "spray_sha256_seen_by_unity": rep["spraySha256"],
    }
    with open(os.path.join(U3, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(json.dumps({k: v.get("pass", v.get("status")) for k, v in acceptance.items()}, ensure_ascii=False))
    print("figs", len(figs), "videos", len(vids))


if __name__ == "__main__":
    main()
