# -*- coding: utf-8 -*-
"""設計46（共通時計の部）：Unity の記録（ds46_clock_report.json・ds46_steps.csv・ds46_playmode.json・ds46_playmode.csv）から、
最小の受入の数値を数え直し（C# の要約の真偽は使わない）、metrics.json・run.json・図 2 枚（1920 × 1080）を作る（numpy・OpenCV）。

数え直すもの：
  1. 同じ時刻で同じ形：Editor の 4 つの道（停止・再開、初期化、途中からの再生、再生中の Seek）の各確かめの形のハッシュ一式を、
     基準の通し（R）の同じ体験の時刻の一式と比べる。Play モードのハッシュも、同じ時刻の R と比べる（画像のハッシュは Editor だけ）。
  2. 同期：毎段・毎フレームの同期の食い違いの数（全段が同じ時刻の決定を受けたか、層の時刻・τ が同じか）。
  3. 181：R の毎段の層の印から、白（頂点の旗・描いた白）・藍の色面（白を切った描画）・爪・飛沫が最終の印に達して変わらなくなる時刻。
  4. 物理の段が読む水の時刻（Play モード）：FixedUpdate の τ と、そのフレームに描く水の τ の差（コマ）。対照の区間（Update で進める）も数える。
  5. 出来事：基準の通しで各出来事が一度だけ、時刻をまたいだ段で起きる。Seek では起こさない。
PC の Unity（batchmode）の記録。HMD 実機ではない。
"""
import csv
import hashlib
import json
import os
import sys
import time
from collections import Counter

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ds44"))
from ds44_report import Panel, put  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/46/clock"
UNITY = OUT + "/unity"
PLAY = OUT + "/playmode"
TSTAR = 12.0
T0 = time.time()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    rep = json.load(open(UNITY + "/ds46_clock_report.json", encoding="utf-8"))
    pm = json.load(open(PLAY + "/ds46_playmode.json", encoding="utf-8"))
    steps = list(csv.DictReader(open(UNITY + "/ds46_steps.csv", encoding="utf-8")))
    prow = list(csv.DictReader(open(PLAY + "/ds46_playmode.csv", encoding="utf-8")))

    # ---- 1. 同じ時刻で同じ形（Editor）
    ref = {s["exp"]: s for s in rep["snaps"] if s["seq"] == "R"}
    cmp_rows, mism = [], 0
    for s in rep["snaps"]:
        if s["seq"] == "R" or s["exp"] not in ref:
            continue
        r = ref[s["exp"]]
        keys = sorted(set(s["h"]) | set(r["h"]))
        bad = [k for k in keys if s["h"].get(k) != r["h"].get(k)]
        if s["passed"] != r["passed"]:
            bad.append("events_passed")
        mism += bool(bad)
        cmp_rows.append({"seq": s["seq"], "label": s["label"], "exp": s["exp"], "keys": len(keys), "mismatch": bad})
    keys_per = sorted(set(k for s in rep["snaps"] for k in s["h"]))
    # 停止の間
    s1 = {s["label"]: s for s in rep["snaps"] if s["seq"] == "S1"}
    stop_same = s1["stop_at_5"]["h"] == s1["stopped_32_frames"]["h"] and s1["stop_at_5"]["step"] == s1["stopped_32_frames"]["step"]
    # Play モード
    pm_rows, pm_mism, pm_cmp = [], 0, 0
    for h in pm["hashes"]:
        r = ref.get(h["exp"])
        bad = None
        if r is not None:
            bad = [k for k in h["h"] if r["h"].get(k) != h["h"][k]]
            pm_cmp += 1
            pm_mism += bool(bad)
        pm_rows.append({"label": h["label"], "frame": h["frame"], "exp": h["exp"], "state": h["state"], "vsEditorR": bad})
    hs = {h["label"]: h for h in pm["hashes"]}
    pm_stop_same = hs["stop_a"]["h"] == hs["stop_b"]["h"] and hs["stop_a"]["exp"] == hs["stop_b"]["exp"] and hs["stop_a"]["step"] == hs["stop_b"]["step"]
    stop_frames = hs["stop_b"]["frame"] - hs["stop_a"]["frame"]
    acc1 = mism == 0 and len(cmp_rows) >= 15 and stop_same and pm_mism == 0 and pm_cmp >= 7 and pm_stop_same

    # ---- 2. 同期
    sync_edit = sum(int(r["sync_bad"]) for r in steps)
    sync_play = sum(int(r["sync_bad"]) for r in prow)

    # ---- 3. 181（R の毎段）
    R = [r for r in steps if r["seq"] == "R"]
    t = np.array([float(r["exp"]) for r in R])
    b181 = {}
    for col, name in [("hero", "主役波の形（参考）"), ("white_flags", "白：頂点の旗"), ("white_img", "白：描いた白（色区 ID、白あり）"),
                      ("indigo_img", "藍：色面の模様（色区 ID、白なし）"), ("claws", "爪"), ("spray", "飛沫（v0 と密）")]:
        v = [r[col] for r in R]
        k = len(v) - 1
        while k > 0 and v[k - 1] == v[-1]:
            k -= 1
        b181[col] = {"name_ja": name, "t_final": float(t[k]), "t_last_change": float(t[k - 1]) if k > 0 else None,
                     "distinct": len(set(v)), "final_at_tstar": abs(float(t[k]) - TSTAR) < 1e-12}
    wf = b181["white_flags"]
    tau_wf = float([r for r in R if float(r["exp"]) == wf["t_final"]][0]["tau"])
    white_count_final = int(R[-1]["white_count"])
    fine = rep["b181"]["fine"]
    fine_after_ok = all(f["allFinal"] for f in fine if f["t"] >= TSTAR)
    fine_before = [f for f in fine if f["t"] < TSTAR]
    visible_four = all(b181[c]["final_at_tstar"] for c in ("white_img", "indigo_img", "claws", "spray"))
    acc181 = visible_four and fine_after_ok

    # ---- 4. 物理の段が読む水の時刻（Play）
    lag = Counter((r["advance_before_physics"], r["fixed_lag_frames"]) for r in prow if r["fixed_this_frame"] == "1")
    dts = Counter(r["deltaTime"] for r in prow)

    # ---- 5. 出来事
    ev = rep["events"]
    evR_ok = len(ev["R"]) == 3 and all(e["fired"] for e in ev["R"]) and len({e["id"] for e in ev["R"]}) == 3 and all(0 <= e["clockT"] - e["eventT"] < rep["dt"] for e in ev["R"])
    evS3_ok = [(e["id"], e["fired"], e["clockT"]) for e in ev["S3"]] == [("t_star", False, 13.0), ("t_star", True, 12.0), ("hold_end", True, 14.0)]

    ab = rep["tstarAB"]
    metrics = {
        "schema": "GreatWave.DS46.clock_metrics/1",
        "number": "設計46",
        "part": "clock（共通時計）",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_kind_ja": "PC の Unity 6000.4.3f1 batchmode（RTX 3080、Direct3D11）。Editor の計算と描画、Editor の Play モード（batchmode で 1 フレームずつ回す、dt 0.02 s）。HMD 実機ではない。利用者は確かめていない",
        "plan_ja": "計画 §2.5 設計46：秒の時計 1 つ（GWClock。美術優先30 の最小版を広げる）で、水面・白・爪・飛沫・船用データ・演出を進める。停止・再開・初期化・途中からの再生",
        "min_acceptance_ja": "停止・再開・初期化・途中再生の後、同じ時刻で同じ形（頂点のハッシュが一致）。181（白・藍・爪・飛沫が同じ t* で終態）",
        "acceptance": [
            {"item": "同じ時刻で同じ形（Editor の 4 つの道）", "criterion": "形のハッシュ一式が基準の通しと一致",
             "value": {"compared": len(cmp_rows), "mismatched": mism, "hash_keys": keys_per, "stopped_32_steps_same": stop_same},
             "judge": "合格" if (mism == 0 and stop_same) else "不合格"},
            {"item": "同じ時刻で同じ形（Play モード）", "criterion": "Editor の基準の通しと一致（画像を除く形のデータ）、止めた 20 フレームで同じ",
             "value": {"compared_with_editor": pm_cmp, "mismatched": pm_mism, "stop_frames": stop_frames, "stop_same": pm_stop_same},
             "judge": "合格" if (pm_mism == 0 and pm_stop_same) else "不合格"},
            {"item": "181 白・藍・爪・飛沫が同じ t* で終態（見える状態の読み。採った読み）", "criterion": "描いた白・藍の色面・爪・飛沫の印が t* = 12.0 s で最終に達し、それより前には達しない（1/32 s の格子、t* のまわり 1/256 s）",
             "value": {k: b181[k] for k in ("white_img", "indigo_img", "claws", "spray")}, "judge": "合格" if acc181 else "不合格"},
        ],
        "acceptance_record": {
            "b181_white_arrival_ja": "白の到着の場（頂点の旗 T_white ≤ τ）は t = %.5f s（τ = %.4f s）で最終（白の頂点 %d）に達し、t* より %.3f s 早い。その後の白は面の動きと三角形の中の縁（g = τ − T_white）で t* まで動く。厳しい読み（白の到着そのものが t* で終わる）では早い → 限界として仕上げ46 へ" % (wf["t_final"], tau_wf, white_count_final, TSTAR - wf["t_final"]),
            "b181_white_flags": wf,
            "b181_hero_geometry": b181["hero"],
            "b181_fine_before_tstar": fine_before,
            "b181_fine_at_or_after_all_final": fine_after_ok,
            "sync_edit_steps": {"steps": len(steps), "bad": sync_edit},
            "sync_play_frames": {"frames": len(prow), "bad": sync_play},
            "tstar_painting_ab": {"diff_pixels_ds41_path_vs_clock": ab["diffPixels"], "diff_pixels_clock_vs_ds41_committed_output": ab["diffPixelsVsPriorDs41File"], "sha256": ab["ds46ClockSha256"]},
            "physics_reads_water": {"early_update_frames_lag0": lag.get(("1", "0"), 0), "early_update_frames_lag1": lag.get(("1", "1"), 0),
                                    "control_update_frames_lag1": lag.get(("0", "1"), 0), "control_update_frames_lag0": lag.get(("0", "0"), 0),
                                    "fixed_steps_per_frame": dict(Counter(r["fixed_count_this_frame"] for r in prow)), "deltaTime": dict(dts)},
            "events": {"R": ev["R"], "S3": ev["S3"], "S4": ev["S4"], "R_once_each_lag_lt_step": evR_ok, "S3_seek_skips_then_fires": evS3_ok},
            "stages": rep["stages"],
            "protected_unchanged": rep["protectedUnchanged"],
        },
        "backlog": {
            "181": "見える状態の読みで合格（描いた白・藍・爪・飛沫が t* = 12.0 s で最終、t* の後は変わらない）。白の到着の場は %.3f s 早く終わる（記録、仕上げ46）" % (TSTAR - wf["t_final"]),
            "199": "記録なし（性能は設計50 の通しと H2。この部では測っていない）",
        },
        "compare_rows": cmp_rows,
        "playmode_rows": pm_rows,
        "playmode_notes": pm["notes"],
        "painting_view_ja": "原画視点は変えていない：DS41_Boats.unity は SHA-256 のまま。時計の道で描いた t* の原画視点は、設計41 の道の描画・設計41 の出力 painting_t120_off.png と画素まで同じ（差 0 画素）。評価器は画素の関数なので値も同じ（回し直していない）",
        "hmd_ja": "PS VR2 は保留（導入は利用者の手）。この部は時計と形のデータだけで、両眼の描画は変えていない",
        "pass": bool(acc1 and acc181 and sync_edit == 0 and sync_play == 0 and ab["diffPixels"] == 0),
    }
    json.dump(metrics, open(OUT + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 図 1：時計の検査
    img = np.full((1080, 1920, 3), 236, np.uint8)
    put(img, "Design46 clock: one GWClock (Master) drives water -> boat water -> white -> claws -> spray -> events  (PC Unity batchmode, not HMD)", (20, 34), 0.62)
    # (a) Play の体験の時刻
    fr = np.array([int(r["frame"]) for r in prow]); ex = np.array([float(r["exp"]) for r in prow])
    ctl = np.array([r["advance_before_physics"] == "0" for r in prow]); stp = np.array([r["state"] == "Stopped" for r in prow])
    pa = Panel(img, 70, 80, 860, 400, (fr.min(), fr.max()), (0, 14.5), "(a) Play mode: experience time per frame (dt 0.02 s). grey = stopped, orange = control (advance in Update)", "t [s]")
    for i in range(len(fr)):
        if stp[i]:
            pa.span(fr[i] - 0.5, fr[i] + 0.5, (215, 215, 215))
        if ctl[i]:
            pa.span(fr[i] - 0.5, fr[i] + 0.5, (170, 210, 250))
    pa.line(fr, ex, (160, 60, 20), 2)
    for h in pm["hashes"]:
        X, Y = pa.X(h["frame"]), pa.Y(h["exp"])
        cv2.circle(img, (X, Y), 5, (30, 140, 30), -1, cv2.LINE_AA)
    pa.axes(list(range(0, int(fr.max()) + 1, 200)), [0, 2, 4, 6, 8, 10, 12, 14])
    cv2.putText(img, "green = hash taken: stop(5.02) x2, seek 8 after play, init, seek 8, seek 12, end 14, seek 12, seek 8, init", (75, 505), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (30, 100, 30), 1, cv2.LINE_AA)
    cv2.putText(img, "Play hashes vs Editor reference at same t: %d compared, %d mismatched. stop 20 frames same: %s" % (pm_cmp, pm_mism, pm_stop_same), (75, 528), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.putText(img, "physics (FixedUpdate) reads water of: same frame %d / %d frames (EarlyUpdate);  control: previous frame %d / %d" % (lag.get(("1", "0"), 0), lag.get(("1", "0"), 0) + lag.get(("1", "1"), 0), lag.get(("0", "1"), 0), lag.get(("0", "1"), 0) + lag.get(("0", "0"), 0)), (75, 551), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
    # (b) 181 の t* のまわり
    ft = np.array([f["t"] for f in fine]) - TSTAR
    pb = Panel(img, 1030, 80, 850, 400, (ft.min(), ft.max()), (-7, -3), "(b) 181 near t*: difference to final state (Seek, 1/256 s). log10; 0 plotted at bottom", "log10")
    for key, col, lab in [("clawsMaxDiffM", (40, 40, 200), "claws max |dx| m"), ("sprayMaxDiff", (30, 140, 230), "spray max |dx| m"), ("heroMaxDiffM", (150, 150, 150), "hero sheet max |dx| m")]:
        y = np.array([np.log10(f[key]) if f[key] > 0 else -7 for f in fine])
        pb.line(ft, y, col, 2, dots=True)
    pb.vline(0.0, (20, 20, 20))
    pb.axes([-8 / 256, -4 / 256, 0, 4 / 256, 8 / 256], [-7, -6, -5, -4, -3], "%.3f", "%g")
    y0 = 505
    for key, col, lab in [("clawsMaxDiffM", (40, 40, 200), "claws"), ("sprayMaxDiff", (30, 140, 230), "spray"), ("heroMaxDiffM", (150, 150, 150), "hero sheet")]:
        cv2.line(img, (1040, y0 - 4), (1070, y0 - 4), col, 2)
        cv2.putText(img, lab, (1076, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)
        y0 += 20
    txt = "white/indigo ID px diff (480x270) at t*-8/256..t*-1/256: " + ",".join(str(f["whiteImgDiffPx"]) for f in fine_before)
    cv2.putText(img, txt, (1200, 505), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.putText(img, "grid 1/32 s: final reached at t = %.3f (white img) %.3f (indigo) %.3f (claws) %.3f (spray)" % tuple(b181[c]["t_final"] for c in ("white_img", "indigo_img", "claws", "spray")), (1200, 528), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.putText(img, "white arrival flags final at t = %.5f s (tau %.4f s), %.3f s before t*  -> recorded limit (Polish46)" % (wf["t_final"], tau_wf, TSTAR - wf["t_final"]), (1200, 551), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (40, 40, 180), 1, cv2.LINE_AA)
    # (c) t* A/B
    a = cv2.imread(UNITY + "/tstar/painting_t120_off_ds41path.png"); b = cv2.imread(UNITY + "/tstar/painting_t120_off_ds46clock.png")
    d = (np.abs(a.astype(np.int16) - b.astype(np.int16)).max(2) > 0).astype(np.uint8) * 255
    tw, th = 600, 338
    for i, (im, lab) in enumerate([(a, "t* painting view: Design41 path (Seek each layer)"), (b, "t* painting view: Design46 clock.Seek(12)"), (cv2.cvtColor(d, cv2.COLOR_GRAY2BGR), "difference (white = differs): %d px" % int((d > 0).sum()))]):
        x = 30 + i * 630
        img[600:600 + th, x:x + tw] = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
        cv2.rectangle(img, (x, 600), (x + tw, 600 + th), (80, 80, 80), 1)
        cv2.putText(img, lab, (x, 592), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
    lines = [
        "Editor: %d checks on 4 paths (stop/resume, init, seek, seek while running) vs reference run R at same t: %d mismatched (%d hash keys incl. rendered painting image)" % (len(cmp_rows), mism, len(keys_per)),
        "sync: every step all 6 stages got the same time decision; layer t / tau equal: Editor %d steps, bad %d;  Play %d frames, bad %d" % (len(steps), sync_edit, len(prow), sync_play),
        "events (placeholder table for Design47): R fires formation_start@2.0, t_star@12.0, hold_end@14.0 once at the crossing step; Seek skips (no fire): %s" % ("ok" if evR_ok and evS3_ok else "NG"),
        "t* painting view identical to Design41 committed output (0 px) -> evaluator values unchanged (not re-run).  DS41_Boats.unity unchanged (SHA-256).",
    ]
    for i, s in enumerate(lines):
        cv2.putText(img, s, (30, 968 + 24 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (20, 20, 20), 1, cv2.LINE_AA)
    fig1 = OUT + "/fig_ds46_clock.png"
    cv2.imwrite(fig1, img)

    # ---- 図 2：時計の道の静止画（原画視点と座席 v1、t 8・10.5・12・13 s）
    img2 = np.full((1080, 1920, 3), 236, np.uint8)
    put(img2, "Design46 clock path stills (clock.Seek): painting view (top) and seat v1 (bottom); t = 12 is t*, t = 13 is the hold (same as t*)", (20, 34), 0.6)
    for r, view in enumerate(["painting", "seat"]):
        for c, tt in enumerate(["08.0", "10.5", "12.0", "13.0"]):
            im = cv2.imread(UNITY + "/stills/%s_t%s.png" % (view, tt))
            w, h = 460, 259
            x, y = 20 + c * 475, 90 + r * 480
            img2[y:y + h, x:x + w] = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
            cv2.rectangle(img2, (x, y), (x + w, y + h), (80, 80, 80), 1)
            cv2.putText(img2, "%s  t = %s s" % (view, tt), (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
    s12 = cv2.imread(UNITY + "/stills/painting_t12.0.png"); s13 = cv2.imread(UNITY + "/stills/painting_t13.0.png")
    same = int((np.abs(s12.astype(np.int16) - s13.astype(np.int16)).max(2) > 0).sum())
    cv2.putText(img2, "painting t=12.0 vs t=13.0 (hold): %d px differ" % same, (20, 1060), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1, cv2.LINE_AA)
    fig2 = OUT + "/stills_ds46_clock.png"
    cv2.imwrite(fig2, img2)

    code = ["Unity/Assets/GreatWave/ArtFirst/Scripts/GWClock.cs", "Unity/Assets/GreatWave/Design31/Scripts/DS31InstancedParticles.cs",
            "Unity/Assets/GreatWave/Design46/Scripts/DS46ClockBus.cs", "Unity/Assets/GreatWave/Design46/Scripts/DS46EventTrack.cs",
            "Unity/Assets/GreatWave/Design46/Scripts/DS46FixedProbe.cs", "Unity/Assets/GreatWave/Design46/Data/ds46_events.json",
            "Unity/Assets/GreatWave/Design46/Editor/DS46Probe.cs", "Unity/Assets/GreatWave/Design46/Editor/DS46ClockTest.cs",
            "Unity/Assets/GreatWave/Design46/Editor/DS46PlayModeCheck.cs", "Unity/Assets/GreatWave/Design46/Scenes/DS46_Clock.unity",
            "Tools/GWWaveGen/ds46/run_ds46_unity.ps1", "Tools/GWWaveGen/ds46/ds46_clock_report.py"]
    outs = [UNITY + "/ds46_clock_report.json", UNITY + "/ds46_steps.csv", PLAY + "/ds46_playmode.json", PLAY + "/ds46_playmode.csv",
            UNITY + "/tstar/painting_t120_off_ds41path.png", UNITY + "/tstar/painting_t120_off_ds46clock.png", OUT + "/metrics.json", fig1, fig2]
    run = {
        "schema": "GreatWave.DS46.clock_run/1", "number": "設計46", "part": "clock",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tools": {"python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__, "unity": "6000.4.3f1（batchmode、E:/6000.4.3f1/Editor/Unity.exe）"},
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds46/run_ds46_unity.ps1 -Method GreatWave.Design46.EditorTools.DS46ClockTest.Run -Log run1（93 s。場面の保存・t* の A/B・基準の通し・4 つの道・181）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds46/run_ds46_unity.ps1 -NoQuit -Method GreatWave.Design46.EditorTools.DS46PlayModeCheck.Run -Log playmode（43 s。Play モード）",
            "py -3.10 -B Tools/GWWaveGen/ds46/ds46_clock_report.py",
        ],
        "inputs_sha256": {p: sha(REPO + "/Unity/" + p) for p in ["Build/Design/28R01F/F_final/timewarp_F_final.json", "Build/Design/33/claws/ds33_claw_frames_f32.bin",
                                                                 "Build/Design/41/model/unity/full/painting_t120_off.png", "Assets/GreatWave/Design41/Scenes/DS41_Boats.unity"]},
        "code_sha256": {p: sha(REPO + "/" + p) for p in code},
        "outputs_sha256": {rel(p): sha(p) for p in outs},
        "unity_logs": {rel(p): sha(p) for p in [OUT + "/logs/unity_ds46_run1.log", OUT + "/logs/unity_ds46_playmode.log"]},
        "settings_restore": {n: json.load(open(OUT + "/logs/ds46_settings_restore_%s.json" % n, encoding="utf-8-sig")) for n in ("run1", "playmode")},
        "seconds_report": round(time.time() - T0, 1),
        "note_ja": "Play モードのログにある UnityEditor.Search.SearchDatabase の ArgumentOutOfRangeException は、Editor の起動時の検索の索引の作りで、設計34 の Play モードのログにも同じものがある（この番号のコードではない）",
    }
    json.dump(run, open(OUT + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("pass", metrics["pass"], "acc1", acc1, "181", acc181, "edit", len(cmp_rows), mism, "play", pm_cmp, pm_mism, "sync", sync_edit, sync_play, "lag", dict(lag))


if __name__ == "__main__":
    main()
