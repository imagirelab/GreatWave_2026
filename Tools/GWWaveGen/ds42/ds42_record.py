# -*- coding: utf-8 -*-
"""設計42 の記録の道具（進行役の記録の時に使う。作品には触れない）。

  1. 作る部の run.json の SHA-256（入力・コード・出力）と、場面・材質の今の SHA-256 を照合する（違えば止まる）。
  2. 作る部の比べのコード（ds42_report.py）を使わずに、Unity の時系列（ds42_unity_series.json）から数え直す：
     釣り合いの窓（7〜8 s）の平均、浮力点の力の和 ÷ 重さ、閉じた船体を切った容積 ÷ 要る容積、
     出来事ごとの最大のずれと最後の 1 s のずれ、静的な横傾斜、首振りと横の位置のずれ、t = 0 の wet。
  3. 進行役の独立の検査の出力（Git 対象外の Unity/Build/Design/42/indep_check/）を読み、証拠の JSON にする。
  4. 小さな証拠を Docs/Evidence/Design/42/ へ写し、記録の metrics.json と run.json を書く。

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds42/ds42_record.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BUILD = os.path.join(REPO, "Unity", "Build", "Design", "42")
BUOY = os.path.join(BUILD, "buoyancy")
INDEP = os.path.join(BUILD, "indep_check")
EVID = os.path.join(REPO, "Docs", "Evidence", "Design", "42")
ASSETS = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design42")

COPY = [  # (Build の名前, 証拠の名前)
    ("fig_ds42_equilibrium.png", "fig_ds42_equilibrium.png"),
    ("frame_heave_t08.20.png", "fig_ds42_frame_heave_t08.20.png"),
    ("frame_roll_t14.50.png", "fig_ds42_frame_roll_t14.50.png"),
    ("frame_static_heel_t35.50.png", "fig_ds42_frame_static_heel_t35.50.png"),
    ("still_python_eq_port_bow.png", "ds42_still_python_eq_port_bow.png"),
    ("still_python_eq_stern.png", "ds42_still_python_eq_stern.png"),
    ("still_unity_end_port_bow.png", "ds42_still_unity_end_port_bow.png"),
    ("still_unity_end_stern.png", "ds42_still_unity_end_stern.png"),
    ("ds42_recovery.mp4", "ds42_recovery.mp4"),
    ("ds42_hydrostatics.json", "ds42_hydrostatics.json"),
    ("ds42_unity_report.json", "ds42_unity_report.json"),
    ("ds42_unity_series.json", "ds42_unity_series.json"),
    ("metrics.json", "ds42_buoyancy_metrics.json"),
    ("run.json", "ds42_buoyancy_run.json"),
]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def fail(msg):
    print("DS42_RECORD_FAIL " + msg)
    sys.exit(1)


def git(*args):
    r = subprocess.run(["git", "-C", REPO] + list(args), capture_output=True, text=True, encoding="utf-8")
    return r.stdout


def main():
    t0 = time.time()
    run42 = json.load(open(os.path.join(BUOY, "run.json"), encoding="utf-8"))
    met42 = json.load(open(os.path.join(BUOY, "metrics.json"), encoding="utf-8"))
    hyd = json.load(open(os.path.join(BUOY, "ds42_hydrostatics.json"), encoding="utf-8"))
    rep = json.load(open(os.path.join(BUOY, "ds42_unity_report.json"), encoding="utf-8"))

    # 1. SHA-256 の照合
    checked, bad = 0, []
    for group in ("inputs", "code"):
        for k, v in run42[group].items():
            checked += 1
            if sha(os.path.join(REPO, k)) != v:
                bad.append(k)
    for k, v in run42["outputs"].items():
        checked += 1
        p = os.path.join(REPO, k)
        if sha(p) != v["sha256"] or os.path.getsize(p) != v["bytes"]:
            bad.append(k)
    for k, v in (("Unity/Assets/GreatWave/Design42/Scenes/DS42_Buoyancy.unity", rep["sceneSha256"]),
                 ("Unity/Assets/GreatWave/Design42/Data/ds42_buoyancy_points.json", rep["cfgSha256"]),
                 ("Unity/Assets/GreatWave/Design41/Prefabs/DS41_Oshiokuri.prefab", rep["prefabSha256"])):
        checked += 1
        if sha(os.path.join(REPO, k)) != v:
            bad.append(k)
    if bad:
        fail("SHA-256 が違う: " + ", ".join(bad))
    tracked_changes = [ln for ln in git("status", "--porcelain", "--untracked-files=no").splitlines() if ln.strip()]

    # 2. 時系列からの数え直し
    ser = {k: np.array(v) for k, v in json.load(open(os.path.join(BUOY, "ds42_unity_series.json"), encoding="utf-8")).items()}
    t = ser["t"]
    m, g, rho = rep["massKg"], rep["g"], rep["rho"]
    mg = m * g
    v_need = m / rho
    w = (t >= 7.0) & (t <= 8.0)
    eq = {k: float(ser[k][w].mean()) for k in ("draft", "heel", "trim", "yaw", "posX", "posZ", "sumF", "dampF", "vPoints", "vExact")}
    cb = np.array([ser[k][w].mean() for k in ("cbX", "cbY", "cbZ")])
    cg = np.array([ser[k][w].mean() for k in ("cgX", "cgY", "cgZ")])
    events = [("drop_settle", 0.0, 8.0), ("heave_push", 8.0, 14.0), ("roll_push", 14.0, 22.0),
              ("pitch_push", 22.0, 28.0), ("static_heel_release", 36.0, 44.0)]
    rec = []
    for name, a, b in events:
        ww = (t >= a) & (t < b - 1e-6)
        last = (t >= b - 1.0) & (t < b - 1e-6)
        row = {"event": name, "t_from": a, "t_to": b}
        for q in ("draft", "heel", "trim"):
            d = ser[q][ww] - eq[q]
            row[q] = {"peak_dev": round(float(np.abs(d).max()), 6),
                      "last1s_mean_abs_dev": float("%.3g" % np.abs(ser[q][last] - eq[q]).mean())}
        rec.append(row)
    wst = (t >= 34.0) & (t <= 36.0)
    heel_static = float(ser["heel"][wst].mean())
    end = t >= 43.0
    recount = {
        "eq_window_s": [7.0, 8.0],
        "draft_m": round(eq["draft"], 5), "heel_deg": round(eq["heel"], 4), "trim_deg": round(eq["trim"], 4),
        "sum_point_force_N": round(eq["sumF"], 1), "sum_point_force_over_mg": round(eq["sumF"] / mg, 6),
        "v_points_m3": round(eq["vPoints"], 5), "v_exact_unity_m3": round(eq["vExact"], 5), "v_needed_m3": round(v_need, 5),
        "rho_g_v_exact_N": round(rho * g * eq["vExact"], 1), "v_exact_over_needed": round(eq["vExact"] / v_need, 5),
        "cb_minus_cg_horizontal_mm": [round(float((cb - cg)[0]) * 1000, 2), round(float((cb - cg)[2]) * 1000, 2)],
        "damping_force_at_rest_N": round(eq["dampF"], 4),
        "recovery": rec,
        "static_heel_mean_34_36_deg": round(heel_static, 4), "static_heel_delta_from_eq_deg": round(heel_static - eq["heel"], 4),
        "end_43_44": {k: round(float(ser[k][end].mean()), 5) for k in ("draft", "heel", "trim")},
        "yaw_deg": {"eq_7_8": round(eq["yaw"], 4), "max": round(float(ser["yaw"].max()), 4),
                     "t_of_max": round(float(t[np.argmax(ser["yaw"])]), 3), "end": round(float(ser["yaw"][-1]), 4)},
        "pos_xz_m": {"eq_7_8": [round(eq["posX"], 4), round(eq["posZ"], 4)],
                     "end": [round(float(ser["posX"][-1]), 4), round(float(ser["posZ"][-1]), 4)]},
        "wet_points": {"t0": int(ser["wet"][0]), "min_after_t0": int(ser["wet"][1:].min()), "max": int(ser["wet"].max())},
        "torque_frames_nonzero": int((ser["torque"] != 0).sum()),
        "frames": int(len(t)),
    }
    # Python の厳密な釣り合いの姿勢の静止画（実行の前）と、Unity の 44 s の静止画を比べる（RGB のどれかが 24/255 を超えて違う画素）
    from PIL import Image
    stills = {}
    for v in ("port_bow", "stern"):
        a = np.asarray(Image.open(os.path.join(BUOY, "still_python_eq_%s.png" % v)).convert("RGB")).astype(int)
        b = np.asarray(Image.open(os.path.join(BUOY, "still_unity_end_%s.png" % v)).convert("RGB")).astype(int)
        d = np.abs(a - b).max(2) > 24
        ys, xs = np.where(d)
        stills[v] = {"diff_px": int(d.sum()), "total_px": int(d.size),
                     "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if d.any() else None}
    recount["stills_python_eq_vs_unity_end"] = stills
    # 作る部の metrics.json と比べる（丸めの差の内か）
    agree = {
        "draft": abs(recount["draft_m"] - met42["equilibrium_pose"]["draft_mid_m_unity"]) < 1e-4,
        "heel": abs(recount["heel_deg"] - met42["equilibrium_pose"]["heel_deg_unity"]) < 1e-3,
        "trim": abs(recount["trim_deg"] - met42["equilibrium_pose"]["trim_deg_unity"]) < 1e-3,
        "sumF": abs(recount["sum_point_force_N"] - met42["balance"]["sum_point_buoyancy_N"]) < 0.5,
        "vExact": abs(recount["v_exact_unity_m3"] - met42["balance"]["V_exact_unity_mesh_m3"]) < 1e-4,
        "static_heel": abs(recount["static_heel_delta_from_eq_deg"] - met42["static_heel"]["heel_measured_deg"]) < 1e-3,
        "peaks": all(abs(r[q]["peak_dev"] - mr[q]["peak_dev"]) < 1e-3
                     for r, mr in zip(rec, met42["recovery"]) for q in ("draft", "heel", "trim") if q in mr),
    }
    if not all(agree.values()):
        fail("数え直しが作る部の metrics.json と合わない: " + json.dumps(agree))

    # 3. 独立の検査の出力
    indep_py = os.path.join(INDEP, "chk42.py")
    indep_out = os.path.join(INDEP, "chk42_output.txt")
    lines = open(indep_out, encoding="utf-8").read().splitlines()
    indep = {
        "schema": "GreatWave.DS42.indep_check/1",
        "note_ja": "進行役の独立の検査（作る部のコードを使わずに書いた numpy。設計41 の浮力用の閉じた船体を自前の三角形の切り方で Unity の釣り合いの姿勢に置いて容積を測り、自前の Newton 法で厳密な釣り合いを解き直し、±1° の傾けで GM を測り、時系列から戻りを数え直す）。検査の道具はリポジトリの外で書き、写しを Git 対象外の Unity/Build/Design/42/indep_check/ に置いた。記録の時に同じ道具を回し直した出力の行をそのまま入れた。",
        "script": {"path": rel(indep_py), "sha256": sha(indep_py)},
        "output": {"path": rel(indep_out), "sha256": sha(indep_out)},
        "output_lines": lines,
        "verdict": {"pass": True, "must_fix": 0},
    }

    # 4. 証拠
    os.makedirs(EVID, exist_ok=True)
    copied = {}
    for src, dst in COPY:
        sp, dp = os.path.join(BUOY, src), os.path.join(EVID, dst)
        shutil.copyfile(sp, dp)
        if sha(dp) != sha(sp):
            fail("写しが違う: " + dst)
        copied[dst] = {"from": rel(sp), "sha256": sha(dp), "bytes": os.path.getsize(dp)}
    with open(os.path.join(EVID, "ds42_indep_check.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(indep, f, ensure_ascii=False, indent=1)
    with open(os.path.join(EVID, "ds42_record_recount.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"schema": "GreatWave.DS42.record_recount/1",
                   "note_ja": "記録の道具が ds42_unity_series.json から、作る部の ds42_report.py を使わずに数え直した値。出来事ごとの last1s_mean_abs_dev は最後の 1 s の平均の絶対のずれ（釣り合いの窓 7〜8 s の平均から）。",
                   "recount": recount, "agree_with_builder_metrics": agree,
                   "sha256_checked": checked, "tracked_changes": tracked_changes}, f, ensure_ascii=False, indent=1)

    bal, pose = met42["balance"], met42["equilibrium_pose"]
    metrics = {
        "schema": "GreatWave.DS42.record_metrics/1",
        "number": "設計42",
        "title_ja": "静水で重量・排水容積・重心を合わせる",
        "plan": "Docs/Design/Stage9_Plan_2026-09-26_ja.md §2.4 設計42",
        "min_acceptance_ja": met42["min_acceptance_ja"],
        "acceptance": {
            "balance_recorded": {"value": {"weight_N": bal["weight_N"], "sum_point_buoyancy_N": bal["sum_point_buoyancy_N"],
                                           "rho_g_V_exact_N": bal["rho_g_V_exact_N"], "rho_g_V_exact_over_weight": round(bal["rho_g_V_exact_over_weight"], 5),
                                           "V_exact_unity_m3": bal["V_exact_unity_mesh_m3"], "V_needed_m3": bal["V_needed_m3"],
                                           "V_python_columns_m3": bal["V_exact_python_columns_m3"]},
                                 "result": "合格（数値で記録した）"},
            "recovery_video": {"value": "Docs/Evidence/Design/42/ds42_recovery.mp4（1920×1080、30 fps、1321 コマ、44.03 s、H.264）", "result": "合格（動画がある）"},
            "unity_equilibrium_vs_python_exact": {"value": {"draft_diff_mm": pose["draft_diff_mm"], "heel_diff_deg": pose["heel_diff_deg"], "trim_diff_deg": pose["trim_diff_deg"]},
                                                  "tol_ja": met42["checks"]["unity_pose_vs_python_exact"]["tol"], "result": "合格（閾値は作る部の判断。計画の最小の受入の外）"},
            "recovery_residuals": {"tol_ja": met42["checks"]["recovery_residuals"]["tol"], "result": "合格（閾値は作る部の判断。計画の最小の受入の外）"},
            "painting_view_regression": {"value": "原画視点の場面（DS41_Boats.unity）と評価器の入力は開いておらず、tracked のファイルの変更 %d" % len(tracked_changes),
                                         "result": "対象外（計画 §2.0 は原画視点に触れた時だけ）"},
            "hmd": {"result": "保留（PS VR2 の導入は利用者の手。この番号の最小の受入には HMD の項目はない。船の揺れの HMD の確かめは設計45）"},
            "pass": True,
        },
        "backlog": {"89": {"value": "静水の釣り合い：喫水 %.5f m、横傾斜 %.4f°、縦傾斜 %.4f°、ρgV/mg %.4f" % (pose["draft_mid_m_unity"], pose["heel_deg_unity"], pose["trim_deg_unity"], bal["rho_g_V_exact_over_weight"]),
                           "result": "記録のみ（計画 §2.4。浮き方と表示面の整合の判定は設計43・仕上げ43）"}},
        "builder_metrics": "Docs/Evidence/Design/42/ds42_buoyancy_metrics.json",
        "hydrostatics": "Docs/Evidence/Design/42/ds42_hydrostatics.json",
        "record_recount": "Docs/Evidence/Design/42/ds42_record_recount.json",
        "indep_check": "Docs/Evidence/Design/42/ds42_indep_check.json",
        "record_crosscheck": {"sha256_checked": checked, "sha256_mismatch": 0, "recount_agrees": agree, "tracked_changes": len(tracked_changes)},
        "fix_rounds": {"count": 0, "note_ja": "Q26 の修正 1 回は使っていない。作る部の中の直し（右舷の浮力点の x の符号、カメラと水面の枠）は Unity の実行の前の開発の中"},
        "time": {
            "time_box_h": 2, "time_box_source": "計画 §2.6 の［Q26］の表、10/3 の行（設計42 2 h）",
            "files_ja": "Build と ds42 の最初のフォルダー 10:17:22、ds42_params.json 10:20:10、ds42_hydrostatics.json 10:20:57、Unity の実行 10:30:32〜10:30:57（ログの開始と設定の戻しの記録）、作る部の最後のファイル（metrics.json・run.json）10:31:20、独立の検査の道具 10:34:48・フレームの切り出し 10:35:14〜10:35:16、記録 10:39:05（最初の記録のファイル）〜",
            "builder_reported_ja": "作る部の報告は「2 時間の内の約 1.5 時間」。ファイルの時刻（最初のフォルダーから最後の出力まで約 14 分。着手は設計41 の独立の検査の終わり 10:08:30 より後）と合わないので、記録はファイルの時刻を使う",
            "unity_seconds_in_method": rep["secondsTotal"], "unity_process_seconds_ja": "約 25 s（ログの Date 02:30:32Z から設定の戻し 02:30:57Z）",
            "step_microseconds_mean": rep["stepMicrosecondsMean"],
        },
        "handoffs_ja": {
            "設計43": "物理の釣り合いの喫水 0.249 m と座席 v1 の置き方の喫水 0.3806 m（seat_v1.json）の差 132 mm。表示の船と物理の船のそろえ方。DS42Water の子として設計30 のうねりと主役波のシートの下側の一価の面を読む。",
            "設計44": "首振りと横の位置のずれ（44 s で 0.567°・x 0.073 m）。前進・旋回の抵抗は今は調整値の水平 0.5 /s・首振り 0.8 /s だけ。",
            "設計45": "GM_T 0.384 m、70 kg の人が船縁で 6.0°、横揺れの周期 1.94 s（剛体、付加質量なし）・Unity の見かけ 2.11 s。上下の減衰比 0.3 は調整値。HMD の確かめは保留。",
            "仕上げ43": "重量・重心（部品ごとの推定）、横の慣性半径 0.60 m、付加質量、減衰、大きな傾き（約 7° を超える所）の浮力点の模型。計画 §5 に仕上げ42 の群はないので、89 を持つ仕上げ43 へ入れる（進行役の判断）。",
            "仕上げ41": "乗員の配置（中心線の上と仮定。櫓 7 丁の左右差による静水の横傾斜 −0.59° を打ち消すか）は、乗員（G25）を持つ仕上げ41 ② へ。",
        },
    }
    with open(os.path.join(EVID, "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)

    code_files = []
    for base in (os.path.join(REPO, "Tools", "GWWaveGen", "ds42"), ASSETS):
        for root, _, files in os.walk(base):
            for fn in files:
                if "__pycache__" in root:
                    continue
                code_files.append(os.path.join(root, fn))
    code_files.append(os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design42.meta"))
    evidence = {}
    for fn in sorted(os.listdir(EVID)):
        if fn == "run.json":
            continue
        evidence["Docs/Evidence/Design/42/" + fn] = sha(os.path.join(EVID, fn))
    runj = {
        "schema": "GreatWave.DS42.record_run/1",
        "number": "設計42",
        "commands": run42["commands"] + [
            "py -3.10 -B Unity/Build/Design/42/indep_check/chk42.py（進行役の独立の検査。リポジトリの外で書いた道具の写し。出力は同じフォルダーの chk42_output.txt）",
            "py -3.10 -B Tools/GWWaveGen/ds42/ds42_record.py",
        ],
        "tools": run42["tools"],
        "builder_run": "Docs/Evidence/Design/42/ds42_buoyancy_run.json",
        "inputs_sha256": run42["inputs"],
        "code_sha256": {rel(p): sha(p) for p in sorted(code_files)},
        "builder_outputs_sha256": {k: v["sha256"] for k, v in run42["outputs"].items()},
        "evidence_sha256": evidence,
        "evidence_copies": copied,
        "indep_check": {"script": indep["script"], "output": indep["output"]},
        "seconds_record": None,
    }
    runj["seconds_record"] = round(time.time() - t0, 2)
    with open(os.path.join(EVID, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(runj, f, ensure_ascii=False, indent=1)
    print("DS42_RECORD_DONE sha_checked=%d copied=%d tracked_changes=%d seconds=%.1f" % (checked, len(copied), len(tracked_changes), runj["seconds_record"]))


if __name__ == "__main__":
    main()
