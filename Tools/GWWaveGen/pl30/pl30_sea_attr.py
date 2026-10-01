# -*- coding: utf-8 -*-
"""仕上げ30：周りの海（near・far）の頂点ごとの面の座標（視点によらない立体の材質 PL30 Ukiyoe Sea の入力）を作る。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_attr.py --sea Unity/Build/Polish/30/sea [--params Tools/GWWaveGen/pl30/pl30_params.json]
出力（<sea>/near/pl30_sea_attr_f32.bin・<sea>/far/pl30_sea_attr_f32.bin。頂点 × 20 の float32、頂点の順は DS27 の格子（行 × 列））:
    UV3 = (qR, uR, hR, wR)      右の高い波と肩の稜の「稜の系」：稜に垂直な符号付きの距離 m（+ が前＝a の増える側）、稜に沿う弧長 m、その所の頂の t* の高さ m、系に属する重み 0〜1
    UV4 = (xS, yS, hfS, wS)     手前の小波の系：頂からの楕円の正規化の座標（a の向き ÷ 半径、c の向き ÷ 横の半径。角度と距離は材質の中で求める）、t* の高さ ÷ 頂の高さ、重み
    UV5 = (t* の法線 xyz, a*)    a* は波の枠の a（進む向きの座標 m。遠い海の溝を波峰線に平行に並べる）
    UV6 = (s, along, rimq, tw)  s 継ぎ目からの線分に沿う t* の距離 m、along 海の溝の沿う座標 m（輪を一周すると _SeaAlongPeriod の整数倍＝継ぎ目なし）、
                                rimq 谷の縁（t* の帯の頂）からの符号付きの距離 m（− が谷の側）、tw 谷の縁の段を付ける重み 0〜1
    UV7 = (hfR, mixR, boatw, wsh) hfR t* の高さ ÷ hR、mixR 前と背の白の閾値の混ぜ（0 背 → 1 前。二つの稜のそれぞれの前の側の量の大きい方）、
                                boatw 座席の船の支えの当て布の重み、wsh 肩の稜の重み（稜の系の混ぜの重み × wR）
修正01（自己評審の must-fix）：
    ・作る部の版（12 個）は、右の高い波と肩の稜のうち「近い方の稜」の座標を頂点ごとに選び、肩の稜の弧長に +1000 m を足していたので、
      近い稜が替わる所で u が約 1000 m、q が最大 285 m 跳んだ（材質の溝・房・切れの継ぎ目の線）。また小波の角度の座標は頂の後ろで 2π 跳び、
      海の溝のうねりと切れも同じ u を使っていた。
    ・この版では、稜の系の座標を「形の断面と同じ連続な場」（右の高い波：a − a_crest(c) を稜の傾きで割った距離と、c だけの関数の弧長。
      肩の稜：両端を直線で延ばした稜への距離と弧長）から作り、二つの稜の重みで滑らかに混ぜる（右と肩の t* の高さの差 ±blend_m で混ぜる）。
      肩の稜の弧長は合流の所で右の高い波の弧長に一致させる。小波は角度ではなく楕円の座標を渡す（角度は断片の中で求めるので頂の後ろの切れ目がない）。
      海の溝の沿う座標は、行ごとの弧長の割合 × 一周の長さ（_SeaAlongPeriod の整数倍）にした（行 0 の最後の列 = 写しの列で一周の長さ）。
原画カメラ・原画の色区は読まない（Q28）。参照モデルは読まない。
"""
import argparse
import os
import sys

import numpy as np
from scipy.ndimage import gaussian_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl30_sea as S  # noqa: E402
from pl30_checks import Pkg, vnormals  # noqa: E402

REPO = S.REPO
NF = 20


