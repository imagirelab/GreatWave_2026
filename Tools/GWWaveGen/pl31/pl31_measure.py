# -*- coding: utf-8 -*-
"""仕上げ31：Unity の描画（PL31Render）から数える。

  1. 白の出現（white の段。色区 ID を白の時刻あり＝on・なし＝off（終態の白の範囲）で同じ形に描いたもの）：
     - 102 の内側：on が白で off が白でない画素（終態の白の範囲の外の白）。0 が目安
     - 176：off が藍中・藍濃の画素で on が違う色（白でない色区が塗り替わる）。0 が目安
     - 画面の白の割合：on の白 ÷ off の白（時刻ごと）。前（仕上げ30）と後（仕上げ31）
  2. 飛沫の原画視点 t*（full の painting_t120_off（飛沫あり）と painting_t120_nospray（飛沫なし）の差）：
     - 飛沫の画素・塊の数、原画の白い点（pl31_spray_dots.json・設計31 の点）の円の外にある塊（原画にない白い点）
     - 151 の描画の読み：原画の点の中心の画素の色（描画）と原画の点の中心の Lab の CIEDE2000
     - 212（空の上の方、行 0〜379）で飛沫が変える画素
使い方：py -3.10 -B Tools/GWWaveGen/pl31/pl31_measure.py --before Unity/Build/Polish/31/r_before --after Unity/Build/Polish/31/r_after --out Unity/Build/Polish/31/measure
"""
import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pl31_spray import ciede2000  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
IDC = {"white": (255, 0, 0), "mizuiro": (0, 255, 0), "ai_mid": (0, 0, 255), "ai_dark": (255, 255, 0)}


def classes(img):
    rgb = img[..., ::-1].astype(np.int16)
    out = np.full(img.shape[:2], -1, np.int8)
    for k, (name, c) in enumerate(IDC.items()):
        out[(np.abs(rgb - np.array(c)).sum(-1) < 30)] = k
    return out


def white_stage(root):
    res = {}
    for p in sorted(glob.glob(os.path.join(root, "white", "*_on.png"))):
        stem = os.path.basename(p)[:-7]
        q = p[:-7] + "_off.png"
        if not os.path.exists(q):
            continue
        on, off = classes(cv2.imread(p)), classes(cv2.imread(q))
        w_on = on == 0; w_off = off == 0
        outside = int((w_on & ~w_off).sum())
        nonwhite = (off == 2) | (off == 3)
        changed = int((nonwhite & (on != off)).sum())
        res[stem] = dict(white_on=int(w_on.sum()), white_off=int(w_off.sum()), frac=float(w_on.sum() / max(w_off.sum(), 1)),
                         outside_final_white=outside, nonwhite_changed=changed, nonwhite_to_white=int((nonwhite & w_on).sum()))
    return res


def lab_of(bgr):
    v = np.asarray(bgr, np.float32).reshape(-1, 1, 3) / 255.0
    return cv2.cvtColor(v, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64)


def spray_stage(root, dots):
    a = cv2.imread(os.path.join(root, "full", "painting_t120_off.png"))
    b = cv2.imread(os.path.join(root, "full", "painting_t120_nospray.png"))
    if a is None or b is None:
        return None
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).sum(-1) > 12
    n, lab, st, cen = cv2.connectedComponentsWithStats(diff.astype(np.uint8), 8)
    comps = []
    D = np.array([[d["x_d"], d["y_d"], 0.5 * d["diam_display_px"]] for d in dots]) if dots else np.zeros((0, 3))
    outside = 0; outside_px = 0
    for i in range(1, n):
        cx, cy = cen[i]
        ar = int(st[i, 4])
        if len(D):
            dd = np.hypot(D[:, 0] - cx, D[:, 1] - cy) - D[:, 2]
            near = float(dd.min())
        else:
            near = 1e9
        o = near > 3.0
        outside += int(o); outside_px += ar if o else 0
        comps.append(dict(x=float(cx), y=float(cy), px=ar, dist_to_dot_px=near, outside=bool(o)))
    # 151 の描画の読み：原画の点の中心の 3×3 の描画の色
    de = []
    if len(D):
        lab_p = np.array([d["lab"] for d in dots])
        cols = []
        for d in dots:
            x, y = int(round(d["x_d"])), int(round(d["y_d"]))
            cols.append(a[max(0, y - 1):y + 2, max(0, x - 1):x + 2].reshape(-1, 3).mean(0))
        lab_r = lab_of(np.array(cols))
        de = ciede2000(lab_p, lab_r)
    top = diff[:380].sum()
    return dict(spray_px=int(diff.sum()), components=int(n - 1), components_outside_dots=outside, px_outside_dots=int(outside_px),
                sky_top_rows0_379_px=int(top),
                de00_render_at_dots=(dict(n=int(len(de)), median=float(np.median(de)), p90=float(np.percentile(de, 90)), max=float(np.max(de)),
                                          over5=int((np.asarray(de) > 5).sum())) if len(de) else None),
                worst_components=sorted([c for c in comps if c["outside"]], key=lambda c: -c["px"])[:20])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dots_after = json.load(open(REPO + "/Unity/Build/Polish/31/spray/pl31_spray_dots.json", encoding="utf-8"))["dots"]
    dots_before = json.load(open(REPO + "/Unity/Build/Design/31/spray/ds31_spray_dots.json", encoding="utf-8"))["dots"]
    out = dict(schema="GreatWave.Polish31.measure/1",
               white=dict(before=white_stage(a.before), after=white_stage(a.after)),
               spray=dict(before=spray_stage(a.before, dots_before), after=spray_stage(a.after, dots_after),
                          after_vs_all_accepted_dots_ja="後の原画の点は目の照合で採った 210 個（区域 186・右上の空 15・船の近く 9）、前は設計31 の 186 個"))
    for k in ("before", "after"):
        w = out["white"][k]
        out["white"][k + "_summary"] = dict(outside_final_white_max=max((v["outside_final_white"] for v in w.values()), default=None),
                                            nonwhite_changed_max=max((v["nonwhite_changed"] for v in w.values()), default=None),
                                            nonwhite_to_white_max=max((v["nonwhite_to_white"] for v in w.values()), default=None))
    json.dump(out, open(os.path.join(a.out, "pl31_measure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k in ("before", "after"):
        print(k, out["white"][k + "_summary"])
        s = out["spray"][k]
        if s:
            print(k, {kk: v for kk, v in s.items() if kk != "worst_components"})
    print("frac painting after", [(kk, round(v["frac"], 3)) for kk, v in out["white"]["after"].items() if kk.startswith("painting")])
    print("frac painting before", [(kk, round(v["frac"], 3)) for kk, v in out["white"]["before"].items() if kk.startswith("painting")])


if __name__ == "__main__":
    main()
