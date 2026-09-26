# E2: how far is K* from a physically generated body? (設計26 feasibility; experiment)
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e2_residual.py --sim <profiles_main_lateral.npz>
#                         py -3.12 -B Tools/GWWaveGen/ds26/e2_residual.py --skip-sim   ((a)(b) だけ → e2_result_nosim.json)
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
# ** (c) にはリポジトリ外の入力が要る **：利用者の Houdini 解算（1.abc）から作った断面の npz（profiles_main_lateral.npz、
#   SHA-256 17def6da6460bcac74824985cadc57ae3b3194df411cd6271d2862be995224e2、リポジトリ外・本機のみ）。
#   --sim <path> か環境変数 GW_DS26_SIM_NPZ で渡す。無ければはっきり止まる（ds26_paths.sim_npz）。npz はリポジトリへ複製しない。
# (a) focused two-system crossing group (+-30 deg), linear + narrow-band 2nd order, section along the bisector at focus,
#     scaled so that crest = K* main-row crest (20.80 m): geometry vs K*, vertical residual on K*'s single-valued envelope.
# (b) carrier amplitude that makes the K* tower volume-neutral per row (tower water taken from the carrier crest).
# (c) the user's Houdini sim late profiles (derived normalized polylines only) scaled to K*: isotropic Froude scaling vs
#     best anisotropic horizontal factor, symmetric chamfer distance.
import sys, json, math
import numpy as np

g = 9.81
import ds26_paths as DP
SKIP_SIM = '--skip-sim' in sys.argv[1:]
kz, out = DP.kstar_rows(), DP.outdir(DP.OUT_FEAS)
simz = None if SKIP_SIM else DP.sim_npz()
d = np.load(kz); A, Y, C = d['A'], d['Y'], d['c']
r0 = int(np.argmin(np.abs(C)))
a0, y0 = A[r0], Y[r0]
H = y0.max(); a_top = a0[np.argmax(y0)]
res = {}

def envelope(a, y, grid):
    # upper single-valued envelope of a polyline (max y over segments crossing each grid a)
    e = np.zeros_like(grid)
    for i in range(len(a) - 1):
        lo, hi = sorted((a[i], a[i + 1]))
        m = (grid >= lo) & (grid <= hi)
        if not m.any():
            continue
        if hi - lo < 1e-9:
            e[m] = np.maximum(e[m], max(y[i], y[i + 1])); continue
        t = (grid[m] - a[i]) / (a[i + 1] - a[i])
        e[m] = np.maximum(e[m], y[i] + t * (y[i + 1] - y[i]))
    return e

def signed_area(a, y):
    # area above SWL enclosed by the section contour and y=0 (shoelace, contour from back margin to front margin)
    return float(np.sum((a[1:] - a[:-1]) * (y[1:] + y[:-1]) / 2.0))

grid = np.linspace(a0.min(), a0.max(), 4001)
envK = envelope(a0, y0, grid)
areaK = signed_area(a0, y0)
fp_back = a0[18]; fp_front = a0[394]
res['kstar_main'] = dict(H=float(H), a_top=float(a_top), area_above_swl_m2=areaK, footprint_m=float(fp_front - fp_back),
                         sheet_a_range=[float(a0.min()), float(a0.max())])

def jonswap(f, fp, gamma=3.3):
    s = np.where(f <= fp, 0.07, 0.09)
    return f ** -5 * np.exp(-1.25 * (fp / f) ** 4) * gamma ** np.exp(-(f - fp) ** 2 / (2 * s * s * fp * fp))

def group_section(lam_p, half_angle_deg, crest_target, xs):
    fp = math.sqrt(g / (2 * math.pi * lam_p))
    f = np.linspace(0.5 * fp, 2.5 * fp, 256)
    S = jonswap(f, fp); amp = np.sqrt(S); amp /= amp.sum()
    k = (2 * math.pi * f) ** 2 / g
    kx = k * math.cos(math.radians(half_angle_deg))
    # linear surface at focus time along the bisector, both systems (equal), unit crest
    phase = np.outer(xs, kx)
    eta1 = (amp[None, :] * np.cos(phase)).sum(1)
    hil = (amp[None, :] * np.sin(phase)).sum(1)
    kbar = (amp * k).sum() / amp.sum()
    # solve A_L so that crest (eta1+eta2 at 0) = target; eta2 = kbar/2*(A^2)(eta1^2 - hil^2) (narrow-band, Tayfun)
    # crest: A + kbar/2*A^2 = target
    AL = (-1 + math.sqrt(1 + 2 * kbar * crest_target)) / kbar
    eta = AL * eta1 + 0.5 * kbar * AL ** 2 * (eta1 ** 2 - hil ** 2)
    return eta, AL, kbar, fp

