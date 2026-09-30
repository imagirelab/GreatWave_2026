# -*- coding: utf-8 -*-
"""設計48（船首の泡・航跡）の記録の道具。作品には触れない（読むだけ）。

  1. 作る部の出力の SHA-256 を、作る部の run.json（inputs・outputs）と ds48_build.json の守るファイルに照らす。違えば止まる。
  2. 作る部の数え直し（ds48_report.py）を使わずに、生の記録（90 Hz の ds48_frames.csv、10 コマ/s の ds48_masks.csv、ds48_play.json、
     座席から見回した PNG、終わりの原画視点の PNG、動画）から、最小の受入と限界の値を数え直し、作る部の metrics.json と比べる。
  3. 場面 DS48_Wake.unity の依存（GUID）を設計47 の DS47_Flow.unity と比べ、Design48 のテキストの資産の改行を数える。
  4. 証拠を Docs/Evidence/Design/48/ へ写す（PNG は 1920×1080 に収め、動画は 5 MB 以下に縮める）。記録の metrics.json・run.json を書く。
PC の Unity の Editor の Play（batchmode、1 フレーム = 1/90 s）の記録を読むだけ。HMD 実機ではない。
実行：py -3.10 -B Tools/GWWaveGen/ds48/ds48_record.py
"""
import csv
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/48/wake"
MAIN = OUT + "/unity/main"
EVD = REPO + "/Docs/Evidence/Design/48"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FFPROBE = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
REF47 = REPO + "/Unity/Build/Design/47/flow/unity/main/painting/painting_end.png"
CFG = REPO + "/Unity/Assets/GreatWave/Design48/Data/ds48_wake.json"
PALETTE = REPO + "/Tools/PaintingTruth/targets/palette.json"
SCENE47 = REPO + "/Unity/Assets/GreatWave/Design47/Scenes/DS47_Flow.unity"
SCENE48 = REPO + "/Unity/Assets/GreatWave/Design48/Scenes/DS48_Wake.unity"
T0 = time.time()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def fnum(x):
    try:
        return float(x)
    except ValueError:
        return float("nan")


