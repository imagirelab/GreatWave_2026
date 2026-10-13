# -*- coding: utf-8 -*-
"""FLIP46：解析の道具（g46_analyze.py・g46_video.py）を、答えの分かった合成の記録で確かめる（py -3.10 -B、numpy だけ）。
2026-10-12 解析と図の道具の役が書いた。Houdini は使わない。記録の形は g46_run.py と同じ（hf・r2・r3・r4・run_c・cfg）。

合成の波（物理ではない。道具の確かめだけ）：
  - 海底は GG06 の尾根（h0 17 m、k 0.25、x' 5.225 から 1:15、横に sech²）。海底の中の水面の場は正（Houdini の衝突の中と同じ向き。
    FLIP44 S8 で測った形）。静かな水面のずれ b = 0.08 m を全部の水面に足す。
  - 頂の上の点 X_top(t, y) = 98.345 m + c t − 0.002 y²（c は t_B に 273.5 m に着く速さ）。高さ A(t, y) は 10.2 m から t_B に 12.0 m へ
    （横に 1 − 0.1 (1 − sech²(y/40))）。形は A sech²(κ ξ) を、高さに比べて前へずらした物（x = ξ + sh·z）。ずらし sh は
    r(t, y) = (t/t_B)³ sech²(y/45) で、r = 1 のとき前の面がちょうど縦（sh = r / (0.7698 A κ)、κ は 0.0312 から t_B に 0.08 /m へ）。
    → 真ん中の縦の接線は t_B = 7.890 × √(h0/g) = 10.388 s、x 273.5 m、zB 12.0 m（hB 4.69 m、zB/hB 2.56）。
  - t ≥ t_td = 9.2 × √(h0/g)（12.11 s）に、横 20 m までの水の中に空気の穴（楕円、半径 2.5 × 1.5 m）を入れる（着水の読みの確かめ）。
  - y = 68 m では r ≤ 0.33（t ≤ 12.1 s）なので一価。t 12.04 s で巻く範囲は sech²(y/45) ≥ (t_B/t)³ → 片側 31 m（全幅 62 m）。
出力：Unity/Build/FLIP46/smoke/synth_ridge/（hf・r2・r3・r4・cfg.json・run_c00001.json・truth.json）
使い方：py -3.10 -B g46_synth_ridge.py
"""
import os, sys, json, math
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/FLIP46/smoke/synth_ridge"
G = 9.80665
H0 = 17.0
TS = math.sqrt(H0 / G)
FPS = 24.0
T_B = 7.890 * TS
X_B = 273.5
T_TD = 9.2 * TS
B = 0.08
X0 = 98.345
C = (X_B - X0) / T_B
K0, KB = 0.0312, 0.08
VOX = 1.0
NX, NZL, NY = 323, 68, 34          # x・横・縦の格子
XS = 0.5 + np.arange(NX)
ZL = 0.5 + np.arange(NZL)
YC = -16.5 + np.arange(NY)


def bed_z(x, y):
    xp = np.asarray(x) / H0; yp = np.asarray(y) / H0
    return -H0 * (1.0 - np.maximum(xp - 5.225, 0.0) / 15.0 / np.cosh(0.25 * yp) ** 2)


def params(t, y):
    s = t / T_B
    A = (10.2 + 1.8 * s) * (1.0 - 0.1 * (1.0 - 1.0 / np.cosh(y / 40.0) ** 2))
    kap = K0 + (KB - K0) * min(s, 1.3)
    r = s ** 3 / np.cosh(y / 45.0) ** 2
    sh = r / (0.7698 * A * kap)
    xtop = X0 + C * t - 0.002 * y * y
    xic = xtop - sh * A
    return A, kap, sh, xtop, xic


def phi(t, y, X, Z):
    """水面の場（水の中で負）。X・Z は同じ形の配列（計画の座標）。"""
    A, kap, sh, xtop, xic = params(t, y)
    zr = Z - B
    eta = A / np.cosh(kap * (X - sh * zr - xic)) ** 2
    p = zr - eta
    if t >= T_TD and y <= 20.0:
        zc = 0.35 * A
        e2 = ((X - (xic + sh * zc)) / 2.5) ** 2 + ((zr - zc) / 1.5) ** 2      # 水の体の真ん中の線（ξ = ξc をずらした所）の上
        p = np.maximum(p, 1.0 - e2)
    return np.maximum(p, bed_z(X, y) - Z)


