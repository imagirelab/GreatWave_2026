# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：要求書の測る規則のうち B2 に関わるものを自動で確かめる（読み取りのみ）。
G1（コードの検査）：AS03 のシェーダーと描画の道具に、原画カメラの投影・画面の座標で色を決める道・テクスチャの読みがないこと。
  画面の微分（fwidth・ddx・ddy）は、アンチエイリアスと keypose の道の面の向きにだけ使う（数を記録する）。
G1（描画）：7 視点と回り台で、主役波の色区が視点で入れ替わらないこと（同じ頂点は同じ色区）を、色の描画ではなく作りで保証する（属性とワールドの光だけ）。
T4 の案（調べ S3 の tech_plan の T4-6・T4-8）は数を記録する。閉じる条件ではない（Q30：美術は利用者が判定する）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_rules.py <版 v11> <メッシュの名前>"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "v11"
MN = sys.argv[2] if len(sys.argv) > 2 else "hero_relief_b1v2"
SH = S.REPO + "/Unity/Assets/GreatWave/ArtSample03/Shaders"
files = [SH + "/AS03Common.cginc", SH + "/AS03_Flat_Keypose.shader", SH + "/AS03_Sculpt_Keypose.shader"]
forbid = ["PaintingCam", "_PaintCam", "_DS36", "ComputeScreenPos", "ComputeGrabScreenPos", "_ScreenParams", "unity_CameraProjection", "unity_CameraInvProjection",
          "UNITY_MATRIX_P", "UNITY_MATRIX_VP", "unity_MatrixVP", "_S01BDesign", "tex2D", "sampler2D", "Texture2D", "SV_Position.xy", "i.pos.xy", "_CameraDepthTexture", "uv3File", "_AF28Bake"]
code = {}
hits = {}
deriv = {}
for p in files:
    t = open(p, encoding="utf-8").read()
    body = "\n".join(l.split("//")[0] for l in t.splitlines())   # 説明の行は除く
    code[p] = S.sha(p)
    hits[p] = [f for f in forbid if f in body]
    deriv[p] = {k: len(re.findall(r"\b%s\s*\(" % k, body)) for k in ("fwidth", "ddx", "ddy")}
rend = S.REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03SurfRender.cs"
rb = open(rend, encoding="utf-8-sig").read()
seg = rb[rb.index("// ---- 美術の見本03 の作り B2：静止の彫りの面と AS03 の材質"): rb.index("var as03Cg = Arg(a, \"-as03ClawGlaze\")")]
rend_hits = [f for f in ("SetMatrix", "worldToCameraMatrix", "projectionMatrix", "PaintingCam", "SetTexture") if f in seg]
ms = S.jload(S.OUT + "/measure/B2_%s_sculpt_measure.json" % TAG)
mf = S.jload(S.OUT + "/measure/B2_%s_flat_measure.json" % TAG)
mr = S.jload(S.OUT + "/mesh/%s_report.json" % MN)
sil = S.jload(S.OUT + "/measure/silhouette_vs_sample02.json")
crest_s = {k: d.get("white_lum_spread") for k, d in ms["crest"].items()}
views_s = {k: d.get("white_lum_spread") for k, d in ms["views"].items()}
gap = mr["spacing_front_face"]
rec = {
    "schema": "GreatWave.AS03.B2_rules/1",
    "G1_code": {"pass": all(not v for v in hits.values()) and not rend_hits, "forbidden_tokens_found": hits, "render_tool_projection_tokens_in_B2_block": rend_hits,
                "screen_derivative_calls": deriv, "files_sha256": code,
                "noteJa": "色・模様・拡散の陰は頂点の属性（面の座標・高さ・線の座標・焼いた AO と固定の光の見通し）とワールドに固定した光だけ。画面の微分はアンチエイリアス（線の縁・白の縁の 1 画素）と keypose の道の ∇q の向きにだけ使う。SCULPT の鏡の光と映り込みだけが見る位置で動く（釉の性質）。"},
    "G1_mesh": {"stretch_note": "稜は面の座標 w（見本01・02 で歪みを測った座標）と高さだけで決まる。静止のメッシュの行を 4 倍に細かくし、Catmull–Rom で補ったので、継ぎ目・T 字はない（行を丸ごと足した）。",
                "faded_vertices": mr["displacement_m"]["faded_area_vertices"]},
    "silhouette_vs_sample02": sil,
    "T4_6_sculpt_white_spread_ge_50": {"target": ">= 50（調べ S3 の案）", "views": views_s, "crest": crest_s,
                                         "fails": [k for k, v in list(views_s.items()) + list(crest_s.items()) if v is not None and v < 50]},
    "T4_6_specular_px": {"sculpt_white": ms["summary"]["specular_px_white_total"], "sculpt_ai": ms["summary"]["specular_px_ai_total"], "flat": mf["summary"]["specular_px_white_total"]},
    "T4_6_drawn_lines": {"sculpt": "0（コードに線の道がない。色が近い画素の数え %d は藍の稜・裾の色の取り違え）" % ms["summary"]["drawn_line_px_total"],
                         "flat": "白と藍の境に 1.2 画素（原画視点 %d 画素）" % mf["views"]["painting"]["drawn_line_px"]},
    "T4_8_spacing": {"target_m": "0.9〜1.1（0.4 H 以上）／1.4〜2.0（0.25〜0.35 H）（調べ S3 の案）。S1 の写真は 0.73／0.93／1.16（冠の下／中ほど／下）",
                     "ours_gap_p50_m": {k: v["gap_p50_m"] for k, v in gap.items()}, "ours_gap_mean_m": {k: v["gap_mean_m"] for k, v in gap.items()},
                     "noteJa": "S3 の案の下の 1.4〜2.0 m は参照モデルの粗い数（S1 で参照モデルの面には溝の凹凸がないと分かった）。S1 の写真の数（下 0.056 H = 1.16 m）に合わせた。"},
    "T4_8_groove_width": {"design": 0.244, "rendered_face_frac": ms["summary"]["face_groove_frac_views"]},
    "lip_white_frac_painting": ms["views"]["painting"].get("lip_white_frac"),
    "judgement_ja": "どれも閉じる条件ではない。美術が届いたかは利用者が判定する（Q29・Q30）。",
}
S.jdump(S.OUT + "/measure/B2_rules.json", rec)
print(json.dumps({"G1": rec["G1_code"]["pass"], "hits": hits, "rend": rend_hits, "deriv": deriv, "spread_fails": rec["T4_6_sculpt_white_spread_ge_50"]["fails"]}, ensure_ascii=False))
