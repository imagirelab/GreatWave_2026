# E4: pre-release lip placement ("crest-front strip"), E1 re-solve from the parked start positions,
# release-ramp acceleration on ALL curled rows (ground and row-crest frames), and mesh validity of the lip strip
# (min edge / triangle area / stretch / seam / flips / self-intersections).  設計26 review fixes 4 and 5.
# Experiment, not a deliverable.  numpy only.  K* is read only.
# shared model for e4_prerelease_ramp.py, e4b_mesh.py, e4c/e5/tw_gate and fig_cause.py (imported; K* rows via ds26_paths)
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
#
# Model (same as E1/E3 unless noted):
#   row crest: ground a = a_top - D_r(T), y = H - vH*T (T = time before t*), speed c_r(T) = beta*c0 + (1-beta)*c0*T/T_row
#   after the row's jet onset T_row = max(tau0 - |c - c_pk|/vpeel, floor), c0 before.
#   release time of a lip vertex: T_i = T_row*(1 - s_i)^p (s_i = arc fraction from the tip; underside on the upper scale).
#   pre-release rule 'point' (E1/E3): every unreleased lip vertex sits on the crest-top point.
#   pre-release rule 'strip' (new): unreleased lip vertices sit on the crest front in column order with spacing delta:
#     upper column j (jt<j<=jtip): crest_top + (j-jt)*delta*d1 ; underside j (jtip<j<=rim): nose + (j-jtip)*delta*d2
#     (d1 = theta1 below horizontal forward, d2 = theta2).  Each vertex is released from its own parked point.
#   release ramp (E3 velocity ramp): v = (1-S) v_body + S (u', w' - g t''), S = smoothstep(t''/Tr_i), exact landing on K*.
#     Closed-form integrals (no numerical integration).  Tr rule: fixed Tr, or 'half' = min(Tr, T_i/2).
#   body proxies for the mesh check only: columns < jt = K* back face lowered by vH*T and moved with the row crest;
#     columns > rim (tube roof, rig) = parked down the face, then smoothstep from the row's onset to K* at t*.
import sys, json, math
import numpy as np

g = 9.81
import ds26_paths as DP
kz = DP.kstar_rows()
d = np.load(kz); A, Y, C = d['A'], d['Y'], d['c']
J_CORNER, J_E = 314, 394

def arc(a, y):
    return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(a), np.diff(y)))])

rows = []
for r in range(A.shape[0]):
    y = Y[r]; a = A[r]; H = y.max()
    if H < 3.0:
        continue
    jt = int(np.argmax(y))
    if jt >= 200:
        continue
    seg = np.arange(jt, J_CORNER + 1); jtip = int(seg[np.argmax(a[seg])])
    w = np.arange(J_CORNER, J_E + 1); yw, aw = y[w], a[w]
    k = np.where((yw[:-1] - 0.3 * H) * (yw[1:] - 0.3 * H) <= 0)[0]
    if len(k) == 0:
        continue
    k = k[0]; f = (0.3 * H - yw[k]) / (yw[k + 1] - yw[k] + 1e-12); a03 = aw[k] + f * (aw[k + 1] - aw[k])
    if a[jtip] - a03 < 0.2 * H or jtip <= jt + 5:
        continue
    un = np.arange(jtip, J_CORNER + 1); yy = y[un]
    kmin = next((i for i in range(1, len(yy) - 1) if yy[i] <= yy[i - 1] and yy[i] < yy[i + 1]), len(yy) - 1)
    un = un[:max(kmin + 1, 6)]
    rim = int(un[-1])
    up = np.arange(jt, jtip + 1)                      # root (crest top) -> tip, column order
    s_up = arc(a[up[::-1]], y[up[::-1]])               # from tip
    S_up = s_up[-1]
    s_up = (s_up / S_up)[::-1]                         # s for columns jt..jtip (1 at jt, 0 at tip)
    s_un_raw = arc(a[un], y[un])
    s_un = np.minimum(s_un_raw / max(S_up, s_un_raw[-1]), 1.0)[1:]  # columns jtip+1..rim
    cols = np.concatenate([up, un[1:]])
    s = np.concatenate([s_up, s_un])
    rows.append(dict(r=r, c=float(C[r]), H=float(H), jt=jt, jtip=jtip, rim=rim, cols=cols, s=s, ja=int(J_CORNER + k + (1 if f > 0.5 else 0)),
                     n_up=len(up) - 1, a_top=float(a[jt])))
