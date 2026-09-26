# E1: inverse-ballistic solve on K*'s lip vertices (設計26 feasibility; experiment, not a deliverable)
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e1_inverse_ballistic.py [restrict]
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
# Reads K* (26修正01) per-row section coords A (travel, m), Y (up, m), c (crest-line, m). Read only.
# Hypothesis: every lip vertex (upper surface crest->tip, underside tip->corner) left the crest tip
# at release time t_i = t* - tau_i with velocity (u_i, w_i) (ground frame) and moved under gravity only.
# The crest (release point) moves forward with the wave frame (speed c0, optional deceleration after
# jet onset to beta*c0 at t*) and rises at v_H m/s. Solve u_i, w_i exactly so that the vertex lands on
# K* at t*, then test plausibility.
import sys, json, itertools, math
import numpy as np

g = 9.81
import ds26_paths as DP
npz, out = DP.kstar_rows(), DP.outdir(DP.OUT_FEAS)
RESTRICT = 'restrict' in sys.argv[1:]  # underside ballistic only from tip to its first local minimum of y (jet hook); tube roof + inner wall = body
TAG = '_restricted' if RESTRICT else ''
d = np.load(npz)
A, Y, C = d['A'], d['Y'], d['c']
NR, NC = A.shape
J_CORNER, J_E = 314, 394

rows = []
for r in range(NR):
    y = Y[r]; a = A[r]
    H = y.max()
    if H < 3.0:
        continue
    jt = int(np.argmax(y))
    if jt >= 200:
        continue
    seg = np.arange(jt, J_CORNER + 1)
    jtip = int(seg[np.argmax(a[seg])])
    # overhang, definition A: inner wall (cols corner..E) at 0.3H -> lip tip
    w = np.arange(J_CORNER, J_E + 1)
    yw, aw = y[w], a[w]
    k = np.where((yw[:-1] - 0.3 * H) * (yw[1:] - 0.3 * H) <= 0)[0]
    if len(k) == 0:
        continue
    k = k[0]
    f = (0.3 * H - yw[k]) / (yw[k + 1] - yw[k] + 1e-12)
    a03 = aw[k] + f * (aw[k + 1] - aw[k])
    OA = a[jtip] - a03
    if OA < 0.2 * H or jtip <= jt + 5:
        continue
    rows.append(dict(r=r, c=float(C[r]), H=float(H), jt=jt, jtip=jtip, OA=float(OA),
                     a_top=float(a[jt]), tipA=float(a[jtip]), tipY=float(y[jtip])))
print('curled rows', len(rows))
c_pk = max(rows, key=lambda q: q['H'])['c']
row_main = min(rows, key=lambda q: abs(q['c']))

def arc(a, y):
    return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(a), np.diff(y)))])

# assemble vertex list: (row idx, col, surface, s_norm, a, y, H, a_top, c)
V = []
for q in rows:
    r = q['r']; a = A[r]; y = Y[r]
    up = np.arange(q['jtip'], q['jt'] - 1, -1)            # tip -> crest top
    un = np.arange(q['jtip'], J_CORNER + 1)                # tip -> corner
    if RESTRICT:
        yy = y[un]
        kmin = next((i for i in range(1, len(yy) - 1) if yy[i] <= yy[i - 1] and yy[i] < yy[i + 1]), len(yy) - 1)
        un = un[:max(kmin + 1, 6)]
    S_up = arc(a[up], y[up])[-1]
    for surf, cols in (('up', up), ('un', un)):
        s = arc(a[cols], y[cols]); S = s[-1]
        if RESTRICT and surf == 'un':
            S = max(S_up, S)  # underside released in the same arc-distance order as the upper surface (thick jet rim)
        for i, j in enumerate(cols):
            if surf == 'un' and j == q['jtip']:
                continue
            V.append((q['r'], j, 0 if surf == 'up' else 1, s[i] / S, a[j], y[j], q['H'], q['a_top'], q['c']))
V = np.array(V)
ROW, COL, SURF, SN, AV, YV, HV, ATOP, CV = [V[:, i] for i in range(9)]
print('lip vertices', len(V))

