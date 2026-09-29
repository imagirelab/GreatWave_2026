# -*- coding: utf-8 -*-
"""設計33（爪の部）：生成器（ds33_claw_rig.py・ds33_claw_anim.py）と別の組み立てで、受入の値を数え直す（numpy。Unity の描画ではない）。

- 主役波の位置は ds31_white.Pkg（設計31 の numpy の Hermite。生成器は ds30_checks.Pkg と ds27_player_ref の重み）＋ O(τ)。τ(t) は時間曲線の表を読み直す。
- 105：各爪の根元の頂点（ds33_claw_frames_f32.bin の爪の最初の頂点）と、根元のセルの 2 つの三角形の面との距離（この検査の中の式）。
- 137：根元の頂点の、根元のセルの三角形の中での重心座標（最小二乗）から材料の座標 (行, 列) を読み、設計32 の sheet_rc との差（セル）と、セルの辺の長さを掛けた m。
- 139：見える（骨格のファイルの 35 番目の値）が τ ≥ τ_start（ds33_claw_rig.json）と一致し、1 → 0 の変化がない。頂点が有限で、先端が根元から離れている（帯が潰れていない）。
- 成長の順（3 段の標準曲線）：ω が 1 に届くコマ ≤ g が 0.5 を越えるコマ（根元が白くなる → 伸びる）、g が 0.99 に届くコマ ≤ κ が 0.99 に届くコマ（最後に曲がる）。
- 頂点数：layout の爪ごとの頂点数 ≤ 600、主爪＋支の合計 ≤ 600。
- 瞬間移動：先端の頂点の 30 Hz の動きが、前後のコマの大きい方の 4 倍 + 5 cm を超える突出の数。
- t* の再投影：truthlib.project_world で根元・先端の頂点を投影し、一覧の表示の画素と比べる（記録のみ）。
出力：Unity/Build/Design/33/claws/ds33_claws_indep_check.json
"""
import json
import os
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
sys.path.insert(0, REPO + "/Tools/PaintingTruth")
import ds31_white as W31  # noqa: E402
import truthlib as T  # noqa: E402

OUT = REPO + "/Unity/Build/Design/33/claws"
D32 = REPO + "/Unity/Build/Design/32/list+ids"


