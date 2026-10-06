# -*- coding: utf-8 -*-
"""組み込みの準備：流体の水面（コマごとの網目）→ Unity が再生する形。二つの方法を同じデータで作り、測って比べる。

方法 A（行ごとに切って 240 × 400 の固定の網目へ並べ直す。提案 §3.6 の二つ目）：
  行の平面 z = 一定 で切り、主な水面の線（箱の後ろの端から前の端まで続く線）を目印で 400 列へ並べる。
  頂点の番号（行・列）はコマが変わっても同じ意味なので、コマの間を補間できる（作品の keypose と同じ前提）。
方法 B（コマごとの網目。提案 §3.6 の確認用の動画の方法、群17・18 の可変の網目）：
  流体の網目をそのまま使う。属性は同じコマの方法 A の網目の一番近い点から写す（主役波の範囲の外は周りの海の色）。
  頂点の番号はコマごとに別なので、コマの間は補間できない（段々に切り替わる）。

測るもの（metrics.json）：
  当てはまり：流体の水面の点（主役波の範囲の中）から方法 A の面までの距離（落とした水しぶき・閉じた空洞が大きな値になる）、
    方法 A の三角形の中点から流体の面までの距離（行の間の補間の誤差）。
  安定（飛び）：方法 A の頂点の 1 コマの動きと 2 階の差（|P(k+1) − 2P(k) + P(k−1)|、重力の何倍かでも）、
    方法 B のコマの間の面の跳び（次のコマの点から前のコマの面までの距離）と、ばらばらの小片の数の出入り。
  大きさ：頂点・三角形の数、試験の書き出し（float32）の大きさ、作品の形式での見込み。
出力：Unity/Build/FLIP37/integration_prep/<seq>/ の metrics.json・frames.json と、Unity が読む pkg/<seq>/{sheet,frames}/。
使い方：py -3.10 integ_convert.py <seq>（seq は SEQS の名前）[--no-unity] [--every N]
"""
import os, sys, glob, json, time, math
import numpy as np
from scipy.spatial import cKDTree
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integ_common as C
import p2_common as P2C

FLIP = C.REPO + "/Unity/Build/FLIP37"
SEQS = {
    # P2 の粗い 3D の計算（まっすぐの岩棚＋強いレンズ、入力 29 m、誘導なし）。巻く手前まで（前の面 −82°）。置き方は P2 の解析の一番似た組（ψ 30°、倍率 1.1）
    "R05": {"mesh_dir": FLIP + "/P2/R05_L120_H29/mesh", "t0": 8.0, "t1": 14.0, "zc": -2.0, "c": [-90.0, 45.0],
            "anchor": [602.0, 21.109375, -2.0], "psi": 30.0, "s": 1.1,
            "label_ja": "P2 R05（3D の流体の計算、粒子 1 m、誘導なし）", "fluid3d": True},
    # P2 のいちばん良い計算 R18（±30° の交わる二つの列＋レンズ＋手前・左の低い棚 2 つ、入力 39 m、誘導なし）。本物の 3D の巻き波
    # （z=0 で前の面が垂直を過ぎた 9.25 s、空洞が閉じた 10.67 s）。置き方は P2 の解析の best（t* 10.375 s、ψ 30°、倍率 1.1）。2026-10-06 23:40 追加
    "R18": {"mesh_dir": FLIP + "/P2/R18_X30L120LG_H39/mesh", "t0": 8.0, "t1": 11.75, "zc": 0.0, "c": [-90.0, 45.0],
            "anchor": [566.0, 18.125, 0.0], "psi": 30.0, "s": 1.1,
            "label_ja": "P2 R18（3D の流体の計算、粒子 1 m、交わる二つの列＋レンズ＋低い棚、入力 39 m、誘導なし。巻き波）", "fluid3d": True},
    # P1 の断面の計算を峰に沿って時刻をずらして並べた試験用の面（巻き込みあり。3D の計算ではない）
    "P1sweep": {"mesh_dir": C.OUT + "/testdata/P1sweep", "t0": 8.25, "t1": 12.5, "zc": 0.0, "c": [-42.0, 42.0],
                "anchor": [563.1, 19.9, 0.0], "psi": 30.0, "s": 1.0,
                "label_ja": "P1 の断面（粒子 0.25 m、誘導なし）を峰に沿って時刻をずらして並べた試験用の面（3D の計算ではない）", "fluid3d": False},
}


