# -*- coding: utf-8 -*-
"""美術の見本03 の組み立て：美術の要求書（Docs/Design/Art_Requirements_ja.md）の測る規則を、3 つの変種（V1 冠 OUT＋SCULPT、V2 冠 OUT＋FLAT、
V3 冠 IN＋SCULPT）の Unity の描画（asm_render.sh）と部品のファイルで自動で確かめ、Unity/Build/Polish/sample03/rules_check.json に書く（読み取りのみ）。

  G1  原画カメラの投影を使わない：AS03 のシェーダー 3 つ（B2 が確かめた版と SHA-256 が同じこと＋禁じた語の検査）、描画の道具 AS03AsmRender の
      AS03 の部分と組み立てで足した部分（冠の画・比べの視点）に原画カメラの行列・テクスチャが無いこと、描画の記録で焼き込みのパスが空・守るファイル不変、
      冠のメッシュのチャンネルが位置・法線・(ao, keyVis, whiteSD, 種類)・(f, 番号, 種類) だけ。面の座標の伸び（T1 の |∇w|）が見本02 より悪くないこと。
  G2  原画視点の関門 78・130・131 ≤ 4 px、132 σ12・72 σ12 p95 ≤ 4 px（as02_asm_eval.sh → sweep_gates.json）。V3 は通ること、V1・V2 は値を記録。評価器 23 も。
  S4  背は AS02C のまま：彫りの面の元の行の頂点を AS02C の .gwb と比べ、背（u < 0）の頂点が動いていないこと。冠の手の根元が背に無いこと。
      背の一つの山の測り（見本02 の S4 の合格）はそのまま当てはまる。
  C2・C3  面の内・近い海の爪 35 本（見本02 修正の回 1 と頂点がバイトまで同じ）で、見本02 と同じ測り（利用者の模型の水準・マスクとの IoU ≥ 0.85）。
  T4（新）  冠の指の先・手の数、指の長さ、枝分かれ（手あたりの指・分かれる所・指どうしの角）が調べ S1 の測った範囲に入ること。白の垂れる縁の舌が
      S1 の数の範囲で面にあること（彫りの面の whiteSD で確かめる）。冠が原画視点のほかのどの視点（7 視点の 6・波頭の回り台 8・回り台 12）でも
      枠の 0.5% より多く見えること（冠の画 _crownmask の (1,0,1) の画素）。頂の輪郭から出る指の数は記録。
  T1  模様の間隔の場所によるばらつき（線の間隔 ÷ 設計の周期 λ(y)）と引き伸ばしの比（|∇w|）を彫りの面で。
美術が届いたかは利用者が決める（Q29・Q30）。ここは「測れる規則を通るか」だけ。目で見た審査は閉じる条件にしない。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as03/asm_rules.py
"""
import glob
import hashlib
import json
import math
import os
import re
import sys
import time

import numpy as np
from PIL import Image

