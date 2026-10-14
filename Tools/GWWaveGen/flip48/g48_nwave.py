# -*- coding: utf-8 -*-
"""FLIP48 R3：谷のある波の表（Tanaka の厳密な孤立波の頂 ＋ 頂の前の線形の長い波の谷）を作る（py -3.10 -B、numpy だけ。数秒）。
2026-10-15 新しく書いた。Unity/Build/FLIP48/plan/campaign_R3_judge.json の queue[0]（G0）の wave（plan/plan_R3_frozen.json に凍らせた）：
  η = η_T(x) + η_t(x)、η_t = −β a sech²(k_s (x − x0 − d))、a = A h0（A 0.3 で 5.10 m）、
  k_s = 0.024472 /m（A 0.3 の GN の κ = 判定の 0.02447。β・A によらず固定【選び：1 本で 1 つだけ変えるため】）、d = dk/k_s（既定 1.6/k_s = 65.4 m）
  u = u_T(x, z) + u_t(x)、u_t = c0 η_t/(h0 + η)（深さによらない。c0 = √(g h0) = 12.91 m/s）
  w = w_T(x, z) + w_t(x, z)、w_t = −(z + h0) du_t/dx（∂u_t/∂x + ∂w_t/∂z = 0、海底で w_t = 0）
  水面が下がった所（η < η_T）の u_T・w_T は Tanaka の表の水の中の値。水面より上は水面 η の値で埋める（u_ext・w_ext。表と同じ決まり）。
これは定常な解ではない：頂は c（14.69 m/s）で、谷は c0（12.91 m/s）で進む形を重ねただけで、重なり（頂の裾は谷の真ん中で +0.77 m）と、
尾根の始まり（x 143 m）・溝の入り口（x 150〜190 m）との重なりで、初めに揺れが出る（測っていない。G0 が 2D でだけ測る）。
「長いうねりの一つの山と、その前の谷」という仮定の波で、測った物ではない。
鍵は Tanaka の表（g46_solitary.write_grid）と同じ（x・z・eta・u・w・u_ext・w_ext・u_surf・w_surf・c・F・a_over_h・h0・x0・t・meta・info）に、
kind・beta・k_s・d・dk・c0_trough・a_m・src_tanaka を足した。場面の solution_table（g48_tanklib.PYSOP）と VEX はそのまま読む
（c・x0 は頂の物。g48_run.py の初めのコマの確かめは頂の真下で比べる）。
使い方：
  py -3.10 -B g48_nwave.py                        β 0.12（既定）の表を書き、g48_cfg.table_checks と谷の確かめを走らせる
  py -3.10 -B g48_nwave.py --beta 0.09            β 0.09 の表（0.15・0.06・0.18 も同じ一行。R4・R5 の β の段）
  py -3.10 -B g48_nwave.py --A 0.35 --beta 0.12   A 0.35 の頂（Tanaka の表 tanaka_a0p35_x107.npz が無ければ g48_cfg.sol_table が作る）
  [--dk 1.6] [--ks 0.024472] [--force]（--force：同じ名前の表を書き直す）
出す物：Unity/Build/FLIP48/solitary/nwave_a<A>_b<β>_d<dk>_x107.npz と、同じ名前の _check.json（確かめ）
"""
import os, sys, json, math, time, argparse

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                 # noqa: E402
import g48_common as GC            # noqa: E402

trapz = getattr(np, "trapezoid", None) or np.trapz


def _interp_z(F, z, zq):
    """F[nz, nx]（z は等間隔で増える）を各列 j で zq[nz, nx] の高さに線形に補う。zq は z の範囲の中。"""
    dz = z[1] - z[0]
    f = (zq - z[0]) / dz
    i = np.clip(np.floor(f).astype(int), 0, len(z) - 2)
    w = np.clip(f - i, 0.0, 1.0)
    jj = np.broadcast_to(np.arange(F.shape[1])[None, :], zq.shape)
    return F[i, jj] * (1.0 - w) + F[i + 1, jj] * w


