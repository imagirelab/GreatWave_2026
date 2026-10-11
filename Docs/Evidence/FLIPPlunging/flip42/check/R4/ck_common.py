# -*- coding: utf-8 -*-
"""FLIP42 R4 の独立の確かめ：記録の読み込み（自前）。g_analyze.py・g_shape.py は使わず、読み込んでもいない。
記録の形は g_run.py の文から：hf_cXXXX.npz（一番上の水面の高さ eta[コマ, z の節, x の節]、x は格子の倍数、z は 5 節で真ん中が 2）、
sec_cXXXX_bYYYY.npz（板の真ん中の断面の水面の場 sdf[コマ, y, x]、float16、±8 m で切る）。t = (コマ − 1)/24。
同じコマが二つの起動にある時（途中保存から続けた所）は、ビット単位で同じかを数え、後の起動の値を使う。
"""
import os, glob, json, re
import numpy as np

ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42"
RUNS = ROOT + "/runs"
PLAN = ROOT + "/plan/plan_numbers.json"
FPS = 24.0
G = 9.80665


def cfg(run):
    return json.load(open(os.path.join(RUNS, run, "cfg.json"), encoding="utf-8"))


def _key(fn):
    m = re.search(r"_c(\d+)(?:_b(\d+))?\.npz$", fn)
    return (int(m.group(1)), int(m.group(2) or 0))


def load_hf(run, keep_full=False):
    files = sorted(glob.glob(os.path.join(RUNS, run, "hf_c*.npz")), key=_key)
    store = {}
    meta = {}
    ov_same = ov_diff = 0
    x = None
    for fn in files:
        d = np.load(fn, allow_pickle=False)
        if x is None:
            x = d["x"]; z = d["z"]
        fr = d["frames"]; eta = d["eta"]; wl = d["wall"]; npt = d["npts"]; lv = d["lvl"]; ssn = d["ss_n"]; ssd = d["ss_dt"]
        for i, f in enumerate(fr):
            f = int(f)
            e = eta[i]
            if f in store:
                if np.array_equal(store[f], e, equal_nan=True):
                    ov_same += 1
                else:
                    ov_diff += 1
            store[f] = e
            meta[f] = (float(wl[i]), int(npt[i]), float(lv[i]), int(ssn[i]), float(ssd[i]), _key(fn)[0])
    frames = np.array(sorted(store))
    out = dict(run=run, x=x, z=z, frames=frames, t=(frames - 1) / FPS, files=len(files), overlap_same=ov_same, overlap_diff=ov_diff)
    E = np.stack([store[f] for f in frames]).astype(np.float32)
    out["mid"] = E[:, 2, :]
    out["in3"] = np.nanmean(E[:, 1:4, :], axis=1)
    if keep_full:
        out["full"] = E
    out["wall"] = np.array([meta[f][0] for f in frames])
    out["npts"] = np.array([meta[f][1] for f in frames])
    out["lvl"] = np.array([meta[f][2] for f in frames])
    out["ss_n"] = np.array([meta[f][3] for f in frames])
    out["ss_dt"] = np.array([meta[f][4] for f in frames])
    out["launch"] = np.array([meta[f][5] for f in frames])
    return out


def load_sec(run):
    files = sorted(glob.glob(os.path.join(RUNS, run, "sec_c*_b*.npz")), key=_key)
    store = {}
    ov_same = ov_diff = 0
    meta = None
    for fn in files:
        d = np.load(fn, allow_pickle=False)
        m = json.loads(str(d["meta"]))
        if meta is None:
            meta = m
        else:
            for k in ("x0", "dx", "nx", "y0", "dy", "ny"):
                assert abs(meta[k] - m[k]) < 1e-9, (fn, k)
        sd = d["sdf"]
        for i, f in enumerate(d["frames"]):
            f = int(f)
            s = sd[i]
            if f in store:
                if np.array_equal(store[f], s, equal_nan=True):
                    ov_same += 1
                else:
                    ov_diff += 1
            store[f] = s
    frames = np.array(sorted(store))
    return dict(run=run, meta=meta, frames=frames, t=(frames - 1) / FPS, sdf=store, files=len(files), overlap_same=ov_same, overlap_diff=ov_diff)


def still_level(hf, xp, node="mid"):
    """計画の読み方 1：自由に進む所（造波板から 0〜930 m）の 0.5〜2.0 s の水面の高さの中央値。"""
    xr = hf["x"] - xp
    mx = (xr >= 0) & (xr <= 930)
    mt = (hf["t"] >= 0.5 - 1e-9) & (hf["t"] <= 2.0 + 1e-9)
    A = hf[node][np.ix_(mt, mx)]
    return float(np.nanmedian(A))
