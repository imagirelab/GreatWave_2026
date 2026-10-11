# -*- coding: utf-8 -*-
"""Independent look at the fine-source videos against the fine bake at the same times (own projection code).
(1) boat view seat 556 bow (Unity player frames): silhouette row of the wave vs. own projection of the shown curve + own boat pose,
    also with the time shifted by +-1/24 s.
(2) end-on outside view (Unity Editor frames): capture rows' frame/alpha vs own playback rule; top outline of the dark sheet vs the
    projected near-end section (depth 70 m); overlays written for viewing.
(3) side view (Python drawing, mp4 frames and evidence stills): water fill of the fine panel vs own fill of the fine curve.
Usage: py -3.10 q_video.py"""
import json, os, subprocess, math
import numpy as np
from PIL import Image, ImageDraw
import q_lib as Q

BUILD = Q.ROOT + "/Unity/Build/RT48"
EVID = Q.ROOT + "/Docs/Evidence/RTPlayback"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
man = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
pairs = np.fromfile(Q.DATA + "/fine/pairs.bin", dtype="<f4").reshape(570, 2, 8192, 2).astype(np.float64)
loops = np.fromfile(Q.DATA + "/fine/loops.bin", dtype="<f4").reshape(-1, 2).astype(np.float64)
loops_idx = {r["frame"]: r["loops"] for r in man["loops_index"]}
interp = [p["interp"] for p in man["pairs"]]
T0 = 138.25
K = 3745
HULL = np.array([-6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0])
OUTV = Q.OUT + "/video"
os.makedirs(OUTV, exist_ok=True)
res = {}


def state(t):
    """own playback rule: pair p=floor((t-T0)*24); interp -> blend, else A; t>=last -> last B."""
    fr = (t - T0) * 24.0
    p = int(math.floor(fr + 1e-9))
    if p >= 570:
        return 569, 1.0, False, 3889
    p = max(p, 0)
    a = fr - p
    if interp[p]:
        return p, a, True, 3319 + p
    return p, 0.0, False, 3319 + p


def curve_at(t):
    p, a, it, f = state(t)
    C = (1 - a) * pairs[p, 0] + a * pairs[p, 1]
    C = C.copy(); C[:, 0] += Q.X0B
    return C, p, a, it, f


def frame_loops(f, phase=-1):
    out = []
    for st, n, ph, area in loops_idx.get(f, []):
        if ph == phase:
            P = loops[st:st + n].copy(); P[:, 0] += Q.X0B
            out.append(P)
    return out


def top_at(curve, xq):
    X = curve[:, 0]; Y = curve[:, 1]
    out = np.full(len(xq), np.nan)
    for n, x in enumerate(xq):
        s = ((X[:-1] - x) * (X[1:] - x) <= 0) & (X[:-1] != X[1:])
        i = np.where(s)[0]
        if len(i):
            out[n] = (Y[i] + (Y[i + 1] - Y[i]) * (x - X[i]) / (X[i + 1] - X[i])).max()
    return out


def boat_from_curve(C, seat):
    h = top_at(C, seat + HULL)
    return float(h.mean()), float(np.degrees(np.arctan(np.polyfit(HULL, h, 1)[0])))


TAB = {}
for seat in (556.0, 574.0):
    TAB[seat] = np.array([boat_from_curve(np.c_[pairs[min(f - 3319, 569), 0 if f < 3889 else 1][:, 0] + Q.X0B,
                                                 pairs[min(f - 3319, 569), 0 if f < 3889 else 1][:, 1]], seat) for f in range(3319, 3890)])


def boat_pose(t, seat=556.0):
    C, p, a, it, f = curve_at(t)
    if it:
        return boat_from_curve(C, seat)
    fr = (t - T0) * 24.0
    i0 = int(math.floor(fr + 1e-9)); u = fr - i0
    i1 = min(i0 + 1, 570)
    tb = TAB[seat]
    return (1 - u) * tb[i0, 0] + u * tb[i1, 0], (1 - u) * tb[i0, 1] + u * tb[i1, 1]


def taper(X, Y):
    w = np.ones_like(X)
    m = (X >= 100) & (X < 200); w[m] = 0.5 - 0.5 * np.cos(np.pi * (X[m] - 100) / 100)
    m = (X > 825) & (X <= 925); w[m] = 0.5 - 0.5 * np.cos(np.pi * (925 - X[m]) / 100)
    w[(X < 100) | (X > 925)] = 0
    return Y * w


# ---------------- (1) boat view
F60 = 540.0 / math.tan(math.radians(30.0))


