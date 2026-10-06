# -*- coding: utf-8 -*-
"""P1 の計算を 1 本ずつ順に走らせる（重い計算は一度に一つ）。py -3.10 p1_queue.py
Unity/Build/FLIP37/P1/queue.json（[{run_id, parms, f_end, ...}, ...]）を 1 本ごとに読み直し、
まだ run.json のない最初の項目を hython run_p1.py で走らせ、続けて p1_analyze.py で解析する。
項目がなくなったら終わる。キューの途中で項目を足してよい。"""
import json, os, subprocess, time, sys

ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P1"
HY = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
Q = os.path.join(ROOT, "queue.json")
LOG = os.path.join(ROOT, "queue.log")
env = dict(os.environ, HOUDINI_TEMP_DIR=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/tmp_houdini")


def log(s):
    with open(LOG, "a", encoding="utf8") as f:
        f.write(time.strftime("%H:%M:%S ") + s + "\n")


while True:
    q = json.load(open(Q, encoding="utf8"))
    todo = [it for it in q if not it.get("skip") and not os.path.exists(os.path.join(ROOT, it["run_id"], "run.json"))]
    if not todo:
        log("queue empty, exit")
        break
    it = todo[0]
    args = {"f_start": 1, "snap_from": 49, "snap_every": 2, "snap_x": [250, 806], "snap_ymin": -20}
    args.update({k: v for k, v in it.items() if k not in ("skip", "no_analysis")})
    log("start %s %s" % (it["run_id"], json.dumps(it.get("parms"), ensure_ascii=False)))
    t0 = time.time()
    with open(os.path.join(ROOT, it["run_id"] + ".log"), "w", encoding="utf8") as fo:
        subprocess.run([HY, os.path.join(HERE, "run_p1.py"), json.dumps(args, ensure_ascii=False)], stdout=fo, stderr=subprocess.STDOUT, env=env)
    log("sim done %s %.0fs" % (it["run_id"], time.time() - t0))
    rd = os.path.join(ROOT, it["run_id"])
    if it.get("no_analysis"):
        continue
    try:
        r = subprocess.run(["py", "-3.10", os.path.join(HERE, "p1_analyze.py"), rd, "--quiet"], capture_output=True, text=True, timeout=900)
        a = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
        ev = a["events"]
        log("analysis %s plunging=%s Bmax=%.2f B085=%s over=%s closed=%s toeH=%s stopped=%s" % (
            it["run_id"], a["plunging"], ev["B_max"] or 0, ev["breaking_onset_B085"] and round(ev["breaking_onset_B085"]["t"], 2),
            ev["face_past_vertical"] and round(ev["face_past_vertical"]["t"], 2), ev["tube_closed_or_nearly"] and round(ev["tube_closed_or_nearly"]["t"], 2),
            a.get("toe_gauge", {}).get("H_toe_m"), a.get("stopped")))
    except Exception as e:
        log("analysis failed %s %s %s" % (it["run_id"], e, (r.stderr[-500:] if 'r' in dir() else "")))
