# -*- coding: utf-8 -*-
"""設計49：波・木船・風の音を numpy で合成して WAV（48 kHz・モノラル・16 bit）にする（D27。ダウンロードも録音もしない）。

読むもの：Unity/Assets/GreatWave/Design49/Data/ds49_sound.json の synth（乱数の種と各音の値）。
書くもの：Unity/Assets/GreatWave/Design49/Audio/ の 4 つの WAV と ds49_audio_manifest.json（値・長さ・SHA-256・音量の統計）。
同じ表と同じ種なら、同じバイトの WAV になる（numpy の既定の乱数生成器 PCG64）。

使い方（リポジトリ根で）：py -3.10 Tools/GWWaveGen/ds49/ds49_synth.py
"""
import hashlib
import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CFG = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design49", "Data", "ds49_sound.json")
OUT = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design49", "Audio")


def band_noise(rng, n, sr, lo, hi, edge=0.15, tilt=0.0):
    """白い雑音を FFT で帯に切る（端は cos でなめらかに、tilt は 1/f^tilt の傾き）。平均 0・RMS 1 に正規化。"""
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    g = np.zeros_like(f)
    lo2, hi2 = lo * (1 - edge), hi * (1 + edge)
    m = (f >= lo) & (f <= hi)
    g[m] = 1.0
    a = (f >= lo2) & (f < lo)
    g[a] = 0.5 - 0.5 * np.cos(np.pi * (f[a] - lo2) / max(lo - lo2, 1e-9))
    b = (f > hi) & (f <= hi2)
    g[b] = 0.5 + 0.5 * np.cos(np.pi * (f[b] - hi) / max(hi2 - hi, 1e-9))
    if tilt:
        g *= np.where(f > 0, (np.maximum(f, 1.0) / max(lo, 1.0)) ** (-tilt), 0.0)
    y = np.fft.irfft(X * g, n)
    y -= y.mean()
    return y / (np.sqrt(np.mean(y * y)) + 1e-12)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def norm_peak(y, dbfs):
    return y * (10 ** (dbfs / 20.0) / (np.max(np.abs(y)) + 1e-12))


