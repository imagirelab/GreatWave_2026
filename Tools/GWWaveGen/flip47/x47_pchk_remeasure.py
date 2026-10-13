# -*- coding: utf-8 -*-
# 確かめの役（2026-10-13）：崩れ k を記録の生の断面から自分で水の格子を作り直し、STUDY52 measure_mask（変えずに読む）と score3 で測り直す。使い方：py -3.10 -B x47_pchk_remeasure.py runs/<計算> <k,k> [main|0..3]
# 読むだけ（書くのは c7 の動画だけ、Unity/Build/FLIP47/videos の中）。
# independent re-measure of 2 breakers from raw sec records: own mask builder + frozen STUDY52 measure_mask + own score3
import sys, os, json, glob, math
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Unity/Build/STUDY52/tools")
import s52_shape as S52
B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP47/"
run, k_list = sys.argv[1], [int(v) for v in sys.argv[2].split(",")]
layer = sys.argv[3] if len(sys.argv) > 3 else "main"
rd = B + run; name = os.path.basename(run)
cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
ana = json.load(open(B + "runs/PERIODIC_compare/periodic_ana_%s.json" % name, encoding="utf8"))
off = float(ana["still_offset_m"]); bed = np.array(cfg["bed"], float)
best = {}
for p in glob.glob(rd + "/sec_c*_b*.npz"):
    f0 = int(os.path.basename(p).split("_c")[1].split("_")[0])
    d = np.load(p); m = json.loads(str(d["meta"]))
    if m["ny"] != 78: continue
    for i, f in enumerate(d["frames"]):
        f = int(f)
        if f not in best or best[f][0] <= f0: best[f] = (f0, p, i, m)
cache = {}
def get(f):
    f0, p, i, m = best[f]
    if p not in cache:
        cache.clear(); dd = np.load(p); cache[p] = (dd["sdf"], dd["sdfz"] if "sdfz" in dd.files else None)
    S = cache[p][0][i].astype(np.float32) if layer == "main" else cache[p][1][i, int(layer)].astype(np.float32)
    xs = m["x0"] + m["dx"] * np.arange(S.shape[1]); ys = m["y0"] + m["dy"] * np.arange(S.shape[0]) - off
    return S, xs, ys
def bed_y(x): return np.interp(x, bed[:, 0], -bed[:, 1])
# print bands (frozen, design 6.2) and centres from shape_measures.json via g47_targets
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47")
import g47_targets as TG
bands = TG.print_bands(json.load(open("G:/Unity/GreatWave_2026_Fresh/Unity/Build/STUDY52/shape_measures.json", encoding="utf8")))
def score3(m):
    s = 0.0
    for k in ("face_chord_deg_01_05", "front_x01_rel", "hood_area"):
        v = m.get(k); lo, hi = bands[k]["band"]; c = bands[k]["center"]
        if v is None or not np.isfinite(v): return None
        d = 0.0
        if lo is not None and v < lo: d = (lo - v) / c
        if hi is not None and v > hi: d = (v - hi) / c
        s += min(d, 1.0)
    return s
def mask(f, xc_hint):
    S, xs, ys = get(f)
    by = bed_y(xs)
    S = S.copy(); S[ys[:, None] < by[None, :] + 0.25] = -1.0          # bed filled as water (same convention as the tool: half cell)
    W = S < 0
    win = np.abs(xs - xc_hint) <= 60
    jt = np.where((W & win[None, :]).any(1))[0].max()
    xc0 = xs[np.where(W[jt] & win)[0]].mean()
    X = np.arange(xc0 - 105, xc0 + 105, 0.05); Z = np.arange(-12.0, ys[jt] + 1.5, 0.05)
    # bilinear
    fx = (X - xs[0]) / (xs[1] - xs[0]); fz = (Z - ys[0]) / (ys[1] - ys[0])
    ix = np.clip(np.floor(fx).astype(int), 0, len(xs) - 2); wx = np.clip(fx - ix, 0, 1)
    iz = np.clip(np.floor(fz).astype(int), 0, len(ys) - 2); wz = np.clip(fz - iz, 0, 1)
    F = (S[iz][:, ix] * (1 - wx) + S[iz][:, ix + 1] * wx) * (1 - wz)[:, None] + (S[iz + 1][:, ix] * (1 - wx) + S[iz + 1][:, ix + 1] * wx) * wz[:, None]
    M = F < 0
    lab, n = ndi.label(M)
    ids = lab[0][lab[0] > 0]
    if len(ids): M = lab == np.bincount(ids).argmax()
    return M, X, Z
print(name, "layer", layer, "bands:", {k: (bands[k]["band"], round(bands[k]["center"], 3)) for k in ("face_chord_deg_01_05", "front_x01_rel", "hood_area", "gap_max", "lip_thick_mid", "back_angle_07_09_deg", "width07_silhouette") if k in bands})
for k in k_list:
    e = [q for q in ana["events"] if q["k"] == k][0]
    on = e["on_frame"]; td = (e.get("touchdown") or {}).get("frame") or on + 72; b3 = e["best3"]
    xc = b3["xc"]
    rep = dict(frame=b3["frame"], score3=b3["score3"], back=b3.get("back_angle"), width=b3.get("width07"), **(b3.get("ruler") or {}))
    print(" k%d reported closest frame:" % k, {a: (round(v, 3) if isinstance(v, float) else v) for a, v in rep.items()})
    rows = []
    xh = e["x_b"]
    for f in range(on, td + 1):
        if f not in best: continue
        M, X, Z = mask(f, xh if f == on else xh_prev)
        m = S52.measure_mask(M, X, Z, flip_extra=dict(Lc=135.4633))
        xh_prev = m["x_c"]
        s3 = score3(m)
        rows.append((f, s3, m))
    xh_prev = None
    bestr = min([r for r in rows if r[1] is not None], key=lambda r: (r[1], -(r[2].get("hood_height_m") or 0)))
    for f, s3, m in rows:
        if f in (on, bestr[0], b3["frame"], td) or (f - on) % 6 == 0:
            print("   f%d t%.2f eta_c %.2f xc %.1f score3 %s chord %.1f foot %.3f area %.3f air %.3f lip %.3f back %.1f width %.2f%s" % (
                f, (f - 1) / 24, m["eta_c"], m["x_c"], None if s3 is None else round(s3, 3), m["face_chord_deg_01_05"], m["front_x01_rel"],
                m.get("hood_area") or 0, m.get("gap_max") or float("nan"), m.get("lip_thick_mid") or float("nan"), m["back_angle_07_09_deg"], m["width07_silhouette"],
                "  <= my min" if f == bestr[0] else ("  <= reported" if f == b3["frame"] else "")))
