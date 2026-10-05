# -*- coding: utf-8 -*-
"""美術の見本06 の組み立て（Q34）：段の行（R8）と塊（LB2）を、見本05 B（B10）と同じ決まりで並べて確かめる（読むだけ。形・材質は変えない）。

確かめること（どれも二つの作りと B10 に同じ道具を当てる）：
  1. 主役波と wave4 の食い込み（3D）：合わせた静止のメッシュの主役波の部分（サブ行 × 列の格子、uv6）と wave4 の格子（wave4_grid.npz）を、
     断面の座標（a・y・c）で比べ、海の上（y > 0.05 m）で相手の体の中に入る頂点を数える（c の 1 m ごとの数と最大の深さ）。
  2. G1 の帯の座標 w の伸び（asm4_rules.stretch_masks、見本05 と同じ決まり）を三つに同じ道具で数え、海の上か下かに分ける。
  3. 原画視点（Unity、爪あり − 爪なし）で、B10 で見えていた爪の塊が、新しい形で隠れていないか（塊ごとの画素）。
  4. 一艘目の船（Unity の ID の画、boat_left = (34,0,0)）の画素と、ほかの描画との差（隠す物の ID）。
使い方：py -3.10 -B Tools/GWWaveGen/as06/asm6_check.py <出力.json> [名前=描画のフォルダー ...]
"""
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as04")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as06")
import shape_common as S  # noqa: E402

P = REPO + "/Unity/Build/Polish"
BUILDS = {
    "B10": {"union": P + "/sample05/fix1/assemble/B/mesh/union_AS05B_f1.json", "hero": P + "/sample05/fix1/B/mesh/hero_smooth_as05b.json",
            "render": P + "/sample05/fix1/assemble/render/B10"},
    "R8": {"union": P + "/sample06/rows/mesh/union_AS06R_d_f1.json", "hero": P + "/sample06/rows/final_d/mesh/hero_smooth_as06r.json",
           "render": P + "/sample06/rows/render/R8"},
    "LB2": {"union": P + "/sample06/lobes/assemble2/mesh/union_AS06L.json", "hero": P + "/sample06/lobes/final2/mesh/hero_smooth_as06l.json",
            "render": P + "/sample06/lobes/assemble2/render/LB2"},
}
W4GRID = P + "/sample04/wave4/mesh_fix1/wave4_grid.npz"


def load_static(js):
    meta = json.load(open(js, encoding="utf-8"))
    n = meta["vertices"]
    raw = np.fromfile(os.path.join(os.path.dirname(js), meta["bin"]), np.float32)
    off = 0
    ch = {}
    for nm, k in meta["channels"]:
        ch[nm] = raw[off:off + n * k].reshape(n, k); off += n * k
    tris = raw[off:].view(np.uint32).reshape(-1, 3).astype(np.int64)
    return ch, tris, meta


def inside_poly(px, py, qa, qy):
    """偶奇の規則の点の内外（多角形 qa・qy は閉じていなくてよい）。"""
    xa = np.r_[qa, qa[0]]; ya = np.r_[qy, qy[0]]
    ins = np.zeros(len(px), bool)
    for i in range(len(xa) - 1):
        x0, y0, x1, y1 = xa[i], ya[i], xa[i + 1], ya[i + 1]
        cond = (y0 > py) != (y1 > py)
        if not cond.any():
            continue
        xc = x0 + (py - y0) * (x1 - x0) / ((y1 - y0) if y1 != y0 else 1e-12)
        ins ^= cond & (px < xc)
    return ins


