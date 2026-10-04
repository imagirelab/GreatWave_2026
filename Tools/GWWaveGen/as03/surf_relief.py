# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：t* の主役波 K*′ AS02C に、巻きに沿う太い稜（彫りの溝）を本当の凹凸として刻んだ静止のメッシュを作る。

- 主役波の格子（行 240 × 列 400）の行（頂に並ぶ向き c の断面）を、主役波の帯（c −22〜+18 m、0.2 m おき）だけ 4 倍に細かくする
  （行を丸ごと足すので T 字のつなぎ目はできない。位置は行の向きの Catmull–Rom、属性は直線で補う）。列（巻きの向き）はそのまま。
- 稜の線の座標 q = w／λ(y)：w は見本01・02 の面の座標（頂に並ぶ向き、等値線が巻きに沿う）、λ(y) は S1 の周期（冠の下 0.035 H・中ほど 0.045 H・
  下の面 0.056 H）。線は下へ扇に開く。間隔が λ の √2 倍を超えると、隣の溝から Y 字に子の溝が分かれる（本数の段 Lq、面の上で 2 m で平らにした）。
- 断面：広く丸い藍の稜（超楕円）と、細い溝（幅は周期の 0.244、S1）。溝の中に細い玉縁。山と谷の差は周期の 0.15（S1 の 0.05〜0.25 の中）。
- 白の区域（背と頂）には刻まない。白の境から 2.5 m で溝が現れきる（冠の下で溝が消える、S1）。背の藍にも刻まない（S1：背の下の藍に溝は見えない）。
- 出力（Git 対象外）：Build/Polish/sample03/surface/mesh/<名前>.bin・.json（AS03StaticMesh の書式、shared/README）と、測りの report。
  頂点の値：POSITION（刻んだ位置）、NORMAL（刻む前の滑らかな法線 n0。シェーダーが同じ式の稜の傾きを画素ごとに足す）、TANGENT（∇q の向き）、
  UV3 = (F, hrel, u, w)、UV4 = (gq = |∇q|, hrow, Lq, q)、UV5 = (ao, keyVis, whiteSD, fade)、UV6 = (行, 列, λ, 0)。
原画カメラの投影は使わない。参照モデルの OBJ・写真は読まない（数は S1 の JSON）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_relief.py [--name hero_relief_v1] [--white-mask <shared/white_mask_f32.bin>] [--bake <bake.npz>]
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402


def catmull_rows(P, r0, r1, k):
    """行 r0..r1（含む）の間に k−1 本ずつ行を足す（Catmull–Rom、端は端の行を写す）。P は 行 × 列 × D。新しい行の並びと、元の行の小数の番号を返す。"""
    R = P.shape[0]
    rows = []
    rid = []
    for r in range(R):
        rows.append(P[r]); rid.append(float(r))
        if r0 <= r < r1:
            pm = P[max(r - 1, 0)]; p0 = P[r]; p1 = P[r + 1]; p2 = P[min(r + 2, R - 1)]
            for i in range(1, k):
                t = i / k
                t2, t3 = t * t, t * t * t
                v = 0.5 * ((2 * p0) + (-pm + p1) * t + (2 * pm - 5 * p0 + 4 * p1 - p2) * t2 + (-pm + 3 * p0 - 3 * p1 + p2) * t3)
                rows.append(v); rid.append(r + t)
    return np.stack(rows, 0), np.array(rid)


def lerp_rows(A, rid):
    r0 = np.floor(rid).astype(int)
    r1 = np.minimum(r0 + 1, A.shape[0] - 1)
    t = (rid - r0)[:, None]
    if A.ndim == 3:
        t = t[..., None]
    return A[r0] * (1 - t) + A[r1] * t


def smooth_level(Pb, lv, R):
    """有限要素の (M + R² K) L = M lv で、本数の段を面の上で半径 R m に平らにする（s01a_attr.py の Ls と同じ作り）。"""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    from s01_param import grad_operator
    nr, nc = Pb.shape[:2]
    pos = Pb.reshape(-1, 3)
    tri = S.grid_tris(nr, nc)
    G, A, _nt = grad_operator(pos, tri)
    K = (G.T @ sp.diags(np.repeat(A, 3)) @ G).tocsc()
    mv = np.zeros(nr * nc); np.add.at(mv, tri.reshape(-1), np.repeat(A / 3.0, 3)); mv = np.maximum(mv, 1e-12)
    L = spla.splu((sp.diags(mv) + R * R * K).tocsc()).solve(mv * lv.reshape(-1))
    return L.reshape(nr, nc)