def load_csv(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def verify_builder():
    run = json.load(open(OUT + "/run.json", encoding="utf-8"))
    build = json.load(open(OUT + "/unity/ds48_build.json", encoding="utf-8"))
    bad = []
    n = 0
    for k, v in run["inputs"].items():
        n += 1
        if sha(REPO + "/" + k) != v:
            bad.append(k)
    for k, v in run["outputs"].items():
        n += 1
        if sha(REPO + "/" + k) != v["sha256"]:
            bad.append(k)
    prot_bad = []
    for line in build["protected"]:
        path, h = line.rsplit(" ", 1)
        p = os.path.normpath(os.path.join(REPO, "Unity", path))
        if sha(p) != h:
            prot_bad.append(path)
    if build["sceneSha256"] != sha(SCENE48):
        bad.append("scene(ds48_build.json)")
    if bad or prot_bad:
        raise SystemExit("SHA-256 が作る部の記録と違う：" + json.dumps({"bad": bad, "protected": prot_bad}, ensure_ascii=False))
    return {"files": n, "protected": len(build["protected"]), "all_same": True}


def recount():
    cfg = json.load(open(CFG, encoding="utf-8"))
    play = json.load(open(MAIN + "/ds48_play.json", encoding="utf-8"))
    rows = load_csv(MAIN + "/ds48_frames.csv")
    masks = load_csv(MAIN + "/ds48_masks.csv")
    c = lambda k: np.array([fnum(r[k]) for r in rows])
    exp = c("exp"); wave = c("wave"); ph = np.array([r["phase"] for r in rows]); ho = c("handed_over")
    extra = [r["extra"].split("|") for r in rows]
    thr = np.array([float(a[0]) for a in extra]); turn = np.array([float(a[1]) for a in extra]); stop = np.array([a[2] == "1" for a in extra])
    v = c("speed"); yr = c("yaw_rate"); gate = c("gate")
    bp = c("bow_port_w"); bs = c("bow_stbd_w"); ap = c("arm_port_w"); ast = c("arm_stbd_w")
    ron = c("renderer_on"); vis = c("visible_verts"); samp = c("samples")
    hid = c("guard_hidden") + c("overhang_hidden") + c("outside_hidden")
    mvy = c("max_visible_y")
    fade_end = cfg["gate"]["fadeEndWaveS"]
    out = {}

    # 受入 1：操作の方向への反応（入力の向きと角速度の両方で選ぶ。作る部と同じ区切り）と、入力を見ない角速度だけの区切り
    right = (ho == 0) & (turn > 0.5) & (yr > 3)
    left = (ho == 0) & (turn < -0.5) & (yr < -3)
    right_y = (ho == 0) & (yr > 3)
    left_y = (ho == 0) & (yr < -3)
    straight = (ho == 0) & (np.abs(yr) < 1) & (gate > 0.999)
    stopped = (ho == 0) & (v < 0.2) & (exp > 20)
    bowmax = np.maximum(bp, bs)
    out["acceptance1"] = {
        "right_turn_frames": int(right.sum()),
        "right_port_gt_stbd_frac": float(np.mean(bp[right] > bs[right])),
        "right_median_port_over_stbd": float(np.median(bp[right] / np.maximum(bs[right], 1e-3))),
        "right_arm_port_gt_stbd_frac": float(np.mean(ap[right] > ast[right])),
        "left_turn_frames": int(left.sum()),
        "left_stbd_gt_port_frac": float(np.mean(bs[left] > bp[left])),
        "left_median_stbd_over_port": float(np.median(bs[left] / np.maximum(bp[left], 1e-3))),
        "left_arm_stbd_gt_port_frac": float(np.mean(ast[left] > ap[left])),
        "yaw_only_right_frames": int(right_y.sum()), "yaw_only_right_port_gt_frac": float(np.mean(bp[right_y] > bs[right_y])),
        "yaw_only_left_frames": int(left_y.sum()), "yaw_only_left_stbd_gt_frac": float(np.mean(bs[left_y] > bp[left_y])),
        "right_turn_exp_range": [float(exp[right].min()), float(exp[right].max())],
        "left_turn_exp_range": [float(exp[left].min()), float(exp[left].max())],
        "straight_frames": int(straight.sum()),
        "straight_corr_speed_bow": float(np.corrcoef(v[straight], bowmax[straight])[0, 1]),
        "stopped_frames": int(stopped.sum()), "stopped_max_bow_w": float(bowmax[stopped].max()),
        "stopped_exp_range": [float(exp[stopped].min()), float(exp[stopped].max())],
        "max_bow_w": float(np.nanmax(bowmax)), "speed_at_max_bow": float(v[int(np.nanargmax(bowmax))]),
        "yaw_at_max_bow": float(yr[int(np.nanargmax(bowmax))]),
        "max_speed": float(np.nanmax(v)), "max_abs_yaw": float(np.nanmax(np.abs(yr))),
        "input_frames_steer": int(((thr != 0) | (turn != 0) | stop)[ho == 0].sum()),
    }
    # 受入 2：主役波の上に航跡が出ない
    mw = np.array([fnum(m["wave"]) for m in masks]); mw = np.where(np.isfinite(mw), mw, -1e9)
    wpx = np.array([int(m["wake_px"]) for m in masks]); hpx = np.array([int(m["hero_px"]) for m in masks])
    ovp = np.array([int(m["overlap_px"]) for m in masks]); mcam = np.array([m["cam"] for m in masks]); mph = np.array([m["phase"] for m in masks])
    after_m = mw >= fade_end
    after_f = np.isfinite(wave) & (wave >= fade_end)
    in02 = np.isfinite(wave) & (wave >= 0) & (wave < fade_end) & (ph == "Formation")
    in02_m = (mw >= 0) & (mw < fade_end)
    gz = np.where(gate <= 0)[0]
    hid_idx = np.where(hid > 0)[0]
    phases = ["Intro", "Approach", "Formation", "Hold", "Afterglow", "End"]
    out["acceptance2"] = {
        "mask_samples": int(len(masks)), "overlap_px_sum": int(ovp.sum()), "overlap_samples": int((ovp > 0).sum()),
        "after_fade_samples": int(after_m.sum()), "after_fade_wake_px_max": int(wpx[after_m].max()),
        "after_fade_hero_visible_samples": int((hpx[after_m] > 0).sum()),
        "after_fade_frames": int(after_f.sum()), "after_fade_visible_verts": int(vis[after_f].sum()),
        "after_fade_renderer_on": int(ron[after_f].sum()), "after_fade_samples_stored": int(samp[after_f].sum()),
        "first_gate_zero_wave": float(wave[gz[0]]) if len(gz) else None,
        "renderer_on_frames_by_phase": {p: int(ron[ph == p].sum()) for p in phases},
        "frames_by_phase": {p: int((ph == p).sum()) for p in phases},
        "wave0_2_frames": int(in02.sum()), "wave0_2_renderer_on": int(ron[in02].sum()),
        "wave0_2_mask_checks": {cam: {"n": int((in02_m & (mcam == cam)).sum()), "wake_visible": int(((wpx > 0) & in02_m & (mcam == cam)).sum()),
                                      "hero_visible": int(((hpx > 0) & in02_m & (mcam == cam)).sum())} for cam in ("chase", "hmd")},
        "guard_hidden_sum": int(hid.sum()),
        "guard_hidden_wave_range": [float(wave[hid_idx].min()), float(wave[hid_idx].max())] if len(hid_idx) else None,
        "gate_max_while_guard_hidden": float(gate[hid_idx].max()) if len(hid_idx) else None,
        "max_visible_vertex_y": float(np.nanmax(mvy)), "guard_height_m": cfg["gate"]["guardHeightM"],
        "per_phase_cam": {p + "/" + cam: {"n": int(((mph == p) & (mcam == cam)).sum()), "wake_visible": int(((wpx > 0) & (mph == p) & (mcam == cam)).sum()),
                                          "hero_visible": int(((hpx > 0) & (mph == p) & (mcam == cam)).sum()), "overlap": int(ovp[(mph == p) & (mcam == cam)].sum())}
                          for p in phases for cam in ("chase", "hmd") if ((mph == p) & (mcam == cam)).any()},
    }
    # 限界の値：大波の時刻 2〜5 s の船の速さ（泡のない船の動き）
    w25 = np.isfinite(wave) & (wave >= 2) & (wave < 5)
    moving = np.isfinite(wave) & (wave >= 2) & (v > 0.2) & (ph == "Formation")
    out["limit_formation_speed"] = {"wave2_5_speed_min": float(v[w25].min()), "wave2_5_speed_max": float(v[w25].max()),
                                    "last_wave_speed_gt_0_2": float(wave[moving].max()) if moving.any() else None,
                                    "wave_at_2_speed": float(v[np.argmin(np.abs(np.where(np.isfinite(wave), wave, 1e9) - 2.0))])}
    # 座席の視点
    hm = mcam == "hmd"
    white = np.array([227, 246, 251], np.uint8)  # BGR
    looks = {}
    for p in sorted(glob.glob(MAIN + "/look/*.png")):
        im = cv2.imread(p)
        looks[os.path.basename(p)] = {"px_white": int(np.all(im == white, axis=2).sum()), "size": [int(im.shape[1]), int(im.shape[0])]}
    out["seat_view"] = {"hmd_samples": int(hm.sum()), "hmd_wake_px_max": int(wpx[hm].max()), "hmd_wake_visible_samples": int((wpx[hm] > 0).sum()),
                        "looks_white_px": looks}
    # 原画視点
    a = cv2.imread(MAIN + "/painting/painting_end.png"); b = cv2.imread(REF47)
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(2)
    out["painting_view"] = {"sha256": sha(MAIN + "/painting/painting_end.png"), "ref47_sha256": sha(REF47), "px_diff": int((d > 0).sum()), "max_diff": int(d.max()),
                            "size": [int(a.shape[1]), int(a.shape[0])]}
    # 実行の道
    ev = play["events"]
    out["play"] = {"frames": play["frames"], "csv_rows": len(rows), "captured": play["captured"], "fixedDeltaTime": play["fixedDeltaTime"],
                   "events_fired": sum(1 for x in ev if x["fired"]), "events": len(ev),
                   "event_lag_s": {x["id"]: round(x["clockT"] - x["eventT"], 6) for x in ev},
                   "handover": play["handover"], "flow_errors": play["flowErrors"], "wake_errors": play["wake"]["errors"], "wake_teleports": play["wake"]["teleports"],
                   "boat_water_fallbacks": play["boatWater"]["fallbacks"], "boat_water_queries": play["boatWater"]["queries"],
                   "input_frames": play["input"]["frames"], "input_fallback_frames": play["input"]["fallbackFrames"],
                   "wake_rebuilds": play["wake"]["rebuilds"], "wake_tick_ms_mean": play["wake"]["tickMsTotal"] / play["wake"]["ticks"],
                   "wake_tick_ms_max": play["wake"]["tickMsMax"], "hull": {"bowZ": play["wake"]["bowZ"], "sternZ": play["wake"]["sternZ"], "halfBeam": play["wake"]["halfBeam"]},
                   "final": play["final"], "phase_first_exp": {p: float(exp[ph == p].min()) for p in phases if (ph == p).any()},
                   "exp_end": float(exp[-1])}
    # 色
    pal = json.load(open(PALETTE, encoding="utf-8"))
    out["color"] = {"cfg_srgb8": cfg["color"]["srgb8"], "palette_white_srgb8": pal["palette"]["white"]["srgb8"],
                    "palette_sha256": sha(PALETTE), "cfg_source_sha256": cfg["color"]["sourceSha256"],
                    "same": cfg["color"]["srgb8"] == pal["palette"]["white"]["srgb8"] and sha(PALETTE) == cfg["color"]["sourceSha256"]}
    return out


def compare_builder(rc):
    m = json.load(open(OUT + "/metrics.json", encoding="utf-8"))
    a1 = m["acceptance1_steering_reaction"]; a2 = m["acceptance2_no_wake_on_hero"]; r1 = rc["acceptance1"]; r2 = rc["acceptance2"]
    pairs = {
        "rightTurnFrames": (a1["rightTurnFrames"], r1["right_turn_frames"]), "leftTurnFrames": (a1["leftTurnFrames"], r1["left_turn_frames"]),
        "rightTurnPortGtStbdFrac": (a1["rightTurnPortGtStbdFrac"], r1["right_port_gt_stbd_frac"]),
        "leftTurnStbdGtPortFrac": (a1["leftTurnStbdGtPortFrac"], r1["left_stbd_gt_port_frac"]),
        "leftTurnArmStbdGtPortFrac": (a1["leftTurnArmStbdGtPortFrac"], r1["left_arm_stbd_gt_port_frac"]),
        "straightCorr": (a1["straightCorrSpeedVsBowWidth"], r1["straight_corr_speed_bow"]),
        "stoppedMaxBowWidth": (a1["stoppedMaxBowWidth"], r1["stopped_max_bow_w"]),
        "overlapPxSum": (a2["overlapPxSum"], r2["overlap_px_sum"]), "afterFadeWakePxMax": (a2["afterFadeWakePxMax"], r2["after_fade_wake_px_max"]),
        "framesAfterFade": (a2["framesAfterFade"], r2["after_fade_frames"]), "framesAfterFadeRendererOn": (a2["framesAfterFadeRendererOn"], r2["after_fade_renderer_on"]),
        "firstFrameGateZeroWave": (a2["firstFrameGateZeroWave"], r2["first_gate_zero_wave"]),
        "guardHiddenVertexInstances": (a2["guardHiddenVertexInstances"], r2["guard_hidden_sum"]),
        "maxVisibleVertexY": (a2["maxVisibleVertexY"], r2["max_visible_vertex_y"]),
        "paintingPxDiff": (m["painting_view_no_regression"]["pxDiff"], rc["painting_view"]["px_diff"]),
        "hmdForwardWakePxMax": (m["seat_view_limit"]["hmdForwardWakePxMax"], rc["seat_view"]["hmd_wake_px_max"]),
    }
    diff = {k: (None if a is None or b is None else float(b) - float(a)) for k, (a, b) in pairs.items()}
    return {"pairs": {k: [a, b] for k, (a, b) in pairs.items()}, "diff_record_minus_builder": diff,
            "max_abs_diff": max(abs(x) for x in diff.values() if x is not None), "builder_pass": m["pass"]}


def scene_deps():
    g47 = set(re.findall(r"guid: ([0-9a-f]{32})", open(SCENE47, encoding="utf-8").read()))
    t48 = open(SCENE48, encoding="utf-8").read()
    g48 = set(re.findall(r"guid: ([0-9a-f]{32})", t48))
    metas = {}
    for p in glob.glob(REPO + "/Unity/Assets/**/*.meta", recursive=True):
        with open(p, encoding="utf-8", errors="replace") as f:
            head = f.read(400)
        mm = re.search(r"guid: ([0-9a-f]{32})", head)
        if mm:
            metas[mm.group(1)] = rel(p)[:-5]
    new = sorted(g48 - g47)
    ent47 = len(re.findall(r"^--- !u!", open(SCENE47, encoding="utf-8").read(), re.M)); ent48 = len(re.findall(r"^--- !u!", t48, re.M))
    cams47 = len(re.findall(r"^--- !u!20 ", open(SCENE47, encoding="utf-8").read(), re.M)); cams48 = len(re.findall(r"^--- !u!20 ", t48, re.M))
    return {"guids47": len(g47), "guids48": len(g48), "new": {g: metas.get(g, "?") for g in new}, "dropped": sorted(g47 - g48),
            "entries47": ent47, "entries48": ent48, "cameras47": cams47, "cameras48": cams48,
            "scene_bytes": os.path.getsize(SCENE48), "scene_sha256": sha(SCENE48)}


def line_endings():
    res = {}
    for p in sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/Design48/**/*", recursive=True) + [REPO + "/Unity/Assets/GreatWave/Design48.meta"]
                    + glob.glob(REPO + "/Tools/GWWaveGen/ds48/*")):
        if os.path.isdir(p) or "__pycache__" in p:
            continue
        b = open(p, "rb").read()
        crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
        res[rel(p)] = "CRLF" if crlf and not lf else ("LF" if lf and not crlf else ("mixed" if crlf and lf else "none"))
    return res


