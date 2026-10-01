# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）：設計の変種を作って速い測りと診断の図を書く（py -3.10）。
usage: py -3.10 backfirst_try.py OUT_DIR label design.json [--ov] [--secs]"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import backfirst_model as M
import backfirst_eval as BE
out, lab, dj = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
d = json.load(open(dj, encoding="utf-8"))
c, A, Y = M.build(d)
np.savez_compressed(os.path.join(out, lab + "_rows.npz"), A=A, Y=Y, c=c)
r = BE.quick(c, A, Y)
print(lab, BE.brief(r), flush=True)
print("   sag worst", r["sag"]["worst"], "72 worst", r["gate"]["72lf"]["worst"], flush=True)
json.dump(r, open(os.path.join(out, lab + "_quick.json"), "w", encoding="utf-8"), indent=1, default=float)
if "--rubric" in sys.argv:
    rr = BE.rubric(c, A, Y, os.path.join(out, "_tmp"))
    print("   rubric must-fail %d (no F01):" % rr["n_must_fail"], "; ".join(rr["fails"]), flush=True)
if "--ov" in sys.argv:
    BE.overlay(c, A, Y, os.path.join(out, lab + "_ov.png"), lab)
