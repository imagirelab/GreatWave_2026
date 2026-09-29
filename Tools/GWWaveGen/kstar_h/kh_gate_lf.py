# -*- coding: utf-8 -*-
"""原画の関門の「大きな輪郭（large form）」版（進行役の判断 2026-09-28 20:00、Q24_quotes.txt の末尾）。py -3.10

判断の要点：原画の 132（唇の頭）と 72（唇の下と管）には爪のこぶ・切れ込みが細かく入っている。設計28修正01 の本体は
爪のこぶを除いた大きな輪郭（原画の線を幅 約 30〜40 px 相当でなめらかにした線）に ≤ 4 px（72 は p95 ≤ 4 px）で合わせ、
細部は段階6 の爪のメッシュ（設計32・33）で合わせる。78・130・131 は従来どおり。両方の値を記録する。

この道具の定義（kstar_h が決めた具体の値）
  * なめらかにする線：main_wave_outline_envelope.json の 131 → 132 → 72 の折れ線をつなぎ、0.25 px で取り直し、
    弧長のガウス σ_LF = 12 px（±1.5σ ≈ 36 px の窓）でならし、132 と 72 の部分だけを置き換える（端点の続きは保つ）。
  * 測り方：評価器（Tools/PaintingTruth/evaluate.py の evaluate_core、包絡版）と同じ「ラベルつき対称 Hausdorff」。
    真値の点の集合は包絡版の空の境界の点のうち、132・72 の点を上のなめらかな線の点に置き換えたもの。描画側の境界の点は
    評価器と同じ（描画の空の被覆 = 1 − max(波の被覆, 参照の海面の被覆) の 0.5 等値線、採点列の内側）。
  * 当てはめ用（kh_fit）：同じ σ で、round 3 の半幅補正つきの目標の線（candA4_fit.Ctx.T）の 132・72 の部分をならす。
"""
import os
import sys
import json
import math

import numpy as np

REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (os.path.join(REPO, "Tools", "PaintingTruth"), os.path.join(REPO, "Tools", "GWWaveGen"),
          os.path.join(REPO, "Tools", "GWWaveGen", "kstar3")):
    if p not in sys.path:
        sys.path.insert(0, p)
SIGMA_LF_PX = 12.0
LF_IDS = ("132", "72")


def smooth_open(P, sigma, step):
    """開いた折れ線を弧長のガウスでならす（端は鏡映で延長して位置を保つ）。P は step 間隔で取り直したもの。"""
    r = int(math.ceil(3 * sigma / step))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) * step / sigma) ** 2); k /= k.sum()
    head = 2 * P[0] - P[1:r + 1][::-1]
    tail = 2 * P[-1] - P[-r - 1:-1][::-1]
    Q = np.vstack([head, P, tail])
    return np.stack([np.convolve(Q[:, i], k, "valid") for i in range(2)], -1)


def resample(P, step):
    P = np.asarray(P, float)
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    n = max(2, int(math.floor(s[-1] / step)) + 1)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], -1)


def lf_polylines(segments, sigma=SIGMA_LF_PX, step=0.25):
    """segments: {id: (n,2) display px} の 131, 132, 72 → {132: 大きな輪郭, 72: 大きな輪郭}（ならした線）。"""
    parts = [resample(segments[k], step) for k in ("131", "132", "72")]
    n1, n2 = len(parts[0]), len(parts[1])
    chain = np.vstack([parts[0], parts[1][1:], parts[2][1:]])
    sm = smooth_open(chain, sigma, step)
    return {"132": sm[n1 - 1:n1 - 1 + n2], "72": sm[n1 - 1 + n2 - 1:]}


