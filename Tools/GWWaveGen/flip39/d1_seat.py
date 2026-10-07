# -*- coding: utf-8 -*-
"""FLIP39 D1-2：座席（seat_v1 の目）から見た P3 の波を、体験の物差しで測る（既存のキャッシュだけ。新しい流体計算はしない）。

座席の目の位置：Tools/GWContext/seat_v1.json の seat.eye_world（Unity の世界座標）。
計算の座標への写し：P3 の置き方 Unity/Build/FLIP37/P3/H25_R18_mg/place_p3.json の M_sim_to_unity（倍率 1.1・回転・平行移動）の逆。
角度は相似変換で変わらないので計算の座標で求め、長さは 1.1 倍して作品（Unity）の長さで書く。
水面：窓の中（x 300〜640、z ±70）は P3 の hf（0.5 m の升、一番上の水面と水の区間の数）、窓の外は R18 の hf（2 m）。
R18 の箱（z ±120 m）の外は計算がないので、平らな海（高さ 0）として扱う。
"""
import sys, os, json, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_common import *

SEAT = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWContext/seat_v1.json"
PLACE = os.path.join(FLIP37, "P3", "H25_R18_mg", "place_p3.json")
NAZ = 720  # 方位の升 0.5°


def setup():
    pl = json.load(open(PLACE, encoding="utf-8"))
    M = np.array(pl["M_sim_to_unity"]); S = float(np.linalg.norm(M[:3, 0]))
    seat = json.load(open(SEAT, encoding="utf-8"))
    Mi = np.linalg.inv(M)
    eye = (Mi @ np.array(seat["seat"]["eye_world"] + [1.0]))[:3]
    return dict(M=M, Mi=Mi, S=S, eye=eye, seat=seat, place=pl)


def surface_points(p3, r18, fi):
    """コマ fi（P3 の並びの番号）の水面の点（x, y, z）と、張り出しの印（区間の数）。窓の中は P3、外は R18。"""
    fr = int(p3["frames"][fi])
    X, Z = np.meshgrid(p3["x"], p3["z"])
    Y = p3["eta"][fi]; Sg = p3["seg"][fi]
    ok = np.isfinite(Y)
    pts = [np.c_[X[ok], Y[ok], Z[ok]]]; segs = [Sg[ok]]
    k = fr - 1
    X2, Z2 = np.meshgrid(r18["x"], r18["z"])
    Y2 = r18["eta"][k]
    inwin = (X2 >= 300) & (X2 <= 640) & (np.abs(Z2) <= 70)
    ok2 = np.isfinite(Y2) & ~inwin
    pts.append(np.c_[X2[ok2], Y2[ok2], Z2[ok2]]); segs.append(r18["seg"][k][ok2])
    return np.concatenate(pts), np.concatenate(segs)


def view_measures(P, eye, rmin=2.0):
    d = P - eye
    hd = np.hypot(d[:, 0], d[:, 2])
    m = hd > rmin
    el = np.degrees(np.arctan2(d[m, 1], hd[m]))
    az = np.degrees(np.arctan2(d[m, 2], -d[m, 0]))       # 0° ＝ 沖（−x、波の来る向き）、+ は +z 側
    ib = np.clip(((az + 180.0) / 360.0 * NAZ).astype(int), 0, NAZ - 1)
    sky = np.full(NAZ, -90.0)
    np.maximum.at(sky, ib, el)
    k = int(np.argmax(el))
    return sky, dict(alpha_max=float(el[k]), az=float(az[k]), dist_h=float(hd[m][k]), y=float(P[m][k, 1]), x=float(P[m][k, 0]), z=float(P[m][k, 2]))


def sky_stats(sky):
    azc = -180 + (np.arange(NAZ) + 0.5) * 360.0 / NAZ
    a = np.clip(sky, 0, 90)
    daz = np.radians(360.0 / NAZ)
    omega = float(np.sum(np.sin(np.radians(a))) * daz)                 # 地平線より上で水が占める立体角 (sr)
    fwd = np.abs(azc) <= 55.0
    hmd = float(np.sum(np.minimum(a[fwd], 55.0)) / (fwd.sum() * 55.0))  # 前 ±55°・上 0〜55° の窓（方位・仰角の座標で）を水が占める割合
    w = {th: float(np.sum(a >= th) * 360.0 / NAZ) for th in (5, 10, 20, 30, 45)}
    ap = float(a.max()); kp = int(np.argmax(a))
    # 頂の 0.8 倍以上の方位の幅（頂のまわりで連続した所）
    above = a >= 0.8 * ap
    i0 = kp; i1 = kp
    while above[(i0 - 1) % NAZ] and (kp - i0) < NAZ: i0 -= 1
    while above[(i1 + 1) % NAZ] and (i1 - kp) < NAZ: i1 += 1
    w80 = (i1 - i0 + 1) * 360.0 / NAZ
    return dict(omega_sr=omega, upper_hemi_frac=omega / (2 * np.pi), hmd_fill=hmd, width_above_deg=w, peak_alpha=ap, peak_az=float(azc[kp]), w80_deg=w80)


