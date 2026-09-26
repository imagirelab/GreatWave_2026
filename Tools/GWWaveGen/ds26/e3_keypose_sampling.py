# E3: keypose sampling for fast ballistic phases + memory estimate (設計26 feasibility; experiment)
# usage (リポジトリの根で): py -3.12 -B Tools/GWWaveGen/ds26/e3_keypose_sampling.py
#   入力：K* = Unity/Build/ArtFirst/26修正01/kstar/（Git 対象外、SHA-256 を照合）。出力：Unity/Build/Design/26/feas/（Git 対象外）。
# Uses the E1 parametrisation (default set below) on the main row's jet-sheet vertices, builds their wave-frame
# trajectories (attached to the release point before release, C1 velocity ramp of length Tr into the ballistic path),
# samples keys at 15/30/60 Hz and measures uniform Catmull-Rom error against a 480 Hz truth.
import sys, json, math
import numpy as np

g = 9.81
import ds26_paths as DP
kz, out = DP.kstar_rows(), DP.outdir(DP.OUT_FEAS)
d = np.load(kz); A, Y, C = d['A'], d['Y'], d['c']
r0 = int(np.argmin(np.abs(C)))
a, y = A[r0], Y[r0]
H = y.max(); jt = int(np.argmax(y)); jtip = int(jt + np.argmax(a[jt:315]))
up = np.arange(jtip, jt - 1, -1)
un = np.arange(jtip, 315)
kmin = next((i for i in range(1, len(un) - 1) if y[un][i] <= y[un][i - 1] and y[un][i] < y[un][i + 1]), len(un) - 1)
un = un[:max(kmin + 1, 6)]
def arcs(cols):
    return np.concatenate([[0], np.cumsum(np.hypot(np.diff(a[cols]), np.diff(y[cols])))])
S_up = arcs(up)[-1]
cols = np.concatenate([up, un[1:]]); sn = np.concatenate([arcs(up) / S_up, np.minimum(arcs(un)[1:] / S_up, 1.0)])
P = dict(c0=20.0, tau0=2.4, p=0.5, beta=0.8, da=0.0, vH=1.0, dy=0.0)

def traj(Tr, t):  # t: time relative to t* (array); returns wave-frame (a, y) for each vertex: shape (nv, nt, 2)
    c0, tau0, p, beta, da, vH, dy = [P[k] for k in ('c0', 'tau0', 'p', 'beta', 'da', 'vH', 'dy')]
    tau = tau0 * (1 - sn) ** p
    tau = np.maximum(tau, 1e-3)
    tau_s = tau.copy()
    D = lambda tb: np.where(tb <= tau0, beta * c0 * tb + (1 - beta) * c0 * tb ** 2 / (2 * tau0), beta * c0 * tau0 + (1 - beta) * c0 * tau0 / 2 + c0 * (tb - tau0))
    # D(tb): ground distance travelled by the wave frame between t*-tb and t* (tb>=0). After t*: frame moves at beta*c0.
    ra = a[jt] + da * H
    ry_of = lambda tb: H - vH * tb - dy * H
    u = (a[cols] - ra + D(tau)) / tau
    w = (y[cols] - ry_of(tau) + 0.5 * g * tau ** 2) / tau
    res = np.zeros((len(cols), len(t), 2))
    for i in range(len(cols)):
        ti = -tau[i]
        # ground-frame body point (release point) at time t: a_g = ra - D(-t) (for t<=0), y = ry(-t)
        tb = np.clip(-t, 0, None)
        ag_body = ra - D(tb) + np.where(t > 0, beta * c0 * t, 0)
        yg_body = ry_of(tb) + np.where(t > 0, vH * t, 0)
        dt = t - ti
        ag_ball = (ra - D(np.array(tau[i]))) + u[i] * dt
        yg_ball = ry_of(tau[i]) + w[i] * dt - 0.5 * g * dt * dt
        if Tr > 0:
            s = np.clip(dt / Tr, 0, 1); wgt = s * s * (3 - 2 * s)  # position blend (C1 if both paths meet at ti)
        else:
            wgt = (dt >= 0).astype(float)
        ag = (1 - wgt) * ag_body + wgt * ag_ball
        yg = (1 - wgt) * yg_body + wgt * yg_ball
        # wave frame: add frame displacement (frame origin at ground a = -D(tb) before t*, +beta*c0*t after)
        frame = np.where(t <= 0, -D(tb), beta * c0 * t)
        res[i, :, 0] = ag - frame; res[i, :, 1] = yg
    return res, u, w, tau

