# -*- coding: utf-8 -*-
"""FLIP39 D1-1：FLIP37 の既存の計算（P1 の最良の断面、P2 の各計算、P3）で、波を高くする仕組みがどれだけ働いたかを測る。
新しい流体計算はしない。読むのは hf.npz（一番上の水面 η(z,x)、毎コマ）と analysis.json・run.json・eta.npz だけ。
出力：Unity/Build/FLIP39/D1/mech_raw.json（図と表は d1_mech_figs.py）。"""
import sys, os, json, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_common import *
from d1_linear_flat import linear_flat
from d1_rays import trace, density_Kr

os.makedirs(OUT, exist_ok=True)
RUNS = [("R05_L120_H29", "R05 レンズ・一列・H29"), ("R08_L120_H33", "R08 レンズ・一列・H33"),
        ("R10_L120X30_H33", "R10 レンズ・±30°・H33"), ("R12_L120X30_H37", "R12 レンズ・±30°・H37"), ("R15_X30O20_H37", "R15 斜め20°（レンズなし）・±30°・H37"),
        ("R16_X30L120LG_H37", "R16 レンズ＋低い棚・±30°・H37"), ("R17_X40L120_H42", "R17 レンズ・±40°・H42"), ("R18_X30L120LG_H39", "R18 レンズ＋低い棚・±30°・H39")]
DEF = dict(lens_A=0.0, lens_zl=60.0, lens_dh=0.0, lens_z0=0.0, obl_deg=0.0, lg1_d=0.0, lg2_d=0.0, cross_deg=0.0, cross_z0=0.0, Lz=240.0)
XMIN, XMAX = 250.0, 704.0


def wavelen(T, h):
    return float(2 * np.pi / kdisp(2 * np.pi / T, h))


def crest_track(eta, x, t, iz, xmin=XMIN, xmax=XMAX):
    """各コマの、z の列 iz の x 方向の最も高い水面（頂）と、その前 150 m の最も低い水面（前の谷）。"""
    m = (x >= xmin) & (x <= xmax)
    out = []
    for f in range(len(t)):
        row = eta[f, iz][m]
        if not np.isfinite(row).any():
            out.append((np.nan, np.nan, np.nan)); continue
        k = int(np.nanargmax(row))
        ah = row[k + 1:k + 1 + int(150 / (x[1] - x[0]))]
        out.append((row[k], x[m][k], np.nanmin(ah) if np.isfinite(ah).any() else np.nan))
    return np.array(out, float)


def crest_line(eta_f, x, xmin=XMIN, xmax=XMAX):
    m = (x >= xmin) & (x <= xmax)
    return np.nanmax(eta_f[:, m], axis=1)


def half_width(z, c):
    mid = 0.5 * (np.nanmax(c) + np.nanmin(c))
    return float(np.sum(c > mid) * (z[1] - z[0]))


def len_above(z, c, frac):
    return float(np.sum(c >= frac * np.nanmax(c)) * (z[1] - z[0]))


def conc_index(eta_f, x, z, xc, zin=30.0):
    """z=0 の頂の x（xc）の前後（xc−100〜xc+60 m）の η² を z ごとに足し、|z|<zin の分の割合。
    z に一様な波なら 2·zin/Lz（幅 240 m で 0.25）。向きの違う波が真ん中へ集まり続けるなら、時間とともに増える。"""
    m = (x >= xc - 100) & (x <= xc + 60)
    E = np.nansum(np.where(np.isfinite(eta_f[:, m]), eta_f[:, m], 0) ** 2, axis=1)
    return float(E[np.abs(z) < zin].sum() / max(E.sum(), 1e-9))


def lin_track(p, tl):
    xl, zl, El = linear_flat(p, tl)
    izl = int(np.argmin(abs(zl)))
    sel = (xl > XMIN) & (xl < 1600)
    return np.array([[tt, El[i, izl][sel].max(), xl[sel][np.argmax(El[i, izl][sel])]] for i, tt in enumerate(tl)])


