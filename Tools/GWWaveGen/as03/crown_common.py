# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1（波頭の立体の白い指の冠と、白の垂れる縁）の共通の道具（numpy。Unity の描画ではない）。

- 入力（どれも読み取りのみ）：t* の主役波 K*′ AS02C（見本02 修正の回 1 の hero_pkg_AS02C、.gwb、行の表、meta）、
  見本02 の属性（attr_pin の s01a v2：A=(F, hrel, u, w)・B=(gw, hrow, Ls, X·L)・C=(法線, 0)、s01_param：(u, w, gu, gw, Xs, q)）、
  見本02 修正の回 1 の爪 83 本（ds33 の並びの書式）、調べ S1 の数（sculpture_spec.json）、S2 の役割（claw_roles.json）。
- 原画のカメラ（PaintingCam v1）は、指を置く場所の制約（IN）と、原画視点の関門の測りだけに使う。原画の色は面へ写さない（Q28）。
- 参照モデルの OBJ・彫刻の写真は読まない（F13-1。数は S1 の JSON から読む）。
"""
import hashlib
import json
import math
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import claws_common as CC  # noqa: E402

U = CC.U
S02 = REPO + "/Unity/Build/Polish/sample02/fix01"
HERO_PKG = S02 + "/assemble/hero_pkg_AS02C"
GWB = S02 + "/back/final/cand/kstarAS02C_a45.gwb"
META = S02 + "/back/final/cand/kstarAS02C_a45_meta.json"
ROWS = S02 + "/back/final/cand/kstarAS02C_a45_rows.npz"
ATTR = S02 + "/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin"
PARAM = S02 + "/assemble/attr_pin/s01_param_f32.bin"
CLAWD = S02 + "/assemble/claws/mesh"
SEA_NEAR = REPO + "/Unity/Build/Polish/30/sea/near/ds30_tstar.gwb"
S03 = REPO + "/Unity/Build/Polish/sample03"
STUDY = S03 + "/study"
OUT = S03 + "/crown"
SHARED = S03 + "/shared"
SPEC = STUDY + "/sculpture_spec.json"
ROLES = STUDY + "/claw_roles.json"
PCREST = STUDY + "/painting_crest.json"
BODY = (18, 394)
NR, NC = 240, 400


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=_np)


def _np(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def pct(a, qs=(10, 50, 90)):
    a = np.asarray(a, np.float64)
    a = a[np.isfinite(a)]
    if not len(a):
        return None
    return {("p%d" % q): round(float(np.percentile(a, q)), 4) for q in qs} | {"n": int(len(a)), "mean": round(float(a.mean()), 4)}


def read_gwb(p):
    import kh_common as K
    return K.read_gwb(p)


class HeroData:
    """t* の主役波 AS02C：世界の位置 X（行 240 × 列 400 × 3、Unity の座標 m、y が上）、属性、面の座標 (u, w)、法線（空気の側）。"""

    def __init__(self):
        CC.HERO = HERO_PKG
        self.X = CC.load_hero()                      # keypose の包みの τ = 0（Unity が描く位置）
        self.R, self.C = self.X.shape[:2]
        self.meta = jload(META)
        fr = self.meta["frame"]
        self.H0 = float(fr["H0_m"])
        self.e = np.array(fr["e_crest"])           # 頂に並ぶ向き（+c、原画視点の右）
        self.t = np.array(fr["t_travel"])          # 進む向き（前）
        self.anchor = np.array(fr["anchor_crest_top_world"])
        rows = np.load(ROWS)
        self.c_row = rows["c"].astype(np.float64)
        self.top_col = rows["top_argmax_col"].astype(np.int64)
        at = np.fromfile(ATTR, np.float32).reshape(self.R, self.C, 12).astype(np.float64)
        self.F, self.hrel, self.u, self.w = at[..., 0], at[..., 1], at[..., 2], at[..., 3]
        self.gw, self.hrow = at[..., 4], at[..., 5]
        self.Nattr = at[..., 8:11]
        par = np.fromfile(PARAM, np.float32).reshape(self.R, self.C, 8).astype(np.float64)
        self.par = par
        self.Tg = U.K.grid_tris(self.R, self.C, BODY[0], BODY[1])
        rr, cc = np.meshgrid(np.arange(self.R, dtype=np.float64), np.arange(self.C, dtype=np.float64), indexing="ij")
        Fr = U.frame_at(self.X, rr, cc)
        self.N = Fr[..., 2, :]                      # 空気の側の法線（設計33 の frame_at）
        self.V = self.X.reshape(-1, 3)

    def sec(self, P):
        """世界の点 → 断面の座標 (a 前, y 高さ, c 頂に並ぶ向き)。原点は頂の点の真下の海面。"""
        d = np.asarray(P, np.float64) - np.array([self.anchor[0], 0.0, self.anchor[2]])
        return np.stack([d @ self.t, d[..., 1], d @ self.e], -1)


def painting_cam(W=1920, H=1080):
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    return U.CamWH(spec, W, H)


def write_obj(p, V, F, N=None, name="mesh"):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="ascii", newline="\n") as f:
        f.write("o %s\n" % name)
        np.savetxt(f, V, fmt="v %.5f %.5f %.5f")
        if N is not None:
            np.savetxt(f, N, fmt="vn %.4f %.4f %.4f")
            FF = np.asarray(F) + 1
            np.savetxt(f, np.stack([FF[:, 0], FF[:, 0], FF[:, 1], FF[:, 1], FF[:, 2], FF[:, 2]], 1), fmt="f %d//%d %d//%d %d//%d")
        else:
            np.savetxt(f, np.asarray(F) + 1, fmt="f %d %d %d")
