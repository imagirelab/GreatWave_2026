# -*- coding: utf-8 -*-
"""設計26 の証拠をまとめる：Unity/Build/Design/26/ の実験と診断の出力から、要点の数値を
Docs/Evidence/Design/26/metrics.json に、実行条件と SHA-256 を run.json に書く。

使い方（リポジトリの根で。普通は run_ds26.ps1 から）:
  py -3.12 -B Tools/GWWaveGen/ds26/ds26_evidence.py [--sim-used] [--pdf-used] [--started-utc <ISO>]
--sim-used：この実行で、解算の断面の npz（リポジトリ外・本機のみ）を渡して E2 の (c) と E2c を計算した。
--pdf-used：この実行で、論文の PDF から Fig. 4・5 の並べ図を作り直した。
数値は出力の JSON から読むだけで、ここで新しく計算するのは、(1) E3 の定数からの keypose の容量、
(2) E5 の断面で本体の中に入る唇の点の数、(3) 美術優先30 の診断の時系列（diag_measure.json）からの関門の値、だけ。
"""
import datetime
import glob
import hashlib
import json
import math
import os
import platform
import subprocess
import sys

import numpy as np

import ds26_paths as DP

ARGS = sys.argv[1:]
SIM_USED = "--sim-used" in ARGS
PDF_USED = "--pdf-used" in ARGS
STARTED = None
if "--started-utc" in ARGS:
    STARTED = ARGS[ARGS.index("--started-utc") + 1]
REPO = DP.REPO
F = DP.OUT_FEAS
G = 9.81


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def sha(p):
    return DP.sha256(p)


def J(name, base=F):
    with open(os.path.join(base, name), encoding="utf-8") as f:
        return json.load(f)


