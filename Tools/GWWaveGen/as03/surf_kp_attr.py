# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：keypose の主役波（_AS03Src = 0。形成の動きでも使える道）の属性。見本02 の 12 個（s01a v2）の C.w（空き）に、
B1 の共有の白の印（格子の頂点ごとの符号付きの距離 m、+ が白）を入れる。PL29UkiyoeHero がそのまま UV3〜UV5 に入れる。
原画カメラの投影は使わない。使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_kp_attr.py [--white-mask <shared/white_mask_f32.bin>]"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--white-mask", default=S.SHARED + "/white_mask_f32.bin")
a = ap.parse_args()
at = np.fromfile(S.ATTR, np.float32).reshape(-1, 12).copy()
wm = np.fromfile(a.white_mask, np.float32)
assert wm.shape[0] == at.shape[0]
at[:, 11] = wm
od = S.OUT + "/attr"
os.makedirs(od, exist_ok=True)
p = od + "/as03_kp_attr_f32.bin"
at.astype(np.float32).tofile(p)
S.jdump(od + "/as03_kp_attr.json", {"schema": "GreatWave.AS03.kp_attr/1", "layoutJa": "頂点ごとの float32 × 12：A = (F, hrel, u, w)、B = (gw, hrow, Ls, X·L̂)、C = (t* の法線 xyz, 白の印の符号付きの距離 m)。UV3〜UV5",
                                    "attr": S.ATTR, "attr_sha256": S.sha(S.ATTR), "white_mask": a.white_mask, "white_mask_sha256": S.sha(a.white_mask),
                                    "output": p, "sha256": S.sha(p), "projection_used": False})
print(p, S.sha(p))
