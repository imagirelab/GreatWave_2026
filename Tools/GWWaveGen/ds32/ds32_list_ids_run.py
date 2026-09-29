# -*- coding: utf-8 -*-
"""設計32 の「一覧と ID」の部を順に回し、run.json（コマンド・道具の版・入出力の SHA-256・時間）と metrics.json（項目 → 値 → 判定）を書く。
  py -3.10 Tools/GWWaveGen/ds32/ds32_list_ids_run.py [--skip-register] [--determinism]
--determinism：一覧と ID を別の場所（Git 対象外の作業フォルダー）へもう一度作り、JSON（経過時間の欄を除く）と bin の SHA-256 を比べる。
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = REPO + "/Tools/GWWaveGen/ds32"
OUT = REPO + "/Unity/Build/Design/32/list+ids"
PY = sys.executable
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def run(args):
    t0 = time.time()
    r = subprocess.run([PY, "-X", "utf8"] + args, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("失敗：" + " ".join(args))
    return round(time.time() - t0, 1), r.stdout[-600:]


def canon(p):
    """JSON の経過時間の欄を除いた正準形の SHA-256。"""
    o = json.load(open(p, encoding="utf-8"))

    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in ("elapsed_s",) and not (k == "path" and isinstance(v, str) and "_det" in v)}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    o = strip(o)
    # 出力先の違い（--out）で変わる欄は除く
    if isinstance(o, dict):
        o.pop("inputs", None) if "claw_hist" in o else None
    return hashlib.sha256(json.dumps(o, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-register", action="store_true")
    ap.add_argument("--determinism", action="store_true")
    a = ap.parse_args()
    steps = []
    if not a.skip_register:
        steps.append(["Tools/GWWaveGen/ds32/ds32_user100_register.py"])
    steps += [["Tools/GWWaveGen/ds32/ds32_claw_list.py"], ["Tools/GWWaveGen/ds32/ds32_claw_figs.py"], ["Tools/GWWaveGen/ds32/ds32_fix01_figs.py"],
              ["Tools/GWWaveGen/ds32/ds32_ids.py"],
              ["Tools/GWWaveGen/ds32/ds32_ids_figs.py"], ["Tools/GWWaveGen/ds32/ds32_ids_indep_check.py"]]
    timings = []
    for s in steps:
        el, tail = run(s)
        timings.append({"command": "py -3.10 -X utf8 " + " ".join(s), "elapsed_s": el})
        print(s[0], el, "s", flush=True)
    if a.skip_register:
        timings.insert(0, {"command": "py -3.10 -X utf8 Tools/GWWaveGen/ds32/ds32_user100_register.py", "elapsed_s": None,
                           "note_ja": "この実行では回さず、前の出力（SHA-256 は outputs の ds32_user100_registration.json）を使った。単独で約 103 s、同じ結果を再現する"})
    det = None
    if a.determinism:
        # 2 回目の出力の置き場（Git 対象外）。記録の時に、会話の作業フォルダーからここへ移した（処理は同じ）
        d2 = REPO + "/Unity/Build/Design/32/_det"
        os.makedirs(d2, exist_ok=True)
        run(["Tools/GWWaveGen/ds32/ds32_claw_list.py", "--out", d2])
        run(["Tools/GWWaveGen/ds32/ds32_ids.py", "--out", d2])
        det = {}
        for fn in ("ds32_claw_inventory.json", "ds32_user100_correspondence.json", "ds32_claw_list_checks.json", "ds32_id_checks.json",
                   "ds32_claw_hist_f32.bin", "ds32_group_hist_f32.bin", "ds32_band_members_i32.bin"):
            p1, p2 = OUT + "/" + fn, d2 + "/" + fn
            h1 = canon(p1) if fn.endswith(".json") else sha(p1)
            h2 = canon(p2) if fn.endswith(".json") else sha(p2)
            det[fn] = {"same": h1 == h2, "sha256_first": h1}
        det["all_same"] = all(v["same"] for k, v in det.items() if isinstance(v, dict))
        det["note_ja"] = "JSON は経過時間の欄を除いた正準形で比べた。bin はそのまま"
        print("determinism", det["all_same"], flush=True)

    # ---- run.json
    import numpy as np
    import cv2
    ff = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    ids = json.load(open(OUT + "/ds32_ids.json", encoding="utf-8"))
    reg = json.load(open(OUT + "/ds32_user100_registration.json", encoding="utf-8"))
    inputs = {
        "Docs/References/Met_JP1847_DP130155.jpg": sha(REPO + "/Docs/References/Met_JP1847_DP130155.jpg"),
        "Tools/PaintingTruth/claws29/claw_inventory.json": sha(REPO + "/Tools/PaintingTruth/claws29/claw_inventory.json"),
        "Tools/PaintingTruth/painting_truth.json": sha(REPO + "/Tools/PaintingTruth/painting_truth.json"),
        "Tools/PaintingTruth/manual_annotations.json": sha(REPO + "/Tools/PaintingTruth/manual_annotations.json"),
        "Tools/PaintingTruth/targets/palette.json": sha(REPO + "/Tools/PaintingTruth/targets/palette.json"),
        "Tools/PaintingTruth/targets/main_wave_outline_envelope.json": sha(REPO + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json"),
        "Tools/GWWaveGen/kstar3/candA4_band_targets.json": sha(REPO + "/Tools/GWWaveGen/kstar3/candA4_band_targets.json"),
        "Unity/Build/Design/31/white/hero_pkg/ds27_keypose.json": sha(REPO + "/Unity/Build/Design/31/white/hero_pkg/ds27_keypose.json"),
        "Unity/Build/Design/31/white/hero_pkg/ds27_pos_rgba16.bin": ids["sheet"]["pos_sha256"] + "（keypose.json の値）",
        "Unity/Build/Design/31/white/hero_pkg/ds27_pos_lo_rgba8.bin": ids["sheet"]["pos_lo_sha256"] + "（keypose.json の値）",
        "Unity/Build/Design/31/white/hero_pkg/ds31_twhite_r32f.bin": ids["sheet"]["twhite_sha256"],
        "Unity/Build/Design/28R01F/F_final/timewarp_F_final.json": ids["clock"]["timewarp_sha256"],
        "Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json": ids["inputs"]["colour_uvwarp"]["sha256"],
        "Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin": sha(REPO + "/Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin"),
        "Unity/Build/Design/31/spray/ds31_spray_table.json": ids["inputs"]["spray_table"]["sha256"],
        "Unity/Build/Design/31/spray/ds31_spray_frames.bin": ids["inputs"]["spray_frames"]["sha256"],
        "Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json": sha(REPO + "/Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json"),
    }
    user_inputs = {"read_only_ja": "G:/research/爪形分析（Q8・D14/D23 の読み取りの例外）。画像とマスクは複製していない。SHA-256 は ds32_user100_registration.json の sources と user_files_sha256",
                   "points_csv": reg["sources"]["points_csv"], "index_csv": reg["sources"]["index_csv"],
                   "files": len(reg["user_files_sha256"])}
    code = {fn: sha(HERE + "/" + fn) for fn in sorted(os.listdir(HERE)) if fn.endswith(".py")}
    outs = {}
    for root, _, fns in os.walk(OUT):
        for fn in sorted(fns):
            if fn.startswith("_") or fn in ("run.json", "metrics.json"):
                continue
            p = os.path.join(root, fn).replace("\\", "/")
            outs[p.replace(OUT + "/", "")] = {"bytes": os.path.getsize(p), "sha256": sha(p)}
    runj = {
        "schema": "GreatWave.DS32.run/1", "number": "設計32", "part": "list+ids",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "commands": timings, "determinism": det,
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "ffmpeg": ff, "os": platform.platform()},
        "inputs_sha256": inputs, "user_read_only_inputs": user_inputs, "code_sha256": code, "outputs": outs,
        "not_used_ja": "Unity・Blender・Houdini は使っていない（numpy/OpenCV と ffmpeg だけ）。参照モデル（Q5）は読んでいない（D20：爪に参照モデルを使わない）。"
                       "禁止の場所（旧試作、G:/Unity/Ukeyoe_Claw の README 以外、G:/research の許可の外）には触れていない。README の 1 ファイルは読んだ（Q8 の例外）。git の操作はしていない",
    }
    with open(OUT + "/run.json", "w", encoding="utf-8") as f:
        json.dump(runj, f, ensure_ascii=False, indent=1)

    # ---- metrics.json
    lc = json.load(open(OUT + "/ds32_claw_list_checks.json", encoding="utf-8"))
    inv = json.load(open(OUT + "/ds32_claw_inventory.json", encoding="utf-8"))
    corr = json.load(open(OUT + "/ds32_user100_correspondence.json", encoding="utf-8"))
    ic = json.load(open(OUT + "/ds32_id_checks.json", encoding="utf-8"))
    ind = json.load(open(OUT + "/ds32_ids_indep_check.json", encoding="utf-8"))
    named = {c["id"]: c for c in inv["claws"] if c["id"] in inv["named_by_user"]}
    fx = lc["fix01"]
    items = [
        {"item": "第6節 受入1：名指しの所（83・84・85 の影、109・中5・110 の起点、127 の下）の前後図",
         "value": {"figure": "fig/fig_ds32_named_before_after.png",
                   "shadow_included": {k: (v.get("shadow") or {}).get("included_new") for k, v in named.items()},
                   "shadow_included_af29": {k: (v.get("shadow") or {}).get("included_af29") for k, v in named.items()},
                   "root_moved_px": {k: v.get("root_move_px") for k, v in named.items()},
                   "added_below_127": [c["id"] for c in inv["claws"] if c.get("seed") == "127の下"]},
         "judgement": "図で確かめた（進行役の目視、利用者未確認）"},
        {"item": "第6節 受入2：利用者の100本のうち一覧と対応した本数と、対応しない爪の一覧（理由つき）",
         "value": corr["summary"], "judgement": "出した（対応の表は ds32_user100_correspondence.json）"},
        {"item": "第6節 受入3：囲まれた影を外した爪 0（藍の輪郭線の内側の非白画素の割合で自動検査）",
         "value": {"tested": lc["shadow_tested"], "excluded_ds32": len(lc["shadow_excluded_new"]), "excluded_af29": len(lc["shadow_excluded_af29"]),
                   "counts_by_threshold": lc["shadow_counts_by_threshold"], "threshold_choice_ja": lc["shadow_threshold_choice_ja"]},
         "judgement": "合格" if lc["shadow_pass"] else "不合格"},
        {"item": "第6節 受入4：列ごとの重ね図（上側・途中・船側）、右側は低優先・未修正",
         "value": ["fig/fig_ds32_rows_upper.png", "fig/fig_ds32_rows_middle.png", "fig/fig_ds32_rows_boat.png", "fig/fig_ds32_rows_bregion.png",
                   "fig/fig_ds32_rows_right_untouched.png"], "judgement": "出した"},
        {"item": "第6節 受入5：IoU（仮の定義を分母・分子の両方に使った値と、美術優先29 の分母A・B の値）",
         "value": {k: lc["iou"][k] for k in ("ds32_regions_vs_A_prime", "ds32_regions_vs_B_prime", "af29_polygons_vs_A_prime", "af29_polygons_vs_B_prime", "af29_recorded")},
         "judgement": "記録のみ"},
        {"item": "設計32：爪の根元を K*′ のシートの (u, v) に結び付け、全コマの ID ごとの根元・先端の履歴",
         "value": {"bound": ic["bound"], "unbound_right_side": len(ic["unbound"]), "frames": ic["frames"], "reprojection_tstar_display_px": ic["reprojection_tstar_display_px"]},
         "judgement": "出した（右側の 25 本は主役波のシートの外で結び付けない）"},
        {"item": "設計書 §11 白波の連続性：同じ群の瞬間移動 0",
         "value": {"teleport_count": ic["teleport_count"], "max_moves_m": ic["max_moves_m"], "indep_pass": ind["pass"],
                   "weighted_centroid_record_only": ic["weighted_centroid_record_only"]},
         "judgement": "合格（numpy の履歴。Unity の描画ではない）" if ic["pass_teleport_0"] and ind["pass"] else "不合格"},
        {"item": "設計書 §11 白波の連続性：意図しない点滅 0",
         "value": {"flicker_count": ic["flicker_count"], "growth_decreasing_samples": ic["growth_decreasing_samples"]},
         "judgement": "合格（numpy）" if ic["pass_flicker_0"] else "不合格"},
        {"item": "backlog 129：群の瞬間的な置き換え 0",
         "value": {"group_member_lost_count": ic["group_member_lost_count"]},
         "judgement": "合格（numpy。使える水準。精度は仕上げ33）" if ic["pass_129_replace_0"] else "不合格"},
        {"item": "backlog 95〜98・122〜128・136〜139（前提）", "value": "一覧の修正版と ID を設計33 へ渡す", "judgement": "記録のみ"},
        {"item": "修正01 指摘1：名指しの所 110 で C105 が C110 の指と C107 を呑み込む",
         "value": {"C105": {k: fx["named_12_and_others"]["C105"].get(k) for k in ("status", "root_ref", "length_af29", "length_new")},
                   "C107": fx["named_12_and_others"]["C107"], "C110": {k: fx["named_12_and_others"]["C110"].get(k) for k in ("status", "root_ref", "length_new")},
                   "containment_named_C105_C107_C110": fx["containment_named_C105_C107_C110"],
                   "containment_pairs_ge_0_5_all": fx["containment_pairs_ge_0_5"],
                   "figures": ["fig/fig_ds32_fix01_c105_c110.png", "fig/fig_ds32_named_before_after.png"]},
         "judgement": "直した（C105 は房の左の口を根元にし、C107 は C105 に統合。他の爪の中心線の半分以上を含む領域の組 %d）" % len(fx["containment_pairs_ge_0_5"])},
        {"item": "修正01 指摘2：口の規則が先端の鉤のすぐ上や曲がり目を口と読んで爪を短く切る",
         "value": {"named_12": {k: {kk: v.get(kk) for kk in ("status", "length_af29", "length_new", "removed", "into_or_dup_of")}
                                for k, v in fx["named_12_and_others"].items() if k in ("C074", "C075", "C078", "C080", "C081", "C082", "C087", "C092", "C093", "C098", "C106", "C107")},
                   "guard_status_counts": {s_: sum(1 for c in inv["claws"] if c["status"] == s_) for s_ in ("root_kept_guard", "mouth_exit", "mouth_guard_reverted")},
                   "short_below_0_5_of_af29_remaining": fx["short_below_0_5_of_af29"],
                   "figures": ["fig/fig_ds32_fix01_truncated.png", "fig/fig_ds32_rows_middle.png", "fig/fig_ds32_rows_boat.png"]},
         "judgement": "直した（元の長さの 0.5 倍未満に縮む口は、両側の線が終わる所だけを口と認め、なければ美術優先29 の根元。残る 0.5 倍未満は %s で、"
                      "根元を戻すと C057 の指を呑み込むので最初の候補のまま＝記録した限界、仕上げ32）" % [x["id"] for x in fx["short_below_0_5_of_af29"]]},
        {"item": "修正01 指摘3：加えた爪 C169 は C163 と同じ指で根元と先端が逆",
         "value": {"removed": fx["removed"], "C163": {k: fx["named_12_and_others"]["C163"].get(k) for k in ("status", "root_ref", "length_new")},
                   "added_after_fix01": inv["counts"]["added"], "figure": "fig/fig_ds32_fix01_c163_c169.png"},
         "judgement": "直した（C169 を重複として消し、ID は欠番、対応表に理由。重複の検査を加えた爪どうしと一覧の爪に回した）"},
        {"item": "修正01 の検査（記録のみ）：根元の先で指が続く疑い",
         "value": {"list": fx["continues_past_root_ge_0.6"], "figure": "fig/fig_ds32_fix01_flags.png"},
         "judgement": "記録のみ（目視では多くが体の中の線に当たるだけの誤検出。仕上げ32 で確かめる）"},
        {"item": "修正01 の後に残る限界（Q26：修正は 1 回だけ。仕上げの番号へ送る）",
         "value": [
             {"limit_ja": "C066 は元の長さの 0.49 倍（最初の口の候補のまま）。美術優先29 の根元まで戻すと領域が C057 の指を呑み込む", "to": "仕上げ32"},
             {"limit_ja": "元の長さの 0.5〜0.6 倍の爪 C112（17.9→9.3 px）・C113。C109（中5）は名指しの起点の直しで短くなった", "to": "仕上げ32"},
             {"limit_ja": "根元の先で指が続く疑い %s（目視では多くが体の中の線に当たるだけの誤検出）" % [x["id"] for x in fx["continues_past_root_ge_0.6"]], "to": "仕上げ32"},
             {"limit_ja": "領域の重なり %d 組（小さい方の 20%% を超えるもの %d 組）と縁のとげ（C007・C082・C093 など）。他の爪の領域の中にある根元 %d（%s。上側は美術優先29 の根元のまま、途中・船側の多くは修正01 で戻した美術優先29 の根元どうしの重なり）"
                          % (fx["region_overlap_pairs"], len(fx["region_overlap_pairs_gt_0_2"]), len(fx["roots_inside_other_region"]),
                             "・".join("%s %d" % (k_, sum(1 for x in fx["roots_inside_other_region"] if x["row"] == k_)) for k_ in ("上側", "途中", "船側", "b区域")
                                      if any(x["row"] == k_ for x in fx["roots_inside_other_region"]))), "to": "仕上げ32"},
             {"limit_ja": "影の検査の定義（二つの爪の凹みの側の共有の水色をどちらへ入れるか）。独立の検査の別の定義では 0.5 未満が 33/149", "to": "仕上げ32（D25 の定義し直し）"},
             {"limit_ja": "利用者の 100 本の位置合わせの不確かさ（C060 に 3 本、先端の距離 62〜68 px の対応 4 本、山の差 < 0.02 の 6 本、同じ画像の claw069・claw076）", "to": "仕上げ32"},
             {"limit_ja": "C174 は C002 の先の続きかもしれない（possible_continuation_of）", "to": "仕上げ32"},
             {"limit_ja": "先端 22 本は根元のカメラの深さの面の上にあり、シートから浮くことがある", "to": "設計33（仕上げ33）"},
             {"limit_ja": "瞬間移動のしきい値 (a) は全体の値（約 1.26 m／コマ）。爪ごとの局所の検査も 0 だった", "to": "設計34"},
             {"limit_ja": "Unity の再生・Mock の両眼の確認はまだ（numpy だけ）。HMD の実機は保留（PS VR2 の導入待ち）", "to": "設計34・保留"}],
         "judgement": "記録した限界"},
        {"item": "回帰（計画 §2.0）：原画視点の描画", "value": "この部は原画視点の描画を変えていない（シート・色面・場面に触れず、爪は描かない）",
         "judgement": "評価器を回す対象ではない（記録）"},
    ]
    m = {"schema": "GreatWave.DS32.metrics/1", "number": "設計32", "part": "list+ids",
         "evidence_kind_ja": "高解像度原画の numpy/OpenCV の計算と重ね図、主役波のパッケージの numpy の評価（Hermite）と点の描画。Unity の描画ではない。HMD 実機ではない",
         "items": items}
    with open(OUT + "/metrics.json", "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    print("run.json / metrics.json written")


if __name__ == "__main__":
    main()