def solve(c0, tau0, p, beta, vpeel, da_frac, vH, dy_frac=0.0):  # release path ends at the crest-top (root) vertex at t*
    tau_row = tau0 - (np.abs(CV - c_pk) / vpeel if np.isfinite(vpeel) else 0.0)
    tau_row = np.maximum(tau_row, 0.3)
    tau = tau_row * (1.0 - SN) ** p
    D = beta * c0 * tau + (1 - beta) * c0 * tau ** 2 / (2 * tau_row)
    ra = ATOP + da_frac * HV
    ry = HV - vH * tau - dy_frac * HV
    with np.errstate(divide='ignore', invalid='ignore'):
        u = (AV - ra + D) / tau
        w = (YV - ry + 0.5 * g * tau ** 2) / tau
    c_at = beta * c0 + (1 - beta) * c0 * tau / tau_row
    dv = np.hypot(u - c_at, w - vH)
    return tau, tau_row, u, w, dv

def plaus(c0, tau, u, w):
    m = tau >= 0.15
    ok_u = (u / c0 >= 0.6) & (u / c0 <= 1.3)
    ok_w = (w / np.sqrt(g * HV) >= -0.2) & (w / np.sqrt(g * HV) <= 0.8)
    ok = ok_u & ok_w
    return m, ok_u, ok_w, ok

grid = dict(c0=[16, 18, 20, 22], tau0=[0.8, 1.2, 1.6, 2.0, 2.4, 2.8], p=[0.5, 1.0, 2.0], beta=[1.0, 0.8],
            vpeel=[math.inf, 30.0, 20.0], da=[0.0, 0.1], vH=[1.0, 2.5])
res = []
for c0, tau0, p, beta, vpeel, da, vH in itertools.product(*grid.values()):
    tau, tau_row, u, w, dv = solve(c0, tau0, p, beta, vpeel, da, vH)
    m, ok_u, ok_w, ok = plaus(c0, tau, u, w)
    tipm = m & (SN == 0)
    res.append(dict(c0=c0, tau0=tau0, p=p, beta=beta, vpeel=(None if not np.isfinite(vpeel) else vpeel), da=da, vH=vH,
                    frac_ok=float(ok[m].mean()), frac_ok_u=float(ok_u[m].mean()), frac_ok_w=float(ok_w[m].mean()),
                    tip_frac_ok=float(ok[tipm].mean()),
                    u_over_c_p5_p50_p95=[float(x) for x in np.percentile(u[m] / c0, [5, 50, 95])],
                    w_over_sqrtgH_p5_p50_p95=[float(x) for x in np.percentile(w[m] / np.sqrt(g * HV[m]), [5, 50, 95])],
                    tip_u_over_c_p50=float(np.median(u[tipm] / c0)),
                    dv_p95=float(np.percentile(dv[m], 95))))
res.sort(key=lambda q: -q['frac_ok'])
best = res[0]
print('best', json.dumps(best))

