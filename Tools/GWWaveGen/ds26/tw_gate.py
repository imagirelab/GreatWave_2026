# Time-warp gate in EXPERIENCE time (review fix 1): apparent vertical acceleration of each curled row's lip tip
#   A(t) = Y''(tau) r(t)^2 + Y'(tau) r'(t),  r = dtau/dt
# must stay <= 0 from the end of the tip's launch ramp to t*, except inside the final freeze ramp (<= 0.5 s).
# Also: on-screen fall time from the tip apex to t*, apparent g, event table (tau -> t) for the draft's §3.
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/tw_gate.py   (needs e4_tip_traj.npz from e4_prerelease_ramp.py)
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
import sys, json, math
import numpy as np
from e4_common import *
import ds26_paths as DP
out = DP.outdir(DP.OUT_FEAS)
DT = 0.001
S = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
Sd = lambda x: np.where((x > 0) & (x < 1), 6 * x * (1 - x), 0.0)

def build(kind, r0=0.5, d1=1.0, tf=0.4, tau_ap=None, restart=2.0):
    """returns t grid, r(t), r'(t), tau(t) on [0, 18] s with tau(12) = 0."""
    t = np.arange(0, 18 + 1e-9, DT)
    if kind == 'old':           # draft v1 default
        r = np.where(t < 8, 1.0, np.where(t < 12, 1 - S((t - 8) / 4), 0.0)); rd = np.where((t >= 8) & (t < 12), -Sd((t - 8) / 4) / 4, 0.0)
    elif kind == 'hard':        # D31(d) real time + hard freeze at t*
        r = np.where(t < 12, 1.0, 0.0); rd = np.zeros_like(t)
    elif kind == 'new':         # real time -> ramp to r0 ending at the earliest tip apex -> constant r0 -> tf ramp to 0 at t*
        Lc = (abs(tau_ap) - r0 * tf / 2) / r0
        t_ap = 12 - tf - Lc; t1 = t_ap - d1
        r = np.ones_like(t); rd = np.zeros_like(t)
        m = (t >= t1) & (t < t_ap); r[m] = 1 - (1 - r0) * S((t[m] - t1) / d1); rd[m] = -(1 - r0) * Sd((t[m] - t1) / d1) / d1
        m = (t >= t_ap) & (t < 12 - tf); r[m] = r0
        m = (t >= 12 - tf) & (t < 12); r[m] = r0 * (1 - S((t[m] - (12 - tf)) / tf)); rd[m] = -r0 * Sd((t[m] - (12 - tf)) / tf) / tf
        r[t >= 12] = 0.0
    m = (t >= 14) & (t < 14 + restart); r[m] = S((t[m] - 14) / restart); rd[m] = Sd((t[m] - 14) / restart) / restart
    r[t >= 14 + restart] = 1.0
    tau = np.concatenate([[0], np.cumsum((r[1:] + r[:-1]) / 2 * DT)])
    tau -= tau[int(round(12 / DT))]
    return t, r, rd, tau

def gate(t, r, rd, tau, TT, tf):
    """TT: dict with tau grid, y, vy, ay per row, launch_end_tau per row. Returns per-row max upward apparent accel outside the freeze ramp."""
    res = []
    for k in range(TT['y'].shape[0]):
        m = (t < 12 - tf) & (tau >= TT['launch_end'][k]) & (tau <= 0)
        if not m.any():
            res.append((0.0, None)); continue
        ay = np.interp(tau[m], TT['tau'], TT['ay'][k]); vy = np.interp(tau[m], TT['tau'], TT['vy'][k])
        A_ = ay * r[m] ** 2 + vy * rd[m]
        i = int(np.argmax(A_)); res.append((float(A_[i]), float(t[m][i])))
    return res

def fall_time(t, tau, tau_apex):
    k = np.where(tau >= tau_apex)[0][0]
    return 12.0 - t[k]

def t_of(t, tau, x):
    if x == 0:
        return 12.0
    if x < 0:
        return float(t[np.where(tau >= x)[0][0]])
    return float(t[np.where(tau >= x - 1e-9)[0][0]])

# tip trajectories: new default (strip, floor 1.2, ramp min(0.6, T_i/2)) from e4; old model (point, Tr 0.6, floor 0.3) recomputed
Z = np.load(out + '/e4_tip_traj.npz')
def launch_end(cf, q):
    R = ramp_solve(q, cf); it = int(np.where(q['cols'] == q['jtip'])[0][0])
    return -R['Tc'][it] + R['Tr'][it]
