# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）の 4：描画から数える（numpy・OpenCV。仕上げ33 の pl33f_measure.py の式を使う）。

  - 視点ごとの爪の画素（作品のまま − 爪なし。差の最大 > 12）、藍の上の爪、明るい地に触れない浮いた成分（pl33f_measure.view_stats）
  - 原画視点 t* の爪の領域（一覧の main の領域を 13 px 広げた所）と b区域の、白い地の上の水色の版の割合・暗い線の画素と成分（pl32f_measure）
  - 原画視点の閉じた輪（pl33f_measure.rings）
  - 爪の一覧との重ね：一覧の main の爪 213 本の中心線（表示の座標）の画素のうち、描画の爪の画素（3 px の許し）に載る割合（中心線の再現）と、
    描画の爪の画素のうち、一覧の爪の領域（13 px 広げた所）の中にある割合（一覧の外へ出ない度合い）。前（仕上げ33）と後で同じ式
  - 上の縁の縁取り（爪なしの描画の白い塊の上の縁の列のうち、15 px 以内に爪の画素がある割合。pl33f2_ridge_img と同じ考え方）
出力：<out>/pl33r01h_measure.json
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl32")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl32f_measure as M  # noqa: E402
import pl33f_measure as F  # noqa: E402

VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"


def centerline_mask():
    inv = json.load(open(INV, encoding="utf-8"))
    Z = np.zeros((1080, 1920), np.uint8)
    for c in inv["claws"]:
        if c.get("zone") != "main" or not c.get("centerline_ref"):
            continue
        p = np.round(M.r2d(np.asarray(c["centerline_ref"], np.float64))).astype(np.int32)
        cv2.polylines(Z, [p], False, 1, 1)
    return Z.astype(bool)


def ridge_fraction(im, fr):
    """爪なしの描画の白い塊（明るさ > 200 で、藍・空でない）の上の縁の列のうち、15 px 以内に爪の画素がある割合。"""
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    white = (g > 200) & (hsv[:, :, 1] < 40)
    white = cv2.morphologyEx(white.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
    m = F.claw_mask(im, fr)
    md = cv2.dilate(m.astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
    cols = np.where(white.any(0))[0]
    if len(cols) == 0:
        return None
    top = white.argmax(0)
    hit = [md[top[x], x] for x in cols]
    return round(float(np.mean(hit)), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="name=dir（描画のフォルダー）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--times", default="t090,t105,t120")
    a = ap.parse_args()
    runs = dict(x.split("=", 1) for x in a.runs)
    ts = a.times.split(",")
    out = {"rule_ja": __doc__, "runs": runs}
    views = {}
    for v in VIEWS:
        for t in ts:
            e = {}
            for k, d in runs.items():
                im = cv2.imread(d + "/views/%s_%s_asis.png" % (v, t)); fr = cv2.imread(d + "/views/%s_%s_clawfree.png" % (v, t))
                if im is None or fr is None:
                    continue
                e[k] = F.view_stats(im, fr)
                if v in ("side_left", "side_right", "back65", "top", "seat", "seat_toward_wave"):
                    e[k]["ridge_ringed_fraction"] = ridge_fraction(im, fr)
            views["%s_%s" % (v, t)] = e
    out["views"] = views
    Zb = M.zone_mask()
    Zc = F.claw_zone()
    P = M.paint_disp()
    CL = centerline_mask()
    rh = {"claw_zone_painting": dict(mizuiro=M.mizuiro_frac(P, Zc), **M.dark_lines(P, Zc)),
          "bregion_painting": dict(mizuiro=M.mizuiro_frac(P, Zb), **M.dark_lines(P, Zb))}
    ov = {}
    rg = {}
    for k, d in runs.items():
        im = cv2.imread(d + "/views/painting_t120_asis.png"); fr = cv2.imread(d + "/views/painting_t120_clawfree.png")
        if im is None:
            continue
        rh["claw_zone_" + k] = dict(mizuiro=M.mizuiro_frac(im, Zc), **M.dark_lines(im, Zc))
        rh["bregion_" + k] = dict(mizuiro=M.mizuiro_frac(im, Zb), **M.dark_lines(im, Zb))
        m = F.claw_mask(im, fr)
        md = cv2.dilate(m.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        ov[k] = dict(centerline_px=int(CL.sum()), centerline_on_claw_frac_tol3=round(float((CL & md).sum() / max(1, CL.sum())), 4),
                     claw_px=int(m.sum()), claw_px_in_list_regions_frac=round(float((m & Zc).sum() / max(1, m.sum())), 4))
        for t in ts:
            im2 = cv2.imread(d + "/views/painting_%s_asis.png" % t); fr2 = cv2.imread(d + "/views/painting_%s_clawfree.png" % t)
            if im2 is not None:
                rg["%s_%s" % (k, t)] = F.rings(im2, fr2, np.ones_like(Zb))
    out["painting_tstar_rhythm"] = rh
    out["overlay_vs_claw_list"] = ov
    out["closed_rings_painting"] = rg
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    s = {k: v for k, v in out.items() if k != "rule_ja"}
    print(json.dumps(s, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