def predicted_row(t, seat=556.0):
    C, p, a, it, f = curve_at(t)
    hv, th = boat_pose(t, seat)
    thr = math.radians(th)
    ex = -1.2 * math.sin(thr); ey = hv + 1.2 * math.cos(thr)
    pts = [np.c_[C[:, 0] - seat, taper(C[:, 0], C[:, 1])]]
    for L in frame_loops(f):
        pts.append(np.c_[L[:, 0] - seat, L[:, 1]])
    P = np.concatenate(pts)
    vx = P[:, 0] - ex; vy = P[:, 1] - ey
    depth = vx * (-math.cos(thr)) + vy * (-math.sin(thr))
    hgt = vx * (-math.sin(thr)) + vy * math.cos(thr)
    m = depth > 2.0
    return float(540.0 - F60 * (hgt[m] / depth[m]).max()), hv, th, f, a, it


def detect_row(img, cols=range(1300, 1800, 10)):
    L = img.astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    rows = []
    for c in cols:
        col = L[:, c]
        d = col[3:] - col[:-3]
        j = np.where(d < -15)[0]
        if len(j):
            rows.append(j[0] + 1.5)
    return float(np.median(rows)), float(np.percentile(rows, 90) - np.percentile(rows, 10))


fr_dir = BUILD + "/video/frames_boat_seat556_bow_fine"
idxs = list(range(0, 1131, 30)) + [int(round((t - T0) * 60)) for t in (154.5, 155.0, 155.5, 155.9, 156.0, 156.25, 156.5, 156.75, 157.0)] + [1130]
idxs = sorted(set(idxs))
rows = []
for i in idxs:
    t = T0 + i / 60.0
    img = np.asarray(Image.open(fr_dir + "/frame_%05d.png" % i).convert("RGB"))
    det, spread = detect_row(img)
    pr, hv, th, f, a, it = predicted_row(t)
    prm = predicted_row(max(t - 1 / 24, T0))[0]; prp = predicted_row(t + 1 / 24)[0]
    rows.append(dict(i=i, t=round(t, 4), frame=f, alpha=round(a, 3), interp=it, heave=round(hv, 3), pitch=round(th, 3), detected=det, spread=spread,
                     predicted=round(pr, 2), d=round(det - pr, 2), d_minus=round(det - prm, 2), d_plus=round(det - prp, 2)))
arr = np.array([[r["d"], r["d_minus"], r["d_plus"]] for r in rows])
res["boat"] = dict(n=len(rows), max_abs_d=float(np.abs(arr[:, 0]).max()), median_abs_d=float(np.median(np.abs(arr[:, 0]))),
                   median_abs_d_minus=float(np.median(np.abs(arr[:, 1]))), median_abs_d_plus=float(np.median(np.abs(arr[:, 2]))),
                   n_better_than_shifted=int(((np.abs(arr[:, 0]) <= np.abs(arr[:, 1])) & (np.abs(arr[:, 0]) <= np.abs(arr[:, 2]))).sum()),
                   deg_per_px=math.degrees(math.atan(1 / F60)), rows=rows)
print("boat", {k: v for k, v in res["boat"].items() if k != "rows"})
for r in rows:
    if r["t"] >= 154:
        print("  ", r)

# ---------------- (2) end-on outside
cap = json.load(open(BUILD + "/video/frames_outside_fine/endon/capture.json", encoding="utf8"))
F26 = 540.0 / math.tan(math.radians(cap["vfovDeg"] / 2))
camY = cap["camPos"][1]; depth0 = cap["camLookAt"][2] - cap["camPos"][2]  # not used; near end at Z=-20000
D_NEAR = -20000.0 - cap["camPos"][2]
mism = []
for r in cap["rows"]:
    p, a, it, f = state(r["t"])
    if f != r["frame"] or abs(a - r["alpha"]) > 1e-6 or it != r["interp"]:
        mism.append([r["i"], r["frame"], f, r["alpha"], a])
