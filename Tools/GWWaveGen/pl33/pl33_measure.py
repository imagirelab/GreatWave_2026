# -*- coding: utf-8 -*-
"""仕上げ33：描いた画像（Unity の PC オフスクリーン描画）で、爪がどの視点から読めるかと、原画視点の爪の律動を数える（numpy・OpenCV。記録）。

前＝仕上げ32 修正の回 1（Build/Polish/32/fix01/r_fix01）、後＝仕上げ33（Build/Polish/33/r_after）。同じ視点・同じ時刻（t 6・9・10.5・12 s）。
1. 視点ごとの爪の画素：作品のままの画像と爪なしの画像で色が 20 より違う画素（爪・膜・縁の線が描いた画素）と、そのうちの暗い線
   （明るさ < 110 で、爪なしの画像では明るさ > 150 の所＝白・空の上に出た墨版の線）と、藍の上の爪（pl32f_measure.claws_over_indigo）。
2. 原画視点 t* の爪の帯の律動：一覧の爪の領域（region_polygon_ref の和を 6 px 太らせた所。原画の爪の範囲）の中の
   水色の版の割合（白い地の上）と、白い地の上の暗い線の成分（pl32f_measure.dark_lines）。原画・前・後。b区域の帯（仕上げ32 の読み）も同じに。
3. 原画視点 t 10.5 s・t* の b区域の閉じた輪（pl32f_measure.closed_rings）。
出力：Unity/Build/Polish/33/measure/pl33_measure.json
"""
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl32")
import pl32f_measure as M  # noqa: E402

RUNS = dict(before=REPO + "/Unity/Build/Polish/32/fix01/r_fix01", after=REPO + "/Unity/Build/Polish/33/r_after")
INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"
OUT = REPO + "/Unity/Build/Polish/33/measure"
VIEWS = M.VIEWS
TS = M.TS


def claw_zone():
    inv = json.load(open(INV, encoding="utf-8"))
    Z = np.zeros((1080, 1920), np.uint8)
    for c in inv["claws"]:
        if c.get("zone") != "main" or not c.get("region_polygon_ref"):
            continue
        cv2.fillPoly(Z, [np.round(M.r2d(np.asarray(c["region_polygon_ref"]))).astype(np.int32)], 1)
    Z = cv2.dilate(Z, np.ones((13, 13), np.uint8))
    return Z.astype(bool)


def claw_pixels(a, f):
    diff = np.abs(a.astype(int) - f.astype(int)).sum(2) > 20
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gf = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    line = diff & (ga < 110) & (gf > 150)
    return dict(px=int(diff.sum()), line_on_light_px=int(line.sum()))


def main():
    os.makedirs(OUT, exist_ok=True)
    out = dict(rule_ja=__doc__, runs={k: os.path.relpath(v, REPO).replace("\\", "/") for k, v in RUNS.items()})
    views = {}
    for k, d in RUNS.items():
        views[k] = {}
        for v in VIEWS:
            for t in TS:
                a = cv2.imread(d + "/views/%s_%s_asis.png" % (v, t))
                f = cv2.imread(d + "/views/%s_%s_clawfree.png" % (v, t))
                if a is None or f is None:
                    continue
                e = claw_pixels(a, f)
                e["over_indigo"] = M.claws_over_indigo(a, f)
                views[k]["%s_%s" % (v, t)] = e
    out["views"] = views
    summ = {}
    for v in VIEWS:
        for t in TS:
            key = "%s_%s" % (v, t)
            if key in views["before"] and key in views["after"]:
                b, a = views["before"][key], views["after"][key]
                summ[key] = {"claw_px": [b["px"], a["px"]], "line_px": [b["line_on_light_px"], a["line_on_light_px"]],
                             "over_indigo_px": [b["over_indigo"]["px"], a["over_indigo"]["px"]]}
    out["views_summary_before_after"] = summ
    Zc = claw_zone()
    Zb = M.zone_mask()
    P = M.paint_disp()
    rhythm = {"claw_zone_px": int(Zc.sum()), "painting": dict(mizuiro=M.mizuiro_frac(P, Zc), **M.dark_lines(P, Zc)),
              "bregion_painting": dict(mizuiro=M.mizuiro_frac(P, Zb), **M.dark_lines(P, Zb))}
    for k, d in RUNS.items():
        a = cv2.imread(d + "/views/painting_t120_asis.png")
        rhythm[k] = dict(mizuiro=M.mizuiro_frac(a, Zc), **M.dark_lines(a, Zc))
        rhythm["bregion_" + k] = dict(mizuiro=M.mizuiro_frac(a, Zb), **M.dark_lines(a, Zb))
    out["painting_tstar_rhythm"] = rhythm
    rings = {}
    for k, d in RUNS.items():
        for t in ("t105", "t120"):
            a = cv2.imread(d + "/views/painting_%s_asis.png" % t)
            f = cv2.imread(d + "/views/painting_%s_clawfree.png" % t)
            rings["%s_%s" % (k, t)] = M.closed_rings(a, f, Zb)
    out["bregion_closed_rings"] = rings
    json.dump(out, open(OUT + "/pl33_measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"rhythm": rhythm, "rings": rings}, ensure_ascii=False))
    for key, e in summ.items():
        print(key, e)


if __name__ == "__main__":
    main()
