# -*- coding: utf-8 -*-
"""美術の見本04 の組み立て（Q32）：美術の要求書（Docs/Design/Art_Requirements_ja.md）の測る規則を、組み立てた見本04（主役波 K*′ AS04 ＋
左端の別の青い波 wave4 ＋ AS04 Flat Smooth ＋ 爪 35 本）の Unity の描画（asm4_render.sh、Build/Polish/sample04/assemble/render/S04）と
部品のファイルで自動で確かめ、Unity/Build/Polish/sample04/rules_check.json に書く（読み取りのみ。形・材質は変えない）。

  G1   原画カメラの投影を使わない：AS04 のシェーダー 2 つ（調べ M の版と SHA-256 が同じ＋禁じた語）、描画の道具 AS03AsmRender（見本03 の確かめた版と同じ）、
       描画の記録（焼き込みのパスが空・守るファイル不変・冠なし）、静止のメッシュのチャンネル。面の座標 u・w の伸び（三角形ごとの |∇u|・|∇w|）。
  G2   原画視点の関門を、主役波と wave4 を合わせた輪郭で：78・130・131 ≤ 4 px、132 σ12・72 σ12 p95 ≤ 4 px（sweep_gates.json）。評価器 23 は記録。
  S4   背は一つの山：合わせた頂の高さ H(c)（主役波の行＋wave4）、後ろからの輪郭（b65・b90・b115、合わせた形）、背の等高線（形づくりの back_measure）。
  S8   出っ張り：利用者の黄色の線の中の原画の射線の最初の当たりの、内の面の線からの距離 p95 ≤ 0.15 m（形づくりの bulge_metric、測り直す）。
  S9   左の白は低い・④ の輪郭は wave4 が作る：原画視点の輪郭の画素ごとに、どの物（主役波・wave4・近い海）が作るか（numpy の z バッファ、表示の 2 倍の細かさ）。
       白の頂の高さ（c ごと、見本03 の形と比べ）、白の最も左の c。Unity の描画の差（wave4 あり・なし）でも確かめる。
  S10  峰に沿う長さ：高さの帯ごとの c の幅（主役波だけ・wave4 と合わせた形）を見本03（AS02C）と比べる。
  S11  三つの層：形の段（唇の前の縁・頂の高さ・原画のカメラからの距離。形づくりの layers）と、側面 2・真上・回り台 12 の numpy の画で、
       層どうしが遮る縁（線として描かれる深さの跳び）で分かれるか、前の面が一続きにつながるか。
  T4   冠のメッシュが無い、面に凹凸が無い：静止のメッシュの点の、滑らかな土台（.gwb の行の Catmull–Rom、surf_relief と同じ式）からのずれの最大。
       見本03 の彫りの面と同じ測りで比べる。シェーダーに光・艶・AO の語が無い。
  C2・C3  面の内の爪 25 本（と近い海 10 本）：置き直しが原画のカメラを中心とする相似（倍率だけ）であること → 形の比（C2）は見本02 の測りのまま、
       原画視点の影（C3）は画素まで同じ。原画視点で主役波・wave4 に隠れる割合、面からの浮き・沈み（記録）。
美術が届いたかは利用者が決める（Q29・Q30）。ここは「測れる規則を通るか」だけ。目で見た審査は閉じる条件にしない。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as04/asm4_rules.py
"""
import json
import os
import re
import sys
import time

import cv2
import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import asm4_common as A  # noqa: E402
import shape_common as SC  # noqa: E402
import shape_eval as SE  # noqa: E402

REPO = A.REPO
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_asm_rules as R2  # noqa: E402
import back_common as BC  # noqa: E402

RENDER = A.ASM + "/render/" + A.RTAG
HERO_ONLY = A.ASM + "/render/" + A.RTAG + "H" if A.FIX else A.P4 + "/shape/render/A4"
GATES = A.ASM + "/render/measure/gates_" + A.RTAG + "/sweep_gates.json"
OUT = A.P4 + "/rules_check.json"
SH = REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders"
SHADERS = [SH + "/AS04Common.cginc", SH + "/AS04_Flat_Smooth_Keypose.shader"]
SHADERS_STUDY_M = list(SHADERS)
if A.FIX:
    # 直しの回 1：白い点だけを直した写し（AS04F）。調べ M の版から変えた所は白い点の関数・その値・名前だけ（g1 で差を確かめる）
    SHADERS = [SH + "/AS04FCommon.cginc", SH + "/AS04F_Flat_Smooth_Keypose.shader"]
TOOL_CS = REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs"
MAT_RUN = A.P4 + "/mat/run.json"
S3_RULES = REPO + "/Docs/Evidence/ArtSample03/rules_check.json"
S2_CLAW_REPORT = A.P + "/sample02/fix01/assemble/claws/mesh/as02_claws_report.json"
BACK_MEASURE = (A.P4 + "/" + A.FIX + "/shape/final/eval_AS04F_back_measure.json") if A.FIX else A.P4 + "/shape/final/eval_AS04_back_measure.json"
S11_VIEWS = ["side_left", "side_right", "top"] + ["tt%d" % a for a in range(0, 360, 30)]
HERO_LABS = (1, 2, 3, 4, 8)


def T():
    return time.strftime("%H:%M:%S")


# ---------------------------------------------------------------- G1
def tri_grad(pos, tri, f):
    p0, p1, p2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = f[tri[:, 1]] - f[tri[:, 0]], f[tri[:, 2]] - f[tri[:, 0]]
    a, b, c = (e1 * e1).sum(1), (e1 * e2).sum(1), (e2 * e2).sum(1)
    det = a * c - b * b
    ok = det > 1e-14
    det = np.where(ok, det, 1.0)
    x = (c * d1 - b * d2) / det
    y = (a * d2 - b * d1) / det
    g = x[:, None] * e1 + y[:, None] * e2
    area = 0.5 * np.sqrt(np.maximum(det, 0))
    L2 = a + c + ((e2 - e1) ** 2).sum(1)
    q = 4 * np.sqrt(3) * area / np.maximum(L2, 1e-12)
    return np.linalg.norm(g, axis=1), area, q, ok


PATTERN_WSD = 1.4   # 模様（帯・白い点・水色の縁）を描く所：whiteSD < 水色の奥の 0.3 m ＋ 水色の幅の最大 1.1 m（as04_flat_smooth_params.txt）


def stretch_masks(path, part=None):
    ch, tri, _ = A.read_static(path)
    pos = ch["position"].astype(np.float64)
    if part == "hero":
        tri = tri[tri[:, 0] < A.N_HERO]
    elif part == "wave4":
        tri = tri[tri[:, 0] >= A.N_HERO]
    u, w = ch["uv3"][:, 2].astype(np.float64), ch["uv3"][:, 3].astype(np.float64)
    front = u[tri].mean(1) >= 0.0
    if part != "wave4":
        F = ch["uv3"][:, 0].astype(np.float64)
        fm = F[tri].mean(1)
        front &= (fm >= 0.0) & (fm <= 4.0)
    pat = ch["uv5"][:, 2].astype(np.float64)[tri].max(1) < PATTERN_WSD
    gu, ar, q, ok = tri_grad(pos, tri, u)
    gw, _, _, _ = tri_grad(pos, tri, w)
    sel = front & ok & (q >= 0.1)
    return dict(tri=tri, pos=pos, sel=sel, pat=pat, gu=gu, gw=gw, ar=ar, nsliver=int((front & ok & (q < 0.1)).sum()))


