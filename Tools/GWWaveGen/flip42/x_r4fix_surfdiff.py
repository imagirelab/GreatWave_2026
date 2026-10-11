# -*- coding: utf-8 -*-
"""FLIP42 R4fix：R3 の途中保存から続けた計算（R3m・R3d）と R3 の、巻き始めより前の水面の差（py -3.10、読むだけ）。
R3d の結果を見る前（2026-10-10 17:55）に決めた測り方：
  水面＝一番上の水面の高さを板の内側の節で平均したもの（g_analyze.zmean、FLIP41 と同じ読み方）。
  範囲＝断面の範囲（造波板から 321〜863 m、cfg の sec.x0〜x1）、コマ 3319〜R3 の巻き始めのコマ（shape.json の onset.frame）。
  量＝差の二乗平均の平方根（RMS）・差の絶対値の最大・99 % 点（m）。R3 の同じコマ・同じ節と比べる。
py -3.10 x_r4fix_surfdiff.py R3m R3d   → 標準出力と R4fix/surfdiff.json"""
import sys, os, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A

ref = "R3"
cfg = json.load(open(os.path.join(A.ROOT, ref, "cfg.json"), encoding="utf8"))
on = json.load(open(os.path.join(A.ROOT, ref, "shape.json"), encoding="utf8"))["onset"]
f_on = int(on["frame"])
D0 = A.load_hf(ref); E0 = A.zmean(D0)
x = D0["x"]; xm = (x >= cfg["sec"]["x0"]) & (x <= cfg["sec"]["x1"])
i0 = {int(f): i for i, f in enumerate(D0["frames"])}
out = dict(ref=ref, onset_frame=f_on, onset_t=on["t"], x_range=[cfg["sec"]["x0"], cfg["sec"]["x1"]], runs={})
for rid in sys.argv[1:]:
    D = A.load_hf(rid); E = A.zmean(D)
    fr = [int(f) for f in D["frames"] if 3319 <= int(f) <= f_on and int(f) in i0]
    i1 = {int(f): i for i, f in enumerate(D["frames"])}
    d = np.array([E[i1[f]][xm] - E0[i0[f]][xm] for f in fr])
    ok = np.isfinite(d)
    a = np.abs(d[ok])
    per = np.sqrt(np.nanmean(d**2, axis=1))
    r = dict(frames=[fr[0], fr[-1]], n_frames=len(fr), rms_m=float(np.sqrt(np.mean(d[ok]**2))), max_abs_m=float(a.max()),
             p99_abs_m=float(np.percentile(a, 99)), rms_last_frame_m=float(per[-1]),
             rms_by_time=[[fr[k], round(float(per[k]), 5)] for k in range(0, len(fr), 24)])
    out["runs"][rid] = r
    print(rid, json.dumps({k: v for k, v in r.items() if k != "rms_by_time"}))
    print("   rms by time", r["rms_by_time"])
json.dump(out, open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/R4fix/surfdiff.json", "w", encoding="utf8"), indent=1)
