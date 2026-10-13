# -*- coding: utf-8 -*-
# 確かめの役（2026-10-13）：入口の波（0 を上に切る波で H・頂・速さ）、静かな水面のずれ、2 点法の跳ね返り（計り所の組と k を変えて）、帯の上流の端の平均の水面と体積の直しの積分を並べる。使い方：py -3.10 -B x47_pchk_inlet.py runs/<計算> [t0,t1]
# 読むだけ（書くのは c7 の動画だけ、Unity/Build/FLIP47/videos の中）。
# independent checker: inlet waves, still level, reflection, band-level vs volume-correction integral
import sys, os, json, glob, math
import numpy as np
R = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP47/"
run = sys.argv[1]
rd = R + run
cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))

def load_hf(rd):
    ps = sorted(glob.glob(rd + "/hf_c*.npz"))
    best = {}
    arr = {}
    for p in ps:
        d = np.load(p); f0 = int(os.path.basename(p)[4:8])
        arr[p] = (d["eta"], d["t"], d["frames"]); X = d["x"]
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f not in best or best[f][0] <= f0:
                best[f] = (f0, p, i)
    fr = sorted(best)
    eta = np.stack([arr[best[f][1]][0][best[f][2]] for f in fr])
    t = np.array([arr[best[f][1]][1][best[f][2]] for f in fr])
    return np.array(fr), t, X, eta

fr, t, X, eta = load_hf(rd)
el = np.nanmean(eta, axis=1)
print(run, "frames", fr[0], fr[-1], len(fr), "dt", np.median(np.diff(t)))
# still level at first frames, flat region
flat = (X > 160) & (X < 560)
for i in range(3):
    print("  t %.3f  flat mean eta %.4f  min %.3f max %.3f" % (t[i], np.nanmean(el[i, flat]), np.nanmin(el[i, flat]), np.nanmax(el[i, flat])))
i15 = np.argmin(abs(t - 1.5))
print("  t %.2f flat mean %.4f (x 450-560: %.4f)" % (t[i15], np.nanmean(el[i15, flat]), np.nanmean(el[i15, (X > 450) & (X < 560)])))
# reported offset
off = None
for p in sorted(glob.glob(rd + "/run_c*.json")):
    r = json.load(open(p, encoding="utf8"))
    so = (r.get("info") or {}).get("still_offset_online")
    if so and off is None:
        off = so.get("value"); print("  still_offset_online", so)
off = off or 0.0
e = el - off

def gauge(xg):
    i = np.searchsorted(X, xg) - 1; w = (xg - X[i]) / (X[i + 1] - X[i])
    return (1 - w) * e[:, i] + w * e[:, i + 1]

def zero_up_waves(tt, ee):
    # zero-UP crossing (independent of tool's zero-down), relative to window mean
    m = ee.mean(); q = ee - m
    up = np.where((q[:-1] < 0) & (q[1:] >= 0))[0]
    out = []
    for a, b in zip(up[:-1], up[1:]):
        seg = ee[a + 1:b + 1]
        out.append((tt[a + 1 + np.argmax(seg)], seg.max(), seg.min(), seg.max() - seg.min(), tt[b] - tt[a]))
    return out, m

