# -*- coding: utf-8 -*-
"""流体の試作（先生の指示 Q37）の証拠を Docs/Evidence/FLIPPrototype/ へまとめる。

新しい計算はしない。Git 対象外の Unity/Build/FLIP37/ にある動画・静止画・表を写し、
runs.jsonl を要約した表、metrics.json（項目 → 値 → 合格／不合格／記録のみ）、
run.json（道具・場面・キャッシュ・描画・写した証拠の SHA-256）を書く。

使い方：py -3.10 -B Tools/GWWaveGen/flip37/fp_deliver.py [copy|tables|metrics|run|all]
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/FLIP37"
EVID = REPO + "/Docs/Evidence/FLIPPrototype"
FFPROBE = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
MAX_MP4 = 30 * 1024 * 1024

# 写す物：(証拠の名前, Build/FLIP37 からの元, 説明)
COPIES = [
    # 動画
    ("fp_v1_painting_cam_rt.mp4", "video/P3_curl_rt.mp4",
     "実時間 19.6 s。上の左＝原画カメラ（PaintingCam v1）、右＝左前の斜め。t=0〜t* 8.54 s、t* で 2 秒止めて三枚の図、回り台 12 方位、R9 との比べ（情報）、続き 1 秒。毎コマ【物理だけ・誘導なし】"),
    ("fp_v2_curl_slow.mp4", "video/P3_curl_slow.mp4",
     "最後の 3 秒（6.54〜9.54 s）を 0.5 倍、t* で 2 秒止める。8.0 s"),
    ("fp_v3_oblique_P3_clay.mp4", "P3/H25_R18_mg/clay_P3place.mp4",
     "P3 の主役の範囲（粒子 0.25 m）、t 6.0〜11.8 s を 0.5 倍。左＝左前の斜め、右＝原画カメラ。巻いて管が閉じ、唇が落ちるまで"),
    ("fp_v4_P1_section_best.mp4", "P1/section_best.mp4",
     "P1 断面の水槽（粒子 0.25 m、B025H32）。伝わる → 立ち上がる → 巻く → 空洞が閉じる。物理だけ"),
    ("fp_v5_P2g_guided_twin.mp4", "P2g/compare_clay.mp4",
     "P2g：上＝G0 物理だけ（双子）、下＝G1 物理＋誘導（上限の中）。誘導は採らなかった"),
    # 静止画
    ("fp_1_tstar_compare.png", "video/hold.png",
     "t* 8.54 s の比べ：① 原画 ② 流体の粘土・原画カメラ ③ シルエットと原画の輪郭（IoU 0.562・145 px）、下の段に左前の斜めと z=0 の断面"),
    ("fp_2_turntable12.png", "video/turntable.png", "t* の流体を 12 方位から（粘土）"),
    ("fp_3_strip.png", "video/strip.png", "動き全体のコマの帯（0〜9.54 s、2 つの固定カメラ）"),
    ("fp_4_candidates.png", "video/candidates.png", "t* とほかの候補 3 つ（8.29・8.04・8.79 s）"),
    ("fp_5_section_z000.png", "P3/H25_R18_mg/section_z000_compare.png",
     "z=0 の断面：流体（P3、t* 8.54 s）と原画の読み A、R18"),
    ("fp_6_camsweep.png", "video/camsweep/camsweep_v1_vs_best.png",
     "カメラを変えた比べ（情報だけ）：本番の v1 と、最も原画に近い遠い望遠のカメラ"),
    ("fp_7_r9_info.png", "video/r9_compare.png", "見本06 R9 と流体を同じカメラで並べた（情報だけ。R9 は目標ではない）"),
    ("fp_8_P2g_twin.png", "P2g/fig_compare.png", "P2g：誘導あり G1 と誘導なし G0 の比べ"),
    ("fp_9_P1_section_compare.png", "P1/compare_best.png", "P1：断面のいちばん良い計算と原画の読み A"),
    ("fp_10_P3_validation.png", "P3/validation.png", "P3：主役の範囲の箱が R18 を再現するかの確かめ（T0〜T0d）"),
    # 表
    ("p1_table.json", "P1/table.json", "P1 断面の探索の表（16 の組み合わせ）"),
    ("p2_table.json", "P2/table.json", "P2 粗い 3D の岩棚の探索の表"),
    ("p2g_compare.json", "P2g/compare.json", "P2g 誘導の双子の比べ（仕事・エネルギー・形）"),
    ("p3_compare_R18.json", "P3/H25_R18_mg/compare_R18.json", "P3 と R18 の比べ、断面の出来事の時刻"),
    ("p3_place.json", "P3/H25_R18_mg/place_p3.json", "P3 の置き方（ψ 30°・倍率 1.1・頂の位置、4×4 の行列）"),
    ("video_scores.json", "video/scores_24826e1b.json", "動画の各コマの原画カメラのシルエットの点数"),
    ("video_camsweep.json", "video/camsweep/camsweep.json", "カメラを変えた比べの全部の値（308 台）"),
]

TOOLS_DIRS = ["Tools/GWWaveGen/flip37", "Tools/GWWaveGen/flip36"]
SCENES = [
    "Houdini/FLIP36/p0_tank.hiplc",
    "Houdini/FLIP37/p0_tank.hiplc",
    "Houdini/FLIP37/p1_tank.hiplc",
    "Houdini/FLIP37/p2_tank.hiplc",
    "Houdini/FLIP37/p2g_tank.hiplc",
    "Houdini/FLIP37/p3_window.hiplc",
    "Unity/Build/FLIP37/P0/p0_tank_FLIP36_orig.hiplc",
    "Unity/Build/FLIP37/P2/p2_tank_v1_R00.hiplc",
    "Unity/Build/FLIP37/P2/p2_tank_v2_R01-R12.hiplc",
    "Unity/Assets/GreatWave/FLIP37Proto/Scenes/F37Proto.unity",
]
# キャッシュ：ディレクトリは「相対パス + SHA-256」の並びの SHA-256（manifest）。ckpt は大きさだけ
CACHE_DIRS = [
    "P3/H25_R18_mg/mesh",
    "P3/H25_R18_mg/sec",
    "P3/C18_export/fields",
    "P2/R18_X30L120LG_H39",
    "P2g/G0_R18_twin",
    "P2g/G1_R18_drag010",
    "P1/B025H32_T14_H32_n4_hr26",
    "video/_hf_R18",
]
CACHE_FILES = [
    "P3/H25_R18_mg/mesh/mesh_0206.npz",
    "P3/H25_R18_mg/place_p3.json",
    "P3/H25_R18_mg/compare_R18.json",
] + ["P3/H25_R18_mg/hf_%s.npz" % c for c in "ABCDEFGHIJKL"]
CKPT_DIRS = [
    "P3/H25_R18_mg/ckpt", "P3/C18_export/ckpt", "P2/R18_X30L120LG_H39/ckpt",
    "P2g/G0_R18_twin/ckpt", "P2g/G1_R18_drag010/ckpt", "P1/B025H32_T14_H32_n4_hr26/ckpt",
]
RENDER_DIRS = [
    "video/frames_rt", "video/frames_slow", "video/render", "video/turntable",
    "video/camsweep/render", "P3/H25_R18_mg/movie_frames_own",
]
RECORDS = [
    "P0/record_ja.md", "P1/record_ja.md", "P2/record_ja.md", "P2g/record_ja.md",
    "P3/record_ja.md", "video/record_ja.md", "integration_prep/record_ja.md",
    "integration_prep/integration_plan_ja.md", "runs.jsonl",
    "video_tools/configs/video_P3_curl.json",
]


def sha(path, buf=8 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk(d, skip=("ckpt", "__pycache__")):
    out = []
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in skip)
        for fn in sorted(files):
            if fn.endswith(".pyc"):
                continue
            p = os.path.join(root, fn)
            out.append(os.path.relpath(p, d).replace("\\", "/"))
    return out


def manifest(d):
    items = walk(d)
    lines = []
    total = 0
    for rel in items:
        p = os.path.join(d, rel)
        total += os.path.getsize(p)
        lines.append("%s %s" % (rel, sha(p)))
    m = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return {"files": len(items), "bytes": total, "manifest_sha256": m,
            "how_ja": "相対パスと SHA-256 の行（名前の順）を改行でつないだ文字列の SHA-256。ckpt と __pycache__ は除く"}


def dirsize(d):
    n = 0
    s = 0
    for root, _, files in os.walk(d):
        for fn in files:
            n += 1
            s += os.path.getsize(os.path.join(root, fn))
    return n, s


def rel(s):
    if isinstance(s, str):
        return s.replace(REPO + "/", "").replace(REPO.replace("/", "\\") + "\\", "")
    if isinstance(s, dict):
        return {k: rel(v) for k, v in s.items()}
    if isinstance(s, list):
        return [rel(v) for v in s]
    return s


def probe(path):
    try:
        out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name",
                              "-of", "json", path], capture_output=True, text=True, timeout=60).stdout
        j = json.loads(out)
        st = [s for s in j.get("streams", []) if "width" in s][0]
        return {"duration_s": round(float(j["format"]["duration"]), 3), "w": st["width"], "h": st["height"],
                "codec": st.get("codec_name")}
    except Exception as e:  # noqa
        return {"error": str(e)}


def do_copy():
    os.makedirs(EVID, exist_ok=True)
    rows = []
    for name, src, note in COPIES:
        s = os.path.join(B, src)
        d = os.path.join(EVID, name)
        shutil.copy2(s, d)
        r = {"name": name, "from": "Unity/Build/FLIP37/" + src, "bytes": os.path.getsize(d),
             "sha256": sha(d), "note_ja": note}
        if name.endswith(".mp4"):
            r.update(probe(d))
            r["le_30MB"] = r["bytes"] <= MAX_MP4
            if not r["le_30MB"]:
                raise SystemExit("MP4 が 30 MB を超えた：" + name)
        rows.append(r)
        print("copy", name, r["bytes"])
    json.dump(rows, open(os.path.join(EVID, "copies.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def load_runs():
    return [json.loads(l) for l in open(B + "/runs.jsonl", encoding="utf-8") if l.strip()]


def do_tables():
    runs = load_runs()
    keep = ["stage", "run_id", "part", "date", "kind", "houdini", "hip", "hip_sha256", "parms", "f_start", "f_end_req",
            "f_end_done", "fps", "particles_first", "particles_max", "particles_last", "wall_total_s", "wall_launch_s",
            "wall_per_frame_median_s", "io_per_frame_median_s", "mesh_per_frame_median_s", "rss_peak_gb", "ckpt_files",
            "ckpt_gb", "stopped", "concurrent_with", "guide", "note"]
    table = []
    for r in runs:
        t = {k: rel(r[k]) for k in keep if k in r}
        table.append(t)
    agg = {}
    for r in runs:
        st = r.get("stage")
        a = agg.setdefault(st, {"rows": 0, "sim_launches": 0, "wall_sum_s": 0.0, "max_launch_s": 0.0,
                                "rss_peak_gb": 0.0, "particles_max": 0, "stopped_or_killed": 0})
        a["rows"] += 1
        rid = r.get("run_id", "")
        if rid.startswith("NOTE") or r.get("kind") in ("render_only", "analysis_only"):
            continue
        w = r.get("wall_launch_s") or (None if rid.endswith("_merged") else r.get("wall_total_s"))
        if w and not rid.endswith("_merged"):
            a["sim_launches"] += 1
            a["wall_sum_s"] += float(w)
            a["max_launch_s"] = max(a["max_launch_s"], float(w))
        if r.get("rss_peak_gb"):
            a["rss_peak_gb"] = max(a["rss_peak_gb"], float(r["rss_peak_gb"]))
        if isinstance(r.get("particles_max"), (int, float)):
            a["particles_max"] = max(a["particles_max"], int(r["particles_max"]))
        stp = str(r.get("stopped") or "")
        if (stp and not stp.startswith("chunk_end")) or "killed" in rid or "aborted" in rid or "paused" in rid:
            a["stopped_or_killed"] += 1
    for a in agg.values():
        a["wall_sum_h"] = round(a["wall_sum_s"] / 3600.0, 2)
        a["wall_sum_s"] = round(a["wall_sum_s"], 1)
    tot = sum(a["wall_sum_s"] for a in agg.values())
    out = {
        "schema": "GreatWave.FLIPProto.runs_table/1",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "Unity/Build/FLIP37/runs.jsonl",
        "source_sha256": sha(B + "/runs.jsonl"),
        "note_ja": "runs.jsonl の全行（98 行）。パスはリポジトリからの相対にした。sim_launches は 1 回の起動ごと（_merged の行と NOTE・描画の行は数えない）。wall_sum は起動の壁時計の合計（途中で止めて run.json の無い起動（P2 の R08・R10 の部分 A・R18 の部分 A、P3 の H25_R18 など）は時間が記録されていないので入らない。合計は下限）。stopped_or_killed は見張りの停止・手で止めた・中止の数（区切りの終わり chunk_end は数えない）。P2 の R10・R12 は Q38 の決まりで 2 本同時、P3 の T0・T0b は C18_export と同時（決まりに反した。P3 の記録 §0）",
        "per_stage": agg,
        "all_stages_wall_sum_h": round(tot / 3600.0, 2),
        "runs": table,
    }
    json.dump(out, open(EVID + "/runs_table.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(agg, ensure_ascii=False, indent=1))
    print("total h", round(tot / 3600.0, 2))


def m(item, value, target, result, src):
    return {"item_ja": item, "value": value, "target": target, "result": result, "source": src}


def do_metrics():
    rt = json.load(open(EVID + "/runs_table.json", encoding="utf-8"))
    ps = rt["per_stage"]
    p3 = ps["P3"]
    met = {
        "schema": "GreatWave.FLIPProto.metrics/1",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note_ja": "先生の指示 Q37 の独立した試作（Houdini FLIP、P0〜P3 と確かめの動画）の主な数。result は 合格／不合格／記録のみ／利用者が判定。形が原画に届いたかを決めるのは利用者（Q28・Q30）。原画視点の輪郭 ≤4 px は Q37 で記録だけになった。値はどれも Unity/Build/FLIP37 の各段の記録と表から写した（新しい計算はしていない）",
        "best_run": {
            "id": "P3 H25_R18_mg",
            "what_ja": "P2 の R18（±30° で交わる二つの波の列＋中央の集まるレンズ＋低い棚 2 つ、周期 14 s、入力 39 m、粒子 1 m）を、主役の範囲 x 300〜640 m・z −70〜+70 m だけ粒子 0.25 m・格子 0.5 m で計算し直した。外の海は R18 から境界で渡す（一方向）。物理だけ・誘導なし",
            "t_star_s": 8.542, "t_star_frame": 206,
            "placement": {"psi_deg": 30, "scale": 1.1, "anchor_sim": [534.25, 20.58, -0.25]},
        },
        "milestone_ja": {
            "巻き込みのある波を物理だけで作る": "できた（先生の指示の組み込みの条件「巻き込みが生じる波が作れるようになったら」を満たす）",
            "原画に似た形": "まだ（似ているのは z=0 の断面の頭だけ）。利用者が判定する",
        },
        "items": {
            "M1_plunge_physics_only": m("物理だけで巻く（唇の下に空気を閉じこめる断面の数）", "7/7（z −60〜+60 m）", "巻く", "合格",
                                        "P3/record_ja.md §4.2、sec/z*/analysis.json"),
            "M1_air_trap_first_s": m("空気を本当に閉じこめた最初の時刻", {"z0": 8.88, "z+20": 8.79, "z-20": 8.88, "z+40": 9.29,
                                                                "z-40": 9.12, "z+60": 11.04, "z-60": 10.88},
                                     "—", "記録のみ", "P3/record_ja.md §4.2"),
            "M1_air_trap_area_z0_m2": m("z=0 の閉じこめた空気の広さ（10.9 s）", 108, "—", "記録のみ", "P3/record_ja.md §4.2"),
            "M1_sequence_continuous": m("伝わる → 立ち上がる → 巻く が途切れない（時間の伸縮・形の引き寄せ・投影での合わせなし）",
                                        "途切れなし。2.96 s の P2→P3 の切り替えで形は跳ばない", "続いている", "合格",
                                        "video/record_ja.md §9"),
            "M1_events_z0_s": m("z=0 の出来事（巻き始め B>0.85 / 前の面が垂直を越す / 管が閉じる）", [6.71, 7.29, 8.88],
                                "—", "記録のみ", "P3/record_ja.md §4.2"),
            "G_guiding_in_best": m("いちばん良い計算の誘導", "なし（DOP は FLIP・重力・海底・境界の帯だけ、壁 wall_on=0）", "なし、または上限の中で双子と並べる",
                                   "合格", "video/record_ja.md §9、runs.jsonl"),
            "G_P2g_guided_twin": m("上限の中の誘導（P2g G1）の大きさ",
                                   {"max_accel_g": 0.100, "work_share_of_wave_energy": 0.025, "off_before_tstar_s": 1.375},
                                   {"max_accel_g": 0.1, "work_share": 0.05, "off_before_tstar_s": "1.0〜1.5"}, "合格（上限の中）",
                                   "P2g/record_ja.md §1"),
            "G_P2g_effect_iou": m("誘導の得（原画カメラの IoU、G0 → G1）", [0.549, 0.553], "—",
                                  "記録のみ（ほとんど変わらず、採らなかった）", "P2g/record_ja.md §1"),
            "S_section_score_z0": m("z=0 の断面の点数（唇の届き・落ち・かぶり、前の面の弦、空洞の幅/高さ、小さいほど近い）", 0.127,
                                    "—", "記録のみ", "P3/record_ja.md §4.3"),
            "S_lip_reach_Hc": m("唇の届き / Hc", 0.50, 0.42, "記録のみ", "P3/record_ja.md §4.3"),
            "S_lip_drop_Hc": m("唇の落ち / Hc", 0.37, 0.33, "記録のみ", "P3/record_ja.md §4.3"),
            "S_lip_cover_Hc": m("唇のかぶり / Hc", 0.34, 0.39, "記録のみ", "P3/record_ja.md §4.3"),
            "S_cavity_w_over_h": m("空洞の幅 / 高さ", 0.79, 0.83, "記録のみ", "P3/record_ja.md §4.3"),
            "S_front_chord_deg": m("前の面の弦", 39, 59, "不合格（記録）", "P3/record_ja.md §4.3"),
            "S_back_len_Hc": m("背：頂 → 0.75 Hc の横 / Hc", 1.20, 0.49, "不合格（記録）", "P3/record_ja.md §4.3"),
            "S_crest_height_m": m("頂の高さ（倍率なし）", 20.4, 20, "記録のみ", "P3/record_ja.md §4.3"),
            "S_ridge_length_m": m("峰に沿って頂の高さがほぼ同じ長さ", "約 100 m（波長 270 m の波は 70 m より短く変われない）",
                                  "原画の読みでは頂の左 20〜30 m で半分の高さ", "不合格（記録）", "P2/record_ja.md §6、video/record_ja.md §9"),
            "S_claw_structures_S11": m("爪の三つの構造（S11）", "なし", "三つ", "不合格（記録）", "video/record_ja.md §9"),
            "P_painting_cam_iou": m("原画カメラ（PaintingCam v1）のシルエット IoU（t*）", 0.562,
                                    "窓の全部が水で 0.503", "記録のみ（形の似方をほとんど表さない）", "video/record_ja.md §4"),
            "P_painting_cam_outline_mean_px": m("原画カメラの輪郭の平均距離（1920 表示）", 145, "原画視点の輪郭 ≤4 px は記録だけ（Q37）",
                                                "記録のみ", "video/record_ja.md §4"),
            "P_best_iou_over_time": m("動きの中で最も高い IoU", {"t_s": 8.25, "iou": 0.596}, "—", "記録のみ", "video/record_ja.md §3"),
            "P_camsweep_low_horizon_best": m("カメラを変えた比べ：水平線が原画と同じ（目の高さ 3 m）で最良",
                                             {"D_m": 500, "h_m": 3, "delta_deg": -25, "vfov_deg": 3.5, "iou": 0.630, "outline_px": 98},
                                             "—", "記録のみ（VR では使えない）", "video/record_ja.md §5"),
            "P_camsweep_overall_best": m("カメラを変えた比べ：全体の最良",
                                         {"D_m": 500, "h_m": 15, "delta_deg": -37, "iou": 0.658, "outline_px": 80, "horizon_y_px": 360},
                                         "—", "記録のみ", "video/record_ja.md §5"),
            "C_P3_wall_total_h": m("P3 本番の計算の壁時計（12 の区切り）", 3.57, "—", "記録のみ", "runs.jsonl"),
            "C_P3_max_launch_s": m("1 回の起動の最長", 1480.4, "≤ 1800 s（30 分）", "合格", "runs.jsonl"),
            "C_P3_rss_peak_gb": m("メモリーの山", 21.91, "64 GB の機械", "記録のみ", "runs.jsonl"),
            "C_P3_particles": m("粒子の数", [34575173, 35483761], "—", "記録のみ", "runs.jsonl"),
            "C_P3_sec_per_frame": m("1 コマ（計算／粒子の読み出し／網目、中央値）", {"sim": "43〜48", "io": "12〜20", "mesh": "11〜14"},
                                    "P0 の見積もり 20〜38 s/コマ", "記録のみ（見積もりは外れた）", "P3/record_ja.md §3・§4.1"),
            "C_P3_ckpt_gb": m("P3 の途中保存", 41.5, "—", "記録のみ（git の外、消してよい）", "runs.jsonl"),
            "C_one_heavy_at_a_time": m("重い計算は一度に 1 つ", "P3 の T0・T0b を C18_export と同時に走らせた（10/6 22:57〜23:24）。P2 の R10・R12 の 2 本同時は Q38 の決まりの中",
                                       "一度に 1 つ（P2 の探索だけ 2 本まで）", "不合格（記録）", "P3/record_ja.md §0"),
            "C_same_problem_fixes": m("同じ問題の直しは 2 回まで",
                                      {"P0 圧力が解けず水が自由落下": "2 回直して条件により再発 → 3 回目はせず、解けると確かめた並びだけを使った",
                                       "P3 箱が R18 を再現しない": "2 回目で合格"},
                                      "≤ 2", "合格（決まりを守った）", "P0/record_ja.md §1、P3/record_ja.md §2"),
            "C_C_drive_writes": m("C: への書き込み", "なし（HOUDINI_TEMP_DIR・キャッシュ・描画はすべて G:）", "なし", "合格", "各段の記録"),
            "C_per_stage": m("段ごとの計算（起動の数・壁時計の合計・最長・メモリーの山・粒子の最大）",
                             {k: {kk: v[kk] for kk in ("sim_launches", "wall_sum_h", "max_launch_s", "rss_peak_gb", "particles_max")}
                              for k, v in ps.items() if v["sim_launches"]},
                             "1 回 ≤ 1800 s", "記録のみ", "runs_table.json"),
            "V_videos_le_30MB": m("動画の大きさ", "3.2・1.8・2.2・3.0・1.7 MB", "≤ 30 MB", "合格", "copies.json"),
        },
        "stages": {
            "P0": "水槽の確かめ。Q36 の静かな水の粒子の減り（55.2 万 → 32.8 万）は水が自由落下して失われていたため。直し 2 回で止まったが条件で再発し、P0 は合格にしなかった（解ける並びだけを使って先へ）",
            "P1": "断面の探索 16 組（周期 12〜16 s、足元の波 16〜27 m、斜面 1:3〜1:6、岩棚 22〜30 m）。全部巻いた。いちばん良い B025H32（0.25 m）：頂 20.3 m、前の面の弦 58°、背 1.19 Hc",
            "P2": "粗い 3D（粒子 1 m・格子 2 m、806 × 240 m）10 本。R18 で峰に沿う一つの山（頂 20.6 m、半分の高さの幅 108 m）が中ほどで巻いた。原画カメラ IoU 0.54〜0.59",
            "P2g": "R18 に上限の中の誘導（G1）と双子（G0）。形の得はほとんどなく、採らなかった",
            "P3": "主役の範囲を粒子 0.25 m で計算。7 つの断面すべてで管が閉じた。t* 8.54 s",
            "Video": "確かめの動画 3 本・静止画・カメラを変えた比べ（新しい計算なし）",
        },
        "per_stage_wall_h": {k: v["wall_sum_h"] for k, v in ps.items()},
        "all_stages_wall_h": rt["all_stages_wall_sum_h"],
    }
    json.dump(met, open(EVID + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("metrics ok", p3)


def do_run():
    t0 = datetime.datetime.now()
    tools = {}
    for d in TOOLS_DIRS:
        for r in walk(REPO + "/" + d):
            tools[d + "/" + r] = sha(REPO + "/" + d + "/" + r)
    proto = {}
    for r in walk(REPO + "/Unity/Assets/GreatWave/FLIP37Proto"):
        proto["Unity/Assets/GreatWave/FLIP37Proto/" + r] = sha(REPO + "/Unity/Assets/GreatWave/FLIP37Proto/" + r)
    scenes = {s: {"sha256": sha(REPO + "/" + s), "bytes": os.path.getsize(REPO + "/" + s)} for s in SCENES}
    caches = {}
    for d in CACHE_DIRS:
        caches["Unity/Build/FLIP37/" + d] = manifest(B + "/" + d)
        print("cache", d, caches["Unity/Build/FLIP37/" + d]["bytes"])
    for f in CACHE_FILES:
        caches["Unity/Build/FLIP37/" + f] = {"sha256": sha(B + "/" + f), "bytes": os.path.getsize(B + "/" + f)}
    ckpt = {}
    for d in CKPT_DIRS:
        n, s = dirsize(B + "/" + d)
        ckpt["Unity/Build/FLIP37/" + d] = {"files": n, "gb": round(s / 1e9, 2), "hashed": False}
    renders = {}
    for d in RENDER_DIRS:
        if os.path.isdir(B + "/" + d):
            renders["Unity/Build/FLIP37/" + d] = manifest(B + "/" + d)
    for name, src, _ in COPIES:
        if src.endswith((".mp4", ".png")):
            renders["Unity/Build/FLIP37/" + src] = sha(B + "/" + src)
    records = {"Unity/Build/FLIP37/" + r: sha(B + "/" + r) for r in RECORDS}
    evid = {}
    for fn in sorted(os.listdir(EVID)):
        if fn == "run.json":
            continue
        evid["Docs/Evidence/FLIPPrototype/" + fn] = sha(EVID + "/" + fn)
    run = {
        "schema": "GreatWave.FLIPProto.deliver_run/1",
        "date": t0.strftime("%Y-%m-%d %H:%M"),
        "note_ja": "Docs/Evidence/FLIPPrototype を作った記録。新しい計算・描画はしていない（Git 対象外の Unity/Build/FLIP37 から写した）。ckpt（途中保存）は大きいので SHA-256 を取らず、数と大きさだけ。git の add・commit・push はしていない",
        "commands": ["py -3.10 -B Tools/GWWaveGen/flip37/fp_deliver.py all"],
        "versions": {
            "python": platform.python_version(),
            "houdini": "Houdini Indie 22.0.459 hython（G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe、画面なし）",
            "blender": "5.2.2（粘土の描画、画面なし）",
            "ffmpeg": "2024-12-19 git-494c961379 full_build",
            "unity": "6000.4.3f1（組み込みの準備の独立した試作の場面だけ。作品の場面は開いていない）",
        },
        "upstream_commands_ja": {
            "P0〜P3": "各段の run_pN.py / p3_chain.py（引数と結果は runs.jsonl の各行）",
            "Video": "py -3.10 Tools/GWWaveGen/flip37/video_make.py all Unity/Build/FLIP37/video_tools/configs/video_P3_curl.json、py -3.10 Tools/GWWaveGen/flip37/video_camsweep.py 同じ設定",
        },
        "inputs": {
            "Docs/References/Met_JP1847_DP130155.jpg": sha(REPO + "/Docs/References/Met_JP1847_DP130155.jpg"),
        },
        "tools": tools,
        "unity_prototype": proto,
        "scenes": scenes,
        "caches": caches,
        "checkpoints_not_hashed": ckpt,
        "renders": renders,
        "records": records,
        "evidence": evid,
        "hash_wall_s": None,
    }
    run["hash_wall_s"] = round((datetime.datetime.now() - t0).total_seconds(), 1)
    json.dump(run, open(EVID + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("run ok", run["hash_wall_s"])


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("copy", "all"):
        do_copy()
    if what in ("tables", "all"):
        do_tables()
    if what in ("metrics", "all"):
        do_metrics()
    if what in ("run", "all"):
        do_run()
