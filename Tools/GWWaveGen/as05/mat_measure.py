# -*- coding: utf-8 -*-
"""美術の見本05 の材質 AS05（Q33）：T5（波の本体の白い粒）と T6（唇の下の内の縁の白・水色）を Unity の描画で測る。

  py -3.10 -B Tools/GWWaveGen/as05/mat_measure.py --render <描画のフォルダー> --mesh <静止のメッシュ .json> --out <測りの .json>
      [--rows <主役波の行の npz>] [--hero-verts 314400] [--edge-report <mat_edge の報告 .json>]

測る物：
  K-T5（調べの決めごと、targets.json と同じ）：原画視点の爪なしの描画で、主役波の藍の面に囲まれた白・水色の小さな塊（2〜400 画素）の数。
       Tools/GWWaveGen/as05/s5_targets.py の appearance をそのまま呼ぶ（主役波の画素の印も同じ：行の npz の格子を numpy で描いた印）。
  K-T6（同じ）：利用者の切り出し（x 736〜891、y 300〜721）で、藍の面の右の縁から 16 画素の帯の、主役波の画素のうち白・水色の割合。
  T5 の広げ：7 視点と波頭の回り台 8 方位の爪なしの描画で、同じ数え方（主役波の印は静止のメッシュを numpy で描いた印）。
  T6 の広げ（面の縁で決める）：主役波が空に接する縁の画素から内へ 16 画素の主役波の画素のうち、白・水色の割合と数。
       原画視点は利用者の切り出しの中、座席は mat_edge の規則の行（サブ行の範囲）の縁だけ。爪ありの描画（利用者が見た画）で測る。
  P1・P2（③・② の帯の色の割合）も s5_targets の appearance が出すので記録する（材質の変更がそれを動かしていないかを見る）。
原画の色は面へ写さない。原画のカメラは測りにだけ使う。
"""
import argparse
import glob
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_common as M  # noqa: E402
import s5_targets as T  # noqa: E402

T0 = time.time()


