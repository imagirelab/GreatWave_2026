# -*- coding: utf-8 -*-
"""K*′ 精修 R1 の記録：参照モデルとの意図した違い（D1〜D6、数値つき、出典）、評審の must-fix への対応、決めたこと（推奨を選んだもの）、
原画と基準がぶつかる所（py -3.10）。入力は kh_R1_deliver.py の出力（評価器の要約と追加の表）だけ。
  py -3.10 kh_R1_record.py <final dir>
"""
import os
import sys
import json

import numpy as np

sys.dont_write_bytecode = True


def chk(r, fid, name_part):
    for x in r["rubric"]["checks"].get(fid, []):
        if name_part in x["name"]:
            return {"name": x["name"], "value": x["value"], "must": x["must"], "pass_must": x["pass_must"]}
    return None


def main(d):
    summ = json.load(open(os.path.join(d, "eval", "kh_eval_summary.json"), encoding="utf-8"))
    cand = {x["label"]: x for x in summ["candidates"]}
    r = cand["R1"]
    sup = json.load(open(os.path.join(d, "kstarR1_supplementary.json"), encoding="utf-8"))
    design = json.load(open(os.path.join(d, "kstarR1_design.json"), encoding="utf-8"))
    z = np.load(os.path.join(d, "kstarR1_a45_rows.npz"))
    c, A, Y = z["c"], z["A"], z["Y"]
    H = Y.max(1)
    H0 = float(H[int(np.argmin(np.abs(c)))])
    far = {("c=%+.0f" % cc): round(float(H[int(np.argmin(np.abs(c - cc)))] / H0), 3) for cc in (4, 6, 8, 10, 12, 13, 14, 15)}
    rec = {
        "schema": "GreatWave.kstar_h.R1.difference_record/1",
        "candidate": "K*' R1 (Houdini, refinement loop 1 of candidate H1A)",
        "reference": "wave_repair_zbrush2.obj - a scan of someone else's exhibited sculpture (author and collection unconfirmed, D18). "
                     "Reference only: layout, proportions and 3-D large forms (Q18-Q20). It is never read by the generator or the fit.",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18、確かめるまで開いたまま）。"
                     "配置・比率・大きな形の考え方だけを参考にし、形は写していない（生成器と当てはめは参照の網を読まない）。",
        "method_ja": "形は Houdini の網（Houdini/Design28R01/kstar_h_R1.hiplc の /obj/kstar_h_design：CTRL の ramp → 断面の案内の曲線 → "
                     "唇の上面の断面の形 → b 区域 → 側の縁 → Skin）が作る。参照モデルは F13（0.3 m 以内の頂点の割合）と量感の比較の数値のためにだけ、"
                     "評価器が一時のキャッシュで読み、消す（SHA-256 を Q20H/deleted_caches_sha256.txt に記録）。シーンには参照の節点を残さない。",
        "F13_proximity_all_reference_vertices": r.get("F13_proximity"),
        "deliberate_differences": [
            {"id": "D1", "what_ja": "背の輪郭をもっと滑らかに（樽の中心のまわりの同心の殻、彫りの波なし）。R1：背の足は凹で海へ流れる（下へ潜らない）",
             "F03_inflections": chk(r, "F03", "曲率の符号"), "F03_roughness": chk(r, "F03", "ざらつき"),
             "reference": "変わり目 3〜5、ざらつき 10〜26（×1e-3）", "views": "V3・V5・V8"},
            {"id": "D2", "what_ja": "球の台座なし。足は前の谷へ流れ、谷から前の海へ一続き",
             "F08_step": chk(r, "F08", "鉛直の段"), "F08_trough": chk(r, "F08", "前の谷"), "views": "V3・V4・V9"},
            {"id": "D3", "what_ja": "唇先は原画の大きな輪郭（σ 12 px）に合わせたなめらかな鉤。爪・指は作らない（段階6 で原画から）",
             "gate_large_form_132_72": sup.get("gate_large_form"),
             "rubric_measures_ja": "ルーブリックの爪の根（0.5 m 以内 ≤ 10 %）と指の根（14 本のうち ≤ 3）は、爪・指がまだ無いので段階6 まで該当なし。",
             "views": "V1・V2・V7"},
            {"id": "D4", "what_ja": "b 区域（第二の波頭）の稜と爪の縁は原画の帯から（参照の房・指の位置は使わない）",
             "band_round3_detector": sup.get("band_round3_detector"), "band_by_design_column": sup.get("band_by_design_column"),
             "Q21_3_detector": r.get("Q21_3"),
             "rubric_measures_ja": "帯の縁の高さ S2 ±0.5 m・房 3 つの指の数は段階6（爪）で測る。ここでは帯の上端（稜）と下端（爪の縁）の原画視点の px。",
             "views": "V1・V7・V8"},
            {"id": "D5", "what_ja": "奥の端は我々の設計：原画視点で管の内側の輪郭（72）を唇先が描き、c +15 で静水面まで高さと厚みが一緒に細る巻きで閉じる",
             "H_over_H0_far": far, "F05_far_mass": chk(r, "F05", "奥の端"),
             "reference": "参照は唇の巻きが c +12 まで H 0.6〜0.75 で続く", "views": "V4・V5・V9"},
            {"id": "D6", "what_ja": "手前の頂の線は原画の外輪郭（78/130/131）が決める（K* の断面の枠の a = 0 に頂）。主断面 H0 と最高点は c −1〜+3",
             "gate": {k: r["gate"][k] for k in ("78", "130", "131")}, "H0_m": H0,
             "highest": {"H_m": float(H.max()), "c_m": float(c[int(np.argmax(H))])}, "views": "V1・V6"},
        ],
        "decisions_taken_ja": [
            "系統は H1A（copy A）を続けた（評審の must-fix 10 番：Houdini の系統を 1 つに。H1A の方が関門・曲率の極値・なめらかさで B より良い）。",
            "132・72 は進行役の 20:00 の判断どおり大きな輪郭（σ 12 px）で合わせ、細部込みの値も評価器の表に残す。",
            "中央のドームの原因（側の縁の帯が ±1.5 m で 1 m ごとに振れた）を取り除くため、原画の輪郭はまず本体の大きな形（頂の線・唇・管・殻・"
            "唇の上面の断面の形、鍵 2.5 m おき）で合わせ、側の縁（視線がかすめる所だけ、9 本の列の帯＋唇先の縁）は ±0.3 m・鍵 1.5 m おき・2 階差の罰で最後に使った。",
            "唇の上面の断面の形（lipprof_1〜5）を足した：原画視点で 132 を描くのは主断面のまわりの行のこの断面の線そのものなので、"
            "線の形（凸の頂 → くびれ → 凸の鉤）を断面の側で決め、行ごとに振らない。",
            "当てはめの仕上げは公式の関門と同じ測り方（真値 → 描画と描画 → 真値、kh_R1_snap.Snap.fixed）を残差にした（H1A の近似の目標では 130 が 1.5 px 甘かった）。",
            "唇が自分を突き抜けない（上面と下面の間隔 ≥ 0.35 m の罰、b 区域の谷は唇の厚みの 40 % まで）、頂の列（90）が最も高い、"
            "列 314 は管の中の最も後ろの点、その高さ ≥ 0.325 H（動きの生成器 ds27 の ja が 0.3 H の交差から内壁を作り直すため。H1A は 0.20 H で t* を 4.2 m 外した）。",
            "H(c) の山は 1 つ（c −20〜−1.5 は下がらない、c +3〜+15 は上がらない、0.3 m までのくぼみは許す）、主断面 H0 ≥ 20.3 m、最高点 ≤ 1.04 H0、奥の落ち ≤ 3.3 m/m。",
            "奥の端は c = +15（最後の行）で静水面へ閉じる（crest_height の最後の鍵 = 0）。側の縁と b 区域は海面（y < 0.3 m）を動かさない（H1A は c −60 の行に −0.74 m の谷、c +15 に 2.8 m の段）。",
            "背の丸みは外の面の最も後ろの点から始め、その下は凹の足で海へ流す（遠い行の足の「蹴り」をなくした）。管は最も低い点の手前（262° − lean）で前の面へ渡す（管の面の縦の S 字をなくした）。",
            "唇の上面の断面の形の帯は頂（列 90）から 22 列かけて C1 でなめらかに立ち上げる（5 列の立ち上げでは列 92 に 12〜17° の 1 頂点の折れ＝頂の角ができた。Q17）。",
            "唇の頭の丸み（tip_round、m）は行の高さの 3.5 % を超えない（閉じる低い行で頭が巻きを支配し、行をまたぐ折れが 782 → 189 に減った）。",
            "巻きは H 3.5 m → 2.0 m で消え、それより低い行は単純なふくらみ（小さく押しつぶした巻きが自分と交差しない）。",
            "奥の行（c ≥ 5）の頂の側の縁の帯（edge_1〜5）は 0（原画視点では本体の中に隠れ、輪郭を作らない。中の面を動かさない）。",
            "唇先の縁（edge_tip）と管の壁の帯（edge_6〜9）は、公式の関門の測り方を線形化して解いた（kh_R1_snap.py、≤ 0.35 m）。",
            "F13 は参照の全頂点で測る（kh_eval を変更。評審の独立検査 6.40 % と揃える）。",
        ],
        "conflicts_ja": [
            "F10 奥で頂の線が後ろへ流れる角 ≤ 20° と F04 の幅は、原画視点で奥の部分が管の口（塗られた空）に出ないことと両立しない（K* 58°、第 2 回 51°、A4 48°、H1A 57° も同じ理由）。奥の行の唇先が 72 の輪郭を描くので、奥は後ろへ流す。",
            "72 の唇の下の大きな輪郭（σ 12 px）には、まだ爪の房の間のくぼみ（振幅 約 8〜12 px、波長 2〜3 m）が残る。唇先の縁（edge_tip、列 200 のまわりだけ）で追ったが ±0.35 m の上限で止まる（72 p95 8.4 px）。側の縁の上限（評審の 0.3 m）を守る限り、段階6 の爪の房で合わせるのが筋。",
            "ルーブリック F02 の奥の行（c > +3）の Rmin は、頂の ±3 m の窓に唇の頭（短い唇の奥の行）が入るので 0.13 m になる（頂そのものは 1 頂点の折れ ≤ 8°、弦角 133〜157°）。F08 の鉛直の段 1.0 m は肩の行（H 約 11 m）の管の最も後ろの壁（y < 4 m）で、前の足ではない。",
            "奥の背（c +9〜+12、列 40〜80）に評審の膨らみの測り R4 0.5〜0.8 m が残る（中央の頂のまわりは ≤ 0.1 m）。奥の頂の線が平面で後ろへ流れて戻る所。平面を単調にすると 72 の管の壁の輪郭が 20 px 以上崩れる（試した）。",
        ],
        "design_keys_file": "kstarR1_design.json",
        "fit_log": design.get("fit_log"),
        "snap_log_best": (design.get("snap_log") or {}).get("best"),
    }
    json.dump(rec, open(os.path.join(d, "kstarR1_difference_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({k: rec[k] for k in ("F13_proximity_all_reference_vertices",)}, default=float))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
