# -*- coding: utf-8 -*-
"""Pinnacle / lens / fan sweep with the calibrated linear predictor. py -3.10 -B. [computed]
Predictor (calibrated on DM1A, DF1A, DA3 onsets, calib.json): widths W(f) = shape widths of the linear crest line at the break
instant (level f x linear summit), in metres, divided by Hc_pred = r_hc h_b; S2s / ring_s = linear side height / linear summit."""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M
import l51_screen as S

TARGET = dict(W50=(1.5, 2.6), W80=(0.8, 1.25), W95=(0.4, 0.85), K=(2.0, 4.5), S2=(0.05, 0.35), W20=(2.3, 3.6), ring_max=(0.15, 0.45))


def miss(m, core=("W50", "W80", "W95", "K", "S2")):
    t = 0.0
    for k in core:
        v = m.get(k)
        if v is None or not np.isfinite(v) or v <= 0:
            t += 3.0; continue
        lo, hi = TARGET[k]
        t += math.log(v / hi) if v > hi else (math.log(lo / v) if v < lo else 0.0)
    return t


def shape_at(tk, A1, ib, Hc, cw=(30.0, 10.0)):
    """shape metrics of the linear field with the crest at axis index ib (unit-independent), widths in m."""
    x, y = tk.x, tk.y
    A = A1
    ts = np.angle(A[0, ib]) / tk.om
    eta = np.real(A * np.exp(-1j * tk.om * ts))
    xb = x[ib]
    cwin = (x >= xb - cw[0]) & (x <= xb + cw[1])
    c = np.max(np.where(cwin[None, :], eta, -np.inf), axis=1)
    yy = np.concatenate([-y[:0:-1], y]); cc = np.concatenate([c[:0:-1], c]); i0 = len(y) - 1
    Hl = float(cc[i0])
    out = dict(H_lin=Hl)
    for f in (0.2, 0.5, 0.8, 0.95):
        wv, ce = M.run_width(cc, yy, i0, f * Hl)
        out["W%d" % int(round(f * 100))] = wv / Hc
        out["W%d_m" % int(round(f * 100))] = wv
        out["W%d_cens" % int(round(f * 100))] = bool(ce)
    out["K"] = out["W20"] / out["W80"] if out["W80"] > 0 else float("nan")
    out["taper"] = out["W80"] / out["W50"] if out["W50"] > 0 else float("nan")
    out["S1"] = float(np.interp(1 * Hc, y, c) / Hl)
    out["S2"] = float(np.interp(2 * Hc, y, c) / Hl)
    XX, YY = np.meshgrid(x, y)
    r = np.hypot(XX - xb, YY)
    ring = (r >= 2 * Hc) & (r <= 5 * Hc) & (XX <= xb + 10)
    out["ring_max"] = float(np.max(eta[ring]) / Hl) if ring.any() else float("nan")
    # longitudinal: summit row
    row = eta[0]
    wv, ce = M.run_width(row, x, ib, 0.5 * Hl)
    out["Lx50"] = wv / Hc
    out["A50"] = out["W50"] / out["Lx50"] if out["Lx50"] > 0 else float("nan")
    return out


def sweep_ainc(tk, A1, gamma_b, r_hc, a_list, x_min=110.0, label="", extra=None):
    x, h = tk.x, tk.h
    hax = h[0]
    L_loc = 2 * math.pi / float(np.median(tk.k[0][(x > x_min) & (hax > 3)]))
    As = S.smooth_rms(A1[0], x, 0.5 * L_loc)
    M2 = np.where(hax > 1.0, 2 * As / np.maximum(hax, 1e-6), 0)     # gamma per unit incident amplitude
    rows = []
    for a in a_list:
        hit = (x >= x_min) & (a * M2 >= gamma_b)
        if not hit.any():
            rows.append(dict(a_inc=a, broke=False, gamma_max=float(a * M2[x >= x_min].max()))); continue
        ib = int(np.argmax(hit)); hb = float(hax[ib]); Hc = r_hc * hb
        o = shape_at(tk, A1, ib, Hc)
        # early breaking off-axis (anywhere on the lens / flanks), linear 2|A|/h, upstream of x_b - 10 and outside the axis strip
        g2 = np.where(h > 1.0, 2 * a * np.abs(A1) / np.maximum(h, 1e-6), 0)
        X = x[None, :]
        offaxis = (X >= x_min) & (X <= x[ib] - 10.0)
        o.update(a_inc=a, broke=True, x_b=float(x[ib]), h_b=hb, Hc_pred=Hc, gain_b=float(As[ib]), early=float(np.max(np.where(offaxis, g2, 0.0)) / gamma_b),
                 c_in_over_Hc=float(a / Hc), H_lin_over_a=float(o["H_lin"]))
        o["miss"] = miss(o)
        rows.append(o)
    return rows


def pinnacle_case(T, h0, xc, R, h_top, shape="cos2", Ry=None, Lx=600.0, W=300.0, periods=30):
    x = np.arange(0, Lx + 1e-9, S.DX); y = np.arange(0, W + 1e-9, S.DX)
    X, Y = np.meshgrid(x, y)
    h = h0 * np.ones_like(X) - M.mound(x, y, xc, R, Ry if Ry else R, h0 - h_top, shape=shape)
    tk, A1, AT = S.run_case(T, x, y, h, target_kind="plane", side=(W - 45.0, 1e9, 1e9 + 1), exit_x0=Lx - 100.0, swash=(2.0, 2.0, 2),
                            periods=periods)
    return tk, A1


if __name__ == "__main__":
    t0 = time.time()
    res = []
    a_list = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 3.5, 4.0]
    which = sys.argv[1] if len(sys.argv) > 1 else "pin"
    if which == "pin":
        for (R, ht, shape) in [(60, 4, "cos2"), (90, 4, "cos2"), (120, 4, "cos2"), (160, 4, "cos2"), (120, 7, "cos2"), (160, 7, "cos2"),
                               (120, 4, "cap"), (160, 4, "cap"), (200, 6, "cap"), (120, 2, "cone"), (200, 2, "cone")]:
            tk, A1 = pinnacle_case(12.0, 19.0, 330.0, float(R), float(ht), shape=shape)
            for gb in (1.1, 1.3, 1.6):
                rows = sweep_ainc(tk, A1, gb, 0.80, a_list)
                best = min([r for r in rows if r.get("broke")], key=lambda r: r["miss"], default=None)
                res.append(dict(case="pin_R%d_ht%g_%s" % (R, ht, shape), gamma_b=gb, rows=rows, best=best))
                if best:
                    print("R%3d ht%2g %-4s gb%.1f best a%.2f xb%.0f hb%.1f Hc%.1f gain%.2f early%.2f | W20 %.1f W50 %.2f W80 %.2f W95 %.2f K %.2f S2 %.2f ring %.2f Lx50 %.2f cin/Hc %.2f miss %.2f" % (
                        R, ht, shape, gb, best["a_inc"], best["x_b"], best["h_b"], best["Hc_pred"], best["gain_b"], best["early"], best["W20"], best["W50"], best["W80"],
                        best["W95"], best["K"], best["S2"], best["ring_max"], best["Lx50"], best["c_in_over_Hc"], best["miss"]), flush=True)
            np.savez_compressed(os.path.join(S.OUT, "pin_R%d_ht%g_%s_A1.npz" % (R, ht, shape)), A=A1, x=tk.x, y=tk.y, h=tk.h)
    json.dump(dict(res=res, wall_s=time.time() - t0), open(os.path.join(S.OUT, "sweep_%s.json" % which), "w"), indent=1, default=float)
    print("wall", time.time() - t0)
