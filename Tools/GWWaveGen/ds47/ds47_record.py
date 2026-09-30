# -*- coding: utf-8 -*-
# 設計47 の記録の道具（導入 → 接近 → 形成 → t* の保持 → 余韻）。
#   1. 作る部の出力・コード・場面・守るファイルの SHA-256 を、作る部の run.json・ds47_build.json・ds47_play.json の値と照合する（違えば止まる）。
#   2. 作る部の測定の道具（ds47_report.py）を使わずに、生の記録（Play モードの 90 Hz の CSV・JSON、動画、終わりの原画視点の PNG）から数え直す：
#      流れの時刻と出来事、引き継ぎと形成の始まりのつなぎ目、座席の船の姿勢（t* で原画の置き方）、視点の動き、一時停止、動画の黒とカット、114 の画素。
#   3. 場面 DS47_Flow.unity の依存（GUID）を設計46 の DS46_Clock.unity と比べ、保存した値（時計・浮力・操船・乗客）と絶対のパスを読む。
#   4. 証拠を Docs/Evidence/Design/47/ へ写し（PNG は 1920 × 1080、動画は 5 MB 以下に縮めた写し）、記録の metrics.json・run.json・数え直しの JSON を書く。
# PC の記録の計算（numpy・OpenCV・ffmpeg）。Unity は回さない。HMD 実機ではない。
# 使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds47/ds47_record.py
import csv
import datetime
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, OrderedDict

import cv2
import numpy as np

T0 = time.time()
REPO = "G:/Unity/GreatWave_2026_Fresh"
UNITY = REPO + "/Unity"
B47 = UNITY + "/Build/Design/47"
FLOW = B47 + "/flow"
FU = FLOW + "/unity"
IND = B47 + "/indep_check"
EV = REPO + "/Docs/Evidence/Design/47"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FLOWJSON = UNITY + "/Assets/GreatWave/Design47/Data/ds47_flow.json"
SCENE47 = UNITY + "/Assets/GreatWave/Design47/Scenes/DS47_Flow.unity"
SCENE46 = UNITY + "/Assets/GreatWave/Design46/Scenes/DS46_Clock.unity"
BOATS43 = UNITY + "/Assets/GreatWave/Design43/Data/ds43_boats.json"
P41 = UNITY + "/Build/Design/41/model/unity/full/painting_t120_off.png"
P46 = UNITY + "/Build/Design/46/clock/unity/tstar/painting_t120_off_ds46clock.png"
MB5 = 5 * 1000 * 1000


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def fail(msg):
    print("止める：" + msg)
    sys.exit(1)


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


# ------------------------------------------------------------------ 1. SHA-256 の照合
run_b = jload(FLOW + "/run.json")
build = jload(FU + "/ds47_build.json")
play_m = jload(FU + "/main/ds47_play.json")
play_v = jload(FU + "/variant/ds47_play.json")
checked = {}
for r, h in run_b["inputs"].items():
    checked[r] = (sha(REPO + "/" + r), h)
for r, v in run_b["outputs"].items():
    checked[r] = (sha(REPO + "/" + r), v["sha256"])
checked["Unity/" + build["scene"]] = (sha(UNITY + "/" + build["scene"]), build["sceneSha256"])
checked["（main の報告の場面）"] = (sha(SCENE47), play_m["sceneSha256"])
checked["（variant の報告の場面）"] = (sha(SCENE47), play_v["sceneSha256"])
prot = {}
for line in build["protected"]:
    r, h = line.rsplit(" ", 1)
    p = os.path.normpath(os.path.join(UNITY, r)).replace("\\", "/")
    prot[p.replace(REPO + "/", "")] = (sha(p), h)
bad = [k for k, (a, b) in list(checked.items()) + list(prot.items()) if a != b]
if bad:
    fail("SHA-256 が作る部の記録と違う: " + ", ".join(bad))
print("SHA-256 の照合：作る部 %d 件・守るファイル %d 件、すべて同じ" % (len(checked), len(prot)))

cfg = jload(FLOWJSON)
TM = cfg["timing"]
boats = {b["key"]: b for b in jload(BOATS43)["boats"]}
PAINT_POS = np.array(boats["boat_mid"]["rootPos"])
PAINT_ROT = np.array(boats["boat_mid"]["rootRot"])   # x, y, z, w（Unity）


# ------------------------------------------------------------------ 2. 数え直し（Play モードの CSV）
def qnorm(q):
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def qangle(a, b):
    d = np.abs(np.sum(qnorm(a) * qnorm(b), axis=-1))
    return np.degrees(2.0 * np.arccos(np.clip(d, 0.0, 1.0)))


def qrot(q, v):
    """Unity の四元数 (x, y, z, w) でベクトルを回す（行ごと）。"""
    q = qnorm(np.atleast_2d(q))
    u = q[:, :3]
    w = q[:, 3:4]
    v = np.broadcast_to(np.asarray(v, dtype=float), u.shape)
    t = 2.0 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


NUM = ["frame", "dt", "exp", "wave", "tau", "paused", "handed_over", "in_thr", "in_turn", "in_stop",
       "boat_x", "boat_y", "boat_z", "boat_qx", "boat_qy", "boat_qz", "boat_qw", "boat_vx", "boat_vy", "boat_vz", "kinematic", "wet_points",
       "rider_x", "rider_y", "rider_z", "cam_x", "cam_y", "cam_z", "cam_qx", "cam_qy", "cam_qz", "cam_qw", "cam_fov",
       "head_dx", "head_dy", "head_dz", "afterglow_u", "events_fired", "events_skipped", "bw_rebuilds", "bw_fallbacks", "comfort_level", "cap"]


