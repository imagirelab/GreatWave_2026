# -*- coding: utf-8 -*-
"""美術の見本05 やり方 B：守る規則（targets.json の K）を、見本04 の asm4_rules.py（変えない）の測りで AS05B の部品へ向けて測る。
py -3.10 -B Tools/GWWaveGen/as05/shapeB_rules.py [描画の名前（既定 B1）]

asm4_common の置き場（主役波の行・静止のメッシュ・wave4 と合わせたメッシュ・爪・描画・測りの置き場）を AS05B のものへ替えてから、
asm4_rules の g2（関門、合わせた輪郭）・s4（背は一つの山）・s8（出っ張り）・s9（④ と左の白）・s10（峰に沿う長さ）・c2_c3（爪）を呼ぶ。
足す測り：K-top（行 c ≥ −8 の点の動き）、K-boat（船・手前の海の射線の禁止域への新しいはみ出し、Unity の ID 画像の船の画素の数を見本04 と比べる）、
S10 を見本04（AS04F ＋ wave4）と比べる（0.6〜0.9 H の帯 ±0.25 m、低い帯 +0.5 m まで）。
出力：Unity/Build/Polish/sample05/shapeB/measure/rules_check_AS05B.json
"""
import json
import os
import sys
import time

os.environ["AS04_FIX"] = "fix1"
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as04")
sys.path.insert(0, HERE)
import asm4_common as A  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "B1"
SB = REPO + "/Unity/Build/Polish/sample05/shapeB"
A.ASM = SB
A.RTAG = TAG
A.UNION = SB + "/union/union.json"
A.WAVE4 = REPO + "/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json"
A.HERO_SM04 = SB + "/mesh/hero_smooth_as05b.json"
A.ROWS04 = SB + "/final/cand/kstarAS05B_a45_rows.npz"
A.GWB04 = SB + "/final/cand/kstarAS05B_a45.gwb"
A.CLAWS04 = SB + "/claws/ds33_claw_layout.json"
A.MEAS = SB + "/measure/rules_" + TAG
import asm4_rules as R  # noqa: E402

R.BACK_MEASURE = SB + "/final/eval_AS05B_back_measure.json"
R.OUT = SB + "/measure/rules_check_AS05B.json"
import shapeB_common as B  # noqa: E402
import shapeB_quick as Q  # noqa: E402


def k_top():
    c, A1, Y1 = B.load_rows(A.ROWS04)
    c0, A0, Y0 = B.load_rows(B.ROWS04F)
    m = c >= B.C_KTOP
    d = max(float(np.abs(A1 - A0)[m].max()), float(np.abs(Y1 - Y0)[m].max()))
    return {"rule_ja": "いちばん高い峰（主の頂と唇、行 c ≥ −8 m）の形は見本04 のまま（点の動き 0.05 m まで）", "max_disp_m": round(d, 5),
            "first_changed_row_c": B.rnd(c[np.nonzero((np.abs(A1 - A0).max(1) + np.abs(Y1 - Y0).max(1)) > 1e-6)[0].max()], 2),
            "verdict": "pass" if d <= 0.05 else "fail"}


