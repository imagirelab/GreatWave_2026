# -*- coding: utf-8 -*-
"""Twin oblique canyon-edge reflectors (Nazare-type: shelf swell totally reflected by a deep canyon edge, reflected beams cross the
incident on the axis). Also: lee-focus gain vs half width W. Linear MSE (steep edges: qualitative). py -3.10 -B [computed]"""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M, l51_screen as S, l51_pin as P
t0 = time.time()
res = {}
which = sys.argv[1]


def dirspec(tk, A1, ib):
    full = np.concatenate([A1[:0:-1, ib], A1[:, ib]])
    sp = np.abs(np.fft.fftshift(np.fft.fft(full * np.hanning(len(full)))))
    ky = np.fft.fftshift(np.fft.fftfreq(len(full), S.DX)) * 2 * math.pi
    k0 = float(tk.k[0, ib]); m = np.abs(ky) <= k0
    th = np.degrees(np.arcsin(np.clip(np.abs(ky[m]) / k0, 0, 1))); e = sp[m] ** 2
    hist = {}
    for lo in range(0, 90, 15):
        mm = (th >= lo) & (th < lo + 15)
        hist["%d-%d" % (lo, lo + 15)] = float(e[mm].sum() / e.sum())
    return float(np.sqrt(np.sum(e * th ** 2) / np.sum(e))), hist


if which == "canyon":
    for (hs, hc, Y0, alpha, x0) in [(17.0, 40.0, 100.0, 25.0, 130.0), (17.0, 40.0, 100.0, 20.0, 130.0), (17.0, 60.0, 110.0, 30.0, 120.0)]:
        W = 140.0; Lx = 520.0
        x = np.arange(0, Lx + 1e-9, S.DX); y = np.arange(0, W + 1e-9, S.DX)
        X, Y = np.meshgrid(x, y)
        ta = math.tan(math.radians(alpha))
        ye = Y0 - (X - x0) * ta
        x1 = x0 + (Y0 - 25.0) / ta
        inside = (X >= x0) & (X <= x1)
        wc = 0.5 * (1 + np.tanh((Y - ye) / 4.0)) * inside
        h = hs + (hc - hs) * wc
        tk, A1, AT = S.run_case(12.0, x, y, h, target_kind="plane", side=None, exit_x0=Lx - 100.0, swash=None, periods=34)
        Aa = np.abs(A1)
        ax = Aa[0]; m = (x > x0) & (x < Lx - 110)
        ib = int(np.where(m)[0][np.argmax(ax[m])])
        rms, hist = dirspec(tk, A1, ib)
        sh = P.shape_at(tk, A1, ib, 1.0)
        key = "canyon_hs%g_hc%g_Y%g_a%g" % (hs, hc, Y0, alpha)
        res[key] = dict(gain_axis_max=float(ax[ib]), x_max=float(x[ib]), x1=x1, h_at=float(h[0, ib]), W50_m=sh["W50_m"], W80_m=sh["W80_m"],
                        W95_m=sh["W95_m"], dir_rms_deg=rms, dir_hist=hist, amp_canyon_mean=float(np.mean(Aa[h > hs + 5])),
                        S2_at_Hc8=float(np.interp(16.0, y, np.max(np.where(((x >= x[ib] - 30) & (x <= x[ib] + 10))[None, :],
                                                                              np.real(A1 * np.exp(-1j * np.angle(A1[0, ib]))), -9), axis=1)) / sh["H_lin"]))
        print(key, json.dumps(res[key], default=float), flush=True)
        np.savez_compressed(os.path.join(S.OUT, key + "_A1.npz"), A=A1, x=x, y=y, h=h)
elif which == "leeW":
    for W in (180.0, 220.0, 260.0):
        T, h0, R, ht, xc = 12.0, 19.0, 60.0, 0.0, 200.0
        Lx = xc + R + 260.0
        x = np.arange(0, Lx + 1e-9, S.DX); y = np.arange(0, W + 1e-9, S.DX)
        h = h0 - M.mound(x, y, xc, R, R, h0 - ht, shape="cos2")
        tk, A1, AT = S.run_case(T, x, y, h, target_kind="plane", side=(W - 45.0, 1e9, 1e9 + 1), exit_x0=Lx - 100.0, swash=(4.0, 2.0, 2), periods=34)
        Aa = np.abs(A1); lee = (x > xc + R) & (x < Lx - 110)
        ib = int(np.where(lee)[0][np.argmax(Aa[0][lee])])
        sh = P.shape_at(tk, A1, ib, 9.1)
        res["W%d" % W] = dict(gain=float(Aa[0, ib]), x=float(x[ib]), W50_m=sh["W50_m"], W80_m=sh["W80_m"], W95_m=sh["W95_m"], S2=sh["S2"], ring=sh["ring_max"])
        print(W, res["W%d" % W], flush=True)
json.dump(res, open(os.path.join(S.OUT, "canyon_%s.json" % which), "w"), indent=1, default=float)
print("wall", time.time() - t0)
