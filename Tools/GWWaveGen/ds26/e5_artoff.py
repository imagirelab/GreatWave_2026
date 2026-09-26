# E5 (review fixes 8/14): first estimate of the P14 "art-off" t* section on the main row (c = 0).
#   body = focused +-30 deg crossing group (linear + narrow-band 2nd order, lambda_p 195 m, crest = K* main crest 20.80 m),
#          i.e. the E2 physical body on the same clock (no width narrowing, no tube roof / hooks / claws);
#   lip  = forward-integrated ballistic flight (NOT inverse-solved to land on K*): release order and times as the default
#          (T_row = main row, p = 0.5, strip parking on the crest front), launch velocity = the median E1 re-solve profile
#          u/c0(s), w/sqrt(gH)(s) of all 133 rows (e4c_default_stats.json), pure ballistic after release.
# Compares with K* main row: tip position, overhang (def. A: inner wall at 0.3H -> tip), chamfer distance of the upper outline.
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e5_artoff.py   (needs e4c_default_stats.json from e4c_default_stats.py)
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
import sys, json, math
import numpy as np
from e4_common import *
import ds26_paths as DP
out = DP.outdir(DP.OUT_FEAS)
q = rows[i_main]; a = A[q['r']]; y = Y[q['r']]; H = q['H']; a_top = q['a_top']
prof = json.load(open(out + '/e4c_default_stats.json'))['new_default']['median_launch_profile']['upper']
sb = np.array([(p['s0'] + p['s1']) / 2 for p in prof]); ub = np.array([p['u_over_c0'] for p in prof]); wb = np.array([p['w_over_sqrtgH'] for p in prof])
cf = Cfg('d', rule='strip', floor=1.2, tr_rule='half')
T_row, Ti, off, K, d1, d2 = row_setup(q, cf)
upm = q['cols'] <= q['jtip']
s = q['s'][upm]; T = np.maximum(Ti[upm], 1e-4); offu = off[upm]
P = crest_g(T, q, T_row, cf) + offu
u = np.interp(s, sb, ub) * cf.c0; w = np.interp(s, sb, wb) * math.sqrt(g * H)
lip = np.stack([P[:, 0] + u * T, P[:, 1] + w * T - 0.5 * g * T ** 2], 1)      # ground at t* (= K* frame)
# body: focused group section along t through the crest top
lam = 195.0; fp = math.sqrt(g / (2 * math.pi * lam)); fq = np.linspace(0.5 * fp, 2.5 * fp, 256)
sj = np.where(fq <= fp, 0.07, 0.09)
Sp = fq ** -5 * np.exp(-1.25 * (fp / fq) ** 4) * 3.3 ** np.exp(-(fq - fp) ** 2 / (2 * sj * sj * fp * fp))
amp = np.sqrt(Sp); amp /= amp.sum(); kk = (2 * math.pi * fq) ** 2 / g; kx = kk * math.cos(math.radians(30))
xs = np.linspace(-60, 60, 2401)
e1 = (amp[None, :] * np.cos(np.outer(xs, kx))).sum(1); hil = (amp[None, :] * np.sin(np.outer(xs, kx))).sum(1)
kbar = (amp * kk).sum() / amp.sum(); AL = (-1 + math.sqrt(1 + 2 * kbar * H)) / kbar
body = AL * e1 + 0.5 * kbar * AL ** 2 * (e1 ** 2 - hil ** 2)
ab = a_top + xs
# overhang def. A for the art-off: inner wall = body front face at 0.3H
front = xs > 0
a03_off = float(np.interp(0.3 * H, body[front][::-1], ab[front][::-1]))
tip_i = int(np.argmax(lip[:, 0]))
jt, jtip = q['jt'], q['jtip']
w_ = np.arange(314, 395); k0 = np.where((y[w_][:-1] - 0.3 * H) * (y[w_][1:] - 0.3 * H) <= 0)[0][0]
a03_K = float(a[w_][k0] + (0.3 * H - y[w_][k0]) / (y[w_][k0 + 1] - y[w_][k0]) * (a[w_][k0 + 1] - a[w_][k0]))
def chamfer(P1, P2):
    d = np.sqrt(((P1[:, None, :] - P2[None, :, :]) ** 2).sum(-1))
    return float(np.sqrt(0.5 * (np.mean(d.min(1) ** 2) + np.mean(d.min(0) ** 2)))), float(max(d.min(1).max(), d.min(0).max()))
Kup = np.stack([a[jt:jtip + 1], y[jt:jtip + 1]], 1)
ch_lip = chamfer(lip, Kup)
# whole upper outline: back face (a < a_top) + lip, vs K* back face + lip
Kback = np.stack([a[18:jt + 1], y[18:jt + 1]], 1)
Oback = np.stack([ab[(ab >= a[18]) & (ab <= a_top)], body[(ab >= a[18]) & (ab <= a_top)]], 1)
ch_all = chamfer(np.concatenate([Oback, lip]), np.concatenate([Kback, Kup]))
res = dict(row_c=q['c'], H=H, T_row=T_row,
           artoff_tip=dict(a=float(lip[tip_i, 0]), y=float(lip[tip_i, 1]), y_over_H=float(lip[tip_i, 1] / H), a_minus_top=float(lip[tip_i, 0] - a_top)),
           kstar_tip=dict(a=float(a[jtip]), y=float(y[jtip]), y_over_H=float(y[jtip] / H), a_minus_top=float(a[jtip] - a_top)),
           artoff_overhang_A_over_H=float((lip[tip_i, 0] - a03_off) / H), kstar_overhang_A_over_H=float((a[jtip] - a03_K) / H),
           artoff_body_footprint_m=float(np.ptp(ab[body > 0.02 * H][[0, -1]])) if (body > 0.02 * H).any() else None,
           lip_upper_chamfer_rms_max_m=ch_lip, upper_outline_chamfer_rms_max_m=ch_all,
           artoff_back_slope_deg=float(np.degrees(np.arctan(np.abs(np.gradient(body, xs))[(xs < 0) & (body > 0.1 * H) & (body < 0.9 * H)].mean()))),
           kstar_back_slope_deg=float(np.degrees(np.arctan((0.8 * H) / max(1e-6, np.interp(0.9 * H, y[18:jt + 1], a[18:jt + 1]) - np.interp(0.1 * H, y[18:jt + 1], a[18:jt + 1]))))))
print(json.dumps(res, indent=1))
json.dump(res, open(out + '/e5_artoff.json', 'w'), indent=1)
np.savez(out + '/e5_artoff_section.npz', lip=lip, body_a=ab, body_y=body, K_a=a, K_y=y, jt=jt, jtip=jtip)
