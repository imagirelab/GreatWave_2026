# -*- coding: utf-8 -*-
"""RT48：x の両端の下ろし（x 100〜200 m・825〜925 m で高さに 1→0 の重み。計算にない形）が、座席の目から見える所にあるかを、焼いた元で数える（py -3.10）。
独立の確かめの k_taper.py（Unity/Build/RT48/check/、R3 の記録から確かめ役が作った線）と同じ数え方を、焼いた線（組 k の A、最後のコマは最後の組の B）に当てる：
  各コマで、目（そのコマの船の上下 ＋ 1.2 m）から前（−x）と後ろ（+x）を見て、手前の水より高い角に出る（隠れない）点のうち、下ろしの帯の点があるか。
  あれば、そのコマを「見える」と数え、そこで見せている高さと計算の高さの差の最大を出す。線は 0.25 m おきに細かくする。範囲は座席の船からのクリップの終わりまで。
使い方: py -3.10 v_taper.py fine      → Unity/Build/RT48/verify/<元>/taper.json"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r_lib as L
import u_bakeio as U

BUILD = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"


def main(src):
    d = os.path.join(BUILD, "data", src)
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf8"))
    P, N = man["playback"]["n_pairs"], man["n_points"]
    pairs = np.fromfile(os.path.join(d, "pairs.bin"), dtype="<f4").reshape(P, 2, N, 2)
    fx = man["x_fade"]["ranges_x_rel"]
    x0 = man["coords"]["origin_x_rel"]
    meta = dict(frame_count=man["time"]["n_frames"], x_origin_m=x0, taper_m=[fx[0][0], fx[0][1], fx[1][0], fx[1][1]])
    tp = U.taper_stored(meta)
    f0 = man["time"]["first_frame"]
    res = dict(source=src, rule="k_taper.py と同じ数え方を焼いた線に当てた（v_taper.py）", seats={})
    for seat in (556.0, 574.0):
        b = man["boat"]["%d" % seat]
        fend = b["clip_end_frame"]
        out = dict(clip_end_frame=fend, n_frames=fend - f0 + 1, front_visible_frames=0, back_visible_frames=0, back_max_dy=0.0, front_max_dy=0.0,
                   back_first_visible_frame=None, front_frames=[])
        for f in range(f0, fend + 1):
            k = f - f0
            c = U.frame_curve(pairs, meta, k).astype(np.float64)
            Pd = L.densify(np.stack([c[:, 0] + x0, c[:, 1]], 1), 0.25)
            eye = b["heave_m"][k] + 1.2
            Yd = Pd[:, 1] * U.taper_weight(Pd[:, 0] - x0, tp)
            for side in ("front", "back"):
                sel = Pd[:, 0] < seat - 0.5 if side == "front" else Pd[:, 0] > seat + 0.5
                x = Pd[sel, 0]; yd = Yd[sel]; yt = Pd[sel, 1]
                order = np.argsort(np.abs(x - seat))
                x, yd, yt = x[order], yd[order], yt[order]
                el = np.arctan2(yd - eye, np.abs(x - seat))
                vis = el > np.maximum.accumulate(np.r_[-np.inf, el[:-1]])
                tz = (x < 200.0) | (x > 825.0)
                v = vis & tz
                if v.any():
                    out[side + "_visible_frames"] += 1
                    if side == "front":
                        out["front_frames"].append(f)
                    elif out["back_first_visible_frame"] is None:
                        out["back_first_visible_frame"] = f
                    out[side + "_max_dy"] = max(out[side + "_max_dy"], float(np.abs(yd[v] - yt[v]).max()))
        out["back_nearest_m"] = 825.0 - seat
        res["seats"]["%d" % seat] = out
        print(seat, {k: v for k, v in out.items() if k != "front_frames"}, flush=True)
    od = os.path.join(BUILD, "verify", src)
    os.makedirs(od, exist_ok=True)
    json.dump(res, open(os.path.join(od, "taper.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
