# -*- coding: utf-8 -*-
"""仕上げ29：群の終わりの記録（Docs/Evidence/Polish/29/metrics.json・run.json）を組む（py -3.10。新しい描画・計算はしない）。

前の点検（metrics_audit.json）・作る部（metrics_build.json）・修正の回（metrics_fix01.json）の記録と、群の終わりに回した
座席の射線の検査（ds29r01_measure qa、--qa）・コードの点検の再実行（--codecheck）から、バックログ項目 → 値 → 判定（合格／不合格／記録のみ）と、
閉じる目安・視点ごとの前後・限界をまとめる。判定の文は Polish_29_ja.md の第 7〜11 節と同じ（進行役の判断、Q24）。
参照の彫刻の写真は読まない（ref_material_numbers.json の数だけ）。参照モデルは読まない。

使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_final_record.py --qa <qa の要約 json> --codecheck <code_check.json>
        --moved <写真から作った作業用の画像を動かす前の sha256 の一覧> --start 2026-10-01T12:05 --end <時刻>
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import platform

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EV = os.path.join(REPO, "Docs", "Evidence", "Polish", "29")


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def load(name):
    return json.load(open(os.path.join(EV, name), encoding="utf-8"))


def qa_values(path):
    if not path or not os.path.isfile(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    out = {"file": rel(path), "sha256": sha(path), "runtime_s": d.get("runtime_s"), "rays": d.get("rays"), "command": d.get("command")}
    subj = list(d.get("subjects", {}).values())
    if subj:
        s = subj[0]
        keep = {}
        for k, v in s.items():
            if k in ("info",):
                continue
            keep[k] = v
        out["subject"] = keep
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qa", default="")
    ap.add_argument("--qa-verdict", default="", help="qa の数の読み（進行役が要約を読んで書く。例：'穴 0・開いた背面 0・切断端 0・継ぎ目 0'）")
    ap.add_argument("--qa-pass", default="", choices=["", "pass", "fail"])
    ap.add_argument("--codecheck", default="")
    ap.add_argument("--moved", default="")
    ap.add_argument("--start", default="2026-10-01T12:05")
    ap.add_argument("--end", default="")
    a = ap.parse_args()
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    au, bu, fx = load("metrics_audit.json"), load("metrics_build.json"), load("metrics_fix01.json")
    rf = load("run_fix01.json")
    rr = fx["renderReport"]
    rel_b = fx["release"]["build"]

    # 視点ごとの前後（前の点検の分類、修正の回の平らな芯と爪）
    per_view = {}
    for v, s in au["summaryByView"].items():
        fb = fx["clawMeltedIdReading"]["byView"].get(v, {})
        cs = fx["clawSeparation"]["fix_p29g"].get(v, {})
        cb = fx["clawSeparation"]["build_p29d"].get(v, {})
        per_view[v] = {
            "before_projection": {"images": s["images"], "projected_frac": s["directFrac"], "extrapolated_band_frac": s["bandFrac"],
                                  "flat_fill_frac": s["flatFillFrac"], "stretch_frac_of_hero": s["stretchFracOfHero"],
                                  "long_seams": s["seamSegmentsLong"], "flat_regions": s["flatRegions"], "flat_core_frac": s["flatCoreFracOfHero"],
                                  "claw_pieces": s.get("clawPieces"), "claw_pieces_melted": s.get("clawPiecesMelted")},
            "after_fix01": {"projected_frac": 0.0, "flat_core_frac": fb.get("after", {}).get("flatCoreFracOfHero"),
                            "flat_regions": fb.get("after", {}).get("flatRegions"),
                            "claw_pieces": cs.get("pieces"), "claw_readable_frac": cs.get("readableFrac"),
                            "claw_readable_frac_build": cb.get("readableFrac")},
            "sheet": "fig_pl29_ba_view_%s.png" % v if v != "turntable" else "fig_pl29c_ba_turntable_t060〜t120.png",
        }

    qa = qa_values(a.qa)
    qa_txt = a.qa_verdict or "（未測定）"
    qa_ok = {"pass": "合格（事前検査。判定は番号41）", "fail": "不合格（記録）", "": "記録のみ（未測定）"}[a.qa_pass]

    closing = [
        {"criterion_ja": "7 視点＋回り台、t 6・9・10.5・12 s で色面の引き伸ばしがない（目で見て）", "value": {
            "projection_stretch": "なし（材質は原画カメラを読まない）", "groove_effective_spacing_factor_p5_p50_p95": fx["stretch"]["after_grooves_octave"]["groove_effective_spacing_factor_p5_p50_p95"],
            "dots_anisotropy_p50_p95": fx["stretch"]["after_arc_ca"]["anisotropy_p50_p95"]}, "verdict": "満たす（管の中の点・粒の楕円は限界 5）"},
        {"criterion_ja": "同じく継ぎ目がない", "value": "見えない（視点ごとの前後の図・切り抜きの図）", "verdict": "満たす"},
        {"criterion_ja": "同じく平らな特徴のない壁がない", "value": {"flat_core_frac_outside_painting": {"projection": au["summaryNonPainting"]["flatCoreFracOfHero"],
                                                                                            "build": 0.022, "fix01": fx["clawMeltedIdReading"]["fix_p29g"]["flatCoreFracOfHero"]},
                                                                "flat_regions": {"projection": au["summaryNonPainting"]["flatRegions"], "build": 41,
                                                                                 "fix01": fx["clawMeltedIdReading"]["fix_p29g"]["flatRegions"]}},
         "verdict": "満たす（残るのは背の白い殻。彫刻と同じ作り）"},
        {"criterion_ja": "同じく爪が読める", "value": {v: fx["clawSeparation"]["fix_p29g"][v]["readableFrac"] for v in fx["clawSeparation"]["fix_p29g"]},
         "verdict": "満たさない（原画視点・座席・座席から波の方向では読める。側面・後ろ・真上・回り台では読めない。造形は仕上げ32・33。限界 1）"},
        {"criterion_ja": "原画視点の形の関門（78・130・131 の定義、132・72 σ12）が後退しない", "value": fx["gatesPaintingView"], "verdict": "満たす（P28R2rec と同じ値）"},
        {"criterion_ja": "色区の項目 73〜270 を新しい読みで測り直して記録する", "value": "colour_items_new_reading", "verdict": "満たす（記録。値は動き、ほとんど不合格）"},
        {"criterion_ja": "コードの点検で、主役波・海の材質の道に原画カメラの投影がない", "value": {"code_check_fix01_allPass": fx["codeCheck"]["allPass"],
                                                                                 "rerun_at_record": (json.load(open(a.codecheck, encoding="utf-8")).get("allPass") if a.codecheck and os.path.isfile(a.codecheck) else None)},
         "verdict": "満たす"},
        {"criterion_ja": "原画視点でも原画に似る（Q28）", "value": {k: fx["paintingMatch"][k].get("白と藍の一致") for k in ("projection", "build_p29d", "fix_p29g_claws1")},
         "verdict": "一部（目で見て作る部より近い。数は同じ程度。限界 3）"},
    ]

    backlog = {
        "83": {"value": "座席 v1 の射線（穴・開いた背面・切断端）：" + qa_txt, "verdict": qa_ok},
        "115": {"value": "同上", "verdict": qa_ok},
        "116": {"value": "同上", "verdict": qa_ok},
        "117": {"value": "原版（減面なし、K*′ P28R2rec の格子 240×400）：継ぎ目の切断・穴は上の qa の数。材質の置き換えは網を変えない。"
                         "軽量版（間引きの格子）に面の座標を付けていない（限界 6）", "verdict": ("合格（原版。事前検査、判定は番号41）" if a.qa_pass == "pass" else qa_ok) + "／軽量版は未"},
        "Q28": {"value": "投影の焼き込みをやめ、視点によらない立体の材質（面の座標・高さ・面の向き・T_white）にした。閉じる目安 8 のうち 6",
                "verdict": "一部（爪の読み＝満たさない、原画らしさ＝一部）"},
        "Q16_F7-1_render": {"value": {"fps30_window_270_345_M1b": {"projection": 52069, "build": 55492, "fix01": 80988},
                                      "hz90_M1b_sum": {"projection": 1192, "build": 5411, "fix01": 11849}},
                             "verdict": "満たさない（限界 2。細い模様の 30 fps の通り過ぎ。HMD の 90／120 Hz で決める）"},
    }

    rows = [
        {"row_ja": "［利用者の言葉］Q28", "verdict": "一部（閉じる目安 8 のうち 6）"},
        {"row_ja": "［利用者の言葉］Q16 F7-1 の描画の側", "verdict": "満たさない（限界 2）"},
        {"row_ja": "唇の端の梯子・モアレ", "value": fx["lipDashes"], "verdict": "一部（t 12 s は消えた、t 10.5 s は 12 片 58 px が残る。限界 4）"},
        {"row_ja": "縦の継ぎ目・前面の足の縦の筋・原画視点の左端の横縞", "verdict": "消えた（投影と外挿の帯から来ていた）"},
        {"row_ja": "座席から波の方向のコマ 330〜420 の継ぎ目に沿う線", "verdict": "一部（線は設計38 の外殻線。仕上げ38）"},
        {"row_ja": "座席の見えない内壁の平らな藍濃・左の横の外挿の帯", "verdict": "消えた"},
        {"row_ja": "行 234〜239 の張り直し（HMD で見えた時だけ）", "verdict": "保留（HMD）"},
        {"row_ja": "軽量版の作り直し", "verdict": "未（限界 6。新しい材質は UV3 の表を使わない）"},
        {"row_ja": "仕上げ28 で形が変わっていれば最初に焼き直す", "verdict": "済（焼き込みをやめ、面の座標を P28R2rec の t* から作った）"},
        {"row_ja": "周りの海のシートを主役波と揃える", "verdict": "一部（調色板は揃えた。溝・白い殻は仕上げ30）"},
    ]

    limits = [
        "爪が側面・後ろ・真上・回り台で読めない（Q28）。造形（設計33 の細い帯、K*′ R4 への結び付けのまま）なので仕上げ32・33",
        "F7-1（Q16）の 30 fps の数えが増えた（52,069 → 80,988）。細い模様の通り過ぎ。HMD の 90／120 Hz で決める",
        "原画視点で原画に似ることは一部（白と藍の一致 0.812、色区の一致 0.561）",
        "唇の先の梯子が t 10.5 s の管の内壁の折り返しに残る（12 片・58 px）",
        "点・泡の粒・房の座標 (sa, ca) が管の中で楕円に伸びる（異方性 p95 17.6）",
        "軽量版に面の座標を付けていない",
        "GPU：主役波の面は 2 眼で約 0.95 ms（投影 0.49 ms）。壁時計の見当で、HMD 実機では未検証",
        "設計50 の DS50_Release.unity と Build/Design/50/release の exe は投影のまま（記録のため）。体験の Release は PL29ReleaseBuild で作る",
    ]

    metrics = {
        "schema": "GreatWave.Polish29.metrics/1",
        "number": "仕上げ29（設計29 表示用サーフェス）",
        "backlog_items": "83、115〜117（最初の項目は［利用者の言葉］Q28）",
        "made_local": now,
        "state_ja": "閉じる目安 8 のうち 6 を満たす（一部 1：原画視点で原画に似ること、満たさない 1：側面・後ろ・真上・回り台の爪）。"
                    "［利用者の言葉］Q16 の F7-1 は満たさない。作る部と修正の回（Q28 の 2 回目の枠）で修正の枠を使い切り、残りは限界として 10/29 以降へ送る。"
                    "進行役の自己評審の前。HMD 実機の結果ではない。利用者は確かめていない。",
        "evidence_kind_ja": "Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）、Editor の Play モード、Release のプレイヤーを PC で 1 回動かした結果、"
                            "numpy の測り（色区・平らな面・爪・F7-1・伸び縮み）、原画視点の評価器 23、Blender 5.2.2 の座席の射線（qa）、コードの点検。HMD 実機の結果ではない。",
        "adopted": {
            "shape": {"gwb": rr["heroMeshGwb"], "gwb_sha256": rr["heroMeshSha256"],
                      "meta_sha256": "90f8dbe1d04be6b9d25f7321645f9d472747cfc01737bd69f8ea4a8418c42a84"},
            "motion": {"package": rr["heroPackage"], "keypose_json_sha256": rr["heroPackageJsonSha256"], "timewarp": rr["timewarp"], "timewarp_sha256": rr["timewarpSha256"]},
            "material": {"shader": rr["heroShader"], "material": rr["material"], "material_sha256": rr["materialSha256"],
                         "params": "Tools/GWWaveGen/pl29/pl29_material_params.txt", "params_sha256": rr["paramFileSha256"], "params_values": fx["materialParams"]},
            "surface_coords": {"file": rr["attr"], "sha256": rr["attrSha256"], "generator": "Tools/GWWaveGen/pl29/pl29_hero_attr.py（--param arc）"},
            "claws": {"shader": "GreatWave/Polish29/PL29 Claw Shade", "material": rr["clawMaterial"], "material_sha256": rr["clawMaterialSha256"], "steps": fx["clawParams"]},
            "scenes": ["Unity/Assets/GreatWave/Polish29/Scenes/PL29_Release.unity", "Unity/Assets/GreatWave/Polish29/Scenes/PL29_SinglePlayback.unity"],
            "release": {"build": "PL29ReleaseBuild（PL29_Release.unity だけ）", "exe_sha256": rel_b["exeSha256"], "data_files": rel_b["dataFiles"], "data_bytes": rel_b["dataBytes"],
                        "bake_files_absent": rel_b["bakeFilesAbsent"]},
        },
        "q28_cause_before": {"noteJa": "前の点検（PL29Audit）。原画視点の外の 71 枚（7 視点＋回り台、4 時刻）で、主役波の見える画素の色の出どころを焼き込みのテクセルの種類で数えた。",
                             "outside_painting": au["summaryNonPainting"], "painting_view": au["summaryPainting"],
                             "painting_camera_identical_to_bake": True, "identity_check_painting_t120": au["identityCheckPaintingT120"]},
        "per_view_before_after": per_view,
        "closing_criteria_plan_5_3": closing,
        "closing_criteria_met": "6/8（一部 1・満たさない 1）",
        "backlog": backlog,
        "seat_ray_qa_G_p28rec": qa,
        "polish29_rows_plan_5_3": rows,
        "painting_view_gates": fx["gatesPaintingView"],
        "evaluator23": fx["evaluator23"],
        "colour_items_new_reading": fx["colourItemsNewReading"],
        "painting_match": fx["paintingMatch"],
        "claw_separation": fx["clawSeparation"],
        "lip_dashes": fx["lipDashes"],
        "stretch": fx["stretch"],
        "f71": fx["f71"],
        "gpu": fx["gpu"],
        "limits_ja": limits,
        "study_numbers": {"file": "ref_material_numbers.json", "sha256": sha(os.path.join(EV, "ref_material_numbers.json")),
                          "noteJa": "参照の彫刻（他者の展示作品、作者・所蔵は未確認）の写真と摺りの工程の写真から読んだ数値・比率だけ。出典はフォルダーとファイルの名前。写真・写真から作った画像・Exif は入れていない。"},
        "parts": {"audit": "metrics_audit.json・catalogue_audit.json", "build": "metrics_build.json", "fix01": "metrics_fix01.json"},
    }
    json.dump(metrics, open(os.path.join(EV, "metrics.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)

    moved = None
    if a.moved and os.path.isfile(a.moved):
        lines = [l.split() for l in open(a.moved, encoding="utf-8") if l.strip()]
        moved = {"count": len(lines), "noteJa": "調べ（STUDY）が Git 対象外の Unity/Build/Polish/29/study/view/ に置いた、写真から作った作業用の縮小・切り抜き（jpg）。"
                                                 "AGENTS.md の Q16（一時データはリポジトリの外）と調べの記録の「仕上げ29 の終わりに消す」に合わせ、群の終わりに、"
                                                 "リポジトリの外のこの会話の一時フォルダー（C: ドライブ）へ動かした（消してはいない。中身は開いていない）。動かす前と後の SHA-256 は同じ。",
                 "files_sha256": {l[1].lstrip("*").lstrip("./"): l[0] for l in lines}}
    evidence = {}
    for p in sorted(glob.glob(os.path.join(EV, "*"))):
        n = os.path.basename(p)
        if n in ("run.json",):
            continue
        evidence[n] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
    run = {
        "schema": "GreatWave.Polish29.run/1",
        "made_local": now,
        "timing": {"group_start": a.start, "record_end": a.end or now,
                   "parts": {"study": "12:05〜12:25", "audit": "〜12:31", "build": "12:33〜14:02", "fix01": "14:22〜15:45", "record": "15:46〜"}},
        "parts": {"audit": "run_audit.json", "build": "run_build.json", "fix01": "run_fix01.json"},
        "tools": {"python": platform.python_version(), "unity": "6000.4.3f1（batchmode、unity.lock で 1 つずつ、Direct3D11、RTX 3080）",
                  "blender": "Steam Blender 5.2.2（座席の射線の qa だけ）", "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build", "houdini": "使っていない"},
        "record_commands": [
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_view_sheets.py --before Unity/Build/Polish/29/before/p28 --after Unity/Build/Polish/29/fix01/p29g "
            "--audit Docs/Evidence/Polish/29/metrics_audit.json --fix Docs/Evidence/Polish/29/metrics_fix01.json --out Docs/Evidence/Polish/29",
            "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py qa --kstar Unity/Build/Polish/28/kstar_p28rec --package G_p28rec=Unity/Build/Polish/28/G_p28rec/art_on "
            "--out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/record/qa_G_p28rec",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_code_check.py …修正の回と同じ引数… --out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/record/codecheck（再実行。修正の回の code_check_fix01.json と鍵ごとに同じ）",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_final_record.py --qa … --codecheck … --moved …",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28_commit_deps.py Unity/Build/Polish/29/commit/seed.txt Unity/Build/Polish/29/commit_list.txt Unity/Build/Polish/29/commit/commit_deps_report.json",
        ],
        "code_check_rerun": ({"file": rel(a.codecheck), "sha256": sha(a.codecheck), "allPass": json.load(open(a.codecheck, encoding="utf-8")).get("allPass")}
                             if a.codecheck and os.path.isfile(a.codecheck) else None),
        "seat_ray_qa": qa,
        "reference_use": {
            "reference_model": "参照モデル wave_repair_zbrush2.obj は、仕上げ29 のどの部でも開いていない（各部の報告）。生成器は読まない（F13-1）。",
            "photos": "G:\\research\\reality scan\\北斋参考 の写真は、調べ（STUDY）で読み取りだけに使い、数値・比率だけを ref_material_numbers.json に書いた。修正の回は調べの作業用の縮小の一覧を見ただけ。"
                      "写真と写真から作った画像は、リポジトリと証拠に入れていない。Exif は写していない。",
            "wave_simulation_q27": "使っていない。",
            "incident": "調べの最初の一覧の命令で、許されたフォルダーの親 G:\\research\\reality scan の直下の名前の一覧を取った（ファイルは開いておらず、作ったものはない。名前は記録に写していない）。",
        },
        "photo_derived_temp_images_moved_out": moved,
        "evidence_sha256": evidence,
        "build_outputs_git_ignored": {"attr_fix01": {"path": rr["attr"], "sha256": rr["attrSha256"]},
                                      "release_exe": {"path": "Unity/Build/Polish/29/release/player/GreatWave50.exe", "sha256": rel_b["exeSha256"]},
                                      "renders": "Unity/Build/Polish/29/before/p28・after/p29d・fix01/p29g（全部の描画・診断・回り台・F7-1・動画）"},
    }
    json.dump(run, open(os.path.join(EV, "run.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print("metrics.json", os.path.getsize(os.path.join(EV, "metrics.json")), "run.json", os.path.getsize(os.path.join(EV, "run.json")), "evidence", len(evidence))


if __name__ == "__main__":
    main()
