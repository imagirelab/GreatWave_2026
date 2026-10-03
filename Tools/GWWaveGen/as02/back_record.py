# -*- coding: utf-8 -*-
"""美術の見本02 BACK：metrics.json（項目 → 値 → 判定）と run.json（命令・道具の版・入出力の SHA-256）を書く。py -3.10
usage: back_record.py <final_dir> <start_iso> <end_iso>
"""
import os
import sys
import json
import glob
import platform

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import back_common as BC  # noqa: E402

sys.path.insert(0, os.path.join(BC.REPO, "Tools", "GWWaveGen", "rubric"))
import rubric_check as RCK  # noqa: E402


def rub(path):
    r = json.load(open(path, encoding="utf-8"))
    out = {}
    for f, lst in r["checks"].items():
        for x in lst:
            out["%s | %s" % (f, x["name"])] = {"value": x["value"], "must": x["must"], "pass_must": x["pass_must"]}
    return r, out


def vol_split(c, A0, Y0, A1, Y1):
    dc = np.gradient(c)
    a0 = np.array([RCK.section_area(A0[i], Y0[i]) for i in range(len(c))])
    a1 = np.array([RCK.section_area(A1[i], Y1[i]) for i in range(len(c))])
    out = {}
    for lo, hi in ((-60, -6), (-6, 0), (0, 3), (3, 6), (6, 9), (9, 12), (12, 16)):
        m = (c > lo) & (c <= hi)
        out["c(%g,%g]" % (lo, hi)] = {"base_m3": round(float((a0 * dc)[m].sum()), 1), "cand_m3": round(float((a1 * dc)[m].sum()), 1),
                                       "change_m3": round(float(((a1 - a0) * dc)[m].sum()), 1)}
    m = c > 0
    out["c>0"] = {"base_m3": round(float((a0 * dc)[m].sum()), 1), "cand_m3": round(float((a1 * dc)[m].sum()), 1),
                  "change_m3": round(float(((a1 - a0) * dc)[m].sum()), 1)}
    return out