REPO = "G:/Unity/GreatWave_2026_Fresh"
U = REPO + "/Unity"
S3 = U + "/Build/Polish/sample03"
S2 = U + "/Build/Polish/sample02"
ASM = S3 + "/assemble"
RENDER = ASM + "/render"
VARIANTS = {"V1": {"crown": "OUT", "shader": "SCULPT"}, "V2": {"crown": "OUT", "shader": "FLAT"}, "V3": {"crown": "IN", "shader": "SCULPT"}}
RELIEF = S3 + "/surface/mesh/hero_relief_b1v2c.json"
GWB = S2 + "/fix01/back/final/cand/kstarAS02C_a45.gwb"
SPEC = S3 + "/study/sculpture_spec.json"
WM_PARAMS = S3 + "/shared/white_mask_params.json"
WM_BAND = S3 + "/shared/white_mask_band_f32.bin"
WM_JSON = S3 + "/shared/white_mask.json"
CLAW_REPORT = S2 + "/fix01/assemble/claws/mesh/as02_claws_report.json"
CLAW_STD = S2 + "/claws/user_claw_standard.json"
LAY83 = S2 + "/fix01/assemble/claws/mesh/ds33_claw_layout.json"
LAY35 = ASM + "/claws35/ds33_claw_layout.json"
S2_RULES = S2 + "/rules_check.json"
B2_RULES = S3 + "/surface/measure/B2_rules.json"
SH = U + "/Assets/GreatWave/ArtSample03/Shaders"
SHADERS = [SH + "/AS03Common.cginc", SH + "/AS03_Flat_Keypose.shader", SH + "/AS03_Sculpt_Keypose.shader"]
TOOL_CS = U + "/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs"
OUT = S3 + "/rules_check.json"
NON_PAINTING_VIEWS = ["seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
FRAME_PX = 1920 * 1080
VIS_MIN = 0.005

sys.path.insert(0, REPO + "/Tools/GWWaveGen/sample01")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
from s01_param import load_gwb  # noqa: E402
import as02_asm_rules as R  # noqa: E402


def sha(p):
    if not os.path.isfile(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def pct(a, qs, w=None):
    a = np.asarray(a, float)
    if a.size == 0:
        return None
    if w is None:
        return [round(float(x), 4) for x in np.percentile(a, qs)]
    o = np.argsort(a)
    cw = np.cumsum(np.asarray(w, float)[o])
    cw /= cw[-1]
    return [round(float(a[o][min(np.searchsorted(cw, q / 100.0), a.size - 1)]), 4) for q in qs]


def load_static(jp):
    j = jl(jp)
    n, m = j["vertices"], j["triangles"]
    bp = os.path.join(os.path.dirname(jp), j["bin"])
    raw = np.fromfile(bp, np.uint8)
    off, ch = 0, {}
    for name, k in j["channels"]:
        ch[name] = np.frombuffer(raw, np.float32, n * k, off).reshape(n, k)
        off += n * k * 4
    tri = np.frombuffer(raw, np.uint32, m * 3, off).reshape(m, 3).astype(np.int64)
    return j, ch, tri


# ---------------------------------------------------------------- G1
def g1(t1res):
    forbid = ["PaintingCam", "_PaintCam", "_DS36", "ComputeScreenPos", "ComputeGrabScreenPos", "_ScreenParams", "unity_CameraProjection",
              "unity_CameraInvProjection", "UNITY_MATRIX_P", "UNITY_MATRIX_VP", "unity_MatrixVP", "_S01BDesign", "tex2D", "sampler2D", "Texture2D",
              "SV_Position.xy", "i.pos.xy", "_CameraDepthTexture", "uv3File", "_AF28Bake"]
    b2 = jl(B2_RULES)["G1_code"]
    code = {}
    ok = True
    for p in SHADERS:
        t = open(p, encoding="utf-8").read()
        body = "\n".join(l.split("//")[0] for l in t.splitlines())
        hits = [f for f in forbid if f in body]
        s = sha(p)
        same = b2["files_sha256"].get(p) == s
        code[rel(p)] = {"sha256": s, "same_as_B2_checked": same, "forbidden_tokens": hits,
                        "screen_derivative_calls": {k: len(re.findall(r"\b%s\s*\(" % k, body)) for k in ("fwidth", "ddx", "ddy")}}
        ok &= (not hits) and same
    cs = open(TOOL_CS, encoding="utf-8-sig").read()
    segs = {
        "B2 の静止の面・材質・冠の部分": cs[cs.index("// ---- 美術の見本03 の作り B2：静止の彫りの面と AS03 の材質"): cs.index("var as03Cg = Arg(a, \"-as03ClawGlaze\")")],
        "組み立ての比べの視点の段": cs[cs.index("// ---- 美術の見本03 の組み立て：利用者だけの比べの図の視点"): cs.index("if (Do(\"fields\"))")],
        "組み立ての冠の画と比べの視点の関数": cs[cs.index("// 美術の見本03 の組み立て：冠だけを ID の色"): cs.index("static bool WaveOnly(string view)")],
    }
    tok = ("SetMatrix", "worldToCameraMatrix", "projectionMatrix", "PaintingCam", "SetTexture", "_DS36", "uv3File")
    tool = {k: [t for t in tok if t in v] for k, v in segs.items()}
    ok &= all(not v for v in tool.values())
    reps = {}
    for v in VARIANTS:
        rr = jl(RENDER + "/%s/as03asm_render_report.json" % v)
        x = {k: rr.get(k) for k in ("heroSdf", "heroUvWarp", "heroUv3File", "protectedUnchanged", "as03Shader", "as03Surf", "as03ClawGlaze", "clawLayout")}
        x["as03Crown"] = rr.get("as03Crown")
        x["changedFiles"] = rr.get("changedFiles")
        reps[v] = x
        ok &= (not x["heroSdf"]) and (not x["heroUvWarp"]) and (not x["heroUv3File"]) and x["protectedUnchanged"] is True
    crowns = {}
    for m in ("OUT", "IN"):
        j = jl(S3 + "/crown/%s/as03_crown.json" % m)
        names = [c[0] for c in j["channels"]]
        crowns[m] = {"channels": j["channels"], "only_geometry_and_glaze_attrs": names == ["position", "normal", "uv5", "uv3"], "bin_sha256": j["sha256"]}
        ok &= crowns[m]["only_geometry_and_glaze_attrs"]
    rmesh = jl(RELIEF.replace(".json", "_report.json"))
    s02 = jl(S2_RULES)["rules"]["G1"]["surface_param"]["now_AS02C"]
    st = t1res["stretch_grad_w"]
    bs = st["same_measure_on_AS02C_base_mesh_same_region"]["non_sliver"]
    surf_ok = st["tri_outside_1_3_to_3x"] <= bs["tri_outside_1_3_to_3x"] and st["area_frac_outside_0p5_to_2x"] <= bs["area_frac_outside_0p5_to_2x"] + 1e-3
    return {"rule_ja": "色・線は原画カメラの投影を使わない（コードの検査）。7 視点＋回り台で引き伸ばし・継ぎ目・平らな面がない",
            "shaders": code, "render_tool": {"path": rel(TOOL_CS), "sha256": sha(TOOL_CS), "projection_tokens_in_checked_parts": tool},
            "render_reports": reps, "crown_meshes": crowns,
            "relief_mesh": {"projection_used": rmesh.get("projection_used"), "reference_obj_read": rmesh.get("reference_obj_read"), "photos_read": rmesh.get("photos_read")},
            "surface_stretch_vs_sample02": {"now_relief_carved_face_non_sliver": {k: st[k] for k in ("triangles", "grad_w_p1_p50_p99", "tri_outside_1_3_to_3x", "area_frac_outside_0p5_to_2x")},
                                            "AS02C_base_same_region_same_measure": bs, "sample02_rules_G1_AS02C_its_own_region": s02, "not_worse": bool(surf_ok),
                                            "slivers_note_ja": "細い三角形（形の良さ < 0.1）は数えない（数は T1 の excluded_slivers に記録）。"},
            "code_pass": bool(ok),
            "note_ja": ("原画のカメラは、原画視点の画を撮る視点、B1 の白の境の位置の数と IN の指の置き場所の制約（形の置き方）、見本02 の爪の置き方 A（射線の上）、"
                        "比べの視点の方位 0 の向きにだけ使った。色・模様は頂点の属性とワールドに固定した光だけで決まる（SCULPT の艶だけが見る位置で動く、釉の性質）。"
                        "7 視点＋波頭の回り台＋回り台の見た目は利用者が並べ図で見る。"),
            "verdict": "pass" if (ok and surf_ok) else "fail"}


# ---------------------------------------------------------------- G2
def g2():
    out, verdicts = {}, {}
    for v in VARIANTS:
        p = RENDER + "/measure/gates_%s/sweep_gates.json" % v
        sg = jl(p)["gates"]
        rows, okv = {}, True
        for k, x in sg.items():
            pv = bool(x["after_claws"] <= x["gate_px"] and x["after_noclaws"] <= x["gate_px"])
            okv &= pv
            rows[k] = {"claws": x["after_claws"], "noclaws": x["after_noclaws"], "gate_px": x["gate_px"], "pass": pv,
                       "sample02_AS02C_A_claws": x["before_claws"], "sample02_AS02C_A_noclaws": x["before_noclaws"], "CP1": x["CP1"], "26修正01": x["26修正01"]}
        out[v] = {"gates": rows, "eval23": R.eval23(RENDER + "/" + v), "source": {"path": rel(p), "sha256": sha(p)}, "all_le_4px": bool(okv)}
        verdicts[v] = "pass" if okv else "fail"
    b2 = {"78": 2.741, "130": 3.5815, "131": 3.4419, "132_s12": 3.6286, "72_s12_p95": [3.7643, 3.5316]}
    return {"rule_ja": "78・130・131（定義どおり）≤ 4 px、132・72 は大きな輪郭で ≤ 4 px", "variants": out, "verdict_by_variant": verdicts,
            "required_ja": "V3（冠 IN）は通ること。V1・V2（冠 OUT）は値を記録する（彫刻のように外へ開く指は原画の空へ出るので、関門を外すのは設計どおり）。",
            "reference_B2_relief_without_crown_noclaws_claws": b2,
            "reference_B1_overlay_prediction": {"IN": [2.741, 3.5815, 3.4419, 3.5576, 3.6577], "OUT": [35.61, 7.152, 23.614, 62.013, 37.755],
                                                "note_ja": "B1 は見本02 の爪なしの色区の画に冠を z バッファで重ねて予測した（主役波は見本02 の keypose の面）。ここは Unity の本当の描画（主役波は B2 の彫りの面）。"},
            "verdict": "pass" if verdicts["V3"] == "pass" else "fail"}


# ---------------------------------------------------------------- S4
def s4(relief):
    j, ch, tri = relief
    pos = ch["position"].astype(np.float64)
    uv3, uv6 = ch["uv3"], ch["uv6"]
    nu, nv, _uv, _uv2, _tri0, gpos = load_gwb(GWB)
    r, c = uv6[:, 0].astype(np.float64), uv6[:, 1].astype(np.float64)
    isint = (np.abs(r - np.round(r)) < 1e-3) & (np.abs(c - np.round(c)) < 1e-3)
    idx = (np.round(r[isint]).astype(np.int64) * nu + np.round(c[isint]).astype(np.int64))
    d = np.linalg.norm(pos[isint] - gpos[idx], axis=1)
    u = uv3[isint, 2]
    back = u < 0.0
    front = ~back
    res = {"vertices_on_original_rows": int(isint.sum()),
           "back_u_lt_0": {"n": int(back.sum()), "max_disp_m": round(float(d[back].max()), 6), "p99_disp_m": round(float(np.percentile(d[back], 99)), 6)},
           "front_u_ge_0": {"n": int(front.sum()), "max_disp_m": round(float(d[front].max()), 4), "note_ja": "前の面の溝は内へ彫った（B2、最大 0.144 m）"}}
    from scipy.spatial import cKDTree
    kd = cKDTree(pos)
    crowns = {}
    for m in ("OUT", "IN"):
        lay = jl(S3 + "/crown/%s/as03_crown_layout.json" % m)
        roots = np.array([h["root_xyz"] for h in lay["hands"]], float)
        _dd, ii = kd.query(roots)
        ur = uv3[ii, 2]
        cj, cch, _ct = load_static(S3 + "/crown/%s/as03_crown.json" % m)
        cp = cch["position"].astype(np.float64)
        sub = cp[:: max(1, len(cp) // 60000)]
        _d2, i2 = kd.query(sub)
        uc = uv3[i2, 2]
        crowns[m] = {"hands": len(roots), "hand_roots_behind_crest_u_lt_-0.3m": int((ur < -0.3).sum()), "hand_root_u_min_m": round(float(ur.min()), 3),
                     "crown_vertices_sampled": int(len(sub)), "crown_vertices_nearest_hero_u_lt_-0.5m_frac": round(float((uc < -0.5).mean()), 4),
                     "crown_vertices_nearest_hero_u_min_m": round(float(uc.min()), 3)}
    s02 = jl(S2_RULES)["rules"]["S4"]
    ok = res["back_u_lt_0"]["max_disp_m"] < 1e-3 and all(x["hand_roots_behind_crest_u_lt_-0.3m"] == 0 for x in crowns.values())
    return {"rule_ja": "背は中ほどがいちばん高く盛り上がり、両側へなだらかに下がる（一つの山）",
            "method_ja": ("組み立てでは背の形を変えていないことを確かめる：B2 の彫りの面の元の行の頂点（行・列が整数）を AS02C の .gwb の同じ頂点と比べ、"
                          "背（u < 0）の頂点の動きが 0（1 mm 未満）であること。B1 の冠の手の根元が頂の線より後ろ（u < −0.3 m）に無いこと（S1：背に指は無い）。"
                          "背の一つの山の測り（見本02 の rules_check.json の S4、AS02C で合格）はそのまま当てはまる。"),
            "relief_vs_AS02C": res, "crown_on_back": crowns,
            "sample02_S4_AS02C": {"verdict": s02["verdict"], "checks": s02["now"]["checks"]},
            "colour_note_ja": ("背の白の境の式は見本02 の hrel > 0.42 から B1 の白の印の hrel > 0.40（＋ゆるい波）へ変わった（色の境だけ。形は同じ）。"
                               "見た目では、見本02 の描画は後ろ 65°・右の側面で背がほぼ海面まで白（クリーム）に見えたが、組み立てでは背の下が藍になる"
                               "（S1：彫刻の背の白は海面から 0.25〜0.40 H まで）。並べ図 asm_3b_views.png で利用者が見る。"),
            "verdict": "pass" if (ok and s02["verdict"] == "pass") else "fail"}


# ---------------------------------------------------------------- C2・C3
def c2_c3():
    lay35 = jl(LAY35)
    kept = {k["user_id"]: k["role"] for k in lay35["as03_asm"]["kept"]}
    lay83 = jl(LAY83)
    fr0 = np.fromfile(os.path.dirname(LAY83) + "/" + lay83["files"]["frames"]["file"], np.float32).reshape(lay83["frames"], lay83["vertices"], 3)
    fr1 = np.fromfile(os.path.dirname(LAY35) + "/" + lay35["files"]["frames"]["file"], np.float32).reshape(lay35["frames"], lay35["vertices"], 3)
    ident = all(np.array_equal(fr0[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]], fr1[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]])
                for c in lay83["claws"] if c["user_id"] in kept)
    rep = jl(CLAW_REPORT)
    placed = [c for c in rep["claws"] if c.get("placed") and "standard" in c and c["user_id"] in kept]
    face_cat = "面から見た IoU"
    c2_fail = {c["user_id"]: [x for x in c.get("standard_fails_ja", []) if not x.startswith(face_cat)] for c in placed}
    c2_fail = {k: v for k, v in c2_fail.items() if v}
    c3_fail = {c["user_id"]: {"iou_painting": c["iou_painting"], "iou_face": c.get("iou_face")} for c in placed
               if c["iou_painting"] < 0.85 or c.get("iou_face", 1.0) < 0.85}
    ip = [c["iou_painting"] for c in placed]
    c2 = {"rule_ja": "どの爪も利用者の模型 claw_low・claw_mid の水準以上（断面の幅と厚みの比、先の細り、表面の滑らかさ＝曲率の跳びを模型と比べる）",
          "claws": len(placed), "by_role": {r: sum(1 for v in kept.values() if v == r) for r in ("FACE_INTERIOR", "NEAR_SEA")},
          "vertices_identical_to_sample02": bool(ident),
          "pass": len(placed) - len(c2_fail), "fail": len(c2_fail), "fail_claws": c2_fail,
          "section_width_over_thickness_p50": float(np.median([c["standard"]["width_over_thickness_mid"] for c in placed])),
          "taper_power_tip30_p50": float(np.median([c["standard"]["taper_power_tip30"] for c in placed])),
          "standard_source": {"path": rel(CLAW_STD), "sha256": sha(CLAW_STD)},
          "note_ja": "見本02 修正の回 1 の爪のうち、面の内（25）と近い海（10）の 35 本。頂点は見本02 とバイトまで同じなので、形の測り（as02_claws_report.json）をそのまま使った。"
                     "波頭の冠の役の 48 本は B1 の冠の指の先になった（冠の測りは T4）。見本02 で C3 に届かなかった claw024・claw045 は冠の役。材質だけ変種と同じ AS03 の釉。",
          "verdict": "pass" if not c2_fail else "fail"}
    c3 = {"rule_ja": "原画カメラから見た各爪の輪郭とマスクの重なり（IoU ≥ 0.85）。100 本を 1 本ずつ 3D に戻して置く",
          "claws": len(placed), "iou_painting_p10_p50_min": [round(float(np.percentile(ip, 10)), 4), round(float(np.percentile(ip, 50)), 4), round(float(min(ip)), 4)],
          "below_085": c3_fail, "pass": len(placed) - len(c3_fail),
          "accounting_100_ja": "100 本 = 置いた 83（面の内 25・近い海 10 は DS34 の爪の層、冠の役 48 は B1 の冠の指の先）＋ 重複 17（見本02 と同じ）",
          "crown_48_ja": "冠の役の 48 本は、OUT では根元の周りに回して面から起こした（原画視点の IoU は測らない。G2 で記録）、IN では見本02 の置き方 A のまま（原画視点の影は見本02 と同じ）。",
          "verdict": "pass" if not c3_fail else "fail"}
    return c2, c3


# ---------------------------------------------------------------- T4
def crown_numbers(spec):
    cr = spec["1_crest_crown"]
    dl = cr["length"]["digit_len_over_H"]["hero"]
    bf = cr["branching"]["branch_start_fraction_of_hand_length"]["value"]
    ang = cr["branching"]["angle_between_digits_same_hand_deg"]["value"]
    out = {}
    for m in ("OUT", "IN"):
        rp = jl(S3 + "/crown/%s/as03_crown_report.json" % m)
        lay = jl(S3 + "/crown/%s/as03_crown_layout.json" % m)
        cnt = rp["measure"]["counts"]
        ft, hd = cnt["fingertips_total"], cnt["hands_total"]
        rngf, rngh = cnt["S1_target"]["fingertips"]["range"], cnt["S1_target"]["hands"]["range"]
        digits = [f for f in lay["fingers"] if f["kind"] == 1]
        users = [f for f in lay["fingers"] if f["kind"] == 2]   # 配置の表では利用者の爪は user_claws の別の表（fingers の種類 2 は無い）
        dlen = [f["length_m"] for f in digits]
        roles = {c["id"]: c for c in jl(S3 + "/study/claw_roles.json")["claws"]}
        ulen = [roles[u["id"]]["length_3d_m"] for u in lay["user_claws"] if u["id"] in roles]
        p50 = float(np.median(dlen))
        # 枝分かれ：手あたりの指（全部の手 = 指の先 ÷ 手）、手続きの手の分かれる所、同じ手の指どうしの角
        by_hand = {}
        for f in digits:   # 手続きの手の指（利用者の爪の房の爪どうしの角は見本02 の置き方のまま）
            by_hand.setdefault(f["hand"], []).append(f)
        dph = [len(v) for v in by_hand.values()]
        bfr = [h["branch_frac"] for h in lay["hands"] if "branch_frac" in h]
        angs = []
        for v in by_hand.values():
            dirs = []
            for f in v:
                d = np.asarray(f["tip_xyz"], float) - np.asarray(f["root"], float)
                n = np.linalg.norm(d)
                if n > 1e-6:
                    dirs.append(d / n)
            for i in range(len(dirs)):
                for k in range(i + 1, len(dirs)):
                    angs.append(math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(dirs[i], dirs[k])))))))
        dph_mean = ft / float(hd)
        checks = {
            "fingertips_in_S1_range": {"value": ft, "range": rngf, "pass": rngf[0] <= ft <= rngf[1]},
            "hands_in_S1_range": {"value": hd, "range": rngh, "pass": rngh[0] <= hd <= rngh[1]},
            "digit_length_p50_in_S1_p25_p75_m": {"value": round(p50, 3), "range": [dl["p25"], dl["p75"]], "pass": dl["p25"] <= p50 <= dl["p75"],
                                                  "ours_p10_p90": [round(float(np.percentile(dlen, 10)), 3), round(float(np.percentile(dlen, 90)), 3)],
                                                  "S1_p10_p90": [dl["p10"], dl["p90"]], "n_procedural_digits": len(dlen),
                                                  "B1_report_p50_m": rp["measure"]["digit_len_m"]["ours"]["p50"],
                                                  "definition_ja": "配置の表（as03_crown_layout.json）の指の管の背骨の長さ。B1 の記録（as03_crown_report.json）の p50 は B1 の別の定義の長さ。どちらも S1 の範囲の中"},
            "digits_per_hand_mean_in_S1_1p5_to_5": {"value": round(dph_mean, 3), "range": [1.5, 5.0], "pass": 1.5 <= dph_mean <= 5.0,
                                                    "note_ja": "S1：スキャンの中央値 1.5（細い指が欠けるので下限）、写真 3（2〜5）"},
            "branch_start_fraction_p50_in_S1_p25_p75": {"value": round(float(np.median(bfr)), 3) if bfr else None, "range": [bf["p25"], bf["p75"]],
                                                        "pass": bool(bfr) and bf["p25"] <= float(np.median(bfr)) <= bf["p75"], "n_hands": len(bfr)},
            "angle_between_digits_same_hand_p50_in_S1_p25_p75_deg": {"value": round(float(np.median(angs)), 1) if angs else None, "range": [ang["p25"], ang["p75"]],
                                                                    "pass": bool(angs) and ang["p25"] <= float(np.median(angs)) <= ang["p75"], "n_pairs": len(angs)},
        }
        out[m] = {"checks": checks, "pass_all": all(x["pass"] for x in checks.values()),
                  "record": {"hands_with_2plus_fingertips_frac": round(float(np.mean([x >= 2 for x in dph])), 3),
                             "fingertips_per_m_rim": cnt["fingertips_per_m"], "rim_length_m": cnt["rim_length_m"],
                             "user_claw_length_p50_m（S2 の claw_roles の 3D の長さ、冠の役 48 本）": round(float(np.median(ulen)), 3) if ulen else None,
                             "layout_hands_listed": len(lay["hands"]),
                             "note_hands_ja": "手の数は B1 の記録（as03_crown_report.json）の hands_total。配置の表の hands の数と 1 違う場合は、袖を外した利用者の爪の房（爪は残る）を記録は数えるため（B1 の記録の第 2 節の 9）。",
                             "digit_overall_below_horizontal_p50_deg": rp["measure"]["digit_overall_below_horizontal_deg"]["ours"]["p50"],
                             "digit_tip_below_horizontal_p50_deg": rp["measure"]["digit_tip_below_horizontal_deg"]["ours"]["p50"],
                             "frac_tips_down": rp["measure"]["frac_tips_down"], "frac_forward": rp["measure"]["frac_forward"],
                             "tips_shape": rp["measure"]["tips"], "root_seam_normal_jump_p99_deg": rp["checks"]["root_seam_normal_jump_deg"]["p99"]},
                  "source": {"report": rel(S3 + "/crown/%s/as03_crown_report.json" % m), "layout_sha256": sha(S3 + "/crown/%s/as03_crown_layout.json" % m)}}
    return out


