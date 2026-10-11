# -*- coding: utf-8 -*-
"""Misc independent numbers for the fine source: interpolated-frame share (own playback rule), x-end taper visibility from the seats
(own line-of-sight code on the baked frame curves), coarse vs fine pitch rate, evidence copies vs build files."""
import json, math, hashlib, os
import numpy as np
import q_lib as Q
T0 = 138.25
res = {}
HULL = np.array([-6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0])

def load(src):
    man = json.load(open(Q.DATA + "/%s/manifest.json" % src, encoding="utf8"))
    pairs = np.fromfile(Q.DATA + "/%s/pairs.bin" % src, dtype="<f4").reshape(570, 2, 8192, 2).astype(np.float64)
    return man, pairs

def top_at(C, xq):
    X = C[:, 0]; Y = C[:, 1]; out = np.full(len(xq), np.nan)
    for n, x in enumerate(xq):
        s = ((X[:-1] - x) * (X[1:] - x) <= 0) & (X[:-1] != X[1:]); i = np.where(s)[0]
        if len(i): out[n] = (Y[i] + (Y[i + 1] - Y[i]) * (x - X[i]) / (X[i + 1] - X[i])).max()
    return out

def frame_curve(pairs, f):
    C = (pairs[f - 3319, 0] if f < 3889 else pairs[569, 1]).copy(); C[:, 0] += Q.X0B; return C

for src in ("fine", "coarse"):
    man, pairs = load(src)
    interp = [p["interp"] for p in man["pairs"]]
    def st(t):
        p = int(math.floor((t - T0) * 24 + 1e-9))
        return p < 570 and interp[p]
    r = {}
    for seat in ("556", "574"):
        end = man["boat"][seat]["clip_end_t"]
        for hz in (60, 90):
            n = int(round((end - T0) * hz)) + 1
            ts = T0 + np.arange(n) / hz
            k = np.array([st(t) for t in ts])
            bk = ts < man["events"]["K_t"] - 1e-9
            r["seat%s_%dhz" % (seat, hz)] = dict(n=n, interp=int(k.sum()), share=float(k.mean()), before_K_n=int(bk.sum()), before_K_interp=int(k[bk].sum()))
    res["share_" + src] = r
    # boat table and rates (own), to clip end
    for seat in (556.0, 574.0):
        end_f = man["boat"][str(int(seat))]["clip_end_frame"]
        tb = []
        for f in range(3319, end_f + 1):
            h = top_at(frame_curve(pairs, f), seat + HULL)
            tb.append((h.mean(), math.degrees(math.atan(np.polyfit(HULL, h, 1)[0]))))
        tb = np.array(tb)
        res.setdefault("boat_" + src, {})[str(int(seat))] = dict(heave=[float(tb[:, 0].min()), float(tb[:, 0].max())], pitch=[float(tb[:, 1].min()), float(tb[:, 1].max())],
                                                               pitch_rate_max=float(np.abs(np.diff(tb[:, 1])).max() * 24), heave_rate_max=float(np.abs(np.diff(tb[:, 0])).max() * 24))
        # taper visibility (own): eye = heave + 1.2 above the seat; sight lines along x in both directions over the tapered surface
        if True:
            vis_back = 0; vis_front = 0; dmax_back = 0.0; dmax_front = 0.0
            for j, f in enumerate(range(3319, end_f + 1)):
                C = frame_curve(pairs, f)
                P = Q.densify(C, 0.25)
                w = np.ones(len(P)); x = P[:, 0]
                m = (x >= 100) & (x < 200); w[m] = 0.5 - 0.5 * np.cos(np.pi * (x[m] - 100) / 100)
                m = (x > 825) & (x <= 925); w[m] = 0.5 - 0.5 * np.cos(np.pi * (925 - x[m]) / 100)
                yd = P[:, 1] * w; eye = tb[j, 0] + 1.2
                for side in ("front", "back"):
                    sel = x < seat - 0.5 if side == "front" else x > seat + 0.5
                    xs, ys, yt = x[sel], yd[sel], P[sel, 1]
                    o = np.argsort(np.abs(xs - seat)); xs, ys, yt = xs[o], ys[o], yt[o]
                    el = np.arctan2(ys - eye, np.abs(xs - seat))
                    prev = np.maximum.accumulate(np.r_[-np.inf, el[:-1]])
                    v = (el > prev) & ((xs < 200) | (xs > 825))
                    if v.any():
                        if side == "back": vis_back += 1; dmax_back = max(dmax_back, float(np.abs(ys[v] - yt[v]).max()))
                        else: vis_front += 1; dmax_front = max(dmax_front, float(np.abs(ys[v] - yt[v]).max()))
            res["boat_" + src][str(int(seat))].update(n_frames=int(end_f - 3319 + 1), taper_back_visible_frames=vis_back, taper_back_max_dy=dmax_back,
                                                       taper_front_visible_frames=vis_front, taper_front_max_dy=dmax_front)
    print(src, json.dumps(res["share_" + src]), json.dumps(res["boat_" + src]))

# evidence copies vs build
run = json.load(open(Q.ROOT + "/Docs/Evidence/RTPlayback/run.json", encoding="utf8"))
def sha(fn):
    h = hashlib.sha256()
    with open(fn, "rb") as fp:
        for b in iter(lambda: fp.read(1 << 24), b""): h.update(b)
    return h.hexdigest()
pairs_ev = {"rtp_13_boat556_bow_fine_ref.mp4": "rt48_boat_seat556_bow_fine_ref.mp4", "rtp_14_side_fine_coarse.mp4": "rt48_side_fine_coarse.mp4",
            "rtp_15_outside_endon_coarse.mp4": "rt48_outside_endon_coarse.mp4", "rtp_16_outside_high_coarse.mp4": "rt48_outside_high_coarse.mp4",
            "rtp_17_outside_endon_fine_ref.mp4": "rt48_outside_endon_fine_ref.mp4", "rtp_18_side_fine_coarse_t154.500.png": "side_fine_coarse_t154.500.png",
            "rtp_19_side_fine_coarse_t156.000.png": "side_fine_coarse_t156.000.png"}
ev = {}
for e, b in pairs_ev.items():
    pe = Q.ROOT + "/Docs/Evidence/RTPlayback/" + e
    pb = Q.ROOT + "/Unity/Build/RT48/video/" + b
    if os.path.exists(pe) and os.path.exists(pb):
        ev[e] = sha(pe) == sha(pb)
    else:
        ev[e] = "missing " + ("evidence" if not os.path.exists(pe) else "build")
res["evidence_equals_build"] = ev
print(ev)
json.dump(res, open(Q.OUT + "/q_misc.json", "w"), indent=1)
