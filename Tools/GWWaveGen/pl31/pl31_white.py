# -*- coding: utf-8 -*-
"""仕上げ31 白の部：白の出現（T_white）・発生の表・102/135/176/177 の測りを、仕上げ28 の採用（K*′ P28R2rec・G_p28rec）と
仕上げ29 の視点によらない材質（PL29 Ukiyoe Keypose：白 = 白の範囲 zZone ∧ T_white ≤ τ）で作り直す。

設計31 の ds31_white.py は F_final の動きと 29修正01 の色面（原画カメラの投影の焼き込み）の「終態の白」で作った。仕上げ29 で投影をやめたので、
終態の白は材質の白の範囲（面の座標だけで決まる。pl31_zone.py）と T_white の到着で決まる。この道具はその定義で数える。

入力（読むだけ）：
  - 主役波のパッケージ Unity/Build/Polish/28/G_p28rec/art_on（位置・精度の層・T_white）と時間曲線 timewarp_G_p28rec.json
  - 面の座標 Unity/Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin と材質の値 Tools/GWWaveGen/pl29/pl29_material_params.txt
出力（Git 対象外）：Unity/Build/Polish/31/white/
  - pl31_white_numpy.json（102・135・177 の測り、白の範囲の頂点の数、誘導の記録）
  - pl31_twhite_r32f.bin（誘導 pl31_white_rate_cap を掛けた T_white。要らなければ書かない）と hero_pkg/（位置はハードリンク、T_white だけ差し替え）
  - pl31_white_onset.json ＋ pl31_white_onset_f32.bin（発生の表。設計31 と同じ 15 値の並び）
102 の読み（美術優先31・設計31 と同じ目安）：30 Hz の 1 コマで白くなる割合が終態の白の 2% 以下。割合は t* の面の上の面積（テクセルの代わり。
三角形ごとに重心座標の標本を置き、面の座標と T_white をシェーダーと同じ線形の補いで読む）と、今の形の世界の面積の 2 つで数える。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
import pl31_zone as Z  # noqa: E402
import ds31_white as W  # noqa: E402

PKG = REPO + "/Unity/Build/Polish/28/G_p28rec/art_on"
WARP = REPO + "/Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json"
OUT = REPO + "/Unity/Build/Polish/31/white"
FPS, T_END, T_STAR = 30, 14.0, 12.0
NEVER = 1e8
BODY = (18, 394)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def build_samples(A, p, R, C, P0, n_sub=3):
    """本体の列の三角形に標本を置き、面の座標を線形に補って白の範囲を読む。戻り値：標本の三角形の頂点・重心座標・t* の面積の重み・範囲の白。"""
    T = W.tri_index(R, C)
    cols = np.tile(np.arange(C), R)
    keep = (cols[T].min(1) >= BODY[0]) & (cols[T].max(1) <= BODY[1])
    T = T[keep]
    area = W.tri_area(P0, T)
    B = Z.tri_samples(n_sub)
    m = len(B)
    Ti = np.repeat(T, m, axis=0)
    Bi = np.tile(B, (len(T), 1))
    wA = np.repeat(area / m, m)
    As = {k: (A[k][Ti] * Bi).sum(1) for k in ("F", "hrel", "c", "ca", "dtip", "hrow")}
    z, _ = Z.zone(As, p)
    return T, Ti, Bi, wA, z > 0


def arrived(TWv, Ti, Bi, tau):
    """シェーダーと同じ到着の読み：頂点の旗（3 頂点とも届いた → 白、3 頂点とも t* まで届かない → 白でない）、それ以外は補った T ≤ τ。
    t* まで届かない頂点の T は τ + 1 に置き換わる（シェーダーの o.tw）。"""
    never = TWv >= NEVER
    tv = np.where(never, tau + 1.0, TWv)
    tt = (tv[Ti] * Bi).sum(1)
    allin = (TWv[Ti] <= tau).all(1)
    allnever = never[Ti].all(1)
    return np.where(allin, True, np.where(allnever, False, tt <= tau))


def sample_T(TWv, Ti, Bi):
    """標本ごとの白くなる τ（t* までに届かないなら +inf）。T_white の補いが単調なので、到着の時刻は補った値（旗の場合は最大の値）。"""
    never = TWv >= NEVER
    tt = (np.where(never, np.inf, TWv)[Ti] * Bi).sum(1)
    tt = np.where(never[Ti].any(1), np.inf, tt)
    allin = TWv[Ti].max(1)
    # 3 頂点とも届いた時刻（最大）より前に、補った値が届く。旗の規則で「最大の時刻」で必ず白になる
    return np.minimum(tt, np.where(never[Ti].any(1), np.inf, allin))


def rate_cap(Ts_sorted, wcum, TWv, fin, frames_t, frames_tau, wt, wtau, cap):
    """名前の付いた美術の誘導 pl31_white_rate_cap（設計31 の ds31_white_rate_cap と同じ形）：30 Hz の 1 コマで白くなる面積の割合が cap を
    越えないよう、T_white を早める向きだけに単調に付け替える。白の広がる順と場所は変えない。"""
    F = np.interp(frames_tau, Ts_sorted, wcum, left=0.0, right=1.0)
    F = np.where(frames_tau < Ts_sorted[0], 0.0, F)
    G = F.copy()
    for k in range(len(F) - 2, -1, -1):
        G[k] = max(F[k], G[k + 1] - cap)
    fv = np.interp(TWv[fin], Ts_sorted, wcum, left=0.0, right=1.0)
    Gu, first = np.unique(G, return_index=True)
    tu = frames_t[first]
    t_new = np.interp(fv, Gu, tu)
    t_old = W.t_of_tau(TWv[fin], wt, wtau)
    keep = np.interp(t_old, frames_t, G - F) <= 1e-12
    t_new = np.where(keep, t_old, np.minimum(t_new, t_old))
    TWn = TWv.copy()
    TWn[fin] = np.minimum(np.interp(t_new, wt, wtau), TWv[fin])
    shift = t_old - t_new
    return TWn, {"cap": cap, "frames_changed": int((G - F > 1e-12).sum()), "vertices_moved": int((np.abs(TWn[fin] - TWv[fin]) > 1e-9).sum()),
                 "t_shift_max_s": float(shift.max()), "tau_shift_max_s": float((TWv[fin] - TWn[fin]).max()),
                 "window_t": [float(frames_t[np.argmax(G - F > 1e-12)]), float(frames_t[len(G) - 1 - np.argmax((G - F > 1e-12)[::-1])])] if (G - F > 1e-12).any() else None}


CLAW_DIR = REPO + "/Unity/Build/Design/33/claws"


def crest_s(A, R, C):
    """行ごとの頂（F = 1）の弧長 s（t* の面の上の m）。列に沿って F が 1 を越える所を線形に補う。"""
    F = A["F"].reshape(R, C); s = A["s"].reshape(R, C)
    sc = np.full(R, np.nan)
    for r in range(R):
        f = F[r, BODY[0]:BODY[1] + 1]; ss = s[r, BODY[0]:BODY[1] + 1]
        k = np.nonzero((f[:-1] < 1.0) & (f[1:] >= 1.0))[0]
        if len(k):
            j = k[0]
            w = (1.0 - f[j]) / max(f[j + 1] - f[j], 1e-9)
            sc[r] = ss[j] + w * (ss[j + 1] - ss[j])
    ok = np.isfinite(sc)
    sc[~ok] = np.interp(np.nonzero(~ok)[0], np.nonzero(ok)[0], sc[ok])
    return sc


def order_patch(A, TW0, fin, body, R, C, seed_row, ks, kb, wf=0.0, wb=0.0):
    """名前の付いた美術の誘導 pl31_white_order（修正01 の形 patch）：白は頂の最も高い所（seed_row の頂）の塊から始まり、
    t* の面の上の距離の順に、頂に沿って横へ・前の面を唇の先と下面へ・背を下へ、同じ速さの比で広がる。
    距離 d = √(Δc² + (Δs/k)²)（Δc：頂に沿う c の差、Δs：頂からの弧長、前は k = ks、背は k = kb）。
    値の集まり（本体の列の有限の T_white）はそのままに、d の順に早い時刻から割り当て直す。
    修正前の形（rank：F の順位・行の頂の高さの順位・元の T の順位の重み）は、頂の 1 本の線（t 6 s）と尾の頂の細い帯（t 8.5〜9.5 s）を作った。
    距離の順では、白の縁はどこでも塊の縁で、頂の線だけが先に白くなることがない。尾の行は頂の両側が同じ時に白くなる（帯の幅のまま進む）。"""
    rows = np.repeat(np.arange(R), C)
    sc = crest_s(A, R, C)
    ds = A["s"] - sc[rows]
    cR = A["c"].reshape(R, C)
    c_seed = float(np.interp(sc[seed_row], A["s"].reshape(R, C)[seed_row], cR[seed_row]))
    dc = A["c"] - c_seed
    g = np.where(ds >= 0, np.maximum(ds - wf, 0.0) / ks, np.maximum(-ds - wb, 0.0) / kb)
    key = np.sqrt(dc * dc + g * g)
    U = fin & body
    ii = np.nonzero(U)[0]
    newT = np.sort(TW0[ii])[np.argsort(np.argsort(key[ii], kind="stable"), kind="stable")]
    TWo = TW0.copy(); TWo[ii] = newT
    info = dict(mode="patch", seed_row=int(seed_row), c_seed_m=c_seed, s_crest_seed_m=float(sc[seed_row]), ks=ks, kb=kb, band_front_m=wf, band_back_m=wb, vertices=int(len(ii)),
                tau_shift_abs_median_s=float(np.median(np.abs(newT - TW0[ii]))), tau_shift_abs_max_s=float(np.abs(newT - TW0[ii]).max()),
                rule_ja="d = √(Δc² + (max(|Δs| − w, 0)/k)²) の順（前 k = ks・w = band_front_m、背 k = kb・w = band_back_m）。頂の両側の幅 w の帯は、"
                        "頂に沿って白が届いた時にそろって白くなる。本体の列の有限の T_white の値の集まりを d の順に割り当て直す")
    return TWo, info, key


def claw_roots(A, R, C, zone_v, wt, wtau):
    """設計33 の爪（場面で再生する焼き込み）の根元：sheet_rc（行, 列）の面の座標、白の範囲か、成長の始まり（最初に見えるコマ）。"""
    rig = json.load(open(CLAW_DIR + "/ds33_claw_rig.json", encoding="utf-8"))
    lay = json.load(open(CLAW_DIR + "/ds33_claw_layout.json", encoding="utf-8"))
    nc = len(lay["claws"])
    sk = np.memmap(CLAW_DIR + "/" + lay["files"]["skel"]["file"], dtype="<f4", mode="r", shape=(lay["frames"], nc, 36))
    vis = np.asarray(sk[:, :, 34]) > 0.5
    first = np.argmax(vis, axis=0)
    anyv = vis.any(0)
    out = []
    cR = A["c"].reshape(R, C); sR = A["s"].reshape(R, C); zR = zone_v.reshape(R, C)
    for k, cl in enumerate(rig["claws"]):
        r, c = cl["sheet_rc"]
        r0, c0 = int(np.floor(r)), int(np.floor(c)); fr, fc = r - r0, c - c0
        w = np.array([(1 - fr) * (1 - fc), (1 - fr) * fc, fr * (1 - fc), fr * fc])
        cor = [(r0, c0), (r0, c0 + 1), (r0 + 1, c0), (r0 + 1, c0 + 1)]
        cm = float(sum(wi * cR[q] for wi, q in zip(w, cor))); sm = float(sum(wi * sR[q] for wi, q in zip(w, cor)))
        out.append(dict(id=cl["id"], k=k, row_name=cl["row"], rc=[float(r), float(c)], corners=[r0 * C + c0, r0 * C + c0 + 1, (r0 + 1) * C + c0, (r0 + 1) * C + c0 + 1],
                        zone=bool(zR[int(round(r)), int(round(c))]), c_m=cm, s_m=sm,
                        t_start=(float(first[k]) / lay["hz"] if anyv[k] else None)))
    return out, dict(rig_sha256=sha(CLAW_DIR + "/ds33_claw_rig.json"), skel_sha256=sha(CLAW_DIR + "/" + lay["files"]["skel"]["file"]))


def claw_lag(TWv, roots, wt, wtau):
    """根元の白（根元の格子の 4 頂点がそろって白くなる時刻、t の秒）と成長の始まりの差。正は「白くなる前に伸び始める」。"""
    res = []
    for q in roots:
        if not q["zone"] or q["t_start"] is None:
            continue
        tw = TWv[q["corners"]]
        t_w = float(W.t_of_tau(tw.max(), wt, wtau)) if (tw < NEVER).all() else float("inf")
        r, c = q["rc"]; fr, fc = r - np.floor(r), c - np.floor(c)
        twb = (1 - fr) * (1 - fc) * tw[0] + (1 - fr) * fc * tw[1] + fr * (1 - fc) * tw[2] + fr * fc * tw[3]
        t_b = float(W.t_of_tau(twb, wt, wtau)) if (tw < NEVER).all() else float("inf")
        res.append(dict(id=q["id"], row_name=q["row_name"], t_start=q["t_start"], t_white_root=t_w, t_white_root_bilinear=t_b,
                        lag_s=t_w - q["t_start"], lag_bilinear_s=t_b - q["t_start"]))
    lag = np.array([x["lag_s"] for x in res])
    lagb = np.array([x["lag_bilinear_s"] for x in res])
    return dict(zone_rooted=len(res), violations=int((lag > 0.5 / FPS).sum()), violations_any=int((lag > 1e-6).sum()),
                lag_max_s=float(lag.max()), violations_bilinear_1frame=int((lagb > 1.0 / FPS).sum()), lag_bilinear_max_s=float(lagb.max()),
                rule_ja="violations：根元の格子の 4 頂点がそろって白くなる時刻が最初に見えるコマより半コマ超遅い。"
                        "violations_bilinear_1frame：根元の T_white を双線形に補った時刻が 1 コマ超遅い",
                worst=sorted(res, key=lambda x: -x["lag_s"])[:8])


def claw_pins(TWv, A, roots, fin, body, wt, wtau, r_pin, v_pin, cone_m):
    """名前の付いた美術の誘導 pl31_white_claw_pin：設計33 の爪（焼き込み）は「根元が白くなると伸び始める」（136）。白の範囲に根元がある爪ごとに、
    根元から r_pin 以内（t* の面の座標 (c, s) の距離）の T_white を、その爪の最初に見えるコマの半コマ前までに早め、その外は v_pin（m/s）で
    根元から広がる円錐の時刻までに早める（円錐は r_pin + cone_m まで。早める向きだけ）。"""
    TWp = TWv.copy()
    U = fin & body
    moved = 0
    for q in roots:
        if not q["zone"] or q["t_start"] is None:
            continue
        d = np.hypot(A["c"] - q["c_m"], A["s"] - q["s_m"])
        m = U & (d < r_pin + cone_m)
        t_pin = q["t_start"] - 0.5 / FPS + np.maximum(d[m] - r_pin, 0.0) / v_pin
        tau_pin = W.tau_at(t_pin, wt, wtau)
        new = np.minimum(TWp[m], tau_pin)
        moved += int((new < TWp[m] - 1e-9).sum())
        TWp[m] = new
    return TWp, dict(r_pin_m=r_pin, v_pin_mps=v_pin, cone_m=cone_m, vertices_moved=moved,
                     rule_ja="白の範囲に根元がある爪ごとに、根元から r_pin 以内の T_white をその爪の最初に見えるコマの半コマ前までに、外は根元から v_pin で広がる円錐の時刻までに早める（円錐は根元から r_pin + cone_m まで。早める向きだけ）")


def fraction_series(Tsamp, wA, white_final, frames_tau):
    m = white_final & np.isfinite(Tsamp)
    o = np.argsort(Tsamp[m])
    Ts = Tsamp[m][o]
    wc = np.cumsum(wA[m][o])
    tot = wA[white_final].sum()
    f = np.interp(frames_tau, Ts, wc / tot, left=0.0, right=wc[-1] / tot)
    f = np.where(frames_tau < Ts[0], 0.0, f)
    return f, Ts, wc / tot, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--rate-cap", type=float, default=0.018, help="pl31_white_rate_cap（0 で切る）。2% の目安を越えるときだけ掛かる")
    ap.add_argument("--n-sub", type=int, default=3)
    ap.add_argument("--order", type=float, default=0.6, help="pl31_white_order：前の白の到着の順を流れの座標 F（頂 → 唇の先 → 下面）へ寄せる重み（0 で切る）")
    ap.add_argument("--order-h", type=float, default=0.3, help="pl31_white_order：行の頂の高さ（高い行から低い行へ）の重み。0 だと頂の全部の行が同時に白くなり、t 6 s に頂の全長の細い白い線になった")
    ap.add_argument("--order-mode", choices=["rank", "patch"], default="patch",
                    help="pl31_white_order の形。rank：修正前（F・頂の高さ・元の T の順位の重み）。patch：修正01（頂の最も高い所からの面の上の距離の順）")
    ap.add_argument("--patch-ks", type=float, default=1.0, help="patch：前の面（頂 → 唇の先 → 下面）の広がりの速さの比（頂に沿う向きに対して）")
    ap.add_argument("--patch-kb", type=float, default=1.0, help="patch：背（頂 → 背の下）の広がりの速さの比")
    ap.add_argument("--patch-wf", type=float, default=0.0, help="patch：頂の前の側の帯の幅 m（頂に沿って白が届いた時にそろって白くなる）")
    ap.add_argument("--patch-wb", type=float, default=0.0, help="patch：頂の背の側の帯の幅 m")
    ap.add_argument("--seed-row", type=int, default=-1, help="patch：白の始まりの行（-1：行の頂の高さ hrow が最大の行）")
    ap.add_argument("--claw-pin", type=float, default=0.6, help="pl31_white_claw_pin：爪の根元から白くする半径 m（0 で切る）")
    ap.add_argument("--claw-pin-v", type=float, default=1.5, help="pl31_white_claw_pin：根元の白が広がる速さ m/s")
    ap.add_argument("--claw-pin-cone", type=float, default=0.6, help="pl31_white_claw_pin：円錐の広がりの上限 m（根元の円の外）")
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    pk = W.Pkg(PKG)
    R, C, n = pk.R, pk.C, pk.n
    wt, wtau = W.load_warp(WARP)
    frames_t = np.arange(int(round(T_END * FPS)) + 1) / FPS
    frames_tau = W.tau_at(frames_t, wt, wtau)
    K = len(frames_t)
    prm = Z.load_params()
    A = Z.load_attr(n=n)
    zv, edgeF = Z.zone(A, prm)
    zone_v = zv > 0
    P0 = pk.P[-1].astype(np.float64)
    T, Ti, Bi, wA, zs = build_samples(A, prm, R, C, P0, a.n_sub)
    TW0 = pk.tw.copy()
    fin0 = TW0 < NEVER
    rows = np.repeat(np.arange(R), C)
    cols = np.tile(np.arange(C), R)
    body = (cols >= BODY[0]) & (cols <= BODY[1])
    log = dict(vertices=int(n), twhite_finite=int(fin0.sum()), zone_vertices=int(zone_v.sum()), zone_body_vertices=int((zone_v & body).sum()),
               zone_body_never=int((zone_v & body & ~fin0).sum()), zone_body_never_rows=sorted(set(int(x) for x in rows[zone_v & body & ~fin0])),
               samples=int(len(Ti)), samples_zone=int(zs.sum()), n_sub=a.n_sub, triangles=int(len(T)))

    def measure(TWv, tag):
        fin = TWv < NEVER
        Ts_ = sample_T(TWv, Ti, Bi)
        final = zs & np.isfinite(Ts_) & (Ts_ <= 0.0)       # 終態の白（t* で白）
        f, Ts_sorted, wcum, tot = fraction_series(Ts_, wA, final, frames_tau)
        inc = np.diff(f)
        # 世界の面積（今の形）：30 Hz のコマごとに、白の標本の面積の重みを今の三角形の面積に置き換えて足す
        warea = np.zeros(K); farea = np.zeros(K)
        m = len(Bi) // len(T)
        tri_final = final.reshape(len(T), m).mean(1)
        for k in range(K):
            tau = float(frames_tau[k])
            if k % 2 and 5.0 < frames_t[k] < 12.0:
                pass
            Pk = pk.eval(tau)
            Ak = W.tri_area(Pk, T)
            wk = (final & (Ts_ <= tau)).reshape(len(T), m).mean(1)
            warea[k] = float((Ak * wk).sum()); farea[k] = float((Ak * tri_final).sum())
        af = warea / np.maximum(farea, 1e-9)
        ainc = np.diff(af)
        first_k = int(np.argmax(f > 0))
        res = dict(tag=tag,
                   final_white_area_tstar_m2=float(tot), final_white_samples=int(final.sum()),
                   zone_samples_never_white=int((zs & ~final).sum()), zone_area_never_white_m2=float(wA[zs & ~final].sum()),
                   first_white_t=float(frames_t[first_k]), first_white_tau=float(Ts_sorted[0]), first_white_t_exact=float(W.t_of_tau(Ts_sorted[0], wt, wtau)),
                   all_white_t=float(frames_t[int(np.argmax(f >= f[-1] - 1e-12))]),
                   surface_fraction_max_increment=float(inc.max()), surface_fraction_max_increment_t=float(frames_t[int(np.argmax(inc)) + 1]),
                   surface_frames_over_2pct=int((inc > 0.02).sum()),
                   world_fraction_max_increment=float(ainc.max()), world_fraction_max_increment_t=float(frames_t[int(np.argmax(ainc)) + 1]),
                   world_frames_over_2pct=int((ainc > 0.02).sum()),
                   monotone_surface=bool((inc >= -1e-12).all()),
                   series=dict(t=frames_t.round(4).tolist(), surface_fraction=f.round(6).tolist(), world_fraction=af.round(6).tolist()))
        return res, Ts_, final, Ts_sorted, wcum, fin

    before, Tsamp0, final0, Ts_sorted0, wcum0, fin = measure(TW0, "G_p28rec の T_white（誘導なし）")
    print("before", {k: v for k, v in before.items() if k != "series"}, "%.1fs" % (time.time() - t0))
    capinfo = None
    orderinfo = None
    TW = TW0
    after = before
    roots, claw_src = claw_roots(A, R, C, zone_v, wt, wtau)
    claws_before = claw_lag(TW0, roots, wt, wtau)
    print("claws before", {k: v for k, v in claws_before.items() if k != "worst"})
    pininfo = None
    if a.order > 0 and a.order_mode == "patch":
        seed = int(np.argmax(A["hrow"].reshape(R, C)[:, 200])) if a.seed_row < 0 else a.seed_row
        TWo, orderinfo, _ = order_patch(A, TW0, fin0, body, R, C, seed, a.patch_ks, a.patch_kb, a.patch_wf, a.patch_wb)
        orderinfo["claws_after_order"] = {k: v for k, v in claw_lag(TWo, roots, wt, wtau).items() if k != "worst"}
        if a.claw_pin > 0:
            TWo, pininfo = claw_pins(TWo, A, roots, fin0, body, wt, wtau, a.claw_pin, a.claw_pin_v, a.claw_pin_cone)
        TW = TWo
        before_cap, _, _, Ts_sorted0, wcum0, _ = measure(TW, "pl31_white_order（patch）・pl31_white_claw_pin の後（cap の前）")
        print("order", {k: v for k, v in before_cap.items() if k != "series"}, {k: v for k, v in orderinfo.items() if k != "claws_after_order"})
        orderinfo["after_order_before_cap"] = {k: v for k, v in before_cap.items() if k != "series"}
        after = before_cap
    elif a.order > 0:
        # 名前の付いた美術の誘導 pl31_white_order（135「上側から船側へ広がる」）：前の側（F ≥ 1）の頂点の T_white の値の集まりはそのままに、
        # 並び替えの鍵 = order·順位(F) + order_h·順位(行の頂の高さの高い順) + 残り·順位(元の T) の順に、早い時刻から割り当て直す
        # （頂 F = 1 → 唇の先 F = 2 → 下面・管。白は頂の高い所の小さな塊から始まり、頂に沿って横へ・前の面を下へ広がる）。
        # 背の側（F < 1）は元のまま（頂から背の下へ広がる）。白の範囲の外の頂点も同じ規則で付け替える（境の補いの段を作らない）
        fr_ = (A["F"] >= 1.0) & fin & body
        ii = np.nonzero(fr_)[0]
        rF = np.argsort(np.argsort(A["F"][ii])) / max(len(ii) - 1, 1)
        rT = np.argsort(np.argsort(TW0[ii])) / max(len(ii) - 1, 1)
        rH = np.argsort(np.argsort(-A["hrow"][ii])) / max(len(ii) - 1, 1)   # 頂の高い行から
        keyo = a.order * rF + a.order_h * rH + max(1 - a.order - a.order_h, 0.0) * rT
        newT = np.sort(TW0[ii])[np.argsort(np.argsort(keyo))]
        TWo = TW0.copy(); TWo[ii] = newT
        orderinfo = dict(order=a.order, order_h=a.order_h, vertices=int(len(ii)), tau_shift_abs_median_s=float(np.median(np.abs(newT - TW0[ii]))),
                         tau_shift_abs_max_s=float(np.abs(newT - TW0[ii]).max()))
        TW = TWo
        before_cap, _, _, Ts_sorted0, wcum0, _ = measure(TW, "pl31_white_order の後（cap の前）")
        print("order", {k: v for k, v in before_cap.items() if k != "series"}, orderinfo)
        orderinfo["after_order_before_cap"] = {k: v for k, v in before_cap.items() if k != "series"}
        after = before_cap
    TWbase = TW
    if a.rate_cap > 0 and max(after["surface_fraction_max_increment"], after["world_fraction_max_increment"]) > 0.02:
        TW, capinfo = rate_cap(Ts_sorted0, wcum0, TWbase, fin, frames_t, frames_tau, wt, wtau, a.rate_cap)
        after, Tsamp1, final1, _, _, _ = measure(TW, "pl31_white_rate_cap の後")
        # 世界の面積の読みでまだ越えるなら、cap を下げてもう一度（最大 3 回）
        cap = a.rate_cap
        tries = 0
        while after["world_fraction_max_increment"] > 0.02 and tries < 3:
            cap *= 0.85
            tries += 1
            TW, capinfo = rate_cap(Ts_sorted0, wcum0, TWbase, fin, frames_t, frames_tau, wt, wtau, cap)
            after, Tsamp1, final1, _, _, _ = measure(TW, "pl31_white_rate_cap の後（cap %.4f）" % cap)
        capinfo["tries_extra"] = tries
        print("after", {k: v for k, v in after.items() if k != "series"}, capinfo)
    else:
        Tsamp1, final1 = sample_T(TW, Ti, Bi), None
        final1 = zs & np.isfinite(Tsamp1) & (Tsamp1 <= 0.0)
    if (capinfo is None) and (orderinfo is not None):
        TW.astype("<f4").tofile(a.out + "/pl31_twhite_r32f.bin")
    final = final1
    TsF = Tsamp1
    if orderinfo is not None or capinfo is not None:
        TW.astype("<f4").tofile(a.out + "/pl31_twhite_r32f.bin")
        hp = a.out + "/hero_pkg"
        os.makedirs(hp, exist_ok=True)
        for fn in (pk.meta["pos_file"], pk.meta["pos_lo_file"]):
            dst = os.path.join(hp, fn)
            if not os.path.exists(dst):
                try:
                    os.link(os.path.join(PKG, fn), dst)
                except OSError:
                    shutil.copyfile(os.path.join(PKG, fn), dst)
        shutil.copyfile(a.out + "/pl31_twhite_r32f.bin", os.path.join(hp, "ds27_twhite_r32f.bin"))
        meta = json.load(open(os.path.join(PKG, "ds27_keypose.json"), encoding="utf-8"))
        meta["twhite_sha256"] = sha(os.path.join(hp, "ds27_twhite_r32f.bin"))
        meta["number"] = "仕上げ31（G_p28rec の T_white に %s を掛けた写し）" % "・".join(
            [x for x, on in (("pl31_white_order（%s）" % a.order_mode, orderinfo is not None), ("pl31_white_claw_pin", pininfo is not None),
                             ("pl31_white_rate_cap", capinfo is not None)) if on])
        json.dump(meta, open(os.path.join(hp, "ds27_keypose.json"), "w", encoding="utf-8"), ensure_ascii=False)
        twinfo = dict(file="pl31_twhite_r32f.bin", sha256=sha(a.out + "/pl31_twhite_r32f.bin"), hero_pkg=hp)
    else:
        twinfo = None

    # ---- 135：前の白（F ≥ 1）を頂（F = 1）から唇の先・管の側（船の側）へ 10 区間（面積の等分）に分け、到着の時刻の中央値と順位相関
    def spread(mask, key, nb=10):
        m = mask & np.isfinite(TsF)
        kk = key[m]; tt = W.t_of_tau(TsF[m], wt, wtau); ww = wA[m]
        o = np.argsort(kk)
        cw = np.cumsum(ww[o]) / ww.sum()
        bins = np.minimum((cw * nb).astype(int), nb - 1)
        med = [float(np.median(tt[o][bins == b])) for b in range(nb)]
        k_med = [float(np.median(kk[o][bins == b])) for b in range(nb)]
        rk = np.argsort(np.argsort(med))
        rho = float(np.corrcoef(np.arange(nb), rk)[0, 1])
        # 標本ごとの順位相関（面積の重みなし）
        r1 = np.argsort(np.argsort(kk)); r2 = np.argsort(np.argsort(tt))
        rho_all = float(np.corrcoef(r1, r2)[0, 1])
        return dict(bins_key_median=k_med, bins_t_median=med, spearman_bins=rho, spearman_samples=rho_all, samples=int(m.sum()))
    Fs = (A["F"][Ti] * Bi).sum(1)
    hs = (A["hrel"][Ti] * Bi).sum(1)
    res135 = dict(rule_ja="135 上側から船側へ広がる：前の白（F ≥ 1）を流れの座標 F（頂 1 → 唇の先 2 → 管の天井 3 → 前面の下 4）の面積の等分 10 区間に分け、"
                           "区間ごとの到着の時刻の中央値の並び（順位相関）。背の白（F < 1）は頂から背の下へ（1 − hrel の順）を記録",
                  front=spread(final & (Fs >= 1.0), Fs), back=spread(final & (Fs < 1.0), 1.0 - hs))
    print("135", res135["front"]["spearman_bins"], res135["back"]["spearman_bins"])

    # ---- 177：同じ縞が同じ水面とともに上がる。藍の胴の溝（行の c の上に並ぶ。面の座標は頂点に付いて動かない）25 本を選び、
    # その頂点の平均の高さを 30 Hz で追う
    lam = float(prm["_GrooveLambda"][0])
    cvals = np.arange(-24, 1) * lam * 1.0 + 0.0
    track = []
    nonwhite_v = ~zone_v & body & (A["hrow"] > 0.08)
    sel_all = []
    for cv in cvals:
        cr = np.unique(np.round(A["c"], 4))
        cn = cr[np.argmin(np.abs(cr - cv))]
        s_ = np.nonzero(nonwhite_v & (np.abs(A["c"] - cn) < 0.05) & (A["F"] > 1.5) & (A["F"] < 4.5))[0]
        sel_all.append(s_)
    heights = np.zeros((K, len(cvals)))
    for k in range(K):
        Pk = pk.eval(float(frames_tau[k]))
        o = pk.origin(float(frames_tau[k]))[0]
        for j, s_ in enumerate(sel_all):
            if len(s_):
                heights[k, j] = float((Pk[s_, 1] + o[1]).mean())
    k2 = int(round(2.0 * FPS)); ks = int(round(T_STAR * FPS))
    dh = np.diff(heights[:ks + 1], axis=0)
    res177 = dict(rule_ja="177 同じ縞が同じ水面とともに上がる：材質の溝は面の座標（t* の c）の上に並び、面の座標は頂点の値（時刻で変わらない）なので、"
                           "同じ溝はいつも同じ頂点の上にある。藍の胴（白の範囲の外、管の中 F 1.5〜4.5）の c = −22.8〜0 m の 25 本の溝の頂点の平均の高さを追う",
                  grooves=len(cvals), vertices_per_groove=[int(len(s_)) for s_ in sel_all], c_m=cvals.round(3).tolist(),
                  height_t2_m=heights[k2].round(3).tolist(), height_tstar_m=heights[ks].round(3).tolist(),
                  rise_m=(heights[ks] - heights[k2]).round(3).tolist(),
                  all_rise=bool((heights[ks] - heights[k2] > 0).all()),
                  max_drop_per_frame_m=float(-dh.min()), frames_dropping=int((dh < -1e-6).sum()))
    print("177", res177["all_rise"], min(res177["rise_m"]), res177["max_drop_per_frame_m"])

    # ---- 発生の表（白の範囲の頂点で T_white が有限、本体の列）
    onset = zone_v & body & (TW < NEVER)
    region = np.zeros(n, np.int8)
    region[A["F"] >= 1.0] = 1
    region[A["F"] >= 2.0] = 2
    region[A["F"] >= 3.0] = 3
    reg_names = ["背（F < 1）", "唇の上面（頂 → 唇の先、F 1〜2）", "唇の下面・管の天井（F 2〜3）", "管の奥・前面（F ≥ 3）"]
    idx = np.where(onset)[0]
    idx = idx[np.argsort(TW[idx], kind="stable")]
    tw_on = TW[idx]
    t_on = W.t_of_tau(tw_on, wt, wtau)
    pos = np.zeros((len(idx), 3)); vel = np.zeros((len(idx), 3))
    key = np.round(tw_on, 3)
    uk, inv = np.unique(key, return_inverse=True)
    for g, tv in enumerate(uk):
        s_ = np.where(inv == g)[0]
        p_, v_ = pk.eval(float(tv), idx[s_], vel=True)
        pos[s_] = p_ + pk.origin(float(tv))[0]
        vel[s_] = v_ + pk.dorigin(float(tv))[0]
    nrm = A["n"]
    rec = np.zeros((len(idx), 15), dtype="<f4")
    rec[:, 0] = rows[idx]; rec[:, 1] = cols[idx]; rec[:, 2] = tw_on; rec[:, 3] = t_on
    rec[:, 4:7] = pos; rec[:, 7:10] = vel; rec[:, 10] = region[idx]; rec[:, 11:14] = nrm[idx]; rec[:, 14] = idx
    rec.tofile(a.out + "/pl31_white_onset_f32.bin")
    spd = np.linalg.norm(vel, axis=1)
    reg_sum = {}
    for r_ in range(4):
        s_ = region[idx] == r_
        if s_.any():
            reg_sum[str(r_)] = dict(name_ja=reg_names[r_], vertices=int(s_.sum()), t_first=float(t_on[s_].min()), t_last=float(t_on[s_].max()),
                                    speed_median_mps=float(np.median(spd[s_])))
    onset_meta = dict(schema="GreatWave.DS31.white_onset/1", number_ja="仕上げ31：白の出現（T_white）を発生位置と時刻にした表（G_p28rec・PL29 の白の範囲）",
                      file="pl31_white_onset_f32.bin", sha256=sha(a.out + "/pl31_white_onset_f32.bin"), records=int(len(idx)),
                      fields=["row", "col", "tau_white", "t_white", "x", "y", "z", "vx", "vy", "vz", "region", "nx", "ny", "nz", "vertex"],
                      layout_ja="float32 リトルエンディアン、記録 × 15。T_white の早い順。位置はワールド（m）、速度はワールドの m/s（τ の秒あたり、波の枠の動きを含む）、"
                                "法線は t* の面の法線（面の座標 C）。region：0 背・1 唇の上面・2 唇の下面と管の天井・3 管の奥と前面",
                      selection_ja="材質 PL29 の白の範囲（頂点の面の座標で zZone > 0）、T_white が有限、本体の列 18〜394。投影の色面は使わない",
                      regions=reg_sum,
                      inputs=dict(package=PKG, pos_sha256=pk.meta["pos_sha256"], twhite_sha256=(twinfo or {}).get("sha256", pk.meta["twhite_sha256"]),
                                  warp=WARP, warp_sha256=sha(WARP), attr=Z.ATTR, attr_sha256=sha(Z.ATTR), params=Z.PARAMS, params_sha256=sha(Z.PARAMS)))
    json.dump(onset_meta, open(a.out + "/pl31_white_onset.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 放出点の候補の旗（行 × 列）：白の範囲・T_white
    np.save(a.out + "/pl31_zone_vertex.npy", zone_v)
    np.save(a.out + "/pl31_twhite_used.npy", TW.astype(np.float32))
    log["seconds"] = time.time() - t0
    claws_after = claw_lag(TW, roots, wt, wtau)
    print("claws after", {k: v for k, v in claws_after.items() if k != "worst"})
    claws = dict(rule_ja="設計33 の爪（場面で再生する焼き込み）のうち根元が白の範囲にあるもの。根元の格子の 4 頂点がそろって白くなる時刻（t）が、"
                         "最初に見えるコマの時刻より半コマ以上遅いものを「白くなる前に伸び始める」と数える", source=claw_src,
                 before=claws_before, after=claws_after)
    out = dict(schema="GreatWave.Polish31.white_numpy/1", log=log, b102_before=before, b102_after=after, pl31_white_order=orderinfo,
               pl31_white_claw_pin=pininfo, claws_136=claws, pl31_white_rate_cap=capinfo, twhite_out=twinfo,
               b135=res135, b177=res177, onset={k: onset_meta[k] for k in ("records", "regions", "selection_ja", "sha256")},
               inputs=onset_meta["inputs"], python=sys.version.split()[0], numpy=np.__version__,
               code_sha256={os.path.basename(__file__): sha(os.path.abspath(__file__)), "pl31_zone.py": sha(os.path.join(HERE, "pl31_zone.py"))})
    json.dump(out, open(a.out + "/pl31_white_numpy.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(dict(log=log, order=orderinfo, cap=capinfo, tw=twinfo, regions=reg_sum), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
