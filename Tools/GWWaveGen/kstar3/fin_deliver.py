# -*- coding: utf-8 -*-
"""Q20 final K*' (refined candidate A): write the deliverables under Unity/Build/Q20/final/ (git-ignored).
Model-free: the reference model's numbers come only from the rubric's numbers-only measurement
(Unity/Build/Q20/rubric/data/measure_ref_model.json); the F13 proximity is added by the separate analysis script in
Unity/Build/Q20/final/_analysis_model/ (which alone reads the OBJ, SHA-checked, through a temporary cache).
  kstarF_a45.gwb / _rows.npz / _meta.json   same GWW0 topology, triangle order and UV scheme as K* 26修正01
  kstarF_gate.json, fig_gate_overlay.png      painting gate (V1.preview_metrics, envelope)
  kstarF_rubric_check.json / _table.md        official rubric (numpy-bool-safe recount), F13 merged later
  kstarF_eval.json, fig_skydiff.png            sky difference vs K* / painting, mesh hygiene, second-crest S1, landmarks
  kstarF_difference_record.json                vs the reference model (someone else's sculpture): per-c large forms,
                                               D1..D6 with numbers, forced-by-painting vs deliberate
  fig_sections_kstar_final.png, fig_crestline.png, fig_warp_magnitude.png
usage: py -3.10 fin_deliver.py rows.npz fin_params.json"""
import sys, os, json, hashlib, datetime, math, glob
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA_export as EX
import fin_eval as FE
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_measure as RM
import rubric_check as RC

OUT = os.path.join(C.REPO, "Unity", "Build", "Q20", "final")
PRE = os.path.join(OUT, "kstarF_a45")
FONT = r"C:\Windows\Fonts\Deng.ttf"
REF_MEAS = os.path.join(C.REPO, "Unity", "Build", "Q20", "rubric", "data", "measure_ref_model.json")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def row_landmarks(A, Y, c):
    """per-row landmark columns of the final geometry (for the motion re-target)."""
    nv, nu = A.shape
    H = Y.max(1)
    out = {k: np.full(nv, -1, int) for k in ("top", "tip", "corner", "facebot")}
    frac = np.full(nv, np.nan)
    for r in range(nv):
        if H[r] < 0.3:
            continue
        a, y = A[r], Y[r]
        jt = int(np.argmax(y[:200])); out["top"][r] = jt
        s = C.arclen(a, y); frac[r] = s[jt] / s[-1]
        seg = np.arange(jt, 380); seg = seg[y[seg] > 0.3 * H[r]]
        jp = int(seg[np.argmax(a[seg])]) if len(seg) else 200; out["tip"][r] = jp
        seg2 = np.arange(jp, 395); seg2 = seg2[y[seg2] > 0.05 * H[r]]
        out["corner"][r] = int(seg2[np.argmin(a[seg2])]) if len(seg2) else 314
        out["facebot"][r] = int(300 + np.argmin(y[300:]))
    return out, frac


