# -*- coding: utf-8 -*-
"""FLIP39 まとめ（10/8）：Docs/Evidence/FLIPTallWave の metrics.json と run.json を書く（ft_deliver.py から呼ぶ。py -3.10）。
大きなキャッシュ（途中保存・網目）は数と大きさだけ。断面の粒子（横の断面の動画に使った分）は名前と SHA-256 をまとめた値。
"""
import os, sys, json, glob, hashlib, datetime

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
B = ROOT + "/Unity/Build/FLIP39/"
EV = ROOT + "/Docs/Evidence/FLIPTallWave/"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def dir_digest(d, pat="*"):
    fs = sorted(f for f in glob.glob(os.path.join(d, pat)) if os.path.isfile(f))
    h = hashlib.sha256()
    tot = 0
    for f in fs:
        h.update(os.path.basename(f).encode()); h.update(sha(f).encode()); tot += os.path.getsize(f)
    return dict(files=len(fs), bytes=tot, sha256_of_names_and_sha256=h.hexdigest())


def dir_size(d):
    n = tot = 0
    for r, _, fs in os.walk(d):
        for f in fs:
            n += 1; tot += os.path.getsize(os.path.join(r, f))
    return dict(files=n, gb=round(tot / 1e9, 2))


def hashes(paths):
    return {rel(p): sha(p) for p in sorted(set(paths)) if os.path.isfile(p)}


