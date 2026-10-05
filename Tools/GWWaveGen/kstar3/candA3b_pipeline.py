# -*- coding: utf-8 -*-
"""Q21 candidate A3b pipeline: design (candA3b_build) -> b-region roll (candA3b_tier) -> edge-only lock (candA3b_fit).
usage: py -3.10 candA3b_pipeline.py candA3b_params.json <tag>   (writes _work/<tag>.npz, <tag>t.npz, <tag>f.npz)"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA3b_common as B
import candA3b_build as BU
import candA3b_tier as TI
import candA3b_fit as FI

if __name__ == "__main__":
    prm_path, tag = sys.argv[1], sys.argv[2]
    prm = json.load(open(prm_path, encoding="utf-8"))
    w = lambda s: os.path.join(B.WORK, s)
    BU.main(prm_path, w(tag + ".npz"))
    TI.main(w(tag + ".npz"), w(tag + "t.npz"), prm_path)
    FI.main(w(tag + "t.npz"), w(tag + "f.npz"), prm.get("fit", {}).get("rounds", 30), prm=prm)
