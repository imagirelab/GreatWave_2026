# E4c: statistics of the E1 re-solve for the new default (strip parking, floor 1.2 s, ramp min(0.6, T_i/2)).
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e4c_default_stats.py
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
import sys, json, math
import numpy as np
from e4_common import *
import ds26_paths as DP
out = DP.outdir(DP.OUT_FEAS)
res = {}
for name, cf in (('new_default', Cfg('d', rule='strip', floor=1.2, tr_rule='half')), ('E1_default', Cfg('e', rule='point', floor=0.3))):
    U = []; W = []; Hs = []; ok = []; m = []; cs = []; su = []; Ti = []; T_rows = []; tipu = []; tipw = []; dv = []
    for q in rows:
        R = ramp_solve(q, cf); mm, oo = plaus(q, R, cf)
        U.append(R['ub']); W.append(R['wb']); Hs.append(np.full(len(R['ub']), q['H'])); ok.append(oo); m.append(mm); cs.append(np.full(len(R['ub']), q['c']))
        su.append(q['cols'] > q['jtip']); Ti.append(R['Tc']); T_rows.append(R['T_row'])
        it = int(np.where(q['cols'] == q['jtip'])[0][0]); tipu.append(R['ub'][it] / cf.c0); tipw.append(R['wb'][it])
        ci = R['ci']; dv.append(np.hypot(R['ub'] - ci, R['wb'] - cf.vH))
    U, W, Hs, ok, m, cs, su, Ti, dv = map(np.concatenate, (U, W, Hs, ok, m, cs, su, Ti, dv))
    un = U / cf.c0; wn = W / np.sqrt(g * Hs); bad = m & ~ok
    res[name] = dict(frac_ok=float(ok[m].mean()), n_eval=int(m.sum()), n_bad=int(bad.sum()),
                     bad_reason=dict(u_high=int((bad & (un > 1.3)).sum()), u_low=int((bad & (un < 0.6)).sum()), w_high=int((bad & (wn > 0.8)).sum()), w_low=int((bad & (wn < -0.2)).sum())),
                     bad_rows_c=[round(float(x), 1) for x in np.unique(np.round(cs[bad], 1))][:20], bad_underside=int((bad & su).sum()),
                     bad_release_tau_range=([round(float(-Ti[bad].max()), 2), round(float(-Ti[bad].min()), 2)] if bad.any() else None),
                     u_over_c0_p5_p50_p95=[round(float(x), 3) for x in np.percentile(un[m], [5, 50, 95])],
                     w_mps_p5_p50_p95=[round(float(x), 2) for x in np.percentile(W[m], [5, 50, 95])],
                     w_over_sqrtgH_p5_p50_p95=[round(float(x), 3) for x in np.percentile(wn[m], [5, 50, 95])],
                     tip_u_over_c0_p50=float(np.median(tipu)), tip_u_over_c0_main=float(tipu[i_main]), tip_w_main=float(tipw[i_main]),
                     dv_p50_p95=[float(np.percentile(dv[m], 50)), float(np.percentile(dv[m], 95))],
                     T_row_min=float(min(T_rows)), T_row_max=float(max(T_rows)))
    # median launch velocity profile vs s (for the art-off lip, P14): bins of s on upper / underside
    prof = {}
    S_all = np.concatenate([q['s'] for q in rows])
    for surf, msk in (('upper', ~su), ('under', su)):
        bins = np.linspace(0, 1, 11); rowsb = []
        for b0, b1 in zip(bins[:-1], bins[1:]):
            k = m & msk & (S_all >= b0) & (S_all < b1)
            if k.sum() > 20:
                rowsb.append(dict(s0=round(b0, 2), s1=round(b1, 2), n=int(k.sum()), u_over_c0=round(float(np.median(un[k])), 3), w_over_sqrtgH=round(float(np.median(wn[k])), 3)))
        prof[surf] = rowsb
    res[name]['median_launch_profile'] = prof
print(json.dumps(res, indent=1))
json.dump(res, open(out + '/e4c_default_stats.json', 'w'), indent=1)
