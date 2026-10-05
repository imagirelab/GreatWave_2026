# -*- coding: utf-8 -*-
"""美術の見本06 の段の行（B-ROWS）：記録（run.json：道具・入力・出力の SHA-256 と主な数）と、測る規則の表の図（rows_8_rules.png）を書く。
py -3.10 -B Tools/GWWaveGen/as06/rows_record.py <描画の名前（R7）> <パイプラインの根の名前（final_c）> <設計.json の名前（design_R7.json）>
見本05 B（B10）の値は Unity/Build/Polish/sample05/fix1/assemble/measure/targets_B10.json と sample05/rules_check_B.json から読む（変えない）。
"""
import glob
import hashlib
import json
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
P6 = P + "/sample06/rows"
TAG, FROOT, DESIGN = sys.argv[1], sys.argv[2], sys.argv[3]
FR = P6 + "/" + FROOT


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace(REPO + "/", "")


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def font(sz):
    for p in ("C:/Windows/Fonts/BIZ-UDGothicR.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main():
    rc = jl(P6 + "/rules_check_%s.json" % TAG)
    rb = jl(P + "/sample05/rules_check_B.json")
    tg = jl(P6 + "/measure/targets_%s.json" % TAG)
    tb = jl(P + "/sample05/fix1/assemble/measure/targets_B10.json")
    qk = jl(P6 + "/measure/quick_%s/quick.json" % TAG)
    tools = sorted(p.replace("\\", "/") for p in glob.glob(REPO + "/Tools/GWWaveGen/as06/rows_*.*"))   # 段の行の道具だけ（同じ置き場のほかの係の道具は含めない）
    outs = [FR + "/final/cand/kstarAS06R_a45_rows.npz", FR + "/final/cand/kstarAS06R_a45.gwb", FR + "/mesh/hero_smooth_as06r.bin",
            FR + "/mesh/white_mask_as06r_f32.bin", FR + "/union/union.bin", FR + "/claws/ds33_claw_layout.json",
            P6 + "/render/%s/as03asm_render_report.json" % TAG, P6 + "/render/%s/as06r_boat_1.json" % TAG]
    uni = sorted(glob.glob(P6 + "/mesh/*.bin"))
    ins = [P + "/sample04/fix1/shape/final/cand/kstarAS04F_a45_rows.npz", P + "/sample04/wave4/mesh_fix1/wave4.json",
           P + "/sample04/fix1/shape/mesh/white_mask_as04f_f32.bin", P + "/sample05/fix1/B/final/cand/kstarAS05B_a45_rows.npz",
           P + "/sample05/study/targets.json", REPO + "/Unity/Assets/GreatWave/ArtSample05/Editor/AS05ABoatRender.cs"]
    run = {"schema": "GreatWave.AS06.rows_run/1", "date": time.strftime("%Y-%m-%d %H:%M"), "render": TAG,
           "design": {"path": rel(P6 + "/" + DESIGN), "sha256": sha(P6 + "/" + DESIGN)},
           "tools": {rel(p): sha(p) for p in tools if os.path.isfile(p)},
           "inputs": {rel(p): sha(p) for p in ins if os.path.isfile(p)},
           "outputs": {rel(p): sha(p) for p in outs + uni if os.path.isfile(p)},
           "reference_model_obj_read": False, "reference_photos_read": False,
           "boat_nearsea_keepout_used_by_generator": False,
           "rules_summary": rc["summary"], "rules_summary_sample05_B10": rb.get("summary"),
           "geometry": tg["geometry"]["layers"], "steps": tg["geometry"]["steps"], "separation": tg["separation_summary"],
           "geometry_B10": tb["geometry"]["layers"], "steps_B10": tb["geometry"]["steps"], "separation_B10": tb["separation_summary"],
           "S11_targets": {k: {"pass": v["pass"], "value": v["value"]} for k, v in rc["rules"]["S11"]["targets"].items()},
           "S11_targets_B10": {k: {"pass": v["pass"], "value": v["value"]} for k, v in rb["rules"]["S11"]["targets"].items()},
           "quick": {"K_top_max_disp_m": qk["K_top_max_disp_m"], "spill": {k: v for k, v in qk["spill_vs_AS04F"].items() if not k.endswith("rows")},
                     "S8": qk["S8"]["dev_from_inner_face_m"], "S10_diff": qk["S10_union_widths"]["diff"], "S4_dent": qk["S4_H_union_dent_m"]}}
    json.dump(run, open(P6 + "/run_%s.json" % TAG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 表の図
    rows = []
    for k in ("G1", "G2", "S4", "S8", "S9", "S10", "S11", "T5", "T6", "C2", "C3", "K-top", "K-boat"):
        rows.append((k, rb["summary"].get(k), rc["summary"].get(k)))
    img = Image.new("RGB", (1920, 1080), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 8), "段の行（B-ROWS）：測る規則と三つの層の目標　見本05 B（B10）｜段の行 %s" % TAG, font=font(28), fill=(0, 0, 0))
    d.text((14, 48), "目標の値は進行役の既定（targets.json）で、利用者の言葉ではない。美術が届いたかは利用者が決める（Q29・Q30）。K-boat は段の行では一艘目の船を相似で手前へ動かした描画で測る。",
           font=font(16), fill=(60, 60, 60))
    y = 90
    d.text((20, y), "規則", font=font(20), fill=(0, 0, 0)); d.text((180, y), "見本05 B", font=font(20), fill=(0, 0, 0)); d.text((330, y), TAG, font=font(20), fill=(0, 0, 0))
    y += 32
    for k, a, b in rows:
        col = (0, 120, 0) if b == "pass" else (200, 0, 0)
        d.text((20, y), k, font=font(19), fill=(0, 0, 0)); d.text((180, y), str(a), font=font(19), fill=(80, 80, 80)); d.text((330, y), str(b), font=font(19), fill=col)
        y += 28
    x0 = 520
    y = 90
    d.text((x0, y), "S11 の目標", font=font(20), fill=(0, 0, 0)); d.text((x0 + 170, y), "基準", font=font(20), fill=(0, 0, 0))
    d.text((x0 + 520, y), "見本05 B", font=font(20), fill=(0, 0, 0)); d.text((x0 + 900, y), TAG, font=font(20), fill=(0, 0, 0))
    y += 32
    T = jl(P + "/sample05/study/targets.json")["targets"]
    for t in T:
        k = t["id"]
        vb = rb["rules"]["S11"]["targets"].get(k, {})
        vr = rc["rules"]["S11"]["targets"].get(k, {})
        def fmt(v):
            s = json.dumps(v.get("value"), ensure_ascii=False)
            return (s[:44] + "…") if len(s) > 45 else s
        d.text((x0, y), "%s（%s）" % (k, t["kind"]), font=font(17), fill=(0, 0, 0))
        d.text((x0 + 170, y), json.dumps(t["pass_if"]["value"], ensure_ascii=False)[:40], font=font(15), fill=(60, 60, 60))
        d.text((x0 + 520, y), fmt(vb), font=font(15), fill=(0, 120, 0) if vb.get("pass") else (200, 0, 0))
        d.text((x0 + 900, y), fmt(vr), font=font(15), fill=(0, 120, 0) if vr.get("pass") else (200, 0, 0))
        y += 26
    y += 16
    g = rc["rules"]["G2"]["gates"]
    d.text((x0, y), "原画視点の関門（合わせた輪郭、px）：" + "、".join("%s %.2f" % (k, v["claws"]) for k, v in g.items()), font=font(17), fill=(0, 0, 0))
    y += 28
    st = rc["rules"]["G1"].get("surface_stretch_front", {}).get("hero", {}).get("patterned_face", {})
    d.text((x0, y), "G1 帯の座標 w の伸びの三角形：%s（見本05 B 0）　コードと記録の検査：%s" % (st.get("gw_tri_outside_1_3_to_3x"), rc["rules"]["G1"].get("code_and_record_checks_pass")),
           font=font(17), fill=(0, 0, 0))
    os.makedirs(P6 + "/sheets_%s" % TAG, exist_ok=True)
    img.save(P6 + "/sheets_%s/rows_8_rules.png" % TAG)
    print("RECORD_DONE", P6 + "/run_%s.json" % TAG)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
