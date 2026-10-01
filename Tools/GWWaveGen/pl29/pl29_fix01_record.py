# -*- coding: utf-8 -*-
"""仕上げ29（Q28）修正の回（1 回目）の証拠をまとめる：前後の図・動画を Docs/Evidence/Polish/29 へ写し、metrics_fix01.json と run_fix01.json を書く。
数は各道具の出力（pl29_after_measure.py・pl29_claw_sep.py・pl29_lip_dashes.py・pl29_stretch.py・pl29_code_check.py・pl28_f71_count.py・PL29Render の gpu・
PL29ReleaseBuild・run_pl29_player.ps1）から読むだけで、ここでは測り直さない。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl29/pl29_fix01_record.py --start 2026-10-01T14:22 --end <時刻>
"""
import argparse
import hashlib
import json
import os
import shutil

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Polish", "29")
FX = os.path.join(B, "fix01")
G = os.path.join(FX, "p29g")
EV = os.path.join(REPO, "Docs", "Evidence", "Polish", "29")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def f71(p):
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


GPU_BUILD_JUDGE = {
    "noteJa": "作る部の評審（judge_gpu、Unity/Build/Polish/29/judge_nc/gpu）が測った値。方法は修正の回の gpu と同じ（壁時計、RTX 3080、HMD ではない）。",
    "projection_before": {"heroMs_2eyes_2064x2208_msaa4": 0.4906, "sdfTextureBytes": 134218683, "meshVertexBufferBytes": 4608000, "meshVertexStride": 48},
    "build_p29d": {"heroMs_2eyes_2064x2208_msaa4": 0.6430, "sdfTextureBytes": 0, "meshVertexBufferBytes": 9216000, "meshVertexStride": 96},
    "summaryJa": "作る部：主役波の面 +0.15 ms（2 眼 2064×2208・MSAA 4、0.49 → 0.64 ms、壁時計の見当、RTX 3080、HMD ではない）。色区の SDF テクスチャを外した"
                 "（実行時 −134 MB／GPU で約 −64 MiB）。頂点バッファ 4.6 → 9.2 MB（面の座標の UV3〜5）。keypose のバッファ（heroGpuBytes 241,344,004）は変わらない。",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-01T14:22")
    ap.add_argument("--end", required=True)
    a = ap.parse_args()
    os.makedirs(EV, exist_ok=True)
    copied = []
    for f in sorted(os.listdir(os.path.join(FX, "sheets"))):
        if f.startswith("fig_pl29c_") and f.endswith(".png"):
            shutil.copy2(os.path.join(FX, "sheets", f), os.path.join(EV, f)); copied.append(f)
    for f in sorted(os.listdir(os.path.join(FX, "videos_ba"))):
        if f.endswith(".mp4"):
            src = os.path.join(FX, "videos_ba", f)
            if os.path.getsize(src) > 5 * 1024 * 1024:
                raise SystemExit("5 MB を超える動画: " + f)
            shutil.copy2(src, os.path.join(EV, f)); copied.append(f)
    for src, dst in [(os.path.join(FX, "codecheck", "code_check.json"), "code_check_fix01.json"),
                     (os.path.join(FX, "stretch", "pl29_stretch.json"), "stretch_fix01.json"),
                     (os.path.join(FX, "clawsep", "claw_sep_p29g.json"), "claw_sep_fix01.json"),
                     (os.path.join(FX, "clawsep", "claw_sep_p29d.json"), "claw_sep_build.json"),
                     (os.path.join(FX, "lip", "lip_dashes.json"), "lip_dashes_fix01.json"),
                     (os.path.join(G, "gpu", "pl29_gpu.json"), "gpu_fix01.json"),
                     (os.path.join(B, "release", "unity", "pl29_build.json"), "release_build_fix01.json")]:
        shutil.copy2(src, os.path.join(EV, dst)); copied.append(dst)
    meas = load(os.path.join(G, "measure", "metrics_build.json"))
    cc = load(os.path.join(FX, "codecheck", "code_check.json"))
    st = load(os.path.join(FX, "stretch", "pl29_stretch.json"))
    csd = load(os.path.join(FX, "clawsep", "claw_sep_p29d.json"))
    csg = load(os.path.join(FX, "clawsep", "claw_sep_p29g.json"))
    lip = load(os.path.join(FX, "lip", "lip_dashes.json"))
    gpu = load(os.path.join(G, "gpu", "pl29_gpu.json"))
    gpu_runs = []
    for d in ["gpu2", "gpu3", "gpu4"]:
        p = os.path.join(FX, d, "gpu", "pl29_gpu.json")
        if os.path.exists(p):
            gpu_runs.append({"run": d, "timing": {t["cond"]: round(t["heroMs"], 3) for t in load(p)["timing"]}})
    gpu_runs.append({"run": "p29g", "timing": {t["cond"]: round(t["heroMs"], 3) for t in gpu["timing"]}})
    rel_build = load(os.path.join(B, "release", "unity", "pl29_build.json"))
    runs = {}
    for tag, rp in [("main1", "report.json"), ("capture1", "report_capture.json")]:
        d = os.path.join(B, "release", "runs", tag)
        r = load(os.path.join(d, rp))
        runs[tag] = {"dir": rel(d), "launch": load(os.path.join(d, "launch.json")),
                     "report": {k: r.get(k) for k in ["pass", "errors", "exceptions", "warnings", "frames", "realSeconds", "quitCause", "dataRootUsed", "gpu", "capturedFrames",
                                                      "waveStartS", "experienceEndS"]}}
    rep = load(os.path.join(G, "pl29_render_report.json"))
    play = [load(os.path.join(FX, d, "pl29_playmode.json")) for d in ("playmode_single", "playmode_release")]
    fign = load(os.path.join(FX, "sheets", "fix01_fig_numbers.json"))
    params = [l.strip() for l in open(os.path.join(REPO, "Tools", "GWWaveGen", "pl29", "pl29_material_params.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")]
    cparams = [l.strip() for l in open(os.path.join(REPO, "Tools", "GWWaveGen", "pl29", "pl29_claw_params.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")]
    f71s = {
        "fps30_projection": f71(os.path.join(B, "before", "p28_f71", "count_pngseq.json")),
        "fps30_build_p29d": f71(os.path.join(B, "after", "p29d", "f71_count_pngseq.json")),
        "fps30_fix_p29g": f71(os.path.join(G, "f71_count_pngseq.json")),
        "hz90_projection": f71(os.path.join(B, "before", "p28_f71_90", "f71_count_90.json")),
        "hz90_build_p29d": f71(os.path.join(B, "after", "f71_90", "f71_count_90.json")),
        "hz90_fix_p29g": f71(os.path.join(FX, "f71_90", "f71_count_90.json")),
        "fps30_fix_splits": {x: f71(os.path.join(FX, x, "f71_count_pngseq.json")) for x in
                             ["xa_nofringe", "xb_nofoamdots", "xc_nofoamcells", "xd_nolobes", "xe_nogroove", "xf_nogroove_nodots_nolines"]},
        "noteJa": "数え方は段階7確認・仕上げ28・作る部と同じ（pl28_f71_count.py --kind pngseq、爪なし・飛沫なし・線あり、無圧縮の PNG）。x* は修正の回の材質の切り分けの試し（採らない）。",
    }
    out = {
        "group": "仕上げ29", "part": "修正の回 1 回目（Q28 は［利用者の言葉］の項目なので 2 回まで）", "time": {"start": a.start, "end": a.end},
        "noteJa": "Unity 6000.4.3f1 の PC オフスクリーン描画（RTX 3080、Direct3D11）と、Release のプレイヤーを PC で動かした結果。HMD 実機ではない。"
                  "投影＝前の点検（PL29Audit、投影の焼き込み）、作る部＝p29d、修正の回＝p29g（同じ形 K*′ P28R2rec と動き G_p28rec）。同じ視点・同じ時刻・同じ数え方。",
        "materialParams": params, "clawParams": cparams,
        "gatesPaintingView": meas["gates"],
        "gatesNoteJa": "輪郭の関門 78・130・131・132（σ12）・72（σ12）は形の値で、修正の回でも P28R2rec・作る部と小数第 4 位まで同じ（後退なし）。CP1／26修正01 との差は仕上げ28 のまま。",
        "evaluator23": {k: {kk: vv for kk, vv in v.items() if kk != "items"} for k, v in meas["eval23"].items()},
        "colourItemsNewReading": meas["colourItems"],
        "paintingMatch": {"projection": fign["painting"]["projection"], "build_p29d": fign["painting"]["build"], "fix_p29g_claws1": meas["paintingMatch"]["after_claws1"],
                          "fix_p29g_claws0": meas["paintingMatch"]["after_claws0"]},
        "clawSeparation": {"build_p29d": csd["byView"], "fix_p29g": csg["byView"], "thresholds": csg["thresholds"]},
        "clawMeltedIdReading": {"fix_p29g": meas["summaryNonPainting"]["after"], "byView": meas["byView"],
                                "noteJa": "pl29_after_measure.py の「溶けた爪」は線なしの ID の画像で数えるので、縁の線を数えない。修正の回は主役波の前の白の陰の板をやめた（爪の後ろが白）ので、"
                                          "この読みでは溶けた片が 6 → 182 に増えた。作品のままの色の画像（線あり）で数えた clawSeparation を正とする（記録のみ）。"},
        "lipDashes": lip["renders"],
        "stretch": {"before_uv2": st["before_uv2"], "after_arc_ca": st["after_arc"], "after_grooves_octave": st["after_grooves_octave"],
                    "after_grooves_octave_c5_15": st["after_grooves_octave_c5_15"], "area_factor": st["area_factor_p5_p50_p95"], "readingJa": st["readingJa"],
                    "reviewerReadingJa": "作る部の評審の読み：溝の 3 次元の間隔は 0.95 m × 1.21（p50）・× 2.73（p95）、c 5〜15 m の中央値 2.39 倍・2 倍を超える面積 68%、異方性 p95 6.7。"},
        "f71": f71s,
        "gpu": {"fix_p29g": {"timingHeroMs": {t["cond"]: round(t["heroMs"], 3) for t in gpu["timing"]}, "keyposeGpuBytes": gpu["keyposeGpuBytes"],
                             "meshVertexBufferBytes": gpu["meshVertexBufferBytes"], "meshVertexStrides": gpu["meshVertexStrides"], "meshRuntimeBytes": gpu["meshRuntimeBytes"],
                             "sdfTextureBytes": gpu["sdfTextureBytes"]},
                "fix_runs": gpu_runs, "build_and_projection": GPU_BUILD_JUDGE, "methodJa": gpu["methodJa"]},
        "codeCheck": {"allPass": cc["allPass"], "shader": cc["shader"]["pass"], "shaderCameraPosOnlyForLineFade": cc["shader"]["cameraPosOnlyForLineFade"],
                      "component": cc["component"]["pass"], "attrGenerator": cc["attrGenerator"]["pass"], "material": cc["material"]["pass"],
                      "scenes": [{"file": s["file"], "pass": s["pass"], "bakeStringsInScene": s.get("bakeStringsInScene"), "seaFlatUv3Leftovers": s.get("seaFlatUv3Leftovers")} for s in cc["scenes"]],
                      "sea": cc["sea"]["pass"], "claw": cc["claw"]["pass"], "release": cc["release"]["pass"], "runtimeRender": cc["runtime"]["render"]["pass"],
                      "runtimePlaymode": [p["pass"] for p in cc["runtime"]["playmode"]], "recordOnly": cc["recordOnly"]},
        "release": {"build": {k: rel_build.get(k) for k in ["scenesInBuild", "playerPath", "exeSha256", "buildResult", "heroPackageDir", "heroMeshGwb", "heroSdfPath", "heroWarpPath",
                                                          "heroUv3File", "heroShader", "heroAttr", "heroAttrSha256", "timewarp", "clawShadeOnClaws", "mustHavePresent", "mustHaveMissing",
                                                          "bakeFilesAbsent", "bakeFilesFound", "dataFiles", "dataBytes", "dataSources"]},
                    "runs": runs},
        "playmode": [{k: v for k, v in p.items() if k != "shots"} for p in play],
        "renderReport": {k: rep.get(k) for k in ["unity", "device", "graphicsApi", "colorSpace", "heroPackage", "heroPackageJsonSha256", "heroMeshGwb", "heroMeshSha256", "timewarp",
                                                 "timewarpSha256", "heroShader", "material", "materialSha256", "attr", "attrSha256", "paramFile", "paramFileSha256", "clawPalette",
                                                 "clawShade", "clawMaterial", "clawMaterialSha256", "clawSteps", "clawVertexClasses", "clawLinesEverywhere",
                                                 "heroSdf", "heroUvWarp", "heroUv3File", "heroUv3Source", "heroGpuBytes", "protectedUnchanged", "secondsTotal"]},
        "evidenceFiles": copied,
    }
    with open(os.path.join(EV, "metrics_fix01.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    files = {
        "generator_attr": "Tools/GWWaveGen/pl29/pl29_hero_attr.py", "params": "Tools/GWWaveGen/pl29/pl29_material_params.txt",
        "params_build_copy": "Tools/GWWaveGen/pl29/pl29_material_params_p29d.txt", "claw_params": "Tools/GWWaveGen/pl29/pl29_claw_params.txt",
        "shader": "Unity/Assets/GreatWave/Polish29/Shaders/PL29_Ukiyoe_Hero.shader", "claw_shader": "Unity/Assets/GreatWave/Polish29/Shaders/PL29_Claw_Shade.shader",
        "component": "Unity/Assets/GreatWave/Polish29/Scripts/PL29UkiyoeHero.cs", "claw_component": "Unity/Assets/GreatWave/Polish29/Scripts/PL29ClawShade.cs",
        "material": "Unity/Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat", "claw_material": "Unity/Assets/GreatWave/Polish29/Materials/PL29_Claw_Shade.mat",
        "render": "Unity/Assets/GreatWave/Polish29/Editor/PL29Render.cs", "setup": "Unity/Assets/GreatWave/Polish29/Editor/PL29Setup.cs",
        "release_build": "Unity/Assets/GreatWave/Polish29/Editor/PL29ReleaseBuild.cs", "playmode": "Unity/Assets/GreatWave/Polish29/Editor/PL29PlayModeCheck.cs",
        "scene_release": "Unity/Assets/GreatWave/Polish29/Scenes/PL29_Release.unity", "scene_single": "Unity/Assets/GreatWave/Polish29/Scenes/PL29_SinglePlayback.unity",
        "measure": "Tools/GWWaveGen/pl29/pl29_after_measure.py", "code_check": "Tools/GWWaveGen/pl29/pl29_code_check.py", "sheets": "Tools/GWWaveGen/pl29/pl29_build_sheets.py",
        "stretch": "Tools/GWWaveGen/pl29/pl29_stretch.py", "claw_sep": "Tools/GWWaveGen/pl29/pl29_claw_sep.py", "lip_dashes": "Tools/GWWaveGen/pl29/pl29_lip_dashes.py",
        "figs": "Tools/GWWaveGen/pl29/pl29_fix01_figs.py", "record": "Tools/GWWaveGen/pl29/pl29_fix01_record.py",
        "runner": "Tools/GWWaveGen/pl29/run_pl29_unity.ps1", "player_runner": "Tools/GWWaveGen/pl29/run_pl29_player.ps1",
        "attr_out": "Unity/Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin（Git 対象外）",
        "attr_build": "Unity/Build/Polish/29/after/attr/pl29_hero_attr_f32.bin（Git 対象外。作る部。--param uv2 で同じ SHA-256 を作り直せる）",
        "kstar_gwb_in": "Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb（Git 対象外）",
        "kstar_meta_in": "Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_meta.json（Git 対象外）",
        "release_exe": "Unity/Build/Polish/29/release/player/GreatWave50.exe（Git 対象外）",
    }
    shas = {}
    for k, v in files.items():
        p = os.path.join(REPO, v.split("（")[0])
        shas[k] = {"path": v, "sha256": sha(p) if os.path.exists(p) else None}
    R = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29"
    P = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl29"
    run = {
        "group": "仕上げ29", "part": "修正の回 1 回目", "time": {"start": a.start, "end": a.end},
        "tools": {"unity": "6000.4.3f1（E:/6000.4.3f1/Editor/Unity.exe、batchmode、unity.lock で 1 つずつ）", "python": "py -3.10（numpy・scipy・Pillow）",
                  "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe", "device": rep.get("device")},
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb %s/../28/kstar_p28rec/kstarP28R2rec_a45.gwb --meta %s/../28/kstar_p28rec/kstarP28R2rec_a45_meta.json --out %s/fix01/attr（--param arc、既定）" % (R, R, R),
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py …同じ… --out %s/fix01/attr_uv2check --param uv2（作る部の attr と同じ SHA-256 4e2d124b… を作り直せることの確かめ）" % R,
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_stretch.py --gwb <K*′ .gwb> --meta <meta> --before %s/after/attr/pl29_hero_attr_f32.bin --after %s/fix01/attr/pl29_hero_attr_f32.bin --out %s/fix01/stretch/pl29_stretch.json" % (R, R, R),
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Render.Render -Log fix01_w1〜w6 -Extra \"-pl29Out %s/fix01/w<n> -pl29Only views,fields …-pl29ParamFile %s/fix01/params/w<n>.txt\"（数値の合わせの試し。採らない）" % (R, R),
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Setup.BuildScenes -Log fix01_setup_scenes3 -Extra \"-pl29ParamFile %s/pl29_material_params.txt -pl29ClawParamFile %s/pl29_claw_params.txt -pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29Out %s/fix01/setup\"" % (P, P, R),
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Render.Render -Log fix01_full_g -Extra \"-pl29Out %s/fix01/p29g -pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29ClawShade 1 -pl29ParamFile %s/pl29_material_params.txt -pl29ClawParamFile %s/pl29_claw_params.txt -pl29F71 264,351 -pl29Gpu 1\"" % (R, P, P),
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Render.Render -Log fix01_f71_90 -Extra \"-pl29Out %s/fix01/f71_90 -pl29Only f71 -pl29F71 810,1035 -pl29F71Hz 90 …（p29g と同じ値）\"" % R,
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Render.Render -Log fix01_gpu2〜4 -Extra \"-pl29Only gpu,views … -pl29Gpu 1\"（GPU の時間の見当の繰り返し）",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Render.Render -Log fix01_x<a〜f> -Extra \"-pl29Only f71 -pl29F71 264,351 -pl29ParamFile %s/fix01/params/x*.txt\"（F7-1 の切り分け。採らない）" % R,
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log fix01_playmode_single|fix01_playmode_release -Extra \"-pl29Scene <PL29 の場面> -pl29Out %s/fix01/playmode_<single|release> -pl29Limit 120|400\"" % R,
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29ReleaseBuild.BuildAll -Log fix01_release_build3",
            "powershell -File Tools/GWWaveGen/pl29/run_pl29_player.ps1 -Tag main1；… -Tag capture1 -Capture",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/29/fix01/p29g --kstar rec",
            "py -3.10 Tools/PaintingTruth/evaluate.py --render <p29g>/full/painting_t120_off.png --ids <p29g>/full/<ids_noline|ids_noline_noclaws|ids_line|ids_line_noclaws>.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir <p29g>/eval23/p29g_<組> --name p29g_<組>",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind pngseq --src <p29g>/f71 --glob painting_f*.png --first 264 --name p29g_png --win 270,345 --out <p29g>/f71_count_pngseq.json（90 Hz は --first 810、窓なし）",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_after_measure.py --after Unity/Build/Polish/29/fix01/p29g --audit Docs/Evidence/Polish/29/metrics_audit.json --rec Unity/Build/Polish/28/unity/scene_rec --out Unity/Build/Polish/29/fix01/p29g/measure",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_claw_sep.py --render <p29d|p29g> --name <p29d|p29g> --out %s/fix01/clawsep" % R,
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_lip_dashes.py --render p28=<before/p28> p29d=<after/p29d> p29g=<fix01/p29g> --out %s/fix01/lip" % R,
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_build_sheets.py --before Unity/Build/Polish/29/before/p28 --after Unity/Build/Polish/29/fix01/p29g --out Unity/Build/Polish/29/fix01/sheets --prefix fig_pl29c --catalogue Docs/Evidence/Polish/29/catalogue_audit.json --title … --alabel … --note …",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_fix01_figs.py --p28 … --p29d … --p29g … --clawsep … --lip … --stretch … --measure … --build-metrics Docs/Evidence/Polish/29/metrics_build.json --out %s/fix01/sheets" % R,
            "ffmpeg -i pl28_<v>_30fps.mp4 -i pl29_<v>_30fps.mp4（p29d）-i pl29_<v>_30fps.mp4（p29g）-filter_complex scale=640:360,drawtext…,hstack=inputs=3 -c:v libx264 -crf 25 → Unity/Build/Polish/29/fix01/videos_ba/pl29c_ba_<v>_30fps.mp4（v = painting・seat・tt）",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_code_check.py --render %s/fix01/p29g --playmode %s/fix01/playmode_single %s/fix01/playmode_release --release-build %s/release/unity/pl29_build.json --player-run %s/release/runs/main1 --out %s/fix01/codecheck" % (R, R, R, R, R, R),
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_fix01_record.py --start 2026-10-01T14:22 --end <時刻>",
        ],
        "files": shas,
        "renderOutputs": {"p29g_report": rel(os.path.join(G, "pl29_render_report.json")), "p29g_report_sha256": sha(os.path.join(G, "pl29_render_report.json")),
                          "videos": [{"name": v["name"], "sha256": v["sha256"], "frames": v["frames"]} for v in rep.get("videos", [])]},
        "evidence": {f: sha(os.path.join(EV, f)) for f in copied},
    }
    with open(os.path.join(EV, "run_fix01.json"), "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("copied", len(copied))


if __name__ == "__main__":
    main()
