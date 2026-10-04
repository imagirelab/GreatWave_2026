# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：空を地にした輪郭（ID の描画の空の色 (0,255,255)）を、見本02（調べ S3 の同じカメラの描画）と比べる。
稜を本当の凹凸にした静止のメッシュで、原画視点などの輪郭がどれだけ動いたか（画素の数と、見本02 の縁からの距離）。評価器の関門そのものではない。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_silhouette.py <描画のフォルダー>"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402

rd = sys.argv[1]
ref = S.S03 + "/study/render/S3_AS02C/diag"


def sky(p):
    a = np.asarray(Image.open(p).convert("RGB"))
    return (a[..., 0] == 0) & (a[..., 1] == 255) & (a[..., 2] == 255)


out = {"ref": ref, "render": rd}
for v in ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]:
    a = sky(ref + "/%s_t120_id_claws0.png" % v); b = sky(rd + "/diag/%s_t120_id_claws0.png" % v)
    dd = a ^ b
    rec = {"diff_px": int(dd.sum())}
    if dd.sum():
        edge = a ^ ndimage.binary_erosion(a)
        dist = ndimage.distance_transform_edt(~edge)
        rec["max_dist_px"] = round(float(dist[dd].max()), 2)
        rec["p99_dist_px"] = round(float(np.percentile(dist[dd], 99)), 2)
    out[v] = rec
S.jdump(S.OUT + "/measure/silhouette_vs_sample02.json", out)
print(out)
