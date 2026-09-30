"""設計50 release の部：Release のプレイヤーの自動の試しの記録を数え直し、H2（フレーム時間の p95/p99）・停止の試し・入口から出口・終わりの画面を
metrics.json にまとめ、図（フレーム時間・時刻の流れ）と、記録の走り（1/30 s ごとの画）から動画と静止画を作る。

使い方（リポジトリ根で）：
  py -3.10 Tools/GWWaveGen/ds50/ds50_report.py --main main1 --capture capture1 [--vr vr1]
入力：Unity/Build/Design/50/release/runs/<tag>/（report*.json・frames*.csv・launch.json・player.log・frames/*.jpg）と unity/ds50_build.json。
出力：Unity/Build/Design/50/release/ の metrics.json・run.json・fig_ds50_*.png・stills/*.png・ds50_release_*.mp4。
"""
import argparse
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

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Unity", "Build", "Design", "50", "release")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
REF47 = os.path.join(REPO, "Unity", "Build", "Design", "47", "flow", "unity", "main", "painting", "painting_end.png")
BUDGET_MS = 1000.0 / 90.0
USER_KEYS = {"Enter", "W", "A", "D", "S", "P", "Escape", "C", "Q", "Space", "R", "Digit1", "Digit2", "Digit3", "Digit4"}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fnum(x):
    try:
        return float(x)
    except ValueError:
        return float("nan")


def load_run(tag, capture=False):
    d = os.path.join(OUT, "runs", tag)
    rep = json.load(open(os.path.join(d, "report_capture.json" if capture else "report.json"), encoding="utf-8"))
    launch = json.load(open(os.path.join(d, "launch.json"), encoding="utf-8-sig"))
    rows = list(csv.DictReader(open(os.path.join(d, "frames_capture.csv" if capture else "frames.csv"), encoding="utf-8")))
    cols = {k: [r[k] for r in rows] for k in rows[0].keys()}
    num = {k: np.array([fnum(v) for v in cols[k]]) for k in ("frame", "st", "real", "udt", "dt", "exp", "wave", "boatX", "boatY", "boatZ", "riderLevel", "audioPlaying", "ftCpu", "ftCpuMain", "ftCpuRender", "ftGpu", "clockRunning", "flowPaused")}
    txt = {k: np.array(cols[k]) for k in ("phase", "shell", "pauseReason", "keys")}
    log = open(os.path.join(d, "player.log"), encoding="utf-8", errors="replace").read()
    return dict(dir=d, rep=rep, launch=launch, n=num, t=txt, log=log)


def pct(a, q):
    a = a[np.isfinite(a)]
    return [round(float(v), 4) for v in np.percentile(a, q)] if len(a) else None


def stats(ms):
    ms = ms[np.isfinite(ms) & (ms > 0)]
    if len(ms) == 0:
        return None
    p = np.percentile(ms, [50, 95, 99])
    return dict(frames=int(len(ms)), meanMs=round(float(ms.mean()), 4), p50Ms=round(float(p[0]), 4), p95Ms=round(float(p[1]), 4), p99Ms=round(float(p[2]), 4),
                maxMs=round(float(ms.max()), 4), over11_1ms=int((ms > BUDGET_MS).sum()), over16_7ms=int((ms > 1000 / 60).sum()))


def h2(run):
    n, t = run["n"], run["t"]
    udt = n["udt"] * 1000.0
    res = {}
    running = t["shell"] == "Running"
    sets = [("running_all", running), ("whole_run_including_screens", np.ones_like(running, bool))]
    for p in ("Intro", "Approach", "Formation", "Hold", "Afterglow"):
        sets.append(("running_" + p, running & (t["phase"] == p)))
    for name, m in sets:
        res[name] = dict(wallFrameTime=stats(udt[m]), cpuFrameTime=stats(n["ftCpu"][m]), cpuMainThread=stats(n["ftCpuMain"][m]), gpuFrameTime=stats(n["ftGpu"][m]))
    return res


