# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）組み立て：美術の要求書（Docs/Design/Art_Requirements_ja.md）の測る規則を、出す前に自動で確かめる。
出力：Build/Polish/sample02/rules_check.json。美術が届いたかは利用者が決める（Q29・Q30）。ここは「測れる規則を通るか」だけ。

  G1  投影を使わない：主役波・爪のシェーダーにテクスチャも原画カメラの行列も無いこと（ファイルの中身）、描画の記録で焼き込みのパスが空、
      属性の生成の記録で projection_used = false。面の座標の伸び（三角形ごとの |∇w|、溝の間隔の逆数）と継ぎ目（辺をまたぐ w の差 ÷ 辺の長さ ≥ 3、溝の間隔が 1/3 に詰まる跳び）を
      前（P28R2rec の属性）と今（AS02B、留めた属性）で数え、今が前より悪くないこと。7 視点＋回り台の見た目は利用者が並べ図で見る。
  G2  原画視点の関門：78・130・131 の最大 ≤ 4 px、132（σ12）・72（σ12 の p95）≤ 4 px（sweep_gates.json）。前の群・CP1・26修正01 と並べる。評価器 23 の数も。
  S4  背は一つの山：back_measure.py の数（c ≥ −14）。H(c) のへこみ 0、背の等高線のへこみ・弦からの出っ張りのへこみが 0（背の部と同じ 0.10 m の許し）、
      各高さの出っ張りの最大が中ほどの区間（頂が 0.9 Hmax 以上の c −6〜+6）、後ろからの輪郭のへこみ ≤ 1 px。
  C2  利用者の模型の水準（as02_claws100.py の standard_check：輪郭のでこぼこ ≤ claw_mid + 2、背骨の曲率の跳び ≤ 模型、断面の比 など）を全部の爪で。
  C3  原画カメラから見た各爪の影と利用者のマスクの IoU ≥ 0.85（と、面から見た作り直しの IoU ≥ 0.85）。100 本のどれも、置いたか重複として記録があること。
  （C4 は記録：参照モデルから測った置き方との比べ）
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_asm_rules.py
"""
import glob
import hashlib
import json
import os
import re
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
S2 = REPO + "/Unity/Build/Polish/sample02"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/sample01")
from s01_param import load_gwb, grad_operator  # noqa: E402

NOW = S2 + "/assemble/render/AS02B_A"
PREV = S2 + "/claws/render/A_final"          # 前の群（爪の部の案 A、P28R2rec の上）
BEFORE = REPO + "/Unity/Build/Polish/sample01/assemble/A2"   # 美術の見本01 A
BEFORE_GATES = REPO + "/Unity/Build/Polish/sample01/assemble/B2"
SHADERS = {"hero": REPO + "/Unity/Assets/GreatWave/Sample01/TexA/Shaders/S01A_Groove_Hero.shader",
           "hero_include": REPO + "/Unity/Assets/GreatWave/Design27/Shaders/DS27Keypose.cginc",
           "claw": REPO + "/Unity/Assets/GreatWave/Polish29/Shaders/PL29_Claw_Shade.shader"}
GWB_OLD = REPO + "/Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb"
GWB_NEW = S2 + "/back/final/cand/kstarAS02B_a45.gwb"
ATTR_OLD = REPO + "/Unity/Build/Polish/sample01/texA/attr/s01a_hero_attr_v2_f32.bin"
ATTR_NEW = S2 + "/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin"
REPORT = S2 + "/assemble/claws/mesh/as02_claws_report.json"
MEASURE = S2 + "/back/final/measure.json"
GATES = S2 + "/assemble/render/measure/gates_AS02B_A/sweep_gates.json"
REFP = S2 + "/claws/ref/as02_ref_claw_placement_r0.7.json"
TOL_DIP = 0.10
MID_ZONE = (-6.0, 6.0)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def g1():
    code = {}
    bad = re.compile(r"sampler2D|sampler3D|Texture2D\b|tex2D|tex2Dlod|_SdfTex|Paint|PaintVP|_DS29|UNITY_MATRIX_VP_PAINT", re.I)
    for k, p in SHADERS.items():
        src = open(p, encoding="utf-8", errors="replace").read()
        body = re.sub(r"//[^\n]*", "", src)
        hits = sorted(set(m.group(0) for m in bad.finditer(body)))
        cam = body.count("_WorldSpaceCameraPos")
        code[k] = {"path": rel(p), "sha256": sha256(p), "forbidden_tokens": hits, "world_camera_pos_uses": cam}
    code["hero"]["inputs_texcoord"] = sorted(set(re.findall(r":\s*(TEXCOORD\d)", open(SHADERS["hero"], encoding="utf-8").read().split("struct v2f")[0])))
    rr = json.load(open(NOW + "/as01s_render_report.json", encoding="utf-8"))
    rep = {k: rr.get(k) for k in ("heroSdf", "heroUvWarp", "heroUv3File", "heroUv3Source", "heroShader", "clawShade", "protectedUnchanged", "heroPackage", "heroMeshGwb", "attr")}
    attr_json = []
    for p in (S2 + "/assemble/attr_pin/a/s01a_hero_attr_v2.json", S2 + "/assemble/attr_pin/as02_asm_attr_pin.json", S2 + "/assemble/attr/param/s01_param.json"):
        j = json.load(open(p, encoding="utf-8"))
        attr_json.append({"path": rel(p), "projection_used": j.get("projection_used")})
    code_ok = (all(not v["forbidden_tokens"] for v in code.values()) and code["hero"]["world_camera_pos_uses"] <= 1
               and code["hero"]["inputs_texcoord"] == ["TEXCOORD3", "TEXCOORD4", "TEXCOORD5"]
               and not rep["heroSdf"] and not rep["heroUvWarp"] and not rep["heroUv3File"] and rep["protectedUnchanged"] is True
               and all(a["projection_used"] is False for a in attr_json))
    # 面の座標の伸び・継ぎ目（主役波の本体の行：q > 0、三角形の面積 > 1e-6）
    surf = {}
    for key, gwb, attr in (("before_P28R2rec", GWB_OLD, ATTR_OLD), ("now_AS02B", GWB_NEW, ATTR_NEW)):
        nu, nv, _uv, _uv2, tri, pos = load_gwb(gwb)
        at = np.fromfile(attr, np.float32).reshape(-1, 12).astype(np.float64)
        prm = np.fromfile(S2 + ("/assemble/attr_repro/param/s01_param_f32.bin" if key.startswith("before") else "/assemble/attr_pin/s01_param_f32.bin"),
                          np.float32).reshape(-1, 8)
        q = prm[:, 7]
        G, A, _ = grad_operator(pos, tri)
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
    b, n = surf["before_P28R2rec"], surf["now_AS02B"]
    surf_ok = (n["stretch_tri_gt3x"] <= b["stretch_tri_gt3x"] and n["seam_edges_dw_over_len_ge3"] <= b["seam_edges_dw_over_len_ge3"]
               and n["stretch_area_frac_gt2x"] <= b["stretch_area_frac_gt2x"] + 1e-3)
    return {"rule_ja": "色・線は原画カメラの投影を使わない（コードの検査）。7 視点＋回り台で引き伸ばし・継ぎ目・平らな面がない",
            "code_check": code, "render_report": rep, "attr_records": attr_json, "code_pass": bool(code_ok),
            "surface_param": surf, "surface_not_worse": bool(surf_ok),
            "visual_ja": "7 視点＋回り台の画（s3a・s4a・s4b・turntable_before_now.mp4）は利用者が見る。背の上は見本 A の材質の白の帯で平らな白に見える（材質の設計どおり。模様は T2 で対象外）。",
            "claw_geometry_note_ja": "爪の形は利用者のマスクから作り、案 A は原画カメラの射線の上で奥行きだけ動かして置いた（形の置き方。色は投影しない。爪の色は帯の頂点の値だけ）。",
            "verdict": "pass" if (code_ok and surf_ok) else "fail"}


def eval23(root):
    out = {}
    for c in ("line", "line_noclaws", "noline", "noline_noclaws"):
        p = root + "/eval23/off_%s/metrics.json" % c
        if not os.path.exists(p):
            out[c] = None
            continue
        it = json.load(open(p, encoding="utf-8"))["items"]
        v = [x.get("verdict") for x in it.values()]
        out[c] = {"pass": v.count("pass"), "fail": v.count("fail"), "other": len(v) - v.count("pass") - v.count("fail")}
    return out


def g2():
    sg = json.load(open(GATES, encoding="utf-8"))["gates"]
    rows = {}
    ok = True
    for k, v in sg.items():
        p = bool(v["after_claws"] <= v["gate_px"] and v["after_noclaws"] <= v["gate_px"])
        ok &= p
        rows[k] = {"now_claws": v["after_claws"], "now_noclaws": v["after_noclaws"], "before_sample01_claws": v["before_claws"],
                   "before_sample01_noclaws": v["before_noclaws"], "CP1": v["CP1"], "26修正01": v["26修正01"], "gate_px": v["gate_px"], "pass": p}
    prev = json.load(open(PREV.replace("/A_final", "/measure/gates_A_final/sweep_gates.json"), encoding="utf-8"))["gates"]
    for k in rows:
        rows[k]["prev_group_claws100_A_claws"] = prev[k]["after_claws"]
    return {"rule_ja": "78・130・131（定義どおり）≤ 4 px、132・72 は大きな輪郭で ≤ 4 px", "gates": rows,
            "eval23": {"now_AS02B_A": eval23(NOW), "prev_group_claws100_A": eval23(PREV), "before_sample01_B2": eval23(BEFORE_GATES)},
            "note_ja": "130・131・132・72 は CP1・26修正01 よりまだ 1.3〜2.3 px 悪い（仕上げ28 の形のまま。今回の背と爪では変わらない）。",
            "verdict": "pass" if ok else "fail"}


def s4():
    m = json.load(open(MEASURE, encoding="utf-8"))
    s = m["summary"]
    out = {}
    for key in ("P28R2rec", "AS02B"):
        x = s[key]
        peaks = {lv: c for lv, c in x["bulge_peak_c_by_level"].items()}
        off = {lv: c for lv, c in peaks.items() if not (MID_ZONE[0] <= c <= MID_ZONE[1])}
        sil = x["silhouette_dip_px_hero"]
        chk = {"H_dip_c_ge_-14_m": {"value": x["H_dip_hero_m"], "pass": x["H_dip_hero_m"] <= 0.0},
               "back_contour_dip_max_m": {"value": x["back_dip_max_m"], "pass": x["back_dip_max_m"] <= TOL_DIP},
               "bulge_over_chord_dip_m": {"value": x["back_bulge_dip_max_m"], "pass": x["back_bulge_dip_max_m"] <= TOL_DIP},
               "bulge_peak_in_middle_zone": {"peak_c_by_level": peaks, "outside_levels": off, "zone_c": list(MID_ZONE), "pass": not off},
               "silhouette_dip_from_behind_px_c_ge_-14": {"value": sil, "pass": max(sil.values()) <= 1.0}}
        out[key] = {"checks": chk, "pass_all": all(v["pass"] for v in chk.values()),
                    "strict_zero_dip": x["back_dip_max_m"] == 0 and x["back_bulge_dip_max_m"] == 0}
    return {"rule_ja": "背の高さ H(c) と背のふくらみの横の分布が一つの山：最大は中ほどの区間、そこから両側へ単調に下がる（へこみの深さ 0）。後ろ 65°・真後ろ・回り台で目でも確かめる",
            "source": {"measure": rel(MEASURE), "sha256": sha256(MEASURE)}, "tolerance_m": TOL_DIP,
            "tolerance_note_ja": "へこみの 0 は、背の部と同じ 0.10 m（行の間隔 0.2 m の半分）までを 0 とみる。厳密な 0 ではない（strict_zero_dip）。",
            "hero_in_render_equals_measured": "Unity の包みの t* の層は AS02B の .gwb と 3.4 µm 以内（as02_asm_pkg.py の復号の確かめ）",
            "before": out["P28R2rec"], "now": out["AS02B"],
            "verdict": "pass" if out["AS02B"]["pass_all"] else "fail",
            "fail_reason_ja": None if out["AS02B"]["pass_all"] else
            "高さ 0.05〜0.4 H0 では、背のふくらみの最大がまだ奥の端（c +6.2〜+10.2）にある（管が深く、その背を前へ引けない。背の部の限界）。0.5〜0.9 H0 は中ほど（c −5.8〜−3.0）。"}


def c2_c3():
    r = json.load(open(REPORT, encoding="utf-8"))
    placed = [c for c in r["claws"] if c.get("placed") and "standard" in c]
    cat = {"outline_lumps": "輪郭のでこぼこ", "spine_curvature_jump": "背骨の曲率の跳び", "face_iou": "面から見た IoU"}
    c2_fail, c3_face = {}, []
    kinds = {}
    for c in placed:
        f = [x for x in c.get("standard_fails_ja", []) if not x.startswith(cat["face_iou"])]
        if f:
            c2_fail[c["user_id"]] = f
            for x in f:
                k = next((kk for kk, v in cat.items() if x.startswith(v)), x.split(" ")[0])
                kinds[k] = kinds.get(k, 0) + 1
        if c.get("iou_face", 1) < 0.85:
            c3_face.append(c["user_id"])
    ip = {c["user_id"]: c["iou_painting"] for c in placed}
    c3_fail = {k: v for k, v in ip.items() if v < 0.85}
    users = len(r["claws"])
    accounted = len(placed) + len(r["summary"]["not_placed"])
    std = json.load(open(S2 + "/claws/user_claw_standard.json", encoding="utf-8"))
    c2 = {"rule_ja": "どの爪も利用者の模型 claw_low・claw_mid の水準以上（断面の幅と厚みの比、先の細り、表面の滑らかさ＝曲率の跳びを模型と比べる）",
          "standard_source": {"path": rel(S2 + "/claws/user_claw_standard.json"), "sha256": sha256(S2 + "/claws/user_claw_standard.json")},
          "placed": len(placed), "pass": len(placed) - len(c2_fail), "fail": len(c2_fail), "fail_by_kind": kinds, "fail_claws": c2_fail,
          "section_width_over_thickness_p50": float(np.median([c["standard"]["width_over_thickness_mid"] for c in placed])),
          "taper_power_tip30_p50": float(np.median([c["standard"]["taper_power_tip30"] for c in placed])),
          "user_model_note_ja": "比べる値は user_claw_standard.json（claw_mid・claw_low を読み取りのみで測った値）。輪郭のでこぼこの上限は claw_mid の 8 ＋ かかとの 2。",
          "verdict": "pass" if not c2_fail else "fail"}
    c3 = {"rule_ja": "原画カメラから見た各爪の輪郭とマスクの重なり（IoU ≥ 0.85）。100 本を 1 本ずつ 3D に戻して置く",
          "users": users, "placed": len(placed), "duplicates_dropped": len(r["summary"]["not_placed"]), "all_accounted": accounted == users,
          "iou_painting_p10_p50_min": [r["summary"]["iou_painting"]["p10"], r["summary"]["iou_painting"]["p50"], r["summary"]["iou_painting"]["min"]],
          "iou_painting_below_085": c3_fail, "iou_face_below_085": c3_face,
          "pass": len(placed) - len(c3_fail), "verdict": "pass" if (not c3_fail and not c3_face and accounted == users) else "fail"}
    refp = json.load(open(REFP, encoding="utf-8"))
    c4 = {"rule_ja": "置き方は参照モデルの爪の置き方に近づける（記録のみ。ここでは判定しない）",
          "root_dir_vs_normal_deg_p50": {"now": float(np.median([c["root_dir_vs_normal_deg"] for c in placed])),
                                         "reference": refp["angle_root_dir_vs_surface_normal_deg"]["p50"]},
          "nearest_root_over_length_p50": {"now": float(np.median([c["nearest_root_over_length"] for c in placed if c.get("nearest_root_over_length") is not None]))},
          "verdict": "record_only"}
    return c2, c3, c4


def main():
    t0 = time.time()
    res = {"schema": "GreatWave.AS02.rules_check/1",
           "created_local": time.strftime("%Y-%m-%dT%H:%M"),
           "noteJa": "美術の見本02 を出す前の、美術の要求書の測る規則の自動の確かめ。美術が届いたかは利用者が決める（Q29・Q30）。目で見た審査は閉じる条件にしない。",
           "sample": {"hero": "K*′ AS02B（背を一つの山にした候補）を t* の静止で", "claws": "利用者の 100 本（重複 17 本を除く 83 本）、案 A（原画の射線の上）",
                      "material": "見本 A（中立の地。模様は対象外、T2）", "render": rel(NOW)},
           "inputs_sha256": {rel(p): sha256(p) for p in (GWB_NEW, ATTR_NEW, REPORT, S2 + "/assemble/claws/mesh/ds33_claw_layout.json",
                                                         S2 + "/assemble/hero_pkg_AS02B/ds27_keypose.json", NOW + "/as01s_render_report.json", GATES, MEASURE)},
           "rules": {}}
    res["rules"]["G1"] = g1()
    res["rules"]["G2"] = g2()
    res["rules"]["S4"] = s4()
    c2, c3, c4 = c2_c3()
    res["rules"]["C2"] = c2
    res["rules"]["C3"] = c3
    res["rules"]["C4_record"] = c4
    v = {k: res["rules"][k]["verdict"] for k in ("G1", "G2", "S4", "C2", "C3")}
    res["summary"] = {"verdicts": v, "all_pass": all(x == "pass" for x in v.values()),
                      "deliverable_by_rule_ja": "要求書の「通らない見本は出さない」により、S4・C2・C3 が通らないうちは見本として出せない。出すかどうかは進行役が決める。"
                      if not all(x == "pass" for x in v.values()) else "測る規則はすべて通った。美術の判定は利用者。"}
    res["elapsed_s"] = round(time.time() - t0, 1)
    p = S2 + "/rules_check.json"
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(res["summary"], ensure_ascii=False))
    print(json.dumps({"G1": {k: res["rules"]["G1"][k] for k in ("code_pass", "surface_not_worse", "surface_param")}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