T0, T1 = -3.0, 0.7
fs_truth = 480
tt = np.arange(T0, T1 + 1e-9, 1 / fs_truth)
out_res = {}
for Tr in (0.0, 0.2, 0.4):
    X, u, w, tau = traj(Tr, tt)
    ent = {}
    for hz in (15, 30, 60, 120):
        step = fs_truth // hz
        keys = X[:, ::step, :]; kt = tt[::step]
        # uniform Catmull-Rom with one-sided ends
        errs = []
        for m in range(len(kt) - 1):
            p1 = keys[:, m]; p2 = keys[:, m + 1]
            p0 = keys[:, m - 1] if m > 0 else 2 * p1 - p2
            p3 = keys[:, m + 2] if m + 2 < len(kt) else 2 * p2 - p1
            seg = np.arange(m * step, (m + 1) * step + 1)
            s = (tt[seg] - kt[m]) * hz
            s = s[None, :, None]
            cr = 0.5 * ((2 * p1)[:, None] + (-p0 + p2)[:, None] * s + (2 * p0 - 5 * p1 + 4 * p2 - p3)[:, None] * s ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3)[:, None] * s ** 3)
            errs.append(np.sqrt(((cr - X[:, seg, :]) ** 2).sum(-1)).max())
        errs = np.array(errs)
        ent[f'{hz}Hz'] = dict(max_err_m=float(errs.max()), p95_seg_err_m=float(np.percentile(errs, 95)), n_keys_over_window=int(len(kt)))
    # per-frame kinematics in the wave frame at 30 Hz (P13 limits)
    X30 = X[:, ::16, :]
    step = np.sqrt((np.diff(X30, axis=1) ** 2).sum(-1)).max()
    d2 = np.sqrt((np.diff(X30, 2, axis=1) ** 2).sum(-1)).max()
    out_res[f'Tr_{Tr}'] = dict(catmull_rom=ent, waveframe_30Hz_max_step_m=float(step), waveframe_30Hz_max_second_diff_m=float(d2),
                               second_diff_limit_2g_m=float(2 * g / 900))
# key budget scenarios (physical time windows), bytes per layer from Step_30: 768,000 pos + 384,000 nrm = 1,152,000 B
LAYER_B = 1152000
UNITY_PER_LAYER_MIB = 397.7 / 181  # Step_30 Profiler figure (readable Texture2DArray, 181 layers)
scen = {
    'A_all15Hz_14s': [(14.0, 15)],
    'B_approach15_break30': [(8.0, 15), (6.0, 30)],
    'C_approach7.5_break30': [(8.0, 7.5), (6.0, 30)],
    'D_approach7.5_break60': [(8.0, 7.5), (6.0, 60)],
    'E_approach7.5_break30_subrect58pct': [(8.0, 7.5), (6.0, 30)],
}
mem = {}
for k, win in scen.items():
    n = int(sum(math.ceil(T * hz) for T, hz in win)) + 1
    frac = 0.58 if 'subrect' in k else 1.0
    mem[k] = dict(windows_s_hz=win, layers=n, file_MiB=n * LAYER_B * frac / 2 ** 20,
                  unity_readable_MiB_est=n * UNITY_PER_LAYER_MIB * frac, unity_nonreadable_MiB_est=n * LAYER_B * frac / 2 ** 20,
                  within_512MiB_readable=bool(n * UNITY_PER_LAYER_MIB * frac <= 512), within_512MiB_nonreadable=bool(n * LAYER_B * frac / 2 ** 20 <= 512))
res = dict(params=P, main_row=r0, n_jet_vertices=int(len(cols)), window_rel_tstar_s=[T0, T1], sampling=out_res, memory=mem,
           notes='Catmull-Rom = uniform keys, one-sided ends. Tr = release ramp (smoothstep position blend body->ballistic). '
                 'Unity readable MiB/layer from Step_30 (397.7 MiB / 181 layers); non-readable assumed = file size (to be measured in 設計29).')
json.dump(res, open(out + '/e3_result.json', 'w'), indent=1)
print(json.dumps(res, indent=1))

