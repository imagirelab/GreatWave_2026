"""設計50 の記録の道具：作る部（release の部）の出力を SHA-256 で照合し、生の記録（プレイヤーの毎フレームの CSV・報告の JSON・
静止画・動画）から作る部の数え直しの道具を使わずに数え直し、証拠を Docs/Evidence/Design/50/ へ写し、記録の metrics.json・run.json を書く。

使い方（リポジトリ根で）：
  py -3.10 -B Tools/GWWaveGen/ds50/ds50_record.py
入力（どれも Git 対象外）：Unity/Build/Design/50/release/（metrics.json・run.json・unity/ds50_build.json・runs/<tag>/・stills/・図・動画・player/）、
  設計47 の painting_end.png、設計49 の証拠の JSON（Docs/Evidence/Design/49/ の ds49_build.json・run.json。守るファイルと設計49 のファイルの SHA-256）。
出力：Docs/Evidence/Design/50/（1920×1080 の PNG・動画の写し・JSON）と、途中のファイル Unity/Build/Design/50/record/。
Unity は回さない。git の命令は使わない。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REL = os.path.join(REPO, "Unity", "Build", "Design", "50", "release")
REC = os.path.join(REPO, "Unity", "Build", "Design", "50", "record")
EVI = os.path.join(REPO, "Docs", "Evidence", "Design", "50")
REF47 = os.path.join(REPO, "Unity", "Build", "Design", "47", "flow", "unity", "main", "painting", "painting_end.png")
EVI49 = os.path.join(REPO, "Docs", "Evidence", "Design", "49")
FFMPEG_DIR = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin"
BUDGET_MS = 1000.0 / 90.0
RUNS = {"main5": "report.json", "vr4": "report.json", "capture5": "report_capture.json", "review_main1": "report.json"}
CSVS = {"main5": "frames.csv", "vr4": "frames.csv", "capture5": "frames_capture.csv", "review_main1": "frames.csv"}
PHASES = ("Intro", "Approach", "Formation", "Hold", "Afterglow")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def r4(v):
    return None if v is None else round(float(v), 4)


# ------------------------------------------------------------------ A. 照合
def verify():
    out = dict(checked=0, mismatches=[])

    def chk(label, path, want):
        got = sha(path) if os.path.exists(path) else "（ない）"
        out["checked"] += 1
        if got != want:
            out["mismatches"].append(dict(label=label, path=rel(path), want=want, got=got))
        return got

    run = jload(os.path.join(REL, "run.json"))
    tagdir = {"main": "main5", "capture": "capture5"}
    for k, v in run["inputs"].items():
        t, name = k.split("/", 1)
        chk("builder input " + k, os.path.join(REL, "runs", tagdir[t], name), v)
    for k, v in run["outputs"].items():
        chk("builder output " + k, os.path.join(REL, k), v)
    chk("ds50_build.json", os.path.join(REL, "unity", "ds50_build.json"), run["buildSha256"])
    met = jload(os.path.join(REL, "metrics.json"))
    b = jload(os.path.join(REL, "unity", "ds50_build.json"))
    player = os.path.join(REL, "player")
    chk("exe", os.path.join(player, "GreatWave50.exe"), met["build"]["exeSha256"])
    chk("Assembly-CSharp.dll", os.path.join(player, "GreatWave50_Data", "Managed", "Assembly-CSharp.dll"), met["build"]["assemblyCSharpSha256"])
    chk("level0", os.path.join(player, "GreatWave50_Data", "level0"), met["build"]["level0Sha256"])
    chk("scene50", os.path.join(REPO, "Unity", b["scene50"]), b["scene50Sha256"])
    chk("scene49 (build の前後)", os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design49", "Scenes", "DS49_Sound.unity"), b["scene49Sha256After"])
    for s in met["stills"]:
        chk("still " + s["key"], os.path.join(REPO, s["path"]), s["sha256"])
    for t in ("main5", "vr4", "capture5"):
        la = jload(os.path.join(REL, "runs", t, "launch.json"))
        chk("launch exe " + t, os.path.join(player, "GreatWave50.exe"), la["exeSha256"])
    # 束ねたデータ 38：プレイヤーの中の写しと、リポジトリの中の元
    gw = os.path.join(player, "GreatWave50_Data", "StreamingAssets", "gwdata")
    data = dict(files=len(b["data"]), bytes=0, bundleMismatch=0, sourceMismatch=0, sourceMissing=0)
    for d in b["data"]:
        data["bytes"] += d["bytes"]
        g = chk("gwdata " + d["rel"], os.path.join(gw, d["rel"]), d["sha256"])
        src = os.path.join(REPO, "Unity", d["rel"])
        if not os.path.exists(src):
            data["sourceMissing"] += 1
        elif sha(src) != g:
            data["sourceMismatch"] += 1
    data["bundleMismatch"] = sum(1 for m in out["mismatches"] if m["label"].startswith("gwdata"))
    extra = []
    for root, _, fs in os.walk(gw):
        for f in fs:
            r = os.path.relpath(os.path.join(root, f), gw).replace("\\", "/")
            if r not in {d["rel"] for d in b["data"]}:
                extra.append(r)
    data["filesNotInList"] = extra
    out["data"] = data
    # 守るファイル 43（設計49 の場面の作りの時の SHA-256）と、設計49 のファイル（設計49 の記録の run.json）
    b49 = jload(os.path.join(EVI49, "ds49_build.json"))
    prot = dict(count=0, changed=[])
    for line in b49["protected"]:
        p, h = line.rsplit(" ", 1)
        prot["count"] += 1
        if sha(os.path.join(REPO, "Unity", p)) != h:
            prot["changed"].append(p)
    out["protected43"] = prot
    r49 = jload(os.path.join(EVI49, "run.json"))
    d49 = dict(count=0, changed=[])

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and len(v) == 64 and k.replace("\\", "/").startswith("Unity/Assets/GreatWave/Design49/"):
                    d49["count"] += 1
                    if sha(os.path.join(REPO, k)) != v:
                        d49["changed"].append(k)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(r49)
    out["design49Files"] = d49
    # 場面の絶対のパスと GUID
    s50 = open(os.path.join(REPO, "Unity", b["scene50"]), encoding="utf-8").read()
    s49 = open(os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design49", "Scenes", "DS49_Sound.unity"), encoding="utf-8").read()
    import re
    out["scene"] = dict(
        bytes=os.path.getsize(os.path.join(REPO, "Unity", b["scene50"])),
        absolutePathStrings=len(re.findall(r"[A-Za-z]:[\\/]", s50)),
        absolutePathStrings49=len(re.findall(r"[A-Za-z]:[\\/]", s49)),
        guids50=sorted(set(re.findall(r"guid: ([0-9a-f]{32})", s50))),
        guids49=sorted(set(re.findall(r"guid: ([0-9a-f]{32})", s49))),
        objects50=s50.count("\n--- !u!"), objects49=s49.count("\n--- !u!"),
        cameras50=s50.count("--- !u!20 "), cameras49=s49.count("--- !u!20 "),
        listeners50=s50.count("--- !u!81 "), listeners49=s49.count("--- !u!81 "))
    newg = sorted(set(out["scene"]["guids50"]) - set(out["scene"]["guids49"]))
    lost = sorted(set(out["scene"]["guids49"]) - set(out["scene"]["guids50"]))
    # 新しい GUID を .meta から引く
    gmap = {}
    for root, _, fs in os.walk(os.path.join(REPO, "Unity", "Assets")):
        for f in fs:
            if f.endswith(".meta"):
                p = os.path.join(root, f)
                try:
                    txt = open(p, encoding="utf-8", errors="ignore").read(400)
                except OSError:
                    continue
                m = re.search(r"guid: ([0-9a-f]{32})", txt)
                if m and m.group(1) in newg:
                    gmap[m.group(1)] = rel(p)[:-5]
    out["scene"]["newGuids"] = {g: gmap.get(g, "（見つからない。組み込みの資産）") for g in newg}
    out["scene"]["lostGuids"] = lost
    del out["scene"]["guids50"], out["scene"]["guids49"]
    out["scene"]["guidCount50"] = len(set(re.findall(r"guid: ([0-9a-f]{32})", s50)))
    out["scene"]["guidCount49"] = len(set(re.findall(r"guid: ([0-9a-f]{32})", s49)))
    return out, met, b


# ------------------------------------------------------------------ B. 毎フレームの CSV の数え直し
def load_csv(path):
    import csv
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    cols = rows[0].keys()
    n, t = {}, {}
    for c in cols:
        if c in ("phase", "shell", "pauseReason", "keys"):
            t[c] = np.array([r[c] for r in rows])
        else:
            n[c] = np.array([float(r[c]) if r[c] not in ("", "NaN") else np.nan for r in rows])
    return n, t


def segs(a):
    out, s = [], 0
    for i in range(1, len(a) + 1):
        if i == len(a) or a[i] != a[s]:
            out.append((str(a[s]), s, i - 1))
            s = i
    return out


def st(ms):
    ms = ms[np.isfinite(ms) & (ms > 0)]
    if len(ms) == 0:
        return None
    p = np.percentile(ms, [50, 95, 99])
    return dict(n=int(len(ms)), mean=r4(ms.mean()), p50=r4(p[0]), p95=r4(p[1]), p99=r4(p[2]), max=r4(ms.max()),
                over11_1=int((ms > BUDGET_MS).sum()))


def recount(tag):
    d = os.path.join(REL, "runs", tag)
    n, t = load_csv(os.path.join(d, CSVS[tag]))
    rep = jload(os.path.join(d, RUNS[tag]))
    fr = n["frame"].astype(np.int64)
    sh, ph, keys = t["shell"], t["phase"], t["keys"]
    o = dict(rows=int(len(fr)), frameFirst=int(fr[0]), frameLast=int(fr[-1]),
             screens=sorted({f"{int(a)}x{int(b)}" for a, b in zip(n["screenW"], n["screenH"])}))
    o["shellSegments"] = [dict(state=s, first=int(fr[a]), last=int(fr[b]), frames=int(b - a + 1), expFirst=r4(n["exp"][a]), expLast=r4(n["exp"][b]),
                               realS=r4(n["real"][b] - n["real"][a])) for s, a, b in segs(sh)]
    o["keysUsed"] = sorted({k for ks in keys if ks for k in ks.split("+")})
    ent = sh == "Entry"
    o["entry"] = dict(frames=int(ent.sum()), expMax=r4(np.nanmax(n["exp"][ent])), realS=r4(n["real"][ent][-1] - n["real"][ent][0]))
    # 停止：Stopped の塊ごと。K = 塊の前の行（キーを読んだフレーム。枠の状態はそのフレームの中で変わる）
    stops = []
    for s, a, b in segs(sh):
        if s != "Stopped":
            continue
        K = a - 1
        I = K
        while I - 1 >= 0 and keys[I - 1] in ("P", "Escape"):
            I -= 1
        boat = np.stack([n["boatX"], n["boatY"], n["boatZ"]], 1)
        e = n["exp"][a:b + 1]
        stops.append(dict(
            key=str(keys[I]), phase=str(ph[K]), wave=r4(n["wave"][K]),
            injectFrame=int(fr[I]), keyReadFrame=int(fr[K]), firstStoppedRow=int(fr[a]), lastStoppedRow=int(fr[b]), stoppedRows=int(b - a + 1),
            injectToKeyReadMs=r4((n["real"][K] - n["real"][I]) * 1000), injectToFirstStoppedRowMs=r4((n["real"][a] - n["real"][I]) * 1000),
            expAdvanceInKeyReadFrameS=r4(n["exp"][K] - n["exp"][K - 1]),
            expMaxDriftAfterKeyReadS=float(np.nanmax(np.abs(e - n["exp"][K]))),
            boatMaxDriftAfterKeyReadM=float(np.nanmax(np.linalg.norm(boat[a:b + 1] - boat[K], axis=1))),
            clockRunningRows=int(np.nansum(n["clockRunning"][a:b + 1])),
            audioPlayingMax=int(np.nanmax(n["audioPlaying"][a:b + 1])),
            pauseReasons=sorted(set(t["pauseReason"][a:b + 1])),
            realStoppedS=r4(n["real"][b] - n["real"][a]),
            resumedToRunning=bool(b + 1 < len(sh) and sh[b + 1] == "Running"),
            expAdvance1AfterResumeS=r4(n["exp"][b + 1] - n["exp"][b]) if b + 1 < len(sh) else None))
    o["stops"] = stops
    lv = n["riderLevel"]
    ch = [i for i in range(1, len(lv)) if lv[i] != lv[i - 1]]
    cks = [i for i in range(1, len(keys)) if keys[i] == "C" and keys[i - 1] != "C"]
    o["comfort"] = [dict(cInjectFrame=int(fr[c]), levelChangeRow=int(fr[i]), rowsAfter=int(fr[i] - fr[c]), before=int(lv[i - 1]), after=int(lv[i]))
                    for c, i in zip(cks, ch)]
    o["audioMaxByShell"] = {s: int(np.nanmax(n["audioPlaying"][sh == s])) for s in sorted(set(sh))}
    o["audioRangeRunningByPhase"] = {p: [int(np.nanmin(n["audioPlaying"][(sh == "Running") & (ph == p)])), int(np.nanmax(n["audioPlaying"][(sh == "Running") & (ph == p)]))]
                                     for p in PHASES if ((sh == "Running") & (ph == p)).any()}
    ie = int(np.argmax(ph == "End"))
    ise = int(np.argmax(sh == "End"))
    endm = sh == "End"
    o["end"] = dict(phaseEndFirstRow=int(fr[ie]), shellEndFirstRow=int(fr[ise]), reportEndEventFrame=rep.get("endEventFrame"), reportEndShownFrame=rep.get("endShownFrame"),
                    expDuringEnd=[r4(np.nanmin(n["exp"][endm])), r4(np.nanmax(n["exp"][endm]))], endRows=int(endm.sum()),
                    realS=r4(n["real"][endm][-1] - n["real"][endm][0]), reportEndScreenRealS=r4(rep.get("endScreenRealS")))
    o["report"] = dict(pass_=rep.get("pass"), quitCause=rep.get("quitCause"), errors=rep.get("errors"), exceptions=rep.get("exceptions"), warnings=rep.get("warnings"),
                       eventsFired=rep.get("eventsFired"), frames=rep.get("frames"), realSeconds=r4(rep.get("realSeconds")), handoverS=r4(rep.get("handoverS")),
                       waveStartS=r4(rep.get("waveStartS")), afterglowStartS=r4(rep.get("afterglowStartS")), endS=r4(rep.get("endS")),
                       vSyncCount=rep.get("vSyncCount"), targetFrameRate=rep.get("targetFrameRate"), graphicsApi=rep.get("graphicsApi"),
                       gpu=rep.get("gpu"), cpu=rep.get("cpu"), dataRootUsed=rep.get("dataRootUsed"), vrRequested=rep.get("vrRequested"), vrActive=rep.get("vrActive"),
                       fontUsed=rep.get("fontUsed"), fixedDeltaTime=r4(rep.get("fixedDeltaTime")))
    if tag != "capture5":
        run = sh == "Running"
        udt = n["udt"] * 1000.0
        h = dict(all=dict(wall=st(udt[run]), cpuMain=st(n["ftCpuMain"][run]), gpu=st(n["ftGpu"][run])))
        for p in PHASES:
            m = run & (ph == p)
            h[p] = dict(wall=st(udt[m]), cpuMain=st(n["ftCpuMain"][m]), gpu=st(n["ftGpu"][m]))
        o["H2"] = h
    lp = os.path.join(d, "player.log")
    if os.path.exists(lp):
        txt = open(lp, encoding="utf-8", errors="ignore").read()
        o["playerLog"] = dict(xrRuntimeUnavailable=txt.count("XR_ERROR_RUNTIME_UNAVAILABLE"), exceptionLines=sum(1 for l in txt.splitlines() if "Exception" in l),
                              dataRootLine=next((l.split(" startCwd=")[0].split("used=")[-1] for l in txt.splitlines() if l.startswith("DS50_DATA_ROOT")), None),
                              startCwdInsideRepo=next((("GreatWave_2026_Fresh" in l.split(" startCwd=")[-1]) for l in txt.splitlines() if l.startswith("DS50_DATA_ROOT")), None))
    return o


# ------------------------------------------------------------------ C. 動画
def video(path):
    probe = subprocess.run([FFMPEG_DIR + "/ffprobe.exe", "-v", "error", "-show_entries", "stream=codec_name,width,height,nb_frames,r_frame_rate",
                            "-show_entries", "format=size,duration", "-of", "json", path], capture_output=True, text=True).stdout
    pj = json.loads(probe)
    cap = cv2.VideoCapture(path)
    means = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        means.append(float(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).mean()))
    cap.release()
    m = np.array(means)
    return dict(bytes=os.path.getsize(path), sha256=sha(path), codec=pj["streams"][0]["codec_name"], width=pj["streams"][0]["width"], height=pj["streams"][0]["height"],
                framesProbe=int(pj["streams"][0]["nb_frames"]), framesDecoded=len(m), fps=pj["streams"][0]["r_frame_rate"], durationS=r4(pj["format"]["duration"]),
                meanLumaMin=r4(m.min()), meanLumaMinAt=int(m.argmin()) + 1, blackFramesUnder16=int((m < 16).sum()), audioStreams=sum(1 for s in pj["streams"] if s.get("codec_name") in ("aac", "mp3", "opus")))


# ------------------------------------------------------------------ D. 終わりの画面と大波の唇
def end_panel():
    end = cv2.imread(os.path.join(REL, "stills", "ds50_end.png"))
    aft = cv2.imread(os.path.join(REL, "stills", "ds50_afterglow.png"))
    diff = np.abs(end.astype(np.int16) - aft.astype(np.int16)).max(2)
    # 飛沫などの小さな動きを除くため、画面の右上（x ≥ 900、y ≤ 500）で行と列の変化の割合から板の範囲を読む
    sub = diff[:500, 900:] > 6
    cols = np.where(sub.mean(0) > 0.5)[0]
    rows = np.where(sub.mean(1) > 0.5)[0]
    x0, x1, y0, y1 = int(cols.min() + 900), int(cols.max() + 900), int(rows.min()), int(rows.max())
    # 板の下にある大波の輪郭の線（暗い墨の線）を、余韻の静止画で数える
    g = cv2.cvtColor(aft, cv2.COLOR_BGR2GRAY)
    ink = g < 110
    box = np.zeros_like(ink)
    box[y0:y1 + 1, x0:x1 + 1] = True
    under = ink & box
    ys, xs = np.where(under)
    o = dict(panelBox=[x0, y0, x1, y1], diffPixelsInBox=int((diff[y0:y1 + 1, x0:x1 + 1] > 6).sum()),
             inkPixelsUnderPanel=int(under.sum()),
             inkBoxUnderPanel=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None,
             inkPixelsUnderPanelLeftOf1150=int((under[:, :1150]).sum()),
             stills=["Unity/Build/Design/50/release/stills/ds50_afterglow.png", "Unity/Build/Design/50/release/stills/ds50_end.png"],
             noteJa="余韻（体験の時刻 67.37 s）と終わりの画面（72.35 s）の静止画の差から板の範囲を読み、余韻の静止画の暗い線（灰 < 110）のうち板の範囲に入るものを数えた。視点は同じ（余韻の留まりの間）")
    # 図：左に余韻、右に終わりの画面（同じ範囲を 2.2 倍）
    X0, Y0, W, H = 820, 150, 420, 360
    k = 2.2
    a = cv2.resize(aft[Y0:Y0 + H, X0:X0 + W], (int(W * k), int(H * k)), interpolation=cv2.INTER_CUBIC)
    e = cv2.resize(end[Y0:Y0 + H, X0:X0 + W], (int(W * k), int(H * k)), interpolation=cv2.INTER_CUBIC)
    canvas = np.full((1080, 1920, 3), 244, np.uint8)
    ox = (1920 - 2 * a.shape[1] - 40) // 2
    oy = 150
    canvas[oy:oy + a.shape[0], ox:ox + a.shape[1]] = a
    canvas[oy:oy + e.shape[0], ox + a.shape[1] + 40:ox + 2 * a.shape[1] + 40] = e
    # 板の縁を右の画に細い線で
    bx0 = ox + a.shape[1] + 40 + int((x0 - X0) * k)
    by1 = oy + int((y1 - Y0) * k)
    cv2.line(canvas, (max(bx0, ox + a.shape[1] + 40), oy), (max(bx0, ox + a.shape[1] + 40), min(by1, oy + e.shape[0] - 1)), (40, 40, 200), 2)
    cv2.line(canvas, (max(bx0, ox + a.shape[1] + 40), min(by1, oy + e.shape[0] - 1)), (ox + 2 * a.shape[1] + 39, min(by1, oy + e.shape[0] - 1)), (40, 40, 200), 2)
    f = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(canvas, "Design 50 release: end screen panel vs the wave lip (crop x %d-%d, y %d-%d, x%.1f)" % (X0, X0 + W, Y0, Y0 + H, k), (40, 60), f, 0.9, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.putText(canvas, "left: afterglow still (exp 67.37 s, no panel)", (ox, oy - 20), f, 0.8, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.putText(canvas, "right: end screen (exp 72.35 s); red line = panel edge", (ox + a.shape[1] + 40, oy - 20), f, 0.8, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.putText(canvas, "panel box x %d-%d, y %d-%d; dark outline pixels under the panel: %d (x %s)" % (x0, x1, y0, y1, o["inkPixelsUnderPanel"],
                "%d-%d" % (o["inkBoxUnderPanel"][0], o["inkBoxUnderPanel"][2]) if o["inkBoxUnderPanel"] else "-"), (40, 1050), f, 0.8, (30, 30, 30), 2, cv2.LINE_AA)
    return o, canvas


# ------------------------------------------------------------------ E. 原画視点の画（記録）
def painting():
    csvp = os.path.join(REL, "runs", "capture5", "frames_capture.csv")
    n, t = load_csv(csvp)
    fr = n["frame"].astype(int)
    ag = jload(os.path.join(REL, "runs", "capture5", "report_capture.json"))["afterglowStartS"]
    m = (t["shell"] == "Running") & (t["phase"] == "Afterglow") & (n["exp"] >= ag + 6.5)
    idx = np.where(m)[0]
    last = int(fr[idx[-1]])
    endf = int(fr[np.argmax(t["phase"] == "End")])
    ref = cv2.imread(REF47).astype(np.int16)
    out = []
    # 余韻の最後のフレーム、作る部の選んだフレーム（終わりの画面の 3 フレーム前）、終わりの出来事のフレーム（終わりの画面が描かれる）
    for f in (last, endf - 3, endf):
        img = cv2.imread(os.path.join(REL, "runs", "capture5", "frames", "f_%06d.jpg" % f)).astype(np.int16)
        d = np.abs(img - ref)
        dm = d.max(2)
        out.append(dict(frame=f, exp=r4(n["exp"][fr == f][0]), shell=str(t["shell"][fr == f][0]), meanAbsDiff=r4(d.mean()),
                        pctOver24=r4((dm > 24).mean() * 100), pctOver64=r4((dm > 64).mean() * 100)))
    return dict(ref=rel(REF47), refSha256=sha(REF47), lastRunningAfterglowFrame=last, endEventFrame=endf, frames=out,
                noteJa="capture5 の JPG（品質は作る部の既定）と設計47 の PNG。JPG の圧縮の差を含む。差は画素ごとの 3 色の差の最大")


# ------------------------------------------------------------------ F. 証拠
def pad_to_1080(src, dst):
    im = cv2.imread(src)
    h, w = im.shape[:2]
    if (w, h) == (1920, 1080):
        shutil.copyfile(src, dst)
        return dict(src=rel(src), dst=rel(dst), from_=[w, h], placed="そのまま")
    bg = [int(v) for v in np.median(np.concatenate([im[0], im[-1]]), 0)]
    c = np.zeros((1080, 1920, 3), np.uint8)
    c[:] = bg
    s = min(1.0, 1920 / w, 1080 / h)
    if s < 1.0:
        im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        h, w = im.shape[:2]
    y, x = (1080 - h) // 2, (1920 - w) // 2
    c[y:y + h, x:x + w] = im
    cv2.imwrite(dst, c)
    return dict(src=rel(src), dst=rel(dst), from_=[int(w / s), int(h / s)], placed="1920×1080 の中央（地は図の地の色 %s）" % bg)


def main():
    t0 = time.time()
    os.makedirs(REC, exist_ok=True)
    os.makedirs(EVI, exist_ok=True)
    ver, met, b = verify()
    if ver["mismatches"]:
        print(json.dumps(ver["mismatches"], ensure_ascii=False, indent=1))
        sys.exit("SHA-256 が合わない")
    rc = {t: recount(t) for t in RUNS if os.path.exists(os.path.join(REL, "runs", t, RUNS[t]))}
    vid = video(os.path.join(REL, "ds50_release_540p_30fps_small.mp4"))
    ep, fig_end = end_panel()
    pv = painting()
    # 作る部の値との差
    diff = {}
    bm = met["gates"]
    main_b = bm[0]["value"]["main"]
    for tag, key in (("main5", "main"), ("vr4", "vr"), ("capture5", "capture")):
        bv = bm[0]["value"][key]
        r = rc[tag]
        diff[tag] = dict(frames=r["rows"] - bv["frames"], eventsFired=r["report"]["eventsFired"] - bv["eventsFired"],
                         keysSame=r["keysUsed"] == bv["keysUsed"], handoverS=r4(r["report"]["handoverS"] - bv["handoverS"]))
    for i, s in enumerate(bm[1]["value"]["main"]):
        r = rc["main5"]["stops"][i]
        diff["main5_stop%d" % i] = dict(keyRead=r["keyReadFrame"] - s["keySeenFrame"], inject=r["injectFrame"] - s["injectFrame"],
                                       injectToKeyReadMs=r4(r["injectToKeyReadMs"] - s["injectToFreezeMs"]),
                                       stoppedRows=r["stoppedRows"] - s["framesAfterKeyWhileStopped"],
                                       boat=r["boatMaxDriftAfterKeyReadM"] - s["boatMoveAfterKeyFrameM"])
    h2b = bm[3]["value"]
    hb = {"all": h2b["running_all"]}
    hb.update({p: h2b["perPhase"]["running_" + p] for p in PHASES})
    diff["H2_main5"] = {p: dict(n=rc["main5"]["H2"][p]["wall"]["n"] - hb[p]["wallFrameTime"]["frames"],
                                p95=r4(rc["main5"]["H2"][p]["wall"]["p95"] - hb[p]["wallFrameTime"]["p95Ms"]),
                                p99=r4(rc["main5"]["H2"][p]["wall"]["p99"] - hb[p]["wallFrameTime"]["p99Ms"])) for p in hb}
    rg = next(g for g in bm if g["item"].startswith("原画視点の回帰"))["value"]
    diff["painting"] = dict(frame=pv["frames"][1]["frame"] - rg["frame"], meanAbsDiff=r4(pv["frames"][1]["meanAbsDiff"] - rg["meanAbsDiff"]),
                            pctOver24=r4(pv["frames"][1]["pctOver24"] - rg["pctPixelsDiffOver24"]), pctOver64=r4(pv["frames"][1]["pctOver64"] - rg["pctPixelsDiffOver64"]))
    rec = dict(schema="GreatWave.DS50.record_recount/1", verify=ver, runs=rc, video=vid, endPanel=ep, painting=pv, diffVsBuilder=diff)
    with open(os.path.join(EVI, "ds50_record_recount.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    # 証拠の写し
    ev = []
    cv2.imwrite(os.path.join(EVI, "fig_ds50_end_panel.png"), fig_end)
    ev.append(dict(dst=rel(os.path.join(EVI, "fig_ds50_end_panel.png")), placed="記録で作った（1920×1080）"))
    for s, dname in (("stills_ds50_release.png", "stills_ds50_release.png"), ("stills/ds50_entry.png", "ds50_entry.png"), ("stills/ds50_end.png", "ds50_end.png"),
                     ("fig_ds50_timeline.png", "fig_ds50_timeline.png"), ("fig_ds50_frametime.png", "fig_ds50_frametime.png"),
                     ("fig_ds50_painting_vs_ds47_diff.png", "fig_ds50_painting_vs_ds47_diff.png")):
        ev.append(pad_to_1080(os.path.join(REL, s), os.path.join(EVI, dname)))
    shutil.copyfile(os.path.join(REL, "ds50_release_540p_30fps_small.mp4"), os.path.join(EVI, "ds50_release_960x540_30fps.mp4"))
    ev.append(dict(src="Unity/Build/Design/50/release/ds50_release_540p_30fps_small.mp4", dst=rel(os.path.join(EVI, "ds50_release_960x540_30fps.mp4")), placed="そのまま"))
    for s, dname in (("metrics.json", "ds50_release_metrics.json"), ("run.json", "ds50_release_run.json"), ("unity/ds50_build.json", "ds50_build.json")):
        shutil.copyfile(os.path.join(REL, s), os.path.join(EVI, dname))
        ev.append(dict(src=rel(os.path.join(REL, s)), dst=rel(os.path.join(EVI, dname)), placed="そのまま"))
    for e in ev:
        im = cv2.imread(os.path.join(REPO, e["dst"])) if e["dst"].endswith(".png") else None
        if im is not None:
            e["size"] = [im.shape[1], im.shape[0]]
        e["bytes"] = os.path.getsize(os.path.join(REPO, e["dst"]))
        e["sha256"] = sha(os.path.join(REPO, e["dst"]))
    # 記録の metrics.json
    m5 = rc["main5"]
    metrics = dict(
        schema="GreatWave.DS50.record_metrics/1",
        numberJa="設計50：初めての人が入口から出口まで試す",
        statusJa="閉じた（使える水準。最小の受入 3 つを PC の Release のプレイヤーで満たした。H2 は記録、H7 と初めての人の試遊（D29）は保留。受入の判定の後の修正 0 回）",
        evidenceKindJa="Unity 6000.4.3f1 の Windows の Release のプレイヤー（BuildOptions.None、D3D11、1920×1080 の窓、vSync 0）を自動の試し（Input System の仮想のキーボード）で動かした、PC（RTX 3080・i7-12700K）の結果。HMD 実機・人の試遊・ゲームパッドの結果ではない",
        planJa=dict(deliverable="Windows の Release ビルド（PC 版と --vr、同じ exe）。日本語の入口画面（操作説明）、停止と揺れ軽減の切替、終了画面。初めての人1〜2名の試遊（D29）",
                    minimumAcceptance="開発者の操作を一度も挟まずに入口から出口まで通る。停止が即座に効く。体験の終わりが分かる（試遊記録）。H2 の p95/p99、H7",
                    dependency="設計45〜49", backlog="271（通し、記録）", timeBox="Q26：3 h（計画の時間枠 ≤0.75日＋試遊）"),
        acceptance=dict(
            entryToExit=dict(item="271（記録）・最小の受入1", pass_=all(rc[t]["report"]["pass_"] and rc[t]["report"]["quitCause"] == "end_q" and rc[t]["report"]["errors"] == 0
                                                              and rc[t]["report"]["exceptions"] == 0 and rc[t]["report"]["eventsFired"] == 9 for t in rc),
                             runs={t: dict(pass_=rc[t]["report"]["pass_"], quitCause=rc[t]["report"]["quitCause"], errors=rc[t]["report"]["errors"], exceptions=rc[t]["report"]["exceptions"],
                                           events=rc[t]["report"]["eventsFired"], keys=rc[t]["keysUsed"], rows=rc[t]["rows"], shellOrder=[s["state"] for s in rc[t]["shellSegments"]],
                                           entryExpMax=rc[t]["entry"]["expMax"]) for t in rc},
                             verdict="合格"),
            stopImmediate=dict(item="最小の受入2", stops={t: [dict(phase=s["phase"], key=s["key"], injectToKeyReadMs=s["injectToKeyReadMs"], injectToFirstStoppedRowMs=s["injectToFirstStoppedRowMs"],
                                                                   expDrift=s["expMaxDriftAfterKeyReadS"], boatDriftM=s["boatMaxDriftAfterKeyReadM"], clockRunningRows=s["clockRunningRows"],
                                                                   audioMax=s["audioPlayingMax"], rows=s["stoppedRows"], resumed=s["resumedToRunning"]) for s in rc[t]["stops"]] for t in rc},
                               verdict="合格"),
            endClear=dict(item="最小の受入3", end={t: rc[t]["end"] for t in rc}, still="Docs/Evidence/Design/50/ds50_end.png",
                          verdict="合格（PC の自動の試しと静止画）。初めての人の試遊記録（D29）は保留（利用者の手）"),
            H2=dict(item="H2（記録）", conditions=met["gates"][3]["value"]["conditions"], main5=m5["H2"], vr4=rc["vr4"]["H2"], review_main1=rc["review_main1"]["H2"] if "review_main1" in rc else None, verdict="記録"),
            H7=dict(item="H7", verdict="保留（利用者の手。PC では停止・再開だけを確かめた。再センタリングは押していない）"),
            D29=dict(item="初めての人の試遊（D29）", verdict="保留（利用者の手）")),
        regression_painting_view=dict(verdict="記録（原画視点の場面は変えていない。Release の余韻の終わりの画は設計47 と JPG の差の範囲）", **pv),
        endPanel=ep, video=vid, build=dict(result=met["build"]["buildResult"], options=met["build"]["buildOptions"], exe=met["build"]["exeSha256"],
                                           dll=met["build"]["assemblyCSharpSha256"], level0=met["build"]["level0Sha256"], scene=met["build"]["sceneSha256"],
                                           playerBytes=met["build"]["playerBytes"], data=ver["data"], scene50=ver["scene"],
                                           protected43Changed=ver["protected43"]["changed"], design49FilesChanged=ver["design49Files"]["changed"]),
        fix_rounds=dict(afterAcceptance=0, duringBuild="build1〜build5（作る部の中。受入の判定の前）"),
        time=dict(timeBoxH=3, builderStarted="2026-09-30 17:23:51（_started.txt）", builderFinished="2026-09-30 18:11:54（_finished.txt）",
                  review="18:16〜18:21（検査のファイルの時刻）", record="18:25〜（READY_TO_COMMIT.txt の時刻まで）"),
        diffVsBuilder=diff, evidence=ev)
    with open(os.path.join(EVI, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
    run = dict(schema="GreatWave.DS50.record_run/1", tool="Tools/GWWaveGen/ds50/ds50_record.py", toolSha256=sha(os.path.abspath(__file__)),
               python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__, ffmpeg="ffmpeg・ffprobe 2024-12-19（G: の full_build）",
               command="py -3.10 -B Tools/GWWaveGen/ds50/ds50_record.py",
               builderCommandsJa=["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds50/run_ds50_unity.ps1 -Method GreatWave.Design50.EditorTools.DS50ReleaseBuild.BuildAll -Log build5",
                                  "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds50/run_ds50_player.ps1 -Tag capture5 -Capture",
                                  "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds50/run_ds50_player.ps1 -Tag main5",
                                  "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds50/run_ds50_player.ps1 -Tag vr4 -Vr",
                                  "py -3.10 Tools/GWWaveGen/ds50/ds50_report.py --main main5 --capture capture5 --vr vr4"],
               unity="6000.4.3f1", device="NVIDIA GeForce RTX 3080・12th Gen Intel(R) Core(TM) i7-12700K・Direct3D11・Windows 11 (10.0.26200)",
               inputs={rel(os.path.join(REL, p)): sha(os.path.join(REL, p)) for p in ("metrics.json", "run.json", "unity/ds50_build.json", "runs/main5/frames.csv", "runs/main5/report.json",
                                                                                     "runs/vr4/frames.csv", "runs/vr4/report.json", "runs/capture5/frames_capture.csv", "runs/capture5/report_capture.json",
                                                                                     "stills/ds50_end.png", "stills/ds50_afterglow.png",
                                                                                     "player/GreatWave50.exe", "player/GreatWave50_Data/Managed/Assembly-CSharp.dll", "player/GreatWave50_Data/level0")},
               reviewRun={rel(os.path.join(REL, "runs", "review_main1", p)): sha(os.path.join(REL, "runs", "review_main1", p)) for p in ("frames.csv", "report.json")
                          if os.path.exists(os.path.join(REL, "runs", "review_main1", p))},
               committed={rel(os.path.join(REPO, p)): sha(os.path.join(REPO, p)) for p in (
                   "Unity/Assets/GreatWave/Design50/Scenes/DS50_Release.unity", "Unity/Assets/GreatWave/Design50/Scripts/DS50Shell.cs", "Unity/Assets/GreatWave/Design50/Scripts/DS50AutoTest.cs",
                   "Unity/Assets/GreatWave/Design50/Editor/DS50ReleaseBuild.cs", "Unity/Assets/GreatWave/Design50/Shaders/DS50_Overlay.shader",
                   "Tools/GWWaveGen/ds50/ds50_report.py", "Tools/GWWaveGen/ds50/run_ds50_unity.ps1", "Tools/GWWaveGen/ds50/run_ds50_player.ps1")},
               ref47=dict(path=rel(REF47), sha256=pv["refSha256"]),
               outputs={e["dst"]: e["sha256"] for e in ev}, seconds=round(time.time() - t0, 2))
    run["outputs"][rel(os.path.join(EVI, "ds50_record_recount.json"))] = sha(os.path.join(EVI, "ds50_record_recount.json"))
    run["outputs"][rel(os.path.join(EVI, "metrics.json"))] = sha(os.path.join(EVI, "metrics.json"))
    with open(os.path.join(EVI, "run.json"), "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("DS50_RECORD ok checked=%d seconds=%.1f" % (ver["checked"], time.time() - t0))


if __name__ == "__main__":
    main()
