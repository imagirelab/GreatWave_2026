# -*- coding: utf-8 -*-
# 確かめの役（2026-10-13）：巻き始めの頂の高さのうち、1〜2 格子の幅のとがりの分（2.5 m・4.5 m の中央値の頂との差）と、とがりを除いた繰り返しの数。使い方：py -3.10 -B x47_pchk_spike.py runs/<計算> <k0,k1> <ka-kb> ...
# 読むだけ（書くのは c7 の動画だけ、Unity/Build/FLIP47/videos の中）。
# crest spikes: raw crest (top of water) vs robust crest (running median over 2.5 m of the top surface) at onset; robust repeatability stats
import sys, os, json, glob, math
import numpy as np
from scipy import ndimage as ndi
B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP47/"
run = sys.argv[1]; kr = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
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
        cache.clear(); cache[p] = np.load(p)["sdf"]
    S = cache[p][i].astype(np.float32)
    xs = m["x0"] + m["dx"] * np.arange(S.shape[1]); ys = m["y0"] + m["dy"] * np.arange(S.shape[0]) - off
    return S, xs, ys
def top(S, ys):
    W = S < 0
    lab, n = ndi.label(W)
    ids = lab[0][lab[0] > 0]
    if len(ids): W = lab == np.bincount(ids).argmax()
    has = W.any(0)
    jt = W.shape[0] - 1 - np.argmax(W[::-1], axis=0)
    # sub-cell: interpolate sdf zero crossing above top cell
    t = np.where(has, ys[jt], np.nan)
    for i in np.where(has)[0]:
        j = jt[i]
        if j + 1 < S.shape[0]:
            a, b = S[j, i], S[j + 1, i]
            if a < 0 <= b: t[i] = ys[j] + (ys[j + 1] - ys[j]) * (-a) / (b - a)
    return t
T = 14.0
rows = []
for e in ana["events"]:
    if e.get("on_frame") is None: continue
    if kr and e["k"] not in kr and not (kr[0] <= e["k"] <= kr[-1]): continue
    f = e["on_frame"]; xb = e["x_b"]
    S, xs, ys = get(f)
    tp = top(S, ys)
    sel = (xs >= xb - 25) & (xs <= xb + 10)
    raw = np.nanmax(tp[sel])
    rob = np.nanmax(ndi.median_filter(np.nan_to_num(tp, nan=-30), size=5)[sel])     # 5 cells = 2.5 m
    rob9 = np.nanmax(ndi.median_filter(np.nan_to_num(tp, nan=-30), size=9)[sel])    # 4.5 m
    # also 0.5 s before onset
    S2, _, _ = get(f - 12); tp2 = top(S2, ys)
    sel2 = (xs >= xb - 35) & (xs <= xb + 5)
    rob_pre = np.nanmax(ndi.median_filter(np.nan_to_num(tp2, nan=-30), size=5)[sel2])
    rows.append((e["k"], f, e["t_onset"], xb, e["h_b"], e["eta_c_onset"], raw, rob, rob9, rob_pre))
    print(" k%2d f%d t%.2f x_b %.1f h_b %.2f | reported eta_c %.2f | my raw top %.2f | robust(2.5 m median) %.2f | robust(4.5 m) %.2f | robust 0.5 s before %.2f | spike %.2f m" % (
        e["k"], f, e["t_onset"], xb, e["h_b"], e["eta_c_onset"], raw, rob, rob9, rob_pre, raw - rob))
def stat(sub, lab):
    k = np.array([r[0] for r in sub], float)
    for j, nm in ((5, "reported eta_c"), (7, "robust eta_c 2.5m"), (8, "robust eta_c 4.5m")):
        v = np.array([r[j] for r in sub])
        p = np.polyfit(k, v, 1)
        print("   %s %s: mean %.2f CV %.3f drift %.3f" % (lab, nm, v.mean(), v.std() / v.mean(), p[0] * (k.max() - k.min()) / v.mean()))
    xb = np.array([r[3] for r in sub]); hb = np.array([r[4] for r in sub]); ton = np.array([r[2] for r in sub])
    ph = ton - k * T
    print("   %s x_b std %.2f m, h_b CV %.3f, phase std/T %.3f, intervals %s" % (lab, xb.std(), hb.std() / hb.mean(), ph.std() / T, np.round(np.diff(ton), 2).tolist()))
if len(sys.argv) > 3:
    for rng in sys.argv[3:]:
        a, b = [int(v) for v in rng.split("-")]
        stat([r for r in rows if a <= r[0] <= b], "k%d-%d" % (a, b))
