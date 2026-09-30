# -*- coding: utf-8 -*-
"""設計44：Unity の記録（ds44_steps.csv 120 Hz・ds44_frames.jsonl 30 fps）から、最小の受入の数値を数える（numpy）。

操船の部品（C#）の内部の値（LastSurge など）は使わず、記録した剛体の位置・四元数・速度から、向き・速さ・首振り・範囲の距離を数え直す。
範囲の距離は ds44_model.Range（numpy で別に書いた符号付き距離）で求める。
  1. 入力 → 加速と抵抗：筋書きの区間ごとの船首方向の速さ・首振りの速さの変化。入力なしの区間の減速を抵抗の式と比べる。
  2. 範囲の外：縁へ向けて前進を押し続ける区間の最大の d（外が正）、押し戻しの加速度の最大、離した後の内向きの戻り。
  3. 引き継ぎ：120 Hz の 1 段ごとの向き・速さの変化（跳び）を、操船の区間の同じ量と、物理の上限（首振り・加速度）から決めた閾値と比べる。
  4. 着いた時：t* の位置・向き・速さのずれ。軌道の追従のずれ。
  5. 記録のみ：座席の目が水の上か、上下の加速度（設計45 へ）。
"""
import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds44_model as M  # noqa: E402

OUT = M.OUT
UNITY = os.path.join(OUT, "unity")


