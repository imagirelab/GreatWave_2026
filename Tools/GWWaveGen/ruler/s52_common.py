# -*- coding: utf-8 -*-
"""STUDY52（Q52 の検討）の道具の写し（Tools/GWWaveGen/ruler。元は Unity/Build/STUDY52/tools、置き場所だけ相対に直した）：形の量を、FLIP42 の断面の記録と原画の輪郭から同じ定義で読む道具（py -3.10、numpy・PIL・scikit-image）。
重い計算はしない。記録を読むだけ。
"""
import os, json, glob, math
import numpy as np
from skimage import measure

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))  # リポジトリの根（元は G: の絶対パス）
RUNS = REPO + "/Unity/Build/FLIP42/runs"
OUT = REPO + "/Unity/Build/STUDY52"
FPS = 24.0


# ------------------------------------------------------------------ FLIP42 の記録
def run_info(rid):
    cfg = json.load(open(os.path.join(RUNS, rid, "cfg.json"), encoding="utf8"))
    ana = json.load(open(os.path.join(RUNS, rid, "ana.json"), encoding="utf8"))
    return dict(x_p=cfg["parms"]["x_p"], dp=cfg["parms"]["dp"], vox=2 * cfg["parms"]["dp"],
                off=ana["still_level_offset_m"], onset=ana["onset"], touch=ana["touchdown"])


def sec_frame(rid, frame):
    """コマ frame の断面の水面の場（後の起動が上書きした物を使う。g_analyze.load_sec と同じ決まり）。"""
    best = None
    for p in glob.glob(os.path.join(RUNS, rid, "sec_c*_b*.npz")):
        b = os.path.basename(p); f0 = int(b[5:9])
        d = np.load(p)
        fr = list(map(int, d["frames"]))
        if frame in fr and frame >= f0 and (best is None or best[0] < f0):
            best = (f0, p, fr.index(frame))
    if best is None:
        return None
    d = np.load(best[1])
    meta = json.loads(str(d["meta"]))
    return d["sdf"][best[2]].astype(np.float32), meta, best[1]


def contours(rid, frame, info=None):
    """0 の等高線（水の側が負）。座標は x：造波板からの距離（m）、z：静かな水面からの高さ（m）。"""
    info = info or run_info(rid)
    S, meta, src = sec_frame(rid, frame)
    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"]) - info["x_p"]
    ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"]) - info["off"]
    j0 = int(np.searchsorted(ys, -25.0))      # g_analyze と同じ：静かな水面の 25 m 下より上だけ
    S = S[j0:]; ys = ys[j0:]
    out = []
    for c in measure.find_contours(S, 0.0):
        X = xs[0] + c[:, 1] * meta["dx"]; Y = ys[0] + c[:, 0] * meta["dy"]
        out.append(np.stack([X, Y], 1))
    return out, dict(S=S, xs=xs, ys=ys, src=os.path.basename(src))


def main_line(lines):
    ext = [l[:, 0].max() - l[:, 0].min() for l in lines]
    m = lines[int(np.argmax(ext))]
    if m[0, 0] > m[-1, 0]:
        m = m[::-1]
    return m


def poly_area(c):
    x, y = c[:, 0], c[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def resample(path, ds):
    seg = np.sqrt((np.diff(path, axis=0) ** 2).sum(1))
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < ds:
        return path
    q = np.arange(0, s[-1], ds)
    return np.stack([np.interp(q, s, path[:, 0]), np.interp(q, s, path[:, 1])], 1)
