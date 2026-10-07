# -*- coding: utf-8 -*-
"""FLIP39 R：座席から見た体験の物差し（D1 §4.2 の定義、E の e_seat.py と同じ式）を、主役の範囲の細かい計算に当てる（py -3.10）。
使い方: py -3.10 r_seat.py <箱の run_dir> <z_seat> [x_seat ...] [--step2]

海の面（目から見える水面の点の雲）：
- 2 m の升（E3 と同じ節）。箱の中（境界の帯の内側）は細かい計算の一番上の水面をその節の ±1 m の升の最大で写し、箱の外は E3 の水面。
  z = −120 m と +120 m の壁で鏡に映す（E3 と同じ。壁は対称の面）。
- 目から 90 m の中で箱の中は、細かい計算の升（粒子の間隔 × 2）の水面をそのまま足す（E では 2 m を 0.5 m へ補間していた所）。
座席の列（頂・前の面の弦・唇の先・船の下の水面）は、細かい計算の列（座席の z の ±0.9 m の最大）で測る。
目：e_seat と同じ。乗る目＝船の長さ（11.33 m）の下の一番上の水面の中央値 + 1.83 m（上下だけ。傾き・押し流し・転覆は入れない）。
乗る目の終わり：断面の粒子が座席の x（±1 m）・目の高さ（±0.6 m）に来た、または船が頂の 0.85 倍まで持ち上げられた。
水面のずれ：細かい計算の水面は粗い計算の水面（ずれ +0.46 m を含む）から始めたので、ずれ = 0.46 m + 始めの 0.25〜0.75 秒の「箱 − E3」の平均の差（推定）。
"""
import sys, os, json, glob
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_analyze import load_hf
from e_seat import surface_cloud, face_chord, EYE, BOAT
from d1_seat import view_measures, sky_stats
from r_compare import load_box
from scipy.ndimage import maximum_filter1d

E3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/E3_dir20_lens"
TOFF = 35.0
OFF_E3 = 0.46


class Merged:
    def __init__(self, rd):
        self.B = load_box(rd)
        self.C = load_hf(E3)
        gb = self.B["grid"]; gc = self.C["grid"]
        self.xb = gb["x0"] + gb["dx"] * np.arange(self.B["eta"].shape[2]); self.zb = gb["z0"] + gb["dz"] * np.arange(self.B["eta"].shape[1])
        self.xc = gc["x0"] + gc["dx"] * np.arange(self.C["eta"].shape[2]); self.zc = gc["z0"] + gc["dz"] * np.arange(self.C["eta"].shape[1])
        wx0, wx1, wz0, wz1 = gb["window"]; pad = gb["pad"]
        rjs = sorted(glob.glob(os.path.join(rd, "run_*.json")))
        padz0 = float(json.load(open(rjs[0], encoding="utf8"))["parms"].get("padz0", pad)) if rjs else 0.0   # 区切りの記録がまだない時は場面の既定（0）
        self.win = (wx0 + pad, wx1 - pad, wz0 + padz0, wz1 - pad)
        self.inb_x = (self.xb >= self.win[0]) & (self.xb <= self.win[1]); self.inb_z = (self.zb >= self.win[2]) & (self.zb <= self.win[3])
        # 細かい升 → 最も近い 2 m の節
        self.mx = np.round((self.xb - gc["x0"]) / gc["dx"]).astype(int); self.mz = np.round((self.zb - gc["z0"]) / gc["dz"]).astype(int)
        self.cidx = {int(f): k for k, f in enumerate(self.C["frames"])}
        # 2 m の節で、箱の中と見なす所（その節の ±1 m がすべて箱の内側）
        self.cin_x = (self.xc - 1 >= self.win[0]) & (self.xc + 1 <= self.win[1]); self.cin_z = (self.zc - 1 >= self.win[2] - 1e-6) & (self.zc + 1 <= self.win[3])
        # 水面のずれ（推定）：始めの 0.25〜0.75 秒（6〜17 コマ目）の箱の内側の平均 − E3 の平均（最初の 6 コマは箱の水面ができる途中で、
        # 差が 0.06 → 0.46 m へ跳ぶ：V1 の記録）
        dd = []
        nB = len(self.B["frames"])
        for k in range(min(6, nB - 1), min(18, nB)):
            f = int(self.B["frames"][k])
            eb = self.B["eta"][k][np.ix_(self.inb_z, self.inb_x)]
            ec = self.C["eta"][self.cidx[f]][np.ix_(self.cin_z, self.cin_x)]
            dd.append(float(np.nanmean(eb) - np.nanmean(ec)))
        self.off_box = OFF_E3 + float(np.mean(dd))
        self.Lz = 240.0

    def frame(self, k):
        """k 番目の箱のコマ：2 m の合わせた水面（ずれを引いた）と区間の数、細かい水面（ずれを引いた）。"""
        f = int(self.B["frames"][k])
        E = self.C["eta"][self.cidx[f]].astype(np.float64) - OFF_E3
        S = self.C["seg"][self.cidx[f]].copy()
        Eb = self.B["eta"][k].astype(np.float64) - self.off_box
        Sb = self.B["seg"][k]
        sub = np.full_like(E, -np.inf); ssub = np.zeros_like(S)
        ZZ, XX = np.meshgrid(self.mz, self.mx, indexing="ij")
        ok = np.isfinite(Eb) & self.inb_z[:, None] & self.inb_x[None, :] & (ZZ >= 0) & (ZZ < E.shape[0]) & (XX >= 0) & (XX < E.shape[1])
        np.maximum.at(sub, (ZZ[ok], XX[ok]), Eb[ok])
        np.maximum.at(ssub, (ZZ[ok], XX[ok]), Sb[ok])
        cin = self.cin_z[:, None] & self.cin_x[None, :] & np.isfinite(sub)
        E[cin] = sub[cin]; S[cin] = ssub[cin]
        return f, E, S, Eb, Sb


