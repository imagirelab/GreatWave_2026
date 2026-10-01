# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）の速い測り（py -3.10、1 候補 約 3〜5 秒）。最適化の費用と途中の判断に使う。

  gate   原画の関門を 1 回の描画で測る：78/130/131 は原画の線そのもの（定義どおりの読み、評価器の包絡版の真値の点）、
         132・72 は σ 12 px の大きな輪郭（kh_gate_lf、28修正01 の 9/28 20:00 の読み。σ 24 の緩めは使わない）。
  dome   評審の j_bulge6 と同じ式（6×… の局所の 2 次曲面の中心の残差、R4 / R6）を粗い間隔で（row_step, col_step）。
  sag    candA4_checks.sag3m と同じ式（c ±1.5 m の法線の撓み、行の帯の内側、列 18〜380）。
  f04    評価基準 F04 の側面の影の幅 0.5H0・0.9H0、正面の幅 0.75H0、奥の体積。
  full   量感（断面積 / H²、c −2〜+2 の平均、参照 0.317 との比）。
  selfx  断面の自己交差の行の数（kh_designR4.section_selfx）、唇の上下の間隔の最小。
参照モデルは読まない。
"""
import os
import sys
import time
import json
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
sys.dont_write_bytecode = True
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"), os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"),
          os.path.join(REPO, "Tools", "PaintingTruth"), os.path.join(REPO, "Tools", "GWWaveGen"),
          os.path.join(REPO, "Tools", "GWWaveGen", "rubric")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402

_C = {}
REF_AREA_OVER_H2 = 0.317   # numbers-only file Q20L3/candA4/_model_side/ref_fullness.json（kh_eval と同じ参照の数）


def _gate_obj():
    if "g" not in _C:
        import kh_gate_lf as KG
        g = KG.LFGate()
        import candA_common as C
        import gw_wavegen as G0
        V1, tgt, fr = C.painting_frame()
        seacov, _ = G0.sea_horizon_cover(fr.cam, tgt.spec)
        _C["g"] = (g, V1, tgt, fr, seacov)
    return _C["g"]


def gate(c, A, Y, want_cov=False):
    g, V1, tgt, fr, seacov = _gate_obj()
    X = fr.world(c, A, Y)
    cov = V1.rasterize(fr.cam, X, V1.triangles(A.shape[1], A.shape[0]))
    other = np.maximum(cov, seacov)
    rpts = g.T.boundary_points(1.0 - other, g.truth.spec, g.truth.fmap)
    F = g.truth.fam["sky_envelope"]
    out = {}
    for k in ("78", "130", "131"):
        res, _, worst = g.T.labelled_hausdorff(F["pts"], F["label"] == k, rpts)
        out[k] = {"max": float(res["max_px"]), "p95": float(res["p95_px"])}
    for k in ("132", "72"):
        res, _, worst = g.T.labelled_hausdorff(g.pts, g.lab == k, rpts)
        out[k + "lf"] = {"max": float(res["max_px"]), "p95": float(res["p95_px"]),
                         "worst": None if worst is None else [round(float(worst[0]), 1), round(float(worst[1]), 1)]}
    for k in ("132", "72"):
        res, _, worst = g.T.labelled_hausdorff(F["pts"], F["label"] == k, rpts)
        out[k + "raw"] = {"max": float(res["max_px"]), "p95": float(res["p95_px"])}
    # sky spill / holes vs the painted sky (scored frame) — pixels
    sky = g.truth.cov["sky_envelope"]
    fm = g.truth.fmap if hasattr(g.truth, "fmap") else None
    wave = cov > 0.5
    out["spill_px"] = int((wave & (sky > 0.5)).sum())
    out["pass"] = bool(all(out[k]["max"] <= 4 for k in ("78", "130", "131")) and out["132lf"]["max"] <= 4 and out["72lf"]["p95"] <= 4)
    if want_cov:
        return out, cov
    return out


def world(c, A, Y):
    E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
    O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
    return O[None, None, :] + A[..., None] * T + Y[..., None] * np.array([0, 1.0, 0]) + c[:, None, None] * E


def dome(c, A, Y, row_step=2, col_step=3, radii=(4.0, 6.0), regions=True):
    """j_bulge6 と同じ式（Unity/Build/Q20L3/judge_fid/j_bulge6.py）。row_step=2, col_step=3 が評審の間隔。"""
    X = world(c, A, Y)
    nv, nu = A.shape
    s = np.concatenate([np.zeros((nv, 1)), np.cumsum(np.linalg.norm(np.diff(X, axis=1), axis=-1), 1)], 1)
    tip = np.full(nv, 200)
    rows = [r for r in range(nv) if abs(c[r]) <= 16][::row_step]
    out = {}
    for Rm in radii:
        M = np.full((nv, nu), np.nan)
        for r0 in rows:
            rs = np.nonzero(np.abs(c - c[r0]) <= Rm)[0][::2]
            for j0 in range(18, 201, col_step):
                if Y[r0, j0] < 0.5 or j0 > tip[r0] - 12:
                    continue
                pts = []
                for r in rs:
                    jj = np.nonzero((np.abs(s[r] - s[r, j0]) <= Rm) & (np.arange(nu) <= tip[r] - 8))[0][::2]
                    pts.append(X[r, jj])
                P = np.concatenate(pts)
                P = P[np.linalg.norm(P - X[r0, j0], axis=1) <= Rm]
                if len(P) < 30:
                    continue
                mu = P.mean(0); _, _, Vt = np.linalg.svd(P - mu, full_matrices=False)
                Q = P - X[r0, j0]; u = Q @ Vt[0]; v = Q @ Vt[1]; w = Q @ Vt[2]
                Mx = np.c_[np.ones_like(u), u, v, u * u, u * v, v * v]
                co, *_ = np.linalg.lstsq(Mx, w, rcond=None)
                M[r0, j0] = abs(co[0])
        f = np.isfinite(M)
        o = {"p99": float(np.nanpercentile(M, 99)), "max": float(np.nanmax(M)), "gt0p3": float((M[f] > 0.3).mean())}
        if regions:
            cc = np.repeat(c[:, None], nu, 1); reg = {}
            for nm, (ja, jb) in (("back", (18, 90)), ("crest_liptop", (90, 201))):
                for cn, (ca, cb) in (("shoulder", (-16, -6)), ("main", (-6, 3)), ("far", (3, 16))):
                    mm = f & (np.arange(nu)[None, :] >= ja) & (np.arange(nu)[None, :] < jb) & (cc >= ca) & (cc < cb)
                    if mm.sum() > 10:
                        reg[nm + "/" + cn] = round(float(np.percentile(M[mm], 99)), 3)
            o["regions_p99"] = reg
        out["R%g" % Rm] = o
        _C["dome_map_R%g" % Rm] = M
    return out


def sag3m(c, A, Y, band=None):
    """candA4_checks.sag3m と同じ式。band（輪郭の帯、True = 除く）を与えなければ帯を除かない（速い版）。"""
    X = world(c, A, Y)
    Xu = np.gradient(X, axis=1); Xv = np.gradient(X, c, axis=0)
    Nrm = np.cross(Xu, Xv); Nrm /= np.maximum(np.linalg.norm(Nrm, axis=-1), 1e-12)[..., None]
    rows = np.nonzero((c >= -18.5) & (c <= 14.5))[0]
    J = np.arange(18, 380)
    vals = []; worst = []
    Xi = {}
    for dq in (-1.5, 1.5):
        q = c[rows] + dq
        Xi[dq] = np.stack([np.stack([np.interp(q, c, X[:, j, k]) for k in range(3)], -1) for j in J], 1)   # (len(rows), len(J), 3)
    for i, r in enumerate(rows):
        s = np.abs(((X[r, J] - 0.5 * (Xi[-1.5][i] + Xi[1.5][i])) * Nrm[r, J]).sum(-1))
        ok = Y[r, J] > 0.3
        if band is not None:
            ok &= ~band[r, J]
        if (c[r] > 16) or (c[r] < -16):
            pass
        if ok.any():
            vals.append(s[ok]); worst.append((round(float(c[r]), 1), round(float(s[ok].max()), 3), int(J[np.argmax(np.where(ok, s, -1))])))
    v = np.concatenate(vals)
    worst = sorted(worst, key=lambda t: -t[1])[:6]
    return {"p99": float(np.percentile(v, 99)), "p95": float(np.percentile(v, 95)), "max": float(v.max()), "n_gt_0p3": int((v > 0.3).sum()), "worst": worst}


def f04(c, A, Y):
    import rubric_measure as RM
    import rubric_check as RC
    H = Y.max(1); main = int(np.argmin(np.abs(c))); H0 = float(H[main])
    wid = {}; ext = {}
    for f in (0.5, 0.9):
        lo, hi = [], []
        for r in range(len(c)):
            if H[r] < f * H0:
                continue
            xs = RM.crossings(RM.poly_to_segs(A[r], Y[r]), f * H0)
            if len(xs) >= 2:
                lo.append((xs.min(), c[r])); hi.append((xs.max(), c[r]))
        if lo:
            l = min(lo); h = max(hi)
            wid[f] = float(h[0] - l[0]); ext[f] = [round(float(l[0]), 2), round(float(l[1]), 1), round(float(h[0]), 2), round(float(h[1]), 1)]
        else:
            wid[f] = 0.0
    ce = c[H >= 0.75 * H0]
    front = float(ce.max() - ce.min()) if len(ce) else 0.0
    dc = np.gradient(c)
    vol = float(sum(RC.section_area(A[r], Y[r]) * dc[r] for r in range(len(c)) if c[r] > 0))
    return {"side_0p5": wid[0.5], "side_0p9": wid[0.9], "front_0p75": front, "far_vol": vol, "ext_0p5": ext.get(0.5), "H0": H0,
            "Hmax": float(H.max()), "c_Hmax": float(c[int(np.argmax(H))])}


def fullness(c, A, Y):
    import rubric_check as RC
    v = []
    for cc in (-2, -1, 0, 1, 2):
        r = int(np.argmin(np.abs(c - cc)))
        H = Y[r].max()
        v.append(RC.section_area(A[r], Y[r]) / H ** 2)
    m = float(np.mean(v))
    return {"area_over_H2": m, "ratio_vs_ref": m / REF_AREA_OVER_H2}


def selfx(c, A, Y):
    import kh_designR4 as D
    sx = D.section_selfx(A, Y)
    mins, cols = D.lip_clearance(A, Y)
    return {"section_selfx_rows": len(sx), "selfx_c": [round(float(c[r]), 1) for r in sorted(sx)][:10], "lip_clear_min": float(mins.min()),
            "lip_clear_rows_lt0": int((mins < 0).sum())}


def band(c, A, Y):
    """b 区域の帯（candA4_checks.band_check：稜＝帯の上端、爪の縁＝帯の下端の像と、原画の帯の輪郭の差）。"""
    import candA_common as C
    import candA4_checks as CK
    V1, tgt, fr = C.painting_frame()
    sil, grown, cov = CK.silhouette_band(c, A, Y, V1, fr)
    b = CK.band_check(c, A, Y, cov)
    return {k: {q: b[k][q] for q in ("median_px", "p90_px", "max_px", "covered_samples", "target_samples")} for k in ("top_vs_top_smooth", "bottom_vs_bottom_smooth")}


def quick(c, A, Y, do_dome=True, dome_step=(2, 3), do_band=True):
    t0 = time.time()
    r = {"gate": gate(c, A, Y)}
    if do_band:
        try:
            r["band"] = band(c, A, Y)
        except Exception as e:
            r["band"] = {"error": str(e)}
    if do_dome:
        r["dome"] = dome(c, A, Y, *dome_step)
    r["sag"] = sag3m(c, A, Y)
    r["f04"] = f04(c, A, Y)
    r["full"] = fullness(c, A, Y)
    r["selfx"] = selfx(c, A, Y)
    r["sec"] = round(time.time() - t0, 1)
    return r


def brief(r):
    g = r["gate"]
    s = "gate 78/130/131 %.2f/%.2f/%.2f 132lf %.2f 72lf p95 %.2f (max %.2f) %s spill %d" % (
        g["78"]["max"], g["130"]["max"], g["131"]["max"], g["132lf"]["max"], g["72lf"]["p95"], g["72lf"]["max"], "PASS" if g["pass"] else "FAIL", g["spill_px"])
    if "dome" in r:
        s += " | R4 %.3f R6 %.3f %s" % (r["dome"]["R4"]["p99"], r["dome"]["R6"]["p99"], json.dumps(r["dome"]["R6"].get("regions_p99", {})))
    if "band" in r and "error" not in r["band"]:
        t_, b_ = r["band"]["top_vs_top_smooth"], r["band"]["bottom_vs_bottom_smooth"]
        s += " | band top %.1f/%.1f/%.1f (%d) bot %.1f/%.1f/%.1f (%d)" % (t_["median_px"], t_["p90_px"], t_["max_px"], t_["covered_samples"],
                                                                     b_["median_px"], b_["p90_px"], b_["max_px"], b_["covered_samples"])
    s += " | sag p99 %.3f max %.3f | F04 %.2f/%.2f front %.1f vol %.0f ext %s | full %.2f | selfx %d clear %.3f (%.1fs)" % (
        r["sag"]["p99"], r["sag"]["max"], r["f04"]["side_0p5"], r["f04"]["side_0p9"], r["f04"]["front_0p75"], r["f04"]["far_vol"], r["f04"]["ext_0p5"],
        r["full"]["ratio_vs_ref"], r["selfx"]["section_selfx_rows"], r["selfx"]["lip_clear_min"], r["sec"])
    return s


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for a in sys.argv[1:]:
        lab, p = a.split("=", 1)
        z = np.load(p)
        r = quick(z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float))
        print(lab, brief(r), flush=True)
        print("   sag worst", r["sag"]["worst"], "72 worst", r["gate"]["72lf"]["worst"], "132 worst", r["gate"]["132lf"]["worst"], flush=True)


def overlay(c, A, Y, path, title=""):
    """原画の上に候補の被覆の輪郭（白）、真値の輪郭（78 赤 / 130 橙 / 131 黄 / 132 緑 / 72 紫）、132・72 の大きな輪郭（細い）を描く。"""
    import cv2
    g, V1, tgt, fr, seacov = _gate_obj()
    res, cov = gate(c, A, Y, want_cov=True)
    plate = cv2.imread(os.path.join(REPO, "Unity", "Build", "Q20H", "plate", "painting_display_1920x1080.png"))
    img = (plate * 0.6).astype(np.uint8)
    m = (cov > 0.5).astype(np.uint8)
    img[m > 0] = (img[m > 0] * 0.6 + np.array([200, 130, 60]) * 0.4).astype(np.uint8)
    cn, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, cn, -1, (255, 255, 255), 1, cv2.LINE_AA)
    cols = {"78": (0, 0, 255), "130": (0, 160, 255), "131": (0, 255, 255), "132": (0, 255, 0), "72": (255, 0, 255)}
    for s in g.truth.outline["envelope"]["segments"]:
        P = np.array(s["points_display"], float)
        cv2.polylines(img, [np.round(P).astype(np.int32).reshape(-1, 1, 2)], False, cols.get(s["id"], (180, 180, 180)), 1, cv2.LINE_AA)
    for k in ("132", "72"):
        cv2.polylines(img, [np.round(g.lf[k]).astype(np.int32).reshape(-1, 1, 2)], False, (255, 255, 0), 1, cv2.LINE_AA)
    txt = "%s  78/130/131 %.2f/%.2f/%.2f  132lf(s12) %.2f  72lf(s12) p95 %.2f  %s" % (
        title, res["78"]["max"], res["130"]["max"], res["131"]["max"], res["132lf"]["max"], res["72lf"]["p95"], "PASS" if res["pass"] else "FAIL")
    cv2.putText(img, txt, (170, 1060), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(path, img)
    return res


def rubric(c, A, Y, tmp_dir):
    """評価基準（Tools/GWWaveGen/rubric/rubric_check.py、関門なし）の必須の否の一覧（F01 は含まない）。"""
    import importlib.util
    for _n in ("rubric_measure", "rubric_check"):
        if _n not in sys.modules or "Tools" not in sys.modules[_n].__file__:
            _sp = importlib.util.spec_from_file_location(_n, os.path.join(REPO, "Tools", "GWWaveGen", "rubric", _n + ".py"))
            _m = importlib.util.module_from_spec(_sp); sys.modules[_n] = _m; _sp.loader.exec_module(_m)
    RC = sys.modules["rubric_check"]
    os.makedirs(tmp_dir, exist_ok=True)
    p = os.path.join(tmp_dir, "_rubric_rows_%d.npz" % os.getpid())
    np.savez_compressed(p, A=A, Y=Y, c=c)
    R = RC.check(p)
    os.remove(p)
    fails = []
    for f, L in R["checks"].items():
        for x in L:
            if x["pass_must"] is not None and not bool(x["pass_must"]):
                v = x["value"]
                v = [round(float(t), 2) for t in v] if isinstance(v, list) else (round(float(v), 2) if isinstance(v, (int, float)) else v)
                fails.append("%s %s=%s" % (f, x["name"][:28], v))
    return {"n_must_fail": len(fails), "fails": fails}
