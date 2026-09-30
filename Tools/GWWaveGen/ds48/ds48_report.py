# -*- coding: utf-8 -*-
"""設計48（船首の泡・航跡）：Unity の Play モードの記録（ds48_play.json・ds48_frames.csv・ds48_masks.csv・コマの JPG・原画視点の PNG）から、
最小の受入を数え直し（C# の要約の真偽は使わない）、動画・図・metrics.json・run.json を作る（numpy・OpenCV・ffmpeg）。

数え直すもの：
  1. 操作の方向に反応する（受入の 1）：90 Hz のフレームごとの入力・速さ・旋回の角速度と、船首の泡の左右の幅・航跡の腕の左右の幅・中央の帯の半幅。
     右旋回（入力 turn = +1、角速度 > 3°/s）の間は外側の左舷の泡が右舷より広く、左旋回では逆。直進（|角速度| < 1°/s）の間は泡の幅が速さと強く相関し、
     停止（Space）の後に速さが 0.2 m/s を下回ると泡の幅は 0.05 m 未満。
  2. 主役波の上に航跡が出ない（受入の 2）：10 コマ/s の画素の検査（追いかけのカメラと座席の視点、640×360）で、航跡が見えている画素（全部 − 航跡なし）と
     主役波の画素（航跡なし − 航跡なし・主役波なし）の重なりが全部の検査で 0。大波の時刻 2 s（fadeEndWaveS）以後は航跡の画素も 0（形成・保持・余韻・終わり）。
     主役波の画素の検査が働いていること（形成・保持で主役波の画素 > 0）も数える。場所の守りの頂点の数（水面が高い・巻き込み）も写す。
  3. 原画視点の回帰なし：終わりの原画視点（DS27 painting、1920×1080、MSAA 8）が設計47 の painting_end.png と画素で同じ。
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
OUT = REPO + "/Unity/Build/Design/48/wake"
MAIN = OUT + "/unity/main"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
REF47 = REPO + "/Unity/Build/Design/47/flow/unity/main/painting/painting_end.png"
CFG = REPO + "/Unity/Assets/GreatWave/Design48/Data/ds48_wake.json"
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
        return list(csv.DictReader(f))


def col(rows, k, conv=float):
    out = []
    for x in rows:
        v = x[k]
        try:
            out.append(conv(v))
        except ValueError:
            out.append(np.nan)
    return np.array(out)


def spans_of(e, ph):
    res = []
    cur, s0 = ph[0], e[0]
    for i in range(1, len(ph)):
        if ph[i] != cur:
            res.append((cur, s0, e[i]))
            cur, s0 = ph[i], e[i]
    res.append((cur, s0, e[-1] + 0.5))
    return res


def draw_keys(img, x0, y0, thr, turn, stop, handed):
    keys = [("W", (1, 0), thr > 0), ("A", (0, 1), turn < 0), ("S", (1, 1), thr < 0), ("D", (2, 1), turn > 0)]
    for k, (cx, cy), on in keys:
        x, y = x0 + cx * 56, y0 + cy * 56
        cv2.rectangle(img, (x, y), (x + 50, y + 50), (60, 200, 255) if on else (90, 90, 90), -1 if on else 2)
        cv2.putText(img, k, (x + 15, y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20) if on else (200, 200, 200), 2, cv2.LINE_AA)
    x, y = x0 + 3 * 56 + 10, y0 + 56
    cv2.rectangle(img, (x, y), (x + 130, y + 50), (60, 200, 255) if stop else (90, 90, 90), -1 if stop else 2)
    cv2.putText(img, "Space", (x + 22, y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20) if stop else (200, 200, 200), 2, cv2.LINE_AA)
    if handed:
        put(img, "input not read (fixed trajectory, D47)", (x0, y0 + 135), 0.5, (200, 200, 200))


def bar(img, x, y, w, val, vmax, label, color):
    cv2.rectangle(img, (x, y), (x + w, y + 16), (70, 70, 70), 1)
    f = 0.0 if not np.isfinite(val) else max(0.0, min(1.0, val / vmax))
    cv2.rectangle(img, (x + 1, y + 1), (x + 1 + int((w - 2) * f), y + 15), color, -1)
    cv2.putText(img, "%s %.2f" % (label, val if np.isfinite(val) else 0.0), (x + w + 8, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)


def make_video(rows, play, path):
    caprows = [r for r in rows if int(r["cap"]) >= 0]
    ncap = play["captured"]
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1920x720", "-framerate", "30", "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ho = play["handover"]
    for r in caprows:
        i = int(r["cap"])
        if i >= ncap:
            break
        c = cv2.imread(MAIN + "/frames_chase/c_%05d.jpg" % i)
        h = cv2.imread(MAIN + "/frames_hmd/h_%05d.jpg" % i)
        fr = np.zeros((720, 1920, 3), np.uint8)
        fr[:, :1280] = c
        fr[:360, 1280:] = h
        hud = fr[360:, 1280:]
        hud[:] = (32, 32, 32)
        e = float(r["exp"]); wv = float(r["wave"]) if r["wave"] not in ("NaN", "") else float("nan")
        put(fr, "DS48 bow foam + wake | chase view (test camera, not in the experience)", (12, 28), 0.6)
        put(fr, "seat view (HMD Camera, PC)", (1292, 26), 0.55)
        cv2.putText(hud, "s %.2f  %s%s" % (e, r["phase"], ("  wave t %.2f" % wv) if np.isfinite(wv) and wv > -50 else ""), (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
        ex = r["extra"].split("|")
        thr, turn, stop = float(ex[0]), float(ex[1]), ex[2] == "1"
        handed = r["handed_over"] == "1"
        if handed:
            thr, turn, stop = 0.0, 0.0, False
        draw_keys(hud, 14, 44, thr, turn, stop, handed)
        cv2.putText(hud, "speed %.2f m/s   yaw rate %+.1f deg/s" % (float(r["speed"]), float(r["yaw_rate"])), (12, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)
        bar(hud, 12, 214, 260, float(r["bow_port_w"]), 1.6, "bow foam port (L) m", (240, 240, 240))
        bar(hud, 12, 238, 260, float(r["bow_stbd_w"]), 1.6, "bow foam stbd (R) m", (240, 240, 240))
        bar(hud, 12, 262, 260, float(r["arm_port_w"]), 0.5, "wake arm port m", (200, 220, 240))
        bar(hud, 12, 286, 260, float(r["arm_stbd_w"]), 0.5, "wake arm stbd m", (200, 220, 240))
        bar(hud, 12, 310, 260, float(r["gate"]), 1.0, "gate (0 = hidden before wave rises)", (120, 200, 255))
        cv2.putText(hud, "samples %s  visible verts %s  renderer %s" % (r["samples"], r["visible_verts"], "on" if r["renderer_on"] == "1" else "off"), (12, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    p.wait()
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed")


def fig_reaction(rows, play, masks, path):
    img = np.full((1300, 1920, 3), 245, np.uint8)
    e = col(rows, "exp"); ph = [r["phase"] for r in rows]
    ex = [r["extra"].split("|") for r in rows]
    thr = np.array([float(a[0]) for a in ex]); turn = np.array([float(a[1]) for a in ex]); stp = np.array([float(a[2]) for a in ex])
    ho = col(rows, "handed_over")
    thr[ho > 0] = np.nan; turn[ho > 0] = np.nan; stp[ho > 0] = np.nan
    xr = (0, float(np.ceil(e.max() / 5) * 5))
    put(img, "DS48 bow foam / wake reaction to steering (main, Play mode 90 Hz; x = experience s)", (20, 34), 0.8)
    sp = spans_of(e, ph)
    H, gap, top = 150, 40, 70
    specs = [("input (intended keys): throttle W/S (black), turn D=+1 A=-1 (red), stop Space (blue); blank after handover", (-1.2, 1.2)),
             ("speed m/s (black), yaw rate deg/s /5 (red)", (-2.5, 3)),
             ("bow foam width m: port/left (red), starboard/right (green)", (0, 1.7)),
             ("wake arm width m (1.5 s behind): port (red), stbd (green); wash half width m /2 (black)", (0, 0.5)),
             ("gate (black), visible wake vertices /600 (blue); guard-hidden vertices /200 (red)", (0, 1.1)),
             ("pixel check 10/s: wake px /1000 chase (black), hmd (grey); hero px /50000 chase (blue); OVERLAP px (red)", (0, 4))]
    pns = []
    for k, (title, yr) in enumerate(specs):
        pn = Panel(img, 90, top + k * (H + gap), 1780, H, xr, yr, title, "")
        for (pnm, a, b) in sp:
            pn.span(a, b, PHASE_COL.get(pnm, (230, 230, 230)))
        for ev in play["events"]:
            pn.vline(ev["clockT"], (120, 120, 120))
        pns.append(pn)
    pns[0].line(e, thr, (20, 20, 20), 2); pns[0].line(e, turn, (40, 40, 220), 2); pns[0].line(e, stp * 0.9, (220, 120, 40), 2)
    pns[1].line(e, col(rows, "speed"), (20, 20, 20), 2); pns[1].line(e, col(rows, "yaw_rate") / 5, (40, 40, 220), 2); pns[1].hline(0, (120, 120, 120))
    pns[2].line(e, col(rows, "bow_port_w"), (40, 40, 220), 2); pns[2].line(e, col(rows, "bow_stbd_w"), (40, 160, 40), 2)
    pns[3].line(e, col(rows, "arm_port_w"), (40, 40, 220), 2); pns[3].line(e, col(rows, "arm_stbd_w"), (40, 160, 40), 2); pns[3].line(e, col(rows, "wash_hw") / 2, (20, 20, 20), 1)
    pns[4].line(e, col(rows, "gate"), (20, 20, 20), 2); pns[4].line(e, col(rows, "visible_verts") / 600, (200, 120, 40), 1)
    gh = col(rows, "guard_hidden") + col(rows, "overhang_hidden") + col(rows, "outside_hidden")
    pns[4].line(e, gh / 200, (40, 40, 220), 1)
    for cam, c1 in (("chase", (20, 20, 20)), ("hmd", (150, 150, 150))):
        m = [x for x in masks if x["cam"] == cam]
        me = np.array([float(x["exp"]) for x in m])
        pns[5].line(me, np.array([float(x["wake_px"]) for x in m]) / 1000, c1, 1, dots=True)
        if cam == "chase":
            pns[5].line(me, np.array([float(x["hero_px"]) for x in m]) / 50000, (200, 120, 40), 1, dots=True)
        pns[5].line(me, np.array([float(x["overlap_px"]) for x in m]), (40, 40, 220), 2, dots=True)
    for pn, yt in zip(pns, ([-1, 0, 1], [-2, 0, 1, 2, 3], [0, 0.5, 1, 1.5], [0, 0.25, 0.5], [0, 0.5, 1], [0, 1, 2, 3, 4])):
        pn.axes(list(range(0, int(xr[1]) + 1, 5)), yt)
    yb = top + 6 * (H + gap) - 8
    xk = 90
    for k2, c2 in PHASE_COL.items():
        cv2.rectangle(img, (xk, yb), (xk + 22, yb + 16), c2, -1)
        cv2.putText(img, k2, (xk + 28, yb + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
        xk += 150
    cv2.putText(img, "grey lines = events (handover, formation start, a->d, jet, t*, afterglow, settled, end)", (xk + 10, yb + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.imwrite(path, img)


def stills(rows, play, picks, path):
    tiles = []
    for (t, lab) in picks:
        r = min((x for x in rows if int(x["cap"]) >= 0), key=lambda x: abs(float(x["exp"]) - t))
        i = int(r["cap"])
        c = cv2.imread(MAIN + "/frames_chase/c_%05d.jpg" % i)
        c = cv2.resize(c, (640, 360), interpolation=cv2.INTER_AREA)
        put(c, "%s | s %.2f | %s" % (lab, float(r["exp"]), r["phase"]), (8, 24), 0.55)
        put(c, "bow L %.2f R %.2f  yaw %+.1f  v %.2f" % (float(r["bow_port_w"]), float(r["bow_stbd_w"]), float(r["yaw_rate"]), float(r["speed"])), (8, 350), 0.5)
        tiles.append(c)
    while len(tiles) % 3:
        tiles.append(np.full_like(tiles[0], 30))
    img = np.vstack([np.hstack(tiles[k:k + 3]) for k in range(0, len(tiles), 3)])
    cv2.imwrite(path, img)


def seat_look(play, path):
    """座席から見回した画（頭の向きを左舷 −110°・右舷 +110°・後ろ 180°、22° 見下ろす。旋回の間と接近の間）。"""
    rows = []
    for n in ["turn_right_s10.5", "turn_left_s19.5", "approach_h+4"]:
        t = []
        for y in ["-110", "+110", "+180"]:
            im = cv2.imread(MAIN + "/look/%s_yaw%s.png" % (n, y))
            im = cv2.resize(im, (640, 360), interpolation=cv2.INTER_AREA)
            put(im, "seat view %s | head yaw %s deg, pitch -22 deg" % (n, y), (8, 24), 0.5)
            t.append(im)
        rows.append(np.hstack(t))
    cv2.imwrite(path, np.vstack(rows))


def main():
    play = json.load(open(MAIN + "/ds48_play.json", encoding="utf-8"))
    cfg = json.load(open(CFG, encoding="utf-8"))
    build = json.load(open(OUT + "/unity/ds48_build.json", encoding="utf-8"))
    rows = read_csv(MAIN + "/ds48_frames.csv")
    masks = read_csv(MAIN + "/ds48_masks.csv")
    e = col(rows, "exp"); ph = np.array([r["phase"] for r in rows])
    ho = col(rows, "handed_over")
    ex = [r["extra"].split("|") for r in rows]
    tin = np.array([float(a[1]) for a in ex]); sin = np.array([a[2] == "1" for a in ex])
    yr = col(rows, "yaw_rate"); v = col(rows, "speed")
    bp = col(rows, "bow_port_w"); bs = col(rows, "bow_stbd_w"); ap = col(rows, "arm_port_w"); as_ = col(rows, "arm_stbd_w")
    gate = col(rows, "gate"); wave = col(rows, "wave")
    fadeEnd = cfg["gate"]["fadeEndWaveS"]

    # 受入の 1：操作の方向への反応
    right = (ho == 0) & (tin > 0.5) & (yr > 3)
    left = (ho == 0) & (tin < -0.5) & (yr < -3)
    straight = (ho == 0) & (np.abs(yr) < 1) & (gate > 0.999)
    stopped = (ho == 0) & (v < 0.2) & (e > 20)
    corr = float(np.corrcoef(v[straight], np.maximum(bp, bs)[straight])[0, 1]) if straight.sum() > 10 else float("nan")
    r1 = {
        "rightTurnFrames": int(right.sum()), "rightTurnPortGtStbdFrac": float(np.mean(bp[right] > bs[right])) if right.any() else None,
        "rightTurnMedianPortOverStbd": float(np.median(bp[right] / np.maximum(bs[right], 1e-3))) if right.any() else None,
        "rightTurnArmPortGtStbdFrac": float(np.mean(ap[right] > as_[right])) if right.any() else None,
        "leftTurnFrames": int(left.sum()), "leftTurnStbdGtPortFrac": float(np.mean(bs[left] > bp[left])) if left.any() else None,
        "leftTurnMedianStbdOverPort": float(np.median(bs[left] / np.maximum(bp[left], 1e-3))) if left.any() else None,
        "leftTurnArmStbdGtPortFrac": float(np.mean(as_[left] > ap[left])) if left.any() else None,
        "straightFrames": int(straight.sum()), "straightCorrSpeedVsBowWidth": corr,
        "stoppedFrames": int(stopped.sum()), "stoppedMaxBowWidth": float(np.max(np.maximum(bp, bs)[stopped])) if stopped.any() else None,
        "maxBowWidth": float(np.max(np.maximum(bp, bs))), "maxSpeed": float(np.nanmax(v)), "maxAbsYawRate": float(np.nanmax(np.abs(yr))),
    }
    r1["pass"] = bool(r1["rightTurnFrames"] > 90 and r1["leftTurnFrames"] > 90 and r1["rightTurnPortGtStbdFrac"] >= 0.95 and r1["leftTurnStbdGtPortFrac"] >= 0.95
                      and corr > 0.8 and r1["stoppedFrames"] > 0 and r1["stoppedMaxBowWidth"] < 0.05)

    # 受入の 2：主役波の上に航跡が出ない
    mex = np.array([float(x["wave"]) if x["wave"] not in ("NaN", "") else -1e9 for x in masks])
    wpx = np.array([int(x["wake_px"]) for x in masks]); hpx = np.array([int(x["hero_px"]) for x in masks]); ovp = np.array([int(x["overlap_px"]) for x in masks])
    mph = np.array([x["phase"] for x in masks]); mcam = np.array([x["cam"] for x in masks])
    after = mex >= fadeEnd
    per_phase = {}
    for pnm in ["Intro", "Approach", "Formation", "Hold", "Afterglow", "End"]:
        for cam in ["chase", "hmd"]:
            s = (mph == pnm) & (mcam == cam)
            if s.any():
                per_phase[pnm + "/" + cam] = {"samples": int(s.sum()), "wakeVisibleSamples": int((wpx[s] > 0).sum()), "maxWakePx": int(wpx[s].max()),
                                              "heroVisibleSamples": int((hpx[s] > 0).sum()), "maxHeroPx": int(hpx[s].max()), "overlapPxSum": int(ovp[s].sum())}
    after_frames = np.isfinite(wave) & (wave >= fadeEnd)
    r2 = {
        "maskSamples": int(len(masks)), "overlapPxSum": int(ovp.sum()), "overlapSamples": int((ovp > 0).sum()),
        "afterFadeSamples": int(after.sum()), "afterFadeWakePxMax": int(wpx[after].max()) if after.any() else None,
        "afterFadeHeroVisibleSamples": int((hpx[after] > 0).sum()) if after.any() else None,
        "framesAfterFade": int(after_frames.sum()), "framesAfterFadeVisibleVerts": int(col(rows, "visible_verts")[after_frames].sum()),
        "framesAfterFadeRendererOn": int(col(rows, "renderer_on")[after_frames].sum()),
        "firstFrameGateZeroWave": float(wave[np.argmax(gate <= 0)]) if (gate <= 0).any() else None,
        "guardHiddenVertexInstances": int((col(rows, "guard_hidden") + col(rows, "overhang_hidden") + col(rows, "outside_hidden")).sum()),
        "guardHiddenByPhase": {pnm: int((col(rows, "guard_hidden") + col(rows, "overhang_hidden") + col(rows, "outside_hidden"))[ph == pnm].sum()) for pnm in ["Intro", "Approach", "Formation"]},
        "maxVisibleVertexY": float(np.nanmax(col(rows, "max_visible_y"))),
        "guardHeightM": cfg["gate"]["guardHeightM"],
        "heroMaxYAtMaskSamples": {"atWave0": None, "atFadeEnd": None, "atTStar": None},
        "perPhase": per_phase,
    }
    hy = np.array([float(x["hero_max_y"]) for x in masks])
    for key, tw in (("atWave0", 0.0), ("atFadeEnd", fadeEnd), ("atTStar", 12.0)):
        ok = np.isfinite(mex) & (mex > -1e8)
        if ok.any():
            j = np.argmin(np.abs(np.where(ok, mex, 1e9) - tw))
            r2["heroMaxYAtMaskSamples"][key] = {"wave": float(mex[j]), "heroMaxY": float(hy[j])}
    r2["pass"] = bool(r2["overlapPxSum"] == 0 and r2["afterFadeWakePxMax"] == 0 and r2["framesAfterFadeVisibleVerts"] == 0 and r2["framesAfterFadeRendererOn"] == 0
                      and (r2["afterFadeHeroVisibleSamples"] or 0) > 0)

    # 原画視点の回帰なし
    a = cv2.imread(MAIN + "/painting/painting_end.png"); b = cv2.imread(REF47)
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(2)
    r3 = {"image": "Unity/Build/Design/48/wake/unity/main/painting/painting_end.png", "sha256": sha(MAIN + "/painting/painting_end.png"),
          "ref47": "Unity/Build/Design/47/flow/unity/main/painting/painting_end.png", "ref47Sha256": sha(REF47),
          "pxDiff": int((d > 0).sum()), "maxDiff": int(d.max())}
    r3["pass"] = r3["pxDiff"] == 0

    # 実行の道
    ev = play["events"]
    r4 = {"frames": play["frames"], "captured": play["captured"], "flowErrors": play["flowErrors"], "wakeErrors": play["wake"]["errors"], "wakeTeleports": play["wake"]["teleports"],
          "boatWaterFallbacks": play["boatWater"]["fallbacks"], "inputFallbackFrames": play["input"]["fallbackFrames"],
          "eventsFired": sum(1 for x in ev if x["fired"]), "events": len(ev), "handover": play["handover"], "experienceEnd": play["clock"]["experienceEnd"],
          "protectedUnchanged": build["protectedUnchanged"],
          "wakeTickMsMean": play["wake"].get("tickMsTotal", float("nan")) / max(1, play["wake"].get("ticks", 1)), "wakeTickMsMax": play["wake"].get("tickMsMax"),
          "wakeTickNoteJa": "DS48Wake.Tick（速さ・網の作り直し、C# の Stopwatch）の PC の Editor の値。HMD 実機の H2 は設計50 で測る", "heroRenderersNote": [n for n in play["notes"] if n.startswith("heroRenderers")]}
    r4["pass"] = bool(r4["flowErrors"] == 0 and r4["wakeErrors"] == 0 and r4["boatWaterFallbacks"] == 0 and r4["eventsFired"] == r4["events"] and r4["protectedUnchanged"])

    video = OUT + "/ds48_wake_30fps.mp4"
    make_video(rows, play, video)
    fig_reaction(rows, play, masks, OUT + "/fig_ds48_reaction.png")
    hs = play["handover"]["s"]; ws = play["handover"]["waveStart"]
    picks = [(4.0, "straight, speeding up"), (6.9, "straight, full speed"), (10.5, "turn right (D)"), (13.5, "after right turn"), (19.5, "turn left (A)"), (23.5, "no input, slowing"),
             (26.4, "stop (Space)"), (hs + 3.0, "approach (fixed trajectory)"), (ws - 0.3, "formation start"), (ws + 1.0, "wave t 1: fading"), (ws + 2.5, "wave t 2.5: gone"), (ws + 12.1, "t* hold: no wake")]
    stills(rows, play, picks, OUT + "/stills_ds48_wake.png")
    seat_look(play, OUT + "/stills_ds48_seat_look.png")

    hm = mcam == "hmd"
    seat = {"hmdForwardWakePxMax": int(wpx[hm].max()), "hmdForwardWakeVisibleSamples": int((wpx[hm] > 0).sum()), "hmdSamples": int(hm.sum()), "looks": play.get("looks", []),
            "noteJa": "座席の視点（前向き、PC の 80°）では、平たい泡と航跡は船縁に隠れ、見える水面はかすめる角度なので、10 コマ/s の検査で 1 画素も見えなかった。"
                      "頭を横・後ろへ向けた画（stills_ds48_seat_look.png）でも、遠くの細い線にしか見えない。記録した限界として仕上げ48 へ送る（受入は追いかけのカメラの動画で判定）"}
    metrics = {"schema": "GreatWave.DS48.wake_metrics/1", "acceptance1_steering_reaction": r1, "acceptance2_no_wake_on_hero": r2, "painting_view_no_regression": r3, "play_path": r4, "seat_view_limit": seat,
               "pass": bool(r1["pass"] and r2["pass"] and r3["pass"] and r4["pass"]),
               "noteJa": "PC の Unity の Editor の Play（batchmode、1 フレーム = 1/90 s）の記録から数え直した。HMD 実機ではない（保留）。追いかけのカメラは試験だけのカメラで、体験の場面には入らない。"}
    json.dump(metrics, open(OUT + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ins = [MAIN + "/ds48_play.json", MAIN + "/ds48_frames.csv", MAIN + "/ds48_masks.csv", OUT + "/unity/ds48_build.json", MAIN + "/painting/painting_end.png", REF47,
           CFG, REPO + "/Unity/Assets/GreatWave/Design48/Scripts/DS48Wake.cs", REPO + "/Unity/Assets/GreatWave/Design48/Scripts/DS48Recorder.cs",
           REPO + "/Unity/Assets/GreatWave/Design48/Shaders/DS48_Foam.shader", REPO + "/Unity/Assets/GreatWave/Design48/Editor/DS48WakeBuild.cs",
           REPO + "/Unity/Assets/GreatWave/Design48/Editor/DS48WakePlay.cs", REPO + "/Unity/Assets/GreatWave/Design48/Scenes/DS48_Wake.unity",
           REPO + "/Unity/Assets/GreatWave/Design48/Materials/DS48_Foam.mat"]
    outs = [video, OUT + "/fig_ds48_reaction.png", OUT + "/stills_ds48_wake.png", OUT + "/stills_ds48_seat_look.png", OUT + "/metrics.json"]
    ffv = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    run = {"schema": "GreatWave.DS48.wake_run/1", "python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__, "ffmpeg": ffv,
           "unity": play["unity"], "device": play["device"],
           "unityCmds": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds48/run_ds48_unity.ps1 -Method GreatWave.Design48.EditorTools.DS48WakePlay.BuildScene -Log build2",
                         "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds48/run_ds48_unity.ps1 -NoQuit -Method GreatWave.Design48.EditorTools.DS48WakePlay.Run -Log main4",
                         "py -3.10 Tools/GWWaveGen/ds48/ds48_report.py"],
           "inputs": {os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in ins},
           "outputs": {os.path.relpath(p, REPO).replace("\\", "/"): {"sha256": sha(p), "bytes": os.path.getsize(p)} for p in outs},
           "seconds": round(time.time() - T0, 1)}
    json.dump(run, open(OUT + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"pass": metrics["pass"], "r1": r1["pass"], "r2": r2["pass"], "r3": r3["pass"], "r4": r4["pass"]}))


if __name__ == "__main__":
    main()
