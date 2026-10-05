# -*- coding: utf-8 -*-
"""美術の見本06 の段の行（B-ROWS、Q34）：as05/fx5_rules.py（変えない）の写しに、形 R（段の行の主役波 AS06R ＋ wave4 fix1、
置き場 Unity/Build/Polish/sample06/rows）を足した。py -3.10 -B Tools/GWWaveGen/as06/rows_rules.py R [描画の名前（既定 R6）]
出力は Unity/Build/Polish/sample06/rows/rules_check_<描画の名前>.json（環境変数 R6_FINAL・R6_UNION でパイプラインの根と静止のメッシュを替える）。Q34 で船を避ける制約を外したので、K-boat は「船を原画のカメラを中心とする相似で手前へ動かした描画で、
一艘目の船の画素が見本04 より減らないか」を測る（船の倍率は描画の記録 as06r_boat_1.json）。
以下は fx5_rules.py の説明のまま。
美術の見本05 の直しの回 fix1（Q33）：asm5_rules.py（変えない）の写し。置き場を直しの回のもの（Build/Polish/sample05/fix1）へ替えた。
  py -3.10 -B Tools/GWWaveGen/as05/fx5_rules.py A|B [描画の名前（既定 A9・B10）]
  出力は Unity/Build/Polish/sample05/rules_check_A.json・rules_check_B.json（直す前の版は rules_check_*_before_fix.json に残す）。
  見本04 の白い粒・内の縁の前の値（t5t6_S04_*）は組み立ての回の Build/Polish/sample05/assemble/measure から読む。
  形 A の S9 は shapeA_rules を、shapeA_common の置き場を fix1/A へ替えてから呼ぶ。
以下は asm5_rules.py の説明のまま。
美術の見本05 の組み立て（Q33）：形 A・形 B のそれぞれを、材質 AS05 を当てて組み立てた Unity の描画と部品のファイルで、美術の要求書の測る規則に
当てて確かめ、Unity/Build/Polish/sample05/rules_check_A.json・rules_check_B.json に書く（読み取りのみ。形・材質は変えない）。

  py -3.10 -B Tools/GWWaveGen/as05/asm5_rules.py A|B [描画の名前（既定 A5・B6）]

見本04 の asm4_rules.py（変えない）の測りを、置き場（主役波の行・静止のメッシュ・wave4・爪・描画・関門）を形 A・B のものへ替えて呼ぶ
（shapeB_rules.py と同じやり方）。形 A の ③ の波 layer3 は、S4・S10 では wave4 と合わせたメッシュ（assemble/A/mesh/wave4_layer3.json）として、
S9 では shapeA_rules.k_s8_s9（layer3 を wave4 と分けて持ち主を数える）で扱う。
  G1   シェーダー AS05 の 2 つのファイルに原画カメラの投影・テクスチャの語がない。AS04F との差は白い点の関数・値と名前だけ。描画の道具 AS03AsmRender は見本03 の
       確かめた版と同じ。描画の記録（焼き込みのパスが空・守るファイル不変・冠なし）。静止のメッシュのチャンネル。mat_edge が変えたのは主役波の whiteSD（uv5.z）だけ。
       面の座標 w の伸び（見本03 の形より増えない）
  G2   原画視点の関門（合わせた輪郭、as02_asm_eval.sh → sweep_gates.json）：78・130・131 ≤ 4 px、132 σ12・72 σ12 p95 ≤ 4 px
  S4   背は一つの山（asm4_rules.s4。形 A は wave4 ＋ layer3 と合わせた H(c)・後ろからの輪郭、背の等高線は AS05A の行で測り直した back_measure）
  S8   出っ張り（asm4_rules.s8）
  S9   左の白は低い・④ は wave4 が作る（B は asm4_rules.s9、A は shapeA_rules.k_s8_s9）
  S10  峰に沿う長さ：低い帯（0.1〜0.5 H）は見本03 より短い（asm4_rules.s10）、高い帯（0.6〜0.9 H）は見本04 と ±0.5 m（±0.25 m も記録）
  S11  三つの層（targets.json の L・P）：層の突出・鞍より前・15 視点の分かれ（両方の組 ≥ 0.5）・原画視点の ③ の見え方
  T5   波の本体の白い粒（asm5_measure.py：爪なしの描画で本体の藍に囲まれた白・水色の小さな塊。原画視点 0、ほかの視点も記録）
  T6   唇の下の内の縁（asm5_measure.py：利用者の切り出しの中の縁から 16 画素の帯の白・水色の割合 ≤ 0.02）
  C2・C3 面の内の爪 25 本（asm4_rules.c2_c3）
  K-top・K-boat（記録）：いちばん高い峰の行 c ≥ −8 m が見本04 のまま、一艘目の船が原画視点で隠れない
美術が届いたかは利用者が決める（Q29・Q30）。ここは「測れる規則を通るか」だけ。
"""
import difflib
import json
import os
import re
import sys
import time

