# -*- coding: utf-8 -*-
"""設計28修正01：動きの担当の証拠（図 2 枚と数値の JSON）を Docs/Evidence/Design/28R01/ に書く。数値は読むだけで作り直さない。

入力（Git 対象外。Unity/Build/Design/28R01/）：
  art_on・art_off・_twice/art_on/                 パッケージ（修正01 の入れた版＝既定、切った版＝設計28 の物理だけと同じ、決定性の作り直し）
  gates/art_on_default.json・art_on_alt.json・art_off_default.json・ref28_art_on_default_q13table.json   ds28r01_gates.py の出力
  q13/art_on.json・art_off.json・ds28_art_on.json                    ds28r01_q13.py の出力（T1・T2）
  p20/ds28r01_p20.json・launch/ds28r01_launch.json                   ds_rise_overlap の大きさ、唇先の打ち出しの表
  r00/                                                              初回の統合（修正の前）の出力
  Unity/Build/Design/28/gates/art_on_default.json                   設計28 の入れた版の関門（比べるため）
出力（Docs/Evidence/Design/28R01/）：fig_ds28r01_q13_sections.png、fig_ds28r01_claws_timewarp.png、ds28r01_motion_metrics.json
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_evidence.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds28r01_figures as FG  # noqa: E402

REPO = FG.REPO
BR = FG.BR
B28 = FG.B28
EVID = os.path.join(REPO, "Docs", "Evidence", "Design", "28R01")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jl(p):
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def gate_summary(p):
    J = jl(p)
    if J is None:
        return None
    out = {}
    for k, g in list(J["gates"].items()) + list(J.get("gates_ds28", {}).items()) + list(J.get("gates_ds28r01", {}).items()):
        out[k] = dict(pass_=g.get("pass"), value=g.get("value"))
    d = J["gates"]["P13"]["detail"]
    out["P13_items"] = {k: dict(value=v["value"], pass_=v["pass"]) for k, v in d.items() if isinstance(v, dict) and "threshold" in v}
    p15 = J["gates"]["P15"]["detail"]
    out["P15_detail"] = {nm: dict(tau=p15[nm]["tau"], table_tau=p15[nm]["table_tau"], first_white_tau=p15[nm]["first_white_tau"], white_ok=p15[nm]["white_ok"])
                         for nm in ("主断面", "峰で最も高い巻きの行")}
    ex = J.get("gates_ds28", {})
    if ex:
        out["P17_detail"] = dict(main=ex["P17"]["detail"]["main_row"], peak=ex["P17"]["detail"]["peak_row"], worst_row=ex["P17"]["detail"]["worst_row"],
                                 from_jet_onset_max_frac=ex["P17"]["detail"]["from_jet_onset_max_frac"])
        out["P18_detail"] = dict(worst=ex["P18"]["detail"]["worst"], rows_over=ex["P18"]["detail"]["rows_over"],
                                 face_vertical=dict(worst=ex["P18"]["detail"]["record_from_face_vertical"]["worst"],
                                                    rows_over=ex["P18"]["detail"]["record_from_face_vertical"]["rows_over"]))
        out["P19_detail"] = ex["P19"]["detail"]
    out["P16_detail"] = J["gates"]["P16"].get("detail", {}).get("summary") if isinstance(J["gates"]["P16"].get("detail"), dict) else None
    out["failed"] = J.get("summary_all", {}).get("failed")
    out["stage_table"] = J.get("stage_table", {}).get("kind")
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    q_old = jl(os.path.join(BR, "q13", "ds28_art_on.json"))
    q_new = jl(os.path.join(BR, "q13", "art_on.json"))
    gates = jl(os.path.join(BR, "gates", "art_on_default.json"))
    f1 = os.path.join(EVID, "fig_ds28r01_q13_sections.png")
    f2 = os.path.join(EVID, "fig_ds28r01_claws_timewarp.png")
    FG.fig_sections(f1, q_old, q_new, gates)
    FG.fig_claws_warp(f2, q_old, q_new)
    pk = {}
    for nm in ("art_on", "art_off", os.path.join("_twice", "art_on")):
        L = jl(os.path.join(BR, nm, "ds28r01_generate_log.json"))
        K = jl(os.path.join(BR, nm, "ds27_keypose.json"))
        if not K:
            continue
        e = dict(layers=K["layers"], pos_sha256=K["pos_sha256"], twhite_sha256=K["twhite_sha256"], keypose_json_sha256=sha(os.path.join(BR, nm, "ds27_keypose.json")))
        if L:
            r = L["result"]
            e.update(pos_mib=r["pos_mib"], gpu_estimate=r["gpu_estimate"], quantization_max_err_m=r["quantization_max_err_m"], seconds=r["seconds"],
                     variant=r["variant"], switches=r["switches"], lip_launch=r.get("lip_launch"), code_sha256=L["code_sha256"],
                     knot_log=[x for x in L["log"] if "節点" in x or "パッケージ" in x or "検査" in x])
            ch = r.get("checks") or {}
            if ch:
                e.update(hermite_playback_err_m=ch.get("hermite_playback_err_m"), tstar_vs_kstar_world_max_m=ch.get("tstar_vs_kstar_world_max_m"))
        pk[nm.replace("\\", "/")] = e
    det = None
    if "art_on" in pk and "_twice/art_on" in pk:
        a, b = pk["art_on"], pk["_twice/art_on"]
        det = dict(pos_same=a["pos_sha256"] == b["pos_sha256"], twhite_same=a["twhite_sha256"] == b["twhite_sha256"],
                   keypose_json_same=a["keypose_json_sha256"] == b["keypose_json_sha256"])
    ref28 = jl(os.path.join(B28, "art_off_phys", "ds27_keypose.json"))
    tw = jl(os.path.join(HERE, "timewarp_default.json"))
    R = jl(os.path.join(HERE, "ds28r01_params.json"))
    M = dict(
        schema="GreatWave.DS28R01.motion_metrics/1", number="設計28修正01", part_ja="動きの修正（Tools/GWWaveGen/ds28r01/）",
        evidence_kind_ja="numpy の生成器・検査器（パッケージを Hermite で読む）。Unity の描画・HMD の結果ではない",
        figures=[rel(f1), rel(f2)],
        packages=pk, determinism_art_on=det,
        art_off_equals_ds28_art_off_phys=(dict(pos_same=pk.get("art_off", {}).get("pos_sha256") == ref28["pos_sha256"],
                                                twhite_same=pk.get("art_off", {}).get("twhite_sha256") == ref28["twhite_sha256"]) if ref28 and "art_off" in pk else None),
        q13=dict(art_on=q_new["results"] if q_new else None, ds28_art_on=q_old["results"] if q_old else None,
                 art_off=(jl(os.path.join(BR, "q13", "art_off.json")) or {}).get("results"),
                 r00_art_on=(jl(os.path.join(BR, "r00", "q13_art_on.json")) or {}).get("results")),
        gates=dict(art_on_default=gate_summary(os.path.join(BR, "gates", "art_on_default.json")),
                   art_on_alt=gate_summary(os.path.join(BR, "gates", "art_on_alt.json")),
                   art_off_default=gate_summary(os.path.join(BR, "gates", "art_off_default.json")),
                   ds28_art_on_default_under_q13_table=gate_summary(os.path.join(BR, "gates", "ref28_art_on_default_q13table.json")),
                   ds28_art_on_default_design26_table=gate_summary(os.path.join(B28, "gates", "art_on_default.json")),
                   r00_art_on_default=gate_summary(os.path.join(BR, "r00", "gates", "art_on_default.json")),
                   r01_art_on_default=gate_summary(os.path.join(BR, "r01", "gates", "art_on_default.json"))),
        revisions=[
            dict(name="r00（初回の統合）", changes_ja="ds_rise_overlap（頂の高さの表）、κ = 1 の唇を放出の前の動きから打ち出す書き方（帯の点の中心差分）、ds_undercut_kstar の h_on、時間曲線（τ −3.0 s に 0.5 倍）、段階の表（b 0.55〜0.72、d ≥ 0.70）",
                 q13=(jl(os.path.join(BR, "r00", "q13_art_on.json")) or {}).get("results", {}).get("T1", {}).get("pass")),
            dict(name="r01（修正1）", changes_ja="唇先の折れの直し（放出の前の速さ・加速度を頂の動きの解析的な微分に）、ds_tower_peak の時刻 −0.1 s、ds_approach_kstar の水の band_frac 0.06 → 0.15、段階の表の読み（b 0.60〜0.72、d ≥ 0.75）",
                 q13=(jl(os.path.join(BR, "r01", "q13_art_on.json")) or {}).get("results", {}).get("T1", {}).get("pass")),
            dict(name="r02（修正2、提出版）", changes_ja="水の band_frac を設計28 の 0.06 へ戻す（修正1 で P17 が 0.177 と 15% を超えた）", q13=(q_new or {}).get("results", {}).get("T1", {}).get("pass"))],
        p20_direct={v: jl(os.path.join(BR, "p20", "ds28r01_p20_direct_%s.json" % v)) for v in ("rise_off", "no_tower_override")},
        p20_ds_rise_overlap=(jl(os.path.join(BR, "p20", "ds28r01_p20.json")) or {}).get("guidance"),
        launch=jl(os.path.join(BR, "launch", "ds28r01_launch.json")),
        timewarp=dict(default=dict(path=rel(os.path.join(HERE, "timewarp_default.json")), sha256=sha(os.path.join(HERE, "timewarp_default.json")), params=tw["params"]) if tw else None,
                      alt=dict(path="Tools/GWWaveGen/ds27/timewarp_alt.json", sha256=sha(os.path.join(FG.DS27, "timewarp_alt.json")))),
        stage_table=R["stage_table_q13"], rise_overlap=R["rise_overlap"], overrides=dict(approach=R.get("approach"), tower=R.get("tower_overrides")),
        tools_sha256={f: sha(os.path.join(HERE, f)) for f in sorted(os.listdir(HERE)) if f.startswith("ds28r01_") and f.endswith((".py", ".json")) and f != "ds28r01_overlap.py"},
    )
    out = os.path.join(EVID, "ds28r01_motion_metrics.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(M, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(dict(figures=M["figures"], metrics=rel(out)), ensure_ascii=False))


if __name__ == "__main__":
    main()
