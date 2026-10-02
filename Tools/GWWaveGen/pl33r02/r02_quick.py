# -*- coding: utf-8 -*-
"""仕上げ33修正02：試しの版ごとの速い数（記録の補助。本番の数は r02_run_eval.sh の各道具）。
  - r01_quick.py の原画視点 t* の律動（爪の領域の水色・暗い線）と一覧との重なり
  - 唇の輪郭の白い欠け（pl33f_measure.py と同じ式：t* の主役波の z バッファの縁 5×5 の帯で、爪なしでは暗く（< 110）作品のままでは明るい（> 170）画素）
  - 座席の揃い（r02_seatfan.py）
使い方：py -3.10 -B Tools/GWWaveGen/pl33r02/r02_quick.py --run <描画> --claws <爪の並び> [--out <json>]
"""
import argparse
import json
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r01")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r02")
import r01_quick as Q  # noqa: E402
import r02_seatfan as SF  # noqa: E402
from pl33_common import TStarDepth  # noqa: E402


def notch(run):
    X0 = SF.SB.U.K.Pkg(SF.SB.HERO).world(0.0)
    dep = TStarDepth(X0)
    hm = dep.mask.astype(np.uint8)
    edge = (cv2.dilate(hm, np.ones((5, 5), np.uint8)) - cv2.erode(hm, np.ones((5, 5), np.uint8))).astype(bool)
    im = cv2.imread(run + "/views/painting_t120_asis.png")
    fr = cv2.imread(run + "/views/painting_t120_clawfree.png")
    g = lambda x: cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)
    nm = edge & (g(fr) < 110) & (g(im) > 170)
    n, cc, st, _ = cv2.connectedComponentsWithStats(nm.astype(np.uint8), connectivity=8)
    return dict(notch_px=int(nm.sum()), notch_components_ge3=int((st[1:, 4] >= 3).sum()), outline_px=int((edge & (g(fr) < 110)).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--claws", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    inv = json.load(open(Q.OV.INV, encoding="utf-8"))
    spec = json.load(open(Q.OV.U.TRUTH, encoding="utf-8"))
    cam = Q.OV.U.CamWH(spec, 1920, 1080)
    ov = Q.OV.measure(a.run, a.claws, inv, cam)[0]
    rh = Q.rhythm(a.run)
    sf = SF.analyse(a.claws, a.run)
    r = dict(rhythm=dict(claw_zone=rh["claw_zone"], bregion=rh["bregion"]),
             overlay={k: round(v, 4) for k, v in ov.items() if k in ("list_recall", "precision_4px", "claw_pixels")},
             notch=notch(a.run), seat={k: v for k, v in sf.items() if k != "fingers"})
    print("R02_QUICK", json.dumps(r, ensure_ascii=False))
    if a.out:
        json.dump(r, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
