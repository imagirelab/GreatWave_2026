# -*- coding: utf-8 -*-
"""番号27：空のドーム（世界の仰角によるグラデーション）を原画の空から当てはめる。

使い方（リポジトリ根で）: py -3.10 Tools/GWContext/af27_sky.py

考え方
- 色はカメラから見た方向の世界の仰角 el（と方位角 az）だけで決める。画面座標は使わない（どの視点・両眼でも同じ空になる）。
- 原画の暗い空の上端（番号23の真値 213「明暗の移行線」＝平滑 L* が L_mid を下回る境）は方位によって仰角 2.6〜3.6° と揺れるので、
  移行の仰角 θt(az) を世界の方位角の関数として持つ（世界に固定した曲線。画面空間ではない）。
- 帯の近くでは仰角を e' = el − w(el)·(θt(az) − θ0) へ付け替え、1 本の色の表（LUT、e' の関数）で色を決める。
  w は el ≤ θ0 + W_FULL で 1、θ0 + W_ZERO で 0 になる直線。上空は仰角だけで決まる。
- 色の表は原画の空の画素（題箋・落款の塗りを除く）を e' で 0.05° ごとに分けた Lab の中央値。帯の中は L* を単調にし、
  上空は広く平滑して雲の斑を消す。L* が L_mid になる e' を θ0 に合わせる。
出力: Tools/GWContext/sky_dome.json（Unity の AF27 が読む）、Unity/Build/ArtFirst/27/sky/（確認図と予測評価）。
"""
import math
import os
import sys

import cv2
import numpy as np

import af27common as C
from af27common import T

sys.path.insert(0, C.PT_DIR)
import evaluate as E  # noqa: E402

AZ0, AZ1, AZ_STEP = -60.0, 60.0, 0.05      # θt(az) の表
E0, E1, E_STEP = -2.0, 40.0, 0.02          # 色の表（e'）
AZ_BIN = 0.2                                 # 移行線の方位の区切り（度、表示で約 8 px）
AZ_SMOOTH = 0.15                             # θt の平滑（度）
AZ_RAMP = 10.0                               # 原画の方位の外で θ0 へ戻す幅（度）
W_FULL, W_ZERO = 1.5, 4.5                    # 付け替えの重み（θ0 からの仰角差、度）
BIN_E = 0.05
SMOOTH_BAND = 0.06                           # 帯（e' < θ0+2.5°）の平滑（度）
SMOOTH_UPPER = 1.2                           # 上空の平滑（度）


def gauss1d(y, sigma_samples):
    if sigma_samples <= 0:
        return y
    r = int(math.ceil(4 * sigma_samples))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_samples) ** 2)
    k /= k.sum()
    yp = np.concatenate([np.repeat(y[:1], r, 0), y, np.repeat(y[-1:], r, 0)], 0)
    if y.ndim == 1:
        return np.convolve(yp, k, "valid")
    return np.stack([np.convolve(yp[:, c], k, "valid") for c in range(y.shape[1])], -1)


def lab_to_linear(lab):
    lab = np.asarray(lab, np.float64)
    fy = (lab[..., 0] + 16.0) / 116.0
    fx = fy + lab[..., 1] / 500.0
    fz = fy - lab[..., 2] / 200.0
    e, k = 216.0 / 24389.0, 24389.0 / 27.0
    finv = lambda f: np.where(f ** 3 > e, f ** 3, (116.0 * f - 16.0) / k)
    xyz = np.stack([finv(fx), np.where(lab[..., 0] > k * e, fy ** 3, lab[..., 0] / k), finv(fz)], -1) * T._WHITE_D65
    return np.clip(xyz @ np.linalg.inv(T._M_RGB2XYZ).T, 0.0, 1.0)


def linear_to_srgb8(lin):
    lin = np.clip(lin, 0, 1)
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(np.round(c * 255.0), 0, 255).astype(np.uint8)


