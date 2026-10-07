# -*- coding: utf-8 -*-
"""FLIP39 E：座席から見た体験の物差し（D1 の定義と同じ。Unity/Build/FLIP39/D1/record_ja.md §4.2）を E の計算に当てる。py -3.10。
使い方: py -3.10 e_seat.py <run_dir> [x_seat ...]

座席：目の高さ 1.83 m（seat_v1 の座位の目の高さ。E の計算は 1 単位 = 1 m のまま、倍率をかけない）、船の長さ 11.33 m（boat_mid）。
座席の z：板（z に一様な波）は z=0、3D は焦点の列 z = −Lz/2（壁＝対称の面の上。鏡に映した海の真ん中）。
座席の x：(1) 設計の座席＝前の面が垂直を過ぎた所 + 8 m（§設計の理由は record_ja.md）、(2) x 500〜640 m を 5 m おきに調べた中で、
目が水に入る前の最大の仰角が最も大きい所。
海の面：板は焦点の列の水面を z 方向に ±300 m へ広げた（z に一様）。3D は z = −Lz/2 の壁で鏡に映し、+Lz/2 の壁でも鏡に映した（壁は対称の面）。
計算の箱の外は平らな海（高さ 0）。
目が水に入った：座席の列の断面の粒子が目の高さ（±0.6 m）・座席の x（±1 m）にある、または一番上の水面が目より上で水の区間が 1 つ（空気のすき間がない）。
唇が頭上：座席の列で、一番上の水面が目より 1 m 以上上にあり、水の区間が 2 つ以上（空気のすき間がある）で、目がまだ乾いている。
"""
import sys, os, json, glob
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_analyze import load_hf
from d1_seat import view_measures, sky_stats, NAZ

EYE = 1.83
BOAT = 11.33


def surface_cloud(eta, x, z, Lz, mirror, eye=None, rfine=90.0, dfine=0.5):
    """一番上の水面の点の雲（x, y, z）。mirror=True で 3D の壁の鏡、False で板（z に一様に広げる）。
    目から rfine m の中は、計算の升目（2 m）を dfine m の升目へ線形に補間して細かくする（近い所で方位の升 0.5° に点の抜けを作らないため）。"""
    from scipy.ndimage import map_coordinates
    if not mirror:
        row = np.nanmean(eta, axis=0)
        zz = np.arange(-300.0, 300.0 + 1e-6, 4.0)
        X, Z = np.meshgrid(x, zz)
        Y = np.broadcast_to(row[None, :], X.shape)
        ok = np.isfinite(Y)
        P = [np.c_[X[ok], Y[ok], Z[ok]]]
        if eye is not None:
            xf_ = np.arange(max(x[0], eye[0] - rfine), min(x[-1], eye[0] + rfine), dfine)
            zf_ = np.arange(eye[2] - rfine, eye[2] + rfine, dfine)
            rf = np.interp(xf_, x, np.where(np.isfinite(row), row, -9.0))
            Xf, Zf = np.meshgrid(xf_, zf_)
            Yf = np.broadcast_to(rf[None, :], Xf.shape)
            m = (np.hypot(Xf - eye[0], Zf - eye[2]) < rfine) & (Yf > -8.0)
            P.append(np.c_[Xf[m], Yf[m], Zf[m]])
        return np.concatenate(P)
    X, Z = np.meshgrid(x, z)
    ok = np.isfinite(eta)
    P = np.c_[X[ok], eta[ok], Z[ok]]
    if eye is not None:
        xf_ = np.arange(max(x[0], eye[0] - rfine), min(x[-1], eye[0] + rfine), dfine)
        zf_ = np.arange(z[0], min(z[-1], eye[2] + rfine), dfine)
        Xf, Zf = np.meshgrid(xf_, zf_)
        ix = (Xf - x[0]) / (x[1] - x[0]); iz = (Zf - z[0]) / (z[1] - z[0])
        E0 = np.where(np.isfinite(eta), eta, -9.0)
        Yf = map_coordinates(E0, [iz, ix], order=1, mode="nearest")
        m = (np.hypot(Xf - eye[0], Zf - eye[2]) < rfine) & (Yf > -8.0)
        P = np.concatenate([P, np.c_[Xf[m], Yf[m], Zf[m]]])
    zw = -0.5 * Lz
    P2 = P.copy(); P2[:, 2] = 2 * zw - P2[:, 2]
    P3 = P.copy(); P3[:, 2] = Lz - P3[:, 2]          # +Lz/2 の壁で鏡
    return np.concatenate([P, P2, P3])


