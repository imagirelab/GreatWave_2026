# -*- coding: utf-8 -*-
"""P2 のまとめの作り直し（py -3.10）：計算ごとに古い粘土の図を消し、p2_post（解析 → 一枚の図 → 粘土 → 並び）を順に走らせる。
計算と並べても邪魔をしにくいよう、自分（と子の Blender・解析）を低い優先度で走らせる。
使い方: py -3.10 p2_final_pass.py <run_id> ...
"""
import sys, os, subprocess, ctypes, time

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2"
try:
    k = ctypes.windll.kernel32
    k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS（子にも継がれる）
except Exception:
    pass
for rid in sys.argv[1:]:
    rd = os.path.join(P2, rid)
    for f in os.listdir(rd):
        if f.startswith("clay_") and (f.endswith(".png") or f.endswith(".json")):
            os.remove(os.path.join(rd, f))
    t0 = time.time()
    with open(os.path.join(P2, "logs", rid + "_final.log"), "w", encoding="utf8") as lf:
        subprocess.run([sys.executable, os.path.join(HERE, "p2_post.py"), rd], stdout=lf, stderr=subprocess.STDOUT)
    print(rid, "done", round(time.time() - t0), "s"); sys.stdout.flush()
