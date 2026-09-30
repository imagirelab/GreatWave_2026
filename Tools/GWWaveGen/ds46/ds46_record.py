# -*- coding: utf-8 -*-
# 設計46 の記録の道具（共通時計）。
#   1. 作る部の出力・コード・場面・守るファイルの SHA-256 を、作る部の run.json と Unity の報告の値と照合する（違えば止まる）。
#   2. 作る部の測定の道具（ds46_clock_report.py）を使わずに、生の記録（Unity の報告 JSON のハッシュ一式、段の CSV、Play モードの CSV・JSON）から
#      受入の数を数え直す：同じ時刻で同じ形（Editor の 4 つの道と Play モード）、同期、物理が読む水の遅れ、181 の終態の時刻、出来事、t* の原画視点の画素。
#   3. 場面 DS46_Clock.unity の依存（GUID）を設計41 の DS41_Boats.unity と比べる。
#   4. 証拠を Docs/Evidence/Design/46/ へ写し、記録の metrics.json・run.json・数え直しの JSON を書く。
# PC の記録の計算（numpy・OpenCV）。Unity は回さない。HMD 実機ではない。
# 使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds46/ds46_record.py
import csv
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
from collections import Counter

import cv2
import numpy as np

T0 = time.time()
REPO = "G:/Unity/GreatWave_2026_Fresh"
UNITY = REPO + "/Unity"
B46 = UNITY + "/Build/Design/46"
CLK = B46 + "/clock"
IND = B46 + "/indep_check"
EV = REPO + "/Docs/Evidence/Design/46"
TSTAR = 12.0
END = 14.0


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


# ------------------------------------------------------------------ 1. SHA-256 の照合
run_b = jload(CLK + "/run.json")
rep = jload(CLK + "/unity/ds46_clock_report.json")
play = jload(CLK + "/playmode/ds46_playmode.json")
checked = {}
for rel, h in run_b["code_sha256"].items():
    checked[rel] = (sha(REPO + "/" + rel), h)
for rel, h in run_b["outputs_sha256"].items():
    checked[rel] = (sha(REPO + "/" + rel), h)
for rel, h in run_b["inputs_sha256"].items():
    checked["Unity/" + rel] = (sha(UNITY + "/" + rel), h)
for rel, h in run_b["unity_logs"].items():
    checked[rel] = (sha(REPO + "/" + rel), h)
checked["Unity/" + rep["scene"]] = (sha(UNITY + "/" + rep["scene"]), rep["sceneSha256"])
prot = {}
for line in rep["protected"]:
    rel, h = line.rsplit(" ", 1)
    p = os.path.normpath(os.path.join(UNITY, rel)).replace("\\", "/")
    prot[p.replace(REPO + "/", "")] = (sha(p), h)
bad = [k for k, (a, b) in list(checked.items()) + list(prot.items()) if a != b]
if bad:
    fail("SHA-256 が作る部の記録と違う: " + ", ".join(bad))
print("SHA-256 の照合：作る部 %d 件・守るファイル %d 件、すべて同じ" % (len(checked), len(prot)))

# ------------------------------------------------------------------ 2. 数え直し
recount = {}

# A. Editor：同じ時刻で同じ形（基準 R と、4 つの道の同じ体験の時刻のハッシュ一式）
snaps = rep["snaps"]
R = [s for s in snaps if s["seq"] == "R"]
rows = []
for s in snaps:
    if s["seq"] == "R":
        continue
    ref = [r for r in R if abs(r["exp"] - s["exp"]) < 1e-9]
    if not ref:
        rows.append({"seq": s["seq"], "label": s["label"], "exp": s["exp"], "ref": None})
        continue
    r = ref[0]
    keys = sorted(set(r["h"]) | set(s["h"]))
    mism = [k for k in keys if r["h"].get(k) != s["h"].get(k)]
    rows.append({"seq": s["seq"], "label": s["label"], "exp": s["exp"], "keys": len(keys), "mismatch": mism,
                 "tau_equal": s["tau"] == r["tau"], "wave_equal": s["wave"] == r["wave"], "passed_equal": s["passed"] == r["passed"]})
