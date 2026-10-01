# -*- coding: utf-8 -*-
"""描いた粘土の静止画を並べる（行 = 視点、列 = 候補）。py -3.10 rays_sheet.py <render_dir> <out.png> <labels,...> <views,...> [width]
出力は 1920 px 幅に合わせる（証拠の決まり：PNG 1920×1080 は別に rays_fig.py で作る）。"""
import os
import sys

import cv2
import numpy as np


def sheet(rd, out, labels, views, width=1920, header=30, left=200, notes=None):
    cw = (width - left) // len(labels)
    rows = []
    for v in views:
        ims = []
        for lab in labels:
            p = os.path.join(rd, "%s__%s.png" % (lab, v))
            im = cv2.imread(p)
            if im is None:
                im = np.full((360, 640, 3), 80, np.uint8)
            h = int(round(im.shape[0] * cw / im.shape[1]))
            ims.append(cv2.resize(im, (cw, h), interpolation=cv2.INTER_AREA))
        hmax = max(i.shape[0] for i in ims)
        ims = [cv2.copyMakeBorder(i, 0, hmax - i.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for i in ims]
        lab_img = np.full((hmax, left, 3), 255, np.uint8)
        cv2.putText(lab_img, v[:26], (6, hmax // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        rows.append(np.hstack([lab_img] + ims))
    top = np.full((header, rows[0].shape[1], 3), 255, np.uint8)
    for i, lab in enumerate(labels):
        cv2.putText(top, lab, (left + i * cw + 8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1, cv2.LINE_AA)
    img = np.vstack([top] + rows)
    if notes:
        foot = np.full((22 * len(notes) + 8, img.shape[1], 3), 255, np.uint8)
        for k, t in enumerate(notes):
            cv2.putText(foot, t, (8, 20 + 22 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        img = np.vstack([img, foot])
    cv2.imwrite(out, img)
    return img


if __name__ == "__main__":
    rd, out, labs, views = sys.argv[1:5]
    sheet(rd, out, labs.split(","), views.split(","), int(sys.argv[5]) if len(sys.argv) > 5 else 1920)