def analyse_p2(rid, label):
    rj, hf = load_run(rid)
    p = dict(DEF); p.update(rj["parms"])
    an = json.load(open(os.path.join(FLIP37, "P2", rid, "analysis.json"), encoding="utf-8"))
    tk = Tank(p)
    x, z, t, e = hf["x"], hf["z"], hf["t"], hf["eta"]
    iz = int(np.argmin(abs(z)))
    tr = crest_track(e, x, t, iz)
    T = p["T"]; L0 = wavelen(T, p["h0"]); k0h = 2 * np.pi / L0 * p["h0"]
    t_on = an.get("t_first_onset_any_section")
    sec0 = an.get("sections", {}).get("z+000", {}).get("events", {})
    t_on0 = (sec0.get("breaking_onset_B085") or {}).get("t")
    t_ov = an.get("t_first_overturn_any_section")
    f_on = int(np.argmin(abs(t - t_on))) if t_on else None
    tend = t_on if t_on else t[-1]
    pre = t <= tend + 1e-6
    c0, x0c, _ = tr[0]
    H0 = c0 - np.nanmin(e[0, iz][(x > x0c) & (x < x0c + 200)])
    k_dip = int(np.nanargmin(np.where(pre & (t > 0.5), tr[:, 0], np.nan)))

    def at_x(xx):
        k = np.where((tr[:, 1] >= xx) & (t > 0.2))[0]
        return (float(t[k[0]]), float(tr[k[0], 0])) if len(k) else (None, None)
    t400, c400 = at_x(400.0); t500, c500 = at_x(500.0)
    lin = lin_track(p, t[(t <= 7.6)][::6])
    om = 2 * np.pi / T
    h_on = float(tk.depth(tr[f_on, 1], 0.0)) if f_on is not None else None
    Ks_on = float(kshoal(om, h_on) / kshoal(om, p["h0"])) if h_on else None
    prof = {}
    for nm, tt in [("t0", 0.0), ("toe", t400), ("onset", t_on)]:
        if tt is None:
            continue
        f = int(np.argmin(abs(t - tt)))
        cl = crest_line(e[f], x)
        prof[nm] = dict(t=float(t[f]), crest_z0=float(cl[iz]), crest_mean=float(np.nanmean(cl)), crest_min=float(np.nanmin(cl)),
                        center_over_mean=float(cl[iz] / np.nanmean(cl)),
                        center_over_edge100=float(cl[iz] / np.nanmean(cl[np.abs(np.abs(z) - 100) < 1.5])),
                        half_width_m=half_width(z, cl), len_above_08=len_above(z, cl, 0.8), conc30=conc_index(e[f], x, z, tr[f, 1]), line=cl)
    ci = []
    for f in range(0, len(t), 3):
        if t[f] > tend + 0.01:
            break
        cl = crest_line(e[f], x)
        ci.append([float(t[f]), float(cl[iz] / np.nanmean(cl)), conc_index(e[f], x, z, tr[f, 1])])
    m = (x >= 120) & (x <= 480)
    HE = float(4 * np.sqrt(np.nanmean(e[0][:, m] ** 2)))
    col = e[0][:, int(np.argmin(abs(x - p["xc0"])))]
    n0share = float(np.nanmean(col) / col[iz])
    return dict(run_id=rid, label=label,
                parms={k: p[k] for k in ("T", "H", "cross_deg", "lens_A", "lens_dh", "lens_zl", "obl_deg", "lg1_d", "lg2_d", "h0", "hr", "slope_n", "xs0", "xc0", "xhot", "xback")},
                L0_m=L0, k0h=k0h,
                input=dict(crest_z0_m=c0, x=x0c, H_z0_m=H0, steep_H_over_L=H0 / L0, miche_limit=0.142 * np.tanh(k0h),
                           ratio_to_miche=H0 / L0 / (0.142 * np.tanh(k0h)), HE_m=HE, n0_share_at_z0=n0share),
                dip=dict(t=float(t[k_dip]), crest_m=float(tr[k_dip, 0]), x=float(tr[k_dip, 1])),
                toe=dict(t=t400, crest_m=c400, an_toe=an.get("toe_gauge_x400", {}).get("z+0")),
                at_x500=dict(t=t500, crest_m=c500, depth_m=float(tk.depth(500.0, 0.0))),
                onset=dict(t_any=t_on, t_z0=t_on0, crest_z0_m=float(tr[f_on, 0]) if f_on is not None else None,
                           x=float(tr[f_on, 1]) if f_on is not None else None, depth_m=h_on, Ks_lin=Ks_on,
                           at_onset=an.get("at_onset"), crest_max_pre=float(np.nanmax(np.where(pre, tr[:, 0], np.nan)))),
                t_overturn_any=t_ov, track=np.c_[t, tr], linear=lin, prof=prof, conc=np.array(ci), z=z)


