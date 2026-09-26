# E6 (review fix 6): PaintingCam v1 frustum footprint on the sea plane at t*, occlusion by K*, and the carrier / swell
# elevation there -> image displacement in display px.  Experiment, numpy only.  K* read only.
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e6_painting_sea.py
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
# PaintingCam v1 (Tools/PaintingTruth/painting_truth.json): pos (0,3,-62), target (-2.5,9.7,4), Unity LookAt, vFOV 26 deg,
# 1920x1080, painting columns 157..1762.  K* frame (kstar_a45_meta.json): world = origin + a*t + c*e (+ y up).
# Carrier at t* = two linear JONSWAP groups (gamma 3.3, lambda_p 195 m, deep water), unidirectional at +-30 deg from t,
# focused at the section origin at t*, scaled so the combined linear crest at focus = A_c = 3.0 m (E2 volume-neutral carrier).
# Also the monochromatic E2 carrier A_c cos(k cos30 a) cos(k sin30 c) (upper bound).  The hero sheet itself is K* at t*.
import sys, json, math
import numpy as np

import ds26_paths as DP
kdir, out = DP.kstar_dir(), DP.outdir(DP.OUT_FEAS)
meta = json.load(open(kdir + '/kstar_a45_meta.json', encoding='utf-8'))
rz = np.load(kdir + '/kstar_a45_rows.npz'); A, Y, C = rz['A'], rz['Y'], rz['c']
fr = meta['frame']; O = np.array(fr['section_origin_world']); tv = np.array(fr['t_travel']); ev = np.array(fr['e_crest'])
g = 9.81
pos = np.array([0.0, 3.0, -62.0]); tgt = np.array([-2.5, 9.7, 4.0]); up = np.array([0.0, 1.0, 0.0])
f = (tgt - pos) / np.linalg.norm(tgt - pos); rt = np.cross(up, f); rt /= np.linalg.norm(rt); u2 = np.cross(f, rt)
W, Hh = 1920, 1080; th = math.tan(math.radians(13.0)); tw = th * W / Hh
fpx = (Hh / 2) / th                                                     # focal length in px

def project(P):  # world (...,3) -> display px (x, y down, pixel centres integer)
    d = P - pos; z = d @ f; x = d @ rt; yy = d @ u2
    return np.stack([(x / z / tw + 1) / 2 * W - 0.5, (1 - (yy / z / th + 1) / 2) * Hh - 0.5], -1), z

STEP = 4
xs = np.arange(157, 1763, STEP); ys = np.arange(0, Hh, STEP)
PX, PY = np.meshgrid(xs, ys)
vx = (PX + 0.5) / W; vy = 1 - (PY + 0.5) / Hh
D = f[None, None, :] + ((2 * vx - 1) * tw)[..., None] * rt[None, None, :] + ((2 * vy - 1) * th)[..., None] * u2[None, None, :]
sea = D[..., 1] < 0
s_hit = np.where(sea, -pos[1] / np.where(sea, D[..., 1], -1), np.inf)
HIT = pos[None, None, :] + s_hit[..., None] * D
depth = s_hit * (D @ f)
sea &= depth <= 900.0

# K* heightfield (upper envelope per row on an a-grid), sheet domain
ag = np.linspace(A.min(), A.max(), 1641)
env = np.zeros((len(C), len(ag)))
for r in range(len(C)):
    a, y = A[r], Y[r]
    for i in range(len(a) - 1):
        lo, hi = sorted((a[i], a[i + 1]))
        m = (ag >= lo) & (ag <= hi)
        if m.any():
            tt = (ag[m] - a[i]) / (a[i + 1] - a[i] + 1e-12)
            env[r, m] = np.maximum(env[r, m], y[i] + tt * (y[i + 1] - y[i]))
amin_r = A.min(1); amax_r = A.max(1)
def to_ac(P):
    d = P - O; return d @ tv, d @ ev
def h_at(a, c):
    ci = np.interp(c, C, np.arange(len(C))); ai = np.interp(a, ag, np.arange(len(ag)))
    i0 = np.clip(np.floor(ci).astype(int), 0, len(C) - 2); j0 = np.clip(np.floor(ai).astype(int), 0, len(ag) - 2)
    fc = ci - i0; fa = ai - j0
    hv = (env[i0, j0] * (1 - fc) * (1 - fa) + env[i0 + 1, j0] * fc * (1 - fa) + env[i0, j0 + 1] * (1 - fc) * fa + env[i0 + 1, j0 + 1] * fc * fa)
    inside = (c >= C.min()) & (c <= C.max()) & (a >= np.interp(c, C, amin_r)) & (a <= np.interp(c, C, amax_r))
    return np.where(inside, hv, -1.0), inside
# occlusion: march each ray from the camera to its sea hit (or 300 m for sky rays) and test y_ray < h
occl = np.zeros(sea.shape, bool)
smax = np.where(sea, s_hit, 300.0)
for k in np.linspace(0.02, 1.0, 400):
    P = pos[None, None, :] + (k * smax)[..., None] * D
    a_, c_ = to_ac(P); h_, ins = h_at(a_, c_)
    occl |= ins & (P[..., 1] < h_) & (k * smax < smax - 0.05)
a_h, c_h = to_ac(HIT)
_, on_sheet = h_at(a_h, c_h)
vis_sea = sea & ~occl                          # sea visible at all (sheet or surrounding)
vis_out = vis_sea & ~on_sheet                  # visible surrounding sea (outside the hero sheet)
hero = occl | (sea & on_sheet)                 # pixels showing the hero sheet (wave body or its flat margins)

