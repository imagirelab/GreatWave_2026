# -*- coding: utf-8 -*-
"""仕上げ27：記録の道具。群の出力（Git 対象外の Unity/Build/Polish/27/ と 28修正01 の F_final）を読み、SHA-256 を照合して、
Docs/Evidence/Polish/27/metrics.json（項目 → 値 → 判定）と run.json（コマンド・版・入出力の SHA-256）を書く。
直す前と後の包みの層ごとの差（本体の列・端の行・t*）もここで数え直す（生成器の記録を使わない）。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl27/pl27_record.py
"""
import hashlib
import json
import os
import platform
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EV = os.path.join(REPO, "Docs", "Evidence", "Polish", "27")
B = os.path.join(REPO, "Unity", "Build", "Polish", "27")
F = os.path.join(REPO, "Unity", "Build", "Design", "28R01F")


def P(*a):
    return os.path.join(REPO, *a)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def J(p):
    return json.load(open(p, encoding="utf-8"))


def load_pkg(d):
    K = J(os.path.join(d, "ds27_keypose.json"))
    L, nv, nu = K["layers"], K["rows"], K["cols"]
    raw = np.fromfile(os.path.join(d, "ds27_pos_rgba16.bin"), "<u2").reshape(L, nv, nu, 4)[..., :3].astype(np.float64)
    return K, np.array(K["bbox_min"]) + raw / 65535.0 * np.array(K["bbox_size"])


def gate_vals(G):
    g = G["gates"]
    p13 = g["P13"]["detail"]
    items = {k: dict(value=v["value"], pass_=bool(v["pass"])) for k, v in p13.items() if isinstance(v, dict) and "value" in v}
    return dict(P2=dict(value=g["P2"]["value"], pass_=bool(g["P2"]["pass"]), worst_row=g["P2"]["detail"]["worst_row"], worst_tau=g["P2"]["detail"]["worst_tau"],
                        main_row_max_ratio=g["P2"]["detail"]["main_row_max_ratio"], calm_excluded=g["P2"]["detail"].get("calm_painting_excluded_ja"),
                        trough_ahead_min_m=g["P2"]["detail"]["trough_ahead_min_m"]),
                P3=dict(value=g["P3"]["value"], pass_=bool(g["P3"]["pass"]), worst_row=g["P3"]["detail"]["worst_row"],
                        full_interval_worst_frac=g["P3"]["detail"]["full_interval_worst_frac"]),
                P13=dict(value=g["P13"]["value"], pass_=bool(g["P13"]["pass"]), items=items,
                         failed=[k for k, v in items.items() if not v["pass_"]]),
                summary=G.get("summary_all") or G.get("summary"),
                all_gates={k: dict(value=v["value"] if not isinstance(v["value"], (dict, list)) else v["value"], pass_=bool(v["pass"])) for k, v in g.items()},
                gates_ds28={k: dict(value=v.get("value"), pass_=bool(v.get("pass"))) for k, v in (G.get("gates_ds28") or {}).items() if isinstance(v, dict)})


