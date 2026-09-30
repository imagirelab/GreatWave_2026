# -*- coding: utf-8 -*-
"""設計44 の記録の道具：作る部の出力の SHA-256 を照合し、剛体の記録から数え直し、証拠を写し、記録の metrics.json・run.json を書く。

- 照合：作る部の run.json の inputs（コードと表）と outputs（動画・図・記録）の SHA-256 を読み直して比べる（違えば止まる）。
- 数え直し（作る部の ds44_measure.py・ds44_model.py・ds44_report.py を使わない）：unity/ds44_steps.csv（120 Hz）の位置・四元数・速度から、
  船首の向き・水平の速さ・引き継ぎの前後の 1 段の変化・閾値を超える段の数（±1 s、引き継ぎ〜形成の始まり、形成と保持）、
  根の進む向き（位置の差）の段、操船の間の d の最大（記録の列）、t* の位置・向き・速さのずれ、傾きの最大、浮力点がすべて水の外の段。
  unity/ds44_frames.jsonl から座席の目の余裕（目の高さ − 目の下の表示面の最も高い交わり）。
  場面 DS44_Steer.unity の stepInFixedUpdate・隠したもの・GUID の依存。
- 証拠：Docs/Evidence/Design/44/ へ写す（図・静止画は 1920 × 1080 の PNG、動画は 5 MB 以下、JSON）。
  引き継ぎの前後の追う視点の 4 コマ（動画のコマ 2098〜2101、s 69.93〜70.03）を 1920 × 1080 の PNG に並べる。
コミットの一覧の点検は、禁止の場所の文字列を持つので、この道具に入れず Git 対象外の Unity/Build/Design/44/record/ds44_commit_scan.py で行う。
使い方：py -3.10 -B Tools/GWWaveGen/ds44/ds44_record.py
PC の batchmode の出力を読むだけで、Unity と HMD は使わない。git も使わない。
"""
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B44 = os.path.join(REPO, "Unity", "Build", "Design", "44")
OUT = os.path.join(B44, "steer")
IND = os.path.join(B44, "indep_check")
REC = os.path.join(B44, "record")
EVD = os.path.join(REPO, "Docs", "Evidence", "Design", "44")
ASSETS = os.path.join(REPO, "Unity", "Assets")
SCENE = os.path.join(ASSETS, "GreatWave", "Design44", "Scenes", "DS44_Steer.unity")
BASE_SCENE = os.path.join(ASSETS, "GreatWave", "Design30", "Scenes", "DS30_SinglePlayback.unity")
CFG = os.path.join(ASSETS, "GreatWave", "Design44", "Data", "ds44_steer.json")
DT = 1.0 / 120.0
TH_HEAD, TH_SPEED = 0.125, 0.0125      # 作る部の閾値（D44-7）


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def dump(p, d):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def rel(p):
    return os.path.relpath(p, REPO).replace(os.sep, "/")


