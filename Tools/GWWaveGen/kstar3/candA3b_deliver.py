# -*- coding: utf-8 -*-
"""Q21 candidate A3b: write the deliverables under Unity/Build/Q20L3/candA3b/ (git-ignored).
  kstarA3b_a45.gwb / _rows.npz / _meta.json   same GWW0 topology / triangle order / UV scheme as K* 26修正01
  candA3b_gate.json, fig_gate_overlay.png      painting gate (V1.preview_metrics, envelope)
  candA3b_rubric_check.json / _table.md        official rubric (numpy-bool-safe recount) + the Q21 checks
  candA3b_q21.json                             Q21-1 / Q21-2 / Q21-3 numbers (also for loop-2 K*' and K* 26修正01)
  candA3b_eval.json, fig_skydiff.png           sky difference, mesh hygiene, second-crest S1
  candA3b_f13.json                             F13 similarity (align B, rubric definition) and vs our placement
  candA3b_difference_record.json               vs the reference model (someone else's sculpture) + credit
  fig_sections_*.png, fig_deformation.png, fig_q21_bumps.png, fig_b_region_edges.png
usage: py -3.10 candA3b_deliver.py final_rows.npz candA3b_params.json"""
import sys, os, json, hashlib, datetime, glob, math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3b_common as B
import candA_export as EX
import fin_eval as FE
import candA3b_q21 as Q
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_check as RC

OUT = B.OUT
PRE = os.path.join(OUT, "kstarA3b_a45")
FONT = r"C:\Windows\Fonts\Deng.ttf"
LOOP2 = os.path.join(C.REPO, "Unity", "Build", "Q20", "final", "kstarF_a45_rows.npz")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def row_landmarks(A, Y, c):
    nv, nu = A.shape
    H = Y.max(1)
    out = {k: np.full(nv, -1, int) for k in ("top", "tip", "corner", "facebot")}
    for r in range(nv):
        if H[r] < 0.3:
            continue
        a, y = A[r], Y[r]
        jt = int(np.argmax(y[:200])); out["top"][r] = jt
        seg = np.arange(jt, 380); seg = seg[y[seg] > 0.3 * H[r]]
        jp = int(seg[np.argmax(a[seg])]) if len(seg) else 200; out["tip"][r] = jp
        seg2 = np.arange(jp, 395); seg2 = seg2[y[seg2] > 0.05 * H[r]]
        out["corner"][r] = int(seg2[np.argmin(a[seg2])]) if len(seg2) else 314
        out["facebot"][r] = int(300 + np.argmin(y[300:]))
    return out


def f13(A, Y, c):
    """share of our vertices (y > 1 m, |c| <= 16 m) within 0.3 m of the reference model's surface: (a) the rubric's
    definition (model in align B, its sea y 1.198 m -> 0), (b) the model placed as our large forms."""
    import candA3b_place as PL
    z = np.load(os.path.join(B.TMP, "ref_cache.npz"))
    V = z["V"].astype(float); F = z["tris"].astype(np.int64)
    S = C.sec(V); S[:, 1] -= 1.198
    pl = json.load(open(os.path.join(B.TMP, "placement.json")))
    Sp = PL.transform(S, np.array(pl["chosen"]["p"], float), np.array(pl["model_top_model_frame"], float))
    sel = (Y > 1.0) & (np.abs(c)[:, None] <= 16.0)
    Q_ = np.stack([A[sel], Y[sel], np.repeat(c, A.shape[1]).reshape(A.shape)[sel]], -1)
    res = {}
    for name, SS in (("align_B_rubric", S), ("our_placement", Sp)):
        cen = SS[F].mean(1)
        mids = np.concatenate([0.5 * (SS[F[:, 0]] + SS[F[:, 1]]), 0.5 * (SS[F[:, 1]] + SS[F[:, 2]])])
        kd = cKDTree(np.concatenate([SS, cen, mids]))
        d, _ = kd.query(Q_)
        res[name] = {"share_within_0.3m": float((d <= 0.3).mean()), "share_within_0.5m": float((d <= 0.5).mean()),
                     "median_dist_m": float(np.median(d)), "n": int(len(d))}
    return res


