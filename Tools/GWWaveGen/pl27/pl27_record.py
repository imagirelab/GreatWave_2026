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
    # ---- 修正 1 回目（2026-09-30。独立の検査の直すべき点 2 つと、記録の直し）
    fx = {}
    for nm in ("determinism_F_final_pkglog", "repro_F_final_logoff_only"):
        q = os.path.join(B, "repro", nm + ".json")
        if os.path.isfile(q):
            R_ = J(q)
            fx[nm] = dict(path=rel(q), sha256=sha(q), off_used=R_.get("off_used", R_.get("off")), all_same=R_["all_same"],
                          layers=[(r["tau"], r["same_rgba16"], r["same_lo_rgba8"], r["max_diff_counts16"]) for r in R_["layers_checked"]])

    def gdiff(var):
        b_, a_ = J(os.path.join(F, "F_final", "gates", var + ".json"))["gates"], J(os.path.join(B, "F_p27", "gates", var + ".json"))["gates"]
        return {k: [b_[k]["value"], a_[k]["value"]] for k in b_ if b_[k]["value"] != a_[k]["value"]}
    k5g = "(5g) 面の反転（30 Hz、向きの決まった最後のコマと比べる）"
    Zs = np.load(os.path.splitext(si_p)[0] + "_series.npz")
    m06 = Zs["tip_jump_m"] > 0.6
    last06 = int(np.nonzero(m06)[0].max())
    g06 = dict(t_s=[round(float(Zs["t"][m06].min()), 4), round(float(Zs["t"][m06].max()), 4)],
               tau_s=[round(float(Zs["tau"][m06].min()), 4), round(float(Zs["tau"][m06].max()), 4)],
               tip_dir_deg_at_last=round(float(Zs["tip_dir_deg"][last06]), 2),
               max_after_m=round(float(np.nanmax(Zs["tip_jump_m"][last06 + 1:])), 4),
               ja="地面の唇先の移動が 0.6 m を超えるコマの体験の時刻・物理の時刻の範囲と、その最後のコマの唇先の向き、その後の最大（seat_items_F_final_series.npz の tip_jump_m）")
    i111 = out["backlog_items"]["111"]
    out["fix_round_01"] = dict(
        date_local="2026-09-30", start_local="2026-09-30T20:55+08:00",
        must_fix=[dict(item_ja="111 の美術優先30 の式（pl27_seat_items.py）",
                       before_ja="連続性の検査一式（P13）を足し、t* = K* を入れていなかった（af30_evidence.py の ok111 と違う）",
                       after_ja="af30_evidence.py の ok111 のとおり（t* の唇先の向き < −20°、1 コマの向きの変化 < 3°、唇先の 1 コマの移動 < 0.6 m、t* = K*）。"
                                "P13 は 111 の式に入らない。満たさないのは地面で測った唇先の移動（波の約 20 m/s の進みを含む）だけ",
                       verdicts_111=i111["verdicts"], af30_formula_failed=i111["value"].get("af30_formula_failed"),
                       af30_formula_failed_wave_frame=i111["value"].get("af30_formula_failed_wave_frame"),
                       tip_jump_m_per_frame=dict(ground=i111["value"]["tip_jump_max_m_per_frame"], wave_frame=i111["value"]["tip_jump_max_m_per_frame_wave_frame"]),
                       ground_over_0p6=g06,
                       figure="Docs/Evidence/Polish/27/fig_pl27_111_tip.png"),
                  dict(item_ja="F_final の作り直し（ds28r01f_pipeline.py・ds28r01f_determinism.py・ds28r01f_p20.py・pl27_repro_check.py）",
                       before_ja="決定性と P20 の台本は、包みの生成の記録の off（F_final は []）だけで生成器を作り直すので、仕上げ27 で既定に入った 2 つの名前が入り、"
                                 "F_final と違う中身を作った（repro_F_final_logoff_only：τ −2.0・−1.5 s の層が 521・603 カウント違う）。一式は F_final の名前で新しい既定の中身を作った",
                       after_ja="ds28r01f_pkglog.package_off：記録の f_on に無い F の名前を切る（F_final では balance_swell_calm・sea_sample_range）。決定性の台本で F_final の 4 層が"
                                "バイトまで同じ（determinism_F_final_pkglog。--out で書いたので F_final の determinism_check.json は書き換えていない）。一式は、既にある包みの"
                                "記録に無い名前が今の既定で入る時に生成の前で止まる（--tag F_final で確かめた。F_final のファイルの時刻は変わらない）。"
                                "設計28修正01 の記録の再現の節に［仕上げ27］の注記",
                       checks=fx)],
        record_corrections=dict(
            P2_calm_excluded=dict(before=Gb["gates"]["P2"]["detail"]["calm_painting_excluded_ja"], after=Ga["gates"]["P2"]["detail"]["calm_painting_excluded_ja"]),
            P3_full_interval_worst_frac_row=dict(before=[Gb["gates"]["P3"]["detail"]["full_interval_worst_frac"], Gb["gates"]["P3"]["detail"]["full_interval_worst_row"]],
                                                 after=[Ga["gates"]["P3"]["detail"]["full_interval_worst_frac"], Ga["gates"]["P3"]["detail"]["full_interval_worst_row"]]),
            gate_value_changes={v: gdiff(v) for v in ("default", "alt", "default_fine", "default_fine_stop13", "default_q13")},
            P13_5g_at=dict(before=Gb["gates"]["P13"]["detail"][k5g]["at"], after=Ga["gates"]["P13"]["detail"][k5g]["at"]),
            seat_view_note_ja="設計27 の DS27Formation の座席の視点は τ −4.889〜−1.700 s の 4 枚が同じ画像（空だけ）なので、座席の差 0 画素に意味があるのは τ −0.950 s より後"),
        not_done_ja="P13 の 4 項目の直しはこの修正でも行っていない（［利用者の言葉］の 2 回目の修正は使っていない。計画 §5.2・§5.3 の「連続性の一式の直し」「測って直す」から外れる。"
                    "記録の第 1.4 節と D-P27-3）")
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
    # 修正 1 回目（2026-09-30）：111 の式を直した道具の回し直しと、F_final の作り直しの確かめ（上の pl27_seat_items.py は直した版で回し直した）
    run["commands_fix_round_01"] = [
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_seat_items.py --package Unity/Build/Design/28R01F/F_final/art_on --kstar Unity/Build/Design/28R01F/kstar_F_final --timewarp Unity/Build/Design/28R01F/F_final/timewarp_F_final.json --gates-json Unity/Build/Design/28R01F/F_final/gates/default_ds27.json --out Unity/Build/Polish/27/seat_items/seat_items_F_final.json",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_fig_111.py --items Unity/Build/Polish/27/seat_items/seat_items_F_final.json --out Docs/Evidence/Polish/27/fig_pl27_111_tip.png",
        "py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_determinism.py --package Unity/Build/Design/28R01F/F_final/art_on --out Unity/Build/Polish/27/repro/determinism_F_final_pkglog.json",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_repro_check.py --package Unity/Build/Design/28R01F/F_final/art_on --off \"\" --out Unity/Build/Polish/27/repro/repro_F_final_logoff_only.json",
        "py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_pipeline.py --kstar Unity/Build/Polish/27/_no_such_kstar --tag F_final（生成の前に止まることの確かめ）",
        "py -3.10 -B Tools/GWWaveGen/pl27/pl27_record.py"]
    ins = [os.path.join(F, "F_final", "art_on", f) for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin", "ds27_sea.npz")]
    ins += [os.path.join(F, "F_final", "timewarp_F_final.json"), gb_p, os.path.join(F, "F_final", "gates", "default_ds27.json")]
    ins += [os.path.join(F, "kstar_final", f) for f in sorted(os.listdir(os.path.join(F, "kstar_final"))) if not f.startswith("_")]
    ins += [P("Tools", "GWContext", "seat_v1.json"), P("Docs", "Evidence", "Design", "26", "ds26_conditions.json"),
            P("Unity", "Build", "Design", "50", "release", "runs", "capture5", "frames_capture.csv"),
            P("Unity", "Build", "Design", "47", "flow", "unity", "main", "ds47_frames.csv"),
            P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_params.json"), P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_model.py"),
            P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_generate.py"),
            P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_pkglog.py"), P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_determinism.py"),
            P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_p20.py"), P("Tools", "GWWaveGen", "ds28r01f", "ds28r01f_pipeline.py"),
            P("Tools", "GWWaveGen", "pl27", "pl27_seat_items.py"), P("Tools", "GWWaveGen", "pl27", "pl27_repro_check.py"),
            P("Tools", "GWWaveGen", "pl27", "pl27_fig_111.py"),
            P("Tools", "GWWaveGen", "af30_evidence.py")]
    run["inputs"] = {rel(p): sha(p) for p in ins if os.path.isfile(p)}
    outs = [os.path.join(B, "F_p27", "art_on", f) for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin", "ds27_sea.npz", "ds28r01f_generate_log.json", "ds27_checks.json")]
    outs += [os.path.join(B, "F_p27", "timewarp_F_p27.json"), ga_p, os.path.join(B, "F_p27", "gates", "default_ds27.json"), os.path.join(B, "F_p27", "scan.json"),
             os.path.join(B, "F_p27", "overlap", "overlap_default.json"), os.path.join(B, "review", "review_F_p27.json"),
             os.path.join(B, "diag", "diag_F_final.json"), os.path.join(B, "diag", "diag_F_p27.json"), si_p, os.path.join(B, "unity", "unity_before_after.json"), rg_p,
             os.path.join(B, "repro", "repro_F_p27.json"), os.path.join(B, "repro", "repro_F_final_off.json"),
             os.path.join(B, "repro", "determinism_F_final_pkglog.json"), os.path.join(B, "repro", "repro_F_final_logoff_only.json"),
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
        "111": "%s（美術優先30 の式、地面の唇先の移動の読み。満たさないのは %s だけで、連続性の検査一式は式に入らない）。波の枠の移動の読みでは %s。"
               "項目の言葉の読みは地面 %s・波の枠 %s（記録）" % (bi["111"]["verdicts"]["verdict_af30_formula"], "・".join(bi["111"]["value"]["af30_formula_failed"]) or "なし",
                                                 bi["111"]["verdicts"]["verdict_af30_formula_wave_frame"], bi["111"]["verdicts"]["verdict_item_words"],
                                                 bi["111"]["verdicts"]["verdict_item_words_wave_frame"]),
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
