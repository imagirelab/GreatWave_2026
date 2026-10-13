# -*- coding: utf-8 -*-
# 確かめの役（2026-10-13）：数えた崩れが本当に巻いたか（記録の格子のまま、底につながる水の下に大気につながる空気がある列の連なり）。scan で数えられていない巻きも探す。使い方：py -3.10 -B x47_pchk_overturn.py runs/<計算> events | scan <x0> <x1>
# 読むだけ（書くのは c7 の動画だけ、Unity/Build/FLIP47/videos の中）。
# independent checker: does each counted breaking event really overturn?  (native 0.5 m record grid, main layer sdf)
# Also scans all frames for overhangs in the slope zone to find overturning that was NOT counted.
import sys, os, json, glob
import numpy as np
from scipy import ndimage as ndi
B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP47/"
run = sys.argv[1]
rd = B + run
name = os.path.basename(run)
cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
ana = json.load(open(B + "runs/PERIODIC_compare/periodic_ana_%s.json" % name, encoding="utf8"))
off = float(ana["still_offset_m"])
bed = np.array(cfg["bed"], float)

# frame -> (file, index), later launch wins
best = {}; meta = None
for p in glob.glob(rd + "/sec_c*_b*.npz"):
    f0 = int(os.path.basename(p).split("_c")[1].split("_")[0])
    d = np.load(p)
    m = json.loads(str(d["meta"]))
    if m["dy"] != 0.5 or m["ny"] != 78 and m["ny"] != int(m.get("ny", 0)):
        pass
    for i, f in enumerate(d["frames"]):
        f = int(f)
        if f not in best or best[f][0] <= f0:
            best[f] = (f0, p, i, m["y0"], m["ny"], m["x0"], m["dx"])
ys_by = {}
cache = {}
def get(f):
    f0, p, i, y0, ny, x0, dx = best[f]
    if p not in cache:
        cache.clear(); cache[p] = np.load(p)["sdf"]
    S = cache[p][i].astype(np.float32)
    ys = y0 + 0.5 * np.arange(S.shape[0]) - off
    xs = x0 + dx * np.arange(S.shape[1])
    return S, xs, ys

def bed_y(x):
    return np.interp(x, bed[:, 0], -bed[:, 1])