def measure(rd, zs, x_seats, step=1):
    M = Merged(rd)
    B = M.B
    xb, zb = M.xb, M.zb
    rowsel = np.abs(zb - zs) <= max(0.9, 0.51 * (zb[1] - zb[0]))
    sdirs = sorted(glob.glob(os.path.join(rd, "sec", "z*")))
    sdir = min(sdirs, key=lambda s: abs(int(os.path.basename(s)[1:]) - zs)) if sdirs else None
    sn = {int(os.path.basename(f)[5:9]): f for f in glob.glob(os.path.join(sdir, "snap_*.npz"))} if sdir else {}
    zsec = int(os.path.basename(sdir)[1:]) if sdir else None
    ks = list(range(0, len(B["frames"]), step))
    res = []
    cache = {}
    Xb, Zb = np.meshgrid(xb, zb)
    inb = M.inb_z[:, None] & M.inb_x[None, :]

    def get(k):
        # コマごとの 2 m の合わせた水面の点の雲（壁で鏡に映したもの）は座席によらないので一度だけ作る
        if k not in cache:
            f, E, S, Eb, Sb = M.frame(k)
            Pc = surface_cloud(E, M.xc, M.zc, M.Lz, True, eye=None).astype(np.float32)
            cache[k] = (f, Pc, Eb.astype(np.float32), Sb)
        return cache[k]
    for xs in x_seats:
        ixs = int(np.argmin(np.abs(xb - xs)))
        hull = (xb >= xs - 0.5 * BOAT) & (xb <= xs + 0.5 * BOAT)
        summ = {}
        for mode in ("ride", "fixed"):
            rows = []
            end_t, end_why = None, None
            for k in ks:
                f, Pbase, Eb, Sb = get(k)
                t = float(B["t"][k])
                rowline = np.nanmax(Eb[rowsel], axis=0); segline = Sb[rowsel].max(axis=0)
                ytop = rowline[ixs]; sg = int(segline[ixs])
                under = rowline[hull & (segline <= 1)]
                ysurf = float(np.nanmedian(under)) if np.isfinite(under).any() else 0.0
                ye = EYE if mode == "fixed" else ysurf + EYE
                eye = np.array([xs, ye, zs])
                sea = (xb < xs) & (xb > xs - 150)
                kk = int(np.nanargmax(np.where(sea, rowline, -np.inf)))
                Hc, xc_ = float(rowline[kk]), float(xb[kk])
                sf = sn.get(f) if (zsec is not None and abs(zsec - zs) <= 1.0) else None
                if mode == "fixed":
                    wet = bool(np.isfinite(ytop) and ytop > EYE and sg <= 1)
                    if not wet and sf is not None:
                        q = np.load(sf)
                        wet = bool(np.any((np.abs(q["x"] - xs) < 1.0) & (np.abs(q["y"] - M.off_box - EYE) < 0.6)))
                    if wet:
                        end_t, end_why = t, "目が水に入った"; break
                else:
                    if sf is not None:
                        q = np.load(sf)
                        if np.any((np.abs(q["x"] - xs) < 1.0) & (np.abs(q["y"] - M.off_box - ye) < 0.6)):
                            end_t, end_why = t, "水が船の上の目の高さに来た（唇・噴流・切り立った面）"; break
                    if ysurf >= 0.85 * Hc and Hc > 3.0:
                        end_t, end_why = t, "船が頂の上に持ち上げられた"; break
                # 目から 90 m の中の箱の水面（細かい升）を足す（壁 z=−120 で鏡に映した分も）
                near = (np.hypot(Xb - xs, Zb - zs) < 90.0) & np.isfinite(Eb) & inb
                Pn = np.c_[Xb[near], Eb[near], Zb[near]]
                Pm = Pn.copy(); Pm[:, 2] = -240.0 - Pm[:, 2]
                Pc = np.concatenate([Pbase, Pn.astype(np.float32), Pm.astype(np.float32)]).astype(np.float64)
                sky, vm = view_measures(Pc, eye)
                sky = maximum_filter1d(sky, 3, mode="wrap")
                st = sky_stats(sky)
                overhead = bool(np.isfinite(ytop) and ytop > ye + 1.0 and sg >= 2)
                fc_ = face_chord(rowline - (ye - EYE), segline, xb, xs)
                rows.append(dict(chord=fc_.get("chord"), lip_lead=fc_.get("lip_lead"), t=t, t_group=t + TOFF, alpha=vm["alpha_max"], dist_h=vm["dist_h"],
                                 hmd=st["hmd_fill"], hemi=st["upper_hemi_frac"], w10=st["width_above_deg"][10], w30=st["width_above_deg"][30],
                                 w80=st["w80_deg"], Hc=Hc - (ye - EYE), xc=xc_, overhead=overhead, eye_y=ye, ysurf=ysurf))
            if not rows:
                summ[mode] = None; continue
            al = np.array([r["alpha"] for r in rows]); tt = np.array([r["t"] for r in rows])
            k = int(np.argmax(al))
            Hc_ = np.array([r["Hc"] for r in rows]); D = xs - np.array([r["xc"] for r in rows])

            def smooth(v, n=12 // step):
                if len(v) < n or n < 2:
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
            summ[mode] = dict(end_t_group=(end_t + TOFF) if end_t is not None else None, end_why=end_why,
                              alpha_max=float(al[k]), t_alpha_max=float(tt[k]) + TOFF, dist_at=float(rows[k]["dist_h"]), eye_y_at=float(rows[k]["eye_y"]),
                              hmd_fill_max=float(max(r["hmd"] for r in rows)), hemi_max=float(max(r["hemi"] for r in rows)),
                              w10_at=float(rows[k]["w10"]), w30_at=float(rows[k]["w30"]), w80_at=float(rows[k]["w80"]),
                              lip_overhead=bool(any(r["overhead"] for r in rows)),
                              t_alpha10=(t10 + TOFF) if t10 is not None else None, view_s=(float(tt[k]) - t10) if t10 is not None else None,
                              growth_share=gs, crest_above_eye_m=float(rows[k]["Hc"] - EYE),
                              chord_at=rows[k]["chord"], lip_lead_max=max([r["lip_lead"] for r in rows if r["lip_lead"] is not None], default=None),
                              series=dict(t_group=[r["t_group"] for r in rows], alpha=[round(r["alpha"], 2) for r in rows],
                                          hmd=[round(r["hmd"], 3) for r in rows], hemi=[round(r["hemi"], 3) for r in rows], Hc=[round(r["Hc"], 2) for r in rows],
                                          xc=[round(r["xc"], 1) for r in rows], eye_y=[round(r["eye_y"], 2) for r in rows], ysurf=[round(r["ysurf"], 2) for r in rows],
                                          grow=[round(float(v), 2) for v in grow], appr=[round(float(v), 2) for v in appr]))
        r = summ.get("ride") or {}
        fx = summ.get("fixed") or {}
        res.append(dict(x_seat=float(xs), z_seat=zs, ride=r, fixed=fx, alpha_max_before_wet=r.get("alpha_max", -1),
                        lip_overhead_while_dry=r.get("lip_overhead"), hmd_fill_max=r.get("hmd_fill_max"), hemi_max=r.get("hemi_max"),
                        growth_share=r.get("growth_share"), view_s=r.get("view_s"), lip_lead_max=r.get("lip_lead_max"), t_alpha_max=r.get("t_alpha_max")))
        print("seat x %.1f z %.0f | ride: alpha %.1f at %.2f, end %s (%s), overhead %s, hmd %.2f, hemi %.2f, lip lead %s, view %s s | fixed: alpha %.1f, end %s" % (
            xs, zs, r.get("alpha_max", -1), r.get("t_alpha_max", -1), r.get("end_t_group"), r.get("end_why"), r.get("lip_overhead"), r.get("hmd_fill_max", -1),
            r.get("hemi_max", -1), r.get("lip_lead_max"), r.get("view_s"), fx.get("alpha_max", -1), fx.get("end_t_group")), flush=True)
    best = max(res, key=lambda r: (bool(r["lip_overhead_while_dry"]), (r["lip_lead_max"] or -99) > 0, r["alpha_max_before_wet"])) if res else None
    out = dict(run_id=os.path.basename(rd.rstrip("/\\")), eye_height_m=EYE, boat_length_m=BOAT, z_seat=zs, off_box_m=M.off_box, off_E3_m=OFF_E3,
               frame_step=step, best_seat=best,
               scan=[{k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "series"}) for k, v in r.items()} for r in res],
               series_best=(best["ride"] or {}).get("series") if best else None)
    nm = os.path.join(rd, "seat_r_z%+04d.json" % int(round(zs)))
    json.dump(out, open(nm, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    rd = sys.argv[1]; zs = float(sys.argv[2])
    xs = [float(v) for v in sys.argv[3:] if not v.startswith("--")] or list(np.arange(470.0, 541.0, 5.0))
    st = 2 if "--step2" in sys.argv else 1
    o = measure(rd, zs, xs, step=st)
    b = o["best_seat"] or {}
    print("best", b.get("x_seat"), json.dumps({k: v for k, v in (b.get("ride") or {}).items() if k != "series"}, default=float, ensure_ascii=False))