cf_new = Cfg('d', rule='strip', floor=1.2, tr_rule='half'); cf_old = Cfg('o', rule='point', floor=0.3)
TTn = dict(tau=Z['tau'], y=Z['y'], vy=Z['vy'], ay=Z['ay'], launch_end=np.array([launch_end(cf_new, q) for q in rows]))
Tg = np.arange(0, 5.0 + 1e-9, 0.001)[::-1]
yo = []; vo = []; ao = []
for q in rows:
    R = ramp_solve(q, cf_old); it = int(np.where(q['cols'] == q['jtip'])[0][0])
    sub = {k: (v[it:it + 1] if isinstance(v, np.ndarray) and v.ndim >= 1 and len(v) == len(R['Tc']) else v) for k, v in R.items()}
    X, V, Aa = state(q, cf_old, sub, Tg); yo.append(X[0, :, 1]); vo.append(V[0, :, 1]); ao.append(Aa[0, :, 1])
TTo = dict(tau=-Tg, y=np.array(yo), vy=np.array(vo), ay=np.array(ao), launch_end=np.array([launch_end(cf_old, q) for q in rows]))

def apex(TT):
    k = np.argmax(TT['y'], axis=1); return TT['tau'][k], TT['y'][np.arange(len(k)), k]
ap_n, apy_n = apex(TTn); ap_o, apy_o = apex(TTo)
im, ip = int(Z['i_main']), int(Z['i_pk'])
res = dict(tip_apex_new=dict(main_tau=float(ap_n[im]), main_y=float(apy_n[im]), peak_tau=float(ap_n[ip]), peak_y=float(apy_n[ip]),
                             earliest_tau=float(ap_n.min()), earliest_c=float(Z['c'][np.argmin(ap_n)]), latest_tau=float(ap_n.max())),
           tip_apex_old_ramp=dict(main_tau=float(ap_o[im]), main_y=float(apy_o[im])))
print(json.dumps(res))

# 1) old warp with old tips (reviewer check) and with new tips
t, r, rd, tau = build('old')
for lab, TT, ap in (('old_warp_old_tips', TTo, ap_o), ('old_warp_new_tips', TTn, ap_n)):
    g_ = gate(t, r, rd, tau, TT, 0.0)
    ay = np.interp(tau, TT['tau'], TT['ay'][im]); vy = np.interp(tau, TT['tau'], TT['vy'][im]); A_ = ay * r ** 2 + vy * rd
    mm = (t > 8.8) & (t < 12)
    up = t[mm][np.where(A_[mm] > 0)[0][0]] if (A_[mm] > 0).any() else None
    res[lab] = dict(main_A_at_t10=float(A_[int(10 / DT)]), main_A_at_t11=float(A_[int(11 / DT)]), main_turns_upward_t=up,
                    main_fall_on_screen_s=fall_time(t, tau, ap[im]), main_fall_physical_s=float(-ap[im]),
                    ballistic_apex_fall_on_screen_s=fall_time(t, tau, -1.393),
                    all_rows_max_upward=max(x[0] for x in g_), rows_failing=int(sum(x[0] > 0.05 for x in g_)))
    print(lab, json.dumps(res[lab]))

# 2) candidate new warps
cands = []
for r0 in (0.3, 0.4, 0.5):
    for d1 in (0.5, 1.0):
        for tf in (0.3, 0.5):
            t, r, rd, tau = build('new', r0=r0, d1=d1, tf=tf, tau_ap=float(ap_n.min()))
            g_ = gate(t, r, rd, tau, TTn, tf)
            cands.append(dict(r0=r0, d1=d1, tf=tf, max_upward_mps2=max(x[0] for x in g_), rows_failing=int(sum(x[0] > 0.05 for x in g_)),
                              main_fall_on_screen_s=fall_time(t, tau, ap_n[im]), t_ramp_start=float(t[np.where(r < 0.999)[0][0]]),
                              tau_at_t0=float(tau[0]), apparent_g_mps2=g * r0 ** 2))
for c_ in cands:
    print('cand', json.dumps(c_))
res['candidates'] = cands

