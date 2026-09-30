# -*- coding: utf-8 -*-
"""設計45：Unity の記録（ds45_rider.csv・ds45_heave30.csv・ds45_unity_report.json）から、
乗客の揺れの数値（metrics.json）・図・静止画・動画（4 段の並べ、主の乗客の切り替え）・run.json を作る（numpy・OpenCV・ffmpeg）。

数値はどれも Unity が書いた乗客の根（RiderComfortRoot）と船の根の記録から、ここで数え直す（部品の内部の値は使わない）。
加速度は 30 Hz（各コマの終わりの段）の位置の 2 階差分。設計30・44 の測り方と同じ。
修正の回（run3）：着座の確認（乗客の目を船の枠（船の根の回転）で座席の目から測った上向き・水平の成分と、船縁の上端（座席の目の 0.149 m 下。設計41）との関係）、
修正の前後の静止画（run2 の控えのコマと run3 のコマ）、Mock の両目（試験だけ。±ipd/2）の静止画を足した。
"""
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ds44"))
from ds44_report import Panel, put  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/45/comfort"
UNITY = OUT + "/unity"
FRAMES = UNITY + "/frames"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
CFG = REPO + "/Unity/Assets/GreatWave/Design45/Data/ds45_comfort.json"
R44 = REPO + "/Unity/Build/Design/44/steer/unity/ds44_unity_report.json"
RIGS = ["main", "L0", "L1", "L2", "L3"]
RUN2 = OUT + "/run2"          # 修正の前（run2）の控え
B43 = REPO + "/Unity/Assets/GreatWave/Design43/Data/ds43_boats.json"
LEV = ["L0", "L1", "L2", "L3"]
NAME_EN = {"L0": "L0 level hold (min heave)", "L1": "L1 + weak heave", "L2": "L2 + turn", "L3": "L3 + tilt"}
COL = {"boat": (150, 150, 150), "L0": (180, 110, 30), "L1": (60, 150, 40), "L2": (30, 140, 230), "L3": (40, 40, 200), "main": (20, 20, 20)}
HANDS = np.array([[-0.25, -0.45, 0.35], [0.25, -0.45, 0.35]])


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def qrot(q, v):
    """q (N,4) xyzw、v (N,3) or (3,)"""
    u = q[:, :3]
    w = q[:, 3:4]
    v = np.broadcast_to(v, u.shape)
    t = 2.0 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def qmul(a, b):
    ax, ay, az, aw = a.T
    bx, by, bz, bw = b.T
    return np.stack([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz], 1)


def qyaw(deg):
    h = np.radians(np.asarray(deg, np.float64)) / 2
    z = np.zeros_like(h)
    return np.stack([z, np.sin(h), z, np.cos(h)], -1)


def ang_step(q):
    d = np.abs(np.sum(q[1:] * q[:-1], 1))
    return np.degrees(2 * np.arccos(np.clip(d, -1, 1)))


def acc30(p):
    a = np.full_like(p, np.nan)
    a[1:-1] = (p[2:] - 2 * p[1:-1] + p[:-2]) * 900.0
    return a


def load():
    with open(UNITY + "/ds45_rider.csv", encoding="utf-8") as f:
        rd = csv.reader(f)
        hdr = next(rd)
        rows = list(rd)
    idx = {k: i for i, k in enumerate(hdr)}
    num = {}
    for k, i in idx.items():
        if k == "cmd":
            num[k] = np.array([r[i] for r in rows])
        else:
            num[k] = np.array([float(r[i]) if r[i] not in ("", "null") else np.nan for r in rows])
    with open(UNITY + "/ds45_heave30.csv", encoding="utf-8") as f:
        rd = csv.reader(f)
        h2 = next(rd)
        hv = np.array([[float(x) for x in r] for r in rd])
    heave = {k: hv[:, i] for i, k in enumerate(h2)}
    return num, heave


def stats(x, m):
    x = np.abs(x[m])
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return {"max": None, "p95": None}
    return {"max": round(float(x.max()), 4), "p95": round(float(np.percentile(x, 95)), 4)}