def seat_line(p3, fi, eye):
    """座席を通る z の列（z=座席）の、座席より沖の水面：頂、前の面の最大の傾き、張り出し（区間 ≥2）の先、座席の真上の水。"""
    iz = int(np.argmin(abs(p3["z"] - eye[2])))
    x = p3["x"]; row = p3["eta"][fi, iz].astype(float); sg = p3["seg"][fi, iz]
    sea = (x < eye[0]) & (x > eye[0] - 150)
    k = int(np.nanargmax(np.where(sea, row, -np.inf)))
    xc, yc = x[k], row[k]
    # 前の面：頂から座席の方（+x）へ、頂の高さの 0.2 倍まで下がる所まで
    j = k
    while j + 1 < len(x) and np.isfinite(row[j + 1]) and row[j + 1] > 0.2 * yc and x[j + 1] <= eye[0] + 30:
        j += 1
    seg_ = slice(k, j + 1)
    sl = -np.gradient(row, x)[seg_]
    face = float(np.degrees(np.arctan(np.nanmax(sl)))) if j > k + 1 else np.nan
    # 張り出し：頂より前で、上から水→空気→水の列
    ov = (sg >= 2) & (x >= xc - 5) & (x <= eye[0] + 40)
    tip = float(x[ov].max()) if ov.any() else np.nan
    ov_len = float(ov.sum() * (x[1] - x[0]))
    ie = int(np.argmin(abs(x - eye[0])))
    return dict(crest_x=float(xc), crest_y=float(yc), face_deg=face, overhang_cols_m=ov_len, lip_tip_x=tip,
                eta_at_seat=float(row[ie]), seg_at_seat=int(sg[ie]))


def crest_shape(p3, fi):
    """峰に沿う頂（窓の中、z ごとの最も高い水面）：頂、頂の 0.8・0.9 倍以上の長さ、半分の高さの幅。"""
    e = p3["eta"][fi]; cl = np.nanmax(e, axis=1); z = p3["z"]; dz = z[1] - z[0]
    Hc = float(np.nanmax(cl))
    return dict(Hc=Hc, z_at=float(z[np.nanargmax(cl)]), L80=float(np.sum(cl >= 0.8 * Hc) * dz), L90=float(np.sum(cl >= 0.9 * Hc) * dz),
                L50=float(np.sum(cl >= 0.5 * Hc) * dz), window_m=float(z[-1] - z[0] + dz))


def run(eye_xz_list=None, step=1):
    C = setup(); S = C["S"]; eye0 = C["eye"]
    p3 = load_p3()
    rj, r18 = load_run("R18_X30L120LG_H39")
    t = p3["t"]
    out = dict(eye_sim=eye0, scale=S, frames=[], seat_line=[], crest=[], sky=[], ride=[])
    for fi in range(0, len(t), step):
        P, sg = surface_points(p3, r18, fi)
        sky, vm = view_measures(P, eye0)
        st = sky_stats(sky)
        sl = seat_line(p3, fi, eye0)
        # 船が水面に乗る場合（上下だけ）：目＝座席の水面＋1.666 m（計算の座標。作品で 1.83 m）
        eye_r = eye0.copy(); eye_r[1] = (sl["eta_at_seat"] if np.isfinite(sl["eta_at_seat"]) else 0.0) + eye0[1]
        sky_r, vm_r = view_measures(P, eye_r)
        st_r = sky_stats(sky_r)
        out["frames"].append(dict(t=float(t[fi]), frame=int(p3["frames"][fi]), view=vm, stats=st, view_ride=vm_r, stats_ride=st_r, eye_ride_y=float(eye_r[1])))
        out["seat_line"].append(sl)
        out["crest"].append(crest_shape(p3, fi))
        out["sky"].append(sky.astype(np.float32))
        out["ride"].append(sky_r.astype(np.float32))
    return out, C


def run_positions(xs, z, step=4):
    """座席の x を動かした時の、いちばん大きい仰角などの最大値（設計の目安。固定の目）。"""
    C = setup(); eye0 = C["eye"]
    p3 = load_p3(); rj, r18 = load_run("R18_X30L120LG_H39")
    t = p3["t"]
    res = []
    for xe in xs:
        eye = np.array([xe, eye0[1], z])
        rows = []
        for fi in range(0, len(t), step):
            P, sg = surface_points(p3, r18, fi)
            sky, vm = view_measures(P, eye)
            st = sky_stats(sky)
            sl = seat_line(p3, fi, eye)
            rows.append((t[fi], vm["alpha_max"], st["hmd_fill"], st["upper_hemi_frac"], sl["eta_at_seat"], sl["seg_at_seat"], vm["dist_h"]))
        rows = np.array(rows)
        wet = rows[:, 4] > eye[1]
        tw = float(rows[np.argmax(wet), 0]) if wet.any() else None
        dry = rows[:, 0] < (tw if tw else 1e9)
        k = int(np.argmax(np.where(dry, rows[:, 1], -99)))
        res.append(dict(x=float(xe), z=float(z), t_eye_under_water=tw,
                        alpha_max_before_wet=float(rows[k, 1]), t_at=float(rows[k, 0]), dist_at=float(rows[k, 6]),
                        hmd_fill_max_before_wet=float(np.max(np.where(dry, rows[:, 2], 0))),
                        hemi_max_before_wet=float(np.max(np.where(dry, rows[:, 3], 0))),
                        overhead_water=bool(np.any(rows[:, 5] >= 2)), series=rows))
    return res


if __name__ == "__main__":
    out, C = run(step=1)
    sky = np.array(out.pop("sky")); ride = np.array(out.pop("ride"))
    np.savez_compressed(os.path.join(OUT, "seat_skyline.npz"), sky=sky, ride=ride, t=np.array([f["t"] for f in out["frames"]]),
                        az=-180 + (np.arange(NAZ) + 0.5) * 360.0 / NAZ)
    print("positions"); sys.stdout.flush()
    pos = run_positions([480.0, 500.0, 520.0, 540.0, 552.19, 570.0, 600.0, 630.0], C["eye"][2], step=4)
    jdump(dict(seat=out, positions=pos, eye_world=C["seat"]["seat"]["eye_world"], boat=C["seat"]["boat"], place=C["place"]), os.path.join(OUT, "seat_raw.json"))
    print("done")