def build(pT, A, beta, dk, ks, x0=GC.X0_CREST, g=GC.G):
    """Tanaka の表 pT に谷を足した配列を返す（書かない）。"""
    d = np.load(pT)
    x = np.asarray(d["x"], float); z = np.asarray(d["z"], float)
    etaT = np.asarray(d["eta"], float)
    uTe = np.asarray(d["u_ext"], float); wTe = np.asarray(d["w_ext"], float)
    h0 = float(d["h0"])
    if abs(h0 - GC.H0) > 1e-9:
        raise SystemExit("Tanaka の表の h0 %r が %r でない" % (h0, GC.H0))
    if not np.allclose(np.diff(z), z[1] - z[0]):
        raise SystemExit("Tanaka の表の z が等間隔でない")
    a = float(d["a_over_h"]) * h0
    dd = dk / ks
    xi = ks * (x - x0 - dd)
    S = 1.0 / np.cosh(xi) ** 2
    eta_t = -beta * a * S
    eta_t_x = 2.0 * beta * a * ks * S * np.tanh(xi)
    eta = etaT + eta_t
    eta_x = np.gradient(etaT, x) + eta_t_x
    c0 = math.sqrt(g * h0)
    u_t = c0 * eta_t / (h0 + eta)
    du_t = c0 * (eta_t_x * (h0 + eta) - eta_t * eta_x) / (h0 + eta) ** 2
    if eta.max() > z[-1] or eta.min() < z[0]:
        raise SystemExit("水面が表の z の範囲の外")
    Z = np.broadcast_to(z[:, None], uTe.shape)
    zq = np.minimum(Z, eta[None, :])                         # 水面より上は水面の高さ
    uq = _interp_z(uTe, z, zq); wq = _interp_z(wTe, z, zq)
    u_ext = uq + u_t[None, :]
    w_ext = wq - (zq + h0) * du_t[None, :]
    below = Z <= eta[None, :]
    u = np.where(below, u_ext, np.nan); w = np.where(below, w_ext, np.nan)
    e1 = eta[None, :]
    us = _interp_z(uTe, z, e1)[0] + u_t
    ws = _interp_z(wTe, z, e1)[0] - (eta + h0) * du_t
    return dict(x=x, z=z, eta=eta, u=u, w=w, u_ext=u_ext, w_ext=w_ext, u_surf=us, w_surf=ws, c=float(d["c"]), F=float(d["F"]),
                a_over_h=float(d["a_over_h"]), h0=h0, x0=float(d["x0"]), t=float(d["t"]) if "t" in d.files else 0.0,
                a=a, d=dd, c0=c0, eta_T=etaT, eta_t=eta_t, u_t=u_t, src_meta=str(d["meta"]) if "meta" in d.files else "")


