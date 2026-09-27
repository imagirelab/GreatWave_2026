# -*- coding: utf-8 -*-
"""設計28：入力条件の変更と較正の掃引の結果（ds28_inputs_run.py の出力）をまとめる（要点の JSON と日本語の表）。

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_summary.py
入力：Unity/Build/Design/28/inputs/ds28_inputs_metrics.json・ds28_inputs_series.npz（Git 対象外）
出力：同じフォルダーの ds28_inputs_summary.json・ds28_inputs_summary.md
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Unity", "Build", "Design", "28", "inputs")
G = 9.81
GATES = ("P1", "P4", "P5", "P6", "P7", "P10", "P15", "P16")


def r_(x, n=2):
    return None if x is None else round(float(x), n)


def footprint(S, frac=0.02):
    """t* の主断面の本体の足跡（y > 0.02H の a の広がり、m）。"""
    A, Y = S["sec_main"][-1, 0], S["sec_main"][-1, 1]
    H = Y.max()
    m = Y > frac * H
    return float(A[m].max() - A[m].min())


def main():
    J = json.load(open(os.path.join(OUT, "ds28_inputs_metrics.json"), encoding="utf-8"))
    M = J["runs"]
    z = np.load(os.path.join(OUT, "ds28_inputs_series.npz"))
    SER = {}
    for k in z.files:
        nm, key = k.split("|", 1)
        SER.setdefault(nm, {})[key] = z[k]

    def row(nm):
        R = M[nm]
        tr = R["tstar"]
        out = dict(label_ja=R["label_ja"].replace("\n", " "), c0_mps=r_(R["cfg"]["c0_used_mps"], 2),
                   tstar_rms_m=tr["rms_m"], tstar_body_cols_rms_m=tr.get("body_cols_rms_m"), tstar_main_row_rms_m=tr["main_row_rms_m"],
                   tstar_max_m=tr["max_m"], tstar_max_at=tr["max_at"], painting_outline_mean_px=tr["painting_upper_outline"]["mean_abs_px"],
                   painting_outline_max_px=tr["painting_upper_outline"]["max_abs_px"], painting_outline_extra_wave_bins=tr["painting_upper_outline"].get("extra_wave_bins"),
                   overhang_Lo_over_H_tstar=dict(main=tr["overhang_Lo_over_H"]["main"], peak=tr["overhang_Lo_over_H"]["peak"]),
                   E1_fraction=R["lip_plausibility_E1"]["fraction"], E1_u_over_c0_p5_50_95=R["lip_plausibility_E1"]["u_over_c0_p5_50_95"])
        g = R.get("gates")
        if g:
            p = g["P15"]["peak_192"]
            q = g["P15"]["main_159"]
            out.update(stage_tau_peak_row=p["tau"], stage_dev_peak_row=p["dev"], stage_tau_main_row=q["tau"],
                       theta_c_at_b_deg=dict(peak=p["theta_c_at_b_deg"], main=q["theta_c_at_b_deg"]),
                       theta_c_min_b_window_deg=dict(peak=p["theta_c_min_b_window_deg"], main=q["theta_c_min_b_window_deg"]),
                       first_white_tau=dict(peak=p["first_white"], main=q["first_white"]), white_at_c_ok=dict(peak=p["white_ok"], main=q["white_ok"]),
                       forward_turn_phi_ge_110_tau=dict(peak=p["phi_ge_110_tau"], main=q["phi_ge_110_tau"]),
                       onset_tau=R["onset"], gates_pass={k: g[k]["pass_"] for k in GATES},
                       gates_failed=[k for k in GATES if not g[k]["pass_"]],
                       P1_speed_mps=dict(main=g["P1"]["main_159"]["speed_mps"], peak=g["P1"]["peak_192"]["speed_mps"]),
                       P5_tip_over_crest=dict(main=g["P5"].get("main_159", {}).get("ratio"), peak=g["P5"].get("peak_192", {}).get("ratio")),
                       P7_s=dict(main=g["P7"]["main_159"], peak=g["P7"]["peak_192"]), P10=dict(corr=g["P10"]["corr"], t50_std_s=g["P10"]["t50_std_s"]),
                       P16_worst_mps2=g["P16"]["worst_A_mps2"], sim_compare_peak_row=R["sim_compare"]["peak_192"],
                       lateral_spread_fit_mps=R["sim_compare"].get("lateral_spread_mps_fit"))
            if nm in SER and "sec_main" in SER[nm]:
                W = footprint(SER[nm])
                cf = math.sqrt(G * 2 * W / (2 * math.pi))
                out["sliding"] = dict(main_row_footprint_tstar_m=r_(W, 1), free_wave_speed_of_2W_mps=r_(cf, 2), c0_over_free=r_(R["cfg"]["c0_used_mps"] / cf, 2),
                                      ground_travel_onset_to_tstar_m=r_(SER[nm]["ca_peak"][-1] - np.interp(R["onset"]["peak"] or -2.4, SER[nm]["t60"], SER[nm]["ca_peak"]), 1))
        return out

    S = dict(schema="GreatWave.DS28.inputs_summary/1", number="設計28",
             evidence_kind_ja="numpy の生成器の解析式の測定（設計27 の生成器を読むだけで継承）。Unity の描画・HMD の結果ではない",
             sources=dict(metrics="Unity/Build/Design/28/inputs/ds28_inputs_metrics.json", frozen_ds27_sha256=J["frozen_ds27_sha256"],
                          sim_reference=J["sim_reference"]))
    S["baselines"] = {nm: row(nm) for nm in ("base_art_on", "base_art_off_kstar") if nm in M}
    S["inputs_physics_only"] = {nm: row(nm) for nm in M if nm.startswith("in_")}
    S["inputs_physics_only_phys_growth"] = {nm: row(nm) for nm in M if nm.startswith("ing_")}
    S["calibration_art_on"] = {nm: row(nm) for nm in ["base_art_on"] + [n for n in M if n.startswith("cal_on_")]}
    S["calibration_physics_only"] = {nm: row(nm) for nm in ["in_d60_l195"] + [n for n in M if n.startswith("cal_ph_")]}
    sw = {}
    for nm in M:
        if nm.startswith("sw_"):
            tr = M[nm]["tstar"]
            sw[nm] = dict(label_ja=M[nm]["label_ja"].replace("\n", " "), tstar_rms_m=tr["rms_m"], body_cols_rms_m=tr.get("body_cols_rms_m"),
                          main_row_rms_m=tr["main_row_rms_m"], max_m=tr["max_m"], painting_outline_mean_px=tr["painting_upper_outline"]["mean_abs_px"],
                          overhang_Lo_over_H_tstar=tr["overhang_Lo_over_H"])
    S["switches_tstar"] = sw
    # 物理の頂の高さ（t* の波峰線に沿った高さと、主役の峰の育ち方）
    from ds28_inputs_model import CarrierCrest, c0_from_inputs
    import ds27_gates as DG
    ks = DG.KStar()
    cs = [-29.5, -25.0, -20.0, -15.0, -10.0, -5.0, 0.0, 3.85, 5.5, 8.0, 12.0]
    ci = [int(np.argmin(np.abs(ks.c - c))) for c in cs]
    phys = dict(c_m=cs, kstar_H_m=[r_(ks.Hrow[i], 1) for i in ci])
    for dth in (0, 60, 120):
        for lam in (195, 250):
            cc = CarrierCrest(dth, lam)
            phys["H_m_d%d_l%d" % (dth, lam)] = [r_(v, 1) for v in cc.height(cc.envelope_c(np.array(cs)))]
    taus = [-10.12, -8.0, -6.0, -4.2, -3.4, -2.4, -2.05, -1.0, 0.0]
    gr = dict(tau_s=taus)
    for lam in (195, 250):
        cc = CarrierCrest(60, lam)
        z_ = cc.hero_zeta(np.array([0.0]), np.array(taus), c0_from_inputs(60, lam))
        H = cc.height(z_)[0]
        gr["phys_H_over_Hstar_l%d" % lam] = [r_(v / H[-1], 3) for v in H]
    if "base_art_on" in SER:
        t60 = SER["base_art_on"]["t60"]
        Hn = SER["base_art_on"]["H_peak"] / SER["base_art_on"]["H_peak"][-1]
        gr["design27_calibrated_peak_row"] = [r_(np.interp(t, t60, Hn), 3) for t in taus]
    S["physical_crest"] = dict(tstar_along_crest=phys, hero_crest_growth=gr,
                               note_ja="物理の頂＝±Δθ/2 の 2 系の分散集中（設計27 の搬送波と同じ成分、NewWave）を焦点（主断面 c = 0）で H* = 20.80 m にし、線形＋狭帯域の 2 次（設計26 E2）。"
                                       "育ち方は焦点で最大になる峰を模様の速さで追った高さ（主断面）で、Δθ によらない（行 c ≠ 0 は包絡の分だけ低い）")
    json.dump(S, open(os.path.join(OUT, "ds28_inputs_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: (list(v.keys()) if isinstance(v, dict) else v) for k, v in S.items()}, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
