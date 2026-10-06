# -*- coding: utf-8 -*-
"""組み込みの準備の試験データ（2）：P1 の断面の計算（B025H32_T14_H32_n4_hr26、粒子 0.25 m、誘導なし）を
峰に沿って時刻をずらして並べた「巻き込みのある試験用の面」。3D の流体の計算ではない（断面の計算の並べ物）と必ず書く。

作り方：
1. 断面の粒子（snap_XXXX.npz）を P1 の解析と同じ升目（p1_analyze.raster・water_mask、0.175 m）で水の形にし、
   ぼかして 0〜1 の場にする（コマごとに 1 回）。
2. 出すコマの時刻 T と峰に沿う位置 z ごとに、その行の時刻 t(z) = T − z / PEEL を決め、前後の 2 枚の断面の場を
   頂の進み（P1 の解析の頂の x の時刻の表）だけ x へずらして時間で混ぜる。
3. (x, y, z) の 3D の場を marching cubes（skimage）で水面の網目にする。
出力：Unity/Build/FLIP37/integration_prep/testdata/P1sweep/mesh_XXXX.npz（P float32、tri int32、t＝T）と sweep.json。
使い方：py -3.10 integ_p1_sweep.py
"""
import os, sys, glob, json, time
import numpy as np
from scipy import ndimage as ndi
from skimage import measure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1_analyze as PA
import integ_common as C

RUN = C.REPO + "/Unity/Build/FLIP37/P1/B025H32_T14_H32_n4_hr26"
OUTD = C.OUT + "/testdata/P1sweep"
PEEL = 40.0                       # 峰に沿う時刻のずれ：1 s あたり 40 m（z < 0 の側＝原画の左がより進んだ段）
ZMIN, ZMAX, DZ = -45.0, 45.0, 1.0
DXV = 0.25                        # 3D の場の升目（x・y）
YLO, YHI = -20.0, 32.0
T_OUT = np.round(np.arange(8.25, 12.5 + 1e-6, 1.0 / 12.0), 6)


def main():
    os.makedirs(OUTD, exist_ok=True)
    t0 = time.time()
    rj = json.load(open(RUN + "/run.json", encoding="utf8"))
    PA.set_dx(rj["parms"])
    an = json.load(open(RUN + "/analysis.json", encoding="utf8"))
    tl = an["timeline"]
    tc = np.array([e["t"] for e in tl]); xc = np.array([e["crest"][0] for e in tl])
    fs = sorted(glob.glob(RUN + "/snap_*.npz"))
    X0, X1 = 401.0, 805.0
    fields, times = [], []
    for f in fs:
        d = np.load(f)
        cnt = PA.raster(d["x"].astype(float), d["y"].astype(float), X0, X1)
        water, closed = PA.water_mask(cnt)
        fld = ndi.gaussian_filter(water.astype(np.float32), 1.0)
        fields.append(fld); times.append(float(d["t"]))
    times = np.array(times)
    ny0, nx0 = fields[0].shape
    print("fields", len(fields), fields[0].shape, "DX", PA.DX, "%.1fs" % (time.time() - t0))
    zs = np.arange(ZMIN, ZMAX + 1e-6, DZ)
    ys = np.arange(YLO, YHI + 1e-6, DXV)
    rec = []
    for T in T_OUT:
        tz = T - zs / PEEL
        xcT = float(np.interp(T, tc, xc))
        xlo = max(X0 + 1, xcT - 115.0); xhi = min(X1 - 1, xcT + 125.0)
        xs = np.arange(xlo, xhi + 1e-6, DXV)
        V = np.zeros((len(xs), len(ys), len(zs)), np.float32)
        XX, YY = np.meshgrid(xs, ys, indexing="ij")
        for k, t in enumerate(tz):
            i1 = int(np.clip(np.searchsorted(times, t), 1, len(times) - 1)); i0 = i1 - 1
            a = float(np.clip((t - times[i0]) / (times[i1] - times[i0]), 0, 1))
            acc = np.zeros_like(XX, dtype=np.float32)
            for ii, wgt in ((i0, 1 - a), (i1, a)):
                if wgt <= 0:
                    continue
                sh = float(np.interp(t, tc, xc) - np.interp(times[ii], tc, xc))   # 頂の進みだけずらす
                col = (XX - sh - X0) / PA.DX - 0.5
                row = (YY - PA.YMIN) / PA.DX - 0.5
                acc += wgt * ndi.map_coordinates(fields[ii], [row, col], order=1, mode="nearest").astype(np.float32)
            V[:, :, k] = acc
        verts, faces, _, _ = measure.marching_cubes(V, 0.5, spacing=(DXV, DXV, DZ))
        P = verts + np.array([xs[0], ys[0], zs[0]])
        fi = int(round(T * 24)) + 1
        np.savez_compressed(OUTD + "/mesh_%04d.npz" % fi, P=P.astype(np.float32), tri=faces.astype(np.int32), t=T)
        rec.append({"frame": fi, "T": float(T), "verts": int(len(P)), "tris": int(len(faces)), "x_range": [float(xs[0]), float(xs[-1])]})
        print("T %.3f verts %d tris %d  %.1fs" % (T, len(P), len(faces), time.time() - t0), flush=True)
    json.dump({"source_run": RUN, "source_run_json_sha256": C.sha256(RUN + "/run.json"), "peel_m_per_s": PEEL,
               "z": [ZMIN, ZMAX, DZ], "dx": DXV, "y": [YLO, YHI], "frames": rec, "wall_s": time.time() - t0,
               "note_ja": "P1 の断面の計算（2D、誘導なし）を、峰に沿う位置 z ごとに時刻を t(z) = T − z/40 s ずらして並べた試験用の面。"
                          "3D の流体の計算ではない。頂の進みで x をずらして前後の 2 枚を混ぜた。z < 0 の側がより進んだ段。"},
              open(OUTD + "/sweep.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
