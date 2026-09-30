# -*- coding: utf-8 -*-
"""設計39 第「紙」部：実行の記録（ds39_run.json：命令・道具の版・入出力の SHA-256）と、最小の受入の表（ds39_acceptance.json）を書く。
値は ds39_paper_metrics.json（ds39_eval.py）と Unity の報告（ds39_render_report.json・ds39_build_report.json）から読む（ここで測り直さない）。
使い方（リポジトリの根で）： py -3.10 -B Tools/GWWaveGen/ds39/ds39_run_record.py
"""
import glob
import hashlib
import json
import os
import platform
import subprocess

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/39/paper"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def main():
    m = json.load(open(OUT + "/ds39_paper_metrics.json", encoding="utf-8"))
    rr = json.load(open(OUT + "/unity/ds39_render_report.json", encoding="utf-8-sig"))
    br = json.load(open(OUT + "/ds39_build_report.json", encoding="utf-8-sig")) if os.path.exists(OUT + "/ds39_build_report.json") else {}
    reg = OUT + "/unity/ds30_tstar_regress.json"
    code = sorted(glob.glob(REPO + "/Tools/GWWaveGen/ds39/*.py") + glob.glob(REPO + "/Tools/GWWaveGen/ds39/*.ps1")
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Design39/**/*.cs", recursive=True)
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Design39/**/*.shader", recursive=True)
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Design39/**/*.cginc", recursive=True)
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Design39/**/*.mat", recursive=True)
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Design39/**/*.unity", recursive=True))
    outs = sorted(glob.glob(OUT + "/unity/video/*.mp4") + glob.glob(OUT + "/fig/*.png") + glob.glob(OUT + "/spray/*.json") + glob.glob(OUT + "/spray/*.bin")
                  + glob.glob(OUT + "/unity/onoff/*.png") + glob.glob(OUT + "/perf/*/*.json"))
    run = dict(
        schema="GreatWave.DS39.run/1", number="設計39", part="紙（紙の地・摺りのむら・小飛沫）",
        commands=[
            "py -3.10 -B Tools/GWWaveGen/ds39/ds39_spray_dense.py（小飛沫の子。約 33 s）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds39/run_ds39_unity.ps1 -Method GreatWave.Design39.EditorTools.DS39Render.Render -Log render（場面・t28・入切・揺れ・動画。約 40 s）",
            "同 -Log swim15 -Extra \"-ds39Skip scene,t28,onoff,video\"（揺れの検査を利得 15 で描き直し）",
            "同 -Method GreatWave.Design39.EditorTools.DS39Render.BuildPerf -Log build（Release プレイヤー。約 15 s）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds39/run_ds39_player.ps1 -Tag run1 -Measure 8、同 -Tag run2 -Measure 8",
            "py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/39/paper/unity --sets t28_claws,t28_white（評価器。全部切の組）",
            "py -3.10 -B Tools/GWWaveGen/ds39/ds39_eval.py --perf run1,run2",
            "py -3.10 -B Tools/GWWaveGen/ds39/ds39_run_record.py"],
        tools=dict(python=platform.python_version(), unity=rr.get("unity"), device=rr.get("device"), graphicsApi=rr.get("graphicsApi"), colorSpace=rr.get("colorSpace"),
                   ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"),
        code_sha256={rel(p): sha(p) for p in code},
        outputs_sha256={rel(p): sha(p) for p in outs},
        inputs_sha256={rel(p): sha(p) for p in [REPO + "/Unity/Build/Design/31/spray/ds31_spray_table.json", REPO + "/Unity/Build/Design/31/spray/ds31_spray_frames.bin",
                                                   REPO + "/Unity/Assets/GreatWave/Design38/Scenes/DS38_Outlines.unity"]},
        unity_protected_unchanged=rr.get("protectedUnchanged"), unity_protected_files=rr.get("protectedFiles"),
        build=dict(result=br.get("buildResult"), seconds=br.get("buildSeconds"), frameTimingStatsRestored=br.get("frameTimingStatsRestored"),
                   protectedUnchanged=br.get("protectedUnchanged")),
        not_used_ja="参照モデル・爪形分析のフォルダー・利用者の解算・写真のフォルダー・禁止の場所・Blender・Houdini は使っていない。git は使っていない。")
    json.dump(run, open(OUT + "/ds39_run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ---- 回帰：評価器の出力の数値の葉を設計38 と比べる（パスの文字列は除く）
    def leaves(o, pre=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from leaves(v, pre + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from leaves(v, pre + "/" + str(i))
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            yield pre, float(o)
        elif isinstance(o, bool):
            yield pre, float(o)
    r38 = REPO + "/Unity/Build/Design/38/outlines/unity/ds30_tstar_regress.json"
    regress = dict(done=os.path.exists(reg), note_ja="values_* は sets の数値の葉。ファイル全体（112 個の値）は SHA-256 で比べた（file_same）")
    if os.path.exists(reg):
        a = dict(leaves(json.load(open(reg, encoding="utf-8"))["sets"])); b = dict(leaves(json.load(open(r38, encoding="utf-8"))["sets"]))
        common = sorted(set(a) & set(b))
        diff = [k for k in common if abs(a[k] - b[k]) > 1e-12]
        regress.update(values_compared=len(common), values_different=len(diff), only_ds39=len(set(a) - set(b)), only_ds38=len(set(b) - set(a)),
                       different_keys=diff[:20], ds39=rel(reg), ds38=rel(r38), file_sha256_ds39=sha(reg), file_sha256_ds38=sha(r38),
                       file_same=sha(reg) == sha(r38),
                       key_values={k: a[k] for k in common if any(t in k for t in ("132_sigma12_max", "72_sigma24_p95", "silhouette_diff_vs_29r01_px"))})
    sw = m["swim"]; idn = m["identity_off_vs_ds38"]
    pd = m.get("perf_delta_vs_base", {})
    acc = dict(
        schema="GreatWave.DS39.acceptance/1", number="設計39", part="紙",
        plan="計画 §2.3 の設計39：最小の受入＝評価と原画比較は全部切で行う（ΔE00 の測定を乱さない）、入れても頭の移動で質感が泳がない。成果物＝各オン/オフの画像と追加 GPU 時間",
        acceptance=[
            dict(item="評価と原画比較は全部切（ΔE00 を乱さない）",
                 value=dict(t28_images_same_pixels_as_ds38=idn["all_same_pixels"], images_compared=sum(len(idn[k]) for k in ("t28_white", "t28_claws")),
                            evaluator_values_compared=regress.get("values_compared"), evaluator_values_different=regress.get("values_different"), default_state="全部切"),
                 verdict="合格" if idn["all_same_pixels"] and regress.get("values_different") == 0 else "不合格または未了"),
            dict(item="入れても頭の移動で質感が泳がない（±0.1 m の揺れ）",
                 value=dict(worst=sw["worst"], all_pass=sw["all_pass"], threshold=sw["S_N_max_def"], bins_per_cell=sw.get("Q_bins_per_cell"),
                            videos=[rel(p) for p in sorted(glob.glob(OUT + "/unity/video/ds39_sway_*.mp4"))]),
                 verdict="合格（PC 描画の揺れ。② は検査で見分けられない限界を記録）" if sw["all_pass"] else "不合格"),
            dict(item="各オン/オフの画像と追加 GPU 時間（成果物）",
                 value=dict(images=len(glob.glob(OUT + "/unity/onoff/*.png")), gpu_delta_median_ms={k: {c: {t: x["d_median_ms"] for t, x in cv.items()} for c, cv in v.items()} for k, v in pd.items()}),
                 verdict="作った（記録）")],
        regression=regress,
        hmd="PS VR2 は保留（Q24。利用者の手が要る）。Mock の両眼は使っていない（この番号の受入は頭の揺れと GPU 時間）",
        fix_rounds_used=0)
    json.dump(acc, open(OUT + "/ds39_acceptance.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps([dict(item=x["item"], verdict=x["verdict"]) for x in acc["acceptance"]], ensure_ascii=False), regress.get("values_compared"), regress.get("values_different"))
    print("wrote ds39_run.json", len(code), len(outs))


if __name__ == "__main__":
    main()
