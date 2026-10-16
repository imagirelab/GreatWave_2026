# -*- coding: utf-8 -*-
"""FLIP3D：DA3 の 3D の面を Unity で繰り返し再生するための共通の読み手（py -3.10、numpy・scipy だけ）。
2026-10-16 進行役（Claude）が新しく書いた。flip45〜49 のファイルは変えない（g45_export_unity の読み手を import して使うだけ）。
記録（どれも Unity/Build/FLIP49/runs/DA3_SC37y30_T12H7p5_dp0p5/ の中。Git には入れていない）：
  surf/s_FFFFF.gw45s  面（R5、GW45SRF1）。3 コマおき（t = 47〜92 s は続けて、92 s の後は 7 s の窓が 4 つ）
  hf_cCCCCC_bBBBBB.npz  上の水面の高さ η（毎コマ、格子 1 m、x 0.5〜441.5・横 0.5〜84.5）
  r4_cCCCCC_bBBBBB.npz  崩れの所の水面の SDF（3 コマおき、格子 1 m、x 225.5〜361.5・上 −9.5〜15.5・横 0.5〜84.5、±6 m で切る）
同じコマが 2 つの起動にある時（途中保存から続けた所）は、後の起動の物を使う（面の記録 surf/ も後の起動が上書きした）。
"""
import os, sys, glob, json, re
import numpy as np

REPO = r"G:/Unity/GreatWave_2026_Fresh"
RUN = REPO + "/Unity/Build/FLIP49/runs/DA3_SC37y30_T12H7p5_dp0p5"
# 2026-10-16 追記：DA3 の途中保存 v.1824 から同じ物理で計算し直し、面（R5）と SDF（r4）を毎コマ書いた記録（DA3r、76.0〜90.0 s、コマ 1825〜2161）。
# DA3 と共通の 3 コマおきのコマでは面の記録がバイト単位で同じ（g49_restart.py compare、restart_compare.json）。読むだけ（書かない）
RUN24 = REPO + "/Unity/Build/FLIP49/runs/DA3r_SC37y30_T12H7p5_dp0p5_c1824_t90"
OUT = REPO + "/Unity/Build/FLIP3D"
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"   # flip45 g45_common.FFMPEG と同じ
FPS_SIM = 24.0
sys.path.insert(0, REPO + "/Tools/GWWaveGen/flip45")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/flip49")
import g45_export_unity as E45          # noqa: E402  読むだけ（変えない）


def t_of(f):
    """コマ f の計算の時刻（s）。コマ 1 が t = 0（面の記録の頭の t と同じ：コマ 1129 → 47.0 s）。"""
    return (f - 1) / FPS_SIM


def surf_frames(run=None):
    return sorted(int(os.path.basename(p)[2:7]) for p in glob.glob((run or RUN) + "/surf/s_*.gw45s"))


def surf_path(f, run=None):
    return (run or RUN) + "/surf/s_%05d.gw45s" % f


def read_surf(f, run=None):
    return E45.read_frame_bytes(open(surf_path(f, run), "rb").read())


def _blocks(kind, run=None):
    out = []
    for p in glob.glob((run or RUN) + "/%s_c*_b*.npz" % kind):
        m = re.search(r"_c(\d+)_b(\d+)\.npz$", p)
        out.append((int(m.group(1)), int(m.group(2)), p))
    return sorted(out)


class Rec:
    """hf（毎コマ）と r4（3 コマおき）をコマ番号で引く。読んだブロックは覚えておく。"""

    def __init__(self, kind, run=None):
        self.kind = kind
        self.where = {}             # frame -> (chunk, path, index)
        self.meta = None
        for c, b, p in _blocks(kind, run):
            with np.load(p, allow_pickle=True) as d:
                fr = d["frames"]
                mt = json.loads(str(d["meta"]))
            if b == 1:
                continue                # コマ 1 だけの始めのブロックは格子が違う（静かな水の箱の確かめ）。使わない
            if self.meta is None:
                self.meta = mt
            elif mt != self.meta:
                raise ValueError("格子の違うブロック：%s" % p)
            for i, f in enumerate(fr):
                f = int(f)
                if f not in self.where or self.where[f][0] < c:
                    self.where[f] = (c, p, i)
        self._cache = {}

    def frames(self):
        return sorted(self.where)

    def get(self, f):
        c, p, i = self.where[f]
        if p not in self._cache:
            if len(self._cache) > 6:
                self._cache.pop(next(iter(self._cache)))
            with np.load(p, allow_pickle=True) as d:
                self._cache[p] = d["eta" if self.kind == "hf" else "sdf"].astype(np.float32)
        return self._cache[p][i]


def axes_hf(meta):
    """hf の η[横, x] の軸（m）。"""
    xs = meta["x0"] + meta["dx"] * np.arange(meta["res"][0])
    zs = meta["z0"] + meta["dz"] * np.arange(meta["res"][2])
    return xs, zs


def sdf_at(sdf, meta, P):
    """r4 の SDF（[横, 上, x]、格子 1 m）を点 P（x, 上, 横）で 1 次の補間。箱の外は nan。"""
    from scipy.ndimage import map_coordinates
    ix = (P[:, 0] - meta["x0"]) / meta["dx"]
    iy = (P[:, 1] - meta["y0"]) / meta["dy"]
    iz = (P[:, 2] - meta["z0"]) / meta["dz"]
    inside = (ix >= 0) & (ix <= meta["nx"] - 1) & (iy >= 0) & (iy <= meta["ny"] - 1) & (iz >= 0) & (iz <= meta["nz"] - 1)
    v = np.full(len(P), np.nan, np.float64)
    if inside.any():
        v[inside] = map_coordinates(sdf.astype(np.float64), np.stack([iz[inside], iy[inside], ix[inside]]), order=1, mode="nearest")
    return v


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