def seg_dist(px, py, qa, qy):
    """点から折れ線（閉じた多角形）までの距離。"""
    xa = np.r_[qa, qa[0]]; ya = np.r_[qy, qy[0]]
    best = np.full(len(px), np.inf)
    for i in range(len(xa) - 1):
        ax, ay, bx, by = xa[i], ya[i], xa[i + 1], ya[i + 1]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / (L if L > 0 else 1e-12), 0, 1)
        best = np.minimum(best, np.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def interpenetration(name, b):
    ch, tri, meta = load_static(b["union"])
    um = json.load(open(b["union"].replace("assemble/B/mesh/union_AS05B_f1.json", "B/union/union.json")
                        .replace("rows/mesh/union_AS06R_d_f1.json", "rows/final_d/union/union.json")
                        .replace("lobes/assemble2/mesh/union_AS06L.json", "lobes/final2/union/union.json"), encoding="utf-8"))
    nh = int(um["parts"][0]["vertices"])
    pos = ch["position"].astype(np.float64)
    Qh = S.sec(pos[:nh]); Qw = S.sec(pos[nh:])
    row = np.round(ch["uv6"][:nh, 0].astype(np.float64), 4); col = ch["uv6"][:nh, 1].astype(np.float64)
    rv, sr = np.unique(row, return_inverse=True)
    c_sr = np.bincount(sr, Qh[:, 2], len(rv)) / np.maximum(np.bincount(sr, None, len(rv)), 1)
    res = {"hero_vertices": nh, "wave4_vertices": int(len(pos) - nh), "hero_c_range_m": [S.rnd(Qh[:, 2].min(), 2), S.rnd(Qh[:, 2].max(), 2)],
           "hero_subrows": int(len(rv))}
    # (a) wave4 の頂点が主役波の体の中（最も近いサブ行の閉じた断面の中）
    w_in = np.zeros(len(Qw), bool); w_depth = np.zeros(len(Qw))
    o_sr = np.argsort(c_sr); cs = c_sr[o_sr]
    j = np.clip(np.searchsorted(cs, Qw[:, 2]), 1, len(cs) - 1)
    j = np.where(np.abs(cs[j - 1] - Qw[:, 2]) < np.abs(cs[j] - Qw[:, 2]), j - 1, j)
    near_sr = o_sr[j]
    dc = np.abs(c_sr[near_sr] - Qw[:, 2])
    for k in np.unique(near_sr):
        m = (near_sr == k) & (dc < 0.3) & (Qw[:, 1] > 0.05)
        if not m.any():
            continue
        jj = np.nonzero(sr == k)[0]
        jj = jj[np.argsort(col[jj])]
        qa, qy = Qh[jj, 0], Qh[jj, 1]
        ins = inside_poly(Qw[m, 0], Qw[m, 1], qa, qy)
        idx = np.nonzero(m)[0][ins]
        w_in[idx] = True
        if len(idx):
            w_depth[idx] = seg_dist(Qw[idx, 0], Qw[idx, 1], qa, qy)
    # (b) 主役波の頂点が wave4 の体の中（wave4 の格子の行 c の断面＝地面で閉じた多角形）
    z = np.load(W4GRID)
    wc, WA, WY = z["c"], z["A"], z["Y"]
    h_in = np.zeros(nh, bool); h_depth = np.zeros(nh)
    sel = (Qh[:, 2] >= wc.min()) & (Qh[:, 2] <= wc.max()) & (Qh[:, 1] > 0.05)
    iw = np.clip(np.round((Qh[:, 2] - wc[0]) / (wc[1] - wc[0])).astype(int), 0, len(wc) - 1)
    for i in np.unique(iw[sel]):
        m = sel & (iw == i)
        qa = np.r_[WA[i], WA[i][::-1]]; qy = np.r_[WY[i], np.full(len(WY[i]), -1.0)]
        ins = inside_poly(Qh[m, 0], Qh[m, 1], qa, qy)
        idx = np.nonzero(m)[0][ins]
        h_in[idx] = True
        if len(idx):
            h_depth[idx] = seg_dist(Qh[idx, 0], Qh[idx, 1], WA[i], WY[i])

    def summ(Q, ins, dep):
        if not ins.any():
            return {"count": 0}
        cc = Q[ins, 2]
        hist = {}
        for e in np.arange(np.floor(cc.min()), np.ceil(cc.max()) + 1):
            k = int(((cc >= e) & (cc < e + 1)).sum())
            if k:
                hist["%.0f" % e] = k
        return {"count": int(ins.sum()), "depth_m_p50_p95_max": [S.rnd(np.median(dep[ins])), S.rnd(np.percentile(dep[ins], 95)), S.rnd(dep[ins].max())],
                "deeper_than_0p1m": int((dep[ins] > 0.1).sum()), "c_hist_1m": hist,
                "a_range": [S.rnd(Q[ins, 0].min(), 2), S.rnd(Q[ins, 0].max(), 2)], "y_range": [S.rnd(Q[ins, 1].min(), 2), S.rnd(Q[ins, 1].max(), 2)]}
    res["wave4_vertices_inside_hero"] = summ(Qw, w_in, w_depth)
    res["hero_vertices_inside_wave4"] = summ(Qh, h_in, h_depth)
    return res


def stretch(name, b):
    os.environ["AS04_FIX"] = "fix1"
    import asm4_common as A  # noqa: E402
    import asm4_rules as R  # noqa: E402
    A.N_HERO = int(json.load(open(b["hero"], encoding="utf-8"))["vertices"])
    m = R.stretch_masks(b["hero"], "hero")
    bad = m["sel"] & m["pat"] & ((m["gw"] < 1 / 3) | (m["gw"] > 3))
    Q = A.K.sec(m["pos"])
    t = m["tri"][bad]
    ym = Q[:, 1][t].mean(1); cm = Q[:, 2][t].mean(1)
    out = {"bad_tri": int(bad.sum()), "above_sea_y_gt_0": int((ym > 0).sum()), "above_y_gt_1m": int((ym > 1.0).sum()),
           "pattern_tris": int((m["sel"] & m["pat"]).sum())}
    if bad.any():
        out["c_p0_p50_p100"] = [S.rnd(x, 2) for x in np.percentile(cm, (0, 50, 100))]
    return out


def claw_vis(renders):
    D = {}
    for k, v in renders.items():
        a = cv2.imread(v + "/views/painting_t120_claws.png").astype(int)
        b = cv2.imread(v + "/views/painting_t120_clawfree.png").astype(int)
        D[k] = np.abs(a - b).sum(-1) > 30
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(D["B10"].astype(np.uint8), np.ones((5, 5), np.uint8)))
    comps = []
    for i in range(1, n):
        if st[i, 4] < 60:
            continue
        m = lab == i
        b0 = int((D["B10"] & m).sum())
        row = {"xywh_display": st[i, :4].tolist(), "B10_px": b0}
        lost = False
        for k in renders:
            if k == "B10":
                continue
            r = int((D[k] & m).sum()); row[k + "_px"] = r
            lost |= r < 0.7 * b0
        if lost:
            comps.append(row)
    return {"diff_px_total": {k: int(d.sum()) for k, d in D.items()}, "components_lost_gt_30pct_vs_B10": comps,
            "method_ja": "原画視点の Unity の画（爪あり − 爪なし、色の差 > 30）。B10 の爪の塊ごとに、新しい形の描画で残る画素を数え、3 割より多く減った塊を挙げる"}