def tongues(spec, relief):
    pr = jl(WM_PARAMS)
    t = spec["2_white_and_drip_edge"]["tongues_small_wave"]
    H = spec["scale"]["H_hero_m"]["value"]
    sp, spu = t["spacing_over_H"]["value"] * H, 0.03 * H
    rows = pr["rows"][66:237]   # 舌を置いた範囲（crown_whitemask.py の edge_length_m = L[236] − L[66]）
    Ls = np.array([r["L_along_edge_m"] for r in rows], float)
    pf = np.array([r["mode"] == "painting_face_start" for r in rows])
    dL = np.diff(Ls)
    vis_len = float(dL[pf[:-1] & pf[1:]].sum())
    edge = float(pr["stats"]["edge_length_m"])
    hid_len = edge - vis_len
    tg = pr["tongues"]
    n_s1 = sum(1 for x in tg if x["regime"].startswith("S1"))
    n_all = len(tg)
    rng_all = [edge / (sp + spu), edge / (sp - spu)]
    rng_hid = [hid_len / (sp + spu), hid_len / (sp - spu)]
    # 彫りの面に舌があるか：細かい帯（行 ×4・列 ×2）の舌の番号を、彫りの面の同じ（行, 列）の頂点の whiteSD と突き合わせる
    j, ch, _tri = relief
    uv6, uv5 = ch["uv6"], ch["uv5"]
    band = np.fromfile(WM_BAND, np.float32).reshape(-1, 11)   # r, c, x, y, z, u, w, white, sd_m, region, tongue_id（README の「× 12」は名前の数が 11）
    bkey = {}
    br, bc, breg, btid = band[:, 0], band[:, 1], band[:, 9], band[:, 10]
    sel = (breg == 3) & (btid >= 0)
    for rr, cc, tid in zip(br[sel], bc[sel], btid[sel]):
        bkey[(int(round(rr * 4)), int(round(cc * 2)))] = int(tid)
    present, inside = {}, {}
    for (rr, cc), wsd in zip(zip(np.round(uv6[:, 0] * 4).astype(np.int64), np.round(uv6[:, 1] * 2).astype(np.int64)), uv5[:, 2]):
        tid = bkey.get((int(rr), int(cc)))
        if tid is None:
            continue
        inside[tid] = inside.get(tid, 0) + 1
        if wsd > 0:
            present[tid] = present.get(tid, 0) + 1
    tids = {int(x["id"]) for x in tg}
    present_ids = sorted(k for k, v in present.items() if v >= 1)
    checks = {"tongues_total_in_S1_count_range_for_edge": {"value": n_all, "edge_length_m": round(edge, 2), "range": [round(x, 1) for x in rng_all],
                                                           "pass": rng_all[0] <= n_all <= rng_all[1]},
              "S1_size_tongues_in_S1_count_range_for_hidden_edge": {"value": n_s1, "edge_length_m": round(hid_len, 2), "range": [round(x, 1) for x in rng_hid],
                                                                     "pass": rng_hid[0] <= n_s1 <= rng_hid[1]},
              "tongues_present_on_relief_surface": {"value": len(present_ids), "of": len(tids), "pass": len(present_ids) == len(tids),
                                                    "missing": sorted(tids - set(present_ids))}}
    return {"checks": checks, "pass_all": all(x["pass"] for x in checks.values()),
            "S1": {"spacing_m": round(sp, 3), "spacing_unc_m": round(spu, 3), "width_m": round(t["width_over_H"]["value"] * H, 3), "length_m": round(t["length_over_H"]["value"] * H, 3)},
            "painting_size_tongues": n_all - n_s1, "painting_face_edge_length_m": round(vis_len, 2),
            "painting_size_tongue_spacing_note_ja": "原画の舌（S2：藍の頭の間隔 p50 約 1.0 m）は原画の藍の面がある行（決め方 painting_face_start）の境に置いた。",
            "note_ja": ("S1 の舌の数の範囲 = 境の長さ ÷ 間隔（2.49 ± 0.62 m、0.12 ± 0.03 H）。原画の視点で見える所の 11 本は原画の舌の大きさ（S2、間隔 約 1 m）"
                        "なので、全体の数（39）は S1 の範囲で、S1 の大きさの舌（28）は見えない所の境の長さで確かめる。S1 では丸い舌は前の小波の縁に見え、"
                        "主の面の垂れは立体の指（T4 の冠）。ここは B1 の白の印（v2）の舌が、彫りの面（B2）の白に入っているか（whiteSD > 0 の頂点）も確かめる。"),
            "source": {"params": rel(WM_PARAMS), "sha256": sha(WM_PARAMS), "band_sha256": sha(WM_BAND)}}