def verify_stops(run):
    """停止の試しを CSV から数え直す（自動の試しの自分の判定とは別に）。"""
    n, t, rep = run["n"], run["t"], run["rep"]
    fr = n["frame"].astype(np.int64)
    idx = {int(f): i for i, f in enumerate(fr)}
    out = []
    for s in rep["stops"]:
        K, I = s["keySeenFrame"], s["injectFrame"]
        # 再開の後に Running に戻ったフレーム（枠の記録）
        R = None
        for c in rep["stateChanges"]:
            f = int(c.split()[0])
            if f > K and "Stopped→Running" in c:
                R = f
                break
        iK, iR = idx.get(K), idx.get(R)
        seg = slice(iK + 1, iR)   # キーを読んだフレームの次から、再開のフレームの前まで
        e = n["exp"][seg]
        b = np.stack([n["boatX"][seg], n["boatY"][seg], n["boatZ"][seg]], 1)
        e_key = n["exp"][iK]
        rec = dict(label=s["label"], key=s["key"], phase=s["phaseAtStop"], injectFrame=I, keySeenFrame=K, resumeFrame=R,
                   framesAfterKeyWhileStopped=int(len(e)),
                   expAdvanceAfterKeyFrameS=float(np.nanmax(np.abs(e - e_key))) if len(e) else None,
                   boatMoveAfterKeyFrameM=float(np.nanmax(np.linalg.norm(b - b[0], axis=1))) if len(b) else None,
                   audioPlayingMax=int(np.nanmax(n["audioPlaying"][seg])) if len(e) else None,
                   clockRunningFrames=int(np.nansum(n["clockRunning"][seg])),
                   shellStoppedFrames=int((t["shell"][seg] == "Stopped").sum()),
                   inputLatencyFrames=int(K - I),
                   injectToFreezeMs=round(float((n["real"][iK] - n["real"][idx[I]]) * 1000.0), 3),
                   wallTimeStoppedS=round(float(n["real"][iR] - n["real"][iK]), 4) if iR is not None else None)
        # 押したフレームの次のフレーム（Input System が読む最も早いフレーム）で停止に入り、その後は時計も船も音も動かない。
        # 船の位置は float32 の丸め（座標 8〜16 m の 1 ULP = 9.5e-7 m）を動きと数えないよう、1e-5 m（0.01 mm）未満を止まっているとする
        rec["pass"] = (rec["inputLatencyFrames"] == 1 and rec["expAdvanceAfterKeyFrameS"] == 0.0 and rec["boatMoveAfterKeyFrameM"] < 1e-5
                       and rec["audioPlayingMax"] == 0 and rec["clockRunningFrames"] == 0 and rec["shellStoppedFrames"] == rec["framesAfterKeyWhileStopped"])
        out.append(rec)
    return out


def keys_used(rep):
    ks = set()
    for k in rep["keysLog"]:
        ks.add(k.split()[1])
    return sorted(ks)


def fig_frametime(run, path):
    n, t = run["n"], run["t"]
    W, H = 1600, 900
    img = np.full((H, W, 3), 245, np.uint8)
    real = n["real"] - n["real"][0]
    udt = n["udt"] * 1000.0
    gpu = n["ftGpu"]
    xr = (0, float(real[-1]) + 1)
    put(img, "Design 50 release: Release player (Windows, D3D11, 1920x1080 windowed, vSync off), automated run main - frame time (H2)", (20, 30), 0.6, (20, 20, 20), 1, bg=False)
    p = Panel(img, 90, 80, 1460, 330, xr, (0, 14), "wall frame time per frame [ms] (Time.unscaledDeltaTime); red dashed = 11.1 ms (90 Hz budget)", "ms")
    # 状態の帯
    sh = t["shell"]
    col = {"Entry": (230, 225, 200), "Stopped": (200, 210, 245), "End": (225, 235, 210)}
    i0 = 0
    for i in range(1, len(sh) + 1):
        if i == len(sh) or sh[i] != sh[i0]:
            if sh[i0] in col:
                p.span(real[i0], real[i - 1], col[sh[i0]])
            i0 = i
    p.line(real, np.minimum(udt, 14), (40, 40, 40), 1)
    p.hline(BUDGET_MS, (40, 40, 220), dashed=True)
    p.axes(range(0, int(xr[1]) + 1, 10), [0, 2, 4, 6, 8, 10, 12, 14])
    q = Panel(img, 90, 490, 1460, 300, xr, (0, 8), "GPU frame time [ms] (FrameTimingManager.gpuFrameTime) and CPU main thread [ms]", "ms")
    q.line(real, np.minimum(gpu, 8), (40, 120, 40), 1)
    q.line(real, np.minimum(n["ftCpuMain"], 8), (160, 80, 40), 1)
    q.axes(range(0, int(xr[1]) + 1, 10), [0, 2, 4, 6, 8])
    put(img, "bands: light blue = entry screen, pink = stopped (P/Esc), green = end screen.  green line = GPU, blue line = CPU main thread.  x = real s since first frame.  Formation frames (20-55 ms) are clipped at the top", (90, 840), 0.45, (40, 40, 40), 1, bg=False)
    cv2.imwrite(path, img)