class Dome:
    """sky_dome.json の内容から方向ごとの色を計算する（シェーダーと同じ式。numpy の予測用）。"""

    def __init__(self, J):
        self.J = J
        a = J["theta_t"]
        self.az = a["az0"] + a["step"] * np.arange(len(a["values_deg"]))
        self.th = np.array(a["values_deg"])
        g = J["gradient"]
        self.e = g["e0"] + g["step"] * np.arange(len(g["linear_rgb"]))
        self.lin = np.array(g["linear_rgb"])
        self.theta0 = J["theta0_deg"]
        self.wf, self.wz = J["w_full_deg"], J["w_zero_deg"]

    def eprime(self, el, az):
        th = np.interp(az, self.az, self.th)
        w = np.clip((self.theta0 + self.wz - el) / (self.wz - self.wf), 0.0, 1.0)
        return el - w * (th - self.theta0)

    def linear(self, el, az):
        ep = self.eprime(el, az)
        return np.stack([np.interp(ep, self.e, self.lin[:, c]) for c in range(3)], -1)


def main():
    out_dir = os.path.join(C.BUILD, "sky")
    os.makedirs(out_dir, exist_ok=True)
    tr = E.Truth()
    spec, fm = tr.spec, tr.fmap
    cam = C.Cam(spec)
    yy, xx = np.mgrid[0:C.H, 0:C.W].astype(np.float64)
    EL, AZ = C.el_az(cam.ray(xx, yy))
    sky = tr.cov["sky_claws"] > 0.5
    P = tr.regions["polygons_display"]
    excl = T.poly_mask((C.H, C.W), P["sky_fill_cartouche"]) | T.poly_mask((C.H, C.W), P["sky_fill_signature"])
    scored = (xx >= fm.x0) & (xx <= fm.x1)
    use = sky & ~excl & scored
    lab = tr.lab_disp
    L_mid = tr.L_mid

    # ---- 1) 移行線の仰角 θt(az)：番号23の真値 213 の点（暗い空の境界のうち空境界から 1 px より離れた点）
    F = tr.fam["sky_dark"]
    tp = F["pts"][F["sel"]["sky_transition"]]
    tel, taz = C.el_az(cam.ray(tp[:, 0], tp[:, 1]))
    # 暗い空の境界がくぼむ所（飛沫の白点が L* の平滑に入る所）は、仰角の最小（上側）を使い、くぼみは追わない。
    edges = np.arange(taz.min() - 1e-9, taz.max() + AZ_BIN, AZ_BIN)
    bc, bv = [], []
    for a0 in edges[:-1]:
        m = (taz >= a0) & (taz < a0 + AZ_BIN)
        if m.sum() >= 2:
            bc.append(float(np.mean(taz[m])))
            bv.append(float(np.max(tel[m])))  # 上側の縁（くぼみを除く）
    bc, bv = np.array(bc), np.array(bv)
    theta0 = float(np.median(bv))
    azg = AZ0 + AZ_STEP * np.arange(int(round((AZ1 - AZ0) / AZ_STEP)) + 1)
    th = np.interp(azg, bc, bv)
    th = gauss1d(th, AZ_SMOOTH / AZ_STEP)
    lo, hi = bc.min(), bc.max()
    ramp = np.clip(np.maximum(lo - azg, azg - hi) / AZ_RAMP, 0.0, 1.0)
    ramp = 0.5 - 0.5 * np.cos(np.pi * ramp)
    th = th * (1 - ramp) + theta0 * ramp

    def eprime(el, az):
        t = np.interp(az, azg, th)
        w = np.clip((theta0 + W_ZERO - el) / (W_ZERO - W_FULL), 0.0, 1.0)
        return el - w * (t - theta0)

    # ---- 2) 色の表（e' ごとの Lab 中央値）
    EP = eprime(EL, AZ)
    eg = E0 + E_STEP * np.arange(int(round((E1 - E0) / E_STEP)) + 1)
    bins = np.arange(E0, E1 + BIN_E, BIN_E)
    idx = np.digitize(EP[use], bins) - 1
    labu = lab[use]
    med = np.full((len(bins) - 1, 3), np.nan)
    cnt = np.bincount(np.clip(idx, 0, len(bins) - 2), minlength=len(bins) - 1)
    order = np.argsort(idx, kind="stable")
    si = idx[order]
    sl = labu[order]
    starts = np.searchsorted(si, np.arange(len(bins) - 1))
    ends = np.searchsorted(si, np.arange(len(bins) - 1), side="right")
    for b in range(len(bins) - 1):
        if ends[b] - starts[b] >= 30:
            med[b] = np.median(sl[starts[b]:ends[b]], axis=0)
    bcen = bins[:-1] + BIN_E / 2
    ok = ~np.isnan(med[:, 0])
    e_lo_data, e_hi_data = float(bcen[ok].min()), float(bcen[ok].max())
    prof = np.stack([np.interp(eg, bcen[ok], med[ok, c]) for c in range(3)], -1)
    band = gauss1d(prof, SMOOTH_BAND / E_STEP)
    upper = gauss1d(prof, SMOOTH_UPPER / E_STEP)
    # 帯の L* を単調（上へ明るく）にする：θ0+2.5° まで累積最大
    band_end = theta0 + 2.5
    ib = eg <= band_end
    band[ib, 0] = np.maximum.accumulate(band[ib, 0])
    wb = np.clip((eg - (theta0 + 2.0)) / 2.0, 0.0, 1.0)
    wb = 0.5 - 0.5 * np.cos(np.pi * wb)
    lut = band * (1 - wb[:, None]) + upper * wb[:, None]
    # L* = L_mid となる e' を θ0 に合わせる（帯の部分だけ平行移動）
    j = np.nonzero((lut[:-1, 0] < L_mid) & (lut[1:, 0] >= L_mid))[0]
    j = j[np.argmin(np.abs(eg[j] - theta0))]
    e_mid = eg[j] + (L_mid - lut[j, 0]) / (lut[j + 1, 0] - lut[j, 0]) * E_STEP
    shift = theta0 - e_mid
    band_s = np.stack([np.interp(eg - shift, eg, band[:, c]) for c in range(3)], -1)
    lut = band_s * (1 - wb[:, None]) + upper * wb[:, None]
    j = np.nonzero((lut[:-1, 0] < L_mid) & (lut[1:, 0] >= L_mid))[0]
    j = j[np.argmin(np.abs(eg[j] - theta0))]
    e_mid2 = eg[j] + (L_mid - lut[j, 0]) / (lut[j + 1, 0] - lut[j, 0]) * E_STEP
    lin = lab_to_linear(lut)

    J = {
        "schema": "GreatWave.AF27.sky_dome/1",
        "number": "27",
        "truth_version": spec["version"],
        "truth_manifest_sha256": T.sha256_file(os.path.join(T.TARGET_DIR, "truth_manifest.json")),
        "description_ja": "世界の仰角によるグラデーションの空。方向 d（カメラから見た向き）の仰角 el = asin(d.y)、方位角 az = atan2(d.x, d.z)（度）。"
                          "e' = el − w(el)·(θt(az) − θ0)、w = clamp((θ0 + w_zero − el)/(w_zero − w_full), 0, 1)。色 = gradient(e')（線形 RGB、線形補間）。"
                          "画面座標は使わない。",
        "theta0_deg": round(theta0, 6),
        "w_full_deg": W_FULL, "w_zero_deg": W_ZERO,
        "theta_t": {"az0": AZ0, "step": AZ_STEP, "values_deg": [round(float(v), 6) for v in th],
                    "source_ja": "番号23 真値の 213（sky_transition）の点を PaintingCam の方向へ戻し、方位 %.2f° ごとに仰角の最大（上側の縁）を取り、"
                                 "σ %.2f° で平滑した。原画の方位の外（%.2f〜%.2f° の外）は %.0f° かけて θ0 へ戻す。" % (AZ_BIN, AZ_SMOOTH, lo, hi, AZ_RAMP),
                    "data_az_range_deg": [round(lo, 4), round(hi, 4)]},
        "gradient": {"e0": E0, "step": E_STEP, "linear_rgb": [[round(float(v), 7) for v in c] for c in lin],
                     "lab": [[round(float(v), 4) for v in c] for c in lut],
                     "source_ja": "原画の空（番号23 sky_claws、題箋・落款の塗りを除く、採点列）の画素を e' で %.2f° ごとに分けた Lab 中央値。"
                                  "帯（e' < θ0+2.5°）は σ %.2f° で平滑し L* を単調にした。上空は σ %.2f° で平滑した。θ0+2〜4° で混ぜる。"
                                  "L* = L_mid の e' を θ0 に合わせるため帯の部分を %.4f° ずらした。データのある範囲は e' %.2f〜%.2f°（外は端の値）。"
                                  % (BIN_E, SMOOTH_BAND, SMOOTH_UPPER, shift, e_lo_data, e_hi_data)},
        "L_mid": L_mid,
        "e_prime_at_L_mid_deg": round(float(e_mid2), 6),
        "band_shift_deg": round(float(shift), 6),
    }
    C.save_json(C.SKY_JSON, J)

    # ---- 3) 予測：原画の空の画素をドームの色で置き換え、番号23の評価器（真値の領域）で測る
    D = Dome(J)
    rgb = tr.disp_rgb.copy()
    dome_rgb = linear_to_srgb8(D.linear(EL, AZ))
    rgb[sky] = dome_rgb[sky]
    reg = E.truth_regs(tr)
    M, det, rp = E.evaluate_core(tr, rgb, reg, versions=("envelope",))
    pred = {}
    for k in ("76", "212", "213"):
        pred[k] = [{kk: m.get(kk) for kk in ("target", "value_max_px", "p95_px", "value", "verdict", "worst_display_xy")} for m in M["items"][k]["measures"]]
    band_steps = band_step_metrics(dome_rgb, sky)
    C.save_json(os.path.join(out_dir, "sky_prediction.json"), {
        "note_ja": "予測（numpy）。原画の空の画素だけをドームの色に置き換え、遮る物（波・船・富士）は真値のままにして評価器にかけた。Unity の描画ではない。",
        "items": pred, "band_steps": band_steps, "theta0_deg": theta0, "band_shift_deg": shift})
    T.imwrite(os.path.join(out_dir, "sky_prediction.png"), rgb)
    E.overlay_png(tr, rgb, det, rp, os.path.join(out_dir, "sky_prediction_overlay.png"), "27 sky dome prediction (numpy)", ("envelope",))
    profile_png(os.path.join(out_dir, "sky_profile.png"), eg, prof, lut, bcen, med, theta0, L_mid)
    for k, v in pred.items():
        print(k, v)
    print("band_steps", band_steps)
    print("theta0 %.4f shift %.4f e_mid2 %.4f" % (theta0, shift, e_mid2))


