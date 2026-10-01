# -*- coding: utf-8 -*-
"""仕上げ28 の回復：numpy の外殻線の予測（rec_common.shell_lines）を、Unity の t* の線の ID 画像（t28_white の af28r01_line_ids.png、
3840×2160、マゼンタ＝線）と比べて確かめる。段階9（R4）と仕上げ28（P28R2）の両方で、予測と Unity の線の画素の一致と、
P28R2 で新しく出た線の塊（段階9 に対して）を数える。py -3.10 rec_linecheck.py <out_dir>
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rec_common as RC  # noqa: E402


def unity_lines(scene):
    from PIL import Image
    p = os.path.join(RC.P28, "unity", scene, "t28_white", "t28", "render", "af28r01_line_ids.png")
    im = np.array(Image.open(p).convert("RGB")).astype(int)
    return (im[..., 0] > 200) & (im[..., 1] < 60) & (im[..., 2] > 200), p


def blobs(m, min_px=40):
    import cv2
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8)), connectivity=8)
    out = []
    for k in range(1, n):
        mm = (lab == k) & m
        if mm.sum() < min_px:
            continue
        ys, xs = np.nonzero(mm)
        out.append([int(mm.sum()), int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())])
    return sorted(out, key=lambda b: -b[0])


def main():
    import cv2
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    mask = RC.load_linemask()
    res = {}
    pred = {}; uni = {}
    for lab, rows, scene in (("R4", RC.ROWS["R4"], "scene_stage9"), ("P28R2", RC.ROWS["P28R2"], "scene_p28")):
        c, A, Y = RC.load_rows(rows)
        ln, zs, zl = RC.shell_lines(c, A, Y, mask, ss=2)
        u, up = unity_lines(scene)
        pred[lab] = ln; uni[lab] = u
        k = np.ones((5, 5), np.uint8)
        ud = cv2.dilate(u.astype(np.uint8), k).astype(bool); pd = cv2.dilate(ln.astype(np.uint8), k).astype(bool)
        res[lab] = {"pred_px": int(ln.sum()), "unity_px": int(u.sum()),
                    "pred_within2px_of_unity": round(float((ln & ud).sum() / max(ln.sum(), 1)), 3),
                    "unity_within2px_of_pred": round(float((u & pd).sum() / max(u.sum(), 1)), 3)}
    k = np.ones((5, 5), np.uint8)
    for kind, d in (("pred", pred), ("unity", uni)):
        new = d["P28R2"] & ~cv2.dilate(d["R4"].astype(np.uint8), k).astype(bool)
        res["new_" + kind] = {"px": int(new.sum()), "blobs_px_x0_x1_y0_y1_at_2x": blobs(new)[:14]}
    RC.jdump(res, os.path.join(out, "rec_linecheck.json"))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    # 図：左上 Unity 段階9、右上 予測 R4、左下 Unity P28R2、右下 予測 P28R2（線を黒、新しい線を赤）
    ims = []
    for lab in ("R4", "P28R2"):
        for d in (uni, pred):
            im = np.full(d[lab].shape + (3,), 255, np.uint8)
            im[d[lab]] = (0, 0, 0)
            if lab == "P28R2":
                new = d["P28R2"] & ~cv2.dilate(d["R4"].astype(np.uint8), k).astype(bool)
                im[cv2.dilate(new.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)] = (0, 0, 230)
            ims.append(cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA))
    top = np.hstack(ims[:2]); bot = np.hstack(ims[2:])
    cv2.imwrite(os.path.join(out, "rec_linecheck.png"), np.vstack([top, bot]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
