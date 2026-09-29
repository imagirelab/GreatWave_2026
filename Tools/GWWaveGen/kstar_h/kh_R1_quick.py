# -*- coding: utf-8 -*-
"""K*′ 精修 R1：設計の json（または行の npz）を素早く測る（py -3.10、1 候補 約 20〜40 秒）。当てはめの途中の判断用。
  原画の関門（公式の gw_wavegen_v1.preview_metrics と大きな輪郭 kh_gate_lfA）、評審の膨らみ（j_bulge6 と同じ式、行・列を間引き）、
  唇の交差（断面の自己交差・唇の間隔）、頂の列より高い点、列 314 の高さ / H、H(c) の山と主断面、外周の行の高さ、4 階差。
usage: py -3.10 kh_R1_quick.py [--full-bulge] label=design.json|rows.npz ...
"""
import os
import sys
import json
import time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"),
          os.path.join(REPO, "Tools", "GWWaveGen")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import kh_designR1 as D  # noqa: E402

_CACHE = {}


def official_gate(c, A, Y, overlay=None):
    import truthlib as TL
    import gw_wavegen_v1 as V1
    if "fr" not in _CACHE:
        params = TL.load_json(os.path.join(REPO, "Tools", "GWWaveGen", "params_v2_af26r01.json"))
        tgt = V1.Target(); fr = V1.Frame(tgt.spec, float(params["alpha_deg"]), params["anchor"], tgt)
        _CACHE["fr"] = (tgt, fr)
    tgt, fr = _CACHE["fr"]
    nv, nu = A.shape
    Xw = fr.world(c, A, Y)
    out = overlay or os.path.join(REPO, "Unity", "Build", "Q20H", "final", "_work", "quick_gate_overlay.png")
    g = V1.preview_metrics(fr, tgt, Xw, V1.triangles(nu, nv), out, "R1 quick")
    return {k: {"max": round(float(g[k]["max_px"]), 2), "p95": round(float(g[k]["p95_px"]), 2)} for k in ("78", "130", "131", "132", "72")}


def lf_gate(c, A, Y):
    import kh_gate_lfA as KG
    if "lf" not in _CACHE:
        _CACHE["lf"] = KG.LFGate()
    r, _ = _CACHE["lf"].measure_rows(c, A, Y)
    return {k: {"max": round(v["max_px"], 2), "p95": round(v["p95_px"], 2), "worst": v["worst_xy"]} for k, v in r.items()}


def bulge6(c, A, Y, row_step=2, col_step=3, radii=(4.0, 6.0)):
    """the judges' j_bulge6 (round 3) measure: local quadric over a Rm neighbourhood, |centre residual| (m)."""
    E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
    O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
    X = O[None, None, :] + A[..., None] * T + Y[..., None] * np.array([0, 1.0, 0]) + c[:, None, None] * E
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
        im = np.unravel_index(np.nanargmax(M), M.shape)
        out["R%g" % Rm] = {"p99": round(float(np.nanpercentile(M, 99)), 3), "max": round(float(np.nanmax(M)), 3),
                           "at_c_col": [round(float(c[im[0]]), 1), int(im[1])], "gt0p3": round(float((M[f] > 0.3).mean()), 3)}
        _CACHE["bulgemap_R%g" % Rm] = M
    return out


def shape_checks(c, A, Y):
    H = Y.max(1)
    r0 = int(np.argmin(np.abs(c)))
    out = {"H0": round(float(H[r0]), 2), "Hmax": round(float(H.max()), 2), "c_Hmax": round(float(c[int(np.argmax(H))]), 2)}
    # peaks of H(c) above 0.5 H0 with prominence >= 0.5 m (rubric F10 style)
    Hs = H.copy(); pk = []
    for i in range(1, len(Hs) - 1):
        if Hs[i] >= Hs[i - 1] and Hs[i] > Hs[i + 1] and Hs[i] > 0.5 * H[r0]:
            left = Hs[:i].min() if i > 0 else Hs[i]
            lmin = Hs[:i][::-1]; rmin = Hs[i + 1:]
            # prominence: drop to the higher of the two surrounding minima before a higher point
            def side_min(v):
                m = Hs[i]
                for x in v:
                    if x > Hs[i]:
                        break
                    m = min(m, x)
                return m
            prom = Hs[i] - max(side_min(lmin), side_min(rmin))
            if prom >= 0.5:
                pk.append([round(float(c[i]), 1), round(float(Hs[i]), 2), round(float(prom), 2)])
    out["H_peaks_prom_ge_0p5"] = pk
    mins, cols = D.lip_clearance(A, Y)
    bad = np.nonzero(mins < 0.0)[0]
    out["lip_clearance_min_m"] = round(float(mins.min()), 3)
    out["lip_clearance_rows_lt0"] = int(len(bad))
    sx = D.section_selfx(A, Y)
    out["section_selfx_rows"] = len(sx)
    out["section_selfx_c"] = [round(float(c[r]), 1) for r in sorted(sx)][:12]
    te = D.top_excess(A, Y)
    body = H > 3.0
    out["top_excess_max_m"] = round(float(te[body].max()), 3)
    out["top_col_argmax_range"] = [int(np.argmax(Y[body], 1).min()), int(np.argmax(Y[body], 1).max())]
    cr = Y[:, 314] / np.maximum(H, 1e-6)
    out["corner314_over_H_min"] = round(float(cr[body].min()), 3)
    amin = 200 + np.argmin(A[:, 200:394], 1)
    out["corner_vs_rearmost_cols_max"] = int(np.abs(amin - 314)[body].max())
    out["edge_rows_absY_max"] = [round(float(np.abs(Y[0]).max()), 3), round(float(np.abs(Y[-1]).max()), 3),
                                 round(float(np.abs(Y[:, 0]).max()), 3), round(float(np.abs(Y[:, -1]).max()), 3)]
    import kh_fitA as KF
    b = KF.bump4(c, A, Y)
    out["bump4_d1_p99_max"] = [round(float(np.percentile(b["d1"], 99)), 3), round(float(b["d1"].max()), 3)]
    out["bump4_d2_p99_max"] = [round(float(np.percentile(b["d2"], 99)), 3), round(float(b["d2"].max()), 3)]
    return out


def load(spec):
    if spec.endswith(".json"):
        d = D.Design.load(spec)
        c, A, Y, P = D.build(d)
        return c, A, Y
    z = np.load(spec)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def quick(spec, full_bulge=False, overlay=None):
    t0 = time.time()
    c, A, Y = load(spec)
    r = {"gate": official_gate(c, A, Y, overlay), "gate_lf": lf_gate(c, A, Y)}
    r["gate_pass_lf"] = bool(all(r["gate"][k]["max"] <= 4 for k in ("78", "130", "131")) and r["gate_lf"]["132"]["max"] <= 4
                             and r["gate_lf"]["72"]["p95"] <= 4)
    r["shape"] = shape_checks(c, A, Y)
    r["bulge6"] = bulge6(c, A, Y, 2 if full_bulge else 4, 3 if full_bulge else 6)
    r["seconds"] = round(time.time() - t0, 1)
    return r


if __name__ == "__main__":
    fb = "--full-bulge" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--"):
            continue
        lab, spec = a.split("=", 1)
        print(lab, json.dumps(quick(spec, fb)), flush=True)