os.environ["AS04_FIX"] = "fix1"
import numpy as np  # noqa: E402

HERE = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05"
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as04")
sys.path.insert(0, HERE)
import asm4_common as A  # noqa: E402

VAR = sys.argv[1]
RTAG_ARG = sys.argv[2] if len(sys.argv) > 2 else None        # 描画の名前（既定 A5・B6）
P = REPO + "/Unity/Build/Polish"
P4 = P + "/sample04"
P5 = P + "/sample05"
ASM5 = P5 + "/fix1/assemble"            # 直しの回 fix1
ASM5_OLD = P5 + "/assemble"             # 見本04 の前の値（t5t6_S04_*）の置き場
FX1 = P5 + "/fix1"
RTAG = RTAG_ARG or {"A": "A9", "B": "B10", "R": "R6"}[VAR]
P6 = P + "/sample06/rows"
FR6 = os.environ.get("R6_FINAL", P6 + "/final")          # パイプラインの根（R6b は final_b）
SRC_UNION = {"A": FX1 + "/A/mesh/union_AS05A.json", "B": FX1 + "/B/union/union.json", "R": FR6 + "/union/union.json"}[VAR]
if VAR == "R":
    ASM5 = P6                            # 見本06：描画・測りの置き場
A.ASM = ASM5
A.RTAG = RTAG
A.MEAS = ASM5 + "/measure/rules_" + RTAG
if VAR == "A":
    A.UNION = ASM5 + "/A/mesh/union_AS05A_f1.json"
    A.WAVE4 = ASM5 + "/A/mesh/wave4_layer3.json"            # S4・S10 の合わせた形（wave4 ＋ layer3）
    A.HERO_SM04 = FX1 + "/A/mesh/hero_smooth_as05a.json"
    A.ROWS04 = FX1 + "/A/hero/cand/kstarAS05A_a45_rows.npz"
    A.GWB04 = FX1 + "/A/hero/cand/kstarAS05A_a45.gwb"
    A.CLAWS04 = FX1 + "/A/claws/ds33_claw_layout.json"
    BACK = FX1 + "/A/eval_AS05A_back_measure.json"
    HERO_ONLY_R = None
    import shapeA_common as _CA              # shapeA_rules（S9）が読む置き場を fix1/A へ
    _CA.OUT = FX1 + "/A"; _CA.CAND = _CA.OUT + "/hero/cand/" + _CA.NAME; _CA.ROWS05A = _CA.CAND + "_rows.npz"
    _CA.GWB05A = _CA.CAND + ".gwb"; _CA.L3_JSON = _CA.OUT + "/l3/layer3.json"
elif VAR == "R":
    # 見本06 の段の行：AS06R の whiteSD に、見本04 の主役波で決めた T6 の規則を当てたもの（as05/fx5_b_edge.py をそのまま使う）
    A.UNION = os.environ.get("R6_UNION", P6 + "/mesh/union_AS06R_f1.json")
    A.WAVE4 = P4 + "/wave4/mesh_fix1/wave4.json"
    A.HERO_SM04 = FR6 + "/mesh/hero_smooth_as06r.json"
    A.ROWS04 = FR6 + "/final/cand/kstarAS06R_a45_rows.npz"
    A.GWB04 = FR6 + "/final/cand/kstarAS06R_a45.gwb"
    A.CLAWS04 = FR6 + "/claws/ds33_claw_layout.json"
    BACK = FR6 + "/final/eval_AS06R_back_measure.json"
    HERO_ONLY_R = ASM5 + "/render/" + RTAG + "H"
    # 見本06：静止のメッシュの行の範囲を広げたので、主役波の頂点の数が見本04（314,400）と違う。主役波と wave4 の分け目を AS06R の数にする
    A.N_HERO = int(A.jl(A.HERO_SM04)["vertices"])