def fit_targets(T, Tlab, sigma=SIGMA_LF_PX):
    """kh_fit 用：round 3 の目標の線 T（1 px 間隔、ラベル Tlab）の 132・72 の部分を σ でならした線に替える。"""
    step = float(np.median(np.linalg.norm(np.diff(T, axis=0), axis=1)))
    sm = smooth_open(T, sigma, step)
    out = T.copy()
    m = np.isin(Tlab, LF_IDS)
    # 131 → 132 のつなぎ目は 30 px でなめらかに移す
    i0 = int(np.nonzero(m)[0][0])          # T is ordered 78, 130, 131, 132, 72: 132 and 72 run to the end
    w = np.clip((np.arange(len(T)) - (i0 - 30)) / 30.0, 0, 1)
    out = T * (1 - w[:, None]) + sm * w[:, None]
    return out


class LFGate:
    def __init__(self):
        import evaluate as E
        import truthlib as T
        self.E, self.T = E, T
        self.truth = E.Truth()
        seg = {s["id"]: np.array(s["points_display"], float) for s in self.truth.outline["envelope"]["segments"]}
        self.lf = lf_polylines(seg)
        F = self.truth.fam["sky_envelope"]
        keep = ~np.isin(F["label"], LF_IDS)
        pts = [F["pts"][keep]]; lab = [F["label"][keep]]
        for k in LF_IDS:
            pts.append(self.lf[k]); lab.append(np.array([k] * len(self.lf[k]), dtype=object))
        self.pts = np.vstack(pts); self.lab = np.concatenate(lab)

    def measure(self, cov_wave, seacov):
        """cov_wave: 波の被覆（1920×1080、0..1）、seacov: 参照の海面の被覆。→ {132: {max_px, p95_px}, 72: {...}}"""
        other = np.maximum(cov_wave, seacov)
        rpts = self.T.boundary_points(1.0 - other, self.truth.spec, self.truth.fmap)
        out = {}
        for k in LF_IDS:
            res, _, worst = self.T.labelled_hausdorff(self.pts, self.lab == k, rpts)
            out[k] = {"max_px": float(res["max_px"]), "p95_px": float(res["p95_px"]), "p50_px": float(res["p50_px"]),
                      "worst_xy": None if worst is None else [round(float(worst[0]), 2), round(float(worst[1]), 2)]}
        return out

    def measure_rows(self, c, A, Y):
        import candA_common as C
        import gw_wavegen as G0
        V1, tgt, fr = C.painting_frame()
        X = fr.world(c, A, Y)
        cov = V1.rasterize(fr.cam, X, V1.triangles(A.shape[1], A.shape[0]))
        seacov, _ = G0.sea_horizon_cover(fr.cam, tgt.spec)
        return self.measure(cov, seacov), cov

    def self_test(self):
        """原画そのもの（真値の包絡版の空）を描画として測る：132・72 の値 = なめらかにした量（爪のこぶの大きさ）。"""
        sky = self.truth.cov["sky_envelope"]
        return self.measure(1.0 - sky, np.zeros_like(sky))


def overlay(path, gate_lf, cov, title=""):
    import cv2
    plate = cv2.imread(os.path.join(REPO, "Unity", "Build", "Q20H", "plate", "painting_display_1920x1080.png"))
    img = (plate * 0.55).astype(np.uint8)
    m = cov > 0.5
    img[m] = (img[m] * 0.55 + np.array([200, 120, 40]) * 0.45).astype(np.uint8)
    for k, col in (("132", (0, 255, 255)), ("72", (255, 0, 255))):
        P = gate_lf.lf[k]
        cv2.polylines(img, [np.round(P).astype(np.int32).reshape(-1, 1, 2)], False, col, 1, cv2.LINE_AA)
    cv2.putText(img, title, (170, 1060), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, "yellow = 132 large form, magenta = 72 large form (sigma %.0f px along the painted line)" % SIGMA_LF_PX,
                (170, 1030), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(path, img)


if __name__ == "__main__":
    g = LFGate()
    print(json.dumps({"self_test_painting_vs_its_large_form": g.self_test()}))
    for arg in sys.argv[1:]:
        lab, p = arg.split("=", 1)
        z = np.load(p)
        r, cov = g.measure_rows(z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float))
        print(lab, json.dumps(r))
