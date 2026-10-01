# -*- coding: utf-8 -*-
"""仕上げ28修正01 の変種 RIDGE：候補の速い確かめ（py -3.10）。原画視点の関門（定義どおりの読み 78/130/131/132/72、σ12 の大きな輪郭 132/72、
評価基準の F01 の公式の経路 rubric_check.check(gate=True)）と、評価基準の必須の不合格の数（F13 なし）。参照モデルは読まない。
usage: py -3.10 r01_ridge_quick.py label=rows.npz ...
"""
import os
import sys
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KH = os.path.abspath(os.path.join(HERE, "..", "kstar_h"))
sys.path.insert(0, KH)
sys.dont_write_bytecode = True
import kh_eval as KE  # noqa: E402  （kh_eval と同じ順で rubric をリポジトリの写しから読む）
import numpy as np  # noqa: E402
import kh_gate_lf as KG  # noqa: E402

lf = KG.LFGate()
for a in sys.argv[1:]:
    t0 = time.time()
    lab, p = a.split("=", 1)
    R = KE.RC.check(p, gate=True, ref_cache=None)
    g = R["gate_raw"]
    z = np.load(p)
    glf, _ = lf.measure_rows(z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float))
    rc = KE.FE.recount(R)
    fails = [ (k, x["name"], x["value"]) for k, v in R["checks"].items() for x in v if not x["pass_must"]]
    print(lab, "def 78/130/131 %.3f/%.3f/%.3f 132 %.3f 72p95 %.3f | lf132 %.3f lf72p95 %.3f | must-fail %s | %.0fs" % (
        g["78"]["max_px"], g["130"]["max_px"], g["131"]["max_px"], g["132"]["max_px"], g["72"]["p95_px"], glf["132"]["max_px"], glf["72"]["p95_px"],
        rc.get("must_fail", rc), time.time() - t0), flush=True)
    for f in fails:
        print("    ", f[0], f[1], f[2] if not isinstance(f[2], float) else round(f[2], 3))