else:
    # B10：形 B（直しの回）の whiteSD に、見本04 の主役波で決めた T6 の規則を当てたもの（fx5_b_edge.py）
    A.UNION = ASM5 + "/B/mesh/union_AS05B_f1.json"
    A.WAVE4 = P4 + "/wave4/mesh_fix1/wave4.json"
    A.HERO_SM04 = FX1 + "/B/mesh/hero_smooth_as05b.json"
    A.ROWS04 = FX1 + "/B/final/cand/kstarAS05B_a45_rows.npz"
    A.GWB04 = FX1 + "/B/final/cand/kstarAS05B_a45.gwb"
    A.CLAWS04 = FX1 + "/B/claws/ds33_claw_layout.json"
    BACK = FX1 + "/B/final/eval_AS05B_back_measure.json"
    HERO_ONLY_R = ASM5 + "/render/" + RTAG + "H"
import asm4_rules as R  # noqa: E402
import shape_common as SC  # noqa: E402

RENDER = ASM5 + "/render/" + RTAG
R.RENDER = RENDER
R.GATES = ASM5 + "/render/measure/gates_" + RTAG + "/sweep_gates.json"
R.BACK_MEASURE = BACK
if HERO_ONLY_R:
    R.HERO_ONLY = HERO_ONLY_R
OUT = (P6 + "/rules_check_%s.json" % RTAG) if VAR == "R" else (P5 + "/rules_check_%s.json" % VAR)
ROWS04F = P4 + "/fix1/shape/final/cand/kstarAS04F_a45_rows.npz"
WAVE4F = P4 + "/wave4/mesh_fix1/wave4.json"
TARGETS = P5 + "/study/targets.json"
SH5 = REPO + "/Unity/Assets/GreatWave/ArtSample05/Shaders"
SH4 = REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders"
SHADERS5 = [(SH5 + "/AS05Common.cginc", SH4 + "/AS04FCommon.cginc"), (SH5 + "/AS05_Flat_Smooth_Keypose.shader", SH4 + "/AS04F_Flat_Smooth_Keypose.shader")]
BOAT_CS = REPO + "/Unity/Assets/GreatWave/ArtSample05/Editor/AS05ABoatRender.cs"
M5F = P5 + "/mat/mesh/union_as05.json"

# 形 A の爪の並びは置き直しの記録を as05a_shape に持つ。asm4_rules.c2_c3 は as04_shape.face_interior を読むので、同じ中身を渡す
_claws_tris0 = A.claws_tris


def _claws_tris(path, kept_only=True):
    out, lay = _claws_tris0(path, kept_only)
    if "as04_shape" not in lay and "as05a_shape" in lay:
        fi = [dict(c) for c in lay["as05a_shape"]["claws"] if c.get("role", "FACE_INTERIOR") == "FACE_INTERIOR"]
        lay["as04_shape"] = {"face_interior": fi, "note_ja": "形 A の as05a_shape の写し（asm5_rules が渡す）"}
    return out, lay


A.claws_tris = _claws_tris


def T():
    return time.strftime("%H:%M:%S")


def code_only(t):
    return "\n".join(l.split("//")[0].rstrip() for l in t.splitlines())