def fig_sections(A, Y, c, path, cs):
    import candA3b_q21 as Q_
    ms = Q_.model_sections(tuple(float(x) for x in cs))
    L2 = np.load(LOOP2)
    W_, H_ = 470, 330
    xl, yl = (-22.0, 18.0), (-6.0, 24.0)
    sx = W_ / (xl[1] - xl[0]); sy = H_ / (yl[1] - yl[0])
    nrow = (len(cs) + 3) // 4
    im = Image.new("RGB", (W_ * 4, (H_ + 26) * nrow + 44), (250, 250, 248)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 18); f2 = ImageFont.truetype(FONT, 15)
    d.text((8, 8), "c = const sections (K* frame, grid 5 m): red = A3b, blue = loop-2 K*' (Q21 rejected), grey = reference model placed as A3b's large forms (someone else's sculpture)", fill=(20, 20, 20), font=f)
    for k, cc in enumerate(cs):
        ox = (k % 4) * W_; oy = 40 + (k // 4) * (H_ + 26)
        X = lambda a, y: (ox + (a - xl[0]) * sx, oy + H_ - (y - yl[0]) * sy)
        for g in range(-20, 19, 5):
            d.line([X(g, yl[0]), X(g, yl[1])], fill=(230, 230, 230))
        for g in range(-5, 25, 5):
            d.line([X(xl[0], g), X(xl[1], g)], fill=(230, 230, 230) if g else (160, 180, 210))
        for sg in ms[float(cc)]:
            d.line([X(*sg[0]), X(*sg[1])], fill=(150, 150, 150), width=1)
        r2 = int(np.argmin(np.abs(L2["c"] - cc))); d.line([X(a, y) for a, y in zip(L2["A"][r2], L2["Y"][r2])], fill=(60, 110, 200), width=1)
        r = int(np.argmin(np.abs(c - cc))); d.line([X(a, y) for a, y in zip(A[r], Y[r])], fill=(215, 40, 40), width=2)
        d.text((ox + 6, oy + 4), "c = %+.1f m" % c[r], fill=(0, 0, 0), font=f2)
    im.save(path)


def fig_field(Fv, c, band, path, title, vmax, cmap=cv2.COLORMAP_VIRIDIS, signed=False):
    nv, nu = Fv.shape
    if signed:
        img = np.clip((Fv / vmax) * 127 + 128, 0, 255).astype(np.uint8)
        img = cv2.applyColorMap(img, cv2.COLORMAP_JET)
    else:
        img = cv2.applyColorMap(np.clip(Fv / vmax * 255, 0, 255).astype(np.uint8), cmap)
    img = cv2.resize(img, (nu * 3, nv * 3), interpolation=cv2.INTER_NEAREST)
    if band is not None:
        bb = cv2.resize(band.astype(np.uint8), (nu * 3, nv * 3), interpolation=cv2.INTER_NEAREST)
        cn, _ = cv2.findContours(bb, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(img, cn, -1, (255, 255, 255), 1)
    for j, nm in ((18, "j_B"), (90, "top"), (200, "tip"), (314, "corner"), (379, "facebot")):
        cv2.line(img, (j * 3, 0), (j * 3, nv * 3), (200, 200, 200), 1)
        cv2.putText(img, nm, (j * 3 + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    for cc in (-20, -15, -10, -5, 0, 3, 6, 10):
        r = int(np.argmin(np.abs(c - cc))); cv2.line(img, (0, r * 3), (40, r * 3), (255, 255, 255), 1)
        cv2.putText(img, "c%+d" % cc, (4, r * 3 - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    bar = np.zeros((44, nu * 3, 3), np.uint8)
    cv2.putText(bar, title, (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.imwrite(path, np.vstack([img, bar]))


def fig_b_edges(r3, A, Y, c, path):
    import candA3b_tier as TI
    V1, tgt, fr = C.painting_frame()
    X = fr.world(c, A, Y)
    cov = V1.rasterize(fr.cam, X, V1.triangles(A.shape[1], A.shape[0])) > 0.5
    img = np.asarray(Image.open(os.path.join(C.REPO, "Docs", "References", "Met_JP1847_DP130155.jpg")).convert("RGB")) if False else None
    base = (np.dstack([cov * 90] * 3) + 30).astype(np.uint8)
    xs = np.array(r3["xs"]); tp = np.array(r3["top_painted"]); lp = np.array(r3["lower_painted"])
    to = np.array(r3["top_ours"], float); lo = np.array(r3["lower_ours"], float)
    for arr, col in ((tp, (0, 255, 0)), (lp, (255, 160, 0))):
        cv2.polylines(base, [np.round(np.stack([xs, arr], -1)).astype(np.int32)], False, col, 2)
    for arr, col in ((to, (0, 0, 255)), (lo, (0, 0, 255))):
        ok = np.isfinite(arr)
        for x, y in zip(xs[ok], arr[ok]):
            cv2.circle(base, (int(x), int(y)), 1, col, -1)
    t, b = B.band_edges()
    cv2.polylines(base, [np.round(t).astype(np.int32)], False, (0, 120, 0), 1)
    cv2.polylines(base, [np.round(b).astype(np.int32)], False, (120, 80, 0), 1)
    crop = base[300:700, 150:800].copy()
    cv2.putText(crop, "b region: green = painted top edge (smoothed; thin = raw), orange = painted claw edge (smoothed), red dots = A3b roll", (6, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    cv2.imwrite(path, crop)


def main():
    rows, prm_path = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    z = np.load(rows); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    prm = json.load(open(prm_path, encoding="utf-8"))
    info = EX.export(rows, PRE)
    lm = row_landmarks(A, Y, c)
    K = np.load(C.KSTAR_ROWS); kc = K["c"].astype(float)
    kidx = np.array([int(np.argmin(np.abs(kc - cc))) for cc in c])
    extra = {k: z[k] for k in z.files if k not in ("A", "Y", "c")}
    np.savez_compressed(PRE + "_rows.npz", A=A, Y=Y, c=c, P=np.stack([A[159], Y[159]], -1), top_col=lm["top"], tip_col=lm["tip"],
                        corner_col=lm["corner"], facebot_col=lm["facebot"], c_kstar=kc[kidx], kstar_row=kidx, **extra)
    V1, tgt, fr = C.painting_frame()
    X = fr.world(c, A, Y); tris = V1.triangles(A.shape[1], A.shape[0])
    gate = V1.preview_metrics(fr, tgt, X, tris, os.path.join(OUT, "fig_gate_overlay.png"), "Q21 candidate A3b painting gate")
    ok = all(gate[k]["max_px"] <= 4 for k in ("78", "130", "131", "132")) and gate["72"]["p95_px"] <= 4
    json.dump({"preview_metrics_envelope": gate, "must": "78/130/131/132 max <= 4 px, 72 p95 <= 4 px (Q21 task)",
               "rubric_F01_strict_kstar_plus_0.5": {k: gate[k]["max_px"] <= b + 0.5 for k, b in {"78": 1.37, "130": 1.80, "131": 1.47, "132": 1.40}.items()},
               "pass": bool(ok)}, open(os.path.join(OUT, "candA3b_gate.json"), "w"), indent=1)
    print("gate", json.dumps({k: (round(gate[k]["max_px"], 2), round(gate[k]["p95_px"], 2)) for k in gate}), ok, flush=True)
    ev, R = FE.evaluate(PRE + "_rows.npz", os.path.join(OUT, "_work", "evA3b"))
    R["summary_recount"] = FE.recount(R)
    json.dump(ev, open(os.path.join(OUT, "candA3b_eval.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    os.replace(os.path.join(OUT, "_work", "evA3b_skydiff.png"), os.path.join(OUT, "fig_skydiff.png"))
    # Q21 checks (A3b, loop-2 K*', K* 26修正01)
    q = {}
    for lab, pth in (("A3b", PRE + "_rows.npz"), ("loop2_KstarF", LOOP2), ("kstar_26r01", C.KSTAR_ROWS)):
        q[lab] = Q.main(pth, os.path.join(OUT, "_work", "q21_%s.json" % lab), with_model=True, label=lab)
    json.dump(q, open(os.path.join(OUT, "candA3b_q21.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    R["checks"]["Q21"] = q21_checks(q)
    json.dump(R, open(os.path.join(OUT, "candA3b_rubric_check.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    open(os.path.join(OUT, "candA3b_rubric_check_table.md"), "w", encoding="utf-8").write(RC.to_table(R) + "\n")
    # F13
    f = f13(A, Y, c)
    json.dump(f, open(os.path.join(OUT, "candA3b_f13.json"), "w"), indent=1)
    print("F13", json.dumps(f), flush=True)
    # figures
    fig_sections(A, Y, c, os.path.join(OUT, "fig_sections_A3b_loop2_model.png"), [-14, -10, -7, -4, -2, 0, 1, 2, 3, 5, 7, 9])
    fz = np.load(os.path.join(OUT, "_work", "q21_A3b_fields.npz"))
    mag_lock = np.linalg.norm(C.world(c, A, Y) - C.world(c, z["A_prefit"], z["Y_prefit"]), axis=-1) if "A_prefit" in z.files else np.zeros_like(A)
    mag_tier = np.linalg.norm(C.world(c, z["A_prefit"], z["Y_prefit"]) - C.world(c, z["A_pretier"], z["Y_pretier"]), axis=-1) if "A_pretier" in z.files else np.zeros_like(A)
    fig_field(mag_lock, c, fz["band"], os.path.join(OUT, "fig_deformation_edge_lock.png"),
              "edge-only lock: 3-D move per vertex (0..0.8 m); white outline = the painting-silhouette edge band (4 m)", 0.8)
    fig_field(mag_tier, c, fz["band"], os.path.join(OUT, "fig_deformation_b_region_roll.png"),
              "b-region roll (design feature, not a painting fit): 3-D move per vertex (0..1.5 m)", 1.5)
    fig_field(fz["dev"], c, fz["band"], os.path.join(OUT, "fig_q21_deviation_from_lowpass.png"),
              "Q21-1: normal deviation from the 1.5 m low-pass surface (-1..+1 m); white = edge band", 1.0, signed=True)
    r3 = q["A3b"]["Q21_3"]
    r3full = Q.q21_3(c, A, Y, np.load(PRE + "_rows.npz"))
    fig_b_edges(r3full, A, Y, c, os.path.join(OUT, "fig_b_region_edges.png"))
    # difference record
    rec = difference_record(A, Y, c, R, ev, q, f)
    json.dump(rec, open(os.path.join(OUT, "candA3b_difference_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    # meta
    here = os.path.dirname(os.path.abspath(__file__))
    code = {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(here, "candA3b_*.py")) + [os.path.join(here, "candA3b_params.json")] +
                                                          [os.path.join(here, n) for n in ("candA_common.py", "candA_export.py", "candA_swarp.py", "fin2_warp.py", "fin2_relax.py", "fin2_design.py", "fin_eval.py")])}
    meta = {"schema": "GreatWave.GWWaveGen.kstar_meta/1", "number": "Q21 candidate A3b (loop 3)", "key": "a45",
            "date": datetime.date.today().isoformat(), "gwb": info, "grid": {"nu": 400, "nv": 240, "landmarks": C.LM, "main_row": 159},
            "frame": {"O": C.O.tolist(), "T": C.T.tolist(), "E": C.E.tolist(), "H0_kstar": C.H0_KSTAR},
            "H0_candidate": float(Y[159].max()), "Hmax": float(Y.max()), "c_Hmax": float(c[int(np.argmax(Y.max(1)))]),
            "method": ["1 reference big wave -> occupancy field (0.1 m voxels) -> Gaussian sigma 1.0 m (section) / 2.4 m (crest) -> large forms (candA3b_model.py; temporary, deleted)",
                       "2 whole-body placement: crest top on the K* anchor (a 0, c 0, H0), yaw 10 deg, 1.1 x along the crest (candA3b_place.py)",
                       "3 per-row design field: placed large forms (M, c <= 2.4) + our barrel around the painted sky pocket (S, c >= 1), smooth union, along-crest smoothing, uniform growth 0.35 m + smooth intersection with the painting's silhouette cone (edge-only carve), our foot / trough, our round back (area-targeted width, Q21-2), near shoulder beyond the model = our hump rows (candA3b_build.py, candA3b_sheet.py)",
                       "4 b-region roll on the shoulder face, from the painted band's edges (candA3b_tier.py)",
                       "5 edge-only silhouette lock (silhouette vertices only, compact falloff; candA3b_fit.py) + untangle"],
            "params": prm, "code_sha256": code, "rubric_summary": R["summary_recount"],
            "reference": "wave_repair_zbrush2.obj (SHA-256 AB4124F9...3D40) -- a scan of someone else's exhibited sculpture (author / collection unconfirmed, D18); its large forms were used as the base of this candidate (Q20: layout, proportions and 3-D large forms may be similar; details and the painting-view edges are ours). The mesh and all caches derived from it were deleted after the run (deleted_caches_sha256.txt)."}
    json.dump(meta, open(PRE + "_meta.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print("rubric", json.dumps(R["summary_recount"]))


def q21_checks(q):
    a = q["A3b"]; out = []
    def add(name, value, must, pm, note=""):
        out.append({"name": name, "value": value, "must": must, "target": "—", "pass_must": pm, "pass_target": None, "note": note})
    i1 = a["Q21_1"]["interior_total"]; l2 = q["loop2_KstarF"]["Q21_1"]["interior_total"]
    add("Q21-1 内側（縁の帯 4 m の外）の低域面からのずれ p99（m）", round(i1["dev_p99_m"], 3), "<= 第 2 回 K*′ の値", i1["dev_p99_m"] <= l2["dev_p99_m"] + 1e-9,
        "第 2 回 %.3f、最大 %.2f（第 2 回 %.2f）" % (l2["dev_p99_m"], i1["dev_max_m"], l2["dev_max_m"]))
    add("Q21-1 内側の平均曲率の極値（|ΔH| > 0.2/m、数）", i1["bumps"], "記録（第 2 回 %d）" % l2["bumps"], None)
    dl = a["Q21_1"].get("deform_edge_lock", {})
    if dl:
        add("Q21-1 原画合わせの変形（縁の固定）：内側の p95／最大（m）", [round(dl["interior"]["p95_m"], 3), round(dl["interior"]["max_m"], 3)],
            "内側 p95 <= 0.30 m", dl["interior"]["p95_m"] <= 0.30, "縁の帯：中央値 %.2f、p95 %.2f、最大 %.2f m" % (dl["edge_band"]["median_m"], dl["edge_band"]["p95_m"], dl["edge_band"]["max_m"]))
    s2 = a["Q21_2"]["summary"]
    add("Q21-2 断面積の比（参照の大きな形、c -8〜+3、範囲）", [round(s2["area_ratio_min"], 2), round(s2["area_ratio_max"], 2)], "0.85〜1.15",
        0.85 <= s2["area_ratio_min"] and s2["area_ratio_max"] <= 1.15, "中央値 %.2f。第 2 回 %.2f〜%.2f" % (s2["area_ratio_median"], q["loop2_KstarF"]["Q21_2"]["summary"]["area_ratio_min"], q["loop2_KstarF"]["Q21_2"]["summary"]["area_ratio_max"]))
    add("Q21-2 殻の厚みの比（範囲）", [round(s2["shell_ratio_min"], 2), round(s2["shell_ratio_max"], 2)], "0.85〜1.15",
        0.85 <= s2["shell_ratio_min"] and s2["shell_ratio_max"] <= 1.15, "中央値 %.2f" % s2["shell_ratio_median"])
    r3 = a["Q21_3"]
    add("Q21-3 b 区域の上端（px、最大／中央値）", [r3["top_edge_all"]["max_px"], r3["top_edge_all"]["median_px"]], "≈ 10 px",
        (r3["top_edge_all"]["max_px"] or 99) <= 12.0, "p90 %.1f" % r3["top_edge_all"]["p90_px"])
    add("Q21-3 b 区域の下端（爪の縁）（px、最大／中央値）", [r3["lower_edge_all"]["max_px"], r3["lower_edge_all"]["median_px"]], "≈ 10 px",
        (r3["lower_edge_all"]["max_px"] or 99) <= 12.0, "p90 %.1f" % r3["lower_edge_all"]["p90_px"])
    add("Q21-3 帯が大波の影の中にある割合", r3["band_pixels_inside_wave_silhouette"], "1.0", r3["band_pixels_inside_wave_silhouette"] >= 0.999)
    return out


def difference_record(A, Y, c, R, ev, q, f):
    s2 = q["A3b"]["Q21_2"]
    D = [
        {"id": "D1", "ja": "背：参照の急な背と台座の代わりに、頂から水平に出て丸く下り、凹の裾で海へ入る我々のドーム（幅は各行の断面積が参照の大きな形の 1.08 倍になるように決め、波峰に沿って平滑化）",
         "numbers": {"area_ratio_c-8..+3": [s2["summary"]["area_ratio_min"], s2["summary"]["area_ratio_max"]]}, "views": ["V3", "V5", "V8"]},
        {"id": "D2", "ja": "台座（球）をなくし、一面の海の上へ：壁は前の谷へ沈み、谷から平らな海へ（参照は台座の縁で切れる）",
         "numbers": {}, "views": ["V3", "V4", "V9"]},
        {"id": "D3", "ja": "原画視点の輪郭（78/130/131/132/72）は原画から：縁だけを原画の影の錐と交わらせ（一様に 0.35 m 大きくしてから切る）、残りを縁の固定で合わせた", "numbers": {"gate": {k: v for k, v in ev["gate"].items()}}, "views": ["V1", "V2", "V7"]},
        {"id": "D4", "ja": "b 区域（第二の波頭）：参照の 3 房と指は写さず、原画の帯の上端と爪の縁から決めた 1 本のなめらかな巻き（高さ 1.5 m）", "numbers": {"Q21_3": q["A3b"]["Q21_3"]}, "views": ["V1", "V7", "V8"]},
        {"id": "D5", "ja": "奥（c > +1）：参照の離れた角（奥の巻き）は使わず、原画の空の窓の後ろを包む我々の管と屋根。唇先は巻いて壁へ戻り、c +7〜+12 で海へ沈む", "numbers": {}, "views": ["V4", "V5", "V9"]},
        {"id": "D6", "ja": "手前の肩（c < -12）は参照の外：原画の 45° の波峰線に沿って、丸い丘へ形を変えながら海へ下りる我々の行", "numbers": {}, "views": ["V1", "V6"]},
    ]
    return {"schema": "GreatWave.Q21.candA3b.difference_record/1",
            "reference": "wave_repair_zbrush2.obj — a scan of someone else's exhibited sculpture (author and collection unconfirmed, D18).",
            "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。候補 A3b は、この作品の大きな形（ぼかした形）を土台にし、原画の輪郭・背・足・谷・奥・肩・b 区域を我々が作った。細部（指・爪・彫り）は使っていない。",
            "f13": f, "differences": D}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
