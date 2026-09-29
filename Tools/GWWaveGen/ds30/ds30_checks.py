# -*- coding: utf-8 -*-
"""設計30：周りの海のシートの検査（numpy。Unity の描画ではない）。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/ds30/ds30_checks.py [--sea Unity/Build/Design/30/sea] [--out Unity/Build/Design/30/checks] [--skip raster]
測るもの（metrics は <out>/ds30_checks.json）:
  1 継ぎ目：near の行 0 と主役波の本体の境の輪（各節点、精度の層あり・なし）、near の外周と far の行 0、T 字の点の線形補間の残り。
  2 接続帯の連続：輪 0 の各辺で、主役波の隣の四角と near の最初の四角の面の法線の内積（各節点）。継ぎ目の頂点の速度の差
    （節点の中心差分＝再生の Hermite の傾き）。高さの差（継ぎ目の頂点どうし）。
  3 面の裏返り（+y を向かない面）の数と場所（各節点）。
  4 外周：主役波の本体・near・far をつないだ面の自由な縁（1 つの三角形にしか属さない辺）のうち、y > −7 m のもの（各節点）。
  5 再生の開始・終了：F_final の時間曲線（timewarp_F_final.json、30 Hz）で、コマの間の頂点の動きの最大と、開始・終了のコマの値。
  6 座席の船の支え（boat_support.json）：竜骨の線の 11 点の下の水面（主役波・near・far の網から）、Δ(τ)、目の余裕（上下する目と
    t* のまま止めた目の両方）。目が水の中かは、目の真上の最も近い面が上向き（水面の下）か下向き（唇の下の空気）かで決める。
  7 t* の原画視点（PaintingCam v1）の回帰：z バッファの ID の描画で、前（29修正01 の場面：主役波の全体・平らな海・仮置き）と後
    （主役波の本体・near・far・残す仮置き）の、主役波の見える画素と空の画素の違いを数え、評価器の項目の範囲ごとに記録する。
  8 図：t* の平面図、原画視点と座席から波の方向の静止画（numpy の描画、段階の τ）。
"""
import argparse
import json
import math
import os
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds30_sea as S  # noqa: E402