def g1():
    forbid = ["PaintingCam", "_PaintCam", "_DS36", "ComputeScreenPos", "ComputeGrabScreenPos", "unity_CameraProjection", "unity_CameraInvProjection",
              "UNITY_MATRIX_P", "UNITY_MATRIX_VP", "unity_MatrixVP", "_S01BDesign", "tex2D", "sampler2D", "Texture2D", "_CameraDepthTexture", "uv3File", "_AF28Bake"]
    ok = True
    code = {}
    for p5, p4 in SHADERS5:
        t5 = open(p5, encoding="utf-8").read()
        body = code_only(t5)
        hits = [f for f in forbid if f in body]
        # 名前を AS04F に戻して、AS04F（変えない）とコードの行で比べる
        norm = (body.replace("GREATWAVE_AS05_COMMON", "GREATWAVE_AS04F_COMMON").replace("AS05Common.cginc", "AS04FCommon.cginc")
                .replace("ArtSample05/AS05FlatSmoothKeypose", "ArtSample04/AS04FFlatSmoothKeypose").replace("AS05FlatSmooth", "AS04FFlatSmooth").replace("AS05", "AS04"))
        b4 = code_only(open(p4, encoding="utf-8").read())
        la = [l for l in norm.splitlines() if l.strip()]
        lb = [l for l in b4.splitlines() if l.strip()]
        dd = list(difflib.ndiff(lb, la))
        added = [l[2:].strip() for l in dd if l.startswith("+ ")]
        removed = [l[2:].strip() for l in dd if l.startswith("- ")]
        rem_fleck = [l for l in removed if "Fleck" in l or "fleck" in l]
        code[A.rel(p5)] = {"sha256": A.sha(p5), "base_AS04F": A.rel(p4), "base_sha256": A.sha(p4), "forbidden_tokens": hits,
                           "code_lines_added_vs_AS04F": added, "code_lines_removed_vs_AS04F": len(removed),
                           "code_lines_removed_with_Fleck": len(rem_fleck),
                           "screen_derivative_calls": {k: len(re.findall(r"\b%s\s*\(" % k, body)) for k in ("fwidth", "ddx", "ddy")}}
        ok &= not hits
        # 足した行は「白い点の値を外した宣言」だけ（例：float4 _MizuFringe;）であること
        ok &= all(("_MizuFringe" in l) for l in added)
    tool_sha = A.sha(R.TOOL_CS)
    s3 = A.jl(R.S3_RULES)["rules"]["G1"]["render_tool"]
    tool_same = tool_sha == s3["sha256"]
    ok &= tool_same
    rr = A.jl(RENDER + "/as03asm_render_report.json")
    rep = {k: rr.get(k) for k in ("heroSdf", "heroUvWarp", "heroUv3File", "protectedUnchanged", "as03Shader", "as03Surf", "as03SurfSha256", "as03Crown",
                                  "as03ClawGlaze", "as03Params", "clawLayout", "as03HeroOutline", "changedFiles")}
    ok &= (not rep["heroSdf"]) and (not rep["heroUvWarp"]) and (not rep["heroUv3File"]) and rep["protectedUnchanged"] is True and not rep["as03Crown"]
    ok &= rep["as03Shader"] == "GreatWave/ArtSample05/AS05FlatSmoothKeypose"
    uj = A.jl(A.UNION)
    chans = [c[0] for c in uj["channels"]]
    ch_ok = chans == ["position", "normal", "tangent", "uv3", "uv4", "uv5", "uv6"]
    ok &= ch_ok
    # mat_edge が変えたのは主役波の whiteSD（uv5.z）だけか
    ch1, t1, _ = A.read_static(SRC_UNION)
    ch2, t2, _ = A.read_static(A.UNION)
    same = {k: bool(np.array_equal(ch1[k], ch2[k])) for k in ch1 if k != "uv5"}
    same["triangles"] = bool(np.array_equal(t1, t2))
    same["uv5_xyw"] = bool(np.array_equal(ch1["uv5"][:, [0, 1, 3]], ch2["uv5"][:, [0, 1, 3]]))
    dz = np.nonzero(ch1["uv5"][:, 2] != ch2["uv5"][:, 2])[0]
    same["uv5_z_changed_vertices"] = int(len(dz))
    same["uv5_z_changed_only_hero"] = bool(len(dz) == 0 or dz.max() < A.N_HERO)
    same["white_to_indigo_vertices"] = int(((ch1["uv5"][:, 2] > 0) & (ch2["uv5"][:, 2] <= 0)).sum())
    geo_ok = all(v for k, v in same.items() if k not in ("uv5_z_changed_vertices", "white_to_indigo_vertices"))
    ok &= geo_ok
    del ch1, ch2
    print(T(), "G1 stretch", flush=True)
    st = {"hero": R.stretch(A.UNION, "hero"), "other_meshes": R.stretch(A.UNION, "wave4"), "AS02C_smooth_sample03_shape": R.stretch(A.HERO_SM02C)}
    a4, a2 = st["hero"]["patterned_face"], st["AS02C_smooth_sample03_shape"]["patterned_face"]
    s_ok = a4["gw_tri_outside_1_3_to_3x"] <= a2["gw_tri_outside_1_3_to_3x"] and a4["gw_area_frac_outside_1_3_to_3x"] <= a2["gw_area_frac_outside_1_3_to_3x"] + 1e-3
    # 伸びの三角形の場所（c・高さ）と、材質の書き換えの前の形のメッシュでも同じかを記録する（どちらの係の直しかを分けるため）
    where = {}
    for nm, path in (("this_mesh", A.UNION), ("shape_mesh_before_mat_edge", SRC_UNION), ("AS05F_material_on_sample04", M5F)):
        m = R.stretch_masks(path, "hero")
        bad = m["sel"] & m["pat"] & ((m["gw"] < 1 / 3) | (m["gw"] > 3))
        Q = A.K.sec(m["pos"]); cm = Q[:, 2][m["tri"]].mean(1); ym = Q[:, 1][m["tri"]].mean(1)
        where[nm] = {"patterned_tri_w_outside": int(bad.sum()),
                     "c_m_p0_p10_p50_p90_p100": [A.rnd(x, 2) for x in np.percentile(cm[bad], (0, 10, 50, 90, 100))] if bad.any() else None,
                     "y_m_p10_p50_p90": [A.rnd(x, 1) for x in np.percentile(ym[bad], (10, 50, 90))] if bad.any() else None}
    boat = None
    if VAR == "A":
        tb = code_only(open(BOAT_CS, encoding="utf-8").read())
        boat = {"path": A.rel(BOAT_CS), "sha256": A.sha(BOAT_CS), "forbidden_tokens": [f for f in forbid if f in tb],
                "note_ja": "一艘目の船を原画のカメラを中心とする相似で動かしてから AS03AsmRender を呼ぶだけの入口（色・線には関わらない）"}
        ok &= not boat["forbidden_tokens"]
    return {"rule_ja": "色・線は原画カメラの投影を使わない（コードの検査）。面の座標の伸びが見本03 の形より増えない",
            "shaders_AS05": code, "render_tool": {"path": A.rel(R.TOOL_CS), "sha256": tool_sha, "same_as_sample03_checked": tool_same},
            "boat_entry_AS05A": boat, "render_report": rep,
            "union_mesh": {"path": A.rel(A.UNION), "bin_sha256": uj["sha256"], "channels": chans, "only_geometry_attrs": ch_ok,
                           "vs_shape_union_before_mat_edge": {"path": A.rel(SRC_UNION), "identity": same}},
            "surface_stretch_front": st, "surface_stretch_not_worse": bool(s_ok), "surface_stretch_where": where,
            "code_and_record_checks_pass": bool(ok),
            "surface_stretch_note_ja": ("帯の座標 w の伸び（|∇w| が 1/3〜3 倍の外）の三角形の数。直す前（組み立ての回）は形 A 795・形 B 805 で、どちらも新しい ② ③ の段の脇の"
                                        "切り口（行の間で断面が急に変わる所）だった。直しの回で段の出入りを広げ、行の間の跳びをなくした（fx5_B_build.py・形 A の設計）"),
            "note_ja": ("材質の色は頂点の属性（帯の座標・白の印 whiteSD）とシェーダーの限られた色だけから。T6 の白の書き換え（mat_edge.py）は原画のカメラを縁の頂点を"
                        "探すのにだけ使い、結果は頂点の whiteSD に残る（どの視点でも同じ面は同じ色）。7 視点と回り台の見た目は利用者が並べ図で見る。"),
            "verdict": "pass" if (ok and s_ok) else "fail"}


