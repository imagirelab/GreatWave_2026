# -*- coding: utf-8 -*-
"""設計30 修正1（1回だけの修正、Q26）：評審の必ず直す2点が Unity の出力から消えたかを、直す前（single）と直した後（single_fix1）で測る。

必ず直す点：
  1) 手前の小波の泡の線の仮置き M1_ForegroundFoam_Static が宙に浮く（t* の seat_low で白い Λ と海を横切る白い帯、原画視点の動画で小波の横の 2 つ目の白い V）。
     直し方：DS30Render の -ds30Hide の既定に加えて描かない（泡と線は設計36・38）。
  2) 主役波と near の継ぎ目に沿った灰色の線（座席の目の seat_toward_wave のコマ 330〜420、t* の seat_low の左下）。
     直し方：主役波の外殻線だけを本体の境の輪から 10 列内側まで描く（DS30SheetPlayer.outlineColInset、-ds30LineInset 10）。

測るもの（画像だけ。評価器や生成器は読まない）：
  a. 灰色の線の画素：外殻線の灰色（藍濃の海 (35,63,97) の上の (72,78,95) 前後）に当たる画素 50 < R < 160 かつ B − R < 40 を、
     水平線と波の足もとより下（y ≥ 760、1920 × 1080）で数える。seat_toward_wave・seat・原画視点・side_left の動画の 5 コマおき
     （t = 8〜14 s、コマ 240〜420）と、t* の seat_low の画像。
  b. 泡の線の白：原画視点の動画のコマ 255〜375 と t* の seat_low で、直す前と後で変わった画素の数と、白（R, G, B > 225）の画素の数。
  c. 直した後の t* の評価器の値と第B部の項目（ds30_tstar_regress.json・ds30b_summary.json）が直す前と同じか（SHA-256・経路・秒・再生モードのコマ数を除く）。
使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds30/ds30_fix1_measure.py
出力：Unity/Build/Design/30/unity/single_fix1/ds30_fix1.json、fig_ds30_fix1.png
"""
import hashlib
import json
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
U = os.path.join(REPO, "Unity", "Build", "Design", "30", "unity")
BEFORE, AFTER = os.path.join(U, "single"), os.path.join(U, "single_fix1")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
Y0 = 760


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def grey_px(im):
    s = im[Y0:]
    r, b = s[..., 0], s[..., 2]
    return int(((r > 50) & (r < 160) & ((b - r) < 40)).sum())


def white_px(im):
    return int((im > 225).all(2).sum())


def frames(mp4, start, stop, step, tmp, tag):
    pat = os.path.join(tmp, tag + "_%04d.png")
    sel = "between(n\\,%d\\,%d)*not(mod(n-%d\\,%d))" % (start, stop, start, step)
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-i", mp4, "-vf", "select='%s'" % sel, "-vsync", "vfr", pat], check=True)
    idx = list(range(start, stop + 1, step))
    return {n: np.asarray(Image.open(pat % (k + 1)).convert("RGB")).astype(np.int32) for k, n in enumerate(idx)}


def same_values(a, b, path=""):
    skip = ("sha", "seconds", "path", "dir", "csv", "/out", "file", "play_mode/frames", "play_mode/states", "play_mode/end", "hidden_context", "attached_foam")
    diffs = []
    if isinstance(a, dict):
        for k in a:
            p = path + "/" + k
            if any(s in p.lower() for s in skip):
                continue
            if not isinstance(b, dict) or k not in b:
                diffs.append(p + " 欠け")
                continue
            diffs += same_values(a[k], b[k], p)
    elif isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            return [path + " 長さ"]
        for i, (x, y) in enumerate(zip(a, b)):
            diffs += same_values(x, y, "%s[%d]" % (path, i))
    elif a != b:
        diffs.append("%s: %r -> %r" % (path, a, b))
    return diffs


