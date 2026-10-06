# -*- coding: utf-8 -*-
"""P2 の計算の途中の様子（py -3.10）。使い方: py -3.10 p2_live.py <run_dir>
z の切り口（sec/zXXXX）ごとの出来事（P1 の p1_analyze：砕けの始まり B>0.85、前の面が垂直を過ぎた、空洞が閉じた）と、
最後に書かれた crest.npy の峰に沿う頂の高さ（10 m の帯ごと）を出す。計算中でも読める（読むだけ）。"""
import sys, os, glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1_analyze as A1  # noqa: E402

rd = sys.argv[1]
for sd in sorted(glob.glob(os.path.join(rd, "sec", "z*")), key=lambda s: int(os.path.basename(s)[1:])):
    try:
        r = A1.analyze(sd, quiet=True)
    except Exception as e:
        print(os.path.basename(sd), "ERR", str(e)[:80]); continue
    ev = r["events"]
    tl = r["timeline"]
    last = tl[-1] if tl else {}
    def e(k):
        v = ev.get(k)
        return "%.2f@x%.0f" % (v["t"], v.get("x") or 0) if isinstance(v, dict) else "-"
    print("%s plunge=%s onset=%s vert=%s tube=%s crest_max=%.1f | last t=%.2f crest=%s" % (
        os.path.basename(sd), r["plunging"], e("breaking_onset_B085"), e("face_past_vertical"), e("tube_closed_or_nearly"),
        ev.get("crest_max_before_overturn_m") or float("nan"), last.get("t", float("nan")), last.get("crest")))
cp = os.path.join(rd, "crest.npy")
if os.path.isfile(cp):
    c = np.load(cp)
    for k in range(max(0, len(c) - 1 - 96), len(c), 24):
        row = c[k]
        print("t=%.2f y:" % row[1], " ".join("%4.1f" % v for v in row[2::3]))
        print("      x:", " ".join("%4.0f" % v for v in row[3::3]))