def s9_A():
    import shapeA_rules as SA
    tris, lab = SA.scene_union()
    s8, s9 = SA.k_s8_s9(tris, lab)
    s9["rule_ja"] = "左側の白は低い。④（輪郭線の最も左の短い一区間）は青い波 wave4 が作る"
    s9["note_ja"] = ("形 A は ③ の波 layer3 があるので、shapeA_rules.k_s8_s9 で layer3 を wave4 と分けて持ち主を数える（形は形 A の係のものと同じ。"
                     "白の最も左の c は材質の書き換えの前の静止のメッシュで読むが、mat_edge が変えたのは右の脇の稜（c 5.7〜13.7 m）だけ）")
    return s9


def s10():
    r = R.s10()
    c4, A4, Y4 = SC.load_rows(A.ROWS04)
    ch, _, _ = A.read_static(A.WAVE4)
    eu = R.bands_union(c4, Y4, ch["position"].astype(np.float64))
    cf, Af, Yf = SC.load_rows(ROWS04F)
    chf, _, _ = A.read_static(WAVE4F)
    e04 = R.bands_union(cf, Yf, chf["position"].astype(np.float64))
    diff = {k: (A.rnd(eu[k]["width_m"] - e04[k]["width_m"], 2) if eu.get(k) and e04.get(k) else None) for k in e04}
    hi = ("0.6", "0.7", "0.8", "0.9")
    hi_ok = all(diff[k] is not None and abs(diff[k]) <= 0.5 for k in hi)
    hi_ok25 = all(diff[k] is not None and abs(diff[k]) <= 0.25 for k in hi)
    r["vs_sample04_AS04F_union"] = {"sample04_union": e04, "diff_m": diff, "high_bands_within_0.5m": bool(hi_ok), "high_bands_within_0.25m": bool(hi_ok25)}
    r["pass_condition_ja"] = ("合わせた形（主役波 ＋ wave4" + (" ＋ layer3" if VAR == "A" else "") + "）で、低い帯（0.1〜0.5 H）が見本03 より短く、どの帯も長くならない。"
                              "高い帯（0.6〜0.9 H、いちばん高い峰の幅）は見本04 と ±0.5 m（Q33：上の峰の幅は見本03・04 のまま）")
    r["verdict_sample03_part"] = r["verdict"]
    r["verdict"] = "pass" if (r["verdict"] == "pass" and hi_ok) else "fail"
    return r


