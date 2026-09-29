# -*- coding: utf-8 -*-
"""設計28修正01 の候補を 1 回の命令で評価し、表を書く（py -3.10）。

各候補について
  F01 原画の関門  gw_wavegen_v1.preview_metrics（包絡版、輪郭 78/130/131/132 の最大 ≤ 4 px かつ K*+0.5、72 の p95 ≤ 4 px）
  ルーブリック   Tools/GWWaveGen/rubric/rubric_check.py（F01〜F08・F10〜F13。F13 は参照モデルの一時キャッシュで測る。
                 2026-09-29 R3：Git 対象外の Unity/Build/Q20/rubric/tools/ の写しをリポジトリへ移した。同じ SHA-256 の写しで
                 R2 の表の数値が変わらないことを確かめてから、F03 の殻・壁の必須の上限を緩めた（rubric_check.py の注））
  Q21 の検査     candA4_checks.run（Q21-1 中の膨らみ・凹み：6×12 の面の当てはめ・3 m の撓み・平均曲率の極値、
                 Q21-2 量感：断面積・背の法線の殻・体積、参照の数値と比べる、Q21-3 b 区域：稜と爪の縁の像と帯の輪郭の差）
  そのほか       原画視点の空の差（穴・はみ出し）、メッシュの衛生（局所の自己交差・裏返り・折れ）、第二の波頭 S1、頂の列
候補の指定（ラベル=パス、いくつでも）
  label=<rows.npz>               K* 形式の行の npz（A, Y, c）
  label=<sheet.gwb>              行が c 一定の面に乗った GWW0（断面の座標へ戻して評価）
  label=hip:<scene.hiplc>#<SOP>  Houdini のシーンの SOP（kh_bridge.py h2g で格子へ移してから評価。--columns で列の置き方）
出力（--out、既定 Unity/Build/Q20H/eval/<日時>）
  <label>/…（行の npz の写し、関門の重ね図、ルーブリックの json/md、Q21 の json、空の差の図）
  kh_eval_table.md / kh_eval_summary.json（候補を列に並べた表）
参照モデル（他者の作品）は F13 のためだけに一時キャッシュ（Unity/Build/Q20H/_tmp、Git 対象外）へ置き、最後に消して SHA-256 を記録する。
  --render      さらに Blender の粘土の描画（9 視点＋利用者の失敗の視点 4、kh_bl.py）と対照図 fig_views_all.png を作る
  --turntable   さらに各候補のターンテーブル（mp4 と 12 枚の静止画の一覧）を作る
usage: py -3.10 kh_eval.py [--out DIR] [--no-f13] [--no-mesh] [--render] [--turntable]
                           [--columns attr|landmark|geometric|auto] label=path ...
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys
import json
import time
import shutil
import datetime
import subprocess

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kh_common as KC  # noqa: E402
KSTAR3 = os.path.join(KC.REPO, "Tools", "GWWaveGen", "kstar3")
RUBRIC_TOOLS = os.path.join(KC.REPO, "Tools", "GWWaveGen", "rubric")      # 2026-09-29 R3: the repository copy (was Unity/Build/Q20/rubric/tools, git-ignored)
for p in (os.path.join(KC.REPO, "Tools", "PaintingTruth"), os.path.join(KC.REPO, "Tools", "GWWaveGen"), KSTAR3, RUBRIC_TOOLS):
    sys.path.insert(0, p)
import numpy as np  # noqa: E402


def _load_repo_rubric():
    """2026-09-29 R3: load the repository copy of the rubric tools BEFORE fin_eval / candA4_checks, which put the git-ignored
    Unity/Build/Q20/rubric/tools first on sys.path and `import rubric_check`: with the repository modules already in sys.modules,
    every importer gets the repository copy (the first R3 re-run of the R2 table still used the git-ignored module this way)."""
    import importlib.util
    for name in ("rubric_measure", "rubric_check"):
        if name in sys.modules and os.path.abspath(sys.modules[name].__file__) == os.path.abspath(os.path.join(RUBRIC_TOOLS, name + ".py")):
            continue
        spec = importlib.util.spec_from_file_location(name, os.path.join(RUBRIC_TOOLS, name + ".py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
    return sys.modules["rubric_check"]


RC = _load_repo_rubric()
import candA_common as C  # noqa: E402
import fin_eval as FE  # noqa: E402
import candA4_checks as CK  # noqa: E402
import rubric_check as _rc_check  # noqa: E402
assert os.path.abspath(_rc_check.__file__) == os.path.abspath(os.path.join(RUBRIC_TOOLS, "rubric_check.py")), _rc_check.__file__
assert os.path.abspath(FE.RC.__file__) == os.path.abspath(os.path.join(RUBRIC_TOOLS, "rubric_check.py")), FE.RC.__file__

REF_FULL = os.path.join(KC.REPO, "Unity", "Build", "Q20L3", "candA4", "_model_side", "ref_fullness.json")
BASE_K = {"78": 1.37, "130": 1.80, "131": 1.47, "132": 1.40}
PROVISIONAL = {
    "sag3m_p99_m": 0.15,          # candA4_checks の注：なめらかな波は ~0.15 m 未満
    "band_median_px": 10.0,       # 利用者 Q21 の b 区域のおおよその輪郭（≈10 px、作業の指示）
    "fullness_ratio_min": 0.90,   # 面積/H² と殻/H の、参照の大波の行（c -2..+2）の値に対する比
}


def log(*a):
    print(*a, flush=True)


def build_ref_cache(tmp_dir):
    h = KC.sha256(KC.REF_OBJ).upper()
    assert h.startswith(KC.REF_SHA_HEAD) and h.endswith(KC.REF_SHA_TAIL), h
    V = []
    with open(KC.REF_OBJ, "rb") as f:
        for line in f:
            if line.startswith(b"v "):
                V.append(line.split()[1:4])
    V = np.array(V, dtype=np.float64)
    M4 = np.array(json.load(open(KC.ALIGN_B, encoding="utf-8"))["obj_to_unity_4x4"])
    Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
    os.makedirs(tmp_dir, exist_ok=True)
    path = os.path.join(tmp_dir, "_kh_ref_f13_cache_%d.npz" % os.getpid())
    np.savez_compressed(path, V=Vu.astype(np.float32))
    return path, h


def drop_ref_cache(path):
    if path and os.path.isfile(path):
        hc = KC.sha256(path)
        os.remove(path)
        with open(os.path.join(KC.OUT_ROOT, "deleted_caches_sha256.txt"), "a", encoding="utf-8") as f:
            f.write("%s  %s  (TEMP align-B cache of the reference model for F13, deleted %s)\n" % (hc, os.path.basename(path), time.strftime("%Y-%m-%d %H:%M:%S")))


def resolve(label, spec, out_dir, columns):
    """候補の指定 → 評価用の rows npz（出力フォルダーの中の写し）"""
    d = os.path.join(out_dir, label)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, label + "_rows.npz")
    src = {"spec": spec}
    if spec.startswith("hip:"):
        hip, sop = spec[4:].split("#", 1)
        pre = os.path.join(d, label)
        cmd = [KC.HYTHON, os.path.join(HERE, "kh_bridge.py"), "h2g", "--hip", hip, "--sop", sop, "--out", pre, "--columns", columns]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=os.path.join(KC.OUT_ROOT), env=env)
        if r.returncode != 0:
            raise RuntimeError("bridge failed: %s\n%s" % (r.stdout[-2000:], r.stderr[-2000:]))
        src["bridge_stdout"] = r.stdout.strip().splitlines()[-1][:2000]
        src["gwb"] = pre + ".gwb"
    elif spec.lower().endswith(".gwb"):
        G = KC.read_gwb(spec)
        S = KC.sec(G["X"]).reshape(G["nv"], G["nu"], 3)
        c = S[..., 2].mean(1)
        spread = float(np.abs(S[..., 2] - c[:, None]).max())
        if spread > 1e-3:
            raise ValueError("%s: rows are not on c-planes (spread %.3f m); convert with kh_bridge.py h2g first" % (spec, spread))
        np.savez_compressed(dst, A=S[..., 0], Y=S[..., 1], c=c, P=np.stack([S[int(np.argmin(np.abs(c))), :, 0], S[int(np.argmin(np.abs(c))), :, 1]], -1))
        src["gwb"] = spec; src["row_plane_spread_m"] = spread
    else:
        z = np.load(spec)
        np.savez_compressed(dst, A=z["A"], Y=z["Y"], c=z["c"], **({"P": z["P"]} if "P" in z.files else {}))
        src["rows"] = spec
    src["sha256_input"] = KC.sha256(src.get("gwb", spec) if not spec.startswith("hip:") else src["gwb"])
    if "gwb" not in src:
        # 描画用の GWW0（K* と同じ三角形・UV の並び）
        z = np.load(dst)
        g = os.path.join(d, label + "_render.gwb")
        nv, nu = z["A"].shape
        uvk, uv2k = KC.kstar_uv() if (nv, nu) == (KC.NV, KC.NU) else (None, None)
        uv = uvk.reshape(-1, 2) if uvk is not None else np.zeros((nv * nu, 2))
        KC.write_gwb(g, nu, nv, uv, uv, KC.triangles(nu, nv), KC.world(z["c"], z["A"], z["Y"]))
        src["render_gwb"] = g
    else:
        src["render_gwb"] = src["gwb"]
    return dst, src


def render(results, out, turntable):
    rd = os.path.join(out, "renders")
    items = ",".join("%s=%s" % (r["label"], r["input"]["render_gwb"]) for r in results)
    cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "kh_bl.py"), "--",
           "views", rd, items, "views=all"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    open(os.path.join(out, "blender_views.log"), "w", encoding="utf-8").write(r.stdout[-20000:] + r.stderr[-5000:])
    if r.returncode != 0:
        raise RuntimeError("blender views failed (see blender_views.log)")
    import kh_contact
    labs = [x["label"] for x in results]
    kh_contact.contact(rd, os.path.join(out, "fig_views_all.png"), labs, "all", 520 if len(labs) <= 3 else 420)
    kh_contact.contact(rd, os.path.join(out, "fig_views_user_failure.png"), labs, "user", 520 if len(labs) <= 3 else 420)
    if turntable:
        for x in results:
            sd = os.path.join(rd, "turntable_" + x["label"])
            cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "kh_bl.py"), "--",
                   "turntable", x["input"]["render_gwb"], os.path.join(rd, "turntable_%s.mp4" % x["label"]), sd]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
                raise RuntimeError("blender turntable failed for %s" % x["label"])
            kh_contact.turntable_sheet(sd, os.path.join(out, "fig_turntable_%s.png" % x["label"]))


def run_q21(rows_path, out_path, label):
    """candA4_checks.run と同じ中身を、部分ごとに失敗しても続くように呼ぶ（失敗は error として記録）。"""
    z = np.load(rows_path); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    V1, tgt, fr = C.painting_frame()
    sil, grown, cov = CK.silhouette_band(c, A, Y, V1, fr)
    interior = ~grown & (Y > 0.3) & (np.abs(c)[:, None] <= 16)

    def safe(f, *a):
        try:
            return f(*a)
        except Exception as e:
            return {"error": "%s: %s" % (type(e).__name__, e)}
    res = {"rows": rows_path, "label": label,
           "silhouette_band": {"sil_vertices": int(sil.sum()), "band_vertices_1p5m": int(grown.sum()), "interior_vertices": int(interior.sum())},
           "Q21_1": {"surface_fit_6x12": safe(CK.surface_fit, c, A, Y, interior), "sag_3m": safe(CK.sag3m, c, A, Y, interior),
                     "mean_curvature_extrema": safe(CK.curvature_extrema, c, A, Y, interior)},
           "Q21_2": safe(CK.fullness, c, A, Y), "Q21_3": safe(CK.band_check, c, A, Y, cov)}
    json.dump(res, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    return res


def fullness_vs_ref(q2, A, Y, c):
    if "error" in q2:
        return {"error": q2["error"], "area_over_H2_mean_c-2_2": None, "shell_over_H_mean_c-2_2": None,
                "volume_above_water_c-14_14_m3": float("nan"), "volume_above_water_c-15_15_m3": float("nan")}
    ref = json.load(open(REF_FULL, encoding="utf-8")) if os.path.isfile(REF_FULL) else None
    rows = q2["rows"]
    keys = ("-2", "-1", "+0", "+1", "+2")
    ar = [rows[k]["area_m2"] for k in keys if k in rows]
    a2 = [rows[k]["area_over_H2"] for k in keys if k in rows]
    sh = [rows[k]["shell_normal_median_over_H"] for k in keys if k in rows and rows[k]["shell_normal_median_over_H"] is not None]
    area = np.array([RC.section_area(A[r], Y[r]) for r in range(len(c))])
    m = (c >= -14) & (c <= 14)
    vol14 = float(np.trapezoid(area[m], c[m]))
    o = {"area_m2_mean_c-2_2": float(np.mean(ar)) if ar else None, "area_over_H2_mean_c-2_2": float(np.mean(a2)) if a2 else None,
         "shell_over_H_mean_c-2_2": float(np.mean(sh)) if sh else None, "volume_above_water_c-14_14_m3": vol14,
         "volume_above_water_c-15_15_m3": q2["volume_above_water_c_-15_15_m3"]}
    if ref:
        b = ref["big_wave_rows_c_-2_2"]
        o["reference"] = {"area_m2_mean": b["area_m2_mean"], "area_over_H2_mean": b["area_over_H2_mean"],
                          "shell_over_H_mean": b["shell_normal_median_over_H_mean"], "volume_c-14_14_m3": ref["volume_above_water_c_-14_14_m3"],
                          "source": "numbers-only file (Q20L3/candA4/_model_side/ref_fullness.json)"}
        o["ratio_area_over_H2"] = o["area_over_H2_mean_c-2_2"] / b["area_over_H2_mean"] if o["area_over_H2_mean_c-2_2"] else None
        o["ratio_shell_over_H"] = o["shell_over_H_mean_c-2_2"] / b["shell_normal_median_over_H_mean"] if o["shell_over_H_mean_c-2_2"] else None
        o["ratio_volume_c-14_14"] = vol14 / ref["volume_above_water_c_-14_14_m3"]
    return o


def evaluate_one(label, rows, src, ref_cache, do_mesh):
    t0 = time.time()
    d = os.path.dirname(rows)
    pre = os.path.join(d, label)
    z = np.load(rows); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    res = {"label": label, "input": src, "rows_npz": rows, "nv": int(A.shape[0]), "nu": int(A.shape[1])}
    # rubric (+ F01 gate via the official path; the overlay lands next to the rows copy)
    R = RC.check(rows, gate=True, ref_cache=ref_cache)
    R["summary_recount"] = FE.recount(R)
    json.dump(R, open(pre + "_rubric_check.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    open(pre + "_rubric_check_table.md", "w", encoding="utf-8").write(RC.to_table(R) + "\n")
    g = R["gate_raw"]
    res["gate"] = g
    res["gate_pass_4px"] = bool(all(g[k]["max_px"] <= 4 for k in BASE_K) and g["72"]["p95_px"] <= 4)
    res["gate_pass_kstar_plus_0p5"] = bool(all(g[k]["max_px"] <= BASE_K[k] + 0.5 for k in BASE_K))
    # large-form gate (coordinator decision 2026-09-28 20:00): 132 / 72 against the painted line smoothed along itself
    # (sigma 12 px, kh_gate_lf); 78 / 130 / 131 unchanged
    try:
        import kh_gate_lf as KG
        if not hasattr(evaluate_one, "_lf"):
            evaluate_one._lf = KG.LFGate()
        glf, _ = evaluate_one._lf.measure_rows(c, A, Y)
        res["gate_lf"] = glf
        res["gate_pass_lf"] = bool(all(g[k]["max_px"] <= 4 for k in ("78", "130", "131")) and glf["132"]["max_px"] <= 4
                                   and glf["72"]["p95_px"] <= 4)
    except Exception as e:
        res["gate_lf"] = {"error": "%s: %s" % (type(e).__name__, e)}
        res["gate_pass_lf"] = None
    # 2026-09-29 R4: the R4 large form (kh_gate_lfR4): 72 smoothed with sigma 24 px (the claw bays closed; the bays belong to stage 6),
    # 132 unchanged (sigma 12 px). Chosen under Q24 on both R3 judges' recommendation; the sigma-12 values above stay recorded.
    try:
        import kh_gate_lfR4 as KG4
        if not hasattr(evaluate_one, "_lf4"):
            evaluate_one._lf4 = KG4.LFGate()
        glf4, _ = evaluate_one._lf4.measure_rows(c, A, Y)
        res["gate_lf_r4"] = glf4
        res["gate_pass_lf_r4"] = bool(all(g[k]["max_px"] <= 4 for k in ("78", "130", "131")) and glf4["132"]["max_px"] <= 4
                                      and glf4["72"]["p95_px"] <= 4)
    except Exception as e:
        res["gate_lf_r4"] = {"error": "%s: %s" % (type(e).__name__, e)}
        res["gate_pass_lf_r4"] = None
    # judges' broad-bulge measure (round 3, read-only script): local quadric residual over 4 m / 6 m windows
    try:
        jb = os.path.join(KC.REPO, "Unity", "Build", "Q20L3", "judge_fid", "j_bulge6.py")
        if os.path.isfile(jb):
            r_ = subprocess.run([sys.executable, jb, pre + "_bulge6", "%s=%s" % (label, rows)], capture_output=True, text=True, timeout=1200,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            bj = json.load(open(pre + "_bulge6.json"))[label]
            res["bulge6"] = {R: {"p99": bj[R]["p99"], "max": bj[R]["max"], "gt0p3": bj[R]["gt0p3"], "regions": bj[R]["regions_p99_max_gt0p3"]}
                             for R in ("R4", "R6")}
    except Exception as e:
        res["bulge6"] = {"error": "%s: %s" % (type(e).__name__, e)}
    res["rubric"] = {"summary": R["summary_recount"], "checks": R["checks"]}
    log("  [%s] rubric %s gate %s (%.0fs)" % (label, R["summary_recount"], {k: round(v["max_px"], 2) for k, v in g.items()}, time.time() - t0))
    if ref_cache:
        from scipy.spatial import cKDTree
        kd = cKDTree(np.load(ref_cache)["V"].astype(float))          # R1: all reference vertices (judge: every second one read 6.32 % vs 6.40 %)
        X, _ = RC.grid_world(A, Y, c)
        msk = (Y.reshape(-1) > 1.0) & (np.abs(np.repeat(c, A.shape[1])) <= 16)
        dd, _ = kd.query(X[msk])
        res["F13_proximity"] = {"within_0p3m": float((dd < 0.3).mean()), "within_1m": float((dd < 1.0).mean()),
                                "median_m": float(np.median(dd)), "p90_m": float(np.percentile(dd, 90)), "vertices": int(msk.sum())}
    # Q21 checks
    q = run_q21(rows, pre + "_q21_checks.json", label)
    q1 = q["Q21_1"]
    sf = q1["surface_fit_6x12"]
    res["Q21_1"] = {"surface_fit_6x12": ({k: (None if v is None else {"max_m": v["max_m"], "p99_m": v["p99_m"]}) for k, v in sf.items()}
                                         if "error" not in sf else {"error": sf["error"]}),
                    "sag_3m": ({k: q1["sag_3m"][k] for k in ("max_m", "p99_m", "p95_m", "n_gt_0.3m")} if "error" not in q1["sag_3m"]
                               else {"error": q1["sag_3m"]["error"], "max_m": float("nan"), "p99_m": float("nan"), "n_gt_0.3m": -1}),
                    "mean_curvature_extrema": q1["mean_curvature_extrema"].get("count", -1),
                    "silhouette_band": q["silhouette_band"]}
    res["Q21_2"] = fullness_vs_ref(q["Q21_2"], A, Y, c)
    b = q.get("Q21_3", {}) if "error" not in q.get("Q21_3", {}) else {}
    res["Q21_3"] = {k: b.get(k) for k in ("top_vs_top_smooth", "bottom_vs_bottom_smooth", "top_vs_top_raw", "bottom_vs_bottom_raw",
                                          "top_depth_inside_silhouette_px_min", "bottom_depth_inside_silhouette_px_min")}
    log("  [%s] Q21 done (%.0fs)" % (label, time.time() - t0))
    # sky difference / mesh hygiene / S1 / landmarks
    V1, tgt, fr = C.painting_frame()
    import gw_wavegen as G0
    res["sky"] = FE.sky_diff(fr, tgt, V1, G0, c, A, Y, pre + "_skydiff.png")
    if do_mesh:
        res["mesh"] = FE.mesh_hygiene(c, A, Y, V1)
    try:
        res["S1"] = FE.second_crest_S1(fr, tgt, V1, A, Y, c)
    except Exception as e:  # the band mask lives in the session scratchpad
        res["S1"] = {"error": str(e)}
    res["landmarks"] = FE.landmark_stats(A, Y, c)
    H = Y.max(1)
    res["shape"] = {"H0_main_m": float(H[int(np.argmin(np.abs(c)))]), "H_max_m": float(H.max()), "c_of_H_max": float(c[int(np.argmax(H))]),
                    "c_range": [float(c.min()), float(c.max())]}
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(pre + "_kh_eval.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    return res


def fmt(v, nd=2):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "合" if v else "**否**"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return ("%." + str(nd) + "f") % v
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(fmt(x, nd) for x in v) + "]"
    return str(v)


def table(results):
    labs = [r["label"] for r in results]
    L = ["| 項目 | 基準 | " + " | ".join(labs) + " |", "| --- | --- | " + " | ".join("---" for _ in labs) + " |"]

    def row(name, crit, vals):
        L.append("| %s | %s | %s |" % (name, crit, " | ".join(vals)))

    row("**原画の関門（F01）合否**", "78/130/131/132 最大 ≤ 4 px、72 p95 ≤ 4 px", [fmt(r["gate_pass_4px"]) for r in results])
    row("関門：K*+0.5 以内", "ルーブリック F01", [fmt(r["gate_pass_kstar_plus_0p5"]) for r in results])
    row("**大きな輪郭の関門（20:00 の判断）合否**", "78/130/131 最大 ≤ 4、132 大きな輪郭 最大 ≤ 4、72 大きな輪郭 p95 ≤ 4",
        [fmt(r.get("gate_pass_lf")) for r in results])
    for k in ("132", "72"):
        row("輪郭 %s 大きな輪郭 最大 / p95（px）" % k, "σ 12 px でならした原画の線（kh_gate_lf）",
            ["%.3f / %.3f" % (r["gate_lf"][k]["max_px"], r["gate_lf"][k]["p95_px"]) if isinstance(r.get("gate_lf"), dict) and k in r["gate_lf"] else "—" for r in results])
    row("**大きな輪郭の関門 R4（72 を σ 24 px で定義し直した版）合否**", "78/130/131 最大 ≤ 4、132 大きな輪郭（σ 12）最大 ≤ 4、72 大きな輪郭（σ 24、爪の湾を閉じる）p95 ≤ 4",
        [fmt(r.get("gate_pass_lf_r4")) for r in results])
    row("輪郭 72 大きな輪郭 R4 最大 / p95（px）", "σ 24 px でならした原画の線（kh_gate_lfR4、R4 で定義し直した関門）",
        ["%.3f / %.3f" % (r["gate_lf_r4"]["72"]["max_px"], r["gate_lf_r4"]["72"]["p95_px"]) if isinstance(r.get("gate_lf_r4"), dict) and "72" in r["gate_lf_r4"] else "—" for r in results])
    for k in ("78", "130", "131", "132"):
        row("輪郭 %s 最大 / p95（px）" % k, "≤ 4 かつ ≤ %.2f" % (BASE_K[k] + 0.5), ["%.3f / %.3f" % (r["gate"][k]["max_px"], r["gate"][k]["p95_px"]) for r in results])
    row("輪郭 72 p95 / 最大（px）", "p95 ≤ 4（最大は記録）", ["%.3f / %.3f" % (r["gate"]["72"]["p95_px"], r["gate"]["72"]["max_px"]) for r in results])
    row("輪郭 71 最大 / p95（px）", "記録のみ", ["%.2f / %.2f" % (r["gate"]["71"]["max_px"], r["gate"]["71"]["p95_px"]) if "71" in r["gate"] else "—" for r in results])
    row("**ルーブリック 必須の不合格の数**", "0", ["**%d** / %d" % (r["rubric"]["summary"]["must_fail"], r["rubric"]["summary"]["n_checks"]) for r in results])
    row("ルーブリック 目標の未達の数", "記録", [str(r["rubric"]["summary"]["target_miss"]) for r in results])
    # every rubric check
    keys = []
    for r in results:
        for fid, lst in r["rubric"]["checks"].items():
            for x in lst:
                if (fid, x["name"]) not in keys:
                    keys.append((fid, x["name"]))
    keys.sort(key=lambda t: t[0])
    for fid, name in keys:
        vals, crit = [], ""
        for r in results:
            x = next((x for x in r["rubric"]["checks"].get(fid, []) if x["name"] == name), None)
            if x is None:
                vals.append("—"); continue
            crit = "必須 %s" % x["must"]
            pm = x["pass_must"]
            flag = "" if pm is None or bool(pm) else " ✗"
            vals.append(fmt(x["value"]) + flag)
        row("%s %s" % (fid, name), crit, vals)
    row("F13 参照から 0.3 m / 1 m 以内の割合", "0.3 m ≤ 0.25（必須）", [("%.3f / %.3f" % (r["F13_proximity"]["within_0p3m"], r["F13_proximity"]["within_1m"])) if "F13_proximity" in r else "—" for r in results])
    # Q21-1
    for reg in ("back", "lip", "under_tube", "face"):
        row("Q21-1 面の当てはめ 6×12 %s 最大 / p99（m）" % reg, "記録（小さいほど中の膨らみがない）",
            [("%.3f / %.3f" % (r["Q21_1"]["surface_fit_6x12"][reg]["max_m"], r["Q21_1"]["surface_fit_6x12"][reg]["p99_m"])) if isinstance(r["Q21_1"]["surface_fit_6x12"].get(reg), dict) else "—" for r in results])
    row("**Q21-1 3 m の撓み p99 / 最大（m）**", "p99 ≤ %.2f（暫定）" % PROVISIONAL["sag3m_p99_m"],
        ["%.3f / %.3f%s" % (r["Q21_1"]["sag_3m"]["p99_m"], r["Q21_1"]["sag_3m"]["max_m"], "" if r["Q21_1"]["sag_3m"]["p99_m"] <= PROVISIONAL["sag3m_p99_m"] else " ✗") for r in results])
    row("Q21-1 3 m の撓み > 0.3 m の頂点数", "0 が目標", [str(r["Q21_1"]["sag_3m"]["n_gt_0.3m"]) for r in results])
    for R in ("R4", "R6"):
        row("**評審の膨らみの測り（j_bulge6）%s p99 / 最大（m）**" % R, "第 3 回の勝者 A4：R4 0.306 / 0.562、R6 0.506 / 1.022",
            ["%.3f / %.3f" % (r["bulge6"][R]["p99"], r["bulge6"][R]["max"]) if isinstance(r.get("bulge6"), dict) and R in r["bulge6"] else "—" for r in results])
    row("Q21-1 平均曲率の極値（丸い膨らみ・凹み）の数", "0 が目標", [str(r["Q21_1"]["mean_curvature_extrema"]) for r in results])
    # Q21-2
    def ratio(r, k):
        v = r["Q21_2"].get(k)
        return "—" if v is None else ("%.2f%s" % (v, "" if v >= PROVISIONAL["fullness_ratio_min"] else " ✗"))
    row("Q21-2 断面積 / H²（c -2..+2 平均）", "参照 %.3f" % (results[0]["Q21_2"].get("reference", {}).get("area_over_H2_mean", float("nan"))),
        [fmt(r["Q21_2"].get("area_over_H2_mean_c-2_2"), 3) for r in results])
    row("**Q21-2 量感の比（面積/H²、参照に対して）**", "≥ %.2f（暫定）" % PROVISIONAL["fullness_ratio_min"], [ratio(r, "ratio_area_over_H2") for r in results])
    row("Q21-2 背の殻 / H（c -2..+2 平均）", "参照 %.3f" % (results[0]["Q21_2"].get("reference", {}).get("shell_over_H_mean", float("nan"))),
        [fmt(r["Q21_2"].get("shell_over_H_mean_c-2_2"), 3) for r in results])
    row("Q21-2 殻の比（参照に対して）", "≥ %.2f（暫定）" % PROVISIONAL["fullness_ratio_min"], [ratio(r, "ratio_shell_over_H") for r in results])
    row("Q21-2 水面より上の体積 c -14..+14（m³）/ 参照比", "参照 %.0f" % (results[0]["Q21_2"].get("reference", {}).get("volume_c-14_14_m3", float("nan"))),
        ["%.0f / %.2f" % (r["Q21_2"]["volume_above_water_c-14_14_m3"], r["Q21_2"].get("ratio_volume_c-14_14", float("nan"))) for r in results])
    # Q21-3
    for k, nm in (("top_vs_top_smooth", "稜（帯の上端）"), ("bottom_vs_bottom_smooth", "爪の縁（帯の下端）")):
        vals = []
        for r in results:
            v = r["Q21_3"].get(k)
            if not isinstance(v, dict) or v.get("median_px") is None:
                vals.append("—"); continue
            vals.append("%.1f / %.1f / %.1f%s" % (v["median_px"], v["p90_px"], v["max_px"], "" if v["median_px"] <= PROVISIONAL["band_median_px"] else " ✗"))
        row("**Q21-3 b 区域 %s 中央値 / p90 / 最大（px）**" % nm, "中央値 ≤ %.0f（≈10 px、暫定）" % PROVISIONAL["band_median_px"], vals)
    row("第二の波頭 S1（帯の射線が第二の段に乗る割合）", "記録（F09 S1）", [fmt(r["S1"].get("share_on_second_tier"), 3) if isinstance(r.get("S1"), dict) else "—" for r in results])
    row("空の差：原画の波の中の穴 / 空へのはみ出し（px）", "記録", ["%d / %d" % (r["sky"]["vs_painting_holes_in_wave"]["px"], r["sky"]["vs_painting_spill_into_sky"]["px"]) for r in results])
    if all("mesh" in r for r in results):
        row("メッシュ：局所の自己交差の頂点 / 裏返り", "0", ["%d / %d" % (r["mesh"]["local_selfx_vertices_win6"], r["mesh"]["flipped_quads_gt150"]) for r in results])
        row("メッシュ：行をまたぐ折れ >30° / >60°", "記録", ["%d / %d" % (r["mesh"]["cross_row_gt30_all"], r["mesh"]["cross_row_gt60_all"]) for r in results])
        row("メッシュ：面積 < 1e-6 m² の三角形", "0", [str(r["mesh"]["degenerate_lt_1e-6"]) for r in results])
    row("頂の列（argmax）の範囲 / 90±5 から外れた行", "記録", ["%s / %d" % (r["landmarks"]["top_col_argmax_range"], r["landmarks"]["rows_top_not_at_90_pm5"]) for r in results])
    row("H0（主断面）/ 最高点（m）/ その c", "記録", ["%.2f / %.2f / %+.1f" % (r["shape"]["H0_main_m"], r["shape"]["H_max_m"], r["shape"]["c_of_H_max"]) for r in results])
    return "\n".join(L)


def main():
    args = sys.argv[1:]
    out = None; do_f13 = True; do_mesh = True; columns = "auto"; do_render = False; do_tt = False
    items = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--out":
            out = args[i + 1]; i += 2; continue
        if a == "--no-f13":
            do_f13 = False; i += 1; continue
        if a == "--no-mesh":
            do_mesh = False; i += 1; continue
        if a == "--render":
            do_render = True; i += 1; continue
        if a == "--turntable":
            do_render = True; do_tt = True; i += 1; continue
        if a == "--columns":
            columns = args[i + 1]; i += 2; continue
        lab, p = a.split("=", 1)
        items.append((lab, p)); i += 1
    if not items:
        raise SystemExit(__doc__)
    out = out or os.path.join(KC.OUT_ROOT, "eval", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    cache = None
    results = []
    try:
        if do_f13:
            cache, h = build_ref_cache(KC.TMP)
            log("reference cache (F13) sha-checked %s...%s (%.0fs)" % (h[:8], h[-4:], time.time() - t0))
        for lab, spec in items:
            log("== %s: %s" % (lab, spec))
            rows, src = resolve(lab, spec, out, columns)
            results.append(evaluate_one(lab, rows, src, cache, do_mesh))
    finally:
        drop_ref_cache(cache)
    if do_render:
        t1 = time.time()
        render(results, out, do_tt)
        log("renders written (%.0fs)" % (time.time() - t1))
    tab = table(results)
    head = ["# kstar_h 評価表（%s）" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "",
            "命令：`py -3.10 Tools/GWWaveGen/kstar_h/kh_eval.py %s`" % " ".join(sys.argv[1:]), "",
            "候補：" + "、".join("%s = `%s`" % (r["label"], r["input"]["spec"]) for r in results), "",
            "✗ = 必須または暫定の基準を満たさない。暫定の基準（kstar_h が置いたもの、利用者の決定ではない）：%s。" % json.dumps(PROVISIONAL, ensure_ascii=False), "",
            "参照モデルは他者の作品（作者・所蔵は未確認）。F13 と量感の比較の数値だけに使い、形は写さない。", ""]
    open(os.path.join(out, "kh_eval_table.md"), "w", encoding="utf-8").write("\n".join(head) + tab + "\n")
    summ = {"schema": "GreatWave.kstar_h.eval/1", "command": sys.argv, "out": out, "seconds": round(time.time() - t0, 1),
            "provisional_thresholds": PROVISIONAL, "rubric_module": os.path.abspath(RC.__file__), "code_sha256": {os.path.basename(p): KC.sha256(p) for p in (
                os.path.join(HERE, "kh_eval.py"), os.path.join(HERE, "kh_common.py"), os.path.join(KSTAR3, "candA4_checks.py"),
                os.path.join(KSTAR3, "fin_eval.py"), os.path.join(RUBRIC_TOOLS, "rubric_check.py"), os.path.join(KSTAR3, "candA4_fit.py"))},
            "candidates": results}
    json.dump(summ, open(os.path.join(out, "kh_eval_summary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    log(tab)
    log("written %s (%.0fs)" % (out, time.time() - t0))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
