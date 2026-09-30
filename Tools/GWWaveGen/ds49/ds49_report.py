# -*- coding: utf-8 -*-
"""設計49：音の通しの記録（Unity の Play モード、AudioRenderer で書き出した混ぜた 2 ch）から、最小の受入の 2 つを数える。

1) 音と見た目の時刻のずれ ≤ 1 フレーム（時計から駆動）
   a. 出来事の記録：音を始めた段 = 出来事が起きた段か、始めた位置 = 体験の時刻 − 出来事の時刻 か、始まりの遅れ（体験の時刻 − 出来事の時刻）< 1 フレーム。
   b. 混ぜた音そのもの：各フレームの音の塊の頭 = そのフレームの体験の時刻（映像のコマと同じ時刻）として並べ、音ごとに
      「時計から決めた中身」（WAV の標本を 体験の時刻 − 出来事の時刻 で並べたもの）との相互相関の山の遅れを測る。
2) 方向が合う（聞き手で確かめる）：0.2 s の窓ごとに、左・右の各 ch を 4 つの音の中身の和として最小二乗で分け、音ごとの左右の釣り合い
   (右 − 左)/(右 + 左) を、聞き手から見た音の位置の左右（sin 方位角）と比べる。頭の向きの試験（右 90°・左 90°）で風の左右が入れ替わるか。

使い方（リポジトリ根で）：py -3.10 Tools/GWWaveGen/ds49/ds49_report.py
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
import wave

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "ds44"))
from ds44_report import Panel, put  # noqa: E402

OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/49/sound"
RUN = OUT + "/unity/" + (sys.argv[1] if len(sys.argv) > 1 else "main")
TAG = "" if len(sys.argv) <= 1 else "_" + sys.argv[1]
CFG = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design49", "Data", "ds49_sound.json")
AUD = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design49", "Audio")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
PAINT48 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/48/wake/unity/main/painting/painting_end.png"
KEYS = ["rumble", "tstar", "wind", "creak"]
COL = {"rumble": (160, 60, 30), "tstar": (30, 30, 200), "wind": (40, 150, 40), "creak": (20, 120, 200)}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fl(rows, k):
    out = []
    for r in rows:
        try:
            out.append(float(r[k]))
        except (ValueError, KeyError):
            out.append(np.nan)
    return np.array(out)


def read_wav(p):
    with wave.open(p, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float64) / 32767.0, w.getframerate()


def expected_track(tk, clip, anchor, loop, sr):
    """時計から決めた中身：標本 k の時刻 tk[k] の、この音の WAV の位置 (tk − anchor)。区間の外は 0。"""
    pos = np.round(np.nan_to_num(tk - anchor, nan=-1e6) * sr).astype(np.int64)
    n = len(clip)
    e = np.zeros(len(tk))
    if loop:
        m = pos >= 0
        e[m] = clip[pos[m] % n]
    else:
        m = (pos >= 0) & (pos < n)
        e[m] = clip[pos[m]]
    return e


def xcorr_lag(x, e, maxlag):
    """x（混ぜた音）と e（期待の中身）の正規化相互相関。lag > 0 = 音が遅れている（x[k] ≈ e[k − lag]）。"""
    n = len(x)
    N = 1 << int(np.ceil(np.log2(2 * n)))
    X = np.fft.rfft(x, N)
    E = np.fft.rfft(e, N)
    c = np.fft.irfft(X * np.conj(E), N)
    lags = np.arange(-maxlag, maxlag + 1)
    v = np.array([c[l % N] for l in lags])
    v /= (np.sqrt(np.sum(x * x) * np.sum(e * e)) + 1e-18)
    i = int(np.argmax(v))
    # 放物線で標本より細かい山
    sub = 0.0
    if 0 < i < len(v) - 1:
        a, b, cc = v[i - 1], v[i], v[i + 1]
        d = a - 2 * b + cc
        sub = 0.5 * (a - cc) / d if abs(d) > 1e-18 else 0.0
    return lags, v, float(lags[i] + sub), float(v[i])


def main():
    t0 = time.time()
    cfg = json.load(open(CFG, encoding="utf-8"))
    play = json.load(open(RUN + "/ds49_play.json", encoding="utf-8"))
    rows = read_csv(RUN + "/ds49_frames.csv")
    arows = read_csv(RUN + "/ds49_audio_frames.csv")
    sr = int(play["audio"]["sampleRate"])
    ch = int(play["audio"]["channels"])
    mix = np.fromfile(RUN + "/ds49_mix.f32", dtype="<f4").astype(np.float64).reshape(-1, ch)
    FR = 1.0 / 90.0
    tracks = {t["key"]: t for t in cfg["tracks"]}
    clips = {k: read_wav(os.path.join(AUD, tracks[k]["clip"]))[0] for k in KEYS}

    # ---- 音の標本 ↔ 体験の時刻（フレーム i の塊の頭 = そのフレームの体験の時刻）
    a_exp = np.array([float(r["exp"]) if r["exp"] not in ("", "NaN") else np.nan for r in arows])
    a_n = np.array([int(r["samples"]) for r in arows])
    a_cum = np.array([int(r["cum"]) for r in arows])
    assert a_cum[-1] == len(mix), (a_cum[-1], len(mix))
    # 音の流れ：AudioRenderer は 1 フレーム = 1/90 s ぶんの標本を貯め、1024 標本の塊で混ぜる（フレームごとの標本は 0 か 1024）。
    # 標本 k の時刻 = AudioRenderer.Start の時の体験の時刻 e0 + k/sr（貯まった分と混ぜた分の差は 0〜1023 標本。dspTime − 標本数/sr が一定であることも確かめる）
    e0 = float(play["audio"]["startExp"])
    tk = e0 + np.arange(len(mix)) / sr
    a_dsp = np.array([float(r["dsp"]) for r in arows])
    d0 = a_dsp - a_cum / sr
    okc = ~np.isnan(a_exp)
    due = (a_exp[okc] - e0) * sr
    rem = due - a_cum[okc]
    run_ok = np.r_[np.diff(a_exp[okc]) > 1e-9, True]   # 時計が止まった後の行（終わり）を除く
    stream = {"e0": e0, "dspMinusSamplesMin": float(d0.min()), "dspMinusSamplesMax": float(d0.max()),
              "remainderSamplesMin": float(rem[run_ok].min()), "remainderSamplesMax": float(rem[run_ok].max()),
              "blockSizes": sorted(set(int(x) for x in a_n))}
    frame_dt = np.diff(a_exp[~np.isnan(a_exp)])
    ev = {e["id"]: e for e in play["events"]}
    anchors = {k: ev[tracks[k]["anchorEvent"]]["eventT"] for k in KEYS}

    # ---- 1a. 出来事の記録
    starts = []
    for s in play["soundStarts"]:
        e = ev.get(s["event"])
        delay = s["exp"] - s["eventT"]          # 出来事の時刻から、それを最初に見せるフレーム（音を始めた段）までの遅れ
        # 音の中身の標本 0 が鳴る時刻（体験の秒）：予約なら 予約の dspTime + 対応の差、すぐ鳴らしたなら expMix − 始めた位置
        zero = (s["scheduledDsp"] + s["mapOffset"]) if s.get("scheduledDsp") is not None else (s["expMix"] - s["startPosS"])
        starts.append({
            "track": s["track"], "event": s["event"], "eventT": s["eventT"], "startExp": s["exp"], "eventClockT": e["clockT"] if e else None,
            "eventStep": e["step"] if e else None, "startStep": s["step"],
            "sameStep": bool(e and e["step"] == s["step"] and s["eventFiredThisStep"]),
            "firstVisualFrameDelayS": delay, "firstVisualFrameDelayFrames": delay / FR,
            "scheduled": s.get("scheduledDsp") is not None, "contentZeroAtS": zero,
            "contentZeroMinusEventMs": (zero - s["eventT"]) * 1000,
            "audioMinusFirstVisualFrameFrames": (zero - s["exp"]) / FR,
            "stepDtS": s["exp"] - s["prev"],
            "eventInsideStep": s["prev"] < s["eventT"] <= s["exp"],
            "audioMinusFirstVisualFrameInStepDt": (zero - s["exp"]) / (s["exp"] - s["prev"]),
        })
    # 判定：出来事と同じ段で始めた・中身の標本 0 が出来事の時刻に鳴る（±1.5 標本）・出来事はそれを最初に見せるフレームの 1 段の中にある（音はそのフレームより 1 段未満だけ先）
    ok_log = all(x["sameStep"] and abs(x["contentZeroMinusEventMs"]) < 1000.0 / sr * 1.5 and x["eventInsideStep"] and abs(x["audioMinusFirstVisualFrameInStepDt"]) <= 1.0 for x in starts) and len(starts) >= 4

    # ---- 1b. 混ぜた音の相互相関
    exps = fl(rows, "exp")
    mono = mix.mean(axis=1)
    sync = {}
    maxlag = int(0.035 * sr)
    segs = {
        "rumble": (anchors["rumble"] + 3.0, anchors["rumble"] + 11.8),
        "tstar": (anchors["tstar"], anchors["tstar"] + 2.0),
        "wind": (1.0, 15.0),
        "creak": None,
    }
    creak_vol = fl(rows, "creak_vol")
    act = creak_vol > 0.25
    if act.any():
        segs["creak"] = (float(exps[act].min()), float(min(exps[act].max(), anchors["tstar"])))
    xc_curves = {}
    for k in KEYS:
        if segs[k] is None:
            continue
        a, b = segs[k]
        m = (tk >= a) & (tk < b)
        e = expected_track(tk[m], clips[k], anchors[k], tracks[k]["loop"], sr)
        lags, v, lag, peak = xcorr_lag(mono[m], e, maxlag)
        xc_curves[k] = (lags, v)
        # 同じ音の、時計から決めた中身の自己相関の山（この値との比で、山が他の音に埋もれていないかを見る）
        sync[k] = {"segmentS": [a, b], "lagSamples": lag, "lagMs": lag / sr * 1000, "lagFrames": lag / sr / FR, "peakCorr": peak,
                   "withinOneFrame": abs(lag / sr) <= FR}
    ok_mix = all(v["withinOneFrame"] and v["peakCorr"] > 0.2 for v in sync.values()) and len(sync) == 4

    # ---- 2. 方向（左右）
    W = int(0.2 * sr)
    E_all = {k: expected_track(tk, clips[k], anchors[k], tracks[k]["loop"], sr) for k in KEYS}
    fr_exp = exps
    lx = {k: fl(rows, k + "_lx") for k in KEYS}
    lz = {k: fl(rows, k + "_lz") for k in KEYS}
    turn = np.array([float(r["extra"].split("|")[3]) if r["extra"].count("|") >= 3 else 0.0 for r in rows])
    win = []
    for w0 in range(0, len(mix) - W, W):
        sl = slice(w0, w0 + W)
        tc = float(tk[w0 + W // 2])
        if np.isnan(tk[w0]) or np.isnan(tk[w0 + W - 1]):
            continue
        E = np.stack([E_all[k][sl] for k in KEYS], 1)
        act_k = [np.sum(E[:, i] ** 2) > 1e-6 for i in range(4)]
        idx = [i for i in range(4) if act_k[i]]
        if not idx:
            continue
        Es = E[:, idx]
        aL, *_ = np.linalg.lstsq(Es, mix[sl, 0], rcond=None)
        aR, *_ = np.linalg.lstsq(Es, mix[sl, 1], rcond=None)
        tot = np.sum(mix[sl] ** 2) + 1e-18
        fi = int(np.argmin(np.abs(fr_exp - tc)))
        rec = {"t": tc, "turn": float(turn[fi])}
        for j, i in enumerate(idx):
            k = KEYS[i]
            share = (aL[j] ** 2 + aR[j] ** 2) * np.sum(Es[:, j] ** 2) / (2 * tot)
            gl, gr = abs(aL[j]), abs(aR[j])
            pan = (gr - gl) / (gr + gl + 1e-18)
            x, z = lx[k][fi], lz[k][fi]
            saz = x / (np.hypot(x, z) + 1e-9)
            rec[k] = {"pan": float(pan), "sinAz": float(saz), "share": float(share), "gL": float(gl), "gR": float(gr)}
        win.append(rec)
    dirn = {}
    for k in KEYS:
        P = np.array([w[k]["pan"] for w in win if k in w and w[k]["share"] > 0.05])
        S = np.array([w[k]["sinAz"] for w in win if k in w and w[k]["share"] > 0.05])
        el = np.abs(S) > 0.25
        agree = np.sign(P[el]) == np.sign(S[el])
        corr = float(np.corrcoef(P, S)[0, 1]) if len(P) > 3 and np.std(P) > 1e-6 and np.std(S) > 1e-6 else float("nan")
        dirn[k] = {"windows": int(len(P)), "eligible": int(el.sum()), "signAgree": int(agree.sum()),
                   "signAgreeFrac": float(agree.mean()) if el.any() else float("nan"), "corrPanSinAz": corr}
    # 頭の向きの試験：風
    ht = {}
    for lab, yaw in (("right90", 90.0), ("left90", -90.0), ("none", 0.0)):
        sel = [w for w in win if "wind" in w and abs(w["turn"] - yaw) < 1e-3 and w["t"] < 10.0 and w["wind"]["share"] > 0.05]
        if sel:
            ht[lab] = {"windows": len(sel), "panMean": float(np.mean([w["wind"]["pan"] for w in sel])), "sinAzMean": float(np.mean([w["wind"]["sinAz"] for w in sel]))}
    flip = ("right90" in ht and "left90" in ht and np.sign(ht["right90"]["panMean"]) == np.sign(ht["right90"]["sinAzMean"])
            and np.sign(ht["left90"]["panMean"]) == np.sign(ht["left90"]["sinAzMean"]) and np.sign(ht["right90"]["panMean"]) != np.sign(ht["left90"]["panMean"]))
    elig_ok = [k for k in KEYS if dirn[k]["eligible"] >= 5]
    ok_dir = bool(flip) and all(dirn[k]["signAgreeFrac"] >= 0.95 for k in elig_ok) and len(elig_ok) >= 2

    # ---- 音の書き出し（映像のコマ 0 = 最初に描いた体験の時刻）
    caps = [(int(r["cap"]), float(r["exp"])) for r in rows if int(r["cap"]) >= 0]
    exp_c0 = caps[0][1]
    k0 = int(np.nanargmin(np.abs(tk - exp_c0)))
    peak = float(np.max(np.abs(mix)))
    gain = min(1.0, 0.95 / peak) if peak > 0 else 1.0
    pcm = np.clip(np.round(mix[k0:] * gain * 32767), -32768, 32767).astype("<i2")
    wav_path = OUT + "/ds49_mix_from_cap0.wav"
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
    full_wav = OUT + "/ds49_mix_full.wav"
    with wave.open(full_wav, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.clip(np.round(mix * gain * 32767), -32768, 32767).astype("<i2").tobytes())
    vid = OUT + "/ds49_sound_30fps.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", "30", "-i", RUN + "/frames_hmd/h_%05d.jpg", "-i", wav_path,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", vid]
    subprocess.run(cmd, check=True)
    vid720 = OUT + "/ds49_sound_540p_30fps_small.mp4"   # 記録へ写す小さい写し（同じ 960x540、画質を下げる）
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", vid, "-c:v", "libx264", "-crf", "30", "-c:a", "aac", "-b:a", "128k", vid720], check=True)

    # ---- 図
    hs, ws_, as_, es_ = play["handover"]["s"], play["handover"]["waveStart"], play["handover"]["afterglowStart"], play["handover"]["end"]
    ts_ = ws_ + 12.0
    img = np.full((1080, 1920, 3), 245, np.uint8)
    put(img, "DS49 sound: audio vs clock (Unity AudioRenderer mix, 48 kHz stereo, 1 frame = 1/90 s)", (20, 30), 0.7, (255, 255, 255))
    # 上：音の包絡と出来事
    pn = Panel(img, 70, 80, 1820, 260, (0, es_ + 1), (-60, 0), "mix level (dBFS, 50 ms RMS) and per-track volume; grey = events", "dB")
    hop = int(0.05 * sr)
    nwin = len(mono) // hop
    rms = np.sqrt(np.mean(mix[:nwin * hop].reshape(nwin, hop, ch) ** 2, axis=(1, 2)))
    tt = tk[np.arange(nwin) * hop + hop // 2]
    pn.span(0, hs, (224, 240, 232)); pn.span(hs, ws_, (247, 230, 210)); pn.span(ws_, ts_, (210, 230, 247)); pn.span(ts_, as_, (230, 210, 247)); pn.span(as_, es_, (235, 235, 235))
    for e in play["events"]:
        pn.vline(e["eventT"])
    pn.line(tt, 20 * np.log10(rms + 1e-9), (40, 40, 40), 1)
    pn.axes(range(0, int(es_) + 2, 5), [-60, -40, -20, 0])
    pv = Panel(img, 70, 400, 1820, 150, (0, es_ + 1), (0, 1.05), "AudioSource.volume per track (rumble brown, t* red, wind green, creak orange)", "vol")
    for k in KEYS:
        pv.line(exps, fl(rows, k + "_vol"), COL[k], 2)
    pv.axes(range(0, int(es_) + 2, 5), [0, 0.5, 1])
    # 下：相互相関
    x0 = 70
    for i, k in enumerate(KEYS):
        if k not in xc_curves:
            continue
        lags, v = xc_curves[k]
        pc = Panel(img, x0 + i * 460, 640, 420, 300, (-35, 35), (min(-0.1, float(v.min())), max(0.3, float(v.max()) * 1.1)),
                   "%s: xcorr vs clock-driven content" % k, "r")
        pc.span(-1000 / 90, 1000 / 90, (215, 240, 215))
        pc.line(lags / sr * 1000, v, COL[k], 2)
        pc.vline(sync[k]["lagMs"], (0, 0, 200), False)
        pc.axes([-30, -20, -11.1, 0, 11.1, 20, 30], [0, round(float(v.max()), 2)], "%.0f")
        put(img, "lag %.2f ms = %.3f frame, r=%.2f" % (sync[k]["lagMs"], sync[k]["lagFrames"], sync[k]["peakCorr"]), (x0 + i * 460 + 10, 975), 0.5)
    put(img, "green band = +-1 frame (11.1 ms). event log: started in the same clock step as its event; sample 0 of the clip plays at the event time (DSP-scheduled) (%s)" % ("all OK" if ok_log else "NG"), (70, 1030), 0.55)
    cv2.imwrite(OUT + "/fig_ds49_sync.png", img)

    img = np.full((1080, 1920, 3), 245, np.uint8)
    put(img, "DS49 sound: direction at the listener (HMD Camera AudioListener). line = sin(azimuth) of source, dots = measured pan (R-L)/(R+L)", (20, 30), 0.62, (255, 255, 255))
    for i, k in enumerate(KEYS):
        p = Panel(img, 90, 80 + i * 245, 1790, 190, (0, es_ + 1), (-1.05, 1.05), "%s  sign agree %s/%s, corr %.2f" % (
            k, dirn[k]["signAgree"], dirn[k]["eligible"], dirn[k]["corrPanSinAz"]), "pan")
        for tr in cfg["demo"]["headTurns"]:
            p.span(tr["s0"], tr["s1"], (230, 225, 250) if tr["yawDeg"] > 0 else (250, 230, 215))
        p.hline(0, (150, 150, 150), True)
        p.line(exps, lx[k] / (np.hypot(lx[k], lz[k]) + 1e-9), (80, 80, 80), 1)
        tw = np.array([w["t"] for w in win if k in w and w[k]["share"] > 0.05])
        pw = np.array([w[k]["pan"] for w in win if k in w and w[k]["share"] > 0.05])
        if len(tw):
            p.line(tw, pw, COL[k], 1, dots=True)
        p.axes(range(0, int(es_) + 2, 5), [-1, 0, 1])
    put(img, "pink = head yaw +90 deg (right, s 3-5.5), blue = head yaw -90 deg (left, s 5.5-8) (test only). wind pan right90 %.2f / left90 %.2f -> flip %s" % (
        ht.get("right90", {}).get("panMean", float("nan")), ht.get("left90", {}).get("panMean", float("nan")), flip), (90, 1060), 0.55)
    cv2.imwrite(OUT + "/fig_ds49_direction.png", img)

    # スペクトログラム（見る用）
    nfft, hop2 = 4096, 1200
    frames = (len(mono) - nfft) // hop2
    win_ = np.hanning(nfft)
    S = np.array([np.abs(np.fft.rfft(mono[i * hop2:i * hop2 + nfft] * win_)) for i in range(frames)]).T
    f = np.fft.rfftfreq(nfft, 1 / sr)
    fb = np.geomspace(20, 16000, 360)
    Sb = np.array([S[np.searchsorted(f, x)] for x in fb])
    db = 20 * np.log10(Sb + 1e-9)
    db = np.clip((db - (db.max() - 80)) / 80, 0, 1)
    sp = cv2.applyColorMap((db[::-1] * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    sp = cv2.resize(sp, (1820, 480), interpolation=cv2.INTER_AREA)
    img = np.full((620, 1920, 3), 245, np.uint8)
    img[80:560, 70:1890] = sp
    tfr = tk[np.arange(frames) * hop2 + nfft // 2]
    for e in play["events"]:
        okf = ~np.isnan(tfr)
        X = 70 + int(np.interp(e["eventT"], tfr[okf], np.arange(frames)[okf]) / frames * 1820)
        cv2.line(img, (X, 80), (X, 560), (255, 255, 255), 1)
        cv2.putText(img, e["id"], (X + 3, 575 + (15 if e["id"] in ("a_to_d_start", "afterglow_settled", "t_star") else 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (30, 30, 30), 1, cv2.LINE_AA)
    put(img, "DS49 mix spectrogram (20 Hz - 16 kHz log, mono sum). x = experience seconds 0-%.1f" % es_, (20, 40), 0.7)
    cv2.imwrite(OUT + "/fig_ds49_spectrogram.png", img)

    # ---- 原画視点の回帰
    pe = RUN + "/painting/painting_end.png"
    reg = {}
    if os.path.exists(pe) and os.path.exists(PAINT48):
        a = cv2.imread(pe)
        b = cv2.imread(PAINT48)
        d = np.abs(a.astype(np.int32) - b.astype(np.int32)).max(axis=2)
        reg = {"painting_end": pe, "sha256": sha(pe), "ref48": PAINT48, "ref48Sha256": sha(PAINT48), "pixelsDifferent": int((d > 0).sum()), "maxDiff": int(d.max())}

    build = json.load(open(OUT + "/unity/ds49_build.json", encoding="utf-8"))
    prot_now = []
    for line in build["protected"]:
        p, h = line.rsplit(" ", 1)
        fp = os.path.join(REPO, "Unity", p)
        prot_now.append({"path": p, "atBuild": h, "now": sha(fp) if os.path.exists(fp) else "", "same": os.path.exists(fp) and sha(fp) == h})

    metrics = {
        "schema": "GreatWave.DS49.metrics/1",
        "acceptance": {
            "syncWithinOneFrame": {"pass": bool(ok_log and ok_mix), "eventLog": ok_log, "mixXcorr": ok_mix,
                                   "noteJa": "出来事の記録（始めた段と位置）と、混ぜた音の相互相関の山の遅れの両方で ≤ 1 フレーム（1/90 s）"},
            "directionAtListener": {"pass": ok_dir, "headTurnFlip": bool(flip),
                                    "noteJa": "左右がはっきりした窓（|sin 方位角| > 0.25、その音の割合 > 5%）で、測った左右の釣り合いの符号が音の位置の左右と合う割合 ≥ 95%（窓が 5 以上の音）。頭の向きの試験で風の左右が入れ替わる"},
        },
        "stream": stream, "starts": starts, "sync": sync, "direction": dirn, "headTurn": ht,
        "frames": {"count": len(rows), "dtMin": float(frame_dt.min()), "dtMax": float(frame_dt.max()), "audioSamples": int(len(mix)),
                   "samplesPerFrame": [int(a_n[~np.isnan(a_exp)][1:].min()), int(a_n[~np.isnan(a_exp)][1:].max())],
                   "audioSamplesWithClock": int(a_n[~np.isnan(a_exp)].sum()), "clockSpanS": float(np.nanmax(a_exp) - np.nanmin(a_exp)),
                   "firstAudioFrameExp": float(np.nanmin(a_exp)), "samplesBeforeClockReady": int(a_n[np.isnan(a_exp)].sum())},
        "mixPeak": peak, "wavGain": gain,
        "resyncs": {t["key"]: t["resyncs"] for t in play["tracks"]}, "startsCount": {t["key"]: t["starts"] for t in play["tracks"]},
        "errors": {"sound": play["soundErrors"], "flow": play["flowErrors"], "boatWaterFallbacks": play["boatWater"]["fallbacks"]},
        "events": play["events"], "handover": play["handover"],
        "paintingRegression": reg, "protectedUnchanged": all(x["same"] for x in prot_now), "protectedCount": len(prot_now),
        "outputs": {"video": vid, "video720": vid720, "wavFromCap0": wav_path, "wavFull": full_wav},
    }
    with open(OUT + "/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
    run = {
        "schema": "GreatWave.DS49.run/1", "python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__,
        "report": "Tools/GWWaveGen/ds49/ds49_report.py", "reportSha256": sha(os.path.abspath(__file__)),
        "inputs": {p: sha(p) for p in [RUN + "/ds49_play.json", RUN + "/ds49_frames.csv", RUN + "/ds49_audio_frames.csv", RUN + "/ds49_mix.f32", CFG]},
        "outputs": {p: sha(p) for p in [vid, vid720, wav_path, full_wav, OUT + "/fig_ds49_sync.png", OUT + "/fig_ds49_direction.png", OUT + "/fig_ds49_spectrogram.png"]},
        "protected": prot_now, "seconds": time.time() - t0,
    }
    with open(OUT + "/run.json", "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print(json.dumps({"acceptance": metrics["acceptance"], "sync": sync, "direction": dirn, "headTurn": ht, "starts": starts,
                      "frames": metrics["frames"], "resyncs": metrics["resyncs"], "painting": reg, "protectedUnchanged": metrics["protectedUnchanged"]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
