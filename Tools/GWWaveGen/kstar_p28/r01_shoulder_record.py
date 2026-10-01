# -*- coding: utf-8 -*-
"""仕上げ28修正01 SHOULDER：試した案の表（trials_table.json）、候補の数値（metrics.json）、実行の記録（run.json）を書く（py -3.10）。
usage: py -3.10 r01_shoulder_record.py <shoulder_dir> <start_iso> <end_iso> [fig]
  fig を付けない最初の呼び出しで trials_table.json と metrics.json を書き、図を作った後に fig を付けて run.json を書く。
"""
import os
import sys
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_shoulder_common as S  # noqa: E402

NOTES = {
    "S1": ("stretch k 0.8（c −10 → +9）", "背の殻が少し太るだけ。後ろから見た頭巾は同じ（少し大きく見える）"),
    "S2": ("offset 外へ 4 m（c −2 → +11）＋defold σ2", "奥の側が持ち上がって平らな頂の大きな塊。ドームは大きくなった。行をまたぐ折れ 325/164"),
    "S3": ("defold σ2.5 だけ", "縦の襞は減るが輪郭は同じ。主の行の頂の弦 104°（Q17 を割る）、行をまたぐ折れ 266/83"),
    "S5": ("offset 内へ −5 m（c −1 → +10）＋defold", "管の天井に当たり、頂は最大 1.4 m しか下がらない。見た目はほぼ同じ"),
    "S7": ("stretch k 1.0 を手前の側へ（c −1 → −12）＋defold", "手前の背が後ろへ出て、真上から中ほどの後ろの膨らみが増えた"),
    "S8": ("stretch k 2.5（c −2 → +9）", "後ろ 65° で奥の端の縦の壁が長い斜面に。真上から後ろへ長い鰭"),
    "S9": ("stretch k 1.6（c −2 → +9）", "S8 の弱い版。同じ傾向"),
    "S10": ("stretch k 2.0（c −8 → +12、端 2.5 m）", "S8 と同じ傾向。真後ろで左の裾に暗い凹み"),
    "S11": ("stretch k 2.5（c −4 → +12、端 2.5 m）", "S8 と同じ傾向"),
    "S13": ("stretch k 2.0 を c +2 より奥だけ（c +2 → +12、端 3 m）", "主の行を厚くしなくても F03 の否は同じ（殻 0.48、壁 0.49、S 字 2）、F04 33.48 m。真後ろで伸ばしの始まりに濃い縦の凹み。採らない"),
    "S12": ("stretch k 2.0（c −8 → +12、端 3 m）＋望む変位のならし → 候補 P28R01SH", "後ろ 65°・−c 側で奥の側が長い斜面（肩）に読める。中ほどの丸い頂は同じ。真後ろの丸い山の輪郭は同じ。真上から奥の端が後ろへ引かれた鰭"),
}
KEYS = ["R6_p99", "back_elliptic_frac", "back_plan_bow_0.5H0_L8_max_m", "back_plan_bow_0.7H0_L8_max_m", "F04_side_width_0.5H0_m",
        "cross_row_folds_gt30_gt60"]


def rnd(v, n=3):
    return None if v is None else round(float(v), n)


def load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}