def band_step_metrics(rgb, sky):
    """空の中で縦に隣り合う画素の ΔE00 の最大と、L* の縦の差の符号反転（段差）の数。"""
    lab = T.srgb8_to_lab(rgb)
    m = T.erode(sky, 2)
    both = m[1:, :] & m[:-1, :]
    d = T.ciede2000(lab[1:, :][both], lab[:-1, :][both])
    return {"adjacent_rows_dE00_max": float(d.max()), "adjacent_rows_dE00_p99": float(np.percentile(d, 99)), "n_pairs": int(both.sum())}


def profile_png(path, eg, prof, lut, bcen, med, theta0, L_mid):
    Hh, Ww = 540, 960
    img = np.full((Hh, Ww, 3), 255, np.uint8)
    e_lo, e_hi = -0.5, 20.0

    def X(e):
        return (60 + (np.asarray(e) - e_lo) / (e_hi - e_lo) * (Ww - 90)).astype(int)

    def Y(v, lo, hi, top, bot):
        return (bot - (np.asarray(v) - lo) / (hi - lo) * (bot - top)).astype(int)
    for (c, lo, hi, top, bot, name) in ((0, 40, 100, 30, 300, "L*"), (2, 0, 25, 330, 510, "b*")):
        cv2.rectangle(img, (60, top), (Ww - 30, bot), (200, 200, 200), 1)
        cv2.putText(img, name, (10, (top + bot) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        ok = ~np.isnan(med[:, c])
        sel = ok & (bcen >= e_lo) & (bcen <= e_hi)
        for e, v in zip(bcen[sel], med[sel, c]):
            cv2.circle(img, (int(X(e)), int(Y(v, lo, hi, top, bot))), 1, (150, 150, 150), -1)
        s = (eg >= e_lo) & (eg <= e_hi)
        pts = np.stack([X(eg[s]), Y(lut[s, c], lo, hi, top, bot)], -1).astype(np.int32)
        cv2.polylines(img, [pts], False, (200, 40, 40), 2)
    cv2.line(img, (int(X(theta0)), 30), (int(X(theta0)), 510), (40, 160, 40), 1)
    yl = int(Y(L_mid, 40, 100, 30, 300))
    cv2.line(img, (60, yl), (Ww - 30, yl), (40, 160, 40), 1)
    for e in range(0, 21, 2):
        cv2.putText(img, str(e), (int(X(e)) - 5, 528), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.putText(img, "e' (deg)  gray: painting median per 0.05deg  red: dome LUT  green: theta0 / L_mid", (70, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    T.imwrite(path, img)


if __name__ == "__main__":
    main()