xs = np.linspace(-400, 400, 16001)
grp = {}
for lam in (200.0, 250.0, 290.0):
    eta, AL, kbar, fp = group_section(lam, 30.0, H, xs)
    # geometry
    i0 = np.argmin(np.abs(xs))
    zc = np.where(np.diff(np.sign(eta)) != 0)[0]
    zf = xs[zc[zc > i0][0]]; zb = xs[zc[zc < i0][-1]]
    slope = np.degrees(np.arctan(np.abs(np.gradient(eta, xs))))
    m_hump = (xs >= zb) & (xs <= zf)
    tr_front = eta[(xs > zf) & (xs < zf + lam)].min(); tr_back = eta[(xs < zb) & (xs > zb - lam)].min()
    # residual vs K* (shift group crest to K* crest top)
    etaK = np.interp(grid - a_top, xs, eta)
    fpm = (grid >= fp_back) & (grid <= fp_front)
    resid = envK - etaK
    area_grp_sheet = float(np.trapezoid(np.clip(etaK, 0, None), grid))
    grp[f'lambda_{int(lam)}'] = dict(
        A_linear_m=AL, kA_linear=float(kbar * AL), crest_m=float(eta[i0]), hump_width_swl_m=float(zf - zb),
        max_slope_deg_in_hump=float(slope[m_hump].max()), trough_front_m=float(tr_front), trough_back_m=float(tr_back),
        hump_area_m2=float(np.trapezoid(eta[m_hump], xs[m_hump])),
        resid_on_kstar_footprint_rms_m=float(np.sqrt(np.mean(resid[fpm] ** 2))), resid_on_kstar_footprint_max_abs_m=float(np.abs(resid[fpm]).max()),
        resid_on_sheet_rms_m=float(np.sqrt(np.mean(resid ** 2))), resid_on_sheet_max_abs_m=float(np.abs(resid).max()),
        group_area_above_swl_over_sheet_m2=area_grp_sheet,
        footprint_ratio_kstar_over_group=float((fp_front - fp_back) / (zf - zb)))
res['focused_group_vs_kstar'] = grp

# (b) volume-neutral carrier amplitude per row: carrier = Ac*cos(k_eff*(a - a_top_row)) over the sheet (lambda 200, 250)
vb = {}
for lam in (200.0, 250.0):
    keff = 2 * math.pi / lam * math.cos(math.radians(30))
    Acs = []; ratio = []
    for r in range(A.shape[0]):
        ar, yr = A[r], Y[r]
        if yr.max() < 3.0:
            continue
        areaR = signed_area(ar, yr)
        at = ar[np.argmax(yr)]
        integ = (math.sin(keff * (ar.max() - at)) - math.sin(keff * (ar.min() - at))) / keff
        Ac = areaR / integ
        Acs.append(Ac); ratio.append(Ac / yr.max())
    Acs = np.array(Acs); ratio = np.array(ratio)
    vb[f'lambda_{int(lam)}'] = dict(Ac_m_p5_p50_p95=[float(x) for x in np.percentile(Acs, [5, 50, 95])],
                                    Ac_over_rowH_p5_p50_p95=[float(x) for x in np.percentile(ratio, [5, 50, 95])],
                                    main_row_Ac_m=float(areaK / ((math.sin(keff * (a0.max() - a_top)) - math.sin(keff * (a0.min() - a_top))) / keff)))
res['volume_neutral_carrier'] = vb

if SKIP_SIM:
    res['sim_profile_vs_kstar'] = 'skipped (--skip-sim): needs the sim-derived npz kept outside the repo'
    json.dump(res, open(out + '/e2_result_nosim.json', 'w'), indent=1)
    print(json.dumps(res, indent=1)[:6000])
    sys.exit(0)
# (c) user's sim late profiles vs K* main row (derived polylines only)
sz = np.load(simz)
def chamfer(P, Q):
    dPQ = np.sqrt(((P[:, None, :] - Q[None, :, :]) ** 2).sum(-1))
    return float(np.sqrt(0.5 * (np.mean(dPQ.min(1) ** 2) + np.mean(dPQ.min(0) ** 2)))), float(max(dPQ.min(1).max(), dPQ.min(0).max()))
def resample(P, n=500):
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], 1)
K = np.stack([a0, y0], 1)
K = K[(K[:, 1] > 0.3)]
K = resample(K)
simres = {}
for sN in (45, 48, 51, 54):
    P = sz[f'main_s{sN:02d}_m'].astype(float)
    P = P[P[:, 1] > 0.05]
    xc = P[np.argmax(P[:, 1]), 0]
    Hs = P[:, 1].max()
    sc = H / Hs
    Pi = np.stack([(P[:, 0] - xc) * sc + a_top, P[:, 1] * sc], 1)
    Pi = Pi[Pi[:, 1] > 0.3]
    Pi = resample(Pi)
    iso = chamfer(Pi, K)
    best = None
    for f in np.linspace(0.15, 1.2, 43):
        for sh in np.linspace(-6, 6, 25):
            Pa = Pi.copy(); Pa[:, 0] = (Pa[:, 0] - a_top) * f + a_top + sh
            ch = chamfer(Pa, K)
            if best is None or ch[0] < best[0]:
                best = (ch[0], ch[1], f, sh)
    # crop both to K*'s footprint region to be fair (sim back face is ~23 m long)
    simres[f's{sN}'] = dict(t_sim_s=(sN + 1) / 24, scale_len=sc, time_scale=math.sqrt(sc),
                           iso_chamfer_rms_m=iso[0], iso_chamfer_max_m=iso[1],
                           aniso_best_f=best[2], aniso_best_shift_m=best[3], aniso_chamfer_rms_m=best[0], aniso_chamfer_max_m=best[1])
res['sim_profile_vs_kstar'] = simres
json.dump(res, open(out + '/e2_result.json', 'w'), indent=1)
print(json.dumps(res, indent=1)[:6000])
