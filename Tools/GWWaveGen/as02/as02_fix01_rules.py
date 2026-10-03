# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）修正の回 1：美術の要求書の測る規則（G1・G2・S4・C2・C3、C4 は記録）を、直した見本でもう一度確かめる。
測り方は組み立ての as02_asm_rules.py と同じ関数・同じ閾値（この道具はそれを読み込み、入力の場所だけを修正の回 1 のものに替える）。
  今   ＝ 背 K*′ AS02C（Build/Polish/sample02/fix01/back/final/cand）＋ 直した爪（fix01/assemble/claws/mesh、案 A、--fix01）、
         描画 fix01/assemble/render/AS02C_A
  前の群 ＝ 見本02 の組み立て（背 AS02B ＋ 爪の部の案 A、Build/Polish/sample02/assemble/render/AS02B_A）
S4 は前（AS02B）と今（AS02C）に加えて、もと（P28R2rec）の値も並べる。
C3 の原画視点の IoU は、修正の回 1 の爪の道具が細かく測った値（IOU_SS 32）。今までの細かさ（S 8）の値も並べる。
出力：Build/Polish/sample02/rules_check.json（前の版は rules_check_AS02B_A.json として残す）。美術が届いたかは利用者が決める（Q29・Q30）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_rules.py
"""
import json
import os
import shutil
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_asm_rules as R  # noqa: E402

S2 = R.S2
FX = S2 + "/fix01"
AS = FX + "/assemble"
NOW = AS + "/render/AS02C_A"
PREV = S2 + "/assemble/render/AS02B_A"
PREV_GATES = S2 + "/assemble/render/measure/gates_AS02B_A/sweep_gates.json"
GWB_NEW = FX + "/back/final/cand/kstarAS02C_a45.gwb"
ATTR_NEW = AS + "/attr_pin/a/s01a_hero_attr_v2_f32.bin"
PARAM_NEW = AS + "/attr_pin/s01_param_f32.bin"
PARAM_OLD = S2 + "/assemble/attr_repro/param/s01_param_f32.bin"      # P28R2rec で回し直した見本01 の面の座標（バイトまで同じ）
REPORT = AS + "/claws/mesh/as02_claws_report.json"
LAYOUT = AS + "/claws/mesh/ds33_claw_layout.json"
MEASURE = FX + "/back/final/measure.json"
GATES = AS + "/render/measure/gates_AS02C_A/sweep_gates.json"
KEYPOSE = AS + "/hero_pkg_AS02C/ds27_keypose.json"
OUT = S2 + "/rules_check.json"
CONFLICT = FX + "/claws/conflict_search.json"
OLD_COPY = S2 + "/rules_check_AS02B_A.json"


def g1():
    import re
    code = {}
    bad = re.compile(r"sampler2D|sampler3D|Texture2D\b|tex2D|tex2Dlod|_SdfTex|Paint|PaintVP|_DS29|UNITY_MATRIX_VP_PAINT", re.I)
    for k, p in R.SHADERS.items():
        src = open(p, encoding="utf-8", errors="replace").read()
        body = re.sub(r"//[^\n]*", "", src)
        hits = sorted(set(m.group(0) for m in bad.finditer(body)))
        cam = body.count("_WorldSpaceCameraPos")
        code[k] = {"path": R.rel(p), "sha256": R.sha256(p), "forbidden_tokens": hits, "world_camera_pos_uses": cam}
    code["hero"]["inputs_texcoord"] = sorted(set(re.findall(r":\s*(TEXCOORD\d)", open(R.SHADERS["hero"], encoding="utf-8").read().split("struct v2f")[0])))
    rr = json.load(open(NOW + "/as01s_render_report.json", encoding="utf-8"))
    rep = {k: rr.get(k) for k in ("heroSdf", "heroUvWarp", "heroUv3File", "heroUv3Source", "heroShader", "clawShade", "protectedUnchanged", "heroPackage", "heroMeshGwb", "attr")}
    attr_json = []
    for p in (AS + "/attr_pin/a/s01a_hero_attr_v2.json", AS + "/attr_pin/as02_asm_attr_pin.json", AS + "/attr/param/s01_param.json"):
        j = json.load(open(p, encoding="utf-8"))
        attr_json.append({"path": R.rel(p), "projection_used": j.get("projection_used")})
    code_ok = (all(not v["forbidden_tokens"] for v in code.values()) and code["hero"]["world_camera_pos_uses"] <= 1
               and code["hero"]["inputs_texcoord"] == ["TEXCOORD3", "TEXCOORD4", "TEXCOORD5"]
               and not rep["heroSdf"] and not rep["heroUvWarp"] and not rep["heroUv3File"] and rep["protectedUnchanged"] is True
               and all(a["projection_used"] is False for a in attr_json))
    surf = {}
    for key, gwb, attr, prmf in (("before_P28R2rec", R.GWB_OLD, R.ATTR_OLD, PARAM_OLD), ("prev_AS02B", R.GWB_NEW, R.ATTR_NEW, S2 + "/assemble/attr_pin/s01_param_f32.bin"),
                                 ("now_AS02C", GWB_NEW, ATTR_NEW, PARAM_NEW)):
        nu, nv, _uv, _uv2, tri, pos = R.load_gwb(gwb)
        at = np.fromfile(attr, np.float32).reshape(-1, 12).astype(np.float64)
        prm = np.fromfile(prmf, np.float32).reshape(-1, 8)
        q = prm[:, 7]
        G, A, _ = R.grad_operator(pos, tri)
        gw = np.linalg.norm((G @ at[:, 3]).reshape(-1, 3), axis=1)
        sel = (A > 1e-6) & (q[tri].min(1) > 0)
        e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
        e = e[np.concatenate([sel, sel, sel])]
        jump = np.abs(at[e[:, 0], 3] - at[e[:, 1], 3]) / np.maximum(np.linalg.norm(pos[e[:, 0]] - pos[e[:, 1]], axis=1), 1e-9)
        g = gw[sel]
        surf[key] = {"triangles": int(sel.sum()), "grad_w_p1_p50_p99": [round(float(x), 4) for x in np.percentile(g, [1, 50, 99])],
                     "stretch_tri_gt3x": int(((g < 1 / 3.0) | (g > 3.0)).sum()),
                     "stretch_area_frac_gt2x": round(float(A[sel][(g < 0.5) | (g > 2.0)].sum() / A[sel].sum()), 5),
                     "seam_edges_dw_over_len_ge3": int((jump >= 3.0).sum()), "edge_dw_over_len_max": round(float(jump.max()), 4)}
    b, n = surf["before_P28R2rec"], surf["now_AS02C"]
    surf_ok = (n["stretch_tri_gt3x"] <= b["stretch_tri_gt3x"] and n["seam_edges_dw_over_len_ge3"] <= b["seam_edges_dw_over_len_ge3"]
               and n["stretch_area_frac_gt2x"] <= b["stretch_area_frac_gt2x"] + 1e-3)
    return {"rule_ja": "色・線は原画カメラの投影を使わない（コードの検査）。7 視点＋回り台で引き伸ばし・継ぎ目・平らな面がない",
            "code_check": code, "render_report": rep, "attr_records": attr_json, "code_pass": bool(code_ok),
            "surface_param": surf, "surface_not_worse": bool(surf_ok),
            "visual_ja": "7 視点＋回り台の画（s3a・s4a・s4b・turntable_before_now.mp4）は利用者が見る。背の上は見本 A の材質の白の帯で平らな白に見える（材質の設計どおり。模様は T2 で対象外）。",
            "claw_geometry_note_ja": "爪の形は利用者のマスクから作り、案 A は原画カメラの射線の上で奥行きだけ動かして置いた（形の置き方。色は投影しない。爪の色は帯の頂点の値だけ）。",
            "verdict": "pass" if (code_ok and surf_ok) else "fail"}


def g2():
    sg = json.load(open(GATES, encoding="utf-8"))["gates"]
    prev = json.load(open(PREV_GATES, encoding="utf-8"))["gates"]
    rows = {}
    ok = True
    for k, v in sg.items():
        p = bool(v["after_claws"] <= v["gate_px"] and v["after_noclaws"] <= v["gate_px"])
        ok &= p
        rows[k] = {"now_claws": v["after_claws"], "now_noclaws": v["after_noclaws"], "before_sample01_claws": v["before_claws"],
                   "before_sample01_noclaws": v["before_noclaws"], "CP1": v["CP1"], "26修正01": v["26修正01"], "gate_px": v["gate_px"], "pass": p,
                   "prev_group_sample02_AS02B_A_claws": prev[k]["after_claws"], "prev_group_sample02_AS02B_A_noclaws": prev[k]["after_noclaws"]}
    return {"rule_ja": "78・130・131（定義どおり）≤ 4 px、132・72 は大きな輪郭で ≤ 4 px", "gates": rows,
            "eval23": {"now_AS02C_A": R.eval23(NOW), "prev_group_sample02_AS02B_A": R.eval23(PREV), "before_sample01_B2": R.eval23(R.BEFORE_GATES)},
            "note_ja": "130・131・132・72 は CP1・26修正01 よりまだ 1.3〜2.3 px 悪い（仕上げ28 の形のまま。背と爪の修正では変わらない）。",
            "verdict": "pass" if ok else "fail"}


def s4():
    m = json.load(open(MEASURE, encoding="utf-8"))
    s = m["summary"]
    out = {}
    for key in ("P28R2rec", "AS02B", "AS02C"):
        x = s[key]
        peaks = {lv: c for lv, c in x["bulge_peak_c_by_level"].items()}
        off = {lv: c for lv, c in peaks.items() if not (R.MID_ZONE[0] <= c <= R.MID_ZONE[1])}
        sil = x["silhouette_dip_px_hero"]
        chk = {"H_dip_c_ge_-14_m": {"value": x["H_dip_hero_m"], "pass": x["H_dip_hero_m"] <= 0.0},
               "back_contour_dip_max_m": {"value": x["back_dip_max_m"], "pass": x["back_dip_max_m"] <= R.TOL_DIP},
               "bulge_over_chord_dip_m": {"value": x["back_bulge_dip_max_m"], "pass": x["back_bulge_dip_max_m"] <= R.TOL_DIP},
               "bulge_peak_in_middle_zone": {"peak_c_by_level": peaks, "outside_levels": off, "zone_c": list(R.MID_ZONE), "pass": not off},
               "silhouette_dip_from_behind_px_c_ge_-14": {"value": sil, "pass": max(sil.values()) <= 1.0}}
        out[key] = {"checks": chk, "pass_all": all(v["pass"] for v in chk.values()),
                    "strict_zero_dip": x["back_dip_max_m"] == 0 and x["back_bulge_dip_max_m"] == 0,
                    "far_volume_c_gt_0_m3": x["F04_like"]["far_volume_c_gt_0_m3"]}
    return {"rule_ja": "背の高さ H(c) と背のふくらみの横の分布が一つの山：最大は中ほどの区間、そこから両側へ単調に下がる（へこみの深さ 0）。後ろ 65°・真後ろ・回り台で目でも確かめる",
            "source": {"measure": R.rel(MEASURE), "sha256": R.sha256(MEASURE)}, "tolerance_m": R.TOL_DIP,
            "tolerance_note_ja": "へこみの 0 は、背の部と同じ 0.10 m（行の間隔 0.2 m の半分）までを 0 とみる。厳密な 0 ではない（strict_zero_dip）。",
            "hero_in_render_equals_measured": "Unity の包みの t* の層は AS02C の .gwb と 3.4 µm 以内（as02_asm_pkg.py の復号の確かめ）",
            "original_P28R2rec": out["P28R2rec"], "before": out["AS02B"], "now": out["AS02C"],
            "verdict": "pass" if out["AS02C"]["pass_all"] else "fail",
            "fix_ja": "背の低い所（0.05〜0.4 H0）で、中ほど（c +1 の周り、p 2 の山形）を最大 1.3 m 後ろへ出し、高さ 0 から 0.8 H0 まで余弦で 0 へ戻した。"
                      "奥の端の裾の前への引き（管との壁が厚い低い所だけ）を c +6 から c +4.5 へ早めた（back_build.py の round_c・round_fade_mode、設計は "
                      "fix01/back/final/cand/back_design.json）。原画視点から見える頂点は動かしていない（back_check で画素の差 0）。",
            "fail_reason_ja": None if out["AS02C"]["pass_all"] else "（落ちた検査は checks を見る）"}


def c2_c3():
    R.REPORT = REPORT
    c2, c3, c4 = R.c2_c3()
    r = json.load(open(REPORT, encoding="utf-8"))
    placed = [c for c in r["claws"] if c.get("placed") and "standard" in c]
    c3["iou_painting_s8_p10_p50_min"] = [round(float(np.percentile([c["iou_painting_s8"] for c in placed], q)), 4) for q in (10, 50)] + \
        [round(float(min(c["iou_painting_s8"] for c in placed)), 4)]
    c3["iou_painting_s8_below_085"] = {c["user_id"]: c["iou_painting_s8"] for c in placed if c["iou_painting_s8"] < 0.85}
    c3["measure_note_ja"] = ("原画視点の影は表示の画素の 32 倍の細かさで塗って測った（今までは 8 倍。OpenCV の三角形の塗りは縁の画素も塗るので、細く小さい爪ほど IoU が"
                             "低く出る偏りがある）。面から見た IoU は 2400 px（今までは 600 px）。今までの細かさの値も iou_painting_s8 に残した。")
    fails = sorted(set(c3["iou_painting_below_085"]) | set(c3["iou_face_below_085"]))
    cs = json.load(open(CONFLICT, encoding="utf-8")) if os.path.isfile(CONFLICT) else {"claws": {}}
    why = {}
    for u in fails:
        x = cs["claws"].get(u)
        if x and x["best_c2_pass"]:
            why[u] = ("利用者のマスクの縁が何度も S 字に曲がる手描きで、輪郭のでこぼこを claw_mid の水準（≤ %d）まで滑らかにすると重なりが下がる。"
                      "%d 通りの形を試した最大：C2 を通る形で IoU %.3f、でこぼこ 12 を許すと %.3f（as02_fix01_conflict_search.py）。C2（利用者の模型の水準）を先にした"
                      % (cs["limits"]["outline_lumps"], x["tried"], x["best_c2_pass"]["iou2d"], x["best_lumps_le_12"]["iou2d"] if x["best_lumps_le_12"] else float("nan")))
        else:
            why[u] = "（両立の探しをしていない）"
    c3["fail_reason_ja"] = why or None
    c3["conflict_search"] = {"path": R.rel(CONFLICT), "sha256": R.sha256(CONFLICT)} if os.path.isfile(CONFLICT) else None
    c3["fix_ja"] = ("厚みの向きを射線へ寄せる（N_ORTHO 0.5 → 0.3・0.15・0）のを、原画視点と面から見た IoU の小さい方が 0.86 に届かない爪だけにした。"
                    "2 次元の形の IoU を切り抜きの枠の外も数えて選び、形を切り抜きの枠で止め、輪の数を 200 まで増やした。")
    c2["fix_ja"] = ("肋の組み方の割合を鎖の弧長でならし（PAIR_SIG 0.6、背骨の曲率の跳びの原因）、爪ごとに輪郭のならしの強さ（ガウス × 平滑化スプライン × 長い波を戻すならし）"
                    "と幅の倍率の 280 通りから、2 次元の水準の検査を通る中で利用者のマスクとの重なりが最大の形を選んだ。形は切り抜きの枠で止め、中ほどの断面の 幅 : 厚み を 1.65 以下にした。")
    return c2, c3, c4


def main():
    t0 = time.time()
    if os.path.isfile(OUT) and not os.path.isfile(OLD_COPY):
        shutil.copy2(OUT, OLD_COPY)
    res = {"schema": "GreatWave.AS02.rules_check/1",
           "created_local": time.strftime("%Y-%m-%dT%H:%M"),
           "round": "修正の回 1（落ちた測る規則 S4・C2・C3 だけを直し、描き直して測り直した）",
           "previous_check": {"path": R.rel(OLD_COPY), "sha256": R.sha256(OLD_COPY) if os.path.isfile(OLD_COPY) else None,
                              "verdicts": json.load(open(OLD_COPY, encoding="utf-8"))["summary"]["verdicts"] if os.path.isfile(OLD_COPY) else None},
           "noteJa": "美術の見本02 を出す前の、美術の要求書の測る規則の自動の確かめ。美術が届いたかは利用者が決める（Q29・Q30）。目で見た審査は閉じる条件にしない。",
           "sample": {"hero": "K*′ AS02C（背の低い所のふくらみの山も中ほどへ寄せた候補）を t* の静止で",
                      "claws": "利用者の 100 本（重複 17 本を除く 83 本）、案 A（原画の射線の上）、修正の回 1 の形（--fix01）",
                      "material": "見本 A（中立の地。模様は対象外、T2）", "render": R.rel(NOW)},
           "inputs_sha256": {R.rel(p): R.sha256(p) for p in (GWB_NEW, ATTR_NEW, REPORT, LAYOUT, KEYPOSE, NOW + "/as01s_render_report.json", GATES, MEASURE)},
           "rules": {}}
    res["rules"]["G1"] = g1()
    res["rules"]["G2"] = g2()
    res["rules"]["S4"] = s4()
    c2, c3, c4 = c2_c3()
    res["rules"]["C2"] = c2
    res["rules"]["C3"] = c3
    res["rules"]["C4_record"] = c4
    v = {k: res["rules"][k]["verdict"] for k in ("G1", "G2", "S4", "C2", "C3")}
    bad = [k for k, x in v.items() if x != "pass"]
    res["summary"] = {"verdicts": v, "all_pass": not bad,
                      "deliverable_by_rule_ja": ("要求書の「通らない見本は出さない」により、%s が通らないうちは見本として出せない。出すかどうかは進行役が決める。" % "・".join(bad))
                      if bad else "測る規則はすべて通った。美術の判定は利用者。"}
    res["elapsed_s"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(res["summary"], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