CROWN_RGB = (13, 55, 255)   # AS03AsmRender の冠の ID の色 (0.25, 0.5, 1) が書き出しの 8 ビットでこうなる（_IdColor は色の値なので線形へ直る）


def crown_px(a):
    return (np.abs(a[..., :3].astype(np.int16) - np.array(CROWN_RGB, np.int16)[None, None, :]).max(-1) <= 3)


def crown_visibility():
    import cv2
    res, okv = {}, {}
    for v in VARIANTS:
        d = RENDER + "/" + v
        frac = {}
        files = [("views/" + n, d + "/views/%s_t120_claws_crownmask.png" % n) for n in NON_PAINTING_VIEWS]
        files += [("crest/az%03d" % a, d + "/crest/t120_az%03d_claws_crownmask.png" % a) for a in range(0, 360, 45)]
        files += [("tt/az%03d" % a, d + "/tt/t120_az%03d_claws_crownmask.png" % a) for a in range(0, 360, 30)]
        prot = {}
        share = {}
        ids = RENDER + "/%s_ids/diag" % ("V3" if VARIANTS[v]["crown"] == "IN" else "V1")   # 主役波の印（冠 OUT は V1 と V2 で形が同じ）
        for key, p in files:
            a = np.asarray(Image.open(p).convert("RGB"))
            m = crown_px(a)
            frac[key] = round(float(m.sum()) / FRAME_PX, 5)
            hp = {"views": ids + "/%s_t120_hero_claws1.png", "crest": ids + "/crest_t120_%s_hero_claws1.png", "tt": ids + "/tt_t120_%s_hero_claws1.png"}[key.split("/")[0]] % key.split("/")[1]
            if os.path.isfile(hp):
                hm = np.asarray(Image.open(hp).convert("RGBA"))[..., 3] == 128
                share[key] = round(float(m.sum()) / max(float(m.sum() + hm.sum()), 1.0), 4)
            if key.startswith("crest/"):
                # 頂の輪郭から出る指（記録）：主役波＋冠の影 U を、半径 12 画素（指の太さの見当 0.4 m × 50 px/m の約 1.2 倍）の円で開き、
                # 開きで消えた所のうち冠の画素が過半の連結成分（≥ 40 画素）を数える
                bg = (a.astype(np.int32).sum(axis=2) == 0)
                Um = (~bg).astype(np.uint8)
                ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
                op = cv2.morphologyEx(Um, cv2.MORPH_OPEN, ker)
                resid = (Um > 0) & (op == 0)
                n, lab, st, _c = cv2.connectedComponentsWithStats(resid.astype(np.uint8), 8)
                cnt = 0
                for i in range(1, n):
                    if st[i, cv2.CC_STAT_AREA] < 40:
                        continue
                    comp = lab == i
                    if m[comp].mean() > 0.5:
                        cnt += 1
                prot[key] = cnt
        pv = d + "/views/painting_t120_claws_crownmask.png"
        po = d + "/views/painting_t120_claws_crownmask_off.png"
        a = np.asarray(Image.open(pv).convert("RGB"))
        b = np.asarray(Image.open(po).convert("RGB"))
        mm = lambda x: int(crown_px(x).sum())
        mn = min(frac, key=frac.get)
        okv[v] = frac[mn] > VIS_MIN
        mns = min(share, key=share.get) if share else None
        res[v] = {"crown_frac_by_view": frac, "min": {"view": mn, "frac": frac[mn]}, "pass": bool(okv[v]),
                  "views_below_0p5pct": {k: x for k, x in frac.items() if x <= VIS_MIN},
                  "record_crown_share_of_wave_silhouette": {"by_view": share, "min": {"view": mns, "share": share.get(mns)} if mns else None,
                                                           "note_ja": "記録だけ：冠の画素 ÷（冠＋見える主役波の画素）。主役波の印は同じカメラの ids の描画（%s_ids/diag の hero_claws1、アルファ 128）。" % ("V3" if VARIANTS[v]["crown"] == "IN" else "V1")},
                  "painting_view_crown_frac": round(mm(a) / FRAME_PX, 5), "false_positive_px_with_crown_hidden": mm(b),
                  "crest_silhouette_protrusions_record": prot}
    return res, okv