rows.sort(key=lambda q: q['c'])
c_pk = max(rows, key=lambda q: q['H'])['c']
i_main = int(np.argmin([abs(q['c']) for q in rows])); i_pk = int(np.argmax([q['H'] for q in rows]))
print('curled rows', len(rows), 'lip vertices', sum(len(q['cols']) for q in rows), 'c_pk', c_pk)

def smooth(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)

class Cfg:
    def __init__(self, name, rule='strip', delta=0.02, th1=40.0, th2=80.0, c0=20.0, tau0=2.4, p=0.5, beta=0.8, vH=1.0,
                 vpeel=20.0, floor=0.3, Tr=0.6, tr_rule='fixed'):
        self.__dict__.update(locals()); del self.__dict__['self']

def row_setup(q, cf):
    T_row = max(cf.tau0 - abs(q['c'] - c_pk) / cf.vpeel, cf.floor)
    Ti = T_row * np.clip(1 - q['s'], 0, 1) ** cf.p
    a = A[q['r']]; y = Y[q['r']]; cols = q['cols']
    d1 = np.array([math.cos(math.radians(cf.th1)), -math.sin(math.radians(cf.th1))])
    d2 = np.array([math.cos(math.radians(cf.th2)), -math.sin(math.radians(cf.th2))])
    off = np.zeros((len(cols), 2))
    if cf.rule == 'strip':
        kk = cols - q['jt']
        upm = cols <= q['jtip']
        off[upm] = kk[upm, None] * cf.delta * d1[None, :]
        nose = q['n_up'] * cf.delta * d1
        off[~upm] = nose[None, :] + (cols[~upm] - q['jtip'])[:, None] * cf.delta * d2[None, :]
    K = np.stack([a[cols], y[cols]], 1)
    return T_row, Ti, off, K, d1, d2

def D_r(T, T_row, cf):
    T = np.asarray(T, float)
    return np.where(T <= T_row, cf.beta * cf.c0 * T + (1 - cf.beta) * cf.c0 * T ** 2 / (2 * T_row),
                    cf.beta * cf.c0 * T_row + (1 - cf.beta) * cf.c0 * T_row / 2 + cf.c0 * (T - T_row))

def crest_g(T, q, T_row, cf):
    return np.stack([q['a_top'] - D_r(T, T_row, cf), q['H'] - cf.vH * np.asarray(T, float)], -1)

def ramp_solve(q, cf):
    """per lip vertex: release time, parked release point, ramp length, solved (u', w'), pure-ballistic (u, w)."""
    T_row, Ti, off, K, d1, d2 = row_setup(q, cf)
    Tc = np.maximum(Ti, 1e-4)
    P = crest_g(Tc, q, T_row, cf) + off                        # ground release point
    ub = (K[:, 0] - P[:, 0]) / Tc; wb = (K[:, 1] - P[:, 1] + 0.5 * g * Tc ** 2) / Tc   # pure ballistic (E1)
    Tr = np.full_like(Tc, cf.Tr) if cf.tr_rule == 'fixed' else np.minimum(cf.Tr, Tc / 2)
    ci = cf.beta * cf.c0 + (1 - cf.beta) * cf.c0 * Tc / T_row; kdec = (1 - cf.beta) * cf.c0 / T_row
    tp = Tc  # time since release at t*
    IS, ISg = integ_S(tp, Tr)
    bx = ci * (tp - IS) - kdec * (tp ** 2 / 2 - ISg); by = cf.vH * (tp - IS)
    u2 = (K[:, 0] - P[:, 0] - bx) / IS; w2 = (K[:, 1] - P[:, 1] - by + g * ISg) / IS
    return dict(T_row=T_row, Ti=Ti, Tc=Tc, off=off, K=K, P=P, ub=ub, wb=wb, Tr=Tr, ci=ci, kdec=kdec, u2=u2, w2=w2)

