# -*- coding: utf-8 -*-
"""FLIP42 R4 の独立の確かめ：巻き始めの読み（弦の長さ）と、険しさの読み（真ん中の節・内側 3 節の平均）を変えた時に、
巻き始めのコマと C3 がどれだけ動くか（自前）。check_R4_geom.py の関数を使う。
py -3.10 check_R4_onset_sens.py → check_R4_onset_sens.json
"""
import os, json
import numpy as np
import check_R4_geom as G
from ck_common import cfg, load_hf, load_sec, still_level

OUTDIR = os.path.dirname(os.path.abspath(__file__))


def main():
    G.AIR_SIGN = G.orient_rule_test()
    out = {}
    for run in ("R4d", "R3"):
        c = cfg(run); xp = c["parms"]["x_p"]; vox = c["parms"]["dp"] * 2
        hf = load_hf(run); sec = load_sec(run); meta = sec["meta"]
        off = still_level(hf, xp); off3 = still_level(hf, xp, "in3")
        xr = hf["x"] - xp
        x_lo = meta["x0"] - xp; x_hi = meta["x0"] + (meta["nx"] - 1) * meta["dx"] - xp
        res = {}
        for step in (0.5, 1.0, 2.0):
            on = None
            for f in sec["frames"]:
                f = int(f)
                if f < 3690:
                    continue
                g = G.analyze_frame(sec["sdf"][f], meta, xp, off, vox, None, step)
                if g.get("overhang"):
                    q = G.hf_quant(hf["mid"][f - 1], xr, off, x_lo, x_hi)
                    q3 = G.hf_quant(hf["in3"][f - 1], xr, off3, x_lo, x_hi)
                    on = dict(frame=f, t=(f - 1) / 24, x_vertical=g["vertical_x"], steep_mid=q["steep"], steep_in3=q3["steep"],
                              eta_c_mid=q["eta_c"], eta_c_in3=q3["eta_c"], H_mid=q["H"], H_in3=q3["H"])
                    break
            res["step_%g" % step] = on
        out[run] = res
    # C3 の組み合わせ
    comb = {}
    for k in ("step_0.5", "step_1", "step_2"):
        a = out["R3"][k]; b = out["R4d"][k]
        comb[k] = dict(C3_mid=(a["steep_mid"] - b["steep_mid"]) / b["steep_mid"], C3_in3=(a["steep_in3"] - b["steep_in3"]) / b["steep_in3"],
                       C1_dt=a["t"] - b["t"], C1_dx=a["x_vertical"] - b["x_vertical"], C2_H_mid=(a["H_mid"] - b["H_mid"]) / b["H_mid"])
    out["C_by_step"] = comb
    json.dump(out, open(os.path.join(OUTDIR, "check_R4_onset_sens.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