cmp_rows = [x for x in rows if x.get("ref", 1) is not None]
hero_upto = [r["h"]["sheet_hero"] for r in R if r["exp"] <= TSTAR + 1e-9]
r12 = [r for r in R if r["exp"] == 12.0][0]
r13 = [r for r in R if r["exp"] == 13.0][0]
r14 = [r for r in R if r["exp"] == 14.0][0]
s1a = [s for s in snaps if s["label"] == "stop_at_5"][0]
s1b = [s for s in snaps if s["label"] == "stopped_32_frames"][0]
recount["editor_same_shape"] = {
    "compared": len(cmp_rows),
    "mismatched": sum(1 for x in cmp_rows if x["mismatch"]),
    "keys_per_compare": sorted(set(x["keys"] for x in cmp_rows)),
    "hash_keys": sorted(r12["h"].keys()),
    "tau_wave_passed_all_equal": all(x["tau_equal"] and x["wave_equal"] and x["passed_equal"] for x in cmp_rows),
    "reference_snaps": [[r["label"], r["exp"]] for r in R],
    "reference_distinct_hero_hash_upto_tstar": len(set(hero_upto)),
    "reference_snaps_upto_tstar": len(hero_upto),
    "hold_t13_equals_t12_except_events": all(r12["h"][k] == r13["h"][k] for k in r12["h"] if k != "events"),
    "end_t14_equals_t12_except_events": all(r12["h"][k] == r14["h"][k] for k in r12["h"] if k != "events"),
    "stopped_32_advances_same_step_and_hashes": s1a["step"] == s1b["step"] and s1a["h"] == s1b["h"],
    "rows": [{k: v for k, v in x.items() if k in ("seq", "label", "exp", "keys", "mismatch")} for x in rows],
}

# B. 段の CSV（Editor、1/32 s）：同期と 181
with open(CLK + "/unity/ds46_steps.csv", encoding="utf-8") as f:
    st = list(csv.DictReader(f))
wave_bad = sum(1 for r in st if abs(float(r["wave"]) - min(max(float(r["exp"]), 0.0), TSTAR)) > 1e-9)
boat_bad = sum(1 for r in st if r["boat_tau"] != r["tau"])
Rr = [r for r in st if r["seq"] == "R"]
tR = np.array([float(r["exp"]) for r in Rr])
b181 = {}
for col in ("hero", "white_flags", "white_img", "indigo_img", "claws", "spray"):
    v = [r[col] for r in Rr]
    fin = v[-1]
    diff = [i for i, x in enumerate(v) if x != fin]
    last = diff[-1] if diff else -1
    first_final = last + 1
    b181[col] = {"t_final": float(tR[first_final]), "t_last_change": float(tR[last]) if last >= 0 else None,
                 "distinct": len(set(v)), "changes": sum(1 for i in range(1, len(v)) if v[i] != v[i - 1]),
                 "changes_after_tstar": sum(1 for i in range(1, len(v)) if v[i] != v[i - 1] and tR[i] > TSTAR + 1e-9),
                 "final_at_tstar": bool(abs(tR[first_final] - TSTAR) < 1e-9)}
wc = [int(r["white_count"]) for r in Rr]
recount["steps_csv"] = {
    "rows": len(st), "sync_bad_sum": sum(int(r["sync_bad"]) for r in st), "wave_clamp_bad": wave_bad, "boat_tau_ne_tau": boat_bad,
    "reference_rows": len(Rr), "reference_dt": sorted(set(round(float(tR[i + 1] - tR[i]), 9) for i in range(len(tR) - 1))),
    "reference_range": [float(tR[0]), float(tR[-1])],
    "white_vertices_final": wc[-1], "white_vertices_first_full_t": float(tR[wc.index(wc[-1])]),
    "tau_at_white_full": float([r for r in Rr if int(r["white_count"]) == wc[-1]][0]["tau"]),
}
recount["b181_grid"] = b181
fine = rep["b181"]["fine"]
recount["b181_fine_1_256"] = {
    "before_tstar_all_layers_nonzero_until": max(x["t"] for x in fine if x["t"] < TSTAR and x["whiteImgDiffPx"] > 0 and x["indigoImgDiffPx"] > 0 and x["clawsMaxDiffM"] > 0 and x["sprayMaxDiff"] > 0),
    "at_or_after_tstar_all_zero": all(x["whiteImgDiffPx"] == 0 and x["indigoImgDiffPx"] == 0 and x["clawsMaxDiffM"] == 0 and x["sprayMaxDiff"] == 0 for x in fine if x["t"] >= TSTAR),
    "white_indigo_px_before_tstar": [x["whiteImgDiffPx"] for x in fine if x["t"] < TSTAR],
    "claws_m_range_before_tstar": [min(x["clawsMaxDiffM"] for x in fine if x["t"] < TSTAR), max(x["clawsMaxDiffM"] for x in fine if x["t"] < TSTAR)],
    "spray_range_before_tstar": [min(x["sprayMaxDiff"] for x in fine if x["t"] < TSTAR), max(x["sprayMaxDiff"] for x in fine if x["t"] < TSTAR)],
    "id_image_size_ja": "色区 ID の画像 480 × 270（DS46ClockTest.SheetIds）",
}