def fit_png(src, dst):
    im = cv2.imread(src)
    h, w = im.shape[:2]
    if (w, h) == (1920, 1080):
        shutil.copyfile(src, dst)
        return {"src_size": [w, h], "scale": 1.0}
    s = min(1920 / w, 1080 / h)
    nw, nh = int(round(w * s)), int(round(h * s))
    r = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.full((1080, 1920, 3), 200, np.uint8)
    x0 = (1920 - nw) // 2; y0 = (1080 - nh) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = r
    cv2.imwrite(dst, canvas)
    return {"src_size": [w, h], "scale": round(s, 4), "placed": [x0, y0, nw, nh]}


def probe(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,nb_read_frames:format=duration,size", "-of", "json", p], capture_output=True, text=True)
    j = json.loads(r.stdout)
    s = j["streams"][0]
    return {"size": [s["width"], s["height"]], "fps": s["r_frame_rate"], "frames": int(s["nb_read_frames"]),
            "duration_s": float(j["format"]["duration"]), "bytes": int(j["format"]["size"])}


def evidence():
    os.makedirs(EVD, exist_ok=True)
    info = {}
    for name in ["fig_ds48_reaction.png", "stills_ds48_wake.png", "stills_ds48_seat_look.png"]:
        info[name] = fit_png(OUT + "/" + name, EVD + "/" + name)
    src = OUT + "/ds48_wake_30fps.mp4"
    dst = EVD + "/ds48_wake_1280x480_30fps.mp4"
    for crf in (26, 28, 30, 32):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src, "-vf", "scale=1280:480:flags=area", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
                        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", dst], check=True)
        if os.path.getsize(dst) <= 5_000_000:
            break
    info["video"] = {"src": probe(src), "src_sha256": sha(src), "copy": probe(dst), "crf": crf}
    for s, d in [(OUT + "/unity/ds48_build.json", "ds48_build.json"), (MAIN + "/ds48_play.json", "ds48_play.json"),
                 (OUT + "/metrics.json", "ds48_wake_metrics.json"), (OUT + "/run.json", "ds48_wake_run.json")]:
        shutil.copyfile(s, EVD + "/" + d)
    return info


def main():
    ver = verify_builder()
    rc = recount()
    cmp_ = compare_builder(rc)
    deps = scene_deps()
    le = line_endings()
    ev = evidence()
    recount_doc = {"schema": "GreatWave.DS48.record_recount/1", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "noteJa": "記録の道具 ds48_record.py が、作る部の数え直し（ds48_report.py）を使わずに生の記録から数え直した値。PC の Editor の Play の記録で、HMD 実機ではない。",
                   "builder_sha256_verified": ver, "recount": rc, "vs_builder": cmp_, "scene": deps, "line_endings": le, "evidence": ev}
    json.dump(recount_doc, open(EVD + "/ds48_record_recount.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    a1 = rc["acceptance1"]; a2 = rc["acceptance2"]
    p1 = a1["right_turn_frames"] > 90 and a1["left_turn_frames"] > 90 and a1["right_port_gt_stbd_frac"] >= 0.95 and a1["left_stbd_gt_port_frac"] >= 0.95 \
        and a1["straight_corr_speed_bow"] > 0.8 and a1["stopped_max_bow_w"] < 0.05
    p2 = a2["overlap_px_sum"] == 0 and a2["after_fade_wake_px_max"] == 0 and a2["after_fade_renderer_on"] == 0 and a2["after_fade_visible_verts"] == 0 \
        and a2["after_fade_hero_visible_samples"] > 0
    p3 = rc["painting_view"]["px_diff"] == 0
    metrics = {
        "schema": "GreatWave.DS48.record_metrics/1", "number": "設計48", "title_ja": "船首泡・航跡",
        "created_utc": recount_doc["created_utc"],
        "evidence_kind_ja": "PC の Unity 6000.4.3f1 の Editor の Play モード（batchmode、EditorApplication.Step で 1 フレーム = 1/90 s）の記録。HMD 実機・Release・実時間ではない。",
        "plan_ja": "計画 §2.5 設計48：調色板の白の平たいメッシュで、船首の泡と航跡。速度と旋回に反応する（依存 設計44、時間枠 ≤0.5日、Q26 で 2 h）",
        "min_acceptance_ja": "操作の方向に反応する動画。主役波の上に航跡が出ない",
        "acceptance": [
            {"item": "操作の方向に反応する動画", "result": "合格" if p1 else "不合格", "value": a1,
             "video": "Docs/Evidence/Design/48/ds48_wake_1280x480_30fps.mp4"},
            {"item": "主役波の上に航跡が出ない", "result": "合格" if p2 else "不合格", "value": {k: a2[k] for k in a2 if k != "per_phase_cam"}},
        ],
        "regression_painting_view": {"result": "合格（評価器は回していない。画素が同じ）" if p3 else "不合格", "value": rc["painting_view"]},
        "play_path": rc["play"],
        "record_only": {"seat_view": rc["seat_view"], "formation_speed": rc["limit_formation_speed"], "color": rc["color"]},
        "hmd": "保留（利用者の手。PS VR2 は未導入）",
        "builder_sha256_verified": ver,
        "record_recount": {"file": "Docs/Evidence/Design/48/ds48_record_recount.json", "max_abs_diff_vs_builder": cmp_["max_abs_diff"]},
        "fix_rounds": {"count": 0, "ja": "受入を判定した後の修正の回は使っていない。作る部の Unity の実行 build1・main1〜3 は判定の前の作る途中の実行で、最終は build2・main4。"},
        "time": {"box_ja": "Q26 の日程で 2 時間（計画 §2.6 の［Q26］の表、10/4 の行の設計48）",
                 "file_times_ja": "作る部の最初のファイル ds48_wake.json 15:51:07、Unity の build1 15:55、最終の build2 16:07:29・main4 16:09:46（UTC 08:09:46）、動画と図 16:10、独立の検査の出力 16:12〜16:17（いずれも +08:00）"},
        "pass": bool(p1 and p2 and p3),
    }
    json.dump(metrics, open(EVD + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ffv = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    ins = [OUT + "/run.json", OUT + "/metrics.json", OUT + "/unity/ds48_build.json", MAIN + "/ds48_play.json", MAIN + "/ds48_frames.csv", MAIN + "/ds48_masks.csv",
           MAIN + "/painting/painting_end.png", REF47, CFG, PALETTE, SCENE47, SCENE48, OUT + "/ds48_wake_30fps.mp4"] + sorted(glob.glob(MAIN + "/look/*.png"))
    outs = sorted(glob.glob(EVD + "/*"))
    run = {"schema": "GreatWave.DS48.record_run/1", "python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__, "ffmpeg": ffv,
           "cmd": "py -3.10 -B Tools/GWWaveGen/ds48/ds48_record.py",
           "builder_cmds": json.load(open(OUT + "/run.json", encoding="utf-8"))["unityCmds"],
           "inputs": {rel(p): sha(p) for p in ins},
           "outputs": {rel(p): {"sha256": sha(p), "bytes": os.path.getsize(p)} for p in outs if not p.endswith("/run.json") and not p.endswith("\\run.json")},
           "seconds": round(time.time() - T0, 1)}
    json.dump(run, open(EVD + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"pass": metrics["pass"], "p1": p1, "p2": p2, "p3": p3, "max_abs_diff": cmp_["max_abs_diff"], "seconds": run["seconds"]}))


if __name__ == "__main__":
    main()
