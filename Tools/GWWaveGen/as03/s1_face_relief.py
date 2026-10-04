# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照モデルの面（唇の下の前の面）に、彫りの溝の凹凸がスキャンに残っているかを数で確かめる。
面の下の帯（海面から 0.2〜0.45 H。上から垂れる指が少ない所）を一辺 0.05 m の格子で詰め、+a の側から見た面の深さ a_front(c, y) を取り、
c の向きに 1.5 m の窓でならした面からのずれ（溝の凹凸）の大きさと、ずれの山の間隔を出す。数だけ（study/s1_face_relief.json）。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_obj as SO  # noqa: E402
from s1_crown import voxelize_sec  # noqa: E402

SEA_Y = 1.1982310754126466
H = 21.33788445650874


def main():
    V, F = SO.load()
    VOX = 0.05
    lo = np.array([-12.0, V[:, 1].min() - VOX, -12.0])
    hi = np.array([3.0, SEA_Y + 0.46 * H, 12.0])
    occ, odd = voxelize_sec(V, F, lo, hi, VOX)
    na, ny, nc = occ.shape
    ys = lo[1] + (np.arange(ny) + 0.5) * VOX
    cs = lo[2] + (np.arange(nc) + 0.5) * VOX
    res = {"H_ref_m": H, "vox_m": VOX, "odd_columns": int(odd)}
    for f in (0.25, 0.3, 0.35, 0.4):
        j = int(np.argmin(np.abs(ys - (SEA_Y + f * H))))
        sl = occ[:, j, :]                    # (na, nc)
        has = sl.any(0)
        afront = np.where(has, lo[0] + (na - 1 - np.argmax(sl[::-1, :], 0) + 0.5) * VOX, np.nan)
        ok = np.isfinite(afront)
        idx = np.nonzero(ok)[0]
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        r = max(runs, key=len)
        c = cs[r]
        a = afront[r]
        win = int(1.5 / VOX)
        ker = np.ones(win) / win
        sm = np.convolve(np.pad(a, win // 2, mode="edge"), ker, mode="valid")[:len(a)]
        d = (a - sm)[win:-win]
        cc = c[win:-win]
        pk = [i for i in range(1, len(d) - 1) if d[i] > d[i - 1] and d[i] >= d[i + 1] and d[i] > 0.03]
        res["band_%.2fH" % f] = {"c_range_m": [float(cc.min()), float(cc.max())], "rms_m": float(np.sqrt(np.mean(d ** 2))),
                                 "rms_over_H": float(np.sqrt(np.mean(d ** 2)) / H),
                                 "p2p_95_m": float(np.percentile(d, 97.5) - np.percentile(d, 2.5)),
                                 "n_peaks_gt_3cm": len(pk), "peak_spacing_m_p50": float(np.median(np.diff(cc[pk]))) if len(pk) > 2 else None}
    json.dump(res, open(SO.STUDY + "/s1_face_relief.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
