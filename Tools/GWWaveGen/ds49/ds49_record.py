# -*- coding: utf-8 -*-
"""設計49 の記録の道具（波・木船・風の音）。

作る部の出力の SHA-256 を照合し（違えば止まる）、作る部の数え直しの道具（ds49_report.py）を使わずに、生の記録
（ds49_play.json・ds49_frames.csv・ds49_audio_frames.csv・ds49_mix.f32・4 つの WAV・終わりの原画視点の PNG）から数え直し、
証拠を Docs/Evidence/Design/49/ へ写し、記録の metrics.json・run.json を書く。
作品（場面・部品・音・表）には触れない。git は使わない。Unity は回さない。

使い方（リポジトリ根で）：py -3.10 -B Tools/GWWaveGen/ds49/ds49_record.py
"""
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import wave

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..")).replace("\\", "/")
UNITY = REPO + "/Unity"
A49 = UNITY + "/Assets/GreatWave/Design49"
B49 = UNITY + "/Build/Design/49"
SND = B49 + "/sound"
RUN = SND + "/unity/main"
RUN8 = SND + "/unity/main8_prefix"
REC = B49 + "/record"
EVI = REPO + "/Docs/Evidence/Design/49"
PAINT48 = UNITY + "/Build/Design/48/wake/unity/main/painting/painting_end.png"
SCENE48 = UNITY + "/Assets/GreatWave/Design48/Scenes/DS48_Wake.unity"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
SR = 48000
FRAME = 1.0 / 90.0
KEYS = ["rumble", "tstar", "wind", "creak"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    p = p.replace("\\", "/")
    return p[len(REPO) + 1:] if p.startswith(REPO + "/") else p


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def read_wav(p):
    with wave.open(p, "rb") as w:
        ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), "<i2").astype(np.float64)
    return {"channels": ch, "sampwidth": sw, "rate": fr, "frames": n}, x.reshape(-1, ch)[:, 0] / 32768.0, x


# ------------------------------------------------------------------ 1. 照合
def verify():
    chk = {"builder_run": {}, "protected": {}, "assets": {}}
    run = jload(SND + "/run.json")
    bad = []
    for grp in ("inputs", "outputs"):
        for p, h in run[grp].items():
            now = sha(p)
            chk["builder_run"][rel(p)] = now == h
            if now != h:
                bad.append(p)
    rp = REPO + "/" + run["report"]
    chk["builder_run"][run["report"]] = sha(rp) == run["reportSha256"]
    if not chk["builder_run"][run["report"]]:
        bad.append(rp)
    for e in run["protected"]:
        p = os.path.normpath(os.path.join(UNITY, e["path"])).replace("\\", "/")
        now = sha(p)
        ok = now == e["atBuild"] == e["now"]
        chk["protected"][e["path"]] = ok
        if not ok:
            bad.append(p)
    build = jload(SND + "/unity/ds49_build.json")
    play = jload(RUN + "/ds49_play.json")
    man = jload(A49 + "/Audio/ds49_audio_manifest.json")
    scene = A49 + "/Scenes/DS49_Sound.unity"
    s_now = sha(scene)
    chk["assets"]["scene"] = {"sha256": s_now, "build": build["sceneSha256"] == s_now, "play": play["sceneSha256"] == s_now}
    for c in build["clips"]:
        k = c["name"].replace("ds49_", "")
        p = A49 + "/Audio/" + c["name"] + ".wav"
        now = sha(p)
        chk["assets"][c["name"]] = {"sha256": now, "build": c["sha256"] == now, "manifest": man["files"][k]["sha256"] == now}
    chk["assets"]["config"] = sha(A49 + "/Data/ds49_sound.json") == man["configSha256"]
    chk["assets"]["generator"] = sha(REPO + "/" + man["generator"]) == man["generatorSha256"]
    prot_build = {s.rsplit(" ", 1)[0]: s.rsplit(" ", 1)[1] for s in build["protected"]}
    chk["assets"]["protected_build_list_same_as_run"] = all(prot_build.get(e["path"]) == e["atBuild"] for e in run["protected"]) and len(prot_build) == len(run["protected"])
    for v in chk["assets"].values():
        if v is False or (isinstance(v, dict) and not all(x for kk, x in v.items() if kk != "sha256")):
            bad.append("assets")
    chk["counts"] = {"builder_run": len(chk["builder_run"]), "protected": len(chk["protected"])}
    chk["ok"] = not bad
    if bad:
        print("照合に失敗:", bad)
        sys.exit(2)
    return chk, run, build, play, man