# C. Play モードの CSV
with open(CLK + "/playmode/ds46_playmode.csv", encoding="utf-8") as f:
    pl = list(csv.DictReader(f))
lag = Counter()
own = Counter()
prev_pb = None
inc_bad = 0
prev_exp = None
prev_step = None
for r in pl:
    pb = r["pb_tau"]
    if r["fixed_this_frame"] == "1" and r["fixed_tau"] not in ("", "null"):
        lag[(r["advance_before_physics"], r["fixed_lag_frames"])] += 1
        if prev_pb is not None and pb != prev_pb:   # 水が動いたコマだけ（止まった・t* の後は区別できない）
            if r["fixed_tau"] == pb:
                own[(r["advance_before_physics"], "0")] += 1
            elif r["fixed_tau"] == prev_pb:
                own[(r["advance_before_physics"], "1")] += 1
            else:
                own[(r["advance_before_physics"], "other")] += 1
    # 同じ段の続き（段の番号が 1 だけ増えた）コマだけ。台本の Seek・初期化の直後のコマは、跳んだ先から dt だけ進む
    if prev_exp is not None and r["state"] == "Running" and r["step_kind"] == "Advance" and int(r["step"]) - prev_step == 1:
        d = float(r["exp"]) - prev_exp
        if abs(d - float(r["deltaTime"])) > 1e-6 and float(r["exp"]) < END - 1e-9:
            inc_bad += 1
    prev_pb = pb
    prev_exp = float(r["exp"])
    prev_step = int(r["step"])
stopped = [r for r in pl if r["state"] == "Stopped" and abs(float(r["exp"]) - 5.0199966207146645) < 1e-9]
hs = {h["label"]: h for h in play["hashes"]}
pvr = []
for h in play["hashes"]:
    ref = [r for r in R if abs(r["exp"] - h["exp"]) < 1e-9]
    if not ref:
        pvr.append([h["label"], h["exp"], "基準なし"])
        continue
    keys = sorted(h["h"].keys())
    pvr.append([h["label"], h["exp"], [k for k in keys if ref[0]["h"].get(k) != h["h"][k]], len(keys)])
recount["playmode"] = {
    "frames": len(pl), "sync_bad_sum": sum(int(r["sync_bad"]) for r in pl),
    "boat_tau_ne_pb_tau": sum(1 for r in pl if r["boat_tau"] != r["pb_tau"]),
    "deltaTime": dict(Counter(r["deltaTime"] for r in pl)),
    "fixed_count_per_frame": dict(Counter(r["fixed_count_this_frame"] for r in pl)),
    "lag_frames_builder_column(advance_before_physics,lag)": {"%s,%s" % k: v for k, v in sorted(lag.items())},
    "lag_frames_own(advance_before_physics,lag)": {"%s,%s" % k: v for k, v in sorted(own.items())},
    "running_increment_ne_deltaTime": inc_bad,
    "stopped_frames_at_5_02": len(stopped), "stopped_steps": sorted(set(r["step"] for r in stopped)),
    "stop_a_equals_stop_b": hs["stop_a"]["h"] == hs["stop_b"]["h"],
    "vs_editor_reference": pvr,
    "compared_with_editor": sum(1 for x in pvr if isinstance(x[2], list)),
    "mismatched_with_editor": sum(1 for x in pvr if isinstance(x[2], list) and x[2]),
}