# post-t* check: jet polyline (upper root->tip->underside hook) self-intersections and thickness while ballistic
def cr2(p_, q_):
    return p_[0] * q_[1] - p_[1] * q_[0]
def n_inter(Pl):
    n = len(Pl) - 1; cnt = 0
    for i in range(n):
        for j in range(i + 2, n):
            p1, p2, q1, q2 = Pl[i], Pl[i + 1], Pl[j], Pl[j + 1]
            if cr2(p2 - p1, q1 - p1) * cr2(p2 - p1, q2 - p1) < 0 and cr2(q2 - q1, p1 - q1) * cr2(q2 - q1, p2 - q1) < 0:
                cnt += 1
    return cnt
tp = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
Xp, u, w, tau = traj(0.0, tp)
order = list(range(len(up) - 1, -1, -1)) + list(range(len(up), len(cols)))  # root(up)->tip->hook
post = []
for k, t_ in enumerate(tp):
    Pl = Xp[order, k, :]
    post.append(dict(t_after_tstar_s=float(t_), self_intersections=n_inter(Pl), tip_waveframe=[float(Xp[0, k, 0]), float(Xp[0, k, 1])],
                     min_y_m=float(Pl[:, 1].min())))
res['post_tstar_jet_polyline'] = post
res['speed_along_lip_at_tstar_ground'] = dict(
    cols_root_to_tip=[int(cols[i]) for i in range(len(up) - 1, -1, -8)],
    speed_mps=[float(math.hypot(u[i], w[i] - g * tau[i])) for i in range(len(up) - 1, -1, -8)])
json.dump(res, open(out + '/e3_result.json', 'w'), indent=1)
print(json.dumps(res['post_tstar_jet_polyline'])); print(json.dumps(res['speed_along_lip_at_tstar_ground']))

# velocity-ramp release (C1 in velocity, exact landing on K* at t*): x(t) = x_body(t_i) + int_{t_i}^{t} [(1-S) v_body + S v_ball] dt,
# v_ball(t) = (u, w - g (t - t_i)), S = smoothstep((t - t_i)/Tr). (u, w) solved linearly so that x(t*) = K*.
def traj_vramp(Tr, t_eval):
    c0, tau0, p, beta, vH = P['c0'], P['tau0'], P['p'], P['beta'], P['vH']
    tau = np.maximum(tau0 * (1 - sn) ** p, 1e-3)
    ra, Htop = a[jt], y[jt]
    cfun = lambda tt_: np.where(tt_ <= 0, beta * c0 + (1 - beta) * c0 * np.clip(-tt_, 0, tau0) / tau0 + np.where(-tt_ > tau0, 0, 0), beta * c0)
    def D(tb):  # ground distance the frame travels from t*-tb to t*
        tb = np.asarray(tb, float)
        return np.where(tb <= tau0, beta * c0 * tb + (1 - beta) * c0 * tb ** 2 / (2 * tau0), beta * c0 * tau0 + (1 - beta) * c0 * tau0 / 2 + c0 * (tb - tau0))
    xb = lambda tt_: np.stack([ra - D(np.clip(-tt_, 0, None)) + np.where(tt_ > 0, beta * c0 * tt_, 0), Htop - vH * np.clip(-tt_, 0, None) + np.where(tt_ > 0, vH * tt_, 0)], -1)
    vb = lambda tt_: np.stack([np.where(tt_ <= 0, beta * c0 + (1 - beta) * c0 * np.clip(-tt_, 0, None) / tau0, beta * c0), np.full_like(tt_, vH)], -1)
    out_pos = np.zeros((len(cols), len(t_eval), 2)); acc_max = 0.0
    for i in range(len(cols)):
        ti = -tau[i]
        ts = np.linspace(ti, max(t_eval.max(), 0.0), 4000)
        dt = ts[1] - ts[0]
        s = np.clip((ts - ti) / Tr, 0, 1) if Tr > 0 else (ts >= ti).astype(float)
        S = s * s * (3 - 2 * s)
        vbody = vb(ts)
        # velocity = (1-S) vbody + S (u, w - g (t - ti)) ; integrate: x = xb(ti) + cum[(1-S) vbody] + (u,w) cum[S] - g cum[S (t-ti)] y
        cum = lambda f: np.concatenate([[0], np.cumsum((f[1:] + f[:-1]) * 0.5 * dt)])
        I_body = np.stack([cum((1 - S) * vbody[:, 0]), cum((1 - S) * vbody[:, 1])], -1)
        I_S = cum(S); I_Sg = cum(S * (ts - ti))
        k0 = np.argmin(np.abs(ts - 0.0))
        x0 = xb(np.array([ti]))[0]
        target = np.array([a[cols[i]], y[cols[i]]])
        rem = target - x0 - I_body[k0] - np.array([0, -g * I_Sg[k0]])
        uw = rem / max(I_S[k0], 1e-9)
        pos = x0[None, :] + I_body + uw[None, :] * I_S[:, None] + np.stack([np.zeros_like(I_Sg), -g * I_Sg], -1)
        # frame
        frame = np.where(ts <= 0, -D(np.clip(-ts, 0, None)), beta * c0 * ts)
        posw = pos.copy(); posw[:, 0] -= frame
        vel = np.gradient(pos, dt, axis=0); acc = np.gradient(vel, dt, axis=0)
        m = (ts > ti + 2 * dt) & (ts < -2 * dt)
        if m.any():
            acc_max = max(acc_max, float(np.sqrt((acc[m] ** 2).sum(-1)).max()))
        # before release: attached to body path (wave frame fixed point moving up at vH)
        te = t_eval
        pre = te < ti
        body_w = np.stack([np.full_like(te, ra), Htop - vH * np.clip(-te, 0, None) + np.where(te > 0, vH * te, 0)], -1)
        out_pos[i] = np.where(pre[:, None], body_w, np.stack([np.interp(te, ts, posw[:, 0]), np.interp(te, ts, posw[:, 1])], -1))
    return out_pos, acc_max