def write_meta(S, R):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    runs = [json.loads(l) for l in open(B + "runs.jsonl", encoding="utf8") if l.strip()]
    wl = [float(r.get("wall_launch_s") or 0) for r in runs]
    copies = json.load(open(EV + "copies.json", encoding="utf8"))
    m = {
        "schema": "GreatWave.FLIPTallWave.metrics/1",
        "date": now,
        "note_ja": "指導教員の指摘（Q39）に沿った独立した試作（Houdini FLIP、D1〜R とレビュー）の主な数。result は 合格／不合格／記録のみ／利用者が判定／未確認。"
                   "値は Unity/Build/FLIP39 の各段の記録と JSON から写した（座席の仰角の数だけは rv_angle_timeline.py の式で求め直した）。新しい流体計算はしていない",
        "best_run": {"id": "R H30_E3（E3_dir20_lens の主役の範囲を粒子 0.3 m で）", "seat": "x 530 m・z −80 m（乗る目）",
                     "what_ja": "一方向の分散による集中＋向きの広がり σθ 20°＋波長と同じ程度の海底の盛り上がり、岩棚 1:4。波を起こすのは水槽の端の造波の帯（x 0〜140 m）と海底の形だけ"},
        "seat_measures_ja": {
            "eye": "乗る目：船が上下だけ水面に乗る（目＝船の長さ 11.33 m の下の水面の中央値＋1.83 m）。傾き・押し流し・転覆なし",
            "alpha": "頂の仰角：目から水が最も高く見える点への地平線からの角度。境目 25°（目だけで見上げる上の端の目安）・45°（首を上げる）・55°（PS VR2 の視野の上の端の推定）・60°（人の視野の上の端）",
            "t25_t45": "仰角が 25°・45° 以上の時間（乗る目の終わりまで）",
            "a2": "乗る目の終わりの 2 秒前の仰角",
            "lip_lead": "目の高さの前の面の足から唇の先までの水平の距離。正なら目が水の上にある間に唇が頭上に来る",
            "growth_share": "仰角 10° 以上の間の、仰角の伸びのうち頂が高くなる分の割合。0.5 を越えると「育つ」が主（定義の上の境目）",
            "source": "Unity/Build/FLIP39/D1/record_ja.md §4.2（Git 対象外）。境目は人の視野・PS VR2 の公表値・幾何から出した目安で、HMD で確かめていない",
        },
        "items": {
            "TW1_physics_only": {"item_ja": "計算の中に力・速さ・目標の形を足していない（流速を変えるのは造波の帯と吸う帯だけ）",
                                 "value": "道具を読んで確かめた（e_tanklib.py の relax_zones、e_build_tank.py、r_build_window.py）", "target": "足さない", "result": "合格"},
            "TW2_crossing_in_FLIP37": {"item_ja": "FLIP37 R18 の ±30° の二つの列の集まりの指標（中央 ±30 m の η² の割合、一様なら 0.25）",
                                       "value": {"t0": 0.414, "足元を通る時": 0.350, "砕け始め": 0.330}, "target": "集まるなら増える",
                                       "result": "記録のみ（原因：集まっていなかった）", "source": "Unity/Build/FLIP39/D1/mech.json"},
            "TW3_growth_ratio_m1": {"item_ja": "崩れる時の頂 ÷ 入口の頂（計算の中で育った比）", "value": {r["id"]: r["m1"] for r in R},
                                    "target": "1 より大きい（前の作品の元 R18 は 1.06）", "result": "合格（E・R で 1.24〜2.37）", "source": "E/table.json、R の記録 §1"},
            "TW4_crest_height_m": {"item_ja": "崩れる時の頂（静かな水面から）", "value": {r["id"]: r["crest"] for r in R}, "target": "—",
                                   "result": "記録のみ（どれも P3 の 20.95 m より低い）"},
            "TW5_seat_t45_s": {"item_ja": "座席の乗る目で仰角 45° 以上の時間", "value": {k: v["t45"] for k, v in S.items()},
                               "target": "P3（0.583 s）より長い（物差しは利用者未確認）", "result": "不合格（0〜0.83 s。延びていない）"},
            "TW6_seat_t25_s": {"item_ja": "座席の乗る目で仰角 25° 以上の時間", "value": {k: v["t25"] for k, v in S.items()},
                               "target": "P3（2.25 s）より長い（物差しは利用者未確認）", "result": "不合格（0〜2.00 s）"},
            "TW7_seat_a2_deg": {"item_ja": "乗る目の終わりの 2 秒前の仰角", "value": {k: v["a2"] for k, v in S.items()}, "target": "—",
                                "result": "記録のみ（どれも 30° 未満）"},
            "TW8_growth_share": {"item_ja": "育つ分の割合（仰角 10° 以上）", "value": {k: v.get("growth_share") for k, v in S.items()},
                                 "target": "0.5 以上で「育つ」が主（D1 の定義の上の境目）", "result": "不合格（0.00〜0.12。近づく分が主）"},
            "TW9_lip_overhead_R": {"item_ja": "R で唇が目の乾いている間に頭上に来た座席",
                                   "value": "調べた 36 か所のうち x 530 m・z −80 m の 1 か所（lip lead +7.2 m、±2.5 m で外れる）", "target": "—", "result": "記録のみ（狭い当たり）"},
            "TW10_breaking_type": {"item_ja": "崩れ方", "value": {"E1・E2": "前へ巻く巻き波", "E3": "前へ巻く（空洞が閉じた、設計から 40 m 横）",
                                                               "R z−80": "80.1 s に頂の先から崩れて乱れた頂", "R z−60": "84.92 s に垂直を過ぎ、85.92 s・x 526 m で空洞が閉じた",
                                                               "R 焦点の列": "縦の細い噴き上がり 22.3 m"}, "target": "—", "result": "利用者が判定"},
            "TW11_convergence": {"item_ja": "崩れ方の収束（粒子 1 m と 0.3 m で違う）", "value": "0.2 m は未実行（5 時間前後の見込み）", "target": "—", "result": "未確認"},
            "TW12_run_limits": {"item_ja": "1 回の起動 30 分以内・重い計算は一度に一つ・自由落下の見張り",
                                "value": {"launches": len(runs), "max_launch_s": round(max(wl), 1), "sum_h": round(sum(wl) / 3600, 2), "freefall_guard_stopped": 0},
                                "target": "≤ 1800 s", "result": "合格", "source": "Unity/Build/FLIP39/runs.jsonl"},
            "TW13_videos_le_30MB": {"item_ja": "証拠の動画が 30 MB 以下", "value": {c["name"]: c["bytes"] for c in copies if c["name"].endswith(".mp4")},
                                    "target": "≤ 31,457,280 bytes", "result": "合格" if all(c.get("le_30MB", True) for c in copies) else "不合格"},
        },
        "rows": R,
        "seat_stats": S,
    }
    json.dump(m, open(EV + "metrics.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)

    caches = [B + "runs.jsonl", B + "D1/mech.json", B + "D1/seat_measures.json", B + "D1/seat_measures_raw.json", B + "D1/seat_raw.json",
              B + "E/table.json", B + "E/visual_breaker.json", B + "E/lens_rays.json", B + "E/lin_long_tank.json", B + "FT/ft_numbers.json"]
    caches += glob.glob(B + "E/*/analysis_e*.json") + glob.glob(B + "E/*/seat_e.json") + glob.glob(B + "E/*/run.json")
    caches += glob.glob(B + "R/H30_E3/*.json") + glob.glob(B + "R/V1_val_d10/*.json") + glob.glob(B + "R/*.json")
    renders = glob.glob(B + "R/videos/*.mp4") + glob.glob(B + "R/*.png") + glob.glob(B + "E/*.png") + glob.glob(B + "E/clips/*.mp4") + \
        glob.glob(B + "D1/*.png") + [B + "review_angle_timeline.png", B + "FT/R_side_sections.mp4", B + "FT/ft_2_experiments.png"]
    run = {
        "schema": "GreatWave.FLIPTallWave.deliver_run/1",
        "date": now,
        "note_ja": "Docs/Evidence/FLIPTallWave を作った記録。新しい流体計算はしていない。横の断面の動画と実験の比べの図だけを、すでにある断面の粒子と JSON から描いた。"
                   "途中保存・網目などの大きなキャッシュは数と大きさだけ（横の断面の動画に使った断面の粒子は、名前と SHA-256 をまとめた値）。git の add・commit・push はしていない",
        "commands": ["py -3.10 -B Tools/GWWaveGen/flip39/ft_side_video.py", "py -3.10 -B Tools/GWWaveGen/flip39/ft_deliver.py"],
        "upstream_commands_ja": {
            "D1": "py -3.10 d1_mech.py → d1_mech_figs.py → d1_seat.py → d1_seat_figs.py → d1_summary.py（Unity/Build/FLIP39/D1/record_ja.md §7）",
            "E": "e_build_tank.py で場面、e_launch.sh・e_chain.py・e_queue.sh・e_queue2.sh で計算（引数と結果は runs.jsonl）、e_post.py・e_analyze.py・e_seat.py・e_render.py・e_render_bl.py・e_compare.py（E の記録 §10）",
            "R": "r_export_coarse.py → r_build_window.py → r_chain.py・r_queue.sh（runs.jsonl）→ r_analyze.py・r_seat.py・r_strip.py・r_curves.py・r_render.py・r_render_bl.py・r_before.py・r_sheet.py（R の記録 §10）",
            "review": "py -3.10 rv_angle_timeline.py",
        },
        "versions": {"python": sys.version.split()[0], "houdini": "Houdini Indie 22.0.459 hython（画面なし）", "blender": "5.2.2（粘土の描画、画面なし）",
                     "ffmpeg": "2024-12-19 git-494c961379 full_build", "unity": "使っていない（作品の場面は開いていない）"},
        "inputs": hashes([ROOT + "/Docs/References/Met_JP1847_DP130155.jpg", ROOT + "/Tools/GWContext/seat_v1.json"]),
        "tools": hashes(glob.glob(ROOT + "/Tools/GWWaveGen/flip39/*.py") + glob.glob(ROOT + "/Tools/GWWaveGen/flip39/*.sh")),
        "scenes": {rel(p): dict(sha256=sha(p), bytes=os.path.getsize(p)) for p in sorted(glob.glob(ROOT + "/Houdini/FLIP39/*.hiplc"))},
        "caches": hashes(caches),
        "caches_sections_used_for_side_video": {z: dir_digest(B + "R/H30_E3/sec/" + z, "snap_*.npz") for z in ("z-080", "z-060")},
        "caches_large_not_hashed": {k: dir_size(B + k) for k in ("E", "R/H30_E3/ckpt", "R/H30_E3/mesh", "R/C3_export", "R/V1_val_d10")},
        "renders": hashes(renders),
        "evidence": {c["name"]: c["sha256"] for c in copies},
        "docs": hashes([ROOT + "/Docs/Progress/FLIP_TallWave_ja.md"] + glob.glob(ROOT + "/Docs/Research/*.md")),
    }
    json.dump(run, open(EV + "run.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("meta written:", len(run["tools"]), "tools,", len(run["caches"]), "caches,", len(run["renders"]), "renders")