def fades(y, sr, fin, fout):
    n = len(y)
    a = int(round(fin * sr))
    b = int(round(fout * sr))
    if a > 0:
        y[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if b > 0:
        y[n - b:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(b) / b)
    return y


def rumble(c, sr, rng):
    n = int(round(c["lengthS"] * sr))
    t = np.arange(n) / sr
    T = c["lengthS"]
    u = t / T
    grow = 10 ** ((c["startDb"] * (1 - u ** c["growthExp"])) / 20.0)
    sub = band_noise(rng, n, sr, *c["subHz"], tilt=1.0)
    roar = band_noise(rng, n, sr, *c["roarHz"], tilt=0.5)
    wash = band_noise(rng, n, sr, *c["washHz"], tilt=0.8)
    swell = 1.0 + 0.25 * np.sin(2 * np.pi * c["swellHz"] * t)
    ad = smoothstep((t - c["adS"]) / 1.2)            # a→d の盛り上がり
    jet = smoothstep((t - c["jetS"]) / (T - c["jetS"]))  # 噴流の始まりから t* へ
    y = sub * (1.0 + 0.35 * ad) + roar * (0.25 + 0.55 * u * u + 0.3 * ad) + wash * (0.55 * jet ** 1.5)
    y *= grow * swell
    y = fades(y, sr, c["fadeInS"], c["fadeOutS"])
    return norm_peak(y, c["peakDbfs"])


def tstar(c, sr, rng):
    n = int(round(c["lengthS"] * sr))
    t = np.arange(n) / sr
    y = np.zeros(n)
    for hs, ha in zip(c["hitsS"], c["hitsAmp"]):
        k0 = int(round(hs * sr))
        tt = t[k0:] - t[k0]
        h = np.zeros(n - k0)
        for fz, dz, az in zip(c["hitModesHz"], c["hitModesDecayS"], c["hitModesAmp"]):
            h += az * np.sin(2 * np.pi * fz * tt + 0.3) * np.exp(-tt / dz)
        burst = rng.standard_normal(n - k0) * np.exp(-tt / 0.0015) * 0.8   # 打った瞬間の乾いた雑音（1.5 ms）
        h += burst
        h[0] = max(abs(h[0]), 0.5) * np.sign(h[0] if h[0] != 0 else 1.0)  # 標本 0 から立ち上がる
        y[k0:] += ha * h
    f0, f1 = c["boomHz"]
    fr = f1 + (f0 - f1) * np.exp(-t / 0.25)
    ph = 2 * np.pi * np.cumsum(fr) / sr
    y += c["boomAmp"] * np.sin(ph) * np.exp(-t / c["boomDecayS"]) * (1 - np.exp(-t / 0.004))
    sh = band_noise(rng, n, sr, *c["shimmerHz"])
    y += c["shimmerAmp"] * sh * (1 - np.exp(-t / 0.08)) * np.exp(-t / c["shimmerDecayS"])
    y = fades(y, sr, 0.0, 0.3)
    return norm_peak(y, c["peakDbfs"])


def wind(c, sr, rng):
    L = c["lengthS"]
    xf = c["crossfadeS"]
    n = int(round((L + xf) * sr))
    t = np.arange(n) / sr
    base = band_noise(rng, n, sr, *c["bandHz"], tilt=0.6)
    gust = np.zeros(n)
    for i, g in enumerate(c["gustHz"]):
        gust += np.sin(2 * np.pi * g * t + rng.uniform(0, 2 * np.pi)) / (i + 1)
    gust = 0.4 + 0.6 * (gust - gust.min()) / (gust.max() - gust.min())
    wh = np.zeros(n)
    for fz in c["whistleHz"]:
        wh += band_noise(rng, n, sr, fz - c["whistleWidthHz"], fz + c["whistleWidthHz"], edge=0.02)
    y = base * gust + c["whistleAmp"] * wh * gust ** 3
    # 輪にする：終わりの xf 秒を始めの xf 秒へ等しい力で重ねる
    m = int(round(L * sr))
    k = n - m
    w = np.arange(k) / k
    head = y[:k] * np.sin(0.5 * np.pi * w) + y[m:] * np.cos(0.5 * np.pi * w)
    out = np.concatenate([head, y[k:m]])
    return norm_peak(out, c["peakDbfs"])


def creak(c, sr, rng):
    n = int(round(c["lengthS"] * sr))
    y = np.zeros(n)
    cnt = c["count"]
    slot = n // cnt
    for i in range(cnt):
        d = rng.uniform(*c["durS"])
        nd = int(d * sr)
        k0 = i * slot + int(rng.uniform(0.05, 0.9) * max(slot - nd - int(0.05 * sr), 1))
        if k0 + nd + int(0.1 * sr) >= n:
            continue
        tt = np.arange(nd) / sr
        r0, r1 = rng.uniform(*c["rateHz"]), rng.uniform(*c["rateHz"])
        rate = r0 + (r1 - r0) * tt / d
        phase = np.cumsum(rate) / sr
        pulses = np.zeros(nd)
        idx = np.nonzero(np.diff(np.floor(phase)) > 0)[0]
        pulses[idx] = 1.0 + 0.3 * rng.standard_normal(len(idx))
        env = np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 0.6
        pulses *= env
        # 木の響き（減衰する正弦の和）へ通す
        irn = int(0.12 * sr)
        ti = np.arange(irn) / sr
        ir = np.zeros(irn)
        for fz, dz in zip(c["modesHz"], c["modesDecayS"]):
            ir += np.sin(2 * np.pi * fz * rng.uniform(0.95, 1.05) * ti) * np.exp(-ti / dz)
        s = np.convolve(pulses, ir)[: nd + irn]
        amp = rng.uniform(0.5, 1.0)
        y[k0:k0 + len(s)] += amp * s
    return norm_peak(y, c["peakDbfs"])


def write_wav(path, y, sr):
    q = np.clip(np.round(y * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(q.tobytes())
    return q


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    cfg = json.load(open(CFG, encoding="utf-8"))
    sr = int(cfg["sampleRate"])
    s = cfg["synth"]
    rng = np.random.default_rng(s["seed"])
    os.makedirs(OUT, exist_ok=True)
    made = {}
    for key, fn in (("rumble", rumble), ("tstar", tstar), ("wind", wind), ("creak", creak)):
        y = fn(s[key], sr, rng)
        p = os.path.join(OUT, s[key]["file"])
        q = write_wav(p, y, sr)
        f = q.astype(np.float64) / 32767.0
        made[key] = {
            "file": "Unity/Assets/GreatWave/Design49/Audio/" + s[key]["file"],
            "sha256": sha(p), "bytes": os.path.getsize(p), "samples": int(len(q)), "seconds": len(q) / sr,
            "peakDbfs": float(20 * np.log10(np.max(np.abs(f)) + 1e-12)),
            "rmsDbfs": float(20 * np.log10(np.sqrt(np.mean(f * f)) + 1e-12)),
            "firstNonZeroSample": int(np.argmax(np.abs(q) > 0)),
        }
        print(key, made[key])
    man = {
        "schema": "GreatWave.DS49.audio_manifest/1",
        "noteJa": "ds49_synth.py が ds49_sound.json の synth から作った WAV（48 kHz・モノラル・16 bit）。ダウンロード・録音・外部の素材は使っていない（D27）",
        "config": "Unity/Assets/GreatWave/Design49/Data/ds49_sound.json", "configSha256": sha(CFG),
        "generator": "Tools/GWWaveGen/ds49/ds49_synth.py", "generatorSha256": sha(os.path.abspath(__file__)),
        "numpy": np.__version__, "python": sys.version.split()[0], "sampleRate": sr, "seed": s["seed"], "files": made,
    }
    with open(os.path.join(OUT, "ds49_audio_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