# D. 出来事
ev = rep["events"]
recount["events"] = {
    "R_fired": [[e["id"], e["eventT"], e["clockT"], e["fired"]] for e in ev["R"]],
    "R_once_each_lag0": sorted(e["id"] for e in ev["R"] if e["fired"]) == ["formation_start", "hold_end", "t_star"] and all(e["clockT"] == e["eventT"] for e in ev["R"]),
    "S3": [[e["id"], e["eventT"], e["clockT"], e["fired"]] for e in ev["S3"]],
    "S4": [[e["id"], e["eventT"], e["clockT"], e["fired"]] for e in ev["S4"]],
    "seek_or_init_fired": 0,
}

# E. t* の原画視点の画素と静止画
def px(a, b):
    ia = cv2.imread(a, cv2.IMREAD_UNCHANGED)
    ib = cv2.imread(b, cv2.IMREAD_UNCHANGED)
    if ia.shape != ib.shape:
        return -1
    return int(np.count_nonzero(np.any(ia != ib, axis=2)))


pA = CLK + "/unity/tstar/painting_t120_off_ds41path.png"
pB = CLK + "/unity/tstar/painting_t120_off_ds46clock.png"
p41 = UNITY + "/Build/Design/41/model/unity/full/painting_t120_off.png"
pI = IND + "/unity/indep_tstar_clock_painting_off.png"
sd = CLK + "/unity/stills"
recount["painting_tstar"] = {
    "sha256": {"ds41_saved": sha(p41), "ds41_path": sha(pA), "ds46_clock": sha(pB), "indep_clock": sha(pI)},
    "px_ds41path_vs_clock": px(pA, pB), "px_clock_vs_ds41_saved": px(pB, p41), "px_indep_clock_vs_ds41_saved": px(pI, p41),
    "px_painting_t12_vs_t13": px(sd + "/painting_t12.0.png", sd + "/painting_t13.0.png"),
    "px_seat_t12_vs_t13": px(sd + "/seat_t12.0.png", sd + "/seat_t13.0.png"),
    "px_painting_t12_vs_tstar_clock": px(sd + "/painting_t12.0.png", pB),
    "size": list(cv2.imread(pB).shape),
}

# F. 場面の依存
def guids(p):
    with open(p, encoding="utf-8") as f:
        return set(re.findall(r"guid: ([0-9a-f]{32})", f.read()))


g41 = guids(UNITY + "/Assets/GreatWave/Design41/Scenes/DS41_Boats.unity")
g46 = guids(UNITY + "/Assets/GreatWave/Design46/Scenes/DS46_Clock.unity")
new = g46 - g41
where = {}
for root, _, files in os.walk(UNITY + "/Assets"):
    for fn in files:
        if fn.endswith(".meta"):
            p = os.path.join(root, fn)
            with open(p, encoding="utf-8", errors="ignore") as f:
                m = re.search(r"guid: ([0-9a-f]{32})", f.read())
            if m and m.group(1) in new:
                where[m.group(1)] = os.path.relpath(p[:-5], REPO).replace("\\", "/")
with open(UNITY + "/Assets/GreatWave/Design46/Scenes/DS46_Clock.unity", encoding="utf-8") as f:
    scene_txt = f.read()
abs_paths = sorted(set(re.findall(r"(?:dataPath|uv3File|tablePath|[A-Za-z]+Path): ([A-Za-z]:[\\/][^\r\n]+)", scene_txt)))
recount["scene_dependencies"] = {
    "guids_ds41": len(g41), "guids_ds46": len(g46), "new_vs_ds41": {g: where.get(g, "（Assets の下にない）") for g in sorted(new)},
    "dropped_vs_ds41": len(g41 - g46),
    "absolute_paths_in_scene": abs_paths,
    "absolute_paths_same_as_ds41": all(a in open(UNITY + "/Assets/GreatWave/Design41/Scenes/DS41_Boats.unity", encoding="utf-8").read() for a in abs_paths),
}

# G. 独立の検査の出力（写すだけ。数は検査の文から）
recount["independent_check_files"] = {
    os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in [IND + "/chk46_recount.json", IND + "/unity/indep46_unity.txt", pI]
}

