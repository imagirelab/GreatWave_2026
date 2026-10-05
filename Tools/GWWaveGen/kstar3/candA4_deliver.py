# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: write the deliverables under Unity/Build/Q20L3/candA4/ (git-ignored).  Model-free (the reference
model's numbers come from numbers-only files; F13 is merged by the separate model-side script).
  kstarA4_a45.gwb / _rows.npz / _meta.json     same GWW0 topology / triangle order / UV scheme as K* 26修正01
  kstarA4_gate.json, fig_gate_overlay.png      painting gate (V1.preview_metrics, envelope)
  kstarA4_rubric_check.json / _table.md        official rubric (numpy-bool-safe recount); F13 merged later
  kstarA4_eval.json, fig_skydiff.png           sky difference vs K* / painting, mesh hygiene, landmarks
  kstarA4_q21_checks.json (+ loop 2 / K* for comparison)   Q21-1 / Q21-2 / Q21-3
  kstarA4_deformation.json, fig_deformation.png            painting-fit deformation: edges vs interior
  kstarA4_difference_record.json               vs the reference model (someone else's sculpture)
  fig_sections_*.png, fig_crestline.png, fig_band_b_region.png, fig_q21_bulge_maps.png
usage: py -3.10 candA4_deliver.py final_rows.npz design.json [--pre param_rows.npz]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys, json, hashlib, datetime, glob
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA_export as EX
import fin_eval as FE
import fin2_deliver as FD
import candA4_checks as CK
import candA4_model as M
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_check as RC

OUT = os.path.join(C.REPO, "Unity", "Build", "Q20L3", "candA4")
PRE = os.path.join(OUT, "kstarA4_a45")
WORK = os.path.join(OUT, "_work")
LOOP2 = os.path.join(C.REPO, "Unity", "Build", "Q20", "final", "kstarF_a45_rows.npz")
FONT = r"C:\Windows\Fonts\Deng.ttf"
HERE = os.path.dirname(os.path.abspath(__file__))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def deformation(c, A, Y, A0, Y0, sil_grown, sil):
    """painting-fit deformation field = final - parametric (pre-snap) form, split into the silhouette band and the
    interior; plus the local (high-frequency) part of the whole parametric fit (final minus a 6x12 smooth fit of it)."""
    D = np.linalg.norm(C.world(c, A, Y) - C.world(c, A0, Y0), axis=-1)
    live = (Y0 > 0.3) & (np.abs(c)[:, None] <= 16)
    edge = live & sil_grown; inner = live & ~sil_grown
    q = lambda v: {"n": int(v.size), "max_m": float(v.max()) if v.size else 0.0, "p99_m": float(np.percentile(v, 99)) if v.size else 0.0,
                   "mean_m": float(v.mean()) if v.size else 0.0, "share_moved_gt_2cm": float((v > 0.02).mean()) if v.size else 0.0}
    return {"definition": "3-D move of every vertex from the parametric sculpt (B-spline parameters fitted to the painting) to the final "
                          "(edge offset along the silhouette-forming edges only); edge band = vertices forming the painting-view outline "
                          "and everything within 1.5 m on the surface of them",
            "silhouette_edge_band": q(D[edge]), "interior": q(D[inner]), "silhouette_vertices_only": q(D[live & sil])}, D


def fig_maps(c, A, Y, D, sil_grown, path, title):
    nv, nu = A.shape
    img = np.clip(D / 0.5 * 255, 0, 255).astype(np.uint8)
    img = cv2.applyColorMap(img, cv2.COLORMAP_VIRIDIS)
    img[Y < 0.3] = (img[Y < 0.3] * 0.35).astype(np.uint8)
    ov = img.copy(); ov[sil_grown] = (0.6 * ov[sil_grown] + 0.4 * np.array([255, 255, 255])).astype(np.uint8)
    img = cv2.resize(ov, (nu * 3, nv * 3), interpolation=cv2.INTER_NEAREST)
    for j, nm in ((18, "j_B"), (90, "top"), (200, "tip"), (314, "corner"), (379, "facebot"), (394, "j_E")):
        cv2.line(img, (j * 3, 0), (j * 3, nv * 3), (255, 255, 255), 1); cv2.putText(img, nm, (j * 3 + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    for cc in (-20, -15, -10, -5, 0, 5, 10, 15):
        r = int(np.argmin(np.abs(c - cc))); cv2.line(img, (0, r * 3), (nu * 3, r * 3), (255, 255, 255), 1)
        cv2.putText(img, "c%+d" % cc, (4, r * 3 - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    bar = np.zeros((44, nu * 3, 3), np.uint8)
    for x in range(nu * 3):
        bar[:, x] = cv2.applyColorMap(np.array([[int(x / (nu * 3) * 255)]], np.uint8), cv2.COLORMAP_VIRIDIS)[0, 0]
    cv2.putText(bar, "0 m", (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(bar, title + "   0.5 m ->   (light = silhouette edge band)", (140, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    cv2.imwrite(path, np.vstack([img, bar]))


def fig_band(c, A, Y, path, q3):
    V1, tgt, fr = C.painting_frame()
    X = fr.world(c, A, Y); tris = V1.triangles(A.shape[1], A.shape[0])
    cov = V1.rasterize(fr.cam, X, tris) > 0.5
    base = cv2.imread(os.path.join(WORK, "painting_disp.png"))
    img = base.copy()
    over = img.copy(); over[cov] = (0.65 * img[cov] + 0.35 * np.array([150, 110, 60])).astype(np.uint8); img = over
    cn, _ = cv2.findContours(cov.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, cn, -1, (30, 30, 200), 1, cv2.LINE_AA)
    bt = json.load(open(os.path.join(HERE, "candA4_band_targets.json"), encoding="utf-8"))
    for k, col, th in (("top_raw", (255, 170, 255), 1), ("bottom_raw", (200, 150, 255), 1), ("top_smooth", (200, 0, 200), 2), ("bottom_smooth", (120, 0, 220), 2)):
        cv2.polylines(img, [np.array(bt[k]).round().astype(np.int32)], False, col, th, cv2.LINE_AA)
    for k, col in (("candidate_top_curve", (0, 200, 0)), ("candidate_bottom_curve", (0, 140, 0))):
        P = np.array(q3[k], float)
        if len(P) > 1:
            cv2.polylines(img, [P.round().astype(np.int32)], False, col, 2, cv2.LINE_AA)
    crop = img[300:680, 180:800]
    crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    txt = ("b region (Q21): painted band edges magenta/purple (thick = large-form target, smoothed 31 px; thin = raw), "
           "A4 ridge contour / claw edge green; blue = A4 painting-view outline")
    pad = np.full((40, crop.shape[1], 3), 250, np.uint8)
    cv2.putText(pad, txt[:130], (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
    cv2.imwrite(path, np.vstack([pad, crop]))


def difference_record(A, Y, c, R, ev, q21):
    H0 = float(Y[int(np.argmin(np.abs(c)))].max())
    base = FD.difference_record(A, Y, c, R, ev)       # per-c large forms vs the model (numbers-only) and K*
    def val(fid, sub):
        for x in R["checks"].get(fid, []):
            if sub in x["name"]:
                return x["value"]
    Hc = Y.max(1)
    Hat = lambda cs: [(float(cc), round(float(Hc[int(np.argmin(np.abs(c - cc)))]), 2)) for cc in cs]
    full = q21["Q21_2"]
    D = [
        {"id": "D1", "kind": "deliberate", "ja": "背は丸い塊（楕円の背＋短い凹の足）で、参照の彫りの波やシートの垂れはない。背の曲率の変わり目 1 回",
         "numbers": {"back_curvature_sign_changes_max": val("F03", "変わり目"), "back_roughness_max_x1e3": val("F03", "ざらつき"),
                     "back_convex_fraction_c0": full["rows"].get("+0", {}).get("back_convex_fraction"), "reference": "3~5 / 10~26（彫りの波）"}, "views": ["V3", "V5", "V8"]},
        {"id": "D2", "kind": "deliberate", "ja": "台座なしで海の上に置く。どの行にも前の谷（深さ 0.10~0.22H）があり、谷から平らな海へ一続き",
         "numbers": {"front_trough_D_over_H_median": val("F08", "谷の深さ"), "vertical_step_m": val("F08", "鉛直の段"), "reference": "球の台座の上"}, "views": ["V3", "V4", "V9"]},
        {"id": "D3", "kind": "forced + deliberate", "ja": "主断面の唇は原画の 132/72 の鉤（頂の弧 → 長い下り → 小さなくびれ → 鉤 → 丸い先）。参照の高い唇（0.8H、指）とは違う",
         "numbers": {"lip_thick_0p75_max_m": val("F06", "0.75"), "lip_thick_2m_max_m": val("F06", "2 m"), "reference_tip_height_over_H": 0.80}, "views": ["V1", "V2", "V7"]},
        {"id": "D4", "kind": "deliberate", "ja": "b 区域（第二の波頭）は手前の肩の行の唇そのもの：頂から下る面・浅い谷・稜（帯の上端）・鼻・爪の縁（帯の下端）を持つ滑らかな段。指・房の細部は写さない（段階 6）",
         "numbers": {k: q21.get("Q21_3", {}).get(k) for k in ("top_vs_top_smooth", "bottom_vs_bottom_smooth")}, "views": ["V1", "V7", "V8"]},
        {"id": "D5", "kind": "forced (retreat) + deliberate (shape)", "ja": "奥の端：原画で唇の下に見える空は、射線に沿って奥へ続く『のぞき穴』。奥の行はその穴を包む丸い管（C 字の断面）のまま、唇先の線が約 60° で後ろへ回り（なめらかな三日月）、穴の後ろで小さな巻きになって閉じる",
         "numbers": {"H_at_c": Hat((2, 4, 6, 8, 10, 12, 14, 16)), "far_sweep_deg": val("F10", "後ろへ流れる"), "far_volume_m3": val("F04", "体積")}, "views": ["V4", "V5", "V6", "V9"]},
        {"id": "D6", "kind": "forced + deliberate", "ja": "手前の頂の線は原画の 45° の波峰線（131/130/78）。参照の肩のように台座の端で切れず、滑らかに海へ下りる",
         "numbers": {"H_at_c": Hat((-24, -20, -17, -14, -11, -8, -5))}, "views": ["V1", "V6"]},
    ]
    base["differences"] = D
    base["method"] = ("the generator (Tools/GWWaveGen/kstar3/candA4_model.py + candA4_fit/farinit/edgesnap.py) never reads the model; "
                      "initial proportions from the rubric's numbers-only measurement of the model's big-wave sections")
    base["schema"] = "GreatWave.Q20L3.candA4.difference_record/1"
    return base


def main():
    rows, design = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    z = np.load(rows); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    A0 = z["A_param"].astype(float) if "A_param" in z.files else A.copy()
    Y0 = z["Y_param"].astype(float) if "Y_param" in z.files else Y.copy()
    info = EX.export(rows, PRE)
    lm, frac = FD.row_landmarks(A, Y, c)
    K = np.load(C.KSTAR_ROWS); kc = K["c"].astype(float)
    kidx = np.array([int(np.argmin(np.abs(kc - cc))) for cc in c])
    np.savez_compressed(PRE + "_rows.npz", A=A, Y=Y, c=c, P=np.stack([A[int(np.argmin(np.abs(c)))], Y[int(np.argmin(np.abs(c)))]], -1),
                        A_param=A0, Y_param=Y0, top_col=lm["top"], top_col_frac=frac, tip_col=lm["tip"], corner_col=lm["corner"],
                        facebot_col=lm["facebot"], c_kstar=kc[kidx], kstar_row=kidx)
    V1, tgt, fr = C.painting_frame()
    X = fr.world(c, A, Y); tris = V1.triangles(A.shape[1], A.shape[0])
    gate = V1.preview_metrics(fr, tgt, X, tris, os.path.join(OUT, "fig_gate_overlay.png"), "Q20 loop 3 cand A4 painting gate")
    basek = {"78": 1.37, "130": 1.80, "131": 1.47, "132": 1.40}
    ok = all(gate[k]["max_px"] <= 4 for k in basek) and gate["72"]["p95_px"] <= 4
    ok_k = all(gate[k]["max_px"] <= basek[k] + 0.5 for k in basek)
    json.dump({"preview_metrics_envelope": gate, "must_max_px": 4.0, "rubric_F01_also_within_K*+0.5": {k: basek[k] + 0.5 for k in basek},
               "must_72_p95_px": 4.0, "pass_4px": bool(ok), "pass_K*+0.5": bool(ok_k)}, open(PRE + "_gate.json", "w"), indent=1)
    print("gate", json.dumps({k: (gate[k]["max_px"], gate[k]["p95_px"]) for k in gate}), ok, ok_k, flush=True)
    ev, R = FE.evaluate(PRE + "_rows.npz", os.path.join(WORK, "evA4"))
    R["summary_recount"] = FE.recount(R)
    json.dump(R, open(PRE + "_rubric_check.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    open(PRE + "_rubric_check_table.md", "w", encoding="utf-8").write(RC.to_table(R) + "\n")
    json.dump(ev, open(PRE + "_eval.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    os.replace(os.path.join(WORK, "evA4_skydiff.png"), os.path.join(OUT, "fig_skydiff.png"))
    # Q21 checks (A4 + loop 2 + K* for comparison)
    q21 = CK.run(PRE + "_rows.npz", PRE + "_q21_checks.json", "A4")
    comp = {}
    for lab, p in (("loop2_Kstar_prime", LOOP2), ("Kstar_26r01", C.KSTAR_ROWS)):
        cp = os.path.join(WORK, "chk_%s.json" % lab)
        comp[lab] = CK.run(p, cp, lab, band=(lab == "loop2_Kstar_prime"))
    def brief(q):
        o = {"surface_fit_max_p99_m": {k: (None if v is None else [round(v["max_m"], 3), round(v["p99_m"], 3)]) for k, v in q["Q21_1"]["surface_fit_6x12"].items()},
             "sag3m_max_p99_m": [round(q["Q21_1"]["sag_3m"]["max_m"], 3), round(q["Q21_1"]["sag_3m"]["p99_m"], 3)],
             "sag3m_n_gt_0p3m": q["Q21_1"]["sag_3m"]["n_gt_0.3m"],
             "mean_curvature_extrema": q["Q21_1"]["mean_curvature_extrema"]["count"]}
        r2 = q["Q21_2"]["rows"]
        o["area_m2_c-2..+2"] = [round(r2[k]["area_m2"], 1) for k in ("-2", "-1", "+0", "+1", "+2")]
        o["shell_normal_over_H_c-2..+2"] = [None if r2[k]["shell_normal_median_over_H"] is None else round(r2[k]["shell_normal_median_over_H"], 3) for k in ("-2", "-1", "+0", "+1", "+2")]
        o["volume_above_water_m3"] = round(q["Q21_2"]["volume_above_water_c_-15_15_m3"], 1)
        if "Q21_3" in q:
            o["band"] = {k: q["Q21_3"][k] for k in ("top_vs_top_smooth", "bottom_vs_bottom_smooth", "top_vs_top_raw", "bottom_vs_bottom_raw")}
        return o
    summary = {"A4": brief(q21), **{k: brief(v) for k, v in comp.items()}}
    json.dump(summary, open(PRE + "_q21_summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("Q21", json.dumps(summary["A4"]), flush=True)
    # deformation field
    sil, grown, cov = CK.silhouette_band(c, A, Y, V1, fr)
    dj, Dm = deformation(c, A, Y, A0, Y0, grown, sil)
    json.dump(dj, open(PRE + "_deformation.json", "w", encoding="utf-8"), indent=1)
    fig_maps(c, A, Y, Dm, grown, os.path.join(OUT, "fig_deformation.png"), "edge offset (final - parametric sculpt)")
    # figures
    FD.fig_sections(A, Y, c, os.path.join(OUT, "fig_sections_kstar_candA4.png"), cs=(-16, -12, -8, -4, -1, 0, 1, 2, 4, 6, 9, 12))
    FD.fig_crestline(A, Y, c, os.path.join(OUT, "fig_crestline.png"))
    fig_band(c, A, Y, os.path.join(OUT, "fig_band_b_region.png"), q21["Q21_3"])
    # difference record
    rec = difference_record(A, Y, c, R, ev, q21)
    json.dump(rec, open(PRE + "_difference_record.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    # meta
    H = Y.max(1); main = int(np.argmin(np.abs(c)))
    km = json.load(open(C.KSTAR_META, encoding="utf-8"))
    code = {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(HERE, "candA4_*.py")) + glob.glob(os.path.join(HERE, "candA4_*.json")))}
    meta = {
        "schema": "GreatWave.GWWaveGen.kstar_meta/1", "number": "Q20 loop 3 candidate A4 (low-DOF parametric sculpt fitted to the painting by its edges)",
        "key": "a45", "generator": "Tools/GWWaveGen/kstar3/candA4_model.py (+ candA4_init/farinit/fit/edgesnap.py)",
        "generated_utc": datetime.datetime.utcnow().isoformat() + "Z", "alpha_deg": 45.0, "files": info,
        "nu": 400, "nv": int(len(c)), "vertex_count": int(A.size), "triangle_count": info["triangle_count"],
        "format_ja": km["format_ja"], "uv_layout_ja": km["uv_layout_ja"].replace("主断面 P0 の弧長", "主断面（c = 0 の行）の弧長"), "frame": km["frame"],
        "profile": {"index": dict(C.LM, main_row=main),
                    "landmark_definition": {
                        "j_B": "back foot (end of the concave foot fillet, the flat back sea begins) - same meaning as K*",
                        "j_top": "crest top = the design curve's point with a horizontal tangent (the chain starts there) - exact, every row",
                        "j_tip": "lip tip = apex of the round tip cap (half of the cap turn) - exact, every row",
                        "j_corner": "CHANGED vs K*: the barrel's rearmost point (min a of the underside + barrel curve)",
                        "j_facebot": "CHANGED vs K*: the bottom of the front trough (every row has a trough)",
                        "j_E": "front flat sea begins - same meaning as K*",
                        "columns_between_landmarks": "uniform arc length inside each of the 7 segments"},
                    "P0_final": np.stack([A[main], Y[main]], -1).round(5).tolist()},
        "rows": {"c_m": c.round(5).tolist(), "main_row": main, "H_m": H.round(4).tolist(),
                 "note": "rows c -60..-18 (growing spacing, 1.2 m at the left end), -18..+17 every 0.21 m; the far curl closes at c ~ +16.5"},
        "H0_m": float(H[main]), "highest_point": {"H_m": float(H.max()), "c_m": float(c[int(np.argmax(H))])},
        "painting_gate": gate, "painting_gate_pass_4px": bool(ok),
        "method_ja": "各行（c 一定の断面）を少数の接線連続の要素（楕円の背と凹の足、頂の弧から鉤までの 5 つの円弧、丸い先、下面のベジェ、2・3 次の調和を持つ丸い管、谷と前の海）で作り、各要素の値は c に沿った少数の節の 3 次スプライン。原画にはこの節の値だけを合わせ（輪郭 78/130/131/132/72、空への漏れと穴、b 区域の稜と爪の縁）、同時に 3 m の撓み（面の法線方向）と参照の比率への正則化をかけた。最後に輪郭を作る縁だけを数ピクセル分、法線方向へずらした（内側は動かない）。",
        "rubric_must_fail_recount": R["summary_recount"], "rubric_tool_summary": R["summary"],
        "q21_summary": summary["A4"], "deformation": dj,
        "reference_model_credit": "Reference: a scan of someone else's exhibited sculpture of Hokusai's Great Wave (author and collection unconfirmed, D18). Used only as a reference for large forms, layout and proportions; not copied.",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン（作者・所蔵は未確認、D18）。大きな形・配置・比率の考え方だけを参考にし、形は写していない。",
        "deliberate_differences_from_reference_ja": {d["id"]: d["ja"] + "（" + d["kind"] + "）" for d in rec["differences"]},
        "design": json.load(open(design, encoding="utf-8")), "code_sha256": code,
    }
    json.dump(meta, open(PRE + "_meta.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({"gate_pass_4px": ok, "must_fail": R["summary_recount"], "gwb": info["gwb_sha256"]}, default=float))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