def r(x, n=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        return [r(v, n) for v in x]
    return round(float(x), n)


# ---------------------------------------------------------------- E1（旧規則：放出の前の点を頂の 1 点に置く）
e1r = J("e1_result_restricted.json")
e1f = J("e1_result.json")
grid_rows = {}
with open(os.path.join(F, "e1_grid_restricted.csv"), encoding="utf-8") as f:
    head = f.readline().strip().split(",")
    for line in f:
        v = dict(zip(head, line.strip().split(",")))
        if (float(v["c0"]) == 20 and float(v["p"]) == 0.5 and v["vpeel"] == "20.0" and float(v["da"]) == 0.0
                and float(v["vH"]) == 1.0):
            key = "%.1f" % float(v["tau0"])
            grid_rows.setdefault(key, {})["no_decel" if float(v["beta"]) == 1.0 else "decel_0p8c0"] = r(float(v["frac_ok"]))
best_full = e1f["details"][0]
E1 = dict(
    what_ja="唇の膜（巻きのある 133 行の上面の頂→唇先と、下面の唇先→縁の最小点 rim）の各点を、t* に K* へ着く重力だけの軌跡で逆算した（旧規則：放出の前の点を全部、頂の 1 点に置く）。c0 20 m/s、p 0.5、広がり 20 m/s、頂の上昇 1 m/s。",
    n_curled_rows=e1r["n_curled_rows"], n_lip_vertices=e1r["n_lip_vertices"], peak_row_c_m=e1r["c_peak_row"],
    plausibility_range=e1r["plausibility"],
    frac_plausible_by_jet_onset_s=dict(sorted(grid_rows.items(), key=lambda kv: float(kv[0]))),
    with_tube_roof=dict(
        n_vertices=e1f["n_lip_vertices"], best_frac=r(best_full["frac_ok"]), best_params=best_full["params"],
        bad_cols_hist=best_full["bad_cols_hist"],
        ja="rim より奥の管の天井・内壁まで弾道にすると、格子の最良でも 93%。外れは列 280〜314 に集まる（15〜40 m/s で下へ投げる必要がある）→ 本体として動かす"),
)

# ---------------------------------------------------------------- E4（前縁の帯で解き直し、全行の放出の補間の加速度）
e4 = J("e4_result.json")
e4c = J("e4c_default_stats.json")
cfgs = {}
for c in e4["configs"]:
    k = c["name"].split(" ")[0]
    cfgs[k] = dict(name=c["name"], frac_plausible=r(c["frac_plausible"]), n_eval=c["n_eval"],
                   accel_ground_g={kk: (vv if kk == "n" else r(vv, 3)) for kk, vv in c["accel_ground_g"].items()},
                   accel_rowcrest_frame_g={kk: r(vv, 3) for kk, vv in c["accel_rowcrest_frame_g"].items()},
                   exceed_rows_c_range=c["exceed_rows_c_range"])
tipB5 = next(c for c in e4["configs"] if c["name"].startswith("B5"))["tip"]
tipA0 = next(c for c in e4["configs"] if c["name"].startswith("A0"))["tip"]
nd = e4c["new_default"]
E4 = dict(
    what_ja="放出の前の唇を峰の前面に列の順で 2 cm おきに並べる（前縁の帯）。各点はその置き場から打ち出され、速度の補間の後は重力だけ。加速度は各点の放出から t* まで（地面の座標）。",
    configs=cfgs,
    default_config="B5",
    default=dict(frac_plausible=r(nd["frac_ok"]), n_eval=nd["n_eval"], n_bad=nd["n_bad"], bad_reason=nd["bad_reason"],
                 bad_rows_c_m=nd["bad_rows_c"], bad_release_tau_range_s=nd["bad_release_tau_range"],
                 u_over_c0_p5_p50_p95=nd["u_over_c0_p5_p50_p95"], w_mps_p5_p50_p95=nd["w_mps_p5_p50_p95"],
                 w_over_sqrtgH_p5_p50_p95=nd["w_over_sqrtgH_p5_p50_p95"], tip_u_over_c0_main=r(nd["tip_u_over_c0_main"], 3),
                 T_row_min_max_s=[nd["T_row_min"], nd["T_row_max"]]),
    strip_sensitivity=[{k: (r(v) if k == "frac" else v) for k, v in s.items()} for s in e4["e1_strip_sensitivity"]],
    tip_apex=dict(
        default_main=dict(tau_s=r(tipB5["main"]["ramp_apex_tau"], 3), y_m=r(tipB5["main"]["ramp_apex_y"], 3),
                          max_rise_above_crest_m=r(tipB5["main"]["ramp_max_rise_above_crest"], 3)),
        default_peak=dict(tau_s=r(tipB5["peak"]["ramp_apex_tau"], 3), y_m=r(tipB5["peak"]["ramp_apex_y"], 3),
                          max_rise_above_crest_m=r(tipB5["peak"]["ramp_max_rise_above_crest"], 3)),
        old_rule_ballistic_main=dict(tau_s=r(tipA0["main"]["ballistic_apex_tau"], 3), y_m=r(tipA0["main"]["ballistic_apex_y"], 3),
                                     max_rise_above_crest_m=r(tipA0["main"]["ballistic_max_rise_above_crest"], 3)),
    ),
)

# ---------------------------------------------------------------- E4b（網の検査、本体の代理）
e4b = J("e4b_mesh_result.json")
E4b = {}
for k, v in e4b.items():
    E4b[k] = dict(tri_area_min_m2=v["tri_area_min_m2"], tri_area_min_kstar_m2=v["tri_area_min_kstar_m2"],
                  row_edge_min_m=r(v["row_edge_min_m"], 5), row_edge_stretch_max=r(v["row_edge_stretch_max"], 2),
                  cross_row_edge_stretch_max=r(v["cross_row_edge_stretch_max"], 2),
                  seam_stretch_min_max=[r(v["seam_stretch_min"], 3), r(v["seam_stretch_max"], 3)],
                  face_flips=v["face_flips"], row_self_intersections=v["row_self_intersections_total"],
                  row_self_intersections_c_range=v.get("row_self_intersections_c_range"),
                  row_self_intersections_tau_range=v.get("row_self_intersections_tau_range"))

# ---------------------------------------------------------------- E2・E2c（本体を物理から作った場合の差）
e2 = J("e2_result.json") if os.path.exists(os.path.join(F, "e2_result.json")) else J("e2_result_nosim.json")
E2 = dict(
    focused_group_vs_kstar={k: dict(rms_m=r(v["resid_on_kstar_footprint_rms_m"], 2), max_m=r(v["resid_on_kstar_footprint_max_abs_m"], 2),
                                    kA_linear=r(v["kA_linear"], 3), hump_width_m=r(v["hump_width_swl_m"], 1),
                                    trough_m=r(v["trough_front_m"], 2)) for k, v in e2["focused_group_vs_kstar"].items()},
    kstar_footprint_m=r(e2["kstar_main"]["footprint_m"], 2),
    volume_neutral_carrier={k: dict(Ac_m_p5_p50_p95=r(v["Ac_m_p5_p50_p95"], 2), main_row_Ac_m=r(v["main_row_Ac_m"], 2))
                            for k, v in e2["volume_neutral_carrier"].items()},
)
if os.path.exists(os.path.join(F, "e2c_result.json")):
    e2c = J("e2c_result.json")
    E2["sim_window_vs_kstar"] = dict(
        frames=sorted(e2c.keys()),
        iso_rms_m=[r(min(v["iso_rms_m"] for v in e2c.values()), 2), r(max(v["iso_rms_m"] for v in e2c.values()), 2)],
        iso_max_m=[r(min(v["iso_max_m"] for v in e2c.values()), 2), r(max(v["iso_max_m"] for v in e2c.values()), 2)],
        aniso_f=[r(min(v["best_f"] for v in e2c.values()), 3), r(max(v["best_f"] for v in e2c.values()), 3)],
        aniso_rms_m=[r(min(v["aniso_rms_m"] for v in e2c.values()), 2), r(max(v["aniso_rms_m"] for v in e2c.values()), 2)],
        aniso_max_m=[r(min(v["aniso_max_m"] for v in e2c.values()), 2), r(max(v["aniso_max_m"] for v in e2c.values()), 2)],
        width_0p3H_sim_scaled_m=[r(min(v["width_at_0p3H_sim_scaled_m"] for v in e2c.values()), 1),
                                 r(max(v["width_at_0p3H_sim_scaled_m"] for v in e2c.values()), 1)],
        width_0p3H_kstar_m=r(next(iter(e2c.values()))["width_at_0p3H_kstar_m"], 1),
        source_ja="利用者の Houdini 解算の終盤の断面（リポジトリ外・本機のみの npz から。形はリポジトリに入れない）を Froude で縮尺")

# ---------------------------------------------------------------- E3（keypose の間隔と容量）
e3 = J("e3_result.json")
LAYER_B = 1.152e6
UNITY_PER_LAYER_MIB = 397.7 / 181
layers = int(round(6.0 * 7.5 + 7.0 * 30)) + 1
E3 = dict(
    instant_switch_cr_err_m={hz: r(v["max_err_m"], 4) for hz, v in e3["sampling"]["Tr_0.0"]["catmull_rom"].items()},
    velocity_ramp={k: dict(cr_max_err_m={hz: r(v, 5) for hz, v in vv["cr_max_err_m"].items()},
                           max_accel_over_g=r(vv["max_accel_over_g"], 3), kstar_landing_err_m=vv["kstar_landing_err_m"])
                   for k, vv in e3["velocity_ramp_release"].items()},
    capacity_estimate=dict(
        plan_ja="物理の時刻 −10〜+3 s：接近 6 s を 7.5 Hz、砕波と崩壊 7 s を 30 Hz（E3 の定数から計算）",
        layers=layers, file_MiB=r(layers * LAYER_B / 2 ** 20, 1),
        unity_readable_MiB_est=r(layers * UNITY_PER_LAYER_MIB, 1),
        unity_readable_subrect58_MiB_est=r(layers * UNITY_PER_LAYER_MIB * 0.58, 1),
        limit_MiB=512),
)

# ---------------------------------------------------------------- E5（美術の誘導を切った版の初見積もり、主断面）
e5 = J("e5_artoff.json")
z5 = np.load(os.path.join(F, "e5_artoff_section.npz"))
inside = int((z5["lip"][:, 1] < np.interp(z5["lip"][:, 0], z5["body_a"], z5["body_y"])).sum())
E5 = dict(artoff_tip_a_y_m=[r(e5["artoff_tip"]["a"], 2), r(e5["artoff_tip"]["y"], 2)],
          kstar_tip_a_y_m=[r(e5["kstar_tip"]["a"], 2), r(e5["kstar_tip"]["y"], 2)],
          lip_upper_chamfer_rms_max_m=r(e5["lip_upper_chamfer_rms_max_m"], 2),
          upper_outline_chamfer_rms_max_m=r(e5["upper_outline_chamfer_rms_max_m"], 2),
          body_footprint_m=r(e5["artoff_body_footprint_m"], 1), back_slope_deg=r(e5["artoff_back_slope_deg"], 1),
          kstar_back_slope_deg=r(e5["kstar_back_slope_deg"], 1),
          lip_upper_points=int(len(z5["lip"])), lip_upper_points_inside_body=inside)

# ---------------------------------------------------------------- E6（t* の原画視点の周りの海）
e6 = J("e6_painting_sea.json")
E6 = dict(frac_hero_sheet=r(e6["frac_hero"], 3), frac_visible_surrounding_sea=r(e6["frac_visible_surrounding_sea"], 4),
          visible_sea_depth_m_min_p50_max=r(e6["visible_surrounding_sea_depth_m"], 1),
          visible_sea_world_XZ_bbox_m=r(e6["visible_surrounding_sea_world_XZ_bbox"], 1),
          carrier_group=dict(eta_min_m=r(e6["carrier_group"]["eta_min_m"], 2), eta_max_m=r(e6["carrier_group"]["eta_max_m"], 2),
                             dpx_max=r(e6["carrier_group"]["dpx_max"], 1), frac_px_over_0p5=r(e6["carrier_group"]["frac_px_over_0p5"], 3)),
          carrier_mono=dict(eta_min_m=r(e6["carrier_mono"]["eta_min_m"], 2), eta_max_m=r(e6["carrier_mono"]["eta_max_m"], 2),
                            dpx_max=r(e6["carrier_mono"]["dpx_max"], 1)),
          swell_Hs5_dpx_p50=r(e6["swell_Hs5_rms1p25_dpx"]["p50"], 1),
          eta_for_0p5px_m_min_p50=[r(e6["eta_for_0p5px_m"]["min"], 4), r(e6["eta_for_0p5px_m"]["p50"], 4)],
          trough_behind_main_line=dict(world_XZ_m=r(e6["trough_behind_main_line"]["world_XZ"], 1),
                                       display_px=r(e6["trough_behind_main_line"]["display_px"], 0),
                                       in_painting_frame=e6["trough_behind_main_line"]["in_painting_frame"]),
          gate_ja="見える周りの海の像のずれ ≤ 0.5 px かつ傾き ≤ 0.5°（t*）。物理の値は満たさない → 美術の誘導 ds_sea_calm_painting・ds_swell_calm")

# ---------------------------------------------------------------- 時間曲線の関門（P16）
tw = J("timewarp_v2.json")
TW = {}
for k in ("default_slowmo", "alt_realtime_hardfreeze", "old_v1"):
    v = tw["tables"][k]
    TW[k] = dict(gate_max_upward_mps2=r(v["gate_max_upward_mps2"], 3), gate_rows_failing=v["gate_rows_failing"],
                 main_fall_on_screen_s=r(v["main_fall_on_screen_s"], 3), main_fall_physical_s=r(v["main_fall_physical_s"], 3),
                 events=v["events"], post=v["post"])
TW["default_slowmo"]["segments"] = tw["tables"]["default_slowmo"].get("segments")
TW["old_warp_new_tips"] = tw["old_warp_new_tips"]
TW["old_warp_old_tips"] = tw["old_warp_old_tips"]
TW["tip_apex_new"] = tw["tip_apex_new"]
TW["candidates"] = [dict(r0=c["r0"], ramp_s=c["d1"], freeze_s=c["tf"], max_upward_mps2=r(c["max_upward_mps2"], 2),
                         rows_failing=c["rows_failing"], main_fall_on_screen_s=r(c["main_fall_on_screen_s"], 2)) for c in tw["candidates"]]
TW["post_tstar"] = dict(tip_over_seat_height_m=r(tw["post_tstar"]["tip_over_seat_height_m"], 2),
                        impact_ground_a_p50_m=r(tw["post_tstar"]["impact_ground_a_p50_m"], 2),
                        events_tau_s={k: r(v, 3) for k, v in tw["post_tstar"]["events_tau"].items()})

# ---------------------------------------------------------------- 美術優先30 の診断（再生される keypose、関門 P1〜P10 の今の値）
D = J("diag_measure.json", DP.OUT_DIAG)
ms = D["main_series"]; gs = D["global_series"]; kin = D["kinematics_240hz_main_row"]
t = np.array(ms["t"], float)
arr = lambda x: np.array([np.nan if v is None else v for v in x], float)
ca = arr(ms["crest_a"]); phi = arr(ms["phi_max"]); ta = arr(ms["tip_a"]); ty = arr(ms["tip_y"])
at = lambda a, tt: float(a[int(np.argmin(np.abs(t - tt)))])
gt = np.array(gs["t"], float); vol = arr(gs["volume_above_swl_m3"]); p95 = arr(gs["speed_p95_body_mps"])
iv = int(np.where(phi >= 90)[0][0])
sp = np.hypot(np.gradient(ta, t), np.gradient(ty, t))
kt = np.array(kin["t"], float); tv = np.array(kin["tip_v"], float); cs = np.array(kin["col_speed"], float)
ia = int(np.nanargmax(np.where(t <= 12, ty, np.nan)))
i1 = int(np.argmin(np.abs(kt - t[ia]))); i2 = int(np.argmin(np.abs(kt - 12.0))); i11 = int(np.argmin(np.abs(kt - 11.0)))
cols = kin["cols"]
wt = np.array(D["white"]["t"], float); wf = np.array(D["white"]["fraction"], float)
m31 = json.load(open(os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "31", "metrics.json"), encoding="utf-8"))


