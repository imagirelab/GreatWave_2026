# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4：別の波（④）と主役波を合わせた検査と粘土の下見（numpy の z バッファ。Unity の描画ではない）。

1. 原画視点の頂の輪郭（主役波 ∪ 別の波）と区間 78 の真値の差（表示の画素、縦の差と最も近い距離）、どの物が輪郭を作るか（④ の x 0〜360）。
2. 合わせた背の高さ H(c)（c の 0.5 m ごとの最大）が一つの山か（頂から左右へ単調に下がるか、へこみの深さ）。
3. 交わり：主役波の頂点のうち別の波の足もとにある物が、別の波の面より上に出ていないか（静止のメッシュの全頂点）。
4. 粘土の下見：原画・座席・座席から波・左右の側面・後ろ 65°・真上（主役波は灰、別の波は青みの粘土、近い海は淡い色）。
使い方：py -3.10 -B Tools/GWWaveGen/as04/w4_check.py [--hero-rows R] [--hero-mesh M] [--wave4 J] [--tag 名前]
出力：Unity/Build/Polish/sample04/wave4/check/<tag>/（Git 対象外）
"""
import argparse
import json
import os

import cv2
import numpy as np

import w4_common as W
import w4_build as B
import s4_render as SR

S, K, CC = W.S, W.K, W.CC
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
COL = {"hero": (196, 196, 190), "wave4": (120, 150, 196), "sea": (214, 222, 226)}


def load_scene(hero_rows, wave4_json):
    c, A, Y = W.load_rows(hero_rows)
    XH = K.world(c, A, Y).reshape(-1, 3)
    TH = K.triangles(A.shape[1], A.shape[0])
    ch, T4, _ = W.read_static(wave4_json)
    X4 = ch["position"].astype(np.float64)
    sg = K.read_gwb(S.SEA_NEAR)
    return dict(XH=XH, TH=TH, X4=X4, T4=T4.astype(np.int64), XS=sg["X"], TS=sg["tris"].astype(np.int64), rows=(c, A, Y))


def tris_all(sc, with_sea=True, with_w4=True):
    parts = [(sc["XH"][sc["TH"]], "hero")]
    if with_w4:
        parts.append((sc["X4"][sc["T4"]], "wave4"))
    if with_sea:
        parts.append((sc["XS"][sc["TS"]], "sea"))
    tris = np.concatenate([p[0] for p in parts])
    lab = np.concatenate([np.full(len(p[0]), i) for i, p in enumerate(parts)])
    names = [p[1] for p in parts]
    return tris, lab, names


def silhouette(sc, scale=2):
    cam = B.painting_cam(scale)
    seg = S.outline_segments()["78"]
    res = {}
    for name, w4 in (("hero_only", False), ("union", True)):
        tris, lab, names = tris_all(sc, with_sea=False, with_w4=w4)
        idb, zb = S.U.raster(cam, tris, np.arange(1, len(tris) + 1))
        idb = idb.reshape(cam.H, cam.W)
        m = idb > 0
        top = np.where(m.any(0), np.argmax(m, 0), -1)
        rows = []
        # 真値の点ごと：縦の差、輪郭の画素への最も近い距離
        edge = np.zeros_like(m)
        edge[1:] |= m[1:] & ~m[:-1]
        ey, ex = np.nonzero(edge)
        for x, yr in seg[::2]:
            px, py = B.ref_to_px(x, yr, scale)
            col = int(round(float(px)))
            if not (0 <= col < cam.W) or top[col] < 0:
                continue
            tid = idb[top[col], col] - 1
            owner = names[lab[tid]]
            dv = (top[col] - 0.5 - float(py)) / scale
            near = np.hypot(ex - px, ey - 0.5 - py)
            rows.append((float(x), float(yr), dv, float(near.min()) / scale, owner))
        res[name] = rows
        if w4:
            # ④ の楔：列ごとに、別の波が見えている画素の下の縁（原画の y）と、原画の楔の下の縁（調べ S の測り）
            M = json.load(open(S.OUT + "/s4_map.json", encoding="utf-8"))
            wl = {e["x_ref"]: e.get("wedge_lower_edge_y_ref_smooth") for e in M["region4"]["columns"]}
            wed = []
            for x in range(4, 361, 16):
                px, _ = B.ref_to_px(x, 900.0, scale)
                col = int(round(float(px)))
                own = lab[np.maximum(idb[:, col] - 1, 0)] == names.index("wave4")
                own &= idb[:, col] > 0
                if not own.any():
                    wed.append([x, None, wl.get(x)]); continue
                yb = np.nonzero(own)[0].max()
                yr = (yb + 0.5) / scale / S.A_DISP - 0.5
                wed.append([x, W.rnd(yr, 1), wl.get(x)])
            res["wedge"] = wed
    out = {"wedge_visible_lower_y_ref_vs_painting": res.pop("wedge")}
    for name, rows in res.items():
        dv = np.array([r[2] for r in rows]); dn = np.array([r[3] for r in rows]); xs = np.array([r[0] for r in rows])
        r4 = xs <= 360
        own = [r[4] for r in rows if r[0] <= 360]
        out[name] = {"seg78_vertical_absmax_px": W.rnd(np.abs(dv).max()), "seg78_vertical_p95_px": W.rnd(np.percentile(np.abs(dv), 95)),
                     "seg78_nearest_max_px": W.rnd(dn.max()), "seg78_nearest_p95_px": W.rnd(np.percentile(dn, 95)),
                     "region4_x0_360_nearest_max_px": W.rnd(dn[r4].max()), "region4_vertical_absmax_px": W.rnd(np.abs(dv[r4]).max()),
                     "region4_owner_share": {k: W.rnd(own.count(k) / max(len(own), 1)) for k in set(own)},
                     "by_x": [[W.rnd(r[0], 0), W.rnd(r[2], 2), W.rnd(r[3], 2), r[4]] for r in rows[::3]]}
    return out


def back_profile(sc):
    c, A, Y = sc["rows"]
    Q4 = K.sec(sc["X4"])
    bins = np.arange(-40, 20.01, 0.5)
    Hh = np.full(len(bins) - 1, 0.0); Hu = np.full(len(bins) - 1, 0.0)
    hc = np.interp(0.5 * (bins[:-1] + bins[1:]), c, Y.max(1))
    k4 = np.digitize(Q4[:, 2], bins) - 1
    w4 = np.zeros(len(bins) - 1)
    for k in range(len(bins) - 1):
        sel = k4 == k
        w4[k] = Q4[sel, 1].max() if sel.any() else 0.0
    Hh = hc; Hu = np.maximum(hc, w4)

    def dip(H):
        i = int(np.argmax(H))
        L = H[:i + 1][::-1]; R = H[i:]
        dl = float(np.max(np.maximum.accumulate(L[::-1])[::-1] - L)) if len(L) else 0.0
        # 頂から外へ進んで、それまでの最小より上がった量の最大（へこみの深さ）
        def rise(seq):
            m = np.minimum.accumulate(seq)
            return float(np.max(seq - m))
        return {"peak_c": W.rnd(0.5 * (bins[i] + bins[i + 1])), "peak_H": W.rnd(H[i]), "dip_left_m": W.rnd(rise(L)), "dip_right_m": W.rnd(rise(R))}
    cm = 0.5 * (bins[:-1] + bins[1:])
    sel = (cm >= -30) & (cm <= -4)
    return {"hero_only": dip(Hh), "union": dip(Hu),
            "by_c": [[W.rnd(a, 2), W.rnd(b, 2), W.rnd(cc, 2)] for a, b, cc in zip(cm[sel][::2], Hh[sel][::2], w4[sel][::2])]}


def penetration(hero_mesh, sc, g):
    """主役波の静止のメッシュの頂点の、別の波の面からの高さ（別の波の残した三角形の足もとだけ）。"""
    ch, _, _ = W.read_static(hero_mesh)
    Q = K.sec(ch["position"].astype(np.float64))
    cs, dg = g["c"], g["d"]
    ac = np.interp(Q[:, 2], cs, g["ac"])
    d = (Q[:, 0] - ac) / np.interp(Q[:, 2], cs, g["fw"])
    inside = (Q[:, 2] > cs[0]) & (Q[:, 2] < cs[-1]) & (d > dg[0]) & (d < dg[-1])
    ir = np.interp(Q[inside, 2], cs, np.arange(len(cs)))
    jc = np.interp(d[inside], dg, np.arange(len(dg)))
    r0 = np.clip(np.floor(ir).astype(int), 0, len(cs) - 2); j0 = np.clip(np.floor(jc).astype(int), 0, len(dg) - 2)
    fr = ir - r0; fj = jc - j0
    keep = np.zeros(g["Y"].shape, bool).ravel()
    keep[g["used"]] = True
    keep = keep.reshape(g["Y"].shape)
    Yg = g["Y"]
    ys = (Yg[r0, j0] * (1 - fr) * (1 - fj) + Yg[r0 + 1, j0] * fr * (1 - fj) + Yg[r0, j0 + 1] * (1 - fr) * fj + Yg[r0 + 1, j0 + 1] * fr * fj)
    kk = keep[r0, j0] & keep[r0 + 1, j0] & keep[r0, j0 + 1] & keep[r0 + 1, j0 + 1]
    above = Q[inside, 1][kk] - ys[kk]
    return {"hero_vertices_under_wave4": int(kk.sum()), "max_hero_above_wave4_m": W.rnd(float(above.max()), 4) if kk.any() else None,
            "count_above_0": int((above > 0).sum()), "count_above_1cm": int((above > 0.01).sum())}


def clay(sc, out, W_=1600, H_=900):
    tris, lab, names = tris_all(sc)
    rgb = np.array([COL[names[k]] for k in lab], np.float64)
    imgs = {}
    for v in VIEWS:
        cam = B.painting_cam(1) if v == "painting" else CC.cam_view(v, W_, H_)
        if v == "painting":
            cam = S.CC.U.CamWH(json.load(open(S.CC.U.TRUTH, encoding="utf-8")), W_, H_)
        img, _ = SR.render(cam, tris, rgb)
        p = os.path.join(out, "clay_%s.png" % v)
        cv2.imwrite(p, img[..., ::-1])
        imgs[v] = p
    return imgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero-rows", default=W.OUT + "/standin/standin_rows.npz")
    ap.add_argument("--hero-mesh", default=W.OUT + "/standin/hero_standin.json")
    ap.add_argument("--wave4", default=W.OUT + "/mesh/wave4.json")
    ap.add_argument("--grid", default=W.OUT + "/mesh/wave4_grid.npz")
    ap.add_argument("--tag", default="standin")
    ap.add_argument("--no-clay", action="store_true")
    a = ap.parse_args()
    out = W.OUT + "/check/" + a.tag
    os.makedirs(out, exist_ok=True)
    sc = load_scene(a.hero_rows, a.wave4)
    g = dict(np.load(a.grid))
    rep = {"schema": "GreatWave.AS04.w4_check/1", "hero_rows": a.hero_rows, "hero_rows_sha256": W.sha(a.hero_rows),
           "hero_mesh": a.hero_mesh, "wave4": a.wave4, "wave4_json_sha256": W.sha(a.wave4),
           "note_ja": "numpy の z バッファの測り（Unity の描画ではない）。原画視点の画素は表示（1920×1080）の画素。",
           "silhouette": silhouette(sc), "back_H": back_profile(sc), "penetration": penetration(a.hero_mesh, sc, g)}
    if not a.no_clay:
        rep["clay"] = clay(sc, out)
    W.jdump(out + "/w4_check.json", rep)
    s = rep["silhouette"]
    print(json.dumps({k: ({kk: vv for kk, vv in s[k].items() if kk != "by_x"} if isinstance(s[k], dict) else s[k]) for k in s}, ensure_ascii=False))
    print(json.dumps({k: v for k, v in rep["back_H"].items() if k != "by_c"}, ensure_ascii=False))
    print(json.dumps(rep["penetration"]))


if __name__ == "__main__":
    main()
