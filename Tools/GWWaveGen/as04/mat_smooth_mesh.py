# -*- coding: utf-8 -*-
"""美術の見本04 の調べ M（Q32）：AS04 Flat Smooth の材質を試すための、凹凸のない t* の主役波の静止のメッシュを作る。

- 見本03 の surf_relief.py（変えない）を --flat で呼び、出力の置き場だけを Build/Polish/sample04/mat/mesh へ替える。
  位置は AS02C の t*（keypose の包みの τ = 0）の格子の行を c −22〜+18 m で 4 倍に細かくしたもの（Catmull–Rom）。彫りの凹凸は 0。
- 頂点の属性（AS04 の材質が読む約束は Build/Polish/sample04/mat/README.md）：
  UV3 = (F, hrel, u, w)、UV4 = (gq, hrow, Lq, q)、UV5 = (ao, keyVis, whiteSD, fade)、UV6 = (行, 列, λ, 白の時刻が来たか)。
  白の境 whiteSD は見本03 の白の印 v2（shared/white_mask_f32.bin ＋ 帯の格子）。冠のメッシュは作らない・置かない。焼いた陰は使わない（ao = keyVis = 1）。
- 加えて、面の座標 u・w の面の上の伸び（|∇u|・|∇w|）を前の面で測り、白い点の格子（u・w で決める）が歪まないかの数を残す。
原画カメラの投影は使わない。参照モデルの OBJ・写真は読まない。
使い方：py -3.10 -B Tools/GWWaveGen/as04/mat_smooth_mesh.py
"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as03")
import surf_common as S  # noqa: E402
import surf_relief as R  # noqa: E402

OUT = REPO + "/Unity/Build/Polish/sample04/mat"
NAME = "hero_smooth_as02c"


def main():
    S.OUT = OUT                                  # surf_relief は S.OUT + "/mesh" へ書く
    sys.argv = ["surf_relief.py", "--name", NAME, "--flat",
                "--white-mask", REPO + "/Unity/Build/Polish/sample03/shared/white_mask_f32.bin",
                "--white-band", REPO + "/Unity/Build/Polish/sample03/shared/white_mask_band_f32.bin"]
    R.main()
    # ---- 面の座標の伸び（前の面：F 2.2〜3.95、白でない所）
    meta = json.load(open(OUT + "/mesh/" + NAME + ".json", encoding="utf-8"))
    n = meta["vertices"]
    raw = np.fromfile(OUT + "/mesh/" + NAME + ".bin", np.float32)
    off = 0
    ch = {}
    for nm, k in meta["channels"]:
        ch[nm] = raw[off:off + n * k].reshape(n, k); off += n * k
    rows = meta["vertices"] // 400
    P = ch["position"].reshape(rows, 400, 3).astype(np.float64)
    A = ch["uv3"].reshape(rows, 400, 4).astype(np.float64)
    C = ch["uv5"].reshape(rows, 400, 4).astype(np.float64)
    gu = np.linalg.norm(S.surface_grad(P, A[..., 2]), axis=-1)
    gw = np.linalg.norm(S.surface_grad(P, A[..., 3]), axis=-1)
    face = (A[..., 0] > 2.2) & (A[..., 0] < 3.95) & (C[..., 2] < -0.5)

    def q(x):
        x = x[face & np.isfinite(x)]
        return {k: round(float(np.percentile(x, p)), 3) for k, p in (("p10", 10), ("p50", 50), ("p90", 90))}

    rep = {"schema": "GreatWave.AS04.mat_smooth_mesh/1", "mesh": meta, "face_vertices": int(face.sum()),
           "grad_u_per_m": q(gu), "grad_w_per_m": q(gw), "ratio_gw_over_gu": q(gw / np.maximum(gu, 1e-6)),
           "noteJa": "前の面（F 2.2〜3.95、白の境から 0.5 m より藍の側）の面の座標の勾配。1 に近いほど u・w が面の上の m に近い。"}
    with open(OUT + "/mesh/" + NAME + "_uvmetric.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: rep[k] for k in ("face_vertices", "grad_u_per_m", "grad_w_per_m", "ratio_gw_over_gu")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