def find_key(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                return v
            x = find_key(v, key)
            if x is not None:
                return x
    elif isinstance(o, list):
        for v in o:
            x = find_key(v, key)
            if x is not None:
                return x
    return None


rs = D["row_sync"]
DIAG = dict(
    what_ja="美術優先30 の再生される 16 ビットの keypose（Unity と同じ非一様 Catmull-Rom）を主断面・全行で測った値（diag_measure.py）。新しい動きが通るべき関門 P1〜P10 に対する今の値",
    P1_crest_mean_speed_3_to_12s_mps=r((at(ca, 12) - at(ca, 3)) / 9.0, 3),
    P1_crest_speed_9_to_12s_mps=r((at(ca, 12) - at(ca, 9)) / 3.0, 3),
    P1_P12_crest_back_travel_m=r(float(np.nanmax(np.where(t <= 12, ca, np.nan))) - at(ca, 12), 3),
    P2_min_surface_y_m=r(float(np.nanmin(arr(gs["ymin"]))), 5),
    P3_volume_above_swl_max_m3=r(float(np.nanmax(vol)), 1), P3_volume_max_t_s=r(float(gt[int(np.nanargmax(vol))]), 3),
    P3_volume_at_tstar_m3=r(float(vol[int(np.argmin(np.abs(gt - 12)))]), 1),
    P3_volume_loss_frac=r(1 - float(vol[int(np.argmin(np.abs(gt - 12)))]) / float(np.nanmax(vol)), 3),
    P4_tip_apex_t_s=r(float(t[ia]), 3), P4_tip_apex_y_m=r(float(ty[ia]), 3),
    P4_tip_mean_vertical_accel_apex_to_tstar_mps2=r((tv[i2, 1] - tv[i1, 1]) / (kt[i2] - kt[i1]), 3),
    P5_tip_speed_max_mps=r(float(np.nanmax(sp)), 2), P5_tip_speed_max_t_s=r(float(t[int(np.nanargmax(sp))]), 3),
    P6_lip_speed_at_11s_by_col_mps={str(c): r(v, 3) for c, v in zip(cols, cs[i11])},
    P6_mid_over_root=r(cs[i11][cols.index(130)] / cs[i11][cols.index(90)], 3),
    P6_root_over_tip=r(cs[i11][cols.index(90)] / cs[i11][cols.index(200)], 3),
    P7_face_vertical_t_s=r(float(t[iv]), 3), P7_vertical_to_tstar_s=r(12.0 - float(t[iv]), 3),
    P7_curled_rows_vertical_t_range_s=[r(rs["t_phi90_curl"]["min"], 3), r(rs["t_phi90_curl"]["max"], 3)],
    P8_body_speed_p95_at_11p8s_over_max=r(float(p95[int(np.argmin(np.abs(gt - 11.8)))]) / float(np.nanmax(p95)), 3),
    P9_first_white_uv_s_step31=r(find_key(m31, "white_first_uv_s"), 3),
    P9_white_fraction_at_face_vertical=r(float(wf[int(np.argmin(np.abs(wt - t[iv])))]), 3),
    P10_t50_std_across_rows_s=r(rs["t50"]["std"], 6), P10_t50_s=r(rs["t50"]["min"], 3),
    kstar_volume_above_swl_m3=r(D["kstar"]["volume_above_swl_m3"], 1),
    keypose_pos_sha256_prefix="3d652c89",
)

# ---------------------------------------------------------------- metrics.json
cond_path = os.path.join(DP.EVID, "ds26_conditions.json")
metrics = dict(
    schema="GreatWave.DS26.metrics/1",
    number="設計26",
    status_ja="初回提出（文書と numpy の実験のみ・Unity と HMD なし）。条件の既定値は利用者未回答（Design_26_ja.md 第10節の D30〜D37）。",
    evidence_kind_ja="numpy の実験（K* と美術優先30 の keypose を読むだけ）と、PIL・OpenCV の図。Unity・Houdini・HMD の結果ではない。実験は成果物ではなく、既定値の実行可能性の確認。",
    backlog_ja="直接の項目なし（段階5 の出口条件。計画 §2.1）",
    conditions=dict(path=rel(cond_path), sha256=sha(cond_path)),
    kstar_rows_sha256=DP.SHA256["kstar_a45_rows.npz"],
    E1_old_rule=E1, E4_strip_rule=E4, E4b_mesh=E4b, E2_physical_body=E2, E3_keypose=E3, E5_artoff=E5,
    E6_painting_sea=E6, P16_time_warp=TW, diag_af30=DIAG,
    notes_ja=[
        "目安の範囲（u/c0 0.6〜1.3、w/√(gH) −0.2〜0.8）は自前で、t* の 0.15 s 前より後に放出される点は評価しない。",
        "E1・E4 は行ごとの 2 次元。E4b だけが行の間の三角形を見るが、本体は代理。E5 は主断面だけの初見積もり。",
        "E2 の (c) と E2c は、利用者の解算から作った断面の npz（リポジトリ外・本機のみ）が要る。この実行で計算したかは run.json の sim_npz_used。",
    ],
)
with open(os.path.join(DP.outdir(DP.EVID), "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1)
    f.write("\n")

# ---------------------------------------------------------------- run.json


def pyver(v):
    code = ("import sys, numpy; s = sys.version.split()[0] + ' numpy ' + numpy.__version__\n"
            "try:\n import cv2; s += ' opencv ' + cv2.__version__\nexcept Exception: pass\n"
            "try:\n import PIL; s += ' pillow ' + PIL.__version__\nexcept Exception: pass\nprint(s)")
    try:
        return subprocess.run(["py", v, "-c", code], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as ex:  # noqa: BLE001
        return "unknown (%s)" % ex


scripts = sorted(glob.glob(os.path.join(REPO, "Tools", "GWWaveGen", "ds26", "*.py")) +
                 glob.glob(os.path.join(REPO, "Tools", "GWWaveGen", "ds26", "*.ps1")))
inputs = [os.path.join(DP.KSTAR_DIR, n) for n in ("kstar_a45_rows.npz", "kstar_a45_meta.json")]
inputs += [os.path.join(DP.KEYPOSE_DIR, n) for n in ("af30_keypose.json", "af30_pos_rgba16.bin")]
inputs += [os.path.join(REPO, "Unity", "Build", "ArtFirst", "31", "white", "af31_twhite_r32f.bin"),
           os.path.join(REPO, "Tools", "GWWaveGen", "af30_rig.json"), os.path.join(REPO, "Tools", "GWWaveGen", "af30_formation.py"),
           os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "31", "metrics.json"),
           os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "30", "af30_painting_formation.png"),
           os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "30", "af30_seat_formation_waveonly.png"),
           os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "31", "af31_painting_white.png"), cond_path]