def log(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def blobs(cls, hero, lo=2, hi=400):
    """白・水色の小さな塊（lo〜hi 画素）で、周りの 90% 超が藍（5×5 で太らせた藍）、中心が主役波の画素のもの。戻り値：(数, 中心の列)。"""
    pale = np.isin(cls, (2, 3)).astype(np.uint8)
    n, labm, st, cen = cv2.connectedComponentsWithStats(pale, connectivity=8)
    ind_d = cv2.dilate((cls == 1).astype(np.uint8), np.ones((5, 5), np.uint8))
    out = []
    for i in range(1, n):
        a = st[i, cv2.CC_STAT_AREA]
        if lo <= a <= hi:
            x, y, w, h = st[i, :4]
            blob = (labm[y:y + h, x:x + w] == i)
            ring = cv2.dilate(np.pad(blob, 1).astype(np.uint8), np.ones((3, 3), np.uint8))[1:-1, 1:-1].astype(bool) & ~blob
            if ring.any() and ind_d[y:y + h, x:x + w][ring].mean() > 0.9 and hero[y + h // 2, x + w // 2]:
                out.append((int(x + w // 2), int(y + h // 2), int(a)))
    return len(out), out


def hero_label(view, ch, tri, nh, W=1920, H=1080):
    tris, lab, th = M.scene(ch, tri, nh, claws=None)
    cm, idb, D, L = M.raster(view, tris, lab, W, H)
    return cm, idb, D, L, th


def edge_band(D, L, region=None, band_px=16):
    C, sky = M.sky_contour(D, L)
    if region is not None:
        C = C & region
    d = ndi.distance_transform_edt(~C)
    return (L == 1) & (d <= band_px) & ~sky, C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", default=M.P4 + "/fix1/shape/final/cand/kstarAS04F_a45_rows.npz")
    ap.add_argument("--hero-verts", type=int, default=M.N_HERO04F)
    ap.add_argument("--edge-report", default=None)
    g = ap.parse_args()
    res = {"schema": "GreatWave.AS05.mat_measure/1", "date": time.strftime("%Y-%m-%d %H:%M"), "render": M.rel(g.render), "mesh": M.rel(g.mesh),
           "tool": M.rel(__file__), "tool_sha256": M.sha(__file__)}
    # ---- K-T5・K-T6（調べの決めごと）
    log("K-T5・K-T6（s5_targets.appearance）")
    cand = {"rows": g.rows, "row_labels": None, "meshes": [{"path": M.P4 + "/wave4/mesh_fix1/wave4.json", "role": "wave4", "layer": 0}]}
    c, Ar, Yr, RL, meshes = T.load_cand(cand)
    tris_s, lab_s = T.scene(c, Ar, Yr, RL, meshes)
    _, hero_mask_s, _ = T.painting_consistency(tris_s, lab_s)
    ap_ = T.appearance(g.render, hero_mask_s)
    res["K_T5_T6_study_rule"] = {"T5_small_white_blobs_on_hero_indigo": ap_.get("T5_small_white_blobs_on_hero_indigo"),
                                 "T6_inner_edge_band_pale_share": ap_.get("T6_inner_edge_band_pale_share"), "T6_band_hero_px": ap_.get("T6_band_hero_px"),
                                 "pass_ja": "T5 は 0、T6 は 0.02 以下で合（targets.json の K-T5・K-T6）"}
    res["P1_P2_bands"] = {k: ap_.get(k) for k in ("r3", "r2")}
    # ---- 面の縁と広げた T5
    ch, tri, _ = M.read_static(g.mesh)
    nh = g.hero_verts
    Hh = M.Hero(ch, tri, nh)
    rule_sr = None
    if g.edge_report and os.path.isfile(g.edge_report):
        er = M.jl(g.edge_report)
        for r in er["results"]:
            if r.get("subrows"):
                rule_sr = r["subrows"]
    res["T5_views"] = {}
    res["T6_surface_edge"] = {}
    views = [(v, g.render + "/views/%s_t120_clawfree.png" % v, g.render + "/views/%s_t120_claws.png" % v) for v in M.VIEWS7]
    for v, pf, pc in views:
        if not os.path.isfile(pf):
            continue
        log("視点", v)
        cm, idb, D, L, th = hero_label(v, ch, tri, nh)
        Rf = np.array(Image.open(pf).convert("RGB"))
        n, lst = blobs(M.color_classes(Rf), L == 1)
        res["T5_views"][v] = {"small_white_blobs_on_hero_indigo": n, "first": lst[:12]}
        if v in ("painting", "seat") and os.path.isfile(pc):
            Rc = np.array(Image.open(pc).convert("RGB"))
            cc = M.color_classes(Rc)
            if v == "painting":
                x0, y0, x1, y1 = M.T6_CROP
                reg = np.zeros(L.shape, bool); reg[y0:y1 + 1, x0:x1 + 1] = True
            else:
                reg = None
                if rule_sr:
                    C, _ = M.sky_contour(D, L)
                    tid = np.clip(idb - 1, 0, len(th) - 1)
                    srp = Hh.sr[th[tid][..., 0]]
                    reg = C & (srp >= rule_sr[0]) & (srp <= rule_sr[1])
            if reg is None:
                continue
            band, C = edge_band(D, L, reg)
            sel = band
            res["T6_surface_edge"][v] = {"edge_px": int(C.sum()), "band_hero_px": int(sel.sum()),
                                         "pale_share": M.rnd(np.isin(cc[sel], (2, 3)).mean()) if sel.any() else None,
                                         "white_px": int((cc[sel] == 3).sum()), "mizuiro_px": int((cc[sel] == 2).sum()),
                                         "region_ja": "利用者の切り出しの中の縁" if v == "painting" else "mat_edge の規則の行（サブ行 %s）の縁" % rule_sr}
    # 波頭の回り台
    res["T5_crest"] = {}
    crest = sorted(glob.glob(g.render + "/crest/t120_az*_clawfree.png"))
    for p in crest:
        Rf = np.array(Image.open(p).convert("RGB"))
        cls = M.color_classes(Rf)
        # 回り台の主役波の印は持たないので、藍の面に囲まれた塊を全部数える（爪なしの描画なので爪は入らない）
        n, lst = blobs(cls, np.ones(cls.shape, bool))
        res["T5_crest"][os.path.basename(p)] = n
    res["seconds"] = round(time.time() - T0, 1)
    M.jdump(g.out, res)
    log("書いた", g.out)
    print({"K_T5": res["K_T5_T6_study_rule"]["T5_small_white_blobs_on_hero_indigo"], "K_T6": res["K_T5_T6_study_rule"]["T6_inner_edge_band_pale_share"],
           "T5_views": {k: v["small_white_blobs_on_hero_indigo"] for k, v in res["T5_views"].items()},
           "T6_surface": {k: v["pale_share"] for k, v in res["T6_surface_edge"].items()}, "T5_crest": res["T5_crest"]})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
