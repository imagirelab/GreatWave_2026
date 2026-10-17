# -*- coding: utf-8 -*-
"""Lee focus of an (almost) emergent shoal on a flat bed, plane swell: gain, lee spot shape metrics with the calibrated predictor,
side-feeding proxy, sensitivity to the half width (W 300 vs the FLIP-like 140 with a 45 m side band). py -3.10 -B [computed]"""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M, l51_screen as S, l51_pin as P
t0 = time.time()
res = {}
cases = json.loads(sys.argv[1])
for c in cases:
    T, h0, R, ht, W, xc = c
    Lx = xc + R + 260.0
    x = np.arange(0, Lx + 1e-9, S.DX); y = np.arange(0, W + 1e-9, S.DX)
    h = h0 - M.mound(x, y, xc, R, R, h0 - ht, shape="cos2")
    tk, A1, AT = S.run_case(T, x, y, h, target_kind="plane", side=(W - 45.0, 1e9, 1e9 + 1), exit_x0=Lx - 100.0, swash=(4.0, 2.0, 2), periods=34)
    Aa = np.abs(A1)
    lee = (x > xc + R) & (x < Lx - 110)
    i = int(np.argmax(Aa[0][lee])); ib = int(np.where(lee)[0][i]); xl = float(x[ib]); G = float(Aa[0, ib])
    L = 2 * math.pi / float(tk.k[0, ib])
    out = dict(case=c, gain_lee=G, x_lee=xl, dist_from_edge=xl - (xc + R), L=L)
    # break a_lin: Miche H_b = 0.142 L tanh(kh) -> a_b = H_b / 2 (linear focus amplitude at the steepness limit) [computed, 2D rule]
    kh = float(tk.k[0, ib] * h0)
    a_b = 0.5 * 0.142 * L * math.tanh(kh)
    out["a_lin_break"] = a_b; out["a_inc_needed"] = a_b / G
    for Hc in (0.65 * 2 * a_b, 0.75 * 2 * a_b):
        sh = P.shape_at(tk, A1, ib, Hc)
        out["Hc%.1f" % Hc] = {k: round(float(sh[k]), 3) for k in ("W20", "W50", "W80", "W95", "K", "taper", "S1", "S2", "ring_max", "Lx50", "A50", "W50_m", "W80_m", "W95_m")}
    # max gamma upstream of the island centre and on the flanks (early breaking of the unfocused swell) at a_inc_needed
    g2 = 2 * out["a_inc_needed"] * Aa / np.maximum(h, 0.5)
    out["gamma_max_flank_h_gt_6"] = float(np.max(np.where(h > 6.0, g2, 0)))
    # side-feeding proxy at the lee spot
    Fx, Fy = S.energy_flux(tk, A1)
    js = int(np.argmin(np.abs(y - 9.0)))
    cg = float(tk.cg[0, ib]); mx = (x >= xl - 2 * cg) & (x <= xl)
    infl = -np.trapz(Fy[js, mx], x[mx]) * 2; thr = np.trapz(Fx[:js + 1, ib], y[:js + 1]) * 2
    out["SF"] = float(infl / thr)
    # lateral directional content at the spot (ky spectrum of A(y))
    full = np.concatenate([A1[:0:-1, ib], A1[:, ib]])
    sp = np.abs(np.fft.fftshift(np.fft.fft(full * np.hanning(len(full)))))
    ky = np.fft.fftshift(np.fft.fftfreq(len(full), S.DX)) * 2 * math.pi
    k0 = float(tk.k[0, ib])
    m = np.abs(ky) <= k0
    th = np.degrees(np.arcsin(np.clip(np.abs(ky[m]) / k0, 0, 1)))
    e = sp[m] ** 2
    out["dir_rms_deg"] = float(np.sqrt(np.sum(e * th ** 2) / np.sum(e)))
    res[str(c)] = out
    np.savez_compressed(os.path.join(S.OUT, "lee_T%g_h%g_R%g_ht%g_W%g_A1.npz" % (T, h0, R, ht, W)), A=A1, x=x, y=y, h=h)
    print(json.dumps(out, default=float), flush=True)
json.dump(res, open(os.path.join(S.OUT, "lee_%s.json" % sys.argv[2]), "w"), indent=1, default=float)
print("wall", time.time() - t0)