def write_static_mesh(path_stem, channels, tris):
    """AS03StaticMesh の書式（shared/README）：チャンネルごとの平面の float32、続いて uint32 の三角形。"""
    n = channels[0][1].shape[0]
    with open(path_stem + ".bin", "wb") as f:
        for name, arr in channels:
            a = np.ascontiguousarray(arr, np.float32)
            assert a.shape[0] == n, name
            f.write(a.tobytes())
        f.write(np.ascontiguousarray(tris, np.uint32).tobytes())
    meta = {"schema": "GreatWave.AS03.static_mesh/1", "vertices": int(n), "triangles": int(tris.shape[0]),
            "channels": [[name, int(arr.shape[1])] for name, arr in channels], "bin": os.path.basename(path_stem) + ".bin",
            "sha256": S.sha(path_stem + ".bin"), "bytes": os.path.getsize(path_stem + ".bin")}
    S.jdump(path_stem + ".json", meta)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="hero_relief_v1")
    ap.add_argument("--kr", type=int, default=4)
    ap.add_argument("--c-range", default="-22,18")
    ap.add_argument("--white-mask", default="", help="B1 の shared/white_mask_f32.bin（格子の頂点ごとの符号付きの距離 m、+ が白）")
    ap.add_argument("--white-band", default="", help="B1 の shared/white_mask_band_f32.bin（頂の帯を細かくした格子で式を直に計算した値。sd_m は負が白）")
    ap.add_argument("--bake", default="")
    ap.add_argument("--depth-over-period", type=float, default=None)
    ap.add_argument("--flat", action="store_true", help="凹凸を刻まない（比べ用。シェーダーの稜の傾きだけ）")
    ap.add_argument("--no-carve", dest="carve", action="store_false", help="稜を外へも盛る（既定は内へ彫る）")
    ap.add_argument("--lod-smooth-m", type=float, default=None, help="本数の段 Lq を平らにする半径 m（既定 2.0。小さいほど Y 字が多い）")
    a = ap.parse_args()
    t0 = time.time()
    meta = S.jload(S.META)
    H0 = float(meta["frame"]["H0_m"])
    spec = S.jload(S.SPEC)
    gp = S.GrooveParams(H0, spec)
    if a.depth_over_period is not None:
        gp.depth_over_period = a.depth_over_period
    if a.lod_smooth_m is not None:
        gp.lod_smooth_m = a.lod_smooth_m
    Pb = S.load_hero_world()
    nr, nc = Pb.shape[:2]
    # .gwb（K* のメッシュ）と包みの τ = 0 の位置の差（同じ形であることの確かめ）
    from s01_param import load_gwb
    _nu, _nv, _uv, _uv2, _tri, gpos = load_gwb(S.GWB)
    dg = np.linalg.norm(gpos.reshape(nr, nc, 3) - Pb, axis=-1)
    at = np.fromfile(S.ATTR, np.float32).reshape(nr, nc, 12).astype(np.float64)
    c_row = np.load(S.ROWS)["c"].astype(np.float64)
    # ---- 段 Lq（元の格子で求めて平らにする）
    lam_b = gp.lam(Pb[..., 1])
    q_b = at[..., 3] / lam_b
    gq_b = np.linalg.norm(S.surface_grad(Pb, q_b), axis=-1)
    lv = np.log2(1.0 / np.maximum(gq_b * lam_b, 1e-3))
    Lq_b = smooth_level(Pb, lv, gp.lod_smooth_m)
    # ---- 行を細かくする
    c0, c1 = [float(x) for x in a.c_range.split(",")]
    sel = np.nonzero((c_row >= c0) & (c_row <= c1))[0]
    r0, r1 = int(sel.min()), int(sel.max())
    P, rid = catmull_rows(Pb, r0, r1, a.kr)
    A = lerp_rows(at, rid)
    Lq = lerp_rows(Lq_b, rid)
    Nr = P.shape[0]
    F, hrel, u, w = A[..., 0], A[..., 1], A[..., 2], A[..., 3]
    hrow, xl = A[..., 5], A[..., 7]
    nattr = S.unit(A[..., 8:11])
    n0 = S.grid_normals(P)
    flip = (n0 * nattr).sum(-1) < 0
    n0[flip] *= -1.0
    lam = gp.lam(P[..., 1])
    q = w / lam
    gvec = S.surface_grad(P, q)
    gq = np.linalg.norm(gvec, axis=-1)
    Tq = S.unit(gvec)
    # ---- 白の境
    if a.white_mask:
        wm = np.fromfile(a.white_mask, np.float32).astype(np.float64).reshape(nr, nc)
        wsd = lerp_rows(wm, rid)
        white_src = "B1 " + a.white_mask + " sha256 " + S.sha(a.white_mask)
        if a.white_band:
            # 帯の格子（行 60〜239 を 4 倍、列 60〜270 を 2 倍、列が速い、頂点ごと float32 × 11：r, c, x, y, z, u, w, white, sd_m（負が白）, region, tongue_id。README の「× 12」は実際は 11）
            raw = np.fromfile(a.white_band, np.float32)
            nper = 11 if raw.size % 11 == 0 and raw.size // 11 == 717 * 421 else 12
            bd = raw.reshape(-1, nper)
            br = np.round((bd[:, 0] - 60.0) * 4.0).astype(int); bc = np.round((bd[:, 1] - 60.0) * 2.0).astype(int)
            nbr, nbc = br.max() + 1, bc.max() + 1
            band = np.full((nbr, nbc), np.nan); band[br, bc] = -bd[:, 8]
            kr_ = np.round((rid - 60.0) * 4.0)
            okr = (rid >= 60.0) & (rid <= 239.0) & (np.abs((rid - 60.0) * 4.0 - kr_) < 1e-6)
            cols = np.arange(nc)
            okc = (cols >= 60) & (cols <= 270)
            sub = band[np.clip(kr_[okr].astype(int), 0, nbr - 1)][:, (cols[okc] - 60) * 2]
            blk = wsd[okr][:, okc]
            good = np.isfinite(sub)
            blk[good] = sub[good]
            tmp = wsd[okr]; tmp[:, okc] = blk; wsd[okr] = tmp
            white_src += " ＋ 帯 " + a.white_band + " sha256 " + S.sha(a.white_band) + " (置き換えた頂点 %d)" % int(good.sum())
    else:
        wsd = S.white_sd_s02(F, hrel, u, w, hrow, H0)
        white_src = "sample02（背 hrel > 0.42＋うねり、頂の前 u < 1.6 m＋房）"
    fade = S.smooth(0.0, gp.fade_len, -wsd)
    fade *= (u >= 0.0)                       # 背（u < 0）の藍には刻まない
    fade *= S.smooth(0.06, 0.12, hrow)        # 低すぎる行
    fade *= S.smooth(4.12, 3.92, F)           # 前の面の下（F 4）より先の裾（手前の海の下へ入る所）には刻まない
    # ---- 稜の高さ（刻む）
    period = lam
    depth = gp.depth_over_period * period * fade
    gfr = gp.gfrac * (0.45 + 0.55 * np.sqrt(fade))   # 溝の端（冠の下）では線が細る
    h, d, gh, km, Ggap = S.groove_h(q, Lq, gq, lam, depth, gfr, gp.bead, gp.pexp, gp.lod)
    # 彫る（内へ削る）：稜の山を元の面に置き、溝を内へ削る（h − depth/2 ≤ 0）。外へ盛ると原画視点の輪郭が外へ出て、
    # 関門 72 σ12 p95 が 4.09／4.22 px（爪なし／あり）で 4 px を超えた（回 12。凹凸なしでは 3.80／3.62）。彫刻家が面に溝を彫るのと同じ向き
    disp = np.where(fade > 1e-3, (h - 0.5 * depth) if a.carve else h, 0.0)
    if a.flat:
        disp[:] = 0.0
    Pd = P + n0 * disp[..., None]
    # ---- 焼いた陰（AO・固定の光の見通し）。無ければ 1
    ao = np.ones((Nr, nc)); kv = np.ones((Nr, nc))
    bake_src = ""
    if a.bake:
        bk = np.load(a.bake)
        ao = lerp_rows(bk["ao"].reshape(nr, nc), rid); kv = lerp_rows(bk["kv"].reshape(nr, nc), rid)
        bake_src = a.bake
    rr = np.repeat(rid[:, None], nc, 1); cc = np.repeat(np.arange(nc, dtype=np.float64)[None, :], Nr, 0)
    # 白の時刻（包みの T_white）：t*（τ = 0）までに白が来た頂点だけ白にしてよい（見本02 の材質と同じ約束。1,200 頂点は「来ない」）
    tw = np.fromfile(S.HERO_PKG + "/ds27_twhite_r32f.bin", np.float32).astype(np.float64).reshape(nr, nc)
    wok = lerp_rows(((tw <= 0.0) & (tw < 1e8)).astype(np.float64), rid)
    N = Nr * nc
    ch = [
        ("position", Pd.reshape(N, 3)),
        ("normal", n0.reshape(N, 3)),
        ("tangent", np.concatenate([Tq.reshape(N, 3), np.ones((N, 1))], 1)),
        ("uv3", np.stack([F, hrel, u, w], -1).reshape(N, 4)),
        ("uv4", np.stack([gq, hrow, Lq, q], -1).reshape(N, 4)),
        ("uv5", np.stack([ao, kv, wsd, fade], -1).reshape(N, 4)),
        ("uv6", np.stack([rr, cc, lam, wok], -1).reshape(N, 4)),
    ]
    tris = S.grid_tris(Nr, nc)
    od = S.OUT + "/mesh"
    os.makedirs(od, exist_ok=True)
    m = write_static_mesh(od + "/" + a.name, ch, tris)
    # ---- 測り：主役波の前の面で、高さごとの溝の間隔（面の上の m）と Y 字の数
    meas = {}
    face = (F > 2.2) & (F < 3.95) & (fade > 0.5)
    # 前の面の高さの帯（±0.6 m）で、各頂点の「隣り合う 2 本の溝の中心の間の面の上の距離」（溝の式の G）の面積の重みなしの中央値と平均
    for lab, yy in (("0.75H", 0.75), ("0.50H", 0.50), ("0.35H", 0.35), ("0.25H", 0.25)):
        y0 = yy * H0
        ok = face & (np.abs(Pd[..., 1] - y0) < 0.6)
        g = Ggap[ok]
        meas[lab] = {"vertices": int(ok.sum()), "gap_p50_m": round(float(np.median(g)), 3) if ok.any() else None,
                     "gap_mean_m": round(float(g.mean()), 3) if ok.any() else None, "target_m": round(float(gp.lam(y0)), 3)}
    fz = (km > 0.05) & (km < 0.95) & face
    from scipy import ndimage
    lab_, nf = ndimage.label(fz)
    rep = {
        "schema": "GreatWave.AS03.surf_relief/1",
        "name": a.name, "seconds": round(time.time() - t0, 1),
        "inputs": {"hero_pkg": S.HERO_PKG, "gwb": S.GWB, "gwb_sha256": S.sha(S.GWB), "attr": S.ATTR, "attr_sha256": S.sha(S.ATTR),
                   "spec": S.SPEC, "spec_sha256": S.sha(S.SPEC), "white": white_src, "bake": bake_src},
        "gwb_vs_pkg_tau0_m": {"max": float(dg.max()), "p99": float(np.percentile(dg, 99))},
        "grid": {"rows_base": nr, "cols": nc, "rows_refined": Nr, "refined_rows_base_range": [r0, r1], "c_range_m": [float(c_row[r0]), float(c_row[r1])], "kr": a.kr,
                 "vertices": N, "triangles": int(tris.shape[0])},
        "groove_params": gp.as_dict(), "flat": a.flat, "carve_inward": a.carve,
        "displacement_m": {"min": float(disp.min()), "max": float(disp.max()), "faded_area_vertices": int((fade > 0.5).sum())},
        "normals_flipped_to_attr": int(flip.sum()),
        "spacing_front_face": meas,
        "fork_zones_front_face": int(nf),
        "Lq_range": [float(Lq.min()), float(Lq.max())],
        "mesh": m,
        "projection_used": False, "reference_obj_read": False, "photos_read": False,
    }
    S.jdump(od + "/" + a.name + "_report.json", rep)
    print(rep["grid"], rep["displacement_m"], rep["gwb_vs_pkg_tau0_m"], rep["spacing_front_face"], "forks", nf, "sec", rep["seconds"])


if __name__ == "__main__":
    main()