# carrier fields at t*
lam = 195.0; kp = 2 * math.pi / lam; Ac = 3.0
fp = math.sqrt(g / (2 * math.pi * lam)); fq = np.linspace(0.5 * fp, 2.5 * fp, 200)
sj = np.where(fq <= fp, 0.07, 0.09)
Sp = fq ** -5 * np.exp(-1.25 * (fp / fq) ** 4) * 3.3 ** np.exp(-(fq - fp) ** 2 / (2 * sj * sj * fp * fp))
amp = np.sqrt(Sp); amp /= amp.sum(); kk = (2 * math.pi * fq) ** 2 / g
d1 = np.array([math.cos(math.radians(30)), math.sin(math.radians(30))]); d2 = np.array([math.cos(math.radians(30)), -math.sin(math.radians(30))])
def eta_group(a, c):
    x1 = a * d1[0] + c * d1[1]; x2 = a * d2[0] + c * d2[1]
    e = np.zeros_like(a)
    for n in range(len(kk)):
        e += amp[n] * (np.cos(kk[n] * x1) + np.cos(kk[n] * x2))
    return Ac / 2 * e                           # combined crest at focus = Ac
def eta_mono(a, c):
    return Ac * np.cos(kp * math.cos(math.radians(30)) * a) * np.cos(kp * math.sin(math.radians(30)) * c)
res = dict(step_px=STEP, n_px=int(PX.size), frac_sea=float(sea.mean()), frac_hero=float(hero.mean()),
           frac_visible_surrounding_sea=float(vis_out.mean()), frac_visible_sheet_flat=float((vis_sea & on_sheet).mean()))
Pv = HIT[vis_out]; av, cv = a_h[vis_out], c_h[vis_out]; dv = depth[vis_out]
res['visible_surrounding_sea_depth_m'] = [float(dv.min()), float(np.percentile(dv, 50)), float(dv.max())]
res['visible_surrounding_sea_world_XZ_bbox'] = [float(Pv[:, 0].min()), float(Pv[:, 0].max()), float(Pv[:, 2].min()), float(Pv[:, 2].max())]
near = dv <= 300
res['visible_surrounding_sea_within_300m_world_XZ_bbox'] = [float(Pv[near, 0].min()), float(Pv[near, 0].max()), float(Pv[near, 2].min()), float(Pv[near, 2].max())]
res['visible_surrounding_sea_a_c_range_within_300m'] = [float(av[near].min()), float(av[near].max()), float(cv[near].min()), float(cv[near].max())]
for lab, fn in (('group', eta_group), ('mono', eta_mono)):
    e = fn(av, cv)
    P1 = Pv.copy(); P1[:, 1] = e
    p0, _ = project(Pv); p1, _ = project(P1)
    dpx = np.abs(p1[:, 1] - p0[:, 1])
    # slope (finite difference in world)
    hx = 0.5
    sx = (fn(av + hx, cv) - fn(av - hx, cv)) / (2 * hx); sc = (fn(av, cv + hx) - fn(av, cv - hx)) / (2 * hx)
    slope = np.degrees(np.arctan(np.hypot(sx, sc)))
    res['carrier_' + lab] = dict(eta_min_m=float(e.min()), eta_max_m=float(e.max()), eta_absmax_within_300m=float(np.abs(e[near]).max()),
                                 dpx_max=float(dpx.max()), dpx_p95=float(np.percentile(dpx, 95)), frac_px_over_0p5=float(np.mean(dpx > 0.5)),
                                 slope_max_deg=float(slope.max()),
                                 where_dpx_max_world=[float(Pv[np.argmax(dpx), 0]), float(Pv[np.argmax(dpx), 2])])
# trough behind the wave (a = -lambda_t/2 on the main line) and the next crossing peak
lt = lam / math.cos(math.radians(30))
for lab, (a0, c0) in (('trough_behind_main_line', (-lt / 2, 0.0)), ('trough_ahead_main_line', (lt / 2, 0.0)),
                      ('next_crossing_peak_minus_c', (lt / 2, -lam)), ('next_crossing_peak_plus_c', (lt / 2, lam))):
    Pw = O + a0 * tv + c0 * ev
    px, z = project(Pw[None, :])
    inside = bool((157 <= px[0, 0] <= 1762) and (0 <= px[0, 1] <= 1079) and z[0] > 0)
    # visible? test the pixel's occlusion state
    vis = None
    if inside:
        ix = int(np.argmin(np.abs(xs - px[0, 0]))); iy = int(np.argmin(np.abs(ys - px[0, 1])))
        vis = bool(vis_out[iy, ix])
    res[lab] = dict(a=a0, c=c0, world_XZ=[float(Pw[0]), float(Pw[2])], display_px=[float(px[0, 0]), float(px[0, 1])], in_painting_frame=inside,
                    visible_not_occluded=vis, eta_group_m=float(eta_group(np.array([a0]), np.array([c0]))[0]), eta_mono_m=float(eta_mono(np.array([a0]), np.array([c0]))[0]))
# tolerance: |eta| giving 0.5 px at the visible surrounding-sea points
P1 = Pv.copy(); P1[:, 1] = 1.0
p0, _ = project(Pv); p1, _ = project(P1); dpx1 = np.abs(p1[:, 1] - p0[:, 1])
res['eta_for_0p5px_m'] = dict(min=float((0.5 / dpx1).min()), p50=float(np.median(0.5 / dpx1)), note='|eta| that moves the visible surface point by 0.5 display px')
res['swell_Hs5_rms1p25_dpx'] = dict(p50=float(np.median(1.25 * dpx1)), max=float((1.25 * dpx1).max()))
print(json.dumps(res, indent=1))
json.dump(res, open(out + '/e6_painting_sea.json', 'w'), indent=1)
np.savez_compressed(out + '/e6_masks.npz', xs=xs, ys=ys, hero=hero, vis_out=vis_out, sea=sea)
