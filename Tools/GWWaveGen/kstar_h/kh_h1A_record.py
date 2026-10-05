# -*- coding: utf-8 -*-
"""候補 H1（copy A）の記録：参照モデルとの意図した違い（D1〜D6、数値つき）、出典、決めたこと（推奨を選んだもの）、
原画と基準がぶつかる所（py -3.10）。入力は kh_h1A_deliver.py の出力（評価器の要約と追加の表）だけ。
  py -3.10 kh_h1A_record.py <candH1_A dir>
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
    r = next(x for x in summ["candidates"] if x["label"] == "H1A")
    sup = json.load(open(os.path.join(d, "kstarH1A_supplementary.json"), encoding="utf-8"))
    design = json.load(open(os.path.join(d, "kstarH1A_design.json"), encoding="utf-8"))
    z = np.load(os.path.join(d, "kstarH1A_a45_rows.npz"))
    c, Y = z["c"], z["Y"]
    H = Y.max(1)
    H0 = float(H[int(np.argmin(np.abs(c)))])
    far = {("c=%+.0f" % cc): round(float(H[int(np.argmin(np.abs(c - cc)))] / H0), 3) for cc in (4, 6, 8, 10, 12, 14)}
    rec = {
        "schema": "GreatWave.kstar_h.H1A.difference_record/1",
        "reference": "wave_repair_zbrush2.obj — a scan of someone else's exhibited sculpture (author and collection unconfirmed, D18). "
                     "Reference only: layout, proportions and 3-D large forms (Q18-Q20). It is never read by the generator.",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。"
                     "大きな形と配置の考え方だけを参考にし、形は写していない（生成器は参照の網を読まない）。",
        "method_ja": "形は Houdini の網（/obj/kstar_h_design：CTRL の ramp → 断面の案内の曲線 → b 区域 → 側の縁 → Skin）が作る。"
                     "参照モデルは F13（0.3 m 以内の頂点の割合）と量感の比較の数値のためにだけ、評価器が一時のキャッシュで読み、消す。",
        "F13_proximity": r.get("F13_proximity"),
        "deliberate_differences": [
            {"id": "D1", "what_ja": "背の輪郭をもっと滑らかに（樽の中心のまわりの同心の殻、彫りの波なし）",
             "F03_inflections": chk(r, "F03", "曲率の符号"), "F03_roughness": chk(r, "F03", "ざらつき"),
             "reference": "変わり目 3〜5、ざらつき 10〜26（×1e-3）", "views": "V3・V5・V8"},
            {"id": "D2", "what_ja": "球の台座なし。足は前の谷へ流れ、谷から前の海へ一続き",
             "F08_step": chk(r, "F08", "鉛直の段"), "F08_trough": chk(r, "F08", "前の谷"), "views": "V3・V4・V9"},
            {"id": "D3", "what_ja": "唇先は原画の大きな輪郭（σ 12 px）に合わせた滑らかな鉤。爪は作らない（段階6 で原画から）",
             "gate_large_form_132_72": sup.get("gate_large_form"), "views": "V1・V2・V7"},
            {"id": "D4", "what_ja": "b 区域（第二の波頭）の稜と爪の縁は原画の帯から（参照の房・指の位置は使わない）",
             "band_by_column": sup.get("band_fit_metric"), "Q21_3_detector": r.get("Q21_3"), "views": "V1・V7・V8"},
            {"id": "D5", "what_ja": "奥の端は我々の設計：原画視点で管の内側の輪郭（72）を唇先が描き、c +14 付近で薄い巻きとして閉じる",
             "H_over_H0_far": far, "reference": "唇の巻きが c +12 まで H 0.6〜0.75 で続く", "views": "V4・V5・V9"},
            {"id": "D6", "what_ja": "手前の頂の線は原画の外輪郭（78/130/131）が決める（K* の断面の枠の a = 0 に頂）",
             "gate": {k: r["gate"][k] for k in ("78", "130", "131")}, "views": "V1・V6"},
        ],
        "decisions_taken_ja": [
            "copy A として作業した（進行役の 20:13 の規則：納品は Unity/Build/Q20H/candH1_A と Houdini/Design28R01/kstar_h_A.hiplc）。",
            "132・72 は進行役の 20:00 の判断どおり大きな輪郭（σ 12 px）で合わせ、細部込みの値も評価器の表に残す。",
            "Q21-1 の膨らみの当てはめの罰は 3 m の撓みでなく c 方向の 4 階差（1 m・2 m 刻み）にした。"
            "理由：3 m の撓みは頂の山と奥の閉じ（大きな曲がり）も数えてしまい、H(c) の頂だけで 0.2〜0.4 m になる。4 階差は二次の傾向を除き、幅 1〜4 m の局所の膨らみ・凹みだけを数える。"
            "評価器の 3 m の撓み（暫定 0.15 m）はそのまま表に残す。",
            "ramp の基底は B-Spline（鍵は制御点、2 階まで連続）。鍵の間で値が波打たない。",
            "手前（c ≤ 0）の頂の a は 0 に固定（K* の断面の枠、奥行きと高さの取り替えを防ぐ）。H(c) の出発は K* の頂の高さ。",
            "肩（c < −3）の管の半径と殻は設計で決め、当てはめでは動かさない（量感：薄い殻の大きな空洞にしない）。",
            "b 区域の稜は設計の列（90 + ledge_pos·110）で原画の帯の上端に、爪の縁は唇先（列 200）で帯の下端に合わせた（連続な当てはめ）。報告は round 3 の検出器でも出す。",
            "原画視点で他の行に隠れる部分にも勾配が届くよう、頂点ごとのはみ出し（塗られた空への食い込み）を罰に加えた。132・72 の近く（30 px）は大きな輪郭の線の向こう側だけを数える。",
        ],
        "conflicts_ja": [
            "F10 奥で頂の線が後ろへ流れる角 ≤ 20° は、原画視点で奥の部分が管の口（塗られた空）に出ないことと両立しない（K* 58°、第 2 回 51°、A4 48° も同じ理由）。奥の行の唇先が 72 の輪郭を描くので、奥は後ろへ流す。",
            "Q21-1 の 3 m の撓み（暫定 0.15 m）は波の頂の山と奥の閉じだけで超える。局所の膨らみは 4 階差で見る（上の決定）。",
        ],
        "design_keys_file": "kstarH1A_design.json",
        "fit_log": design.get("fit_log"),
    }
    json.dump(rec, open(os.path.join(d, "kstarH1A_difference_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({k: rec[k] for k in ("F13_proximity",)}, default=float))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