def main():
    t0 = time.time()
    cfg = json.load(open(CFG, encoding="utf-8"))
    rep = json.load(open(UNITY + "/ds45_unity_report.json", encoding="utf-8"))
    r44 = json.load(open(R44, encoding="utf-8"))
    s_h, s_f = float(r44["handoverS"]), float(r44["formationStartS"])
    t_star = s_f + 12.0
    num, heave = load()
    s = num["s"]
    N = len(s)
    fr = np.arange(3, N, 4)            # 各コマの終わりの段（s = n/30、n = 1..）
    s30 = s[fr]
    secs = {"steering_0_70": (0.0, s_h), "approach_70_sf": (s_h, s_f), "formation_sf_tstar": (s_f, t_star), "hold_tstar_end": (t_star, s[-1] + 1e-6), "all": (0.0, s[-1] + 1e-6)}
    be = np.stack([num["bex"], num["bey"], num["bez"]], 1)
    bq = np.stack([num["bqx"], num["bqy"], num["bqz"], num["bqw"]], 1)
    seat_off = cfg["seatYawOffsetDeg"]
    ser = {"boat": {"p": be, "q": qmul(bq, qyaw(np.full(N, seat_off))), "yaw": num["boatYaw"] + seat_off, "tilt": num["boatTilt"]}}
    for r in RIGS:
        ser[r] = {"p": np.stack([num[r + "_x"], num[r + "_y"], num[r + "_z"]], 1), "q": np.stack([num[r + "_qx"], num[r + "_qy"], num[r + "_qz"], num[r + "_qw"]], 1),
                  "yaw": num[r + "_yaw"], "tilt": num[r + "_tilt"], "devV": num[r + "_devV"], "devH": num[r + "_devH"],
                  "cam": np.stack([num[r + "_cx"], num[r + "_cy"], num[r + "_cz"]], 1)}
    # 着座（修正の回）：乗客の目を船の枠で座席の目から測る（船の根の回転の逆で回す）。120 Hz の全段
    gun = float(cfg["seatEyeAboveGunwaleM"])
    bqi = bq * np.array([-1.0, -1.0, -1.0, 1.0])
    seat_frame = {r: qrot(bqi, ser[r]["p"] - be) for r in RIGS}
    # 30 Hz の値
    M = {}
    for k, v in ser.items():
        p = v["p"][fr]
        a = acc30(p)
        q = v["q"][fr]
        w = np.concatenate([[np.nan], ang_step(q) * 30.0])
        yr = np.gradient(v["yaw"][fr], s30)
        M[k] = {"ay": a[:, 1], "ah": np.hypot(a[:, 0], a[:, 2]), "w": w, "yawRate": yr, "tilt": v["tilt"][fr]}
    lv = {}
    for k in ["boat"] + LEV + ["main"]:
        d = {}
        for sk, (a, b) in secs.items():
            m = (s30 >= a) & (s30 < b)
            d[sk] = {"accVert_mps2": stats(M[k]["ay"], m), "accHoriz_mps2": stats(M[k]["ah"], m), "angSpeed_degps": stats(M[k]["w"], m),
                     "yawRate_degps": stats(M[k]["yawRate"], m), "tilt_deg": stats(M[k]["tilt"], m)}
            if k != "boat":
                dev = np.linalg.norm(ser[k]["p"][fr] - be[fr], axis=1)
                d[sk]["eyeFromSeatEye_m"] = stats(dev, m)
                d[sk]["eyeFromSeatEyeVert_m"] = stats(ser[k]["p"][fr][:, 1] - be[fr][:, 1], m)
                # 着座（修正の回）：船の枠の上向きの成分（120 Hz の全段）と船縁の上端
                m120 = (s >= a) & (s < b)
                ub = seat_frame[k][m120]
                d[sk]["eyeInBoatFrameUp_m"] = {"min": round(float(ub[:, 1].min()), 4), "max": round(float(ub[:, 1].max()), 4)}
                d[sk]["eyeInBoatFrameHoriz_m_max"] = round(float(np.hypot(ub[:, 0], ub[:, 2]).max()), 4)
                d[sk]["eyeBelowGunwaleTop_fraction"] = round(float(np.mean(ub[:, 1] < -gun)), 4)
                # 手の到達位置（乗客の枠の左右の手 ±0.25, −0.45, +0.35 m）が、船に固定した座席の枠に対してずれる量
                hd = []
                for h in HANDS:
                    pr = ser[k]["p"][fr] + qrot(ser[k]["q"][fr], h)
                    pa = be[fr] + qrot(ser["boat"]["q"][fr], h)
                    hd.append(np.linalg.norm(pr - pa, axis=1))
                d[sk]["handsVsBoatSeatFrame_m"] = stats(np.maximum(hd[0], hd[1]), m)
        lv[k] = d
    # t* と終わりの目のずれ
    i_star = int(np.argmin(np.abs(s30 - t_star)))
    at_star = {k: {"eyeFromSeatEye_m": round(float(np.linalg.norm(ser[k]["p"][fr][i_star] - be[fr][i_star])), 4), "tilt_deg": round(float(ser[k]["tilt"][fr][i_star]), 3),
                   "yawMinusSeatYaw_deg": round(float(ser[k]["yaw"][fr][i_star] - ser["boat"]["yaw"][fr][i_star]), 3)} for k in LEV + ["main"]}
    at_end = {k: {"eyeFromSeatEye_m": round(float(np.linalg.norm(ser[k]["p"][-1] - be[-1])), 4)} for k in LEV + ["main"]}
    cam_eq = max(float(np.abs(ser[k]["cam"] - ser[k]["p"]).max()) for k in RIGS)

    # 切り替えの跳び（主の乗客、120 Hz の段ごと）
    mq = ser["main"]["q"]
    rot_step = np.concatenate([[0.0], ang_step(mq)])
    rel = ser["main"]["p"] - be
    rel_step = np.concatenate([[0.0], np.linalg.norm(np.diff(rel, axis=0), axis=1)])
    cmd = num["cmd"]
    sw = []
    reset_idx = [i for i, c in enumerate(cmd) if "reset" in c]
    for i, c in enumerate(cmd):
        if not c:
            continue
        m = (s >= s[i] - 1e-9) & (s <= s[i] + cfg["blendS"] + 0.25)
        is_reset = "reset" in c
        mm = m.copy()
        if is_reset:
            mm[i] = False
        # 比べる値：同じ窓で段を固定した乗客の段ごとの回転の大きい方
        lv_from = int(num["level"][i - 1]) if i > 0 else 0
        lv_to = int(num["level"][i])
        ref = max(float(np.concatenate([[0.0], ang_step(ser["L%d" % lv_from]["q"])])[m].max()), float(np.concatenate([[0.0], ang_step(ser["L%d" % lv_to]["q"])])[m].max()))
        refr = 0.0
        for L in ("L%d" % lv_from, "L%d" % lv_to):
            rr = ser[L]["p"] - be
            refr = max(refr, float(np.concatenate([[0.0], np.linalg.norm(np.diff(rr, axis=0), axis=1)])[m].max()))
        sw.append({"s": round(float(s[i]), 4), "cmd": c, "from": "L%d" % lv_from, "to": "L%d" % lv_to, "reset": is_reset,
                   "maxRotPerStep_deg": round(float(rot_step[mm].max()), 5), "fixedLevelsMaxRotPerStep_deg": round(ref, 5),
                   "maxRelMovePerStep_m": round(float(rel_step[mm].max()), 5), "fixedLevelsMaxRelMovePerStep_m": round(refr, 5),
                   "resetSnap_deg": round(float(rot_step[i]), 3) if is_reset else None})
    rot_lim, rel_lim = 0.5, 0.01
    no_jump = all((w["maxRotPerStep_deg"] <= max(rot_lim, w["fixedLevelsMaxRotPerStep_deg"] + 0.05)) and w["maxRelMovePerStep_m"] <= max(rel_lim, w["fixedLevelsMaxRelMovePerStep_m"] + 0.002) for w in sw)
    # 段の時間の並び（予定どおりか）
    expect = [0] * 12 + [1] * 12 + [2] * 12 + [3] * 18 + [2] * 6 + [1] * 6 + [0] * 18 + [3] * 4 + [0] * 6
    got = rep["levelTimelineS"]
    timeline_ok = got[:len(expect)] == expect[:len(got)]

    # 設計30 の座席の上下
    th = heave["t"]
    hv = {"boat": heave["bey"]}
    for L in LEV:
        hv[L] = heave[L + "_y"]
    mid = [b for b in json.load(open(B43, encoding="utf-8"))["boats"] if b["key"] == "boat_mid"][0]
    q0 = np.tile(np.array(mid["rootRot"], np.float64), (len(th), 1)) * np.array([-1.0, -1.0, -1.0, 1.0])
    hbe = np.stack([heave["bex"], heave["bey"], heave["bez"]], 1)
    h30 = {}
    for k, y in hv.items():
        a = np.full_like(y, np.nan)
        a[1:-1] = (y[2:] - 2 * y[1:-1] + y[:-2]) * 900.0
        e = {"accVert_mps2": stats(a, np.ones_like(a, bool)), "rangeY_m": round(float(y.max() - y.min()), 4)}
        if k != "boat":
            e["eyeFromSeatEyeVert_m"] = stats(y - hv["boat"], np.ones_like(y, bool))
            e["tilt_deg_max"] = round(float(np.abs(heave[k + "_tilt"]).max()), 4)
            ub = qrot(q0, np.stack([heave[k + "_x"], heave[k + "_y"], heave[k + "_z"]], 1) - hbe)
            e["eyeInBoatFrameUp_m"] = {"min": round(float(ub[:, 1].min()), 4), "max": round(float(ub[:, 1].max()), 4)}
            e["eyeBelowGunwaleTop_fraction"] = round(float(np.mean(ub[:, 1] < -gun)), 4)
        h30[k] = e
    for L in LEV:
        h30[L]["accMaxRatioToBoat"] = round(h30[L]["accVert_mps2"]["max"] / h30["boat"]["accVert_mps2"]["max"], 4)

    # 着座の判定（修正の回。計画の最小の受入の外の確認）：全段・全区間で、目が船の枠の頭打ち（上 maxDevUpM・下 maxDevDownM）の中にあり、船縁の上端より上
    up_lim, dn_lim = float(cfg["maxDevUpM"]), float(cfg["maxDevDownM"])
    seat_all = {r: {"upMin_m": round(float(seat_frame[r][:, 1].min()), 4), "upMax_m": round(float(seat_frame[r][:, 1].max()), 4),
                    "horizMax_m": round(float(np.hypot(seat_frame[r][:, 0], seat_frame[r][:, 2]).max()), 4),
                    "belowGunwaleTop_fraction": round(float(np.mean(seat_frame[r][:, 1] < -gun)), 4)} for r in RIGS}
    seated_ok = all(v["upMin_m"] >= -dn_lim - 1e-3 and v["upMax_m"] <= up_lim + 1e-3 and v["belowGunwaleTop_fraction"] == 0.0 for v in seat_all.values()) and \
        all(h30[L]["eyeBelowGunwaleTop_fraction"] == 0.0 and h30[L]["eyeInBoatFrameUp_m"]["min"] >= -dn_lim - 1e-3 for L in LEV)
    acc_ratio = {}
    for L in LEV:
        acc_ratio[L] = {sk: (round(lv[L][sk]["accVert_mps2"]["max"] / lv["boat"][sk]["accVert_mps2"]["max"], 4) if lv["boat"][sk]["accVert_mps2"]["max"] else None) for sk in ("formation_sf_tstar", "hold_tstar_end")}
        acc_ratio[L]["heave30"] = h30[L]["accMaxRatioToBoat"]
    run2_seat = None
    if os.path.exists(RUN2 + "/metrics.json"):
        m2 = json.load(open(RUN2 + "/metrics.json", encoding="utf-8"))
        run2_seat = {"noteJa": "修正の前（run2。控えは Build/Design/45/comfort/run2）。独立の検査が数えた値：形成の間、目は船の枠で L0 −0.576〜+0.557 m、L1〜L3 −0.517〜+0.500 m、船縁の上端より下 L0 53.8%・L1〜L3 46.7%",
                     "heave30AccMax": {L: m2["backlog85_heaveScale"]["heave30"][L]["accVert_mps2"]["max"] for L in LEV},
                     "formationAccMax": {L: m2["run44Replay"]["byLevel"][L]["formation_sf_tstar"]["accVert_mps2"]["max"] for L in LEV}}

    codecheck = json.load(open(OUT + "/codecheck.json", encoding="utf-8"))
    struct_ok = rep["riderRootIsSceneRoot"] and rep["boatRootIsSceneRoot"] and rep["notAncestorEitherWay"] and rep["chainOk"] and rep["trackedPoseDriverOnHmd"]
    refs_ok = sorted(x.split("（")[0] for x in rep["hmdCameraReferencedBy"]) == ["DS45RiderComfort.hmdCamera", "XROrigin.m_Camera"]
    hmd_ok = rep["hmdLocalPosMaxAbsChange"] == 0 and rep["hmdLocalRotMaxAngleDeg"] == 0
    levels_ok = rep["inputPath"] == "InputState.Change" and timeline_ok and rep["resetCount"] == 2 and no_jump

    metrics = {
        "schema": "GreatWave.DS45.metrics/1",
        "number": "設計45 乗客の揺れを一種類ずつ調整する（part comfort）",
        "noteJa": "PC の batchmode の記録から数え直した値（HMD 実機ではない）。船の動きは設計44 の run3 の記録（物理は解き直していない）。加速度は 30 Hz の位置の 2 階差分。段の値（kV・kTilt など）は進行役の調整値（D45-5）。",
        "gates": [
            {"item": "4 段を切り替えられる（計画 §2.4 の最小の受入）", "value": {"inputPath": rep["inputPath"], "switchLog": rep["switchLog"], "levelTimelineMatches": timeline_ok, "resetCount": rep["resetCount"], "noJumpAtSwitch": no_jump,
                                                                   "jumpRuleJa": "切り替えの窓（押してから blendS + 0.25 s）で、段ごとの回転 ≤ max(0.5°, 段を固定した 2 つの乗客の最大 + 0.05°)、船の目に対する乗客の目の動き ≤ max(1 cm、段を固定した 2 つの乗客の最大 + 2 mm)／段（1/120 s）。座席リセットの段そのものは除く（利用者の操作による瞬時の向きの戻し。量は resetSnap_deg）。閾値は進行役が決めた（D45-7）"},
             "result": "合格" if levels_ok else "不合格"},
            {"item": "HMD Camera のローカル姿勢に手を入れていない（コードの検査）", "value": {"staticCodeCheckPassed": codecheck["passed"], "runtimeWrites": [w["receiver"] + "." + w["member"] + "（" + w["file"] + ":" + str(w["line"]) + "）" for w in codecheck["runtimeWrites"]],
                                                                          "hmdLocalPosMaxAbsChange": rep["hmdLocalPosMaxAbsChange"], "hmdLocalRotMaxAngleDeg": rep["hmdLocalRotMaxAngleDeg"], "hmdChecks": rep["hmdChecks"],
                                                                          "hmdCameraReferencedBy": rep["hmdCameraReferencedBy"], "structureSiblingsOk": struct_ok},
             "result": "合格" if (codecheck["passed"] and hmd_ok and refs_ok and struct_ok) else "不合格"},
            {"item": "着座（修正の回の確認。計画の最小の受入の外）：どの段でも、目は船の枠で座席の目から上 maxDevUpM・下 maxDevDownM の中、船縁の上端（座席の目の 0.149 m 下。設計41）より上", "value": {"maxDevUpM": up_lim, "maxDevDownM": dn_lim, "maxDevHM": cfg["maxDevHM"], "seatEyeAboveGunwaleM": gun, "run44ReplayAllSteps": seat_all,
                                                                                 "heave30": {L: {"eyeInBoatFrameUp_m": h30[L]["eyeInBoatFrameUp_m"], "belowGunwaleTop_fraction": h30[L]["eyeBelowGunwaleTop_fraction"]} for L in LEV},
                                                                                 "accMaxRatioToBoat": acc_ratio, "run2BeforeFix": run2_seat},
             "result": "合格" if seated_ok else "不合格"},
            {"item": "H5（唇が頭上を越えるときの快適性、PS VR2）", "value": "PS VR2 は未導入（利用者の手）。PC の代わりの動画（4 段の並べ、頭を 30° 上げた視点）と Mock の両目の静止画（stereo_ds45_mock.png、±%.3f m）だけ" % (cfg["test"].get("ipdM", 0.064) / 2), "result": "保留"},
            {"item": "H7（再センタリング・停止・復帰のアプリ側＝座席リセット、PS VR2）", "value": {"recenterMaxPosErrM": rep["recenterMaxPosErrM"], "recenterMaxYawErrDeg": rep["recenterMaxYawErrDeg"], "recenterCases": rep["recenterCases"], "resetCountInRun": rep["resetCount"]},
             "result": "保留（計算の検査は済み。実機は未検証）"},
            {"item": "利用者の試遊記録（PS VR2、約 1 時間）", "value": "PS VR2 は未導入。PC の代わりの動画だけ", "result": "保留"},
        ],
        "backlog85_heaveScale": {"noteJa": "バックログ 85（上下動の倍率、記録）。段ごとの kV と、設計30 の座席の上下（最大 約 6 m/s²）・設計44 の物理の船を入れた時の乗客の上下の加速度", "kV": {L["key"]: L["kV"] for L in cfg["levels"]},
                                 "heave30": h30, "result": "記録のみ"},
        "run44Replay": {"sections_s": {k: [round(a, 4), round(b, 4)] for k, (a, b) in secs.items()}, "byLevel": lv, "atTstar": at_star, "atEnd": at_end, "switches": sw,
                        "cameraWorldEqualsRiderRootMaxM": cam_eq, "result": "記録のみ"},
        "sources": {"boatStepsCsv": {"path": "Unity/Build/Design/44/steer/unity/ds44_steps.csv", "sha256": rep["boatStepsSha256"]},
                    "boatFramesJsonl": {"path": "Unity/Build/Design/44/steer/unity/ds44_frames.jsonl", "sha256": rep["boatFramesSha256"]},
                    "heave30": {"path": "Unity/Build/Design/30/sea/boat_support.json", "sha256": rep["heave30Sha256"]}},
    }
    with open(OUT + "/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)

    # ---------------------------------------------------------------- 図
    W, H = 1920, 1080
    img = np.full((H, W, 3), 250, np.uint8)
    cv2.putText(img, "Design 45 rider comfort (PC batchmode, not HMD). Boat motion = Design 44 run3 log; rider = RiderComfortRoot (4 levels).", (40, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 1, cv2.LINE_AA)
    xt = list(range(0, 95, 10))
    pw, ph = 860, 250
    X0, X1 = 70, 1010
    Ys = [80, 420, 760]

    def spans(p):
        p.span(0, s_h, (224, 240, 232)); p.span(s_h, s_f, (247, 230, 210)); p.span(s_f, t_star, (210, 230, 247)); p.span(t_star, s[-1], (238, 238, 238))
        for x in (s_h, s_f, t_star):
            p.vline(x)
    p = Panel(img, X0, Ys[0], pw, ph, (0, s[-1]), (-0.5, 3.5), "active level of the main rider (keys 1-4 / d-pad), black ticks = switch, red = seat reset", "level")
    spans(p)
    p.line(s[::4], num["level"][::4], COL["main"], 2)
    for w in sw:
        if w["reset"]:
            X = p.X(w["s"])
            cv2.line(img, (X, p.y0), (X, p.y0 + p.h), (0, 0, 235), 3)
        else:
            p.vline(w["s"], (20, 20, 20), dashed=False)
    p.axes(xt, [0, 1, 2, 3])
    p = Panel(img, X1, Ys[0], pw, ph, (0, s[-1]), (0, 30), "|vertical accel| of the eye (m/s^2, 30 Hz): grey boat seat eye, blue L0, green L1 (=L2,L3)", "m/s2")
    spans(p)
    p.line(s30, np.abs(M["boat"]["ay"]), COL["boat"], 1)
    p.line(s30, np.abs(M["L1"]["ay"]), COL["L1"], 1)
    p.line(s30, np.abs(M["L0"]["ay"]), COL["L0"], 2)
    p.axes(xt, [0, 10, 20, 30])
    yl = (min(np.nanmin(ser["boat"]["yaw"]), np.nanmin(ser["L0"]["yaw"])) - 10, max(np.nanmax(ser["boat"]["yaw"]), np.nanmax(ser["L0"]["yaw"])) + 10)
    p = Panel(img, X0, Ys[1], pw, ph, (0, s[-1]), yl, "rider yaw (deg): grey = seat facing on the boat, blue L0/L1 (world-fixed), orange L2/L3 (follows), black main", "deg")
    spans(p)
    p.line(s30, ser["boat"]["yaw"][fr], COL["boat"], 3)
    p.line(s30, ser["L0"]["yaw"][fr], COL["L0"], 2)
    p.line(s30, ser["L2"]["yaw"][fr], COL["L2"], 1)
    p.line(s30, ser["main"]["yaw"][fr], COL["main"], 1)
    step = 30 if yl[1] - yl[0] > 120 else 15
    p.axes(xt, list(range(int(math.ceil(yl[0] / step) * step), int(yl[1]) + 1, step)))
    p = Panel(img, X1, Ys[1], pw, ph, (0, s[-1]), (-0.25, 0.25), "eye from seat eye along the boat's up axis (m): blue L0, green L1; dashed = cap +-%.2f, red = gunwale top (-%.3f)" % (up_lim, gun), "m")
    spans(p)
    p.line(s[::4], seat_frame["L1"][::4, 1], COL["L1"], 1)
    p.line(s[::4], seat_frame["L0"][::4, 1], COL["L0"], 2)
    p.hline(up_lim, (90, 90, 90), dashed=True); p.hline(-dn_lim, (90, 90, 90), dashed=True); p.hline(-gun, (0, 0, 220), dashed=False)
    p.axes(xt, [-0.2, -0.1, 0.0, 0.1, 0.2], fmt_y="%.1f")
    ylo, yhi = float(min(hv[k].min() for k in hv)) - 0.3, float(max(hv[k].max() for k in hv)) + 0.3
    p = Panel(img, X0, Ys[2], pw, ph, (0, th[-1]), (ylo, yhi), "Design 30 seat heave (boat_support.json): eye height (m), grey boat, blue L0, green L1-L3", "m")
    p.span(12.0, th[-1], (238, 238, 238)); p.vline(12.0)
    p.line(th, hv["boat"], COL["boat"], 3)
    p.line(th, hv["L1"], COL["L1"], 2)
    p.line(th, hv["L0"], COL["L0"], 2)
    p.axes(list(range(0, 15, 2)), [round(x, 1) for x in np.linspace(ylo, yhi, 5)], fmt_y="%.1f")
    p = Panel(img, X1, Ys[2], pw, ph, (0, th[-1]), (0, 8), "Design 30 seat heave: |vertical accel| (m/s^2, 30 Hz), grey boat (max %.2f), blue L0 (%.2f), green L1 (%.2f)" % (h30["boat"]["accVert_mps2"]["max"], h30["L0"]["accVert_mps2"]["max"], h30["L1"]["accVert_mps2"]["max"]), "m/s2")
    p.span(12.0, th[-1], (238, 238, 238)); p.vline(12.0)
    for k in ("boat", "L1", "L0"):
        y = hv[k]
        a = np.full_like(y, np.nan)
        a[1:-1] = np.abs(y[2:] - 2 * y[1:-1] + y[:-2]) * 900.0
        p.line(th, a, COL[k], 2 if k != "boat" else 1)
    p.axes(list(range(0, 15, 2)), [0, 2, 4, 6, 8])
    cv2.putText(img, "s (s): green = steering 0-70 | light blue = fixed trajectory lead | tan = formation t 0-12 | grey = hold at t*.  Bottom row: t (s) of the Design 30 single playback.", (40, H - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
    cv2.imwrite(OUT + "/fig_ds45_comfort.png", img)

    # ---------------------------------------------------------------- 静止画（4 段 × 4 つの時刻）
    moments = [("s 30 steering, boat turned", 30.0), ("s 84 formation", 84.0), ("t* %.2f" % t_star, t_star), ("end of hold", s[-1] - 0.05)]
    tw, thh = 480, 270
    st = np.full((1080, 1920, 3), 245, np.uint8)
    for j, (lab, sm) in enumerate(moments):
        n = int(round(sm * 30))
        for i, L in enumerate(LEV):
            im = cv2.imread("%s/%s_%04d.jpg" % (FRAMES, L, n))
            im = cv2.resize(im, (tw, thh), interpolation=cv2.INTER_AREA)
            put(im, NAME_EN[L], (8, 22), 0.5)
            put(im, lab, (8, thh - 10), 0.45)
            st[j * thh:(j + 1) * thh, i * tw:(i + 1) * tw] = im
    cv2.imwrite(OUT + "/stills_ds45_levels.png", st)

    # 修正の前後（run2 の控えのコマと run3 のコマ。同じ時刻・同じ見上げのカメラ）
    n_star = 2750   # run2 の控えに残したコマ（s 91.667 = t* + 0.02 s）
    fa = np.full((1080, 1920, 3), 245, np.uint8)
    rows_ba = [("run2 (before fix) s 86.67", RUN2 + "/frames", 2600), ("run3 (after fix) s 86.67", FRAMES, 2600),
               ("run2 (before fix) s 91.67 (t*+0.02)", RUN2 + "/frames", n_star), ("run3 (after fix) s 91.67 (t*+0.02)", FRAMES, n_star)]
    ba_ok = True
    for j, (lab, d_, n) in enumerate(rows_ba):
        for i, L in enumerate(LEV):
            im = cv2.imread("%s/%s_%04d.jpg" % (d_, L, n))
            if im is None:
                ba_ok = False
                continue
            im = cv2.resize(im, (tw, thh), interpolation=cv2.INTER_AREA)
            put(im, NAME_EN[L], (8, 22), 0.5)
            put(im, lab, (8, thh - 10), 0.45)
            fa[j * thh:(j + 1) * thh, i * tw:(i + 1) * tw] = im
    if ba_ok:
        cv2.imwrite(OUT + "/fix_ds45_seated_before_after.png", fa)
    # Mock の両目（試験だけ。見上げのカメラを右向きに ±ipd/2。HMD の代わり）
    stn = [min(rep["frames"] - 1, int(round(x * 30))) for x in cfg["test"].get("stereoS", [])]
    if stn:
        sm = np.full((1080, 1920, 3), 245, np.uint8)
        for j, n in enumerate(stn[:4]):
            for i, (L, e) in enumerate((("L0", "L"), ("L0", "R"), ("L3", "L"), ("L3", "R"))):
                im = cv2.imread("%s/stereo_%s_%04d_%s.jpg" % (FRAMES, L, n, e))
                if im is None:
                    continue
                im = cv2.resize(im, (tw, thh), interpolation=cv2.INTER_AREA)
                put(im, "%s  %s eye (IPD %.3f m)" % (NAME_EN[L], "left" if e == "L" else "right", cfg["test"].get("ipdM", 0.064)), (8, 22), 0.45)
                put(im, "s %.2f  %s" % (n / 30.0, "Mock stereo, PC, not HMD"), (8, thh - 10), 0.45)
                sm[j * thh:(j + 1) * thh, i * tw:(i + 1) * tw] = im
        cv2.imwrite(OUT + "/stereo_ds45_mock.png", sm)

    # ---------------------------------------------------------------- 動画
    def phase(sx):
        if sx < s_h:
            return "STEERING (Design 44)"
        if sx < s_f:
            return "FIXED TRAJECTORY"
        if sx < t_star:
            return "FORMATION t = %.2f s" % (sx - s_f)
        return "HOLD at t*"
    nF = rep["frames"]
    lvl_by_frame = np.concatenate([[0], num["level"][fr]]).astype(int)
    cmd_by_frame = {}
    for w in sw:
        cmd_by_frame[int(math.floor(w["s"] * 30 + 1e-6))] = w

    def enc(path, size):
        return subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % size, "-r", "30", "-i", "-",
                                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast", path], stdin=subprocess.PIPE)
    pg = enc(OUT + "/ds45_levels_grid_30fps.mp4", (1920, 1080))
    pm = enc(OUT + "/ds45_main_switching_30fps.mp4", (1280, 720))
    last_cmd = None
    for n in range(nF):
        sx = n / 30.0
        canvas = np.zeros((1080, 1920, 3), np.uint8)
        for i, L in enumerate(LEV):
            im = cv2.imread("%s/%s_%04d.jpg" % (FRAMES, L, n))
            im = cv2.resize(im, (960, 540), interpolation=cv2.INTER_LINEAR)
            put(im, NAME_EN[L], (12, 30), 0.8, thick=2)
            canvas[(i // 2) * 540:(i // 2 + 1) * 540, (i % 2) * 960:(i % 2 + 1) * 960] = im
        put(canvas, "s %.2f  %s   rider camera looking 30 deg up (test only)   PC batchmode, not HMD" % (sx, phase(sx)), (12, 1070), 0.7)
        pg.stdin.write(canvas.tobytes())
        im = cv2.imread("%s/main_%04d.jpg" % (FRAMES, n))
        im = cv2.resize(im, (1280, 720), interpolation=cv2.INTER_LINEAR)
        L = "L%d" % lvl_by_frame[n]
        put(im, "main rider: " + NAME_EN[L], (14, 34), 0.9, thick=2)
        if n in cmd_by_frame:
            last_cmd = (n, cmd_by_frame[n])
        if last_cmd and n - last_cmd[0] < 60:
            w = last_cmd[1]
            put(im, ("SEAT RESET (%s)" % w["cmd"].split("@")[1]) if w["reset"] else ("switch %s -> %s (%s)" % (w["from"], w["to"], w["cmd"].split("@")[1])), (14, 76), 0.8, (120, 230, 255), 2)
        put(im, "s %.2f  %s" % (sx, phase(sx)), (14, 706), 0.7)
        pm.stdin.write(im.tobytes())
    for pp in (pg, pm):
        pp.stdin.close()
        pp.wait()

    # ---------------------------------------------------------------- run.json
    outs = ["metrics.json", "codecheck.json", "fig_ds45_comfort.png", "stills_ds45_levels.png", "fix_ds45_seated_before_after.png", "stereo_ds45_mock.png", "ds45_levels_grid_30fps.mp4", "ds45_main_switching_30fps.mp4",
            "unity/ds45_rider.csv", "unity/ds45_heave30.csv", "unity/ds45_unity_report.json"]
    ins = ["Unity/Assets/GreatWave/Design45/Data/ds45_comfort.json", "Unity/Assets/GreatWave/Design45/Scripts/DS45ComfortConfig.cs", "Unity/Assets/GreatWave/Design45/Scripts/DS45ComfortSolver.cs",
           "Unity/Assets/GreatWave/Design45/Scripts/DS45ComfortInput.cs", "Unity/Assets/GreatWave/Design45/Scripts/DS45RiderComfort.cs", "Unity/Assets/GreatWave/Design45/Editor/DS45ComfortTest.cs",
           "Unity/Assets/GreatWave/Design45/Scenes/DS45_Comfort.unity", "Tools/GWWaveGen/ds45/ds45_codecheck.py", "Tools/GWWaveGen/ds45/ds45_report.py", "Tools/GWWaveGen/ds45/run_ds45_unity.ps1",
           "Unity/Build/Design/44/steer/unity/ds44_steps.csv", "Unity/Build/Design/44/steer/unity/ds44_frames.jsonl", "Unity/Build/Design/30/sea/boat_support.json", "Tools/GWContext/seat_v1.json",
           "Unity/Assets/GreatWave/Design44/Scenes/DS44_Steer.unity"]
    run = {"schema": "GreatWave.DS45.run/1",
           "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds45/run_ds45_unity.ps1 -Method GreatWave.Design45.EditorTools.DS45ComfortTest.Run -Log run3（修正の回。run1・run2 の控えは Build/Design/45/comfort/run1・run2）",
                        "py -3.10 Tools/GWWaveGen/ds45/ds45_codecheck.py", "py -3.10 Tools/GWWaveGen/ds45/ds45_report.py"],
           "tools": {"unity": rep["unity"], "graphics": rep["device"] + " " + rep["graphicsApi"], "python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__,
                     "ffmpeg": FFMPEG},
           "unitySeconds": rep["secondsTotal"], "reportSeconds": round(time.time() - t0, 1),
           "inputs": {p: sha(os.path.join(REPO, p)) for p in ins},
           "outputs": {p: sha(os.path.join(OUT, p)) for p in outs if os.path.exists(os.path.join(OUT, p))}}
    with open(OUT + "/run.json", "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("DS45_REPORT levels=%s code=%s seated=%s hmd=%s refs=%s struct=%s timeline=%s noJump=%s seconds=%.1f" % (
        metrics["gates"][0]["result"], metrics["gates"][1]["result"], metrics["gates"][2]["result"], hmd_ok, refs_ok, struct_ok, timeline_ok, no_jump, time.time() - t0))


if __name__ == "__main__":
    main()