def ridge_attrs(feat, a, c, AP):
    """稜の系（右の高い波＋肩の稜）の連続な座標。"""
    qr = feat.sample_clamped(a, c, "aR_q"); ur = feat.sample_clamped(a, c, "aR_u"); hr = feat.sample_clamped(a, c, "aR_h")
    Fr = feat.sample(a, c, "right_only") if "right_only" in feat.r else feat.sample(a, c, "right")
    Fall = feat.sample(a, c, "right")
    if "aS_q" in feat.r:
        qs = feat.sample_clamped(a, c, "aS_q"); us = feat.sample_clamped(a, c, "aS_u"); hs = feat.sample_clamped(a, c, "aS_h")
        Fs = feat.sample(a, c, "shoulder")
        Ls = feat.attr_shoulder["L"]
        cg, ug = feat.right_u_of_c
        cJ = float(feat.shoulder_path["c"][-1])
        uJ = float(np.interp(cJ, cg, ug))
        us2 = uJ - (Ls - us)                       # 合流の所で右の高い波の弧長と同じ
        Ws = S.smoothstep((Fs - Fr) / float(AP["ridge_blend_m"]) + 0.5)
        q = (1 - Ws) * qr + Ws * qs
        u = (1 - Ws) * ur + Ws * us2
        h = (1 - Ws) * hr + Ws * hs
        # 前と背の白の閾値の混ぜ（0 背 → 1 前）：二つの稜のそれぞれの前の側の量の、その稜がある所での大きい方
        # （q そのものを混ぜると、合流の所で肩の稜の頂が右の高い波の背の q を受けて背の閾値になり、白が切れた）
        pr = S.smoothstep((Fr / np.maximum(hr, 0.5) - 0.5) / 0.3)
        ps = S.smoothstep((Fs / np.maximum(hs, 0.5) - 0.5) / 0.3)
        mix = np.maximum(S.smoothstep((qr + 1.5) / 3.0) * pr, S.smoothstep((qs + 1.5) / 3.0) * ps)
    else:
        q, u, h, Ws = qr, ur, hr, np.zeros_like(qr)
        mix = S.smoothstep((qr + 1.5) / 3.0)
    # 頂の t* の高さは谷の続き（ds30_trough_continue、負）を含めた高さにする（肩の稜の上り口は谷の続きの上を通り、頂が最大 1.9 m 低い。
    # 含めないと今の高さの比が 0.82〜0.92 に止まり、白が切れた）
    tr = feat.sample(a, c, "trough")
    h = np.maximum(h + tr, 0.5)
    w = S.smoothstep((Fall - 0.15) / 0.6) * S.smoothstep((h - 0.8) / 1.2)
    hf = np.where(h > 1e-3, (Fall + tr) / np.maximum(h, 1e-3), 0.0)
    return q, u, h, w, hf, Ws, mix


def small_attrs(feat, a, c):
    sm = feat.small
    Sp = feat.F["ds30_small_wave"]
    da = a - sm["a"]; dc = c - sm["c"]
    xs = np.where(da < 0, da / Sp["radius_back_m"], da / Sp["radius_front_m"])
    ys = dc / Sp["radius_side_m"]
    Fs = feat.sample(a, c, "small")
    hf = Fs / max(sm["h"], 1e-3)
    w = S.smoothstep((Fs - 0.15) / 0.6)
    return xs, ys, hf, w


def sea_along(X, Ltot):
    """行ごとの弧長の割合 × Ltot（列 0 で 0、写しの最後の列で Ltot）。"""
    seg = np.linalg.norm(np.diff(X[..., [0, 2]], axis=1), axis=-1)       # (R, C−1)
    cum = np.concatenate([np.zeros((X.shape[0], 1)), np.cumsum(seg, axis=1)], axis=1)
    tot = np.maximum(cum[:, -1:], 1e-6)
    return cum / tot * Ltot, cum[:, -1]


def trough_rim_from_package(sd, sn, feat, a, c, AP, kinds):
    """生成器の谷の縁のうねり（pl30_trough_rim。near/pl30_rim.json の列ごとの重み W、頂の距離 s_rim、高さ h）から谷の座標を作る。"""
    rr = S.load_json(os.path.join(sd, "near", "pl30_rim.json"))
    W = np.array(rr["W"] + [rr["W"][0]], np.float64)[: sn.shape[1]]
    s_r = float(rr["s_rim_m"])
    sth = np.array(rr.get("sin_theta", [1.0] * (sn.shape[1] - 1)) + [rr.get("sin_theta", [1.0])[0]], np.float64)[: sn.shape[1]]
    fH = feat.sample(a, c, "right") + feat.sample(a, c, "small")
    bw = feat.sample(a, c, "boat_w")
    rimq = sn * sth[None, :] - s_r                     # 継ぎ目に垂直な距離で測る（生成器と同じ）
    bdk = feat.sample_clamped(a, c, "boat_dk")
    bo = AP.get("tw_boat_off_m", [1.5, 3.0])
    wbo = S.smoothstep((bdk - bo[0]) / (bo[1] - bo[0])) if bo[1] > bo[0] else np.ones_like(bdk)
    twv = W[None, :] * (1.0 - S.smoothstep((rimq - AP["rim_outer_m"]) / 1.0)) * wbo \
        * (1.0 - S.smoothstep((fH - AP["rim_feature_max_m"]) / 0.5))
    hrim = W * float(rr["h_m"])
    return rimq, twv, hrim, dict(rim_cols_w05=int((W > 0.5).sum()), s_rim_m=s_r, h_m=float(rr["h_m"]),
                                 rim_kinds={str(k): int(((W > 0.5) & (kinds[: len(W)] == k)).sum()) for k in np.unique(kinds)},
                                 tw_vertices_05=int((twv > 0.5).sum()))


