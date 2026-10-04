# -*- coding: utf-8 -*-
"""美術の見本05 やり方 B：targets.json の目標（L・P・K）ごとに、見本05 B の値と合否を一つの表にまとめ（summary_AS05B.json）、表の図（sB_8_targets.png）と
run.json（道具・入力・出力の SHA-256）を書く。py -3.10 -B Tools/GWWaveGen/as05/shapeB_record.py [描画の名前（既定 B2）]
入力：Unity/Build/Polish/sample05/shapeB/measure/targets_AS05B_<描画>.json（s5_targets measure）、measure/rules_check_AS05B.json（shapeB_rules）。
"""
import glob
import json
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeB_common as B  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "B2"
SB = B.OUT
TG = json.load(open(B.P + "/sample05/study/targets.json", encoding="utf-8"))
FONT = "C:/Windows/Fonts/meiryo.ttc"


def get(d, path):
    cur = d
    for k in path.split("."):
        if cur is None:
            return None
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def judge(op, thr, v):
    if v is None:
        return None
    if op == ">=":
        return v >= thr
    if op == "<=":
        return v <= thr
    if op == "between":
        return thr[0] <= v <= thr[1]
    return None


def main():
    M = json.load(open(SB + "/measure/targets_AS05B_%s.json" % TAG, encoding="utf-8"))
    Rr = json.load(open(SB + "/measure/rules_check_AS05B.json", encoding="utf-8"))
    rows = []
    g = M["geometry"]
    for t in TG["targets"]:
        tid = t["id"]; op = t["pass_if"]["op"]; thr = t["pass_if"]["value"]
        if tid == "L5-lip":
            v = {k: get(g, "layers.%s.lip_ahead_of_crest_m" % k) for k in ("2", "3")}
            ok = all(x is not None and x <= thr for x in v.values())
        elif tid == "L6-sep":
            v = {k: get(M, "separation_summary.%s.separated_share" % k) for k in ("1-2", "2-3")}
            ok = all(x is not None and x >= thr for x in v.values())
        elif tid == "L6-label":
            v = {k: get(M, "painting_label_consistency.%s.share_label_k" % k) for k in ("r1", "r2", "r3")}
            ok = all(v[k] is not None and v[k] >= thr[k] for k in v)
        elif tid == "L6-vis3":
            v = get(M, "separation_summary.layer3_views_with_2000px"); ok = judge(op, thr, v)
        elif op == "ranges":
            base = t["metric"].replace("appearance.", "")
            if base.endswith("cell_agreement_indigo"):
                v = get(M["appearance"], base)
                ok = v is not None and all(thr[k][0] <= v[k] <= thr[k][1] for k in thr)
            else:
                v = get(M["appearance"], base)
                vv = dict(v or {})
                if v:
                    vv["white+mizuiro"] = round(v["white"] + v["mizuiro"], 3)
                ok = v is not None and all(thr[k][0] <= vv[k] <= thr[k][1] for k in thr)
                v = vv
        else:
            v = get(M, t["metric"]); ok = judge(op, thr, v)
        rows.append({"id": tid, "kind": t["kind"], "rule_ja": t["rule_ja"], "value": v, "pass_if": t["pass_if"], "baseline_sample04": t.get("baseline_sample04"),
                     "pass": ok})
    ap = M.get("appearance") or {}
    K = []
    K.append({"id": "K-G2", "value": {k: v["claws"] for k, v in Rr["G2"]["gates"].items()}, "pass": Rr["G2"]["verdict"] == "pass"})
    K.append({"id": "K-S8", "value": {"dev_p95_m": get(Rr, "S8.AS04.dev_from_inner_face_m.p95"), "first_hit_inner_share": get(Rr, "S8.AS04.first_hit_inner_face_share")},
              "pass": Rr["S8"]["verdict"] == "pass"})
    K.append({"id": "K-S9", "value": {"region4_wave4_share": get(Rr, "S9.per_segment.78.region4_x_lt_360.owner_share.wave4"),
                                      "leftmost_white_c_m": get(Rr, "S9.white_part.AS04.leftmost_white_c_m")}, "pass": Rr["S9"]["verdict"] == "pass"})
    K.append({"id": "K-S4", "value": {k: v["value"] for k, v in Rr["S4"]["checks"].items()}, "pass": Rr["S4"]["verdict"] == "pass"})
    K.append({"id": "K-S10", "value": Rr["S10_vs_sample04"]["diff_m"], "pass": Rr["S10_vs_sample04"]["verdict"] == "pass"})
    K.append({"id": "K-T5", "value": ap.get("T5_small_white_blobs_on_hero_indigo"), "pass": ap.get("T5_small_white_blobs_on_hero_indigo") == 0})
    K.append({"id": "K-T6", "value": ap.get("T6_inner_edge_band_pale_share"), "pass": (ap.get("T6_inner_edge_band_pale_share") is not None and ap.get("T6_inner_edge_band_pale_share") <= 0.02)})
    K.append({"id": "K-top", "value": Rr["K_top"]["max_disp_m"], "pass": Rr["K_top"]["verdict"] == "pass"})
    K.append({"id": "K-boat", "value": {"protect_spill_new_cells": Rr["K_boat"]["protect_spill_new_cells_vs_AS04F"],
                                        "boat_left_px_ratio": Rr["K_boat"]["boat_left_pixels_ratio_vs_sample04"]}, "pass": Rr["K_boat"]["verdict"] == "pass"})
    K.append({"id": "K-claws", "value": {"C3_iou_p10_p50_min": get(Rr, "C2_C3.C3.iou_painting_p10_p50_min_sample02"), "C2_fail": get(Rr, "C2_C3.C2.fail")}, "pass": Rr.get("C2_C3", {}).get("verdict") == "pass"})
    out = {"schema": "GreatWave.AS05B.summary/1", "date": time.strftime("%Y-%m-%d %H:%M"), "render": TAG, "targets": rows, "kept": K}
    B.jdump(SB + "/measure/summary_AS05B.json", out)
    # 表の図
    f = ImageFont.truetype(FONT, 17); fb = ImageFont.truetype(FONT, 26)
    H = 110 + 30 * (len(rows) + len(K) + 3)
    S = Image.new("RGB", (1920, H), (248, 246, 240)); d = ImageDraw.Draw(S)
    d.text((20, 12), "見本05 やり方 B：測れる目標（targets.json）と守る規則の結果", fill=(20, 20, 20), font=fb)
    d.text((20, 52), "目標の値は進行役の既定で、利用者の言葉ではない。美術が届いたかは利用者が決める（Q29・Q30）。合 = 目標に届いた、否 = 届かない", fill=(60, 60, 60), font=f)
    y = 96
    def fmt(v):
        s = json.dumps(v, ensure_ascii=False)
        return s if len(s) < 120 else s[:117] + "…"
    for r in rows + [{"id": "―― 守る規則 ――", "value": "", "pass": None}] + K:
        col = (30, 120, 50) if r["pass"] is True else ((190, 40, 40) if r["pass"] is False else (60, 60, 60))
        mark = "合" if r["pass"] is True else ("否" if r["pass"] is False else (str(r["pass"]) if r["pass"] else ""))
        d.text((20, y), r["id"], fill=(20, 20, 20), font=f)
        d.text((180, y), mark, fill=col, font=f)
        d.text((260, y), fmt(r["value"]), fill=(30, 30, 30), font=f)
        y += 30
    os.makedirs(SB + "/sheets", exist_ok=True)
    S.save(SB + "/sheets/sB_8_targets.png")
    # run.json
    tools = sorted(glob.glob(B.REPO + "/Tools/GWWaveGen/as05/shapeB_*")) + [B.REPO + "/Tools/GWWaveGen/as05/as05b_flat_smooth_params.txt"]
    outs = [SB + "/final/design_AS05B.json", SB + "/final/cand/kstarAS05B_a45_rows.npz", SB + "/final/cand/kstarAS05B_a45.gwb",
            SB + "/final/cand/kstarAS05B_a45_meta.json", SB + "/mesh/hero_smooth_as05b.json", SB + "/mesh/hero_smooth_as05b.bin",
            SB + "/mesh/white_mask_as05b_f32.bin", SB + "/union/union.json", SB + "/claws/ds33_claw_layout.json", SB + "/claws/ds33_claw_frames_f32.bin",
            SB + "/hero_pkg_AS05B/ds27_keypose.json", SB + "/attr/a/s01a_hero_attr_v2_f32.bin", SB + "/final/quick/row_labels.npy"]
    ins = [B.ROWS04F, B.WAVE4_F1, B.REPO + "/Unity/Build/Polish/sample04/fix1/shape/mesh/white_mask_as04f_f32.bin",
           B.REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz", B.REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz",
           B.REPO + "/Tools/GWWaveGen/as04/as04_flat_smooth_params.txt", B.P + "/sample05/study/targets.json"]
    rel = lambda p: p.replace("\\", "/").replace(B.REPO + "/", "")
    run = {"schema": "GreatWave.AS05B.run/1", "date": time.strftime("%Y-%m-%d %H:%M"), "render": TAG,
           "tools": {rel(p): B.sha(p) for p in tools if os.path.isfile(p)},
           "inputs": {rel(p): B.sha(p) for p in ins if os.path.isfile(p)},
           "outputs": {rel(p): B.sha(p) for p in outs if os.path.isfile(p)},
           "unity_assets_used_unchanged": {rel(p): B.sha(p) for p in (B.REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04F_Flat_Smooth_Keypose.shader",
                                                                       B.REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04FCommon.cginc",
                                                                       B.REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs")},
           "reference_model_read": False, "photos_read": False, "git": "add・commit・push はしていない"}
    B.jdump(SB + "/run.json", run)
    print(json.dumps([[r["id"], r["pass"]] for r in rows + K], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