def stretch(path, part=None):
    m = stretch_masks(path, part)
    out = {"excluded_slivers_q_lt_0.1": m["nsliver"]}
    for reg, s in (("patterned_face", m["sel"] & m["pat"]), ("white_face", m["sel"] & ~m["pat"]), ("all_front", m["sel"])):
        o = {"triangles": int(s.sum())}
        if s.any():
            for k in ("gu", "gw"):
                gg = m[k][s]; aa = m["ar"][s]
                bad = (gg < 1 / 3) | (gg > 3)
                o[k + "_p10_p50_p90"] = [A.rnd(x) for x in np.percentile(gg, (10, 50, 90))]
                o[k + "_tri_outside_1_3_to_3x"] = int(bad.sum())
                o[k + "_area_frac_outside_1_3_to_3x"] = A.rnd(float(aa[bad].sum() / aa.sum()), 5)
        out[reg] = o
    return out


def stretch_visible():
    """引き伸ばしの三角形（前の面、|∇u| か |∇w| が 1/3〜3 倍の外）が各視点で何画素見えるか（記録。numpy の z バッファ）。"""
    m = stretch_masks(A.UNION, "hero")
    tris, lab, _ = A.scene("S04")
    lab2 = lab.copy()
    L0 = lab2[:len(m["tri"])]
    bw = m["sel"] & ((m["gw"] < 1 / 3) | (m["gw"] > 3))
    bu = m["sel"] & ((m["gu"] < 1 / 3) | (m["gu"] > 3))
    L0[bu & m["pat"]] = 11; L0[bu & ~m["pat"]] = 12; L0[bw & ~m["pat"]] = 9; L0[bw & m["pat"]] = 10
    out = {}
    for v in ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"] + ["tt%d" % a for a in range(0, 360, 30)]:
        cam = A.painting_cam(1) if v == "painting" else A.view_cam(v)
        _, D, L = A.raster(cam, tris, lab2)
        out[v] = {"w_white": int((L == 9).sum()), "w_patterned": int((L == 10).sum()), "u_patterned": int((L == 11).sum()), "u_white": int((L == 12).sum())}
        if v in ("painting", "tt330"):
            np.save(A.MEAS + "/g1_stretch_labels_%s.npy" % v, L.astype(np.int8))
    return out


def g1():
    forbid = ["PaintingCam", "_PaintCam", "_DS36", "ComputeScreenPos", "ComputeGrabScreenPos", "unity_CameraProjection", "unity_CameraInvProjection",
              "UNITY_MATRIX_P", "UNITY_MATRIX_VP", "unity_MatrixVP", "_S01BDesign", "tex2D", "sampler2D", "Texture2D", "_CameraDepthTexture", "uv3File", "_AF28Bake"]
    mat_run = json.dumps(A.jl(MAT_RUN), ensure_ascii=False)
    code, ok = {}, True
    for p in SHADERS:
        t = open(p, encoding="utf-8").read()
        body = "\n".join(l.split("//")[0] for l in t.splitlines())
        hits = [f for f in forbid if f in body]
        s = A.sha(p)
        same = s in mat_run
        derived = None
        if not same and A.FIX:
            # 直しの回の写し：調べ M の版（SHA-256 が mat/run.json にある）との差の行が、白い点の直し（AS04FlecksM・_FleckAniso）と名前・説明の行だけか
            import difflib
            base = SHADERS_STUDY_M[SHADERS.index(p)]
            tb = open(base, encoding="utf-8").read().splitlines()
            ta = t.splitlines()
            added = [l for l in difflib.ndiff(tb, ta) if l.startswith("+ ")]
            removed = [l for l in difflib.ndiff(tb, ta) if l.startswith("- ")]
            allowed_removed = all(("AS04Flecks(" in l) or ("AS04FlatSmoothKeypose" in l) or ("AS04Common.cginc" in l) or ("GREATWAVE_AS04_COMMON" in l)
                                  or ("Name \"AS04FlatSmooth\"" in l) or ("_FleckShape;" in l) for l in removed)
            base_same = A.sha(base) in mat_run
            derived = {"study_M_base": A.rel(base), "study_M_base_sha256": A.sha(base), "study_M_base_same_as_run": base_same,
                       "added_lines": len(added), "removed_lines": len(removed), "removed_lines_only_fleck_call_name_include": bool(allowed_removed),
                       "removed_lines_text": [l[2:].strip()[:120] for l in removed]}
            same = bool(base_same and allowed_removed)
        sp = len(re.findall(r"_ScreenParams", body))
        code[A.rel(p)] = {"sha256": s, "same_as_study_M": same, "fix_copy_of_study_M": derived, "forbidden_tokens": hits, "_ScreenParams_uses": sp,
                          "screen_derivative_calls": {k: len(re.findall(r"\b%s\s*\(" % k, body)) for k in ("fwidth", "ddx", "ddy")}}
        ok &= (not hits) and same
    tool_sha = A.sha(TOOL_CS)
    s3 = A.jl(S3_RULES)["rules"]["G1"]["render_tool"]
    tool_same = tool_sha == s3["sha256"]
    ok &= tool_same
    rr = A.jl(RENDER + "/as03asm_render_report.json")
    rep = {k: rr.get(k) for k in ("heroSdf", "heroUvWarp", "heroUv3File", "protectedUnchanged", "as03Shader", "as03Surf", "as03Crown", "as03ClawGlaze",
                                  "clawLayout", "as03HeroOutline", "changedFiles")}
    ok &= (not rep["heroSdf"]) and (not rep["heroUvWarp"]) and (not rep["heroUv3File"]) and rep["protectedUnchanged"] is True and not rep["as03Crown"]
    uj = A.jl(A.UNION)
    chans = [c[0] for c in uj["channels"]]
    ch_ok = chans == ["position", "normal", "tangent", "uv3", "uv4", "uv5", "uv6"]
    ok &= ch_ok
    st = {"AS04_hero": stretch(A.UNION, "hero"), "wave4": stretch(A.UNION, "wave4"), "AS02C_smooth_sample03_shape": stretch(A.HERO_SM02C)}
    a4, a2, w4 = st["AS04_hero"]["patterned_face"], st["AS02C_smooth_sample03_shape"]["patterned_face"], st["wave4"]["patterned_face"]
    # 見本02・03 と同じ規則：帯の座標 w の勾配（|∇w|）が 1/3〜3 倍の外の三角形が、前（見本03 の形）より増えないこと（模様を描く面で）
    s_ok = (a4["gw_tri_outside_1_3_to_3x"] <= a2["gw_tri_outside_1_3_to_3x"] and a4["gw_area_frac_outside_1_3_to_3x"] <= a2["gw_area_frac_outside_1_3_to_3x"] + 1e-3
            and w4["gw_area_frac_outside_1_3_to_3x"] <= 1e-3)
    print(T(), "G1 stretch visible", flush=True)
    sv = stretch_visible()
    w4rep = A.jl(os.path.dirname(A.WAVE4) + "/wave4_build_report.json")
    return {"rule_ja": "色・線は原画カメラの投影を使わない（コードの検査）。7 視点＋回り台で引き伸ばし・継ぎ目・平らな面がない",
            "shaders": code, "render_tool": {"path": A.rel(TOOL_CS), "sha256": tool_sha, "same_as_sample03_checked": tool_same},
            "render_report_S04": rep, "union_mesh": {"path": A.rel(A.UNION), "bin_sha256": uj["sha256"], "channels": chans, "only_geometry_attrs": ch_ok},
            "surface_stretch_front": st, "surface_stretch_not_worse": bool(s_ok),
            "surface_stretch_rule_ja": ("見本02・03 と同じ規則で判定：模様（帯・白い点・水色の縁）を描く前の面（whiteSD < 1.4 m）で、帯の座標 w の勾配 |∇w| が "
                                        "1/3〜3 倍の外の三角形が見本03 の形（AS02C）より増えないこと（細い三角形を除く）。"
                                        "白（平らな一色で模様なし）の面と、白い点の格子だけに効く u は記録。"),
            "surface_stretch_record_ja": ("記録：AS04 の主役波では、白の面で |∇w| が外の三角形 %d（白の前の面の面積の %.2f%%。唇を短くした c −10〜−4 m の主の唇の左の端、"
                                          "白い一色なので帯は描かれない）、模様の面で |∇u| が外の三角形 %d（%.2f%%。c −0.2〜+0.95 m の巻きの内の細い帯。u は白い点の格子だけに使う）。"
                                          "見本03 の形ではどちらもほぼ 0。各視点で見える画素は stretch_visible_px。") % (
                st["AS04_hero"]["white_face"]["gw_tri_outside_1_3_to_3x"], 100 * st["AS04_hero"]["white_face"]["gw_area_frac_outside_1_3_to_3x"],
                a4["gu_tri_outside_1_3_to_3x"], 100 * a4["gu_area_frac_outside_1_3_to_3x"]),
            "stretch_visible_px": sv,
            "wave4_whiteSD_source_ja": ("wave4 の whiteSD（水色の帯・淡い筋・白い点の境）は、原画の楔の帯の境の位置を、原画のカメラの射線が wave4 の面に当たる所の "
                                        "面の座標 u・c として測り、c に沿ってならした値（w4_paint.py・w4_build.py）。見本03 の白の印（前の白の境を原画視点の藍の面の始まりに合わせた）"
                                        "と同じ「位置を測って面の値にする」作りで、色は材質の限られた色。シェーダーに原画カメラの行列・テクスチャは無い。"),
            "wave4_build_report_keys": sorted(list(w4rep.keys()))[:20],
            "note_ja": "7 視点＋波頭の回り台＋回り台の見た目（引き伸ばし・継ぎ目・平らな面）は利用者が並べ図で見る。ここは面の座標の伸びの数だけ。",
            "verdict": "pass" if (ok and s_ok) else "fail"}