def boat(renders):
    ims = {k: cv2.imread(v + "/full/ids_noline_noclaws.png")[..., ::-1] for k, v in renders.items()}
    bm = {k: (im[..., 0] == 34) & (im[..., 1] == 0) & (im[..., 2] == 0) for k, im in ims.items()}
    allb = np.zeros_like(next(iter(bm.values())))
    for k, m in bm.items():
        if k != "B10":
            allb |= m
    out = {"boat_left_px_2x": {k: int(m.sum()) for k, m in bm.items()}, "union_of_moved_px_2x": int(allb.sum()), "missing_vs_union": {}}
    names = {(0, 255, 255): "sky", (255, 255, 0): "sea", (255, 0, 0): "hero", (0, 255, 0): "wave4", (0, 0, 255): "other_blue",
             (34, 34, 0): "boat_other", (0, 34, 0): "boat_other2", (0, 0, 0): "black"}
    for k, m in bm.items():
        if k == "B10":
            continue
        miss = allb & ~m
        cols, cnt = np.unique(ims[k][miss].reshape(-1, 3), axis=0, return_counts=True)
        out["missing_vs_union"][k] = {"px": int(miss.sum()), "covered_by": {names.get(tuple(int(x) for x in c), str(tuple(int(x) for x in c))): int(n_) for c, n_ in zip(cols, cnt)}}
    out["note_ja"] = "ID の色の名は、画の中の最も多い所（空・海・主役波の中ほど・左の wave4）から進行役が読んだもの"
    return out


def main():
    out_p = sys.argv[1]
    extra = dict(a.split("=", 1) for a in sys.argv[2:])
    renders = {k: b["render"] for k, b in BUILDS.items()}
    renders.update(extra)
    res = {"schema": "GreatWave.AS06.asm6_check/1", "tool": "Tools/GWWaveGen/as06/asm6_check.py",
           "inputs": {k: {"union": b["union"], "union_bin_sha256": json.load(open(b["union"], encoding="utf-8"))["sha256"], "hero": b["hero"],
                          "render": b["render"]} for k, b in BUILDS.items()},
           "interpenetration_hero_wave4": {}, "g1_stretch": {}}
    for k, b in BUILDS.items():
        res["interpenetration_hero_wave4"][k] = interpenetration(k, b)
        print(k, "interp", json.dumps(res["interpenetration_hero_wave4"][k], ensure_ascii=False)[:600], flush=True)
        res["g1_stretch"][k] = stretch(k, b)
        print(k, "stretch", res["g1_stretch"][k], flush=True)
    res["painting_claw_visibility"] = claw_vis(renders)
    res["boat_left"] = boat(renders)
    print(json.dumps(res["painting_claw_visibility"], ensure_ascii=False))
    print(json.dumps(res["boat_left"], ensure_ascii=False))
    S.jdump(out_p, res)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