def trough_rim(Xn, sn, feat, a, c, AP, kinds):
    """（作る部の後の試し。使わない）t* の near の各列で、継ぎ目から上る帯の頂（谷の縁）の位置と高さ。地形の誘導と船の支えの所は除く。"""
    R, C = sn.shape
    srim = np.zeros(C); hrim = np.zeros(C); ok = np.zeros(C)
    fH = feat.sample(a, c, "right") + feat.sample(a, c, "small")
    bw = feat.sample(a, c, "boat_w")
    smax = float(AP["rim_s_max_m"])
    for j in range(C):
        s = sn[:, j]; y = Xn[:, j, 1]
        m = (s > 0.3) & (s < smax)
        if m.sum() < 3:
            continue
        k = np.nonzero(m)[0]
        kk = k[np.argmax(y[k])]
        if kk == k[-1]:
            continue                                   # 帯の中で上り続ける（谷の縁ではない）
        prom = y[kk] - y[0]
        if prom < AP["rim_prom_min_m"]:
            continue
        if fH[kk, j] > AP["rim_feature_max_m"] or bw[: kk + 1, j].max() > 0.02:
            continue
        srim[j] = s[kk]; hrim[j] = y[kk]; ok[j] = S.smoothstep((prom - AP["rim_prom_min_m"]) / AP["rim_prom_full_m"])
    # 列に沿ってならす（重み付き、輪なので wrap）
    sc = float(AP["rim_smooth_cols"])
    wn = gaussian_filter1d(ok, sc, mode="wrap")
    s_s = gaussian_filter1d(ok * srim, sc, mode="wrap") / np.maximum(wn, 1e-6)
    h_s = gaussian_filter1d(ok * hrim, sc, mode="wrap") / np.maximum(wn, 1e-6)
    tw = np.clip(gaussian_filter1d(ok, float(AP["tw_smooth_cols"]), mode="wrap"), 0, 1)
    s_s = np.where(wn > 1e-3, s_s, float(AP["rim_default_s_m"]))
    rimq = sn - s_s[None, :]
    # 谷の帯の重み：縁の内（継ぎ目〜縁）と縁の外の少し（縁の線の外の泡の点のため）。継ぎ目からの帯の外では 0
    twv = tw[None, :] * (1.0 - S.smoothstep((rimq - AP["rim_outer_m"]) / 1.0)) * (1.0 - S.smoothstep(bw / 0.05)) \
        * (1.0 - S.smoothstep((fH - AP["rim_feature_max_m"]) / 0.5))
    return rimq, twv, h_s, dict(rim_cols=int((ok > 0.5).sum()), rim_s_median=float(np.median(srim[ok > 0.5])) if (ok > 0.5).any() else None,
                                rim_h_median=float(np.median(hrim[ok > 0.5])) if (ok > 0.5).any() else None,
                                rim_kinds={str(k): int(((ok > 0.5) & (kinds[:C] == k)).sum()) for k in np.unique(kinds)})


