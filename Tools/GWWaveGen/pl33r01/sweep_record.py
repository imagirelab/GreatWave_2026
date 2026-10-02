# -*- coding: utf-8 -*-
"""仕上げ33修正01 変種 SWEEP：候補の証拠（metrics.json・run.json）をまとめる（新しい計算・描画はしない）。

読むもの（Git 対象外の Unity/Build/Polish/33r01/sweep/ の下）：measure/sweep_gates.json・sweep_measure.json・sweep_overlay.json・pl33f_measure_sweep.json・
  sweep_perf.json、claws/ds33_claw_layout.json・sweep_report.json、crown/pl33_crown.json、setup/sweep_setup.json、playmode_*/、release/unity/sweep_build.json、
  evidence/eye_verdicts.json（進行役が目で見た判定を書いた入力）。
書くもの：evidence/metrics.json、evidence/run.json（コマンド、道具の版、入出力の SHA-256、参照の読み）。図・動画の大きさの確かめ（PNG 1920×1080、MP4 ≤ 5 MB）。
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_record.py
"""
import glob
import hashlib
import json
import os
import platform
import shutil
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
S = REPO + "/Unity/Build/Polish/33r01/sweep"
EV = S + "/evidence"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jl(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8-sig"))
    except Exception:
        return default


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    os.makedirs(EV, exist_ok=True)
    # 小さい数の JSON を証拠のフォルダーへ写す
    copies = {}
    for src in ["measure/sweep_gates.json", "measure/sweep_measure.json", "measure/sweep_overlay.json", "measure/pl33f_measure_sweep.json",
                "measure/sweep_perf.json", "claws/sweep_report.json", "crown/pl33_crown.json", "setup/sweep_setup.json",
                "release/unity/sweep_build.json"]:
        p = os.path.join(S, src)
        if os.path.exists(p):
            dst = os.path.join(EV, os.path.basename(src) if not src.startswith("crown/") else "sweep_crown_report.json")
            shutil.copyfile(p, dst)
            copies[src] = rel(dst)
    for d in glob.glob(S + "/playmode_*"):
        for f in glob.glob(d + "/*.json"):
            dst = os.path.join(EV, os.path.basename(d) + "_" + os.path.basename(f))
            shutil.copyfile(f, dst)
            copies[rel(f)] = rel(dst)
    for f in glob.glob(S + "/measure/fig_*.png"):
        shutil.copyfile(f, os.path.join(EV, os.path.basename(f)))
    lay = jl(S + "/claws/ds33_claw_layout.json", {})
    rep = jl(S + "/claws/sweep_report.json", {})
    gates = jl(S + "/measure/sweep_gates.json", {})
    meas = jl(S + "/measure/sweep_measure.json", {})
    ovl = jl(S + "/measure/sweep_overlay.json", {})
    perf = jl(S + "/measure/sweep_perf.json", {})
    pm = jl(S + "/measure/pl33f_measure_sweep.json", {})
    eye = jl(EV + "/eye_verdicts.json", {})
    crown = jl(S + "/crown/pl33_crown.json", {})
    # 図・動画の確かめ
    media = []
    for f in sorted(glob.glob(EV + "/*.png")) + sorted(glob.glob(EV + "/*.mp4")):
        e = dict(file=rel(f), bytes=os.path.getsize(f), sha256=sha(f))
        if f.endswith(".png"):
            im = cv2.imread(f)
            e["size"] = [int(im.shape[1]), int(im.shape[0])]
            e["ok"] = e["size"] == [1920, 1080]
        else:
            e["ok"] = e["bytes"] <= 5 * 1024 * 1024
        media.append(e)
    fing = rep.get("fingers", {})
    s2c = {}
    for v in fing.values():
        k = "s2=%.2f w=%.2f" % (v.get("s2", 0), v.get("w_scale", 0))
        s2c[k] = s2c.get(k, 0) + 1
    metrics = {
        "schema": "GreatWave.Polish33R01.sweep_metrics/1",
        "number_ja": "仕上げ33修正01 変種 SWEEP（候補。採用は進行役が決める）",
        "variant_ja": "原画の爪 184 本を、原画のカメラの射線の上で深さを選んで立てた 3D の指（掃引の管）に置き換え、冠の爪を同じ断面の長く太い指に作り直した",
        "candidate_dir": rel(S),
        "claw_layer": {"entries": len(lay.get("claws", [])), "vertices": lay.get("vertices"), "triangles": lay.get("triangles"),
                       "fingers_C": sum(1 for c in lay.get("claws", []) if c["id"].startswith("C")),
                       "crown_K": sum(1 for c in lay.get("claws", []) if c["id"].startswith("K")),
                       "before_pl33_fix02": {"entries": 561, "vertices": 95547, "triangles": 183240},
                       "frames_bytes": (lay.get("files", {}).get("frames", {}) or {}).get("bytes"),
                       "summary": rep.get("summary"), "footprint_steps": s2c,
                       "crown_dropped": crown.get("dropped"), "crown_kept": len(crown.get("crowns", []))},
        "gates": gates.get("gates"), "raw_detail_with_claws": gates.get("raw_detail_with_claws"), "eval23": gates.get("eval23"),
        "overlay_vs_list": {"before": ovl.get("before"), "after": ovl.get("after")},
        "standing_images": meas.get("after", {}).get("images"), "standing_images_before": meas.get("before", {}).get("images"),
        "standing_geometry": {"before": meas.get("before", {}).get("geometry"), "after": meas.get("after", {}).get("geometry")},
        "pl33f_measure": {k: pm.get(k) for k in list(pm.keys())[:60]} if isinstance(pm, dict) else None,
        "perf": perf,
        "eye_ja": eye,
        "release_data_bytes": {"sweep": (jl(S + "/release/unity/sweep_build.json", {}) or {}).get("dataBytes"), "pl33_fix02": 1196466028},
        "notes_ja": [
            "pl33f_measure.py（仕上げ33 の数の道具）は輪の 8 頂点の平均を輪の中心としている。SWEEP の輪は頂点の角度が不揃い（白を約 9 割にするため）なので、平均は中心から −N（水色の版の側）へ最大で厚みの約 0.34 倍ずれる。"
            "そのため pl33f_measure_sweep.json の geometry.fix.penetration（C の輪が面より 5 cm 下：t 9・10.5・12 s で 205・280・250）と C_tstar_centre_tip_projection_shift_px は SWEEP では読み違い。"
            "輪の中心を頂点 2 と 6 の中点にした同じ式の数は sweep_measure.json の penetration_centre_v2v6（C：0・1・3、K：0・0・0。前の仕上げ33 は C 5・2・9、膜 6・3・10）。",
            "pl33f_measure_sweep.json の before＝仕上げ32 修正の回 1、build＝仕上げ33 修正の回 2（この変種の『前』）、fix＝SWEEP。",
            "sweep_measure.json の地ごとの爪の画素は、爪なしの描画の色で空（生成りの空と灰色の空）・藍・白に分けた近似。",
            "負荷はプレイヤー（Release、PC の 1920×1080 の窓、RTX 3080、Direct3D11）の FrameTimingManager の中央値で、HMD の実機ではない。2 組目の前（pl33_2）は別の作業の Unity の Editor が止まるのを待ってから動かした。",
            "Unity/Assets/GreatWave/Polish33R01.meta は同じ時に動いている別の変種（houdini）と共有のフォルダーの meta。"],
        "media": media,
        "copies": copies,
    }
    json.dump(metrics, open(EV + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # run.json
    import scipy
    files = {}
    for p in [S + "/claws/" + v["file"] for v in lay.get("files", {}).values()] + [S + "/claws/ds33_claw_layout.json"]:
        if os.path.exists(p):
            files[rel(p)] = {"bytes": os.path.getsize(p), "sha256": sha(p)}
    for p in glob.glob(REPO + "/Tools/GWWaveGen/pl33r01/sweep_*") + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish33R01/sweep/**/*.*", recursive=True):
        if os.path.isfile(p) and not p.endswith(".pyc"):
            files[rel(p)] = {"bytes": os.path.getsize(p), "sha256": sha(p)}
    inputs = {}
    for p in [REPO + "/Unity/Build/Polish/33/fix02/claws/ds33_claw_frames_f32.bin", REPO + "/Unity/Build/Polish/33/fix02/claws/ds33_claw_layout.json",
              REPO + "/Unity/Build/Polish/32/fix01/claws/ds33_claw_rig.json", REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json",
              REPO + "/Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json", REPO + "/Unity/Build/Polish/32/white/pl31_zone_vertex.npy",
              REPO + "/Tools/PaintingTruth/painting_truth.json", REPO + "/Docs/References/Met_JP1847_DP130155.jpg"]:
        if os.path.exists(p):
            inputs[rel(p)] = sha(p)
    for p in glob.glob(REPO + "/Unity/Build/Polish/32/white/hero_pkg/*"):
        inputs[rel(p)] = sha(p)
    run = {
        "schema": "GreatWave.Polish33R01.sweep_run/1",
        "commands_ja": [
            "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_build.py --no-crown <FARGS> --out Unity/Build/Polish/33r01/sweep/fingers",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_crown.py --scale 0.85 --seat-free --relief Unity/Build/Polish/33r01/sweep/fingers --out Unity/Build/Polish/33r01/sweep/crown",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_build.py <FARGS> --crown-src Unity/Build/Polish/33r01/sweep/crown --out Unity/Build/Polish/33r01/sweep/claws",
            "FARGS = --s2 1.5 --k3 4.5 --l3-min 1.2 --l3-max 5.0 --w-rel 0.18 --w-min 0.30 --w-max 0.7 --taper 1.8 --inside-min 0.995 --allow-dil 3",
            "描画：Unity/Build/Polish/33r01/sweep/run_render.sh r_final views,tt,t28,full,video（PL33Render、-pl32Claws Build/Polish/33r01/sweep/claws/ds33_claw_layout.json -pl33Look 1）",
            "評価器：pl28u_regress.py --scene <r_final> --kstar rec、evaluate.py ×4（線あり・線ありの爪なし・線なし・線なしの爪なし）、sweep_gates.py",
            "数：sweep_measure.py、sweep_overlay.py、Tools/GWWaveGen/pl33/pl33f_measure.py --fix-run <r_final> --fix-claws <claws> --build-run Build/Polish/33/fix02/r_fix02 --build-claws Build/Polish/33/fix02/claws",
            "図：sweep_sheets.py --after <r_final>（前＝Build/Polish/33/fix02/r_fix02）",
            "Unity：run_unity_steps.sh（PL33R01SweepSetup.BuildScenes、PL29PlayModeCheck ×2、PL33R01SweepReleaseBuild.BuildAll、sweep_run_player.ps1 ×4（仕上げ33 と SWEEP を交互に）、sweep_perf.py）",
            "記録：sweep_record.py"],
        "tools": {"python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__, "scipy": scipy.__version__, "platform": platform.platform(),
                  "unity": "6000.4.3f1（E:/6000.4.3f1/Editor/Unity.exe、batchmode）", "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"},
        "inputs_sha256": inputs,
        "outputs": files,
        "references_ja": [
            "参照の写真（利用者の指示 Q16 の例外 G:/research/reality scan/北斋参考、読み取りのみ）：フォルダーの一覧を取り、正面图.jpg・左45.jpg・右图.jpg・顶图、.jpg・背图.jpg の 5 枚の縮小の写しを"
            "会話の作業フォルダー（リポジトリの外の一時の場所）に作り、そのうち 3 枚（左45.jpg・右图.jpg・正面图.jpg）を画面で見た（頂と唇の指が縁から外へ突き出し、先で巻くこと、"
            "正面からは唇の縁の指が下へ垂れる房の輪に見えることの確かめ。作り方の参考だけで、形・寸法は写していない）。写しは同じ日に消した。画像・寸法・形・Exif はリポジトリと成果物に入れていない。",
            "参照モデル G:/research/model/wave_repair_zbrush2.obj、利用者の爪形分析 G:/research/爪形分析、G:/research/Wave Simulation はこの変種では開いていない。生成器は OBJ を読まない（F13-1）。",
            "原画：リポジトリの Docs/References/Met_JP1847_DP130155.jpg（重ね図の背景）。"],
    }
    json.dump(run, open(EV + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    bad = [m for m in media if not m["ok"]]
    print("SWEEP_RECORD_DONE media", len(media), "bad", bad)


if __name__ == "__main__":
    main()