# ---------------------------------------------------------------- G2
def g2():
    sg = A.jl(GATES)["gates"]
    rows, ok = {}, True
    for k, x in sg.items():
        pv = bool(x["after_claws"] <= x["gate_px"] and x["after_noclaws"] <= x["gate_px"])
        ok &= pv
        rows[k] = {"claws": x["after_claws"], "noclaws": x["after_noclaws"], "gate_px": x["gate_px"], "pass": pv,
                   "sample02_AS02C_claws": x["before_claws"], "CP1": x.get("CP1"), "26修正01": x.get("26修正01")}
    _ho = (A.ASM + "/render/measure/gates_" + A.RTAG + "H/sweep_gates.json") if A.FIX else A.P4 + "/shape/render/measure/gates_A4/sweep_gates.json"
    hero_only = A.jl(_ho)["gates"] if os.path.isfile(_ho) else {}
    w4old = A.jl(A.P4 + "/wave4/render/measure/gates_as04/sweep_gates.json")["gates"]
    return {"rule_ja": "78・130・131（定義どおり）≤ 4 px、132・72 は大きな輪郭で ≤ 4 px。合わせた輪郭（主役波＋wave4）で測る",
            "render": A.rel(RENDER), "gates": rows, "eval23_record": R2.eval23(RENDER),
            "hero_only_A4_record": {k: v["after_claws"] for k, v in hero_only.items()},
            "stale_value_in_wave4_record": {"78_reported_by_wave4_task": w4old["78"]["after_claws"], "78_fresh_S04": sg["78"]["after_claws"],
                                            "note_ja": ("wave4 の作りの記録の 78 2.9185 は、wave4/render/as04/t28_claws の pl28u_tstar_verdict.json が 18:29 の途中の版の描画の"
                                                        "まま残り（as02_gates.py は判定のファイルがあると測り直さない）、19:01 の描き直しで測り直されなかった値。"
                                                        "組み立ての S04 は新しいフォルダーで測り直した（描画の画は 19:01 の版と画素まで同じ）。")},
            "source": {"path": A.rel(GATES), "sha256": A.sha(GATES)},
            "verdict": "pass" if ok else "fail"}


# ---------------------------------------------------------------- S4
def union_H(c, Yr, X4):
    H = Yr[:, A.S4.J_B:A.S4.J_TIP + 1].max(1)
    Q = A.K.sec(X4)
    Hu = H.copy()
    for i in range(len(c)):
        lo = 0.5 * (c[i - 1] + c[i]) if i > 0 else c[i] - 0.1
        hi = 0.5 * (c[i] + c[i + 1]) if i < len(c) - 1 else c[i] + 0.1
        m = (Q[:, 2] >= lo) & (Q[:, 2] < hi)
        if m.any():
            Hu[i] = max(Hu[i], Q[m, 1].max())
    return H, Hu


def sil_top_points(P, view, cvals):
    w, h = int(view["w"]), int(view["h"])
    x, y, z = BC.project(P, view["eye"], view["tgt"], view["vfov"], w, h)
    keep = (P[:, 1] > 0.05) & (z > 0)
    xi = np.floor(x[keep]).astype(int); yy = y[keep]; cc = cvals[keep]
    m = (xi >= 0) & (xi < w)
    xi, yy, cc = xi[m], yy[m], cc[m]
    top = np.full(w, np.inf); np.minimum.at(top, xi, yy)
    ctop = np.full(w, np.nan)
    o = np.lexsort((yy, xi)); xs = xi[o]; first = np.r_[True, xs[1:] != xs[:-1]]
    ctop[xs[first]] = cc[o][first]
    return top, ctop


