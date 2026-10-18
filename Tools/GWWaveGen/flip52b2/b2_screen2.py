# -*- coding: utf-8 -*-
"""FLIP52B2 round-2 candidate screen, part 2 (py -3.10 -B; numpy, scipy). 2026-10-18 written new (Claude).
Reads only (DFG-2B-E run records, diag/*.json of b2_*); writes Unity/Build/FLIP52B2/diag/screen2_*.json. Nothing frozen is edited.
Commands:
  g4ts     G4 band-steepness time series of DFG-2B-E: kp x (3x3-median hf - eta0) max per frame in the generating side band
           (y >= 95 m, x <= 180.25 m) and the inlet band (x <= 100 m), per group window; when / where the max sits relative to t_fn and to the
           arrival time of a wave reflected at x 235-250 m (the candidate (c) face) [measured + computed]
  refl     linear reflection of the bed variants (1D, normal and oblique incidence, layers T 9.33 / 7 / 5.6 s): exact linear potential theory by
           eigenfunction matching over a stepped approximation of the bed (propagating + evanescent modes) [computed]
  lipclock lip-clock / convergence-at-curl table for candidate (c) from the measured DFG-2B-E crest track and the DFG-S step-edge record
           [measured + calibrated + guess]
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import b2_common as B                   # noqa: E402
import numpy as np                      # noqa: E402

KP = 0.088136                           # judge G4 kp [measured from judge_DFGB.json]


# ============================================================================ G4 time series
def g4ts(stride=2):
    from scipy import ndimage as ndi
    t0 = time.time()
    J = B.jload(B.JUDGE)
    eta0 = float(J["eta0"])
    H = B.GA52.Blocks(B.RUN, "hf", "eta")
    fr = [f for f in H.frames() if (f - 1) / B.FPS >= 30.0][::stride]
    rows = []
    for f in fr:
        a, meta = H.get(f)
        x = float(meta["x0"]) + float(meta["dx"]) * np.arange(a.shape[1])
        y = float(meta["z0"]) + float(meta["dz"]) * np.arange(a.shape[0])
        sub_x = x <= 183.0
        A = a[:, sub_x]
        m = ndi.median_filter(np.nan_to_num(A, nan=-30.0), size=3, mode="nearest") - eta0
        xs = x[sub_x]
        sd = (y[:, None] >= 95.0) & (xs[None, :] <= 180.25)
        inl = (xs[None, :] <= 100.0) & np.ones_like(y[:, None], bool)
        v = np.where(sd, m, -1e9); j = int(np.argmax(v)); iy, ix = np.unravel_index(j, v.shape)
        w = np.where(inl, m, -1e9); k = int(np.argmax(w)); ky, kx = np.unravel_index(k, w.shape)
        rows.append(dict(f=int(f), t=(f - 1) / B.FPS, side=KP * float(v[iy, ix]), side_x=float(xs[ix]), side_y=float(y[iy]),
                         inlet=KP * float(w[ky, kx]), inlet_x=float(xs[kx]), inlet_y=float(y[ky])))
    T = np.array([r["t"] for r in rows]); S = np.array([r["side"] for r in rows]); I = np.array([r["inlet"] for r in rows])
    groups = []
    for g in J["groups"]:
        tfn = g["t_fn"]
        m = (T >= tfn - 28.0 + 14.0 - 28.0 / 2.0) & (T < tfn + 14.0 - 28.0 / 2.0 + 14.0)        # [t_fn - 28, t_fn): the period that builds group n
        m = (T >= tfn - 28.0) & (T < tfn)
        if not m.any():
            continue
        i = int(np.argmax(np.where(m, S, -1)))
        groups.append(dict(n=g["n"], t_fn=tfn, side_max=float(S[i]), t=float(T[i]), t_rel_fn=float(T[i] - tfn), x=rows[i]["side_x"], y=rows[i]["side_y"],
                           inlet_max=float(np.max(np.where(m, I, -1)))))
    i = int(np.argmax(S))
    # top-10 instants of the side band (distinct by >= 2 s)
    order = np.argsort(-S); top = []
    for q in order:
        if all(abs(T[q] - T[p]) >= 2.0 for p in top):
            top.append(int(q))
        if len(top) >= 8:
            break
    out = dict(rule="kp x (3x3-median hf - eta0), kp %.6f (judge), side band y >= 95 m, x <= 180.25 m; inlet x <= 100 m; every %d-th frame from t 30 s" % (KP, stride),
               overall=dict(side_max=float(S[i]), t=float(T[i]), x=rows[i]["side_x"], y=rows[i]["side_y"], inlet_max=float(I.max()), t_inlet=float(T[int(np.argmax(I))])),
               per_period=groups,
               top_side=[dict(t=float(T[q]), side=float(S[q]), x=rows[q]["side_x"], y=rows[q]["side_y"],
                              t_rel_nearest_fn=float(min((T[q] - g["t_fn"] for g in J["groups"]), key=abs))) for q in top],
               series=dict(t=T[::3], side=S[::3], inlet=I[::3]), cpu_s=round(time.time() - t0, 1))
    B.jdump(out, B.OUT + "/screen2_g4ts.json")
    print(json.dumps(dict(overall=out["overall"], per_period=groups, top=out["top_side"]), default=float))
    return out


# ============================================================================ linear reflection by eigenfunction matching (stepped bed)
def _roots(om, h, M):
    """k0 (propagating, real) and M evanescent kappa_m (k = i kappa) of om^2 = g k tanh(k h)."""
    g = B.G
    k = om * om / g
    for _ in range(80):
        f = g * k * math.tanh(k * h) - om * om
        df = g * math.tanh(k * h) + g * k * h / math.cosh(k * h) ** 2
        k -= f / df
    ks = [k]
    for m in range(1, M + 1):
        # om^2 = -g kap tan(kap h): kap in ((m - 1/2) pi / h, m pi / h)
        lo = (m - 0.5) * math.pi / h + 1e-12; hi = m * math.pi / h - 1e-12
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            f = -g * mid * math.tan(mid * h) - om * om
            if f > 0:
                lo = mid
            else:
                hi = mid
        ks.append(1j * 0.5 * (lo + hi))
    return np.array(ks, complex)


def _Zprof(k, h, z):
    """normalised vertical eigenfunction cosh(k (z + h)) / cosh(k h) for real k; cos(kap (z + h)) / cos(kap h) for k = i kap."""
    if abs(k.imag) > 0:
        kap = k.imag
        return np.cos(kap * (z + h)) / math.cos(kap * h)
    return np.cosh(k.real * (z + h)) / math.cosh(k.real * h)


def reflection(om, x_nodes, h_nodes, ky=0.0, M=8, nz=240):
    """|R| and |T| (energy-flux transmission) of a plane wave (frequency om, alongshore wavenumber ky) incident from the left on a stepped bed:
    regions j = 0 .. N (depth h_j, region j spans x_nodes[j-1] .. x_nodes[j]); at each step, matching of the potential over the deeper column
    and of the horizontal velocity (zero normal flux on the step face) with M evanescent modes; global system for the mode amplitudes
    (left- and right-going in every region, outgoing only in the end regions) [computed]. Oblique: k_x = sqrt(k^2 - ky^2) per mode."""
    hs = np.asarray(h_nodes, float); xs = np.asarray(x_nodes, float)          # len(hs) = len(xs) + 1
    N = len(hs)
    K = [_roots(om, h, M) for h in hs]
    KX = []
    for k in K:
        kx = np.sqrt(k.astype(complex) ** 2 - ky * ky)
        kx = np.where(np.imag(kx) < 0, -kx, kx)                                 # decaying / outgoing: Im(kx) >= 0
        kx = np.where((np.abs(np.imag(kx)) < 1e-12) & (np.real(kx) < 0), -kx, kx)
        KX.append(kx)
    nm = M + 1
    # unknowns: region 0: R_m (left-going) ; regions 1..N-2: A_m (right-going), B_m (left-going) ; region N-1: T_m (right-going)
    # mode m in region j: phi = sum [A e^{i kx (x - xL_j)} + B e^{-i kx (x - xR_j)}] Z_m(z)  (referenced at the region ends: no overflow)
    nun = nm * (2 * N - 2)
    idx = {}
    c = 0
    idx[(0, "B")] = c; c += nm
    for j in range(1, N - 1):
        idx[(j, "A")] = c; c += nm
        idx[(j, "B")] = c; c += nm
    idx[(N - 1, "A")] = c; c += nm
    Mat = np.zeros((nun, nun), complex); rhs = np.zeros(nun, complex)
    row = 0
    for s in range(N - 1):                                                     # step s between region s (left) and s + 1 (right) at x = xs[s]
        hL, hR = hs[s], hs[s + 1]
        hd, hsh = max(hL, hR), min(hL, hR)
        z = np.linspace(-hd, 0.0, nz); wz = np.full(nz, z[1] - z[0]); wz[0] *= 0.5; wz[-1] *= 0.5
        deepL = hL >= hR
        ZL = np.array([_Zprof(k, hL, np.maximum(z, -hL)) * (z >= -hL - 1e-9) for k in K[s]])      # (nm, nz)
        ZR = np.array([_Zprof(k, hR, np.maximum(z, -hR)) * (z >= -hR - 1e-9) for k in K[s + 1]])
        # amplitude factors at x = xs[s] for each unknown block: left region s
        xLs = xs[s - 1] if s >= 1 else None
        def left_terms():
            terms = []
            if s == 0:
                # incident e^{i kx0 (x - xs[0])} (unit at the step), reflected B e^{-i kx (x - xs[0])}
                terms.append(("inc", None, None))
                terms.append(((0, "B"), np.ones(nm), -1.0))
            else:
                ex = np.exp(1j * KX[s] * (xs[s] - xs[s - 1]))
                terms.append(((s, "A"), ex, +1.0))
                terms.append(((s, "B"), np.ones(nm), -1.0))
            return terms
        def right_terms():
            terms = []
            if s + 1 == N - 1:
                terms.append(((N - 1, "A"), np.ones(nm), +1.0))
            else:
                ex = np.exp(1j * KX[s + 1] * (xs[s + 1] - xs[s]))
                terms.append(((s + 1, "A"), np.ones(nm), +1.0))
                terms.append(((s + 1, "B"), ex, -1.0))
            return terms
        # (1) potential continuity over the shallower column, projected on the shallow-side modes; (2) flux: deep-side velocity = shallow-side
        # velocity on the shallow column, 0 on the step face, projected on the deep-side modes
        Zs = ZR if deepL else ZL; Zd = ZL if deepL else ZR
        Ks_side = s + 1 if deepL else s
        on_sh = (z >= -hsh - 1e-9)
        for p in range(nm):                                                    # potential equations, test with shallow modes
            wtest = Zs[p] * wz * on_sh
            for side, Zmat, KXs, terms in (("L", ZL, KX[s], left_terms()), ("R", ZR, KX[s + 1], right_terms())):
                sg = 1.0 if side == "L" else -1.0
                proj = Zmat @ wtest                                             # (nm,)
                for key, fac, dirn in terms:
                    if key == "inc":
                        rhs[row] -= sg * proj[0] * 1.0
                        continue
                    i0 = idx[key]
                    Mat[row, i0:i0 + nm] += sg * proj * fac
            row += 1
        for p in range(nm):                                                    # flux equations, test with deep modes over the deep column
            wtest = Zd[p] * wz
            for side, Zmat, KXs, terms in (("L", ZL, KX[s], left_terms()), ("R", ZR, KX[s + 1], right_terms())):
                sg = 1.0 if side == "L" else -1.0
                proj = Zmat @ wtest
                for key, fac, dirn in terms:
                    if key == "inc":
                        rhs[row] -= sg * proj[0] * 1j * KXs[0]
                        continue
                    i0 = idx[key]
                    Mat[row, i0:i0 + nm] += sg * proj * fac * (1j * KXs * dirn)
            row += 1
    sol = np.linalg.solve(Mat, rhs)
    R0 = sol[idx[(0, "B")]]
    T0 = sol[idx[(N - 1, "A")]]
    # energy flux ratio: F ~ |a|^2 cg cos(theta) with a ~ phi amplitude x om / g; cg and k_x per region
    def cgx(om, k, kx, h):
        k = k.real; cg = 0.5 * (om / k) * (1 + 2 * k * h / math.sinh(2 * k * h))
        return cg * (kx.real / k)
    F0 = cgx(om, K[0][0], KX[0][0], hs[0]); FN = cgx(om, K[-1][0], KX[-1][0], hs[-1])
    Tflux = (abs(T0) ** 2 * FN / F0) if KX[-1][0].real > 0 else 0.0
    return dict(R=abs(R0), Rc=complex(R0), T_flux=float(Tflux), energy_sum=float(abs(R0) ** 2 + Tflux))


def bed_profile(kind, x_L=235.25, s2=3.0, shelf=6.0, s1=10.0, x_toe=160.25, h0=19.0, dx=0.5, x_end=None):
    """stepped approximation (dx) of the 1D bed from x_toe - 5 to the end of the slope; kind: '1to10_to_h' (1:10 down to depth 'shelf'),
    'two_slope' (1:10 to x_L, then 1:s2 to 'shelf')."""
    def h(x):
        u = np.maximum(x - x_toe, 0.0)
        if kind == "two_slope":
            uL = x_L - x_toe
            R = np.where(u <= uL, u / s1, uL / s1 + (u - uL) / s2)
        else:
            R = u / s1
        return np.maximum(shelf, h0 - R)
    xa = x_toe - 2.0
    xb = x_end if x_end is not None else (x_toe + (h0 - shelf) * s1 if kind != "two_slope" else x_L + (h0 - (x_L - x_toe) / s1 - shelf) * s2) + 2.0
    xn = np.arange(xa, xb + 1e-9, dx)
    xm = 0.5 * (xn[1:] + xn[:-1])
    hm = np.concatenate([[h(np.array(xa - 1.0))], h(xm), [h(np.array(xb + 1.0))]])
    return xn, hm


def refl():
    t0 = time.time()
    sea = B.sea_of()
    oms = [2 * math.pi / T for T in sea["T"]]
    out = dict(rule="linear potential theory, eigenfunction matching on a 0.5 m (1:10) / 0.25 m (steep) stepped bed, 8 evanescent modes; "
                    "R = reflected / incident amplitude; T_flux = transmitted energy-flux fraction; energy_sum = |R|^2 + T_flux (1 = closed) [computed]",
               variants={})
    variants = {
        "D19B_1to10_to_h6": dict(kind="1to10", shelf=6.0, dx=1.0),
        "c2_1to3_hL11p5_shelf6": dict(kind="two_slope", x_L=235.25, s2=3.0, shelf=6.0, dx=0.5),
        "c2_1to3_hL11p5_shelf5": dict(kind="two_slope", x_L=235.25, s2=3.0, shelf=5.0, dx=0.5),
        "c2_1to3_hL11p5_shelf7": dict(kind="two_slope", x_L=235.25, s2=3.0, shelf=7.0, dx=0.5),
        "c3_1to5_hL11p5_shelf6": dict(kind="two_slope", x_L=235.25, s2=5.0, shelf=6.0, dx=0.5),
        "c4_1to2_hL11p5_shelf6": dict(kind="two_slope", x_L=235.25, s2=2.0, shelf=6.0, dx=0.5),
    }
    for nm, v in variants.items():
        # reflection of the part beyond x_L only (the 1:10 approach is common): bed from x_L - 2 (or the 1:10 at the same depths for D19B)
        if v["kind"] == "two_slope":
            x_toe2 = v["x_L"]; h_start = 19.0 - (v["x_L"] - 160.25) / 10.0
            xn, hm = bed_profile("1to10", x_toe=x_toe2, h0=h_start, s1=v["s2"], shelf=v["shelf"], dx=v["dx"])
        else:
            h_start = 11.5
            xn, hm = bed_profile("1to10", x_toe=235.25, h0=h_start, s1=10.0, shelf=v["shelf"], dx=v["dx"])
        res = {}
        for T, om in zip(sea["T"], oms):
            for th in (0.0, 30.0, 50.0):
                k0 = _roots(om, hm[0], 0)[0].real
                ky = k0 * math.sin(math.radians(th))
                r = reflection(om, xn, hm, ky=ky)
                res["T%.2f_th%d" % (T, th)] = r
        out["variants"][nm] = dict(spec=v, h_start=h_start, n_steps=len(xn), res=res)
        print(nm, json.dumps({k: round(q["R"], 3) for k, q in res.items()}), json.dumps({k: round(q["energy_sum"], 3) for k, q in res.items()}), flush=True)
    # sanity: a single sharp step 11.5 -> 6 m (long-wave limit (1 - sqrt(h2/h1)) / (1 + sqrt(h2/h1)) = 0.141)
    out["check_sharp_step_T60"] = reflection(2 * math.pi / 60.0, np.array([0.0]), np.array([11.5, 6.0]))
    out["check_sharp_step_longwave_R"] = (1 - math.sqrt(6 / 11.5)) / (1 + math.sqrt(6 / 11.5))
    out["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(out, B.OUT + "/screen2_refl.json")
    print("check", out["check_sharp_step_T60"], out["check_sharp_step_longwave_R"])
    return out


# ============================================================================ measured reflection in DFG-2B-E (directional split of the harmonic maps)
def reflm(x_rng=(104.0, 160.0), y_max=95.0, ndir=46, ridge=1e-3):
    """least-squares split of each FLIP harmonic map (diag/harm_DFGB2E.npz, windows W2 / P1 / P3) on the flat part x 104-160 m (h 19 m),
    y <= 95 m, into plane waves e^{+- i kx x} cos(ky y) (symmetric about y = 0; theta 0-88 deg); reflected / incident amplitude
    ratio = sqrt(sum |a-|^2 / sum |a+|^2) per layer [measured].
    NOT USED: on a 56 m window the +- kx split of the wide-angle components is ill-conditioned (R 0.5-0.7 is an artefact of the ridge
    splitting near-degenerate columns); kept only as a record of the attempt (its json was deleted)."""
    t0 = time.time()
    Z = np.load(B.OUT + "/harm_DFGB2E.npz")
    x = Z["x"]; y = Z["y"]
    mx = (x >= x_rng[0]) & (x <= x_rng[1]); my = y <= y_max
    X_, Y_ = np.meshgrid(x[mx], y[my])
    out = dict(rule=reflm.__doc__.strip(), x_rng=x_rng, y_max=y_max, res={})
    oms = {int(n): float(o) for n, o in zip(Z["ns"], Z["om"])}
    P = 28.0
    for win in ("W2", "P1", "P3"):
        for n in (1, 2, 3, 4, 5):
            key = "%s_n%d" % (win, n)
            if key not in Z.files:
                continue
            om = 2 * math.pi * n / P
            k = _roots(om, 19.0, 0)[0].real
            th = np.radians(np.linspace(0.0, 88.0, ndir))
            kx = k * np.cos(th); ky = k * np.sin(th)
            cols = []
            for sgn in (1.0, -1.0):
                for a, b in zip(kx, ky):
                    cols.append((np.exp(1j * sgn * a * X_) * np.cos(b * Y_)).ravel())
            M = np.stack(cols, 1)
            d = Z[key].astype(complex)[np.ix_(my, mx)].ravel()
            A = M.conj().T @ M; rhs = M.conj().T @ d
            lam = ridge * np.trace(A).real / A.shape[0]
            c = np.linalg.solve(A + lam * np.eye(A.shape[0]), rhs)
            ap = c[:ndir]; am = c[ndir:]
            fit = M @ c
            rel = float(np.linalg.norm(d - fit) / np.linalg.norm(d))
            out["res"][key] = dict(n=n, T=P / n, R_amp=float(np.sqrt(np.sum(np.abs(am) ** 2) / np.sum(np.abs(ap) ** 2))), rel_resid=rel,
                                   rms_map=float(np.sqrt(np.mean(np.abs(d) ** 2))))
    out["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(out, B.OUT + "/screen2_reflm.json")
    print(json.dumps({k: (round(v["R_amp"], 3), round(v["rel_resid"], 3), round(v["rms_map"], 3)) for k, v in out["res"].items()}))
    return out


# ============================================================================ linear G4 side-band maximum: base vs phase pre-compensation (b)
def g4lin(dphi=(-0.060788, 0.279111, 0.513994), x_fs=(250.25, 260.25)):
    """kp x max_t eta_lin over the generating side band (y >= 95 m, x <= 180.25 m) and the inlet band (x <= 100 m) of the plain linear WKB design
    sea (all 34 directions, as tabulated), base and with the per-layer table phase pre-compensation e^{-i dphi_n} (judge G2f phases) [computed];
    FLIP / linear at the base = measured 0.397067 / linear [calibrated]."""
    t0 = time.time()
    sea = B.sea_of()
    x = np.arange(0.5, 181.0, 1.0); y = np.arange(0.5, 140.0, 1.0)
    maps, _ = B.lin_maps(x, y, sea)
    oms = [2 * math.pi / T for T in sea["T"]]
    tp = np.arange(0.0, 28.0, 1.0 / 12.0)
    sd = (y[:, None] >= 95.0) & (x[None, :] <= 180.25)
    inl = (x[None, :] <= 100.0) & np.ones((len(y), 1), bool)
    res = {}
    for lab, dp in (("base", (0.0, 0.0, 0.0)), ("G2f_comp", dphi)):
        best_s = (-1.0, None); best_i = (-1.0, None)
        for t in tp:
            e = np.zeros((len(y), len(x)))
            for A, om, d in zip(maps, oms, dp):
                e += np.real(A * np.exp(-1j * d) * np.exp(-1j * om * t))
            vs = np.where(sd, e, -1e9); j = int(np.argmax(vs)); iy, ix = np.unravel_index(j, vs.shape)
            if vs[iy, ix] > best_s[0]:
                best_s = (float(vs[iy, ix]), dict(t_rel_tf=float(t), x=float(x[ix]), y=float(y[iy])))
            vi = np.where(inl, e, -1e9); j = int(np.argmax(vi)); iy, ix = np.unravel_index(j, vi.shape)
            if vi[iy, ix] > best_i[0]:
                best_i = (float(vi[iy, ix]), dict(t_rel_tf=float(t), x=float(x[ix]), y=float(y[iy])))
        res[lab] = dict(side_kA=KP * best_s[0], side_at=best_s[1], inlet_kA=KP * best_i[0], inlet_at=best_i[1])
    ratio = 0.397067 / res["base"]["side_kA"]
    res["FLIP_over_linear_side_base"] = ratio
    for xf in x_fs:                                                            # candidate (a): seaward design focus, same sea and bands
        mp, _ = B.lin_maps(x, y, sea, x_f=xf)
        bs = -1.0
        for t in tp:
            e = np.zeros((len(y), len(x)))
            for A, om in zip(mp, oms):
                e += np.real(A * np.exp(-1j * om * t))
            bs = max(bs, float(np.max(np.where(sd, e, -1e9))))
        res["xf%.2f" % xf] = dict(side_kA=KP * bs, side_FLIP_equiv=KP * bs * ratio)
    res["G2f_comp_side_FLIP_equiv"] = res["G2f_comp"]["side_kA"] * ratio
    res["cpu_s"] = round(time.time() - t0, 1)
    B.jdump(res, B.OUT + "/screen2_g4lin.json")
    print(json.dumps(res, default=float))
    return res


# ============================================================================ reflected linear field of the candidate face: G4 and the converged crest
def g4refl(x_L=235.25, s2=3.0, shelf=5.0, label="c2_1to3_hL11p5_shelf5"):
    """upper bound of the G4 change from the wave reflected by the candidate face (1:s2 from x_L to the shelf): every design component j
    (layer n, alongshore ky_j conserved) is reflected at x_r = x_L - 2 m with the complex linear coefficient R_n(ky_j) of the eigenfunction
    model (refl), mirrored in x with its WKB amplitude and phase: A_r = R A_j(x) exp(i (2 Phi_j(x_r) - Phi_j(x))) exp(i ky_j y); NO band damping
    (the side band relaxes deviations at x <= 180 m and absorbs at x >= 210 m: real values lower). Reported: kp x max_t eta in the side band
    with and without A_r (linear; FLIP-equivalent x 1.0397 = measured / linear at the base), the reflected field alone, and the effect on
    the centre-line crest maximum at x 220-240 m [computed]."""
    t0 = time.time()
    sea = B.sea_of()
    xr = x_L - 2.0
    xg = np.arange(0.5, 241.0, 1.0)
    dfs, xgu = B.dirfields(xg, sea)
    idx = np.array([int(np.argmin(np.abs(xgu - v))) for v in xg]); ir = int(np.argmin(np.abs(xgu - xr)))
    y = np.arange(0.5, 140.0, 1.0)
    h_start = 19.0 - (x_L - 160.25) / 10.0
    xn, hm = bed_profile("1to10", x_toe=x_L, h0=h_start, s1=s2, shelf=shelf, dx=0.5)
    xn = xn - xn[0] + xr                                                          # first step at x_r
    Ainc = []; Aref = []; Rtab = []
    for n, d in enumerate(dfs):
        Ai = np.zeros((len(y), len(xg)), complex); Ar = np.zeros_like(Ai)
        cache = {}
        for j in range(len(d.a)):
            kyj = float(d.ky[j]); key = round(abs(kyj), 6)
            if key not in cache:
                cache[key] = reflection(d.om, xn, hm, ky=abs(kyj))["Rc"]
            R = cache[key]
            ey = np.exp(1j * kyj * y)[:, None]
            Ai += ey * (d.Aj[j, idx] * np.exp(1j * d.Phi[j, idx]))[None, :]
            Ar += ey * (R * d.Aj[j, idx] * np.exp(1j * (2.0 * d.Phi[j, ir] - d.Phi[j, idx])))[None, :]
        Ainc.append(Ai); Aref.append(Ar)
        Rtab.append({("ky%.4f" % k): [abs(v), float(np.angle(v))] for k, v in sorted(cache.items())})
    oms = [2 * math.pi / T for T in sea["T"]]
    tp = np.arange(0.0, 28.0, 1.0 / 12.0)
    sd = (y[:, None] >= 95.0) & (xg[None, :] <= 180.25)
    cl = (y[:, None] <= 1.0) & (xg[None, :] >= 220.0) & (xg[None, :] <= 240.0)
    best = {k: (-1e9, None) for k in ("side_inc", "side_tot", "side_ref", "crest_inc", "crest_tot")}
    for t in tp:
        ei = np.zeros((len(y), len(xg))); er = np.zeros_like(ei)
        for A, R_, om in zip(Ainc, Aref, oms):
            ph = np.exp(-1j * om * t)
            ei += np.real(A * ph); er += np.real(R_ * ph)
        for k, f, m in (("side_inc", ei, sd), ("side_tot", ei + er, sd), ("side_ref", er, sd), ("crest_inc", ei, cl), ("crest_tot", ei + er, cl)):
            v = np.where(m, f, -1e9); j = int(np.argmax(v)); iy, ix = np.unravel_index(j, v.shape)
            if v[iy, ix] > best[k][0]:
                best[k] = (float(v[iy, ix]), dict(t_rel_tf=float(t), x=float(xg[ix]), y=float(y[iy])))
    rat = 1.0396613547863491
    # G2f gauges (x 110 m, y 0.5 / 20 / 40 / 60 / 80 m): amplitude-sum ratio and the summed phase change from adding A_r [computed]
    ix110 = int(np.argmin(np.abs(xg - 110.0))); gy = [int(np.argmin(np.abs(y - v))) for v in (0.5, 20.0, 40.0, 60.0, 80.0)]
    g2f = []
    for n, (A, R_) in enumerate(zip(Ainc, Aref)):
        ai = A[gy, ix110]; at = (A + R_)[gy, ix110]
        g2f.append(dict(layer=n, R_change=float(np.sum(np.abs(at)) / np.sum(np.abs(ai))),
                        phase_change_rad=float(np.angle(np.sum(at * np.conj(ai) / np.abs(ai)))), ref_over_inc_per_gauge=list(np.abs(R_[gy, ix110]) / np.abs(ai))))
    out = dict(label=label, G2f_gauges_effect=g2f, rule=g4refl.__doc__.strip(), x_L=x_L, s2=s2, shelf=shelf, x_r=xr,
               side_kA_lin=dict(inc=KP * best["side_inc"][0], tot=KP * best["side_tot"][0], ref_alone=KP * best["side_ref"][0]),
               side_at=dict(inc=best["side_inc"][1], tot=best["side_tot"][1], ref=best["side_ref"][1]),
               side_kA_FLIP_equiv=dict(inc=rat * KP * best["side_inc"][0], tot=rat * KP * best["side_tot"][0]),
               delta_side_FLIP_equiv=rat * KP * (best["side_tot"][0] - best["side_inc"][0]),
               crest_lin=dict(inc=best["crest_inc"][0], tot=best["crest_tot"][0], ratio=best["crest_tot"][0] / best["crest_inc"][0],
                              at_inc=best["crest_inc"][1], at_tot=best["crest_tot"][1]),
               R_by_layer_ky=Rtab, cpu_s=round(time.time() - t0, 1))
    B.jdump(out, B.OUT + "/screen2_g4refl_%s.json" % label)
    print(json.dumps({k: out[k] for k in ("side_kA_lin", "delta_side_FLIP_equiv", "crest_lin", "G2f_gauges_effect")}, default=float))
    return out


# ============================================================================ breaking-factor (BF) model of the e51 shape at the lip
DFGS_DIAG = B.REPO + "/Unity/Build/FLIP52S2/screens/design_20261018/dfgs_diag.json"
KEYS = ("W50", "W80", "W95", "S2")


def bfmodel():
    """Measured: from the start of breaking to the lip / most print-like frame, the e51 widths and S2 grow by factors that look bed-independent
    (DFG-2B-E 1:10 beach: start = first tracked frame with B = u_s / c >= 0.75 after the converged instant, end = pv53 most print-like frame;
    DFG-S 1:3 face + 6 m shelf: start = first frame with Hc / h >= 0.75 (the shelf edge), end = the r2 onset frame) [measured].
    Model: lip state = start state x factors; miss = e51 score_vs_target (log excess over the core ranges, K not in the factor set: 0 in
    every measured lip). Start states: DFG-2B-E as run = its measured B 0.75 state (self-check); candidate (c) = the measured converged state
    (breaking starts at the face toe, 0 s capped ride) or the state 0.25 s / 0.5 s later on 1:10 (late start); per group, every factor set
    of the 6 measured groups [calibrated]."""
    t0 = time.time()
    TJ = B.jload(B.OUT + "/track_DFGB2E.json")
    PV = B.jload(B.PV53)
    fac = []; starts = {}
    for g in TJ["groups"]:
        s = g["series"]; tr = np.array(s["t_rel_conv"], float); Bv = np.array([v if v is not None else np.nan for v in s["B"]])
        i0 = int(np.argmin(np.abs(tr)))
        ib = next(i for i in range(i0, len(tr)) if Bv[i] >= 0.75)
        pl = g["print_like"]
        end = dict(W50=pl["W50"], W80=pl["W80"], W95=pl["W95"], S2=pl["S2"])
        st = {k: s["e51_" + k][ib] for k in KEYS}
        fac.append(dict(src="DFGB2E G%d" % g["n"], start_t_rel_conv=float(tr[ib]), f={k: end[k] / st[k] for k in KEYS}, start=st, end=end))
        sts = {}
        for lab, dt in (("toe_0s", 0.0), ("late_0p25s", 0.25), ("late_0p5s", 0.5)):
            i = int(np.argmin(np.abs(tr - dt)))
            sts[lab] = {k: s["e51_" + k][i] for k in KEYS}
        sts["asrun_B0p75"] = st
        starts["G%d" % g["n"]] = sts
    D = B.jload(DFGS_DIAG)
    for g in D["groups"]:
        fr = g["frames"]; ton = g["onset"]["t"]
        h_of = lambda x: max(6.0, 20.0 - max(x - 108.0, 0.0) / 3.0)
        i0 = next(i for i, f in enumerate(fr) if f["t"] >= g["conv"]["t"] - 1e-6)
        ib = next(i for i in range(i0, len(fr)) if fr[i]["Hc"] / h_of(fr[i]["x_pk"]) >= 0.75)
        ie = int(np.argmin([abs(f["t"] - ton) for f in fr]))
        st = {k: fr[ib][k] for k in KEYS}; en = {k: fr[ie][k] for k in KEYS}
        fac.append(dict(src="DFGS G%d" % g["n"], start_t_rel_on=fr[ib]["t"] - ton, f={k: en[k] / st[k] for k in KEYS}, start=st, end=en))

    def miss(m):
        return B.EM.score_vs_target(dict(m, K=None))[0]
    res = {}
    for lab in ("asrun_B0p75", "toe_0s", "late_0p25s", "late_0p5s"):
        rows = []
        for gn, sts in starts.items():
            for F in fac:
                m = {k: sts[lab][k] * F["f"][k] for k in KEYS}
                rows.append(dict(group=gn, factors=F["src"], miss=miss(m), state=m))
        ms = np.array([r["miss"] for r in rows])
        res[lab] = dict(median=float(np.median(ms)), p10=float(np.percentile(ms, 10)), p90=float(np.percentile(ms, 90)), min=float(ms.min()),
                        max=float(ms.max()), group_medians={gn: float(np.median([r["miss"] for r in rows if r["group"] == gn])) for gn in starts},
                        n=len(rows))
    out = dict(rule=bfmodel.__doc__.strip(), factors=fac, starts=starts, predictions=res,
               measured_lip_miss_DFGB2E=[g["print_like"]["miss"] for g in TJ["groups"]], cpu_s=round(time.time() - t0, 1))
    B.jdump(out, B.OUT + "/screen2_bfmodel.json")
    print(json.dumps(dict(factors=[(F["src"], {k: round(v, 2) for k, v in F["f"].items()}) for F in fac], predictions=res,
                          measured=out["measured_lip_miss_DFGB2E"]), default=float))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["g4ts"]:
        g4ts()
    elif a[:1] == ["refl"]:
        refl()
    elif a[:1] == ["reflm"]:
        reflm()
    elif a[:1] == ["g4lin"]:
        g4lin()
    elif a[:1] == ["bfmodel"]:
        bfmodel()
    elif a[:1] == ["g4refl"]:
        g4refl()
        g4refl(shelf=6.0, label="c2_1to3_hL11p5_shelf6")
        g4refl(s2=5.0, shelf=6.0, label="c3_1to5_hL11p5_shelf6")
    else:
        print(__doc__)