res["endon_state_mismatch"] = dict(n_rows=len(cap["rows"]), n_mismatch=len(mism), first=mism[:5])
print("endon state mismatches", len(mism), mism[:3])
ed = []
for t in (150.0, 153.0, 154.5, 155.0, 155.5, 156.0, 156.5, 157.0):
    i = int(round((t - T0) * 60)); r = cap["rows"][i]
    C, p, a, it, f = curve_at(r["t"])
    X = C[:, 0] - 556.0
    col = 960 + F26 * (X - r["camX"]) / D_NEAR
    row = 540 - F26 * (C[:, 1] - camY) / D_NEAR
    img = Image.open(BUILD + "/video/frames_outside_fine/endon/frame_%05d.png" % i).convert("RGB")
    A = np.asarray(img).astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    # top outline per column where the near section top is above the camera height (+0.5 m)
    cols = np.arange(0, 1920, 4)
    xq = r["camX"] + (cols - 960) * D_NEAR / F26 + 556.0
    ytop = top_at(C, xq)
    ok = np.isfinite(ytop) & (ytop > camY + 0.5)
    dd = []
    for c, yt in zip(cols[ok], ytop[ok]):
        pr = 540 - F26 * (yt - camY) / D_NEAR
        colL = A[:, c]
        j = np.where(colL < colL[5] - 40)[0]
        if len(j):
            dd.append(j[0] - pr)
    dd = np.array(dd)
    ed.append(dict(t=t, i=i, frame=f, n_cols=int(len(dd)), median_px=float(np.median(dd)) if len(dd) else None,
                   p95_abs_px=float(np.percentile(np.abs(dd), 95)) if len(dd) else None, px_per_m=F26 / D_NEAR))
    # overlay
    dr = ImageDraw.Draw(img)
    pts = [(float(cx), float(cy)) for cx, cy in zip(col, row) if -50 < cx < 1970 and -50 < cy < 1130]
    if len(pts) > 1:
        dr.line(pts, fill=(255, 0, 0), width=1)
    for L in frame_loops(f, -1) + frame_loops(f, 1):
        lc = 960 + F26 * (L[:, 0] - 556.0 - r["camX"]) / D_NEAR; lr = 540 - F26 * (L[:, 1] - camY) / D_NEAR
        dr.line(list(zip(lc.tolist(), lr.tolist())), fill=(255, 200, 0), width=1)
    img.save(OUTV + "/endon_overlay_t%.3f.png" % t)
res["endon_outline"] = ed
print("endon outline", ed)

# ---------------- (3) side view, fine (upper) panel
S_PX = 1840 / 150.0
PX0, PY0, PH = 40, 196, int(round(24 * S_PX))


def water_mask_pred(t):
    C, p, a, it, f = curve_at(t)
    W, H = 1840, PH
    im = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(im)
    def tp(P):
        return list(zip(((P[:, 0] - 470) * S_PX).tolist(), ((14 - P[:, 1]) * S_PX).tolist()))
    poly = np.vstack([C, [[C[-1, 0], -60], [C[0, 0], -60]]])
    dr.polygon(tp(poly), fill=255)
    for L in frame_loops(f, -1):
        dr.polygon(tp(L), fill=255)
    for L in frame_loops(f, 1):
        dr.polygon(tp(L), fill=0)
    return np.asarray(im) > 0, C


def side_compare(img, t, tag):
    sub = np.asarray(img.convert("RGB")).astype(np.int32)[PY0:PY0 + PH, PX0:PX0 + 1840]
    water = (np.abs(sub - np.array([28, 78, 96])).sum(2) < 60) | (np.abs(sub - np.array([8, 32, 42])).sum(2) < 50)
    sky = np.abs(sub - np.array([214, 225, 232])).sum(2) < 45
    pred, C = water_mask_pred(t)
    from scipy import ndimage
    edge = pred ^ ndimage.binary_erosion(pred)
    dist_edge = ndimage.distance_transform_edt(~edge)
    wrong = (water & ~pred) | (sky & pred)
    # exclude the ruler/boat/labels region: x 540-580 m band (boat, seat labels) and the ruler box at the lower left
    xs = 470 + (np.arange(1840) + 0.5) / S_PX
    excl = np.zeros_like(wrong); excl[:, (xs > 545) & (xs < 585)] = True; excl[PH - 140:, :200] = True
    w2 = wrong & ~excl
    dm = dist_edge[w2] / S_PX if w2.any() else np.array([0.0])
    return dict(tag=tag, t=t, n_wrong=int(w2.sum()), max_dist_m=float(dm.max()), n_wrong_far_0p12m=int((dm > 0.12).sum()),
                n_water_px=int(water.sum()), n_pred_px=int(pred.sum()))


sd = []
for fn, t in (("rtp_18_side_fine_coarse_t154.500.png", 154.5), ("rtp_19_side_fine_coarse_t156.000.png", 156.0)):
    sd.append(side_compare(Image.open(EVID + "/" + fn), t, fn))
mp4 = EVID + "/rtp_14_side_fine_coarse.mp4"
for t in (140.0, 150.0, 154.0, 154.5, 155.5, 156.0, 156.5, 157.5, 159.0, 161.0):
    i = int(round((t - T0) * 60))
    png = OUTV + "/side_mp4_i%05d.png" % i
    if not os.path.exists(png):
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", mp4, "-vf", "select=eq(n\\,%d)" % i, "-vsync", "0", "-frames:v", "1", png], check=True)
    sd.append(side_compare(Image.open(png), T0 + i / 60.0, "mp4 i=%d" % i))
res["side_fine_panel"] = sd
for s in sd:
    print("side", s)
json.dump(res, open(Q.OUT + "/q_video.json", "w"), indent=1, default=float)
