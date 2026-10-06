# -*- coding: utf-8 -*-
"""P2g（誘導の双子）の計算を順に走らせ（p2_queue.py の複製。場所を P2g、計算を run_p2g.py にした）、終わるたびに解析と図を作る（py -3.10）。重い計算は一度に一つだけ。
使い方: py -3.10 p2_queue.py <queue.json>
queue.json: [{"run_id": "...", "parms": {...}, "f_end": 360}, ...]
各計算は sh p2_launch.sh と同じ引数で hython の run_p2.py を呼ぶ。記録は runs.jsonl（run_p2.py が書く）。
"""
import sys, os, json, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2g"
HYTHON = r"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
env = dict(os.environ, HOUDINI_TEMP_DIR=r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/tmp_houdini")
tried = set()


def next_job():
    # 19:05 から：計算が一つ終わるたびに queue.json を読み直す（まだ走らせていない計算を足したり変えたりできる）
    for job in json.load(open(sys.argv[1], encoding="utf8")):
        rid = job["run_id"]
        if rid in tried:
            continue
        if os.path.isfile(os.path.join(P2, rid, "run.json")):
            print("skip", rid); tried.add(rid); continue
        return job
    return None


while True:
    job = next_job()
    if job is None:
        break
    rid = job["run_id"]; tried.add(rid)
    J = {"run_id": rid, "parms": job["parms"], "f_start": 1, "f_end": job.get("f_end", 360), "snap_from": job.get("snap_from", 145),
         "snap_every": 2, "snap_x": [380, 806], "snap_zhalf": 1.5, "mesh_from": job.get("mesh_from", 145), "mesh_every": 3,
         "wall_limit_s": 1740, "note": job.get("note", ""), "concurrent_with": job.get("concurrent_with"),
         "ckpt_on": job.get("ckpt_on", 0), "ckpt_every": job.get("ckpt_every", 48)}
    if job.get("snap_zc"):
        J["snap_zc"] = job["snap_zc"]
    if job.get("f_start"):
        J["f_start"] = int(job["f_start"])   # 途中保存からの続き（ckpt_dir に元の計算の ckpt を渡す）
    if job.get("ckpt_dir"):
        J["ckpt_dir"] = job["ckpt_dir"]
    t0 = time.time()
    with open(os.path.join(P2, "logs", rid + ".log"), "w", encoding="utf8") as lf:
        subprocess.run([HYTHON, os.path.join(HERE, "run_p2g.py"), json.dumps(J)], stdout=lf, stderr=subprocess.STDOUT, env=env)
    print("ran", rid, round(time.time() - t0), "s"); sys.stdout.flush()
    rd = os.path.join(P2, rid)
    # 解析と図は次の計算と並べて走らせる（軽い）
    if job.get("merge_into"):
        # 途中保存からの続き（部分 B）を元の計算（部分 A）へつなぎ、A の解析と図を作り直す
        ra = job["merge_into"]
        with open(os.path.join(P2, "logs", rid + "_merge.log"), "w", encoding="utf8") as lf:
            subprocess.run([sys.executable, os.path.join(HERE, "p2_merge.py"), ra, rid, job.get("merge_note", "")], stdout=lf, stderr=subprocess.STDOUT)
        rd = os.path.join(P2, ra)
        for f in os.listdir(rd):
            if f.startswith("clay_") and (f.endswith(".png") or f.endswith(".json")):
                os.remove(os.path.join(rd, f))
        subprocess.Popen([sys.executable, os.path.join(HERE, "p2_post.py"), rd],
                         stdout=open(os.path.join(P2, "logs", ra + "_post.log"), "w"), stderr=subprocess.STDOUT)
        continue
    if job.get("no_post"):
        continue
    subprocess.Popen([sys.executable, os.path.join(HERE, "p2_post.py"), rd],
                     stdout=open(os.path.join(P2, "logs", rid + "_post.log"), "w"), stderr=subprocess.STDOUT)