def place_fn(cfg):
    T, E = P2C.TE(cfg["psi"])
    _, O = P2C.place(np.zeros((1, 3)), cfg["anchor"], cfg["psi"], cfg["s"])
    a = np.array(cfg["anchor"], float)
    s = float(cfg["s"])
    Y = np.array([0.0, 1.0, 0.0])

    def f(Psim):
        Q = np.asarray(Psim, float) - np.array([a[0], 0.0, a[2]])
        return O + s * (Q[..., 0:1] * T + Q[..., 1:2] * Y + Q[..., 2:3] * E)

    M = np.stack([T, Y, E], 1) * s           # 向きの変換（法線は回転だけ）
    return f, M, O, T, E


def components(tri, nverts):
    """三角形のつながりの塊（頂点を共有する三角形）。戻り：塊ごとの三角形の数。"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    m = len(tri)
    r = np.repeat(np.arange(m), 3); c = tri.ravel()
    A = coo_matrix((np.ones(len(r)), (r, c + m)), shape=(m + nverts, m + nverts))
    n, lab = connected_components(A, directed=False)
    lt = lab[:m]
    _, cnt = np.unique(lt, return_counts=True)
    return np.sort(cnt)[::-1]


def stats(a):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return None
    return {"mean": float(a.mean()), "p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95)),
            "p99": float(np.percentile(a, 99)), "max": float(a.max()), "n": int(len(a))}


def main():
    seq = sys.argv[1]
    no_unity = "--no-unity" in sys.argv
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 1
    cfg = SEQS[seq]
    od = C.OUT + "/" + seq
    os.makedirs(od, exist_ok=True)
    pk = C.OUT + "/pkg/" + seq
    for m in ("sheet", "frames"):
        os.makedirs(pk + "/" + m, exist_ok=True)
    files = sorted(glob.glob(cfg["mesh_dir"] + "/mesh_*.npz"))
    frames = []
    for f in files:
        d = np.load(f)
        t = float(d["t"])
        if cfg["t0"] - 1e-6 <= t <= cfg["t1"] + 1e-6:
            frames.append((t, f))
    frames = frames[::every]
    sigma_t = float(sys.argv[sys.argv.index("--sigma-t") + 1]) if "--sigma-t" in sys.argv else 1.0
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
    if tag:
        od = od + "_" + tag
        os.makedirs(od, exist_ok=True)
    zrows = cfg["zc"] + np.linspace(cfg["c"][0], cfg["c"][1], C.NV)
    tri_sheet = C.grid_triangles()
    place, M, O, T, E = place_fn(cfg)
    ez = E                                      # 峰に沿う向き（Unity）
    rowg, colg = np.meshgrid(np.arange(C.NV), np.arange(C.NU), indexing="ij")
    t_start = time.time()
    # 1 回目：コマごとに行の目印を出す（頂からの弧長）。2 回目の前に時間の向きにならす（sigma_t コマ。0 ならならさない）
    rows_all, K_all = [], []
    for k, (t, f) in enumerate(frames):
        d = np.load(f)
        rows, K = C.frame_rows(d["P"].astype(np.float64), d["tri"].astype(np.int64), zrows)
        rows_all.append(rows); K_all.append(K)
    K_all = np.array(K_all)
    K_sm = ndi.gaussian_filter1d(K_all, sigma_t, axis=0, mode="nearest") if sigma_t > 0 else K_all
    print("pass1 %.0fs" % (time.time() - t_start), flush=True)
    rec = []
    prevG = []                                  # 方法 A の位置（計算の座標）の並び（2 階の差のため）
    prevB = None
    idx_sheet, idx_frames = [], []
    met = {"fit_fluid_to_sheet": [], "fit_sheet_mid_to_fluid": [], "A_step": [], "A_d2": [], "B_jump": [],
           "B_components": [], "B_small_components": []}
    sizes = {"sheet_bytes": [], "frames_bytes": [], "frames_verts": [], "frames_tris": []}
    for k, (t, f) in enumerate(frames):
        d = np.load(f)
        P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
        t1 = time.time()
        G, info = C.build_sheet(rows_all[k], K_sm[k], zrows)
        rows_all[k] = None
        t_conv = time.time() - t1
        # ---- 当てはまり
        zlo, zhi = zrows[0], zrows[-1]
        xr_lo = G[:, :, 0].min(1); xr_hi = G[:, :, 0].max(1)
        ri = np.clip(np.round((P[:, 2] - zlo) / (zhi - zlo) * (C.NV - 1)).astype(int), 0, C.NV - 1)
        inwin = (P[:, 2] >= zlo) & (P[:, 2] <= zhi) & (P[:, 0] >= xr_lo[ri]) & (P[:, 0] <= xr_hi[ri])
        Q = P[inwin]
        if len(Q) > 60000:
            Q = Q[np.random.default_rng(k).choice(len(Q), 60000, replace=False)]
        Gs = G.reshape(-1, 3)
        trS = cKDTree(Gs)
        dF2S = C.surf_distance(Q, Gs, tri_sheet, k=6, tree=trS)
        cen = Gs[tri_sheet].mean(1)
        cen = cen[np.random.default_rng(k + 7).choice(len(cen), min(60000, len(cen)), replace=False)]
        dS2F = C.surf_distance(cen, P, tri, k=6)
        # ---- 安定（方法 A）
        if prevG:
            dP = G - prevG[-1]
            step = np.linalg.norm(dP, axis=-1)
            nG = C.grid_normals(G)
            dn = np.abs((dP * nG).sum(-1))
            tang = np.sqrt(np.maximum(step ** 2 - dn ** 2, 0))
            met["A_step"].append({"t": t, **stats(step), "normal_p99": float(np.percentile(dn, 99)), "tangent_p99": float(np.percentile(tang, 99)),
                                  "tangent_max": float(tang.max())})
            if len(prevG) >= 2 and prevB is not None:
                # 1 コマ飛ばして補間した網目（前の前と今の中点）が、飛ばしたコマの流体の面からどれだけ離れるか（キャッシュを半分にしたときの補間の誤差）
                mid = (0.5 * (prevG[-2] + G)).reshape(-1, 3)
                mid = mid[np.random.default_rng(k + 11).choice(len(mid), 40000, replace=False)]
                Pp, tp = prevB
                di = C.surf_distance(mid, Pp, tp, k=6)
                met.setdefault("A_interp_skip1", []).append({"t": float(frames[k - 1][0]), **stats(di), "frac_gt_0p25m": float((di > 0.25).mean())})
            if len(prevG) >= 2:
                d2 = np.linalg.norm(G - 2 * prevG[-1] + prevG[-2], axis=-1)
                dt = t - frames[k - 1][0]
                met["A_d2"].append({"t": t, **stats(d2), "p99_g": float(np.percentile(d2, 99) / dt ** 2 / 9.81),
                                    "max_g": float(d2.max() / dt ** 2 / 9.81),
                                    "n_over_0p5m": int((d2 > 0.5).sum()), "n_over_2m": int((d2 > 2.0).sum())})
        prevG = (prevG + [G])[-2:]
        # ---- 方法 B のコマの間の跳び・小片
        comp = components(tri, len(P))
        met["B_components"].append({"t": t, "n": int(len(comp)), "small_lt50": int((comp < 50).sum()),
                                    "tris_in_small": int(comp[comp < 50].sum())})
        if prevB is not None:
            Pp, tp = prevB
            sub = P[inwin]
            if len(sub) > 40000:
                sub = sub[np.random.default_rng(k + 3).choice(len(sub), 40000, replace=False)]
            dj = C.surf_distance(sub, Pp, tp, k=6)
            met["B_jump"].append({"t": t, **stats(dj)})
        prevB = (P, tri)
        met["fit_fluid_to_sheet"].append({"t": t, **stats(dF2S), "frac_gt_0p25m": float((dF2S > 0.25).mean()),
                                          "frac_gt_1m": float((dF2S > 1.0).mean())})
        met["fit_sheet_mid_to_fluid"].append({"t": t, **stats(dS2F)})
        # ---- Unity の座標と属性（方法 A）
        Gu = place(G)
        Nu = C.grid_normals(Gu)
        u, F, w = C.sheet_attributes(info, zrows, cfg["zc"])
        hrow = np.broadcast_to(np.clip(cfg["s"] * info["y_top"] / C.H0, 0, 2)[:, None], u.shape)
        wsd, won = C.white_rule(u, F, info, w)
        wsd = C.smooth_grid(wsd, 2.0, 0.0)
        # 面の上の長さ（u・w・whiteSD）は Unity の m にする（置き方の一様の倍率 s を掛ける。約束：|∇u|・|∇w| ≈ 1）
        sc = float(cfg["s"])
        u, w, wsd = u * sc, w * sc, wsd * sc
        chA = C.as05_channels(Gu, Nu, u, F, w, ez, hrow, wsd, won, rowg, colg)
        chA["uv4"][:, 2] = C.smooth_grid(chA["uv4"][:, 2].reshape(C.NV, C.NU), 3.0, 3.0).ravel()   # Lq を面の上でならす（約 2 m）
        fi = int(round(t * 24)) + 1
        if not no_unity:
            nbA = C.write_static_mesh(pk + "/sheet/f_%04d.json" % fi, chA, tri_sheet,
                                      {"t": t, "seq": seq, "method": "sheet"})
        else:
            nbA = (len(chA["position"]) * 22 * 4 + len(tri_sheet) * 12)
        idx_sheet.append({"t": t, "json": "f_%04d.json" % fi, "bin": "f_%04d.bin" % fi, "vertices": C.NV * C.NU, "triangles": int(len(tri_sheet))})
        # ---- 方法 B：流体の網目そのもの＋近い所の属性
        Pu = place(P)
        Nb = C.vertex_normals(Pu, tri)
        dd, nn = trS.query(P, k=1)
        near = (dd < 1.5) & inwin
        ub = u.reshape(-1)[nn]; Fb = F.reshape(-1)[nn]; wb = w.reshape(-1)[nn]
        hb = hrow.reshape(-1)[nn]; sdb = wsd.reshape(-1)[nn]; onb = won.reshape(-1)[nn]
        Fb = np.where(near, Fb, -1.0); hb = np.where(near, hb, 0.0); sdb = np.where(near, sdb, -5.0)
        chB = C.as05_channels(Pu, Nb, ub, Fb, wb, ez, hb, sdb, onb)
        if not no_unity:
            nbB = C.write_static_mesh(pk + "/frames/f_%04d.json" % fi, chB, tri, {"t": t, "seq": seq, "method": "frames"})
        else:
            nbB = len(P) * 22 * 4 + len(tri) * 12
        idx_frames.append({"t": t, "json": "f_%04d.json" % fi, "bin": "f_%04d.bin" % fi, "vertices": int(len(P)), "triangles": int(len(tri))})
        sizes["sheet_bytes"].append(nbA); sizes["frames_bytes"].append(nbB)
        sizes["frames_verts"].append(int(len(P))); sizes["frames_tris"].append(int(len(tri)))
        # 方法 B の「主役波の範囲の中」の頂点の数（作品で主役波だけを流体の網目にする場合の見込み）
        mrow = int(np.argmin(np.abs(zrows - cfg["zc"])))
        rec.append({"t": t, "frame": fi, "convert_s": round(t_conv, 3), "rows_ok": int(info["ok"].sum()),
                    "rows_overhang": int(info["overhang"].sum()), "rows_dropped_pieces": int((info["ndrop"] > 0).sum()),
                    "dropped_len_m_sum": float(info["Ldrop"].sum()),
                    "fluid_verts": int(len(P)), "fluid_verts_in_hero": int(inwin.sum()),
                    "main_row": {"z": float(zrows[mrow]), "knots_rel_m": [float(x) for x in info["K"][mrow]],
                                 "y_top": float(info["y_top"][mrow]), "x_top": float(info["x_top"][mrow]),
                                 "min_angle_deg": float(info["min_angle_deg"][mrow]), "overhang": bool(info["overhang"][mrow])},
                    "y_top_max": float(np.nanmax(info["y_top"])),
                    "knot_jump_raw_max_m": (np.abs(K_all[k] - K_all[k - 1]).max(0).round(3).tolist() if k > 0 else None),
                    "knot_jump_used_max_m": (np.abs(K_sm[k] - K_sm[k - 1]).max(0).round(3).tolist() if k > 0 else None),
                    "white_on_rows": int(won[:, 0].sum())})
        np.save(od + "/sheet_sim_%04d.npy" % fi, G.astype(np.float32))
        np.savez_compressed(od + "/sheet_attr_%04d.npz" % fi, t=t, K=info["K"], y_top=info["y_top"], x_top=info["x_top"],
                            overhang=info["overhang"], min_angle_deg=info["min_angle_deg"], whiteSD=wsd.astype(np.float32),
                            whiteOn=won[:, 0].astype(np.uint8), u=u.astype(np.float32), F=F.astype(np.float32))
        print("%s t=%.3f conv %.2fs fit p95 %.3f p99 %.3f max %.2f | overhang rows %d drop %d | %.0fs" % (
            seq, t, t_conv, met["fit_fluid_to_sheet"][-1]["p95"], met["fit_fluid_to_sheet"][-1]["p99"],
            met["fit_fluid_to_sheet"][-1]["max"], info["overhang"].sum(), (info["ndrop"] > 0).sum(), time.time() - t_start), flush=True)
    common = {"schema": "GreatWave.F37.seq/1", "seq": seq, "label_ja": cfg["label_ja"], "rate_hz": 1.0 / np.median(np.diff([x[0] for x in frames])),
              "placement": {"anchor": cfg["anchor"], "psi_deg": cfg["psi"], "s": cfg["s"], "O": O.tolist(), "T": T.tolist(), "E": E.tolist(),
                            "note_ja": "p2_common.place と同じ一様の倍率・回転・平行移動だけ（形は変えない）"},
              "layout": "position3,normal3,uv3_4,uv4_4,uv5_4,uv6_4 の平面の float32、続いて uint32 の三角形（書式 GreatWave.AS03.static_mesh/1 の .bin と同じ並び）"}
    if not no_unity:
        json.dump({**common, "method": "sheet", "topology": "fixed", "frames": idx_sheet}, open(pk + "/sheet/index.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
        json.dump({**common, "method": "frames", "topology": "variable", "frames": idx_frames}, open(pk + "/frames/index.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    nfr = len(frames)
    nvA = C.NV * C.NU
    summ = {
        "seq": seq, "label_ja": cfg["label_ja"], "frames": nfr, "t_range": [frames[0][0], frames[-1][0]], "rate_hz": common["rate_hz"],
        "rows_c": cfg["c"], "zc": cfg["zc"], "wall_s": time.time() - t_start, "sigma_t_frames": sigma_t, "landmarks_version": 2,
        "fit_fluid_to_sheet_all": {"p95_max_over_frames": max(x["p95"] for x in met["fit_fluid_to_sheet"]),
                                   "p99_max_over_frames": max(x["p99"] for x in met["fit_fluid_to_sheet"]),
                                   "max_over_frames": max(x["max"] for x in met["fit_fluid_to_sheet"]),
                                   "frac_gt_1m_max": max(x["frac_gt_1m"] for x in met["fit_fluid_to_sheet"])},
        "fit_sheet_mid_all": {"p99_max_over_frames": max(x["p99"] for x in met["fit_sheet_mid_to_fluid"]),
                              "max_over_frames": max(x["max"] for x in met["fit_sheet_mid_to_fluid"])},
        "A_step_max": max((x["max"] for x in met["A_step"]), default=None),
        "A_d2_p99_max": max((x["p99"] for x in met["A_d2"]), default=None),
        "A_d2_max": max((x["max"] for x in met["A_d2"]), default=None),
        "A_d2_p99_g_max": max((x["p99_g"] for x in met["A_d2"]), default=None),
        "A_frames_with_d2_over_2m": sum(1 for x in met["A_d2"] if x["n_over_2m"] > 0),
        "A_tangent_p99_max": max((x["tangent_p99"] for x in met["A_step"]), default=None),
        "A_normal_p99_max": max((x["normal_p99"] for x in met["A_step"]), default=None),
        "A_interp_skip1_p95_median": float(np.median([x["p95"] for x in met.get("A_interp_skip1", [])])) if met.get("A_interp_skip1") else None,
        "A_interp_skip1_p99_max": max((x["p99"] for x in met.get("A_interp_skip1", [])), default=None),
        "A_interp_skip1_max": max((x["max"] for x in met.get("A_interp_skip1", [])), default=None),
        "B_jump_p95_median": float(np.median([x["p95"] for x in met["B_jump"]])) if met["B_jump"] else None,
        "B_jump_p99_max": max((x["p99"] for x in met["B_jump"]), default=None),
        "B_components_range": [min(x["n"] for x in met["B_components"]), max(x["n"] for x in met["B_components"])],
        "B_small_components_max": max(x["small_lt50"] for x in met["B_components"]),
        "sizes": {"sheet_vertices": nvA, "sheet_triangles": int(len(tri_sheet)),
                  "frames_vertices_range": [min(sizes["frames_verts"]), max(sizes["frames_verts"])],
                  "frames_hero_vertices_range": [min(r["fluid_verts_in_hero"] for r in rec), max(r["fluid_verts_in_hero"] for r in rec)],
                  "test_sheet_MB_per_frame": float(np.mean(sizes["sheet_bytes"]) / 1e6),
                  "test_frames_MB_per_frame": float(np.mean(sizes["frames_bytes"]) / 1e6),
                  "prod_sheet_keypose_MB_per_layer": nvA * 8 / 1e6,
                  "prod_sheet_keypose_plus_lo_MB_per_layer": nvA * 12 / 1e6,
                  "prod_sheet_static_attr_MB_once": nvA * 12 * 4 / 1e6 + len(tri_sheet) * 12 / 1e6,
                  "note_ja": "試験の書き出しは float32 で全部のチャンネルをコマごとに書いた（Unity の確かめ用）。作品の形式の見込み："
                             "方法 A は今の keypose（RGBA16＝8 B/頂点/コマ、精度の層 RGBA8 を足して 12 B）と、属性 12 個 float32 と三角形を 1 回だけ。"
                             "方法 B は頂点の番号がコマごとに違うので、位置・法線・属性・三角形をコマごとに全部持つ（下の frames の値）。"},
    }
    json.dump({"summary": summ, "metrics": met, "frames": rec}, open(od + "/metrics.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