def s4():
    c4, A4, Y4 = SC.load_rows(A.ROWS04)
    ch4, tri4, _ = A.read_static(A.WAVE4)
    X4 = ch4["position"].astype(np.float64)
    H, Hu = union_H(c4, Y4, X4)
    win = c4 >= -14.0
    hs = {"hero_only": {"all": BC.shape_stats(c4, H), "window_c_ge_-14": BC.shape_stats(c4[win], H[win])},
          "union_hero_wave4": {"all": BC.shape_stats(c4, Hu), "window_c_ge_-14": BC.shape_stats(c4[win], Hu[win])}}
    for k in hs:
        for kk in hs[k]:
            hs[k][kk] = {a: A.rnd(b, 3) for a, b in hs[k][kk].items()}
    views = BC.load_views()
    Q4 = A.K.sec(X4)
    sil = {}
    c2, A2, Y2 = SC.load_rows(A.ROWS02C)
    for vn in ("b65_back65_clay", "b90_back_straight", "b115_back_minus_c"):
        v = views[vn]
        t02, ct02 = BC.silhouette_top(c2, A2, Y2, v)
        th, cth = BC.silhouette_top(c4, A4, Y4, v)
        tw, ctw = sil_top_points(X4, v, Q4[:, 2])
        tu = np.minimum(th, tw)
        ctu = np.where(tw < th, ctw, cth)
        res = {}
        for name, top, ct in (("AS02C_sample03_shape", t02, ct02), ("AS04_hero_only", th, cth), ("AS04_union", tu, ctu)):
            ok = np.isfinite(top)
            xs = np.nonzero(ok)[0]
            hg = v["h"] - top[ok]
            cw = ct[ok] >= -14.0
            st_all = BC.shape_stats(xs.astype(float), hg)
            st_w = BC.shape_stats(xs[cw].astype(float), hg[cw]) if cw.sum() > 5 else None
            res[name] = {"dip_px_all": A.rnd(st_all["dip_depth"], 2), "dip_px_window_c_ge_-14": A.rnd(st_w["dip_depth"], 2) if st_w else None,
                         "x_at_dip_all": A.rnd(st_all["x_at_dip"], 0)}
        sil[vn] = res
    bm = A.jl(BACK_MEASURE)
    bm_ok = bm["inputs"]["AS04"]["sha256"] == A.sha(A.ROWS04)
    sm = bm["summary"]["AS04"]
    peaks = sm["bulge_peak_c_by_level"]
    off = {lv: cc for lv, cc in peaks.items() if not (-6.0 <= cc <= 6.0)}
    chk = {"H_dip_union_c_ge_-14_m": {"value": hs["union_hero_wave4"]["window_c_ge_-14"]["dip_depth"], "pass": hs["union_hero_wave4"]["window_c_ge_-14"]["dip_depth"] <= 0.0},
           "back_contour_dip_max_m（主役波の背、0.10 m まで）": {"value": sm["back_dip_max_m"], "pass": sm["back_dip_max_m"] <= 0.10},
           "bulge_over_chord_dip_m": {"value": sm["back_bulge_dip_max_m"], "pass": sm["back_bulge_dip_max_m"] <= 0.10},
           "silhouette_dip_from_behind_px_union_c_ge_-14（1 px まで）": {"value": {k: v["AS04_union"]["dip_px_window_c_ge_-14"] for k, v in sil.items()},
                                                                       "pass": max(v["AS04_union"]["dip_px_window_c_ge_-14"] for v in sil.values()) <= 1.0}}
    rec = {"bulge_peak_in_middle_zone_c_-6_6（記録。見本02 から外へ出る高さがある）": {"peak_c_by_level": peaks, "outside_levels": off}}
    allpass = all(v["pass"] for v in chk.values())
    return {"rule_ja": "背は中ほどがいちばん高く盛り上がり、両側へなだらかに下がる（一つの山）。後ろ 65°・真後ろ・回り台で目でも確かめる",
            "H_of_c": hs, "silhouette_from_behind": sil, "checks": chk, "record": rec,
            "back_contour_source": {"path": A.rel(BACK_MEASURE), "rows_sha256_matches": bm_ok},
            "method_ja": ("H(c) は主役波の行ごとの頂（列 18〜200 の最大）と、その行の幅の中の wave4 の頂点の高さの最大の大きい方。"
                          "後ろからの輪郭は見本02 の back_measure と同じカメラ（b65・b90・b115）で、主役波は行を細かく補った点、wave4 は静止のメッシュの頂点を投影した一番上。"
                          "窓 c ≥ −14 は見本02 と同じ（b区域より +c 側）。全部の行の値も記録する。"),
            "verdict": "pass" if allpass else "fail"}


# ---------------------------------------------------------------- 原画視点の id（2 倍）
_PV = {}


def painting_ids(kind="S04", scale=2):
    key = (kind, scale)
    if key not in _PV:
        tris, lab, _ = A.scene(kind)
        cam = A.painting_cam(scale)
        _, D, L = A.raster(cam, tris, lab)
        _PV[key] = (cam, D, L)
    return _PV[key]


def owner_name(l):
    return "hero" if l in HERO_LABS else {5: "wave4", 6: "sea", 7: "claw", 0: "sky"}[int(l)]


# ---------------------------------------------------------------- S8
def s8():
    c0, A0, Y0 = SC.load_rows(A.ROWS02C)
    c4, A4, Y4 = SC.load_rows(A.ROWS04)
    b0 = SC.bulge_metric(c0, A0, Y0)
    b4 = SC.bulge_metric(c4, A4, Y4)
    cam, D, L = painting_ids("S04", 2)
    poly = (np.asarray(SC.BULGE_DISP, float) + 0.5) * 2 - 0.5
    m = np.zeros(L.shape, np.uint8)
    cv2.fillPoly(m, [np.round(poly).astype(np.int32)], 1)
    ll = L[m > 0]
    share = {owner_name(k): A.rnd(float((np.vectorize(owner_name)(ll) == owner_name(k)).mean())) for k in np.unique(ll)}
    ok = b4["dev_from_inner_face_m"]["p95"] <= 0.15
    return {"rule_ja": "原画視点で頂の下・唇の左の内側の面の帯（利用者の黄色の線）は、内側の面と同じ弧の上にあり、出っ張り・折り重なりを作らない",
            "measure_ja": "その所の面の、内側の面の弧からの出っ張り p95 ≤ 0.15 m（形づくりの shape_common.bulge_metric：黄色の線の中の原画の射線の最初の当たりが、その行の内の面の線からどれだけ離れているか）",
            "AS02C_sample03_shape": b0, "AS04": b4, "painting_view_owner_share_in_loop_S04": share,
            "verdict": "pass" if ok else "fail"}