def main():
    out = dict(schema="GreatWave.pl27.metrics/1", number="仕上げ27", group_ja="設計27 単発砕波（設計26 を含む）", backlog=[80, 106, 107, 108, 111],
               time_box_days=0.5, evidence_kind_ja="numpy の生成器・関門の検査器・調べの道具、Unity の PC オフスクリーン描画、Release のプレイヤーの PC の画面のコマ。HMD 実機ではない")
    run = dict(schema="GreatWave.pl27.run/1", python=platform.python_version(), numpy=np.__version__, machine=platform.platform(), unity="6000.4.3f1",
               commands=[], inputs={}, outputs={})
    # ---- (1) P2・P3・P13：前（F_final）と後（F_p27）
    gb_p, ga_p = os.path.join(F, "F_final", "gates", "default.json"), os.path.join(B, "F_p27", "gates", "default.json")
    Gb, Ga = J(gb_p), J(ga_p)
    before, after = gate_vals(Gb), gate_vals(Ga)
    db, da = J(os.path.join(B, "diag", "diag_F_final.json")), J(os.path.join(B, "diag", "diag_F_p27.json"))
    Kb, Pb = load_pkg(os.path.join(F, "F_final", "art_on"))
    Ka, Pa = load_pkg(os.path.join(B, "F_p27", "art_on"))
    kn = np.array(Kb["knot_tau"])
    assert np.array_equal(kn, np.array(Ka["knot_tau"]))
    d = np.linalg.norm(Pa - Pb, axis=-1)
    per = d.reshape(len(kn), -1).max(1)
    dv = d.max(0)
    body = np.zeros_like(dv, bool)
    body[40:231, 18:395] = True
    glog = J(os.path.join(B, "F_p27", "art_on", "ds28r01f_generate_log.json"))["result"]
    p20 = {k: dict(max_vertex_diff_m=round(v["max_vertex_diff_m"], 4), at=v.get("at")) for k, v in glog["p20"].items()}
    tw_a, tw_b = J(os.path.join(B, "F_p27", "timewarp_F_p27.json")), J(os.path.join(F, "F_final", "timewarp_F_final.json"))
    out["Q10_P2_P3_P13"] = dict(
        label_ja="［利用者の言葉］Q10：関門 P2・P3・P13（設計27 の連続性の一式）を採用の動きで測り、安く直せる所を直す",
        before=dict(package=rel(os.path.join(F, "F_final", "art_on")), gates=rel(gb_p), gates_sha256=sha(gb_p), **before),
        after=dict(package=rel(os.path.join(B, "F_p27", "art_on")), gates=rel(ga_p), gates_sha256=sha(ga_p), **after),
        diag_before=dict(P2_all=db["P2"]["all"], P2_window_covered=db["P2"]["window_covered"], P2_window_not_covered=db["P2"]["window_not_covered"],
                         P2_ext_sea_all=db["P2_ext"]["all"], P3=dict(max=db["P3"]["max"], worst_row=db["P3"]["worst_row"], over_0p1_rows=db["P3"]["over_0p1_rows"]),
                         P13=db["P13"]),
        diag_after=dict(P2_all=da["P2"]["all"], P3=dict(max=da["P3"]["max"], worst_row=da["P3"]["worst_row"], over_0p1_rows=da["P3"]["over_0p1_rows"]),
                        P13_counts={k: da["P13"][k].get("count") for k in ("acc_2", "edge_5b", "stretch_5c", "flips_5g")}),
        fixes=[dict(name="num_sea_sample_range", kind_ja="数値の条件", value="周りの海の標本 a −480〜130 m（F_final は −330〜130 m）", gate="P2",
                    effect_ja="包み（位置・白・keypose）は変えず、ds27_sea.npz の標本の範囲だけが広がる"),
               dict(name="num_balance_swell_calm", kind_ja="数値の条件", value="搬送波の振幅の窓の釣り合いのうねりの項に κ_s(τ) を掛ける", gate="P2・P3",
                    effect_ja="τ −4〜0 s の A_c と、シートの外端の帯・端の行の海だけが変わる（P20 %.3f m）。本体の列と t* は変わらない" % p20.get("num_balance_swell_calm（仕上げ27。海の釣り合いの κ_s だけを切った形との差）", {}).get("max_vertex_diff_m", float("nan")))],
        package_diff=dict(knots_same=True, bbox_same=Kb["bbox_min"] == Ka["bbox_min"] and Kb["bbox_size"] == Ka["bbox_size"],
                          tstar_layer_max_m=float(per[-1]), layers_tau_le_m4_max_m=float(per[kn <= -4.0 + 1e-9].max()),
                          max_m=float(per.max()), max_at_tau=float(kn[int(per.argmax())]),
                          per_tau_max_m={("%.2f" % t): round(float(per[int(np.argmin(np.abs(kn - t)))]), 4) for t in (-4.0, -3.5, -3.0, -2.5, -2.0, -1.5, -1.0, -0.5, -0.1, 0.0)},
                          body_rows40_230_cols_jB_jE_max_m=float(dv[body].max()),
                          vertices_changed_gt_1cm=int((dv > 0.01).sum()),
                          rows_with_changes_gt_1cm=sorted({int(r) for r in np.nonzero(dv > 0.01)[0]}),
                          pos_sha256_before=Kb["pos_sha256"], pos_sha256_after=Ka["pos_sha256"],
                          twhite_same=Kb["twhite_sha256"] == Ka["twhite_sha256"]),
        timewarp_same_t_tau=tw_a["t"] == tw_b["t"] and tw_a["tau"] == tw_b["tau"],
        p20=p20, generate_seconds=glog.get("seconds"), sea_npz=glog.get("sea_npz"))
    ok2 = after["P2"]["pass_"]
    ok3 = after["P3"]["pass_"]
    out["Q10_P2_P3_P13"]["verdict"] = dict(P2="合格" if ok2 else "不合格", P3="合格" if ok3 else "不合格",
                                          P13="不合格（%s。限界として仕上げ28 へ）" % "・".join(after["P13"]["failed"]) if not after["P13"]["pass_"] else "合格")
    # ---- Unity の前後
    ub = J(os.path.join(B, "unity", "unity_before_after.json"))
    rr = J(os.path.join(B, "unity", "F_p27", "ds27_render_report.json"))
    out["unity_before_after"] = dict(diffs=ub["diffs"], render=dict(passed=rr["passed"], protectedUnchanged=rr["protectedUnchanged"], meshUnchanged=rr["meshUnchanged"],
                                                                     sceneSha256=rr["sceneSha256"], posSha256=rr["posSha256"], warpFileSha256=rr["warpFileSha256"],
                                                                     totalSeconds=rr["totalSeconds"]))
    # ---- (2) ds26_conditions.json
    dc = P("Tools", "GWWaveGen", "ds26_conditions.json")
    DC = J(dc)
    out["ds26_conditions_copy"] = dict(path=rel(dc), sha256=sha(dc), source=DC["q11_applied"]["source"], changes=[c["key"] for c in DC["q11_applied"]["changes"]],
                                       numbers_changed=DC["q11_applied"]["numbers_changed"], verdict="作った（Q11 を反映。数値は変えない）")
    # ---- (3) 座席の静止画
    ss = J(os.path.join(EV, "seat_stills.json"))
    out["seat_stills"] = dict(stills=ss["stills"], figure=ss["figure"]["path"], verdict="置き換えた（体験の場面 DS50_Release の座席 v1。Release のプレイヤーの PC の画面のコマ）")
    # ---- (4) 80・106〜108・111
    si_p = os.path.join(B, "seat_items", "seat_items_F_final.json")
    SI = J(si_p)
    out["backlog_items"] = {k: dict(name_ja=v["name_ja"], value={kk: vv for kk, vv in v["value"].items() if kk != "continuity_P13"},
                                    verdicts={kk: vv for kk, vv in v.items() if kk.startswith("verdict")}, reading_ja=v.get("reading_ja"))
                            for k, v in SI["items"].items()}
    out["backlog_items_source"] = dict(path=rel(si_p), sha256=sha(si_p), seat=SI["seat"], rows=SI["rows"], landmarks=SI["landmarks"])
    # ---- 評価器（爪あり・爪なし）
    rg_p = os.path.join(B, "regress", "ds30_tstar_regress.json")
    if os.path.isfile(rg_p):
        RG = J(rg_p)
        ev = {}
        for s in ("t28_claws", "t28_white"):
            v = RG["sets"][s]
            rows = v["verdict"]["silhouettes_vs_kstar_prime"]["rows"]
            ev[s] = {"78": rows["78"]["unity_max_px"], "130": rows["130"]["unity_max_px"], "131": rows["131"]["unity_max_px"],
                     "132_sigma12_max": round(v["lfgate"]["132_sigma12_max"], 4), "72_sigma24_p95": round(v["lfgate"]["72_sigma24_p95"], 4),
                     "verdict_changes_vs_28r01": v["verdict"]["verdict_changes_vs_28r01"], "items_over_0p5": v["verdict"]["items_over_0p5"],
                     "sym_worst_diff_vs_29r01_px": v["sym"]["worst_diff_vs_29r01_px"], "flat_266_267": v["sym"]["flat_painting_view_266_267"]}
        out["painting_evaluator"] = dict(output=rel(rg_p), output_sha256=sha(rg_p), stage8_design40_41_output_sha256="4ca57d3a973d94d4feca5dfc9c11397e4246b36d5236986df5046c2a35b8931e",
                                         same_as_previous=sha(rg_p) == "4ca57d3a973d94d4feca5dfc9c11397e4246b36d5236986df5046c2a35b8931e",
                                         input_ja="設計41 の t* の組（Unity/Build/Design/41/model/unity/t28_claws・t28_white の t28 の写し）。段階8確認・段階9確認と同じ入力（体験の場面の t* はこの群で変えていない）",
                                         values=ev,
                                         cp1_26r01_ja=dict(cp1={"78": 2.772, "130": 1.968, "131": 1.814, "132": 1.326, "72": 1.558},
                                                           r26_01={"78": 1.641, "130": 1.953, "131": 1.798, "132": 1.574, "72": 1.723},
                                                           source="Docs/Progress/Design_40_ja.md 第 0 節の 3・第 3 節の表（ds40_acceptance.json の cp1_26r01_regression_stated）"))
    # ---- 再現の抜き取り
    rp = {}
    for nm in ("repro_F_p27", "repro_F_final_off"):
        q = os.path.join(B, "repro", nm + ".json")
        if os.path.isfile(q):
            R_ = J(q)
            rp[nm] = dict(package=R_["package"], off=R_["off"], all_same=R_["all_same"], layers=[(r["tau"], r["same_rgba16"], r["same_lo_rgba8"]) for r in R_["layers_checked"]])
    out["Q10_P2_P3_P13"]["repro_sampled"] = dict(results=rp, note_ja="1 つのプロセスで節点の 5 層を作り直した抜き取り。全層の一致は確かめていない")
    # ---- 時間
    pt = J(os.path.join(B, "F_p27", "pipeline_timing.json"))
    out["timing"] = dict(start_local="2026-09-30T19:45:31+08:00", pipeline=pt["timing"], note_ja="終わりの時刻は記録の本文")
    # ---- run.json
    run["commands"] = [
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_diag.py --package Unity/Build/Design/28R01F/F_final/art_on --kstar Unity/Build/Design/28R01F/kstar_F_final --gates-json Unity/Build/Design/28R01F/F_final/gates/default_ds27.json --out Unity/Build/Polish/27/diag/diag_F_final.json --ext-a-min -480",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_ds26_conditions.py",
        pt["command"],
        "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds28r01f/run_ds28r01f_unity.ps1 -Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Log p27_F_p27 -Version art_on -Warp default -Package Build/Polish/27/F_p27/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Polish/27/unity/F_p27 -Stills \"t03=-4.889,t05=-3.202,t065=-2.450,t08=-1.700,t095=-0.950,t11=-0.203,tstar=0\" -Views \"painting,seat,side_left\" -Skip \"video,frames\"",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_fig_unity.py",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_diag.py --package Unity/Build/Polish/27/F_p27/art_on --kstar Unity/Build/Polish/27/kstar_F_p27 --gates-json Unity/Build/Polish/27/F_p27/gates/default_ds27.json --out Unity/Build/Polish/27/diag/diag_F_p27.json",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_fig_gates.py --before Unity/Build/Polish/27/diag/diag_F_final.json --after Unity/Build/Polish/27/diag/diag_F_p27.json --out Docs/Evidence/Polish/27/fig_pl27_p2_p3_before_after.png",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_repro_check.py --package Unity/Build/Polish/27/F_p27/art_on --out Unity/Build/Polish/27/repro/repro_F_p27.json",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_repro_check.py --package Unity/Build/Design/28R01F/F_final/art_on --off balance_swell_calm,sea_sample_range --out Unity/Build/Polish/27/repro/repro_F_final_off.json",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_seat_stills.py",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_seat_items.py --package Unity/Build/Design/28R01F/F_final/art_on --kstar Unity/Build/Design/28R01F/kstar_F_final --timewarp Unity/Build/Design/28R01F/F_final/timewarp_F_final.json --gates-json Unity/Build/Design/28R01F/F_final/gates/default_ds27.json --out Unity/Build/Polish/27/seat_items/seat_items_F_final.json",
        "py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Polish/27/regress --sets t28_claws,t28_white",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_record.py"]
    ins = [os.path.join(F, "F_final", "art_on", f) for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin", "ds27_sea.npz")]
    ins += [os.path.join(F, "F_final", "timewarp_F_final.json"), gb_p, os.path.join(F, "F_final", "gates", "default_ds27.json")]
    ins += [os.path.join(F, "kstar_final", f) for f in sorted(os.listdir(os.path.join(F, "kstar_final"))) if not f.startswith("_")]
    ins += [P("Tools", "GWContext", "seat_v1.json"), P("Docs", "Evidence", "Design", "26", "ds26_conditions.json"),
            P("Unity", "Build", "Design", "50", "release", "runs", "capture5", "frames_capture.csv"),
            P("Unity", "Build", "Design", "47", "flow", "unity", "main", "ds47_frames.csv"),
            P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_params.json"), P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_model.py"),
            P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_generate.py")]
    run["inputs"] = {rel(p): sha(p) for p in ins if os.path.isfile(p)}
    outs = [os.path.join(B, "F_p27", "art_on", f) for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin", "ds27_sea.npz", "ds28r01f_generate_log.json", "ds27_checks.json")]
    outs += [os.path.join(B, "F_p27", "timewarp_F_p27.json"), ga_p, os.path.join(B, "F_p27", "gates", "default_ds27.json"), os.path.join(B, "F_p27", "scan.json"),
             os.path.join(B, "F_p27", "overlap", "overlap_default.json"), os.path.join(B, "review", "review_F_p27.json"),
             os.path.join(B, "diag", "diag_F_final.json"), os.path.join(B, "diag", "diag_F_p27.json"), si_p, os.path.join(B, "unity", "unity_before_after.json"), rg_p,
             os.path.join(B, "repro", "repro_F_p27.json"), os.path.join(B, "repro", "repro_F_final_off.json"),
             P("Tools", "GWWaveGen", "ds26_conditions.json")]
    outs += [os.path.join(EV, f) for f in sorted(os.listdir(EV)) if f.endswith(".png") or f == "seat_stills.json"]
    run["outputs"] = {rel(p): sha(p) for p in outs if os.path.isfile(p)}
    bi = out["backlog_items"]

    def vv(k, extra=""):
        v = bi[k]["verdicts"]
        return "%s（美術優先30 の式。項目の言葉の読みは %s%s、記録）" % (v["verdict_af30_formula"], v["verdict_item_words"], extra)
    out["summary_verdicts"] = {
        "Q10 P2（F_p27）": out["Q10_P2_P3_P13"]["verdict"]["P2"], "Q10 P3（F_p27）": out["Q10_P2_P3_P13"]["verdict"]["P3"],
        "Q10 P13（F_p27）": "不合格（4/12。限界として仕上げ28 へ）" if not after["P13"]["pass_"] else "合格",
        "ds26_conditions.json の写し": "作った", "座席の静止画 3 枚": "置き換えた（体験の場面の座席 v1）",
        "80": vv("80"), "106": vv("106"), "107": vv("107"),
        "108": "仰角の読み %s・真上の読み %s" % (bi["108"]["verdicts"]["verdict_elevation_reading"], bi["108"]["verdicts"]["verdict_overhead_reading"]),
        "111": vv("111", "（地面の移動の読み）。波の枠の移動の読みは %s" % bi["111"]["verdicts"].get("verdict_item_words_wave_frame")),
        "原画視点の評価器（爪あり・爪なし）": "段階9確認と同じ値（出力の SHA-256 が同じ）" if (out.get("painting_evaluator") or {}).get("same_as_previous") else "要確認"}
    with open(os.path.join(EV, "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(EV, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("P2 %s → %s、P3 %s → %s、P13 %s → %s" % (before["P2"]["value"], after["P2"]["value"], before["P3"]["value"], after["P3"]["value"],
                                                  before["P13"]["failed"], after["P13"]["failed"]))
    print("書いた：metrics.json・run.json（入力 %d、出力 %d）" % (len(run["inputs"]), len(run["outputs"])))


if __name__ == "__main__":
    main()
