# -*- coding: utf-8 -*-
"""FLIP39 E：計算の後の解析を順に行う（e_analyze → e_seat → e_render）。py -3.10 e_post.py <run_id> ... [--clip] [--no-analyze] [--no-seat]"""
import sys, os, subprocess, glob
E = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E"
T = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
for rid in args:
    rd = os.path.join(E, rid)
    # E3 は頂が焦点の列（壁）の外（z = −80 m）に出たので、その列を主に解析し、焦点の列は別の名前で残す
    ROWS = {"E3_dir20_lens": -80}
    if "--no-analyze" not in sys.argv:
        extra = ["--row=%d" % ROWS[rid], "--main"] if rid in ROWS else []
        subprocess.run(["py", "-3.10", os.path.join(T, "e_analyze.py"), rd] + extra, stdout=open(os.path.join(rd, "analyze_log.txt"), "w"), stderr=subprocess.STDOUT)
        if rid in ROWS:
            subprocess.run(["py", "-3.10", os.path.join(T, "e_analyze.py"), rd, "--row=-118"], stdout=open(os.path.join(rd, "analyze_wall_log.txt"), "w"), stderr=subprocess.STDOUT)
    if "--no-seat" not in sys.argv:
        subprocess.run(["py", "-3.10", os.path.join(T, "e_seat.py"), rd, "--step2"], stdout=open(os.path.join(rd, "seat_log.txt"), "w"), stderr=subprocess.STDOUT)
    for f in glob.glob(os.path.join(rd, "render", "still_*.png")):
        os.remove(f)
    cmd = ["py", "-3.10", os.path.join(T, "e_render.py"), rd] + (["--clip"] if "--clip" in sys.argv else [])
    subprocess.run(cmd, stdout=open(os.path.join(rd, "render_log.txt"), "w"), stderr=subprocess.STDOUT)
    print("post done", rid, flush=True)
