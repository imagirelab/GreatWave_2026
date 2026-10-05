# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: (re)design of the far end and of the near-shoulder tail on top of a fitted design (numbers only).
Far end (c > 0): the lip roofs the painting's see-through tube while the row is tall enough (tip line receding ~2.1 m per
m of c), then the curl closes behind the tube's near edge (H to 0 at c +13.5).  Shorter than the first try (c +17), so
the plan-view sweep is shorter.  Tail (c < -18, outside the painting frame): a small curl shrinking into the sea
(no drooping tier lip).
usage: py -3.10 candA4_redesign_far.py design_in.json design_out.json"""
import sys, json
import numpy as np

FAR = [2.0, 3.5, 5.0, 6.5, 8.0, 9.5, 11.0, 12.5, 13.5]
H = [20.1, 19.4, 18.5, 17.4, 16.3, 13.0, 8.2, 3.6, 0.0]
AT = [-1.5, -2.9, -4.5, -6.2, -8.0, -10.5, -12.8, -14.6, -15.6]
TAIL = {-60: 0.0, -38: 0.0, -28: 4.6, -22: 9.0}
TAIL_SHAPE = {"ea": 0.5, "r1": 0.20, "t1": 30, "r2": 0.35, "t2": 25, "r3": 0.10, "t3": 12, "r4": 0.15, "t4": 55, "r5": 0.06, "t5": 20,
              "tc": 150, "bx": 0.25, "by": 0.33, "rR": 0.22, "e2c": 0.0, "e2s": 0.0, "phj": 60}


def main(a, b):
    d = json.load(open(a))
    S = list(d["sites"]["default"])
    near = [s for s in S if s <= 0.5]
    newS = near + FAR
    vals = {}
    for k, v in d["values"].items():
        v = np.array(v, float)
        out = [float(v[S.index(s)]) for s in near]
        for s in FAR:           # far shape parameters: carried over by interpolation of the previous far design
            out.append(float(np.interp(min(s, 11.0), S, v)))
        vals[k] = out
    for s, h, at in zip(FAR, H, AT):
        i = newS.index(s); vals["H"][i] = h; vals["aT"][i] = at
    for s, h in TAIL.items():
        i = newS.index(s); vals["H"][i] = h
        for k, v in TAIL_SHAPE.items():
            vals[k][i] = v
    d["sites"]["default"] = newS; d["values"] = vals
    d["note"] = (d.get("note", "") + " | far end redesigned (closing c +13.5) and tail (c < -18) set to a small curl").strip(" |")
    json.dump(d, open(b, "w"), indent=1)
    print(newS)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
