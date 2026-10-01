# -*- coding: utf-8 -*-
"""仕上げ28 の回復（rec）の診断：R4・P28R1・P28R2（と候補）の原画視点の z バッファーで、
(1) 段階9 の Unity の t* で船・手前の海（CPU のメッシュ）が見えていた画素のうち、候補の立ち上がった波の面が新しく覆う画素と、
    それを覆う行（c）・列、
(2) 外殻線の出る画素の予測（rec_common.line_pixels、設計38 の線の印）の、R4 に対して新しく出た画素と、その行・列
を数え、図にする。py -3.10 rec_diag.py <out_dir> [label=rows.npz ...]
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rec_common as RC  # noqa: E402


def analyse(label, path, S9, mask, eye, ref=None):
    c, A, Y = RC.load_rows(path)
    z, ids = RC.zbuf(c, A, Y, 1)
    up = RC.upright_tri_mask(Y)
    t = ids - 1
    hero = (t >= 0) & up[np.clip(t, 0, None)]
    lp, cont = RC.line_pixels(c, A, Y, ids, eye, mask)
    prot = S9["boat_left"] | S9["boat_mid"] | S9["boat_fg"] | S9["cpu"]
    newcov = prot & hero
    iv, iu = RC.tri_quad(ids)
    res = {"label": label, "rows": path, "rows_sha256": RC.sha256(path),
           "hero_px": int(hero.sum()),
           "covers_stage9_protected_px": {k: int((S9[k] & hero).sum()) for k in ("boat_left", "boat_mid", "boat_fg", "cpu")},
           "line_px_pred": int(lp.sum())}
    if newcov.any():
        rr = c[iv[newcov]]; cc = iu[newcov]
        res["cover_rows_c"] = [round(float(np.percentile(rr, q)), 2) for q in (1, 10, 50, 90, 99)]
        res["cover_cols"] = [int(np.percentile(cc, q)) for q in (1, 10, 50, 90, 99)]
    out = {"z": z, "ids": ids, "hero": hero, "line": lp, "c": c, "A": A, "Y": Y}
    if ref is not None:
        nl = lp & ~ref["line"]
        res["line_px_new_vs_ref"] = int(nl.sum())
        if nl.any():
            ys, xs = np.nonzero(nl)
            res["new_line_bbox_xy"] = [int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())]
            rr = c[iv[nl]]; cc = iu[nl]
            # 塊ごと（8 連結）
            import cv2
            n, lab, st, _ = cv2.connectedComponentsWithStats(nl.astype(np.uint8), connectivity=8)
            blobs = []
            for k in np.argsort(-st[1:, cv2.CC_STAT_AREA])[:12] + 1:
                m = lab == k
                if st[k, cv2.CC_STAT_AREA] < 25:
                    continue
                blobs.append({"px": int(st[k, cv2.CC_STAT_AREA]), "x": [int(st[k, 0]), int(st[k, 0] + st[k, 2])], "y": [int(st[k, 1]), int(st[k, 1] + st[k, 3])],
                              "rows_c": [round(float(c[iv[m]].min()), 1), round(float(c[iv[m]].max()), 1)], "cols": [int(iu[m].min()), int(iu[m].max())]})
            res["new_line_blobs"] = blobs
        gone = ref["hero"] & ~hero; grown = hero & ~ref["hero"]
        res["hero_grown_px_vs_ref"] = int(grown.sum()); res["hero_lost_px_vs_ref"] = int(gone.sum())
        if grown.any():
            g2 = grown & (np.arange(grown.shape[0])[:, None] > 450)
            if g2.any():
                ys, xs = np.nonzero(g2)
                res["hero_grown_lower_bbox_xy"] = [int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()), int(g2.sum())]
    return res, out


def fig(outs, S9, png):
    import cv2
    ims = []
    for lab, o in outs:
        im = np.full((1080, 1920, 3), 235, np.uint8)
        im[S9["sky"]] = (250, 235, 205)
        im[S9["cpu"]] = (90, 90, 90)
        im[S9["boat_left"] | S9["boat_mid"] | S9["boat_fg"]] = (120, 180, 230)
        im[o["hero"]] = (160, 110, 40)
        im[o["line"]] = (30, 30, 200)
        cv2.putText(im, lab, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 3)
        ims.append(cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA))
    while len(ims) % 2:
        ims.append(np.full_like(ims[0], 255))
    rows = [np.hstack(ims[i:i + 2]) for i in range(0, len(ims), 2)]
    cv2.imwrite(png, np.vstack(rows))


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    items = [("R4", RC.ROWS["R4"]), ("P28R1", RC.ROWS["P28R1"]), ("P28R2", RC.ROWS["P28R2"])]
    for a in sys.argv[2:]:
        k, v = a.split("=", 1)
        items.append((k, v))
    S9 = RC.stage9_classes(1)
    mask = RC.load_linemask()
    eye = RC.cam_pos()
    ref = None
    res_all = []; outs = []
    for lab, p in items:
        r, o = analyse(lab, p, S9, mask, eye, ref)
        if ref is None:
            ref = o
        res_all.append(r); outs.append((lab, o))
        print(json.dumps(r, ensure_ascii=False))
    RC.jdump({"note_ja": "原画視点の z バッファー（1920×1080）。protected＝段階9 の Unity の t* の ID 画像で船・CPU のメッシュ（手前の海）が見える画素。"
                         "line_px_pred＝外殻線の出る画素の予測（設計38 の線の印）。ref＝最初の行（R4）。", "items": res_all}, os.path.join(out, "rec_diag.json"))
    fig(outs, S9, os.path.join(out, "rec_diag.png"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
