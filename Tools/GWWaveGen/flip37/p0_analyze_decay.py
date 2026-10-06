# -*- coding: utf-8 -*-
"""P0 T2 の補い：hot start の波（t=0 で高さ H がそろった進む波）が、時間とともにどれだけ低くなるか（数値の減衰）。
起こす帯から来る波の前（x = xg + cg·t）より先の窓だけを使い、周期 T の時間窓ごとに進む波の高さ（a·exp(-ikx) の合わせ）を出す。
減り方を時間の指数で合わせ、波のエネルギーが 2 波長進む時間（2L/cg）での高さの減りに直す。
使い方: py -3.10 p0_analyze_decay.py '<JSON>'  {"runs": [...], "T": 14, "h": 60, "xw": [500, 640], "t_starts": [0, 4, 7, 14], "xg": 140, "out": "..."}"""
import numpy as np, json, sys, os
a = json.loads(sys.argv[1]); G = 9.80665
xs = None; T_all = []; E_all = []; F_all = []
for rd in a["runs"]:
    d = np.load(os.path.join(rd, "eta.npz"))
    xs = d["x"]; fr = d["frames"]
    keep = np.ones(len(fr), bool) if not F_all else fr > max(np.concatenate(F_all))
    F_all.append(fr[keep]); T_all.append(d["t"][keep]); E_all.append(d["eta"][keep])
t = np.concatenate(T_all); eta = np.concatenate(E_all)
T = float(a["T"]); h = float(a["h"]); om = 2 * np.pi / T
k = om * om / G
for _ in range(60):
    th = np.tanh(k * h); k -= (G * k * th - om * om) / (G * th + G * k * h * (1 - th * th))
L = 2 * np.pi / k; c = L / T; cg = 0.5 * c * (1 + 2 * k * h / np.sinh(2 * k * h))
x0, x1 = a["xw"]; mm = (xs >= x0) & (xs < x1); X = xs[mm]
M = np.stack([np.exp(-1j * k * X), np.exp(1j * k * X)], axis=1)
rows = []
for ts in a["t_starts"]:
    m = (t >= ts - 1e-6) & (t < ts + T - 1e-6)
    if m.sum() < 0.9 * T * 24:
        continue
    front = a["xg"] + cg * (ts + T)
    ee = eta[m][:, mm]; ee = np.where(np.isnan(ee), 0.0, ee); ee = ee - ee.mean(axis=0, keepdims=True)
    A = 2.0 / m.sum() * (ee * np.exp(-1j * om * t[m])[:, None]).sum(axis=0)
    sol, *_ = np.linalg.lstsq(M, A, rcond=None)
    rows.append({"t0": ts, "t_mid": ts + T / 2, "H_incident": float(2 * abs(sol[0])), "Kr": float(abs(sol[1]) / abs(sol[0])),
                 "gen_front_x_at_end": float(front), "window_clear_of_gen_front": bool(front < x0)})
ok = [r for r in rows if r["window_clear_of_gen_front"]]
res = {"L": float(L), "c": float(c), "cg": float(cg), "xw": [x0, x1], "rows": rows}
if len(ok) >= 2:
    tm = np.array([r["t_mid"] for r in ok]); Hh = np.array([r["H_incident"] for r in ok])
    p = np.polyfit(tm, np.log(Hh), 1)
    t2L = 2 * L / cg
    res["decay_per_s"] = float(-p[0]); res["time_for_2L_s"] = float(t2L)
    res["height_loss_2L_from_decay"] = float(1 - np.exp(p[0] * t2L))
    res["H_at_t0_fit"] = float(np.exp(p[1]))
print(json.dumps(res, indent=1))
if a.get("out"):
    json.dump(res, open(a["out"], "w"), indent=1)