def main():
    out = {"schema": "ds30_fix1/1", "number": "設計30 修正1", "before": BEFORE, "after": AFTER, "grey_rule_ja": "50 < R < 160 かつ B − R < 40、y ≥ %d（1920 × 1080）" % Y0}
    rep = json.load(open(os.path.join(AFTER, "ds30_render_report.json"), encoding="utf-8"))
    out["after_render"] = {"hidden": rep["hidden"], "attachedFoam": rep.get("attachedFoam"), "heroLineInset": rep["heroLineInset"],
                           "heroLineTrianglesWindow": rep["heroLineTrianglesWindow"], "heroTrianglesWindow": rep["heroTrianglesWindow"],
                           "passed": rep["passed"], "protectedUnchanged": rep["protectedUnchanged"], "sceneSha256": rep.get("sceneSha256")}
    vids = {}
    figs = []
    with tempfile.TemporaryDirectory() as tmp:
        for v, (a0, a1) in {"seat_toward_wave": (240, 420), "seat": (240, 420), "painting": (240, 420), "side_left": (240, 420)}.items():
            fb = frames(os.path.join(BEFORE, "video", "ds30_%s_30fps.mp4" % v), a0, a1, 5, tmp, "b_" + v)
            fa = frames(os.path.join(AFTER, "video", "ds30_%s_30fps.mp4" % v), a0, a1, 5, tmp, "a_" + v)
            rec = {"frames": sorted(fb), "grey_before": [grey_px(fb[n]) for n in sorted(fb)], "grey_after": [grey_px(fa[n]) for n in sorted(fa)],
                   "changed_px": [int((np.abs(fb[n] - fa[n]).sum(2) > 30).sum()) for n in sorted(fb)],
                   "white_before": [white_px(fb[n]) for n in sorted(fb)], "white_after": [white_px(fa[n]) for n in sorted(fa)]}
            rec["grey_before_max"], rec["grey_after_max"] = max(rec["grey_before"]), max(rec["grey_after"])
            vids[v] = rec
            if v == "seat_toward_wave":
                figs.append((fb[390], fa[390], "seat_toward_wave f390 (t 13.0 s)"))
            if v == "painting":
                figs.append((fb[315], fa[315], "painting f315 (t 10.5 s)"))
    out["videos"] = vids
    sl_b = np.asarray(Image.open(os.path.join(BEFORE, "t28_seaids", "t28", "render", "af28r01_seat_low.png")).convert("RGB")).astype(np.int32)
    sl_a = np.asarray(Image.open(os.path.join(AFTER, "t28_seaids", "t28", "render", "af28r01_seat_low.png")).convert("RGB")).astype(np.int32)
    out["tstar_seat_low"] = {"grey_before": grey_px(sl_b), "grey_after": grey_px(sl_a), "white_before": white_px(sl_b), "white_after": white_px(sl_a),
                             "changed_px": int((np.abs(sl_b - sl_a).sum(2) > 30).sum())}
    figs.append((sl_b, sl_a, "seat_low t* (t 12 s)"))
    # c. 評価器の値・第B部の項目が同じか
    for fn in ("ds30_tstar_regress.json", "ds30b_summary.json"):
        a = json.load(open(os.path.join(BEFORE, fn), encoding="utf-8"))
        b = json.load(open(os.path.join(AFTER, fn), encoding="utf-8"))
        d = same_values(a, b)
        out["same_" + fn.replace(".json", "")] = {"identical_values": not d, "differences": d}
    s = json.load(open(os.path.join(AFTER, "ds30b_summary.json"), encoding="utf-8"))["items"]
    out["after_items"] = {"holes_seat_worst_px": s["holes"]["holes"]["seatWorstHolePx"], "holes_painting_worst_px": s["holes"]["holes"]["paintingWorstHolePx"],
                          "holes_frames": s["holes"]["holes"]["frames"], "seat_eye_under_water_frames": s["seat_eye"]["under_water_frames"],
                          "seat_eye_min_clearance_m": s["seat_eye"]["min_clearance_m"], "tstar_regression": s["tstar_regression"]["seaids"],
                          "start_end": {k: s["start_end"]["per_sheet"]["hero"][k] for k in ("start_step_m", "median_next30_m", "end_step_m", "hold_max_step_m")},
                          "seam_hero_near_max_dy_m": s["seam_hero_near"]["max_dy_m"], "seam_hero_near_max_dv_mps": s["seam_hero_near"]["max_dv_mps"],
                          "seam_hero_near_side_normal_dot_min": s["seam_hero_near"]["side_normal_dot_min"], "play_mode_pass": s["play_mode"]["pass"]}
    # 図：直す前（左）と後（右）
    rows = []
    for b, a, lab in figs:
        pair = []
        for im, t in ((b, "before " + lab), (a, "after " + lab)):
            pi = Image.fromarray(im.astype(np.uint8)).resize((960, 540))
            dr = ImageDraw.Draw(pi)
            dr.rectangle((0, 0, 330, 22), fill=(0, 0, 0))
            dr.text((5, 5), t, fill=(255, 255, 0))
            pair.append(np.asarray(pi))
        rows.append(np.concatenate(pair, 1))
    fig = os.path.join(AFTER, "fig_ds30_fix1.png")
    Image.fromarray(np.concatenate(rows, 0)).save(fig)
    out["figure"] = fig
    out["figure_sha256"] = sha256(fig)
    p = os.path.join(AFTER, "ds30_fix1.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    v = out["videos"]
    print("DS30_FIX1 stw grey max %d -> %d, seat_low t* grey %d -> %d white %d -> %d, painting changed max %d, tstar same=%s summary same=%s -> %s" % (
        v["seat_toward_wave"]["grey_before_max"], v["seat_toward_wave"]["grey_after_max"], out["tstar_seat_low"]["grey_before"], out["tstar_seat_low"]["grey_after"],
        out["tstar_seat_low"]["white_before"], out["tstar_seat_low"]["white_after"], max(v["painting"]["changed_px"]),
        out["same_ds30_tstar_regress"]["identical_values"], out["same_ds30b_summary"]["identical_values"], p))


if __name__ == "__main__":
    main()