def load_steps(path=os.path.join(UNITY, "ds44_steps.csv")):
    with open(path, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        rows = list(rd)
    num = {}
    for k in rows[0].keys():
        if k in ("mode", "playState", "src"):
            num[k] = np.array([r[k] for r in rows])
        else:
            num[k] = np.array([float(r[k]) if r[k] not in ("", "null") else np.nan for r in rows])
    return num


def load_frames(path=os.path.join(UNITY, "ds44_frames.jsonl")):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def heading_from_quat(qx, qy, qz, qw):
    # forward = q * (0, 0, 1)
    fx = 2 * (qx * qz + qw * qy)
    fz = 1 - 2 * (qx * qx + qy * qy)
    return np.degrees(np.arctan2(fx, fz))


def measure(P=None):
    P = P or M.load_params()
    fr = M.Frame(P)
    rng = M.Range(P, fr)
    S = load_steps()
    F = load_frames()
    rep = json.load(open(os.path.join(UNITY, "ds44_unity_report.json"), encoding="utf-8"))
    dt = 1.0 / 120.0
    s = S["s"]
    psi = np.degrees(np.unwrap(np.radians(heading_from_quat(S["qx"], S["qy"], S["qz"], S["qw"]))))
    vx, vz = S["vx"], S["vz"]
    spd = np.hypot(vx, vz)
    fx, fz = np.sin(np.radians(psi)), np.cos(np.radians(psi))
    surge = vx * fx + vz * fz
    sway = vx * fz - vz * fx
    yawrate = np.gradient(psi, s)
    d = np.array([rng.sdf((x, z)) for x, z in zip(S["x"], S["z"])])
    mode = S["mode"]
    steer = mode == "Steering"
    ih = int(np.argmax(~steer)) if (~steer).any() else None
    s_h = float(rep["handoverS"])
    s_f = float(rep["formationStartS"])
    t_star_s = s_f + P["traj"]["formationS"]
    out = {"handover_index": ih, "handover_s": s_h, "formation_start_s": s_f, "t_star_s": t_star_s}

    segcol = S["seg"]

    def seg_mask(a, b):
        # 記録の seg（段の始めに入れた筋書きの区間の番号）で選ぶ
        idx = [i for i, g in enumerate(P["test"]["segments"]) if abs(g["s0"] - a) < 1e-6 and abs(g["s1"] - b) < 1e-6]
        if idx:
            return segcol == idx[0]
        return (s > a + 1e-9) & (s <= b + 1e-9)

    def at(t):
        return int(np.argmin(np.abs(s - t)))

    # ---- 1. 入力 → 加速と抵抗
    segs = P["test"]["segments"]
    seg_rows = []
    for g in segs:
        m = seg_mask(g["s0"], g["s1"])
        i0, i1 = at(g["s0"]), at(g["s1"])
        seg_rows.append(dict(label=g["labelJa"], s0=g["s0"], s1=g["s1"], device=g["device"],
                             surge_start=float(surge[i0]), surge_end=float(surge[i1]), surge_max=float(surge[m].max()), surge_min=float(surge[m].min()),
                             yawrate_mean=float(yawrate[m].mean()), yawrate_absmax=float(np.abs(yawrate[m]).max()), heading_change_deg=float(psi[i1] - psi[i0]),
                             thr_in_mean=float(np.nanmean(S["thrIn"][m])), turn_in_mean=float(np.nanmean(S["turnIn"][m])), stop_in=float(np.nanmax(S["stopIn"][m])),
                             src=sorted(set(S["src"][m].tolist()))))
    out["segments"] = seg_rows
    dyn = P["dyn"]
    # 加速：W の区間（最初の区間）
    g0 = segs[0]
    m0 = seg_mask(g0["s0"], g0["s1"])
    on = np.where(m0 & (surge > 0.05))[0]
    acc = dict(v_end=float(surge[at(g0["s1"])]), v_end_ratio_to_vmax=float(surge[at(g0["s1"])] / dyn["vMaxFwd"]),
               onset_s_after_press=float(s[on[0]] - g0["s0"]) if len(on) else None,
               accel_first_2s_mps2=float((surge[at(g0["s0"] + 2)] - surge[at(g0["s0"])]) / 2.0))
    acc["pass_"] = bool(acc["v_end_ratio_to_vmax"] >= 0.8 and acc["onset_s_after_press"] is not None and acc["onset_s_after_press"] <= 0.5)
    # 抵抗：入力なしの区間（2 番目）
    g1 = segs[1]
    m1 = seg_mask(g1["s0"], g1["s1"]) & (s > g1["s0"] + 1.0)      # 入力の遅れ（0.4 s）の後
    du = np.gradient(surge, s)
    pred = -(dyn["dragLinPerS"] * surge + dyn["dragQuadPerM"] * surge * np.abs(surge))
    drag = dict(surge_start=float(surge[at(g1["s0"])]), surge_end=float(surge[at(g1["s1"])]),
                decel_measured_mean=float(du[m1].mean()), decel_model_mean=float(pred[m1].mean()),
                ratio_measured_to_model=float(du[m1].mean() / pred[m1].mean()),
                rms_diff_mps2=float(np.sqrt(np.mean((du[m1] - pred[m1]) ** 2))))
    drag["pass_"] = bool(drag["surge_end"] < drag["surge_start"] and 0.7 <= drag["ratio_measured_to_model"] <= 1.3)
    # 旋回・停止・後進
    by = {g["labelJa"]: r for g, r in zip(segs, seg_rows)}
    tr = seg_rows[2]
    turn_right = dict(yawrate_absmax=tr["yawrate_absmax"], heading_change_deg=tr["heading_change_deg"], pass_=bool(tr["heading_change_deg"] > 20 and tr["yawrate_mean"] > 0))
    st = seg_rows[3]
    m3 = seg_mask(segs[3]["s0"], segs[3]["s1"])
    stopped = np.where(m3 & (np.abs(surge) < 0.05))[0]
    stop = dict(surge_start=st["surge_start"], surge_end=st["surge_end"], time_to_below_0p05=float(s[stopped[0]] - segs[3]["s0"]) if len(stopped) else None)
    stop["pass_"] = bool(stop["time_to_below_0p05"] is not None and abs(st["surge_end"]) < 0.05)
    tl = seg_rows[5]
    turn_left_rest = dict(yawrate_mean=tl["yawrate_mean"], heading_change_deg=tl["heading_change_deg"], surge_absmax=float(max(abs(tl["surge_max"]), abs(tl["surge_min"]))),
                          pass_=bool(tl["heading_change_deg"] < -5 and tl["yawrate_mean"] < 0))
    rv = seg_rows[8]
    reverse = dict(surge_start=rv["surge_start"], surge_end=rv["surge_end"], surge_min=rv["surge_min"], pass_=bool(rv["surge_end"] < rv["surge_start"] and rv["surge_min"] < 0))
    out["input_to_motion"] = dict(accelerate=acc, drag=drag, turn_right=turn_right, stop=stop, turn_left_at_rest=turn_left_rest, reverse=reverse,
                                  pass_=bool(acc["pass_"] and drag["pass_"] and turn_right["pass_"] and stop["pass_"] and turn_left_rest["pass_"] and reverse["pass_"]))

    # ---- 2. 範囲の外
    gp = segs[6]
    mp = seg_mask(gp["s0"], gp["s1"])
    mrel = seg_mask(segs[7]["s0"], segs[7]["s1"])
    n_in = np.array([-rng.grad((x, z)) for x, z in zip(S["x"], S["z"])])
    v_out = -(vx * n_in[:, 0] + vz * n_in[:, 1])      # 外向きの速さ
    band_rows = np.where(mp & (d > -P["range"]["bandM"]))[0]
    rr = dict(d_max_whole_steering=float(d[steer].max()), d_max_push_segment=float(d[mp].max()), s_at_d_max=float(s[mp][np.argmax(d[mp])]),
              outward_speed_at_band_entry=float(v_out[band_rows[0]]) if len(band_rows) else None,
              outward_speed_end_of_push_segment=float(v_out[at(gp["s1"])]),
              push_accel_max_mps2=float(np.nanmax(S["pushA"][steer])),
              d_release_start=float(d[at(segs[7]["s0"])]), d_release_end=float(d[at(segs[7]["s1"])]),
              inward_move_after_release_m=float(d[at(segs[7]["s0"])] - d[at(segs[7]["s1"])]),
              time_in_band_s=float(((d > -P["range"]["bandM"]) & steer).sum() * dt))
    rr["pass_"] = bool(rr["d_max_whole_steering"] <= 0.0 and rr["inward_move_after_release_m"] > 0.3 and rr["push_accel_max_mps2"] <= 1.0 and rr["outward_speed_end_of_push_segment"] <= 0.05)
    rr["criterion_ja"] = "縁へ向けた前進を押し続けても縁（d = 0）を越えない、区間の終わりで外向きの速さ ≤ 0.05 m/s、離した後に 0.3 m 以上内へ戻る、押し戻しの加速度 ≤ 1 m/s²（快適性の目安。調整値）"
    out["out_of_range"] = rr

    # ---- 3. 引き継ぎ
    k = np.arange(len(s))
    dpsi = np.diff(psi)                   # 1 段の向きの変化（度）
    dv = np.diff(spd)                     # 1 段の速さの変化（m/s）
    ddpsi = np.abs(np.diff(dpsi))         # 首振りの速さの変化（度/段²）
    ddv = np.abs(np.diff(dv))
    steer_idx = np.where(steer[1:])[0]
    st_ok = steer_idx[(steer_idx > 2) & (steer_idx < ih - 2)]
    ymax = max(dyn["yawRateMaxDeg"], P["traj"]["yawRateMaxDeg"])
    thr_dpsi = 1.5 * ymax * dt            # 0.15°/段（12°/s の 1.5 倍）
    thr_dv = 1.5 * 1.0 * dt               # 1 m/s² の 1.5 倍
    win = np.where((s >= s_h - 1.0) & (s <= s_h + 1.0))[0]
    win = win[(win >= 1) & (win < len(s) - 1)]
    jp = dict(
        s_last_steering=float(s[ih - 1]), s_first_trajectory=float(s[ih]),
        heading_before_deg=float(psi[ih - 1]), heading_after_deg=float(psi[ih]), heading_step_deg=float(dpsi[ih - 1]),
        heading_step_prev_deg=float(dpsi[ih - 2]), heading_step_next_deg=float(dpsi[ih]),
        yawrate_change_at_handover_degps=float((dpsi[ih - 1] - dpsi[ih - 2]) / dt),
        speed_before=float(spd[ih - 1]), speed_after=float(spd[ih]), speed_step=float(dv[ih - 1]), speed_step_prev=float(dv[ih - 2]), speed_step_next=float(dv[ih]),
        accel_change_at_handover_mps2=float((dv[ih - 1] - dv[ih - 2]) / dt),
        steering_p99_abs_heading_step_deg=float(np.percentile(np.abs(dpsi[st_ok]), 99)), steering_max_abs_heading_step_deg=float(np.abs(dpsi[st_ok]).max()),
        steering_p99_abs_speed_step=float(np.percentile(np.abs(dv[st_ok]), 99)), steering_max_abs_speed_step=float(np.abs(dv[st_ok]).max()),
        steering_max_yawrate_change_degps2=float(ddpsi[st_ok[:-1]].max() / dt / dt),
        window_max_abs_heading_step_deg=float(np.abs(dpsi[win - 1]).max()), window_max_abs_speed_step=float(np.abs(dv[win - 1]).max()),
        threshold_heading_step_deg=thr_dpsi, threshold_speed_step=thr_dv,
    )
    qx, qy, qz, qw = S["qx"], S["qy"], S["qz"], S["qw"]
    tilt = np.degrees(np.arccos(np.clip(1 - 2 * (qx * qx + qz * qz), -1, 1)))
    lead_rows = np.where((~steer[1:]) & (s[1:] < s_f))[0]
    form_rows = np.where((~steer[1:]) & (s[1:] >= s_f))[0]
    jp["jumps_heading_window"] = int((np.abs(dpsi[win - 1]) > thr_dpsi).sum())
    jp["jumps_speed_window"] = int((np.abs(dv[win - 1]) > thr_dv).sum())
    jp["jumps_heading_lead"] = int((np.abs(dpsi[lead_rows]) > thr_dpsi).sum())
    jp["jumps_speed_lead"] = int((np.abs(dv[lead_rows]) > thr_dv).sum())
    jp["lead_max_abs_heading_step_deg"] = float(np.abs(dpsi[lead_rows]).max())
    jp["lead_max_abs_speed_step"] = float(np.abs(dv[lead_rows]).max())
    jp["formation_record"] = dict(
        heading_steps_over_threshold=int((np.abs(dpsi[form_rows]) > thr_dpsi).sum()), speed_steps_over_threshold=int((np.abs(dv[form_rows]) > thr_dv).sum()),
        heading_steps_over_threshold_tilt_lt20=int(((np.abs(dpsi[form_rows]) > thr_dpsi) & (tilt[1:][form_rows] < 20)).sum()),
        tilt_max_deg=float(tilt[form_rows + 1].max()), s_tilt_max=float(s[form_rows + 1][np.argmax(tilt[form_rows + 1])]),
        note_ja="形成の区間（単発再生の t 0〜12 s と保持）。波が船を持ち上げて大きく傾ける（設計43 の記録と同じ所）。傾きが大きい時の水平の船首の向きは定まりにくい。受入の判定には入れず、設計45・仕上げ43 へ送る")
    jp["heading_step_ratio_to_steering_max"] = float(abs(jp["heading_step_deg"]) / max(jp["steering_max_abs_heading_step_deg"], 1e-9))
    jp["speed_step_ratio_to_steering_max"] = float(abs(jp["speed_step"]) / max(jp["steering_max_abs_speed_step"], 1e-9))
    # 30 fps（コマ）で見た時
    fr_s = np.array([f["s"] for f in F])
    fr_psi = np.interp(fr_s, s, psi)
    fr_spd = np.interp(fr_s, s, spd)
    nh = int(np.argmin(np.abs(fr_s - s_h)))
    fr_dpsi = np.diff(fr_psi)
    fr_dv = np.diff(fr_spd)
    jp["frame30_heading_steps_around_deg"] = [float(x) for x in fr_dpsi[nh - 3:nh + 3]]
    jp["frame30_speed_steps_around"] = [float(x) for x in fr_dv[nh - 3:nh + 3]]
    jp["pass_"] = bool(jp["jumps_heading_window"] == 0 and jp["jumps_speed_window"] == 0 and jp["jumps_heading_lead"] == 0 and jp["jumps_speed_lead"] == 0)
    jp["criterion_ja"] = ("跳び = 1 段（1/120 s）の変化が物理の上限の 1.5 倍を超えること（向き：12°/s × 1.5 × dt = %.3f°、速さ：1 m/s² × 1.5 × dt = %.4f m/s）。"
                          "引き継ぎの前後 ±1 s と、引き継ぎから形成の始まりまで（軌道の前半、水は t = 0 のコマ）で 0 回なら合格（91・92 を使える水準で）。形成の区間は記録のみ" % (thr_dpsi, thr_dv))
    out["handover"] = jp

    # ---- 4. 着いた時と追従
    ist = at(t_star_s)
    tgt = np.array([fr.o[0], fr.o[1]])
    arr = dict(s=float(s[ist]), pos_err_m=float(np.hypot(S["x"][ist] - tgt[0], S["z"][ist] - tgt[1])), yaw_err_deg=float(M.wrap_deg(psi[ist] - fr.yaw)),
               speed=float(spd[ist]), speed_1s_before=float(spd[at(t_star_s - 1)]),
               hold_pos_err_max_m=float(np.hypot(S["x"][s >= t_star_s] - tgt[0], S["z"][s >= t_star_s] - tgt[1]).max()),
               hold_yaw_err_absmax_deg=float(np.abs([M.wrap_deg(a - fr.yaw) for a in psi[s >= t_star_s]]).max()))
    arr["pass_"] = bool(arr["pos_err_m"] <= 0.05 and abs(arr["yaw_err_deg"]) <= 0.5 and arr["speed"] <= 0.05)
    arr["criterion_ja"] = "t* で原画の水平の位置から ≤ 5 cm、向き ≤ 0.5°、速さ ≤ 0.05 m/s（進行役が決めた目安）"
    out["arrival"] = arr
    tm = ~steer
    ex = S["tgtX"][tm] - S["x"][tm]
    ez = S["tgtZ"][tm] - S["z"][tm]
    out["tracking"] = dict(pos_err_max_m=float(np.nanmax(np.hypot(ex, ez))), yaw_err_absmax_deg=float(np.nanmax(np.abs([M.wrap_deg(a) for a in (S["tgtYaw"][tm] - psi[tm])]))),
                           note_ja="目標は段の始めの値、実際は段の後の値なので、1 段分の進み（速さ × 1/120 s）を含む")
    tr_spd = spd[tm & (s <= t_star_s)]
    tr_yr = yawrate[tm & (s <= t_star_s)]
    out["trajectory"] = dict(L_m=rep["trajL"], T_s=rep["trajT"], lead_s=rep["trajLead"], arc_deg=rep["trajArcDeg"], arc_R_m=rep["trajArcR"], v0=rep["trajV0"], vcap=rep["trajVCap"],
                             beta0_deg=rep["trajBeta0"], c_rate_degps=rep["trajCRate"], speed_max=float(tr_spd.max()), yawrate_absmax_degps=float(np.abs(tr_yr).max()),
                             u_max_painting_frame=float(max(fr.to_uv((x, z))[0] for x, z in zip(S["x"][tm], S["z"][tm]))))

    # 固定の軌道の作り方の照合：同じ引き継ぎの状態から numpy 版（ds44_model.Trajectory）で作り直し、C# の結果と比べる
    p0 = np.array([rep["handoverPos"][0], rep["handoverPos"][2]])
    v0 = np.array([rep["handoverVel"][0], rep["handoverVel"][2]])
    trp = M.Trajectory(P, p0, v0, rep["handoverYawDeg"], rep["handoverYawRateDegPs"], 0.0, fr)
    ux, uz = np.array(rep["trajPathX"]), np.array(rep["trajPathZ"])
    dev = [float(np.min(np.hypot(trp.X[:, 0] - x, trp.X[:, 1] - z))) for x, z in zip(ux, uz)]
    ts = np.linspace(0, trp.T, 200)
    act = []
    for t in ts:
        i = at(s_h + t)
        e = trp.eval(t)
        act.append(float(np.hypot(S["x"][i] - e[0][0], S["z"][i] - e[0][1])))
    out["trajectory_crosscheck"] = dict(numpy_L=trp.L, numpy_T=trp.T, numpy_lead=trp.lead, numpy_arc_deg=trp.arc_deg, unity_L=rep["trajL"], unity_T=rep["trajT"], unity_lead=rep["trajLead"],
                                        unity_path_vs_numpy_path_max_m=max(dev), actual_vs_numpy_eval_max_m=max(act),
                                        note_ja="引き継ぎの状態（Unity の記録）から numpy 版で軌道を作り直し、C# の道（400 点）と実際の位置（200 時刻）を比べた")

    # ---- 5. 記録のみ
    eye_margin = []
    in_water = 0
    for f in F:
        ey = f["eye"][1]
        hits = sorted(f["eyeHits"])
        above = sum(1 for h in hits if h > ey)
        if above % 2 == 1:
            in_water += 1
        below = [h for h in hits if h <= ey]
        eye_margin.append(ey - below[-1] if below else np.nan)
    eye_margin = np.array(eye_margin)
    out["seat_eye"] = dict(frames=len(F), in_water_frames=in_water, margin_min_m=float(np.nanmin(eye_margin)), margin_min_s=float(fr_s[np.nanargmin(eye_margin)]))
    ay = np.gradient(S["vy"], s)
    k30 = np.convolve(ay, np.ones(4) / 4, mode="same")
    out["heave_accel"] = dict(steering_absmax_mps2=float(np.abs(k30[steer]).max()), lead_absmax_mps2=float(np.abs(k30[(~steer) & (s < s_f)]).max()) if ((~steer) & (s < s_f)).any() else None,
                              formation_absmax_mps2=float(np.abs(k30[(s >= s_f) & (s <= t_star_s)]).max()), note_ja="上下の加速度（4 段の移動平均）。設計45 の快適性へ（記録のみ）")
    out["wet_zero_steps"] = int((S["wet"] == 0).sum())
    out["series"] = dict(s=s, psi=psi, spd=spd, surge=surge, sway=sway, yawrate=yawrate, d=d, steer=steer, tilt=tilt)
    return out, S, F, rep


if __name__ == "__main__":
    o, S, F, rep = measure()
    ser = o.pop("series")
    print(json.dumps(o, ensure_ascii=False, indent=1)[:9000])
