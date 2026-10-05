# -*- coding: utf-8 -*-
"""K*′ 精修 R1：今の動きの生成器（ds28r01e、kstar_dir = 候補のフォルダー）で候補へ動きを当て直せるかの検査（py -3.10、約 4 分）。
評審（Q20H/judge_H1A_fid/jt_retarget.py）と同じ中身：t* が候補をそのまま再現するか、τ −6〜0 s の各こまの断面の自己交差・
行をまたぐ折れ・最高点（こまが破綻して 100 m を超えないか）・外周の高さ。生成器のコードは読むだけ。
usage: py -3.10 kh_R1_retarget.py <label> <kstar_dir> <out.json>
"""
import sys, os, json, time, traceback
import numpy as np
REPO = r"G:\Unity\GreatWave_2026_Fresh"
GW = os.path.join(REPO, "Tools", "GWWaveGen")
for d in ("ds27", "ds28", "ds28r01b", "ds28r01c", "ds28r01d", "ds28r01e"):
    sys.path.insert(0, os.path.join(GW, d))
sys.path.insert(0, GW); sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.dont_write_bytecode = True
import gw_wavegen_v1 as V1
import gw_wavegen as G0
from ds28r01e_model import Generator
key, kdir, outp = sys.argv[1], sys.argv[2], sys.argv[3]


def sanity(X, A, Y):
    R = {"nan": int((~np.isfinite(X)).sum())}
    si = G0.self_intersections(A, Y); R["section_selfx_rows"] = int(sum(1 for k in si if k > 0))
    bad = V1.local_self_intersections(X, win=6); R["local_selfx_vertices"] = len(bad)
    d1 = X[1:, 1:] - X[:-1, :-1]; d2 = X[:-1, 1:] - X[1:, :-1]
    n = np.cross(d1, d2); a = np.linalg.norm(n, axis=-1); n = n / np.maximum(a, 1e-15)[..., None]
    ym = np.maximum.reduce([Y[:-1, :-1], Y[1:, :-1], Y[:-1, 1:], Y[1:, 1:]]); ok = (a > 1e-6) & (ym > 0.3)
    vr = np.degrees(np.arccos(np.clip((n[:-1] * n[1:]).sum(-1), -1, 1)))[ok[:-1] & ok[1:]]
    R["cross_row_p99"] = float(np.percentile(vr, 99)) if len(vr) else None
    R["cross_row_gt30"] = int((vr > 30).sum()); R["cross_row_gt90"] = int((vr > 90).sum()); R["Hmax"] = float(Y.max())
    ring = np.concatenate([Y[0], Y[-1], Y[:, 0], Y[:, -1]]); R["outer_ring_absy_max"] = float(np.abs(ring).max())
    return R


out = {"key": key, "kdir": kdir, "generator": "Tools/GWWaveGen/ds28r01e (read-only)"}
t0 = time.time()
try:
    g = Generator(kstar_dir=kdir)
    out["build_ok"] = True; out["build_s"] = round(time.time() - t0, 1)
    K = g.K
    out["ja_minus_corner"] = [int(v) for v in np.percentile((g.ja - g.jK)[g.has_body], [0, 50, 100])] if hasattr(g, "ja") else None
    fr = {}
    for tau in (-6.0, -3.0, -2.0, -1.0, -0.5, -0.4, -0.25, 0.0):
        try:
            r = g.local(tau, info=True)
            X, A, Y = r[0], r[1], r[2]
            R = sanity(X, A, Y)
            if tau == 0.0:
                Yk = getattr(K, "Y_full", K.Y)
                d = np.hypot(A - K.A, Y - Yk)
                R["tstar_vs_cand_max_m"] = float(d.max()); R["tstar_vs_cand_p99_m"] = float(np.percentile(d, 99))
            fr["%g" % tau] = R
        except Exception as ex:
            fr["%g" % tau] = {"error": repr(ex), "trace": traceback.format_exc()[-1200:]}
        print(key, tau, json.dumps(fr["%g" % tau], default=float)[:400], flush=True)
    out["frames"] = fr
    out["Hmax_all_frames"] = max(v.get("Hmax", 0) for v in fr.values() if isinstance(v, dict))
except Exception as ex:
    out["build_ok"] = False; out["error"] = repr(ex); out["trace"] = traceback.format_exc()[-3000:]; print(out["trace"])
out["seconds"] = round(time.time() - t0, 1)
json.dump(out, open(outp, "w", encoding="utf-8"), indent=1, default=float, ensure_ascii=False)
print("DONE", key, out.get("build_ok"), out["seconds"])
