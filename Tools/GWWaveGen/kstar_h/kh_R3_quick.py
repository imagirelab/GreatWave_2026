# -*- coding: utf-8 -*-
"""K*′ 精修 R3：設計の json（kh_designR3）または行の npz を素早く測る（py -3.10、1 候補 約 30〜60 秒）。当てはめの途中の判断用。
  原画の関門（公式と大きな輪郭）、評審 R2 の測り（上から見た背のくびれ notch：y 3 / 6 / 10 m の背の平面の線の ±4 m の弦からの前への出、
  評審の膨らみ j_bulge6 と同じ式の R4 / R6 と区域ごとの p99、4 階差 bump4）、メッシュの衛生（fin_eval.mesh_hygiene：局所の自己交差・
  裏返り・行をまたぐ折れ）、形の検査（kh_R1_quick）、ルーブリック（Tools/GWWaveGen/rubric の写し、F03 は 2026-09-29 に緩めた版）、
  --q21：量感（Q21-2）と b 区域の帯（Q21-3）。
usage: py -3.10 kh_R3_quick.py [--q21] [--no-rubric] [--json OUT] label=design.json|rows.npz ...
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys
import json
import time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"),
          os.path.join(REPO, "Tools", "GWWaveGen"), os.path.join(REPO, "Tools", "GWWaveGen", "rubric")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import importlib.util  # noqa: E402
for _n in ("rubric_measure", "rubric_check"):           # the repository copy first (kstar3/fin_eval would import the git-ignored one)
    _sp = importlib.util.spec_from_file_location(_n, os.path.join(REPO, "Tools", "GWWaveGen", "rubric", _n + ".py"))
    _m = importlib.util.module_from_spec(_sp); sys.modules[_n] = _m; _sp.loader.exec_module(_m)
import kh_designR3 as D  # noqa: E402
import kh_R1_quick as Q1  # noqa: E402

TMP = os.path.join(REPO, "Unity", "Build", "Q20H", "final", "_work", "R3", "tmp")


def load(spec):
    if spec.endswith(".json"):
        c, A, Y, P = D.build(D.Design.load(spec))
        return c, A, Y
    z = np.load(spec)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def back_plan_notch(c, A, Y, heights=(3.0, 6.0, 10.0)):
    """the judges' R2 measure (Unity/Build/Q20H/_judge_R2/rj_shape.py): per absolute height h the plan position a of the back (cols 0..top)
    along c (0.5 m), and its forward deviation from the chord of c +-4 m (positive = the back pushed forward = a waist)."""
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
        cq = np.arange(-14, 14.01, 0.5)
        m = np.isfinite(ab)
        v = np.interp(cq, c[m], ab[m]); v[(cq < c[m].min()) | (cq > c[m].max())] = np.nan
        dev = []
        for i, cc in enumerate(cq):
            j0 = np.searchsorted(cq, cc - 4); j1 = np.searchsorted(cq, cc + 4)
            if j0 < 0 or j1 >= len(cq) or not (np.isfinite(v[j0]) and np.isfinite(v[j1]) and np.isfinite(v[i])):
                dev.append(np.nan); continue
            dev.append(v[i] - 0.5 * (v[j0] + v[j1]))
        dev = np.array(dev)
        k = int(np.nanargmax(dev))
        out["y%g" % h] = {"notch_max_m": round(float(dev[k]), 3), "at_c": float(cq[k])}
    return out


def bulge_regions(c, A, Y):
    r = Q1.bulge6(c, A, Y, 2, 3)
    cc = np.repeat(c[:, None], D.NU, 1)
    jj = np.arange(D.NU)[None, :]
    for R in ("R4", "R6"):
        M = Q1._CACHE["bulgemap_" + R]
        f = np.isfinite(M)
        reg = {}
        for nm, (ca, cb) in (("shoulder c<-5", (-16, -5)), ("main -5..+3", (-5, 3)), ("mid +3..+9", (3, 9)), ("far +9..+16", (9, 16))):
            mm = f & (cc >= ca) & (cc < cb)
            if mm.sum() > 10:
                reg[nm] = round(float(np.percentile(M[mm], 99)), 2)
        for nm, (ja, jb) in (("back cols<75", (0, 75)), ("crest+lip cols>=75", (75, 400))):
            mm = f & (jj >= ja) & (jj < jb)
            if mm.sum() > 10:
                reg[nm] = round(float(np.percentile(M[mm], 99)), 2)
        thr = 0.31 if R == "R4" else 0.6
        rr, jx = np.nonzero(f & (M > thr))
        r[R]["n_over_target"] = int(len(rr))
        r[R]["over_target_c_cols"] = sorted(set((round(float(c[a]) / 2) * 2, int(b) // 20 * 20) for a, b in zip(rr, jx)))[:20]
        r[R]["regions_p99"] = reg
    return r


def bump(c, A, Y):
    import kh_fitA as KF
    b = KF.bump4(c, A, Y)
    d1 = b["d1"]
    i, k = np.unravel_index(np.argsort(d1.ravel())[-3:], d1.shape)
    out = {"d1_p99": round(float(np.percentile(d1, 99)), 3), "d1_max": round(float(d1.max()), 3),
           "d1_top_c_col": [[float(KF.BUMP_C[a]), int(KF.BUMP_J[b_])] for a, b_ in zip(i, k)]}
    # the lip edge (the tip strip 180..220 that bump4 leaves out), c -9..+13
    X3 = KF.D_world(c, A, Y)[:, np.arange(180, 221, 4), :]
    C = np.arange(-9.0, 13.01, 0.5)
    P = [np.stack([np.stack([np.interp(C + kk, c, X3[:, j, q]) for q in range(3)], -1) for j in range(X3.shape[1])], 0) for kk in (-2, -1, 0, 1, 2)]
    v = np.linalg.norm(P[0] - 4 * P[1] + 6 * P[2] - 4 * P[3] + P[4], axis=-1)
    out["lipedge_d1_p99"] = round(float(np.percentile(v, 99)), 3)
    out["lipedge_d1_max"] = round(float(v.max()), 3)
    return out


def mesh(c, A, Y):
    import candA_common as C
    import fin_eval as FE
    V1, tgt, fr = C.painting_frame()
    m = FE.mesh_hygiene(c, A, Y, V1)
    return {k: m[k] for k in ("local_selfx_vertices_win6", "local_selfx_rows", "flipped_quads_gt150", "flipped_rows", "cross_row_gt30_all",
                              "cross_row_gt60_all", "cross_row_gt30_by_c", "degenerate_lt_1e-6", "min_tri_area_m2")}


def rubric(c, A, Y, tag):
    import rubric_check as RC
    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, "rq_%s_rows.npz" % tag)
    np.savez_compressed(p, A=A, Y=Y, c=c)
    R = RC.check(p)
    fails, keep = [], {}
    for f, L in R["checks"].items():
        for x in L:
            v = x["value"]
            vv = v if not isinstance(v, float) else round(v, 3)
            if isinstance(v, list):
                vv = [round(float(t), 3) for t in v]
            if x["pass_must"] is not None and not bool(x["pass_must"]):
                fails.append("%s %s=%s" % (f, x["name"][:30], json.dumps(vv)))
            if f == "F03" or any(k in x["name"] for k in ("折れ > 30", "奥 c > +3", "最長 / H(c)")):
                keep[f + " " + x["name"][:26]] = vv
    return {"n_must_fail_nogate": len(fails), "fails": fails, "key": keep}


def q21(c, A, Y):
    import candA_common as C
    import candA4_checks as CK
    V1, tgt, fr = C.painting_frame()
    sil, grown, cov = CK.silhouette_band(c, A, Y, V1, fr)
    out = {}
    try:
        b = CK.band_check(c, A, Y, cov)
        out["band"] = {k: b.get(k) for k in ("top_vs_top_smooth", "bottom_vs_bottom_smooth")}
    except Exception as e:
        out["band"] = {"error": str(e)}
    try:
        f = CK.fullness(c, A, Y)
        rows = f["rows"]
        ks = ("-2", "-1", "+0", "+1", "+2")
        out["area_over_H2_c-2_2"] = round(float(np.mean([rows[k]["area_over_H2"] for k in ks if k in rows])), 3)
        sh = [rows[k]["shell_normal_median_over_H"] for k in ks if k in rows and rows[k]["shell_normal_median_over_H"] is not None]
        out["shell_over_H_c-2_2"] = round(float(np.mean(sh)), 3) if sh else None
        out["ratio_area_vs_ref0.317"] = round(out["area_over_H2_c-2_2"] / 0.317, 2)
        out["ratio_shell_vs_ref0.289"] = round(out["shell_over_H_c-2_2"] / 0.289, 2) if sh else None
    except Exception as e:
        out["fullness"] = {"error": str(e)}
    return out


def quick(spec, tag, do_rubric=True, do_q21=False):
    t0 = time.time()
    c, A, Y = load(spec)
    os.makedirs(TMP, exist_ok=True)
    r = {"gate": Q1.official_gate(c, A, Y, os.path.join(TMP, "gate_%s.png" % tag)), "gate_lf": Q1.lf_gate(c, A, Y)}
    r["gate_pass_lf"] = bool(all(r["gate"][k]["max"] <= 4 for k in ("78", "130", "131")) and r["gate_lf"]["132"]["max"] <= 4
                             and r["gate_lf"]["72"]["p95"] <= 4)
    r["notch"] = back_plan_notch(c, A, Y)
    r["bulge6"] = bulge_regions(c, A, Y)
    r["bump4"] = bump(c, A, Y)
    r["mesh"] = mesh(c, A, Y)
    sc = Q1.shape_checks(c, A, Y)
    r["shape"] = {k: sc[k] for k in ("H0", "Hmax", "c_Hmax", "H_peaks_prom_ge_0p5", "lip_clearance_min_m", "lip_clearance_rows_lt0",
                                     "section_selfx_rows", "section_selfx_c", "top_excess_max_m", "edge_rows_absY_max")}
    if do_rubric:
        r["rubric"] = rubric(c, A, Y, tag)
    if do_q21:
        r["q21"] = q21(c, A, Y)
    r["seconds"] = round(time.time() - t0, 1)
    return r, (c, A, Y)


def brief(r):
    g, lf = r["gate"], r["gate_lf"]
    s = "gate 78/130/131 %.2f/%.2f/%.2f 132lf %.2f 72lf p95 %.2f %s | notch y3 %.2f@%g y6 %.2f@%g y10 %.2f@%g | R4 %.3f R6 %.3f %s | bump4 %.2f lip %.2f | mesh selfx %d flip %d gt60 %d | selfx_rows %d clear %.3f" % (
        g["78"]["max"], g["130"]["max"], g["131"]["max"], lf["132"]["max"], lf["72"]["p95"], "PASS" if r["gate_pass_lf"] else "FAIL",
        r["notch"]["y3"]["notch_max_m"], r["notch"]["y3"]["at_c"], r["notch"]["y6"]["notch_max_m"], r["notch"]["y6"]["at_c"],
        r["notch"]["y10"]["notch_max_m"], r["notch"]["y10"]["at_c"],
        r["bulge6"]["R4"]["p99"], r["bulge6"]["R6"]["p99"], json.dumps(r["bulge6"]["R6"]["regions_p99"]),
        r["bump4"]["d1_p99"], r["bump4"]["lipedge_d1_p99"],
        r["mesh"]["local_selfx_vertices_win6"], r["mesh"]["flipped_quads_gt150"], r["mesh"]["cross_row_gt60_all"],
        r["shape"]["section_selfx_rows"], r["shape"]["lip_clearance_min_m"])
    if "rubric" in r:
        s += " | rubric must-fail %d" % r["rubric"]["n_must_fail_nogate"]
    return s


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    jo = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    res = {}
    skip = {jo}
    for a in sys.argv[1:]:
        if a.startswith("--") or a in skip:
            continue
        lab, spec = a.split("=", 1)
        r, _ = quick(spec, lab, "--no-rubric" not in sys.argv, "--q21" in sys.argv)
        res[lab] = r
        print(lab, brief(r), flush=True)
        if "rubric" in r:
            print("   fails:", "; ".join(r["rubric"]["fails"]), flush=True)
            print("   F03:", json.dumps({k: v for k, v in r["rubric"]["key"].items() if k.startswith("F03")}, ensure_ascii=False), flush=True)
        if "q21" in r:
            print("   q21:", json.dumps(r["q21"], ensure_ascii=False), flush=True)
        print("   mesh:", json.dumps({k: r["mesh"][k] for k in ("local_selfx_rows", "flipped_rows", "cross_row_gt30_by_c")}), "shape:", json.dumps(r["shape"]), flush=True)
    if jo:
        json.dump(res, open(jo, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