def analyse_p1(rid, label):
    base = os.path.join(FLIP37, "P1", rid)
    rj = json.load(open(os.path.join(base, "run.json"), encoding="utf-8")); an = json.load(open(os.path.join(base, "analysis.json"), encoding="utf-8"))
    d = np.load(os.path.join(base, "eta.npz"))
    p = dict(DEF); p.update(rj["parms"]); tk = Tank(p)
    x, t, e = d["x"], d["t"], d["eta"]
    tr = crest_track(e[:, None, :], x, t, 0)
    L0 = wavelen(p["T"], p["h0"]); k0h = 2 * np.pi / L0 * p["h0"]
    ev = an["events"]; t_on = ev["breaking_onset_B085"]["t"]
    f_on = int(np.argmin(abs(t - t_on)))
    c0, x0c, _ = tr[0]
    H0 = c0 - np.nanmin(e[0][(x > x0c) & (x < x0c + 200)])
    pre = t <= t_on + 1e-6
    k_dip = int(np.nanargmin(np.where(pre & (t > 0.5), tr[:, 0], np.nan)))
    om = 2 * np.pi / p["T"]; h_on = float(tk.depth(tr[f_on, 1], 0.0))
    lin = lin_track(p, t[(t <= 9.6)][::6])
    return dict(run_id=rid, label=label, L0_m=L0, k0h=k0h,
                input=dict(crest_z0_m=c0, x=x0c, H_z0_m=H0, steep_H_over_L=H0 / L0, miche_limit=0.142 * np.tanh(k0h),
                           ratio_to_miche=H0 / L0 / (0.142 * np.tanh(k0h))),
                dip=dict(t=float(t[k_dip]), crest_m=float(tr[k_dip, 0]), x=float(tr[k_dip, 1])),
                toe=an.get("toe_gauge"),
                onset=dict(t_z0=t_on, crest_z0_m=float(tr[f_on, 0]), x=float(tr[f_on, 1]), depth_m=h_on,
                           Ks_lin=float(kshoal(om, h_on) / kshoal(om, p["h0"])), crest_max_pre=float(np.nanmax(np.where(pre, tr[:, 0], np.nan)))),
                t_overturn=ev["face_past_vertical"]["t"], track=np.c_[t, tr], linear=lin)


def analyse_p3():
    hf = load_p3()
    x, z, t, e = hf["x"], hf["z"], hf["t"], hf["eta"]
    iz = int(np.argmin(abs(z)))
    tr = crest_track(e, x, t, iz, xmin=300.5, xmax=636.0)
    a = json.load(open(os.path.join(FLIP37, "P3", "H25_R18_mg", "sec", "z+000", "analysis.json"), encoding="utf-8"))
    ev = a.get("events")
    t_on = ev["breaking_onset_B085"]["t"]; t_ov = ev["face_past_vertical"]["t"]
    f_on = int(np.argmin(abs(t - t_on))); f_ov = int(np.argmin(abs(t - t_ov)))
    prof = {}
    for nm, ff in [("start", 0), ("onset", f_on), ("overturn", f_ov)]:
        cl = crest_line(e[ff], x, 300.5, 636.0)
        prof[nm] = dict(t=float(t[ff]), crest_z0=float(cl[iz]), crest_max=float(np.nanmax(cl)), z_at_max=float(z[np.nanargmax(cl)]),
                        len_above_08=len_above(z, cl, 0.8), len_above_09=len_above(z, cl, 0.9), line=cl)
    return dict(run_id="H25_R18_mg", label="P3 主役の範囲（0.25 m）", events_z0=ev, track=np.c_[t, tr],
                onset=dict(t_z0=t_on, crest_z0_m=float(tr[f_on, 0]), x=float(tr[f_on, 1])),
                overturn=dict(t_z0=t_ov, crest_z0_m=float(tr[f_ov, 0]), x=float(tr[f_ov, 1])),
                crest_max_pre_overturn=float(np.nanmax(tr[:f_ov + 1, 0])), prof=prof, z=z)


def rays_summary(parms):
    p = dict(DEF); p.update(parms)
    res = {}
    for nm, mod in [("R18", {}), ("lens_only", {"lg1_d": 0, "lg2_d": 0}), ("straight", {"lg1_d": 0, "lg2_d": 0, "lens_A": 0, "lens_dh": 0})]:
        q = dict(p); q.update(mod); tk = Tank(q)
        res[nm] = {}
        for th in (0.0, 30.0):
            rr, dz0 = trace(tk, q["T"], th)
            zc, Kr = density_Kr(rr, dz0, q["Lz"])
            base = np.median(Kr[310.0])
            i0 = int(np.argmin(abs(zc)))
            res[nm]["%d" % th] = dict(x=list(Kr.keys()), Kr_z0=[float(Kr[s][i0] / base) for s in Kr], zc=zc,
                                     Kr_z_at={str(int(s)): (Kr[s] / base) for s in (480.0, 500.0, 520.0, 540.0)})
    return res


if __name__ == "__main__":
    R = {}
    for rid, lab in RUNS:
        print("P2", rid); sys.stdout.flush()
        R[rid] = analyse_p2(rid, lab)
    P1 = {}
    for rid, lab in [("B025H32_T14_H32_n4_hr26", "P1 最良 B025H32（断面 0.25 m）"), ("S02_T14_H28_n4_hr26_d05", "P1 S02（断面 0.5 m）")]:
        print("P1", rid); sys.stdout.flush()
        P1[rid] = analyse_p1(rid, lab)
    print("P3"); sys.stdout.flush()
    P3 = analyse_p3()
    print("rays"); sys.stdout.flush()
    RAYS = rays_summary(load_run("R18_X30L120LG_H39")[0]["parms"])
    jdump(dict(P2=R, P1=P1, P3=P3, rays=RAYS), os.path.join(OUT, "mech_raw.json"))
    print("done")