def t4(spec, relief):
    cn = crown_numbers(spec)
    tg = tongues(spec, relief)
    vis, okv = crown_visibility()
    verdict = {}
    for v, x in VARIANTS.items():
        verdict[v] = "pass" if (cn[x["crown"]]["pass_all"] and tg["pass_all"] and okv[v]) else "fail"
    return {"rule_ja": "波頭の指の数と長さ・枝分かれ・垂れる縁の舌の数を彫刻から測った値と比べる。全視点で波頭が平らな面だけにならない",
            "rule_detail_ja": ("（1）冠の指の先 83〜111・手 33〜59（S1 を主役波の頂の縁の長さへ当てた範囲）、（2）手続きの指の長さの中央値が S1 の p25〜p75（0.616〜1.131 m）、"
                               "（3）枝分かれ：手あたりの指の先 1.5〜5、分かれる所の中央値が S1 の p25〜p75（手の長さの 0.351〜0.512）、同じ手の指どうしの角の中央値が "
                               "S1 の p25〜p75（24.3〜67.2°）、（4）垂れる縁の舌の数が S1 の範囲で、彫りの面の白に入っている、（5）冠が原画視点のほかのどの視点（7 視点の 6・"
                               "波頭の回り台 8 方位・回り台 12 方位）でも枠の 0.5% より多く見える（冠の画の (1,0,1) の画素）。範囲の取り方は組み立ての担当の既定（S1 の測った"
                               "分布の四分位、数は S1 の範囲）。進行役が変えてよい。"),
            "crown_numbers": cn, "drip_tongues": tg, "crown_visibility": vis, "verdict_by_variant": verdict,
            "verdict": "pass" if all(x == "pass" for x in verdict.values()) else "fail"}