def fig_timeline(run, path, stops):
    n, t, rep = run["n"], run["t"], run["rep"]
    W, H = 1600, 700
    img = np.full((H, W, 3), 245, np.uint8)
    real = n["real"] - n["real"][0]
    xr = (0, float(real[-1]) + 1)
    put(img, "Design 50 release: entry -> experience -> end -> exit, automated (virtual keyboard only). experience clock vs real time", (20, 30), 0.6, (20, 20, 20), 1, bg=False)
    p = Panel(img, 90, 80, 1460, 440, xr, (0, 80), "experience seconds (GWClock) - flat while entry screen / stopped / end screen", "s")
    sh = t["shell"]
    col = {"Entry": (230, 225, 200), "Stopped": (200, 210, 245), "End": (225, 235, 210)}
    i0 = 0
    for i in range(1, len(sh) + 1):
        if i == len(sh) or sh[i] != sh[i0]:
            if sh[i0] in col:
                p.span(real[i0], real[i - 1], col[sh[i0]])
            i0 = i
    p.line(real, n["exp"], (30, 30, 30), 2)
    for c in rep["stateChanges"]:
        parts = c.split()
        f = int(parts[0])
        i = np.searchsorted(n["frame"], f)
        if i < len(real):
            p.vline(real[i], (90, 90, 90))
            put(img, parts[-1][:14], (p.X(real[i]) + 3, 100 + 14 * (rep["stateChanges"].index(c) % 6)), 0.38, (20, 20, 20), 1, bg=False)
    p.axes(range(0, int(xr[1]) + 1, 10), range(0, 81, 10))
    y = 580
    for s in stops:
        put(img, "stop %-28s key=%-6s latency %d frame(s) (%.2f ms)  clock/boat/audio after key: %s/%s/%s  %s" % (
            s["phase"], s["key"], s["inputLatencyFrames"], s["injectToFreezeMs"], s["expAdvanceAfterKeyFrameS"], s["boatMoveAfterKeyFrameM"], s["audioPlayingMax"], "PASS" if s["pass"] else "FAIL"),
            (90, y), 0.45, (20, 20, 20), 1, bg=False)
        y += 22
    cv2.imwrite(path, img)


def make_video(cap, outp_full, outp_small):
    d = os.path.join(cap["dir"], "frames")
    files = sorted(os.listdir(d))
    first = int(files[0][2:8])
    last = int(files[-1][2:8])
    assert last - first + 1 == len(files), "記録の画が抜けている"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", "30", "-start_number", str(first), "-i", os.path.join(d, "f_%06d.jpg"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", outp_full]
    subprocess.run(cmd, check=True)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", outp_full, "-vf", "scale=960:540", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", outp_small], check=True)
    return dict(frames=len(files), firstFrame=first, lastFrame=last, seconds=round(len(files) / 30.0, 3))


