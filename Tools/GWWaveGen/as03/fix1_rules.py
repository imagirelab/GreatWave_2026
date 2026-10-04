# -*- coding: utf-8 -*-
"""美術の見本03 修正の回 1：測る規則の確かめ（asm_rules.py をそのまま使い、読む描画を Build/Polish/sample03/fix01/render へ替え、
修正の回 1 の部品の検査を足す）。前の rules_check.json は rules_check_before_fix.json に残す（このスクリプトは上書きしない。先に写すこと）。

足した検査（asm_rules.py の判定に加える）：
  G1  修正の回 1 の冠の部品（fix1_foam・fix1_drips、OUT・IN）のチャンネルが位置・法線・(ao, keyVis, whiteSD, 種類)・(f, 番号, 種類) だけ。
      材質の値の表（fix1_*_params.txt）は値だけで、シェーダーのコードは変えていない（SHA-256 が B2 の確かめた版と同じ）。
  T4  垂れる縁の滴（批評の提案：冠の数を頂の線と唇の縁の線に分けて測る）：唇の縁の滴の間隔の中央値が 0.6〜1.0 m（彫刻の正面の写真の読み
      0.8 m = 0.037 H、±25%）、長さの中央値が 0.6〜1.45 m（0.03〜0.07 H）、最も太い所の幅の中央値が 0.30〜0.48 m（0.015〜0.023 H）。
      数は記録（唇の縁の線に垂れる場所が無い行がある）。
  記録 批評の測り（critic_measure.py：見える白のうち冠の割合、指の周りの輪の白・藍、白の明るさ、暗い塊、回り台の出っ張り）を、
      前（組み立て）と後（修正の回 1）で並べる（判定には使わない。進行役が規則にするか決める）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as03/fix1_rules.py
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asm_rules as A  # noqa: E402
import critic_measure as CM  # noqa: E402

S3 = A.S3
FIX = S3 + "/fix01"
FIXC = FIX + "/crown"
A.RENDER = FIX + "/render"
A.OUT = S3 + "/rules_check.json"
PARAMS = [A.REPO + "/Tools/GWWaveGen/as03/fix1_sculpt_params.txt", A.REPO + "/Tools/GWWaveGen/as03/fix1_flat_params.txt"]
DRIP_RANGES = {"spacing_p50_m": [0.6, 1.0], "length_p50_m": [0.6, 1.45], "width_max_p50_m": [0.30, 0.48]}

_g1 = A.g1
_t4 = A.t4


def g1_fix(t1res):
    r = _g1(t1res)
    parts, ok = {}, True
    for m in ("OUT", "IN"):
        for nm in ("fix1_foam", "fix1_drips"):
            p = FIXC + "/%s/%s.json" % (m, nm)
            j = A.jl(p)
            names = [c[0] for c in j["channels"]]
            okp = names == ["position", "normal", "uv5", "uv3"]
            parts["%s/%s" % (m, nm)] = {"channels": j["channels"], "only_geometry_and_glaze_attrs": okp, "bin_sha256": j["sha256"],
                                        "vertices": j["vertices"], "triangles": j["triangles"]}
            ok &= okp
    r["crown_meshes_fix1_parts"] = parts
    r["fix1_material_params"] = {A.rel(p): {"sha256": A.sha(p), "lines": [l for l in open(p, encoding="utf-8").read().splitlines() if l and not l.startswith("#")]}
                                 for p in PARAMS}
    r["fix1_note_ja"] = ("修正の回 1 はシェーダーのコードを変えていない（上の shaders の SHA-256 が B2 の確かめた版と同じ）。材質の値の表だけを替えた"
                         "（環境の明るさ・回り込み・溝の青・藍の艶・FLAT の冠の淡い水色）。泡の皮・滴は面の座標 (u, w) と白の印 whiteSD で置いた形で、"
                         "原画のカメラは IN（V3）の置き場所の制約にだけ使った（色は写さない）。")
    if not ok:
        r["code_pass"] = False
        r["verdict"] = "fail"
    return r


def drip_checks():
    out = {}
    for m in ("OUT", "IN"):
        rp = A.jl(FIXC + "/%s/fix1_parts_report.json" % m)
        d = rp["drips"]["measure"]
        f = rp["foam"]["measure"]
        vals = {"spacing_p50_m": (d["spacing_along_w_m"] or {}).get("p50"), "length_p50_m": d["length_m"]["p50"], "width_max_p50_m": d["width_max_m"]["p50"]}
        checks = {k: {"value": vals[k], "range": DRIP_RANGES[k], "pass": vals[k] is not None and DRIP_RANGES[k][0] <= vals[k] <= DRIP_RANGES[k][1]} for k in DRIP_RANGES}
        out[m] = {"checks": checks, "pass_all": all(x["pass"] for x in checks.values()),
                  "record": {"drips": d["drips"], "dropped": d["dropped"], "lip_line_length_m": d["lip_line_length_m"], "drips_per_m_of_lip_line": d["drips_per_m"],
                             "spacing_along_w_m": d["spacing_along_w_m"], "length_m": d["length_m"], "width_max_m": d["width_max_m"],
                             "foam": {k: f[k] for k in ("lumps", "chains", "chain_spacing_w_m", "lump_height_m", "lump_width_m", "skin_area_above_surface_m2", "in_constraint")}},
                  "source": {"report": A.rel(FIXC + "/%s/fix1_parts_report.json" % m), "sha256": A.sha(FIXC + "/%s/fix1_parts_report.json" % m)}}
    return out


def critic_record():
    CM.RENDER = A.RENDER
    CM.OUT = FIX + "/critic_metrics_after.json"
    CM.main()
    after = A.jl(CM.OUT)
    before = A.jl(S3 + "/critic/critic_metrics.json")
    rows = {}
    for V in ("V1", "V2", "V3"):
        rv = {}
        for grp in ("crest", "views"):
            for k in after["variants"][V][grp]:
                a = after["variants"][V][grp][k]
                b = before["variants"][V][grp].get(k, {})
                rv["%s/%s" % (grp, k)] = {"crown_share_of_white": [b.get("crown_share_of_white"), a["crown_share_of_white"]],
                                          "ring_indigo": [b.get("ring_indigo"), a["ring_indigo"]],
                                          "white_lum_p25_p50_p75": [(b.get("white_lum_p5_25_50_75_95") or [None] * 5)[1:4], (a["white_lum_p5_25_50_75_95"] or [None] * 5)[1:4]],
                                          "dark_crown_blobs": [len(b.get("dark_crown_blobs_in_white", [])), len(a["dark_crown_blobs_in_white"])]}
        rv["turntable_protrusion_p50"] = {k: [before["variants"][V]["turntable_protrusion"].get(k, {}).get("peak_over_h_p50"), x["peak_over_h_p50"]]
                                          for k, x in after["variants"][V]["turntable_protrusion"].items()}
        rows[V] = rv
    return {"note_ja": "批評の測り（critic_measure.py）の [前（組み立て）, 後（修正の回 1）]。判定には使わない（記録）。冠の割合は泡の皮も冠に数える。",
            "after_file": {"path": A.rel(CM.OUT), "sha256": A.sha(CM.OUT)}, "by_variant": rows}


def t4_fix(spec, relief):
    r = _t4(spec, relief)
    dc = drip_checks()
    r["drip_fringe_fix1"] = dc
    r["drip_fringe_rule_ja"] = ("修正の回 1 で足した下位の検査：唇の縁から垂れる立体の滴（彫刻の正面の写真の読み：間隔 約 0.8 m、長さ 0.6〜1.45 m、幅 0.30〜0.48 m、"
                                "批評の数）。間隔は唇の線に沿う w の差（2 m より大きい切れ目は除く）。")
    old = dict(r["verdict_by_variant"])
    for v, x in A.VARIANTS.items():
        if not dc[x["crown"]]["pass_all"]:
            r["verdict_by_variant"][v] = "fail"
    r["verdict_by_variant_without_drip_check"] = old
    r["verdict"] = "pass" if all(x == "pass" for x in r["verdict_by_variant"].values()) else "fail"
    r["critic_metrics_before_after_record"] = critic_record()
    return r


A.g1 = g1_fix
A.t4 = t4_fix

if __name__ == "__main__":
    A.main()
    # 出力に修正の回 1 の印を足す
    res = A.jl(A.OUT)
    res["fix01"] = {"noteJa": ("美術の見本03 修正の回 1（Q31、批評の必ず直す所と T4 の失敗を直す 1 回）。描画は Build/Polish/sample03/fix01/render。"
                               "冠 = B1 の冠（OUT・IN、変えていない）＋ 修正の回 1 の泡の皮と唇の縁から垂れる滴（fix1_crown.py）。材質の値 = fix1_*_params.txt。"
                               "前の結果は rules_check_before_fix.json。"),
                    "before": A.rel(S3 + "/rules_check_before_fix.json"),
                    "crown_parts": {m: [A.rel(S3 + "/crown/%s/as03_crown.json" % m), A.rel(FIXC + "/%s/fix1_foam.json" % m), A.rel(FIXC + "/%s/fix1_drips.json" % m)]
                                    for m in ("OUT", "IN")},
                    "inputs_sha256_fix1": {A.rel(p): A.sha(p) for p in [FIXC + "/%s/%s.bin" % (m, n) for m in ("OUT", "IN") for n in ("fix1_foam", "fix1_drips")]
                                           + PARAMS + [A.REPO + "/Tools/GWWaveGen/as03/fix1_crown.py", A.REPO + "/Tools/GWWaveGen/as03/fix1_render.sh"]}}
    res["sample"]["render"] = {v: A.rel(A.RENDER + "/" + v) for v in A.VARIANTS}
    with open(A.OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    print("FIX1_RULES_DONE", json.dumps(res["summary"]["verdicts"], ensure_ascii=False))