# ---------------------------------------------------------------- S9
def s9():
    cam, D, L = painting_ids("S04", 2)
    cov = L > 0
    sky_nb = np.zeros_like(cov)
    sky_nb[1:] |= ~cov[:-1]
    sky_nb[:-1] |= ~cov[1:]
    sky_nb[:, 1:] |= ~cov[:, :-1]
    sky_nb[:, :-1] |= ~cov[:, 1:]
    edge = cov & sky_nb
    ey, ex = np.nonzero(edge)
    tr = cKDTree(np.c_[ex, ey].astype(float))
    segs = A.S4.outline_segments()
    per = {}
    by_pt = {}
    for sid in ("78", "130", "131", "132", "72"):
        Pr = segs[sid]
        Pp = A.ref_to_px(Pr, 2)
        dd, ii = tr.query(Pp)
        own = [owner_name(L[ey[i], ex[i]]) for i in ii]
        r = {"points": len(Pr), "owner_share": {k: A.rnd(own.count(k) / len(own)) for k in sorted(set(own))},
             "nearest_edge_px_display_max": A.rnd(dd.max() / 2, 2), "nearest_edge_px_display_p95": A.rnd(np.percentile(dd, 95) / 2, 2)}
        if sid == "78":
            m4 = Pr[:, 0] < 360.0
            o4 = [o for o, k in zip(own, m4) if k]
            on = [o for o, k in zip(own, m4) if not k]
            r["region4_x_lt_360"] = {"points": int(m4.sum()), "owner_share": {k: A.rnd(o4.count(k) / len(o4)) for k in sorted(set(o4))},
                                     "nearest_edge_px_display_max": A.rnd(dd[m4].max() / 2, 2)}
            r["x_ge_360"] = {"points": int((~m4).sum()), "owner_share": {k: A.rnd(on.count(k) / len(on)) for k in sorted(set(on))}}
            by_pt["78"] = [[A.rnd(Pr[i, 0], 0), A.rnd(Pr[i, 1], 0), own[i], A.rnd(dd[i] / 2, 2)] for i in range(0, len(Pr), 4)]
        per[sid] = r
    # 列ごとの一番上の画素の持ち主（並べ図用）
    top = np.where(cov.any(0), np.argmax(cov, 0), -1)
    topown = np.array([L[top[x], x] if top[x] >= 0 else 0 for x in range(L.shape[1])], np.int16)
    np.savez_compressed(A.MEAS + "/s9_painting_owner_x2.npz", L=L.astype(np.int8), top=top, topown=topown)
    # ④ の楔：wave4 が見えている画素の一番下（原画の y）と原画の楔の下の縁
    M = A.jl(A.P4 + "/map/s4_map.json")
    wl = {e["x_ref"]: e.get("wedge_lower_edge_y_ref_smooth") for e in M["region4"]["columns"]}
    wed = []
    for x in range(4, 361, 16):
        px = A.ref_to_px(np.array([[x, 900.0]]), 2)[0, 0]
        col = int(round(px))
        own = np.nonzero(L[:, col] == 5)[0]
        y = None
        if len(own):
            y = A.px_to_ref(np.array([[col, own.max()]]), 2)[0, 1]
        wed.append({"x_ref": x, "wave4_visible_lower_y_ref": A.rnd(y, 1) if y is not None else None, "painting_wedge_lower_y_ref": wl.get(x),
                    "too_high_px": A.rnd(wl.get(x) - y, 1) if (y is not None and wl.get(x)) else None})
    # 白の頂の高さ（c ごと）：見本03 の形（AS02C、白の印 v2）と AS04（白の印を番号で引き継ぎ、距離を測り直したもの）
    white = {}
    for name, path in (("AS02C_sample03_shape", A.HERO_SM02C), ("AS04", A.HERO_SM04)):
        ch, _, _ = A.read_static(path)
        Q = A.K.sec(ch["position"].astype(np.float64))
        wsd = ch["uv5"][:, 2]
        wm = wsd > 0
        bins = np.arange(-34.0, -7.99, 2.0)
        tops = []
        for lo in bins[:-1]:
            m = wm & (Q[:, 2] >= lo) & (Q[:, 2] < lo + 2.0)
            tops.append([A.rnd(lo + 1.0, 1), A.rnd(Q[m, 1].max(), 2) if m.any() else None, int(m.sum())])
        white[name] = {"white_vertices": int(wm.sum()), "white_vertices_c_lt_-12.6": int((wm & (Q[:, 2] < -12.6)).sum()),
                       "leftmost_white_c_m": A.rnd(Q[wm, 2].min(), 2), "white_top_y_by_c_bin_2m": tops}
    # Unity の描画での確かめ：wave4 あり（S04）となし（形づくりの A4）の原画視点の差
    from PIL import Image
    a = np.asarray(Image.open(RENDER + "/views/painting_t120_claws.png").convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(HERO_ONLY + "/views/painting_t120_claws.png").convert("RGB")).astype(np.int16)
    dm = np.abs(a - b).sum(-1) > 12
    np.save(A.MEAS + "/s9_unity_diff_mask.npy", dm)
    x360 = A.ref_to_px(np.array([[360.0, 900.0]]), 1)[0, 0]
    ys, xs = np.nonzero(dm)
    p4 = A.ref_to_px(np.array(A.S4.REG4, float), 1)
    m4 = np.zeros(dm.shape, np.uint8)
    cv2.fillPoly(m4, [np.round(p4).astype(np.int32)], 1)
    unity = {"changed_pixels": int(dm.sum()), "bbox_display_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None,
             "changed_right_of_x_ref_360": int((xs > x360 + 2).sum()), "x_display_of_x_ref_360": A.rnd(x360, 1),
             "region4_polygon_changed_share": A.rnd(float(dm[m4 > 0].mean())),
             "note_ja": "Unity の原画視点の描画（爪あり）で、wave4 あり（組み立て S04）と なし（形づくりの A4）の差の画素（RGB の差の和 > 12）。差は wave4 が見える所だけに出るはず。"}
    r4 = per["78"]["region4_x_lt_360"]["owner_share"]
    ok = r4.get("wave4", 0) >= 0.95 and white["AS04"]["white_vertices_c_lt_-12.6"] < white["AS02C_sample03_shape"]["white_vertices_c_lt_-12.6"]
    return {"rule_ja": "左側の白は下へ押されて低い。④（輪郭線の最も左の短い一区間）は青い波が作る。白い波を左へ延ばして高い輪郭線に合わせない",
            "measure_ja": ("原画視点（表示の 2 倍の細かさの numpy の z バッファ。主役波 AS04 ＋ wave4 の静止のメッシュ・近い海・爪）で、空と接する輪郭の画素の持ち主を数え、"
                           "原画の輪郭の真値の点（区間ごと）に最も近い輪郭の画素の持ち主を数える。④ = 区間 78 の x < 360（原画の画素）。"),
            "per_segment": per, "segment78_points_sampled": by_pt.get("78"),
            "wedge_lower_edge": wed, "white_part": white, "unity_render_diff_with_without_wave4": unity,
            "pass_condition_ja": "④ の真値の点の 95% 以上を wave4 が作り、主役波の白の頂点が c < −12.6 m で見本03 より少ない",
            "verdict": "pass" if ok else "fail"}


# ---------------------------------------------------------------- S10
def bands_union(c, Yr, X4, H=20.27, fr=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)):
    Hc = Yr[:, A.S4.J_B:A.S4.J_TIP + 1].max(1)
    cg = np.arange(-60.0, 15.0001, 0.05)
    hh = np.interp(cg, c, Hc)
    Q = A.K.sec(X4)
    k = np.clip(np.round((Q[:, 2] + 60.0) / 0.05).astype(int), 0, len(cg) - 1)
    w4 = np.zeros(len(cg)); np.maximum.at(w4, k, Q[:, 1])
    hu = np.maximum(hh, w4)
    out = {}
    for f in fr:
        sel = np.nonzero(hu >= f * H)[0]
        out["%.1f" % f] = {"c_lo": A.rnd(cg[sel[0]], 2), "c_hi": A.rnd(cg[sel[-1]], 2), "width_m": A.rnd(cg[sel[-1]] - cg[sel[0]], 2)} if len(sel) else None
    return out


def s10():
    c0, A0, Y0 = SC.load_rows(A.ROWS02C)
    c4, A4, Y4 = SC.load_rows(A.ROWS04)
    ch4, _, _ = A.read_static(A.WAVE4)
    e0, e4 = SC.band_extent(c0, A0, Y0), SC.band_extent(c4, A4, Y4)
    eu = bands_union(c4, Y4, ch4["position"].astype(np.float64))
    e0u = bands_union(c0, Y0, np.zeros((0, 3)))
    rat = {k: {"hero_only": A.rnd(e4[k]["width_m"] / e0[k]["width_m"]) if e4.get(k) and e0.get(k) else None,
               "union": A.rnd(eu[k]["width_m"] / e0u[k]["width_m"]) if eu.get(k) and e0u.get(k) else None} for k in e0}
    low = ("0.1", "0.2", "0.3", "0.4", "0.5")
    ok = all(rat[k]["union"] is not None and rat[k]["union"] < 1.0 for k in low) and all(rat[k]["union"] is not None and rat[k]["union"] <= 1.0001 for k in rat)
    return {"rule_ja": "波の峰に沿う向き（横向）に長すぎない。詰める（見本03 と比べる）",
            "method_ja": ("高さの帯（H = 20.27 m の 0.1〜0.9）ごとに、頂がその高さを越える c の範囲の幅。主役波だけは形づくりの band_extent（行の頂）、"
                          "合わせた形は主役波の行の頂と wave4 の頂点の高さを c の 0.05 m おきに重ねた大きい方（主役波だけの値と 0.05 m の差がありうる）。"),
            "AS02C_sample03_shape": e0, "AS02C_on_0p05m_grid": e0u, "AS04_hero_only": e4, "AS04_union_hero_wave4": eu, "ratio_vs_sample03": rat,
            "pass_condition_ja": "合わせた形で低い帯（0.1〜0.5 H）が見本03 より短く、どの帯も長くならない。高い帯（0.6〜0.9 H）は計画どおり第 2 段（D6）で、今は同じ",
            "verdict": "pass" if ok else "fail"}