def main():
    t0 = time.time()
    rig = json.load(open(OUT + "/ds33_claw_rig.json", encoding="utf-8"))
    lay = json.load(open(OUT + "/ds33_claw_layout.json", encoding="utf-8"))
    inv = json.load(open(D32 + "/ds32_claw_inventory.json", encoding="utf-8"))
    ids32 = json.load(open(D32 + "/ds32_ids.json", encoding="utf-8"))
    NFR, nv = lay["frames"], lay["vertices"]
    claws = rig["claws"]
    nc = len(claws)
    V = np.memmap(OUT + "/" + lay["files"]["frames"]["file"], np.float32, "r", shape=(NFR, nv, 3))
    SK = np.fromfile(OUT + "/" + lay["files"]["skel"]["file"], np.float32).reshape(NFR, nc, 36).astype(np.float64)
    pkg = W31.Pkg(REPO + "/" + rig["sheet"]["package"])
    R, C = pkg.R, pkg.C
    w = json.load(open(REPO + "/" + lay["timewarp"]["path"], encoding="utf-8"))
    taus = np.interp(np.arange(NFR) / float(lay["hz"]), np.array(w["t"]), np.array(w["tau"]))
    off = np.array([c["vert_offset"] for c in lay["claws"]])
    cnt = np.array([c["vert_count"] for c in lay["claws"]])
    rc32 = {c["id"]: c["sheet_rc"] for c in ids32["claws"] if c.get("bound")}
    rc = np.array([rc32[c["id"]] for c in claws], np.float64)
    r0 = np.clip(np.floor(rc[:, 0]).astype(int), 0, R - 2)
    c0 = np.clip(np.floor(rc[:, 1]).astype(int), 0, C - 2)
    tau_s = np.array([c["tau_start"] for c in claws])
    d105 = np.zeros((NFR, nc)); dpar = np.zeros((NFR, nc)); dslide = np.zeros((NFR, nc))
    for f, tau in enumerate(taus):
        Pw = pkg.eval(float(tau)) + pkg.origin(float(tau))[0]
        Pw = Pw.reshape(R, C, 3)
        a = Pw[r0, c0]; b = Pw[r0 + 1, c0]; cc = Pw[r0, c0 + 1]; d = Pw[r0 + 1, c0 + 1]
        p = np.asarray(V[f, off], np.float64)
        best = np.full(nc, np.inf); rr = np.zeros(nc); ccol = np.zeros(nc)
        for half, (A, B, Cc) in enumerate(((a, b, cc), (cc, b, d))):
            M = np.stack([B - A, Cc - A], -1)                      # n × 3 × 2
            rhs = p - A
            uv = np.linalg.solve(np.einsum("nki,nkj->nij", M, M), np.einsum("nki,nk->ni", M, rhs)[..., None])[..., 0]
            q = A + np.einsum("nij,nj->ni", M, uv)
            dist = np.linalg.norm(p - q, axis=1)
            outside = np.maximum.reduce([-uv[:, 0], -uv[:, 1], uv[:, 0] + uv[:, 1] - 1, np.zeros(nc)])
            score = dist + 10 * outside
            u, v = uv[:, 0], uv[:, 1]
            if half == 0:
                rr_h, cc_h = r0 + u, c0 + v
            else:
                rr_h, cc_h = r0 + u + v, c0 + 1 - u
            better = score < best
            best[better] = score[better]; rr[better] = rr_h[better]; ccol[better] = cc_h[better]
            d105[f, better] = dist[better]
        dr = rr - rc[:, 0]; dc = ccol - rc[:, 1]
        dpar[f] = np.hypot(dr, dc)
        er = np.linalg.norm(b - a, axis=1); ec = np.linalg.norm(cc - a, axis=1)
        dslide[f] = np.hypot(dr * er, dc * ec)
    vis = SK[:, :, 34] > 0.5
    exp_vis = taus[:, None] >= tau_s[None, :]
    vis_mismatch = int((vis != exp_vis).sum())
    off_trans = int((vis[:-1] & ~vis[1:]).sum())
    fin = bool(np.all(np.isfinite(np.asarray(V[::10]))))
    # 帯が潰れていない：見えるコマで先端（根元の点 + 1 + 輪 × 8 の次）と根元の距離 > 0
    tipi = off + 1 + np.array([c["stations"] for c in claws]) * 8
    collapse = 0
    for f in range(0, NFR, 5):
        dd = np.linalg.norm(np.asarray(V[f, tipi], np.float64) - np.asarray(V[f, off], np.float64), axis=1)
        collapse += int((vis[f] & (dd <= 1e-6)).sum())
    # 成長の順
    s, g, k, om = SK[:, :, 30], SK[:, :, 31], SK[:, :, 32], SK[:, :, 33]

    def first(mask):
        return np.array([int(np.argmax(mask[:, i])) if mask[:, i].any() else NFR for i in range(nc)])
    f_om1 = first(vis & (om >= 0.999)); f_g05 = first(vis & (g >= 0.5)); f_g99 = first(vis & (g >= 0.99)); f_k99 = first(vis & (k >= 0.99))
    order_bad_root = [claws[i]["id"] for i in range(nc) if f_om1[i] > f_g05[i]]
    order_bad_curl = [claws[i]["id"] for i in range(nc) if f_g99[i] > f_k99[i]]
    k_at_g99 = np.array([k[f_g99[i], i] if f_g99[i] < NFR else np.nan for i in range(nc)])
    # 頂点数
    inst = {}
    for c, n in zip(claws, cnt):
        key = c["parent"] if c["type"] == "branch" else c["id"]
        inst[key] = inst.get(key, 0) + int(n)
    # 先端の突出
    tip = np.asarray(V[:, tipi], np.float64)
    dm = np.linalg.norm(tip[1:] - tip[:-1], axis=-1)
    both = vis[1:] & vis[:-1]
    dn = np.zeros_like(dm); dn[1:-1] = np.maximum(dm[:-2], dm[2:]); dn[0] = dm[1]; dn[-1] = dm[-2]
    spikes = int((both & (dm > 4 * dn + 0.05)).sum())
    # t* の再投影（truthlib）
    spec = T.load_spec()
    byid = {c["id"]: c for c in inv["claws"]}
    x_, y_ = T.project_world(spec, np.asarray(V[-1, off], np.float64))[:2]
    rp = np.stack([x_, y_], -1)
    x_, y_ = T.project_world(spec, np.asarray(V[-1, tipi], np.float64))[:2]
    tp = np.stack([x_, y_], -1)
    e_root = np.array([np.hypot(*(rp[i][:2] - np.asarray(byid[c["id"]]["root_display"]))) for i, c in enumerate(claws)])
    e_tip = np.array([np.hypot(*(tp[i][:2] - np.asarray(byid[c["id"]]["tip_display"]))) for i, c in enumerate(claws)])
    d105v = np.where(vis, d105, 0); dsl = np.where(vis, dslide, 0); dpv = np.where(vis, dpar, 0)
    res = dict(
        schema="GreatWave.DS33.claws_indep_check/1", method_ja=__doc__,
        item105=dict(max_m=float(d105v.max()), pass_=bool(d105v.max() <= 1e-3)),
        item137=dict(max_param_cells=float(dpv.max()), max_m=float(dsl.max()), pass_=bool(dsl.max() <= 1e-3)),
        item139=dict(visibility_mismatch=vis_mismatch, visible_to_hidden=off_trans, finite=fin, collapsed_frames_every5=collapse,
                     pass_=bool(vis_mismatch == 0 and off_trans == 0 and fin and collapse == 0)),
        growth_order=dict(root_whitens_before_extend_bad=order_bad_root, curl_last_bad=order_bad_curl,
                          kappa_when_g_reaches_0p99=dict(max=float(np.nanmax(k_at_g99)), median=float(np.nanmedian(k_at_g99))),
                          pass_=bool(not order_bad_root and not order_bad_curl)),
        vertices=dict(per_claw_max=int(cnt.max()), per_instance_max=int(max(inst.values())), pass_=bool(cnt.max() <= 600 and max(inst.values()) <= 600)),
        tip_spikes=spikes,
        reprojection_tstar_truthlib=dict(root_max_px=float(e_root.max()), tip_max_px=float(e_tip.max()), tip_p95_px=float(np.percentile(e_tip, 95)),
                                         note_ja="先端の頂点は骨格の曲線の終わり（一覧の先端の表示の画素に置いた関節）。根元は設計32 の sheet_rc（寄せた根元はその分ずれる）"),
        inputs=dict(frames_sha256=lay["files"]["frames"]["sha256"], skel_sha256=lay["files"]["skel"]["sha256"]),
        elapsed_s=round(time.time() - t0, 1))
    with open(OUT + "/ds33_claws_indep_check.json", "w", encoding="utf-8", newline="\n") as fo:
        json.dump(res, fo, ensure_ascii=False, indent=1)
        fo.write("\n")
    print(json.dumps({k_: v_ for k_, v_ in res.items() if k_ not in ("method_ja",)}, ensure_ascii=False)[:2500])


if __name__ == "__main__":
    main()
