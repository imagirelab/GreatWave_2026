# -*- coding: utf-8 -*-
"""仕上げ28 の回復：残る新しい線が、設計38 の線の印の決まり（原画視点で主役波の面の外から 4 px より内側に出た線の頂点を 0 にし、
どの時刻でも輪郭の 4 px 以内に出た頂点は除き、1 格子広げる）で消える種類かを、t* だけで numpy で確かめる（記録のみの見込み。
印のファイルは作らず、Unity の描画にも使わない。印の作り直しは仕上げ38 の最初の作業。計画 §5.1）。
py -3.10 rec_mask_preview.py <out.json> label=rows.npz ...
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rec_common as RC  # noqa: E402
import rec_score as RS  # noqa: E402


def preview(path, ss=2):
    import cv2
    old = RC.load_linemask()
    c, A, Y = RC.load_rows(path)
    ones = np.ones_like(old)
    ln, zs, zl, src = RC.shell_lines(c, A, Y, ones, ss=ss, want_src=True)
    face = np.isfinite(zs)
    din = cv2.distanceTransform(face.astype(np.uint8), cv2.DIST_L2, 5) / ss       # 面の内側の、面の外までの距離（表示 px）
    inside = ln & (din > 4.0)
    near = ln & (din <= 4.0)
    nu, nv = RC.NU, RC.NV

    def verts(m):
        q = src[m]; q = q[q >= 0]
        r = q // (nu - 1); j = q % (nu - 1)
        v = np.zeros((nv, nu), bool)
        for dr in (0, 1):
            for dj in (0, 1):
                v[r + dr, j + dj] = True
        return v
    vin = verts(inside); vnear = verts(near)
    zero = vin & ~vnear
    z2 = zero.copy()
    z2[1:] |= zero[:-1]; z2[:-1] |= zero[1:]; z2[:, 1:] |= zero[:, :-1]; z2[:, :-1] |= zero[:, 1:]
    newmask = np.where(z2, 0.0, old)
    mask0, ln0, zs0, S9 = RS.ref_state(ss)
    ln2, _, _ = RC.shell_lines(c, A, Y, newmask.astype(np.float32), ss=ss)
    k = np.ones((2 * ss + 1, 2 * ss + 1), np.uint8)
    new_old = RS.score(path, ss)[1]["new"]
    new2 = ln2 & ~cv2.dilate(ln0.astype(np.uint8), k).astype(bool)
    return {"rows": path, "rows_sha256": RC.sha256(path), "zero_vertices_added": int((z2 & (old >= 0.5)).sum()),
            "new_line_px_with_R4_mask": int(new_old.sum()), "new_line_px_upper_y_lt_900_with_R4_mask": int(new_old[: 900 * ss].sum()),
            "new_line_px_with_preview_mask": int(new2.sum()), "new_line_px_upper_y_lt_900_with_preview_mask": int(new2[: 900 * ss].sum()),
            # 面の外から 4 px より内側（面の中）に残る新しい線と、面の縁から 4 px 以内・面の外（輪郭の線が動いた分）に残る新しい線
            "new_line_px_inside_face_gt4px_with_R4_mask": int((new_old & (din > 4.0)).sum()),
            "new_line_px_inside_face_gt4px_with_preview_mask": int((new2 & (din > 4.0)).sum()),
            "new_line_px_outline_le4px_with_preview_mask": int((new2 & (din <= 4.0)).sum())}


def main():
    outp = sys.argv[1]
    out = {"note_ja": "記録のみの見込み（t* だけ、ss=2 の画素）。設計38 の決まりを t* の 1 時刻で当てた印（元の印の 0 に足す）で、R4（段階9）に対する新しい線が残るか。"
                      "印のファイルは作らない。Unity の描画は元の印（設計38）のまま。", "items": {}}
    for a in sys.argv[2:]:
        k, p = a.split("=", 1)
        out["items"][k] = preview(p)
        print(k, json.dumps(out["items"][k], ensure_ascii=False))
    RC.jdump(out, outp)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
