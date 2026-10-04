# -*- coding: utf-8 -*-
"""美術の見本05 の組み立て（Q33）：形 A・形 B（と前の見本04）の Unity の描画で、T5（波の本体の白い粒）と T6（唇の下の内の縁の白・水色）を測る。

  py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render <描画> --mesh <静止のメッシュ .json> --out <測り .json>
      [--hero-verts 314400] [--w4-verts 99789] [--ttnc <回り台の爪なしの描画のフォルダー>]

mat_measure.py（材質の係、変えない）と同じ数え方（blobs・edge_band）を、次のように広げた。
  - 静止のメッシュの三角形を、主役波（頂点 < hero-verts）・wave4（その次の w4-verts 個）・③ の波 layer3（その後ろ、形 A だけ）に分けて印を付ける
    （mat_measure は主役波の後ろを全部「ほかのメッシュ」にするので、layer3 の上の粒を数えない）。
  - T5：7 視点・波頭の回り台 8 方位・回り台 12 方位の爪なしの描画で、波の本体（主役波 ＋ layer3）の藍に囲まれた白・水色の小さな塊（2〜400 画素）の数。
    塊の中心が本体の画素（numpy の z バッファの印、mat_measure と同じく太らせない）にあるものだけを数える。空の色（生成り、r − b > 38）の塊は数えない
    （輪郭線が空を小さく囲む所。白の塗り r − b ≈ 25、水色は r < b に近い。第 1 版は印を太らせて空の切れ端を数えた）。wave4 の上の塊は別に数える（原画の小さな波の白い点 3 つ）。
  - T6（面の縁で決める。材質の係の T6_surface_edge と同じ式）：主役波が空に接する縁の画素から内へ 16 画素の主役波の画素のうち、白・水色の割合。
    原画視点は利用者の切り出し（x 736〜891、y 300〜721）の中の縁、座席・座席から波・波頭の回り台 0°・45° は右の脇の稜の行（c 5.6〜13.8 m）の縁。
    爪ありの描画（利用者が見た画）で測る。
原画の色は面へ写さない。原画のカメラ（とほかの視点のカメラ）は測りにだけ使う。
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
import mat_measure as MM  # noqa: E402

T0 = time.time()
T6_C_RANGE = (5.6, 13.8)       # 右の脇の稜（mat_edge の規則の行 c 5.7〜13.7 m を少し広げた）
T6_VIEWS = {"painting": "views/painting_t120_claws.png", "seat": "views/seat_t120_claws.png",
            "seat_toward_wave": "views/seat_toward_wave_t120_claws.png", "crest0": "crest/t120_az000_claws.png", "crest45": "crest/t120_az045_claws.png"}


def log(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def scene(ch, tri, nh, nw4, with_sea=True):
    pos = ch["position"].astype(np.float64)
    mx = tri.max(1)
    mn = tri.min(1)
    lab = np.full(len(tri), 5, np.int16)
    lab[mx < nh] = 1
    lab[mn >= nh + nw4] = 3
    parts, labs = [pos[tri]], [lab]
    if with_sea:
        st = M.A.sea_tris()
        parts.append(st); labs.append(np.full(len(st), 6, np.int16))
    return np.concatenate(parts), np.concatenate(labs), tri[mx < nh]


SKY_RB = 38


def not_sky(Rf, lst):
    out = []
    for x, y, a in lst:
        r, g, b = [int(v) for v in Rf[y, x]]
        if r - b <= SKY_RB:
            out.append((x, y, a))
    return out


def count_t5(img_path, L):
    Rf = np.array(Image.open(img_path).convert("RGB"))
    cls = M.color_classes(Rf)
    body = np.isin(L, (1, 3))
    w4 = L == 5
    _, lb = MM.blobs(cls, body)
    _, lw = MM.blobs(cls, w4)
    _, la = MM.blobs(cls, np.ones(cls.shape, bool))
    lb, lw, la2 = not_sky(Rf, lb), not_sky(Rf, lw), not_sky(Rf, la)
    return {"body_blobs": len(lb), "body_first": lb[:12], "wave4_blobs": len(lw), "all_blobs_no_mask_not_sky": len(la2), "all_blobs_no_mask": len(la)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hero-verts", type=int, default=314400)
    ap.add_argument("--w4-verts", type=int, default=99789)
    ap.add_argument("--ttnc", default=None)
    ap.add_argument("--parts", default="views,crest,tt,t6", help="測る組：views・crest・tt・t6 を , で区切って")
    g = ap.parse_args()
    parts = set(g.parts.split(","))
    ch, tri, j = M.read_static(g.mesh)
    nh, nw4 = g.hero_verts, g.w4_verts
    H = M.Hero(ch, tri, nh)
    tris, lab, th = scene(ch, tri, nh, nw4)
    tris_ns, lab_ns, _ = scene(ch, tri, nh, nw4, with_sea=False)
    res = {"schema": "GreatWave.AS05.asm5_measure/1", "date": time.strftime("%Y-%m-%d %H:%M"), "render": M.rel(g.render), "mesh": M.rel(g.mesh),
           "mesh_bin_sha256": j.get("sha256"), "tool": M.rel(__file__), "tool_sha256": M.sha(__file__),
           "parts": {"hero": [0, nh], "wave4": [nh, nh + nw4], "layer3": [nh + nw4, len(ch["position"])]}}
    # ---- T5
    t5 = {}
    jobs = [(v, g.render + "/views/%s_t120_clawfree.png" % v, v) for v in M.VIEWS7] if "views" in parts else []
    if "crest" in parts:
        jobs += [("crest%d" % a, g.render + "/crest/t120_az%03d_clawfree.png" % a, "crest%d" % a) for a in range(0, 360, 45)]
    ttd = g.ttnc or g.render
    if "tt" in parts:
        jobs += [("tt%d" % a, ttd + "/tt/t120_az%03d_noclaws.png" % a, "tt%d" % a) for a in range(0, 360, 30)]
    for name, p, cv in jobs:
        if not os.path.isfile(p):
            continue
        tv, lv = (tris_ns, lab_ns) if cv.startswith("crest") else (tris, lab)
        _, idb, D, L = M.raster(cv, tv, lv)
        t5[name] = count_t5(p, L)
        log("T5", name, t5[name]["body_blobs"], t5[name]["wave4_blobs"])
    res["parts_measured"] = sorted(parts)
    res["T5"] = {"per_view": t5, "body_blobs_total": int(sum(v["body_blobs"] for v in t5.values())),
                 "painting_body_blobs": t5.get("painting", {}).get("body_blobs"),
                 "views_with_body_blobs": {k: v["body_blobs"] for k, v in t5.items() if v["body_blobs"]},
                 "rule_ja": "爪なしの描画で、波の本体（主役波 ＋ layer3）の藍に囲まれた白・水色の小さな塊（2〜400 画素）の数。0 で合（要求書 T5）"}
    # ---- T6
    t6 = {}
    for v, rp in T6_VIEWS.items():
        p = g.render + "/" + rp
        if "t6" not in parts or not os.path.isfile(p):
            continue
        tv, lv = (tris_ns, lab_ns) if v.startswith("crest") else (tris, lab)
        _, idb, D, L = M.raster(v, tv, lv)
        cc = M.color_classes(np.array(Image.open(p).convert("RGB")))
        if v == "painting":
            x0, y0, x1, y1 = M.T6_CROP
            reg = np.zeros(L.shape, bool); reg[y0:y1 + 1, x0:x1 + 1] = True
            rj = "利用者の切り出し（x 736〜891、y 300〜721）の中の縁"
        else:
            C0, _ = M.sky_contour(D, L)
            tid = np.clip(idb - 1, 0, len(tris) - 1)
            is_h = (L == 1)
            # 主役波の三角形の番号 → 主役波の三角形の配列の番号（scene は主役波の三角形を先頭の順に並べない：lab の順と同じ並び）
            hid = np.cumsum(lab == 1) - 1
            ht = np.where(is_h, hid[tid], 0)
            srp = H.sr[th[np.clip(ht, 0, len(th) - 1)][..., 0]]
            cpx = H.c_sr[srp]
            reg = C0 & is_h & (cpx >= T6_C_RANGE[0]) & (cpx <= T6_C_RANGE[1])
            rj = "右の脇の稜の行（c %.1f〜%.1f m）の縁" % T6_C_RANGE
        band, C = MM.edge_band(D, L, reg)
        t6[v] = {"edge_px": int(C.sum()), "band_hero_px": int(band.sum()),
                 "pale_share": M.rnd(np.isin(cc[band], (2, 3)).mean()) if band.any() else None,
                 "white_px": int((cc[band] == 3).sum()), "mizuiro_px": int((cc[band] == 2).sum()), "region_ja": rj}
        log("T6", v, t6[v]["pale_share"], t6[v]["band_hero_px"])
    res["T6"] = {"per_view": t6, "painting_pale_share": t6.get("painting", {}).get("pale_share"),
                 "rule_ja": ("主役波が空に接する縁の画素から内へ 16 画素の主役波の画素のうち白・水色の割合（爪ありの描画）。"
                             "原画視点（利用者の切り出し）で 0.02 以下を合とする（targets.json の K-T6 の値。測り方は材質の係の T6_surface_edge）")}
    res["seconds"] = round(time.time() - T0, 1)
    M.jdump(g.out, res)
    log("書いた", g.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
