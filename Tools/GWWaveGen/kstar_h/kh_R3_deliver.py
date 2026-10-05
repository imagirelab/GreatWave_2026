# -*- coding: utf-8 -*-
"""K*′ 精修 R3 の納品（kh_R2_deliver.py の R3 版）：設計の json → Houdini のシーン → 橋で格子へ → 同じ評価器 → 追加の検査 → 図と対照表（py -3.10）。

  py -3.10 kh_R3_deliver.py <design.json> [--out Unity/Build/Q20H/final] [--hip Houdini/Design28R01/kstar_h_R3.hiplc]
                            [--no-eval] [--no-turntable]
手順
  1 hython kh_design_sceneR3.py：土台のシーン（kstar_h_base.hiplc）に /obj/kstar_h_design（CTRL → guides → far_smooth → back_shape → lip_profile →
    bregion_ledge → lip_head → side_edges → skin → OUT）を組み、参照モデルの節点を消して保存・cook・検査（CTRL = json、Houdini と numpy の一致、
    行の面、参照のパスの文字列 0）
  2 hython kh_bridge.py h2g（attr の列、行は kh_row_c）→ kstarR3_a45.gwb / _rows.npz / .obj / _meta.json（meta に目印・H0・出典を足す）
  3 kh_eval.py（関門・ルーブリック（Tools/GWWaveGen/rubric、F03 は 2026-09-29 に緩めた版）・Q21・空の差・メッシュ・F13、Blender の 9+4 視点、
    ターンテーブル）：R3 と R2・A4・K*
  4 追加：大きな輪郭の関門と重ね図、評審 R2 の測り（上から見た背のくびれ notch、膨らみ R4 / R6 の区域ごと、bump4、メッシュの衛生）、
    形の検査、b 区域の帯、Blender BVH の三角形どうしの交差（R3・R2）、断面図、対照図（R3 | R2 | A4 | K* | 参照は数値だけ）
参照モデル（他者の作品）の画像は対照図に入れない（数値の欄だけ）。
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys
import json
import time
import shutil
import argparse
import subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import kh_common as KC  # noqa: E402

OUT_DEF = os.path.join(KC.OUT_ROOT, "final")
HIP_DEF = os.path.join(KC.HIP_DIR, "kstar_h_R3.hiplc")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MSYS_NO_PATHCONV="1", PYTHONIOENCODING="utf-8")
R2_ROWS = os.path.join(KC.OUT_ROOT, "final", "_R2", "kstarR2_a45_rows.npz")
R2_GWB = os.path.join(KC.OUT_ROOT, "final", "_R2", "kstarR2_a45.gwb")
PRE = "kstarR3_a45"
REF_NUMBERS = os.path.join(KC.REPO, "Unity", "Build", "Q20L3", "candA4", "_model_side", "ref_fullness.json")


def run(cmd, log, timeout=1800, cwd=None):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, cwd=cwd or KC.OUT_ROOT, encoding="utf-8", errors="replace")
    open(log, "w", encoding="utf-8").write("$ %s\n\n%s\n---- stderr\n%s" % (" ".join(cmd), r.stdout[-30000:], r.stderr[-8000:]))
    if r.returncode != 0:
        raise RuntimeError("failed (%d): %s — see %s" % (r.returncode, cmd[1] if len(cmd) > 1 else cmd, log))
    return r.stdout, round(time.time() - t, 1)


def notch_interior(c, A, Y, heights=(3.0, 6.0, 10.0)):
    """the judges' notch, but only where both chord ends (c +-4 m) lie inside the measured range (the judges' script clamps the left chord end
    at c -14 to the point itself, so for c -14 .. -10.5 it reports half the plan slope, not a notch)."""
    nv = len(c)
    H = Y.max(1); top = Y.argmax(1)
    out = {}
    for h in heights:
        ab = np.full(nv, np.nan)
        for r in range(nv):
            if H[r] < h + 0.5:
                continue
            yy = Y[r, :top[r] + 1]; aa = A[r, :top[r] + 1]
            i = np.nonzero(yy >= h)[0]
            if len(i) == 0:
                continue
            i = i[0]
            if i == 0:
                ab[r] = aa[0]; continue
            t = (h - yy[i - 1]) / (yy[i] - yy[i - 1]); ab[r] = aa[i - 1] + t * (aa[i] - aa[i - 1])
        m = np.isfinite(ab)
        cq = np.arange(-18.0, 14.01, 0.5)
        v = np.interp(cq, c[m], ab[m]); v[(cq < c[m].min()) | (cq > c[m].max())] = np.nan
        best = (-9.0, None)
        for i, cc in enumerate(cq):
            j0 = np.searchsorted(cq, cc - 4 - 1e-9); j1 = np.searchsorted(cq, cc + 4 - 1e-9)
            if cq[j0] != cc - 4 or j1 >= len(cq) or cq[j1] != cc + 4:
                continue
            if not (np.isfinite(v[j0]) and np.isfinite(v[j1]) and np.isfinite(v[i])):
                continue
            dv = v[i] - 0.5 * (v[j0] + v[j1])
            if dv > best[0]:
                best = (dv, cc)
        out["y%g" % h] = {"notch_max_m": round(float(best[0]), 3), "at_c": best[1]}
    return out


def supplementary(rows, out, label):
    sys.path.insert(0, os.path.join(KC.REPO, "Tools", "GWWaveGen", "kstar3"))
    import kh_gate_lfA as KG
    import kh_fitA as KF
    import kh_R1_quick as Q
    import kh_R3_quick as Q3
    import candA4_fit as F
    z = np.load(rows); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    res = {}
    g = KG.LFGate()
    lf, cov = g.measure_rows(c, A, Y)
    res["gate_large_form"] = lf
    if label == "R3":
        KG.overlay(os.path.join(out, "fig_gate_large_form.png"), g, cov, "R3: large-form gate 132 %.2f / 72 p95 %.2f px" % (lf["132"]["max_px"], lf["72"]["p95_px"]))
    res["shape_checks"] = Q.shape_checks(c, A, Y)
    res["judge_R2_notch_as_scripted"] = Q3.back_plan_notch(c, A, Y)
    res["judge_R2_notch_interior_chords"] = notch_interior(c, A, Y)
    res["bulge6_regions"] = Q3.bulge_regions(c, A, Y)
    res["bump4"] = Q3.bump(c, A, Y)
    res["mesh"] = Q3.mesh(c, A, Y)
    ctx = KF.Ctx()
    sdf, covb, X = ctx.cov_sdf(c, A, Y)
    rws = np.nonzero((c > -18.5) & (c < -3.5))[0]
    tp, bp = F.band_curves(ctx.base, c, A, Y, X, rws)
    rt = F.curve_vs_target(tp, ctx.base.band_top); rb = F.curve_vs_target(bp, ctx.base.band_bot)
    res["band_round3_detector"] = {"ridge_median_px": float(np.median(np.abs(rt))), "ridge_p90_px": float(np.percentile(np.abs(rt), 90)),
                                   "claw_median_px": float(np.median(np.abs(rb))), "claw_p90_px": float(np.percentile(np.abs(rb), 90))}
    return res


def bvh_selfx(out, items):
    """Blender BVH triangle-triangle self-intersection (kh_R1_selfx_bl.py = the judges' jt_selfx_bl.py logic)."""
    js = os.path.join(out, "kstarR3_bvh_selfx.json")
    cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "kh_R1_selfx_bl.py"), "--", js] + \
          ["%s=%s" % (k, v) for k, v in items]
    run(cmd, os.path.join(out, "logs", "4_bvh_selfx.log"), timeout=1200, cwd=out)
    return json.load(open(js, encoding="utf-8"))


