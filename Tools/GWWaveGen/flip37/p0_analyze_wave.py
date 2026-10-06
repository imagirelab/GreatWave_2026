# -*- coding: utf-8 -*-
"""P0 T2 の解析：小さな波（周期 T）の、進む波の高さの x による変化（2 波長での減り）と、吸う帯からの跳ね返り（反射率）。
η(x, t) を周期 T の整数倍の時間で離散フーリエ変換し、各 x の複素振幅 A(x) を得て、
窓ごとに A(x) = a·exp(-ikx) + b·exp(+ikx) を最小二乗で合わせる（a＝進む波、b＝戻る波）。k は線形の分散関係。
使い方: py -3.10 p0_analyze_wave.py '<JSON>'
JSON: {"runs": ["<run_dir>", ...（続きの計算の順）], "T": 14, "h": 60, "t1": 12, "nper": 2,
       "x_lo": 150, "x_hi": 720, "win": 135, "x_ref1": 160, "out": "<json path>"}
"""
import numpy as np, json, sys, os
a = json.loads(sys.argv[1])
G = 9.80665
xs = None; T_all = []; E_all = []; F_all = []
for rd in a["runs"]:
    d = np.load(os.path.join(rd, "eta.npz"))
    if xs is None:
        xs = d["x"]
    fr = d["frames"]
    keep = np.ones(len(fr), bool)
    if F_all:
        keep = fr > max(np.concatenate(F_all))
    F_all.append(fr[keep]); T_all.append(d["t"][keep]); E_all.append(d["eta"][keep])
fr = np.concatenate(F_all); t = np.concatenate(T_all); eta = np.concatenate(E_all)
T = float(a["T"]); h = float(a["h"]); om = 2 * np.pi / T
k = om * om / G
for _ in range(60):
    th = np.tanh(k * h); f = G * k * th - om * om; df = G * th + G * k * h * (1 - th * th); k -= f / df
L = 2 * np.pi / k
t1 = float(a.get("t1", 12.0)); nper = int(a.get("nper", 2))
m = (t >= t1 - 1e-6) & (t < t1 + nper * T - 1e-6)
tt = t[m]; ee = eta[m]
if len(tt) < 10:
    print(json.dumps({"error": "not enough frames", "t_max": float(t.max())})); sys.exit(0)
ee = np.where(np.isnan(ee), np.nanmean(ee), ee)
ee = ee - ee.mean(axis=0, keepdims=True)
A = 2.0 / len(tt) * (ee * np.exp(-1j * om * tt)[:, None]).sum(axis=0)   # eta ≈ Re(A e^{iωt})
Hrange = ee.max(axis=0) - ee.min(axis=0)
res = {"T": T, "h": h, "k": float(k), "L": float(L), "t_window": [float(tt[0]), float(tt[-1])], "frames_used": int(len(tt)),
       "windows": []}
win = float(a.get("win", L / 2)); xlo = float(a["x_lo"]); xhi = float(a["x_hi"])
c = xlo
while c + win <= xhi + 1e-6:
    mm = (xs >= c) & (xs < c + win)
    X = xs[mm]
    M = np.stack([np.exp(-1j * k * X), np.exp(1j * k * X)], axis=1)
    sol, *_ = np.linalg.lstsq(M, A[mm], rcond=None)
    fit = M @ sol
    resid = float(np.linalg.norm(A[mm] - fit) / max(np.linalg.norm(A[mm]), 1e-9))
    res["windows"].append({"x0": float(c), "x1": float(c + win), "xc": float(c + win / 2),
                           "H_incident": float(2 * abs(sol[0])), "H_reflected": float(2 * abs(sol[1])),
                           "Kr": float(abs(sol[1]) / max(abs(sol[0]), 1e-9)), "fit_resid": resid,
                           "H_range_mean": float(Hrange[mm].mean())})
    c += win / 2
W = res["windows"]
if W:
    w0 = W[0]
    # 2 波長先の窓（中心の差が 2L に最も近い窓）
    j = int(np.argmin([abs((w["xc"] - w0["xc"]) - 2 * L) for w in W]))
    res["height_loss_2L"] = {"from_xc": w0["xc"], "to_xc": W[j]["xc"], "distance_over_L": (W[j]["xc"] - w0["xc"]) / L,
                             "H_from": w0["H_incident"], "H_to": W[j]["H_incident"],
                             "loss_frac": 1 - W[j]["H_incident"] / max(w0["H_incident"], 1e-9)}
    res["Kr_last_window"] = W[-1]["Kr"]
    res["Kr_max"] = max(w["Kr"] for w in W)
    res["Kr_median"] = float(np.median([w["Kr"] for w in W]))
print(json.dumps(res, indent=1))
if a.get("out"):
    json.dump(res, open(a["out"], "w"), indent=1)
