# -*- coding: utf-8 -*-
"""contact sheet of the 9 standard views: K* | candidate [| extra] (work image)."""
import sys, os, cv2, numpy as np
from candB_common import *
tags = sys.argv[1].split(","); out = sys.argv[2]
views = ["v1_painting", "v2_seat", "v3_side_along_crest_cam_side", "v4_true_side_perp_crest_front", "v5_back_three_quarter",
         "v6_top_down", "v7_user6_az330_el10", "v8_user7_az290_el5", "v9_user8_az030_el25"]
sel = sys.argv[3].split(",") if len(sys.argv) > 3 else views
rows = []
for v in sel:
    ims = []
    for t in tags:
        if t == "kstar":
            f = os.path.join(RUBRIC, "renders", "kstar__%s.png" % v)
        elif t == "ref":
            f = os.path.join(RUBRIC, "renders", "ref__%s.png" % v)
        else:
            f = os.path.join(WORK, "renders_%s" % t, "candB__%s.png" % v)
        im = cv2.imread(f)
        if im is None:
            im = np.zeros((720, 1280, 3), np.uint8)
        im = cv2.resize(im, (640, int(640 * im.shape[0] / im.shape[1])))
        cv2.putText(im, "%s %s" % (t, v[:14]), (8, 22), 0, 0.6, (0, 0, 0), 2)
        ims.append(im)
    h = max(i.shape[0] for i in ims)
    ims = [np.vstack([i, np.full((h - i.shape[0], 640, 3), 255, np.uint8)]) for i in ims]
    rows.append(np.hstack(ims))
cv2.imwrite(out, np.vstack(rows))