# ------------------------------------------------------------------ 3. 数え直しと作る部の値の差
bm = jload(CLK + "/metrics.json")
diff = {
    "editor_compared": recount["editor_same_shape"]["compared"] - bm["acceptance"][0]["value"]["compared"],
    "editor_mismatched": recount["editor_same_shape"]["mismatched"] - bm["acceptance"][0]["value"]["mismatched"],
    "play_compared": recount["playmode"]["compared_with_editor"] - bm["acceptance"][1]["value"]["compared_with_editor"],
    "play_mismatched": recount["playmode"]["mismatched_with_editor"] - bm["acceptance"][1]["value"]["mismatched"],
    "sync_edit_steps": recount["steps_csv"]["rows"] - bm["acceptance_record"]["sync_edit_steps"]["steps"],
    "sync_play_frames": recount["playmode"]["frames"] - bm["acceptance_record"]["sync_play_frames"]["frames"],
}
for col, key in (("white_img", "white_img"), ("indigo_img", "indigo_img"), ("claws", "claws"), ("spray", "spray")):
    diff["b181_t_final_" + col] = b181[col]["t_final"] - bm["acceptance"][2]["value"][key]["t_final"]
diff["b181_t_final_white_flags"] = b181["white_flags"]["t_final"] - bm["acceptance_record"]["b181_white_flags"]["t_final"]
recount["diff_vs_builder"] = diff
if any(v != 0 for v in diff.values()):
    fail("数え直しが作る部の値と違う: " + json.dumps(diff, ensure_ascii=False))

# ------------------------------------------------------------------ 4. 証拠の写し
os.makedirs(EV, exist_ok=True)
copies = {
    CLK + "/fig_ds46_clock.png": "fig_ds46_clock.png",
    CLK + "/stills_ds46_clock.png": "stills_ds46_clock.png",
    CLK + "/metrics.json": "ds46_clock_metrics.json",
    CLK + "/run.json": "ds46_clock_run.json",
    CLK + "/unity/ds46_clock_report.json": "ds46_clock_report.json",
    CLK + "/unity/ds46_steps.csv": "ds46_steps.csv",
    CLK + "/playmode/ds46_playmode.json": "ds46_playmode.json",
    CLK + "/playmode/ds46_playmode.csv": "ds46_playmode.csv",
    IND + "/chk46_recount.json": "ds46_indep_recount.json",
    IND + "/unity/indep46_unity.txt": "ds46_indep_unity.txt",
}
for src, dst in copies.items():
    shutil.copyfile(src, EV + "/" + dst)
    if sha(src) != sha(EV + "/" + dst):
        fail("写しの SHA-256 が違う: " + dst)
for p in ("fig_ds46_clock.png", "stills_ds46_clock.png"):
    im = cv2.imread(EV + "/" + p)
    if im.shape[:2] != (1080, 1920):
        fail("1920 × 1080 でない: " + p)