def make(A=GC.A0, beta=GC.BETA_R3, dk=GC.DK_R3, ks=None, x0=GC.X0_CREST, force=False):
    """谷のある波の表を書く（あれば書かない）。返り値 (パス, 情報)。"""
    import g48_cfg as CF
    ks = float(ks) if ks else GC.KS_R3
    p = GC.nwave_path(A, beta, dk, x0)
    if os.path.exists(p) and not force:
        d = np.load(p)
        return p, dict(made="exists", beta=float(d["beta"]), k_s=float(d["k_s"]), d=float(d["d"]), sha256=GC.sha256_file(p)[:16])
    if not (0.0 <= beta <= 0.5):
        raise SystemExit("β %r は 0〜0.5 の外（計画の範囲は 0.06〜0.18）" % beta)
    pT, si = CF.sol_table(A, x0)
    t0 = time.time()
    b = build(pT, A, beta, dk, ks, x0)
    meta = dict(method="Tanaka (1986) exact solitary crest (g46_solitary table) + linear long-wave leading trough (FLIP48 R3 'nwave')",
                made_by="Tools/GWWaveGen/flip48/g48_nwave.py", date=time.strftime("%Y-%m-%d %H:%M:%S"),
                src_tanaka=pT, src_tanaka_sha256=GC.sha256_file(pT)[:16], A=float(A), a_m=b["a"], beta=float(beta), k_s=ks, dk=float(dk), d_m=b["d"],
                c_crest=b["c"], c0_trough=b["c0"], h0=b["h0"], x0=b["x0"], g=GC.G,
                eta="eta_T(x) - beta*a*sech^2(k_s*(x - x0 - d))",
                u="u_T(x,z) + c0*eta_t/(h0+eta) (uniform in z)", w="w_T(x,z) - (z+h0)*d(u_t)/dx",
                above_surface="u, w NaN; u_ext, w_ext filled with the value at the (new) surface",
                steady=False,
                note="NOT a steady solution: the crest part moves at c, the trough part at c0; their overlap and the overlap with the ridge toe "
                     "(x 143 m) and the channel ramp (x 150-190 m) give transients that are not measured. Assumed to be one crest of a long swell.",
                tags=dict(beta="chosen", k_s="chosen (= GN kappa at A 0.3, held fixed)", dk="chosen", c0="computed", crest="computed (Tanaka exact)"),
                units="m, m/s", layout="u[z, x]", frame="crest at x0 + c t, trough centre at x0 + d + c0 t (approx.)", z="still water z = 0, flat bed z = -h0", t=0.0)
    js = json.dumps(meta, ensure_ascii=False)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    np.savez_compressed(p, x=b["x"], z=b["z"], eta=b["eta"], u=b["u"], w=b["w"], u_ext=b["u_ext"], w_ext=b["w_ext"], u_surf=b["u_surf"],
                        w_surf=b["w_surf"], c=np.float64(b["c"]), F=np.float64(b["F"]), a_over_h=np.float64(b["a_over_h"]), h0=np.float64(b["h0"]),
                        x0=np.float64(b["x0"]), t=np.float64(0.0), meta=js, info=js, kind="nwave", beta=np.float64(beta), k_s=np.float64(ks),
                        d=np.float64(b["d"]), dk=np.float64(dk), c0_trough=np.float64(b["c0"]), a_m=np.float64(b["a"]), src_tanaka=pT)
    return p, dict(made="new", s=round(time.time() - t0, 2), beta=float(beta), k_s=ks, d=b["d"], sha256=GC.sha256_file(p)[:16], tanaka=si)


