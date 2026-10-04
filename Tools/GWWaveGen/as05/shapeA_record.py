# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：targets.json の L・P の目標と K の守る決まりを、測った値で表にし、run.json（道具・入力・出力の SHA-256）を書く。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_record.py <targets_measured.json> <rules.json> <render_dir>
出力：Unity/Build/Polish/sample05/shapeA/targets_check.json・run.json
"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402

TARGETS = C.P + "/sample05/study/targets.json"


def get(d, path):
    cur = d
    for k in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
    return cur


def judge(v, op, val):
    if v is None:
        return None
    if op == ">=":
        return v >= val
    if op == "<=":
        return v <= val
    if op == "between":
        return val[0] <= v <= val[1]
    return None


def main():
    tm, rl, rd = sys.argv[1:4]
    T = json.load(open(TARGETS, encoding="utf-8"))
    M = json.load(open(tm, encoding="utf-8"))
    R = json.load(open(rl, encoding="utf-8"))
    rows = []
    for t in T["targets"]:
        tid, metric, pf = t["id"], t["metric"], t["pass_if"]
        res = {"id": tid, "kind": t["kind"], "metric": metric, "pass_if": pf, "baseline_sample04": t.get("baseline_sample04")}
        if "{" in metric:
            pre, rest = metric.split("{", 1)
            keys, post = rest.split("}", 1)
            vals = {}
            ok = True
            for k in keys.split(","):
                v = get(M, pre + k + post)
                vals[k] = v
                thr = pf["value"][k] if isinstance(pf["value"], dict) else pf["value"]
                j = judge(v, pf["op"], thr)
                ok = ok and bool(j)
            res["value"] = vals; res["pass"] = ok
        elif pf["op"] == "ranges":
            v = get(M, metric)
            res["value"] = v
            ok = v is not None
            if ok:
                for k, (lo, hi) in pf["value"].items():
                    x = sum(v.get(q, 0) for q in k.split("+")) if "+" in k else v.get(k)
                    ok = ok and x is not None and lo <= x <= hi
            res["pass"] = bool(ok)
        else:
            v = get(M, metric)
            res["value"] = v
            res["pass"] = judge(v, pf["op"], pf["value"])
        rows.append(res)
    app = M.get("appearance") or {}
    k = {"K-G2": R.get("K-G2", {}).get("verdict"), "K-S8": R["K-S8"]["verdict"], "K-S9": R["K-S9"]["verdict"], "K-S4": R["K-S4"]["verdict"],
         "K-S10": R["K-S10"]["verdict"], "K-top": R["K-top"]["verdict"], "K-claws": R["K-claws"]["verdict"], "K-boat": R["K-boat"]["verdict"],
         "K-T5": {"value": app.get("T5_small_white_blobs_on_hero_indigo"), "pass": app.get("T5_small_white_blobs_on_hero_indigo") == 0},
         "K-T6": {"value": app.get("T6_inner_edge_band_pale_share"), "pass": (app.get("T6_inner_edge_band_pale_share") or 1) <= 0.02}}
    out = {"schema": "GreatWave.AS05A.targets_check/1", "date": time.strftime("%Y-%m-%d %H:%M"), "targets_source": TARGETS, "measured": tm, "rules": rl,
           "render": rd, "L_P": rows, "K": k,
           "summary": {"must_pass": sum(1 for r in rows if r["kind"] == "must" and r["pass"]), "must_total": sum(1 for r in rows if r["kind"] == "must"),
                       "should_pass": sum(1 for r in rows if r["kind"] == "should" and r["pass"]), "should_total": sum(1 for r in rows if r["kind"] == "should"),
                       "failed": [r["id"] for r in rows if not r["pass"]],
                       "K_failed": [kk for kk, v in k.items() if (v.get("pass") is False if isinstance(v, dict) else v != "pass")]},
           "judge_ja": "目標の値は進行役の既定で、利用者の言葉ではない。美術が届いたかは利用者が決める（Q29・Q30）"}
    C.jdump(C.OUT + "/targets_check.json", out)
    tools = sorted(glob.glob(C.REPO + "/Tools/GWWaveGen/as05/shapeA_*")) + [C.REPO + "/Unity/Assets/GreatWave/ArtSample05/Editor/AS05ABoatRender.cs"]
    outs = [C.ROWS05A, C.GWB05A, C.CAND + "_meta.json", C.OUT + "/hero/row_labels_AS05A.npy", C.L3_JSON, C.L3_JSON.replace(".json", ".bin"),
            C.OUT + "/l3/layer3_labels.npy", C.OUT + "/mesh/hero_smooth_as05a.json", C.OUT + "/mesh/hero_smooth_as05a.bin",
            C.OUT + "/mesh/white_mask_as05a_f32.bin", C.OUT + "/mesh/union_AS05A.json", C.OUT + "/mesh/union_AS05A.bin",
            C.OUT + "/claws/ds33_claw_layout.json", C.OUT + "/claws/ds33_claw_frames_f32.bin", C.OUT + "/l3/boat_scale.json",
            C.OUT + "/hero_pkg_AS05A/ds27_keypose.json", C.OUT + "/attr/a/s01a_hero_attr_v2_f32.bin", tm, rl, C.OUT + "/targets_check.json"]
    run = {"schema": "GreatWave.AS05A.run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": "美術の見本05 のやり方 A（Q33）：③ を主役波の左前の別の小さな砕け波（layer3）にし、一艘目の船を原画のカメラを中心とする相似で手前へ、② に縁の頂と溝を作り、左の唇を引っ込めた。",
           "commands": ["bash Tools/GWWaveGen/as05/shapeA_pipeline.sh（shapeA_hero → pl29 → s01_param → s01a → as02_asm_pkg → shapeA_mesh → shapeA_l3 → shapeA_labels → shapeA_claws → w4_merge ×2）",
                        "py -3.10 -B Tools/GWWaveGen/as05/shapeA_boat.py（船の倍率）",
                        "BOAT_S=<倍率> bash Tools/GWWaveGen/as05/shapeA_render.sh %s views,tt,full,t28" % os.path.basename(rd),
                        "RB=…/sample05/shapeA/render LG=…/logs BEFORE=…/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh %s" % os.path.basename(rd),
                        "py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py measure …/measure/cand_AS05A.json …/measure/targets_AS05A_%s.json" % os.path.basename(rd),
                        "py -3.10 -B Tools/GWWaveGen/as05/shapeA_rules.py <render> …/measure/rules_AS05A.json",
                        "py -3.10 -B Tools/GWWaveGen/as05/shapeA_clay.py（AS05A・AS04F、全部の視点）",
                        "py -3.10 -B Tools/GWWaveGen/as05/shapeA_sheets.py %s" % os.path.basename(rd),
                        "py -3.10 -B Tools/GWWaveGen/as05/shapeA_record.py …"],
           "tools_sha256": {p.replace(C.REPO + "/", ""): C.sha(p) for p in tools if os.path.isfile(p)},
           "inputs_sha256": {p.replace(C.REPO + "/", ""): C.sha(p) for p in (C.ROWS04F, C.WAVE4_F1, C.WAVE4_F1.replace(".json", ".bin"),
                                                                            C.P4 + "/assemble/render/FX1/full/ids_noline_noclaws.png",
                                                                            C.P + "/sample03/assemble/claws35/ds33_claw_layout.json", TARGETS)},
           "outputs_sha256": {p.replace(C.REPO + "/", ""): C.sha(p) for p in outs if os.path.isfile(p)},
           "render_report": rd + "/as03asm_render_report.json",
           "reference_model_read": False, "photos_read": False, "git": "add・commit・push はしていない"}
    C.jdump(C.OUT + "/run.json", run)
    print(json.dumps(out["summary"], ensure_ascii=False))
    for r in rows:
        print(r["id"], r["kind"], r["pass"], json.dumps(r["value"], ensure_ascii=False)[:160])
    print(json.dumps(k, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
