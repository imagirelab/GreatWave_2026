# -*- coding: utf-8 -*-
"""Details for C2: where the (c) exceedances before contact are; lip reach/thickness with and without 0.25 m resampling of the face."""
import json, numpy as np
from scipy import ndimage
import q_lib as Q
OFF = Q.still_offset_fine(); H = 0.125
cm = json.load(open(Q.DATA + "/coarse/manifest.json", encoding="utf8"))
crest = {r["frame"]: r["crest_x"] for r in cm["frames"]}
out = {}
for f in (3726, 3740, 3743, 3754):
    phi, xs, ys = Q.load_phi(f)
    m = (xs >= crest[f] - 20) & (xs <= crest[f] + 20)
    Fw = phi[:, m] < 0
    X = np.broadcast_to(xs[m][None, :], Fw.shape); Yh = np.broadcast_to((ys - OFF)[:, None], Fw.shape)
    S, sx, sy = Q.load_sec(f); eta, xh = Q.load_hf(f)
    Ya = Yh + Q.OFF_R3
    Sw = Q.bilinear(S, sx, sy, X.ravel(), Ya.ravel()).reshape(X.shape) < 0
    def drop(M):
        lab, n = ndimage.label(M); keep = set(np.unique(lab[0])) - {0}
        sz = ndimage.sum(M, lab, np.arange(1, n + 1)) * H * H
        d = [i + 1 for i in range(n) if (i + 1) not in keep and sz[i] < 0.25]
        return M & ~np.isin(lab, d) if d else M
    Fw = drop(Fw); Sw = drop(Sw)
    dS = ndimage.distance_transform_edt(~Sw) * H
    dd = np.where(Fw, dS, 0)
    j, i = np.unravel_index(np.argmax(dd), dd.shape)
    # is that fine-water pixel part of a separate (closed) fine blob or of the main body?
    lab, n = ndimage.label(Fw)
    main = lab[0, :].max()
    out[f] = dict(max=float(dd.max()), x=float(X[j, i]), y=float(Yh[j, i]), crest_x=crest[f], dx_from_crest=float(X[j, i] - crest[f]),
                  in_bottom_connected_body=bool(lab[j, i] in set(np.unique(lab[0])) - {0}), blob_area_m2=float((lab == lab[j, i]).sum() * H * H))
    print(f, out[f])
json.dump(out, open(Q.OUT + "/q_c2_detail.json", "w"), indent=1)