def nwave_checks(p):
    """g48_cfg.table_checks（形を変えない波の流量 Q = c η は谷では成り立たない。並べて書くだけ）と、谷の確かめ：
    水面の最小とその x、尾根の始まり・溝の入り口での η、谷の体積、Green の法則での棚の上の谷の上限、作り方の流量の一致（Q − c0 η_t と
    Tanaka の流れを新しい水面まで積んだ物）、∂u/∂x + ∂w/∂z、NaN。"""
    import g48_cfg as CF
    out = dict(table_checks=CF.table_checks(p))
    d = np.load(p)
    x = d["x"]; z = d["z"]; eta = d["eta"]; ue = d["u_ext"]; we = d["w_ext"]
    beta = float(d["beta"]); ks = float(d["k_s"]); dd = float(d["d"]); a = float(d["a_m"]); c0 = float(d["c0_trough"]); h0 = float(d["h0"])
    x0 = float(d["x0"]); c = float(d["c"])
    dT = np.load(str(d["src_tanaka"]))
    etaT = dT["eta"]; uT = dT["u_ext"]
    eta_t = eta - etaT
    i = int(np.argmin(eta))
    out["trough"] = dict(beta=beta, k_s=ks, d_m=dd, a_m=a, trough_amp_m=beta * a, c0=c0, c_crest=c,
                         eta_min_m=float(eta[i]), x_eta_min_m=float(x[i]),
                         eta_t_min_m=float(eta_t.min()), x_trough_centre_m=x0 + dd,
                         eta_at_trough_centre_m=float(np.interp(x0 + dd, x, eta)), crest_tail_at_trough_centre_m=float(np.interp(x0 + dd, x, etaT)),
                         eta_at={str(xq): float(np.interp(xq, x, eta)) for xq in (143.0, 150.0, 170.0, 190.0, 240.0, 296.0, 360.0)},
                         eta_t_at={str(xq): float(np.interp(xq, x, eta_t)) for xq in (0.0, 143.0, 150.0, 190.0, 296.0, 360.0)},
                         volume_trough_m2=float(trapz(eta_t, x)), volume_total_m2=float(trapz(eta, x)), volume_crest_m2=float(trapz(etaT, x)),
                         still_level_drop_if_spread_over_Lx_m=float(trapz(eta_t, x)) / float(x[-1] - x[0]),
                         green_upper_bound_on_shelf_m=beta * a * (h0 / GC.SHELF_H) ** 0.25,
                         shelf_depth_if_green_bound_m=GC.SHELF_H - beta * a * (h0 / GC.SHELF_H) ** 0.25,
                         tags=dict(trough_amp="chosen (beta*a)", eta_min="computed (crest tail + trough overlap)",
                                   green_upper_bound="computed (Green's law, linear upper bound, no breaking/reflection)"))
    # 作り方の流量の一致：Q_new − c0 η_t（u_t (h0+η) = c0 η_t）と、Tanaka の流れを新しい水面 η まで積んだ物
    def qcol(U, e):
        Q = np.zeros(len(x))
        for j in range(len(x)):
            zi = z[z < e[j]]
            q = trapz(U[:len(zi), j], zi) if len(zi) > 1 else 0.0
            q += 0.5 * (U[len(zi) - 1, j] + np.interp(e[j], z, U[:, j])) * (e[j] - zi[-1])
            Q[j] = q
        return Q
    Qn = qcol(ue, eta); QT = qcol(uT, eta)
    big = np.abs(eta_t) > 0.01 * beta * a
    out["flux_construction_rel_err_max"] = float(np.max(np.abs(Qn - c0 * eta_t - QT)[big]) / (c * a)) if big.any() else None
    # 定常な波からの離れ（判定でない。谷の所で Q ≠ c η になるのが当たり前）
    sel = np.abs(eta) > 0.05 * a
    out["flux_vs_c_eta_rel_max"] = float(np.max(np.abs(Qn - c * eta)[sel]) / (c * a))
    out["flux_vs_c_eta_note_ja"] = "Q = c η は形を変えずに c で進む波の決まり。谷は c0 で進むので谷の所では成り立たない（作り方の確かめではない）"
    dx = x[1] - x[0]; dz = z[1] - z[0]
    du = np.gradient(ue, dx, axis=1); dw = np.gradient(we, dz, axis=0)
    Zg = z[:, None] * np.ones((1, len(x)))
    inside = (Zg < eta[None, :] - 0.5) & (Zg > -h0 + 0.5) & big[None, :]
    out["div_rel_rms_trough"] = float(np.sqrt(np.mean((du + dw)[inside] ** 2)) / max(np.sqrt(np.mean(du[inside] ** 2)), 1e-12)) if inside.any() else None
    out["nan_in_ext"] = int((~np.isfinite(ue)).sum() + (~np.isfinite(we)).sum())
    out["u_nan_above_surface_ok"] = bool(np.all(np.isnan(d["u"][Zg > eta[None, :]])) and np.all(np.isfinite(d["u"][Zg <= eta[None, :]])))
    out["w_bed_max_abs"] = float(np.max(np.abs(we[0]))) if abs(z[0] + h0) < 1e-9 else None
    # 頂の高さは谷の裾の分だけ下がる（A 0.3・β 0.12 で 5.10 → 5.01 m【計算】）。作り方の確かめ：下がり ＝ 頂の x の η_t
    iT = int(np.argmax(etaT))
    out["crest_tanaka_m"] = float(etaT.max()); out["crest_combined_m"] = float(eta.max())
    out["crest_change_m"] = float(eta.max() - etaT.max()); out["eta_t_at_tanaka_crest_m"] = float(eta_t[iT])
    out["crest_change_note_ja"] = "谷の裾（頂の x で η_t）が頂を下げる。計画の「5.10 m の頂」は Tanaka の表の値で、足した後の頂はこの値"
    out["ok"] = dict(construction_flux=(out["flux_construction_rel_err_max"] or 0.0) < 1e-3, no_nan_ext=out["nan_in_ext"] == 0,
                     nan_above_surface=out["u_nan_above_surface_ok"], div=(out["div_rel_rms_trough"] or 0.0) < 0.05,
                     covers_0_360=out["table_checks"]["x_range"][0] <= 0.0 and out["table_checks"]["x_range"][1] >= GC.LX,
                     crest_change_is_trough_tail=abs(out["crest_change_m"] - out["eta_t_at_tanaka_crest_m"]) < 0.02)
    out["all_ok"] = bool(all(out["ok"].values()))
    return out