# ---------------------------------------------------------------- S11
def layer_view_metrics(L, D):
    H, W_ = L.shape
    vis = {k: int((L == k).sum()) for k in (1, 2, 3)}
    occ = {}
    cont = {}
    for dy, dx in ((0, 1), (1, 0)):
        a, b = L[:H - dy, :W_ - dx], L[dy:, dx:]
        da, db = D[:H - dy, :W_ - dx], D[dy:, dx:]
        both = np.isfinite(da) & np.isfinite(db)
        near = np.minimum(np.where(both, da, 1e9), np.where(both, db, 1e9))
        jump = both & (np.abs(da - db) > np.maximum(0.5, 0.03 * near))
        for p, q in ((1, 2), (2, 3), (1, 3)):
            pair = ((a == p) & (b == q)) | ((a == q) & (b == p))
            occ[(p, q)] = occ.get((p, q), 0) + int((pair & jump).sum())
            cont[(p, q)] = cont.get((p, q), 0) + int((pair & ~jump).sum())
    # 前の面（1・2・3・4）を、深さの跳びのない隣どうしでつないだ連結成分
    front = np.isin(L, (1, 2, 3, 4))
    e = A.occl_edges(D)
    reg = (front & ~e).astype(np.uint8)
    n, comp = cv2.connectedComponents(reg, connectivity=4)
    conn = {}
    for p, q in ((1, 2), (2, 3), (1, 3)):
        cp = np.bincount(comp[(L == p) & (reg > 0)], minlength=n)
        cq = np.bincount(comp[(L == q) & (reg > 0)], minlength=n)
        cp[0] = 0; cq[0] = 0
        shared = int(np.minimum(cp, cq)[(cp >= 50) & (cq >= 50)].sum())
        conn[(p, q)] = shared
    return vis, occ, cont, conn


def s11():
    c0, A0, Y0 = SC.load_rows(A.ROWS02C)
    c4, A4, Y4 = SC.load_rows(A.ROWS04)
    cam = SC.paint_cam()
    geo = {"AS02C_sample03_shape": SE.layers(c0, A0, Y0, cam), "AS04": SE.layers(c4, A4, Y4, cam)}
    for k in geo:
        geo[k].pop("front_edge_by_row", None)
    views = {}
    os.makedirs(A.MEAS + "/s11", exist_ok=True)
    for kind, name in (("S03", "AS02C_sample03_shape"), ("S04", "AS04_union")):
        tris, lab, _ = A.scene(kind, with_claws=False)
        for vn in S11_VIEWS:
            camv = A.view_cam(vn)
            _, D, L = A.raster(camv, tris, lab)
            vis, occ, cont, conn = layer_view_metrics(L, D)
            img = A.tint(L, D)
            cv2.imwrite(A.MEAS + "/s11/%s_%s.png" % (kind, vn), img[..., ::-1])
            pr = {}
            for (p, q) in ((1, 2), (2, 3), (1, 3)):
                both = vis[p] >= 200 and vis[q] >= 200
                sep = both and (occ[(p, q)] >= 20 or conn[(p, q)] == 0) and cont[(p, q)] == 0
                pr["%d-%d" % (p, q)] = {"both_visible": both, "occlusion_edge_px": occ[(p, q)], "continuous_contact_px": cont[(p, q)],
                                         "same_front_sheet_px": conn[(p, q)], "separated": bool(sep) if both else None}
            views.setdefault(name, {})[vn] = {"visible_px": {str(k): v for k, v in vis.items()}, "pairs": pr}
            print(T(), "S11", kind, vn, vis, {k: (v["occlusion_edge_px"], v["same_front_sheet_px"], v["separated"]) for k, v in pr.items()}, flush=True)
    summ = {}
    for name, vv in views.items():
        s = {}
        for pk in ("1-2", "2-3", "1-3"):
            arr = [x["pairs"][pk]["separated"] for x in vv.values() if x["pairs"][pk]["separated"] is not None]
            s[pk] = {"views_both_visible": len(arr), "separated_views": int(sum(arr)), "separated_share": A.rnd(sum(arr) / len(arr)) if arr else None}
        summ[name] = s
    a4 = summ["AS04_union"]
    ok = all((a4[pk]["separated_share"] or 0) >= 0.5 for pk in ("1-2", "2-3"))
    return {"rule_ja": "爪の三つの大きな区域 ①浪尖・②b区域・③最左側の小区域を、構造の層としてはっきり表す（側面・上・回り台で別の層として読める）",
            "geometry_steps": geo,
            "view_method_ja": ("numpy の z バッファ（Unity の描画ではない。主役波・wave4・近い海、爪なし）で、側面 2・真上・回り台 12 方位を描き、三角形に層の印"
                               "（① c −2〜+8、② c −15.5〜−11.5、③ c −23〜−17 の、頂より前 u ≥ 0 で高さ 0.25 H0 以上の面。c は形づくりの shape_eval.LAYERS）を付けた。"
                               "層 p・q が「分かれて読める」＝ どちらも 200 画素以上見え、隣り合う画素どうしが深さの跳びなしに触れておらず、"
                               "かつ、p が q の手前に重なる遮る縁（深さの跳び > max(0.5 m, 深さの 3%)、設計38 の外殻の線が描く所に当たる）が 20 画素以上あるか、"
                               "前の面（①②③とほかの前の面）を深さの跳びのない隣どうしでつないだ時に p と q が別の塊になること。"),
            "views": views, "summary": summ,
            "pass_condition_ja": "見本04 で、隣の層の組（①②・②③）が、両方見える視点の半分以上で分かれて読めること（進行役の既定。変えてよい）",
            "verdict": "pass" if ok else "fail"}


# ---------------------------------------------------------------- T4
def catmull_base(gwb, uv6):
    g = A.K.read_gwb(gwb)
    X = g["X"].reshape(g["nv"], g["nu"], 3)
    R = X.shape[0]
    r = uv6[:, 0].astype(np.float64); col = np.round(uv6[:, 1]).astype(int)
    r0 = np.floor(r + 1e-6).astype(int); t = (r - r0)[:, None]
    pm = X[np.maximum(r0 - 1, 0), col]; p0 = X[r0, col]; p1 = X[np.minimum(r0 + 1, R - 1), col]; p2 = X[np.minimum(r0 + 2, R - 1), col]
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p0) + (-pm + p1) * t + (2 * pm - 5 * p0 + 4 * p1 - p2) * t2 + (-pm + 3 * p0 - 3 * p1 + p2) * t3)


