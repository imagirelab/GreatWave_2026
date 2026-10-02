# -*- coding: utf-8 -*-
"""仕上げ33 の作る部の記録（metrics_build.json・run_build.json と、数の JSON の写し）を Docs/Evidence/Polish/33 へ書く（Git 対象外の出力から数を読み直すだけ。描画・測りはしない）。
記録の部（2026-10-02）で出力の名前を metrics.json・run.json から metrics_build.json・run_build.json に替えた（群の最終の metrics.json・run.json は pl33r_record.py が書くので、走らせ直しても上書きしない）。
使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33_record.py
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/33"
EV = REPO + "/Docs/Evidence/Polish/33"


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    return json.load(open(p, encoding="utf-8-sig"))


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    os.makedirs(EV, exist_ok=True)
    copies = {B + "/measure/pl33_measure.json": "pl33_measure.json", B + "/measure/pl33_checks.json": "pl33_checks.json",
              B + "/measure/pl33_gates.json": "pl33_gates.json", B + "/measure/pl33_perf.json": "pl33_perf.json",
              B + "/r_after/pl33_bumps.json": "pl33_bumps_after.json", B + "/r_after/pl33_bumps_white.json": "pl33_bumps_after_noclaws.json",
              B + "/tmp/pl33_bumps_before.json": "pl33_bumps_before.json", B + "/relief/pl33_relief_report.json": "pl33_relief_report.json",
              B + "/claws/pl33_crown.json": "pl33_crown.json", B + "/setup/pl33_setup.json": "pl33_setup.json",
              B + "/release/unity/pl33_build.json": "release_build.json", B + "/r_after/pl33_render_report.json": "render_report_after.json",
              B + "/playmode_Release/pl29_playmode.json": "playmode_release.json", B + "/playmode_SinglePlayback/pl29_playmode.json": "playmode_single.json",
              B + "/r_after/pl28u_regress.json": "pl28u_regress_after.json"}
    for s, d in copies.items():
        if os.path.exists(s):
            shutil.copyfile(s, EV + "/" + d)
    g = jl(B + "/measure/pl33_gates.json")
    ch = jl(B + "/measure/pl33_checks.json")
    me = jl(B + "/measure/pl33_measure.json")
    pf = jl(B + "/measure/pl33_perf.json")
    bu = jl(B + "/r_after/pl33_bumps.json")
    lay = jl(B + "/claws/ds33_claw_layout.json")
    rh = me["painting_tstar_rhythm"]
    vs = me["views_summary_before_after"]
    ga, gb = g["after"]["t28_claws"], g["before"]["t28_claws"]
    m = {
        "schema": "GreatWave.Polish33.metrics/1", "number": "仕上げ33（設計33 爪の造形）",
        "before": "仕上げ32（コミット ede11c8。修正の回 1 の状態。描画 Build/Polish/32/fix01/r_fix01）", "after": "仕上げ33（Build/Polish/33/r_after）",
        "evidence_kind_ja": "Unity 6000.4.3f1 の PC オフスクリーン描画・Editor の Play モード・Release のプレイヤー（PC）と numpy・OpenCV の計算。HMD 実機ではない。利用者は見ていない。",
        "gates_painting_view": {
            "78_max_px": [gb["def"]["78"]["max_px"], ga["def"]["78"]["max_px"]], "130_max_px": [gb["def"]["130"]["max_px"], ga["def"]["130"]["max_px"]],
            "131_max_px": [gb["def"]["131"]["max_px"], ga["def"]["131"]["max_px"]], "132_sigma12_max_px": [gb["s12_132"], ga["s12_132"]],
            "72_sigma12_p95_px_claws": [gb["s12_72p95"], ga["s12_72p95"]], "72_sigma12_p95_px_noclaws": [g["before"]["t28_white"]["s12_72p95"], g["after"]["t28_white"]["s12_72p95"]],
            "verdict": "後退なし（前と同じ値。爪の投影は射線の上を動かしただけで、冠の爪は原画視点で見えず、膜は主役波の中に収めた）",
            "cp1": {"78": 2.772, "130": 1.968, "131": 1.814, "132": 1.326, "72": 1.558}, "26r01": {"78": 1.641, "130": 1.953, "131": 1.798, "132": 1.574, "72": 1.723},
            "eval23_before": g["before"]["eval23"], "eval23_after": g["after"]["eval23"]},
        "backlog": {
            "99": {"value": ch["99_C095_side_thickness_over_front_width"], "verdict": "満たす（C095 の側面の厚み／正面の幅 0.20、根元から先まで同じ。座席から立ち上がった帯の側面が見える）"},
            "100": {"value": {"closed_band": True, "outline_132_def_px": ga["def"]["132"]["max_px"], "outline_72_def_p95_px": ga["def"]["72"]["p95_px"]},
                    "verdict": "一部（帯は根元の扇・輪・先端で閉じた筒で、穴・切断面はない。原画構図の輪郭の細部込み ≤4 px は満たさない＝下の 132・72）"},
            "101": {"verdict": "記録（芽の段 s < 0.2 は面に付いた短い帯。冠の爪も芽から伸びる。座席 t 9 s で芽が見える）"},
            "103_104": {"verdict": "満たす（原画の爪の t* の投影は仕上げ32 と同じ：投影の差 最大 %s px。仕上げ32 の 122・127・128 の先端 ≤ 2.10 px のまま）" % ch["C_tstar_projection_shift_px_max"]},
            "105": {"value": {"C_root_identical_to_pl32": ch["C_root_and_circle_identical_to_pl32fix01"], "crown_root_to_sheet_vertex_max_m": ch["crown_root_to_sheet_vertex_max_m"]}, "verdict": "満たす"},
            "129": {"value": {k: v["teleports_gt_0p5m"] for k, v in ch["motion"].items()}, "verdict": "満たす（瞬間移動 0）"},
            "136": {"verdict": "満たす（原画の爪は仕上げ32 の成長のまま。冠の爪は根元の T_white（τ −2.78〜−0.44 s）で伸び始め、t* で終わる）"},
            "137": {"value": ch["crown_root_to_sheet_vertex_max_m"], "verdict": "満たす（冠の爪の根元はシートの頂点そのもの。滑り 8 µm 以下＝float32 の丸め）"},
            "138": {"verdict": "満たす（立ち上がりの向きと冠の爪の向きは根元の座標系で持ち、面が回れば一緒に回る）"},
            "139": {"value": {"claws": len([c for c in lay["claws"] if c["id"].startswith("C")]), "crown": len([c for c in lay["claws"] if c["id"].startswith("K")]),
                              "nan": sum(v["nan"] for v in ch["motion"].values())}, "verdict": "満たす（途中の欠落 0、NaN 0）"},
            "140_141_180_262": {"value": {"seat_t120_claw_px": vs["seat_t120"]["claw_px"], "seat_toward_wave_t120_claw_px": vs["seat_toward_wave_t120"]["claw_px"],
                                          "penetration": ch["penetration_ring_centres"]}, "verdict": "記録（座席から、面から立ち上がった指が手前・奥で重なり、指の間に藍・空が見える。目で見た判定。数の判定はしていない）"},
            "200_207_208": {"verdict": "記録（爪の白は主役波の白と同じ色の値。根元の円は仕上げ32 の決まりで水色の版のまま）"},
            "204": {"value": {"flips": ch["204_ring_up_flips_by_kind"], "ids": ch["204_ring_up_flips_ids"], "width_outside": ch["204_frames_width_outside_first_last_range"]},
                    "verdict": "一部（幅は範囲の内。輪の上面の向きの裏返り 28 コマは C021・C067・C090 で、仕上げ32 の帯のまま＝立ち上げは輪を平行に動かすだけ）"},
            "205_206": {"verdict": "記録（帯は閉じた筒。鉤の内の膜は線のない水色の薄い膜で、座席から爪の下の陰として見える）"},
            "238": {"verdict": "満たす（根元の線は仕上げ32 のとおり開き、膜には線を出さない）"},
        },
        "plan_5_3": {
            "user_words_bregion": {"mizuiro_painting_before_after": [rh["bregion_painting"]["mizuiro"], rh["bregion_before"]["mizuiro"], rh["bregion_after"]["mizuiro"]],
                                   "line_components_painting_before_after": [rh["bregion_painting"]["components"], rh["bregion_before"]["components"], rh["bregion_after"]["components"]],
                                   "verdict": "一部（房の付け根の水色の塊は増えた。藍の窓・3 つの房の形は主役波の形と材質の限界）"},
            "painting_claw_rhythm": {"mizuiro_painting_before_after": [rh["painting"]["mizuiro"], rh["before"]["mizuiro"], rh["after"]["mizuiro"]],
                                     "dark_line_px_painting_before_after": [rh["painting"]["dark_line_px"], rh["before"]["dark_line_px"], rh["after"]["dark_line_px"]],
                                     "verdict": "直した（爪の領域の水色の割合が原画と同じ程度）"},
            "views_claw_px_t120": {k: vs[k] for k in vs if k.endswith("t120")},
            "132_72_detail_bumps": {"after": {k: {"max_px": v["max_px"], "p95_px": v["p95_px"]} for k, v in bu["items"].items()},
                                    "verdict": "満たさない（限界。4 px を超える所は主役波の面の輪郭のこぶ（爪なしでも同じ所）と、爪の先と先の間で包絡に届かないへこみ）"},
        },
        "unity": {"perf": pf, "release_data_bytes": jl(B + "/release/unity/pl33_build.json").get("dataBytes"),
                  "claw_vertices": lay["vertices"], "claw_triangles": lay["triangles"]},
    }
    json.dump(m, open(EV + "/metrics_build.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    code = sorted(glob.glob(REPO + "/Tools/GWWaveGen/pl33/*.py") + glob.glob(REPO + "/Tools/GWWaveGen/pl33/*.ps1") +
                  glob.glob(REPO + "/Unity/Assets/GreatWave/Polish33/*/*.cs") + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish33/*/*.shader") +
                  glob.glob(REPO + "/Unity/Assets/GreatWave/Polish33/Scenes/*.unity"))
    run = {"schema": "GreatWave.Polish33.run/1",
           "commands": [
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_claw_relief.py --h-rel 0.35 --h-max 0.8 --tip-drop 0.4 --out Unity/Build/Polish/33/relief",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_crown.py",
               "bash Unity/Build/Polish/33/run_render.sh r_after views,tt,t28,full,video",
               "bash Unity/Build/Polish/32/run_eval.sh Unity/Build/Polish/33/r_after",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_bumps.py Unity/Build/Polish/33/r_after/t28_claws Unity/Build/Polish/33/r_after/pl33_bumps.json",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_measure.py", "py -3.10 -B Tools/GWWaveGen/pl33/pl33_checks.py",
               "run_pl33_unity.ps1 -Method GreatWave.Polish33.EditorTools.PL33Setup.BuildScenes -Log build_scenes",
               "run_pl33_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode_<Release|SinglePlayback> -Extra \"-pl29Scene Assets/GreatWave/Polish33/Scenes/PL33_<…>.unity …\"",
               "run_pl33_unity.ps1 -Method GreatWave.Polish33.EditorTools.PL33ReleaseBuild.BuildAll -Log release_build",
               "run_pl32_player.ps1 -Tag pl33pair<1|2> ; run_pl33_player.ps1 -Tag pair<1|2>（交互に 2 組）",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_sheets.py --before Unity/Build/Polish/32/fix01/r_fix01 --after Unity/Build/Polish/33/r_after --out Docs/Evidence/Polish/33",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_figs.py", "py -3.10 -B Tools/GWWaveGen/pl33/pl33_record.py"],
           "tools": {"unity": "6000.4.3f1（E:/6000.4.3f1/Editor/Unity.exe）", "python": "py -3.10（numpy・OpenCV・scipy・PIL）", "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"},
           "inputs_sha256": {rel(p): sha(p) for p in [B + "/../32/fix01/claws/ds33_claw_frames_f32.bin", B + "/../32/white/hero_pkg/ds27_keypose.json",
                                                      B + "/../32/white/hero_pkg/ds27_twhite_r32f.bin", B + "/../32/white/pl31_zone_vertex.npy",
                                                      B + "/../28/G_p28rec/timewarp_G_p28rec.json", B + "/../32/fix01/list/ds32_claw_inventory.json"]},
           "outputs_sha256": {rel(p): sha(p) for p in [B + "/claws/ds33_claw_layout.json", B + "/claws/ds33_claw_frames_f32.bin", B + "/claws/ds33_claw_tris_i32.bin",
                                                       B + "/claws/ds33_claw_tri_attr_u16.bin", B + "/claws/pl33_crown.json", B + "/relief/ds33_claw_layout.json",
                                                       B + "/release/player/GreatWave50.exe"]},
           "code_sha256": {rel(p): sha(p) for p in code},
           "reference_photos_read_ja": "利用者の指示 Q16 の例外の写真のフォルダー G:/research/reality scan/北斋参考 の 3 枚（正面图.jpg・左45.jpg・背图.jpg）を画面で見ただけ（頂の指の形の見え方の参考）。"
                                       "画像・寸法・形はリポジトリと成果物に入れていない。Exif は写していない。参照モデルの OBJ は読んでいない。",
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()}
    json.dump(run, open(EV + "/run_build.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33_RECORD_DONE", len(code), "code files")


if __name__ == "__main__":
    main()