def face_chord(rowline, segline, x, xs):
    """座席の列の前の面：頂（座席より沖 150 m の最も高い水面）、目の高さの足（座席から沖へ見て、一番上の水面が目の高さを越える最初の x）、
    弦の角度（足 → 頂）、唇の先（頂より前で水の区間が 2 つ以上の列の最も岸の側の x）、lip lead = 唇の先 − 足。"""
    sea = (x < xs) & (x > xs - 150)
    if not np.any(np.isfinite(np.where(sea, rowline, np.nan))):
        return {}
    k = int(np.nanargmax(np.where(sea, rowline, -np.inf)))
    Hc, xc = float(rowline[k]), float(x[k])
    toe = None
    for j in range(int(np.argmin(np.abs(x - xs))), k, -1):
        if np.isfinite(rowline[j]) and rowline[j] >= EYE:
            toe = float(x[j]); break
    chord = float(np.degrees(np.arctan2(Hc - EYE, toe - xc))) if (toe is not None and toe > xc) else (90.0 if toe is not None else None)
    ov = (segline >= 2) & (x >= xc - 5) & (x <= xs + 2)
    tip = float(x[ov].max()) if ov.any() else None
    return dict(Hc=Hc, xc=xc, toe=toe, chord=chord, lip_tip=tip, lip_lead=(tip - toe) if (tip is not None and toe is not None) else None)


def snaps(rd, zc_pref):
    sd = sorted(glob.glob(os.path.join(rd, "sec", "z*")))
    if not sd:
        return {}
    sdir = sd[0] if len(sd) == 1 else min(sd, key=lambda s: abs(int(os.path.basename(s)[1:]) - zc_pref))
    out = {}
    for f in sorted(glob.glob(os.path.join(sdir, "snap_*.npz"))):
        fr = int(os.path.basename(f)[5:9])
        out[fr] = f
    return out


def eye_wet(snapfile, xs, ytop, seg):
    if ytop is not None and np.isfinite(ytop) and ytop > EYE and seg <= 1:
        return True
    if snapfile is None:
        return False
    d = np.load(snapfile)
    m = (np.abs(d["x"] - xs) < 1.0) & (np.abs(d["y"] - EYE) < 0.6)
    return bool(m.any())