def top(t, y):
    A, kap, sh, xtop, xic = params(t, y)
    xi = np.arange(-20.0, 360.0, 0.05)
    eta = A / np.cosh(kap * (xi - xic)) ** 2
    X = xi + sh * eta
    idx = np.round(X - 0.5).astype(int)
    ok = (idx >= 0) & (idx < NX)
    out = np.full(NX, -99.0)
    np.maximum.at(out, idx[ok], eta[ok] + B)
    bad = out < -50
    if bad.any():
        out[bad] = np.interp(XS[bad], XS[~bad], out[~bad])
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    nf = int(round(15.0 * FPS)) + 1
    frames = np.arange(1, nf + 1); ts = (frames - 1) / FPS
    XX, YY = np.meshgrid(XS, YC)
    meta_hf = dict(res=[NX, NY, NZL], x0=0.5, dx=1.0, z0=0.5, dz=1.0, y0=-16.5, dy=1.0, t_off=0.0)
    vel = {"vel.x": dict(res=[NX + 1, NY, NZL], p0=[0.0, -16.5, 0.5], d=[1.0, 1.0, 1.0], k=[0], z=0.5),
           "vel.y": dict(res=[NX, NY + 1, NZL], p0=[0.5, -17.0, 0.5], d=[1.0, 1.0, 1.0], k=[0], z=0.5)}
    meta_r2 = dict(res=[NX, NY, NZL], iz=0, z=0.5, x0=0.5, dx=1.0, nx=NX, y0=-16.5, dy=1.0, ny=NY, clip_m=8.0, t_off=0.0, vel=vel)
    meta_r3 = dict(meta_r2, z=67.5)
    # R4（x 150〜323、縦 −10〜16、t 9〜14 s）
    x4 = XS[XS >= 150.0]; y4 = YC[(YC >= -10.0) & (YC <= 16.0)]
    meta_r4 = dict(x0=float(x4[0]), dx=1.0, nx=len(x4), z0=0.5, dz=1.0, nz=NZL, y0=float(y4[0]), dy=1.0, ny=len(y4), clip_m=6.0, t_off=0.0)
    X4, Y4 = np.meshgrid(x4, y4)
    blocks = [(1, 2)] + [(a, min(a + 120, nf + 1)) for a in range(2, nf + 1, 120)]
    for a, b in blocks:
        fr = np.arange(a, b); tt = (fr - 1) / FPS
        hf = np.zeros((len(fr), NZL, NX), np.float32); r2 = np.zeros((len(fr), NY, NX), np.float16); r3 = np.zeros_like(r2)
        for i, t in enumerate(tt):
            for j, y in enumerate(ZL):
                hf[i, j] = top(t, y)
            r2[i] = np.clip(phi(t, 0.5, XX, YY), -8, 8)
            r3[i] = np.clip(phi(t, 67.5, XX, YY), -8, 8)
        np.savez_compressed(OUT + "/hf_c00001_b%05d.npz" % a, eta=hf, frames=fr, t=tt, meta=json.dumps(meta_hf))
        z16 = np.zeros((len(fr), NY, NX + 1), np.float16); w16 = np.zeros((len(fr), NY + 1, NX), np.float16)
        np.savez_compressed(OUT + "/r2_c00001_b%05d.npz" % a, sdf=r2, u=z16, w=w16, frames=fr, t=tt, meta=json.dumps(meta_r2))
        np.savez_compressed(OUT + "/r3_c00001_b%05d.npz" % a, sdf=r3, u=z16, v=np.zeros((len(fr), NY, NX), np.float16), w=w16,
                            frames=fr, t=tt, meta=json.dumps(meta_r3))
        print("block", a, b - 1)
    f4 = frames[(ts >= 9.0 - 1e-9) & (ts <= 14.0 + 1e-9)]
    for a in range(int(f4[0]), int(f4[-1]) + 1, 24):
        fr = np.arange(a, min(a + 24, int(f4[-1]) + 1)); tt = (fr - 1) / FPS
        r4 = np.zeros((len(fr), NZL, len(y4), len(x4)), np.float16)
        for i, t in enumerate(tt):
            for j, y in enumerate(ZL):
                r4[i, j] = np.clip(phi(t, y, X4, Y4), -6, 6)
        np.savez_compressed(OUT + "/r4_c00001_b%05d.npz" % a, sdf=r4, frames=fr, t=tt, meta=json.dumps(meta_r4))
        print("r4 block", a)
    parms = dict(dp=0.5, gridscale=2.0, x0=0.0, Lx=323.0, W=68.0, zb=-17.0, Hz=34.0, h0=H0, t_off=0.0,
                 ridge_on=1.0, ridge_x0=5.225 * H0, ridge_k=0.25, ridge_s=15.0)
    cfg = dict(run_id="synth_ridge", stage="FLIP46", kind="synthetic", parms=parms, f_start=1, f_first=1, f_end=int(nf),
               note="合成の記録（g46_synth_ridge.py）。物理ではない。解析の道具の確かめだけ")
    json.dump(cfg, open(OUT + "/cfg.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    run = dict(stage="FLIP46", run_id="synth_ridge", f_start=1, f_end_done=int(nf), stopped=None, parms=parms,
               info=dict(still_offset_online=dict(value=B, n_frames=25, x_range=[260.0, 310.0], window=[0.5, 1.5])))
    json.dump(run, open(OUT + "/run_c00001.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    tf = T_B; f_on = int(math.ceil(tf * FPS - 1e-9)) + 1
    t9 = 9.142 * TS
    half9 = 45.0 * math.acosh(1.0 / math.sqrt((T_B / t9) ** 3))
    truth = dict(t_B=T_B, x_B=X_B, zB=12.0, hB=float(-bed_z(X_B, 0.0)), zB_over_hB=12.0 / float(-bed_z(X_B, 0.0)), still_offset=B,
                 first_frame_at_or_after_tB=f_on, t_td=T_TD, first_frame_at_or_after_td=int(math.ceil(T_TD * FPS - 1e-9)) + 1,
                 fig9_t=t9, fig9_overturned_half_m=half9, fig9_far_r=float((t9 / T_B) ** 3 / math.cosh(68.0 / 45.0) ** 2),
                 note_ja="r = 1 で前の面が縦。格子 1 m の読みでは、縦の接線は真の時刻より数コマずれうる（読みの細かさの確かめ）")
    json.dump(truth, open(OUT + "/truth.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(truth, ensure_ascii=False))


if __name__ == "__main__":
    main()