def get(d, path):
    cur = d
    for k in path.split("."):
        if cur is None or not isinstance(cur, dict):
            return None
        cur = cur.get(k)
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


def s11():
    Tg = A.jl(TARGETS)
    M = A.jl(ASM5 + "/measure/targets_%s.json" % RTAG)
    rows = {}
    for t in Tg["targets"]:
        tid, metric, pf = t["id"], t["metric"], t["pass_if"]
        res = {"kind": t["kind"], "metric": metric, "pass_if": pf, "baseline_sample04": t.get("baseline_sample04")}
        if "{" in metric:
            pre, rest = metric.split("{", 1)
            keys, post = rest.split("}", 1)
            vals, ok = {}, True
            for k in keys.split(","):
                v = get(M, pre + k + post)
                vals[k] = v
                thr = pf["value"][k] if isinstance(pf["value"], dict) else pf["value"]
                ok = ok and bool(judge(v, pf["op"], thr))
            res["value"], res["pass"] = vals, ok
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
            res["value"], res["pass"] = v, judge(v, pf["op"], pf["value"])
        rows[tid] = res
    asked = {"layer_prominence": ["L1-2", "L1-3"], "forward_offsets": ["L2-2", "L2-3"], "separation_15views_both_pairs_ge_0.5": ["L6-sep"],
             "painting_view_look_of_3": ["P1-top", "P1-mid", "P1-cells"]}
    asked_res = {k: {i: rows[i]["pass"] for i in v} for k, v in asked.items()}
    ok = all(all(x for x in v.values()) for v in asked_res.values())
    must = {i: r["pass"] for i, r in rows.items() if r["kind"] == "must"}
    should = {i: r["pass"] for i, r in rows.items() if r["kind"] == "should"}
    return {"rule_ja": "三つの層 ①②③ を形で分ける（Q32・Q33、targets.json の L・P）", "targets_source": A.rel(TARGETS),
            "measured": A.rel(ASM5 + "/measure/targets_%s.json" % RTAG), "asked_by_orchestrator": asked_res, "targets": rows,
            "must_pass": "%d/%d" % (sum(1 for v in must.values() if v), len(must)), "should_pass": "%d/%d" % (sum(1 for v in should.values() if v), len(should)),
            "must_fail_ids": [i for i, v in must.items() if not v],
            "note_ja": ("目標の値は調べの係が決めた既定で、利用者の言葉ではない（利用者が美術を決める、Q29・Q30）。P1・P2 は原画視点の Unity の描画（爪あり）の色の割合。"
                        "L6-sep は見本04 の S11 と同じ決めごと（15 視点の numpy の z バッファで層どうしが遮る縁で分かれるか）"),
            "verdict": "pass" if ok else "fail"}


def load_t56(tag):
    """asm5_measure の測り（7 視点＋T6 の組 _v と、波頭・回り台の組 _ct）を 1 つにまとめる。"""
    out = {"files": [], "T5": {"per_view": {}}, "T6": {"per_view": {}}}
    for part in ("v", "ct"):
        p = (ASM5_OLD if tag == "S04" else ASM5) + "/measure/t5t6_%s_%s.json" % (tag, part)
        if not os.path.isfile(p):
            continue
        d = A.jl(p)
        out["files"].append({"path": A.rel(p), "sha256": A.sha(p), "mesh_bin_sha256": d.get("mesh_bin_sha256")})
        out["T5"]["per_view"].update(d["T5"]["per_view"])
        out["T6"]["per_view"].update(d["T6"]["per_view"])
    pv = out["T5"]["per_view"]
    out["T5"]["painting_body_blobs"] = pv.get("painting", {}).get("body_blobs")
    out["T5"]["body_blobs_total"] = int(sum(v["body_blobs"] for v in pv.values()))
    out["T5"]["views_with_body_blobs"] = {k: v["body_blobs"] for k, v in pv.items() if v["body_blobs"]}
    out["T6"]["painting_pale_share"] = out["T6"]["per_view"].get("painting", {}).get("pale_share")
    return out