def load_csv(p):
    with open(p, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    d = {k: np.array([float(r[k]) for r in rows]) for k in NUM}
    for k in ("clock_state", "phase", "pause_reason", "steer_mode", "extra"):
        d[k] = np.array([r[k] for r in rows])
    ex = [r["extra"].split("|") for r in rows]
    d["y_local"] = np.array([float(e[3]) for e in ex])
    d["y_paint"] = np.array([float(e[4]) for e in ex])
    d["n"] = len(rows)
    return d


def runs(mask):
    out = []
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def flow_recount(d, play, name):
    R = OrderedDict()
    n = d["n"]
    fr = d["frame"].astype(int)
    R["rows"] = n
    R["frames_contiguous"] = bool(np.all(np.diff(fr) == 1))
    R["frame_range"] = [int(fr[0]), int(fr[-1])]
    R["dt_values"] = sorted(set(float(x) for x in d["dt"]))
    exp = d["exp"]
    R["exp_first_last"] = [float(exp[0]), float(exp[-1])]
    # 進めたコマの時刻の増え方（止めた・終わったコマは除く）
    de = np.diff(exp)
    running = (d["clock_state"][1:] == "Running") & (d["clock_state"][:-1] == "Running")
    R["running_increment_ne_dt"] = int(np.sum(running & (np.abs(de - d["dt"][1:]) > 1e-6)))
    R["experience_decreases"] = int(np.sum(de < -1e-12))
    # 相の数と境の時刻
    ph = d["phase"]
    order = []
    for p in ph:
        if not order or order[-1] != p:
            order.append(p)
    R["phase_order"] = order
    R["phase_frames"] = {p: int(np.sum(ph == p)) for p in order}
    R["phase_first_exp"] = {p: float(exp[np.argmax(ph == p)]) for p in order}
    # 出来事（報告の log）と表の結び付き
    ev = play["events"]
    ids = [e["id"] for e in ev]
    lag = [e["clockT"] - e["eventT"] for e in ev]
    ho = play["handover"]
    anchor = {"experience": 0.0, "handover": ho["s"], "wave": ho["waveStart"], "afterglow": ho["afterglowStart"]}
    table = {e["id"]: e["t"] for e in play["eventTable"]}
    exp_tab = {}
    for e in cfg["events"]:
        t = anchor[e["anchor"]] + e["offset"]
        if e["anchor"] == "experience":
            t = max(t, 1e-6)
        exp_tab[e["id"]] = t
    R["events"] = {
        "count": len(ev), "fired_once_each": len(ids) == len(set(ids)) == len(cfg["events"]) and all(e["fired"] for e in ev),
        "ids": ids, "lag_s": [round(x, 6) for x in lag], "max_lag_s": max(lag), "min_lag_s": min(lag),
        "max_lag_lt_one_90Hz_frame": bool(max(lag) < 1.0 / 90.0),
        "table_vs_flow_json_max_abs_s": max(abs(table[k] - exp_tab[k]) for k in exp_tab),
        "csv_events_fired_final": int(d["events_fired"][-1]), "csv_events_skipped_final": int(d["events_skipped"][-1]),
    }
    # 引き継ぎの規則（D47-1）
    total = ho["s"] + ho["lead"] + TM["formationS"] + TM["holdS"] + TM["afterglowMoveS"] + TM["afterglowDwellS"]
    R["handover"] = {
        "s": ho["s"], "lead": ho["lead"], "trajT": ho["trajT"], "lead_eq_trajT_minus_12": abs(ho["lead"] - (ho["trajT"] - TM["formationS"])) < 1e-9,
        "waveStart": ho["waveStart"], "afterglowStart": ho["afterglowStart"], "end": ho["end"], "predictedTotal": ho["predictedTotal"],
        "total_from_parts": total, "within_60_90": 60.0 <= ho["end"] <= 90.0, "reason": ho["reason"], "predictions": ho["predictions"],
        "in_intro_window": TM["introMinS"] <= ho["s"] <= TM["introMaxS"], "predicted_ge_target": ho["predictedTotal"] >= TM["targetTotalS"],
    }
    # 船の姿勢と動き
    pos = np.stack([d["boat_x"], d["boat_y"], d["boat_z"]], 1)
    q = np.stack([d["boat_qx"], d["boat_qy"], d["boat_qz"], d["boat_qw"]], 1)
    step = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    hstep = np.linalg.norm(np.diff(pos[:, [0, 2]], axis=0), axis=1)
    rstep = qangle(q[1:], q[:-1])
    ih = int(np.argmax(d["handed_over"] > 0.5))
    iF = int(np.argmax(ph == "Formation"))

    def seam(i, label):
        lo, hi = max(1, i - 90), max(1, i - 3)
        base = step[lo - 1:hi - 1]
        win = list(range(max(0, i - 4), min(n - 1, i + 4)))
        return {"label": label, "row": i, "frame": int(fr[i]), "exp": float(exp[i]),
                "steps_m_around": [[int(fr[k + 1]), round(float(step[k]), 5), round(float(rstep[k]), 4)] for k in win],
                "max_step_m_around": float(max(step[k] for k in win)), "min_step_m_around": float(min(step[k] for k in win)),
                "max_rot_step_deg_around": float(max(rstep[k] for k in win)),
                "median_step_m_before_90": float(np.median(base)) if len(base) else None,
                "max_step_m_before_90": float(np.max(base)) if len(base) else None}

    R["seam_handover"] = seam(ih, "handover")
    R["seam_formation_start"] = seam(iF, "formation_start")
    sp = np.hypot(d["boat_vx"], d["boat_vz"])
    R["boat_speed_at_handover_mps"] = float(sp[ih])
    pre = (ph == "Intro") | (ph == "Approach")
    R["buoyancy_steer_intro_approach"] = {
        "frames": int(np.sum(pre)), "non_kinematic": int(np.sum(pre & (d["kinematic"] < 0.5))),
        "wet_points_values": sorted(set(int(x) for x in d["wet_points"][pre])),
        "steering_frames": int(np.sum(d["steer_mode"] == "Steering")), "trajectory_frames": int(np.sum(d["steer_mode"] == "Trajectory")),
        "steer_modes": dict(Counter(d["steer_mode"])),
        "nonzero_throttle_frames": int(np.sum(d["in_thr"] != 0)), "nonzero_turn_frames": int(np.sum(d["in_turn"] != 0)),
        "stop_frames": int(np.sum(d["in_stop"] != 0)),
    }
    post = ~pre
    R["scripted_after_formation"] = {"frames": int(np.sum(post)), "kinematic": int(np.sum(post & (d["kinematic"] > 0.5)))}
    R["comfort_levels"] = sorted(set(int(x) for x in d["comfort_level"]))
    # 形成と保持の船（D47-2）
    fh = (ph == "Formation") | (ph == "Hold")
    fwd = qrot(q, [0.0, 0.0, 1.0])
    up = qrot(q, [0.0, 1.0, 0.0])
    pitch = np.degrees(np.arcsin(np.clip(fwd[:, 1], -1, 1)))
    tilt = np.degrees(np.arccos(np.clip(up[:, 1], -1, 1)))
    vy = np.diff(pos[:, 1]) / d["dt"][1:]
    iF_ = np.where(fh)[0]
    formation = ph == "Formation"
    above = pos[:, 1] - d["y_local"]
    R["formation_hold_boat"] = {
        "max_abs_pitch_deg": float(np.max(np.abs(pitch[fh]))), "max_tilt_from_vertical_deg": float(np.max(tilt[fh])),
        "tilt_at_end_deg": float(tilt[-1]), "pitch_at_end_deg": float(pitch[-1]),
        "max_root_y_step_m": float(np.max(np.abs(np.diff(pos[iF_[0]:iF_[-1] + 1, 1])))),
        "max_abs_vertical_speed_mps": float(np.max(np.abs(vy[iF_[0]:iF_[-1]]))),
        "y_min_max_m": [float(np.min(pos[fh, 1])), float(np.max(pos[fh, 1]))],
        "root_minus_floating_height_m_formation": [float(np.min(above[formation])), float(np.max(above[formation]))],
        "root_minus_floating_height_at_wave": [float(d["wave"][formation][np.argmax(above[formation])]), float(d["wave"][formation][np.argmin(above[formation])])],
        "max_tilt_intro_approach_deg": float(np.max(tilt[pre])),
    }
    # t* の前の最後の段と、終わりの姿勢
    it = int(np.argmax((ph == "Hold")))
    last = [[int(fr[k]), float(d["wave"][k]), float(np.linalg.norm(pos[k] - PAINT_POS)), float(qangle(q[k:k + 1], PAINT_ROT[None])[0])] for k in range(it - 5, it + 2)]
    R["approach_to_painting_pose"] = {"rows_before_hold": last,
                                      "end_pos_diff_m": float(np.linalg.norm(pos[-1] - PAINT_POS)),
                                      "end_rot_diff_deg": float(qangle(q[-1:], PAINT_ROT[None])[0]),
                                      "hold_to_end_max_pos_diff_m": float(np.max(np.linalg.norm(pos[it:] - PAINT_POS, axis=1))),
                                      "hold_to_end_max_rot_diff_deg": float(np.max(qangle(q[it:], np.broadcast_to(PAINT_ROT, q[it:].shape))))}
    # 視点（HMD Camera）の動き
    cp = np.stack([d["cam_x"], d["cam_y"], d["cam_z"]], 1)
    cq = np.stack([d["cam_qx"], d["cam_qy"], d["cam_qz"], d["cam_qw"]], 1)
    cstep = np.linalg.norm(np.diff(cp, axis=0), axis=1)
    crot = qangle(cq[1:], cq[:-1])
    cfov = np.abs(np.diff(d["cam_fov"]))
    cam = {}
    for p in order:
        m = ph[1:] == p
        if not np.any(m):
            continue
        cam[p] = {"frames": int(np.sum(ph == p)), "max_pos_step_m": float(np.max(cstep[m])), "max_speed_mps": float(np.max(cstep[m] / d["dt"][1:][m])),
                  "max_rot_step_deg": float(np.max(crot[m])), "max_fov_step_deg": float(np.max(cfov[m]))}
    ia = int(np.argmax(ph == "Afterglow"))
    cam_extra = {"afterglow_start_to_end_distance_m": float(np.linalg.norm(cp[-1] - cp[ia - 1])),
                 "afterglow_path_length_m": float(np.sum(cstep[ia - 1:])), "fov_start_end": [float(d["cam_fov"][ia - 1]), float(d["cam_fov"][-1])],
                 "yaw_deg_before_afterglow_minmax": None}
    fw = qrot(cq[:ia], [0.0, 0.0, 1.0])
    yaw = np.degrees(np.arctan2(fw[:, 0], fw[:, 2]))
    cam_extra["yaw_deg_before_afterglow_minmax"] = [float(np.min(yaw)), float(np.max(yaw))]
    bfw = fwd[:ia]
    byaw = np.degrees(np.arctan2(bfw[:, 0], bfw[:, 2]))
    cam_extra["boat_yaw_deg_before_afterglow_minmax"] = [float(np.min(byaw)), float(np.max(byaw))]
    R["camera"] = cam
    R["camera_extra"] = cam_extra
    R["head_offset_nonzero_frames"] = int(np.sum((np.abs(d["head_dx"]) + np.abs(d["head_dy"]) + np.abs(d["head_dz"])) > 1e-6))
    # 船用水面データ
    bw = play["boatWater"]
    R["boat_water"] = {"rebuilds_csv_final": int(d["bw_rebuilds"][-1]), "rebuilds": bw["rebuilds"], "ms_mean": bw["rebuildMsTotal"] / max(1, bw["rebuilds"]),
                       "fallbacks": bw["fallbacks"], "queries": bw["queries"],
                       "rebuild_rows_by_phase": {p: int(np.sum((np.diff(d["bw_rebuilds"]) > 0) & (ph[1:] == p))) for p in order}}
    R["input"] = play["input"]
    # 一時停止
    pr = runs(d["paused"] > 0.5)
    R["pause_runs"] = []
    for a, b in pr:
        seg = slice(a, b + 1)
        R["pause_runs"].append({"rows": [a, b], "frames": b - a + 1, "phase": sorted(set(ph[seg])), "exp_range": float(np.ptp(exp[seg])),
                                "boat_move_m": float(np.max(np.linalg.norm(pos[seg] - pos[a], axis=1))), "clock_states": sorted(set(d["clock_state"][seg])),
                                "duration_s": float(np.sum(d["dt"][seg])), "reason": sorted(set(d["pause_reason"][seg]))})
    R["leaves"] = [{k: L[k] for k in ("name", "started", "paused", "restored", "resumed", "offset")} | {
        "pause_after_frames": L["paused"] - L["started"], "resume_after_frames": L["resumed"] - L["restored"],
        "pause_after_s": (L["paused"] - L["started"]) / 90.0, "resume_after_s": (L["resumed"] - L["restored"]) / 90.0,
        "exp_paused_eq_resumed": L["expPaused"] == L["expResumed"]} for L in play["leaves"]]
    # 記録したコマ（30 fps の動画のもと）
    cap = d["cap"] > 0.5
    ce = exp[cap]
    dce = np.diff(ce)
    R["captured"] = {"rows": int(np.sum(cap)), "exp_step_min_max": [float(np.min(dce)), float(np.max(dce))] if len(dce) else None,
                     "exp_step_not_1_30": int(np.sum(np.abs(dce - 1.0 / 30.0) > 1e-4)) if len(dce) else None,
                     "exp_step_not_1_30_where": [float(x) for x in ce[1:][np.abs(dce - 1.0 / 30.0) > 1e-4][:12]] if len(dce) else None}
    R["pose_vs_painting_json_unity"] = play.get("poseVsPaintingJson")
    R["vertex_px_unity"] = play.get("vertexPx")
    R["view_cam_vs_painting_unity"] = play.get("viewCamVsPainting")
    R["flow_log"] = play["flowLog"]
    return R


dm = load_csv(FU + "/main/ds47_frames.csv")
dv = load_csv(FU + "/variant/ds47_frames.csv")
recount = OrderedDict()
recount["main"] = flow_recount(dm, play_m, "main")
recount["variant"] = flow_recount(dv, play_v, "variant")
pf = qrot(PAINT_ROT, [0.0, 0.0, 1.0])[0]
recount["painting_pose_boat_mid"] = {"rootPos": PAINT_POS.tolist(), "rootRot_xyzw": PAINT_ROT.tolist(), "local_plus_z_world": pf.tolist(),
                                     "local_plus_z_pitch_deg": float(np.degrees(np.arcsin(pf[1]))),
                                     "note_ja": "ds43_boats.json の boat_mid の根の局所 +z を世界へ回した向き。y が負なら +z の端が下がる"}

# ------------------------------------------------------------------ 3. 動画（86）
def video_scan(path):
    capv = cv2.VideoCapture(path)
    fps = capv.get(cv2.CAP_PROP_FPS)
    W = int(capv.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(capv.get(cv2.CAP_PROP_FRAME_HEIGHT))
    means, darks, mads = [], [], []
    prev = None
    last = None
    while True:
        ok, fr = capv.read()
        if not ok:
            break
        y = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        means.append(float(y.mean()))
        darks.append(float((y < 20).mean()))
        s = cv2.resize(y, (480, 270), interpolation=cv2.INTER_AREA).astype(np.int16)
        mads.append(float(np.abs(s - prev).mean()) if prev is not None else 0.0)
        prev = s
        last = fr
    capv.release()
    means, darks, mads = np.array(means), np.array(darks), np.array(mads)
    n = len(means)
    med = np.array([np.median(np.delete(mads[max(1, k - 6):min(n, k + 7)], np.where(np.arange(max(1, k - 6), min(n, k + 7)) == k)[0])) if k > 0 else 0 for k in range(n)])
    ratio = np.where(np.arange(n) > 0, mads / np.maximum(0.25, med), 0.0)
    return {"frames": n, "fps": fps, "size": [W, H], "seconds": n / fps if fps else None,
            "black_frames(mean<20 or dark>0.9)": int(np.sum((means < 20) | (darks > 0.9))),
            "min_mean_luma": float(means.min()), "min_mean_luma_frame": int(means.argmin()), "max_dark_fraction": float(darks.max()),
            "max_mad_480x270": float(mads.max()), "max_mad_frame": int(mads.argmax()), "max_mad_t_s": float(mads.argmax() / fps),
            "frames_mad_gt_40": int(np.sum(mads > 40)), "max_spike_ratio": float(ratio.max()), "max_spike_frame": int(ratio.argmax()),
            "cuts(mad>20 and spike>3)": int(np.sum((mads > 20) & (ratio > 3))),
            "near_frozen_frames(mad<0.02)": int(np.sum(mads[1:] < 0.02))}, last


vid, last_frame = video_scan(FLOW + "/ds47_flow_30fps.mp4")
recount["video_86"] = vid


# ------------------------------------------------------------------ 4. 114 の画素
def img(p):
    return cv2.imread(p, cv2.IMREAD_COLOR).astype(np.int16)


def pxdiff(a, b):
    d = np.max(np.abs(a - b), axis=2)
    ys, xs = np.nonzero(d)
    return {"px": int(np.count_nonzero(d)), "px_over_8": int(np.count_nonzero(d > 8)), "max": int(d.max()),
            "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None}


PE = FU + "/main/painting/painting_end.png"
VE = FU + "/main/painting/view_end.png"
NB = FU + "/main/painting/painting_end_noboat.png"
RB = FU + "/main/painting/painting_end_refboat.png"
VPE = FU + "/variant/painting/painting_end.png"
pe, ve, nb, rb, vpe, p41, p46 = (img(p) for p in (PE, VE, NB, RB, VPE, P41, P46))
ride = np.max(np.abs(pe - nb), axis=2) > 24
refm = np.max(np.abs(rb - nb), axis=2) > 24
m41 = np.max(np.abs(p41 - nb), axis=2) > 24


def iou(a, b):
    return float(np.sum(a & b) / max(1, np.sum(a | b)))


def bbox(m):
    ys, xs = np.nonzero(m)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def centroid(m):
    ys, xs = np.nonzero(m)
    return np.array([xs.mean(), ys.mean()])


lf = cv2.resize(last_frame, (1920, 1080)).astype(np.int16) if last_frame is not None else None
recount["painting_114"] = {
    "sha256": {"painting_end": sha(PE), "view_end": sha(VE), "refboat": sha(RB), "noboat": sha(NB), "variant_painting_end": sha(VPE), "ds41_saved": sha(P41), "ds46_clock": sha(P46)},
    "view_end_vs_painting_end": pxdiff(ve, pe), "painting_end_vs_ds41_saved": pxdiff(pe, p41), "painting_end_vs_ds46_clock": pxdiff(pe, p46),
    "refboat_vs_ds41_saved": pxdiff(rb, p41), "ds46_vs_ds41": pxdiff(p46, p41), "variant_end_vs_main_end": pxdiff(vpe, pe), "variant_end_vs_ds41_saved": pxdiff(vpe, p41),
    "mask_threshold": 24, "ride_mask_px": int(ride.sum()), "refboat_mask_px": int(refm.sum()), "ds41_boat_mask_px": int(m41.sum()),
    "iou_ride_vs_refboat": iou(ride, refm), "iou_ride_vs_ds41": iou(ride, m41),
    "centroid_shift_px": float(np.linalg.norm(centroid(ride) - centroid(refm))), "ride_bbox_xyxy": bbox(ride),
    "video_last_frame_vs_painting_end_mean_abs": float(np.mean(np.abs(lf - pe))) if lf is not None else None,
    "video_last_frame_vs_painting_end_px_over_40": int(np.count_nonzero(np.max(np.abs(lf - pe), axis=2) > 40)) if lf is not None else None,
}
if recount["painting_114"]["iou_ride_vs_refboat"] < 0.99 or recount["main"]["approach_to_painting_pose"]["end_pos_diff_m"] > 1e-3:
    fail("114 の数え直しが作る部の値と合わない")


# ------------------------------------------------------------------ 5. 場面の依存・保存した値・改行
def guids(p):
    with open(p, encoding="utf-8") as f:
        return set(re.findall(r"guid: ([0-9a-f]{32})", f.read()))


g46 = guids(SCENE46)
g47 = guids(SCENE47)
new = g47 - g46
where = {}
for root, _, files in os.walk(UNITY + "/Assets"):
    for fn in files:
        if fn.endswith(".meta"):
            p = os.path.join(root, fn)
            with open(p, encoding="utf-8", errors="ignore") as f:
                m = re.search(r"guid: ([0-9a-f]{32})", f.read())
            if m and m.group(1) in new:
                where[m.group(1)] = rel(p[:-5])
with open(SCENE47, encoding="utf-8") as f:
    s47 = f.read()


def comp_block(ident):
    i = s47.find("m_EditorClassIdentifier: Assembly-CSharp::" + ident + "\n")
    if i < 0:
        return None
    j = s47.find("\n--- ", i)
    return s47[i:j]


def val(block, key):
    m = re.search(r"\n  " + key + r": ([^\n]*)", block or "")
    return m.group(1) if m else None


blk = {k: comp_block(v) for k, v in {"clock": "GreatWave.ArtFirst.GWClock", "buoy": "GreatWave.Design42.DS42Buoyancy", "steer": "GreatWave.Design44.DS44BoatSteer",
                                    "rider": "GreatWave.Design45.DS45RiderComfort", "flow": "GreatWave.Design47.DS47Flow", "playback": "GreatWave.Design30.DS30SinglePlayback"}.items()}
abs_paths = sorted(set(re.findall(r"(?:[A-Za-z]+Path|[A-Za-z0-9]+File): ([A-Za-z]:[\\/][^\r\n]+)", s47)))
with open(SCENE46, encoding="utf-8") as f:
    s46 = f.read()
recount["scene"] = {
    "path": rel(SCENE47), "bytes": os.path.getsize(SCENE47), "sha256": sha(SCENE47),
    "guids_ds46": len(g46), "guids_ds47": len(g47), "new_vs_ds46": {g: where.get(g, "（Assets の下にない）") for g in sorted(new)}, "dropped_vs_ds46": len(g46 - g47),
    "clock": {k: val(blk["clock"], k) for k in ("mode", "advanceBeforePhysics", "startSeconds", "endSeconds", "waveStartSeconds", "tStarSeconds", "maxStepSeconds")},
    "buoyancy_stepInFixedUpdate": val(blk["buoy"], "stepInFixedUpdate"), "steer_stepInFixedUpdate": val(blk["steer"], "stepInFixedUpdate"),
    "rider": {k: val(blk["rider"], k) for k in ("startLevel", "stepInLateUpdate", "readInput")},
    "flow": {k: val(blk["flow"], k) for k in ("startWaterY", "eqDraftM", "placeAtStart")},
    "absolute_paths": abs_paths, "absolute_paths_same_as_ds46": all(a in s46 for a in abs_paths),
    "leftsupport_in_scene": "M1_Revision_LeftSupport" in s47,
}
lineend = {}
for base in (UNITY + "/Assets/GreatWave/Design47", REPO + "/Tools/GWWaveGen/ds47"):
    for root, _, files in os.walk(base):
        for fn in files:
            if "__pycache__" in root:
                continue
            p = os.path.join(root, fn)
            b = open(p, "rb").read()
            crlf = b.count(b"\r\n")
            lf = b.count(b"\n") - crlf
            lineend[rel(p)] = "CRLF" if crlf and not lf else ("LF" if lf and not crlf else ("混在" if crlf and lf else "改行なし"))
for p in (UNITY + "/Assets/GreatWave/Design47.meta",):
    b = open(p, "rb").read()
    lineend[rel(p)] = "CRLF" if b"\r\n" in b else "LF"
recount["line_endings"] = dict(sorted(lineend.items()))

# ------------------------------------------------------------------ 6. 数え直しと作る部の値の差
bm = jload(FLOW + "/metrics.json")
M = recount["main"]
V = recount["variant"]
diff = OrderedDict()
diff["video_frames"] = vid["frames"] - bm["acceptance"]["86_video_black_and_cut"]["value"]["frames"]
diff["video_black"] = vid["black_frames(mean<20 or dark>0.9)"] - bm["acceptance"]["86_video_black_and_cut"]["value"]["blackFrames"]
diff["video_cut"] = vid["cuts(mad>20 and spike>3)"] - bm["acceptance"]["86_video_black_and_cut"]["value"]["cutFrames"]
diff["total_s_main"] = round(M["handover"]["end"] - bm["flow"]["totalS"], 9)
diff["total_s_variant"] = round(V["handover"]["end"] - bm["variant_stop_and_leave"]["totalS"], 9)
diff["handover_s_main"] = round(M["handover"]["s"] - bm["flow"]["handover"]["s"], 9)
diff["end_pos_diff_m_main"] = round(M["approach_to_painting_pose"]["end_pos_diff_m"] - bm["acceptance"]["114_ridden_boat_at_painting_position"]["value"]["rootPosDiffM"], 6)
diff["ride_mask_px"] = recount["painting_114"]["ride_mask_px"] - bm["painting_114_images"]["ridePixels"]
diff["iou"] = round(recount["painting_114"]["iou_ride_vs_refboat"] - bm["painting_114_images"]["iou"], 9)
diff["px_vs_ds46"] = recount["painting_114"]["painting_end_vs_ds46_clock"]["px"] - bm["painting_114_images"]["diffPixelsVsDs46TStar"]
diff["px_vs_ds46_over8"] = recount["painting_114"]["painting_end_vs_ds46_clock"]["px_over_8"] - bm["painting_114_images"]["diffPixelsVsDs46TStarOver8"]
diff["max_vs_ds46"] = recount["painting_114"]["painting_end_vs_ds46_clock"]["max"] - bm["painting_114_images"]["maxAbsDiffVsDs46"]
diff["pause_runs"] = len(V["pause_runs"]) - len(bm["variant_stop_and_leave"]["pauseRuns"])
diff["pause_frames"] = [a["frames"] - b["frames"] for a, b in zip(V["pause_runs"], bm["variant_stop_and_leave"]["pauseRuns"])]
diff["boat_water_rebuilds"] = M["boat_water"]["rebuilds_csv_final"] - bm["flow"]["boatWater"]["rebuilds"]
diff["afterglow_max_speed_mps"] = round(M["camera"]["Afterglow"]["max_speed_mps"] - bm["flow"]["phaseCameraSteps"]["Afterglow"]["maxPosSpeedMps"], 6)
recount["diff_vs_builder"] = diff
nonzero = [key for key, v in diff.items() if key != "pause_frames" and abs(v) > 1e-6] + (["pause_frames"] if any(diff["pause_frames"]) else [])
recount["diff_nonzero_keys"] = nonzero
if nonzero:
    print("注意：数え直しと作る部の値の差 " + json.dumps({k: diff[k] for k in nonzero}, ensure_ascii=False))

# 独立の検査の要約（写すだけ）
ind = jload(IND + "/video_chk.json")["summary"]
recount["independent_check_files"] = {rel(IND + "/" + f): sha(IND + "/" + f) for f in sorted(os.listdir(IND)) if not f.endswith(".npy")}

# ------------------------------------------------------------------ 7. 証拠の写し
os.makedirs(EV, exist_ok=True)
copies = {
    FLOW + "/fig_ds47_timeline.png": "fig_ds47_timeline.png",
    FLOW + "/fig_ds47_114.png": "fig_ds47_114.png",
    FLOW + "/fig_ds47_variant.png": "fig_ds47_variant.png",
    FLOW + "/metrics.json": "ds47_flow_metrics.json",
    FLOW + "/run.json": "ds47_flow_run.json",
    FU + "/ds47_build.json": "ds47_build.json",
    FU + "/main/ds47_play.json": "ds47_play_main.json",
    FU + "/variant/ds47_play.json": "ds47_play_variant.json",
}
for src, dst in copies.items():
    shutil.copyfile(src, EV + "/" + dst)
    if sha(src) != sha(EV + "/" + dst):
        fail("写しの SHA-256 が違う: " + dst)
# 静止画の一覧（作る部は 1920 × 1440）を 0.75 倍にして 1920 × 1080 の中央へ（左右は紙に近い灰の余白）
st = cv2.imread(FLOW + "/stills_ds47_flow.png", cv2.IMREAD_COLOR)
sm = cv2.resize(st, (1440, 1080), interpolation=cv2.INTER_AREA)
canvas = np.full((1080, 1920, 3), 245, np.uint8)
canvas[:, 240:1680] = sm
cv2.imwrite(EV + "/stills_ds47_flow.png", canvas, [cv2.IMWRITE_PNG_COMPRESSION, 9])
# 独立の検査の動画の要約
with open(EV + "/ds47_indep_video_summary.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump({"note_ja": "進行役の独立の検査（Unity/Build/Design/47/indep_check/video_chk.py、Git 対象外）の要約の部分だけを写した。コマの番号は 0 始まり、30 fps",
               "summary": ind}, f, ensure_ascii=False, indent=1)
# 動画：1280 × 720 に縮めて 5 MB の下へ
vsrc = FLOW + "/ds47_flow_30fps.mp4"
vdst = EV + "/ds47_flow_720p_30fps.mp4"
venc = None
for crf in (26, 28, 30, 32, 34):
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", vsrc, "-vf", "scale=1280:720:flags=area", "-c:v", "libx264", "-preset", "slow",
                    "-crf", str(crf), "-pix_fmt", "yuv420p", "-an", vdst], check=True)
    if os.path.getsize(vdst) <= MB5:
        venc = {"crf": crf, "bytes": os.path.getsize(vdst), "size": "1280x720", "preset": "slow"}
        break