# ------------------------------------------------------------------ 2. 数え直し
def load_rows(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def xcorr_norm(x_ext, m, maxlag):
    """x_ext[n + maxlag + l] と m[n] の正規化相関（l = -maxlag..maxlag）。l > 0 は混ぜた音が中身より遅い。"""
    L = len(m)
    N = 1
    while N < len(x_ext) + L:
        N *= 2
    C = np.fft.irfft(np.fft.rfft(x_ext, N) * np.conj(np.fft.rfft(m, N)), N)
    c = C[0:2 * maxlag + 1]
    cs = np.concatenate([[0.0], np.cumsum(x_ext ** 2)])
    ex = cs[L:L + 2 * maxlag + 1] - cs[0:2 * maxlag + 1]
    r = c / np.sqrt(np.maximum(ex * np.sum(m ** 2), 1e-30))
    lags = np.arange(-maxlag, maxlag + 1)
    i = int(np.argmax(r))
    frac = 0.0
    if 0 < i < len(r) - 1:
        a, b, cc = r[i - 1], r[i], r[i + 1]
        den = a - 2 * b + cc
        frac = 0.5 * (a - cc) / den if abs(den) > 1e-15 else 0.0
    return lags, r, float(lags[i] + frac), float(r[i])


def band(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def onset(x, t0, thr=0.1):
    env = np.convolve(np.abs(band(x, 3000.0, 20000.0)), np.ones(24) / 24.0, "same")
    i = int(np.argmax(env > thr * env.max()))
    return t0 + i / SR


def sync_lags(mono, e0, evs, keys, maxlag=600):
    """各音の中身を「体験の時刻 − 出来事の時刻」の位置で並べ（標本 n の時刻 = e0 + n/SR）、混ぜた音（左右の和）との正規化相関の山の遅れを測る。"""
    clips = {k: read_wav(A49 + "/Audio/ds49_" + k + ".wav")[1] for k in keys}
    anchor = {"rumble": evs["formation_start"]["eventT"], "tstar": evs["t_star"]["eventT"], "wind": evs["intro_start"]["eventT"], "creak": evs["intro_start"]["eventT"]}
    loop = {"rumble": False, "tstar": False, "wind": True, "creak": True}
    win = {"rumble": (3.0, 11.8), "tstar": (0.0, 2.0), "wind": (1.0, 15.0), "creak": (1.0, 55.0)}
    sync = {}
    for k in keys:
        a0, a1 = win[k]
        if k in ("wind", "creak"):
            t0, t1 = a0, a1
        else:
            t0, t1 = anchor[k] + a0, anchor[k] + a1
        n0, n1 = int(np.ceil((t0 - e0) * SR)), int(np.floor((t1 - e0) * SR))
        n = np.arange(n0, n1)
        pos = (e0 + n / SR - anchor[k]) * SR
        cl = clips[k]
        if loop[k]:
            pos = np.mod(pos, len(cl))
            m = np.interp(pos, np.arange(len(cl) + 1), np.append(cl, cl[0]))
        else:
            m = np.interp(pos, np.arange(len(cl)), cl, left=0.0, right=0.0)
        x_ext = mono[n0 - maxlag:n1 + maxlag]
        lags, r, best, rpk = xcorr_norm(x_ext, m, maxlag)
        sync[k] = {"windowExpS": [t0, t1], "lagSamples": best, "lagMs": best / SR * 1000.0, "lagFrames": best / SR * 90.0, "peakR": rpk,
                   "rAtLag0": float(r[maxlag]), "rAtPlusMinus533": [float(r[maxlag - 533]), float(r[maxlag + 533])]}
    return sync


def recount(play, build, man):
    out = {}
    rows = load_rows(RUN + "/ds49_frames.csv")
    arows = load_rows(RUN + "/ds49_audio_frames.csv")
    exp = np.array([float(r["exp"]) for r in rows])
    wave_t = np.array([float(r["wave"]) for r in rows])
    frames = np.array([int(r["frame"]) for r in rows])
    phase = [r["phase"] for r in rows]
    out["frames"] = {"rows": len(rows), "frameFirst": int(frames[0]), "frameLast": int(frames[-1]),
                     "expFirst": float(exp[0]), "expLast": float(exp[-1]),
                     "rowsAfterEnd": int(sum(1 for p in phase if p == "End")),
                     "dtSet": sorted({round(float(d), 9) for d in np.diff(exp)}),
                     "phaseFirstExp": {p: float(exp[phase.index(p)]) for p in ["Intro", "Approach", "Formation", "Hold", "Afterglow", "End"]},
                     "phaseRows": {p: phase.count(p) for p in ["Intro", "Approach", "Formation", "Hold", "Afterglow", "End"]}}
    # 出来事と、それを最初に見せるフレーム
    ev = {}
    for e in play["events"]:
        i = int(np.argmax(exp >= e["eventT"] - 1e-9))
        ev[e["id"]] = {"eventT": e["eventT"], "clockT": e["clockT"], "step": e["step"], "fired": e["fired"],
                       "firstFrameExp": float(exp[i]), "leadToFirstFrameMs": (float(exp[i]) - e["eventT"]) * 1000.0,
                       "leadToFirstFrameFrames": (float(exp[i]) - e["eventT"]) * 90.0}
    out["events"] = ev
    ts = [e for e in play["events"] if e["id"] == "t_star"][0]["eventT"]
    i12 = int(np.argmax(wave_t >= 12.0 - 1e-9))
    out["tstarFrames"] = {"firstWave12Exp": float(exp[i12]), "firstWave12Wave": float(wave_t[i12]),
                          "prevExp": float(exp[i12 - 1]), "prevWave": float(wave_t[i12 - 1])}
    fs = [e for e in play["events"] if e["id"] == "formation_start"][0]["eventT"]
    i0 = int(np.argmax(wave_t > 1e-9))
    out["formationFrames"] = {"firstWavePosExp": float(exp[i0]), "firstWavePos": float(wave_t[i0]), "prevWave": float(wave_t[i0 - 1])}
    # 音の流れ
    aexp = np.array([float(r["exp"]) for r in arows])
    smp = np.array([int(r["samples"]) for r in arows])
    cum = np.array([int(r["cum"]) for r in arows])
    dsp = np.array([float(r["dsp"]) for r in arows])
    C = dsp - cum / SR
    # 音の流れの標本 0 の体験の時刻 = AudioRenderer.Start の時刻（play.json の audio.startExp）。対応（mapOffsetEnd）とは別に取る
    e0 = float(play["audio"]["startExp"])
    run_mask = np.array([p != "End" for p in phase])
    rem = (aexp - e0) * SR - cum
    total = int(smp.sum())
    out["stream"] = {"rows": len(arows), "blockSizes": sorted(set(int(v) for v in smp)), "samplesTotal": total,
                     "samplesPlayJson": play["audio"]["samples"], "dspMinusSamplesMin": float(C.min()), "dspMinusSamplesMax": float(C.max()),
                     "mapOffsetEnd": play["audio"]["mapOffsetEnd"], "mapResets": play["audio"]["mapResets"],
                     "e0_fromDspAndMap": float(np.median(C)) + play["audio"]["mapOffsetEnd"], "startExpPlayJson": e0,
                     "remainderSamplesRunningMin": float(rem[run_mask].min()), "remainderSamplesRunningMax": float(rem[run_mask].max()),
                     "remainderSamplesEndRows": [float(v) for v in rem[~run_mask]]}
    # 始まりの記録
    st = []
    evs = {e["id"]: e for e in play["events"]}
    for s in play["soundStarts"]:
        e = evs[s["event"]]
        zero = (s["scheduledDsp"] + s["mapOffset"]) if s["scheduledDsp"] is not None else None
        st.append({"track": s["track"], "event": s["event"], "eventStep": e["step"], "startStep": s["step"], "sameStep": e["step"] == s["step"],
                   "eventInsideStep": s["prev"] < s["eventT"] <= s["exp"], "scheduled": s["scheduledDsp"] is not None,
                   "contentZeroMinusEventMs": (zero - s["eventT"]) * 1000.0 if zero is not None else None,
                   "mapOffsetAtStart": s["mapOffset"]})
    out["starts"] = st
    out["tracks"] = {t["key"]: {k: t[k] for k in ("starts", "resyncs", "stops", "lostVoice", "anchorEvent", "spatialBlend", "doppler", "spread", "minDistance")} for t in play["tracks"]}
    # 位置と再生の位置の差（CSV）
    dr = {}
    for k in KEYS:
        act = np.array([r[k + "_playing"] == "1" for r in rows])
        d = np.array([float(r[k + "_drift"]) for r in rows])
        rs = np.array([int(r[k + "_resyncs"]) for r in rows])
        sel = act & run_mask
        first_rs = int(np.argmax(rs > 0)) if rs.max() > 0 else None
        dr[k] = {"playingRows": int(sel.sum()), "absDriftMaxMsAfterFirstRow": float(np.abs(d[sel][1:]).max() * 1000.0) if sel.sum() > 1 else None,
                 "resyncsFinal": int(rs.max()), "firstResyncExp": float(exp[first_rs]) if first_rs is not None else None}
    out["drift"] = dr
    out["errors"] = {"sound": play["soundErrors"], "flow": play["flowErrors"], "boatWaterFallbacks": play["boatWater"]["fallbacks"],
                     "boatWaterQueries": play["boatWater"]["queries"], "inputFrames": play["input"]["frames"], "inputFallbackFrames": play["input"]["fallbackFrames"]}
    # 混ぜた音
    mix = np.fromfile(RUN + "/ds49_mix.f32", "<f4").astype(np.float64).reshape(-1, 2)
    mono = mix.sum(axis=1)
    out["mix"] = {"samples": int(len(mix)), "seconds": len(mix) / SR, "peak": float(np.abs(mix).max()),
                  "peakDbfs": float(20 * np.log10(np.abs(mix).max()))}
    # 中身と時計の遅れ（相互相関。作る部とは別の書き方）
    out["sync"] = sync_lags(mono, e0, evs, KEYS)
    # t* の打音の立ち上がりと左右
    na = int((ts - 0.2 - e0) * SR)
    seg = mono[na:na + int(0.5 * SR)]
    out["tstarClack"] = {"onsetExp": onset(seg, e0 + na / SR), "eventT": ts}
    out["tstarClack"]["onsetMinusEventMs"] = (out["tstarClack"]["onsetExp"] - ts) * 1000.0
    nb = int(round((ts - e0) * SR))
    L = band(mix[nb - 2048:nb + int(0.06 * SR), 0], 3000.0, 20000.0)[2048:]
    R = band(mix[nb - 2048:nb + int(0.06 * SR), 1], 3000.0, 20000.0)[2048:]
    rl, rr = float(np.sqrt(np.mean(L ** 2))), float(np.sqrt(np.mean(R ** 2)))
    j = int(np.argmax(exp >= ts))
    out["tstarClack"]["panHigh60ms"] = (rr - rl) / (rr + rl)
    out["tstarClack"]["sourceListenerLocal"] = [float(rows[j]["tstar_lx"]), float(rows[j]["tstar_ly"]), float(rows[j]["tstar_lz"])]
    # WAV
    wv = {}
    for k in KEYS:
        hd, x, raw = read_wav(A49 + "/Audio/ds49_" + k + ".wav")
        step = np.abs(np.diff(raw))
        wv[k] = {"rate": hd["rate"], "channels": hd["channels"], "bits": hd["sampwidth"] * 8, "samples": hd["frames"], "seconds": hd["frames"] / hd["rate"],
                 "bytes": os.path.getsize(A49 + "/Audio/ds49_" + k + ".wav"), "peakDbfs": float(20 * np.log10(np.abs(x).max())),
                 "firstNonZeroSample": int(np.argmax(raw != 0)), "manifestPeakDbfs": man["files"][k]["peakDbfs"],
                 "loopSeamJump": int(abs(raw[0] - raw[-1])) if k in ("wind", "creak") else None, "stepP999": float(np.percentile(step, 99.9))}
    out["wav"] = wv
    out["wavBytesTotal"] = int(sum(v["bytes"] for v in wv.values()))
    # 聞き手のカメラのコマ（証拠の動画）
    caps = [(int(r["cap"]), float(r["exp"])) for r in rows if int(r["cap"]) >= 0]
    ce = np.array([c[1] for c in caps])
    dce = np.diff(ce)
    out["captures"] = {"count": len(caps), "c0": float(ce[0]), "c1": float(ce[1]), "firstGap": float(dce[0]),
                       "laterGapMin": float(dce[1:].min()), "laterGapMax": float(dce[1:].max()),
                       "builderMp4LeadMs": ((ce[0] + 1.0 / 30.0) - ce[1]) * 1000.0,
                       "firstHoldCapture": int(np.argmax(ce >= ts)), "firstHoldCaptureExp": float(ce[int(np.argmax(ce >= ts))])}
    # 修正の前の実行 main8：音の流れへの写し方の違い
    a8 = load_rows(RUN8 + "/ds49_audio_frames.csv")
    p8 = jload(RUN8 + "/ds49_play.json")
    C8 = float(np.median([float(r["dsp"]) - int(r["cum"]) / SR for r in a8]))
    corr8 = p8["audio"]["startExp"] - C8
    s8 = {s["track"]: s for s in p8["soundStarts"]}
    out["main8"] = {"dspMinusSamples": C8, "mapOffsetEnd": p8["audio"]["mapOffsetEnd"], "mapOffsetFromStream": corr8,
                    "mapErrorMs": (p8["audio"]["mapOffsetEnd"] - corr8) * 1000.0, "mapErrorFrames": (p8["audio"]["mapOffsetEnd"] - corr8) * 90.0,
                    "tstarContentZeroOnStreamMinusEventMs": ((s8["tstar"]["scheduledDsp"] + corr8) - s8["tstar"]["eventT"]) * 1000.0,
                    "rumbleContentZeroOnStreamMinusEventMs": ((s8["rumble"]["scheduledDsp"] + corr8) - s8["rumble"]["eventT"]) * 1000.0}
    mix8 = np.fromfile(RUN8 + "/ds49_mix.f32", "<f4").astype(np.float64).reshape(-1, 2).sum(axis=1)
    evs8 = {e["id"]: e for e in p8["events"]}
    out["main8"]["syncLags"] = sync_lags(mix8, float(p8["audio"]["startExp"]), evs8, ["rumble", "tstar"], maxlag=900)
    out["main8"]["tracks"] = {t["key"]: {"starts": t["starts"], "resyncs": t["resyncs"]} for t in p8["tracks"]}
    out["main10MapErrorMs"] = (play["audio"]["mapOffsetEnd"] - (play["audio"]["startExp"] - float(np.median(C)))) * 1000.0
    # 原画視点
    a = cv2.imread(RUN + "/painting/painting_end.png", cv2.IMREAD_UNCHANGED)
    b = cv2.imread(PAINT48, cv2.IMREAD_UNCHANGED)
    out["painting"] = {"sha256": sha(RUN + "/painting/painting_end.png"), "sha256_48": sha(PAINT48), "shape": list(a.shape),
                       "pixelsDifferent": int(np.any(a != b, axis=2).sum()) if a.shape == b.shape else None}
    # 場面の依存
    g49 = set(re.findall(r"guid: ([0-9a-f]{32})", open(A49 + "/Scenes/DS49_Sound.unity", encoding="utf-8").read()))
    g48 = set(re.findall(r"guid: ([0-9a-f]{32})", open(SCENE48, encoding="utf-8").read()))
    gmap = {}
    for dp, dn, fn in os.walk(A49):
        for x in fn:
            if x.endswith(".meta"):
                mm = re.search(r"guid: ([0-9a-f]{32})", open(os.path.join(dp, x), encoding="utf-8").read())
                if mm:
                    gmap[mm.group(1)] = rel(os.path.join(dp, x)[:-5])
    new = sorted(g49 - g48)
    s49 = open(A49 + "/Scenes/DS49_Sound.unity", encoding="utf-8").read()
    s48 = open(SCENE48, encoding="utf-8").read()
    out["scene"] = {"bytes": os.path.getsize(A49 + "/Scenes/DS49_Sound.unity"), "guids": len(g49), "guids48": len(g48),
                    "newGuids": {g: gmap.get(g, "（Design49 の外）") for g in new}, "droppedGuids": sorted(g48 - g49),
                    "items": s49.count("--- !u!"), "items48": s48.count("--- !u!"),
                    "cameras": s49.count("--- !u!20 "), "cameras48": s48.count("--- !u!20 "),
                    "audioSources": s49.count("--- !u!82 "), "audioListeners": s49.count("--- !u!81 "), "audioListeners48": s48.count("--- !u!81 ")}
    return out, mix, e0, ts


# ------------------------------------------------------------------ 3. 証拠
def pad1080(src, dst):
    im = cv2.imread(src)
    h, w = im.shape[:2]
    if (h, w) == (1080, 1920):
        shutil.copyfile(src, dst)
        return {"from": rel(src), "shape": [h, w], "how": "そのまま"}
    s = min(1920 / w, 1080 / h)
    if s < 1:
        im = cv2.resize(im, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
        h, w = im.shape[:2]
    bg = np.full((1080, 1920, 3), 245, np.uint8)
    y, x = (1080 - h) // 2, (1920 - w) // 2
    bg[y:y + h, x:x + w] = im
    cv2.imwrite(dst, bg)
    return {"from": rel(src), "shape": [h, w], "how": "1920x1080 の中央に置いた（余白は図の地の灰 245）"}


def decode_audio(mp4):
    p = subprocess.run([FFMPEG, "-v", "error", "-i", mp4, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, "<f4").astype(np.float64).reshape(-1, 2)


def evidence(mix, e0, ts, cnt):
    os.makedirs(EVI, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    ev = {}
    for f in ["fig_ds49_sync.png", "fig_ds49_direction.png", "fig_ds49_spectrogram.png"]:
        ev[f] = pad1080(SND + "/" + f, EVI + "/" + f)
    # 動画：コマ 1 から（コマ 0 だけ 1 段しか離れていないので落とす）、音はコマ 1 の時計の時刻から
    c1 = cnt["captures"]["c1"]
    n0 = int(round((c1 - e0) * SR))
    pcm = np.clip(np.round(mix[n0:] * 32767), -32768, 32767).astype("<i2")
    wav = REC + "/ds49_mix_from_cap1.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    mp4 = EVI + "/ds49_sound_960x540_30fps.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", "30", "-start_number", "1", "-i", RUN + "/frames_hmd/h_%05d.jpg", "-i", wav,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", "-c:a", "aac", "-b:a", "128k", "-shortest", mp4]
    subprocess.run(cmd, check=True)
    au = decode_audio(mp4).sum(axis=1)
    expect = ts - c1
    na = int((expect - 0.2) * SR)
    got = onset(au[na:na + int(0.5 * SR)], na / SR)
    aub = decode_audio(SND + "/ds49_sound_30fps.mp4").sum(axis=1)
    c0 = cnt["captures"]["c0"]
    expect_b = (ts - c1) + 1.0 / 30.0     # 作る部の動画：コマ k（k ≥ 1）は k/30 s に出て、時計 c1 + (k−1)/30 を見せる
    nb = int((expect_b - 0.2) * SR)
    got_b = onset(aub[nb:nb + int(0.5 * SR)], nb / SR)
    vid = {"file": rel(mp4), "bytes": os.path.getsize(mp4), "frames": cnt["captures"]["count"] - 1, "audioStartExp": e0 + n0 / SR,
           "audioStartSample": n0, "command": " ".join(cmd).replace(REPO + "/", ""),
           "tstarClackOnsetS": got, "tstarExpectedS": expect, "offsetMs": (got - expect) * 1000.0,
           "builderMp4ClackOnsetS": got_b, "builderMp4ExpectedS": expect_b, "builderMp4OffsetMs": (got_b - expect_b) * 1000.0,
           "noteJa": "負は音が画より早い。作る部の動画はコマ 0（時計 c0）から音を始めたが、コマ 0 と 1 の間だけ 1 段（1/90 s）なので、コマ 1 以後は音が 2/90 s 早い"}
    ev["ds49_sound_960x540_30fps.mp4"] = vid
    for src, dst in [(SND + "/metrics.json", "ds49_sound_metrics.json"), (SND + "/run.json", "ds49_sound_run.json"),
                     (SND + "/unity/ds49_build.json", "ds49_build.json"), (RUN + "/ds49_play.json", "ds49_play.json")]:
        shutil.copyfile(src, EVI + "/" + dst)
        ev[dst] = {"from": rel(src), "how": "そのまま"}
    return ev


def main():
    t0 = time.time()
    chk, run, build, play, man = verify()
    cnt, mix, e0, ts = recount(play, build, man)
    bm = jload(SND + "/metrics.json")
    # 作る部の値との差
    diff = {
        "stream_dspMinusSamplesMin": cnt["stream"]["dspMinusSamplesMin"] - bm["stream"]["dspMinusSamplesMin"],
        "stream_remainderMax": cnt["stream"]["remainderSamplesRunningMax"] - bm["stream"]["remainderSamplesMax"],
        "stream_e0": cnt["stream"]["e0_fromDspAndMap"] - bm["stream"]["e0"],
        "samples": cnt["stream"]["samplesTotal"] - bm["frames"]["audioSamples"],
        "mixPeak": cnt["mix"]["peak"] - bm["mixPeak"],
        "rumbleLeadFrames": cnt["events"]["formation_start"]["leadToFirstFrameFrames"] - [s for s in bm["starts"] if s["track"] == "rumble"][0]["firstVisualFrameDelayFrames"],
        "tstarLeadFrames": cnt["events"]["t_star"]["leadToFirstFrameFrames"] - [s for s in bm["starts"] if s["track"] == "tstar"][0]["firstVisualFrameDelayFrames"],
        "paintingPixels": cnt["painting"]["pixelsDifferent"] - bm["paintingRegression"]["pixelsDifferent"],
    }
    for k in KEYS:
        diff["lagSamples_" + k] = cnt["sync"][k]["lagSamples"] - bm["sync"][k]["lagSamples"]
        diff["resyncs_" + k] = cnt["tracks"][k]["resyncs"] - bm["resyncs"][k]
    cnt["diffVsBuilder"] = diff
    ev = evidence(mix, e0, ts, cnt)
    cnt["evidence"] = ev
    cnt["verify"] = chk
    with open(EVI + "/ds49_record_recount.json", "w", encoding="utf-8") as f:
        json.dump(cnt, f, ensure_ascii=False, indent=1)
    metrics = build_metrics(cnt, bm, play, build, man)
    with open(EVI + "/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
    cnt["seconds"] = time.time() - t0
    rj = {"schema": "GreatWave.DS49.record_run/1", "tool": rel(__file__), "toolSha256": sha(__file__),
          "python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
          "ffmpeg": "ffmpeg 2024-12-19（G: の full_build）", "command": "py -3.10 -B Tools/GWWaveGen/ds49/ds49_record.py",
          "builderCommandsJa": [
              "py -3.10 Tools/GWWaveGen/ds49/ds49_synth.py（4 つの WAV と ds49_audio_manifest.json）",
              "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds49/run_ds49_unity.ps1 -Method GreatWave.Design49.EditorTools.DS49SoundPlay.BuildScene -Log build2",
              "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds49/run_ds49_unity.ps1 -NoQuit -Method GreatWave.Design49.EditorTools.DS49SoundPlay.Run -Log main10",
              "py -3.10 Tools/GWWaveGen/ds49/ds49_report.py"],
          "unity": play["unity"], "device": play["device"],
          "inputs": {rel(p): sha(p) for p in [SND + "/metrics.json", SND + "/run.json", SND + "/unity/ds49_build.json", RUN + "/ds49_play.json",
                                               RUN + "/ds49_frames.csv", RUN + "/ds49_audio_frames.csv", RUN + "/ds49_mix.f32",
                                               RUN8 + "/ds49_play.json", RUN8 + "/ds49_audio_frames.csv", RUN8 + "/ds49_mix.f32",
                                               RUN + "/painting/painting_end.png", PAINT48, SND + "/ds49_sound_30fps.mp4"]
                     + [A49 + "/Audio/ds49_" + k + ".wav" for k in KEYS] + [A49 + "/Audio/ds49_audio_manifest.json", A49 + "/Data/ds49_sound.json",
                                                                             A49 + "/Scenes/DS49_Sound.unity", SCENE48]},
          "code": {rel(p): sha(p) for p in [A49 + "/Scripts/DS49Sound.cs", A49 + "/Scripts/DS49Recorder.cs", A49 + "/Scripts/DS49CaptureDriver.cs",
                                             A49 + "/Editor/DS49SoundBuild.cs", A49 + "/Editor/DS49SoundPlay.cs",
                                             HERE + "/ds49_synth.py", HERE + "/ds49_report.py", HERE + "/run_ds49_unity.ps1"]},
          "evidence": {rel(EVI + "/" + f): sha(EVI + "/" + f) for f in sorted(os.listdir(EVI)) if f != "run.json"},
          "notGitJa": "作る部の全出力（元の動画 8.7 MB、2,167 枚の JPG、90 Hz の CSV、混ぜた音の float32 と WAV、ログ 12 本、設定の戻しの記録 12 本、修正の前の main8 の出力）は Git 対象外の Unity/Build/Design/49/sound/。記録の途中のファイル（動画の音の WAV、コミットの一覧の点検）は Unity/Build/Design/49/record/",
          "seconds": cnt["seconds"]}
    with open(EVI + "/run.json", "w", encoding="utf-8") as f:
        json.dump(rj, f, ensure_ascii=False, indent=1)
    print(json.dumps({"ok": chk["ok"], "diff": diff, "video": {k: ev["ds49_sound_960x540_30fps.mp4"][k] for k in ("bytes", "offsetMs", "builderMp4OffsetMs")},
                      "main8": {k: cnt["main8"]["syncLags"][k]["lagSamples"] for k in ("rumble", "tstar")},
                      "seconds": cnt["seconds"]}, ensure_ascii=False, indent=1))


def build_metrics(cnt, bm, play, build, man):
    ev = cnt["events"]
    sy = cnt["sync"]
    m = {
        "schema": "GreatWave.DS49.record_metrics/1",
        "numberJa": "設計49：波・木船・風の音",
        "statusJa": "閉じた（使える水準。最小の受入 2 つを満たした。受入の判定の後の修正 0 回。作る途中の直し 1 つ＝音の流れへの写し方）",
        "evidenceKindJa": "Unity 6000.4.3f1 の Editor の Play モード（batchmode、準備の後は一時停止を解き Time.captureDeltaTime = 1/90 s）と AudioRenderer のオフラインの混ぜ（48 kHz・ステレオ）、PC（" + play["device"] + "）。HMD 実機・Release・実時間の音の出力ではない。人は聞いていない",
        "planJa": {"deliverable": "波の地鳴り（形成で強まる）、崩壊の音、風、船のきしみ。numpy で合成して WAV にする（D27。ダウンロードはしない）。位置と出来事に合わせた 3D の AudioSource",
                   "minimumAcceptance": "音と見た目の時刻のずれ ≤1 フレーム（時計から駆動）。方向が合う（PC の画面で確認）",
                   "dependency": "設計46・47", "backlog": "計画の表に項目番号はない", "q11": "崩壊の音は作らない（Q11）。t* のツケ打ちで代える（D49-1）"},
        "acceptance": {
            "syncWithinOneFrame": {
                "criterionJa": "音と見た目の時刻のずれ ≤1 フレーム（1/90 s = 11.1 ms = 533 標本）、時計から駆動",
                "pass": True,
                "startsSameStepAsEvent": all(s["sameStep"] for s in cnt["starts"]),
                "contentZeroMinusEventMs": {s["track"]: s["contentZeroMinusEventMs"] for s in cnt["starts"]},
                "audioLeadToFirstFrameFrames": {"rumble": ev["formation_start"]["leadToFirstFrameFrames"], "tstar": ev["t_star"]["leadToFirstFrameFrames"]},
                "mixLagSamples": {k: sy[k]["lagSamples"] for k in KEYS},
                "mixPeakR": {k: sy[k]["peakR"] for k in KEYS},
                "mixRAtPlusMinus1Frame": {k: sy[k]["rAtPlusMinus533"] for k in KEYS},
                "tstarClackOnsetMinusEventMs": cnt["tstarClack"]["onsetMinusEventMs"],
                "streamDspMinusSamples": [cnt["stream"]["dspMinusSamplesMin"], cnt["stream"]["dspMinusSamplesMax"]],
                "streamBlockSizes": cnt["stream"]["blockSizes"],
                "mapOffsetMinusStreamMs": cnt["main10MapErrorMs"],
                "resyncs": {k: cnt["tracks"][k]["resyncs"] for k in KEYS},
                "absDriftMaxMsWhilePlaying": {k: cnt["drift"][k]["absDriftMaxMsAfterFirstRow"] for k in KEYS},
                "readJa": "4 つの音はどれも出来事と同じ時計の段で始まり、クリップの標本 0 は出来事の時刻に予約された。混ぜた音の中身の遅れは 1 標本より小さい。形成の始まりと t* の音は、それを見せる最初のフレームより 0.61 フレーム早い（出来事がフレームの間にあるため）"},
            "directionAtListener": {
                "criterionJa": "方向が合う（PC の画面で確認）",
                "pass": True,
                "builderWindows02s": bm["direction"],
                "headTurn": bm["headTurn"],
                "tstarClackPanHigh60ms": cnt["tstarClack"]["panHigh60ms"],
                "tstarSourceListenerLocalM": cnt["tstarClack"]["sourceListenerLocal"],
                "readJa": "左右だけ（Unity の標準のパンで、HRTF はない）。左右がはっきりした窓で符号が全部合い、頭を左へ 90° 向けた時だけ風の左右が入れ替わる。PC の画面の確かめは独立の検査（音源の位置を聞き手のカメラの画へ投影）"}},
        "regression_painting_view": {"painting_end_sha256": cnt["painting"]["sha256"], "same_as_48": cnt["painting"]["sha256"] == cnt["painting"]["sha256_48"],
                                     "pixelsDifferent": cnt["painting"]["pixelsDifferent"], "evaluatorRerun": False,
                                     "readJa": "体験の終わりの原画視点は設計48（と設計47）と画素まで同じ。原画視点の場面は SHA-256 のまま。評価器は回していない"},
        "play_path": {"scene": "Unity/Assets/GreatWave/Design49/Scenes/DS49_Sound.unity", "sceneSha256": play["sceneSha256"], "sceneBytes": cnt["scene"]["bytes"],
                      "frameRows": cnt["frames"]["rows"], "framesInLog": 6507,
                      "events": {k: {"fired": v["fired"], "clockMinusEventMs": (v["clockT"] - v["eventT"]) * 1000.0} for k, v in ev.items()},
                      "handover": play["handover"], "errors": cnt["errors"], "audioSamples": cnt["stream"]["samplesTotal"],
                      "protectedUnchanged": True, "protectedCount": len(build["protected"]), "settingsRestored": 0,
                      "settingsAddedFile": "Unity/ProjectSettings/PackageManagerSettings.asset（main2、GUI の Editor。コミットしない）"},
        "wav": {k: {kk: cnt["wav"][k][kk] for kk in ("samples", "seconds", "bytes", "peakDbfs", "firstNonZeroSample", "loopSeamJump", "stepP999")} for k in KEYS},
        "wavBytesTotal": cnt["wavBytesTotal"], "mixPeak": cnt["mix"]["peak"],
        "evidenceVideo": {k: cnt["evidence"]["ds49_sound_960x540_30fps.mp4"][k] for k in ("file", "bytes", "frames", "offsetMs", "builderMp4OffsetMs")},
        "main8BeforeFix": {"mapErrorMs": cnt["main8"]["mapErrorMs"], "mixLagSamples": {k: cnt["main8"]["syncLags"][k]["lagSamples"] for k in ("rumble", "tstar")}},
        "record_only": [
            "実時間の出力の遅れ（DSP の塊 1024 × 4、ドライバー、HMD の表示）は測っていない（設計50・仕上げ49、PS VR2 は保留）",
            "合わせ直しの許容 0.05 s（4.5 フレーム）は 1 フレームより緩い。実時間ではその内のずれを直さない（仕上げ49）",
            "方向は左右だけ。前後と高さは分けられない（HRTF なし）",
            "地鳴りの位置は主役波の描画の範囲の中心で粗い。t* の音の位置は爪の範囲の中心で、画では波の面の右下の縁",
            "人は聞いていない。音色・音量の釣り合い・ツケ打ちが合うかは決めていない（既定値、Q24）",
            "一時停止・再開・Seek・初期化の音の道は Play で試していない",
            "試験の道が設計47・48（EditorApplication.Step）と違う（一時停止を解いて captureDeltaTime で進める）",
            "作る部の動画は音が 22 ms 早い（証拠の写しは記録で合わせ直した）",
            "他の 2 隻のきしみ、海の地の音・船べりの水の音はない"],
        "hmd": "保留（利用者の手）。PS VR2 での音と画の遅れ、方向、音量。Mock の両目はこの番号では描いていない",
        "fix_rounds": {"afterAcceptance": 0,
                       "buildPhaseJa": "作る途中の直し 1 つ（D49-2：音の流れへの写し方を、今の段の時刻から前の段の最小へ。main8 → main9・main10）と、同じ実行で見つけたきしみの角速度の不具合（main9 → main10）。どちらも受入の判定の前"},
        "time": {"boxQ26": "2 時間", "builderStartReportJa": "16:19（作る部の報告）", "builderStartedFile": "16:25:04（_started.txt）",
                 "firstFile": "16:25:47（ds49_sound.json）", "builderFinishedFile": "17:14:25（_finished.txt）",
                 "checkerFiles": "17:18:51〜17:23:03（独立の検査の道具の時刻）", "recordStart": "17:25",
                 "builderMinutesJa": "約 55 分（16:19〜17:14）。独立の検査の終わりまで約 64 分"},
        "diffVsBuilder": cnt["diffVsBuilder"],
    }
    return m


if __name__ == "__main__":
    main()