t0, t1 = [float(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else (66.0, float(t[-1]))
m = (t >= t0) & (t <= t1)
sf = cfg["sf"]
print("  input SF H %.2f c %.3f eta_c %.3f; window %.0f-%.0f" % (sf["H"], sf["c"], sf.get("eta_crest", float("nan")), t0, t1))
crest_t = {}
for xg in (450, 480, 510, 540, 560):
    w, mean = zero_up_waves(t[m], gauge(xg)[m])
    H = np.array([v[3] for v in w]); C = np.array([v[1] for v in w]); Tz = np.array([v[4] for v in w])
    crest_t[xg] = np.array([v[0] for v in w])
    print("  x %d n %d H mean %.2f (min %.2f max %.2f, CV %.3f)  crest mean %.2f (from local mean %.2f)  local mean %.2f  T %.2f+-%.2f" % (
        xg, len(H), H.mean(), H.min(), H.max(), H.std() / H.mean(), C.mean(), C.mean() - mean, mean, Tz.mean(), Tz.std()))
    print("     H per wave:", np.round(H, 2).tolist())
# speed from 450 -> 560
sp = []
for tc in crest_t[450]:
    j = np.argmin(abs(crest_t[560] - (tc + 110 / sf["c"])))
    lag = crest_t[560][j] - tc
    if 5 < lag < 12: sp.append(110 / lag)
print("  speed 450->560: %.3f m/s (n %d, sd %.3f); design H11 c 13.745, input c %.3f" % (np.mean(sp), len(sp), np.std(sp), sf["c"]))
# reflection 2-gauge (first harmonic) with several pairs
T = sf["T"]; om = 2 * math.pi / T
nper = int((t1 - t0) // T); tw0 = t1 - nper * T; mm = (t >= tw0) & (t < t1)
def k_lin(T, h):
    k = om * om / 9.80665
    for _ in range(100): k = om * om / (9.80665 * math.tanh(k * h))
    return k
for kk, nm in ((sf["k"], "kSF"), (k_lin(T, 19.0), "klin")):
    for xa, xb in ((450, 480), (480, 510), (510, 540), (450, 510), (480, 540)):
        ea = gauge(xa)[mm]; eb = gauge(xb)[mm]; tt = t[mm]
        Ba = 2 * np.mean((ea - ea.mean()) * np.exp(-1j * om * tt)); Bb = 2 * np.mean((eb - eb.mean()) * np.exp(-1j * om * tt))
        A = np.array([[np.exp(-1j * kk * xa), np.exp(1j * kk * xa)], [np.exp(-1j * kk * xb), np.exp(1j * kk * xb)]])
        I, Rr = np.linalg.solve(A, np.array([Ba, Bb]))
        print("  refl %s pair %d-%d dx/L %.3f: aI %.3f aR %.3f Kr %.3f" % (nm, xa, xb, (xb - xa) * kk / 2 / math.pi, abs(I), abs(Rr), abs(Rr) / abs(I)))
# band-upstream level vs cumulative volume correction
nT = int(round(T * 24))
def run_mean(a): return np.convolve(a, np.ones(nT) / nT, mode="same")
lv = {}
for (a, b) in ((160, 240), (300, 400), (440, 560)):
    s = (X >= a) & (X <= b)
    lv[(a, b)] = run_mean(np.nanmean(e[:, s], axis=1))
# volume correction d
rows = []
for p in sorted(glob.glob(rd + "/run_c*.json")):
    r = json.load(open(p, encoding="utf8"))
    vc = (r.get("info") or {}).get("volcorr")
    if vc and "rows" in vc and vc.get("mode", 0) != 1:
        rows += [(rr[0], rr[1], rr[2], rr[3], rr[4]) for rr in vc["rows"]]
    elif vc and vc.get("mode") == 1:
        rows += [(rr[0], rr[1], rr[2], None, rr[7]) for rr in vc["rows"]]
if rows:
    rows = sorted({rr[0]: rr for rr in rows}.values())
    rt = np.array([rr[1] for rr in rows]); rd_ = np.array([rr[4] for rr in rows], float)
    cum = np.concatenate([[0], np.cumsum(rd_[:-1] * np.diff(rt))])   # integral of d dt (1/s * s)
    print("  volcorr rows", len(rows), "d mean %.2e, frac at limit %.2f" % (rd_.mean(), np.mean(abs(abs(rd_) - cfg['parms'].get('vol_dmax', 0.002)) < 1e-9)))
    for ts in (30, 60, 84, 100, 120, 140, 160, 175, 182):
        i = np.argmin(abs(t - ts)); j = np.argmin(abs(rt - ts))
        V = rows[j][2]; V0 = rows[j][3]
        print("   t %5.0f  lvl160-240 %+.2f  300-400 %+.2f  440-560 %+.2f | int d dt %+.4f -> x19m %+.2f m | V/V0-1 %s" % (
            ts, lv[(160, 240)][i], lv[(300, 400)][i], lv[(440, 560)][i], cum[j], cum[j] * 19.0,
            ("%+.4f" % (V / V0 - 1)) if (V0 and V) else "-"))
else:
    for ts in (30, 60, 84, 100, 120, 140, 160, 175, 182):
        i = np.argmin(abs(t - ts))
        if i < len(t): print("   t %5.0f  lvl160-240 %+.2f  300-400 %+.2f  440-560 %+.2f (no volcorr)" % (ts, lv[(160, 240)][i], lv[(300, 400)][i], lv[(440, 560)][i]))
