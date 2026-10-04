# -*- coding: utf-8 -*-
"""美術の見本04 の直しの回 1（fix1）：主役波 K*′ AS04 の行を作り直す（S11 の ②③ の間の湾、ほか）。
py -3.10 -B Tools/GWWaveGen/as04/fx1_build.py <out_prefix> <design.json>

shape_build.py（変えない）の順（op_shorten → op_left → 境の輪を土台へ）に、次を足す。
  shorten_more（list）：op_shorten をもう一度（別の c の窓で）かける。② と ③ の間（c −17〜−15.5 m）の唇を短くし、湾を作る（S11）。
  post_smooth（list）：{"c": [c0, c1], "cols": [j0, j1], "sigma_rows": s} 行の向きに、その窓の中だけ断面の差をならす（目の形の小さな窪みを消す）。
行の c・格子 400 × 240・目印の列・境の輪は変えない。参照モデル・写真は読まない。原画のカメラは測りにだけ使う。
"""
import json
import os
import sys
import time

import numpy as np
from scipy.ndimage import gaussian_filter1d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_build as B  # noqa: E402
import shape_common as S  # noqa: E402
import shape_ops as O  # noqa: E402


def build(design):
    extras = design.get("shorten_more", [])
    orig = O.op_shorten
    info_more = []

    def chained(c, A, Y, p):
        A2, Y2, w, info = orig(c, A, Y, p)
        for q in extras:
            A2, Y2, w2, inf2 = orig(c, A2, Y2, q)
            info_more.append({"window": q.get("c_full"), "rows": len(inf2), "cut_max": max([r["cut"] for r in inf2] or [0])})
        return A2, Y2, w, info

    B.O.op_shorten = chained
    try:
        c, A, Y, log = B.build(design)
    finally:
        B.O.op_shorten = orig
    log["shorten_more"] = info_more
    for ps in design.get("post_smooth", []):
        c0, c1 = ps["c"]; j0, j1 = ps["cols"]
        A0, Y0 = A.copy(), Y.copy()
        As = gaussian_filter1d(A, ps["sigma_rows"], axis=0, mode="nearest")
        Ys = gaussian_filter1d(Y, ps["sigma_rows"], axis=0, mode="nearest")
        wr = S.ss((c - c0) / max(ps.get("blend", 0.6), 1e-6)) * S.ss((c1 - c) / max(ps.get("blend", 0.6), 1e-6))
        jj = np.arange(A.shape[1])
        wc = S.ss((jj - j0) / 4.0) * S.ss((j1 - jj) / 4.0)
        W = wr[:, None] * wc[None, :]
        A = A0 + W * (As - A0); Y = Y0 + W * (Ys - Y0)
    for vf in design.get("valley_fill", []):
        # 頂から唇の前の縁までの断面の谷を埋める（水を張るように、低い方の縁の高さまで）。唇の瘤の手前の谷が原画視点で内の輪郭（設計38 の線の切れ端）を作るため
        c0, c1 = vf["c"]; j1 = vf["col_end"]
        wr = S.ss((c - c0) / max(vf.get("blend", 0.6), 1e-6)) * S.ss((c1 - c) / max(vf.get("blend", 0.6), 1e-6))
        for i in np.nonzero(wr > 1e-3)[0]:
            jc = int(np.argmax(Y[i, 18:201])) + 18
            y = Y[i, jc:j1 + 1]
            lm = np.maximum.accumulate(y); rm = np.maximum.accumulate(y[::-1])[::-1]
            yf = np.minimum(lm, rm)
            Y[i, jc:j1 + 1] = y + wr[i] * (yf - y)
    # 境の輪は土台のまま
    c0_, A0_, Y0_ = S.load_rows()
    for AA, A0x in ((A, A0_), (Y, Y0_)):
        AA[0] = A0x[0]; AA[-1] = A0x[-1]; AA[:, 0] = A0x[:, 0]; AA[:, -1] = A0x[:, -1]
    return c, A, Y, log


def main():
    pre, dpath = sys.argv[1], sys.argv[2]
    design = json.load(open(dpath, encoding="utf-8"))
    t0 = time.time()
    c, A, Y, log = build(design)
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    A1, Y1 = log.pop("_stage1")
    np.savez(pre + "_stage1_rows.npz", c=c, A=A1, Y=Y1)
    prov = {"route": "美術の見本04 の直しの回 1 Tools/GWWaveGen/as04/fx1_build.py（shape_build.py の順に、②③ の湾 shorten_more と窓のならし post_smooth を足した。numpy、行の断面の作り直し）",
            "base": "K*′ AS02C (%s, sha256 %s)" % (S.BASE_ROWS.replace(S.REPO + "/", ""), S.sha(S.BASE_ROWS)),
            "design": design, "reference_model_read_by_generator": False, "photos_read_by_generator": False}
    S.K.write_candidate(pre, c, A, Y, prov)
    S.jdump(pre + "_build_log.json", {"design": design, "log": log, "seconds": round(time.time() - t0, 1)})
    print("FX1_BUILD_DONE", pre, round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