def pick_stills(cap):
    n, t, rep = cap["n"], cap["t"], cap["rep"]
    fr = n["frame"].astype(np.int64)
    sh, exp = t["shell"], n["exp"]
    d = os.path.join(cap["dir"], "frames")

    def first(m, add=0):
        i = np.flatnonzero(m)
        return int(fr[min(i[0] + add, len(fr) - 1)]) if len(i) else None

    ws, ag = rep["waveStartS"], rep["afterglowStartS"]
    lvl = n["riderLevel"]
    picks = [
        ("entry", "1 entry screen (Japanese controls)", first(sh == "Entry", 45)),
        ("intro", "2 intro: steering (W/A/D)", first((sh == "Running") & (exp >= 6.0))),
        ("stop_intro", "3 stop (P) in intro", first(sh == "Stopped", 15)),
        ("comfort", "4 comfort toggle (C) -> L3 notice", first((lvl == 3), 20)),
        ("formation", "5 formation: jet start", first((sh == "Running") & (exp >= ws + 9.6))),
        ("stop_formation", "6 stop (Esc) in formation", first((sh == "Stopped") & (exp > ws), 10)),
        ("tstar_hold", "7 t* hold", first((sh == "Running") & (exp >= ws + 12.8))),
        ("afterglow", "8 afterglow: painting view", first((sh == "Running") & (exp >= ag + 9.0))),
        ("end", "9 end screen", first(sh == "End", 30)),
    ]
    os.makedirs(os.path.join(OUT, "stills"), exist_ok=True)
    out, tiles = [], []
    for key, lab, f in picks:
        if f is None:
            out.append(dict(key=key, frame=None))
            continue
        img = cv2.imread(os.path.join(d, "f_%06d.jpg" % f))
        p = os.path.join(OUT, "stills", "ds50_%s.png" % key)
        cv2.imwrite(p, img)
        i = int(np.searchsorted(fr, f))
        out.append(dict(key=key, labelEn=lab, frame=f, exp=round(float(exp[i]), 4), shell=str(sh[i]), path=os.path.relpath(p, REPO).replace("\\", "/"), sha256=sha256_file(p)))
        tile = cv2.resize(img, (640, 360), interpolation=cv2.INTER_AREA)
        put(tile, "%s  (exp %.1f s)" % (lab, exp[i]), (8, 22), 0.5, (255, 255, 255), 1, bg=True)
        tiles.append(tile)
    while len(tiles) % 3:
        tiles.append(np.full((360, 640, 3), 245, np.uint8))
    rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
    sheet = np.vstack(rows)
    cv2.imwrite(os.path.join(OUT, "stills_ds50_release.png"), sheet)
    return out