def k_boat():
    from PIL import Image
    c, A1, Y1 = B.load_rows(A.ROWS04)
    c0, A0, Y0 = B.load_rows(B.ROWS04F)
    sp = Q.spill(c, A1, Y1, (c0, A0, Y0))
    out = {"rule_ja": "一艘目の船を原画視点で層の面が隠さない（船・手前の海の射線の禁止域へ新しくはみ出さない・Unity の ID 画像の船の画素を減らさない）",
           "protect_spill_new_cells_vs_AS04F": sp["boat_nearsea_keepout_new_cells"], "protect_spill_rows": sp["boat_rows"],
           "sky_keepout_new_cells_vs_AS04F": sp["sky_keepout_new_cells"], "selfx_new_rows_c": sp["selfx_new_rows_c"], "cell_m": sp["cell_m"]}
    ids = {}
    for name, p in (("AS05B", SB + "/render/" + TAG + "/full/ids_line.png"),
                    ("sample04_FX1", REPO + "/Unity/Build/Polish/sample04/assemble/render/FX1/full/ids_line.png")):
        im = np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
        ids[name] = {"boat_left_px": int(((im[..., 0] == 34) & (im[..., 1] == 0) & (im[..., 2] == 0)).sum()),
                     "boat_mid_px": int(((im[..., 0] == 0) & (im[..., 1] == 34) & (im[..., 2] == 0)).sum()),
                     "boat_fg_px": int(((im[..., 0] == 34) & (im[..., 1] == 34) & (im[..., 2] == 0)).sum())}
    out["unity_id_boat_pixels"] = ids
    r = ids["AS05B"]["boat_left_px"] / max(ids["sample04_FX1"]["boat_left_px"], 1)
    out["boat_left_pixels_ratio_vs_sample04"] = round(r, 4)
    out["verdict"] = "pass" if (r >= 0.98 and sp["boat_nearsea_keepout_new_cells"] == 0) else ("pass_px_only" if r >= 0.98 else "fail")
    out["note_ja"] = ("禁止域（0.12 m 角の格子）への新しいはみ出しは見本04 AS04F に対して %d セル。作り直した唇の下の点は、見張り（shapeB_build.protect_guard）で"
                      "禁止域の外へ押し上げ、押し上げの量を行・列の向きになめらかにした。Unity の ID 画像の船の画素の比でも、船が隠れていないことを確かめる"
                      % sp["boat_nearsea_keepout_new_cells"])
    return out


def s10_vs_sample04():
    c, A1, Y1 = B.load_rows(A.ROWS04)
    c0, A0, Y0 = B.load_rows(B.ROWS04F)
    ch4, _, _ = A.read_static(A.WAVE4)
    X4 = ch4["position"].astype(np.float64)
    bw, dent = Q.bands_union(c, Y1, X4)
    bw0, dent0 = Q.bands_union(c0, Y0, X4)
    diff = {k: (round(bw[k] - bw0[k], 2) if bw[k] is not None and bw0[k] is not None else None) for k in bw}
    hi_ok = all(diff[k] is not None and abs(diff[k]) <= 0.25 for k in ("0.6", "0.7", "0.8", "0.9"))
    lo_ok = all(diff[k] is not None and diff[k] <= 0.5 for k in ("0.1", "0.2", "0.3", "0.4", "0.5"))
    return {"rule_ja": "峰に沿う長さ：0.6〜0.9 H の帯は見本04 と同じ（±0.25 m）、低い帯は +0.5 m まで（H = 20.27 m、主役波 ＋ wave4）",
            "AS05B_widths_m": bw, "sample04_widths_m": bw0, "diff_m": diff, "verdict": "pass" if (hi_ok and lo_ok) else "fail"}


def main():
    t0 = time.time()
    os.makedirs(A.MEAS, exist_ok=True)
    res = {"schema": "GreatWave.AS05B.rules/1", "date": time.strftime("%Y-%m-%d %H:%M"), "render": TAG,
           "inputs": {A.rel(p): A.sha(p) for p in (A.UNION, A.WAVE4, A.HERO_SM04, A.ROWS04, A.GWB04, A.CLAWS04)}}
    def c23():
        c2, c3, rows = R.c2_c3()
        return {"C2": c2, "C3": c3, "per_claw": rows, "verdict": "pass" if (c2["verdict"] == "pass" and c3["verdict"] == "pass") else "fail"}
    for name, fn in (("K_top", k_top), ("K_boat", k_boat), ("S10_vs_sample04", s10_vs_sample04), ("G2", R.g2), ("S4", R.s4), ("S8", R.s8),
                     ("S9", R.s9), ("S10_vs_sample03", R.s10), ("C2_C3", c23)):
        try:
            res[name] = fn()
        except Exception as ex:  # noqa
            import traceback
            res[name] = {"error": repr(ex), "trace": traceback.format_exc()[-1500:]}
        print(name, res[name].get("verdict"), round(time.time() - t0, 1), flush=True)
        A.jdump(R.OUT, res)
    res["seconds"] = round(time.time() - t0, 1)
    A.jdump(R.OUT, res)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