def integ_S(tp, Tr):
    s = np.clip(tp / Tr, 0, 1)
    IS = Tr * (s ** 3 - s ** 4 / 2) + np.maximum(tp - Tr, 0)
    ISg = np.where(tp <= Tr, Tr ** 2 * (0.75 * s ** 4 - 0.4 * s ** 5), Tr ** 2 * 0.35 + (tp ** 2 - Tr ** 2) / 2)
    return IS, ISg

def state(q, cf, R, T):
    """ground position/velocity/acceleration of every lip vertex at times T (time before t*): T is (nt,) or (nv, nt).
    returns X, V, Acc with shape (nv, nt, 2)"""
    T = np.asarray(T, float)
    if T.ndim == 1:
        T = T[None, :]
    nv = len(R['Tc']); T = np.broadcast_to(T, (nv, T.shape[1]))
    Ti = R['Tc'][:, None]; tp = Ti - T                           # time since release
    rel = tp >= 0
    tpc = np.clip(tp, 0, None); Tr = R['Tr'][:, None]
    IS, ISg = integ_S(tpc, Tr)
    s = np.clip(tpc / Tr, 0, 1); S = smooth(s); Sd = np.where(s < 1, 6 * s * (1 - s) / Tr, 0.0)
    ci = R['ci'][:, None]; kd = R['kdec']
    u2 = R['u2'][:, None]; w2 = R['w2'][:, None]
    Px = R['P'][:, 0][:, None]; Py = R['P'][:, 1][:, None]
    x_rel = Px + ci * (tpc - IS) - kd * (tpc ** 2 / 2 - ISg) + u2 * IS
    y_rel = Py + cf.vH * (tpc - IS) + w2 * IS - g * ISg
    vbx = ci - kd * tpc
    vx_rel = (1 - S) * vbx + S * u2; vy_rel = (1 - S) * cf.vH + S * (w2 - g * tpc)
    ax_rel = Sd * (u2 - vbx) + (1 - S) * (-kd); ay_rel = Sd * (w2 - g * tpc - cf.vH) - S * g
    # parked (pre-release): crest top + fixed offset
    x_pk = q['a_top'] - D_r(T, R['T_row'], cf) + R['off'][:, 0][:, None]
    y_pk = q['H'] - cf.vH * T + R['off'][:, 1][:, None]
    vx_pk = np.where(T <= R['T_row'], cf.beta * cf.c0 + (1 - cf.beta) * cf.c0 * T / R['T_row'], cf.c0)
    ax_pk = np.where(T <= R['T_row'], -kd, 0.0)
    X = np.stack([np.where(rel, x_rel, x_pk), np.where(rel, y_rel, y_pk)], -1)
    V = np.stack([np.where(rel, vx_rel, vx_pk), np.where(rel, vy_rel, cf.vH)], -1)
    Aac = np.stack([np.where(rel, ax_rel, ax_pk), np.where(rel, ay_rel, 0.0)], -1)
    return X, V, Aac

def plaus(q, R, cf):
    m = R['Ti'] >= 0.15
    okU = (R['ub'] / cf.c0 >= 0.6) & (R['ub'] / cf.c0 <= 1.3)
    wn = R['wb'] / math.sqrt(g * q['H'])
    okW = (wn >= -0.2) & (wn <= 0.8)
    return m, okU & okW