vr = {}
for Tr in (0.4, 0.6, 0.8):
    X, amax = traj_vramp(Tr, tt[tt <= 0.0])
    tt0 = tt[tt <= 0.0]
    ent = {}
    for hz in (15, 30, 60):
        step = fs_truth // hz
        keys = X[:, ::step, :]; kt = tt0[::step]
        errs = []
        for m in range(len(kt) - 1):
            p1 = keys[:, m]; p2 = keys[:, m + 1]
            p0 = keys[:, m - 1] if m > 0 else 2 * p1 - p2
            p3 = keys[:, m + 2] if m + 2 < len(kt) else 2 * p2 - p1
            seg = np.arange(m * step, (m + 1) * step + 1)
            s_ = ((tt0[seg] - kt[m]) * hz)[None, :, None]
            crv = 0.5 * ((2 * p1)[:, None] + (-p0 + p2)[:, None] * s_ + (2 * p0 - 5 * p1 + 4 * p2 - p3)[:, None] * s_ ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3)[:, None] * s_ ** 3)
            errs.append(np.sqrt(((crv - X[:, seg, :]) ** 2).sum(-1)).max())
        ent[f'{hz}Hz'] = float(np.max(errs))
    X30 = X[:, ::16, :]
    vr[f'Tr_{Tr}'] = dict(cr_max_err_m=ent, max_accel_ground_mps2=amax, max_accel_over_g=amax / g,
                          wave_frame_30Hz_max_step_m=float(np.sqrt((np.diff(X30, axis=1) ** 2).sum(-1)).max()),
                          kstar_landing_err_m=float(np.abs(X[:, -1, :] - np.stack([a[cols], y[cols]], -1)).max()))
res['velocity_ramp_release'] = vr
json.dump(res, open(out + '/e3_result.json', 'w'), indent=1)
print(json.dumps(vr, indent=1))

# snapshots of the main-row jet sheet (wave frame) for the figure
snap_t = np.array([-2.4, -2.0, -1.5, -1.0, -0.5, 0.0, 0.2, 0.4, 0.6])
Xs, _ = traj_vramp(0.6, snap_t)
np.savez(out + '/e3_mainrow_snapshots.npz', t=snap_t, X=Xs, K_a=a, K_y=y, cols=cols, n_up=len(up), jt=jt, jtip=jtip,
         seat_a_ground=16.57, seat_y=1.83, c0=P['c0'], beta=P['beta'], tau=np.maximum(P['tau0'] * (1 - sn) ** P['p'], 1e-3), Tr=0.6)
