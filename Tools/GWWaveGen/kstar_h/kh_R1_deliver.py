# -*- coding: utf-8 -*-
"""K*′ 精修 R1 の納品：設計の json → Houdini のシーン → 橋で格子へ → 同じ評価器 → 追加の検査 → 図と対照表（py -3.10）。

  py -3.10 kh_R1_deliver.py <design.json> [--out Unity/Build/Q20H/final] [--hip Houdini/Design28R01/kstar_h_R1.hiplc]
                            [--no-eval] [--no-turntable]
手順
  1 hython kh_design_sceneR1.py：土台のシーン（kstar_h_base.hiplc）に /obj/kstar_h_design（CTRL → guides → lip_profile → bregion_ledge →
    side_edges → skin → OUT）を組み、参照モデルの節点を消して保存・cook・検査（CTRL = json、Houdini と numpy の一致、行の面）
  2 hython kh_bridge.py h2g（attr の列、行は kh_row_c）→ kstarR1_a45.gwb / _rows.npz / .obj / _meta.json（meta に目印・H0・出典を足す）
  3 kh_eval.py（関門・ルーブリック・Q21・空の差・メッシュ・F13、Blender の 9+4 視点、ターンテーブル）：R1 と K*・第 2 回・A4・H1A
  4 追加：大きな輪郭の関門と重ね図、R1 の形の検査（kh_R1_quick：唇の交差・頂の列・列 314・H(c) の山・外周・4 階差・評審の膨らみ）、
    b 区域の帯、断面図、対照表（K* | 第 2 回 | 第 3 回の最良 A4 | Houdini K*′ R1 | 参照モデル）
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys
import json
import time
import glob
import shutil
import argparse
import subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import kh_common as KC  # noqa: E402

OUT_DEF = os.path.join(KC.OUT_ROOT, "final")
HIP_DEF = os.path.join(KC.HIP_DIR, "kstar_h_R1.hiplc")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MSYS_NO_PATHCONV="1", PYTHONIOENCODING="utf-8")
L2_ROWS = os.path.join(KC.REPO, "Unity", "Build", "Q20", "final", "kstarF_a45_rows.npz")
H1A_ROWS = os.path.join(KC.OUT_ROOT, "candH1_A", "kstarH1A_a45_rows.npz")
REF_RENDERS = os.path.join(KC.REPO, "Unity", "Build", "Q20", "rubric", "renders")
PRE = "kstarR1_a45"


def run(cmd, log, timeout=1800, cwd=None):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, cwd=cwd or KC.OUT_ROOT, encoding="utf-8", errors="replace")
    open(log, "w", encoding="utf-8").write("$ %s\n\n%s\n---- stderr\n%s" % (" ".join(cmd), r.stdout[-30000:], r.stderr[-8000:]))
    if r.returncode != 0:
        raise RuntimeError("failed (%d): %s — see %s" % (r.returncode, cmd[1] if len(cmd) > 1 else cmd, log))
    return r.stdout, round(time.time() - t, 1)


def supplementary(rows, out):
    sys.path.insert(0, os.path.join(KC.REPO, "Tools", "GWWaveGen", "kstar3"))
    import kh_gate_lfA as KG
    import kh_fitA as KF
    import kh_R1_quick as Q
    import candA4_fit as F
    z = np.load(rows); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    res = {}
    g = KG.LFGate()
    lf, cov = g.measure_rows(c, A, Y)
    res["gate_large_form"] = lf
    KG.overlay(os.path.join(out, "fig_gate_large_form.png"), g, cov, "R1: large-form gate 132 %.2f / 72 p95 %.2f px" % (lf["132"]["max_px"], lf["72"]["p95_px"]))
    res["shape_checks"] = Q.shape_checks(c, A, Y)
    res["bulge6_quick"] = Q.bulge6(c, A, Y, 2, 3)
    ctx = KF.Ctx()
    sdf, covb, X = ctx.cov_sdf(c, A, Y)
    rws = np.nonzero((c > -18.5) & (c < -3.5))[0]
    tp, bp = F.band_curves(ctx.base, c, A, Y, X, rws)
    rt = F.curve_vs_target(tp, ctx.base.band_top); rb = F.curve_vs_target(bp, ctx.base.band_bot)
    res["band_round3_detector"] = {"ridge_median_px": float(np.median(np.abs(rt))), "ridge_p90_px": float(np.percentile(np.abs(rt), 90)),
                                   "claw_median_px": float(np.median(np.abs(rb))), "claw_p90_px": float(np.percentile(np.abs(rb), 90))}
    # the design's own ridge column (90 + ledge_pos * 110) and the tip column 200 of every shoulder row (the fit's measure)
    try:
        import kh_designR1 as D
        d = D.Design.load(os.path.join(out, "kstarR1_design.json"))
        P = d.eval(c)
        jr = np.round(90.0 + 110.0 * np.asarray(P["ledge_pos"])[rws]).astype(int)
        Pw = ctx.base.fr.cam.project(X[rws, 150:216].reshape(-1, 3))[:, :2].reshape(len(rws), 66, 2)
        jj = np.arange(150, 216)[None, :]
        win = (jj >= jr[:, None] - 15) & (jj <= jr[:, None] + 8)
        kr_ = np.argmin(np.where(win, Pw[..., 1], np.inf), 1); pr = Pw[np.arange(len(rws)), kr_]
        kb_ = 38 + np.argmax(Pw[:, 38:66, 1], 1); pb = Pw[np.arange(len(rws)), kb_]
        rt2 = F.curve_vs_target(pr, ctx.base.band_top); rb2 = F.curve_vs_target(pb, ctx.base.band_bot)
        res["band_by_design_column"] = {"ridge_median_px": float(np.median(np.abs(rt2))), "ridge_p90_px": float(np.percentile(np.abs(rt2), 90)),
                                        "claw_median_px": float(np.median(np.abs(rb2))), "claw_p90_px": float(np.percentile(np.abs(rb2), 90))}
    except Exception as e:
        res["band_by_design_column"] = {"error": str(e)}
    json.dump(res, open(os.path.join(out, "kstarR1_supplementary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    return res


def figures(rows, out):
    import kh_secplot as SP
    Kz = np.load(KC.KSTAR_ROWS); Az = np.load(KC.A4_ROWS); Hz = np.load(H1A_ROWS); z = np.load(rows)
    SP.sections_png(os.path.join(out, "fig_sections_R1_H1A_A4_Kstar.png"),
                    [("R1", z["c"], z["A"], z["Y"], (0, 0, 220)), ("H1A", Hz["c"], Hz["A"], Hz["Y"], (0, 160, 0)),
                     ("A4", Az["c"], Az["A"], Az["Y"], (200, 80, 0)), ("K*", Kz["c"], Kz["A"], Kz["Y"], (150, 150, 150))],
                    [-16, -12, -8, -4, -2, 0, 2, 4, 6, 8, 10, 12, 13, 14, 14.6, 15],
                    "sections (constant c, K* frame, grid 5 m): red = K*' R1 (Houdini), green = H1A, blue = A4, grey = K*")


def sheets(out):
    rd = os.path.join(out, "eval", "renders")
    for p in glob.glob(os.path.join(REF_RENDERS, "ref__v*.png")):
        shutil.copyfile(p, os.path.join(rd, "Reference__" + os.path.basename(p)[5:]))
    labs = "Kstar,L2,A4,R1,Reference"
    run(["py", "-3.10", os.path.join(HERE, "kh_contact.py"), rd, os.path.join(out, "fig_sheet_Kstar_L2_A4_R1_reference.png"), labs, "views=std", "cell=440"],
        os.path.join(out, "logs", "5_sheet.log"))
    run(["py", "-3.10", os.path.join(HERE, "kh_contact.py"), rd, os.path.join(out, "fig_sheet_user_failure_views.png"), "Kstar,L2,A4,H1A,R1", "views=user", "cell=440"],
        os.path.join(out, "logs", "5_sheet_user.log"))


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
    design = os.path.join(out, "kstarR1_design.json")
    if os.path.abspath(a.design) != design:
        shutil.copyfile(os.path.abspath(a.design), design)
    rep = {"design": os.path.abspath(a.design), "hip": a.hip}
    # 1 Houdini scene (saved in the repository folder: small, no geometry, no reference-model nodes)
    so, sec = run([KC.HYTHON, os.path.join(HERE, "kh_design_sceneR1.py"), "--design", design, "--out", a.hip,
                   "--verify", os.path.join(out, "houdini_scene_verify.json")], os.path.join(logs, "1_scene.log"))
    rep["scene"] = json.load(open(os.path.join(out, "houdini_scene_verify.json"), encoding="utf-8")); rep["scene"]["seconds"] = sec
    print("scene", json.dumps(rep["scene"].get("verify", {}))[:600], flush=True)
    # a copy of the saved scene next to the deliverables (the task asks for the .hiplc in the delivery folder too)
    shutil.copyfile(a.hip, os.path.join(out, os.path.basename(a.hip)))
    # 2 bridge
    pre = os.path.join(out, PRE)
    so, sec = run([KC.HYTHON, os.path.join(HERE, "kh_bridge.py"), "h2g", "--hip", a.hip, "--sop", "/obj/kstar_h_design/OUT",
                   "--out", pre, "--columns", "attr"], os.path.join(logs, "2_bridge.log"))
    rep["bridge"] = json.loads(so.strip().splitlines()[-1]); rep["bridge"]["seconds"] = sec
    print("bridge", json.dumps(rep["bridge"])[:600], flush=True)
    rows = pre + "_rows.npz"
    import kh_designR1 as D
    c2, A2, Y2, _ = D.build(D.Design.load(design))
    z = np.load(rows)
    dA = np.abs(z["A"] - A2); dY = np.abs(z["Y"] - Y2)
    rep["bridge_vs_numpy_max_m"] = float(max(dA.max(), dY.max()))
    rep["bridge_vs_numpy_body_max_m"] = float(max(dA[np.abs(Y2) > 0.05].max(), dY[np.abs(Y2) > 0.05].max()))
    # the bridge's meta: add the landmark semantics, H0 and the credit (the motion generator reads profile.index)
    mp = pre + "_meta.json"
    meta = json.load(open(mp, encoding="utf-8"))
    H = z["Y"].max(1)
    meta["H0_m"] = float(H[int(np.argmin(np.abs(z["c"])))])
    meta["highest_point"] = {"H_m": float(H.max()), "c_m": float(z["c"][int(np.argmax(H))])}
    meta["landmarks_semantics_ja"] = ("列 18 背の足（凹の足の始まり）/ 90 頂（断面の最も高い点）/ 200 唇先 / 314 管の中の最も後ろの点（lean で回した後）/ "
                                      "379 前の谷の底 / 394 前の海の始まり（R1）")
    meta["generator"] = "Tools/GWWaveGen/kstar_h/kh_designR1.py via Houdini/Design28R01/kstar_h_R1.hiplc (/obj/kstar_h_design) and kh_bridge.py h2g"
    meta["reference_model_credit_ja"] = ("参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。"
                                         "配置・比率・大きな形の考え方だけを参考にし、形は写していない（生成器は参照の網を読まない）。")
    json.dump(meta, open(mp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    # 3 evaluator
    if not a.no_eval:
        items = ["R1=%s" % (pre + ".gwb"), "Kstar=%s" % KC.KSTAR_ROWS, "L2=%s" % L2_ROWS, "A4=%s" % KC.A4_ROWS, "H1A=%s" % H1A_ROWS]
        cmd = ["py", "-3.10", os.path.join(HERE, "kh_eval.py"), "--out", os.path.join(out, "eval"), "--render"]
        if not a.no_turntable:
            cmd.append("--turntable")
        so, sec = run(cmd + items, os.path.join(logs, "3_eval.log"), timeout=5400)
        rep["eval_seconds"] = sec
        for f in ("kh_eval_table.md", "fig_views_all.png", "fig_views_user_failure.png"):
            p = os.path.join(out, "eval", f)
            if os.path.isfile(p):
                shutil.copyfile(p, os.path.join(out, f.replace("kh_eval_table", "kstarR1_eval_table")))
        tt = os.path.join(out, "eval", "renders", "turntable_R1.mp4")
        if os.path.isfile(tt):
            shutil.copyfile(tt, os.path.join(out, "turntable_R1.mp4"))
        tp = os.path.join(out, "eval", "fig_turntable_R1.png")
        if os.path.isfile(tp):
            shutil.copyfile(tp, os.path.join(out, "fig_turntable_R1.png"))
        sheets(out)
    # 4 supplementary
    rep["supplementary"] = supplementary(rows, out)
    figures(rows, out)
    rep["seconds"] = round(time.time() - t0, 1)
    json.dump(rep, open(os.path.join(out, "kstarR1_deliver_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: rep[k] for k in ("bridge_vs_numpy_max_m", "bridge_vs_numpy_body_max_m", "supplementary", "seconds")}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