def fig_sections(A, Y, c, path, cs=(-14, -10, -6, -3, 0, 1, 2, 3, 4, 5, 6, 8)):
    K = np.load(C.KSTAR_ROWS)
    W_, H_ = 470, 330
    xl, yl = (-22.0, 18.0), (-6.0, 23.0)
    sx = W_ / (xl[1] - xl[0]); sy = H_ / (yl[1] - yl[0])
    im = Image.new("RGB", (W_ * 4, (H_ + 26) * 3 + 44), (250, 250, 248)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 18); f2 = ImageFont.truetype(FONT, 15)
    d.text((8, 8), "c = const sections (K* frame, grid 5 m): red = K*' final, blue = K* 26修正01 (current), grey dashed = still water", fill=(20, 20, 20), font=f)
    for k, cc in enumerate(cs):
        ox = (k % 4) * W_; oy = 40 + (k // 4) * (H_ + 26)
        for g in range(-20, 19, 5):
            d.line([(ox + (g - xl[0]) * sx, oy), (ox + (g - xl[0]) * sx, oy + H_)], fill=(230, 230, 230))
        for g in range(-5, 24, 5):
            d.line([(ox, oy + H_ - (g - yl[0]) * sy), (ox + W_, oy + H_ - (g - yl[0]) * sy)], fill=(230, 230, 230) if g else (160, 180, 210))
        def pl(a, y, col, w=2):
            d.line([(ox + (aa - xl[0]) * sx, oy + H_ - (yy - yl[0]) * sy) for aa, yy in zip(a, y)], fill=col, width=w)
        rk = int(np.argmin(np.abs(K["c"] - cc))); pl(K["A"][rk], K["Y"][rk], (60, 110, 200), 1)
        r = int(np.argmin(np.abs(c - cc))); pl(A[r], Y[r], (215, 40, 40), 2)
        d.text((ox + 6, oy + 4), "c = %+.1f m" % c[r], fill=(0, 0, 0), font=f2)
    im.save(path)


def crest_lines(A, Y, c, H0):
    H = Y.max(1)
    at = np.full(len(c), np.nan); tip = np.full(len(c), np.nan)
    for r in range(len(c)):
        if H[r] < 2.0:
            continue
        m = RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0) or {}
        at[r] = m.get("a_top", np.nan); tip[r] = m.get("a_tip", np.nan)
    return H, at, tip


def fig_crestline(A, Y, c, path):
    K = np.load(C.KSTAR_ROWS)
    H0 = Y[int(np.argmin(np.abs(c)))].max()
    Hf, atf, tipf = crest_lines(A, Y, c, H0)
    Hk, atk, tipk = crest_lines(K["A"], K["Y"], K["c"], H0)
    Wd, Hh = 1400, 820
    im = Image.new("RGB", (Wd, Hh), (250, 250, 248)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 18)
    d.text((10, 8), "top: plan (a of the crest top = solid, lip tip = dashed) along c; bottom: elevation H(c).  red = K*' final, blue = K* 26修正01", fill=(0, 0, 0), font=f)
    cx = lambda cc: 60 + (cc + 24) / 40 * (Wd - 100)
    def panel(oy, h, lo, hi, series, lab):
        d.rectangle([60, oy, Wd - 40, oy + h], outline=(180, 180, 180))
        for g in np.arange(-24, 17, 2):
            d.line([(cx(g), oy), (cx(g), oy + h)], fill=(235, 235, 235)); d.text((cx(g) - 8, oy + h + 2), "%d" % g, fill=(90, 90, 90), font=f)
        for g in np.arange(math.ceil(lo), hi + 1e-9, 2 if hi - lo < 30 else 5):
            yy = oy + h - (g - lo) / (hi - lo) * h
            d.line([(60, yy), (Wd - 40, yy)], fill=(235, 235, 235)); d.text((20, yy - 9), "%g" % g, fill=(90, 90, 90), font=f)
        for cc, v, col, dash in series:
            pts = [(cx(a), oy + h - (b - lo) / (hi - lo) * h) for a, b in zip(cc, v) if np.isfinite(b) and -24 <= a <= 16]
            if dash:
                for i in range(0, len(pts) - 1, 3):
                    d.line(pts[i:i + 2], fill=col, width=2)
            else:
                d.line(pts, fill=col, width=2)
        d.text((65, oy + 4), lab, fill=(0, 0, 0), font=f)
    panel(40, 330, -12, 14, [(K["c"], atk, (60, 110, 200), False), (K["c"], tipk, (60, 110, 200), True),
                             (c, atf, (215, 40, 40), False), (c, tipf, (215, 40, 40), True)], "plan: a (m)")
    panel(420, 330, 0, 24, [(K["c"], Hk, (60, 110, 200), False), (c, Hf, (215, 40, 40), False)], "elevation: H (m)")
    im.save(path)


