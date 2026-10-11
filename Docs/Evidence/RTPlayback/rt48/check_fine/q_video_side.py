# -*- coding: utf-8 -*-
"""Side view (rtp_14 / rtp_18 / rtp_19), fine (upper) panel: water fill vs own fill of the fine curve at the same time.
Excludes drawn annotations: the dashed still-water line (Y=0 +-3 px), the ruler (lower left), the boat/seat labels (x 545-585 m),
the 'still water' label (upper right). Reports wrong pixels and their distance to the own curve outline."""
import json, os, subprocess, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import q_lib as Q
EVID = Q.ROOT + "/Docs/Evidence/RTPlayback"
OUTV = Q.OUT + "/video"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
man = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
pairs = np.fromfile(Q.DATA + "/fine/pairs.bin", dtype="<f4").reshape(570, 2, 8192, 2).astype(np.float64)
loops = np.fromfile(Q.DATA + "/fine/loops.bin", dtype="<f4").reshape(-1, 2).astype(np.float64)
loops_idx = {r["frame"]: r["loops"] for r in man["loops_index"]}
interp = [p["interp"] for p in man["pairs"]]
T0 = 138.25
S_PX = 1840 / 150.0
PX0, PY0, PH = 40, 196, int(round(24 * S_PX))

def state(t):
    fr = (t - T0) * 24.0
    p = int(math.floor(fr + 1e-9))
    if p >= 570: return 569, 1.0, 3889
    a = fr - p
    return (p, a, 3319 + p) if interp[p] else (p, 0.0, 3319 + p)

def loops_of(f, ph):
    out = []
    for st, n, phs, area in loops_idx.get(f, []):
        if phs == ph:
            P = loops[st:st + n].copy(); P[:, 0] += Q.X0B; out.append(P)
    return out

def tp(P):
    return list(zip(((P[:, 0] - 470) * S_PX).tolist(), ((14 - P[:, 1]) * S_PX).tolist()))

def pred_mask(t):
    p, a, f = state(t)
    C = (1 - a) * pairs[p, 0] + a * pairs[p, 1]; C = C.copy(); C[:, 0] += Q.X0B
    im = Image.new("L", (1840, PH), 0); dr = ImageDraw.Draw(im)
    dr.polygon(tp(np.vstack([C, [[C[-1, 0], -60], [C[0, 0], -60]]])), fill=255)
    for L in loops_of(f, -1): dr.polygon(tp(L), fill=255)
    for L in loops_of(f, 1): dr.polygon(tp(L), fill=0)
    return np.asarray(im) > 0, f

def compare(img, t, tag):
    sub = np.asarray(img.convert("RGB")).astype(np.int32)[PY0:PY0 + PH, PX0:PX0 + 1840]
    water = (np.abs(sub - np.array([28, 78, 96])).sum(2) < 60) | (np.abs(sub - np.array([8, 32, 42])).sum(2) < 50)
    sky = np.abs(sub - np.array([214, 225, 232])).sum(2) < 45
    pred, f = pred_mask(t)
    edge = pred ^ ndimage.binary_erosion(pred)
    dist = ndimage.distance_transform_edt(~edge) / S_PX
    xs = 470 + (np.arange(1840) + 0.5) / S_PX
    ys = 14 - (np.arange(PH) + 0.5) / S_PX
    X, Y = np.meshgrid(xs, ys)
    excl = (np.abs(Y) < 3 / S_PX) | ((X > 545) & (X < 585)) | ((X < 486) & (Y < 4)) | ((X > 605) & (Y > 0) & (Y < 3))
    wrong = ((water & ~pred) | (sky & pred)) & ~excl
    d = dist[wrong]
    far = wrong & (dist > 0.12)
    locs = np.c_[X[far], Y[far]]
    return dict(tag=tag, t=round(t, 4), frame=f, n_wrong=int(wrong.sum()), n_wrong_beyond_0p12m=int(far.sum()),
                max_dist_m=float(d.max()) if len(d) else 0.0, far_x_range=[float(locs[:, 0].min()), float(locs[:, 0].max())] if len(locs) else None,
                far_y_range=[float(locs[:, 1].min()), float(locs[:, 1].max())] if len(locs) else None,
                n_pred=int(pred.sum()), n_water=int(water.sum()))

rows = []
for fn, t in (("rtp_18_side_fine_coarse_t154.500.png", 154.5), ("rtp_19_side_fine_coarse_t156.000.png", 156.0)):
    rows.append(compare(Image.open(EVID + "/" + fn), t, fn))
for t in (140.0, 150.0, 154.0, 154.5, 155.5, 156.0, 156.5, 157.5, 159.0, 161.0):
    i = int(round((t - T0) * 60)); png = OUTV + "/side_mp4_i%05d.png" % i
    if not os.path.exists(png):
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", EVID + "/rtp_14_side_fine_coarse.mp4", "-vf", "select=eq(n\,%d)" % i, "-vsync", "0", "-frames:v", "1", png], check=True)
    rows.append(compare(Image.open(png), T0 + i / 60.0, "rtp_14 i=%d" % i))
    # also +-1 video frame of the bake (1/24 s) to see that the matching time is the right one
    for dt in (-1 / 24, 1 / 24):
        r = compare(Image.open(png), T0 + i / 60.0 + dt, "rtp_14 i=%d shifted %+.4f s" % (i, dt))
        rows.append(r)
for r in rows: print(r)
json.dump(rows, open(Q.OUT + "/q_video_side.json", "w"), indent=1)