def figures(rows, out):
    import kh_secplot as SP
    Kz = np.load(KC.KSTAR_ROWS); Az = np.load(KC.A4_ROWS); Rz = np.load(R2_ROWS); z = np.load(rows)
    SP.sections_png(os.path.join(out, "fig_sections_R3_R2_A4_Kstar.png"),
                    [("R3", z["c"], z["A"], z["Y"], (0, 0, 220)), ("R2", Rz["c"], Rz["A"], Rz["Y"], (0, 160, 0)),
                     ("A4", Az["c"], Az["A"], Az["Y"], (200, 80, 0)), ("K*", Kz["c"], Kz["A"], Kz["Y"], (150, 150, 150))],
                    [-16, -12, -8, -4, -2, 0, 2, 4, 6, 8, 10, 12, 13, 14, 14.6, 15],
                    "sections (constant c, K* frame, grid 5 m): red = K*' R3 (Houdini), green = R2 (loop 2), blue = A4, grey = K*")


def ref_numbers_panel(path, height, width=620):
    """a text-only column: the reference model's numbers (never its images; it is someone else's work)."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        f = ImageFont.truetype(r"C:\Windows\Fonts\Deng.ttf", 20); fb = ImageFont.truetype(r"C:\Windows\Fonts\Deng.ttf", 24)
    except Exception:
        f = fb = ImageFont.load_default()
    im = Image.new("RGB", (width, height), (250, 250, 246))
    d = ImageDraw.Draw(im)
    lines = ["Reference (numbers only)", "参照モデル：数値だけ（他者の作品。画像は載せない）", ""]
    try:
        ref = json.load(open(REF_NUMBERS, encoding="utf-8"))
        b = ref["big_wave_rows_c_-2_2"]
        lines += ["area / H^2 (c -2..+2):  %.3f" % b["area_over_H2_mean"], "back shell / H (c -2..+2):  %.3f" % b["shell_normal_median_over_H_mean"],
                  "volume above water c -14..+14:  %.0f m3" % ref["volume_above_water_c_-14_14_m3"]]
    except Exception as e:
        lines += ["(ref_fullness.json: %s)" % e]
    lines += ["", "rubric reference ranges (rubric_ja.md):", "back straight / H  0.18..0.35", "back circle R / H  0.7..1.4",
              "back slope 0.9H  30..44 deg", "shell / H  0.23..0.31", "wall 0.5H / H  0.22..0.28", "tube R / H  0.42..0.46",
              "", "F13: K*' vertices within 0.3 m of the", "reference surface must stay <= 25 %", "(see kstarR3_eval_table.md)"]
    y = 20
    for i, t in enumerate(lines):
        d.text((20, y), t, fill=(0, 0, 0), font=fb if i == 0 else f)
        y += 34 if i == 0 else 28
    im.save(path)
    return path


def sheets(out):
    from PIL import Image
    rd = os.path.join(out, "eval", "renders")
    labs = "R3,R2,A4,Kstar"
    std = os.path.join(out, "_sheet_std_tmp.png")
    run(["py", "-3.10", os.path.join(HERE, "kh_contact.py"), rd, std, labs, "views=std", "cell=440"], os.path.join(out, "logs", "5_sheet.log"))
    run(["py", "-3.10", os.path.join(HERE, "kh_contact.py"), rd, os.path.join(out, "fig_sheet_user_failure_views.png"), labs, "views=user", "cell=440"],
        os.path.join(out, "logs", "5_sheet_user.log"))
    a = Image.open(std).convert("RGB")
    p = ref_numbers_panel(os.path.join(out, "_refnum_tmp.png"), a.height)
    b = Image.open(p).convert("RGB")
    s = Image.new("RGB", (a.width + b.width, a.height), (255, 255, 255))
    s.paste(a, (0, 0)); s.paste(b, (a.width, 0))
    s.save(os.path.join(out, "fig_sheet_R3_R2_A4_Kstar_refnumbers.png"))
    os.remove(std); os.remove(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--out", default=OUT_DEF)
    ap.add_argument("--hip", default=HIP_DEF)
    ap.add_argument("--no-turntable", action="store_true")
    ap.add_argument("--no-eval", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    logs = os.path.join(out, "logs"); os.makedirs(logs, exist_ok=True)
    design = os.path.join(out, "kstarR3_design.json")
    if os.path.abspath(a.design) != design:
        shutil.copyfile(os.path.abspath(a.design), design)
    rep = {"design": os.path.abspath(a.design), "hip": a.hip}
    # 1 Houdini scene (saved in the repository folder: small, no geometry, no reference-model nodes)
    so, sec = run([KC.HYTHON, os.path.join(HERE, "kh_design_sceneR3.py"), "--design", design, "--out", a.hip,
                   "--verify", os.path.join(out, "houdini_scene_verify.json")], os.path.join(logs, "1_scene.log"))
    rep["scene"] = json.load(open(os.path.join(out, "houdini_scene_verify.json"), encoding="utf-8")); rep["scene"]["seconds"] = sec
    print("scene", json.dumps(rep["scene"].get("verify", {}))[:600], flush=True)
    shutil.copyfile(a.hip, os.path.join(out, os.path.basename(a.hip)))
    hb = open(a.hip, "rb").read()
    rep["scene"]["reference_strings_in_hiplc"] = {k: hb.count(k.encode("utf-8")) for k in ("wave_repair", "reality scan", "北斋参考", "research/model", "research\\model")}
    rep["scene"]["hiplc_sha256"] = KC.sha256(a.hip)
    # 2 bridge
    pre = os.path.join(out, PRE)
    so, sec = run([KC.HYTHON, os.path.join(HERE, "kh_bridge.py"), "h2g", "--hip", a.hip, "--sop", "/obj/kstar_h_design/OUT",
                   "--out", pre, "--columns", "attr"], os.path.join(logs, "2_bridge.log"))
    rep["bridge"] = json.loads(so.strip().splitlines()[-1]); rep["bridge"]["seconds"] = sec
    print("bridge", json.dumps(rep["bridge"])[:600], flush=True)
    rows = pre + "_rows.npz"
    import kh_designR3 as D
    c2, A2, Y2, _ = D.build(D.Design.load(design))
    z = np.load(rows)
    dA = np.abs(z["A"] - A2); dY = np.abs(z["Y"] - Y2)
    rep["bridge_vs_numpy_max_m"] = float(max(dA.max(), dY.max()))
    rep["bridge_vs_numpy_body_max_m"] = float(max(dA[np.abs(Y2) > 0.05].max(), dY[np.abs(Y2) > 0.05].max()))
    mp = pre + "_meta.json"
    meta = json.load(open(mp, encoding="utf-8"))
    H = z["Y"].max(1)
    meta["H0_m"] = float(H[int(np.argmin(np.abs(z["c"])))])
    meta["highest_point"] = {"H_m": float(H.max()), "c_m": float(z["c"][int(np.argmax(H))])}
    meta["landmarks_semantics_ja"] = ("列 18 背の足（凹の足の始まり）/ 90 頂（断面の最も高い点）/ 200 唇先 / 314 管の中の最も後ろの点（lean で回した後）/ "
                                      "379 前の谷の底 / 394 前の海の始まり（R3、R1・R2 と同じ）。R3：両端の 1.5 m より低い行は相似に縮む錐で、最後の行は "
                                      "0.4 % の極小の断面（高さ 6 mm 以下）。")
    meta["generator"] = "Tools/GWWaveGen/kstar_h/kh_designR3.py via Houdini/Design28R01/kstar_h_R3.hiplc (/obj/kstar_h_design) and kh_bridge.py h2g"
    meta["reference_model_credit_ja"] = ("参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。"
                                         "配置・比率・大きな形の考え方だけを参考にし、形は写していない（生成器は参照の網を読まない）。")
    json.dump(meta, open(mp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    # 3 evaluator
    if not a.no_eval:
        items = ["R3=%s" % (pre + ".gwb"), "R2=%s" % R2_ROWS, "A4=%s" % KC.A4_ROWS, "Kstar=%s" % KC.KSTAR_ROWS]
        cmd = ["py", "-3.10", os.path.join(HERE, "kh_eval.py"), "--out", os.path.join(out, "eval"), "--render"]
        if not a.no_turntable:
            cmd.append("--turntable")
        so, sec = run(cmd + items, os.path.join(logs, "3_eval.log"), timeout=5400)
        rep["eval_seconds"] = sec
        for f in ("kh_eval_table.md", "fig_views_all.png", "fig_views_user_failure.png"):
            p = os.path.join(out, "eval", f)
            if os.path.isfile(p):
                shutil.copyfile(p, os.path.join(out, f.replace("kh_eval_table", "kstarR3_eval_table")))
        tt = os.path.join(out, "eval", "renders", "turntable_R3.mp4")
        if os.path.isfile(tt):
            shutil.copyfile(tt, os.path.join(out, "turntable_R3.mp4"))
        tp = os.path.join(out, "eval", "fig_turntable_R3.png")
        if os.path.isfile(tp):
            shutil.copyfile(tp, os.path.join(out, "fig_turntable_R3.png"))
        sheets(out)
    # 4 supplementary (R3 and, for the comparison table, R2 and A4 with the same code)
    sup = {"R3": supplementary(rows, out, "R3"), "R2": supplementary(R2_ROWS, out, "R2"), "A4": supplementary(KC.A4_ROWS, out, "A4")}
    json.dump(sup, open(os.path.join(out, "kstarR3_supplementary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    rep["supplementary"] = {k: {kk: v[kk] for kk in ("gate_large_form", "judge_R2_notch_as_scripted", "judge_R2_notch_interior_chords")} for k, v in sup.items()}
    try:
        rep["bvh_selfx"] = bvh_selfx(out, [("R3", pre + ".gwb"), ("R2", R2_GWB)])
    except Exception as e:
        rep["bvh_selfx"] = {"error": str(e)}
    figures(rows, out)
    rep["seconds"] = round(time.time() - t0, 1)
    json.dump(rep, open(os.path.join(out, "kstarR3_deliver_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: rep[k] for k in ("bridge_vs_numpy_max_m", "bridge_vs_numpy_body_max_m", "seconds")}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