REPO = S.REPO
sys.path.insert(0, os.path.join(REPO, "Tools", "GWContext"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds27"))
import af27common as C27  # noqa: E402
from ds27_player_ref import hermite_weights  # noqa: E402

W, H = 1920, 1080


# ---------------------------------------------------------------- パッケージ
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

    def layer(self, i, fine=True, rows=None, cols=None):
        rs = slice(None) if rows is None else rows
        cs = slice(None) if cols is None else cols
        q = self.hi[i, rs, cs, :3].astype(np.float64)
        if fine:
            q = q + self.lo[i, rs, cs, :3].astype(np.float64) / 255.0 - 0.5
        return self.bmin + q / 65535.0 * self.bsz

    def origin(self, tau):
        return np.array([np.interp(tau, self.ft, self.fo[:, j]) for j in range(3)])

    def at(self, tau, fine=True):
        idx, w = hermite_weights(self.knots, tau)
        X = sum(wi * self.layer(ii, fine) for ii, wi in zip(idx, w) if wi != 0.0)
        return X

    def world(self, tau, fine=True):
        return self.at(tau, fine) + self.origin(tau)[None, None, :]


def grid_tris(R, Cn, c0=0, c1=None):
    c1 = Cn - 1 if c1 is None else c1
    r, c = np.meshgrid(np.arange(R - 1), np.arange(c0, c1), indexing="ij")
    a = (r * Cn + c).ravel(); b = ((r + 1) * Cn + c).ravel(); cc = (r * Cn + c + 1).ravel(); d = ((r + 1) * Cn + c + 1).ravel()
    return np.stack([np.stack([a, b, cc], 1), np.stack([cc, b, d], 1)], 1).reshape(-1, 3)


def face_normals(V, T):
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    return fn


# ---------------------------------------------------------------- 1〜4
def seam_checks(hero, near, far, idx, fs):
    loop = np.array([[d["hero_row"], d["hero_col"]] for d in idx["loop"]])
    NL = len(loop)
    jb, je = idx["body_cols"]
    res = dict(seam_fine_max_m=0.0, seam_hi_only_max_m=0.0, nearfar_max_m=0.0, tjunction_resid_max_m=0.0,
               normal_dot=[], vel_diff_max_mps=0.0, flips=[], free_edges_above=[])
    kn = hero.knots
    Tn = grid_tris(near.R, near.C)
    Tf = grid_tris(far.R, far.C)
    ndots_all = []
    worst = []
    prevN = prevH = None
    vel_worst = 0.0
    # 主役波の本体の網の三角形（列 jb〜je の四角）
    Th = grid_tris(hero.R, hero.C, jb, je)
    for i in range(hero.L):
        Xh = hero.layer(i)
        Xn = near.layer(i)
        Xf = far.layer(i)
        Xn_hi = near.layer(i, fine=False)
        Xh_hi = hero.layer(i, fine=False)
        ring_h = Xh[loop[:, 0], loop[:, 1]]
        res["seam_fine_max_m"] = max(res["seam_fine_max_m"], float(np.abs(Xn[0, :NL] - ring_h).max()))
        res["seam_hi_only_max_m"] = max(res["seam_hi_only_max_m"], float(np.abs(Xn_hi[0, :NL] - Xh_hi[loop[:, 0], loop[:, 1]]).max()))
        res["nearfar_max_m"] = max(res["nearfar_max_m"], float(np.abs(Xf[0, :-1] - Xn[-1, 0:NL:fs]).max()))
        o = Xn[-1, :NL]
        m = np.arange(NL)
        j0 = (m // fs) * fs; j1 = (j0 + fs) % NL; s = (m - j0) / fs
        lin = (1 - s)[:, None] * o[j0] + s[:, None] * o[j1]
        res["tjunction_resid_max_m"] = max(res["tjunction_resid_max_m"], float(np.abs(lin - o).max()))
        # 法線の内積：輪 0 の各頂点で、主役波の側の面だけから作った法線（面積の重み）と、near の側（行 0〜1 の帯）の面だけから作った法線
        if i == 0:
            vid = loop[:, 0] * hero.C + loop[:, 1]
            Tn0 = grid_tris(2, near.C)
        Vh = Xh.reshape(-1, 3)
        fh = face_normals(Vh, Th)
        nh = np.zeros_like(Vh)
        for kk in range(3):
            np.add.at(nh, Th[:, kk], fh)
        hv = nh[vid]
        Vn2 = Xn[:2].reshape(-1, 3)
        fn2 = face_normals(Vn2, Tn0)
        nn2 = np.zeros_like(Vn2)
        for kk in range(3):
            np.add.at(nn2, Tn0[:, kk], fn2)
        nv = nn2[:NL].copy()
        nv[0] += nn2[NL]                               # 閉じる列の写しの分を足す
        la = np.linalg.norm(nv, axis=1); lb = np.linalg.norm(hv, axis=1)
        ok = (la > 1e-4) & (lb > 1e-4)
        dots = np.full(NL, np.nan)
        dots[ok] = (nv[ok] * hv[ok]).sum(1) / (la[ok] * lb[ok])
        ndots_all.append(dots)
        # 裏返り（+y を向かない面）
        fnn = face_normals(Xn.reshape(-1, 3), Tn)
        fnf = face_normals(Xf.reshape(-1, 3), Tf)
        area_n = np.linalg.norm(fnn, axis=1)
        flips_n = int(((fnn[:, 1] <= 0) & (area_n > 1e-6)).sum())
        nf_tris = Tf[: (far.R - 2) * (far.C - 1) * 2]                   # すそ（最後の行の四角）を除く
        fnf2 = face_normals(Xf.reshape(-1, 3), nf_tris)
        flips_f = int(((fnf2[:, 1] <= 0) & (np.linalg.norm(fnf2, axis=1) > 1e-6)).sum())
        res["flips"].append([float(kn[i]), flips_n, flips_f])
        # 速度の差（継ぎ目の頂点、節点の中心差分）
        if 0 < i < hero.L - 1:
            pass
    ND = np.array(ndots_all)
    fin = ND[np.isfinite(ND)]
    res["normal_dot"] = dict(min=float(fin.min()), p001=float(np.percentile(fin, 0.1)), p01=float(np.percentile(fin, 1)),
                             p05=float(np.percentile(fin, 5)), median=float(np.median(fin)), n=int(fin.size),
                             n_degenerate=int((~np.isfinite(ND)).sum()))
    # 最悪の場所
    wi = np.nanargmin(ND)
    li, jj = np.unravel_index(wi, ND.shape)
    res["normal_dot"]["worst"] = dict(tau=float(kn[li]), near_col=int(jj), hero_rc=[int(v) for v in loop[jj]], dot=float(ND[li, jj]))
    # 帯ごと（前・後・両端の扇）
    kinds = np.array([d["ray"] for d in idx["loop"]])
    res["normal_dot"]["by_ray_kind"] = {kd: dict(min=float(np.nanmin(ND[:, kinds == kd])), p1=float(np.nanpercentile(ND[:, kinds == kd], 1)))
                                        for kd in ("front", "back", "fanL", "fanR")}
    # 船の支えの帯（船体の下）とそれ以外に分ける：near の行 1 の点の船の支えの重み > 0.02
    feat = S.Features(S.Hero())
    bw = np.zeros_like(ND)
    for i in range(hero.L):
        X1 = near.layer(i, rows=slice(1, 2))[0, :NL]
        sh = feat.shape(X1[:, 0] * feat.h.t[0] + X1[:, 2] * feat.h.t[2], X1[:, 0] * feat.h.e[0] + X1[:, 2] * feat.h.e[2])
        bw[i] = sh.get("boat_w", np.zeros(NL))
    for kd in ("front", "back"):
        m = (kinds == kd)[None, :] & np.isfinite(ND)
        a_ = ND[m & (bw <= 0.02)]; b_ = ND[m & (bw > 0.02)]
        res["normal_dot"]["by_ray_kind"][kd].update(dict(outside_boat_min=float(a_.min()), outside_boat_p1=float(np.percentile(a_, 1)),
                                                          outside_boat_n=int(a_.size), under_boat_min=float(b_.min()) if b_.size else None,
                                                          under_boat_n=int(b_.size)))
    wj = np.nanargmin(np.where((kinds == "front")[None, :] & (bw <= 0.02), ND, np.inf))
    li, jj = np.unravel_index(wj, ND.shape)
    res["normal_dot"]["front_outside_boat_worst"] = dict(tau=float(kn[li]), near_col=int(jj), hero_rc=[int(v) for v in loop[jj]], dot=float(ND[li, jj]))
    # 速度：継ぎ目の頂点の中心差分（主役波と near）
    vmax = 0.0
    for i in range(1, hero.L - 1):
        dt = kn[i + 1] - kn[i - 1]
        vh = (hero.layer(i + 1)[loop[:, 0], loop[:, 1]] - hero.layer(i - 1)[loop[:, 0], loop[:, 1]]) / dt
        vn = (near.layer(i + 1)[0, :NL] - near.layer(i - 1)[0, :NL]) / dt
        vmax = max(vmax, float(np.abs(vh - vn).max()))
    res["vel_diff_max_mps"] = vmax
    return res


def free_edges_check(hero, near, far, idx, taus):
    """主役波の本体・near・far をつないだ面の自由な縁（y > −7 m）。near の外周と far の行 0 は T 字の継ぎ目として覆われる扱い。"""
    jb, je = idx["body_cols"]
    out = []
    for tau in taus:
        # 自由な縁は網の位相だけで決まる：主役波の本体の境（輪 0）は near の行 0 と共有、near の外周は far の行 0 と共有（T 字）、
        # far の最後の行（すそ）だけが自由。すその高さを測る。
        Xf = far.world(tau)
        skirt = Xf[-1]
        out.append(dict(tau=float(tau), free_edges_topology=int(far.C - 1), free_edge_y_max_m=float(skirt[:, 1].max()),
                        free_edges_above_minus7=int((skirt[:, 1] > -7.0).sum())))
    return out


# ---------------------------------------------------------------- 面の高さ（鉛直の線と網の交わり）
def vertical_hits(V, T, q):
    """q：(m, 2) の (x, z)。各点の鉛直の線と三角形の交わりの (y, 法線の y の符号) のリスト。"""
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


def boat_support(hero, near, far, idx, feat, P):
    tw = S.load_json(os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "F_final", "timewarp_F_final.json"))
    t_all = np.array(tw["t"]); tau_all = np.array(tw["tau"])
    t_end = float(t_all[-1])
    frames = np.arange(0, int(round(t_end * 30)) + 1) / 30.0
    taus = np.interp(frames, t_all, tau_all)
    seat = S.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
    eye = np.array(seat["seat"]["eye_world"])
    keel = feat.keel
    kxz = keel["xz"]
    kyl = keel["y"]
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
                keep_v = d < 40.0
                kt = keep_v[T].any(1)
                Vs.append(Vw); Ts.append(T[kt] + off); off += len(Vw)
            V = np.concatenate(Vs); T = np.concatenate(Ts)
            q = np.concatenate([kxz, eye[None, [0, 2]]], 0)
            hits = vertical_hits(V, T, q)
            cache[key] = hits
        hits = cache[key]
        # 竜骨の点の水面：上向きの面のうち、竜骨の点に最も近い高さ
        wy = []
        for k in range(len(kxz)):
            ups = [y for (y, sg) in hits[k] if sg > 0]
            wy.append(min(ups, key=lambda y: abs(y - kyl[k])) if ups else np.nan)
        rows.append(dict(t=float(frames[fi]), tau=tau, keel_water=wy, eye_hits=hits[-1]))
    kw = np.array([r["keel_water"] for r in rows])
    # 目の点の下の水面（上向きの面のうち、t* の目の下の水面に最も近い高さ）
    ew0 = max([y for (y, sg) in rows[-1]["eye_hits"] if sg > 0 and y <= eye[1]], default=0.0)
    ew = []
    for r in rows:
        ups = [y for (y, sg) in r["eye_hits"] if sg > 0]
        ew.append(min(ups, key=lambda y: abs(y - ew0)) if ups else ew0)
    ew = np.array(ew)
    raw = ew - ew0
    # 修正1：Δ は目の点（座席）の下の水面の t* からの差（竜骨の 11 点の平均では、t* で 33° 傾いた船の目が船尾の側にあるため、
    # 平らな海で目が水面より下がった）。0.1 s の窓でならす。t* 以後は 0
    n = max(1, int(round(P["boat"]["smooth_s"] * 30)))
    ker = np.ones(2 * n + 1) / (2 * n + 1)
    pad = np.pad(raw, n, mode="edge")
    delta = np.convolve(pad, ker, mode="valid")
    tstar_frame = int(np.argmin(np.abs(taus - 0.0)))
    first0 = int(np.nonzero(taus >= -1e-9)[0][0])
    delta = delta - delta[first0]
    delta[first0:] = 0.0
    # 目の余裕：目の真上の最も近い面が上向きなら水の中
    out = []
    for fi, r in enumerate(rows):
        for mode, dy in (("heave", float(delta[fi])), ("static", 0.0)):
            ey = eye[1] + dy
            kim = [None if not np.isfinite(v) else float(v - (kyl[k] + dy)) for k, v in enumerate(r["keel_water"])]
            above = [(y, sg) for (y, sg) in r["eye_hits"] if y > ey]
            below = [(y, sg) for (y, sg) in r["eye_hits"] if y <= ey]
            under_water = bool(above and min(above)[1] > 0)
            wbelow = max([y for (y, sg) in below if sg > 0], default=np.nan)
            r.setdefault(mode, dict(eye_y=ey, under_water=under_water, clearance_to_water_below_m=float(ey - wbelow) if np.isfinite(wbelow) else None,
                                    keel_immersion_m=kim))
    rec = dict(schema="GreatWave.DS30.boat_support/1", boat="boat_mid（seat_v1）", eye_world_tstar=eye.tolist(),
               eye_above_deck_m=seat["seat"]["eye_above_deck_m"], deck_world_tstar=seat["seat"]["deck_hit_world"],
               note_ja="30 Hz のコマ（F_final の時間曲線、t = 0 は τ %.3f、t* = %.1f s、その後は保持）。keel_water は竜骨の線（seat_v1 の water_contact、"
                       "11 点）の下の水面（主役波の本体・near・far の網の上向きの面のうち竜骨に最も近い高さ）。delta_m = 竜骨の水面の t* からの差の平均を "
                       "（修正1 で）目の点の下の水面の t* からの差を 0.1 s の窓でならし、t* 以後は 0。heave は船と目 = t* の位置 + delta（姿勢は t* のまま）、static は t* のまま止めたもの。keel_immersion_m は竜骨の各点の（水面 − 竜骨）。under_water は目の真上の"
                       "最も近い面が上向き（水面の下）のとき true（唇の下の空気は下向きの面）。" % (taus[0], tw["t_star_s"]),
               frames=[dict(t=r["t"], tau=r["tau"], delta_m=float(delta[i]), keel_water_m=[None if not np.isfinite(v) else float(v) for v in r["keel_water"]],
                            heave=r["heave"], static=r["static"]) for i, r in enumerate(rows)],
               keel_line=dict(y=[float(v) for v in kyl], draft_m=keel["draft"], xz=kxz.tolist()))
    hv = [f["heave"] for f in rec["frames"]]; st = [f["static"] for f in rec["frames"]]
    cl_h = [f["clearance_to_water_below_m"] for f in hv if f["clearance_to_water_below_m"] is not None]
    cl_s = [f["clearance_to_water_below_m"] for f in st if f["clearance_to_water_below_m"] is not None]
    kt = np.array(rec["frames"][tstar_frame]["keel_water_m"], dtype=float)
    def kimr(mode):
        v = np.array([[np.nan if x is None else x for x in f[mode]["keel_immersion_m"]] for f in rec["frames"]], float)
        return dict(bow_min=float(np.nanmin(v[:, 0])), bow_max=float(np.nanmax(v[:, 0])), stern_min=float(np.nanmin(v[:, -1])), stern_max=float(np.nanmax(v[:, -1])),
                    all_min=float(np.nanmin(v)), all_max=float(np.nanmax(v)))
    summ = dict(frames=len(rows), heave_under_water_frames=int(sum(f["under_water"] for f in hv)), static_under_water_frames=int(sum(f["under_water"] for f in st)),
                heave_min_clearance_m=float(min(cl_h)) if cl_h else None, static_min_clearance_m=float(min(cl_s)) if cl_s else None,
                delta_range_m=[float(delta.min()), float(delta.max())], delta_max_step_m_per_frame=float(np.abs(np.diff(delta)).max()),
                delta_max_accel_m_per_s2=float(np.abs(np.diff(delta, 2)).max() * 900.0),
                keel_immersion_heave=kimr("heave"), keel_immersion_static=kimr("static"),
                tstar_keel_immersion_m=[None if not np.isfinite(v) else float(v) for v in (kt - (kyl))],
                tstar_keel_minus_water_note_ja="t* の竜骨の各点の（水面 − 竜骨）。喫水 %.3f m なら理想。負は船底が水面より上（浮いている）。" % keel["draft"])
    rec["summary"] = summ
    return rec


# ---------------------------------------------------------------- z バッファの描画
def raster_ids(cam, tris, ids, near_clip=0.1):
    """tris：(N,3,3) ワールド、ids：(N,) int。戻り値：(H,W) の id（0 = 何もない）と 1/z。"""
    # 近い面（カメラの前 near_clip）で三角形を切る（修正1：切らずに落とすと、カメラの近くで面をまたぐ大きな三角形が消え、穴に見えた）
    d = (tris - cam.pos[None, None, :]) @ cam.f - near_clip
    nin = (d > 0).sum(1)
    keep = [tris[nin == 3]]; kid = [ids[nin == 3]]
    for m_in in (1, 2):
        sel = np.nonzero(nin == m_in)[0]
        if not len(sel):
            continue
        T3 = tris[sel]; D3 = d[sel]
        for k in range(len(sel)):
            P3, D = T3[k], D3[k]
            poly = []
            for a in range(3):
                b = (a + 1) % 3
                if D[a] > 0:
                    poly.append(P3[a])
                if (D[a] > 0) != (D[b] > 0):
                    tt = D[a] / (D[a] - D[b])
                    poly.append(P3[a] + tt * (P3[b] - P3[a]))
            for q in range(1, len(poly) - 1):
                keep.append(np.array([[poly[0], poly[q], poly[q + 1]]])); kid.append(ids[sel[k]:sel[k] + 1])
    tris = np.concatenate(keep); ids = np.concatenate(kid)
    P = tris.reshape(-1, 3)
    xy, z = cam.project(P)
    xy = xy.reshape(-1, 3, 2); z = z.reshape(-1, 3)
    ok = np.all(z > near_clip * 0.5, axis=1)
    xy, z, ids = xy[ok], z[ok], ids[ok]
    iz = 1.0 / z
    x0 = np.floor(xy[..., 0].min(1)).astype(np.int64); x1 = np.ceil(xy[..., 0].max(1)).astype(np.int64)
    y0 = np.floor(xy[..., 1].min(1)).astype(np.int64); y1 = np.ceil(xy[..., 1].max(1)).astype(np.int64)
    vis = (x1 >= 0) & (x0 < W) & (y1 >= 0) & (y0 < H)
    xy, iz, ids, x0, x1, y0, y1 = xy[vis], iz[vis], ids[vis], x0[vis], x1[vis], y0[vis], y1[vis]
    x0 = np.clip(x0, 0, W - 1); x1 = np.clip(x1, 0, W - 1); y0 = np.clip(y0, 0, H - 1); y1 = np.clip(y1, 0, H - 1)
    size = np.maximum(x1 - x0 + 1, y1 - y0 + 1)
    zb = np.zeros(H * W); idb = np.zeros(H * W, np.int32)
    ax, ay = xy[:, 0, 0], xy[:, 0, 1]; bx, by = xy[:, 1, 0], xy[:, 1, 1]; cx, cy = xy[:, 2, 0], xy[:, 2, 1]
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)

    def splat(sel, K):
        if not len(sel):
            return
        oy, ox = np.meshgrid(np.arange(K), np.arange(K), indexing="ij")
        oy = oy.ravel(); ox = ox.ravel()
        step = max(1, 800_000 // (K * K))
        for s0 in range(0, len(sel), step):
            ss = sel[s0:s0 + step]
            px = x0[ss][:, None] + ox[None, :]; py = y0[ss][:, None] + oy[None, :]
            inb = (px <= x1[ss][:, None]) & (py <= y1[ss][:, None])
            d = den[ss][:, None]
            okd = np.abs(d) > 1e-12
            dd = np.where(okd, d, 1.0)
            l1 = ((by[ss][:, None] - cy[ss][:, None]) * (px - cx[ss][:, None]) + (cx[ss][:, None] - bx[ss][:, None]) * (py - cy[ss][:, None])) / dd
            l2 = ((cy[ss][:, None] - ay[ss][:, None]) * (px - cx[ss][:, None]) + (ax[ss][:, None] - cx[ss][:, None]) * (py - cy[ss][:, None])) / dd
            l3 = 1 - l1 - l2
            ins = inb & okd & (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
            if not ins.any():
                continue
            zz = l1 * iz[ss][:, 0:1] + l2 * iz[ss][:, 1:2] + l3 * iz[ss][:, 2:3]
            ti = np.broadcast_to(np.arange(len(ss))[:, None], ins.shape)[ins]
            pix = (py * W + px)[ins]; zv = zz[ins]; iv = ids[ss][ti]
            o = np.lexsort((-zv, pix))
            pix, zv, iv = pix[o], zv[o], iv[o]
            first = np.ones(len(pix), bool); first[1:] = pix[1:] != pix[:-1]
            pix, zv, iv = pix[first], zv[first], iv[first]
            upd = zv > zb[pix]
            zb[pix[upd]] = zv[upd]; idb[pix[upd]] = iv[upd]
    done = np.zeros(len(size), bool)
    for K in (1, 2, 4, 8, 16, 32, 64):
        sel = np.nonzero((~done) & (size <= K))[0]
        splat(sel, K)
        done[sel] = True
    for t in np.nonzero(~done)[0]:
        # 大きな三角形：外接箱の画素を全部調べる
        X, Y = np.meshgrid(np.arange(x0[t], x1[t] + 1), np.arange(y0[t], y1[t] + 1))
        d = den[t]
        if abs(d) < 1e-12:
            continue
        l1 = ((by[t] - cy[t]) * (X - cx[t]) + (cx[t] - bx[t]) * (Y - cy[t])) / d
        l2 = ((cy[t] - ay[t]) * (X - cx[t]) + (ax[t] - cx[t]) * (Y - cy[t])) / d
        l3 = 1 - l1 - l2
        ins = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        zz = l1 * iz[t, 0] + l2 * iz[t, 1] + l3 * iz[t, 2]
        pix = (Y * W + X)[ins]; zv = zz[ins]
        upd = zv > zb[pix]
        zb[pix[upd]] = zv[upd]; idb[pix[upd]] = ids[t]
    return idb.reshape(H, W), zb.reshape(H, W)


def boats_tris():
    L = S.load_json(os.path.join(REPO, "Tools", "GWContext", "context_layout.json"))
    seat = S.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
    g, ms = C27.load_dump("boat_blockout")
    out = []
    for key, b in L["boats"].items():
        pos, q, sc = np.array(b["position"]), b["rotation_quat_xyzw"], b["scale"]
        if key == "boat_mid":
            pos, q, sc = np.array(seat["boat"]["position"]), seat["boat"]["rotation_quat_xyzw"], seat["boat"]["scale"]
        R = C27.quat_to_mat(q)
        for m in ms:
            V = pos[None, :] + (R @ (sc * m["V"]).T).T
            for I in m["subs"]:
                out.append(V[I])
    return np.concatenate(out)


def placeholder_tris():
    L = S.load_json(os.path.join(REPO, "Tools", "GWContext", "context_layout.json"))
    res = {}
    g, ms = C27.load_dump("foam_static")
    for m in ms:
        if m["name"] in ("M1_ForegroundSwell_Static", "M1_ForegroundFoam_Static"):
            res[m["name"]] = [m["V"][I] for I in m["subs"]]
    g, ms = C27.load_dump("revision_slopes")
    for m in ms:
        if m["name"] == "M1_Revision_LeftSupport":
            dy = L["placeholders"]["M1_Revision_LeftSupport"]["translate_y"]
            V = m["V"] + np.array([0, dy, 0])
            res[m["name"]] = [V[I] for I in m["subs"]]
    raw = open(os.path.join(REPO, "Unity", "Build", "ArtFirst", "27R01", "water", "af27r01_right_slope.bin"), "rb").read()
    n, i0, i1 = np.frombuffer(raw, np.int32, 3, 4)
    V = np.frombuffer(raw, np.float32, n * 3, 16).reshape(-1, 3).astype(float)
    I0 = np.frombuffer(raw, np.int32, i0, 16 + n * 12).reshape(-1, 3)
    I1 = np.frombuffer(raw, np.int32, i1, 16 + n * 12 + i0 * 4).reshape(-1, 3)
    res["AF27R01_RightSlope"] = [V[I0], V[I1]]
    return res


CLS = dict(sky=0, hero_body=1, hero_margin=2, near_sea=3, near_white=4, far=5, flat=6, rs_white=7, rs_dark=8, fg_swell=9, fg_foam=10,
           ls_white=11, ls_dark=12, boat=13)
PAL = {0: (196, 232, 249), 1: (150, 90, 40), 2: (96, 63, 34), 3: (96, 63, 34), 4: (227, 246, 251), 5: (96, 63, 34), 6: (96, 63, 34),
       7: (227, 246, 251), 8: (96, 63, 34), 9: (227, 246, 251), 10: (227, 246, 251), 11: (227, 246, 251), 12: (96, 63, 34), 13: (158, 193, 229)}


def scene_tris(tau, hero, near, far, jb, je, mode, boats, ph, cls_near, cls_far, delta_boat=0.0):
    tl, il = [], []
    Xh = hero.world(tau)
    Th = grid_tris(hero.R, hero.C, jb, je)
    tl.append(Xh.reshape(-1, 3)[Th]); il.append(np.full(len(Th), CLS["hero_body"]))
    if mode == "before":
        for c0, c1 in ((0, jb), (je, hero.C - 1)):
            Tm = grid_tris(hero.R, hero.C, c0, c1)
            tl.append(Xh.reshape(-1, 3)[Tm]); il.append(np.full(len(Tm), CLS["hero_margin"]))
        # 平らな海（AF28_SeaFlat の上面 y −0.07、x ±500・z −400〜600）。カメラの後ろへ回る大きな三角形を落とさないよう 10 m の格子に割る
        xs = np.arange(-500, 501, 10.0); zs = np.arange(-400, 601, 10.0)
        X0, Z0 = np.meshgrid(xs[:-1], zs[:-1], indexing="ij")
        X0 = X0.ravel(); Z0 = Z0.ravel()
        q00 = np.stack([X0, np.full_like(X0, -0.07), Z0], 1); q10 = q00 + [10, 0, 0]; q01 = q00 + [0, 0, 10]; q11 = q00 + [10, 0, 10]
        flat = np.concatenate([np.stack([q00, q01, q11], 1), np.stack([q00, q11, q10], 1)])
        tl.append(flat); il.append(np.full(len(flat), CLS["flat"]))
        tl += [ph["AF27R01_RightSlope"][0], ph["AF27R01_RightSlope"][1], ph["M1_ForegroundSwell_Static"][0]]
        il += [np.full(len(ph["AF27R01_RightSlope"][0]), CLS["rs_white"]), np.full(len(ph["AF27R01_RightSlope"][1]), CLS["rs_dark"]),
               np.full(len(ph["M1_ForegroundSwell_Static"][0]), CLS["fg_swell"])]
    else:
        Xn = near.world(tau).reshape(-1, 3); Tn = grid_tris(near.R, near.C)
        cn = cls_near.reshape(-1)[Tn].max(1)
        tl.append(Xn[Tn]); il.append(np.where(cn > 0, CLS["near_white"], CLS["near_sea"]))
        Xf = far.world(tau).reshape(-1, 3); Tf = grid_tris(far.R, far.C)
        tl.append(Xf[Tf]); il.append(np.full(len(Tf), CLS["far"]))
    for nm, cl in (("M1_ForegroundFoam_Static", "fg_foam"),):
        for T in ph[nm]:
            tl.append(T); il.append(np.full(len(T), CLS[cl]))
    T0, T1 = ph["M1_Revision_LeftSupport"]
    tl += [T0, T1]; il += [np.full(len(T0), CLS["ls_white"]), np.full(len(T1), CLS["ls_dark"])]
    tl.append(boats + np.array([0, delta_boat, 0])); il.append(np.full(len(boats), CLS["boat"]))
    return np.concatenate(tl), np.concatenate(il)


def colorize(ids, zb=None):
    img = np.zeros(ids.shape + (3,), np.uint8)
    for k, c in PAL.items():
        img[ids == k] = c
    return img


def painting_regression(hero, near, far, idx, outdir, cls_near, cls_far, boats, ph):
    spec = S.load_json(os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json"))
    cam = C27.Cam(spec)
    jb, je = idx["body_cols"]
    res = {}
    imgs = {}
    for mode in ("before", "after"):
        tr, ii = scene_tris(0.0, hero, near, far, jb, je, mode, boats, ph, cls_near, cls_far)
        t0 = time.time()
        ids, zb = raster_ids(cam, tr, ii)
        imgs[mode] = ids
        res[mode + "_seconds"] = round(time.time() - t0, 1)
    b, a = imgs["before"], imgs["after"]
    hero_b, hero_a = b == 1, a == 1
    sky_b, sky_a = b == 0, a == 0
    white = lambda x: np.isin(x, [4, 7, 9, 10, 11])  # noqa: E731
    dark = lambda x: np.isin(x, [2, 3, 5, 6, 8, 12])  # noqa: E731
    reg = S.load_json(os.path.join(REPO, "Tools", "PaintingTruth", "targets", "regions.json"))
    zone = np.zeros((H, W), np.uint8)
    cv2.fillPoly(zone, [np.round(np.array(reg["polygons_display"]["main_wave_palette_zone"])).astype(np.int32)], 1)
    zone = zone.astype(bool)
    env = S.load_json(os.path.join(REPO, "Tools", "PaintingTruth", "targets", "main_wave_outline_envelope.json"))
    seg_masks = {}
    for sgm in env["segments"]:
        m = np.zeros((H, W), np.uint8)
        pts = np.round(np.array(sgm["points_display"])).astype(np.int32)
        cv2.polylines(m, [pts], False, 1, thickness=13)          # 線の両側 6 px
        seg_masks[sgm["id"]] = m.astype(bool)
    dh = hero_b ^ hero_a
    ds = sky_b ^ sky_a
    dw = (white(b) ^ white(a)) & ~hero_b & ~hero_a
    items = {}
    for sid, m in seg_masks.items():
        items[sid] = dict(hero_visible_changed_px=int((dh & m).sum()), sky_changed_px=int((ds & m).sum()))
    items["palette_zone"] = dict(hero_visible_changed_px=int((dh & zone).sum()), sky_changed_px=int((ds & zone).sum()),
                                 white_dark_changed_px_outside_hero=int((dw & zone).sum()))
    res.update(dict(hero_visible_px_before=int(hero_b.sum()), hero_visible_px_after=int(hero_a.sum()),
                    hero_visible_changed_px=int(dh.sum()), sky_changed_px=int(ds.sum()), white_dark_changed_px_outside_hero=int(dw.sum()),
                    items=items))
    # 図
    cb, ca = colorize(b), colorize(a)
    diff = np.full((H, W, 3), 255, np.uint8)
    diff[dh] = (0, 0, 255); diff[ds & ~dh] = (255, 0, 0); diff[dw & ~dh & ~ds] = (0, 170, 0)
    diff[~(dh | ds | dw)] = (cb[~(dh | ds | dw)] * 0.35 + 165).astype(np.uint8)
    cv2.imwrite(os.path.join(outdir, "ds30_painting_tstar_ids_before.png"), cb)
    cv2.imwrite(os.path.join(outdir, "ds30_painting_tstar_ids_after.png"), ca)
    cv2.imwrite(os.path.join(outdir, "ds30_painting_tstar_ids_diff.png"), diff)
    return res, imgs


def shade_render(cam, tr, ii, bg=(196, 232, 249)):
    ids, zb = raster_ids(cam, tr, ii)
    img = colorize(ids)
    # 奥行きの段差を線で見せる（段差・穴・二重面の確認用）
    z = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-9), 1e4)
    gx = np.abs(np.diff(np.log(z), axis=1, prepend=np.log(z[:, :1])))
    gy = np.abs(np.diff(np.log(z), axis=0, prepend=np.log(z[:1, :])))
    edge = (np.maximum(gx, gy) > 0.08) & (ids > 0)
    img[edge] = (40, 40, 40)
    return img, ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sea", default="Unity/Build/Design/30/sea")
    ap.add_argument("--out", default="Unity/Build/Design/30/checks")
    ap.add_argument("--skip", default="")
    args = ap.parse_args()
    skip = set(args.skip.split(",")) if args.skip else set()
    t0 = time.time()
    sd = os.path.join(REPO, args.sea)
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    P = S.load_json(S.PARAMS)
    hero_s = S.Hero()
    hero = Pkg(hero_s.dir)
    near = Pkg(os.path.join(sd, "near")); far = Pkg(os.path.join(sd, "far"))
    idx = S.load_json(os.path.join(sd, "near", "ds30_ring0_index.json"))
    assert np.array_equal(near.knots, hero.knots) and np.array_equal(far.knots, hero.knots)
    assert np.array_equal(near.ft, hero.ft) and np.array_equal(near.fo, hero.fo)
    fs = P["grid"]["far_subsample"]
    feat = S.Features(hero_s)
    feat.set_growth(S.load_json(os.path.join(sd, "ds30_generate_log.json"))["hero_hmax_knots"])
    M = dict(number="設計30", schema="GreatWave.DS30.checks/1", renderer_ja="numpy（Unity の描画ではない）", sea=args.sea,
             near_sha256=near.k["pos_sha256"], far_sha256=far.k["pos_sha256"], hero_sha256=hero.k["pos_sha256"],
             knots_same=True, frame_same=True)
    if "seam" not in skip:
        M["seam"] = seam_checks(hero, near, far, idx, fs)
        print("seam", json.dumps({k: v for k, v in M["seam"].items() if k not in ("flips",)}, ensure_ascii=False)[:1500])
        fl = np.array(M["seam"]["flips"])
        M["seam"]["flips_summary"] = dict(near_max=int(fl[:, 1].max()), near_at_tau=float(fl[np.argmax(fl[:, 1]), 0]), far_max=int(fl[:, 2].max()),
                                          near_tstar=int(fl[-1, 1]))
    kn = hero.knots
    if "rim" not in skip:
        M["rim"] = free_edges_check(hero, near, far, idx, [float(kn[0]), -6.0, -3.0, -1.0, 0.0])
    if "jump" not in skip:
        tw = S.load_json(os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "F_final", "timewarp_F_final.json"))
        t_all = np.array(tw["t"]); tau_all = np.array(tw["tau"])
        frames = np.arange(0, int(round(float(t_all[-1]) * 30)) + 1) / 30.0
        taus = np.interp(frames, t_all, tau_all)
        disp = []
        prev = None
        for tau in taus:
            cur = (near.world(float(tau)), far.world(float(tau)))
            if prev is not None:
                disp.append([float(np.abs(cur[0] - prev[0]).max()), float(np.abs(cur[1] - prev[1]).max())])
            prev = cur
        disp = np.array(disp)
        acc = np.abs(np.diff(disp, axis=0))
        M["playback"] = dict(frames=len(taus), tau_start=float(taus[0]), tau_end=float(taus[-1]), t_star_s=tw["t_star_s"],
                             max_step_near_m=float(disp[:, 0].max()), max_step_far_m=float(disp[:, 1].max()),
                             p99_step_near_m=float(np.percentile(disp[:, 0], 99)),
                             first_steps_near_m=[float(v) for v in disp[:3, 0]], last_moving_steps_near_m=[float(v) for v in disp[disp[:, 0] > 0][-3:, 0]],
                             hold_steps_near_m=[float(v) for v in disp[-3:, 0]], max_step_change_near_m=float(acc[:, 0].max()),
                             note_ja="コマ（30 Hz）の間の頂点の動きの最大（ワールド）。t = 0 のコマは τ の最初の値をそのまま出す（前のコマはない）。t* の後は保持で 0。")
        print("playback", M["playback"])
    if "boat" not in skip:
        rec = boat_support(hero, near, far, idx, feat, P)
        S.save_json(os.path.join(sd, "boat_support.json"), rec)
        M["boat"] = rec["summary"]
        print("boat", json.dumps(rec["summary"], ensure_ascii=False))
    if "raster" not in skip:
        cls_near = np.fromfile(os.path.join(sd, "near", "ds30_class_u8.bin"), np.uint8).reshape(near.R, near.C)
        cls_far = np.fromfile(os.path.join(sd, "far", "ds30_class_u8.bin"), np.uint8).reshape(far.R, far.C)
        boats = boats_tris()
        ph = placeholder_tris()
        res, imgs = painting_regression(hero, near, far, idx, out, cls_near, cls_far, boats, ph)
        M["painting_tstar"] = res
        print("painting", json.dumps({k: v for k, v in res.items() if k != "items"}, ensure_ascii=False), json.dumps(res["items"])[:1500])
        # 段階の τ の静止画（原画視点・座席から波の方向）
        spec = S.load_json(os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json"))
        cam_p = C27.Cam(spec)
        seat = S.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
        eye = np.array(seat["seat"]["eye_world"])
        bs = S.load_json(os.path.join(sd, "boat_support.json")) if os.path.exists(os.path.join(sd, "boat_support.json")) else None
        tdir = hero_s.t
        jb, je = idx["body_cols"]
        tiles = []
        for tau in (-7.5, -4.0, -2.5, -1.2, -0.5, 0.0):
            dlt = 0.0
            if bs:
                fr = min(bs["frames"], key=lambda f: abs(f["tau"] - tau))
                dlt = fr["delta_m"]
            tr, ii = scene_tris(tau, hero, near, far, jb, je, "after", boats, ph, cls_near, cls_far, delta_boat=dlt)
            ip, _ = shade_render(cam_p, tr, ii)
            e2 = eye + np.array([0, dlt, 0])
            cam_s = C27.Cam(spec, position=e2, target=e2 - np.array([tdir[0], 0, tdir[2]]) * 10.0, vfov=70.0)
            isv, _ = shade_render(cam_s, tr, ii)
            for nm, im in (("painting", ip), ("seat_toward_wave", isv)):
                cv2.putText(im, "numpy %s tau %.2f" % (nm, tau), (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
                cv2.imwrite(os.path.join(out, "ds30_%s_tau%+.2f.png" % (nm, tau)), im)
            tiles.append((cv2.resize(ip, (640, 360)), cv2.resize(isv, (640, 360))))
        sheet = np.concatenate([np.concatenate([t[0] for t in tiles[:3]], 1), np.concatenate([t[0] for t in tiles[3:]], 1),
                                np.concatenate([t[1] for t in tiles[:3]], 1), np.concatenate([t[1] for t in tiles[3:]], 1)], 0)
        cv2.imwrite(os.path.join(out, "ds30_stills_sheet.png"), sheet)
    M["seconds"] = round(time.time() - t0, 1)
    S.save_json(os.path.join(out, "ds30_checks.json"), M)
    print("done", M["seconds"])


if __name__ == "__main__":
    main()