# default (design) parameter set: chosen from the top of the table but with vpeel finite (P10) -- report both
def details(par, label):
    c0, tau0, p, beta, vpeel, da, vH = par
    tau, tau_row, u, w, dv = solve(c0, tau0, p, beta, vpeel, da, vH)
    m, ok_u, ok_w, ok = plaus(c0, tau, u, w)
    out = dict(label=label, params=dict(c0=c0, tau_tip0=tau0, p=p, beta=beta, vpeel=(None if not np.isfinite(vpeel) else vpeel), da_frac=da, vH=vH))
    out['frac_ok'] = float(ok[m].mean()); out['n_eval'] = int(m.sum()); out['n_bad'] = int((~ok & m).sum())
    out['bad_by_reason'] = dict(u_high=int((m & (u / c0 > 1.3)).sum()), u_low=int((m & (u / c0 < 0.6)).sum()),
                               w_high=int((m & (w / np.sqrt(g * HV) > 0.8)).sum()), w_low=int((m & (w / np.sqrt(g * HV) < -0.2)).sum()))
    bad = m & ~ok
    out['bad_cols_hist'] = {str(int(k)): int(v) for k, v in zip(*np.unique((COL[bad] // 20 * 20).astype(int), return_counts=True))}
    out['bad_surface'] = dict(upper=int((bad & (SURF == 0)).sum()), under=int((bad & (SURF == 1)).sum()))
    out['u_over_c'] = [float(x) for x in np.percentile(u[m] / c0, [1, 5, 25, 50, 75, 95, 99])]
    out['w_mps'] = [float(x) for x in np.percentile(w[m], [1, 5, 25, 50, 75, 95, 99])]
    out['dv_mps_p50_p95_max'] = [float(np.percentile(dv[m], 50)), float(np.percentile(dv[m], 95)), float(dv[m].max())]
    out['release_ramp_min_s_for_2g_p95'] = float(np.percentile(dv[m], 95) / (2 * g))
    # post-t*: tip of each row -> impact
    c1 = beta * c0
    imp = []
    for q in rows:
        k = np.where((ROW == q['r']) & (SN == 0) & (SURF == 0))[0][0]
        wt = w[k] - g * tau[k]
        ti = (wt + math.sqrt(wt * wt + 2 * g * YV[k])) / g
        imp.append((q['c'], ti, AV[k] + u[k] * ti, AV[k] + (u[k] - c1) * ti, u[k] / c0, wt))
    imp = np.array(imp)
    out['impact_time_after_tstar_s_p5_p50_p95'] = [float(x) for x in np.percentile(imp[:, 1], [5, 50, 95])]
    out['impact_ground_a_m_p50'] = float(np.median(imp[:, 2]))
    out['impact_waveframe_a_m_p50'] = float(np.median(imp[:, 3]))
    # seat v1: a 16.57, c -1.43, y 1.83 (ground-fixed)
    rs = min(rows, key=lambda q: abs(q['c'] + 1.43))
    k = np.where((ROW == rs['r']) & (SN == 0) & (SURF == 0))[0][0]
    wt = w[k] - g * tau[k]
    t_over = (16.57 - AV[k]) / u[k]
    y_over = YV[k] + wt * t_over - 0.5 * g * t_over ** 2
    out['seat_row_c'] = rs['c']
    out['lip_tip_over_seat'] = dict(t_after_tstar_s=float(t_over), height_m=float(y_over), tip_u_mps=float(u[k]), tip_w_at_tstar_mps=float(wt))
    out['front_foot_reaches_seat_s'] = float((16.57 - 11.70) / c1)
    # main row: lip thickness growth after t*, backward self-intersection
    r0 = row_main['r']
    mu = (ROW == r0) & (SURF == 0); mn = (ROW == r0) & (SURF == 1)
    iu = np.where(mu)[0][np.argsort(SN[mu])]; inn = np.where(mn)[0][np.argsort(SN[mn])]
    def pos(ix, dt):  # ground==wave frame at t*; dt>0 after t*
        vt_w = w[ix] - g * tau[ix]
        return AV[ix] + u[ix] * dt, YV[ix] + vt_w * dt - 0.5 * g * dt * dt
    thick = []
    for sn in (0.2, 0.4, 0.6):
        ku = iu[np.argmin(np.abs(SN[iu] - sn))]; kn = inn[np.argmin(np.abs(SN[inn] - sn))]
        th0 = math.hypot(AV[ku] - AV[kn], YV[ku] - YV[kn])
        pa, py_ = pos(np.array([ku, kn]), 0.3)
        thick.append(dict(s_norm=sn, t0_m=th0, t_plus_0p3s_m=float(math.hypot(pa[0] - pa[1], py_[0] - py_[1]))))
    out['main_lip_thickness'] = thick
    def cr2(a_, b_):
        return a_[0] * b_[1] - a_[1] * b_[0]
    def seg_inter(P):
        n = len(P) - 1; cnt = 0
        for i in range(n):
            p1, p2 = P[i], P[i + 1]
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                q1, q2 = P[j], P[j + 1]
                d1 = cr2(p2 - p1, q1 - p1); d2 = cr2(p2 - p1, q2 - p1)
                d3 = cr2(q2 - q1, p1 - q1); d4 = cr2(q2 - q1, p2 - q1)
                if d1 * d2 < 0 and d3 * d4 < 0:
                    cnt += 1
        return cnt
    back = []
    trow = tau[iu[0]]
    for fr in (0.0, 0.25, 0.5, 0.75):
        tp = fr * trow  # time before t*
        Dp = beta * c0 * tp + (1 - beta) * c0 * tp ** 2 / (2 * trow)
        pts = []; tipw = None
        for ix in list(iu[::-1]) + list(inn):  # root(up) -> tip -> root(under)
            if tau[ix] >= tp and tau[ix] > 1e-3:
                dtb = tau[ix] - tp  # time since release
                ag = (ATOP[ix] + da * HV[ix] - (beta * c0 * tau[ix] + (1 - beta) * c0 * tau[ix] ** 2 / (2 * trow))) + u[ix] * dtb
                yg = (HV[ix] - vH * tau[ix]) + w[ix] * dtb - 0.5 * g * dtb * dtb
                pts.append((ag + Dp, yg))
                if ix == iu[0]:
                    tipw = [float(ag + Dp), float(yg)]
        P = np.array(pts)
        back.append(dict(t_before_tstar_s=tp, n_released=len(P), self_intersections=(seg_inter(P) if len(P) > 3 else 0),
                         tip_waveframe_a_y=tipw))
    out['main_backward_polyline'] = back
    return out

top = res[:15]
defaults = [
    ((20, 2.4, 0.5, 0.8, 20.0, 0.0, 1.0), 'D0 DEFAULT c0=20, tau=2.4, p=0.5, decel 0.8, peel 20, vH 1'),
    ((20, 1.6, 1.0, 1.0, 30.0, 0.1, 2.5), 'D1 c0=20, tau=1.6, linear release, no decel, peel 30 m/s'),
    ((20, 2.0, 1.0, 0.8, 30.0, 0.1, 2.5), 'D2 c0=20, tau=2.0, linear, decel to 0.8c, peel 30'),
    ((18, 2.0, 1.0, 0.8, 30.0, 0.1, 2.5), 'D3 c0=18, tau=2.0, linear, decel 0.8, peel 30'),
]
bp = (best['c0'], best['tau0'], best['p'], best['beta'], (best['vpeel'] if best['vpeel'] else math.inf), best['da'], best['vH'])
det = [details(bp, 'BEST of grid')] + [details(p, l) for p, l in defaults]
summary = dict(n_curled_rows=len(rows), c_peak_row=c_pk, main_row={k: (float(v) if not isinstance(v, str) else v) for k, v in row_main.items()}, n_lip_vertices=int(len(V)),
               plausibility=dict(u_over_c=[0.6, 1.3], w_over_sqrt_gH=[-0.2, 0.8], eval_tau_min_s=0.15),
               grid=grid, top15=top, details=det,
               rows_table=[dict(c=q['c'], H=q['H'], OA_over_H=q['OA'] / q['H'], tip_minus_top_a=q['tipA'] - q['a_top'], tipY_over_H=q['tipY'] / q['H']) for q in rows[::8]])
json.dump(summary, open(out + '/e1_result' + TAG + '.json', 'w'), indent=1, default=lambda o: None if (isinstance(o, float) and not np.isfinite(o)) else str(o))
# compact csv of whole grid
with open(out + '/e1_grid' + TAG + '.csv', 'w') as f:
    f.write('c0,tau0,p,beta,vpeel,da,vH,frac_ok,frac_ok_u,frac_ok_w,tip_frac_ok,tip_u_over_c_p50,dv_p95\n')
    for q in res:
        f.write(','.join(str(q[k]) for k in ['c0', 'tau0', 'p', 'beta', 'vpeel', 'da', 'vH', 'frac_ok', 'frac_ok_u', 'frac_ok_w', 'tip_frac_ok', 'tip_u_over_c_p50', 'dv_p95']) + '\n')
for x in det:
    print(json.dumps({k: x[k] for k in x if k not in ('bad_cols_hist',)}, ensure_ascii=False)[:1800])
print('rows sample', json.dumps(summary['rows_table'])[:1500])
