# -*- coding: utf-8 -*-
"""仕上げ28：動きの当て直し（K*′ P28R2 の上の G_final と、修正の回の版）の測定値と実行条件を、証拠の metrics_motion.json・run_motion.json に集める。
測定の出力（Git 対象外の Unity/Build/Polish/28/）だけを読む。値を作り直さない。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_motion_record.py [--fix G_p28a]
"""
import argparse
import glob
import hashlib
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = "Unity/Build/Polish/28"
EV = "Docs/Evidence/Polish/28"


def ab(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def jl(p):
    p = ab(p)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    p = ab(p)
    if not os.path.isfile(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def gate_row(gt, tag, s="default"):
    g = ((gt or {}).get("tags", {}).get(tag) or {}).get("sets", {}).get(s)
    if not g:
        return None
    out = {}
    for k in ["P%d" % i for i in range(1, 20)] + ["Painting"]:
        if k in g:
            out[k] = dict(value=g[k]["value"], pass_=g[k]["pass_"])
    out["P13_items"] = {k.split("）")[0] + "）" if "）" in k else k: dict(value=v["value"], pass_=v["pass_"]) for k, v in g.get("P13_items", {}).items()}
    out["P17_main_row"] = g.get("P17_main_row")
    out["failed"] = (g.get("summary_all") or {}).get("failed")
    return out


def scan_m(tag_dir):
    s = jl(os.path.join(tag_dir, "scan.json"))
    if not s:
        return None
    m1 = s["m1"]
    m2 = s["m2"]
    V = m2["volume"]["V_m3"]
    vv = {k: v for k, v in V.items()}
    vmax_k = max(vv, key=lambda k: vv[k])
    return dict(m1=dict(hz=m1["hz"], frames=m1["frames"], section_selfx_frames=m1["section_selfx_frames"],
                        local_selfx_motion_frames=m1["local_selfx_motion_frames"], verdict_ja=m1["verdict_ja"]),
                tstar_vs_kstar_m=m2["tstar"], V_scan_max=[vmax_k, vv[vmax_k]], V_scan_tstar=vv.get("+0.00"),
                V_scan_loss_frac=round(1 - vv.get("+0.00") / vv[vmax_k], 4))


def fr(tag):
    d = jl("%s/motion/fr/motion_%s.json" % (B, tag))
    if not d:
        return None
    c = d["chord_pre_lip"]
    return dict(V_max=d["V_max"], V_loss_frac_from_max=d["V_loss_frac_from_max"], V_m3=d["V_m3"],
                V_step_last2s_max_before_max_ratio=d["V_step_last2s_max_before_max_ratio"], selfx_frames_60hz=d["selfx_frames"],
                chord_rows_le110_ge0p5s=c["rows_le110_ge0p5s"], chord_rows_le125_ge0p5s=c["rows_le125_ge0p5s"], chord_min_deg=c["min_deg"],
                chord_argmin_row=c["argmin_row"], chord_main_peak_min=c["main_peak_min"], chord_worst_rows=c["worst_rows"][:6])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", default="", help="修正の回の版（, 区切り）")
    ap.add_argument("--adopt", default="")
    a = ap.parse_args()
    fixes = [x for x in a.fix.split(",") if x]
    tags = ["F_final", "G_final"] + fixes
    gt = jl("%s/motion/gates_table.json" % B)
    rv = {t: (jl("%s/review/review_%s.json" % (B, t)) or {}).get(t) for t in tags if t != "F_final"}
    rv["F_final"] = (jl("Unity/Build/Design/28R01F/review/review_F_final.json") or {}).get("F_final")
    loaf = jl("%s/motion/loaf_E_F_G.json" % B)
    loaf_fix = dict(G_p28a=jl("%s/motion/loaf_fix.json" % B), G_p28b=jl("%s/motion/loaf_fix2.json" % B))
    m = dict(schema="GreatWave.Polish28.metrics_motion/1", made_local=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
             note_ja="仕上げ28 の動きの当て直し（計画 §5.3 仕上げ28 の Q10 の行と動きの項目）。numpy の生成器と検査器・Blender の粘土・Unity の PC オフスクリーン描画。HMD 実機ではない。関門 P1〜P20 は計画のとおり測って記録し、合否は閉じる目安に入れない",
             kstar_freeze=jl("%s/kstar_p28/_frozen_from.json" % B))
    m["adopted"] = a.adopt
    m["gates_default_16bit"] = {t: gate_row(gt, t) for t in (["F_final", "F_p27", "G_final"] + fixes)}
    m["gates_other_sets_failed"] = {t: {s: (((gt or {}).get("tags", {}).get(t) or {}).get("sets", {}).get(s) or {}).get("summary_all")
                                        for s in ("default_fine", "default_fine_stop13", "alt", "default_q13")} for t in tags}
    m["scan_60hz"] = {"F_final": scan_m(ab("Unity/Build/Design/28R01F/F_final")), "G_final": scan_m(ab("%s/G_final" % B))}
    for fx in fixes:
        m["scan_60hz"][fx] = scan_m(ab("%s/%s" % (B, fx)))
    m["final_review_motion_definitions"] = {t: fr(t) for t in tags}
    m["p13_2_map"] = {t: jl("%s/motion/acc30_%s.json" % (B, t)) for t in tags if jl("%s/motion/acc30_%s.json" % (B, t))}
    for t, d in m["p13_2_map"].items():
        d.pop("top_tau", None)
    m["loaf_M10"] = dict(E_F_G=loaf, fix=loaf_fix)
    keep = ("pace", "front_crest", "curl", "no_rebound_before_stop")
    m["review_q13_q15_q17"] = {t: ({k: (v or {}).get(k) for k in keep} if v else None) for t, v in rv.items()}
    f71 = "%s/motion/f71" % B
    m["F7_1"] = dict(
        video_ds29r01=jl("%s/count_ds29r01_painting.json" % f71) and {k: jl("%s/count_ds29r01_painting.json" % f71)[k] for k in ("windows_video_frames",)},
        lossless=jl("%s/count_F_final_pngseq.json" % f71) and jl("%s/count_F_final_pngseq.json" % f71)["windows_video_frames"],
        reencoded=jl("%s/count_F_final_reenc.json" % f71) and jl("%s/count_F_final_reenc.json" % f71)["windows_video_frames"],
        tracked_vs_fixed=(jl("%s/track_F_final.json" % f71) or {}).get("windows"),
        geometry={t: (jl("%s/geom_%s.json" % (f71, t)) or {}).get("windows") for t in ("F_final", "G_final", "G_p28b")},
        tau_rate_max_step={t: (jl("%s/geom_%s.json" % (f71, t)) or {}).get("tau_rate", {}).get("max_step") for t in ("F_final", "G_final", "G_p28b")},
        verdict_ja="原因は動き（精度の層・τ(t)・行き戻り）でも焼き込みの模様の座標でもない。無圧縮でも跳びの約 6 割が残り（残りは x264 の圧縮が足した分）、面に付いて動く点の内側では跳び 0。細かい斑が 1 コマに約 5.8 px 動くことの 30 fps の標本化（描画の側）。仕上げ29（描画・焼き込み）と仕上げ37（1 コマの組の測り方）へ")
    probes = {os.path.basename(p): jl(p) for p in sorted(glob.glob(ab("%s/motion/probe/probe_p_*.json" % B)))}
    m["probes_ds28p"] = {k: {vk: dict(p20_max_m=vv.get("p20_max_m"), back_reversal_cols_gt_0p1m=vv.get("back_reversal_cols_gt_0p1m"),
                                      back_reversal_worst_m=vv.get("back_reversal_worst_m"),
                                      loaf_index={t: x["loaf_index"] for t, x in vv.get("loaf", {}).items()},
                                      chord_rows_le110={t: x["rows_le110"] for t, x in vv.get("chord", {}).items()})
                             for vk, vv in (d or {}).get("variants", {}).items()} for k, d in probes.items()}
    m["timing"] = {t: jl("%s/%s/pipeline_timing.json" % (B, t)) for t in tags if t != "F_final"}
    m["p13_2_attribution"] = {os.path.basename(p): jl(p) for p in sorted(glob.glob(ab("%s/motion/probe/probe_acc30_*.json" % B)))}
    m["ds28p_logs"] = {t: jl("%s/%s/art_on/ds28p_generate_log.json" % (B, t)) for t in fixes}
    m["determinism"] = {t: jl("%s/motion/determinism_%s.json" % (B, t)) for t in fixes}
    os.makedirs(ab(EV), exist_ok=True)
    with open(ab("%s/metrics_motion.json" % EV), "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    # run_motion.json：コマンドと SHA-256
    code = sorted(glob.glob(ab("Tools/GWWaveGen/pl28/*.py")) + glob.glob(ab("Tools/GWWaveGen/pl28/*.sh")) + glob.glob(ab("Tools/GWWaveGen/pl28/*.ps1"))
                  + glob.glob(ab("Tools/GWWaveGen/ds28p/*.py")) + glob.glob(ab("Tools/GWWaveGen/ds28p/*.json")))
    inputs = ["%s/kstar_p28/kstarP28R2_a45.gwb" % B, "%s/kstar_p28/kstarP28R2_a45_rows.npz" % B, "%s/kstar_p28/kstarP28R2_a45_meta.json" % B,
              "Unity/Build/Design/28R01F/F_final/art_on/ds27_pos_rgba16.bin", "Unity/Build/Design/28R01F/F_final/timewarp_F_final.json",
              "Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json",
              "Unity/Build/Design/29R01/unity/f_final_kp/video/ds29_painting_30fps.mp4", "Unity/Build/Design/40/stage7_review/s7_video.py",
              "Unity/Build/Design/28R01F/_scratch/final_review/fr_motion.py", "Unity/Build/Design/28R01F/_scratch/final_review/fr_pkg.py"]
    outputs = []
    for t in tags[1:]:
        outputs += ["%s/%s/art_on/ds27_pos_rgba16.bin" % (B, t), "%s/%s/art_on/ds27_pos_lo_rgba8.bin" % (B, t), "%s/%s/art_on/ds27_keypose.json" % (B, t),
                    "%s/%s/art_on/ds27_twhite_r32f.bin" % (B, t), "%s/%s/timewarp_%s.json" % (B, t, t)]
    ev = sorted(glob.glob(ab("%s/*" % EV)))
    run = dict(schema="GreatWave.Polish28.run_motion/1", made_local=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               tools=dict(python="3.10 (numpy 2.2.6, Pillow, OpenCV 4.12)", blender="Steam Blender 5.2.2（Workbench、ヘッドレス）",
                          unity="6000.4.3f1 Editor batchmode（PC オフスクリーン、RTX 3080、Direct3D11）", ffmpeg="2024-12-19 full_build"),
               commands=[
                   "（凍結）Unity/Build/Polish/28/r2/cand の gwb・rows・meta を Unity/Build/Polish/28/kstar_p28/ へ写し、_frozen_from.json に SHA-256（読み取り専用の属性）",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_pipeline_limited.py --max-jobs 2 -- --kstar Unity/Build/Polish/28/kstar_p28 --tag G_final --root Unity/Build/Polish/28 --workers 5 --check-workers 4",
                   "py -3.10 -B Tools/GWWaveGen/ds28p/ds28p_generate.py --kstar Unity/Build/Polish/28/kstar_p28 --name <tag>/art_on --out Unity/Build/Polish/28 --workers 5",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_pipeline_limited.py --max-jobs 3 -- --kstar Unity/Build/Polish/28/kstar_p28 --tag <tag> --root Unity/Build/Polish/28 --skip-generate --check-workers 4",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_gate_table.py --tag F_final=Unity/Build/Design/28R01F/F_final --tag F_p27=Unity/Build/Polish/27/F_p27 --tag G_final=Unity/Build/Polish/28/G_final [--tag <tag>=…] --out Unity/Build/Polish/28/motion/gates_table.json",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_fr_motion.py <tag> <包み> <時間曲線> 60 <出力> <K*′ の meta>",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_acc30_map.py --package <包み> --out Unity/Build/Polish/28/motion/acc30_<tag>.json --rows 48,198",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_loaf.py --tag E=… --tag F_final=… --tag G_final=… --kstar-meta Unity/Build/Polish/28/kstar_p28/kstarP28R2_a45_meta.json --out Unity/Build/Polish/28/motion/loaf_E_F_G.json",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_probe_p.py --package Unity/Build/Polish/28/G_final/art_on --variants … --out Unity/Build/Polish/28/motion/probe/probe_p_*.json",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_geom.py --package <包み> --warp <時間曲線> --out Unity/Build/Polish/28/motion/f71/geom_<tag>.json",
                   "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl28/run_pl28_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log f71_F_final -Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Polish/28/motion/f71/unity_F_final -Stills <f0264〜f0351 の τ（stills_F_final_f264_351.txt）> -Skip t28,capture,video,timing -Extra \"-ds29Name f71_F_final -ds29MeshFromPackage 0 -ds29StillViews painting -ds29KStarGwb Build/Design/28R01F/kstar_final/kstarR4_a45.gwb -ds29Sdf Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin -ds29Warp Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json\"",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind video|pngseq|reenc …（段階7確認の s7_video.py と同じ数え方）",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_track.py --stills Unity/Build/Polish/28/motion/f71/unity_F_final/stills --first 264 --package Unity/Build/Design/28R01F/F_final/art_on --warp Unity/Build/Design/28R01F/F_final/timewarp_F_final.json --out Unity/Build/Polish/28/motion/f71/track_F_final.json",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_fig.py …（fig_pl28_f71_cause.png）",
                   "sh Tools/GWWaveGen/pl28/run_pl28_clay.sh <tag> <包み> <時間曲線> <K*′>（Blender の粘土のこま）",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_clay_compose.py video|sheet …",
                   "py -3.10 -B Tools/GWWaveGen/pl28/pl28_motion_record.py --fix <tag>"],
               code_sha256={os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in code},
               inputs_sha256={p: sha(p) for p in inputs},
               outputs_sha256={p: sha(p) for p in outputs},
               evidence_sha256={os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in ev if os.path.isfile(p)})
    with open(ab("%s/run_motion.json" % EV), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("written", EV)


if __name__ == "__main__":
    main()