def boat_split(render_dir, blobs):
    """原画視点の塊を、船の縁（Unity の ID の画で船の画素から 4 画素以内）とそれ以外に分ける。船は波の本体ではない（numpy の印の場面に船はない）。"""
    import cv2
    im = cv2.imread(render_dir + "/full/ids_noline_noclaws.png")[..., ::-1]
    boat = np.zeros(im.shape[:2], bool)
    for col in ((34, 0, 0), (0, 34, 0), (34, 34, 0)):
        boat |= (im[..., 0] == col[0]) & (im[..., 1] == col[1]) & (im[..., 2] == col[2])
    b1 = cv2.resize(boat.astype(np.uint8), (1920, 1080), interpolation=cv2.INTER_AREA) > 0
    b1 = cv2.dilate(b1.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    near = [x for x in blobs if b1[x[1], x[0]]]
    other = [x for x in blobs if not b1[x[1], x[0]]]
    return near, other


def t5():
    m = load_t56(RTAG)
    b = load_t56("S04")
    pv = m["T5"]["per_view"]
    pfirst = pv.get("painting", {}).get("body_first", [])
    near, other = boat_split(RENDER, pfirst) if pv.get("painting", {}).get("body_blobs", 0) <= 12 else ([], pfirst)
    v7 = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
    seven = {v: pv[v]["body_blobs"] for v in v7 if v in pv}
    ok = len(other) == 0
    return {"painting_body_blobs_excluding_boat_edges": len(other), "painting_blobs_at_boat_edges": near, "painting_blobs_other": other,"rule_ja": "波の本体の面に白い粒を描かない（原画の白い点は波から飛び散る浪花・白い泡で、波の本体ではない。Q33）",
            "measured": m["files"],
            "painting_body_blobs": m["T5"]["painting_body_blobs"], "sample04_painting_body_blobs": b["T5"]["painting_body_blobs"],
            "seven_views": seven, "sample04_seven_views": {v: b["T5"]["per_view"][v]["body_blobs"] for v in v7 if v in b["T5"]["per_view"]},
            "all_views_total": m["T5"]["body_blobs_total"], "sample04_all_views_total": b["T5"]["body_blobs_total"],
            "views_with_body_blobs": m["T5"]["views_with_body_blobs"],
            "wave4_blobs_painting": pv.get("painting", {}).get("wave4_blobs"),
            "pass_condition_ja": ("原画視点の爪なしの描画で、波の本体（主役波" + (" ＋ layer3" if VAR == "A" else "") + "）の藍に囲まれた白・水色の小さな塊（2〜400 画素）が、"
                                  "船の縁（Unity の ID の画の船の画素から 4 画素以内、船の縁のアンチエイリアス）を除いて 0。ほかの視点・回り台は記録"),
            "verdict": "pass" if ok else "fail"}


def t6():
    m = load_t56(RTAG)
    b = load_t56("S04")
    v = m["T6"]["painting_pale_share"]
    ok = v is not None and v <= 0.02
    return {"rule_ja": "利用者の切り出し（唇の下の内の縁、藍の面が巻きの中の空に接する縁）に白・水色を置かない。藍の面がそのまま縁の線まで来る（Q33）",
            "measured": m["files"],
            "painting_crop_pale_share": v, "sample04_painting_crop_pale_share": b["T6"]["painting_pale_share"],
            "per_view": m["T6"]["per_view"], "sample04_per_view": {k: x.get("pale_share") for k, x in b["T6"]["per_view"].items()},
            "pass_condition_ja": "原画視点の切り出しの中の縁から内へ 16 画素の主役波の画素の白・水色の割合 ≤ 0.02（座席・座席から波・波頭 0°・45° は右の脇の稜の行の縁で記録）",
            "verdict": "pass" if ok else "fail"}


def k_top():
    c, A1, Y1 = SC.load_rows(A.ROWS04)
    c0, A0, Y0 = SC.load_rows(ROWS04F)
    m = c >= -8.0
    d = float(np.max(np.hypot(A1[m] - A0[m], Y1[m] - Y0[m])))
    return {"rule_ja": "いちばん高い峰（主の頂と唇、行 c ≥ −8 m）の形は見本04 のまま（点の動き 0.05 m まで）", "max_disp_m": A.rnd(d, 4),
            "verdict": "pass" if d <= 0.05 else "fail"}


def k_boat():
    import cv2
    out = {}
    for nm, p in (("sample04_FX1", P4 + "/assemble/render/FX1/full/ids_noline_noclaws.png"), (RTAG, RENDER + "/full/ids_noline_noclaws.png")):
        im = cv2.imread(p)[..., ::-1]
        out[nm] = int(((im[..., 0] == 34) & (im[..., 1] == 0) & (im[..., 2] == 0)).sum())
    r = out[RTAG] / max(out["sample04_FX1"], 1)
    rec = {"rule_ja": "一艘目の船を原画視点で層の面が隠さない（Unity の ID の画の boat_left の画素を見本04 より減らさない）",
           "boat_left_px_ids_noline_noclaws_2x": out, "ratio": A.rnd(r, 4), "verdict": "pass" if r >= 0.98 else "fail"}
    if VAR == "R":
        bl = RENDER + "/as06r_boat_1.json"
        rec["boat_move"] = A.jl(bl) if os.path.isfile(bl) else None
        rec["note_ja"] = ("見本06 の段の行は Q34 で船を避ける制約を外した。一艘目の船は原画のカメラを中心とする相似で手前へ動かして描いた（名前の付いた美術の誘導。"
                          "原画視点の画は同じで、ほかの視点では小さくなる。船と波の差し込み合いは造型の後で調整する）")
    if VAR == "A":
        bl = RENDER + "/as05a_boat_1.json"
        rec["boat_move"] = A.jl(bl) if os.path.isfile(bl) else None
        rec["note_ja"] = ("形 A は一艘目の船を原画のカメラを中心とする相似（倍率 0.7434）で手前へ動かした（名前の付いた美術の誘導。原画視点の画は同じで、ほかの視点では 0.74 倍）。"
                          "旧い唇の舌が隠していた舳先が見えるので画素が増える")
    return rec


def main():
    t0 = time.time()
    os.makedirs(A.MEAS, exist_ok=True)
    res = {"schema": "GreatWave.AS05.rules_check/1", "date": time.strftime("%Y-%m-%d %H:%M"), "variant": VAR,
           "sample_ja": ("美術の見本06 の段の行（Q34）・形 %s：主役波 %s ＋ wave4 fix1%s ＋ 材質 AS05（白い粒なし・内の縁の白の書き換え）＋ 爪 35 本（面の内 25・近い海 10、"
                         "波頭の爪なし）。Unity 6000.4.3f1 の PC オフスクリーン描画で、HMD 実機ではない") % (
               VAR, {"A": "AS05A", "B": "AS05B", "R": "AS06R"}[VAR], " ＋ ③ の波 layer3（一艘目の船は相似で手前へ、倍率 0.7434）" if VAR == "A" else ""),
           "render": {"path": A.rel(RENDER), "report_sha256": A.sha(RENDER + "/as03asm_render_report.json")},
           "inputs": {A.rel(p): A.sha(p) for p in (A.UNION, SRC_UNION, A.WAVE4, A.HERO_SM04, A.ROWS04, A.GWB04, A.CLAWS04, BACK, TARGETS)},
           "judge_ja": "美術が届いたかは利用者が決める（Q29・Q30）。ここは「測れる規則を通るか」だけ", "rules": {}}
    steps = [("G1", g1), ("G2", R.g2), ("S4", R.s4), ("S8", R.s8), ("S9", s9_A if VAR == "A" else R.s9), ("S10", s10), ("S11", s11),
             ("T5", t5), ("T6", t6), ("C2_C3", None), ("K-top", k_top), ("K-boat", k_boat)]
    for name, fn in steps:
        try:
            if name == "C2_C3":
                c2, c3, rows = R.c2_c3()
                res["rules"]["C2"] = c2
                res["rules"]["C3"] = c3
                res["claws_per_claw"] = rows
                print(T(), "C2", c2.get("verdict"), "C3", c3.get("verdict"), flush=True)
                continue
            res["rules"][name] = fn()
        except Exception as ex:  # noqa
            import traceback
            res["rules"][name] = {"error": repr(ex), "trace": traceback.format_exc()[-2000:], "verdict": "error"}
        print(T(), name, res["rules"][name].get("verdict"), round(time.time() - t0, 1), flush=True)
        A.jdump(OUT, res)
    res["summary"] = {k: v.get("verdict") for k, v in res["rules"].items()}
    res["elapsed_s"] = round(time.time() - t0, 1)
    A.jdump(OUT, res)
    print(json.dumps(res["summary"], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