outs = sorted(p for p in glob.glob(os.path.join(DP.EVID, "*")) if os.path.basename(p) not in ("run.json", "ds26_conditions.json"))
nc = sorted(p for p in glob.glob(os.path.join(DP.OUT_ROOT, "**", "*"), recursive=True) if os.path.isfile(p))
finished = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
run = dict(
    schema="GreatWave.DS26.run/1",
    number="設計26",
    started_utc=STARTED,
    finished_utc=finished.isoformat(),
    commands=[
        "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds26/run_ds26.ps1 -SimNpz <profiles_main_lateral.npz（リポジトリ外・本機のみ）> -PaperPdf <McAllister 2019 の PDF（本機）>",
        "py -3.12 -B Tools/GWWaveGen/ds26/e1_inverse_ballistic.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/e1_inverse_ballistic.py restrict",
        "py -3.12 -B Tools/GWWaveGen/ds26/e2_residual.py --sim <npz>（npz が無ければ --skip-sim）",
        "py -3.12 -B Tools/GWWaveGen/ds26/e2c_sim_window.py --sim <npz>",
        "py -3.12 -B Tools/GWWaveGen/ds26/e3_keypose_sampling.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/e4_prerelease_ramp.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/e4b_mesh.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/e4c_default_stats.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/e5_artoff.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/e6_painting_sea.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/tw_gate.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/timewarp_table.py",
        "py -3.10 -B Tools/GWWaveGen/ds26/fig_e1.py",
        "py -3.10 -B Tools/GWWaveGen/ds26/fig_cause.py",
        "py -3.10 -B Tools/GWWaveGen/ds26/fig_paper_panels.py --pdf <PDF>",
        "py -3.10 -B Tools/GWWaveGen/ds26/diag_measure.py",
        "py -3.10 -B Tools/GWWaveGen/ds26/diag_figs.py",
        "py -3.10 -B Tools/GWWaveGen/ds26/diag_cues.py",
        "py -3.12 -B Tools/GWWaveGen/ds26/ds26_evidence.py --sim-used --pdf-used --started-utc <ISO>",
    ],
    tools={"py -3.12": pyver("-3.12"), "py -3.10": pyver("-3.10"), "os": platform.platform()},
    sim_npz_used=SIM_USED,
    paper_pdf_used=PDF_USED,
    external_inputs_ja=dict(
        sim_npz=dict(name="profiles_main_lateral.npz", sha256=DP.SHA256["profiles_main_lateral.npz"],
                     where_ja="リポジトリ外（本機のみ）。利用者の Houdini 解算から作った主断面と横断面の水面の線。形なので入れない"),
        user_sim_files=dict(**{"1.abc": "e945d8a6072b92be7cbab6158b1f28af808a2791513c65b7ebca54d0cb977220",
                               "1.fbx": "b63e2ebe7c149416f90da7f48ac83793d5dc756cf2cec279b6dbe7ff4cf1cc7b"},
                            note_ja="出典としてファイル名と SHA-256 だけを書く。この実行では開いていない（測定済みの数値と上の npz だけを使う）"),
        paper_pdf=dict(citation="McAllister, Draycott, Adcock, Taylor & van den Bremer (2019) J. Fluid Mech. 860, 767-786, doi:10.1017/jfm.2018.886, CC BY 4.0",
                       sha256=DP.SHA256["paper_pdf"],
                       extracted_objects=[465, 466, 467, 468, 476, 477, 478, 479, 480, 481]),
    ),
    inputs_sha256={rel(p): sha(p) for p in scripts + inputs if os.path.isfile(p)},
    outputs_sha256={rel(p): sha(p) for p in outs},
    not_committed_sha256={rel(p): sha(p) for p in nc},
    not_committed_ja="Unity/Build/Design/26/ は Git 対象外（/Unity/Build/）。feas/ は実験の出力（JSON・CSV・npz）、diag/ は美術優先30 の測定、paper/ は PDF から取り出した Fig. 4・5 の埋め込み JPEG。同じコマンドで作り直せる（E2 の (c)・E2c だけはリポジトリ外の npz が要る）。",
)
if STARTED:
    try:
        st = datetime.datetime.fromisoformat(STARTED)
        run["elapsed_s"] = round((finished - st).total_seconds(), 1)
    except ValueError:
        pass
with open(os.path.join(DP.EVID, "run.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(run, f, ensure_ascii=False, indent=1)
    f.write("\n")
print("metrics.json・run.json を書きました：", rel(DP.EVID))