def attrs_for(X, feat, s_ring, along, AP, rim=None):
    t_ax, e_ax = feat.h.t, feat.h.e
    a = X[..., 0] * t_ax[0] + X[..., 2] * t_ax[2]
    c = X[..., 0] * e_ax[0] + X[..., 2] * e_ax[2]
    sh = X.shape[:2]
    qR, uR, hR, wR, hfR, Ws, mixR = ridge_attrs(feat, a, c, AP)
    xS, yS, hfS, wS = small_attrs(feat, a, c)
    n = vnormals(X)
    bw = feat.sample(a, c, "boat_w")
    out = np.zeros(sh + (NF,), np.float32)
    out[..., 0] = qR; out[..., 1] = uR; out[..., 2] = hR; out[..., 3] = wR
    out[..., 4] = xS; out[..., 5] = yS; out[..., 6] = hfS; out[..., 7] = wS
    out[..., 8:11] = n; out[..., 11] = a
    out[..., 12] = s_ring; out[..., 13] = along
    if rim is not None:
        rimq, tw, hrim = rim
        out[..., 14] = rimq; out[..., 15] = tw
    else:
        out[..., 14] = 1e3; out[..., 15] = 0.0
    out[..., 16] = hfR; out[..., 17] = mixR; out[..., 18] = bw
    out[..., 19] = Ws * wR                                                # 肩の稜の重み（材質の頂の泡の線を肩の稜だけにする）
    stats = dict(ridge_vertices_w05=int((wR > 0.5).sum()), small_vertices_w05=int((wS > 0.5).sum()), shoulder_blend_mid=int(((Ws > 0.1) & (Ws < 0.9) & (wR > 0.05)).sum()),
                 hR_max=float(hR.max()), s_max=float(s_ring.max()))
    return out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sea", default="Unity/Build/Polish/30/sea")
    ap.add_argument("--params", default=S.PARAMS)
    args = ap.parse_args()
    P = S.load_json(args.params)
    AP = P["attr"]
    hero = S.Hero(P)
    feat = S.Features(hero, P)
    sd = os.path.join(REPO, args.sea)
    near = Pkg(os.path.join(sd, "near")); far = Pkg(os.path.join(sd, "far"))
    idx = S.load_json(os.path.join(sd, "near", "ds30_ring0_index.json"))
    kinds = np.array([d["ray"] for d in idx["loop"]] + [idx["loop"][0]["ray"]])
    Xn = near.layer(near.L - 1)
    sn = np.concatenate([np.zeros((1, Xn.shape[1])), np.cumsum(np.linalg.norm(np.diff(Xn[..., [0, 2]], axis=0), axis=-1), axis=0)], 0)
    # 海の溝の沿う座標：一周の長さ Ltot（継ぎ目から ref_s の行の一周を、周期の整数倍に丸める）
    _, Lrow = sea_along(Xn, 1.0)
    kref = int(np.argmin(np.abs(np.median(sn, axis=1) - AP["along_ref_s_m"])))
    Lam = float(AP["along_period_m"])
    Ltot = max(1, int(round(Lrow[kref] / Lam))) * Lam
    along_n, _ = sea_along(Xn, Ltot)
    t_ax, e_ax = feat.h.t, feat.h.e
    a_n = Xn[..., 0] * t_ax[0] + Xn[..., 2] * t_ax[2]
    c_n = Xn[..., 0] * e_ax[0] + Xn[..., 2] * e_ax[2]
    rimq, tw, hrim, rim_stats = trough_rim_from_package(sd, sn, feat, a_n, c_n, AP, kinds)
    An, st_n = attrs_for(Xn, feat, sn, along_n, AP, rim=(rimq, tw, hrim))
    Xf = far.layer(far.L - 1)
    fsub = (near.C - 1) // (far.C - 1)
    s_out = sn[-1, 0:near.C:fsub][:far.C]
    sf = s_out[None, :] + np.concatenate([np.zeros((1, Xf.shape[1])), np.cumsum(np.linalg.norm(np.diff(Xf[..., [0, 2]], axis=0), axis=-1), axis=0)], 0)
    along_f, _ = sea_along(Xf, Ltot)
    Af, st_f = attrs_for(Xf, feat, sf, along_f, AP, rim=None)
    rec = {}
    for nm, A_, st in (("near", An, st_n), ("far", Af, st_f)):
        p = os.path.join(sd, nm, "pl30_sea_attr_f32.bin")
        A_.reshape(-1).astype("<f4").tofile(p)
        rec[nm] = dict(path=os.path.relpath(p, REPO).replace("\\", "/"), sha256=S.sha256_file(p), vertices=int(A_.shape[0] * A_.shape[1]), floats_per_vertex=NF, **st)
        print(nm, rec[nm])
    print("rim", rim_stats, "Ltot", Ltot, "ref row", kref, "Lrow ref", float(Lrow[kref]))
    S.save_json(os.path.join(sd, "pl30_sea_attr_log.json"), dict(number="仕上げ30 修正01", floats_per_vertex=NF, along_total_m=Ltot, along_period_m=Lam,
                                                              along_ref_row=kref, rim=rim_stats, attr_params=AP,
                                                              params_sha256=S.sha256_file(args.params),
                                                              code_sha256=S.sha256_file(os.path.abspath(__file__)), files=rec))


if __name__ == "__main__":
    main()