# 3) chosen default and alternative: event tables
DEF = dict(r0=0.5, d1=1.0, tf=0.4)
ev = {'a (round crest), peak row': -4.2, 'b (sharp crest), peak row': -3.4, 'c (jet onset, first white), peak row': -2.4,
      'c, main row': -2.2075, 'd (overhang >= 0.1H), peak row': -2.05, 'd, main row': -1.86,
      'tip apex, peak row': float(ap_n[ip]), 'tip apex, main row': float(ap_n[im]), 'earliest tip apex (any row)': float(ap_n.min()),
      'jet onset of the farthest curled row (floor 1.2 s)': -1.2}
post = {}
# post-t* events for the new default (seat row c = -1.43; seat a = 16.57 m, y = 1.83 m; front foot at a = 11.70 m)
qs = min(rows, key=lambda q: abs(q['c'] + 1.43)); R = ramp_solve(qs, cf_new); it = int(np.where(qs['cols'] == qs['jtip'])[0][0])
sub = {k: (v[it:it + 1] if isinstance(v, np.ndarray) and v.ndim >= 1 and len(v) == len(R['Tc']) else v) for k, v in R.items()}
X, V, _ = state(qs, cf_new, sub, np.array([0.0])); vx, vy = V[0, 0]; ak, yk = X[0, 0]
t_over = (16.57 - ak) / vx; y_over = yk + vy * t_over - 0.5 * g * t_over ** 2
imp = []
for q in rows:
    R2 = ramp_solve(q, cf_new); it2 = int(np.where(q['cols'] == q['jtip'])[0][0])
    sub2 = {k: (v[it2:it2 + 1] if isinstance(v, np.ndarray) and v.ndim >= 1 and len(v) == len(R2['Tc']) else v) for k, v in R2.items()}
    X2, V2, _ = state(q, cf_new, sub2, np.array([0.0])); y0 = X2[0, 0, 1]; w0 = V2[0, 0, 1]
    ti = (w0 + math.sqrt(w0 * w0 + 2 * g * y0)) / g; imp.append((ti, X2[0, 0, 0] + V2[0, 0, 0] * ti))
imp = np.array(imp)
post = {'lip tip passes over the seat': float(t_over), 'wave face reaches the seat': (16.57 - 11.70) / (0.8 * 20.0),
        'lip tip impact p5': float(np.percentile(imp[:, 0], 5)), 'lip tip impact p50': float(np.percentile(imp[:, 0], 50)),
        'lip tip impact p95': float(np.percentile(imp[:, 0], 95)), 'collapse end': 3.0}
res['post_tstar'] = dict(seat_row_c=qs['c'], tip_over_seat_height_m=float(y_over), tip_velocity_at_tstar=[float(vx), float(vy)],
                         impact_ground_a_p50_m=float(np.median(imp[:, 1])), events_tau=post)
tables = {}
for lab, kind, kw in (('default_slowmo', 'new', dict(DEF, tau_ap=float(ap_n.min()))), ('alt_realtime_hardfreeze', 'hard', {}), ('old_v1', 'old', {})):
    t, r, rd, tau = build(kind, **kw)
    tf = kw.get('tf', 0.0)
    g_ = gate(t, r, rd, tau, TTn, tf)
    row = dict(gate_max_upward_mps2=max(x[0] for x in g_), gate_rows_failing=int(sum(x[0] > 0.05 for x in g_)),
               main_fall_on_screen_s=fall_time(t, tau, ap_n[im]), main_fall_physical_s=float(-ap_n[im]),
               tau_at_t0=float(tau[0]), tau_at_t18=float(tau[-1]),
               events={k: dict(tau=round(v, 3), t=round(t_of(t, tau, v), 2)) for k, v in ev.items()},
               post={k: dict(tau=round(v, 3), t=round(t_of(t, tau, v), 2)) for k, v in post.items()},
               grid={str(x): round(float(tau[int(round(x / DT))]), 3) for x in (0, 2, 4, 6, 7, 8, 9, 10, 11, 11.6, 12, 14, 15, 16, 17, 18)})
    if kind == 'new':
        Lc = (abs(kw['tau_ap']) - DEF['r0'] * DEF['tf'] / 2) / DEF['r0']
        row['segments'] = dict(ramp_start_t=round(12 - DEF['tf'] - Lc - DEF['d1'], 3), apex_t=round(12 - DEF['tf'] - Lc, 3), freeze_ramp_start_t=12 - DEF['tf'],
                               r0=DEF['r0'], apparent_g=g * DEF['r0'] ** 2)
    tables[lab] = row
    print(lab, json.dumps(row, ensure_ascii=False))
res['tables'] = tables
json.dump(res, open(out + '/timewarp_v2.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=float)
