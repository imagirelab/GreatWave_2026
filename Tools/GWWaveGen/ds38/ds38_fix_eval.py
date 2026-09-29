# -*- coding: utf-8 -*-
"""設計38 修正の回（進行役の検査の後の 1 回、Q26）：線の連続のコマ（l191）を、納める版の定義と、検査で使われたゆるい定義の両方で数える（numpy/OpenCV）。

入力：<unity>/ds38_render_report.json と <unity>/l191/l191_<組>.bin（DS38Render の出力。Git 対象外）。
数えるもの（組ごと・線の出どころごと）：
  official：ds38_line_eval.py の eval_seq（一瞬だけ出た線・一瞬だけ消えた線（出どころの列・行をそろえる）・跳び）の塊。
  loose_blink：f−1 と f+1 の同じ画素に同じ出どころ（番号だけ。列・行は見ない）の線があり、f ではどの出どころの線も 1 px の内にない画素の、10 px 以上の塊
              （進行役の検査の定義。出どころの番号ごと）。
  loose_flash：f の線で、f−1 と f+1 のどちらの線からも T = 5.5 px より遠い画素の塊。
  appear_vanish：f+1 の線で f の線から T より遠い（出た）／ f の線で f+1 の線から T より遠い（消えた）画素の塊（検査の頭の揺れの定義。頭の揺れの組で使う）。
  ds37_hole：出どころを見ない一瞬だけ消えた線（設計37 の定義。f−1・f+1 の同じ画素に線、f は 1.5 px の内に線がない）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds38/ds38_fix_eval.py --unity <DS38Render の出力> --out <json>
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds38_line_eval as le  # noqa: E402

W, H = le.W, le.H
NAMES = {1: "hero", 2: "near", 3: "far", 4: "claws"}
K3 = np.ones((3, 3), np.uint8)


def ncl(mask, minpx=10):
    if not mask.any():
        return []
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    return [(int(st[k, 4]), int(cen[k, 0]), int(cen[k, 1])) for k in range(1, n) if st[k, 4] >= minpx]


def ids_img(a):
    m = np.zeros(H * W, np.uint8)
    m[a["idx"]] = a["sheet"].astype(np.uint8)
    return m.reshape(H, W)


def loose(frames, T=5.5):
    IM = [ids_img(a) for a in frames]
    DT = [cv2.distanceTransform((im == 0).astype(np.uint8), cv2.DIST_L2, 5) for im in IM]
    out = {"loose_blink": {}, "loose_flash": {}, "appear": {}, "vanish": {}, "ds37_hole": 0, "examples": {}}
    for sid in (1, 2, 4):
        for k in ("loose_blink", "loose_flash", "appear", "vanish"):
            out[k][NAMES[sid]] = 0
    ex = out["examples"]
    n = len(frames)
    for f in range(n):
        anyf = cv2.dilate((IM[f] > 0).astype(np.uint8), K3)
        if 0 < f < n - 1:
            both_any = (IM[f - 1] > 0) & (IM[f + 1] > 0)
            out["ds37_hole"] += len(ncl(both_any & (DT[f] > 1.5)))
            for sid in (1, 2, 4):
                nm = NAMES[sid]
                b = (IM[f - 1] == sid) & (IM[f + 1] == sid) & (anyf == 0)
                c = ncl(b)
                out["loose_blink"][nm] += len(c)
                for x in c[:2]:
                    ex.setdefault("blink_" + nm, [])
                    if len(ex["blink_" + nm]) < 12:
                        ex["blink_" + nm].append((f,) + x)
                fl = (IM[f] == sid) & (DT[f - 1] > T) & (DT[f + 1] > T)
                out["loose_flash"][nm] += len(ncl(fl))
        if f < n - 1:
            for sid in (1, 2, 4):
                nm = NAMES[sid]
                ca = ncl((IM[f + 1] == sid) & (DT[f] > T))
                cv = ncl((IM[f] == sid) & (DT[f + 1] > T))
                out["appear"][nm] += len(ca)
                out["vanish"][nm] += len(cv)
                for tag, cc in (("appear_", ca), ("vanish_", cv)):
                    for x in cc[:2]:
                        ex.setdefault(tag + nm, [])
                        if len(ex[tag + nm]) < 12:
                            ex[tag + nm].append((f,) + x)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unity", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seqs", default="")
    args = ap.parse_args()
    rep = le.load_json(os.path.join(args.unity, "ds38_render_report.json"))
    res = {"unity": args.unity, "candidate": rep.get("candidate"), "seqs": {}}
    for r in rep["seqs"]:
        if args.seqs and r["name"] not in args.seqs.split(","):
            continue
        p = os.path.join(args.unity, "l191", os.path.basename(r["path"]))
        off = le.eval_seq(p, r)
        frames = le.read_frames(p)
        lz = loose(frames)
        byk = np.zeros(5, np.int64)
        for a in frames:
            byk += np.bincount(a["sheet"], minlength=5)[:5]
        d = {"official": {"flash": off["flash_clusters"], "hole": off["hole_clusters"], "jump": off["jump_clusters"],
                          "by_sheet": off["clusters_by_sheet"], "hole_ds37_def": off["hole_ds37_clusters"], "pass": off["pass"]},
             "loose": lz, "line_px_by_sheet_total": byk.tolist(), "frames": len(frames)}
        res["seqs"][r["name"]] = d
        print(r["name"], "official", d["official"]["flash"], d["official"]["hole"], d["official"]["jump"], d["official"]["by_sheet"],
              "| loose_blink", lz["loose_blink"], "appear", lz["appear"], "vanish", lz["vanish"], "ds37", lz["ds37_hole"],
              "| px", byk.tolist(), flush=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