# ---------------------------------------------------------------- T1
ATTR02 = S2 + "/fix01/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin"


def stretch_stats(pos, tri, wv, carved):
    e1 = pos[tri[:, 1]] - pos[tri[:, 0]]
    e2 = pos[tri[:, 2]] - pos[tri[:, 0]]
    e3 = pos[tri[:, 2]] - pos[tri[:, 1]]
    nrm = np.cross(e1, e2)
    A2 = np.linalg.norm(nrm, axis=1)
    L2 = (e1 ** 2).sum(1) + (e2 ** 2).sum(1) + (e3 ** 2).sum(1)
    qual = 2.0 * math.sqrt(3.0) * A2 / np.maximum(L2, 1e-18)
    df1 = (wv[tri[:, 1]] - wv[tri[:, 0]])[:, None]
    df2 = (wv[tri[:, 2]] - wv[tri[:, 0]])[:, None]
    grad = (df1 * np.cross(e2, nrm) + df2 * np.cross(nrm, e1)) / np.maximum((A2 ** 2)[:, None], 1e-18)
    gwa = np.linalg.norm(grad, axis=1)
    sel_all = carved[tri].all(axis=1) & (A2 > 1e-9)
    slv = sel_all & (qual < 0.1)
    out = []
    for sel in (sel_all, sel_all & ~slv):
        gw = gwa[sel]
        ta = A2[sel] / 2.0
        out.append({"triangles": int(sel.sum()), "grad_w_p1_p50_p99": pct(gw, [1, 50, 99]),
                    "tri_outside_1_3_to_3x": int(((gw < 1 / 3.0) | (gw > 3.0)).sum()),
                    "area_frac_outside_0p5_to_2x": round(float(ta[(gw < 0.5) | (gw > 2.0)].sum() / ta.sum()), 5)})
    sl = {"triangles": int(slv.sum()), "area_m2": round(float(A2[slv].sum() / 2.0), 4),
          "area_frac": round(float(A2[slv].sum() / max(A2[sel_all].sum(), 1e-12)), 6),
          "tri_outside_1_3_to_3x": int(((gwa[slv] < 1 / 3.0) | (gwa[slv] > 3.0)).sum())}
    return out[0], out[1], sl