if venc is None:
    fail("縮めても 5 MB を超える")
vsm, _ = video_scan(vdst)
venc["scan"] = vsm
recount["video_720p_copy"] = venc
for p in ("fig_ds47_timeline.png", "fig_ds47_114.png", "fig_ds47_variant.png", "stills_ds47_flow.png"):
    if cv2.imread(EV + "/" + p).shape[:2] != (1080, 1920):
        fail("1920 × 1080 でない: " + p)
for p in os.listdir(EV):
    if os.path.getsize(EV + "/" + p) > MB5:
        fail("5 MB を超える: " + p)

with open(EV + "/ds47_record_recount.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(recount, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


# ------------------------------------------------------------------ 8. 記録の metrics.json・run.json
def ft(p):
    s = os.stat(p)
    return {"created": datetime.datetime.fromtimestamp(s.st_ctime).strftime("%H:%M:%S"), "modified": datetime.datetime.fromtimestamp(s.st_mtime).strftime("%H:%M:%S")}


tlist = [FLOW + "/_started.txt", UNITY + "/Assets/GreatWave/Design47.meta", REPO + "/Tools/GWWaveGen/ds47/run_ds47_unity.ps1",
         UNITY + "/Assets/GreatWave/Design47/Scripts/DS47Recorder.cs", UNITY + "/Assets/GreatWave/Design47/Data/ds47_flow.json",
         UNITY + "/Assets/GreatWave/Design47/Editor/DS47FlowPlay.cs", UNITY + "/Assets/GreatWave/Design47/Editor/DS47FlowBuild.cs",
         UNITY + "/Assets/GreatWave/Design47/Materials/DS47_LeaveOverlay.mat", UNITY + "/Assets/GreatWave/Design47/Scripts/DS47Flow.cs",
         SCENE47]
tlist += [FLOW + "/logs/" + f for f in sorted(os.listdir(FLOW + "/logs")) if f.endswith(".log")]
tlist += [FU + "/debug_start_height.txt", FU + "/ds47_build.json", FU + "/main/ds47_play.json", FU + "/variant/ds47_play.json",
          FLOW + "/ds47_flow_30fps.mp4", FLOW + "/metrics.json", FLOW + "/_finished.txt", REPO + "/Tools/GWWaveGen/ds47/ds47_report.py"]
tlist += [IND + "/" + f for f in ("video_chk.py", "video_chk.json", "csv_chk.py", "px114.py", "paused.jpg")]
times = {rel(p): ft(p) for p in tlist}
started = open(FLOW + "/_started.txt", encoding="utf-8").read().strip()
finished = open(FLOW + "/_finished.txt", encoding="utf-8").read().strip()

metrics = OrderedDict()
metrics["schema"] = "GreatWave.DS47.record_metrics/1"
metrics["number"] = "設計47"
metrics["title_ja"] = "導入→接近→砕波→余韻をつなぐ"
metrics["created_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
metrics["evidence_kind_ja"] = ("PC の Unity 6000.4.3f1 の Editor の Play モード（batchmode。止めた状態で EditorApplication.Step により 1 フレーム = 1/90 s ずつ進め、"
                               "30 fps の動画のコマはオフスクリーンで描いた。RTX 3080）。入力は Input System の仮想のキーボードを DS44Input.Read で読んだ。"
                               "頭の動きは HMD Camera の局所の位置を試験がずらした。進行役の独立の検査（numpy・OpenCV）、記録の数え直し（numpy・OpenCV・ffmpeg）。"
                               "HMD 実機ではない。Release のプレイヤーではない。実時間の Play ではない。利用者は確かめていない")
metrics["plan_ja"] = ("計画 §2.5 設計47：絵コンテと演出イベントの表（JSON）。導入（静かな海で操船）→ 接近（うねりが 1.5 倍へ育つ、固定軌道へ引き継ぎ）→ 形成（Q10 の時間の骨格）"
                      "→ t* で 2 s 保持 → 余韻（同じ時刻の原画視点を見せ、自分の船を原画の中で見つける最小の V1）。全体 60〜90 秒")
metrics["min_acceptance_ja"] = "通し動画で黒画面・カットの途切れ 0（86 を使える水準で）。原画視点で乗っている船が原画の位置にある（114 を記録）"
metrics["backlog"] = ["84", "85", "86", "109", "110", "113", "114"]
metrics["acceptance"] = [
    {"item": "86：通し動画で黒画面・カットの途切れ 0", "result": "合格",
     "value": {"video": {"frames": vid["frames"], "fps": vid["fps"], "size": vid["size"], "seconds": vid["seconds"], "bytes": os.path.getsize(vsrc), "sha256": sha(vsrc)},
               "record_black": vid["black_frames(mean<20 or dark>0.9)"], "record_cuts": vid["cuts(mad>20 and spike>3)"], "record_frames_mad_gt_40": vid["frames_mad_gt_40"],
               "record_min_mean_luma": vid["min_mean_luma"], "record_max_mad": vid["max_mad_480x270"], "record_max_mad_t_s": vid["max_mad_t_s"],
               "builder": bm["acceptance"]["86_video_black_and_cut"]["value"],
               "indep": {"black": len(ind["blackFrames"]), "cuts": len(ind["cutFrames"]), "minMeanY": ind["minMeanY"], "minSsim": ind["minSsim"], "maxEcr": ind["maxEcr"], "maxSpike": ind["maxSpike"]},
               "captured_exp_step": M["captured"]["exp_step_min_max"]}},
    {"item": "114（記録）：原画視点で乗っている船が原画の位置にある", "result": "合格（記録）",
     "value": {"end_pos_diff_m": M["approach_to_painting_pose"]["end_pos_diff_m"], "end_rot_diff_deg": M["approach_to_painting_pose"]["end_rot_diff_deg"],
               "vertex_px_unity": M["vertex_px_unity"], "iou_ride_vs_refboat": recount["painting_114"]["iou_ride_vs_refboat"],
               "centroid_shift_px": recount["painting_114"]["centroid_shift_px"], "ride_mask_px": recount["painting_114"]["ride_mask_px"],
               "view_end_vs_painting_end_px": recount["painting_114"]["view_end_vs_painting_end"]["px"],
               "painting_end_vs_ds41_saved": recount["painting_114"]["painting_end_vs_ds41_saved"],
               "variant_end_pos_diff_m": V["approach_to_painting_pose"]["end_pos_diff_m"]}},
    {"item": "計画 §2.0 の回帰なし（原画視点）", "result": "合格（原画視点の場面は SHA-256 のまま。終わりの原画視点は設計41・46 と 4 画素の差で、どれも乗っていた船の縁。評価器は回していない）",
     "value": {"painting_scenes_unchanged": True, "protected_files": len(prot), "px_vs_ds41": recount["painting_114"]["painting_end_vs_ds41_saved"]["px"],
               "refboat_vs_ds41_px": recount["painting_114"]["refboat_vs_ds41_saved"]["px"]}},
    {"item": "段階8確認 F8-3（物理の船・操船・乗客・船用水面データを一つの体験の場面に入れ、Play で回す）", "result": "Editor の Play モードで済み（Release は設計50）",
     "value": {"buoyancy_nonkinematic_intro_approach": M["buoyancy_steer_intro_approach"], "comfort_levels": M["comfort_levels"],
               "boat_water_rebuilds": M["boat_water"]["rebuilds"], "scene_saved_values": {k: recount["scene"][k] for k in ("clock", "buoyancy_stepInFixedUpdate", "steer_stepInFixedUpdate", "rider")}}},
    {"item": "HMD（PS VR2）", "result": "保留（導入は利用者の手）。余韻の視点の移動の快適さ、座席の見上げ（109・110・113）、頭の追跡での一時停止は実機で確かめていない"},
]
metrics["acceptance_record"] = {
    "flow_main": {k: M["handover"][k] for k in ("s", "lead", "trajT", "waveStart", "afterglowStart", "end", "predictedTotal", "predictions", "reason", "within_60_90")},
    "flow_variant": {k: V["handover"][k] for k in ("s", "lead", "trajT", "waveStart", "afterglowStart", "end", "predictedTotal", "predictions", "reason", "within_60_90")},
    "variant_speed_at_handover_mps": V["boat_speed_at_handover_mps"],
    "events_main": M["events"], "events_variant": V["events"],
    "seams_main": {"handover": M["seam_handover"], "formation_start": M["seam_formation_start"]},
    "formation_hold_boat_main": M["formation_hold_boat"],
    "camera_main": M["camera"], "camera_extra_main": M["camera_extra"],
    "pause_runs_variant": V["pause_runs"], "leaves_variant": V["leaves"],
    "boat_water_main": M["boat_water"],
    "painting_pose_bow_note": recount["painting_pose_boat_mid"],
}
metrics["record_recount"] = {"file": "Docs/Evidence/Design/47/ds47_record_recount.json", "diff_vs_builder": diff}
metrics["builder_sha256_verified"] = {"files": len(checked), "protected": len(prot), "all_same": True}
metrics["fix_rounds"] = {"count": 0, "ja": ("作る部の中の作り直し（compile の誤り 2、打ち切った実行 4、場面の作り直し 5 回）は受入の判定の前の作る途中の変更で、"
                                          "作る部の最終の実行（build5・main5・variant8）で最小の受入を満たした。進行役の独立の検査は必須の指摘 0。修正の回（Q26 の 1 回）は使っていない")}
metrics["time"] = {"box_ja": "Q26 の日程で 4 時間（計画 §2.6 の［Q26］の表、10/3 の行の設計47。計画の時間枠は ≤1日）",
                   "started": started, "builder_finished": finished, "file_times": times}
metrics["hmd_ja"] = "保留（PS VR2 の導入は利用者の手）。Mock の両目の描画はこの番号では描いていない。PC の座席の視点（HMD Camera を画面のカメラとして描いた単眼）だけ"
metrics["painting_view_ja"] = ("DS41_Boats.unity・DS46_Clock.unity・DS39_Paper.unity は SHA-256 のまま（ほかの守るファイルとあわせて %d）。"
                               "体験の終わりの原画視点は設計41・46 の t* の原画視点と 4 画素の差（どれも乗っていた船の縁、最大 24/255）で、波の画素は同じ" % len(prot))
metrics["evidence"] = sorted(set(os.listdir(EV) + ["metrics.json", "run.json"]))
with open(EV + "/metrics.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

logs = {rel(FLOW + "/logs/" + f): sha(FLOW + "/logs/" + f) for f in ("unity_ds47_build5.log", "unity_ds47_main5.log", "unity_ds47_variant8.log")}
run = OrderedDict()
run["schema"] = "GreatWave.DS47.record_run/1"
run["number"] = "設計47"
run["created_utc"] = metrics["created_utc"]
run["tools"] = {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "ffmpeg": FFMPEG,
                "unity": "6000.4.3f1（batchmode の Editor の Play モード。作る部だけ。記録と独立の検査では使っていない）"}
run["builder_commands"] = run_b["unityCmds"] + [run_b["videoCmd"]]
run["builder_iterations_ja"] = run_b["iterationsJa"]
run["check_commands_ja"] = ["進行役の独立の検査：py -3.10 video_chk.py・csv_chk.py・px114.py・mk_sheet.py（写しは Unity/Build/Design/47/indep_check/、Git 対象外）"]
run["record_commands"] = ["py -3.10 -B Tools/GWWaveGen/ds47/ds47_record.py",
                          "py -3.10 -B Unity/Build/Design/47/record/ds47_commit_scan.py（コミットの一覧の点検。Git 対象外）"]
run["builder_inputs_sha256"] = run_b["inputs"]
run["builder_outputs_sha256"] = {k: v["sha256"] for k, v in run_b["outputs"].items()}
run["builder_logs_sha256"] = logs
run["protected_sha256"] = {k: v[0] for k, v in prot.items()}
run["scene"] = {"path": rel(SCENE47), "sha256": sha(SCENE47), "bytes": os.path.getsize(SCENE47)}
run["settings_restore"] = {f: {k: jload(FLOW + "/logs/" + f)[k] for k in ("restored", "addedFiles")} for f in sorted(os.listdir(FLOW + "/logs")) if f.endswith(".json")}
run["video_720p"] = {"cmd_ja": FFMPEG + " -i ds47_flow_30fps.mp4 -vf scale=1280:720:flags=area -c:v libx264 -preset slow -crf %d -pix_fmt yuv420p -an ds47_flow_720p_30fps.mp4" % venc["crf"],
                     "sha256": sha(vdst), "bytes": venc["bytes"]}
run["record_code_sha256"] = {"Tools/GWWaveGen/ds47/ds47_record.py": sha(REPO + "/Tools/GWWaveGen/ds47/ds47_record.py")}
run["evidence_sha256"] = {"Docs/Evidence/Design/47/" + p: sha(EV + "/" + p) for p in sorted(os.listdir(EV)) if p not in ("metrics.json", "run.json")}
run["evidence_sha256_metrics"] = sha(EV + "/metrics.json")
run["seconds"] = round(time.time() - T0, 1)
run["note_ja"] = ("SHA-256 は作業の木のバイトの値。作る部の全出力（2,197 枚の JPG、静止画、終わりの原画視点の PNG、90 Hz の CSV、ログ、元の 1080p の動画）と"
                  "独立の検査の写しは Git 対象外の Unity/Build/Design/47/ にある")
with open(EV + "/run.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(run, f, ensure_ascii=False, indent=1)

print(json.dumps({"video": vid, "diff": diff, "main_handover": M["handover"], "variant_handover": V["handover"], "seams": [M["seam_handover"]["max_step_m_around"], M["seam_formation_start"]["max_step_m_around"]],
                  "pause": V["pause_runs"], "painting": {k: recount["painting_114"][k] for k in ("view_end_vs_painting_end", "painting_end_vs_ds41_saved", "iou_ride_vs_refboat", "ride_mask_px")},
                  "scene": {k: recount["scene"][k] for k in ("new_vs_ds46", "clock", "absolute_paths", "absolute_paths_same_as_ds46")},
                  "venc": {k: venc[k] for k in ("crf", "bytes")}, "seconds": run["seconds"]}, ensure_ascii=False, indent=1, default=str))
