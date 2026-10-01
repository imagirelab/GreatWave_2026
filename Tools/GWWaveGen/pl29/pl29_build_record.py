# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の作る部（BUILD）の証拠をまとめる：前後の図・動画を Docs/Evidence/Polish/29 へ写し、metrics_build.json と run_build.json を書く。
数は pl29_after_measure.py（metrics_build.json の元）・pl29_code_check.py・pl28_f71_count.py の出力から読むだけで、ここでは測り直さない。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl29/pl29_build_record.py --start 2026-10-01T12:33 --end <時刻>
"""
import argparse
import hashlib
import json
import os
import shutil

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Polish", "29")
AFTER = os.path.join(B, "after", "p29d")
EV = os.path.join(REPO, "Docs", "Evidence", "Polish", "29")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def f71(p, n_key="all"):
    d = load(p)
    a = d["all"]
    n = a["frames"][1] - a["frames"][0] + 1
    m = a["M1b_fill_flicker"]
    out = {"file": rel(p), "frames": n, "M1b_sum_px": m["sum_px"], "M1b_per_frame_px": round(m["sum_px"] / n, 1), "M1b_max_px": m["max_px"],
           "M1b_blobs_ge20": m["big_blobs_ge20"], "M1b_max_blob_px": m["max_big_blob_px_in_frame"], "M2_line_off": a["M2_line_blink"]["off_clusters"]}
    w = d.get("windows_video_frames", {}).get("270_345")
    if w:
        out["window_270_345"] = {"M1b_sum_px": w["M1b_sum_px"], "M1b_max_px": w["M1b_max_px"]}
    return out


BY_EYE = {
    "painting": "t*：白い頂と背（背の白に細い淡い水色の流れの線）、中ほどに胴の藍の窓（藍中の溝が流れに沿って走り、紙の白い点）。窓の上の縁は爪の形の白い舌。"
                "右の巻きは白と淡い水色に藍の切れ込み、左（b区域の側）は白と淡い水色の帯の下に溝の入った藍の胴。原画の配置（白い頂・藍の胴・流れの縞）には似るが、"
                "原画の爪と泡の細かい模様（前は投影で写していた）はなく、立体の爪（設計33・34）は小さくまばら。t 6 s は溝の入った藍のふくらみ、t 9〜10.5 s は頂から白が広がる。"
                "引き伸ばし・継ぎ目・左端の横縞・足の縦の筋は見えない。",
    "seat": "t 10.5・12 s：内側の面いっぱいに流れに沿う溝と白い点、頂の縁に爪の形の白い舌が垂れ、立体の波として読める。前の、ぎざぎざの梯子・引き伸ばし・平らな藍の壁は消えた。"
            "t 6・9 s は大波がまだ画面の下の端だけ。",
    "seat_toward_wave": "t 10.5・12 s：内側の面は溝と白い点で埋まり、平らな藍の壁も外挿の縦の帯もない。足の側では溝が太い帯になってやや賑やか。右の高い波（周りの海のシート）は"
                        "平らな淡い水色・藍中の面のまま（海の 4 段、仕上げ30）。設計38 の外殻線が主役波の足と海の境に残る（前は同じ色の上を横切って見えた線。今は溝のある足の縁に重なる）。",
    "side_left": "白い殻（淡い水色の流れの線と陰の段）と、下の溝の入った藍の胴。前の外挿の縞（行・列の色を写した帯）は消えた。t 6 s は溝の入った藍のふくらみで、海と同じ藍濃の地なので輪郭は溝と線で読む。",
    "side_right": "同じく白い殻と溝の藍。巻きの下面は淡い水色。引き伸ばし・帯はない。",
    "back65": "背の白い殻に淡い水色の流れの線と陰の段、下の藍の胴に溝。前の外挿の縦の帯と平らな藍は消えた。形の問題（中ほどのドーム、仕上げ28 の限界 1）は形なので残る。",
    "top": "白い頂と淡い水色の陰、唇の窓の藍に溝。前の外挿の帯・継ぎ目は消えた。",
    "turntable": "12 方位どれでも、白い殻（流れの線と陰）と溝の藍の胴の同じ材質。継ぎ目・引き伸ばし・外挿の帯はない。後ろ側（180〜270°）は白の殻が大きく、溝は根元だけ。",
}

ITEMS = [
    {"item": "［利用者の言葉］Q28 原画カメラからの投影の焼き込みを、視点によらない立体の材質に置き換える",
     "after": "主役波の色・溝・白・境の線を面の座標（流れの座標 F・行の c・弧長 s・t* の相対の高さ）・t* の法線・T_white だけで決める PL29 Ukiyoe Keypose に替えた。"
              "コードの点検（code_check_build.json）で、主役波と周りの海の材質の道に原画カメラの投影が残らないことを確かめた。Polish29 の場面 2 つと Play モードで確かめた。",
     "judgementJa": "作る部としては満たす（7 視点＋回り台を目で見て、投影の破れの種類（引き伸ばし・継ぎ目・外挿の帯・平らな藍の壁）は見えない）。閉じる判定は進行役の自己評審。"},
    {"item": "F7-1 の描画の側（t 9〜11.5 s の 1 コマの跳び）",
     "after": "30 fps の数え（段階7確認と同じ）では、前 52,813／後 57,567（窓 270〜345：前 52,069／後 55,492、1 コマの最大 1,643 → 1,289）で減らない。"
              "同じ窓を 90 Hz で撮ると前 5.3／後 24.2 px／コマ（最大 25／61）で、前も後もほぼ消える。数えの多くは、t 9〜11.5 s に約 10 px／コマ（30 fps）で動く細い縞の"
              "1 コマの通り過ぎで、模様の座標の跳びではない。溝・白い点を切ると 30 fps でも 3,213（−94%）。",
     "judgementJa": "焼き込みの模様の座標（F7-1 の描画の側の原因）はなくなった。30 fps の数えは細い縞の動きで残る（限界として記録。PS VR2 の 90／120 Hz では小さい）。"},
    {"item": "色の焼き込みの傷：唇の端の梯子・モアレ、縦の継ぎ目、前面の足の縦の筋、原画視点の左端の横縞",
     "after": "どれも投影と外挿の帯から来ていたので、置き換えで消えた（前後の図と切り抜き fig_pl29b_ba_crops.png）。溝は周期が 3〜6 px より細かくなる所で薄めて消す（モアレよけ）。",
     "judgementJa": "消えた（目で見て）"},
    {"item": "座席から波の方向のコマ 330〜420 で継ぎ目に沿う線が暗い海を横切る",
     "after": "線は設計38 の外殻線で、材質の置き換えでは消えない。主役波の足に溝が入ったので、線は溝のある足の縁に重なり、暗い海を横切る線には見えにくくなった（t 12 s で目で見た）。",
     "judgementJa": "一部（線そのものは仕上げ38）"},
    {"item": "座席の見えない内壁の平らな藍濃と、左の横の外挿の帯",
     "after": "内壁は溝と白い点の入った藍になり、外挿の帯はなくなった。平らな面（芯 > 48 px、≥ 2,000 px）は原画視点の外で 134 → 41 個、主役波の画素の 20.2% → 2.2%。残る 41 個の多くは白の殻・淡い水色の大きな塊。",
     "judgementJa": "消えた（藍の平らな壁）。白の殻の大きな塊は流れの線で和らげた"},
    {"item": "溶けた爪",
     "after": "爪の色を設計36 の投影の表から設計34 の白（上面）・淡い水色（縁の側面と下面）に戻し、主役波の白い頂の下は藍の窓・溝になったので、色区の読みで溶けた爪は 原画視点 128 → 1／174、原画視点の外 180 → 6／509。"
              "ただし爪の数と形（設計33）は段階9 の主役波に合わせたままで、原画視点では小さくまばら。",
     "judgementJa": "色の溶けは減った。爪の造形・配置は仕上げ32・33"},
    {"item": "行 234〜239 の張り直し（HMD で見えた時だけ）", "after": "HMD はまだない。行の法線の折れ・細い面の接触は形の問題で、材質では扱わない。", "judgementJa": "保留（HMD）"},
    {"item": "軽量版を新しい UV3 の表で作り直す", "after": "新しい材質は UV3 の表（投影の座標）を使わないので、UV3 の作り直しは要らない。軽量版（設計29 の間引きの格子）に面の座標を付ける作業はこの部ではしていない。",
     "judgementJa": "未（軽量版の格子に pl29_hero_attr を当てる作業が残る）"},
    {"item": "周りの海のシートを主役波と揃える",
     "after": "near・far は設計36 の t* の高さによる 4 段（投影なし）のまま。調色板は主役波の材質から写す（DS36SeaPalette.SyncFromHero）。右の高い波・手前の小波に溝や白い殻を付けるのは、計画 §5.3 の仕上げ30（右の高い波・手前の小波）の作業なので、順番を守ってこの部ではしていない。",
     "judgementJa": "一部（投影なし・同じ限定色。形と模様は仕上げ30）"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-01T12:33")
    ap.add_argument("--end", required=True)
    a = ap.parse_args()
    os.makedirs(EV, exist_ok=True)
    copied = []
    for f in sorted(os.listdir(os.path.join(B, "after", "sheets"))):
        if f.endswith(".png"):
            shutil.copy2(os.path.join(B, "after", "sheets", f), os.path.join(EV, f)); copied.append(f)
    for f in sorted(os.listdir(os.path.join(B, "after", "videos_ba"))):
        if f.endswith(".mp4"):
            src = os.path.join(B, "after", "videos_ba", f)
            if os.path.getsize(src) > 5 * 1024 * 1024:
                raise SystemExit("5 MB を超える動画: " + f)
            shutil.copy2(src, os.path.join(EV, f)); copied.append(f)
    meas = load(os.path.join(AFTER, "measure", "metrics_build.json"))
    cc = load(os.path.join(B, "after", "codecheck", "code_check.json"))
    shutil.copy2(os.path.join(B, "after", "codecheck", "code_check.json"), os.path.join(EV, "code_check_build.json")); copied.append("code_check_build.json")
    pm = load(os.path.join(B, "after", "sheets", "painting_match.json"))
    params = [l.strip() for l in open(os.path.join(REPO, "Tools", "GWWaveGen", "pl29", "pl29_material_params.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")]
    rep = load(os.path.join(AFTER, "pl29_render_report.json"))
    play = [load(os.path.join(B, "after", d, "pl29_playmode.json")) for d in ("playmode_single", "playmode_release")]
    out = {
        "group": "仕上げ29", "part": "BUILD（視点によらない立体の材質を作る）", "time": {"start": a.start, "end": a.end},
        "noteJa": "Unity 6000.4.3f1 の PC オフスクリーン描画（RTX 3080、Direct3D11）。HMD 実機ではない。前＝前の点検（PL29Audit、投影の焼き込み）、後＝PL29Render（同じ形 K*′ P28R2rec と動き G_p28rec、"
                  "PL29 Ukiyoe Keypose、爪は設計34 の白・淡い水色）。同じ視点・同じ時刻・同じ数え方。",
        "materialParams": params,
        "byEyeJa": BY_EYE,
        "items": ITEMS,
        "gatesPaintingView": meas["gates"],
        "gatesNoteJa": "輪郭の関門は形の値で、材質を替えても仕上げ28 の P28R2rec と小数第 4 位まで同じ（後退なし）。CP1／26修正01 との差は仕上げ28 のまま（130・131 は CP1 より約 1.6 px 悪い）。",
        "colourItemsNewReading": meas["colourItems"],
        "colourItemsNoteJa": "色区の項目 73〜270・265〜267 は、原画の色区の境と描画の色区の境の距離。投影をやめたので値が大きく動き、ほとんど不合格になる（新しい読み）。投影に戻して追わない（Q28）。",
        "evaluator23": {k: {kk: vv for kk, vv in v.items() if kk != "items"} for k, v in meas["eval23"].items()},
        "evaluator23NoteJa": "評価器 23（Tools/PaintingTruth/evaluate.py）の合否の数は前（仕上げ28 rec）と同じ（爪・線のありなし 4 組とも、合否の変わった項目なし）。",
        "paintingMatch": pm,
        "byView": meas["byView"],
        "summaryNonPainting": meas["summaryNonPainting"],
        "f71": {
            "fps30_before": f71(os.path.join(B, "before", "p28_f71", "count_pngseq.json")),
            "fps30_after": f71(os.path.join(AFTER, "f71_count_pngseq.json")),
            "fps30_after_no_grooves_no_dots": f71(os.path.join(B, "after", "xA_nogroove", "f71_count_pngseq.json")),
            "fps30_after_no_shade_no_edgeline_r6params": f71(os.path.join(B, "after", "xB_noshade_noline", "f71_count_pngseq.json")),
            "fps30_after_without_white_lines_r6": f71(os.path.join(B, "after", "r6", "f71_count_pngseq.json")),
            "hz90_before": f71(os.path.join(B, "before", "p28_f71_90", "f71_count_90.json")),
            "hz90_after": f71(os.path.join(B, "after", "f71_90", "f71_count_90.json")),
            "noteJa": "数え方は段階7確認・仕上げ28 と同じ（pl28_f71_count.py --kind pngseq、爪なし・飛沫なし・線あり、無圧縮の PNG）。90 Hz は同じ t 9〜11.5 s を 1/90 s ごとに撮って同じ道具で数えた（コマの番号 810〜1035）。"
                      "xA・xB・r6 は材質の切り分けの試し（採らない）。xB と r6 は白の中の流れの線を足す前の数。",
        },
        "codeCheck": {"allPass": cc["allPass"], "shader": cc["shader"]["pass"], "component": cc["component"]["pass"], "attrGenerator": cc["attrGenerator"]["pass"],
                      "material": cc["material"]["pass"], "scenes": [s["pass"] for s in cc["scenes"]], "sea": cc["sea"]["pass"],
                      "runtimeRender": cc["runtime"]["render"]["pass"], "runtimePlaymode": [p["pass"] for p in cc["runtime"]["playmode"]], "recordOnly": cc["recordOnly"]},
        "playmode": [{k: v for k, v in p.items() if k != "shots"} for p in play],
        "renderReport": {k: rep.get(k) for k in ["unity", "device", "graphicsApi", "colorSpace", "heroPackage", "heroPackageJsonSha256", "heroMeshGwb", "heroMeshSha256", "timewarp",
                                                 "timewarpSha256", "heroShader", "material", "materialSha256", "attr", "attrSha256", "paramFile", "paramFileSha256", "clawPalette",
                                                 "heroSdf", "heroUvWarp", "heroUv3File", "heroUv3Source", "heroGpuBytes", "protectedUnchanged", "secondsTotal"]},
        "evidenceFiles": copied,
    }
    with open(os.path.join(EV, "metrics_build.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    files = {
        "generator_attr": "Tools/GWWaveGen/pl29/pl29_hero_attr.py", "params": "Tools/GWWaveGen/pl29/pl29_material_params.txt",
        "shader": "Unity/Assets/GreatWave/Polish29/Shaders/PL29_Ukiyoe_Hero.shader", "component": "Unity/Assets/GreatWave/Polish29/Scripts/PL29UkiyoeHero.cs",
        "material": "Unity/Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat", "render": "Unity/Assets/GreatWave/Polish29/Editor/PL29Render.cs",
        "setup": "Unity/Assets/GreatWave/Polish29/Editor/PL29Setup.cs", "playmode": "Unity/Assets/GreatWave/Polish29/Editor/PL29PlayModeCheck.cs",
        "audit_edit": "Unity/Assets/GreatWave/Polish29/Editor/PL29Audit.cs",
        "scene_release": "Unity/Assets/GreatWave/Polish29/Scenes/PL29_Release.unity", "scene_single": "Unity/Assets/GreatWave/Polish29/Scenes/PL29_SinglePlayback.unity",
        "measure": "Tools/GWWaveGen/pl29/pl29_after_measure.py", "code_check": "Tools/GWWaveGen/pl29/pl29_code_check.py", "sheets": "Tools/GWWaveGen/pl29/pl29_build_sheets.py",
        "fig_extra": "Tools/GWWaveGen/pl29/pl29_fig_extra.py", "quicksheet": "Tools/GWWaveGen/pl29/pl29_quicksheet.py", "runner": "Tools/GWWaveGen/pl29/run_pl29_unity.ps1",
        "record": "Tools/GWWaveGen/pl29/pl29_build_record.py",
        "attr_out": "Unity/Build/Polish/29/after/attr/pl29_hero_attr_f32.bin（Git 対象外）",
        "kstar_gwb_in": "Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb（Git 対象外）",
        "kstar_meta_in": "Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_meta.json（Git 対象外）",
    }
    shas = {}
    for k, v in files.items():
        p = os.path.join(REPO, v.split("（")[0])
        shas[k] = {"path": v, "sha256": sha(p) if os.path.exists(p) else None}
    run = {
        "group": "仕上げ29", "part": "BUILD", "time": {"start": a.start, "end": a.end},
        "tools": {"unity": "6000.4.3f1（E:/6000.4.3f1/Editor/Unity.exe、batchmode、unity.lock で 1 つずつ）", "python": "py -3.10（numpy・scipy・Pillow・OpenCV）",
                  "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe", "device": rep.get("device")},
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb --meta G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_meta.json --out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/after/attr",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Setup.BuildScenes -Log setup_scenes3 -Extra \"-pl29ParamFile <repo>/Tools/GWWaveGen/pl29/pl29_material_params.txt -pl29Out <repo>/Unity/Build/Polish/29/after/setup\"",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Setup.EnsureMaterial -Log setup_mat2 -Extra \"-pl29ParamFile <repo>/Tools/GWWaveGen/pl29/pl29_material_params.txt\"（材質のファイルからシェーダーにない古い値を 1 つ消した。値は同じ）",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Render.Render -Log after_full_d -Extra \"-pl29Out <repo>/Unity/Build/Polish/29/after/p29d -pl29ParamFile <repo>/Tools/GWWaveGen/pl29/pl29_material_params.txt -pl29F71 264,351\"",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Render.Render -Log f71_90 -Extra \"-pl29Out <repo>/Unity/Build/Polish/29/after/f71_90 -pl29Only f71 -pl29F71 810,1035 -pl29F71Hz 90 -pl29ParamFile <params>\"",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Audit.Render -Log f71_90_before -Extra \"-pl29State p28 -pl29Out <repo>/Unity/Build/Polish/29/before/p28_f71_90 -pl29Skip views,tt,diag -pl29F71 810,1035 -pl29F71Hz 90\"",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish28.EditorTools.PL28Render.Render -Log before_video -Extra \"-pl28State p28 -pl28Out <repo>/Unity/Build/Polish/29/before/p28_video -pl28Skip t28,full,views,tt -pl28VideoViews painting,seat -pl28HeroPkg Build/Polish/28/G_p28rec/art_on -pl28HeroGwb Build/Polish/28/unity/bake_rec/kstar/kstar_a45.gwb -pl28HeroSdf Build/Polish/28/unity/bake_rec/bake/af28r01_uvsdf_a45.bin -pl28HeroUvWarp Build/Polish/28/unity/bake_rec/bake/af28r01_uvwarp_a45.json -pl28Timewarp Build/Polish/28/G_p28rec/timewarp_G_p28rec.json\"",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode_single -Extra \"-pl29Scene Assets/GreatWave/Polish29/Scenes/PL29_SinglePlayback.unity -pl29Out <repo>/Unity/Build/Polish/29/after/playmode_single -pl29Limit 120\"",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode_release -Extra \"-pl29Scene Assets/GreatWave/Polish29/Scenes/PL29_Release.unity -pl29Out <repo>/Unity/Build/Polish/29/after/playmode_release -pl29Limit 400\"",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/29/after/p29d --kstar rec",
            "py -3.10 Tools/PaintingTruth/evaluate.py --render <p29d>/full/painting_t120_off.png --ids <p29d>/full/<ids_noline|ids_noline_noclaws|ids_line|ids_line_noclaws>.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir <p29d>/eval23/p29d_<組> --name p29d_<組>",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind pngseq --src <p29d>/f71 --glob painting_f*.png --first 264 --name p29d_png --win 270,345 --out <p29d>/f71_count_pngseq.json（90 Hz は --first 810、窓なし）",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_after_measure.py --after Unity/Build/Polish/29/after/p29d --audit Docs/Evidence/Polish/29/metrics_audit.json --rec Unity/Build/Polish/28/unity/scene_rec --out Unity/Build/Polish/29/after/p29d/measure",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_build_sheets.py --before Unity/Build/Polish/29/before/p28 --after Unity/Build/Polish/29/after/p29d --out Unity/Build/Polish/29/after/sheets --catalogue Docs/Evidence/Polish/29/catalogue_audit.json",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_fig_extra.py --before Unity/Build/Polish/29/before/p28 --after Unity/Build/Polish/29/after/p29d --playmode Unity/Build/Polish/29/after/playmode_release --out Unity/Build/Polish/29/after/sheets",
            "ffmpeg -i <前の動画 pl28_<v>_30fps.mp4> -i <後の動画 pl29_<v>_30fps.mp4> -filter_complex drawtext…hstack -c:v libx264 -crf 25 → Unity/Build/Polish/29/after/videos_ba/pl29b_ba_<v>_30fps.mp4（v = painting・seat・tt）",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_code_check.py --render Unity/Build/Polish/29/after/p29d --playmode Unity/Build/Polish/29/after/playmode_single Unity/Build/Polish/29/after/playmode_release --out Unity/Build/Polish/29/after/codecheck",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_build_record.py --start 2026-10-01T12:33 --end <時刻>",
        ],
        "noteJa": "p29d の描画は、材質のファイルからシェーダーにない古い値（_FrontWhite、シェーダーは読まない）を消す前のファイル（SHA-256 " + str(rep.get("materialSha256")) +
                  "）に、同じ数値のファイル（-pl29ParamFile）を当てて描いた。今の材質のファイルの値と同じ。",
        "files": shas,
        "renderOutputs": {"p29d_report": rel(os.path.join(AFTER, "pl29_render_report.json")), "p29d_report_sha256": sha(os.path.join(AFTER, "pl29_render_report.json")),
                          "videos": [{"name": v["name"], "sha256": v["sha256"], "frames": v["frames"]} for v in rep.get("videos", [])]},
        "evidence": {f: sha(os.path.join(EV, f)) for f in copied},
    }
    with open(os.path.join(EV, "run_build.json"), "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("copied", len(copied))


if __name__ == "__main__":
    main()