def t1(relief, spec):
    j, ch, tri = relief
    pos = ch["position"].astype(np.float64)
    uv3, uv4, uv5, uv6 = ch["uv3"], ch["uv4"], ch["uv5"], ch["uv6"]
    gq, Lq = uv4[:, 0].astype(np.float64), uv4[:, 2].astype(np.float64)
    lam = uv6[:, 2].astype(np.float64)
    fade, wsd = uv5[:, 3], uv5[:, 2]
    y = pos[:, 1]
    carved = (fade > 0.5) & (wsd < 0) & (gq > 1e-4) & (lam > 0.05)
    P0 = np.exp2(-np.round(Lq))
    spacing = P0 / np.maximum(gq, 1e-6)
    ratio = spacing / np.maximum(lam, 1e-6)
    # 頂点の面積（隣の三角形の 1/3）
    e1 = pos[tri[:, 1]] - pos[tri[:, 0]]
    e2 = pos[tri[:, 2]] - pos[tri[:, 0]]
    nrm = np.cross(e1, e2)
    A2 = np.linalg.norm(nrm, axis=1)
    va = np.zeros(len(pos))
    for k in range(3):
        np.add.at(va, tri[:, k], A2 / 6.0)
    H0 = float(spec["scale"]["H_hero_m"]["value"])
    bands = {"0.65-0.90H（冠の下）": (0.65, 0.90), "0.35-0.65H（中ほど）": (0.35, 0.65), "0.10-0.35H（下の面）": (0.10, 0.35)}
    by = {}
    for k, (a, b) in bands.items():
        s = carved & (y >= a * H0) & (y < b * H0)
        if s.sum() < 50:
            continue
        w = va[s]
        rr = ratio[s]
        mu = float(np.average(rr, weights=w))
        cv = float(np.sqrt(np.average((rr - mu) ** 2, weights=w)) / mu)
        by[k] = {"vertices": int(s.sum()), "spacing_m_p50": pct(spacing[s], [50], w)[0], "lambda_m_p50": pct(lam[s], [50], w)[0],
                 "ratio_mean": round(mu, 4), "ratio_cv": round(cv, 4), "ratio_p5_p50_p95": pct(rr, [5, 50, 95], w)}
    w = va[carved]
    rr = ratio[carved]
    lo, hi = 1 / math.sqrt(2) * 0.9, math.sqrt(2) * 1.1
    frac_in = float(w[(rr >= lo) & (rr <= hi)].sum() / w.sum())
    # 引き伸ばし：三角形ごとの |∇w|（w は面の座標 m。理想 1）。形の良さ q = 4√3·面積 ÷ 辺の 2 乗の和（正三角形 1）が 0.1 未満の細い三角形
    # （唇の先の折れ目、列 198〜200 に並ぶ。面積 0.0001 m² ほどで画素より小さい）は |∇w| の数値が暴れるので判定から外し、数を記録する
    wv = uv3[:, 3].astype(np.float64)
    stretch_all, stretch, sl = stretch_stats(pos, tri, wv, carved)
    nu, nv, _uv, _uv2, tri0, gpos = load_gwb(GWB)
    r6, c6 = uv6[:, 0].astype(np.float64), uv6[:, 1].astype(np.float64)
    isint = (np.abs(r6 - np.round(r6)) < 1e-3) & (np.abs(c6 - np.round(c6)) < 1e-3)
    carved0 = np.zeros(nu * nv, bool)
    carved0[(np.round(r6[isint]) * nu + np.round(c6[isint])).astype(np.int64)] = carved[isint]
    w0 = np.fromfile(ATTR02, np.float32).reshape(-1, 12)[:, 3].astype(np.float64)
    base_all, base, base_sl = stretch_stats(gpos, tri0, w0, carved0)
    rm = jl(RELIEF.replace(".json", "_report.json"))
    s1 = {"0.75H": 0.73, "0.50H": 0.93, "0.25H": 1.16}
    gaps = {k: {"gap_mean_m": v["gap_mean_m"], "gap_p50_m": v["gap_p50_m"], "design_m": v["target_m"], "S1_photo_m": s1.get(k),
                "mean_over_design": round(v["gap_mean_m"] / v["target_m"], 3)} for k, v in rm["spacing_front_face"].items()}
    gaps_ok = all(0.85 <= g["mean_over_design"] <= 1.15 for g in gaps.values())
    ok_ratio = frac_in >= 0.95
    ok_stretch = stretch["tri_outside_1_3_to_3x"] == 0 and stretch["area_frac_outside_0p5_to_2x"] <= 0.002
    return {"rule_ja": "歪まず、引き伸ばされない。原画とも参照モデルとも合う（模様の間隔の場所によるばらつき、引き伸ばしの比）",
            "rule_detail_ja": ("（1）溝の線の間隔 ÷ 設計の周期 λ(y)（λ は S1 の写真の周期を通る：冠の下 0.035 H・中ほど 0.045 H・下 0.056 H）が、彫った面の面積の 95% 以上で "
                               "0.64〜1.56（Y 字で分かれる √2 の幅 ±10%）、（2）彫った面で数えた溝の中心の間隔（B2 の測り）の平均が設計の ±15%、"
                               "（3）面の座標 w の |∇w|（伸び）が 1/3〜3 倍を外れる三角形 0、0.5〜2 倍を外れる面積 ≤ 0.2%。範囲は組み立ての担当の既定（進行役が変えてよい）。"),
            "spacing_ratio": {"carved_vertices": int(carved.sum()), "frac_area_in_0.64_1.56": round(frac_in, 4), "p1_p5_p50_p95_p99": pct(rr, [1, 5, 50, 95, 99], w),
                              "by_height": by, "pass": bool(ok_ratio)},
            "groove_gaps_measured_B2": {"bands": gaps, "pass": bool(gaps_ok), "fork_zones_front_face": rm.get("fork_zones_front_face")},
            "stretch_grad_w": dict(stretch, **{"pass": bool(ok_stretch), "excluded_slivers_q_lt_0.1": sl, "all_triangles_incl_slivers": stretch_all,
                                               "same_measure_on_AS02C_base_mesh_same_region": {"non_sliver": base, "all": base_all, "slivers": base_sl},
                                               "note_ja": "AS02C の元の格子（行を細かくする前）でも同じ所・同じ測りで数えた（like-for-like）。細い三角形は元の格子にもある（唇の先の折れ目）。"}),
            "painting_note_ja": "原画の中くらいの青の帯の間隔は約 1 m（調べ S2）。彫刻の写真は 0.73／0.93／1.16 m（S1）。",
            "verdict": "pass" if (ok_ratio and gaps_ok and ok_stretch) else "fail"}


