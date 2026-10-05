# -*- coding: utf-8 -*-
"""候補 H1（copy A）の納品：設計の json → Houdini のシーン → 橋で格子へ → 同じ評価器 → 図（py -3.10）。

  py -3.10 kh_h1A_deliver.py <design.json> [--out Unity/Build/Q20H/candH1_A] [--hip Houdini/Design28R01/kstar_h_A.hiplc]
                             [--compare] [--no-turntable] [--no-eval]
手順
  1 hython kh_design_sceneA.py：土台のシーン（kstar_h_base.hiplc）に /obj/kstar_h_design（CTRL → guides → bregion_ledge →
    side_edges → skin → OUT）を組み、json の鍵を CTRL の ramp へ入れて保存・cook・検査（Houdini と numpy の一致、行の面）
  2 hython kh_bridge.py h2g（attr の列、行は kh_row_c）→ kstarH1A_a45.gwb / _rows.npz / .obj / _meta.json
  3 kh_eval.py（関門・ルーブリック・Q21・空の差・メッシュ・F13、Blender の 9+4 視点、ターンテーブル）。--compare で K* と A4 も並べる
  4 追加の表：大きな輪郭の関門（kh_gate_lfA、進行役の 20:00 の判断）、4 階差の膨らみ（kh_fitA.bump4）、
    b 区域の帯（candA4_fit の band_curves）、原画視点の重ね図、断面図（K*・A4 と）、空の領域の断面図
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

OUT_DEF = os.path.join(KC.OUT_ROOT, "candH1_A")
HIP_DEF = os.path.join(KC.HIP_DIR, "kstar_h_A.hiplc")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MSYS_NO_PATHCONV="1", PYTHONIOENCODING="utf-8")


def run(cmd, log, timeout=1800, cwd=None):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, cwd=cwd or KC.OUT_ROOT, encoding="utf-8", errors="replace")
    open(log, "w", encoding="utf-8").write("$ %s\n\n%s\n---- stderr\n%s" % (" ".join(cmd), r.stdout[-30000:], r.stderr[-8000:]))
    if r.returncode != 0:
        raise RuntimeError("failed (%d): %s — see %s" % (r.returncode, cmd[1] if len(cmd) > 1 else cmd, log))
    return r.stdout, round(time.time() - t, 1)


def supplementary(rows, out, label):
    sys.path.insert(0, os.path.join(KC.REPO, "Tools", "GWWaveGen", "kstar3"))
    import kh_fitA as KF
    import kh_gate_lfA as KG
    import candA4_fit as F
    z = np.load(rows); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    res = {}
    g = KG.LFGate()
    lf, cov = g.measure_rows(c, A, Y)
    res["gate_large_form"] = lf
    KG.overlay(os.path.join(out, "fig_gate_large_form.png"), g, cov, "%s: large-form gate 132 %.2f / 72 p95 %.2f px" % (label, lf["132"]["max_px"], lf["72"]["p95_px"]))
    b = KF.bump4(c, A, Y)
    res["bump4"] = {"d1_p99_m": float(np.percentile(b["d1"], 99)), "d1_max_m": float(b["d1"].max()),
                    "d2_p99_m": float(np.percentile(b["d2"], 99)), "d2_max_m": float(b["d2"].max()),
                    "baseline_constant_shape_p99": [0.072, 0.637],
                    "note_ja": "|Δ⁴X|（c 方向、1 m と 2 m の刻み、列 18〜186・214〜379、c −17〜+9、y > 0.3 m）。波峰の高さと平面だけが変わる形（中の形の ramp は一定）で 0.07 / 0.64 m。"}
    ctx = KF.Ctx()
    prob = KF.Problem(ctx, KF.D.Design({}), [], {"band": 1.0})
    sdf, covb, X = ctx.cov_sdf(c, A, Y)
    rws = np.nonzero((c > -18.5) & (c < -3.5))[0]
    tp, bp = F.band_curves(ctx.base, c, A, Y, X, rws)
    rt = F.curve_vs_target(tp, ctx.base.band_top); rb = F.curve_vs_target(bp, ctx.base.band_bot)
    res["band_fit_metric"] = {"ridge_median_px": float(np.median(np.abs(rt))), "ridge_p90_px": float(np.percentile(np.abs(rt), 90)),
                              "claw_median_px": float(np.median(np.abs(rb))), "claw_p90_px": float(np.percentile(np.abs(rb), 90))}
    json.dump(res, open(os.path.join(out, "kstarH1A_supplementary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return res


def figures(rows, out, design):
    import kh_secplot as SP
    Kz = np.load(KC.KSTAR_ROWS); Az = np.load(KC.A4_ROWS); z = np.load(rows)
    SP.sections_png(os.path.join(out, "fig_sections_H1A_Kstar_A4.png"),
                    [("H1A", z["c"], z["A"], z["Y"], (0, 0, 220)), ("K*", Kz["c"], Kz["A"], Kz["Y"], (150, 150, 150)),
                     ("A4", Az["c"], Az["A"], Az["Y"], (200, 80, 0))],
                    [-16, -12, -8, -4, -2, 0, 2, 4, 6, 8, 10, 12], "sections (constant c, K* frame, grid 5 m): red = H1A, grey = K*, blue = A4")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--out", default=OUT_DEF)
    ap.add_argument("--hip", default=HIP_DEF)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--no-turntable", action="store_true")
    ap.add_argument("--no-eval", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    logs = os.path.join(out, "logs"); os.makedirs(logs, exist_ok=True)
    design = os.path.abspath(a.design)
    shutil.copyfile(design, os.path.join(out, "kstarH1A_design.json"))
    rep = {"design": design, "hip": a.hip}
    # 1 Houdini scene
    so, sec = run([KC.HYTHON, os.path.join(HERE, "kh_design_sceneA.py"), "--design", design, "--out", a.hip,
                   "--verify", os.path.join(out, "houdini_scene_verify.json")], os.path.join(logs, "1_scene.log"))
    rep["scene"] = json.load(open(os.path.join(out, "houdini_scene_verify.json"), encoding="utf-8")); rep["scene"]["seconds"] = sec
    print("scene", json.dumps(rep["scene"].get("verify", {}))[:600], flush=True)
    # 2 bridge
    pre = os.path.join(out, "kstarH1A_a45")
    so, sec = run([KC.HYTHON, os.path.join(HERE, "kh_bridge.py"), "h2g", "--hip", a.hip, "--sop", "/obj/kstar_h_design/OUT",
                   "--out", pre, "--columns", "attr"], os.path.join(logs, "2_bridge.log"))
    rep["bridge"] = json.loads(so.strip().splitlines()[-1]); rep["bridge"]["seconds"] = sec
    print("bridge", json.dumps(rep["bridge"])[:600], flush=True)
    rows = pre + "_rows.npz"
    # bridge vs the numpy build of the same design
    import kh_designA as D
    c2, A2, Y2, _ = D.build(D.Design.load(design))
    z = np.load(rows)
    rep["bridge_vs_numpy_max_m"] = float(max(np.abs(z["A"] - A2)[z["Y"] > -9].max(), np.abs(z["Y"] - Y2).max()))
    # 3 evaluator
    if not a.no_eval:
        items = ["H1A=%s" % (pre + ".gwb")]
        if a.compare:
            items += ["Kstar=%s" % KC.KSTAR_ROWS, "A4=%s" % KC.A4_ROWS]
        cmd = ["py", "-3.10", os.path.join(HERE, "kh_eval.py"), "--out", os.path.join(out, "eval"), "--render"]
        if not a.no_turntable:
            cmd.append("--turntable")
        so, sec = run(cmd + items, os.path.join(logs, "3_eval.log"), timeout=3600)
        rep["eval_seconds"] = sec
        for f in ("kh_eval_table.md", "fig_views_all.png", "fig_views_user_failure.png"):
            p = os.path.join(out, "eval", f)
            if os.path.isfile(p):
                shutil.copyfile(p, os.path.join(out, f.replace("kh_eval_table", "kstarH1A_eval_table")))
    # 4 supplementary
    rep["supplementary"] = supplementary(rows, out, "H1A")
    figures(rows, out, design)
    rep["seconds"] = round(time.time() - t0, 1)
    json.dump(rep, open(os.path.join(out, "kstarH1A_deliver_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: rep[k] for k in ("bridge_vs_numpy_max_m", "supplementary", "seconds")}, indent=1, default=str)[:3000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
