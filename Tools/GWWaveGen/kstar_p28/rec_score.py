# -*- coding: utf-8 -*-
"""仕上げ28 の回復：候補の行（rows.npz）を、原画視点の 2 つの後退で採点する（numpy。Unity の描画の前の選別）。
 (1) 新しい線：rec_common.shell_lines（設計38 の反転シェルと線の印。Unity の t* の線の ID 画像で、段階9 に対して新しく出た線の塊の
     画素数が一致することを確かめた。rec_linecheck.json）の、R4（段階9）に対して新しく出た線の画素と塊（行 c・列の範囲つき）。
 (2) 船と手前の海を覆う：段階9 の Unity の t* の ID 画像で船（boat_left・boat_mid・boat_fg）と CPU のメッシュ（手前の海）が見える画素で、
     候補の主役波の面の奥行きが R4 より 0.05 m 以上手前に来た画素（R4 はそこで船の後ろにある。手前に来るほど船を隠しうる）の数と、
     そのうち R4 の奥行きより 1 m 以上手前の画素の数。R4 が覆っていない画素を候補が新しく覆う数も数える。
py -3.10 rec_score.py <out_json> label=rows.npz [label=rows.npz ...]（1 行目の前に R4 を自動で入れる）
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rec_common as RC  # noqa: E402

_CACHE = {}


def ref_state(ss):
    if ss not in _CACHE:
        mask = RC.load_linemask()
        c, A, Y = RC.load_rows(RC.ROWS["R4"])
        ln, zs, zl = RC.shell_lines(c, A, Y, mask, ss=ss)
        S9 = RC.stage9_classes(ss)
        _CACHE[ss] = (mask, ln, zs, S9)
    return _CACHE[ss]


def score(path, ss=2, label=None):
    import cv2
    mask, ln0, zs0, S9 = ref_state(ss)
    c, A, Y = RC.load_rows(path)
    ln, zs, zl, src = RC.shell_lines(c, A, Y, mask, ss=ss, want_src=True)
    k = np.ones((2 * ss + 1, 2 * ss + 1), np.uint8)
    new = ln & ~cv2.dilate(ln0.astype(np.uint8), k).astype(bool)
    prot = S9["boat_left"] | S9["boat_mid"] | S9["boat_fg"] | S9["cpu"]
    fin0 = np.isfinite(zs0); fin = np.isfinite(zs)
    closer = prot & fin & fin0 & (zs < zs0 - 0.05)
    closer1 = prot & fin & fin0 & (zs < zs0 - 1.0)
    newcov = prot & fin & ~fin0
    # 線の塊と、その出どころの行・列（線の画素を描いたシェルの三角形の四角形）
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(new.astype(np.uint8), np.ones((9, 9), np.uint8)), connectivity=8)
    bl = []
    for kk in range(1, n):
        m = (lab == kk) & new
        if m.sum() < 30 * ss:
            continue
        ys, xs = np.nonzero(m)
        q = src[m]; q = q[q >= 0]
        rr = q // (RC.NU - 1); cc = q % (RC.NU - 1)
        bl.append({"px": int(m.sum()), "x": [int(xs.min() / ss), int(xs.max() / ss)], "y": [int(ys.min() / ss), int(ys.max() / ss)],
                   "rows": [int(rr.min()), int(rr.max())], "rows_c": [round(float(c[rr.min()]), 1), round(float(c[rr.max()]), 1)],
                   "cols": [int(cc.min()), int(cc.max())], "cols_p10_p90": [int(np.percentile(cc, 10)), int(np.percentile(cc, 90))]})
    bl.sort(key=lambda b: -b["px"])
    res = {"label": label, "rows": path, "rows_sha256": RC.sha256(path), "ss": ss,
           "new_line_px": int(new.sum()), "new_line_px_upper_y_lt_900": int(new[: int(900 * ss)].sum()),
           "new_line_blobs": bl[:16],
           "protected_closer_px_0p05m": int(closer.sum()), "protected_closer_px_1m": int(closer1.sum()),
           "protected_newcover_px": int(newcov.sum()),
           "boat_left_closer_px_0p05m": int((closer & S9["boat_left"]).sum())}
    return res, {"new": new, "closer": closer, "ln": ln, "src": src}


def main():
    outp = sys.argv[1]
    items = [("R4", RC.ROWS["R4"])] + [tuple(a.split("=", 1)) for a in sys.argv[2:]]
    allr = []
    for lab, p in items:
        r, _ = score(p, 2, lab)
        allr.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "new_line_blobs"}, ensure_ascii=False))
        for b in r["new_line_blobs"][:10]:
            print("   ", b)
    RC.jdump({"note_ja": "ss=2（3840×2160 の読み。px は ss=2 の画素）。R4 に対する新しい線と、段階9 の船・手前の海の画素で主役波が手前へ来た画素。",
              "items": allr}, outp)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