rc_path = EV + "/ds46_record_recount.json"
with open(rc_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(recount, f, ensure_ascii=False, indent=1, default=lambda o: o.item())


# ------------------------------------------------------------------ 5. 記録の metrics.json・run.json
def ft(p):
    s = os.stat(p)
    c = datetime.datetime.fromtimestamp(s.st_ctime).strftime("%H:%M:%S")
    m = datetime.datetime.fromtimestamp(s.st_mtime).strftime("%H:%M:%S")
    return {"created": c, "modified": m}


times = {os.path.relpath(p, REPO).replace("\\", "/"): ft(p) for p in [
    UNITY + "/Assets/GreatWave/Design31/Scripts/DS31InstancedParticles.cs",
    UNITY + "/Assets/GreatWave/Design46/Data/ds46_events.json",
    UNITY + "/Assets/GreatWave/Design46/Scripts/DS46EventTrack.cs",
    UNITY + "/Assets/GreatWave/Design46/Scripts/DS46ClockBus.cs",
    UNITY + "/Assets/GreatWave/ArtFirst/Scripts/GWClock.cs",
    UNITY + "/Assets/GreatWave/Design46/Scripts/DS46FixedProbe.cs",
    UNITY + "/Assets/GreatWave/Design46/Editor/DS46Probe.cs",
    UNITY + "/Assets/GreatWave/Design46/Editor/DS46ClockTest.cs",
    UNITY + "/Assets/GreatWave/Design46/Editor/DS46PlayModeCheck.cs",
    REPO + "/Tools/GWWaveGen/ds46/run_ds46_unity.ps1",
    CLK + "/_started.txt",
    UNITY + "/Assets/GreatWave/Design46/Scenes/DS46_Clock.unity",
    CLK + "/logs/unity_ds46_run1.log",
    CLK + "/logs/unity_ds46_playmode.log",
    CLK + "/metrics.json",
    IND + "/chk46_recount.py",
    IND + "/logs/unity_indep46_run1.log",
    IND + "/logs/unity_indep46_run2.log",
    IND + "/Indep46Check.cs.txt",
]}

ed = recount["editor_same_shape"]
pm = recount["playmode"]
metrics = {
    "schema": "GreatWave.DS46.record_metrics/1",
    "number": "設計46",
    "title_ja": "共通時計で水面・白波・船用データを同期する",
    "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "evidence_kind_ja": "PC の Unity 6000.4.3f1 batchmode（RTX 3080、Direct3D11）。Editor の計算と描画（時計を外から進める）と、Editor の Play モード（batchmode でプレイヤーのループを 1 フレームずつ回す、dt 0.02 s）。進行役の独立の検査（Unity の batch と numpy）、記録の数え直し（numpy）。HMD 実機ではない。Release のプレイヤーではない。利用者は確かめていない",
    "plan_ja": "計画 §2.5 設計46：秒の時計1つ（GWClock。美術優先30 の最小版を広げる）で、水面・白・爪・飛沫・船用データ・演出を進める。停止・再開・初期化・途中からの再生",
    "min_acceptance_ja": "停止・再開・初期化・途中再生の後、同じ時刻で同じ形（頂点のハッシュが一致）。181（白・藍・爪・飛沫が同じ t* で終態）",
    "backlog": ["181", "199"],
    "acceptance": [
        {"item": "停止・再開・初期化・途中再生の後、同じ時刻で同じ形（頂点のハッシュが一致）", "result": "合格",
         "value": {"editor_compared": ed["compared"], "editor_mismatched": ed["mismatched"], "editor_hash_keys": ed["hash_keys"],
                   "play_compared": pm["compared_with_editor"], "play_mismatched": pm["mismatched_with_editor"],
                   "play_stopped_frames_same": pm["stopped_frames_at_5_02"], "indep_unity_compared": 18, "indep_unity_mismatched": 0}},
        {"item": "181：白・藍・爪・飛沫が同じ t* で終態（見える状態の読み。採った読み）", "result": "合格",
         "value": {k: b181[k] for k in ("white_img", "indigo_img", "claws", "spray")}},
        {"item": "計画 §2.0 の回帰なし（原画視点）", "result": "合格（画素が同じ。評価器は回していない）",
         "value": {"px_clock_vs_ds41_saved": recount["painting_tstar"]["px_clock_vs_ds41_saved"], "px_ds41path_vs_clock": recount["painting_tstar"]["px_ds41path_vs_clock"],
                   "px_indep_clock_vs_ds41_saved": recount["painting_tstar"]["px_indep_clock_vs_ds41_saved"]}},
        {"item": "HMD（PS VR2）", "result": "保留（導入は利用者の手）"},
    ],
    "acceptance_record": {
        "b181_strict_white_arrival": {"result": "記録のみ（限界。仕上げ46）", "white_flags": b181["white_flags"],
                                       "white_vertices_final": recount["steps_csv"]["white_vertices_final"], "tau_at_full": recount["steps_csv"]["tau_at_white_full"],
                                       "early_by_s": round(TSTAR - b181["white_flags"]["t_final"], 5),
                                       "reading_ja": "白の到着の場（頂点の旗 T_white ≤ τ）は t = 11.28125 s で最終に達し、t* より 0.719 s 早い。進行役の独立の検査で、形を t* に止めて白の τ だけを動かすと、白そのものの寄与は t = 11.28125 s から 0 画素（色区 ID の画像では 11.25 s から）。その後の白は、下の面が動くことで運ばれるだけで、三角形の中の縁は動かない（作る部の記録の「三角形の中の縁で t* まで動く」は誤り。作る部のファイルは変えていない）",
                                       "indep_white_only_px": [[10.5, 2178, 2422], [11.0, 271, 456], [11.2, 58, 267], [11.25, 0, 219], [11.28125, 0, 0]]},
        "sync": {"editor_steps": recount["steps_csv"]["rows"], "editor_bad": recount["steps_csv"]["sync_bad_sum"], "play_frames": pm["frames"], "play_bad": pm["sync_bad_sum"]},
        "physics_reads_water": {"builder_column": pm["lag_frames_builder_column(advance_before_physics,lag)"], "own": pm["lag_frames_own(advance_before_physics,lag)"],
                                "fixed_per_frame": pm["fixed_count_per_frame"]},
        "events": recount["events"],
    },
    "record_recount": {"file": "Docs/Evidence/Design/46/ds46_record_recount.json", "diff_vs_builder": diff},
    "builder_sha256_verified": {"files": len(checked), "protected": len(prot), "all_same": True},
    "fix_rounds": {"count": 0, "ja": "作る部の最初の実行で最小の受入を満たし、進行役の独立の検査は必須の指摘 0。修正の回は使っていない"},
    "time": {"box_ja": "Q26 の日程で 2 時間（計画 §2.6 の［Q26］の表、10/3 の行。計画の時間枠は ≤0.5日）",
             "file_times": times},
    "hmd_ja": "保留（PS VR2 の導入は利用者の手）。この番号は時計と形のデータで、両眼の描画は変えていない。Mock の両目は描いていない",
    "painting_view_ja": "DS41_Boats.unity と DS39_Paper.unity は SHA-256 のまま。時計の道の t* の原画視点は設計41 の出力と 0 画素の差で、評価器（画素の関数）の値も同じ",
    "evidence": sorted(os.listdir(EV) + ["metrics.json", "run.json"]),
}
metrics["evidence"] = sorted(set(metrics["evidence"]))
with open(EV + "/metrics.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=1, default=lambda o: o.item())

run = {
    "schema": "GreatWave.DS46.record_run/1",
    "number": "設計46",
    "created_utc": metrics["created_utc"],
    "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
              "unity": "6000.4.3f1（batchmode。作る部と独立の検査。記録では使っていない）"},
    "builder_commands": run_b["commands"],
    "check_commands_ja": ["進行役の独立の検査：Unity/Build/Design/46/indep_check/run_indep46_unity.ps1（Indep46Check.cs.txt を一時に Editor へ置いて 2 回実行し、終わりに消した。Git 対象外）",
                          "py -3.10 Unity/Build/Design/46/indep_check/chk46_recount.py（Git 対象外）"],
    "record_commands": ["py -3.10 -B Tools/GWWaveGen/ds46/ds46_record.py",
                        "py -3.10 -B Unity/Build/Design/46/record/ds46_commit_scan.py（コミットの一覧の点検。Git 対象外）"],
    "builder_inputs_sha256": run_b["inputs_sha256"],
    "builder_code_sha256": run_b["code_sha256"],
    "builder_outputs_sha256": run_b["outputs_sha256"],
    "protected_sha256": {k: v[0] for k, v in prot.items()},
    "scene": {"path": "Unity/" + rep["scene"], "sha256": rep["sceneSha256"], "bytes": os.path.getsize(UNITY + "/" + rep["scene"])},
    "settings_restore": run_b["settings_restore"],
    "record_code_sha256": {"Tools/GWWaveGen/ds46/ds46_record.py": sha(REPO + "/Tools/GWWaveGen/ds46/ds46_record.py")},
    "evidence_sha256": {"Docs/Evidence/Design/46/" + p: sha(EV + "/" + p) for p in sorted(os.listdir(EV)) if p not in ("metrics.json", "run.json")},
    "evidence_sha256_metrics": sha(EV + "/metrics.json"),
    "seconds": round(time.time() - T0, 1),
    "note_ja": "SHA-256 は作業の木のバイトの値。コマの PNG（stills の 8 枚、t* の 2 枚）とログは Git 対象外。独立の検査の写しは検査の出力のまま（ds46_indep_recount.json・ds46_indep_unity.txt）",
}
with open(EV + "/run.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(run, f, ensure_ascii=False, indent=1)
print(json.dumps({"editor": [ed["compared"], ed["mismatched"]], "play": [pm["compared_with_editor"], pm["mismatched_with_editor"]],
                  "b181": {k: b181[k]["t_final"] for k in b181}, "lag_own": pm["lag_frames_own(advance_before_physics,lag)"],
                  "painting": recount["painting_tstar"], "deps": recount["scene_dependencies"]["new_vs_ds41"],
                  "seconds": run["seconds"]}, ensure_ascii=False, indent=1))