def run_cfg(cf, nsamp=400):
    n_ev = 0; n_ok = 0; accg = []; accw = []; worst = []; tipinfo = {}
    for iq, q in enumerate(rows):
        R = ramp_solve(q, cf)
        m, ok = plaus(q, R, cf)
        n_ev += int(m.sum()); n_ok += int((ok & m).sum())
        # accel on each vertex's own window (release -> t*), nsamp samples, excluding 3 at each end
        idx = np.where(m)[0]
        if len(idx):
            sub = {k: (v[idx] if isinstance(v, np.ndarray) and v.ndim >= 1 and len(v) == len(R['Tc']) else v) for k, v in R.items()}
            fr = np.linspace(0, 1, nsamp)[3:-3]
            Ts = sub['Tc'][:, None] * (1 - fr[None, :])
            _, _, Aac = state(q, cf, sub, Ts)
            ag = np.hypot(Aac[..., 0], Aac[..., 1]).max(1); aw = np.hypot(Aac[..., 0] + R['kdec'], Aac[..., 1]).max(1)
            accg.extend(list(ag / g)); accw.extend(list(aw / g))
            worst.extend([(float(ag[k] / g), q['c'], int(q['cols'][i]), float(R['Tc'][i])) for k, i in enumerate(idx)])
        if iq in (i_main, i_pk):
            # tip (s=0) apex, relative rise above the crest, pure ballistic vs ramp
            it = int(np.where(q['cols'] == q['jtip'])[0][0])
            Tg = np.linspace(R['T_row'] + 0.2, 0, 4001)
            sub = {k: (v[it:it + 1] if isinstance(v, np.ndarray) and v.ndim >= 1 and len(v) == len(R['Tc']) else v) for k, v in R.items()}
            X, V, _ = state(q, cf, sub, Tg)
            ycr = q['H'] - cf.vH * Tg
            k_ap = int(np.argmax(X[0, :, 1])); k_rel = int(np.argmax(X[0, :, 1] - ycr))
            Ti = R['Tc'][it]; wb = R['wb'][it]
            tipinfo['main' if iq == i_main else 'peak'] = dict(
                c=q['c'], T_row=R['T_row'], tip_release_tau=-Ti,
                ramp_apex_tau=float(-Tg[k_ap]), ramp_apex_y=float(X[0, k_ap, 1]), ramp_crest_y_at_apex=float(ycr[k_ap]),
                ramp_max_rise_above_crest=float((X[0, :, 1] - ycr).max()), ramp_max_rise_tau=float(-Tg[k_rel]),
                ballistic_apex_tau=float(-Ti + wb / g), ballistic_apex_y=float(R['P'][it, 1] + wb ** 2 / (2 * g)),
                ballistic_max_rise_above_crest=float((wb - cf.vH) ** 2 / (2 * g)),
                tip_w=float(wb), tip_u_over_c0=float(R['ub'][it] / cf.c0), crest_at_onset_over_H=float((q['H'] - cf.vH * R['T_row']) / q['H']))
    accg = np.array(accg); accw = np.array(accw); worst.sort(reverse=True)
    far = [w for w in worst if w[0] > 2.0]
    return dict(name=cf.name, cfg={k: v for k, v in cf.__dict__.items()}, frac_plausible=n_ok / n_ev, n_eval=n_ev,
                accel_ground_g=dict(p50=float(np.percentile(accg, 50)), p95=float(np.percentile(accg, 95)), p99=float(np.percentile(accg, 99)),
                                    max=float(accg.max()), frac_gt_2g=float(np.mean(accg > 2.0)), n=int(len(accg))),
                accel_rowcrest_frame_g=dict(p95=float(np.percentile(accw, 95)), max=float(accw.max()), frac_gt_2g=float(np.mean(accw > 2.0))),
                worst5=[(round(a, 2), round(c, 1), j, round(t, 2)) for a, c, j, t in worst[:5]],
                exceed_rows_c_range=([round(min(w[1] for w in far), 1), round(max(w[1] for w in far), 1)] if far else None),
                exceed_release_tau_max=(round(max(w[3] for w in far), 2) if far else None), tip=tipinfo)