def fig_warp(z, c, path):
    M = z["warp_mag"]; Y0 = z["Y_pre"]
    nv, nu = M.shape
    img = np.clip(M / 2.0 * 255, 0, 255).astype(np.uint8)
    img = cv2.applyColorMap(img, cv2.COLORMAP_VIRIDIS)
    img[Y0 < 0.02] = (img[Y0 < 0.02] * 0.35).astype(np.uint8)
    img = cv2.resize(img, (nu * 3, nv * 3), interpolation=cv2.INTER_NEAREST)
    for j, nm in ((18, "j_B"), (90, "top"), (200, "tip"), (314, "corner"), (379, "facebot"), (394, "j_E")):
        cv2.line(img, (j * 3, 0), (j * 3, nv * 3), (255, 255, 255), 1)
        cv2.putText(img, nm, (j * 3 + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    for cc in (-20, -15, -10, -5, 0, 3, 6, 10):
        r = int(np.argmin(np.abs(c - cc))); cv2.line(img, (0, r * 3), (nu * 3, r * 3), (255, 255, 255), 1)
        cv2.putText(img, "c%+d" % cc, (4, r * 3 - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    bar = np.zeros((40, nu * 3, 3), np.uint8)
    for x in range(nu * 3):
        bar[:, x] = cv2.applyColorMap(np.array([[int(x / (nu * 3) * 255)]], np.uint8), cv2.COLORMAP_VIRIDIS)[0, 0]
    cv2.putText(bar, "0 m", (4, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(bar, "2.0 m  (3-D move of each vertex: pre-warp design -> final; dark = flat sea)", (nu * 3 - 700, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imwrite(path, np.vstack([img, bar]))


def ours_at(A, Y, c, H0, cc):
    r = int(np.argmin(np.abs(c - cc)))
    segs = RM.poly_to_segs(A[r], Y[r])
    m = RM.section_metrics(segs, 0.0, H0, open_w=0.0) or {}
    if m.get("H", 0) >= 0.5 * H0:
        m.update(RM.back_shape(segs, 0.0, m["H"], m["a_top"]))
    return m, float(c[r])


def difference_record(A, Y, c, R_rubric, ev):
    H0 = float(Y[int(np.argmin(np.abs(c)))].max())
    ref = json.load(open(REF_MEAS, encoding="utf-8"))
    K = np.load(C.KSTAR_ROWS)
    keys = ["H_over_H0", "a_top", "theta_c_deg", "overhang_over_H", "lip_thick_0p75_m", "lip_thick_2m_m", "wall_50_over_H",
            "back_slope_max_deg", "front_trough_depth_over_H", "back_R_over_H", "back_longest_straight_over_H"]
    rows = []
    for cc in np.arange(-12.0, 12.01, 1.0):
        rm = ref["sections"].get("%.1f" % cc) or ref["sections"].get(str(float(cc)))
        ofin, cfin = ours_at(A, Y, c, H0, cc)
        oks, cks = ours_at(K["A"].astype(float), K["Y"].astype(float), K["c"].astype(float), H0, cc)
        rows.append({"c": float(cc), "final_row_c": cfin,
                     "final": {k: (round(float(ofin[k]), 3) if ofin.get(k) is not None and np.isfinite(ofin.get(k)) else None) for k in keys},
                     "reference_model": {k: (round(float(rm[k]), 3) if rm and rm.get(k) is not None else None) for k in keys},
                     "kstar_26r01": {k: (round(float(oks[k]), 3) if oks.get(k) is not None and np.isfinite(oks.get(k)) else None) for k in keys}})
    chk = {x["name"]: x for L in R_rubric["checks"].values() for x in L}
    def val(fid, sub):
        for x in R_rubric["checks"].get(fid, []):
            if sub in x["name"]:
                return x["value"]
    Hc = Y.max(1)
    far = [(round(float(cc), 1), round(float(Hc[int(np.argmin(np.abs(c - cc)))]), 2)) for cc in (3, 5, 7, 9, 11)]
    near = [(round(float(cc), 1), round(float(Hc[int(np.argmin(np.abs(c - cc)))]), 2)) for cc in (-18, -15, -12, -9, -6)]
    D = [
        {"id": "D1", "kind": "deliberate", "ja": "背の輪郭を参照モデルより滑らかに（超楕円のドーム＋凹の足、曲率の変わり目 1 回）",
         "numbers": {"back_curvature_sign_changes_max": val("F03", "変わり目"), "back_roughness_max_x1e3": val("F03", "ざらつき"),
                     "reference": "3~5 / 10~26（彫りの波）"}, "views": ["V3", "V5", "V8"]},
        {"id": "D2", "kind": "deliberate", "ja": "球の台座・箱の台をなくし、一面の海の上に置く（面は前の谷へ沈み、谷から平らな海へ一続き）",
         "numbers": {"front_trough_D_over_H_median": val("F08", "谷の深さ"), "vertical_step_m": val("F08", "鉛直の段"),
                     "reference": "台座（ボウル）の上"}, "views": ["V3", "V4", "V9"]},
        {"id": "D3", "kind": "deliberate (partly forced)", "ja": "唇先は原画の 132/72 から（薄い刃が巻いて下へ垂れる鉤）。参照の短い爪の唇は使わない。爪は段階 6",
         "numbers": {"main_row_tip_a_m": round(float(ofin_main.get("a_tip", np.nan)), 2) if (ofin_main := ours_at(A, Y, c, H0, 0.0)[0]) else None,
                     "main_row_tip_y_m": round(float(ofin_main.get("y_tip", np.nan)), 2),
                     "lip_thick_0p75_max_m": val("F06", "0.75"), "lip_thick_2m_max_m": val("F06", "2 m"),
                     "reference_lip_thick_m": "0.30~0.39 / 0.40~0.53", "forced_note_ja": "原画の唇の帯（132 と 72 の間、主断面で 4~7 m）を覆うため、主断面の近くの行の唇は参照より厚い（原画が決める）"},
         "views": ["V1", "V2", "V7"]},
        {"id": "D4", "kind": "deliberate", "ja": "第二の波頭は原画の帯から（手前の肩の行の唇の段が帯の高さ 8~12 m に来る）。参照の 3 房・14 本の指・ポケットは写さない（管の壁の房はなくした）",
         "numbers": {"S1_share_on_second_tier": round(ev["S1"]["share_on_second_tier"], 3), "fingers": 0, "tube_wall_lobes": 0,
                     "reference": "房 3・指 14・ポケット"}, "views": ["V1", "V7", "V8"]},
        {"id": "D5", "kind": "deliberate (shape) / forced (retreat)", "ja": "奥の端：開いた管の口（原画の空の窓を包む薄いフード）から、窓の後ろで巻きが小さくなり海へ消える（参照は c +12 まで屋根が続く）",
         "numbers": {"H_at_c": far, "far_sweep_deg": val("F10", "後ろへ流れる"), "far_volume_m3": val("F04", "体積"),
                     "forced_note_ja": "原画視点で唇の下の空（72 の窓）は射線に沿って奥へ続くので、低くなる奥の行はその後ろ（-a）へ下がるしかない（奥の流れ角 約 50° は原画が決める。B は面を切って 0° にした）"},
         "views": ["V4", "V5", "V9"]},
        {"id": "D6", "kind": "forced + deliberate", "ja": "手前の頂の線は原画の 45° の波峰線（131/130/78）。参照の肩のように台座の端で切れず、海へ下りる",
         "numbers": {"H_at_c": near}, "views": ["V1", "V6"]},
    ]
    return {"schema": "GreatWave.Q20.final.difference_record/1",
            "reference": "wave_repair_zbrush2.obj — a scan of someone else's exhibited sculpture (author and collection unconfirmed, D18); used as a reference only. Numbers of the model come from the rubric's numbers-only measurement (align B, sea y 1.198 m).",
            "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。大きな形と配置の考え方だけを参考にし、形は写していない。",
            "method": "the generator (Tools/GWWaveGen/kstar3/fin_*.py) never reads the model; knot tables set from numbers and the painting.",
            "per_c_large_forms": rows, "differences": D,
            "proximity_F13": "filled by Unity/Build/Q20/final/_analysis_model/fin_model_measure.py (temporary cache, SHA logged)"}


def main():
    rows, prm_path = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    z = np.load(rows); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    prm = json.load(open(prm_path, encoding="utf-8"))
    info = EX.export(rows, PRE)
    lm, frac = row_landmarks(A, Y, c)
    K = np.load(C.KSTAR_ROWS); kc = K["c"].astype(float)
    kidx = np.array([int(np.argmin(np.abs(kc - cc))) for cc in c])
    np.savez_compressed(PRE + "_rows.npz", A=A, Y=Y, c=c, P=np.stack([A[159], Y[159]], -1), A_pre=z["A_pre"], Y_pre=z["Y_pre"],
                        warp_mag=z["warp_mag"], prefit_scale=z["prefit_scale"], top_col=lm["top"], top_col_frac=frac, tip_col=lm["tip"],
                        corner_col=lm["corner"], facebot_col=lm["facebot"], c_kstar=kc[kidx], kstar_row=kidx)
    # gate
    V1, tgt, fr = C.painting_frame()
    X = fr.world(c, A, Y); tris = V1.triangles(A.shape[1], A.shape[0])
    gate = V1.preview_metrics(fr, tgt, X, tris, os.path.join(OUT, "fig_gate_overlay.png"), "Q20 K*' final painting gate")
    base = {"78": 1.37, "130": 1.80, "131": 1.47, "132": 1.40}
    ok = all(gate[k]["max_px"] <= 4 and gate[k]["max_px"] <= base[k] + 0.5 for k in base) and gate["72"]["p95_px"] <= 4
    json.dump({"preview_metrics_envelope": gate, "must_max_px": {k: base[k] + 0.5 for k in base}, "must_72_p95_px": 4.0,
               "kstar_26r01_72_max_px": 5.50, "pass": bool(ok)}, open(os.path.join(OUT, "kstarF_gate.json"), "w"), indent=1)
    # rubric + eval
    ev, R = FE.evaluate(PRE + "_rows.npz", os.path.join(OUT, "_work", "evF"))
    R["summary_recount"] = FE.recount(R)
    json.dump(R, open(os.path.join(OUT, "kstarF_rubric_check.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    open(os.path.join(OUT, "kstarF_rubric_check_table.md"), "w", encoding="utf-8").write(RC.to_table(R) + "\n")
    json.dump(ev, open(os.path.join(OUT, "kstarF_eval.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    os.replace(os.path.join(OUT, "_work", "evF_skydiff.png"), os.path.join(OUT, "fig_skydiff.png"))
    # difference record
    rec = difference_record(A, Y, c, R, ev)
    json.dump(rec, open(os.path.join(OUT, "kstarF_difference_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    # figures
    fig_sections(A, Y, c, os.path.join(OUT, "fig_sections_kstar_final.png"))
    fig_crestline(A, Y, c, os.path.join(OUT, "fig_crestline.png"))
    fig_warp(z, c, os.path.join(OUT, "fig_warp_magnitude.png"))
    # meta
    H = Y.max(1); main = 159
    km = json.load(open(C.KSTAR_META, encoding="utf-8"))
    wj = os.path.splitext(rows)[0] + "_warp.json"
    warp = json.load(open(wj)) if os.path.isfile(wj) else {}
    code = {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fin_*.py")) +
                                                          [os.path.join(os.path.dirname(os.path.abspath(__file__)), n) for n in
                                                           ("candA_common.py", "candA_warp.py", "candA_swarp.py", "candA_prefit.py", "candA_export.py")])}
    meta = {
        "schema": "GreatWave.GWWaveGen.kstar_meta/1", "number": "Q20 final K*' (refined candidate A, loop 1)", "key": "a45",
        "generator": "Tools/GWWaveGen/kstar3/fin_design.py + fin_pipeline.py (secondary design from numbers and the painting; painting-silhouette lock)",
        "generated_utc": datetime.datetime.utcnow().isoformat() + "Z", "alpha_deg": 45.0, "files": info,
        "nu": 400, "nv": int(len(c)), "vertex_count": int(A.size), "triangle_count": info["triangle_count"],
        "format_ja": km["format_ja"], "uv_layout_ja": km["uv_layout_ja"].replace("主断面 P0 の弧長", "主断面（行 159）の弧長"), "frame": km["frame"],
        "profile": {"index": dict(C.LM, main_row=main),
                    "landmark_definition": {
                        "j_B": "back foot (surface leaves the flat back sea) - same meaning as K*",
                        "j_top": "crest top of the DESIGN curve; after the warp the row's highest vertex is stored per row as top_col / top_col_frac in the rows npz (the column may differ from 90 on the near shoulder)",
                        "j_tip": "lip nose = most forward point between the crest and the tube wall (above 0.3 H) - same meaning as K*; per-row tip_col in the rows npz",
                        "j_corner": "CHANGED vs K*: the tube's back-most point (K*: the corner between the lip underside and the inner wall); per-row corner_col",
                        "j_facebot": "CHANGED vs K*: the trough bottom in front of / under the tube (K*: the bottom of the vertical face / plinth); per-row facebot_col",
                        "j_E": "front flat sea begins - same meaning as K*",
                        "columns_between_landmarks": "graded arc-length spacing (no spacing jump at a landmark)"},
                    "motion_retarget_note_ja": "ds27/ds28 は K* の目印の列を前提にしている。j_corner と j_facebot の意味が変わった（上）。行ごとの top_col / tip_col / corner_col / facebot_col と、K* の対応する行（kstar_row, c_kstar）を rows npz に入れた。奥の行（c > 0）は K* と違い c +12.2 で海へ消える。",
                    "P0_final": np.stack([A[main], Y[main]], -1).round(5).tolist()},
        "rows": {"c_m": c.round(5).tolist(), "main_row": main, "H_m": H.round(4).tolist(),
                 "note": "rows 0..159 c -60..0 (0.2 m to -22 m, growing beyond), rows 160..239 c 0..+12.2 (0.127 m to ~+9.4, growing)"},
        "H0_m": float(H[main]), "highest_point": {"H_m": float(H.max()), "c_m": float(c[int(np.argmax(H))])},
        "painting_gate": gate, "painting_gate_pass": bool(ok),
        "warp": {"method_ja": "設計形 → 手前の肩の高さの前合わせ → 原画画面の薄板スプライン 5 回（3 次元の近さ 4 m）→ 頂の曲率の下限（1.75 m）と行をまたぐ平滑化 → 面の中の局所の締め → 原画の関門を満たすまで局所の締め＋曲率の下限 → 自己交差の解消",
                 "warp_mag_max_m": warp.get("warp_mag_max_m"), "warp_mag_p95_m": warp.get("warp_mag_p95_m"), "warp_mag_p50_m": warp.get("warp_mag_p50_m")},
        "rubric_must_fail_recount": R["summary_recount"], "rubric_tool_summary": R["summary"],
        "reference_model_credit": "Reference: a scan of someone else's exhibited sculpture of Hokusai's Great Wave (author and collection unconfirmed, D18). Used only as a reference for large forms and layout; not copied.",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン（作者・所蔵は未確認、D18）。大きな形と配置の考え方だけを参考にし、形は写していない。",
        "deliberate_differences_from_reference_ja": {d["id"]: d["ja"] + "（" + d["kind"] + "）" for d in rec["differences"]},
        "params": prm, "code_sha256": code,
    }
    json.dump(meta, open(PRE + "_meta.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({"gate_pass": ok, "must_fail": R["summary_recount"], "gwb": info["gwb_sha256"]}, default=float))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
