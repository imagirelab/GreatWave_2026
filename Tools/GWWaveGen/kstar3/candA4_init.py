# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: initial parameter design (before the painting fit).

Numbers only.  The proportions come from the rubric's measured reference-model ranges (Q20 rubric F03/F07, measured on
the reference model's big-wave sections; no mesh is read here):
  shell thickness 0.23-0.31 H, barrel radius 0.42-0.46 H, overhang 0.40-0.58 H, back slope 30-44 deg at 0.9 H,
  big-wave section area / H^2 ~0.29-0.34 (Q20L3 A4 measurement, c -2..+3), lip 0.30-0.39 m thick 0.75 m from the tip,
  crest near c 0, far end = the lip curling on at 0.6-0.75 H (we close it earlier: the painting view's tube opening).
The crest line / heights start from K* 26修正01 (painting-fitted) and are re-fitted by candA4_fit.py.
usage: py -3.10 candA4_init.py out.json
"""
import sys, json
import numpy as np

SITES = [-60, -38, -28, -22, -18, -15, -12, -9, -6.5, -4.5, -2.5, -1, 0.5, 2, 3.5, 5, 6.5, 8, 10, 11.5, 13, 14.5, 16]


def table():
    S = np.array(SITES, float)
    def pw(pairs):
        x = np.array([p[0] for p in pairs], float); v = np.array([p[1] for p in pairs], float)
        return np.interp(S, x, v)
    shoulder = lambda sh, main, far=None: pw([(-60, sh), (-6.5, sh), (-2.5, main), (1, main), (3.5, far if far is not None else main), (16, far if far is not None else main)])
    V = {}
    # near shoulder heights from K*; far part: a tall C wrapping the painting's tube opening (the sky seen through the
    # barrel recedes ~1 m per m of c), closing as a shrinking curl from c +10 to +16 (|dH/dc| <= ~3.5)
    V["H"] = [0, 0, 5.5, 9.8, 11.2, 11.3, 12.6, 16.1, 18.0, 19.3, 20.0, 20.6, 20.8, 20.2, 19.8, 19.4, 19.1, 18.8, 18.2, 15.5, 11.0, 5.5, 0.0]
    V["aT"] = [0] * 12 + [-0.2, -1.0, -2.3, -3.6, -5.0, -6.4, -8.3, -10.0, -11.8, -13.5, -15.0]
    V["ea"] = shoulder(0.42, 0.40, 0.40)
    V["eb"] = shoulder(0.80, 0.82, 0.80)
    V["thb"] = shoulder(78, 80, 80)
    V["rf"] = shoulder(0.12, 0.12, 0.12)
    # lip chain: main = the painting's 132 (top arc R ~3.7 m, long gentle descent, small concave neck, hook);
    # shoulder = the b region (descent, valley, ridge = band top, nose, claw tip = band bottom)
    V["r1"] = shoulder(0.16, 0.18, 0.18)
    V["t1"] = shoulder(30, 22, 25)
    V["r2"] = shoulder(0.40, 0.60, 0.45)
    V["t2"] = shoulder(30, 30, 30)
    V["r3"] = shoulder(0.12, 0.12, 0.10)
    V["t3"] = shoulder(60, 33, 25)
    V["r4"] = shoulder(0.10, 0.11, 0.10)
    V["t4"] = shoulder(100, 60, 60)
    V["r5"] = shoulder(0.06, 0.06, 0.06)
    V["t5"] = shoulder(35, 40, 40)
    V["rt"] = shoulder(0.18, 0.2, 0.18)
    V["tc"] = shoulder(150, 140, 150)
    V["k0"] = shoulder(0.35, 0.35, 0.35)
    V["k1"] = shoulder(0.35, 0.35, 0.35)
    V["bx"] = shoulder(0.26, 0.22, 0.23)
    V["by"] = pw([(-60, 0.33), (-6.5, 0.33), (-2.5, 0.25), (1, 0.25), (2, 0.347), (3.5, 0.379), (5, 0.412), (6.5, 0.435), (8, 0.457), (10, 0.489), (11.5, 0.48), (16, 0.45)])
    V["rR"] = pw([(-60, 0.26), (-6.5, 0.26), (-2.5, 0.40), (1, 0.40), (2, 0.337), (3.5, 0.333), (6.5, 0.34), (10, 0.352), (11.5, 0.29), (16, 0.28)])
    for k in ("e2c", "e2s", "e3c", "e3s"):
        V[k] = [0.0] * len(S)
    V["phj"] = shoulder(60, 60, 60)
    V["phe"] = shoulder(10, 10, 10)
    V["lr"] = shoulder(0.40, 0.40, 0.40)
    V["dsea"] = [0.0] * len(S)
    return {k: [float(x) for x in np.asarray(v, float)] for k, v in V.items()}


if __name__ == "__main__":
    d = {"sites": {"default": SITES}, "values": table(),
         "note": "cand A4 initial design (proportions from the rubric's reference-model ranges; heights from K*)"}
    json.dump(d, open(sys.argv[1], "w", encoding="utf-8"), indent=1)
    print(sys.argv[1])