def relief_dev(path, gwb, part=None):
    ch, tri, _ = A.read_static(path)
    n = A.N_HERO if part == "hero" else len(ch["position"])
    pos = ch["position"][:n].astype(np.float64)
    base = catmull_base(gwb, ch["uv6"][:n])
    d = np.linalg.norm(pos - base, axis=1)
    nrm = ch["normal"][:n].astype(np.float64)
    sd = ((pos - base) * nrm).sum(1)
    u = ch["uv3"][:n, 2]; wsd = ch["uv5"][:n, 2]
    out = {"vertices": int(n), "max_dev_m": A.rnd(d.max(), 4), "p99_dev_m": A.rnd(np.percentile(d, 99), 4),
           "front_u_ge_0_max_dev_m": A.rnd(d[u >= 0].max(), 4), "white_whiteSD_gt_0_max_dev_m": A.rnd(d[wsd > 0].max(), 4) if (wsd > 0).any() else None,
           "signed_along_normal_min_max_m": [A.rnd(sd.min(), 4), A.rnd(sd.max(), 4)]}
    return out


def t4():
    rr = A.jl(RENDER + "/as03asm_render_report.json")
    log = open(A.ASM + "/logs/run_asm4_%s_views_crest_tt_full_t28.txt" % A.RTAG, encoding="utf-8", errors="replace").read()
    ulog = open(A.ASM + "/logs/unity_as04mat_asm4_%s_views_crest_tt_full_t28.log" % A.RTAG, encoding="utf-8", errors="replace").read()
    crown_arg = "-as03Crown" in ulog.split("AS03ASM_RENDER_DONE")[0] and re.search(r"-as03Crown\s+\S", ulog) is not None
    dev04 = relief_dev(A.UNION, A.GWB04, "hero")
    dev02 = relief_dev(A.HERO_SM02C, A.GWB02C)
    dev03 = relief_dev(A.RELIEF03, A.GWB02C)
    # wave4：格子（解析の式から作った A・Y）と静止のメッシュの点
    g = dict(np.load(os.path.dirname(A.WAVE4) + "/wave4_grid.npz"))
    ch, _, _ = A.read_static(A.WAVE4)
    Xg = A.K.world(g["c"], g["A"], g["Y"]).reshape(-1, 3)[g["used"]]
    w4d = float(np.linalg.norm(ch["position"].astype(np.float64) - Xg, axis=1).max())
    # 解析の面のなめらかさ：格子の行・列の二階差（m）
    Y = g["Y"]; used = np.zeros(Y.size, bool); used[g["used"]] = True; used = used.reshape(Y.shape)
    d2r = np.abs(Y[2:] - 2 * Y[1:-1] + Y[:-2])[used[2:] & used[1:-1] & used[:-2]]
    shader = "\n".join(l.split("//")[0] for p in SHADERS for l in open(p, encoding="utf-8").read().splitlines())
    light_tok = [t for t in ("_WorldSpaceLightPos0", "_LightColor0", "ShadeSH9", "UnityLightingCommon", "Lighting.cginc", "reflect(", "_Gloss", "_Spec", "_AO") if t in shader]
    SMR = A.jl(A.HERO_SM04.replace(".json", "_report.json"))
    ok = (not rr.get("as03Crown")) and (not crown_arg) and dev04["max_dev_m"] <= 0.01 and w4d <= 0.001 and not light_tok
    return {"rule_ja": "面と白い所は原画の平らな塗りで、表面は滑らか：彫りの稜・彫ったような跡・泡の皮を作らない。冠のメッシュがない",
            "crown_mesh": {"render_report_as03Crown": rr.get("as03Crown"), "crown_argument_in_unity_command": bool(crown_arg)},
            "relief_vs_smooth_base": {"method_ja": ("静止のメッシュの各点を、その点の行・列（uv6）で .gwb の行を Catmull–Rom で補った滑らかな土台（見本03 の surf_relief.py と同じ式）と比べたずれ。"
                                                    "凹凸を彫った見本03 の面も同じ測りで並べる。"),
                                      "AS04_hero_in_union": dev04, "AS02C_smooth_mat_study": dev02, "sample03_relief_b1v2c（V1・V2・V3 の面）": dev03},
            "wave4": {"max_dev_from_analytic_grid_m": A.rnd(w4d, 6), "row_second_difference_p99_max_m": [A.rnd(np.percentile(d2r, 99), 5), A.rnd(d2r.max(), 4)],
                      "note_ja": "wave4 は sech² の断面・3 次の曲線・2 次のなめらかな最大で作った解析の面（w4_build.py）。変位・彫りの道はない。"},
            "shader_lighting_tokens": light_tok,
            "shape_mesh_report": {k: SMR.get(k) for k in ("flat", "displacement_m", "gwb_vs_pkg_tau0_m")},
            "pass_condition_ja": "冠が無い、主役波の点の土台からのずれ ≤ 1 cm（包みの量子化の分）、wave4 は解析の格子と同じ、シェーダーに光・艶・AO の語が無い",
            "verdict": "pass" if ok else "fail"}