def overhang(S, xs, ys, xa, xb):
    """main water body (connected to the bed); columns where main water has air below it and water further below."""
    by = bed_y(xs)
    W = (S < 0) | (ys[:, None] < by[None, :] + 0.25)
    lab, n = ndi.label(W)
    main = lab == lab[0, len(xs) // 2] if lab[0, len(xs) // 2] > 0 else W
    # air connected to the top of the domain (atmosphere) vs enclosed
    A = ~main
    alab, an = ndi.label(A)
    top_ids = set(np.unique(alab[-1, :])) - {0}
    atm = np.isin(alab, list(top_ids))
    sel = (xs >= xa) & (xs <= xb)
    res = []
    for i in np.where(sel)[0]:
        col = main[:, i]
        if not col.any():
            res.append((0, 0.0, 0)); continue
        jt = np.where(col)[0].max()
        below = col[:jt + 1]
        # air cells below the top water and above the lowest main water run that touches the bed
        air = ~below
        if not air.any():
            res.append((0, 0.0, 0)); continue
        # gap = air cells under the top water whose column has water again below them
        jj = np.where(air)[0]
        jj = jj[jj > np.where(col)[0].min()]
        gap = len(jj)
        open_air = int(atm[jj, i].sum()) if gap else 0
        res.append((open_air if OPEN else gap, ys[jt], open_air))
    g = np.array([r[0] for r in res]); oa = np.array([r[2] for r in res])
    xsel = xs[sel]
    # contiguous columns with gap >= 2 cells (1 m)
    ov = g >= 2
    lab1, n1 = ndi.label(ov)
    best_len = 0.0; best_gap = 0; best_x = None; best_open = 0
    for k in range(1, n1 + 1):
        idx = np.where(lab1 == k)[0]
        L = len(idx) * 0.5
        if L > best_len:
            best_len = L; best_gap = int(g[idx].max()); best_x = float(xsel[idx].mean()); best_open = int(oa[idx].max())
    return best_len, best_gap * 0.5, best_x, best_open

mode = sys.argv[2] if len(sys.argv) > 2 else "events"
OPEN = True
if mode == "events":
    print(name, "off", off)
    for e in ana["events"]:
        on = e.get("on_frame"); xb = e.get("x_b")
        if on is None:
            print(" k", e["k"], "no onset"); continue
        td = (e.get("touchdown") or {}).get("frame"); b3 = (e.get("best3") or {}).get("frame")
        bestL = (0, 0, None, None, 0)
        rows = []
        for f in range(on, min(on + 4 * 24, max(best)) + 1, 2):
            if f not in best: continue
            S, xs, ys = get(f)
            L, gp, x, op = overhang(S, xs, ys, xb - 30, xb + 70)
            rows.append((f, L, gp, x, op))
            if L > bestL[0]: bestL = (L, gp, x, f, op)
        # first frame with overhang >= 2 m
        f2 = next((r[0] for r in rows if r[1] >= 2.0), None)
        Lb3 = None
        if b3 in best:
            S, xs, ys = get(b3); Lb3 = overhang(S, xs, ys, xb - 30, xb + 70)
        OPEN = False
        cav = 0.0; cavf = None
        for f in range(on, min(on + 6 * 24, max(best)) + 1, 2):
            if f not in best: continue
            S, xs, ys = get(f)
            by = bed_y(xs); W = (S < 0) | (ys[:, None] < by[None, :] + 0.25)
            A = ~W; al, an = ndi.label(A)
            topi = set(np.unique(al[-1, :])) - {0}
            sel = (xs >= xb - 30) & (xs <= xb + 70)
            for lb in range(1, an + 1):
                if lb in topi: continue
                m = al == lb
                if not (m & sel[None, :]).any(): continue
                a = m.sum() * 0.25
                if a > cav: cav = a; cavf = f
        OPEN = True
        print("   closed air pocket max area %.1f m2 (frame %s)" % (cav, cavf))
        print(" k%2d on f%d t%.2f x%.1f h_b %.1f eta %.2f | best3 f%s td f%s | max overhang %.1f m gap %.1f m at f%s x %s (open-air cells %d) | first >=2m f%s | at best3: L %.1f gap %.1f" % (
            e["k"], on, e["t_onset"], xb, e["h_b"], e["eta_c_onset"], b3, td, bestL[0], bestL[1], bestL[3], ("%.1f" % bestL[2]) if bestL[2] else "-", bestL[4], f2,
            (Lb3[0] if Lb3 else -1), (Lb3[1] if Lb3 else -1)))
else:
    # scan all frames for overhangs >= 3 m in the slope/beach zone; cluster in time
    xa, xb = float(sys.argv[3]), float(sys.argv[4])
    hits = []
    for f in sorted(best):
        if f % 2: continue
        S, xs, ys = get(f)
        if S.shape[0] < 60: continue
        L, gp, x, op = overhang(S, xs, ys, xa, xb)
        if L >= 3.0 and op > 0:
            hits.append((f, L, gp, x))
    # cluster
    cl = []
    for h in hits:
        if cl and h[0] - cl[-1][-1][0] <= 12: cl[-1].append(h)
        else: cl.append([h])
    on_frames = [e.get("on_frame") for e in ana["events"]]
    for c in cl:
        f0, f1 = c[0][0], c[-1][0]
        mx = max(c, key=lambda h: h[1])
        near = [k for k, o in zip([e["k"] for e in ana["events"]], on_frames) if o and f0 - 48 <= o <= f1]
        print(" open overhang >=3 m: frames %d-%d (t %.1f-%.1f s) x %.0f->%.0f max L %.1f m gap %.1f m; counted k near: %s" % (
            f0, f1, (f0 - 1) / 24, (f1 - 1) / 24, c[0][3], c[-1][3], mx[1], mx[2], near))