def hms(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


def verify(run):
    rows, bad = [], []
    items = dict(run["inputs"])
    items.update({k: v["sha256"] for k, v in run["outputs"].items()})
    for k, v in items.items():
        p = os.path.join(REPO, k)
        got = sha(p) if os.path.exists(p) else None
        rows.append(dict(path=k, expected=v, same=got == v))
        if got != v:
            bad.append(k)
    return rows, bad


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def steps(sub="unity"):
    with open(os.path.join(OUT, sub, "ds44_steps.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    txt = ("mode", "playState", "src")
    return {k: (np.array([r[k] for r in rows]) if k in txt else
                np.array([float(r[k]) if r[k] not in ("", "null") else np.nan for r in rows])) for k in rows[0]}


def recount():
    S = steps()
    cfg = load(CFG)
    P = cfg["painting"]
    s, mode = S["s"], S["mode"]
    qx, qy, qz, qw = S["qx"], S["qy"], S["qz"], S["qw"]
    head = np.degrees(np.arctan2(2 * (qx * qz + qw * qy), 1 - 2 * (qx * qx + qy * qy)))
    tilt = np.degrees(np.arccos(np.clip(1 - 2 * (qx * qx + qz * qz), -1, 1)))
    spd = np.hypot(S["vx"], S["vz"])
    dh, dv = wrap(np.diff(head)), np.diff(spd)
    iH = int(np.argmax(mode == "Trajectory"))
    iF = int(np.argmax(S["tPlay"] >= 0))
    iA = int(np.argmin(np.abs(S["tPlay"] - 12.0) + np.where(S["tPlay"] >= 0, 0, 1e9)))
    sd = s[:-1]
    win = (sd >= s[iH] - 1.0) & (sd <= s[iH] + 1.0)
    lead = (sd >= s[iH]) & (sd < s[iF])
    form = sd >= s[iF]
    steer = (mode[:-1] == "Steering") & (mode[1:] == "Steering")

    def cnt(m):
        return dict(heading_steps_over=int((np.abs(dh[m]) > TH_HEAD).sum()), speed_steps_over=int((np.abs(dv[m]) > TH_SPEED).sum()),
                    heading_step_absmax_deg=float(np.abs(dh[m]).max()), speed_step_absmax=float(np.abs(dv[m]).max()))
    cog = np.degrees(np.arctan2(np.diff(S["x"]), np.diff(S["z"])))
    dcog = wrap(np.diff(cog))
    k = iH - 1
    st = mode == "Steering"
    hold = np.arange(len(s)) >= iA
    perr = np.hypot(S["x"] - P["x"], S["z"] - P["z"])
    wet = S["wet"]
    out = dict(
        steps=int(len(s)), dt_median=float(np.median(np.diff(s))),
        modes={m: int((mode == m).sum()) for m in sorted(set(mode.tolist()))},
        handover=dict(
            s_last_steering=float(s[iH - 1]), s_first_trajectory=float(s[iH]),
            heading_steps_prev_at_next_deg=[float(dh[k - 1]), float(dh[k]), float(dh[k + 1])],
            speed_steps_prev_at_next=[float(dv[k - 1]), float(dv[k]), float(dv[k + 1])],
            speed_at_handover=float(spd[iH - 1]), heading_at_handover_deg=float(head[iH - 1]),
            window_pm1s=cnt(win), handover_to_formation=cnt(lead), formation_and_hold=cnt(form),
            steering_phase=dict(heading_step_absmax_deg=float(np.abs(dh[steer]).max()), speed_step_absmax=float(np.abs(dv[steer]).max())),
            pivot_course_steps_deg=[float(v) for v in dcog[iH - 3:iH + 3]],
            pivot_course_step_absmax_pm1s_deg=float(np.abs(dcog[win[:-1]]).max()),
            note_ja="向き = 四元数の前の向きの水平の方位、速さ = 重心の水平の速度の大きさ（記録の vx・vz）。根の進む向き = 位置の差の方位"),
        range=dict(d_max_steering=float(np.nanmax(S["d"][st])), s_at_d_max=float(s[st][np.nanargmax(S["d"][st])])),
        formation_start=dict(s_first_tPlay_ge0=float(s[iF]), handover_plus_lead=float(load(os.path.join(OUT, "unity", "ds44_unity_report.json"))["formationStartS"])),
        arrival=dict(s=float(s[iA]), tPlay=float(S["tPlay"][iA]), pos_err_m=float(perr[iA]), yaw_err_deg=float(wrap(head[iA] - P["yawDeg"])),
                     speed=float(spd[iA]), hold_pos_err_max_m=float(perr[hold].max()), hold_yaw_err_absmax_deg=float(np.abs(wrap(head[hold] - P["yawDeg"])).max())),
        tilt=dict(max_deg=float(tilt.max()), s_at_max=float(s[tilt.argmax()]), max_steering_deg=float(tilt[st].max())),
        wet_zero_steps=int((wet == 0).sum()),
        band_part_of_R2=band_yaw(S, head),
        run1_arrival=run1_arrival(P),
        run1_vs_run2_steering_rows=steering_rows_same(),
        inputs_src=sorted(set(S["src"].tolist())))
    # 座席の目の余裕（30 fps のコマ）
    fr = [json.loads(l) for l in open(os.path.join(OUT, "unity", "ds44_frames.jsonl"), encoding="utf-8") if l.strip()]
    mg = []
    for f in fr:
        hits = f.get("eyeHits") or []
        mg.append(f["eye"][1] - max(hits) if hits else np.inf)
    mg = np.array(mg)
    out["seat_eye"] = dict(frames=len(fr), in_water_frames=int((mg < 0).sum()), no_hit_frames=int(np.isinf(mg).sum()),
                           margin_min_m=float(mg.min()), margin_min_s=float(fr[int(mg.argmin())]["s"]))
    # 場面
    txt = open(SCENE, encoding="utf-8").read()
    ls = re.search(r"m_Name: M1_Revision_LeftSupport\n(?:.*\n){0,6}?\s*m_IsActive: (\d)", txt)
    out["scene"] = dict(sha256=sha(SCENE), bytes=os.path.getsize(SCENE),
                        stepInFixedUpdate_values=[int(x) for x in re.findall(r"stepInFixedUpdate: (\d)", txt)],
                        M1_Revision_LeftSupport_m_IsActive=int(ls.group(1)) if ls else None,
                        guid_deps=guid_deps(txt))
    return out


def band_yaw(S, head, s0=43.13, s1=53.0):
    m = (S["s"] >= s0) & (S["s"] < s1)
    return dict(s=[s0, s1], heading_change_deg=float(wrap(head[m][-1] - head[m][0])), yawrate_absmax_degps=float(np.nanmax(np.abs(S["wyDeg"][m]))),
                note_ja="R2 の区間のうち帯に入った後（独立の検査の帯への入り s 43.13）。船首を勝手に回さないこと（D44-3）の確かめ")


def run1_arrival(P):
    """修正の前（run1、速度の帰還だけ）の t* のずれ。"""
    S = steps("run1")
    qx, qy, qz, qw = S["qx"], S["qy"], S["qz"], S["qw"]
    head = np.degrees(np.arctan2(2 * (qx * qz + qw * qy), 1 - 2 * (qx * qx + qy * qy)))
    iA = int(np.argmin(np.abs(S["tPlay"] - 12.0) + np.where(S["tPlay"] >= 0, 0, 1e9)))
    perr = np.hypot(S["x"] - P["x"], S["z"] - P["z"])
    yerr = wrap(head - P["yawDeg"])
    hold = np.arange(len(perr)) >= iA
    return dict(s=float(S["s"][iA]), pos_err_m=float(perr[iA]), yaw_err_deg=float(yerr[iA]), speed=float(np.hypot(S["vx"], S["vz"])[iA]),
                hold_pos_err_max_m=float(perr[hold].max()), hold_yaw_err_absmax_deg=float(np.abs(yerr[hold]).max()),
                tilt_max_deg=float(np.degrees(np.arccos(np.clip(1 - 2 * (qx * qx + qz * qz), -1, 1))).max()))


def steering_rows_same():
    """run1 と run2（修正 D44-4 の前後）の操船の区間の行が同じか（CSV の文字のまま比べる）。"""
    def rows(sub):
        with open(os.path.join(OUT, sub, "ds44_steps.csv"), encoding="utf-8") as f:
            return list(csv.reader(f))
    a, b = rows("run1"), rows("run2")
    n = diff = 0
    for i in range(1, min(len(a), len(b))):
        if a[i][3] != "Steering":
            break
        n += 1
        diff += a[i] != b[i]
    return dict(steering_rows=n, rows_differ=diff, header_same=a[0] == b[0])


def guid_map():
    m = {}
    for dp, dn, fn in os.walk(ASSETS):
        for f in fn:
            if f.endswith(".meta"):
                p = os.path.join(dp, f)
                with open(p, encoding="utf-8", errors="replace") as fh:
                    g = re.search(r"^guid: ([0-9a-f]{32})", fh.read(), re.M)
                if g:
                    m[g.group(1)] = rel(p[:-5])
    return m


def guid_deps(txt):
    gm = guid_map()
    mine = set(re.findall(r"guid: ([0-9a-f]{32})", txt))
    base = set(re.findall(r"guid: ([0-9a-f]{32})", open(BASE_SCENE, encoding="utf-8").read()))
    new = sorted(mine - base)
    return dict(guids=len(mine), in_base_scene=len(mine & base),
                not_in_base=[dict(guid=g, path=gm.get(g, "（Assets の外。Unity の組み込み・パッケージ）")) for g in new])


def compare(rc, bm):
    h = bm["min_acceptance"]["handover_jumps"]
    a = bm["arrival"]
    c = dict(
        heading_step=abs(rc["handover"]["heading_steps_prev_at_next_deg"][1] - h["heading_step_deg"]),
        speed_step=abs(rc["handover"]["speed_steps_prev_at_next"][1] - h["speed_step"]),
        jumps_window=abs(rc["handover"]["window_pm1s"]["heading_steps_over"] + rc["handover"]["window_pm1s"]["speed_steps_over"]
                         - h["jumps_heading_window"] - h["jumps_speed_window"]),
        jumps_lead=abs(rc["handover"]["handover_to_formation"]["heading_steps_over"] + rc["handover"]["handover_to_formation"]["speed_steps_over"]
                       - h["jumps_heading_lead"] - h["jumps_speed_lead"]),
        d_max=abs(rc["range"]["d_max_steering"] - bm["min_acceptance"]["out_of_range"]["d_max_whole_steering"]),
        arrival_pos=abs(rc["arrival"]["pos_err_m"] - a["pos_err_m"]),
        arrival_yaw=abs(rc["arrival"]["yaw_err_deg"] - a["yaw_err_deg"]),
        hold_pos=abs(rc["arrival"]["hold_pos_err_max_m"] - a["hold_pos_err_max_m"]),
        tilt_max=abs(rc["tilt"]["max_deg"] - h["formation_record"]["tilt_max_deg"]),
        wet_zero=abs(rc["wet_zero_steps"] - bm["record_only"]["wet_zero_steps"]),
        eye_margin=abs(rc["seat_eye"]["margin_min_m"] - bm["record_only"]["seat_eye"]["margin_min_m"]))
    return {k: float(v) for k, v in c.items()}


def handover_png(dst, frames=(2098, 2099, 2100, 2101)):
    cap = cv2.VideoCapture(os.path.join(OUT, "ds44_steer_30fps.mp4"))
    can = np.zeros((1080, 1920, 3), np.uint8)
    for i, n in enumerate(frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, n)
        ok, im = cap.read()
        assert ok, n
        tile = im[:540, :960].copy()       # 追う視点（動画の左上）
        lab = "video frame %d  (s = %.2f)%s" % (n, n / 30.0, "  <- handover s = 70.00" if n == 2100 else "")
        cv2.rectangle(tile, (0, 500), (960, 540), (0, 0, 0), -1)
        cv2.putText(tile, lab, (8, 528), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        y0, x0 = (i // 2) * 540, (i % 2) * 960
        can[y0:y0 + 540, x0:x0 + 960] = tile
    cv2.imwrite(dst, can)
    return dict(frames=list(frames), source="ds44_steer_30fps.mp4 の左上（追う視点、960 × 540）", layout="2 × 2")


def file_times():
    items = ["Tools/GWWaveGen/ds44", "Unity/Build/Design/44", "Unity/Assets/GreatWave/Design44/Data/ds44_steer.json",
             "Unity/Assets/GreatWave/Design44/Scripts/DS44Trajectory.cs", "Unity/Assets/GreatWave/Design44/Scripts/DS44Input.cs",
             "Tools/GWWaveGen/ds44/run_ds44_unity.ps1",
             "Unity/Build/Design/44/steer/run1/ds44_steps.csv", "Unity/Build/Design/44/steer/logs/unity_ds44_run1.log",
             "Unity/Assets/GreatWave/Design44/Scripts/DS44BoatSteer.cs", "Unity/Build/Design/44/steer/run2/ds44_steps.csv",
             "Unity/Build/Design/44/steer/logs/unity_ds44_run2.log", "Unity/Assets/GreatWave/Design44/Editor/DS44SteerTest.cs",
             "Unity/Assets/GreatWave/Design44/Scenes/DS44_Steer.unity", "Unity/Build/Design/44/steer/logs/unity_ds44_run3.log",
             "Tools/GWWaveGen/ds44/ds44_model.py", "Tools/GWWaveGen/ds44/ds44_measure.py", "Tools/GWWaveGen/ds44/ds44_grid.py",
             "Unity/Build/Design/44/steer/ds44_trajectory_grid.json", "Tools/GWWaveGen/ds44/ds44_report.py",
             "Unity/Build/Design/44/steer/fig_ds44_steer.png", "Unity/Build/Design/44/steer/ds44_steer_30fps.mp4",
             "Unity/Build/Design/44/steer/metrics.json", "Unity/Build/Design/44/indep_check/ck44_stdout.txt"]
    out = {}
    for p in items:
        a = os.path.join(REPO, p)
        if os.path.exists(a):
            st = os.stat(a)
            out[p] = dict(created=hms(st.st_ctime), modified=hms(st.st_mtime))
    return out


def main():
    t0 = time.time()
    os.makedirs(EVD, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    run_b = load(os.path.join(OUT, "run.json"))
    rows, bad = verify(run_b)
    if bad:
        print("SHA-256 が作る部の run.json と違う：", bad)
        sys.exit(1)
    met_b = load(os.path.join(OUT, "metrics.json"))
    rc = recount()
    cmp_ = compare(rc, met_b)
    ind_txt = open(os.path.join(IND, "ck44_stdout.txt"), encoding="utf-8").read()
    indep = dict(schema="GreatWave.DS44.indep_check/1", number="設計44",
                 note_ja="進行役の独立の検査 ck44_physics.py（作る部の ds44 の道具を import しない numpy。記録した剛体の状態 unity/ds44_steps.csv と ds44_steer.json だけを読む）の出力。"
                         "Git 対象外の写し Unity/Build/Design/44/indep_check/ck44_physics.py を記録の時に回し直した出力で、検査の時の報告の値と同じ",
                 script_sha256=sha(os.path.join(IND, "ck44_physics.py")), stdout_lines=ind_txt.splitlines())
    dump(os.path.join(EVD, "ds44_indep_check.json"), indep)

    copies = {
        "fig_ds44_steer.png": os.path.join(OUT, "fig_ds44_steer.png"),
        "stills_ds44_key_moments.png": os.path.join(OUT, "stills_ds44_key_moments.png"),
        "ds44_steer_30fps.mp4": os.path.join(OUT, "ds44_steer_30fps.mp4"),
        "ds44_steer_metrics.json": os.path.join(OUT, "metrics.json"),
        "ds44_steer_run.json": os.path.join(OUT, "run.json"),
        "ds44_unity_report.json": os.path.join(OUT, "unity", "ds44_unity_report.json"),
        "ds44_trajectory_grid.json": os.path.join(OUT, "ds44_trajectory_grid.json"),
    }
    for dst, src in copies.items():
        shutil.copyfile(src, os.path.join(EVD, dst))
    hp = handover_png(os.path.join(EVD, "fig_ds44_handover_chase_frames.png"))
    for f in ("fig_ds44_steer.png", "stills_ds44_key_moments.png", "fig_ds44_handover_chase_frames.png"):
        assert cv2.imread(os.path.join(EVD, f)).shape[:2] == (1080, 1920), f
    assert os.path.getsize(os.path.join(EVD, "ds44_steer_30fps.mp4")) <= 5 * 1000 * 1000

    dump(os.path.join(EVD, "ds44_record_recount.json"), dict(
        schema="GreatWave.DS44.record_recount/1", number="設計44",
        note_ja="記録の道具 ds44_record.py の数え直し。作る部の ds44_measure.py・ds44_model.py・ds44_report.py は使わず、ds44_steps.csv・ds44_frames.jsonl・場面のファイルから数えた",
        recount=rc, diff_vs_builder_metrics=cmp_, handover_png=hp))

    ma = met_b["min_acceptance"]
    metrics = dict(
        schema="GreatWave.DS44.record_metrics/1", number="設計44", title_ja="前進・減速・旋回・停止",
        created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        evidence_kind_ja="PC の Unity 6000.4.3f1 batchmode（RTX 3080、Direct3D11）の物理と描画、Input System の仮想の機器、numpy の測定、進行役の独立の検査。HMD 実機ではない。利用者は確かめていない",
        plan_ja="計画 §2.4 設計44：導入と接近の区間だけの操船（設計15 の候補範囲）。入力はキーボード／ゲームパッドを先に作り、PS VR2 の Sense は SteamVR 経由で使えれば足す。範囲の外は柔らかく押し戻す。形成の前に座席の船を原画の位置へ導く固定の軌道へ引き継ぐ（D26）",
        min_acceptance_ja=met_b["min_acceptance_ja"],
        acceptance=dict(
            input_to_motion=dict(pass_=ma["input_to_motion"]["pass_"], video="Docs/Evidence/Design/44/ds44_steer_30fps.mp4",
                                 builder=dict(v_end=ma["input_to_motion"]["accelerate"]["v_end"], onset_s=ma["input_to_motion"]["accelerate"]["onset_s_after_press"],
                                              drag_ratio=ma["input_to_motion"]["drag"]["ratio_measured_to_model"], stop_end=ma["input_to_motion"]["stop"]["surge_end"],
                                              turn_right_deg=ma["input_to_motion"]["turn_right"]["heading_change_deg"]),
                                 indep_ja="独立の検査：W 0 → 2.326 m/s、動き出し 0.125 s（閾値 0.01 m/s。作る部は 0.05 m/s で 0.30 s）、減速の比 0.960（12.5〜20 s。作る部は 13〜20 s で 0.987）、W＋D +45.41°、Space 2.130 → 0.021 m/s、左スティック −17.28°、L2 −0.712 → −1.233 m/s"),
            out_of_range=dict(pass_=ma["out_of_range"]["pass_"], d_max_builder=ma["out_of_range"]["d_max_whole_steering"],
                              d_max_record=rc["range"]["d_max_steering"], criterion_ja=ma["out_of_range"]["criterion_ja"]),
            handover_jumps=dict(pass_=ma["handover_jumps"]["pass_"], heading_step_deg=ma["handover_jumps"]["heading_step_deg"],
                                speed_step=ma["handover_jumps"]["speed_step"], record=rc["handover"],
                                criterion_ja=ma["handover_jumps"]["criterion_ja"]),
            pass_=bool(ma["pass_"])),
        arrival=met_b["arrival"], trajectory=met_b["trajectory"], trajectory_crosscheck=met_b["trajectory_crosscheck"],
        backlog=met_b["backlog"], decisions_q24=met_b["decisions_ja"], limits_builder_ja=met_b["limits_ja"],
        fix_rounds=dict(count=1,
                        fix01_ja="作る部の中の run2（D44-4）：run1 は軌道を速度の帰還だけで追い、t* のずれ 0.14 m・5.6°（保持で最大 0.27 m・15°）。軌道の間は段ごとに水平の位置と首の向きを軌道へ合わせた。Q26 の修正 1 回はこれに当てた",
                        not_counted_ja=["run3：追う視点と横の視点のカメラを左舷の側へ動かしただけ（ds44_steps.csv は run2 とバイトで同じ。設計43 の run2 と同じ扱い）",
                                        "検査の後の報告の図の直し（report_fix）：fig_ds44_steer.png の文字の重なりと、動画の crf 23 → 25。Unity と物理は回していない（ds44_steps.csv 643b376f… のまま）"]),
        record_recount=dict(file="Docs/Evidence/Design/44/ds44_record_recount.json", diff_vs_builder_max=float(max(cmp_.values())), diff=cmp_),
        builder_sha256_verified=dict(files=len(rows), all_same=not bad),
        time=dict(box_ja="Q26 の日程で 4 時間（計画 §2.6 の［Q26］の表、10/3 の行。計画の時間枠は ≤1日）", file_times=file_times(),
                  builder_report_ja="作る部の報告は「4 時間の内の約 37 分（11:20:45〜11:58）、修正 1 回」、報告の図の直しは「約 10 分」",
                  unity_in_run_s=dict(run1=78.6, run2=101.0, run3=101.9), report_s=run_b["seconds_report"]),
        hmd_ja="保留（PS VR2 の導入は利用者の手）。PS VR2 の Sense、手で押す機器、HMD の確かめも保留。Mock の両眼は描いていない",
        painting_view_ja="原画視点の場面（DS39_Paper.unity・DS41_Boats.unity）は開いていない。守るファイル 26 の SHA-256 は 3 回の実行の前後で同じ。計画 §2.0 の回帰は対象外",
        evidence=sorted(os.listdir(EVD) + ["metrics.json", "run.json"]),
    )
    metrics["evidence"] = sorted(set(metrics["evidence"]))
    dump(os.path.join(EVD, "metrics.json"), metrics)

    ev_sha = {rel(os.path.join(EVD, f)): sha(os.path.join(EVD, f)) for f in sorted(os.listdir(EVD)) if f != "run.json"}
    code = {}
    for root in (HERE, os.path.join(ASSETS, "GreatWave", "Design44")):
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d != "__pycache__"]
            for f in sorted(fn):
                code[rel(os.path.join(dp, f))] = sha(os.path.join(dp, f))
    code["Unity/Assets/GreatWave/Design44.meta"] = sha(os.path.join(ASSETS, "GreatWave", "Design44.meta"))
    run = dict(
        schema="GreatWave.DS44.record_run/1", number="設計44", created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        tools=dict(python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__, unity="6000.4.3f1（batchmode。記録では使っていない）",
                   ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe（作る部）", input_system="com.unity.inputsystem 1.19.0（Unity/Packages/manifest.json）"),
        builder_commands=run_b["commands"],
        record_commands=["py -3.10 -B Unity/Build/Design/44/indep_check/ck44_physics.py > Unity/Build/Design/44/indep_check/ck44_stdout.txt（進行役の独立の検査。Git 対象外の写し）",
                         "py -3.10 -B Tools/GWWaveGen/ds44/ds44_record.py",
                         "py -3.10 -B Unity/Build/Design/44/record/ds44_commit_scan.py（コミットの一覧の点検。Git 対象外）"],
        builder_inputs_sha256=run_b["inputs"], builder_outputs=run_b["outputs"],
        scene=dict(path="Unity/Assets/GreatWave/Design44/Scenes/DS44_Steer.unity", sha256=rc["scene"]["sha256"], bytes=rc["scene"]["bytes"]),
        code_sha256=code, evidence_sha256=ev_sha,
        seconds=round(time.time() - t0, 1),
        note_ja="SHA-256 は作業の木のバイトの値。Unity のコマの JPG（8,433 枚）とログは Git 対象外で SHA-256 を取っていない")
    dump(os.path.join(EVD, "run.json"), run)
    print(json.dumps(dict(verified=len(rows), bad=bad, diff_max=max(cmp_.values()), diff=cmp_, seconds=run["seconds"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