def main():
    sd = sys.argv[1]; t_start = sys.argv[2]; t_end = sys.argv[3]
    fin = os.path.join(sd, "final")
    m1 = load(os.path.join(sd, "metrics", "try_metrics.json")); m2 = load(os.path.join(sd, "metrics", "try_metrics2.json"))
    md = load(os.path.join(fin, "metrics_dome.json"))
    allm = {**m1, **m2, **md}
    rows = []
    for lab in ["P28R2rec", "S1", "S2", "S3", "S5", "S7", "S8", "S9", "S10", "S11", "S13", "S12"]:
        m = allm.get(lab, {})
        d = NOTES.get(lab, ("土台（採用中の K*′ P28R2rec）", "後ろ 65°・真後ろ・回り台で丸い頭巾（ドーム）"))
        des = os.path.join(sd, "try", lab.lower(), "design.json")
        rows.append({"label": lab, "design": load(des) if os.path.isfile(des) else None, "what_ja": d[0], "note_ja": d[1],
                     **{k: m.get(k) for k in KEYS}, "arcs_main_min_deg": (m.get("arcs_pm2m") or {}).get("main_min_deg"),
                     "arcs_main_rows_lt110": (m.get("arcs_pm2m") or {}).get("main_rows_lt110")})
    S.jdump({"schema": "GreatWave.Polish28r01.shoulder_trials/1",
             "note_ja": "どの案も原画視点で見える頂点を動かさない（土台の z バッファーの見える四角形の頂点を止める）。目で見た判定は Blender の粘土（rays_bl.py）。"
                        "数値は r2_metrics.py（評審の j_dome と同じ読み）。S4・S6 は S5 と同じ作りの小さい版で、記録だけ（図なし）。", "rows": rows},
            os.path.join(fin, "trials_table.json"))
    ev = load(os.path.join(fin, "eval", "kh_eval_summary.json"))
    cands = {c["label"]: c for c in ev.get("candidates", [])}
    chk = load(os.path.join(fin, "check_painting_unchanged.json"))
    hv = load(os.path.join(sd, "houdini", "r01_shoulder_hiplc_verify.json"))

    def pick(lab):
        c = cands.get(lab)
        if not c:
            return None
        g = c["gate"]; lf = c["gate_lf"]; ru = c["rubric"]["summary"]
        q1 = c["Q21_1"]; q2 = c["Q21_2"]; q3 = c["Q21_3"]
        out = {"gate_78_130_131_max_px": [round(g[k]["max_px"], 3) for k in ("78", "130", "131")],
               "gate_132_lf_sigma12_max_px": round(lf["132"]["max_px"], 3), "gate_72_lf_sigma12_p95_px": round(lf["72"]["p95_px"], 3),
               "gate_pass_lf_sigma12": c["gate_pass_lf"], "rubric_must_fail": ru["must_fail"], "rubric_target_miss": ru["target_miss"],
               "bulge6_R6_p99_max": [round(c["bulge6"]["R6"]["p99"], 3), round(c["bulge6"]["R6"]["max"], 3)],
               "sag3m_p99_max": [round(q1["sag_3m"]["p99_m"], 3), round(q1["sag_3m"]["max_m"], 3)],
               "surface_fit_back_p99_m": round(q1["surface_fit_6x12"]["back"]["p99_m"], 3),
               "fullness_area_over_H2_c-2_2": round(q2["area_over_H2_mean_c-2_2"], 3), "shell_over_H_c-2_2": round(q2["shell_over_H_mean_c-2_2"], 3),
               "b_region_top_vs_smooth_median_p90_max_px": [rnd(q3["top_vs_top_smooth"].get(k), 2) for k in ("median_px", "p90_px", "max_px")],
               "mesh_cross_row_gt30_gt60": [c["mesh"]["cross_row_gt30_all"], c["mesh"]["cross_row_gt60_all"]]}
        fails = {}
        for fam, lst in c["rubric"]["checks"].items():
            for it in lst:
                if not it.get("pass_must", True):
                    fails["%s %s" % (fam, it["name"])] = it["value"]
        out["rubric_must_fail_items"] = fails
        return out
    res = {lab: pick(lab) for lab in ("P28R01SH", "P28R2rec", "R4", "Kstar_26R01")}
    for v in res.values():
        if v:
            v.pop("rubric_must_fail_items", None)     # 評価器の要約の項目名は文字化けしているので、表（kh_eval_table.md）から読む
    a, b = {}, {}
    tab = os.path.join(fin, "eval", "kh_eval_table.md")
    if os.path.isfile(tab):
        for ln in open(tab, encoding="utf-8"):
            cs = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(cs) >= 4 and cs[0].startswith("F") and cs[0][1:3].isdigit():
                if "✗" in cs[2]:
                    a[cs[0]] = cs[2]
                if "✗" in cs[3]:
                    b[cs[0]] = cs[3]
    metrics = {
        "schema": "GreatWave.Polish28r01.shoulder_metrics/1",
        "candidate": "K*′ P28R01SH (Unity/Build/Polish/28r01/shoulder/cand/kstarP28R01SH_a45.*)",
        "base": "K*′ P28R2rec (Unity/Build/Polish/28/kstar_p28rec)",
        "dome_by_eye_ja": "消えていない。後ろ 65°・−c 側の後ろで、奥の端の縦の壁が長い斜面（肩）に変わったが、中ほどの丸い頂（頭巾の頭）は土台と同じ。"
                          "真後ろの丸い山の輪郭は同じ（原画で止まる頂の線と、管の口から見える奥の唇で決まる）で、左下の裾に暗い凹みが増えた。"
                          "真上からは奥の端が後ろへ長く引かれた鰭になる（Q21 の「从上方看右边…后拉的凸起」と同じ種類）。",
        "painting_view_unchanged": chk,
        "kh_eval": res,
        "rubric_must_fail_new_vs_base": {k: a[k] for k in a if k not in b},
        "rubric_must_fail_fixed_vs_base": {k: b[k] for k in b if k not in a},
        "rubric_must_fail_changed_value_both_fail": {k: [a[k], b[k]] for k in a if k in b and a[k] != b[k]},
        "dome_metrics_r2": {k: md.get(k) for k in ("P28R01SH", "P28R2rec", "R4")},
        "houdini_scene": hv,
        "silhouette_freedom_from_behind": load(os.path.join(fin, "silhouette_freedom.json")),
        "why_dome_stays_ja": "後ろから見た山の輪郭は行ごとの頂の高さ H(c) で決まる。c ≤ −1 の行は頂が原画の輪郭（78・130・131・132）を描くか、見える点が頂の 0.25 m 以内にあり、"
                             "空の射線の天井も頂の 0.1〜0.5 m 上で、H を変えられない（丸い頂の右半分と頭）。c 9.6〜13.2 の行は管の口から唇が見え、H はその唇の約 1 m 上に止まる（奥の端の落ち）。"
                             "背の殻を後ろへ伸ばしても H(c) は変わらない（候補と土台の H の差 0）ので、真後ろの丸い山の輪郭はそのまま残る。"
                             "動かせるのは c 0〜9 の頂を上げる向き（天井 20.6〜24.8 m。RIDGE の向き）と、管の天井の分だけ下げる向き（試した S5 で最大 1.4 m）だけ。",
        "closing_criteria_ja": {
            "後ろ 65° と回り台でドームが見えない": "満たさない（目で見て）",
            "b区域が 3 つの房": "土台と同じ（1 つ）。原画視点は画素まで同じ",
            "F04 ≤ 18.5 m で本体が薄くない": "F04 34.85 m（土台 27.64）で悪化。薄くはない（量感の比 2.20、殻の比 1.62）が、Q16 の横の厚み・Q21 の「奥の厚い壁」に逆らう（F03 壁 0.5H/H 0.90）",
            "78・130・131 ≤ 4 px（定義どおり）": "土台と同じ 2.439／3.230／3.355（kh_eval の幾何の読み）。Unity の読みも原画視点が画素まで同じなので土台と同じと見込む（描いていない）",
            "132・72 σ12 ≤ 4 px": "土台と同じ 3.790／3.682（kh_eval の幾何の読み）",
            "134・267": "原画視点が画素まで同じなので土台と同じ（不合格のまま）。描いていない",
            "t* の頂と手前の尾が弧": "手前の尾 123.3°、本体 114.0°（110° 未満 0 行。土台 123.3°・113.3°）"},
    }
    S.jdump(metrics, os.path.join(fin, "metrics.json"))
    if len(sys.argv) > 4 and sys.argv[4] == "fig":
        code = sorted(glob.glob(os.path.join(HERE, "r01_shoulder_*.py")))
        deps = [os.path.join(HERE, n) for n in ("r2_common.py", "rec_common.py", "r2_build.py", "r2_metrics.py", "judge_dome_defs.py", "rays_bl.py", "rays_views.json")]
        deps += [os.path.join(S.REPO, "Tools", "GWWaveGen", "kstar_h", n) for n in ("kh_common.py", "kh_eval.py", "kh_bl.py", "kh_houdini.py")]
        outs = sorted(glob.glob(os.path.join(sd, "cand", "*"))) + sorted(glob.glob(os.path.join(fin, "sheets", "*"))) + \
            [os.path.join(S.REPO, "Houdini", "Polish28", "r01_shoulder.hiplc"), os.path.join(fin, "metrics.json"), os.path.join(fin, "trials_table.json"),
             os.path.join(fin, "check_painting_unchanged.json"), os.path.join(fin, "metrics_dome.json"), os.path.join(fin, "eval", "kh_eval_table.md")]
        ins = [S.BASE_GWB, S.BASE_ROWS, S.KEEPOUT_CACHE, S.PROTECT_CACHE, S.R4_ROWS,
               os.path.join(S.REPO, "Unity", "Build", "Design", "38", "outlines", "unity", "prep", "ds38_hero_linemask_f32.bin")]
        rel = lambda p: os.path.relpath(p, S.REPO).replace("\\", "/")
        dc = os.path.join(sd, "_tmp", "deleted_caches_sha256.txt")
        run = {
            "schema": "GreatWave.Polish28r01.shoulder_run/1", "start_local": t_start, "end_local": t_end,
            "time_box_h": 6,
            "commands": [
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_build.py <sd>/try/sN/kstarSH_sN <sd>/try/sN/design.json   # 試した案 S1〜S13（S12 が候補と同じ）",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_eval.py --no-mesh --out <sd>/try/s13/eval S13=…   # S13 の F03 を確かめた",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_freedom.py <sd>/final/silhouette_freedom.json <sd>/cand/kstarP28R01SH_a45_rows.npz",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_build.py <sd>/cand/kstarP28R01SH_a45 <sd>/cand/shoulder_design.json",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_check.py <sd>/final/check_painting_unchanged.json <sd>/cand/kstarP28R01SH_a45_rows.npz",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_eval.py --out <sd>/final/eval P28R01SH=… P28R2rec=… R4=… Kstar_26R01=…",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r2_metrics.py <sd>/final/metrics_dome.json P28R01SH=… P28R2rec=… R4=… S12=…",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r2_metrics.py <sd>/metrics/try_metrics.json …; … try_metrics2.json …",
                "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <sd>/final/renders P28R2rec=…,P28R01SH=… views=all",
                "blender … --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- turntable <gwb> <sd>/final/renders/turntable_<label>.mp4 <sd>/final/renders/turntable_<label>",
                "blender … --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <sd>/trials_renders S1=…,…,S11=… views=b65_back65_clay+b90_back_straight+v6_top_down",
                "\"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe\" Tools/GWWaveGen/kstar_p28/r01_shoulder_houdini.py <sd> Houdini/Polish28/r01_shoulder.hiplc <sd>/houdini/r01_shoulder_hiplc_verify.json",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_fig.py <sd>",
                "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_record.py <sd> <start> <end> fig"],
            "shoulder_dir": rel(sd),
            "determinism": "r01_shoulder_build.py を同じ設計で 2 度回し、rows がバイトまで同じ（try/s12 と cand）",
            "code_sha256": {rel(p): S.sha256(p) for p in code + deps if os.path.isfile(p)},
            "inputs_sha256": {rel(p): S.sha256(p) for p in ins if os.path.isfile(p)},
            "outputs_sha256": {rel(p): S.sha256(p) for p in outs if os.path.isfile(p)},
            "reference_model": {"path_note": "評価器 kh_eval.py の F13 と量感の比べの数値だけ。SHA-256 を照合した一時キャッシュで読み、終わりに消した。生成器は読まない（F13-1）。参照モデルを描いた画像はない",
                                "sha256_expected": "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40",
                                "deleted_caches": open(dc, encoding="utf-8").read().strip().splitlines() if os.path.isfile(dc) else []},
            "forbidden_paths_touched": "なし（旧試作・G:\\research の禁止の場所は読まず、一覧も取らず。find / のような全体をたどる命令は使っていない）",
            "git": "書き込みなし（add・commit・push をしていない）",
            "heavy_numpy_concurrency": "重い numpy は 1 つずつ（kh_eval の間に走らせたのは Blender の粘土の描画だけ）",
        }
        S.jdump(run, os.path.join(fin, "run.json"))
    print("ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
