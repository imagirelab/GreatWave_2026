# -*- coding: utf-8 -*-
"""FLIP51 'deep focused groups' calibration: the frozen e51 convergence metrics on the FLIP45 V1 record (Fochesato 2007 case,
T 7.004 s, h 20 m flat, 30 components uniform +-45 deg, a_sum 6.29 m, FLIP particle 0.5 m). Read only on FLIP45/runs/V1;
writes Unity/Build/FLIP51/screens/dfg51/v1_calibration.json. 2026-10-17 written new (Claude). py -3.10 -B dfg51_v1cal.py"""
import os, sys, json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import e51_metrics as EM  # noqa: E402

RD = os.path.join(EM.ROOT, "Unity/Build/FLIP45/runs/V1")
ETA0 = 0.07836636900901794          # V1 ana.json still_level_offset_m
ON_F, ON_X = 1330, 242.5            # V1 ana.json onset (t 53.375 s; t = (f - 1)/24 - 2)
KEEP = ("Hc", "x_pk", "W20", "W50", "W80", "W95", "taper", "K", "S1", "S2", "ring_max", "Lx50", "A50", "face_deg", "concavity", "back_deg")


def main():
    xwin = (ON_X - 60.0, ON_X + 35.0)
    avail = EM.frames_available(RD)
    rows = []
    for f in range(ON_F - 72, ON_F + 37, 3):
        if f not in avail:
            continue
        m = EM.frame_metrics(RD, f, xwin, ETA0, with_section=True)
        if not m or "W50" not in m:
            continue
        r = {k: (float(m[k]) if k in m else None) for k in KEEP}
        r["frame"] = f; r["t"] = (f - 1) / 24.0 - 2.0; r["W50_m"] = m["W50"] * m["Hc"]
        r["miss"] = EM.score_vs_target(m)[0]
        rows.append(r)
    on = [r for r in rows if r["frame"] == ON_F][0]
    mx = max([r for r in rows if r["frame"] <= ON_F + 36 and r["frame"] >= ON_F - 72], key=lambda r: r["Hc"])
    out = dict(run=RD, eta0=ETA0, onset=on, max=mx, rows=rows,
               note="t = (f-1)/24 - 2 (V1 t_off -2 s); linear theory (dfg51_screen F07): Hc 6.28 m, W50 57.0 m (W50/Hc 9.06); "
                    "second order: Hc 7.98 m, W50 50.5 m (6.34)")
    p = os.path.join(EM.ROOT, "Unity/Build/FLIP51/screens/dfg51/v1_calibration.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    for k in ("onset", "max"):
        r = out[k]
        print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in r.items()})
    print("wrote", p)


if __name__ == "__main__":
    main()
