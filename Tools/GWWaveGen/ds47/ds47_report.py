# -*- coding: utf-8 -*-
"""設計47（導入→接近→形成→保持→余韻の部）：Unity の Play モードの記録（main・variant の ds47_play.json・ds47_frames.csv・コマの JPG・静止画・原画視点の PNG）から、
最小の受入を数え直し（C# の要約の真偽は使わない）、動画・図・metrics.json・run.json を作る（numpy・OpenCV・ffmpeg）。

数え直すもの：
  1. 86：通しの動画（main、1920×1080、30 fps）の黒画面とカットの途切れ。
     黒：コマの輝度の平均 < 16 か、輝度 < 20 の画素が 90 % 以上。
     カット：隣のコマとの差（480×270 の灰色の平均の絶対差 MAD）と、輝度の分布の相関。MAD > 40、または（MAD > 前後 ±15 コマの中央値の 8 倍 かつ MAD > 12 かつ 分布の相関 < 0.6）。
     独立に ffmpeg の blackdetect（d = 0.03 s、pix_th = 0.10）と scdet（threshold = 10）でも数える。
     記録の CSV（90 Hz のフレームごと）から、視点（HMD Camera）の 1 フレームの移動・回転・画角の跳びの最大も出す。
  2. 114：終わりの原画視点（DS27 painting、1920×1080、MSAA 8）で、乗っていた船だけの画素（船あり − 船なし）と、原画の場面の boat_mid だけの画素
     （原画の船あり − 船なし）の重なり（IoU）・輪郭の最大のずれ（px、両向きの Hausdorff）・重心のずれ。C# の頂点の写しの差（vertexPx）も写す。
     設計46 の t* の原画視点（painting_t120_off_ds46clock.png）との画素の差も記録する。
  3. variant：途中で止まった船（速さ ≈ 0 からの引き継ぎ）と、観賞の位置から外れた時の一時停止・再開（止めている間、体験の時刻と船が動かない）。
PC の Unity（Editor の Play、batchmode、EditorApplication.Step で 1 フレーム = 1/90 s）の記録。HMD 実機ではない。
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ds44"))
from ds44_report import Panel, put  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/47/flow"
MAIN = OUT + "/unity/main"
VAR = OUT + "/unity/variant"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
REF46 = REPO + "/Unity/Build/Design/46/clock/unity/tstar/painting_t120_off_ds46clock.png"
T0 = time.time()
PHASE_COL = {"Intro": (200, 230, 200), "Approach": (230, 220, 180), "Formation": (180, 200, 240), "Hold": (170, 170, 240), "Afterglow": (230, 200, 230), "End": (220, 220, 220)}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(p):
    with open(p, encoding="utf-8") as f:
        r = list(csv.DictReader(f))
    return r


def col(rows, k, conv=float):
    return np.array([conv(x[k]) for x in rows])


def quat_to_euler_pitch_roll(qx, qy, qz, qw):
    """船の縦揺れ（船首上げ正）と横揺れ（度）。Unity の回転（左手系）で、局所の +z 船首・+x 右舷。"""
    fx = 2 * (qx * qz + qw * qy)
    fy = 2 * (qy * qz - qw * qx)
    fz = 1 - 2 * (qx * qx + qy * qy)
    rx = 1 - 2 * (qy * qy + qz * qz)
    ry = 2 * (qx * qy + qw * qz)
    rz = 2 * (qx * qz - qw * qy)
    pitch = np.degrees(np.arctan2(fy, np.hypot(fx, fz)))
    roll = np.degrees(np.arctan2(-ry, np.hypot(rx, rz)))
    return pitch, roll


def quat_angle(a, b):
    d = np.abs(np.sum(a * b, axis=1))
    return np.degrees(2 * np.arccos(np.clip(d, 0, 1)))


# ---------------------------------------------------------------- 1. 動画と 86
def make_video():
    frames = sorted(f for f in os.listdir(MAIN + "/frames") if f.endswith(".jpg"))
    mp4 = OUT + "/ds47_flow_30fps.mp4"
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-framerate", "30", "-i", MAIN + "/frames/f_%05d.jpg",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", mp4]
    subprocess.run(cmd, check=True)
    return mp4, len(frames), cmd


def continuity(nframes):
    meanY, dark, mad, hcorr = [], [], [], []
    prev, prevh = None, None
    for i in range(nframes):
        g = cv2.imread(MAIN + "/frames/f_%05d.jpg" % i, cv2.IMREAD_GRAYSCALE)
        s = cv2.resize(g, (480, 270), interpolation=cv2.INTER_AREA).astype(np.float32)
        meanY.append(float(g.mean()))
        dark.append(float((g < 20).mean()))
        h = cv2.calcHist([g], [0], None, [64], [0, 256])
        cv2.normalize(h, h)
        if prev is None:
            mad.append(0.0)
            hcorr.append(1.0)
        else:
            mad.append(float(np.abs(s - prev).mean()))
            hcorr.append(float(cv2.compareHist(prevh, h, cv2.HISTCMP_CORREL)))
        prev, prevh = s, h
    meanY, dark, mad, hcorr = map(np.array, (meanY, dark, mad, hcorr))
    black = np.where((meanY < 16) | (dark >= 0.9))[0]
    cuts = []
    for i in range(1, nframes):
        lo, hi = max(1, i - 15), min(nframes, i + 16)
        nb = np.concatenate([mad[lo:i], mad[i + 1:hi]])
        med = float(np.median(nb)) if nb.size else 0.0
        if mad[i] > 40 or (mad[i] > 8 * max(med, 0.05) and mad[i] > 12 and hcorr[i] < 0.6):
            cuts.append(i)
    return dict(meanY=meanY, dark=dark, mad=mad, hcorr=hcorr, black=black.tolist(), cuts=cuts)


def ffmpeg_detect(mp4):
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", mp4, "-vf", "blackdetect=d=0.03:pix_th=0.10,scdet=threshold=10", "-an", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = r.stderr.splitlines()
    blacks = [l for l in lines if "black_start" in l]
    scd = [l for l in lines if "lavfi.scd.score" in l or "scd.time" in l]
    return dict(cmd=" ".join(cmd), blackIntervals=len(blacks), blackLines=blacks[:10], sceneChanges=len(scd), sceneLines=scd[:10])


# ---------------------------------------------------------------- 2. 114
def masks_114():
    P = MAIN + "/painting/"
    end = cv2.imread(P + "painting_end.png")
    nob = cv2.imread(P + "painting_end_noboat.png")
    ref = cv2.imread(P + "painting_end_refboat.png")
    view = cv2.imread(P + "view_end.png")
    mr = (np.abs(end.astype(np.int16) - nob.astype(np.int16)).max(axis=2) > 8)
    mp = (np.abs(ref.astype(np.int16) - nob.astype(np.int16)).max(axis=2) > 8)
    inter, union = int((mr & mp).sum()), int((mr | mp).sum())
    iou = inter / union if union else float("nan")

    def edge(m):
        m8 = m.astype(np.uint8)
        return (m8 - cv2.erode(m8, np.ones((3, 3), np.uint8))) > 0

    def dmax(a, b):
        if not a.any() or not b.any():
            return float("nan")
        dt = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 5)
        return float(dt[a].max())

    er, ep = edge(mr), edge(mp)
    haus = max(dmax(er, ep), dmax(ep, er))
    cy_r, cx_r = np.argwhere(mr).mean(axis=0)
    cy_p, cx_p = np.argwhere(mp).mean(axis=0)
    diff_end_ref = int((np.abs(end.astype(np.int16) - ref.astype(np.int16)).max(axis=2) > 0).sum())
    diff_view_end = int((np.abs(view.astype(np.int16) - end.astype(np.int16)).max(axis=2) > 0).sum())
    r46 = cv2.imread(REF46)
    d46 = np.abs(end.astype(np.int16) - r46.astype(np.int16)).max(axis=2)
    ys, xs = np.nonzero(mr)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return dict(end=end, ref=ref, view=view, mr=mr, mp=mp, d46=d46, res=dict(
        ridePixels=int(mr.sum()), paintingBoatPixels=int(mp.sum()), iou=iou, hausdorffPx=haus,
        centroidShiftPx=float(np.hypot(cx_r - cx_p, cy_r - cy_p)), rideBboxPx=bbox,
        diffPixelsEndVsRefboat=diff_end_ref, diffPixelsViewEndVsPaintingEnd=diff_view_end,
        diffPixelsVsDs46TStar=int((d46 > 0).sum()), diffPixelsVsDs46TStarOver8=int((d46 > 8).sum()), maxAbsDiffVsDs46=int(d46.max()),
        ref46=REF46, ref46Sha256=sha(REF46)))


# ---------------------------------------------------------------- 図
def fig_timeline(rows, play, cont, capexp, path):
    img = np.full((1080, 1920, 3), 245, np.uint8)
    e = col(rows, "exp")
    ph = [r["phase"] for r in rows]
    x = col(rows, "boat_x"); z = col(rows, "boat_z"); y = col(rows, "boat_y")
    q = np.stack([col(rows, k) for k in ("boat_qx", "boat_qy", "boat_qz", "boat_qw")], 1)
    pitch, roll = quat_to_euler_pitch_roll(*q.T)
    dt = np.maximum(np.diff(e, prepend=e[0]), 1e-9)
    sp = np.hypot(np.gradient(x), np.gradient(z)) / np.maximum(np.gradient(e), 1e-9)
    sp[~np.isfinite(sp)] = 0
    ho = play["handover"]
    px0, pz0 = 7.025619983673096, -14.941940307617188
    dist = np.hypot(x - px0, z - pz0)
    fov = col(rows, "cam_fov"); agu = col(rows, "afterglow_u")
    xr = (0, float(np.ceil(e.max() / 5) * 5))
    put(img, "DS47 flow timeline (main, Play mode, 90 Hz frames; x = experience seconds)", (20, 34), 0.8, (255, 255, 255))

    def spans(pn):
        cur, s0 = ph[0], e[0]
        for i in range(1, len(ph)):
            if ph[i] != cur:
                pn.span(s0, e[i], PHASE_COL.get(cur, (230, 230, 230)))
                cur, s0 = ph[i], e[i]
        pn.span(s0, e[-1] + 0.5, PHASE_COL.get(cur, (230, 230, 230)))
        for ev in play["events"]:
            pn.vline(ev["clockT"], (120, 120, 120))

    H, gap, top = 150, 42, 80
    pns = []
    specs = [("boat speed m/s (white-bg = horizontal)", (0, 3), "m/s"), ("distance to painting boat position m", (0, 80), "m"),
             ("boat pitch = asin(forward.y) (blue), roll (red) deg; root y m x10 (green)", (-40, 40), "deg"),
             ("camera vfov deg (black), afterglow u x100 (purple)", (0, 110), "deg"),
             ("video frame diff MAD (red) / mean luma /10 (blue); dashed = cut threshold 40", (0, 45), "")]
    for k, (title, yr, yl) in enumerate(specs):
        pn = Panel(img, 90, top + k * (H + gap), 1780, H, xr, yr, title, yl)
        spans(pn)
        pns.append(pn)
    pns[0].line(e, sp, (40, 40, 40), 1)
    pns[1].line(e, dist, (40, 40, 40), 1)
    pns[2].line(e, pitch, (200, 90, 30), 1); pns[2].line(e, roll, (40, 40, 200), 1); pns[2].line(e, y * 10, (40, 160, 40), 1)
    pns[3].line(e, fov, (20, 20, 20), 1); pns[3].line(e, agu * 100, (160, 60, 160), 1)
    pns[4].line(capexp, cont["mad"], (40, 40, 220), 1); pns[4].line(capexp, cont["meanY"] / 10, (200, 120, 40), 1); pns[4].hline(40, (40, 40, 220), False)
    for pn, yt in zip(pns, ([0, 1, 2, 3], [0, 20, 40, 60, 80], [-40, -20, 0, 20, 40], [0, 26, 50, 80, 110], [0, 10, 20, 30, 40])):
        pn.axes(list(range(0, int(xr[1]) + 1, 5)), yt)
    yb = top + 5 * (H + gap) - 10
    xk = 90
    for k2, c2 in PHASE_COL.items():
        cv2.rectangle(img, (xk, yb), (xk + 22, yb + 16), c2, -1)
        cv2.putText(img, k2, (xk + 28, yb + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
        xk += 150
    cv2.putText(img, "grey lines = events (handover %.2f s, formation %.2f s, t* %.2f s, afterglow %.2f s, end %.2f s)" % (ho["s"], ho["waveStart"], ho["waveStart"] + 12, ho["afterglowStart"], ho["end"]),
                (xk + 10, yb + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.imwrite(path, img)


def fig_story(rows, play, path):
    capi = col(rows, "cap", int); e = col(rows, "exp")
    ho = play["handover"]
    ws, ag, en = ho["waveStart"], ho["afterglowStart"], ho["end"]
    picks = [("intro s 3", 3.0), ("intro s 12 (turning)", 12.0), ("handover %.1f" % ho["s"], ho["s"]), ("approach", 0.5 * (ho["s"] + ws)),
             ("formation start", ws), ("wave t 8", ws + 8), ("t* (wave 12)", ws + 12), ("hold end", ag - 0.05), ("afterglow u 0.25", ag + 1.5),
             ("afterglow u 0.5", ag + 3.0), ("afterglow u 0.75", ag + 4.5), ("end (painting view)", en)]
    tiles = []
    for lab, t in picks:
        m = np.where(capi >= 0)[0]
        j = m[np.argmin(np.abs(e[m] - t))]
        im = cv2.imread(MAIN + "/frames/f_%05d.jpg" % capi[j])
        im = cv2.resize(im, (640, 360), interpolation=cv2.INTER_AREA)
        put(im, "%s | s %.2f | %s" % (lab, e[j], rows[j]["phase"]), (8, 24), 0.55)
        tiles.append(im)
    g = np.vstack([np.hstack(tiles[i:i + 3]) for i in range(0, 12, 3)])
    g = cv2.resize(g, (1920, 1440))
    cv2.imwrite(path, g)


def fig_114(m, play, path):
    end = m["end"].copy()
    for mask, c in ((m["mp"], (255, 255, 0)), (m["mr"], (0, 0, 255))):
        cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(end, cs, -1, c, 1)
    x0, y0, x1, y1 = m["res"]["rideBboxPx"]
    pad = 30
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(1919, x1 + pad), min(1079, y1 + pad)
    crop = end[y0:y1, x0:x1]
    sc = min(900 / crop.shape[1], 500 / crop.shape[0])
    crop = cv2.resize(crop, (int(crop.shape[1] * sc), int(crop.shape[0] * sc)), interpolation=cv2.INTER_NEAREST)
    img = np.full((1080, 1920, 3), 245, np.uint8)
    small = cv2.resize(end, (960, 540), interpolation=cv2.INTER_AREA)
    img[60:600, 20:980] = small
    img[60:60 + crop.shape[0], 1000:1000 + crop.shape[1]] = crop
    d46 = m["d46"]
    dv = cv2.resize(m["end"], (720, 405), interpolation=cv2.INTER_AREA)
    dv = (dv * 0.45 + 140).astype(np.uint8)
    for yy, xx in np.argwhere(d46 > 0):
        cv2.circle(dv, (int(xx * 720 / 1920), int(yy * 405 / 1080)), 7, (0, 0, 255), 2)
    img[620:620 + 405, 20:20 + 720] = dv
    r = m["res"]; v = play["vertexPx"]; pv = play["poseVsPaintingJson"]
    put(img, "114: painting view at the end of the afterglow (DS27 painting, 1920x1080, MSAA 8). red = ridden boat outline, cyan = painting-scene boat_mid (drawn first; identical)", (20, 30), 0.55)
    lines = ["ridden root vs painting pose: %.2e m, %.3f deg" % (pv["posDiffM"], pv["rotDiffDeg"]),
             "same-prefab vertices projected: max %.2e px, p95 %.2e px (%d vertices)" % (v["maxPx"], v["p95Px"], v["vertices"]),
             "mask IoU %.4f, Hausdorff %.2f px, centroid %.3f px" % (r["iou"], r["hausdorffPx"], r["centroidShiftPx"]),
             "pixels differing: end vs ref-boat render %d, view camera vs painting camera %d" % (r["diffPixelsEndVsRefboat"], r["diffPixelsViewEndVsPaintingEnd"]),
             "vs DS46 t* painting view: %d px differ (%d over 8/255, max %d)" % (r["diffPixelsVsDs46TStar"], r["diffPixelsVsDs46TStarOver8"], r["maxAbsDiffVsDs46"])]
    for k, s in enumerate(lines):
        put(img, s, (760, 660 + 34 * k), 0.6)
    put(img, "left-bottom: pixels differing from the DS46 t* painting view (red circles, %d px)" % int((d46 > 0).sum()), (20, 1050), 0.5)
    put(img, "zoom x%.1f around the ridden boat" % sc, (1004, 60 + crop.shape[0] + 24), 0.5)
    cv2.imwrite(path, img)


def fig_variant(vrows, vplay, path):
    img = np.full((1080, 1920, 3), 245, np.uint8)
    S = VAR + "/stills/"
    names = [("variant_s10_intro", "s 10: stopped boat (Space 6-10 s, then no input)"), ("variant_intro_leave_paused", "intro: head 0.8 m right -> paused"),
             ("variant_handover", "handover from rest (v0 %.3f m/s)" % vplay["handover"]["trajV0"]), ("variant_hold_leave_paused", "hold: head 0.9 m back -> paused"),
             ("variant_tstar", "t*"), ("variant_end", "end: painting view")]
    for k, (n, lab) in enumerate(names):
        im = cv2.imread(S + n + ".png")
        im = cv2.resize(im, (620, 349), interpolation=cv2.INTER_AREA)
        put(im, lab, (8, 24), 0.55)
        yy, xx = 40 + (k // 3) * 360, 20 + (k % 3) * 630
        img[yy:yy + 349, xx:xx + 620] = im
    e = col(vrows, "exp"); p = col(vrows, "paused", int); fr = col(vrows, "frame")
    x = col(vrows, "boat_x"); z = col(vrows, "boat_z")
    rt = np.cumsum(col(vrows, "dt"))
    pn = Panel(img, 90, 800, 1780, 220, (0, float(rt.max())), (0, float(np.ceil(e.max() / 10) * 10)), "variant: experience seconds (black) vs frame time; paused frames shaded; boat horizontal move per frame x1000 (green)", "s")
    for i in np.where(np.diff(np.r_[0, p, 0]) != 0)[0].reshape(-1, 2) if p.any() else []:
        pn.span(rt[i[0]], rt[min(i[1], len(rt) - 1)], (200, 200, 250))
    pn.line(rt, e, (20, 20, 20), 1)
    mv = np.r_[0, np.hypot(np.diff(x), np.diff(z))] * 1000
    pn.line(rt, np.clip(mv, 0, e.max()), (40, 160, 40), 1)
    pn.axes(list(range(0, int(rt.max()) + 1, 5)), list(range(0, int(np.ceil(e.max() / 10) * 10) + 1, 10)))
    cv2.imwrite(path, img)


# ---------------------------------------------------------------- 本体
def main():
    play = json.load(open(MAIN + "/ds47_play.json", encoding="utf-8"))
    vplay = json.load(open(VAR + "/ds47_play.json", encoding="utf-8"))
    rows = read_csv(MAIN + "/ds47_frames.csv")
    vrows = read_csv(VAR + "/ds47_frames.csv")
    build = json.load(open(OUT + "/unity/ds47_build.json", encoding="utf-8"))

    mp4, nfr, vcmd = make_video()
    cont = continuity(nfr)
    ff = ffmpeg_detect(mp4)
    capi = col(rows, "cap", int); e = col(rows, "exp")
    capexp = np.array([e[np.where(capi == i)[0][0]] for i in range(nfr)])

    # 視点の跳び（90 Hz のフレームごと）
    cp = np.stack([col(rows, k) for k in ("cam_x", "cam_y", "cam_z")], 1)
    cq = np.stack([col(rows, k) for k in ("cam_qx", "cam_qy", "cam_qz", "cam_qw")], 1)
    dpos = np.linalg.norm(np.diff(cp, axis=0), axis=1)
    drot = quat_angle(cq[1:], cq[:-1])
    dfov = np.abs(np.diff(col(rows, "cam_fov")))
    ph = np.array([r["phase"] for r in rows])
    cam = {}
    for name in ("Intro", "Approach", "Formation", "Hold", "Afterglow", "End"):
        idx = np.where(ph[1:] == name)[0]
        if idx.size:
            cam[name] = dict(frames=int(idx.size), maxPosStepM=float(dpos[idx].max()), maxRotStepDeg=float(drot[idx].max()), maxFovStepDeg=float(dfov[idx].max()),
                             maxPosSpeedMps=float((dpos[idx] / np.maximum(np.diff(e)[idx], 1e-9)).max()) if name not in ("End",) else 0.0)
    # 船の姿勢（形成・保持）
    q = np.stack([col(rows, k) for k in ("boat_qx", "boat_qy", "boat_qz", "boat_qw")], 1)
    pitch, roll = quat_to_euler_pitch_roll(*q.T)
    fidx = np.where(np.isin(ph, ["Formation", "Hold"]))[0]
    by = col(rows, "boat_y")
    ex = [r["extra"].split("|") for r in rows]
    ylocal = np.array([float(t[3]) if len(t) > 3 else np.nan for t in ex]); ypaint = np.array([float(t[4]) if len(t) > 4 else np.nan for t in ex])
    boat_form = dict(maxPitchDeg=float(np.abs(pitch[fidx]).max()), maxRollDeg=float(np.abs(roll[fidx]).max()),
                     pitchAtEnd=float(pitch[-1]), rollAtEnd=float(roll[-1]),
                     maxRootYStepMPerFrame=float(np.abs(np.diff(by[fidx])).max()),
                     maxVertSpeedMps=float((np.abs(np.diff(by[fidx])) / np.maximum(np.diff(e[fidx]), 1e-9)).max()),
                     yLocalMinusRootAtFormationStart=float(ylocal[fidx[0]] - by[fidx[0]]) if np.isfinite(ylocal[fidx[0]]) else None)
    m = masks_114()
    r114 = m["res"]

    fig_timeline(rows, play, cont, capexp, OUT + "/fig_ds47_timeline.png")
    fig_story(rows, play, OUT + "/stills_ds47_flow.png")
    fig_114(m, play, OUT + "/fig_ds47_114.png")
    fig_variant(vrows, vplay, OUT + "/fig_ds47_variant.png")

    # variant の数え直し
    ve = col(vrows, "exp"); vp = col(vrows, "paused", int); vx = col(vrows, "boat_x"); vz = col(vrows, "boat_z")
    pz = np.where(vp == 1)[0]
    runs = np.split(pz, np.where(np.diff(pz) != 1)[0] + 1) if pz.size else []
    run_info = []
    for rr in runs:
        a, b = rr[0], rr[-1]
        run_info.append(dict(frames=int(rr.size), exp=float(ve[a]), phase=vrows[a]["phase"], expConstant=bool(np.ptp(ve[a:b + 1]) < 1e-9),
                             boatMoveM=float(np.hypot(np.ptp(vx[a:b + 1]), np.ptp(vz[a:b + 1]))), durationS=float(np.sum(col(vrows[a:b + 1], "dt")))))
    vho = vplay["handover"]
    frozen_exp = bool(run_info) and all(ri["expConstant"] and ri["boatMoveM"] < 1e-6 for ri in run_info)

    ok86 = len(cont["black"]) == 0 and len(cont["cuts"]) == 0 and ff["blackIntervals"] == 0
    ok114 = play["vertexPx"]["maxPx"] <= 4.0 and r114["iou"] >= 0.99
    total = play["handover"]["end"]
    metrics = {
        "schema": "GreatWave.DS47.flow_metrics/1",
        "noteJa": "設計47（導入→接近→形成→保持→余韻）。PC の Unity の Editor の Play モード（batchmode、1 フレーム = 1/90 s）の記録から numpy・OpenCV・ffmpeg で数え直した値。HMD 実機ではない。",
        "acceptance": {
            "86_video_black_and_cut": {"value": {"frames": nfr, "seconds": nfr / 30.0, "blackFrames": len(cont["black"]), "cutFrames": len(cont["cuts"]),
                                                  "maxMad": float(cont["mad"].max()), "maxMadAt": float(capexp[int(np.argmax(cont["mad"]))]), "minHistCorr": float(cont["hcorr"].min()),
                                                  "minMeanLuma": float(cont["meanY"].min()), "ffmpegBlackIntervals": ff["blackIntervals"], "ffmpegSceneChanges": ff["sceneChanges"]},
                                        "threshold": "黒 0・カット 0（86 を使える水準で）", "pass": ok86},
            "114_ridden_boat_at_painting_position": {"value": {"vertexMaxPx": play["vertexPx"]["maxPx"], "vertexP95Px": play["vertexPx"]["p95Px"], "maskIoU": r114["iou"], "hausdorffPx": r114["hausdorffPx"],
                                                               "rootPosDiffM": play["poseVsPaintingJson"]["posDiffM"], "rootRotDiffDeg": play["poseVsPaintingJson"]["rotDiffDeg"]},
                                                     "threshold": "記録（原画視点の ≤4 px に照らす。頂点の写しの最大 ≤ 4 px、IoU ≥ 0.99）", "pass": ok114},
        },
        "flow": {"totalS": total, "targetTotalS": 72.0, "handover": play["handover"], "events": play["events"], "clockEnd": play["clock"], "phaseCameraSteps": cam,
                 "boatFormationHold": boat_form, "boatWater": play["boatWater"], "input": play["input"], "frames90Hz": play["frames"], "captured": play["captured"]},
        "painting_114_images": r114,
        "variant_stop_and_leave": {"handover": vho, "totalS": vho["end"], "pauseRuns": run_info, "pauseCount": vplay["pause"], "leaves": vplay["leaves"],
                                   "expFrozenWhilePaused": frozen_exp, "vertexPx": vplay["vertexPx"], "poseVsPaintingJson": vplay["poseVsPaintingJson"], "events": vplay["events"]},
        "ffmpeg": ff,
        "backlog": {
            "86": "通しの動画で黒画面・カットの途切れ 0（使える水準）。acceptance を参照",
            "114": "記録：原画視点で乗っていた船が原画の位置にある。acceptance を参照",
            "84": "記録のみ：接近でうねりを 1.5 倍へ育てる演出は入れていない（表示のシートが焼いたコマで、待機は t = 0 のコマ）。仕上げ47 へ",
            "85": "記録のみ：乗客の上下動の倍率は設計45 の L0（kV = 0。速い上下を渡さない、遅い上下は渡る）を既定にした",
            "109_110_113": "記録のみ：座席からの見上げ（形成・t*・保持）は stills_ds47_flow.png の座席の視点（PC の HMD Camera、頭の向きは座席の正面のまま）。頭を上げた追跡は HMD の保留",
        },
        "regression": {"paintingView": "原画視点の場面（DS41_Boats・DS46_Clock・DS39_Paper）は変えていない（ds47_build.json の protectedUnchanged）。終わりの原画視点と設計46 の t* の原画視点の画素の差は painting_114_images",
                       "build": {"protectedUnchanged": build["protectedUnchanged"], "changed": build["changed"]}},
        "seconds": time.time() - T0,
    }
    with open(OUT + "/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1, default=float)
    ins = [MAIN + "/ds47_play.json", MAIN + "/ds47_frames.csv", VAR + "/ds47_play.json", VAR + "/ds47_frames.csv", OUT + "/unity/ds47_build.json", REF46,
           REPO + "/Unity/Assets/GreatWave/Design47/Data/ds47_flow.json", REPO + "/Unity/Assets/GreatWave/Design47/Scripts/DS47Flow.cs",
           REPO + "/Unity/Assets/GreatWave/Design47/Scripts/DS47Recorder.cs", REPO + "/Unity/Assets/GreatWave/Design47/Editor/DS47FlowBuild.cs",
           REPO + "/Unity/Assets/GreatWave/Design47/Editor/DS47FlowPlay.cs", REPO + "/Unity/Assets/GreatWave/Design47/Scenes/DS47_Flow.unity",
           MAIN + "/painting/painting_end.png", MAIN + "/painting/painting_end_noboat.png", MAIN + "/painting/painting_end_refboat.png", MAIN + "/painting/view_end.png"]
    outs = [mp4, OUT + "/fig_ds47_timeline.png", OUT + "/stills_ds47_flow.png", OUT + "/fig_ds47_114.png", OUT + "/fig_ds47_variant.png", OUT + "/metrics.json"]
    ffv = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    run = {"schema": "GreatWave.DS47.flow_run/1", "python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__, "ffmpeg": ffv,
           "unity": play["unity"], "device": play["device"], "videoCmd": " ".join(vcmd),
           "unityCmds": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds47/run_ds47_unity.ps1 -Method GreatWave.Design47.EditorTools.DS47FlowPlay.BuildScene -Log build5",
                         "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds47/run_ds47_unity.ps1 -NoQuit -Method GreatWave.Design47.EditorTools.DS47FlowPlay.Run -Log main5 -Extra \"-ds47Script main\"",
                         "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds47/run_ds47_unity.ps1 -NoQuit -Method GreatWave.Design47.EditorTools.DS47FlowPlay.Run -Log variant8 -Extra \"-ds47Script variant\"",
                         "py -3.10 Tools/GWWaveGen/ds47/ds47_report.py"],
           "inputs": {os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in ins if os.path.exists(p)},
           "outputs": {os.path.relpath(p, REPO).replace("\\", "/"): {"sha256": sha(p), "bytes": os.path.getsize(p)} for p in outs if os.path.exists(p)},
           "iterationsJa": ["build1・build2：C# の書き間違い（Key の名前の衝突・置換の誤り）で compile できず、直した",
                            "main1：Play の batchmode で EditorApplication.Step の 1 フレームが 1/90 s（固定の時間刻み）になり、3330 フレームで体験の 37 s までしか進まず引き継ぎに届かなかったので打ち切り、フレームの時間の和で 1/30 s ごとに描く形に替えた",
                            "variant1〜2：状態の記録の文字列の誤りで compile できず／50 回待つ進め方が遅いので打ち切り、止めた状態で毎回 Step する形に替えた",
                            "variant3・main2・variant4：通った。形成の始まりで物理の船と時計の姿勢の高さの差 2.13 m（原画の置き方の高さへ 3 s で持ち上がる）を見つけ、高さもその場の水から原画の置き方へ移す形に替えた。出発点で船が 1.2 m 落ちるのを見つけた",
                            "dbg1〜2：Editor で出発点の水面を読み、−0.936 m と確かめた。Play の Start では再生器が一時 τ = 0（t*）にあり、その水（≈ 0）を読んでいた → 場面を作る時に τ(0) の水面を読んで startWaterY に入れる形に替えた（build4）",
                            "main3・variant5：通った。余韻の終わりの HMD Camera の画が原画視点の描画と 100,944 画素違う（線の縁）のを見つけ、HDR の違い（HMD Camera 1、DS27 painting 0）と分かったので、HMD Camera の描き方を原画視点のカメラにそろえた（build5）",
                            "main4：形成の始まりのつなぎ目で 1 フレーム水平に止まるのを直すため、実行中にコードを変えたので打ち切った",
                            "main5・variant7：最終のコード。ただし打ち切った main4 の外側の命令が残っていて、variant6 が variant7 の後に同じ出力の場所へ重ねて走った（同じコード）ので、variant だけを variant8 として一つで走らせ直した",
                            "受入の数値は main5 と variant8 の記録から数えた"],
           "seconds": time.time() - T0}
    with open(OUT + "/run.json", "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print(json.dumps(metrics["acceptance"], ensure_ascii=True, indent=1, default=float))
    print("cam", json.dumps(cam, indent=0))
    print("boat", boat_form)
    print("variant runs", run_info, "frozen", frozen_exp)
    print("seconds", time.time() - T0)


if __name__ == "__main__":
    main()
