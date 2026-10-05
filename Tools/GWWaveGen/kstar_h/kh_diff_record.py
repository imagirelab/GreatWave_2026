# -*- coding: utf-8 -*-
"""候補 H1 の「参照モデルと意図して変えた所」（ルーブリック第 4 節 D1〜D6）と出典の記録を、評価の結果（kh_eval の json）から書く。py -3.10
参照モデル（wave_repair_zbrush2.obj）は他者の展示作品のスキャン（作者・所蔵は未確認、D18）。生成器（kh_design）は参照モデルの網を読まない。
usage: py -3.10 kh_diff_record.py <eval_dir> <label> <out.json>
"""
import os
import sys
import json


def pick(R, fid, key):
    for x in R["checks"].get(fid, []):
        if key in x["name"]:
            return {"name": x["name"], "value": x["value"], "must": x["must"], "pass_must": x["pass_must"]}
    return None


def main(eval_dir, label, out):
    E = json.load(open(os.path.join(eval_dir, label, label + "_kh_eval.json"), encoding="utf-8"))
    R = json.load(open(os.path.join(eval_dir, label, label + "_rubric_check.json"), encoding="utf-8"))
    rec = {
        "schema": "GreatWave.kstar_h.difference_record/1",
        "candidate": label,
        "reference": "wave_repair_zbrush2.obj (SHA-256 AB4124F9...3D40) and the photos in 北斎参考: a scan of someone else's exhibited "
                     "sculpture (author and collection unconfirmed, D18). Used as a reference only (layout, proportions, 3-D large forms).",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。大きな形と配置の考え方・比率だけを参考にし、形は写していない。",
        "method": "Houdini network /obj/kstar_h_design (Houdini/Design28R01/kstar_h.hiplc): CTRL ramps -> per-section guide curves "
                  "(Tools/GWWaveGen/kstar_h/kh_design.py, a concentric-shell section family: round back, round top arc, lip blade and head, "
                  "near-circular barrel, foot into a front trough) -> b-region ledge -> side edges -> Skin.  The generator never reads the "
                  "model mesh; the reference enters only as numbers (shell/H, R/H ratios in the rubric) and through the F13 proximity check.",
        "F13_proximity": E.get("F13_proximity"),
        "deliberate_differences": [
            {"id": "D1", "what": "smoother back than the reference (no carved waves on the back)",
             "measure": [pick(R, "F03", "曲率の符号"), pick(R, "F03", "ざらつき")],
             "reference_values": "inflections 3-5, roughness 10-26 (x1e-3)", "views": "V3 V5 V8"},
            {"id": "D2", "what": "no plinth / ball base: the foot flows into a front trough and the open sea",
             "measure": [pick(R, "F08", "鉛直の段"), pick(R, "F08", "前の谷")], "views": "V3 V4 V9"},
            {"id": "D3", "what": "lip tip and claws from the painting (the claws themselves are stage 6); the body follows the painting's large-form "
                                "outline 132/72 (sigma 12 px), not the model's lip",
             "measure": [E.get("gate_lf")], "views": "V1 V2 V7"},
            {"id": "D4", "what": "b region (second crest) edges from the painting's band (Q21-3), three lobes as one smooth ledge",
             "measure": [E.get("Q21_3")], "views": "V1 V7 V8"},
            {"id": "D5", "what": "far end: our own length and height (a thin curl closing to the sea by c +20), not the model's lip running to c +12 "
                                "at 0.6-0.75 H",
             "measure": [pick(R, "F05", "奥の端"), pick(R, "F10", "奥の端の高さの落ち")], "views": "V4 V5 V9"},
            {"id": "D6", "what": "near crest line = the painting's 45 deg crest (78/130/131), not the model's shoulder",
             "measure": [{k: E["gate"][k] for k in ("78", "130", "131")}], "views": "V1 V6"},
        ],
    }
    json.dump(rec, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print("written", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
