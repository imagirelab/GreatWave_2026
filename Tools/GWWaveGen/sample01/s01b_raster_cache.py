# -*- coding: utf-8 -*-
"""美術の見本01 B：t* の主役波（K*′ P28R2rec）を各視点の numpy の z バッファで描き、画素ごとの三角形と重心座標を保存する（形と視点だけで決まる。材質によらない）。
使い方：py -3.10 -B s01b_raster_cache.py [視点 ...]（既定 painting）。出力 work/raster_<視点>.npz（tid int32、bary float32）"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s01b_common as S

WORK = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/work/"


def main():
    views = sys.argv[1:] or ["painting"]
    g = S.load_gwb()
    for v in views:
        t0 = time.time()
        cm = S.cam(v)
        tid, b, z = S.raster_bary(cm, g["pos"], g["tri"])
        np.savez_compressed(WORK + f"raster_{v}.npz", tid=tid.astype(np.int32), bary=b.astype(np.float32), z=z.astype(np.float32))
        print(v, "%.1f s" % (time.time() - t0), int((tid >= 0).sum()))


if __name__ == "__main__":
    main()