def main():
    t0 = time.time()
    spec = jl(SPEC)
    relief = load_static(RELIEF)
    res = {"schema": "GreatWave.AS03.rules_check/1", "created_local": time.strftime("%Y-%m-%dT%H:%M"),
           "noteJa": ("美術の見本03 を出す前の、美術の要求書の測る規則の自動の確かめ。美術が届いたかは利用者が決める（Q29・Q30）。目で見た審査は閉じる条件にしない。"
                      "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止だけ。"),
           "sample": {"variants": {"V1": "冠 OUT（彫刻のように外へ開く）＋ SCULPT（彫刻の艶と陰）", "V2": "冠 OUT ＋ FLAT（浮世絵の平らな色）",
                                   "V3": "冠 IN（原画視点の影を原画の白の冠・爪の区域に収める）＋ SCULPT"},
                      "common": "主役波 = B2 の彫りの面 hero_relief_b1v2c（K*′ AS02C、白の印 v2）、爪 = 見本02 修正の回 1 の面の内 25・近い海 10（変種と同じ AS03 の釉）、海 = PL30",
                      "render": {v: rel(RENDER + "/" + v) for v in VARIANTS}},
           "inputs_sha256": {rel(p): sha(p) for p in (RELIEF, RELIEF.replace(".json", ".bin"), GWB, SPEC, WM_JSON, WM_PARAMS, WM_BAND, CLAW_REPORT, LAY35, LAY83,
                                                       S3 + "/crown/OUT/as03_crown.bin", S3 + "/crown/IN/as03_crown.bin",
                                                       S3 + "/crown/OUT/as03_crown_layout.json", S3 + "/crown/IN/as03_crown_layout.json", TOOL_CS) + tuple(SHADERS)},
           "rules": {}}
    t1r = t1(relief, spec)
    res["rules"]["G1"] = g1(t1r)
    res["rules"]["G2"] = g2()
    res["rules"]["S4"] = s4(relief)
    c2, c3 = c2_c3()
    res["rules"]["C2"] = c2
    res["rules"]["C3"] = c3
    res["rules"]["T4"] = t4(spec, relief)
    res["rules"]["T1"] = t1r
    v = {k: res["rules"][k]["verdict"] for k in ("G1", "G2", "S4", "C2", "C3", "T4", "T1")}
    byv = {}
    for name in VARIANTS:
        byv[name] = {"G1": v["G1"], "G2": res["rules"]["G2"]["verdict_by_variant"][name], "S4": v["S4"], "C2": v["C2"], "C3": v["C3"],
                     "T4": res["rules"]["T4"]["verdict_by_variant"][name], "T1": v["T1"]}
    bad = [k for k, x in v.items() if x != "pass"]
    res["summary"] = {"verdicts": v, "by_variant": byv, "all_pass": not bad,
                      "G2_note_ja": "G2 は V3 が通れば合格（V1・V2 の冠 OUT は原画の空へ指が出るので記録だけ）。",
                      "deliverable_by_rule_ja": ("要求書の「通らない見本は出さない」により、%s が通らないうちは見本として出せない。出すかどうかは進行役が決める。" % "・".join(bad))
                      if bad else "測る規則はすべて通った（G2 は V3 で）。美術の判定は利用者。"}
    res["elapsed_s"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(res["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
