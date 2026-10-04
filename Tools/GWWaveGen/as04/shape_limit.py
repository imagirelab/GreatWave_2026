# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：作り直した行（shape_build の出力）を、土台 AS02C からの変位として、原画視点の禁止域で押さえる。

仕上げ28修正01 の r01_shoulder_build.Build の確かめと押さえをそのまま使う（変えない）：
  - 原画の空の射線の禁止域（膨らみ 3 px）と、段階9 の船・手前の海の射線の禁止域（R4 の面の手前まで）に、土台の塗りにない所で新しくかからない。
  - 断面が新しく自己交差しない。背の海の帯は単調。
  - 変位の向きに沿って禁止域までの余地で、変位の割合（0..1）を上から押さえ、c 方向・列の方向にならす（3 次元でなめらか）。
違うのは、望む変位が shape_build の結果と土台の差であること、原画視点で見える頂点も止めないこと（形を変えるのは原画視点で見える所だから。
関門の行・列は、shape_build がそもそも動かさない）。
py -3.10 -B shape_limit.py <out_prefix> <base_rows.npz（段 1：唇を短くした行）> <target_rows.npz（段 2：左と ③ を足した行）> [--write-candidate]
土台の塗り（禁止域の「新しく」の基準）は段 1。段 1 の唇の短くしは、禁止域へのはみ出しを shape_eval で別に測る。
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402

sys.path.insert(0, S.REPO + "/Tools/GWWaveGen/kstar_p28")
import r01_shoulder_build as SB  # noqa: E402


class LimitBuild(SB.Build):
    def __init__(self, target, base, design=None):
        d = {"sigma_c_m": float(os.environ.get("AS04_LIMIT_SIGMA_C", "1.2")), "sigma_cols": 2.0, "clear_margin_m": 0.15}
        if design:
            d.update(design)
        super().__init__(d, base)
        z = np.load(target)
        assert np.allclose(z["c"], self.c)
        self.At, self.Yt = z["A"].astype(float), z["Y"].astype(float)
        self.visq[:] = False
        self.visv[:] = False

    def anchors(self):
        self.ja = np.full(self.nv, 18 + 8); self.jf = np.full(self.nv, 399)

    def desired(self):
        dA = self.At - self.A0; dY = self.Yt - self.Y0
        dA[0] = dA[-1] = 0.0; dY[0] = dY[-1] = 0.0
        return dA, dY, {"desired_from": "shape_build target"}

    def assemble(self, mul, dA, dY):
        # 海の帯も shape_build のとおりに動かす（土台の Build は列 0..17 を並べ直すので、ここでは割合を掛けるだけ）
        A = self.A0 + mul * dA
        Y = self.Y0 + mul * dY
        return A, Y


def main():
    pre, base, target = sys.argv[1], sys.argv[2], sys.argv[3]
    t0 = time.time()
    b = LimitBuild(target, base)
    A, Y = b.run()
    c = b.c
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    mv_t = np.hypot(b.At - b.A0, b.Yt - b.Y0)
    lost = np.hypot(b.At - A, b.Yt - Y)
    rep = {"base": base, "base_sha256": S.sha(base), "target": target, "target_sha256": S.sha(target), "log": b.log,
           "desired_max_m": S.rnd(mv_t.max()), "lost_vs_target_m": {"max": S.rnd(lost.max()), "p99": S.rnd(np.percentile(lost[mv_t > 0.01], 99)) if (mv_t > 0.01).any() else 0.0},
           "rows_limited_c": [S.rnd(c[i], 2) for i in range(len(c)) if lost[i].max() > 0.05],
           "seconds": round(time.time() - t0, 1)}
    if "--write-candidate" in sys.argv:
        prov = {"route": "美術の見本04 の形づくり Tools/GWWaveGen/as04/shape_build.py → shape_limit.py（r01_shoulder_build.Build の禁止域の押さえ）",
                "base": "K*′ AS02C (%s, sha256 %s)" % (S.BASE_ROWS.replace(S.REPO + "/", ""), S.sha(S.BASE_ROWS)),
                "stage1": base.replace("\\", "/"),
                "target": target.replace("\\", "/"), "reference_model_read_by_generator": False, "photos_read_by_generator": False}
        S.K.write_candidate(pre, c, A, Y, prov)
    else:
        np.savez(pre + "_rows.npz", c=c, A=A, Y=Y)
    S.jdump(pre + "_limit_report.json", rep)
    print(json.dumps({k: v for k, v in rep.items() if k != "log"}, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
