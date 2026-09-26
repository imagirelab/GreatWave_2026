# E2c: user's sim late main-section profiles (derived polylines) vs K* main row, windowed around the crest.
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e2c_sim_window.py --sim <profiles_main_lateral.npz>
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
# ** リポジトリ外の入力が要る **：利用者の Houdini 解算（1.abc）から作った断面の npz（profiles_main_lateral.npz、
#   SHA-256 17def6da6460bcac74824985cadc57ae3b3194df411cd6271d2862be995224e2、リポジトリ外・本機のみ）。
#   --sim <path> か環境変数 GW_DS26_SIM_NPZ で渡す。無ければはっきり止まる（ds26_paths.sim_npz）。npz はリポジトリへ複製しない。
import sys, json, math
import numpy as np
import ds26_paths as DP
d = np.load(DP.kstar_rows()); sz = np.load(DP.sim_npz()); out = DP.outdir(DP.OUT_FEAS)
A, Y, C = d['A'], d['Y'], d['c']; r0 = int(np.argmin(np.abs(C)))
a0, y0 = A[r0], Y[r0]; H = y0.max(); at = a0[np.argmax(y0)]
def resample(P, n=400):
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))]); t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], 1)
def chamfer(P, Q):
    dd = np.sqrt(((P[:, None, :] - Q[None, :, :]) ** 2).sum(-1))
    return float(np.sqrt(0.5 * (np.mean(dd.min(1) ** 2) + np.mean(dd.min(0) ** 2)))), float(max(dd.min(1).max(), dd.min(0).max()))
K = np.stack([a0, y0], 1); K = resample(K[K[:, 1] > 0.3 * H * 0 + 1.0])
res = {}
for sN in (45, 48, 51, 54):
    P = sz[f'main_s{sN:02d}_m'].astype(float)
    Hs = P[:, 1].max(); xc = P[np.argmax(P[:, 1]), 0]; sc = H / Hs
    W = P[(P[:, 0] > xc - 1.5 * Hs) & (P[:, 0] < xc + 1.5 * Hs) & (P[:, 1] > 1.0 / sc)]
    Pi = np.stack([(W[:, 0] - xc) * sc + at, W[:, 1] * sc], 1); Pi = resample(Pi)
    iso = chamfer(Pi, K)
    best = None
    for f in np.linspace(0.1, 1.5, 57):
        for sh in np.linspace(-8, 8, 33):
            Pa = Pi.copy(); Pa[:, 0] = (Pa[:, 0] - at) * f + at + sh
            ch = chamfer(Pa, K)
            if best is None or ch[0] < best[0]: best = (ch[0], ch[1], f, sh)
    # footprint-like width at 0.3 H (sim) vs K*
    def width_at(Pw, level):
        m = Pw[:, 1] >= level; xs = Pw[m, 0]; return float(xs.max() - xs.min()) if m.any() else None
    res[f's{sN}'] = dict(len_scale=sc, time_scale=math.sqrt(sc), iso_rms_m=iso[0], iso_max_m=iso[1], best_f=best[2], best_shift_m=best[3],
                         aniso_rms_m=best[0], aniso_max_m=best[1],
                         width_at_0p3H_sim_scaled_m=width_at(np.stack([(P[:, 0] - xc) * sc, P[:, 1] * sc], 1), 0.3 * H),
                         width_at_0p3H_kstar_m=width_at(np.stack([a0, y0], 1), 0.3 * H))
json.dump(res, open(out + '/e2c_result.json', 'w'), indent=1); print(json.dumps(res, indent=1))
