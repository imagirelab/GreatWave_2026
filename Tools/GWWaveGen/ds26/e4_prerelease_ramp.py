# E4 main: plausibility (E1 re-solve from parked start points), all-row release-ramp acceleration, tip apex, tip trajectories.
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e4_prerelease_ramp.py   (model in e4_common.py; mesh checks in e4b_mesh.py)
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
import sys, json, math
import numpy as np
from e4_common import *
import ds26_paths as DP
out = DP.outdir(DP.OUT_FEAS)

cfgs = [
    Cfg('A0 point Tr0.6 (E1/E3, reviewer reproduction)', rule='point'),
    Cfg('A1 point Tr0.8', rule='point', Tr=0.8),
    Cfg('B1 strip Tr0.6', rule='strip'),
    Cfg('B2 strip Tr=min(0.6,Ti/2)', rule='strip', tr_rule='half'),
    Cfg('B3 strip Tr0.6 floor1.2', rule='strip', floor=1.2),
    Cfg('B4 strip Tr0.6 peel30', rule='strip', vpeel=30.0),
    Cfg('B5 strip Tr=min(0.6,Ti/2) floor1.2', rule='strip', tr_rule='half', floor=1.2),
    Cfg('B6 strip Tr0.6 floor1.2 peel30', rule='strip', floor=1.2, vpeel=30.0),
]
results = [run_cfg(cf) for cf in cfgs]
for rr in results:
    print(json.dumps({k: rr[k] for k in ('name', 'frac_plausible', 'accel_ground_g', 'accel_rowcrest_frame_g', 'worst5', 'exceed_rows_c_range', 'exceed_release_tau_max')}))
    print('   tip', json.dumps(rr['tip']))

# E1 re-solve sensitivity with the strip rule (pure ballistic plausibility, Tr irrelevant)
sens = []
for tau0 in (1.6, 2.0, 2.4, 2.8):
    for vpeel in (20.0, 30.0):
        for floor in (0.3, 1.2):
            cf = Cfg('s', rule='strip', tau0=tau0, vpeel=vpeel, floor=floor)
            n_ev = n_ok = 0
            for q in rows:
                R = ramp_solve(q, cf); m, ok = plaus(q, R, cf); n_ev += m.sum(); n_ok += (ok & m).sum()
            sens.append(dict(tau0=tau0, vpeel=vpeel, floor=floor, frac=float(n_ok / n_ev)))
for delta in (0.01, 0.02, 0.04):
    cf = Cfg('s', rule='strip', delta=delta, floor=1.2)
    n_ev = n_ok = 0
    for q in rows:
        R = ramp_solve(q, cf); m, ok = plaus(q, R, cf); n_ev += m.sum(); n_ok += (ok & m).sum()
    sens.append(dict(tau0=2.4, vpeel=20.0, floor=1.2, delta=delta, frac=float(n_ok / n_ev)))
print('sens', json.dumps(sens))

# tip trajectories for the time-warp gate (default config): tau grid 1 ms, all curled rows
cfd = Cfg('default', rule='strip', floor=1.2, tr_rule='half')
Tg = np.arange(0, 5.0 + 1e-9, 0.001)[::-1]
tipY = []; tipV = []; tipA = []; tipRel = []; crY = []
for q in rows:
    R = ramp_solve(q, cfd)
    it = int(np.where(q['cols'] == q['jtip'])[0][0])
    sub = {k: (v[it:it + 1] if isinstance(v, np.ndarray) and v.ndim >= 1 and len(v) == len(R['Tc']) else v) for k, v in R.items()}
    X, V, Aa = state(q, cfd, sub, Tg)
    tipY.append(X[0, :, 1]); tipV.append(V[0, :, 1]); tipA.append(Aa[0, :, 1]); tipRel.append(-R['Tc'][it]); crY.append(q['H'] - cfd.vH * Tg)
np.savez(out + '/e4_tip_traj.npz', tau=-Tg, y=np.array(tipY), vy=np.array(tipV), ay=np.array(tipA), release_tau=np.array(tipRel),
         crest_y=np.array(crY), c=np.array([q['c'] for q in rows]), H=np.array([q['H'] for q in rows]), i_main=i_main, i_pk=i_pk)
json.dump(dict(n_rows=len(rows), c_pk=c_pk, main_c=rows[i_main]['c'], peak_c=rows[i_pk]['c'], configs=results, e1_strip_sensitivity=sens,
               notes='accel = max |a| over (release, t*) per vertex with T_i >= 0.15 s, 400 samples minus 3 at each end; '
                                 'ground frame = inertial; row-crest frame = ground minus the row crest deceleration (1-beta)c0/T_row. '
                                 'Mesh proxies: back face = K* lowered by vH*T; tube roof columns after the rim = parked on the face then smoothstep '
                                 'to K* from the row onset (stand-in for the design-27 rig).'),
          open(out + '/e4_result.json', 'w'), indent=1, default=float)
