# -*- coding: utf-8 -*-
"""仕上げ30：周りの海のパッケージの検査（numpy。Unity の描画ではない）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/checks_final [--skip boat,kink]
    （--sea に設計30 のパッケージ Unity/Build/Design/30/sea を渡すと「前」の値を同じ読みで測る。その時は --hero-pkg に設計30 が使った F_final を渡さず、
      主役波は今の採用（G_p28rec）のままで測る＝仕上げ29 までの場面で実際に描かれていた組み合わせ）
測るもの（計画 §5.3 仕上げ30 の ① の目標と S5-2）：
  seam   主役波の境の輪と near の行 0 の隔たり（全節点）、near の外周と far の行 0 の隔たり（T 字）、継ぎ目の両側の面の法線の内積（列ごと、5 節点おき＋t*）
  boat   座席の船の支えの当て布の稜・溝：t* の near の各列で、継ぎ目から 8 m の内の y(s) の ±1 m の弦からの出っ張り（竜骨の足跡の外）。目標 ≤ 0.1 m
  kink   near の帯（継ぎ目から 12 m の内）の頂点ごとの y の 30 Hz の二階差分（目標 ≤ 0.05 m／コマ²）と、帯の傾き（目標 45° 以下、継ぎ目から 1 m より外）
  fuji   原画視点の t 5〜10.5 s（0.25 s おき）と t* で、海（near・far の 0〜3 行）と主役波の網の画面の上の縁が、富士の雪の下の端（y 752 px）より上に出る列の数と、
         富士の雪の画素（仕上げ29 の t* の描画の色で取った印）のうち、網の上の縁より上に残る割合（見える割合）。頂点と辺の中点の投影の列ごとの最小で縁を取る
  boatheave  座席の船の上下（boat_support.json。設計30 と同じ読み）を G_p28rec の時間曲線で作り、<sea>/boat_support.json に書く
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl30_sea as S  # noqa: E402

REPO = S.REPO
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds27"))
from ds27_player_ref import hermite_weights  # noqa: E402

W, H = 1920, 1080
FUJI_SNOW_RGB = (252, 249, 230)


class Pkg:
    def __init__(self, d):
        self.dir = d
        k = S.load_json(os.path.join(d, "ds27_keypose.json"))
        self.k = k
        self.L, self.R, self.C = k["layers"], k["rows"], k["cols"]
        self.bmin = np.array(k["bbox_min"]); self.bsz = np.array(k["bbox_size"])
        self.knots = np.array(k["knot_tau"])
        self.ft = np.array(k["frame"]["tau"]); self.fo = np.array(k["frame"]["origin"])
        self.hi = np.memmap(os.path.join(d, k["pos_file"]), dtype="<u2", mode="r", shape=(self.L, self.R, self.C, 4))
        self.lo = np.memmap(os.path.join(d, k["pos_lo_file"]), dtype="u1", mode="r", shape=(self.L, self.R, self.C, 4))

    def layer(self, i, rows=None):
        rs = slice(None) if rows is None else rows
        q = self.hi[i, rs, :, :3].astype(np.float64) + self.lo[i, rs, :, :3].astype(np.float64) / 255.0 - 0.5
        return self.bmin + q / 65535.0 * self.bsz

    def origin(self, tau):
        return np.array([np.interp(tau, self.ft, self.fo[:, j]) for j in range(3)])

    def at(self, tau, rows=None):
        idx, w = hermite_weights(self.knots, tau)
        return sum(wi * self.layer(ii, rows) for ii, wi in zip(idx, w) if wi != 0.0)

    def world(self, tau, rows=None):
        return self.at(tau, rows) + self.origin(tau)[None, None, :]


def grid_tris(R, Cn, c0=0, c1=None):
    c1 = Cn - 1 if c1 is None else c1
    r, c = np.meshgrid(np.arange(R - 1), np.arange(c0, c1), indexing="ij")
    a = (r * Cn + c).ravel(); b = ((r + 1) * Cn + c).ravel(); cc = (r * Cn + c + 1).ravel(); d = ((r + 1) * Cn + c + 1).ravel()
    return np.stack([np.stack([a, b, cc], 1), np.stack([cc, b, d], 1)], 1).reshape(-1, 3)


def vnormals(X):
    """格子の頂点の法線（隣の差の外積。DS27Normal と同じ向き：(P[r+1]−P[r]) × (P[c+1]−P[c]) が +y）。"""
    dr = np.zeros_like(X); dc = np.zeros_like(X)
    dr[1:-1] = X[2:] - X[:-2]; dr[0] = X[1] - X[0]; dr[-1] = X[-1] - X[-2]
    dc[:, 1:-1] = X[:, 2:] - X[:, :-2]; dc[:, 0] = X[:, 1] - X[:, 0]; dc[:, -1] = X[:, -1] - X[:, -2]
    n = np.cross(dr, dc)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)


def timewarp(P):
    tw = S.load_json(os.path.join(REPO, "Unity", "Build", "Polish", "28", "G_p28rec", "timewarp_G_p28rec.json"))
    return np.array(tw["t"]), np.array(tw["tau"]), tw


# ---------------------------------------------------------------- seam
def seam(hero, near, far, idx, P):
    loop = np.array([[d["hero_row"], d["hero_col"]] for d in idx["loop"]])
    NL = len(loop)
    kn = hero.knots
    ks = sorted(set(list(range(0, len(kn), 5)) + [len(kn) - 1]))
    ring = []; tj = []; dots = []
    jb, je = idx["body_cols"]
    for i in ks:
        Xh = hero.layer(i); Xn = near.layer(i); Xf = far.layer(i, rows=slice(0, 2))
        ring.append(float(np.abs(Xh[loop[:, 0], loop[:, 1]] - Xn[0, :NL]).max()))
        fs = (near.C - 1) // (far.C - 1)
        tj.append(float(np.abs(Xn[-1, 0:NL:fs] - Xf[0, :far.C - 1]).max()))
        # 法線：主役波の境の頂点の法線（本体の列の中で求める）と near の行 0 の頂点の法線（near の格子で求める）
        nh = vnormals(Xh[:, jb:je + 1])
        nn = vnormals(Xn)
        hh = nh[loop[:, 0], loop[:, 1] - jb]
        d = (hh * nn[0, :NL]).sum(-1)
        dots.append(d)
    dots = np.array(dots)
    kinds = np.array([d["ray"] for d in idx["loop"]])
    good = ~((loop[:, 0] == 0) | (loop[:, 0] == hero.R - 1))      # 錐の点（行 0・239）を除く
    front = (kinds == "front") & good
    return dict(ring0_max_diff_m=float(max(ring)), near_far_T_max_diff_m=float(max(tj)), knots_checked=len(ks),
                normal_dot_min_excl_cone=float(dots[:, good].min()), normal_dot_p1_excl_cone=float(np.percentile(dots[:, good], 1)),
                normal_dot_tstar_min_excl_cone=float(dots[-1, good].min()), normal_dot_tstar_front_min=float(dots[-1, front].min()),
                normal_dot_below09_tstar=int((dots[-1, good] < 0.9).sum()), normal_dot_below09_max_per_knot=int((dots[:, good] < 0.9).sum(1).max()),
                worst=dict(knot=int(ks[int(np.unravel_index(np.argmin(np.where(good[None], dots, 9)), dots.shape)[0])]),
                           col=int(np.unravel_index(np.argmin(np.where(good[None], dots, 9)), dots.shape)[1])),
                note_ja="法線は頂点の法線（隣の差の外積）。主役波は本体の列 18〜394 の中で求めた（設計30 は余白の列を含む格子で求めた）。錐の点（主役波の行 0・239）は法線が決まらないので除いた。")


# ---------------------------------------------------------------- boat
def boat_ridge(hero, near, feat, P, attr_path=None):
    X = near.layer(near.L - 1)
    qcr = None
    if attr_path and os.path.exists(attr_path):
        _raw = np.fromfile(attr_path, "<f4")
        _A = _raw.reshape(near.R, near.C, _raw.size // (near.R * near.C))
        qcr = _A[..., 0].astype(np.float64)   # 作る部 12 個・修正01 20 個のどちらも 0 番が稜の q
        if _A.shape[-1] >= 16:
            # 修正01：谷の縁のうねりの頂（面の座標 rimq の ±1 m、重み tw > 0.2）は自然の頂なので、右の高い波の稜と同じく数えない
            qcr = np.where((np.abs(_A[..., 14]) < 1.0) & (_A[..., 15] > 0.2), 0.0, qcr)
    O = near.origin(0.0)
    t_ax, e_ax = feat.h.t, feat.h.e
    a = X[..., 0] * t_ax[0] + X[..., 2] * t_ax[2]
    c = X[..., 0] * e_ax[0] + X[..., 2] * e_ax[2]
    wB = feat.sample(a, c, "boat_w")
    k = feat.keel
    # 竜骨の足跡からの平面図の距離
    A0, C0, A1, C1 = k["a"][0], k["c"][0], k["a"][-1], k["c"][-1]
    L2 = (A1 - A0) ** 2 + (C1 - C0) ** 2
    u = np.clip(((a - A0) * (A1 - A0) + (c - C0) * (C1 - C0)) / L2, 0, 1)
    dk = np.hypot(a - (A0 + u * (A1 - A0)), c - (C0 + u * (C1 - C0)))
    B = P["features"]["ds30_boat_support"]
    cols = np.nonzero((wB[1:12].max(0) > 0.01) | (dk[0] < B["outer_m"] + 3))[0]
    cols = cols[cols < near.C - 1]
    worst = dict(ridge=0.0, groove=0.0)
    out = []
    for j in cols:
        xz = X[:, j, [0, 2]]
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(xz, axis=0), axis=1))])
        m = s < 8.0
        if m.sum() < 5:
            continue
        ss = np.linspace(0.0, min(8.0, s[m].max()), 161)
        yy = np.interp(ss, s, X[:, j, 1])
        dd = np.interp(ss, s, dk[:, j])
        qc = np.interp(ss, s, qcr[:, j]) if qcr is not None else np.full_like(ss, 99.0)
        for q in range(20, len(ss) - 20):
            if dd[q] <= B["inner_m"] or abs(qc[q]) < 2.0:      # 竜骨の足跡の内と、右の高い波の稜（自然の頂）の ±2 m は数えない
                continue
            lo, hi = yy[q - 20:q + 1], yy[q:q + 21]
            if yy[q] >= lo.max() and yy[q] >= hi.max():        # 本当の山（±1 m の中で最も高い）
                prom = yy[q] - max(lo.min(), hi.min())
            elif yy[q] <= lo.min() and yy[q] <= hi.min():      # 本当の谷
                prom = yy[q] - min(lo.max(), hi.max())
            else:
                continue
            if prom > worst["ridge"]:
                worst["ridge"] = float(prom); worst["ridge_at"] = dict(col=int(j), s=float(ss[q]), dk=float(dd[q]), y=float(yy[q]))
            if prom < worst["groove"]:
                worst["groove"] = float(prom); worst["groove_at"] = dict(col=int(j), s=float(ss[q]), dk=float(dd[q]), y=float(yy[q]))
    # 竜骨の各点の t* の水面との差（喫水 0.38 m が理想）
    kw = []
    for (ka, kc, ky) in zip(k["a"], k["c"], k["y"]):
        d2 = (a - ka) ** 2 + (c - kc) ** 2
        r, j = np.unravel_index(np.argmin(d2), d2.shape)
        kw.append(float(X[r, j, 1] - ky))
    return dict(cols=int(len(cols)), max_ridge_outside_keel_m=worst["ridge"], max_groove_outside_keel_m=worst["groove"], where=worst,
                keel_water_minus_keel_m=kw, draft_m=k["draft"],
                note_ja="t* の near の、船の支えにかかる列（当て布の重み > 0.01 か、行 0 が竜骨から outer + 3 m の内）で、継ぎ目から 8 m の内の y(s) の本当の山・谷（±1 m の中で最も高い・低い所）の"
                        "高さ（±1 m の両側の低い方・高い方からの差。正が稜、負が溝）の最大。右の高い波の稜（面の座標 q の ±2 m）は自然の頂なので数えない。竜骨の足跡（inner_m）の内は数えない。keel_water_minus_keel_m は竜骨の 11 点の真下に最も近い near の頂点の高さ − 竜骨（喫水 %.3f m が理想）。" % k["draft"])


# ---------------------------------------------------------------- kink
def kinks(near, P, t_all, tau_all, rows_s=12.0):
    frames = np.arange(0, int(round(14.0 * 30)) + 1) / 30.0
    taus = np.interp(frames, t_all, tau_all)
    X0 = near.layer(near.L - 1)
    s0 = np.concatenate([np.zeros((1, X0.shape[1])), np.cumsum(np.linalg.norm(np.diff(X0[..., [0, 2]], axis=0), axis=-1), axis=0)], 0)
    nr = int(min(near.R, np.max(np.nonzero((s0 < rows_s).any(1))[0]) + 1))
    rows = slice(0, nr)
    Y = np.zeros((len(taus), nr, near.C))
    slope = np.zeros(len(taus))
    slope_at = []
    for fi, tau in enumerate(taus):
        Xw = near.at(float(tau), rows=rows)
        Y[fi] = Xw[..., 1]
        dxz = np.linalg.norm(np.diff(Xw[..., [0, 2]], axis=0), axis=-1)
        dy = np.abs(np.diff(Xw[..., 1], axis=0))
        sm = 0.5 * (s0[1:nr] + s0[:nr - 1])
        ang = np.degrees(np.arctan2(dy, np.maximum(dxz, 1e-6)))
        ang = np.where((sm > 1.0) & (sm < rows_s), ang, 0.0)
        slope[fi] = ang.max()
        r, c = np.unravel_index(np.argmax(ang), ang.shape)
        slope_at.append((int(r), int(c)))
    d2 = np.abs(Y[2:] - 2 * Y[1:-1] + Y[:-2])
    m = np.unravel_index(np.argmax(d2), d2.shape)
    per_frame = d2.reshape(d2.shape[0], -1).max(1)
    win = (taus[1:-1] >= -3.1) & (taus[1:-1] <= -2.4)
    return dict(rows_in_band=nr, max_d2_m_per_frame2=float(d2.max()), max_at=dict(frame=int(m[0] + 1), tau=float(taus[m[0] + 1]), row=int(m[1]), col=int(m[2])),
                p999_d2=float(np.percentile(d2, 99.9)), frames_over_005=int((per_frame > 0.05).sum()),
                window_tau_m3p1_m2p4_max_d2=float(per_frame[win].max()) if win.any() else None,
                max_slope_deg=float(slope.max()), max_slope_frame=int(np.argmax(slope)), max_slope_at=slope_at[int(np.argmax(slope))],
                window_max_slope_deg=float(slope[1:-1][win].max()) if win.any() else None,
                note_ja="near の継ぎ目から %.0f m の内の行の頂点の y の 30 Hz の二階差分（m／コマ²、t 0〜14 s、G_p28rec の時間曲線）と、"
                        "線分に沿う傾きの最大（継ぎ目から 1 m より外）。窓は設計30 の限界 2 の τ −3.1〜−2.4 s。" % rows_s)


# ---------------------------------------------------------------- fuji
def painting_cam():
    spec = S.load_json(os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json"))
    pc = spec["painting_cam"]
    cam = np.array(pc["position"], float); tgt = np.array(pc["target"], float)
    fw = (tgt - cam) / np.linalg.norm(tgt - cam)
    rt = np.cross([0, 1, 0], fw); rt /= np.linalg.norm(rt)
    up = np.cross(fw, rt)
    th = math.tan(math.radians(pc["vertical_fov_deg"] / 2))
    return cam, fw, rt, up, th


def project(Pw, camspec):
    cam, fw, rt, up, th = camspec
    d = Pw - cam
    z = d @ fw; x = d @ rt; y = d @ up
    asp = W / H
    with np.errstate(divide="ignore", invalid="ignore"):
        sx = (x / (z * th * asp) * 0.5 + 0.5) * W
        sy = (0.5 - y / (z * th) * 0.5) * H
    return sx, sy, z


def envelope(Pw, camspec, x0, x1):
    """網の頂点と辺の中点の投影で、画面の列 x0〜x1 の各列の最も上の y（なければ +inf）。"""
    R, Cn, _ = Pw.shape
    pts = [Pw.reshape(-1, 3), (0.5 * (Pw[1:] + Pw[:-1])).reshape(-1, 3), (0.5 * (Pw[:, 1:] + Pw[:, :-1])).reshape(-1, 3),
           (0.25 * (Pw[1:, 1:] + Pw[:-1, :-1] + Pw[1:, :-1] + Pw[:-1, 1:])).reshape(-1, 3)]
    Q = np.concatenate(pts)
    sx, sy, z = project(Q, camspec)
    m = (z > 0.5) & (sx >= x0) & (sx < x1 + 1)
    env = np.full(x1 - x0 + 1, np.inf)
    xi = np.clip(np.floor(sx[m]).astype(int) - x0, 0, x1 - x0)
    np.minimum.at(env, xi, sy[m])
    return env


def fuji(hero, near, far, idx, P, t_all, tau_all, snow_png, t1=10.5, dt=0.25):
    from PIL import Image
    im = np.asarray(Image.open(snow_png).convert("RGB")).astype(int)
    mask = (np.abs(im[..., 0] - 252) < 6) & (np.abs(im[..., 1] - 249) < 6) & (np.abs(im[..., 2] - 230) < 8)
    mask[:600] = False; mask[800:] = False; mask[:, :1050] = False; mask[:, 1350:] = False
    ys, xs = np.nonzero(mask)
    x0, x1 = int(xs.min()) - 40, int(xs.max()) + 40
    camspec = painting_cam()
    jb, je = idx["body_cols"]
    res = []
    # 修正02：--fuji-t1・--fuji-dt で t 5〜12 s を細かく見られるようにした（既定は作る部・修正01 と同じ t 5〜10.5 s の 0.25 s おき＋t*）
    tl = list(np.arange(5.0, t1 + 1e-6, dt))
    for t in tl + ([12.0] if t1 < 12.0 - 1e-6 else []):
        tau = float(np.interp(t, t_all, tau_all))
        envs = {}
        envs["near"] = envelope(near.world(tau), camspec, x0, x1)
        envs["far"] = envelope(far.world(tau, rows=slice(0, 4)), camspec, x0, x1)
        Xh = hero.world(tau)[:, jb:je + 1]
        envs["hero"] = envelope(Xh, camspec, x0, x1)
        env = np.minimum(np.minimum(envs["near"], envs["far"]), envs["hero"])
        vis = ys < env[xs - x0]
        sea_only = np.minimum(envs["near"], envs["far"])
        vis_sea = ys < sea_only[xs - x0]
        res.append(dict(t=float(t), tau=tau, snow_px=int(len(ys)), snow_visible_frac=float(vis.mean()), snow_visible_frac_sea_only=float(vis_sea.mean()),
                        sea_top_y_over_snow_cols=float(np.min(sea_only[(xs.min() - x0):(xs.max() - x0 + 1)])),
                        hero_top_y_over_snow_cols=float(np.min(envs["hero"][(xs.min() - x0):(xs.max() - x0 + 1)]))))
    return dict(snow_mask_from=os.path.relpath(snow_png, REPO).replace("\\", "/"), snow_px=int(len(ys)), snow_x=[int(xs.min()), int(xs.max())], snow_y=[int(ys.min()), int(ys.max())],
                frames=res, min_visible_frac_t5_10=float(min(r["snow_visible_frac"] for r in res if r["t"] <= 10.0)),
                min_visible_frac_all=float(min(r["snow_visible_frac"] for r in res)),
                min_visible_frac_sea_only_t5_10=float(min(r["snow_visible_frac_sea_only"] for r in res if r["t"] <= 10.0)),
                note_ja="numpy の投影（原画視点 PaintingCam v1）。網の頂点・辺の中点・四角の中心の投影の列ごとの最も上の y を網の上の縁とし、富士の雪の印（仕上げ29 の t* の"
                        "原画視点の描画で、雪の色 (252,249,230) ±6 の画素）のうち縁より上に残る割合。sea_only は主役波を数えない（主役波が隠す分は仕上げ30 の責任の外）。")


# ---------------------------------------------------------------- boat heave（設計30 と同じ読み）
def vertical_hits(V, T, q):
    P0 = V[T[:, 0]]; P1 = V[T[:, 1]]; P2 = V[T[:, 2]]
    xmin = np.minimum(np.minimum(P0[:, 0], P1[:, 0]), P2[:, 0]); xmax = np.maximum(np.maximum(P0[:, 0], P1[:, 0]), P2[:, 0])
    zmin = np.minimum(np.minimum(P0[:, 2], P1[:, 2]), P2[:, 2]); zmax = np.maximum(np.maximum(P0[:, 2], P1[:, 2]), P2[:, 2])
    fn = np.cross(P1 - P0, P2 - P0)
    hits = []
    for x, z in q:
        s = np.nonzero((xmin <= x) & (x <= xmax) & (zmin <= z) & (z <= zmax))[0]
        hl = []
        if len(s):
            a, b, c = P0[s], P1[s], P2[s]
            d = (b[:, 2] - c[:, 2]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 2] - c[:, 2])
            ok = np.abs(d) > 1e-12
            l1 = np.where(ok, ((b[:, 2] - c[:, 2]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (z - c[:, 2])) / np.where(ok, d, 1), -1)
            l2 = np.where(ok, ((c[:, 2] - a[:, 2]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (z - c[:, 2])) / np.where(ok, d, 1), -1)
            l3 = 1 - l1 - l2
            ins = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
            y = l1 * a[:, 1] + l2 * b[:, 1] + l3 * c[:, 1]
            for k in np.nonzero(ins)[0]:
                hl.append((float(y[k]), float(np.sign(fn[s[k], 1]))))
        hits.append(hl)
    return hits


def boat_heave(hero, near, far, idx, feat, P, t_all, tau_all, tw):
    frames = np.arange(0, int(round(float(t_all[-1]) * 30)) + 1) / 30.0
    taus = np.interp(frames, t_all, tau_all)
    seat = S.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
    eye = np.array(seat["seat"]["eye_world"])
    keel = feat.keel
    kxz = keel["xz"]; kyl = keel["y"]
    jb, je = idx["body_cols"]
    Th = grid_tris(hero.R, hero.C, jb, je)
    Tn = grid_tris(near.R, near.C); Tf = grid_tris(far.R, far.C)
    Tf = Tf[: (far.R - 2) * (far.C - 1) * 2]
    centre = np.array([kxz[:, 0].mean(), kxz[:, 1].mean()])
    rows = []
    cache = {}
    for fi, tau in enumerate(taus):
        tau = float(tau)
        key = round(tau, 9)
        if key not in cache:
            Vs, Ts = [], []
            off = 0
            for pk, T in ((hero, Th), (near, Tn), (far, Tf)):
                Vw = pk.world(tau).reshape(-1, 3)
                d = np.hypot(Vw[:, 0] - centre[0], Vw[:, 2] - centre[1])
                kt = (d < 40.0)[T].any(1)
                Vs.append(Vw); Ts.append(T[kt] + off); off += len(Vw)
            V = np.concatenate(Vs); T = np.concatenate(Ts)
            q = np.concatenate([kxz, eye[None, [0, 2]]], 0)
            cache[key] = vertical_hits(V, T, q)
        hits = cache[key]
        wy = []
        for k in range(len(kxz)):
            ups = [y for (y, sg) in hits[k] if sg > 0]
            wy.append(min(ups, key=lambda y: abs(y - kyl[k])) if ups else np.nan)
        rows.append(dict(t=float(frames[fi]), tau=tau, keel_water=wy, eye_hits=hits[-1]))
    ew0 = max([y for (y, sg) in rows[-1]["eye_hits"] if sg > 0 and y <= eye[1]], default=0.0)
    ew = np.array([min([y for (y, sg) in r["eye_hits"] if sg > 0] or [ew0], key=lambda y: abs(y - ew0)) for r in rows])
    raw = ew - ew0
    n = max(1, int(round(P["boat"]["smooth_s"] * 30)))
    ker = np.ones(2 * n + 1) / (2 * n + 1)
    delta = np.convolve(np.pad(raw, n, mode="edge"), ker, mode="valid")
    first0 = int(np.nonzero(taus >= -1e-9)[0][0])
    delta = delta - delta[first0]
    delta[first0:] = 0.0
    for fi, r in enumerate(rows):
        for mode, dy in (("heave", float(delta[fi])), ("static", 0.0)):
            ey = eye[1] + dy
            kim = [None if not np.isfinite(v) else float(v - (kyl[k] + dy)) for k, v in enumerate(r["keel_water"])]
            above = [(y, sg) for (y, sg) in r["eye_hits"] if y > ey]
            below = [(y, sg) for (y, sg) in r["eye_hits"] if y <= ey]
            under_water = bool(above and min(above)[1] > 0)
            wbelow = max([y for (y, sg) in below if sg > 0], default=np.nan)
            r[mode] = dict(eye_y=ey, under_water=under_water, clearance_to_water_below_m=float(ey - wbelow) if np.isfinite(wbelow) else None, keel_immersion_m=kim)
    rec = dict(schema="GreatWave.DS30.boat_support/1", number="仕上げ30", boat="boat_mid（seat_v1）", eye_world_tstar=eye.tolist(),
               eye_above_deck_m=seat["seat"]["eye_above_deck_m"], deck_world_tstar=seat["seat"]["deck_hit_world"],
               note_ja="30 Hz のコマ（G_p28rec の時間曲線、t = 0 は τ %.3f、t* = %.1f s、その後は保持）。keel_water は竜骨の線（seat_v1 の water_contact、11 点）の下の水面"
                       "（主役波の本体・near・far の網の上向きの面のうち竜骨に最も近い高さ）。delta_m は目の点の下の水面の t* からの差を %.1f s の窓でならし、t* 以後は 0"
                       "（設計30 の修正1 と同じ。設計30 の boat_support.json の説明の「0.1 s」は誤りで、値は smooth_s）。heave は船と目 = t* の位置 + delta（姿勢は t* のまま）。"
                       % (taus[0], tw["t_star_s"], P["boat"]["smooth_s"]),
               frames=[dict(t=r["t"], tau=r["tau"], delta_m=float(delta[i]), keel_water_m=[None if not np.isfinite(v) else float(v) for v in r["keel_water"]],
                            heave=r["heave"], static=r["static"]) for i, r in enumerate(rows)],
               keel_line=dict(y=[float(v) for v in kyl], draft_m=keel["draft"], xz=kxz.tolist()))
    hv = [f["heave"] for f in rec["frames"]]
    cl_h = [f["clearance_to_water_below_m"] for f in hv if f["clearance_to_water_below_m"] is not None]
    rec["summary"] = dict(frames=len(rows), heave_under_water_frames=int(sum(f["under_water"] for f in hv)),
                          heave_min_clearance_m=float(min(cl_h)) if cl_h else None, delta_range_m=[float(delta.min()), float(delta.max())],
                          delta_max_accel_m_per_s2=float(np.abs(np.diff(delta, 2)).max() * 900.0),
                          tstar_keel_water_minus_keel_m=[None if not np.isfinite(v) else float(v - kyl[k]) for k, v in enumerate(rows[first0]["keel_water"])])
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sea", default="Unity/Build/Polish/30/sea")
    ap.add_argument("--out", default="Unity/Build/Polish/30/checks_final")
    ap.add_argument("--params", default=S.PARAMS)
    ap.add_argument("--skip", default="")
    ap.add_argument("--snow", default="Unity/Build/Polish/29/fix01/p29g/views/painting_t120_asis.png")
    ap.add_argument("--fuji-t1", type=float, default=10.5)
    ap.add_argument("--fuji-dt", type=float, default=0.25)
    args = ap.parse_args()
    skip = set(args.skip.split(",")) if args.skip else set()
    t0 = time.time()
    P = S.load_json(args.params)
    sd = os.path.join(REPO, args.sea)
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    hero_s = S.Hero(P)
    hero = Pkg(hero_s.dir)
    near = Pkg(os.path.join(sd, "near")); far = Pkg(os.path.join(sd, "far"))
    idx = S.load_json(os.path.join(sd, "near", "ds30_ring0_index.json"))
    t_all, tau_all, tw = timewarp(P)
    same = bool(np.array_equal(near.knots, hero.knots))
    M = dict(number="仕上げ30", schema="GreatWave.PL30.checks/1", renderer_ja="numpy（Unity の描画ではない）", sea=args.sea, hero=os.path.relpath(hero.dir, REPO).replace("\\", "/"),
             near_knots_same_as_hero=same, near_layers=near.L, near_rows=near.R, near_cols=near.C, far_rows=far.R, far_cols=far.C)
    feat = None
    if not ({"boat", "boatheave"} <= skip):
        feat = S.Features(hero_s, P)
    if "seam" not in skip:
        if same:
            M["seam"] = seam(hero, near, far, idx, P)
        else:
            # 設計30 の海（F_final の 242 節点）と G_p28rec の主役波：τ で読んだ境の輪の隔たり（仕上げ28 の 4.134 m と同じ読み）
            loop = np.array([[d["hero_row"], d["hero_col"]] for d in idx["loop"]])
            NL = len(loop)
            worst = 0.0
            for tau in np.linspace(hero.knots[0], 0.0, 121):
                Xh = hero.world(float(tau)); Xn = near.world(float(tau), rows=slice(0, 1))
                worst = max(worst, float(np.abs(Xh[loop[:, 0], loop[:, 1]] - Xn[0, :NL]).max()))
            M["seam"] = dict(ring0_max_diff_m=worst, note_ja="節点の時刻が違う（設計30 の海は F_final の 242 節点）ので、τ の 121 点で読んだ隔たりの最大。")
        print("seam", json.dumps(M["seam"], ensure_ascii=False)[:600])
    if "boat" not in skip and feat is not None:
        M["boat_patch"] = boat_ridge(hero, near, feat, P, os.path.join(sd, "near", "pl30_sea_attr_f32.bin"))
        print("boat", json.dumps({k: v for k, v in M["boat_patch"].items() if k != "note_ja"}, ensure_ascii=False)[:800])
    if "kink" not in skip:
        M["kink"] = kinks(near, P, t_all, tau_all)
        print("kink", json.dumps({k: v for k, v in M["kink"].items() if k != "note_ja"}, ensure_ascii=False)[:800])
    if "fuji" not in skip:
        M["fuji"] = fuji(hero, near, far, idx, P, t_all, tau_all, os.path.join(REPO, args.snow), args.fuji_t1, args.fuji_dt)
        print("fuji", json.dumps({k: v for k, v in M["fuji"].items() if k not in ("frames", "note_ja")}, ensure_ascii=False))
        for r in M["fuji"]["frames"]:
            print("  t %.2f vis %.3f vis_sea %.3f sea_top %.0f hero_top %.0f" % (r["t"], r["snow_visible_frac"], r["snow_visible_frac_sea_only"], r["sea_top_y_over_snow_cols"], r["hero_top_y_over_snow_cols"]))
    if "boatheave" not in skip and same and feat is not None:
        rec = boat_heave(hero, near, far, idx, feat, P, t_all, tau_all, tw)
        S.save_json(os.path.join(sd, "boat_support.json"), rec)
        M["boat_heave"] = rec["summary"]
        print("heave", json.dumps(rec["summary"], ensure_ascii=False))
    M["seconds"] = round(time.time() - t0, 1)
    S.save_json(os.path.join(out, "pl30_checks.json"), M)
    print("done", M["seconds"], "s")


if __name__ == "__main__":
    main()
