# -*- coding: utf-8 -*-
"""R4b 確かめ（2026-10-11）：記録の読み込みと線形の値。g_analyze.py・g_shape.py・check/R4 の道具は使わない（自前で書いた）。
記録の形は npz の中身（frames・eta・x・z・sdf・meta）から読んだ。t = (コマ − 1)/24。
"""
import os, glob, json, math
import numpy as np

ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs"
PLAN = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/plan/plan_numbers.json"
OUT = os.path.dirname(os.path.abspath(__file__))
G = 9.80665
FPS = 24.0


def plan():
    with open(PLAN, encoding="utf-8") as fh:
        return json.load(fh)


def cfg(rid):
    with open(os.path.join(ROOT, rid, "cfg.json"), encoding="utf-8") as fh:
        return json.load(fh)


def wavenumber(om, h):
    """ω² = g k tanh(kh) をニュートン法で（配列）。"""
    om = np.asarray(om, float)
    k = np.where(om > 0, om * om / G / np.sqrt(np.tanh(np.maximum(om * om / G * h, 1e-12))), 0.0)
    for _ in range(80):
        th = np.tanh(k * h)
        f = G * k * th - om * om
        d = G * th + G * k * h / np.cosh(np.minimum(k * h, 300)) ** 2
        k = np.where(om > 0, k - f / np.where(d > 0, d, 1), 0.0)
    return k


def group_speed(om, h):
    k = wavenumber(om, h)
    with np.errstate(all="ignore"):
        c = np.where(k > 0, om / np.where(k > 0, k, 1), math.sqrt(G * h))
        n = np.where(k * h > 1e-8, 0.5 + k * h / np.sinh(np.minimum(2 * k * h, 600)), 1.0)
    return c * n


def components(P):
    lab, full = P["lab"], P["full"]
    f = np.linspace(lab["fc"] * (1 - lab["dff"] / 2), lab["fc"] * (1 + lab["dff"] / 2), lab["N"]) / math.sqrt(full["lam"])
    om = 2 * np.pi * f
    k = wavenumber(om, full["h"])
    a = lab["S"] / k.sum() * np.ones_like(f)
    return dict(f=f, om=om, k=k, a=a, h=full["h"], xb=full["xb"], tb=full["tb"], Tc=full["Tc"], Lc=full["Lc"],
                ramp=P["tank"]["ramp"], df=f[1] - f[0])


def hf(rid):
    """一番上の水面の高さ。重なったコマは後の起動（始めのコマが大きい方）を使い、重なりが同じかも数える。"""
    files = glob.glob(os.path.join(ROOT, rid, "hf_c*.npz"))
    files.sort(key=lambda p: int(os.path.basename(p)[4:8]))
    pick = {}
    data = []
    for j, p in enumerate(files):
        d = np.load(p)
        data.append(d)
        for i, fr in enumerate(d["frames"]):
            pick[int(fr)] = (j, i)
    frs = np.array(sorted(pick))
    x = data[-1]["x"]; z = data[-1]["z"]
    eta = np.empty((len(frs), len(z), len(x)), np.float32)
    ssn = np.zeros(len(frs), int); wall = np.zeros(len(frs))
    cache = {}
    for n, fr in enumerate(frs):
        j, i = pick[int(fr)]
        if j not in cache:
            cache.clear()
            d = data[j]
            cache[j] = (d["eta"], d["ss_n"], d["wall"])
        e, s, w = cache[j]
        eta[n] = e[i]; ssn[n] = s[i]; wall[n] = w[i]
    # 重なりの確かめ（同じコマが 2 つのファイルにある時、値が同じか）
    seen = {}
    ndup = 0; ndiff = 0
    for j, d in enumerate(data):
        for i, fr in enumerate(d["frames"]):
            fr = int(fr)
            if fr in seen:
                ndup += 1
                j0, i0 = seen[fr]
                if not np.array_equal(data[j0]["eta"][i0], d["eta"][i], equal_nan=True):
                    ndiff += 1
            seen[fr] = (j, i)
    return dict(frames=frs, t=(frs - 1) / FPS, x=x, z=z, eta=eta, ss_n=ssn, wall=wall, nfiles=len(files), ndup=ndup, ndiff=ndiff)


def still(D, xp, node="mid"):
    m = (D["t"] >= 0.5) & (D["t"] <= 2.0)
    xm = (D["x"] >= xp) & (D["x"] <= xp + 930.0)
    if node == "mid":
        e = D["eta"][m][:, D["eta"].shape[1] // 2, :][:, xm]
    else:
        e = D["eta"][m][:, 1:-1, :][:, :, xm].mean(1)
    return float(np.nanmedian(e))


def gauge_series(D, xs, off):
    """内側 3 節の平均を x で線形に補間。"""
    e = np.nanmean(D["eta"][:, 1:-1, :], axis=1) - off
    x = D["x"]
    i = int(np.searchsorted(x, xs)) - 1
    w = (xs - x[i]) / (x[i + 1] - x[i])
    return (1 - w) * e[:, i] + w * e[:, i + 1]


def ramp(t, R):
    c = np.clip(t / R, 0.0, 1.0)
    return 0.5 * (1 - np.cos(np.pi * c))


def linear_series(C, x_rel, t, npad=1 << 19):
    """造波板の位置の目標（始めのなだらかさ込み）を周波数ごとに線形の分散で x_rel まで進め、t の窓で切る。"""
    th = C["k"][None, :] * (0.0 - C["xb"]) - C["om"][None, :] * (t[:, None] - C["tb"])
    e0 = ramp(t, C["ramp"]) * (C["a"][None, :] * np.cos(th)).sum(1)
    dt = t[1] - t[0]
    F = np.fft.rfft(e0, npad)
    fr = np.fft.rfftfreq(npad, dt)
    kk = wavenumber(2 * np.pi * fr, C["h"])
    return np.fft.irfft(F * np.exp(-1j * kk * x_rel), npad)[:len(t)]


def sec_frames(rid):
    """断面の水面の場：コマ → (ファイル, 番号)。後の起動を使う。"""
    files = glob.glob(os.path.join(ROOT, rid, "sec_c*_b*.npz"))
    pick = {}
    meta = None
    for p in files:
        b = os.path.basename(p)
        c0 = int(b[5:9])
        d = np.load(p)
        if meta is None:
            meta = json.loads(str(d["meta"]))
        for i, fr in enumerate(d["frames"]):
            fr = int(fr)
            if fr not in pick or pick[fr][0] < c0:
                pick[fr] = (c0, p, i)
    return pick, meta


class SecReader:
    def __init__(self, rid):
        self.pick, self.meta = sec_frames(rid)
        self.frames = np.array(sorted(self.pick))
        self._p = None; self._a = None

    def get(self, fr):
        c0, p, i = self.pick[int(fr)]
        if p != self._p:
            self._a = np.load(p)["sdf"]; self._p = p
        return self._a[i].astype(np.float32)


def dump(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=float)