def summary(p, info, ck):
    t = ck["trough"]; tc = ck["table_checks"]
    return "\n".join([
        "%s  %s" % (p, info),
        "all_ok %s %s" % (ck["all_ok"], ck["ok"]),
        "crest %.3f m at x %.2f (Tanaka %.3f m, change %+.3f m; c %.3f m/s); trough beta %.3f amp %.3f m, k_s %.6f /m, centre x %.2f m (d %.2f m), c0 %.3f m/s" % (
            tc["crest_m"], tc["x_crest"], ck["crest_tanaka_m"], ck["crest_change_m"], t["c_crest"], t["beta"], t["trough_amp_m"], t["k_s"],
            t["x_trough_centre_m"], t["d_m"], t["c0"]),
        "eta min %.3f m at x %.2f (crest tail at trough centre %+.3f m, eta there %+.3f m); eta at %s" % (
            t["eta_min_m"], t["x_eta_min_m"], t["crest_tail_at_trough_centre_m"], t["eta_at_trough_centre_m"],
            {k: round(v, 3) for k, v in t["eta_at"].items()}),
        "volume crest %.1f trough %.1f total %.1f m2/m (trough spread over the tank %.3f m); Green bound on shelf %.3f m -> depth %.2f m" % (
            t["volume_crest_m2"], t["volume_trough_m2"], t["volume_total_m2"], t["still_level_drop_if_spread_over_Lx_m"], t["green_upper_bound_on_shelf_m"],
            t["shelf_depth_if_green_bound_m"]),
        "flux construction err %.2e, Q vs c*eta (not expected to hold) %.3f, div rel rms (trough) %s, table div rel rms %.2e, w at bed %s" % (
            ck["flux_construction_rel_err_max"], ck["flux_vs_c_eta_rel_max"], ck["div_rel_rms_trough"], tc["div_rel_rms"], ck["w_bed_max_abs"])])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--A", type=float, default=GC.A0)
    ap.add_argument("--beta", type=float, default=GC.BETA_R3)
    ap.add_argument("--dk", type=float, default=GC.DK_R3)
    ap.add_argument("--ks", type=float, default=None, help="谷の k_s（既定は A 0.3 の GN の κ 0.024472 /m。β・A によらず固定）")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    p, info = make(a.A, a.beta, a.dk, a.ks, force=a.force)
    ck = nwave_checks(p)
    ck.update(npz=p, made=info, date=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(ck, open(p[:-4] + "_check.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print(summary(p, info, ck))
