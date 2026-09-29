# -*- coding: utf-8 -*-
"""設計29修正01：設計29 の検査器にない、この番号の最小の受入と引き継ぎの項目を測る（numpy。読むだけ）。

サブコマンド（リポジトリの根で。出力は Git 対象外の Unity/Build/Design/29R01/measure/）
  tstar    t*（τ = 0）の網と K*′ の差（精度の層つき・16 bit だけ）、原画視点の画面での頂点の動き（px）、
           原画の関門の幾何の測り（78・130・131・132・72 の原画の線そのもの、132 の大きな輪郭 σ 12 px、72 の大きな輪郭 σ 24 px。
           kh_gate_lfR4.py の LFGate と同じ真値・同じ評価器（Tools/PaintingTruth）。被覆は gw_wavegen_v1.rasterize、海は M1 の参照の海面）を
           K*′ の行（kstar_final の rows.npz。K*′ の評価表の値を再現する確かめ）・復号した t* の網の 3 つで測る。
           --unity-ids <af28r01_class_ids.png> を渡すと、Unity の t* の描画（ID 画像：空以外 = 主役波）の被覆でも同じ関門を測る（引き継ぎ (d)）。
  farwall  30 Hz の二階差分（ワールド、全頂点、|X(τ+h) − 2X(τ) + X(τ−h)|、h = 1/30 s）の最後の 0.1 s の行ごとの最大と、2 g（0.0218 m）を
           超える行（設計29 §6 の 3：奥の壁の行 209〜214 の最後の 0.067 s の急な下がり 0.111 m）。精度の層つきと 16 bit だけの両方。
  normals  再生器のシェーダーの頂点の法線（DS27KeyposeCore.cginc の DS27Normal：周りの最大 6 面の外積の和、長さ 0 なら +Y）を numpy で
           写し、K*′ の行 239（最後の行、長さ 0 の線分と 2 cm の細い帯。引き継ぎ (c)）と周りの行で、決まらない法線（+Y に置き換え）の数、
           隣の行（238）の法線との角度、float64 の K*′ の法線との角度を、t* と最後の 1 s（30 Hz）で測る。
  memory   keypose の GPU メモリの見積もり（層 × 行 × 列 × バイト。16 bit だけ・16 bit ＋ 精度の層の詰め方ごと、読み取り可能の写しの有無）。
使い方：py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_extra.py tstar|farwall|normals|memory [--package …] [--kstar …]
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds29r01_common as C  # noqa: E402

REPO = C.REPO
for p in (os.path.join(REPO, "Tools", "PaintingTruth"), os.path.join(REPO, "Tools", "GWWaveGen"),
          os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h")):
    if p not in sys.path:
        sys.path.insert(0, p)
G = 9.81
HZ = 30
KSTAR_EVAL_TABLE = "Unity/Build/Q20H/final/kstarR4_eval_table.md"
# K*′（R4）の評価表の値（kstarR4_eval_table.md の R4 の列。関門の比べの基準）
KSTAR_NUMBERS = {"raw_78": {"max_px": 2.741}, "raw_130": {"max_px": 3.831}, "raw_131": {"max_px": 2.924},
                 "raw_132": {"max_px": 5.911}, "raw_72": {"p95_px": 8.717, "max_px": 10.467},
                 "lf_132": {"max_px": 3.905, "p95_px": 3.569}, "lf72_s24": {"max_px": 7.601, "p95_px": 3.746}}
GATE_KEYS = [("raw_78", "max_px"), ("raw_130", "max_px"), ("raw_131", "max_px"), ("raw_132", "max_px"), ("raw_72", "p95_px"),
             ("lf_132", "max_px"), ("lf72_s24", "p95_px")]


def surf(pkg, decode, kstar):
    Q = C.setup(kstar, decode)
    C.STATE["decode"] = decode
    return Q, Q.PackageSurface(os.path.join(REPO, pkg), "%s_%s" % (os.path.basename(pkg.rstrip("/")), decode))


# ---------------------------------------------------------------- 原画の関門（幾何・Unity の画像）
class PaintingGate:
    def __init__(self):
        import kh_gate_lfR4 as KG4
        import candA_common as CA
        import gw_wavegen as G0
        self.g4 = KG4.LFGate()
        V1, tgt, fr = CA.painting_frame()
        self.V1, self.tgt, self.fr = V1, tgt, fr
        self.seacov, self.horizon_y = G0.sea_horizon_cover(fr.cam, tgt.spec)
        F = self.g4.truth.fam["sky_envelope"]
        self.raw_pts, self.raw_lab = F["pts"], F["label"]

    def cover_world(self, X):
        """X (nv, nu, 3) のワールド位置 → 原画視点の被覆（1920 × 1080、2 × 2 の標本の平均）。"""
        nv, nu = X.shape[:2]
        return self.V1.rasterize(self.fr.cam, X, self.V1.triangles(nu, nv))

    def cover_rows(self, c, A, Y):
        return self.cover_world(self.fr.world(c, A, Y))

    def project(self, X):
        return self.fr.cam.project(X.reshape(-1, 3))

    def measure(self, cov):
        T = self.g4.T
        other = np.maximum(cov, self.seacov)
        rpts = T.boundary_points(1.0 - other, self.g4.truth.spec, self.g4.truth.fmap)
        out = {}
        for k in ("78", "130", "131", "132", "72"):
            res, _, w = T.labelled_hausdorff(self.raw_pts, self.raw_lab == k, rpts)
            out["raw_" + k] = dict(max_px=round(float(res["max_px"]), 3), p95_px=round(float(res["p95_px"]), 3))
        for k, key in (("132", "lf_132"), ("72", "lf72_s24")):
            res, _, w = T.labelled_hausdorff(self.g4.pts, self.g4.lab == k, rpts)
            out[key] = dict(max_px=round(float(res["max_px"]), 3), p95_px=round(float(res["p95_px"]), 3))
        out["gate_pass"] = bool(all(out["raw_" + k]["max_px"] <= 4 for k in ("78", "130", "131")) and out["lf_132"]["max_px"] <= 4
                                and out["lf72_s24"]["p95_px"] <= 4)
        return out


def diff_vs(m, base):
    d = {}
    for k, s in GATE_KEYS:
        if k in m and k in base and s in base[k]:
            d["%s.%s" % (k, s)] = round(m[k][s] - base[k][s], 3)
    return d, max(abs(v) for v in d.values())


def run_tstar(a):
    t0 = time.time()
    out = dict(schema="GreatWave.DS29R01.tstar/1", package=a.package, kstar=a.kstar, kstar_numbers_source=KSTAR_EVAL_TABLE,
               kstar_numbers=KSTAR_NUMBERS)
    Q, S = surf(a.package, "fine", a.kstar)
    import ds27_gates as G27
    ks = G27.KStar()
    kdir = os.path.join(REPO, a.kstar)
    rows_npz = [f for f in os.listdir(kdir) if f.endswith("_rows.npz")][0]
    z = np.load(os.path.join(kdir, rows_npz))
    PG = PaintingGate()
    # K*′ の行から（評価表の再現の確かめ）と、K*′ の gwb の頂点（ワールド）から
    cov_rows = PG.cover_rows(z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float))
    m_rows = PG.measure(cov_rows)
    cov_k = PG.cover_world(ks.X)
    m_k = PG.measure(cov_k)
    out["kstar_rows_npz"] = dict(file=C.rel(os.path.join(kdir, rows_npz)), gate=m_rows, diff_vs_table=diff_vs(m_rows, KSTAR_NUMBERS)[0],
                                 max_abs_diff_vs_table_px=diff_vs(m_rows, KSTAR_NUMBERS)[1])
    out["kstar_gwb"] = dict(gate=m_k, cover_diff_vs_rows=dict(pixels_gt_0p5=int((np.abs(cov_k - cov_rows) > 0.5).sum()),
                                                                 sum_abs=round(float(np.abs(cov_k - cov_rows).sum()), 2)))
    res = {}
    Pk = PG.project(ks.X)
    for dec in ("fine", "hi"):
        C.STATE["decode"] = dec
        s = Q.PackageSurface(os.path.join(REPO, a.package), "t_" + dec)
        X = s.world(0.0).reshape(ks.nv, ks.nu, 3)
        d = np.linalg.norm(X - ks.X, axis=-1)
        P = PG.project(X)
        # 画面の中（1920 × 1080 の ±10 px）でカメラの前（rasterize と同じ：深さ > 0.5）の頂点だけ（カメラの面の近くの点は射影が発散する）
        cam = PG.fr.cam
        vis = ((Pk[:, 2] > 0.5) & (P[:, 2] > 0.5) & (Pk[:, 0] > -10) & (Pk[:, 0] < cam.W + 10) & (Pk[:, 1] > -10) & (Pk[:, 1] < cam.H + 10))
        dp = np.linalg.norm(P[vis, :2] - Pk[vis, :2], axis=1)
        cov = PG.cover_world(X)
        m = PG.measure(cov)
        dd, mx = diff_vs(m, m_k)
        res[dec] = dict(decode_ja=s.info()["decode_ja"], vertex_diff_vs_kstar_mm=dict(max=round(float(d.max()) * 1000, 4),
                                                                                       rms=round(float(np.sqrt((d ** 2).mean())) * 1000, 4)),
                        painting_screen_shift_px=dict(max=round(float(dp.max()), 5), p99=round(float(np.percentile(dp, 99)), 5),
                                                      vertices_in_frame=int(vis.sum())),
                        cover_diff_vs_kstar=dict(pixels_gt_0p5=int((np.abs(cov - cov_k) > 0.5).sum()), sum_abs=round(float(np.abs(cov - cov_k).sum()), 3)),
                        gate=m, diff_vs_kstar_gwb=dd, max_abs_diff_vs_kstar_gwb_px=mx,
                        diff_vs_table=diff_vs(m, KSTAR_NUMBERS)[0], max_abs_diff_vs_table_px=diff_vs(m, KSTAR_NUMBERS)[1],
                        regression_pass=bool(mx <= 0.5))
    out["decoded_tstar"] = res
    if a.unity_ids:
        from PIL import Image
        for spec in a.unity_ids:
            lab, p = spec.split("=", 1) if "=" in spec else ("unity", spec)
            p = p if os.path.isabs(p) else os.path.join(REPO, p)
            im = np.asarray(Image.open(p).convert("RGB")).astype(np.int32)
            sky = (im[..., 0] == 255) & (im[..., 1] == 255) & (im[..., 2] == 255)
            cov_u = (~sky).astype(np.float64)
            H0, W0 = PG.seacov.shape
            ss = cov_u.shape[0] // H0
            if ss > 1:          # ID 画像は 3840 × 2160（2 × 2 の標本）で描かれる：幾何の被覆（2 × 2 の標本の平均）と同じにならす
                cov_u = cov_u[:H0 * ss, :W0 * ss].reshape(H0, ss, W0, ss).mean((1, 3))
            m = PG.measure(cov_u)
            dd, mx = diff_vs(m, m_k)
            out.setdefault("unity_image", {})[lab] = dict(
                file=C.rel(p), sha256=C.sha256_file(p), size=[int(im.shape[1]), int(im.shape[0])],
                note_ja="Unity の t* の ID 画像（主役波だけ、空 = 白、アンチエイリアスなし）の空以外を波の被覆にした。海は M1 の参照の海面（幾何と同じ）",
                gate=m, diff_vs_kstar_gwb_geometry=dd, max_abs_diff_vs_kstar_gwb_px=mx,
                diff_vs_table=diff_vs(m, KSTAR_NUMBERS)[0],
                cover_diff_vs_kstar_geometry=dict(pixels_gt_0p5=int((np.abs(cov_u - cov_k) > 0.5).sum())))
    out["criterion_ja"] = ("原画視点の回帰なし：K*′ の値（評価表・同じ評価器で K*′ の gwb を測った値）と ±0.5 px（計画 §2.0、設計29 §3）。"
                           "関門の合否（78/130/131 最大 ≤ 4、132 大きな輪郭 σ12 最大 ≤ 4、72 大きな輪郭 σ24 p95 ≤ 4）は K*′ の読み（設計28修正01 の Q24 の採用）")
    out["runtime_s"] = round(time.time() - t0, 1)
    C.jdump(os.path.join(a.out, "ds29r01_tstar.json"), out)
    print(json.dumps({k: (v if k != "kstar_numbers" else None) for k, v in out.items() if k in ("kstar_rows_npz",)}, ensure_ascii=False)[:600])
    for dec, r in res.items():
        print("DS29R01 tstar", dec, r["vertex_diff_vs_kstar_mm"], r["painting_screen_shift_px"], "gate diff max", r["max_abs_diff_vs_kstar_gwb_px"], flush=True)
    for lab, r in out.get("unity_image", {}).items():
        print("DS29R01 unity", lab, r["gate"], "diff max", r["max_abs_diff_vs_kstar_gwb_px"], flush=True)


def run_light_tstar(a):
    """軽量版（--light の包み）の t* の網で、同じ原画の関門を測り、K*′（原版の t*）との差と、原画視点の被覆の差を記録する。"""
    t0 = time.time()
    Q, S = surf(a.package, "fine", a.kstar)
    import ds27_gates as G27
    ks = G27.KStar()
    PG = PaintingGate()
    cov_k = PG.cover_world(ks.X)
    m_k = PG.measure(cov_k)
    out = dict(schema="GreatWave.DS29R01.light_tstar/1", kstar=a.kstar, kstar_gate=m_k)
    for spec in a.light:
        lab, p = spec.split("=", 1)
        s = Q.PackageSurface(os.path.join(REPO, p), lab)
        X = s.world(0.0).reshape(s.rows, s.cols, 3)
        cov = PG.cover_world(X)
        m = PG.measure(cov)
        dd, mx = diff_vs(m, m_k)
        # 原版との輪郭の差：被覆の 0.5 等値線の点どうしの対称の距離（px）
        T = PG.g4.T
        rp_k = T.iso_points(cov_k, 0.5) if hasattr(T, "iso_points") else None
        rp_l = T.iso_points(cov, 0.5) if hasattr(T, "iso_points") else None
        sil = None
        if rp_k is not None and len(rp_k) and len(rp_l):
            from scipy.spatial import cKDTree
            d1 = cKDTree(rp_l).query(rp_k)[0]
            d2 = cKDTree(rp_k).query(rp_l)[0]
            sil = dict(max_px=round(float(max(d1.max(), d2.max())), 3), p95_px=round(float(np.percentile(np.r_[d1, d2], 95)), 3))
        out[lab] = dict(package=p, rows=s.rows, cols=s.cols, layers=s.L, gate=m, diff_vs_kstar_px=dd, max_abs_diff_vs_kstar_px=mx,
                        regression_pass=bool(mx <= 0.5), silhouette_vs_original_painting=sil,
                        cover_pixels_diff_gt_0p5=int((np.abs(cov - cov_k) > 0.5).sum()))
        print("DS29R01 light", lab, m, "diff max", mx, "sil", sil, flush=True)
    out["runtime_s"] = round(time.time() - t0, 1)
    C.jdump(os.path.join(a.out, "ds29r01_light_tstar.json"), out)


# ---------------------------------------------------------------- 奥の壁の最後の下がり
def run_farwall(a):
    t0 = time.time()
    Q, _ = surf(a.package, "fine", a.kstar)
    import ds27_gates as G27
    ks = G27.KStar()
    thr = 2 * G / HZ ** 2
    taus = [-k / HZ for k in range(12, -1, -1)]          # τ −0.4〜0 s
    out = dict(schema="GreatWave.DS29R01.farwall/1", package=a.package, threshold_m=thr, threshold_ja="2 g（30 Hz の二階差分 2·9.81/30² m）",
               definition_ja="d2(τ) = |X(τ+h) − 2X(τ) + X(τ−h)|、h = 1/30 s、ワールド。『最後の 0.067 s』= d2(−1/30)（X(−2/30)・X(−1/30)・X(0) の 3 コマ）",
               d29_reference_ja="設計29 §6 の 3：設計28 の網で奥の壁の行 209〜214、最後の 0.067 s に 0.111 m（約 10 g）")
    for dec in ("fine", "hi"):
        C.STATE["decode"] = dec
        s = Q.PackageSurface(os.path.join(REPO, a.package), "fw_" + dec)
        Xs = np.stack([s.world(t).reshape(ks.nv, ks.nu, 3) for t in taus])
        d2 = np.linalg.norm(Xs[2:] - 2 * Xs[1:-1] + Xs[:-2], axis=-1)       # (n−2, nv, nu) at taus[1:-1]
        tc = taus[1:-1]
        last = d2[-1]                                      # τ = −1/30
        last3 = d2[-3:].max(0)                             # τ −0.1〜−1/30
        rowmax = last.max(1)
        order = np.argsort(-rowmax)
        over = np.nonzero(rowmax > thr)[0]
        r_all = d2.max(0).max(1)
        rec = dict(max_last_m=round(float(last.max()), 5), max_last_g=round(float(last.max()) * HZ ** 2 / G, 2),
                   at_last=dict(row=int(np.unravel_index(last.argmax(), last.shape)[0]), col=int(np.unravel_index(last.argmax(), last.shape)[1])),
                   rows_over_2g_last=[int(r) for r in over], n_rows_over_2g_last=int(len(over)),
                   vertices_over_2g_last=int((last > thr).sum()),
                   top_rows_last=[dict(row=int(r), d2_m=round(float(rowmax[r]), 5), col=int(last[r].argmax())) for r in order[:8]],
                   max_last_0p1s_m=round(float(last3.max()), 5), vertices_over_2g_last_0p1s=int((last3 > thr).sum()),
                   max_window_m=round(float(d2.max()), 5), max_window_tau=round(float(tc[int(np.unravel_index(d2.argmax(), d2.shape)[0])]), 4),
                   rows_over_2g_window=[int(r) for r in np.nonzero(r_all > thr)[0]],
                   far_rows_200_239_last_max_m=round(float(last[200:].max()), 5),
                   per_tau_max=[[round(float(t), 4), round(float(d2[i].max()), 5)] for i, t in enumerate(tc)])
        out[dec] = rec
        print("DS29R01 farwall", dec, rec["max_last_m"], rec["n_rows_over_2g_last"], rec["top_rows_last"][:3], flush=True)
    out["runtime_s"] = round(time.time() - t0, 1)
    C.jdump(os.path.join(a.out, "ds29r01_farwall.json"), out)


# ---------------------------------------------------------------- 再生器の法線（行 239）
def shader_normals(X):
    """DS27Normal の写し。X (nv, nu, 3) → 単位法線 (nv, nu, 3) と、決まらない（長さ 0 → +Y）頂点の真偽。"""
    nv, nu = X.shape[:2]
    n = np.zeros_like(X)
    dD = np.zeros_like(X); dR = np.zeros_like(X); dU = np.zeros_like(X); dL = np.zeros_like(X)
    dD[:-1] = X[1:] - X[:-1]
    dR[:, :-1] = X[:, 1:] - X[:, :-1]
    dU[1:] = X[:-1] - X[1:]
    dL[:, 1:] = X[:, :-1] - X[:, 1:]
    # T1 of quad (r,c)
    n[:-1, :-1] += np.cross(dD[:-1, :-1], dR[:-1, :-1])
    # quad (r, c-1): needs hd & hl
    dDL = np.zeros_like(X)
    dDL[:-1, 1:] = X[1:, :-1] - X[:-1, 1:]
    n[:-1, 1:] += np.cross(dL[:-1, 1:], dDL[:-1, 1:]) + np.cross(dDL[:-1, 1:], dD[:-1, 1:])
    # quad (r-1, c): hu & hr
    dUR = np.zeros_like(X)
    dUR[1:, :-1] = X[:-1, 1:] - X[1:, :-1]
    n[1:, :-1] += np.cross(dUR[1:, :-1], dU[1:, :-1]) + np.cross(dR[1:, :-1], dUR[1:, :-1])
    # quad (r-1, c-1) T2: hu & hl
    n[1:, 1:] += np.cross(dU[1:, 1:], dL[1:, 1:])
    ln = np.linalg.norm(n, axis=-1)
    und = ~(ln > 1e-30)
    un = np.where(und[..., None], np.array([0.0, 1.0, 0.0]), n / np.maximum(ln, 1e-300)[..., None])
    return un, und


def ang(a, b):
    return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))


def run_normals(a):
    t0 = time.time()
    Q, _ = surf(a.package, "fine", a.kstar)
    import ds27_gates as G27
    ks = G27.KStar()
    K = ks.X
    uK, undK = shader_normals(K)
    rows = [236, 237, 238, 239]
    seg = np.linalg.norm(np.diff(K, axis=1), axis=-1)       # (nv, nu-1) 行の方向の線分
    vseg = np.linalg.norm(K[1:] - K[:-1], axis=-1)           # 行の間
    out = dict(schema="GreatWave.DS29R01.normals/1", package=a.package, kstar=a.kstar,
               shader_ja="DS27KeyposeCore.cginc の DS27Normal（周りの最大 6 面の正規化しない外積の和、長さ ≤ 1e−30 なら +Y）を numpy で写した",
               kstar_row239=dict(zero_length_row_segments=int((seg[239] < 1e-6).sum()), row_segments_lt_1mm=int((seg[239] < 1e-3).sum()),
                                 gap_to_row238_m=dict(min=round(float(vseg[238].min()), 4), median=round(float(np.median(vseg[238])), 4),
                                                      max=round(float(vseg[238].max()), 4)),
                                 undefined_normals_kstar_float32=int(undK[239].sum())))
    taus = [0.0] + [-k / HZ for k in range(1, 31)]
    res = {}
    for dec in ("fine", "hi"):
        C.STATE["decode"] = dec
        s = Q.PackageSurface(os.path.join(REPO, a.package), "n_" + dec)
        per = []
        worst = dict(undefined=0, ang_vs_238_max=0.0, ang_vs_kstar_max=0.0)
        for t in taus:
            X = s.world(t).reshape(ks.nv, ks.nu, 3)
            un, und = shader_normals(X)
            r239 = dict(tau=round(t, 4), undefined=int(und[239].sum()), undefined_all_rows=int(und.sum()),
                        undefined_rows=[int(r) for r in np.unique(np.nonzero(und)[0])][:12],
                        ang_vs_row238_deg=dict(max=round(float(ang(un[239], un[238]).max()), 2), p99=round(float(np.percentile(ang(un[239], un[238]), 99)), 2),
                                               n_gt_30=int((ang(un[239], un[238]) > 30).sum()), n_gt_60=int((ang(un[239], un[238]) > 60).sum())),
                        ang_row238_vs_237_deg=dict(max=round(float(ang(un[238], un[237]).max()), 2)))
            if t == 0.0:
                a_k = ang(un, uK)
                r239["ang_vs_kstar_shader_normal_deg"] = {str(r): dict(max=round(float(a_k[r].max()), 3), p99=round(float(np.percentile(a_k[r], 99)), 3)) for r in rows}
                r239["ang_vs_kstar_all_rows_max_deg"] = round(float(a_k.max()), 3)
                wr = np.unravel_index(a_k.argmax(), a_k.shape)
                r239["ang_vs_kstar_all_rows_at"] = [int(wr[0]), int(wr[1])]
                cols_bad = np.nonzero(ang(un[239], un[238]) > 30)[0]
                r239["row239_cols_gt30_vs_238"] = [int(c) for c in cols_bad[:40]]
                worst["ang_vs_kstar_max"] = r239["ang_vs_kstar_all_rows_max_deg"]
            worst["undefined"] = max(worst["undefined"], r239["undefined"])
            worst["ang_vs_238_max"] = max(worst["ang_vs_238_max"], r239["ang_vs_row238_deg"]["max"])
            per.append(r239)
        # 形成の全体（30 Hz、τ −12〜0 s）：奥の端の行 228〜239 で、再生器の法線が 1 つ手前の行の法線と 90° を超えて違う頂点（裏返った法線）
        # と決まらない法線。折れ返りの検査（隣 2 つ以上と逆向きの面）が行 230〜239・列 200〜249 に集まるので、描画に出うる法線の裏返りを数える
        far = dict(rows=[228, 239], frames=0, frames_with_flip=0, flip_vertex_frames=0, undefined_vertex_frames=0, worst=None, per_tau=[])
        for k in range(12 * HZ + 1):
            t = -12.0 + k / HZ
            X = s.world(t).reshape(ks.nv, ks.nu, 3)
            un, und = shader_normals(X)
            aa = ang(un[228:240], un[227:239])
            nflip = int((aa > 90).sum())
            far["frames"] += 1
            far["frames_with_flip"] += int(nflip > 0)
            far["flip_vertex_frames"] += nflip
            far["undefined_vertex_frames"] += int(und[228:240].sum())
            if nflip:
                far["per_tau"].append([round(t, 4), nflip])
                if far["worst"] is None or nflip > far["worst"]["n"]:
                    rr, cc = np.nonzero(aa > 90)
                    far["worst"] = dict(tau=round(t, 4), n=nflip, rows=sorted(set(int(r) + 228 for r in rr)), cols=[int(cc.min()), int(cc.max())])
        far["per_tau"] = far["per_tau"][:80]
        res[dec] = dict(worst=worst, frames=per, formation_far_rows=far)
        print("DS29R01 normals far rows", dec, {k: far[k] for k in ("frames_with_flip", "flip_vertex_frames", "undefined_vertex_frames", "worst")}, flush=True)
        print("DS29R01 normals", dec, worst, per[0]["ang_vs_row238_deg"], per[0].get("ang_vs_kstar_shader_normal_deg", {}).get("239"), flush=True)
    # K*′ 自身（float32 の gwb）でも行 239 と 238 の法線の角度
    out["kstar_self"] = dict(ang_row239_vs_238_deg=dict(max=round(float(ang(uK[239], uK[238]).max()), 2),
                                                        n_gt_30=int((ang(uK[239], uK[238]) > 30).sum()),
                                                        n_gt_60=int((ang(uK[239], uK[238]) > 60).sum())),
                             ang_row238_vs_237_deg_max=round(float(ang(uK[238], uK[237]).max()), 2),
                             undefined_rows=[int(r) for r in np.unique(np.nonzero(undK)[0])][:20], undefined_total=int(undK.sum()))
    out["decoded"] = res
    out["runtime_s"] = round(time.time() - t0, 1)
    C.jdump(os.path.join(a.out, "ds29r01_normals.json"), out)
    print("DS29R01 normals kstar_self", out["kstar_self"], out["kstar_row239"], flush=True)


# ---------------------------------------------------------------- GPU メモリ
def run_memory(a):
    pj = os.path.join(REPO, a.package, "ds27_keypose.json")
    J = json.load(open(pj, encoding="utf-8"))
    L, nv, nu = int(J["layers"]), int(J["rows"]), int(J["cols"])
    n = nv * nu
    MiB = 2 ** 20
    ntri = 2 * (nv - 1) * (nu - 1)
    tw = n * 4
    mesh_v = n * (12 + 12 + 8 + 8 + 8) / MiB    # 設計29 の実測（原版 4.39 MiB：位置・法線・UV・UV2・UV3 の頂点の属性）の見積もりに合わせた目安
    idx = ntri * 3 * 4 / MiB
    lay = {
        "hi_only_structuredbuffer_6B": dict(bytes_per_vertex_layer=6, note_ja="設計27〜29 の再生器（16 bit × 3 を StructuredBuffer<uint> に詰める、GPU だけ）。精度の層を読まない"),
        "hi_plus_lo_packed_9B": dict(bytes_per_vertex_layer=9, note_ja="16 bit × 3 ＋ 8 bit × 3 を 72 bit で詰める（GPU だけ）"),
        "hi_plus_lo_structuredbuffer_10B": dict(bytes_per_vertex_layer=10, note_ja="16 bit × 3（6 B）＋ 精度の層 8 bit × 3 を 1 つの uint（4 B）に詰める（GPU だけ）"),
        "texture2darray_rgba64_rgba32_12B": dict(bytes_per_vertex_layer=12, note_ja="RGBA64 ＋ RGBA32 の Texture2DArray、読み取り不可（GPU だけ）。設計28修正01 の見積もり fine_texture2darray_mib"),
        "texture2darray_rgba64_rgba32_readable_24B": dict(bytes_per_vertex_layer=24, note_ja="同じ、読み取り可能（CPU の写しで 2 倍）。設計28修正01 の 532 MiB"),
    }
    for k, v in lay.items():
        pos = L * n * v["bytes_per_vertex_layer"] / MiB
        v["position_mib"] = round(pos, 2)
        v["total_with_twhite_mesh_mib"] = round(pos + tw / MiB + mesh_v + idx, 2)
        v["pass_le_512"] = bool(v["total_with_twhite_mesh_mib"] <= 512)
    out = dict(schema="GreatWave.DS29R01.memory/1", package=a.package, layers=L, rows=nv, cols=nu, vertices=n, triangles=ntri,
               twhite_mib=round(tw / MiB, 3), mesh_vertex_attr_mib_estimate=round(mesh_v, 2), index_mib=round(idx, 2),
               package_gpu_estimate=J.get("gpu_estimate"), layouts=lay, budget_mib=512,
               note_ja=("見積もり（バッファの大きさの和）。Unity の実測（再生器の割り当ての数の増え）は精度の層を読む再生器の側で測る。"
                        "設計29 の原版の実測は 186 層・位置 102.2 MiB（6 B）で、同じ式の 186 × 96,000 × 6 B = 102.2 MiB と一致した"))
    C.jdump(os.path.join(a.out, "ds29r01_memory.json"), out)
    for k, v in lay.items():
        print("DS29R01 memory", k, v["position_mib"], v["total_with_twhite_mesh_mib"], v["pass_le_512"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["tstar", "farwall", "normals", "memory", "light_tstar"])
    ap.add_argument("--package", default=C.DEFAULT_PACKAGE)
    ap.add_argument("--kstar", default=C.DEFAULT_KSTAR)
    ap.add_argument("--unity-ids", action="append", default=[])
    ap.add_argument("--light", action="append", default=[], help="light_tstar：名前=<軽量版の包み>")
    ap.add_argument("--out", default=os.path.join(C.OUT_ROOT, "measure"))
    a = ap.parse_args()
    {"tstar": run_tstar, "farwall": run_farwall, "normals": run_normals, "memory": run_memory, "light_tstar": run_light_tstar}[a.cmd](a)


if __name__ == "__main__":
    main()