def painting_regression(cap):
    """余韻の終わり（原画の視点に着いた後、終わりの画面の前）の画を、設計47 の painting_end.png と比べる（記録のみ。JPG の記録なので小さな差は出る）。"""
    n, t, rep = cap["n"], cap["t"], cap["rep"]
    # CSV の行は自動の試し（実行の順 −300）が枠（100）より先に書くので、終わりの画面へ入ったフレームの行はまだ Running。
    # その画には終わりの画面が写るので、終わりの画面へ入る 3 フレーム前の画を使う
    m = (t["shell"] == "Running") & (n["exp"] >= rep["afterglowStartS"] + 6.5)
    i = np.flatnonzero(m)
    if not len(i) or not os.path.exists(REF47):
        return None
    i = i[:-3]
    f = int(n["frame"][i[-1]])
    a = cv2.imread(os.path.join(cap["dir"], "frames", "f_%06d.jpg" % f)).astype(np.int16)
    b = cv2.imread(REF47).astype(np.int16)
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0])).astype(np.int16)
    diff = np.abs(a - b).max(axis=2)
    vis = np.clip(diff * 4, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT, "fig_ds50_painting_vs_ds47_diff.png"), cv2.applyColorMap(vis, cv2.COLORMAP_MAGMA))
    return dict(frame=f, exp=round(float(n["exp"][i[-1]]), 4), ref=os.path.relpath(REF47, REPO).replace("\\", "/"), refSha256=sha256_file(REF47),
                meanAbsDiff=round(float(np.abs(a - b).mean()), 4), pctPixelsDiffOver24=round(float((diff > 24).mean() * 100), 4), pctPixelsDiffOver64=round(float((diff > 64).mean() * 100), 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--vr", default="")
    a = ap.parse_args()
    t0 = time.time()
    run = load_run(a.main)
    cap = load_run(a.capture, capture=True)
    vr = load_run(a.vr) if a.vr else None
    build = json.load(open(os.path.join(OUT, "unity", "ds50_build.json"), encoding="utf-8"))
    rep = run["rep"]
    H2 = h2(run)
    stops = verify_stops(run)
    stops_cap = verify_stops(cap)
    fig_frametime(run, os.path.join(OUT, "fig_ds50_frametime.png"))
    fig_timeline(run, os.path.join(OUT, "fig_ds50_timeline.png"), stops)
    vid = make_video(cap, os.path.join(OUT, "ds50_release_30fps.mp4"), os.path.join(OUT, "ds50_release_540p_30fps_small.mp4"))
    stills = pick_stills(cap)
    reg = painting_regression(cap)

    def through(r):
        rp, ln = r["rep"], r["launch"]
        ks = keys_used(rp)
        return dict(tag=os.path.basename(r["dir"]), pass_=bool(rp["pass"] and ln["exitCode"] == 0 and not ln["timedOut"] and set(ks) <= USER_KEYS),
                    autotestPass=rp["pass"], exitCode=ln["exitCode"], timedOut=ln["timedOut"], quitCause=rp["quitCause"], keysUsed=ks, developerInputs=ln.get("developerInputs"),
                    entryShownS=round(rp["entryRealS"], 3), endScreenS=round(rp["endScreenRealS"], 3), eventsFired=rp["eventsFired"], errors=rp["errors"], exceptions=rp["exceptions"],
                    experienceTotalS=round(rp["endS"], 4), handoverS=round(rp["handoverS"], 4), realSeconds=round(rp["realSeconds"], 3), frames=rp["frames"],
                    dataRootUsed=rp["dataRootUsed"], workingDirectory=ln["workingDirectory"], vrRequested=rp["vrRequested"], vrActive=rp["vrActive"], vrStatusJa=rp["vrStatusJa"],
                    screen="%dx%d" % (rp["screenW"], rp["screenH"]), stopsPassAutotest=[s["pass"] for s in rp["stops"]], comfortPass=[c["pass"] for c in rp["comfort"]],
                    unityLogErrorLines=int(sum(1 for L in r["log"].splitlines() if ("Exception" in L) or L.startswith("Error") or " error " in L.lower())),
                    openxrRuntimeUnavailableLines=int(r["log"].count("XR_ERROR_RUNTIME_UNAVAILABLE")))

    th_main, th_cap = through(run), through(cap)
    th_vr = through(vr) if vr else None
    end_ok = bool(rep["endShown"] and rep["endShownFrame"] > 0 and rep["endEventFrame"] > 0 and rep["quitCause"].startswith("end_"))
    rs = H2["running_all"]
    metrics = dict(
        schema="GreatWave.DS50.release.metrics/1", generated=time.strftime("%Y-%m-%dT%H:%M:%S"),
        build=dict(exe=build["playerPath"], exeSha256=build["exeSha256"],
                   assemblyCSharpSha256=sha256_file(os.path.join(OUT, "player", "GreatWave50_Data", "Managed", "Assembly-CSharp.dll")),
                   level0Sha256=sha256_file(os.path.join(OUT, "player", "GreatWave50_Data", "level0")), buildResult=build["buildResult"], buildOptions=build["buildOptions"], scene=build["scene50"], sceneSha256=build["scene50Sha256"],
                   playerBytes=build["totalSize"], dataFiles=build["dataFiles"], dataBytes=build["dataBytes"], absolutePathsAfter=build["absolutePathsAfter"], rewrites=len(build["rewrites"]),
                   protectedUnchanged=build["protectedUnchanged"], layerSetTogglesOff=build["layerSetTogglesOff"], frameTimingStatsRestored=build["frameTimingStatsRestored"], runInBackgroundRestored=build["runInBackgroundRestored"]),
        gates=[
            dict(item="最小の受入1：開発者の操作を一度も挟まずに入口から出口まで通る（271、通し）", criterion="Release の exe・自動の試し（仮想のキーボードで利用者と同じキーだけ）で入口 → 体験 → 終わりの画面 → Q で出口、exit 0、例外・エラー 0、出来事 9",
                 value=dict(main=th_main, capture=th_cap, vr=th_vr), verdict="合格" if th_main["pass_"] and th_cap["pass_"] and (th_vr is None or th_vr["pass_"]) else "不合格"),
            dict(item="最小の受入2：停止が即座に効く", criterion="押したキーを Input System が読む最初のフレームで停止し、その後は時計・座席の船・音が 1 フレームも進まない（導入・形成・余韻の 3 回）",
                 value=dict(main=stops, capture=stops_cap), verdict="合格" if all(s["pass"] for s in stops + stops_cap) and len(stops) == 3 else "不合格"),
            dict(item="最小の受入3：体験の終わりが分かる", criterion="end の出来事の後に終わりの画面（日本語、終了の操作と自動終了の秒）が出て、Q で出口。初めての人の試遊記録（D29）は保留（利用者の手）",
                 value=dict(endEventFrame=rep["endEventFrame"], endShownFrame=rep["endShownFrame"], endScreenShownS=round(rep["endScreenRealS"], 3), quitCause=rep["quitCause"], still="Unity/Build/Design/50/release/stills/ds50_end.png"),
                 verdict="合格（PC の自動の試し）。試遊の記録は保留" if end_ok else "不合格"),
            dict(item="H2：このPCのフレーム時間 p95/p99（記録）", criterion="記録（PS VR2 の 90 Hz の 1 コマ 11.1 ms に照らす。判定は HMD 実機）",
                 value=dict(conditions="Release・D3D11・1920x1080 の窓・vSync 0・targetFrameRate −1・PC の単眼（XR なし）・" + rep["gpu"] + "・" + rep["cpu"], running_all=rs, perPhase={k: v for k, v in H2.items() if k.startswith("running_") and k != "running_all"}, wholeRun=H2["whole_run_including_screens"]),
                 verdict="記録"),
            dict(item="H7：再センタリング・停止・復帰（HMD の通し）", criterion="PS VR2 の実機", value="PC の停止・再開は上の最小の受入2。HMD の runtime 側の再センタリング・停止は PS VR2 の導入が要る", verdict="保留（利用者の手）"),
            dict(item="D29：初めての人 1〜2 名の試遊", criterion="利用者本人と研究室の 1 名（既定値・利用者未回答）", value="exe と操作の説明は用意した（入口の画面）", verdict="保留（利用者の手）"),
            dict(item="--vr（同じ exe）", criterion="記録（XR の runtime がなければ PC の画面へ戻る）", value=th_vr, verdict="記録（HMD 実機は保留）" if th_vr else "未実行"),
            dict(item="原画視点の回帰（計画 §2.0、記録）", criterion="余韻の終わりの画を設計47 の painting_end.png と比べる（JPG の記録なので記録のみ）", value=reg, verdict="記録"),
        ],
        video=dict(full="Unity/Build/Design/50/release/ds50_release_30fps.mp4", small="Unity/Build/Design/50/release/ds50_release_540p_30fps_small.mp4", **vid),
        stills=stills,
    )
    json.dump(metrics, open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    outs = ["metrics.json", "fig_ds50_frametime.png", "fig_ds50_timeline.png", "fig_ds50_painting_vs_ds47_diff.png", "stills_ds50_release.png", "ds50_release_30fps.mp4", "ds50_release_540p_30fps_small.mp4"]
    runj = dict(script="Tools/GWWaveGen/ds50/ds50_report.py", args=sys.argv[1:], python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__, ffmpeg=FFMPEG,
                inputs={k: sha256_file(os.path.join(r["dir"], f)) for k, r, f in [("main/report.json", run, "report.json"), ("main/frames.csv", run, "frames.csv"), ("capture/report_capture.json", cap, "report_capture.json"), ("capture/frames_capture.csv", cap, "frames_capture.csv")]},
                build="Unity/Build/Design/50/release/unity/ds50_build.json", buildSha256=sha256_file(os.path.join(OUT, "unity", "ds50_build.json")),
                outputs={o: sha256_file(os.path.join(OUT, o)) for o in outs if os.path.exists(os.path.join(OUT, o))}, seconds=round(time.time() - t0, 2))
    json.dump(runj, open(os.path.join(OUT, "run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("main pass", th_main["pass_"], "capture pass", th_cap["pass_"], "vr", th_vr and th_vr["pass_"])
    print("stops", [s["pass"] for s in stops], [s["pass"] for s in stops_cap])
    print("H2 running wall p95/p99", rs["wallFrameTime"]["p95Ms"], rs["wallFrameTime"]["p99Ms"], "gpu", rs["gpuFrameTime"] and (rs["gpuFrameTime"]["p95Ms"], rs["gpuFrameTime"]["p99Ms"]))
    print("regression", reg)


if __name__ == "__main__":
    main()
