# -*- coding: utf-8 -*-
"""(1) option-D fan + upstream shoal lens; (2) island / near-emergent shoal: lee crossing. Linear MSE. py -3.10 -B [computed]"""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M, l51_screen as S, l51_pin as P
t0 = time.time()
res = {}
which = sys.argv[1]
if which == "fanlens":
    for (T, a_sum, lens) in [(10.0, 6.503, None), (10.0, 6.503, (130.0, 30.0, 60.0, 12.0)), (10.0, 6.503, (130.0, 30.0, 90.0, 10.0)),
                             (12.0, 6.331, None), (12.0, 6.331, (130.0, 30.0, 90.0, 10.0))]:
        x = np.arange(0, 412 + 1e-9, S.DX); y = np.arange(0, 140 + 1e-9, S.DX)
        h = M.bed_beach(x, y)
        if lens:
            xc, Rx, Ry, ht = lens
            h = h - M.mound(x, y, xc, Rx, Ry, 19.0 - ht)
        fan = dict(h0=19.0, x_toe=160.25, s=10.0, a_sum=1.0, x_f=220.25)
        tk, A1, AT = S.run_case(T, x, y, h, target_kind="fan", fan=fan, side=(95.0, 180.25, 210.25), periods=30)
        A = A1 * a_sum
        hax = h[0]
        L_loc = 2 * math.pi / float(np.median(tk.k[0][(x > 110) & (hax > 3)]))
        As = S.smooth_rms(A[0], x, 0.5 * L_loc)
        gam = np.where(hax > 1, 2 * As / hax, 0)
        m = (x > 160) & (x < 300)
        # x where the 3D-fan gamma reaches the DM1A/DF1A calibrated break value (1.19-1.27)
        gb = 1.23
        hit = (x > 160) & (gam >= gb)
        ib = int(np.argmax(hit)) if hit.any() else None
        key = "T%g_%s" % (T, "nolens" if lens is None else "lens_xc%d_Rx%d_Ry%d_ht%g" % lens)
        o = dict(amp_focus_max=float(np.abs(A[0][m]).max()), x_amp_max=float(x[m][np.argmax(np.abs(A[0][m]))]),
                 x_b=None if ib is None else float(x[ib]), h_b=None if ib is None else float(hax[ib]))
        if ib is not None:
            Hc = 0.80 * hax[ib]
            sh = P.shape_at(tk, A, ib, Hc)
            o.update({k: sh[k] for k in ("W20", "W50", "W80", "W95", "K", "S2", "ring_max", "W50_m", "W80_m")}, Hc_pred=Hc)
            g2 = 2 * np.abs(A) / np.maximum(h, 1.0)
            o["early_lens"] = float(np.max(np.where((x[None, :] < x[ib] - 15) & (x[None, :] > 100), g2, 0)) / gb)
        res[key] = o
        print(key, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in o.items()}, flush=True)
elif which == "island":
    for (R, ht, a) in [(60.0, 0.0, 1.0), (100.0, 0.0, 1.0), (100.0, 3.0, 1.0)]:
        Lx, W = 640.0, 300.0
        x = np.arange(0, Lx + 1e-9, S.DX); y = np.arange(0, W + 1e-9, S.DX)
        h0 = 19.0
        h = h0 - M.mound(x, y, 260.0, R, R, h0 - ht, shape="cos2")
        tk, A1, AT = S.run_case(12.0, x, y, h, target_kind="plane", side=(W - 45.0, 1e9, 1e9 + 1), exit_x0=Lx - 100.0,
                                swash=(4.0, 2.0, 2), periods=34)
        Aa = np.abs(A1)
        lee = (x > 260 + R) & (x < Lx - 110)
        ax = Aa[0][lee]
        i = int(np.argmax(ax)); xl = float(x[lee][i])
        # lateral crossing angle from the lateral wavenumber: unwrap phase across y at xl
        jx = int(np.argmin(np.abs(x - xl)))
        prof = Aa[:, jx]
        jhalf = int(np.argmax(prof < 0.5 * prof[0])) if (prof < 0.5 * prof[0]).any() else -1
        # local direction spread: Fourier of A(y) at xl over |y| < 150
        yy = y[y < 150]
        Ay = A1[: len(yy), jx]
        full = np.concatenate([Ay[:0:-1], Ay])
        k0 = float(tk.k[0, jx])
        spec = np.abs(np.fft.fftshift(np.fft.fft(full * np.hanning(len(full)))))
        ky = np.fft.fftshift(np.fft.fftfreq(len(full), S.DX)) * 2 * math.pi
        th = np.degrees(np.arcsin(np.clip(ky / k0, -1, 1)))
        sp = spec / spec.max()
        thpk = float(abs(th[np.argmax(np.where(np.abs(th) > 5, sp, 0))]))
        key = "island_R%d_ht%g" % (R, ht)
        res[key] = dict(lee_amp_max=float(ax[i]), x_lee=xl, fwhm_lee_m=float(2 * y[jhalf]) if jhalf > 0 else None,
                        k0=k0, side_lobe_dir_deg=thpk, amp_far_side=float(Aa[-30, jx]))
        print(key, res[key], flush=True)
json.dump(res, open(os.path.join(S.OUT, "extra_%s.json" % which), "w"), indent=1, default=float)
print("wall", time.time() - t0)