def measure(rd, x_seats=None, step=1):
    hf = load_hf(rd)
    rj = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    an = json.load(open(os.path.join(rd, "analysis_e.json"), encoding="utf8"))
    P = rj["parms"]; Lz = float(P["Lz"]); toff = float(P.get("t_off", 0.0))
    g = hf["grid"]; dx = g["dx"]
    x = g["x0"] + dx * np.arange(hf["eta"].shape[2])
    z = g["z0"] + g["dz"] * np.arange(hf["eta"].shape[1])
    mirror = Lz > 20
    zs = -0.5 * Lz + 0.5 if mirror else 0.0
    rowz = an.get("row_z")
    if mirror and rowz is not None:
        zs = float(rowz)   # 頂の列（E3）
    off = float(an.get("level_offset_m", 0.43))
    sn = snaps(rd, (zs if rowz is not None else -119) if mirror else 0)
    iz_row = 0 if mirror else None
    br = an.get("breaking") or {}
    ev = br.get("events", {}) if br else {}
    x_ov = ev.get("face_past_vertical", {}).get("x") if ev.get("face_past_vertical") else None
    t_ov = ev.get("face_past_vertical", {}).get("t") if ev.get("face_past_vertical") else None
    if x_seats is None:
        xs0_ = float(P.get("xs0", 420.0)) if float(P.get("xs0", 420.0)) < float(P["Lx"]) else float(P["Lx"]) - 386.0
        x_seats = list(np.arange(xs0_ + 80.0, xs0_ + 221.0, 5.0))   # 岩棚の並びで x 500〜640 m（斜面の始まり 420 m から +80〜+220 m）
        if x_ov:
            x_seats = sorted(set(x_seats + [round(x_ov + 8.0, 1)]))
    # 時刻の範囲：焦点の 25 秒前から最後まで
    tf_sim = float(an["group"]["tf"]) - toff
    fsel = [i for i in range(len(hf["t"])) if hf["t"][i] >= tf_sim - 25.0][::step]
    from scipy.ndimage import maximum_filter1d
    res = []
    for xs in x_seats:
        ixs = int(np.argmin(np.abs(x - xs)))
        hull = (x >= xs - 5.7) & (x <= xs + 5.7)
        summ = {}
        for mode in ("ride", "fixed"):
            rows = []
            end_t, end_why = None, None
            for i in fsel:
                fr = int(hf["frames"][i]); t = float(hf["t"][i])
                E = hf["eta"][i] - off
                izr = int(round((zs - g["z0"]) / g["dz"])) if (mirror and rowz is not None) else 0
                rowline = np.nanmean(E, axis=0) if not mirror else np.nanmax(E[max(izr - 1, 0):izr + 2], axis=0)
                segline = hf["seg"][i].max(axis=0) if not mirror else hf["seg"][i][max(izr - 1, 0):izr + 2].max(axis=0)
                ytop = rowline[ixs]; sg = int(segline[ixs])
                # 船の位置の水面：船の長さ（11.33 m）の下の一番上の水面の中央値（張り出しの列は除く）
                under = rowline[hull & (segline <= 1)]
                ysurf = float(np.nanmedian(under)) if np.isfinite(under).any() else 0.0
                ye = EYE if mode == "fixed" else ysurf + EYE
                eye = np.array([xs, ye, zs])
                sf = sn.get(fr)
                sea = (x < xs) & (x > xs - 150)
                k = int(np.nanargmax(np.where(sea, rowline, -np.inf)))
                Hc, xc = float(rowline[k]), float(x[k])
                if mode == "fixed":
                    if eye_wet(sf, xs, ytop, sg):
                        end_t, end_why = t, "目が水に入った"; break
                else:
                    if sf is not None:
                        q = np.load(sf)
                        if np.any((np.abs(q["x"] - xs) < 1.0) & (np.abs(q["y"] - off - ye) < 0.6)):
                            end_t, end_why = t, "水が船の上の目の高さに来た（唇・噴流・切り立った面）"; break
                    if ysurf >= 0.85 * Hc and Hc > 3.0:
                        end_t, end_why = t, "船が頂の上に持ち上げられた"; break
                Pc = surface_cloud(E, x, z, Lz, mirror, eye=eye)
                sky, vm = view_measures(Pc, eye)
                # 方位の升（0.5°）の点の抜けを埋める：5 升（2.5°）の最大でならす（D1 の P3 は 0.5 m の升目で抜けがなかった。E は 2 m の升目を補間した）
                sky = maximum_filter1d(sky, 5, mode="wrap")
                st = sky_stats(sky)
                overhead = bool(np.isfinite(ytop) and ytop > ye + 1.0 and sg >= 2)
                fc_ = face_chord(rowline - (ye - EYE), segline, x, xs)
                rows.append(dict(chord=fc_.get("chord"), lip_lead=fc_.get("lip_lead"), t=t, t_group=t + toff, alpha=vm["alpha_max"], dist_h=vm["dist_h"],
                                 hmd=st["hmd_fill"], hemi=st["upper_hemi_frac"], w10=st["width_above_deg"][10], w30=st["width_above_deg"][30],
                                 w80=st["w80_deg"], Hc=Hc - (ye - EYE), xc=xc, overhead=overhead, eye_y=ye))
            if not rows:
                summ[mode] = None; continue
            al = np.array([r["alpha"] for r in rows]); tt = np.array([r["t"] for r in rows])
            k = int(np.argmax(al))
            # 立ち上がる速さ：座席の列の頂（目からの高さ Hc−目、距離 D）から、仰角の速さを「頂が高くなる分」と「近づく分」に分ける（0.5 秒でならす）
            Hc_ = np.array([r["Hc"] for r in rows]); D = xs - np.array([r["xc"] for r in rows])
            def smooth(v, n=12):
                if len(v) < n:
                    return v
                ker = np.ones(n) / n
                return np.convolve(np.pad(v, (n // 2, n - 1 - n // 2), mode="edge"), ker, mode="valid")
            Hs, Ds = smooth(Hc_), smooth(D)
            dH = np.gradient(Hs, tt); dD = np.gradient(Ds, tt)
            den = Ds ** 2 + (Hs - EYE) ** 2
            grow = np.degrees(Ds * dH / den); appr = np.degrees(-(Hs - EYE) * dD / den)
            view = al >= 10.0
            gs = float(np.sum(np.clip(grow[view], 0, None)) / max(np.sum(np.clip(grow[view], 0, None)) + np.sum(np.clip(appr[view], 0, None)), 1e-9)) if view.any() else None
            t10 = float(tt[np.argmax(view)]) if view.any() else None
            summ[mode] = dict(end_t_group=(end_t + toff) if end_t is not None else None, end_why=end_why,
                              alpha_max=float(al[k]), t_alpha_max=float(tt[k]) + toff, dist_at=float(rows[k]["dist_h"]), eye_y_at=float(rows[k]["eye_y"]),
                              hmd_fill_max=float(max(r["hmd"] for r in rows)), hemi_max=float(max(r["hemi"] for r in rows)),
                              w10_at=float(rows[k]["w10"]), w30_at=float(rows[k]["w30"]), w80_at=float(rows[k]["w80"]),
                              lip_overhead=bool(any(r["overhead"] for r in rows)),
                              t_alpha10=(t10 + toff) if t10 is not None else None, view_s=(float(tt[k]) - t10) if t10 is not None else None,
                              growth_share=gs, crest_above_eye_m=float(rows[k]["Hc"] - EYE),
                              chord_at=rows[k]["chord"], lip_lead_max=max([r["lip_lead"] for r in rows if r["lip_lead"] is not None], default=None),
                              series=dict(t_group=[r["t_group"] for r in rows][::2], alpha=[round(r["alpha"], 2) for r in rows][::2],
                                          hmd=[round(r["hmd"], 3) for r in rows][::2], Hc=[round(r["Hc"], 2) for r in rows][::2],
                                          eye_y=[round(r["eye_y"], 2) for r in rows][::2],
                                          grow=[round(float(v), 2) for v in grow][::2], appr=[round(float(v), 2) for v in appr][::2]))
        r = summ.get("ride") or {}
        fx = summ.get("fixed") or {}
        res.append(dict(x_seat=float(xs), z_seat=zs, ride=r, fixed=fx,
                        # 主の物差し（板・3D とも乗る目。理由は record_ja.md：群の前の波が 1.83 m を越えるので固定の目は焦点の前に水に入る）
                        alpha_max_before_wet=r.get("alpha_max", -1), lip_overhead_while_dry=r.get("lip_overhead"), hmd_fill_max=r.get("hmd_fill_max"),
                        growth_share=r.get("growth_share"), view_s=r.get("view_s"), w80_at=r.get("w80_at"), t_alpha_max=r.get("t_alpha_max"),
                        t_eye_wet=(r["end_t_group"] - toff) if r.get("end_t_group") is not None else None))
        print("seat x %.1f | ride: alpha %.1f at %.2f, end %s (%s), overhead %s, hmd %.2f, growth %s | fixed: alpha %.1f, end %s" % (
            xs, r.get("alpha_max", -1), r.get("t_alpha_max", -1), r.get("end_t_group"), r.get("end_why"), r.get("lip_overhead"), r.get("hmd_fill_max", -1),
            r.get("growth_share"), fx.get("alpha_max", -1), fx.get("end_t_group")), flush=True)
    best = max(res, key=lambda r: (bool(r["lip_overhead_while_dry"]), r["alpha_max_before_wet"])) if res else None
    design = None
    if x_ov:
        cand = [r for r in res if abs(r["x_seat"] - (x_ov + 8.0)) < 0.2]
        design = cand[0] if cand else None
    out = dict(run_id=os.path.basename(rd.rstrip("/\\")), eye_height_m=EYE, boat_length_m=BOAT, mirror=mirror, z_seat=zs,
               x_overturn=x_ov, t_overturn_sim=t_ov, design_seat=design, best_seat=best, scan=[{k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "series"}) for k, v in r.items()} for r in res],
               series_best=(best["ride"] or {}).get("series") if best else None, series_design=(design["ride"] or {}).get("series") if design else None)
    # 峰に沿う長さ（頂の 0.8 倍以上）：前の面が垂直を過ぎた時刻（なければ最も高い時刻）の、z ごとの最も高い水面
    i_ov = int(np.argmin(np.abs(hf["t"] - (t_ov if t_ov is not None else float(an["crest_max_any"]["t_group"]) - toff))))
    E = hf["eta"][i_ov] - off
    cl = np.nanmax(np.where((x[None, :] > 400) & (x[None, :] < 706), E, -np.inf), axis=1)
    if mirror:
        Hc = float(np.nanmax(cl)); dz = g["dz"]
        L80 = float(np.sum(cl >= 0.8 * Hc) * dz) * 2.0 - dz      # 壁で鏡に映した全長（壁の上の 1 本は重ねない）
        L50 = float(np.sum(cl >= 0.5 * Hc) * dz) * 2.0 - dz
        out["crest_line"] = dict(t=float(hf["t"][i_ov]) + toff, Hc=Hc, L80_m=L80, L50_m=L50, z=z.tolist(), crest_z=[round(float(v), 2) for v in cl])
    else:
        out["crest_line"] = dict(t=float(hf["t"][i_ov]) + toff, Hc=float(np.nanmax(cl)), L80_m=None, L50_m=None, note="板：z に一様（端のない峰）")
    json.dump(out, open(os.path.join(rd, "seat_e.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    xs = [float(v) for v in sys.argv[2:] if not v.startswith("--")] or None
    st = 2 if "--step2" in sys.argv else 1
    o = measure(sys.argv[1], xs, step=st)
    o["frame_step"] = st
    print(json.dumps({k: o[k] for k in ("x_overturn", "crest_line")}, default=float)[:600])
    for nm in ("best_seat", "design_seat"):
        b = o[nm] or {}
        print(nm, b.get("x_seat"), "ride", json.dumps({k: v for k, v in (b.get("ride") or {}).items() if k != "series"}, default=float, ensure_ascii=False))