# ---------------------------------------------------------------- C2・C3
def c2_c3():
    new, lay4 = A.claws_tris(A.CLAWS04)
    old, lay3 = A.claws_tris(A.CLAWS03)
    oldm = {c["user_id"]: c for c in old}
    cam = SC.paint_cam()
    rec = {r["user_id"]: r for r in lay4["as04_shape"]["face_interior"]}
    rep = {c["user_id"]: c for c in A.jl(S2_CLAW_REPORT)["claws"]}
    rows = []
    # 原画視点の隠れ（2 倍）：爪なしの場面の深さ
    vis = {}
    for kind, cl in (("S04", new), ("S03", old)):
        tris, lab, _ = A.scene(kind, with_claws=False)
        camp = A.painting_cam(2)
        _, D0, _ = A.raster(camp, tris, lab)
        for c in cl:
            if c["role"] != "FACE_INTERIOR":
                continue
            _, Dc, Lc = A.raster(camp, c["verts"][c["tris"]], np.full(len(c["tris"]), 7, np.int16))
            m = Lc > 0
            v = m & (Dc <= D0 + 0.02)
            vis[(kind, c["user_id"])] = (int(m.sum()), float(v.sum() / max(m.sum(), 1)))
    # 面からの浮き・沈み（近い頂点の法線で、記録）
    surf = {}
    for kind, path in (("S04", A.UNION), ("S03", A.HERO_SM02C)):
        ch, _, _ = A.read_static(path)
        n = A.N_HERO
        surf[kind] = (cKDTree(ch["position"][:n].astype(np.float64)), ch["position"][:n].astype(np.float64), ch["normal"][:n].astype(np.float64))
    for c in new:
        uid = c["user_id"]
        o = oldm[uid]
        Vn, Vo = c["verts"], o["verts"]
        if c["role"] == "FACE_INTERIOR":
            k = float(np.linalg.norm(Vn[0] - cam.pos) / np.linalg.norm(Vo[0] - cam.pos))
        else:
            k = 1.0
        pred = cam.pos + (Vo - cam.pos) * k
        res = float(np.linalg.norm(Vn - pred, axis=1).max())
        xyn, _ = cam.project(Vn); xyo, _ = cam.project(Vo)
        dpx = float(np.linalg.norm(xyn - xyo, axis=1).max())
        r = rep.get(uid, {})
        e = {"user_id": uid, "role": c["role"], "scale_about_painting_cam": A.rnd(k, 4), "similarity_residual_m": A.rnd(res, 6),
             "painting_projection_shift_px_max": A.rnd(dpx, 5), "moved_m": rec.get(uid, {}).get("moved_m", 0.0),
             "length_3d_m_sample02": r.get("length_3d_m"), "length_3d_m_now": A.rnd((r.get("length_3d_m") or 0) * k, 3),
             "iou_painting_sample02": r.get("iou_painting"), "c2_fails_sample02": [x for x in r.get("standard_fails_ja", []) if not x.startswith("面から見た IoU")]}
        for kind, V in (("S04", Vn), ("S03", Vo)):
            kd, P, N = surf[kind]
            dd, ii = kd.query(V)
            sd = ((V - P[ii]) * N[ii]).sum(1)
            side = np.sign(np.median(sd)) or 1.0
            e["surface_" + kind] = {"root_dist_m": A.rnd(dd[0], 3), "max_below_surface_m": A.rnd(max(0.0, -float((sd * side).min())), 3),
                                    "max_above_surface_m": A.rnd(float((sd * side).max()), 3)}
            if (kind, uid) in vis:
                e["painting_visible_" + kind] = {"px_x2": vis[(kind, uid)][0], "visible_frac": A.rnd(vis[(kind, uid)][1], 3)}
        rows.append(e)
    face = [e for e in rows if e["role"] == "FACE_INTERIOR"]
    sim_ok = all(e["similarity_residual_m"] <= 1e-3 and e["painting_projection_shift_px_max"] <= 0.01 for e in rows)
    c2fail = {e["user_id"]: e["c2_fails_sample02"] for e in rows if e["c2_fails_sample02"]}
    c3fail = {e["user_id"]: e["iou_painting_sample02"] for e in face if (e["iou_painting_sample02"] or 0) < 0.85}
    vfr4 = [e["painting_visible_S04"]["visible_frac"] for e in face]
    vfr3 = [e["painting_visible_S03"]["visible_frac"] for e in face]
    c2 = {"rule_ja": "どの爪も、利用者の模型 claw_low・claw_mid の水準以上（断面の幅と厚みの比、先の細り、表面の滑らかさを模型と比べる）",
          "claws": len(rows), "by_role": {r: sum(1 for e in rows if e["role"] == r) for r in ("FACE_INTERIOR", "NEAR_SEA")},
          "reseat_is_similarity_about_painting_cam": sim_ok,
          "scale_range_face_interior": [A.rnd(min(e["scale_about_painting_cam"] for e in face), 3), A.rnd(max(e["scale_about_painting_cam"] for e in face), 3)],
          "moved_gt_1cm": sum(1 for e in face if abs(e["moved_m"]) > 0.01),
          "fail": len(c2fail), "fail_claws": c2fail,
          "note_ja": ("形づくり（shape_claws.py）は面の内の 25 本を、原画のカメラを中心に倍率だけかけて置き直した。相似なので、C2 の量（断面の比・先の細り・"
                      "曲率の跳び・輪郭のでこぼこ。どれも比か角）は見本02 の測り（as02_claws_report.json）のまま。3D の大きさは倍率の分だけ大きい（記録）。"),
          "verdict": "pass" if (sim_ok and not c2fail) else "fail"}
    c3 = {"rule_ja": "原画カメラから見た各爪の輪郭とマスクの重なり（IoU ≥ 0.85）",
          "claws_face_interior": len(face), "projection_unchanged": sim_ok,
          "iou_painting_p10_p50_min_sample02": [A.rnd(np.percentile([e["iou_painting_sample02"] for e in face], q), 4) for q in (10, 50)] + [A.rnd(min(e["iou_painting_sample02"] for e in face), 4)],
          "below_085": c3fail,
          "painting_visible_frac_p10_p50_min": {"S04": [A.rnd(np.percentile(vfr4, 10), 3), A.rnd(np.median(vfr4), 3), A.rnd(min(vfr4), 3)],
                                                "S03": [A.rnd(np.percentile(vfr3, 10), 3), A.rnd(np.median(vfr3), 3), A.rnd(min(vfr3), 3)]},
          "note_ja": ("原画視点の影は画素まで同じ（相似の中心が原画のカメラ）なので、IoU は見本02 の測りのまま。原画視点で主役波・wave4 に隠れる割合は numpy の z バッファで"
                      "記録（隠れる爪が増えていれば並べ図で確かめる）。"),
          "verdict": "pass" if (sim_ok and not c3fail) else "fail"}
    return c2, c3, rows


def main():
    os.makedirs(A.MEAS, exist_ok=True)
    only = sys.argv[1:]
    if only and os.path.isfile(OUT):
        # 一部の規則だけ測り直して、前の rules_check.json に入れ替える
        res = A.jl(OUT)
        fns = {"G1": g1, "G2": g2, "S4": s4, "S8": s8, "S9": s9, "S10": s10, "T4": t4, "S11": s11}
        for name in only:
            print(T(), name, flush=True)
            if name in ("C2", "C3"):
                c2, c3, rows = c2_c3()
                res["rules"]["C2"] = c2; res["rules"]["C3"] = c3; res["claws_per_claw"] = rows
            else:
                res["rules"][name] = fns[name]()
            print(T(), name, res["rules"][name]["verdict"], flush=True)
        res["summary"] = {k: v["verdict"] for k, v in res["rules"].items()}
        res["date_partial_rerun"] = {"rules": only, "at": time.strftime("%Y-%m-%d %H:%M")}
        A.jdump(OUT, res)
        print(json.dumps(res["summary"], ensure_ascii=False))
        return
    t0 = time.time()
    res = {"schema": "GreatWave.AS04.rules_check/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "sample_ja": "美術の見本04（Q32）：主役波 K*′ AS04 ＋ ④ の別の青い波 wave4 ＋ AS04 Flat Smooth ＋ 爪 35 本（面の内 25・近い海 10）。t* = 12 s の静止",
           "requirements": A.rel(REPO + "/Docs/Design/Art_Requirements_ja.md"),
           "render": {"path": A.rel(RENDER), "report_sha256": A.sha(RENDER + "/as03asm_render_report.json")},
           "inputs": {A.rel(p): A.sha(p) for p in (A.UNION, A.WAVE4, A.HERO_SM04, A.ROWS04, A.GWB04, A.CLAWS04, A.ROWS02C, A.HERO_SM02C, A.CLAWS03, A.RELIEF03)},
           "judge_ja": "美術が届いたかは利用者が決める（Q29・Q30）。ここは測れる規則を通るかだけ。", "rules": {}}
    for name, fn in (("G1", g1), ("G2", g2), ("S4", s4), ("S8", s8), ("S9", s9), ("S10", s10), ("T4", t4)):
        print(T(), name, flush=True)
        res["rules"][name] = fn()
        print(T(), name, res["rules"][name]["verdict"], flush=True)
        A.jdump(OUT, res)
    print(T(), "C2C3", flush=True)
    c2, c3, rows = c2_c3()
    res["rules"]["C2"] = c2; res["rules"]["C3"] = c3; res["claws_per_claw"] = rows
    A.jdump(OUT, res)
    print(T(), "S11", flush=True)
    res["rules"]["S11"] = s11()
    res["summary"] = {k: v["verdict"] for k, v in res["rules"].items()}
    res["elapsed_s"] = round(time.time() - t0, 1)
    A.jdump(OUT, res)
    print(json.dumps(res["summary"], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
