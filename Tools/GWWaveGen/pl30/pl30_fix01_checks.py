# -*- coding: utf-8 -*-
"""仕上げ30 修正の回 1：自己評審が挙げた数の検査（numpy。Unity の描画ではない）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix01_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/fix01/checks_<名前> [--skip tilt,attr,boat,fg,rise]
測るもの：
  attr  面の座標の隣の頂点との跳び（列の隣・行の隣）。見える所（波に属する重み > 0.05 の頂点を含む組）と全部を分けて数える。
        仕上げ30 の作る部の版（12 個）と修正01 の版（20 個）の両方を読む。|Δu| > 100 m・|Δq| > 5 m・|Δh| > 3 m の組の数と最大。
  tilt  near の帯（継ぎ目から 12 m の内）の三角形の面の傾き（法線と +y の角）。5 節点おき＋t*。面積 0.01 m² 未満の三角形は除いた値も出す。
        地形の誘導（右の高い波・肩の稜・小波の t* の高さ > 0.3 m）と船の支えの当て布（重み > 0.01）の所を除いた「帯の式だけの所」の最大も出す。
  boat  座席の船の竜骨の 11 点を通る、竜骨に垂直な断面（±4 m、0.1 m おき）の t* の水面：竜骨の外（1.2〜4 m）の 1 m の中の最大の落差、
        竜骨の外の溝（両側より低い所）の深さ、継ぎ目の法線の内積の最小（全節点と t*。pl30_checks.seam と同じ読み）。
  fg    原画視点の手前の船（boat_fg、場面の書き出しの網）の船底の足跡の t* の水面の高さ（仕上げ29 の海は 0.0 m）。
  rise  右の高い波の頂（右の誘導の t* の高さ > 15 m の所）の今の高さの、30 Hz の時間の変化（平均と最大の上がる速さ m/s、t 9〜12 s）。
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl30_sea as S  # noqa: E402
from pl30_checks import Pkg, vnormals, timewarp, seam  # noqa: E402

REPO = S.REPO


def attr_jumps(sd, near, far):
    out = {}
    for nm, pk in (("near", near), ("far", far)):
        p = os.path.join(sd, nm, "pl30_sea_attr_f32.bin")
        n = os.path.getsize(p) // 4 // (pk.R * pk.C)
        A = np.fromfile(p, "<f4").reshape(pk.R, pk.C, n).astype(np.float64)
        if n == 12:
            names = dict(q=0, hcr=1, wf=2, u=5, hf=7)
            vis = A[..., 2]
            pairs = [("q", "u", "hcr", vis)]
            fields = {k: A[..., i] for k, i in names.items()}
            groups = [dict(q=fields["q"], u=fields["u"], h=fields["hcr"], w=vis, name="ridge_or_small")]
            sea_u = fields["u"]
        else:
            groups = [dict(q=A[..., 0], u=A[..., 1], h=A[..., 2], w=A[..., 3], name="ridge"),
                      dict(q=np.hypot(A[..., 4], A[..., 5]), u=np.arctan2(A[..., 5], A[..., 4]), h=A[..., 6], w=A[..., 7], name="small")]
            sea_u = A[..., 13]
        rec = {}
        for g in groups:
            for key, thr in (("q", 5.0), ("u", 100.0), ("h", 3.0)):
                for ax, axn in ((1, "col"), (0, "row")):
                    d = np.abs(np.diff(g[key], axis=ax))
                    if g["name"] == "small" and key == "u":
                        d = np.minimum(d, 2 * np.pi - d)       # 角度の周期
                    w = np.maximum(np.take(g["w"], range(0, g["w"].shape[ax] - 1), axis=ax), np.take(g["w"], range(1, g["w"].shape[ax]), axis=ax))
                    vis = w > 0.05
                    rec["%s_%s_%s" % (g["name"], key, axn)] = dict(max_all=float(d.max()), max_visible=float(d[vis].max()) if vis.any() else 0.0,
                                                                  n_over_all=int((d > thr).sum()), n_over_visible=int((d[vis] > thr).sum()), thr=thr)
        # 海の溝の沿う座標（作る部は u を使っていた）
        dc = np.abs(np.diff(sea_u, axis=1)); dr = np.abs(np.diff(sea_u, axis=0))
        rec["sea_along"] = dict(col_max=float(dc.max()), row_max=float(dr.max()), col_p999=float(np.percentile(dc, 99.9)),
                                n_col_over_20=int((dc > 20).sum()), n_row_over_20=int((dr > 20).sum()))
        out[nm] = rec
    return out


def tri_tilt(X, s, smax=12.0, feat_mask=None):
    """X (R, C, 3)、s (R, C)。三角形の傾き（度）と面積。"""
    R, C, _ = X.shape
    P00, P10, P01, P11 = X[:-1, :-1], X[1:, :-1], X[:-1, 1:], X[1:, 1:]
    n1 = np.cross(P10 - P00, P01 - P00)
    n2 = np.cross(P10 - P01, P11 - P01)
    out = []
    sm = 0.25 * (s[:-1, :-1] + s[1:, :-1] + s[:-1, 1:] + s[1:, 1:])
    for n in (n1, n2):
        area = 0.5 * np.linalg.norm(n, axis=-1)
        ang = np.degrees(np.arccos(np.clip(np.abs(n[..., 1]) / np.maximum(2 * area, 1e-12), 0, 1)))
        out.append((ang, area))
    ang = np.maximum(out[0][0], out[1][0])
    area = np.minimum(out[0][1], out[1][1])
    band = sm < smax
    return ang, area, band


def tilt(near, sd, feat, P):
    X0 = near.layer(near.L - 1)
    s0 = np.concatenate([np.zeros((1, X0.shape[1])), np.cumsum(np.linalg.norm(np.diff(X0[..., [0, 2]], axis=0), axis=-1), axis=0)], 0)
    t_ax, e_ax = feat.h.t, feat.h.e
    a = X0[..., 0] * t_ax[0] + X0[..., 2] * t_ax[2]
    c = X0[..., 0] * e_ax[0] + X0[..., 2] * e_ax[2]
    fH = feat.sample(a, c, "right") + feat.sample(a, c, "small")
    bw = feat.sample(a, c, "boat_w")
    fq = 0.25 * (fH[:-1, :-1] + fH[1:, :-1] + fH[:-1, 1:] + fH[1:, 1:])
    bq = 0.25 * (bw[:-1, :-1] + bw[1:, :-1] + bw[:-1, 1:] + bw[1:, 1:])
    idx = S.load_json(os.path.join(sd, "near", "ds30_ring0_index.json"))
    kinds = np.array([d["ray"] for d in idx["loop"]] + [idx["loop"][0]["ray"]])
    ks = sorted(set(list(range(0, near.L, 5)) + [near.L - 1]))
    rec = dict(all=dict(max=0.0), nondegen=dict(max=0.0), band_only=dict(max=0.0), tstar={}, quad=dict(max=0.0, band_only_max=0.0, per_knot_max=[]))
    for i in ks:
        X = near.layer(i)
        # 四角の傾き（対角線の外積の法線。自己評審の「quad-tilt」の読みに近い。対角線が 0.1 m より短い四角は除く）
        d1 = X[1:, 1:] - X[:-1, :-1]; d2 = X[:-1, 1:] - X[1:, :-1]
        nq = np.cross(d1, d2)
        qt = np.degrees(np.arccos(np.clip(np.abs(nq[..., 1]) / np.maximum(np.linalg.norm(nq, axis=-1), 1e-12), 0, 1)))
        sq = 0.25 * (s0[:-1, :-1] + s0[1:, :-1] + s0[:-1, 1:] + s0[1:, 1:])
        okq = (sq < 12.0) & (np.linalg.norm(d1, axis=-1) > 0.1) & (np.linalg.norm(d2, axis=-1) > 0.1)
        vq = np.where(okq, qt, -1.0); vqb = np.where(okq & (fq < 0.3) & (bq < 0.01), qt, -1.0)
        rec["quad"]["per_knot_max"].append([float(near.knots[i]), round(float(vq.max()), 2), round(float(vqb.max()), 2)])
        if vq.max() > rec["quad"]["max"]:
            r_, c_ = np.unravel_index(np.argmax(vq), vq.shape)
            rec["quad"].update(max=float(vq.max()), at=dict(knot=int(i), tau=float(near.knots[i]), row=int(r_), col=int(c_), kind=str(kinds[c_]), feature_h_tstar=float(fq[r_, c_]), boat_w=float(bq[r_, c_])))
        if vqb.max() > rec["quad"]["band_only_max"]:
            r_, c_ = np.unravel_index(np.argmax(vqb), vqb.shape)
            rec["quad"].update(band_only_max=float(vqb.max()), band_only_at=dict(knot=int(i), tau=float(near.knots[i]), row=int(r_), col=int(c_), kind=str(kinds[c_])))
        if i == near.L - 1:
            rec["quad"]["tstar_max"] = float(vq.max()); rec["quad"]["tstar_band_only_max"] = float(vqb.max())
            rec["quad"]["tstar_band_only_n_over45"] = int((vqb > 45).sum())
            rec["quad"]["frames_band_only_over45"] = None
        ang, area, band = tri_tilt(X, s0)
        for key, m in (("all", band), ("nondegen", band & (area > 0.01)), ("band_only", band & (area > 0.01) & (fq < 0.3) & (bq < 0.01))):
            if not m.any():
                continue
            v = np.where(m, ang, -1)
            r, cc = np.unravel_index(np.argmax(v), v.shape)
            if v[r, cc] > rec[key]["max"]:
                rec[key] = dict(max=float(v[r, cc]), knot=int(i), tau=float(near.knots[i]), row=int(r), col=int(cc), kind=str(kinds[cc]), s=float(s0[r, cc]),
                                feature_h_tstar=float(fq[r, cc]), boat_w=float(bq[r, cc]), area_m2=float(area[r, cc]))
            if i == near.L - 1:
                rec["tstar"][key] = float(v.max())
                rec["tstar"][key + "_p99"] = float(np.percentile(ang[m], 99))
        # 帯の式だけの所の 45° を超える三角形の数（t*）
        if i == near.L - 1:
            m = band & (area > 0.01) & (fq < 0.3) & (bq < 0.01)
            rec["tstar"]["band_only_n_over45"] = int((ang[m] > 45).sum())
            rec["tstar"]["nondegen_n_over45"] = int((ang[band & (area > 0.01)] > 45).sum())
            kk = {}
            for kd in np.unique(kinds):
                mm = band & (area > 0.01) & (kinds[None, :-1] == kd)
                kk[str(kd)] = float(ang[mm].max()) if mm.any() else 0.0
            rec["tstar"]["by_kind_nondegen"] = kk
    pk = np.array([x[2] for x in rec["quad"]["per_knot_max"]])
    rec["quad"]["knots_band_only_over45"] = int((pk > 45).sum()); rec["quad"]["knots_checked"] = int(len(pk))
    return rec


def boat(near, sd, feat, P, hero):
    from scipy.interpolate import griddata
    k = feat.keel
    ax = np.array([k["axis"][0], k["axis"][2]]); ax /= np.linalg.norm(ax)
    perp = np.array([-ax[1], ax[0]])
    out = dict(profiles=[])
    X = near.layer(near.L - 1) + near.origin(0.0)[None, None, :]
    xz = X[..., [0, 2]].reshape(-1, 2); yy = X[..., 1].reshape(-1)
    pr = np.array(k["p_ref"])
    m = (np.abs(xz[:, 0] - pr[0]) < 25) & (np.abs(xz[:, 1] - pr[2]) < 25)
    d = np.linspace(-4, 4, 81)
    worst_drop, worst_groove, worst_ridge = 0.0, 0.0, 0.0
    for si, (s_, ky) in enumerate(zip(k["s"], k["y"])):
        p = pr[[0, 2]] + s_ * ax
        q = p[None, :] + d[:, None] * perp[None, :]
        y = griddata(xz[m], yy[m], q, method="linear")
        prof = dict(s=float(s_), keel_y=float(ky), target=float(ky + k["draft"]), y=[None if not np.isfinite(v) else round(float(v), 3) for v in y])
        outside = np.abs(d) >= 1.2
        drop = 0.0
        for j in range(len(d) - 10):
            if not (outside[j] and outside[j + 10]) or np.sign(d[j]) != np.sign(d[j + 10]):
                continue
            if np.isfinite(y[j]) and np.isfinite(y[j + 10]):
                drop = max(drop, abs(y[j + 10] - y[j]))
        prof["max_drop_1m_outside"] = drop
        # 溝・稜：竜骨の外で、±1 m の両側より低い（高い）所
        g, r_ = 0.0, 0.0
        for j in range(10, len(d) - 10):
            if not outside[j] or not np.isfinite(y[j - 10:j + 11]).all():
                continue
            lo, hi = y[j - 10:j + 1], y[j:j + 11]
            if y[j] <= lo.min() and y[j] <= hi.min():
                g = min(g, y[j] - min(lo.max(), hi.max()))
            if y[j] >= lo.max() and y[j] >= hi.max():
                r_ = max(r_, y[j] - max(lo.min(), hi.min()))
        prof["groove"] = g; prof["ridge"] = r_
        worst_drop = max(worst_drop, drop); worst_groove = min(worst_groove, g); worst_ridge = max(worst_ridge, r_)
        out["profiles"].append(prof)
    out.update(max_drop_1m_outside_m=worst_drop, max_groove_m=worst_groove, max_ridge_m=worst_ridge)
    return out


def fg_height(near, far, P):
    from scipy.interpolate import griddata
    d = S.load_json(os.path.join(REPO, "Unity", "Build", "Polish", "30", "dump", "pl30_scene_dump.json"))
    bf = [o for o in d["objects"] if o["name"].endswith("boat_fg")][0]
    V = np.array(bf["worldVertices"], np.float64).reshape(-1, 3)
    out = {}
    for nm, pk in (("near", near), ("far", far)):
        X = pk.layer(pk.L - 1) + pk.origin(0.0)[None, None, :]
        P_ = X.reshape(-1, 3)
        m = (np.abs(P_[:, 0] - 1.3) < 12) & (np.abs(P_[:, 2] + 32.2) < 8)
        if m.sum() < 4:
            continue
        q = np.array([[x, z] for x in np.linspace(V[:, 0].min(), V[:, 0].max(), 7) for z in np.linspace(V[:, 2].min(), V[:, 2].max(), 3)])
        y = griddata(P_[m][:, [0, 2]], P_[m][:, 1], q, method="linear")
        out[nm] = dict(min=float(np.nanmin(y)), max=float(np.nanmax(y)), mean=float(np.nanmean(y)))
    out["boat_fg_bottom_y"] = float(V[:, 1].min())
    return out


def rise(near, feat, P):
    t_all, tau_all, _ = timewarp(P)
    X0 = near.layer(near.L - 1)
    t_ax, e_ax = feat.h.t, feat.h.e
    a = X0[..., 0] * t_ax[0] + X0[..., 2] * t_ax[2]
    c = X0[..., 0] * e_ax[0] + X0[..., 2] * e_ax[2]
    fr = feat.sample(a, c, "right")
    m = fr > 15.0
    frames = np.arange(int(9 * 30), int(12 * 30) + 1) / 30.0
    taus = np.interp(frames, t_all, tau_all)
    hmax = []
    for tau in taus:
        Y = near.at(float(tau))[..., 1]
        hmax.append(float(Y[m].max()))
    hmax = np.array(hmax)
    v = np.diff(hmax) * 30.0
    # 10〜11.5 s の平均（作る部の記録の「t 10〜11.5 s に約 5 m/s」と同じ窓）と、全体の最大
    w = (frames[1:] > 10.0) & (frames[1:] <= 11.5)
    h0 = float(np.interp(10.0, frames, hmax)); h1 = float(np.interp(11.5, frames, hmax))
    k10 = int(np.argmax(v))
    return dict(crest_vertices=int(m.sum()), h_t9=float(hmax[0]), h_t10=h0, h_t11_5=h1, h_t12=float(hmax[-1]),
                mean_rise_m_s_t10_11_5=(h1 - h0) / 1.5, max_rise_m_s=float(v.max()), max_rise_at_t=float(frames[1:][k10]),
                mean_rise_m_s_over_window_frames=float(v[w].mean()),
                note_ja="右の高い波の頂（t* の右の誘導 > 15 m の near の頂点）の今の高さの最大を 30 Hz で読み、隣のコマの差 × 30 を上がる速さとした。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sea", default="Unity/Build/Polish/30/sea")
    ap.add_argument("--out", default="Unity/Build/Polish/30/fix01/checks")
    ap.add_argument("--params", default=S.PARAMS)
    ap.add_argument("--skip", default="")
    args = ap.parse_args()
    skip = set(args.skip.split(",")) if args.skip else set()
    t0 = time.time()
    P = S.load_json(args.params)
    sd = os.path.join(REPO, args.sea)
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    hero_s = S.Hero(P)
    near = Pkg(os.path.join(sd, "near")); far = Pkg(os.path.join(sd, "far"))
    feat = S.Features(hero_s, P)
    M = dict(number="仕上げ30 修正の回 1", sea=args.sea, params_sha256=S.sha256_file(args.params), renderer_ja="numpy（Unity の描画ではない）")
    if "attr" not in skip:
        M["attr"] = attr_jumps(sd, near, far)
        print("attr", json.dumps({k: {kk: (vv if not isinstance(vv, dict) else {x: y for x, y in vv.items() if x in ("max_visible", "n_over_visible", "n_over_all", "col_max", "row_max")}) for kk, vv in v.items()} for k, v in M["attr"].items()}, ensure_ascii=False)[:3000])
    if "tilt" not in skip:
        M["tilt"] = tilt(near, sd, feat, P)
        print("tilt", json.dumps(M["tilt"], ensure_ascii=False)[:1500])
    if "boat" not in skip:
        hero = Pkg(hero_s.dir)
        idx = S.load_json(os.path.join(sd, "near", "ds30_ring0_index.json"))
        M["boat"] = boat(near, sd, feat, P, hero_s)
        M["seam"] = seam(hero, near, far, idx, P)
        print("boat", json.dumps({k: v for k, v in M["boat"].items() if k != "profiles"}, ensure_ascii=False))
        for p in M["boat"]["profiles"]:
            print("  s %.2f target %.2f drop %.2f groove %.2f ridge %.2f" % (p["s"], p["target"], p["max_drop_1m_outside"], p["groove"], p["ridge"]))
        print("seam", json.dumps({k: v for k, v in M["seam"].items() if k != "note_ja"}, ensure_ascii=False))
    if "fg" not in skip:
        M["fg"] = fg_height(near, far, P)
        print("fg", M["fg"])
    if "rise" not in skip:
        M["rise"] = rise(near, feat, P)
        print("rise", json.dumps({k: v for k, v in M["rise"].items() if k != "note_ja"}, ensure_ascii=False))
    M["seconds"] = round(time.time() - t0, 1)
    S.save_json(os.path.join(out, "pl30_fix01_checks.json"), M)
    print("done", M["seconds"], "s")


if __name__ == "__main__":
    main()