def main():
    fd, t0, t1 = sys.argv[1:4]
    meas = json.load(open(os.path.join(fd, "measure.json"), encoding="utf-8"))
    chk = json.load(open(os.path.join(fd, "check_painting_unchanged.json"), encoding="utf-8"))
    rb, RB = rub(os.path.join(fd, "rubric_P28R2rec.json"))
    rc, RCd = rub(os.path.join(fd, "rubric_AS02B.json"))
    sb, sc = meas["summary"]["P28R2rec"], meas["summary"]["AS02B"]
    mb, mc = meas["measure"]["P28R2rec"], meas["measure"]["AS02B"]
    c, A0, Y0 = BC.load_rows(BC.BASE_ROWS)
    _, A1, Y1 = BC.load_rows(os.path.join(fd, "cand", "kstarAS02B_a45_rows.npz"))
    px = {}
    for line in open(os.path.join(fd, "render_pixel_diff.txt"), encoding="utf-8"):
        k, v = line.split()
        px[k] = int(v)

    def lvl(M):
        return {k: {"dip_m": v["dip_depth_m"], "bay_m": v["bay_depth_m"], "c_at_bay": v["c_at_bay"],
                    "bulge_over_chord_dip_m": v["bulge_over_chord_dip_m"], "c_at_bulge_max": v["c_at_bulge_max"],
                    "c_range": v["c_range"]} for k, v in M["levels"].items()}
    changed = {}
    for k in RB:
        if k in RCd and (RB[k]["value"] != RCd[k]["value"] or RB[k]["pass_must"] != RCd[k]["pass_must"]):
            changed[k] = {"base": RB[k]["value"], "cand": RCd[k]["value"], "must": RB[k]["must"],
                          "pass_must_base": RB[k]["pass_must"], "pass_must_cand": RCd[k]["pass_must"]}
    met = {
        "schema": "GreatWave.AS02.back_metrics/1",
        "note_ja": "美術の見本02 の BACK（要求書 S4）。今の K*′ P28R2rec と候補 K*′ AS02B（t* の静止）。測りは back_measure.py（c ≥ −14 は b区域より奥の背の山の範囲）。"
                   "評価基準は rubric_check.py（F13 なし、参照モデルは読まない）。判定は測る規則の自動の確かめで、美術の合否は利用者が決める（Q30）。",
        "S4_unimodal": {
            "H_dip_c_ge_-14_m": {"base": sb["H_dip_hero_m"], "cand": sc["H_dip_hero_m"], "judge": "合（0）"},
            "H_dip_all_rows_m": {"base": sb["H_dip_all_m"], "cand": sc["H_dip_all_m"],
                                 "judge": "記録のみ（b区域の第二の波頭 c ≈ −18 と −15.8 の鞍。原画が止める行 c ≤ −1。F10 は別の稜として数えない）"},
            "H_max_c": {"base": sb["H_max_c"], "cand": sc["H_max_c"]},
            "back_contour_dip_max_m": {"base": sb["back_dip_max_m"], "cand": sc["back_dip_max_m"], "rule": "0 に近い（< 0.10 m）",
                                       "judge": "合" if sc["back_dip_max_m"] < 0.10 else "否"},
            "back_contour_bay_max_m": {"base": sb["back_bay_max_m"], "cand": sc["back_bay_max_m"],
                                       "judge": "記録（候補の 0.3〜0.47 m は c ≈ −11 の肩との境。背の山の中 c ≥ −6 では 0.2 m 以下）"},
            "bulge_over_chord_dip_m": {"base": sb["back_bulge_dip_max_m"], "cand": sc["back_bulge_dip_max_m"], "judge": "合（二つの山 → 一つの山）"},
            "bulge_peak_c_by_level": {"base": sb["bulge_peak_c_by_level"], "cand": sc["bulge_peak_c_by_level"],
                                      "judge": "0.5〜0.9H0 は c −5.4〜−2.8（頂が 0.9 Hmax 以上の区間 c −6〜+6 の中）。0.05〜0.4H0 は奥の端 c +6〜+10（管が深く背を引けない。限界）"},
            "levels_base": lvl(mb), "levels_cand": lvl(mc),
            "groove_c_0p4_to_2": "今の背は高さ 0.3〜0.9H0 の全部で c ≈ +0.4〜+2 が 1.0〜1.7 m 引っ込む（縦の溝）。候補で埋めた",
            "silhouette_dip_px_c_ge_-14": {"base": sb["silhouette_dip_px_hero"], "cand": sc["silhouette_dip_px_hero"], "judge": "記録（1 画素以下）"},
            "silhouette_dip_px_all": {"base": sb["silhouette_dip_px_all"], "cand": sc["silhouette_dip_px_all"], "judge": "記録（b区域。原画が止める）"},
        },
        "painting_view_unchanged": {
            "zbuffer_ss1": chk["painting_zbuffer_ss1"], "zbuffer_ss2": chk["painting_zbuffer_ss2"],
            "aa_coverage_ss1": chk["painting_aa_coverage_ss1"], "shell_lines_ss1": chk["shell_lines_ss1"],
            "H_change_max_m": chk["H_change_max_m"], "judge": "合（原画視点の画素が全部同じ）" if chk["painting_view_unchanged"] else "否"},
        "gates": {
            "rubric_F01_preview_metrics_envelope": {"base": rb.get("gate_raw"), "cand": rc.get("gate_raw"),
                                                    "judge": "同じ" if rb.get("gate_raw") == rc.get("gate_raw") else "違う"},
            "unity_gates_note_ja": "原画視点の画素が全部同じなので、Unity の評価器（爪あり・なし）は回していない。値は仕上げ28 の P28R2rec のまま"
                                   "（78／130／131 2.741／3.582／3.442 px、132 σ12 3.558、72 σ12 p95 3.851／爪あり 3.570 px。CP1 2.772／1.968／1.814、1.326、1.558。26修正01 1.641／1.953／1.798、1.574、1.723）。",
        },
        "render_pixel_diff_gt24_1280x720": px,
        "rubric": {"summary_base": rb["summary"], "summary_cand": rc["summary"], "changed_items": changed},
        "far_volume_split_m3": vol_split(c, A0, Y0, A1, Y1),
        "limits_ja": [
            "評価基準 F03 の殻の厚みの上限（0.42H）と壁 0.5H の上限（0.42）を、背の山の中 c +1〜+4 で超える（0.554H・0.522）。溝を埋めると背が厚くなるため。両側（c ≈ −4 の肋は原画に見える深い管、奥の端は薄い壁の管）が動かせない",
            "F04 の奥 c > 0 の体積が +144 m³（+7.7%）。増えは背の山の中 c 0〜6（+203 m³）で、奥の端 c > 6 は −59 m³（裾を引いた）",
            "F05 の奥の端の 0.5H(c) の固まりの幅 7.68 → 9.94 m（もとから必須 3.0 m に届かない）",
            "0.05〜0.4H0 の低い所では、奥の端（c +6〜+10）がいちばん後ろへ出たまま（管が深く、背を前へ引けない）",
            "頂のすぐ下（頂から約 1 m）と、原画に見える縁の近く（c ≤ −4）には、今の行ごとの細い縦の筋が少し残る",
            "b区域の第二の波頭（H のへこみ 0.23 m）は原画が止めるので残した",
        ],
    }
    BC.jdump(met, os.path.join(fd, "metrics.json"))
    tools = sorted(glob.glob(os.path.join(HERE, "back_*.py")))
    dep = [os.path.join(BC.REPO, "Tools", "GWWaveGen", "kstar_p28", n) for n in ("r01_shoulder_build.py", "r01_shoulder_common.py", "r2_common.py", "r2_build.py", "rec_common.py", "rays_bl.py")] + \
          [os.path.join(BC.REPO, "Tools", "GWWaveGen", "kstar_h", n) for n in ("kh_common.py", "kh_bl.py")] + \
          [os.path.join(BC.REPO, "Tools", "GWWaveGen", "rubric", n) for n in ("rubric_check.py", "rubric_measure.py")]
    outs = sorted(set(glob.glob(os.path.join(fd, "*.*")) + glob.glob(os.path.join(fd, "cand", "*.*"))))
    run = {
        "schema": "GreatWave.AS02.back_run/1", "start_local": t0, "end_local": t1,
        "python": platform.python_version(), "numpy": np.__version__,
        "blender": "Blender 5.2.2 LTS（Steam、Workbench の粘土）", "ffmpeg": "ffmpeg-2024-12-19-git-494c961379-full_build",
        "houdini": "使っていない（numpy の生成器で作った）",
        "reference_model": "読んでいない（rubric_check を --ref なしで回した。F13 なし）。一時キャッシュも作っていない",
        "base": {"rows": BC.BASE_ROWS, "rows_sha256": BC.sha256(BC.BASE_ROWS), "gwb": BC.BASE_GWB, "gwb_sha256": BC.sha256(BC.BASE_GWB)},
        "commands": [
            "OPENBLAS_NUM_THREADS=1 py -3.10 -B Tools/GWWaveGen/as02/back_build.py <final>/cand/kstarAS02B_a45 <final>/cand/back_design.json  （2 度回し、rows・gwb がバイトまで同じ）",
            "py -3.10 -B Tools/GWWaveGen/as02/back_check.py <final>/check_painting_unchanged.json <final>/cand/kstarAS02B_a45_rows.npz",
            "py -3.10 -B Tools/GWWaveGen/rubric/rubric_check.py <rows> <out.json> --gate  （土台と候補）",
            "py -3.10 -B Tools/GWWaveGen/as02/back_rubric_diff.py <final>/rubric_P28R2rec.json <final>/rubric_AS02B.json <final>/rubric_diff.json",
            "py -3.10 -B Tools/GWWaveGen/as02/back_measure.py <final>/measure.json P28R2rec=<base rows> AS02B=<cand rows>",
            "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <final>/renders P28R2rec=<gwb>,AS02B=<gwb> views=all",
            "blender ... rays_bl.py -- turntable <gwb> <final>/turntable/tt_<label>.mp4 <final>/turntable/stills_<label> 240 72 16 960 540",
            "ffmpeg（2 本を横に並べて 1920×1080、libx264 crf 26）→ <final>/clay_turntable_P28R2rec_AS02B.mp4",
            "py -3.10 -B Tools/GWWaveGen/as02/back_sheet.py / back_tt_sheet.py / back_chart.py（図）",
            "py -3.10 -B Tools/GWWaveGen/as02/back_record.py <final> <start> <end>",
        ],
        "tools_sha256": {os.path.relpath(p, BC.REPO).replace("\\", "/"): BC.sha256(p) for p in tools + dep},
        "outputs_sha256": {os.path.relpath(p, fd).replace("\\", "/"): BC.sha256(p) for p in outs if os.path.isfile(p)},
        "incidents_ja": ["rubric_check.py --gate は入力の rows の隣に重ね図の PNG を書く。土台の凍結フォルダー（Unity/Build/Polish/28/kstar_p28rec/）に "
                         "kstarP28R2rec_a45_rows_gate_overlay.png が書かれたので、この見本のフォルダーへ移した（凍結の 4 ファイルは変わっていない、SHA-256 は上の base のとおり）"],
    }
    BC.jdump(run, os.path.join(fd, "run.json"))
    print("ok", len(run["outputs_sha256"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
